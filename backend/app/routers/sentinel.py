"""
RESILIA Sentinel Agent Endpoints — Sprint 2
=============================================
Control plane and observability API for the Autonomous Sentinel Agent.
"""
from fastapi import APIRouter, Query

from app.agents.sentinel_agent import sentinel_agent

router = APIRouter(prefix="/sentinel", tags=["sentinel"])


@router.get("/status")
async def get_sentinel_status():
    """
    Retrieve Sentinel Agent health and operational statistics.

    Returns:
      - running: whether the agent is active
      - uptime_seconds: seconds since agent start
      - scan_interval_s: periodic scan frequency
      - scans_completed: total network-wide scans run
      - anomalies_detected: total anomalies identified across all scans
      - alerts_escalated: total autonomous alerts written to DynamoDB
      - decisions_logged: decisions held in memory (rolling window)
      - event_bus_processed: total events processed by the event bus
    """
    return sentinel_agent.status()


@router.post("/scan")
async def trigger_sentinel_scan():
    """
    Manually trigger a full network-wide Sentinel inspection.

    The agent evaluates every PHC in the database using multi-factor
    cascading risk scoring. Returns a scan summary including:
      - PHCs evaluated
      - Anomalies found
      - Duration in seconds

    Note: Scans are protected by a reentrant lock — concurrent requests
    queue behind the active scan rather than running in parallel.
    """
    summary = sentinel_agent.scan_network()
    return summary


@router.get("/decisions")
async def get_sentinel_decisions(
    limit: int = Query(50, ge=1, le=200, description="Max decisions to return"),
    phc_id: str = Query(None, description="Filter by PHC ID"),
    action: str = Query(None, description="Filter by action: ALERT_ESCALATED | MONITORING | CLEAR"),
):
    """
    Retrieve recent autonomous agent decisions and reasoning.

    Returns the last `limit` decisions, newest first.
    Each decision includes:
      - trigger: what caused the evaluation (event type or PERIODIC_SCAN)
      - risk_score / risk_severity: cascaded multi-factor score
      - cascade_multiplier: compounding factor (1.0 = no cascade)
      - active_compounding_factors: list of co-occurring risk signals
      - reasoning: full plain-English agent explanation
      - action_taken: what the agent did (escalated alert / monitoring / clear)
    """
    decisions = sentinel_agent.recent_decisions(limit=limit * 3)  # over-fetch then filter

    if phc_id:
        decisions = [d for d in decisions if d["phc_id"] == phc_id]
    if action:
        decisions = [d for d in decisions if d["action_taken"] == action]

    return decisions[:limit]
