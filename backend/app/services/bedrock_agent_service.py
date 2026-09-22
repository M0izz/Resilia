"""
RESILIA Bedrock Agent Service & Mathematical Guardrails — Phase 7
=================================================================
"No component gets to pretend something happened when it didn't."

Provides:
  - Input sanitization (facility names, medicine codes, clinical parameters).
  - Bedrock runtime client integration with Claude 3.5 Sonnet.
  - Transparent fallback tagging ("DETERMINISTIC_RULES (Bedrock unavailable or disabled)").
  - Strict mathematical guardrails: LLM can generate strategic narrative,
    but CANNOT override or alter OR-Tools allocations, routes, or safety stocks.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.optimization import (
    OperationalInterventionPlan,
    OptimizationResult,
)

logger = logging.getLogger(__name__)


def sanitize_input_text(text: str) -> str:
    """Sanitize freeform input text against injection and illegal characters."""
    if not text:
        return ""
    # Strip HTML tags and control characters
    clean = re.sub(r"<[^>]*>", "", text)
    clean = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", clean)
    return clean.strip()[:1000]


def enforce_numerical_guardrails(
    plan: OperationalInterventionPlan,
    solver_result: OptimizationResult,
) -> None:
    """
    Mathematical Guardrail Invariant:
    Guarantees that no narrative or external model overrides OR-Tools solver solutions.
    """
    if abs(plan.total_units - solver_result.total_allocated_units) > 1e-3:
        raise ValueError(
            f"Guardrail violation: Plan total units ({plan.total_units}) diverges from "
            f"MILP solver allocation ({solver_result.total_allocated_units})."
        )

    if len(plan.routes) != len(solver_result.allocated_routes):
        raise ValueError(
            f"Guardrail violation: Plan route count ({len(plan.routes)}) does not match "
            f"solver route count ({len(solver_result.allocated_routes)})."
        )

    for r_plan, r_solver in zip(plan.routes, solver_result.allocated_routes):
        if r_plan.source_phc_id != r_solver.source_phc_id:
            raise ValueError(f"Guardrail violation: Route source {r_plan.source_phc_id} != {r_solver.source_phc_id}.")
        if abs(r_plan.quantity - r_solver.quantity) > 1e-3:
            raise ValueError(
                f"Guardrail violation: Route quantity for {r_plan.source_phc_id} ({r_plan.quantity}) "
                f"diverges from solver ({r_solver.quantity})."
            )


class BedrockAgentService:
    """
    Amazon Bedrock Agent wrapper with strict operational guardrails and fallback transparency.
    """

    @classmethod
    def generate_narrative_explanation(
        cls,
        target_phc_name: str,
        medicine_name: str,
        total_units: float,
        solver_result: OptimizationResult,
        clinical_urgency: str = "HIGH",
    ) -> Dict[str, Any]:
        """
        Generate operational guidance via Bedrock or transparent deterministic fallback.
        """
        sanitized_phc = sanitize_input_text(target_phc_name)
        sanitized_med = sanitize_input_text(medicine_name)

        if not settings.bedrock_enabled:
            return {
                "explanation_source": "DETERMINISTIC_RULES (Bedrock unavailable or disabled)",
                "model_id": "none",
                "summary": (
                    f"Operational reallocation of {total_units:,.0f} units of {sanitized_med} to {sanitized_phc} "
                    f"cleared via OR-Tools MILP solver. Clinical urgency level: {clinical_urgency}."
                ),
                "is_fallback": True,
            }

        try:
            import boto3
            client_kwargs = {
                "region_name": settings.aws_region,
                "aws_access_key_id": settings.aws_access_key_id,
                "aws_secret_access_key": settings.aws_secret_access_key,
            }
            bedrock = boto3.client("bedrock-runtime", **client_kwargs)

            prompt = (
                f"You are the RESILIA National Healthcare Logistics Advisor.\n"
                f"A mathematical redistribution plan has been solved:\n"
                f"- Recipient: {sanitized_phc}\n"
                f"- Commodity: {sanitized_med}\n"
                f"- Total Allocated Units: {total_units:,.0f}\n"
                f"- Status: {solver_result.status}\n\n"
                f"CRITICAL CONSTRAINT: You must NEVER change or invent quantities, routes, or clinical claims.\n"
                f"Provide a 2-sentence executive summary explaining the rationale and transit priority."
            )

            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            })

            response = bedrock.invoke_model(
                modelId=settings.bedrock_model_id,
                body=body,
            )
            response_body = json.loads(response["body"].read())
            generated_text = response_body["content"][0]["text"]

            return {
                "explanation_source": f"AMAZON_BEDROCK ({settings.bedrock_model_id})",
                "model_id": settings.bedrock_model_id,
                "summary": generated_text.strip(),
                "is_fallback": False,
            }
        except Exception as exc:
            logger.warning("Bedrock invocation failed (%s) — using transparent deterministic fallback.", exc)
            return {
                "explanation_source": "DETERMINISTIC_RULES (Bedrock execution failed)",
                "model_id": settings.bedrock_model_id,
                "summary": (
                    f"Operational reallocation of {total_units:,.0f} units of {sanitized_med} to {sanitized_phc} "
                    f"cleared via OR-Tools MILP solver."
                ),
                "is_fallback": True,
                "error_detail": str(exc),
            }
