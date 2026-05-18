#!/usr/bin/env python
"""Generate recursive PIPE/GRU-D rollouts and alert summaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import joblib
import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, PIPE_STATE_COLUMNS, TARGET_COLUMNS
from src.experiments.train_pipe_grud import (
    MODEL_VERSION as PIPE_MODEL_VERSION,
    STATE_TARGET_NAMES,
    apply_output_blend,
    load_sequences,
    make_model,
    prepare_window_frame,
    _require_torch,
)


DEFAULT_SEQUENCES = Path("data/pipe_grud/pipe_sequence_dataset_v0.parquet")
DEFAULT_MODEL = Path("models/pipe_grud/pipe_grud_model_v0.pt")
DEFAULT_MODEL_MANIFEST = Path("reports/pipe_grud/pipe_grud_manifest.json")
DEFAULT_FUZZY_CALIBRATORS_DIR = Path("models/anfis/calibrators")
DEFAULT_OUTPUT_DIR = Path("data/pipe_grud")
DEFAULT_REPORT_DIR = Path("reports/pipe_grud")
DEFAULT_ROLLOUTS = DEFAULT_OUTPUT_DIR / "pipe_rollout_alerts_v0.parquet"
DEFAULT_SUMMARY = DEFAULT_REPORT_DIR / "pipe_rollout_alert_summary.csv"
DEFAULT_TOP_ALERTS = DEFAULT_REPORT_DIR / "pipe_rollout_top_alerts.csv"
DEFAULT_RECENT_TOP_ALERTS = DEFAULT_REPORT_DIR / "pipe_rollout_recent_top_alerts.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_rollout_alert_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_rollout_alert_manifest.json"

ROLLOUT_VERSION = "pipe_grud_rollout_alerts_v0"
Z90 = 1.6448536269514722


@dataclass(frozen=True)
class CalibratorInfo:
    path: Path
    calibrator: Any
    threshold: float


def _format_int(value: int) -> str:
    return f"{value:,}"


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=_json_default)
        handle.write("\n")
    tmp_path.replace(path)


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp_path, index=False)
    tmp_path.replace(path)


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.unlink(missing_ok=True)
    try:
        frame.to_parquet(tmp_path, index=False)
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def _write_text_atomic(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _clip01(values: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def _elapsed(started: float) -> str:
    return f"{time.monotonic() - started:,.1f}s"


def _season_features_from_month(month: np.ndarray) -> np.ndarray:
    month_float = np.asarray(month, dtype="float32")
    radians = 2.0 * np.pi * (month_float - 1.0) / 12.0
    return np.column_stack(
        [
            np.sin(radians),
            np.cos(radians),
            np.sin(2.0 * radians),
            np.cos(2.0 * radians),
        ]
    ).astype("float32")


def compute_irc(states: np.ndarray, *, alpha: float, beta: float, gamma: float) -> np.ndarray:
    denominator = alpha + beta + gamma
    if denominator <= 0:
        raise ValueError("IRC weights must sum to a positive value")
    y_n = states[..., 0]
    y_f = states[..., 1]
    y_t = states[..., 2]
    return _clip01((alpha * y_n + beta * (1.0 - y_f) + gamma * y_t) / denominator)


def alert_band(probability: pd.Series) -> pd.Series:
    return pd.cut(
        probability.clip(0.0, 1.0),
        bins=[-np.inf, 0.10, 0.25, 0.50, 0.75, np.inf],
        labels=["very_low", "watch", "elevated", "high", "very_high"],
    ).astype("object")


def _load_model(path: Path, device: Any) -> tuple[Any, dict[str, Any], dict[str, Any], Any | None]:
    torch = _require_torch()
    payload = torch.load(path, map_location=device, weights_only=False)
    if payload.get("model_version") != PIPE_MODEL_VERSION:
        raise ValueError(f"Unsupported model version: {payload.get('model_version')!r}")
    input_columns = list(payload.get("input_columns", INPUT_COLUMNS))
    target_columns = list(payload.get("target_columns", TARGET_COLUMNS))
    if input_columns != INPUT_COLUMNS:
        raise ValueError("Model input columns do not match the current PIPE sequence schema")
    if target_columns != TARGET_COLUMNS:
        raise ValueError("Model target columns do not match the current PIPE sequence schema")

    config = dict(payload["config"])
    model = make_model(
        input_dim=len(input_columns),
        target_dim=len(target_columns),
        hidden_dim=int(config["hidden_dim"]),
        num_layers=int(config["num_layers"]),
        dropout=float(config["dropout"]),
        residual_mode=str(config["residual_mode"]),
    )
    model.load_state_dict(payload["model_state_dict"])
    model.to(device)
    model.eval()

    blend_mapping = dict(payload.get("output_blend_weights") or {})
    blend_tensor = None
    if blend_mapping:
        blend_tensor = torch.tensor(
            [float(blend_mapping[target]) for target in STATE_TARGET_NAMES],
            device=device,
            dtype=torch.float32,
        )
    return model, config, payload, blend_tensor


def load_calibrators(args: argparse.Namespace) -> dict[int, CalibratorInfo]:
    if args.disable_calibrated_bloom:
        return {}
    calibrators: dict[int, CalibratorInfo] = {}
    for horizon in range(1, args.rollout_horizon + 1):
        path = args.fuzzy_calibrators_dir / f"irc1_h{horizon}_isotonic.joblib"
        if not path.exists():
            if args.require_calibrators:
                raise FileNotFoundError(path)
            continue
        payload = joblib.load(path)
        calibrators[horizon] = CalibratorInfo(
            path=path,
            calibrator=payload["calibrator"],
            threshold=float(payload["threshold"]),
        )
    return calibrators


def select_rollout_indices(frame: pd.DataFrame, args: argparse.Namespace, history_length: int) -> np.ndarray:
    eligible = frame[frame["window_position"] >= history_length - 1].copy()
    if args.split != "all":
        eligible = eligible[eligible["split"] == args.split].copy()
    if eligible.empty:
        raise ValueError("No eligible rollout origins found for the requested scope")
    eligible["_origin_period"] = pd.PeriodIndex(eligible["origin_year_month"].astype(str), freq="M").asi8
    eligible = eligible.sort_values(
        ["_origin_period", "source_id", "site_id", "split"],
        ascending=[False, True, True, True],
        kind="mergesort",
    )
    if args.scope == "latest-sites":
        eligible = eligible.drop_duplicates(["source_id", "site_id"], keep="first")
    if args.max_origins is not None:
        eligible = eligible.head(args.max_origins)
    eligible = eligible.sort_values(["source_id", "site_id", "_origin_period"], kind="mergesort")
    return eligible.index.to_numpy(dtype="int64")


def _window_array(x_values: np.ndarray, indices: np.ndarray, history_length: int) -> np.ndarray:
    return np.stack([x_values[index - history_length + 1 : index + 1] for index in indices]).astype("float32")


def _quantile(values: np.ndarray, q: float) -> np.ndarray:
    return np.quantile(values, q, axis=1)


def _calibrate_probabilities(irc_values: np.ndarray, calibrator: CalibratorInfo | None) -> np.ndarray | None:
    if calibrator is None:
        return None
    flat = irc_values.reshape(-1)
    probabilities = calibrator.calibrator.predict(flat)
    return _clip01(probabilities).reshape(irc_values.shape)


def rollout_batch(
    *,
    model: Any,
    blend_weights: Any | None,
    x_windows: np.ndarray,
    origin_months: pd.Series,
    args: argparse.Namespace,
    device: Any,
    generator: Any,
    calibrators: dict[int, CalibratorInfo],
) -> list[pd.DataFrame]:
    torch = _require_torch()
    sample_count = 1 if args.deterministic else int(args.samples)
    if sample_count < 1:
        raise ValueError("--samples must be >= 1")
    window = torch.from_numpy(x_windows).to(device=device, dtype=torch.float32)
    window = window.repeat_interleave(sample_count, dim=0)
    origin_periods = pd.PeriodIndex(origin_months.astype(str), freq="M")
    batch_size = len(origin_months)
    parts: list[pd.DataFrame] = []

    with torch.no_grad():
        for horizon in range(1, args.rollout_horizon + 1):
            mu, logvar = model(window)
            mu = apply_output_blend(mu, window, blend_weights)
            if args.deterministic:
                next_state = mu
            else:
                sigma = torch.sqrt(torch.exp(torch.clamp(logvar, min=-10.0, max=2.0)))
                noise = torch.randn(mu.shape, generator=generator, device=device, dtype=mu.dtype)
                next_state = mu + sigma * noise
            next_state = torch.clamp(next_state, min=0.0, max=1.0)

            target_periods = origin_periods + horizon
            season = _season_features_from_month(target_periods.month.to_numpy())
            season_repeated = np.repeat(season, sample_count, axis=0)
            season_tensor = torch.from_numpy(season_repeated).to(device=device, dtype=torch.float32)
            next_input = torch.cat([next_state, season_tensor], dim=1)
            window = torch.cat([window[:, 1:, :], next_input[:, None, :]], dim=1)

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
    return parts


def build_rollouts(
    frame: pd.DataFrame,
    indices: np.ndarray,
    *,
    model: Any,
    blend_weights: Any | None,
    args: argparse.Namespace,
    history_length: int,
    device: Any,
    calibrators: dict[int, CalibratorInfo],
) -> pd.DataFrame:
    torch = _require_torch()
    generator = torch.Generator(device=device)
    generator.manual_seed(int(args.random_seed))
    x_values = frame[INPUT_COLUMNS].to_numpy(dtype="float32")
    parts: list[pd.DataFrame] = []
    for start in range(0, len(indices), args.batch_size):
        batch_indices = indices[start : start + args.batch_size]
        batch_info = frame.loc[batch_indices].reset_index(drop=True)
        x_windows = _window_array(x_values, batch_indices, history_length)
        batch_parts = rollout_batch(
            model=model,
            blend_weights=blend_weights,
            x_windows=x_windows,
            origin_months=batch_info["origin_year_month"],
            args=args,
            device=device,
            generator=generator,
            calibrators=calibrators,
        )
        identity = batch_info[["source_id", "site_id", "split", "origin_year_month"]].copy()
        origin_states = x_windows[:, -1, : len(PIPE_STATE_COLUMNS)]
        identity["origin_irc1_rollout_basis"] = compute_irc(
            origin_states,
            alpha=args.irc_alpha,
            beta=args.irc_beta,
            gamma=args.irc_gamma,
        )
        for column_index, column in enumerate(PIPE_STATE_COLUMNS):
            identity[f"origin_{column}"] = origin_states[:, column_index]
        for batch_part in batch_parts:
            current = pd.concat([identity.reset_index(drop=True), batch_part.reset_index(drop=True)], axis=1)
            parts.append(current)
    rollouts = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    rollouts.insert(0, "rollout_version", ROLLOUT_VERSION)
    rollouts["pipe_model_version"] = PIPE_MODEL_VERSION
    rollouts["deterministic"] = bool(args.deterministic)
    rollouts["predicted_alert_h"] = rollouts["alert_probability_irc"] >= args.alert_prob_threshold
    rollouts["alert_band"] = alert_band(rollouts["alert_probability_irc"])
    return rollouts


def _quantile_95(values: pd.Series) -> float:
    return float(values.quantile(0.95))


def build_summary(rollouts: pd.DataFrame) -> pd.DataFrame:
    working = rollouts.copy()
    working["_source_site_key"] = working["source_id"].astype(str) + "\x1f" + working["site_id"].astype(str)
    aggregations = {
        "rows": ("alert_probability_irc", "size"),
        "sites": ("site_id", "nunique"),
        "first_origin_year_month": ("origin_year_month", "min"),
        "last_origin_year_month": ("origin_year_month", "max"),
        "first_forecast_year_month": ("forecast_year_month", "min"),
        "last_forecast_year_month": ("forecast_year_month", "max"),
        "predicted_alerts": ("predicted_alert_h", "sum"),
        "mean_alert_probability_irc": ("alert_probability_irc", "mean"),
        "p95_alert_probability_irc": ("alert_probability_irc", _quantile_95),
        "mean_irc": ("irc_mean", "mean"),
        "p95_irc": ("irc_p95", _quantile_95),
        "mean_probability_bloom": ("probability_bloom_mean", "mean"),
    }
    by_source = (
        working.groupby(["source_id", "rollout_horizon_months"], dropna=False)
        .agg(**aggregations)
        .reset_index()
    )
    overall = (
        working.groupby(["rollout_horizon_months"], dropna=False)
        .agg(
            rows=("alert_probability_irc", "size"),
            sites=("_source_site_key", "nunique"),
            first_origin_year_month=("origin_year_month", "min"),
            last_origin_year_month=("origin_year_month", "max"),
            first_forecast_year_month=("forecast_year_month", "min"),
            last_forecast_year_month=("forecast_year_month", "max"),
            predicted_alerts=("predicted_alert_h", "sum"),
            mean_alert_probability_irc=("alert_probability_irc", "mean"),
            p95_alert_probability_irc=("alert_probability_irc", _quantile_95),
            mean_irc=("irc_mean", "mean"),
            p95_irc=("irc_p95", _quantile_95),
            mean_probability_bloom=("probability_bloom_mean", "mean"),
        )
        .reset_index()
    )
    overall.insert(0, "source_id", "all")
    out = pd.concat([overall, by_source], ignore_index=True)
    out["predicted_alert_rate"] = out["predicted_alerts"] / out["rows"]
    out["rows"] = out["rows"].astype("int64")
    out["sites"] = out["sites"].astype("int64")
    out["predicted_alerts"] = out["predicted_alerts"].astype("int64")
    return out.sort_values(["rollout_horizon_months", "source_id"]).reset_index(drop=True)


def build_top_alerts(rollouts: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if top_n <= 0:
        return pd.DataFrame()
    parts = []
    columns = [
        "rank_within_horizon",
        "source_id",
        "site_id",
        "split",
        "origin_year_month",
        "forecast_year_month",
        "rollout_horizon_months",
        "alert_probability_irc",
        "irc_mean",
        "irc_p95",
        "probability_bloom_mean",
        "predicted_alert_h",
        "alert_band",
        "origin_irc1_rollout_basis",
    ]
    for horizon, group in rollouts.groupby("rollout_horizon_months", sort=True):
        ranked = group.copy()
        ranked["_origin_period"] = pd.PeriodIndex(ranked["origin_year_month"].astype(str), freq="M").asi8
        top = ranked.sort_values(
            [
                "alert_probability_irc",
                "probability_bloom_mean",
                "irc_p95",
                "irc_mean",
                "origin_irc1_rollout_basis",
                "_origin_period",
                "source_id",
                "site_id",
            ],
            ascending=[False, False, False, False, False, False, True, True],
            kind="mergesort",
        ).head(top_n)
        top = top.copy()
        top.insert(0, "rank_within_horizon", np.arange(1, len(top) + 1))
        parts.append(top[[column for column in columns if column in top.columns]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=columns)


def build_recent_top_alerts(rollouts: pd.DataFrame, *, top_n: int, recent_months: int) -> pd.DataFrame:
    if recent_months <= 0:
        raise ValueError("recent_months must be positive")
    parts = []
    for horizon, group in rollouts.groupby("rollout_horizon_months", sort=True):
        periods = pd.PeriodIndex(group["origin_year_month"].astype(str), freq="M")
        max_period = periods.max()
        cutoff = max_period - (recent_months - 1)
        recent = group.loc[periods >= cutoff].copy()
        if recent.empty:
            continue
        top = build_top_alerts(recent, top_n)
        top.insert(1, "recent_window_start", str(cutoff))
        top.insert(2, "recent_window_end", str(max_period))
        parts.append(top)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def write_report(
    *,
    args: argparse.Namespace,
    summary: pd.DataFrame,
    top_alerts: pd.DataFrame,
    recent_top_alerts: pd.DataFrame,
    selected_origins: int,
    history_length: int,
    calibrated_horizons: list[int],
    started_at: datetime,
) -> None:
    horizon_rows = summary[summary["source_id"] == "all"].copy()
    lines = [
        "# PIPE/GRU-D Rollout Alert Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        "",
        "## Scope",
        "",
        "This report recursively rolls the frozen PIPE/GRU-D state model forward and aggregates alert statistics.",
        "It is an operational simulation over `S(t)`, not an observed validation/test metric table.",
        "Alert probabilities are the share of sampled trajectories whose IRC reaches the configured threshold.",
        "",
        "## Configuration",
        "",
        f"- Origin scope: `{args.scope}`",
        f"- Split filter: `{args.split}`",
        f"- Selected origins: `{_format_int(selected_origins)}`",
        f"- History length: `{history_length}`",
        f"- Rollout horizon: `{args.rollout_horizon}` month(s)",
        f"- Samples per origin: `{1 if args.deterministic else args.samples}`",
        f"- Deterministic mode: `{bool(args.deterministic)}`",
        f"- IRC weights: alpha=`{args.irc_alpha}`, beta=`{args.irc_beta}`, gamma=`{args.irc_gamma}`",
        f"- IRC alert threshold: `{args.irc_alert_threshold}`",
        f"- Alert probability threshold: `{args.alert_prob_threshold}`",
        f"- Calibrated bloom horizons available: `{calibrated_horizons}`",
        "",
        "## Horizon Summary",
        "",
        "| horizon | rows | sites | origin range | forecast range | predicted alerts | alert rate | mean P(IRC alert) | p95 P(IRC alert) | mean IRC | p95 IRC | mean calibrated bloom probability |",
        "|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(horizon_rows.sort_values("rollout_horizon_months")):
        lines.append(
            f"| {int(row.rollout_horizon_months)} | {_format_int(int(row.rows))} | {_format_int(int(row.sites))} | "
            f"`{row.first_origin_year_month}..{row.last_origin_year_month}` | "
            f"`{row.first_forecast_year_month}..{row.last_forecast_year_month}` | "
            f"{_format_int(int(row.predicted_alerts))} | {_format_float(float(row.predicted_alert_rate))} | "
            f"{_format_float(float(row.mean_alert_probability_irc))} | "
            f"{_format_float(float(row.p95_alert_probability_irc))} | {_format_float(float(row.mean_irc))} | "
            f"{_format_float(float(row.p95_irc))} | {_format_float(float(row.mean_probability_bloom))} |"
        )
    lines.extend(
        [
            "",
            "## Recent Top Alert Preview",
            "",
            f"Recent window: last `{args.recent_months}` months per horizon.",
            "",
            "| horizon | rank | source | site | origin | forecast | P(IRC alert) | IRC p95 | calibrated bloom mean | band |",
            "|---:|---:|---|---|---|---|---:|---:|---:|---|",
        ]
    )
    preview = (
        recent_top_alerts.groupby("rollout_horizon_months", sort=True).head(5)
        if not recent_top_alerts.empty
        else recent_top_alerts
    )
    if preview.empty:
        lines.append("| NA | NA | `NA` | `NA` | `NA` | `NA` | NA | NA | NA | `NA` |")
    else:
        for row in dataframe_rows(preview):
            lines.append(
                f"| {int(row.rollout_horizon_months)} | {int(row.rank_within_horizon)} | `{row.source_id}` | "
                f"`{row.site_id}` | `{row.origin_year_month}` | `{row.forecast_year_month}` | "
                f"{_format_float(float(row.alert_probability_irc))} | {_format_float(float(row.irc_p95))} | "
                f"{_format_float(float(row.probability_bloom_mean))} | `{row.alert_band}` |"
            )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Rollout alerts: `{args.rollouts}`",
            f"- Summary: `{args.summary}`",
            f"- Top alerts: `{args.top_alerts}`",
            f"- Recent top alerts: `{args.recent_top_alerts}`",
            f"- Manifest: `{args.manifest}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(
    *,
    args: argparse.Namespace,
    rollouts: pd.DataFrame,
    summary: pd.DataFrame,
    top_alerts: pd.DataFrame,
    recent_top_alerts: pd.DataFrame,
    model_config: dict[str, Any],
    model_payload: dict[str, Any],
    selected_origins: int,
    history_length: int,
    calibrators: dict[int, CalibratorInfo],
    started_at: datetime,
) -> dict[str, Any]:
    input_paths = [args.sequences, args.model]
    if args.model_manifest.exists():
        input_paths.append(args.model_manifest)
    input_paths.extend(info.path for info in calibrators.values())
    outputs = [args.rollouts, args.summary, args.top_alerts, args.report]
    outputs.insert(3, args.recent_top_alerts)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "status": "completed",
        "rollout_version": ROLLOUT_VERSION,
        "pipe_model_version": model_payload.get("model_version"),
        "config": {
            "scope": args.scope,
            "split": args.split,
            "history_length": int(history_length),
            "rollout_horizon": int(args.rollout_horizon),
            "samples": int(1 if args.deterministic else args.samples),
            "deterministic": bool(args.deterministic),
            "batch_size": int(args.batch_size),
            "max_origins": args.max_origins,
            "irc_alpha": float(args.irc_alpha),
            "irc_beta": float(args.irc_beta),
            "irc_gamma": float(args.irc_gamma),
            "irc_alert_threshold": float(args.irc_alert_threshold),
            "alert_prob_threshold": float(args.alert_prob_threshold),
            "recent_months": int(args.recent_months),
            "random_seed": int(args.random_seed),
            "model_config": model_config,
            "calibrated_bloom_horizons": sorted(calibrators),
        },
        "row_counts": {
            "selected_origins": int(selected_origins),
            "rollout_rows": int(len(rollouts)),
            "summary_rows": int(len(summary)),
            "top_alert_rows": int(len(top_alerts)),
            "recent_top_alert_rows": int(len(recent_top_alerts)),
        },
        "inputs": [_file_record(path) for path in input_paths],
        "outputs": [_file_record(path) for path in outputs],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate recursive PIPE/GRU-D state rollouts and alert summaries.")
    parser.add_argument("--sequences", type=Path, default=DEFAULT_SEQUENCES)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--model-manifest", type=Path, default=DEFAULT_MODEL_MANIFEST)
    parser.add_argument("--fuzzy-calibrators-dir", type=Path, default=DEFAULT_FUZZY_CALIBRATORS_DIR)
    parser.add_argument("--rollouts", type=Path, default=DEFAULT_ROLLOUTS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--top-alerts", type=Path, default=DEFAULT_TOP_ALERTS)
    parser.add_argument("--recent-top-alerts", type=Path, default=DEFAULT_RECENT_TOP_ALERTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--scope", choices=["latest-sites", "all-eligible"], default="latest-sites")
    parser.add_argument("--split", choices=["all", "train", "validation", "test"], default="all")
    parser.add_argument("--history-length", type=int, default=None)
    parser.add_argument("--rollout-horizon", type=int, default=3)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--max-origins", type=int, default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--irc-alpha", type=float, default=0.5)
    parser.add_argument("--irc-beta", type=float, default=0.5)
    parser.add_argument("--irc-gamma", type=float, default=2.0)
    parser.add_argument("--irc-alert-threshold", type=float, default=0.5)
    parser.add_argument("--alert-prob-threshold", type=float, default=0.5)
    parser.add_argument("--top-n", type=int, default=3000)
    parser.add_argument("--recent-months", type=int, default=24)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--disable-calibrated-bloom", action="store_true")
    parser.add_argument("--require-calibrators", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rollout_horizon < 1:
        raise ValueError("--rollout-horizon must be >= 1")
    if args.samples < 1:
        raise ValueError("--samples must be >= 1")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be >= 1")
    if args.recent_months < 1:
        raise ValueError("--recent-months must be >= 1")
    started_at = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()

    torch = _require_torch()
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"using device {device}", flush=True)

    print(f"loading model {args.model}", flush=True)
    model, model_config, model_payload, blend_weights = _load_model(args.model, device)
    history_length = int(args.history_length or model_config["history_length"])
    if history_length < 1:
        raise ValueError("history length must be >= 1")

    print(f"loading sequences {args.sequences}", flush=True)
    frame = load_sequences(args.sequences, max_rows=args.max_rows)
    frame = prepare_window_frame(frame)
    print(f"sequence rows={len(frame):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    calibrators = load_calibrators(args)
    print(f"loaded calibrated bloom horizons={sorted(calibrators)}", flush=True)

    indices = select_rollout_indices(frame, args, history_length)
    print(f"selected rollout origins={len(indices):,}; elapsed={_elapsed(started_monotonic)}", flush=True)

    rollouts = build_rollouts(
        frame,
        indices,
        model=model,
        blend_weights=blend_weights,
        args=args,
        history_length=history_length,
        device=device,
        calibrators=calibrators,
    )
    summary = build_summary(rollouts)
    top_alerts = build_top_alerts(rollouts, args.top_n)
    recent_top_alerts = build_recent_top_alerts(rollouts, top_n=args.top_n, recent_months=args.recent_months)

    _write_parquet_atomic(rollouts, args.rollouts)
    print(f"wrote {args.rollouts} ({len(rollouts):,} rows)", flush=True)
    _write_csv_atomic(summary, args.summary)
    print(f"wrote {args.summary}", flush=True)
    _write_csv_atomic(top_alerts, args.top_alerts)
    print(f"wrote {args.top_alerts}", flush=True)
    _write_csv_atomic(recent_top_alerts, args.recent_top_alerts)
    print(f"wrote {args.recent_top_alerts}", flush=True)
    write_report(
        args=args,
        summary=summary,
        top_alerts=top_alerts,
        recent_top_alerts=recent_top_alerts,
        selected_origins=len(indices),
        history_length=history_length,
        calibrated_horizons=sorted(calibrators),
        started_at=started_at,
    )
    print(f"wrote {args.report}", flush=True)
    manifest = manifest_payload(
        args=args,
        rollouts=rollouts,
        summary=summary,
        top_alerts=top_alerts,
        recent_top_alerts=recent_top_alerts,
        model_config=model_config,
        model_payload=model_payload,
        selected_origins=len(indices),
        history_length=history_length,
        calibrators=calibrators,
        started_at=started_at,
    )
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.manifest}; elapsed={_elapsed(started_monotonic)}", flush=True)


if __name__ == "__main__":
    main()
