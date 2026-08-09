#!/usr/bin/env python
"""Adopt the published A0/1729 light reports under fail-closed E0-MX.

E0-MX is an additive governance overlay over the published H-E0-MW source
commit and the intervening, exact five-file A0 light-output publication.  It
does not rewrite any A0 artifact, does not treat the unpublished P-E0-MW plan
as authority, and preserves the historical E0-MU manifest/source binding.
No public writer accepts caller-supplied payloads or verification evidence.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments import closure_anfis_ablation_model_publication_patch as mw
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = mw.PROJECT_ROOT
mt = mw.mt

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/anfis_ablation_model_publication_adoption_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/anfis_ablation_model_publication_adoption_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "anfis_ablation_model_publication_adoption_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_anfis_ablation_model_publication_adoption_patch/lock_bundle.guard"
)
LOCKER_PATH = Path(
    "src/experiments/lock_closure_anfis_ablation_model_publication_adoption_patch.py"
)

H_MW_HEAD = "68107147c1a67c30ecfa64c862dd39531e574a9a"
H_MW_PARENT = "455f593fc276dc0b74565e34aea4a09342badb30"
ADOPTED_LIGHT_COMMIT = "5b24549f2d4791f6500e661f9ee404c0dc7a0866"
ADOPTED_LIGHT_PARENT = H_MW_HEAD
BASE_COMMIT = ADOPTED_LIGHT_COMMIT
PATCH_GATE = "E0-MX"
SCHEMA_VERSION = "closure_anfis_ablation_model_publication_adoption_patch_lock_v1"
COMPANION_VERSION = (
    "closure_anfis_ablation_model_publication_adoption_patch_lock_manifest_v1"
)
EXPECTED_COMPANION_INPUT_COUNT = 87
EXPECTED_HISTORICAL_INPUT_COUNT = 11

BLOCKED_P_MV_LOCK_PATH = (
    "reports/closure_v1/00_protocol/"
    "anfis_ablation_model_manifest_patch_lock.json"
)
BLOCKED_P_MV_COMPANION_PATH = (
    "reports/closure_v1/00_protocol/"
    "anfis_ablation_model_manifest_patch_lock_manifest.json"
)
BLOCKED_P_MV_LOCK_BYTES = 28_403
BLOCKED_P_MV_LOCK_SHA256 = (
    "0704ad83b0cf9c4f2de17c948e32eec889c435164268f815b9a99b05c6fd2b07"
)
BLOCKED_P_MV_COMPANION_BYTES = 17_033
BLOCKED_P_MV_COMPANION_SHA256 = (
    "25fbd11373d420db3127718c6808f57c2e96d05630371956035d69d0ac3d2966"
)
BLOCKED_P_MV_REPORT_PATH = "tmp/pre_commit_artifacts_20260808T195750Z.md"
BLOCKED_P_MV_REPORT_BYTES = 7_451
BLOCKED_P_MV_REPORT_SHA256 = (
    "3146b15569758cd4048e2f649147a0ff90c25b1d9b9d67e905f5fe51b2b4ab77"
)
BLOCKED_P_MV_ARCHIVE = "tmp/p_e0_mv_blocked_20260808T195750Z"

SUPERSEDED_P_MW_LOCK_PATH = mw.DEFAULT_PATCH_LOCK_PATH.as_posix()
SUPERSEDED_P_MW_COMPANION_PATH = mw.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix()

SUPERSEDED_MW_PATHS = (
    "src/data/prepare_commit_artifacts.py",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py",
    "src/experiments/train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
    "tests/test_train_closure_anfis_ablation.py",
)
PRESERVED_MW_PATHS = tuple(
    path for path in mw.PATCH_PATHS if path not in set(SUPERSEDED_MW_PATHS)
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): (
        "anfis_ablation_model_publication_adoption_patch_lock_schema"
    ),
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_ADOPTION_PATCH_1.md": (
        "anfis_ablation_model_publication_adoption_patch_protocol"
    ),
    "src/data/prepare_commit_artifacts.py": (
        "publication_adoption_patch_deferred_dvc_precommit_assistant"
    ),
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": (
        "publication_adoption_patch_anfis_ablation_model_bundle_auditor"
    ),
    "src/experiments/closure_anfis_ablation_model_publication_adoption_patch.py": (
        "anfis_ablation_model_publication_adoption_patch_validator"
    ),
    LOCKER_PATH.as_posix(): "anfis_ablation_model_publication_adoption_patch_locker",
    "src/experiments/train_closure_anfis_ablation.py": (
        "publication_adoption_patch_anfis_ablation_trainer"
    ),
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": (
        "publication_adoption_patch_anfis_ablation_model_bundle_auditor_tests"
    ),
    "tests/test_closure_anfis_ablation_model_publication_patch.py": (
        "publication_adoption_patch_superseded_mw_regression_tests"
    ),
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py": (
        "anfis_ablation_model_publication_adoption_patch_tests"
    ),
    "tests/test_train_closure_anfis_ablation.py": (
        "publication_adoption_patch_anfis_ablation_trainer_tests"
    ),
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_ADDED_PATHS = tuple(
    path for path in PATCH_PATHS if path not in set(SUPERSEDED_MW_PATHS)
)
PATCH_COMPONENT_GIT_MODES = {
    path: "100755" if path == "src/data/prepare_commit_artifacts.py" else "100644"
    for path in PATCH_PATHS
}

REGISTERED_SEEDS = mw.REGISTERED_SEEDS
ORDERED_SLOTS = mw.ORDERED_SLOTS
E0_M_PATHS = mw.E0_M_PATHS
OUTCOME_ACCESS_LOG = mw.OUTCOME_ACCESS_LOG
EMPTY_SHA256 = mw.EMPTY_SHA256
SHA1_RE = mw.SHA1_RE
SHA256_RE = mw.SHA256_RE
HISTORICAL_A0_AUTHORITY = mw.HISTORICAL_A0_AUTHORITY
HISTORICAL_A0_FINAL_RECORDS = mw.HISTORICAL_A0_FINAL_RECORDS
HISTORICAL_A0_LIGHT_PATHS = mw.HISTORICAL_A0_LIGHT_PATHS
LIGHT_SLOT_OUTPUT_NAMES = mw.LIGHT_SLOT_OUTPUT_NAMES

TYPE_CHECK_COMMAND = mw.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    ".venv/bin/python",
    "-m",
    "pytest",
    "-q",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
    "tests/test_train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
)
# Frozen from the exact four-file H-E0-MX focused collection.
FOCUSED_TEST_COUNT = 89
POETRY_CHECK_COMMAND = mw.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mw.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mw.DIFF_CHECK_COMMAND
FOCUSED_PYTEST_ENVIRONMENT = dict(mw.FOCUSED_PYTEST_ENVIRONMENT)
FOCUSED_SUMMARY_RE = re.compile(
    r"^(?P<count>[1-9][0-9]*) passed in (?P<seconds>[0-9]+\.[0-9]{2})s"
    r"(?: \((?P<clock>(?:[0-9]+ days?, )?[0-9]+:[0-9]{2}:[0-9]{2})\))?$"
)
FORBIDDEN_FOCUSED_SUMMARY_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed|errors?|failed)\b",
    flags=re.IGNORECASE,
)

UNPUBLISHED_AUTHORIZATIONS = dict(mw.UNPUBLISHED_AUTHORIZATIONS)
LOCK_SEALS = {
    "historical_a0_bundle_preserved": True,
    "historical_a0_bundle_rewrite_forbidden": True,
    "historical_mu_authority_preserved": True,
    "published_h_mv_preserved": True,
    "published_h_mw_preserved": True,
    "adopted_light_commit_preserved": True,
    "adopted_light_outputs_rewrite_forbidden": True,
    "p_mw_superseded_unmaterialized": True,
    "blocked_p_mv_rejected_as_authority": True,
    "blocked_p_mv_not_required": True,
    "model_manifest_dialect": "pretty_indent_2_insertion_order_newline",
    "completion_marker_written_last": True,
    "compact_sorted_manifest_dialect_rejected": True,
    "next_slot": {"model_id": "A1", "base_seed": 1729},
    "target_access_end": "2020-12",
    "calibration_2021_closed": True,
    "holdout_and_post_2021_closed": True,
    "ten_slots_individual_only": True,
    "dvc_absent": True,
    "outcomes_absent": True,
    "historical_inputs_compared_to_current_paths": False,
}


class AnfisAblationModelPublicationAdoptionPatchError(RuntimeError):
    """Raised when the additive E0-MX authority is not exact."""


def _translate(exc: BaseException) -> AnfisAblationModelPublicationAdoptionPatchError:
    return AnfisAblationModelPublicationAdoptionPatchError(str(exc))


def _root(repo_root: Path | None) -> Path:
    return mw._root(repo_root)


def _canonical_json(value: Any) -> bytes:
    return mw._canonical_json(value)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest_records(records: Sequence[Mapping[str, Any]]) -> str:
    return mw._digest_records(records)


def _exact_equal(left: Any, right: Any) -> bool:
    return mw._exact_equal(left, right)


def _file_record(
    path: Path, *, role: str, repo_root: Path
) -> dict[str, Any]:
    try:
        return mw._file_record(path, role=role, repo_root=repo_root)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _plain_git_blob_record(
    repo_root: Path, commit: str, path: str, *, role: str
) -> dict[str, Any]:
    try:
        return mw._plain_git_blob_record(repo_root, commit, path, role=role)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _historical_git_blob_record(
    repo_root: Path, commit: str, path: str, *, role: str
) -> dict[str, Any]:
    try:
        return mw._historical_git_blob_record(repo_root, commit, path, role=role)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _git(repo_root: Path, *arguments: str) -> str:
    try:
        return mw._git(repo_root, *arguments)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _git_head(repo_root: Path, ref: str = "HEAD") -> str:
    try:
        return mw._git_head(repo_root, ref)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _single_parent(repo_root: Path, commit: str, *, context: str) -> str:
    try:
        return mw._single_parent(repo_root, commit, context=context)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _git_scope(repo_root: Path, parent: str, head: str) -> dict[str, Any]:
    try:
        return mw._git_scope(repo_root, parent, head)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _require_exact_git_modes(
    repo_root: Path,
    commit: str,
    expected: Mapping[str, str],
    *,
    context: str,
) -> None:
    try:
        mw._require_exact_git_modes(repo_root, commit, expected, context=context)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _require_git_modes(
    repo_root: Path, commit: str, paths: Sequence[str], *, context: str
) -> None:
    try:
        mw._require_git_modes(repo_root, commit, paths, context=context)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _live_remote_main_head(repo_root: Path) -> str:
    try:
        return mw._live_remote_main_head(repo_root)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _read_regular_bytes(path: Path, *, repo_root: Path) -> bytes:
    try:
        return mw._read_regular_bytes(path, repo_root=repo_root)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _load_json(path: Path, *, repo_root: Path) -> dict[str, Any]:
    try:
        return mw._load_json(path, repo_root=repo_root)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _strict_json(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        return mw._strict_json(payload, label=label)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _lexists(path: Path) -> bool:
    return mw._lexists(path)


def _temporary_path(path: Path) -> Path:
    return mt._temporary_path(path)


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX lock timestamp must be a string"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX lock timestamp is malformed"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX lock timestamp must include a timezone"
        )


def _blocked_p_mv_attempt() -> dict[str, Any]:
    """Return immutable incident metadata; no archived file is read."""
    return {
        "gate": "E0-MV",
        "status": "blocked_unpublished_precommit_failed",
        "lock": {
            "path": BLOCKED_P_MV_LOCK_PATH,
            "bytes": BLOCKED_P_MV_LOCK_BYTES,
            "sha256": BLOCKED_P_MV_LOCK_SHA256,
        },
        "companion": {
            "path": BLOCKED_P_MV_COMPANION_PATH,
            "bytes": BLOCKED_P_MV_COMPANION_BYTES,
            "sha256": BLOCKED_P_MV_COMPANION_SHA256,
        },
        "precommit_report": {
            "path": BLOCKED_P_MV_REPORT_PATH,
            "bytes": BLOCKED_P_MV_REPORT_BYTES,
            "sha256": BLOCKED_P_MV_REPORT_SHA256,
        },
        "failure_classification": "generic_experiment_manifest_filename_classifier",
        "published": False,
        "authoritative": False,
        "physical_input": False,
        "historical_input": False,
        "retry_forbidden": True,
        "local_archive": BLOCKED_P_MV_ARCHIVE,
        "archive_required_for_effective_authority": False,
    }


def _superseded_p_mw_plan(repo_root: Path) -> dict[str, Any]:
    """Describe the observable unpublished MW plan without inventing an attempt."""
    lock_absent = not _lexists(repo_root / mw.DEFAULT_PATCH_LOCK_PATH)
    companion_absent = not _lexists(
        repo_root / mw.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    )
    introduced = {
        path: bool(_git(repo_root, "log", "--all", "--format=%H", "--", path))
        for path in (
            SUPERSEDED_P_MW_LOCK_PATH,
            SUPERSEDED_P_MW_COMPANION_PATH,
        )
    }
    if not lock_absent or not companion_absent or any(introduced.values()):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "P-E0-MW is not an absent, unpublished plan"
        )
    return {
        "gate": "E0-MW",
        "status": "superseded_unmaterialized",
        "h_head": H_MW_HEAD,
        "intervening_commit": ADOPTED_LIGHT_COMMIT,
        "lock_path": SUPERSEDED_P_MW_LOCK_PATH,
        "companion_path": SUPERSEDED_P_MW_COMPANION_PATH,
        "public_paths_absent": True,
        "introduced_in_git": False,
        "published": False,
        "authoritative": False,
        "physical_input": False,
        "historical_input": False,
        "retry_forbidden": True,
        "local_attempt_metadata_required": False,
    }


def _adopted_light_records() -> list[dict[str, Any]]:
    return sorted(
        (
            dict(record)
            for record in HISTORICAL_A0_FINAL_RECORDS
            if str(record["path"]) in set(HISTORICAL_A0_LIGHT_PATHS)
        ),
        key=lambda record: str(record["path"]),
    )


AdoptedA0PhysicalSnapshot = tuple[
    tuple[str, int, int, int, int, int, int, int, str], ...
]


def _adopted_a0_physical_snapshot(
    repo_root: Path,
) -> AdoptedA0PhysicalSnapshot:
    """Bind exact8 path/dev/inode/mode/link/time/size/hash observations."""
    snapshot: list[tuple[str, int, int, int, int, int, int, int, str]] = []
    for expected in HISTORICAL_A0_FINAL_RECORDS:
        relative = str(expected["path"])
        path = repo_root / relative
        try:
            metadata = path.lstat()
        except FileNotFoundError as exc:
            raise AnfisAblationModelPublicationAdoptionPatchError(
                f"Adopted A0 final is absent: {relative}"
            ) from exc
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o644
            or metadata.st_nlink != 1
        ):
            raise AnfisAblationModelPublicationAdoptionPatchError(
                f"Adopted A0 final must be regular 0644 with one hard link: {relative}"
            )
        observed = _file_record(
            Path(relative), role=str(expected["role"]), repo_root=repo_root
        )
        if observed != expected:
            raise AnfisAblationModelPublicationAdoptionPatchError(
                f"Adopted A0 final bytes drifted: {relative}"
            )
        snapshot.append(
            (
                relative,
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_mode,
                metadata.st_nlink,
                metadata.st_mtime_ns,
                metadata.st_ctime_ns,
                metadata.st_size,
                str(observed["sha256"]),
            )
        )
    return tuple(snapshot)


def _require_adopted_a0_snapshot(
    expected: AdoptedA0PhysicalSnapshot,
    *,
    repo_root: Path,
    context: str,
) -> None:
    if _adopted_a0_physical_snapshot(repo_root) != expected:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX adopted A0 physical identity drifted {context}"
        )


def _adopted_light_publication(repo_root: Path) -> dict[str, Any]:
    _adopted_a0_physical_snapshot(repo_root)
    expected_records = _adopted_light_records()
    expected_paths = [str(record["path"]) for record in expected_records]
    expected_scope = {
        "added": 5,
        "modified": 0,
        "deleted": 0,
        "paths": expected_paths,
    }
    if (
        _single_parent(
            repo_root, ADOPTED_LIGHT_COMMIT, context="adopted A0 light commit"
        )
        != ADOPTED_LIGHT_PARENT
        or _git_scope(repo_root, ADOPTED_LIGHT_PARENT, ADOPTED_LIGHT_COMMIT)
        != expected_scope
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "Adopted A0 light commit topology or exact five-addition scope drifted"
        )
    _require_exact_git_modes(
        repo_root,
        ADOPTED_LIGHT_COMMIT,
        {path: "100644" for path in expected_paths},
        context="adopted A0 light commit",
    )
    git_records = [
        _plain_git_blob_record(
            repo_root,
            ADOPTED_LIGHT_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        )
        for record in expected_records
    ]
    physical_records = [
        _file_record(
            Path(str(record["path"])),
            role=str(record["role"]),
            repo_root=repo_root,
        )
        for record in expected_records
    ]
    if git_records != expected_records or physical_records != expected_records:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "Adopted A0 light outputs differ from frozen A0 records"
        )
    return {
        "commit": ADOPTED_LIGHT_COMMIT,
        "parent": ADOPTED_LIGHT_PARENT,
        "status": "published_adopted",
        "scope": {"added": 5, "modified": 0, "deleted": 0},
        "component_count": 5,
        "components": expected_records,
        "components_sha256": _digest_records(expected_records),
        "components_git_mode": "100644",
        "matches_historical_a0_light_subset": True,
        "git_blob_verified": True,
        "physical_bytes_verified": True,
        "scientific_slot_authority_changed": False,
        "historical_manifest_rewritten": False,
        "rewrite_forbidden": True,
        "companion_physical_inputs": True,
    }


def _h_mw_component_records(repo_root: Path) -> list[dict[str, Any]]:
    return [
        _plain_git_blob_record(repo_root, H_MW_HEAD, path, role=role)
        for path, role in sorted(mw.PATCH_COMPONENT_ROLES.items())
    ]


def _partition_h_mw_components(
    records: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_path = {str(record.get("path")): dict(record) for record in records}
    if set(by_path) != set(mw.PATCH_PATHS) or len(by_path) != len(records):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "Published H-E0-MW components differ from the closed partition"
        )
    preserved = [by_path[path] for path in sorted(PRESERVED_MW_PATHS)]
    superseded = [by_path[path] for path in sorted(SUPERSEDED_MW_PATHS)]
    if len(preserved) != 4 or len(superseded) != 6:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "Published H-E0-MW must partition as four preserved plus six superseded"
        )
    return preserved, superseded


def _base_mw_authority(repo_root: Path) -> dict[str, Any]:
    expected_scope = {
        "added": 5,
        "modified": 5,
        "deleted": 0,
        "paths": list(mw.PATCH_PATHS),
    }
    if (
        _single_parent(repo_root, H_MW_HEAD, context="H-E0-MW") != H_MW_PARENT
        or _git_scope(repo_root, H_MW_PARENT, H_MW_HEAD) != expected_scope
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "Published H-E0-MW topology drifted"
        )
    _require_exact_git_modes(
        repo_root,
        H_MW_HEAD,
        mw.PATCH_COMPONENT_GIT_MODES,
        context="H-E0-MW",
    )
    components = _h_mw_component_records(repo_root)
    preserved, superseded = _partition_h_mw_components(components)
    for record in preserved:
        physical = _file_record(
            Path(str(record["path"])), role=str(record["role"]), repo_root=repo_root
        )
        if physical != record:
            raise AnfisAblationModelPublicationAdoptionPatchError(
                f"Preserved H-E0-MW component drifted: {record['path']}"
            )
    try:
        base_mv_authority = mw._base_mv_authority(repo_root)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc
    return {
        "h_head": H_MW_HEAD,
        "h_parent": H_MW_PARENT,
        "h_scope": {"added": 5, "modified": 5, "deleted": 0},
        "component_count": 10,
        "components": components,
        "components_sha256": _digest_records(components),
        "preserved_component_count": 4,
        "preserved_components": preserved,
        "preserved_components_sha256": _digest_records(preserved),
        "superseded_component_count": 6,
        "superseded_components": superseded,
        "superseded_components_sha256": _digest_records(superseded),
        "base_mv_authority": base_mv_authority,
        "p_mw_publication_status": "superseded_unmaterialized",
        "p_mw_is_authority": False,
    }


def _h_mx_components(head: str, repo_root: Path) -> list[dict[str, Any]]:
    physical = [
        _file_record(Path(path), role=role, repo_root=repo_root)
        for path, role in sorted(PATCH_COMPONENT_ROLES.items())
    ]
    expected = [
        _plain_git_blob_record(repo_root, head, path, role=role)
        for path, role in sorted(PATCH_COMPONENT_ROLES.items())
    ]
    if physical != expected:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX H components differ from their Git blobs"
        )
    return physical


def _historical_mw_inputs(repo_root: Path) -> list[dict[str, Any]]:
    direct_records = [
        _historical_git_blob_record(
            repo_root,
            H_MW_HEAD,
            path,
            role=f"superseded_mw_{mw.PATCH_COMPONENT_ROLES[path]}",
        )
        for path in sorted(SUPERSEDED_MW_PATHS)
    ]
    try:
        inherited_records = [dict(record) for record in mw._historical_mv_inputs(repo_root)]
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc
    records = [*inherited_records, *direct_records]
    records.sort(
        key=lambda record: (
            str(record.get("path")),
            str(record.get("commit")),
            str(record.get("role")),
        )
    )
    identities = {
        (record.get("path"), record.get("commit"), record.get("role"))
        for record in records
    }
    if len(records) != EXPECTED_HISTORICAL_INPUT_COUNT:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX historical input count drifted"
        )
    if len(identities) != EXPECTED_HISTORICAL_INPUT_COUNT:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX historical (path, commit, role) identities are not unique"
        )
    return records


def _companion_physical_inputs(
    *,
    h_components: Sequence[Mapping[str, Any]],
    base_authority: Mapping[str, Any],
) -> list[dict[str, Any]]:
    base_mv = base_authority.get("base_mv_authority")
    preserved_mw = base_authority.get("preserved_components")
    if not isinstance(base_mv, Mapping) or not isinstance(preserved_mw, list):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX companion source authority is absent"
        )
    p_mu = base_mv.get("p_mu_authority")
    preserved_mv = base_mv.get("preserved_components")
    if not isinstance(p_mu, Mapping) or not isinstance(preserved_mv, list):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX nested MV/MU companion authority is absent"
        )
    preserved_mu = p_mu.get("preserved_physical_inputs")
    p_mu_components = p_mu.get("p_components")
    if not isinstance(preserved_mu, list) or not isinstance(p_mu_components, list):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX P-E0-MU physical records are absent"
        )
    records = [
        *(dict(record) for record in preserved_mu),
        *(dict(record) for record in p_mu_components),
        *(dict(record) for record in preserved_mv),
        *(dict(record) for record in preserved_mw),
        *(
            {
                **dict(record),
                "role": f"adopted_a0_light_{record['role']}",
            }
            for record in _adopted_light_records()
        ),
        *(dict(record) for record in h_components),
    ]
    records.sort(key=lambda record: str(record.get("path")))
    paths = [str(record.get("path")) for record in records]
    blocked_paths = {
        BLOCKED_P_MV_LOCK_PATH,
        BLOCKED_P_MV_COMPANION_PATH,
        SUPERSEDED_P_MW_LOCK_PATH,
        SUPERSEDED_P_MW_COMPANION_PATH,
    }
    if (
        len(records) != EXPECTED_COMPANION_INPUT_COUNT
        or len(set(paths)) != EXPECTED_COMPANION_INPUT_COUNT
        or blocked_paths.intersection(paths)
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX companion must bind 87 unique physical inputs without P-MV/P-MW"
        )
    return records


def _expected_manifest_dialect() -> dict[str, Any]:
    return mw._expected_manifest_dialect()


def _control_namespace_state(repo_root: Path) -> dict[str, bool]:
    return {
        "mx_lock_absent": not _lexists(repo_root / DEFAULT_PATCH_LOCK_PATH),
        "mx_companion_absent": not _lexists(
            repo_root / DEFAULT_PATCH_LOCK_MANIFEST_PATH
        ),
        "mx_lock_temp_absent": not _lexists(
            repo_root / _temporary_path(DEFAULT_PATCH_LOCK_PATH)
        ),
        "mx_companion_temp_absent": not _lexists(
            repo_root / _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        ),
        "mx_locker_guard_absent": not _lexists(repo_root / LOCKER_GUARD_PATH),
        "blocked_mv_lock_absent": not _lexists(repo_root / Path(BLOCKED_P_MV_LOCK_PATH)),
        "blocked_mv_companion_absent": not _lexists(
            repo_root / Path(BLOCKED_P_MV_COMPANION_PATH)
        ),
        "superseded_mw_lock_absent": not _lexists(
            repo_root / mw.DEFAULT_PATCH_LOCK_PATH
        ),
        "superseded_mw_companion_absent": not _lexists(
            repo_root / mw.DEFAULT_PATCH_LOCK_MANIFEST_PATH
        ),
        "p_mu_lock_present": _lexists(
            repo_root / mw.mv.mu.DEFAULT_PATCH_LOCK_PATH
        ),
        "p_mu_companion_present": _lexists(
            repo_root / mw.mv.mu.DEFAULT_PATCH_LOCK_MANIFEST_PATH
        ),
    }


def _prohibited_namespace_state(repo_root: Path) -> dict[str, bool]:
    return {
        "e0_m_paths_absent": not any(
            _lexists(repo_root / path) for path in E0_M_PATHS
        ),
        "outcome_access_log_absent": not _lexists(repo_root / OUTCOME_ACCESS_LOG),
    }


def preflight_anfis_ablation_model_publication_adoption_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    encoded = _canonical_json(schema)
    forbidden = {"minimum", "maximum", "format", "minLength", "maxLength"}
    observed: set[str] = set()
    numeric_const_issues: list[str] = []

    def walk(value: Any, *, path: str = "$") -> None:
        if isinstance(value, Mapping):
            observed.update(str(key) for key in value)
            if "const" in value:
                constant = value["const"]
                if type(constant) in {int, float} and (
                    type(constant) is not int or value.get("type") != "integer"
                ):
                    numeric_const_issues.append(path)
            for key, child in value.items():
                walk(child, path=f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, path=f"{path}[{index}]")

    walk(schema)
    unsupported = sorted(forbidden.intersection(observed))
    if unsupported or numeric_const_issues:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX schema exceeds the supported validator subset"
        )
    return {
        "schema_path": DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
        "canonical_schema_bytes": len(encoded),
        "canonical_schema_sha256": _sha256_bytes(encoded),
        "supported_subset_verified": True,
        "unsupported_semantic_keywords": [],
    }


def collect_anfis_ablation_model_publication_adoption_patch_prelock_state(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    preflight_anfis_ablation_model_publication_adoption_patch_schema(repo_root=root)
    head = _git_head(root)
    expected_scope = {
        "added": 5,
        "modified": 6,
        "deleted": 0,
        "paths": list(PATCH_PATHS),
    }
    if (
        _single_parent(root, head, context="H-E0-MX") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, head) != expected_scope
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "H-E0-MX must be the exact 6M+5A child of adopted light commit"
        )
    _require_exact_git_modes(
        root, head, PATCH_COMPONENT_GIT_MODES, context="H-E0-MX"
    )
    branch = _git(root, "branch", "--show-current").strip()
    tracking = _git_head(root, "origin/main")
    remote = _live_remote_main_head(root) if verify_remote else tracking
    if branch != "main" or tracking != head or remote != head:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "H-E0-MX refs are not aligned with main"
        )
    status_lines = [
        line
        for line in _git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
        if line
    ]
    if status_lines:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX prelock worktree scope drifted: {status_lines}"
        )

    h_components = _h_mx_components(head, root)
    base_authority = _base_mw_authority(root)
    adopted_light = _adopted_light_publication(root)
    superseded_p_mw = _superseded_p_mw_plan(root)
    historical_inputs = _historical_mw_inputs(root)
    physical_inputs = _companion_physical_inputs(
        h_components=h_components, base_authority=base_authority
    )
    try:
        adopted_a0 = mw.mv._historical_a0_bundle(root)
        namespace = mw.mv._training_namespace_state(root)
    except mw.mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc
    controls = _control_namespace_state(root)
    prohibited = _prohibited_namespace_state(root)
    if not all(controls.values()) or not all(prohibited.values()):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX control or scientific boundary namespace drifted"
        )
    return {
        "repository": {
            "branch": branch,
            "head": head,
            "parent": BASE_COMMIT,
            "tracking_head": tracking,
            "remote_head": remote,
            "remote_verification_mode": (
                "live_remote_main_verified" if verify_remote else "tracking_ref_only"
            ),
            "worktree_scope": "clean_with_adopted_light_outputs_tracked",
        },
        "h_patch": {
            "base_commit": BASE_COMMIT,
            "head": head,
            "parent": BASE_COMMIT,
            "component_count": 11,
            "components": h_components,
            "components_sha256": _digest_records(h_components),
            "components_git_modes": dict(PATCH_COMPONENT_GIT_MODES),
            "scope": {"added": 5, "modified": 6, "deleted": 0},
        },
        "base_mw_authority": base_authority,
        "blocked_p_mv_attempt": _blocked_p_mv_attempt(),
        "superseded_p_mw_plan": superseded_p_mw,
        "adopted_light_publication": adopted_light,
        "adopted_a0_bundle": adopted_a0,
        "manifest_dialect": _expected_manifest_dialect(),
        "companion_contract": {
            "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
            "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
            "output_count": 1,
            "script_path": LOCKER_PATH.as_posix(),
            "physical_inputs_sha256": _digest_records(physical_inputs),
            "historical_inputs_sha256": _digest_records(historical_inputs),
            "blocked_p_mv_in_inputs": False,
            "superseded_p_mw_in_inputs": False,
            "adopted_a0_light_outputs_in_inputs": True,
            "manifest_written_last": True,
        },
        "prelock": {
            **namespace,
            "historical_a0_finals_sha256": adopted_a0["finals_sha256"],
            "adopted_light_components_sha256": adopted_light[
                "components_sha256"
            ],
            "control_paths": controls,
            "prohibited_namespaces": prohibited,
        },
    }


def build_anfis_ablation_model_publication_adoption_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    required = {
        "repository",
        "h_patch",
        "base_mw_authority",
        "blocked_p_mv_attempt",
        "superseded_p_mw_plan",
        "adopted_light_publication",
        "adopted_a0_bundle",
        "manifest_dialect",
        "companion_contract",
        "prelock",
    }
    if set(prelock) != required:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX prelock bundle dialect drifted"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "locked_unpublished",
        "gate": PATCH_GATE,
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
        "repository": dict(cast(Mapping[str, Any], prelock["repository"])),
        "h_patch": dict(cast(Mapping[str, Any], prelock["h_patch"])),
        "base_mw_authority": dict(
            cast(Mapping[str, Any], prelock["base_mw_authority"])
        ),
        "blocked_p_mv_attempt": dict(
            cast(Mapping[str, Any], prelock["blocked_p_mv_attempt"])
        ),
        "superseded_p_mw_plan": dict(
            cast(Mapping[str, Any], prelock["superseded_p_mw_plan"])
        ),
        "adopted_light_publication": dict(
            cast(Mapping[str, Any], prelock["adopted_light_publication"])
        ),
        "adopted_a0_bundle": dict(
            cast(Mapping[str, Any], prelock["adopted_a0_bundle"])
        ),
        "manifest_dialect": dict(
            cast(Mapping[str, Any], prelock["manifest_dialect"])
        ),
        "companion_contract": dict(
            cast(Mapping[str, Any], prelock["companion_contract"])
        ),
        "prelock": dict(cast(Mapping[str, Any], prelock["prelock"])),
        "verification": dict(verification),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
        "seals": dict(LOCK_SEALS),
    }


def _command_evidence(
    command: Sequence[str], stdout: str, stderr: str
) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": _sha256_bytes(stdout.encode("utf-8")),
        "stderr_sha256": _sha256_bytes(stderr.encode("utf-8")),
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": len(stderr.splitlines()),
    }


def _run_command(
    command: Sequence[str],
    *,
    repo_root: Path,
    sanitize_pytest_environment: bool = False,
) -> tuple[dict[str, Any], str, str]:
    environment = os.environ.copy()
    if sanitize_pytest_environment:
        environment.update(FOCUSED_PYTEST_ENVIRONMENT)
    result = subprocess.run(
        list(command),
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if result.returncode != 0:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"Verification command failed ({result.returncode}): "
            f"{' '.join(command)}\n{result.stdout}\n{result.stderr}"
        )
    return (
        _command_evidence(command, result.stdout, result.stderr),
        result.stdout,
        result.stderr,
    )


def _parse_focused_summary(stdout: str, stderr: str) -> dict[str, int]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    matches = [line for line in lines if FOCUSED_SUMMARY_RE.fullmatch(line)]
    match = FOCUSED_SUMMARY_RE.fullmatch(matches[0]) if len(matches) == 1 else None
    if (
        FOCUSED_TEST_COUNT <= 0
        or stderr.strip()
        or not lines
        or len(matches) != 1
        or matches[0] != lines[-1]
        or FORBIDDEN_FOCUSED_SUMMARY_RE.search(stdout + "\n" + stderr) is not None
        or match is None
        or int(match.group("count")) != FOCUSED_TEST_COUNT
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX focused pytest summary is not one closed clean result"
        )
    return {
        "test_count": FOCUSED_TEST_COUNT,
        "skipped_count": 0,
        "deselected_count": 0,
    }


def _audit_historical_a0_semantics(repo_root: Path) -> dict[str, Any]:
    try:
        return mw._audit_historical_a0_semantics(repo_root)
    except mw.AnfisAblationModelPublicationPatchError as exc:
        raise _translate(exc) from exc


def _run_anfis_ablation_model_publication_adoption_patch_verification(
    *,
    adopted_snapshot: AdoptedA0PhysicalSnapshot,
    expected_schema_preflight: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="before verification"
    )
    schema_preflight = preflight_anfis_ablation_model_publication_adoption_patch_schema(
        repo_root=root
    )
    if (
        expected_schema_preflight is not None
        and dict(expected_schema_preflight) != schema_preflight
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX schema changed before verification"
        )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after schema preflight"
    )
    full_type_check, stdout, stderr = _run_command(TYPE_CHECK_COMMAND, repo_root=root)
    if stdout != "All checks passed!\n" or stderr:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX full type-check output drifted"
        )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after full type check"
    )
    focused_tests, stdout, stderr = _run_command(
        FOCUSED_TEST_COMMAND,
        repo_root=root,
        sanitize_pytest_environment=True,
    )
    focused_tests.update(_parse_focused_summary(stdout, stderr))
    focused_tests["stdout_text"] = stdout
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after focused tests"
    )
    poetry_check, stdout, stderr = _run_command(POETRY_CHECK_COMMAND, repo_root=root)
    if stdout != "All set!\n" or stderr:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX poetry-check output drifted"
        )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after poetry check"
    )
    publication_guard, stdout, stderr = _run_command(
        PUBLICATION_GUARD_COMMAND, repo_root=root
    )
    if stdout != (
        "Checking tracked files before publication...\n"
        "OK: tracked files look publication-ready.\n"
    ) or stderr:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX publication-guard output drifted"
        )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after publication guard"
    )
    git_diff_check, stdout, stderr = _run_command(DIFF_CHECK_COMMAND, repo_root=root)
    if stdout or stderr:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX git diff-check output drifted"
        )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after git diff check"
    )
    historical_a0_semantic_audit = _audit_historical_a0_semantics(root)
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after historical A0 audit"
    )
    return {
        "schema_preflight": schema_preflight,
        "full_type_check": full_type_check,
        "focused_tests": focused_tests,
        "poetry_check": poetry_check,
        "publication_guard": publication_guard,
        "git_diff_check": git_diff_check,
        "historical_a0_semantic_audit": historical_a0_semantic_audit,
        "execution_boundaries": {
            "development_targets_through_2020_read_during_verification": True,
            "historical_a0_semantic_audit_run": True,
            "adopted_a0_regular_0644_nlink1": True,
            "adopted_a0_snapshot_unchanged": True,
            "trainer_entrypoint_run": False,
            "model_fit_or_optimization_run": False,
            "auditor_entrypoint_run": False,
            "calibration_2021_targets_read_during_verification": False,
            "holdout_or_post_2021_targets_read_during_verification": False,
            "dvc_commands_run": False,
            "scientific_network_commands_run": False,
            "future_outcomes_accessed": False,
            "pytest_environment": dict(FOCUSED_PYTEST_ENVIRONMENT),
        },
    }


def run_anfis_ablation_model_publication_adoption_patch_verification(
    *,
    expected_schema_preflight: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Run verification with a transaction-local, non-serialized exact8 baseline."""
    root = _root(repo_root)
    adopted_snapshot = _adopted_a0_physical_snapshot(root)
    return _run_anfis_ablation_model_publication_adoption_patch_verification(
        adopted_snapshot=adopted_snapshot,
        expected_schema_preflight=expected_schema_preflight,
        repo_root=root,
    )


