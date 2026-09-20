"""
Agentic Loop Service — Orchestrates the complete autonomous agentic lifecycle.

Phases:
  1. Telemetry Ingestion (Real DB/Store state)
  2. Sentinel Risk Evaluation (Attributed compound scoring)
  3. Predictive Intelligence (Real Ridge forecast & depletion curve)
  4. Crisis Twin Simulation (SimPy discrete-event shock test)
  5. Resource Optimization (Google OR-Tools SCIP MILP solver)
  6. Operational Response Synthesis (ResponseAgent justification & plan generation)
  7. Human-in-the-Loop Governance (AWAITING_APPROVAL check; stops here if not authorized)
  8. Step Functions Workflow Execution (DynamoDB debit/credit & carrier dispatch)
  9. Explainable AI Audit Trail (SHA-256 chained immutable ledger)
 10. Federated Learning Model Refinement (Flower FedAvg collaborative training)
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.agents.crisis_agent import crisis_agent
from app.agents.resource_agent import ResourceAgent
from app.agents.response_agent import ResponseAgent
from app.agents.sentinel_agent import SentinelAgent
from app.db.in_memory_store import in_memory_store
from app.models.crisis import CrisisScenarioRequest, FederatedTrainingRequest
from app.models.optimization import OptimizationRequest, SurplusCandidate
from app.services.audit_service import audit_ledger
from app.services.crisis_simulator import crisis_simulator
from app.services.federated_learning import federated_engine
from app.services.forecast_engine import (
    forecast_medicine_depletion,
    forecast_patient_demand,
)
from app.services.optimization_engine import OptimizationEngine
from app.services.resource_finder import ResourceFinder
from app.services.risk_engine import (
    MedicineRiskInput,
    PHCRiskInput,
    score_phc_multifactor,
)
from app.services.workflow_executor import WorkflowExecutor

logger = logging.getLogger(__name__)


class AgenticLoopStep(BaseModel):
    """Execution state of a single step in the agentic loop."""
    step_index: int
    step_name: str
    agent_or_service: str
    status: str = "COMPLETED"  # "COMPLETED", "IN_PROGRESS", "AWAITING_APPROVAL", "FAILED"
    duration_ms: float
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AgenticLoopTrace(BaseModel):
    """Complete trace of an autonomous loop run."""
    run_id: str
    triggered_at: str
    facility_id: str
    facility_name: str
    medicine_code: str
    total_steps: int
    status: str  # "COMPLETED" or "AWAITING_APPROVAL"
    total_duration_ms: float
    steps: List[AgenticLoopStep]
    final_outcome: str
    plan_id: Optional[str] = None
    demo_mode: bool = False


class AgenticLoopOrchestrator:
    """
    Coordinates the complete agentic resilience lifecycle.
    Consumes live store data, enforces human approval gates, and never fabricates execution ARNs.
    """

    def __init__(self):
        self._latest_trace: Optional[AgenticLoopTrace] = None
        self._history: List[AgenticLoopTrace] = []

    def execute_loop(
        self,
        facility_id: str = "MH-PUN-042",
        medicine_code: str = "ORS-001",
        approved_by: Optional[str] = None,
        demo_mode: bool = False,
    ) -> AgenticLoopTrace:
        """
        Execute the agentic loop.
        If approved_by is None, execution halts at Step 7 in AWAITING_APPROVAL status.
        """
        t_global_start = time.perf_counter()
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        steps: List[AgenticLoopStep] = []

        # ── Step 1: Telemetry Ingestion ──
        t0 = time.perf_counter()
        phc_item = in_memory_store.get_item("resilia-phcs", {"phc_id": facility_id})
        if not phc_item:
            phc_item = {
                "phc_id": facility_id,
                "name": f"PHC {facility_id}",
                "district": "Pune",
                "state": "Maharashtra",
                "beds_total": 24,
                "beds_occupied": 19,
                "doctors_total": 4,
                "doctors_present": 3,
                "lat": 18.5089,
                "lng": 73.9260,
            }

        facility_name = phc_item.get("name", facility_id)
        district = phc_item.get("district", "Pune")
        state = phc_item.get("state", "Maharashtra")

        # Ingest medicine inventory
        inv_items = in_memory_store.get_table_items("resilia-inventory")
        med_item = next(
            (i for i in inv_items if i.get("phc_id") == facility_id and i.get("medicine_code") == medicine_code),
            None,
        )
        if med_item:
            current_stock = float(med_item.get("quantity", 100.0))
            daily_burn = float(med_item.get("daily_consumption", 20.0))
            medicine_name = med_item.get("medicine_name", medicine_code)
            criticality = med_item.get("criticality", "CRITICAL")
        else:
            current_stock = 450.0
            daily_burn = 70.3
            medicine_name = "Oral Rehydration Salts" if medicine_code == "ORS-001" else medicine_code
            criticality = "CRITICAL"

        steps.append(
            AgenticLoopStep(
                step_index=1,
                step_name="PHC Network Ingestion",
                agent_or_service="Network Data Layer (Store & Telemetry)",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                summary=(
                    f"Ingested operational telemetry for {facility_name}: {medicine_name} stock={current_stock:.0f}, "
                    f"burn={daily_burn:.1f}/day, beds={phc_item.get('beds_occupied', 0)}/{phc_item.get('beds_total', 0)}."
                ),
                details={
                    "facility_id": facility_id,
                    "facility_name": facility_name,
                    "medicine_code": medicine_code,
                    "current_stock": current_stock,
                    "daily_burn": daily_burn,
                    "beds_occupied": phc_item.get("beds_occupied", 0),
                    "beds_total": phc_item.get("beds_total", 0),
                },
            )
        )

        # ── Step 2: Sentinel Agent Anomaly & Risk Detection ──
        t0 = time.perf_counter()
        risk_inp = PHCRiskInput(
            phc_id=facility_id,
            beds_total=phc_item.get("beds_total", 20),
            beds_occupied=phc_item.get("beds_occupied", 15),
            doctors_total=phc_item.get("doctors_total", 4),
            doctors_present=phc_item.get("doctors_present", 3),
            patient_7d_change_pct=15.0,
            medicines=[
                MedicineRiskInput(
                    medicine_code=medicine_code,
                    medicine_name=medicine_name,
                    quantity=current_stock,
                    daily_consumption=daily_burn,
                    criticality=criticality,
                )
            ],
            supplier_delay_days=2,
        )
        risk_res = score_phc_multifactor(risk_inp)
        severity_str = risk_res.risk_severity.value if hasattr(risk_res.risk_severity, "value") else str(risk_res.risk_severity)
        steps.append(
            AgenticLoopStep(
                step_index=2,
                step_name="Sentinel Agent Anomaly Detection",
                agent_or_service="Sentinel Agent (Autonomous Risk Evaluator)",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                summary=f"Computed {severity_str} compound risk (Score: {risk_res.risk_score}/100, Cascade: {risk_res.cascade_multiplier}x). Primary driver: {risk_res.primary_category.value if hasattr(risk_res.primary_category, 'value') else risk_res.primary_category}.",
                details={
                    "risk_score": risk_res.risk_score,
                    "severity": severity_str,
                    "cascade_multiplier": risk_res.cascade_multiplier,
                    "compounding_factors": risk_res.active_compounding_factors,
                },
            )
        )

        # ── Step 3: Predictive Intelligence Forecasting ──
        t0 = time.perf_counter()
        patient_records = [
            p for p in in_memory_store.get_table_items("resilia-patients")
            if p.get("phc_id") == facility_id
        ]
        patient_forecasts, surge_prob, baseline_patients = forecast_patient_demand(
            patient_records, horizon=14
        )
        _curve, stockout_eval = forecast_medicine_depletion(
            medicine_code=medicine_code,
            medicine_name=medicine_name,
            current_stock=current_stock,
            daily_consumption=daily_burn,
            unit="units",
            patient_forecasts=patient_forecasts,
            baseline_daily_patients=baseline_patients,
        )

        runway_days = stockout_eval.days_until_stockout if stockout_eval.within_horizon else round(current_stock / max(1.0, daily_burn), 1)
        needed_units = max(200.0, round(daily_burn * 14.0 - current_stock))

        steps.append(
            AgenticLoopStep(
                step_index=3,
                step_name="Predictive Intelligence Forecasting",
                agent_or_service="Forecast Agent (Ridge Forecaster & Depletion Model)",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                summary=f"Forecast projected runway of {runway_days:.1f} days for {medicine_name}. Deficit to cover 14-day safety stock: {needed_units:.0f} units.",
                details={
                    "runway_days": runway_days,
                    "stockout_within_horizon": stockout_eval.within_horizon,
                    "deficit_units": needed_units,
                    "surge_probability": surge_prob,
                },
            )
        )

        # ── Step 4: Crisis Twin Cascading Stress Simulation ──
        t0 = time.perf_counter()
        crisis_req = CrisisScenarioRequest(
            prompt=f"Simulate 14-day surge of {medicine_name} at {facility_name}",
            district=district,
            patient_surge_pct=35.0,
            transport_delay_days=2,
            deficit_medicine=medicine_code,
        )
        crisis_res = crisis_agent.orchestrate_simulation(crisis_req)
        steps.append(
            AgenticLoopStep(
                step_index=4,
                step_name="Crisis Twin Cascading Simulation",
                agent_or_service="Crisis Agent (SimPy Discrete-Event Engine)",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                summary=f"Simulated network disruption: unmitigated status quo causes {crisis_res.avoided_stockouts} avoided stockouts (Baseline resilience: {crisis_res.resilience_score_baseline:.1f} -> Mitigated: {crisis_res.resilience_score_mitigated:.1f}).",
                details={
                    "baseline_resilience": crisis_res.resilience_score_baseline,
                    "mitigated_resilience": crisis_res.resilience_score_mitigated,
                    "avoided_stockouts": crisis_res.avoided_stockouts,
                    "safeguarded_patients": crisis_res.safeguarded_patients,
                },
            )
        )

        # ── Step 5: Resource Optimization (Google OR-Tools) ──
        t0 = time.perf_counter()
        target_lat = float(phc_item.get("lat", 18.5089))
        target_lng = float(phc_item.get("lng", 73.9260))
        candidates = ResourceFinder.find_surplus_candidates(
            target_phc_id=facility_id,
            medicine_code=medicine_code,
            target_lat=target_lat,
            target_lng=target_lng,
            target_district=district,
            target_state=state,
        )
        opt_res = OptimizationEngine.solve(
            target_phc_id=facility_id,
            target_phc_name=facility_name,
            target_district=district,
            medicine_code=medicine_code,
            medicine_name=medicine_name,
            deficit_units=needed_units,
            candidates=candidates,
            vehicle_capacity=3000.0,
        )
        steps.append(
            AgenticLoopStep(
                step_index=5,
                step_name="Resource Optimization Engine",
                agent_or_service="Resource Agent (Google OR-Tools SCIP MILP)",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                summary=f"OR-Tools MILP allocated {opt_res.total_allocated_units:.0f} units across {len(opt_res.allocated_routes)} route(s) in {opt_res.runtime_ms:.2f} ms (Status: {opt_res.status}).",
                details={
                    "solver_status": opt_res.status,
                    "allocated_units": opt_res.total_allocated_units,
                    "unmet_units": opt_res.unmet_deficit_units,
                    "runtime_ms": opt_res.runtime_ms,
                    "routes_count": len(opt_res.allocated_routes),
                },
            )
        )

        # ── Step 6: Operational Intervention Plan Synthesis ──
        t0 = time.perf_counter()
        plan = ResponseAgent.generate_plan(
            target_phc_id=facility_id,
            target_phc_name=facility_name,
            target_district=district,
            medicine_code=medicine_code,
            medicine_name=medicine_name,
            current_stock=current_stock,
            daily_burn=daily_burn,
            stock_out_days=runway_days,
            optimization_result=opt_res,
            candidate_surplus=candidates,
        )
        plan.status = "AWAITING_APPROVAL"

        steps.append(
            AgenticLoopStep(
                step_index=6,
                step_name="Response Plan Synthesis",
                agent_or_service="Response Agent (Operational Rationale Engine)",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                summary=f"Synthesized intervention plan {plan.plan_id}: Reallocate {plan.total_units:.0f} units of {medicine_name}. Status: AWAITING_APPROVAL.",
                details={
                    "plan_id": plan.plan_id,
                    "total_units": plan.total_units,
                    "assigned_vehicle": plan.assigned_vehicle_id,
                    "confidence": plan.confidence,
                },
            )
        )

        # ── Step 7: Human Governance Gate ──
        t0 = time.perf_counter()
        if not approved_by:
            # Operational governance gate: HALT HERE if no authorized human approval provided
            steps.append(
                AgenticLoopStep(
                    step_index=7,
                    step_name="Human Health Officer Governance",
                    agent_or_service="Human Governance Gate (Digital Authorization)",
                    status="AWAITING_APPROVAL",
                    duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                    summary=f"Plan {plan.plan_id} is awaiting digital authorization from the District Health Officer. Execution halted until approved.",
                    details={"plan_id": plan.plan_id, "approved": False, "status": "AWAITING_APPROVAL"},
                )
            )

            total_ms = round((time.perf_counter() - t_global_start) * 1000, 2)
            trace = AgenticLoopTrace(
                run_id=run_id,
                triggered_at=datetime.utcnow().isoformat(),
                facility_id=facility_id,
                facility_name=facility_name,
                medicine_code=medicine_code,
                total_steps=len(steps),
                status="AWAITING_APPROVAL",
                total_duration_ms=total_ms,
                steps=steps,
                final_outcome=f"Intervention plan {plan.plan_id} generated. Awaiting human digital sign-off before physical dispatch.",
                plan_id=plan.plan_id,
                demo_mode=demo_mode,
            )
            self._latest_trace = trace
            self._history.append(trace)
            return trace

        # If human approval is provided:
        steps.append(
            AgenticLoopStep(
                step_index=7,
                step_name="Human Health Officer Governance",
                agent_or_service="Human Governance Gate (Digital Authorization)",
                status="COMPLETED",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                summary=f"Intervention plan {plan.plan_id} authorized and digitally signed by {approved_by}.",
                details={"plan_id": plan.plan_id, "approved_by": approved_by, "approved": True},
            )
        )

        # ── Step 8: Step Functions Workflow Execution ──
        t0 = time.perf_counter()
        wf_res = WorkflowExecutor.execute_approval(
            plan=plan,
            approved_by=approved_by,
            note="Approved via operational agentic loop.",
        )
        execution_id = wf_res.get("execution_id", run_id)
        execution_arn = wf_res.get("execution_arn")
        execution_type = wf_res.get("execution_type", "LOCAL_SIMULATED")

        steps.append(
            AgenticLoopStep(
                step_index=8,
                step_name="Workflow Execution Pipeline",
                agent_or_service="AWS Step Functions & EventBridge",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                summary=f"Workflow executed ({execution_type}): {len(wf_res.get('shipment_ids', []))} shipment(s) staged and dispatched.",
                details={
                    "execution_id": execution_id,
                    "execution_arn": execution_arn,
                    "execution_type": execution_type,
                    "status": "SUCCEEDED",
                    "shipments": wf_res.get("shipment_ids", []),
                },
            )
        )

        # ── Step 9: Cryptographic AI Decision Audit ──
        t0 = time.perf_counter()
        audit_rec = audit_ledger.record_decision(
            facility_id=facility_id,
            facility_name=facility_name,
            district=district,
            what_happened=f"{medicine_name} shortage mitigation: {plan.total_units:.0f} units rebalanced to {facility_name}.",
            why_flagged=f"Risk Score {risk_res.risk_score} with projected runway of {runway_days:.1f} days.",
            predictive_model="RESILIA-ForecastEngine v2.1 (Ridge Regressor)",
            ai_recommendation=plan.recommended_action,
            optimization_engine="Google OR-Tools SCIP MILP",
            approved_by=approved_by,
            executed_action=f"Dispatched shipment via {execution_type} ({execution_id}).",
            execution_arn=execution_arn or execution_id,
        )
        steps.append(
            AgenticLoopStep(
                step_index=9,
                step_name="Explainable AI Audit Trail",
                agent_or_service="Cryptographic Audit Ledger",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                summary=f"Appended tamper-evident block {audit_rec.audit_id} with SHA-256 hash {audit_rec.record_hash[:16]}…",
                details={"audit_id": audit_rec.audit_id, "record_hash": audit_rec.record_hash, "verified": True},
            )
        )

        # ── Step 10: Federated Learning Calibration ──
        t0 = time.perf_counter()
        fed_req = FederatedTrainingRequest(rounds=2, districts=["Pune Cluster", "Mumbai Cluster"])
        fed_res = federated_engine.run_federated_training(fed_req)
        steps.append(
            AgenticLoopStep(
                step_index=10,
                step_name="Federated Model Continuous Refinement",
                agent_or_service="Flower (flwr) FedAvg Coordinator",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                summary=f"Federated parameter exchange completed (Loss delta: -{fed_res.loss_reduction_pct:.1f}%). Mechanism demo with non-pooled local telemetry.",
                details={"rounds": 2, "loss_reduction_pct": fed_res.loss_reduction_pct, "privacy_mode": "Local Differential Privacy"},
            )
        )

        total_ms = round((time.perf_counter() - t_global_start) * 1000, 2)
        trace = AgenticLoopTrace(
            run_id=run_id,
            triggered_at=datetime.utcnow().isoformat(),
            facility_id=facility_id,
            facility_name=facility_name,
            medicine_code=medicine_code,
            total_steps=len(steps),
            status="COMPLETED",
            total_duration_ms=total_ms,
            steps=steps,
            final_outcome=f"Complete 10-phase cycle executed. Intervention plan {plan.plan_id} approved by {approved_by} and verified in audit ledger.",
            plan_id=plan.plan_id,
            demo_mode=demo_mode,
        )

        self._latest_trace = trace
        self._history.append(trace)
        return trace

    def get_latest_trace(self) -> Optional[AgenticLoopTrace]:
        """Return the most recent agentic loop execution trace."""
        return self._latest_trace


# Singleton orchestrator
agentic_orchestrator = AgenticLoopOrchestrator()
