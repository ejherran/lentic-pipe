#!/usr/bin/env python
"""Run the Gate 1 synthetic smoke for the adaptive ANFIS layer."""

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

from src.fuzzy.adaptive_anfis import (
    _require_torch,
    make_adaptive_anfis,
    max_parameter_delta,
    parameter_snapshot,
    set_reproducible_seed,
    train_supervised_anfis,
)


DEFAULT_REPORT_DIR = Path("reports/anfis")
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "adaptive_anfis_synthetic_smoke_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "adaptive_anfis_synthetic_smoke_manifest.json"
DEFAULT_METRICS = DEFAULT_REPORT_DIR / "adaptive_anfis_synthetic_smoke_metrics.csv"


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


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def synthetic_module_data(module: str, rows: int, seed: int) -> tuple[np.ndarray, np.ndarray, list[str]]:
    rng = np.random.default_rng(seed)
    if module == "ANFIS-N":
        names = ["TP_scaled", "TN_scaled", "ratio_imbalance_scaled"]
        x = rng.uniform(0.0, 1.0, size=(rows, len(names))).astype("float32")
        y = 0.45 * x[:, 0] + 0.35 * x[:, 1] + 0.20 * x[:, 2]
    elif module == "ANFIS-F":
        names = ["DO_good", "pH_good", "turbidity_good", "secchi_good"]
        x = rng.uniform(0.0, 1.0, size=(rows, len(names))).astype("float32")
        y = 0.30 * x[:, 0] + 0.25 * x[:, 1] + 0.20 * x[:, 2] + 0.25 * x[:, 3]
    elif module == "ANFIS-T":
        names = ["temperature_favorable", "current_chla_pressure"]
        x = rng.uniform(0.0, 1.0, size=(rows, len(names))).astype("float32")
        y = 0.45 * x[:, 0] + 0.55 * x[:, 1]
    else:
        raise ValueError(f"Unknown synthetic module: {module}")
    noise = rng.normal(0.0, 0.015, size=rows).astype("float32")
    return x, np.clip(y + noise, 0.0, 1.0).astype("float32"), names


def run_module(module: str, args: argparse.Namespace) -> dict[str, Any]:
    torch = _require_torch()
    module_seed_offsets = {"ANFIS-N": 101, "ANFIS-F": 202, "ANFIS-T": 303}
    x, y, feature_names = synthetic_module_data(module, args.rows, args.random_seed + module_seed_offsets[module])
    model = make_adaptive_anfis(
        input_dim=x.shape[1],
        membership_count=args.memberships,
        min_width=args.min_width,
        min_gap=args.min_gap,
    )
    before = parameter_snapshot(model)
    with torch.no_grad():
        initial_prediction = model(torch.as_tensor(x, dtype=torch.float32))
        initial_loss = torch.nn.functional.mse_loss(initial_prediction, torch.as_tensor(y, dtype=torch.float32)).item()
    curve = train_supervised_anfis(
        model,
        x,
        y,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        random_seed=args.random_seed,
        grad_clip=args.grad_clip,
    )
    with torch.no_grad():
        prediction = model(torch.as_tensor(x, dtype=torch.float32))
        final_loss = torch.nn.functional.mse_loss(prediction, torch.as_tensor(y, dtype=torch.float32)).item()
    prediction_np = prediction.detach().cpu().numpy()
    finite_loss = bool(np.isfinite(final_loss))
    output_in_range = bool((prediction_np >= -1e-6).all() and (prediction_np <= 1.0 + 1e-6).all())
    ordered = model.centers_are_ordered()
    parameter_delta = max_parameter_delta(model, before)
    relative_improvement = (float(initial_loss) - float(final_loss)) / max(float(initial_loss), 1e-12)
    status = "passed" if finite_loss and output_in_range and ordered and parameter_delta > 0 and relative_improvement > 0 else "failed"
    centers = model.ordered_centers().detach().cpu().numpy()
    widths = model.positive_widths().detach().cpu().numpy()
    return {
        "module": module,
        "status": status,
        "rows": int(args.rows),
        "input_dim": int(x.shape[1]),
        "feature_names": feature_names,
        "memberships": int(args.memberships),
        "rules": int(model.rule_count),
        "initial_loss": float(initial_loss),
        "final_loss": float(final_loss),
        "relative_loss_improvement": float(relative_improvement),
        "finite_loss": finite_loss,
        "output_min": float(prediction_np.min()),
        "output_max": float(prediction_np.max()),
        "output_in_range": output_in_range,
        "centers_ordered": ordered,
        "max_parameter_delta": float(parameter_delta),
        "center_min": float(centers.min()),
        "center_max": float(centers.max()),
        "width_min": float(widths.min()),
        "width_max": float(widths.max()),
        "curve": curve,
    }


