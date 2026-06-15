from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.experiments.build_pipe_sequences import PIPE_STATE_COLUMNS, SEASON_COLUMNS
from src.experiments.train_pipe_neural_ode import (
    STATE_INPUT_COLUMNS,
    make_neural_ode_model,
    synthetic_sequence_frame,
)


def test_synthetic_sequence_frame_has_pipe_schema_and_splits() -> None:
    frame = synthetic_sequence_frame(sites_per_split=2, months_per_split=4, seed=1729)

    assert len(frame) == 24
    assert set(frame["split"]) == {"train", "validation", "test"}
    assert set(STATE_INPUT_COLUMNS).issubset(frame.columns)
    assert set(SEASON_COLUMNS).issubset(frame.columns)
    assert frame[[f"target_{column}" for column in PIPE_STATE_COLUMNS[:6]]].max().max() <= 1.0
    assert frame[[f"target_{column}" for column in PIPE_STATE_COLUMNS[:6]]].min().min() >= 0.0


def test_neural_ode_model_forward_returns_bounded_state() -> None:
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchdiffeq")

    model = make_neural_ode_model(
        state_dim=len(STATE_INPUT_COLUMNS),
        season_dim=len(SEASON_COLUMNS),
        hidden_dim=8,
        depth=1,
        dropout=0.0,
        derivative_scale=0.2,
        integration_time=1.0,
        ode_method="rk4",
        ode_step_size=0.5,
        rtol=1e-3,
        atol=1e-4,
    )
    state = torch.full((3, len(STATE_INPUT_COLUMNS)), 0.5)
    season = torch.zeros((3, len(SEASON_COLUMNS)))

    mu, logvar = model(state, season)

    assert tuple(mu.shape) == (3, len(STATE_INPUT_COLUMNS))
    assert tuple(logvar.shape) == (3, len(STATE_INPUT_COLUMNS))
    assert torch.all(mu[:, :6] >= 0.0)
    assert torch.all(mu[:, :6] <= 1.0)


def test_train_pipe_neural_ode_cli_writes_synthetic_smoke_outputs(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    pytest.importorskip("torchdiffeq")

    model_path = tmp_path / "model.pt"
    checkpoint_path = tmp_path / "checkpoint.pt"
    metrics_path = tmp_path / "metrics.csv"
    persistence_path = tmp_path / "persistence.csv"
    comparison_path = tmp_path / "comparison.csv"
    blend_weights_path = tmp_path / "blend_weights.csv"
    blend_search_path = tmp_path / "blend_search.csv"
    training_curve_path = tmp_path / "training_curve.csv"
    examples_path = tmp_path / "examples.csv"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"

    subprocess.run(
        [
            sys.executable,
            "src/experiments/train_pipe_neural_ode.py",
            "--synthetic-smoke",
            "--synthetic-sites",
            "2",
            "--synthetic-months-per-split",
            "4",
            "--epochs",
            "1",
            "--batch-size",
            "4",
            "--hidden-dim",
            "8",
            "--depth",
            "1",
            "--ode-step-size",
            "0.5",
            "--progress-every-batches",
            "0",
            "--max-examples",
            "3",
            "--model",
            str(model_path),
            "--checkpoint",
            str(checkpoint_path),
            "--metrics",
            str(metrics_path),
            "--persistence-metrics",
            str(persistence_path),
            "--comparison",
            str(comparison_path),
            "--blend-weights",
            str(blend_weights_path),
            "--blend-search",
            str(blend_search_path),
            "--training-curve",
            str(training_curve_path),
            "--examples",
            str(examples_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
        ],
        check=True,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")

    assert model_path.exists()
    assert checkpoint_path.exists()
    assert manifest["status"] == "completed"
    assert manifest["scope"]["synthetic_smoke"] is True
    assert manifest["row_counts"]["sampled_transitions"]["train"] == 8
    assert manifest["outputs"]
    assert "PIPE Neural ODE Training Report v0" in report
