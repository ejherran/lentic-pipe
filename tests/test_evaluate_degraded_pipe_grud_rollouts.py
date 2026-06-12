from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, PIPE_STATE_COLUMNS, TARGET_COLUMNS
from src.experiments.train_pipe_grud import STATE_TARGET_NAMES, make_model


def _sequence_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for step in range(4):
        row: dict[str, object] = {
            "source_id": "A",
            "site_id": "s1",
            "sequence_step": step,
            "origin_year_month": f"2022-{step + 1:02d}",
            "target_year_month": f"2022-{step + 2:02d}",
            "target_gap_months": 1,
            "split": "test",
        }
        state_values = {
            "yN": 0.60,
            "yF": 0.40,
            "yT": 0.70,
            "sigma_N": 0.10,
            "sigma_F": 0.10,
            "sigma_T": 0.10,
            "delta_yN": 0.00,
            "delta_yF": 0.00,
            "delta_yT": 0.00,
        }
        for column in PIPE_STATE_COLUMNS:
            row[f"x_{column}"] = state_values[column]
            row[f"target_{column}"] = state_values[column]
        for column in INPUT_COLUMNS:
            row.setdefault(column, 0.0)
        rows.append(row)
    return pd.DataFrame(rows)


def _target_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for origin_month in ["2022-02", "2022-03"]:
        origin_period = cast(pd.Period, pd.Period(origin_month, freq="M"))
        for horizon in [1, 2]:
            rows.append(
                {
                    "source_id": "A",
                    "site_id": "s1",
                    "origin_year_month": origin_month,
                    "horizon_months": horizon,
                    "split": "test",
                    "target_year_month": str(origin_period + horizon),
                    "bloom_h": 1,
                    "target_risk_chla_h": 0.8,
                }
            )
    return pd.DataFrame(rows)


def _write_identity_residual_model(path: Path, history_length: int = 2) -> None:
    torch = pytest.importorskip("torch")
    model = make_model(
        input_dim=len(INPUT_COLUMNS),
        target_dim=len(TARGET_COLUMNS),
        hidden_dim=4,
        num_layers=1,
        dropout=0.0,
        residual_mode="add_last",
    )
    for parameter in model.parameters():
        torch.nn.init.zeros_(parameter)
    torch.save(
        {
            "model_version": "pipe_grud_v0",
            "best_epoch": 1,
            "best_validation_loss": 0.0,
            "best_validation_objective": 0.0,
            "config": {
                "history_length": history_length,
                "hidden_dim": 4,
                "num_layers": 1,
                "dropout": 0.0,
                "residual_mode": "add_last",
                "mse_weight": 0.0,
            },
            "input_columns": INPUT_COLUMNS,
            "target_columns": TARGET_COLUMNS,
            "target_weights": {},
            "output_blend_weights": {target: 1.0 for target in STATE_TARGET_NAMES},
            "model_state_dict": model.state_dict(),
        },
        path,
    )


def _config_text() -> str:
    return """
schema_version: 1
randomization:
  seeds:
    - 20260612
pipe_state_variable_groups:
  pipe_state_level:
    variables:
      - x_yN
      - x_yF
      - x_yT
  pipe_state_all:
    variables:
      - x_yN
      - x_yF
      - x_yT
      - x_sigma_N
      - x_sigma_F
      - x_sigma_T
      - x_delta_yN
      - x_delta_yF
      - x_delta_yT
scenario_sets:
  pipe_state_test:
    - control_observed
    - ablate_pipe_state_level
scenarios:
  - scenario_id: control_observed
    family: control
    tier: core
    operations: []
  - scenario_id: ablate_pipe_state_level
    family: pipe_state_ablation
    tier: core
    operations:
      - type: set_sequence_inputs
        variable_group: pipe_state_level
        fill_value: 0.0
"""


