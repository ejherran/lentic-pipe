#!/usr/bin/env python
"""Build monthly panels from canonical observations.

The script has two phases:
1. Aggregate each observation parquet part into a smaller monthly partial.
2. Combine partials into a long monthly panel and a wide ML-ready panel.

Partials make the job resumable: interrupted runs keep completed partials and
continue from the next observation part when launched with --resume.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_OBSERVATIONS_DIR = Path("data/interim/observations")
DEFAULT_PANEL_DIR = Path("data/panel")
DEFAULT_PARTIAL_DIR = Path("data/panel/_monthly_partials")
DEFAULT_LONG = Path("data/panel/monthly_long_v0.parquet")
DEFAULT_WIDE = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_REPORT = Path("reports/data/PANEL_REPORT_v0.md")
DEFAULT_MANIFEST = Path("data/panel/monthly_panel_manifest_v0.json")

GROUP_COLUMNS = ["source_id", "site_id", "site_id_source", "year_month", "variable_canonical"]
OUTPUT_COLUMNS = ["source_id", "site_id", "site_id_source", "site_name", "year_month", "variable_canonical"]
READ_COLUMNS = OUTPUT_COLUMNS + ["value_canonical", "qc_flag"]


def _format_int(value: int) -> str:
    return f"{value:,}"


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


def _stop_requested(stop_file: Path) -> bool:
    return stop_file.exists()


def iter_observation_parts(observations_dir: Path, sources: list[str] | None) -> list[Path]:
    source_dirs = [observations_dir / source for source in sources] if sources else sorted(
        path for path in observations_dir.iterdir() if path.is_dir()
    )
    parts: list[Path] = []
    for source_dir in source_dirs:
        parts.extend(sorted(source_dir.glob("part-*.parquet")))
    return parts


def partial_path_for(part_path: Path, observations_dir: Path, partial_dir: Path) -> Path:
    source_id = part_path.parent.name
    return partial_dir / source_id / f"{part_path.stem}.monthly.parquet"


def partial_meta_path_for(partial_path: Path) -> Path:
    return partial_path.with_name(f"{partial_path.stem}.meta.json")


def aggregate_part(part_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_parquet(part_path, columns=READ_COLUMNS)
    input_rows = int(len(frame))
    missing_year_month = int(frame["year_month"].isna().sum())
    missing_variable = int(frame["variable_canonical"].isna().sum())
    panelable_mask = frame["year_month"].notna() & frame["variable_canonical"].notna()
    panelable_rows = int(panelable_mask.sum())
    summary = {
        "input_rows": input_rows,
        "panelable_rows": panelable_rows,
        "excluded_rows": input_rows - panelable_rows,
        "excluded_missing_year_month": missing_year_month,
        "excluded_missing_variable": missing_variable,
    }
    frame = frame[panelable_mask].copy()
    if frame.empty:
        summary.update({"monthly_groups": 0, "n_obs_total": 0, "n_obs_ok": 0, "n_obs_bad": 0})
        return pd.DataFrame(columns=OUTPUT_COLUMNS), summary

    grouped_frame = frame.groupby(GROUP_COLUMNS, dropna=False)
    total = grouped_frame.size().rename("n_obs_total")
    site_names = grouped_frame["site_name"].first()
    site_names.name = "site_name"

    ok = frame[(frame["qc_flag"] == "ok") & frame["value_canonical"].notna()].copy()
    if ok.empty:
        out = total.to_frame().join(site_names, how="left").reset_index()
        out["n_obs_ok"] = 0
        out["value_sum"] = 0.0
        out["value_sumsq"] = 0.0
        out["value_min"] = np.nan
        out["value_max"] = np.nan
    else:
        ok["value_canonical"] = pd.to_numeric(ok["value_canonical"], errors="coerce")
        ok = ok[ok["value_canonical"].notna()]
        ok["value_sumsq_component"] = ok["value_canonical"] * ok["value_canonical"]
        value_agg = ok.groupby(GROUP_COLUMNS, dropna=False).agg(
            n_obs_ok=("value_canonical", "count"),
            value_sum=("value_canonical", "sum"),
            value_sumsq=("value_sumsq_component", "sum"),
            value_min=("value_canonical", "min"),
            value_max=("value_canonical", "max"),
        )
        out = total.to_frame().join(site_names, how="left").join(value_agg, how="left").reset_index()
        out["n_obs_ok"] = out["n_obs_ok"].fillna(0).astype("int64")
        out["value_sum"] = out["value_sum"].fillna(0.0)
        out["value_sumsq"] = out["value_sumsq"].fillna(0.0)
    out["n_obs_bad"] = out["n_obs_total"] - out["n_obs_ok"]
    out = out[
        OUTPUT_COLUMNS
        + ["n_obs_total", "n_obs_ok", "value_sum", "value_sumsq", "value_min", "value_max", "n_obs_bad"]
    ]
    summary.update(
        {
            "monthly_groups": int(len(out)),
            "n_obs_total": int(out["n_obs_total"].sum()),
            "n_obs_ok": int(out["n_obs_ok"].sum()),
            "n_obs_bad": int(out["n_obs_bad"].sum()),
        }
    )
    return out, summary


def build_partials(args: argparse.Namespace) -> tuple[list[Path], list[dict[str, Any]]]:
    if args.overwrite and args.partial_dir.exists():
        shutil.rmtree(args.partial_dir)
    args.partial_dir.mkdir(parents=True, exist_ok=True)

    parts = iter_observation_parts(args.observations_dir, args.source)
    if args.max_parts is not None:
        parts = parts[: args.max_parts]
    partial_paths: list[Path] = []
    partial_summaries: list[dict[str, Any]] = []
    started = datetime.now(timezone.utc)
    for index, part_path in enumerate(parts, start=1):
        if _stop_requested(args.stop_file):
            print(f"stop requested before part {index}/{len(parts)}; leaving completed partials intact")
            break
        output_path = partial_path_for(part_path, args.observations_dir, args.partial_dir)
        meta_path = partial_meta_path_for(output_path)
        if args.resume and output_path.exists() and meta_path.exists():
            partial_paths.append(output_path)
            with meta_path.open("r", encoding="utf-8") as handle:
                partial_summaries.append(json.load(handle))
            if index == 1 or index % args.progress_every_parts == 0 or index == len(parts):
                print(f"partial {index}/{len(parts)} exists; skipped {part_path}", flush=True)
            continue

        partial, summary = aggregate_part(part_path)
        summary.update(
            {
                "source_id": part_path.parent.name,
                "observation_part": part_path.as_posix(),
                "partial_path": output_path.as_posix(),
            }
        )
        _write_parquet_atomic(partial, output_path)
        _write_json_atomic(summary, meta_path)
        partial_paths.append(output_path)
        partial_summaries.append(summary)
        if index == 1 or index % args.progress_every_parts == 0 or index == len(parts):
            elapsed = datetime.now(timezone.utc) - started
            print(
                f"partial {index}/{len(parts)} wrote {output_path} "
                f"({len(partial):,} monthly groups; excluded={summary['excluded_rows']:,}); "
                f"elapsed={elapsed}",
                flush=True,
            )
    return partial_paths, partial_summaries


def combine_partials(partial_paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_parquet(path) for path in partial_paths]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    partials = pd.concat(frames, ignore_index=True)
    grouped_partials = partials.groupby(GROUP_COLUMNS, dropna=False)
    site_names = grouped_partials["site_name"].first()
    site_names.name = "site_name"
    grouped = grouped_partials.agg(
        n_obs_total=("n_obs_total", "sum"),
        n_obs_ok=("n_obs_ok", "sum"),
        n_obs_bad=("n_obs_bad", "sum"),
        value_sum=("value_sum", "sum"),
        value_sumsq=("value_sumsq", "sum"),
        value_min=("value_min", "min"),
        value_max=("value_max", "max"),
    )
    out = grouped.join(site_names, how="left").reset_index()
    out["value_mean"] = np.where(out["n_obs_ok"] > 0, out["value_sum"] / out["n_obs_ok"], np.nan)
    numerator = out["value_sumsq"] - (out["value_sum"] * out["value_sum"] / out["n_obs_ok"].replace(0, np.nan))
    out["value_std"] = np.where(out["n_obs_ok"] > 1, np.sqrt(np.maximum(numerator, 0) / (out["n_obs_ok"] - 1)), np.nan)
    out["qc_ok_rate"] = np.where(out["n_obs_total"] > 0, out["n_obs_ok"] / out["n_obs_total"], np.nan)
    return out[
        OUTPUT_COLUMNS
        + [
            "n_obs_total",
            "n_obs_ok",
            "n_obs_bad",
            "qc_ok_rate",
            "value_mean",
            "value_std",
            "value_min",
            "value_max",
        ]
    ]


def build_wide_panel(long_panel: pd.DataFrame) -> pd.DataFrame:
    index_cols = ["source_id", "site_id", "site_id_source", "year_month"]
    site_names = long_panel.groupby(index_cols, dropna=False)["site_name"].first()
    site_names.name = "site_name"
    site_names = site_names.reset_index()
    metric_map = {
        "value_mean": "mean",
        "value_std": "std",
        "value_min": "min",
        "value_max": "max",
        "n_obs_ok": "n_obs",
        "n_obs_bad": "n_bad",
        "qc_ok_rate": "qc_ok_rate",
    }
    wide_parts = []
    for metric, prefix in metric_map.items():
        pivot = long_panel.pivot_table(
            index=index_cols,
            columns="variable_canonical",
            values=metric,
            aggfunc="first",
        )
        pivot.columns = [f"{prefix}_{column}" for column in pivot.columns]
        wide_parts.append(pivot)
    wide = pd.concat(wide_parts, axis=1).reset_index()
    wide = wide.merge(site_names, on=index_cols, how="left")
    front_cols = ["source_id", "site_id", "site_id_source", "site_name", "year_month"]
    wide = wide[front_cols + [column for column in wide.columns if column not in front_cols]]
    wide["year_month"] = pd.to_datetime(wide["year_month"], format="%Y-%m", errors="coerce")
    wide["month"] = wide["year_month"].dt.month
    day_of_year = wide["year_month"].dt.dayofyear.fillna(1)
    wide["season_sin_1"] = np.sin(2 * math.pi * day_of_year / 365.25)
    wide["season_cos_1"] = np.cos(2 * math.pi * day_of_year / 365.25)
    wide["season_sin_2"] = np.sin(4 * math.pi * day_of_year / 365.25)
    wide["season_cos_2"] = np.cos(4 * math.pi * day_of_year / 365.25)
    wide["year_month"] = wide["year_month"].dt.strftime("%Y-%m")

    if {"mean_TN_ugL", "mean_TP_ugL"}.issubset(wide.columns):
        wide["TN_TP_ratio"] = wide["mean_TN_ugL"] / wide["mean_TP_ugL"]
    if "mean_TP_ugL" in wide.columns:
        wide["log_TP"] = np.log(wide["mean_TP_ugL"] + 0.1)
    if "mean_TN_ugL" in wide.columns:
        wide["log_TN"] = np.log(wide["mean_TN_ugL"] + 0.1)
    if "mean_chlorophyll_a_ugL" in wide.columns:
        wide["log_chlorophyll_a"] = np.log(wide["mean_chlorophyll_a_ugL"] + 0.1)
        denominator = np.log(30 + 0.1) - np.log(5 + 0.1)
        wide["risk_chla"] = np.clip(
            (np.log(wide["mean_chlorophyll_a_ugL"] + 0.1) - np.log(5 + 0.1)) / denominator,
            0,
            1,
        )
    return wide


def summarize_partial_coverage(partial_summaries: list[dict[str, Any]]) -> pd.DataFrame:
    if not partial_summaries:
        return pd.DataFrame(
            columns=[
                "input_rows",
                "panelable_rows",
                "excluded_rows",
                "excluded_missing_year_month",
                "excluded_missing_variable",
            ]
        )
    summary = pd.DataFrame(partial_summaries)
    return summary.groupby("source_id").agg(
        input_rows=("input_rows", "sum"),
        panelable_rows=("panelable_rows", "sum"),
        excluded_rows=("excluded_rows", "sum"),
        excluded_missing_year_month=("excluded_missing_year_month", "sum"),
        excluded_missing_variable=("excluded_missing_variable", "sum"),
    )


def write_report(
    long_panel: pd.DataFrame,
    wide_panel: pd.DataFrame,
    partial_summaries: list[dict[str, Any]],
    args: argparse.Namespace,
) -> None:
    args.report.parent.mkdir(parents=True, exist_ok=True)
    coverage = summarize_partial_coverage(partial_summaries)
    by_source = long_panel.groupby("source_id").agg(
        monthly_variable_rows=("variable_canonical", "count"),
        source_site_months=("site_id", "nunique"),
        n_obs_ok=("n_obs_ok", "sum"),
        n_obs_bad=("n_obs_bad", "sum"),
    )
    variable_counts = long_panel.groupby("variable_canonical")["n_obs_ok"].sum().sort_index()
    lines = [
        "# Monthly Panel Report v0",
        "",
        f"Long panel rows: `{_format_int(len(long_panel))}`",
        f"Wide panel rows: `{_format_int(len(wide_panel))}`",
        "",
        "## By Source",
        "",
        "| source_id | monthly variable rows | unique sites | panelable observations | ok observations | bad observations |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for source_id, row in by_source.iterrows():
        lines.append(
            f"| `{source_id}` | {_format_int(int(row['monthly_variable_rows']))} | "
            f"{_format_int(int(row['source_site_months']))} | "
            f"{_format_int(int(row['n_obs_ok'] + row['n_obs_bad']))} | {_format_int(int(row['n_obs_ok']))} | "
            f"{_format_int(int(row['n_obs_bad']))} |"
        )
    lines.extend(
        [
            "",
            "## Input Coverage",
            "",
            "| source_id | canonical observations | panelable observations | excluded rows | excluded missing month | excluded missing variable |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for source_id, row in coverage.iterrows():
        lines.append(
            f"| `{source_id}` | {_format_int(int(row['input_rows']))} | "
            f"{_format_int(int(row['panelable_rows']))} | {_format_int(int(row['excluded_rows']))} | "
            f"{_format_int(int(row['excluded_missing_year_month']))} | "
            f"{_format_int(int(row['excluded_missing_variable']))} |"
        )
    lines.extend(["", "## OK Observations By Variable", "", "| variable | ok observations |", "|---|---:|"])
    for variable, count in variable_counts.items():
        lines.append(f"| `{variable}` | {_format_int(int(count))} |")
    lines.extend(
        [
            "",
            "## Aggregation Policy",
            "",
            "- Monthly values use `qc_flag == ok` and non-null `value_canonical`.",
            "- Bad or unsupported observations are retained only as counts (`n_obs_bad`, `qc_ok_rate`).",
            "- Observations without `year_month` are excluded from monthly aggregation and counted in Input Coverage.",
            "- `value_mean`, `value_std`, `value_min`, and `value_max` are exact over OK observations.",
            "- Exact monthly medians are intentionally not computed in v0 because high-frequency sources contain hundreds of millions of observations.",
            "",
        ]
    )
    args.report.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build monthly long and wide panels from canonical observations.")
    parser.add_argument("--observations-dir", type=Path, default=DEFAULT_OBSERVATIONS_DIR)
    parser.add_argument("--panel-dir", type=Path, default=DEFAULT_PANEL_DIR)
    parser.add_argument("--partial-dir", type=Path, default=DEFAULT_PARTIAL_DIR)
    parser.add_argument("--long", type=Path, default=DEFAULT_LONG)
    parser.add_argument("--wide", type=Path, default=DEFAULT_WIDE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source", action="append", help="Source id to include. Defaults to all sources.")
    parser.add_argument("--max-parts", type=int, default=None, help="Limit observation parts for smoke tests.")
    parser.add_argument("--progress-every-parts", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--stop-file", type=Path, default=Path("data/panel/STOP_REQUESTED"))
    parser.add_argument("--partials-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.overwrite and args.resume:
        raise SystemExit("--overwrite and --resume are mutually exclusive")
    started = datetime.now(timezone.utc)
    partial_paths, partial_summaries = build_partials(args)
    if args.partials_only:
        print(f"partials complete: {len(partial_paths)} files")
        return
    if _stop_requested(args.stop_file):
        raise SystemExit(f"stop requested by {args.stop_file}; combine phase skipped")
    print(f"combining {len(partial_paths)} monthly partials", flush=True)
    long_panel = combine_partials(partial_paths)
    wide_panel = build_wide_panel(long_panel)
    _write_parquet_atomic(long_panel, args.long)
    _write_parquet_atomic(wide_panel, args.wide)
    write_report(long_panel, wide_panel, partial_summaries, args)
    coverage = summarize_partial_coverage(partial_summaries)
    coverage_payload = {
        str(source_id): {key: int(value) for key, value in row.items()}
        for source_id, row in coverage.to_dict(orient="index").items()
    }
    manifest = {
        "status": "completed",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "observation_parts": len(partial_paths),
        "input_rows": int(sum(summary["input_rows"] for summary in partial_summaries)),
        "panelable_rows": int(sum(summary["panelable_rows"] for summary in partial_summaries)),
        "excluded_rows": int(sum(summary["excluded_rows"] for summary in partial_summaries)),
        "coverage_by_source": coverage_payload,
        "long_panel": args.long.as_posix(),
        "wide_panel": args.wide.as_posix(),
        "long_rows": int(len(long_panel)),
        "wide_rows": int(len(wide_panel)),
    }
    _write_json_atomic(manifest, args.manifest)
    print(f"monthly long panel written: {args.long} ({len(long_panel):,} rows)")
    print(f"monthly wide panel written: {args.wide} ({len(wide_panel):,} rows)")
    print(f"monthly panel report written: {args.report}")


if __name__ == "__main__":
    main()