def metrics_frame(results: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for result in results:
        rows.append(
            {
                "module": result["module"],
                "status": result["status"],
                "rows": result["rows"],
                "input_dim": result["input_dim"],
                "memberships": result["memberships"],
                "rules": result["rules"],
                "initial_loss": result["initial_loss"],
                "final_loss": result["final_loss"],
                "relative_loss_improvement": result["relative_loss_improvement"],
                "finite_loss": result["finite_loss"],
                "output_min": result["output_min"],
                "output_max": result["output_max"],
                "output_in_range": result["output_in_range"],
                "centers_ordered": result["centers_ordered"],
                "max_parameter_delta": result["max_parameter_delta"],
                "center_min": result["center_min"],
                "center_max": result["center_max"],
                "width_min": result["width_min"],
                "width_max": result["width_max"],
            }
        )
    return pd.DataFrame(rows)


def write_report(results: list[dict[str, Any]], metrics: pd.DataFrame, args: argparse.Namespace, generated_at: str) -> None:
    status = "completed" if (metrics["status"] == "passed").all() else "failed"
    lines = [
        "# Adaptive ANFIS Synthetic Smoke Report",
        "",
        f"Generated at UTC: `{generated_at}`",
        "",
        f"Status: `{status}`",
        "",
        "## Scope",
        "",
        "This Gate 1 smoke uses synthetic data only. It checks that a small",
        "trainable Gaussian-membership Sugeno ANFIS can learn bounded module",
        "mappings before any real-data adaptive ANFIS claim is made.",
        "",
        "## Configuration",
        "",
        f"- rows per module: `{args.rows}`",
        f"- memberships per input: `{args.memberships}`",
        f"- epochs: `{args.epochs}`",
        f"- learning rate: `{args.learning_rate}`",
        f"- random seed: `{args.random_seed}`",
        "",
        "## Module Metrics",
        "",
        "| module | status | rows | input dim | rules | initial loss | final loss | relative improvement | output range | centers ordered | max parameter delta |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|",
    ]
    for row in metrics.itertuples(index=False):
        lines.append(
            f"| `{row.module}` | `{row.status}` | {int(row.rows):,} | {int(row.input_dim)} | {int(row.rules):,} | "
            f"{_format_float(float(row.initial_loss))} | {_format_float(float(row.final_loss))} | "
            f"{_format_float(float(row.relative_loss_improvement))} | "
            f"`{_format_float(float(row.output_min))}-{_format_float(float(row.output_max))}` | "
            f"`{bool(row.centers_ordered)}` | {_format_float(float(row.max_parameter_delta))} |"
        )
    lines.extend(
        [
            "",
            "## Gate Checks",
            "",
            f"- finite loss: `{bool(metrics['finite_loss'].all())}`",
            f"- outputs in `[0, 1]`: `{bool(metrics['output_in_range'].all())}`",
            f"- ordered centers: `{bool(metrics['centers_ordered'].all())}`",
            f"- parameter update observed: `{bool((metrics['max_parameter_delta'] > 0).all())}`",
            f"- loss improved: `{bool((metrics['relative_loss_improvement'] > 0).all())}`",
            "",
            "## Outputs",
            "",
            f"- Metrics: `{args.metrics.as_posix()}`",
            f"- Manifest: `{args.manifest.as_posix()}`",
        ]
    )
    _write_text_atomic("\n".join(lines) + "\n", args.report)


def write_manifest(results: list[dict[str, Any]], metrics: pd.DataFrame, args: argparse.Namespace, generated_at: str) -> None:
    status = "completed" if (metrics["status"] == "passed").all() else "failed"
    curve_summary = {}
    for result in results:
        curve = result["curve"]
        losses = [float(row["loss"]) for row in curve]
        curve_summary[result["module"]] = {
            "epochs": int(len(curve)),
            "initial_loss": float(losses[0]),
            "final_loss": float(result["final_loss"]),
            "min_loss": float(min([*losses, float(result["final_loss"])])),
        }
    payload = {
        "status": status,
        "generated_at_utc": generated_at,
        "config": {
            "rows": int(args.rows),
            "memberships": int(args.memberships),
            "epochs": int(args.epochs),
            "learning_rate": float(args.learning_rate),
            "random_seed": int(args.random_seed),
            "min_width": float(args.min_width),
            "min_gap": float(args.min_gap),
            "grad_clip": float(args.grad_clip),
        },
        "modules": [
            {key: value for key, value in result.items() if key != "curve"}
            for result in results
        ],
        "inputs": [],
        "training_curve_summary": curve_summary,
        "script": _file_record(Path(__file__)),
        "adaptive_anfis_module": _file_record(Path("src/fuzzy/adaptive_anfis.py")),
        "outputs": [_file_record(args.metrics), _file_record(args.report)],
    }
    _write_json_atomic(payload, args.manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--rows", type=int, default=128)
    parser.add_argument("--memberships", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--min-width", type=float, default=0.03)
    parser.add_argument("--min-gap", type=float, default=1e-4)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rows <= 0:
        raise ValueError("--rows must be positive")
    set_reproducible_seed(args.random_seed)
    generated_at = datetime.now(timezone.utc).isoformat()
    results = [run_module(module, args) for module in ["ANFIS-N", "ANFIS-F", "ANFIS-T"]]
    metrics = metrics_frame(results)
    _write_csv_atomic(metrics, args.metrics)
    write_report(results, metrics, args, generated_at)
    write_manifest(results, metrics, args, generated_at)
    print(f"wrote {args.report}")
    print(f"wrote {args.manifest}")


if __name__ == "__main__":
    main()
