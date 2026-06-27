from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def _panel() -> pd.DataFrame:
    rows = []
    for site_index, site_id in enumerate(["a", "b"], start=1):
        for month_index, year_month in enumerate(["2020-01", "2020-02", "2020-03"], start=1):
            chla = float(8.0 * site_index * month_index)
            rows.append(
                {
                    "source_id": "wqp",
                    "site_id": site_id,
                    "year_month": year_month,
                    "mean_temperature_C": 22.0 + month_index,
                    "mean_TP_ugL": 35.0 + 12.0 * month_index,
                    "mean_TN_ugL": 700.0 + 50.0 * month_index,
                    "mean_secchi_depth_m": 1.2 - 0.1 * month_index,
                    "mean_turbidity_NTU": 10.0 + month_index,
                    "mean_DO_mgL": 7.0 - 0.2 * month_index,
                    "mean_chlorophyll_a_ugL": chla,
                    "n_obs_temperature_C": 3,
                    "n_obs_TP_ugL": 2,
                    "n_obs_TN_ugL": 2,
                    "n_obs_secchi_depth_m": 1,
                    "n_obs_turbidity_NTU": 1,
                    "n_obs_DO_mgL": 3,
                    "n_obs_chlorophyll_a_ugL": 2,
                    "qc_ok_rate_temperature_C": 1.0,
                    "qc_ok_rate_TP_ugL": 0.9,
                    "qc_ok_rate_TN_ugL": 0.9,
                    "qc_ok_rate_secchi_depth_m": 1.0,
                    "qc_ok_rate_turbidity_NTU": 1.0,
                    "qc_ok_rate_DO_mgL": 0.9,
                    "qc_ok_rate_chlorophyll_a_ugL": 1.0,
                    "std_temperature_C": 0.5,
                    "std_TP_ugL": 3.0,
                    "std_TN_ugL": 80.0,
                    "std_secchi_depth_m": 0.1,
                    "std_turbidity_NTU": 2.0,
                    "std_DO_mgL": 0.3,
                    "std_chlorophyll_a_ugL": 1.5,
                }
            )
    return pd.DataFrame(rows)


def _splits() -> pd.DataFrame:
    rows = []
    for site_id in ["a", "b"]:
        for horizon in [1, 2]:
            for split in ["validation", "test"]:
                risk = 0.25 if site_id == "a" else 0.75
                rows.append(
                    {
                        "source_id": "wqp",
                        "site_id": site_id,
                        "origin_year_month": "2020-02",
                        "horizon_months": horizon,
                        "split": split,
                        "bloom_h": site_id == "b",
                        "target_risk_chla_h": risk,
                    }
                )
    return pd.DataFrame(rows)


def test_evaluate_mifal_observable_cli_writes_smoke_outputs(tmp_path: Path) -> None:
    panel_path = tmp_path / "panel.parquet"
    splits_path = tmp_path / "splits.parquet"
    output_dir = tmp_path / "reports"
    _panel().to_parquet(panel_path, index=False)
    _splits().to_parquet(splits_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_mifal_observable.py",
            "--panel",
            str(panel_path),
            "--splits",
            str(splits_path),
            "--surface",
            "observable_no_current_chla",
            "--horizons",
            "1,2",
            "--evaluation-splits",
            "validation,test",
            "--max-rows-per-split",
            "10",
            "--include-voi",
            "--output-dir",
            str(output_dir),
            "--output-name",
            "mifal_observable_test",
        ],
        check=True,
    )

    predictions_path = output_dir / "mifal_observable_test_predictions.csv"
    metrics_path = output_dir / "mifal_observable_test_metrics.csv"
    availability_path = output_dir / "mifal_observable_test_availability.csv"
    report_path = output_dir / "mifal_observable_test_report.md"
    manifest_path = output_dir / "mifal_observable_test_manifest.json"

    predictions = pd.read_csv(predictions_path)
    metrics = pd.read_csv(metrics_path)
    availability = pd.read_csv(availability_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")

    assert len(predictions) == 8
    assert set(predictions["surface"]) == {"observable_no_current_chla"}
    assert not predictions["has_Chl"].any()
    assert predictions["has_Chl_prev"].all()
    assert predictions["risk_conservative"].between(0.0, 1.0).all()
    assert set(metrics["split"]) == {"validation", "test"}
    assert {"interval_coverage_risk", "winkler_score_risk", "f2"}.issubset(metrics.columns)
    assert {"Chl_prev", "TP", "Tw"}.issubset(set(availability["mifal_variable"]))
    assert manifest["status"] == "completed"
    assert manifest["row_counts"]["prediction_rows"] == 8
    assert "MIFAL-ED/T2 Observable Smoke Report v0" in report


def test_evaluate_mifal_observable_cli_filters_reference_rows(tmp_path: Path) -> None:
    panel_path = tmp_path / "panel.parquet"
    splits_path = tmp_path / "splits.parquet"
    reference_path = tmp_path / "reference.csv"
    output_dir = tmp_path / "reports"
    _panel().to_parquet(panel_path, index=False)
    _splits().to_parquet(splits_path, index=False)
    pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "b",
                "origin_year_month": "2020-02",
                "rollout_horizon_months": 2,
                "split": "validation",
            }
        ]
    ).to_csv(reference_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_mifal_observable.py",
            "--panel",
            str(panel_path),
            "--splits",
            str(splits_path),
            "--reference-rows",
            str(reference_path),
            "--surface",
            "observable_current_chla",
            "--horizons",
            "1,2",
            "--evaluation-splits",
            "validation",
            "--max-rows-per-split",
            "10",
            "--output-dir",
            str(output_dir),
            "--output-name",
            "mifal_observable_reference_test",
        ],
        check=True,
    )

    predictions = pd.read_csv(output_dir / "mifal_observable_reference_test_predictions.csv")
    manifest = json.loads((output_dir / "mifal_observable_reference_test_manifest.json").read_text(encoding="utf-8"))
    report = (output_dir / "mifal_observable_reference_test_report.md").read_text(encoding="utf-8")

    assert len(predictions) == 1
    assert predictions.iloc[0]["site_id"] == "b"
    assert int(predictions.iloc[0]["horizon_months"]) == 2
    assert manifest["config"]["reference_rows"] == str(reference_path)
    assert "Reference rows" in report
