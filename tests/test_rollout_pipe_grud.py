from __future__ import annotations

import json
import math
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, PIPE_STATE_COLUMNS, TARGET_COLUMNS
from src.experiments.rollout_pipe_grud import compute_irc, select_rollout_indices
from src.experiments.train_pipe_grud import STATE_TARGET_NAMES, make_model, prepare_window_frame


def _sequence_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for step in range(4):
        row: dict[str, object] = {
            "source_id": "A",
            "site_id": "s1",
            "sequence_step": step,
            "origin_year_month": f"2022-{step + 1:02d}",
            "target_year_month": f"2022-{step + 2:02d}",
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


def test_compute_irc_uses_pipe_weight_semantics() -> None:
    states = pd.DataFrame({"yN": [0.6], "yF": [0.4], "yT": [0.7]}).to_numpy()

    irc = compute_irc(states, alpha=0.5, beta=0.5, gamma=2.0)

    assert math.isclose(float(irc[0]), 2.0 / 3.0)


def test_select_rollout_indices_picks_latest_source_scoped_site() -> None:
    frame = prepare_window_frame(_sequence_rows())
    args = Namespace(split="all", scope="latest-sites", max_origins=None)

    indices = select_rollout_indices(frame, args, history_length=2)

    assert len(indices) == 1
    assert frame.loc[int(indices[0]), "origin_year_month"] == "2022-04"


def test_rollout_pipe_grud_cli_writes_alert_outputs(tmp_path: Path) -> None:
    pytest.importorskip("torch")

    sequences_path = tmp_path / "sequences.parquet"
    model_path = tmp_path / "model.pt"
    model_manifest_path = tmp_path / "model_manifest.json"
    rollouts_path = tmp_path / "rollouts.parquet"
    summary_path = tmp_path / "summary.csv"
    top_alerts_path = tmp_path / "top_alerts.csv"
    recent_top_alerts_path = tmp_path / "recent_top_alerts.csv"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"

    _sequence_rows().to_parquet(sequences_path, index=False)
    _write_identity_residual_model(model_path)
    model_manifest_path.write_text('{"status": "test"}\n', encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "src/experiments/rollout_pipe_grud.py",
            "--sequences",
            str(sequences_path),
            "--model",
            str(model_path),
            "--model-manifest",
            str(model_manifest_path),
            "--fuzzy-calibrators-dir",
            str(tmp_path / "missing_calibrators"),
            "--rollouts",
            str(rollouts_path),
            "--summary",
            str(summary_path),
            "--top-alerts",
            str(top_alerts_path),
            "--recent-top-alerts",
            str(recent_top_alerts_path),
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

    rollouts = pd.read_parquet(rollouts_path)
    summary = pd.read_csv(summary_path)
    top_alerts = pd.read_csv(top_alerts_path)
    recent_top_alerts = pd.read_csv(recent_top_alerts_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert len(rollouts) == 2
    assert set(rollouts["rollout_horizon_months"]) == {1, 2}
    assert rollouts["predicted_alert_h"].all()
    assert rollouts["alert_probability_irc"].tolist() == [1.0, 1.0]
    assert all(math.isclose(value, 2.0 / 3.0, rel_tol=1e-6) for value in rollouts["irc_mean"])
    assert summary[summary["source_id"] == "all"]["predicted_alerts"].tolist() == [1, 1]
    assert top_alerts["rank_within_horizon"].tolist() == [1, 1]
    assert recent_top_alerts["rank_within_horizon"].tolist() == [1, 1]
    assert recent_top_alerts["recent_window_end"].tolist() == ["2022-04", "2022-04"]
    assert manifest["status"] == "completed"
    assert manifest["row_counts"]["selected_origins"] == 1
    assert manifest["row_counts"]["rollout_rows"] == 2
    assert manifest["row_counts"]["recent_top_alert_rows"] == 2
    assert manifest["config"]["deterministic"] is True
    assert "PIPE/GRU-D Rollout Alert Report v0" in report_path.read_text(encoding="utf-8")
