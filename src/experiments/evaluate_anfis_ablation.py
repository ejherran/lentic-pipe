"""Pure in-memory E7 evaluation for the sealed Closure V1 batch.

The runner owns outcome access and publication.  This component validates the
published E0-U authority, consumes only data frames supplied in
``batch_context``, and returns deterministic artifact envelopes without file
system, network, Git, DVC, training, or model-loading operations.
"""

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
from sklearn.metrics import average_precision_score


COMPONENT_ID = "E7_anfis_ablation"
STAGE_ID = "E7"
RNG_SEED = 1729
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
MODEL_IDS = ("A0", "P0", "P1", "A1")
HORIZONS_MONTHS = (1, 2, 3)
TERMINAL_STATUSES = (
    "success",
    "input_ineligible",
    "target_unavailable",
    "model_unavailable",
    "numerical_failure",
    "infrastructure_failure",
)
PAIRWISE_CONTRASTS = (("P1", "P0"), ("P1", "A0"), ("P0", "A0"), ("A1", "A0"), ("A1", "P1"))
PREDICTION_COLUMNS = (
    "model_id",
    "seed",
    "source_id",
    "site_id",
    "common_origin_id",
    "evaluation_cohort",
    "evaluation_role",
    "horizon_months",
    "target_year_month",
    "status",
    "y_true",
    "y_prob",
)
OUTPUT_PATHS = (
    "reports/closure_v1/07_anfis_ablation_evaluation/ablation_metrics.csv",
    "reports/closure_v1/07_anfis_ablation_evaluation/ablation_pairwise.csv",
    "reports/closure_v1/07_anfis_ablation_evaluation/membership_stability.csv",
    "reports/closure_v1/07_anfis_ablation_evaluation/anfis_learning_curve.csv",
    "reports/closure_v1/07_anfis_ablation_evaluation/anfis_ablation_report.md",
)
CONTEXT_KEYS = frozenset(
    {
        "execution_id",
        "rng_seed",
        "tables",
        "stage_results",
        "model_availability",
        "software_evidence",
    }
)
AUTHORITY_FLAGS = MappingProxyType(
    {
        "gate": "E0-U",
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
    }
)
COMPONENT_CONTRACT = MappingProxyType(
    {
        "schema_version": "closure_e7_anfis_ablation_component_v1",
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "input_tables": ["e7_predictions"],
        "optional_input_tables": ["e7_memberships", "e7_learning_curve"],
        "model_ids": list(MODEL_IDS),
        "registered_seeds": list(REGISTERED_SEEDS),
        "horizons_months": list(HORIZONS_MONTHS),
        "terminal_statuses": list(TERMINAL_STATUSES),
        "pairwise_contrasts": [list(pair) for pair in PAIRWISE_CONTRASTS],
        "unavailable_policy": "retain_explicit_model_unavailable_rows",
        "matching_unit": [
            "seed",
            "source_id",
            "site_id",
            "common_origin_id",
            "evaluation_cohort",
            "evaluation_role",
            "horizon_months",
            "target_year_month",
        ],
        "source_id": "wqp",
        "evaluation_cohort": "location_holdout",
        "evaluation_role": "test",
        "outcome_boundary": "target_year_month_after_2021_12",
        "common_origin_time_rule": "target_year_month_minus_horizon_is_constant",
        "learning_curve_historical_status_map": {
            "completed": "available",
            "resource_failure_recorded": "not_available",
        },
        "saturation_claim_authorized": False,
        "output_paths": list(OUTPUT_PATHS),
        "pure_in_memory": True,
    }
)


class ClosureAnfisAblationError(RuntimeError):
    """Raised when the sealed E7 contract or supplied data drift."""


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


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def component_contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_canonical_json_bytes(COMPONENT_CONTRACT)))


def component_contract_sha256() -> str:
    return _sha256(COMPONENT_CONTRACT)


def _require_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ClosureAnfisAblationError(f"{context} must be a mapping")
    return cast(Mapping[str, Any], value)


