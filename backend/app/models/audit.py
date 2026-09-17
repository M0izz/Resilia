"""
Data models for Sprint 5: Security & Explainable AI Decision Trail.
Implements cryptographically chained audit records for healthcare interventions.
"""
from __future__ import annotations
import hashlib
import json
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class AIDecisionAuditRecord(BaseModel):
    """
    Immutable, explainable audit record for an AI decision or intervention.
    Includes the complete decision trail and SHA-256 cryptographic chain hash.
    """
    audit_id: str = Field(..., description="Unique audit record identifier (e.g. AUD-2026-9A8F)")
    sequence_number: int = Field(..., description="Monotonically increasing sequence number in the chain")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    facility_id: str = Field(..., description="Impacted facility ID (e.g. MH-PUN-042)")
    facility_name: str = Field(..., description="Impacted facility name")
    district: str = Field(..., description="Administrative district")

    # ── Explainability Dimensions ──
    what_happened: str = Field(..., description="Clinical/logistical incident summary")
    why_flagged: str = Field(..., description="Multi-factor compound risk triggers & anomalies")
    predictive_model: str = Field(..., description="Model ID/version that produced the forecast")
    ai_recommendation: str = Field(..., description="Agent operational recommendation")
    optimization_engine: str = Field(..., description="Solver and constraints utilized")
    approved_by: str = Field(..., description="Authorized human health official who approved/reviewed")
    executed_action: str = Field(..., description="Action dispatched via AWS Step Functions / EventBridge")
    execution_arn: Optional[str] = Field(None, description="AWS Step Functions execution ARN")

    # ── Cryptographic Integrity ──
    previous_hash: str = Field("0" * 64, description="SHA-256 hash of the preceding audit record in chain")
    record_hash: str = Field("", description="SHA-256 hash of this record")
    is_verified: bool = True

    def compute_hash(self) -> str:
        """Compute SHA-256 hash over canonical representation of record contents."""
        content = {
            "audit_id": self.audit_id,
            "sequence_number": self.sequence_number,
            "facility_id": self.facility_id,
            "what_happened": self.what_happened,
            "why_flagged": self.why_flagged,
            "predictive_model": self.predictive_model,
            "ai_recommendation": self.ai_recommendation,
            "optimization_engine": self.optimization_engine,
            "approved_by": self.approved_by,
            "executed_action": self.executed_action,
            "previous_hash": self.previous_hash,
        }
        canonical_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


class AuditTrailQueryResponse(BaseModel):
    """Paginated or filtered response of AI decision records."""
    total_records: int
    chain_integrity_valid: bool
    latest_block_hash: str
    records: List[AIDecisionAuditRecord]


class AuditIntegrityVerificationResponse(BaseModel):
    """Detailed cryptographic chain integrity verification report."""
    is_valid: bool
    total_blocks_verified: int
    genesis_block_id: str
    latest_block_id: str
    broken_links: List[Dict[str, Any]] = Field(default_factory=list)
    verified_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
