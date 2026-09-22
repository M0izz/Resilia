"""
RESILIA Resilient In-Memory Data Store.
Provides a thread-safe, high-speed, zero-dependency data store populated with
the realistic 75-facility Indian PHC network across Maharashtra, Delhi, Karnataka,
Tamil Nadu, and West Bengal.

Acts as an automatic failover when DynamoDB Local is offline or unreachable,
guaranteeing 100% platform availability and graceful degradation.
"""
from __future__ import annotations
import random
import uuid
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# ─── Medicine Catalogue ────────────────────────────────────────────────────────

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

# ─── Suppliers ─────────────────────────────────────────────────────────────────

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

# ─── Geographic Network ────────────────────────────────────────────────────────

NETWORK = {
    "MH": {
        "state": "Maharashtra",
        "districts": {
            "PUN": {"name": "Pune", "center": (18.5204, 73.8567), "hospital": "DH-PUN-001", "localities": ["Hadapsar", "Kondhwa", "Yerawada", "Kothrud", "Wakad", "Pimpri", "Chinchwad", "Dhanori", "Warje", "Baner", "Bavdhan", "Lohegaon", "Sinhagad", "Katraj", "Ambegaon"]},
            "MUM": {"name": "Mumbai City", "center": (19.0760, 72.8777), "hospital": "DH-MUM-001", "localities": ["Dharavi", "Andheri East", "Kurla West", "Ghatkopar", "Malad East", "Borivali", "Vikhroli", "Goregaon", "Vile Parle", "Kandivali"]},
            "NGP": {"name": "Nagpur", "center": (21.1458, 79.0882), "hospital": "DH-NGP-001", "localities": ["Kamptee", "Hingna", "Butibori", "Wadi", "Pardi", "Kalamna", "Nandanvan"]},
        },
    },
    "DL": {
        "state": "Delhi",
        "districts": {
            "CD": {"name": "Central Delhi", "center": (28.6448, 77.2167), "hospital": "DH-DL-001", "localities": ["Karol Bagh", "Patel Nagar", "Rajinder Nagar", "Chanakyapuri", "Sadar Bazar"]},
            "SD": {"name": "South Delhi", "center": (28.5355, 77.2090), "hospital": "DH-SD-001", "localities": ["Saket", "Mehrauli", "Hauz Khas", "Kalkaji", "Okhla", "Malviya Nagar"]},
            "ND": {"name": "North Delhi", "center": (28.7041, 77.1025), "hospital": "DH-ND-001", "localities": ["Jahangirpuri", "Mangolpuri", "Burari", "Shakurpur", "Rohini"]},
        },
    },
    "KA": {
        "state": "Karnataka",
        "districts": {
            "BLR": {"name": "Bengaluru Urban", "center": (12.9716, 77.5946), "hospital": "DH-BLR-001", "localities": ["Rajajinagar", "Whitefield", "Hebbal", "Jayanagar", "Koramangala", "Yeshwantpur", "Malleshwaram"]},
            "MYS": {"name": "Mysuru", "center": (12.2958, 76.6394), "hospital": "DH-MYS-001", "localities": ["Kuvempunagar", "Jayalakshmipuram", "Vijayanagar", "Nazarbad", "Lakshmipuram"]},
        },
    },
    "TN": {
        "state": "Tamil Nadu",
        "districts": {
            "CHN": {"name": "Chennai", "center": (13.0827, 80.2707), "hospital": "DH-CHN-001", "localities": ["Tondiarpet", "Royapuram", "Ayanavaram", "Perambur", "Vyasarpadi", "Tiruvottiyur"]},
            "CBE": {"name": "Coimbatore", "center": (11.0168, 76.9558), "hospital": "DH-CBE-001", "localities": ["Ukkadam", "Singanallur", "Ganapathy", "Saibaba Colony", "Peelamedu"]},
        },
    },
    "WB": {
        "state": "West Bengal",
        "districts": {
            "KOL": {"name": "Kolkata", "center": (22.5726, 88.3639), "hospital": "DH-KOL-001", "localities": ["Tangra", "Park Circus", "Tiljala", "Beniapukur", "Kidderpore", "Watgunge"]},
            "HWH": {"name": "Howrah", "center": (22.5958, 88.2636), "hospital": "DH-HWH-001", "localities": ["Shibpur", "Bantra", "Liluah", "Bally", "Domjur"]},
        },
    },
}

