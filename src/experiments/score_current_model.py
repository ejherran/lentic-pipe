#!/usr/bin/env python
"""Score all operational monthly panel rows with the frozen current model."""

from __future__ import annotations

import argparse
import gc
import hashlib
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import joblib
import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows, year_month_month, year_month_year

from src.experiments import baselines as baseline_run
from src.experiments import select_baselines
from src.experiments.apply_refined_model import (
    _clip01,
    _file_record,
    _format_float,
    _format_int,
    _write_csv_atomic,
    _write_json_atomic,
    _write_text_atomic,
    load_selection,
    load_source_selection,
)
from src.experiments.refine_expert_fuzzy import (
    META_NUMERIC_FEATURES,
    STATE_FEATURE_COLUMNS,
    add_evidence_features,
    baseline_calibrator_path,
    build_deterministic_candidates,
    fuzzy_calibrator_path,
    load_baseline_selection,
    load_calibrator,
    load_state,
)


DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_STATE = Path("data/fuzzy/state_vector_v0.parquet")
DEFAULT_BASELINE_SELECTION = Path("reports/baselines/baseline_selection.csv")
DEFAULT_BASELINE_MODELS_DIR = Path("models/baselines")
DEFAULT_BASELINE_CALIBRATORS_DIR = Path("models/baselines/calibrators")
DEFAULT_FUZZY_CALIBRATORS_DIR = Path("models/anfis/calibrators")
DEFAULT_REFINED_MODELS_DIR = Path("models/anfis/refined")
DEFAULT_SELECTION = Path("reports/anfis/refined_fuzzy_selection.csv")
DEFAULT_SOURCE_SELECTION = Path("reports/anfis/refined_fuzzy_source_selection.csv")
DEFAULT_CURRENT_REGISTRY = Path("models/anfis/current_model_registry_v0.json")
DEFAULT_CURRENT_MANIFEST = Path("reports/anfis/current_model_manifest.json")
DEFAULT_OUTPUT_DIR = Path("data/fuzzy")
DEFAULT_REPORT_DIR = Path("reports/anfis")
DEFAULT_SCORES = DEFAULT_OUTPUT_DIR / "operational_scores_v0.parquet"
DEFAULT_SUMMARY = DEFAULT_REPORT_DIR / "operational_scores_summary.csv"
DEFAULT_TOP_RISKS = DEFAULT_REPORT_DIR / "operational_top_risks.csv"
DEFAULT_RECENT_TOP_RISKS = DEFAULT_REPORT_DIR / "operational_recent_top_risks.csv"
DEFAULT_LATEST_SITE_TOP_RISKS = DEFAULT_REPORT_DIR / "operational_latest_site_top_risks.csv"
DEFAULT_RECENT_LATEST_SITE_TOP_RISKS = DEFAULT_REPORT_DIR / "operational_recent_latest_site_top_risks.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "operational_scores_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "operational_scores_manifest.json"

MODEL_VERSION = "current_refined_fuzzy_v0"
OPERATIONAL_SCORE_VERSION = "operational_scores_v0"
KEY_COLUMNS = ["source_id", "site_id", "origin_year_month", "horizon_months", "split"]
CORE_SCORE_COLUMNS = ["baseline_calibrated", "irc1_calibrated", "irc1_no_chla_calibrated"]
EVIDENCE_COLUMNS = [
    "full_evidence",
    "exogenous_evidence",
    "evidence_N",
    "evidence_F",
    "evidence_T",
    "evidence_T_no_chla",
]
OUTPUT_COLUMNS = [
    "model_version",
    "operational_score_version",
    "source_id",
    "site_id",
    "origin_year_month",
    "horizon_months",
    "split",
    "current_model_score_name",
    "probability_bloom_h",
    "threshold_bloom_h",
    "predicted_bloom_h",
    "risk_band",
    "source_selector_score_name",
    "source_selector_known_source",
    "source_selector_fallback_score_name",
    "baseline_calibrated",
    "irc1_calibrated",
    "irc1_no_chla_calibrated",
    "source_selector",
    "full_evidence",
    "exogenous_evidence",
    "evidence_N",
    "evidence_F",
    "evidence_T",
    "evidence_T_no_chla",
]


def _parse_blend_weights(value: str) -> list[float]:
    weights = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not weights or any(weight < 0.0 or weight > 1.0 for weight in weights):
        raise ValueError("--blend-weights must contain values between 0 and 1")
    return sorted(set(weights))


