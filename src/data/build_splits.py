#!/usr/bin/env python
"""Build chronological, leakage-safe splits for monthly target rows."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pandas_utils import dataframe_rows


DEFAULT_TARGET_MODEL = Path("data/targets/monthly_targets_model_v0.parquet")
DEFAULT_FREEZE_MANIFEST = Path("data/freeze/data_freeze_manifest_v0.json")
DEFAULT_DERIVED_MANIFEST = Path("data/freeze/derived_file_manifest_v0.csv")
DEFAULT_OUTPUT_DIR = Path("data/splits")
DEFAULT_SPLITS = DEFAULT_OUTPUT_DIR / "monthly_model_splits_v0.parquet"
DEFAULT_DISCARDED = DEFAULT_OUTPUT_DIR / "monthly_model_splits_discarded_v0.parquet"
DEFAULT_SUMMARY = DEFAULT_OUTPUT_DIR / "split_summary_by_source_horizon_v0.csv"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "SPLIT_REPORT.md"
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "split_manifest.json"


def _format_int(value: int) -> str:
    return f"{value:,}"


def _format_float(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
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


def _period(value: str) -> pd.Period:
    return cast(pd.Period, pd.Period(value, freq="M"))


def _assign_split(
    months: pd.Series,
    *,
    train_end: str,
    validation_start: str,
    validation_end: str,
    test_start: str,
    test_end: str | None,
) -> pd.Series:
    values = pd.PeriodIndex(months.astype(str), freq="M")
    out = pd.Series(pd.NA, index=months.index, dtype="string")
    train_mask = values <= _period(train_end)
    validation_mask = (values >= _period(validation_start)) & (values <= _period(validation_end))
    test_mask = values >= _period(test_start)
    if test_end is not None:
        test_mask = test_mask & (values <= _period(test_end))
    out.loc[train_mask] = "train"
    out.loc[validation_mask] = "validation"
    out.loc[test_mask] = "test"
    return out


def _load_freeze_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    return dict(zip(frame["path"], frame["sha256"], strict=False))


def build_splits(targets: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    targets = targets.copy()
    targets["origin_split"] = _assign_split(
        targets["origin_year_month"],
        train_end=args.train_end,
        validation_start=args.validation_start,
        validation_end=args.validation_end,
        test_start=args.test_start,
        test_end=args.test_end,
    )
    targets["target_split"] = _assign_split(
        targets["target_year_month"],
        train_end=args.train_end,
        validation_start=args.validation_start,
        validation_end=args.validation_end,
        test_start=args.test_start,
        test_end=args.test_end,
    )
    targets["split_reason"] = np.where(
        targets["origin_split"].isna() | targets["target_split"].isna(),
        "outside_split_bounds",
        np.where(targets["origin_split"] == targets["target_split"], "kept", "crosses_split_boundary"),
    )
    kept = targets[targets["split_reason"] == "kept"].copy()
    kept["split"] = kept["origin_split"].astype("string")
    discarded = targets[targets["split_reason"] != "kept"].copy()
    return kept.reset_index(drop=True), discarded.reset_index(drop=True)


def summarize_splits(kept: pd.DataFrame) -> pd.DataFrame:
    grouped = kept.groupby(["source_id", "horizon_months", "split"], dropna=False)
    out = grouped.agg(
        rows=("site_id", "size"),
        sites=("site_id", "nunique"),
        bloom_positive=("bloom_h", "sum"),
        origin_min=("origin_year_month", "min"),
        origin_max=("origin_year_month", "max"),
        target_min=("target_year_month", "min"),
        target_max=("target_year_month", "max"),
    ).reset_index()
    out["bloom_positive"] = out["bloom_positive"].fillna(0).astype("int64")
    out["bloom_negative"] = out["rows"] - out["bloom_positive"]
    out["bloom_rate"] = np.where(out["rows"] > 0, out["bloom_positive"] / out["rows"], np.nan)
    return out.sort_values(["source_id", "horizon_months", "split"]).reset_index(drop=True)


def summarize_overall(kept: pd.DataFrame) -> pd.DataFrame:
    grouped = kept.groupby(["split", "horizon_months"], dropna=False)
    out = grouped.agg(
        rows=("site_id", "size"),
        sites=("site_id", "nunique"),
        bloom_positive=("bloom_h", "sum"),
        origin_min=("origin_year_month", "min"),
        origin_max=("origin_year_month", "max"),
        target_min=("target_year_month", "min"),
        target_max=("target_year_month", "max"),
    ).reset_index()
    out["bloom_positive"] = out["bloom_positive"].fillna(0).astype("int64")
    out["bloom_negative"] = out["rows"] - out["bloom_positive"]
    out["bloom_rate"] = np.where(out["rows"] > 0, out["bloom_positive"] / out["rows"], np.nan)
    return out.sort_values(["split", "horizon_months"]).reset_index(drop=True)


def summarize_discarded(discarded: pd.DataFrame) -> pd.DataFrame:
    if discarded.empty:
        return pd.DataFrame(columns=["source_id", "horizon_months", "split_reason", "rows", "bloom_positive"])
    grouped = discarded.groupby(["source_id", "horizon_months", "split_reason"], dropna=False)
    out = grouped.agg(rows=("site_id", "size"), bloom_positive=("bloom_h", "sum")).reset_index()
    out["bloom_positive"] = out["bloom_positive"].fillna(0).astype("int64")
    return out.sort_values(["source_id", "horizon_months", "split_reason"]).reset_index(drop=True)


def write_report(
    args: argparse.Namespace,
    kept: pd.DataFrame,
    discarded: pd.DataFrame,
    summary: pd.DataFrame,
    overall: pd.DataFrame,
    discarded_summary: pd.DataFrame,
    freeze_hashes: dict[str, str],
) -> None:
    leakage_rows = int((kept["origin_split"] != kept["target_split"]).sum())
    lines = [
        "# Split Report v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Target model rows input: `{_format_int(len(kept) + len(discarded))}`",
        f"Rows kept: `{_format_int(len(kept))}`",
        f"Rows discarded: `{_format_int(len(discarded))}`",
        f"Leakage rows after filtering: `{_format_int(leakage_rows)}`",
        "",
        "## Freeze References",
        "",
        f"- Freeze manifest: `{args.freeze_manifest}`",
        f"- Target model table: `{args.target_model}`",
        f"- Target model SHA-256: `{freeze_hashes.get(args.target_model.as_posix(), 'unavailable')}`",
        f"- Panel with targets SHA-256: `{freeze_hashes.get('data/targets/panel_monthly_with_targets_v0.parquet', 'unavailable')}`",
        "",
        "## Temporal Boundaries",
        "",
        "| split | origin/target month rule |",
        "|---|---|",
        f"| train | `<= {args.train_end}` |",
        f"| validation | `{args.validation_start}` through `{args.validation_end}` |",
        f"| test | `>= {args.test_start}`{f' through `{args.test_end}`' if args.test_end else ''} |",
        "",
        "Rows are kept only when `origin_split == target_split`.",
        "",
        "## Overall By Split And Horizon",
        "",
        "| split | horizon | rows | sites | bloom positives | bloom negatives | bloom rate | origin range | target range |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in dataframe_rows(overall):
        lines.append(
            f"| `{row.split}` | {int(row.horizon_months)} | {_format_int(int(row.rows))} | "
            f"{_format_int(int(row.sites))} | {_format_int(int(row.bloom_positive))} | "
            f"{_format_int(int(row.bloom_negative))} | {_format_float(float(row.bloom_rate))} | "
            f"`{row.origin_min}..{row.origin_max}` | `{row.target_min}..{row.target_max}` |"
        )

    lines.extend(
        [
            "",
            "## By Source, Horizon, And Split",
            "",
            "| source_id | horizon | split | rows | sites | bloom positives | bloom rate | origin range | target range |",
            "|---|---:|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in dataframe_rows(summary):
        lines.append(
            f"| `{row.source_id}` | {int(row.horizon_months)} | `{row.split}` | {_format_int(int(row.rows))} | "
            f"{_format_int(int(row.sites))} | {_format_int(int(row.bloom_positive))} | "
            f"{_format_float(float(row.bloom_rate))} | `{row.origin_min}..{row.origin_max}` | "
            f"`{row.target_min}..{row.target_max}` |"
        )

    lines.extend(
        [
            "",
            "## Discarded Rows",
            "",
            "| source_id | horizon | reason | rows | bloom positives |",
            "|---|---:|---|---:|---:|",
        ]
    )
    if discarded_summary.empty:
        lines.append("| `NA` | 0 | `none` | 0 | 0 |")
    else:
        for row in dataframe_rows(discarded_summary):
            lines.append(
                f"| `{row.source_id}` | {int(row.horizon_months)} | `{row.split_reason}` | "
                f"{_format_int(int(row.rows))} | {_format_int(int(row.bloom_positive))} |"
            )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Kept split rows: `{args.splits}`",
            f"- Discarded rows: `{args.discarded}`",
            f"- Summary CSV: `{args.summary}`",
            f"- Manifest: `{args.manifest}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(
    args: argparse.Namespace,
    kept: pd.DataFrame,
    discarded: pd.DataFrame,
    summary: pd.DataFrame,
    overall: pd.DataFrame,
    discarded_summary: pd.DataFrame,
    freeze_hashes: dict[str, str],
    started_at: datetime,
) -> dict[str, Any]:
    leakage_rows = int((kept["origin_split"] != kept["target_split"]).sum())
    return {
        "status": "completed",
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_manifest": args.freeze_manifest.as_posix(),
        "target_model": args.target_model.as_posix(),
        "target_model_sha256": freeze_hashes.get(args.target_model.as_posix()),
        "panel_with_targets_sha256": freeze_hashes.get("data/targets/panel_monthly_with_targets_v0.parquet"),
        "boundaries": {
            "train_end": args.train_end,
            "validation_start": args.validation_start,
            "validation_end": args.validation_end,
            "test_start": args.test_start,
            "test_end": args.test_end,
        },
        "input_rows": int(len(kept) + len(discarded)),
        "kept_rows": int(len(kept)),
        "discarded_rows": int(len(discarded)),
        "leakage_rows_after_filter": leakage_rows,
        "splits": args.splits.as_posix(),
        "discarded": args.discarded.as_posix(),
        "summary": args.summary.as_posix(),
        "report": args.report.as_posix(),
        "overall": overall.to_dict(orient="records"),
        "by_source_horizon_split": summary.to_dict(orient="records"),
        "discarded_summary": discarded_summary.to_dict(orient="records"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build chronological splits without origin-target leakage.")
    parser.add_argument("--target-model", type=Path, default=DEFAULT_TARGET_MODEL)
    parser.add_argument("--freeze-manifest", type=Path, default=DEFAULT_FREEZE_MANIFEST)
    parser.add_argument("--derived-manifest", type=Path, default=DEFAULT_DERIVED_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--discarded", type=Path, default=DEFAULT_DISCARDED)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--train-end", default="2018-12")
    parser.add_argument("--validation-start", default="2019-01")
    parser.add_argument("--validation-end", default="2021-12")
    parser.add_argument("--test-start", default="2022-01")
    parser.add_argument("--test-end", default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = [args.splits, args.discarded, args.summary, args.report, args.manifest]
    existing = [path for path in outputs if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"Output exists: {existing}. Use --overwrite to replace split outputs.")

    started_at = datetime.now(timezone.utc)
    targets = pd.read_parquet(args.target_model)
    print(f"loaded target model rows: {len(targets):,}", flush=True)
    kept, discarded = build_splits(targets, args)
    print(f"kept rows: {len(kept):,}; discarded rows: {len(discarded):,}", flush=True)

    summary = summarize_splits(kept)
    overall = summarize_overall(kept)
    discarded_summary = summarize_discarded(discarded)
    freeze_hashes = _load_freeze_hashes(args.derived_manifest)

    _write_parquet_atomic(kept, args.splits)
    _write_parquet_atomic(discarded, args.discarded)
    _write_csv_atomic(summary, args.summary)
    write_report(args, kept, discarded, summary, overall, discarded_summary, freeze_hashes)
    payload = manifest_payload(args, kept, discarded, summary, overall, discarded_summary, freeze_hashes, started_at)
    _write_json_atomic(payload, args.manifest)
    print(f"splits written: {args.splits}", flush=True)
    print(f"split report written: {args.report}", flush=True)
    print(f"split manifest written: {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