def validate_component_boundary(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    *,
    component_id: str,
    stage_id: str,
    output_paths: Sequence[str],
) -> str:
    """Validate the common authority and runner contract without I/O."""

    authority = _require_mapping(authority, context="E0-U authority")
    contract = _require_mapping(sealed_batch_contract, context="sealed batch contract")
    for key, expected in AUTHORITY_FLAGS.items():
        if type(authority.get(key)) is not type(expected) or authority.get(key) != expected:
            raise ClosureAnfisAblationError(f"E0-U authority field drifted: {key}")
    command = contract.get("sealed_command")
    if not isinstance(command, str) or authority.get("sealed_batch_command") != command:
        raise ClosureAnfisAblationError("authority and sealed command are not bound")
    expected_contract = {
        "schema_version": "closure_sealed_evaluation_batch_v1",
        "experiment_id": "closure_v1",
        "formal_model_lock_gate": "E0-M",
        "execution_gate": "E0-U",
        "authority_is_first_execute_operation": True,
        "evaluation_refit": "forbidden",
        "failed_model_replacement": "forbidden",
        "silent_row_deletion": "forbidden",
        "manifest_last": True,
        "one_batch_only": True,
    }
    for key, expected in expected_contract.items():
        if type(contract.get(key)) is not type(expected) or contract.get(key) != expected:
            raise ClosureAnfisAblationError(f"sealed batch field drifted: {key}")
    components = contract.get("components")
    stages = contract.get("stages")
    if not isinstance(components, Sequence) or isinstance(components, (str, bytes)):
        raise ClosureAnfisAblationError("sealed batch components are absent")
    if not isinstance(stages, Sequence) or isinstance(stages, (str, bytes)):
        raise ClosureAnfisAblationError("sealed batch stages are absent")
    matching_components = [
        item
        for item in components
        if isinstance(item, Mapping) and item.get("component_id") == component_id
    ]
    matching_stages = [
        item for item in stages if isinstance(item, Mapping) and item.get("stage_id") == stage_id
    ]
    if (
        len(matching_components) != 1
        or matching_components[0].get("stage_id") != stage_id
        or matching_components[0].get("preflight_api")
        != "preflight_closure_sealed_batch_component"
        or matching_components[0].get("execute_api")
        != "execute_closure_sealed_batch_component"
        or len(matching_stages) != 1
        or matching_stages[0].get("output_paths") != list(output_paths)
        or matching_stages[0].get("requires_outcomes") is not True
    ):
        raise ClosureAnfisAblationError(f"sealed {stage_id} component/stage drifted")
    return _sha256(contract)


def validate_batch_context(batch_context: Mapping[str, Any]) -> dict[str, Any]:
    context = _require_mapping(batch_context, context="batch_context")
    if set(context) != CONTEXT_KEYS:
        raise ClosureAnfisAblationError("batch_context keys are not exact")
    if not isinstance(context.get("execution_id"), str) or not context["execution_id"]:
        raise ClosureAnfisAblationError("batch_context execution_id is absent")
    if type(context.get("rng_seed")) is not int or context["rng_seed"] != RNG_SEED:
        raise ClosureAnfisAblationError("batch_context rng_seed drifted")
    for key in ("tables", "stage_results", "model_availability", "software_evidence"):
        if not isinstance(context.get(key), Mapping):
            raise ClosureAnfisAblationError(f"batch_context {key} is not a mapping")
    tables: dict[str, pd.DataFrame] = {}
    for name, value in cast(Mapping[str, Any], context["tables"]).items():
        if not isinstance(name, str) or not isinstance(value, pd.DataFrame):
            raise ClosureAnfisAblationError("batch_context tables must map names to DataFrames")
        tables[name] = value.copy(deep=True)
    return {
        "execution_id": context["execution_id"],
        "rng_seed": context["rng_seed"],
        "tables": tables,
        "stage_results": dict(cast(Mapping[str, Any], context["stage_results"])),
        "model_availability": dict(cast(Mapping[str, Any], context["model_availability"])),
        "software_evidence": dict(cast(Mapping[str, Any], context["software_evidence"])),
    }


