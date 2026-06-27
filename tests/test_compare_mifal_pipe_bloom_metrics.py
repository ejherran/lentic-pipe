from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def test_compare_mifal_pipe_bloom_metrics_cli_writes_comparison(tmp_path: Path) -> None:
    mifal_path = tmp_path / "mifal_metrics.csv"
    pipe_path = tmp_path / "pipe_metrics.csv"
    output_dir = tmp_path / "reports"
    pd.DataFrame(
        [
            {
                "model_name": "no_current",
                "surface": "observable_no_current_chla",
                "split": "validation",
                "horizon_months": 1,
                "rows": 10,
                "positive_rows": 2,
                "predicted_positive_rate": 0.4,
                "precision": 0.5,
                "recall": 1.0,
                "fbeta": 0.83,
                "pr_auc": 0.55,
                "brier": 0.12,
            }
        ]
    ).to_csv(mifal_path, index=False)
    pd.DataFrame(
        [
            {
                "target_event": "bloom_h",
                "split": "validation",
                "rollout_horizon_months": 1,
                "rows": 10,
                "positive_rows": 2,
                "predicted_positive_rate": 0.3,
                "precision": 0.6,
                "recall": 0.75,
                "fbeta": 0.71,
                "pr_auc": 0.65,
                "brier": 0.10,
            }
        ]
    ).to_csv(pipe_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/compare_mifal_pipe_bloom_metrics.py",
            "--mifal-metrics",
            str(mifal_path),
            "--pipe-metrics",
            str(pipe_path),
            "--output-dir",
            str(output_dir),
            "--output-name",
            "comparison_test",
        ],
        check=True,
    )

    comparison = pd.read_csv(output_dir / "comparison_test_comparison.csv")
    manifest = json.loads((output_dir / "comparison_test_manifest.json").read_text(encoding="utf-8"))
    report = (output_dir / "comparison_test_report.md").read_text(encoding="utf-8")

    assert len(comparison) == 1
    assert comparison.iloc[0]["target_event"] == "bloom_h"
    assert round(float(comparison.iloc[0]["delta_recall"]), 2) == 0.25
    assert round(float(comparison.iloc[0]["delta_pr_auc"]), 2) == -0.10
    assert manifest["status"] == "completed"
    assert manifest["comparison_version"] == "mifal_pipe_bloom_metric_comparison_v0"
    assert "MIFAL does not emit the PIPE `irc_alert` target" in report
