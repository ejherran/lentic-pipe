from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.experiments.apply_refined_model import apply_selection, evaluate_current_predictions, load_selection


def _synthetic_refined_scores() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_id": ["A", "A", "B", "B"],
            "site_id": ["s1", "s2", "s3", "s4"],
            "origin_year_month": ["2020-01", "2020-01", "2020-01", "2020-01"],
            "horizon_months": [1, 1, 2, 2],
            "split": ["test", "test", "test", "test"],
            "bloom_h": [0, 1, 0, 1],
            "target_risk_chla_h": [0.0, 1.0, 0.0, 1.0],
            "baseline_calibrated": [0.2, 0.7, 0.4, 0.8],
            "blend_irc1_w0p25": [0.1, 0.9, 0.3, 0.7],
            "source_selector": [0.4, 0.6, 0.2, 0.9],
            "full_evidence": [0.5, 0.8, 0.4, 0.9],
        }
    )


def _synthetic_selection() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "horizon_months": [1, 2],
            "score_name": ["blend_irc1_w0p25", "source_selector"],
            "selected_threshold": [0.5, 0.6],
            "selection_policy": ["validation policy", "validation policy"],
        }
    )


def test_apply_selection_uses_frozen_horizon_scores() -> None:
    refined_scores = _synthetic_refined_scores()
    selection = _synthetic_selection()
    source_selection = pd.DataFrame(
        {
            "source_id": ["A", "B"],
            "horizon_months": [1, 2],
            "selected_score": ["blend_irc1_w0p25", "source_selector"],
        }
    )

    predictions = apply_selection(refined_scores, selection, source_selection)

    assert predictions["probability_bloom_h"].tolist() == [0.1, 0.9, 0.2, 0.9]
    assert predictions["predicted_bloom_h"].tolist() == [False, True, False, True]
    assert predictions["current_model_score_name"].tolist() == [
        "blend_irc1_w0p25",
        "blend_irc1_w0p25",
        "source_selector",
        "source_selector",
    ]
    assert "source_selector_score_name" in predictions.columns


def test_evaluate_current_predictions_reports_metrics() -> None:
    predictions = apply_selection(_synthetic_refined_scores(), _synthetic_selection())
    metrics = evaluate_current_predictions(predictions)
    all_test = metrics[(metrics["source_id"] == "all") & (metrics["split"] == "test")]

    assert len(all_test) == 2
    assert all_test["pr_auc"].notna().all()
    assert all_test["brier"].notna().all()


def test_apply_refined_model_cli_writes_signed_outputs(tmp_path: Path) -> None:
    refined_scores_path = tmp_path / "refined_scores.parquet"
    selection_path = tmp_path / "selection.csv"
    source_selection_path = tmp_path / "source_selection.csv"
    refined_manifest_path = tmp_path / "refined_manifest.json"
    predictions_path = tmp_path / "current_predictions.parquet"
    metrics_path = tmp_path / "current_metrics.csv"
    report_path = tmp_path / "current_report.md"
    registry_path = tmp_path / "current_registry.json"
    manifest_path = tmp_path / "current_manifest.json"

    _synthetic_refined_scores().to_parquet(refined_scores_path, index=False)
    _synthetic_selection().to_csv(selection_path, index=False)
    pd.DataFrame(
        {
            "source_id": ["A", "B", "C"],
            "horizon_months": [1, 2, 2],
            "selected_score": ["blend_irc1_w0p25", "source_selector", "source_selector"],
            "validation_pr_auc": [1.0, 1.0, float("nan")],
        }
    ).to_csv(source_selection_path, index=False)
    refined_manifest_path.write_text('{"model_family": "refined_expert_fuzzy_ensemble_v0"}\n', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "src/experiments/apply_refined_model.py",
            "--refined-scores",
            str(refined_scores_path),
            "--selection",
            str(selection_path),
            "--source-selection",
            str(source_selection_path),
            "--refined-manifest",
            str(refined_manifest_path),
            "--predictions",
            str(predictions_path),
            "--metrics",
            str(metrics_path),
            "--report",
            str(report_path),
            "--registry",
            str(registry_path),
            "--manifest",
            str(manifest_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "wrote" in result.stdout
    for path in [predictions_path, metrics_path, report_path, registry_path, manifest_path]:
        assert path.exists()
        assert path.stat().st_size > 0
    loaded_selection = load_selection(selection_path)
    assert loaded_selection["horizon_months"].tolist() == [1, 2]
    predictions = pd.read_parquet(predictions_path)
    assert predictions["model_version"].eq("current_refined_fuzzy_v0").all()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert registry["model_version"] == "current_refined_fuzzy_v0"
    assert "NaN" not in registry_path.read_text(encoding="utf-8")
    assert manifest["row_counts"]["prediction_rows"] == 4
    assert all(len(record["sha256"]) == 64 for record in manifest["outputs"])
