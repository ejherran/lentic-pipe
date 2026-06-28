from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from src.experiments.evaluate_counterfactual_planning import NON_CAUSAL_GUARDRAIL
from src.experiments.evaluate_counterfactual_planning_v1 import objective_components


def _config_text() -> str:
    return textwrap.dedent(
        """
        schema_version: 1
        protocol:
          phase: synthetic_test
        planning_unit:
          horizons_months:
            - 1
            - 2
          selection_split: validation
          heldout_split: test
        scenario_family:
          name: raw_proxy_support_grid
          enabled: true
          scenarios:
            - scenario_id: no_action
              action_type: no_action
              relative_cost: 0.0
              operations: []
            - scenario_id: clarity_strong
              action_type: clarity_improvement
              relative_cost: 2.0
              operations:
                - variable: secchi_depth_m
                  panel_column: mean_secchi_depth_m
                  operation: multiply
                  value: 1.20
                - variable: turbidity_NTU
                  panel_column: mean_turbidity_NTU
                  operation: multiply
                  value: 0.80
        constraints:
          clip_to_plausible_range: true
          max_relative_cost:
            normal: 3.0
          historical_support:
            site_level_quantiles:
              min_observed_months: 2
              lower: 0.05
              upper: 0.95
            source_level_fallback_quantiles:
              lower: 0.01
              upper: 0.99
        objective:
          default_planning_mode: normal
          planning_modes:
            normal:
              lambda_cost: 0.05
          weights:
            irc_alert_risk_reduction: 0.6
            bloom_probability_reduction: 0.4
          lambda_uncertainty: 0.1
          lambda_support: 0.05
        """
    ).strip()


def _variables_text() -> str:
    return textwrap.dedent(
        """
        schema_version: 1
        canonical_variables:
          secchi_depth_m:
            plausible_range:
              min: 0
              max: 100
          turbidity_NTU:
            plausible_range:
              min: 0
              max: 10000
        """
    ).strip()


def _panel_rows() -> pd.DataFrame:
    rows = []
    months = ["2020-01", "2020-02", "2020-03"]
    for index, month in enumerate(months):
        rows.append(
            {
                "source_id": "wqp",
                "site_id": "site_a",
                "site_id_source": "wqp:site_a",
                "site_name": "Site A",
                "year_month": month,
                "mean_TP_ugL": 80.0 + index,
                "mean_TN_ugL": 900.0 + index * 10.0,
                "TN_TP_ratio": (900.0 + index * 10.0) / (80.0 + index),
                "mean_DO_mgL": 6.0,
                "mean_pH": 7.4,
                "mean_turbidity_NTU": 30.0 + index,
                "mean_secchi_depth_m": 0.80 + index * 0.02,
                "mean_temperature_C": 25.0,
                "mean_chlorophyll_a_ugL": 20.0,
                "risk_chla": 0.70,
                "qc_ok_rate_TP_ugL": 1.0,
                "qc_ok_rate_TN_ugL": 1.0,
                "qc_ok_rate_DO_mgL": 1.0,
                "qc_ok_rate_pH": 1.0,
                "qc_ok_rate_turbidity_NTU": 1.0,
                "qc_ok_rate_secchi_depth_m": 1.0,
                "qc_ok_rate_temperature_C": 1.0,
                "qc_ok_rate_chlorophyll_a_ugL": 1.0,
            }
        )
    for index, month in enumerate(months):
        rows.append(
            {
                "source_id": "wqp",
                "site_id": "site_b",
                "site_id_source": "wqp:site_b",
                "site_name": "Site B",
                "year_month": month,
                "mean_TP_ugL": 40.0 + index,
                "mean_TN_ugL": 650.0 + index * 10.0,
                "TN_TP_ratio": (650.0 + index * 10.0) / (40.0 + index),
                "mean_DO_mgL": 7.5,
                "mean_pH": 7.2,
                "mean_turbidity_NTU": 16.0 + index,
                "mean_secchi_depth_m": 1.10 + index * 0.02,
                "mean_temperature_C": 24.0,
                "mean_chlorophyll_a_ugL": 10.0,
                "risk_chla": 0.45,
                "qc_ok_rate_TP_ugL": 1.0,
                "qc_ok_rate_TN_ugL": 1.0,
                "qc_ok_rate_DO_mgL": 1.0,
                "qc_ok_rate_pH": 1.0,
                "qc_ok_rate_turbidity_NTU": 1.0,
                "qc_ok_rate_secchi_depth_m": 1.0,
                "qc_ok_rate_temperature_C": 1.0,
                "qc_ok_rate_chlorophyll_a_ugL": 1.0,
            }
        )
    return pd.DataFrame(rows)


