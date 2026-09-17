from pydantic import BaseModel, Field
from typing import Optional
from app.models.common import AlertType, RiskSeverity


class Alert(BaseModel):
    alert_id: str
    phc_id: str
    phc_name: str
    district: str
    state: str

    alert_type: AlertType
    severity: RiskSeverity
    risk_score: int = Field(ge=0, le=100)

    title: str
    message: str
    factors: list[str]

    medicine: Optional[str] = None
    days_of_stock: Optional[float] = None
    supplier_id: Optional[str] = None

    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None

    created_at: str   # ISO datetime
    expires_at: Optional[str] = None


class AlertAcknowledge(BaseModel):
    acknowledged_by: str
    note: Optional[str] = None
