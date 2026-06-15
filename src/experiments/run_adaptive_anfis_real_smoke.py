#!/usr/bin/env python
"""Run the Gate 2 bounded real-data smoke for adaptive ANFIS."""

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
import pyarrow.parquet as pq
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    recall_score,
    roc_auc_score,
)

from src.fuzzy.adaptive_anfis import (
    _require_torch,
    make_adaptive_anfis,
    max_parameter_delta,
    parameter_snapshot,
    set_reproducible_seed,
    train_supervised_anfis,
)
from src.fuzzy.expert import (
    compute_irc1,
    nutrient_pressure,
    physicochemical_condition,
    thermal_biological_favorability,
)


DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_STATE = Path("data/fuzzy/state_vector_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_REPORT_DIR = Path("reports/anfis")
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "adaptive_anfis_real_smoke_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "adaptive_anfis_real_smoke_manifest.json"
DEFAULT_MODULE_METRICS = DEFAULT_REPORT_DIR / "adaptive_anfis_real_smoke_module_metrics.csv"
DEFAULT_TARGET_METRICS = DEFAULT_REPORT_DIR / "adaptive_anfis_real_smoke_target_metrics.csv"
DEFAULT_PREDICTIONS = DEFAULT_REPORT_DIR / "adaptive_anfis_real_smoke_predictions.csv"
DEFAULT_MEMBERSHIPS_INITIAL = DEFAULT_REPORT_DIR / "adaptive_anfis_real_smoke_memberships_initial.csv"
DEFAULT_MEMBERSHIPS_FINAL = DEFAULT_REPORT_DIR / "adaptive_anfis_real_smoke_memberships_final.csv"

KEY_COLUMNS = ["source_id", "site_id", "origin_year_month"]
PANEL_KEY_COLUMNS = ["source_id", "site_id", "site_id_source", "site_name", "year_month"]
PANEL_FEATURE_COLUMNS = [
    "mean_TP_ugL",
    "mean_TN_ugL",
    "TN_TP_ratio",
    "mean_DO_mgL",
    "mean_pH",
    "mean_turbidity_NTU",
    "mean_secchi_depth_m",
    "mean_temperature_C",
    "mean_chlorophyll_a_ugL",
    "risk_chla",
]
OPTIONAL_QC_COLUMNS = [
    "qc_ok_rate_TP_ugL",
    "qc_ok_rate_TN_ugL",
    "qc_ok_rate_DO_mgL",
    "qc_ok_rate_pH",
    "qc_ok_rate_turbidity_NTU",
    "qc_ok_rate_secchi_depth_m",
    "qc_ok_rate_temperature_C",
    "qc_ok_rate_chlorophyll_a_ugL",
]
STATE_COLUMNS = [
    "source_id",
    "site_id",
    "year_month",
    "yN",
    "yF",
    "yT",
    "yT_no_chla",
    "irc1",
    "irc1_no_chla",
]
SPLIT_COLUMNS = [
    "source_id",
    "site_id",
    "origin_year_month",
    "horizon_months",
    "split",
    "bloom_h",
    "target_risk_chla_h",
]
MODULE_SPECS: dict[str, dict[str, Any]] = {
    "ANFIS-N": {
        "feature_columns": ["tp_pressure", "tn_pressure", "ratio_imbalance_pressure"],
        "target_column": "yN",
        "output_column": "yN_adaptive",
        "sigma_column": "sigma_N_adaptive_proxy",
    },
    "ANFIS-F": {
        "feature_columns": ["do_good", "ph_good", "turbidity_good", "secchi_good"],
        "target_column": "yF",
        "output_column": "yF_adaptive",
        "sigma_column": "sigma_F_adaptive_proxy",
    },
    "ANFIS-T": {
        "feature_columns": ["temp_favorable", "current_chla_pressure"],
        "target_column": "yT",
        "output_column": "yT_adaptive",
        "sigma_column": "sigma_T_adaptive_proxy",
    },
    "ANFIS-T-no-current": {
        "feature_columns": ["temp_favorable"],
        "target_column": "yT_no_chla",
        "output_column": "yT_no_chla_adaptive",
        "sigma_column": "sigma_T_no_chla_adaptive_proxy",
    },
}
TARGET_SCORE_COLUMNS = ["irc1", "irc1_no_chla", "irc1_adaptive", "irc1_no_chla_adaptive"]


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


def _manifest_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": _manifest_path(path), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


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


def _write_text_atomic(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _format_int(value: int | float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{int(value):,}"


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _parse_int_list(value: str) -> list[int]:
    out = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not out:
        raise ValueError("Expected at least one integer")
    return sorted(set(out))


def _parse_str_list(value: str) -> list[str]:
    out = [part.strip() for part in value.split(",") if part.strip()]
    if not out:
        raise ValueError("Expected at least one value")
    return out


def _safe_metric(metric_fn: Any, *args: Any, **kwargs: Any) -> float:
    try:
        return float(metric_fn(*args, **kwargs))
    except ValueError:
        return float("nan")


def _safe_corr(left: pd.Series, right: pd.Series, method: str = "spearman") -> float:
    pair = pd.concat([left, right], axis=1).dropna()
    if pair.shape[0] < 2 or pair.iloc[:, 0].nunique() < 2 or pair.iloc[:, 1].nunique() < 2:
        return float("nan")
    return float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method=method))


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _available_columns(path: Path) -> list[str]:
    return list(pq.read_schema(path).names)


def _read_existing_columns(path: Path, columns: list[str]) -> pd.DataFrame:
    available = set(_available_columns(path))
    required = [column for column in columns if column in available]
    missing = sorted(set(columns) - available)
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")
    return pd.read_parquet(path, columns=required)


def _optional_panel_columns(path: Path) -> list[str]:
    available = set(_available_columns(path))
    required = PANEL_KEY_COLUMNS + PANEL_FEATURE_COLUMNS
    missing_required = sorted(set(required) - available)
    if missing_required:
        raise ValueError(f"{path} is missing required panel columns: {missing_required}")
    return required + [column for column in OPTIONAL_QC_COLUMNS if column in available]


def load_splits(path: Path, horizons: list[int], splits: list[str]) -> pd.DataFrame:
    frame = _read_existing_columns(path, SPLIT_COLUMNS)
    frame = frame[frame["horizon_months"].isin(horizons) & frame["split"].isin(splits)].copy()
    frame["bloom_h"] = pd.to_numeric(frame["bloom_h"], errors="coerce")
    frame["target_risk_chla_h"] = pd.to_numeric(frame["target_risk_chla_h"], errors="coerce").clip(0.0, 1.0)
    frame["origin_year_month"] = frame["origin_year_month"].astype(str)
    return frame


def sample_splits(frame: pd.DataFrame, rows_per_split_horizon: int, random_seed: int) -> pd.DataFrame:
    if rows_per_split_horizon <= 0:
        raise ValueError("--sample-rows-per-split-horizon must be positive")
    rows = []
    for _, group in frame.groupby(["split", "horizon_months"], dropna=False, sort=True):
        if len(group) > rows_per_split_horizon:
            group = group.sample(n=rows_per_split_horizon, random_state=random_seed)
        rows.append(group)
    if not rows:
        raise ValueError("No split rows remain after horizon/split filtering")
    sampled = pd.concat(rows, ignore_index=True)
    return sampled.sort_values(["split", "horizon_months", "source_id", "site_id", "origin_year_month"]).reset_index(drop=True)


def load_state(path: Path) -> pd.DataFrame:
    frame = _read_existing_columns(path, STATE_COLUMNS)
    frame = frame.rename(columns={"year_month": "origin_year_month"})
    frame["origin_year_month"] = frame["origin_year_month"].astype(str)
    return frame


def load_panel(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=_optional_panel_columns(path))
    frame = frame.rename(columns={"year_month": "origin_year_month"})
    frame["origin_year_month"] = frame["origin_year_month"].astype(str)
    return frame


def build_real_smoke_frame(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    splits = load_splits(args.splits, _parse_int_list(args.horizons), _parse_str_list(args.splits_to_use))
    sampled = sample_splits(splits, args.sample_rows_per_split_horizon, args.random_seed)
    state = load_state(args.state)
    panel = load_panel(args.panel)
    joined = sampled.merge(state, on=KEY_COLUMNS, how="left", validate="many_to_one", indicator="state_merge")
    joined = joined.merge(panel, on=KEY_COLUMNS, how="left", validate="many_to_one", indicator="panel_merge")
    alignment = {
        "sampled_split_rows": int(len(sampled)),
        "state_matched_rows": int((joined["state_merge"] == "both").sum()),
        "panel_matched_rows": int((joined["panel_merge"] == "both").sum()),
        "state_missing_rows": int((joined["state_merge"] != "both").sum()),
        "panel_missing_rows": int((joined["panel_merge"] != "both").sum()),
    }
    joined = joined[(joined["state_merge"] == "both") & (joined["panel_merge"] == "both")].copy()
    joined = joined.drop(columns=["state_merge", "panel_merge"])
    if joined.empty:
        raise ValueError("No rows remain after joining sampled splits to panel and state")
    return add_module_features(joined), alignment


def add_module_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    _, _, trace_n = nutrient_pressure(out)
    _, _, trace_f = physicochemical_condition(out)
    _, _, _, _, trace_t = thermal_biological_favorability(out)
    feature_frame = pd.concat(
        [
            trace_n[["tp_pressure", "tn_pressure", "ratio_imbalance_pressure"]],
            trace_f[["do_good", "ph_good", "turbidity_good", "secchi_good"]],
            trace_t[["temp_favorable", "current_chla_pressure"]],
        ],
        axis=1,
    )
    for column in feature_frame.columns:
        out[column] = pd.to_numeric(feature_frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return out


def _module_xy(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    features = frame[spec["feature_columns"]].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    missing_fraction = features.isna().mean(axis=1)
    features = features.fillna(0.5).clip(0.0, 1.0)
    target = pd.to_numeric(frame[spec["target_column"]], errors="coerce").clip(0.0, 1.0)
    return features, target, missing_fraction


def _sample_training_rows(frame: pd.DataFrame, spec: dict[str, Any], args: argparse.Namespace, seed_offset: int) -> pd.DataFrame:
    candidate = frame[frame["split"] == "train"].drop_duplicates(KEY_COLUMNS).copy()
    _, target, missing_fraction = _module_xy(candidate, spec)
    valid = target.notna()
    max_missing_fraction = getattr(args, "max_train_missing_fraction", None)
    if max_missing_fraction is not None:
        valid &= missing_fraction <= float(max_missing_fraction)
    candidate = candidate.loc[valid].copy()
    if len(candidate) > args.train_rows_per_module:
        candidate = candidate.sample(n=args.train_rows_per_module, random_state=args.random_seed + seed_offset)
    if len(candidate) < args.min_module_rows:
        raise ValueError(
            f"{spec['output_column']} has {len(candidate)} train rows; "
            f"minimum required is {args.min_module_rows}"
        )
    return candidate.reset_index(drop=True)


def _membership_table(model: Any, module: str, feature_names: list[str], phase: str) -> pd.DataFrame:
    centers = model.ordered_centers().detach().cpu().numpy()
    widths = model.positive_widths().detach().cpu().numpy()
    rows = []
    for feature_index, feature_name in enumerate(feature_names):
        for membership_index in range(centers.shape[1]):
            rows.append(
                {
                    "phase": phase,
                    "module": module,
                    "feature": feature_name,
                    "membership_index": int(membership_index),
                    "center": float(centers[feature_index, membership_index]),
                    "width": float(widths[feature_index, membership_index]),
                }
            )
    return pd.DataFrame(rows)


def _predict_with_sigma(model: Any, features: pd.DataFrame, missing_fraction: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    torch = _require_torch()
    x = torch.as_tensor(features.to_numpy(dtype="float32"), dtype=torch.float32)
    with torch.no_grad():
        details = model(x, return_details=True)
    prediction = details["prediction"].detach().cpu().numpy()
    normalized = details["normalized_firing_strengths"].detach().cpu().numpy()
    entropy = -(normalized * np.log(np.clip(normalized, 1e-12, 1.0))).sum(axis=1)
    if normalized.shape[1] > 1:
        entropy = entropy / np.log(normalized.shape[1])
    sigma = np.clip(0.10 + 0.45 * entropy + 0.35 * missing_fraction.to_numpy(dtype="float64"), 0.0, 1.0)
    return prediction, sigma


def train_modules(
    frame: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    module_metrics: list[dict[str, Any]] = []
    initial_memberships: list[pd.DataFrame] = []
    final_memberships: list[pd.DataFrame] = []
    models: dict[str, Any] = {}
    seed_offsets = {"ANFIS-N": 101, "ANFIS-F": 202, "ANFIS-T": 303, "ANFIS-T-no-current": 404}
    for module, spec in MODULE_SPECS.items():
        training = _sample_training_rows(frame, spec, args, seed_offsets[module])
        train_x, train_y, _ = _module_xy(training, spec)
        model = make_adaptive_anfis(
            input_dim=train_x.shape[1],
            membership_count=args.memberships,
            min_width=args.min_width,
            min_gap=args.min_gap,
            center_constraint=getattr(args, "center_constraint", "ordered"),
        )
        initial_memberships.append(_membership_table(model, module, list(train_x.columns), "initial"))
        before = parameter_snapshot(model)
        torch = _require_torch()
        with torch.no_grad():
            initial_prediction = model(torch.as_tensor(train_x.to_numpy(dtype="float32"), dtype=torch.float32))
            initial_loss = torch.nn.functional.mse_loss(
                initial_prediction,
                torch.as_tensor(train_y.to_numpy(dtype="float32"), dtype=torch.float32),
            ).item()
        curve = train_supervised_anfis(
            model,
            train_x.to_numpy(dtype="float32"),
            train_y.to_numpy(dtype="float32"),
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            random_seed=args.random_seed + seed_offsets[module],
            grad_clip=args.grad_clip,
        )
        final_memberships.append(_membership_table(model, module, list(train_x.columns), "final"))
        eval_x, eval_y, eval_missing = _module_xy(frame, spec)
        eval_valid = eval_y.notna()
        prediction, sigma = _predict_with_sigma(model, eval_x, eval_missing)
        frame[spec["output_column"]] = prediction
        frame[spec["sigma_column"]] = sigma
        output_std = float(np.nanstd(prediction))
        final_train_loss = float(curve[-1]["loss"])
        finite_loss = bool(np.isfinite(final_train_loss))
        ordered = model.centers_are_ordered()
        parameter_delta = max_parameter_delta(model, before)
        anchor_mae = _safe_metric(
            mean_absolute_error,
            eval_y.loc[eval_valid].to_numpy(dtype="float64"),
            prediction[eval_valid.to_numpy()],
        )
        anchor_rmse = _safe_metric(
            _rmse,
            eval_y.loc[eval_valid].to_numpy(dtype="float64"),
            prediction[eval_valid.to_numpy()],
        )
        spearman = _safe_corr(pd.Series(prediction, index=frame.index), eval_y)
        status = (
            "passed"
            if finite_loss
            and ordered
            and parameter_delta > 0
            and output_std >= args.min_output_std
            and int(eval_valid.sum()) >= args.min_module_rows
            else "failed"
        )
        module_metrics.append(
            {
                "module": module,
                "status": status,
                "train_rows": int(len(training)),
                "eval_rows": int(eval_valid.sum()),
                "input_dim": int(train_x.shape[1]),
                "memberships": int(args.memberships),
                "rules": int(model.rule_count),
                "initial_train_loss": float(initial_loss),
                "final_train_loss": final_train_loss,
                "relative_train_loss_improvement": (float(initial_loss) - final_train_loss) / max(float(initial_loss), 1e-12),
                "finite_loss": finite_loss,
                "centers_ordered": ordered,
                "max_parameter_delta": float(parameter_delta),
                "output_min": float(np.nanmin(prediction)),
                "output_max": float(np.nanmax(prediction)),
                "output_std": output_std,
                "anchor_mae": float(anchor_mae),
                "anchor_rmse": float(anchor_rmse),
                "anchor_spearman": float(spearman),
                "mean_missing_fraction": float(eval_missing.mean()),
                "epochs": int(len(curve)),
                "curve_initial_loss": float(curve[0]["loss"]),
                "curve_final_loss": final_train_loss,
                "curve_min_loss": float(min(row["loss"] for row in curve)),
            }
        )
        models[module] = model
    return (
        models,
        pd.DataFrame(module_metrics),
        pd.concat(initial_memberships, ignore_index=True),
        pd.concat(final_memberships, ignore_index=True),
    )


def add_composite_scores(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["irc1_adaptive"] = compute_irc1(out["yN_adaptive"], out["yF_adaptive"], out["yT_adaptive"])
    out["irc1_no_chla_adaptive"] = compute_irc1(out["yN_adaptive"], out["yF_adaptive"], out["yT_no_chla_adaptive"])
    return out


def target_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for score_name in TARGET_SCORE_COLUMNS:
        for _, group in frame.groupby(["horizon_months", "split"], dropna=False, sort=True):
            horizon = int(group["horizon_months"].iloc[0])
            split = str(group["split"].iloc[0])
            score = pd.to_numeric(group[score_name], errors="coerce").clip(0.0, 1.0)
            target_risk = pd.to_numeric(group["target_risk_chla_h"], errors="coerce").clip(0.0, 1.0)
            bloom = pd.to_numeric(group["bloom_h"], errors="coerce")
            valid_probability = score.notna()
            valid_risk = valid_probability & target_risk.notna()
            valid_bloom = valid_probability & bloom.notna()
            y_true = bloom.loc[valid_bloom].round().astype("int8").to_numpy()
            probability = score.loc[valid_bloom].to_numpy(dtype="float64")
            predicted = (probability >= 0.5).astype("int8")
            risk_true = target_risk.loc[valid_risk].to_numpy(dtype="float64")
            risk_pred = score.loc[valid_risk].to_numpy(dtype="float64")
            rows.append(
                {
                    "score_name": score_name,
                    "horizon_months": horizon,
                    "split": split,
                    "rows": int(len(group)),
                    "bloom_rows": int(len(y_true)),
                    "risk_rows": int(len(risk_true)),
                    "threshold": 0.5,
                    "bloom_positive": int(y_true.sum()) if len(y_true) else 0,
                    "bloom_rate": float(y_true.mean()) if len(y_true) else float("nan"),
                    "pr_auc": _safe_metric(average_precision_score, y_true, probability) if len(y_true) else float("nan"),
                    "roc_auc": _safe_metric(roc_auc_score, y_true, probability) if len(y_true) else float("nan"),
                    "brier": _safe_metric(brier_score_loss, y_true, probability) if len(y_true) else float("nan"),
                    "recall": _safe_metric(recall_score, y_true, predicted, zero_division=0) if len(y_true) else float("nan"),
                    "macro_f1": _safe_metric(f1_score, y_true, predicted, average="macro", zero_division=0) if len(y_true) else float("nan"),
                    "risk_rmse": _safe_metric(_rmse, risk_true, risk_pred) if len(risk_true) else float("nan"),
                    "risk_mae": _safe_metric(mean_absolute_error, risk_true, risk_pred) if len(risk_true) else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def prediction_columns() -> list[str]:
    return [
        "source_id",
        "site_id",
        "origin_year_month",
        "horizon_months",
        "split",
        "bloom_h",
        "target_risk_chla_h",
        "yN",
        "yN_adaptive",
        "sigma_N_adaptive_proxy",
        "yF",
        "yF_adaptive",
        "sigma_F_adaptive_proxy",
        "yT",
        "yT_adaptive",
        "sigma_T_adaptive_proxy",
        "yT_no_chla",
        "yT_no_chla_adaptive",
        "sigma_T_no_chla_adaptive_proxy",
        "irc1",
        "irc1_adaptive",
        "irc1_no_chla",
        "irc1_no_chla_adaptive",
    ]


def write_report(
    *,
    args: argparse.Namespace,
    generated_at: str,
    status: str,
    alignment: dict[str, Any],
    module_metrics: pd.DataFrame,
    target_metrics_frame: pd.DataFrame,
) -> None:
    validation = target_metrics_frame[
        (target_metrics_frame["split"] == "validation")
        & target_metrics_frame["score_name"].isin(["irc1_adaptive", "irc1_no_chla_adaptive"])
    ].copy()
    lines = [
        "# Adaptive ANFIS Real-Data Smoke Report",
        "",
        f"Generated at UTC: `{generated_at}`",
        "",
        f"Status: `{status}`",
        "",
        "## Scope",
        "",
        "This Gate 2 smoke trains bounded adaptive ANFIS modules on a sampled",
        "real-data slice using expert fuzzy substates as pseudo-label anchors.",
        "It does not produce the full adaptive state vector and must not be used",
        "as a thesis-scale adaptive PIPE result.",
        "",
        "## Configuration",
        "",
        f"- sampled rows per split/horizon: `{args.sample_rows_per_split_horizon}`",
        f"- train rows per module: `{args.train_rows_per_module}`",
        f"- memberships per input: `{args.memberships}`",
        f"- epochs: `{args.epochs}`",
        f"- learning rate: `{args.learning_rate}`",
        f"- random seed: `{args.random_seed}`",
        "",
        "## Alignment",
        "",
        f"- sampled split rows: `{_format_int(alignment['sampled_split_rows'])}`",
        f"- state matched rows: `{_format_int(alignment['state_matched_rows'])}`",
        f"- panel matched rows: `{_format_int(alignment['panel_matched_rows'])}`",
        f"- state missing rows: `{_format_int(alignment['state_missing_rows'])}`",
        f"- panel missing rows: `{_format_int(alignment['panel_missing_rows'])}`",
        "",
        "## Module Anchor Metrics",
        "",
        "| module | status | train rows | eval rows | final loss | anchor MAE | anchor RMSE | Spearman | output std | ordered |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in module_metrics.to_dict(orient="records"):
        lines.append(
            f"| `{row['module']}` | `{row['status']}` | {_format_int(row['train_rows'])} | "
            f"{_format_int(row['eval_rows'])} | "
            f"{_format_float(row['final_train_loss'])} | {_format_float(row['anchor_mae'])} | "
            f"{_format_float(row['anchor_rmse'])} | {_format_float(row['anchor_spearman'])} | "
            f"{_format_float(row['output_std'])} | `{bool(row['centers_ordered'])}` |"
        )
    lines.extend(
        [
            "",
            "## Validation Target Metrics",
            "",
            "| score | horizon | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | risk RMSE | risk MAE |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if validation.empty:
        lines.append("| `NA` | NA | NA | NA | NA | NA | NA | NA | NA | NA |")
    else:
        for row in validation.to_dict(orient="records"):
            lines.append(
                f"| `{row['score_name']}` | {int(row['horizon_months'])} | {_format_int(row['rows'])} | "
                f"{_format_float(row['pr_auc'])} | {_format_float(row['roc_auc'])} | {_format_float(row['brier'])} | "
                f"{_format_float(row['recall'])} | {_format_float(row['macro_f1'])} | "
                f"{_format_float(row['risk_rmse'])} | {_format_float(row['risk_mae'])} |"
            )
    lines.extend(
        [
            "",
            "## Gate Checks",
            "",
            f"- split/state/panel alignment: `{alignment['state_missing_rows'] == 0 and alignment['panel_missing_rows'] == 0}`",
            f"- adaptive outputs are non-constant: `{bool((module_metrics['output_std'] >= args.min_output_std).all())}`",
            f"- expert-anchor metrics written: `{not module_metrics.empty}`",
            f"- validation target metrics written: `{not validation.empty}`",
            "- full and no-current surfaces separated: `True`",
            "",
            "## Outputs",
            "",
            f"- Module metrics: `{args.module_metrics.as_posix()}`",
            f"- Target metrics: `{args.target_metrics.as_posix()}`",
            f"- Prediction sample: `{args.predictions.as_posix()}`",
            f"- Initial memberships: `{args.memberships_initial.as_posix()}`",
            f"- Final memberships: `{args.memberships_final.as_posix()}`",
            f"- Manifest: `{args.manifest.as_posix()}`",
        ]
    )
    _write_text_atomic("\n".join(lines) + "\n", args.report)


def write_manifest(
    *,
    args: argparse.Namespace,
    generated_at: str,
    status: str,
    alignment: dict[str, Any],
    module_metrics: pd.DataFrame,
) -> None:
    curve_summary = {
        row["module"]: {
            "epochs": int(row["epochs"]),
            "initial_loss": float(row["curve_initial_loss"]),
            "final_loss": float(row["curve_final_loss"]),
            "min_loss": float(row["curve_min_loss"]),
        }
        for row in module_metrics.to_dict(orient="records")
    }
    payload = {
        "status": status,
        "generated_at_utc": generated_at,
        "config": {
            "sample_rows_per_split_horizon": int(args.sample_rows_per_split_horizon),
            "train_rows_per_module": int(args.train_rows_per_module),
            "min_module_rows": int(args.min_module_rows),
            "memberships": int(args.memberships),
            "epochs": int(args.epochs),
            "learning_rate": float(args.learning_rate),
            "random_seed": int(args.random_seed),
            "min_width": float(args.min_width),
            "min_gap": float(args.min_gap),
            "grad_clip": float(args.grad_clip),
            "min_output_std": float(args.min_output_std),
            "horizons": _parse_int_list(args.horizons),
            "splits_to_use": _parse_str_list(args.splits_to_use),
        },
        "sample_alignment": alignment,
        "module_metrics": module_metrics.to_dict(orient="records"),
        "training_curve_summary": curve_summary,
        "inputs": [_file_record(args.panel), _file_record(args.state), _file_record(args.splits)],
        "script": _file_record(Path(__file__)),
        "adaptive_anfis_module": _file_record(Path("src/fuzzy/adaptive_anfis.py")),
        "outputs": [
            _file_record(args.module_metrics),
            _file_record(args.target_metrics),
            _file_record(args.predictions),
            _file_record(args.memberships_initial),
            _file_record(args.memberships_final),
            _file_record(args.report),
        ],
    }
    _write_json_atomic(payload, args.manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--module-metrics", type=Path, default=DEFAULT_MODULE_METRICS)
    parser.add_argument("--target-metrics", type=Path, default=DEFAULT_TARGET_METRICS)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--memberships-initial", type=Path, default=DEFAULT_MEMBERSHIPS_INITIAL)
    parser.add_argument("--memberships-final", type=Path, default=DEFAULT_MEMBERSHIPS_FINAL)
    parser.add_argument("--horizons", default="1,2,3")
    parser.add_argument("--splits-to-use", default="train,validation,test")
    parser.add_argument("--sample-rows-per-split-horizon", type=int, default=512)
    parser.add_argument("--train-rows-per-module", type=int, default=512)
    parser.add_argument("--min-module-rows", type=int, default=16)
    parser.add_argument("--memberships", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--min-width", type=float, default=0.03)
    parser.add_argument("--min-gap", type=float, default=1e-4)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--min-output-std", type=float, default=1e-4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.train_rows_per_module <= 0:
        raise ValueError("--train-rows-per-module must be positive")
    if args.epochs <= 0:
        raise ValueError("--epochs must be positive")
    set_reproducible_seed(args.random_seed)
    generated_at = datetime.now(timezone.utc).isoformat()
    frame, alignment = build_real_smoke_frame(args)
    _, module_metrics, memberships_initial, memberships_final = train_modules(frame, args)
    frame = add_composite_scores(frame)
    target_metrics_frame = target_metrics(frame)
    prediction_sample = frame[prediction_columns()].sort_values(
        ["split", "horizon_months", "source_id", "site_id", "origin_year_month"]
    )
    validation_metrics_exist = not target_metrics_frame[
        (target_metrics_frame["split"] == "validation")
        & target_metrics_frame["score_name"].isin(["irc1_adaptive", "irc1_no_chla_adaptive"])
    ].empty
    status = (
        "completed"
        if alignment["state_missing_rows"] == 0
        and alignment["panel_missing_rows"] == 0
        and bool((module_metrics["status"] == "passed").all())
        and validation_metrics_exist
        else "failed"
    )
    _write_csv_atomic(module_metrics, args.module_metrics)
    _write_csv_atomic(target_metrics_frame, args.target_metrics)
    _write_csv_atomic(prediction_sample, args.predictions)
    _write_csv_atomic(memberships_initial, args.memberships_initial)
    _write_csv_atomic(memberships_final, args.memberships_final)
    write_report(
        args=args,
        generated_at=generated_at,
        status=status,
        alignment=alignment,
        module_metrics=module_metrics,
        target_metrics_frame=target_metrics_frame,
    )
    write_manifest(
        args=args,
        generated_at=generated_at,
        status=status,
        alignment=alignment,
        module_metrics=module_metrics,
    )
    print(f"wrote {args.report}")
    print(f"wrote {args.manifest}")


if __name__ == "__main__":
    main()