def _validate_command_evidence(
    value: Any,
    *,
    expected_command: Sequence[str],
    context: str,
    exact_stdout: str | None = None,
) -> None:
    keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX {context} evidence dialect drifted"
        )
    if value.get("command") != list(expected_command) or value.get("returncode") != 0:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX {context} command/result drifted"
        )
    if (
        any(
            not isinstance(value.get(key), str)
            or SHA256_RE.fullmatch(str(value[key])) is None
            for key in ("stdout_sha256", "stderr_sha256")
        )
        or any(
            type(value.get(key)) is not int or int(value[key]) < 0
            for key in ("stdout_line_count", "stderr_line_count")
        )
        or value.get("stderr_sha256") != EMPTY_SHA256
        or value.get("stderr_line_count") != 0
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX {context} digest/line evidence drifted"
        )
    if exact_stdout is not None and (
        value.get("stdout_sha256") != _sha256_bytes(exact_stdout.encode("utf-8"))
        or value.get("stdout_line_count") != len(exact_stdout.splitlines())
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX {context} stdout evidence drifted"
        )


def _validate_verification(value: Any, *, repo_root: Path) -> None:
    keys = {
        "schema_preflight",
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
        "historical_a0_semantic_audit",
        "execution_boundaries",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX verification dialect drifted"
        )
    expected_preflight = preflight_anfis_ablation_model_publication_adoption_patch_schema(
        repo_root=repo_root
    )
    if not _exact_equal(value.get("schema_preflight"), expected_preflight):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX schema-preflight evidence drifted"
        )
    _validate_command_evidence(
        value.get("full_type_check"),
        expected_command=TYPE_CHECK_COMMAND,
        context="full type check",
        exact_stdout="All checks passed!\n",
    )
    focused = value.get("focused_tests")
    focused_keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
        "stdout_text",
        "test_count",
        "skipped_count",
        "deselected_count",
    }
    if not isinstance(focused, Mapping) or set(focused) != focused_keys:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX focused-test evidence dialect drifted"
        )
    base_focused = {
        key: focused[key]
        for key in focused_keys
        if key not in {"stdout_text", "test_count", "skipped_count", "deselected_count"}
    }
    _validate_command_evidence(
        base_focused,
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused tests",
    )
    stdout_text = focused.get("stdout_text")
    if not isinstance(stdout_text, str):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX focused stdout is absent"
        )
    parsed = _parse_focused_summary(stdout_text, "")
    if (
        focused.get("stdout_sha256") != _sha256_bytes(stdout_text.encode("utf-8"))
        or focused.get("stdout_line_count") != len(stdout_text.splitlines())
        or {key: focused.get(key) for key in parsed} != parsed
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX focused-test stdout binding drifted"
        )
    _validate_command_evidence(
        value.get("poetry_check"),
        expected_command=POETRY_CHECK_COMMAND,
        context="poetry check",
        exact_stdout="All set!\n",
    )
    _validate_command_evidence(
        value.get("publication_guard"),
        expected_command=PUBLICATION_GUARD_COMMAND,
        context="publication guard",
        exact_stdout=(
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n"
        ),
    )
    _validate_command_evidence(
        value.get("git_diff_check"),
        expected_command=DIFF_CHECK_COMMAND,
        context="git diff check",
        exact_stdout="",
    )
    expected_audit = {
        "status": "passed",
        "model_id": "A0",
        "base_seed": 1729,
        "input_count": 10,
        "authority_record_count": 3,
        "source_code_count": 1,
        "output_count": 7,
        "schema_exact": True,
        "hash_bindings_verified": True,
        "calibration_targets_read": False,
        "test_or_holdout_targets_read": False,
        "future_outcomes_accessed": False,
        "dvc_command_executed": False,
        "scientific_network_egress": False,
        "writes_performed": False,
    }
    if not _exact_equal(value.get("historical_a0_semantic_audit"), expected_audit):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX historical A0 semantic-audit evidence drifted"
        )
    expected_boundaries = {
        "development_targets_through_2020_read_during_verification": True,
        "historical_a0_semantic_audit_run": True,
        "adopted_a0_regular_0644_nlink1": True,
        "adopted_a0_snapshot_unchanged": True,
        "trainer_entrypoint_run": False,
        "model_fit_or_optimization_run": False,
        "auditor_entrypoint_run": False,
        "calibration_2021_targets_read_during_verification": False,
        "holdout_or_post_2021_targets_read_during_verification": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "future_outcomes_accessed": False,
        "pytest_environment": dict(FOCUSED_PYTEST_ENVIRONMENT),
    }
    if not _exact_equal(value.get("execution_boundaries"), expected_boundaries):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX verification execution boundaries drifted"
        )


