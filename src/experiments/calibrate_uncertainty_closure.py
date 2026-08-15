"""Pure E8 audit of pre-E0-U locked conformal uncertainty factors.

The component never receives calibration rows and never fits or adjusts a
conformal factor. It consumes the exact 90 ``q_c`` records published by the
2021 calibration lock, applies them to the sealed WQP location-holdout surface,
and returns in-memory artifact envelopes to the transaction-owning runner.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import numpy as np
import pandas as pd

from src.experiments.evaluate_anfis_ablation import (
    ClosureAnfisAblationError,
    artifact_envelope,
    validate_batch_context,
    validate_component_boundary,
)


COMPONENT_ID = "E8_uncertainty"
STAGE_ID = "E8"
NOMINAL_LEVELS = (0.80, 0.90, 0.95)
PRIMARY_NOMINAL = 0.90
MINIMUM_GROUP_ROWS = 30
SCALE_FLOOR = 1e-6
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
HORIZONS_MONTHS = (1, 2, 3)
UNCERTAINTY_MODEL_IDS = ("A0", "A1")
ZERO_SLOT_MODEL_IDS = ("A2",)
SURFACE_ID = "closure_v1_primary"
ENDPOINT = "target_risk_chla_h"
TERMINAL_STATUSES = (
    "success",
    "input_ineligible",
    "target_unavailable",
    "model_unavailable",
    "numerical_failure",
    "infrastructure_failure",
)
GAUSSIAN_FACTORS = MappingProxyType(
    {
        0.80: 1.2815515655446004,
        0.90: 1.6448536269514722,
        0.95: 1.959963984540054,
    }
)
EVALUATION_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "common_origin_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "evaluation_cohort",
    "evaluation_role",
    "model_id",
    "model_seed",
    "seed_slot",
    "status",
    "y_true",
    "prediction",
    "sigma",
)
OPTIONAL_STRATUM_COLUMNS = (
    "nutrient_evidence_quartile",
    "input_missingness_quartile",
    "location_input_frequency",
    "location_novelty",
    "degradation_scenario",
)
LOCKED_FACTOR_COLUMNS = (
    "model_id",
    "model_seed",
    "horizon_months",
    "coverage_level",
    "calibration_year",
    "finite_rows",
    "order_statistic_rank",
    "q_c",
    "status",
)
FACTOR_KEY_COLUMNS = (
    "model_id",
    "model_seed",
    "horizon_months",
    "coverage_level",
)
LEDGER_GROUP_COLUMNS = (
    "model_id",
    "surface_id",
    "endpoint",
    "horizon_months",
    "model_seed",
    "seed_slot",
    "nominal_coverage",
)
FAILURE_COUNT_COLUMNS = tuple(
    f"{status}_row_count" for status in TERMINAL_STATUSES if status != "success"
)
LEDGER_COLUMNS = (
    *LEDGER_GROUP_COLUMNS,
    "interval_version",
    "attempted_row_count",
    "success_row_count",
    "interval_row_count",
    *FAILURE_COUNT_COLUMNS,
    "location_count",
    "empirical_coverage",
    "absolute_coverage_error",
    "mean_interval_width",
    "median_interval_width",
    "winkler_interval_score",
    "brier_score",
    "status",
    "calibration_verdict",
)
COMPARISON_COLUMNS = (
    "record_type",
    "hypothesis_id",
    "hypothesis_family",
    "analysis_role",
    *LEDGER_GROUP_COLUMNS,
    "attempted_row_count",
    "paired_row_count",
    "mean_winkler_delta_after_minus_before",
    "q_c",
    "effect_estimate",
    "ci_lower",
    "ci_upper",
    "p_value",
    "holm_family_size",
    "status",
    "unavailable_reason",
)
CONDITIONAL_BASE_COLUMNS = (
    "model_id",
    "surface_id",
    "endpoint",
    "model_seed",
    "seed_slot",
    "nominal_coverage",
)
CONDITIONAL_COLUMNS = (
    *CONDITIONAL_BASE_COLUMNS,
    "breakdown_id",
    "stratum",
    "attempted_row_count",
    "success_row_count",
    "failure_row_count",
    "location_count",
    "empirical_coverage",
    "absolute_coverage_error",
    "mean_interval_width",
    "median_interval_width",
    "winkler_interval_score",
    "status",
)
RELIABILITY_COLUMNS = (
    "model_id",
    "model_seed",
    "seed_slot",
    "horizon_months",
    "bin_id",
    "row_count",
    "mean_prediction",
    "observed_frequency",
)
OUTPUT_PATHS = (
    "reports/closure_v1/08_uncertainty/uncertainty_ledger.csv",
    "reports/closure_v1/08_uncertainty/conditional_coverage.csv",
    "reports/closure_v1/08_uncertainty/recalibration_comparison.csv",
    "reports/closure_v1/08_uncertainty/reliability_bins.csv",
    "reports/closure_v1/08_uncertainty/uncertainty_report.md",
)
COMPONENT_CONTRACT = MappingProxyType(
    {
        "schema_version": "closure_e8_uncertainty_component_v2",
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "locked_factor_table": "locked_conformal_factors",
        "calibration_table": "forbidden",
        "evaluation_table": "uncertainty_evaluation",
        "locked_factor_columns": list(LOCKED_FACTOR_COLUMNS),
        "locked_factor_count": 90,
        "locked_factor_models": list(UNCERTAINTY_MODEL_IDS),
        "locked_factor_calibration_year": 2021,
        "locked_factor_finite_rows": 224,
        "nominal_levels": list(NOMINAL_LEVELS),
        "registered_seeds": list(REGISTERED_SEEDS),
        "horizons_months": list(HORIZONS_MONTHS),
        "uncertainty_applicable_models": list(UNCERTAINTY_MODEL_IDS),
        "zero_slot_models": list(ZERO_SLOT_MODEL_IDS),
        "evaluation_columns": list(EVALUATION_COLUMNS),
        "evaluation_cohort": "location_holdout",
        "evaluation_role": "test",
        "outcome_boundary": "target_year_month_after_2021_12",
        "minimum_group_rows": MINIMUM_GROUP_ROWS,
        "scale_floor": SCALE_FLOOR,
        "raw_interval": "mu_plus_or_minus_locked_native_gaussian_factor_times_sigma",
        "locked_interval": "mu_plus_or_minus_pre_e0_u_q_c_times_sigma",
        "q_fit_or_recompute_during_batch": "forbidden",
        "q_refit_within_conditional_strata": "forbidden",
        "always_required_conditional_breakdowns": [
            "global",
            "horizon",
            "predicted_risk_band",
        ],
        "required_when_input_stratum_is_present": list(OPTIONAL_STRATUM_COLUMNS),
        "conditional_metrics": [
            "empirical_coverage",
            "absolute_coverage_error",
            "mean_interval_width",
            "median_interval_width",
            "winkler_interval_score",
        ],
        "confirmatory_family_E": {
            "hypothesis_id": "H_E_uncertainty_before_vs_after_recalibration",
            "model_id": "P1",
            "nominal_coverage": PRIMARY_NOMINAL,
            "holm_family_size": 1,
            "availability": "not_estimable_model_unavailable",
            "replacement": "forbidden",
        },
        "output_paths": list(OUTPUT_PATHS),
        "pure_in_memory": True,
    }
)


class ClosureUncertaintyError(RuntimeError):
    """Raised when E8 inputs or the locked conformal contract drift."""


def _plain_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _plain_json(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def component_contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_canonical_json_bytes(COMPONENT_CONTRACT)))


def component_contract_sha256() -> str:
    return hashlib.sha256(_canonical_json_bytes(COMPONENT_CONTRACT)).hexdigest()


def _boundary(
    authority: Mapping[str, Any], sealed_batch_contract: Mapping[str, Any]
) -> str:
    try:
        return validate_component_boundary(
            authority,
            sealed_batch_contract,
            component_id=COMPONENT_ID,
            stage_id=STAGE_ID,
            output_paths=OUTPUT_PATHS,
        )
    except ClosureAnfisAblationError as exc:
        raise ClosureUncertaintyError(str(exc)) from exc


def _exact_integer(frame: pd.DataFrame, column: str, *, name: str) -> pd.Series:
    numeric = pd.to_numeric(frame[column], errors="coerce")
    values = numeric.to_numpy(dtype="float64")
    if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise ClosureUncertaintyError(f"{name} {column} is not exact integer")
    return numeric.astype("int64")


def normalize_locked_conformal_factors(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate the exact 90 published records without deriving a new ``q_c``."""

    if tuple(frame.columns) != LOCKED_FACTOR_COLUMNS:
        raise ClosureUncertaintyError("locked_conformal_factors columns are not exact")
    out = frame.copy(deep=True)
    out["model_id"] = out["model_id"].astype(str)
    out["status"] = out["status"].astype(str)
    for column in (
        "model_seed",
        "horizon_months",
        "calibration_year",
        "finite_rows",
        "order_statistic_rank",
    ):
        out[column] = _exact_integer(out, column, name="locked_conformal_factors")
    for column in ("coverage_level", "q_c"):
        raw = out[column]
        numeric = pd.to_numeric(raw, errors="coerce")
        if bool((raw.notna() & numeric.isna()).any()) or not np.isfinite(
            numeric.to_numpy(dtype="float64")
        ).all():
            raise ClosureUncertaintyError(
                f"locked_conformal_factors {column} is not finite numeric"
            )
        out[column] = numeric.astype("float64")
    out["coverage_level"] = out["coverage_level"].round(2)
    expected_keys = {
        (model_id, seed, horizon, nominal)
        for model_id in UNCERTAINTY_MODEL_IDS
        for seed in REGISTERED_SEEDS
        for horizon in HORIZONS_MONTHS
        for nominal in NOMINAL_LEVELS
    }
    observed_keys = set(
        out.loc[:, list(FACTOR_KEY_COLUMNS)].itertuples(index=False, name=None)
    )
    if (
        len(out) != 90
        or out.duplicated(list(FACTOR_KEY_COLUMNS)).any()
        or observed_keys != expected_keys
        or not out["calibration_year"].eq(2021).all()
        or not out["finite_rows"].eq(224).all()
        or not out["status"].eq("completed").all()
        or not out["q_c"].gt(0.0).all()
    ):
        raise ClosureUncertaintyError("locked_conformal_factors exact90 registry drifted")
    expected_rank = np.minimum(
        out["finite_rows"].to_numpy(dtype="int64"),
        np.ceil(
            (out["finite_rows"].to_numpy(dtype="float64") + 1.0)
            * out["coverage_level"].to_numpy(dtype="float64")
        ).astype("int64"),
    )
    if not np.array_equal(
        out["order_statistic_rank"].to_numpy(dtype="int64"), expected_rank
    ):
        raise ClosureUncertaintyError("locked conformal order-statistic metadata drifted")
    monotone = (
        out.sort_values(
            ["model_id", "model_seed", "horizon_months", "coverage_level"],
            kind="mergesort",
        )
        .groupby(["model_id", "model_seed", "horizon_months"], sort=True)["q_c"]
        .apply(
            lambda values: bool(
                np.all(np.diff(values.to_numpy(dtype="float64")) > 0.0)
            )
        )
    )
    if not monotone.all():
        raise ClosureUncertaintyError("locked conformal factors are not level-monotone")
    return out.sort_values(list(FACTOR_KEY_COLUMNS), kind="mergesort").reset_index(
        drop=True
    )