def artifact_envelope(
    artifact_format: str, payload: Any, *, manifest_last: bool = False
) -> dict[str, Any]:
    if artifact_format not in {"csv", "json", "markdown", "parquet", "xml"}:
        raise ClosureAnfisAblationError("artifact format is unsupported")
    allowed = isinstance(payload, (pd.DataFrame, Mapping, str, bytes))
    if not allowed or type(manifest_last) is not bool:
        raise ClosureAnfisAblationError("artifact envelope payload drifted")
    return {"format": artifact_format, "payload": payload, "manifest_last": manifest_last}


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], *, context: str) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ClosureAnfisAblationError(f"{context} missing columns: {missing}")


def _normalize_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    if tuple(frame.columns) != PREDICTION_COLUMNS:
        raise ClosureAnfisAblationError("e7_predictions columns are not exact")
    out = frame.copy(deep=True)
    out["model_id"] = out["model_id"].astype(str)
    out["status"] = out["status"].astype(str)
    for column in ("seed", "horizon_months"):
        numeric = pd.to_numeric(out[column], errors="raise")
        values = numeric.to_numpy(dtype="float64")
        if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
            raise ClosureAnfisAblationError(
                f"e7_predictions {column} is not exact integer"
            )
        out[column] = numeric.astype("int64")
    for column in ("y_true", "y_prob"):
        raw = out[column]
        numeric = pd.to_numeric(raw, errors="coerce")
        if bool((raw.notna() & numeric.isna()).any()):
            raise ClosureAnfisAblationError(
                f"e7_predictions {column} contains a nonnumeric value"
            )
        out[column] = numeric
    for column in (
        "source_id",
        "site_id",
        "common_origin_id",
        "evaluation_cohort",
        "evaluation_role",
        "target_year_month",
    ):
        out[column] = out[column].astype(str)
        if bool(out[column].eq("").any()):
            raise ClosureAnfisAblationError(f"e7_predictions {column} is empty")
    if (
        not out["source_id"].eq("wqp").all()
        or not out["evaluation_cohort"].eq("location_holdout").all()
        or not out["evaluation_role"].eq("test").all()
    ):
        raise ClosureAnfisAblationError(
            "e7_predictions is not restricted to locked WQP location-holdout test rows"
        )
    if not out["common_origin_id"].str.fullmatch(r"[0-9a-f]{64}").all():
        raise ClosureAnfisAblationError("e7_predictions common-origin identity is not canonical")
    if not out["target_year_month"].str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all():
        raise ClosureAnfisAblationError("e7_predictions target month is not canonical")
    target_periods = pd.PeriodIndex(out["target_year_month"], freq="M")
    if not (target_periods > pd.Period("2021-12", freq="M")).all():
        raise ClosureAnfisAblationError("e7_predictions target month is outside post-2021")
    if not set(out["model_id"]).issubset(MODEL_IDS):
        raise ClosureAnfisAblationError("e7_predictions contains an unknown model")
    if not set(out["seed"]).issubset(REGISTERED_SEEDS):
        raise ClosureAnfisAblationError("e7_predictions contains an unregistered seed")
    if not set(out["horizon_months"]).issubset(HORIZONS_MONTHS):
        raise ClosureAnfisAblationError("e7_predictions horizon drifted")
    if not set(out["status"]).issubset(TERMINAL_STATUSES):
        raise ClosureAnfisAblationError("e7_predictions terminal status drifted")
    duplicate_key = [
        "model_id",
        "seed",
        "source_id",
        "site_id",
        "common_origin_id",
        "evaluation_cohort",
        "evaluation_role",
        "horizon_months",
        "target_year_month",
    ]
    if bool(out.duplicated(duplicate_key).any()):
        raise ClosureAnfisAblationError("e7_predictions contains duplicate exact rows")
    identity = [
        "source_id",
        "site_id",
        "common_origin_id",
        "evaluation_cohort",
        "evaluation_role",
        "horizon_months",
        "target_year_month",
    ]
    expected_pairs = {(model, seed) for model in MODEL_IDS for seed in REGISTERED_SEEDS}
    pair_sets = out.groupby(identity, sort=True).apply(
        lambda group: set(zip(group["model_id"], group["seed"], strict=True)),
        include_groups=False,
    )
    if out.empty or any(pairs != expected_pairs for pairs in pair_sets):
        raise ClosureAnfisAblationError(
            "e7_predictions omits a registered model-by-seed intent"
        )
    intent = out.loc[:, identity].drop_duplicates()
    base_identity = [
        "source_id",
        "site_id",
        "common_origin_id",
        "evaluation_cohort",
        "evaluation_role",
    ]
    implied_origins = pd.PeriodIndex(intent["target_year_month"], freq="M") - intent[
        "horizon_months"
    ].to_numpy(dtype="int64")
    intent = intent.assign(_implied_origin=implied_origins.astype(str))
    origin_counts = intent.groupby(base_identity, sort=True)["_implied_origin"].nunique()
    horizon_sets = intent.groupby(base_identity, sort=True)["horizon_months"].apply(set)
    if (
        bool(origin_counts.ne(1).any())
        or any(horizons != set(HORIZONS_MONTHS) for horizons in horizon_sets)
    ):
        raise ClosureAnfisAblationError("e7_predictions common-origin time identity drifted")
    common_identity_counts = (
        intent.groupby("common_origin_id", sort=True)[
            ["source_id", "site_id", "evaluation_cohort", "evaluation_role", "_implied_origin"]
        ]
        .nunique()
    )
    if bool(common_identity_counts.gt(1).any().any()):
        raise ClosureAnfisAblationError("e7_predictions common-origin mapping drifted")
    success = out["status"].eq("success")
    if bool((success & (~np.isfinite(out["y_true"]) | ~np.isfinite(out["y_prob"]))).any()):
        raise ClosureAnfisAblationError("successful E7 rows contain nonfinite values")
    if bool((success & ~out["y_prob"].between(0.0, 1.0, inclusive="both")).any()):
        raise ClosureAnfisAblationError("successful E7 probabilities leave [0,1]")
    if bool((success & ~out["y_true"].isin([0.0, 1.0])).any()):
        raise ClosureAnfisAblationError("successful E7 targets are not binary")
    target_present = out["y_true"].notna()
    if bool(
        (
            target_present
            & (~np.isfinite(out["y_true"]) | ~out["y_true"].isin([0.0, 1.0]))
        ).any()
    ):
        raise ClosureAnfisAblationError("available E7 targets are not finite binary values")
    if bool(out.loc[~success, "y_prob"].notna().any()):
        raise ClosureAnfisAblationError("failed E7 rows contain invented predictions")
    target_counts = out.groupby(identity, sort=True)["y_true"].nunique(dropna=True)
    target_presence = out.assign(_target_present=out["y_true"].notna()).groupby(
        identity, sort=True
    )["_target_present"].nunique()
    if bool(target_counts.gt(1).any()) or bool(target_presence.gt(1).any()):
        raise ClosureAnfisAblationError("E7 targets drifted within an exact intent")
    if bool(out.loc[out["status"].eq("target_unavailable"), "y_true"].notna().any()):
        raise ClosureAnfisAblationError("target-unavailable E7 row contains an observed target")
    return out.sort_values(duplicate_key, kind="mergesort").reset_index(drop=True)


