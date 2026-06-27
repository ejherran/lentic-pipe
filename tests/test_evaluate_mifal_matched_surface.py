from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def _prediction_rows(surface: str, *, extra: bool = False) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for split in ["validation", "test"]:
        for horizon in [1, 2]:
            for index, score in enumerate([0.10, 0.35, 0.65, 0.90]):
                actual = int(index >= 2)
                adjusted = min(1.0, score + 0.05) if surface == "observable_current_chla" else score
                rows.append(
                    {
                        "mifal_observable_version": "mifal_observable_v0",
                        "mifal_calibration_version": "mifal_observable_alert_calibration_v0",
                        "surface": surface,
                        "source_id": "wqp",
                        "site_id": f"s{index}",
                        "origin_year_month": "2020-01" if split == "validation" else "2022-01",
                        "horizon_months": horizon,
                        "split": split,
                        "bloom_h": actual,
                        "target_risk_chla_h": float(actual),
                        "risk_interval_lo": max(0.0, adjusted - 0.2),
                        "risk_interval_hi": min(1.0, adjusted + 0.2),
                        "risk_conservative": adjusted,
                        "uncertainty": 0.4,
                        "data_reliability": 0.5,
                        "confidence": 0.5,
                        "mifal_probability_bloom_calibrated": adjusted,
                        "mifal_bloom_probability_threshold": 0.5,
                        "mifal_predicted_bloom_h": int(adjusted >= 0.5),
                    }
                )
    if extra:
        rows.append(
            {
                "mifal_observable_version": "mifal_observable_v0",
                "mifal_calibration_version": "mifal_observable_alert_calibration_v0",
                "surface": surface,
                "source_id": "wqp",
                "site_id": "extra",
                "origin_year_month": "2020-01",
                "horizon_months": 1,
                "split": "validation",
                "bloom_h": 0,
                "target_risk_chla_h": 0.0,
                "risk_interval_lo": 0.0,
                "risk_interval_hi": 0.2,
                "risk_conservative": 0.1,
                "uncertainty": 0.4,
                "data_reliability": 0.5,
                "confidence": 0.5,
                "mifal_probability_bloom_calibrated": 0.1,
                "mifal_bloom_probability_threshold": 0.5,
                "mifal_predicted_bloom_h": 0,
            }
        )
    return pd.DataFrame(rows)


def test_evaluate_mifal_matched_surface_cli_uses_exact_validation_intersection(tmp_path: Path) -> None:
    no_current_path = tmp_path / "no_current.csv"
    current_path = tmp_path / "current.csv"
    reference_path = tmp_path / "reference.csv"
    output_dir = tmp_path / "reports"
    _prediction_rows("observable_no_current_chla", extra=True).to_csv(no_current_path, index=False)
    _prediction_rows("observable_current_chla").to_csv(current_path, index=False)
    pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": f"s{index}",
                "origin_year_month": "2020-01",
                "rollout_horizon_months": horizon,
                "split": "validation",
            }
            for horizon in [1, 2]
            for index in range(4)
        ]
    ).to_csv(reference_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_mifal_matched_surface.py",
            "--prediction",
            f"no_current={no_current_path}",
            "--prediction",
            f"current={current_path}",
            "--reference-rows",
            str(reference_path),
            "--output-dir",
            str(output_dir),
            "--output-name",
            "mifal_matched_test",
            "--evaluation-splits",
            "validation",
        ],
        check=True,
    )

    matched = pd.read_csv(output_dir / "mifal_matched_test_matched_rows.csv")
    metrics = pd.read_csv(output_dir / "mifal_matched_test_metrics.csv")
    comparison = pd.read_csv(output_dir / "mifal_matched_test_comparison.csv")
    manifest = json.loads((output_dir / "mifal_matched_test_manifest.json").read_text(encoding="utf-8"))
    report = (output_dir / "mifal_matched_test_report.md").read_text(encoding="utf-8")

    assert set(matched["split"]) == {"validation"}
    assert set(matched["model_name"]) == {"no_current", "current"}
    assert "extra" not in set(matched["site_id"])
    assert manifest["status"] == "completed"
    assert manifest["mifal_matched_version"] == "mifal_observable_matched_surface_v0"
    assert manifest["row_counts"]["matched_key_rows"] == 8
    assert manifest["row_counts"]["matched_prediction_rows"] == 16
    assert set(metrics["model_name"]) == {"no_current", "current"}
    assert set(comparison["baseline_model"]) == {"no_current"}
    assert "exact intersection" in report
    assert "does not fit calibrators" in report
