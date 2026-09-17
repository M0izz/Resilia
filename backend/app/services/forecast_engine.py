"""
RESILIA Predictive Forecast Engine — Sprint 2
===============================================
Machine learning & statistical engine for 14-day healthcare intelligence.

Algorithms used (all pure sklearn/numpy — zero C-compiler issues):
  - Ridge regression + PolynomialFeatures (degree 2) for trend fitting
  - Day-of-week one-hot encoding for seasonal correction
  - Residual std → 90% confidence intervals (z = 1.645)
  - Linear interpolation for exact stockout date calculation

Falls back gracefully to linear extrapolation when < 7 days of history.
"""
from __future__ import annotations

import logging
import math
import threading
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from app.models.forecast import (
    BedForecastPoint,
    DailyForecastPoint,
    MedicineDepletionPoint,
    MedicineForecast,
    PHCForecast,
    StaffingDeficitDay,
    StockOutPrediction,
)

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────

HORIZON_DAYS = 14
CI_Z = 1.645            # 90% confidence interval z-score
SURGE_THRESHOLD = 1.25  # P(footfall > 1.25× baseline) → "surge"
BED_OVERFLOW_PCT = 0.95 # bed overflow threshold
WHO_PATIENTS_PER_DOCTOR = 40.0   # WHO recommended max OPD per doctor per day

# ─── Sklearn lazy import (avoids import-time cost) ───────────────────────

_sklearn_lock = threading.Lock()
_Ridge = None
_PolynomialFeatures = None


def _load_sklearn():
    global _Ridge, _PolynomialFeatures
    if _Ridge is None:
        with _sklearn_lock:
            if _Ridge is None:
                from sklearn.linear_model import Ridge
                from sklearn.preprocessing import PolynomialFeatures
                _Ridge = Ridge
                _PolynomialFeatures = PolynomialFeatures


# ─── Internal helpers ─────────────────────────────────────────────────────

def _day_of_week_features(date_obj: datetime) -> np.ndarray:
    """One-hot encode day of week (0=Mon … 6=Sun) as 6 binary features."""
    dow = date_obj.weekday()
    ohe = np.zeros(6)
    if dow < 6:
        ohe[dow] = 1.0
    return ohe


def _build_feature_matrix(dates: list[datetime]) -> np.ndarray:
    """
    Build X matrix: [day_index, day_index², dow_0, …, dow_5]
    Using polynomial day index + day-of-week seasonal encoding.
    """
    features = []
    t0 = dates[0].toordinal()
    for d in dates:
        t = d.toordinal() - t0
        dow = _day_of_week_features(d)
        features.append([t, t * t, *dow])
    return np.array(features, dtype=float)


def _fit_predict(
    train_dates: list[datetime],
    y_train: np.ndarray,
    predict_dates: list[datetime],
) -> tuple[np.ndarray, float]:
    """
    Fit Ridge regression and return (predictions, residual_std).
    Falls back to linear trend when fewer than 5 training points.
    """
    n = len(train_dates)
    if n < 3:
        # Trivial: just return the mean
        mean_val = float(np.mean(y_train)) if n > 0 else 0.0
        preds = np.full(len(predict_dates), max(0.0, mean_val))
        return preds, mean_val * 0.2

    _load_sklearn()
    X_train = _build_feature_matrix(train_dates)
    X_pred  = _build_feature_matrix(predict_dates)

    if n < 7:
        # Linear only — skip quadratic term
        X_train = X_train[:, :1]   # only day_index
        X_pred  = X_pred[:, :1]

    try:
        model = _Ridge(alpha=1.0)
        model.fit(X_train, y_train)
        predictions = model.predict(X_pred)
        residuals = y_train - model.predict(X_train)
        residual_std = float(np.std(residuals))
    except Exception as exc:
        logger.warning("Ridge fit failed, falling back to mean: %s", exc)
        mean_val = float(np.mean(y_train))
        predictions = np.full(len(predict_dates), max(0.0, mean_val))
        residual_std = mean_val * 0.2

    predictions = np.maximum(0.0, predictions)
    return predictions, max(residual_std, 0.1)


# ─── Patient Demand Forecasting ──────────────────────────────────────────