def _expected_prelock() -> dict[str, Any]:
    expected = dict(mw.mv._expected_prelock())
    expected["adopted_light_components_sha256"] = _digest_records(
        _adopted_light_records()
    )
    expected["control_paths"] = {
        "mx_lock_absent": True,
        "mx_companion_absent": True,
        "mx_lock_temp_absent": True,
        "mx_companion_temp_absent": True,
        "mx_locker_guard_absent": True,
        "blocked_mv_lock_absent": True,
        "blocked_mv_companion_absent": True,
        "superseded_mw_lock_absent": True,
        "superseded_mw_companion_absent": True,
        "p_mu_lock_present": True,
        "p_mu_companion_present": True,
    }
    return expected


def validate_anfis_ablation_model_publication_adoption_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    allow_registered_pointers: bool = False,
    repo_root: Path | None = None,
) -> None:
    if type(allow_registered_pointers) is not bool:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX registered-pointer policy must be an exact boolean"
        )
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise AnfisAblationModelPublicationAdoptionPatchError(str(exc)) from exc
    _validate_timestamp(payload.get("created_at_utc"))
    if not _exact_equal(payload.get("authorizations"), UNPUBLISHED_AUTHORIZATIONS):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX unpublished authorizations drifted"
        )
    if not _exact_equal(payload.get("seals"), LOCK_SEALS):
        raise AnfisAblationModelPublicationAdoptionPatchError("E0-MX seals drifted")
    if not _exact_equal(payload.get("blocked_p_mv_attempt"), _blocked_p_mv_attempt()):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX blocked P-E0-MV incident metadata drifted"
        )
    if not _exact_equal(
        payload.get("superseded_p_mw_plan"), _superseded_p_mw_plan(root)
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX superseded P-E0-MW metadata drifted"
        )
    adopted_light = _adopted_light_publication(root)
    if not _exact_equal(payload.get("adopted_light_publication"), adopted_light):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX adopted light publication drifted"
        )
    repository = payload.get("repository")
    h_patch = payload.get("h_patch")
    if not isinstance(repository, Mapping) or not isinstance(h_patch, Mapping):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX repository/H binding is absent"
        )
    h_head = repository.get("head")
    expected_scope = {
        "added": 5,
        "modified": 6,
        "deleted": 0,
        "paths": list(PATCH_PATHS),
    }
    if (
        repository.get("branch") != "main"
        or not isinstance(h_head, str)
        or SHA1_RE.fullmatch(h_head) is None
        or repository.get("parent") != BASE_COMMIT
        or repository.get("tracking_head") != h_head
        or repository.get("remote_head") != h_head
        or repository.get("remote_verification_mode") != "live_remote_main_verified"
        or repository.get("worktree_scope")
        != "clean_with_adopted_light_outputs_tracked"
        or _single_parent(root, h_head, context="H-E0-MX") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, h_head) != expected_scope
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX repository/H topology drifted"
        )
    _require_exact_git_modes(
        root, h_head, PATCH_COMPONENT_GIT_MODES, context="H-E0-MX"
    )
    h_components = _h_mx_components(h_head, root)
    expected_h = {
        "base_commit": BASE_COMMIT,
        "head": h_head,
        "parent": BASE_COMMIT,
        "component_count": 11,
        "components": h_components,
        "components_sha256": _digest_records(h_components),
        "components_git_modes": dict(PATCH_COMPONENT_GIT_MODES),
        "scope": {"added": 5, "modified": 6, "deleted": 0},
    }
    if not _exact_equal(h_patch, expected_h):
        raise AnfisAblationModelPublicationAdoptionPatchError("E0-MX H binding drifted")
    base_authority = _base_mw_authority(root)
    if not _exact_equal(payload.get("base_mw_authority"), base_authority):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX H-E0-MW/H-E0-MV/P-E0-MU reconstruction drifted"
        )
    try:
        adopted = mw.mv._historical_a0_bundle(
            root, allow_registered_pointer=allow_registered_pointers
        )
    except mw.mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc
    if not _exact_equal(payload.get("adopted_a0_bundle"), adopted):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX adopted A0/1729 binding drifted"
        )
    if not _exact_equal(payload.get("manifest_dialect"), _expected_manifest_dialect()):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX model-manifest dialect drifted"
        )
    physical_inputs = _companion_physical_inputs(
        h_components=h_components, base_authority=base_authority
    )
    historical_inputs = _historical_mw_inputs(root)
    expected_contract = {
        "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
        "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
        "output_count": 1,
        "script_path": LOCKER_PATH.as_posix(),
        "physical_inputs_sha256": _digest_records(physical_inputs),
        "historical_inputs_sha256": _digest_records(historical_inputs),
        "blocked_p_mv_in_inputs": False,
        "superseded_p_mw_in_inputs": False,
        "adopted_a0_light_outputs_in_inputs": True,
        "manifest_written_last": True,
    }
    if not _exact_equal(payload.get("companion_contract"), expected_contract):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX companion contract drifted"
        )
    if not _exact_equal(payload.get("prelock"), _expected_prelock()):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX complete prelock binding drifted"
        )
    _validate_verification(payload.get("verification"), repo_root=root)


