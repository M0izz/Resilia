"""
Run Walk-Forward Backtest and System Benchmarks.

Usage:
    python backend/scripts/run_backtest.py
"""
import sys
import os
import json

# Ensure backend root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.evaluation_service import EvaluationService

def main():
    print("=" * 60)
    print("RESILIA — Running Quantitative Walk-Forward Backtest & Benchmarks")
    print("=" * 60)

    report = EvaluationService.get_benchmarks()
    data = report.model_dump()

    print(f"\nData Source: {report.data_source}")
    print(f"Status:      {report.evaluation_status}")
    print(f"Disclaimer:  {report.disclaimer}")
    print("\n--- FORECASTING PILLAR ---")
    print(f"  MAE (patients/day):       {report.forecasting.mae_units}")
    print(f"  RMSE (patients/day):      {report.forecasting.rmse_units}")
    print(f"  Stockout Pred Accuracy:   {report.forecasting.stockout_prediction_accuracy_pct}%")
    print(f"  Precision / Recall:       {report.forecasting.precision_pct}% / {report.forecasting.recall_pct}%")
    print(f"  Evaluations Count:        {report.forecasting.test_evaluations_count}")

    print("\n--- OPTIMIZATION PILLAR ---")
    print(f"  Shortage Reduction:       {report.optimization.shortage_reduction_pct}%")
    print(f"  Mean Solver Runtime:      {report.optimization.mean_solver_runtime_ms:.2f} ms")
    print(f"  Constraint Satisfaction:  {report.optimization.constraint_satisfaction_rate_pct}%")
    print(f"  Safety Stock Violations:  {report.optimization.safety_stock_violations_count}")

    print("\n--- SIMULATION PILLAR ---")
    print(f"  Crisis Lead Time:         {report.simulation.crisis_detection_lead_time_hours} hrs")
    print(f"  Network Resilience Gain:  {report.simulation.network_resilience_gain_pct}%")
    print(f"  Safeguarded Patients:     {report.simulation.safeguarded_patient_care_episodes}")

    print("\n--- SYSTEM PERFORMANCE PILLAR ---")
    print(f"  API Latency p50 / p95:    {report.system_performance.api_latency_p50_ms} ms / {report.system_performance.api_latency_p95_ms} ms")
    print(f"  Store Query Latency:      {report.system_performance.dynamodb_query_latency_ms} ms")
    print(f"  Audit Execution Success:  {report.system_performance.agent_autonomous_execution_success_pct}%")

    print(f"\nOverall Resilience Score:   {report.overall_resilience_score} / 100.0")
    print("=" * 60)

    # Save to JSON artifact
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "data"))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "backtest_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Results persisted to: {out_path}\n")

if __name__ == "__main__":
    main()
