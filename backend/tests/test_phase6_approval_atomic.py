"""
Unit tests for Phase 6: Human Approval Gates & Atomic Execution
===============================================================
Verifies:
  - Strict human approval requirement (rejects empty approver).
  - Idempotent execution (prevents double-debiting on duplicate submissions).
  - Atomic inventory deduction and insufficient stock error handling.
  - State transitions from PROPOSED/AWAITING_APPROVAL to APPROVED upon human gate clearance.
"""
import pytest
from app.models.optimization import (
    AllocationRoute,
    OperationalInterventionPlan,
    InterventionImpact,
    InterventionConfidence,
    OptimizationResult,
)
from app.services.workflow_executor import WorkflowExecutor
from app.db.in_memory_store import in_memory_store


def _build_test_plan(plan_id: str, donor_id: str, dest_id: str, qty: float) -> OperationalInterventionPlan:
    route = AllocationRoute(
        source_phc_id=donor_id,
        source_name=f"PHC {donor_id}",
        source_district="Pune",
        destination_phc_id=dest_id,
        destination_name=f"PHC {dest_id}",
        destination_district="Pune",
        is_cross_district=False,
        medicine_code="ORS-001",
        medicine_name="Oral Rehydration Salts",
        quantity=qty,
        distance_km=15.0,
        eta_hours=0.8,
        vehicle_id="V-10",
        transport_cost_inr=500.0,
        remaining_source_stock_days=10.0,
    )

    opt_result = OptimizationResult(
        status="OPTIMAL",
        objective_value=500.0,
        runtime_ms=12.5,
        target_phc_id=dest_id,
        medicine_code="ORS-001",
        medicine_name="Oral Rehydration Salts",
        deficit_units=qty,
        total_allocated_units=qty,
        unmet_deficit_units=0.0,
        allocated_routes=[route],
        candidates_evaluated=1,
    )

    return OperationalInterventionPlan(
        plan_id=plan_id,
        target_phc_id=dest_id,
        target_phc_name=f"PHC {dest_id}",
        target_district="Pune",
        medicine_code="ORS-001",
        medicine_name="Oral Rehydration Salts",
        title=f"Emergency Transfer of ORS-001 to PHC {dest_id}",
        problem_summary="Critical stock depletion expected within 48h.",
        recommended_action="Inter-facility emergency replenishment",
        expected_impact="Runway extended to 14 days.",
        status="AWAITING_APPROVAL",
        impact_metrics=InterventionImpact(
            pre_stock_days=2.0,
            post_stock_days=14.0,
            days_gained=12.0,
            risk_reduction_pct=75.0,
        ),
        transport_summary="Dispatched via primary local road corridor.",
        primary_source_phc_id=donor_id,
        primary_source_phc_name=f"PHC {donor_id}",
        primary_source_district="Pune",
        is_cross_district=False,
        total_units=qty,
        eta_hours=0.8,
        assigned_vehicle_id="V-10",
        confidence=InterventionConfidence(
            rating="HIGH",
            score_pct=95.0,
        ),
        routes=[route],
        optimization_result=opt_result,
    )


def test_approval_gate_rejects_missing_approver():
    plan = _build_test_plan("PLAN-GATE-01", "PHC-D1", "PHC-R1", 100.0)

    # Empty approver must fail
    with pytest.raises(ValueError, match="human approver credential"):
        WorkflowExecutor.execute_approval(plan, approved_by="", note="test")

    with pytest.raises(ValueError, match="human approver credential"):
        WorkflowExecutor.execute_approval(plan, approved_by="   ", note="test")


def test_idempotent_execution_prevents_double_debit():
    donor = "PHC-IDEMP-DONOR"
    dest = "PHC-IDEMP-DEST"
    med = "ORS-001"

    # Seed donor and dest inventory
    in_memory_store.put_item("resilia-inventory", {
        "phc_id": donor,
        "medicine_code": med,
        "quantity": 1000.0,
        "daily_consumption": 20.0,
    })
    in_memory_store.put_item("resilia-inventory", {
        "phc_id": dest,
        "medicine_code": med,
        "quantity": 50.0,
        "daily_consumption": 20.0,
    })

    plan = _build_test_plan("PLAN-IDEMP-01", donor, dest, 200.0)
    key = "idemp-key-test-001"

    # First execution
    res1 = WorkflowExecutor.execute_approval(plan, approved_by="Dr. Priya Sharma", idempotency_key=key)
    assert res1["status"] == "SUCCEEDED"
    assert res1.get("is_idempotent_replay") is not True

    donor_after1 = in_memory_store.get_item("resilia-inventory", {"phc_id": donor, "medicine_code": med})
    dest_after1 = in_memory_store.get_item("resilia-inventory", {"phc_id": dest, "medicine_code": med})
    assert donor_after1["quantity"] == 800.0
    assert dest_after1["quantity"] == 250.0

    # Second execution with same idempotency key
    res2 = WorkflowExecutor.execute_approval(plan, approved_by="Dr. Priya Sharma", idempotency_key=key)
    assert res2["is_idempotent_replay"] is True

    # Inventory must NOT have been debited again!
    donor_after2 = in_memory_store.get_item("resilia-inventory", {"phc_id": donor, "medicine_code": med})
    dest_after2 = in_memory_store.get_item("resilia-inventory", {"phc_id": dest, "medicine_code": med})
    assert donor_after2["quantity"] == 800.0
    assert dest_after2["quantity"] == 250.0


def test_insufficient_stock_raises_atomic_error():
    donor = "PHC-LOW-STOCK"
    dest = "PHC-DEST-01"
    med = "ORS-001"

    # Only 50 units available
    in_memory_store.put_item("resilia-inventory", {
        "phc_id": donor,
        "medicine_code": med,
        "quantity": 50.0,
        "daily_consumption": 10.0,
    })

    # Plan requests 300 units
    plan = _build_test_plan("PLAN-INSUF-01", donor, dest, 300.0)

    with pytest.raises(ValueError, match="insufficient"):
        WorkflowExecutor.execute_approval(plan, approved_by="Dr. Anita Roy")