def forecast_patient_demand(
    patient_history: list[dict],
    horizon: int = HORIZON_DAYS,
) -> tuple[list[DailyForecastPoint], float, float]:
    """
    Forecast OPD + IPD patient demand for the next `horizon` days.

    Args:
        patient_history: List of dicts with keys: date (YYYY-MM-DD),
                         total_opd, total_ipd
        horizon: Number of days to project

    Returns:
        (forecast_points, surge_probability, baseline_daily)
    """
    if not patient_history:
        today = datetime.utcnow().date()
        points = []
        for i in range(1, horizon + 1):
            d = (today + timedelta(days=i)).isoformat()
            points.append(DailyForecastPoint(
                date=d, day_index=i,
                predicted_opd=0, predicted_ipd=0, predicted_total=0,
                confidence_low=0, confidence_high=0,
            ))
        return points, 0.0, 0.0

    # Parse history
    records = sorted(patient_history, key=lambda r: r["date"])
    train_dates = [datetime.strptime(r["date"], "%Y-%m-%d") for r in records]
    y_opd = np.array([float(r.get("total_opd", 0)) for r in records])
    y_ipd = np.array([float(r.get("total_ipd", 0)) for r in records])

    baseline = float(np.mean(y_opd + y_ipd)) if len(records) > 0 else 0.0

    # Future dates
    last_date = train_dates[-1]
    future_dates = [last_date + timedelta(days=i) for i in range(1, horizon + 1)]

    pred_opd, std_opd = _fit_predict(train_dates, y_opd, future_dates)
    pred_ipd, std_ipd = _fit_predict(train_dates, y_ipd, future_dates)

    points: list[DailyForecastPoint] = []
    surge_count = 0

    for i, (fd, opd, ipd) in enumerate(zip(future_dates, pred_opd, pred_ipd)):
        total = opd + ipd
        ci_half = CI_Z * math.sqrt(std_opd**2 + std_ipd**2)
        if total > SURGE_THRESHOLD * baseline:
            surge_count += 1
        points.append(DailyForecastPoint(
            date=fd.strftime("%Y-%m-%d"),
            day_index=i + 1,
            predicted_opd=round(opd, 1),
            predicted_ipd=round(ipd, 1),
            predicted_total=round(total, 1),
            confidence_low=round(max(0, total - ci_half), 1),
            confidence_high=round(total + ci_half, 1),
        ))

    surge_prob = min(1.0, surge_count / horizon)
    return points, round(surge_prob, 3), round(baseline, 1)


# ─── Medicine Depletion & Stockout ────────────────────────────────────────

def forecast_medicine_depletion(
    medicine_code: str,
    medicine_name: str,
    current_stock: float,
    daily_consumption: float,
    unit: str,
    patient_forecasts: list[DailyForecastPoint],
    baseline_daily_patients: float,
    criticality: str = "MEDIUM",
    horizon: int = HORIZON_DAYS,
) -> tuple[list[MedicineDepletionPoint], StockOutPrediction]:
    """
    Project medicine stock depletion over `horizon` days.

    Consumption is scaled by projected patient growth ratio each day,
    ensuring medicine demand tracks disease burden changes.
    """
    today = datetime.utcnow().date()
    current_dos = current_stock / daily_consumption if daily_consumption > 0 else 999.0

    curve: list[MedicineDepletionPoint] = []
    remaining = current_stock
    cumulative_consumed = 0.0
    stockout_date: Optional[str] = None
    days_until_stockout: Optional[float] = None

    for i in range(1, horizon + 1):
        d = (today + timedelta(days=i)).isoformat()

        # Growth-adjusted daily consumption
        if baseline_daily_patients > 0 and i <= len(patient_forecasts):
            growth_ratio = patient_forecasts[i - 1].predicted_total / max(1.0, baseline_daily_patients)
            growth_ratio = max(0.5, min(growth_ratio, 3.0))  # clamp to [0.5, 3.0]
        else:
            growth_ratio = 1.0

        daily_use = daily_consumption * growth_ratio
        consumed_today = min(remaining, daily_use)
        cumulative_consumed += consumed_today
        remaining -= consumed_today
        remaining = max(0.0, remaining)

        # Exact stockout: interpolate between the day stock hits 0
        if stockout_date is None and remaining == 0.0 and consumed_today > 0:
            # Linear interpolation: how far into day i did stock run out?
            frac = (remaining + consumed_today) / daily_use if daily_use > 0 else 0.0
            exact_days = (i - 1) + frac
            stockout_date = (today + timedelta(days=exact_days)).isoformat()
            days_until_stockout = round(exact_days, 1)

        curve.append(MedicineDepletionPoint(
            date=d,
            day_index=i,
            projected_stock=round(remaining, 2),
            daily_consumption_projected=round(daily_use, 2),
            cumulative_consumed=round(cumulative_consumed, 2),
        ))

    # Stockout probability — based on current days-of-stock vs horizon
    if current_dos <= 0:
        stockout_prob = 1.0
    elif current_dos >= horizon * 2:
        stockout_prob = 0.0
    else:
        # Sigmoid-like: probability rises as DOS shrinks relative to horizon
        stockout_prob = round(
            1.0 / (1.0 + math.exp(0.3 * (current_dos - horizon * 0.5))),
            3,
        )

    within_horizon = stockout_date is not None

    # Risk level
    if days_until_stockout is not None:
        if days_until_stockout <= 3:
            risk_level = "CRITICAL"
        elif days_until_stockout <= 7:
            risk_level = "HIGH"
        elif days_until_stockout <= 14:
            risk_level = "WATCH"
        else:
            risk_level = "NORMAL"
    else:
        risk_level = "NORMAL"

    # CI: ±15% of days_until_stockout (uncertainty from consumption variance)
    ci_days = round(days_until_stockout * 0.15, 1) if days_until_stockout else None

    prediction = StockOutPrediction(
        medicine_code=medicine_code,
        medicine_name=medicine_name,
        current_stock=current_stock,
        current_days_of_stock=round(current_dos, 1),
        daily_consumption_baseline=daily_consumption,
        stockout_date=stockout_date,
        days_until_stockout=days_until_stockout,
        stockout_probability=stockout_prob,
        confidence_interval_days=ci_days,
        within_horizon=within_horizon,
        risk_level=risk_level,
    )
    return curve, prediction


