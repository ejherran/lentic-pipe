#!/usr/bin/env python
"""Backtest direct multi-gap PIPE Neural ODE v2 forecasts against observed states."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, PIPE_STATE_COLUMNS, SEASON_COLUMNS, TARGET_COLUMNS
from src.experiments.evaluate_pipe_grud_rollouts import (
    attach_observations,
    build_alert_metrics,
    build_examples,
    build_state_metrics,
    compact_backtest_rows,
    load_bloom_targets,
    observed_state_frame,
    write_table_atomic,
    _future_availability,
)
from src.experiments.evaluate_pipe_neural_ode_rollouts import load_reference_origin_filter
from src.experiments.rollout_pipe_grud import (
    DEFAULT_FUZZY_CALIBRATORS_DIR,
    alert_band,
    compute_irc,
    load_calibrators,
    _calibrate_probabilities,
    _elapsed,
    _file_record,
    _format_float,
    _format_int,
    _quantile,
    _write_csv_atomic,
    _write_json_atomic,
    _write_text_atomic,
)
from src.experiments.train_pipe_grud import prepare_window_frame, _require_torch
from src.experiments.train_pipe_neural_ode import STATE_INPUT_COLUMNS, _bound_state_tensor
from src.experiments.train_pipe_neural_ode_v1 import load_history_sequences
from src.experiments.train_pipe_neural_ode_v2 import (
    MODEL_VERSION as PIPE_NEURAL_ODE_CONTINUOUS_MODEL_VERSION,
    apply_output_blend_v2,
    make_continuous_time_neural_ode_model,
)


DEFAULT_SEQUENCES = Path("data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_BRANCH = "adaptive_wqp_focused_continuous_v2_full_direct_h123"
DEFAULT_MODEL = Path("models/pipe_neural_ode") / DEFAULT_BRANCH / "pipe_neural_ode_continuous_model_v2.pt"
DEFAULT_MODEL_MANIFEST = (
    Path("reports/pipe_neural_ode") / DEFAULT_BRANCH / "pipe_neural_ode_continuous_manifest.json"
)
DEFAULT_REPORT_DIR = Path("reports/pipe_neural_ode") / DEFAULT_BRANCH
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_direct_backtest_metrics.csv"
DEFAULT_ALERT_METRICS = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_direct_backtest_alert_metrics.csv"
DEFAULT_EXAMPLES = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_direct_backtest_examples.csv"
DEFAULT_BACKTEST_ROWS = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_direct_backtest_rows.parquet"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_direct_backtest_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_neural_ode_continuous_direct_backtest_manifest.json"

DIRECT_VERSION = "pipe_neural_ode_continuous_direct_v2"
DIRECT_BACKTEST_VERSION = "pipe_neural_ode_continuous_direct_backtest_v2"


def _origin_month_positions(months: pd.Series) -> np.ndarray:
    periods = pd.PeriodIndex(months.astype(str), freq="M")
    return np.asarray([period.month - 1 for period in periods], dtype="float32")


def _has_direct_future(frame: pd.DataFrame, frame_indices: np.ndarray, horizon: int) -> np.ndarray:
    run_ids = frame["window_run_id"].to_numpy(dtype="int64")
    positions = frame["window_position"].to_numpy(dtype="int64")
    out = np.zeros(len(frame_indices), dtype=bool)
    last_index = len(frame) - 1
    for position, frame_index in enumerate(frame_indices):
        target_index = int(frame_index) + int(horizon) - 1
        if target_index > last_index:
            continue
        if run_ids[target_index] != run_ids[int(frame_index)]:
            continue
        if positions[target_index] != positions[int(frame_index)] + int(horizon) - 1:
            continue
        out[position] = True
    return out


def _initial_windows(
    x_values: np.ndarray,
    frame_indices: np.ndarray,
    history_length: int,
) -> np.ndarray:
    windows: list[np.ndarray] = []
    for frame_index in frame_indices:
        start_index = int(frame_index) - history_length + 1
        if start_index < 0:
            raise ValueError("Selected origin does not have enough history for Neural ODE v2 direct backtest")
        windows.append(x_values[start_index : int(frame_index) + 1])
    if not windows:
        return np.empty((0, history_length, x_values.shape[1]), dtype="float32")
    return np.stack(windows).astype("float32")


def _load_model(path: Path, device: Any) -> tuple[Any, dict[str, Any], dict[str, Any], Any | None]:
    torch = _require_torch()
    payload = torch.load(path, map_location=device, weights_only=False)
    model_version = payload.get("model_version")
    if model_version != PIPE_NEURAL_ODE_CONTINUOUS_MODEL_VERSION:
        raise ValueError(f"Unsupported Neural ODE v2 direct model version: {model_version!r}")

    input_columns = list(payload.get("input_columns", INPUT_COLUMNS))
    target_columns = list(payload.get("target_columns", TARGET_COLUMNS))
    state_input_columns = list(payload.get("state_input_columns", STATE_INPUT_COLUMNS))
    season_columns = list(payload.get("season_columns", SEASON_COLUMNS))
    if input_columns[: len(INPUT_COLUMNS)] != INPUT_COLUMNS:
        raise ValueError("Model input columns do not start with the current PIPE sequence schema")
    if target_columns != TARGET_COLUMNS:
        raise ValueError("Model target columns do not match the current PIPE sequence schema")
    if state_input_columns != STATE_INPUT_COLUMNS:
        raise ValueError("Model state input columns do not match the Neural ODE v2 schema")
    if season_columns != SEASON_COLUMNS:
        raise ValueError("Model season columns do not match the Neural ODE v2 schema")

    config = dict(payload["config"])
    context_dim = len(input_columns) - len(INPUT_COLUMNS)
    if int(config.get("input_dim", len(input_columns))) != len(input_columns):
        raise ValueError("Model input dimension does not match serialized input columns")
    if int(config.get("context_dim", context_dim)) != context_dim:
        raise ValueError("Model context dimension does not match serialized input columns")

    model = make_continuous_time_neural_ode_model(
        input_dim=len(input_columns),
        state_dim=len(STATE_INPUT_COLUMNS),
        season_dim=len(SEASON_COLUMNS),
        context_dim=context_dim,
        history_hidden_dim=int(config["history_hidden_dim"]),
        history_layers=int(config["history_layers"]),
        latent_dim=int(config["latent_dim"]),
        dynamics_hidden_dim=int(config["dynamics_hidden_dim"]),
        dynamics_depth=int(config["dynamics_depth"]),
        dropout=float(config["dropout"]),
        derivative_scale=float(config["derivative_scale"]),
        state_delta_scale=float(config["state_delta_scale"]),
        ode_method=str(config["ode_method"]),
        ode_step_size=float(config["ode_step_size"]),
        rtol=float(config["rtol"]),
        atol=float(config["atol"]),
    )
    model.load_state_dict(payload["model_state_dict"])
    model.to(device)
    model.eval()

    blend_mapping = dict(payload.get("output_blend_weights") or {})
    blend_tensor = None
    if blend_mapping:
        blend_tensor = torch.tensor(
            [float(blend_mapping[target]) for target in PIPE_STATE_COLUMNS],
            device=device,
            dtype=torch.float32,
        )
    return model, config, payload, blend_tensor


def select_direct_backtest_indices(
    frame: pd.DataFrame,
    args: argparse.Namespace,
    observed: pd.DataFrame,
    reference_origin_filter: pd.DataFrame | None,
    history_length: int,
) -> tuple[np.ndarray, pd.DataFrame]:
    eligible = frame.copy()
    eligible["_frame_index"] = eligible.index.astype("int64")
    eligible = eligible[eligible["window_position"] >= history_length - 1].copy()
    if args.split != "all":
        eligible = eligible[eligible["split"] == args.split].copy()
    if reference_origin_filter is not None:
        eligible = eligible.merge(
            reference_origin_filter,
            on=["source_id", "site_id", "split", "origin_year_month"],
            how="inner",
            validate="many_to_one",
        )
    if eligible.empty:
        raise ValueError("No eligible Neural ODE v2 direct backtest origins found")

    eligible = eligible.sort_values(["source_id", "site_id", "origin_year_month"], kind="mergesort")
    availability, summary = _future_availability(
        frame,
        eligible["_frame_index"].to_numpy(dtype="int64"),
        observed,
        rollout_horizon=args.rollout_horizon,
    )
    for horizon in range(1, args.rollout_horizon + 1):
        availability[f"has_direct_sequence_h{horizon}"] = _has_direct_future(
            frame,
            availability["_frame_index"].to_numpy(dtype="int64"),
            horizon,
        )
        availability[f"has_direct_observed_h{horizon}"] = (
            availability[f"has_observed_h{horizon}"] & availability[f"has_direct_sequence_h{horizon}"]
        )
        summary.loc[
            summary["rollout_horizon_months"] == horizon,
            "origins_with_direct_sequence_future",
        ] = int(availability[f"has_direct_sequence_h{horizon}"].sum())
        summary.loc[
            summary["rollout_horizon_months"] == horizon,
            "origins_with_direct_observed_future",
        ] = int(availability[f"has_direct_observed_h{horizon}"].sum())

    horizon_columns = [f"has_direct_observed_h{horizon}" for horizon in range(1, args.rollout_horizon + 1)]
    if args.allow_partial_horizons:
        selected = availability[availability[horizon_columns].any(axis=1)].copy()
    else:
        selected = availability[availability[horizon_columns].all(axis=1)].copy()
    if selected.empty:
        raise ValueError("No Neural ODE v2 direct origins have complete observed direct futures")

    if args.max_origins is not None and len(selected) > args.max_origins:
        rng = np.random.default_rng(int(args.random_seed))
        selected_positions = rng.choice(selected.index.to_numpy(), size=int(args.max_origins), replace=False)
        selected = selected.loc[np.sort(selected_positions)].copy()

    summary["selected_origins"] = int(len(selected))
    summary["selection_policy"] = "any_direct_observed_horizon" if args.allow_partial_horizons else "complete_direct_horizons"
    return selected["_frame_index"].to_numpy(dtype="int64"), summary


def build_direct_predictions(
    frame: pd.DataFrame,
    indices: np.ndarray,
    *,
    model: Any,
    blend_weights: Any | None,
    model_payload: dict[str, Any],
    args: argparse.Namespace,
    device: Any,
    calibrators: dict[int, Any],
) -> pd.DataFrame:
    torch = _require_torch()
    generator = torch.Generator(device=device)
    generator.manual_seed(int(args.random_seed))
    sample_count = 1 if args.deterministic else int(args.samples)
    if sample_count < 1:
        raise ValueError("--samples must be >= 1")

    input_columns = list(model_payload.get("input_columns", INPUT_COLUMNS))
    history_length = int(model_payload.get("config", {}).get("history_length", 1))
    x_values = frame[input_columns].to_numpy(dtype="float32")
    origin_month_values = _origin_month_positions(frame["origin_year_month"])
    state_values = frame[STATE_INPUT_COLUMNS].to_numpy(dtype="float32")
    origin_periods_all = pd.PeriodIndex(frame["origin_year_month"].astype(str), freq="M")
    parts: list[pd.DataFrame] = []

    for start in range(0, len(indices), args.batch_size):
        batch_indices = indices[start : start + args.batch_size]
        batch_info = frame.loc[batch_indices].reset_index(drop=True)
        batch_state = state_values[batch_indices]
        batch_windows = _initial_windows(x_values, batch_indices, history_length)
        batch_months = origin_month_values[batch_indices]
        origin_periods = origin_periods_all[batch_indices]

        identity = batch_info[["source_id", "site_id", "split", "origin_year_month"]].copy()
        identity["origin_irc1_rollout_basis"] = compute_irc(
            batch_state,
            alpha=args.irc_alpha,
            beta=args.irc_beta,
            gamma=args.irc_gamma,
        )
        for column_index, column in enumerate(PIPE_STATE_COLUMNS):
            identity[f"origin_{column}"] = batch_state[:, column_index]

        x_batch = torch.from_numpy(batch_windows).to(device=device, dtype=torch.float32)
        origin_month_batch = torch.from_numpy(batch_months).to(device=device, dtype=torch.float32)
        with torch.no_grad():
            for horizon in range(1, args.rollout_horizon + 1):
                dt_batch = torch.full((len(batch_indices),), float(horizon), device=device, dtype=torch.float32)
                mu, logvar = model(x_batch, dt_batch, origin_month_batch)
                mu = apply_output_blend_v2(mu, x_batch, blend_weights)
                if args.deterministic:
                    state_samples = mu[:, None, :]
                else:
                    sigma = torch.sqrt(torch.exp(torch.clamp(logvar, min=-10.0, max=2.0)))
                    noise = torch.randn(
                        (mu.shape[0], sample_count, mu.shape[1]),
                        generator=generator,
                        device=device,
                        dtype=mu.dtype,
                    )
                    state_samples = mu[:, None, :] + sigma[:, None, :] * noise
                state_samples = _bound_state_tensor(state_samples)
                states = state_samples.detach().cpu().numpy()
                irc_values = compute_irc(states, alpha=args.irc_alpha, beta=args.irc_beta, gamma=args.irc_gamma)
                calibrated = _calibrate_probabilities(irc_values, calibrators.get(horizon))
                target_periods = origin_periods + horizon
                horizon_frame = pd.DataFrame(
                    {
                        "forecast_year_month": target_periods.astype(str),
                        "rollout_horizon_months": horizon,
                        "samples": sample_count,
                        "irc_mean": irc_values.mean(axis=1),
                        "irc_p05": _quantile(irc_values, 0.05),
                        "irc_p50": _quantile(irc_values, 0.50),
                        "irc_p95": _quantile(irc_values, 0.95),
                        "alert_irc_threshold": float(args.irc_alert_threshold),
                        "alert_probability_irc": (irc_values >= args.irc_alert_threshold).mean(axis=1),
                        "alert_probability_threshold": float(args.alert_prob_threshold),
                    }
                )
                if calibrated is not None:
                    threshold = calibrators[horizon].threshold
                    horizon_frame["probability_bloom_mean"] = calibrated.mean(axis=1)
                    horizon_frame["probability_bloom_p05"] = _quantile(calibrated, 0.05)
                    horizon_frame["probability_bloom_p50"] = _quantile(calibrated, 0.50)
                    horizon_frame["probability_bloom_p95"] = _quantile(calibrated, 0.95)
                    horizon_frame["bloom_probability_threshold_h"] = threshold
                    horizon_frame["predicted_bloom_alert_h"] = horizon_frame["probability_bloom_mean"] >= threshold
                else:
                    horizon_frame["probability_bloom_mean"] = np.nan
                    horizon_frame["probability_bloom_p05"] = np.nan
                    horizon_frame["probability_bloom_p50"] = np.nan
                    horizon_frame["probability_bloom_p95"] = np.nan
                    horizon_frame["bloom_probability_threshold_h"] = np.nan
                    horizon_frame["predicted_bloom_alert_h"] = False
                for column_index, column in enumerate(PIPE_STATE_COLUMNS):
                    values = states[:, :, column_index]
                    horizon_frame[f"{column}_mean"] = values.mean(axis=1)
                    horizon_frame[f"{column}_p05"] = _quantile(values, 0.05)
                    horizon_frame[f"{column}_p95"] = _quantile(values, 0.95)
                parts.append(pd.concat([identity.reset_index(drop=True), horizon_frame.reset_index(drop=True)], axis=1))

    predictions = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    predictions.insert(0, "rollout_version", DIRECT_VERSION)
    predictions["pipe_model_version"] = PIPE_NEURAL_ODE_CONTINUOUS_MODEL_VERSION
    predictions["deterministic"] = bool(args.deterministic)
    predictions["predicted_alert_h"] = predictions["alert_probability_irc"] >= args.alert_prob_threshold
    predictions["alert_band"] = alert_band(predictions["alert_probability_irc"])
    return predictions


def _retag_metric_versions(metrics: pd.DataFrame, alert_metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = metrics.copy()
    alert_metrics = alert_metrics.copy()
    if "backtest_version" in metrics.columns:
        metrics["backtest_version"] = DIRECT_BACKTEST_VERSION
    if "backtest_version" in alert_metrics.columns:
        alert_metrics["backtest_version"] = DIRECT_BACKTEST_VERSION
    return metrics, alert_metrics


def write_report(
    *,
    args: argparse.Namespace,
    metrics: pd.DataFrame,
    alert_metrics: pd.DataFrame,
    availability_summary: pd.DataFrame,
    selected_origins: int,
    evaluated_rows: int,
    model_payload: dict[str, Any],
    started_at: datetime,
) -> None:
    headline = metrics[
        (metrics["group_type"] == "overall") & (metrics["source_id"] == "all") & (metrics["target"].isin(["all", "irc1"]))
    ].copy()
    alert_headline = alert_metrics[
        (alert_metrics["group_type"] == "overall") & (alert_metrics["source_id"] == "all")
    ].copy()
    lines = [
        "# PIPE Neural ODE Continuous-Time Direct Backtest Report v2",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        "",
        "## Scope",
        "",
        "This report evaluates direct multi-gap PIPE Neural ODE v2 forecasts against observed future fuzzy states.",
        "Each h1/h2/h3 prediction starts from the same observed origin history instead of recursively feeding predictions.",
        "",
        "## Configuration",
        "",
        f"- Split filter: `{args.split}`",
        f"- Selected origins: `{_format_int(selected_origins)}`",
        f"- Evaluated direct rows: `{_format_int(evaluated_rows)}`",
        f"- Max origins cap: `{args.max_origins}`",
        f"- Model version: `{model_payload.get('model_version')}`",
        f"- History length: `{model_payload.get('config', {}).get('history_length')}`",
        f"- Direct horizon: `{args.rollout_horizon}` month(s)",
        f"- Observed state source: `{args.observed_state_source}`",
        f"- Reference backtest rows: `{args.reference_backtest_rows}`",
        f"- Samples per origin: `{1 if args.deterministic else args.samples}`",
        f"- Deterministic mode: `{bool(args.deterministic)}`",
        f"- Horizon policy: `{'partial' if args.allow_partial_horizons else 'complete'}`",
        "",
        "## Future Availability",
        "",
        "| horizon | eligible origins | observed future | direct sequence future | direct observed future | selected origins | policy |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in dataframe_rows(availability_summary.sort_values("rollout_horizon_months")):
        lines.append(
            f"| {int(row.rollout_horizon_months)} | {_format_int(int(row.eligible_origins))} | "
            f"{_format_int(int(row.origins_with_observed_future))} | "
            f"{_format_int(int(row.origins_with_direct_sequence_future))} | "
            f"{_format_int(int(row.origins_with_direct_observed_future))} | "
            f"{_format_int(int(row.selected_origins))} | `{row.selection_policy}` |"
        )
    lines.extend(
        [
            "",
            "## State Metrics",
            "",
            "| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if headline.empty:
        lines.append("| `NA` | NA | `NA` | 0 | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(headline.sort_values(["split", "rollout_horizon_months", "target"])):
            lines.append(
                f"| `{row.split}` | {int(row.rollout_horizon_months)} | `{row.target}` | "
                f"{_format_int(int(row.rows))} | {_format_float(row.rmse)} | {_format_float(row.persistence_rmse)} | "
                f"{_format_float(row.rmse_relative_improvement)} | {_format_float(row.mae)} | "
                f"{_format_float(row.simulation_90_coverage)} |"
            )
    lines.extend(
        [
            "",
            "## Alert Metrics",
            "",
            "| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if alert_headline.empty:
        lines.append("| `NA` | `NA` | NA | 0 | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(alert_headline.sort_values(["target_event", "split", "rollout_horizon_months"])):
            lines.append(
                f"| `{row.target_event}` | `{row.split}` | {int(row.rollout_horizon_months)} | "
                f"{_format_int(int(row.rows))} | {_format_float(row.positive_rate)} | "
                f"{_format_float(row.predicted_positive_rate)} | {_format_float(row.pr_auc)} | "
                f"{_format_float(row.brier)} | {_format_float(row.recall)} | {_format_float(row.macro_f1)} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- This is a direct multi-gap backtest, not a recursive rollout.",
            "- Compare it with recursive v1/v0 evidence only after matching origins and keeping the direct/recursive distinction explicit.",
            "- Calibration and 2B policy comparison require a later row-level calibration gate.",
            "",
            "## Outputs",
            "",
            f"- Backtest rows: `{args.backtest_rows}`",
            f"- State metrics: `{args.metrics}`",
            f"- Alert metrics: `{args.alert_metrics}`",
            f"- Diagnostic examples: `{args.examples}`",
            f"- Manifest: `{args.manifest}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(
    *,
    args: argparse.Namespace,
    metrics: pd.DataFrame,
    alert_metrics: pd.DataFrame,
    examples: pd.DataFrame,
    backtest_rows: pd.DataFrame,
    availability_summary: pd.DataFrame,
    selected_origins: int,
    evaluated_rows: int,
    calibrators: dict[int, Any],
    model_config: dict[str, Any],
    model_payload: dict[str, Any],
    started_at: datetime,
) -> dict[str, Any]:
    inputs = [args.sequences, args.model]
    if args.splits.exists():
        inputs.append(args.splits)
    if args.model_manifest.exists():
        inputs.append(args.model_manifest)
    if args.reference_backtest_rows is not None and args.reference_backtest_rows.exists():
        inputs.append(args.reference_backtest_rows)
    inputs.extend(info.path for info in calibrators.values())
    outputs = [args.backtest_rows, args.metrics, args.alert_metrics, args.examples, args.report]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "status": "completed",
        "backtest_version": DIRECT_BACKTEST_VERSION,
        "direct_version": DIRECT_VERSION,
        "pipe_model_version": model_payload.get("model_version", PIPE_NEURAL_ODE_CONTINUOUS_MODEL_VERSION),
        "config": {
            "split": args.split,
            "history_length": int(model_config["history_length"]),
            "rollout_horizon": int(args.rollout_horizon),
            "observed_state_source": args.observed_state_source,
            "reference_backtest_rows": str(args.reference_backtest_rows) if args.reference_backtest_rows else None,
            "samples": int(1 if args.deterministic else args.samples),
            "deterministic": bool(args.deterministic),
            "batch_size": int(args.batch_size),
            "max_origins": args.max_origins,
            "allow_partial_horizons": bool(args.allow_partial_horizons),
            "irc_alpha": float(args.irc_alpha),
            "irc_beta": float(args.irc_beta),
            "irc_gamma": float(args.irc_gamma),
            "irc_alert_threshold": float(args.irc_alert_threshold),
            "alert_prob_threshold": float(args.alert_prob_threshold),
            "random_seed": int(args.random_seed),
            "model_config": model_config,
            "calibrated_bloom_horizons": sorted(calibrators),
        },
        "row_counts": {
            "selected_origins": int(selected_origins),
            "evaluated_direct_rows": int(evaluated_rows),
            "availability_summary_rows": int(len(availability_summary)),
            "backtest_row_export_rows": int(len(backtest_rows)),
            "metric_rows": int(len(metrics)),
            "alert_metric_rows": int(len(alert_metrics)),
            "example_rows": int(len(examples)),
        },
        "inputs": [_file_record(path) for path in inputs if path.exists()],
        "outputs": [_file_record(path) for path in outputs],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", type=Path, default=DEFAULT_SEQUENCES)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--model-manifest", type=Path, default=DEFAULT_MODEL_MANIFEST)
    parser.add_argument("--reference-backtest-rows", type=Path, default=None)
    parser.add_argument("--fuzzy-calibrators-dir", type=Path, default=DEFAULT_FUZZY_CALIBRATORS_DIR)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--alert-metrics", type=Path, default=DEFAULT_ALERT_METRICS)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--backtest-rows", type=Path, default=DEFAULT_BACKTEST_ROWS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--split", choices=["all", "train", "validation", "test"], default="test")
    parser.add_argument("--rollout-horizon", type=int, default=3)
    parser.add_argument("--observed-state-source", choices=["origin_and_target", "target"], default="origin_and_target")
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--max-origins", type=int, default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--examples-per-group", type=int, default=20)
    parser.add_argument("--irc-alpha", type=float, default=0.5)
    parser.add_argument("--irc-beta", type=float, default=0.5)
    parser.add_argument("--irc-gamma", type=float, default=2.0)
    parser.add_argument("--irc-alert-threshold", type=float, default=0.5)
    parser.add_argument("--alert-prob-threshold", type=float, default=0.5)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--disable-calibrated-bloom", action="store_true")
    parser.add_argument("--require-calibrators", action="store_true")
    parser.add_argument("--allow-partial-horizons", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rollout_horizon < 1:
        raise ValueError("--rollout-horizon must be >= 1")
    if args.samples < 1:
        raise ValueError("--samples must be >= 1")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be >= 1")
    if args.max_origins is not None and args.max_origins < 1:
        raise ValueError("--max-origins must be >= 1")

    started_at = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()
    torch = _require_torch()
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"using device {device}", flush=True)

    print(f"loading Neural ODE v2 direct model {args.model}", flush=True)
    model, model_config, model_payload, blend_weights = _load_model(args.model, device)
    input_columns = list(model_payload.get("input_columns", INPUT_COLUMNS))
    print(f"loading sequences {args.sequences}", flush=True)
    frame = load_history_sequences(args.sequences, max_rows=args.max_rows, input_columns=input_columns)
    frame = prepare_window_frame(frame)
    observed = observed_state_frame(frame, source=args.observed_state_source)
    print(f"sequence rows={len(frame):,}; observed states={len(observed):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    reference_origin_filter = load_reference_origin_filter(args.reference_backtest_rows)
    if reference_origin_filter is not None:
        print(f"loaded reference origins={len(reference_origin_filter):,}", flush=True)

    calibrators = load_calibrators(args)
    print(f"loaded calibrated bloom horizons={sorted(calibrators)}", flush=True)

    indices, availability_summary = select_direct_backtest_indices(
        frame,
        args,
        observed,
        reference_origin_filter,
        history_length=int(model_config["history_length"]),
    )
    print(f"selected direct origins={len(indices):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    predictions = build_direct_predictions(
        frame,
        indices,
        model=model,
        blend_weights=blend_weights,
        model_payload=model_payload,
        args=args,
        device=device,
        calibrators=calibrators,
    )
    bloom_targets = load_bloom_targets(args.splits, args.rollout_horizon)
    backtest = attach_observations(predictions, observed, bloom_targets, args=args)
    if backtest.empty:
        raise ValueError("No Neural ODE v2 direct rows could be matched to observed future states")
    print(f"matched observed direct rows={len(backtest):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    metrics, alert_metrics = _retag_metric_versions(build_state_metrics(backtest), build_alert_metrics(backtest))
    examples = build_examples(backtest, args.examples_per_group)
    backtest_rows = compact_backtest_rows(backtest)

    write_table_atomic(backtest_rows, args.backtest_rows)
    print(f"wrote {args.backtest_rows}", flush=True)
    _write_csv_atomic(metrics, args.metrics)
    print(f"wrote {args.metrics}", flush=True)
    _write_csv_atomic(alert_metrics, args.alert_metrics)
    print(f"wrote {args.alert_metrics}", flush=True)
    _write_csv_atomic(examples, args.examples)
    print(f"wrote {args.examples}", flush=True)
    write_report(
        args=args,
        metrics=metrics,
        alert_metrics=alert_metrics,
        availability_summary=availability_summary,
        selected_origins=len(indices),
        evaluated_rows=len(backtest),
        model_payload=model_payload,
        started_at=started_at,
    )
    print(f"wrote {args.report}", flush=True)
    manifest = manifest_payload(
        args=args,
        metrics=metrics,
        alert_metrics=alert_metrics,
        examples=examples,
        backtest_rows=backtest_rows,
        availability_summary=availability_summary,
        selected_origins=len(indices),
        evaluated_rows=len(backtest),
        calibrators=calibrators,
        model_config=model_config,
        model_payload=model_payload,
        started_at=started_at,
    )
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.manifest}; elapsed={_elapsed(started_monotonic)}", flush=True)


if __name__ == "__main__":
    main()