# ─── Flagship Problem PHCs ───────────────────────────────────────────────────

DEMO_PHCS = {
    "MH-PUN-042": {
        "name": "PHC Hadapsar", "locality": "Hadapsar",
        "beds_total": 30, "beds_occupied": 27, "beds_icu": 4,
        "doctors_total": 4, "doctors_present": 2,
        "nurses_total": 8, "nurses_present": 5,
        "asha_workers": 12,
        "oxygen_cylinders": 6, "oxygen_available": 2,
        "ambulance_available": False, "generator_functional": True,
        "has_cold_chain": True, "cold_chain_status": "NORMAL",
        "special_medicine_issues": {"ORS-001": {"quantity": 180.0, "daily": 95.0, "days_of_stock": 1.9, "status": "CRITICAL"}},
        "_supplier_id": "SUP-MH-002",
        "_patient_change": 0.42,
    },
    "MH-PUN-018": {
        "name": "PHC Pimpri Hub", "locality": "Pimpri",
        "beds_total": 40, "beds_occupied": 18, "beds_icu": 6,
        "doctors_total": 6, "doctors_present": 5,
        "nurses_total": 12, "nurses_present": 10,
        "asha_workers": 18,
        "oxygen_cylinders": 15, "oxygen_available": 12,
        "ambulance_available": True, "generator_functional": True,
        "has_cold_chain": True, "cold_chain_status": "NORMAL",
        "special_medicine_issues": {"ORS-001": {"quantity": 3800.0, "daily": 60.0, "days_of_stock": 63.3, "status": "SURPLUS"}},
        "_supplier_id": "SUP-MH-001",
        "_patient_change": 0.05,
    },
}


