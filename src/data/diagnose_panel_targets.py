#!/usr/bin/env python
"""Generate coverage and target diagnostics before data freeze."""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows


DEFAULT_PANEL_WITH_TARGETS = Path("data/targets/panel_monthly_with_targets_v0.parquet")
DEFAULT_TARGET_LONG = Path("data/targets/monthly_targets_long_v0.parquet")
DEFAULT_OUTPUT_DIR = Path("data/diagnostics")
DEFAULT_REPORT = Path("reports/data/DATA_DIAGNOSTIC_REPORT_v0.md")
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "diagnostic_manifest_v0.json"
DEFAULT_FIGURE_DIR = Path("reports/data/figures")

VARIABLES = [
    "DO_mgL",
    "TN_ugL",
    "TP_ugL",
    "chlorophyll_a_ugL",
    "pH",
    "secchi_depth_m",
    "temperature_C",
    "turbidity_NTU",
]
KEY_COLUMNS = ["source_id", "site_id", "site_id_source", "site_name", "year_month"]


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


def _svg_text(x: float, y: float, text: str, *, size: int = 12, anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
        f'font-size="{size}" text-anchor="{anchor}" fill="#1f2937">{html.escape(str(text))}</text>'
    )


def _write_bar_svg(path: Path, title: str, labels: list[str], values: list[float], *, max_value: float = 1.0) -> None:
    width = 920
    row_height = 34
    margin_left = 230
    margin_right = 90
    margin_top = 52
    height = margin_top + row_height * len(labels) + 35
    bar_width = width - margin_left - margin_right
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        _svg_text(24, 30, title, size=18),
        f'<line x1="{margin_left}" y1="{margin_top - 18}" x2="{margin_left + bar_width}" y2="{margin_top - 18}" stroke="#d1d5db"/>',
    ]
    for index, (label, value) in enumerate(zip(labels, values, strict=False)):
        y = margin_top + index * row_height
        clipped = min(max(float(value), 0.0), max_value)
        width_value = 0 if max_value == 0 else clipped / max_value * bar_width
        lines.append(_svg_text(20, y + 17, label, size=12))
        lines.append(f'<rect x="{margin_left}" y="{y}" width="{bar_width}" height="20" fill="#eef2f7"/>')
        lines.append(f'<rect x="{margin_left}" y="{y}" width="{width_value:.1f}" height="20" fill="#2563eb"/>')
        lines.append(_svg_text(margin_left + bar_width + 10, y + 15, f"{float(value):.3f}", size=12))
    lines.append("</svg>")
    _write_text_atomic("\n".join(lines), path)


def _color_for_rate(value: float) -> str:
    value = min(max(float(value), 0.0), 1.0)
    red = int(239 - 205 * value)
    green = int(246 - 85 * value)
    blue = int(255 - 120 * value)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _write_heatmap_svg(path: Path, title: str, matrix: pd.DataFrame) -> None:
    cell_width = 118
    cell_height = 38
    margin_left = 150
    margin_top = 86
    width = margin_left + cell_width * len(matrix.columns) + 40
    height = margin_top + cell_height * len(matrix.index) + 60
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        _svg_text(24, 30, title, size=18),
    ]
    for column_index, column in enumerate(matrix.columns):
        x = margin_left + column_index * cell_width + cell_width / 2
        lines.append(_svg_text(x, margin_top - 24, column, size=11, anchor="middle"))
    for row_index, index in enumerate(matrix.index):
        y = margin_top + row_index * cell_height
        lines.append(_svg_text(20, y + 24, index, size=12))
        for column_index, column in enumerate(matrix.columns):
            value = float(matrix.loc[index, column])
            x = margin_left + column_index * cell_width
            lines.append(
                f'<rect x="{x}" y="{y}" width="{cell_width - 2}" height="{cell_height - 2}" '
                f'fill="{_color_for_rate(value)}" stroke="#ffffff"/>'
            )
            lines.append(_svg_text(x + cell_width / 2, y + 23, f"{value:.2f}", size=11, anchor="middle"))
    lines.append("</svg>")
    _write_text_atomic("\n".join(lines), path)


