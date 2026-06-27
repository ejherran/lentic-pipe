from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def _panel() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "a",
                "year_month": "2020-01",
                "mean_temperature_C": 24.0,
                "mean_TP_ugL": 80.0,
                "mean_TN_ugL": 900.0,
                "mean_secchi_depth_m": 0.8,
                "mean_turbidity_NTU": 20.0,
                "mean_DO_mgL": 6.0,
                "mean_chlorophyll_a_ugL": 25.0,
            },
            {
                "source_id": "wqp",
                "site_id": "b",
                "year_month": "2020-01",
                "mean_temperature_C": np.nan,
                "mean_TP_ugL": 40.0,
                "mean_TN_ugL": np.nan,
                "mean_secchi_depth_m": 1.2,
                "mean_turbidity_NTU": np.nan,
                "mean_DO_mgL": 5.0,
                "mean_chlorophyll_a_ugL": np.nan,
            },
            {
                "source_id": "lakebed_us_cse",
                "site_id": "c",
                "year_month": "2020-01",
                "mean_temperature_C": 26.0,
                "mean_TP_ugL": 55.0,
                "mean_TN_ugL": 700.0,
                "mean_secchi_depth_m": 0.6,
                "mean_turbidity_NTU": 10.0,
                "mean_DO_mgL": 4.0,
                "mean_chlorophyll_a_ugL": 31.0,
            },
        ]
    )


def _splits() -> pd.DataFrame:
    rows = []
    for source_id, site_id, split in [("wqp", "a", "validation"), ("wqp", "b", "validation"), ("lakebed_us_cse", "c", "test")]:
        for horizon in [1, 2]:
            rows.append(
                {
                    "source_id": source_id,
                    "site_id": site_id,
                    "origin_year_month": "2020-01",
                    "horizon_months": horizon,
                    "split": split,
                    "bloom_h": horizon == 1,
                    "target_risk_chla_h": 0.5,
                }
            )
    return pd.DataFrame(rows)


def test_audit_mifal_inputs_cli_writes_reproducible_outputs(tmp_path: Path) -> None:
    panel_path = tmp_path / "panel.parquet"
    splits_path = tmp_path / "splits.parquet"
    output_dir = tmp_path / "reports"
    _panel().to_parquet(panel_path, index=False)
    _splits().to_parquet(splits_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/audit_mifal_inputs.py",
            "--panel",
            str(panel_path),
            "--splits",
            str(splits_path),
            "--horizons",
            "1,2",
            "--evaluation-splits",
            "validation,test",
            "--output-dir",
            str(output_dir),
            "--output-name",
            "mifal_input_audit_test",
        ],
        check=True,
    )

    summary_path = output_dir / "mifal_input_audit_test_summary.csv"
    by_split_path = output_dir / "mifal_input_audit_test_by_split.csv"
    report_path = output_dir / "mifal_input_audit_test_report.md"
    manifest_path = output_dir / "mifal_input_audit_test_manifest.json"

    summary = pd.read_csv(summary_path)
    by_split = pd.read_csv(by_split_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")

    coverage = dict(zip(summary["mifal_variable"], summary["coverage_rate"], strict=True))
    status = dict(zip(summary["mifal_variable"], summary["adapter_status"], strict=True))
    assert coverage["TP"] == 1.0
    assert coverage["Chl"] == 4 / 6
    assert coverage["Wind"] == 0.0
    assert status["TN"] == "unit_transform_observable"
    assert status["Wind"] == "unavailable_in_freeze"
    assert set(by_split["split"]) == {"validation", "test"}
    assert manifest["status"] == "completed"
    assert manifest["decision"]["complete_minimum_surface"] is False
    assert "MIFAL-ED/T2 Input Audit v0" in report
