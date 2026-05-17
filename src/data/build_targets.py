#!/usr/bin/env python
"""Build monthly target tables from the monthly panel.

Targets are source-scoped: a target for a WQP site is searched only inside WQP,
and the same applies to LakeBeD and AquaMatch. Cross-source site resolution is a
separate later step.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows


DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_TARGET_DIR = Path("data/targets")
DEFAULT_LONG = DEFAULT_TARGET_DIR / "monthly_targets_long_v0.parquet"
DEFAULT_MODEL_LONG = DEFAULT_TARGET_DIR / "monthly_targets_model_v0.parquet"
DEFAULT_PANEL_WITH_TARGETS = DEFAULT_TARGET_DIR / "panel_monthly_with_targets_v0.parquet"
DEFAULT_REPORT = Path("reports/data/TARGET_REPORT_v0.md")
DEFAULT_MANIFEST = DEFAULT_TARGET_DIR / "target_manifest_v0.json"

KEY_COLUMNS = ["source_id", "site_id", "site_id_source", "site_name", "year_month"]
JOIN_COLUMNS = ["source_id", "site_id", "year_month"]
TARGET_VALUE_COLUMNS = [
    "mean_chlorophyll_a_ugL",
    "n_obs_chlorophyll_a_ugL",
    "qc_ok_rate_chlorophyll_a_ugL",
]

RISK_EPSILON = 0.1
RISK_LOW_CHLA = 5.0
BLOOM_THRESHOLD_CHLA = 30.0
TROPHIC_THRESHOLDS = {
    "oligotrophic_max": 2.6,
    "mesotrophic_max": 7.3,
    "eutrophic_max": 56.0,
}


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


def _risk_from_chla(chla: pd.Series) -> pd.Series:
    denominator = np.log(BLOOM_THRESHOLD_CHLA + RISK_EPSILON) - np.log(RISK_LOW_CHLA + RISK_EPSILON)
    risk = (np.log(chla + RISK_EPSILON) - np.log(RISK_LOW_CHLA + RISK_EPSILON)) / denominator
    return risk.clip(lower=0, upper=1)


def _trophic_state_from_chla(chla: pd.Series) -> pd.Series:
    states = pd.Series(pd.NA, index=chla.index, dtype="string")
    present = chla.notna()
    states.loc[present & (chla < TROPHIC_THRESHOLDS["oligotrophic_max"])] = "oligotrophic"
    states.loc[present & (chla >= TROPHIC_THRESHOLDS["oligotrophic_max"]) & (chla < TROPHIC_THRESHOLDS["mesotrophic_max"])] = (
        "mesotrophic"
    )
    states.loc[present & (chla >= TROPHIC_THRESHOLDS["mesotrophic_max"]) & (chla < TROPHIC_THRESHOLDS["eutrophic_max"])] = (
        "eutrophic"
    )
    states.loc[present & (chla >= TROPHIC_THRESHOLDS["eutrophic_max"])] = "hypereutrophic"
    return states


def _add_months(year_month: pd.Series, months: int) -> pd.Series:
    return (pd.PeriodIndex(year_month.astype(str), freq="M") + months).astype(str)


def _validate_panel_columns(panel: pd.DataFrame) -> None:
    required = set(KEY_COLUMNS + TARGET_VALUE_COLUMNS)
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"Panel is missing required columns: {missing}")


def build_target_long(panel: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    _validate_panel_columns(panel)
    origin = panel[KEY_COLUMNS].copy()
    target_lookup = panel[["source_id", "site_id", "year_month"] + TARGET_VALUE_COLUMNS].copy()
    target_lookup["_target_month_present"] = True
    target_lookup = target_lookup.rename(
        columns={
            "year_month": "target_year_month",
            "mean_chlorophyll_a_ugL": "future_chlorophyll_a_ugL",
            "n_obs_chlorophyll_a_ugL": "future_chlorophyll_a_n_obs",
            "qc_ok_rate_chlorophyll_a_ugL": "future_chlorophyll_a_qc_ok_rate",
        }
    )

    frames: list[pd.DataFrame] = []
    for horizon in horizons:
        candidates = origin.copy()
        candidates = candidates.rename(columns={"year_month": "origin_year_month"})
        candidates["horizon_months"] = int(horizon)
        candidates["target_year_month"] = _add_months(candidates["origin_year_month"], horizon)
        merged = candidates.merge(
            target_lookup,
            on=["source_id", "site_id", "target_year_month"],
            how="left",
        )
        merged["target_month_exists"] = merged["_target_month_present"].fillna(False).astype(bool)
        merged = merged.drop(columns=["_target_month_present"])
        merged["has_target"] = merged["future_chlorophyll_a_ugL"].notna()
        bloom = pd.Series(pd.NA, index=merged.index, dtype="boolean")
        has_target = merged["has_target"].astype(bool)
        bloom.loc[has_target] = merged.loc[has_target, "future_chlorophyll_a_ugL"] > BLOOM_THRESHOLD_CHLA
        merged["bloom_h"] = bloom
        merged["target_risk_chla_h"] = _risk_from_chla(merged["future_chlorophyll_a_ugL"])
        merged["target_trophic_state_h"] = _trophic_state_from_chla(merged["future_chlorophyll_a_ugL"])
        frames.append(merged)

    long = pd.concat(frames, ignore_index=True)
    return long[
        [
            "source_id",
            "site_id",
            "site_id_source",
            "site_name",
            "origin_year_month",
            "horizon_months",
            "target_year_month",
            "target_month_exists",
            "has_target",
            "future_chlorophyll_a_ugL",
            "future_chlorophyll_a_n_obs",
            "future_chlorophyll_a_qc_ok_rate",
            "bloom_h",
            "target_risk_chla_h",
            "target_trophic_state_h",
        ]
    ]


def build_model_long(target_long: pd.DataFrame) -> pd.DataFrame:
    return target_long[target_long["has_target"]].reset_index(drop=True)


def attach_targets_to_panel(panel: pd.DataFrame, target_long: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    out = panel.copy()
    base_cols = [
        "source_id",
        "site_id",
        "origin_year_month",
        "target_year_month",
        "target_month_exists",
        "has_target",
        "future_chlorophyll_a_ugL",
        "future_chlorophyll_a_n_obs",
        "future_chlorophyll_a_qc_ok_rate",
        "bloom_h",
        "target_risk_chla_h",
        "target_trophic_state_h",
    ]
    for horizon in horizons:
        subset = target_long[target_long["horizon_months"] == horizon][base_cols].copy()
        subset = subset.rename(columns={"origin_year_month": "year_month"})
        rename_map = {
            column: f"{column}_h{horizon}"
            for column in subset.columns
            if column not in JOIN_COLUMNS
        }
        subset = subset.rename(columns=rename_map)
        out = out.merge(subset, on=JOIN_COLUMNS, how="left")
    return out


def summarize_by_horizon(target_long: pd.DataFrame) -> pd.DataFrame:
    grouped = target_long.groupby("horizon_months", dropna=False)
    summary = grouped.agg(
        candidate_rows=("has_target", "size"),
        target_month_rows=("target_month_exists", "sum"),
        target_rows=("has_target", "sum"),
    )
    positives = target_long[target_long["has_target"]].groupby("horizon_months")["bloom_h"].sum()
    summary["bloom_positive"] = positives
    summary["bloom_positive"] = summary["bloom_positive"].fillna(0).astype("int64")
    summary["bloom_negative"] = summary["target_rows"] - summary["bloom_positive"]
    summary["missing_target_month"] = summary["candidate_rows"] - summary["target_month_rows"]
    summary["missing_chla_in_target_month"] = summary["target_month_rows"] - summary["target_rows"]
    summary["bloom_rate"] = np.where(
        summary["target_rows"] > 0,
        summary["bloom_positive"] / summary["target_rows"],
        np.nan,
    )
    return summary.reset_index()


def summarize_by_source_horizon(target_long: pd.DataFrame) -> pd.DataFrame:
    grouped = target_long.groupby(["source_id", "horizon_months"], dropna=False)
    summary = grouped.agg(
        candidate_rows=("has_target", "size"),
        target_month_rows=("target_month_exists", "sum"),
        target_rows=("has_target", "sum"),
    )
    positives = target_long[target_long["has_target"]].groupby(["source_id", "horizon_months"])["bloom_h"].sum()
    summary["bloom_positive"] = positives
    summary["bloom_positive"] = summary["bloom_positive"].fillna(0).astype("int64")
    summary["bloom_negative"] = summary["target_rows"] - summary["bloom_positive"]
    summary["missing_target_month"] = summary["candidate_rows"] - summary["target_month_rows"]
    summary["missing_chla_in_target_month"] = summary["target_month_rows"] - summary["target_rows"]
    summary["bloom_rate"] = np.where(
        summary["target_rows"] > 0,
        summary["bloom_positive"] / summary["target_rows"],
        np.nan,
    )
    return summary.reset_index()


def _write_report(
    target_long: pd.DataFrame,
    model_long: pd.DataFrame,
    panel_with_targets: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    args.report.parent.mkdir(parents=True, exist_ok=True)
    by_horizon = summarize_by_horizon(target_long)
    by_source_horizon = summarize_by_source_horizon(target_long)
    site_counts = model_long.groupby(["source_id", "horizon_months"])["site_id"].nunique().reset_index()
    site_counts.columns = ["source_id", "horizon_months", "sites_with_target"]
    chla_stats = model_long.groupby("horizon_months")["future_chlorophyll_a_ugL"].agg(
        count="count",
        mean="mean",
        median="median",
        p95=lambda series: series.quantile(0.95),
        max="max",
    )

    lines = [
        "# Target Report v0",
        "",
        f"Panel input rows: `{_format_int(len(panel_with_targets))}`",
        f"Target candidate rows: `{_format_int(len(target_long))}`",
        f"Rows with available Chl-a target: `{_format_int(len(model_long))}`",
        "",
        "## By Horizon",
        "",
        "| horizon_months | candidate rows | target month rows | target rows | missing target month | missing Chl-a in target month | bloom positives | bloom negatives | bloom rate |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(by_horizon):
        lines.append(
            f"| {int(row.horizon_months)} | {_format_int(int(row.candidate_rows))} | "
            f"{_format_int(int(row.target_month_rows))} | {_format_int(int(row.target_rows))} | "
            f"{_format_int(int(row.missing_target_month))} | {_format_int(int(row.missing_chla_in_target_month))} | "
            f"{_format_int(int(row.bloom_positive))} | {_format_int(int(row.bloom_negative))} | "
            f"{_format_float(float(row.bloom_rate))} |"
        )

    lines.extend(
        [
            "",
            "## By Source And Horizon",
            "",
            "| source_id | horizon_months | target rows | sites with target | bloom positives | bloom rate | missing target month | missing Chl-a in target month |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    source_site_lookup = {
        (row.source_id, int(row.horizon_months)): int(row.sites_with_target)
        for row in dataframe_rows(site_counts)
    }
    for row in dataframe_rows(by_source_horizon):
        sites = source_site_lookup.get((row.source_id, int(row.horizon_months)), 0)
        lines.append(
            f"| `{row.source_id}` | {int(row.horizon_months)} | {_format_int(int(row.target_rows))} | "
            f"{_format_int(sites)} | {_format_int(int(row.bloom_positive))} | "
            f"{_format_float(float(row.bloom_rate))} | {_format_int(int(row.missing_target_month))} | "
            f"{_format_int(int(row.missing_chla_in_target_month))} |"
        )

    lines.extend(
        [
            "",
            "## Future Chl-a Distribution",
            "",
            "| horizon_months | count | mean | median | p95 | max |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for horizon, row in chla_stats.iterrows():
        lines.append(
            f"| {int(horizon)} | {_format_int(int(row['count']))} | {_format_float(float(row['mean']))} | "
            f"{_format_float(float(row['median']))} | {_format_float(float(row['p95']))} | "
            f"{_format_float(float(row['max']))} |"
        )

    lines.extend(
        [
            "",
            "## Target Policy",
            "",
            f"- Horizons are exact calendar-month offsets: `{', '.join(str(item) for item in args.horizons)}`.",
            "- Targets are source-scoped by `source_id` and `site_id`; no cross-source site merge is assumed.",
            f"- `bloom_h = 1` when future monthly mean Chl-a is greater than `{BLOOM_THRESHOLD_CHLA:g} ug/L`.",
            "- Continuous risk uses the project log normalization with epsilon `0.1`, low reference `5 ug/L`, and bloom reference `30 ug/L`.",
            "- `target_trophic_state_h` is a crisp Chl-a proxy in v0: oligotrophic `<2.6`, mesotrophic `<7.3`, eutrophic `<56`, hypereutrophic `>=56` ug/L.",
            "- The final fuzzy trophic state remains a later ANFIS/Mamdani output; this v0 target is only a supervised proxy.",
            "",
            "## Outputs",
            "",
            f"- `{args.long}`: all origin-month by horizon candidates, including missing targets.",
            f"- `{args.model_long}`: only rows with available future Chl-a target.",
            f"- `{args.panel_with_targets}`: monthly panel with h1/h2/h3 target columns attached.",
            f"- `{args.manifest}`: machine-readable target build manifest.",
            "",
        ]
    )
    args.report.write_text("\n".join(lines), encoding="utf-8")


def _manifest_payload(
    target_long: pd.DataFrame,
    model_long: pd.DataFrame,
    panel_with_targets: pd.DataFrame,
    args: argparse.Namespace,
    started_at: datetime,
) -> dict[str, Any]:
    by_horizon = summarize_by_horizon(target_long)
    by_source_horizon = summarize_by_source_horizon(target_long)
    return {
        "status": "completed",
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "panel": args.panel.as_posix(),
        "horizons_months": [int(item) for item in args.horizons],
        "long_targets": args.long.as_posix(),
        "model_long_targets": args.model_long.as_posix(),
        "panel_with_targets": args.panel_with_targets.as_posix(),
        "report": args.report.as_posix(),
        "panel_rows": int(len(panel_with_targets)),
        "target_candidate_rows": int(len(target_long)),
        "model_target_rows": int(len(model_long)),
        "bloom_threshold_chla_ugL": BLOOM_THRESHOLD_CHLA,
        "risk_policy": {
            "epsilon": RISK_EPSILON,
            "low_chla_ugL": RISK_LOW_CHLA,
            "bloom_chla_ugL": BLOOM_THRESHOLD_CHLA,
        },
        "trophic_state_proxy": TROPHIC_THRESHOLDS,
        "by_horizon": by_horizon.to_dict(orient="records"),
        "by_source_horizon": by_source_horizon.to_dict(orient="records"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build target tables from the monthly panel.")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET_DIR)
    parser.add_argument("--long", type=Path, default=DEFAULT_LONG)
    parser.add_argument("--model-long", type=Path, default=DEFAULT_MODEL_LONG)
    parser.add_argument("--panel-with-targets", type=Path, default=DEFAULT_PANEL_WITH_TARGETS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--horizons", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--max-origin-rows", type=int, default=None, help="Limit panel rows for smoke tests.")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_paths = [args.long, args.model_long, args.panel_with_targets, args.report, args.manifest]
    existing = [path for path in output_paths if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"Output exists: {existing}. Use --overwrite to replace target outputs.")

    started_at = datetime.now(timezone.utc)
    panel = pd.read_parquet(args.panel)
    if args.max_origin_rows is not None:
        panel = panel.head(args.max_origin_rows).copy()
    print(f"loaded panel {args.panel} ({len(panel):,} origin rows)", flush=True)

    target_long = build_target_long(panel, args.horizons)
    model_long = build_model_long(target_long)
    panel_with_targets = attach_targets_to_panel(panel, target_long, args.horizons)

    _write_parquet_atomic(target_long, args.long)
    print(f"target candidates written: {args.long} ({len(target_long):,} rows)", flush=True)
    _write_parquet_atomic(model_long, args.model_long)
    print(f"model targets written: {args.model_long} ({len(model_long):,} rows)", flush=True)
    _write_parquet_atomic(panel_with_targets, args.panel_with_targets)
    print(f"panel with targets written: {args.panel_with_targets} ({len(panel_with_targets):,} rows)", flush=True)

    _write_report(target_long, model_long, panel_with_targets, args)
    manifest = _manifest_payload(target_long, model_long, panel_with_targets, args, started_at)
    _write_json_atomic(manifest, args.manifest)
    print(f"target report written: {args.report}", flush=True)
    print(f"target manifest written: {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
