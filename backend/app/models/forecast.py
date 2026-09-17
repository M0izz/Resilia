"""
RESILIA Forecast Models — Sprint 2
===================================
Pydantic models for 14-day predictive intelligence outputs.
"""
from pydantic import BaseModel, Field
from typing import Optional


# ─── Patient Demand Forecast ─────────────────────────────────────────────

class DailyForecastPoint(BaseModel):
    """Single day prediction for patient footfall."""
    date: str                              # ISO date YYYY-MM-DD
    day_index: int                         # 1–14 from today
    predicted_opd: float                   # Outpatient count
    predicted_ipd: float                   # Inpatient count
    predicted_total: float
    confidence_low: float                  # 90% CI lower bound
    confidence_high: float                 # 90% CI upper bound


# ─── Medicine Depletion Curve ─────────────────────────────────────────────

class MedicineDepletionPoint(BaseModel):
    """Stock level at a given projected day."""
    date: str
    day_index: int
    projected_stock: float
    daily_consumption_projected: float
    cumulative_consumed: float


class StockOutPrediction(BaseModel):
    """Stockout risk summary for one medicine."""
    medicine_code: str
    medicine_name: str
    current_stock: float
    current_days_of_stock: float
    daily_consumption_baseline: float
    stockout_date: Optional[str] = None    # ISO date, None if > 14 days
    days_until_stockout: Optional[float] = None  # None if safe within horizon
    stockout_probability: float = Field(ge=0.0, le=1.0)
    confidence_interval_days: Optional[float] = None  # ±N days uncertainty
    within_horizon: bool                   # True if stockout within 14 days
    risk_level: str                        # CRITICAL / HIGH / WATCH / NORMAL


# ─── Bed Occupancy Forecast ───────────────────────────────────────────────

class BedForecastPoint(BaseModel):
    """Projected bed occupancy for one day."""
    date: str
    day_index: int
    projected_occupancy: float             # absolute count
    projected_occupancy_pct: float         # 0–100
    capacity_limit: int
    overflow_probability: float = Field(ge=0.0, le=1.0)


# ─── Staffing Deficit Forecast ────────────────────────────────────────────

class StaffingDeficitDay(BaseModel):
    """Day where patient load exceeds current staff capacity."""
    date: str
    day_index: int
    predicted_patients: float
    patients_per_doctor: float             # projected ratio
    who_threshold: float                   # recommended max ratio
    deficit: bool                          # True if ratio exceeds threshold
    deficit_severity: str                  # NORMAL / WATCH / HIGH / CRITICAL


# ─── Composite PHC Forecast ───────────────────────────────────────────────

class PHCForecast(BaseModel):
    """Complete 14-day forecast for a single PHC."""
    phc_id: str
    phc_name: str
    forecast_generated_at: str             # ISO datetime
    horizon_days: int = 14

    # Patient footfall
    patient_forecasts: list[DailyForecastPoint]
    surge_probability: float = Field(ge=0.0, le=1.0)  # P(footfall > 1.25× baseline)
    baseline_daily_patients: float

    # Beds
    bed_forecasts: list[BedForecastPoint]
    bed_overflow_probability: float = Field(ge=0.0, le=1.0)  # P(>95% capacity)
    bed_capacity: int

    # Medicine stockouts (critical medicines only)
    medicine_stockouts: list[StockOutPrediction]

    # Staffing
    staffing_deficit_days: list[StaffingDeficitDay]
    total_deficit_days: int

    # Summary flags
    has_imminent_stockout: bool            # stockout within 7 days
    has_bed_overflow_risk: bool            # >50% probability of overflow
    has_staffing_gap: bool


# ─── Per-Medicine Forecast (detailed endpoint) ─────────────────────────────

class MedicineForecast(BaseModel):
    """Detailed depletion trajectory for a single medicine at a PHC."""
    phc_id: str
    medicine_code: str
    medicine_name: str
    current_stock: float
    unit: str
    daily_consumption: float
    depletion_curve: list[MedicineDepletionPoint]
    stockout_prediction: StockOutPrediction
    forecast_generated_at: str
