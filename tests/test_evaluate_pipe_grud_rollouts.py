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
from src.experiments.evaluate_pipe_grud_rollouts import observed_state_frame
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


def test_observed_state_frame_uses_origin_and_target_states() -> None:
    observed = observed_state_frame(_sequence_rows())

    assert observed["observed_year_month"].tolist() == ["2022-01", "2022-02", "2022-03", "2022-04", "2022-05"]
    assert all(math.isclose(value, 0.70, rel_tol=1e-6) for value in observed["actual_yT"])


def test_evaluate_pipe_grud_rollouts_cli_writes_backtest_outputs(tmp_path: Path) -> None:
    pytest.importorskip("torch")

    sequences_path = tmp_path / "sequences.parquet"
    splits_path = tmp_path / "splits.parquet"
    model_path = tmp_path / "model.pt"
    model_manifest_path = tmp_path / "model_manifest.json"
    metrics_path = tmp_path / "metrics.csv"
    alert_metrics_path = tmp_path / "alert_metrics.csv"
    examples_path = tmp_path / "examples.csv"
    backtest_rows_path = tmp_path / "backtest_rows.parquet"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"

    _sequence_rows().to_parquet(sequences_path, index=False)
    _target_rows().to_parquet(splits_path, index=False)
    _write_identity_residual_model(model_path)
    model_manifest_path.write_text('{"status": "test"}\n', encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_pipe_grud_rollouts.py",
            "--sequences",
            str(sequences_path),
            "--splits",
            str(splits_path),
            "--model",
            str(model_path),
            "--model-manifest",
            str(model_manifest_path),
            "--fuzzy-calibrators-dir",
            str(tmp_path / "missing_calibrators"),
            "--metrics",
            str(metrics_path),
            "--alert-metrics",
            str(alert_metrics_path),
            "--examples",
            str(examples_path),
            "--backtest-rows",
            str(backtest_rows_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
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

    metrics = pd.read_csv(metrics_path)
    alert_metrics = pd.read_csv(alert_metrics_path)
    backtest_rows = pd.read_parquet(backtest_rows_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    overall_all = metrics[
        (metrics["group_type"] == "overall") & (metrics["target"] == "all")
    ].sort_values("rollout_horizon_months")
    irc_alert = alert_metrics[
        (alert_metrics["group_type"] == "overall") & (alert_metrics["target_event"] == "irc_alert")
    ].sort_values("rollout_horizon_months")

    assert overall_all["rows"].tolist() == [18, 18]
    assert all(math.isclose(value, 0.0, abs_tol=1e-7) for value in overall_all["rmse"])
    assert irc_alert["rows"].tolist() == [2, 2]
    assert irc_alert["positive_rows"].tolist() == [2, 2]
    assert len(backtest_rows) == 4
    assert {"alert_probability_irc", "actual_irc_alert", "irc_mean", "bloom_h"}.issubset(backtest_rows.columns)
    assert manifest["status"] == "completed"
    assert manifest["row_counts"]["selected_origins"] == 2
    assert manifest["row_counts"]["evaluated_rollout_rows"] == 4
    assert manifest["row_counts"]["backtest_row_export_rows"] == 4
    assert manifest["script"]["path"] == "src/experiments/evaluate_pipe_grud_rollouts.py"
    assert "PIPE/GRU-D Rollout Backtest Report v0" in report_path.read_text(encoding="utf-8")
