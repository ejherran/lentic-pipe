#!/usr/bin/env python
"""Run P15 paired M0-P1 degradation with frozen Closure V2 models.

The default command is read-only. ``--execute`` materializes the physical
mask table and four lightweight result tables. After ``dvc add`` has created
the pointer, ``--finalize`` writes the report and completion manifest last.
No mode fits, recalibrates, or changes a model or threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import subprocess
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from sklearn.metrics import average_precision_score

from src.experiments import closure_phase3_context as phase3
from src.experiments.closure_contract import ClosureContractError, load_json_mapping, load_yaml_mapping
from src.experiments.closure_v2 import evaluate_models as evaluation
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT
from src.experiments.closure_v2.build_eligibility import EXPECTED_SEEDS
from src.experiments.closure_v2.hashing import canonical_json_bytes, md5_file, sha256_file


SCRIPT_PATH = Path("src/experiments/closure_v2/run_degradation.py")
ANALYSIS_PLAN = Path("configs/closure_v2/analysis_plan.yaml")
EXECUTION_GUIDE = Path("docs/closure_v2/EXECUTION_GUIDE.md")
MODEL_LOCK = Path("reports/closure_v2/00_protocol/model_lock.json")
INPUT_MANIFEST = Path("reports/closure_v2/01_surface/locked_evaluation_input_manifest.json")
EVALUATION_MANIFEST = Path("reports/closure_v2/04_evaluation/evaluation_manifest.json")
INFERENCE_MANIFEST = Path("reports/closure_v2/05_inference/inference_manifest.json")
PREDICTIONS = Path("data/closure_v2/predictions_long.parquet")
PREDICTIONS_POINTER = Path("data/closure_v2/predictions_long.parquet.dvc")
V1_REFERENCE_MANIFEST = Path("reports/closure_v2/00_protocol/v1_reference_manifest.json")
V1_MASKS = Path("data/closure_v1/degradation_masks.parquet")
V1_MASKS_POINTER = Path("data/closure_v1/degradation_masks.parquet.dvc")
MASKS = Path("data/closure_v2/degradation_masks.parquet")
MASKS_POINTER = Path("data/closure_v2/degradation_masks.parquet.dvc")
OUTPUT_ROOT = Path("reports/closure_v2/06_degradation")
METRICS = OUTPUT_ROOT / "degradation_metrics.csv"
PAIRWISE = OUTPUT_ROOT / "pairwise_effects.csv"
FAILURES = OUTPUT_ROOT / "failure_registry.csv"
AUPD = OUTPUT_ROOT / "aupd.csv"
REPORT = OUTPUT_ROOT / "DEGRADATION_REPORT.md"
MANIFEST = OUTPUT_ROOT / "degradation_manifest.json"
MATERIALIZED_OUTPUTS = (MASKS, METRICS, PAIRWISE, FAILURES, AUPD)
ALL_OUTPUTS = (*MATERIALIZED_OUTPUTS, MASKS_POINTER, REPORT, MANIFEST)

P14_COMMIT = "fc01314c36466ef678468dbad4c813e4758fa7d2"
V1_MASKS_SHA256 = "27cb48f7ac7fc63bc0aee2ce37412788d272c47aea1e2aa65a898cb32316f541"
V1_POINTER_SHA256 = "2a8529c0d277460d2c8316fc5a0ba19354013ea3013b1c6c1d994efdca89add9"
V1_POINTER_GIT_BLOB = "81c232934d8dd4c5875edd333cf8a359a8ee6b10"
V1_DVC_MD5 = "c483aab92229b79d5f77d4024c768be6"
V1_DVC_SIZE = 6037

RAW_VARIABLES = tuple(phase3.RAW_MEAN_COLUMNS)
HORIZONS = (1, 2, 3)
COHORTS = ("legacy_posthoc", "fresh_primary")
ESTIMANDS = ("observation_weighted", "site_weighted")
SCENARIOS = (
    "control",
    "mcar_10", "mcar_25", "mcar_50",
    "block_1m_10", "block_3m_10", "block_6m_25",
    "ablate_nutrients", "ablate_clarity", "ablate_oxygen",
    "combined_severe",
)
ABLATIONS = {
    "ablate_nutrients": {"mean_TP_ugL", "mean_TN_ugL"},
    "ablate_clarity": {"mean_turbidity_NTU", "mean_secchi_depth_m"},
    "ablate_oxygen": {"mean_DO_mgL"},
}
AUPD_FAMILIES = {
    "mcar": (("control", 0.0), ("mcar_10", 0.10), ("mcar_25", 0.25), ("mcar_50", 0.50)),
    "temporal_block": (("control", 0.0), ("block_1m_10", 1.0), ("block_3m_10", 3.0), ("block_6m_25", 6.0)),
}
PREEXECUTION_IMPLEMENTATION_PATHS = {
    "data/closure_v2/.gitignore",
    SCRIPT_PATH.as_posix(),
    "tests/closure_v2/test_degradation.py",
}


class DegradationError(ClosureContractError):
    """Raised when P15 crosses its frozen degradation boundary."""


def _git(*args: str, root: Path = PROJECT_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _require_regular(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise DegradationError(f"Required regular file is absent: {relative}")
    return path


def _verify_record(root: Path, record: Mapping[str, Any], *, label: str) -> None:
    relative = Path(str(record.get("path", "")))
    path = _require_regular(root, relative)
    if path.stat().st_size != record.get("bytes") or sha256_file(path) != record.get("sha256"):
        raise DegradationError(f"{label} artifact binding drifted: {relative}")


def _validate_pointer(root: Path, pointer_path: Path, physical_path: Path, record: Mapping[str, Any]) -> None:
    pointer = yaml.safe_load(_require_regular(root, pointer_path).read_text(encoding="utf-8"))
    outs = pointer.get("outs") if isinstance(pointer, Mapping) else None
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise DegradationError(f"DVC pointer is malformed: {pointer_path}")
    physical = _require_regular(root, physical_path)
    if (
        outs[0].get("path") != physical_path.name
        or outs[0].get("md5") != record.get("dvc_md5")
        or outs[0].get("size") != record.get("dvc_size")
        or md5_file(physical) != record.get("dvc_md5")
        or physical.stat().st_size != record.get("dvc_size")
    ):
        raise DegradationError(f"DVC physical binding drifted: {physical_path}")


def _validate_v1_empty_masks(root: Path) -> dict[str, Any]:
    physical = _require_regular(root, V1_MASKS)
    pointer = _require_regular(root, V1_MASKS_POINTER)
    reference = load_json_mapping(_require_regular(root, V1_REFERENCE_MANIFEST))
    tracked = reference.get("records")
    if not isinstance(tracked, list):
        raise DegradationError("V1 reference tracked-file registry is absent")
    matches = [record for record in tracked if isinstance(record, Mapping) and record.get("path") == V1_MASKS_POINTER.as_posix()]
    if len(matches) != 1 or matches[0].get("object_id") != V1_POINTER_GIT_BLOB:
        raise DegradationError("V1 degradation pointer Git binding drifted")
    parsed = yaml.safe_load(pointer.read_text(encoding="utf-8"))
    outs = parsed.get("outs") if isinstance(parsed, Mapping) else None
    if (
        sha256_file(physical) != V1_MASKS_SHA256
        or sha256_file(pointer) != V1_POINTER_SHA256
        or not isinstance(outs, list) or len(outs) != 1
        or not isinstance(outs[0], Mapping)
        or outs[0].get("md5") != V1_DVC_MD5
        or outs[0].get("size") != V1_DVC_SIZE
        or pq.read_metadata(physical).num_rows != 0
    ):
        raise DegradationError("V1 degradation-mask empty artifact drifted")
    return {
        "path": V1_MASKS.as_posix(), "sha256": V1_MASKS_SHA256,
        "dvc_pointer": V1_MASKS_POINTER.as_posix(), "dvc_md5": V1_DVC_MD5,
        "bytes": V1_DVC_SIZE, "rows": 0, "compatible": False,
        "reuse_status": "bound_by_hash_but_not_reusable_empty_v1_artifact",
    }


def validate_p14(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    head = _git("rev-parse", "HEAD", root=root)
    remote = _git("rev-parse", "origin/closure-v2", root=root)
    if head != P14_COMMIT or remote != head:
        raise DegradationError("P15 requires the exact published P14 commit")
    changed = {
        value
        for command in (("diff", "--name-only"), ("diff", "--cached", "--name-only"), ("ls-files", "--others", "--exclude-standard"))
        for value in _git(*command, root=root).splitlines()
        if value
    }
    if not changed.issubset(PREEXECUTION_IMPLEMENTATION_PATHS):
        raise DegradationError(f"Unexpected P15 pre-execution changes: {sorted(changed - PREEXECUTION_IMPLEMENTATION_PATHS)}")
    plan = load_yaml_mapping(_require_regular(root, ANALYSIS_PLAN))
    inference = plan.get("inference")
    multiplicity = plan.get("multiplicity")
    if not isinstance(inference, Mapping) or not isinstance(multiplicity, Mapping):
        raise DegradationError("Analysis-plan degradation authorities are malformed")
    families = multiplicity.get("families")
    if (
        inference.get("unit") != "source_id_plus_site_id"
        or inference.get("seed_pseudoreplication") != "forbidden"
        or multiplicity.get("method") != "holm"
        or multiplicity.get("reduce_family_for_unavailable_contrast") is not False
        or not isinstance(families, Mapping)
        or families.get("D") != ["all_registered_M0_vs_P1_degradation_contrasts"]
    ):
        raise DegradationError("Registered family-D contract drifted")
    evaluation_manifest = load_json_mapping(_require_regular(root, EVALUATION_MANIFEST))
    if any(evaluation_manifest.get(key) != value for key, value in {
        "phase": "P13", "status": "completed", "prediction_rows": 650_304,
        "refit_performed": False, "recalibration_performed": False,
        "failed_prediction_values_nulled": True, "manifest_written_last": True,
    }.items()):
        raise DegradationError("P13 evaluation authority drifted")
    for record in cast(Sequence[Mapping[str, Any]], evaluation_manifest.get("outputs", [])):
        _verify_record(root, record, label="P13")
    prediction_record = evaluation_manifest.get("data_artifact")
    if not isinstance(prediction_record, Mapping):
        raise DegradationError("P13 prediction data binding is absent")
    _verify_record(root, prediction_record, label="P13")
    _validate_pointer(root, PREDICTIONS_POINTER, PREDICTIONS, prediction_record)
    inference_manifest = load_json_mapping(_require_regular(root, INFERENCE_MANIFEST))
    if any(inference_manifest.get(key) != value for key, value in {
        "phase": "P14", "status": "completed", "authority_commit": "047c614944e66b2ba7e5229cc289ce317ba3602a",
        "bootstrap_distribution_rows": 96_000, "holm_universe_reduced": False,
        "refit_performed": False, "recalibration_performed": False,
        "manifest_written_last": True,
    }.items()):
        raise DegradationError("P14 inference authority drifted")
    for record in cast(Sequence[Mapping[str, Any]], inference_manifest.get("outputs", [])):
        _verify_record(root, record, label="P14")
    return {
        "status": "p14_effective", "head": head,
        "evaluation_manifest_sha256": sha256_file(root / EVALUATION_MANIFEST),
        "inference_manifest_sha256": sha256_file(root / INFERENCE_MANIFEST),
        "v1_degradation_masks": _validate_v1_empty_masks(root),
    }


def _payload(scenario: str, seed: int, source: str, site: str, month: str, variable: str) -> bytes:
    values = [
        "closure_v2", "P15", scenario, seed,
        unicodedata.normalize("NFC", source), unicodedata.normalize("NFC", site),
        month, variable,
    ]
    return json.dumps(values, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()


def _uniform(scenario: str, seed: int, source: str, site: str, month: str, variable: str) -> float:
    digest = hashlib.sha256(_payload(scenario, seed, source, site, month, variable)).digest()
    return int.from_bytes(digest[:8], "big", signed=False) / 18446744073709551616.0


def _mcar_mask(frame: pd.DataFrame, scenario: str, seed: int, fraction: float) -> pd.Series:
    eligible = frame["eligible"].astype(bool)
    values = [
        _uniform(scenario, seed, str(source), str(site), str(month), str(variable)) < fraction
        for source, site, month, variable in frame[["source_id", "site_id", "year_month", "raw_variable"]].itertuples(index=False, name=None)
    ]
    return pd.Series(values, index=frame.index, dtype="bool") & eligible


def _block_mask(frame: pd.DataFrame, scenario: str, seed: int, length: int, fraction: float) -> pd.Series:
    masked = pd.Series(False, index=frame.index, dtype="bool")
    for raw_key, group in frame.groupby(["source_id", "site_id", "raw_variable"], sort=True):
        source, site, variable = cast(tuple[Any, Any, Any], raw_key)
        observed = group.loc[group["eligible"].astype(bool)].copy()
        if observed.empty:
            continue
        observed["period"] = pd.PeriodIndex(observed["year_month"].astype(str), freq="M")
        observed = observed.sort_values("period").drop_duplicates("period")
        span = pd.period_range(observed["period"].min(), observed["period"].max(), freq="M")
        observed_periods = set(observed["period"])
        candidates = [
            start for start in span
            if start + (length - 1) <= span[-1]
            and all(start + offset in observed_periods for offset in range(length))
        ]
        target = max(1, math.floor(fraction * len(observed) / length + 0.5)) if candidates else 0
        ordered = sorted(
            candidates,
            key=lambda start: (_uniform(scenario, seed, str(source), str(site), str(start), str(variable)), start),
        )
        occupied: set[pd.Period] = set()
        for start in ordered:
            months = {start + offset for offset in range(length)}
            if months & occupied:
                continue
            occupied.update(months)
            if len(occupied) >= target * length:
                break
        periods = pd.PeriodIndex(group["year_month"].astype(str), freq="M")
        masked.loc[group.index] = periods.isin(occupied) & group["eligible"].to_numpy(dtype=bool)
    return masked


def _physical_cells(monthly: pd.DataFrame, cohort: str) -> pd.DataFrame:
    identity = ["source_id", "site_id", "year_month"]
    if monthly.duplicated(identity).any():
        raise DegradationError(f"Monthly physical surface is duplicated: {cohort}")
    long = monthly[[*identity, "row_present", *RAW_VARIABLES]].melt(
        id_vars=[*identity, "row_present"], value_vars=list(RAW_VARIABLES),
        var_name="raw_variable", value_name="value",
    )
    long.insert(0, "evaluation_cohort", cohort)
    long["eligible"] = long["row_present"].astype(bool) & pd.to_numeric(long["value"], errors="coerce").map(np.isfinite)
    return long.sort_values([*identity, "raw_variable"], kind="stable").reset_index(drop=True)


def _scenario_mask(base: pd.DataFrame, scenario: str, seed: int) -> pd.Series:
    if scenario == "control":
        return pd.Series(False, index=base.index, dtype="bool")
    if scenario.startswith("mcar_"):
        return _mcar_mask(base, scenario, seed, int(scenario.split("_")[1]) / 100.0)
    if scenario.startswith("block_"):
        parts = scenario.split("_")
        return _block_mask(base, scenario, seed, int(parts[1].removesuffix("m")), int(parts[2]) / 100.0)
    if scenario in ABLATIONS:
        return base["raw_variable"].isin(ABLATIONS[scenario]) & base["eligible"]
    if scenario == "combined_severe":
        removed = set().union(*ABLATIONS.values())
        return (
            _mcar_mask(base, "mcar_50", seed, 0.50)
            | _block_mask(base, "block_6m_25", seed, 6, 0.25)
            | (base["raw_variable"].isin(removed) & base["eligible"])
        )
    raise DegradationError(f"Unknown P15 scenario: {scenario}")


def build_masks(
    monthly_by_cohort: Mapping[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[tuple[str, str, int], pd.Series]]:
    rows: list[pd.DataFrame] = []
    lookup: dict[tuple[str, str, int], pd.Series] = {}
    for cohort in COHORTS:
        base = _physical_cells(monthly_by_cohort[cohort], cohort)
        for scenario in SCENARIOS:
            for seed in EXPECTED_SEEDS:
                mask = _scenario_mask(base, scenario, seed)
                if (mask & ~base["eligible"]).any():
                    raise DegradationError("A degradation mask selected an ineligible physical cell")
                lookup[(cohort, scenario, seed)] = mask.copy()
                part = base[["evaluation_cohort", "source_id", "site_id", "year_month", "raw_variable", "eligible"]].copy()
                part.insert(1, "scenario_id", scenario)
                part.insert(2, "degradation_seed", seed)
                part["masked"] = mask.to_numpy(dtype=bool)
                eligible_count = int(base["eligible"].sum())
                part["realized_fraction"] = float(mask.sum() / eligible_count) if eligible_count else 0.0
                rows.append(part)
    output = pd.concat(rows, ignore_index=True).sort_values(
        ["evaluation_cohort", "scenario_id", "degradation_seed", "source_id", "site_id", "year_month", "raw_variable"],
        kind="stable",
    ).reset_index(drop=True)
    expected = sum(len(_physical_cells(monthly_by_cohort[cohort], cohort)) for cohort in COHORTS) * len(SCENARIOS) * len(EXPECTED_SEEDS)
    if len(output) != expected or output.duplicated([
        "evaluation_cohort", "scenario_id", "degradation_seed", "source_id", "site_id", "year_month", "raw_variable",
    ]).any():
        raise DegradationError("P15 mask universe drifted")
    return output, lookup


def _mask_digest(frame: pd.DataFrame) -> str:
    selected = frame.loc[frame["masked"], ["source_id", "site_id", "year_month", "raw_variable"]]
    return hashlib.sha256(canonical_json_bytes(selected.to_dict("records"))).hexdigest()


def _apply_mask(monthly: pd.DataFrame, base: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    degraded = monthly.copy(deep=True).sort_values(["source_id", "site_id", "year_month"], kind="stable").reset_index(drop=True)
    ordered_base = base.sort_values(["source_id", "site_id", "year_month", "raw_variable"], kind="stable").reset_index(drop=True)
    ordered_mask = mask.loc[ordered_base.index].to_numpy(dtype=bool)
    matrix = ordered_mask.reshape(len(degraded), len(RAW_VARIABLES))
    observed_order = tuple(ordered_base["raw_variable"].iloc[:len(RAW_VARIABLES)].astype(str))
    expected_order = tuple(sorted(RAW_VARIABLES))
    if observed_order != expected_order:
        raise DegradationError("Raw-variable mask reshape order drifted")
    for column_index, variable in enumerate(expected_order):
        selected = matrix[:, column_index]
        degraded.loc[selected, variable] = np.nan
        stem = variable.removeprefix("mean_")
        for column in (f"std_{stem}", f"qc_ok_rate_{stem}"):
            if column in degraded:
                degraded.loc[selected, column] = np.nan
        for column in (f"n_obs_{stem}", f"n_bad_{stem}"):
            if column in degraded:
                degraded.loc[selected, column] = 0
    tp = pd.to_numeric(degraded["mean_TP_ugL"], errors="coerce")
    tn = pd.to_numeric(degraded["mean_TN_ugL"], errors="coerce")
    degraded["log_TP"] = np.log(tp + 0.1)
    degraded["log_TN"] = np.log(tn + 0.1)
    degraded["TN_TP_ratio"] = tn / tp
    return degraded


def _degraded_origins(origins: pd.DataFrame, degraded_monthly: pd.DataFrame) -> pd.DataFrame:
    ordered = origins.sort_values(["source_id", "site_id", "origin_year_month", "origin_id"], kind="stable").reset_index(drop=True).copy()
    surface = degraded_monthly.rename(columns={"year_month": "origin_year_month"})
    keys = ["source_id", "site_id", "origin_year_month"]
    replacement = ordered[keys].merge(surface[[*keys, *phase3.PHYSICAL_COLUMNS]], on=keys, how="left", validate="many_to_one", sort=False)
    if len(replacement) != len(ordered):
        raise DegradationError("Degraded origin projection changed the intent denominator")
    ordered.loc[:, list(phase3.PHYSICAL_COLUMNS)] = replacement[list(phase3.PHYSICAL_COLUMNS)].to_numpy()
    return ordered


def _adaptive_state(arrays: Mapping[str, np.ndarray], monthly: pd.DataFrame, seed: int) -> pd.DataFrame:
    features = phase3._anfis_feature_frame(monthly)
    values: dict[str, np.ndarray] = {}
    for module, channel in (("N", "N"), ("F", "F"), ("T", "T")):
        prediction, sigma = phase3._anfis_forward(arrays, seed=seed, module=module, features=features)
        values[f"y{channel}"] = prediction
        values[f"sigma_{channel}"] = sigma
    state = monthly[["source_id", "site_id", "year_month", "row_present"]].copy()
    for column, value in values.items():
        state[column] = value
    state = state.sort_values(["source_id", "site_id", "year_month"], kind="stable").reset_index(drop=True)
    prior = state.groupby(["source_id", "site_id"], sort=False)[["year_month", "row_present", "yN", "yF", "yT"]].shift(1)
    current_period = pd.PeriodIndex(state["year_month"], freq="M")
    prior_period = pd.PeriodIndex(prior["year_month"].fillna("1900-01"), freq="M")
    exact = (
        (current_period.asi8 - prior_period.asi8 == 1)
        & state["row_present"].astype(bool).to_numpy()
        & prior["row_present"].fillna(False).astype(bool).to_numpy()
    )
    for channel in ("yN", "yF", "yT"):
        delta = state[channel].to_numpy(dtype=np.float64) - pd.to_numeric(prior[channel], errors="coerce").to_numpy(dtype=np.float64)
        delta[~exact] = 0.0
        state[f"delta_{channel}"] = delta
    return state


def _load_targets(root: Path) -> pd.DataFrame:
    columns = [
        "evaluation_cohort", "model_id", "base_seed", "aggregation_level", "origin_id",
        "source_id", "site_id", "origin_year_month", "target_year_month", "horizon_months",
        "target_available", "outcome_bloom_30", "target_risk_chla_h",
    ]
    frame = pq.read_table(_require_regular(root, PREDICTIONS), columns=columns).to_pandas()
    targets = frame.loc[
        frame["model_id"].eq("P1") & frame["aggregation_level"].eq("family") & frame["base_seed"].eq(-1)
    ].drop(columns=["model_id", "base_seed", "aggregation_level"])
    if len(targets) != (4488 + 2286) * 3 or targets.duplicated(["evaluation_cohort", "origin_id", "horizon_months"]).any():
        raise DegradationError("Published P13 target projection drifted")
    return targets.reset_index(drop=True)


def _prediction_frame(
    metadata: pd.DataFrame,
    target_rows: pd.DataFrame,
    score: Mapping[str, np.ndarray],
    *,
    cohort: str,
    scenario: str,
    degradation_seed: int,
    model_id: str,
    model_seed: int,
    mask_sha256: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(metadata.to_dict("records")):
        for horizon in HORIZONS:
            column = horizon - 1
            valid = bool(score["valid"][index, column])
            rows.append({
                "evaluation_cohort": cohort, "scenario_id": scenario,
                "degradation_seed": degradation_seed, "model_id": model_id,
                "model_seed": model_seed, "origin_id": record["origin_id"],
                "source_id": record["source_id"], "site_id": record["site_id"],
                "origin_year_month": record["origin_year_month"], "horizon_months": horizon,
                "intent_to_predict": True,
                "input_eligible": str(record["base_input_status"]) == "eligible",
                "prediction_successful": valid,
                "bloom_probability": float(score["bloom"][index, column]) if valid else math.nan,
                "alert_threshold": float(score["threshold"][index, column]) if valid else math.nan,
                "predicted_risk_chla": float(score["risk"][index, column]) if valid else math.nan,
                "risk_interval_lower_90": float(score["lower"][index, column]) if valid else math.nan,
                "risk_interval_upper_90": float(score["upper"][index, column]) if valid else math.nan,
                "base_input_reason": str(record["base_input_reason"]),
                "mask_sha256": mask_sha256,
            })
    output = pd.DataFrame(rows)
    output = output.merge(
        target_rows,
        on=["evaluation_cohort", "origin_id", "source_id", "site_id", "origin_year_month", "horizon_months"],
        how="left", validate="one_to_one", sort=False,
    )
    if output["target_available"].isna().any():
        raise DegradationError("P13 target keys do not cover the degradation intent universe")
    output["target_available"] = output["target_available"].astype(bool)
    output["metric_evaluable"] = output["prediction_successful"] & output["target_available"]
    output["predicted_alert"] = (
        output["prediction_successful"]
        & (output["bloom_probability"] >= output["alert_threshold"])
    )
    output["terminal_status"] = np.where(
        ~output["input_eligible"], "input_ineligible",
        np.where(~output["prediction_successful"], "degraded_model_unavailable",
                 np.where(~output["target_available"], "target_unavailable", "success")),
    )
    output["failure_reason"] = np.where(
        output["terminal_status"].eq("input_ineligible"), output["base_input_reason"],
        np.where(output["terminal_status"].eq("degraded_model_unavailable"), "insufficient_degraded_evidence",
                 np.where(output["terminal_status"].eq("target_unavailable"), "published_target_unavailable", "")),
    )
    return output


def _weights(frame: pd.DataFrame, estimand: str) -> np.ndarray:
    if estimand == "observation_weighted":
        return np.ones(len(frame), dtype=np.float64)
    counts = frame.groupby(["source_id", "site_id"], sort=False)["origin_id"].transform("size")
    return 1.0 / counts.to_numpy(dtype=np.float64)


def _f2(y: np.ndarray, predicted: np.ndarray, weights: np.ndarray) -> float:
    tp = float(weights[(predicted == 1) & (y == 1)].sum())
    fp = float(weights[(predicted == 1) & (y == 0)].sum())
    fn = float(weights[(predicted == 0) & (y == 1)].sum())
    denominator = 5.0 * tp + 4.0 * fn + fp
    return 5.0 * tp / denominator if denominator else math.nan


def _metric_values(frame: pd.DataFrame, estimand: str, model_id: str) -> dict[str, tuple[float, str, int]]:
    evaluable = frame.loc[frame["metric_evaluable"]].copy()
    values: dict[str, tuple[float, str, int]] = {}
    if evaluable.empty:
        values.update({metric: (math.nan, "not_estimable_no_rows", 0) for metric in ("pr_auc", "brier", "f2")})
    else:
        weights = _weights(evaluable, estimand)
        y = evaluable["outcome_bloom_30"].astype(int).to_numpy()
        p = evaluable["bloom_probability"].to_numpy(dtype=np.float64)
        predicted = evaluable["predicted_alert"].astype(int).to_numpy()
        values["pr_auc"] = (
            float(average_precision_score(y, p, sample_weight=weights)) if len(np.unique(y)) == 2 else math.nan,
            "estimated" if len(np.unique(y)) == 2 else "not_estimable_single_class", len(evaluable),
        )
        values["brier"] = (float(np.average((p - y) ** 2, weights=weights)), "estimated", len(evaluable))
        f2 = _f2(y, predicted, weights)
        values["f2"] = (f2, "estimated" if math.isfinite(f2) else "not_estimable_no_positive_decision_mass", len(evaluable))
    values["availability"] = (float(frame["prediction_successful"].mean()), "estimated", len(frame))
    values["failure_rate"] = (float((~frame["prediction_successful"]).mean()), "estimated", len(frame))
    interval = evaluable.loc[
        evaluable["risk_interval_lower_90"].notna()
        & evaluable["risk_interval_upper_90"].notna()
        & evaluable["target_risk_chla_h"].notna()
    ]
    if model_id == "M0":
        for metric in ("picp", "mpiw", "winkler"):
            values[metric] = (math.nan, "not_applicable_distinct_type2_interval_semantics", 0)
    elif interval.empty:
        for metric in ("picp", "mpiw", "winkler"):
            values[metric] = (math.nan, "not_estimable_no_interval_rows", 0)
    else:
        weights = _weights(interval, estimand)
        target = interval["target_risk_chla_h"].to_numpy(dtype=np.float64)
        lower = interval["risk_interval_lower_90"].to_numpy(dtype=np.float64)
        upper = interval["risk_interval_upper_90"].to_numpy(dtype=np.float64)
        width = upper - lower
        penalty = np.where(target < lower, 20.0 * (lower - target), np.where(target > upper, 20.0 * (target - upper), 0.0))
        values["picp"] = (float(np.average((target >= lower) & (target <= upper), weights=weights)), "descriptive_available", len(interval))
        values["mpiw"] = (float(np.average(width, weights=weights)), "descriptive_available", len(interval))
        values["winkler"] = (float(np.average(width + penalty, weights=weights)), "descriptive_available", len(interval))
    return values


def _metric_rows(frame: pd.DataFrame, *, estimand: str, shared_success: int) -> list[dict[str, Any]]:
    first = frame.iloc[0]
    values = _metric_values(frame, estimand, str(first["model_id"]))
    base = {
        "evaluation_cohort": first["evaluation_cohort"], "scenario_id": first["scenario_id"],
        "degradation_seed": int(first["degradation_seed"]), "model_id": first["model_id"],
        "model_seed": int(first["model_seed"]), "horizon_months": int(first["horizon_months"]),
        "estimand": estimand, "attempted": len(frame),
        "input_eligible": int(frame["input_eligible"].sum()),
        "prediction_successful": int(frame["prediction_successful"].sum()),
        "target_available": int(frame["target_available"].sum()),
        "metric_evaluable": int(frame["metric_evaluable"].sum()),
        "shared_success": shared_success, "mask_sha256": first["mask_sha256"],
    }
    return [
        {**base, "metric": metric, "estimate": estimate, "metric_rows": rows, "status": status}
        for metric, (estimate, status, rows) in values.items()
    ]


def _pairwise_rows(left: pd.DataFrame, right: pd.DataFrame, *, estimand: str) -> tuple[list[dict[str, Any]], int]:
    keys = ["evaluation_cohort", "scenario_id", "degradation_seed", "origin_id", "source_id", "site_id", "origin_year_month", "horizon_months"]
    fields = [*keys, "prediction_successful", "target_available", "metric_evaluable", "bloom_probability", "predicted_alert", "outcome_bloom_30", "mask_sha256"]
    paired = left[fields].merge(right[fields], on=keys, how="outer", validate="one_to_one", suffixes=("_m0", "_p1"), indicator=True)
    if not paired["_merge"].eq("both").all() or not paired["mask_sha256_m0"].equals(paired["mask_sha256_p1"]):
        raise DegradationError("M0/P1 intent or common-mask pairing drifted")
    shared = paired.loc[
        paired["metric_evaluable_m0"] & paired["metric_evaluable_p1"]
    ].copy()
    first = paired.iloc[0]
    base = {
        "evaluation_cohort": first["evaluation_cohort"], "scenario_id": first["scenario_id"],
        "degradation_seed": int(first["degradation_seed"]), "aggregation_level": "seed",
        "horizon_months": int(first["horizon_months"]), "estimand": estimand,
        "comparison_id": "M0_vs_P1", "challenger": "M0", "reference": "P1",
        "attempted_pairs": len(paired), "shared_success_rows": len(shared),
        "shared_success_locations": int(shared[["source_id", "site_id"]].drop_duplicates().shape[0]),
        "mask_sha256": first["mask_sha256_m0"], "seed_pseudoreplication": False,
    }
    rows: list[dict[str, Any]] = []
    if shared.empty:
        for metric in ("pr_auc", "brier", "f2"):
            rows.append({**base, "metric": metric, "m0_estimate": math.nan, "p1_estimate": math.nan, "delta_m0_minus_p1": math.nan, "status": "not_estimable_no_shared_success"})
        return rows, 0
    weights = _weights(shared, estimand)
    y = shared["outcome_bloom_30_m0"].astype(int).to_numpy()
    if not shared["outcome_bloom_30_m0"].equals(shared["outcome_bloom_30_p1"]):
        raise DegradationError("M0/P1 paired outcomes drifted")
    estimates: dict[str, tuple[float, float, str]] = {}
    m0p = shared["bloom_probability_m0"].to_numpy(dtype=np.float64)
    p1p = shared["bloom_probability_p1"].to_numpy(dtype=np.float64)
    if len(np.unique(y)) == 2:
        estimates["pr_auc"] = (
            float(average_precision_score(y, m0p, sample_weight=weights)),
            float(average_precision_score(y, p1p, sample_weight=weights)), "estimated",
        )
    else:
        estimates["pr_auc"] = (math.nan, math.nan, "not_estimable_single_class")
    estimates["brier"] = (
        float(np.average((m0p - y) ** 2, weights=weights)),
        float(np.average((p1p - y) ** 2, weights=weights)), "estimated",
    )
    estimates["f2"] = (
        _f2(y, shared["predicted_alert_m0"].astype(int).to_numpy(), weights),
        _f2(y, shared["predicted_alert_p1"].astype(int).to_numpy(), weights), "estimated",
    )
    for metric, (m0, p1, status) in estimates.items():
        rows.append({
            **base, "metric": metric, "m0_estimate": m0, "p1_estimate": p1,
            "delta_m0_minus_p1": m0 - p1 if math.isfinite(m0) and math.isfinite(p1) else math.nan,
            "status": status,
        })
    return rows, len(shared)


def _family_pairwise(rows: pd.DataFrame) -> pd.DataFrame:
    keys = ["evaluation_cohort", "scenario_id", "horizon_months", "estimand", "comparison_id", "challenger", "reference", "metric"]
    family = rows.groupby(keys, sort=True, as_index=False).agg(
        degradation_seed=("degradation_seed", lambda values: -1),
        aggregation_level=("aggregation_level", lambda values: "family_mean_over_registered_seeds"),
        attempted_pairs=("attempted_pairs", "min"),
        shared_success_rows=("shared_success_rows", "min"),
        shared_success_locations=("shared_success_locations", "min"),
        mask_sha256=("mask_sha256", lambda values: "five_registered_mask_slots"),
        seed_pseudoreplication=("seed_pseudoreplication", "max"),
        m0_estimate=("m0_estimate", "mean"), p1_estimate=("p1_estimate", "mean"),
        delta_m0_minus_p1=("delta_m0_minus_p1", "mean"),
        delta_seed_sd=("delta_m0_minus_p1", "std"),
        registered_seed_slots=("degradation_seed", "nunique"),
        status=("status", lambda values: "descriptive_available" if all(value == "estimated" for value in values) else "not_estimable_incomplete_seed_family"),
    )
    if not family["registered_seed_slots"].eq(len(EXPECTED_SEEDS)).all():
        raise DegradationError("Pairwise family lost a registered seed slot")
    family["crossover_status"] = "not_assessed_on_single_scenario_row"
    for cohort in COHORTS:
        for horizon in HORIZONS:
            for estimand in ESTIMANDS:
                part = family.loc[
                    family["evaluation_cohort"].eq(cohort)
                    & family["horizon_months"].eq(horizon)
                    & family["estimand"].eq(estimand)
                ]
                for family_name, levels in AUPD_FAMILIES.items():
                    signs: list[int] = []
                    for scenario, _ in levels:
                        pr = part.loc[part["scenario_id"].eq(scenario) & part["metric"].eq("pr_auc"), "delta_m0_minus_p1"]
                        br = part.loc[part["scenario_id"].eq(scenario) & part["metric"].eq("brier"), "delta_m0_minus_p1"]
                        if len(pr) != 1 or len(br) != 1 or not np.isfinite(pr.iloc[0]) or not np.isfinite(br.iloc[0]):
                            signs.append(0)
                        else:
                            signs.append(1 if pr.iloc[0] > 0 and br.iloc[0] < 0 else -1 if pr.iloc[0] < 0 and br.iloc[0] > 0 else 0)
                    supported = any(signs[index] != 0 and signs[index + 1] == -signs[index] for index in range(len(signs) - 1))
                    status = f"supported_{family_name}_joint_pr_auc_brier" if supported else f"not_supported_{family_name}"
                    index = part.index[part["scenario_id"].isin([scenario for scenario, _ in levels])]
                    existing = family.loc[index, "crossover_status"].astype(str)
                    family.loc[index, "crossover_status"] = np.where(existing.eq("not_assessed_on_single_scenario_row"), status, existing + ";" + status)
    return family[rows.columns.tolist() + ["delta_seed_sd", "registered_seed_slots", "crossover_status"]]


def _aupd(metrics: pd.DataFrame) -> pd.DataFrame:
    selected = metrics.loc[metrics["metric"].isin(["pr_auc", "brier"])].copy()
    rows: list[dict[str, Any]] = []
    keys = ["evaluation_cohort", "model_id", "model_seed", "degradation_seed", "horizon_months", "estimand", "metric"]
    for raw_key, group in selected.groupby(keys, sort=True):
        cohort, model, model_seed, degradation_seed, horizon, estimand, metric = cast(tuple[Any, ...], raw_key)
        by_scenario = group.set_index("scenario_id")
        for family_name, levels in AUPD_FAMILIES.items():
            estimates = [float(by_scenario.loc[scenario, "estimate"]) if scenario in by_scenario.index else math.nan for scenario, _ in levels]
            baseline = estimates[0]
            retention = [
                value / baseline if metric == "pr_auc" and math.isfinite(value) and math.isfinite(baseline) and baseline != 0
                else baseline / value if metric == "brier" and math.isfinite(value) and math.isfinite(baseline) and value != 0
                else math.nan
                for value in estimates
            ]
            x = np.asarray([level for _, level in levels], dtype=np.float64)
            y = np.asarray(retention, dtype=np.float64)
            value = float(np.trapezoid(y, x) / (x[-1] - x[0])) if np.isfinite(y).all() else math.nan
            rows.append({
                "evaluation_cohort": cohort, "model_id": model, "model_seed": int(model_seed),
                "degradation_seed": int(degradation_seed), "aggregation_level": "seed",
                "horizon_months": int(horizon), "estimand": estimand,
                "degradation_family": family_name, "metric": metric,
                "retention_orientation": "higher" if metric == "pr_auc" else "lower",
                "aupd": value, "status": "estimated" if math.isfinite(value) else "not_estimable",
            })
    seed = pd.DataFrame(rows)
    family_keys = ["evaluation_cohort", "model_id", "horizon_months", "estimand", "degradation_family", "metric", "retention_orientation"]
    family = seed.groupby(family_keys, sort=True, as_index=False).agg(
        model_seed=("model_seed", lambda values: -1), degradation_seed=("degradation_seed", lambda values: -1),
        aggregation_level=("aggregation_level", lambda values: "family_mean_over_registered_seeds"),
        aupd=("aupd", "mean"), aupd_seed_sd=("aupd", "std"), registered_seed_slots=("degradation_seed", "nunique"),
        status=("status", lambda values: "descriptive_available" if all(value == "estimated" for value in values) else "not_estimable_incomplete_seed_family"),
    )
    seed["aupd_seed_sd"] = math.nan
    seed["registered_seed_slots"] = 1
    return pd.concat([seed, family], ignore_index=True, sort=False).sort_values(
        ["evaluation_cohort", "model_id", "aggregation_level", "horizon_months", "estimand", "degradation_family", "metric", "degradation_seed"], kind="stable"
    ).reset_index(drop=True)


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    pq.write_table(
        pa.Table.from_pandas(frame, preserve_index=False), buffer,
        compression="zstd", use_dictionary=True, write_statistics=True, data_page_version="1.0",
    )
    return buffer.getvalue()


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _exclusive_bundle(contents: Sequence[tuple[Path, bytes]], *, root: Path) -> None:
    created: list[tuple[Path, int]] = []
    temporaries: list[Path] = []
    try:
        for relative, payload in contents:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise DegradationError(f"Refusing to overwrite P15 output: {relative}")
            temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
            temporaries.append(temporary)
            with temporary.open("xb") as handle:
                handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            os.link(temporary, destination)
            created.append((destination, destination.stat().st_ino))
            temporary.unlink()
    except BaseException:
        for destination, inode in reversed(created):
            if destination.is_file() and not destination.is_symlink() and destination.stat().st_ino == inode:
                destination.unlink()
        raise
    finally:
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)


def _load_runtime(root: Path) -> tuple[
    dict[str, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]],
    dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, np.ndarray],
    dict[tuple[str, int, int], Mapping[str, Any]], dict[tuple[str, int, int], float],
    dict[tuple[str, int, int, str], float], pd.DataFrame,
]:
    cohorts = evaluation._load_cohorts(root)
    arrays, warmup, _, _ = phase3._load_overlay(root)
    specs, thresholds, conformal = evaluation._load_calibration(root)
    monthly: dict[str, pd.DataFrame] = {}
    bases: dict[str, pd.DataFrame] = {}
    for cohort, (intents, history, _) in cohorts.items():
        sites = set(intents["site_id"].astype(str))
        cohort_warmup = warmup.loc[warmup["site_id"].astype(str).isin(sites)].copy()
        monthly[cohort] = phase3._deduplicated_month_surface(history, cohort_warmup)
        bases[cohort] = _physical_cells(monthly[cohort], cohort)
    return cohorts, monthly, bases, arrays, specs, thresholds, conformal, _load_targets(root)


def build_tables(root: Path = PROJECT_ROOT) -> dict[str, pd.DataFrame]:
    cohorts, monthly_by_cohort, bases, arrays, specs, thresholds, conformal, targets = _load_runtime(root)
    masks, mask_lookup = build_masks(monthly_by_cohort)
    metric_rows: list[dict[str, Any]] = []
    pairwise_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    for cohort in COHORTS:
        intents, history, origins = cohorts[cohort]
        target_rows = targets.loc[targets["evaluation_cohort"].eq(cohort)].copy()
        for scenario in SCENARIOS:
            for seed in EXPECTED_SEEDS:
                mask = mask_lookup[(cohort, scenario, seed)]
                degraded_monthly = _apply_mask(monthly_by_cohort[cohort], bases[cohort], mask)
                state = _adaptive_state(arrays, degraded_monthly, seed)
                metadata, valid = evaluation._sequence_frame(intents, history, state)
                p1_score = evaluation._temporal_scores("P1", seed, metadata, valid, specs, thresholds, conformal, root=root)
                degraded_origins = _degraded_origins(origins, degraded_monthly)
                phase_m0 = phase3._load_m0_predictions(degraded_origins)[("M0", 1729)]
                m0_score = evaluation._empty_score(len(metadata))
                m0_score["valid"] = phase_m0["valid"].astype(bool)
                m0_score["bloom"] = phase_m0["bloom_raw"].astype(np.float64)
                m0_score["risk"] = phase_m0["continuous"].astype(np.float64)
                m0_score["threshold"][m0_score["valid"]] = 0.5
                mask_part = masks.loc[
                    masks["evaluation_cohort"].eq(cohort)
                    & masks["scenario_id"].eq(scenario)
                    & masks["degradation_seed"].eq(seed)
                ]
                digest = _mask_digest(mask_part)
                m0 = _prediction_frame(metadata, target_rows, m0_score, cohort=cohort, scenario=scenario, degradation_seed=seed, model_id="M0", model_seed=1729, mask_sha256=digest)
                p1 = _prediction_frame(metadata, target_rows, p1_score, cohort=cohort, scenario=scenario, degradation_seed=seed, model_id="P1", model_seed=seed, mask_sha256=digest)
                for horizon in HORIZONS:
                    m0_h = m0.loc[m0["horizon_months"].eq(horizon)].copy()
                    p1_h = p1.loc[p1["horizon_months"].eq(horizon)].copy()
                    for estimand in ESTIMANDS:
                        paired, shared_count = _pairwise_rows(m0_h, p1_h, estimand=estimand)
                        pairwise_rows.extend(paired)
                        metric_rows.extend(_metric_rows(m0_h, estimand=estimand, shared_success=shared_count))
                        metric_rows.extend(_metric_rows(p1_h, estimand=estimand, shared_success=shared_count))
                    for model_frame in (m0_h, p1_h):
                        for (status, reason), group in model_frame.groupby(["terminal_status", "failure_reason"], sort=True, dropna=False):
                            failure_rows.append({
                                "evaluation_cohort": cohort, "scenario_id": scenario,
                                "degradation_seed": seed, "model_id": str(model_frame["model_id"].iloc[0]),
                                "model_seed": int(model_frame["model_seed"].iloc[0]), "horizon_months": horizon,
                                "terminal_status": status, "failure_reason": reason,
                                "rows": len(group), "locations": int(group[["source_id", "site_id"]].drop_duplicates().shape[0]),
                                "intent_rows_preserved": True, "mask_sha256": digest,
                            })
    metrics = pd.DataFrame(metric_rows).sort_values(
        ["evaluation_cohort", "scenario_id", "degradation_seed", "model_id", "horizon_months", "estimand", "metric"], kind="stable"
    ).reset_index(drop=True)
    pair_seed = pd.DataFrame(pairwise_rows).sort_values(
        ["evaluation_cohort", "scenario_id", "degradation_seed", "horizon_months", "estimand", "metric"], kind="stable"
    ).reset_index(drop=True)
    pair_seed["delta_seed_sd"] = math.nan
    pair_seed["registered_seed_slots"] = 1
    pair_seed["crossover_status"] = "not_assessed_on_single_seed_row"
    pairwise = pd.concat([pair_seed, _family_pairwise(pair_seed.drop(columns=["delta_seed_sd", "registered_seed_slots", "crossover_status"]))], ignore_index=True, sort=False)
    failures = pd.DataFrame(failure_rows).sort_values(
        ["evaluation_cohort", "scenario_id", "degradation_seed", "model_id", "horizon_months", "terminal_status", "failure_reason"], kind="stable"
    ).reset_index(drop=True)
    if failures.groupby(["evaluation_cohort", "scenario_id", "degradation_seed", "model_id", "horizon_months"], sort=False)["rows"].sum().nunique() > 2:
        raise DegradationError("Failure registry did not preserve intent denominators")
    return {"masks": masks, "metrics": metrics, "pairwise": pairwise, "failures": failures, "aupd": _aupd(metrics)}


def preflight(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_p14(root)
    cohorts, monthly, _, _, _, _, _, targets = _load_runtime(root)
    return {
        **authority, "status": "ready_for_paired_degradation",
        "scenarios": list(SCENARIOS), "registered_seeds": list(EXPECTED_SEEDS),
        "cohorts": {
            cohort: {"intent_origins": len(cohorts[cohort][0]), "locations": int(cohorts[cohort][0]["site_id"].nunique()), "physical_months": len(monthly[cohort])}
            for cohort in COHORTS
        },
        "published_target_rows": len(targets), "models": ["M0", "P1"],
        "same_masks_per_pair": True, "refit_performed": False, "recalibration_performed": False,
        "outputs_absent": all(not (root / path).exists() and not (root / path).is_symlink() for path in ALL_OUTPUTS),
        "writes_performed": False, "outcomes_reopened": False,
    }


def execute(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_p14(root)
    if any((root / path).exists() or (root / path).is_symlink() for path in ALL_OUTPUTS):
        raise DegradationError("P15 output namespace is not empty")
    guard = root / "tmp/closure_v2_degradation.guard"
    guard.parent.mkdir(parents=True, exist_ok=True)
    try:
        guard.mkdir()
    except FileExistsError as error:
        raise DegradationError("P15 degradation guard already exists") from error
    try:
        tables = build_tables(root)
        payloads = {
            MASKS: _parquet_bytes(tables["masks"]), METRICS: _csv_bytes(tables["metrics"]),
            PAIRWISE: _csv_bytes(tables["pairwise"]), FAILURES: _csv_bytes(tables["failures"]),
            AUPD: _csv_bytes(tables["aupd"]),
        }
        _exclusive_bundle([(path, payloads[path]) for path in MATERIALIZED_OUTPUTS], root=root)
        return {
            "status": "paired_degradation_materialized_unfinalized", "authority": authority,
            "mask_rows": len(tables["masks"]), "metric_rows": len(tables["metrics"]),
            "pairwise_rows": len(tables["pairwise"]), "failure_rows": len(tables["failures"]),
            "aupd_rows": len(tables["aupd"]), "same_masks_per_pair": True,
            "refit_performed": False, "recalibration_performed": False, "outcomes_reopened": False,
            "next_required": ".venv/bin/dvc add data/closure_v2/degradation_masks.parquet then --finalize",
        }
    finally:
        guard.rmdir()


def _report_bytes(root: Path) -> bytes:
    metrics = pd.read_csv(_require_regular(root, METRICS))
    pairwise = pd.read_csv(_require_regular(root, PAIRWISE))
    aupd = pd.read_csv(_require_regular(root, AUPD))
    family = pairwise.loc[
        pairwise["aggregation_level"].eq("family_mean_over_registered_seeds")
        & pairwise["estimand"].eq("observation_weighted")
        & pairwise["metric"].isin(["pr_auc", "brier"])
    ]
    crossover = sorted(set(family["crossover_status"].dropna().astype(str)))
    interval = metrics.loc[
        metrics["model_id"].eq("P1") & metrics["scenario_id"].eq("control")
        & metrics["estimand"].eq("observation_weighted") & metrics["metric"].isin(["picp", "mpiw", "winkler"])
    ]
    family_aupd = aupd.loc[
        aupd["aggregation_level"].eq("family_mean_over_registered_seeds")
        & aupd["estimand"].eq("observation_weighted")
    ]
    lines = [
        "# Closure V2 paired degradation report", "",
        "P15 applied identical deterministic raw-input masks to frozen M0 and P1 inference. It did not fit, recalibrate, replace a seed, change a threshold, reopen outcomes, or pool cohorts/estimands.", "",
        "## Mask authority", "",
        f"The V1 mask artifact is bound by SHA-256 `{V1_MASKS_SHA256}` and DVC MD5 `{V1_DVC_MD5}`, but contains zero rows. It is therefore historical evidence, not a reusable degradation surface. V2 masks use the guide's explicit categories and the previously sealed V1 MCAR/block intensities with a namespaced SHA-256 RNG.", "",
        "## Observation-weighted family effects", "", family.to_markdown(index=False), "",
        "## P1 interval diagnostics under control", "", interval.to_markdown(index=False), "",
        "M0 PICP/MPIW/Winkler are `not_applicable_distinct_type2_interval_semantics`; no type-2 interval was equated with P1's propagated probabilistic split-conformal interval.", "",
        "## Robustness AUPD", "", family_aupd.to_markdown(index=False), "",
        "## Crossover", "", "Crossover requires a joint direction reversal in both PR-AUC and Brier across adjacent registered levels. Recorded statuses: " + ", ".join(f"`{value}`" for value in crossover) + ".", "",
        "## Boundaries", "",
        "`fresh_primary` remains internal evaluation on unused WQP monitoring locations, not external validation. `legacy_posthoc` remains retrospective/complementary. Family D is retained, but raw/Holm p-values are not manufactured because a degradation p-value formula and directional alternative were not predeclared. Results are descriptive and do not establish field causality or official recommendations.", "",
        f"- P14 authority commit: `{P14_COMMIT}`",
        f"- P14 inference manifest SHA-256: `{sha256_file(root / INFERENCE_MANIFEST)}`",
        f"- degradation script SHA-256: `{sha256_file(root / SCRIPT_PATH)}`", "",
    ]
    return "\n".join(lines).encode("utf-8")


def _record(relative: Path, *, root: Path, role: str) -> dict[str, Any]:
    path = _require_regular(root, relative)
    return {"path": relative.as_posix(), "role": role, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def finalize(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    if (root / REPORT).exists() or (root / REPORT).is_symlink() or (root / MANIFEST).exists() or (root / MANIFEST).is_symlink():
        raise DegradationError("P15 final report or manifest already exists")
    for path in (*MATERIALIZED_OUTPUTS, MASKS_POINTER):
        _require_regular(root, path)
    pointer = yaml.safe_load((root / MASKS_POINTER).read_text(encoding="utf-8"))
    outs = pointer.get("outs") if isinstance(pointer, Mapping) else None
    physical = root / MASKS
    if (
        not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping)
        or outs[0].get("path") != MASKS.name or outs[0].get("size") != physical.stat().st_size
        or outs[0].get("md5") != md5_file(physical)
    ):
        raise DegradationError("P15 mask DVC pointer does not bind its physical table")
    masks = pq.read_table(physical).to_pandas()
    metrics = pd.read_csv(root / METRICS)
    pairwise = pd.read_csv(root / PAIRWISE)
    failures = pd.read_csv(root / FAILURES)
    aupd = pd.read_csv(root / AUPD)
    expected_slots = len(COHORTS) * len(SCENARIOS) * len(EXPECTED_SEEDS)
    if (
        masks.groupby(["evaluation_cohort", "scenario_id", "degradation_seed"]).ngroups != expected_slots
        or not set(metrics["metric"]) == {"pr_auc", "brier", "f2", "picp", "mpiw", "winkler", "availability", "failure_rate"}
        or not pairwise.loc[pairwise["aggregation_level"].eq("family_mean_over_registered_seeds"), "registered_seed_slots"].eq(5).all()
        or failures.empty or aupd.empty
    ):
        raise DegradationError("P15 materialized tables failed final validation")
    report = _report_bytes(root)
    manifest = {
        "schema_version": "closure_v2_degradation_manifest_v1",
        "experiment_id": "closure_v2", "phase": "P15", "status": "completed",
        "authority_commit": P14_COMMIT,
        "script": _record(SCRIPT_PATH, root=root, role="paired_degradation_runner"),
        "inputs": [
            _record(path, root=root, role=role)
            for path, role in (
                (ANALYSIS_PLAN, "locked_analysis_plan"), (EXECUTION_GUIDE, "public_execution_guide"),
                (MODEL_LOCK, "locked_model_registry"), (INPUT_MANIFEST, "locked_evaluation_inputs"),
                (EVALUATION_MANIFEST, "p13_evaluation_manifest"), (INFERENCE_MANIFEST, "p14_inference_manifest"),
                (PREDICTIONS_POINTER, "p13_prediction_pointer"), (V1_REFERENCE_MANIFEST, "v1_reference_manifest"),
                (V1_MASKS_POINTER, "v1_empty_mask_pointer"),
            )
        ],
        "v1_mask_binding": _validate_v1_empty_masks(root),
        "data_artifact": {
            "path": MASKS.as_posix(), "role": "common_m0_p1_degradation_masks",
            "bytes": physical.stat().st_size, "sha256": sha256_file(physical),
            "rows": len(masks), "dvc_pointer": MASKS_POINTER.as_posix(),
            "dvc_md5": outs[0]["md5"], "dvc_size": outs[0]["size"],
        },
        "outputs": [
            _record(path, root=root, role="degradation_output")
            for path in (METRICS, PAIRWISE, FAILURES, AUPD, MASKS_POINTER)
        ] + [{"path": REPORT.as_posix(), "role": "degradation_output", "bytes": len(report), "sha256": hashlib.sha256(report).hexdigest()}],
        "scenarios": list(SCENARIOS), "registered_seeds": list(EXPECTED_SEEDS),
        "evaluation_cohorts": list(COHORTS), "estimands": list(ESTIMANDS),
        "mask_slot_count": expected_slots, "mask_rows": len(masks),
        "metric_rows": len(metrics), "pairwise_rows": len(pairwise),
        "failure_registry_rows": len(failures), "aupd_rows": len(aupd),
        "same_masks_per_m0_p1_pair": True, "intent_origins_preserved": True,
        "seed_pseudoreplication": False, "cohorts_pooled": False, "estimands_pooled": False,
        "refit_performed": False, "recalibration_performed": False,
        "outcomes_reopened": False, "threshold_changed": False,
        "m0_p1_interval_semantics_equated": False,
        "holm_family_D_retained": True, "raw_p_values_computed": False,
        "holm_p_values_computed": False,
        "p_value_absence_reason": "degradation_p_value_formula_and_directional_alternative_not_predeclared",
        "crossover_rule": "joint_pr_auc_and_brier_direction_reversal_across_adjacent_registered_levels",
        "manifest_written_last": True,
    }
    _exclusive_bundle([(REPORT, report), (MANIFEST, canonical_json_bytes(manifest))], root=root)
    return {
        "status": "paired_degradation_completed", "mask_rows": len(masks),
        "mask_dvc_md5": outs[0]["md5"], "mask_dvc_size": outs[0]["size"],
        "report_sha256": sha256_file(root / REPORT), "manifest_sha256": sha256_file(root / MANIFEST),
        "manifest_written_last": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--execute", action="store_true")
    group.add_argument("--finalize", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute() if args.execute else finalize() if args.finalize else preflight()
    print(canonical_json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
