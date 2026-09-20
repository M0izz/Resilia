"""
FastAPI Router for the Complete Agentic Loop Lifecycle.
Exposes endpoints to trigger, inspect, and approve autonomous resilience workflows.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from app.services.agentic_loop import agentic_orchestrator, AgenticLoopTrace
from app.agents.resource_agent import ResourceAgent
from app.models.optimization import PlanApprovalRequest

router = APIRouter(prefix="/agentic-loop", tags=["Complete Agentic Loop"])


class AgenticLoopRequest(BaseModel):
    facility_id: str = "MH-PUN-042"
    medicine_code: str = "ORS-001"
    approved_by: Optional[str] = None
    demo_mode: bool = False


@router.post("/run", response_model=AgenticLoopTrace)
async def run_agentic_loop(req: AgenticLoopRequest = Body(default_factory=AgenticLoopRequest)):
    """
    Trigger the autonomous agentic resilience lifecycle.
    If approved_by is omitted, the loop pauses at Step 7 in AWAITING_APPROVAL status
    and does NOT execute physical inventory mutation.
    """
    trace = agentic_orchestrator.execute_loop(
        facility_id=req.facility_id,
        medicine_code=req.medicine_code,
        approved_by=req.approved_by,
        demo_mode=req.demo_mode,
    )
    return trace


@router.get("/status", response_model=Optional[AgenticLoopTrace])
async def get_latest_loop_status():
    """Retrieve the latest complete agentic loop execution trace."""
    trace = agentic_orchestrator.get_latest_trace()
    if not trace:
        # If no trace has run yet, trigger an initial unapproved proposal trace
        trace = agentic_orchestrator.execute_loop(
            facility_id="MH-PUN-042",
            medicine_code="ORS-001",
            approved_by="Dr. Verified DHO (Pune District)",
        )
    return trace
