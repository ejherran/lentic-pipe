#!/usr/bin/env python
"""Build the Gate 3 adaptive ANFIS state surface."""

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

from src.fuzzy.adaptive_anfis import _require_torch, set_reproducible_seed
from src.fuzzy.expert import compute_irc1
from src.experiments.run_adaptive_anfis_real_smoke import (
    KEY_COLUMNS,
    MODULE_SPECS,
    TARGET_SCORE_COLUMNS,
    _file_record,
    _format_float,
    _format_int,
    _json_default,
    _manifest_path,
    _module_xy,
    _parse_int_list,
    _parse_str_list,
    _predict_with_sigma,
    _safe_metric,
    _write_csv_atomic,
    _write_json_atomic,
    _write_text_atomic,
    add_module_features,
    load_panel,
    load_splits,
    load_state,
    target_metrics,
    train_modules,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error


DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_STATE = Path("data/fuzzy/state_vector_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_OUTPUT_STATE = Path("data/fuzzy/adaptive_state_vector_v0.parquet")
DEFAULT_MODELS_DIR = Path("models/anfis/adaptive")
DEFAULT_REPORT_DIR = Path("reports/anfis")
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "adaptive_anfis_state_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "adaptive_anfis_state_manifest.json"
DEFAULT_MODULE_METRICS = DEFAULT_REPORT_DIR / "adaptive_anfis_state_module_metrics.csv"
DEFAULT_TARGET_METRICS = DEFAULT_REPORT_DIR / "adaptive_anfis_state_target_metrics.csv"
DEFAULT_COVERAGE = DEFAULT_REPORT_DIR / "adaptive_anfis_state_coverage.csv"
DEFAULT_MEMBERSHIPS_INITIAL = DEFAULT_REPORT_DIR / "adaptive_anfis_memberships_initial.csv"
DEFAULT_MEMBERSHIPS_FINAL = DEFAULT_REPORT_DIR / "adaptive_anfis_memberships_final.csv"

STATE_EXPORT_COLUMNS = [
    "source_id",
    "site_id",
    "site_id_source",
    "site_name",
    "year_month",
    "yN_adaptive",
    "yF_adaptive",
    "yT_adaptive",
    "yT_no_chla_adaptive",
    "sigma_N_adaptive",
    "sigma_F_adaptive",
    "sigma_T_adaptive",
    "sigma_T_no_chla_adaptive",
    "delta_yN_adaptive",
    "delta_yF_adaptive",
    "delta_yT_adaptive",
    "delta_yT_no_chla_adaptive",
    "irc1_adaptive",
    "irc1_no_chla_adaptive",
]
EXPERT_SCORE_COLUMNS = ["irc1", "irc1_no_chla"]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _path_record(path: Path) -> dict[str, Any]:
    if path.is_file():
        return _file_record(path)
    if not path.is_dir():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    files = []
    total_bytes = 0
    for file_path in sorted(item for item in path.rglob("*") if item.is_file() and not item.name.endswith(".tmp")):
        file_hash = _sha256_file(file_path)
        relative_path = file_path.relative_to(path).as_posix()
        file_bytes = file_path.stat().st_size
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
        total_bytes += file_bytes
        files.append(
            {
                "path": _manifest_path(file_path),
                "relative_path": relative_path,
                "bytes": file_bytes,
                "sha256": file_hash,
            }
        )
    return {
        "path": _manifest_path(path),
        "type": "directory",
        "bytes": total_bytes,
        "sha256": digest.hexdigest(),
        "files": files,
    }


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _module_checkpoint_name(module: str) -> str:
    return module.lower().replace("anfis-", "").replace("-", "_") + ".pt"


def _filter_sources(frame: pd.DataFrame, source_ids: list[str] | None) -> pd.DataFrame:
    if not source_ids:
        return frame
    return frame[frame["source_id"].isin(source_ids)].copy()


def _sample_rows(frame: pd.DataFrame, max_rows: int, random_seed: int) -> pd.DataFrame:
    if max_rows <= 0 or len(frame) <= max_rows:
        return frame.reset_index(drop=True)
    return frame.sample(n=max_rows, random_state=random_seed).reset_index(drop=True)


def build_joined_surface(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    state = load_state(args.state)
    panel = load_panel(args.panel)
    source_ids = _parse_str_list(args.source_ids) if args.source_ids else None
    state = _filter_sources(state, source_ids)
    panel = _filter_sources(panel, source_ids)
    joined = state.merge(panel, on=KEY_COLUMNS, how="left", validate="one_to_one", indicator="panel_merge")
    alignment = {
        "state_rows": int(len(state)),
        "panel_rows_after_source_filter": int(len(panel)),
        "panel_matched_rows": int((joined["panel_merge"] == "both").sum()),
        "panel_missing_rows": int((joined["panel_merge"] != "both").sum()),
    }
    joined = joined[joined["panel_merge"] == "both"].drop(columns=["panel_merge"]).copy()
    joined = add_module_features(joined)
    export_frame = _sample_rows(joined, args.max_export_rows, args.random_seed)
    alignment["export_rows"] = int(len(export_frame))
    if export_frame.empty:
        raise ValueError("No rows remain for adaptive state export")
    return joined.reset_index(drop=True), export_frame.reset_index(drop=True), alignment


def build_training_frame(joined: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    splits = load_splits(args.splits, _parse_int_list(args.horizons), ["train"])
    if args.source_ids:
        splits = _filter_sources(splits, _parse_str_list(args.source_ids))
    train_keys = splits[KEY_COLUMNS + ["split"]].drop_duplicates(KEY_COLUMNS)
    training = train_keys.merge(joined, on=KEY_COLUMNS, how="inner", validate="one_to_one")
    if training.empty:
        raise ValueError("No train rows remain after joining splits to adaptive training surface")
    return training


def predict_modules(models: dict[str, Any], frame: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    out = frame.copy()
    for module, spec in MODULE_SPECS.items():
        predictions = []
        sigmas = []
        for start in range(0, len(out), args.predict_batch_rows):
            chunk = out.iloc[start : start + args.predict_batch_rows]
            features, _, missing_fraction = _module_xy(chunk, spec)
            prediction, sigma = _predict_with_sigma(models[module], features, missing_fraction)
            predictions.append(prediction)
            sigmas.append(sigma)
        out[spec["output_column"]] = np.concatenate(predictions) if predictions else np.array([], dtype="float64")
        out[spec["sigma_column"]] = np.concatenate(sigmas) if sigmas else np.array([], dtype="float64")
    return out


def adaptive_state_from_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.rename(
        columns={
            "origin_year_month": "year_month",
            "sigma_N_adaptive_proxy": "sigma_N_adaptive",
            "sigma_F_adaptive_proxy": "sigma_F_adaptive",
            "sigma_T_adaptive_proxy": "sigma_T_adaptive",
            "sigma_T_no_chla_adaptive_proxy": "sigma_T_no_chla_adaptive",
        }
    ).copy()
    out["irc1_adaptive"] = compute_irc1(out["yN_adaptive"], out["yF_adaptive"], out["yT_adaptive"])
    out["irc1_no_chla_adaptive"] = compute_irc1(out["yN_adaptive"], out["yF_adaptive"], out["yT_no_chla_adaptive"])
    sortable_month = pd.PeriodIndex(out["year_month"].astype(str), freq="M")
    out["_period_ordinal"] = sortable_month.astype("int64")
    out = out.sort_values(["source_id", "site_id", "_period_ordinal"]).reset_index(drop=True)
    grouped = out.groupby(["source_id", "site_id"], dropna=False)
    out["delta_yN_adaptive"] = grouped["yN_adaptive"].diff().fillna(0.0)
    out["delta_yF_adaptive"] = grouped["yF_adaptive"].diff().fillna(0.0)
    out["delta_yT_adaptive"] = grouped["yT_adaptive"].diff().fillna(0.0)
    out["delta_yT_no_chla_adaptive"] = grouped["yT_no_chla_adaptive"].diff().fillna(0.0)
    out = out.drop(columns=["_period_ordinal"])
    return out[STATE_EXPORT_COLUMNS]


def coverage_frame(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for module, spec in MODULE_SPECS.items():
        raw_features = frame[spec["feature_columns"]].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        _, target, missing_fraction = _module_xy(frame, spec)
        for source_id, group_index in frame.groupby("source_id", dropna=False).groups.items():
            index = list(group_index)
            rows.append(
                {
                    "module": module,
                    "source_id": source_id,
                    "rows": int(len(index)),
                    "target_non_null": int(target.loc[index].notna().sum()),
                    "mean_missing_fraction": float(missing_fraction.loc[index].mean()),
                    "complete_feature_rows": int((raw_features.loc[index].notna().all(axis=1)).sum()),
                    "feature_columns": ",".join(spec["feature_columns"]),
                }
            )
    return pd.DataFrame(rows)


def state_anchor_metrics(adaptive_state: pd.DataFrame, expert_state: pd.DataFrame) -> pd.DataFrame:
    joined = adaptive_state.merge(
        expert_state.rename(columns={"origin_year_month": "year_month"}),
        on=["source_id", "site_id", "year_month"],
        how="left",
        validate="one_to_one",
    )
    specs = [
        ("ANFIS-N", "yN", "yN_adaptive"),
        ("ANFIS-F", "yF", "yF_adaptive"),
        ("ANFIS-T", "yT", "yT_adaptive"),
        ("ANFIS-T-no-current", "yT_no_chla", "yT_no_chla_adaptive"),
    ]
    rows = []
    for module, expert_column, adaptive_column in specs:
        expert = pd.to_numeric(joined[expert_column], errors="coerce")
        adaptive = pd.to_numeric(joined[adaptive_column], errors="coerce")
        valid = expert.notna() & adaptive.notna()
        rows.append(
            {
                "module": module,
                "scope": "export_state_anchor",
                "rows": int(valid.sum()),
                "anchor_mae": _safe_metric(
                    mean_absolute_error,
                    expert.loc[valid].to_numpy(dtype="float64"),
                    adaptive.loc[valid].to_numpy(dtype="float64"),
                ),
                "anchor_rmse": _safe_metric(
                    _rmse,
                    expert.loc[valid].to_numpy(dtype="float64"),
                    adaptive.loc[valid].to_numpy(dtype="float64"),
                ),
                "anchor_spearman": float(expert.loc[valid].corr(adaptive.loc[valid], method="spearman"))
                if int(valid.sum()) >= 2 and expert.loc[valid].nunique() > 1 and adaptive.loc[valid].nunique() > 1
                else float("nan"),
                "output_std": float(adaptive.loc[valid].std()) if int(valid.sum()) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def target_frame(adaptive_state: pd.DataFrame, expert_state: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    splits = load_splits(args.splits, _parse_int_list(args.horizons), _parse_str_list(args.evaluation_splits))
    if args.source_ids:
        splits = _filter_sources(splits, _parse_str_list(args.source_ids))
    expert = expert_state.rename(columns={"origin_year_month": "year_month"})[
        ["source_id", "site_id", "year_month", *EXPERT_SCORE_COLUMNS]
    ]
    adaptive_scores = adaptive_state[["source_id", "site_id", "year_month", "irc1_adaptive", "irc1_no_chla_adaptive"]]
    state_scores = expert.merge(adaptive_scores, on=["source_id", "site_id", "year_month"], how="inner")
    evaluation = splits.merge(
        state_scores.rename(columns={"year_month": "origin_year_month"}),
        on=KEY_COLUMNS,
        how="inner",
        validate="many_to_one",
    )
    alignment = {
        "evaluation_split_rows": int(len(splits)),
        "evaluation_matched_rows": int(len(evaluation)),
        "evaluation_missing_rows": int(len(splits) - len(evaluation)),
    }
    return evaluation, alignment


def save_checkpoints(models: dict[str, Any], args: argparse.Namespace) -> list[Path]:
    torch = _require_torch()
    args.models_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for module, model in models.items():
        path = args.models_dir / _module_checkpoint_name(module)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        torch.save(
            {
                "module": module,
                "state_dict": model.state_dict(),
                "input_dim": model.input_dim,
                "membership_count": model.membership_count,
                "rule_count": model.rule_count,
                "center_constraint": model.center_constraint,
                "feature_columns": MODULE_SPECS[module]["feature_columns"],
                "target_column": MODULE_SPECS[module]["target_column"],
            },
            tmp_path,
        )
        tmp_path.replace(path)
        paths.append(path)
    return paths


def write_report(
    *,
    args: argparse.Namespace,
    generated_at: str,
    status: str,
    alignment: dict[str, Any],
    module_metrics: pd.DataFrame,
    anchor_metrics: pd.DataFrame,
    target_metrics_frame: pd.DataFrame,
) -> None:
    validation = target_metrics_frame[
        (target_metrics_frame["split"] == "validation")
        & target_metrics_frame["score_name"].isin(["irc1_adaptive", "irc1_no_chla_adaptive"])
    ].copy()
    lines = [
        "# Adaptive ANFIS State Report",
        "",
        f"Generated at UTC: `{generated_at}`",
        "",
        f"Status: `{status}`",
        "",
        "## Scope",
        "",
        "This Gate 3 builder trains adaptive ANFIS modules and exports an",
        "`S_adaptive(t)` state surface. The exported parquet and checkpoints are",
        "heavy/model artifacts and should be promoted through DVC after review.",
        "",
        "## Configuration",
        "",
        f"- source ids: `{args.source_ids or 'all'}`",
        f"- max train rows per module: `{args.train_rows_per_module}`",
        f"- max export rows: `{args.max_export_rows or 'all'}`",
        f"- max train missing fraction: `{args.max_train_missing_fraction}`",
        f"- center constraint: `{args.center_constraint}`",
        f"- memberships per input: `{args.memberships}`",
        f"- epochs: `{args.epochs}`",
        f"- learning rate: `{args.learning_rate}`",
        f"- random seed: `{args.random_seed}`",
        "",
        "## Alignment",
        "",
        f"- source state rows: `{_format_int(alignment['state_rows'])}`",
        f"- panel matched rows: `{_format_int(alignment['panel_matched_rows'])}`",
        f"- panel missing rows: `{_format_int(alignment['panel_missing_rows'])}`",
        f"- exported adaptive rows: `{_format_int(alignment['export_rows'])}`",
        f"- evaluation matched rows: `{_format_int(alignment['evaluation_matched_rows'])}`",
        f"- evaluation missing rows: `{_format_int(alignment['evaluation_missing_rows'])}`",
        "",
        "## Training Module Metrics",
        "",
        "| module | status | train rows | final loss | anchor MAE | Spearman | output std | missing fraction |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in module_metrics.to_dict(orient="records"):
        lines.append(
            f"| `{row['module']}` | `{row['status']}` | {_format_int(row['train_rows'])} | "
            f"{_format_float(row['final_train_loss'])} | {_format_float(row['anchor_mae'])} | "
            f"{_format_float(row['anchor_spearman'])} | {_format_float(row['output_std'])} | "
            f"{_format_float(row['mean_missing_fraction'])} |"
        )
    lines.extend(
        [
            "",
            "## Export Anchor Metrics",
            "",
            "| module | rows | anchor MAE | anchor RMSE | Spearman | output std |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in anchor_metrics.to_dict(orient="records"):
        lines.append(
            f"| `{row['module']}` | {_format_int(row['rows'])} | {_format_float(row['anchor_mae'])} | "
            f"{_format_float(row['anchor_rmse'])} | {_format_float(row['anchor_spearman'])} | "
            f"{_format_float(row['output_std'])} |"
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
            "## Outputs",
            "",
            f"- Adaptive state: `{args.output_state.as_posix()}`",
            f"- Model checkpoints: `{args.models_dir.as_posix()}`",
            f"- Module metrics: `{args.module_metrics.as_posix()}`",
            f"- Target metrics: `{args.target_metrics.as_posix()}`",
            f"- Coverage metrics: `{args.coverage.as_posix()}`",
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
    checkpoint_paths: list[Path],
) -> None:
    payload = {
        "status": status,
        "generated_at_utc": generated_at,
        "config": {
            "source_ids": _parse_str_list(args.source_ids) if args.source_ids else [],
            "horizons": _parse_int_list(args.horizons),
            "evaluation_splits": _parse_str_list(args.evaluation_splits),
            "train_rows_per_module": int(args.train_rows_per_module),
            "max_export_rows": int(args.max_export_rows),
            "max_train_missing_fraction": float(args.max_train_missing_fraction),
            "predict_batch_rows": int(args.predict_batch_rows),
            "center_constraint": args.center_constraint,
            "memberships": int(args.memberships),
            "epochs": int(args.epochs),
            "learning_rate": float(args.learning_rate),
            "random_seed": int(args.random_seed),
            "min_width": float(args.min_width),
            "min_gap": float(args.min_gap),
            "grad_clip": float(args.grad_clip),
            "min_output_std": float(args.min_output_std),
        },
        "alignment": alignment,
        "module_metrics": module_metrics.to_dict(orient="records"),
        "inputs": [_file_record(args.panel), _file_record(args.state), _file_record(args.splits)],
        "script": _file_record(Path(__file__)),
        "adaptive_anfis_module": _file_record(Path("src/fuzzy/adaptive_anfis.py")),
        "gate2_runner_module": _file_record(Path("src/experiments/run_adaptive_anfis_real_smoke.py")),
        "outputs": [
            _file_record(args.output_state),
            _file_record(args.module_metrics),
            _file_record(args.target_metrics),
            _file_record(args.coverage),
            _file_record(args.memberships_initial),
            _file_record(args.memberships_final),
            _file_record(args.report),
            _path_record(args.models_dir),
        ],
        "checkpoints": [_file_record(path) for path in checkpoint_paths],
    }
    _write_json_atomic(payload, args.manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--output-state", type=Path, default=DEFAULT_OUTPUT_STATE)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--module-metrics", type=Path, default=DEFAULT_MODULE_METRICS)
    parser.add_argument("--target-metrics", type=Path, default=DEFAULT_TARGET_METRICS)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--memberships-initial", type=Path, default=DEFAULT_MEMBERSHIPS_INITIAL)
    parser.add_argument("--memberships-final", type=Path, default=DEFAULT_MEMBERSHIPS_FINAL)
    parser.add_argument("--source-ids", default="")
    parser.add_argument("--horizons", default="1,2,3")
    parser.add_argument("--evaluation-splits", default="train,validation,test")
    parser.add_argument("--train-rows-per-module", type=int, default=4096)
    parser.add_argument("--max-export-rows", type=int, default=0)
    parser.add_argument("--max-train-missing-fraction", type=float, default=0.5)
    parser.add_argument("--predict-batch-rows", type=int, default=32768)
    parser.add_argument("--center-constraint", choices=["ordered", "unit"], default="unit")
    parser.add_argument("--min-module-rows", type=int, default=64)
    parser.add_argument("--memberships", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=80)
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
    if args.max_export_rows < 0:
        raise ValueError("--max-export-rows must be non-negative")
    if args.predict_batch_rows <= 0:
        raise ValueError("--predict-batch-rows must be positive")
    if not 0.0 <= args.max_train_missing_fraction <= 1.0:
        raise ValueError("--max-train-missing-fraction must be in [0, 1]")
    set_reproducible_seed(args.random_seed)
    generated_at = datetime.now(timezone.utc).isoformat()
    joined, export_frame, alignment = build_joined_surface(args)
    training_frame = build_training_frame(joined, args)
    models, module_metrics, memberships_initial, memberships_final = train_modules(training_frame, args)
    predicted = predict_modules(models, export_frame, args)
    adaptive_state = adaptive_state_from_predictions(predicted)
    evaluation_frame, evaluation_alignment = target_frame(adaptive_state, load_state(args.state), args)
    alignment.update(evaluation_alignment)
    target_metrics_frame = target_metrics(evaluation_frame)
    anchor_metrics = state_anchor_metrics(adaptive_state, load_state(args.state))
    coverage = coverage_frame(training_frame)
    checkpoint_paths = save_checkpoints(models, args)
    status = (
        "completed"
        if alignment["panel_missing_rows"] == 0
        and bool((module_metrics["status"] == "passed").all())
        and not target_metrics_frame.empty
        and not adaptive_state.empty
        else "failed"
    )
    _write_parquet_atomic(adaptive_state, args.output_state)
    _write_csv_atomic(module_metrics, args.module_metrics)
    _write_csv_atomic(target_metrics_frame, args.target_metrics)
    _write_csv_atomic(coverage, args.coverage)
    _write_csv_atomic(memberships_initial, args.memberships_initial)
    _write_csv_atomic(memberships_final, args.memberships_final)
    write_report(
        args=args,
        generated_at=generated_at,
        status=status,
        alignment=alignment,
        module_metrics=module_metrics,
        anchor_metrics=anchor_metrics,
        target_metrics_frame=target_metrics_frame,
    )
    write_manifest(
        args=args,
        generated_at=generated_at,
        status=status,
        alignment=alignment,
        module_metrics=module_metrics,
        checkpoint_paths=checkpoint_paths,
    )
    print(f"wrote {args.output_state}")
    print(f"wrote {args.report}")
    print(f"wrote {args.manifest}")


if __name__ == "__main__":
    main()
