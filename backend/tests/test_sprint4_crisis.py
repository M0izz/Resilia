"""
Test suite for Sprint 4 — Crisis Digital Twin, SimPy Cascading Simulation,
and Flower Federated Intelligence.
"""
import pytest
from app.agents.crisis_agent import crisis_agent
from app.services.digital_twin import digital_twin, haversine_km
from app.services.crisis_simulator import crisis_simulator
from app.services.federated_learning import federated_engine
from app.models.crisis import CrisisScenarioRequest, FederatedTrainingRequest


def test_crisis_agent_prompt_parsing():
    """Verify Crisis Agent NLP correctly parses the user's prompt."""
    prompt = "Simulate a 40% dengue patient surge across Pune for the next 14 days with a two-day medicine supply disruption."
    scenario = crisis_agent.parse_natural_language_prompt(prompt)

    assert scenario.surge_pct == 40.0
    assert scenario.duration_days == 14
    assert scenario.region.lower() == "pune"
    assert scenario.disease.lower() == "dengue"
    assert scenario.supply_disruption_days == 2.0
    assert "ORS-001" in scenario.affected_resources


def test_digital_twin_topology():
    """Verify NetworkX digital twin graph contains PHCs, hospitals, and warehouses."""
    snapshot = digital_twin.get_snapshot()
    assert snapshot.total_facilities >= 7

    node_types = {n.node_type for n in snapshot.nodes}
    assert "PHC" in node_types
    assert "DISTRICT_HOSPITAL" in node_types
    assert "WAREHOUSE" in node_types

    # Edges should include supply routes and referral corridors
    edge_types = {e.edge_type for e in snapshot.edges}
    assert "SUPPLY_ROUTE" in edge_types
    assert "REFERRAL_CORRIDOR" in edge_types


def test_simpy_crisis_simulation():
    """Verify SimPy dual simulation produces baseline cascading failure and mitigated resilience gain."""
    prompt = "Simulate a 40% dengue patient surge across Pune for the next 14 days with a two-day medicine supply disruption."
    scenario = crisis_agent.parse_natural_language_prompt(prompt)

    comparison = crisis_simulator.run_crisis_stress_test(scenario=scenario)

    # Baseline should exhibit lower resilience and cascade events
    assert comparison.baseline.resilience_score < 75.0
    assert comparison.baseline.stockout_events_count > 0
    assert len(comparison.baseline.time_series) == 14

    # RESILIA mitigated run should achieve high resilience and avoid stockouts
    assert comparison.resilia_mitigated.resilience_score > comparison.baseline.resilience_score
    assert comparison.resilience_gain_pct > 0.0
    assert comparison.avoided_stockouts > 0
    assert comparison.safeguarded_patients > 0
    assert len(comparison.autonomous_interventions_dispatched) > 0


def test_federated_learning_simulation():
    """Verify Flower FedAvg simulation trains across 5 regional districts with differential privacy."""
    req = FederatedTrainingRequest(
        rounds=3,
        districts=["Pune Cluster", "Mumbai Cluster", "Nashik Cluster"],
        differential_privacy_epsilon=1.2,
        local_epochs_per_round=2,
    )
    res = federated_engine.run_federated_training(req)

    assert res.rounds_completed == 3
    assert len(res.metrics) == 3
    assert res.final_global_loss < res.initial_global_loss
    assert res.loss_reduction_pct > 0.0
    assert res.privacy_certificate["raw_patient_records_transmitted"] == 0
    assert res.status == "CONVERGED"


if __name__ == "__main__":
    print("Running Sprint 4 tests...")
    test_crisis_agent_prompt_parsing()
    print("✓ Crisis Agent parsing passed")
    test_digital_twin_topology()
    print("✓ Digital Twin topology passed")
    test_simpy_crisis_simulation()
    print("✓ SimPy simulation & Before vs After passed")
    test_federated_learning_simulation()
    print("✓ Federated Learning passed")
    print("\nALL SPRINT 4 TESTS PASSED!")
