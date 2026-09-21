"""
RESILIA Healthcare Risk Engine — Sprint 2
==========================================
Sprint 1: Deterministic, rule-based risk scoring.
Sprint 2: Multi-factor cascading risk with non-linear interaction multiplier.

Base risk score = sum of component scores, capped at 100.
Cascading multiplier applied when ≥2 compounding factors are active:
  Any 2 factors   → ×1.2–1.4
  All 3 factors   → ×1.6  (low stock + patient surge + supplier delay)

Severity buckets (Sprint 2):
  0–24   NORMAL   (green)
  25–49  WATCH    (blue)
  50–74  HIGH     (orange)
  75–100 CRITICAL (red)

Legacy aliases LOW/MEDIUM remain for backward compatibility with seeded data.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from app.models.common import RiskSeverity, RiskCategory


# ─── Scoring constants ────────────────────────────────────────────────────

# Stock-out risk (max 40 pts)
STOCK_SCORE = {
    "critical_3d":   40,   # < 3 days of stock
    "critical_7d":   30,   # < 7 days
    "warning_14d":   15,   # < 14 days
    "ok":             0,
}

# Bed utilization (max 20 pts)
BED_SCORE = {
    "overflow_95":   20,   # > 95%
    "high_85":       12,   # > 85%
    "moderate_75":    6,   # > 75%
    "ok":             0,
}

# Doctor attendance (max 20 pts)
DOCTOR_SCORE = {
    "severe_50":     20,   # < 50% present
    "low_75":        12,   # < 75%
    "partial_100":    6,   # < 100%
    "full":           0,
}

# Patient surge (7-day trend) (max 20 pts)
SURGE_SCORE = {
    "high_30":       20,   # > 30% above 7-day avg
    "moderate_15":   12,   # > 15%
    "low_5":          6,   # > 5%
    "stable":         0,
}

# Supplier delay (bonus risk, max 15 pts)
SUPPLIER_SCORE = {
    "severe_7d":     15,   # delay > 7 days
    "moderate_3d":   10,   # delay > 3 days
    "minor":          5,   # any delay
    "none":           0,
}

# Criticality multipliers applied to the medicine component only
CRITICALITY_MULT = {
    "CRITICAL": 1.5,
    "HIGH":     1.25,
    "MEDIUM":   1.0,
    "LOW":      0.75,
}

SEVERITY_THRESHOLDS = {
    RiskSeverity.CRITICAL: 75,
    RiskSeverity.HIGH:     50,
    RiskSeverity.WATCH:    25,
    RiskSeverity.NORMAL:    0,
}

# ── Cascading multiplier thresholds ──────────────────────────────────────
# Triggered when multiple compounding factors co-occur.
# Formula: base_score × cascade_multiplier (capped at 100)
CASCADE_MULTIPLIER_ALL3  = 1.6   # low stock + surge + supplier delay
CASCADE_MULTIPLIER_STOCK_SURGE    = 1.4   # low stock + patient surge
CASCADE_MULTIPLIER_STOCK_SUPPLIER = 1.35  # low stock + supplier delay
CASCADE_MULTIPLIER_SURGE_SUPPLIER = 1.2   # surge + supplier delay only


# ─── Data inputs ─────────────────────────────────────────────────────────

@dataclass
class MedicineRiskInput:
    medicine_code: str
    medicine_name: str
    quantity: float
    daily_consumption: float
    criticality: str          # CRITICAL / HIGH / MEDIUM / LOW
    supplier_delayed: bool = False
    delay_days: int = 0
    expiry_days: int = 365    # days until expiry


@dataclass
class PHCRiskInput:
    phc_id: str
    beds_total: int
    beds_occupied: int
    doctors_total: int
    doctors_present: int
    patient_7d_change_pct: float = 0.0
    medicines: list[MedicineRiskInput] = field(default_factory=list)
    supplier_delay_days: int = 0


# ─── Output types ─────────────────────────────────────────────────────────

@dataclass
class MedicineRiskResult:
    medicine_code: str
    medicine_name: str
    days_of_stock: float
    risk_score: int
    risk_severity: RiskSeverity
    factors: list[str]


@dataclass
class PHCRiskResult:
    phc_id: str
    risk_score: int
    risk_severity: RiskSeverity
    factors: list[str]

    # Component breakdown
    medicine_score: int
    bed_score: int
    doctor_score: int
    surge_score: int
    supplier_score: int

    # Worst medicine
    worst_medicine: Optional[str]
    worst_days_of_stock: Optional[float]
    medicine_details: list[MedicineRiskResult]


@dataclass
class MultiFactorRiskResult:
    """Sprint 2 & Phase 3: Enhanced risk result with cascading compound analysis and audited factor attribution."""
    phc_id: str

    # Final cascaded score (base × multiplier, capped at 100)
    risk_score: int
    risk_severity: RiskSeverity
    primary_category: RiskCategory

    # Base additive score before cascade
    base_score: int

    # Cascade metadata
    cascade_multiplier: float            # 1.0 = no cascade; up to 1.6
    active_compounding_factors: list[str]  # human-readable trigger list

    # Component sub-scores (pre-cascade)
    sub_scores: dict                     # {"medicine": int, "bed": int, ...}
    factor_contributions: dict           # Percentage contribution of each factor to base risk

    # Audited policy and triggered rules
    policy_version: str = "2026.03.1"
    triggered_rules: list[str] = field(default_factory=list)

    # Worst medicine reference
    worst_medicine: Optional[str] = None
    worst_days_of_stock: Optional[float] = None
    medicine_details: list[MedicineRiskResult] = field(default_factory=list)

    # Plain-English agent explanation
    agent_explanation: str = ""

    # Full factor list from base scoring
    factors: list[str] = field(default_factory=list)


# ─── Core calculations ────────────────────────────────────────────────────

def days_of_stock(quantity: float, daily_consumption: float) -> float:
    """
    Medicine Risk = current stock ÷ average daily consumption.
    Returns 999.0 if consumption is zero (no risk).
    """
    if daily_consumption <= 0:
        return 999.0
    return round(quantity / daily_consumption, 1)


def score_medicine(inp: MedicineRiskInput) -> MedicineRiskResult:
    """
    Score an individual medicine.
    Base score from days-of-stock table, then multiply by criticality.
    """
    dos = days_of_stock(inp.quantity, inp.daily_consumption)
    factors: list[str] = []

    # Base stock score
    if dos < 3:
        base = STOCK_SCORE["critical_3d"]
        factors.append(f"< 3 days of stock ({dos:.1f}d)")
    elif dos < 7:
        base = STOCK_SCORE["critical_7d"]
        factors.append(f"< 7 days of stock ({dos:.1f}d)")
    elif dos < 14:
        base = STOCK_SCORE["warning_14d"]
        factors.append(f"< 14 days of stock ({dos:.1f}d)")
    else:
        base = STOCK_SCORE["ok"]

    # Supplier delay amplifier (applied before criticality mult)
    if inp.supplier_delayed:
        if inp.delay_days >= 7:
            base = min(base + SUPPLIER_SCORE["severe_7d"], 40)
            factors.append(f"Supplier delay {inp.delay_days}d (severe)")
        elif inp.delay_days >= 3:
            base = min(base + SUPPLIER_SCORE["moderate_3d"], 40)
            factors.append(f"Supplier delay {inp.delay_days}d")
        else:
            base = min(base + SUPPLIER_SCORE["minor"], 40)
            factors.append("Supplier delay (minor)")

    # Expiry warning
    if 0 < inp.expiry_days <= 30:
        base = min(base + 10, 40)
        factors.append(f"Expiring in {inp.expiry_days}d")
    elif 0 < inp.expiry_days <= 60:
        base = min(base + 5, 40)
        factors.append(f"Expiring in {inp.expiry_days}d")

    # Apply criticality multiplier
    mult = CRITICALITY_MULT.get(inp.criticality, 1.0)
    score = min(100, int(base * mult))

    return MedicineRiskResult(
        medicine_code=inp.medicine_code,
        medicine_name=inp.medicine_name,
        days_of_stock=dos,
        risk_score=score,
        risk_severity=severity_from_score(score),
        factors=factors,
    )


def score_phc(inp: PHCRiskInput) -> PHCRiskResult:
    """
    Compute the composite PHC risk score from all components.

    Components (max contribution):
      medicine_score : 40 pts  (worst critical medicine)
      bed_score      : 20 pts
      doctor_score   : 20 pts
      surge_score    : 20 pts
      supplier_score : 15 pts  (additional, separate from medicine supplier)

    Total capped at 100.
    """
    factors: list[str] = []

    # ── Medicine component ──
    med_results = [score_medicine(m) for m in inp.medicines]
    critical_meds = [r for r in med_results if r.medicine_code in
                     {m.medicine_code for m in inp.medicines if m.criticality in ("CRITICAL", "HIGH")}]
    if critical_meds:
        worst = max(critical_meds, key=lambda r: r.risk_score)
        medicine_score = worst.risk_score
        worst_medicine = worst.medicine_name
        worst_dos = worst.days_of_stock
        if worst.risk_score >= 30:
            factors.extend(worst.factors)
    else:
        medicine_score = 0
        worst_medicine = None
        worst_dos = None

    # ── Bed utilization component ──
    if inp.beds_total > 0:
        bed_rate = inp.beds_occupied / inp.beds_total
    else:
        bed_rate = 0.0

    if bed_rate > 0.95:
        bed_score = BED_SCORE["overflow_95"]
        factors.append(f"Bed occupancy critical ({bed_rate:.0%})")
    elif bed_rate > 0.85:
        bed_score = BED_SCORE["high_85"]
        factors.append(f"Bed occupancy high ({bed_rate:.0%})")
    elif bed_rate > 0.75:
        bed_score = BED_SCORE["moderate_75"]
        factors.append(f"Bed occupancy elevated ({bed_rate:.0%})")
    else:
        bed_score = BED_SCORE["ok"]

    # ── Doctor attendance component ──
    if inp.doctors_total > 0:
        doc_rate = inp.doctors_present / inp.doctors_total
    else:
        doc_rate = 1.0

    if doc_rate < 0.50:
        doctor_score = DOCTOR_SCORE["severe_50"]
        factors.append(f"Severe doctor shortage ({doc_rate:.0%} present)")
    elif doc_rate < 0.75:
        doctor_score = DOCTOR_SCORE["low_75"]
        factors.append(f"Doctor shortage ({doc_rate:.0%} present)")
    elif doc_rate < 1.0:
        doctor_score = DOCTOR_SCORE["partial_100"]
    else:
        doctor_score = DOCTOR_SCORE["full"]

    # ── Patient surge component ──
    pct = inp.patient_7d_change_pct
    if pct > 30:
        surge_score = SURGE_SCORE["high_30"]
        factors.append(f"Patient surge +{pct:.0f}% (7d)")
    elif pct > 15:
        surge_score = SURGE_SCORE["moderate_15"]
        factors.append(f"Patient trend rising +{pct:.0f}%")
    elif pct > 5:
        surge_score = SURGE_SCORE["low_5"]
    else:
        surge_score = SURGE_SCORE["stable"]

    # ── Supplier delay component (PHC-level, separate from medicine) ──
    delay = inp.supplier_delay_days
    if delay >= 7:
        supplier_score = SUPPLIER_SCORE["severe_7d"]
        factors.append(f"Supplier delay {delay}d (severe)")
    elif delay >= 3:
        supplier_score = SUPPLIER_SCORE["moderate_3d"]
        factors.append(f"Supplier delay {delay}d")
    elif delay > 0:
        supplier_score = SUPPLIER_SCORE["minor"]
    else:
        supplier_score = SUPPLIER_SCORE["none"]

    total = min(100, medicine_score + bed_score + doctor_score + surge_score + supplier_score)

    return PHCRiskResult(
        phc_id=inp.phc_id,
        risk_score=total,
        risk_severity=severity_from_score(total),
        factors=factors,
        medicine_score=medicine_score,
        bed_score=bed_score,
        doctor_score=doctor_score,
        surge_score=surge_score,
        supplier_score=supplier_score,
        worst_medicine=worst_medicine,
        worst_days_of_stock=worst_dos,
        medicine_details=med_results,
    )


def severity_from_score(score: int) -> RiskSeverity:
    if score >= SEVERITY_THRESHOLDS[RiskSeverity.CRITICAL]:
        return RiskSeverity.CRITICAL
    elif score >= SEVERITY_THRESHOLDS[RiskSeverity.HIGH]:
        return RiskSeverity.HIGH
    elif score >= SEVERITY_THRESHOLDS[RiskSeverity.WATCH]:
        return RiskSeverity.WATCH
    return RiskSeverity.NORMAL


# ─── Sprint 2: Multi-factor cascading risk ────────────────────────────────

def score_phc_multifactor(inp: PHCRiskInput) -> MultiFactorRiskResult:
    """
    Compute compound risk with non-linear cascading interaction multiplier.

    Cascade triggers:
      • Low stock (worst critical medicine < 7 days)
      • Patient surge (>15% above 7-day average)
      • Supplier delay (delay_days > 3)

    When 2 or 3 of these co-occur the base score is multiplied:
      All 3             → ×1.6
      Low stock + surge → ×1.4
      Low stock + delay → ×1.35
      Surge + delay     → ×1.2
    """
    # ── Run base scoring ──
    base_result = score_phc(inp)
    base_score = base_result.risk_score

    # ── Detect compounding factors ──
    has_low_stock = False
    if base_result.worst_days_of_stock is not None:
        has_low_stock = base_result.worst_days_of_stock < 7

    has_surge = inp.patient_7d_change_pct > 15
    has_delay = inp.supplier_delay_days > 3

    # Also check per-medicine supplier delays
    if not has_delay:
        has_delay = any(m.supplier_delayed and m.delay_days > 3 for m in inp.medicines)

    active_factors: list[str] = []
    if has_low_stock:
        dos = base_result.worst_days_of_stock or 0
        active_factors.append(
            f"Critical stock: {base_result.worst_medicine} ({dos:.1f}d remaining)"
        )
    if has_surge:
        active_factors.append(
            f"Patient surge: +{inp.patient_7d_change_pct:.0f}% above 7-day baseline"
        )
    if has_delay:
        active_factors.append(
            f"Supplier delay: {inp.supplier_delay_days}d replenishment gap"
        )

    # ── Determine cascade multiplier ──
    n_factors = sum([has_low_stock, has_surge, has_delay])
    if n_factors == 3:
        multiplier = CASCADE_MULTIPLIER_ALL3
    elif has_low_stock and has_surge:
        multiplier = CASCADE_MULTIPLIER_STOCK_SURGE
    elif has_low_stock and has_delay:
        multiplier = CASCADE_MULTIPLIER_STOCK_SUPPLIER
    elif has_surge and has_delay:
        multiplier = CASCADE_MULTIPLIER_SURGE_SUPPLIER
    else:
        multiplier = 1.0

    cascaded_score = min(100, int(base_score * multiplier))
    severity = severity_from_score(cascaded_score)

    # ── Primary risk category ──
    if base_result.medicine_score >= base_result.bed_score and base_result.medicine_score >= base_result.surge_score:
        primary_category = RiskCategory.MEDICINE_STOCKOUT
    elif base_result.bed_score >= base_result.surge_score:
        primary_category = RiskCategory.BED_OVERLOAD
    else:
        primary_category = RiskCategory.PATIENT_SURGE

    if n_factors >= 2:
        primary_category = RiskCategory.COMBINED_CASCADING

    # ── Agent explanation ──
    if multiplier == 1.0:
        explanation = (
            f"PHC {inp.phc_id} scored {cascaded_score}/100 ({severity.value}). "
            f"No cascading interaction detected. "
            f"Dominant factors: {'; '.join(base_result.factors[:3]) or 'None'}."
        )
    else:
        factor_str = " + ".join(active_factors)
        explanation = (
            f"⚠ CASCADING RISK DETECTED at PHC {inp.phc_id}. "
            f"Base score {base_score} escalated to {cascaded_score} (×{multiplier:.2f} multiplier). "
            f"Compounding factors: {factor_str}. "
            f"Severity escalated to {severity.value}. Immediate review recommended."
        )

    # ── Factor Contributions & Audited Rules (Phase 3) ──
    sub_scores = {
        "medicine":  base_result.medicine_score,
        "bed":       base_result.bed_score,
        "doctor":    base_result.doctor_score,
        "surge":     base_result.surge_score,
        "supplier":  base_result.supplier_score,
    }

    if base_score > 0:
        factor_contributions = {
            k: round((v / base_score) * 100.0, 1) for k, v in sub_scores.items()
        }
    else:
        factor_contributions = {k: 0.0 for k in sub_scores}

    triggered_rules: list[str] = []
    if base_result.worst_days_of_stock is not None:
        if base_result.worst_days_of_stock < 3:
            triggered_rules.append("RULE-STOCK-CRITICAL-3D")
        elif base_result.worst_days_of_stock < 7:
            triggered_rules.append("RULE-STOCK-WARNING-7D")
        elif base_result.worst_days_of_stock < 14:
            triggered_rules.append("RULE-STOCK-ADVISORY-14D")

    if inp.beds_total > 0:
        bed_util = (inp.beds_occupied / inp.beds_total) * 100
        if bed_util > 95:
            triggered_rules.append("RULE-BED-OVERFLOW-95")
        elif bed_util > 85:
            triggered_rules.append("RULE-BED-HIGH-85")

    if inp.doctors_total > 0:
        doc_att = (inp.doctors_present / inp.doctors_total) * 100
        if doc_att < 50:
            triggered_rules.append("RULE-DOCTOR-SHORTAGE-50")
        elif doc_att < 75:
            triggered_rules.append("RULE-DOCTOR-LOW-75")

    if inp.patient_7d_change_pct > 30:
        triggered_rules.append("RULE-SURGE-SEVERE-30")
    elif inp.patient_7d_change_pct > 15:
        triggered_rules.append("RULE-SURGE-MODERATE-15")

    if inp.supplier_delay_days > 7:
        triggered_rules.append("RULE-SUPPLIER-SEVERE-7D")
    elif inp.supplier_delay_days > 3:
        triggered_rules.append("RULE-SUPPLIER-MODERATE-3D")

    if n_factors == 3:
        triggered_rules.append("RULE-CASCADE-ALL3")
    elif has_low_stock and has_surge:
        triggered_rules.append("RULE-CASCADE-STOCK-SURGE")
    elif has_low_stock and has_delay:
        triggered_rules.append("RULE-CASCADE-STOCK-SUPPLIER")
    elif has_surge and has_delay:
        triggered_rules.append("RULE-CASCADE-SURGE-SUPPLIER")

    return MultiFactorRiskResult(
        phc_id=inp.phc_id,
        risk_score=cascaded_score,
        risk_severity=severity,
        primary_category=primary_category,
        base_score=base_score,
        cascade_multiplier=multiplier,
        active_compounding_factors=active_factors,
        sub_scores=sub_scores,
        factor_contributions=factor_contributions,
        policy_version="2026.03.1",
        triggered_rules=triggered_rules,
        worst_medicine=base_result.worst_medicine,
        worst_days_of_stock=base_result.worst_days_of_stock,
        medicine_details=base_result.medicine_details,
        agent_explanation=explanation,
        factors=base_result.factors,
    )


# ─── Convenience metrics ──────────────────────────────────────────────────

def bed_utilization_pct(occupied: int, total: int) -> float:
    return round(occupied / total * 100, 1) if total > 0 else 0.0


def doctor_attendance_pct(present: int, total: int) -> float:
    return round(present / total * 100, 1) if total > 0 else 0.0


def nurse_attendance_pct(present: int, total: int) -> float:
    return round(present / total * 100, 1) if total > 0 else 0.0
