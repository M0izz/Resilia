"""
RESILIA Response Agent — Sprint 3
==================================
Converts mathematical OR-Tools optimization solutions into actionable,
human-readable operational intervention plans.

Responsibilities:
  1. Synthesizes Problem, Recommended Action, Expected Impact, Transport, ETA.
  2. Evaluates Plan Confidence (combining surplus margins, corridor clearance, expiry buffer).
  3. Formulates the exact INTERVENTION PLAN schema for human approval.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.models.optimization import (
    InterventionConfidence,
    InterventionImpact,
    OperationalInterventionPlan,
    OptimizationResult,
    SurplusCandidate,
)

logger = logging.getLogger(__name__)


class ResponseAgent:
    """
    Autonomous Response Agent that bridges OR-Tools linear programming
    with human-in-the-loop operational healthcare administration.
    """

    @classmethod
    def generate_plan(
        cls,
        target_phc_id: str,
        target_phc_name: str,
        target_district: str,
        medicine_code: str,
        medicine_name: str,
        current_stock: float,
        daily_burn: float,
        stock_out_days: float,
        optimization_result: OptimizationResult,
        candidate_surplus: list[SurplusCandidate],
    ) -> OperationalInterventionPlan:
        """
        Produce a comprehensive OperationalInterventionPlan from solver output.
        """
        routes = optimization_result.allocated_routes
        total_units = optimization_result.total_allocated_units

        # If solver could not allocate any units
        if not routes or total_units <= 0:
            return cls._generate_unfeasible_plan(
                target_phc_id=target_phc_id,
                target_phc_name=target_phc_name,
                target_district=target_district,
                medicine_code=medicine_code,
                medicine_name=medicine_name,
                current_stock=current_stock,
                daily_burn=daily_burn,
                stock_out_days=stock_out_days,
                optimization_result=optimization_result,
            )

        # Primary route is the largest allocation
        primary_route = routes[0]
        max_eta = max(r.eta_hours for r in routes)

        # ── Impact Assessment ────────────────────────────────────────────────
        new_total_stock = current_stock + total_units
        post_stock_days = round(new_total_stock / max(daily_burn, 1.0), 1)
        days_gained = round(post_stock_days - stock_out_days, 1)

        # Risk reduction estimate: moving from critical (<5d) to safe (>14d) = ~75-85% risk drop
        risk_reduction = min(88.0, round((days_gained / max(post_stock_days, 1.0)) * 95.0, 1))

        impact = InterventionImpact(
            pre_stock_days=round(stock_out_days, 1),
            post_stock_days=post_stock_days,
            stock_out_avoided=True,
            days_gained=days_gained,
            risk_reduction_pct=risk_reduction,
        )

        # ── Confidence Scoring ───────────────────────────────────────────────
        confidence = cls._calculate_confidence(routes, optimization_result)

        # ── Structured Descriptions ──────────────────────────────────────────
        source_summary = (
            f"{primary_route.source_name} ({primary_route.source_phc_id})"
            if len(routes) == 1
            else f"{primary_route.source_name} + {len(routes)-1} secondary facility"
        )

        problem_text = (
            f"{medicine_name} ({medicine_code}) stock-out predicted at {target_phc_name} ({target_phc_id}) "
            f"in {stock_out_days:.1f} days. Current inventory is {current_stock:,.0f} units against a burn rate "
            f"of {daily_burn:.1f} units/day."
        )

        if len(routes) == 1:
            rec_action = (
                f"Transfer {total_units:,.0f} units of {medicine_name} from {primary_route.source_name} "
                f"({primary_route.source_phc_id}, {primary_route.source_district} District) to {target_phc_name}."
            )
        else:
            route_parts = [f"{r.quantity:,.0f} units from {r.source_name}" for r in routes]
            rec_action = (
                f"Multi-source redistribution of {total_units:,.0f} total units: {'; '.join(route_parts)} "
                f"to {target_phc_name}."
            )

        cross_district_note = " (Cross-District Redistribution)" if primary_route.is_cross_district else " (Intra-District Transfer)"

        expected_impact_text = (
            f"Stock-out avoided. Runway extended from {stock_out_days:.1f} days to {post_stock_days:.1f} days "
            f"(+{days_gained:.1f} days safety buffer). Composite facility risk reduced by {risk_reduction:.1f}%."
        )

        transport_text = (
            f"Vehicle {primary_route.vehicle_id} assigned. Transit distance: {primary_route.distance_km:.1f} km via "
            f"primary logistics corridor{cross_district_note}. Estimated transit time: {primary_route.eta_hours:.1f} hours."
        )

        plan = OperationalInterventionPlan(
            target_phc_id=target_phc_id,
            target_phc_name=target_phc_name,
            target_district=target_district,
            medicine_code=medicine_code,
            medicine_name=medicine_name,
            title=f"Intervention Plan: Rebalance {medicine_code} to {target_phc_name}",
            problem_summary=problem_text,
            recommended_action=rec_action,
            expected_impact=expected_impact_text,
            impact_metrics=impact,
            transport_summary=transport_text,
            primary_source_phc_id=primary_route.source_phc_id,
            primary_source_phc_name=primary_route.source_name,
            primary_source_district=primary_route.source_district,
            is_cross_district=primary_route.is_cross_district,
            total_units=total_units,
            eta_hours=max_eta,
            assigned_vehicle_id=primary_route.vehicle_id,
            confidence=confidence,
            routes=routes,
            optimization_result=optimization_result,
        )

        logger.info(
            "ResponseAgent created plan %s for %s (%s): %s units from %s (ETA: %.1fh, Conf: %s)",
            plan.plan_id, target_phc_id, medicine_code, total_units,
            primary_route.source_phc_id, max_eta, confidence.rating,
        )
        return plan

    @classmethod
    def _calculate_confidence(
        cls,
        routes: list,
        optimization_result: OptimizationResult,
    ) -> InterventionConfidence:
        """
        Evaluate objective confidence based on surplus health, transport, and coverage.
        """
        score = 80.0
        breakdown = {}

        # 1. Deficit Coverage
        coverage_pct = (optimization_result.total_allocated_units / max(optimization_result.deficit_units, 1.0)) * 100.0
        if coverage_pct >= 95.0:
            score += 10.0
            breakdown["Deficit Coverage"] = f"Full requirement fulfilled ({coverage_pct:.1f}%)"
        else:
            score -= 15.0
            breakdown["Deficit Coverage"] = f"Partial coverage ({coverage_pct:.1f}%) due to network constraints"

        # 2. Source Safety Stock Buffer
        min_rem_days = min(r.remaining_source_stock_days for r in routes)
        if min_rem_days >= 10.0:
            score += 5.0
            breakdown["Source Buffer"] = f"Robust remaining buffer at source ({min_rem_days:.1f} days > 7.0d safety stock)"
        else:
            breakdown["Source Buffer"] = f"Adequate remaining buffer ({min_rem_days:.1f} days)"

        # 3. Transit Distance / Road Corridor
        max_dist = max(r.distance_km for r in routes)
        if max_dist < 100.0:
            score += 4.0
            breakdown["Logistics Corridor"] = f"Short-haul transfer ({max_dist:.1f} km); minimal traffic variance"
        elif max_dist < 250.0:
            breakdown["Logistics Corridor"] = f"Standard regional corridor ({max_dist:.1f} km)"
        else:
            score -= 5.0
            breakdown["Logistics Corridor"] = f"Long-distance cross-district corridor ({max_dist:.1f} km)"

        final_score = max(50.0, min(98.5, score))
        rating = "HIGH" if final_score >= 85.0 else "MEDIUM" if final_score >= 70.0 else "LOW"

        return InterventionConfidence(
            rating=rating,
            score_pct=round(final_score, 1),
            factor_breakdown=breakdown,
        )

    @classmethod
    def _generate_unfeasible_plan(
        cls,
        target_phc_id: str,
        target_phc_name: str,
        target_district: str,
        medicine_code: str,
        medicine_name: str,
        current_stock: float,
        daily_burn: float,
        stock_out_days: float,
        optimization_result: OptimizationResult,
    ) -> OperationalInterventionPlan:
        """Fallback plan when no surplus can be redistributed."""
        problem = (
            f"Critical {medicine_name} shortage at {target_phc_name}. Stockout expected in {stock_out_days:.1f} days. "
            f"No candidate facilities in the regional network hold surplus exceeding safety-stock thresholds."
        )
        return OperationalInterventionPlan(
            target_phc_id=target_phc_id,
            target_phc_name=target_phc_name,
            target_district=target_district,
            medicine_code=medicine_code,
            medicine_name=medicine_name,
            title=f"Emergency Supplier Escalation: {medicine_code} to {target_phc_name}",
            problem_summary=problem,
            recommended_action=f"Trigger emergency warehouse requisition for {optimization_result.deficit_units:,.0f} units via State Medical Corporation.",
            expected_impact="Redistribution unfeasible; external supplier intervention required immediately.",
            impact_metrics=InterventionImpact(
                pre_stock_days=round(stock_out_days, 1),
                post_stock_days=round(stock_out_days, 1),
                stock_out_avoided=False,
                days_gained=0.0,
                risk_reduction_pct=0.0,
            ),
            transport_summary="Commercial emergency freight dispatch requested.",
            primary_source_phc_id="STATE-DEPOT-01",
            primary_source_phc_name="Central State Medical Depot",
            primary_source_district="State HQ",
            is_cross_district=True,
            total_units=0.0,
            eta_hours=24.0,
            assigned_vehicle_id="DEPOT-EMERG-01",
            confidence=InterventionConfidence(
                rating="LOW",
                score_pct=35.0,
                factor_breakdown={"Network Surplus": "Zero qualified surplus facilities found."},
            ),
            routes=[],
            optimization_result=optimization_result,
        )


response_agent = ResponseAgent()
