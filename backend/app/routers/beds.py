from fastapi import APIRouter, HTTPException, Query
from boto3.dynamodb.conditions import Key
from app.db.dynamodb import Tables, scan_all
from app.services.risk_engine import bed_utilization_pct

router = APIRouter(prefix="/beds", tags=["beds"])


@router.get("/{phc_id}")
async def get_bed_status(phc_id: str):
    """Current bed occupancy for a PHC."""
    resp = Tables.phcs().get_item(Key={"phc_id": phc_id})
    phc = resp.get("Item")
    if not phc:
        raise HTTPException(status_code=404, detail=f"PHC {phc_id} not found")

    total = int(phc.get("beds_total", 0))
    occupied = int(phc.get("beds_occupied", 0))
    icu = int(phc.get("beds_icu", 0))
    available = max(0, total - occupied)
    rate = bed_utilization_pct(occupied, total)

    return {
        "phc_id": phc_id,
        "beds_total": total,
        "beds_occupied": occupied,
        "beds_available": available,
        "beds_icu": icu,
        "utilization_pct": rate,
        "status": (
            "CRITICAL" if rate >= 95 else
            "HIGH"     if rate >= 85 else
            "MODERATE" if rate >= 75 else
            "NORMAL"
        ),
    }


@router.get("/district/utilization")
async def district_bed_utilization(
    state_code: str = Query(...),
    district_code: str = Query(...),
):
    """Aggregate bed stats for every PHC in a district."""
    from app.db.dynamodb import query_gsi
    from boto3.dynamodb.conditions import Key as K
    phcs = query_gsi(
        "resilia-phcs", "State-Index",
        K("state_code").eq(state_code) & K("district_code").eq(district_code),
    )
    results = []
    for p in phcs:
        total = int(p.get("beds_total", 0))
        occupied = int(p.get("beds_occupied", 0))
        results.append({
            "phc_id": p["phc_id"],
            "name": p.get("name", ""),
            "beds_total": total,
            "beds_occupied": occupied,
            "beds_available": max(0, total - occupied),
            "utilization_pct": bed_utilization_pct(occupied, total),
        })
    return sorted(results, key=lambda x: x["utilization_pct"], reverse=True)
