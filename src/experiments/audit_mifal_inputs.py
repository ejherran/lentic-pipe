#!/usr/bin/env python
"""Audit which MIFAL-ED/T2 inputs are observable on the frozen panel surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

from src.pandas_utils import dataframe_rows


MIFAL_INPUT_AUDIT_VERSION = "mifal_input_audit_v0"
DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_OUTPUT_DIR = Path("reports/mifal")
DEFAULT_OUTPUT_NAME = "mifal_input_audit"
OUTPUT_SUFFIXES = {
    "summary": "summary.csv",
    "by_split": "by_split.csv",
    "by_source": "by_source.csv",
    "report": "report.md",
    "manifest": "manifest.json",
}
PANEL_KEY_COLUMNS = ["source_id", "site_id", "year_month"]
SPLIT_COLUMNS = ["source_id", "site_id", "origin_year_month", "horizon_months", "split", "bloom_h", "target_risk_chla_h"]
MINIMUM_RECOMMENDED_VARIABLES = {"Tw", "TP", "Secchi", "Wind", "Chl"}


@dataclass(frozen=True)
class MIFALInputSpec:
    mifal_variable: str
    role: str
    adapter_status: str
    panel_columns: tuple[str, ...]
    panel_units: str
    mifal_units: str
    adapter_note: str


MIFAL_INPUT_SPECS = [
    MIFALInputSpec(
        "Tw",
        "minimum_temperature",
        "direct_observable",
        ("mean_temperature_C",),
        "deg C",
        "deg C",
        "Origin-month water temperature maps directly to MIFAL water temperature.",
    ),
    MIFALInputSpec(
        "TP",
        "minimum_nutrients",
        "direct_observable",
        ("mean_TP_ugL",),
        "ug/L",
        "ug/L",
        "Total phosphorus maps directly to MIFAL TP.",
    ),
    MIFALInputSpec(
        "TN",
        "optional_nutrients",
        "unit_transform_observable",
        ("mean_TN_ugL",),
        "ug/L",
        "mg/L",
        "Adapter must divide by 1000 before passing TN to MIFAL.",
    ),
    MIFALInputSpec(
        "Secchi",
        "minimum_light",
        "direct_observable",
        ("mean_secchi_depth_m",),
        "m",
        "m",
        "Secchi depth maps directly to transparency/light availability.",
    ),
    MIFALInputSpec(
        "Turb",
        "light_support",
        "direct_observable",
        ("mean_turbidity_NTU",),
        "NTU",
        "NTU",
        "Turbidity can support light limitation when Secchi is absent.",
    ),
    MIFALInputSpec(
        "DOb",
        "optional_internal_loading",
        "qualified_observable",
        ("mean_DO_mgL",),
        "mg/L",
        "mg/L",
        "Panel DO is not guaranteed to be bottom oxygen; treat as qualified evidence unless depth policy is added.",
    ),
    MIFALInputSpec(
        "Chl",
        "minimum_biological_observation",
        "direct_observable",
        ("mean_chlorophyll_a_ugL",),
        "ug/L",
        "ug/L",
        "Origin-month Chl-a can assimilate the analysis state before forecasting.",
    ),
    MIFALInputSpec(
        "Chl_prev",
        "minimum_biological_memory",
        "constructible_from_origin",
        ("mean_chlorophyll_a_ugL",),
        "ug/L",
        "ug/L",
        "First adapter can seed biological memory from origin-month Chl-a; later versions should audit explicit lags.",
    ),
    MIFALInputSpec(
        "Wind",
        "minimum_hydrodynamics",
        "unavailable_in_freeze",
        (),
        "m/s",
        "m/s",
        "No wind or mixing column is present in the current frozen monthly panel.",
    ),
    MIFALInputSpec(
        "Residence",
        "optional_hydrodynamics",
        "unavailable_in_freeze",
        (),
        "days",
        "days",
        "No lake-specific residence-time column is present in the current frozen monthly panel.",
    ),
    MIFALInputSpec(
        "Flushing",
        "optional_hydrodynamics",
        "unavailable_in_freeze",
        (),
        "day^-1",
        "day^-1",
        "No flushing-rate column is present in the current frozen monthly panel.",
    ),
    MIFALInputSpec(
        "Strat",
        "optional_hydrodynamics",
        "unavailable_in_freeze",
        (),
        "[0,1]",
        "[0,1]",
        "No stratification index is present in the current frozen monthly panel.",
    ),
    MIFALInputSpec(
        "Phyco",
        "optional_biological_proxy",
        "unavailable_in_freeze",
        (),
        "source-specific",
        "normalized_or_configured",
        "Phyco signals were reserved for future extension and are not in the current canonical panel.",
    ),
    MIFALInputSpec(
        "Sat",
        "optional_spatial_bloom_proxy",
        "unavailable_in_freeze",
        (),
        "[0,1]",
        "[0,1]",
        "Satellite bloom index is not in the current frozen monthly panel.",
    ),
    MIFALInputSpec(
        "Visual",
        "optional_qualitative_bloom_proxy",
        "unavailable_in_freeze",
        (),
        "[0,1]",
        "[0,1]",
        "Visual bloom reports are not in the current frozen monthly panel.",
    ),
    MIFALInputSpec(
        "Rain",
        "optional_runoff",
        "unavailable_in_freeze",
        (),
        "mm",
        "mm",
        "Recent precipitation is not in the current frozen monthly panel.",
    ),
    MIFALInputSpec(
        "LandLoad",
        "optional_runoff",
        "unavailable_in_freeze",
        (),
        "[0,1]",
        "[0,1]",
        "Land-load/runoff pressure is not in the current frozen monthly panel.",
    ),
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
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


def _parse_csv_list(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("At least one item is required")
    return items


def _parse_int_csv(value: str) -> list[int]:
    try:
        return [int(item) for item in _parse_csv_list(value)]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected comma-separated integers") from exc


def _safe_output_name(value: str) -> str:
    normalized = value.strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if not normalized or any(character not in allowed for character in normalized):
        raise argparse.ArgumentTypeError("Use only letters, numbers, underscores, and hyphens")
    return normalized


def _parquet_columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema.names)


def output_paths(output_dir: Path, output_name: str) -> dict[str, Path]:
    return {
        key: output_dir / f"{output_name}_{suffix}"
        for key, suffix in OUTPUT_SUFFIXES.items()
    }


def _existing_spec_columns(panel_columns: set[str]) -> list[str]:
    columns = set(PANEL_KEY_COLUMNS)
    for spec in MIFAL_INPUT_SPECS:
        columns.update(column for column in spec.panel_columns if column in panel_columns)
    return [column for column in PANEL_KEY_COLUMNS + sorted(columns - set(PANEL_KEY_COLUMNS)) if column in panel_columns]


def load_audit_surface(args: argparse.Namespace) -> pd.DataFrame:
    split_columns = set(_parquet_columns(args.splits))
    missing_split_columns = sorted(set(SPLIT_COLUMNS) - split_columns)
    if missing_split_columns:
        raise ValueError(f"Splits file is missing required columns: {missing_split_columns}")
    splits = pd.read_parquet(args.splits, columns=SPLIT_COLUMNS)
    splits = splits[splits["horizon_months"].isin(args.horizons)].copy()
    splits = splits[splits["split"].isin(args.evaluation_splits)].copy()
    if args.max_rows_per_split is not None:
        sampled: list[pd.DataFrame] = []
        for _, group in splits.groupby(["split", "horizon_months"], sort=False):
            n = min(args.max_rows_per_split, len(group))
            sampled.append(group.sample(n=n, random_state=args.random_seed))
        splits = pd.concat(sampled, ignore_index=True) if sampled else splits.iloc[0:0].copy()

    panel_columns = set(_parquet_columns(args.panel))
    missing_key_columns = sorted(set(PANEL_KEY_COLUMNS) - panel_columns)
    if missing_key_columns:
        raise ValueError(f"Panel file is missing required key columns: {missing_key_columns}")
    read_columns = _existing_spec_columns(panel_columns)
    panel = pd.read_parquet(args.panel, columns=read_columns)
    panel = panel.rename(columns={"year_month": "origin_year_month"})
    frame = splits.merge(
        panel,
        on=["source_id", "site_id", "origin_year_month"],
        how="left",
        validate="many_to_one",
    )
    numeric_columns = frame.select_dtypes(include=[np.number]).columns
    frame[numeric_columns] = frame[numeric_columns].replace([np.inf, -np.inf], np.nan)
    return frame


def _present_mask(frame: pd.DataFrame, spec: MIFALInputSpec) -> pd.Series:
    existing = [column for column in spec.panel_columns if column in frame.columns]
    if not existing:
        return pd.Series(False, index=frame.index, dtype=bool)
    return frame[existing].notna().any(axis=1)


def _coverage_row(frame: pd.DataFrame, spec: MIFALInputSpec, extra: dict[str, object] | None = None) -> dict[str, object]:
    rows = int(len(frame))
    present = int(_present_mask(frame, spec).sum()) if rows else 0
    existing_columns = [column for column in spec.panel_columns if column in frame.columns]
    status = spec.adapter_status if existing_columns else "unavailable_in_surface"
    if not spec.panel_columns:
        status = "unavailable_in_freeze"
    row: dict[str, object] = {
        "mifal_input_audit_version": MIFAL_INPUT_AUDIT_VERSION,
        "mifal_variable": spec.mifal_variable,
        "role": spec.role,
        "adapter_status": status,
        "panel_columns_expected": ",".join(spec.panel_columns),
        "panel_columns_found": ",".join(existing_columns),
        "panel_units": spec.panel_units,
        "mifal_units": spec.mifal_units,
        "rows": rows,
        "present_rows": present,
        "missing_rows": rows - present,
        "coverage_rate": float(present / rows) if rows else float("nan"),
        "adapter_note": spec.adapter_note,
    }
    if extra:
        row.update(extra)
    return row


def summarize_variables(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([_coverage_row(frame, spec) for spec in MIFAL_INPUT_SPECS])


def summarize_by_group(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if frame.empty:
        return pd.DataFrame(rows)
    for key, group in frame.groupby(group_columns, dropna=False, sort=True):
        key_values = key if isinstance(key, tuple) else (key,)
        extra = dict(zip(group_columns, key_values, strict=True))
        for spec in MIFAL_INPUT_SPECS:
            rows.append(_coverage_row(group, spec, extra))
    return pd.DataFrame(rows)


def audit_decision(summary: pd.DataFrame) -> dict[str, Any]:
    by_variable = {
        str(row.mifal_variable): float(row.coverage_rate)
        for row in dataframe_rows(summary)
        if str(row.mifal_variable) in MINIMUM_RECOMMENDED_VARIABLES
    }
    observed_minimum = [variable for variable, coverage in by_variable.items() if coverage > 0.0]
    missing_minimum = sorted(MINIMUM_RECOMMENDED_VARIABLES - set(observed_minimum))
    return {
        "minimum_recommended_variables": sorted(MINIMUM_RECOMMENDED_VARIABLES),
        "observed_minimum_variables": sorted(observed_minimum),
        "missing_minimum_variables": missing_minimum,
        "complete_minimum_surface": not missing_minimum,
        "recommended_next_gate": "build_mifal_observable_minimal_adapter" if observed_minimum else "extend_input_data_before_modeling",
    }


def write_report(args: argparse.Namespace, frame: pd.DataFrame, summary: pd.DataFrame, by_split: pd.DataFrame, decision: dict[str, Any]) -> None:
    paths = output_paths(args.output_dir, args.output_name)
    lines = [
        "# MIFAL-ED/T2 Input Audit v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Panel: `{args.panel.as_posix()}`",
        f"Splits: `{args.splits.as_posix()}`",
        f"Audit rows: `{_format_int(len(frame))}`",
        f"Horizons: `{', '.join(str(item) for item in args.horizons)}`",
        f"Evaluation splits: `{', '.join(args.evaluation_splits)}`",
        "",
        "This is an input-availability audit, not a MIFAL performance evaluation.",
        "",
        "## Gate Decision",
        "",
        f"- Complete recommended minimum surface: `{decision['complete_minimum_surface']}`",
        f"- Observed minimum variables: `{', '.join(decision['observed_minimum_variables']) or 'none'}`",
        f"- Missing minimum variables: `{', '.join(decision['missing_minimum_variables']) or 'none'}`",
        f"- Recommended next gate: `{decision['recommended_next_gate']}`",
        "",
        "The first empirical MIFAL variant should use the observable panel inputs and represent unavailable drivers through priors and low reliability, rather than fabricating hydrodynamic or meteorological covariates.",
        "",
        "## Overall Variable Coverage",
        "",
        "| MIFAL variable | role | status | found columns | rows | present rows | coverage | note |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in dataframe_rows(summary):
        lines.append(
            f"| `{row.mifal_variable}` | `{row.role}` | `{row.adapter_status}` | "
            f"`{row.panel_columns_found or 'none'}` | {_format_int(int(row.rows))} | "
            f"{_format_int(int(row.present_rows))} | {_format_float(float(row.coverage_rate))} | "
            f"{row.adapter_note} |"
        )

    lines.extend(
        [
            "",
            "## Coverage By Split",
            "",
            "| split | horizon | MIFAL variable | rows | present rows | coverage |",
            "|---|---:|---|---:|---:|---:|",
        ]
    )
    visible = by_split[by_split["mifal_variable"].isin(sorted(MINIMUM_RECOMMENDED_VARIABLES | {"TN", "Turb", "DOb"}))]
    for row in dataframe_rows(visible):
        lines.append(
            f"| `{row.split}` | {int(row.horizon_months)} | `{row.mifal_variable}` | "
            f"{_format_int(int(row.rows))} | {_format_int(int(row.present_rows))} | "
            f"{_format_float(float(row.coverage_rate))} |"
        )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Summary: `{paths['summary'].as_posix()}`",
            f"- By split: `{paths['by_split'].as_posix()}`",
            f"- By source: `{paths['by_source'].as_posix()}`",
            f"- Manifest: `{paths['manifest'].as_posix()}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), paths["report"])


def manifest_payload(args: argparse.Namespace, frame: pd.DataFrame, summary: pd.DataFrame, by_split: pd.DataFrame, by_source: pd.DataFrame, decision: dict[str, Any], started_at: datetime) -> dict[str, Any]:
    paths = output_paths(args.output_dir, args.output_name)
    return {
        "status": "completed",
        "mifal_input_audit_version": MIFAL_INPUT_AUDIT_VERSION,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": _file_record(Path(__file__)),
        "config": {
            "panel": args.panel.as_posix(),
            "splits": args.splits.as_posix(),
            "horizons": args.horizons,
            "evaluation_splits": args.evaluation_splits,
            "max_rows_per_split": args.max_rows_per_split,
            "random_seed": args.random_seed,
            "output_name": args.output_name,
        },
        "inputs": [_file_record(args.panel), _file_record(args.splits)],
        "input_specs": [asdict(spec) for spec in MIFAL_INPUT_SPECS],
        "decision": decision,
        "row_counts": {
            "audit_rows": int(len(frame)),
            "summary_rows": int(len(summary)),
            "by_split_rows": int(len(by_split)),
            "by_source_rows": int(len(by_source)),
        },
        "outputs": [_file_record(path) for key, path in paths.items() if key != "manifest" and path.exists()],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit MIFAL-ED/T2 input availability on the monthly panel and split surface.")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--horizons", type=_parse_int_csv, default="1,2,3")
    parser.add_argument("--evaluation-splits", type=_parse_csv_list, default="train,validation,test")
    parser.add_argument("--max-rows-per-split", type=int, default=None)
    parser.add_argument("--random-seed", type=int, default=1729)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-name", type=_safe_output_name, default=DEFAULT_OUTPUT_NAME)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started_at = datetime.now(timezone.utc)
    print(f"loading audit surface from {args.splits} and {args.panel}", flush=True)
    frame = load_audit_surface(args)
    print(f"audit rows: {len(frame):,}", flush=True)
    summary = summarize_variables(frame)
    by_split = summarize_by_group(frame, ["split", "horizon_months"])
    by_source = summarize_by_group(frame, ["source_id", "split", "horizon_months"])
    decision = audit_decision(summary)
    paths = output_paths(args.output_dir, args.output_name)
    _write_csv_atomic(summary, paths["summary"])
    _write_csv_atomic(by_split, paths["by_split"])
    _write_csv_atomic(by_source, paths["by_source"])
    write_report(args, frame, summary, by_split, decision)
    manifest = manifest_payload(args, frame, summary, by_split, by_source, decision, started_at)
    _write_json_atomic(manifest, paths["manifest"])
    print(f"audit report written: {paths['report']}", flush=True)
    print(f"audit manifest written: {paths['manifest']}", flush=True)


if __name__ == "__main__":
    main()