def _elapsed(started: float) -> str:
    return f"{time.monotonic() - started:,.1f}s"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_record(path: Path) -> dict[str, Any]:
    if path.is_file():
        return _file_record(path)
    if not path.is_dir():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    files: list[dict[str, Any]] = []
    total_bytes = 0
    for file_path in sorted(item for item in path.rglob("*") if item.is_file() and not item.name.endswith(".tmp")):
        relative_path = file_path.relative_to(path).as_posix()
        file_hash = _sha256_file(file_path)
        file_bytes = file_path.stat().st_size
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
        total_bytes += file_bytes
        files.append(
            {
                "path": file_path.as_posix(),
                "relative_path": relative_path,
                "bytes": file_bytes,
                "sha256": file_hash,
            }
        )
    return {
        "path": path.as_posix(),
        "type": "directory",
        "bytes": total_bytes,
        "sha256": digest.hexdigest(),
        "files": files,
    }


def _score_part_path(scores_path: Path, horizon: int) -> Path:
    return scores_path / f"part-h{horizon:02d}.parquet"


def _write_score_part_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.unlink(missing_ok=True)
    try:
        frame.to_parquet(tmp_path, index=False)
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def _add_origin_date_features(frame: pd.DataFrame, column: str = "origin_year_month") -> pd.DataFrame:
    out = frame.copy()
    out["origin_month"] = year_month_month(out[column]).astype("int16")
    out["origin_year"] = year_month_year(out[column]).astype("int16")
    return out


def _load_panel(path: Path) -> tuple[pd.DataFrame, list[str]]:
    feature_columns = baseline_run._available_feature_columns(path)
    panel = pd.read_parquet(path, columns=baseline_run.FEATURE_KEY_COLUMNS + feature_columns)
    panel = panel.rename(columns={"year_month": "origin_year_month"})
    panel = _add_origin_date_features(panel)
    numeric_columns = panel.select_dtypes(include=[np.number]).columns
    panel[numeric_columns] = panel[numeric_columns].replace([np.inf, -np.inf], np.nan)
    return panel, feature_columns


def _load_splits(path: Path, horizons: list[int]) -> pd.DataFrame:
    splits = pd.read_parquet(path, columns=baseline_run.ID_COLUMNS + baseline_run.TARGET_COLUMNS)
    splits = splits[splits["horizon_months"].isin(horizons)].copy()
    splits["bloom_h"] = splits["bloom_h"].astype(bool).astype("int8")
    splits["target_risk_chla_h"] = pd.to_numeric(splits["target_risk_chla_h"], errors="coerce").clip(0, 1)
    return _add_origin_date_features(splits)


