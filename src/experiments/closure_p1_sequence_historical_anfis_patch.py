#!/usr/bin/env python
"""Validate the additive Closure V1 historical-ANFIS sequence patch.

E0-MC is a narrow successor to the published E0-MB authority.  It keeps
P-E0-MB and P-E0-DLP immutable, reconstructs their historical evidence from
Git, and permits only the one-shot P1 sequence build for seed 1729.  The
historical E0-DLP *effective* loader is deliberately not used: that loader is
correctly bound to the physical files that existed at H-E0-DLP and therefore
cannot validate a later, intentionally hardened sequence builder.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments import closure_development_runtime_patch as dlp
from src.experiments import closure_development_runtime_sequence_patch as dls
from src.experiments import closure_p1_sequence_builder_patch as e0_mb
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_p1_sequence_historical_anfis_patch_lock_v1"
PATCH_GATE = "E0-MC"
PATCH_ID = "p1_sequence_historical_anfis_authority_patch_1"
PATCH_STATUS = "locked"
EXPERIMENT_ID = "closure_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
PUBLISHED_REF = "origin/main"

E0_MB_H_COMMIT = "e6fba7acc98287fb3d1e405bd7ffc64a7ff8793e"
E0_MB_P_COMMIT = "34c0b4e3203eca32bee69732a823519f2b0e61eb"
E0_DLP_H_COMMIT = "5bb01e92b9b8c9b099b07b2f2cc5b8b9be359b30"
E0_DLP_P_COMMIT = "9123b5120f9470bba8643c6f4c73b86f85ccec25"
PATCH_BASE_COMMIT = E0_MB_P_COMMIT

AUTHORIZED_MODEL_ID = "P1"
AUTHORIZED_BASE_SEED = 1729

DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/p1_sequence_historical_anfis_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "p1_sequence_historical_anfis_patch_lock_manifest.json"
)
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/p1_sequence_historical_anfis_patch_lock.schema.json"
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): (
        "p1_sequence_historical_anfis_patch_lock_schema"
    ),
    "docs/closure_v1/E0_M_P1_SEQUENCE_HISTORICAL_ANFIS_PATCH_1.md": (
        "p1_sequence_historical_anfis_patch_protocol"
    ),
    "src/experiments/build_closure_pipe_sequences.py": (
        "historical_anfis_aware_p1_sequence_builder"
    ),
    "src/experiments/closure_p1_sequence_historical_anfis_patch.py": (
        "p1_sequence_historical_anfis_patch_validator"
    ),
    "src/experiments/lock_closure_p1_sequence_historical_anfis_patch.py": (
        "p1_sequence_historical_anfis_patch_locker"
    ),
    "tests/test_build_closure_pipe_sequences.py": (
        "historical_anfis_aware_p1_sequence_builder_tests"
    ),
    "tests/test_closure_p1_sequence_historical_anfis_patch.py": (
        "p1_sequence_historical_anfis_patch_tests"
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

E0_MB_SUPERSEDED_PATHS = PATCH_MODIFIED_PATHS
E0_MB_PRESERVED_PATHS = tuple(
    path for path in e0_mb.PATCH_PATHS if path not in E0_MB_SUPERSEDED_PATHS
)
E0_DLP_SUPERSEDED_PATHS = PATCH_MODIFIED_PATHS
E0_DLP_PRESERVED_DRIFT_PATHS = tuple(
    path
    for path in dlp.BASE_COMPONENT_DRIFT_ALLOWLIST
    if path not in E0_DLP_SUPERSEDED_PATHS
)

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_p1_sequence_historical_anfis_patch.py",
    "tests/test_closure_p1_sequence_builder_patch.py",
    "tests/test_build_closure_pipe_sequences.py",
    "-q",
)
FOCUSED_TEST_COUNT = 116
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")

PATCH_CORRECTION = {
    "issue_id": "historical_anfis_effective_loader_domain_mismatch_1",
    "classification": "historical_provenance_adapter_only",
    "legacy_effective_dlp_loader_used_for_historical_manifest": False,
    "replacement": "git_bound_historical_e0_dlp_reconstruction",
    "e0_mb_superseded_component_count": 2,
    "e0_mb_preserved_component_count": 5,
    "e0_dlp_superseded_drift_component_count": 2,
    "e0_dlp_preserved_drift_component_count": 4,
    "scientific_sequence_contract_changed": False,
    "state_mapping_changed": False,
    "denominator_changed": False,
    "outcome_access_changed": False,
}
PATCH_AUTHORIZATIONS = {
    "prior_one_shot_authorization_consumed": True,
    "p1_sequence_retry_authorized": False,
    "p1_sequence_builder_authorized": False,
    "effective_in_payload": False,
    "publication_required": True,
    "authorized_model_id": AUTHORIZED_MODEL_ID,
    "authorized_base_seed": AUTHORIZED_BASE_SEED,
    "batch_seed_execution_authorized": False,
    "retry_under_previous_authority_authorized": False,
    "p1_fit_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "future_outcomes_accessed": False,
}
EFFECTIVE_AUTHORIZATIONS = {
    **PATCH_AUTHORIZATIONS,
    "p1_sequence_retry_authorized": True,
    "p1_sequence_builder_authorized": True,
    "publication_required": False,
    "authorization_effective": True,
}
PATCH_SEALS = {
    "e0_mb_preserved_as_historical_authority": True,
    "e0_dlp_preserved_as_historical_authority": True,
    "e0_mb_lock_rewritten": False,
    "e0_dlp_lock_rewritten": False,
    "only_builder_and_test_superseded_in_e0_mb": True,
    "only_builder_and_test_superseded_in_e0_dlp_drift": True,
    "scientific_sequence_contract_changed": False,
    "state_mapping_changed": False,
    "denominator_changed": False,
    "seed_order_changed": False,
    "holdout_accessed": False,
    "post_2021_outcomes_accessed": False,
    "does_not_replace_e0_m": True,
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class P1SequenceHistoricalAnfisPatchError(RuntimeError):
    """Raised when E0-MC cannot prove its closed historical authority."""


def _translate(error: BaseException) -> P1SequenceHistoricalAnfisPatchError:
    return P1SequenceHistoricalAnfisPatchError(str(error))


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
        return e0_mb._git(*args)
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def _require_commit(value: str, *, context: str) -> str:
    try:
        return e0_mb._require_commit(value, context=context)
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def _require_ancestor(ancestor: str, descendant: str) -> None:
    try:
        e0_mb._require_ancestor(ancestor, descendant)
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def _git_blob(commit: str, path: str) -> bytes:
    try:
        return e0_mb._git_blob(commit, path)
    except e0_mb.P1SequenceBuilderPatchError as exc:
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
        return e0_mb._file_record(path, role=role)
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def _file_identity(path: Path) -> dict[str, Any]:
    record = _file_record(path, role="physical_file")
    return {key: record[key] for key in ("path", "bytes", "sha256")}


def _physical_git_record(
    commit: str,
    path: str,
    *,
    role: str,
) -> dict[str, Any]:
    expected = _git_record(commit, path, role=role)
    physical = _file_record(Path(path), role=role)
    if physical != expected:
        raise P1SequenceHistoricalAnfisPatchError(
            f"Physical artifact differs from Git authority {commit}: {path}"
        )
    return expected


def _load_regular_json(path: Path, *, context: str) -> dict[str, Any]:
    try:
        return e0_mb._load_regular_json(path, context=context)
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def _canonical_json_record(
    payload: Mapping[str, Any],
    path: Path,
    *,
    role: str,
    context: str,
) -> dict[str, Any]:
    record = _file_record(path, role=role)
    canonical = _canonical_json(payload)
    if record["bytes"] != len(canonical) or record["sha256"] != _sha256_bytes(
        canonical
    ):
        raise P1SequenceHistoricalAnfisPatchError(
            f"{context} bytes are not canonical"
        )
    return record


def _introduced_commit(path: str) -> str:
    try:
        return e0_mb._introduced_commit(path)
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def _observed_diff_entries(base: str, head: str) -> list[dict[str, str]]:
    try:
        return e0_mb._observed_diff_entries(base, head)
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def _assert_paths_untouched(
    base: str,
    descendant: str,
    paths: Sequence[str],
    *,
    context: str,
) -> None:
    try:
        e0_mb._assert_paths_untouched(base, descendant, paths, context=context)
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def _remote_main_oid() -> str:
    try:
        return e0_mb._remote_main_oid()
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def _component_set(
    records: Sequence[Mapping[str, Any]],
    *,
    current_bytes_required_to_match_historical: bool,
) -> dict[str, Any]:
    normalized = [dict(record) for record in records]
    paths = [str(record["path"]) for record in normalized]
    return {
        "count": len(normalized),
        "paths": paths,
        "records": normalized,
        "records_sha256": _record_digest(normalized),
        "current_bytes_required_to_match_historical": (
            current_bytes_required_to_match_historical
        ),
    }


def patch_git_diff_payload(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-E0-MC")
    ancestry = _git("rev-list", "--parents", "-n", "1", patch_head).split()
    if ancestry != [patch_head, PATCH_BASE_COMMIT]:
        raise P1SequenceHistoricalAnfisPatchError(
            "H-E0-MC must be the direct non-merge child of P-E0-MB"
        )
    expected = [
        {
            "status": "M" if path in PATCH_MODIFIED_PATHS else "A",
            "path": path,
        }
        for path in PATCH_PATHS
    ]
    observed = _observed_diff_entries(PATCH_BASE_COMMIT, patch_head)
    if observed != expected:
        raise P1SequenceHistoricalAnfisPatchError(
            f"H-E0-MC diff differs from its closed 2M+5A allowlist: {observed}"
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
    patch_head = _require_commit(patch_head, context="H-E0-MC")
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


def _reconstruct_published_e0_mb_historical_authority(
    *, execution_head: str
) -> dict[str, Any]:
    if e0_mb.PATCH_BASE_COMMIT != "9851211bdc7b14d07ccfef997e7681a232f1f611":
        raise P1SequenceHistoricalAnfisPatchError("E0-MB base commit drifted")
    try:
        payload, summary = (
            e0_mb.load_published_p1_sequence_builder_patch_historical_authority()
        )
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc
    if (
        summary.get("patch_head") != E0_MB_H_COMMIT
        or summary.get("lock_commit") != E0_MB_P_COMMIT
        or summary.get("authorization_effective") is not False
        or summary.get("p1_sequence_builder_authorized") is not False
    ):
        raise P1SequenceHistoricalAnfisPatchError(
            "Published E0-MB historical summary drifted"
        )

    components = cast(Mapping[str, Any], payload["patch_components"])
    raw_records = cast(Sequence[Mapping[str, Any]], components["records"])
    by_path = {str(record["path"]): dict(record) for record in raw_records}
    if set(by_path) != set(e0_mb.PATCH_PATHS):
        raise P1SequenceHistoricalAnfisPatchError(
            "Historical H-E0-MB component paths drifted"
        )
    superseded = [by_path[path] for path in E0_MB_SUPERSEDED_PATHS]
    preserved = [by_path[path] for path in E0_MB_PRESERVED_PATHS]
    for record in superseded:
        expected = _git_record(
            E0_MB_H_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        )
        if record != expected:
            raise P1SequenceHistoricalAnfisPatchError(
                f"Historical H-E0-MB superseded component drifted: {record['path']}"
            )
    for record in preserved:
        path = str(record["path"])
        expected = _git_record(
            E0_MB_H_COMMIT,
            path,
            role=str(record["role"]),
        )
        physical = _file_record(Path(path), role=str(record["role"]))
        current = _git_record(
            execution_head,
            path,
            role=str(record["role"]),
        )
        if record != expected or physical != record or current != record:
            raise P1SequenceHistoricalAnfisPatchError(
                f"Preserved H-E0-MB component drifted: {path}"
            )
    _assert_paths_untouched(
        E0_MB_H_COMMIT,
        execution_head,
        E0_MB_PRESERVED_PATHS,
        context="preserved H-E0-MB components",
    )

    lock_record = _physical_git_record(
        E0_MB_P_COMMIT,
        e0_mb.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        role="external_p1_sequence_builder_patch_lock",
    )
    companion_record = _physical_git_record(
        E0_MB_P_COMMIT,
        e0_mb.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        role="p1_sequence_builder_patch_companion",
    )
    return {
        "gate": "E0-MB",
        "patch_head": E0_MB_H_COMMIT,
        "lock_commit": E0_MB_P_COMMIT,
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
        "p1_sequence_builder_authorized": False,
        "p1_fit_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }


def _expected_dlp_drift_records(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    try:
        base_snapshot = dlp._base_lock_snapshot(
            dlp.DEFAULT_LOCK_PATH,
            dlp.DEFAULT_LOCK_SCHEMA,
        )
        base_payload = cast(Mapping[str, Any], base_snapshot["payload"])
        base_records = dlp._base_component_records(base_payload)
    except dlp.DevelopmentRuntimePatchError as exc:
        raise _translate(exc) from exc
    records: list[dict[str, Any]] = []
    for path in sorted(dlp.BASE_COMPONENT_DRIFT_ALLOWLIST):
        base = base_records.get(path)
        if base is None:
            raise P1SequenceHistoricalAnfisPatchError(
                f"E0-DLP base component is absent: {path}"
            )
        blob = _git_blob(E0_DLP_H_COMMIT, path)
        records.append(
            {
                "path": path,
                "base_bytes": base["bytes"],
                "base_sha256": base["sha256"],
                "patch_bytes": len(blob),
                "patch_sha256": _sha256_bytes(blob),
            }
        )
    return records


def _dlp_historical_summary(
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    preserved = cast(Mapping[str, Any], authority["preserved_components"])
    return {
        "base_repository_head": authority["base_repository_head"],
        "e0_dlp_patch_head": authority["e0_dlp_patch_head"],
        "e0_dlp_lock_commit": authority["e0_dlp_lock_commit"],
        "records_sha256": authority["records_sha256"],
        "preserved_component_count": preserved["count"],
        "preserved_component_records_sha256": preserved["records_sha256"],
        "base_e0_dl_unchanged": authority["base_e0_dl_unchanged"],
        "base_e0_dlp_unchanged": authority["base_e0_dlp_unchanged"],
        "historical_schema_and_payload_validated": authority[
            "historical_schema_and_payload_validated"
        ],
        "physical_development_authority_verified": authority[
            "physical_development_authority_verified"
        ],
        "e0_dlp_adopted_seed_physical_artifacts_verified": authority[
            "e0_dlp_adopted_seed_physical_artifacts_verified"
        ],
    }


def _reconstruct_historical_e0_dlp_authority(
    *,
    execution_head: str,
    require_physical_artifacts: bool,
) -> dict[str, Any]:
    payload = _load_regular_json(dlp.DEFAULT_PATCH_LOCK_PATH, context="P-E0-DLP lock")
    schema = _load_regular_json(
        dlp.DEFAULT_PATCH_LOCK_SCHEMA,
        context="P-E0-DLP schema",
    )
    try:
        # Static/schema validation is historical-safe.  Do not replace this
        # with load_and_validate_development_runtime_patch_lock(), whose
        # effective contract intentionally compares current physical paths.
        dlp.validate_development_runtime_patch_lock_payload(payload, schema)
    except (ClosureContractError, dlp.DevelopmentRuntimePatchError) as exc:
        raise _translate(exc) from exc

    if (
        cast(Mapping[str, Any], payload["patch_repository"]).get("head")
        != E0_DLP_H_COMMIT
    ):
        raise P1SequenceHistoricalAnfisPatchError("Historical E0-DLP H commit drifted")
    ancestry = _git("rev-list", "--parents", "-n", "1", E0_DLP_P_COMMIT).split()
    if ancestry != [E0_DLP_P_COMMIT, E0_DLP_H_COMMIT]:
        raise P1SequenceHistoricalAnfisPatchError(
            "P-E0-DLP is not the direct child of H-E0-DLP"
        )
    expected_publication = [
        {"status": "A", "path": dlp.DEFAULT_PATCH_LOCK_PATH.as_posix()},
        {"status": "A", "path": dlp.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix()},
    ]
    if _observed_diff_entries(E0_DLP_H_COMMIT, E0_DLP_P_COMMIT) != expected_publication:
        raise P1SequenceHistoricalAnfisPatchError("P-E0-DLP scope drifted")
    _require_ancestor(E0_DLP_P_COMMIT, execution_head)
    _assert_paths_untouched(
        E0_DLP_P_COMMIT,
        execution_head,
        (
            dlp.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            dlp.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
        ),
        context="P-E0-DLP publication",
    )

    lock_record = _physical_git_record(
        E0_DLP_P_COMMIT,
        dlp.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        role="external_development_runtime_patch_lock",
    )
    companion_record = _physical_git_record(
        E0_DLP_P_COMMIT,
        dlp.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
        role="development_runtime_patch_companion",
    )
    try:
        dlp._validate_patch_publication_bundle(
            payload,
            execution_head=execution_head,
            published_head=execution_head,
        )
    except dlp.DevelopmentRuntimePatchError as exc:
        raise _translate(exc) from exc

    expected_drift = _expected_dlp_drift_records(payload)
    locked_drift = cast(Mapping[str, Any], payload["base_component_drift"])
    raw_locked_records = cast(
        Sequence[Mapping[str, Any]],
        locked_drift["records"],
    )
    locked_records = [dict(record) for record in raw_locked_records]
    if locked_records != expected_drift:
        raise P1SequenceHistoricalAnfisPatchError(
            "Historical E0-DLP base-component drift records changed"
        )
    by_path = {str(record["path"]): record for record in locked_records}
    superseded = [by_path[path] for path in E0_DLP_SUPERSEDED_PATHS]
    preserved = [by_path[path] for path in E0_DLP_PRESERVED_DRIFT_PATHS]
    for record in preserved:
        path = Path(str(record["path"]))
        physical = _file_identity(path)
        if (
            physical["bytes"] != record["patch_bytes"]
            or physical["sha256"] != record["patch_sha256"]
        ):
            raise P1SequenceHistoricalAnfisPatchError(
                f"Preserved E0-DLP drift component changed physically: {path}"
            )
    _assert_paths_untouched(
        E0_DLP_H_COMMIT,
        execution_head,
        E0_DLP_PRESERVED_DRIFT_PATHS,
        context="preserved E0-DLP drift components",
    )

    patch_components = cast(Mapping[str, Any], payload["patch_components"])
    raw_patch_records = cast(
        Sequence[Mapping[str, Any]],
        patch_components["records"],
    )
    patch_records = [dict(record) for record in raw_patch_records]
    expected_patch_paths = tuple(sorted(dlp.PATCH_COMPONENT_ROLES))
    if [str(record["path"]) for record in patch_records] != list(
        expected_patch_paths
    ):
        raise P1SequenceHistoricalAnfisPatchError(
            "Historical E0-DLP patch-component paths drifted"
        )
    for record in patch_records:
        path = str(record["path"])
        expected = _git_record(
            E0_DLP_H_COMMIT,
            path,
            role=str(record["role"]),
        )
        physical = _file_record(Path(path), role=str(record["role"]))
        if record != expected or physical != record:
            raise P1SequenceHistoricalAnfisPatchError(
                f"Preserved E0-DLP patch component drifted: {path}"
            )
    _assert_paths_untouched(
        E0_DLP_H_COMMIT,
        execution_head,
        expected_patch_paths,
        context="preserved E0-DLP patch components",
    )

    try:
        dls_authority = dls._historical_authority_record(
            require_physical_artifacts=require_physical_artifacts
        )
    except (dls.DevelopmentRuntimeSequencePatchError, RuntimeError, ValueError) as exc:
        raise _translate(exc) from exc
    adopted = cast(Mapping[str, Any], payload["adopted_seed_bundle"])
    manifest = cast(Mapping[str, Any], adopted["manifest"])
    return {
        "gate": "E0-DLP",
        "patch_head": E0_DLP_H_COMMIT,
        "lock_commit": E0_DLP_P_COMMIT,
        "lock": lock_record,
        "companion_manifest": companion_record,
        "superseded_drift_components": _component_set(
            superseded,
            current_bytes_required_to_match_historical=False,
        ),
        "preserved_drift_components": _component_set(
            preserved,
            current_bytes_required_to_match_historical=True,
        ),
        "preserved_patch_components": _component_set(
            patch_records,
            current_bytes_required_to_match_historical=True,
        ),
        "adopted_seed_manifest": dict(manifest),
        "dls_historical_authority": _dlp_historical_summary(dls_authority),
        "effective_dlp_loader_called": False,
        "historical_authority_verified": True,
        "development_fit_historically_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }


def _historical_anfis_contract(
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    manifest = cast(Mapping[str, Any], authority["adopted_seed_manifest"])
    return {
        "base_seed": AUTHORIZED_BASE_SEED,
        "manifest": dict(manifest),
        "runtime_validator_record": dict(dlp.HISTORICAL_RUNTIME_VALIDATOR_RECORD),
        "generating_script_record": dict(dlp.HISTORICAL_ANFIS_SCRIPT_RECORD),
        "strict_state_adapter_record": dict(dlp.HISTORICAL_ANFIS_DEPENDENCY_RECORD),
        "historical_uppercase_artifact_paths": True,
        "effective_dlp_loader_called": False,
        "git_bound_historical_authority_required": True,
    }


def p1_sequence_namespace_absence() -> dict[str, Any]:
    try:
        return e0_mb.p1_sequence_namespace_absence()
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def closure_progression_namespace_absence() -> dict[str, Any]:
    try:
        return e0_mb.closure_progression_namespace_absence()
    except e0_mb.P1SequenceBuilderPatchError as exc:
        raise _translate(exc) from exc


def collect_p1_sequence_historical_anfis_patch_prelock_state(
    verify_remote: bool,
) -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise P1SequenceHistoricalAnfisPatchError(
            f"H-E0-MC lock requires a clean worktree: {status}"
        )
    head = _require_commit(_git("rev-parse", "HEAD"), context="H-E0-MC HEAD")
    if _git("branch", "--show-current") != "main":
        raise P1SequenceHistoricalAnfisPatchError("H-E0-MC requires branch main")
    published = _require_commit(
        _git("rev-parse", PUBLISHED_REF),
        context=PUBLISHED_REF,
    )
    if published != head:
        raise P1SequenceHistoricalAnfisPatchError(
            "H-E0-MC HEAD differs from origin/main"
        )
    remote = _remote_main_oid() if verify_remote else published
    if remote != head:
        raise P1SequenceHistoricalAnfisPatchError(
            "H-E0-MC HEAD differs from live origin/main"
        )
    git_diff = patch_git_diff_payload(head)
    components = patch_component_bundle(head)
    for record in cast(Sequence[Mapping[str, Any]], components["records"]):
        physical = _file_record(Path(str(record["path"])), role=str(record["role"]))
        if physical != record:
            raise P1SequenceHistoricalAnfisPatchError(
                f"H-E0-MC physical component differs from Git: {record['path']}"
            )
    e0_mb_authority = _reconstruct_published_e0_mb_historical_authority(
        execution_head=head
    )
    e0_dlp_authority = _reconstruct_historical_e0_dlp_authority(
        execution_head=head,
        require_physical_artifacts=True,
    )
    sequence_prelock = p1_sequence_namespace_absence()
    progression_prelock = closure_progression_namespace_absence()
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
            "e0_mb": e0_mb_authority,
            "e0_dlp": e0_dlp_authority,
        },
        "current_runtime_builder_record": builder,
        "historical_anfis_contract": _historical_anfis_contract(e0_dlp_authority),
        "sequence_prelock": sequence_prelock,
        "progression_prelock": progression_prelock,
    }


def _validate_command_evidence(
    value: Any,
    command: Sequence[str],
    *,
    context: str,
) -> None:
    if not isinstance(value, Mapping):
        raise P1SequenceHistoricalAnfisPatchError(
            f"E0-MC {context} evidence must be an object"
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
        raise P1SequenceHistoricalAnfisPatchError(
            f"E0-MC {context} command evidence drifted"
        )
    if value.get("returncode") != 0:
        raise P1SequenceHistoricalAnfisPatchError(
            f"E0-MC {context} did not pass"
        )
    for field in ("stdout_sha256", "stderr_sha256"):
        if SHA256_RE.fullmatch(str(value.get(field, ""))) is None:
            raise P1SequenceHistoricalAnfisPatchError(
                f"E0-MC {context} {field} drifted"
            )
    for field in ("stdout_line_count", "stderr_line_count"):
        if type(value.get(field)) is not int or value[field] < 0:
            raise P1SequenceHistoricalAnfisPatchError(
                f"E0-MC {context} {field} drifted"
            )


def validate_p1_sequence_historical_anfis_patch_verification(
    payload: Mapping[str, Any],
) -> None:
    commands = {
        "full_type_check": TYPE_CHECK_COMMAND,
        "focused_tests": FOCUSED_TEST_COMMAND,
        "poetry_check": POETRY_CHECK_COMMAND,
        "publication_guard": PUBLICATION_GUARD_COMMAND,
        "git_diff_check": DIFF_CHECK_COMMAND,
    }
    if set(payload) != set(commands):
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC verification fields drifted"
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
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC focused-test evidence drifted"
        )


def build_p1_sequence_historical_anfis_patch_lock_payload(
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
        "patch_repository": dict(
            cast(Mapping[str, Any], prelock["patch_repository"])
        ),
        "git_diff": dict(cast(Mapping[str, Any], prelock["git_diff"])),
        "patch_components": dict(
            cast(Mapping[str, Any], prelock["patch_components"])
        ),
        "base_authorities": dict(
            cast(Mapping[str, Any], prelock["base_authorities"])
        ),
        "current_runtime_builder_record": dict(
            cast(Mapping[str, Any], prelock["current_runtime_builder_record"])
        ),
        "historical_anfis_contract": dict(
            cast(Mapping[str, Any], prelock["historical_anfis_contract"])
        ),
        "sequence_prelock": dict(
            cast(Mapping[str, Any], prelock["sequence_prelock"])
        ),
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
            "role": "external_p1_sequence_historical_anfis_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }


def validate_p1_sequence_historical_anfis_patch_lock_payload(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    require_physical_patch_components: bool = True,
) -> None:
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.p1_sequence_historical_anfis_patch_lock",
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
            "role": "external_p1_sequence_historical_anfis_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise P1SequenceHistoricalAnfisPatchError(
                f"E0-MC fixed field drifted: {field}"
            )
    created = payload.get("created_at_utc")
    if not isinstance(created, str):
        raise P1SequenceHistoricalAnfisPatchError("E0-MC timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC timestamp is invalid"
        ) from exc
    if timestamp.utcoffset() is None:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC timestamp requires a timezone"
        )

    repository = cast(Mapping[str, Any], payload["patch_repository"])
    patch_head = _require_commit(str(repository.get("head", "")), context="H-E0-MC")
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
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC patch repository record drifted"
        )
    if payload.get("git_diff") != patch_git_diff_payload(patch_head):
        raise P1SequenceHistoricalAnfisPatchError("E0-MC Git diff drifted")
    components = patch_component_bundle(patch_head)
    if payload.get("patch_components") != components:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC component bundle drifted"
        )
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    if require_physical_patch_components:
        for record in cast(Sequence[Mapping[str, Any]], components["records"]):
            physical = _file_record(
                Path(str(record["path"])),
                role=str(record["role"]),
            )
            if physical != record:
                raise P1SequenceHistoricalAnfisPatchError(
                    f"Physical H-E0-MC component drifted: {record['path']}"
                )
        _assert_paths_untouched(
            patch_head,
            execution_head,
            PATCH_PATHS,
            context="H-E0-MC components",
        )

    expected_authorities = {
        "e0_mb": _reconstruct_published_e0_mb_historical_authority(
            execution_head=execution_head
        ),
        "e0_dlp": _reconstruct_historical_e0_dlp_authority(
            execution_head=execution_head,
            require_physical_artifacts=True,
        ),
    }
    if payload.get("base_authorities") != expected_authorities:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC historical authorities drifted"
        )
    expected_contract = _historical_anfis_contract(expected_authorities["e0_dlp"])
    if payload.get("historical_anfis_contract") != expected_contract:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC historical ANFIS contract drifted"
        )
    builder_records = [
        record
        for record in cast(Sequence[Mapping[str, Any]], components["records"])
        if record["path"] == "src/experiments/build_closure_pipe_sequences.py"
    ]
    if len(builder_records) != 1:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC current builder component is not unique"
        )
    expected_builder = dict(builder_records[0])
    expected_builder["role"] = "current_runtime_builder"
    if payload.get("current_runtime_builder_record") != expected_builder:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC current builder record drifted"
        )
    if payload.get("sequence_prelock") != e0_mb._sequence_prelock_contract():
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC sequence prelock drifted"
        )
    if payload.get("progression_prelock") != e0_mb._progression_prelock_contract():
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC progression prelock drifted"
        )
    validate_p1_sequence_historical_anfis_patch_verification(
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
    mb_authority = cast(Mapping[str, Any], authorities["e0_mb"])
    dlp_authority = cast(Mapping[str, Any], authorities["e0_dlp"])
    inputs = [
        _generic_record(
            by_path[DEFAULT_PATCH_LOCK_SCHEMA.as_posix()],
            role="p1_sequence_historical_anfis_patch_lock_schema",
        ),
        _generic_record(
            by_path[
                "src/experiments/closure_p1_sequence_historical_anfis_patch.py"
            ],
            role="p1_sequence_historical_anfis_patch_validator",
        ),
        _generic_record(
            by_path["src/experiments/build_closure_pipe_sequences.py"],
            role="current_runtime_builder",
        ),
        dict(cast(Mapping[str, Any], mb_authority["lock"])),
        dict(cast(Mapping[str, Any], mb_authority["companion_manifest"])),
        dict(cast(Mapping[str, Any], dlp_authority["lock"])),
        dict(cast(Mapping[str, Any], dlp_authority["companion_manifest"])),
    ]
    inputs = sorted(inputs, key=lambda record: str(record["path"]))

    historical_inputs: list[dict[str, Any]] = []
    mb_superseded = cast(Mapping[str, Any], mb_authority["superseded_components"])
    for record in cast(Sequence[Mapping[str, Any]], mb_superseded["records"]):
        historical_inputs.append(
            {
                **dict(record),
                "commit": E0_MB_H_COMMIT,
                "hash_source": "git_blob_at_commit",
            }
        )
    dlp_superseded = cast(
        Mapping[str, Any], dlp_authority["superseded_drift_components"]
    )
    for record in cast(Sequence[Mapping[str, Any]], dlp_superseded["records"]):
        historical_inputs.append(
            {
                "path": record["path"],
                "role": "historical_e0_dlp_patched_base_component",
                "bytes": record["patch_bytes"],
                "sha256": record["patch_sha256"],
                "commit": E0_DLP_H_COMMIT,
                "hash_source": "git_blob_at_commit",
            }
        )
    historical_inputs = sorted(
        historical_inputs,
        key=lambda record: (str(record["path"]), str(record["commit"])),
    )
    return {
        "manifest_version": "closure_p1_sequence_historical_anfis_patch_manifest_v1",
        "status": "completed",
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": payload["created_at_utc"],
        "outputs": [dict(lock_record)],
        "script": _generic_record(
            by_path[
                "src/experiments/lock_closure_p1_sequence_historical_anfis_patch.py"
            ],
            role="generating_script",
        ),
        "inputs": inputs,
        "historical_inputs": historical_inputs,
        "physical_inputs_only": True,
        "historical_inputs_compared_to_current_paths": False,
        "prior_one_shot_authorization_consumed": True,
        "p1_sequence_retry_authorized": False,
        "p1_sequence_builder_authorized": False,
        "effective_in_payload": False,
        "publication_required": True,
        "authorized_model_id": AUTHORIZED_MODEL_ID,
        "authorized_base_seed": AUTHORIZED_BASE_SEED,
        "retry_under_previous_authority_authorized": False,
        "p1_fit_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
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
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC lock and companion commits differ"
        )
    ancestry = _git("rev-list", "--parents", "-n", "1", lock_commit).split()
    if ancestry != [lock_commit, patch_head]:
        raise P1SequenceHistoricalAnfisPatchError(
            "P-E0-MC must be the direct child of H-E0-MC"
        )
    expected = [
        {"status": "A", "path": lock_path},
        {"status": "A", "path": companion_path},
    ]
    if _observed_diff_entries(patch_head, lock_commit) != expected:
        raise P1SequenceHistoricalAnfisPatchError(
            "P-E0-MC must add exactly lock plus companion"
        )
    _require_ancestor(lock_commit, execution_head)
    _assert_paths_untouched(
        lock_commit,
        execution_head,
        (lock_path, companion_path),
        context="P-E0-MC publication",
    )
    return (
        lock_commit,
        _physical_git_record(
            lock_commit,
            lock_path,
            role="external_p1_sequence_historical_anfis_patch_lock",
        ),
        _physical_git_record(
            lock_commit,
            companion_path,
            role="p1_sequence_historical_anfis_patch_companion",
        ),
    )


def _load_unpublished_p1_sequence_historical_anfis_patch_lock(
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _load_regular_json(DEFAULT_PATCH_LOCK_PATH, context="E0-MC lock")
    schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MC schema")
    validate_p1_sequence_historical_anfis_patch_lock_payload(payload, schema)
    lock_record = _canonical_json_record(
        payload,
        DEFAULT_PATCH_LOCK_PATH,
        role="external_p1_sequence_historical_anfis_patch_lock",
        context="E0-MC lock",
    )
    companion = _load_regular_json(DEFAULT_PATCH_MANIFEST_PATH, context="E0-MC companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1SequenceHistoricalAnfisPatchError("E0-MC companion drifted")
    _canonical_json_record(
        companion,
        DEFAULT_PATCH_MANIFEST_PATH,
        role="p1_sequence_historical_anfis_patch_companion",
        context="E0-MC companion",
    )
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    if execution_head != patch_head:
        raise P1SequenceHistoricalAnfisPatchError(
            "Unpublished E0-MC validation must run at H-E0-MC"
        )
    return payload, {
        "status": "locked_unpublished",
        "gate": PATCH_GATE,
        "patch_head": patch_head,
        "lock_commit": None,
        "execution_head": execution_head,
        "published_head": None,
        "publication_verified": False,
        "remote_publication_verified": False,
        "historical_e0_mb_verified": True,
        "historical_e0_dlp_verified": True,
        "historical_anfis_context_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": False,
        "authorization_effective": False,
        **PATCH_AUTHORIZATIONS,
    }


def load_published_p1_sequence_historical_anfis_patch_historical_authority(
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _load_regular_json(DEFAULT_PATCH_LOCK_PATH, context="E0-MC lock")
    schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MC schema")
    validate_p1_sequence_historical_anfis_patch_lock_payload(
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
        role="external_p1_sequence_historical_anfis_patch_lock",
        context="E0-MC lock",
    ):
        raise P1SequenceHistoricalAnfisPatchError("Published E0-MC lock drifted")
    companion = _load_regular_json(DEFAULT_PATCH_MANIFEST_PATH, context="E0-MC companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1SequenceHistoricalAnfisPatchError("Published E0-MC companion drifted")
    if companion_record != _canonical_json_record(
        companion,
        DEFAULT_PATCH_MANIFEST_PATH,
        role="p1_sequence_historical_anfis_patch_companion",
        context="E0-MC companion",
    ):
        raise P1SequenceHistoricalAnfisPatchError(
            "Published E0-MC companion record drifted"
        )
    return payload, {
        "status": "published_p1_sequence_historical_anfis_patch_historical_authority_valid",
        "gate": PATCH_GATE,
        "patch_head": payload["patch_repository"]["head"],
        "lock_commit": lock_commit,
        "execution_head": execution_head,
        "publication_topology_verified": True,
        "authorization_effective": False,
        **PATCH_AUTHORIZATIONS,
    }


def load_and_validate_p1_sequence_historical_anfis_patch_lock(
) -> tuple[dict[str, Any], dict[str, Any]]:
    sequence_before = p1_sequence_namespace_absence()
    progression_before = closure_progression_namespace_absence()
    payload = _load_regular_json(DEFAULT_PATCH_LOCK_PATH, context="E0-MC lock")
    schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MC schema")
    validate_p1_sequence_historical_anfis_patch_lock_payload(payload, schema)
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise P1SequenceHistoricalAnfisPatchError(
            f"E0-MC execution requires a clean worktree and index: {status}"
        )
    lock_commit, lock_record, companion_record = _validate_p_commit_topology(
        payload,
        execution_head=execution_head,
    )
    if execution_head != lock_commit:
        raise P1SequenceHistoricalAnfisPatchError(
            "The one-shot E0-MC authorization requires HEAD at the exact P commit"
        )
    if _git("branch", "--show-current") != "main":
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC effective authorization requires branch main"
        )
    refs = {
        "head": execution_head,
        "main": _require_commit(_git("rev-parse", "main"), context="main"),
        "tracking": _require_commit(
            _git("rev-parse", PUBLISHED_REF),
            context=PUBLISHED_REF,
        ),
        "origin_head": _require_commit(
            _git("rev-parse", "origin/HEAD"),
            context="origin/HEAD",
        ),
    }
    if set(refs.values()) != {lock_commit}:
        raise P1SequenceHistoricalAnfisPatchError(
            f"E0-MC publication refs diverged: {refs}"
        )
    remote = _remote_main_oid()
    if remote != lock_commit:
        raise P1SequenceHistoricalAnfisPatchError(
            "Local and live origin/main differ for E0-MC"
        )
    if lock_record != _canonical_json_record(
        payload,
        DEFAULT_PATCH_LOCK_PATH,
        role="external_p1_sequence_historical_anfis_patch_lock",
        context="E0-MC lock",
    ):
        raise P1SequenceHistoricalAnfisPatchError("Published E0-MC lock drifted")
    companion = _load_regular_json(DEFAULT_PATCH_MANIFEST_PATH, context="E0-MC companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1SequenceHistoricalAnfisPatchError("Published E0-MC companion drifted")
    if companion_record != _canonical_json_record(
        companion,
        DEFAULT_PATCH_MANIFEST_PATH,
        role="p1_sequence_historical_anfis_patch_companion",
        context="E0-MC companion",
    ):
        raise P1SequenceHistoricalAnfisPatchError(
            "Published E0-MC companion record drifted"
        )
    if p1_sequence_namespace_absence() != sequence_before:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC sequence namespace changed during gate"
        )
    if closure_progression_namespace_absence() != progression_before:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC progression namespace changed during gate"
        )
    return payload, {
        "status": "published_p1_sequence_historical_anfis_patch_valid",
        "gate": PATCH_GATE,
        "patch_head": payload["patch_repository"]["head"],
        "lock_commit": lock_commit,
        "execution_head": execution_head,
        "published_head": lock_commit,
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_e0_mb_verified": True,
        "historical_e0_dlp_verified": True,
        "historical_anfis_context_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": True,
        "authorization_inputs": [lock_record, companion_record],
        **EFFECTIVE_AUTHORIZATIONS,
    }


def require_p1_sequence_historical_anfis_authorized(
    model_id: str,
    base_seed: int | None,
) -> dict[str, Any]:
    if model_id != AUTHORIZED_MODEL_ID or base_seed != AUTHORIZED_BASE_SEED:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC authorizes only the one-shot P1 sequence build for seed 1729"
        )
    _, summary = load_and_validate_p1_sequence_historical_anfis_patch_lock()
    required_true = (
        "prior_one_shot_authorization_consumed",
        "p1_sequence_retry_authorized",
        "publication_verified",
        "remote_publication_verified",
        "historical_e0_mb_verified",
        "historical_e0_dlp_verified",
        "historical_anfis_context_verified",
        "transactional_builder_verified",
        "sequence_namespace_absent",
        "p1_sequence_builder_authorized",
        "authorization_effective",
    )
    failed = [field for field in required_true if summary.get(field) is not True]
    if failed:
        raise P1SequenceHistoricalAnfisPatchError(
            f"E0-MC authorization predicates failed: {failed}"
        )
    required_false = (
        "batch_seed_execution_authorized",
        "retry_under_previous_authority_authorized",
        "effective_in_payload",
        "publication_required",
        "p1_fit_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "future_outcomes_accessed",
    )
    drifted = [field for field in required_false if summary.get(field) is not False]
    if drifted:
        raise P1SequenceHistoricalAnfisPatchError(
            f"E0-MC fail-closed seals drifted: {drifted}"
        )
    p1_sequence_namespace_absence()
    closure_progression_namespace_absence()
    return summary


def _require_effective_context_authorization(
    authorization: Mapping[str, Any] | None,
) -> None:
    if authorization is None:
        raise P1SequenceHistoricalAnfisPatchError(
            "Seed-1729 historical context requires explicit E0-MC authority"
        )
    required = {
        "gate": PATCH_GATE,
        "authorized_model_id": AUTHORIZED_MODEL_ID,
        "authorized_base_seed": AUTHORIZED_BASE_SEED,
        "prior_one_shot_authorization_consumed": True,
        "p1_sequence_retry_authorized": True,
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_e0_mb_verified": True,
        "historical_e0_dlp_verified": True,
        "historical_anfis_context_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": True,
        "p1_sequence_builder_authorized": True,
        "authorization_effective": True,
        "batch_seed_execution_authorized": False,
        "retry_under_previous_authority_authorized": False,
        "effective_in_payload": False,
        "publication_required": False,
        "p1_fit_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    drifted = [
        field
        for field, expected in required.items()
        if authorization.get(field) != expected
    ]
    if drifted:
        raise P1SequenceHistoricalAnfisPatchError(
            f"E0-MC historical context authorization drifted: {drifted}"
        )
    inputs = authorization.get("authorization_inputs")
    if (
        not isinstance(inputs, Sequence)
        or isinstance(inputs, (str, bytes))
        or len(inputs) != 2
    ):
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC historical context requires lock and companion inputs"
        )
    expected_inputs = {
        (
            DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "external_p1_sequence_historical_anfis_patch_lock",
        ),
        (
            DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
            "p1_sequence_historical_anfis_patch_companion",
        ),
    }
    observed_inputs: set[tuple[object, object]] = set()
    for record in inputs:
        if not isinstance(record, Mapping) or set(record) != {
            "path",
            "role",
            "bytes",
            "sha256",
        }:
            raise P1SequenceHistoricalAnfisPatchError(
                "E0-MC historical context authority input record drifted"
            )
        observed_inputs.add((record.get("path"), record.get("role")))
    if observed_inputs != expected_inputs:
        raise P1SequenceHistoricalAnfisPatchError(
            "E0-MC historical context authority input paths drifted"
        )


def historical_seed_1729_anfis_context(
    manifest: Mapping[str, Any],
    *,
    authorization: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    dependencies = manifest.get("dependencies")
    inputs = manifest.get("inputs")
    if (
        not isinstance(dependencies, Sequence)
        or isinstance(dependencies, (str, bytes))
        or not isinstance(inputs, Sequence)
        or isinstance(inputs, (str, bytes))
    ):
        return None
    historical_path = str(dlp.HISTORICAL_RUNTIME_VALIDATOR_RECORD["path"])
    dependency_matches = [
        record
        for record in dependencies
        if isinstance(record, Mapping) and record.get("path") == historical_path
    ]
    input_matches = [
        record
        for record in inputs
        if isinstance(record, Mapping) and record.get("path") == historical_path
    ]
    exact_dependency = any(
        dict(record) == dlp.HISTORICAL_RUNTIME_VALIDATOR_RECORD
        for record in dependency_matches
    )
    exact_input = any(
        dict(record) == dlp.HISTORICAL_RUNTIME_VALIDATOR_RECORD
        for record in input_matches
    )
    effective_seed_identity = (
        authorization is not None
        and manifest.get("manifest_version") == "closure_anfis_seed_manifest_v1"
        and manifest.get("base_seed") == AUTHORIZED_BASE_SEED
    )
    if not effective_seed_identity and not exact_dependency and not exact_input:
        return None
    _require_effective_context_authorization(authorization)
    if (
        len(dependency_matches) != 1
        or len(input_matches) != 1
        or dict(dependency_matches[0]) != dlp.HISTORICAL_RUNTIME_VALIDATOR_RECORD
        or dict(input_matches[0]) != dlp.HISTORICAL_RUNTIME_VALIDATOR_RECORD
    ):
        raise P1SequenceHistoricalAnfisPatchError(
            "Seed-1729 historical runtime-validator record is not unique and exact"
        )
    script = manifest.get("script")
    fitter_path = str(dlp.HISTORICAL_ANFIS_FITTER_FILE["path"])
    fitter_dependencies = [
        record
        for record in dependencies
        if isinstance(record, Mapping) and record.get("path") == fitter_path
    ]
    fitter_inputs = [
        record
        for record in inputs
        if isinstance(record, Mapping) and record.get("path") == fitter_path
    ]
    if (
        not isinstance(script, Mapping)
        or dict(script) != dlp.HISTORICAL_ANFIS_SCRIPT_RECORD
        or len(fitter_dependencies) != 1
        or dict(fitter_dependencies[0]) != dlp.HISTORICAL_ANFIS_DEPENDENCY_RECORD
        or fitter_inputs
    ):
        raise P1SequenceHistoricalAnfisPatchError(
            "Seed-1729 historical fitter provenance is not unique and exact"
        )
    canonical = _canonical_json(manifest)
    expected_bytes, expected_sha256 = dlp.EXPECTED_SEED_FINALS[
        dlp.SEED_MANIFEST_PATH.as_posix()
    ]
    if (
        manifest.get("manifest_version") != "closure_anfis_seed_manifest_v1"
        or manifest.get("base_seed") != AUTHORIZED_BASE_SEED
        or len(canonical) != expected_bytes
        or _sha256_bytes(canonical) != expected_sha256
    ):
        raise P1SequenceHistoricalAnfisPatchError(
            "Historical compatibility is restricted to the frozen seed-1729 manifest"
        )
    physical_manifest = _load_regular_json(
        dlp.SEED_MANIFEST_PATH,
        context="historical seed-1729 manifest",
    )
    if dict(manifest) != physical_manifest:
        raise P1SequenceHistoricalAnfisPatchError(
            "Seed-1729 consumer payload differs from its frozen physical manifest"
        )
    authorization_payload = manifest.get("authorization")
    if not isinstance(authorization_payload, Mapping) or (
        authorization_payload.get("lock_sha256") != dlp.EXPECTED_BASE_LOCK_SHA256
        or authorization_payload.get("execution_head") != dlp.EXPECTED_BASE_LOCK_COMMIT
        or authorization_payload.get("published_ref") != dlp.EXPECTED_PUBLISHED_REF
        or authorization_payload.get("published_head") != dlp.EXPECTED_BASE_LOCK_COMMIT
        or authorization_payload.get("remote_main_oid") != dlp.EXPECTED_BASE_LOCK_COMMIT
        or authorization_payload.get("development_fit_authorized") is not True
        or authorization_payload.get("evaluation_authorized") is not False
        or authorization_payload.get("e0_u_authorized") is not False
        or authorization_payload.get("future_outcomes_accessed") is not False
    ):
        raise P1SequenceHistoricalAnfisPatchError(
            "Seed-1729 historical consumer authorization drifted"
        )
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    authority = _reconstruct_historical_e0_dlp_authority(
        execution_head=execution_head,
        require_physical_artifacts=True,
    )
    expected_manifest = {
        "path": dlp.SEED_MANIFEST_PATH.as_posix(),
        "role": "seed_1729_completion_manifest",
        "bytes": expected_bytes,
        "sha256": expected_sha256,
    }
    if authority.get("adopted_seed_manifest") != expected_manifest:
        raise P1SequenceHistoricalAnfisPatchError(
            "Historical E0-DLP does not adopt the exact seed-1729 manifest"
        )
    for record, context in (
        (dlp.HISTORICAL_RUNTIME_VALIDATOR_RECORD, "runtime validator"),
        (dlp.HISTORICAL_ANFIS_DEPENDENCY_RECORD, "ANFIS fitter"),
    ):
        expected = _git_record(
            dlp.EXPECTED_BASE_LOCK_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        )
        if expected != record:
            raise P1SequenceHistoricalAnfisPatchError(
                f"Historical seed-1729 {context} Git record drifted"
            )
    return {
        "manifest_path": dlp.SEED_MANIFEST_PATH.as_posix(),
        "manifest_bytes": expected_bytes,
        "manifest_sha256": expected_sha256,
        "historical_source_records": {
            "generating_script": dict(dlp.HISTORICAL_ANFIS_SCRIPT_RECORD),
            "strict_anfis_state_adapter": dict(
                dlp.HISTORICAL_ANFIS_DEPENDENCY_RECORD
            ),
            "runtime_lock_validator": dict(
                dlp.HISTORICAL_RUNTIME_VALIDATOR_RECORD
            ),
        },
        "historical_uppercase_artifact_paths": True,
        "patch_lock_path": dlp.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "base_seed": AUTHORIZED_BASE_SEED,
        "compatibility_fallback": False,
        "historical_authority_gate": PATCH_GATE,
        "e0_dlp_historical_authority_verified": True,
        "effective_dlp_loader_called": False,
    }


__all__ = [
    "DEFAULT_PATCH_LOCK_PATH",
    "DEFAULT_PATCH_MANIFEST_PATH",
    "DEFAULT_PATCH_LOCK_SCHEMA",
    "P1SequenceHistoricalAnfisPatchError",
    "build_p1_sequence_historical_anfis_patch_lock_payload",
    "collect_p1_sequence_historical_anfis_patch_prelock_state",
    "historical_seed_1729_anfis_context",
    "load_and_validate_p1_sequence_historical_anfis_patch_lock",
    "load_published_p1_sequence_historical_anfis_patch_historical_authority",
    "require_p1_sequence_historical_anfis_authorized",
    "validate_p1_sequence_historical_anfis_patch_lock_payload",
]
