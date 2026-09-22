"""
Audit Service — Cryptographically chained AI Decision Trail.
Guarantees explainability, accountability, and tamper-evident logging
for all autonomous agent recommendations, human approvals, and workflow executions.
"""
from __future__ import annotations
import threading
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
from app.config import settings
from app.models.audit import (
    AIDecisionAuditRecord,
    AuditTrailQueryResponse,
    AuditIntegrityVerificationResponse,
)

logger = logging.getLogger(__name__)


class AIDecisionAuditLedger:
    """
    In-memory append-only ledger with cryptographic hash chaining (SHA-256).
    Simulates Amazon OpenSearch / DynamoDB audit ledger with zero-tampering guarantees.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._chain: List[AIDecisionAuditRecord] = []
        self._seed_initial_audit_trail()

    def _seed_initial_audit_trail(self) -> None:
        """Seed initial immutable audit decisions demonstrating past operational milestones."""
        arn_base = settings.step_functions_arn
        seeds = [
            {
                "audit_id": "AUD-2026-0811",
                "facility_id": "MH-PUN-042",
                "facility_name": "PHC Hadapsar",
                "district": "Pune",
                "what_happened": "ORS-001 stock reached 320 units; stockout forecasted within 4.2 days under 42% patient footfall surge.",
                "why_flagged": "Multi-Factor Compound Risk Score = 0.88 (Low inventory 3.2 days runway + 42% surge + 48h supplier delay).",
                "predictive_model": "RESILIA-ForecastAgent v2.0 (ARIMA-Poisson Demand Forecaster)",
                "ai_recommendation": "Redistribute 1,100 ORS-001 units from PHC Pimpri Hub (18.7 days surplus) via carrier V-17.",
                "optimization_engine": "Google OR-Tools SCIP Mixed-Integer Linear Programming (MILP)",
                "approved_by": "Dr. Priya Sharma (District Health Officer, Pune)",
                "executed_action": "Intervention workflow executed: debited PHC-018, credited PHC-042, carrier V-17 dispatched.",
                "execution_arn": f"{arn_base}:exec-0811" if arn_base else None,
                "minutes_ago": 180,
            },
            {
                "audit_id": "AUD-2026-0812",
                "facility_id": "MH-PUN-019",
                "facility_name": "PHC Kondhwa",
                "district": "Pune",
                "what_happened": "Paracetamol 500mg buffer exhausted; pediatric dengue arrivals spiked +35% in southern urban corridor.",
                "why_flagged": "Cascading Risk Multiplier 2.1x due to concurrent acute respiratory and viral fever admissions.",
                "predictive_model": "RESILIA-Sentinel Compound Evaluator v2.1",
                "ai_recommendation": "Cross-district transfer of 1,200 PCTM-001 units from PHC Shirwal Central (Satara) via Express Corridor.",
                "optimization_engine": "Google OR-Tools SCIP with Distance & Cross-District Penalty Constraints",
                "approved_by": "Dr. Anand Kulkarni (Divisional Health Commissioner, Pune Division)",
                "executed_action": "Intervention workflow executed: cross-district logistics waiver applied, carrier V-09 dispatched.",
                "execution_arn": f"{arn_base}:exec-0812" if arn_base else None,
                "minutes_ago": 120,
            },
            {
                "audit_id": "AUD-2026-0813",
                "facility_id": "DH-PUN-001",
                "facility_name": "Aundh District Civil Hospital",
                "district": "Pune",
                "what_happened": "Inpatient Dengue ICU bed saturation hit 92%; peripheral PHC spillovers impending.",
                "why_flagged": "SimPy Crisis Twin detected cascading overflow from 3 peripheral health posts within 36 hours.",
                "predictive_model": "RESILIA-SimPy Digital Twin Engine v1.0",
                "ai_recommendation": "Emergency dispatch of 2,500 units IV Normal Saline and deployment of 4 reserve medical officers.",
                "optimization_engine": "Multi-Echelon Capacity Redistribution Engine",
                "approved_by": "Dr. Rajiv Deshmukh (Civil Surgeon, Aundh Hospital)",
                "executed_action": "Dispatched emergency replenishment from Central Medical Depot WH-PUN-01; emitted EventBridge alert BED_OVERFLOW_AVERTED.",
                "execution_arn": f"{arn_base}:exec-0813" if arn_base else None,
                "minutes_ago": 45,
            },
        ]

        prev_hash = "0" * 64
        for i, s in enumerate(seeds):
            dt = datetime.now(timezone.utc) - timedelta(minutes=s["minutes_ago"])
            rec = AIDecisionAuditRecord(
                audit_id=s["audit_id"],
                sequence_number=i + 1,
                timestamp=dt.isoformat(),
                facility_id=s["facility_id"],
                facility_name=s["facility_name"],
                district=s["district"],
                what_happened=s["what_happened"],
                why_flagged=s["why_flagged"],
                predictive_model=s["predictive_model"],
                ai_recommendation=s["ai_recommendation"],
                optimization_engine=s["optimization_engine"],
                approved_by=s["approved_by"],
                executed_action=s["executed_action"],
                execution_arn=s["execution_arn"],
                previous_hash=prev_hash,
            )
            rec.record_hash = rec.compute_hash()
            prev_hash = rec.record_hash
            self._chain.append(rec)

    def record_decision(
        self,
        facility_id: str,
        facility_name: str,
        district: str,
        what_happened: str,
        why_flagged: str,
        predictive_model: str,
        ai_recommendation: str,
        optimization_engine: str,
        approved_by: str,
        executed_action: str,
        execution_arn: Optional[str] = None,
    ) -> AIDecisionAuditRecord:
        """Append a new explainable decision record to the tamper-evident hash chain."""
        with self._lock:
            seq = len(self._chain) + 1
            prev_hash = self._chain[-1].record_hash if self._chain else ("0" * 64)
            audit_id = f"AUD-2026-{seq:04d}"

            rec = AIDecisionAuditRecord(
                audit_id=audit_id,
                sequence_number=seq,
                timestamp=datetime.now(timezone.utc).isoformat(),
                facility_id=facility_id,
                facility_name=facility_name,
                district=district,
                what_happened=what_happened,
                why_flagged=why_flagged,
                predictive_model=predictive_model,
                ai_recommendation=ai_recommendation,
                optimization_engine=optimization_engine,
                approved_by=approved_by,
                executed_action=executed_action,
                execution_arn=execution_arn,
                previous_hash=prev_hash,
            )
            rec.record_hash = rec.compute_hash()
            self._chain.append(rec)
            logger.info("Committed AI Decision Audit Record: %s (Block #%d)", audit_id, seq)
            return rec

    def get_records(self, limit: int = 50, facility_id: Optional[str] = None) -> AuditTrailQueryResponse:
        """Retrieve recent audit records with chain verification status."""
        with self._lock:
            filtered = self._chain
            if facility_id:
                filtered = [r for r in filtered if r.facility_id == facility_id]

            # Latest first
            sorted_records = list(reversed(filtered))[:limit]
            is_valid, _ = self._verify_chain_integrity()

            latest_hash = self._chain[-1].record_hash if self._chain else ("0" * 64)

            return AuditTrailQueryResponse(
                total_records=len(self._chain),
                chain_integrity_valid=is_valid,
                latest_block_hash=latest_hash,
                records=sorted_records,
            )

    def verify_integrity(self) -> AuditIntegrityVerificationResponse:
        """Thorough cryptographic verification across the entire audit hash chain."""
        with self._lock:
            is_valid, broken = self._verify_chain_integrity()
            genesis_id = self._chain[0].audit_id if self._chain else "NONE"
            latest_id = self._chain[-1].audit_id if self._chain else "NONE"

            return AuditIntegrityVerificationResponse(
                is_valid=is_valid,
                total_blocks_verified=len(self._chain),
                genesis_block_id=genesis_id,
                latest_block_id=latest_id,
                broken_links=broken,
            )

    def _verify_chain_integrity(self) -> Tuple[bool, List[Dict[str, Any]]]:
        """Internal helper validating SHA-256 block hashes and chaining links."""
        broken = []
        for i, block in enumerate(self._chain):
            # Check previous hash link
            if i > 0:
                expected_prev = self._chain[i - 1].record_hash
                if block.previous_hash != expected_prev:
                    broken.append({
                        "block_seq": block.sequence_number,
                        "audit_id": block.audit_id,
                        "error": "PREVIOUS_HASH_MISMATCH",
                        "actual_prev": block.previous_hash,
                        "expected_prev": expected_prev,
                    })

            # Check block's own hash validity
            computed = block.compute_hash()
            if block.record_hash != computed:
                broken.append({
                    "block_seq": block.sequence_number,
                    "audit_id": block.audit_id,
                    "error": "CONTENT_HASH_TAMPERED",
                    "actual_hash": block.record_hash,
                    "computed_hash": computed,
                })

        return (len(broken) == 0), broken


# Singleton ledger instance
audit_ledger = AIDecisionAuditLedger()
