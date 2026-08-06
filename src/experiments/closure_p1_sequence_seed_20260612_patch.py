#!/usr/bin/env python
"""Validate the additive Closure V1 P1/20260612 sequence authority.

E0-MH is a builder-only successor to the published P1/1729 unavailable
consumer evidence.  It reconstructs E0-MC and E0-MG from immutable Git
history, binds the published P1/1729 sequence+consumer bundle, binds the
already-published ANFIS state for seed 20260612, and authorizes exactly one
future P1 sequence build for seed 20260612.  It never authorizes training,
evaluation, E0-M, E0-U, DVC mutation, or outcome access.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments import audit_closure_p0_model_availability as availability
from src.experiments import closure_contract
from src.experiments import closure_p1_sequence_builder_patch as e0_mb
from src.experiments import closure_p1_sequence_historical_anfis_patch as e0_mc
from src.experiments import closure_p1_temporal_consumer_schema_subset_patch as e0_mg
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_p1_sequence_seed_20260612_patch_lock_v1"
PATCH_GATE = "E0-MH"
PATCH_ID = "p1_sequence_seed_20260612_authority_patch_1"
PATCH_STATUS = "locked"
EXPERIMENT_ID = "closure_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
PUBLISHED_REF = "origin/main"

AUTHORIZED_MODEL_ID = "P1"
AUTHORIZED_BASE_SEED = 20_260_612

E0_MC_H_COMMIT = "5bdac0fe8279297dbdb04e38146726431511fe7a"
E0_MC_P_COMMIT = "d76f35b20a0d5b5515ec31acbca1e953730afce4"
E0_MG_H_COMMIT = "fb0280f795606b1bfcb379ae9e0bb1e1879b47b8"
E0_MG_P_COMMIT = "730cd7df72039dc12c4f7a9a3793c2f5f893b5e3"
P1_1729_CONSUMER_COMMIT = "5d8bbef0fe58e57cd2180570bd6aef5f07923781"
P1_1729_SEQUENCE_COMMIT = e0_mg.P1_BUNDLE_COMMIT
ANFIS_20260612_COMMIT = "b16b27d5e38afae493202bba7576bb0c4f52283e"
PATCH_BASE_COMMIT = P1_1729_CONSUMER_COMMIT

DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/p1_sequence_seed_20260612_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "p1_sequence_seed_20260612_patch_lock_manifest.json"
)
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/p1_sequence_seed_20260612_patch_lock.schema.json"
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): "p1_sequence_seed_20260612_patch_lock_schema",
    "docs/closure_v1/E0_M_P1_SEQUENCE_SEED_20260612_PATCH_1.md": (
        "p1_sequence_seed_20260612_patch_protocol"
    ),
    "src/experiments/build_closure_pipe_sequences.py": (
        "p1_sequence_seed_20260612_gate_routing"
    ),
    "src/experiments/closure_p1_sequence_seed_20260612_patch.py": (
        "p1_sequence_seed_20260612_patch_validator"
    ),
    "src/experiments/lock_closure_p1_sequence_seed_20260612_patch.py": (
        "p1_sequence_seed_20260612_patch_locker"
    ),
    "tests/test_build_closure_pipe_sequences.py": (
        "p1_sequence_seed_20260612_builder_gate_tests"
    ),
    "tests/test_closure_p1_sequence_seed_20260612_patch.py": (
        "p1_sequence_seed_20260612_patch_tests"
    ),
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_MODIFIED_PATHS = (
    "src/experiments/build_closure_pipe_sequences.py",
    "tests/test_build_closure_pipe_sequences.py",
)
PATCH_ADDED_PATHS = tuple(
    path for path in PATCH_PATHS if path not in PATCH_MODIFIED_PATHS
)

E0_MC_SUPERSEDED_PATHS = PATCH_MODIFIED_PATHS
E0_MC_PRESERVED_PATHS = tuple(
    path for path in e0_mc.PATCH_PATHS if path not in E0_MC_SUPERSEDED_PATHS
)

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_p1_sequence_seed_20260612_patch.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_closure_p1_temporal_consumer_schema_subset_patch.py",
    "-q",
)
# Exact closed collection for the three H-E0-MH focal files above.  Earlier
# one-shot suites encode pristine 1729 namespaces and are historical evidence,
# not executable predicates after the published 1729 sequence+consumer bundle.
FOCUSED_TEST_COUNT = 114
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")

P1_1729_SEQUENCE_PATH = Path(
    "data/closure_v1/development/sequences/P1/seed_1729.parquet"
)
P1_1729_POINTER_PATH = Path(f"{P1_1729_SEQUENCE_PATH.as_posix()}.dvc")
P1_1729_SUMMARY_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P1/seed_1729_summary.csv"
)
P1_1729_SEQUENCE_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P1/seed_1729_manifest.json"
)
P1_1729_REPORT_PATH = Path(
    "reports/closure_v1/02_models/P1/seed_1729_report.md"
)
P1_1729_MODEL_MANIFEST_PATH = Path(
    "reports/closure_v1/02_models/P1/seed_1729_manifest.json"
)
P1_1729_PRESENT_PATHS = (
    P1_1729_SEQUENCE_PATH,
    P1_1729_POINTER_PATH,
    P1_1729_SUMMARY_PATH,
    P1_1729_SEQUENCE_MANIFEST_PATH,
    P1_1729_REPORT_PATH,
    P1_1729_MODEL_MANIFEST_PATH,
)
P1_1729_SEQUENCE_COMMIT_PATHS = (
    P1_1729_POINTER_PATH.as_posix(),
    P1_1729_SEQUENCE_MANIFEST_PATH.as_posix(),
    P1_1729_SUMMARY_PATH.as_posix(),
    "src/experiments/audit_closure_p1_sequence_bundle.py",
    "tests/test_audit_closure_p1_sequence_bundle.py",
)

ANFIS_20260612_STATE_PATH = Path(
    "data/closure_v1/development/anfis/seed_20260612/"
    "adaptive_no_current_state.parquet"
)
ANFIS_20260612_POINTER_PATH = Path(
    f"{ANFIS_20260612_STATE_PATH.as_posix()}.dvc"
)
ANFIS_20260612_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/anfis/seed_20260612/manifest.json"
)

EXPECTED_ARTIFACTS = {
    P1_1729_SEQUENCE_PATH.as_posix(): (1_380_222, "860da77ac60c1aefb88cc9359631badc676864c77fb6df1d4b1ab87e01992069"),
    P1_1729_POINTER_PATH.as_posix(): (100, "2281aee7f23f714837bf441b10b7c1c43829b830d4841ffe0513f9abbcf83db6"),
    P1_1729_SUMMARY_PATH.as_posix(): (356, "a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e"),
    P1_1729_SEQUENCE_MANIFEST_PATH.as_posix(): (6_527, "5f1086b9409dac13625d77759badd8f3e9ba39a140a1d578da5ef6285f0295ea"),
    P1_1729_REPORT_PATH.as_posix(): (174, "aea483a6ba91d448fa0b743825ea9cb2284878f6b2b097fce53f6711216bfa6d"),
    P1_1729_MODEL_MANIFEST_PATH.as_posix(): (13_416, "3e95ee94ef1ae076d969bf7782b58a79b30a8e3d537e62efb16248e39b95e36a"),
    ANFIS_20260612_STATE_PATH.as_posix(): (1_214_885, "99b4bc37de88d76068c044423071046cb6b0341056024c4de41cd1af51d09d26"),
    ANFIS_20260612_POINTER_PATH.as_posix(): (116, "7c88755a0cb55a6a177bf6f883f1e879221a5e415e3fd243fc27576051cd00e2"),
    ANFIS_20260612_MANIFEST_PATH.as_posix(): (20_883, "e7523963c6f09ea83235d9578d492ec34a654ce8328f79f1b05e49aa84669053"),
}

PATCH_CORRECTION = {
    "issue_id": "p1_sequence_next_seed_authority_1",
    "classification": "ordered_seed_progression_authority_only",
    "historical_e0_mc_effective_loader_called": False,
    "historical_e0_mg_effective_loader_called": False,
    "p1_1729_consumer_preserved": True,
    "authorized_next_seed": AUTHORIZED_BASE_SEED,
    "scientific_sequence_contract_changed": False,
    "state_mapping_changed": False,
    "denominator_changed": False,
    "outcome_access_changed": False,
}
PATCH_AUTHORIZATIONS = {
    "prior_p1_1729_slot_completed": True,
    "authorized_model_id": AUTHORIZED_MODEL_ID,
    "authorized_base_seed": AUTHORIZED_BASE_SEED,
    "p1_sequence_builder_authorized": False,
    "effective_in_payload": False,
    "publication_required": True,
    "batch_seed_execution_authorized": False,
    "retry_authorized": False,
    "p1_consumer_authorized": False,
    "p1_fit_authorized": False,
    "dvc_commands_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "future_outcomes_accessed": False,
}
EFFECTIVE_AUTHORIZATIONS = {
    **PATCH_AUTHORIZATIONS,
    "p1_sequence_builder_authorized": True,
    "effective_in_payload": False,
    "publication_required": False,
    "authorization_effective": True,
}
PATCH_SEALS = {
    "e0_mc_preserved_as_historical_authority": True,
    "e0_mg_preserved_as_historical_authority": True,
    "p1_1729_sequence_bundle_preserved": True,
    "p1_1729_consumer_bundle_preserved": True,
    "anfis_20260612_state_bundle_preserved": True,
    "only_builder_and_test_superseded_from_e0_mc": True,
    "target_seed_namespace_absent_at_lock": True,
    "later_seed_namespaces_absent_at_lock": True,
    "scientific_sequence_contract_changed": False,
    "seed_order_changed": False,
    "holdout_accessed": False,
    "post_2021_outcomes_accessed": False,
    "does_not_replace_e0_m": True,
}


class P1SequenceSeed20260612PatchError(RuntimeError):
    """Raised when E0-MH cannot prove its closed next-seed authority."""


def _translate(error: BaseException) -> P1SequenceSeed20260612PatchError:
    return P1SequenceSeed20260612PatchError(str(error))


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _path_digest(paths: Sequence[str]) -> str:
    return _sha256_bytes("\n".join(paths).encode("utf-8"))


def _record_digest(records: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_bytes(
        json.dumps(
            list(records),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


def _git(*args: str) -> str:
    try:
        return e0_mc._git(*args)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _require_commit(value: str, *, context: str) -> str:
    try:
        return e0_mc._require_commit(value, context=context)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _require_ancestor(ancestor: str, descendant: str) -> None:
    try:
        e0_mc._require_ancestor(ancestor, descendant)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _git_blob(commit: str, path: str) -> bytes:
    try:
        return e0_mc._git_blob(commit, path)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _git_record(commit: str, path: str, *, role: str) -> dict[str, Any]:
    payload = _git_blob(commit, path)
    return {
        "path": path,
        "role": role,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _file_record(path: Path, *, role: str) -> dict[str, Any]:
    try:
        return e0_mc._file_record(path, role=role)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _load_regular_json(path: Path, *, context: str) -> dict[str, Any]:
    try:
        return e0_mc._load_regular_json(path, context=context)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _keyword_occurrences(value: Any, keyword: str) -> int:
    if isinstance(value, Mapping):
        return sum(
            (1 if key == keyword else 0) + _keyword_occurrences(child, keyword)
            for key, child in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return sum(_keyword_occurrences(child, keyword) for child in value)
    return 0


def preflight_p1_sequence_seed_20260612_patch_schema(
    schema_path: Path = DEFAULT_PATCH_LOCK_SCHEMA,
) -> dict[str, Any]:
    """Prove the physical E0-MH schema is supported before heavy checks."""
    if schema_path != DEFAULT_PATCH_LOCK_SCHEMA:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH schema preflight requires the closed default path"
        )
    schema = _load_regular_json(schema_path, context="E0-MH schema preflight")
    minimum_count = _keyword_occurrences(schema, "minimum")
    format_count = _keyword_occurrences(schema, "format")
    if minimum_count or format_count:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH schema contains unsupported keywords: "
            f"minimum={minimum_count}, format={format_count}"
        )
    validator = getattr(closure_contract, "_assert_supported_json_schema", None)
    if not callable(validator):
        raise P1SequenceSeed20260612PatchError(
            "E0-MH schema-definition validator is unavailable"
        )
    try:
        validator(schema)
    except ClosureContractError as exc:
        raise _translate(exc) from exc
    record = _file_record(
        schema_path,
        role="p1_sequence_seed_20260612_patch_lock_schema",
    )
    if type(record["bytes"]) is not int or record["bytes"] <= 0:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH schema must be a non-empty regular JSON file"
        )
    return {
        "gate": PATCH_GATE,
        "schema_path": schema_path.as_posix(),
        "schema_bytes": record["bytes"],
        "schema_sha256": record["sha256"],
        "supported_subset_verified": True,
        "minimum_keyword_absent": True,
        "format_keyword_absent": True,
    }


def _canonical_json_record(
    payload: Mapping[str, Any],
    path: Path,
    *,
    role: str,
    context: str,
) -> dict[str, Any]:
    try:
        return e0_mc._canonical_json_record(
            payload,
            path,
            role=role,
            context=context,
        )
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _introduced_commit(path: str) -> str:
    try:
        return e0_mc._introduced_commit(path)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _observed_diff_entries(base: str, head: str) -> list[dict[str, str]]:
    try:
        return e0_mc._observed_diff_entries(base, head)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _assert_paths_untouched(
    base: str,
    descendant: str,
    paths: Sequence[str],
    *,
    context: str,
) -> None:
    try:
        e0_mc._assert_paths_untouched(base, descendant, paths, context=context)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _remote_main_oid() -> str:
    try:
        return e0_mc._remote_main_oid()
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _path_entry_exists(path: Path) -> bool:
    return availability._path_entry_exists(path)


def _expected_artifact_record(path: Path, *, role: str) -> dict[str, Any]:
    expected = EXPECTED_ARTIFACTS[path.as_posix()]
    record = _file_record(path, role=role)
    if (record["bytes"], record["sha256"]) != expected:
        raise P1SequenceSeed20260612PatchError(
            f"Protected Closure artifact drifted: {path.as_posix()}"
        )
    return record


def _component_set(
    records: Sequence[Mapping[str, Any]],
    *,
    current_bytes_required_to_match_historical: bool,
) -> dict[str, Any]:
    copied = [dict(record) for record in records]
    return {
        "count": len(copied),
        "paths": [str(record["path"]) for record in copied],
        "records": copied,
        "records_sha256": _record_digest(copied),
        "current_bytes_required_to_match_historical": (
            current_bytes_required_to_match_historical
        ),
    }


def patch_git_diff_payload(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-E0-MH")
    ancestry = _git("rev-list", "--parents", "-n", "1", patch_head).split()
    if ancestry != [patch_head, PATCH_BASE_COMMIT]:
        raise P1SequenceSeed20260612PatchError(
            "H-E0-MH must be the direct non-merge child of P1/1729"
        )
    expected = [
        {"status": "M" if path in PATCH_MODIFIED_PATHS else "A", "path": path}
        for path in PATCH_PATHS
    ]
    observed = _observed_diff_entries(PATCH_BASE_COMMIT, patch_head)
    if observed != expected:
        raise P1SequenceSeed20260612PatchError(
            f"H-E0-MH diff differs from its closed 2M+5A allowlist: {observed}"
        )
    return {
        "base_commit": PATCH_BASE_COMMIT,
        "patch_head": patch_head,
        "modified_count": 2,
        "added_count": 5,
        "entries": expected,
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "only_allowed_additions_and_modifications": True,
    }


def patch_component_bundle(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-E0-MH")
    records = [
        _git_record(patch_head, path, role=PATCH_COMPONENT_ROLES[path])
        for path in PATCH_PATHS
    ]
    return {
        "count": len(records),
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "records": records,
        "records_sha256": _record_digest(records),
    }


def _historical_e0_mc_authority(*, execution_head: str) -> dict[str, Any]:
    payload = _load_regular_json(
        e0_mc.DEFAULT_PATCH_LOCK_PATH,
        context="P-E0-MC lock",
    )
    schema = _load_regular_json(
        e0_mc.DEFAULT_PATCH_LOCK_SCHEMA,
        context="H-E0-MC schema",
    )
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.historical_p1_sequence_patch_lock",
        )
    except ClosureContractError as exc:
        raise _translate(exc) from exc
    fixed = {
        "lock_version": e0_mc.LOCK_VERSION,
        "status": e0_mc.PATCH_STATUS,
        "experiment_id": e0_mc.EXPERIMENT_ID,
        "surface_id": e0_mc.SURFACE_ID,
        "gate": e0_mc.PATCH_GATE,
        "patch_id": e0_mc.PATCH_ID,
        "authorizations": e0_mc.PATCH_AUTHORIZATIONS,
        "seals": e0_mc.PATCH_SEALS,
    }
    if any(payload.get(field) != expected for field, expected in fixed.items()):
        raise P1SequenceSeed20260612PatchError(
            "Historical E0-MC fixed contract drifted"
        )
    repository = cast(Mapping[str, Any], payload["patch_repository"])
    if repository.get("head") != E0_MC_H_COMMIT:
        raise P1SequenceSeed20260612PatchError("Historical E0-MC H commit drifted")
    if payload.get("git_diff") != e0_mc.patch_git_diff_payload(E0_MC_H_COMMIT):
        raise P1SequenceSeed20260612PatchError("Historical E0-MC diff drifted")
    expected_components = e0_mc.patch_component_bundle(E0_MC_H_COMMIT)
    if payload.get("patch_components") != expected_components:
        raise P1SequenceSeed20260612PatchError(
            "Historical E0-MC component bundle drifted"
        )
    ancestry = _git("rev-list", "--parents", "-n", "1", E0_MC_P_COMMIT).split()
    if ancestry != [E0_MC_P_COMMIT, E0_MC_H_COMMIT]:
        raise P1SequenceSeed20260612PatchError("P-E0-MC topology drifted")
    expected_publication = [
        {"status": "A", "path": e0_mc.DEFAULT_PATCH_LOCK_PATH.as_posix()},
        {"status": "A", "path": e0_mc.DEFAULT_PATCH_MANIFEST_PATH.as_posix()},
    ]
    if _observed_diff_entries(E0_MC_H_COMMIT, E0_MC_P_COMMIT) != expected_publication:
        raise P1SequenceSeed20260612PatchError("P-E0-MC scope drifted")
    _require_ancestor(E0_MC_P_COMMIT, execution_head)
    _assert_paths_untouched(
        E0_MC_P_COMMIT,
        execution_head,
        (
            e0_mc.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            e0_mc.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        ),
        context="P-E0-MC publication",
    )
    components = cast(Mapping[str, Any], payload["patch_components"])
    records = [
        dict(record)
        for record in cast(Sequence[Mapping[str, Any]], components["records"])
    ]
    by_path = {str(record["path"]): record for record in records}
    if set(by_path) != set(e0_mc.PATCH_PATHS) or len(by_path) != len(records):
        raise P1SequenceSeed20260612PatchError(
            "Historical E0-MC component paths drifted"
        )
    superseded = [by_path[path] for path in E0_MC_SUPERSEDED_PATHS]
    preserved = [by_path[path] for path in E0_MC_PRESERVED_PATHS]
    for record in records:
        if record != _git_record(
            E0_MC_H_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        ):
            raise P1SequenceSeed20260612PatchError(
                f"Historical E0-MC Git record drifted: {record['path']}"
            )
    for record in preserved:
        if _file_record(
            Path(str(record["path"])), role=str(record["role"])
        ) != record:
            raise P1SequenceSeed20260612PatchError(
                f"Preserved E0-MC component drifted: {record['path']}"
            )
    _assert_paths_untouched(
        E0_MC_H_COMMIT,
        execution_head,
        E0_MC_PRESERVED_PATHS,
        context="preserved H-E0-MC components",
    )
    lock_record = _file_record(
        e0_mc.DEFAULT_PATCH_LOCK_PATH,
        role="external_p1_sequence_historical_anfis_patch_lock",
    )
    companion_record = _file_record(
        e0_mc.DEFAULT_PATCH_MANIFEST_PATH,
        role="p1_sequence_historical_anfis_patch_companion",
    )
    if lock_record != _git_record(
        E0_MC_P_COMMIT,
        e0_mc.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        role="external_p1_sequence_historical_anfis_patch_lock",
    ) or companion_record != _git_record(
        E0_MC_P_COMMIT,
        e0_mc.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        role="p1_sequence_historical_anfis_patch_companion",
    ):
        raise P1SequenceSeed20260612PatchError(
            "Published E0-MC lock bundle drifted"
        )
    companion = _load_regular_json(
        e0_mc.DEFAULT_PATCH_MANIFEST_PATH,
        context="P-E0-MC companion",
    )
    try:
        expected_companion = e0_mc._expected_companion(
            payload,
            lock_record=lock_record,
        )
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc
    if companion != expected_companion:
        raise P1SequenceSeed20260612PatchError(
            "Published E0-MC companion drifted"
        )
    return {
        "gate": "E0-MC",
        "patch_head": E0_MC_H_COMMIT,
        "lock_commit": E0_MC_P_COMMIT,
        "lock": lock_record,
        "companion_manifest": companion_record,
        "superseded_components": _component_set(
            superseded,
            current_bytes_required_to_match_historical=False,
        ),
        "preserved_components": _component_set(
            preserved,
            current_bytes_required_to_match_historical=True,
        ),
        "publication_topology_verified": True,
        "historical_authority_verified": True,
        "effective_loader_called": False,
        "future_outcomes_accessed": False,
    }


def _historical_e0_mg_authority(*, execution_head: str) -> dict[str, Any]:
    payload = _load_regular_json(e0_mg.DEFAULT_PATCH_LOCK_PATH, context="P-E0-MG lock")
    schema = _load_regular_json(e0_mg.DEFAULT_PATCH_LOCK_SCHEMA, context="H-E0-MG schema")
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.historical_p1_consumer_patch_lock",
        )
    except ClosureContractError as exc:
        raise _translate(exc) from exc
    fixed = {
        "lock_version": e0_mg.LOCK_VERSION,
        "status": e0_mg.PATCH_STATUS,
        "experiment_id": e0_mg.EXPERIMENT_ID,
        "surface_id": e0_mg.SURFACE_ID,
        "gate": e0_mg.PATCH_GATE,
        "patch_id": e0_mg.PATCH_ID,
        "authorizations": e0_mg.PATCH_AUTHORIZATIONS,
        "seals": e0_mg.PATCH_SEALS,
    }
    if any(payload.get(field) != expected for field, expected in fixed.items()):
        raise P1SequenceSeed20260612PatchError(
            "Historical E0-MG fixed contract drifted"
        )
    if cast(Mapping[str, Any], payload["patch_repository"]).get("head") != E0_MG_H_COMMIT:
        raise P1SequenceSeed20260612PatchError("Historical E0-MG H commit drifted")
    if payload.get("git_diff") != e0_mg.patch_git_diff_payload(E0_MG_H_COMMIT):
        raise P1SequenceSeed20260612PatchError("Historical E0-MG diff drifted")
    components = e0_mg.patch_component_bundle(E0_MG_H_COMMIT)
    if payload.get("patch_components") != components:
        raise P1SequenceSeed20260612PatchError(
            "Historical E0-MG component bundle drifted"
        )
    ancestry = _git("rev-list", "--parents", "-n", "1", E0_MG_P_COMMIT).split()
    if ancestry != [E0_MG_P_COMMIT, E0_MG_H_COMMIT]:
        raise P1SequenceSeed20260612PatchError("P-E0-MG topology drifted")
    expected_publication = [
        {"status": "A", "path": e0_mg.DEFAULT_PATCH_LOCK_PATH.as_posix()},
        {"status": "A", "path": e0_mg.DEFAULT_PATCH_MANIFEST_PATH.as_posix()},
    ]
    if _observed_diff_entries(E0_MG_H_COMMIT, E0_MG_P_COMMIT) != expected_publication:
        raise P1SequenceSeed20260612PatchError("P-E0-MG scope drifted")
    _require_ancestor(E0_MG_P_COMMIT, execution_head)
    _assert_paths_untouched(
        E0_MG_P_COMMIT,
        execution_head,
        (
            e0_mg.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            e0_mg.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        ),
        context="P-E0-MG publication",
    )
    lock_record = _file_record(
        e0_mg.DEFAULT_PATCH_LOCK_PATH,
        role="external_p1_temporal_consumer_schema_subset_patch_lock",
    )
    companion_record = _file_record(
        e0_mg.DEFAULT_PATCH_MANIFEST_PATH,
        role="p1_temporal_consumer_schema_subset_patch_companion",
    )
    if lock_record != _git_record(
        E0_MG_P_COMMIT,
        e0_mg.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        role="external_p1_temporal_consumer_schema_subset_patch_lock",
    ) or companion_record != _git_record(
        E0_MG_P_COMMIT,
        e0_mg.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        role="p1_temporal_consumer_schema_subset_patch_companion",
    ):
        raise P1SequenceSeed20260612PatchError(
            "Published E0-MG lock bundle drifted"
        )
    companion = _load_regular_json(
        e0_mg.DEFAULT_PATCH_MANIFEST_PATH,
        context="P-E0-MG companion",
    )
    try:
        expected_companion = e0_mg._expected_companion(
            payload,
            lock_record=lock_record,
        )
    except e0_mg.P1TemporalConsumerSchemaSubsetPatchError as exc:
        raise _translate(exc) from exc
    if companion != expected_companion:
        raise P1SequenceSeed20260612PatchError("Historical E0-MG companion drifted")
    records = [
        dict(record)
        for record in cast(Sequence[Mapping[str, Any]], components["records"])
    ]
    for record in records:
        if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
            raise P1SequenceSeed20260612PatchError(
                f"Preserved E0-MG component drifted: {record['path']}"
            )
    _assert_paths_untouched(
        E0_MG_H_COMMIT,
        execution_head,
        e0_mg.PATCH_PATHS,
        context="preserved H-E0-MG components",
    )
    return {
        "gate": "E0-MG",
        "patch_head": E0_MG_H_COMMIT,
        "lock_commit": E0_MG_P_COMMIT,
        "lock": lock_record,
        "companion_manifest": companion_record,
        "preserved_components": _component_set(
            records,
            current_bytes_required_to_match_historical=True,
        ),
        "publication_topology_verified": True,
        "historical_authority_verified": True,
        "effective_loader_called": False,
        "future_outcomes_accessed": False,
    }


def _published_p1_1729_bundle(*, execution_head: str) -> dict[str, Any]:
    sequence_ancestry = _git(
        "rev-list", "--parents", "-n", "1", P1_1729_SEQUENCE_COMMIT
    ).split()
    if sequence_ancestry != [P1_1729_SEQUENCE_COMMIT, E0_MC_P_COMMIT]:
        raise P1SequenceSeed20260612PatchError(
            "P1/1729 sequence publication topology drifted"
        )
    expected_sequence_diff = [
        {"status": "A", "path": path}
        for path in P1_1729_SEQUENCE_COMMIT_PATHS
    ]
    if _observed_diff_entries(E0_MC_P_COMMIT, P1_1729_SEQUENCE_COMMIT) != (
        expected_sequence_diff
    ):
        raise P1SequenceSeed20260612PatchError(
            "P1/1729 sequence publication scope drifted"
        )
    for path in P1_1729_SEQUENCE_COMMIT_PATHS:
        entry = _git("ls-tree", P1_1729_SEQUENCE_COMMIT, "--", path).split(
            maxsplit=3
        )
        if len(entry) != 4 or entry[0] != "100644" or entry[1] != "blob" or entry[3] != path:
            raise P1SequenceSeed20260612PatchError(
                f"P1/1729 sequence publication mode drifted: {path}"
            )
    _require_ancestor(P1_1729_SEQUENCE_COMMIT, execution_head)
    _assert_paths_untouched(
        P1_1729_SEQUENCE_COMMIT,
        execution_head,
        P1_1729_SEQUENCE_COMMIT_PATHS,
        context="published P1/1729 sequence bundle",
    )
    ancestry = _git(
        "rev-list", "--parents", "-n", "1", P1_1729_CONSUMER_COMMIT
    ).split()
    if ancestry != [P1_1729_CONSUMER_COMMIT, E0_MG_P_COMMIT]:
        raise P1SequenceSeed20260612PatchError(
            "P1/1729 consumer publication topology drifted"
        )
    expected_diff = [
        {"status": "A", "path": P1_1729_MODEL_MANIFEST_PATH.as_posix()},
        {"status": "A", "path": P1_1729_REPORT_PATH.as_posix()},
    ]
    if _observed_diff_entries(E0_MG_P_COMMIT, P1_1729_CONSUMER_COMMIT) != expected_diff:
        raise P1SequenceSeed20260612PatchError(
            "P1/1729 consumer publication scope drifted"
        )
    for record in expected_diff:
        path = record["path"]
        entry = _git("ls-tree", P1_1729_CONSUMER_COMMIT, "--", path).split(
            maxsplit=3
        )
        if len(entry) != 4 or entry[0] != "100644" or entry[1] != "blob" or entry[3] != path:
            raise P1SequenceSeed20260612PatchError(
                f"P1/1729 consumer publication mode drifted: {path}"
            )
    _require_ancestor(P1_1729_CONSUMER_COMMIT, execution_head)
    tracked_paths = tuple(path.as_posix() for path in P1_1729_PRESENT_PATHS[1:])
    _assert_paths_untouched(
        P1_1729_CONSUMER_COMMIT,
        execution_head,
        tracked_paths,
        context="published P1/1729 bundle",
    )
    records = [
        _expected_artifact_record(path, role=f"p1_1729_{index}")
        for index, path in enumerate(P1_1729_PRESENT_PATHS, start=1)
    ]
    sequence_records = records[1:4]
    consumer_records = records[4:]
    for record in sequence_records:
        if _git_record(
            P1_1729_SEQUENCE_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        ) != record:
            raise P1SequenceSeed20260612PatchError(
                f"Published P1/1729 Git record drifted: {record['path']}"
            )
    for record in consumer_records:
        if _git_record(
            P1_1729_CONSUMER_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        ) != record:
            raise P1SequenceSeed20260612PatchError(
                f"Published P1/1729 consumer record drifted: {record['path']}"
            )
    manifest = _load_regular_json(
        P1_1729_MODEL_MANIFEST_PATH,
        context="P1/1729 model manifest",
    )
    expected_fields = {
        "status": "completed",
        "slot_status": "model_unavailable",
        "fit_status": "not_attempted",
        "failure_reason": "sequence_fit_rows_unavailable",
        "model_id": "P1",
        "base_seed": 1729,
        "device": "cpu",
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "model_artifact_emitted": False,
        "fit_status_counts": {
            "success": 8_925,
            "autoregressive_target_unavailable": 488,
        },
        "failure_reason_counts": {"missing_target_state": 488},
        "completion_marker_written_last": True,
    }
    drifted = [
        field for field, expected in expected_fields.items() if manifest.get(field) != expected
    ]
    if drifted or next(reversed(manifest)) != "completion_marker_written_last":
        raise P1SequenceSeed20260612PatchError(
            f"P1/1729 model-unavailable manifest drifted: {drifted}"
        )
    report_record = EXPECTED_ARTIFACTS[P1_1729_REPORT_PATH.as_posix()]
    if manifest.get("outputs") != [
        {
            "path": P1_1729_REPORT_PATH.as_posix(),
            "bytes": report_record[0],
            "sha256": report_record[1],
            "artifact_role": "report",
        }
    ]:
        raise P1SequenceSeed20260612PatchError(
            "P1/1729 manifest does not bind only its report"
        )
    observed = {
        path.as_posix()
        for path in availability._p1_absence_paths(1729)
        if _path_entry_exists(path)
    }
    expected_present = {path.as_posix() for path in P1_1729_PRESENT_PATHS}
    if observed != expected_present:
        raise P1SequenceSeed20260612PatchError(
            f"P1/1729 namespace differs from its closed publication: {sorted(observed)}"
        )
    return {
        "sequence_commit": P1_1729_SEQUENCE_COMMIT,
        "consumer_commit": P1_1729_CONSUMER_COMMIT,
        "records": records,
        "records_sha256": _record_digest(records),
        "present_paths": sorted(expected_present),
        "model_unavailable_semantics_verified": True,
        "sequence_commit_scope_verified": True,
        "consumer_commit_scope_verified": True,
        "completion_marker_written_last": True,
        "future_outcomes_accessed": False,
    }


def _anfis_20260612_state_bundle(*, execution_head: str) -> dict[str, Any]:
    ancestry = _git("rev-list", "--parents", "-n", "1", ANFIS_20260612_COMMIT).split()
    if ancestry != [ANFIS_20260612_COMMIT, e0_mc.E0_DLP_P_COMMIT]:
        raise P1SequenceSeed20260612PatchError(
            "ANFIS 20260612 publication topology drifted"
        )
    _require_ancestor(ANFIS_20260612_COMMIT, execution_head)
    tracked = (
        ANFIS_20260612_POINTER_PATH.as_posix(),
        ANFIS_20260612_MANIFEST_PATH.as_posix(),
    )
    _assert_paths_untouched(
        ANFIS_20260612_COMMIT,
        execution_head,
        tracked,
        context="ANFIS 20260612 publication",
    )
    records = [
        _expected_artifact_record(
            ANFIS_20260612_STATE_PATH,
            role="anfis_20260612_state_parquet",
        ),
        _expected_artifact_record(
            ANFIS_20260612_POINTER_PATH,
            role="anfis_20260612_state_pointer",
        ),
        _expected_artifact_record(
            ANFIS_20260612_MANIFEST_PATH,
            role="anfis_20260612_state_manifest",
        ),
    ]
    for record in records[1:]:
        if _git_record(
            ANFIS_20260612_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        ) != record:
            raise P1SequenceSeed20260612PatchError(
                f"ANFIS 20260612 Git record drifted: {record['path']}"
            )
    manifest = _load_regular_json(
        ANFIS_20260612_MANIFEST_PATH,
        context="ANFIS 20260612 manifest",
    )
    expected_fields = {
        "manifest_version": "closure_anfis_seed_manifest_v1",
        "status": "completed",
        "slot_status": "available",
        "fit_status": "passed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "F1",
        "consumer_model_id": "P1",
        "base_seed": AUTHORIZED_BASE_SEED,
        "state_artifact_emitted": True,
        "state_output_materialized": True,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "completion_marker_written_last": True,
    }
    drifted = [
        field for field, expected in expected_fields.items() if manifest.get(field) != expected
    ]
    if drifted:
        raise P1SequenceSeed20260612PatchError(
            f"ANFIS 20260612 manifest drifted: {drifted}"
        )
    state_expected = EXPECTED_ARTIFACTS[ANFIS_20260612_STATE_PATH.as_posix()]
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes)):
        raise P1SequenceSeed20260612PatchError("ANFIS 20260612 outputs drifted")
    state_matches = [
        record
        for record in outputs
        if isinstance(record, Mapping)
        and record.get("path") == ANFIS_20260612_STATE_PATH.as_posix()
        and record.get("bytes") == state_expected[0]
        and record.get("sha256") == state_expected[1]
    ]
    if len(state_matches) != 1:
        raise P1SequenceSeed20260612PatchError(
            "ANFIS 20260612 manifest does not bind its state exactly once"
        )
    return {
        "publication_commit": ANFIS_20260612_COMMIT,
        "records": records,
        "records_sha256": _record_digest(records),
        "slot_status": "available",
        "fit_status": "passed",
        "state_manifest_verified": True,
        "future_outcomes_accessed": False,
    }


def p1_seed_20260612_namespace_paths() -> tuple[Path, ...]:
    paths = availability._p1_absence_paths(AUTHORIZED_BASE_SEED)
    if len(paths) != 28 or len({path.as_posix() for path in paths}) != 28:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH target namespace cardinality drifted"
        )
    return paths


def _sequence_prelock_contract() -> dict[str, Any]:
    paths = [path.as_posix() for path in p1_seed_20260612_namespace_paths()]
    return {
        "model_id": AUTHORIZED_MODEL_ID,
        "base_seed": AUTHORIZED_BASE_SEED,
        "count": 28,
        "paths": paths,
        "paths_sha256": _path_digest(paths),
        "all_absent_at_lock": True,
    }


def p1_seed_20260612_namespace_absence() -> dict[str, Any]:
    contract = _sequence_prelock_contract()
    existing = [
        path.as_posix()
        for path in p1_seed_20260612_namespace_paths()
        if _path_entry_exists(path)
    ]
    if existing:
        raise P1SequenceSeed20260612PatchError(
            f"P1 seed 20260612 namespace is not pristine: {existing}"
        )
    return contract


def _progression_prelock_contract() -> dict[str, Any]:
    all_paths = tuple(
        path
        for seed in availability.EXPECTED_SEEDS
        for path in availability._p1_absence_paths(seed)
    )
    present = sorted(path.as_posix() for path in P1_1729_PRESENT_PATHS)
    absent = [path.as_posix() for path in all_paths if path.as_posix() not in set(present)]
    return {
        "p1_seed_order": list(availability.EXPECTED_SEEDS),
        "p1_path_count": len(all_paths),
        "p1_paths_sha256": _path_digest([path.as_posix() for path in all_paths]),
        "completed_seed": 1729,
        "completed_seed_present_count": len(present),
        "completed_seed_present_paths": present,
        "remaining_absent_count": len(absent),
        "remaining_absent_paths_sha256": _path_digest(absent),
        "next_authorized_seed": AUTHORIZED_BASE_SEED,
        "e0_m_output_count": 0,
        "outcome_access_log_state": "absent",
        "future_outcomes_accessed": False,
    }


def closure_progression_prelock() -> dict[str, Any]:
    contract = _progression_prelock_contract()
    all_paths = tuple(
        path
        for seed in availability.EXPECTED_SEEDS
        for path in availability._p1_absence_paths(seed)
    )
    observed = {path.as_posix() for path in all_paths if _path_entry_exists(path)}
    expected = {path.as_posix() for path in P1_1729_PRESENT_PATHS}
    existing_e0_m = [
        path.as_posix() for path in availability.E0_M_OUTPUTS if _path_entry_exists(path)
    ]
    outcome = _path_entry_exists(availability.OUTCOME_ACCESS_LOG)
    if observed != expected or existing_e0_m or outcome:
        raise P1SequenceSeed20260612PatchError(
            "Closure progression is not pristine before P1 seed 20260612: "
            f"p1={sorted(observed)}, e0_m={existing_e0_m}, outcome={outcome}"
        )
    return contract


# Stable names consumed by the hardened locker.  Both checks are read-only and
# preserve the ordered progression (1729 closed, 20260612 still absent).
def p1_sequence_namespace_absence() -> dict[str, Any]:
    return p1_seed_20260612_namespace_absence()


def closure_progression_namespace_absence() -> dict[str, Any]:
    return closure_progression_prelock()


def collect_p1_sequence_seed_20260612_patch_prelock_state(
    *,
    verify_remote: bool,
) -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise P1SequenceSeed20260612PatchError(
            f"H-E0-MH lock requires a clean worktree: {status}"
        )
    head = _require_commit(_git("rev-parse", "HEAD"), context="H-E0-MH HEAD")
    if _git("branch", "--show-current") != "main":
        raise P1SequenceSeed20260612PatchError("H-E0-MH requires branch main")
    published = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    if published != head:
        raise P1SequenceSeed20260612PatchError("H-E0-MH HEAD differs from origin/main")
    remote = _remote_main_oid() if verify_remote else published
    if remote != head:
        raise P1SequenceSeed20260612PatchError(
            "H-E0-MH HEAD differs from live origin/main"
        )
    git_diff = patch_git_diff_payload(head)
    components = patch_component_bundle(head)
    for record in cast(Sequence[Mapping[str, Any]], components["records"]):
        if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
            raise P1SequenceSeed20260612PatchError(
                f"Physical H-E0-MH component drifted: {record['path']}"
            )
    builder = next(
        dict(record)
        for record in cast(Sequence[Mapping[str, Any]], components["records"])
        if record["path"] == "src/experiments/build_closure_pipe_sequences.py"
    )
    builder["role"] = "current_runtime_builder"
    return {
        "patch_repository": {
            "head": head,
            "parent": PATCH_BASE_COMMIT,
            "branch": "main",
            "published_ref": PUBLISHED_REF,
            "published_head": published,
            "remote_main_oid": remote,
            "worktree_status": "clean",
            "exact_diff_verified": True,
        },
        "git_diff": git_diff,
        "patch_components": components,
        "base_authorities": {
            "e0_mc": _historical_e0_mc_authority(execution_head=head),
            "e0_mg": _historical_e0_mg_authority(execution_head=head),
        },
        "p1_1729_publication": _published_p1_1729_bundle(execution_head=head),
        "anfis_20260612_state_bundle": _anfis_20260612_state_bundle(
            execution_head=head
        ),
        "current_runtime_builder_record": builder,
        "sequence_prelock": p1_seed_20260612_namespace_absence(),
        "progression_prelock": closure_progression_prelock(),
    }


def _validate_command_evidence(
    value: Any,
    command: Sequence[str],
    *,
    context: str,
) -> None:
    if not isinstance(value, Mapping):
        raise P1SequenceSeed20260612PatchError(
            f"E0-MH {context} evidence must be an object"
        )
    expected_keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    if context == "focused_tests":
        expected_keys.update({"test_count", "skipped_count", "deselected_count"})
    if set(value) != expected_keys or tuple(value.get("command", ())) != tuple(command):
        raise P1SequenceSeed20260612PatchError(
            f"E0-MH {context} command evidence drifted"
        )
    if value.get("returncode") != 0:
        raise P1SequenceSeed20260612PatchError(f"E0-MH {context} did not pass")
    for field in ("stdout_sha256", "stderr_sha256"):
        digest = value.get(field)
        if not isinstance(digest, str) or len(digest) != 64:
            raise P1SequenceSeed20260612PatchError(
                f"E0-MH {context} {field} drifted"
            )
    for field in ("stdout_line_count", "stderr_line_count"):
        if type(value.get(field)) is not int or value[field] < 0:
            raise P1SequenceSeed20260612PatchError(
                f"E0-MH {context} {field} drifted"
            )


def validate_p1_sequence_seed_20260612_patch_verification(
    payload: Mapping[str, Any],
) -> None:
    commands = {
        "full_type_check": TYPE_CHECK_COMMAND,
        "focused_tests": FOCUSED_TEST_COMMAND,
        "poetry_check": POETRY_CHECK_COMMAND,
        "publication_guard": PUBLICATION_GUARD_COMMAND,
        "git_diff_check": DIFF_CHECK_COMMAND,
    }
    if set(payload) != {*commands, "schema_subset_preflight"}:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH verification fields drifted"
        )
    schema_preflight = payload.get("schema_subset_preflight")
    if (
        not isinstance(schema_preflight, Mapping)
        or dict(schema_preflight)
        != preflight_p1_sequence_seed_20260612_patch_schema()
    ):
        raise P1SequenceSeed20260612PatchError(
            "E0-MH schema preflight evidence drifted"
        )
    for field, command in commands.items():
        _validate_command_evidence(payload[field], command, context=field)
    focused = cast(Mapping[str, Any], payload["focused_tests"])
    if (
        FOCUSED_TEST_COUNT <= 0
        or focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise P1SequenceSeed20260612PatchError(
            "E0-MH focused-test evidence drifted"
        )


def build_p1_sequence_seed_20260612_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    return {
        "lock_version": LOCK_VERSION,
        "status": PATCH_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": created_at_utc,
        "patch_repository": dict(cast(Mapping[str, Any], prelock["patch_repository"])),
        "git_diff": dict(cast(Mapping[str, Any], prelock["git_diff"])),
        "patch_components": dict(cast(Mapping[str, Any], prelock["patch_components"])),
        "base_authorities": dict(cast(Mapping[str, Any], prelock["base_authorities"])),
        "p1_1729_publication": dict(
            cast(Mapping[str, Any], prelock["p1_1729_publication"])
        ),
        "anfis_20260612_state_bundle": dict(
            cast(Mapping[str, Any], prelock["anfis_20260612_state_bundle"])
        ),
        "current_runtime_builder_record": dict(
            cast(Mapping[str, Any], prelock["current_runtime_builder_record"])
        ),
        "sequence_prelock": dict(cast(Mapping[str, Any], prelock["sequence_prelock"])),
        "progression_prelock": dict(
            cast(Mapping[str, Any], prelock["progression_prelock"])
        ),
        "sequence_atomicity": dict(e0_mb.PATCH_ATOMICITY),
        "correction": dict(PATCH_CORRECTION),
        "verification": dict(verification),
        "authorizations": dict(PATCH_AUTHORIZATIONS),
        "seals": dict(PATCH_SEALS),
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_p1_sequence_seed_20260612_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }


def validate_p1_sequence_seed_20260612_patch_lock_payload(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    require_physical_patch_components: bool = True,
) -> None:
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.p1_sequence_seed_20260612_patch_lock",
        )
    except ClosureContractError as exc:
        raise _translate(exc) from exc
    fixed = {
        "lock_version": LOCK_VERSION,
        "status": PATCH_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "sequence_atomicity": e0_mb.PATCH_ATOMICITY,
        "correction": PATCH_CORRECTION,
        "authorizations": PATCH_AUTHORIZATIONS,
        "seals": PATCH_SEALS,
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_p1_sequence_seed_20260612_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise P1SequenceSeed20260612PatchError(
                f"E0-MH fixed field drifted: {field}"
            )
    created = payload.get("created_at_utc")
    if not isinstance(created, str):
        raise P1SequenceSeed20260612PatchError("E0-MH timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P1SequenceSeed20260612PatchError("E0-MH timestamp is invalid") from exc
    if timestamp.utcoffset() is None:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH timestamp requires a timezone"
        )
    repository = cast(Mapping[str, Any], payload["patch_repository"])
    patch_head = _require_commit(str(repository.get("head", "")), context="H-E0-MH")
    if repository != {
        "head": patch_head,
        "parent": PATCH_BASE_COMMIT,
        "branch": "main",
        "published_ref": PUBLISHED_REF,
        "published_head": patch_head,
        "remote_main_oid": patch_head,
        "worktree_status": "clean",
        "exact_diff_verified": True,
    }:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH patch repository record drifted"
        )
    if payload.get("git_diff") != patch_git_diff_payload(patch_head):
        raise P1SequenceSeed20260612PatchError("E0-MH Git diff drifted")
    components = patch_component_bundle(patch_head)
    if payload.get("patch_components") != components:
        raise P1SequenceSeed20260612PatchError("E0-MH component bundle drifted")
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    if require_physical_patch_components:
        for record in cast(Sequence[Mapping[str, Any]], components["records"]):
            if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
                raise P1SequenceSeed20260612PatchError(
                    f"Physical H-E0-MH component drifted: {record['path']}"
                )
        _assert_paths_untouched(
            patch_head,
            execution_head,
            PATCH_PATHS,
            context="H-E0-MH components",
        )
    expected_authorities = {
        "e0_mc": _historical_e0_mc_authority(execution_head=execution_head),
        "e0_mg": _historical_e0_mg_authority(execution_head=execution_head),
    }
    if payload.get("base_authorities") != expected_authorities:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH historical authorities drifted"
        )
    if payload.get("p1_1729_publication") != _published_p1_1729_bundle(
        execution_head=execution_head
    ):
        raise P1SequenceSeed20260612PatchError("P1/1729 publication drifted")
    if payload.get("anfis_20260612_state_bundle") != _anfis_20260612_state_bundle(
        execution_head=execution_head
    ):
        raise P1SequenceSeed20260612PatchError("ANFIS 20260612 bundle drifted")
    builder_records = [
        record
        for record in cast(Sequence[Mapping[str, Any]], components["records"])
        if record["path"] == "src/experiments/build_closure_pipe_sequences.py"
    ]
    if len(builder_records) != 1:
        raise P1SequenceSeed20260612PatchError("E0-MH builder record is not unique")
    expected_builder = dict(builder_records[0])
    expected_builder["role"] = "current_runtime_builder"
    if payload.get("current_runtime_builder_record") != expected_builder:
        raise P1SequenceSeed20260612PatchError("E0-MH current builder drifted")
    if payload.get("sequence_prelock") != _sequence_prelock_contract():
        raise P1SequenceSeed20260612PatchError("E0-MH sequence prelock drifted")
    if payload.get("progression_prelock") != _progression_prelock_contract():
        raise P1SequenceSeed20260612PatchError("E0-MH progression prelock drifted")
    validate_p1_sequence_seed_20260612_patch_verification(
        cast(Mapping[str, Any], payload["verification"])
    )


def _generic_record(record: Mapping[str, Any], *, role: str) -> dict[str, Any]:
    return {
        "path": record["path"],
        "role": role,
        "bytes": record["bytes"],
        "sha256": record["sha256"],
    }


def _expected_companion(
    payload: Mapping[str, Any],
    *,
    lock_record: Mapping[str, Any],
) -> dict[str, Any]:
    components = cast(Mapping[str, Any], payload["patch_components"])
    records = cast(Sequence[Mapping[str, Any]], components["records"])
    by_path = {str(record["path"]): record for record in records}
    authorities = cast(Mapping[str, Any], payload["base_authorities"])
    mc = cast(Mapping[str, Any], authorities["e0_mc"])
    mg = cast(Mapping[str, Any], authorities["e0_mg"])
    publication = cast(Mapping[str, Any], payload["p1_1729_publication"])
    state = cast(Mapping[str, Any], payload["anfis_20260612_state_bundle"])
    inputs = [
        _generic_record(
            by_path[DEFAULT_PATCH_LOCK_SCHEMA.as_posix()],
            role="p1_sequence_seed_20260612_patch_lock_schema",
        ),
        _generic_record(
            by_path["src/experiments/closure_p1_sequence_seed_20260612_patch.py"],
            role="p1_sequence_seed_20260612_patch_validator",
        ),
        _generic_record(
            by_path["src/experiments/build_closure_pipe_sequences.py"],
            role="current_runtime_builder",
        ),
        dict(cast(Mapping[str, Any], mc["lock"])),
        dict(cast(Mapping[str, Any], mc["companion_manifest"])),
        dict(cast(Mapping[str, Any], mg["lock"])),
        dict(cast(Mapping[str, Any], mg["companion_manifest"])),
        *[
            dict(record)
            for record in cast(Sequence[Mapping[str, Any]], publication["records"])
        ],
        *[
            dict(record)
            for record in cast(Sequence[Mapping[str, Any]], state["records"])
        ],
    ]
    inputs = sorted(inputs, key=lambda record: (str(record["path"]), str(record["role"])))
    historical_inputs = [
        {
            **dict(record),
            "commit": E0_MC_H_COMMIT,
            "hash_source": "git_blob_at_commit",
        }
        for record in cast(
            Sequence[Mapping[str, Any]],
            cast(Mapping[str, Any], mc["superseded_components"])["records"],
        )
    ]
    return {
        "manifest_version": "closure_p1_sequence_seed_20260612_patch_manifest_v1",
        "status": "completed",
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": payload["created_at_utc"],
        "outputs": [dict(lock_record)],
        "script": _generic_record(
            by_path["src/experiments/lock_closure_p1_sequence_seed_20260612_patch.py"],
            role="generating_script",
        ),
        "inputs": inputs,
        "historical_inputs": historical_inputs,
        "physical_inputs_only": True,
        "historical_inputs_compared_to_current_paths": False,
        **PATCH_AUTHORIZATIONS,
        "authoritative_contract": False,
        "authoritative_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "completion_marker_written_last": True,
    }


def _validate_p_commit_topology(
    payload: Mapping[str, Any],
    *,
    execution_head: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    lock_path = DEFAULT_PATCH_LOCK_PATH.as_posix()
    companion_path = DEFAULT_PATCH_MANIFEST_PATH.as_posix()
    lock_commit = _introduced_commit(lock_path)
    if lock_commit != _introduced_commit(companion_path):
        raise P1SequenceSeed20260612PatchError("E0-MH lock commits differ")
    ancestry = _git("rev-list", "--parents", "-n", "1", lock_commit).split()
    if ancestry != [lock_commit, patch_head]:
        raise P1SequenceSeed20260612PatchError(
            "P-E0-MH must be the direct child of H-E0-MH"
        )
    expected = [
        {"status": "A", "path": lock_path},
        {"status": "A", "path": companion_path},
    ]
    if _observed_diff_entries(patch_head, lock_commit) != expected:
        raise P1SequenceSeed20260612PatchError(
            "P-E0-MH must add exactly lock plus companion"
        )
    for path in (lock_path, companion_path):
        entry = _git("ls-tree", lock_commit, "--", path).split(maxsplit=3)
        if (
            len(entry) != 4
            or entry[0] != "100644"
            or entry[1] != "blob"
            or entry[3] != path
        ):
            raise P1SequenceSeed20260612PatchError(
                f"P-E0-MH publication mode drifted: {path}"
            )
    _require_ancestor(lock_commit, execution_head)
    _assert_paths_untouched(
        lock_commit,
        execution_head,
        (lock_path, companion_path),
        context="P-E0-MH publication",
    )
    return (
        lock_commit,
        _file_record(
            DEFAULT_PATCH_LOCK_PATH,
            role="external_p1_sequence_seed_20260612_patch_lock",
        ),
        _file_record(
            DEFAULT_PATCH_MANIFEST_PATH,
            role="p1_sequence_seed_20260612_patch_companion",
        ),
    )


def _load_unpublished_p1_sequence_seed_20260612_patch_lock(
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _load_regular_json(DEFAULT_PATCH_LOCK_PATH, context="E0-MH lock")
    schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MH schema")
    validate_p1_sequence_seed_20260612_patch_lock_payload(payload, schema)
    lock_record = _canonical_json_record(
        payload,
        DEFAULT_PATCH_LOCK_PATH,
        role="external_p1_sequence_seed_20260612_patch_lock",
        context="E0-MH lock",
    )
    companion = _load_regular_json(
        DEFAULT_PATCH_MANIFEST_PATH,
        context="E0-MH companion",
    )
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1SequenceSeed20260612PatchError("E0-MH companion drifted")
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    if execution_head != patch_head:
        raise P1SequenceSeed20260612PatchError(
            "Unpublished E0-MH validation must run at H-E0-MH"
        )
    return payload, {
        "status": "locked_unpublished",
        "gate": PATCH_GATE,
        "patch_head": patch_head,
        "lock_commit": None,
        "authorization_effective": False,
        **PATCH_AUTHORIZATIONS,
    }


def load_published_p1_sequence_seed_20260612_patch_historical_authority(
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _load_regular_json(DEFAULT_PATCH_LOCK_PATH, context="E0-MH lock")
    schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MH schema")
    validate_p1_sequence_seed_20260612_patch_lock_payload(
        payload,
        schema,
        require_physical_patch_components=False,
    )
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    lock_commit, lock_record, companion_record = _validate_p_commit_topology(
        payload,
        execution_head=execution_head,
    )
    if lock_record != _canonical_json_record(
        payload,
        DEFAULT_PATCH_LOCK_PATH,
        role="external_p1_sequence_seed_20260612_patch_lock",
        context="E0-MH lock",
    ):
        raise P1SequenceSeed20260612PatchError("Published E0-MH lock drifted")
    companion = _load_regular_json(
        DEFAULT_PATCH_MANIFEST_PATH,
        context="E0-MH companion",
    )
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1SequenceSeed20260612PatchError("Published E0-MH companion drifted")
    if companion_record != _canonical_json_record(
        companion,
        DEFAULT_PATCH_MANIFEST_PATH,
        role="p1_sequence_seed_20260612_patch_companion",
        context="E0-MH companion",
    ):
        raise P1SequenceSeed20260612PatchError(
            "Published E0-MH companion record drifted"
        )
    return payload, {
        "status": "published_p1_sequence_seed_20260612_historical_authority_valid",
        "gate": PATCH_GATE,
        "patch_head": payload["patch_repository"]["head"],
        "lock_commit": lock_commit,
        "execution_head": execution_head,
        "authorization_effective": False,
        **PATCH_AUTHORIZATIONS,
    }


def load_and_validate_p1_sequence_seed_20260612_patch_lock(
) -> tuple[dict[str, Any], dict[str, Any]]:
    sequence_before = p1_seed_20260612_namespace_absence()
    progression_before = closure_progression_prelock()
    payload = _load_regular_json(DEFAULT_PATCH_LOCK_PATH, context="E0-MH lock")
    schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MH schema")
    validate_p1_sequence_seed_20260612_patch_lock_payload(payload, schema)
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise P1SequenceSeed20260612PatchError(
            f"E0-MH execution requires a clean worktree: {status}"
        )
    lock_commit, lock_record, companion_record = _validate_p_commit_topology(
        payload,
        execution_head=execution_head,
    )
    if execution_head != lock_commit:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH execution requires HEAD at the exact P commit"
        )
    if _git("branch", "--show-current") != "main":
        raise P1SequenceSeed20260612PatchError("E0-MH requires branch main")
    refs = {
        ref: _require_commit(_git("rev-parse", ref), context=ref)
        for ref in ("HEAD", "main", "origin/main", "origin/HEAD")
    }
    if set(refs.values()) != {lock_commit}:
        raise P1SequenceSeed20260612PatchError(
            f"E0-MH publication refs diverged: {refs}"
        )
    if _remote_main_oid() != lock_commit:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH differs from live origin/main"
        )
    if lock_record != _canonical_json_record(
        payload,
        DEFAULT_PATCH_LOCK_PATH,
        role="external_p1_sequence_seed_20260612_patch_lock",
        context="E0-MH lock",
    ):
        raise P1SequenceSeed20260612PatchError("Published E0-MH lock drifted")
    companion = _load_regular_json(
        DEFAULT_PATCH_MANIFEST_PATH,
        context="E0-MH companion",
    )
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1SequenceSeed20260612PatchError("Published E0-MH companion drifted")
    if companion_record != _canonical_json_record(
        companion,
        DEFAULT_PATCH_MANIFEST_PATH,
        role="p1_sequence_seed_20260612_patch_companion",
        context="E0-MH companion",
    ):
        raise P1SequenceSeed20260612PatchError(
            "Published E0-MH companion record drifted"
        )
    if p1_seed_20260612_namespace_absence() != sequence_before:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH sequence namespace changed during gate"
        )
    if closure_progression_prelock() != progression_before:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH progression namespace changed during gate"
        )
    return payload, {
        "status": "published_p1_sequence_seed_20260612_patch_valid",
        "gate": PATCH_GATE,
        "patch_head": payload["patch_repository"]["head"],
        "lock_commit": lock_commit,
        "execution_head": execution_head,
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_e0_mc_verified": True,
        "historical_e0_mg_verified": True,
        "p1_1729_publication_verified": True,
        "anfis_20260612_state_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": True,
        "progression_prelock_verified": True,
        "authorization_inputs": [lock_record, companion_record],
        **EFFECTIVE_AUTHORIZATIONS,
    }


def require_p1_sequence_seed_20260612_authorized(
    model_id: str,
    base_seed: int | None,
) -> dict[str, Any]:
    if model_id != AUTHORIZED_MODEL_ID or base_seed != AUTHORIZED_BASE_SEED:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH authorizes only the one-shot P1 sequence build for seed 20260612"
        )
    _, summary = load_and_validate_p1_sequence_seed_20260612_patch_lock()
    required_true = (
        "prior_p1_1729_slot_completed",
        "publication_verified",
        "remote_publication_verified",
        "historical_e0_mc_verified",
        "historical_e0_mg_verified",
        "p1_1729_publication_verified",
        "anfis_20260612_state_verified",
        "transactional_builder_verified",
        "sequence_namespace_absent",
        "progression_prelock_verified",
        "p1_sequence_builder_authorized",
        "authorization_effective",
    )
    failed = [field for field in required_true if summary.get(field) is not True]
    if failed:
        raise P1SequenceSeed20260612PatchError(
            f"E0-MH authorization predicates failed: {failed}"
        )
    required_false = (
        "batch_seed_execution_authorized",
        "retry_authorized",
        "p1_consumer_authorized",
        "p1_fit_authorized",
        "dvc_commands_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "future_outcomes_accessed",
        "effective_in_payload",
        "publication_required",
    )
    drifted = [field for field in required_false if summary.get(field) is not False]
    if drifted:
        raise P1SequenceSeed20260612PatchError(
            f"E0-MH fail-closed seals drifted: {drifted}"
        )
    p1_seed_20260612_namespace_absence()
    closure_progression_prelock()
    return summary
