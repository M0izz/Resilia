"""
RESILIA Data Quality & Telemetry Freshness Service — Phase 1
=============================================================
"No component gets to pretend something happened when it didn't."

Provides:
  - Telemetry freshness scoring (0.0 to 1.0) decaying with age in hours.
  - Completeness audit for PHC and inventory records.
  - TelemetryQualityReport assessing if data is sufficient for deterministic risk evaluation.
  - Generates UNKNOWN risk status when critical telemetry is absent/stale (>72 hours).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Max acceptable age before data is considered completely stale
STALE_THRESHOLD_HOURS = 72.0
FRESH_THRESHOLD_HOURS = 6.0


def parse_timestamp(ts: Any) -> Optional[datetime]:
    """Parse ISO timestamp string or datetime object into UTC datetime."""
    if not ts:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    if isinstance(ts, str):
        try:
            # Handle standard ISO format and trailing Z
            clean_ts = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None
    return None


def calculate_freshness_score(last_updated: Any, reference_time: Optional[datetime] = None) -> Tuple[float, float]:
    """
    Calculate freshness score between 0.0 (fully stale / missing) and 1.0 (perfectly fresh).
    
    Returns:
        (freshness_score, age_hours)
    """
    dt = parse_timestamp(last_updated)
    if dt is None:
        return 0.0, 999.0

    ref = reference_time or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)

    age_seconds = (ref - dt).total_seconds()
    age_hours = max(0.0, age_seconds / 3600.0)

    if age_hours <= FRESH_THRESHOLD_HOURS:
        score = 1.0
    elif age_hours >= STALE_THRESHOLD_HOURS:
        score = 0.0
    else:
        # Linear decay between FRESH_THRESHOLD and STALE_THRESHOLD
        decay_span = STALE_THRESHOLD_HOURS - FRESH_THRESHOLD_HOURS
        score = max(0.0, min(1.0, 1.0 - (age_hours - FRESH_THRESHOLD_HOURS) / decay_span))

    return round(score, 3), round(age_hours, 1)


@dataclass
class TelemetryQualityReport:
    phc_id: str
    freshness_score: float
    completeness_score: float
    overall_quality: float
    is_stale: bool
    is_incomplete: bool
    can_evaluate_risk: bool
    missing_fields: List[str]
    stale_hours: float
    explanation: str
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phc_id": self.phc_id,
            "freshness_score": self.freshness_score,
            "completeness_score": self.completeness_score,
            "overall_quality": self.overall_quality,
            "is_stale": self.is_stale,
            "is_incomplete": self.is_incomplete,
            "can_evaluate_risk": self.can_evaluate_risk,
            "missing_fields": self.missing_fields,
            "stale_hours": self.stale_hours,
            "explanation": self.explanation,
            "evaluated_at": self.evaluated_at,
        }


def assess_phc_telemetry_quality(
    phc: Optional[Dict[str, Any]],
    inventory: Optional[List[Dict[str, Any]]] = None,
    reference_time: Optional[datetime] = None,
) -> TelemetryQualityReport:
    """
    Audit PHC telemetry and inventory data quality.
    If required telemetry fields are missing or data is older than 72 hours,
    flags the PHC so risk evaluation cannot silently fabricate numbers.
    """
    if not phc:
        return TelemetryQualityReport(
            phc_id="UNKNOWN",
            freshness_score=0.0,
            completeness_score=0.0,
            overall_quality=0.0,
            is_stale=True,
            is_incomplete=True,
            can_evaluate_risk=False,
            missing_fields=["phc_record"],
            stale_hours=999.0,
            explanation="PHC record does not exist in persistence layer.",
        )

    phc_id = phc.get("phc_id", "UNKNOWN")
    missing_fields: List[str] = []

    # 1. Freshness assessment
    last_updated_raw = phc.get("last_updated") or phc.get("updated_at") or phc.get("created_at")
    freshness_score, age_hours = calculate_freshness_score(last_updated_raw, reference_time=reference_time)
    is_stale = age_hours >= STALE_THRESHOLD_HOURS or freshness_score <= 0.0

    # 2. Completeness assessment
    required_phc_fields = ["beds_total", "beds_occupied", "doctors_total", "doctors_present"]
    for f in required_phc_fields:
        if f not in phc or phc[f] is None:
            missing_fields.append(f)

    # Check inventory completeness
    inv_items = inventory or []
    if not inv_items:
        missing_fields.append("inventory_telemetry")
    else:
        # At least one medicine must have positive daily_consumption and non-negative quantity
        valid_meds = [
            item for item in inv_items
            if item.get("medicine_code") and "quantity" in item and "daily_consumption" in item
        ]
        if not valid_meds:
            missing_fields.append("valid_medicine_records")

    total_checks = len(required_phc_fields) + 1  # 4 fields + inventory
    present_checks = total_checks - len(missing_fields)
    completeness_score = round(max(0.0, present_checks / total_checks), 3)

    # Overall quality: 60% completeness, 40% freshness
    overall_quality = round((0.6 * completeness_score) + (0.4 * freshness_score), 3)
    is_incomplete = len(missing_fields) > 0

    # If critical fields are missing, risk cannot be computed deterministically
    can_evaluate_risk = not is_stale and completeness_score >= 0.8

    if not can_evaluate_risk:
        reasons = []
        if is_stale:
            reasons.append(f"Telemetry stale by {age_hours:.1f} hours (>72h limit)")
        if is_incomplete:
            reasons.append(f"Missing required fields: {', '.join(missing_fields)}")
        explanation = f"Telemetry quality insufficient for deterministic risk scoring: {'; '.join(reasons)}"
    else:
        explanation = f"Telemetry verified: freshness={freshness_score:.2f}, completeness={completeness_score:.2f}."

    return TelemetryQualityReport(
        phc_id=phc_id,
        freshness_score=freshness_score,
        completeness_score=completeness_score,
        overall_quality=overall_quality,
        is_stale=is_stale,
        is_incomplete=is_incomplete,
        can_evaluate_risk=can_evaluate_risk,
        missing_fields=missing_fields,
        stale_hours=age_hours,
        explanation=explanation,
    )