# ─── Bed Occupancy Forecast ───────────────────────────────────────────────

def forecast_bed_occupancy(
    beds_occupied: int,
    beds_total: int,
    patient_forecasts: list[DailyForecastPoint],
    baseline_daily_patients: float,
    horizon: int = HORIZON_DAYS,
) -> tuple[list[BedForecastPoint], float]:
    """
    Project bed occupancy over `horizon` days using patient growth rate.
    Returns (forecast_points, overflow_probability).
    """
    today = datetime.utcnow().date()
    overflow_days = 0
    points: list[BedForecastPoint] = []

    for i in range(1, horizon + 1):
        d = (today + timedelta(days=i)).isoformat()

        if baseline_daily_patients > 0 and i <= len(patient_forecasts):
            growth = patient_forecasts[i - 1].predicted_total / max(1.0, baseline_daily_patients)
        else:
            growth = 1.0

        projected = min(beds_total, beds_occupied * growth)
        pct = (projected / beds_total * 100.0) if beds_total > 0 else 0.0

        # Overflow probability: logistic function around 95% threshold
        overflow_prob = round(
            1.0 / (1.0 + math.exp(-6.0 * (pct / 100.0 - BED_OVERFLOW_PCT))),
            3,
        )
        if overflow_prob >= 0.5:
            overflow_days += 1

        points.append(BedForecastPoint(
            date=d,
            day_index=i,
            projected_occupancy=round(projected, 1),
            projected_occupancy_pct=round(pct, 1),
            capacity_limit=beds_total,
            overflow_probability=overflow_prob,
        ))

    overflow_prob_overall = round(overflow_days / horizon, 3) if horizon > 0 else 0.0
    return points, overflow_prob_overall


# ─── Staffing Deficit Forecast ────────────────────────────────────────────

def forecast_staffing_deficit(
    doctors_present: int,
    patient_forecasts: list[DailyForecastPoint],
    horizon: int = HORIZON_DAYS,
    who_threshold: float = WHO_PATIENTS_PER_DOCTOR,
) -> list[StaffingDeficitDay]:
    """
    Compute days where projected patient volume exceeds staff capacity.
    Uses WHO benchmark of ~40 OPD visits per doctor per day.
    """
    today = datetime.utcnow().date()
    max_capacity = doctors_present * who_threshold
    result: list[StaffingDeficitDay] = []

    for i in range(1, horizon + 1):
        d = (today + timedelta(days=i)).isoformat()
        if i <= len(patient_forecasts):
            predicted = patient_forecasts[i - 1].predicted_opd
        else:
            predicted = max_capacity  # assume no deficit beyond data

        ratio = predicted / max(1.0, doctors_present)
        deficit = ratio > who_threshold

        if deficit:
            excess_pct = (ratio - who_threshold) / who_threshold
            if excess_pct > 0.5:
                severity = "CRITICAL"
            elif excess_pct > 0.25:
                severity = "HIGH"
            else:
                severity = "WATCH"
        else:
            severity = "NORMAL"

        result.append(StaffingDeficitDay(
            date=d,
            day_index=i,
            predicted_patients=round(predicted, 1),
            patients_per_doctor=round(ratio, 1),
            who_threshold=who_threshold,
            deficit=deficit,
            deficit_severity=severity,
        ))

    return result


