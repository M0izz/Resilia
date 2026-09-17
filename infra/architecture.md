# RESILIA Production Architecture on AWS

## Enterprise Cloud Deployment Topology

```
                                      [ Internet / Health Officials ]
                                                     │
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │     AWS Route 53 (DNS)        │
                                     │     AWS WAF (Threat Filter)   │
                                     └───────────────┬───────────────┘
                                                     │
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │    Amazon API Gateway (HTTP)  │
                                     │   + Cognito JWT Authorizer    │
                                     └───────────────┬───────────────┘
                                                     │
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │      AWS ALB (Load Balancer)  │
                                     └───────────────┬───────────────┘
                                                     │
                                     ┌───────────────┴───────────────┐
                                     ▼                               ▼
                      ┌─────────────────────────────┐ ┌─────────────────────────────┐
                      │    ECS Fargate: Backend     │ │    ECS Fargate: Dashboard   │
                      │   (FastAPI Microservices)   │ │    (Streamlit Command UI)   │
                      └──────────────┬──────────────┘ └─────────────────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│   Amazon DynamoDB   │   │ Amazon EventBridge  │   │   Amazon Bedrock    │
│  - Resilia-PHCs     │   │ - ResiliaEventBus   │   │ - Claude 3.5 Sonnet │
│  - Resilia-Inventory│   │   (Reactive Pub/Sub)│   │   (Agent Reasoning) │
│  - Resilia-Audit    │   └──────────┬──────────┘   └─────────────────────┘
└─────────────────────┘              │
                                     ▼
                          ┌─────────────────────┐
                          │ AWS Step Functions  │
                          │ - ResiliaPipeline   │
                          │   (Execution Logic) │
                          └──────────┬──────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
┌─────────────────────┐                             ┌─────────────────────┐
│  Amazon OpenSearch  │                             │      Amazon S3      │
│  - Semantic Incident│                             │  - Model Weights    │
│    Search & Audit   │                             │  - Cold Archives    │
└─────────────────────┘                             └─────────────────────┘
```

## Core AWS Services Mapping

1. **Amazon Bedrock**:
   - Powers the autonomous agent layer (`SentinelAgent`, `ForecastAgent`, `CrisisAgent`, `ResourceAgent`, `ResponseAgent`).
   - Claude 3.5 Sonnet / Titan models generate clinical problem justifications, risk evaluations, and natural language scenario interpretations.

2. **Amazon DynamoDB**:
   - Zero-administration serverless key-value database hosting PHC registries, live medicine stocks, beds, staff, and audit records.
   - Global Secondary Indexes (`DistrictIndex`, `SequenceIndex`) enable single-digit millisecond query latency.

3. **Amazon EventBridge**:
   - Serverless event bus routing operational events (`PATIENT_SURGE`, `INVENTORY_ALERT`, `SUPPLIER_DELAY`, `INTERVENTION_APPROVED`).
   - Decouples monitoring agents from downstream execution pipelines.

4. **AWS Step Functions**:
   - Orchestrates multi-step distributed intervention workflows:
     `ValidateSurplus -> DebitSource -> CreditTarget -> DispatchCarrier -> EmitEventBridge -> WriteAuditRecord`.

5. **Amazon OpenSearch & S3**:
   - OpenSearch provides log analytics and semantic search across historical incident logs.
   - S3 provides encrypted immutable storage for federated model checkpoints and compliance archives.

6. **AWS Cognito & Verified Permissions (Cedar)**:
   - Manages user identity and fine-grained role-based access control:
     - `DistrictHealthOfficers`: Full intervention review and execution rights.
     - `PHCPharmacists`: Local telemetry ingestion and stock adjustments.
     - `NationalCommanders`: Platform-wide governance and national policy tuning.

---

