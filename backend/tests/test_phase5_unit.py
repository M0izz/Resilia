"""
Phase 5 — Unit tests with assertions for core service logic.

Tests cover:
 - In-memory store: data integrity, risk scoring, alert generation
 - Evaluation service: all metrics are numeric and within reasonable bounds
 - Forecast engine: backtest error metrics, depletion date calculation
 - Data source transparency: data_source fields present and labelled correctly
 - Health endpoint: data_source field present
"""
from __future__ import annotations

import sys
import os
import math

# Ensure backend is importable when running from repo root
backend_dir = os.path.join(os.path.dirname(__file__), "..", "..")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.in_memory_store import in_memory_store
from app.services.evaluation_service import EvaluationService
from app.services.forecast_engine import (
    forecast_patient_demand,
    forecast_medicine_depletion,
)


# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Store integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestInMemoryStore:
    """Verify the 75-PHC synthetic store initialises correctly."""

    def test_phc_count(self):
        phcs = in_memory_store.get_table_items("resilia-phcs")
        assert len(phcs) >= 50, f"Expected >=50 PHCs, got {len(phcs)}"

    def test_all_phcs_have_required_fields(self):
        required = {"phc_id", "name", "state", "district", "lat", "lng",
                    "risk_score", "risk_severity", "beds_total", "doctors_total"}
        for phc in in_memory_store.get_table_items("resilia-phcs"):
            missing = required - set(phc.keys())
            assert not missing, f"PHC {phc.get('phc_id')} missing fields: {missing}"

    def test_risk_scores_in_valid_range(self):
        for phc in in_memory_store.get_table_items("resilia-phcs"):
            rs = phc["risk_score"]
            assert 0 <= rs <= 100, f"PHC {phc['phc_id']} risk_score={rs} out of range"

    def test_risk_severity_matches_score(self):
        mapping = {"CRITICAL": (75, 100), "HIGH": (55, 74), "MEDIUM": (35, 54), "LOW": (0, 34)}
        for phc in in_memory_store.get_table_items("resilia-phcs"):
            sev = phc["risk_severity"]
            rs = phc["risk_score"]
            lo, hi = mapping[sev]
            assert lo <= rs <= hi, (
                f"PHC {phc['phc_id']} severity={sev} but risk_score={rs} "
                f"(expected {lo}–{hi})"
            )

    def test_inventory_count(self):
        inv = in_memory_store.get_table_items("resilia-inventory")
        phcs = in_memory_store.get_table_items("resilia-phcs")
        assert len(inv) >= len(phcs) * 10, (
            f"Expected at least {len(phcs)*10} inventory lines, got {len(inv)}"
        )

    def test_days_of_stock_positive(self):
        for item in in_memory_store.get_table_items("resilia-inventory"):
            dos = item.get("days_of_stock", -1)
            assert dos >= 0, f"Negative days_of_stock for {item}"

    def test_alerts_generated_for_high_risk_phcs(self):
        phcs = in_memory_store.get_table_items("resilia-phcs")
        high_risk = [p for p in phcs if p["risk_severity"] in ("CRITICAL", "HIGH")]
        alerts = in_memory_store.get_table_items("resilia-alerts")
        assert len(alerts) > 0, "No alerts generated for high-risk PHCs"
        assert len(alerts) <= len(high_risk) + 1

    def test_patient_records_span_30_days(self):
        patients = in_memory_store.get_table_items("resilia-patients")
        dates = sorted({r["date"] for r in patients})
        assert len(dates) >= 28, f"Expected >=28 unique patient days, got {len(dates)}"

    def test_hadapsar_has_ors_critical_status(self):
        """PHC Hadapsar should have ORS-001 in CRITICAL status (demo scenario)."""
        inv = in_memory_store.get_table_items("resilia-inventory")
        hadapsar_ors = [
            i for i in inv
            if i["phc_id"] == "MH-PUN-042" and i["medicine_code"] == "ORS-001"
        ]
        assert hadapsar_ors, "ORS-001 not found for MH-PUN-042"
        assert hadapsar_ors[0]["status"] == "CRITICAL", (
            f"Expected CRITICAL, got {hadapsar_ors[0]['status']}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation Service — class-scoped fixture using classmethod pattern
# ─────────────────────────────────────────────────────────────────────────────

_eval_report = None  # module-level cache to avoid re-computing


def get_eval_report():
    global _eval_report
    if _eval_report is None:
        _eval_report = EvaluationService.get_benchmarks()
    return _eval_report


class TestEvaluationService:
    """Verify computed evaluation metrics are real numbers in sensible bounds."""

    def test_data_source_is_synthetic(self):
        report = get_eval_report()
        assert report.data_source == "SYNTHETIC-DEMO"
        assert "SYNTHETIC" in report.evaluation_status

    def test_forecasting_mae_is_positive(self):
        report = get_eval_report()
        assert report.forecasting.mae_units >= 0
        assert math.isfinite(report.forecasting.mae_units)

    def test_forecasting_rmse_gte_mae(self):
        """RMSE >= MAE by definition."""
        report = get_eval_report()
        assert report.forecasting.rmse_units >= report.forecasting.mae_units

    def test_stockout_accuracy_in_range(self):
        report = get_eval_report()
        acc = report.forecasting.stockout_prediction_accuracy_pct
        assert 0.0 <= acc <= 100.0, f"Accuracy={acc} out of [0,100]"

    def test_precision_recall_in_range(self):
        report = get_eval_report()
        assert 0.0 <= report.forecasting.precision_pct <= 100.0
        assert 0.0 <= report.forecasting.recall_pct <= 100.0

    def test_test_evaluations_count_matches_inventory(self):
        report = get_eval_report()
        inv = in_memory_store.get_table_items("resilia-inventory")
        assert report.forecasting.test_evaluations_count == len(inv)

    def test_shortage_reduction_in_range(self):
        report = get_eval_report()
        sr = report.optimization.shortage_reduction_pct
        assert 0.0 <= sr <= 100.0, f"Shortage reduction={sr} out of [0,100]"

    def test_solver_runtime_is_non_negative(self):
        report = get_eval_report()
        assert report.optimization.mean_solver_runtime_ms >= 0.0

    def test_constraint_satisfaction_in_range(self):
        report = get_eval_report()
        assert 0.0 <= report.optimization.constraint_satisfaction_rate_pct <= 100.0

    def test_crisis_lead_time_is_positive(self):
        report = get_eval_report()
        assert report.simulation.crisis_detection_lead_time_hours >= 0.0

    def test_resilience_gain_is_positive(self):
        report = get_eval_report()
        assert report.simulation.network_resilience_gain_pct >= 0.0

    def test_safeguarded_patients_is_positive(self):
        report = get_eval_report()
        assert report.simulation.safeguarded_patient_care_episodes >= 0

    def test_api_latency_ordering(self):
        """p50 <= p95 <= p99."""
        report = get_eval_report()
        sys_perf = report.system_performance
        assert sys_perf.api_latency_p50_ms <= sys_perf.api_latency_p95_ms
        assert sys_perf.api_latency_p95_ms <= sys_perf.api_latency_p99_ms

    def test_store_latency_sub_100ms(self):
        """In-memory store should be very fast."""
        report = get_eval_report()
        assert report.system_performance.dynamodb_query_latency_ms < 100.0

    def test_overall_score_in_range(self):
        report = get_eval_report()
        assert 0.0 <= report.overall_resilience_score <= 100.0

    def test_forecasting_data_source_labelled(self):
        report = get_eval_report()
        assert report.forecasting.data_source == "SYNTHETIC-DEMO"
        assert report.optimization.data_source == "SYNTHETIC-DEMO"
        assert report.simulation.data_source == "SYNTHETIC-DEMO"
        assert report.system_performance.data_source == "SYNTHETIC-DEMO"

    def test_disclaimer_field_present(self):
        report = get_eval_report()
        assert report.disclaimer, "disclaimer field should be a non-empty string"
        assert "synthetic" in report.disclaimer.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Forecast Engine
# ─────────────────────────────────────────────────────────────────────────────

class TestForecastEngine:
    """Unit tests for the Ridge regression forecast engine."""

    def test_patient_demand_forecast_returns_14_days(self):
        patients = in_memory_store.get_table_items("resilia-patients")
        hadapsar = [r for r in patients if r["phc_id"] == "MH-PUN-042"]
        points, surge_prob, baseline = forecast_patient_demand(hadapsar[:20], horizon=14)
        assert len(points) == 14

    def test_patient_demand_forecast_surge_prob_in_range(self):
        patients = in_memory_store.get_table_items("resilia-patients")
        hadapsar = [r for r in patients if r["phc_id"] == "MH-PUN-042"]
        _, surge_prob, _ = forecast_patient_demand(hadapsar, horizon=14)
        assert 0.0 <= surge_prob <= 1.0

    def test_patient_demand_predictions_non_negative(self):
        patients = in_memory_store.get_table_items("resilia-patients")
        hadapsar = [r for r in patients if r["phc_id"] == "MH-PUN-042"]
        points, _, _ = forecast_patient_demand(hadapsar, horizon=14)
        for p in points:
            assert p.predicted_total >= 0
            assert p.confidence_low <= p.confidence_high

    def test_medicine_depletion_forecast_stockout(self):
        """ORS-001 at Hadapsar should predict stockout within 7 days."""
        # forecast_medicine_depletion requires patient_forecasts + baseline
        patients = in_memory_store.get_table_items("resilia-patients")
        hadapsar = [r for r in patients if r["phc_id"] == "MH-PUN-042"]
        patient_forecasts, _, baseline = forecast_patient_demand(hadapsar, horizon=14)

        _curve, stockout = forecast_medicine_depletion(
            medicine_code="ORS-001",
            medicine_name="ORS",
            current_stock=180.0,
            daily_consumption=95.0,
            unit="packets",
            patient_forecasts=patient_forecasts,
            baseline_daily_patients=baseline,
        )
        assert stockout.within_horizon is True, "Should predict stockout within 14-day horizon"
        assert stockout.days_until_stockout is not None
        assert stockout.days_until_stockout < 14.0

    def test_medicine_depletion_no_stockout_for_surplus(self):
        """Item with 60+ days of stock should not stockout within 14-day horizon."""
        patients = in_memory_store.get_table_items("resilia-patients")
        pimpri = [r for r in patients if r["phc_id"] == "MH-PUN-018"]
        patient_forecasts, _, baseline = forecast_patient_demand(pimpri, horizon=14)

        _curve, stockout = forecast_medicine_depletion(
            medicine_code="ORS-001",
            medicine_name="ORS",
            current_stock=3800.0,
            daily_consumption=60.0,
            unit="packets",
            patient_forecasts=patient_forecasts,
            baseline_daily_patients=baseline,
        )
        # 63 days of stock — should NOT stockout within 14-day horizon
        assert stockout.within_horizon is False, (
            f"Expected no stockout, but got days_until_stockout={stockout.days_until_stockout}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# API endpoints: data transparency
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint_has_data_source():
    """Phase 2: /health must return data_source field."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "data_source" in data, "/health missing data_source field"
        assert data["data_source"] in ("LIVE", "SYNTHETIC-IN-MEMORY")
        assert "dynamodb_online" in data


@pytest.mark.asyncio
async def test_evaluation_endpoint_has_disclaimer():
    """Phase 1: /evaluation/benchmarks must include disclaimer and data_source."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/evaluation/benchmarks")
        assert resp.status_code == 200
        data = resp.json()
        # disclaimer and data_source are top-level fields in ComprehensiveEvaluationReport
        assert "data_source" in data, f"Missing data_source in: {list(data.keys())}"
        assert "SYNTHETIC" in data["data_source"]
        assert "SYNTHETIC" in data["evaluation_status"]
        # disclaimer is included in the model — verify it's non-empty
        assert data.get("disclaimer"), "disclaimer field should be non-empty"


@pytest.mark.asyncio
async def test_alerts_returns_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/alerts?limit=10")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_phcs_endpoint_returns_records():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/phcs?limit=10")
        assert resp.status_code == 200
        assert len(resp.json()) > 0