# ─── Composite PHC Forecast Orchestrator ─────────────────────────────────

def generate_phc_forecast(
    phc_id: str,
    phc_name: str,
    patient_history: list[dict],
    inventory_items: list[dict],
    beds_occupied: int,
    beds_total: int,
    doctors_present: int,
    horizon: int = HORIZON_DAYS,
) -> PHCForecast:
    """
    Orchestrate all sub-forecasts for a PHC into a single PHCForecast.

    Args:
        phc_id:           PHC identifier
        phc_name:         PHC display name
        patient_history:  List of patient daily records from DynamoDB
        inventory_items:  List of inventory records from DynamoDB
        beds_occupied:    Current occupied beds
        beds_total:       Total bed capacity
        doctors_present:  Number of doctors on duty today
        horizon:          Forecast horizon in days
    """
    now_iso = datetime.utcnow().isoformat()

    # 1. Patient demand forecast
    patient_forecasts, surge_prob, baseline_daily = forecast_patient_demand(
        patient_history, horizon
    )

    # 2. Bed occupancy forecast
    bed_forecasts, bed_overflow_prob = forecast_bed_occupancy(
        beds_occupied, beds_total, patient_forecasts, baseline_daily, horizon
    )

    # 3. Medicine depletion — only CRITICAL and HIGH criticality medicines
    medicine_stockouts: list[StockOutPrediction] = []
    for item in inventory_items:
        criticality = item.get("criticality", "LOW")
        if criticality not in ("CRITICAL", "HIGH"):
            continue
        daily_consumption = float(item.get("daily_consumption", 0))
        if daily_consumption <= 0:
            continue
        current_stock = float(item.get("quantity", 0))
        _, stockout_pred = forecast_medicine_depletion(
            medicine_code=item.get("medicine_code", ""),
            medicine_name=item.get("medicine_name", ""),
            current_stock=current_stock,
            daily_consumption=daily_consumption,
            unit=item.get("unit", "units"),
            patient_forecasts=patient_forecasts,
            baseline_daily_patients=baseline_daily,
            criticality=criticality,
            horizon=horizon,
        )
        medicine_stockouts.append(stockout_pred)

    # Sort by urgency (lowest days_until_stockout first)
    medicine_stockouts.sort(
        key=lambda s: s.days_until_stockout if s.days_until_stockout is not None else 9999
    )

    # 4. Staffing deficit
    staffing_deficit_days = forecast_staffing_deficit(
        doctors_present, patient_forecasts, horizon
    )
    total_deficit_days = sum(1 for d in staffing_deficit_days if d.deficit)

    # 5. Summary flags
    has_imminent_stockout = any(
        s.days_until_stockout is not None and s.days_until_stockout <= 7
        for s in medicine_stockouts
    )
    has_bed_overflow_risk = bed_overflow_prob >= 0.5
    has_staffing_gap = total_deficit_days > 3

    return PHCForecast(
        phc_id=phc_id,
        phc_name=phc_name,
        forecast_generated_at=now_iso,
        horizon_days=horizon,
        patient_forecasts=patient_forecasts,
        surge_probability=surge_prob,
        baseline_daily_patients=baseline_daily,
        bed_forecasts=bed_forecasts,
        bed_overflow_probability=bed_overflow_prob,
        bed_capacity=beds_total,
        medicine_stockouts=medicine_stockouts,
        staffing_deficit_days=staffing_deficit_days,
        total_deficit_days=total_deficit_days,
        has_imminent_stockout=has_imminent_stockout,
        has_bed_overflow_risk=has_bed_overflow_risk,
        has_staffing_gap=has_staffing_gap,
    )