def _expected_companion(
    payload: Mapping[str, Any],
    lock_record: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    h_patch = payload.get("h_patch")
    base_authority = payload.get("base_mw_authority")
    if not isinstance(h_patch, Mapping) or not isinstance(base_authority, Mapping):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "Cannot construct E0-MX companion sections"
        )
    h_components = h_patch.get("components")
    if not isinstance(h_components, list):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "Cannot construct E0-MX companion component records"
        )
    inputs = _companion_physical_inputs(
        h_components=cast(list[dict[str, Any]], h_components),
        base_authority=base_authority,
    )
    historical_inputs = _historical_mw_inputs(root)
    historical_identities = {
        (record.get("path"), record.get("commit"), record.get("role"))
        for record in historical_inputs
    }
    if (
        len(historical_inputs) != EXPECTED_HISTORICAL_INPUT_COUNT
        or len(historical_identities) != EXPECTED_HISTORICAL_INPUT_COUNT
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX companion must bind 11 historical path/commit/role identities"
        )
    script = next(
        (
            dict(record)
            for record in h_components
            if record.get("path") == LOCKER_PATH.as_posix()
        ),
        None,
    )
    if script is None:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX companion generating script is absent"
        )
    try:
        output = mw.mv._validate_role_record(lock_record)
    except mw.mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc
    if (
        output.get("path") != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or output.get("role") != "anfis_ablation_model_publication_adoption_patch_lock"
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX companion lock output record drifted"
        )
    blocked_paths = {
        BLOCKED_P_MV_LOCK_PATH,
        BLOCKED_P_MV_COMPANION_PATH,
        SUPERSEDED_P_MW_LOCK_PATH,
        SUPERSEDED_P_MW_COMPANION_PATH,
    }
    if blocked_paths.intersection(
        str(record.get("path")) for record in (*inputs, *historical_inputs)
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "Blocked/superseded P-E0-MV/P-E0-MW leaked into E0-MX inputs"
        )
    return {
        "manifest_version": COMPANION_VERSION,
        "gate": PATCH_GATE,
        "status": "completed",
        "script": script,
        "inputs": inputs,
        "historical_inputs": historical_inputs,
        "historical_inputs_compared_to_current_paths": False,
        "outputs": [output],
        "physical_inputs_only": True,
        "blocked_p_mv_in_inputs": False,
        "superseded_p_mw_in_inputs": False,
        "adopted_a0_light_outputs_in_inputs": True,
        "adopted_a0_bundle_rewritten": False,
        "manifest_written_last": True,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "scientific_network_commands_run": False,
        "historical_a0_semantic_audit_run": True,
        "adopted_a0_regular_0644_nlink1": True,
        "adopted_a0_snapshot_unchanged": True,
        "trainer_entrypoint_run": False,
        "auditor_entrypoint_run": False,
        "model_fit_or_optimization_run": False,
        "calibration_2021_targets_read_during_verification": False,
        "holdout_or_post_2021_targets_read_during_verification": False,
        "future_outcomes_accessed": False,
        "completion_marker_written_last": True,
    }


