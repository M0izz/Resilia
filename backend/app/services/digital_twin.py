"""
Digital Twin Service — Healthcare Network Topological Modeling using NetworkX.
Represents PHCs, CHCs, District Hospitals, and Central Warehouses as a graph
with supply arteries and clinical referral/spillover corridors.
"""
from __future__ import annotations
import math
import logging
from typing import Dict, List, Any, Optional, Tuple
import networkx as nx

from app.models.crisis import (
    DigitalTwinNode,
    DigitalTwinEdge,
    NetworkGraphResponse,
)

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class HealthcareDigitalTwin:
    """
    In-memory NetworkX digital twin for regional healthcare topology.
    Models PHCs, District Hospitals, Warehouses, supply routes, and referral cascades.
    """

    def __init__(self, region: str = "Pune"):
        self.region = region
        self.graph: nx.DiGraph = nx.DiGraph()
        self._initialize_network()

    def _initialize_network(self) -> None:
        """Build initial graph nodes and edges for Pune & Western Maharashtra."""
        self.graph.clear()

        # ─── 1. Warehouse & Depot Nodes ──────────────────────────────────
        warehouses = [
            {
                "id": "WH-PUN-01",
                "name": "Pune Central Medical Depot",
                "node_type": "WAREHOUSE",
                "district": "Pune",
                "lat": 18.5204,
                "lon": 73.8567,
                "beds_total": 0,
                "beds_occupied": 0,
                "doctors_count": 4,
                "inventory": {
                    "ORS-001": 50000.0,
                    "PCTM-001": 60000.0,
                    "IVNS-001": 25000.0,
                    "AMOX-001": 30000.0,
                    "ARTM-001": 15000.0,
                },
            }
        ]

        # ─── 2. District Hospitals & Tertiary Hubs ────────────────────────
        district_hospitals = [
            {
                "id": "DH-PUN-001",
                "name": "Aundh District Civil Hospital",
                "node_type": "DISTRICT_HOSPITAL",
                "district": "Pune",
                "lat": 18.5602,
                "lon": 73.8031,
                "beds_total": 250,
                "beds_occupied": 190,
                "doctors_count": 35,
                "inventory": {
                    "ORS-001": 12000.0,
                    "PCTM-001": 15000.0,
                    "IVNS-001": 8000.0,
                    "AMOX-001": 7500.0,
                    "ARTM-001": 4000.0,
                },
            }
        ]

        # ─── 3. Primary Health Centres (PHCs) ────────────────────────────
        phcs = [
            {
                "id": "MH-PUN-042",
                "name": "PHC Hadapsar",
                "node_type": "PHC",
                "district": "Pune",
                "lat": 18.5089,
                "lon": 73.9260,
                "beds_total": 24,
                "beds_occupied": 19,
                "doctors_count": 3,
                "inventory": {"ORS-001": 320.0, "PCTM-001": 540.0, "IVNS-001": 140.0, "AMOX-001": 210.0, "ARTM-001": 90.0},
            },
            {
                "id": "MH-PUN-018",
                "name": "PHC Pimpri Hub",
                "node_type": "PHC",
                "district": "Pune",
                "lat": 18.6298,
                "lon": 73.7997,
                "beds_total": 36,
                "beds_occupied": 18,
                "doctors_count": 5,
                "inventory": {"ORS-001": 1850.0, "PCTM-001": 2200.0, "IVNS-001": 850.0, "AMOX-001": 950.0, "ARTM-001": 410.0},
            },
            {
                "id": "MH-PUN-019",
                "name": "PHC Kondhwa",
                "node_type": "PHC",
                "district": "Pune",
                "lat": 18.4695,
                "lon": 73.8887,
                "beds_total": 20,
                "beds_occupied": 16,
                "doctors_count": 2,
                "inventory": {"ORS-001": 410.0, "PCTM-001": 600.0, "IVNS-001": 180.0, "AMOX-001": 230.0, "ARTM-001": 110.0},
            },
            {
                "id": "MH-PUN-033",
                "name": "PHC Kothrud",
                "node_type": "PHC",
                "district": "Pune",
                "lat": 18.5074,
                "lon": 73.8077,
                "beds_total": 22,
                "beds_occupied": 14,
                "doctors_count": 3,
                "inventory": {"ORS-001": 1150.0, "PCTM-001": 1300.0, "IVNS-001": 420.0, "AMOX-001": 560.0, "ARTM-001": 280.0},
            },
            {
                "id": "MH-PUN-051",
                "name": "PHC Wagholi",
                "node_type": "PHC",
                "district": "Pune",
                "lat": 18.5808,
                "lon": 73.9790,
                "beds_total": 18,
                "beds_occupied": 12,
                "doctors_count": 2,
                "inventory": {"ORS-001": 890.0, "PCTM-001": 950.0, "IVNS-001": 310.0, "AMOX-001": 380.0, "ARTM-001": 170.0},
            },
            {
                "id": "MH-SAT-027",
                "name": "PHC Shirwal Central",
                "node_type": "PHC",
                "district": "Satara",
                "lat": 18.1340,
                "lon": 73.9850,
                "beds_total": 28,
                "beds_occupied": 13,
                "doctors_count": 4,
                "inventory": {"ORS-001": 2400.0, "PCTM-001": 2900.0, "IVNS-001": 1100.0, "AMOX-001": 1250.0, "ARTM-001": 520.0},
            },
            {
                "id": "MH-SOL-061",
                "name": "PHC Baramati East",
                "node_type": "PHC",
                "district": "Solapur",
                "lat": 18.1517,
                "lon": 74.5771,
                "beds_total": 26,
                "beds_occupied": 15,
                "doctors_count": 3,
                "inventory": {"ORS-001": 1400.0, "PCTM-001": 1650.0, "IVNS-001": 620.0, "AMOX-001": 700.0, "ARTM-001": 340.0},
            },
        ]

        all_nodes = warehouses + district_hospitals + phcs
        for n in all_nodes:
            self.graph.add_node(
                n["id"],
                name=n["name"],
                node_type=n["node_type"],
                district=n["district"],
                lat=n["lat"],
                lon=n["lon"],
                beds_total=n["beds_total"],
                beds_occupied=n["beds_occupied"],
                doctors_count=n["doctors_count"],
                inventory=n["inventory"],
                stress_score=0.0,
            )

        # ─── 4. Build Supply Edges (Warehouse -> All PHCs & Hospitals) ──
        wh_id = "WH-PUN-01"
        for target_node in district_hospitals + phcs:
            tid = target_node["id"]
            dist_km = haversine_km(
                self.graph.nodes[wh_id]["lat"], self.graph.nodes[wh_id]["lon"],
                self.graph.nodes[tid]["lat"], self.graph.nodes[tid]["lon"]
            )
            speed_kmh = 35.0  # Urban/semi-rural medical logistics speed
            eta_h = round(dist_km / speed_kmh, 1) + 1.0  # +1h loading
            self.graph.add_edge(
                wh_id,
                tid,
                edge_type="SUPPLY_ROUTE",
                distance_km=round(dist_km, 1),
                eta_hours=eta_h,
                capacity_units=15000.0,
                stress_pct=15.0,
            )

        # ─── 5. Inter-PHC Redistribution Edges ───────────────────────────
        # Allow lateral redistribution between nearby facilities
        facility_nodes = phcs + district_hospitals
        for i, f1 in enumerate(facility_nodes):
            for j, f2 in enumerate(facility_nodes):
                if i != j:
                    dist = haversine_km(f1["lat"], f1["lon"], f2["lat"], f2["lon"])
                    if dist <= 90.0:  # within reach of emergency inter-facility transfer
                        eta = round(dist / 40.0, 1) + 0.5
                        self.graph.add_edge(
                            f1["id"],
                            f2["id"],
                            edge_type="SUPPLY_ROUTE",
                            distance_km=round(dist, 1),
                            eta_hours=eta,
                            capacity_units=5000.0,
                            stress_pct=10.0,
                        )

        # ─── 6. Build Patient Referral / Spillover Edges ──────────────────
        # Each PHC refers critical overflows to District Hospital
        dh_id = "DH-PUN-001"
        for p in phcs:
            pid = p["id"]
            dist_to_dh = haversine_km(
                self.graph.nodes[pid]["lat"], self.graph.nodes[pid]["lon"],
                self.graph.nodes[dh_id]["lat"], self.graph.nodes[dh_id]["lon"]
            )
            self.graph.add_edge(
                pid,
                dh_id,
                edge_type="REFERRAL_CORRIDOR",
                distance_km=round(dist_to_dh, 1),
                eta_hours=round(dist_to_dh / 45.0, 1),
                capacity_units=50.0,  # daily patient transfer capacity
                stress_pct=25.0,
            )

        # Connect geographically closest PHCs for localized spillover
        for p1 in phcs:
            closest_neighbor = None
            min_d = float("inf")
            for p2 in phcs:
                if p1["id"] != p2["id"]:
                    d = haversine_km(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
                    if d < min_d:
                        min_d = d
                        closest_neighbor = p2["id"]
            if closest_neighbor and min_d <= 35.0:
                self.graph.add_edge(
                    p1["id"],
                    closest_neighbor,
                    edge_type="REFERRAL_CORRIDOR",
                    distance_km=round(min_d, 1),
                    eta_hours=round(min_d / 30.0, 1),
                    capacity_units=20.0,
                    stress_pct=10.0,
                )

    def calculate_node_stress(self, node_id: str, surge_factor: float = 1.0) -> float:
        """Compute normalized stress score (0-100) for a node given its current state."""
        node = self.graph.nodes[node_id]
        if node["node_type"] == "WAREHOUSE":
            return 10.0

        # Bed stress (0-40 pts)
        total_beds = max(node.get("beds_total", 1), 1)
        occ_beds = node.get("beds_occupied", 0)
        bed_ratio = min(occ_beds / total_beds, 2.0)
        bed_pts = min(bed_ratio * 40.0, 40.0)

        # Stockout stress (0-40 pts)
        inv = node.get("inventory", {})
        ors_stock = inv.get("ORS-001", 1000.0)
        pctm_stock = inv.get("PCTM-001", 1000.0)
        # Daily baseline consumption roughly 65 units
        stock_burn_days = (ors_stock + pctm_stock) / max(2 * 65.0 * surge_factor, 1.0)
        if stock_burn_days < 3.0:
            inv_pts = 40.0
        elif stock_burn_days < 7.0:
            inv_pts = 25.0
        elif stock_burn_days < 14.0:
            inv_pts = 10.0
        else:
            inv_pts = 2.0

        # Staff stress (0-20 pts)
        docs = max(node.get("doctors_count", 1), 1)
        pts_per_doc = (occ_beds * 1.5) / docs
        staff_pts = min((pts_per_doc / 15.0) * 20.0, 20.0)

        stress = round(min(bed_pts + inv_pts + staff_pts, 100.0), 1)
        node["stress_score"] = stress
        return stress

    def get_snapshot(self) -> NetworkGraphResponse:
        """Export serializable network graph representation."""
        nodes_out: List[DigitalTwinNode] = []
        edges_out: List[DigitalTwinEdge] = []
        stress_vals = []
        critical = []

        for nid, data in self.graph.nodes(data=True):
            stress = self.calculate_node_stress(nid)
            stress_vals.append(stress)
            is_critical = stress >= 75.0 or (data.get("beds_occupied", 0) >= data.get("beds_total", 1))
            if is_critical and data.get("node_type") != "WAREHOUSE":
                critical.append(nid)

            nodes_out.append(
                DigitalTwinNode(
                    id=nid,
                    name=data["name"],
                    node_type=data["node_type"],
                    district=data["district"],
                    latitude=data["lat"],
                    longitude=data["lon"],
                    beds_total=data["beds_total"],
                    beds_occupied=data["beds_occupied"],
                    doctors_count=data["doctors_count"],
                    inventory=data.get("inventory", {}),
                    stress_score=stress,
                    is_bottleneck=is_critical,
                )
            )

        for u, v, data in self.graph.edges(data=True):
            edges_out.append(
                DigitalTwinEdge(
                    source=u,
                    target=v,
                    edge_type=data.get("edge_type", "SUPPLY_ROUTE"),
                    distance_km=data.get("distance_km", 0.0),
                    eta_hours=data.get("eta_hours", 1.0),
                    capacity_units=data.get("capacity_units", 5000.0),
                    stress_pct=data.get("stress_pct", 10.0),
                )
            )

        avg_stress = round(sum(stress_vals) / max(len(stress_vals), 1), 1)

        return NetworkGraphResponse(
            nodes=nodes_out,
            edges=edges_out,
            total_facilities=len(nodes_out),
            avg_network_stress=avg_stress,
            critical_nodes=critical,
        )

    def find_nearest_referral_hub(self, source_id: str) -> Optional[str]:
        """Find the nearest higher-capacity hospital or PHC with available bed capacity."""
        if source_id not in self.graph:
            return None
        candidates = []
        src_data = self.graph.nodes[source_id]
        for nid, data in self.graph.nodes(data=True):
            if nid == source_id or data.get("node_type") == "WAREHOUSE":
                continue
            # Capacity check
            avail_beds = data.get("beds_total", 0) - data.get("beds_occupied", 0)
            if avail_beds > 0:
                dist = haversine_km(src_data["lat"], src_data["lon"], data["lat"], data["lon"])
                candidates.append((dist, nid))

        if not candidates:
            # Fallback to district hospital even if strained
            return "DH-PUN-001"
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]


# Singleton instance
digital_twin = HealthcareDigitalTwin(region="Pune")
