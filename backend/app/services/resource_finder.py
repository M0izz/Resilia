"""
RESILIA Resource Finder Service — Sprint 3
===========================================
Scans the healthcare facility network to identify candidate facilities
holding surplus inventory beyond safety-stock thresholds.

Calculates:
  • Haversine geodetic distance (km)
  • Road transit ETA (hours) accounting for corridor speed profiles
  • Safety stock reserve (default 7 days)
  • Available transferable surplus units
  • Cross-district vs intra-district categorization
"""
from __future__ import annotations

import logging
import math
import socket
from urllib.parse import urlparse
from typing import Optional

from app.config import settings
from app.models.optimization import SurplusCandidate

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0
DEFAULT_SAFETY_STOCK_DAYS = 7.0
MIN_TRANSFERABLE_UNITS = 25.0


def _is_db_reachable() -> bool:
    try:
        endpoint = settings.dynamodb_endpoint or "http://localhost:8001"
        parsed = urlparse(endpoint)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8001
        with socket.create_connection((host, port), timeout=0.15):
            return True
    except Exception:
        return False


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the great circle distance between two points in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_KM * c, 2)


def estimate_transit_eta(distance_km: float, is_cross_district: bool) -> float:
    """
    Estimate door-to-door transit time in hours.
    Accounts for loading/dispatch buffer + highway vs local road transit speed.
    """
    if is_cross_district:
        # Inter-district: higher speed highway transit + transit hub clearance
        avg_speed = 52.0  # km/h
        buffer_hours = 0.8
    else:
        # Intra-district / urban traffic
        avg_speed = 35.0  # km/h
        buffer_hours = 0.5

    transit_time = distance_km / max(avg_speed, 10.0)
    return round(buffer_hours + transit_time, 1)


