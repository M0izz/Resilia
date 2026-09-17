"""
RESILIA — Database Seed Script
================================
Generates and inserts 75 realistic PHCs across 5 Indian states.

Distribution:
  7 CRITICAL  (demo-story PHCs with specific problems)
  15 HIGH
  25 MEDIUM
  28 LOW/HEALTHY
  ─────────────
  75 TOTAL

Run:  python data/seed_db.py
"""
import boto3
import json
import random
import uuid
import sys
import os
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import time
from datetime import datetime, timedelta, date
from decimal import Decimal

# ─── DynamoDB connection ───────────────────────────────────────────────────

ENDPOINT  = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8001")
REGION    = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
KEY_ID    = os.environ.get("AWS_ACCESS_KEY_ID", "local")
KEY_SEC   = os.environ.get("AWS_SECRET_ACCESS_KEY", "local")

dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id=KEY_ID,
    aws_secret_access_key=KEY_SEC,
)
client = boto3.client(
    "dynamodb",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id=KEY_ID,
    aws_secret_access_key=KEY_SEC,
)

# ─── Table names ───────────────────────────────────────────────────────────

TABLES = {
    "phcs":          "resilia-phcs",
    "inventory":     "resilia-inventory",
    "patients":      "resilia-patients",
    "staff":         "resilia-staff",
    "alerts":        "resilia-alerts",
    "suppliers":     "resilia-suppliers",
    "shipments":     "resilia-shipments",
    "interventions": "resilia-interventions",
}

# ─── Medicine catalogue ────────────────────────────────────────────────────

MEDICINES = [
    {"code": "ORS-001",   "name": "Oral Rehydration Salts",      "category": "Oral Rehydration",  "criticality": "CRITICAL", "unit": "packets",  "reorder": 500,  "max": 5000, "daily_base": 70},
    {"code": "PCTM-001",  "name": "Paracetamol 500mg",           "category": "Analgesic",         "criticality": "CRITICAL", "unit": "tablets",  "reorder": 800,  "max": 8000, "daily_base": 120},
    {"code": "AMOX-001",  "name": "Amoxicillin 500mg",           "category": "Antibiotic",        "criticality": "CRITICAL", "unit": "capsules", "reorder": 400,  "max": 4000, "daily_base": 50},
    {"code": "CTMX-001",  "name": "Cotrimoxazole 480mg",         "category": "Antibiotic",        "criticality": "HIGH",     "unit": "tablets",  "reorder": 300,  "max": 3000, "daily_base": 40},
    {"code": "MTRN-001",  "name": "Metronidazole 400mg",         "category": "Antibiotic",        "criticality": "HIGH",     "unit": "tablets",  "reorder": 300,  "max": 3000, "daily_base": 35},
    {"code": "IFA-001",   "name": "Iron Folic Acid",             "category": "Nutritional",       "criticality": "MEDIUM",   "unit": "tablets",  "reorder": 600,  "max": 6000, "daily_base": 80},
    {"code": "VITA-001",  "name": "Vitamin A 200000 IU",         "category": "Nutritional",       "criticality": "MEDIUM",   "unit": "capsules", "reorder": 200,  "max": 2000, "daily_base": 20},
    {"code": "ARTM-001",  "name": "Artemether-Lumefantrine",     "category": "Antimalarial",      "criticality": "CRITICAL", "unit": "tablets",  "reorder": 200,  "max": 2000, "daily_base": 25},
    {"code": "DOXY-001",  "name": "Doxycycline 100mg",           "category": "Antibiotic",        "criticality": "HIGH",     "unit": "capsules", "reorder": 200,  "max": 2000, "daily_base": 20},
    {"code": "CPRO-001",  "name": "Ciprofloxacin 500mg",         "category": "Antibiotic",        "criticality": "HIGH",     "unit": "tablets",  "reorder": 200,  "max": 2000, "daily_base": 20},
    {"code": "MISO-001",  "name": "Misoprostol 200mcg",          "category": "Obstetric",         "criticality": "CRITICAL", "unit": "tablets",  "reorder": 100,  "max": 1000, "daily_base": 8},
    {"code": "IVNS-001",  "name": "IV Normal Saline 500ml",      "category": "IV Fluids",         "criticality": "CRITICAL", "unit": "bottles",  "reorder": 50,   "max": 500,  "daily_base": 12},
    {"code": "IVRL-001",  "name": "Ringer's Lactate 500ml",      "category": "IV Fluids",         "criticality": "HIGH",     "unit": "bottles",  "reorder": 50,   "max": 500,  "daily_base": 8},
    {"code": "BENZ-001",  "name": "Benzyl Benzoate 25% Lotion",  "category": "Dermatological",    "criticality": "MEDIUM",   "unit": "bottles",  "reorder": 30,   "max": 300,  "daily_base": 5},
    {"code": "CHLOR-001", "name": "Chloroquine Phosphate 250mg", "category": "Antimalarial",      "criticality": "HIGH",     "unit": "tablets",  "reorder": 150,  "max": 1500, "daily_base": 18},
]

# ─── Geographic data ───────────────────────────────────────────────────────

