"""
Unit tests for Phase 2: EventBridge Telemetry Ingestion Schema & Dispatch
========================================================================
Verifies:
  - OperationalEvent.to_eventbridge_entry() formats exact AWS EventBridge PutEventsRequestEntry.
  - Detail is valid JSON string.
  - Resources ARN conforms to arn:aws:resilia:<region>::facility/<phc_id>.
  - EventBus calls put_events when eventbridge_enabled=True.
  - EventBus handles EventBridge exceptions gracefully without disrupting local subscribers.
"""
import json
from unittest.mock import MagicMock
from app.config import settings
from app.events.event_bus import EventBus, EventType, OperationalEvent


def test_eventbridge_entry_format():
    event = OperationalEvent(
        event_type=EventType.INVENTORY_UPDATED,
        phc_id="PHC-PUN-001",
        payload={"medicine_code": "ORS-001", "quantity": 120, "daily_consumption": 40},
    )

    entry = event.to_eventbridge_entry()

    assert entry["Source"] == "resilia.telemetry"
    assert entry["DetailType"] == "INVENTORY_UPDATED"
    assert entry["EventBusName"] == settings.event_bus_name
    assert entry["Resources"] == [f"arn:aws:resilia:{settings.aws_region}::facility/PHC-PUN-001"]
    assert "Time" in entry

    # Detail must be valid serialized JSON
    detail = json.loads(entry["Detail"])
    assert detail["medicine_code"] == "ORS-001"
    assert detail["quantity"] == 120


def test_eventbridge_put_events_dispatched_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "eventbridge_enabled", True)

    mock_boto_client = MagicMock()
    mock_boto_client.put_events.return_value = {
        "FailedEntryCount": 0,
        "Entries": [{"EventId": "aws-eb-test-id-123"}],
    }

    monkeypatch.setattr("boto3.client", lambda service, **kwargs: mock_boto_client if service == "events" else MagicMock())

    bus = EventBus()
    event = OperationalEvent(
        event_type=EventType.SUPPLIER_DELAYED,
        phc_id="PHC-MAH-002",
        payload={"delay_days": 5},
    )

    event_id = bus.emit(event)
    assert event_id == event.event_id

    # Check put_events was called with matching entry
    assert mock_boto_client.put_events.called
    call_args = mock_boto_client.put_events.call_args[1]
    entries = call_args["Entries"]
    assert len(entries) == 1
    assert entries[0]["DetailType"] == "SUPPLIER_DELAYED"
    assert entries[0]["Source"] == "resilia.telemetry"


def test_eventbridge_exception_does_not_break_local_bus(monkeypatch):
    monkeypatch.setattr(settings, "eventbridge_enabled", True)

    def failing_put_events(*args, **kwargs):
        raise RuntimeError("AWS EventBridge simulated timeout")

    mock_client = MagicMock()
    mock_client.put_events.side_effect = failing_put_events
    monkeypatch.setattr("boto3.client", lambda service, **kwargs: mock_client)

    bus = EventBus()
    received = []
    bus.subscribe(EventType.BED_OVERFLOW, lambda ev: received.append(ev.phc_id))
    bus.start()

    try:
        bus.emit(OperationalEvent(
            event_type=EventType.BED_OVERFLOW,
            phc_id="PHC-LOCAL-001",
            payload={"beds_occupied": 25, "beds_total": 20},
        ))

        # Wait shortly for background worker
        import time
        for _ in range(20):
            if received:
                break
            time.sleep(0.05)

        assert "PHC-LOCAL-001" in received
    finally:
        bus.stop()