def _normalize_evaluation(frame: pd.DataFrame) -> pd.DataFrame:
    columns = tuple(frame.columns)
    if columns[: len(EVALUATION_COLUMNS)] != EVALUATION_COLUMNS:
        raise ClosureUncertaintyError("uncertainty_evaluation core columns are not exact")
    extras = columns[len(EVALUATION_COLUMNS) :]
    if len(extras) != len(set(extras)) or not set(extras).issubset(
        OPTIONAL_STRATUM_COLUMNS
    ):
        raise ClosureUncertaintyError("uncertainty_evaluation strata columns drifted")
    out = frame.copy(deep=True)
    text_columns = (
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "origin_year_month",
        "target_year_month",
        "evaluation_cohort",
        "evaluation_role",
        "model_id",
        "status",
        *extras,
    )
    for column in text_columns:
        if out[column].isna().any():
            raise ClosureUncertaintyError(
                f"uncertainty_evaluation text field is null: {column}"
            )
        out[column] = out[column].astype(str)
        if out[column].str.len().eq(0).any():
            raise ClosureUncertaintyError(
                f"uncertainty_evaluation text field is empty: {column}"
            )
    for column in ("horizon_months", "model_seed", "seed_slot"):
        out[column] = _exact_integer(out, column, name="uncertainty_evaluation")
    for column in ("y_true", "prediction", "sigma"):
        raw = out[column]
        numeric = pd.to_numeric(raw, errors="coerce")
        if bool((raw.notna() & numeric.isna()).any()):
            raise ClosureUncertaintyError(
                f"uncertainty_evaluation {column} contains a nonnumeric value"
            )
        out[column] = numeric.astype("float64")
    if (
        out.empty
        or not out["source_id"].eq("wqp").all()
        or not out["evaluation_cohort"].eq("location_holdout").all()
        or not out["evaluation_role"].eq("test").all()
        or set(out["model_id"]) != set(UNCERTAINTY_MODEL_IDS)
        or not out["model_seed"].isin(REGISTERED_SEEDS).all()
        or not out["seed_slot"].isin(REGISTERED_SEEDS).all()
        or not out["model_seed"].eq(out["seed_slot"]).all()
        or not out["horizon_months"].isin(HORIZONS_MONTHS).all()
        or not out["status"].isin(TERMINAL_STATUSES).all()
        or out["model_id"].isin(ZERO_SLOT_MODEL_IDS).any()
    ):
        raise ClosureUncertaintyError("uncertainty_evaluation locked scope drifted")
    if not out["common_origin_id"].str.fullmatch(r"[0-9a-f]{64}").all():
        raise ClosureUncertaintyError("uncertainty_evaluation common-origin id drifted")
    try:
        origins = pd.PeriodIndex(out["origin_year_month"], freq="M")
        targets = pd.PeriodIndex(out["target_year_month"], freq="M")
    except (TypeError, ValueError) as exc:
        raise ClosureUncertaintyError("uncertainty_evaluation month dialect drifted") from exc
    horizons = out["horizon_months"].to_numpy(dtype="int64")
    expected_targets = pd.PeriodIndex(
        [origin + int(horizon) for origin, horizon in zip(origins, horizons, strict=True)],
        freq="M",
    )
    if not targets.equals(expected_targets) or not (
        targets > pd.Period("2021-12", freq="M")
    ).all():
        raise ClosureUncertaintyError("uncertainty_evaluation target-time boundary drifted")
    identity = [
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
        "evaluation_cohort",
        "evaluation_role",
    ]
    exact_key = [*identity, "model_id", "model_seed", "seed_slot"]
    if out.duplicated(exact_key).any():
        raise ClosureUncertaintyError("uncertainty_evaluation exact rows are duplicated")
    expected_pairs = {
        (model_id, seed)
        for model_id in UNCERTAINTY_MODEL_IDS
        for seed in REGISTERED_SEEDS
    }
    pair_sets = out.groupby(identity, sort=True).apply(
        lambda group: set(zip(group["model_id"], group["seed_slot"], strict=True)),
        include_groups=False,
    )
    if any(pairs != expected_pairs for pairs in pair_sets):
        raise ClosureUncertaintyError(
            "uncertainty_evaluation omits an A0/A1 registered seed intent"
        )
    origin_identity = [
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "origin_year_month",
        "evaluation_cohort",
        "evaluation_role",
    ]
    horizon_sets = (
        out.loc[:, [*origin_identity, "horizon_months"]]
        .drop_duplicates()
        .groupby(origin_identity, sort=True)["horizon_months"]
        .apply(set)
    )
    if any(horizons_seen != set(HORIZONS_MONTHS) for horizons_seen in horizon_sets):
        raise ClosureUncertaintyError("uncertainty_evaluation origin horizon set drifted")
    common_mapping = out.groupby("common_origin_id", sort=True)[
        [
            "source_id",
            "site_id",
            "holdout_group_id",
            "origin_year_month",
            "evaluation_cohort",
            "evaluation_role",
        ]
    ].nunique()
    if bool((common_mapping.to_numpy(dtype="int64") > 1).any()):
        raise ClosureUncertaintyError("uncertainty_evaluation common-origin mapping drifted")
    for column in extras:
        if out.groupby(identity, sort=True)[column].nunique(dropna=False).gt(1).any():
            raise ClosureUncertaintyError(
                f"uncertainty_evaluation stratum drifts within intent: {column}"
            )
    success = out["status"].eq("success")
    successful_values = out.loc[success, ["y_true", "prediction", "sigma"]]
    if (
        not np.isfinite(successful_values.to_numpy(dtype="float64")).all()
        or not out.loc[success, "y_true"].between(0.0, 1.0, inclusive="both").all()
        or not out.loc[success, "prediction"].between(
            0.0, 1.0, inclusive="both"
        ).all()
        or not out.loc[success, "sigma"].gt(0.0).all()
    ):
        raise ClosureUncertaintyError("uncertainty_evaluation successful values drifted")
    if out.loc[~success, ["prediction", "sigma"]].notna().any().any():
        raise ClosureUncertaintyError(
            "uncertainty_evaluation non-success row contains invented uncertainty values"
        )
    target_unavailable = out["status"].eq("target_unavailable")
    target_present = out["y_true"].notna()
    if (
        out.loc[target_unavailable, "y_true"].notna().any()
        or (
            target_present
            & (
                ~np.isfinite(out["y_true"])
                | ~out["y_true"].between(0.0, 1.0, inclusive="both")
            )
        ).any()
    ):
        raise ClosureUncertaintyError("uncertainty_evaluation target nullability drifted")
    target_presence = out.assign(_target_present=target_present).groupby(
        identity, sort=True
    )["_target_present"].nunique()
    target_values = out.groupby(identity, sort=True)["y_true"].nunique(dropna=True)
    if target_presence.gt(1).any() or target_values.gt(1).any():
        raise ClosureUncertaintyError("uncertainty_evaluation target drifts within intent")
    return out.sort_values(exact_key, kind="mergesort").reset_index(drop=True)


