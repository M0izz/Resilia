# 🏥 RESILIA — Autonomous Healthcare Supply-Chain Resilience Platform

> **An Agentic AI Operating System for National Healthcare Supply-Chain Resilience.**  
> *Transforming public healthcare networks from reactive, siloed shortages to autonomous, predictive, and self-healing resilience.*

---

## ⚠️ What's Real vs. What's Simulated

This table applies to **every quantitative claim** in this README. All benchmarks are computed on the bundled **synthetic 75-PHC demo dataset** — they are not from a live production deployment. The algorithms are real; the data they run on is representative, not production.

| Component | Status | Details |
| :--- | :--- | :--- |
| FastAPI backend + routing | ✅ Real | Fully functional, production-quality |
| In-memory 75-PHC dataset | ⚠️ Synthetic-Demo | Realistic but generated with `random.seed(42)` |
| Ridge regression forecasting | ✅ Real algorithm | Walk-forward backtest computed at runtime |
| OR-Tools SCIP MILP solver | ✅ Real | Actual solver; runtime measured with `time.perf_counter()` |
| Federated learning (Flower/flwr) | ⚠️ Simulated | PyTorch training loop on synthetic data; no real FL server |
| SimPy crisis simulation | ⚠️ Simulated | Discrete-event engine on synthetic PHC graph |
| SHA-256 audit ledger | ✅ Real | Cryptographic chain computed at runtime |
| AWS infra (DynamoDB, Step Functions) | ⚠️ Local/IaC | Uses DynamoDB Local; CloudFormation IaC is defined but not deployed |
| All benchmark numbers in `/evaluation/benchmarks` | ⚠️ Computed on synthetic | Computed at request time from synthetic data; not from production |

---

## 🌟 The 5-Sprint Evolution Story

| Sprint | System Evolution | Core Question Answered | Technology Centerpiece |
| :--- | :--- | :--- | :--- |
| **Sprint 1** | **PHC Network Foundation** | *"What is happening right now?"* | FastAPI, DynamoDB, Streamlit Geographic Map |
| **Sprint 2** | **Predictive Intelligence** | *"What is likely to happen next?"* | Multi-Factor Cascading Risk Engine, Forecast Agent, Sentinel Agent |
| **Sprint 3** | **Resource Optimization** | *"What should we actually do about it?"* | Google OR-Tools SCIP MILP Solver, Resource Agent, AWS Step Functions |
| **Sprint 4** | **Crisis Digital Twin** | *"What if situations get significantly worse?"* | NetworkX Topological Twin, SimPy Discrete-Event Engine, Flower (flwr) FedAvg |
| **Sprint 5** | **National Resilience Platform** | *"Can we continuously manage, execute, and improve the system?"* | Unified National Command Center, 10-Phase Agentic Loop, Immutable Audit, AWS CloudFormation |

```
    S1: OBSERVE ──► S2: PREDICT ──► S3: OPTIMIZE ──► S4: SIMULATE ──► S5: ORCHESTRATE + LEARN
```

---

## 🏛️ End-to-End System Architecture

```
                                  [ Public Healthcare Network: 75 PHCs (Synthetic Demo) ]
                                                     │
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │     Telemetry Stream Ingest   │
                                     │ (DynamoDB Streams/EventBridge)│
                                     └───────────────┬───────────────┘
                                                     │
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │   🤖 SENTINEL AGENT (SENTRY)  │
                                     │ Multi-Factor Compound Scoring │
                                     └───────────────┬───────────────┘
                                                     │ (Risk Score: Computed from inventory/staff/supplier)
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │   🔮 FORECAST AGENT (PREDICT) │
                                     │ 14-Day Demand & Stockout Date │
                                     └───────────────┬───────────────┘
                                                     │ (Stockout date predicted via Ridge regression)
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │  🌪️ CRISIS TWIN (SIMULATE)    │
                                     │ SimPy Cascading Failure Engine│
                                     └───────────────┬───────────────┘
                                                     │ (Cascading impact computed on synthetic graph)
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │  🧮 RESOURCE AGENT (OPTIMIZE) │
                                     │ Google OR-Tools SCIP MILP     │
                                     └───────────────┬───────────────┘
                                                     │ (Optimal transfer plan solved in measured ms)
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │  ⚡ RESPONSE AGENT (SYNTHESIS) │
                                     │ Operational Rationale         │
                                     └───────────────┬───────────────┘
                                                     │
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │   🧑‍⚕️ HUMAN DHO GOVERNANCE    │
                                     │ Digital Sign-Off & Approval   │
                                     └───────────────┬───────────────┘
                                                     │ (Approved)
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │  ⚙️ AWS STEP FUNCTIONS        │
                                     │ State Machine & Fleet Dispatch│
                                     └───────┬───────────────┬───────┘
                                             │               │
                                             ▼               ▼
                        ┌─────────────────────────┐     ┌─────────────────────────┐
                        │ 📜 IMMUTABLE AI AUDIT   │     │ 🌸 FEDERATED LEARNING   │
                        │ SHA-256 Chained Ledger  │     │ Flower FedAvg (Simulated)│
                        └─────────────────────────┘     └─────────────────────────┘
```

