#!/usr/bin/env python
"""Audit operational predictor coverage for the no-current-Chl-a surface."""

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

from src.pandas_utils import dataframe_rows


AUDIT_VERSION = "no_chla_operational_surface_audit_v0"
DEFAULT_PANEL = Path("data/targets/panel_monthly_with_targets_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_SEQUENCES = Path("data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet")
DEFAULT_REPORT_DIR = Path("reports/pipe_grud/no_current_chla")
DEFAULT_PREFIX = "no_chla_operational_surface_audit"
DEFAULT_SUMMARY = DEFAULT_REPORT_DIR / f"{DEFAULT_PREFIX}_summary.csv"
DEFAULT_BY_SOURCE = DEFAULT_REPORT_DIR / f"{DEFAULT_PREFIX}_by_source_split_horizon.csv"
DEFAULT_FEATURE_COVERAGE = DEFAULT_REPORT_DIR / f"{DEFAULT_PREFIX}_feature_coverage.csv"
DEFAULT_SEQUENCE_COVERAGE = DEFAULT_REPORT_DIR / f"{DEFAULT_PREFIX}_sequence_coverage.csv"
DEFAULT_LOW_EVIDENCE_EXAMPLES = DEFAULT_REPORT_DIR / f"{DEFAULT_PREFIX}_low_evidence_examples.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / f"{DEFAULT_PREFIX}_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / f"{DEFAULT_PREFIX}_manifest.json"

PANEL_KEY_COLUMNS = ["source_id", "site_id", "site_id_source", "site_name", "year_month"]
SPLIT_COLUMNS = [
    "source_id",
    "site_id",
    "site_id_source",
    "site_name",
    "origin_year_month",
    "horizon_months",
    "target_year_month",
    "bloom_h",
    "target_risk_chla_h",
    "split",
]
RAW_VARIABLES = {
    "nutrient": ["TP_ugL", "TN_ugL"],
    "temperature": ["temperature_C"],
    "light_proxy": ["secchi_depth_m", "turbidity_NTU"],
    "physicochemical": ["DO_mgL", "pH"],
}
DERIVED_NUTRIENT_COLUMNS = ["TN_TP_ratio", "log_TP", "log_TN"]
FORBIDDEN_CHLA_PREDICTOR_COLUMNS = [
    "mean_chlorophyll_a_ugL",
    "std_chlorophyll_a_ugL",
    "min_chlorophyll_a_ugL",
    "max_chlorophyll_a_ugL",
    "n_obs_chlorophyll_a_ugL",
    "n_bad_chlorophyll_a_ugL",
    "qc_ok_rate_chlorophyll_a_ugL",
    "log_chlorophyll_a",
    "risk_chla",
]
FEATURE_ROWS = [
    ("nutrient", "TP_ugL", "mean_TP_ugL"),
    ("nutrient", "TN_ugL", "mean_TN_ugL"),
    ("nutrient", "TN_TP_ratio", "TN_TP_ratio"),
    ("nutrient", "log_TP", "log_TP"),
    ("nutrient", "log_TN", "log_TN"),
    ("temperature", "temperature_C", "mean_temperature_C"),
    ("light_proxy", "secchi_depth_m", "mean_secchi_depth_m"),
    ("light_proxy", "turbidity_NTU", "mean_turbidity_NTU"),
    ("physicochemical", "DO_mgL", "mean_DO_mgL"),
    ("physicochemical", "pH", "mean_pH"),
]
SEQUENCE_COLUMNS = [
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "split",
    "x_yN",
    "x_yF",
    "x_yT",
    "x_irc1",
    "x_irc1_no_chla",
    "x_evidence_N",
    "x_evidence_F",
    "x_evidence_T_no_chla",
    "x_missing_N",
    "x_missing_F",
    "x_missing_T_no_chla",
]


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


def _json_sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_json_sanitize(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return _json_sanitize(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


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
        json.dump(_json_sanitize(payload), handle, indent=2, ensure_ascii=False, default=_json_default, allow_nan=False)
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


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return float("nan")
    return float(numerator / denominator)


def _parquet_columns(path: Path) -> list[str]:
    return list(pq.read_schema(path).names)


def _read_parquet_columns(path: Path, columns: list[str], *, required: list[str]) -> pd.DataFrame:
    available = set(_parquet_columns(path))
    missing_required = sorted(set(required).difference(available))
    if missing_required:
        raise ValueError(f"{path} is missing required columns: {missing_required}")
    selected = [column for column in columns if column in available]
    return pd.read_parquet(path, columns=selected)


def _mean_column(variable: str) -> str:
    return f"mean_{variable}"


def _numeric_present(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return values.notna()


def read_panel(path: Path) -> pd.DataFrame:
    columns = PANEL_KEY_COLUMNS[:]
    for variables in RAW_VARIABLES.values():
        for variable in variables:
            columns.extend([_mean_column(variable), f"n_obs_{variable}", f"qc_ok_rate_{variable}"])
    columns.extend(DERIVED_NUTRIENT_COLUMNS)
    columns.extend(FORBIDDEN_CHLA_PREDICTOR_COLUMNS)
    return _read_parquet_columns(path, columns, required=["source_id", "site_id", "year_month"])


def read_splits(path: Path) -> pd.DataFrame:
    return _read_parquet_columns(path, SPLIT_COLUMNS, required=["source_id", "site_id", "origin_year_month", "split"])


def read_sequences(path: Path) -> pd.DataFrame:
    return _read_parquet_columns(path, SEQUENCE_COLUMNS, required=["source_id", "site_id", "origin_year_month", "split"])


def attach_origin_predictors(splits: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    origin = panel.rename(columns={"year_month": "origin_year_month"}).copy()
    merge_columns = ["source_id", "site_id", "origin_year_month"]
    out = splits.merge(
        origin.drop(columns=[column for column in ["site_id_source", "site_name"] if column in origin.columns]),
        on=merge_columns,
        how="left",
        validate="many_to_one",
    )
    present_columns = [column for _, _, column in FEATURE_ROWS if column in out.columns]
    out["origin_panel_matched"] = out[present_columns].notna().any(axis=1) if present_columns else False
    return out


def add_evidence_flags(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["has_tp"] = _numeric_present(out, "mean_TP_ugL")
    out["has_tn"] = _numeric_present(out, "mean_TN_ugL")
    out["has_any_nutrient"] = out["has_tp"] | out["has_tn"]
    out["has_both_nutrients"] = out["has_tp"] & out["has_tn"]
    out["has_nutrient_ratio"] = _numeric_present(out, "TN_TP_ratio")
    out["has_temperature"] = _numeric_present(out, "mean_temperature_C")
    out["has_light_proxy"] = _numeric_present(out, "mean_secchi_depth_m") | _numeric_present(out, "mean_turbidity_NTU")
    out["has_physicochemical"] = _numeric_present(out, "mean_DO_mgL") | _numeric_present(out, "mean_pH")
    out["has_current_chla_forbidden"] = _numeric_present(out, "mean_chlorophyll_a_ugL") | _numeric_present(out, "risk_chla")
    out["nonseason_exogenous_groups"] = (
        out["has_any_nutrient"].astype("int8")
        + out["has_temperature"].astype("int8")
        + out["has_light_proxy"].astype("int8")
        + out["has_physicochemical"].astype("int8")
    )
    high = out["has_any_nutrient"] & out["has_temperature"] & (out["has_light_proxy"] | out["has_physicochemical"])
    medium = out["has_any_nutrient"] & (out["has_temperature"] | out["has_light_proxy"] | out["has_physicochemical"])
    low = out["nonseason_exogenous_groups"] > 0
    out["operational_evidence_band"] = "season_only"
    out.loc[low, "operational_evidence_band"] = "low"
    out.loc[medium, "operational_evidence_band"] = "medium"
    out.loc[high, "operational_evidence_band"] = "high"
    out["precursor_ready"] = high
    return out


def _bloom_positive(series: pd.Series) -> int:
    return int(pd.Series(series).fillna(False).astype(bool).sum())


def summarize_operational_coverage(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    grouped = frame.groupby(group_columns, dropna=False)
    summary = grouped.agg(
        rows=("site_id", "size"),
        sites=("site_id", "nunique"),
        bloom_positive=("bloom_h", _bloom_positive),
        target_risk_chla_mean=("target_risk_chla_h", "mean"),
        origin_panel_matched_rows=("origin_panel_matched", "sum"),
        current_chla_forbidden_present_rows=("has_current_chla_forbidden", "sum"),
        any_nutrient_rows=("has_any_nutrient", "sum"),
        both_nutrients_rows=("has_both_nutrients", "sum"),
        nutrient_ratio_rows=("has_nutrient_ratio", "sum"),
        temperature_rows=("has_temperature", "sum"),
        light_proxy_rows=("has_light_proxy", "sum"),
        physicochemical_rows=("has_physicochemical", "sum"),
        precursor_ready_rows=("precursor_ready", "sum"),
        mean_nonseason_exogenous_groups=("nonseason_exogenous_groups", "mean"),
        origin_min=("origin_year_month", "min"),
        origin_max=("origin_year_month", "max"),
        target_min=("target_year_month", "min"),
        target_max=("target_year_month", "max"),
    ).reset_index()
    band_counts = (
        frame.groupby(group_columns + ["operational_evidence_band"], dropna=False)
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    summary = summary.merge(band_counts, on=group_columns, how="left")
    for band in ["high", "medium", "low", "season_only"]:
        if band not in summary.columns:
            summary[band] = 0
        summary[f"{band}_rate"] = summary[band] / summary["rows"]
    rate_columns = [
        "origin_panel_matched",
        "current_chla_forbidden_present",
        "any_nutrient",
        "both_nutrients",
        "nutrient_ratio",
        "temperature",
        "light_proxy",
        "physicochemical",
        "precursor_ready",
    ]
    for column in rate_columns:
        summary[f"{column}_rate"] = summary[f"{column}_rows"] / summary["rows"]
    summary["bloom_rate"] = summary["bloom_positive"] / summary["rows"]
    int_columns = [
        "rows",
        "sites",
        "bloom_positive",
        "origin_panel_matched_rows",
        "current_chla_forbidden_present_rows",
        "any_nutrient_rows",
        "both_nutrients_rows",
        "nutrient_ratio_rows",
        "temperature_rows",
        "light_proxy_rows",
        "physicochemical_rows",
        "precursor_ready_rows",
        "high",
        "medium",
        "low",
        "season_only",
    ]
    for column in int_columns:
        summary[column] = summary[column].fillna(0).astype("int64")
    return summary.sort_values(group_columns).reset_index(drop=True)


def build_feature_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["source_id", "split", "horizon_months"]
    for _, group in frame.groupby(group_columns, dropna=False):
        source_id = str(group["source_id"].iloc[0])
        split = str(group["split"].iloc[0])
        horizon = int(group["horizon_months"].iloc[0])
        for family, variable, column in FEATURE_ROWS:
            present = _numeric_present(group, column)
            rows.append(
                {
                    "source_id": source_id,
                    "split": split,
                    "horizon_months": horizon,
                    "feature_family": family,
                    "feature_name": variable,
                    "column": column,
                    "rows": int(len(group)),
                    "present_rows": int(present.sum()),
                    "coverage_rate": _safe_rate(float(present.sum()), float(len(group))),
                    "sites_with_value": int(group.loc[present, "site_id"].nunique()),
                    "bloom_positive": _bloom_positive(group["bloom_h"]),
                }
            )
    return pd.DataFrame(rows).sort_values(["source_id", "split", "horizon_months", "feature_family", "feature_name"])


def build_sequence_coverage(sequences: pd.DataFrame | None) -> pd.DataFrame:
    if sequences is None or sequences.empty:
        return pd.DataFrame(
            columns=[
                "source_id",
                "split",
                "rows",
                "sites",
                "origin_min",
                "origin_max",
                "target_min",
                "target_max",
                "mean_x_evidence_N",
                "mean_x_evidence_F",
                "mean_x_evidence_T_no_chla",
                "mean_x_missing_N",
                "mean_x_missing_F",
                "mean_x_missing_T_no_chla",
                "low_nutrient_evidence_rate",
                "low_temperature_evidence_rate",
                "mean_abs_irc_chla_delta",
                "changed_irc_chla_delta_rate",
            ]
        )
    frame = sequences.copy()
    for column in SEQUENCE_COLUMNS:
        if column.startswith("x_") and column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if {"x_irc1", "x_irc1_no_chla"}.issubset(frame.columns):
        frame["abs_irc_chla_delta"] = (frame["x_irc1"] - frame["x_irc1_no_chla"]).abs()
        frame["changed_irc_chla_delta"] = frame["abs_irc_chla_delta"] > 1e-9
    else:
        frame["abs_irc_chla_delta"] = np.nan
        frame["changed_irc_chla_delta"] = False
    frame["low_nutrient_evidence"] = frame["x_evidence_N"].fillna(0.0) < 0.34 if "x_evidence_N" in frame.columns else False
    frame["low_temperature_evidence"] = (
        frame["x_evidence_T_no_chla"].fillna(0.0) < 0.34 if "x_evidence_T_no_chla" in frame.columns else False
    )
    grouped = frame.groupby(["source_id", "split"], dropna=False)
    out = grouped.agg(
        rows=("site_id", "size"),
        sites=("site_id", "nunique"),
        origin_min=("origin_year_month", "min"),
        origin_max=("origin_year_month", "max"),
        target_min=("target_year_month", "min"),
        target_max=("target_year_month", "max"),
        mean_x_evidence_N=("x_evidence_N", "mean") if "x_evidence_N" in frame.columns else ("site_id", lambda _: np.nan),
        mean_x_evidence_F=("x_evidence_F", "mean") if "x_evidence_F" in frame.columns else ("site_id", lambda _: np.nan),
        mean_x_evidence_T_no_chla=("x_evidence_T_no_chla", "mean")
        if "x_evidence_T_no_chla" in frame.columns
        else ("site_id", lambda _: np.nan),
        mean_x_missing_N=("x_missing_N", "mean") if "x_missing_N" in frame.columns else ("site_id", lambda _: np.nan),
        mean_x_missing_F=("x_missing_F", "mean") if "x_missing_F" in frame.columns else ("site_id", lambda _: np.nan),
        mean_x_missing_T_no_chla=("x_missing_T_no_chla", "mean")
        if "x_missing_T_no_chla" in frame.columns
        else ("site_id", lambda _: np.nan),
        low_nutrient_evidence_rate=("low_nutrient_evidence", "mean"),
        low_temperature_evidence_rate=("low_temperature_evidence", "mean"),
        mean_abs_irc_chla_delta=("abs_irc_chla_delta", "mean"),
        changed_irc_chla_delta_rate=("changed_irc_chla_delta", "mean"),
    ).reset_index()
    out["rows"] = out["rows"].astype("int64")
    out["sites"] = out["sites"].astype("int64")
    return out.sort_values(["source_id", "split"]).reset_index(drop=True)


def build_low_evidence_examples(frame: pd.DataFrame, examples_per_group: int) -> pd.DataFrame:
    if examples_per_group <= 0 or frame.empty:
        return pd.DataFrame()
    columns = [
        "source_id",
        "site_id",
        "site_id_source",
        "site_name",
        "split",
        "horizon_months",
        "origin_year_month",
        "target_year_month",
        "bloom_h",
        "target_risk_chla_h",
        "operational_evidence_band",
        "has_tp",
        "has_tn",
        "has_temperature",
        "has_light_proxy",
        "has_physicochemical",
        "has_current_chla_forbidden",
    ]
    available = [column for column in columns if column in frame.columns]
    subset = frame[frame["operational_evidence_band"].isin(["season_only", "low"])].copy()
    subset = subset.sort_values(["source_id", "split", "horizon_months", "origin_year_month", "site_id"])
    return (
        subset.groupby(["source_id", "split", "horizon_months"], dropna=False)
        .head(examples_per_group)[available]
        .reset_index(drop=True)
    )


def write_report(
    *,
    report_path: Path,
    audit_frame: pd.DataFrame,
    summary: pd.DataFrame,
    by_source: pd.DataFrame,
    sequence_coverage: pd.DataFrame,
    output_paths: dict[str, Path],
    sequence_loaded: bool,
    started_at: datetime,
) -> None:
    rows = len(audit_frame)
    sites = int(audit_frame["site_id"].nunique()) if rows else 0
    any_nutrient_rate = float(audit_frame["has_any_nutrient"].mean()) if rows else float("nan")
    precursor_ready_rate = float(audit_frame["precursor_ready"].mean()) if rows else float("nan")
    season_only_rate = float((audit_frame["operational_evidence_band"] == "season_only").mean()) if rows else float("nan")
    forbidden_rate = float(audit_frame["has_current_chla_forbidden"].mean()) if rows else float("nan")
    lines = [
        "# No-Current-Chl-a Operational Surface Audit",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        f"Audit version: `{AUDIT_VERSION}`",
        "",
        "## Purpose",
        "",
        "This audit checks whether target-bearing rows have non-Chl-a precursor evidence at the origin month.",
        "It does not train, calibrate, or select thresholds.",
        "",
        "Current Chl-a columns are treated as forbidden predictors for the operational early-warning contract.",
        "They are counted only as a diagnostic reference.",
        "",
        "## Headline Counts",
        "",
        f"- Target split rows audited: `{_format_int(rows)}`",
        f"- Source-scoped sites audited: `{_format_int(sites)}`",
        f"- Rows with any nutrient precursor: `{_format_float(any_nutrient_rate)}`",
        f"- Rows with high precursor readiness: `{_format_float(precursor_ready_rate)}`",
        f"- Rows with season-only non-Chl-a evidence: `{_format_float(season_only_rate)}`",
        f"- Rows where forbidden current Chl-a exists but must not be used: `{_format_float(forbidden_rate)}`",
        "",
        "## Evidence Band Rules",
        "",
        "- `high`: nutrient evidence plus temperature plus either light proxy or physicochemical evidence.",
        "- `medium`: nutrient evidence plus at least one nonseason companion group.",
        "- `low`: at least one nonseason exogenous group, but not enough for `medium`.",
        "- `season_only`: no nonseason exogenous group is present at the origin month.",
        "",
        "## By Split And Horizon",
        "",
        "| split | horizon | rows | sites | bloom rate | any nutrient | both nutrients | temperature | high | medium | low | season only |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if summary.empty:
        lines.append("| `NA` | 0 | 0 | 0 | NA | NA | NA | NA | NA | NA | NA | NA |")
    else:
        for row in dataframe_rows(summary):
            lines.append(
                f"| `{row.split}` | {int(row.horizon_months)} | {_format_int(int(row.rows))} | "
                f"{_format_int(int(row.sites))} | {_format_float(float(row.bloom_rate))} | "
                f"{_format_float(float(row.any_nutrient_rate))} | {_format_float(float(row.both_nutrients_rate))} | "
                f"{_format_float(float(row.temperature_rate))} | {_format_float(float(row.high_rate))} | "
                f"{_format_float(float(row.medium_rate))} | {_format_float(float(row.low_rate))} | "
                f"{_format_float(float(row.season_only_rate))} |"
            )
    lines.extend(
        [
            "",
            "## By Source",
            "",
            "| source | split | horizon | rows | bloom rate | any nutrient | high | season only | forbidden Chl-a present |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(by_source.head(40)):
        lines.append(
            f"| `{row.source_id}` | `{row.split}` | {int(row.horizon_months)} | {_format_int(int(row.rows))} | "
            f"{_format_float(float(row.bloom_rate))} | {_format_float(float(row.any_nutrient_rate))} | "
            f"{_format_float(float(row.high_rate))} | {_format_float(float(row.season_only_rate))} | "
            f"{_format_float(float(row.current_chla_forbidden_present_rate))} |"
        )
    if len(by_source) > 40:
        lines.append(f"| ... | ... | ... | {len(by_source) - 40} additional rows in CSV | ... | ... | ... | ... | ... |")

    lines.extend(["", "## Sequence Surface Check", ""])
    if not sequence_loaded:
        lines.append("- No-current-Chl-a sequence table was not loaded; sequence coverage was skipped.")
    elif sequence_coverage.empty:
        lines.append("- No sequence rows were available.")
    else:
        lines.extend(
            [
                "| source | split | rows | mean evidence N | mean evidence F | mean evidence T no Chl-a | low nutrient evidence | changed IRC by Chl-a removal |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in dataframe_rows(sequence_coverage):
            lines.append(
                f"| `{row.source_id}` | `{row.split}` | {_format_int(int(row.rows))} | "
                f"{_format_float(float(row.mean_x_evidence_N))} | {_format_float(float(row.mean_x_evidence_F))} | "
                f"{_format_float(float(row.mean_x_evidence_T_no_chla))} | "
                f"{_format_float(float(row.low_nutrient_evidence_rate))} | "
                f"{_format_float(float(row.changed_irc_chla_delta_rate))} |"
            )

    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- Low nutrient coverage is evidence about the available operational data surface, not evidence that nutrients are ecologically unimportant.",
            "- Rows with current Chl-a present are still valid targets, but current Chl-a must remain excluded from operational predictors.",
            "- Source-scoped targets do not assume that WQP nutrient rows and AquaMatch Chl-a rows refer to the same lake unless an accepted crosswalk is promoted later.",
            "",
            "## Outputs",
            "",
        ]
    )
    for label, path in output_paths.items():
        lines.append(f"- `{label}`: `{path}`")
    lines.append("")
    _write_text_atomic("\n".join(lines), report_path)


def manifest_payload(
    *,
    args: argparse.Namespace,
    audit_frame: pd.DataFrame,
    summary: pd.DataFrame,
    by_source: pd.DataFrame,
    feature_coverage: pd.DataFrame,
    sequence_coverage: pd.DataFrame,
    low_evidence_examples: pd.DataFrame,
    output_paths: dict[str, Path],
    started_at: datetime,
    sequence_loaded: bool,
) -> dict[str, Any]:
    inputs = [_file_record(args.panel), _file_record(args.splits)]
    if sequence_loaded:
        inputs.append(_file_record(args.sequences))
    outputs = [_file_record(path) for path in output_paths.values() if path != args.manifest]
    return {
        "audit_version": AUDIT_VERSION,
        "status": "completed",
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "forbidden_chla_predictor_columns": FORBIDDEN_CHLA_PREDICTOR_COLUMNS,
            "evidence_band_rules": {
                "high": "nutrient and temperature and (light_proxy or physicochemical)",
                "medium": "nutrient and at least one of temperature, light_proxy, physicochemical",
                "low": "at least one nonseason exogenous group, but not medium/high",
                "season_only": "no nonseason exogenous group",
            },
            "examples_per_group": int(args.examples_per_group),
            "sequence_optional": bool(args.sequence_optional),
        },
        "row_counts": {
            "audited_rows": int(len(audit_frame)),
            "audited_sites": int(audit_frame["site_id"].nunique()) if len(audit_frame) else 0,
            "summary_rows": int(len(summary)),
            "by_source_rows": int(len(by_source)),
            "feature_coverage_rows": int(len(feature_coverage)),
            "sequence_coverage_rows": int(len(sequence_coverage)),
            "low_evidence_example_rows": int(len(low_evidence_examples)),
        },
        "inputs": inputs,
        "outputs": outputs,
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit no-current-Chl-a operational predictor coverage.")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--sequences", type=Path, default=DEFAULT_SEQUENCES)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--by-source", type=Path, default=DEFAULT_BY_SOURCE)
    parser.add_argument("--feature-coverage", type=Path, default=DEFAULT_FEATURE_COVERAGE)
    parser.add_argument("--sequence-coverage", type=Path, default=DEFAULT_SEQUENCE_COVERAGE)
    parser.add_argument("--low-evidence-examples", type=Path, default=DEFAULT_LOW_EVIDENCE_EXAMPLES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--examples-per-group", type=int, default=5)
    parser.add_argument("--sequence-optional", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_paths = {
        "summary": args.summary,
        "by_source": args.by_source,
        "feature_coverage": args.feature_coverage,
        "sequence_coverage": args.sequence_coverage,
        "low_evidence_examples": args.low_evidence_examples,
        "report": args.report,
        "manifest": args.manifest,
    }
    existing = [path for path in output_paths.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"Output exists: {existing}. Use --overwrite to replace audit outputs.")

    if not args.sequences.exists() and not args.sequence_optional:
        raise SystemExit(f"No-current-Chl-a sequence table is missing: {args.sequences}")

    started_at = datetime.now(timezone.utc)
    panel = read_panel(args.panel)
    print(f"loaded origin panel ({len(panel):,} rows)", flush=True)
    splits = read_splits(args.splits)
    print(f"loaded split target rows ({len(splits):,} rows)", flush=True)
    audit_frame = add_evidence_flags(attach_origin_predictors(splits, panel))
    print(f"built audit frame ({len(audit_frame):,} rows)", flush=True)

    sequence_loaded = args.sequences.exists()
    sequences = read_sequences(args.sequences) if sequence_loaded else None
    if sequences is not None:
        print(f"loaded no-current-Chl-a sequences ({len(sequences):,} rows)", flush=True)

    summary = summarize_operational_coverage(audit_frame, ["split", "horizon_months"])
    by_source = summarize_operational_coverage(audit_frame, ["source_id", "split", "horizon_months"])
    feature_coverage = build_feature_coverage(audit_frame)
    sequence_coverage = build_sequence_coverage(sequences)
    low_evidence_examples = build_low_evidence_examples(audit_frame, args.examples_per_group)

    _write_csv_atomic(summary, args.summary)
    _write_csv_atomic(by_source, args.by_source)
    _write_csv_atomic(feature_coverage, args.feature_coverage)
    _write_csv_atomic(sequence_coverage, args.sequence_coverage)
    _write_csv_atomic(low_evidence_examples, args.low_evidence_examples)
    write_report(
        report_path=args.report,
        audit_frame=audit_frame,
        summary=summary,
        by_source=by_source,
        sequence_coverage=sequence_coverage,
        output_paths={key: value for key, value in output_paths.items() if key != "manifest"},
        sequence_loaded=sequence_loaded,
        started_at=started_at,
    )
    manifest = manifest_payload(
        args=args,
        audit_frame=audit_frame,
        summary=summary,
        by_source=by_source,
        feature_coverage=feature_coverage,
        sequence_coverage=sequence_coverage,
        low_evidence_examples=low_evidence_examples,
        output_paths=output_paths,
        started_at=started_at,
        sequence_loaded=sequence_loaded,
    )
    _write_json_atomic(manifest, args.manifest)

    for label, path in output_paths.items():
        print(f"wrote {label}: {path}", flush=True)


if __name__ == "__main__":
    main()