def _validate_availability(
    evaluation: pd.DataFrame, availability: Mapping[str, Any]
) -> None:
    expected = {
        "A0": "available",
        "A1": "available",
        "A2": "unavailable",
        "P1": "unavailable",
    }
    if any(availability.get(model_id) != status for model_id, status in expected.items()):
        raise ClosureUncertaintyError("sealed uncertainty model availability drifted")
    if set(evaluation["model_id"]) != {"A0", "A1"}:
        raise ClosureUncertaintyError("uncertainty evaluation model universe drifted")
    if evaluation["status"].eq("model_unavailable").any():
        raise ClosureUncertaintyError("available uncertainty model was marked unavailable")


def apply_locked_conformal_factors(
    evaluation: pd.DataFrame, factors: pd.DataFrame
) -> pd.DataFrame:
    """Expand nominal levels and apply only the supplied locked ``q_c`` values."""

    nominal = pd.DataFrame({"nominal_coverage": list(NOMINAL_LEVELS)})
    expanded = evaluation.merge(nominal, how="cross", validate="many_to_many")
    factor_view = factors.rename(columns={"coverage_level": "nominal_coverage"})
    expanded = expanded.merge(
        factor_view,
        on=["model_id", "model_seed", "horizon_months", "nominal_coverage"],
        how="left",
        validate="many_to_one",
        suffixes=("", "_factor"),
        indicator="_factor_merge",
    )
    if not expanded["_factor_merge"].eq("both").all():
        raise ClosureUncertaintyError("uncertainty evaluation lacks a locked q_c binding")
    expanded = expanded.drop(columns="_factor_merge")
    expanded["surface_id"] = SURFACE_ID
    expanded["endpoint"] = ENDPOINT
    success = expanded["status"].eq("success")
    gaussian = expanded["nominal_coverage"].map(GAUSSIAN_FACTORS)
    raw_half_width = gaussian * expanded["sigma"]
    locked_half_width = expanded["q_c"] * expanded["sigma"]
    expanded["raw_lower"] = np.where(
        success, expanded["prediction"] - raw_half_width, np.nan
    )
    expanded["raw_upper"] = np.where(
        success, expanded["prediction"] + raw_half_width, np.nan
    )
    expanded["locked_lower"] = np.where(
        success, expanded["prediction"] - locked_half_width, np.nan
    )
    expanded["locked_upper"] = np.where(
        success, expanded["prediction"] + locked_half_width, np.nan
    )
    generated = ["raw_lower", "raw_upper", "locked_lower", "locked_upper"]
    if (
        not np.isfinite(
            expanded.loc[success, generated].to_numpy(dtype="float64")
        ).all()
        or expanded.loc[~success, generated].notna().any().any()
    ):
        raise ClosureUncertaintyError("uncertainty interval application drifted")
    return expanded