## Agent Interaction Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant PHC as PHC Network Sensor
    participant Bus as Amazon EventBridge
    participant Sentinel as Sentinel Agent
    participant Forecast as Forecast Agent
    participant Crisis as Crisis Digital Twin
    participant Resource as Resource Agent (OR-Tools)
    participant Response as Response Agent (Bedrock)
    participant DHO as District Health Officer
    participant StepFn as AWS Step Functions
    participant Audit as Cryptographic Audit Ledger
    participant Fed as Flower Federated Learning

    PHC->>Bus: INVENTORY_UPDATED (ORS-001 = 320 units)
    Bus->>Sentinel: Route Event Notification
    Sentinel->>Sentinel: Evaluate Multi-Factor Compound Risk (0.88)
    Sentinel->>Forecast: Trigger Failure Horizon Prediction
    Forecast->>Forecast: 14-Day Demand Forecaster (Stockout in 4.2d)
    Forecast->>Crisis: Run SimPy Cascading Stress Test
    Crisis->>Crisis: SimPy models 11 facility collapse & hospital overflow
    Crisis->>Resource: Problem Handoff (Deficit: 1,064 units)
    Resource->>Resource: Google OR-Tools SCIP MILP optimization
    Resource->>Response: Allocation Found (1,100 units from PHC Pimpri Hub)
    Response->>DHO: Synthesized Clinical Intervention Plan (Confidence: 94%)
    DHO->>Response: Digital Sign-Off & Approval
    Response->>StepFn: Initiate State Machine Execution
    StepFn->>PHC: Debit Pimpri / Credit Hadapsar / Dispatch Carrier V-17
    StepFn->>Audit: Append SHA-256 Chained AI Decision Record
    StepFn->>Fed: Outbreak Metrics Handoff
    Fed->>Fed: Flower FedAvg Multi-District Collaborative Update
```

---

## Data-Flow Pipeline Diagram

```mermaid
flowchart TD
    subgraph SENSING["1. Real-Time Sensing Layer"]
        A1[PHC Dispensary Telemetry] --> B[DynamoDB Streams]
        A2[Hospital Bed Influx] --> B
        A3[Logistics Carrier GPS] --> B
    end

    subgraph AGENTS["2. Autonomous AI Agent Layer"]
        B --> C[Sentinel Agent]
        C -- "Compound Risk Trigger" --> D[Forecast Agent]
        D -- "Projected Stockout" --> E[Crisis Digital Twin]
        E -- "Network Failure Cascade" --> F[Resource Agent]
        F -- "OR-Tools MILP Solver" --> G[Response Agent]
    end

    subgraph GOVERNANCE["3. Human Governance & Execution"]
        G --> H{District Health Officer}
        H -- "Approve" --> I[AWS Step Functions]
        H -- "Modify / Override" --> F
        I --> J[Carrier V-17 Dispatched]
    end

    subgraph AUDIT_AND_LEARNING["4. Verification & Federated Learning"]
        I --> K[(SHA-256 Immutable Audit Ledger)]
        I --> L[Flower Federated Aggregator]
        L --> M[Refined Outbreak Neural Predictor]
    end
```

---

## Federated Learning Architecture (Flower + DP-SGD)

```mermaid
flowchart LR
    subgraph Regional_Edge_Nodes["Regional District Edge Nodes (Private EHRs)"]
        Node1["Pune Cluster\n(Private Local Data)"]
        Node2["Mumbai Cluster\n(Private Local Data)"]
        Node3["Nashik Cluster\n(Private Local Data)"]
        Node4["Bengaluru Hub\n(Private Local Data)"]
        Node5["Delhi NCR\n(Private Local Data)"]
    end

    subgraph Central_Coordinator["Central Coordinator (Zero-Leakage Server)"]
        Aggregator["Flower FedAvg Aggregator\n(W_global = Σ n_k/N * W_k)"]
        Cert["DISHA & HIPAA Privacy Certificate\n(0 Raw Records Shared)"]
    end

    Node1 -- "DP-SGD Weights (ε=1.2)" --> Aggregator
    Node2 -- "DP-SGD Weights (ε=1.2)" --> Aggregator
    Node3 -- "DP-SGD Weights (ε=1.2)" --> Aggregator
    Node4 -- "DP-SGD Weights (ε=1.2)" --> Aggregator
    Node5 -- "DP-SGD Weights (ε=1.2)" --> Aggregator

    Aggregator --> Cert
    Aggregator -- "Updated Global Weights" --> Node1
    Aggregator -- "Updated Global Weights" --> Node2
    Aggregator -- "Updated Global Weights" --> Node3
    Aggregator -- "Updated Global Weights" --> Node4
    Aggregator -- "Updated Global Weights" --> Node5
```
