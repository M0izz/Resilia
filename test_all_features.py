import os
import sys

# Add backend to sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

print("=== TESTING ALL RESILIA FEATURES VIA TESTCLIENT ===")

tests = [
    ("Health Check", "GET", "/health", None),
    ("States List", "GET", "/phcs/states", None),
    ("Districts List", "GET", "/phcs/districts?state_code=MH", None),
    ("Network Summary", "GET", "/phcs/network-summary", None),
    ("PHC List", "GET", "/phcs", None),
    ("Alerts Feed", "GET", "/alerts?limit=10", None),
    ("Unacknowledged Alerts Count", "GET", "/alerts/unacknowledged/count", None),
    ("Sentinel Status", "GET", "/sentinel/status", None),
    ("Optimization Plans", "GET", "/optimization/plans", None),
    ("Audit Ledger", "GET", "/audit/ledger", None),
    ("Audit Verify Integrity", "GET", "/audit/verify-integrity", None),
    ("Evaluation Benchmarks", "GET", "/evaluation/benchmarks", None),
    ("Crisis Catalog", "GET", "/crisis/scenarios", None),
    ("Simulate Crisis", "POST", "/crisis/simulate", {
        "prompt": "40% dengue surge across Pune for 14 days",
        "district": "Pune",
        "patient_surge_pct": 42.0,
        "transport_delay_days": 2,
        "deficit_medicine": "ORS-001"
    }),
    ("Federated Train", "POST", "/crisis/federated/train", {"rounds": 2, "districts": ["PUN", "MUM"]}),
    ("Canonical Demo Status", "GET", "/demo/canonical-scenario-status", None),
    ("Agentic Loop Run", "POST", "/agentic-loop/run", {
        "facility_id": "MH-PUN-042",
        "medicine_code": "ORS-001",
        "approved_by": "Dr. Priya Sharma"
    }),
]

for name, method, url, payload in tests:
    try:
        if method == "GET":
            resp = client.get(url)
        else:
            resp = client.post(url, json=payload or {})
        status = resp.status_code
        print(f"[{'PASS' if status in (200, 201) else 'FAIL'}] {name:30} {method} {url[:35]:35} -> {status}")
        if status not in (200, 201):
            print(f"       Error detail: {resp.text[:200]}")
    except Exception as e:
        print(f"[FAIL] {name:30} Exception: {e}")