def _target_has_cols(horizons: list[int]) -> list[str]:
    cols = []
    for horizon in horizons:
        cols.extend(
            [
                f"target_month_exists_h{horizon}",
                f"has_target_h{horizon}",
                f"bloom_h_h{horizon}",
            ]
        )
    return cols


def read_panel(path: Path, horizons: list[int]) -> pd.DataFrame:
    columns = KEY_COLUMNS[:]
    for variable in VARIABLES:
        columns.extend(
            [
                f"mean_{variable}",
                f"n_obs_{variable}",
                f"n_bad_{variable}",
                f"qc_ok_rate_{variable}",
            ]
        )
    columns.extend(_target_has_cols(horizons))
    return pd.read_parquet(path, columns=columns)


def read_target_long(path: Path) -> pd.DataFrame:
    columns = [
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
        "bloom_h",
        "target_risk_chla_h",
        "target_trophic_state_h",
    ]
    return pd.read_parquet(path, columns=columns)


def build_coverage_by_source(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for source_id, group in panel.groupby("source_id", dropna=False):
        rows.append(
            {
                "source_id": source_id,
                "site_month_rows": len(group),
                "sites": group["site_id"].nunique(),
                "start_year_month": group["year_month"].min(),
                "end_year_month": group["year_month"].max(),
            }
        )
    return pd.DataFrame(rows).sort_values("source_id").reset_index(drop=True)


def build_coverage_by_site(panel: pd.DataFrame) -> pd.DataFrame:
    grouped = panel.groupby(["source_id", "site_id", "site_id_source", "site_name"], dropna=False)
    out = grouped.agg(
        site_month_rows=("year_month", "size"),
        start_year_month=("year_month", "min"),
        end_year_month=("year_month", "max"),
    ).reset_index()
    for variable in VARIABLES:
        mean_col = f"mean_{variable}"
        out[f"months_with_{variable}"] = grouped[mean_col].count().to_numpy()
    out["months_with_chla"] = out["months_with_chlorophyll_a_ugL"]
    out["chla_coverage_rate"] = out["months_with_chla"] / out["site_month_rows"]
    return out.sort_values(["source_id", "site_id"]).reset_index(drop=True)


def build_coverage_by_variable(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total_site_months = len(panel)
    for variable in VARIABLES:
        mean_col = f"mean_{variable}"
        n_obs_col = f"n_obs_{variable}"
        n_bad_col = f"n_bad_{variable}"
        qc_col = f"qc_ok_rate_{variable}"
        has_var = panel[mean_col].notna()
        rows.append(
            {
                "variable_canonical": variable,
                "site_month_rows": total_site_months,
                "months_with_value": int(has_var.sum()),
                "coverage_rate": float(has_var.mean()),
                "sites_with_value": int(panel.loc[has_var, "site_id"].nunique()),
                "ok_observations": int(panel[n_obs_col].sum(skipna=True)),
                "bad_observations": int(panel[n_bad_col].sum(skipna=True)),
                "mean_qc_ok_rate_across_months": float(panel.loc[has_var, qc_col].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("variable_canonical").reset_index(drop=True)


def build_coverage_by_site_variable(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    base = panel[["source_id", "site_id", "site_id_source", "site_name", "year_month"]]
    for variable in VARIABLES:
        mean_col = f"mean_{variable}"
        n_obs_col = f"n_obs_{variable}"
        n_bad_col = f"n_bad_{variable}"
        tmp = base.copy()
        tmp["variable_canonical"] = variable
        tmp["has_value"] = panel[mean_col].notna()
        tmp["ok_observations"] = panel[n_obs_col].fillna(0)
        tmp["bad_observations"] = panel[n_bad_col].fillna(0)
        grouped = tmp.groupby(
            ["source_id", "site_id", "site_id_source", "site_name", "variable_canonical"],
            dropna=False,
        )
        out = grouped.agg(
            site_month_rows=("year_month", "size"),
            months_with_value=("has_value", "sum"),
            ok_observations=("ok_observations", "sum"),
            bad_observations=("bad_observations", "sum"),
        ).reset_index()
        rows.append(out)
    result = pd.concat(rows, ignore_index=True)
    result["coverage_rate"] = result["months_with_value"] / result["site_month_rows"]
    int_cols = ["site_month_rows", "months_with_value", "ok_observations", "bad_observations"]
    for column in int_cols:
        result[column] = result[column].round().astype("int64")
    return result.sort_values(["source_id", "site_id", "variable_canonical"]).reset_index(drop=True)


def build_coverage_by_source_variable(coverage_by_site_variable: pd.DataFrame) -> pd.DataFrame:
    grouped = coverage_by_site_variable.groupby(["source_id", "variable_canonical"], dropna=False)
    out = grouped.agg(
        site_month_rows=("site_month_rows", "sum"),
        months_with_value=("months_with_value", "sum"),
        sites=("site_id", "nunique"),
        sites_with_value=("months_with_value", lambda series: int((series > 0).sum())),
        ok_observations=("ok_observations", "sum"),
        bad_observations=("bad_observations", "sum"),
    ).reset_index()
    out["coverage_rate"] = out["months_with_value"] / out["site_month_rows"]
    return out.sort_values(["source_id", "variable_canonical"]).reset_index(drop=True)


def build_bloom_counts_by_site_horizon(target_long: pd.DataFrame) -> pd.DataFrame:
    grouped = target_long.groupby(
        ["source_id", "site_id", "site_id_source", "site_name", "horizon_months"],
        dropna=False,
    )
    out = grouped.agg(
        candidate_rows=("has_target", "size"),
        target_month_rows=("target_month_exists", "sum"),
        target_rows=("has_target", "sum"),
        bloom_positive=("bloom_h", "sum"),
    ).reset_index()
    out["bloom_positive"] = out["bloom_positive"].fillna(0).astype("int64")
    out["bloom_negative"] = out["target_rows"] - out["bloom_positive"]
    out["missing_target_month"] = out["candidate_rows"] - out["target_month_rows"]
    out["missing_chla_in_target_month"] = out["target_month_rows"] - out["target_rows"]
    out["bloom_rate"] = np.where(out["target_rows"] > 0, out["bloom_positive"] / out["target_rows"], np.nan)
    int_cols = [
        "candidate_rows",
        "target_month_rows",
        "target_rows",
        "bloom_positive",
        "bloom_negative",
        "missing_target_month",
        "missing_chla_in_target_month",
    ]
    for column in int_cols:
        out[column] = out[column].astype("int64")
    return out.sort_values(["source_id", "site_id", "horizon_months"]).reset_index(drop=True)


def build_target_coverage_by_source_horizon(target_long: pd.DataFrame) -> pd.DataFrame:
    grouped = target_long.groupby(["source_id", "horizon_months"], dropna=False)
    out = grouped.agg(
        candidate_rows=("has_target", "size"),
        target_month_rows=("target_month_exists", "sum"),
        target_rows=("has_target", "sum"),
        bloom_positive=("bloom_h", "sum"),
    ).reset_index()
    out["bloom_positive"] = out["bloom_positive"].fillna(0).astype("int64")
    out["bloom_negative"] = out["target_rows"] - out["bloom_positive"]
    out["missing_target_month"] = out["candidate_rows"] - out["target_month_rows"]
    out["missing_chla_in_target_month"] = out["target_month_rows"] - out["target_rows"]
    out["target_coverage_rate"] = out["target_rows"] / out["candidate_rows"]
    out["bloom_rate"] = np.where(out["target_rows"] > 0, out["bloom_positive"] / out["target_rows"], np.nan)
    return out.sort_values(["source_id", "horizon_months"]).reset_index(drop=True)


def build_feature_missingness(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    feature_cols = [column for column in panel.columns if column.startswith(("mean_", "n_obs_", "n_bad_", "qc_ok_rate_"))]
    for column in sorted(feature_cols):
        missing = int(panel[column].isna().sum())
        rows.append(
            {
                "column": column,
                "rows": len(panel),
                "missing_rows": missing,
                "present_rows": len(panel) - missing,
                "missing_rate": missing / len(panel),
            }
        )
    return pd.DataFrame(rows)


def build_chla_distribution_by_source(target_long: pd.DataFrame) -> pd.DataFrame:
    model = target_long[target_long["has_target"]].copy()
    grouped = model.groupby(["source_id", "horizon_months"], dropna=False)["future_chlorophyll_a_ugL"]
    out = grouped.agg(
        count="count",
        mean="mean",
        median="median",
        p05=lambda series: series.quantile(0.05),
        p95=lambda series: series.quantile(0.95),
        max="max",
    ).reset_index()
    return out.sort_values(["source_id", "horizon_months"]).reset_index(drop=True)


def write_figures(
    figure_dir: Path,
    coverage_by_variable: pd.DataFrame,
    coverage_by_source_variable: pd.DataFrame,
    target_coverage: pd.DataFrame,
    chla_distribution: pd.DataFrame,
) -> dict[str, Path]:
    figure_dir.mkdir(parents=True, exist_ok=True)
    figures = {
        "variable_coverage": figure_dir / "variable_coverage.svg",
        "source_variable_coverage": figure_dir / "source_variable_coverage.svg",
        "target_coverage": figure_dir / "target_coverage_by_source_horizon.svg",
        "future_chla_p95": figure_dir / "future_chla_p95_by_source_horizon.svg",
    }
    _write_bar_svg(
        figures["variable_coverage"],
        "Coverage Rate By Variable",
        coverage_by_variable["variable_canonical"].tolist(),
        coverage_by_variable["coverage_rate"].astype(float).tolist(),
    )
    heatmap = coverage_by_source_variable.pivot_table(
        index="source_id",
        columns="variable_canonical",
        values="coverage_rate",
        aggfunc="first",
    ).fillna(0.0)
    heatmap = heatmap[[column for column in VARIABLES if column in heatmap.columns]]
    _write_heatmap_svg(figures["source_variable_coverage"], "Coverage Rate By Source And Variable", heatmap)

    target_labels = [f"{row.source_id} h{int(row.horizon_months)}" for row in dataframe_rows(target_coverage)]
    _write_bar_svg(
        figures["target_coverage"],
        "Target Coverage Rate By Source And Horizon",
        target_labels,
        target_coverage["target_coverage_rate"].astype(float).tolist(),
    )

    chla_labels = [f"{row.source_id} h{int(row.horizon_months)}" for row in dataframe_rows(chla_distribution)]
    max_p95 = float(max(chla_distribution["p95"].max(), 1.0))
    _write_bar_svg(
        figures["future_chla_p95"],
        "Future Chl-a p95 By Source And Horizon",
        chla_labels,
        chla_distribution["p95"].astype(float).tolist(),
        max_value=max_p95,
    )
    return figures


def write_report(
    report_path: Path,
    panel: pd.DataFrame,
    target_long: pd.DataFrame,
    coverage_by_source: pd.DataFrame,
    coverage_by_variable: pd.DataFrame,
    target_coverage: pd.DataFrame,
    bloom_counts: pd.DataFrame,
    chla_distribution: pd.DataFrame,
    paths: dict[str, Path],
    figures: dict[str, Path],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    target_rows = int(target_long["has_target"].sum())
    bloom_rows = int(target_long.loc[target_long["has_target"], "bloom_h"].sum())
    lines = [
        "# Data Diagnostic Report v0",
        "",
        f"Panel rows: `{_format_int(len(panel))}`",
        f"Target candidate rows: `{_format_int(len(target_long))}`",
        f"Rows with target: `{_format_int(target_rows)}`",
        f"Bloom positives across all horizons: `{_format_int(bloom_rows)}`",
        "",
        "## Source Coverage",
        "",
        "| source_id | site-month rows | sites | start | end |",
        "|---|---:|---:|---|---|",
    ]
    for row in dataframe_rows(coverage_by_source):
        lines.append(
            f"| `{row.source_id}` | {_format_int(int(row.site_month_rows))} | {_format_int(int(row.sites))} | "
            f"`{row.start_year_month}` | `{row.end_year_month}` |"
        )

    lines.extend(
        [
            "",
            "## Variable Coverage",
            "",
            "| variable | months with value | coverage rate | sites with value | OK observations | bad observations | mean monthly QC OK rate |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(coverage_by_variable):
        lines.append(
            f"| `{row.variable_canonical}` | {_format_int(int(row.months_with_value))} | "
            f"{_format_float(float(row.coverage_rate))} | {_format_int(int(row.sites_with_value))} | "
            f"{_format_int(int(row.ok_observations))} | {_format_int(int(row.bad_observations))} | "
            f"{_format_float(float(row.mean_qc_ok_rate_across_months))} |"
        )

    lines.extend(
        [
            "",
            "## Target Coverage By Source And Horizon",
            "",
            "| source_id | horizon | target rows | target coverage rate | bloom positives | bloom rate | missing target month | missing Chl-a in target month |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(target_coverage):
        lines.append(
            f"| `{row.source_id}` | {int(row.horizon_months)} | {_format_int(int(row.target_rows))} | "
            f"{_format_float(float(row.target_coverage_rate))} | {_format_int(int(row.bloom_positive))} | "
            f"{_format_float(float(row.bloom_rate))} | {_format_int(int(row.missing_target_month))} | "
            f"{_format_int(int(row.missing_chla_in_target_month))} |"
        )

    site_horizon = bloom_counts[bloom_counts["target_rows"] > 0].groupby("horizon_months").agg(
        sites_with_target=("site_id", "count"),
        sites_with_bloom=("bloom_positive", lambda series: int((series > 0).sum())),
        sites_without_bloom=("bloom_positive", lambda series: int((series == 0).sum())),
    )
    lines.extend(
        [
            "",
            "## Bloom Site Counts",
            "",
            "| horizon | sites with target | sites with >=1 bloom | sites with 0 blooms |",
            "|---:|---:|---:|---:|",
        ]
    )
    for horizon, row in site_horizon.iterrows():
        lines.append(
            f"| {int(horizon)} | {_format_int(int(row['sites_with_target']))} | "
            f"{_format_int(int(row['sites_with_bloom']))} | {_format_int(int(row['sites_without_bloom']))} |"
        )

    lines.extend(
        [
            "",
            "## Future Chl-a By Source And Horizon",
            "",
            "| source_id | horizon | count | mean | median | p05 | p95 | max |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in dataframe_rows(chla_distribution):
        lines.append(
            f"| `{row.source_id}` | {int(row.horizon_months)} | {_format_int(int(row.count))} | "
            f"{_format_float(float(row.mean))} | {_format_float(float(row.median))} | "
            f"{_format_float(float(row.p05))} | {_format_float(float(row.p95))} | "
            f"{_format_float(float(row.max))} |"
        )

    lines.extend(
        [
            "",
            "## Absence Interpretation",
            "",
            "- Missing target month means the source-site has no row at the future calendar month.",
            "- Missing Chl-a in target month means the source-site-month exists, but no OK Chl-a monthly mean is available.",
            "- These missingness classes are operational/data-coverage missingness. They should be treated as MAR/MNAR risk until split-level diagnostics are complete; do not assume MCAR.",
            "- Targets are source-scoped; cross-source site equivalence is not assumed.",
            "",
            "## Figures",
            "",
        ]
    )
    for label, path in figures.items():
        lines.append(f"- `{label}`: `{path}`")

    lines.extend(
        [
            "",
            "## Output Tables",
            "",
        ]
    )
    for label, path in paths.items():
        lines.append(f"- `{label}`: `{path}`")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose monthly panel coverage and target availability.")
    parser.add_argument("--panel-with-targets", type=Path, default=DEFAULT_PANEL_WITH_TARGETS)
    parser.add_argument("--target-long", type=Path, default=DEFAULT_TARGET_LONG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--horizons", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_paths = {
        "coverage_by_source": args.output_dir / "coverage_by_source.csv",
        "coverage_by_site": args.output_dir / "coverage_by_site.csv",
        "coverage_by_variable": args.output_dir / "coverage_by_variable.csv",
        "coverage_by_site_variable": args.output_dir / "coverage_by_site_variable.csv",
        "coverage_by_source_variable": args.output_dir / "coverage_by_source_variable.csv",
        "bloom_counts_by_site_horizon": args.output_dir / "bloom_counts_by_site_horizon.csv",
        "target_coverage_by_source_horizon": args.output_dir / "target_coverage_by_source_horizon.csv",
        "feature_missingness": args.output_dir / "feature_missingness.csv",
        "chla_distribution_by_source_horizon": args.output_dir / "chla_distribution_by_source_horizon.csv",
    }
    existing = [path for path in [*output_paths.values(), args.report, args.manifest] if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"Output exists: {existing}. Use --overwrite to replace diagnostic outputs.")

    started_at = datetime.now(timezone.utc)
    panel = read_panel(args.panel_with_targets, args.horizons)
    print(f"loaded panel with targets ({len(panel):,} rows)", flush=True)
    target_long = read_target_long(args.target_long)
    print(f"loaded target candidates ({len(target_long):,} rows)", flush=True)

    coverage_by_source = build_coverage_by_source(panel)
    coverage_by_site = build_coverage_by_site(panel)
    coverage_by_variable = build_coverage_by_variable(panel)
    coverage_by_site_variable = build_coverage_by_site_variable(panel)
    coverage_by_source_variable = build_coverage_by_source_variable(coverage_by_site_variable)
    bloom_counts = build_bloom_counts_by_site_horizon(target_long)
    target_coverage = build_target_coverage_by_source_horizon(target_long)
    feature_missingness = build_feature_missingness(panel)
    chla_distribution = build_chla_distribution_by_source(target_long)

    frames = {
        "coverage_by_source": coverage_by_source,
        "coverage_by_site": coverage_by_site,
        "coverage_by_variable": coverage_by_variable,
        "coverage_by_site_variable": coverage_by_site_variable,
        "coverage_by_source_variable": coverage_by_source_variable,
        "bloom_counts_by_site_horizon": bloom_counts,
        "target_coverage_by_source_horizon": target_coverage,
        "feature_missingness": feature_missingness,
        "chla_distribution_by_source_horizon": chla_distribution,
    }
    for label, frame in frames.items():
        _write_csv_atomic(frame, output_paths[label])
        print(f"wrote {output_paths[label]} ({len(frame):,} rows)", flush=True)

    figures = write_figures(
        args.figure_dir,
        coverage_by_variable,
        coverage_by_source_variable,
        target_coverage,
        chla_distribution,
    )
    for path in figures.values():
        print(f"wrote {path}", flush=True)

    write_report(
        args.report,
        panel,
        target_long,
        coverage_by_source,
        coverage_by_variable,
        target_coverage,
        bloom_counts,
        chla_distribution,
        output_paths,
        figures,
    )
    manifest = {
        "status": "completed",
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "panel_with_targets": args.panel_with_targets.as_posix(),
        "target_long": args.target_long.as_posix(),
        "report": args.report.as_posix(),
        "panel_rows": int(len(panel)),
        "target_candidate_rows": int(len(target_long)),
        "target_rows": int(target_long["has_target"].sum()),
        "bloom_positive_rows": int(target_long.loc[target_long["has_target"], "bloom_h"].sum()),
        "outputs": {label: path.as_posix() for label, path in output_paths.items()},
        "figures": {label: path.as_posix() for label, path in figures.items()},
    }
    _write_json_atomic(manifest, args.manifest)
    print(f"diagnostic report written: {args.report}", flush=True)
    print(f"diagnostic manifest written: {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
