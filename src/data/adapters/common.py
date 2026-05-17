"""Shared helpers for raw source adapters."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


CANONICAL_COLUMNS = [
    "source_id",
    "source_file",
    "source_row_id",
    "site_id_source",
    "site_id",
    "site_name",
    "sample_datetime",
    "year_month",
    "latitude",
    "longitude",
    "depth_m",
    "variable_raw",
    "variable_canonical",
    "value_raw",
    "unit_raw",
    "value_canonical",
    "unit_canonical",
    "conversion",
    "qc_flag",
    "source_quality",
    "flags_json",
]


@dataclass(frozen=True)
class ConvertedValue:
    value: float | None
    conversion: str
    qc_flag: str


@dataclass(frozen=True)
class ObservationChunk:
    frame: pd.DataFrame
    unit_id: str
    unit_index: int
    total_units: int | None = None
    raw_start: int | None = None
    raw_end: int | None = None


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def ensure_parent(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def normalize_unit(unit: Any) -> str:
    if unit is None or pd.isna(unit):
        return ""
    return str(unit).strip().replace("µ", "u")


def conversion_value(value: float, conversion: str) -> float:
    if conversion == "identity":
        return value
    if conversion == "identity_approximate":
        return value
    if conversion == "multiply_1000":
        return value * 1000.0
    if conversion == "multiply_0_3048":
        return value * 0.3048
    if conversion == "multiply_0_0254":
        return value * 0.0254
    if conversion == "fahrenheit_to_celsius":
        return (value - 32.0) * 5.0 / 9.0
    raise ValueError(f"Unsupported conversion rule: {conversion}")


def convert_canonical_value(
    value: Any,
    unit: Any,
    canonical_variable: str,
    variables_config: dict[str, Any],
) -> ConvertedValue:
    variable_config = variables_config["canonical_variables"][canonical_variable]
    raw_value = to_float(value)
    if raw_value is None:
        return ConvertedValue(None, "not_converted", "non_numeric_or_missing")

    unit_key = normalize_unit(unit)
    conversions = variable_config.get("conversions", {})
    conversion_label: str | None = None
    if canonical_variable == "pH" and unit_key == "":
        conversion = conversions.get("dimensionless")
        if conversion is not None:
            conversion_label = "assume_blank_unit_dimensionless"
    else:
        conversion = conversions.get(unit_key)
    if conversion is None:
        return ConvertedValue(None, "not_converted", f"unsupported_unit:{unit_key}")
    conversion_label = conversion_label or conversion

    converted = conversion_value(raw_value, conversion)
    impossible = variable_config.get("impossible_if", [])
    if "negative" in impossible and converted < 0:
        return ConvertedValue(None, conversion_label, "impossible_negative")

    plausible = variable_config.get("plausible_range") or {}
    min_value = plausible.get("min")
    max_value = plausible.get("max")
    if min_value is not None and converted < float(min_value):
        return ConvertedValue(converted, conversion_label, "outside_plausible_range")
    if max_value is not None and converted > float(max_value):
        return ConvertedValue(converted, conversion_label, "outside_plausible_range")
    return ConvertedValue(converted, conversion_label, "ok")


def convert_depth_m(value: Any, unit: Any) -> float | None:
    raw_value = to_float(value)
    if raw_value is None:
        return None
    unit_key = normalize_unit(unit)
    if unit_key in {"", "m", "meter", "meters"}:
        return raw_value
    if unit_key in {"ft", "feet"}:
        return raw_value * 0.3048
    if unit_key in {"in", "inch", "inches"}:
        return raw_value * 0.0254
    return None


def namespaced_site_id(source_id: str, site_id_source: Any) -> str:
    cleaned = "" if site_id_source is None or pd.isna(site_id_source) else str(site_id_source).strip()
    return f"{source_id}:{cleaned}"


def year_month_from_datetime(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, errors="coerce", utc=True).dt.strftime("%Y-%m")


def flags_to_json(flags: dict[str, Any]) -> str:
    cleaned = {
        str(key): (None if value is None or pd.isna(value) else value)
        for key, value in flags.items()
    }
    return json.dumps(cleaned, ensure_ascii=False, sort_keys=True)


def empty_canonical_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=CANONICAL_COLUMNS)


def enforce_schema(frame: pd.DataFrame) -> pd.DataFrame:
    for column in CANONICAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame[CANONICAL_COLUMNS]
