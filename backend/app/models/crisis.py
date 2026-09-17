"""
Data models for Sprint 4: Crisis Digital Twin, SimPy Cascading Simulation,
and Flower Federated Intelligence.
"""
from __future__ import annotations
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ─── Crisis Scenario Input & Parsing ──────────────────────────────────────

class CrisisScenarioRequest(BaseModel):
    """Scenario request payload from natural language or interactive sliders."""
    prompt: Optional[str] = Field(
        None,
        description="Natural language scenario description (e.g., 'Simulate a 40% dengue patient surge across Pune for 14 days with a 2-day supply disruption')"
    )
    region: str = Field("Pune", description="Target district or region")
    disease: str = Field("Dengue", description="Disease or crisis type")
    surge_pct: float = Field(40.0, description="Patient arrival surge percentage (e.g. 40.0 means +40%)")
    duration_days: int = Field(14, ge=3, le=60, description="Simulation timeline in days")
    supply_disruption_days: float = Field(2.0, ge=0.0, le=14.0, description="Additional supply delivery delay in days")
    affected_resources: List[str] = Field(
        default_factory=lambda: ["ORS-001", "PCTM-001", "IVNS-001", "BEDS", "DOCTORS"],
        description="List of impacted medicines and hospital resources"
    )
    bed_capacity_modifier: float = Field(1.0, ge=0.3, le=2.0, description="Multiplier on available bed capacity")
    staff_availability_modifier: float = Field(1.0, ge=0.3, le=2.0, description="Multiplier on available clinical staff")
    enable_resilia_balancing: bool = Field(True, description="Whether to simulate autonomous OR-Tools stock balancing")


class ParsedCrisisScenario(BaseModel):
    """Structured crisis parameters parsed by the Crisis Agent."""
    original_prompt: str
    region: str
    disease: str
    surge_pct: float
    duration_days: int
    supply_disruption_days: float
    affected_resources: List[str]
    bed_capacity_modifier: float = 1.0
    staff_availability_modifier: float = 1.0
    confidence_score: float = 0.95
    parsing_engine: str = "ResiliaCrisisAgent-NLP"
    extracted_keywords: List[str] = Field(default_factory=list)
    parsed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ─── Digital Twin Network Topology (NetworkX) ─────────────────────────────

class DigitalTwinNode(BaseModel):
    """Node in the healthcare graph: PHC, Hospital, or Warehouse."""
    id: str
    name: str
    node_type: str = Field("PHC", description="'PHC', 'CHC', 'DISTRICT_HOSPITAL', or 'WAREHOUSE'")
    district: str
    latitude: float
    longitude: float
    beds_total: int
    beds_occupied: int
    doctors_count: int
    inventory: Dict[str, float] = Field(default_factory=dict, description="Current stock units by medicine code")
    stress_score: float = Field(0.0, description="Normalized stress index (0-100)")
    is_bottleneck: bool = False


class DigitalTwinEdge(BaseModel):
    """Edge in the healthcare graph: Supply Route or Referral Corridor."""
    source: str
    target: str
    edge_type: str = Field("SUPPLY_ROUTE", description="'SUPPLY_ROUTE' or 'REFERRAL_CORRIDOR'")
    distance_km: float
    eta_hours: float
    capacity_units: float = 10000.0
    stress_pct: float = 0.0


class NetworkGraphResponse(BaseModel):
    """Complete digital twin network snapshot."""
    nodes: List[DigitalTwinNode]
    edges: List[DigitalTwinEdge]
    total_facilities: int
    avg_network_stress: float
    critical_nodes: List[str]


# ─── SimPy Simulation Output & Cascading Failures ──────────────────────────

class CascadingFailureEvent(BaseModel):
    """Log entry when a node fails or spills over into another node."""
    timestamp_day: float
    phc_id: str
    phc_name: str
    failure_type: str = Field(..., description="'STOCKOUT', 'BED_OVERFLOW', 'DOCTOR_EXHAUSTION', 'CASCADE_SPILLOVER'")
    severity: str = Field("CRITICAL", description="'CRITICAL', 'HIGH', 'WARNING'")
    description: str
    spillover_target_phc_id: Optional[str] = None
    spillover_target_phc_name: Optional[str] = None
    excess_patients: int = 0
    unmet_units: float = 0.0


class SimPyTimeSeriesPoint(BaseModel):
    """Day-by-day aggregate state during simulation."""
    day: float
    patient_arrivals: float
    active_inpatient_beds: float
    bed_occupancy_pct: float
    available_stock_ors: float
    available_stock_pctm: float
    doctor_utilization_pct: float
    unmet_demand_cumulative: float
    active_stockouts: int
    spillover_events_today: int


class SimulationRunResult(BaseModel):
    """Outcome of a single SimPy run (either Baseline or Mitigated)."""
    mode: str = Field(..., description="'BASELINE_UNMITIGATED' or 'RESILIA_MITIGATED'")
    time_series: List[SimPyTimeSeriesPoint]
    cascade_events: List[CascadingFailureEvent]
    resilience_score: float = Field(..., description="Overall resilience rating (0 to 100)")
    total_patients_served: float
    total_unmet_patients: float
    stockout_events_count: int
    total_stockout_facility_days: float
    peak_bed_occupancy_pct: float
    simulation_runtime_ms: float


class ResilienceComparison(BaseModel):
    """Side-by-side Before vs After benchmark for judge presentation."""
    scenario: ParsedCrisisScenario
    baseline: SimulationRunResult
    resilia_mitigated: SimulationRunResult
    resilience_score_baseline: float
    resilience_score_mitigated: float
    resilience_gain_pct: float
    avoided_stockouts: int
    safeguarded_patients: float
    prevented_spillover_cascades: int
    autonomous_interventions_dispatched: List[Dict[str, Any]] = Field(default_factory=list)
    executive_summary: str


# ─── Federated Intelligence (Flower + PyTorch) ────────────────────────────

class FederatedTrainingRequest(BaseModel):
    """Federated training simulation parameters."""
    rounds: int = Field(5, ge=1, le=15, description="Number of FedAvg aggregation rounds")
    districts: List[str] = Field(
        default_factory=lambda: ["Pune Cluster", "Mumbai Cluster", "Nashik Cluster", "Bengaluru Hub", "Delhi NCR"],
        description="Participating regional federated nodes"
    )
    differential_privacy_epsilon: float = Field(1.2, description="Differential privacy budget epsilon (e.g. 1.2)")
    local_epochs_per_round: int = Field(3, ge=1, le=10)


class FederatedRoundMetric(BaseModel):
    """Round-by-round federated training metrics."""
    round_idx: int
    global_loss: float
    validation_mae: float
    client_losses: Dict[str, float]
    active_clients: int
    communication_payload_kb: float
    differential_privacy_applied: bool = True


class FederatedTrainingResult(BaseModel):
    """Outcome of multi-district federated collaborative learning."""
    rounds_completed: int
    participating_districts: List[str]
    initial_global_loss: float
    final_global_loss: float
    loss_reduction_pct: float
    final_validation_mae: float
    metrics: List[FederatedRoundMetric]
    privacy_certificate: Dict[str, Any]
    model_architecture: str = "Resilia-FedSurge-MLP (PyTorch)"
    status: str = "CONVERGED"