NETWORK = {
    "MH": {
        "state": "Maharashtra",
        "districts": {
            "PUN": {
                "name": "Pune",
                "center": (18.5204, 73.8567),
                "hospital": "DH-PUN-001",
                "localities": [
                    "Hadapsar", "Kondhwa", "Yerawada", "Kothrud", "Wakad",
                    "Pimpri", "Chinchwad", "Dhanori", "Warje", "Baner",
                    "Bavdhan", "Lohegaon", "Sinhagad", "Katraj", "Ambegaon",
                ],
            },
            "MUM": {
                "name": "Mumbai City",
                "center": (19.0760, 72.8777),
                "hospital": "DH-MUM-001",
                "localities": [
                    "Dharavi", "Andheri East", "Kurla West", "Ghatkopar",
                    "Malad East", "Borivali", "Vikhroli", "Goregaon",
                    "Vile Parle", "Kandivali",
                ],
            },
            "NGP": {
                "name": "Nagpur",
                "center": (21.1458, 79.0882),
                "hospital": "DH-NGP-001",
                "localities": [
                    "Kamptee", "Hingna", "Butibori", "Wadi", "Pardi",
                    "Kalamna", "Nandanvan",
                ],
            },
        },
    },
    "DL": {
        "state": "Delhi",
        "districts": {
            "CD": {
                "name": "Central Delhi",
                "center": (28.6448, 77.2167),
                "hospital": "DH-DL-001",
                "localities": [
                    "Karol Bagh", "Patel Nagar", "Rajinder Nagar",
                    "Chanakyapuri", "Sadar Bazar",
                ],
            },
            "SD": {
                "name": "South Delhi",
                "center": (28.5355, 77.2090),
                "hospital": "DH-SD-001",
                "localities": [
                    "Saket", "Mehrauli", "Hauz Khas", "Kalkaji",
                    "Okhla", "Malviya Nagar",
                ],
            },
            "ND": {
                "name": "North Delhi",
                "center": (28.7041, 77.1025),
                "hospital": "DH-ND-001",
                "localities": [
                    "Jahangirpuri", "Mangolpuri", "Burari",
                    "Shakurpur", "Rohini",
                ],
            },
        },
    },
    "KA": {
        "state": "Karnataka",
        "districts": {
            "BLR": {
                "name": "Bengaluru Urban",
                "center": (12.9716, 77.5946),
                "hospital": "DH-BLR-001",
                "localities": [
                    "Rajajinagar", "Whitefield", "Hebbal", "Jayanagar",
                    "Koramangala", "Yeshwantpur", "Malleshwaram",
                ],
            },
            "MYS": {
                "name": "Mysuru",
                "center": (12.2958, 76.6394),
                "hospital": "DH-MYS-001",
                "localities": [
                    "Kuvempunagar", "Jayalakshmipuram", "Vijayanagar",
                    "Nazarbad", "Lakshmipuram",
                ],
            },
        },
    },
    "TN": {
        "state": "Tamil Nadu",
        "districts": {
            "CHN": {
                "name": "Chennai",
                "center": (13.0827, 80.2707),
                "hospital": "DH-CHN-001",
                "localities": [
                    "Tondiarpet", "Royapuram", "Ayanavaram",
                    "Perambur", "Vyasarpadi", "Tiruvottiyur",
                ],
            },
            "CBE": {
                "name": "Coimbatore",
                "center": (11.0168, 76.9558),
                "hospital": "DH-CBE-001",
                "localities": [
                    "Ukkadam", "Singanallur", "Ganapathy",
                    "Saibaba Colony", "Peelamedu",
                ],
            },
        },
    },
    "WB": {
        "state": "West Bengal",
        "districts": {
            "KOL": {
                "name": "Kolkata",
                "center": (22.5726, 88.3639),
                "hospital": "DH-KOL-001",
                "localities": [
                    "Tangra", "Park Circus", "Tiljala",
                    "Beniapukur", "Kidderpore", "Watgunge",
                ],
            },
            "HWH": {
                "name": "Howrah",
                "center": (22.5958, 88.2636),
                "hospital": "DH-HWH-001",
                "localities": [
                    "Shibpur", "Bantra", "Liluah",
                    "Bally", "Domjur",
                ],
            },
        },
    },
}

# ─── Supplier data ─────────────────────────────────────────────────────────

SUPPLIERS = [
    {"supplier_id": "SUP-MH-001", "id": "SUP-MH-001", "name": "Maharashtra Medical Supplies Corp", "state": "MH", "reliability": 8.2, "lead_time": 4, "delayed": False,  "delay_days": 0,  "delay_reason": ""},
    {"supplier_id": "SUP-MH-002", "id": "SUP-MH-002", "name": "Pune District Pharma Hub",          "state": "MH", "reliability": 6.5, "lead_time": 5, "delayed": True,   "delay_days": 4,  "delay_reason": "Road blockage NH-48"},
    {"supplier_id": "SUP-MH-003", "id": "SUP-MH-003", "name": "Nagpur Medical Depot",              "state": "MH", "reliability": 7.8, "lead_time": 3, "delayed": False,  "delay_days": 0,  "delay_reason": ""},
    {"supplier_id": "SUP-DL-001", "id": "SUP-DL-001", "name": "Delhi State Medical Stores",        "state": "DL", "reliability": 7.5, "lead_time": 2, "delayed": False,  "delay_days": 0,  "delay_reason": ""},
    {"supplier_id": "SUP-DL-002", "id": "SUP-DL-002", "name": "North Delhi Pharma Warehouse",      "state": "DL", "reliability": 5.2, "lead_time": 3, "delayed": True,   "delay_days": 6,  "delay_reason": "Strike at distributor"},
    {"supplier_id": "SUP-KA-001", "id": "SUP-KA-001", "name": "Karnataka State Medical Corp",      "state": "KA", "reliability": 8.8, "lead_time": 3, "delayed": False,  "delay_days": 0,  "delay_reason": ""},
    {"supplier_id": "SUP-KA-002", "id": "SUP-KA-002", "name": "Bengaluru City Pharma Centre",      "state": "KA", "reliability": 5.9, "lead_time": 4, "delayed": True,   "delay_days": 5,  "delay_reason": "Stock shortage at warehouse"},
    {"supplier_id": "SUP-TN-001", "id": "SUP-TN-001", "name": "Tamil Nadu Medical Supplies Ltd",   "state": "TN", "reliability": 8.1, "lead_time": 3, "delayed": False,  "delay_days": 0,  "delay_reason": ""},
    {"supplier_id": "SUP-TN-002", "id": "SUP-TN-002", "name": "Chennai District Drug Warehouse",   "state": "TN", "reliability": 7.3, "lead_time": 4, "delayed": False,  "delay_days": 0,  "delay_reason": ""},
    {"supplier_id": "SUP-WB-001", "id": "SUP-WB-001", "name": "West Bengal Medical Stores",        "state": "WB", "reliability": 7.0, "lead_time": 4, "delayed": True,   "delay_days": 3,  "delay_reason": "Flood damage to access road"},
    {"supplier_id": "SUP-WB-002", "id": "SUP-WB-002", "name": "Kolkata State Pharma Hub",          "state": "WB", "reliability": 8.5, "lead_time": 3, "delayed": False,  "delay_days": 0,  "delay_reason": ""},
]

