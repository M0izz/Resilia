"""
FastAPI Router for the Complete Agentic Loop Lifecycle.
Exposes endpoints to trigger and trace the full 10-phase autonomous pipeline.
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, Body

from app.services.agentic_loop import agentic_orchestrator, AgenticLoopTrace

router = APIRouter(prefix="/agentic-loop", tags=["Complete 10-Phase Agentic Loop"])


@router.post("/run", response_model=AgenticLoopTrace)
async def run_full_agentic_loop(payload: Dict[str, Any] = Body(default_factory=dict)):
    """
    Trigger the complete 10-phase autonomous agentic resilience lifecycle:
    Monitoring -> Sentinel Detect -> Forecast Predict -> Crisis Simulate ->
    Resource Optimize -> Response Plan -> Human Approval -> AWS Execution ->
    AI Decision Audit -> Federated Learning Model Refinement.
    """
    facility_id = payload.get("facility_id", "MH-PUN-042")
    facility_name = payload.get("facility_name", "PHC Hadapsar")
    district = payload.get("district", "Pune")
    approved_by = payload.get("approved_by", "Dr. Priya Sharma (District Health Officer, Pune)")

    trace = agentic_orchestrator.execute_loop(
        facility_id=facility_id,
        facility_name=facility_name,
        district=district,
        auto_approve=True,
        approved_by=approved_by,
    )
    return trace


@router.get("/status", response_model=AgenticLoopTrace)
async def get_latest_loop_status():
    """Retrieve the latest complete agentic loop execution trace and intermediate artifacts."""
    return agentic_orchestrator.get_latest_trace()
