#!/usr/bin/env python
"""Backtest recursive PIPE Neural ODE rollouts against observed future states."""

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
    _season_features_from_month,
    _write_csv_atomic,
    _write_json_atomic,
    _write_text_atomic,
)
from src.experiments.train_pipe_grud import load_sequences, _require_torch
from src.experiments.train_pipe_neural_ode import (
    MODEL_VERSION as PIPE_NEURAL_ODE_MODEL_VERSION,
    STATE_INPUT_COLUMNS,
    apply_output_blend,
    make_neural_ode_model,
    prepare_transition_frame,
    _bound_state_tensor,
)


DEFAULT_SEQUENCES = Path("data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_MODEL = Path("models/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_model_v0.pt")
DEFAULT_MODEL_MANIFEST = Path("reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_manifest.json")
DEFAULT_REPORT_DIR = Path("reports/pipe_neural_ode/adaptive_wqp_focused")
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "pipe_neural_ode_rollout_backtest_metrics.csv"
DEFAULT_ALERT_METRICS = DEFAULT_REPORT_DIR / "pipe_neural_ode_rollout_backtest_alert_metrics.csv"
DEFAULT_EXAMPLES = DEFAULT_REPORT_DIR / "pipe_neural_ode_rollout_backtest_examples.csv"
DEFAULT_BACKTEST_ROWS = DEFAULT_REPORT_DIR / "pipe_neural_ode_rollout_backtest_rows.parquet"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_neural_ode_rollout_backtest_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_neural_ode_rollout_backtest_manifest.json"

ROLLOUT_VERSION = "pipe_neural_ode_rollout_v0"
BACKTEST_VERSION = "pipe_neural_ode_rollout_backtest_v0"
STATE_KEY_COLUMNS = ["source_id", "site_id", "split", "observed_year_month"]
REFERENCE_ORIGIN_COLUMNS = ["source_id", "site_id", "split", "origin_year_month"]


def load_reference_origin_filter(path: Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        reference = pd.read_parquet(path)
    elif suffix == ".csv":
        reference = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported reference backtest rows suffix for {path}: expected .parquet or .csv")
    missing = [column for column in REFERENCE_ORIGIN_COLUMNS if column not in reference.columns]
    if missing:
        raise ValueError(f"Reference backtest rows are missing required columns: {missing}")
    reference = reference[REFERENCE_ORIGIN_COLUMNS].drop_duplicates().copy()
    for column in REFERENCE_ORIGIN_COLUMNS:
        reference[column] = reference[column].astype(str)
    if reference.empty:
        raise ValueError("Reference backtest rows do not contain any origins")
    return reference.sort_values(REFERENCE_ORIGIN_COLUMNS).reset_index(drop=True)


def _load_model(path: Path, device: Any) -> tuple[Any, dict[str, Any], dict[str, Any], Any | None]:
    torch = _require_torch()
    payload = torch.load(path, map_location=device, weights_only=False)
    if payload.get("model_version") != PIPE_NEURAL_ODE_MODEL_VERSION:
        raise ValueError(f"Unsupported Neural ODE model version: {payload.get('model_version')!r}")
    input_columns = list(payload.get("input_columns", INPUT_COLUMNS))
    target_columns = list(payload.get("target_columns", TARGET_COLUMNS))
    state_input_columns = list(payload.get("state_input_columns", STATE_INPUT_COLUMNS))
    season_columns = list(payload.get("season_columns", SEASON_COLUMNS))
    if input_columns != INPUT_COLUMNS:
        raise ValueError("Model input columns do not match the current PIPE sequence schema")
    if target_columns != TARGET_COLUMNS:
        raise ValueError("Model target columns do not match the current PIPE sequence schema")
    if state_input_columns != STATE_INPUT_COLUMNS:
        raise ValueError("Model state input columns do not match the Neural ODE rollout schema")
    if season_columns != SEASON_COLUMNS:
        raise ValueError("Model season columns do not match the Neural ODE rollout schema")

    config = dict(payload["config"])
    model = make_neural_ode_model(
        state_dim=len(STATE_INPUT_COLUMNS),
        season_dim=len(SEASON_COLUMNS),
        hidden_dim=int(config["hidden_dim"]),
        depth=int(config["depth"]),
        dropout=float(config["dropout"]),
        derivative_scale=float(config["derivative_scale"]),
        integration_time=float(config["integration_time"]),
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


def select_backtest_indices(
    frame: pd.DataFrame,
    args: argparse.Namespace,
    observed: pd.DataFrame,
    reference_origin_filter: pd.DataFrame | None,
) -> tuple[np.ndarray, pd.DataFrame]:
    eligible = frame.copy()
    eligible["_frame_index"] = eligible.index.astype("int64")
    if args.split != "all":
        eligible = eligible[eligible["split"] == args.split].copy()
    if reference_origin_filter is not None:
        eligible = eligible.merge(
            reference_origin_filter,
            on=REFERENCE_ORIGIN_COLUMNS,
            how="inner",
            validate="many_to_one",
        )
    if eligible.empty:
        raise ValueError("No eligible Neural ODE backtest origins found for the requested split")

    eligible = eligible.sort_values(["source_id", "site_id", "origin_year_month"], kind="mergesort")
    availability, summary = _future_availability(
        frame,
        eligible["_frame_index"].to_numpy(dtype="int64"),
        observed,
        rollout_horizon=args.rollout_horizon,
    )
    horizon_columns = [f"has_observed_h{horizon}" for horizon in range(1, args.rollout_horizon + 1)]
    if args.allow_partial_horizons:
        selected = availability[availability["available_horizons"] > 0].copy()
    else:
        selected = availability[availability[horizon_columns].all(axis=1)].copy()
    if selected.empty:
        raise ValueError("No Neural ODE backtest origins have observed future states for the requested horizon policy")

    if args.max_origins is not None and len(selected) > args.max_origins:
        rng = np.random.default_rng(int(args.random_seed))
        selected_positions = rng.choice(selected.index.to_numpy(), size=int(args.max_origins), replace=False)
        selected = selected.loc[np.sort(selected_positions)].copy()

    summary["selected_origins"] = int(len(selected))
    summary["selection_policy"] = "any_observed_horizon" if args.allow_partial_horizons else "complete_horizons"
    return selected["_frame_index"].to_numpy(dtype="int64"), summary


def rollout_batch(
    *,
    model: Any,
    blend_weights: Any | None,
    state_values: np.ndarray,
    season_values: np.ndarray,
    origin_months: pd.Series,
    args: argparse.Namespace,
    device: Any,
    generator: Any,
    calibrators: dict[int, Any],
) -> list[pd.DataFrame]:
    torch = _require_torch()
    sample_count = 1 if args.deterministic else int(args.samples)
    if sample_count < 1:
        raise ValueError("--samples must be >= 1")
    state = torch.from_numpy(state_values.astype("float32")).to(device=device, dtype=torch.float32)
    season = torch.from_numpy(season_values.astype("float32")).to(device=device, dtype=torch.float32)
    state = state.repeat_interleave(sample_count, dim=0)
    season = season.repeat_interleave(sample_count, dim=0)
    origin_periods = pd.PeriodIndex(origin_months.astype(str), freq="M")
    batch_size = len(origin_months)
    parts: list[pd.DataFrame] = []

    with torch.no_grad():
        for horizon in range(1, args.rollout_horizon + 1):
            mu, logvar = model(state, season)
            mu = apply_output_blend(mu, state, blend_weights)
            if args.deterministic:
                next_state = mu
            else:
                sigma = torch.sqrt(torch.exp(torch.clamp(logvar, min=-10.0, max=2.0)))
                noise = torch.randn(mu.shape, generator=generator, device=device, dtype=mu.dtype)
                next_state = mu + sigma * noise
            next_state = _bound_state_tensor(next_state)

            target_periods = origin_periods + horizon
            states = next_state.detach().cpu().numpy().reshape(batch_size, sample_count, len(PIPE_STATE_COLUMNS))
            irc_values = compute_irc(states, alpha=args.irc_alpha, beta=args.irc_beta, gamma=args.irc_gamma)
            calibrated = _calibrate_probabilities(irc_values, calibrators.get(horizon))
            frame = pd.DataFrame(
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
                frame["probability_bloom_mean"] = calibrated.mean(axis=1)
                frame["probability_bloom_p05"] = _quantile(calibrated, 0.05)
                frame["probability_bloom_p50"] = _quantile(calibrated, 0.50)
                frame["probability_bloom_p95"] = _quantile(calibrated, 0.95)
                frame["bloom_probability_threshold_h"] = threshold
                frame["predicted_bloom_alert_h"] = frame["probability_bloom_mean"] >= threshold
            else:
                frame["probability_bloom_mean"] = np.nan
                frame["probability_bloom_p05"] = np.nan
                frame["probability_bloom_p50"] = np.nan
                frame["probability_bloom_p95"] = np.nan
                frame["bloom_probability_threshold_h"] = np.nan
                frame["predicted_bloom_alert_h"] = False
            for column_index, column in enumerate(PIPE_STATE_COLUMNS):
                values = states[:, :, column_index]
                frame[f"{column}_mean"] = values.mean(axis=1)
                frame[f"{column}_p05"] = _quantile(values, 0.05)
                frame[f"{column}_p95"] = _quantile(values, 0.95)
            parts.append(frame)

            state = next_state
            next_season = _season_features_from_month(target_periods.month.to_numpy())
            next_season = np.repeat(next_season, sample_count, axis=0)
            season = torch.from_numpy(next_season).to(device=device, dtype=torch.float32)
    return parts


def build_rollouts(
    frame: pd.DataFrame,
    indices: np.ndarray,
    *,
    model: Any,
    blend_weights: Any | None,
    args: argparse.Namespace,
    device: Any,
    calibrators: dict[int, Any],
) -> pd.DataFrame:
    torch = _require_torch()
    generator = torch.Generator(device=device)
    generator.manual_seed(int(args.random_seed))
    state_values = frame[STATE_INPUT_COLUMNS].to_numpy(dtype="float32")
    season_values = frame[SEASON_COLUMNS].to_numpy(dtype="float32")
    parts: list[pd.DataFrame] = []
    for start in range(0, len(indices), args.batch_size):
        batch_indices = indices[start : start + args.batch_size]
        batch_info = frame.loc[batch_indices].reset_index(drop=True)
        batch_state = state_values[batch_indices]
        batch_season = season_values[batch_indices]
        batch_parts = rollout_batch(
            model=model,
            blend_weights=blend_weights,
            state_values=batch_state,
            season_values=batch_season,
            origin_months=batch_info["origin_year_month"],
            args=args,
            device=device,
            generator=generator,
            calibrators=calibrators,
        )
        identity = batch_info[["source_id", "site_id", "split", "origin_year_month"]].copy()
        identity["origin_irc1_rollout_basis"] = compute_irc(
            batch_state,
            alpha=args.irc_alpha,
            beta=args.irc_beta,
            gamma=args.irc_gamma,
        )
        for column_index, column in enumerate(PIPE_STATE_COLUMNS):
            identity[f"origin_{column}"] = batch_state[:, column_index]
        for batch_part in batch_parts:
            parts.append(pd.concat([identity.reset_index(drop=True), batch_part.reset_index(drop=True)], axis=1))
    rollouts = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    rollouts.insert(0, "rollout_version", ROLLOUT_VERSION)
    rollouts["pipe_model_version"] = PIPE_NEURAL_ODE_MODEL_VERSION
    rollouts["deterministic"] = bool(args.deterministic)
    rollouts["predicted_alert_h"] = rollouts["alert_probability_irc"] >= args.alert_prob_threshold
    rollouts["alert_band"] = alert_band(rollouts["alert_probability_irc"])
    return rollouts


def _retag_metric_versions(metrics: pd.DataFrame, alert_metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = metrics.copy()
    alert_metrics = alert_metrics.copy()
    if "backtest_version" in metrics.columns:
        metrics["backtest_version"] = BACKTEST_VERSION
    if "backtest_version" in alert_metrics.columns:
        alert_metrics["backtest_version"] = BACKTEST_VERSION
    return metrics, alert_metrics


def write_report(
    *,
    args: argparse.Namespace,
    metrics: pd.DataFrame,
    alert_metrics: pd.DataFrame,
    availability_summary: pd.DataFrame,
    selected_origins: int,
    evaluated_rows: int,
    calibrated_horizons: list[int],
    started_at: datetime,
) -> None:
    headline = metrics[
        (metrics["group_type"] == "overall") & (metrics["source_id"] == "all") & (metrics["target"].isin(["all", "irc1"]))
    ].copy()
    alert_headline = alert_metrics[
        (alert_metrics["group_type"] == "overall") & (alert_metrics["source_id"] == "all")
    ].copy()
    lines = [
        "# PIPE Neural ODE Rollout Backtest Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        "",
        "## Scope",
        "",
        "This report evaluates recursive PIPE Neural ODE rollouts against observed future fuzzy states.",
        "It is a historical backtest and should be compared with PIPE/GRU-D rollout backtests on the same sequence surface.",
        "",
        "## Configuration",
        "",
        f"- Split filter: `{args.split}`",
        f"- Selected origins: `{_format_int(selected_origins)}`",
        f"- Evaluated rollout rows: `{_format_int(evaluated_rows)}`",
        f"- Max origins cap: `{args.max_origins}`",
        f"- Rollout horizon: `{args.rollout_horizon}` month(s)",
        f"- Observed state source: `{args.observed_state_source}`",
        f"- Reference backtest rows: `{args.reference_backtest_rows}`",
        f"- Samples per origin: `{1 if args.deterministic else args.samples}`",
        f"- Deterministic mode: `{bool(args.deterministic)}`",
        f"- Horizon policy: `{'partial' if args.allow_partial_horizons else 'complete'}`",
        f"- IRC weights: alpha=`{args.irc_alpha}`, beta=`{args.irc_beta}`, gamma=`{args.irc_gamma}`",
        f"- IRC alert threshold: `{args.irc_alert_threshold}`",
        f"- Alert probability threshold: `{args.alert_prob_threshold}`",
        f"- Random seed: `{args.random_seed}`",
        f"- Calibrated bloom horizons available: `{calibrated_horizons}`",
        "",
        "## Future Availability",
        "",
        "| horizon | eligible origins | origins with observed future | selected origins | policy |",
        "|---:|---:|---:|---:|---|",
    ]
    for row in dataframe_rows(availability_summary.sort_values("rollout_horizon_months")):
        lines.append(
            f"| {int(row.rollout_horizon_months)} | {_format_int(int(row.eligible_origins))} | "
            f"{_format_int(int(row.origins_with_observed_future))} | {_format_int(int(row.selected_origins))} | "
            f"`{row.selection_policy}` |"
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
            "- This backtest measures historical predictive behavior; it is not an operational deployment artifact.",
            "- Recursive behavior can differ from one-step behavior because each forecast state becomes the next origin state.",
            "- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.",
            "- Source-level rows are diagnostic and can be unstable for sources with limited support.",
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
        "backtest_version": BACKTEST_VERSION,
        "rollout_version": ROLLOUT_VERSION,
        "pipe_model_version": model_payload.get("model_version", PIPE_NEURAL_ODE_MODEL_VERSION),
        "config": {
            "split": args.split,
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
            "evaluated_rollout_rows": int(evaluated_rows),
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

    print(f"loading Neural ODE model {args.model}", flush=True)
    model, model_config, model_payload, blend_weights = _load_model(args.model, device)

    print(f"loading sequences {args.sequences}", flush=True)
    frame = load_sequences(args.sequences, max_rows=args.max_rows)
    frame = prepare_transition_frame(frame)
    observed = observed_state_frame(frame, source=args.observed_state_source)
    print(f"sequence rows={len(frame):,}; observed states={len(observed):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    reference_origin_filter = load_reference_origin_filter(args.reference_backtest_rows)
    if reference_origin_filter is not None:
        print(f"loaded reference origins={len(reference_origin_filter):,}", flush=True)

    calibrators = load_calibrators(args)
    print(f"loaded calibrated bloom horizons={sorted(calibrators)}", flush=True)

    indices, availability_summary = select_backtest_indices(frame, args, observed, reference_origin_filter)
    print(f"selected backtest origins={len(indices):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    rollouts = build_rollouts(
        frame,
        indices,
        model=model,
        blend_weights=blend_weights,
        args=args,
        device=device,
        calibrators=calibrators,
    )
    bloom_targets = load_bloom_targets(args.splits, args.rollout_horizon)
    backtest = attach_observations(rollouts, observed, bloom_targets, args=args)
    if backtest.empty:
        raise ValueError("No Neural ODE rollout rows could be matched to observed future states")
    print(f"matched observed rollout rows={len(backtest):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

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
        calibrated_horizons=sorted(calibrators),
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
