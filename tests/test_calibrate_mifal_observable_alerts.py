from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def _predictions() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for split in ["validation", "test"]:
        for horizon in [1, 2]:
            for index, score in enumerate([0.10, 0.35, 0.65, 0.90]):
                actual = int(index >= 2)
                rows.append(
                    {
                        "mifal_observable_version": "mifal_observable_v0",
                        "surface": "observable_no_current_chla",
                        "source_id": "wqp",
                        "site_id": f"s{index}",
                        "origin_year_month": "2020-01" if split == "validation" else "2022-01",
                        "horizon_months": horizon,
                        "split": split,
                        "bloom_h": actual,
                        "target_risk_chla_h": float(actual),
                        "risk_interval_lo": max(0.0, score - 0.2),
                        "risk_interval_hi": min(1.0, score + 0.2),
                        "risk_conservative": score,
                        "uncertainty": 0.4,
                        "interval_confidence": 0.6,
                        "data_reliability": 0.5,
                        "confidence": 0.5,
                        "alert_class": "high" if score >= 0.5 else "watch",
                        "observation_reliability": 0.2,
                        "top_factor": "Nutrients",
                        "recommended_sampling": "TP",
                        "payload_variables": "TP,Tw",
                        "has_Tw": True,
                        "has_TP": True,
                        "has_TN": False,
                        "has_Secchi": False,
                        "has_Turb": False,
                        "has_DOb": False,
                        "has_Chl": False,
                        "has_Chl_prev": False,
                    }
                )
    return pd.DataFrame(rows)


def test_calibrate_mifal_observable_alerts_cli_uses_validation_only(tmp_path: Path) -> None:
    predictions_path = tmp_path / "predictions.csv"
    calibrator_dir = tmp_path / "calibrators"
    output_dir = tmp_path / "reports"
    _predictions().to_csv(predictions_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/calibrate_mifal_observable_alerts.py",
            "--predictions",
            str(predictions_path),
            "--calibrator-dir",
            str(calibrator_dir),
            "--output-dir",
            str(output_dir),
            "--output-name",
            "mifal_calibration_test",
            "--evaluation-splits",
            "validation",
            "--min-calibration-rows",
            "2",
            "--min-threshold-rows",
            "2",
        ],
        check=True,
    )

    thresholds_path = output_dir / "mifal_calibration_test_thresholds.csv"
    metrics_path = output_dir / "mifal_calibration_test_metrics.csv"
    calibrated_path = output_dir / "mifal_calibration_test_calibrated_predictions.csv"
    report_path = output_dir / "mifal_calibration_test_report.md"
    manifest_path = output_dir / "mifal_calibration_test_manifest.json"

    thresholds = pd.read_csv(thresholds_path)
    metrics = pd.read_csv(metrics_path)
    calibrated = pd.read_csv(calibrated_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")

    assert set(thresholds["target_event"]) == {"bloom_h"}
    assert set(thresholds["calibration_split"]) == {"validation"}
    assert set(metrics["split"]) == {"validation"}
    assert {"mifal_probability_bloom_calibrated", "mifal_predicted_bloom_h"}.issubset(calibrated.columns)
    assert len(list(calibrator_dir.glob("*.json"))) == 2
    assert manifest["status"] == "completed"
    assert manifest["mifal_calibration_version"] == "mifal_observable_alert_calibration_v0"
    assert manifest["row_counts"]["threshold_rows"] == 2
    assert "MIFAL-ED/T2 Validation Calibration Report v0" in report
    assert "selected only on the calibration split" in report
