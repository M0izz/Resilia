"""
Unit tests for Phase 4: Calibrated Forecasting System
======================================================
Verifies:
  - FeaturePipeline lag, rolling statistics, and seasonal feature extraction.
  - Autoregressive forecast row creation.
  - ModelMetadata persistence and artifact registry.
  - Model metadata validation.
"""
from datetime import datetime, timedelta
import json
import os
import numpy as np

from app.services.forecast_features import (
    FeaturePipeline,
    ModelMetadata,
    save_model_artifact,
)


def test_feature_pipeline_feature_extraction():
    base = datetime(2026, 1, 1)
    dates = [base + timedelta(days=i) for i in range(25)]
    # Values with weekly cycle
    values = [50.0 + 10.0 * np.sin(i / 7.0 * 2 * np.pi) + (i % 7) for i in range(25)]

    X, y, feature_names = FeaturePipeline.extract_features(dates, values)

    assert len(X) == 25 - 7  # 18 samples after 7-day lag window
    assert len(y) == 18
    assert X.shape[1] == len(feature_names)
    assert "lag_1" in feature_names
    assert "lag_7" in feature_names
    assert "roll_mean_7" in feature_names
    assert "roll_std_7" in feature_names


def test_feature_pipeline_forecast_row():
    base = datetime(2026, 1, 1)
    predict_date = datetime(2026, 1, 15)
    recent_values = [45.0, 52.0, 48.0, 55.0, 50.0, 62.0, 58.0]

    row = FeaturePipeline.build_forecast_row(predict_date, base, recent_values)

    assert row.shape == (1, 13)
    # Check t_step is 14 days
    assert row[0, 0] == 14.0


def test_model_metadata_save_artifact(tmp_path):
    metadata = ModelMetadata(
        version="1.0.0",
        model_type="RidgeRegression",
        alpha=1.0,
        features_used=["t_step", "lag_1", "roll_mean_7"],
        r2_score=0.85,
        mae=4.2,
        rmse=6.1,
        coverage_90pct=0.88,
        n_samples=500,
    )

    artifact_path = save_model_artifact(None, metadata, registry_dir=str(tmp_path))
    assert os.path.exists(artifact_path)

    with open(artifact_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["version"] == "1.0.0"
    assert loaded["r2_score"] == 0.85
    assert loaded["mae"] == 4.2
    assert loaded["rmse"] == 6.1
    assert loaded["coverage_90pct"] == 0.88
