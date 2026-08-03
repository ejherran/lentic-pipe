#!/usr/bin/env python
"""Materialize the deterministic Closure V1 expert no-current-Chl-a state.

This is the only Closure model-surface builder that is allowed before E0-DL.
It does not fit a model and it never reads scientific outcomes.  The physical
read is restricted to the locked expert-state projection, after which the
E0-C development guard assigns the three pre-2022 development roles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from src.experiments.closure_contract import resolve_repo_path
from src.experiments.closure_development_guard import (
    DEVELOPMENT_ROLES,
    DevelopmentGate,
    DevelopmentScanAudit,
    assign_point_roles,
    assert_development_frame,
    load_development_gate,
    scan_development_rows,
)
from src.experiments.closure_runtime_contract import (
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_RUNTIME_SCHEMA,
    ClosureRuntimeContractError,
    closure_state_deltas,
    load_and_validate_development_runtime,
    validate_autoregressive_state_mapping,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_VERSION = "closure_expert_no_current_state_manifest_v1"
LINEAGE_AUDIT_VERSION = "closure_expert_no_current_state_lineage_v1"
SEMANTIC_AUDIT_VERSION = "closure_expert_no_current_state_semantic_audit_v1"
KEY_COLUMNS = ("source_id", "site_id", "year_month")
P0_LEVEL_COLUMNS = ("yN", "yF", "yT_no_chla")
P0_SIGMA_COLUMNS = ("sigma_N", "sigma_F", "sigma_T_no_chla")
P0_DELTA_COLUMNS = ("delta_yN", "delta_yF", "delta_yT_no_chla")
FORBIDDEN_LINEAGE_TOKENS = (
    "chlorophyll",
    "chla",
    "risk_chla",
    "irc1",
    "yT_adaptive",
    "sigma_T_adaptive",
    "delta_yT_adaptive",
)


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": _manifest_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _write_json_atomic(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
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


def _dependency_snapshot(
    dependencies: Sequence[tuple[Path, str]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for raw_path, role in dependencies:
        path = raw_path.resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        record = {**_file_record(path), "role": role}
        records[str(record["path"])] = record
    return records


def _assert_unchanged(
    before: Mapping[str, Mapping[str, Any]],
    dependencies: Sequence[tuple[Path, str]],
) -> None:
    after = _dependency_snapshot(dependencies)
    if dict(before) != after:
        changed = sorted(set(before).union(after))
        raise ClosureRuntimeContractError(
            "A Closure expert-state source or implementation dependency changed "
            f"during materialization: {changed}"
        )


def _runtime_section(runtime: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = runtime.get(key)
    if not isinstance(value, Mapping):
        raise ClosureRuntimeContractError(f"development_runtime.{key} must be a mapping")
    return value


def _canonical_sort(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["_source_utf8"] = out["source_id"].map(lambda value: str(value).encode("utf-8"))
    out["_site_utf8"] = out["site_id"].map(lambda value: str(value).encode("utf-8"))
    out = out.sort_values(
        ["_source_utf8", "_site_utf8", "year_month"],
        kind="mergesort",
    )
    return out.drop(columns=["_source_utf8", "_site_utf8"]).reset_index(drop=True)


def _validate_unit_interval(frame: pd.DataFrame, columns: Sequence[str]) -> None:
    for column in columns:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if bool((~numeric.map(math.isfinite)).any()) or not bool(numeric.between(0.0, 1.0).all()):
            raise ClosureRuntimeContractError(
                f"Closure expert-state column {column!r} must be finite in [0, 1]"
            )


def load_projected_p0_anchor(
    path: Path,
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate,
) -> tuple[pd.DataFrame, DevelopmentScanAudit]:
    """Read exactly the P0 state allowlist through the development scanner."""
    state = _runtime_section(runtime, "primary_autoregressive_state")
    export = _runtime_section(state, "state_export")
    expected_path = resolve_repo_path(str(export["p0_source_path"]))
    if path.resolve() != expected_path.resolve():
        raise ClosureRuntimeContractError("P0 expert source path differs from the runtime contract")
    columns = tuple(str(value) for value in export["p0_source_projection_columns"])
    expected_columns = (*KEY_COLUMNS, *P0_LEVEL_COLUMNS, *P0_SIGMA_COLUMNS)
    if columns != expected_columns:
        raise ClosureRuntimeContractError("P0 expert source projection differs from the closed allowlist")
    frame, audit = scan_development_rows(
        path,
        gate,
        columns=columns,
        point_month_column="year_month",
    )
    return frame.loc[:, [*columns, "assignment_role", "time_role"]].copy(), audit


def build_expert_no_current_state(
    projected: pd.DataFrame,
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate,
) -> pd.DataFrame:
    """Build the exact P0 export without trusting legacy delta columns."""
    state = _runtime_section(runtime, "primary_autoregressive_state")
    mappings = _runtime_section(state, "model_state_mappings")
    p0 = _runtime_section(mappings, "P0")
    mapping = validate_autoregressive_state_mapping(
        "P0",
        _runtime_section(p0, "input_state_mapping"),
    )
    if mapping != dict(_runtime_section(p0, "target_state_mapping")):
        raise ClosureRuntimeContractError("P0 input and target state mappings must be identical")

    required = {
        *KEY_COLUMNS,
        *P0_LEVEL_COLUMNS,
        *P0_SIGMA_COLUMNS,
        "assignment_role",
        "time_role",
    }
    missing = sorted(required.difference(projected.columns))
    if missing:
        raise ClosureRuntimeContractError(f"Projected P0 anchor is missing columns: {missing}")
    if bool(projected.loc[:, list(KEY_COLUMNS)].isna().any().any()):
        raise ClosureRuntimeContractError("Projected P0 anchor contains null keys")
    if bool(projected.duplicated(list(KEY_COLUMNS), keep=False).any()):
        raise ClosureRuntimeContractError("Projected P0 anchor contains duplicate state keys")
    assert_development_frame(
        projected,
        gate,
        role_column="time_role",
        allowed_roles=DEVELOPMENT_ROLES,
    )
    _validate_unit_interval(projected, (*P0_LEVEL_COLUMNS, *P0_SIGMA_COLUMNS))

    source = projected.loc[:, [*KEY_COLUMNS, *P0_LEVEL_COLUMNS, *P0_SIGMA_COLUMNS]].copy()
    delta_records = closure_state_deltas(
        "P0",
        source.loc[:, [*KEY_COLUMNS, *P0_LEVEL_COLUMNS]].to_dict(orient="records"),
        development_keys=gate.development_keys,
    )
    deltas = pd.DataFrame(delta_records)
    out = projected.loc[:, [*KEY_COLUMNS, "time_role", *P0_LEVEL_COLUMNS, *P0_SIGMA_COLUMNS]].merge(
        deltas,
        on=list(KEY_COLUMNS),
        how="left",
        validate="one_to_one",
    )
    export = _runtime_section(state, "state_export")
    output_columns = tuple(str(value) for value in export["p0_output_columns"])
    if set(out.columns) != set(output_columns):
        raise ClosureRuntimeContractError(
            "P0 expert state does not match the exact output allowlist"
        )
    out = _canonical_sort(out.loc[:, output_columns])
    return validate_expert_state(out, runtime=runtime, gate=gate)


def validate_expert_state(
    frame: pd.DataFrame,
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate,
) -> pd.DataFrame:
    state = _runtime_section(runtime, "primary_autoregressive_state")
    export = _runtime_section(state, "state_export")
    expected_columns = tuple(str(value) for value in export["p0_output_columns"])
    if tuple(frame.columns) != expected_columns:
        raise ClosureRuntimeContractError("P0 expert output columns are not the closed ordered allowlist")
    forbidden = sorted(
        column
        for column in frame.columns
        if any(token.lower() in column.lower() for token in FORBIDDEN_LINEAGE_TOKENS)
        and column not in {"yT_no_chla", "sigma_T_no_chla", "delta_yT_no_chla"}
    )
    if forbidden:
        raise ClosureRuntimeContractError(f"P0 expert output contains forbidden lineage: {forbidden}")
    if bool(frame.duplicated(list(KEY_COLUMNS), keep=False).any()):
        raise ClosureRuntimeContractError("P0 expert output contains duplicate keys")
    assert_development_frame(
        frame,
        gate,
        role_column="time_role",
        allowed_roles=DEVELOPMENT_ROLES,
    )
    _validate_unit_interval(frame, (*P0_LEVEL_COLUMNS, *P0_SIGMA_COLUMNS))
    for column in P0_DELTA_COLUMNS:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if bool((~numeric.map(math.isfinite)).any()) or not bool(numeric.between(-1.0, 1.0).all()):
            raise ClosureRuntimeContractError(
                f"Closure expert-state delta {column!r} must be finite in [-1, 1]"
            )
    if str(frame["year_month"].max()) > str(export["latest_state_month"]):
        raise ClosureRuntimeContractError("P0 expert output materialized a row after 2021-12")
    return frame


def audit_materialized_expert_state(
    path: Path,
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate | None = None,
) -> dict[str, Any]:
    """Semantically audit only the outcome-free expert-state Parquet.

    This deliberately reads the generated expert state, never target or
    post-2021 outcome tables.  It reuses the same closed allowlist, assignment
    guard, time-role geometry, and delta implementation as the builder.
    """
    active_gate = gate or load_development_gate()
    state = _runtime_section(runtime, "primary_autoregressive_state")
    export = _runtime_section(state, "state_export")
    expected_columns = tuple(str(value) for value in export["p0_output_columns"])
    if not path.is_file():
        raise ClosureRuntimeContractError(
            f"Closure expert-state Parquet is missing: {_manifest_path(path)}"
        )
    frame = pd.read_parquet(path)
    validated = validate_expert_state(frame, runtime=runtime, gate=active_gate)

    location_keys = frozenset(
        zip(
            validated["source_id"].astype(str),
            validated["site_id"].astype(str),
            strict=True,
        )
    )
    holdout_overlap = location_keys.intersection(active_gate.holdout_keys)
    unknown = location_keys.difference(active_gate.development_keys).difference(
        active_gate.holdout_keys
    )
    if holdout_overlap or unknown or location_keys != active_gate.development_keys:
        raise ClosureRuntimeContractError(
            "Closure expert-state Parquet must contain exactly the 353 development locations"
        )

    expected_roles = assign_point_roles(validated, gate=active_gate)
    observed_roles = validated["time_role"].astype("string")
    if not bool(observed_roles.eq(expected_roles).all()):
        raise ClosureRuntimeContractError(
            "Closure expert-state time roles differ from the locked calendar bounds"
        )

    source = validated.loc[:, [*KEY_COLUMNS, *P0_LEVEL_COLUMNS]].copy()
    expected_deltas = pd.DataFrame(
        closure_state_deltas(
            "P0",
            source.to_dict(orient="records"),
            development_keys=active_gate.development_keys,
        )
    )
    observed_deltas = validated.loc[:, [*KEY_COLUMNS, *P0_DELTA_COLUMNS, "delta_previous_month_missing"]]
    compared = observed_deltas.merge(
        expected_deltas,
        on=list(KEY_COLUMNS),
        how="outer",
        validate="one_to_one",
        suffixes=("_observed", "_expected"),
        indicator=True,
    )
    if not bool(compared["_merge"].eq("both").all()):
        raise ClosureRuntimeContractError("Closure expert-state delta keys drifted")
    for column in P0_DELTA_COLUMNS:
        difference = (
            pd.to_numeric(compared[f"{column}_observed"], errors="coerce")
            - pd.to_numeric(compared[f"{column}_expected"], errors="coerce")
        ).abs()
        if bool(difference.isna().any()) or bool(difference.gt(1e-7).any()):
            raise ClosureRuntimeContractError(
                f"Closure expert-state delta {column!r} differs from exact-month recomputation"
            )
    if not bool(
        compared["delta_previous_month_missing_observed"]
        .astype(bool)
        .eq(compared["delta_previous_month_missing_expected"].astype(bool))
        .all()
    ):
        raise ClosureRuntimeContractError(
            "Closure expert-state missing-previous-month flags drifted"
        )

    role_counts = {
        role: int(validated["time_role"].eq(role).sum()) for role in DEVELOPMENT_ROLES
    }
    return {
        "audit_version": SEMANTIC_AUDIT_VERSION,
        "schema_allowlist_verified": tuple(validated.columns) == expected_columns,
        "exact_development_locations_verified": True,
        "zero_holdout_overlap": len(holdout_overlap) == 0,
        "zero_unknown_assignment_overlap": len(unknown) == 0,
        "locked_time_roles_verified": True,
        "unit_interval_values_verified": True,
        "signed_deltas_verified": True,
        "exact_month_delta_recomputation_verified": True,
        "no_post_2021_materialization": True,
        "future_outcomes_accessed": False,
        "rows": int(len(validated)),
        "locations": len(location_keys),
        "minimum_year_month": str(validated["year_month"].min()),
        "maximum_year_month": str(validated["year_month"].max()),
        "role_counts": role_counts,
        "delta_previous_month_missing_count": int(
            validated["delta_previous_month_missing"].sum()
        ),
        "source_projection": list(export["p0_source_projection_columns"]),
        "output_allowlist": list(expected_columns),
    }


def expert_lineage_audit(
    frame: pd.DataFrame,
    *,
    runtime: Mapping[str, Any],
    scan_audit: DevelopmentScanAudit,
) -> dict[str, Any]:
    state = _runtime_section(runtime, "primary_autoregressive_state")
    export = _runtime_section(state, "state_export")
    role_counts = {
        role: int(frame["time_role"].eq(role).sum()) for role in DEVELOPMENT_ROLES
    }
    checks = {
        "exact_raw_projection": True,
        "locked_development_key_membership": True,
        "zero_holdout_overlap": True,
        "zero_unknown_assignment_overlap": True,
        "exact_state_mapping": True,
        "no_current_chla_state_allowlist": True,
        "one_month_delta_geometry": True,
        "no_optional_context_columns": True,
        "no_post_2021_materialization": True,
    }
    return {
        "audit_version": LINEAGE_AUDIT_VERSION,
        "status": "passed",
        "experiment_id": "closure_v1",
        "surface_id": str(state["surface_id"]),
        "future_outcomes_accessed": False,
        "post_2021_outcomes_materialized": False,
        "e0_u_authorized": False,
        "checks": checks,
        "source_projection": list(export["p0_source_projection_columns"]),
        "output_allowlist": list(export["p0_output_columns"]),
        "rows": int(len(frame)),
        "locations": int(frame.loc[:, ["source_id", "site_id"]].drop_duplicates().shape[0]),
        "minimum_year_month": str(frame["year_month"].min()),
        "maximum_year_month": str(frame["year_month"].max()),
        "role_counts": role_counts,
        "delta_previous_month_missing_count": int(frame["delta_previous_month_missing"].sum()),
        "scan": {
            "materialized_rows": scan_audit.materialized_rows,
            "returned_rows": scan_audit.returned_rows,
            "boundary_crossing_rows": scan_audit.boundary_crossing_rows,
            "role_counts": scan_audit.role_counts,
        },
        "zero_holdout_overlap": True,
        "zero_unknown_assignment_overlap": True,
        "full_current_chla_sibling_columns": False,
        "optional_context_columns": [],
        "delta_geometry": "current_minus_exact_previous_calendar_month",
    }


def write_expert_bundle(
    frame: pd.DataFrame,
    *,
    output_path: Path,
    lineage_path: Path,
    manifest_path: Path,
    lineage: Mapping[str, Any],
    manifest_base: Mapping[str, Any],
) -> dict[str, Any]:
    """Write Parquet, then lineage audit, and the completion manifest last."""
    _write_parquet_atomic(frame, output_path)
    _write_json_atomic(lineage, lineage_path)
    payload = dict(manifest_base)
    payload["outputs"] = [
        {**_file_record(output_path), "role": "expert_no_current_state"},
        {**_file_record(lineage_path), "role": "lineage_audit"},
    ]
    _write_json_atomic(payload, manifest_path)
    return payload


def expert_dependency_paths_and_roles(
    *,
    runtime_config: Path,
    runtime_schema: Path,
    source_path: Path,
    gate: DevelopmentGate,
    runtime: Mapping[str, Any],
) -> list[tuple[Path, str]]:
    authority = _runtime_section(runtime, "authority")
    return [
        (runtime_config, "development_runtime_config"),
        (runtime_schema, "development_runtime_schema"),
        (source_path, "restored_expert_anchor_source"),
        (gate.assignment_path, "holdout_assignment"),
        (gate.holdout_manifest_path, "holdout_manifest"),
        (gate.protocol_lock_path, "protocol_lock"),
        (
            resolve_repo_path(str(authority["common_origin_manifest_path"])),
            "common_origin",
        ),
        (
            resolve_repo_path(str(authority["common_origin_completion_manifest_path"])),
            "common_origin_completion_manifest",
        ),
        (Path(__file__), "strict_expert_state_adapter"),
        (
            PROJECT_ROOT / "src/experiments/closure_runtime_contract.py",
            "runtime_contract_validator",
        ),
        (
            PROJECT_ROOT / "src/experiments/closure_development_guard.py",
            "closure_development_guard",
        ),
        (PROJECT_ROOT / "src/experiments/closure_contract.py", "closure_contract"),
        (
            PROJECT_ROOT / "src/experiments/build_closure_holdout.py",
            "holdout_assignment_builder",
        ),
        (PROJECT_ROOT / "src/pandas_utils.py", "pandas_utils"),
    ]


def expert_bundle_contract(
    runtime: Mapping[str, Any],
    *,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    runtime_schema: Path = DEFAULT_RUNTIME_SCHEMA,
    gate: DevelopmentGate | None = None,
) -> dict[str, Any]:
    """Return the exact physical provenance contract for the expert bundle."""
    active_gate = gate or load_development_gate()
    config_path = resolve_repo_path(runtime_config)
    schema_path = resolve_repo_path(runtime_schema)
    state = _runtime_section(runtime, "primary_autoregressive_state")
    export = _runtime_section(state, "state_export")
    source_path = resolve_repo_path(str(export["p0_source_path"]))
    p0 = _runtime_section(
        _runtime_section(state, "model_state_mappings"),
        "P0",
    )
    dependencies = expert_dependency_paths_and_roles(
        runtime_config=config_path,
        runtime_schema=schema_path,
        source_path=source_path,
        gate=active_gate,
        runtime=runtime,
    )
    return {
        "surface_id": str(state["surface_id"]),
        "state_mapping": dict(_runtime_section(p0, "input_state_mapping")),
        "runtime": {
            "config_path": _manifest_path(config_path),
            "config_sha256": _sha256_file(config_path),
            "schema_path": _manifest_path(schema_path),
            "schema_sha256": _sha256_file(schema_path),
            "fit_authorized": False,
        },
        "script": {**_file_record(Path(__file__)), "role": "generating_script"},
        "inputs": [
            {**_file_record(source_path), "role": "locked_expert_anchor"},
            {**_file_record(active_gate.assignment_path), "role": "holdout_assignment"},
        ],
        "dependencies": list(_dependency_snapshot(dependencies).values()),
        "source_projection": list(export["p0_source_projection_columns"]),
        "output_allowlist": list(export["p0_output_columns"]),
        "time_roles": list(DEVELOPMENT_ROLES),
        "dependency_paths_and_roles": dependencies,
    }


def require_pristine_expert_bundle(runtime: Mapping[str, Any]) -> None:
    """Reject any final, pointer, or temporary H artifact before row I/O."""
    artifacts = _runtime_section(runtime, "artifacts")
    output = resolve_repo_path(str(artifacts["expert_state_path"]))
    lineage = resolve_repo_path(str(artifacts["expert_state_lineage_audit_path"]))
    manifest = resolve_repo_path(str(artifacts["expert_state_manifest_path"]))
    pointer = output.with_suffix(output.suffix + ".dvc")
    planned = (output, lineage, manifest, pointer)
    candidates = [
        candidate
        for path in planned
        for candidate in (path, path.with_suffix(path.suffix + ".tmp"))
    ]
    existing = [_manifest_path(path) for path in candidates if path.exists()]
    if existing:
        raise ClosureRuntimeContractError(
            "Closure expert-state H is one-shot; existing artifacts require "
            f"review and authorized removal: {existing}"
        )


def require_published_h0(runtime: Mapping[str, Any]) -> dict[str, Any]:
    """Lazily prove that the clean H0 source HEAD is already public."""
    from src.experiments.closure_development_runtime_lock import (  # noqa: PLC0415
        clean_published_repository_identity,
    )

    return clean_published_repository_identity(runtime, verify_remote=True)


def materialize_expert_state(
    *,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    runtime_schema: Path = DEFAULT_RUNTIME_SCHEMA,
) -> dict[str, Any]:
    runtime, runtime_summary = load_and_validate_development_runtime(
        runtime_config,
        runtime_schema,
        cross_validate_locked=False,
        validate_repository=False,
    )
    if runtime_summary.get("implementation_lock_present") is not False:
        raise ClosureRuntimeContractError(
            "The deterministic expert state is a pre-E0-DL artifact and cannot be rebuilt "
            "after an implementation lock exists"
        )
    if runtime_summary.get("fit_authorized") is not False:
        raise ClosureRuntimeContractError(
            "The deterministic expert state cannot be rebuilt after development fit is authorized"
        )
    source_repository = require_published_h0(runtime)
    require_pristine_expert_bundle(runtime)
    validated_runtime, validated_summary = load_and_validate_development_runtime(
        runtime_config,
        runtime_schema,
        cross_validate_locked=True,
        validate_repository=True,
    )
    if validated_runtime != runtime:
        raise ClosureRuntimeContractError(
            "Closure runtime changed between H0 publication and full validation"
        )
    if (
        validated_summary.get("implementation_lock_present") is not False
        or validated_summary.get("fit_authorized") is not False
    ):
        raise ClosureRuntimeContractError(
            "The deterministic expert state cannot cross the E0-DL boundary"
        )
    runtime_summary = validated_summary
    gate = load_development_gate()
    state = _runtime_section(runtime, "primary_autoregressive_state")
    export = _runtime_section(state, "state_export")
    artifacts = _runtime_section(runtime, "artifacts")
    source_path = resolve_repo_path(str(export["p0_source_path"]))
    expected_hash = str(
        _runtime_section(_runtime_section(runtime, "anfis"), "source_projection")[
            "expert_anchor_sha256"
        ]
    )
    if _sha256_file(source_path) != expected_hash:
        raise ClosureRuntimeContractError("Restored expert anchor differs from its locked SHA-256")

    bundle_contract = expert_bundle_contract(
        runtime,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        gate=gate,
    )
    dependencies = bundle_contract.pop("dependency_paths_and_roles")
    before = {
        str(record["path"]): record
        for record in bundle_contract["dependencies"]
    }
    projected, scan_audit = load_projected_p0_anchor(source_path, runtime=runtime, gate=gate)
    frame = build_expert_no_current_state(projected, runtime=runtime, gate=gate)
    lineage = expert_lineage_audit(frame, runtime=runtime, scan_audit=scan_audit)
    _assert_unchanged(before, dependencies)

    output_path = resolve_repo_path(str(artifacts["expert_state_path"]))
    lineage_path = resolve_repo_path(str(artifacts["expert_state_lineage_audit_path"]))
    manifest_path = resolve_repo_path(str(artifacts["expert_state_manifest_path"]))
    generated_at = datetime.now(timezone.utc).isoformat()
    manifest_base: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "status": "completed",
        "generated_at_utc": generated_at,
        "experiment_id": "closure_v1",
        "surface_id": bundle_contract["surface_id"],
        "model_id": "P0",
        "artifact_role": "deterministic_expert_state_pre_e0_dl",
        "future_outcomes_accessed": False,
        "post_2021_outcomes_materialized": False,
        "zero_holdout_overlap": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "runtime": bundle_contract["runtime"],
        "state_mapping": bundle_contract["state_mapping"],
        "source_projection": bundle_contract["source_projection"],
        "output_allowlist": bundle_contract["output_allowlist"],
        "time_roles": bundle_contract["time_roles"],
        "source_repository": source_repository,
        "counts": {
            "rows": int(len(frame)),
            "locations": int(frame.loc[:, ["source_id", "site_id"]].drop_duplicates().shape[0]),
            "delta_previous_month_missing": int(frame["delta_previous_month_missing"].sum()),
        },
        "script": bundle_contract["script"],
        "inputs": bundle_contract["inputs"],
        "dependencies": bundle_contract["dependencies"],
        "completion_marker_written_last": True,
    }
    payload = write_expert_bundle(
        frame,
        output_path=output_path,
        lineage_path=lineage_path,
        manifest_path=manifest_path,
        lineage=lineage,
        manifest_base=manifest_base,
    )
    print(f"wrote {output_path} ({len(frame):,} rows)")
    print(f"wrote {lineage_path}")
    print(f"wrote {manifest_path}")
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_RUNTIME_SCHEMA)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    materialize_expert_state(runtime_config=args.config, runtime_schema=args.schema)


if __name__ == "__main__":
    main()
