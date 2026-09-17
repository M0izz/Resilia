"""
RESILIA Event Bus Endpoints — Sprint 2
========================================
Ingest and monitor operational telemetry events.
Simulates AWS EventBridge for interactive testing and dashboard display.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.events.event_bus import EventType, OperationalEvent, event_bus

router = APIRouter(prefix="/events", tags=["events"])


# ─── Request schema ───────────────────────────────────────────────────────

class EmitEventRequest(BaseModel):
    event_type: EventType
    phc_id: str
    payload: dict = {}
    source: Optional[str] = "api.manual"


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.post("/emit")
async def emit_event(body: EmitEventRequest):
    """
    Inject an operational event into the RESILIA event bus.

    The event is immediately stored in the recent events deque and
    queued for async processing by all subscribed handlers
    (including the Sentinel Agent).

    Example payloads:
      SUPPLIER_DELAYED:  {"delay_days": 8, "supplier_name": "PharmaCo"}
      PATIENT_SURGE:     {"patient_7d_change_pct": 35}
      INVENTORY_UPDATED: {"medicine_code": "ORS-001", "new_quantity": 50}

    Returns the event_id for correlation with sentinel decisions.
    """
    event = OperationalEvent(
        event_type=body.event_type,
        phc_id=body.phc_id,
        payload=body.payload,
        source=body.source or "api.manual",
    )
    event_id = event_bus.emit(event)
    return {
        "status":     "emitted",
        "event_id":   event_id,
        "event_type": body.event_type.value,
        "phc_id":     body.phc_id,
        "timestamp":  event.timestamp,
    }


@router.get("/recent")
async def get_recent_events(
    limit: int = Query(50, ge=1, le=200, description="Max events to return"),
    event_type: Optional[EventType] = Query(None, description="Filter by event type"),
    phc_id: Optional[str] = Query(None, description="Filter by PHC ID"),
):
    """
    Retrieve recent operational events from the event stream.

    Returns newest events first. Events are kept in a rolling in-memory
    window of the last 200 events.
    """
    events = event_bus.recent_events(limit=limit * 3)

    if event_type:
        events = [e for e in events if e["event_type"] == event_type.value]
    if phc_id:
        events = [e for e in events if e["phc_id"] == phc_id]

    return events[:limit]


@router.get("/types")
async def list_event_types():
    """List all supported operational event types."""
    return [{"event_type": et.value, "description": _EVENT_DESCRIPTIONS.get(et.value, "")}
            for et in EventType]


_EVENT_DESCRIPTIONS = {
    "INVENTORY_UPDATED":  "Medicine stock level changed at a PHC",
    "PATIENT_LOGGED":     "New patient visit recorded",
    "SUPPLIER_DELAYED":   "Replenishment shipment delayed",
    "SHIPMENT_UPDATED":   "Shipment status change (dispatched / delivered / cancelled)",
    "PATIENT_SURGE":      "Unexpected spike in patient footfall detected",
    "STAFF_SHORTAGE":     "Doctor or nurse attendance below threshold",
    "BED_OVERFLOW":       "Bed occupancy exceeds 95% capacity",
    "RISK_ESCALATED":     "PHC risk score crossed severity threshold",
}
