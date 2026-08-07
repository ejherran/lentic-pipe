"""Strict Closure V1 panel adapter for the M0 MIFAL comparator.

This module is intentionally independent from :mod:`src.mifal.panel_adapter`.
The historical adapter contains observed chlorophyll and ``Chl_prev`` paths;
Closure V1 instead projects a closed, physical, non-chlorophyll allowlist.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Any

import pandas as pd

from src.mifal.ed_t2 import MIFALConfig, Observation


PANEL_KEY_COLUMNS = ("source_id", "site_id", "year_month")
STRICT_MIFAL_VARIABLES = ("Tw", "TP", "TN", "Secchi", "Turb", "DOb")

PANEL_VALUE_COLUMNS = (
    "mean_temperature_C",
    "mean_TP_ugL",
    "mean_TN_ugL",
    "mean_secchi_depth_m",
    "mean_turbidity_NTU",
    "mean_DO_mgL",
)
PANEL_COUNT_COLUMNS = (
    "n_obs_temperature_C",
    "n_obs_TP_ugL",
    "n_obs_TN_ugL",
    "n_obs_secchi_depth_m",
    "n_obs_turbidity_NTU",
    "n_obs_DO_mgL",
)
PANEL_QC_COLUMNS = (
    "qc_ok_rate_temperature_C",
    "qc_ok_rate_TP_ugL",
    "qc_ok_rate_TN_ugL",
    "qc_ok_rate_secchi_depth_m",
    "qc_ok_rate_turbidity_NTU",
    "qc_ok_rate_DO_mgL",
)
PANEL_STD_COLUMNS = (
    "std_temperature_C",
    "std_TP_ugL",
    "std_TN_ugL",
    "std_secchi_depth_m",
    "std_turbidity_NTU",
    "std_DO_mgL",
)
PANEL_PHYSICAL_COLUMNS = (
    "mean_temperature_C",
    "n_obs_temperature_C",
    "qc_ok_rate_temperature_C",
    "std_temperature_C",
    "mean_TP_ugL",
    "n_obs_TP_ugL",
    "qc_ok_rate_TP_ugL",
    "std_TP_ugL",
    "mean_TN_ugL",
    "n_obs_TN_ugL",
    "qc_ok_rate_TN_ugL",
    "std_TN_ugL",
    "mean_secchi_depth_m",
    "n_obs_secchi_depth_m",
    "qc_ok_rate_secchi_depth_m",
    "std_secchi_depth_m",
    "mean_turbidity_NTU",
    "n_obs_turbidity_NTU",
    "qc_ok_rate_turbidity_NTU",
    "std_turbidity_NTU",
    "mean_DO_mgL",
    "n_obs_DO_mgL",
    "qc_ok_rate_DO_mgL",
    "std_DO_mgL",
)
PANEL_PROJECTION_COLUMNS = (*PANEL_KEY_COLUMNS, *PANEL_PHYSICAL_COLUMNS)

EVIDENCE_GROUPS: dict[str, tuple[str, ...]] = {
    "temperature": ("Tw",),
    "nutrients": ("TP", "TN"),
    "light": ("Secchi", "Turb"),
    "internal_do": ("DOb",),
}
MINIMUM_EVIDENCE_GROUPS = 2

FORBIDDEN_EXACT_COLUMNS = frozenset(
    {
        "chlorophyll_a_ugL",
        "mean_chlorophyll_a_ugL",
        "std_chlorophyll_a_ugL",
        "n_obs_chlorophyll_a_ugL",
        "n_bad_chlorophyll_a_ugL",
        "qc_ok_rate_chlorophyll_a_ugL",
        "log_chlorophyll_a",
        "risk_chla",
        "Chl",
        "Chl_prev",
        "irc1",
        "irc1_adaptive",
        "x_irc1",
        "yT",
        "sigma_T",
        "delta_yT",
        "yT_adaptive",
        "sigma_T_adaptive",
        "delta_yT_adaptive",
    }
)

SOURCE_QUALITY_WQP = 0.80
MIFAL_VARIABLE_BOUNDS = MIFALConfig().variable_bounds


class ClosureMIFALAdapterError(ValueError):
    """Raised when the strict non-chlorophyll projection is violated."""


@dataclass(frozen=True)
class ClosurePanelVariableSpec:
    mifal_variable: str
    value_column: str
    n_obs_column: str
    qc_ok_rate_column: str
    std_column: str
    source_fit: float
    age_days: float
    unit_scale: float = 1.0


CLOSURE_VARIABLE_SPECS = (
    ClosurePanelVariableSpec(
        "Tw",
        "mean_temperature_C",
        "n_obs_temperature_C",
        "qc_ok_rate_temperature_C",
        "std_temperature_C",
        1.0,
        15.0,
    ),
    ClosurePanelVariableSpec(
        "TP",
        "mean_TP_ugL",
        "n_obs_TP_ugL",
        "qc_ok_rate_TP_ugL",
        "std_TP_ugL",
        1.0,
        15.0,
    ),
    ClosurePanelVariableSpec(
        "TN",
        "mean_TN_ugL",
        "n_obs_TN_ugL",
        "qc_ok_rate_TN_ugL",
        "std_TN_ugL",
        0.95,
        15.0,
        unit_scale=0.001,
    ),
    ClosurePanelVariableSpec(
        "Secchi",
        "mean_secchi_depth_m",
        "n_obs_secchi_depth_m",
        "qc_ok_rate_secchi_depth_m",
        "std_secchi_depth_m",
        1.0,
        15.0,
    ),
    ClosurePanelVariableSpec(
        "Turb",
        "mean_turbidity_NTU",
        "n_obs_turbidity_NTU",
        "qc_ok_rate_turbidity_NTU",
        "std_turbidity_NTU",
        0.90,
        15.0,
    ),
    ClosurePanelVariableSpec(
        "DOb",
        "mean_DO_mgL",
        "n_obs_DO_mgL",
        "qc_ok_rate_DO_mgL",
        "std_DO_mgL",
        0.55,
        15.0,
    ),
)


def validate_projection(columns: Sequence[str] = PANEL_PROJECTION_COLUMNS) -> tuple[str, ...]:
    """Validate and return the one permissible physical panel projection."""
    normalized = tuple(str(column) for column in columns)
    if normalized != PANEL_PROJECTION_COLUMNS:
        raise ClosureMIFALAdapterError("Closure MIFAL panel projection drifted")
    if len(PANEL_PHYSICAL_COLUMNS) != 24 or len(set(PANEL_PHYSICAL_COLUMNS)) != 24:
        raise ClosureMIFALAdapterError("Closure MIFAL requires exactly 24 physical columns")
    if len(set(normalized)) != len(normalized):
        raise ClosureMIFALAdapterError("Closure MIFAL panel projection contains duplicates")
    forbidden = sorted(FORBIDDEN_EXACT_COLUMNS.intersection(normalized))
    lowered = "\n".join(normalized).lower()
    if forbidden or "chlorophyll" in lowered or "risk_chla" in lowered:
        raise ClosureMIFALAdapterError(
            f"Closure MIFAL projection contains forbidden chlorophyll lineage: {forbidden}"
        )
    return normalized


def project_closure_panel(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop every non-authorized panel column and preserve the fixed order."""
    projection = validate_projection()
    if not frame.columns.is_unique:
        raise ClosureMIFALAdapterError("Panel frame contains duplicate columns")
    missing = sorted(set(projection).difference(frame.columns))
    if missing:
        raise ClosureMIFALAdapterError(
            f"Panel frame is missing strict Closure MIFAL columns: {missing}"
        )
    return frame.loc[:, list(projection)].copy()


