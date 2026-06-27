from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd


def _panel() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for site in ["a", "b"]:
        for month in ["2020-01", "2020-02", "2020-03", "2020-04"]:
            rows.append(
                {
                    "source_id": "wqp",
                    "site_id": site,
                    "year_month": month,
                    "mean_temperature_C": 22.0,
                    "mean_TP_ugL": 45.0 if site == "a" else 12.0,
                    "mean_TN_ugL": 900.0 if site == "a" else 240.0,
                    "mean_secchi_depth_m": 0.8 if site == "a" else 2.5,
                    "mean_turbidity_NTU": 18.0 if site == "a" else 3.0,
                    "mean_DO_mgL": 7.0,
                    "mean_chlorophyll_a_ugL": 48.0 if site == "a" else 4.0,
                    "n_obs_temperature_C": 2,
                    "n_obs_TP_ugL": 2,
                    "n_obs_TN_ugL": 2,
                    "n_obs_secchi_depth_m": 2,
                    "n_obs_turbidity_NTU": 2,
                    "n_obs_DO_mgL": 2,
                    "n_obs_chlorophyll_a_ugL": 2,
                    "qc_ok_rate_temperature_C": 1.0,
                    "qc_ok_rate_TP_ugL": 1.0,
                    "qc_ok_rate_TN_ugL": 1.0,
                    "qc_ok_rate_secchi_depth_m": 1.0,
                    "qc_ok_rate_turbidity_NTU": 1.0,
                    "qc_ok_rate_DO_mgL": 1.0,
                    "qc_ok_rate_chlorophyll_a_ugL": 1.0,
                    "std_temperature_C": 0.5,
                    "std_TP_ugL": 2.0,
                    "std_TN_ugL": 20.0,
                    "std_secchi_depth_m": 0.1,
                    "std_turbidity_NTU": 0.5,
                    "std_DO_mgL": 0.2,
                    "std_chlorophyll_a_ugL": 2.0,
                }
            )
    return pd.DataFrame(rows)


def _splits() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for split, origin in [("validation", "2020-02"), ("test", "2020-03")]:
        for site in ["a", "b"]:
            bloom = int(site == "a")
            for horizon in [1, 2, 3]:
                rows.append(
                    {
                        "source_id": "wqp",
                        "site_id": site,
                        "origin_year_month": origin,
                        "horizon_months": horizon,
                        "split": split,
                        "bloom_h": bloom,
                        "target_risk_chla_h": float(bloom),
                    }
                )
    return pd.DataFrame(rows)


def _config() -> str:
    return textwrap.dedent(
        """
        schema_version: 1
        randomization:
          seeds:
            - 7
        scenario_sets:
          mifal_test:
            - control_observed
            - ablate_nutrients
            - site_retention_50
        scenarios:
          - scenario_id: control_observed
            family: control
            tier: core
            operations: []
          - scenario_id: ablate_nutrients
            family: feature_family_ablation
            tier: core
            operations:
              - type: set_variables_missing
                variable_group: nutrients
          - scenario_id: site_retention_50
            family: site_retention
            tier: core
            operations:
              - type: stratified_site_retention
                retain_fraction: 0.50
        """
    ).strip()


def test_mifal_controlled_degradation_cli_writes_outputs(tmp_path: Path) -> None:
    config_path = tmp_path / "degradation.yaml"
    panel_path = tmp_path / "panel.parquet"
    splits_path = tmp_path / "splits.parquet"
    thresholds_path = tmp_path / "thresholds.csv"
    calibrator_dir = tmp_path / "calibrators"
    output_dir = tmp_path / "reports"
    calibrator_dir.mkdir()

    config_path.write_text(_config(), encoding="utf-8")
    _panel().to_parquet(panel_path, index=False)
    _splits().to_parquet(splits_path, index=False)
    threshold_rows: list[dict[str, object]] = []
    for horizon in [1, 2, 3]:
        calibrator_path = calibrator_dir / f"observable_current_chla_h{horizon}_bloom_h_calibrator.json"
        calibrator_path.write_text(
            json.dumps(
                {
                    "mifal_calibration_version": "mifal_observable_alert_calibration_v0",
                    "surface": "observable_current_chla",
                    "target_event": "bloom_h",
                    "horizon_months": horizon,
                    "score_column": "risk_conservative",
                    "calibration_split": "validation",
                    "training_rows": 2,
                    "positive_rows": 1,
                    "method": "isotonic",
                    "x_thresholds": [0.0, 1.0],
                    "y_thresholds": [0.0, 1.0],
                }
            ),
            encoding="utf-8",
        )
        threshold_rows.append(
            {
                "mifal_calibration_version": "mifal_observable_alert_calibration_v0",
                "surface": "observable_current_chla",
                "target_event": "bloom_h",
                "horizon_months": horizon,
                "calibration_split": "validation",
                "selection_objective": "f_beta",
                "fbeta_beta": 2.0,
                "min_recall": 0.0,
                "min_precision": 0.0,
                "score_column": "mifal_probability_bloom_calibrated",
                "selected_threshold": 0.5,
                "constraint_satisfied": True,
                "calibration_rows": 2,
                "calibration_positive_rows": 1,
                "calibration_positive_rate": 0.5,
                "calibration_predicted_positive_rows": 1,
                "calibration_predicted_positive_rate": 0.5,
                "calibration_precision": 1.0,
                "calibration_recall": 1.0,
                "calibration_fbeta": 1.0,
                "calibration_macro_f1": 1.0,
                "calibration_mcc": 1.0,
                "calibrator_path": calibrator_path.as_posix(),
                "calibrator_method": "isotonic",
            }
        )
    pd.DataFrame(threshold_rows).to_csv(thresholds_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_mifal_controlled_degradation.py",
            "--config",
            str(config_path),
            "--panel",
            str(panel_path),
            "--splits",
            str(splits_path),
            "--reference-rows",
            "none",
            "--thresholds",
            str(thresholds_path),
            "--scenario-set",
            "mifal_test",
            "--evaluation-splits",
            "validation,test",
            "--output-dir",
            str(output_dir),
            "--output-name",
            "mifal_test",
            "--min-rows",
            "1",
            "--max-examples-per-run",
            "2",
        ],
        check=True,
    )

    metrics = pd.read_csv(output_dir / "mifal_test_metrics.csv")
    summary = pd.read_csv(output_dir / "mifal_test_summary.csv")
    availability = pd.read_csv(output_dir / "mifal_test_availability.csv")
    manifest = json.loads((output_dir / "mifal_test_manifest.json").read_text(encoding="utf-8"))

    assert set(summary["scenario_id"]) == {"control_observed", "ablate_nutrients", "site_retention_50"}
    assert set(summary["scenario_status"]) == {"evaluated"}
    assert set(metrics["scenario_id"]) == {"control_observed", "ablate_nutrients", "site_retention_50"}
    assert set(metrics["score_recomputed"]) == {True}
    assert {"delta_fbeta_vs_control", "interval_coverage_risk", "absolute_calibration_bias"}.issubset(metrics.columns)
    assert not availability.empty
    assert manifest["status"] == "completed"
    assert manifest["row_counts"]["summary_rows"] == 3
