from __future__ import annotations

import json
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, SEASON_COLUMNS, TARGET_COLUMNS
from src.experiments.train_pipe_grud import make_loss_weights, prepare_window_frame
from src.experiments.train_pipe_neural_ode import STATE_INPUT_COLUMNS, synthetic_sequence_frame
from src.experiments.train_pipe_neural_ode_v2 import (
    ContinuousTimeWindowDataset,
    continuous_time_training_loss,
    eligible_continuous_time_examples,
    make_continuous_time_neural_ode_model,
    parse_horizons,
)


def test_parse_horizons_deduplicates_and_sorts() -> None:
    assert parse_horizons("3,1,2,2") == [1, 2, 3]


def test_continuous_time_examples_cover_direct_horizons() -> None:
    frame = prepare_window_frame(synthetic_sequence_frame(sites_per_split=1, months_per_split=6, seed=11))

    end_indices, gaps = eligible_continuous_time_examples(
        frame,
        split="train",
        history_length=3,
        horizons=[1, 2, 3],
    )

    assert len(end_indices) == 9
    assert {horizon: int((gaps == horizon).sum()) for horizon in [1, 2, 3]} == {1: 4, 2: 3, 3: 2}


def test_continuous_time_dataset_targets_future_gap() -> None:
    frame = prepare_window_frame(synthetic_sequence_frame(sites_per_split=1, months_per_split=6, seed=17))
    end_indices, gaps = eligible_continuous_time_examples(
        frame,
        split="train",
        history_length=3,
        horizons=[2],
    )
    origin_month = np.zeros(len(frame), dtype="float32")
    dataset = ContinuousTimeWindowDataset(
        frame[INPUT_COLUMNS].to_numpy(dtype="float32"),
        frame[TARGET_COLUMNS].to_numpy(dtype="float32"),
        origin_month,
        end_indices,
        gaps,
        history_length=3,
    )

    x_window, y_target, dt, _origin_month, gap = dataset[0]

    assert tuple(x_window.shape) == (3, len(INPUT_COLUMNS))
    assert tuple(y_target.shape) == (len(TARGET_COLUMNS),)
    assert float(dt) == 2.0
    assert int(gap) == 2
    np.testing.assert_allclose(y_target.numpy(), frame.loc[int(end_indices[0]) + 1, TARGET_COLUMNS].to_numpy())


def test_continuous_time_model_forward_and_loss_are_finite() -> None:
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchdiffeq")

    model = make_continuous_time_neural_ode_model(
        input_dim=len(INPUT_COLUMNS),
        state_dim=len(STATE_INPUT_COLUMNS),
        season_dim=len(SEASON_COLUMNS),
        context_dim=0,
        history_hidden_dim=8,
        history_layers=1,
        latent_dim=6,
        dynamics_hidden_dim=8,
        dynamics_depth=1,
        dropout=0.0,
        derivative_scale=0.2,
        state_delta_scale=0.3,
        ode_method="rk4",
        ode_step_size=0.5,
        rtol=1e-3,
        atol=1e-4,
    )
    x_window = torch.zeros((3, 4, len(INPUT_COLUMNS)))
    x_window[:, :, : len(STATE_INPUT_COLUMNS)] = 0.5
    dt = torch.tensor([1.0, 2.0, 3.0])
    origin_month = torch.tensor([0.0, 3.0, 6.0])
    target = torch.full((3, len(TARGET_COLUMNS)), 0.4)
    weights = torch.from_numpy(make_loss_weights())
    args = argparse.Namespace(
        mse_weight=0.5,
        irc_loss_weight=0.1,
        irc_alpha=0.5,
        irc_beta=0.5,
        irc_gamma=2.0,
    )

    mu, logvar = model(x_window, dt, origin_month)
    loss = continuous_time_training_loss(mu, logvar, target, weights, args)
    loss.backward()

    assert tuple(mu.shape) == (3, len(STATE_INPUT_COLUMNS))
    assert tuple(logvar.shape) == (3, len(STATE_INPUT_COLUMNS))
    assert bool(torch.isfinite(loss))
    assert torch.all(mu[:, :6] >= 0.0)
    assert torch.all(mu[:, :6] <= 1.0)


def test_train_pipe_neural_ode_v2_cli_writes_synthetic_smoke_outputs(tmp_path: Path) -> None:
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
            "src/experiments/train_pipe_neural_ode_v2.py",
            "--synthetic-smoke",
            "--synthetic-sites",
            "2",
            "--synthetic-months-per-split",
            "6",
            "--history-length",
            "3",
            "--forecast-horizons",
            "1,2,3",
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
    assert manifest["model_version"] == "pipe_neural_ode_continuous_v2"
    assert manifest["config"]["forecast_horizons"] == [1, 2, 3]
    assert manifest["row_counts"]["sampled_examples"]["train"] == 18
    assert manifest["outputs"]
    assert "PIPE Neural ODE Continuous-Time Training Report v2" in report
