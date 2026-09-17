"""
Test suite for Canonical Judge Demonstration Pipeline.
Verifies the single unified 10-phase story executes end-to-end without manual patching.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.judge_demo import judge_demo_engine


def test_judge_demo_engine_execution():
    """Verify CanonicalJudgeDemoEngine runs all 10 stages and computes hard metrics."""
    report = judge_demo_engine.execute_canonical_scenario(
        approved_by="Dr. Priya Sharma (District Health Officer, Pune)"
    )

    assert report.scenario_id == "CANONICAL-PUNE-DENGUE-SURGE"
    assert report.target_facility_id == "MH-PUN-042"
    assert len(report.stages) == 10

    # Verify stage titles
    stage_titles = [s.stage_title for s in report.stages]
    assert "1. Real-World Shock" in stage_titles[0]
    assert "2. Continuous Monitoring" in stage_titles[1]
    assert "3. Multi-Factor Risk Detection" in stage_titles[2]
    assert "4. Predictive Failure Horizon" in stage_titles[3]
    assert "5. 'What If?' Crisis Simulation" in stage_titles[4]
    assert "6. Mathematical Optimization" in stage_titles[5]
    assert "7. Human-in-the-Loop Governance" in stage_titles[6]
    assert "8. Automated Execution Pipeline" in stage_titles[7]
    assert "9. Measurable Impact & Immutable Audit" in stage_titles[8]
    assert "10. Continuous System Learning" in stage_titles[9]

    # Verify hard quantitative evidence metrics
    assert report.baseline_resilience_score < 65.0
    assert report.mitigated_resilience_score > 80.0
    assert report.resilience_gain_pct >= 20.0
    assert report.avoided_stockouts_count == 11
    assert report.safeguarded_patient_episodes >= 1000
    assert report.rebalanced_medicine_units == 1100.0
    assert report.fleet_eta_hours < 6.0
    assert report.logistics_cost_savings_pct >= 30.0
    assert len(report.audit_block_hash) == 64  # Valid SHA-256 hash


@pytest.mark.asyncio
async def test_judge_demo_api_routes():
    """Verify FastAPI /demo routes over HTTP."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # POST /demo/run-canonical-scenario
        post_res = await client.post(
            "/demo/run-canonical-scenario",
            json={"approved_by": "Dr. Priya Sharma (DHO, Pune)"}
        )
        assert post_res.status_code == 200
        data = post_res.json()
        assert data["scenario_id"] == "CANONICAL-PUNE-DENGUE-SURGE"
        assert len(data["stages"]) == 10
        assert data["avoided_stockouts_count"] == 11

        # GET /demo/canonical-scenario-status
        get_res = await client.get("/demo/canonical-scenario-status")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["scenario_id"] == "CANONICAL-PUNE-DENGUE-SURGE"
        assert get_data["resilience_gain_pct"] > 0
