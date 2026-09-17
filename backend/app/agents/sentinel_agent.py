"""
RESILIA Sentinel Agent — Sprint 2
====================================
Autonomous monitoring agent for proactive PHC network surveillance.

Architecture:
  • Subscribes to all EventBus events → evaluates risk on every relevant signal
  • Periodic background scan loop (every 60s) for network-wide anomaly detection
  • Runs multi-factor cascading risk scoring + forecast engine per evaluation
  • Autonomously escalates alerts to DynamoDB when risk crosses WATCH threshold
  • Maintains in-memory decision log (last 500 decisions) for dashboard display

Thread safety:
  • decisions deque is protected by threading.Lock
  • scan_network uses a reentrant lock to prevent concurrent scans
  • All DynamoDB writes are atomic per-item operations
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.events.event_bus import EventType, OperationalEvent, event_bus
from app.services.risk_engine import (
    MedicineRiskInput,
    PHCRiskInput,
    score_phc_multifactor,
)
from app.models.common import AlertType, RiskSeverity

logger = logging.getLogger(__name__)

# ─── Scan interval ────────────────────────────────────────────────────────

SCAN_INTERVAL_SECONDS = 60
MAX_DECISIONS = 500
ALERT_ESCALATION_THRESHOLD = RiskSeverity.WATCH


# ─── Decision log entry ───────────────────────────────────────────────────

@dataclass
class AgentDecision:
    """Single autonomous decision logged by the Sentinel Agent."""
    phc_id: str
    phc_name: str
    trigger: str                         # event type or "PERIODIC_SCAN"
    risk_score: int
    risk_severity: str
    base_score: int
    cascade_multiplier: float
    active_compounding_factors: list[str]
    reasoning: str                       # Full agent_explanation
    action_taken: str                    # "ALERT_ESCALATED" | "MONITORING" | "CLEAR"
    alert_id: Optional[str] = None

    # Auto-populated
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "decision_id":               self.decision_id,
            "timestamp":                 self.timestamp,
            "phc_id":                    self.phc_id,
            "phc_name":                  self.phc_name,
            "trigger":                   self.trigger,
            "risk_score":                self.risk_score,
            "risk_severity":             self.risk_severity,
            "base_score":                self.base_score,
            "cascade_multiplier":        self.cascade_multiplier,
            "active_compounding_factors": self.active_compounding_factors,
            "reasoning":                 self.reasoning,
            "action_taken":              self.action_taken,
            "alert_id":                  self.alert_id,
        }


# ─── Sentinel Agent ───────────────────────────────────────────────────────

class SentinelAgent:
    """
    RESILIA Autonomous Sentinel Agent.

    Responsibilities:
      1. React to operational events → immediate PHC risk evaluation
      2. Periodic network-wide scan → catch emerging anomalies
      3. Auto-escalate alerts for WATCH / HIGH / CRITICAL risk
      4. Log every decision for audit trail and dashboard display
    """

    def __init__(self):
        self._decisions: deque[AgentDecision] = deque(maxlen=MAX_DECISIONS)
        self._lock = threading.Lock()
        self._scan_lock = threading.RLock()
        self._running = False
        self._scan_thread: Optional[threading.Thread] = None
        self._started_at: Optional[str] = None

        # Stats
        self._scans_completed = 0
        self._anomalies_detected = 0
        self._alerts_escalated = 0

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._started_at = datetime.utcnow().isoformat()

        # Subscribe to event bus
        event_bus.subscribe(EventType.INVENTORY_UPDATED,  self._handle_inventory_updated)
        event_bus.subscribe(EventType.PATIENT_LOGGED,     self._handle_patient_logged)
        event_bus.subscribe(EventType.SUPPLIER_DELAYED,   self._handle_supplier_delayed)
        event_bus.subscribe(EventType.SHIPMENT_UPDATED,   self._handle_shipment_updated)
        event_bus.subscribe(EventType.PATIENT_SURGE,      self._handle_patient_surge)
        event_bus.subscribe(EventType.STAFF_SHORTAGE,     self._handle_staff_shortage)
        event_bus.subscribe(EventType.BED_OVERFLOW,       self._handle_bed_overflow)

        # Start periodic scan loop
        self._scan_thread = threading.Thread(
            target=self._background_loop,
            name="resilia-sentinel",
            daemon=True,
        )
        self._scan_thread.start()
        logger.info("Sentinel Agent started. Scan interval: %ds", SCAN_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._running = False
        if self._scan_thread:
            self._scan_thread.join(timeout=5.0)
        logger.info(
            "Sentinel Agent stopped. Scans: %d | Anomalies: %d | Alerts: %d",
            self._scans_completed, self._anomalies_detected, self._alerts_escalated,
        )

    # ── Status ────────────────────────────────────────────────────────────

    def status(self) -> dict:
        uptime_s = 0
        if self._started_at:
            delta = datetime.utcnow() - datetime.fromisoformat(self._started_at)
            uptime_s = int(delta.total_seconds())

        return {
            "running":            self._running,
            "started_at":         self._started_at,
            "uptime_seconds":     uptime_s,
            "scan_interval_s":    SCAN_INTERVAL_SECONDS,
            "scans_completed":    self._scans_completed,
            "anomalies_detected": self._anomalies_detected,
            "alerts_escalated":   self._alerts_escalated,
            "decisions_logged":   len(self._decisions),
            "event_bus_processed": event_bus.total_processed,
        }

    def recent_decisions(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return [d.to_dict() for d in list(self._decisions)[:limit]]

    # ── Event handlers ────────────────────────────────────────────────────

    def _handle_inventory_updated(self, event: OperationalEvent) -> None:
        logger.info("Sentinel: INVENTORY_UPDATED event for %s", event.phc_id)
        self._evaluate_phc(event.phc_id, trigger="INVENTORY_UPDATED", extra_payload=event.payload)

    def _handle_patient_logged(self, event: OperationalEvent) -> None:
        self._evaluate_phc(event.phc_id, trigger="PATIENT_LOGGED", extra_payload=event.payload)

    def _handle_supplier_delayed(self, event: OperationalEvent) -> None:
        logger.warning("Sentinel: SUPPLIER_DELAYED for %s — delay_days=%s",
                       event.phc_id, event.payload.get("delay_days", "?"))
        self._evaluate_phc(event.phc_id, trigger="SUPPLIER_DELAYED", extra_payload=event.payload)

    def _handle_shipment_updated(self, event: OperationalEvent) -> None:
        self._evaluate_phc(event.phc_id, trigger="SHIPMENT_UPDATED", extra_payload=event.payload)

    def _handle_patient_surge(self, event: OperationalEvent) -> None:
        logger.warning("Sentinel: PATIENT_SURGE at %s", event.phc_id)
        self._evaluate_phc(event.phc_id, trigger="PATIENT_SURGE", extra_payload=event.payload)

    def _handle_staff_shortage(self, event: OperationalEvent) -> None:
        self._evaluate_phc(event.phc_id, trigger="STAFF_SHORTAGE", extra_payload=event.payload)

    def _handle_bed_overflow(self, event: OperationalEvent) -> None:
        self._evaluate_phc(event.phc_id, trigger="BED_OVERFLOW", extra_payload=event.payload)

    # ── Core evaluation ───────────────────────────────────────────────────

    def _evaluate_phc(
        self,
        phc_id: str,
        trigger: str,
        extra_payload: Optional[dict] = None,
    ) -> Optional[AgentDecision]:
        """
        Load PHC data from DynamoDB, run multi-factor risk scoring,
        optionally escalate an alert, and log the decision.
        """
        try:
            from app.db.dynamodb import Tables, scan_all, query_gsi
            from boto3.dynamodb.conditions import Key, Attr

            # Load PHC record
            resp = Tables.phcs().get_item(Key={"phc_id": phc_id})
            phc = resp.get("Item")
            if not phc:
                logger.debug("Sentinel: PHC %s not found in DB — skipping", phc_id)
                return None

            phc_name = phc.get("name", phc_id)

            # Load inventory
            inventory = query_gsi(
                "resilia-inventory", "PHC-Inventory-Index",
                Key("phc_id").eq(phc_id),
            ) if False else []  # GSI may not exist — use scan

            try:
                inventory = Tables.inventory().query(
                    KeyConditionExpression=Key("phc_id").eq(phc_id)
                ).get("Items", [])
            except Exception:
                inventory = []

            # Apply payload overrides (event may carry updated supplier delay)
            supplier_delay_days = int(phc.get("supplier_delay_days", 0))
            if extra_payload:
                supplier_delay_days = max(
                    supplier_delay_days,
                    int(extra_payload.get("delay_days", 0)),
                )
                patient_surge_pct = float(extra_payload.get("patient_7d_change_pct",
                                         phc.get("patient_7d_change_pct", 0)))
            else:
                patient_surge_pct = float(phc.get("patient_7d_change_pct", 0))

            # Build risk input
            med_inputs = []
            for item in inventory:
                daily = float(item.get("daily_consumption", 0))
                if daily <= 0:
                    continue
                med_inputs.append(MedicineRiskInput(
                    medicine_code=item.get("medicine_code", ""),
                    medicine_name=item.get("medicine_name", ""),
                    quantity=float(item.get("quantity", 0)),
                    daily_consumption=daily,
                    criticality=item.get("criticality", "LOW"),
                    supplier_delayed=supplier_delay_days > 0,
                    delay_days=supplier_delay_days,
                    expiry_days=int(item.get("expiry_days", 365)),
                ))

            phc_input = PHCRiskInput(
                phc_id=phc_id,
                beds_total=int(phc.get("beds_total", 0)),
                beds_occupied=int(phc.get("beds_occupied", 0)),
                doctors_total=int(phc.get("doctors_total", 1)),
                doctors_present=int(phc.get("doctors_present", 1)),
                patient_7d_change_pct=patient_surge_pct,
                medicines=med_inputs,
                supplier_delay_days=supplier_delay_days,
            )

            # Multi-factor risk scoring
            result = score_phc_multifactor(phc_input)

            # Determine action
            severity_val = result.risk_severity.value
            alert_id = None

            if result.risk_severity in (RiskSeverity.WATCH, RiskSeverity.HIGH, RiskSeverity.CRITICAL):
                self._anomalies_detected += 1
                action = "ALERT_ESCALATED"
                alert_id = self._escalate_alert(phc, result, trigger)
            elif result.cascade_multiplier > 1.0:
                action = "MONITORING"
            else:
                action = "CLEAR"

            decision = AgentDecision(
                phc_id=phc_id,
                phc_name=phc_name,
                trigger=trigger,
                risk_score=result.risk_score,
                risk_severity=severity_val,
                base_score=result.base_score,
                cascade_multiplier=result.cascade_multiplier,
                active_compounding_factors=result.active_compounding_factors,
                reasoning=result.agent_explanation,
                action_taken=action,
                alert_id=alert_id,
            )

            with self._lock:
                self._decisions.appendleft(decision)

            logger.info(
                "Sentinel DECISION: phc=%s trigger=%-20s score=%d (%s) cascade=×%.2f action=%s",
                phc_id, trigger, result.risk_score, severity_val,
                result.cascade_multiplier, action,
            )
            return decision

        except Exception as exc:
            logger.error("Sentinel: Error evaluating PHC %s: %s", phc_id, exc, exc_info=True)
            return None

    def _escalate_alert(self, phc: dict, result, trigger: str) -> Optional[str]:
        """Write an autonomous alert to DynamoDB."""
        try:
            from app.db.dynamodb import Tables

            now = datetime.utcnow().isoformat()
            alert_id = f"SENTINEL-{uuid.uuid4()}"
            severity = result.risk_severity.value

            # Map severity to alert type
            if result.cascade_multiplier > 1.0:
                alert_type = AlertType.COMPOUND.value
            elif result.sub_scores.get("medicine", 0) >= 30:
                alert_type = AlertType.STOCKOUT_RISK.value
            elif result.sub_scores.get("bed", 0) >= 12:
                alert_type = AlertType.BED_OVERFLOW.value
            else:
                alert_type = AlertType.COMPOUND.value

            title = (
                f"[SENTINEL] Cascading risk detected — {result.primary_category.value.replace('_', ' ').title()}"
                if result.cascade_multiplier > 1.0
                else f"[SENTINEL] {severity} risk at {phc.get('name', phc['phc_id'])}"
            )

            Tables.alerts().put_item(Item={
                "alert_id":      alert_id,
                "created_at":    now,
                "phc_id":        phc["phc_id"],
                "phc_name":      phc.get("name", phc["phc_id"]),
                "district":      phc.get("district", ""),
                "state":         phc.get("state", ""),
                "alert_type":    alert_type,
                "severity":      severity,
                "risk_score":    result.risk_score,
                "title":         title,
                "message":       result.agent_explanation,
                "factors":       result.factors,
                "acknowledged":  False,
                "cascade_multiplier": str(result.cascade_multiplier),
                "trigger_event": trigger,
            })
            self._alerts_escalated += 1
            logger.info("Sentinel escalated alert %s for %s (%s)", alert_id, phc["phc_id"], severity)

            # Sprint 3: Trigger Resource Agent to formulate an optimized intervention plan
            try:
                from app.agents.resource_agent import resource_agent
                from app.models.optimization import OptimizationRequest
                med_code = phc.get("critical_medicine_code", "ORS-001")
                resource_agent.plan_intervention(
                    OptimizationRequest(
                        target_phc_id=phc["phc_id"],
                        medicine_code=med_code,
                    )
                )
                logger.info("Sentinel dispatched problem signal to ResourceAgent for PHC %s (%s)", phc["phc_id"], med_code)
            except Exception as e:
                logger.debug("ResourceAgent dispatch from Sentinel deferred: %s", e)

            return alert_id
        except Exception as exc:
            logger.error("Sentinel: Failed to escalate alert: %s", exc)
            return None

    # ── Periodic network scan ──────────────────────────────────────────────

    def scan_network(self) -> dict:
        """
        Full network-wide Sentinel inspection.
        Evaluates every PHC in the database.
        Returns summary statistics.
        """
        with self._scan_lock:
            try:
                from app.db.dynamodb import scan_all
                phcs = scan_all("resilia-phcs")
            except Exception as exc:
                logger.error("Sentinel scan: failed to load PHCs: %s", exc)
                return {"error": str(exc)}

            logger.info("Sentinel network scan starting — %d PHCs", len(phcs))
            scan_start = time.time()

            evaluated = 0
            anomalies = 0
            for phc in phcs:
                decision = self._evaluate_phc(phc["phc_id"], trigger="PERIODIC_SCAN")
                if decision:
                    evaluated += 1
                    if decision.action_taken == "ALERT_ESCALATED":
                        anomalies += 1

            elapsed = round(time.time() - scan_start, 2)
            self._scans_completed += 1

            summary = {
                "scan_id":      str(uuid.uuid4()),
                "timestamp":    datetime.utcnow().isoformat(),
                "phcs_evaluated": evaluated,
                "anomalies_found": anomalies,
                "duration_s":   elapsed,
                "scans_total":  self._scans_completed,
            }
            logger.info(
                "✅ Sentinel scan complete: %d PHCs | %d anomalies | %.2fs",
                evaluated, anomalies, elapsed,
            )
            return summary

    def _background_loop(self) -> None:
        """Daemon loop: run scan_network every SCAN_INTERVAL_SECONDS."""
        # Short initial delay to let API finish startup
        time.sleep(10)
        while self._running:
            try:
                self.scan_network()
            except Exception as exc:
                logger.error("Sentinel background loop error: %s", exc)
            # Sleep in small chunks to detect stop() quickly
            for _ in range(SCAN_INTERVAL_SECONDS):
                if not self._running:
                    break
                time.sleep(1)


# ─── Module-level singleton ────────────────────────────────────────────────

sentinel_agent = SentinelAgent()
