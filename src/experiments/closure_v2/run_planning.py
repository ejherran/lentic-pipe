#!/usr/bin/env python
"""Run P16 frozen-P1 counterfactual planning for Closure V2.

The default command is a read-only preflight. ``--execute`` applies the ten
locked raw-proxy scenarios at each origin, propagates them through frozen P1
rollouts, and materializes the physical origin table plus lightweight
summaries. After ``dvc add``, ``--finalize`` writes the report and manifest
last. No mode fits, recalibrates, or changes a model or threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.experiments import closure_phase3_context as phase3
from src.experiments.closure_contract import ClosureContractError, load_json_mapping, load_yaml_mapping
from src.experiments.closure_v2 import evaluate_models as evaluation
from src.experiments.closure_v2 import run_degradation as degradation
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT
from src.experiments.closure_v2.build_eligibility import EXPECTED_SEEDS, INPUT_COLUMNS
from src.experiments.closure_v2.calibrate_temporal import _load_model, recursive_predictions
from src.experiments.closure_v2.hashing import canonical_json_bytes, md5_file, sha256_file
from src.experiments.evaluate_planning_inference import (
    ACTION_SCENARIOS,
    BASELINE_SCENARIO,
    BOOTSTRAP_REPLICATES,
    PRIMARY_COST_WEIGHT,
    PRIMARY_SUPPORT_WEIGHT,
    PRIMARY_UNCERTAINTY_WEIGHT,
    SENSITIVITY_MULTIPLIERS,
    _bootstrap,
    _coherence,
    _sensitivity,
)


SCRIPT_PATH = Path("src/experiments/closure_v2/run_planning.py")
ANALYSIS_PLAN = Path("configs/closure_v2/analysis_plan.yaml")
EXECUTION_GUIDE = Path("docs/closure_v2/EXECUTION_GUIDE.md")
MODEL_LOCK = Path("reports/closure_v2/00_protocol/model_lock.json")
P15_MANIFEST = Path("reports/closure_v2/06_degradation/degradation_manifest.json")
EXPERIMENTAL_MATRIX = Path("configs/closure_v1/experimental_matrix.yaml")
LEGACY_CATALOG = Path("configs/counterfactual_planning_v1.yaml")
VARIABLES_CONFIG = Path("configs/variables.yaml")
ASSIGNMENT = Path("data/closure_v1/closure_holdout_assignment.csv")
PANEL = Path("data/panel/panel_monthly_v0.parquet")
PANEL_POINTER = Path("data/panel/panel_monthly_v0.parquet.dvc")
V1_PLANNING = Path("reports/closure_v1/09_planning/planning_origin_deltas.parquet")
V1_PLANNING_POINTER = Path("reports/closure_v1/09_planning/planning_origin_deltas.parquet.dvc")
OUTPUT_ROOT = Path("reports/closure_v2/07_planning")
ORIGIN_DELTAS = OUTPUT_ROOT / "planning_origin_deltas.parquet"
ORIGIN_POINTER = OUTPUT_ROOT / "planning_origin_deltas.parquet.dvc"
BOOTSTRAP = OUTPUT_ROOT / "planning_bootstrap.csv"
SENSITIVITY = OUTPUT_ROOT / "planning_sensitivity.csv"
COHERENCE = OUTPUT_ROOT / "ecological_coherence.csv"
REPORT = OUTPUT_ROOT / "PLANNING_REPORT.md"
MANIFEST = OUTPUT_ROOT / "planning_manifest.json"
MATERIALIZED_OUTPUTS = (ORIGIN_DELTAS, BOOTSTRAP, SENSITIVITY, COHERENCE)
ALL_OUTPUTS = (*MATERIALIZED_OUTPUTS, ORIGIN_POINTER, REPORT, MANIFEST)

P15_COMMIT = "0af1bff01cbb581886ce34c697fbd8b731e2553a"
EXPERIMENTAL_MATRIX_SHA256 = "9291db8a53f3fd7b5c199d0496eb09b20cef62f9f10347aa29858349efa352e6"
LEGACY_CATALOG_SHA256 = "ee594a4bece416a60e962437aadc826f019b8015433860d18a1b3cd8435d2648"
VARIABLES_SHA256 = "e945ae0fb7ccb4cd2cb9c742c7177e45a17bb8f96217b971259c0d61ef11cc57"
ASSIGNMENT_SHA256 = "b090994b9ec9a3cd6af8e3261879872a12efe301e02fe1727ded519b46ebedef"
PANEL_SHA256 = "8aedc531b9e024bd8f73e66f917932b8301f79309d4596618c5a839e3b70dc62"
PANEL_POINTER_SHA256 = "eb34b0b5578c40f1e7984ee0698786efd8eea116ec125d7c7f4507ddfacdad9c"
PANEL_DVC_MD5 = "9aeaac8466f16cae4ef4164980899059"
PANEL_BYTES = 103_469_973
V1_PLANNING_SHA256 = "64fe67eaac3560da9fec04a1e696c98a1e0f10e0d85cdaa8549689a12493fcc6"
V1_PLANNING_POINTER_SHA256 = "5ee258a17b590c4b85ca2f804838cea2cf5388426ab075fbfb2e9b4c30d432d8"
V1_PLANNING_DVC_MD5 = "f67f23c22af0056b67852cc645703d19"
V1_PLANNING_BYTES = 7_788
P15_MANIFEST_SHA256 = "6c5f3aa93900e256b6187fbfd15603befaa19acabc94a80f0e7094efe7789d03"

COHORTS = ("legacy_posthoc", "fresh_primary")
HORIZONS = (1, 2, 3)
SCENARIO_IDS = (BASELINE_SCENARIO, *ACTION_SCENARIOS)
ACTION_COLUMNS = (
    "mean_TP_ugL", "mean_TN_ugL", "mean_secchi_depth_m",
    "mean_turbidity_NTU", "mean_DO_mgL",
)
PREEXECUTION_IMPLEMENTATION_PATHS = {
    SCRIPT_PATH.as_posix(),
    "tests/closure_v2/test_planning.py",
}


@dataclass(frozen=True)
class Operation:
    variable: str
    panel_column: str
    operation: str
    value: float


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    action_type: str
    relative_cost: float
    operations: tuple[Operation, ...]


class PlanningError(ClosureContractError):
    """Raised when P16 crosses its locked planning boundary."""


def _git(*args: str, root: Path = PROJECT_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _require_regular(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise PlanningError(f"Required regular file is absent: {relative}")
    return path


def _verify_record(root: Path, record: Mapping[str, Any], *, label: str) -> None:
    relative = Path(str(record.get("path", "")))
    path = _require_regular(root, relative)
    if path.stat().st_size != record.get("bytes") or sha256_file(path) != record.get("sha256"):
        raise PlanningError(f"{label} artifact binding drifted: {relative}")


def _pointer(root: Path, relative: Path) -> Mapping[str, Any]:
    payload = yaml.safe_load(_require_regular(root, relative).read_text(encoding="utf-8"))
    outs = payload.get("outs") if isinstance(payload, Mapping) else None
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise PlanningError(f"Malformed DVC pointer: {relative}")
    return cast(Mapping[str, Any], outs[0])


def _validate_v1_planning(root: Path) -> dict[str, Any]:
    physical = _require_regular(root, V1_PLANNING)
    pointer = _require_regular(root, V1_PLANNING_POINTER)
    out = _pointer(root, V1_PLANNING_POINTER)
    if (
        sha256_file(physical) != V1_PLANNING_SHA256
        or sha256_file(pointer) != V1_PLANNING_POINTER_SHA256
        or out.get("md5") != V1_PLANNING_DVC_MD5
        or out.get("size") != V1_PLANNING_BYTES
        or out.get("path") != V1_PLANNING.name
        or pq.read_metadata(physical).num_rows != 0
    ):
        raise PlanningError("V1 empty planning artifact drifted")
    return {
        "path": V1_PLANNING.as_posix(), "sha256": V1_PLANNING_SHA256,
        "dvc_pointer": V1_PLANNING_POINTER.as_posix(), "dvc_md5": V1_PLANNING_DVC_MD5,
        "bytes": V1_PLANNING_BYTES, "rows": 0, "compatible": False,
        "reuse_status": "bound_by_hash_but_not_reusable_empty_v1_p1_unavailable_artifact",
    }


def _scenario_from_mapping(raw: Mapping[str, Any]) -> Scenario:
    operations = raw.get("operations")
    if not isinstance(operations, list):
        raise PlanningError("Planning scenario operations are malformed")
    relative_cost = raw.get("relative_cost")
    if (
        not isinstance(relative_cost, (int, float))
        or isinstance(relative_cost, bool)
    ):
        raise PlanningError("Planning scenario relative_cost is malformed")
    parsed: list[Operation] = []
    for operation in operations:
        if not isinstance(operation, Mapping):
            raise PlanningError("Planning operation is malformed")
        parsed.append(Operation(
            variable=str(operation.get("variable")),
            panel_column=str(operation.get("panel_column")),
            operation=str(operation.get("operation")),
            value=float(operation.get("value")),
        ))
    return Scenario(
        scenario_id=str(raw.get("scenario_id")), action_type=str(raw.get("action_type")),
        relative_cost=float(relative_cost), operations=tuple(parsed),
    )


def load_scenarios(root: Path = PROJECT_ROOT) -> tuple[Scenario, ...]:
    matrix = load_yaml_mapping(_require_regular(root, EXPERIMENTAL_MATRIX))
    planning = matrix.get("e9_planning_inference")
    if not isinstance(planning, Mapping):
        raise PlanningError("Locked V1 planning matrix is absent")
    raw_scenarios = planning.get("scenarios")
    if not isinstance(raw_scenarios, list):
        raise PlanningError("Locked planning scenario catalog is absent")
    legacy = load_yaml_mapping(_require_regular(root, LEGACY_CATALOG))
    family = legacy.get("scenario_family")
    if not isinstance(family, Mapping) or family.get("scenarios") != raw_scenarios:
        raise PlanningError("V1 planning catalog and experimental matrix differ")
    scenarios = tuple(_scenario_from_mapping(cast(Mapping[str, Any], raw)) for raw in raw_scenarios if isinstance(raw, Mapping))
    if tuple(scenario.scenario_id for scenario in scenarios) != SCENARIO_IDS:
        raise PlanningError("P16 scenario universe drifted")
    objective = planning.get("objective_contract")
    support = planning.get("support_contract")
    family_d = planning.get("confirmatory_family_D")
    if (
        planning.get("scenario_count") != 10
        or not isinstance(objective, Mapping)
        or objective.get("primary_weights") != {"irc_alert_risk_reduction": 0.60, "bloom_probability_reduction": 0.40}
        or objective.get("base_penalties") != {"lambda_cost": 0.05, "lambda_uncertainty": 0.10, "lambda_support": 0.05}
        or not isinstance(support, Mapping)
        or support.get("fit_role") != "training"
        or support.get("fit_population") != "non_holdout_wqp_locations"
        or support.get("source_fallback_envelope") != {"lower_quantile": 0.01, "upper_quantile": 0.99}
        or support.get("heldout_locations_use_source_fallback") is not True
        or not isinstance(family_d, Mapping)
        or family_d.get("action_scenario_ids") != list(ACTION_SCENARIOS)
        or family_d.get("alternative") != "greater_than_zero"
        or family_d.get("p_value_universe_size") != 9
        or family_d.get("correction_method") != "holm"
    ):
        raise PlanningError("Locked planning objective/inference contract drifted")
    return scenarios


def validate_p15(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    head = _git("rev-parse", "HEAD", root=root)
    remote = _git("rev-parse", "origin/closure-v2", root=root)
    if head != P15_COMMIT or remote != head:
        raise PlanningError("P16 requires the exact published P15 commit")
    changed = {
        value
        for command in (("diff", "--name-only"), ("diff", "--cached", "--name-only"), ("ls-files", "--others", "--exclude-standard"))
        for value in _git(*command, root=root).splitlines()
        if value
    }
    if not changed.issubset(PREEXECUTION_IMPLEMENTATION_PATHS):
        raise PlanningError(f"Unexpected P16 pre-execution changes: {sorted(changed - PREEXECUTION_IMPLEMENTATION_PATHS)}")
    if (
        sha256_file(_require_regular(root, EXPERIMENTAL_MATRIX)) != EXPERIMENTAL_MATRIX_SHA256
        or sha256_file(_require_regular(root, LEGACY_CATALOG)) != LEGACY_CATALOG_SHA256
        or sha256_file(_require_regular(root, VARIABLES_CONFIG)) != VARIABLES_SHA256
        or sha256_file(_require_regular(root, ASSIGNMENT)) != ASSIGNMENT_SHA256
        or sha256_file(_require_regular(root, PANEL)) != PANEL_SHA256
        or (root / PANEL).stat().st_size != PANEL_BYTES
        or sha256_file(_require_regular(root, PANEL_POINTER)) != PANEL_POINTER_SHA256
    ):
        raise PlanningError("Planning catalog/support authority drifted")
    panel_out = _pointer(root, PANEL_POINTER)
    if panel_out.get("md5") != PANEL_DVC_MD5 or panel_out.get("size") != PANEL_BYTES or panel_out.get("path") != PANEL.name:
        raise PlanningError("Panel DVC binding drifted")
    manifest = load_json_mapping(_require_regular(root, P15_MANIFEST))
    if sha256_file(root / P15_MANIFEST) != P15_MANIFEST_SHA256 or any(manifest.get(key) != value for key, value in {
        "phase": "P15", "status": "completed", "same_masks_per_m0_p1_pair": True,
        "refit_performed": False, "recalibration_performed": False,
        "outcomes_reopened": False, "manifest_written_last": True,
    }.items()):
        raise PlanningError("P15 degradation authority drifted")
    for record in cast(Sequence[Mapping[str, Any]], manifest.get("outputs", [])):
        _verify_record(root, record, label="P15")
    model_lock = evaluation._validate_model_lock(root)
    scenarios = load_scenarios(root)
    plan = load_yaml_mapping(_require_regular(root, ANALYSIS_PLAN))
    families = cast(Mapping[str, Any], cast(Mapping[str, Any], plan.get("multiplicity", {})).get("families", {}))
    if families.get("E") != list(ACTION_SCENARIOS):
        raise PlanningError("Closure V2 Holm family E drifted")
    return {
        "status": "p15_effective", "head": head, "model_lock": model_lock,
        "p15_manifest_sha256": P15_MANIFEST_SHA256,
        "scenario_ids": [scenario.scenario_id for scenario in scenarios],
        "v1_planning": _validate_v1_planning(root),
    }


def _plausible_ranges(root: Path) -> dict[str, tuple[float | None, float | None]]:
    payload = load_yaml_mapping(_require_regular(root, VARIABLES_CONFIG))
    variables = payload.get("canonical_variables")
    if not isinstance(variables, Mapping):
        raise PlanningError("Canonical variable registry is absent")
    result: dict[str, tuple[float | None, float | None]] = {}
    for variable, raw in variables.items():
        if not isinstance(raw, Mapping) or not isinstance(raw.get("plausible_range"), Mapping):
            continue
        plausible = cast(Mapping[str, Any], raw["plausible_range"])
        lower = plausible.get("min")
        upper = plausible.get("max")
        result[str(variable)] = (
            float(lower) if lower is not None else None,
            float(upper) if upper is not None else None,
        )
    return result


def load_support(root: Path = PROJECT_ROOT) -> dict[str, tuple[float, float]]:
    assignment = pd.read_csv(_require_regular(root, ASSIGNMENT))
    development = set(assignment.loc[assignment["assignment_role"].eq("development"), "site_id"].astype(str))
    if len(development) != 353 or int(assignment["assignment_role"].eq("internal_holdout").sum()) != 88:
        raise PlanningError("V1 development/holdout assignment drifted")
    panel = pq.read_table(
        _require_regular(root, PANEL), columns=["source_id", "site_id", "year_month", *ACTION_COLUMNS],
        filters=[("source_id", "=", "wqp"), ("year_month", "<=", "2018-12")],
    ).to_pandas()
    panel = panel.loc[panel["site_id"].astype(str).isin(development)].copy()
    if panel.empty or set(panel["source_id"].astype(str)) != {"wqp"} or panel["year_month"].astype(str).max() > "2018-12":
        raise PlanningError("Training-only support surface drifted")
    bounds: dict[str, tuple[float, float]] = {}
    for column in ACTION_COLUMNS:
        values = pd.to_numeric(panel[column], errors="coerce")
        values = values[np.isfinite(values)]
        if len(values) < 24:
            raise PlanningError(f"Training support is insufficient: {column}")
        bounds[column] = (float(values.quantile(0.01, interpolation="linear")), float(values.quantile(0.99, interpolation="linear")))
    return bounds


def _refresh_nutrients(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    tp = pd.to_numeric(out["mean_TP_ugL"], errors="coerce")
    tn = pd.to_numeric(out["mean_TN_ugL"], errors="coerce")
    out["log_TP"] = np.log(tp + 0.1)
    out["log_TN"] = np.log(tn + 0.1)
    out["TN_TP_ratio"] = tn / tp.replace(0.0, np.nan)
    return out


def apply_scenario(
    origins: pd.DataFrame,
    scenario: Scenario,
    support: Mapping[str, tuple[float, float]],
    plausible: Mapping[str, tuple[float | None, float | None]],
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    out = origins.copy(deep=True)
    available = np.ones(len(out), dtype=bool)
    violation = np.zeros(len(out), dtype=bool)
    clipped = np.zeros(len(out), dtype=bool)
    for operation in scenario.operations:
        if operation.panel_column not in out or operation.panel_column not in support:
            raise PlanningError(f"Unregistered planning lever: {operation.panel_column}")
        before = pd.to_numeric(out[operation.panel_column], errors="coerce").to_numpy(dtype=np.float64)
        finite = np.isfinite(before)
        available &= finite
        after = before * operation.value if operation.operation == "multiply" else before + operation.value if operation.operation == "add" else None
        if after is None:
            raise PlanningError(f"Unsupported planning operation: {operation.operation}")
        lower, upper = plausible.get(operation.variable, (None, None))
        if lower is not None:
            clipped |= finite & (after < lower)
            after = np.maximum(after, lower)
        if upper is not None:
            clipped |= finite & (after > upper)
            after = np.minimum(after, upper)
        support_lower, support_upper = support[operation.panel_column]
        violation |= finite & ((after < support_lower) | (after > support_upper))
        out[operation.panel_column] = after
    out = _refresh_nutrients(out)
    if scenario.scenario_id == BASELINE_SCENARIO and (not available.all() or violation.any() or clipped.any()):
        raise PlanningError("no_action acquired an action restriction")
    return out, available, violation, clipped


def _replace_last_state(
    selected: pd.DataFrame,
    modified_origins: pd.DataFrame,
    arrays: Mapping[str, np.ndarray],
    seed: int,
) -> pd.DataFrame:
    features = phase3._anfis_feature_frame(modified_origins)
    values: dict[str, np.ndarray] = {}
    for module, channel in (("N", "N"), ("F", "F"), ("T", "T")):
        state, sigma = phase3._anfis_forward(arrays, seed=seed, module=module, features=features)
        values[f"x_y{channel}"] = state
        values[f"x_sigma_{channel}"] = sigma
    out = selected.copy(deep=True)
    for column in INPUT_COLUMNS:
        out[column] = [np.asarray(value, dtype=np.float64).copy() for value in selected[column]]
    for channel in ("N", "F", "T"):
        state_column = f"x_y{channel}"
        sigma_column = f"x_sigma_{channel}"
        delta_column = f"x_delta_y{channel}"
        for index in range(len(out)):
            state_values = cast(np.ndarray, out.at[index, state_column])
            sigma_values = cast(np.ndarray, out.at[index, sigma_column])
            delta_values = cast(np.ndarray, out.at[index, delta_column])
            state_values[-1] = values[state_column][index]
            sigma_values[-1] = values[sigma_column][index]
            delta_values[-1] = state_values[-1] - state_values[-2]
    return out


def _rollout(
    selected: pd.DataFrame,
    valid: np.ndarray,
    model: Any,
    blend: Any,
) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    result = {
        horizon: (
            np.full((len(selected), 9), np.nan, dtype=np.float64),
            np.full((len(selected), 9), np.nan, dtype=np.float64),
        )
        for horizon in HORIZONS
    }
    indices = np.flatnonzero(valid)
    if not len(indices):
        return result
    predicted = recursive_predictions(selected.iloc[indices].reset_index(drop=True), model, blend)
    for horizon in HORIZONS:
        state, sigma = result[horizon]
        state[indices] = predicted[horizon][0]
        sigma[indices] = predicted[horizon][1]
    return result


def _irc(state: np.ndarray) -> np.ndarray:
    return np.clip((state[:, 0] + (1.0 - state[:, 1]) + state[:, 2]) / 3.0, 0.0, 1.0)


def _bloom_proxy(state: np.ndarray, irc: np.ndarray) -> np.ndarray:
    return np.clip(0.5 * state[:, 2] + 0.5 * irc, 0.0, 1.0)


def _target_month(values: pd.Series, horizon: int) -> list[str]:
    return [str(cast(pd.Period, pd.Period(str(value), freq="M")) + horizon) for value in values]


def _seed_scenario_rows(
    metadata: pd.DataFrame,
    baseline: Mapping[int, tuple[np.ndarray, np.ndarray]],
    action: Mapping[int, tuple[np.ndarray, np.ndarray]],
    base_valid: np.ndarray,
    action_valid: np.ndarray,
    action_available: np.ndarray,
    support_violation: np.ndarray,
    plausible_clip: np.ndarray,
    *,
    cohort: str,
    seed: int,
    scenario: Scenario,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for horizon in HORIZONS:
        base_state, base_sigma = baseline[horizon]
        action_state, action_sigma = action[horizon]
        successful = base_valid & action_valid
        base_irc = _irc(base_state)
        action_irc = _irc(action_state)
        base_bloom = _bloom_proxy(base_state, base_irc)
        action_bloom = _bloom_proxy(action_state, action_irc)
        base_u = np.nanmean(base_sigma[:, :3], axis=1)
        action_u = np.nanmean(action_sigma[:, :3], axis=1)
        delta_irc = base_irc - action_irc
        delta_bloom = base_bloom - action_bloom
        delta_u = action_u - base_u
        base_objective = 0.60 * delta_irc + 0.40 * delta_bloom
        objective = (
            base_objective - PRIMARY_COST_WEIGHT * scenario.relative_cost
            - PRIMARY_UNCERTAINTY_WEIGHT * np.maximum(0.0, delta_u)
            - PRIMARY_SUPPORT_WEIGHT * support_violation.astype(np.float64)
        )
        frame = metadata[["origin_id", "source_id", "site_id", "origin_year_month", "base_input_status", "base_input_reason"]].copy()
        frame.insert(0, "evaluation_cohort", cohort)
        frame["target_year_month"] = _target_month(frame["origin_year_month"], horizon)
        frame["horizon_months"] = horizon
        frame["scenario_id"] = scenario.scenario_id
        frame["action_type"] = scenario.action_type
        frame["model_id"] = "P1"
        frame["seed"] = seed
        frame["intent_to_plan"] = True
        frame["input_eligible"] = base_valid
        frame["action_input_available"] = action_available
        frame["status"] = np.where(
            ~base_valid, "input_ineligible",
            np.where(~action_available, "action_input_unavailable", np.where(~action_valid, "model_unavailable", "success")),
        )
        frame["failure_code"] = np.where(
            frame["status"].eq("input_ineligible"), frame["base_input_reason"],
            np.where(frame["status"].eq("action_input_unavailable"), "required_action_proxy_missing",
                     np.where(frame["status"].eq("model_unavailable"), "frozen_p1_rollout_unavailable", "")),
        )
        frame["registered_relative_cost"] = scenario.relative_cost
        for column, values in (
            ("delta_irc", delta_irc), ("delta_bloom", delta_bloom), ("delta_u", delta_u),
            ("base_objective", base_objective), ("delta_objective", objective),
            ("relative_cost", np.full(len(frame), scenario.relative_cost)),
            ("support_violation", support_violation.astype(np.float64)),
            ("plausible_clip", plausible_clip.astype(np.float64)),
        ):
            frame[column] = np.where(successful, values, np.nan)
        scientific = ["delta_irc", "delta_bloom", "delta_u", "base_objective", "delta_objective", "relative_cost", "support_violation", "plausible_clip"]
        if frame.loc[~frame["status"].eq("success"), scientific].notna().any().any():
            raise PlanningError("Failed planning rows retained scientific values")
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def _family_rows(seed_rows: pd.DataFrame, *, cohort: str, intended_origins: int) -> pd.DataFrame:
    keys = [
        "evaluation_cohort", "origin_id", "source_id", "site_id", "origin_year_month",
        "target_year_month", "horizon_months", "scenario_id", "action_type",
    ]
    scientific = [
        "delta_irc", "delta_bloom", "delta_u", "base_objective", "delta_objective",
        "relative_cost", "support_violation", "plausible_clip",
    ]
    grouped = seed_rows.groupby(keys, sort=True, dropna=False)
    family = grouped.agg(
        registered_relative_cost=("registered_relative_cost", "first"),
        intended_seed_slots=("seed", "nunique"),
        successful_seed_slots=("status", lambda values: sum(value == "success" for value in values)),
        input_eligible=("input_eligible", "all"),
        action_input_available=("action_input_available", "all"),
        **{column: (column, "mean") for column in scientific},
    ).reset_index()
    complete = family["successful_seed_slots"].eq(len(EXPECTED_SEEDS))
    family["status"] = np.where(complete, "shared_success", "not_estimable_incomplete_seed_family")
    family["failure_code"] = np.where(
        complete, "",
        np.where(~family["input_eligible"], "base_input_ineligible",
                 np.where(~family["action_input_available"], "required_action_proxy_missing", "missing_action_or_no_action_registered_seed")),
    )
    family.loc[~complete, scientific] = np.nan
    family["seed_count"] = np.where(complete, len(EXPECTED_SEEDS), family["successful_seed_slots"])
    family["cluster_id"] = family["source_id"].astype(str) + "::" + family["site_id"].astype(str)
    family["intent_to_plan"] = True
    family["availability"] = family["successful_seed_slots"] / len(EXPECTED_SEEDS)
    expected = intended_origins * len(HORIZONS) * len(ACTION_SCENARIOS)
    if (
        len(family) != expected
        or not family["intended_seed_slots"].eq(len(EXPECTED_SEEDS)).all()
        or family.duplicated(["evaluation_cohort", "origin_id", "horizon_months", "scenario_id"]).any()
        or family.loc[~complete, scientific].notna().any().any()
    ):
        raise PlanningError(f"P16 family intent universe drifted: {cohort}")
    order = [
        "evaluation_cohort", "origin_id", "source_id", "site_id", "cluster_id",
        "origin_year_month", "target_year_month", "horizon_months", "scenario_id", "action_type",
        "intent_to_plan", "input_eligible", "action_input_available", "status", "failure_code",
        "intended_seed_slots", "successful_seed_slots", "seed_count", "availability",
        "registered_relative_cost", *scientific,
    ]
    return family[order].sort_values(
        ["evaluation_cohort", "scenario_id", "source_id", "site_id", "origin_year_month", "horizon_months"], kind="stable"
    ).reset_index(drop=True)


def _inference_tables(origin_deltas: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summaries: list[pd.DataFrame] = []
    sensitivities: list[pd.DataFrame] = []
    coherences: list[pd.DataFrame] = []
    for cohort in COHORTS:
        full = origin_deltas.loc[origin_deltas["evaluation_cohort"].eq(cohort)].copy()
        shared = full.loc[full["status"].eq("shared_success")].copy()
        _, summary = _bootstrap(shared)
        intended = full.groupby("scenario_id", sort=True).size()
        available = shared.groupby("scenario_id", sort=True).size()
        summary.insert(0, "evaluation_cohort", cohort)
        summary.insert(1, "estimand", "observation_weighted_pooled_h1_h3")
        summary["intended_row_count"] = summary["scenario_id"].map(intended).fillna(0).astype(int)
        summary["shared_success_row_count"] = summary["scenario_id"].map(available).fillna(0).astype(int)
        summary["availability"] = summary["shared_success_row_count"] / summary["intended_row_count"]
        summary["result_state"] = "posthoc_available" if cohort == "legacy_posthoc" else "confirmatory_available"
        summary["alternative"] = "greater_than_zero"
        summary["holm_universe_size"] = len(ACTION_SCENARIOS)
        summaries.append(summary)
        sensitivity = _sensitivity(shared)
        sensitivity.insert(0, "evaluation_cohort", cohort)
        sensitivity.insert(1, "estimand", "observation_weighted_pooled_h1_h3")
        sensitivities.append(sensitivity)
        coherence = _coherence(shared, summary)
        coherence.insert(0, "evaluation_cohort", cohort)
        coherence.insert(1, "estimand", "observation_weighted_pooled_h1_h3")
        coherence["result_state"] = "posthoc_available" if cohort == "legacy_posthoc" else "confirmatory_available"
        coherences.append(coherence)
    bootstrap = pd.concat(summaries, ignore_index=True).sort_values(["evaluation_cohort", "scenario_id"], kind="stable").reset_index(drop=True)
    sensitivity = pd.concat(sensitivities, ignore_index=True).sort_values(
        ["evaluation_cohort", "scenario_id", "cost_weight_multiplier", "support_penalty_multiplier"], kind="stable"
    ).reset_index(drop=True)
    coherence = pd.concat(coherences, ignore_index=True).sort_values(["evaluation_cohort", "scenario_id"], kind="stable").reset_index(drop=True)
    if (
        len(bootstrap) != len(COHORTS) * len(ACTION_SCENARIOS)
        or len(sensitivity) != len(COHORTS) * len(ACTION_SCENARIOS) * len(SENSITIVITY_MULTIPLIERS) ** 2
        or len(coherence) != len(COHORTS) * len(ACTION_SCENARIOS)
        or bootstrap.groupby("evaluation_cohort")["scenario_id"].nunique().ne(9).any()
    ):
        raise PlanningError("P16 inferential output universe drifted")
    return bootstrap, sensitivity, coherence


def _load_runtime(root: Path) -> tuple[
    dict[str, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]],
    dict[str, pd.DataFrame], dict[str, np.ndarray], dict[str, tuple[float, float]],
    dict[str, tuple[float | None, float | None]], tuple[Scenario, ...],
]:
    cohorts = evaluation._load_cohorts(root)
    arrays, warmup, _, _ = phase3._load_overlay(root)
    monthly: dict[str, pd.DataFrame] = {}
    for cohort, (intents, history, _) in cohorts.items():
        sites = set(intents["site_id"].astype(str))
        cohort_warmup = warmup.loc[warmup["site_id"].astype(str).isin(sites)].copy()
        monthly[cohort] = phase3._deduplicated_month_surface(history, cohort_warmup)
    support = load_support(root)
    development = set(pd.read_csv(root / ASSIGNMENT).loc[lambda frame: frame["assignment_role"].eq("development"), "site_id"].astype(str))
    if any(set(bundle[0]["site_id"].astype(str)) & development for bundle in cohorts.values()):
        raise PlanningError("Evaluation locations crossed the support-fit population")
    return cohorts, monthly, arrays, support, _plausible_ranges(root), load_scenarios(root)


def build_tables(root: Path = PROJECT_ROOT) -> dict[str, pd.DataFrame]:
    cohorts, monthly_by_cohort, arrays, support, plausible, scenarios = _load_runtime(root)
    action_scenarios = [scenario for scenario in scenarios if scenario.scenario_id != BASELINE_SCENARIO]
    family_tables: list[pd.DataFrame] = []
    for cohort in COHORTS:
        intents, history, origins = cohorts[cohort]
        ordered_origins = origins.sort_values(["source_id", "site_id", "origin_year_month", "origin_id"], kind="stable").reset_index(drop=True)
        seed_tables: list[pd.DataFrame] = []
        for seed in EXPECTED_SEEDS:
            state = degradation._adaptive_state(arrays, monthly_by_cohort[cohort], seed)
            selected, base_valid = evaluation._sequence_frame(intents, history, state)
            if not selected["origin_id"].astype(str).equals(ordered_origins["origin_id"].astype(str)):
                raise PlanningError("Planning origin/sequence order drifted")
            model, blend, _ = _load_model("P1", seed, root=root)
            baseline = _rollout(selected, base_valid, model, blend)
            for scenario in action_scenarios:
                modified, action_available, violation, clipped = apply_scenario(ordered_origins, scenario, support, plausible)
                action_selected = _replace_last_state(selected, modified, arrays, seed)
                action_valid = base_valid & action_available
                action = _rollout(action_selected, action_valid, model, blend)
                seed_tables.append(_seed_scenario_rows(
                    selected, baseline, action, base_valid, action_valid, action_available,
                    violation, clipped, cohort=cohort, seed=seed, scenario=scenario,
                ))
        all_seed_rows = pd.concat(seed_tables, ignore_index=True)
        family_tables.append(_family_rows(all_seed_rows, cohort=cohort, intended_origins=len(intents)))
    origin_deltas = pd.concat(family_tables, ignore_index=True).sort_values(
        ["evaluation_cohort", "scenario_id", "source_id", "site_id", "origin_year_month", "horizon_months"], kind="stable"
    ).reset_index(drop=True)
    bootstrap, sensitivity, coherence = _inference_tables(origin_deltas)
    return {
        "origin_deltas": origin_deltas, "bootstrap": bootstrap,
        "sensitivity": sensitivity, "coherence": coherence,
    }


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
                raise PlanningError(f"Refusing to overwrite P16 output: {relative}")
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


def preflight(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_p15(root)
    cohorts, monthly, _, support, _, scenarios = _load_runtime(root)
    return {
        **authority, "status": "ready_for_frozen_p1_planning",
        "cohorts": {
            cohort: {"intent_origins": len(cohorts[cohort][0]), "locations": int(cohorts[cohort][0]["site_id"].nunique()), "physical_months": len(monthly[cohort])}
            for cohort in COHORTS
        },
        "scenario_count": len(scenarios), "action_count": len(ACTION_SCENARIOS),
        "registered_seeds": list(EXPECTED_SEEDS), "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "support_fit_role": "training_through_2018_12_non_holdout_wqp",
        "support_source_fallback_bounds": support,
        "outcomes_opened": False, "refit_performed": False, "recalibration_performed": False,
        "outputs_absent": all(not (root / path).exists() and not (root / path).is_symlink() for path in ALL_OUTPUTS),
        "writes_performed": False,
    }


def execute(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_p15(root)
    if any((root / path).exists() or (root / path).is_symlink() for path in ALL_OUTPUTS):
        raise PlanningError("P16 output namespace is not empty")
    guard = root / "tmp/closure_v2_planning.guard"
    guard.parent.mkdir(parents=True, exist_ok=True)
    try:
        guard.mkdir()
    except FileExistsError as error:
        raise PlanningError("P16 planning guard already exists") from error
    try:
        tables = build_tables(root)
        payloads = {
            ORIGIN_DELTAS: _parquet_bytes(tables["origin_deltas"]),
            BOOTSTRAP: _csv_bytes(tables["bootstrap"]),
            SENSITIVITY: _csv_bytes(tables["sensitivity"]),
            COHERENCE: _csv_bytes(tables["coherence"]),
        }
        repeated = {
            ORIGIN_DELTAS: _parquet_bytes(tables["origin_deltas"].copy(deep=True)),
            BOOTSTRAP: _csv_bytes(tables["bootstrap"].copy(deep=True)),
            SENSITIVITY: _csv_bytes(tables["sensitivity"].copy(deep=True)),
            COHERENCE: _csv_bytes(tables["coherence"].copy(deep=True)),
        }
        if {path: hashlib.sha256(value).hexdigest() for path, value in payloads.items()} != {
            path: hashlib.sha256(value).hexdigest() for path, value in repeated.items()
        }:
            raise PlanningError("P16 deterministic serialization check failed")
        _exclusive_bundle([(path, payloads[path]) for path in MATERIALIZED_OUTPUTS], root=root)
        return {
            "status": "frozen_p1_planning_materialized_unfinalized", "authority": authority,
            "origin_delta_rows": len(tables["origin_deltas"]),
            "shared_success_rows": int(tables["origin_deltas"]["status"].eq("shared_success").sum()),
            "bootstrap_rows": len(tables["bootstrap"]), "sensitivity_rows": len(tables["sensitivity"]),
            "coherence_rows": len(tables["coherence"]), "refit_performed": False,
            "recalibration_performed": False, "outcomes_opened": False,
            "next_required": ".venv/bin/dvc add reports/closure_v2/07_planning/planning_origin_deltas.parquet then --finalize",
        }
    finally:
        guard.rmdir()


def _report_bytes(root: Path) -> bytes:
    bootstrap = pd.read_csv(_require_regular(root, BOOTSTRAP))
    coherence = pd.read_csv(_require_regular(root, COHERENCE))
    fresh = bootstrap.loc[bootstrap["evaluation_cohort"].eq("fresh_primary")]
    legacy = bootstrap.loc[bootstrap["evaluation_cohort"].eq("legacy_posthoc")]
    lines = [
        "# Closure V2 frozen-P1 planning report", "",
        "P16 applied the ten locked V1 raw-proxy scenarios independently at each evaluation origin and propagated the resulting current-state perturbation through the frozen P1 residual probabilistic GRU rollout. No model, calibrator, threshold, action, cost, support envelope, or objective weight was fitted or selected after evaluation.", "",
        "## Fresh-primary family E", "", fresh.to_markdown(index=False), "",
        "## Legacy-posthoc family E", "", legacy.to_markdown(index=False), "",
        "## Ecological coherence", "", coherence.to_markdown(index=False), "",
        "## Interpretation boundaries", "",
        "The alternative `delta_objective_vs_no_action > 0`, clustered bootstrap formula, and Holm family of nine actions were inherited from the locked V1 experimental matrix. Every action remains in the multiplicity universe whether favorable, unfavorable, unavailable, or outside support. `fresh_primary` is internal model-behavior evidence on unused WQP monitoring locations; `legacy_posthoc` is retrospective/complementary. These raw-proxy simulations are not causal field effects, official recommendations, guaranteed interventions, or universal optima.", "",
        f"- P15 authority commit: `{P15_COMMIT}`",
        f"- locked experimental matrix SHA-256: `{EXPERIMENTAL_MATRIX_SHA256}`",
        f"- planning script SHA-256: `{sha256_file(root / SCRIPT_PATH)}`", "",
    ]
    return "\n".join(lines).encode("utf-8")


def _record(relative: Path, *, root: Path, role: str) -> dict[str, Any]:
    path = _require_regular(root, relative)
    return {"path": relative.as_posix(), "role": role, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def finalize(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    if (root / REPORT).exists() or (root / REPORT).is_symlink() or (root / MANIFEST).exists() or (root / MANIFEST).is_symlink():
        raise PlanningError("P16 final report or manifest already exists")
    for path in (*MATERIALIZED_OUTPUTS, ORIGIN_POINTER):
        _require_regular(root, path)
    out = _pointer(root, ORIGIN_POINTER)
    physical = root / ORIGIN_DELTAS
    if out.get("path") != ORIGIN_DELTAS.name or out.get("size") != physical.stat().st_size or out.get("md5") != md5_file(physical):
        raise PlanningError("P16 origin-delta DVC pointer does not bind its physical table")
    origins = pq.read_table(physical).to_pandas()
    bootstrap = pd.read_csv(root / BOOTSTRAP)
    sensitivity = pd.read_csv(root / SENSITIVITY)
    coherence = pd.read_csv(root / COHERENCE)
    expected_origins = (4488 + 2286) * len(HORIZONS) * len(ACTION_SCENARIOS)
    if (
        len(origins) != expected_origins
        or len(bootstrap) != 18 or len(sensitivity) != 162 or len(coherence) != 18
        or origins.groupby(["evaluation_cohort", "origin_id", "horizon_months"])["scenario_id"].nunique().ne(9).any()
        or bootstrap.groupby("evaluation_cohort")["scenario_id"].nunique().ne(9).any()
    ):
        raise PlanningError("P16 final table universe drifted")
    report = _report_bytes(root)
    manifest = {
        "schema_version": "closure_v2_planning_manifest_v1",
        "experiment_id": "closure_v2", "phase": "P16", "status": "completed",
        "authority_commit": P15_COMMIT,
        "script": _record(SCRIPT_PATH, root=root, role="frozen_p1_planning_runner"),
        "inputs": [
            _record(path, root=root, role=role)
            for path, role in (
                (ANALYSIS_PLAN, "locked_v2_analysis_plan"), (EXECUTION_GUIDE, "public_execution_guide"),
                (MODEL_LOCK, "locked_model_registry"), (P15_MANIFEST, "p15_degradation_manifest"),
                (EXPERIMENTAL_MATRIX, "locked_v1_planning_matrix"), (LEGACY_CATALOG, "locked_action_catalog"),
                (VARIABLES_CONFIG, "plausible_ranges"), (ASSIGNMENT, "development_holdout_assignment"),
                (PANEL_POINTER, "training_support_panel_pointer"), (V1_PLANNING_POINTER, "v1_empty_planning_pointer"),
            )
        ],
        "v1_planning_binding": _validate_v1_planning(root),
        "data_artifact": {
            "path": ORIGIN_DELTAS.as_posix(), "role": "planning_origin_deltas_complete_intent_universe",
            "bytes": physical.stat().st_size, "sha256": sha256_file(physical), "rows": len(origins),
            "dvc_pointer": ORIGIN_POINTER.as_posix(), "dvc_md5": out["md5"], "dvc_size": out["size"],
        },
        "outputs": [
            _record(path, root=root, role="planning_output")
            for path in (BOOTSTRAP, SENSITIVITY, COHERENCE, ORIGIN_POINTER)
        ] + [{"path": REPORT.as_posix(), "role": "planning_output", "bytes": len(report), "sha256": hashlib.sha256(report).hexdigest()}],
        "scenario_ids": list(SCENARIO_IDS), "action_scenario_ids": list(ACTION_SCENARIOS),
        "registered_seeds": list(EXPECTED_SEEDS), "evaluation_cohorts": list(COHORTS),
        "origin_delta_rows": len(origins), "shared_success_rows": int(origins["status"].eq("shared_success").sum()),
        "bootstrap_summary_rows": len(bootstrap), "bootstrap_replicates_per_action": BOOTSTRAP_REPLICATES,
        "sensitivity_rows": len(sensitivity), "ecological_coherence_rows": len(coherence),
        "objective": "0.60*delta_irc+0.40*delta_bloom-0.05*cost-0.10*max(0,delta_u)-0.05*support_violation",
        "primary_endpoint": "delta_objective_vs_no_action",
        "primary_estimand": "observation_weighted_mean_over_exact_common_origins_and_horizons_1_2_3",
        "cluster_unit": "source_id_plus_site_id", "alternative": "greater_than_zero",
        "holm_universe": "E", "holm_universe_size": 9, "holm_universe_reduced": False,
        "support_fit_role": "training_through_2018_12_non_holdout_wqp",
        "heldout_support_policy": "wqp_source_fallback_quantiles_0.01_0.99",
        "action_application": "origin_current_raw_proxy_then_frozen_p1_rollout",
        "seed_aggregation": "paired_action_minus_no_action_then_equal_mean_over_all_five_registered_seeds",
        "intent_origins_preserved": True, "failed_values_nulled": True,
        "seeds_used_as_ecological_replicates": False, "cohorts_pooled": False,
        "refit_performed": False, "recalibration_performed": False,
        "outcomes_opened": False, "field_causality_claimed": False,
        "official_recommendation_claimed": False, "universal_optimality_claimed": False,
        "manifest_written_last": True,
    }
    _exclusive_bundle([(REPORT, report), (MANIFEST, canonical_json_bytes(manifest))], root=root)
    return {
        "status": "frozen_p1_planning_completed", "origin_delta_rows": len(origins),
        "origin_dvc_md5": out["md5"], "origin_dvc_size": out["size"],
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
