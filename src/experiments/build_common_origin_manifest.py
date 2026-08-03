#!/usr/bin/env python
"""Build the outcome-independent Closure V1 common-origin universe.

Intent-to-predict origins are frozen from input history before target-key
availability is joined.  The command can materialize only the 353 published
development locations and calendar rows through December 2021.  It projects no
target value, legacy split label, or chlorophyll-a field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments.build_closure_holdout import (
    PRECURSOR_READ_COLUMNS,
    build_precursor_month_status,
)
from src.experiments.closure_contract import load_json_mapping, load_yaml_mapping, repository_relative
from src.experiments.closure_development_guard import (
    ASSIGNMENT_DEVELOPMENT,
    DEVELOPMENT_ROLES,
    DevelopmentGate,
    DevelopmentGuardError,
    DevelopmentScanAudit,
    assert_development_frame,
    assign_pair_roles,
    load_development_gate,
    scan_development_rows,
)
from src.pandas_utils import dataframe_rows


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PANEL = Path("data/panel/panel_monthly_v0.parquet")
DEFAULT_SPLITS = Path("data/splits/monthly_model_splits_v0.parquet")
DEFAULT_TARGETS = Path("data/targets/monthly_targets_model_v0.parquet")
DEFAULT_TARGET_MANIFEST = Path("data/targets/target_manifest_v0.json")
DEFAULT_SPLIT_MANIFEST = Path("data/splits/split_manifest.json")
DEFAULT_ANALYSIS_PLAN = Path("configs/closure_v1/analysis_plan.yaml")
DEFAULT_PRIMARY_SURFACE = Path("configs/closure_v1/surface_primary.yaml")
DEFAULT_MODEL_BENCHMARK = Path("configs/closure_v1/model_benchmark.yaml")
DEFAULT_LOCATION_HOLDOUT = Path("configs/closure_v1/location_holdout.yaml")
DEFAULT_OUTPUT = Path("data/closure_v1/common_origin_manifest.parquet")
DEFAULT_MANIFEST = Path("reports/closure_v1/01_surface/common_origin_manifest.json")

COMMON_ORIGIN_CODE_DEPENDENCIES = (
    Path("src/experiments/build_common_origin_manifest.py"),
    Path("src/experiments/build_closure_holdout.py"),
    Path("src/experiments/closure_contract.py"),
    Path("src/experiments/closure_development_guard.py"),
    Path("src/pandas_utils.py"),
)
COMMON_ORIGIN_CONFIG_DEPENDENCIES = (
    DEFAULT_ANALYSIS_PLAN,
    Path("configs/closure_v1/analysis_plan.schema.json"),
    DEFAULT_PRIMARY_SURFACE,
    Path("configs/closure_v1/surface_secondary.yaml"),
    DEFAULT_LOCATION_HOLDOUT,
    DEFAULT_MODEL_BENCHMARK,
    Path("configs/closure_v1/experimental_matrix.yaml"),
    Path("configs/counterfactual_planning_v1.yaml"),
)

SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
HISTORY_LENGTH_MONTHS = 12
HORIZONS_MONTHS = (1, 2, 3)
TARGET_KEY_COLUMNS = [
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
]
ORIGIN_KEY_COLUMNS = ["source_id", "site_id", "origin_year_month"]
FULL_KEY_COLUMNS = TARGET_KEY_COLUMNS
MODEL_IDS = ("B0", "B1", "B2", "F0", "F1", "P0", "P1", "M0")
EVIDENCE_DOMAINS = (
    "nutrient",
    "temperature",
    "light",
    "physicochemical",
    "context",
)


@dataclass(frozen=True)
class IntentOriginAudit:
    """Input-only origin construction counts."""

    monthly_status_rows: int
    input_eligible_month_rows: int
    history_candidate_origins: int
    retained_intent_origins: int
    excluded_role_crossing_origins: int
    excluded_locked_evaluation_origins: int


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": repository_relative(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verified_file_record(
    path: Path,
    *,
    expected_sha256: str,
    role: str,
) -> dict[str, Any]:
    record = _file_record(path)
    if record["sha256"] != expected_sha256:
        raise DevelopmentGuardError(f"{role} changed during common-origin construction")
    return {**record, "role": role}


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _git_execution_state() -> dict[str, Any]:
    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=no"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    status_lines = [line for line in status.stdout.splitlines() if line]
    return {
        "base_head": _git_head(),
        "base_head_is_complete_source_identity": False,
        "tracked_worktree_status": "dirty" if status_lines else "clean",
        "tracked_status_lines": status_lines,
    }


def _reproduction_command(args: argparse.Namespace) -> list[str]:
    return [
        "poetry",
        "run",
        "python",
        COMMON_ORIGIN_CODE_DEPENDENCIES[0].as_posix(),
        "--panel",
        repository_relative(args.panel),
        "--splits",
        repository_relative(args.splits),
        "--output",
        repository_relative(args.output),
        "--manifest",
        repository_relative(args.manifest),
    ]


def _write_json_atomic(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _stable_id(namespace: str, values: Sequence[str | int]) -> str:
    payload = json.dumps(
        [namespace, *values],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _period(value: str, *, field_name: str) -> pd.Period:
    try:
        period = cast(pd.Period, pd.Period(value, freq="M"))
    except ValueError as exc:
        raise DevelopmentGuardError(f"{field_name} contains an invalid calendar month: {value!r}") from exc
    if str(period) != value:
        raise DevelopmentGuardError(f"{field_name} must use canonical YYYY-MM values: {value!r}")
    return period


def _window_evidence(indexed: pd.DataFrame, history: Sequence[pd.Period]) -> dict[str, int | float]:
    rows = indexed.loc[[str(month) for month in history]]
    evidence: dict[str, int | float] = {}
    for domain in EVIDENCE_DOMAINS:
        count = int(rows[f"{domain}_available"].astype(bool).sum())
        evidence[f"{domain}_evidence_months"] = count
        evidence[f"{domain}_evidence_fraction"] = count / float(HISTORY_LENGTH_MONTHS)
    return evidence


def _origin_records_for_location(
    group: pd.DataFrame,
    gate: DevelopmentGate,
) -> tuple[list[dict[str, Any]], int, int, int]:
    source_id = str(group["source_id"].iloc[0])
    site_id = str(group["site_id"].iloc[0])
    eligible_months = {
        _period(str(row.year_month), field_name="year_month")
        for row in dataframe_rows(group)
        if bool(row.input_eligible)
    }
    indexed = group.set_index("year_month")
    if bool(indexed.index.duplicated(keep=False).any()):
        raise DevelopmentGuardError("Precursor status contains duplicate site/month rows")
    calibration_end = _period(
        gate.bounds.calibration_threshold_end,
        field_name="calibration_threshold_end",
    )

    records: list[dict[str, Any]] = []
    history_candidates = 0
    crossing_exclusions = 0
    locked_exclusions = 0
    for origin in sorted(eligible_months):
        history = [origin - offset for offset in range(HISTORY_LENGTH_MONTHS - 1, -1, -1)]
        if any(month not in eligible_months for month in history):
            continue
        history_candidates += 1
        targets = [origin + horizon for horizon in HORIZONS_MONTHS]
        if targets[-1] > calibration_end:
            locked_exclusions += 1
            continue

        geometry = pd.DataFrame(
            {
                "origin_year_month": [str(origin)] * len(HORIZONS_MONTHS),
                "target_year_month": [str(target) for target in targets],
            }
        )
        roles = assign_pair_roles(geometry, gate=gate)
        non_null_roles = set(roles.dropna().astype(str))
        if bool(roles.isna().any()) or len(non_null_roles) != 1:
            crossing_exclusions += 1
            continue
        time_role = next(iter(non_null_roles))
        common_origin_id = _stable_id(
            "closure_v1_common_origin_v1",
            [source_id, site_id, str(origin)],
        )
        evidence = _window_evidence(indexed, history)
        base: dict[str, Any] = {
            "surface_id": SURFACE_ID,
            "source_id": source_id,
            "site_id": site_id,
            "common_origin_id": common_origin_id,
            "holdout_group_id": f"{source_id}::{site_id}",
            "assignment_role": ASSIGNMENT_DEVELOPMENT,
            "time_role": time_role,
            "origin_year_month": str(origin),
            "history_start_year_month": str(history[0]),
            "history_end_year_month": str(history[-1]),
            "history_length_months": HISTORY_LENGTH_MONTHS,
            "input_eligible": True,
            "input_eligible_months": HISTORY_LENGTH_MONTHS,
            "complete_horizon_geometry": True,
            **evidence,
        }
        for horizon, target in zip(HORIZONS_MONTHS, targets, strict=True):
            records.append(
                {
                    **base,
                    "evaluation_unit_id": _stable_id(
                        "closure_v1_evaluation_unit_v1",
                        [source_id, site_id, str(origin), str(target), horizon],
                    ),
                    "target_year_month": str(target),
                    "horizon_months": horizon,
                }
            )
    return records, history_candidates, crossing_exclusions, locked_exclusions


def build_intent_origin_rows(
    precursor_rows: pd.DataFrame,
    gate: DevelopmentGate,
) -> tuple[pd.DataFrame, IntentOriginAudit]:
    """Freeze input-eligible h1--h3 geometry without consulting targets."""
    assert_development_frame(precursor_rows, gate)
    status = build_precursor_month_status(precursor_rows[PRECURSOR_READ_COLUMNS])
    assignment = gate.assignment.loc[
        lambda frame: frame["assignment_role"].eq(ASSIGNMENT_DEVELOPMENT),
        ["source_id", "site_id"],
    ]
    status = status.merge(assignment, on=["source_id", "site_id"], how="inner", validate="many_to_one")
    if status.empty:
        raise DevelopmentGuardError("No precursor status rows remain for development locations")

    records: list[dict[str, Any]] = []
    history_candidates = 0
    crossing_exclusions = 0
    locked_exclusions = 0
    for _, group in status.groupby(["source_id", "site_id"], sort=True):
        location_records, location_candidates, location_crossings, location_locked = _origin_records_for_location(
            group,
            gate,
        )
        records.extend(location_records)
        history_candidates += location_candidates
        crossing_exclusions += location_crossings
        locked_exclusions += location_locked

    if not records:
        raise DevelopmentGuardError("No input-eligible common origins remain after temporal-role checks")
    frame = pd.DataFrame.from_records(records)
    frame = frame.sort_values(FULL_KEY_COLUMNS, kind="mergesort").reset_index(drop=True)
    retained_origins = int(frame[ORIGIN_KEY_COLUMNS].drop_duplicates().shape[0])
    audit = IntentOriginAudit(
        monthly_status_rows=int(len(status)),
        input_eligible_month_rows=int(status["input_eligible"].astype(bool).sum()),
        history_candidate_origins=history_candidates,
        retained_intent_origins=retained_origins,
        excluded_role_crossing_origins=crossing_exclusions,
        excluded_locked_evaluation_origins=locked_exclusions,
    )
    return frame, audit


def _normalize_target_keys(target_key_rows: pd.DataFrame, gate: DevelopmentGate) -> pd.DataFrame:
    missing = [column for column in TARGET_KEY_COLUMNS if column not in target_key_rows.columns]
    if missing:
        raise DevelopmentGuardError(f"Target-key availability frame is missing columns: {missing}")
    if target_key_rows.empty:
        return target_key_rows[TARGET_KEY_COLUMNS].copy()
    assert_development_frame(target_key_rows, gate)
    frame = target_key_rows[TARGET_KEY_COLUMNS].copy()
    for column in ("source_id", "site_id", "origin_year_month", "target_year_month"):
        if bool(frame[column].isna().any()):
            raise DevelopmentGuardError(f"Target-key availability contains null {column}")
        frame[column] = frame[column].astype(str)
    horizons = pd.to_numeric(frame["horizon_months"], errors="coerce")
    if bool(horizons.isna().any()) or not bool(horizons.isin(HORIZONS_MONTHS).all()):
        raise DevelopmentGuardError("Target-key availability contains an invalid horizon")
    frame["horizon_months"] = horizons.astype("int8")
    if bool(frame.duplicated(TARGET_KEY_COLUMNS, keep=False).any()):
        raise DevelopmentGuardError("Target-key availability contains duplicate exact keys")

    origins = pd.PeriodIndex(frame["origin_year_month"], freq="M")
    targets = pd.PeriodIndex(frame["target_year_month"], freq="M")
    expected_targets = origins + frame["horizon_months"].to_numpy(dtype="int64")
    if not bool((expected_targets.astype(str) == targets.astype(str)).all()):
        raise DevelopmentGuardError("Target-key availability violates origin+horizon target arithmetic")
    roles = assign_pair_roles(frame, gate=gate)
    if bool(roles.isna().any()):
        raise DevelopmentGuardError("Target-key availability contains a temporal-role crossing")
    if "time_role" in target_key_rows.columns:
        observed_roles = target_key_rows["time_role"].astype("string").reset_index(drop=True)
        if not bool(observed_roles.eq(roles.reset_index(drop=True)).all()):
            raise DevelopmentGuardError("Target-key availability role differs from the locked role resolver")
    return frame.sort_values(TARGET_KEY_COLUMNS, kind="mergesort").reset_index(drop=True)


def attach_target_availability(
    intent_rows: pd.DataFrame,
    target_key_rows: pd.DataFrame,
    gate: DevelopmentGate,
) -> pd.DataFrame:
    """Left-join pre-cutoff target-key presence after intent is frozen."""
    normalized_targets = _normalize_target_keys(target_key_rows, gate)
    availability = normalized_targets.assign(_target_key_present=True)
    out = intent_rows.merge(
        availability,
        on=TARGET_KEY_COLUMNS,
        how="left",
        validate="one_to_one",
    )
    out["target_evaluable"] = out.pop("_target_key_present").fillna(False).astype(bool)
    grouped = out.groupby(ORIGIN_KEY_COLUMNS, sort=False)["target_evaluable"]
    for horizon in HORIZONS_MONTHS:
        horizon_map = (
            out.loc[out["horizon_months"].eq(horizon), ORIGIN_KEY_COLUMNS + ["target_evaluable"]]
            .set_index(ORIGIN_KEY_COLUMNS)["target_evaluable"]
        )
        origin_index = pd.MultiIndex.from_frame(out[ORIGIN_KEY_COLUMNS])
        out[f"target_evaluable_h{horizon}"] = origin_index.map(horizon_map).astype(bool)
    out["complete_targets_evaluable"] = grouped.transform("all").astype(bool)
    return out


def _model_contract_statuses(path: Path = DEFAULT_MODEL_BENCHMARK) -> dict[str, str]:
    payload = load_yaml_mapping(path)
    models = payload.get("models")
    if not isinstance(models, Mapping):
        raise DevelopmentGuardError("model_benchmark.models must be a mapping")
    statuses: dict[str, str] = {}
    for model_id in MODEL_IDS:
        model = models.get(model_id)
        if not isinstance(model, Mapping) or not isinstance(model.get("closure_eligibility"), str):
            raise DevelopmentGuardError(f"model_benchmark.models.{model_id} lacks closure_eligibility")
        statuses[model_id] = str(model["closure_eligibility"])
    return statuses


def add_model_contract_statuses(
    frame: pd.DataFrame,
    *,
    model_benchmark_path: Path = DEFAULT_MODEL_BENCHMARK,
) -> pd.DataFrame:
    out = frame.copy()
    for model_id, status in _model_contract_statuses(model_benchmark_path).items():
        out[f"model_contract_status_{model_id}"] = status
    return out


def validate_common_origin_rows(frame: pd.DataFrame, gate: DevelopmentGate) -> pd.DataFrame:
    """Validate exact three-horizon geometry and denominator metadata."""
    required = {
        "surface_id",
        "common_origin_id",
        "evaluation_unit_id",
        "holdout_group_id",
        "assignment_role",
        "time_role",
        "history_start_year_month",
        "history_end_year_month",
        "history_length_months",
        "input_eligible",
        "input_eligible_months",
        "complete_horizon_geometry",
        "target_evaluable",
        "target_evaluable_h1",
        "target_evaluable_h2",
        "target_evaluable_h3",
        "complete_targets_evaluable",
        *TARGET_KEY_COLUMNS,
        *(f"model_contract_status_{model_id}" for model_id in MODEL_IDS),
        *(f"{domain}_evidence_months" for domain in EVIDENCE_DOMAINS),
        *(f"{domain}_evidence_fraction" for domain in EVIDENCE_DOMAINS),
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise DevelopmentGuardError(f"Common-origin manifest is missing columns: {missing}")
    if frame.empty:
        raise DevelopmentGuardError("Common-origin manifest cannot be empty")
    assert_development_frame(frame, gate, role_column="time_role")
    if set(frame["surface_id"].astype(str)) != {SURFACE_ID}:
        raise DevelopmentGuardError("Common-origin manifest has an unexpected surface_id")
    if bool(frame.duplicated(FULL_KEY_COLUMNS, keep=False).any()):
        raise DevelopmentGuardError("Common-origin manifest contains duplicate exact keys")
    expected_group_ids = frame["source_id"].astype(str) + "::" + frame["site_id"].astype(str)
    if not bool(frame["holdout_group_id"].astype(str).eq(expected_group_ids).all()):
        raise DevelopmentGuardError("Common-origin holdout_group_id must equal source_id::site_id")

    calibration_end = _period(
        gate.bounds.calibration_threshold_end,
        field_name="calibration_threshold_end",
    )
    for _, group in frame.groupby(ORIGIN_KEY_COLUMNS, sort=False):
        if len(group) != len(HORIZONS_MONTHS) or set(group["horizon_months"].astype(int)) != set(HORIZONS_MONTHS):
            raise DevelopmentGuardError("Each common origin must contain exactly horizons 1, 2, and 3")
        if group["common_origin_id"].nunique(dropna=False) != 1:
            raise DevelopmentGuardError("A common origin has conflicting common_origin_id values")
        if group["time_role"].nunique(dropna=False) != 1:
            raise DevelopmentGuardError("All horizons of a common origin must share one time_role")
        if group["complete_targets_evaluable"].nunique(dropna=False) != 1:
            raise DevelopmentGuardError("A common origin has conflicting complete-target flags")
        availability_by_horizon = {
            int(row.horizon_months): bool(row.target_evaluable)
            for row in dataframe_rows(group)
        }
        for horizon in HORIZONS_MONTHS:
            expected_availability = availability_by_horizon[horizon]
            if not bool(group[f"target_evaluable_h{horizon}"].eq(expected_availability).all()):
                raise DevelopmentGuardError(
                    f"A common origin has inconsistent target_evaluable_h{horizon} metadata"
                )
        expected_complete = all(availability_by_horizon.values())
        if not bool(group["complete_targets_evaluable"].eq(expected_complete).all()):
            raise DevelopmentGuardError("complete_targets_evaluable does not equal all h1--h3 flags")

    origins = pd.PeriodIndex(frame["origin_year_month"].astype(str), freq="M")
    targets = pd.PeriodIndex(frame["target_year_month"].astype(str), freq="M")
    horizons = pd.to_numeric(frame["horizon_months"], errors="raise").astype("int64")
    if not bool(((origins + horizons.to_numpy()).astype(str) == targets.astype(str)).all()):
        raise DevelopmentGuardError("Common-origin manifest violates target month arithmetic")
    if bool((targets > calibration_end).any()):
        raise DevelopmentGuardError("Common-origin manifest materialized a target after 2021-12")
    resolved_roles = assign_pair_roles(frame, gate=gate)
    if bool(resolved_roles.isna().any()) or not bool(
        frame["time_role"].astype("string").eq(resolved_roles).all()
    ):
        raise DevelopmentGuardError("Common-origin time_role differs from the locked pair-role resolver")
    expected_history_start = origins - (HISTORY_LENGTH_MONTHS - 1)
    if not bool((expected_history_start.astype(str) == frame["history_start_year_month"].astype(str)).all()):
        raise DevelopmentGuardError("Common-origin history start is not origin minus 11 months")
    if not bool(frame["history_end_year_month"].astype(str).eq(frame["origin_year_month"].astype(str)).all()):
        raise DevelopmentGuardError("Common-origin history end must equal origin")
    if not bool(pd.to_numeric(frame["history_length_months"], errors="coerce").eq(HISTORY_LENGTH_MONTHS).all()):
        raise DevelopmentGuardError("Common-origin history length must equal 12")
    if not bool(frame["input_eligible"].astype(bool).all()):
        raise DevelopmentGuardError("Common-origin manifest contains an input-ineligible origin")
    if not bool(pd.to_numeric(frame["input_eligible_months"], errors="coerce").eq(HISTORY_LENGTH_MONTHS).all()):
        raise DevelopmentGuardError("Common-origin input_eligible_months must equal 12")
    if not bool(frame["complete_horizon_geometry"].astype(bool).all()):
        raise DevelopmentGuardError("Common-origin manifest contains incomplete horizon geometry")

    expected_origin_ids = [
        _stable_id(
            "closure_v1_common_origin_v1",
            [str(row.source_id), str(row.site_id), str(row.origin_year_month)],
        )
        for row in dataframe_rows(frame)
    ]
    if not bool(frame["common_origin_id"].astype(str).eq(expected_origin_ids).all()):
        raise DevelopmentGuardError("Common-origin IDs do not match the canonical serialization")
    expected_unit_ids = [
        _stable_id(
            "closure_v1_evaluation_unit_v1",
            [
                str(row.source_id),
                str(row.site_id),
                str(row.origin_year_month),
                str(row.target_year_month),
                int(row.horizon_months),
            ],
        )
        for row in dataframe_rows(frame)
    ]
    if not bool(frame["evaluation_unit_id"].astype(str).eq(expected_unit_ids).all()):
        raise DevelopmentGuardError("Evaluation-unit IDs do not match the canonical serialization")
    if bool(frame["evaluation_unit_id"].astype(str).duplicated(keep=False).any()):
        raise DevelopmentGuardError("evaluation_unit_id values must be unique")

    forbidden_names = [
        column
        for column in frame.columns
        if "chlorophyll" in column.lower() or "chla" in column.lower()
    ]
    if forbidden_names:
        raise DevelopmentGuardError(f"Common-origin metadata contains forbidden Chl-a lineage: {forbidden_names}")
    forbidden_assignment_metadata = {
        "stratum_id",
        "historical_bloom_presence",
        "precursor_coverage_fraction",
        "precursor_coverage_band",
        "series_length_months",
        "series_length_band",
        "deterministic_rank_sha256",
    }
    leaked_assignment_metadata = sorted(forbidden_assignment_metadata.intersection(frame.columns))
    if leaked_assignment_metadata:
        raise DevelopmentGuardError(
            f"Common-origin metadata leaks assignment strata: {leaked_assignment_metadata}"
        )
    expected_statuses = _model_contract_statuses()
    for model_id, expected_status in expected_statuses.items():
        if set(frame[f"model_contract_status_{model_id}"].astype(str)) != {expected_status}:
            raise DevelopmentGuardError(f"Model contract status drift for {model_id}")
    for domain in EVIDENCE_DOMAINS:
        counts = pd.to_numeric(frame[f"{domain}_evidence_months"], errors="coerce")
        fractions = pd.to_numeric(frame[f"{domain}_evidence_fraction"], errors="coerce")
        if bool(counts.isna().any()) or not bool(counts.between(0, HISTORY_LENGTH_MONTHS).all()):
            raise DevelopmentGuardError(f"Invalid {domain} evidence-month count")
        expected_fractions = counts / float(HISTORY_LENGTH_MONTHS)
        if bool(fractions.isna().any()) or not bool(fractions.eq(expected_fractions).all()):
            raise DevelopmentGuardError(f"Invalid {domain} evidence fraction")
    return frame.sort_values(FULL_KEY_COLUMNS, kind="mergesort").reset_index(drop=True)


def _locked_source_record(protocol_lock: Mapping[str, Any], path: Path) -> dict[str, Any]:
    logical_path = repository_relative(path)
    source_artifacts = protocol_lock.get("source_artifacts")
    if not isinstance(source_artifacts, Sequence) or isinstance(source_artifacts, (str, bytes)):
        raise DevelopmentGuardError("Protocol lock source_artifacts must be an array")
    matches = [
        item
        for item in source_artifacts
        if isinstance(item, Mapping) and item.get("path") == logical_path
    ]
    if len(matches) != 1:
        raise DevelopmentGuardError(f"Protocol lock must contain exactly one source record for {logical_path}")
    locked = matches[0]
    observed = _file_record(path)
    if locked.get("sha256") != observed["sha256"] or int(locked.get("bytes", -1)) != observed["bytes"]:
        raise DevelopmentGuardError(f"Locked source artifact changed before E0-D: {logical_path}")
    return {
        **observed,
        "role": locked.get("role"),
        "hash_source": "protocol_lock",
    }


def _scan_audit_payload(audit: DevelopmentScanAudit) -> dict[str, Any]:
    return {
        "materialized_rows": audit.materialized_rows,
        "returned_rows": audit.returned_rows,
        "boundary_crossing_rows": audit.boundary_crossing_rows,
        "role_counts": audit.role_counts,
    }


def _role_horizon_counts(frame: pd.DataFrame) -> list[dict[str, Any]]:
    counts = cast(
        pd.Series,
        frame.groupby(["time_role", "horizon_months", "target_evaluable"], dropna=False).size(),
    )
    grouped = counts.rename("rows").reset_index().sort_values(
        ["time_role", "horizon_months", "target_evaluable"]
    )
    return cast(list[dict[str, Any]], grouped.to_dict(orient="records"))


def _manifest_payload(
    *,
    output: Path,
    gate: DevelopmentGate,
    frame: pd.DataFrame,
    intent_audit: IntentOriginAudit,
    panel_scan_audit: DevelopmentScanAudit,
    target_key_scan_audit: DevelopmentScanAudit,
    source_records: Sequence[Mapping[str, Any]],
    parent_records: Sequence[Mapping[str, Any]],
    code_records: Sequence[Mapping[str, Any]],
    config_records: Sequence[Mapping[str, Any]],
    repository_state: Mapping[str, Any],
    reproduction_command: Sequence[str],
) -> dict[str, Any]:
    origin_rows = frame[ORIGIN_KEY_COLUMNS].drop_duplicates()
    role_origin_counts = (
        frame.drop_duplicates(ORIGIN_KEY_COLUMNS)
        .groupby("time_role")
        .size()
        .reindex(DEVELOPMENT_ROLES, fill_value=0)
        .astype(int)
        .to_dict()
    )
    return {
        "manifest_version": "closure_common_origin_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "execution": {
            "repository": dict(repository_state),
            "source_tree_identity": "code_config_parent_sha256_records",
            "reproduction_command": list(reproduction_command),
            "future_outcomes_semantically_decoded": False,
        },
        "future_outcomes_accessed": False,
        "target_values_projected": [],
        "target_parquet_semantically_opened": False,
        "post_cutoff_target_rows_materialized": 0,
        "target_availability_used_for_origin_selection": False,
        "availability_join": "left_after_intent_freeze",
        "assignment": {
            "path": repository_relative(gate.assignment_path),
            "bytes": gate.assignment_path.stat().st_size,
            "sha256": gate.assignment_sha256,
            **gate.expected_counts,
            "holdout_fit_overlap_count": 0,
        },
        "projections": {
            "panel": PRECURSOR_READ_COLUMNS,
            "target_keys": TARGET_KEY_COLUMNS,
            "panel_predicate": "source_id=wqp AND exact development site_id AND year_month<=2021-12",
            "target_key_predicate": (
                "source_id=wqp AND exact development site_id AND "
                "origin_year_month<=2021-12 AND target_year_month<=2021-12"
            ),
        },
        "scans": {
            "panel": _scan_audit_payload(panel_scan_audit),
            "target_keys": _scan_audit_payload(target_key_scan_audit),
        },
        "intent_origin_audit": asdict(intent_audit),
        "counts": {
            "rows": int(len(frame)),
            "intent_origins": int(len(origin_rows)),
            "sites": int(frame[["source_id", "site_id"]].drop_duplicates().shape[0]),
            "target_evaluable_rows": int(frame["target_evaluable"].sum()),
            "complete_targets_evaluable_origins": int(
                frame.loc[frame["complete_targets_evaluable"], ORIGIN_KEY_COLUMNS].drop_duplicates().shape[0]
            ),
            "intent_origins_by_role": role_origin_counts,
            "by_role_horizon_target_evaluable": _role_horizon_counts(frame),
        },
        "invariants": {
            "holdout_overlap_count": 0,
            "unknown_assignment_count": 0,
            "post_2021_materialized_count": 0,
            "chlorophyll_columns_projected": 0,
            "duplicate_exact_keys": 0,
            "rows_per_origin": 3,
            "target_arithmetic_exact": True,
            "one_role_per_origin": True,
            "history_length_months": HISTORY_LENGTH_MONTHS,
            "horizons_months": list(HORIZONS_MONTHS),
        },
        "source_inputs": list(source_records),
        "parent_artifacts": list(parent_records),
        "code": list(code_records),
        "configs": list(config_records),
        "output": _file_record(output),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the outcome-independent Closure V1 common-origin manifest."
    )
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gate = load_development_gate()
    repository_state_before = _git_execution_state()
    protocol_lock = load_json_mapping(gate.protocol_lock_path)
    source_paths = [
        args.panel,
        args.splits,
        DEFAULT_TARGETS,
        DEFAULT_TARGET_MANIFEST,
        DEFAULT_SPLIT_MANIFEST,
    ]
    source_paths = [PROJECT_ROOT / path if not path.is_absolute() else path for path in source_paths]
    source_records_before = [_locked_source_record(protocol_lock, path.resolve()) for path in source_paths]
    code_records_before = [
        _file_record(PROJECT_ROOT / path) for path in COMMON_ORIGIN_CODE_DEPENDENCIES
    ]
    config_records_before = [
        _file_record(PROJECT_ROOT / path) for path in COMMON_ORIGIN_CONFIG_DEPENDENCIES
    ]
    parent_records_before = [
        _verified_file_record(
            gate.protocol_lock_path,
            expected_sha256=gate.protocol_lock_sha256,
            role="protocol_lock",
        ),
        _verified_file_record(
            gate.holdout_manifest_path,
            expected_sha256=gate.holdout_manifest_sha256,
            role="holdout_manifest",
        ),
        _verified_file_record(
            gate.assignment_path,
            expected_sha256=gate.assignment_sha256,
            role="holdout_assignment",
        ),
    ]

    panel_rows, panel_scan_audit = scan_development_rows(
        args.panel,
        gate,
        columns=PRECURSOR_READ_COLUMNS,
        point_month_column="year_month",
    )
    intent_rows, intent_audit = build_intent_origin_rows(panel_rows, gate)

    target_keys, target_key_scan_audit = scan_development_rows(
        args.splits,
        gate,
        columns=TARGET_KEY_COLUMNS,
        origin_column="origin_year_month",
        target_column="target_year_month",
    )
    common_rows = attach_target_availability(intent_rows, target_keys, gate)
    common_rows = add_model_contract_statuses(common_rows)
    common_rows = validate_common_origin_rows(common_rows, gate)

    source_records_after = [_locked_source_record(protocol_lock, path.resolve()) for path in source_paths]
    if source_records_before != source_records_after:
        raise DevelopmentGuardError("A locked source artifact changed during common-origin construction")
    parent_records_after = [
        _verified_file_record(
            gate.protocol_lock_path,
            expected_sha256=gate.protocol_lock_sha256,
            role="protocol_lock",
        ),
        _verified_file_record(
            gate.holdout_manifest_path,
            expected_sha256=gate.holdout_manifest_sha256,
            role="holdout_manifest",
        ),
        _verified_file_record(
            gate.assignment_path,
            expected_sha256=gate.assignment_sha256,
            role="holdout_assignment",
        ),
    ]
    if parent_records_before != parent_records_after:
        raise DevelopmentGuardError("A parent gate artifact changed during common-origin construction")
    code_records_after = [
        _file_record(PROJECT_ROOT / path) for path in COMMON_ORIGIN_CODE_DEPENDENCIES
    ]
    config_records_after = [
        _file_record(PROJECT_ROOT / path) for path in COMMON_ORIGIN_CONFIG_DEPENDENCIES
    ]
    if code_records_before != code_records_after:
        raise DevelopmentGuardError("A code dependency changed during common-origin construction")
    if config_records_before != config_records_after:
        raise DevelopmentGuardError("A configuration dependency changed during common-origin construction")
    repository_state_after = _git_execution_state()
    if repository_state_before != repository_state_after:
        raise DevelopmentGuardError("Repository state changed during common-origin construction")

    output = args.output.resolve() if args.output.is_absolute() else (PROJECT_ROOT / args.output).resolve()
    manifest = args.manifest.resolve() if args.manifest.is_absolute() else (PROJECT_ROOT / args.manifest).resolve()
    _write_parquet_atomic(common_rows, output)
    payload = _manifest_payload(
        output=output,
        gate=gate,
        frame=common_rows,
        intent_audit=intent_audit,
        panel_scan_audit=panel_scan_audit,
        target_key_scan_audit=target_key_scan_audit,
        source_records=source_records_after,
        parent_records=parent_records_after,
        code_records=code_records_after,
        config_records=config_records_after,
        repository_state=repository_state_after,
        reproduction_command=_reproduction_command(args),
    )
    _write_json_atomic(payload, manifest)
    print(
        f"wrote {output} with {len(common_rows):,} rows and "
        f"{common_rows[ORIGIN_KEY_COLUMNS].drop_duplicates().shape[0]:,} intent origins",
        flush=True,
    )
    print(f"wrote completion manifest {manifest}", flush=True)


if __name__ == "__main__":
    main()