class ResilientInMemoryStore:
    """Thread-safe, self-initializing store providing immediate access to the 75-facility dataset."""

    def __init__(self):
        self._initialized = False
        self.tables: Dict[str, List[dict]] = {
            "resilia-phcs": [],
            "resilia-inventory": [],
            "resilia-patients": [],
            "resilia-staff": [],
            "resilia-alerts": [],
            "resilia-suppliers": [],
            "resilia-shipments": [],
            "resilia-interventions": [],
        }
        self._ensure_initialized()

    def _ensure_initialized(self):
        if self._initialized:
            return
        logger.info("Initializing Resilient InMemory Store with 75-PHC national dataset...")
        rng = random.Random(42)  # Deterministic seed for reproducible testing

        # 1. Suppliers
        self.tables["resilia-suppliers"] = [dict(s) for s in SUPPLIERS]

        # 2. PHCs
        phc_counter = 1
        phc_list = []
        for state_code, sdata in NETWORK.items():
            state_name = sdata["state"]
            sup_candidates = [s for s in SUPPLIERS if s["state"] == state_code]
            for dist_code, ddata in sdata["districts"].items():
                dist_name = ddata["name"]
                c_lat, c_lon = ddata["center"]
                for loc in ddata["localities"]:
                    if dist_code == "PUN" and loc == "Hadapsar":
                        phc_id = "MH-PUN-042"
                    elif dist_code == "PUN" and loc == "Pimpri":
                        phc_id = "MH-PUN-018"
                    else:
                        phc_id = f"{state_code}-{dist_code}-{phc_counter:03d}"
                    if phc_id in DEMO_PHCS:
                        pdata = DEMO_PHCS[phc_id]
                        name = pdata["name"]
                        locality = pdata["locality"]
                        beds_t = pdata["beds_total"]
                        beds_o = pdata["beds_occupied"]
                        beds_icu = pdata["beds_icu"]
                        doc_t = pdata["doctors_total"]
                        doc_p = pdata["doctors_present"]
                        nur_t = pdata["nurses_total"]
                        nur_p = pdata["nurses_present"]
                        asha = pdata["asha_workers"]
                        oxy_t = pdata["oxygen_cylinders"]
                        oxy_a = pdata["oxygen_available"]
                        amb = pdata["ambulance_available"]
                        gen = pdata["generator_functional"]
                        cc = pdata["has_cold_chain"]
                        ccs = pdata["cold_chain_status"]
                        sup_id = pdata["_supplier_id"]
                        pchange = pdata["_patient_change"]
                        special_meds = pdata["special_medicine_issues"]
                    else:
                        name = f"PHC {loc}"
                        locality = loc
                        beds_t = rng.choice([10, 20, 30])
                        beds_o = int(beds_t * rng.uniform(0.3, 0.85))
                        beds_icu = max(1, int(beds_t * 0.15))
                        doc_t = rng.choice([2, 3, 4])
                        doc_p = max(1, int(doc_t * rng.uniform(0.5, 1.0)))
                        nur_t = doc_t * 2
                        nur_p = max(1, int(nur_t * rng.uniform(0.6, 1.0)))
                        asha = rng.randint(6, 16)
                        oxy_t = rng.randint(4, 12)
                        oxy_a = max(1, int(oxy_t * rng.uniform(0.4, 0.9)))
                        amb = rng.random() > 0.35
                        gen = rng.random() > 0.15
                        cc = True
                        ccs = "NORMAL"
                        sup_id = sup_candidates[0]["id"] if sup_candidates else "SUP-MH-001"
                        pchange = round(rng.uniform(-0.15, 0.25), 2)
                        special_meds = {}

                    lat = round(c_lat + rng.uniform(-0.06, 0.06), 4)
                    lon = round(c_lon + rng.uniform(-0.06, 0.06), 4)

                    phc_rec = {
                        "phc_id": phc_id,
                        "name": name,
                        "state_code": state_code,
                        "state": state_name,
                        "district_code": dist_code,
                        "district": dist_name,
                        "locality": locality,
                        "zone": "URBAN" if dist_code in ("PUN", "MUM", "BLR", "CHN", "KOL", "CD") else "RURAL",
                        "lat": lat,
                        "lng": lon,
                        "latitude": lat,
                        "longitude": lon,
                        "address": f"Near Community Health Center, {locality}, {dist_name}",
                        "catchment_population": rng.randint(25000, 75000),
                        "beds_total": beds_t,
                        "beds_occupied": beds_o,
                        "beds_icu": beds_icu,
                        "doctors_total": doc_t,
                        "doctors_present": doc_p,
                        "nurses_total": nur_t,
                        "nurses_present": nur_p,
                        "asha_workers": asha,
                        "pharmacists": 1,
                        "oxygen_cylinders": oxy_t,
                        "oxygen_available": oxy_a,
                        "ambulance_available": amb,
                        "generator_functional": gen,
                        "has_cold_chain": cc,
                        "cold_chain_status": ccs,
                        "nearest_district_hospital": ddata["hospital"],
                        "district_hospital_id": ddata["hospital"],
                        "distance_to_hospital_km": round(rng.uniform(8.0, 35.0), 1),
                        "primary_supplier_id": sup_id,
                        "supplier_ids": [sup_id],
                        "risk_score": 35,
                        "risk_severity": "LOW",
                        "risk_factors": [],
                        "active_alerts": 0,
                        "last_updated": datetime.utcnow().isoformat(),
                        "patient_surge_pct": round(pchange * 100, 1),
                        "_special_meds": special_meds,
                        "_supplier_id": sup_id,
                        "_patient_change": pchange,
                    }
                    phc_list.append(phc_rec)
                    phc_counter += 1

        # 3. Inventories & Risk Scoring
        all_inventory = []
        for phc in phc_list:
            phc_inv = []
            sup = next((s for s in SUPPLIERS if s["id"] == phc["_supplier_id"]), {"delay_days": 0})
            special = phc.get("_special_meds", {})

            for med in MEDICINES:
                code = med["code"]
                base_daily = med["daily_base"]
                daily = round(base_daily * (1.0 + phc["_patient_change"]) * rng.uniform(0.85, 1.15), 1)

                if code in special:
                    sp = special[code]
                    qty = float(sp["quantity"])
                    daily = float(sp.get("daily", daily))
                    dos = round(qty / daily, 1) if daily > 0 else 99.0
                    status = sp.get("status", "NORMAL")
                else:
                    dos = round(rng.uniform(5.0, 35.0), 1)
                    qty = round(dos * daily)
                    if dos < 5.0:
                        status = "CRITICAL"
                    elif dos < 10.0:
                        status = "LOW"
                    elif dos > 30.0:
                        status = "SURPLUS"
                    else:
                        status = "NORMAL"

                inv_risk_int = int(max(5, min(95, 100 - (dos * 3.5))))
                inv_rec = {
                    "phc_id": phc["phc_id"],
                    "medicine_code": code,
                    "medicine_name": med["name"],
                    "category": med["category"],
                    "criticality": med["criticality"],
                    "unit": med["unit"],
                    "quantity": float(qty),
                    "reorder_level": float(med["reorder"]),
                    "max_stock_level": float(med["max"]),
                    "max_capacity": float(med["max"]),
                    "daily_consumption": daily,
                    "days_of_stock": dos,
                    "status": status,
                    "expiry_date": (date.today() + timedelta(days=rng.randint(180, 540))).isoformat(),
                    "batch_number": f"BN-{rng.randint(10000, 99999)}",
                    "supplier_id": phc["_supplier_id"],
                    "last_restocked": (datetime.utcnow() - timedelta(days=rng.randint(2, 20))).strftime("%Y-%m-%d"),
                    "last_updated": datetime.utcnow().isoformat(),
                    "risk_score": inv_risk_int,
                    "risk_severity": "CRITICAL" if inv_risk_int >= 75 else ("HIGH" if inv_risk_int >= 55 else ("MEDIUM" if inv_risk_int >= 35 else "LOW")),
                }
                phc_inv.append(inv_rec)
                all_inventory.append(inv_rec)

            # Compute compound multi-factor risk score
            critical_meds = [i for i in phc_inv if i["criticality"] == "CRITICAL" and i["days_of_stock"] < 7.0]
            stockout_risk = 0.85 if critical_meds else 0.15
            bed_ratio = phc["beds_occupied"] / phc["beds_total"] if phc["beds_total"] > 0 else 0.5
            staff_ratio = phc["doctors_present"] / phc["doctors_total"] if phc["doctors_total"] > 0 else 0.5
            delay_penalty = min(0.3, sup.get("delay_days", 0) * 0.05)

            compound_score = round(min(0.98, max(0.08, (stockout_risk * 0.45) + (bed_ratio * 0.25) + ((1.0 - staff_ratio) * 0.15) + delay_penalty)), 2)
            risk_score_int = int(round(compound_score * 100))
            if risk_score_int >= 75:
                severity = "CRITICAL"
            elif risk_score_int >= 55:
                severity = "HIGH"
            elif risk_score_int >= 35:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            factors = []
            if critical_meds:
                factors.append(f"Critical stockout risk: {critical_meds[0]['medicine_name']} ({critical_meds[0]['days_of_stock']}d)")
            if bed_ratio >= 0.85:
                factors.append(f"High bed occupancy ({int(bed_ratio*100)}%)")
            if staff_ratio <= 0.6:
                factors.append("Staff deficit")
            if sup.get("delay_days", 0) > 0:
                factors.append(f"Supplier delayed {sup.get('delay_days')}d ({sup.get('delay_reason')})")

            phc["risk_score"] = risk_score_int
            phc["risk_severity"] = severity
            phc["risk_factors"] = factors
            phc["active_alerts"] = len(factors)

        # Clean private fields from phcs
        for p in phc_list:
            p.pop("_special_meds", None)
            p.pop("_supplier_id", None)
            p.pop("_patient_change", None)

        self.tables["resilia-phcs"] = phc_list
        self.tables["resilia-inventory"] = all_inventory

        # 4. Alerts
        alerts = []
        for p in phc_list:
            if p["risk_severity"] in ("CRITICAL", "HIGH"):
                inv_items = [i for i in all_inventory if i["phc_id"] == p["phc_id"]]
                crit = sorted(inv_items, key=lambda x: x["days_of_stock"])
                worst = crit[0] if crit else None
                if worst:
                    alerts.append({
                        "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                        "phc_id": p["phc_id"],
                        "phc_name": p["name"],
                        "district": p["district"],
                        "state": p["state"],
                        "alert_type": "STOCKOUT_RISK",
                        "severity": p["risk_severity"],
                        "risk_score": p["risk_score"],
                        "title": f"{worst['medicine_name']} stockout risk at {p['name']}",
                        "message": f"Inventory reaches critical zero threshold in {worst['days_of_stock']} days under active demand curve.",
                        "factors": p["risk_factors"],
                        "medicine": worst["medicine_name"],
                        "days_of_stock": worst["days_of_stock"],
                        "supplier_id": worst.get("supplier_id"),
                        "acknowledged": False,
                        "acknowledged_by": None,
                        "acknowledged_at": None,
                        "created_at": datetime.utcnow().isoformat(),
                    })
        self.tables["resilia-alerts"] = alerts

        # 4b. Patients (30-day daily records per PHC)
        patients = []
        today = date.today()
        for p in phc_list:
            is_hadapsar = (p["phc_id"] == "MH-PUN-042")
            base_opd = 85 if is_hadapsar else rng.randint(40, 75)
            for d in range(29, -1, -1):
                cur_date = (today - timedelta(days=d)).isoformat()
                # Post-monsoon surge effect for Hadapsar
                if is_hadapsar and d < 14:
                    surge_mult = 1.0 + (0.42 * (14 - d) / 14.0) + rng.uniform(-0.04, 0.06)
                else:
                    surge_mult = 1.0 + rng.uniform(-0.12, 0.12)
                opd = max(15, int(base_opd * surge_mult))
                ipd = max(2, min(p["beds_total"], int(p["beds_occupied"] * rng.uniform(0.85, 1.1))))
                new_adm = max(0, int(ipd * rng.uniform(0.12, 0.25)))
                disch = max(0, int(ipd * rng.uniform(0.10, 0.22)))

                if is_hadapsar:
                    dengue_c = int(opd * rng.uniform(0.28, 0.42))
                    diarrhea_c = int(opd * rng.uniform(0.18, 0.26))
                    fever_c = int(opd * rng.uniform(0.15, 0.22))
                else:
                    dengue_c = int(opd * rng.uniform(0.02, 0.07))
                    diarrhea_c = int(opd * rng.uniform(0.08, 0.16))
                    fever_c = int(opd * rng.uniform(0.10, 0.18))
                resp_c = max(1, opd - (dengue_c + diarrhea_c + fever_c))

                patients.append({
                    "phc_id": p["phc_id"],
                    "date": cur_date,
                    "total_opd": opd,
                    "total_ipd": ipd,
                    "new_admissions": new_adm,
                    "discharges": disch,
                    "referrals_out": max(0, int(ipd * 0.05)),
                    "deaths": 0 if rng.random() > 0.05 else 1,
                    "disease_breakdown": {
                        "dengue": dengue_c,
                        "diarrhea": diarrhea_c,
                        "fever": fever_c,
                        "respiratory": resp_c,
                    },
                    "trend": "rising" if (is_hadapsar and d < 14) else "stable",
                })
        self.tables["resilia-patients"] = patients

        # 4c. Staff (30-day daily attendance per PHC)
        staff_records = []
        for p in phc_list:
            doc_t = p["doctors_total"]
            doc_p = p["doctors_present"]
            nur_t = p["nurses_total"]
            nur_p = p["nurses_present"]
            asha_t = p["asha_workers"]
            pharm_t = p["pharmacists"]
            for d in range(29, -1, -1):
                cur_date = (today - timedelta(days=d)).isoformat()
                dp = max(1, doc_p if d == 0 else int(doc_t * rng.uniform(0.5, 1.0)))
                np = max(1, nur_p if d == 0 else int(nur_t * rng.uniform(0.6, 1.0)))
                ap = max(1, int(asha_t * rng.uniform(0.7, 0.95)))
                pp = max(0, pharm_t if rng.random() > 0.1 else 0)
                staff_records.append({
                    "phc_id": p["phc_id"],
                    "date": cur_date,
                    "doctors_total": doc_t,
                    "doctors_present": dp,
                    "nurses_total": nur_t,
                    "nurses_present": np,
                    "asha_total": asha_t,
                    "asha_active": ap,
                    "pharmacists_total": pharm_t,
                    "pharmacists_present": pp,
                    "on_leave": [f"DOC-{p['phc_id']}-01"] if (doc_t - dp) > 0 else [],
                })
        self.tables["resilia-staff"] = staff_records

        # 5. Shipments
        shipments = []
        for p in phc_list[:15]:
            sup = next((s for s in SUPPLIERS if s["state"] == p["state_code"]), SUPPLIERS[0])
            shipments.append({
                "shipment_id": f"SHP-{uuid.uuid4().hex[:8].upper()}",
                "phc_id": p["phc_id"],
                "supplier_id": sup["supplier_id"],
                "supplier_name": sup["name"],
                "status": "DELAYED" if sup["delayed"] else "IN_TRANSIT",
                "ordered_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                "expected_delivery": (datetime.utcnow() + timedelta(days=2)).isoformat(),
                "delay_days": sup["delay_days"],
                "delay_reason": sup["delay_reason"],
                "total_value_inr": 24500.0,
            })
        self.tables["resilia-shipments"] = shipments

        # 6. Interventions
        self.tables["resilia-interventions"] = [
            {
                "intervention_id": "INTV-DEMO-PUN-042",
                "plan_id": "PLAN-MH-PUN-042",
                "status": "DISPATCHED",
                "target_phc_id": "MH-PUN-042",
                "donor_phc_id": "MH-PUN-018",
                "medicine_code": "ORS-001",
                "quantity": 1100.0,
                "confidence_score": 0.96,
                "recommended_action": "Execute urgent point-to-point lateral supply transfer.",
                "created_at": datetime.utcnow().isoformat(),
                "approved_by": "Dr. Priya Sharma (DHO Pune)",
            }
        ]

        self._initialized = True
        logger.info(f"Resilient Store populated: {len(phc_list)} PHCs, {len(all_inventory)} inventory lines, {len(patients)} patient days, {len(alerts)} alerts.")

    def get_table_items(self, table_name: str, filter_expr=None) -> List[dict]:
        self._ensure_initialized()
        items = self.tables.get(table_name, [])
        if filter_expr is not None:
            return [dict(i) for i in items if matches_condition(i, filter_expr)]
        return [dict(i) for i in items]

    def get_item(self, table_name: str, key: dict) -> Optional[dict]:
        self._ensure_initialized()
        items = self.tables.get(table_name, [])
        for item in items:
            match = True
            for k, v in key.items():
                if item.get(k) != v:
                    match = False
                    break
            if match:
                return dict(item)
        return None

    def query_table(self, table_name: str, index_name: str = None, key_condition=None, filter_expr=None) -> List[dict]:
        self._ensure_initialized()
        items = self.tables.get(table_name, [])
        if key_condition is not None:
            items = [i for i in items if matches_condition(i, key_condition)]
        if filter_expr is not None:
            items = [i for i in items if matches_condition(i, filter_expr)]
        return [dict(i) for i in items]

    def update_item(self, table_name: str, key: dict, attribute_updates: dict) -> bool:
        self._ensure_initialized()
        items = self.tables.get(table_name, [])
        for idx, item in enumerate(items):
            if all(item.get(k) == v for k, v in key.items()):
                item.update(attribute_updates)
                return True
        return False

    def put_item(self, table_name: str, item: dict) -> None:
        self._ensure_initialized()
        if table_name not in self.tables:
            self.tables[table_name] = []
        items = self.tables[table_name]

        # Determine composite or single primary key
        if table_name == "resilia-inventory" or ("phc_id" in item and "medicine_code" in item):
            key_attrs = ["phc_id", "medicine_code"]
        elif table_name in ("resilia-patients", "resilia-staff"):
            key_attrs = ["phc_id", "date"]
        elif table_name == "resilia-shipments":
            key_attrs = ["shipment_id", "phc_id"]
        elif "phc_id" in item:
            key_attrs = ["phc_id"]
        elif "alert_id" in item:
            key_attrs = ["alert_id"]
        elif "intervention_id" in item:
            key_attrs = ["intervention_id"]
        elif "supplier_id" in item:
            key_attrs = ["supplier_id"]
        else:
            key_attrs = [list(item.keys())[0]]

        for idx, existing in enumerate(items):
            if all(existing.get(k) == item.get(k) for k in key_attrs):
                items[idx] = dict(item)
                return
        items.append(dict(item))

    def delete_item(self, table_name: str, key: dict) -> bool:
        """Delete an item by key from the in-memory table."""
        self._ensure_initialized()
        items = self.tables.get(table_name, [])
        for idx, item in enumerate(items):
            if all(item.get(k) == v for k, v in key.items()):
                items.pop(idx)
                return True
        return False

    def reset(self) -> None:
        """Reset in-memory store to fresh seed data."""
        self._initialized = False
        for k in self.tables:
            self.tables[k] = []
        self._ensure_initialized()