def _validate_availability(
    predictions: pd.DataFrame, availability: Mapping[str, Any]
) -> None:
    for model_id in MODEL_IDS:
        state = availability.get(model_id)
        if state not in {"available", "unavailable"}:
            raise ClosureAnfisAblationError(
                f"model availability is absent or invalid: {model_id}"
            )
        rows = predictions["model_id"].eq(model_id)
        if state == "unavailable":
            if not predictions.loc[rows, "status"].eq("model_unavailable").all():
                raise ClosureAnfisAblationError(
                    f"unavailable model produced a non-unavailable row: {model_id}"
                )
        elif predictions.loc[rows, "status"].eq("model_unavailable").any():
            raise ClosureAnfisAblationError(
                f"available model was silently marked unavailable: {model_id}"
            )


def _metric_rows(
    predictions: pd.DataFrame, availability: Mapping[str, Any]
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model_id in MODEL_IDS:
        model_available = availability.get(model_id) == "available"
        for seed in REGISTERED_SEEDS:
            for horizon in (1, 2, 3):
                group = predictions[
                    predictions["model_id"].eq(model_id)
                    & predictions["seed"].eq(seed)
                    & predictions["horizon_months"].eq(horizon)
                ]
                successful = group[group["status"].eq("success")]
                status = "available" if model_available and not successful.empty else (
                    "model_unavailable" if not model_available else "no_successful_rows"
                )
                values: dict[str, float] = {
                    "pr_auc": math.nan,
                    "brier": math.nan,
                    "rmse": math.nan,
                    "mae": math.nan,
                }
                if status == "available":
                    actual = successful["y_true"].to_numpy(dtype=float)
                    score = successful["y_prob"].to_numpy(dtype=float)
                    values["brier"] = float(np.mean(np.square(score - actual)))
                    values["rmse"] = float(np.sqrt(values["brier"]))
                    values["mae"] = float(np.mean(np.abs(score - actual)))
                    if np.unique(actual).size == 2:
                        values["pr_auc"] = float(average_precision_score(actual, score))
                for metric, value in values.items():
                    rows.append(
                        {
                            "evaluation_cohort": "location_holdout",
                            "evaluation_role": "test",
                            "model_id": model_id,
                            "seed": seed,
                            "horizon_months": horizon,
                            "metric": metric,
                            "value": value,
                            "row_count": int(len(successful)),
                            "attempted_row_count": int(len(group)),
                            "status": status,
                        }
                    )
    return pd.DataFrame(rows)


def _pairwise_rows(
    predictions: pd.DataFrame, availability: Mapping[str, Any]
) -> pd.DataFrame:
    keys = [
        "seed",
        "source_id",
        "site_id",
        "common_origin_id",
        "evaluation_cohort",
        "evaluation_role",
        "horizon_months",
        "target_year_month",
    ]
    rows: list[dict[str, Any]] = []
    successful = predictions[predictions["status"].eq("success")].copy()
    for challenger, reference in PAIRWISE_CONTRASTS:
        available = availability.get(challenger) == "available" and availability.get(reference) == "available"
        left = successful[successful["model_id"].eq(challenger)][keys + ["y_true", "y_prob"]]
        right = successful[successful["model_id"].eq(reference)][keys + ["y_true", "y_prob"]]
        paired = left.merge(right, on=keys, suffixes=("_challenger", "_reference"), validate="one_to_one")
        if not paired.empty and not np.allclose(
            paired["y_true_challenger"], paired["y_true_reference"], rtol=0.0, atol=0.0
        ):
            raise ClosureAnfisAblationError("paired E7 targets drifted across models")
        for horizon in HORIZONS_MONTHS:
            group = paired[paired["horizon_months"].eq(horizon)]
            status = "available" if available and not group.empty else (
                "model_unavailable" if not available else "no_common_success_rows"
            )
            values = {"delta_brier": math.nan, "delta_mae": math.nan, "delta_pr_auc": math.nan}
            if status == "available" and not group.empty:
                actual = group["y_true_challenger"].to_numpy(dtype=float)
                challenger_score = group["y_prob_challenger"].to_numpy(dtype=float)
                reference_score = group["y_prob_reference"].to_numpy(dtype=float)
                values["delta_brier"] = float(
                    np.mean(np.square(challenger_score - actual) - np.square(reference_score - actual))
                )
                values["delta_mae"] = float(
                    np.mean(np.abs(challenger_score - actual) - np.abs(reference_score - actual))
                )
                if np.unique(actual).size == 2:
                    values["delta_pr_auc"] = float(
                        average_precision_score(actual, challenger_score)
                        - average_precision_score(actual, reference_score)
                    )
            rows.append(
                {
                    "evaluation_cohort": "location_holdout",
                    "evaluation_role": "test",
                    "challenger_model_id": challenger,
                    "reference_model_id": reference,
                    "horizon_months": horizon,
                    "common_row_count": int(len(group)),
                    "status": status,
                    **values,
                }
            )
    return pd.DataFrame(rows)


def _membership_summary(value: pd.DataFrame | None) -> pd.DataFrame:
    columns = [
        "model_id",
        "module",
        "feature",
        "membership_index",
        "seed_count",
        "center_mean",
        "center_sd",
        "width_mean",
        "width_sd",
        "centers_ordered_all_seeds",
        "status",
    ]
    if value is None:
        return pd.DataFrame([{key: ("not_available" if key == "status" else math.nan) for key in columns}])
    frame = value.copy()
    aliases = {"base_seed": "seed", "input_name": "feature"}
    frame = frame.rename(columns={key: target for key, target in aliases.items() if key in frame and target not in frame})
    required = ("model_id", "seed", "module", "feature", "membership_index", "center", "width")
    _require_columns(frame, required, context="e7_memberships")
    for column in ("seed", "membership_index", "center", "width"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame["seed"] = frame["seed"].astype("int64")
    if not set(frame["seed"]).issubset(REGISTERED_SEEDS):
        raise ClosureAnfisAblationError("membership record uses an unregistered seed")
    if bool((~np.isfinite(frame["center"]) | ~np.isfinite(frame["width"]) | (frame["width"] <= 0)).any()):
        raise ClosureAnfisAblationError("membership center/width is invalid")
    order_keys = ["model_id", "seed", "module", "feature", "membership_index"]
    if bool(frame.duplicated(order_keys).any()):
        raise ClosureAnfisAblationError("membership records are duplicated")
    ordered = cast(
        pd.Series,
        (
        frame.sort_values(order_keys, kind="mergesort")
        .groupby(["model_id", "seed", "module", "feature"], sort=True)["center"]
        .apply(lambda series: bool(np.all(np.diff(series.to_numpy(dtype=float)) > 0.0)))
        ),
    )
    ordered_frame = (
        ordered
        .rename("ordered")
        .reset_index()
    )
    summary = (
        frame.groupby(["model_id", "module", "feature", "membership_index"], sort=True)
        .agg(
            seed_count=("seed", "nunique"),
            center_mean=("center", "mean"),
            center_sd=("center", lambda x: float(np.std(x, ddof=0))),
            width_mean=("width", "mean"),
            width_sd=("width", lambda x: float(np.std(x, ddof=0))),
        )
        .reset_index()
    )
    all_ordered = ordered_frame.groupby(["model_id", "module", "feature"], sort=True)["ordered"].all().reset_index()
    summary = summary.merge(all_ordered, on=["model_id", "module", "feature"], validate="many_to_one")
    summary = summary.rename(columns={"ordered": "centers_ordered_all_seeds"})
    summary["status"] = np.where(
        summary["seed_count"].eq(len(REGISTERED_SEEDS)),
        "available",
        "insufficient_seed_support",
    )
    return summary.loc[:, columns]


def _learning_curve(value: pd.DataFrame | None) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame(
            [
                {
                    "training_rows_per_module": size,
                    "status": "not_available",
                    "limitation": "training_size_not_completed",
                    "saturation_claim_authorized": False,
                }
                for size in (4096, 16384, 65536)
            ]
        )
    frame = value.copy()
    if "sample_size" in frame and "training_rows_per_module" not in frame:
        frame = frame.rename(columns={"sample_size": "training_rows_per_module"})
    _require_columns(frame, ("training_rows_per_module",), context="e7_learning_curve")
    frame["training_rows_per_module"] = pd.to_numeric(
        frame["training_rows_per_module"], errors="raise"
    ).astype("int64")
    registered_sizes = {4096, 16384, 65536}
    if not set(frame["training_rows_per_module"]).issubset(registered_sizes):
        raise ClosureAnfisAblationError("learning-curve size is not registered")
    if "status" not in frame:
        frame["status"] = "available"
    frame["status"] = frame["status"].astype(str)
    frame["status"] = frame["status"].replace(
        {"completed": "available", "resource_failure_recorded": "not_available"}
    )
    if not set(frame["status"]).issubset({"available", "not_available"}):
        raise ClosureAnfisAblationError("learning-curve status drifted")
    represented = set(frame["training_rows_per_module"])
    completed = set(
        frame.loc[frame["status"].eq("available"), "training_rows_per_module"]
    )
    missing = [size for size in sorted(registered_sizes) if size not in represented]
    if missing:
        supplement = pd.DataFrame(
            [
                {
                    "training_rows_per_module": size,
                    "status": "not_available",
                    "limitation": "training_size_not_completed",
                    "saturation_claim_authorized": False,
                }
                for size in missing
            ]
        )
        frame = pd.concat([frame, supplement], ignore_index=True, sort=False)
    if "limitation" not in frame:
        frame["limitation"] = ""
    frame["saturation_claim_authorized"] = False
    return frame.sort_values(["training_rows_per_module"], kind="mergesort").reset_index(drop=True)


def _report(metrics: pd.DataFrame, pairwise: pd.DataFrame, learning: pd.DataFrame) -> str:
    available_models = sorted(metrics.loc[metrics["status"].eq("available"), "model_id"].unique())
    unavailable_models = sorted(set(MODEL_IDS).difference(available_models))
    completed_sizes = sorted(
        learning.loc[learning["status"].eq("available"), "training_rows_per_module"].astype(int).unique()
    )
    return "\n".join(
        [
            "# Closure V1 E7 ANFIS ablation",
            "",
            "This locked analysis is availability-aware and uses exact common rows.",
            "It does not refit or replace an unavailable model.",
            "",
            f"- Available variants: `{', '.join(available_models) or 'none'}`",
            f"- Unavailable/no-success variants: `{', '.join(unavailable_models) or 'none'}`",
            f"- Pairwise records: `{len(pairwise)}`",
            f"- Completed learning-curve sizes: `{completed_sizes}`",
            "- Saturation claim authorized: `False`",
            "",
            "Correlation with an expert anchor is fidelity evidence, not predictive validity.",
            "",
        ]
    )


def preflight_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    if not isinstance(repo_root, Path):
        raise ClosureAnfisAblationError("E7 repository root is not a Path")
    del repo_root
    contract_sha256 = validate_component_boundary(
        authority,
        sealed_batch_contract,
        component_id=COMPONENT_ID,
        stage_id=STAGE_ID,
        output_paths=OUTPUT_PATHS,
    )
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
    context = validate_batch_context(batch_context)
    tables = cast(dict[str, pd.DataFrame], context["tables"])
    if "e7_predictions" not in tables:
        raise ClosureAnfisAblationError("batch_context lacks e7_predictions")
    predictions = _normalize_predictions(tables["e7_predictions"])
    availability = cast(Mapping[str, Any], context["model_availability"])
    sealed_availability = sealed_batch_contract.get("model_availability")
    if not isinstance(sealed_availability, Mapping) or dict(availability) != dict(
        sealed_availability
    ):
        raise ClosureAnfisAblationError("model availability is not batch-bound")
    _validate_availability(predictions, availability)
    metrics = _metric_rows(predictions, availability)
    pairwise = _pairwise_rows(predictions, availability)
    memberships = _membership_summary(tables.get("e7_memberships"))
    learning = _learning_curve(tables.get("e7_learning_curve"))
    report = _report(metrics, pairwise, learning)
    any_available = bool(metrics["status"].eq("available").any())
    artifacts = {
        OUTPUT_PATHS[0]: artifact_envelope("csv", metrics),
        OUTPUT_PATHS[1]: artifact_envelope("csv", pairwise),
        OUTPUT_PATHS[2]: artifact_envelope("csv", memberships),
        OUTPUT_PATHS[3]: artifact_envelope("csv", learning),
        OUTPUT_PATHS[4]: artifact_envelope("markdown", report, manifest_last=True),
    }
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "completed" if any_available else "completed_unavailable",
        "artifacts": artifacts,
        "tables": {
            "e7_ablation_metrics": metrics.copy(deep=True),
            "e7_ablation_pairwise": pairwise.copy(deep=True),
            "e7_membership_stability": memberships.copy(deep=True),
            "e7_learning_curve_summary": learning.copy(deep=True),
        },
        "diagnostics": {
            "component_contract_sha256": component_contract_sha256(),
            "input_row_count": int(len(predictions)),
            "available_metric_group_count": int(metrics["status"].eq("available").sum()),
            "unavailable_models": sorted(
                model for model in MODEL_IDS if availability.get(model) != "available"
            ),
            "refit_performed": False,
            "silent_row_deletion": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }
