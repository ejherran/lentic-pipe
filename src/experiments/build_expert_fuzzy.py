#!/usr/bin/env python
"""Build expert fuzzy state vector S(t) and IRC1 from the monthly panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows, group_key_tuple
import joblib
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    recall_score,
    roc_auc_score,
)

from src.fuzzy.expert import (
    DEFAULT_IRC_WEIGHTS,
    KEY_COLUMNS,
    build_expert_state,
    compute_irc1,
    membership_spec_table,
    rules_table,
)


DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_OUTPUT_DIR = Path("data/fuzzy")
DEFAULT_REPORT_DIR = Path("reports/anfis")
DEFAULT_STATE = DEFAULT_OUTPUT_DIR / "state_vector_v0.parquet"
DEFAULT_TRACE = DEFAULT_REPORT_DIR / "trace_examples.csv"
DEFAULT_RULES = DEFAULT_REPORT_DIR / "rules.csv"
DEFAULT_MEMBERSHIPS = DEFAULT_REPORT_DIR / "memberships.csv"
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "irc1_metrics.csv"
DEFAULT_CALIBRATED_METRICS = DEFAULT_REPORT_DIR / "irc1_calibrated_metrics.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "anfis_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "fuzzy_manifest.json"
DEFAULT_CALIBRATORS_DIR = Path("models/anfis/calibrators")
SCORE_COLUMNS = ["irc1", "irc1_no_chla"]


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


def _safe_metric(metric_fn: Any, *args: Any, **kwargs: Any) -> float:
    try:
        return float(metric_fn(*args, **kwargs))
    except ValueError:
        return float("nan")


def _safe_corr(left: pd.Series, right: pd.Series, method: str) -> float:
    pair = pd.concat([left, right], axis=1).dropna()
    if pair.shape[0] < 2 or pair.iloc[:, 0].nunique() < 2 or pair.iloc[:, 1].nunique() < 2:
        return float("nan")
    return float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method=method))


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _parse_weight_grid(value: str) -> list[float]:
    out = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not out or any(part <= 0 for part in out):
        raise ValueError("--weight-grid must contain positive numeric values")
    return out


def _candidate_weights(grid: list[float]) -> list[dict[str, float]]:
    return [{"alpha": a, "beta": b, "gamma": c} for a in grid for b in grid for c in grid]


def _load_panel(path: Path, max_rows: int | None = None) -> pd.DataFrame:
    panel = pd.read_parquet(path)
    if max_rows:
        panel = panel.head(max_rows).copy()
    return panel


def _load_splits(path: Path, max_rows: int | None = None) -> pd.DataFrame:
    columns = [
        "source_id",
        "site_id",
        "origin_year_month",
        "horizon_months",
        "split",
        "bloom_h",
        "target_risk_chla_h",
    ]
    splits = pd.read_parquet(path, columns=columns)
    splits["bloom_h"] = splits["bloom_h"].astype(bool).astype("int8")
    splits["target_risk_chla_h"] = pd.to_numeric(splits["target_risk_chla_h"], errors="coerce").clip(0.0, 1.0)
    if max_rows:
        splits = splits.head(max_rows).copy()
    return splits


def fit_irc_weights(
    state: pd.DataFrame,
    splits: pd.DataFrame,
    *,
    grid: list[float],
    max_rows: int,
    random_seed: int,
) -> tuple[dict[str, float], pd.DataFrame]:
    train = splits[splits["split"] == "train"].merge(
        state[["source_id", "site_id", "year_month", "yN", "yF", "yT"]],
        left_on=["source_id", "site_id", "origin_year_month"],
        right_on=["source_id", "site_id", "year_month"],
        how="inner",
    )
    if max_rows and len(train) > max_rows:
        train = train.sample(n=max_rows, random_state=random_seed).copy()
    rows = []
    y = train["bloom_h"].to_numpy(dtype="int8")
    for weights in _candidate_weights(grid):
        score = compute_irc1(train["yN"], train["yF"], train["yT"], weights).to_numpy(dtype="float64")
        rows.append(
            {
                **weights,
                "train_rows": int(len(train)),
                "train_pr_auc": _safe_metric(average_precision_score, y, score),
                "train_brier": _safe_metric(brier_score_loss, y, score),
            }
        )
    search = pd.DataFrame(rows).sort_values(
        ["train_pr_auc", "train_brier", "alpha", "beta", "gamma"],
        ascending=[False, True, True, True, True],
    )
    best = search.iloc[0]
    weights = {"alpha": float(best.alpha), "beta": float(best.beta), "gamma": float(best.gamma)}
    return weights, search.reset_index(drop=True)


def evaluate_current_state(state: pd.DataFrame, score_columns: list[str] | None = None) -> pd.DataFrame:
    score_columns = score_columns or SCORE_COLUMNS
    frame = state[state["risk_chla_current"].notna()].copy()
    if frame.empty:
        return pd.DataFrame()
    rows = []
    groups = [("all", frame)]
    groups.extend((source, group) for source, group in frame.groupby("source_id", dropna=False))
    for score_name in score_columns:
        for source, group in groups:
            rows.append(
                {
                    "metric_scope": "current",
                    "score_name": score_name,
                    "source_id": source,
                    "horizon_months": np.nan,
                    "split": "panel",
                    "rows": int(len(group)),
                    "pearson_score_risk_chla": _safe_corr(group[score_name], group["risk_chla_current"], "pearson"),
                    "spearman_score_risk_chla": _safe_corr(group[score_name], group["risk_chla_current"], "spearman"),
                    "rmse_score_risk_chla": _rmse(
                        group["risk_chla_current"].to_numpy(dtype="float64"),
                        group[score_name].to_numpy(dtype="float64"),
                    ),
                    "mae_score_risk_chla": mean_absolute_error(
                        group["risk_chla_current"].to_numpy(dtype="float64"),
                        group[score_name].to_numpy(dtype="float64"),
                    ),
                    "pr_auc": np.nan,
                    "roc_auc": np.nan,
                    "brier": np.nan,
                    "recall": np.nan,
                    "macro_f1": np.nan,
                }
            )
    return pd.DataFrame(rows)


def evaluate_targets(
    state: pd.DataFrame,
    splits: pd.DataFrame,
    threshold: float,
    score_columns: list[str] | None = None,
) -> pd.DataFrame:
    score_columns = score_columns or SCORE_COLUMNS
    joined = splits.merge(
        state[["source_id", "site_id", "year_month"] + score_columns],
        left_on=["source_id", "site_id", "origin_year_month"],
        right_on=["source_id", "site_id", "year_month"],
        how="inner",
    )
    rows = []
    group_specs = [(["horizon_months", "split"], "all"), (["source_id", "horizon_months", "split"], "source")]
    for score_name in score_columns:
        for group_columns, source_mode in group_specs:
            for keys, group in joined.groupby(group_columns, dropna=False):
                key_parts = group_key_tuple(keys)
                if source_mode == "all":
                    horizon, split = key_parts
                    source_id = "all"
                else:
                    source_id, horizon, split = key_parts
                y = group["bloom_h"].to_numpy(dtype="int8")
                score = group[score_name].clip(0.0, 1.0).to_numpy(dtype="float64")
                predicted = (score >= threshold).astype("int8")
                rows.append(
                    {
                        "metric_scope": "target",
                        "score_name": score_name,
                        "source_id": source_id,
                        "horizon_months": int(horizon),
                        "split": split,
                        "rows": int(len(group)),
                        "pearson_score_risk_chla": np.nan,
                        "spearman_score_risk_chla": np.nan,
                        "rmse_score_risk_chla": _safe_metric(
                            _rmse,
                            group["target_risk_chla_h"].to_numpy(dtype="float64"),
                            score,
                        ),
                        "mae_score_risk_chla": _safe_metric(
                            mean_absolute_error,
                            group["target_risk_chla_h"].to_numpy(dtype="float64"),
                            score,
                        ),
                        "pr_auc": _safe_metric(average_precision_score, y, score),
                        "roc_auc": _safe_metric(roc_auc_score, y, score),
                        "brier": _safe_metric(brier_score_loss, y, score),
                        "recall": _safe_metric(recall_score, y, predicted, zero_division=0),
                        "macro_f1": _safe_metric(f1_score, y, predicted, average="macro", zero_division=0),
                    }
                )
    return pd.DataFrame(rows)


def _candidate_thresholds(probability: np.ndarray) -> np.ndarray:
    quantiles = np.unique(np.quantile(probability, np.linspace(0.01, 0.99, 99)))
    fixed = np.linspace(0.05, 0.95, 19)
    return np.unique(np.concatenate([fixed, quantiles, np.array([0.5])]))


def choose_threshold(y_true: np.ndarray, probability: np.ndarray) -> tuple[float, float]:
    best_threshold = 0.5
    best_score = -1.0
    for threshold in _candidate_thresholds(probability):
        predicted = (probability >= threshold).astype("int8")
        score = f1_score(y_true, predicted, average="macro", zero_division=0)
        if score > best_score:
            best_threshold = float(threshold)
            best_score = float(score)
    return best_threshold, best_score


def evaluate_calibrated_scores(
    state: pd.DataFrame,
    splits: pd.DataFrame,
    *,
    score_columns: list[str] | None,
    calibrators_dir: Path,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    score_columns = score_columns or SCORE_COLUMNS
    joined = splits.merge(
        state[["source_id", "site_id", "year_month"] + score_columns],
        left_on=["source_id", "site_id", "origin_year_month"],
        right_on=["source_id", "site_id", "year_month"],
        how="inner",
    )
    calibrators_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for score_name in score_columns:
        for horizon in sorted(joined["horizon_months"].dropna().unique()):
            horizon_frame = joined[joined["horizon_months"] == horizon].copy()
            validation = horizon_frame[horizon_frame["split"] == "validation"].copy()
            if validation.empty:
                continue
            validation_y = validation["bloom_h"].to_numpy(dtype="int8")
            validation_score = validation[score_name].clip(0.0, 1.0).to_numpy(dtype="float64")
            calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            calibrator.fit(validation_score, validation_y)
            validation_calibrated = calibrator.predict(validation_score).clip(0.0, 1.0)
            threshold, threshold_macro_f1 = choose_threshold(validation_y, validation_calibrated)
            calibrator_path = calibrators_dir / f"{score_name}_h{int(horizon)}_isotonic.joblib"
            joblib.dump(
                {
                    "score_name": score_name,
                    "horizon_months": int(horizon),
                    "calibrator": calibrator,
                    "threshold": threshold,
                    "threshold_selection": "validation max macro-F1 on calibrated IRC probabilities",
                    "threshold_macro_f1_validation": threshold_macro_f1,
                },
                calibrator_path,
            )
            artifacts.append(
                {
                    "score_name": score_name,
                    "horizon_months": int(horizon),
                    "calibration": "isotonic",
                    **_file_record(calibrator_path),
                }
            )
            for split in ["validation", "test"]:
                split_frame = horizon_frame[horizon_frame["split"] == split].copy()
                if split_frame.empty:
                    continue
                calibrated = calibrator.predict(split_frame[score_name].clip(0.0, 1.0).to_numpy(dtype="float64")).clip(0.0, 1.0)
                split_eval = split_frame.copy()
                split_eval["_calibrated_score"] = calibrated
                group_specs = [(None, "all", split_eval)]
                group_specs.extend((source, "source", group) for source, group in split_eval.groupby("source_id", dropna=False))
                for source_id, source_mode, group in group_specs:
                    group_calibrated = group["_calibrated_score"].to_numpy(dtype="float64")
                    y = group["bloom_h"].to_numpy(dtype="int8")
                    predicted = (group_calibrated >= threshold).astype("int8")
                    rows.append(
                        {
                            "metric_scope": "target_calibrated",
                            "score_name": score_name,
                            "source_id": "all" if source_id is None else source_id,
                            "horizon_months": int(horizon),
                            "split": split,
                            "rows": int(len(group)),
                            "threshold": threshold,
                            "pr_auc": _safe_metric(average_precision_score, y, group_calibrated),
                            "roc_auc": _safe_metric(roc_auc_score, y, group_calibrated),
                            "brier": _safe_metric(brier_score_loss, y, group_calibrated),
                            "recall": _safe_metric(recall_score, y, predicted, zero_division=0),
                            "macro_f1": _safe_metric(f1_score, y, predicted, average="macro", zero_division=0),
                        }
                    )
    return pd.DataFrame(rows), artifacts


def trace_examples(trace: pd.DataFrame, state: pd.DataFrame, n: int, random_seed: int) -> pd.DataFrame:
    merged = trace.merge(
        state[
            KEY_COLUMNS
            + [
                "irc1",
                "irc1_no_chla",
                "delta_yN",
                "delta_yF",
                "delta_yT",
                "delta_yT_no_chla",
                "evidence_N",
                "evidence_F",
                "evidence_T",
                "evidence_T_no_chla",
                "state_trophic_expert",
            ]
        ],
        on=KEY_COLUMNS,
        how="left",
        suffixes=("", "_state"),
    )
    if len(merged) <= n:
        return merged
    return merged.sample(n=n, random_state=random_seed).sort_values(KEY_COLUMNS).reset_index(drop=True)


def write_report(
    *,
    args: argparse.Namespace,
    state: pd.DataFrame,
    metrics: pd.DataFrame,
    calibrated_metrics: pd.DataFrame,
    weights: dict[str, float],
    weight_search: pd.DataFrame | None,
    calibration_artifacts: list[dict[str, Any]],
) -> None:
    label_counts = state["state_trophic_expert"].value_counts(dropna=False).reset_index()
    label_counts.columns = ["state_trophic_expert", "rows"]
    target_metrics = metrics[metrics["metric_scope"] == "target"].copy()
    current_metrics = metrics[metrics["metric_scope"] == "current"].copy()
    evidence_summary = (
        state.groupby("source_id", dropna=False)
        .agg(
            rows=("site_id", "size"),
            evidence_N_mean=("evidence_N", "mean"),
            evidence_F_mean=("evidence_F", "mean"),
            evidence_T_mean=("evidence_T", "mean"),
            evidence_T_no_chla_mean=("evidence_T_no_chla", "mean"),
            high_uncert_N_rate=("sigma_N", lambda value: float((value >= 0.7).mean())),
            high_uncert_F_rate=("sigma_F", lambda value: float((value >= 0.7).mean())),
            high_uncert_T_rate=("sigma_T", lambda value: float((value >= 0.7).mean())),
        )
        .reset_index()
    )
    lines = [
        "# Expert Fuzzy / ANFIS Fallback Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Scope",
        "",
        "This is `expert_fuzzy_v0`: a deterministic expert fuzzy fallback for PIPE Layer 1.",
        "It produces pseudo-labels and S(t), but it is not an adaptive ANFIS training result.",
        "",
        "## IRC1 Weights",
        "",
        f"- alpha/yN: `{weights['alpha']}`",
        f"- beta/(1-yF): `{weights['beta']}`",
        f"- gamma/yT: `{weights['gamma']}`",
        f"- mode: `{args.weights_mode}`",
        "",
        "## State Vector",
        "",
        f"- rows: `{_format_int(len(state))}`",
        f"- sites: `{_format_int(state[['source_id', 'site_id']].drop_duplicates().shape[0])}`",
        f"- output: `{args.state}`",
        "",
        "## Module Evidence",
        "",
        "| source | rows | evidence N | evidence F | evidence T | evidence T no Chl-a | high sigma N | high sigma F | high sigma T |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(evidence_summary):
        lines.append(
            f"| `{row.source_id}` | {_format_int(int(row.rows))} | {_format_float(row.evidence_N_mean)} | "
            f"{_format_float(row.evidence_F_mean)} | {_format_float(row.evidence_T_mean)} | "
            f"{_format_float(row.evidence_T_no_chla_mean)} | {_format_float(row.high_uncert_N_rate)} | "
            f"{_format_float(row.high_uncert_F_rate)} | {_format_float(row.high_uncert_T_rate)} |"
        )
    lines.extend(
        [
            "",
            "## Current-Month Scores vs Current Chl-a Risk",
            "",
            "| score | source | rows | Pearson | Spearman | RMSE | MAE |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(current_metrics.sort_values(["score_name", "source_id"])):
        lines.append(
            f"| `{row.score_name}` | `{row.source_id}` | {_format_int(int(row.rows))} | "
            f"{_format_float(row.pearson_score_risk_chla)} | { _format_float(row.spearman_score_risk_chla)} | "
            f"{_format_float(row.rmse_score_risk_chla)} | {_format_float(row.mae_score_risk_chla)} |"
        )
    lines.extend(
        [
            "",
            "## Raw Target Metrics By Horizon, Split, And Source",
            "",
            "| score | source | horizon | split | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | MAE risk |",
            "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    report_target = target_metrics[
        (target_metrics["source_id"] == "all") | (target_metrics["split"].isin(["validation", "test"]))
    ].copy()
    for row in dataframe_rows(report_target.sort_values(["score_name", "horizon_months", "split", "source_id"])):
        lines.append(
            f"| `{row.score_name}` | `{row.source_id}` | {int(row.horizon_months)} | `{row.split}` | "
            f"{_format_int(int(row.rows))} | {_format_float(row.pr_auc)} | {_format_float(row.roc_auc)} | "
            f"{_format_float(row.brier)} | {_format_float(row.recall)} | {_format_float(row.macro_f1)} | "
            f"{_format_float(row.mae_score_risk_chla)} |"
        )
    if not calibrated_metrics.empty:
        calibrated_all = calibrated_metrics[calibrated_metrics["source_id"] == "all"].copy()
        lines.extend(
            [
                "",
                "## Calibrated Target Metrics",
                "",
                "| score | horizon | split | rows | threshold | PR-AUC | ROC-AUC | Brier | recall | macro-F1 |",
                "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in dataframe_rows(calibrated_all.sort_values(["score_name", "horizon_months", "split"])):
            lines.append(
                f"| `{row.score_name}` | {int(row.horizon_months)} | `{row.split}` | {_format_int(int(row.rows))} | "
                f"{_format_float(row.threshold)} | {_format_float(row.pr_auc)} | {_format_float(row.roc_auc)} | "
                f"{_format_float(row.brier)} | {_format_float(row.recall)} | {_format_float(row.macro_f1)} |"
            )
    lines.extend(
        [
            "",
            "## Trophic Expert State Counts",
            "",
            "| state | rows |",
            "|---|---:|",
        ]
    )
    for row in dataframe_rows(label_counts):
        lines.append(f"| `{row.state_trophic_expert}` | {_format_int(int(row.rows))} |")

    if weight_search is not None and not weight_search.empty:
        lines.extend(
            [
                "",
                "## Top IRC1 Weight Candidates",
                "",
                "| rank | alpha | beta | gamma | train rows | train PR-AUC | train Brier |",
                "|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for rank, row in enumerate(dataframe_rows(weight_search.head(10)), start=1):
            lines.append(
                f"| {rank} | {_format_float(row.alpha)} | {_format_float(row.beta)} | {_format_float(row.gamma)} | "
                f"{_format_int(int(row.train_rows))} | {_format_float(row.train_pr_auc)} | {_format_float(row.train_brier)} |"
            )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- State vector: `{args.state}`",
            f"- Metrics: `{args.metrics}`",
            f"- Calibrated metrics: `{args.calibrated_metrics}`",
            f"- Rules: `{args.rules}`",
            f"- Memberships: `{args.memberships}`",
            f"- Trace examples: `{args.trace}`",
            f"- Manifest: `{args.manifest}`",
        ]
    )
    if calibration_artifacts:
        lines.extend(
            [
                "",
                "## Calibration Artifacts",
                "",
                "| score | horizon | calibration | path | sha256 |",
                "|---|---:|---|---|---|",
            ]
        )
        for artifact in calibration_artifacts:
            lines.append(
                f"| `{artifact['score_name']}` | {int(artifact['horizon_months'])} | `{artifact['calibration']}` | "
                f"`{artifact['path']}` | `{artifact['sha256']}` |"
            )
    _write_text_atomic("\n".join(lines) + "\n", args.report)


def build_manifest(
    *,
    args: argparse.Namespace,
    weights: dict[str, float],
    output_paths: list[Path],
    row_counts: dict[str, int],
    calibration_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_family": "expert_fuzzy_v0",
        "claim": "deterministic expert fuzzy fallback, not adaptive ANFIS",
        "panel": args.panel.as_posix(),
        "splits": args.splits.as_posix() if args.splits else None,
        "weights_mode": args.weights_mode,
        "irc_weights": weights,
        "threshold": args.threshold,
        "row_counts": row_counts,
        "score_columns": SCORE_COLUMNS,
        "calibration": {
            "method": "isotonic",
            "fit_split": "validation",
            "threshold_policy": "validation max macro-F1",
            "artifacts": calibration_artifacts,
        },
        "outputs": [_file_record(path) for path in output_paths if path.exists()],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--memberships", type=Path, default=DEFAULT_MEMBERSHIPS)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--calibrated-metrics", type=Path, default=DEFAULT_CALIBRATED_METRICS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--calibrators-dir", type=Path, default=DEFAULT_CALIBRATORS_DIR)
    parser.add_argument("--weights-mode", choices=["expert", "train-grid"], default="train-grid")
    parser.add_argument("--weight-grid", default="0.5,1,2")
    parser.add_argument("--weight-fit-max-rows", type=int, default=500_000)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--trace-sample-size", type=int, default=500)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--max-panel-rows", type=int, default=0)
    parser.add_argument("--max-split-rows", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"loading panel {args.panel}", flush=True)
    panel = _load_panel(args.panel, args.max_panel_rows or None)
    print(f"panel rows={len(panel):,}", flush=True)

    provisional_state, _ = build_expert_state(panel, irc_weights=DEFAULT_IRC_WEIGHTS)
    weights = DEFAULT_IRC_WEIGHTS.copy()
    weight_search: pd.DataFrame | None = None
    splits = None
    if args.splits and args.splits.exists():
        print(f"loading splits {args.splits}", flush=True)
        splits = _load_splits(args.splits, args.max_split_rows or None)
        print(f"split rows={len(splits):,}", flush=True)
    if args.weights_mode == "train-grid" and splits is not None and not splits.empty:
        print("fitting IRC1 alpha/beta/gamma on train split only", flush=True)
        weights, weight_search = fit_irc_weights(
            provisional_state,
            splits,
            grid=_parse_weight_grid(args.weight_grid),
            max_rows=args.weight_fit_max_rows,
            random_seed=args.random_seed,
        )
        print(f"selected weights alpha={weights['alpha']}, beta={weights['beta']}, gamma={weights['gamma']}", flush=True)

    print("building final expert fuzzy state vector", flush=True)
    state, trace = build_expert_state(panel, irc_weights=weights)
    metrics_parts = [evaluate_current_state(state)]
    calibrated_metrics = pd.DataFrame()
    calibration_artifacts: list[dict[str, Any]] = []
    if splits is not None and not splits.empty:
        print("evaluating IRC1 against target splits", flush=True)
        metrics_parts.append(evaluate_targets(state, splits, args.threshold))
        print("calibrating IRC1 variants on validation split", flush=True)
        calibrated_metrics, calibration_artifacts = evaluate_calibrated_scores(
            state,
            splits,
            score_columns=SCORE_COLUMNS,
            calibrators_dir=args.calibrators_dir,
        )
    metrics = pd.concat([part for part in metrics_parts if not part.empty], ignore_index=True)

    rules = rules_table(weights)
    memberships = membership_spec_table()
    traces = trace_examples(trace, state, args.trace_sample_size, args.random_seed)
    _write_parquet_atomic(state, args.state)
    _write_csv_atomic(metrics, args.metrics)
    _write_csv_atomic(calibrated_metrics, args.calibrated_metrics)
    _write_csv_atomic(rules, args.rules)
    _write_csv_atomic(memberships, args.memberships)
    _write_csv_atomic(traces, args.trace)
    if weight_search is not None:
        _write_csv_atomic(weight_search, args.report.with_name("irc1_weight_search.csv"))
    write_report(
        args=args,
        state=state,
        metrics=metrics,
        calibrated_metrics=calibrated_metrics,
        weights=weights,
        weight_search=weight_search,
        calibration_artifacts=calibration_artifacts,
    )
    output_paths = [args.state, args.metrics, args.calibrated_metrics, args.rules, args.memberships, args.trace, args.report]
    if weight_search is not None:
        output_paths.append(args.report.with_name("irc1_weight_search.csv"))
    manifest = build_manifest(
        args=args,
        weights=weights,
        output_paths=output_paths,
        row_counts={
            "panel_rows": int(len(panel)),
            "state_rows": int(len(state)),
            "metrics_rows": int(len(metrics)),
            "calibrated_metrics_rows": int(len(calibrated_metrics)),
        },
        calibration_artifacts=calibration_artifacts,
    )
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.state}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
