from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def _calibrated_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for split in ["validation", "test"]:
        for score in [0.05, 0.20, 0.45, 0.70, 0.90]:
            actual = int(score >= 0.45)
            rows.append(
                {
                    "source_id": "wqp",
                    "site_id": f"s{score}",
                    "split": split,
                    "origin_year_month": "2020-01",
                    "forecast_year_month": "2020-02",
                    "rollout_horizon_months": 1,
                    "alert_probability_irc": score,
                    "alert_probability_threshold": 0.5,
                    "actual_irc_alert": actual,
                    "probability_bloom_mean": score,
                    "bloom_probability_threshold_h": 0.5,
                    "bloom_h": actual,
                    "rollout_probability_bloom_calibrated": score,
                }
            )
        rows.append(
            {
                "source_id": "wqp",
                "site_id": f"missing-bloom-{split}",
                "split": split,
                "origin_year_month": "2020-01",
                "forecast_year_month": "2020-02",
                "rollout_horizon_months": 1,
                "alert_probability_irc": 0.95,
                "alert_probability_threshold": 0.5,
                "actual_irc_alert": 1,
                "probability_bloom_mean": 0.95,
                "bloom_probability_threshold_h": 0.5,
                "bloom_h": None,
                "rollout_probability_bloom_calibrated": 0.95,
            }
        )
    return pd.DataFrame(rows)


def test_compare_pipe_rollout_alert_policies_cli_writes_policy_frontier(tmp_path: Path) -> None:
    calibrated_rows_path = tmp_path / "calibrated_rows.parquet"
    thresholds_path = tmp_path / "thresholds.csv"
    metrics_path = tmp_path / "metrics.csv"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"
    _calibrated_rows().to_parquet(calibrated_rows_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/compare_pipe_rollout_alert_policies.py",
            "--calibrated-rows",
            str(calibrated_rows_path),
            "--thresholds",
            str(thresholds_path),
            "--metrics",
            str(metrics_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--selection-objectives",
            "fixed,f1,mcc,closest_pr",
            "--min-threshold-rows",
            "2",
        ],
        check=True,
    )

    thresholds = pd.read_csv(thresholds_path)
    metrics = pd.read_csv(metrics_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert set(thresholds["target_event"]) == {"irc_alert", "bloom_h"}
    assert set(thresholds["policy_name"]) == {"fixed", "f1", "mcc", "closest_pr"}
    assert set(metrics["split"]) == {"validation", "test"}
    assert {"mcc", "f1", "balanced_accuracy", "pr_distance"}.issubset(metrics.columns)
    test_bloom = metrics[(metrics["target_event"] == "bloom_h") & (metrics["split"] == "test")]
    test_irc = metrics[(metrics["target_event"] == "irc_alert") & (metrics["split"] == "test")]
    assert set(test_bloom["rows"]) == {5}
    assert set(test_irc["rows"]) == {6}
    assert manifest["status"] == "completed"
    assert manifest["row_counts"]["threshold_rows"] == 8
    assert manifest["script"]["path"] == "src/experiments/compare_pipe_rollout_alert_policies.py"
    assert "Policy Frontier Report" in report_path.read_text(encoding="utf-8")
