"""
Test suite for Sprint 5 — National Command Center, Security & AI Decision Auditability,
Complete 10-Phase Agentic Loop, and Platform Benchmarking.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.audit_service import audit_ledger
from app.services.agentic_loop import agentic_orchestrator
from app.services.evaluation_service import evaluation_service


def test_audit_ledger_integrity():
    """Verify cryptographic SHA-256 block hash chaining and integrity verification."""
    # 1. Initial seeded chain should be valid
    is_valid, broken = audit_ledger._verify_chain_integrity()
    assert is_valid is True
    assert len(broken) == 0

    # 2. Append new decision record
    rec = audit_ledger.record_decision(
        facility_id="MH-PUN-042",
        facility_name="PHC Hadapsar",
        district="Pune",
        what_happened="Emergency rebalance of 1,000 ORS units during Dengue surge.",
        why_flagged="Compound risk score 0.88.",
        predictive_model="RESILIA-ForecastAgent v2.0",
        ai_recommendation="Transfer from PHC Pimpri Hub via Route MH-PUN-018->042.",
        optimization_engine="Google OR-Tools SCIP MILP",
        approved_by="Dr. Priya Sharma (DHO)",
        executed_action="Dispatched vehicle V-17.",
    )
    assert rec.sequence_number >= 4
    assert len(rec.record_hash) == 64  # SHA-256 hex length
    assert rec.previous_hash != ""

    # 3. Chain should remain valid after append
    is_valid_after, _ = audit_ledger._verify_chain_integrity()
    assert is_valid_after is True


def test_agentic_loop_orchestration():
    """Verify the complete 10-phase autonomous agentic loop executes sequentially when authorized."""
    trace = agentic_orchestrator.execute_loop(
        facility_id="MH-PUN-042",
        medicine_code="ORS-001",
        approved_by="Dr. Verified DHO (Pune)",
    )
    assert trace.total_steps == 10
    assert trace.status == "COMPLETED"
    assert len(trace.steps) == 10

    # Verify key steps in the sequence
    step_names = [s.step_name for s in trace.steps]
    assert "PHC Network Ingestion" in step_names[0]
    assert "Sentinel Agent Anomaly Detection" in step_names[1]
    assert "Predictive Intelligence Forecasting" in step_names[2]
    assert "Crisis Twin Cascading Simulation" in step_names[3]
    assert "Resource Optimization Engine" in step_names[4]
    assert "Response Plan Synthesis" in step_names[5]
    assert "Human Health Officer Governance" in step_names[6]
    assert "Explainable AI Audit Trail" in step_names[8]
    assert "Federated Model Continuous Refinement" in step_names[9]


def test_agentic_loop_halts_at_approval_gate():
    """Verify that execution halts at Step 7 in AWAITING_APPROVAL if not authorized."""
    trace = agentic_orchestrator.execute_loop(
        facility_id="MH-PUN-042",
        medicine_code="ORS-001",
        approved_by=None,
    )
    assert trace.total_steps == 7
    assert trace.status == "AWAITING_APPROVAL"
    assert trace.steps[-1].status == "AWAITING_APPROVAL"
    assert "awaiting digital authorization" in trace.steps[-1].summary.lower()


def test_evaluation_benchmarks():
    """Verify quantitative empirical metrics across all 4 pillars."""
    bench = evaluation_service.get_benchmarks()
    # Forecasting
    assert bench.forecasting.stockout_prediction_accuracy_pct >= 90.0
    assert bench.forecasting.mae_units <= 5.0
    # Optimization
    assert bench.optimization.shortage_reduction_pct >= 90.0
    assert bench.optimization.safety_stock_violations_count == 0
    # Simulation
    assert bench.simulation.crisis_detection_lead_time_hours >= 24.0
    assert bench.simulation.network_resilience_gain_pct >= 10.0
    # System
    assert bench.system_performance.api_latency_p50_ms < 30.0
    assert bench.system_performance.step_functions_success_rate_pct >= 99.0


@pytest.mark.asyncio
async def test_sprint5_api_endpoints():
    """Verify all Sprint 5 FastAPI routes over HTTP."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Root verification
        root_res = await client.get("/")
        assert root_res.status_code == 200
        assert "5 — National Command Center" in root_res.json()["sprint"]

        # 2. Audit Trail
        audit_res = await client.get("/audit/records?limit=10")
        assert audit_res.status_code == 200
        assert audit_res.json()["chain_integrity_valid"] is True
        assert len(audit_res.json()["records"]) >= 3

        # 3. Audit Integrity Verification
        ver_res = await client.get("/audit/verify-integrity")
        assert ver_res.status_code == 200
        assert ver_res.json()["is_valid"] is True

        # 4. Agentic Loop Execution (without approval -> AWAITING_APPROVAL)
        loop_res = await client.post("/agentic-loop/run", json={"facility_id": "MH-PUN-042"})
        assert loop_res.status_code == 200
        assert loop_res.json()["status"] == "AWAITING_APPROVAL"
        assert loop_res.json()["total_steps"] == 7

        # 4b. Agentic Loop Execution (with human approval -> COMPLETED)
        loop_approved = await client.post(
            "/agentic-loop/run",
            json={"facility_id": "MH-PUN-042", "approved_by": "Dr. Verified DHO (Pune)"},
        )
        assert loop_approved.status_code == 200
        assert loop_approved.json()["total_steps"] == 10
        assert loop_approved.json()["status"] == "COMPLETED"

        # 5. Agentic Loop Status
        status_res = await client.get("/agentic-loop/status")
        assert status_res.status_code == 200
        assert status_res.json()["status"] in ("COMPLETED", "AWAITING_APPROVAL")

        # 6. Evaluation Benchmarks
        bench_res = await client.get("/evaluation/benchmarks")
        assert bench_res.status_code == 200
        assert bench_res.json()["overall_resilience_score"] > 90.0
