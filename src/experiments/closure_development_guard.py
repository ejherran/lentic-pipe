#!/usr/bin/env python
"""Fail-closed runtime guard for Closure V1 development data.

This module is deliberately separate from :mod:`closure_contract`, whose
contents are part of the externally sealed E0-P protocol.  It turns the
published E0-C assignment and the locked temporal decisions into executable
runtime checks for E0-D.  It never exposes an option to include the internal
holdout and never materializes target rows after December 2021.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pyarrow.dataset as ds

from src.experiments.build_closure_holdout import (
    ASSIGNMENT_DEVELOPMENT,
    ASSIGNMENT_HOLDOUT,
    ASSIGNMENT_OUTPUT_COLUMNS,
)
from src.experiments.closure_contract import load_and_validate_analysis_plan, resolve_repo_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANALYSIS_PLAN = Path("configs/closure_v1/analysis_plan.yaml")
DEFAULT_ASSIGNMENT = Path("data/closure_v1/closure_holdout_assignment.csv")
DEFAULT_HOLDOUT_MANIFEST = Path("reports/closure_v1/00_protocol/holdout_manifest.json")
DEFAULT_PROTOCOL_LOCK = Path("reports/closure_v1/00_protocol/protocol_lock.json")

ASSIGNMENT_LOGICAL_PATH = DEFAULT_ASSIGNMENT.as_posix()
PROTOCOL_LOCK_LOGICAL_PATH = DEFAULT_PROTOCOL_LOCK.as_posix()
KEY_COLUMNS = ["source_id", "site_id"]
ROLE_TRAINING = "training"
ROLE_MODEL_SELECTION = "model_selection"
ROLE_CALIBRATION_THRESHOLD = "calibration_threshold"
DEVELOPMENT_ROLES = (
    ROLE_TRAINING,
    ROLE_MODEL_SELECTION,
    ROLE_CALIBRATION_THRESHOLD,
)
MONTH_PATTERN = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
GIT_OBJECT_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")


class DevelopmentGuardError(ValueError):
    """Raised when data would cross a locked Closure V1 development boundary."""


@dataclass(frozen=True)
class TimeRoleBounds:
    """Locked month boundaries used by E0-D."""

    training_end: str
    model_selection_start: str
    model_selection_end: str
    calibration_threshold_start: str
    calibration_threshold_end: str
    locked_evaluation_start: str


@dataclass(frozen=True)
class DevelopmentGate:
    """Validated, immutable view of the E0-C assignment and E0-D bounds."""

    assignment_path: Path
    assignment_sha256: str
    holdout_manifest_path: Path
    holdout_manifest_sha256: str
    protocol_lock_path: Path
    protocol_lock_sha256: str
    locked_repository_head: str
    repository_validated: bool
    bounds: TimeRoleBounds
    _assignment: pd.DataFrame = field(repr=False, compare=False)

    @property
    def assignment(self) -> pd.DataFrame:
        """Return a defensive copy of the assignment without feature use."""
        return self._assignment.copy(deep=True)

    @property
    def development_keys(self) -> frozenset[tuple[str, str]]:
        rows = self._assignment[self._assignment["assignment_role"] == ASSIGNMENT_DEVELOPMENT]
        return frozenset(zip(rows["source_id"], rows["site_id"], strict=True))

    @property
    def holdout_keys(self) -> frozenset[tuple[str, str]]:
        rows = self._assignment[self._assignment["assignment_role"] == ASSIGNMENT_HOLDOUT]
        return frozenset(zip(rows["source_id"], rows["site_id"], strict=True))

    @property
    def expected_counts(self) -> dict[str, int]:
        roles = self._assignment["assignment_role"].value_counts()
        return {
            "eligible_locations": int(len(self._assignment)),
            "development_locations": int(roles.get(ASSIGNMENT_DEVELOPMENT, 0)),
            "holdout_locations": int(roles.get(ASSIGNMENT_HOLDOUT, 0)),
        }


@dataclass(frozen=True)
class DevelopmentScanAudit:
    """Counts produced without exposing holdout or locked-evaluation rows."""

    materialized_rows: int
    returned_rows: int
    boundary_crossing_rows: int
    _role_counts: tuple[tuple[str, int], ...]

    @property
    def role_counts(self) -> dict[str, int]:
        return dict(self._role_counts)


def _sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_mapping(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevelopmentGuardError(f"Cannot load {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise DevelopmentGuardError(f"{label} must contain a JSON object: {path}")
    return cast(dict[str, Any], payload)


def _resolve_runtime_path(path: str | Path, *, allow_external: bool) -> Path:
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()
    if not allow_external:
        try:
            resolved.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise DevelopmentGuardError(f"Runtime path is outside the project: {path}") from exc
    return resolved


def _mapping(payload: Mapping[str, Any], key: str, *, context: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise DevelopmentGuardError(f"{context}.{key} must be a mapping")
    return value


def _canonical_month(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not MONTH_PATTERN.fullmatch(value):
        raise DevelopmentGuardError(f"{field_name} must use canonical YYYY-MM values")
    try:
        period = pd.Period(value, freq="M")
    except ValueError as exc:
        raise DevelopmentGuardError(f"{field_name} contains an invalid calendar month") from exc
    if str(period) != value:
        raise DevelopmentGuardError(f"{field_name} must use canonical YYYY-MM values")
    return value


def _month_ordinal(value: str, *, field_name: str) -> int:
    period = cast(pd.Period, pd.Period(_canonical_month(value, field_name=field_name), freq="M"))
    return int(period.ordinal)


def _month_ordinals(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise DevelopmentGuardError(f"Missing required month column: {column}")
    values = frame[column].astype("string")
    valid = values.str.fullmatch(MONTH_PATTERN, na=False)
    if not bool(valid.all()):
        sample = values.loc[~valid].head(3).tolist()
        raise DevelopmentGuardError(f"{column} contains invalid YYYY-MM values: {sample}")
    try:
        periods = pd.PeriodIndex(values.astype(str), freq="M")
    except ValueError as exc:
        raise DevelopmentGuardError(f"{column} contains invalid calendar months") from exc
    canonical = pd.Series(periods.astype(str), index=frame.index, dtype="string")
    if not bool(canonical.eq(values).all()):
        raise DevelopmentGuardError(f"{column} contains non-canonical calendar months")
    return pd.Series(periods.asi8, index=frame.index, dtype="int64")


def _load_time_role_bounds(analysis_plan_path: str | Path = DEFAULT_ANALYSIS_PLAN) -> TimeRoleBounds:
    plan, _ = load_and_validate_analysis_plan(
        analysis_plan_path,
        require_files=True,
        reject_unresolved=False,
    )
    roles = _mapping(plan, "time_roles", context="analysis_plan")
    training = _mapping(roles, "training", context="analysis_plan.time_roles")
    selection = _mapping(roles, "model_selection", context="analysis_plan.time_roles")
    calibration = _mapping(roles, "calibration_threshold", context="analysis_plan.time_roles")
    evaluation = _mapping(roles, "locked_evaluation", context="analysis_plan.time_roles")
    return TimeRoleBounds(
        training_end=_canonical_month(training.get("target_end"), field_name="time_roles.training.target_end"),
        model_selection_start=_canonical_month(
            selection.get("origin_start"), field_name="time_roles.model_selection.origin_start"
        ),
        model_selection_end=_canonical_month(
            selection.get("target_end"), field_name="time_roles.model_selection.target_end"
        ),
        calibration_threshold_start=_canonical_month(
            calibration.get("origin_start"), field_name="time_roles.calibration_threshold.origin_start"
        ),
        calibration_threshold_end=_canonical_month(
            calibration.get("target_end"), field_name="time_roles.calibration_threshold.target_end"
        ),
        locked_evaluation_start=_canonical_month(
            evaluation.get("target_start"), field_name="time_roles.locked_evaluation.target_start"
        ),
    )


def validate_assignment_frame(
    frame: pd.DataFrame,
    *,
    expected_counts: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Validate the exact E0-C schema and return a canonical sorted copy."""
    if frame.columns.tolist() != ASSIGNMENT_OUTPUT_COLUMNS:
        raise DevelopmentGuardError(
            "Closure assignment columns or order differ from the locked 11-column schema"
        )
    if frame.empty:
        raise DevelopmentGuardError("Closure assignment cannot be empty")

    out = frame.copy()
    for column in ("source_id", "site_id", "holdout_group_id", "assignment_role"):
        if bool(out[column].isna().any()):
            raise DevelopmentGuardError(f"Closure assignment contains null {column}")
        out[column] = out[column].astype(str)
        if bool(out[column].str.strip().eq("").any()):
            raise DevelopmentGuardError(f"Closure assignment contains blank {column}")

    if set(out["source_id"]) != {"wqp"}:
        raise DevelopmentGuardError("Closure assignment must contain source_id=wqp only")
    if bool(out.duplicated(KEY_COLUMNS, keep=False).any()):
        raise DevelopmentGuardError("Closure assignment has duplicate source_id/site_id keys")
    expected_group_ids = out["source_id"] + "::" + out["site_id"]
    if not bool(out["holdout_group_id"].eq(expected_group_ids).all()):
        raise DevelopmentGuardError("holdout_group_id must equal source_id::site_id")
    if bool(out["holdout_group_id"].duplicated(keep=False).any()):
        raise DevelopmentGuardError("Closure assignment has duplicate holdout_group_id values")

    roles = set(out["assignment_role"])
    expected_roles = {ASSIGNMENT_DEVELOPMENT, ASSIGNMENT_HOLDOUT}
    if roles != expected_roles:
        raise DevelopmentGuardError(f"Closure assignment roles must be exactly {sorted(expected_roles)}")
    ranks = out["deterministic_rank_sha256"].astype("string")
    if not bool(ranks.str.fullmatch(SHA256_PATTERN, na=False).all()):
        raise DevelopmentGuardError("deterministic_rank_sha256 contains invalid values")
    if bool(ranks.duplicated(keep=False).any()):
        raise DevelopmentGuardError("deterministic_rank_sha256 values must be unique")

    if expected_counts is not None:
        expected_total = int(expected_counts.get("eligible_locations", -1))
        expected_development = int(expected_counts.get("development_locations", -1))
        expected_holdout = int(expected_counts.get("holdout_locations", -1))
        observed_development = int(out["assignment_role"].eq(ASSIGNMENT_DEVELOPMENT).sum())
        observed_holdout = int(out["assignment_role"].eq(ASSIGNMENT_HOLDOUT).sum())
        observed = (len(out), observed_development, observed_holdout)
        expected = (expected_total, expected_development, expected_holdout)
        if observed != expected:
            raise DevelopmentGuardError(
                "Closure assignment counts differ from the published manifest: "
                f"observed={observed}, expected={expected}"
            )

    return out.sort_values(KEY_COLUMNS, kind="mergesort").reset_index(drop=True)