---

## ⭐ The Canonical Demo Flow (Synthetic Dataset)

In a single interactive scenario, RESILIA demonstrates the complete closed-loop transformation on the **synthetic 75-PHC dataset**. All numbers below are produced by the running code, not hardcoded:

1. **Real-World Shock**: Post-monsoon Dengue surge (+42% footfall in Pune) coinciding with an NH-48 supplier delay.
2. **Autonomous Sensing**: Telemetry reveals PHC Hadapsar ORS stock in CRITICAL status (< 2 days of stock at current consumption).
3. **Compound Risk Detection**: Sentinel Agent computes a compound risk score from inventory + bed occupancy + staffing + supplier delay factors.
4. **Predictive Failure Horizon**: Forecast Agent's Ridge regression model predicts exact stockout date within the 14-day horizon.
5. **'What If?' Digital Twin Simulation**: SimPy discrete-event engine models cascading facility impacts on the synthetic PHC network graph.
6. **Mathematical Optimization**: OR-Tools SCIP MILP solver allocates surplus from PHC Pimpri Hub, runtime measured live with `time.perf_counter()`.
7. **Human Governance**: District Health Officer grants digital authorization.
8. **Automated Workflow**: Step Functions state machine debits source, credits target, dispatches carrier.
9. **Measurable Impact & Audit**: Resilience score delta computed from pre/post risk scores; sealed with SHA-256 block hash.
10. **Continuous Learning**: Flower FedAvg simulates multi-district collaborative training with **0 raw patient records shared** (differential privacy).

---

## 📊 Quantitative Benchmarks ⚠️ COMPUTED ON SYNTHETIC DATA

> All values below are computed at runtime by `GET /evaluation/benchmarks`. They reflect algorithm performance on the **synthetic 75-PHC demo dataset** — NOT a production deployment. The response carries `"data_source": "SYNTHETIC-DEMO"` and an explicit `"disclaimer"` field.

To reproduce these numbers locally:

```bash
cd backend && python -m uvicorn app.main:app --port 8000
curl http://localhost:8000/evaluation/benchmarks | python -m json.tool
```

| Pillar | Metric | How It's Computed | Example Range (synthetic) |
| :--- | :--- | :--- | :--- |
| **Forecasting** | Stockout Prediction Accuracy | TP+TN / total inventory items (status vs. DOS threshold) | 70–95% |
| | Walk-forward MAE | 7-day held-out backtest on patient history | 5–20 patients/day |
| | Precision / Recall | TP/(TP+FP), TP/(TP+FN) on LOW/CRITICAL flags | 60–95% |
| **Optimization** | Shortage Reduction | Available surplus / flagged deficit for ORS-001 | 50–100% |
| | OR-Tools Solver Runtime | `time.perf_counter()` on actual micro-solve | 0.1–50 ms |
| | Constraint Satisfaction | Routes respecting safety-stock and vehicle-capacity | ~100% |
| **Simulation** | Crisis Detection Lead Time | Days-of-stock × 24h for flagged items | 24–168 hours |
| | Resilience Gain | (pre_risk - post_risk) / pre_risk after modelled intervention | 10–35% |
| | Safeguarded Patients | Avg daily visits × 14 days at high-risk PHCs | 500–3,000 |
| **System** | Store Latency p50 | 5 measured `in_memory_store` probes + HTTP overhead | < 50 ms |
| | Audit Success Rate | Successful audit records / total (from audit ledger) | Varies |

*Methodology: see `backend/scripts/run_backtest.py` — regenerate with `make benchmark`.*

---

## 🔍 What's Real vs. Simulated

To ensure complete transparency during technical evaluation, here is the exact breakdown of implemented components and their data provenance:

| Component | Status | Provenance & Implementation Details |
| :--- | :--- | :--- |
| **Mathematical Optimization** | **REAL** | Powered by **Google OR-Tools (SCIP MILP solver)** in `backend/app/services/optimization_engine.py`. Solves multi-facility supply allocation, vehicle capacity, and safety-stock constraints with real wall-clock timing (`time.perf_counter()`). |
| **Forecasting Engine** | **REAL ALGORITHM** | Real Scikit-Learn **Ridge regression** with rolling features in `backend/app/services/forecast_engine.py`. Backtested using walk-forward cross-validation on time-series records. |
| **Cryptographic Audit Ledger** | **REAL** | Full SHA-256 hash chaining with verifiable cryptographic pointers in `backend/app/services/audit_service.py`. Verifiable via `GET /audit/verify-integrity`. |
| **Healthcare & Patient Data** | **SYNTHETIC** | All 75 Primary Healthcare Centres (PHCs), inventory levels, consumption rates, and 30-day OPD/IPD visits are procedurally generated using Maharashtra geographic coordinates (`data/seed_db.py` / `in_memory_store.py`). No real patient or private hospital data is used. |
| **Data Storage Layer** | **HYBRID** | Supports both **AWS DynamoDB** (local or cloud) and automatic thread-safe in-memory fallback (`in_memory_store.py`). When DynamoDB is unreachable, the system continues running on the in-memory graph and visibly tags all API responses with `"data_source": "SYNTHETIC-DEMO"`. |
| **Demo Scenario** | **HYBRID** | The canonical Pune Dengue Surge (PHC Hadapsar ORS stockout) is a curated storyline demonstrating the full 10-step agent loop (`scenario_type: scripted_demo`). In addition, the live pipeline accepts arbitrary PHC and medicine inputs via `POST /agentic-loop/run` or the interactive dashboard. |
| **Federated Learning** | **MECHANISM DEMO** | Implements the **Flower FedAvg** orchestration pattern with differential privacy clipping in `backend/app/services/federated_learning.py`. Demonstrates multi-district parameter exchange without centralizing records; not yet trained on clinical telemetry. |
| **AWS Cloud Infrastructure** | **IaC SPECIFICATION** | Full AWS topology is defined via CloudFormation in `infra/resilia-cloudformation.yml`. For local development and hackathon demonstration, services run containerized via `docker-compose.yml`. |

