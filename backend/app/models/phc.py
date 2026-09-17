from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.common import RiskSeverity, ZoneType


class PHC(BaseModel):
    phc_id: str
    name: str
    state: str
    state_code: str
    district: str
    district_code: str
    zone: ZoneType
    lat: float
    lng: float
    address: str

    # Capacity
    beds_total: int
    beds_occupied: int
    beds_icu: int

    # Staff
    doctors_total: int
    doctors_present: int
    nurses_total: int
    nurses_present: int
    asha_workers: int
    pharmacists: int

    # Relationships
    supplier_ids: list[str]
    district_hospital_id: str

    # Risk
    risk_score: int = Field(ge=0, le=100)
    risk_severity: RiskSeverity
    risk_factors: list[str] = []

    # Operational
    active_alerts: int = 0
    last_updated: str  # ISO8601

    # Computed helpers (not stored, set by API)
    bed_utilization_pct: Optional[float] = None
    doctor_attendance_pct: Optional[float] = None
    nurse_attendance_pct: Optional[float] = None


class PHCSummary(BaseModel):
    """Lightweight version for list/map endpoints."""
    phc_id: str
    name: str
    state: str
    state_code: str
    district: str
    district_code: str
    lat: float
    lng: float
    risk_score: int
    risk_severity: RiskSeverity
    active_alerts: int
    beds_occupied: int
    beds_total: int
    doctors_present: int
    doctors_total: int


class PHCFilter(BaseModel):
    state_code: Optional[str] = None
    district_code: Optional[str] = None
    risk_severity: Optional[RiskSeverity] = None
    min_risk_score: Optional[int] = None


class NetworkSummary(BaseModel):
    """National/state level aggregate stats."""
    total_phcs: int
    critical: int
    high: int
    medium: int
    low: int
    active_alerts: int
    medicine_shortages: int
    avg_bed_utilization: float
    avg_doctor_attendance: float
    total_patients_today: int
    pending_interventions: int
