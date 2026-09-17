from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from boto3.dynamodb.conditions import Key
from app.db.dynamodb import Tables
from app.models.patient import DailyPatientRecord, PatientSummary
from datetime import datetime, timedelta, date

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/{phc_id}", response_model=list[DailyPatientRecord])
async def get_patient_history(phc_id: str, days: int = Query(7, ge=1, le=90)):
    """Daily patient records for the last N days."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
    resp = Tables.patients().query(
        KeyConditionExpression=Key("phc_id").eq(phc_id) & Key("date").gte(cutoff),
        ScanIndexForward=False,
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail=f"No patient records for {phc_id}")
    return items


@router.get("/{phc_id}/summary", response_model=PatientSummary)
async def get_patient_summary(phc_id: str):
    """7-day footfall summary with trend calculation."""
    cutoff = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
    resp = Tables.patients().query(
        KeyConditionExpression=Key("phc_id").eq(phc_id) & Key("date").gte(cutoff),
        ScanIndexForward=False,
    )
    records = resp.get("Items", [])
    if not records:
        raise HTTPException(status_code=404, detail="No patient data")

    sorted_recs = sorted(records, key=lambda r: r["date"], reverse=True)
    today_rec = sorted_recs[0]
    today_opd = int(today_rec.get("total_opd", 0))
    today_ipd = int(today_rec.get("total_ipd", 0))

    opd_values = [int(r.get("total_opd", 0)) for r in sorted_recs]
    avg_7d = sum(opd_values) / len(opd_values) if opd_values else 0

    # Trend vs 7 days ago
    if len(opd_values) >= 7:
        change_pct = round((opd_values[0] - opd_values[-1]) / max(opd_values[-1], 1) * 100, 1)
    else:
        change_pct = 0.0

    trend = "rising" if change_pct > 5 else ("falling" if change_pct < -5 else "stable")

    # Aggregate disease breakdown
    disease_totals: dict[str, int] = {}
    for r in sorted_recs:
        for disease, count in (r.get("disease_breakdown") or {}).items():
            disease_totals[disease] = disease_totals.get(disease, 0) + int(count)

    top_diseases = sorted(
        [{"disease": k, "count": v} for k, v in disease_totals.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    return PatientSummary(
        phc_id=phc_id,
        today_opd=today_opd,
        today_ipd=today_ipd,
        avg_7d_opd=round(avg_7d, 1),
        trend=trend,
        change_7d_pct=change_pct,
        top_diseases=top_diseases,
    )