# ─── Specific "problem" PHC configurations for the demo ───────────────────
# These override random generation to create compelling demo data.

DEMO_PHCS = {
    "MH-PUN-042": {
        "name": "PHC Hadapsar",
        "locality": "Hadapsar",
        "beds_total": 30, "beds_occupied": 27,
        "doctors_total": 3, "doctors_present": 2,
        "nurses_total": 6, "nurses_present": 5,
        "asha_workers": 12,
        "zone": "Urban",
        "supplier_id": "SUP-MH-002",        # delayed 4 days
        "patient_7d_change_pct": 23.4,
        "inventory_overrides": {
            "ORS-001":  {"quantity": 450,  "daily_consumption": 70.3},  # 6.4 days → CRITICAL
            "PCTM-001": {"quantity": 920,  "daily_consumption": 70.0},  # 13.1 days → MEDIUM
            "AMOX-001": {"quantity": 1200, "daily_consumption": 45.0},
        },
    },
    "MH-PUN-019": {
        "name": "PHC Kondhwa",
        "locality": "Kondhwa",
        "beds_total": 25, "beds_occupied": 22,
        "doctors_total": 2, "doctors_present": 2,
        "nurses_total": 5, "nurses_present": 4,
        "asha_workers": 10,
        "zone": "Semi-urban",
        "supplier_id": "SUP-MH-002",        # same delayed supplier
        "patient_7d_change_pct": 35.1,      # surge
        "inventory_overrides": {
            "PCTM-001": {"quantity": 380,  "daily_consumption": 90.5},  # 4.2 days → CRITICAL
            "ORS-001":  {"quantity": 1800, "daily_consumption": 65.0},
        },
    },
    "DL-CD-007": {
        "name": "PHC Karol Bagh",
        "locality": "Karol Bagh",
        "beds_total": 40, "beds_occupied": 39,  # 97.5% → CRITICAL
        "doctors_total": 3, "doctors_present": 1,  # 33% → CRITICAL
        "nurses_total": 7, "nurses_present": 4,
        "asha_workers": 15,
        "zone": "Urban",
        "supplier_id": "SUP-DL-001",
        "patient_7d_change_pct": 28.7,
        "inventory_overrides": {
            "IVNS-001": {"quantity": 28,  "daily_consumption": 9.0},    # 3.1 days → CRITICAL
            "ORS-001":  {"quantity": 2400, "daily_consumption": 80.0},
        },
    },
    "KA-BLR-015": {
        "name": "PHC Whitefield",
        "locality": "Whitefield",
        "beds_total": 35, "beds_occupied": 30,
        "doctors_total": 3, "doctors_present": 2,
        "nurses_total": 6, "nurses_present": 5,
        "asha_workers": 12,
        "zone": "Urban",
        "supplier_id": "SUP-KA-002",       # delayed 5 days
        "patient_7d_change_pct": 19.2,
        "inventory_overrides": {
            "IVNS-001": {"quantity": 35,   "daily_consumption": 11.3},  # 3.1 days → CRITICAL
            "ARTM-001": {"quantity": 120,  "daily_consumption": 22.0},  # 5.5 days → HIGH
        },
    },
    "TN-CHN-023": {
        "name": "PHC Tondiarpet",
        "locality": "Tondiarpet",
        "beds_total": 28, "beds_occupied": 25,
        "doctors_total": 2, "doctors_present": 2,
        "nurses_total": 5, "nurses_present": 4,
        "asha_workers": 10,
        "zone": "Urban",
        "supplier_id": "SUP-TN-001",
        "patient_7d_change_pct": 31.5,
        "inventory_overrides": {
            "AMOX-001": {"quantity": 275,  "daily_consumption": 50.0},  # 5.5 days → CRITICAL
            "DOXY-001": {"quantity": 180,  "daily_consumption": 30.0},  # 6.0 days → HIGH
        },
    },
    "WB-KOL-031": {
        "name": "PHC Tangra",
        "locality": "Tangra",
        "beds_total": 30, "beds_occupied": 28,
        "doctors_total": 2, "doctors_present": 2,
        "nurses_total": 5, "nurses_present": 5,
        "asha_workers": 12,
        "zone": "Urban",
        "supplier_id": "SUP-WB-001",       # delayed (flood) 3 days
        "patient_7d_change_pct": 42.0,     # malaria season surge
        "inventory_overrides": {
            "ARTM-001": {"quantity": 95,   "daily_consumption": 28.0},  # 3.4 days → CRITICAL
            "CHLOR-001": {"quantity": 180, "daily_consumption": 25.0},  # 7.2 days → HIGH
        },
    },
    "MH-NGP-008": {
        "name": "PHC Kamptee",
        "locality": "Kamptee",
        "beds_total": 20, "beds_occupied": 19,  # 95% → CRITICAL
        "doctors_total": 2, "doctors_present": 1,  # 50% → CRITICAL
        "nurses_total": 4, "nurses_present": 3,
        "asha_workers": 8,
        "zone": "Rural",
        "supplier_id": "SUP-MH-001",
        "patient_7d_change_pct": 17.3,
        "inventory_overrides": {
            "ORS-001":  {"quantity": 290,  "daily_consumption": 55.0},  # 5.3 days → CRITICAL
            "MISO-001": {"quantity": 45,   "daily_consumption": 9.0},   # 5.0 days → CRITICAL
        },
    },
}


