from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.experiments.audit_current_model import (
    build_calibration_bins,
    build_confusion_by_group,
    build_error_examples,
    build_lift_table,
)


def _synthetic_predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "model_version": ["current_refined_fuzzy_v0"] * 8,
            "source_id": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "site_id": [f"s{i}" for i in range(8)],
            "origin_year_month": ["2020-01"] * 8,
            "horizon_months": [1, 1, 1, 1, 2, 2, 2, 2],
            "split": ["test", "test", "validation", "validation", "test", "test", "validation", "validation"],
            "bloom_h": [0, 1, 0, 1, 0, 1, 0, 1],
            "target_risk_chla_h": [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
            "probability_bloom_h": [0.2, 0.8, 0.1, 0.7, 0.9, 0.4, 0.3, 0.8],
            "threshold_bloom_h": [0.5] * 8,
            "predicted_bloom_h": [False, True, False, True, True, False, False, True],
            "current_model_score_name": ["score"] * 8,
            "source_selector_score_name": ["score"] * 8,
            "full_evidence": [0.1, 0.9, 0.2, 0.8, 0.4, 0.7, 0.5, 1.0],
            "exogenous_evidence": [0.0, 0.8, 0.3, 0.6, 0.2, 0.9, 0.5, 0.7],
            "evidence_N": [0.1] * 8,
            "evidence_F": [0.2] * 8,
            "evidence_T": [0.3] * 8,
            "evidence_T_no_chla": [0.4] * 8,
        }
    )


def test_audit_tables_have_expected_rows() -> None:
    predictions = _synthetic_predictions()

    calibration = build_calibration_bins(predictions, bins=5)
    lift = build_lift_table(predictions, deciles=2)
    confusion = build_confusion_by_group(predictions)
    errors = build_error_examples(predictions, examples_per_group=2)

    assert {"mean_pred_probability", "observed_bloom_rate", "abs_calibration_error"}.issubset(calibration.columns)
    assert calibration["bin"].between(0, 4).all()
    assert {"lift", "capture_rate", "cumulative_capture_rate"}.issubset(lift.columns)
    assert set(confusion["group_type"]).issuperset({"overall", "source", "full_evidence_band", "exogenous_evidence_band"})
    assert set(errors["error_type"]) == {"false_negative", "false_positive"}


def test_audit_current_model_cli_writes_signed_outputs(tmp_path: Path) -> None:
    predictions_path = tmp_path / "current_predictions.parquet"
    metrics_path = tmp_path / "current_metrics.csv"
    registry_path = tmp_path / "registry.json"
    current_manifest_path = tmp_path / "current_manifest.json"
    report_path = tmp_path / "audit.md"
    calibration_path = tmp_path / "calibration.csv"
    lift_path = tmp_path / "lift.csv"
    confusion_path = tmp_path / "confusion.csv"
    errors_path = tmp_path / "errors.csv"
    manifest_path = tmp_path / "audit_manifest.json"

    predictions = _synthetic_predictions()
    predictions.to_parquet(predictions_path, index=False)
    pd.DataFrame(
        [
            {
                "model_version": "current_refined_fuzzy_v0",
                "source_id": "all",
                "horizon_months": 1,
                "split": "test",
                "rows": 2,
                "pr_auc": 1.0,
                "roc_auc": 1.0,
                "brier": 0.04,
                "recall": 1.0,
                "macro_f1": 1.0,
            }
        ]
    ).to_csv(metrics_path, index=False)
    registry_path.write_text('{"model_version": "current_refined_fuzzy_v0"}\n', encoding="utf-8")
    current_manifest_path.write_text('{"model_version": "current_refined_fuzzy_v0"}\n', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "src/experiments/audit_current_model.py",
            "--predictions",
            str(predictions_path),
            "--metrics",
            str(metrics_path),
            "--registry",
            str(registry_path),
            "--current-manifest",
            str(current_manifest_path),
            "--report",
            str(report_path),
            "--calibration-bins",
            str(calibration_path),
            "--lift-table",
            str(lift_path),
            "--confusion",
            str(confusion_path),
            "--error-examples",
            str(errors_path),
            "--manifest",
            str(manifest_path),
            "--bins",
            "5",
            "--deciles",
            "2",
            "--examples-per-group",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "wrote" in result.stdout
    for path in [report_path, calibration_path, lift_path, confusion_path, errors_path, manifest_path]:
        assert path.exists()
        assert path.stat().st_size > 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["row_counts"]["prediction_rows"] == 8
    assert all(len(record["sha256"]) == 64 for record in manifest["outputs"])
