"""
FastAPI Router for AI Decision Audit Trail & Security.
Exposes endpoints to query immutable decision history and verify cryptographic integrity.
"""
from __future__ import annotations
from typing import Optional, Dict, Any
from fastapi import APIRouter, Query, Body, HTTPException

from app.models.audit import (
    AIDecisionAuditRecord,
    AuditTrailQueryResponse,
    AuditIntegrityVerificationResponse,
)
from app.services.audit_service import audit_ledger

router = APIRouter(prefix="/audit", tags=["Security & AI Decision Auditability"])


@router.get("/records", response_model=AuditTrailQueryResponse)
async def get_audit_trail(
    limit: int = Query(50, ge=1, le=200),
    facility_id: Optional[str] = Query(None, description="Filter by facility ID")
):
    """
    Retrieve the immutable AI Decision Trail with cryptographic chain verification.
    Records why decisions were flagged, models used, human approvers, and execution outputs.
    """
    return audit_ledger.get_records(limit=limit, facility_id=facility_id)


@router.get("/verify-integrity", response_model=AuditIntegrityVerificationResponse)
async def verify_audit_chain_integrity():
    """
    Cryptographic verification endpoint: Recalculates SHA-256 hashes across all blocks
    and validates hash pointer linkages to guarantee zero data tampering.
    """
    return audit_ledger.verify_integrity()


@router.post("/records", response_model=AIDecisionAuditRecord)
async def log_decision_record(payload: Dict[str, Any] = Body(...)):
    """Append a new explainable AI decision record to the tamper-evident ledger."""
    required = ["facility_id", "facility_name", "district", "what_happened", "why_flagged",
                "predictive_model", "ai_recommendation", "optimization_engine", "approved_by", "executed_action"]
    for r in required:
        if r not in payload:
            raise HTTPException(status_code=400, detail=f"Missing required audit field: '{r}'")

    rec = audit_ledger.record_decision(
        facility_id=payload["facility_id"],
        facility_name=payload["facility_name"],
        district=payload["district"],
        what_happened=payload["what_happened"],
        why_flagged=payload["why_flagged"],
        predictive_model=payload["predictive_model"],
        ai_recommendation=payload["ai_recommendation"],
        optimization_engine=payload["optimization_engine"],
        approved_by=payload["approved_by"],
        executed_action=payload["executed_action"],
        execution_arn=payload.get("execution_arn"),
    )
    return rec
