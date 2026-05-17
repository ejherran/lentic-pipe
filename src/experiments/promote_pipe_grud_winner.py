#!/usr/bin/env python
"""Promote a selected PIPE/GRU-D sweep trial to the canonical model artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import pandas as pd

from src.experiments.train_pipe_grud import (
    DEFAULT_BLEND_SEARCH,
    DEFAULT_BLEND_WEIGHTS,
    DEFAULT_CHECKPOINT,
    DEFAULT_COMPARISON,
    DEFAULT_EXAMPLES,
    DEFAULT_MANIFEST,
    DEFAULT_METRICS,
    DEFAULT_MODEL,
    DEFAULT_PERSISTENCE_METRICS,
    DEFAULT_REPORT,
    DEFAULT_TRAINING_CURVE,
)


DEFAULT_COMMON_EVAL = Path("reports/pipe_grud/pipe_grud_sweep_common_eval.csv")
DEFAULT_COMMON_EVAL_MANIFEST = Path("reports/pipe_grud/pipe_grud_sweep_common_eval_manifest.json")
DEFAULT_PROMOTION_REPORT = Path("reports/pipe_grud/pipe_grud_promotion_report.md")
DEFAULT_PROMOTION_MANIFEST = Path("reports/pipe_grud/pipe_grud_promotion_manifest.json")
DEFAULT_MODEL_BACKUP_ROOT = Path("models/pipe_grud/promotion_backups")
DEFAULT_REPORT_BACKUP_ROOT = Path("reports/pipe_grud/promotion_backups")


SOURCE_REPORT_FILES = {
    "metrics": "pipe_grud_metrics.csv",
    "persistence_metrics": "pipe_grud_persistence_metrics.csv",
    "comparison": "pipe_grud_persistence_comparison.csv",
    "blend_weights": "pipe_grud_output_blend_weights.csv",
    "blend_search": "pipe_grud_output_blend_search.csv",
    "training_curve": "pipe_grud_training_curve.csv",
    "examples": "pipe_grud_prediction_examples.csv",
    "report": "pipe_grud_report.md",
    "manifest": "pipe_grud_manifest.json",
}


DESTINATION_PATHS = {
    "model": DEFAULT_MODEL,
    "checkpoint": DEFAULT_CHECKPOINT,
    "metrics": DEFAULT_METRICS,
    "persistence_metrics": DEFAULT_PERSISTENCE_METRICS,
    "comparison": DEFAULT_COMPARISON,
    "blend_weights": DEFAULT_BLEND_WEIGHTS,
    "blend_search": DEFAULT_BLEND_SEARCH,
    "training_curve": DEFAULT_TRAINING_CURVE,
    "examples": DEFAULT_EXAMPLES,
    "report": DEFAULT_REPORT,
}


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


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


def _copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copy2(source, tmp_path)
    tmp_path.replace(destination)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def select_trial(common_eval: pd.DataFrame, *, rank: int, trial_id: str | None) -> pd.Series:
    if trial_id:
        selected = common_eval[common_eval["trial_id"] == trial_id]
        if selected.empty:
            raise ValueError(f"Trial id not found in common evaluation: {trial_id}")
        return selected.sort_values("common_selection_rank").iloc[0]
    selected = common_eval[common_eval["common_selection_rank"] == rank]
    if selected.empty:
        raise ValueError(f"Common selection rank not found: {rank}")
    return selected.iloc[0]


def source_paths_for_trial(trial: pd.Series) -> dict[str, Path]:
    model_path = Path(str(trial.model_path))
    report_path = Path(str(trial.trial_report_path))
    report_dir = report_path.parent
    paths = {
        "model": model_path,
        "checkpoint": model_path.parent / "pipe_grud_checkpoint.pt",
    }
    paths.update({key: report_dir / filename for key, filename in SOURCE_REPORT_FILES.items()})
    missing = [path.as_posix() for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Selected trial is incomplete; missing files: {missing}")
    return paths


def backup_existing(destinations: dict[str, Path], args: argparse.Namespace) -> list[dict[str, Any]]:
    backed_up: list[dict[str, Any]] = []
    if args.no_backup:
        return backed_up
    for key, destination in destinations.items():
        if not destination.exists():
            continue
        backup_root = args.model_backup_root if key in {"model", "checkpoint"} else args.report_backup_root
        backup_path = backup_root / args.promotion_id / destination.name
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, backup_path)
        backed_up.append(
            {
                "artifact": key,
                "source": destination.as_posix(),
                "backup": backup_path.as_posix(),
                "backup_sha256": _sha256_file(backup_path),
            }
        )
    return backed_up


def promote_files(source_paths: dict[str, Path], destination_paths: dict[str, Path]) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for key, destination in destination_paths.items():
        source = source_paths[key]
        _copy_atomic(source, destination)
        copied.append(
            {
                "artifact": key,
                "source": source.as_posix(),
                "destination": destination.as_posix(),
                "source_sha256": _sha256_file(source),
                "destination_sha256": _sha256_file(destination),
            }
        )
    return copied


def promoted_model_manifest(
    *,
    trial: pd.Series,
    trial_manifest: dict[str, Any],
    common_eval_manifest: dict[str, Any] | None,
    copied: list[dict[str, Any]],
    backups: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    outputs = [record["destination"] for record in copied]
    inputs = [
        _file_record(Path(str(trial.manifest_path))) if "manifest_path" in trial and Path(str(trial.manifest_path)).exists() else None,
        _file_record(args.common_eval),
        _file_record(args.common_eval_manifest) if args.common_eval_manifest.exists() else None,
    ]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "model_version": trial_manifest.get("model_version", "pipe_grud_v0"),
        "config": trial_manifest.get("config", {}),
        "row_counts": trial_manifest.get("row_counts", {}),
        "selection": trial_manifest.get("selection", {}),
        "common_evaluation_selection": trial.to_dict(),
        "promotion": {
            "promotion_id": args.promotion_id,
            "source_trial_id": trial.trial_id,
            "source_trial_manifest": str(trial.manifest_path) if "manifest_path" in trial else None,
            "common_eval_manifest": args.common_eval_manifest.as_posix() if args.common_eval_manifest.exists() else None,
            "copied": copied,
            "backups": backups,
        },
        "inputs": [record for record in inputs if record is not None],
        "outputs": [_file_record(Path(path)) for path in outputs if Path(path).exists()],
        "source_trial_manifest_payload": trial_manifest,
        "common_eval_manifest_payload": common_eval_manifest,
        "script": _file_record(Path(__file__)),
    }


def write_promotion_report(
    *,
    trial: pd.Series,
    copied: list[dict[str, Any]],
    backups: list[dict[str, Any]],
    args: argparse.Namespace,
) -> None:
    lines = [
        "# PIPE/GRU-D Promotion Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Promotion id: `{args.promotion_id}`",
        "",
        "## Selected Trial",
        "",
        f"- Trial: `{trial.trial_id}`",
        f"- Common selection rank: `{int(trial.common_selection_rank)}`",
        f"- History length: `{int(trial.history_length)}`",
        f"- Hidden dimension: `{int(trial.hidden_dim)}`",
        f"- MSE weight: `{_format_float(float(trial.mse_weight))}`",
        f"- Common validation objective: `{_format_float(float(trial.common_validation_objective))}`",
        f"- Common validation RMSE: `{_format_float(float(trial.common_validation_rmse))}`",
        f"- Common validation MAE: `{_format_float(float(trial.common_validation_mae))}`",
        f"- Common test RMSE: `{_format_float(float(trial.common_test_rmse))}`",
        f"- Common test MAE: `{_format_float(float(trial.common_test_mae))}`",
        "",
        "## Copied Artifacts",
        "",
        "| artifact | source | destination | sha256 match |",
        "|---|---|---|---|",
    ]
    for record in copied:
        match = record["source_sha256"] == record["destination_sha256"]
        lines.append(
            f"| `{record['artifact']}` | `{record['source']}` | `{record['destination']}` | `{match}` |"
        )
    lines.extend(["", "## Backups", ""])
    if not backups:
        lines.append("No previous canonical artifacts were backed up.")
    else:
        lines.extend(["| artifact | backup | sha256 |", "|---|---|---|"])
        for record in backups:
            lines.append(f"| `{record['artifact']}` | `{record['backup']}` | `{record['backup_sha256']}` |")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Promotion manifest: `{args.promotion_manifest}`",
            f"- Canonical model manifest: `{args.destination_manifest}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), args.promotion_report)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote a PIPE/GRU-D sweep winner to canonical artifacts.")
    parser.add_argument("--common-eval", type=Path, default=DEFAULT_COMMON_EVAL)
    parser.add_argument("--common-eval-manifest", type=Path, default=DEFAULT_COMMON_EVAL_MANIFEST)
    parser.add_argument("--rank", type=int, default=1)
    parser.add_argument("--trial-id", default=None)
    parser.add_argument("--promotion-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--destination-model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--destination-checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--destination-metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--destination-persistence-metrics", type=Path, default=DEFAULT_PERSISTENCE_METRICS)
    parser.add_argument("--destination-comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--destination-blend-weights", type=Path, default=DEFAULT_BLEND_WEIGHTS)
    parser.add_argument("--destination-blend-search", type=Path, default=DEFAULT_BLEND_SEARCH)
    parser.add_argument("--destination-training-curve", type=Path, default=DEFAULT_TRAINING_CURVE)
    parser.add_argument("--destination-examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--destination-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--destination-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--promotion-report", type=Path, default=DEFAULT_PROMOTION_REPORT)
    parser.add_argument("--promotion-manifest", type=Path, default=DEFAULT_PROMOTION_MANIFEST)
    parser.add_argument("--model-backup-root", type=Path, default=DEFAULT_MODEL_BACKUP_ROOT)
    parser.add_argument("--report-backup-root", type=Path, default=DEFAULT_REPORT_BACKUP_ROOT)
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rank < 1:
        raise ValueError("--rank must be >= 1")
    common_eval = pd.read_csv(args.common_eval)
    trial = select_trial(common_eval, rank=args.rank, trial_id=args.trial_id)
    source_paths = source_paths_for_trial(trial)
    destination_paths = dict(DESTINATION_PATHS)
    destination_paths["model"] = args.destination_model
    destination_paths["checkpoint"] = args.destination_checkpoint
    destination_paths["metrics"] = args.destination_metrics
    destination_paths["persistence_metrics"] = args.destination_persistence_metrics
    destination_paths["comparison"] = args.destination_comparison
    destination_paths["blend_weights"] = args.destination_blend_weights
    destination_paths["blend_search"] = args.destination_blend_search
    destination_paths["training_curve"] = args.destination_training_curve
    destination_paths["examples"] = args.destination_examples
    destination_paths["report"] = args.destination_report
    if args.dry_run:
        print(f"selected trial: {trial.trial_id}", flush=True)
        for key, destination in destination_paths.items():
            print(f"would copy {key}: {source_paths[key]} -> {destination}", flush=True)
        return
    backup_paths = dict(destination_paths)
    backup_paths["manifest"] = args.destination_manifest
    backups = backup_existing(backup_paths, args)
    copied = promote_files(source_paths, destination_paths)
    trial_manifest = _load_json(source_paths["manifest"])
    common_eval_manifest = _load_json(args.common_eval_manifest) if args.common_eval_manifest.exists() else None
    manifest = promoted_model_manifest(
        trial=trial,
        trial_manifest=trial_manifest,
        common_eval_manifest=common_eval_manifest,
        copied=copied,
        backups=backups,
        args=args,
    )
    _write_json_atomic(manifest, args.destination_manifest)
    promotion_manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "promotion_id": args.promotion_id,
        "selected_trial": trial.to_dict(),
        "copied": copied,
        "backups": backups,
        "canonical_manifest": _file_record(args.destination_manifest),
        "script": _file_record(Path(__file__)),
    }
    _write_json_atomic(promotion_manifest, args.promotion_manifest)
    write_promotion_report(trial=trial, copied=copied, backups=backups, args=args)
    print(f"promoted trial {trial.trial_id}", flush=True)
    print(f"wrote {args.destination_manifest}", flush=True)
    print(f"wrote {args.promotion_report}", flush=True)
    print(f"wrote {args.promotion_manifest}", flush=True)


if __name__ == "__main__":
    main()
