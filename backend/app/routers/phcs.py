from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from boto3.dynamodb.conditions import Key, Attr
from app.db.dynamodb import Tables, scan_all, query_gsi
from app.models.phc import PHC, PHCSummary, NetworkSummary
from app.models.common import RiskSeverity
from app.services import risk_engine

router = APIRouter(prefix="/phcs", tags=["phcs"])


@router.get("", response_model=list[PHCSummary])
async def list_phcs(
    state_code: Optional[str] = Query(None),
    district_code: Optional[str] = Query(None),
    severity: Optional[RiskSeverity] = Query(None),
    limit: int = Query(200, le=500),
):
    """
    List PHCs with optional state/district/severity filters.
    Returns lightweight PHCSummary for map rendering.
    """
    if state_code:
        if district_code:
            items = query_gsi(
                "resilia-phcs", "State-Index",
                Key("state_code").eq(state_code) & Key("district_code").eq(district_code),
            )
        else:
            items = query_gsi(
                "resilia-phcs", "State-Index",
                Key("state_code").eq(state_code),
            )
    else:
        items = scan_all("resilia-phcs")

    if severity:
        items = [i for i in items if i.get("risk_severity") == severity.value]

    return items[:limit]


@router.get("/network-summary", response_model=NetworkSummary)
async def network_summary(state_code: Optional[str] = Query(None)):
    """
    Aggregate national (or state) statistics for the command center KPI strip.
    """
    if state_code:
        items = query_gsi("resilia-phcs", "State-Index", Key("state_code").eq(state_code))
    else:
        items = scan_all("resilia-phcs")

    if not items:
        raise HTTPException(status_code=404, detail="No PHCs found")

    counts = {s: 0 for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
    total_alerts = 0
    bed_rates, doc_rates = [], []
    total_patients = 0

    for p in items:
        sev = p.get("risk_severity", "LOW")
        counts[sev] = counts.get(sev, 0) + 1
        total_alerts += int(p.get("active_alerts", 0))

        bt = int(p.get("beds_total", 0))
        bo = int(p.get("beds_occupied", 0))
        if bt > 0:
            bed_rates.append(bo / bt)

        dt = int(p.get("doctors_total", 0))
        dp = int(p.get("doctors_present", 0))
        if dt > 0:
            doc_rates.append(dp / dt)

    # Count medicine shortages: PHCs with any active STOCKOUT_RISK alerts
    stockout_alerts = scan_all("resilia-alerts", Attr("alert_type").eq("STOCKOUT_RISK"))
    shortage_phcs = len({a["phc_id"] for a in stockout_alerts})

    return NetworkSummary(
        total_phcs=len(items),
        critical=counts["CRITICAL"],
        high=counts["HIGH"],
        medium=counts["MEDIUM"],
        low=counts["LOW"],
        active_alerts=total_alerts,
        medicine_shortages=shortage_phcs,
        avg_bed_utilization=round(sum(bed_rates) / len(bed_rates) * 100, 1) if bed_rates else 0.0,
        avg_doctor_attendance=round(sum(doc_rates) / len(doc_rates) * 100, 1) if doc_rates else 0.0,
        total_patients_today=total_patients,
        pending_interventions=0,   # filled by interventions router in future
    )


@router.get("/states")
async def list_states():
    """Return distinct state codes and names from the PHC table."""
    items = scan_all("resilia-phcs")
    seen = {}
    for p in items:
        sc = p.get("state_code")
        if sc and sc not in seen:
            seen[sc] = p.get("state", sc)
    return [{"state_code": k, "state": v} for k, v in sorted(seen.items())]


@router.get("/districts")
async def list_districts(state_code: str = Query(...)):
    """Return distinct districts for a given state."""
    items = query_gsi("resilia-phcs", "State-Index", Key("state_code").eq(state_code))
    seen = {}
    for p in items:
        dc = p.get("district_code")
        if dc and dc not in seen:
            seen[dc] = p.get("district", dc)
    return [{"district_code": k, "district": v} for k, v in sorted(seen.items())]


@router.get("/{phc_id}", response_model=PHC)
async def get_phc(phc_id: str):
    """Fetch a single PHC by ID."""
    resp = Tables.phcs().get_item(Key={"phc_id": phc_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail=f"PHC {phc_id} not found")

    # Enrich computed fields
    item["bed_utilization_pct"] = risk_engine.bed_utilization_pct(
        int(item.get("beds_occupied", 0)), int(item.get("beds_total", 1))
    )
    item["doctor_attendance_pct"] = risk_engine.doctor_attendance_pct(
        int(item.get("doctors_present", 0)), int(item.get("doctors_total", 1))
    )
    item["nurse_attendance_pct"] = risk_engine.nurse_attendance_pct(
        int(item.get("nurses_present", 0)), int(item.get("nurses_total", 1))
    )
    return item


@router.post("/{phc_id}/recalculate-risk")
async def recalculate_risk(phc_id: str):
    """
    Re-run the risk engine for a single PHC using current DynamoDB data.
    Updates the PHC record in place.
    """
    phc_resp = Tables.phcs().get_item(Key={"phc_id": phc_id})
    phc = phc_resp.get("Item")
    if not phc:
        raise HTTPException(status_code=404, detail=f"PHC {phc_id} not found")

    # Load inventory
    inv_resp = Tables.inventory().query(
        KeyConditionExpression=Key("phc_id").eq(phc_id)
    )
    inventory = inv_resp.get("Items", [])

    # Build risk input
    med_inputs = [
        risk_engine.MedicineRiskInput(
            medicine_code=i["medicine_code"],
            medicine_name=i["medicine_name"],
            quantity=float(i.get("quantity", 0)),
            daily_consumption=float(i.get("daily_consumption", 1)),
            criticality=i.get("criticality", "MEDIUM"),
        )
        for i in inventory
    ]

    inp = risk_engine.PHCRiskInput(
        phc_id=phc_id,
        beds_total=int(phc.get("beds_total", 0)),
        beds_occupied=int(phc.get("beds_occupied", 0)),
        doctors_total=int(phc.get("doctors_total", 0)),
        doctors_present=int(phc.get("doctors_present", 0)),
        medicines=med_inputs,
    )

    result = risk_engine.score_phc(inp)

    # Update DynamoDB
    from datetime import datetime
    Tables.phcs().update_item(
        Key={"phc_id": phc_id},
        UpdateExpression="SET risk_score = :rs, risk_severity = :rv, risk_factors = :rf, last_updated = :lu",
        ExpressionAttributeValues={
            ":rs": result.risk_score,
            ":rv": result.risk_severity.value,
            ":rf": result.factors,
            ":lu": datetime.utcnow().isoformat(),
        },
    )

    return {
        "phc_id": phc_id,
        "risk_score": result.risk_score,
        "risk_severity": result.risk_severity,
        "factors": result.factors,
        "components": {
            "medicine": result.medicine_score,
            "beds": result.bed_score,
            "doctors": result.doctor_score,
            "surge": result.surge_score,
            "supplier": result.supplier_score,
        },
    }
