from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from src.experiments.evaluate_counterfactual_planning import (
    NON_CAUSAL_GUARDRAIL,
    objective_components,
)


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
        scenario_spaces:
          state_proxy:
            channels:
              x_yN:
                absolute_offsets:
                  - 0.0
                  - -0.05
                  - -0.15
              x_yF:
                absolute_offsets:
                  - 0.0
                  - 0.05
        proxy_actions:
          nutrient_reduction_tp:
            relative_unit_cost: 1.0
          clarity_improvement:
            relative_unit_cost: 0.7
          combined_nutrient_clarity:
            relative_coordination_cost: 0.2
        scenario_families:
          minimal_state_grid:
            enabled: true
            include_actions:
              - no_action
              - nutrient_reduction_tp
              - clarity_improvement
              - combined_nutrient_clarity
            max_combined_nonzero_offsets: 2
        constraints:
          state_channels_clip_to_unit_interval: true
          max_relative_cost:
            normal: 2.0
        objective:
          default_planning_mode: normal
          planning_modes:
            normal:
              lambda_cost: 0.05
          weights:
            irc_alert_risk_reduction: 0.6
            bloom_probability_reduction: 0.4
          lambda_uncertainty: 0.1
        reporting:
          prohibited_claim: The scenario will reduce real-world eutrophication.
        """
    ).strip()


def _planning_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "site_low_n",
                "split": "validation",
                "origin_year_month": "2020-01",
                "x_yN": 0.03,
                "x_yF": 0.40,
                "x_yT": 0.65,
                "x_sigma_N": 0.10,
                "x_sigma_F": 0.20,
                "x_sigma_T": 0.30,
                "actual_irc_alert": 1,
                "bloom_h": 1,
            },
            {
                "source_id": "wqp",
                "site_id": "site_mid",
                "split": "validation",
                "origin_year_month": "2020-02",
                "x_yN": 0.50,
                "x_yF": 0.35,
                "x_yT": 0.60,
                "x_sigma_N": 0.20,
                "x_sigma_F": 0.20,
                "x_sigma_T": 0.20,
                "actual_irc_alert": 1,
                "bloom_h": 0,
            },
            {
                "source_id": "wqp",
                "site_id": "site_test",
                "split": "test",
                "origin_year_month": "2020-03",
                "x_yN": 0.25,
                "x_yF": 0.55,
                "x_yT": 0.45,
                "x_sigma_N": 0.10,
                "x_sigma_F": 0.10,
                "x_sigma_T": 0.10,
                "actual_irc_alert": 0,
                "bloom_h": 0,
            },
        ]
    )


def test_objective_components_penalizes_cost_and_uncertainty() -> None:
    config = {
        "objective": {
            "planning_modes": {"normal": {"lambda_cost": 0.05}},
            "weights": {"irc_alert_risk_reduction": 0.6, "bloom_probability_reduction": 0.4},
            "lambda_uncertainty": 0.10,
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
        config=config,
        planning_mode="normal",
    )

    assert components["risk_reduction_absolute"] == pytest.approx(0.20)
    assert components["objective_value"] == pytest.approx(0.20 - 0.05 - 0.01)


def test_evaluate_counterfactual_planning_cli_writes_reproducible_outputs(tmp_path: Path) -> None:
    config_path = tmp_path / "counterfactual_planning.yaml"
    planning_rows_path = tmp_path / "planning_rows.parquet"
    output_dir = tmp_path / "planning"
    metrics_path = output_dir / "counterfactual_test_metrics.csv"
    summary_path = output_dir / "counterfactual_test_summary.csv"
    pareto_path = output_dir / "counterfactual_test_pareto.csv"
    examples_path = output_dir / "counterfactual_test_examples.csv"
    report_path = output_dir / "counterfactual_test_report.md"
    manifest_path = output_dir / "counterfactual_test_manifest.json"

    config_path.write_text(_config_text(), encoding="utf-8")
    _planning_rows().to_parquet(planning_rows_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_counterfactual_planning.py",
            "--config",
            str(config_path),
            "--planning-rows",
            str(planning_rows_path),
            "--output-dir",
            str(output_dir),
            "--output-name",
            "counterfactual_test",
            "--evaluation-splits",
            "validation,test",
            "--max-rows-per-split",
            "3",
            "--examples-per-scenario",
            "2",
        ],
        check=True,
    )

    metrics = pd.read_csv(metrics_path)
    summary = pd.read_csv(summary_path)
    pareto = pd.read_csv(pareto_path)
    examples = pd.read_csv(examples_path)
    report = report_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert {"no_action", "state_yN_m0p15_yF_0"}.issubset(set(summary["scenario_id"]))
    statuses = dict(zip(summary["scenario_id"], summary["scenario_status"], strict=True))
    assert statuses["no_action"] == "completed"
    assert statuses["state_yN_m0p15_yF_0"] == "infeasible"
    assert int(summary.loc[summary["scenario_id"] == "state_yN_m0p15_yF_0", "clipped_rows"].iloc[0]) > 0
    assert float(summary.loc[summary["scenario_id"] == "no_action", "relative_cost"].iloc[0]) == 0.0
    assert float(summary.loc[summary["scenario_id"] == "no_action", "objective_value"].iloc[0]) == pytest.approx(0.0)

    assert set(metrics["split"]) == {"validation", "test"}
    assert set(metrics["horizon_months"]) == {1, 2}
    assert not pareto.empty
    assert not examples.empty
    assert NON_CAUSAL_GUARDRAIL in report
    assert "Prohibited claim" in report
    assert manifest["status"] == "completed"
    assert manifest["planning_version"] == "counterfactual_planning_grid_v0"
    assert [record["role"] for record in manifest["inputs"]] == ["config", "planning_rows"]
    assert manifest["config"]["output_name"] == "counterfactual_test"
    assert manifest["row_counts"]["summary_rows"] == len(summary)
    assert manifest["row_counts"]["metric_rows"] == len(metrics)
    assert manifest["script"]["path"] == "src/experiments/evaluate_counterfactual_planning.py"