def _finite_or_none(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if isfinite(numeric) else None


def _count_quality(n_obs: float | None) -> float:
    if n_obs is None or n_obs <= 0.0:
        return 0.75
    return min(1.0, sqrt(min(n_obs, 3.0) / 3.0))


def _observation_sigma(
    std_value: float | None,
    n_obs: float | None,
    unit_scale: float,
) -> float | None:
    if std_value is None or std_value < 0.0:
        return None
    if n_obs is None or n_obs <= 0.0:
        return std_value * unit_scale
    return std_value * unit_scale / sqrt(max(n_obs, 1.0))


def _variable_observation(
    row: Mapping[str, Any],
    spec: ClosurePanelVariableSpec,
) -> Observation | None:
    value = _finite_or_none(row.get(spec.value_column))
    if value is None:
        return None
    scaled_value = value * spec.unit_scale
    bounds = MIFAL_VARIABLE_BOUNDS[spec.mifal_variable]
    if not bounds[0] <= scaled_value <= bounds[1]:
        return None
    n_obs = _finite_or_none(row.get(spec.n_obs_column))
    if n_obs is None or n_obs < 1.0:
        return None
    qc_ok_rate = _finite_or_none(row.get(spec.qc_ok_rate_column))
    std_value = _finite_or_none(row.get(spec.std_column))
    qc_quality = 0.75 if qc_ok_rate is None else min(max(qc_ok_rate, 0.0), 1.0)
    quality = SOURCE_QUALITY_WQP
    quality *= qc_quality
    quality *= _count_quality(n_obs)
    return Observation(
        value=scaled_value,
        source_quality=quality,
        source_fit=spec.source_fit,
        sigma=_observation_sigma(std_value, n_obs, spec.unit_scale),
        age_days=spec.age_days,
        independence=1.0,
    )


def panel_row_to_closure_mifal_payload(
    row: Mapping[str, Any],
) -> dict[str, Observation]:
    """Create a WQP-only payload containing six possible non-Chl variables."""
    validate_projection()
    if str(row.get("source_id")) != "wqp":
        raise ClosureMIFALAdapterError("Closure MIFAL accepts only source_id='wqp'")
    payload: dict[str, Observation] = {}
    for spec in CLOSURE_VARIABLE_SPECS:
        observation = _variable_observation(row, spec)
        if observation is not None:
            payload[spec.mifal_variable] = observation
    unknown = sorted(set(payload).difference(STRICT_MIFAL_VARIABLES))
    if unknown:
        raise ClosureMIFALAdapterError(
            f"Closure MIFAL payload contains unauthorized variables: {unknown}"
        )
    return payload


def observed_evidence_groups(payload: Mapping[str, Observation]) -> tuple[str, ...]:
    """Return ecological evidence groups represented by at least one variable."""
    variables = set(payload)
    return tuple(
        group
        for group, members in EVIDENCE_GROUPS.items()
        if variables.intersection(members)
    )


def payload_is_eligible(payload: Mapping[str, Observation]) -> bool:
    """Require at least two distinct ecological evidence groups."""
    return len(observed_evidence_groups(payload)) >= MINIMUM_EVIDENCE_GROUPS


validate_projection()
