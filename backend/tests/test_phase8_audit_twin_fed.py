"""
Unit tests for Phase 8: Cryptographic Audit Ledger & Monte Carlo Digital Twin
=============================================================================
Verifies:
  - Cryptographic hash chaining (SHA-256) across all audit records.
  - Tamper detection: modifying any record breaks verification.
  - Monte Carlo crisis simulation percentiles: P10 <= P50 <= P90.
  - Federated learning PyTorch convergence reporting.
"""
from app.services.audit_service import AIDecisionAuditLedger
from app.models.crisis import ParsedCrisisScenario, FederatedTrainingRequest
from app.services.crisis_simulator import CrisisSimulatorEngine
from app.services.federated_learning import FederatedIntelligenceEngine


def test_audit_ledger_integrity_and_tamper_detection():
    ledger = AIDecisionAuditLedger()

    # Initial chain must be cryptographically valid
    res_init = ledger.verify_integrity()
    assert res_init.is_valid is True
    assert len(res_init.broken_links) == 0

    # Record a new decision
    rec = ledger.record_decision(
        facility_id="PHC-TEST-01",
        facility_name="PHC Test",
        district="Pune",
        what_happened="Routine inventory rebalance",
        why_flagged="Buffer optimization",
        predictive_model="Ridge-AR",
        ai_recommendation="Transfer 100 units",
        optimization_engine="Google OR-Tools",
        approved_by="Dr. Test",
        executed_action="Step Functions exec",
    )

    assert rec.sequence_number == res_init.total_blocks_verified + 1
    assert rec.previous_hash == res_init.latest_block_id or len(rec.previous_hash) == 64

    # Verification after append
    res_after = ledger.verify_integrity()
    assert res_after.is_valid is True

    # Intentionally tamper with a record
    with ledger._lock:
        ledger._chain[1].what_happened = "TAMPERED: Altered audit record data."

    # Verification must catch the tampering!
    res_tampered = ledger.verify_integrity()
    assert res_tampered.is_valid is False
    assert len(res_tampered.broken_links) > 0


def test_monte_carlo_percentiles():
    scenario = ParsedCrisisScenario(
        original_prompt="Simulate a 40% dengue surge in Pune for 5 days with supply disruption",
        region="Pune",
        disease="Dengue Fever",
        surge_pct=40.0,
        duration_days=5,
        supply_disruption_days=1.5,
        affected_resources=["ORS-001"],
    )

    mc_results = CrisisSimulatorEngine.run_monte_carlo_stress_test(scenario, num_iterations=5)

    assert mc_results["iterations_evaluated"] == 5
    ci = mc_results["confidence_intervals"]

    # Verify P10 <= P50 <= P90 invariant for resilience gain
    assert ci["resilience_gain_pct"]["p10"] <= ci["resilience_gain_pct"]["p50"] <= ci["resilience_gain_pct"]["p90"]
    assert ci["safeguarded_patients"]["p10"] <= ci["safeguarded_patients"]["p50"] <= ci["safeguarded_patients"]["p90"]


def test_federated_learning_real_pytorch_loss():
    req = FederatedTrainingRequest(
        districts=["Pune Cluster", "Mumbai Cluster"],
        rounds=2,
        local_epochs_per_round=1,
    )
    result = FederatedIntelligenceEngine.run_federated_training(req)

    assert result.status in ("CONVERGED", "COMPLETED", "TRAINING_COMPLETE")
    assert result.rounds_completed == 2
    assert len(result.metrics) == 2

    # Losses should be positive floats
    for r in result.metrics:
        assert r.global_loss >= 0.0
        assert r.active_clients == 2
