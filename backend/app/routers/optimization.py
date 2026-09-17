"""
RESILIA Optimization & Response Router — Sprint 3
=================================================
FastAPI endpoints for:
  • Triggering OR-Tools redistribution plans
  • Querying network surplus candidates
  • Inspecting operational intervention plans
  • Human-in-the-loop approval, modification, and rejection
  • Step Functions execution tracking
"""
from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.agents.resource_agent import resource_agent
from app.models.optimization import (
    OperationalInterventionPlan,
    OptimizationRequest,
    PlanApprovalRequest,
    PlanModifyRequest,
    PlanRejectRequest,
    SurplusCandidate,
)
from app.services.resource_finder import ResourceFinder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimization", tags=["optimization"])


@router.post("/plan", response_model=OperationalInterventionPlan)
def create_intervention_plan(request: OptimizationRequest):
    """
    Trigger network surplus discovery, OR-Tools Mixed-Integer Linear Programming,
    and Response Agent synthesis to generate a complete Operational Intervention Plan.
    """
    try:
        plan = resource_agent.plan_intervention(request)
        return plan
    except Exception as exc:
        logger.error("Failed to generate intervention plan: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(exc)}")


@router.get("/plans", response_model=list[OperationalInterventionPlan])
def list_intervention_plans(status: Optional[str] = Query(None, description="Filter by plan status")):
    """List all intervention plans (awaiting approval, approved, modified, rejected)."""
    return resource_agent.list_plans(status=status)


@router.get("/plans/{plan_id}", response_model=OperationalInterventionPlan)
def get_intervention_plan(plan_id: str):
    """Fetch complete intervention plan details including OR-Tools proof and Step Functions trace."""
    plan = resource_agent.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return plan


@router.post("/plans/{plan_id}/approve")
def approve_intervention_plan(plan_id: str, req: PlanApprovalRequest):
    """
    Human Approves the Intervention Plan.
    Triggers simulated AWS Step Functions state machine execution:
      1. Inventory debit & credit
      2. Shipment record creation with tracking
      3. EventBridge event notification
      4. DynamoDB audit record logging
    """
    try:
        trace = resource_agent.approve_plan(
            plan_id=plan_id,
            approved_by=req.approved_by,
            note=req.note,
        )
        return {
            "status": "APPROVED",
            "plan_id": plan_id,
            "workflow_execution": trace,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    except Exception as exc:
        logger.error("Error approving plan %s: %s", plan_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Approval workflow execution failed: {str(exc)}")


@router.post("/plans/{plan_id}/modify", response_model=OperationalInterventionPlan)
def modify_intervention_plan(plan_id: str, req: PlanModifyRequest):
    """Human modifies allocation quantity or source facility before approving."""
    try:
        plan = resource_agent.modify_plan(
            plan_id=plan_id,
            override_quantity=req.override_quantity,
            selected_source_id=req.selected_source_phc_id,
            modified_by=req.modified_by,
            notes=req.notes,
        )
        return plan
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")


@router.post("/plans/{plan_id}/reject", response_model=OperationalInterventionPlan)
def reject_intervention_plan(plan_id: str, req: PlanRejectRequest):
    """Human rejects the intervention plan with a logged reason."""
    try:
        plan = resource_agent.reject_plan(
            plan_id=plan_id,
            rejected_by=req.rejected_by,
            reason=req.reason,
        )
        return plan
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")


@router.get("/surplus/{medicine_code}", response_model=list[SurplusCandidate])
def get_network_surplus(
    medicine_code: str,
    target_phc_id: str = Query("MH-PUN-042", description="Reference destination PHC ID"),
):
    """Inspect all candidate facilities holding surplus of the specified medicine."""
    meta = resource_agent._get_phc_metadata(target_phc_id)
    candidates = ResourceFinder.find_surplus_candidates(
        target_phc_id=target_phc_id,
        medicine_code=medicine_code,
        target_lat=float(meta.get("lat", 18.5204)),
        target_lng=float(meta.get("lng", 73.8567)),
        target_district=meta.get("district", "Pune"),
        target_state=meta.get("state", "Maharashtra"),
    )
    return candidates
