"""Adapters from the frozen monthly panel surface to MIFAL observations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Any

import pandas as pd

from src.mifal.ed_t2 import MIFALConfig, Observation


MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA = "observable_current_chla"
MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA = "observable_no_current_chla"
MIFAL_SURFACES = [
    MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA,
    MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA,
]

PANEL_KEY_COLUMNS = ["source_id", "site_id", "year_month"]
PANEL_ADAPTER_VALUE_COLUMNS = [
    "mean_temperature_C",
    "mean_TP_ugL",
    "mean_TN_ugL",
    "mean_secchi_depth_m",
    "mean_turbidity_NTU",
    "mean_DO_mgL",
    "mean_chlorophyll_a_ugL",
]
PANEL_ADAPTER_COUNT_COLUMNS = [
    "n_obs_temperature_C",
    "n_obs_TP_ugL",
    "n_obs_TN_ugL",
    "n_obs_secchi_depth_m",
    "n_obs_turbidity_NTU",
    "n_obs_DO_mgL",
    "n_obs_chlorophyll_a_ugL",
]
PANEL_ADAPTER_QC_COLUMNS = [
    "qc_ok_rate_temperature_C",
    "qc_ok_rate_TP_ugL",
    "qc_ok_rate_TN_ugL",
    "qc_ok_rate_secchi_depth_m",
    "qc_ok_rate_turbidity_NTU",
    "qc_ok_rate_DO_mgL",
    "qc_ok_rate_chlorophyll_a_ugL",
]
PANEL_ADAPTER_STD_COLUMNS = [
    "std_temperature_C",
    "std_TP_ugL",
    "std_TN_ugL",
    "std_secchi_depth_m",
    "std_turbidity_NTU",
    "std_DO_mgL",
    "std_chlorophyll_a_ugL",
]
PANEL_ADAPTER_COLUMNS = [
    *PANEL_KEY_COLUMNS,
    *PANEL_ADAPTER_VALUE_COLUMNS,
    *PANEL_ADAPTER_COUNT_COLUMNS,
    *PANEL_ADAPTER_QC_COLUMNS,
    *PANEL_ADAPTER_STD_COLUMNS,
]

PREV_CHLA_COLUMNS = [
    "prev_mean_chlorophyll_a_ugL",
    "prev_n_obs_chlorophyll_a_ugL",
    "prev_qc_ok_rate_chlorophyll_a_ugL",
    "prev_std_chlorophyll_a_ugL",
]

SOURCE_QUALITY_PRIORS = {
    "aquamatch_chla": 0.75,
    "lakebed_us_cse": 0.90,
    "nla": 0.90,
    "wqp": 0.80,
}
DEFAULT_SOURCE_QUALITY = 0.80
MIFAL_VARIABLE_BOUNDS = MIFALConfig().variable_bounds


@dataclass(frozen=True)
class PanelVariableSpec:
    mifal_variable: str
    value_column: str
    n_obs_column: str
    qc_ok_rate_column: str
    std_column: str
    source_fit: float
    age_days: float
    unit_scale: float = 1.0


CURRENT_SPECS = [
    PanelVariableSpec("Tw", "mean_temperature_C", "n_obs_temperature_C", "qc_ok_rate_temperature_C", "std_temperature_C", 1.0, 15.0),
    PanelVariableSpec("TP", "mean_TP_ugL", "n_obs_TP_ugL", "qc_ok_rate_TP_ugL", "std_TP_ugL", 1.0, 15.0),
    PanelVariableSpec("TN", "mean_TN_ugL", "n_obs_TN_ugL", "qc_ok_rate_TN_ugL", "std_TN_ugL", 0.95, 15.0, unit_scale=0.001),
    PanelVariableSpec("Secchi", "mean_secchi_depth_m", "n_obs_secchi_depth_m", "qc_ok_rate_secchi_depth_m", "std_secchi_depth_m", 1.0, 15.0),
    PanelVariableSpec("Turb", "mean_turbidity_NTU", "n_obs_turbidity_NTU", "qc_ok_rate_turbidity_NTU", "std_turbidity_NTU", 0.90, 15.0),
    PanelVariableSpec("DOb", "mean_DO_mgL", "n_obs_DO_mgL", "qc_ok_rate_DO_mgL", "std_DO_mgL", 0.55, 15.0),
    PanelVariableSpec("Chl", "mean_chlorophyll_a_ugL", "n_obs_chlorophyll_a_ugL", "qc_ok_rate_chlorophyll_a_ugL", "std_chlorophyll_a_ugL", 1.0, 15.0),
]
PREV_CHLA_SPEC = PanelVariableSpec(
    "Chl_prev",
    "prev_mean_chlorophyll_a_ugL",
    "prev_n_obs_chlorophyll_a_ugL",
    "prev_qc_ok_rate_chlorophyll_a_ugL",
    "prev_std_chlorophyll_a_ugL",
    0.90,
    45.0,
)


def validate_surface(surface: str) -> str:
    if surface not in MIFAL_SURFACES:
        raise ValueError(f"Unknown MIFAL surface {surface!r}. Expected one of {MIFAL_SURFACES!r}")
    return surface


def is_present(value: Any) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return isfinite(numeric)


def _float_or_none(value: Any) -> float | None:
    if not is_present(value):
        return None
    return float(value)


def source_quality_prior(source_id: object) -> float:
    return SOURCE_QUALITY_PRIORS.get(str(source_id), DEFAULT_SOURCE_QUALITY)


def count_quality(n_obs: float | None) -> float:
    if n_obs is None or n_obs <= 0.0:
        return 0.75
    return min(1.0, sqrt(min(n_obs, 3.0) / 3.0))


def observation_sigma(std_value: float | None, n_obs: float | None, unit_scale: float) -> float | None:
    if std_value is None or std_value < 0.0:
        return None
    if n_obs is None or n_obs <= 0.0:
        return std_value * unit_scale
    return (std_value / sqrt(max(n_obs, 1.0))) * unit_scale


def within_mifal_bounds(variable: str, value: float) -> bool:
    bounds = MIFAL_VARIABLE_BOUNDS.get(variable)
    if bounds is None:
        return True
    lo, hi = bounds
    return lo <= value <= hi


def variable_observation(row: Mapping[str, Any], spec: PanelVariableSpec) -> Observation | None:
    value = _float_or_none(row.get(spec.value_column))
    if value is None:
        return None
    scaled_value = value * spec.unit_scale
    if not within_mifal_bounds(spec.mifal_variable, scaled_value):
        return None
    n_obs = _float_or_none(row.get(spec.n_obs_column))
    qc_ok_rate = _float_or_none(row.get(spec.qc_ok_rate_column))
    std_value = _float_or_none(row.get(spec.std_column))
    source_quality = source_quality_prior(row.get("source_id")) * (qc_ok_rate if qc_ok_rate is not None else 0.75) * count_quality(n_obs)
    sigma = observation_sigma(std_value, n_obs, spec.unit_scale)
    return Observation(
        value=scaled_value,
        source_quality=source_quality,
        source_fit=spec.source_fit,
        sigma=sigma,
        age_days=spec.age_days,
        independence=1.0,
    )


def panel_row_to_mifal_payload(row: Mapping[str, Any], surface: str = MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA) -> dict[str, Observation]:
    surface = validate_surface(surface)
    payload: dict[str, Observation] = {}
    for spec in CURRENT_SPECS:
        if surface == MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA and spec.mifal_variable == "Chl":
            continue
        observation = variable_observation(row, spec)
        if observation is not None:
            payload[spec.mifal_variable] = observation
    previous_chla = variable_observation(row, PREV_CHLA_SPEC)
    if previous_chla is not None:
        payload["Chl_prev"] = previous_chla
    return payload


def payload_availability(payload: Mapping[str, Observation]) -> dict[str, bool]:
    variables = ["Tw", "TP", "TN", "Secchi", "Turb", "DOb", "Chl", "Chl_prev"]
    return {f"has_{variable}": variable in payload for variable in variables}


def add_previous_chla_columns(panel: pd.DataFrame) -> pd.DataFrame:
    required = {"source_id", "site_id", "year_month", "mean_chlorophyll_a_ugL"}
    missing = sorted(required - set(panel.columns))
    if missing:
        raise ValueError(f"Panel frame is missing previous-Chl-a columns: {missing}")
    available_columns = [
        column
        for column in [
            "source_id",
            "site_id",
            "year_month",
            "mean_chlorophyll_a_ugL",
            "n_obs_chlorophyll_a_ugL",
            "qc_ok_rate_chlorophyll_a_ugL",
            "std_chlorophyll_a_ugL",
        ]
        if column in panel.columns
    ]
    previous = panel[available_columns].copy()
    previous["origin_year_month"] = (pd.PeriodIndex(previous["year_month"].astype(str), freq="M") + 1).astype(str)
    previous = previous.drop(columns=["year_month"])
    previous = previous.rename(
        columns={
            "mean_chlorophyll_a_ugL": "prev_mean_chlorophyll_a_ugL",
            "n_obs_chlorophyll_a_ugL": "prev_n_obs_chlorophyll_a_ugL",
            "qc_ok_rate_chlorophyll_a_ugL": "prev_qc_ok_rate_chlorophyll_a_ugL",
            "std_chlorophyll_a_ugL": "prev_std_chlorophyll_a_ugL",
        }
    )
    current = panel.copy().rename(columns={"year_month": "origin_year_month"})
    return current.merge(previous, on=["source_id", "site_id", "origin_year_month"], how="left", validate="one_to_one")