def _manifest_output_record(manifest: Mapping[str, Any], logical_path: str) -> Mapping[str, Any]:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes)):
        raise DevelopmentGuardError("holdout manifest outputs must be an array")
    matches = [item for item in outputs if isinstance(item, Mapping) and item.get("path") == logical_path]
    if len(matches) != 1:
        raise DevelopmentGuardError(f"holdout manifest must contain exactly one record for {logical_path}")
    return matches[0]


def _run_git(args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit={completed.returncode}"
        raise DevelopmentGuardError(f"Git repository validation failed: git {' '.join(args)}: {detail}")
    return completed


def _repository_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise DevelopmentGuardError(f"Repository validation path is outside the project: {path}") from exc


def _validate_repository_state(paths: Sequence[Path], *, locked_repository_head: str) -> None:
    relative_paths = [_repository_relative(path) for path in paths]
    _run_git(["ls-files", "--error-unmatch", *relative_paths])
    diff = _run_git(["diff", "--quiet", "HEAD", "--", *relative_paths], check=False)
    if diff.returncode != 0:
        raise DevelopmentGuardError("Locked assignment, manifest, or protocol lock differs from HEAD")
    _run_git(["merge-base", "--is-ancestor", locked_repository_head, "HEAD"])
    assignment_commit = _run_git(
        ["log", "-1", "--format=%H", "--", relative_paths[0]]
    ).stdout.strip()
    if not GIT_OBJECT_PATTERN.fullmatch(assignment_commit):
        raise DevelopmentGuardError("Cannot resolve the commit that published the holdout assignment")
    _run_git(["merge-base", "--is-ancestor", assignment_commit, "HEAD"])


def load_development_gate(
    *,
    assignment_path: str | Path = DEFAULT_ASSIGNMENT,
    manifest_path: str | Path = DEFAULT_HOLDOUT_MANIFEST,
    protocol_lock_path: str | Path = DEFAULT_PROTOCOL_LOCK,
    analysis_plan_path: str | Path = DEFAULT_ANALYSIS_PLAN,
    validate_repository: bool = True,
) -> DevelopmentGate:
    """Load and validate the immutable E0-C artifacts used by E0-D."""
    assignment_resolved = _resolve_runtime_path(
        assignment_path,
        allow_external=not validate_repository,
    )
    manifest_resolved = _resolve_runtime_path(
        manifest_path,
        allow_external=not validate_repository,
    )
    protocol_lock_resolved = _resolve_runtime_path(
        protocol_lock_path,
        allow_external=not validate_repository,
    )
    for label, path in (
        ("assignment", assignment_resolved),
        ("holdout manifest", manifest_resolved),
        ("protocol lock", protocol_lock_resolved),
    ):
        if not path.is_file():
            raise DevelopmentGuardError(f"Missing {label}: {path}")

    manifest = _load_json_mapping(manifest_resolved, label="holdout manifest")
    if manifest.get("status") != "completed" or manifest.get("experiment_id") != "closure_v1":
        raise DevelopmentGuardError("Holdout manifest is not the completed closure_v1 assignment manifest")
    if manifest.get("future_outcomes_accessed") is not False:
        raise DevelopmentGuardError("Holdout manifest does not attest future_outcomes_accessed=false")

    counts = _mapping(manifest, "counts", context="holdout_manifest")
    expected_counts = {
        "eligible_locations": counts.get("eligible_locations"),
        "development_locations": counts.get("development_locations"),
        "holdout_locations": counts.get("holdout_locations"),
    }
    assignment_record = _manifest_output_record(manifest, ASSIGNMENT_LOGICAL_PATH)
    assignment_hash = _sha256(assignment_resolved)
    if assignment_record.get("sha256") != assignment_hash:
        raise DevelopmentGuardError("Closure assignment SHA-256 differs from the published manifest")
    if int(assignment_record.get("bytes", -1)) != assignment_resolved.stat().st_size:
        raise DevelopmentGuardError("Closure assignment byte count differs from the published manifest")

    assignment = validate_assignment_frame(
        pd.read_csv(assignment_resolved),
        expected_counts=expected_counts,
    )

    protocol_record = _mapping(manifest, "protocol_lock", context="holdout_manifest")
    if protocol_record.get("path") != PROTOCOL_LOCK_LOGICAL_PATH:
        raise DevelopmentGuardError("Holdout manifest references an unexpected protocol lock path")
    protocol_hash = _sha256(protocol_lock_resolved)
    if protocol_record.get("sha256") != protocol_hash:
        raise DevelopmentGuardError("Protocol lock SHA-256 differs from the holdout manifest")
    protocol_lock = _load_json_mapping(protocol_lock_resolved, label="protocol lock")
    if protocol_lock.get("status") != "locked" or protocol_lock.get("experiment_id") != "closure_v1":
        raise DevelopmentGuardError("Protocol lock is not the locked closure_v1 protocol")
    if protocol_lock.get("future_outcomes_accessed") is not False:
        raise DevelopmentGuardError("Protocol lock does not attest future_outcomes_accessed=false")
    if protocol_lock.get("holdout_assignment_created") is not False:
        raise DevelopmentGuardError("Protocol lock must predate the E0-C assignment")
    locked_repository = _mapping(protocol_lock, "locked_repository", context="protocol_lock")
    locked_head = locked_repository.get("head")
    if not isinstance(locked_head, str) or not GIT_OBJECT_PATTERN.fullmatch(locked_head):
        raise DevelopmentGuardError("Protocol lock contains an invalid locked repository HEAD")
    if protocol_record.get("locked_repository_head") != locked_head:
        raise DevelopmentGuardError("Holdout manifest and protocol lock disagree on the locked HEAD")

    if validate_repository:
        _validate_repository_state(
            [assignment_resolved, manifest_resolved, protocol_lock_resolved],
            locked_repository_head=locked_head,
        )

    bounds = _load_time_role_bounds(analysis_plan_path)
    return DevelopmentGate(
        assignment_path=assignment_resolved,
        assignment_sha256=assignment_hash,
        holdout_manifest_path=manifest_resolved,
        holdout_manifest_sha256=_sha256(manifest_resolved),
        protocol_lock_path=protocol_lock_resolved,
        protocol_lock_sha256=protocol_hash,
        locked_repository_head=locked_head,
        repository_validated=validate_repository,
        bounds=bounds,
        _assignment=assignment,
    )


def _resolve_bounds(gate: DevelopmentGate | None) -> TimeRoleBounds:
    return gate.bounds if gate is not None else _load_time_role_bounds()


def assign_point_roles(
    frame: pd.DataFrame,
    *,
    month_column: str = "year_month",
    gate: DevelopmentGate | None = None,
) -> pd.Series:
    """Assign a role to same-month fit rows and reject any post-2021 row."""
    bounds = _resolve_bounds(gate)
    months = _month_ordinals(frame, month_column)
    training_end = _month_ordinal(bounds.training_end, field_name="training_end")
    selection_start = _month_ordinal(bounds.model_selection_start, field_name="model_selection_start")
    selection_end = _month_ordinal(bounds.model_selection_end, field_name="model_selection_end")
    calibration_start = _month_ordinal(
        bounds.calibration_threshold_start, field_name="calibration_threshold_start"
    )
    calibration_end = _month_ordinal(
        bounds.calibration_threshold_end, field_name="calibration_threshold_end"
    )
    if bool((months > calibration_end).any()):
        raise DevelopmentGuardError("E0-D materialized a point row after 2021-12")

    roles = pd.Series(pd.NA, index=frame.index, dtype="string", name="time_role")
    roles.loc[months <= training_end] = ROLE_TRAINING
    roles.loc[months.between(selection_start, selection_end)] = ROLE_MODEL_SELECTION
    roles.loc[months.between(calibration_start, calibration_end)] = ROLE_CALIBRATION_THRESHOLD
    if bool(roles.isna().any()):
        raise DevelopmentGuardError("Point rows do not map to the locked development roles")
    return roles


def assign_pair_roles(
    frame: pd.DataFrame,
    *,
    origin_column: str = "origin_year_month",
    target_column: str = "target_year_month",
    gate: DevelopmentGate | None = None,
) -> pd.Series:
    """Assign roles only when origin and target lie inside the same interval.

    Boundary-crossing rows receive ``pandas.NA`` so callers can exclude and
    audit them.  A materialized origin or target after 2021 is always an error.
    """
    bounds = _resolve_bounds(gate)
    origins = _month_ordinals(frame, origin_column)
    targets = _month_ordinals(frame, target_column)
    if bool((origins > targets).any()):
        raise DevelopmentGuardError("Origin month cannot be after target month")

    training_end = _month_ordinal(bounds.training_end, field_name="training_end")
    selection_start = _month_ordinal(bounds.model_selection_start, field_name="model_selection_start")
    selection_end = _month_ordinal(bounds.model_selection_end, field_name="model_selection_end")
    calibration_start = _month_ordinal(
        bounds.calibration_threshold_start, field_name="calibration_threshold_start"
    )
    calibration_end = _month_ordinal(
        bounds.calibration_threshold_end, field_name="calibration_threshold_end"
    )
    if bool(((origins > calibration_end) | (targets > calibration_end)).any()):
        raise DevelopmentGuardError("E0-D materialized an origin or target after 2021-12")

    roles = pd.Series(pd.NA, index=frame.index, dtype="string", name="time_role")
    roles.loc[(origins <= training_end) & (targets <= training_end)] = ROLE_TRAINING
    roles.loc[
        origins.between(selection_start, selection_end)
        & targets.between(selection_start, selection_end)
    ] = ROLE_MODEL_SELECTION
    roles.loc[
        origins.between(calibration_start, calibration_end)
        & targets.between(calibration_start, calibration_end)
    ] = ROLE_CALIBRATION_THRESHOLD
    return roles


def assert_development_frame(
    frame: pd.DataFrame,
    gate: DevelopmentGate,
    *,
    role_column: str | None = None,
    allowed_roles: Collection[str] | None = None,
) -> None:
    """Defense-in-depth assertion for every E0-D fit or output frame."""
    missing = [column for column in KEY_COLUMNS if column not in frame.columns]
    if missing:
        raise DevelopmentGuardError(f"Development frame is missing key columns: {missing}")
    if frame.empty:
        raise DevelopmentGuardError("Development frame cannot be empty")
    if bool(frame[KEY_COLUMNS].isna().any().any()):
        raise DevelopmentGuardError("Development frame contains null assignment keys")

    keys = set(
        zip(
            frame["source_id"].astype(str),
            frame["site_id"].astype(str),
            strict=True,
        )
    )
    holdout_overlap = keys.intersection(gate.holdout_keys)
    unknown = keys.difference(gate.development_keys).difference(gate.holdout_keys)
    if holdout_overlap:
        raise DevelopmentGuardError(
            f"Development frame contains {len(holdout_overlap)} internal-holdout location(s)"
        )
    if unknown:
        raise DevelopmentGuardError(
            f"Development frame contains {len(unknown)} unknown or unassigned location(s)"
        )
    if not keys.issubset(gate.development_keys):
        raise DevelopmentGuardError("Development frame is not a subset of the exact development assignment")

    if "assignment_role" in frame.columns:
        observed_assignment_roles = set(frame["assignment_role"].dropna().astype(str))
        if observed_assignment_roles != {ASSIGNMENT_DEVELOPMENT}:
            raise DevelopmentGuardError("Development frame assignment_role must be development only")

    if role_column is not None:
        if role_column not in frame.columns:
            raise DevelopmentGuardError(f"Development frame is missing role column: {role_column}")
        if bool(frame[role_column].isna().any()):
            raise DevelopmentGuardError("Development frame contains boundary-crossing or missing roles")
        permitted = set(allowed_roles or DEVELOPMENT_ROLES)
        observed = set(frame[role_column].astype(str))
        if not observed.issubset(permitted):
            raise DevelopmentGuardError(
                f"Development frame contains forbidden roles: {sorted(observed.difference(permitted))}"
            )

    for legacy_column in ("split", "dataset_split"):
        if legacy_column not in frame.columns:
            continue
        forbidden = frame[legacy_column].astype(str).str.lower().isin(
            {"test", "holdout", "internal_holdout", "locked_evaluation"}
        )
        if bool(forbidden.any()):
            raise DevelopmentGuardError(f"E0-D frame contains a forbidden {legacy_column} label")


def _development_assignment_frame(gate: DevelopmentGate) -> pd.DataFrame:
    assignment = gate.assignment
    return assignment.loc[
        assignment["assignment_role"].eq(ASSIGNMENT_DEVELOPMENT),
        ["source_id", "site_id", "holdout_group_id", "assignment_role"],
    ].copy()


def scan_development_rows(
    path: str | Path,
    gate: DevelopmentGate,
    *,
    columns: Sequence[str],
    point_month_column: str | None = None,
    origin_column: str | None = None,
    target_column: str | None = None,
) -> tuple[pd.DataFrame, DevelopmentScanAudit]:
    """Project and filter a Parquet source before materializing E0-D rows.

    Pair-role scans require both ``origin_column`` and ``target_column``.
    Point-role scans use ``point_month_column``.  Omitting all three is allowed
    for outcome-free history surfaces, but the returned frame has no
    ``time_role`` column.
    """
    requested = list(columns)
    if not requested or len(set(requested)) != len(requested):
        raise DevelopmentGuardError("Parquet projection columns must be non-empty and unique")
    missing_keys = [column for column in KEY_COLUMNS if column not in requested]
    if missing_keys:
        raise DevelopmentGuardError(f"Parquet projection must include assignment keys: {missing_keys}")
    pair_requested = origin_column is not None or target_column is not None
    if pair_requested and (origin_column is None or target_column is None):
        raise DevelopmentGuardError("Pair-role scans require both origin_column and target_column")
    if point_month_column is not None and pair_requested:
        raise DevelopmentGuardError("Choose either point-role or pair-role scanning, not both")
    for temporal_column in (point_month_column, origin_column, target_column):
        if temporal_column is not None and temporal_column not in requested:
            raise DevelopmentGuardError(f"Parquet projection is missing temporal column: {temporal_column}")

    source = _resolve_runtime_path(path, allow_external=not gate.repository_validated)
    if not source.exists():
        raise DevelopmentGuardError(f"Missing Parquet source: {source}")
    dataset = ds.dataset(source, format="parquet")
    missing_columns = sorted(set(requested).difference(dataset.schema.names))
    if missing_columns:
        raise DevelopmentGuardError(f"Parquet source is missing projected columns: {missing_columns}")

    development_site_ids = sorted(site_id for source_id, site_id in gate.development_keys if source_id == "wqp")
    predicate = (ds.field("source_id") == "wqp") & ds.field("site_id").isin(development_site_ids)
    if point_month_column is not None:
        predicate = predicate & (ds.field(point_month_column) <= gate.bounds.calibration_threshold_end)
    if pair_requested:
        assert origin_column is not None and target_column is not None
        predicate = predicate & (ds.field(origin_column) <= gate.bounds.calibration_threshold_end)
        predicate = predicate & (ds.field(target_column) <= gate.bounds.calibration_threshold_end)

    table = dataset.scanner(columns=requested, filter=predicate).to_table()
    frame = table.to_pandas()
    if frame.empty:
        raise DevelopmentGuardError("No rows remain after the pre-materialization development filter")
    materialized_rows = int(len(frame))
    frame["source_id"] = frame["source_id"].astype(str)
    frame["site_id"] = frame["site_id"].astype(str)
    frame = frame.merge(
        _development_assignment_frame(gate),
        on=KEY_COLUMNS,
        how="left",
        validate="many_to_one",
    )
    if bool(frame["assignment_role"].isna().any()):
        raise DevelopmentGuardError("Pre-filtered rows failed the exact development assignment join")

    boundary_crossing_rows = 0
    if point_month_column is not None:
        frame["time_role"] = assign_point_roles(frame, month_column=point_month_column, gate=gate)
    elif pair_requested:
        assert origin_column is not None and target_column is not None
        frame["time_role"] = assign_pair_roles(
            frame,
            origin_column=origin_column,
            target_column=target_column,
            gate=gate,
        )
        crossing = frame["time_role"].isna()
        boundary_crossing_rows = int(crossing.sum())
        frame = frame.loc[~crossing].copy()
        if frame.empty:
            raise DevelopmentGuardError("All materialized rows cross locked temporal-role boundaries")

    role_counts: tuple[tuple[str, int], ...]
    if "time_role" in frame.columns:
        counts = frame["time_role"].value_counts()
        role_counts = tuple(
            (role, int(counts[role]))
            for role in DEVELOPMENT_ROLES
            if role in counts.index
        )
        assert_development_frame(frame, gate, role_column="time_role")
    else:
        role_counts = tuple()
        assert_development_frame(frame, gate)

    frame = frame.reset_index(drop=True)
    return frame, DevelopmentScanAudit(
        materialized_rows=materialized_rows,
        returned_rows=int(len(frame)),
        boundary_crossing_rows=boundary_crossing_rows,
        _role_counts=role_counts,
    )


__all__ = [
    "ASSIGNMENT_DEVELOPMENT",
    "ASSIGNMENT_HOLDOUT",
    "DEVELOPMENT_ROLES",
    "DevelopmentGate",
    "DevelopmentGuardError",
    "DevelopmentScanAudit",
    "ROLE_CALIBRATION_THRESHOLD",
    "ROLE_MODEL_SELECTION",
    "ROLE_TRAINING",
    "TimeRoleBounds",
    "assert_development_frame",
    "assign_pair_roles",
    "assign_point_roles",
    "load_development_gate",
    "scan_development_rows",
    "validate_assignment_frame",
]
