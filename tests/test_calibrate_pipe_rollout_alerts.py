from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def _backtest_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for split in ["validation", "test"]:
        for horizon in [1, 2]:
            for index, score in enumerate([0.10, 0.35, 0.65, 0.90]):
                actual = int(index >= 2)
                rows.append(
                    {
                        "source_id": "wqp",
                        "site_id": f"s{index}",
                        "split": split,
                        "origin_year_month": "2022-01" if split == "test" else "2020-01",
                        "forecast_year_month": "2022-02" if split == "test" else "2020-02",
                        "rollout_horizon_months": horizon,
                        "samples": 8,
                        "alert_irc_threshold": 0.5,
                        "alert_probability_irc": score,
                        "alert_probability_threshold": 0.5,
                        "predicted_alert_h": score >= 0.5,
                        "actual_irc": score,
                        "actual_irc_alert": actual,
                        "irc_mean": score,
                        "irc_p05": max(0.0, score - 0.1),
                        "irc_p50": score,
                        "irc_p95": min(1.0, score + 0.1),
                        "irc_abs_error": 0.0,
                        "origin_irc1_rollout_basis": score,
                        "bloom_target_year_month": "2022-02" if split == "test" else "2020-02",
                        "bloom_h": actual,
                        "target_risk_chla_h": float(actual),
                        "probability_bloom_mean": score,
                        "probability_bloom_p05": max(0.0, score - 0.1),
                        "probability_bloom_p50": score,
                        "probability_bloom_p95": min(1.0, score + 0.1),
                        "bloom_probability_threshold_h": 0.5,
                        "predicted_bloom_alert_h": score >= 0.5,
                    }
                )
    return pd.DataFrame(rows)


def test_calibrate_pipe_rollout_alerts_cli_writes_thresholds_and_metrics(tmp_path: Path) -> None:
    backtest_rows_path = tmp_path / "backtest_rows.parquet"
    calibrator_dir = tmp_path / "calibrators"
    thresholds_path = tmp_path / "thresholds.csv"
    metrics_path = tmp_path / "metrics.csv"
    calibrated_rows_path = tmp_path / "calibrated_rows.parquet"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"
    _backtest_rows().to_parquet(backtest_rows_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/calibrate_pipe_rollout_alerts.py",
            "--backtest-rows",
            str(backtest_rows_path),
            "--calibrator-dir",
            str(calibrator_dir),
            "--thresholds",
            str(thresholds_path),
            "--metrics",
            str(metrics_path),
            "--calibrated-rows",
            str(calibrated_rows_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--evaluation-splits",
            "validation,test",
            "--min-calibration-rows",
            "2",
            "--min-threshold-rows",
            "2",
            "--min-recall",
            "0.5",
        ],
        check=True,
    )

    thresholds = pd.read_csv(thresholds_path)
    metrics = pd.read_csv(metrics_path)
    calibrated = pd.read_parquet(calibrated_rows_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert set(thresholds["target_event"]) == {"irc_alert", "bloom_h"}
    assert set(metrics["split"]) == {"validation", "test"}
    assert {"rollout_probability_bloom_calibrated", "rollout_predicted_bloom_h"}.issubset(calibrated.columns)
    assert len(list(calibrator_dir.glob("*.joblib"))) == 2
    assert manifest["status"] == "completed"
    assert manifest["row_counts"]["threshold_rows"] == 4
    assert manifest["script"]["path"] == "src/experiments/calibrate_pipe_rollout_alerts.py"
    assert "Rollout Alert Calibration Report" in report_path.read_text(encoding="utf-8")
