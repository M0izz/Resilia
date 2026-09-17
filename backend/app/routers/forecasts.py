"""
RESILIA Forecast Endpoints — Sprint 2
=======================================
Provides 14-day predictive intelligence for PHC facilities.
"""
from fastapi import APIRouter, HTTPException, Query
from boto3.dynamodb.conditions import Key

from app.db.dynamodb import Tables, scan_all
from app.models.forecast import PHCForecast, MedicineForecast
from app.services.forecast_engine import (
    generate_phc_forecast,
    forecast_medicine_depletion,
    forecast_patient_demand,
)

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


def _load_phc(phc_id: str) -> dict:
    resp = Tables.phcs().get_item(Key={"phc_id": phc_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail=f"PHC '{phc_id}' not found")
    return item


def _load_inventory(phc_id: str) -> list[dict]:
    try:
        return Tables.inventory().query(
            KeyConditionExpression=Key("phc_id").eq(phc_id)
        ).get("Items", [])
    except Exception:
        return []


def _load_patient_history(phc_id: str, days: int = 30) -> list[dict]:
    """Query recent patient records for the PHC."""
    try:
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        resp = Tables.patients().query(
            KeyConditionExpression=(
                Key("phc_id").eq(phc_id) & Key("date").gte(cutoff)
            )
        )
        return resp.get("Items", [])
    except Exception:
        return []


@router.get("/phc/{phc_id}", response_model=PHCForecast)
async def get_phc_forecast(
    phc_id: str,
    horizon: int = Query(14, ge=1, le=30, description="Forecast horizon in days"),
):
    """
    Generate a comprehensive 14-day forecast for a Primary Health Centre.

    Returns:
      - Daily patient footfall projections with 90% confidence bands
      - Medicine depletion curves and exact stockout dates for critical medicines
      - Bed occupancy forecast with overflow probability
      - Staffing deficit days (WHO ratio violations)
      - Summary risk flags
    """
    phc = _load_phc(phc_id)
    inventory = _load_inventory(phc_id)
    patient_history = _load_patient_history(phc_id, days=30)

    forecast = generate_phc_forecast(
        phc_id=phc_id,
        phc_name=phc.get("name", phc_id),
        patient_history=patient_history,
        inventory_items=inventory,
        beds_occupied=int(phc.get("beds_occupied", 0)),
        beds_total=int(phc.get("beds_total", 20)),
        doctors_present=int(phc.get("doctors_present", 1)),
        horizon=horizon,
    )
    return forecast


@router.get("/phc/{phc_id}/medicine/{medicine_code}", response_model=MedicineForecast)
async def get_medicine_forecast(
    phc_id: str,
    medicine_code: str,
    horizon: int = Query(14, ge=1, le=30),
):
    """
    High-resolution depletion trajectory for a single medicine at a PHC.

    Returns daily projected stock levels, growth-adjusted daily consumption,
    cumulative depletion curve, and stockout probability with confidence interval.
    """
    from datetime import datetime

    phc = _load_phc(phc_id)

    # Load specific medicine inventory record
    try:
        resp = Tables.inventory().get_item(
            Key={"phc_id": phc_id, "medicine_code": medicine_code}
        )
        item = resp.get("Item")
    except Exception:
        item = None

    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"Medicine '{medicine_code}' not found for PHC '{phc_id}'",
        )

    patient_history = _load_patient_history(phc_id, days=30)
    patient_forecasts, _, baseline = forecast_patient_demand(patient_history, horizon)

    daily_consumption = float(item.get("daily_consumption", 0))
    if daily_consumption <= 0:
        raise HTTPException(
            status_code=422,
            detail="Medicine has zero daily consumption — cannot forecast depletion.",
        )

    current_stock = float(item.get("quantity", 0))
    depletion_curve, stockout_pred = forecast_medicine_depletion(
        medicine_code=medicine_code,
        medicine_name=item.get("medicine_name", medicine_code),
        current_stock=current_stock,
        daily_consumption=daily_consumption,
        unit=item.get("unit", "units"),
        patient_forecasts=patient_forecasts,
        baseline_daily_patients=baseline,
        criticality=item.get("criticality", "MEDIUM"),
        horizon=horizon,
    )

    return MedicineForecast(
        phc_id=phc_id,
        medicine_code=medicine_code,
        medicine_name=item.get("medicine_name", medicine_code),
        current_stock=current_stock,
        unit=item.get("unit", "units"),
        daily_consumption=daily_consumption,
        depletion_curve=depletion_curve,
        stockout_prediction=stockout_pred,
        forecast_generated_at=datetime.utcnow().isoformat(),
    )