# ─── Helpers ───────────────────────────────────────────────────────────────

rng = random.Random(42)   # deterministic seed for reproducibility

def jitter(lat: float, lng: float, radius: float = 0.05):
    """Randomly offset coordinates by up to radius degrees."""
    return (
        round(lat + rng.uniform(-radius, radius), 4),
        round(lng + rng.uniform(-radius, radius), 4),
    )


def random_stock(medicine: dict, profile: str = "normal") -> dict:
    """
    Generate inventory quantity based on PHC health profile.
    profile: "normal" | "low" | "critical" | "surplus"
    """
    reorder = medicine["reorder"]
    max_s   = medicine["max"]
    daily   = medicine["daily_base"]

    if profile == "critical":
        qty = rng.uniform(reorder * 0.1, reorder * 0.5)
        cons = rng.uniform(daily * 0.9, daily * 1.3)
    elif profile == "low":
        qty = rng.uniform(reorder * 0.5, reorder * 1.2)
        cons = rng.uniform(daily * 0.8, daily * 1.2)
    elif profile == "surplus":
        qty = rng.uniform(reorder * 4, max_s)
        cons = rng.uniform(daily * 0.7, daily * 1.0)
    else:  # normal
        qty = rng.uniform(reorder * 1.5, max_s * 0.8)
        cons = rng.uniform(daily * 0.8, daily * 1.2)

    return {"quantity": round(qty, 0), "daily_consumption": round(cons, 1)}


def make_phc_id(state_code: str, district_code: str, num: int) -> str:
    return f"{state_code}-{district_code}-{num:03d}"


def days_of_stock(qty: float, cons: float) -> float:
    return round(qty / cons, 1) if cons > 0 else 999.0


def compute_risk_score(phc_data: dict, inventory: list[dict], supplier_delay: int, patient_change_pct: float) -> tuple[int, str, list[str]]:
    """Inline risk scoring (mirrors risk_engine.py for seed independence)."""
    score = 0
    factors = []

    # Medicine component (max 40, with criticality mult)
    critical_meds = [i for i in inventory if i["criticality"] in ("CRITICAL", "HIGH")]
    if critical_meds:
        worst = min(critical_meds, key=lambda m: days_of_stock(m["quantity"], m["daily_consumption"]))
        dos = days_of_stock(worst["quantity"], worst["daily_consumption"])
        mult = 1.5 if worst["criticality"] == "CRITICAL" else 1.25
        if dos < 3:   base = int(40 * mult)
        elif dos < 7: base = int(30 * mult)
        elif dos < 14:base = int(15 * mult)
        else:         base = 0
        med_score = min(40, base)
        if med_score > 0:
            med_name = worst.get("medicine_name", worst.get("name", "Medicine"))
            factors.append(f"{med_name} — {dos:.1f} days of stock")
        score += med_score

    # Supplier delay (max 15)
    if supplier_delay >= 7:   score += 15; factors.append(f"Supplier delay {supplier_delay}d (severe)")
    elif supplier_delay >= 3: score += 10; factors.append(f"Supplier delay {supplier_delay}d")
    elif supplier_delay > 0:  score += 5

    # Bed utilization (max 20)
    bt = phc_data.get("beds_total", 1)
    bo = phc_data.get("beds_occupied", 0)
    bed_rate = bo / bt if bt > 0 else 0
    if bed_rate > 0.95:   score += 20; factors.append(f"Bed occupancy critical ({bed_rate:.0%})")
    elif bed_rate > 0.85: score += 12; factors.append(f"Bed occupancy high ({bed_rate:.0%})")
    elif bed_rate > 0.75: score += 6

    # Doctor attendance (max 20)
    dt = phc_data.get("doctors_total", 1)
    dp = phc_data.get("doctors_present", 1)
    doc_rate = dp / dt if dt > 0 else 1.0
    if doc_rate < 0.50:   score += 20; factors.append(f"Severe doctor shortage ({doc_rate:.0%})")
    elif doc_rate < 0.75: score += 12; factors.append(f"Doctor shortage ({doc_rate:.0%})")
    elif doc_rate < 1.0:  score += 6

    # Patient surge (max 20)
    if patient_change_pct > 30:   score += 20; factors.append(f"Patient surge +{patient_change_pct:.0f}%")
    elif patient_change_pct > 15: score += 12; factors.append(f"Patient trend rising +{patient_change_pct:.0f}%")
    elif patient_change_pct > 5:  score += 6

    score = min(100, score)
    if score >= 70:   severity = "CRITICAL"
    elif score >= 50: severity = "HIGH"
    elif score >= 30: severity = "MEDIUM"
    else:             severity = "LOW"

    return score, severity, factors


