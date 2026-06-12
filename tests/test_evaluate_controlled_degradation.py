from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.experiments.evaluate_controlled_degradation import _metric_dict


def test_metric_dict_marks_ranking_metrics_undefined_for_single_class() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        metrics = _metric_dict(np.array([0.05, 0.10, 0.20]), np.array([0, 0, 0]), threshold=0.5)

    assert not caught
    assert metrics["positive_rows"] == 0
    assert pd.isna(metrics["pr_auc"])
    assert pd.isna(metrics["roc_auc"])
    assert pd.isna(metrics["balanced_accuracy"])


def _score_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    scores = [0.10, 0.40, 0.65, 0.90]
    for source_id in ["wqp", "aquamatch_chla"]:
        for index, score in enumerate(scores, start=1):
            actual = int(score >= 0.50)
            rows.append(
                {
                    "source_id": source_id,
                    "site_id": f"{source_id}_site_{index}",
                    "split": "test",
                    "origin_year_month": f"2020-{index:02d}",
                    "forecast_year_month": f"2020-{index + 1:02d}",
                    "rollout_horizon_months": 1,
                    "alert_probability_irc": score,
                    "actual_irc_alert": actual,
                    "probability_bloom_mean": score,
                    "rollout_probability_bloom_calibrated": score,
                    "bloom_h": actual,
                    "TP_ugL": 10.0 + index,
                    "TN_ugL": 100.0 + index,
                    "chlorophyll_a_ugL": 5.0 + index,
                }
            )
    return pd.DataFrame(rows)


def _thresholds() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for policy_name in ["closest_pr", "fixed"]:
        rows.append(
            {
                "policy_name": policy_name,
                "target_event": "irc_alert",
                "rollout_horizon_months": 1,
                "score_column": "alert_probability_irc",
                "selected_threshold": 0.50,
            }
        )
        rows.append(
            {
                "policy_name": policy_name,
                "target_event": "bloom_h",
                "rollout_horizon_months": 1,
                "score_column": (
                    "rollout_probability_bloom_calibrated"
                    if policy_name == "closest_pr"
                    else "probability_bloom_mean"
                ),
                "selected_threshold": 0.50,
            }
        )
    return pd.DataFrame(rows)


def _config_text() -> str:
    return textwrap.dedent(
        """
        schema_version: 1
        protocol:
          default_alert_policy:
            selection_objective: closest_pr
          comparison_alert_policies:
            - fixed
        evaluation:
          splits:
            - test
        randomization:
          seeds:
            - 7
        canonical_variable_groups:
          nutrients:
            variables:
              - TP_ugL
              - TN_ugL
          all_core_predictors:
            variables:
              - TP_ugL
              - TN_ugL
              - chlorophyll_a_ugL
        scenario_sets:
          test:
            - control_observed
            - source_scope_wqp_only
            - site_retention_50
            - ablate_nutrients
        scenarios:
          - scenario_id: control_observed
            family: control
            tier: core
            operations: []
          - scenario_id: source_scope_wqp_only
            family: source_scope_diagnostic
            tier: extended
            operations:
              - type: filter_source_id
                include:
                  - wqp
          - scenario_id: site_retention_50
            family: site_retention
            tier: core
            operations:
              - type: stratified_site_retention
                retain_fraction: 0.50
          - scenario_id: ablate_nutrients
            family: feature_family_ablation
            tier: core
            operations:
              - type: set_variables_missing
                variable_group: nutrients
        """
    ).strip()


def test_evaluate_controlled_degradation_cli_writes_reproducible_outputs(tmp_path: Path) -> None:
    config_path = tmp_path / "degradation_scenarios.yaml"
    scored_rows_path = tmp_path / "score_rows.parquet"
    thresholds_path = tmp_path / "thresholds.csv"
    output_dir = tmp_path / "degradation"
    metrics_path = output_dir / "controlled_degradation_coverage_test_metrics.csv"
    summary_path = output_dir / "controlled_degradation_coverage_test_summary.csv"
    report_path = output_dir / "controlled_degradation_coverage_test_report.md"
    manifest_path = output_dir / "controlled_degradation_coverage_test_manifest.json"

    config_path.write_text(_config_text(), encoding="utf-8")
    _score_rows().to_parquet(scored_rows_path, index=False)
    _thresholds().to_csv(thresholds_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_controlled_degradation.py",
            "--config",
            str(config_path),
            "--scored-rows",
            str(scored_rows_path),
            "--thresholds",
            str(thresholds_path),
            "--output-name",
            "coverage_test",
            "--output-dir",
            str(output_dir),
            "--scenario-set",
            "test",
            "--policies",
            "closest_pr,fixed",
            "--evaluation-splits",
            "test",
            "--min-rows",
            "1",
        ],
        check=True,
    )

    metrics = pd.read_csv(metrics_path)
    summary = pd.read_csv(summary_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    statuses = dict(zip(summary["scenario_id"], summary["scenario_status"], strict=True))
    assert statuses["control_observed"] == "evaluated"
    assert statuses["source_scope_wqp_only"] == "evaluated"
    assert statuses["site_retention_50"] == "evaluated"
    assert statuses["ablate_nutrients"] == "skipped_requires_model_recompute"
    assert set(metrics["scenario_id"]) == {"control_observed", "source_scope_wqp_only", "site_retention_50"}
    assert set(metrics["alert_policy"]) == {"closest_pr", "fixed"}
    assert {"delta_f2_vs_control", "rows_retained_rate", "mcc"}.issubset(metrics.columns)
    assert set(metrics["score_recomputed"]) == {False}
    assert set(summary[summary["scenario_status"] == "evaluated"]["score_recomputed"]) == {False}

    source_scope = metrics[(metrics["scenario_id"] == "source_scope_wqp_only") & (metrics["source_id"] == "all")]
    assert set(source_scope["rows"]) == {4}
    assert set(source_scope["control_rows"]) == {8}
    assert set(source_scope["rows_retained_rate"]) == {0.5}

    skipped = summary[summary["scenario_id"] == "ablate_nutrients"].iloc[0]
    assert skipped["metrics_rows"] == 0
    assert not bool(skipped["score_recomputed"])
    assert manifest["status"] == "completed"
    assert manifest["config"]["output_name"] == "coverage_test"
    assert manifest["row_counts"]["summary_rows"] == 4
    assert manifest["row_counts"]["evaluated_runs"] == 3
    assert manifest["row_counts"]["skipped_runs"] == 1
    assert manifest["row_counts"]["evaluated_scenarios"] == 3
    assert manifest["row_counts"]["skipped_scenarios"] == 1
    assert manifest["script"]["path"] == "src/experiments/evaluate_controlled_degradation.py"
    assert "Controlled Degradation Report" in report_path.read_text(encoding="utf-8")
