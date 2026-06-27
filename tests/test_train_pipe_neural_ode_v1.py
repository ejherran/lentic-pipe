from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, SEASON_COLUMNS, TARGET_COLUMNS
from src.experiments.train_pipe_grud import make_loss_weights, prepare_window_frame
from src.experiments.train_pipe_neural_ode import STATE_INPUT_COLUMNS, synthetic_sequence_frame
from src.experiments.train_pipe_neural_ode_v1 import (
    EVIDENCE_CONTEXT_COLUMNS,
    IRC_CONTEXT_COLUMNS,
    MultiStepWindowDataset,
    checkpoint_selection_label,
    checkpoint_selection_objective,
    eligible_multistep_window_indices,
    history_training_loss,
    input_columns_for_context,
    make_history_neural_ode_model,
    multistep_training_loss,
    resolve_context_columns,
)


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


def test_context_columns_extend_history_neural_ode_input() -> None:
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchdiffeq")

    context_columns = resolve_context_columns("evidence")
    input_columns = input_columns_for_context(context_columns)
    model = make_history_neural_ode_model(
        input_dim=len(input_columns),
        state_dim=len(STATE_INPUT_COLUMNS),
        season_dim=len(SEASON_COLUMNS),
        context_dim=len(context_columns),
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
    x_window = torch.zeros((3, 4, len(input_columns)))
    x_window[:, :, : len(STATE_INPUT_COLUMNS)] = 0.5
    x_window[:, :, len(INPUT_COLUMNS) :] = 1.0

    mu, logvar = model(x_window)

    assert context_columns == EVIDENCE_CONTEXT_COLUMNS
    assert tuple(mu.shape) == (3, len(STATE_INPUT_COLUMNS))
    assert tuple(logvar.shape) == (3, len(STATE_INPUT_COLUMNS))
    assert torch.all(mu[:, :6] >= 0.0)
    assert torch.all(mu[:, :6] <= 1.0)


def test_irc_context_group_matches_current_adaptive_sequence_artifact() -> None:
    assert resolve_context_columns("irc") == IRC_CONTEXT_COLUMNS


def test_history_training_loss_accepts_irc_auxiliary_term() -> None:
    torch = pytest.importorskip("torch")

    mu = torch.full((2, len(TARGET_COLUMNS)), 0.5)
    logvar = torch.zeros_like(mu)
    target = torch.full((2, len(TARGET_COLUMNS)), 0.4)
    weights = torch.from_numpy(make_loss_weights())
    args = argparse.Namespace(
        mse_weight=0.5,
        irc_loss_weight=0.25,
        irc_alpha=0.5,
        irc_beta=0.5,
        irc_gamma=2.0,
    )

    loss = history_training_loss(mu, logvar, target, weights, args)

    assert bool(torch.isfinite(loss))


def test_multistep_window_dataset_requires_complete_future_horizon() -> None:
    frame = prepare_window_frame(synthetic_sequence_frame(sites_per_split=1, months_per_split=6, seed=11))

    indices = eligible_multistep_window_indices(frame, split="train", history_length=3, horizon=3)

    assert frame.loc[indices, "window_position"].tolist() == [2, 3]

    dataset = MultiStepWindowDataset(
        frame[INPUT_COLUMNS].to_numpy(dtype="float32"),
        frame[TARGET_COLUMNS].to_numpy(dtype="float32"),
        indices,
        history_length=3,
        horizon=3,
    )
    x_window, future_targets, future_inputs = dataset[0]

    assert tuple(x_window.shape) == (3, len(INPUT_COLUMNS))
    assert tuple(future_targets.shape) == (3, len(TARGET_COLUMNS))
    assert tuple(future_inputs.shape) == (2, len(INPUT_COLUMNS))


def test_multistep_training_loss_is_finite() -> None:
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchdiffeq")

    frame = prepare_window_frame(synthetic_sequence_frame(sites_per_split=1, months_per_split=6, seed=17))
    indices = eligible_multistep_window_indices(frame, split="train", history_length=3, horizon=2)
    dataset = MultiStepWindowDataset(
        frame[INPUT_COLUMNS].to_numpy(dtype="float32"),
        frame[TARGET_COLUMNS].to_numpy(dtype="float32"),
        indices,
        history_length=3,
        horizon=2,
    )
    x_window, future_targets, future_inputs = dataset[0]
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
    args = argparse.Namespace(
        mse_weight=0.5,
        multi_step_loss_weight=1.0,
        context_columns="none",
        irc_loss_weight=0.25,
        irc_alpha=0.5,
        irc_beta=0.5,
        irc_gamma=2.0,
    )
    weights = torch.from_numpy(make_loss_weights())

    loss = multistep_training_loss(
        model,
        x_window.unsqueeze(0),
        future_targets.unsqueeze(0),
        future_inputs.unsqueeze(0),
        weights,
        args,
    )

    assert bool(torch.isfinite(loss))


def test_multistep_checkpoint_objective_can_use_one_step_selection() -> None:
    rollout_args = argparse.Namespace(
        training_objective="multi_step",
        multi_step_checkpoint_objective="rollout_loss",
        checkpoint_selection_metric="balanced",
    )
    one_step_args = argparse.Namespace(
        training_objective="multi_step",
        multi_step_checkpoint_objective="one_step",
        checkpoint_selection_metric="balanced",
    )

    assert checkpoint_selection_label(rollout_args) == "multi_step_rollout_loss"
    assert checkpoint_selection_label(one_step_args) == "multi_step_one_step_balanced"
    assert (
        checkpoint_selection_objective(
            args=rollout_args,
            validation_rollout_loss=-2.0,
            validation_one_step_objective=0.75,
        )
        == -2.0
    )
    assert (
        checkpoint_selection_objective(
            args=one_step_args,
            validation_rollout_loss=-2.0,
            validation_one_step_objective=0.75,
        )
        == 0.75
    )


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
            "--context-columns",
            "irc",
            "--irc-loss-weight",
            "0.25",
            "--checkpoint-selection-metric",
            "balanced_irc",
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
    assert manifest["config"]["context_columns"] == IRC_CONTEXT_COLUMNS
    assert manifest["config"]["input_dim"] == len(INPUT_COLUMNS) + len(IRC_CONTEXT_COLUMNS)
    assert manifest["config"]["irc_loss_weight"] == 0.25
    assert manifest["selection"]["one_step_checkpoint_selection_metric"] == "balanced_irc"
    assert manifest["selection"]["best_validation_irc_rmse"] is not None
    assert manifest["row_counts"]["sampled_windows"]["train"] == 8
    assert manifest["outputs"]
    assert "PIPE Neural ODE History Training Report v1" in report
