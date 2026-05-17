#!/usr/bin/env python
"""Review expert fuzzy outputs against calibrated baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import pandas as pd

from src.pandas_utils import dataframe_rows


DEFAULT_ANFIS_DIR = Path("reports/anfis")
DEFAULT_BASELINE_METRICS = Path("reports/baselines/baseline_calibrated_metrics.csv")
DEFAULT_IRC_METRICS = DEFAULT_ANFIS_DIR / "irc1_metrics.csv"
DEFAULT_CALIBRATED_METRICS = DEFAULT_ANFIS_DIR / "irc1_calibrated_metrics.csv"
DEFAULT_REPORT = DEFAULT_ANFIS_DIR / "expert_fuzzy_review.md"
DEFAULT_COMPARISON = DEFAULT_ANFIS_DIR / "expert_fuzzy_test_comparison.csv"
DEFAULT_SOURCE_SUMMARY = DEFAULT_ANFIS_DIR / "expert_fuzzy_source_summary.csv"
DEFAULT_MANIFEST = DEFAULT_ANFIS_DIR / "expert_fuzzy_review_manifest.json"


def _format_int(value: int) -> str:
    return f"{value:,}"


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


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


def _write_json_atomic(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, object]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def load_baseline_test(path: Path) -> pd.DataFrame:
    baseline = pd.read_csv(path)
    out = baseline[
        (baseline["selection_task"] == "bloom")
        & (baseline["phase"] == "isotonic_calibrated")
        & (baseline["split"] == "test")
    ].copy()
    return out[
        [
            "horizon_months",
            "model",
            "rows",
            "threshold",
            "pr_auc",
            "roc_auc",
            "brier",
            "recall",
            "macro_f1",
        ]
    ].rename(
        columns={
            "model": "baseline_model",
            "rows": "baseline_rows",
            "threshold": "baseline_threshold",
            "pr_auc": "baseline_pr_auc",
            "roc_auc": "baseline_roc_auc",
            "brier": "baseline_brier",
            "recall": "baseline_recall",
            "macro_f1": "baseline_macro_f1",
        }
    )


def load_irc_test(path: Path) -> pd.DataFrame:
    calibrated = pd.read_csv(path)
    out = calibrated[
        (calibrated["metric_scope"] == "target_calibrated")
        & (calibrated["source_id"] == "all")
        & (calibrated["split"] == "test")
    ].copy()
    return out[
        [
            "score_name",
            "horizon_months",
            "rows",
            "threshold",
            "pr_auc",
            "roc_auc",
            "brier",
            "recall",
            "macro_f1",
        ]
    ].rename(
        columns={
            "rows": "irc_rows",
            "threshold": "irc_threshold",
            "pr_auc": "irc_pr_auc",
            "roc_auc": "irc_roc_auc",
            "brier": "irc_brier",
            "recall": "irc_recall",
            "macro_f1": "irc_macro_f1",
        }
    )


def build_test_comparison(baseline_path: Path, calibrated_path: Path) -> pd.DataFrame:
    baseline = load_baseline_test(baseline_path)
    irc = load_irc_test(calibrated_path)
    comparison = irc.merge(baseline, on="horizon_months", how="left")
    comparison["delta_pr_auc_vs_baseline"] = comparison["irc_pr_auc"] - comparison["baseline_pr_auc"]
    comparison["delta_brier_vs_baseline"] = comparison["irc_brier"] - comparison["baseline_brier"]
    comparison["delta_macro_f1_vs_baseline"] = comparison["irc_macro_f1"] - comparison["baseline_macro_f1"]
    return comparison.sort_values(["score_name", "horizon_months"]).reset_index(drop=True)


def build_source_summary(raw_path: Path, calibrated_path: Path) -> pd.DataFrame:
    raw = pd.read_csv(raw_path)
    calibrated = pd.read_csv(calibrated_path)
    raw_test = raw[
        (raw["metric_scope"] == "target")
        & (raw["split"] == "test")
        & (raw["source_id"] != "all")
    ].copy()
    raw_test = raw_test[
        [
            "score_name",
            "source_id",
            "horizon_months",
            "rows",
            "pr_auc",
            "roc_auc",
            "brier",
            "recall",
            "macro_f1",
            "mae_score_risk_chla",
        ]
    ].rename(
        columns={
            "pr_auc": "raw_pr_auc",
            "roc_auc": "raw_roc_auc",
            "brier": "raw_brier",
            "recall": "raw_recall",
            "macro_f1": "raw_macro_f1",
            "mae_score_risk_chla": "raw_mae_risk",
        }
    )
    calibrated_test = calibrated[
        (calibrated["metric_scope"] == "target_calibrated")
        & (calibrated["split"] == "test")
        & (calibrated["source_id"] != "all")
    ].copy()
    calibrated_test = calibrated_test[
        ["score_name", "source_id", "horizon_months", "threshold", "brier", "macro_f1", "recall"]
    ].rename(
        columns={
            "threshold": "calibrated_threshold",
            "brier": "calibrated_brier",
            "macro_f1": "calibrated_macro_f1",
            "recall": "calibrated_recall",
        }
    )
    return raw_test.merge(calibrated_test, on=["score_name", "source_id", "horizon_months"], how="left").sort_values(
        ["score_name", "horizon_months", "source_id"]
    )


def write_report(comparison: pd.DataFrame, source_summary: pd.DataFrame, args: argparse.Namespace) -> None:
    lines = [
        "# Expert Fuzzy Review",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Calibrated Test Comparison Vs Selected Baselines",
        "",
        "| score | horizon | baseline | IRC PR-AUC | baseline PR-AUC | d PR-AUC | IRC Brier | baseline Brier | d Brier | IRC macro-F1 | baseline macro-F1 | d macro-F1 |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(comparison):
        lines.append(
            f"| `{row.score_name}` | {int(row.horizon_months)} | `{row.baseline_model}` | "
            f"{_format_float(row.irc_pr_auc)} | {_format_float(row.baseline_pr_auc)} | "
            f"{_format_float(row.delta_pr_auc_vs_baseline)} | {_format_float(row.irc_brier)} | "
            f"{_format_float(row.baseline_brier)} | {_format_float(row.delta_brier_vs_baseline)} | "
            f"{_format_float(row.irc_macro_f1)} | {_format_float(row.baseline_macro_f1)} | "
            f"{_format_float(row.delta_macro_f1_vs_baseline)} |"
        )

    lines.extend(
        [
            "",
            "## Source-Level Test Summary",
            "",
            "| score | source | horizon | rows | raw PR-AUC | raw Brier | calibrated Brier | raw macro-F1 | calibrated macro-F1 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(source_summary):
        lines.append(
            f"| `{row.score_name}` | `{row.source_id}` | {int(row.horizon_months)} | "
            f"{_format_int(int(row.rows))} | {_format_float(row.raw_pr_auc)} | {_format_float(row.raw_brier)} | "
            f"{_format_float(row.calibrated_brier)} | {_format_float(row.raw_macro_f1)} | "
            f"{_format_float(row.calibrated_macro_f1)} |"
        )

    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- Comparison CSV: `{args.comparison}`",
            f"- Source summary CSV: `{args.source_summary}`",
            f"- Review manifest: `{args.manifest}`",
        ]
    )
    _write_text_atomic("\n".join(lines) + "\n", args.report)


def build_manifest(
    comparison: pd.DataFrame,
    source_summary: pd.DataFrame,
    args: argparse.Namespace,
) -> dict[str, object]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "review": "expert_fuzzy_vs_calibrated_baselines",
        "row_counts": {
            "comparison_rows": int(len(comparison)),
            "source_summary_rows": int(len(source_summary)),
        },
        "inputs": [
            _file_record(args.baseline_metrics),
            _file_record(args.irc_metrics),
            _file_record(args.calibrated_metrics),
        ],
        "outputs": [
            _file_record(args.report),
            _file_record(args.comparison),
            _file_record(args.source_summary),
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-metrics", type=Path, default=DEFAULT_BASELINE_METRICS)
    parser.add_argument("--irc-metrics", type=Path, default=DEFAULT_IRC_METRICS)
    parser.add_argument("--calibrated-metrics", type=Path, default=DEFAULT_CALIBRATED_METRICS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--source-summary", type=Path, default=DEFAULT_SOURCE_SUMMARY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comparison = build_test_comparison(args.baseline_metrics, args.calibrated_metrics)
    source_summary = build_source_summary(args.irc_metrics, args.calibrated_metrics)
    _write_csv_atomic(comparison, args.comparison)
    _write_csv_atomic(source_summary, args.source_summary)
    write_report(comparison, source_summary, args)
    manifest = build_manifest(comparison, source_summary, args)
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.report}")
    print(f"wrote {args.comparison}")
    print(f"wrote {args.source_summary}")
    print(f"wrote {args.manifest}")


if __name__ == "__main__":
    main()