def _winkler(
    y: np.ndarray, lower: np.ndarray, upper: np.ndarray, nominal: float
) -> np.ndarray:
    alpha = 1.0 - nominal
    score = upper - lower
    score = score + np.where(y < lower, (2.0 / alpha) * (lower - y), 0.0)
    return score + np.where(y > upper, (2.0 / alpha) * (y - upper), 0.0)


def _group_status(group: pd.DataFrame, interval_count: int) -> str:
    if interval_count:
        return "available"
    for status in (
        "target_unavailable",
        "input_ineligible",
        "numerical_failure",
        "infrastructure_failure",
    ):
        if group["status"].eq(status).all():
            return status
    return "no_successful_rows"


def _interval_metrics(
    group: pd.DataFrame,
    *,
    lower_column: str,
    upper_column: str,
    nominal_coverage: float | None = None,
) -> dict[str, Any]:
    y = group["y_true"].to_numpy(dtype="float64")
    lower = group[lower_column].to_numpy(dtype="float64")
    upper = group[upper_column].to_numpy(dtype="float64")
    valid = np.isfinite(y) & np.isfinite(lower) & np.isfinite(upper)
    nominal_values = group["nominal_coverage"].unique()
    if len(nominal_values) == 1:
        nominal = float(nominal_values[0])
    elif len(nominal_values) == 0 and nominal_coverage in NOMINAL_LEVELS:
        nominal = float(nominal_coverage)
    else:
        raise ClosureUncertaintyError("uncertainty metric nominal group drifted")
    coverage = (
        float(np.mean((y[valid] >= lower[valid]) & (y[valid] <= upper[valid])))
        if valid.any()
        else math.nan
    )
    width = upper[valid] - lower[valid]
    winkler = (
        _winkler(y[valid], lower[valid], upper[valid], nominal)
        if valid.any()
        else np.array([], dtype="float64")
    )
    prediction = group["prediction"].to_numpy(dtype="float64")
    binary = (
        valid
        & np.isin(y, (0.0, 1.0))
        & (prediction >= 0.0)
        & (prediction <= 1.0)
    )
    return {
        "valid": valid,
        "interval_row_count": int(valid.sum()),
        "empirical_coverage": coverage,
        "absolute_coverage_error": (
            abs(coverage - nominal) if math.isfinite(coverage) else math.nan
        ),
        "mean_interval_width": float(np.mean(width)) if width.size else math.nan,
        "median_interval_width": float(np.median(width)) if width.size else math.nan,
        "winkler_interval_score": (
            float(np.mean(winkler)) if winkler.size else math.nan
        ),
        "brier_score": (
            float(np.mean(np.square(prediction[binary] - y[binary])))
            if binary.any()
            else math.nan
        ),
    }