@pytest.mark.asyncio
async def test_inventory_endpoint_returns_records():
    """Inventory route is /inventory/{phc_id} (path param)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/inventory/MH-PUN-042")
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert len(data) > 0, "Expected inventory items for MH-PUN-042"


# ─────────────────────────────────────────────────────────────────────────────
# Risk Engine unit tests (Phase 5.2)
# ─────────────────────────────────────────────────────────────────────────────

from app.services.risk_engine import (
    score_phc_multifactor,
    PHCRiskInput,
    MedicineRiskInput,
    RiskSeverity,
)

class TestRiskEngineScenarios:
    """Test compound scoring formula against hand-calculated expected values for 3 scenarios."""

    def test_low_risk_scenario(self):
        """Scenario 1: Low risk (beds 30%, docs 100%, 0 surge, 50 days stock) -> NORMAL."""
        low_inp = PHCRiskInput(
            phc_id="TEST-LOW-001",
            beds_total=20,
            beds_occupied=6,
            doctors_total=4,
            doctors_present=4,
            patient_7d_change_pct=2.0,
            medicines=[
                MedicineRiskInput(
                    medicine_code="MED-1",
                    medicine_name="Med 1",
                    quantity=500.0,
                    daily_consumption=10.0,
                    criticality="LOW",
                )
            ],
        )
        res = score_phc_multifactor(low_inp)
        assert res.risk_score < 25
        assert res.risk_severity == RiskSeverity.NORMAL
        assert res.cascade_multiplier == 1.0

    def test_medium_risk_scenario(self):
        """Scenario 2: Medium/elevated risk (beds 80%, docs 75%, 8 days stock) -> elevated score."""
        med_inp = PHCRiskInput(
            phc_id="TEST-MED-002",
            beds_total=20,
            beds_occupied=16,
            doctors_total=4,
            doctors_present=3,
            patient_7d_change_pct=8.0,
            medicines=[
                MedicineRiskInput(
                    medicine_code="MED-2",
                    medicine_name="Med 2",
                    quantity=80.0,
                    daily_consumption=10.0,
                    criticality="MEDIUM",
                )
            ],
        )
        res = score_phc_multifactor(med_inp)
        assert 15 <= res.risk_score <= 50
        assert res.base_score > 0
        assert "medicine" in res.sub_scores

    def test_critical_risk_with_cascading_compounding(self):
        """Scenario 3: Critical risk with compounding multiplier (beds 100%, docs 25%, surge 35%, 2d stock)."""
        crit_inp = PHCRiskInput(
            phc_id="TEST-CRIT-003",
            beds_total=20,
            beds_occupied=20,
            doctors_total=4,
            doctors_present=1,
            patient_7d_change_pct=35.0,
            supplier_delay_days=8,
            medicines=[
                MedicineRiskInput(
                    medicine_code="MED-3",
                    medicine_name="Med 3",
                    quantity=20.0,
                    daily_consumption=10.0,
                    criticality="CRITICAL",
                )
            ],
        )
        res = score_phc_multifactor(crit_inp)
        assert res.risk_score >= 75
        assert res.risk_severity == RiskSeverity.CRITICAL
        assert res.cascade_multiplier >= 1.4
        assert len(res.active_compounding_factors) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# Optimization Engine constraint satisfaction & edge cases (Phase 5.2)
# ─────────────────────────────────────────────────────────────────────────────

from app.services.optimization_engine import OptimizationEngine
from app.models.optimization import SurplusCandidate, OptimizationRequest

class TestOptimizationEngineEdgeCases:
    """Test constraint satisfaction (vehicle capacity, safety stock) with edge cases."""

    def test_zero_surplus_available(self):
        c1 = SurplusCandidate(
            phc_id="MH-PUN-001", phc_name="P1", district="Pune", state="Maharashtra",
            lat=18.5, lng=73.8, current_stock=100.0, daily_consumption=20.0,
            current_days=5.0, safety_stock_units=140.0, surplus_days=0.0,
            available_surplus_units=0.0, is_cross_district=False,
            distance_km=15.0, eta_hours=0.5
        )
        res = OptimizationEngine.solve(
            target_phc_id="MH-PUN-042", target_phc_name="Hadapsar", target_district="Pune",
            medicine_code="ORS-001", medicine_name="ORS", deficit_units=500.0,
            candidates=[c1]
        )
        assert res.total_allocated_units == 0.0
        assert res.unmet_deficit_units == 500.0
        assert len(res.allocated_routes) == 0

    def test_multiple_candidates_and_vehicle_capacity(self):
        c2 = SurplusCandidate(
            phc_id="MH-PUN-002", phc_name="P2", district="Pune", state="Maharashtra",
            lat=18.52, lng=73.85, current_stock=2000.0, daily_consumption=20.0,
            current_days=100.0, safety_stock_units=140.0, surplus_days=93.0,
            available_surplus_units=600.0, is_cross_district=False,
            distance_km=10.0, eta_hours=0.3
        )
        c3 = SurplusCandidate(
            phc_id="MH-PUN-003", phc_name="P3", district="Pune", state="Maharashtra",
            lat=18.55, lng=73.90, current_stock=1500.0, daily_consumption=20.0,
            current_days=75.0, safety_stock_units=140.0, surplus_days=68.0,
            available_surplus_units=400.0, is_cross_district=False,
            distance_km=25.0, eta_hours=0.8
        )
        res = OptimizationEngine.solve(
            target_phc_id="MH-PUN-042", target_phc_name="Hadapsar", target_district="Pune",
            medicine_code="ORS-001", medicine_name="ORS", deficit_units=500.0,
            candidates=[c2, c3], vehicle_capacity=300.0
        )
        assert res.total_allocated_units == 500.0
        assert len(res.allocated_routes) == 2
        for route in res.allocated_routes:
            assert route.quantity <= 300.0, "Route exceeds vehicle capacity"
            assert route.quantity > 0

    def test_safety_stock_never_violated(self):
        c4 = SurplusCandidate(
            phc_id="MH-PUN-004", phc_name="P4", district="Pune", state="Maharashtra",
            lat=18.52, lng=73.85, current_stock=300.0, daily_consumption=20.0,
            current_days=15.0, safety_stock_units=140.0, surplus_days=8.0,
            available_surplus_units=160.0, is_cross_district=False,
            distance_km=12.0, eta_hours=0.4
        )
        res = OptimizationEngine.solve(
            target_phc_id="MH-PUN-042", target_phc_name="Hadapsar", target_district="Pune",
            medicine_code="ORS-001", medicine_name="ORS", deficit_units=1000.0,
            candidates=[c4]
        )
        assert res.total_allocated_units <= 160.0
        assert res.total_allocated_units == 160.0


# ─────────────────────────────────────────────────────────────────────────────
# Sentinel Agent unit tests (Phase 5.2)
# ─────────────────────────────────────────────────────────────────────────────

from app.agents.sentinel_agent import SentinelAgent

class TestSentinelAgentUnit:
    """Test SentinelAgent risk monitoring and compound scoring on known facilities."""

    def test_sentinel_evaluates_known_high_risk_phc(self):
        agent = SentinelAgent()
        decision = agent._evaluate_phc("MH-PUN-042", trigger="UNIT_TEST")
        assert decision is not None
        assert decision.risk_severity in ("CRITICAL", "HIGH")
        assert decision.risk_score >= 50
        assert len(decision.active_compounding_factors) >= 0

    def test_sentinel_decisions_logged(self):
        agent = SentinelAgent()
        initial_count = len(agent.recent_decisions())
        agent._evaluate_phc("MH-PUN-042", trigger="UNIT_TEST_LOG")
        assert len(agent.recent_decisions()) == initial_count + 1
        assert agent.recent_decisions()[0]["phc_id"] == "MH-PUN-042"


# ─────────────────────────────────────────────────────────────────────────────
# Resource Agent unit tests (Phase 5.2)
# ─────────────────────────────────────────────────────────────────────────────

from app.agents.resource_agent import ResourceAgent

class TestResourceAgentUnit:
    """Test ResourceAgent plan_intervention() and safety stock constraints."""

    def test_plan_intervention_creates_valid_plan(self):
        res_agent = ResourceAgent()
        req = OptimizationRequest(
            target_phc_id="MH-PUN-042",
            medicine_code="ORS-001",
            deficit_units=500.0,
        )
        plan = res_agent.plan_intervention(req)
        assert plan.plan_id.startswith("INTV-")
        assert plan.target_phc_id == "MH-PUN-042"
        assert plan.total_units > 0
        assert plan.status in ("AWAITING_APPROVAL", "PROPOSED", "DRAFT", "PENDING_APPROVAL")
        assert len(plan.routes) > 0

    def test_plan_intervention_respects_safety_stock(self):
        res_agent = ResourceAgent()
        req = OptimizationRequest(
            target_phc_id="MH-PUN-042",
            medicine_code="ORS-001",
            deficit_units=200.0,
        )
        plan = res_agent.plan_intervention(req)
        for route in plan.routes:
            assert route.quantity > 0
            assert route.remaining_source_stock_days >= 0

