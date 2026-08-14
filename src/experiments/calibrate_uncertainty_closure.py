"""Pure split-conformal E8 uncertainty audit for the sealed Closure V1 batch."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
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
TERMINAL_STATUSES = (
    "success",
    "input_ineligible",
    "target_unavailable",
    "model_unavailable",
    "numerical_failure",
    "infrastructure_failure",
)
GAUSSIAN_FACTORS = MappingProxyType(
    {0.80: 1.2815515655446004, 0.90: 1.6448536269514722, 0.95: 1.959963984540054}
)
BASE_COLUMNS = (
    "model_id",
    "seed",
    "source_id",
    "site_id",
    "horizon_months",
    "target_year_month",
    "status",
    "y_true",
    "prediction",
    "lower",
    "upper",
    "nominal_coverage",
)
GROUP_COLUMNS = (
    "model_id",
    "surface_id",
    "endpoint",
    "horizon_months",
    "seed",
    "nominal_coverage",
)
INTENT_COLUMNS = (
    "surface_id",
    "endpoint",
    "source_id",
    "site_id",
    "horizon_months",
    "target_year_month",
    "nominal_coverage",
)
FACTOR_COLUMNS = (
    *GROUP_COLUMNS,
    "calibration_row_count",
    "finite_score_count",
    "order_index_one_based",
    "q",
    "status",
)
LEDGER_COLUMNS = (
    *GROUP_COLUMNS,
    "interval_version",
    "row_count",
    "empirical_coverage",
    "absolute_coverage_error",
    "mean_interval_width",
    "median_interval_width",
    "winkler_interval_score",
    "brier_score",
    "calibration_verdict",
)
COMPARISON_COLUMNS = (
    *GROUP_COLUMNS,
    "paired_row_count",
    "mean_winkler_delta_after_minus_before",
    "q",
    "status",
)
CONDITIONAL_COLUMNS = (
    *GROUP_COLUMNS,
    "breakdown_id",
    "stratum",
    "row_count",
    "location_count",
    "empirical_coverage",
    "absolute_coverage_error",
    "mean_interval_width",
    "median_interval_width",
    "status",
)
RELIABILITY_COLUMNS = (
    "model_id",
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
        "schema_version": "closure_e8_uncertainty_component_v1",
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "calibration_table": "uncertainty_calibration",
        "evaluation_table": "uncertainty_evaluation",
        "nominal_levels": list(NOMINAL_LEVELS),
        "registered_seeds": list(REGISTERED_SEEDS),
        "horizons_months": list(HORIZONS_MONTHS),
        "minimum_group_rows": MINIMUM_GROUP_ROWS,
        "scale_floor": SCALE_FLOOR,
        "order_index": "min(n,ceil((n+1)*coverage))",
        "interpolation": "none_higher_order_statistic",
        "exact_intent_coverage": "every_intent_has_every_model_by_registered_seed",
        "non_success_prediction_values": "all_null",
        "model_unavailable_y_true": "null",
        "q_refit_on_evaluation": False,
        "output_paths": list(OUTPUT_PATHS),
        "pure_in_memory": True,
    }
)


class ClosureUncertaintyError(RuntimeError):
    """Raised when E8 inputs or the locked conformal contract drift."""


def _canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, Mapping):
        value = {str(key): _plain_json(item) for key, item in value.items()}
    elif isinstance(value, (list, tuple)):
        value = [_plain_json(item) for item in value]
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _plain_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


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


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], *, name: str) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ClosureUncertaintyError(f"{name} missing columns: {missing}")


def _normalize(frame: pd.DataFrame, *, name: str) -> pd.DataFrame:
    _require_columns(frame, BASE_COLUMNS, name=name)
    out = frame.copy(deep=True)
    if "surface_id" not in out:
        out["surface_id"] = "closure_v1_primary"
    if "endpoint" not in out:
        out["endpoint"] = "risk"
    for column in (
        "seed",
        "horizon_months",
        "y_true",
        "prediction",
        "lower",
        "upper",
        "nominal_coverage",
    ):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out["seed"] = out["seed"].astype("int64")
    out["horizon_months"] = out["horizon_months"].astype("int64")
    out["model_id"] = out["model_id"].astype(str)
    out["surface_id"] = out["surface_id"].astype(str)
    out["endpoint"] = out["endpoint"].astype(str)
    out["status"] = out["status"].astype(str)
    for column in (
        "model_id",
        "surface_id",
        "endpoint",
        "source_id",
        "site_id",
        "target_year_month",
    ):
        out[column] = out[column].astype(str)
        if bool(out[column].eq("").any()):
            raise ClosureUncertaintyError(f"{name} {column} is empty")
    if not out["target_year_month"].str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all():
        raise ClosureUncertaintyError(f"{name} target month is not canonical")
    if not set(out["seed"]).issubset(REGISTERED_SEEDS):
        raise ClosureUncertaintyError(f"{name} contains an unregistered seed")
    if not set(out["horizon_months"]).issubset(HORIZONS_MONTHS):
        raise ClosureUncertaintyError(f"{name} horizon drifted")
    if not set(out["status"]).issubset(TERMINAL_STATUSES):
        raise ClosureUncertaintyError(f"{name} terminal status drifted")
    rounded_nominal = out["nominal_coverage"].round(2)
    if bool((~np.isfinite(out["nominal_coverage"])).any()) or bool(
        (~np.isclose(out["nominal_coverage"], rounded_nominal, rtol=0.0, atol=1e-12)).any()
    ):
        raise ClosureUncertaintyError(f"{name} nominal coverage is not canonical")
    out["nominal_coverage"] = rounded_nominal
    if not set(out["nominal_coverage"]).issubset(NOMINAL_LEVELS):
        raise ClosureUncertaintyError(f"{name} nominal coverage is not registered")
    success = out["status"].eq("success")
    numeric = out.loc[success, ["y_true", "prediction", "lower", "upper", "nominal_coverage"]]
    if bool((~np.isfinite(numeric)).any().any()):
        raise ClosureUncertaintyError(f"{name} successful rows contain nonfinite values")
    if bool((success & (out["upper"] <= out["lower"])).any()):
        raise ClosureUncertaintyError(f"{name} interval width is not positive")
    midpoint = (out["lower"] + out["upper"]) / 2.0
    if bool(
        (
            success
            & ~np.isclose(midpoint, out["prediction"], rtol=1e-10, atol=1e-12)
        ).any()
    ):
        raise ClosureUncertaintyError(f"{name} Gaussian interval is not centered")
    generated_columns = ["prediction", "lower", "upper"]
    if "sigma" in out:
        out["sigma"] = pd.to_numeric(out["sigma"], errors="coerce")
        generated_columns.append("sigma")
        gaussian = out["nominal_coverage"].map(GAUSSIAN_FACTORS)
        expected_half_width = gaussian * out["sigma"]
        observed_half_width = (out["upper"] - out["lower"]) / 2.0
        if bool((success & (~np.isfinite(out["sigma"]) | (out["sigma"] <= 0.0))).any()):
            raise ClosureUncertaintyError(f"{name} sigma is invalid")
        if bool(
            (
                success
                & ~np.isclose(
                    observed_half_width,
                    expected_half_width,
                    rtol=1e-8,
                    atol=1e-10,
                )
            ).any()
        ):
            raise ClosureUncertaintyError(f"{name} Gaussian factor drifted")
    if bool(out.loc[~success, generated_columns].notna().any().any()):
        raise ClosureUncertaintyError(
            f"{name} non-success rows contain invented uncertainty values"
        )
    model_unavailable = out["status"].eq("model_unavailable")
    if bool(out.loc[model_unavailable, "y_true"].notna().any()):
        raise ClosureUncertaintyError(
            f"{name} model-unavailable rows contain invented target values"
        )
    target_unavailable = out["status"].eq("target_unavailable")
    if bool(out.loc[target_unavailable, "y_true"].notna().any()):
        raise ClosureUncertaintyError(
            f"{name} target-unavailable rows contain target values"
        )
    keys = [
        "model_id",
        "surface_id",
        "endpoint",
        "seed",
        "source_id",
        "site_id",
        "horizon_months",
        "target_year_month",
        "nominal_coverage",
    ]
    if bool(out.duplicated(keys).any()):
        raise ClosureUncertaintyError(f"{name} contains duplicate exact rows")
    return out.sort_values(keys, kind="mergesort").reset_index(drop=True)


def conformal_order_statistic(scores: Sequence[float], nominal_coverage: float) -> float:
    """Return the frozen finite-sample higher order statistic without interpolation."""

    values = np.asarray(scores, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < MINIMUM_GROUP_ROWS:
        raise ClosureUncertaintyError("conformal group has fewer than 30 finite scores")
    if nominal_coverage not in NOMINAL_LEVELS:
        raise ClosureUncertaintyError("conformal nominal level is not registered")
    one_based = min(len(values), int(math.ceil((len(values) + 1) * nominal_coverage)))
    return float(np.sort(values, kind="mergesort")[one_based - 1])


def _scale(frame: pd.DataFrame) -> np.ndarray:
    if "sigma" in frame:
        sigma = pd.to_numeric(frame["sigma"], errors="coerce").to_numpy(dtype=float)
    else:
        factors = frame["nominal_coverage"].round(2).map(GAUSSIAN_FACTORS).to_numpy(dtype=float)
        sigma = (frame["upper"].to_numpy(dtype=float) - frame["lower"].to_numpy(dtype=float)) / (2.0 * factors)
    return np.maximum(sigma, SCALE_FLOOR)


def fit_conformal_factors(calibration: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    successful = calibration[calibration["status"].eq("success")].copy()
    for group_key, group in successful.groupby(list(GROUP_COLUMNS), sort=True, dropna=False):
        scale = _scale(group)
        scores = np.abs(group["y_true"].to_numpy(dtype=float) - group["prediction"].to_numpy(dtype=float)) / scale
        finite = scores[np.isfinite(scores)]
        status = "available" if len(finite) >= MINIMUM_GROUP_ROWS else "insufficient_calibration_support"
        q = conformal_order_statistic(finite, float(group_key[-1])) if status == "available" else math.nan
        rows.append(
            {
                **dict(zip(GROUP_COLUMNS, group_key, strict=True)),
                "calibration_row_count": int(len(group)),
                "finite_score_count": int(len(finite)),
                "order_index_one_based": (
                    min(len(finite), int(math.ceil((len(finite) + 1) * float(group_key[-1]))))
                    if len(finite)
                    else 0
                ),
                "q": q,
                "status": status,
            }
        )
    return pd.DataFrame(rows, columns=FACTOR_COLUMNS)


def _winkler(y: np.ndarray, lower: np.ndarray, upper: np.ndarray, nominal: float) -> np.ndarray:
    alpha = 1.0 - nominal
    value = upper - lower
    value = value + np.where(y < lower, (2.0 / alpha) * (lower - y), 0.0)
    return value + np.where(y > upper, (2.0 / alpha) * (y - upper), 0.0)


def apply_conformal_factors(evaluation: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    successful = evaluation[evaluation["status"].eq("success")].copy()
    merged = successful.merge(
        factors,
        on=list(GROUP_COLUMNS),
        how="left",
        validate="many_to_one",
        suffixes=("", "_factor"),
    )
    merged["scale"] = _scale(merged)
    merged["q"] = pd.to_numeric(merged["q"], errors="coerce")
    available = merged["status_factor"].eq("available") & np.isfinite(merged["q"])
    merged["after_lower"] = np.where(available, merged["prediction"] - merged["q"] * merged["scale"], np.nan)
    merged["after_upper"] = np.where(available, merged["prediction"] + merged["q"] * merged["scale"], np.nan)
    merged["recalibration_status"] = np.where(available, "available", "not_available")
    return merged


def _summary_rows(applied: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ledger: list[dict[str, Any]] = []
    comparison: list[dict[str, Any]] = []
    for raw_group_key, group in applied.groupby(
        list(GROUP_COLUMNS), sort=True, dropna=False
    ):
        group_key = cast(tuple[Any, ...], raw_group_key)
        nominal = float(group_key[-1])
        y = group["y_true"].to_numpy(dtype=float)
        before_lower = group["lower"].to_numpy(dtype=float)
        before_upper = group["upper"].to_numpy(dtype=float)
        available = group["recalibration_status"].eq("available").to_numpy(dtype=bool)
        for label, lower, upper, mask in (
            ("before", before_lower, before_upper, np.ones(len(group), dtype=bool)),
            (
                "after",
                group["after_lower"].to_numpy(dtype=float),
                group["after_upper"].to_numpy(dtype=float),
                available,
            ),
        ):
            valid = mask & np.isfinite(y) & np.isfinite(lower) & np.isfinite(upper)
            coverage = float(np.mean((y[valid] >= lower[valid]) & (y[valid] <= upper[valid]))) if valid.any() else math.nan
            width = upper[valid] - lower[valid]
            winkler = _winkler(y[valid], lower[valid], upper[valid], nominal) if valid.any() else np.array([])
            prediction = group["prediction"].to_numpy(dtype=float)
            binary = valid & np.isin(y, (0.0, 1.0)) & (prediction >= 0.0) & (prediction <= 1.0)
            ledger.append(
                {
                    **dict(zip(GROUP_COLUMNS, group_key, strict=True)),
                    "interval_version": label,
                    "row_count": int(valid.sum()),
                    "empirical_coverage": coverage,
                    "absolute_coverage_error": abs(coverage - nominal) if math.isfinite(coverage) else math.nan,
                    "mean_interval_width": float(np.mean(width)) if len(width) else math.nan,
                    "median_interval_width": float(np.median(width)) if len(width) else math.nan,
                    "winkler_interval_score": float(np.mean(winkler)) if len(winkler) else math.nan,
                    "brier_score": (
                        float(np.mean(np.square(prediction[binary] - y[binary])))
                        if binary.any()
                        else math.nan
                    ),
                    "calibration_verdict": (
                        "calibrated" if math.isfinite(coverage) and abs(coverage - nominal) <= 0.05 else "not_uniformly_calibrated"
                    ),
                }
            )
        before_score = _winkler(y, before_lower, before_upper, nominal)
        after_valid = available & np.isfinite(group["after_lower"]) & np.isfinite(group["after_upper"])
        delta = np.full(len(group), np.nan)
        delta[after_valid] = _winkler(
            y[after_valid],
            group.loc[after_valid, "after_lower"].to_numpy(dtype=float),
            group.loc[after_valid, "after_upper"].to_numpy(dtype=float),
            nominal,
        ) - before_score[after_valid]
        comparison.append(
            {
                **dict(zip(GROUP_COLUMNS, group_key, strict=True)),
                "paired_row_count": int(np.isfinite(delta).sum()),
                "mean_winkler_delta_after_minus_before": float(np.nanmean(delta)) if np.isfinite(delta).any() else math.nan,
                "q": float(group["q"].iloc[0]) if np.isfinite(group["q"].iloc[0]) else math.nan,
                "status": "available" if np.isfinite(delta).any() else "not_available",
            }
        )
    return (
        pd.DataFrame(ledger, columns=LEDGER_COLUMNS),
        pd.DataFrame(comparison, columns=COMPARISON_COLUMNS),
    )


def _conditional_rows(applied: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    available = applied[applied["recalibration_status"].eq("available")].copy()
    breakdowns: list[tuple[str, pd.Series]] = [
        ("global", pd.Series("all", index=available.index, dtype="object")),
        ("horizon", available["horizon_months"].astype(str)),
    ]
    if "predicted_risk" in available:
        bands = pd.cut(
            pd.to_numeric(available["predicted_risk"], errors="coerce"),
            bins=[0.0, 0.25, 0.5, 0.75, 1.0],
            right=False,
            include_lowest=True,
            labels=["[0,.25)", "[.25,.5)", "[.5,.75)", "[.75,1]"],
        ).astype("object")
        bands.loc[pd.to_numeric(available["predicted_risk"], errors="coerce").eq(1.0)] = "[.75,1]"
        breakdowns.append(("predicted_risk_band", bands.astype(str)))
    for optional, name in (
        ("nutrient_evidence_quartile", "nutrient_evidence_quartile"),
        ("missingness_quartile", "missingness_quartile"),
        ("site_frequency_band", "site_frequency_band"),
        ("location_novelty", "location_novelty"),
        ("degradation_scenario", "degradation_scenario"),
    ):
        if optional in available:
            breakdowns.append((name, available[optional].astype(str)))
    for breakdown, labels in breakdowns:
        local = available.assign(_stratum=labels)
        grouping = [*GROUP_COLUMNS, "_stratum"]
        for key, group in local.groupby(grouping, sort=True, dropna=False):
            nominal = float(key[-2])
            y = group["y_true"].to_numpy(dtype=float)
            lower = group["after_lower"].to_numpy(dtype=float)
            upper = group["after_upper"].to_numpy(dtype=float)
            valid = np.isfinite(y) & np.isfinite(lower) & np.isfinite(upper)
            count = int(valid.sum())
            coverage = float(np.mean((y[valid] >= lower[valid]) & (y[valid] <= upper[valid]))) if count >= MINIMUM_GROUP_ROWS else math.nan
            width = upper[valid] - lower[valid]
            rows.append(
                {
                    **dict(zip(GROUP_COLUMNS, key[:-1], strict=True)),
                    "breakdown_id": breakdown,
                    "stratum": str(key[-1]),
                    "row_count": count,
                    "location_count": int(group.loc[valid, ["source_id", "site_id"]].drop_duplicates().shape[0]),
                    "empirical_coverage": coverage,
                    "absolute_coverage_error": abs(coverage - nominal) if math.isfinite(coverage) else math.nan,
                    "mean_interval_width": float(np.mean(width)) if count >= MINIMUM_GROUP_ROWS else math.nan,
                    "median_interval_width": float(np.median(width)) if count >= MINIMUM_GROUP_ROWS else math.nan,
                    "status": "available" if count >= MINIMUM_GROUP_ROWS else "insufficient_support",
                }
            )
    return pd.DataFrame(rows, columns=CONDITIONAL_COLUMNS)


def _reliability_rows(evaluation: pd.DataFrame) -> pd.DataFrame:
    frame = evaluation[evaluation["status"].eq("success")].copy()
    binary = frame["y_true"].isin([0.0, 1.0]) & frame["prediction"].between(0.0, 1.0, inclusive="both")
    frame = frame[binary]
    if frame.empty:
        return pd.DataFrame(columns=RELIABILITY_COLUMNS)
    frame["bin_id"] = np.minimum((frame["prediction"] * 10).astype(int), 9)
    return (
        frame.groupby(["model_id", "horizon_months", "bin_id"], sort=True)
        .agg(row_count=("y_true", "size"), mean_prediction=("prediction", "mean"), observed_frequency=("y_true", "mean"))
        .reset_index()
        .loc[:, list(RELIABILITY_COLUMNS)]
    )


def _validate_availability(
    calibration: pd.DataFrame,
    evaluation: pd.DataFrame,
    availability: Mapping[str, Any],
) -> None:
    expected_models = set(availability)
    if not expected_models or any(
        not isinstance(model_id, str)
        or not model_id
        or state not in {"available", "unavailable"}
        for model_id, state in availability.items()
    ):
        raise ClosureUncertaintyError("sealed model availability is malformed")
    for name, frame in (
        ("uncertainty_calibration", calibration),
        ("uncertainty_evaluation", evaluation),
    ):
        if frame.empty:
            raise ClosureUncertaintyError(f"{name} is empty")
        observed_models = set(frame["model_id"])
        if observed_models != expected_models:
            raise ClosureUncertaintyError(
                f"{name} model universe is not exact"
            )
        expected_pairs = {
            (model_id, seed)
            for model_id in sorted(expected_models)
            for seed in REGISTERED_SEEDS
        }
        intent_sets = frame.groupby(list(INTENT_COLUMNS), sort=True).apply(
            lambda group: set(zip(group["model_id"], group["seed"], strict=True)),
            include_groups=False,
        )
        if intent_sets.empty or any(
            pairs != expected_pairs for pairs in intent_sets
        ):
            raise ClosureUncertaintyError(
                f"{name} omits a sealed model-by-seed intent"
            )
    for model_id in sorted(expected_models):
        state = availability.get(model_id)
        rows = pd.concat(
            [
                calibration.loc[calibration["model_id"].eq(model_id), "status"],
                evaluation.loc[evaluation["model_id"].eq(model_id), "status"],
            ],
            ignore_index=True,
        )
        if state == "unavailable" and not rows.eq("model_unavailable").all():
            raise ClosureUncertaintyError(
                f"unavailable uncertainty model produced results: {model_id}"
            )
        if state == "available" and rows.eq("model_unavailable").any():
            raise ClosureUncertaintyError(
                f"available uncertainty model was silently unavailable: {model_id}"
            )


def _report(ledger: pd.DataFrame, factors: pd.DataFrame, conditional: pd.DataFrame) -> str:
    available = int(factors["status"].eq("available").sum()) if not factors.empty else 0
    sparse = int(factors["status"].ne("available").sum()) if not factors.empty else 0
    primary = ledger[(ledger["nominal_coverage"].eq(PRIMARY_NOMINAL)) & ledger["interval_version"].eq("after")]
    calibrated = int(primary["calibration_verdict"].eq("calibrated").sum())
    return "\n".join(
        [
            "# Closure V1 E8 uncertainty audit",
            "",
            "Split-conformal factors were fitted only from the supplied locked calibration role.",
            "No factor was refit in evaluation or within a conditional stratum.",
            "",
            f"- Available conformal groups: `{available}`",
            f"- Insufficient-support groups: `{sparse}`",
            f"- Primary 90% groups within ±0.05 coverage error: `{calibrated}/{len(primary)}`",
            f"- Conditional diagnostic rows retained: `{len(conditional)}`",
            "",
            "Uncertainty is quantified and audited; this report does not claim uniform calibration where diagnostics fail.",
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
    preflight_closure_sealed_batch_component(authority, sealed_batch_contract, repo_root)
    try:
        context = validate_batch_context(batch_context)
    except ClosureAnfisAblationError as exc:
        raise ClosureUncertaintyError(str(exc)) from exc
    tables = cast(dict[str, pd.DataFrame], context["tables"])
    if "uncertainty_calibration" not in tables or "uncertainty_evaluation" not in tables:
        raise ClosureUncertaintyError("batch_context lacks uncertainty calibration/evaluation")
    calibration = _normalize(tables["uncertainty_calibration"], name="uncertainty_calibration")
    evaluation = _normalize(tables["uncertainty_evaluation"], name="uncertainty_evaluation")
    availability = cast(Mapping[str, Any], context["model_availability"])
    sealed_availability = sealed_batch_contract.get("model_availability")
    if not isinstance(sealed_availability, Mapping) or dict(availability) != dict(
        sealed_availability
    ):
        raise ClosureUncertaintyError("model availability is not batch-bound")
    _validate_availability(calibration, evaluation, availability)
    factors = fit_conformal_factors(calibration)
    applied = apply_conformal_factors(evaluation, factors)
    ledger, comparison = _summary_rows(applied)
    conditional = _conditional_rows(applied)
    reliability = _reliability_rows(evaluation)
    report = _report(ledger, factors, conditional)
    any_available = bool(applied["recalibration_status"].eq("available").any())
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
        "status": "completed" if any_available else "completed_unavailable",
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
            "calibration_row_count": int(len(calibration)),
            "evaluation_row_count": int(len(evaluation)),
            "available_factor_count": int(factors["status"].eq("available").sum()) if not factors.empty else 0,
            "minimum_group_rows": MINIMUM_GROUP_ROWS,
            "q_refit_in_evaluation": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }
