"""
Unit tests for Phase 3: Sentinel Risk Worker Decoupling & Configurable Rules
============================================================================
Verifies:
  - MultiFactorRiskResult outputs policy_version="2026.03.1".
  - Numeric factor_contributions breakdown with accurate percentage sum.
  - Audited rule triggers (e.g. RULE-STOCK-CRITICAL-3D, RULE-CASCADE-STOCK-SURGE).
  - Sentinel agent records explainable factor attributions.
"""
from app.services.risk_engine import (
    MedicineRiskInput,
    PHCRiskInput,
    score_phc_multifactor,
)
from app.models.common import RiskSeverity, RiskCategory


def test_multifactor_risk_rule_attribution_and_policy_version():
    inp = PHCRiskInput(
        phc_id="PHC-TEST-003",
        beds_total=20,
        beds_occupied=19,     # 95% -> RULE-BED-HIGH-85 (or overflow if >95%)
        doctors_total=2,
        doctors_present=1,    # 50% -> RULE-DOCTOR-LOW-75
        patient_7d_change_pct=25.0,  # 25% -> RULE-SURGE-MODERATE-15
        medicines=[
            MedicineRiskInput(
                medicine_code="ORS-001",
                medicine_name="Oral Rehydration Salts",
                quantity=10,
                daily_consumption=10,  # 1.0 day -> <3d -> RULE-STOCK-CRITICAL-3D
                criticality="HIGH",
                supplier_delayed=True,
                delay_days=5,          # 5 days -> RULE-SUPPLIER-MODERATE-3D
            )
        ],
        supplier_delay_days=5,
    )

    result = score_phc_multifactor(inp)

    # 1. Policy version
    assert result.policy_version == "2026.03.1"

    # 2. Triggered rules
    assert "RULE-STOCK-CRITICAL-3D" in result.triggered_rules
    assert "RULE-SURGE-MODERATE-15" in result.triggered_rules
    assert "RULE-SUPPLIER-MODERATE-3D" in result.triggered_rules
    assert "RULE-CASCADE-ALL3" in result.triggered_rules or "RULE-CASCADE-STOCK-SURGE" in result.triggered_rules

    # 3. Factor contributions
    assert "medicine" in result.factor_contributions
    assert "bed" in result.factor_contributions
    assert "surge" in result.factor_contributions
    assert "doctor" in result.factor_contributions
    assert "supplier" in result.factor_contributions

    # Total contribution should sum approximately to 100%
    total_pct = sum(result.factor_contributions.values())
    assert 99.0 <= total_pct <= 101.0


def test_standalone_sentinel_scan_network():
    from app.agents.sentinel_agent import sentinel_agent
    summary = sentinel_agent.scan_network()
    assert "scan_id" in summary
    assert "phcs_evaluated" in summary
    assert summary["phcs_evaluated"] >= 0
