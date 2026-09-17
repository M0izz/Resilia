"""
RESILIA Resource Agent — Sprint 3
=================================
Autonomous Resource Optimization Agent that detects healthcare shortages,
identifies regional network surpluses, coordinates mathematical optimization via
Google OR-Tools, and operationalizes recommendations into intervention plans.

Features:
  • Receives problem signals from Sentinel Agent / Forecast Engine
  • Coordinates network-wide candidate surplus identification
  • Triggers OR-Tools Mixed-Integer Linear Programming reallocation
  • Delegates human-readable plan formulation to Response Agent
  • Thread-safe in-memory cache & DynamoDB persistence
  • Out-of-the-box demo story: PHC-042 ORS 4-day stock-out mitigation
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from app.agents.response_agent import ResponseAgent
from app.events.event_bus import EventType, OperationalEvent, event_bus
from app.models.optimization import (
    OperationalInterventionPlan,
    OptimizationRequest,
    OptimizationResult,
    SurplusCandidate,
)
from app.services.optimization_engine import OptimizationEngine
from app.services.resource_finder import ResourceFinder, _is_db_reachable
from app.services.workflow_executor import WorkflowExecutor

logger = logging.getLogger(__name__)


class ResourceAgent:
    """
    Autonomous Resource Optimization & Intervention Agent for RESILIA.
    """

    def __init__(self):
        self._plans: dict[str, OperationalInterventionPlan] = {}
        self._lock = threading.Lock()
        self._initialized = False

    def start(self) -> None:
        """Initialize the agent and pre-seed the flagship Sprint 3 showcase plan."""
        with self._lock:
            if self._initialized:
                return
            self._initialized = True

            # Register event subscriber for automated reactive planning
            event_bus.subscribe(EventType.INVENTORY_UPDATED, self._handle_inventory_event)

            # Generate the primary demo story intervention: PHC-042 ORS Stock-out
            try:
                self._seed_flagship_demo_plan()
            except Exception as exc:
                logger.warning("ResourceAgent: Failed to pre-seed flagship demo plan: %s", exc)

            logger.info("ResourceAgent initialized successfully.")

    def _seed_flagship_demo_plan(self) -> None:
        """
        Pre-seeds the flagship demo scenario requested in Sprint 3:
          Target: PHC Hadapsar (MH-PUN-042)
          Problem: ORS stock-out predicted in 4.2 days (450 units remaining, burn 70.3/day)
          Network Surplus:
            • PHC-018 → 8.2 days surplus (Pimpri Hub)
            • PHC-027 → 12.5 days surplus (Satara Central)
            • PHC-061 → 5.4 days surplus (Solapur East)
          Recommended: Transfer 1,000 ORS units from PHC-018 (or optimal combination)
          Transport: Vehicle V-17, ETA 4.8-5.0 hours
        """
        target_phc_id = "MH-PUN-042"
        target_name = "PHC Hadapsar"
        target_district = "Pune"
        target_state = "Maharashtra"
        medicine_code = "ORS-001"
        medicine_name = "Oral Rehydration Salts"
        current_stock = 450.0
        daily_burn = 70.3
        stock_out_days = 4.2
        target_deficit = 1000.0  # Desired replenishment

        candidates = ResourceFinder._generate_fallback_candidates(
            target_phc_id=target_phc_id,
            medicine_code=medicine_code,
            target_lat=18.5089,
            target_lng=73.9260,
            target_district=target_district,
            target_state=target_state,
            safety_stock_days=7.0,
        )

        opt_result = OptimizationEngine.solve(
            target_phc_id=target_phc_id,
            target_phc_name=target_name,
            target_district=target_district,
            medicine_code=medicine_code,
            medicine_name=medicine_name,
            deficit_units=target_deficit,
            candidates=candidates,
            vehicle_capacity=3000.0,
        )

        plan = ResponseAgent.generate_plan(
            target_phc_id=target_phc_id,
            target_phc_name=target_name,
            target_district=target_district,
            medicine_code=medicine_code,
            medicine_name=medicine_name,
            current_stock=current_stock,
            daily_burn=daily_burn,
            stock_out_days=stock_out_days,
            optimization_result=opt_result,
            candidate_surplus=candidates,
        )

        # Standardize demo ID for predictable testing
        plan.plan_id = "INTV-DEMO-PUN-042"
        self._plans[plan.plan_id] = plan
        logger.info("Flagship demo plan INTV-DEMO-PUN-042 pre-seeded.")

    def plan_intervention(self, req: OptimizationRequest) -> OperationalInterventionPlan:
        """
        Execute the full pipeline on-demand:
          Collect parameters → ResourceFinder → OR-Tools → ResponseAgent → Cache
        """
        # 1. Fetch target PHC metadata
        phc_info = self._get_phc_metadata(req.target_phc_id)
        target_name = phc_info.get("name", f"PHC {req.target_phc_id}")
        target_district = phc_info.get("district", "Unknown")
        target_state = phc_info.get("state", "Maharashtra")
        target_lat = float(phc_info.get("lat", 18.5204))
        target_lng = float(phc_info.get("lng", 73.8567))

        # 2. Fetch inventory & deficit
        inv_info = self._get_inventory_metadata(req.target_phc_id, req.medicine_code)
        med_name = inv_info.get("medicine_name", "Essential Medicine")
        current_stock = float(inv_info.get("quantity", 300.0))
        daily_burn = float(inv_info.get("daily_consumption", 50.0))
        if daily_burn <= 0:
            daily_burn = 50.0
        stock_out_days = current_stock / daily_burn

        needed_target_units = daily_burn * req.target_stock_days
        deficit_units = max(100.0, round(needed_target_units - current_stock, 0))

        # 3. Find qualified surplus candidates
        candidates = ResourceFinder.find_surplus_candidates(
            target_phc_id=req.target_phc_id,
            medicine_code=req.medicine_code,
            target_lat=target_lat,
            target_lng=target_lng,
            target_district=target_district,
            target_state=target_state,
            safety_stock_days=req.safety_stock_days,
            max_distance_km=req.max_distance_km,
            allow_cross_district=req.allow_cross_district,
            min_surplus_days=req.min_surplus_days,
        )

        # 4. Run OR-Tools optimization
        opt_result = OptimizationEngine.solve(
            target_phc_id=req.target_phc_id,
            target_phc_name=target_name,
            target_district=target_district,
            medicine_code=req.medicine_code,
            medicine_name=med_name,
            deficit_units=deficit_units,
            candidates=candidates,
            vehicle_capacity=req.vehicle_capacity,
        )

        # 5. Operationalize via Response Agent
        plan = ResponseAgent.generate_plan(
            target_phc_id=req.target_phc_id,
            target_phc_name=target_name,
            target_district=target_district,
            medicine_code=req.medicine_code,
            medicine_name=med_name,
            current_stock=current_stock,
            daily_burn=daily_burn,
            stock_out_days=stock_out_days,
            optimization_result=opt_result,
            candidate_surplus=candidates,
        )

        with self._lock:
            self._plans[plan.plan_id] = plan

        return plan

    def get_plan(self, plan_id: str) -> Optional[OperationalInterventionPlan]:
        with self._lock:
            return self._plans.get(plan_id)

    def list_plans(self, status: Optional[str] = None) -> list[OperationalInterventionPlan]:
        with self._lock:
            plans = list(self._plans.values())

        if status:
            plans = [p for p in plans if p.status.upper() == status.upper()]

        return sorted(plans, key=lambda p: p.created_at, reverse=True)

    def approve_plan(
        self,
        plan_id: str,
        approved_by: str,
        note: Optional[str] = None,
    ) -> dict:
        """Approve plan and trigger the Step Functions simulation workflow."""
        plan = self.get_plan(plan_id)
        if not plan:
            raise KeyError(f"Intervention plan {plan_id} not found")

        if plan.status == "APPROVED":
            return plan.workflow_execution or {"status": "ALREADY_APPROVED"}

        workflow_trace = WorkflowExecutor.execute_approval(
            plan=plan,
            approved_by=approved_by,
            note=note,
        )
        return workflow_trace

    def modify_plan(
        self,
        plan_id: str,
        override_quantity: Optional[float],
        selected_source_id: Optional[str],
        modified_by: str,
        notes: Optional[str] = None,
    ) -> OperationalInterventionPlan:
        """Human modifications to plan parameters."""
        plan = self.get_plan(plan_id)
        if not plan:
            raise KeyError(f"Intervention plan {plan_id} not found")

        with self._lock:
            if override_quantity and override_quantity > 0:
                plan.total_units = override_quantity
                if plan.routes:
                    plan.routes[0].quantity = override_quantity
                plan.recommended_action = (
                    f"[MODIFIED by {modified_by}] Transfer {override_quantity:,.0f} units of {plan.medicine_name} "
                    f"from {plan.primary_source_phc_name} to {plan.target_phc_name}."
                )

            if selected_source_id:
                plan.primary_source_phc_id = selected_source_id
                if plan.routes:
                    plan.routes[0].source_phc_id = selected_source_id

            plan.status = "MODIFIED"
            plan.modification_notes = notes or f"Modified by {modified_by}"

        return plan

    def reject_plan(self, plan_id: str, rejected_by: str, reason: str) -> OperationalInterventionPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise KeyError(f"Intervention plan {plan_id} not found")

        with self._lock:
            plan.status = "REJECTED"
            plan.rejection_reason = f"Rejected by {rejected_by}: {reason}"

        return plan

    # ── Helpers ────────────────────────────────────────────────────────────

    def _get_phc_metadata(self, phc_id: str) -> dict:
        if _is_db_reachable():
            try:
                from app.db.dynamodb import Tables
                from boto3.dynamodb.conditions import Key
                resp = Tables.phcs().get_item(Key={"phc_id": phc_id})
                if "Item" in resp:
                    return resp["Item"]
            except Exception:
                pass

        # Demo fallback
        if "042" in phc_id or "PUN" in phc_id:
            return {"phc_id": phc_id, "name": "PHC Hadapsar", "district": "Pune", "state": "Maharashtra", "lat": 18.5089, "lng": 73.9260}
        return {"phc_id": phc_id, "name": f"PHC {phc_id}", "district": "Central", "state": "Maharashtra", "lat": 18.5204, "lng": 73.8567}

    def _get_inventory_metadata(self, phc_id: str, medicine_code: str) -> dict:
        if _is_db_reachable():
            try:
                from app.db.dynamodb import Tables
                from boto3.dynamodb.conditions import Key
                resp = Tables.inventory().get_item(Key={"phc_id": phc_id, "medicine_code": medicine_code})
                if "Item" in resp:
                    return resp["Item"]
            except Exception:
                pass

        # Demo fallback
        if medicine_code == "ORS-001":
            return {"medicine_name": "Oral Rehydration Salts", "quantity": 450.0, "daily_consumption": 70.3}
        return {"medicine_name": medicine_code, "quantity": 300.0, "daily_consumption": 40.0}

    def _handle_inventory_event(self, event: OperationalEvent) -> None:
        """Autonomous reactive listener."""
        # When inventory is reported dangerously low, auto-generate plan if not already active
        payload = event.payload or {}
        if payload.get("days_of_stock", 999) < 5.0 and "medicine_code" in payload:
            logger.info("ResourceAgent: Auto-triggering plan for low stock event at %s", event.phc_id)
            try:
                self.plan_intervention(
                    OptimizationRequest(
                        target_phc_id=event.phc_id,
                        medicine_code=payload["medicine_code"],
                    )
                )
            except Exception as e:
                logger.debug("ResourceAgent background auto-plan skipped: %s", e)


resource_agent = ResourceAgent()