def _make_train_frame(splits: pd.DataFrame, panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    train = splits[(splits["horizon_months"] == horizon) & (splits["split"] == "train")].copy()
    if train.empty:
        raise ValueError(f"No train split rows found for horizon {horizon}")
    frame = train.merge(
        panel,
        on=["source_id", "site_id", "origin_year_month", "origin_month", "origin_year"],
        how="left",
        validate="many_to_one",
    )
    numeric_columns = frame.select_dtypes(include=[np.number]).columns
    frame[numeric_columns] = frame[numeric_columns].replace([np.inf, -np.inf], np.nan)
    return frame


def _score_baseline(
    frame: pd.DataFrame,
    train: pd.DataFrame,
    *,
    selected_model: str,
    horizon: int,
    args: argparse.Namespace,
    numeric_features: list[str],
) -> pd.DataFrame:
    out = frame.copy()
    predict_args = argparse.Namespace(models_dir=args.baseline_models_dir, numeric_features=numeric_features)
    raw_baseline = select_baselines.predict_bloom_probability(out, selected_model, horizon, predict_args, train)
    calibrator, _ = load_calibrator(baseline_calibrator_path(args, selected_model, horizon))
    out["baseline_raw"] = _clip01(raw_baseline)
    out["baseline_calibrated"] = _clip01(calibrator.predict(out["baseline_raw"].to_numpy(dtype="float64")))
    return out


def _add_state_and_fuzzy_scores(frame: pd.DataFrame, state: pd.DataFrame, *, horizon: int, args: argparse.Namespace) -> pd.DataFrame:
    out = frame.merge(
        state,
        on=["source_id", "site_id", "origin_year_month"],
        how="left",
        validate="many_to_one",
    )
    out = add_evidence_features(out)
    for score_name in ["irc1", "irc1_no_chla"]:
        calibrator, _ = load_calibrator(fuzzy_calibrator_path(args, score_name, horizon))
        raw = out[score_name].clip(0.0, 1.0).to_numpy(dtype="float64")
        out[f"{score_name}_calibrated"] = _clip01(calibrator.predict(raw))
    return out


def _needed_score_names(selection_row: pd.Series, source_selection: pd.DataFrame) -> set[str]:
    names = {str(selection_row["score_name"])}
    if not source_selection.empty and "selected_score" in source_selection.columns:
        names.update(source_selection["selected_score"].dropna().astype(str).tolist())
    names.discard("source_selector")
    return names


def _load_meta_candidate_if_needed(
    frame: pd.DataFrame,
    *,
    horizon: int,
    needed_scores: set[str],
    args: argparse.Namespace,
    artifacts: list[Path],
) -> pd.DataFrame:
    if "meta_logistic" not in needed_scores:
        return frame
    path = args.refined_models_dir / f"meta_logistic_h{horizon}.joblib"
    payload = joblib.load(path)
    estimator = payload["estimator"]
    features = payload.get("features", ["source_id"] + META_NUMERIC_FEATURES)
    missing = [column for column in features if column not in frame.columns]
    if missing:
        raise ValueError(f"Meta model h{horizon} requires missing columns: {missing}")
    out = frame.copy()
    out["meta_logistic"] = _clip01(estimator.predict_proba(out[features])[:, 1])
    artifacts.append(path)
    return out


def _infer_source_selector_fallback(source_selection: pd.DataFrame, global_score_name: str) -> str:
    if not source_selection.empty and {"selected_score", "selection_reason"}.issubset(source_selection.columns):
        reasons = source_selection["selection_reason"].fillna("").astype(str).str.contains("fallback", case=False)
        fallback_rows = source_selection[reasons]
        if not fallback_rows.empty:
            return str(fallback_rows["selected_score"].mode().iloc[0])
    if global_score_name != "source_selector":
        return global_score_name
    return "baseline_calibrated"


def _add_source_selector(
    frame: pd.DataFrame,
    *,
    selection_row: pd.Series,
    source_selection: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    out = frame.copy()
    global_score_name = str(selection_row["score_name"])
    fallback_score = _infer_source_selector_fallback(source_selection, global_score_name)
    if fallback_score == "source_selector":
        fallback_score = "baseline_calibrated"
    if fallback_score not in out.columns:
        raise ValueError(f"Source selector fallback score `{fallback_score}` is missing from operational frame")

    selector_map: dict[str, str] = {}
    if not source_selection.empty:
        selector_map = dict(
            zip(
                source_selection["source_id"].astype(str),
                source_selection["selected_score"].astype(str),
                strict=False,
            )
        )
    source_as_text = out["source_id"].astype(str)
    out["source_selector_score_name"] = source_as_text.map(selector_map).fillna(fallback_score)
    out["source_selector_known_source"] = source_as_text.isin(selector_map).astype(bool)
    out["source_selector_fallback_score_name"] = fallback_score

    source_selector = np.empty(len(out), dtype="float64")
    for score_name, index in out.groupby("source_selector_score_name", dropna=False).groups.items():
        score_name = str(score_name)
        if score_name not in out.columns:
            raise ValueError(f"Source selector score `{score_name}` is missing from operational frame")
        positions = np.asarray(index, dtype="int64")
        source_selector[positions] = out.iloc[positions][score_name].to_numpy(dtype="float64")
    out["source_selector"] = _clip01(source_selector)
    return out, fallback_score


def _add_deterministic_candidates(frame: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    out = frame.copy()
    for name, values in build_deterministic_candidates(out, args.blend_weights).items():
        out[name] = values
    return out


def _risk_band(probability: pd.Series) -> pd.Series:
    return pd.cut(
        probability.clip(0.0, 1.0),
        bins=[-np.inf, 0.2, 0.4, 0.6, 0.8, np.inf],
        labels=["very_low", "low", "moderate", "high", "very_high"],
    ).astype("object")


def _build_prediction_output(frame: pd.DataFrame, selection_row: pd.Series) -> pd.DataFrame:
    score_name = str(selection_row["score_name"])
    if score_name not in frame.columns:
        raise ValueError(f"Selected score `{score_name}` is missing from operational frame")
    threshold = float(selection_row["selected_threshold"])
    probability = pd.Series(_clip01(frame[score_name]), index=frame.index)

    out = frame[[column for column in KEY_COLUMNS + CORE_SCORE_COLUMNS + ["source_selector"] + EVIDENCE_COLUMNS if column in frame.columns]].copy()
    out["model_version"] = MODEL_VERSION
    out["operational_score_version"] = OPERATIONAL_SCORE_VERSION
    out["current_model_score_name"] = score_name
    out["probability_bloom_h"] = probability
    out["threshold_bloom_h"] = threshold
    out["predicted_bloom_h"] = probability >= threshold
    out["risk_band"] = _risk_band(probability)
    for column in ["source_selector_score_name", "source_selector_known_source", "source_selector_fallback_score_name"]:
        if column in frame.columns:
            out[column] = frame[column]
    if "source_selector_score_name" not in out.columns:
        out["source_selector_score_name"] = ""
    if "source_selector_known_source" not in out.columns:
        out["source_selector_known_source"] = False
    if "source_selector_fallback_score_name" not in out.columns:
        out["source_selector_fallback_score_name"] = ""
    return out[[column for column in OUTPUT_COLUMNS if column in out.columns]]


def _quantile(percentile: float) -> Any:
    def calculate(values: pd.Series) -> float:
        return float(values.quantile(percentile))

    calculate.__name__ = f"p{int(percentile * 100):02d}"
    return calculate


def build_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    working = predictions.copy()
    working["_source_site_key"] = working["source_id"].astype(str) + "\x1f" + working["site_id"].astype(str)
    grouped = (
        working.groupby(["source_id", "horizon_months"], dropna=False)
        .agg(
            rows=("probability_bloom_h", "size"),
            sites=("site_id", "nunique"),
            first_origin_year_month=("origin_year_month", "min"),
            last_origin_year_month=("origin_year_month", "max"),
            predicted_blooms=("predicted_bloom_h", "sum"),
            mean_probability=("probability_bloom_h", "mean"),
            median_probability=("probability_bloom_h", "median"),
            p90_probability=("probability_bloom_h", _quantile(0.90)),
            p95_probability=("probability_bloom_h", _quantile(0.95)),
            max_probability=("probability_bloom_h", "max"),
            mean_full_evidence=("full_evidence", "mean"),
            mean_exogenous_evidence=("exogenous_evidence", "mean"),
        )
        .reset_index()
    )
    grouped["predicted_bloom_rate"] = grouped["predicted_blooms"] / grouped["rows"]
    overall = (
        working.groupby(["horizon_months"], dropna=False)
        .agg(
            rows=("probability_bloom_h", "size"),
            sites=("_source_site_key", "nunique"),
            first_origin_year_month=("origin_year_month", "min"),
            last_origin_year_month=("origin_year_month", "max"),
            predicted_blooms=("predicted_bloom_h", "sum"),
            mean_probability=("probability_bloom_h", "mean"),
            median_probability=("probability_bloom_h", "median"),
            p90_probability=("probability_bloom_h", _quantile(0.90)),
            p95_probability=("probability_bloom_h", _quantile(0.95)),
            max_probability=("probability_bloom_h", "max"),
            mean_full_evidence=("full_evidence", "mean"),
            mean_exogenous_evidence=("exogenous_evidence", "mean"),
        )
        .reset_index()
    )
    overall.insert(0, "source_id", "all")
    overall["predicted_bloom_rate"] = overall["predicted_blooms"] / overall["rows"]
    return pd.concat([overall, grouped], ignore_index=True).sort_values(["horizon_months", "source_id"]).reset_index(drop=True)


def build_top_risks(predictions: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if top_n <= 0:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    parts = []
    columns = [
        "source_id",
        "site_id",
        "origin_year_month",
        "horizon_months",
        "probability_bloom_h",
        "threshold_bloom_h",
        "threshold_margin",
        "predicted_bloom_h",
        "risk_band",
        "evidence_priority",
        "current_model_score_name",
        "source_selector_score_name",
        "full_evidence",
        "exogenous_evidence",
    ]
    for horizon, group in predictions.groupby("horizon_months", sort=True):
        ranked = group.copy()
        ranked["threshold_margin"] = ranked["probability_bloom_h"] - ranked["threshold_bloom_h"]
        ranked["evidence_priority"] = (
            ranked[["full_evidence", "exogenous_evidence"]]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
            .mean(axis=1)
        )
        ranked["_origin_period"] = pd.PeriodIndex(ranked["origin_year_month"].astype(str), freq="M").asi8
        top = ranked.sort_values(
            [
                "probability_bloom_h",
                "threshold_margin",
                "evidence_priority",
                "full_evidence",
                "exogenous_evidence",
                "_origin_period",
                "source_id",
                "site_id",
                "origin_year_month",
            ],
            ascending=[False, False, False, False, False, False, True, True, True],
            kind="mergesort",
        ).head(top_n).copy()
        top.insert(0, "rank_within_horizon", np.arange(1, len(top) + 1))
        parts.append(top[[column for column in ["rank_within_horizon"] + columns if column in top.columns]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=columns)


def build_recent_top_risks(predictions: pd.DataFrame, *, top_n: int, recent_months: int) -> pd.DataFrame:
    if recent_months <= 0:
        raise ValueError("recent_months must be positive")
    parts = []
    for horizon, group in predictions.groupby("horizon_months", sort=True):
        periods = pd.PeriodIndex(group["origin_year_month"].astype(str), freq="M")
        max_period = periods.max()
        cutoff = max_period - (recent_months - 1)
        recent = group.loc[periods >= cutoff].copy()
        if recent.empty:
            continue
        top = build_top_risks(recent, top_n)
        top.insert(1, "recent_window_start", str(cutoff))
        top.insert(2, "recent_window_end", str(max_period))
        parts.append(top)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def build_latest_site_top_risks(predictions: pd.DataFrame, top_n: int) -> pd.DataFrame:
    ranked = predictions.copy()
    ranked["_origin_period"] = pd.PeriodIndex(ranked["origin_year_month"].astype(str), freq="M").asi8
    latest = (
        ranked.sort_values(
            ["source_id", "site_id", "horizon_months", "_origin_period", "origin_year_month"],
            ascending=[True, True, True, False, False],
            kind="mergesort",
        )
        .drop_duplicates(["source_id", "site_id", "horizon_months"], keep="first")
        .drop(columns=["_origin_period"])
    )
    return build_top_risks(latest, top_n)


def build_recent_latest_site_top_risks(predictions: pd.DataFrame, *, top_n: int, recent_months: int) -> pd.DataFrame:
    if recent_months <= 0:
        raise ValueError("recent_months must be positive")
    parts = []
    for horizon, group in predictions.groupby("horizon_months", sort=True):
        periods = pd.PeriodIndex(group["origin_year_month"].astype(str), freq="M")
        max_period = periods.max()
        cutoff = max_period - (recent_months - 1)
        recent = group.loc[periods >= cutoff].copy()
        if recent.empty:
            continue
        top = build_latest_site_top_risks(recent, top_n)
        top.insert(1, "recent_window_start", str(cutoff))
        top.insert(2, "recent_window_end", str(max_period))
        parts.append(top)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _read_score_part(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def _score_parts_available(scores_path: Path, horizons: list[int]) -> bool:
    return scores_path.is_dir() and all(_score_part_path(scores_path, horizon).exists() for horizon in horizons)


def write_report(
    *,
    args: argparse.Namespace,
    summary: pd.DataFrame,
    top_risks: pd.DataFrame,
    recent_top_risks: pd.DataFrame,
    latest_site_top_risks: pd.DataFrame,
    recent_latest_site_top_risks: pd.DataFrame,
    selected_baselines: pd.DataFrame,
    selection: pd.DataFrame,
    fallback_by_horizon: dict[int, str],
    started_at_utc: str,
) -> None:
    horizon_rows = summary[summary["source_id"] == "all"].copy()
    lines = [
        "# Operational Current Model Scores v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at_utc}`",
        "",
        "## Scope",
        "",
        "Scores every monthly panel row for each selected horizon using the frozen current refined fuzzy model.",
        "These are operational probabilities, not validation/test metrics.",
        "",
        "## Horizon Summary",
        "",
        "| horizon | rows | sites | selected score | threshold | predicted blooms | predicted rate | mean probability | p95 probability | max probability |",
        "|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(horizon_rows.sort_values("horizon_months")):
        selected = selection[selection["horizon_months"] == int(row.horizon_months)].iloc[0]
        lines.append(
            f"| {int(row.horizon_months)} | {_format_int(int(row.rows))} | {_format_int(int(row.sites))} | "
            f"`{selected.score_name}` | {_format_float(float(selected.selected_threshold))} | "
            f"{_format_int(int(row.predicted_blooms))} | {_format_float(float(row.predicted_bloom_rate))} | "
            f"{_format_float(float(row.mean_probability))} | {_format_float(float(row.p95_probability))} | "
            f"{_format_float(float(row.max_probability))} |"
        )

    lines.extend(
        [
            "",
            "## Selected Baselines",
            "",
            "| horizon | baseline model |",
            "|---:|---|",
        ]
    )
    for row in dataframe_rows(selected_baselines.sort_values("horizon_months")):
        lines.append(f"| {int(row.horizon_months)} | `{row.model}` |")

    if fallback_by_horizon:
        lines.extend(
            [
                "",
                "## Source Selector Fallback",
                "",
                "Unknown future sources use the fallback score below until the refinement step is rerun with validation evidence for that source.",
                "",
                "| horizon | fallback score |",
                "|---:|---|",
            ]
        )
        for horizon, fallback in sorted(fallback_by_horizon.items()):
            lines.append(f"| {horizon} | `{fallback}` |")

    lines.extend(
        [
        "",
        "## Outputs",
        "",
            f"- Scores: `{args.scores}`",
            f"- Summary: `{args.summary}`",
            f"- Top risks: `{args.top_risks}`",
            f"- Recent top risks: `{args.recent_top_risks}`",
            f"- Latest-site top risks: `{args.latest_site_top_risks}`",
            f"- Recent latest-site top risks: `{args.recent_latest_site_top_risks}`",
            f"- Manifest: `{args.manifest}`",
            "",
            "Top-risk ranking rule: probability desc; threshold margin desc; evidence priority desc; full evidence desc; exogenous evidence desc; most recent month desc; source/site/date asc.",
            "",
            f"Recent top-risk window: last `{int(args.recent_months)}` months per horizon, anchored on each horizon's latest `origin_year_month`.",
            f"Recent top-risk rows written: `{_format_int(len(recent_top_risks))}`",
            f"Latest-site top-risk rows written: `{_format_int(len(latest_site_top_risks))}`",
            f"Recent latest-site top-risk rows written: `{_format_int(len(recent_latest_site_top_risks))}`",
            f"Top-risk rows written: `{_format_int(len(top_risks))}`",
        ]
    )
    _write_text_atomic("\n".join(lines) + "\n", args.report)


def build_manifest(
    *,
    args: argparse.Namespace,
    total_score_rows: int,
    summary: pd.DataFrame,
    top_risks: pd.DataFrame,
    recent_top_risks: pd.DataFrame,
    latest_site_top_risks: pd.DataFrame,
    recent_latest_site_top_risks: pd.DataFrame,
    selected_baselines: pd.DataFrame,
    selection: pd.DataFrame,
    source_selection: pd.DataFrame,
    artifacts: list[Path],
    started_at_utc: str,
) -> dict[str, Any]:
    input_paths = [
        args.panel,
        args.splits,
        args.state,
        args.baseline_selection,
        args.selection,
        args.source_selection,
        args.current_registry,
        args.current_manifest,
    ]
    output_paths = [
        args.scores,
        args.summary,
        args.top_risks,
        args.recent_top_risks,
        args.latest_site_top_risks,
        args.recent_latest_site_top_risks,
        args.report,
    ]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at_utc,
        "model_version": MODEL_VERSION,
        "operational_score_version": OPERATIONAL_SCORE_VERSION,
        "row_counts": {
            "score_rows": int(total_score_rows),
            "summary_rows": int(len(summary)),
            "top_risk_rows": int(len(top_risks)),
            "recent_top_risk_rows": int(len(recent_top_risks)),
            "latest_site_top_risk_rows": int(len(latest_site_top_risks)),
            "recent_latest_site_top_risk_rows": int(len(recent_latest_site_top_risks)),
            "selected_baseline_rows": int(len(selected_baselines)),
            "selection_rows": int(len(selection)),
            "source_selection_rows": int(len(source_selection)),
        },
        "config": {
            "horizons": [int(horizon) for horizon in args.horizons],
            "blend_weights": [float(weight) for weight in args.blend_weights],
            "top_n": int(args.top_n),
            "recent_months": int(args.recent_months),
        },
        "inputs": [_file_record(path) for path in input_paths if path.exists()],
        "model_artifacts": [_file_record(path) for path in sorted(set(artifacts), key=lambda item: item.as_posix()) if path.exists()],
        "outputs": [_path_record(path) for path in output_paths if path.exists()],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--baseline-selection", type=Path, default=DEFAULT_BASELINE_SELECTION)
    parser.add_argument("--baseline-models-dir", type=Path, default=DEFAULT_BASELINE_MODELS_DIR)
    parser.add_argument("--baseline-calibrators-dir", type=Path, default=DEFAULT_BASELINE_CALIBRATORS_DIR)
    parser.add_argument("--fuzzy-calibrators-dir", type=Path, default=DEFAULT_FUZZY_CALIBRATORS_DIR)
    parser.add_argument("--refined-models-dir", type=Path, default=DEFAULT_REFINED_MODELS_DIR)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--source-selection", type=Path, default=DEFAULT_SOURCE_SELECTION)
    parser.add_argument("--current-registry", type=Path, default=DEFAULT_CURRENT_REGISTRY)
    parser.add_argument("--current-manifest", type=Path, default=DEFAULT_CURRENT_MANIFEST)
    parser.add_argument("--scores", type=Path, default=DEFAULT_SCORES)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--top-risks", type=Path, default=DEFAULT_TOP_RISKS)
    parser.add_argument("--recent-top-risks", type=Path, default=DEFAULT_RECENT_TOP_RISKS)
    parser.add_argument("--latest-site-top-risks", type=Path, default=DEFAULT_LATEST_SITE_TOP_RISKS)
    parser.add_argument("--recent-latest-site-top-risks", type=Path, default=DEFAULT_RECENT_LATEST_SITE_TOP_RISKS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--horizons", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--blend-weights", default="0.25,0.5,0.75")
    parser.add_argument("--top-n", type=int, default=1000)
    parser.add_argument("--recent-months", type=int, default=24)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> None:
    started = time.monotonic()
    started_at_utc = datetime.now(timezone.utc).isoformat()
    args = parse_args()
    args.blend_weights = _parse_blend_weights(args.blend_weights)
    args.horizons = sorted(set(int(horizon) for horizon in args.horizons))

    selected_baselines = load_baseline_selection(args.baseline_selection)
    selection = load_selection(args.selection)
    source_selection = load_source_selection(args.source_selection)

    selected_baselines = selected_baselines[selected_baselines["horizon_months"].isin(args.horizons)].copy()
    selection = selection[selection["horizon_months"].isin(args.horizons)].copy()
    if selected_baselines["horizon_months"].nunique() != len(args.horizons):
        missing = sorted(set(args.horizons).difference(selected_baselines["horizon_months"].astype(int)))
        raise ValueError(f"Missing selected bloom baseline for horizons: {missing}")
    if selection["horizon_months"].nunique() != len(args.horizons):
        missing = sorted(set(args.horizons).difference(selection["horizon_months"].astype(int)))
        raise ValueError(f"Missing refined current-model selection for horizons: {missing}")

    if args.scores.exists() and not args.scores.is_dir():
        raise ValueError(f"Scores output path must be a directory for resumable scoring: {args.scores}")
    args.scores.mkdir(parents=True, exist_ok=True)

    all_parts_available = bool(args.resume and _score_parts_available(args.scores, args.horizons))
    panel: pd.DataFrame | None = None
    splits: pd.DataFrame | None = None
    state: pd.DataFrame | None = None
    numeric_features: list[str] = []
    if all_parts_available:
        print(f"all score parts already exist in {args.scores}; rebuilding reports only", flush=True)
    else:
        print(f"loading panel {args.panel}", flush=True)
        panel, available_features = _load_panel(args.panel)
        numeric_features = baseline_run.feature_columns_for_model(available_features)
        print(f"panel rows={len(panel):,}; elapsed={_elapsed(started)}", flush=True)
        print(f"loading splits {args.splits}", flush=True)
        splits = _load_splits(args.splits, args.horizons)
        print(f"split rows={len(splits):,}; elapsed={_elapsed(started)}", flush=True)
        print(f"loading state {args.state}", flush=True)
        state = load_state(args.state)
        print(f"state rows={len(state):,}; elapsed={_elapsed(started)}", flush=True)

    summary_parts: list[pd.DataFrame] = []
    top_risk_parts: list[pd.DataFrame] = []
    recent_top_risk_parts: list[pd.DataFrame] = []
    latest_site_top_risk_parts: list[pd.DataFrame] = []
    recent_latest_site_top_risk_parts: list[pd.DataFrame] = []
    artifact_paths: list[Path] = []
    fallback_by_horizon: dict[int, str] = {}
    for position, horizon in enumerate(args.horizons, start=1):
        horizon_started = time.monotonic()
        selected_model = str(selected_baselines.loc[selected_baselines["horizon_months"] == horizon, "model"].iloc[0])
        selection_row = selection.loc[selection["horizon_months"] == horizon].iloc[0]
        horizon_source_selection = source_selection[source_selection["horizon_months"] == horizon].copy()
        part_path = _score_part_path(args.scores, horizon)
        needed_scores = _needed_score_names(selection_row, horizon_source_selection)
        fallback_score = _infer_source_selector_fallback(horizon_source_selection, str(selection_row["score_name"]))
        if str(selection_row["score_name"]) == "source_selector" or not horizon_source_selection.empty:
            fallback_by_horizon[horizon] = fallback_score
        baseline_artifact = args.baseline_models_dir / f"{selected_model}_h{horizon}.joblib"
        if baseline_artifact.exists():
            artifact_paths.append(baseline_artifact)
        artifact_paths.append(baseline_calibrator_path(args, selected_model, horizon))
        artifact_paths.append(fuzzy_calibrator_path(args, "irc1", horizon))
        artifact_paths.append(fuzzy_calibrator_path(args, "irc1_no_chla", horizon))
        if "meta_logistic" in needed_scores:
            artifact_paths.append(args.refined_models_dir / f"meta_logistic_h{horizon}.joblib")
        if args.resume and part_path.exists():
            print(
                f"h{horizon} ({position}/{len(args.horizons)}): reusing existing score part {part_path}",
                flush=True,
            )
            horizon_predictions = _read_score_part(part_path)
            summary_parts.append(build_summary(horizon_predictions))
            top_risk_parts.append(build_top_risks(horizon_predictions, args.top_n))
            recent_top_risk_parts.append(
                build_recent_top_risks(horizon_predictions, top_n=args.top_n, recent_months=args.recent_months)
            )
            latest_site_top_risk_parts.append(build_latest_site_top_risks(horizon_predictions, args.top_n))
            recent_latest_site_top_risk_parts.append(
                build_recent_latest_site_top_risks(
                    horizon_predictions,
                    top_n=args.top_n,
                    recent_months=args.recent_months,
                )
            )
            del horizon_predictions
            gc.collect()
            print(f"h{horizon}: resumed in {_elapsed(horizon_started)}; total elapsed={_elapsed(started)}", flush=True)
            continue

        if panel is None or splits is None or state is None:
            raise RuntimeError(f"Missing score part for h{horizon}, but input data was not loaded")
        print(
            f"h{horizon} ({position}/{len(args.horizons)}): scoring {len(panel):,} panel rows with baseline `{selected_model}`",
            flush=True,
        )
        train = _make_train_frame(splits, panel, horizon)
        frame = panel.copy()
        frame["horizon_months"] = horizon
        frame["split"] = "operational"
        frame = _score_baseline(
            frame,
            train,
            selected_model=selected_model,
            horizon=horizon,
            args=args,
            numeric_features=numeric_features,
        )

        frame = _add_state_and_fuzzy_scores(frame, state, horizon=horizon, args=args)
        frame = _add_deterministic_candidates(frame, args)

        frame = _load_meta_candidate_if_needed(
            frame,
            horizon=horizon,
            needed_scores=needed_scores,
            args=args,
            artifacts=artifact_paths,
        )
        frame, fallback_score = _add_source_selector(
            frame,
            selection_row=selection_row,
            source_selection=horizon_source_selection,
        )

        horizon_predictions = _build_prediction_output(frame, selection_row)
        _write_score_part_atomic(horizon_predictions, part_path)
        summary_parts.append(build_summary(horizon_predictions))
        top_risk_parts.append(build_top_risks(horizon_predictions, args.top_n))
        recent_top_risk_parts.append(
            build_recent_top_risks(horizon_predictions, top_n=args.top_n, recent_months=args.recent_months)
        )
        latest_site_top_risk_parts.append(build_latest_site_top_risks(horizon_predictions, args.top_n))
        recent_latest_site_top_risk_parts.append(
            build_recent_latest_site_top_risks(
                horizon_predictions,
                top_n=args.top_n,
                recent_months=args.recent_months,
            )
        )
        print(
            f"h{horizon}: wrote {part_path}; rows={len(horizon_predictions):,}; completed in {_elapsed(horizon_started)}; total elapsed={_elapsed(started)}",
            flush=True,
        )
        del train, frame, horizon_predictions
        gc.collect()

    summary = pd.concat(summary_parts, ignore_index=True).sort_values(["horizon_months", "source_id"]).reset_index(drop=True)
    top_risks = pd.concat(top_risk_parts, ignore_index=True) if top_risk_parts else pd.DataFrame()
    recent_top_risks = pd.concat(recent_top_risk_parts, ignore_index=True) if recent_top_risk_parts else pd.DataFrame()
    latest_site_top_risks = (
        pd.concat(latest_site_top_risk_parts, ignore_index=True) if latest_site_top_risk_parts else pd.DataFrame()
    )
    recent_latest_site_top_risks = (
        pd.concat(recent_latest_site_top_risk_parts, ignore_index=True)
        if recent_latest_site_top_risk_parts
        else pd.DataFrame()
    )
    total_score_rows = int(summary.loc[summary["source_id"] == "all", "rows"].sum())
    print(f"building final reports for {total_score_rows:,} operational score rows", flush=True)

    _write_csv_atomic(summary, args.summary)
    _write_csv_atomic(top_risks, args.top_risks)
    _write_csv_atomic(recent_top_risks, args.recent_top_risks)
    _write_csv_atomic(latest_site_top_risks, args.latest_site_top_risks)
    _write_csv_atomic(recent_latest_site_top_risks, args.recent_latest_site_top_risks)
    write_report(
        args=args,
        summary=summary,
        top_risks=top_risks,
        recent_top_risks=recent_top_risks,
        latest_site_top_risks=latest_site_top_risks,
        recent_latest_site_top_risks=recent_latest_site_top_risks,
        selected_baselines=selected_baselines,
        selection=selection,
        fallback_by_horizon=fallback_by_horizon,
        started_at_utc=started_at_utc,
    )
    manifest = build_manifest(
        args=args,
        total_score_rows=total_score_rows,
        summary=summary,
        top_risks=top_risks,
        recent_top_risks=recent_top_risks,
        latest_site_top_risks=latest_site_top_risks,
        recent_latest_site_top_risks=recent_latest_site_top_risks,
        selected_baselines=selected_baselines,
        selection=selection,
        source_selection=source_selection,
        artifacts=artifact_paths,
        started_at_utc=started_at_utc,
    )
    _write_json_atomic(manifest, args.manifest)

    print(f"wrote {args.scores}", flush=True)
    print(f"wrote {args.summary}", flush=True)
    print(f"wrote {args.top_risks}", flush=True)
    print(f"wrote {args.recent_top_risks}", flush=True)
    print(f"wrote {args.latest_site_top_risks}", flush=True)
    print(f"wrote {args.recent_latest_site_top_risks}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)
    print(f"done; elapsed={_elapsed(started)}", flush=True)


if __name__ == "__main__":
    main()