def _planning_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "site_a",
                "split": "validation",
                "origin_year_month": "2020-02",
                "actual_irc_alert": 1,
                "bloom_h": 1,
            },
            {
                "source_id": "wqp",
                "site_id": "site_b",
                "split": "validation",
                "origin_year_month": "2020-02",
                "actual_irc_alert": 0,
                "bloom_h": 0,
            },
            {
                "source_id": "wqp",
                "site_id": "site_a",
                "split": "test",
                "origin_year_month": "2020-03",
                "actual_irc_alert": 1,
                "bloom_h": 1,
            },
        ]
    )


def test_objective_components_penalizes_support() -> None:
    config = {
        "objective": {
            "planning_modes": {"normal": {"lambda_cost": 0.05}},
            "weights": {"irc_alert_risk_reduction": 0.6, "bloom_probability_reduction": 0.4},
            "lambda_uncertainty": 0.10,
            "lambda_support": 0.05,
        }
    }

    components = objective_components(
        baseline_irc=0.80,
        scenario_irc=0.60,
        baseline_bloom=0.70,
        scenario_bloom=0.50,
        baseline_uncertainty=0.10,
        scenario_uncertainty=0.20,
        relative_cost=1.0,
        support_violation=1.0,
        config=config,
        planning_mode="normal",
    )

    assert components["risk_reduction_absolute"] == pytest.approx(0.20)
    assert components["support_penalty"] == pytest.approx(0.05)
    assert components["objective_value"] == pytest.approx(0.20 - 0.05 - 0.01 - 0.05)


def test_evaluate_counterfactual_planning_v1_cli_writes_support_aware_outputs(tmp_path: Path) -> None:
    config_path = tmp_path / "counterfactual_planning_v1.yaml"
    variables_path = tmp_path / "variables.yaml"
    panel_path = tmp_path / "panel.parquet"
    planning_rows_path = tmp_path / "planning_rows.parquet"
    output_dir = tmp_path / "planning"
    metrics_path = output_dir / "counterfactual_v1_test_metrics.csv"
    summary_path = output_dir / "counterfactual_v1_test_summary.csv"
    pareto_path = output_dir / "counterfactual_v1_test_pareto.csv"
    examples_path = output_dir / "counterfactual_v1_test_examples.csv"
    report_path = output_dir / "counterfactual_v1_test_report.md"
    manifest_path = output_dir / "counterfactual_v1_test_manifest.json"

    config_path.write_text(_config_text(), encoding="utf-8")
    variables_path.write_text(_variables_text(), encoding="utf-8")
    _panel_rows().to_parquet(panel_path, index=False)
    _planning_rows().to_parquet(planning_rows_path, index=False)

    result = subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_counterfactual_planning_v1.py",
            "--config",
            str(config_path),
            "--planning-rows",
            str(planning_rows_path),
            "--panel",
            str(panel_path),
            "--variables-config",
            str(variables_path),
            "--output-dir",
            str(output_dir),
            "--output-name",
            "counterfactual_v1_test",
            "--evaluation-splits",
            "validation,test",
            "--max-rows-per-split",
            "2",
            "--examples-per-scenario",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    metrics = pd.read_csv(metrics_path)
    summary = pd.read_csv(summary_path)
    pareto = pd.read_csv(pareto_path)
    examples = pd.read_csv(examples_path)
    report = report_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert {"no_action", "clarity_strong"}.issubset(set(summary["scenario_id"]))
    statuses = dict(zip(summary["scenario_id"], summary["scenario_status"], strict=True))
    assert statuses["no_action"] == "completed"
    assert statuses["clarity_strong"] == "completed"
    assert float(summary.loc[summary["scenario_id"] == "no_action", "objective_value"].iloc[0]) == pytest.approx(0.0)
    assert int(summary.loc[summary["scenario_id"] == "clarity_strong", "support_violation_rows"].iloc[0]) > 0
    assert float(summary.loc[summary["scenario_id"] == "clarity_strong", "support_violation_rate"].iloc[0]) > 0.0

    assert set(metrics["split"]) == {"validation", "test"}
    assert set(metrics["horizon_months"]) == {1, 2}
    assert not pareto.empty
    assert not examples.empty
    assert "Counterfactual planning V1 completed." in result.stdout
    assert "Created files:" in result.stdout
    assert "counterfactual_v1_test_metrics.csv" in result.stdout
    assert "counterfactual_v1_test_manifest.json" in result.stdout
    assert NON_CAUSAL_GUARDRAIL in report
    assert "raw-input perturbations" in report
    assert manifest["status"] == "completed"
    assert manifest["planning_version"] == "counterfactual_planning_raw_proxy_v1"
    assert [record["role"] for record in manifest["inputs"]] == [
        "config",
        "planning_rows",
        "panel",
        "variables_config",
    ]
    assert manifest["config"]["output_name"] == "counterfactual_v1_test"
    assert manifest["row_counts"]["summary_rows"] == len(summary)
    assert manifest["row_counts"]["metric_rows"] == len(metrics)
    assert manifest["script"]["path"] == "src/experiments/evaluate_counterfactual_planning_v1.py"
