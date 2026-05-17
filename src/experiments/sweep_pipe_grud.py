#!/usr/bin/env python
"""Run a controlled hyperparameter sweep for the PIPE/GRU-D temporal model."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import pandas as pd

from src.pandas_utils import dataframe_rows

from src.experiments.train_pipe_grud import DEFAULT_SEQUENCE_MANIFEST, DEFAULT_SEQUENCES


DEFAULT_REPORT_DIR = Path("reports/pipe_grud")
DEFAULT_MODEL_DIR = Path("models/pipe_grud")
DEFAULT_SUMMARY = DEFAULT_REPORT_DIR / "pipe_grud_sweep_summary.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_grud_sweep_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_grud_sweep_manifest.json"
DEFAULT_TRIAL_REPORT_ROOT = DEFAULT_REPORT_DIR / "sweep_trials"
DEFAULT_TRIAL_MODEL_ROOT = DEFAULT_MODEL_DIR / "sweep_trials"
TRAIN_SCRIPT = PROJECT_ROOT / "src/experiments/train_pipe_grud.py"


@dataclass(frozen=True)
class TrialConfig:
    trial_id: str
    history_length: int
    hidden_dim: int
    mse_weight: float
    learning_rate: float
    random_seed: int


@dataclass(frozen=True)
class TrialPaths:
    report_dir: Path
    model_dir: Path
    model: Path
    checkpoint: Path
    metrics: Path
    persistence_metrics: Path
    comparison: Path
    blend_weights: Path
    blend_search: Path
    training_curve: Path
    examples: Path
    report: Path
    manifest: Path


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _format_int(value: int) -> str:
    return f"{value:,}"


def _slug_float(value: float) -> str:
    text = f"{value:g}".replace("-", "m").replace(".", "p")
    return text


def _parse_int_grid(value: str) -> list[int]:
    values: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        parsed = int(part)
        if parsed < 1:
            raise ValueError("Integer grid values must be >= 1")
        if parsed not in values:
            values.append(parsed)
    if not values:
        raise ValueError("Grid must contain at least one integer value")
    return values


def _parse_float_grid(value: str, *, minimum: float = 0.0, exclusive_minimum: bool = False) -> list[float]:
    values: list[float] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        parsed = float(part)
        invalid = parsed < minimum or (exclusive_minimum and parsed <= minimum)
        if invalid:
            bound = f"> {minimum}" if exclusive_minimum else f">= {minimum}"
            raise ValueError(f"Float grid values must be {bound}")
        if parsed not in values:
            values.append(parsed)
    if not values:
        raise ValueError("Grid must contain at least one float value")
    return values


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


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


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_trial_configs(args: argparse.Namespace) -> list[TrialConfig]:
    history_lengths = _parse_int_grid(args.history_lengths)
    hidden_dims = _parse_int_grid(args.hidden_dims)
    mse_weights = _parse_float_grid(args.mse_weights, minimum=0.0)
    learning_rates = _parse_float_grid(args.learning_rates, minimum=0.0, exclusive_minimum=True)
    configs: list[TrialConfig] = []
    for index, (history_length, hidden_dim, mse_weight, learning_rate) in enumerate(
        itertools.product(history_lengths, hidden_dims, mse_weights, learning_rates), start=1
    ):
        seed = args.random_seed if not args.vary_seed else args.random_seed + index - 1
        trial_id = (
            f"h{history_length:02d}_hd{hidden_dim:03d}_mse{_slug_float(mse_weight)}"
            f"_lr{_slug_float(learning_rate)}_seed{seed}"
        )
        configs.append(
            TrialConfig(
                trial_id=trial_id,
                history_length=history_length,
                hidden_dim=hidden_dim,
                mse_weight=mse_weight,
                learning_rate=learning_rate,
                random_seed=seed,
            )
        )
    if args.limit_trials is not None:
        configs = configs[: args.limit_trials]
    return configs


def trial_paths(config: TrialConfig, args: argparse.Namespace) -> TrialPaths:
    report_dir = args.trial_report_root / args.sweep_id / config.trial_id
    model_dir = args.trial_model_root / args.sweep_id / config.trial_id
    return TrialPaths(
        report_dir=report_dir,
        model_dir=model_dir,
        model=model_dir / "pipe_grud_model.pt",
        checkpoint=model_dir / "pipe_grud_checkpoint.pt",
        metrics=report_dir / "pipe_grud_metrics.csv",
        persistence_metrics=report_dir / "pipe_grud_persistence_metrics.csv",
        comparison=report_dir / "pipe_grud_persistence_comparison.csv",
        blend_weights=report_dir / "pipe_grud_output_blend_weights.csv",
        blend_search=report_dir / "pipe_grud_output_blend_search.csv",
        training_curve=report_dir / "pipe_grud_training_curve.csv",
        examples=report_dir / "pipe_grud_prediction_examples.csv",
        report=report_dir / "pipe_grud_report.md",
        manifest=report_dir / "pipe_grud_manifest.json",
    )


def build_train_command(config: TrialConfig, paths: TrialPaths, args: argparse.Namespace, *, resume: bool) -> list[str]:
    command = [
        sys.executable,
        TRAIN_SCRIPT.as_posix(),
        "--sequences",
        args.sequences.as_posix(),
        "--sequence-manifest",
        args.sequence_manifest.as_posix(),
        "--model",
        paths.model.as_posix(),
        "--checkpoint",
        paths.checkpoint.as_posix(),
        "--metrics",
        paths.metrics.as_posix(),
        "--persistence-metrics",
        paths.persistence_metrics.as_posix(),
        "--comparison",
        paths.comparison.as_posix(),
        "--blend-weights",
        paths.blend_weights.as_posix(),
        "--blend-search",
        paths.blend_search.as_posix(),
        "--training-curve",
        paths.training_curve.as_posix(),
        "--examples",
        paths.examples.as_posix(),
        "--report",
        paths.report.as_posix(),
        "--manifest",
        paths.manifest.as_posix(),
        "--history-length",
        str(config.history_length),
        "--hidden-dim",
        str(config.hidden_dim),
        "--num-layers",
        str(args.num_layers),
        "--dropout",
        str(args.dropout),
        "--residual-mode",
        args.residual_mode,
        "--mse-weight",
        str(config.mse_weight),
        "--checkpoint-selection-metric",
        args.checkpoint_selection_metric,
        "--blend-selection-metric",
        args.blend_selection_metric,
        "--blend-grid",
        args.blend_grid,
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--learning-rate",
        str(config.learning_rate),
        "--weight-decay",
        str(args.weight_decay),
        "--grad-clip",
        str(args.grad_clip),
        "--random-seed",
        str(config.random_seed),
        "--max-train-windows",
        str(args.max_train_windows),
        "--max-eval-windows",
        str(args.max_eval_windows),
        "--max-examples",
        str(args.max_examples),
        "--device",
        args.device,
        "--progress-every-batches",
        str(args.progress_every_batches),
    ]
    if args.max_rows is not None:
        command.extend(["--max-rows", str(args.max_rows)])
    if resume and paths.checkpoint.exists():
        command.append("--resume")
    return command


def run_trial(config: TrialConfig, paths: TrialPaths, args: argparse.Namespace) -> tuple[int, float, bool]:
    resume_trial = bool(args.resume)
    command = build_train_command(config, paths, args, resume=resume_trial)
    print(f"\ntrial {config.trial_id}: starting", flush=True)
    print(" ".join(command), flush=True)
    started = time.monotonic()
    process = subprocess.Popen(command)
    interrupted = False
    try:
        return_code = process.wait()
    except KeyboardInterrupt:
        interrupted = True
        print("interrupt requested; waiting for active trial to write its latest checkpoint/report", flush=True)
        try:
            return_code = process.wait(timeout=args.interrupt_wait_seconds)
        except subprocess.TimeoutExpired:
            process.terminate()
            return_code = process.wait()
    elapsed = time.monotonic() - started
    print(f"trial {config.trial_id}: return_code={return_code}; elapsed={elapsed:,.1f}s", flush=True)
    return int(return_code), float(elapsed), interrupted


def _metric_row(metrics: pd.DataFrame, split: str) -> dict[str, float | int | None]:
    rows = metrics[(metrics["split"] == split) & (metrics["target"] == "all")]
    if rows.empty:
        return {
            f"{split}_rows": None,
            f"{split}_rmse": None,
            f"{split}_mae": None,
            f"{split}_nll": None,
            f"{split}_interval_90_coverage": None,
        }
    row = rows.iloc[0]
    return {
        f"{split}_rows": int(row.rows),
        f"{split}_rmse": float(row.rmse),
        f"{split}_mae": float(row.mae),
        f"{split}_nll": float(row.nll),
        f"{split}_interval_90_coverage": float(row.interval_90_coverage),
    }


def _comparison_row(comparison: pd.DataFrame, split: str) -> dict[str, float | int | None]:
    rows = comparison[(comparison["split"] == split) & (comparison["target"] == "all")]
    if rows.empty:
        return {
            f"{split}_rmse_relative_improvement": None,
            f"{split}_mae_relative_improvement": None,
        }
    row = rows.iloc[0]
    return {
        f"{split}_rmse_relative_improvement": float(row.rmse_relative_improvement),
        f"{split}_mae_relative_improvement": float(row.mae_relative_improvement),
    }


def collect_trial_summary(
    config: TrialConfig,
    paths: TrialPaths,
    *,
    return_code: int | None,
    elapsed_seconds: float | None,
    skipped: bool,
) -> dict[str, Any]:
    manifest = _load_json(paths.manifest) if paths.manifest.exists() else {}
    status = str(manifest.get("status", "missing_manifest"))
    if return_code not in (None, 0) and status == "missing_manifest":
        status = "failed"
    if skipped:
        status = "skipped_completed"
    selection = manifest.get("selection", {})
    row_counts = manifest.get("row_counts", {})
    sampled_windows = row_counts.get("sampled_windows", {})
    row: dict[str, Any] = {
        "trial_id": config.trial_id,
        "status": status,
        "return_code": return_code,
        "elapsed_seconds": elapsed_seconds,
        "history_length": config.history_length,
        "hidden_dim": config.hidden_dim,
        "mse_weight": config.mse_weight,
        "learning_rate": config.learning_rate,
        "random_seed": config.random_seed,
        "best_epoch": selection.get("best_epoch"),
        "best_validation_objective": selection.get("best_validation_objective"),
        "best_validation_loss": selection.get("best_validation_loss"),
        "best_validation_rmse_all": selection.get("best_validation_rmse_all"),
        "best_validation_mae_all": selection.get("best_validation_mae_all"),
        "sampled_train_windows": sampled_windows.get("train"),
        "sampled_validation_windows": sampled_windows.get("validation"),
        "sampled_test_windows": sampled_windows.get("test"),
        "model_path": paths.model.as_posix(),
        "report_path": paths.report.as_posix(),
        "manifest_path": paths.manifest.as_posix(),
    }
    if paths.metrics.exists():
        metrics = pd.read_csv(paths.metrics)
        for split in ["train", "validation", "test"]:
            row.update(_metric_row(metrics, split))
    if paths.comparison.exists():
        comparison = pd.read_csv(paths.comparison)
        for split in ["train", "validation", "test"]:
            row.update(_comparison_row(comparison, split))
    return row


def rank_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    out = summary.copy()
    out["selection_rank"] = pd.NA
    completed_mask = out["status"].isin(["completed", "skipped_completed"]) & out["best_validation_objective"].notna()
    completed = out[completed_mask].sort_values(
        ["best_validation_objective", "validation_rmse", "validation_mae", "test_rmse", "trial_id"],
        na_position="last",
    )
    for rank, index in enumerate(completed.index, start=1):
        out.loc[index, "selection_rank"] = rank
    return out.sort_values(["selection_rank", "trial_id"], na_position="last").reset_index(drop=True)


def write_report(summary: pd.DataFrame, args: argparse.Namespace, started_at: datetime) -> None:
    completed = summary[summary["selection_rank"].notna()].copy() if not summary.empty else pd.DataFrame()
    best = completed.sort_values("selection_rank").iloc[0] if not completed.empty else None
    lines = [
        "# PIPE/GRU-D Hyperparameter Sweep",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        f"Sweep id: `{args.sweep_id}`",
        "",
        "## Scope",
        "",
        "This sweep compares PIPE/GRU-D hyperparameter configurations without overwriting the frozen model artifact.",
        "Ranking is selected on validation only; test metrics are included for audit after selection.",
        "History lengths change the eligible window population; use the common-window evaluation before promotion.",
        "",
        "## Grid",
        "",
        f"- History lengths: `{args.history_lengths}`",
        f"- Hidden dimensions: `{args.hidden_dims}`",
        f"- MSE weights: `{args.mse_weights}`",
        f"- Learning rates: `{args.learning_rates}`",
        f"- Epochs: `{args.epochs}`",
        f"- Max train windows: `{args.max_train_windows}`",
        f"- Max eval windows: `{args.max_eval_windows}`",
        "",
        "## Best Validation Selection",
        "",
    ]
    if best is None:
        lines.append("No completed trial is available yet.")
    else:
        lines.extend(
            [
                f"- Trial: `{best.trial_id}`",
                f"- History length: `{int(best.history_length)}`",
                f"- Hidden dimension: `{int(best.hidden_dim)}`",
                f"- MSE weight: `{_format_float(float(best.mse_weight))}`",
                f"- Learning rate: `{best.learning_rate:g}`",
                f"- Best epoch: `{int(best.best_epoch)}`",
                f"- Validation objective: `{_format_float(float(best.best_validation_objective))}`",
                f"- Validation RMSE all: `{_format_float(float(best.validation_rmse))}`",
                f"- Validation MAE all: `{_format_float(float(best.validation_mae))}`",
                f"- Test RMSE all: `{_format_float(float(best.test_rmse))}`",
                f"- Test MAE all: `{_format_float(float(best.test_mae))}`",
                f"- Test RMSE improvement vs persistence: `{_format_float(float(best.test_rmse_relative_improvement))}`",
                f"- Test MAE improvement vs persistence: `{_format_float(float(best.test_mae_relative_improvement))}`",
                f"- Trial report: `{best.report_path}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Ranked Trials",
            "",
            "| rank | trial | status | h | hidden | mse | lr | best epoch | validation objective | validation RMSE | validation MAE | test RMSE | test MAE |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if summary.empty:
        lines.append("| NA | `NA` | `NA` | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(summary):
            rank = "NA" if pd.isna(row.selection_rank) else str(int(row.selection_rank))
            best_epoch = "NA" if pd.isna(row.best_epoch) else str(int(row.best_epoch))
            lines.append(
                f"| {rank} | `{row.trial_id}` | `{row.status}` | {int(row.history_length)} | "
                f"{int(row.hidden_dim)} | {_format_float(float(row.mse_weight))} | {float(row.learning_rate):g} | "
                f"{best_epoch} | {_format_float(row.best_validation_objective)} | "
                f"{_format_float(row.validation_rmse)} | {_format_float(row.validation_mae)} | "
                f"{_format_float(row.test_rmse)} | {_format_float(row.test_mae)} |"
            )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Summary CSV: `{args.summary}`",
            f"- Manifest: `{args.manifest}`",
            f"- Trial reports root: `{args.trial_report_root / args.sweep_id}`",
            f"- Trial models root: `{args.trial_model_root / args.sweep_id}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(
    *,
    args: argparse.Namespace,
    summary: pd.DataFrame,
    trial_configs: list[TrialConfig],
    started_at: datetime,
    status: str,
) -> dict[str, Any]:
    completed = summary[summary["selection_rank"].notna()].copy() if not summary.empty else pd.DataFrame()
    best = completed.sort_values("selection_rank").iloc[0].to_dict() if not completed.empty else {}
    output_paths = [args.summary, args.report]
    trial_manifest_paths = [Path(path) for path in summary.get("manifest_path", []) if Path(path).exists()]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "status": status,
        "sweep_id": args.sweep_id,
        "config": {
            "history_lengths": _parse_int_grid(args.history_lengths),
            "hidden_dims": _parse_int_grid(args.hidden_dims),
            "mse_weights": _parse_float_grid(args.mse_weights, minimum=0.0),
            "learning_rates": _parse_float_grid(args.learning_rates, minimum=0.0, exclusive_minimum=True),
            "epochs": int(args.epochs),
            "batch_size": int(args.batch_size),
            "max_train_windows": int(args.max_train_windows),
            "max_eval_windows": int(args.max_eval_windows),
            "checkpoint_selection_metric": args.checkpoint_selection_metric,
            "blend_selection_metric": args.blend_selection_metric,
            "blend_grid": args.blend_grid,
            "same_seed_for_all_trials": not args.vary_seed,
            "random_seed": int(args.random_seed),
        },
        "row_counts": {
            "planned_trials": int(len(trial_configs)),
            "summary_rows": int(len(summary)),
            "completed_trials": int(summary["status"].isin(["completed", "skipped_completed"]).sum())
            if not summary.empty
            else 0,
        },
        "selection": best,
        "inputs": [_file_record(args.sequences), _file_record(args.sequence_manifest)],
        "outputs": [_file_record(path) for path in output_paths if path.exists()],
        "trial_manifests": [_file_record(path) for path in trial_manifest_paths],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a controlled PIPE/GRU-D hyperparameter sweep.")
    parser.add_argument("--sequences", type=Path, default=DEFAULT_SEQUENCES)
    parser.add_argument("--sequence-manifest", type=Path, default=DEFAULT_SEQUENCE_MANIFEST)
    parser.add_argument("--sweep-id", default="pipe_grud_sweep_v0")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trial-report-root", type=Path, default=DEFAULT_TRIAL_REPORT_ROOT)
    parser.add_argument("--trial-model-root", type=Path, default=DEFAULT_TRIAL_MODEL_ROOT)
    parser.add_argument("--history-lengths", default="3,6,12")
    parser.add_argument("--hidden-dims", default="64,96,128")
    parser.add_argument("--mse-weights", default="0.25,0.5,1.0")
    parser.add_argument("--learning-rates", default="0.001")
    parser.add_argument("--num-layers", type=int, default=1)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--residual-mode", choices=["add_last", "none"], default="add_last")
    parser.add_argument("--checkpoint-selection-metric", choices=["nll", "rmse", "mae", "balanced"], default="balanced")
    parser.add_argument("--blend-selection-metric", choices=["mae", "rmse", "balanced"], default="balanced")
    parser.add_argument("--blend-grid", default="0,0.1,0.2,0.35,0.5,0.65,0.8,0.9,1")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--vary-seed", action="store_true")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--max-train-windows", type=int, default=0)
    parser.add_argument("--max-eval-windows", type=int, default=0)
    parser.add_argument("--max-examples", type=int, default=100)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit-trials", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-after-failure", action="store_true")
    parser.add_argument("--progress-every-batches", type=int, default=100)
    parser.add_argument("--interrupt-wait-seconds", type=int, default=600)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.epochs < 1:
        raise ValueError("--epochs must be >= 1")
    if args.limit_trials is not None and args.limit_trials < 1:
        raise ValueError("--limit-trials must be >= 1 when provided")
    started_at = datetime.now(timezone.utc)
    trial_configs = build_trial_configs(args)
    print(f"planned trials={len(trial_configs):,}; sweep_id={args.sweep_id}", flush=True)

    rows: list[dict[str, Any]] = []
    interrupted = False
    failed = False
    for index, config in enumerate(trial_configs, start=1):
        paths = trial_paths(config, args)
        print(f"\n[{index}/{len(trial_configs)}] {config.trial_id}", flush=True)
        if args.dry_run:
            rows.append(
                collect_trial_summary(
                    config,
                    paths,
                    return_code=None,
                    elapsed_seconds=None,
                    skipped=False,
                )
            )
            continue
        if args.resume and paths.manifest.exists():
            manifest = _load_json(paths.manifest)
            if manifest.get("status") == "completed":
                print(f"trial {config.trial_id}: already completed; skipping", flush=True)
                rows.append(
                    collect_trial_summary(
                        config,
                        paths,
                        return_code=0,
                        elapsed_seconds=0.0,
                        skipped=True,
                    )
                )
                continue
        return_code, elapsed_seconds, was_interrupted = run_trial(config, paths, args)
        rows.append(
            collect_trial_summary(
                config,
                paths,
                return_code=return_code,
                elapsed_seconds=elapsed_seconds,
                skipped=False,
            )
        )
        if was_interrupted:
            interrupted = True
            break
        if return_code != 0:
            failed = True
            if args.stop_after_failure:
                break

    summary = rank_summary(pd.DataFrame(rows))
    _write_csv_atomic(summary, args.summary)
    write_report(summary, args, started_at)
    status = "interrupted" if interrupted else "failed" if failed else "completed"
    manifest = manifest_payload(
        args=args,
        summary=summary,
        trial_configs=trial_configs,
        started_at=started_at,
        status=status,
    )
    _write_json_atomic(manifest, args.manifest)
    print(f"\nwrote {args.summary}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)
    print(f"status={status}", flush=True)


if __name__ == "__main__":
    main()
