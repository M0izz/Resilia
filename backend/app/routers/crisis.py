"""
FastAPI Router for Sprint 4: Crisis Digital Twin, SimPy Cascading Stress Tests,
and Flower Federated Intelligence.
"""
from __future__ import annotations
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body

from app.models.crisis import (
    CrisisScenarioRequest,
    ParsedCrisisScenario,
    NetworkGraphResponse,
    ResilienceComparison,
    FederatedTrainingRequest,
    FederatedTrainingResult,
)
from app.agents.crisis_agent import crisis_agent
from app.services.digital_twin import digital_twin
from app.services.federated_learning import federated_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crisis", tags=["Crisis Digital Twin & Federated Intelligence"])


@router.get("/presets", response_model=List[Dict[str, Any]])
@router.get("/scenarios", response_model=List[Dict[str, Any]])
async def get_preset_scenarios():
    """Retrieve catalog of pre-configured high-impact crisis demo scenarios."""
    return crisis_agent.get_presets()


@router.post("/parse-scenario", response_model=ParsedCrisisScenario)
async def parse_crisis_prompt(
    payload: Dict[str, str] = Body(...)
):
    """
    Crisis Agent endpoint: Translates free-form natural language prompts
    into structured digital twin simulation parameters.
    """
    prompt = payload.get("prompt", "")
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="A non-empty 'prompt' is required.")
    return crisis_agent.parse_natural_language_prompt(prompt)


@router.get("/network-graph", response_model=NetworkGraphResponse)
async def get_digital_twin_network():
    """
    Retrieve the current NetworkX topological digital twin snapshot,
    including PHC nodes, hospital referral hubs, central warehouses, and stress metrics.
    """
    return digital_twin.get_snapshot()


@router.post("/simulate", response_model=ResilienceComparison)
async def run_crisis_simulation(request: CrisisScenarioRequest):
    """
    Execute full SimPy discrete-event stress test across the healthcare network.
    Runs both Unmitigated Baseline and RESILIA Autonomous Balancing,
    returning time-series projections, cascading failure event logs,
    and before-vs-after resilience impact benchmarks.
    """
    try:
        comparison = crisis_agent.orchestrate_simulation(request)
        return comparison
    except Exception as exc:
        logger.exception("Simulation execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(exc)}")


@router.post("/federated/train", response_model=FederatedTrainingResult)
async def run_federated_learning_simulation(
    request: FederatedTrainingRequest = Body(default_factory=FederatedTrainingRequest)
):
    """
    Trigger multi-district federated collaborative training (Flower FedAvg simulation).
    Trains PyTorch neural predictors across isolated district nodes with differential privacy,
    collaborating without centralizing raw patient health records.
    """
    try:
        result = federated_engine.run_federated_training(request)
        return result
    except Exception as exc:
        logger.exception("Federated training failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Federated learning error: {str(exc)}")
