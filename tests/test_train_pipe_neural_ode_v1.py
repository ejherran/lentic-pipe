from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, SEASON_COLUMNS
from src.experiments.train_pipe_neural_ode import STATE_INPUT_COLUMNS
from src.experiments.train_pipe_neural_ode_v1 import make_history_neural_ode_model


def test_history_neural_ode_model_forward_returns_bounded_state() -> None:
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchdiffeq")

    model = make_history_neural_ode_model(
        input_dim=len(INPUT_COLUMNS),
        state_dim=len(STATE_INPUT_COLUMNS),
        season_dim=len(SEASON_COLUMNS),
        history_hidden_dim=8,
        history_layers=1,
        latent_dim=6,
        dynamics_hidden_dim=8,
        dynamics_depth=1,
        dropout=0.0,
        derivative_scale=0.2,
        state_delta_scale=0.3,
        integration_time=1.0,
        ode_method="rk4",
        ode_step_size=0.5,
        rtol=1e-3,
        atol=1e-4,
    )
    x_window = torch.zeros((3, 4, len(INPUT_COLUMNS)))
    x_window[:, :, : len(STATE_INPUT_COLUMNS)] = 0.5

    mu, logvar = model(x_window)

    assert tuple(mu.shape) == (3, len(STATE_INPUT_COLUMNS))
    assert tuple(logvar.shape) == (3, len(STATE_INPUT_COLUMNS))
    assert torch.all(mu[:, :6] >= 0.0)
    assert torch.all(mu[:, :6] <= 1.0)
    assert torch.all(mu[:, 6:] >= -1.0)
    assert torch.all(mu[:, 6:] <= 1.0)


def test_train_pipe_neural_ode_v1_cli_writes_synthetic_smoke_outputs(tmp_path: Path) -> None:
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
            "src/experiments/train_pipe_neural_ode_v1.py",
            "--synthetic-smoke",
            "--synthetic-sites",
            "2",
            "--synthetic-months-per-split",
            "6",
            "--history-length",
            "3",
            "--epochs",
            "1",
            "--batch-size",
            "4",
            "--history-hidden-dim",
            "8",
            "--latent-dim",
            "6",
            "--dynamics-hidden-dim",
            "8",
            "--dynamics-depth",
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
    assert manifest["model_version"] == "pipe_neural_ode_history_v1"
    assert manifest["scope"]["synthetic_smoke"] is True
    assert manifest["row_counts"]["sampled_windows"]["train"] == 8
    assert manifest["outputs"]
    assert "PIPE Neural ODE History Training Report v1" in report