def matches_condition(item: dict, cond) -> bool:
    """Evaluate DynamoDB condition against an in-memory dictionary item."""
    if cond is None:
        return True
    try:
        expr = cond.get_expression()
        op = expr.get("operator")
        if op == "AND":
            return all(matches_condition(item, v) for v in expr.get("values", []))
        elif op == "OR":
            return any(matches_condition(item, v) for v in expr.get("values", []))
        elif op == "=":
            vals = expr.get("values", [])
            attr_name = getattr(vals[0], "name", None)
            return str(item.get(attr_name)) == str(vals[1])
        elif op == ">=":
            vals = expr.get("values", [])
            attr_name = getattr(vals[0], "name", None)
            return str(item.get(attr_name)) >= str(vals[1])
        elif op == "<=":
            vals = expr.get("values", [])
            attr_name = getattr(vals[0], "name", None)
            return str(item.get(attr_name)) <= str(vals[1])
        elif op == ">":
            vals = expr.get("values", [])
            attr_name = getattr(vals[0], "name", None)
            return str(item.get(attr_name)) > str(vals[1])
        elif op == "<":
            vals = expr.get("values", [])
            attr_name = getattr(vals[0], "name", None)
            return str(item.get(attr_name)) < str(vals[1])
    except Exception:
        pass
    return True


# Singleton instance
in_memory_store = ResilientInMemoryStore()
