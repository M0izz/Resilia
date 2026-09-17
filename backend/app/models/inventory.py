from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from app.models.common import MedicineCriticality, RiskSeverity


class InventoryItem(BaseModel):
    phc_id: str
    medicine_code: str
    medicine_name: str
    category: str           # e.g. "Oral Rehydration", "Analgesic"
    criticality: MedicineCriticality

    quantity: float
    unit: str               # packets / tablets / vials / bottles
    reorder_level: float
    max_stock_level: float

    daily_consumption: float   # average daily consumption (last 30 days)
    days_of_stock: float       # = quantity / daily_consumption

    expiry_date: str           # ISO date string
    batch_number: str
    supplier_id: str

    last_restocked: str        # ISO datetime
    last_updated: str          # ISO datetime

    # Risk
    risk_score: int = Field(ge=0, le=100)
    risk_severity: RiskSeverity


class InventoryUpdate(BaseModel):
    quantity: float
    reason: str = "Manual update"
    updated_by: str = "system"


class InventorySnapshot(BaseModel):
    """Aggregate inventory stats for a PHC."""
    phc_id: str
    total_medicines: int
    critical_items: int
    items_below_reorder: int
    items_expiring_30d: int
    worst_days_of_stock: float
    worst_medicine: str


# Standard Indian PHC medicine formulary
MEDICINE_CATALOGUE = [
    {"code": "ORS-001",  "name": "Oral Rehydration Salts",      "category": "Oral Rehydration",  "criticality": "CRITICAL", "unit": "packets",  "reorder": 500,  "max": 5000},
    {"code": "PCTM-001", "name": "Paracetamol 500mg",           "category": "Analgesic",         "criticality": "CRITICAL", "unit": "tablets",  "reorder": 800,  "max": 8000},
    {"code": "AMOX-001", "name": "Amoxicillin 500mg",           "category": "Antibiotic",        "criticality": "CRITICAL", "unit": "capsules", "reorder": 400,  "max": 4000},
    {"code": "CTMX-001", "name": "Cotrimoxazole 480mg",         "category": "Antibiotic",        "criticality": "HIGH",     "unit": "tablets",  "reorder": 300,  "max": 3000},
    {"code": "MTRN-001", "name": "Metronidazole 400mg",         "category": "Antibiotic",        "criticality": "HIGH",     "unit": "tablets",  "reorder": 300,  "max": 3000},
    {"code": "IFA-001",  "name": "Iron Folic Acid",             "category": "Nutritional",       "criticality": "MEDIUM",   "unit": "tablets",  "reorder": 600,  "max": 6000},
    {"code": "VITA-001", "name": "Vitamin A 200000 IU",         "category": "Nutritional",       "criticality": "MEDIUM",   "unit": "capsules", "reorder": 200,  "max": 2000},
    {"code": "ARTM-001", "name": "Artemether-Lumefantrine",     "category": "Antimalarial",      "criticality": "CRITICAL", "unit": "tablets",  "reorder": 200,  "max": 2000},
    {"code": "DOXY-001", "name": "Doxycycline 100mg",           "category": "Antibiotic",        "criticality": "HIGH",     "unit": "capsules", "reorder": 200,  "max": 2000},
    {"code": "CPRO-001", "name": "Ciprofloxacin 500mg",         "category": "Antibiotic",        "criticality": "HIGH",     "unit": "tablets",  "reorder": 200,  "max": 2000},
    {"code": "MISO-001", "name": "Misoprostol 200mcg",          "category": "Obstetric",         "criticality": "CRITICAL", "unit": "tablets",  "reorder": 100,  "max": 1000},
    {"code": "IVNS-001", "name": "IV Normal Saline 500ml",      "category": "IV Fluids",         "criticality": "CRITICAL", "unit": "bottles",  "reorder": 50,   "max": 500},
    {"code": "IVRL-001", "name": "Ringer's Lactate 500ml",      "category": "IV Fluids",         "criticality": "HIGH",     "unit": "bottles",  "reorder": 50,   "max": 500},
    {"code": "BENZ-001", "name": "Benzyl Benzoate 25% Lotion",  "category": "Dermatological",    "criticality": "MEDIUM",   "unit": "bottles",  "reorder": 30,   "max": 300},
    {"code": "CHLOR-001","name": "Chloroquine Phosphate 250mg", "category": "Antimalarial",      "criticality": "HIGH",     "unit": "tablets",  "reorder": 150,  "max": 1500},
]