class ResourceFinder:
    """
    Network surveillance service to identify candidate surplus facilities
    for medicine stock-out mitigation.
    """

    @classmethod
    def find_surplus_candidates(
        cls,
        target_phc_id: str,
        medicine_code: str,
        target_lat: float,
        target_lng: float,
        target_district: str,
        target_state: str,
        safety_stock_days: float = DEFAULT_SAFETY_STOCK_DAYS,
        max_distance_km: float = 400.0,
        allow_cross_district: bool = True,
        min_surplus_days: float = 3.0,
    ) -> list[SurplusCandidate]:
        """
        Scan all network facilities and return qualified surplus candidates.
        """
        candidates: list[SurplusCandidate] = []

        try:
            if not _is_db_reachable():
                raise ConnectionError("DynamoDB Local endpoint unreachable; utilizing simulated network graph")

            from app.db.dynamodb import scan_all
            from boto3.dynamodb.conditions import Attr

            # Scan inventory for this medicine across all facilities
            inv_items = scan_all("resilia-inventory", Attr("medicine_code").eq(medicine_code))
            phc_items = {p["phc_id"]: p for p in scan_all("resilia-phcs")}

            for inv in inv_items:
                phc_id = inv.get("phc_id")
                if not phc_id or phc_id == target_phc_id:
                    continue

                phc = phc_items.get(phc_id, {})
                source_district = phc.get("district", inv.get("district", "Unknown"))
                source_state = phc.get("state", inv.get("state", target_state))
                is_cross = source_district.lower() != target_district.lower()

                if not allow_cross_district and is_cross:
                    continue

                src_lat = float(phc.get("lat", target_lat + 0.1))
                src_lng = float(phc.get("lng", target_lng + 0.1))

                dist_km = haversine_distance(target_lat, target_lng, src_lat, src_lng)
                if dist_km > max_distance_km:
                    continue

                current_stock = float(inv.get("quantity", 0))
                daily_burn = float(inv.get("daily_consumption", 1.0))
                if daily_burn <= 0:
                    daily_burn = 1.0

                current_days = current_stock / daily_burn
                safety_units = daily_burn * safety_stock_days
                available_units = max(0.0, current_stock - safety_units)
                surplus_days = max(0.0, current_days - safety_stock_days)

                if available_units < MIN_TRANSFERABLE_UNITS or surplus_days < min_surplus_days:
                    continue

                eta = estimate_transit_eta(dist_km, is_cross)
                candidate = SurplusCandidate(
                    phc_id=phc_id,
                    phc_name=phc.get("name", f"PHC {phc_id}"),
                    district=source_district,
                    state=source_state,
                    lat=src_lat,
                    lng=src_lng,
                    current_stock=current_stock,
                    daily_consumption=daily_burn,
                    current_days=round(current_days, 1),
                    safety_stock_days=safety_stock_days,
                    safety_stock_units=round(safety_units, 1),
                    surplus_days=round(surplus_days, 1),
                    available_surplus_units=round(available_units, 1),
                    distance_km=dist_km,
                    eta_hours=eta,
                    is_cross_district=is_cross,
                    risk_severity=phc.get("risk_severity", "LOW"),
                    expiry_days=int(inv.get("expiry_days", 180)),
                )
                candidates.append(candidate)

        except Exception as exc:
            logger.warning("ResourceFinder DB query failed (%s); generating synthetic demo network", exc)
            candidates = cls._generate_fallback_candidates(
                target_phc_id=target_phc_id,
                medicine_code=medicine_code,
                target_lat=target_lat,
                target_lng=target_lng,
                target_district=target_district,
                target_state=target_state,
                safety_stock_days=safety_stock_days,
            )

        # Sort candidates: closest with healthy surplus first
        candidates.sort(key=lambda c: (c.distance_km, -c.available_surplus_units))
        return candidates

    @classmethod
    def _generate_fallback_candidates(
        cls,
        target_phc_id: str,
        medicine_code: str,
        target_lat: float,
        target_lng: float,
        target_district: str,
        target_state: str,
        safety_stock_days: float,
    ) -> list[SurplusCandidate]:
        """
        Realistic fallback candidates matching the RESILIA demo narrative:
        Shortage at PHC-042 (Hadapsar), surplus at PHC-018, PHC-027, PHC-061.
        """
        # Coordinates around Maharashtra / Pune / Satara / Solapur corridor
        archetypes = [
            {
                "phc_id": "MH-PUN-018",
                "name": "PHC Pimpri Hub",
                "district": "Pune",
                "lat": target_lat + 0.12,
                "lng": target_lng - 0.08,
                "current_stock": 1850.0,
                "daily_burn": 68.0,
                "is_cross": False,
                "expiry_days": 210,
            },
            {
                "phc_id": "MH-SAT-027",
                "name": "PHC Shirwal Central",
                "district": "Satara",
                "lat": target_lat - 0.45,
                "lng": target_lng + 0.05,
                "current_stock": 2400.0,
                "daily_burn": 55.0,
                "is_cross": True,
                "expiry_days": 240,
            },
            {
                "phc_id": "MH-SOL-061",
                "name": "PHC Baramati East",
                "district": "Solapur",
                "lat": target_lat - 0.65,
                "lng": target_lng + 0.52,
                "current_stock": 1400.0,
                "daily_burn": 60.0,
                "is_cross": True,
                "expiry_days": 190,
            },
            {
                "phc_id": "MH-PUN-012",
                "name": "PHC Kothrud Apex",
                "district": "Pune",
                "lat": target_lat + 0.06,
                "lng": target_lng - 0.09,
                "current_stock": 950.0,
                "daily_burn": 50.0,
                "is_cross": False,
                "expiry_days": 160,
            },
        ]

        result = []
        for arch in archetypes:
            dist = haversine_distance(target_lat, target_lng, arch["lat"], arch["lng"])
            current_days = arch["current_stock"] / arch["daily_burn"]
            safety_units = arch["daily_burn"] * safety_stock_days
            avail_units = max(0.0, arch["current_stock"] - safety_units)
            surplus_days = max(0.0, current_days - safety_stock_days)

            eta = estimate_transit_eta(dist, arch["is_cross"])
            result.append(
                SurplusCandidate(
                    phc_id=arch["phc_id"],
                    phc_name=arch["name"],
                    district=arch["district"],
                    state=target_state,
                    lat=arch["lat"],
                    lng=arch["lng"],
                    current_stock=arch["current_stock"],
                    daily_consumption=arch["daily_burn"],
                    current_days=round(current_days, 1),
                    safety_stock_days=safety_stock_days,
                    safety_stock_units=round(safety_units, 1),
                    surplus_days=round(surplus_days, 1),
                    available_surplus_units=round(avail_units, 1),
                    distance_km=dist,
                    eta_hours=eta,
                    is_cross_district=arch["is_cross"],
                    risk_severity="LOW",
                    expiry_days=arch["expiry_days"],
                )
            )
        return result