---

## 📜 Security & Cryptographic AI Decision Trail

Every clinical intervention committed by RESILIA permanently answers 7 mandatory explainability questions:

- **What happened?** Clinical/logistics trigger summary.
- **Why was it flagged?** Multi-factor compound risk parameters and surge multiplier.
- **Which model predicted it?** Versioned identifier of the forecasting algorithm.
- **What recommendation was generated?** Exact reallocation volume and source/destination facilities.
- **What optimization was performed?** Google OR-Tools SCIP constraints and solver proof.
- **Who approved it?** Certified name and credentials of the authorizing health officer.
- **What action was executed and when?** AWS Step Functions execution ARN and timestamp.
- **SHA-256 Hash Chaining:** Each record contains a cryptographic pointer (`previous_hash`) linking to its predecessor, guaranteeing tamper-evident auditability (`GET /audit/verify-integrity`).

---

## ☁️ AWS Cloud Production Topology (IaC — Not Yet Deployed)

RESILIA is designed to be fully cloud-native, defined via Infrastructure as Code in `infra/resilia-cloudformation.yml`. The current repo runs against **DynamoDB Local** via docker-compose. A real AWS deployment would use:

- **Amazon DynamoDB**: Serverless operational persistence with Global Secondary Indexes for single-digit ms reads.
- **Amazon EventBridge**: Reactive event bus decoupling telemetry from agent intervention loops.
- **AWS Step Functions**: Distributed state machine orchestrating physical inventory updates and carrier dispatches.
- **Amazon API Gateway**: High-throughput edge gateway.
- **Amazon OpenSearch & S3**: Semantic search across incident histories and encrypted storage for model checkpoints.
- **AWS Cognito & Cedar RBAC**: Fine-grained access control separating District Health Officers, Pharmacists, and National Commanders.

---

## 🚀 Quickstart Guide

### 1. Run with Docker Compose (Recommended)

```bash
# Clone and start all services (DynamoDB local, FastAPI backend, Streamlit dashboard)
docker compose up -d

# Dashboard is live at: http://localhost:8501
# FastAPI Swagger docs at: http://localhost:8000/docs
```

> **Note:** `dynamodb_local.zip` is no longer committed to this repo. Docker Compose pulls the official `amazon/dynamodb-local` image automatically. The API will operate on the in-memory synthetic dataset if DynamoDB Local is unavailable, and will show a `⚠️ SYNTHETIC DEMO DATA` banner in the dashboard.

### 2. Run Locally Outside Docker

```bash
# Backend Setup
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Dashboard Setup (in a separate terminal)
cd dashboard
pip install streamlit plotly pandas numpy requests
streamlit run app.py
```

### 3. Run Test Suite

```bash
cd backend
python -m pytest tests/ -v

# Phase 5 unit tests with real assertions:
python -m pytest tests/test_phase5_unit.py -v
```

---

## 🌐 FastAPI Core Endpoints

- **`POST /demo/run-canonical-scenario`**: Execute the single unified 10-phase judge demonstration scenario (synthetic data).
- **`GET /demo/canonical-scenario-status`**: Retrieve the latest canonical demonstration report and evidence metrics.
- **`POST /crisis/simulate`**: Execute SimPy discrete-event digital twin stress simulation (Baseline vs. Mitigated).
- **`POST /crisis/federated/train`**: Run Flower FedAvg multi-district collaborative training with Differential Privacy (simulated).
- **`POST /optimization/plan`**: Formulate Google OR-Tools SCIP Mixed-Integer Linear Programming redistribution plan.
- **`POST /agentic-loop/run`**: Trigger the complete 10-phase autonomous agentic loop.
- **`GET /audit/verify-integrity`**: Cryptographically verify SHA-256 hash chain signatures across the audit ledger.
- **`GET /evaluation/benchmarks`**: Retrieve computed scorecard across all 4 operational pillars (includes `data_source` and `disclaimer` fields).
- **`GET /health`**: Liveness check — includes `data_source: LIVE | SYNTHETIC-IN-MEMORY` and `dynamodb_online` fields.
