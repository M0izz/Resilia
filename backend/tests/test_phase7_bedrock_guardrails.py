"""
Unit tests for Phase 7: Bedrock Agent Guardrails & Honest LLM Invocations
========================================================================
Verifies:
  - Input sanitization against injections.
  - Transparent fallback tagging when Bedrock is disabled or unreachable.
  - Strict mathematical guardrails: plan quantities must match solver outputs exactly.
"""
import pytest
from app.config import settings
from app.models.optimization import (
    AllocationRoute,
    OperationalInterventionPlan,
    OptimizationResult,
    InterventionImpact,
    InterventionConfidence,
)
from app.services.bedrock_agent_service import (
    sanitize_input_text,
    enforce_numerical_guardrails,
    BedrockAgentService,
)


def test_input_sanitization():
    dirty = "<script>alert('injection')</script>PHC Pune\x00 Central"
    clean = sanitize_input_text(dirty)
    assert "<script>" not in clean
    assert "\x00" not in clean
    assert "PHC Pune Central" in clean


def test_bedrock_disabled_returns_honest_fallback(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_enabled", False)

    solver_res = OptimizationResult(
        status="OPTIMAL",
        objective_value=120.0,
        runtime_ms=10.0,
        target_phc_id="PHC-TEST",
        medicine_code="MED-01",
        medicine_name="ORS",
        deficit_units=500.0,
        total_allocated_units=500.0,
        unmet_deficit_units=0.0,
        allocated_routes=[],
        candidates_evaluated=1,
    )

    result = BedrockAgentService.generate_narrative_explanation(
        target_phc_name="PHC Test",
        medicine_name="ORS",
        total_units=500.0,
        solver_result=solver_res,
    )

    assert result["is_fallback"] is True
    assert "Bedrock unavailable or disabled" in result["explanation_source"]
    assert "500" in result["summary"]


def test_enforce_numerical_guardrails_catches_divergence():
    route_solver = AllocationRoute(
        source_phc_id="PHC-DONOR-1",
        source_name="Donor PHC",
        source_district="Pune",
        destination_phc_id="PHC-RECIP-1",
        destination_name="Recip PHC",
        destination_district="Pune",
        is_cross_district=False,
        medicine_code="ORS-01",
        medicine_name="ORS",
        quantity=300.0,
        distance_km=20.0,
        eta_hours=1.0,
        vehicle_id="V-1",
        transport_cost_inr=100.0,
        remaining_source_stock_days=10.0,
    )

    solver_res = OptimizationResult(
        status="OPTIMAL",
        objective_value=100.0,
        runtime_ms=5.0,
        target_phc_id="PHC-RECIP-1",
        medicine_code="ORS-01",
        medicine_name="ORS",
        deficit_units=300.0,
        total_allocated_units=300.0,
        unmet_deficit_units=0.0,
        allocated_routes=[route_solver],
        candidates_evaluated=1,
    )

    # Valid plan matching solver
    valid_plan = OperationalInterventionPlan(
        target_phc_id="PHC-RECIP-1",
        target_phc_name="Recip PHC",
        target_district="Pune",
        medicine_code="ORS-01",
        medicine_name="ORS",
        title="Test Plan",
        problem_summary="Stock low",
        recommended_action="Transfer",
        expected_impact="High",
        impact_metrics=InterventionImpact(pre_stock_days=2, post_stock_days=14, days_gained=12, risk_reduction_pct=80),
        transport_summary="Road",
        primary_source_phc_id="PHC-DONOR-1",
        primary_source_phc_name="Donor PHC",
        primary_source_district="Pune",
        is_cross_district=False,
        total_units=300.0,
        eta_hours=1.0,
        assigned_vehicle_id="V-1",
        confidence=InterventionConfidence(rating="HIGH", score_pct=95),
        routes=[route_solver],
        optimization_result=solver_res,
    )

    # Must pass without error
    enforce_numerical_guardrails(valid_plan, solver_res)

    # Now simulate an LLM hallucination where total_units is altered to 450
    hallucinated_plan = valid_plan.model_copy(deep=True)
    hallucinated_plan.total_units = 450.0

    with pytest.raises(ValueError, match="Guardrail violation: Plan total units"):
        enforce_numerical_guardrails(hallucinated_plan, solver_res)
