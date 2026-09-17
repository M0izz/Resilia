"""
FastAPI Router for the Canonical Judge Demonstration Pipeline.
Exposes endpoints to run and inspect the end-to-end judge demonstration scenario.
"""
from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter, Body

from app.services.judge_demo import judge_demo_engine, CanonicalJudgeScenarioReport

router = APIRouter(prefix="/demo", tags=["Canonical Judge Demonstration"])


@router.post("/run-canonical-scenario", response_model=CanonicalJudgeScenarioReport)
async def run_canonical_judge_demo(payload: Dict[str, Any] = Body(default_factory=dict)):
    """
    Execute the single unified judge demonstration flow:
    Real-World Shock -> Sensing -> Risk Detection -> Predictive Failure ->
    SimPy 'What-If' Simulation -> OR-Tools Optimization -> Human Approval ->
    AWS Step Functions Execution -> Measurable Impact -> Federated Learning.
    """
    approved_by = payload.get("approved_by", "Dr. Priya Sharma (District Health Officer, Pune)")
    report = judge_demo_engine.execute_canonical_scenario(approved_by=approved_by)
    return report


@router.get("/canonical-scenario-status", response_model=CanonicalJudgeScenarioReport)
async def get_canonical_judge_demo_status():
    """Retrieve the latest executed canonical judge demonstration report and metrics."""
    return judge_demo_engine.get_status()
