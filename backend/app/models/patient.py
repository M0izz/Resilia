from pydantic import BaseModel
from typing import Optional


class DailyPatientRecord(BaseModel):
    phc_id: str
    date: str               # YYYY-MM-DD

    total_opd: int          # Out-patient department
    total_ipd: int          # In-patient department
    new_admissions: int
    discharges: int
    referrals_out: int
    deaths: int

    disease_breakdown: dict[str, int]  # {"dengue": 28, "diarrhea": 42, ...}

    change_7d_pct: Optional[float] = None   # vs 7 days ago
    change_30d_pct: Optional[float] = None  # vs 30 days ago
    trend: Optional[str] = None             # "rising" | "stable" | "falling"


class PatientSummary(BaseModel):
    phc_id: str
    today_opd: int
    today_ipd: int
    avg_7d_opd: float
    trend: str
    change_7d_pct: float
    top_diseases: list[dict]  # [{disease, count}]
