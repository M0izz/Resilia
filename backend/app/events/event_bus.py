"""
RESILIA Event Bus — Sprint 2
==============================
In-process event bus simulating AWS EventBridge.

Design:
  • Standardized OperationalEvent schema with typed EventType enum
  • Thread-safe queue.Queue for async processing in background worker
  • deque(maxlen=200) stores recent events for dashboard polling
  • Subscribers register per-EventType handlers (many-to-one)
  • Module-level singleton `event_bus` used by routers and sentinel
"""
from __future__ import annotations

import logging
import queue
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable

logger = logging.getLogger(__name__)


# ─── Event Types ─────────────────────────────────────────────────────────

class EventType(str, Enum):
    INVENTORY_UPDATED  = "INVENTORY_UPDATED"
    PATIENT_LOGGED     = "PATIENT_LOGGED"
    SUPPLIER_DELAYED   = "SUPPLIER_DELAYED"
    SHIPMENT_UPDATED   = "SHIPMENT_UPDATED"
    PATIENT_SURGE      = "PATIENT_SURGE"
    STAFF_SHORTAGE     = "STAFF_SHORTAGE"
    BED_OVERFLOW       = "BED_OVERFLOW"
    RISK_ESCALATED     = "RISK_ESCALATED"


# ─── Event Schema ─────────────────────────────────────────────────────────

@dataclass
class OperationalEvent:
    """Standardized RESILIA operational event — mirrors AWS EventBridge envelope."""
    event_type: EventType
    phc_id: str
    payload: dict = field(default_factory=dict)

    # Auto-populated
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "resilia.operational"

    def to_dict(self) -> dict:
        return {
            "event_id":   self.event_id,
            "event_type": self.event_type.value,
            "phc_id":     self.phc_id,
            "timestamp":  self.timestamp,
            "source":     self.source,
            "payload":    self.payload,
        }


# ─── Event Bus ────────────────────────────────────────────────────────────

class EventBus:
    """
    Thread-safe, in-memory event bus.

    Usage:
        bus = EventBus()
        bus.subscribe(EventType.SUPPLIER_DELAYED, my_handler)
        bus.start()
        bus.emit(OperationalEvent(EventType.SUPPLIER_DELAYED, "MH-PUN-042", {...}))
        bus.stop()
    """

    def __init__(self, max_recent: int = 200, worker_timeout: float = 1.0):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._queue: queue.Queue[OperationalEvent] = queue.Queue()
        self._recent: deque[dict] = deque(maxlen=max_recent)
        self._worker_timeout = worker_timeout
        self._running = False
        self._thread: threading.Thread | None = None
        self._total_processed = 0
        self._lock = threading.Lock()

    # ── Subscription ──

    def subscribe(self, event_type: EventType, handler: Callable[[OperationalEvent], None]) -> None:
        """Register a handler for a specific event type."""
        with self._lock:
            self._handlers[event_type.value].append(handler)
        logger.debug("EventBus: subscribed handler for %s", event_type.value)

    def unsubscribe_all(self, event_type: EventType) -> None:
        with self._lock:
            self._handlers[event_type.value].clear()

    # ── Emission ──

    def emit(self, event: OperationalEvent) -> str:
        """
        Emit an event — non-blocking.
        Returns the event_id for tracking.
        """
        self._recent.appendleft(event.to_dict())
        self._queue.put(event)
        logger.info(
            "EventBus EMIT %-25s phc=%-15s id=%s",
            event.event_type.value, event.phc_id, event.event_id[:8],
        )
        return event.event_id

    # ── Recent events (for dashboard) ──

    def recent_events(self, limit: int = 50) -> list[dict]:
        """Return the last `limit` events, newest first."""
        with self._lock:
            return list(self._recent)[:limit]

    @property
    def total_processed(self) -> int:
        return self._total_processed

    # ── Lifecycle ──

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._worker,
            name="resilia-event-bus",
            daemon=True,
        )
        self._thread.start()
        logger.info("EventBus started.")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("EventBus stopped. Total processed: %d", self._total_processed)

    # ── Worker ──

    def _worker(self) -> None:
        """Background thread: dequeue events and dispatch to handlers."""
        while self._running:
            try:
                event = self._queue.get(timeout=self._worker_timeout)
            except queue.Empty:
                continue

            handlers = self._handlers.get(event.event_type.value, [])
            for handler in handlers:
                try:
                    handler(event)
                except Exception as exc:
                    logger.error(
                        "EventBus handler error for %s: %s",
                        event.event_type.value, exc,
                    )
            self._total_processed += 1
            self._queue.task_done()


# ─── Module-level singleton ────────────────────────────────────────────────

event_bus = EventBus()