def _revalidate_publication_state_under_guard(
    payload: Mapping[str, Any],
    *,
    repo_root: Path,
    expected_published_outputs: Sequence[Path],
    adopted_snapshot: AdoptedA0PhysicalSnapshot,
) -> None:
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=repo_root, context="at guarded revalidation entry"
    )
    repository = payload.get("repository")
    h_patch = payload.get("h_patch")
    base_authority = payload.get("base_mw_authority")
    if not all(
        isinstance(section, Mapping)
        for section in (repository, h_patch, base_authority)
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded publication sections are absent"
        )
    repository = cast(Mapping[str, Any], repository)
    h_patch = cast(Mapping[str, Any], h_patch)
    base_authority = cast(Mapping[str, Any], base_authority)
    h_head = repository.get("head")
    if (
        not isinstance(h_head, str)
        or _git_head(repo_root) != h_head
        or _git_head(repo_root, "origin/main") != h_head
        or _live_remote_main_head(repo_root) != h_head
        or _git(repo_root, "branch", "--show-current").strip() != "main"
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded Git refs drifted"
        )
    h_components = _h_mx_components(h_head, repo_root)
    if not _exact_equal(h_patch.get("components"), h_components):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded H components drifted"
        )
    live_base = _base_mw_authority(repo_root)
    if not _exact_equal(base_authority, live_base):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded MW/MV/MU reconstruction drifted"
        )
    if not _exact_equal(
        payload.get("adopted_light_publication"),
        _adopted_light_publication(repo_root),
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded adopted light publication drifted"
        )
    if not _exact_equal(
        payload.get("superseded_p_mw_plan"), _superseded_p_mw_plan(repo_root)
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded superseded P-E0-MW metadata drifted"
        )
    try:
        live_a0 = mw.mv._historical_a0_bundle(repo_root)
        live_namespace = mw.mv._training_namespace_state(repo_root)
    except mw.mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc
    if not _exact_equal(payload.get("adopted_a0_bundle"), live_a0):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded adopted A0/1729 bundle drifted"
        )
    physical_inputs = _companion_physical_inputs(
        h_components=h_components, base_authority=live_base
    )
    historical_inputs = _historical_mw_inputs(repo_root)
    contract = payload.get("companion_contract")
    if (
        not isinstance(contract, Mapping)
        or contract.get("physical_input_count") != EXPECTED_COMPANION_INPUT_COUNT
        or contract.get("historical_input_count") != EXPECTED_HISTORICAL_INPUT_COUNT
        or contract.get("physical_inputs_sha256") != _digest_records(physical_inputs)
        or contract.get("historical_inputs_sha256")
        != _digest_records(historical_inputs)
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded companion digests drifted"
        )
    expected_prelock = payload.get("prelock")
    if not isinstance(expected_prelock, Mapping) or any(
        not _exact_equal(expected_prelock.get(key), value)
        for key, value in live_namespace.items()
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded training namespace drifted"
        )
    live_prohibited = _prohibited_namespace_state(repo_root)
    if not all(live_prohibited.values()) or not _exact_equal(
        expected_prelock.get("prohibited_namespaces"), live_prohibited
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded scientific boundary drifted"
        )
    stable_controls = _control_namespace_state(repo_root)
    for key in (
        "blocked_mv_lock_absent",
        "blocked_mv_companion_absent",
        "superseded_mw_lock_absent",
        "superseded_mw_companion_absent",
        "p_mu_lock_present",
        "p_mu_companion_present",
    ):
        if stable_controls.get(key) is not True:
            raise AnfisAblationModelPublicationAdoptionPatchError(
                f"E0-MX guarded stable control drifted: {key}"
            )
    expected_paths = {path.as_posix() for path in expected_published_outputs}
    status_lines = [
        line
        for line in _git(
            repo_root, "status", "--porcelain", "--untracked-files=all"
        ).splitlines()
        if line
    ]
    if (
        any(len(line) < 4 or line[:2] != "??" for line in status_lines)
        or {line[3:] for line in status_lines} != expected_paths
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX guarded worktree scope drifted: {status_lines}"
        )
    controlled_temporaries = (
        _temporary_path(DEFAULT_PATCH_LOCK_PATH),
        _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
    )
    if any(_lexists(repo_root / path) for path in controlled_temporaries):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX guarded publication temporary appeared"
        )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=repo_root, context="at guarded revalidation exit"
    )


