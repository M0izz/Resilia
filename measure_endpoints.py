import time
import requests
import subprocess
import sys
import os

print("Starting backend test...")
# Let's import the FastAPI app directly and test with TestClient to measure raw Python latency!
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

endpoints = [
    ("GET", "/health"),
    ("GET", "/phcs/states"),
    ("GET", "/phcs/network-summary"),
    ("GET", "/phcs"),
    ("GET", "/alerts?limit=20"),
    ("GET", "/forecasts/phc/MH-PUN-042"),
    ("GET", "/optimization/plans"),
    ("GET", "/evaluation/benchmarks"),
    ("GET", "/demo/canonical-scenario-status"),
]

print("\n--- Latency of endpoints (in-process TestClient) ---")
for method, url in endpoints:
    t0 = time.time()
    if method == "GET":
        resp = client.get(url)
    t1 = time.time()
    ms = (t1 - t0) * 1000
    print(f"{method} {url:35} -> Status {resp.status_code} in {ms:6.1f} ms")
