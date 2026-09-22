"""
Unit and integration tests for Phase 1: Real AWS Persistence & Data Quality Baseline
===================================================================================
Verifies:
  - Telemetry freshness scoring and completeness assessment.
  - Fail-fast DynamoDB behavior in staging/production when DB is offline.
  - X-Resilia-Data-Source and X-Resilia-Environment headers.
  - Sentinel agent emits UNKNOWN risk severity when telemetry data is absent or stale.
"""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.db.dynamodb import (
    is_dynamodb_online,
    get_data_source,
    PersistenceUnavailableError,
    ResilientTableWrapper,
)
from app.services.data_quality import (
    calculate_freshness_score,
    assess_phc_telemetry_quality,
)
from app.models.common import RiskSeverity
from app.agents.sentinel_agent import sentinel_agent


client = TestClient(app)


def test_freshness_score_calculation():
    now = datetime.now(timezone.utc)
    
    # 1 hour old -> fresh (1.0)
    score_1h, age_1h = calculate_freshness_score((now - timedelta(hours=1)).isoformat(), reference_time=now)
    assert score_1h == 1.0
    assert age_1h == 1.0

    # 39 hours old -> roughly 0.5 decay
    score_39h, age_39h = calculate_freshness_score((now - timedelta(hours=39)).isoformat(), reference_time=now)
    assert 0.4 <= score_39h <= 0.6

    # 80 hours old -> stale (0.0)
    score_80h, age_80h = calculate_freshness_score((now - timedelta(hours=80)).isoformat(), reference_time=now)
    assert score_80h == 0.0
    assert age_80h == 80.0

    # None / missing
    score_none, _ = calculate_freshness_score(None)
    assert score_none == 0.0


def test_assess_phc_telemetry_quality_complete_and_incomplete():
    now = datetime.now(timezone.utc)

    # Missing PHC
    report_missing = assess_phc_telemetry_quality(None)
    assert report_missing.can_evaluate_risk is False
    assert report_missing.is_stale is True

    # Complete and fresh PHC
    complete_phc = {
        "phc_id": "PHC-TEST-001",
        "name": "Test PHC",
        "beds_total": 20,
        "beds_occupied": 10,
        "doctors_total": 3,
        "doctors_present": 2,
        "last_updated": (now - timedelta(hours=2)).isoformat(),
    }
    complete_inventory = [
        {
            "medicine_code": "MED-001",
            "medicine_name": "Paracetamol",
            "quantity": 500,
            "daily_consumption": 25,
            "criticality": "HIGH",
        }
    ]
    report_ok = assess_phc_telemetry_quality(complete_phc, complete_inventory, reference_time=now)
    assert report_ok.can_evaluate_risk is True
    assert report_ok.is_stale is False
    assert report_ok.completeness_score == 1.0

    # Missing beds and inventory
    incomplete_phc = {
        "phc_id": "PHC-TEST-002",
        "last_updated": (now - timedelta(hours=2)).isoformat(),
        "doctors_total": 2,
        "doctors_present": 2,
    }
    report_inc = assess_phc_telemetry_quality(incomplete_phc, [], reference_time=now)
    assert report_inc.can_evaluate_risk is False
    assert "beds_total" in report_inc.missing_fields
    assert "inventory_telemetry" in report_inc.missing_fields


def test_api_headers_exposed():
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Resilia-Data-Source" in response.headers
    assert "X-Resilia-Environment" in response.headers
    assert response.headers["X-Resilia-Environment"] == settings.environment


def test_fail_fast_in_staging_when_dynamodb_offline(monkeypatch):
    # Simulate staging environment with offline dynamodb
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "dynamodb_fail_fast", True)
    
    # Mock is_dynamodb_online to return False
    from app.db import dynamodb
    monkeypatch.setattr(dynamodb, "is_dynamodb_online", lambda: False)

    # Direct table operation should raise PersistenceUnavailableError
    wrapper = ResilientTableWrapper("resilia-phcs")
    with pytest.raises(PersistenceUnavailableError):
        wrapper.get_item(Key={"phc_id": "PHC-PUN-001"})

    # HTTP request should return 503
    resp = client.get("/phcs")
    assert resp.status_code == 503
    assert "Primary persistence unavailable" in resp.json()["detail"]
    assert resp.headers.get("X-Resilia-Data-Source") == "UNAVAILABLE"


def test_sentinel_emits_unknown_for_stale_data(monkeypatch):
    # Ensure demo_mode is False
    monkeypatch.setattr(settings, "demo_mode", False)

    # In-memory PHC with stale timestamp (>72 hours)
    from app.db.in_memory_store import in_memory_store
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=96)).isoformat()
    test_phc_id = "PHC-TEST-STALE-001"
    
    try:
        in_memory_store.put_item("resilia-phcs", {
            "phc_id": test_phc_id,
            "name": "Stale PHC",
            "last_updated": stale_time,
            "beds_total": 10,
            "beds_occupied": 5,
            "doctors_total": 2,
            "doctors_present": 2,
        })

        # Evaluate PHC via Sentinel
        decision = sentinel_agent._evaluate_phc(test_phc_id, trigger="UNIT_TEST")
        assert decision is not None
        assert decision.risk_severity == RiskSeverity.UNKNOWN.value
        assert decision.action_taken == "DATA_GAP_ALERT"
        assert "DATA_GAP" in decision.active_compounding_factors
    finally:
        in_memory_store.delete_item("resilia-phcs", {"phc_id": test_phc_id})