def test_evaluate_degraded_pipe_grud_rollouts_cli_writes_recomputed_outputs(tmp_path: Path) -> None:
    pytest.importorskip("torch")

    config_path = tmp_path / "degradation.yaml"
    sequences_path = tmp_path / "sequences.parquet"
    splits_path = tmp_path / "splits.parquet"
    thresholds_path = tmp_path / "thresholds.csv"
    model_path = tmp_path / "model.pt"
    model_manifest_path = tmp_path / "model_manifest.json"
    state_metrics_path = tmp_path / "state_metrics.csv"
    alert_metrics_path = tmp_path / "alert_metrics.csv"
    policy_metrics_path = tmp_path / "policy_metrics.csv"
    summary_path = tmp_path / "summary.csv"
    examples_path = tmp_path / "examples.csv"
    backtest_rows_path = tmp_path / "backtest_rows.parquet"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"

    config_path.write_text(_config_text(), encoding="utf-8")
    _sequence_rows().to_parquet(sequences_path, index=False)
    _target_rows().to_parquet(splits_path, index=False)
    pd.DataFrame(
        [
            {
                "policy_name": "closest_pr",
                "target_event": "irc_alert",
                "rollout_horizon_months": 1,
                "score_column": "alert_probability_irc",
                "selected_threshold": 0.5,
            },
            {
                "policy_name": "closest_pr",
                "target_event": "irc_alert",
                "rollout_horizon_months": 2,
                "score_column": "alert_probability_irc",
                "selected_threshold": 0.5,
            },
        ]
    ).to_csv(thresholds_path, index=False)
    _write_identity_residual_model(model_path)
    model_manifest_path.write_text('{"status": "test"}\n', encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_degraded_pipe_grud_rollouts.py",
            "--config",
            str(config_path),
            "--sequences",
            str(sequences_path),
            "--splits",
            str(splits_path),
            "--thresholds",
            str(thresholds_path),
            "--model",
            str(model_path),
            "--model-manifest",
            str(model_manifest_path),
            "--fuzzy-calibrators-dir",
            str(tmp_path / "missing_calibrators"),
            "--rollout-calibrator-dir",
            str(tmp_path / "missing_rollout_calibrators"),
            "--state-metrics",
            str(state_metrics_path),
            "--alert-metrics",
            str(alert_metrics_path),
            "--policy-metrics",
            str(policy_metrics_path),
            "--summary",
            str(summary_path),
            "--examples",
            str(examples_path),
            "--backtest-rows",
            str(backtest_rows_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--scenario-set",
            "pipe_state_test",
            "--rollout-horizon",
            "2",
            "--deterministic",
            "--disable-calibrated-bloom",
            "--batch-size",
            "1",
            "--irc-alert-threshold",
            "0.5",
            "--alert-prob-threshold",
            "0.5",
        ],
        check=True,
    )

    state_metrics = pd.read_csv(state_metrics_path)
    alert_metrics = pd.read_csv(alert_metrics_path)
    policy_metrics = pd.read_csv(policy_metrics_path)
    summary = pd.read_csv(summary_path)
    backtest_rows = pd.read_parquet(backtest_rows_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert summary["scenario_id"].tolist() == ["control_observed", "ablate_pipe_state_level"]
    assert summary["score_recomputed"].tolist() == [True, True]
    degraded_summary = summary[summary["scenario_id"] == "ablate_pipe_state_level"].iloc[0]
    assert int(degraded_summary["affected_rows"]) == 4
    assert int(degraded_summary["affected_cells"]) == 12
    assert int(degraded_summary["affected_selected_window_rows"]) == 3
    assert int(degraded_summary["affected_selected_window_cells"]) == 9
    assert set(state_metrics["scenario_id"]) == {"control_observed", "ablate_pipe_state_level"}
    assert set(alert_metrics["scenario_id"]) == {"control_observed", "ablate_pipe_state_level"}
    assert set(policy_metrics["scenario_id"]) == {"control_observed", "ablate_pipe_state_level"}
    assert set(policy_metrics["alert_policy"]) == {"closest_pr"}
    assert int(summary["policy_metric_rows"].sum()) == len(policy_metrics)
    assert len(backtest_rows) == 8

    control_alerts = backtest_rows[backtest_rows["scenario_id"] == "control_observed"]
    degraded_alerts = backtest_rows[backtest_rows["scenario_id"] == "ablate_pipe_state_level"]
    assert all(math.isclose(value, 1.0, abs_tol=1e-7) for value in control_alerts["alert_probability_irc"])
    assert all(math.isclose(value, 0.0, abs_tol=1e-7) for value in degraded_alerts["alert_probability_irc"])
    assert manifest["status"] == "completed"
    assert manifest["row_counts"]["selected_origins"] == 2
    assert manifest["row_counts"]["backtest_row_rows"] == 8
    assert manifest["script"]["path"] == "src/experiments/evaluate_degraded_pipe_grud_rollouts.py"
    assert "Recomputed PIPE/GRU-D State Degradation Report" in report_path.read_text(encoding="utf-8")
