from pydantic import BaseModel
from typing import Optional


class DailyStaffRecord(BaseModel):
    phc_id: str
    date: str   # YYYY-MM-DD

    doctors_total: int
    doctors_present: int
    nurses_total: int
    nurses_present: int
    asha_total: int
    asha_active: int
    pharmacists_total: int
    pharmacists_present: int

    on_leave: list[str]     # staff IDs on leave
    notes: Optional[str] = None


class StaffAttendanceSummary(BaseModel):
    phc_id: str
    date: str
    doctor_attendance_pct: float
    nurse_attendance_pct: float
    asha_active_pct: float
    is_understaffed: bool
    shortage_types: list[str]  # ["doctors", "nurses"]