def _summary_rows(applied: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ledger: list[dict[str, Any]] = []
    comparison: list[dict[str, Any]] = []
    for raw_group_key, group in applied.groupby(
        list(LEDGER_GROUP_COLUMNS), sort=True, dropna=False
    ):
        group_key = cast(tuple[Any, ...], raw_group_key)
        group_values = dict(zip(LEDGER_GROUP_COLUMNS, group_key, strict=True))
        for version, lower_column, upper_column in (
            ("raw_gaussian", "raw_lower", "raw_upper"),
            ("locked_conformal", "locked_lower", "locked_upper"),
        ):
            metrics = _interval_metrics(
                group, lower_column=lower_column, upper_column=upper_column
            )
            valid = cast(np.ndarray, metrics["valid"])
            coverage_error = cast(float, metrics["absolute_coverage_error"])
            ledger.append(
                {
                    **group_values,
                    "interval_version": version,
                    "attempted_row_count": int(len(group)),
                    "success_row_count": int(group["status"].eq("success").sum()),
                    "interval_row_count": metrics["interval_row_count"],
                    **{
                        column: int(
                            group["status"].eq(column.removesuffix("_row_count")).sum()
                        )
                        for column in FAILURE_COUNT_COLUMNS
                    },
                    "location_count": int(
                        group.loc[valid, ["source_id", "site_id"]]
                        .drop_duplicates()
                        .shape[0]
                    ),
                    "empirical_coverage": metrics["empirical_coverage"],
                    "absolute_coverage_error": coverage_error,
                    "mean_interval_width": metrics["mean_interval_width"],
                    "median_interval_width": metrics["median_interval_width"],
                    "winkler_interval_score": metrics["winkler_interval_score"],
                    "brier_score": metrics["brier_score"],
                    "status": _group_status(
                        group, cast(int, metrics["interval_row_count"])
                    ),
                    "calibration_verdict": (
                        "calibrated"
                        if math.isfinite(coverage_error) and coverage_error <= 0.05
                        else (
                            "not_uniformly_calibrated"
                            if math.isfinite(coverage_error)
                            else "not_estimable"
                        )
                    ),
                }
            )
        success = group["status"].eq("success").to_numpy(dtype=bool)
        y = group["y_true"].to_numpy(dtype="float64")
        nominal = float(group_values["nominal_coverage"])
        raw_score = _winkler(
            y[success],
            group.loc[success, "raw_lower"].to_numpy(dtype="float64"),
            group.loc[success, "raw_upper"].to_numpy(dtype="float64"),
            nominal,
        )
        locked_score = _winkler(
            y[success],
            group.loc[success, "locked_lower"].to_numpy(dtype="float64"),
            group.loc[success, "locked_upper"].to_numpy(dtype="float64"),
            nominal,
        )
        delta = locked_score - raw_score
        comparison.append(
            {
                "record_type": "descriptive_locked_q_group",
                "hypothesis_id": "",
                "hypothesis_family": "",
                "analysis_role": "descriptive",
                **group_values,
                "attempted_row_count": int(len(group)),
                "paired_row_count": int(len(delta)),
                "mean_winkler_delta_after_minus_before": (
                    float(np.mean(delta)) if len(delta) else math.nan
                ),
                "q_c": float(group["q_c"].iloc[0]),
                "effect_estimate": math.nan,
                "ci_lower": math.nan,
                "ci_upper": math.nan,
                "p_value": math.nan,
                "holm_family_size": 0,
                "status": "available" if len(delta) else "no_successful_rows",
                "unavailable_reason": "",
            }
        )
    origin_count = applied[
        [
            "source_id",
            "site_id",
            "holdout_group_id",
            "common_origin_id",
            "origin_year_month",
        ]
    ].drop_duplicates().shape[0]
    comparison.append(
        {
            "record_type": "confirmatory_hypothesis",
            "hypothesis_id": "H_E_uncertainty_before_vs_after_recalibration",
            "hypothesis_family": "E",
            "analysis_role": "confirmatory",
            "model_id": "P1",
            "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
            "endpoint": "yN;yF;yT",
            "horizon_months": math.nan,
            "model_seed": math.nan,
            "seed_slot": math.nan,
            "nominal_coverage": PRIMARY_NOMINAL,
            "attempted_row_count": int(origin_count * 3 * 3 * len(REGISTERED_SEEDS)),
            "paired_row_count": 0,
            "mean_winkler_delta_after_minus_before": math.nan,
            "q_c": math.nan,
            "effect_estimate": math.nan,
            "ci_lower": math.nan,
            "ci_upper": math.nan,
            "p_value": math.nan,
            "holm_family_size": 1,
            "status": "not_estimable_model_unavailable",
            "unavailable_reason": "P1_model_unavailable_no_substitution",
        }
    )
    return (
        pd.DataFrame(ledger, columns=LEDGER_COLUMNS),
        pd.DataFrame(comparison, columns=COMPARISON_COLUMNS),
    )


def _conditional_record(
    group: pd.DataFrame,
    base_values: Mapping[str, Any],
    *,
    breakdown_id: str,
    stratum: str,
) -> dict[str, Any]:
    metrics = _interval_metrics(
        group,
        lower_column="locked_lower",
        upper_column="locked_upper",
        nominal_coverage=float(base_values["nominal_coverage"]),
    )
    valid = cast(np.ndarray, metrics["valid"])
    interval_rows = cast(int, metrics["interval_row_count"])
    enough = interval_rows >= MINIMUM_GROUP_ROWS
    return {
        **dict(base_values),
        "breakdown_id": breakdown_id,
        "stratum": stratum,
        "attempted_row_count": int(len(group)),
        "success_row_count": int(group["status"].eq("success").sum()),
        "failure_row_count": int(group["status"].ne("success").sum()),
        "location_count": int(
            group.loc[valid, ["source_id", "site_id"]].drop_duplicates().shape[0]
        ),
        "empirical_coverage": metrics["empirical_coverage"] if enough else math.nan,
        "absolute_coverage_error": (
            metrics["absolute_coverage_error"] if enough else math.nan
        ),
        "mean_interval_width": metrics["mean_interval_width"] if enough else math.nan,
        "median_interval_width": (
            metrics["median_interval_width"] if enough else math.nan
        ),
        "winkler_interval_score": (
            metrics["winkler_interval_score"] if enough else math.nan
        ),
        "status": "available" if enough else "insufficient_support",
    }


def _conditional_rows(applied: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    risk_labels = ("[0,.25)", "[.25,.5)", "[.5,.75)", "[.75,1]")
    for raw_base_key, base in applied.groupby(
        list(CONDITIONAL_BASE_COLUMNS), sort=True, dropna=False
    ):
        base_key = cast(tuple[Any, ...], raw_base_key)
        base_values = dict(zip(CONDITIONAL_BASE_COLUMNS, base_key, strict=True))
        rows.append(
            _conditional_record(
                base, base_values, breakdown_id="global", stratum="all"
            )
        )
        for horizon in HORIZONS_MONTHS:
            rows.append(
                _conditional_record(
                    base.loc[base["horizon_months"].eq(horizon)],
                    base_values,
                    breakdown_id="horizon",
                    stratum=str(horizon),
                )
            )
        risk = pd.to_numeric(base["prediction"], errors="coerce")
        bands = pd.cut(
            risk,
            bins=[0.0, 0.25, 0.5, 0.75, 1.0],
            right=False,
            include_lowest=True,
            labels=list(risk_labels),
        ).astype("object")
        bands.loc[risk.eq(1.0)] = risk_labels[-1]
        for label in risk_labels:
            rows.append(
                _conditional_record(
                    base.loc[bands.eq(label)],
                    base_values,
                    breakdown_id="predicted_risk_band",
                    stratum=label,
                )
            )
        unavailable_risk = bands.isna()
        if unavailable_risk.any():
            rows.append(
                _conditional_record(
                    base.loc[unavailable_risk],
                    base_values,
                    breakdown_id="predicted_risk_band",
                    stratum="not_available",
                )
            )
        for column in OPTIONAL_STRATUM_COLUMNS:
            if column not in base:
                continue
            for label in sorted(base[column].astype(str).unique()):
                rows.append(
                    _conditional_record(
                        base.loc[base[column].astype(str).eq(label)],
                        base_values,
                        breakdown_id=column,
                        stratum=label,
                    )
                )
    result = pd.DataFrame(rows, columns=CONDITIONAL_COLUMNS)
    required = {"global", "horizon", "predicted_risk_band"}.union(
        column for column in OPTIONAL_STRATUM_COLUMNS if column in applied
    )
    if set(result["breakdown_id"]) != required:
        raise ClosureUncertaintyError("E8 conditional breakdown coverage drifted")
    return result


def _reliability_rows(evaluation: pd.DataFrame) -> pd.DataFrame:
    frame = evaluation.loc[evaluation["status"].eq("success")].copy()
    frame = frame.loc[
        frame["y_true"].isin([0.0, 1.0])
        & frame["prediction"].between(0.0, 1.0, inclusive="both")
    ]
    if frame.empty:
        return pd.DataFrame(columns=RELIABILITY_COLUMNS)
    frame["bin_id"] = np.minimum((frame["prediction"] * 10).astype(int), 9)
    return (
        frame.groupby(
            ["model_id", "model_seed", "seed_slot", "horizon_months", "bin_id"],
            sort=True,
        )
        .agg(
            row_count=("y_true", "size"),
            mean_prediction=("prediction", "mean"),
            observed_frequency=("y_true", "mean"),
        )
        .reset_index()
        .loc[:, list(RELIABILITY_COLUMNS)]
    )


def _report(
    ledger: pd.DataFrame,
    factors: pd.DataFrame,
    conditional: pd.DataFrame,
    comparison: pd.DataFrame,
) -> str:
    primary = ledger.loc[
        ledger["nominal_coverage"].eq(PRIMARY_NOMINAL)
        & ledger["interval_version"].eq("locked_conformal")
    ]
    calibrated = int(primary["calibration_verdict"].eq("calibrated").sum())
    confirmatory = comparison.loc[
        comparison["analysis_role"].eq("confirmatory")
    ].iloc[0]
    return "\n".join(
        [
            "# Closure V1 E8 uncertainty audit",
            "",
            "The audit consumed the 90 conformal factors locked before E0-U.",
            "No calibration rows were supplied and no q_c was fitted, recomputed, pooled, or adjusted.",
            "",
            f"- Locked q_c records consumed: `{len(factors)}`",
            f"- Primary 90% descriptive groups within ±0.05 coverage error: `{calibrated}/{len(primary)}`",
            f"- Conditional diagnostic rows retained: `{len(conditional)}`",
            f"- Confirmatory family E: `{confirmatory['status']}`",
            "- Holm family E universe retained: `1`",
            "- P1 substitution: `forbidden`",
            "",
            "A0/A1 uncertainty summaries are descriptive. They do not replace the unavailable P1 confirmatory estimand.",
            "",
        ]
    )


def preflight_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    if not isinstance(repo_root, Path):
        raise ClosureUncertaintyError("E8 repository root is not a Path")
    del repo_root
    contract_sha256 = _boundary(authority, sealed_batch_contract)
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "ready",
        "contract_sha256": contract_sha256,
        "outcome_paths_opened": False,
        "writes_performed": False,
    }


def execute_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    batch_context: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    preflight_closure_sealed_batch_component(
        authority, sealed_batch_contract, repo_root
    )
    try:
        context = validate_batch_context(batch_context)
    except ClosureAnfisAblationError as exc:
        raise ClosureUncertaintyError(str(exc)) from exc
    tables = cast(dict[str, pd.DataFrame], context["tables"])
    if "uncertainty_calibration" in tables:
        raise ClosureUncertaintyError(
            "E8 calibration rows are forbidden during the sealed batch"
        )
    if (
        "locked_conformal_factors" not in tables
        or "uncertainty_evaluation" not in tables
    ):
        raise ClosureUncertaintyError(
            "batch_context lacks locked conformal factors or uncertainty evaluation"
        )
    factors = normalize_locked_conformal_factors(tables["locked_conformal_factors"])
    evaluation = _normalize_evaluation(tables["uncertainty_evaluation"])
    availability = cast(Mapping[str, Any], context["model_availability"])
    sealed_availability = sealed_batch_contract.get("model_availability")
    if not isinstance(sealed_availability, Mapping) or dict(availability) != dict(
        sealed_availability
    ):
        raise ClosureUncertaintyError("model availability is not batch-bound")
    _validate_availability(evaluation, availability)
    applied = apply_locked_conformal_factors(evaluation, factors)
    ledger, comparison = _summary_rows(applied)
    conditional = _conditional_rows(applied)
    reliability = _reliability_rows(evaluation)
    report = _report(ledger, factors, conditional, comparison)
    artifacts = {
        OUTPUT_PATHS[0]: artifact_envelope("csv", ledger),
        OUTPUT_PATHS[1]: artifact_envelope("csv", conditional),
        OUTPUT_PATHS[2]: artifact_envelope("csv", comparison),
        OUTPUT_PATHS[3]: artifact_envelope("csv", reliability),
        OUTPUT_PATHS[4]: artifact_envelope("markdown", report, manifest_last=True),
    }
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "completed_unavailable",
        "artifacts": artifacts,
        "tables": {
            "e8_conformal_factors": factors.copy(deep=True),
            "e8_uncertainty_ledger": ledger.copy(deep=True),
            "e8_conditional_coverage": conditional.copy(deep=True),
            "e8_recalibration_comparison": comparison.copy(deep=True),
            "e8_reliability_bins": reliability.copy(deep=True),
        },
        "diagnostics": {
            "component_contract_sha256": component_contract_sha256(),
            "locked_factor_count": int(len(factors)),
            "evaluation_attempt_row_count": int(len(evaluation)),
            "uncertainty_applicable_model_ids": list(UNCERTAINTY_MODEL_IDS),
            "a2_slot_count": 0,
            "calibration_table_received": False,
            "q_fit_or_recompute_performed": False,
            "q_refit_in_evaluation": False,
            "confirmatory_family_E_status": "not_estimable_model_unavailable",
            "holm_family_E_universe_size": 1,
            "p1_substitution_performed": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }


__all__ = [
    "ClosureUncertaintyError",
    "apply_locked_conformal_factors",
    "component_contract",
    "component_contract_sha256",
    "execute_closure_sealed_batch_component",
    "normalize_locked_conformal_factors",
    "preflight_closure_sealed_batch_component",
]