def execute_and_publish_anfis_ablation_model_publication_adoption_patch_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconstruct, verify once, and atomically publish P-E0-MX."""
    root = _root(repo_root)
    adopted_snapshot = _adopted_a0_physical_snapshot(root)
    schema_preflight = preflight_anfis_ablation_model_publication_adoption_patch_schema(
        repo_root=root
    )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after transaction schema preflight"
    )
    before = collect_anfis_ablation_model_publication_adoption_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after initial prelock collection"
    )
    verification = _run_anfis_ablation_model_publication_adoption_patch_verification(
        adopted_snapshot=adopted_snapshot,
        expected_schema_preflight=schema_preflight,
        repo_root=root,
    )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after transaction verification"
    )
    after = collect_anfis_ablation_model_publication_adoption_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after final prelock collection"
    )
    if not _exact_equal(before, after):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX prelock state changed during verification"
        )
    payload = build_anfis_ablation_model_publication_adoption_patch_lock_payload(
        before,
        verification,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after lock payload construction"
    )
    validate_anfis_ablation_model_publication_adoption_patch_lock_payload(
        payload, repo_root=root
    )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after lock payload validation"
    )
    controlled = (
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        _temporary_path(DEFAULT_PATCH_LOCK_PATH),
        _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        LOCKER_GUARD_PATH,
    )
    occupied = [path.as_posix() for path in controlled if _lexists(root / path)]
    if occupied:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX lock namespace is occupied: {occupied}"
        )
    _require_adopted_a0_snapshot(
        adopted_snapshot, repo_root=root, context="after namespace preflight"
    )
    guard: mt._OwnedGuard | None = None
    published: list[mt._OwnedOutput] = []
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MX lock bundle publication in progress\n",
            repo_root=root,
        )
        _require_adopted_a0_snapshot(
            adopted_snapshot, repo_root=root, context="after guard acquisition"
        )
        _revalidate_publication_state_under_guard(
            payload,
            repo_root=root,
            expected_published_outputs=(),
            adopted_snapshot=adopted_snapshot,
        )
        _require_adopted_a0_snapshot(
            adopted_snapshot, repo_root=root, context="immediately before lock publication"
        )
        lock_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH,
            _canonical_json(dict(payload)),
            repo_root=root,
        )
        published.append(lock_output)
        _require_adopted_a0_snapshot(
            adopted_snapshot, repo_root=root, context="immediately after lock publication"
        )
        lock_record = _file_record(
            DEFAULT_PATCH_LOCK_PATH,
            role="anfis_ablation_model_publication_adoption_patch_lock",
            repo_root=root,
        )
        companion = _expected_companion(payload, lock_record, repo_root=root)
        _require_adopted_a0_snapshot(
            adopted_snapshot,
            repo_root=root,
            context="immediately before companion publication",
        )
        companion_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            _canonical_json(companion),
            repo_root=root,
        )
        published.append(companion_output)
        _require_adopted_a0_snapshot(
            adopted_snapshot,
            repo_root=root,
            context="immediately after companion publication",
        )
        if not _exact_equal(
            _load_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root), dict(payload)
        ) or not _exact_equal(
            _load_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root), companion
        ):
            raise AnfisAblationModelPublicationAdoptionPatchError(
                "Published E0-MX bundle differs from its payloads"
            )
        for output in published:
            mt._validate_owned_output(output)
        _revalidate_publication_state_under_guard(
            payload,
            repo_root=root,
            expected_published_outputs=(
                DEFAULT_PATCH_LOCK_PATH,
                DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            ),
            adopted_snapshot=adopted_snapshot,
        )
        for output in published:
            mt._validate_owned_output(output)
        _require_adopted_a0_snapshot(
            adopted_snapshot, repo_root=root, context="immediately before guard release"
        )
        mt._release_publication_guard(guard)
        guard = None
        _require_adopted_a0_snapshot(
            adopted_snapshot, repo_root=root, context="after guard release"
        )
        for output in published:
            mt._validate_owned_output(output)
        _require_adopted_a0_snapshot(
            adopted_snapshot, repo_root=root, context="before successful return"
        )
        committed = True
        return dict(payload), companion
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        for output in reversed(published):
            mt._rollback_owned_output(output)
        raise _translate(exc) from exc
    except BaseException:
        for output in reversed(published):
            mt._rollback_owned_output(output)
        raise
    finally:
        if guard is not None:
            mt._release_publication_guard(guard, tolerate_foreign=True)
        if committed:
            for output in published:
                mt._close_owned_output(output)


def publish_anfis_ablation_model_publication_adoption_patch_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Safe writer alias; caller-supplied payloads are intentionally impossible."""
    return execute_and_publish_anfis_ablation_model_publication_adoption_patch_lock_bundle(
        repo_root=repo_root
    )