def to_decimal(obj):
    """Recursively convert float to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(round(obj, 4)))
    if isinstance(obj, dict):
        return {k: to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_decimal(v) for v in obj]
    return obj


# ─── Table creation ────────────────────────────────────────────────────────

TABLE_DEFS = [
    {
        "TableName": "resilia-phcs",
        "KeySchema": [{"AttributeName": "phc_id", "KeyType": "HASH"}],
        "AttributeDefinitions": [
            {"AttributeName": "phc_id",       "AttributeType": "S"},
            {"AttributeName": "state_code",   "AttributeType": "S"},
            {"AttributeName": "district_code","AttributeType": "S"},
            {"AttributeName": "risk_severity","AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "State-Index",
                "KeySchema": [
                    {"AttributeName": "state_code",    "KeyType": "HASH"},
                    {"AttributeName": "district_code", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            },
            {
                "IndexName": "Risk-Index",
                "KeySchema": [
                    {"AttributeName": "state_code",   "KeyType": "HASH"},
                    {"AttributeName": "risk_severity","KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            },
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
    },
    {
        "TableName": "resilia-inventory",
        "KeySchema": [
            {"AttributeName": "phc_id",        "KeyType": "HASH"},
            {"AttributeName": "medicine_code", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "phc_id",        "AttributeType": "S"},
            {"AttributeName": "medicine_code", "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
    },
    {
        "TableName": "resilia-patients",
        "KeySchema": [
            {"AttributeName": "phc_id", "KeyType": "HASH"},
            {"AttributeName": "date",   "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "phc_id", "AttributeType": "S"},
            {"AttributeName": "date",   "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": "resilia-staff",
        "KeySchema": [
            {"AttributeName": "phc_id", "KeyType": "HASH"},
            {"AttributeName": "date",   "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "phc_id", "AttributeType": "S"},
            {"AttributeName": "date",   "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": "resilia-alerts",
        "KeySchema": [
            {"AttributeName": "alert_id",    "KeyType": "HASH"},
            {"AttributeName": "created_at",  "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "alert_id",   "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
            {"AttributeName": "phc_id",     "AttributeType": "S"},
            {"AttributeName": "severity",   "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "PHC-Alert-Index",
                "KeySchema": [
                    {"AttributeName": "phc_id",     "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            },
            {
                "IndexName": "Severity-Index",
                "KeySchema": [
                    {"AttributeName": "severity",   "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            },
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": "resilia-suppliers",
        "KeySchema": [{"AttributeName": "supplier_id", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "supplier_id", "AttributeType": "S"}],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": "resilia-shipments",
        "KeySchema": [
            {"AttributeName": "shipment_id", "KeyType": "HASH"},
            {"AttributeName": "phc_id",      "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "shipment_id", "AttributeType": "S"},
            {"AttributeName": "phc_id",      "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "PHC-Shipment-Index",
                "KeySchema": [{"AttributeName": "phc_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            },
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": "resilia-interventions",
        "KeySchema": [
            {"AttributeName": "intervention_id", "KeyType": "HASH"},
            {"AttributeName": "created_at",      "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "intervention_id", "AttributeType": "S"},
            {"AttributeName": "created_at",      "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
]


def create_tables():
    existing = set(client.list_tables()["TableNames"])
    for defn in TABLE_DEFS:
        name = defn["TableName"]
        if name in existing:
            print(f"  ✓ Table exists: {name}")
            continue
        dynamodb.create_table(**defn)
        print(f"  + Created table: {name}")
    # Wait for tables to be active
    time.sleep(1)


# ─── Generation functions ─────────────────────────────────────────────────

def generate_phcs() -> list[dict]:
    phcs = []
    counter = {}    # state+district → sequential number

    # ── Add the 7 demo PHCs first ──
    for phc_id, cfg in DEMO_PHCS.items():
        parts = phc_id.split("-")
        state_code, district_code = parts[0], parts[1]
        num = int(parts[2])
        district_data = NETWORK[state_code]["districts"][district_code]
        clat, clng = district_data["center"]
        lat, lng = jitter(clat, clng, 0.06)

        phcs.append({
            "phc_id":           phc_id,
            "name":             cfg["name"],
            "state":            NETWORK[state_code]["state"],
            "state_code":       state_code,
            "district":         district_data["name"],
            "district_code":    district_code,
            "zone":             cfg["zone"],
            "lat":              lat,
            "lng":              lng,
            "address":          f"{cfg['locality']}, {district_data['name']}",
            "beds_total":       cfg["beds_total"],
            "beds_occupied":    cfg["beds_occupied"],
            "beds_icu":         rng.randint(1, 3),
            "doctors_total":    cfg["doctors_total"],
            "doctors_present":  cfg["doctors_present"],
            "nurses_total":     cfg["nurses_total"],
            "nurses_present":   cfg["nurses_present"],
            "asha_workers":     cfg["asha_workers"],
            "pharmacists":      1,
            "supplier_ids":     [cfg["supplier_id"]],
            "district_hospital_id": district_data["hospital"],
            "_supplier_id":     cfg["supplier_id"],
            "_patient_change":  cfg["patient_7d_change_pct"],
            "_inventory_overrides": cfg.get("inventory_overrides", {}),
            "active_alerts":    0,
            "risk_score":       0,
            "risk_severity":    "LOW",
            "risk_factors":     [],
            "last_updated":     datetime.utcnow().isoformat(),
        })
        counter[(state_code, district_code)] = max(counter.get((state_code, district_code), 0), num)

    # ── Generate the remaining ~68 PHCs ──
    profiles = (
        ["high"] * 8 + ["medium"] * 18 + ["low"] * 42
    )
    rng.shuffle(profiles)
    profile_idx = 0

    for state_code, state_data in NETWORK.items():
        for district_code, district_data in state_data["districts"].items():
            localities = district_data["localities"].copy()
            rng.shuffle(localities)
            clat, clng = district_data["center"]

            # Pick suppliers for this state
            state_suppliers = [s for s in SUPPLIERS if s["state"] == state_code]
            if not state_suppliers:
                state_suppliers = SUPPLIERS[:1]

            # How many PHCs for this district
            n_phcs = len(localities)

            for i, locality in enumerate(localities):
                key = (state_code, district_code)
                counter[key] = counter.get(key, 0) + 1
                num = counter[key]
                phc_id = make_phc_id(state_code, district_code, num)

                # Skip if already added as demo PHC
                if phc_id in DEMO_PHCS:
                    continue

                profile = profiles[profile_idx % len(profiles)]
                profile_idx += 1

                lat, lng = jitter(clat, clng, 0.08)
                sup = rng.choice(state_suppliers)

                if profile == "high":
                    beds_t = rng.randint(20, 40)
                    beds_o = int(beds_t * rng.uniform(0.85, 0.98))
                    doc_t = rng.randint(2, 4)
                    doc_p = max(1, int(doc_t * rng.uniform(0.4, 0.75)))
                    patient_change = rng.uniform(15, 40)
                    zone = rng.choice(["Urban", "Semi-urban", "Rural"])
                elif profile == "medium":
                    beds_t = rng.randint(20, 40)
                    beds_o = int(beds_t * rng.uniform(0.65, 0.85))
                    doc_t = rng.randint(2, 4)
                    doc_p = max(1, int(doc_t * rng.uniform(0.7, 1.0)))
                    patient_change = rng.uniform(5, 15)
                    zone = rng.choice(["Urban", "Semi-urban", "Rural"])
                else:
                    beds_t = rng.randint(15, 35)
                    beds_o = int(beds_t * rng.uniform(0.3, 0.65))
                    doc_t = rng.randint(2, 3)
                    doc_p = doc_t
                    patient_change = rng.uniform(-5, 5)
                    zone = rng.choice(["Rural", "Semi-urban"])

                nurses_t = doc_t + rng.randint(1, 3)
                nurses_p = min(nurses_t, max(1, int(nurses_t * rng.uniform(0.7, 1.0))))

                phcs.append({
                    "phc_id":           phc_id,
                    "name":             f"PHC {locality}",
                    "state":            state_data["state"],
                    "state_code":       state_code,
                    "district":         district_data["name"],
                    "district_code":    district_code,
                    "zone":             zone,
                    "lat":              lat,
                    "lng":              lng,
                    "address":          f"{locality}, {district_data['name']}",
                    "beds_total":       beds_t,
                    "beds_occupied":    beds_o,
                    "beds_icu":         rng.randint(0, 3),
                    "doctors_total":    doc_t,
                    "doctors_present":  doc_p,
                    "nurses_total":     nurses_t,
                    "nurses_present":   nurses_p,
                    "asha_workers":     rng.randint(6, 18),
                    "pharmacists":      1,
                    "supplier_ids":     [sup["id"]],
                    "district_hospital_id": district_data["hospital"],
                    "_supplier_id":     sup["id"],
                    "_patient_change":  round(patient_change, 1),
                    "_inventory_overrides": {},
                    "active_alerts":    0,
                    "risk_score":       0,
                    "risk_severity":    "LOW",
                    "risk_factors":     [],
                    "last_updated":     datetime.utcnow().isoformat(),
                })

    return phcs


def generate_inventory(phc: dict) -> list[dict]:
    """Generate 15 medicine records for a PHC."""
    supplier_id = phc["_supplier_id"]
    sup = next((s for s in SUPPLIERS if s["id"] == supplier_id), SUPPLIERS[0])
    overrides = phc.get("_inventory_overrides", {})

    # Determine base stock profile
    risk_severity = phc.get("risk_severity", "LOW")
    if risk_severity == "CRITICAL":
        base_profile = "low"
    elif risk_severity == "HIGH":
        base_profile = "low"
    else:
        base_profile = "normal"

    inventory = []
    today = date.today()

    for med in MEDICINES:
        if med["code"] in overrides:
            override = overrides[med["code"]]
            qty = override["quantity"]
            cons = override["daily_consumption"]
        else:
            stock = random_stock(med, base_profile)
            qty = stock["quantity"]
            cons = stock["daily_consumption"]

        dos = days_of_stock(qty, cons)
        expiry_days = rng.randint(30, 730)
        expiry_date = (today + timedelta(days=expiry_days)).isoformat()

        # Risk score for this medicine
        mult = 1.5 if med["criticality"] == "CRITICAL" else 1.25 if med["criticality"] == "HIGH" else 1.0
        if dos < 3:   base = 40
        elif dos < 7: base = 30
        elif dos < 14:base = 15
        else:         base = 0
        risk_score = min(100, int(base * mult))
        if risk_score >= 70:   med_sev = "CRITICAL"
        elif risk_score >= 50: med_sev = "HIGH"
        elif risk_score >= 30: med_sev = "MEDIUM"
        else:                  med_sev = "LOW"

        inventory.append({
            "phc_id":           phc["phc_id"],
            "medicine_code":    med["code"],
            "medicine_name":    med["name"],
            "category":         med["category"],
            "criticality":      med["criticality"],
            "quantity":         float(qty),
            "unit":             med["unit"],
            "reorder_level":    float(med["reorder"]),
            "max_stock_level":  float(med["max"]),
            "daily_consumption":float(cons),
            "days_of_stock":    float(dos),
            "expiry_date":      expiry_date,
            "batch_number":     f"BN-{rng.randint(10000,99999)}",
            "supplier_id":      supplier_id,
            "last_restocked":   (datetime.utcnow() - timedelta(days=rng.randint(5, 30))).isoformat(),
            "last_updated":     datetime.utcnow().isoformat(),
            "risk_score":       risk_score,
            "risk_severity":    med_sev,
        })

    return inventory


def generate_patient_records(phc: dict) -> list[dict]:
    """7 days of daily patient footfall records."""
    base_opd = rng.randint(60, 180)
    change_pct = phc.get("_patient_change", 0.0)
    records = []
    today = date.today()

    diseases = ["diarrhea", "malaria", "dengue", "respiratory", "typhoid", "skin", "injuries", "antenatal", "other"]

    for i in range(7):
        day = today - timedelta(days=6 - i)
        # Apply trend: ramp from 0% change to full change_pct over 7 days
        day_factor = 1 + (change_pct / 100) * (i / 6)
        opd = max(10, int(base_opd * day_factor * rng.uniform(0.9, 1.1)))
        ipd = max(0, int(opd * rng.uniform(0.04, 0.10)))
        admissions = max(0, int(ipd * rng.uniform(0.3, 0.7)))
        discharges = max(0, admissions - rng.randint(0, 2))
        referrals = max(0, int(ipd * rng.uniform(0.05, 0.15)))

        # Disease breakdown
        total_disease = opd
        breakdown = {}
        for d in diseases[:-1]:
            share = rng.uniform(0.05, 0.25)
            count = int(total_disease * share)
            breakdown[d] = count
        breakdown["other"] = max(0, total_disease - sum(breakdown.values()))

        # 7d change vs first day
        if i > 0:
            first = records[0]["total_opd"]
            change = round((opd - first) / max(first, 1) * 100, 1)
        else:
            change = 0.0

        records.append({
            "phc_id":          phc["phc_id"],
            "date":            day.isoformat(),
            "total_opd":       opd,
            "total_ipd":       ipd,
            "new_admissions":  admissions,
            "discharges":      discharges,
            "referrals_out":   referrals,
            "deaths":          0,
            "disease_breakdown": breakdown,
            "change_7d_pct":   change,
            "trend":           ("rising" if change > 5 else "falling" if change < -5 else "stable"),
        })

    return records


def generate_staff_record(phc: dict) -> dict:
    today = date.today().isoformat()
    return {
        "phc_id":              phc["phc_id"],
        "date":                today,
        "doctors_total":       phc["doctors_total"],
        "doctors_present":     phc["doctors_present"],
        "nurses_total":        phc["nurses_total"],
        "nurses_present":      phc["nurses_present"],
        "asha_total":          phc["asha_workers"],
        "asha_active":         max(1, int(phc["asha_workers"] * rng.uniform(0.7, 1.0))),
        "pharmacists_total":   phc.get("pharmacists", 1),
        "pharmacists_present": phc.get("pharmacists", 1),
        "on_leave":            [],
        "notes":               None,
    }


def generate_shipment(phc: dict, supplier: dict) -> dict:
    today = datetime.utcnow()
    ordered = today - timedelta(days=rng.randint(1, 5))
    base_lead = supplier["lead_time"]
    delay = supplier["delay_days"]
    expected = ordered + timedelta(days=base_lead)
    status = "DELAYED" if supplier["delayed"] else rng.choice(["PENDING", "IN_TRANSIT", "IN_TRANSIT"])

    # Pick 3-5 medicines for the shipment
    meds_sample = rng.sample(MEDICINES, rng.randint(3, 5))
    items = [
        {
            "medicine_code": m["code"],
            "medicine_name": m["name"],
            "quantity": float(rng.randint(100, 1000)),
            "unit": m["unit"],
            "batch_number": f"BN-{rng.randint(10000,99999)}",
            "expiry_date": (date.today() + timedelta(days=rng.randint(180, 730))).isoformat(),
        }
        for m in meds_sample
    ]

    return {
        "shipment_id":    f"SHP-{uuid.uuid4().hex[:8].upper()}",
        "phc_id":         phc["phc_id"],
        "supplier_id":    supplier["id"],
        "supplier_name":  supplier["name"],
        "status":         status,
        "ordered_at":     ordered.isoformat(),
        "expected_delivery": expected.isoformat(),
        "actual_delivery":   None,
        "delay_days":        delay,
        "delay_reason":      supplier.get("delay_reason", ""),
        "items":             items,
        "total_value_inr":   float(rng.randint(5000, 50000)),
        "notes":             None,
    }


def generate_alert(phc: dict, inventory: list[dict]) -> list[dict]:
    """Generate alerts based on risk scores."""
    alerts = []
    now = datetime.utcnow()

    severity = phc.get("risk_severity", "LOW")
    if severity not in ("CRITICAL", "HIGH"):
        return []

    # Find the worst medicine
    worst_med = None
    worst_dos = 999.0
    for item in inventory:
        if item["criticality"] in ("CRITICAL", "HIGH"):
            dos = item["days_of_stock"]
            if dos < worst_dos:
                worst_dos = dos
                worst_med = item

    if worst_med:
        alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
        sev = "CRITICAL" if worst_dos < 7 else "HIGH"
        alerts.append({
            "alert_id":     alert_id,
            "phc_id":       phc["phc_id"],
            "phc_name":     phc["name"],
            "district":     phc["district"],
            "state":        phc["state"],
            "alert_type":   "STOCKOUT_RISK",
            "severity":     sev,
            "risk_score":   phc["risk_score"],
            "title":        f"{worst_med['medicine_name']} stock-out risk at {phc['name']}",
            "message":      (
                f"{worst_med['medicine_name']} stock at {phc['name']} will last only "
                f"{worst_dos:.1f} days at current consumption rate of "
                f"{worst_med['daily_consumption']:.0f} {worst_med['unit']}/day. "
                f"Current stock: {int(worst_med['quantity'])} {worst_med['unit']}."
            ),
            "factors":      phc.get("risk_factors", []),
            "medicine":     worst_med["medicine_name"],
            "days_of_stock":worst_dos,
            "supplier_id":  worst_med.get("supplier_id"),
            "acknowledged": False,
            "acknowledged_by": None,
            "acknowledged_at": None,
            "created_at":   now.isoformat(),
            "expires_at":   (now + timedelta(days=7)).isoformat(),
        })

    # Bed overflow alert
    beds_t = phc.get("beds_total", 1)
    beds_o = phc.get("beds_occupied", 0)
    bed_rate = beds_o / beds_t if beds_t > 0 else 0
    if bed_rate > 0.90:
        alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
        alerts.append({
            "alert_id":     alert_id,
            "phc_id":       phc["phc_id"],
            "phc_name":     phc["name"],
            "district":     phc["district"],
            "state":        phc["state"],
            "alert_type":   "BED_OVERFLOW",
            "severity":     "HIGH" if bed_rate > 0.95 else "MEDIUM",
            "risk_score":   phc["risk_score"],
            "title":        f"Bed capacity critical at {phc['name']} ({bed_rate:.0%})",
            "message":      f"{beds_o} of {beds_t} beds occupied ({bed_rate:.0%}). Referral capacity may be needed.",
            "factors":      [f"Bed occupancy {bed_rate:.0%}"],
            "medicine":     None,
            "days_of_stock":None,
            "supplier_id":  None,
            "acknowledged": False,
            "acknowledged_by": None,
            "acknowledged_at": None,
            "created_at":   (now - timedelta(minutes=rng.randint(10, 120))).isoformat(),
            "expires_at":   None,
        })

    return alerts


# ─── Main seeding function ────────────────────────────────────────────────

def seed():
    print("\n══════════════════════════════════════════")
    print("  RESILIA Database Seed")
    print(f"  DynamoDB: {ENDPOINT}")
    print("══════════════════════════════════════════\n")

    # 1. Create tables
    print("1. Creating DynamoDB tables…")
    create_tables()

    # 2. Seed suppliers
    print("\n2. Seeding suppliers…")
    sup_table = dynamodb.Table("resilia-suppliers")
    for sup in SUPPLIERS:
        sup_table.put_item(Item=to_decimal(sup))
    print(f"   ✓ {len(SUPPLIERS)} suppliers")

    # 3. Generate PHCs
    print("\n3. Generating PHCs…")
    phcs = generate_phcs()
    print(f"   Generated {len(phcs)} PHC records")

    # 4. Generate inventory + compute risk for each PHC
    print("\n4. Generating inventory + computing risk scores…")
    all_inventory = []
    phc_table = dynamodb.Table("resilia-phcs")
    inv_table  = dynamodb.Table("resilia-inventory")

    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for phc in phcs:
        inventory = generate_inventory(phc)
        all_inventory.extend(inventory)

        # Find the supplier
        sup_id = phc["_supplier_id"]
        sup = next((s for s in SUPPLIERS if s["id"] == sup_id), {"delay_days": 0})

        # Compute risk
        score, severity, factors = compute_risk_score(
            phc, inventory, sup.get("delay_days", 0), phc.get("_patient_change", 0.0)
        )
        phc["risk_score"]    = score
        phc["risk_severity"] = severity
        phc["risk_factors"]  = factors
        severity_counts[severity] += 1

    print(f"   ✓ Risk distribution: CRITICAL={severity_counts['CRITICAL']} HIGH={severity_counts['HIGH']} MEDIUM={severity_counts['MEDIUM']} LOW={severity_counts['LOW']}")

    # 5. Write PHCs
    print("\n5. Writing PHC records…")
    for phc in phcs:
        clean = {k: v for k, v in phc.items() if not k.startswith("_")}
        phc_table.put_item(Item=to_decimal(clean))
    print(f"   ✓ {len(phcs)} PHCs written")

    # 6. Write inventory
    print("\n6. Writing inventory records…")
    with inv_table.batch_writer() as batch:
        for item in all_inventory:
            batch.put_item(Item=to_decimal(item))
    print(f"   ✓ {len(all_inventory)} inventory records ({len(MEDICINES)} medicines × {len(phcs)} PHCs)")

    # 7. Generate + write patient records
    print("\n7. Generating patient records (7 days × each PHC)…")
    pat_table = dynamodb.Table("resilia-patients")
    total_patient_recs = 0
    with pat_table.batch_writer() as batch:
        for phc in phcs:
            for rec in generate_patient_records(phc):
                batch.put_item(Item=to_decimal(rec))
                total_patient_recs += 1
    print(f"   ✓ {total_patient_recs} patient records")

    # 8. Generate + write staff records
    print("\n8. Generating staff records…")
    staff_table = dynamodb.Table("resilia-staff")
    with staff_table.batch_writer() as batch:
        for phc in phcs:
            batch.put_item(Item=to_decimal(generate_staff_record(phc)))
    print(f"   ✓ {len(phcs)} staff records")

    # 9. Generate shipments (one per PHC for delayed suppliers)
    print("\n9. Generating shipment records…")
    ship_table = dynamodb.Table("resilia-shipments")
    total_shipments = 0
    for phc in phcs:
        sup_id = phc["_supplier_id"]
        sup = next((s for s in SUPPLIERS if s["id"] == sup_id), None)
        if sup:
            ship = generate_shipment(phc, sup)
            ship_table.put_item(Item=to_decimal(ship))
            total_shipments += 1
    print(f"   ✓ {total_shipments} shipment records")

    # 10. Generate alerts
    print("\n10. Generating alerts for HIGH/CRITICAL PHCs…")
    alert_table = dynamodb.Table("resilia-alerts")
    phc_inv_map = {}
    for item in all_inventory:
        phc_inv_map.setdefault(item["phc_id"], []).append(item)

    total_alerts = 0
    for phc in phcs:
        alerts = generate_alert(phc, phc_inv_map.get(phc["phc_id"], []))
        for alert in alerts:
            alert_table.put_item(Item=to_decimal(alert))
            total_alerts += 1
        # Update PHC active_alerts count
        if alerts:
            phc_table.update_item(
                Key={"phc_id": phc["phc_id"]},
                UpdateExpression="SET active_alerts = :a",
                ExpressionAttributeValues={":a": len(alerts)},
            )
    print(f"   ✓ {total_alerts} alerts generated")

    print("\n══════════════════════════════════════════")
    print("  ✅  Seed complete!")
    print(f"  PHCs:        {len(phcs)}")
    print(f"  Medicines:   {len(all_inventory)}")
    print(f"  Patients:    {total_patient_recs}")
    print(f"  Alerts:      {total_alerts}")
    print(f"  Suppliers:   {len(SUPPLIERS)}")
    print(f"  Shipments:   {total_shipments}")
    print("══════════════════════════════════════════\n")


if __name__ == "__main__":
    seed()
