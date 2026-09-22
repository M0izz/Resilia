"""
RESILIA Walk-Forward Backtest & Quantitative Benchmarking — Phase 4
===================================================================
Executes walk-forward cross-validation using FeaturePipeline & Ridge regression:
  - Multi-step rolling evaluation over historical patient series
  - Evaluates MAE, RMSE, R², and 90% confidence interval coverage
  - Persists versioned model artifact to models/model_v1.0.0.json
  - Persists system benchmark results to app/data/backtest_results.json

Usage:
    python backend/scripts/run_backtest.py
"""
import sys
import os
import json
from datetime import datetime, timezone
import numpy as np

# Ensure backend root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.evaluation_service import EvaluationService
from app.services.forecast_features import FeaturePipeline, ModelMetadata, save_model_artifact
from app.db.dynamodb import Tables, scan_all


def run_walk_forward_backtest():
    """Execute walk-forward cross-validation across all PHC patient series."""
    from sklearn.linear_model import Ridge
    from sklearn.metrics import r2_score, mean_absolute_error, root_mean_squared_error

    patients = scan_all("resilia-patients")
    if not patients:
        print("No patient records found in persistence store.")
        return None

    # Group by PHC
    from collections import defaultdict
    phc_series = defaultdict(list)
    for p in patients:
        phc_series[p["phc_id"]].append(p)

    all_actuals = []
    all_preds = []
    all_in_ci = []

    total_folds = 0
    trained_model = None
    feature_names = []

    for phc_id, records in phc_series.items():
        sorted_records = sorted(records, key=lambda x: x["date"])
        if len(sorted_records) < 18:
            continue

        dates = [datetime.strptime(r["date"], "%Y-%m-%d") for r in sorted_records]
        values = [float(r.get("total_opd", 0)) + float(r.get("total_ipd", 0)) for r in sorted_records]

        # Walk-forward splits: train on [0 : t], test on [t : t+7]
        window_size = 14
        step_size = 7

        for t in range(window_size, len(values) - step_size + 1, step_size):
            train_dates = dates[:t]
            train_values = values[:t]
            test_dates = dates[t : t + step_size]
            test_values = values[t : t + step_size]

            X_train, y_train, feat_cols = FeaturePipeline.extract_features(train_dates, train_values)
            if len(X_train) < 5:
                continue

            feature_names = feat_cols
            model = Ridge(alpha=1.0)
            model.fit(X_train, y_train)
            trained_model = model

            # In-sample residuals for 90% confidence interval
            train_preds = model.predict(X_train)
            residuals = y_train - train_preds
            sigma = float(np.std(residuals)) if len(residuals) > 1 else 5.0
            z_90 = 1.645

            # Forecast next 7 days autoregressively
            curr_vals = list(train_values)
            for i, d in enumerate(test_dates):
                row = FeaturePipeline.build_forecast_row(d, train_dates[0], curr_vals)
                pred = float(model.predict(row)[0])
                pred = max(0.0, pred)
                curr_vals.append(pred)

                actual = test_values[i]
                all_actuals.append(actual)
                all_preds.append(pred)

                # Check if actual is within 90% CI: [pred - z*sigma, pred + z*sigma]
                in_ci = (pred - z_90 * sigma) <= actual <= (pred + z_90 * sigma)
                all_in_ci.append(in_ci)

            total_folds += 1

    if not all_actuals:
        return None

    y_true = np.array(all_actuals)
    y_pred = np.array(all_preds)

    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    r2 = float(r2_score(y_true, y_pred)) if len(y_true) > 1 else 0.0
    coverage = float(np.mean(all_in_ci)) if all_in_ci else 0.0

    metadata = ModelMetadata(
        version="1.0.0",
        model_type="RidgeRegression-Autoregressive",
        alpha=1.0,
        features_used=feature_names,
        r2_score=r2,
        mae=mae,
        rmse=rmse,
        coverage_90pct=coverage,
        n_samples=len(all_actuals),
    )

    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))
    meta_path = save_model_artifact(trained_model, metadata, registry_dir=models_dir)

    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "coverage_90pct": coverage,
        "total_test_points": len(all_actuals),
        "total_folds": total_folds,
        "model_artifact": meta_path,
        "metadata": metadata.to_dict(),
    }


def main():
    print("=" * 65)
    print("RESILIA — Running Quantitative Walk-Forward Backtest & Benchmarks")
    print("=" * 65)

    # 1. Walk-forward backtest
    print("\n--- PHASE 4: WALK-FORWARD FORECAST BACKTEST ---")
    wf_results = run_walk_forward_backtest()
    if wf_results:
        print(f"  Total Test Points:        {wf_results['total_test_points']}")
        print(f"  Folds Evaluated:          {wf_results['total_folds']}")
        print(f"  Empirical MAE:            {wf_results['mae']:.2f} patients/day")
        print(f"  Empirical RMSE:           {wf_results['rmse']:.2f} patients/day")
        print(f"  R² Score:                 {wf_results['r2']:.4f}")
        print(f"  90% CI Coverage:          {wf_results['coverage_90pct'] * 100:.1f}%")
        print(f"  Model Artifact Saved:     {wf_results['model_artifact']}")
    else:
        print("  Notice: Insufficient historical series for full walk-forward split.")

    # 2. Overall system benchmarks
    report = EvaluationService.get_benchmarks()
    data = report.model_dump()
    if wf_results:
        data["walk_forward_forecasting"] = wf_results

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
    print("=" * 65)

    # Save to JSON artifact
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "data"))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "backtest_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Results persisted to: {out_path}\n")


if __name__ == "__main__":
    main()