def _validate_p_publication(
    payload: Mapping[str, Any], *, repo_root: Path
) -> dict[str, str]:
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("head"), str
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX H repository binding is absent"
        )
    h_head = str(repository["head"])
    head = _git_head(repo_root)
    tracking = _git_head(repo_root, "origin/main")
    remote = _live_remote_main_head(repo_root)
    expected_paths = sorted(
        (
            DEFAULT_PATCH_LOCK_PATH.as_posix(),
            DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
        )
    )
    if (
        _git(repo_root, "branch", "--show-current").strip() != "main"
        or _single_parent(repo_root, head, context="P-E0-MX") != h_head
        or tracking != head
        or remote != head
        or _git_scope(repo_root, h_head, head)
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "paths": expected_paths,
        }
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "Published P-E0-MX topology/refs drifted"
        )
    _require_git_modes(repo_root, head, expected_paths, context="P-E0-MX")
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


def _static_effective_authority(
    payload: Mapping[str, Any],
    *,
    publication: Mapping[str, str],
    lock: Mapping[str, Any],
    companion: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    h_patch = cast(Mapping[str, Any], payload["h_patch"])
    companion_contract = cast(Mapping[str, Any], payload["companion_contract"])
    runtime = _file_record(
        Path("configs/closure_v1/anfis_ablation_training_development_runtime.yaml"),
        role="anfis_ablation_training_runtime_contract",
        repo_root=repo_root,
    )
    return {
        "gate": PATCH_GATE,
        "status": "effective_preflight_passed",
        "adopted_light_commit": ADOPTED_LIGHT_COMMIT,
        "h_patch_head": publication["h_patch_head"],
        "p_patch_head": publication["p_patch_head"],
        "runtime": runtime,
        "lock": dict(lock),
        "companion": dict(companion),
        "h_components_sha256": h_patch["components_sha256"],
        "physical_inputs_sha256": companion_contract["physical_inputs_sha256"],
        "runtime_sha256": runtime["sha256"],
        "lock_sha256": lock["sha256"],
        "companion_sha256": companion["sha256"],
    }


def _slot_manifest_binding(
    static: Mapping[str, Any], *, model_id: str, base_seed: int, index: int
) -> dict[str, Any]:
    binding = {
        key: static[key]
        for key in (
            "gate",
            "status",
            "h_patch_head",
            "p_patch_head",
            "h_components_sha256",
            "physical_inputs_sha256",
            "runtime_sha256",
            "lock_sha256",
            "companion_sha256",
        )
    }
    binding.update(
        {
            "authorized_model_id": model_id,
            "authorized_base_seed": base_seed,
            "completed_prefix_count": index,
            "slot_creation_prefix_count": index,
        }
    )
    return binding


def _current_trainer_record(repo_root: Path) -> dict[str, Any]:
    return _file_record(
        Path("src/experiments/train_closure_anfis_ablation.py"),
        role="trainer",
        repo_root=repo_root,
    )


def _historical_trainer_record(repo_root: Path) -> dict[str, Any]:
    return _plain_git_blob_record(
        repo_root,
        mw.mv.MU_H_HEAD,
        "src/experiments/train_closure_anfis_ablation.py",
        role="trainer",
    )


def _validate_completed_mx_slot(
    static: Mapping[str, Any],
    *,
    model_id: str,
    base_seed: int,
    target_index: int,
    repo_root: Path,
    target_reference: Any,
    allow_pointer: bool = False,
) -> None:
    if type(allow_pointer) is not bool:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX completed-slot pointer policy must be an exact boolean"
        )
    paths = mt.anfis_ablation_training_slot_paths(model_id, base_seed)
    manifest_bytes = _read_regular_bytes(paths["manifest"], repo_root=repo_root)
    manifest = _strict_json(
        manifest_bytes, label=f"E0-MX model manifest {model_id}/{base_seed}"
    )
    expected_binding = _slot_manifest_binding(
        static, model_id=model_id, base_seed=base_seed, index=target_index
    )
    if (
        not manifest
        or next(reversed(manifest)) != "completion_marker_written_last"
        or manifest_bytes != mw.mv._model_manifest_json(manifest)
        or not _exact_equal(manifest.get("authority"), expected_binding)
        or manifest.get("model_id") != model_id
        or manifest.get("base_seed") != base_seed
        or manifest.get("status") != "completed"
        or manifest.get("slot_status") != "available"
        or manifest.get("fit_status") != "passed"
        or manifest.get("completion_marker_written_last") is not True
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX completed slot manifest drifted: {model_id}/{base_seed}"
        )
    expected_outputs = [
        _file_record(path, role=name, repo_root=repo_root)
        for name, path in paths.items()
        if name != "manifest"
    ]
    if not _exact_equal(manifest.get("outputs"), expected_outputs):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX completed slot outputs drifted: {model_id}/{base_seed}"
        )
    trainer = _current_trainer_record(repo_root)
    if not _exact_equal(manifest.get("script"), trainer) or not _exact_equal(
        manifest.get("source_code"), [trainer]
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX completed slot source drifted: {model_id}/{base_seed}"
        )
    expected_authority_records = [
        dict(cast(Mapping[str, Any], static["runtime"])),
        dict(cast(Mapping[str, Any], static["lock"])),
        dict(cast(Mapping[str, Any], static["companion"])),
    ]
    if not _exact_equal(manifest.get("authority_records"), expected_authority_records):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX completed slot authority records drifted: {model_id}/{base_seed}"
        )
    from src.experiments.audit_closure_anfis_ablation_model_bundle import (
        AnfisAblationModelAuditError,
        _load_runtime_contract,
        validate_anfis_ablation_model_bundle_semantics,
    )

    runtime, _ = _load_runtime_contract(repo_root)
    try:
        result = validate_anfis_ablation_model_bundle_semantics(
            model_id=model_id,
            base_seed=base_seed,
            authority_binding=expected_binding,
            runtime=runtime,
            repo_root=repo_root,
            allow_pointer=allow_pointer,
            target_reference=target_reference,
            slot_source_record=trainer,
        )
    except AnfisAblationModelAuditError as exc:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX completed slot failed semantic audit: {model_id}/{base_seed}"
        ) from exc
    if (
        result.get("status") != "passed"
        or result.get("schema_exact") is not True
        or result.get("hash_bindings_verified") is not True
        or any(
            result.get(key) is not False
            for key in (
                "calibration_targets_read",
                "test_or_holdout_targets_read",
                "future_outcomes_accessed",
                "dvc_command_executed",
                "scientific_network_egress",
                "writes_performed",
            )
        )
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX completed slot semantic evidence drifted: {model_id}/{base_seed}"
        )


def _slot_light_paths(paths: Mapping[str, Path]) -> set[str]:
    if set(LIGHT_SLOT_OUTPUT_NAMES) - set(paths):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX slot path dialect is missing light outputs"
        )
    return {paths[name].as_posix() for name in LIGHT_SLOT_OUTPUT_NAMES}


def _validate_registered_prediction_pointer(
    *, model_id: str, base_seed: int, repo_root: Path
) -> None:
    try:
        mt._validate_prediction_pointer(
            model_id=model_id, base_seed=base_seed, repo_root=repo_root
        )
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _validate_exact_training_prefix(
    static: Mapping[str, Any], *, audit_mode: bool, repo_root: Path
) -> int:
    if type(audit_mode) is not bool:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX prefix audit mode must be an exact boolean"
        )
    _adopted_light_publication(repo_root)
    complete: list[bool] = []
    pointer_presence: list[bool] = []
    slot_paths: list[dict[str, Path]] = []
    for model_id, base_seed in ORDERED_SLOTS:
        paths = mt.anfis_ablation_training_slot_paths(model_id, base_seed)
        slot_paths.append(paths)
        observed = [_lexists(repo_root / path) for path in paths.values()]
        if any(observed) and not all(observed):
            raise AnfisAblationModelPublicationAdoptionPatchError(
                f"E0-MX partial slot exists: {model_id}/{base_seed}"
            )
        complete.append(all(observed))
        pointer = mt._pointer_path(model_id, base_seed)
        pointer_presence.append(_lexists(repo_root / pointer))
        prohibited = [
            *(mt._temporary_path(path) for path in paths.values()),
            mt._guard_path(model_id, base_seed),
            Path(f"{pointer.as_posix()}.tmp"),
        ]
        if any(_lexists(repo_root / path) for path in prohibited):
            raise AnfisAblationModelPublicationAdoptionPatchError(
                f"E0-MX prohibited temporary/guard exists: {model_id}/{base_seed}"
            )
    prefix = 0
    while prefix < len(complete) and complete[prefix]:
        prefix += 1
    if prefix < 1 or any(complete[prefix:]):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX completed slots do not form the exact adopted prefix"
        )
    registered = any(pointer_presence)
    if registered and (
        not audit_mode or prefix != len(ORDERED_SLOTS) or not all(pointer_presence)
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX pointers require the complete explicit post-registration audit"
        )
    target_reference: Any | None = None
    expected_light_paths: set[str] = set()
    for index, (model_id, base_seed) in enumerate(ORDERED_SLOTS[:prefix]):
        paths = slot_paths[index]
        expected_light_paths.update(_slot_light_paths(paths))
        if index == 0:
            try:
                mw.mv._historical_a0_bundle(
                    repo_root, allow_registered_pointer=registered
                )
            except mw.mv.AnfisAblationModelManifestPatchError as exc:
                raise _translate(exc) from exc
        else:
            if target_reference is None:
                from src.experiments.audit_closure_anfis_ablation_model_bundle import (
                    load_cutoff_target_reference,
                )

                target_reference = load_cutoff_target_reference(repo_root=repo_root)
            _validate_completed_mx_slot(
                static,
                model_id=model_id,
                base_seed=base_seed,
                target_index=index,
                repo_root=repo_root,
                target_reference=target_reference,
                allow_pointer=registered,
            )
        if registered:
            _validate_registered_prediction_pointer(
                model_id=model_id, base_seed=base_seed, repo_root=repo_root
            )
    if any(_lexists(repo_root / path) for path in E0_M_PATHS) or _lexists(
        repo_root / OUTCOME_ACCESS_LOG
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX progression crossed E0-M/outcome boundary"
        )
    status_lines = [
        line
        for line in _git(
            repo_root, "status", "--porcelain", "--untracked-files=all"
        ).splitlines()
        if line
    ]
    future_light_paths = expected_light_paths - set(HISTORICAL_A0_LIGHT_PATHS)
    if not registered:
        expected_status = [f"?? {path}" for path in sorted(future_light_paths)]
        if status_lines != expected_status:
            raise AnfisAblationModelPublicationAdoptionPatchError(
                f"E0-MX unregistered slot status drifted: {status_lines}"
            )
        return prefix
    allowed_registered_paths = {
        *future_light_paths,
        *(mt._pointer_path(model, seed).as_posix() for model, seed in ORDERED_SLOTS),
        "models.dvc",
    }
    for line in status_lines:
        if (
            len(line) < 4
            or line[:2] not in {"??", "A ", " M", "M "}
            or line[3:] not in allowed_registered_paths
        ):
            raise AnfisAblationModelPublicationAdoptionPatchError(
                f"E0-MX post-registration worktree drifted: {line}"
            )
    return prefix


