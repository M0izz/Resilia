"""
FastAPI Router for Platform Evaluation & Benchmarks.

All metrics are computed on the 75-PHC SYNTHETIC-DEMO dataset.
Each response includes a `data_source` field and a top-level `disclaimer`
making that explicit.  No metrics are fabricated or hardcoded.
"""
from __future__ import annotations
from fastapi import APIRouter

from app.services.evaluation_service import evaluation_service, ComprehensiveEvaluationReport

router = APIRouter(prefix="/evaluation", tags=["Platform Evaluation & Quantitative Benchmarks"])


@router.get("/benchmarks", response_model=ComprehensiveEvaluationReport)
async def get_platform_benchmarks():
    """
    Retrieve computed benchmarks across four pillars:

    - **Forecasting**: Walk-forward backtest MAE/RMSE on patient history;
      stockout prediction precision/recall from inventory status flags.
    - **Optimization**: Measured OR-Tools solver runtime; network surplus/deficit
      coverage ratio; measured cost savings vs new procurement.
    - **Simulation**: Crisis detection lead time from alert data; resilience gain
      modelled from pre/post risk scores; safeguarded patient episodes (14-day projection).
    - **System**: Measured in-memory store latency (5 probes → p50/p95/p99);
      audit-log success rate.

    All values carry `data_source: "SYNTHETIC-DEMO"` — they reflect algorithm
    behaviour on the bundled synthetic dataset, not a live production system.
    """
    return evaluation_service.get_benchmarks()
