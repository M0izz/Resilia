from pydantic import BaseModel
from typing import Optional
from app.models.common import InterventionStatus


class InterventionAction(BaseModel):
    action_type: str           # "MEDICINE_TRANSFER" | "EMERGENCY_ORDER" | "STAFF_REALLOCATION" | "BED_RESERVATION"
    description: str
    from_phc: Optional[str] = None
    to_phc: Optional[str] = None
    medicine: Optional[str] = None
    quantity: Optional[float] = None
    staff_role: Optional[str] = None
    urgency: str = "NORMAL"    # "IMMEDIATE" | "URGENT" | "NORMAL"
    estimated_cost_inr: Optional[float] = None


class Intervention(BaseModel):
    intervention_id: str
    title: str
    description: str
    trigger_alert_ids: list[str]
    affected_phcs: list[str]

    status: InterventionStatus
    actions: list[InterventionAction]

    estimated_risk_reduction_pct: float
    created_by: str            # "system" | "sentinel-agent" | user_id
    created_at: str

    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    completed_at: Optional[str] = None

    explanation: Optional[str] = None   # Bedrock-generated (Sprint 2+)


class InterventionApproval(BaseModel):
    approved_by: str
    note: Optional[str] = None


class InterventionRejection(BaseModel):
    rejected_by: str
    reason: str