def _effective_authorizations(*, model_id: str, audit: bool) -> dict[str, bool]:
    return {
        "a0_development_fit_authorized": not audit and model_id == "A0",
        "a1_development_fit_authorized": not audit and model_id == "A1",
        "target_access_through_2020_authorized": True,
        "selection_diagnostics_authorized": True,
        "model_bundle_audit_authorized": audit,
        "calibration_authorized": False,
        "calibration_target_access_authorized": False,
        "final_e7_metrics_authorized": False,
        "rollout_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "scientific_network_authorized": False,
        "outcome_access_authorized": False,
        "future_outcomes_accessed": False,
        "batch_slot_execution_authorized": False,
    }


def _summary_authorizations() -> dict[str, bool]:
    return {
        key: False
        for key in _effective_authorizations(model_id="A0", audit=False)
    }


def load_effective_anfis_ablation_model_publication_adoption_patch_authority(
    *,
    model_id: str | None = None,
    base_seed: int | None = None,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if type(audit_current_unpublished) is not bool:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX audit mode must be an exact boolean"
        )
    target_supplied = model_id is not None or base_seed is not None
    if target_supplied and (model_id is None or base_seed is None):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX target model/seed is incomplete"
        )
    if audit_current_unpublished and not target_supplied:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX audit mode requires one explicit target"
        )
    if target_supplied:
        if type(model_id) is not str or type(base_seed) is not int:
            raise AnfisAblationModelPublicationAdoptionPatchError(
                "E0-MX target model/seed types drifted"
            )
        try:
            mt.validate_model_seed(model_id, base_seed)
        except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
            raise _translate(exc) from exc
    if verify_remote is not True:
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX effective authority requires live remote verification"
        )
    root = _root(repo_root)
    payload_bytes = _read_regular_bytes(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    payload = _strict_json(payload_bytes, label="P-E0-MX lock")
    if payload_bytes != _canonical_json(payload):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX lock is not canonical JSON"
        )
    pointer_presence = [
        _lexists(root / mt._pointer_path(slot_model, slot_seed))
        for slot_model, slot_seed in ORDERED_SLOTS
    ]
    allow_registered_pointers = audit_current_unpublished and all(pointer_presence)
    validate_anfis_ablation_model_publication_adoption_patch_lock_payload(
        payload,
        allow_registered_pointers=allow_registered_pointers,
        repo_root=root,
    )
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="anfis_ablation_model_publication_adoption_patch_lock",
        repo_root=root,
    )
    companion_bytes = _read_regular_bytes(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    companion_payload = _strict_json(companion_bytes, label="P-E0-MX companion")
    if (
        companion_bytes != _canonical_json(companion_payload)
        or not _exact_equal(
            companion_payload,
            _expected_companion(payload, lock_record, repo_root=root),
        )
    ):
        raise AnfisAblationModelPublicationAdoptionPatchError(
            "E0-MX lock companion drifted"
        )
    companion_record = _file_record(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        role="anfis_ablation_model_publication_adoption_patch_lock_manifest",
        repo_root=root,
    )
    publication = _validate_p_publication(payload, repo_root=root)
    static = _static_effective_authority(
        payload,
        publication=publication,
        lock=lock_record,
        companion=companion_record,
        repo_root=root,
    )
    prefix = _validate_exact_training_prefix(
        static, audit_mode=audit_current_unpublished, repo_root=root
    )
    if model_id is None or base_seed is None:
        return {
            **static,
            **_summary_authorizations(),
            "authorized_model_id": None,
            "authorized_base_seed": None,
            "completed_prefix_count": prefix,
            "slot_creation_prefix_count": None,
            "audit_current_unpublished": False,
            "slot_manifest_authority": None,
            "slot_source_record": None,
            "ordered_slots": [
                {"model_id": slot_model, "base_seed": slot_seed}
                for slot_model, slot_seed in ORDERED_SLOTS
            ],
            "progression_policy": (
                "exact_pretty_manifest_prefix_no_pointers_until_all_ten"
            ),
        }
    target_index = ORDERED_SLOTS.index((model_id, base_seed))
    valid_target = (
        target_index < prefix
        if audit_current_unpublished
        else target_index == prefix
    )
    if not valid_target:
        mode = "audit" if audit_current_unpublished else "build"
        raise AnfisAblationModelPublicationAdoptionPatchError(
            f"E0-MX target is not in the exact {mode} position"
        )
    if audit_current_unpublished and target_index == 0:
        slot_manifest_authority = dict(HISTORICAL_A0_AUTHORITY)
        slot_source_record = _historical_trainer_record(root)
    else:
        slot_manifest_authority = _slot_manifest_binding(
            static,
            model_id=model_id,
            base_seed=base_seed,
            index=target_index,
        )
        slot_source_record = _current_trainer_record(root)
    return {
        **static,
        **_effective_authorizations(
            model_id=model_id, audit=audit_current_unpublished
        ),
        "authorized_model_id": model_id,
        "authorized_base_seed": base_seed,
        "completed_prefix_count": prefix,
        "slot_creation_prefix_count": target_index,
        "audit_current_unpublished": audit_current_unpublished,
        "slot_manifest_authority": slot_manifest_authority,
        "slot_source_record": slot_source_record,
        "ordered_slots": [
            {"model_id": slot_model, "base_seed": slot_seed}
            for slot_model, slot_seed in ORDERED_SLOTS
        ],
        "progression_policy": "exact_pretty_manifest_prefix_no_pointers_until_all_ten",
    }


def load_effective_anfis_ablation_model_publication_authority(
    *,
    model_id: str | None = None,
    base_seed: int | None = None,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Compatibility spelling used by consumers."""
    return load_effective_anfis_ablation_model_publication_adoption_patch_authority(
        model_id=model_id,
        base_seed=base_seed,
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


def require_anfis_ablation_model_publication_adoption_patch_authority(
    model_id: str,
    base_seed: int,
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    return load_effective_anfis_ablation_model_publication_adoption_patch_authority(
        model_id=model_id,
        base_seed=base_seed,
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


def require_anfis_ablation_model_publication_authority(
    model_id: str,
    base_seed: int,
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    return require_anfis_ablation_model_publication_adoption_patch_authority(
        model_id,
        base_seed,
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


__all__ = [
    "AnfisAblationModelPublicationAdoptionPatchError",
    "DEFAULT_PATCH_LOCK_MANIFEST_PATH",
    "DEFAULT_PATCH_LOCK_PATH",
    "DEFAULT_PATCH_LOCK_SCHEMA",
    "DEFAULT_PATCH_MANIFEST_PATH",
    "FOCUSED_TEST_COMMAND",
    "FOCUSED_TEST_COUNT",
    "LOCKER_GUARD_PATH",
    "PATCH_ADDED_PATHS",
    "PATCH_COMPONENT_GIT_MODES",
    "PATCH_COMPONENT_ROLES",
    "PATCH_PATHS",
    "SUPERSEDED_MW_PATHS",
    "build_anfis_ablation_model_publication_adoption_patch_lock_payload",
    "collect_anfis_ablation_model_publication_adoption_patch_prelock_state",
    "execute_and_publish_anfis_ablation_model_publication_adoption_patch_lock_bundle",
    "load_effective_anfis_ablation_model_publication_authority",
    "load_effective_anfis_ablation_model_publication_adoption_patch_authority",
    "preflight_anfis_ablation_model_publication_adoption_patch_schema",
    "publish_anfis_ablation_model_publication_adoption_patch_lock_bundle",
    "require_anfis_ablation_model_publication_authority",
    "require_anfis_ablation_model_publication_adoption_patch_authority",
    "run_anfis_ablation_model_publication_adoption_patch_verification",
    "validate_anfis_ablation_model_publication_adoption_patch_lock_payload",
]
