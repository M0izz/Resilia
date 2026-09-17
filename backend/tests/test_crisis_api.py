"""
Test API endpoints for /crisis routes in FastAPI.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_crisis_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Root includes crisis endpoints
        root_res = await client.get("/")
        assert root_res.status_code == 200
        assert ("Crisis Digital Twin" in root_res.json()["sprint"] or "National Command Center" in root_res.json()["sprint"])

        # 2. GET /crisis/presets
        presets_res = await client.get("/crisis/presets")
        assert presets_res.status_code == 200
        presets = presets_res.json()
        assert len(presets) >= 3

        # 3. POST /crisis/parse-scenario
        prompt = "Simulate a 40% dengue patient surge across Pune for the next 14 days with a two-day medicine supply disruption."
        parse_res = await client.post("/crisis/parse-scenario", json={"prompt": prompt})
        assert parse_res.status_code == 200
        data = parse_res.json()
        assert data["surge_pct"] == 40.0
        assert data["duration_days"] == 14
        assert data["supply_disruption_days"] == 2.0

        # 4. GET /crisis/network-graph
        graph_res = await client.get("/crisis/network-graph")
        assert graph_res.status_code == 200
        graph_data = graph_res.json()
        assert graph_data["total_facilities"] >= 7
        assert len(graph_data["nodes"]) >= 7
        assert len(graph_data["edges"]) >= 5

        # 5. POST /crisis/simulate
        sim_res = await client.post(
            "/crisis/simulate",
            json={
                "prompt": prompt,
                "region": "Pune",
                "disease": "Dengue",
                "surge_pct": 40.0,
                "duration_days": 14,
                "supply_disruption_days": 2.0,
            }
        )
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        assert sim_data["resilience_gain_pct"] > 0
        assert sim_data["avoided_stockouts"] > 0
        assert sim_data["safeguarded_patients"] > 0
        assert len(sim_data["baseline"]["time_series"]) == 14
        assert len(sim_data["resilia_mitigated"]["time_series"]) == 14

        # 6. POST /crisis/federated/train
        fed_res = await client.post(
            "/crisis/federated/train",
            json={
                "rounds": 2,
                "districts": ["Pune Cluster", "Mumbai Cluster"],
                "differential_privacy_epsilon": 1.2,
                "local_epochs_per_round": 2,
            }
        )
        assert fed_res.status_code == 200
        fed_data = fed_res.json()
        assert fed_data["rounds_completed"] == 2
        assert fed_data["status"] == "CONVERGED"
        assert fed_data["privacy_certificate"]["raw_patient_records_transmitted"] == 0
