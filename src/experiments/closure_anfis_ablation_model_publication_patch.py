#!/usr/bin/env python
"""Fail-closed E0-MW publication authority for ANFIS-ablation manifests.

E0-MW is an additive implementation-only overlay over published H-E0-MV.  It
preserves the historical A0/1729 bundle and P-E0-MU authority, records the
failed P-E0-MV publication attempt as non-authoritative incident metadata, and
uses a new lock basename that is outside the generic experiment-manifest
filename dialect.  No public writer accepts caller-supplied payloads or
verification evidence.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments import closure_anfis_ablation_model_manifest_patch as mv
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = mv.PROJECT_ROOT
mt = mv.mt

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/anfis_ablation_model_publication_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/anfis_ablation_model_publication_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "anfis_ablation_model_publication_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_anfis_ablation_model_publication_patch/lock_bundle.guard"
)
LOCKER_PATH = Path(
    "src/experiments/lock_closure_anfis_ablation_model_publication_patch.py"
)

H_MV_HEAD = "455f593fc276dc0b74565e34aea4a09342badb30"
H_MV_PARENT = "404983e3dfc511d982b2641aa4aea769dcbc6beb"
BASE_COMMIT = H_MV_HEAD
PATCH_GATE = "E0-MW"
SCHEMA_VERSION = "closure_anfis_ablation_model_publication_patch_lock_v1"
COMPANION_VERSION = (
    "closure_anfis_ablation_model_publication_patch_lock_manifest_v1"
)
EXPECTED_COMPANION_INPUT_COUNT = 77
EXPECTED_HISTORICAL_INPUT_COUNT = 5

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

SUPERSEDED_MV_PATHS = (
    "src/data/prepare_commit_artifacts.py",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py",
    "src/experiments/train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
    "tests/test_train_closure_anfis_ablation.py",
)
PRESERVED_MV_PATHS = tuple(
    path for path in mv.PATCH_PATHS if path not in set(SUPERSEDED_MV_PATHS)
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): (
        "anfis_ablation_model_publication_patch_lock_schema"
    ),
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_PATCH_1.md": (
        "anfis_ablation_model_publication_patch_protocol"
    ),
    "src/data/prepare_commit_artifacts.py": (
        "publication_patch_deferred_dvc_precommit_assistant"
    ),
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": (
        "publication_patch_anfis_ablation_model_bundle_auditor"
    ),
    "src/experiments/closure_anfis_ablation_model_publication_patch.py": (
        "anfis_ablation_model_publication_patch_validator"
    ),
    LOCKER_PATH.as_posix(): "anfis_ablation_model_publication_patch_locker",
    "src/experiments/train_closure_anfis_ablation.py": (
        "publication_patch_anfis_ablation_trainer"
    ),
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": (
        "publication_patch_anfis_ablation_model_bundle_auditor_tests"
    ),
    "tests/test_closure_anfis_ablation_model_publication_patch.py": (
        "anfis_ablation_model_publication_patch_tests"
    ),
    "tests/test_train_closure_anfis_ablation.py": (
        "publication_patch_anfis_ablation_trainer_tests"
    ),
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_ADDED_PATHS = tuple(
    path for path in PATCH_PATHS if path not in set(SUPERSEDED_MV_PATHS)
)
PATCH_COMPONENT_GIT_MODES = {
    path: "100755" if path == "src/data/prepare_commit_artifacts.py" else "100644"
    for path in PATCH_PATHS
}

REGISTERED_SEEDS = mv.REGISTERED_SEEDS
ORDERED_SLOTS = mv.ORDERED_SLOTS
E0_M_PATHS = mv.E0_M_PATHS
OUTCOME_ACCESS_LOG = mv.OUTCOME_ACCESS_LOG
EMPTY_SHA256 = mv.EMPTY_SHA256
SHA1_RE = mv.SHA1_RE
SHA256_RE = mv.SHA256_RE
HISTORICAL_A0_AUTHORITY = mv.HISTORICAL_A0_AUTHORITY
HISTORICAL_A0_FINAL_RECORDS = mv.HISTORICAL_A0_FINAL_RECORDS
HISTORICAL_A0_LIGHT_PATHS = mv.HISTORICAL_A0_LIGHT_PATHS
LIGHT_SLOT_OUTPUT_NAMES = mv.LIGHT_SLOT_OUTPUT_NAMES

TYPE_CHECK_COMMAND = mv.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    ".venv/bin/python",
    "-m",
    "pytest",
    "-q",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
    "tests/test_train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
)
# Finalized from the exact closed H-E0-MW collection.
FOCUSED_TEST_COUNT = 74
POETRY_CHECK_COMMAND = mv.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mv.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mv.DIFF_CHECK_COMMAND
FOCUSED_PYTEST_ENVIRONMENT = dict(mv.FOCUSED_PYTEST_ENVIRONMENT)
FOCUSED_SUMMARY_RE = re.compile(
    r"^(?P<count>[1-9][0-9]*) passed in (?P<seconds>[0-9]+\.[0-9]{2})s"
    r"(?: \((?P<clock>(?:[0-9]+ days?, )?[0-9]+:[0-9]{2}:[0-9]{2})\))?$"
)
FORBIDDEN_FOCUSED_SUMMARY_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed|errors?|failed)\b",
    flags=re.IGNORECASE,
)

UNPUBLISHED_AUTHORIZATIONS = dict(mv.UNPUBLISHED_AUTHORIZATIONS)
LOCK_SEALS = {
    "historical_a0_bundle_preserved": True,
    "historical_a0_bundle_rewrite_forbidden": True,
    "historical_mu_authority_preserved": True,
    "published_h_mv_preserved": True,
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


class AnfisAblationModelPublicationPatchError(RuntimeError):
    """Raised when the additive E0-MW authority is not exact."""


def _translate(exc: BaseException) -> AnfisAblationModelPublicationPatchError:
    return AnfisAblationModelPublicationPatchError(str(exc))


def _root(repo_root: Path | None) -> Path:
    return mv._root(repo_root)


def _canonical_json(value: Any) -> bytes:
    return mv._canonical_json(value)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest_records(records: Sequence[Mapping[str, Any]]) -> str:
    return mv._digest_records(records)


def _exact_equal(left: Any, right: Any) -> bool:
    return mv._exact_equal(left, right)


def _file_record(
    path: Path, *, role: str, repo_root: Path
) -> dict[str, Any]:
    try:
        return mv._file_record(path, role=role, repo_root=repo_root)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _plain_git_blob_record(
    repo_root: Path, commit: str, path: str, *, role: str
) -> dict[str, Any]:
    try:
        return mv._plain_git_blob_record(repo_root, commit, path, role=role)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _historical_git_blob_record(
    repo_root: Path, commit: str, path: str, *, role: str
) -> dict[str, Any]:
    try:
        return mv._historical_git_blob_record(repo_root, commit, path, role=role)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _git(repo_root: Path, *arguments: str) -> str:
    try:
        return mv._git(repo_root, *arguments)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _git_head(repo_root: Path, ref: str = "HEAD") -> str:
    try:
        return mv._git_head(repo_root, ref)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _single_parent(repo_root: Path, commit: str, *, context: str) -> str:
    try:
        return mv._single_parent(repo_root, commit, context=context)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _git_scope(repo_root: Path, parent: str, head: str) -> dict[str, Any]:
    try:
        return mv._git_scope(repo_root, parent, head)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _require_exact_git_modes(
    repo_root: Path,
    commit: str,
    expected: Mapping[str, str],
    *,
    context: str,
) -> None:
    try:
        mv._require_exact_git_modes(repo_root, commit, expected, context=context)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _require_git_modes(
    repo_root: Path, commit: str, paths: Sequence[str], *, context: str
) -> None:
    try:
        mv._require_git_modes(repo_root, commit, paths, context=context)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _live_remote_main_head(repo_root: Path) -> str:
    try:
        return mv._live_remote_main_head(repo_root)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _read_regular_bytes(path: Path, *, repo_root: Path) -> bytes:
    try:
        return mv._read_regular_bytes(path, repo_root=repo_root)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _load_json(path: Path, *, repo_root: Path) -> dict[str, Any]:
    try:
        return mv._load_json(path, repo_root=repo_root)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _strict_json(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        return mv._strict_json(payload, label=label)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def _lexists(path: Path) -> bool:
    return mv._lexists(path)


def _temporary_path(path: Path) -> Path:
    return mt._temporary_path(path)


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW lock timestamp must be a string"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW lock timestamp is malformed"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW lock timestamp must include a timezone"
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


def _h_mv_component_records(repo_root: Path) -> list[dict[str, Any]]:
    return [
        _plain_git_blob_record(repo_root, H_MV_HEAD, path, role=role)
        for path, role in sorted(mv.PATCH_COMPONENT_ROLES.items())
    ]


def _partition_h_mv_components(
    records: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_path = {str(record.get("path")): dict(record) for record in records}
    if set(by_path) != set(mv.PATCH_PATHS) or len(by_path) != len(records):
        raise AnfisAblationModelPublicationPatchError(
            "Published H-E0-MV components differ from the closed partition"
        )
    preserved = [by_path[path] for path in sorted(PRESERVED_MV_PATHS)]
    superseded = [by_path[path] for path in sorted(SUPERSEDED_MV_PATHS)]
    if len(preserved) != 5 or len(superseded) != 5:
        raise AnfisAblationModelPublicationPatchError(
            "Published H-E0-MV must partition as five preserved plus five superseded"
        )
    return preserved, superseded


def _base_mv_authority(repo_root: Path) -> dict[str, Any]:
    expected_scope = {
        "added": 5,
        "modified": 5,
        "deleted": 0,
        "paths": list(mv.PATCH_PATHS),
    }
    if (
        _single_parent(repo_root, H_MV_HEAD, context="H-E0-MV") != H_MV_PARENT
        or _git_scope(repo_root, H_MV_PARENT, H_MV_HEAD) != expected_scope
    ):
        raise AnfisAblationModelPublicationPatchError(
            "Published H-E0-MV topology drifted"
        )
    _require_exact_git_modes(
        repo_root,
        H_MV_HEAD,
        mv.PATCH_COMPONENT_GIT_MODES,
        context="H-E0-MV",
    )
    components = _h_mv_component_records(repo_root)
    preserved, superseded = _partition_h_mv_components(components)
    for record in preserved:
        physical = _file_record(
            Path(str(record["path"])), role=str(record["role"]), repo_root=repo_root
        )
        if physical != record:
            raise AnfisAblationModelPublicationPatchError(
                f"Preserved H-E0-MV component drifted: {record['path']}"
            )
    try:
        p_mu_authority = mv._mu_authority(repo_root)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc
    return {
        "h_head": H_MV_HEAD,
        "h_parent": H_MV_PARENT,
        "h_scope": {"added": 5, "modified": 5, "deleted": 0},
        "component_count": 10,
        "components": components,
        "components_sha256": _digest_records(components),
        "preserved_component_count": 5,
        "preserved_components": preserved,
        "preserved_components_sha256": _digest_records(preserved),
        "superseded_component_count": 5,
        "superseded_components": superseded,
        "superseded_components_sha256": _digest_records(superseded),
        "p_mu_authority": p_mu_authority,
        "p_mv_publication_status": "blocked_unpublished",
        "p_mv_is_authority": False,
    }


def _h_mw_components(head: str, repo_root: Path) -> list[dict[str, Any]]:
    physical = [
        _file_record(Path(path), role=role, repo_root=repo_root)
        for path, role in sorted(PATCH_COMPONENT_ROLES.items())
    ]
    expected = [
        _plain_git_blob_record(repo_root, head, path, role=role)
        for path, role in sorted(PATCH_COMPONENT_ROLES.items())
    ]
    if physical != expected:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW H components differ from their Git blobs"
        )
    return physical


def _historical_mv_inputs(repo_root: Path) -> list[dict[str, Any]]:
    records = [
        _historical_git_blob_record(
            repo_root,
            H_MV_HEAD,
            path,
            role=f"superseded_mv_{mv.PATCH_COMPONENT_ROLES[path]}",
        )
        for path in sorted(SUPERSEDED_MV_PATHS)
    ]
    if len(records) != EXPECTED_HISTORICAL_INPUT_COUNT:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW historical input count drifted"
        )
    return records


def _companion_physical_inputs(
    *,
    h_components: Sequence[Mapping[str, Any]],
    base_authority: Mapping[str, Any],
) -> list[dict[str, Any]]:
    p_mu = base_authority.get("p_mu_authority")
    preserved_mv = base_authority.get("preserved_components")
    if not isinstance(p_mu, Mapping) or not isinstance(preserved_mv, list):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW companion source authority is absent"
        )
    preserved_mu = p_mu.get("preserved_physical_inputs")
    p_mu_components = p_mu.get("p_components")
    if not isinstance(preserved_mu, list) or not isinstance(p_mu_components, list):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW P-E0-MU physical records are absent"
        )
    records = [
        *(dict(record) for record in preserved_mu),
        *(dict(record) for record in p_mu_components),
        *(dict(record) for record in preserved_mv),
        *(dict(record) for record in h_components),
    ]
    records.sort(key=lambda record: str(record.get("path")))
    paths = [str(record.get("path")) for record in records]
    blocked_paths = {BLOCKED_P_MV_LOCK_PATH, BLOCKED_P_MV_COMPANION_PATH}
    if (
        len(records) != EXPECTED_COMPANION_INPUT_COUNT
        or len(set(paths)) != EXPECTED_COMPANION_INPUT_COUNT
        or blocked_paths.intersection(paths)
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW companion must bind 77 unique physical inputs without blocked P-E0-MV"
        )
    return records


def _expected_manifest_dialect() -> dict[str, Any]:
    return mv._expected_manifest_dialect()


def _control_namespace_state(repo_root: Path) -> dict[str, bool]:
    return {
        "mw_lock_absent": not _lexists(repo_root / DEFAULT_PATCH_LOCK_PATH),
        "mw_companion_absent": not _lexists(
            repo_root / DEFAULT_PATCH_LOCK_MANIFEST_PATH
        ),
        "mw_lock_temp_absent": not _lexists(
            repo_root / _temporary_path(DEFAULT_PATCH_LOCK_PATH)
        ),
        "mw_companion_temp_absent": not _lexists(
            repo_root / _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        ),
        "mw_locker_guard_absent": not _lexists(repo_root / LOCKER_GUARD_PATH),
        "blocked_mv_lock_absent": not _lexists(repo_root / Path(BLOCKED_P_MV_LOCK_PATH)),
        "blocked_mv_companion_absent": not _lexists(
            repo_root / Path(BLOCKED_P_MV_COMPANION_PATH)
        ),
        "p_mu_lock_present": _lexists(repo_root / mv.mu.DEFAULT_PATCH_LOCK_PATH),
        "p_mu_companion_present": _lexists(
            repo_root / mv.mu.DEFAULT_PATCH_LOCK_MANIFEST_PATH
        ),
    }


def _prohibited_namespace_state(repo_root: Path) -> dict[str, bool]:
    return {
        "e0_m_paths_absent": not any(
            _lexists(repo_root / path) for path in E0_M_PATHS
        ),
        "outcome_access_log_absent": not _lexists(repo_root / OUTCOME_ACCESS_LOG),
    }


def preflight_anfis_ablation_model_publication_patch_schema(
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW schema exceeds the supported validator subset"
        )
    return {
        "schema_path": DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
        "canonical_schema_bytes": len(encoded),
        "canonical_schema_sha256": _sha256_bytes(encoded),
        "supported_subset_verified": True,
        "unsupported_semantic_keywords": [],
    }


def collect_anfis_ablation_model_publication_patch_prelock_state(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    preflight_anfis_ablation_model_publication_patch_schema(repo_root=root)
    head = _git_head(root)
    expected_scope = {
        "added": 5,
        "modified": 5,
        "deleted": 0,
        "paths": list(PATCH_PATHS),
    }
    if (
        _single_parent(root, head, context="H-E0-MW") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, head) != expected_scope
    ):
        raise AnfisAblationModelPublicationPatchError(
            "H-E0-MW must be the exact 5M+5A child of published H-E0-MV"
        )
    _require_exact_git_modes(
        root, head, PATCH_COMPONENT_GIT_MODES, context="H-E0-MW"
    )
    branch = _git(root, "branch", "--show-current").strip()
    tracking = _git_head(root, "origin/main")
    remote = _live_remote_main_head(root) if verify_remote else tracking
    if branch != "main" or tracking != head or remote != head:
        raise AnfisAblationModelPublicationPatchError(
            "H-E0-MW refs are not aligned with main"
        )
    status_lines = [
        line
        for line in _git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
        if line
    ]
    expected_status = [f"?? {path}" for path in sorted(HISTORICAL_A0_LIGHT_PATHS)]
    if status_lines != expected_status:
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW prelock worktree scope drifted: {status_lines}"
        )

    h_components = _h_mw_components(head, root)
    base_authority = _base_mv_authority(root)
    historical_inputs = _historical_mv_inputs(root)
    physical_inputs = _companion_physical_inputs(
        h_components=h_components, base_authority=base_authority
    )
    try:
        adopted_a0 = mv._historical_a0_bundle(root)
        namespace = mv._training_namespace_state(root)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc
    controls = _control_namespace_state(root)
    prohibited = _prohibited_namespace_state(root)
    if not all(controls.values()) or not all(prohibited.values()):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW control or scientific boundary namespace drifted"
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
            "worktree_scope": "exact_historical_a0_light_outputs_only",
        },
        "h_patch": {
            "base_commit": BASE_COMMIT,
            "head": head,
            "parent": BASE_COMMIT,
            "component_count": 10,
            "components": h_components,
            "components_sha256": _digest_records(h_components),
            "components_git_modes": dict(PATCH_COMPONENT_GIT_MODES),
            "scope": {"added": 5, "modified": 5, "deleted": 0},
        },
        "base_mv_authority": base_authority,
        "blocked_p_mv_attempt": _blocked_p_mv_attempt(),
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
            "historical_a0_outputs_in_inputs": False,
            "manifest_written_last": True,
        },
        "prelock": {
            **namespace,
            "historical_a0_finals_sha256": adopted_a0["finals_sha256"],
            "control_paths": controls,
            "prohibited_namespaces": prohibited,
        },
    }


def build_anfis_ablation_model_publication_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    required = {
        "repository",
        "h_patch",
        "base_mv_authority",
        "blocked_p_mv_attempt",
        "adopted_a0_bundle",
        "manifest_dialect",
        "companion_contract",
        "prelock",
    }
    if set(prelock) != required:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW prelock bundle dialect drifted"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "locked_unpublished",
        "gate": PATCH_GATE,
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
        "repository": dict(cast(Mapping[str, Any], prelock["repository"])),
        "h_patch": dict(cast(Mapping[str, Any], prelock["h_patch"])),
        "base_mv_authority": dict(
            cast(Mapping[str, Any], prelock["base_mv_authority"])
        ),
        "blocked_p_mv_attempt": dict(
            cast(Mapping[str, Any], prelock["blocked_p_mv_attempt"])
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
        raise AnfisAblationModelPublicationPatchError(
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW focused pytest summary is not one closed clean result"
        )
    return {
        "test_count": FOCUSED_TEST_COUNT,
        "skipped_count": 0,
        "deselected_count": 0,
    }


def _audit_historical_a0_semantics(repo_root: Path) -> dict[str, Any]:
    try:
        return mv._audit_historical_a0_semantics(repo_root)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc


def run_anfis_ablation_model_publication_patch_verification(
    *,
    expected_schema_preflight: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    schema_preflight = preflight_anfis_ablation_model_publication_patch_schema(
        repo_root=root
    )
    if (
        expected_schema_preflight is not None
        and dict(expected_schema_preflight) != schema_preflight
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW schema changed before verification"
        )
    full_type_check, stdout, stderr = _run_command(TYPE_CHECK_COMMAND, repo_root=root)
    if stdout != "All checks passed!\n" or stderr:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW full type-check output drifted"
        )
    focused_tests, stdout, stderr = _run_command(
        FOCUSED_TEST_COMMAND,
        repo_root=root,
        sanitize_pytest_environment=True,
    )
    focused_tests.update(_parse_focused_summary(stdout, stderr))
    focused_tests["stdout_text"] = stdout
    poetry_check, stdout, stderr = _run_command(POETRY_CHECK_COMMAND, repo_root=root)
    if stdout != "All set!\n" or stderr:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW poetry-check output drifted"
        )
    publication_guard, stdout, stderr = _run_command(
        PUBLICATION_GUARD_COMMAND, repo_root=root
    )
    if stdout != (
        "Checking tracked files before publication...\n"
        "OK: tracked files look publication-ready.\n"
    ) or stderr:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW publication-guard output drifted"
        )
    git_diff_check, stdout, stderr = _run_command(DIFF_CHECK_COMMAND, repo_root=root)
    if stdout or stderr:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW git diff-check output drifted"
        )
    historical_a0_semantic_audit = _audit_historical_a0_semantics(root)
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
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW {context} evidence dialect drifted"
        )
    if value.get("command") != list(expected_command) or value.get("returncode") != 0:
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW {context} command/result drifted"
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
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW {context} digest/line evidence drifted"
        )
    if exact_stdout is not None and (
        value.get("stdout_sha256") != _sha256_bytes(exact_stdout.encode("utf-8"))
        or value.get("stdout_line_count") != len(exact_stdout.splitlines())
    ):
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW {context} stdout evidence drifted"
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW verification dialect drifted"
        )
    expected_preflight = preflight_anfis_ablation_model_publication_patch_schema(
        repo_root=repo_root
    )
    if not _exact_equal(value.get("schema_preflight"), expected_preflight):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW schema-preflight evidence drifted"
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW focused-test evidence dialect drifted"
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW focused stdout is absent"
        )
    parsed = _parse_focused_summary(stdout_text, "")
    if (
        focused.get("stdout_sha256") != _sha256_bytes(stdout_text.encode("utf-8"))
        or focused.get("stdout_line_count") != len(stdout_text.splitlines())
        or {key: focused.get(key) for key in parsed} != parsed
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW focused-test stdout binding drifted"
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW historical A0 semantic-audit evidence drifted"
        )
    expected_boundaries = {
        "development_targets_through_2020_read_during_verification": True,
        "historical_a0_semantic_audit_run": True,
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW verification execution boundaries drifted"
        )


def _expected_prelock() -> dict[str, Any]:
    expected = dict(mv._expected_prelock())
    expected["control_paths"] = {
        "mw_lock_absent": True,
        "mw_companion_absent": True,
        "mw_lock_temp_absent": True,
        "mw_companion_temp_absent": True,
        "mw_locker_guard_absent": True,
        "blocked_mv_lock_absent": True,
        "blocked_mv_companion_absent": True,
        "p_mu_lock_present": True,
        "p_mu_companion_present": True,
    }
    return expected


def validate_anfis_ablation_model_publication_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    allow_registered_pointers: bool = False,
    repo_root: Path | None = None,
) -> None:
    if type(allow_registered_pointers) is not bool:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW registered-pointer policy must be an exact boolean"
        )
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise AnfisAblationModelPublicationPatchError(str(exc)) from exc
    _validate_timestamp(payload.get("created_at_utc"))
    if not _exact_equal(payload.get("authorizations"), UNPUBLISHED_AUTHORIZATIONS):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW unpublished authorizations drifted"
        )
    if not _exact_equal(payload.get("seals"), LOCK_SEALS):
        raise AnfisAblationModelPublicationPatchError("E0-MW seals drifted")
    if not _exact_equal(payload.get("blocked_p_mv_attempt"), _blocked_p_mv_attempt()):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW blocked P-E0-MV incident metadata drifted"
        )
    repository = payload.get("repository")
    h_patch = payload.get("h_patch")
    if not isinstance(repository, Mapping) or not isinstance(h_patch, Mapping):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW repository/H binding is absent"
        )
    h_head = repository.get("head")
    expected_scope = {
        "added": 5,
        "modified": 5,
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
        != "exact_historical_a0_light_outputs_only"
        or _single_parent(root, h_head, context="H-E0-MW") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, h_head) != expected_scope
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW repository/H topology drifted"
        )
    _require_exact_git_modes(
        root, h_head, PATCH_COMPONENT_GIT_MODES, context="H-E0-MW"
    )
    h_components = _h_mw_components(h_head, root)
    expected_h = {
        "base_commit": BASE_COMMIT,
        "head": h_head,
        "parent": BASE_COMMIT,
        "component_count": 10,
        "components": h_components,
        "components_sha256": _digest_records(h_components),
        "components_git_modes": dict(PATCH_COMPONENT_GIT_MODES),
        "scope": {"added": 5, "modified": 5, "deleted": 0},
    }
    if not _exact_equal(h_patch, expected_h):
        raise AnfisAblationModelPublicationPatchError("E0-MW H binding drifted")
    base_authority = _base_mv_authority(root)
    if not _exact_equal(payload.get("base_mv_authority"), base_authority):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW H-E0-MV/P-E0-MU reconstruction drifted"
        )
    try:
        adopted = mv._historical_a0_bundle(
            root, allow_registered_pointer=allow_registered_pointers
        )
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc
    if not _exact_equal(payload.get("adopted_a0_bundle"), adopted):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW adopted A0/1729 binding drifted"
        )
    if not _exact_equal(payload.get("manifest_dialect"), _expected_manifest_dialect()):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW model-manifest dialect drifted"
        )
    physical_inputs = _companion_physical_inputs(
        h_components=h_components, base_authority=base_authority
    )
    historical_inputs = _historical_mv_inputs(root)
    expected_contract = {
        "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
        "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
        "output_count": 1,
        "script_path": LOCKER_PATH.as_posix(),
        "physical_inputs_sha256": _digest_records(physical_inputs),
        "historical_inputs_sha256": _digest_records(historical_inputs),
        "blocked_p_mv_in_inputs": False,
        "historical_a0_outputs_in_inputs": False,
        "manifest_written_last": True,
    }
    if not _exact_equal(payload.get("companion_contract"), expected_contract):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW companion contract drifted"
        )
    if not _exact_equal(payload.get("prelock"), _expected_prelock()):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW complete prelock binding drifted"
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
    base_authority = payload.get("base_mv_authority")
    if not isinstance(h_patch, Mapping) or not isinstance(base_authority, Mapping):
        raise AnfisAblationModelPublicationPatchError(
            "Cannot construct E0-MW companion sections"
        )
    h_components = h_patch.get("components")
    if not isinstance(h_components, list):
        raise AnfisAblationModelPublicationPatchError(
            "Cannot construct E0-MW companion component records"
        )
    inputs = _companion_physical_inputs(
        h_components=cast(list[dict[str, Any]], h_components),
        base_authority=base_authority,
    )
    historical_inputs = _historical_mv_inputs(root)
    if (
        len(historical_inputs) != EXPECTED_HISTORICAL_INPUT_COUNT
        or len({str(record.get("path")) for record in historical_inputs})
        != EXPECTED_HISTORICAL_INPUT_COUNT
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW companion must bind exactly five historical H-E0-MV inputs"
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW companion generating script is absent"
        )
    try:
        output = mv._validate_role_record(lock_record)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc
    if (
        output.get("path") != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or output.get("role") != "anfis_ablation_model_publication_patch_lock"
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW companion lock output record drifted"
        )
    blocked_paths = {BLOCKED_P_MV_LOCK_PATH, BLOCKED_P_MV_COMPANION_PATH}
    if blocked_paths.intersection(
        str(record.get("path")) for record in (*inputs, *historical_inputs)
    ):
        raise AnfisAblationModelPublicationPatchError(
            "Blocked P-E0-MV attempt leaked into E0-MW companion inputs"
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
        "historical_a0_outputs_in_inputs": False,
        "adopted_a0_bundle_rewritten": False,
        "manifest_written_last": True,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "scientific_network_commands_run": False,
        "historical_a0_semantic_audit_run": True,
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
) -> None:
    repository = payload.get("repository")
    h_patch = payload.get("h_patch")
    base_authority = payload.get("base_mv_authority")
    if not all(
        isinstance(section, Mapping)
        for section in (repository, h_patch, base_authority)
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW guarded publication sections are absent"
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW guarded Git refs drifted"
        )
    h_components = _h_mw_components(h_head, repo_root)
    if not _exact_equal(h_patch.get("components"), h_components):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW guarded H components drifted"
        )
    live_base = _base_mv_authority(repo_root)
    if not _exact_equal(base_authority, live_base):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW guarded H-E0-MV/P-E0-MU reconstruction drifted"
        )
    try:
        live_a0 = mv._historical_a0_bundle(repo_root)
        live_namespace = mv._training_namespace_state(repo_root)
    except mv.AnfisAblationModelManifestPatchError as exc:
        raise _translate(exc) from exc
    if not _exact_equal(payload.get("adopted_a0_bundle"), live_a0):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW guarded adopted A0/1729 bundle drifted"
        )
    physical_inputs = _companion_physical_inputs(
        h_components=h_components, base_authority=live_base
    )
    historical_inputs = _historical_mv_inputs(repo_root)
    contract = payload.get("companion_contract")
    if (
        not isinstance(contract, Mapping)
        or contract.get("physical_input_count") != EXPECTED_COMPANION_INPUT_COUNT
        or contract.get("historical_input_count") != EXPECTED_HISTORICAL_INPUT_COUNT
        or contract.get("physical_inputs_sha256") != _digest_records(physical_inputs)
        or contract.get("historical_inputs_sha256")
        != _digest_records(historical_inputs)
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW guarded companion digests drifted"
        )
    expected_prelock = payload.get("prelock")
    if not isinstance(expected_prelock, Mapping) or any(
        not _exact_equal(expected_prelock.get(key), value)
        for key, value in live_namespace.items()
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW guarded training namespace drifted"
        )
    live_prohibited = _prohibited_namespace_state(repo_root)
    if not all(live_prohibited.values()) or not _exact_equal(
        expected_prelock.get("prohibited_namespaces"), live_prohibited
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW guarded scientific boundary drifted"
        )
    stable_controls = _control_namespace_state(repo_root)
    for key in (
        "blocked_mv_lock_absent",
        "blocked_mv_companion_absent",
        "p_mu_lock_present",
        "p_mu_companion_present",
    ):
        if stable_controls.get(key) is not True:
            raise AnfisAblationModelPublicationPatchError(
                f"E0-MW guarded stable control drifted: {key}"
            )
    expected_paths = {
        *HISTORICAL_A0_LIGHT_PATHS,
        *(path.as_posix() for path in expected_published_outputs),
    }
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
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW guarded worktree scope drifted: {status_lines}"
        )
    controlled_temporaries = (
        _temporary_path(DEFAULT_PATCH_LOCK_PATH),
        _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
    )
    if any(_lexists(repo_root / path) for path in controlled_temporaries):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW guarded publication temporary appeared"
        )


def execute_and_publish_anfis_ablation_model_publication_patch_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconstruct, verify once, and atomically publish P-E0-MW."""
    root = _root(repo_root)
    schema_preflight = preflight_anfis_ablation_model_publication_patch_schema(
        repo_root=root
    )
    before = collect_anfis_ablation_model_publication_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    verification = run_anfis_ablation_model_publication_patch_verification(
        expected_schema_preflight=schema_preflight, repo_root=root
    )
    after = collect_anfis_ablation_model_publication_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    if not _exact_equal(before, after):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW prelock state changed during verification"
        )
    payload = build_anfis_ablation_model_publication_patch_lock_payload(
        before,
        verification,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    validate_anfis_ablation_model_publication_patch_lock_payload(
        payload, repo_root=root
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
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW lock namespace is occupied: {occupied}"
        )
    guard: mt._OwnedGuard | None = None
    published: list[mt._OwnedOutput] = []
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MW lock bundle publication in progress\n",
            repo_root=root,
        )
        _revalidate_publication_state_under_guard(
            payload, repo_root=root, expected_published_outputs=()
        )
        lock_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH,
            _canonical_json(dict(payload)),
            repo_root=root,
        )
        published.append(lock_output)
        lock_record = _file_record(
            DEFAULT_PATCH_LOCK_PATH,
            role="anfis_ablation_model_publication_patch_lock",
            repo_root=root,
        )
        companion = _expected_companion(payload, lock_record, repo_root=root)
        companion_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            _canonical_json(companion),
            repo_root=root,
        )
        published.append(companion_output)
        if not _exact_equal(
            _load_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root), dict(payload)
        ) or not _exact_equal(
            _load_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root), companion
        ):
            raise AnfisAblationModelPublicationPatchError(
                "Published E0-MW bundle differs from its payloads"
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
        )
        for output in published:
            mt._validate_owned_output(output)
        mt._release_publication_guard(guard)
        guard = None
        for output in published:
            mt._validate_owned_output(output)
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


def publish_anfis_ablation_model_publication_patch_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Safe writer alias; caller-supplied payloads are intentionally impossible."""
    return execute_and_publish_anfis_ablation_model_publication_patch_lock_bundle(
        repo_root=repo_root
    )


def _validate_p_publication(
    payload: Mapping[str, Any], *, repo_root: Path
) -> dict[str, str]:
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("head"), str
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW H repository binding is absent"
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
        or _single_parent(repo_root, head, context="P-E0-MW") != h_head
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
        raise AnfisAblationModelPublicationPatchError(
            "Published P-E0-MW topology/refs drifted"
        )
    _require_git_modes(repo_root, head, expected_paths, context="P-E0-MW")
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
        mv.MU_H_HEAD,
        "src/experiments/train_closure_anfis_ablation.py",
        role="trainer",
    )


def _validate_completed_mw_slot(
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW completed-slot pointer policy must be an exact boolean"
        )
    paths = mt.anfis_ablation_training_slot_paths(model_id, base_seed)
    manifest_bytes = _read_regular_bytes(paths["manifest"], repo_root=repo_root)
    manifest = _strict_json(
        manifest_bytes, label=f"E0-MW model manifest {model_id}/{base_seed}"
    )
    expected_binding = _slot_manifest_binding(
        static, model_id=model_id, base_seed=base_seed, index=target_index
    )
    if (
        not manifest
        or next(reversed(manifest)) != "completion_marker_written_last"
        or manifest_bytes != mv._model_manifest_json(manifest)
        or not _exact_equal(manifest.get("authority"), expected_binding)
        or manifest.get("model_id") != model_id
        or manifest.get("base_seed") != base_seed
        or manifest.get("status") != "completed"
        or manifest.get("slot_status") != "available"
        or manifest.get("fit_status") != "passed"
        or manifest.get("completion_marker_written_last") is not True
    ):
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW completed slot manifest drifted: {model_id}/{base_seed}"
        )
    expected_outputs = [
        _file_record(path, role=name, repo_root=repo_root)
        for name, path in paths.items()
        if name != "manifest"
    ]
    if not _exact_equal(manifest.get("outputs"), expected_outputs):
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW completed slot outputs drifted: {model_id}/{base_seed}"
        )
    trainer = _current_trainer_record(repo_root)
    if not _exact_equal(manifest.get("script"), trainer) or not _exact_equal(
        manifest.get("source_code"), [trainer]
    ):
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW completed slot source drifted: {model_id}/{base_seed}"
        )
    expected_authority_records = [
        dict(cast(Mapping[str, Any], static["runtime"])),
        dict(cast(Mapping[str, Any], static["lock"])),
        dict(cast(Mapping[str, Any], static["companion"])),
    ]
    if not _exact_equal(manifest.get("authority_records"), expected_authority_records):
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW completed slot authority records drifted: {model_id}/{base_seed}"
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
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW completed slot failed semantic audit: {model_id}/{base_seed}"
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
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW completed slot semantic evidence drifted: {model_id}/{base_seed}"
        )


def _slot_light_paths(paths: Mapping[str, Path]) -> set[str]:
    if set(LIGHT_SLOT_OUTPUT_NAMES) - set(paths):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW slot path dialect is missing light outputs"
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW prefix audit mode must be an exact boolean"
        )
    complete: list[bool] = []
    pointer_presence: list[bool] = []
    slot_paths: list[dict[str, Path]] = []
    for model_id, base_seed in ORDERED_SLOTS:
        paths = mt.anfis_ablation_training_slot_paths(model_id, base_seed)
        slot_paths.append(paths)
        observed = [_lexists(repo_root / path) for path in paths.values()]
        if any(observed) and not all(observed):
            raise AnfisAblationModelPublicationPatchError(
                f"E0-MW partial slot exists: {model_id}/{base_seed}"
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
            raise AnfisAblationModelPublicationPatchError(
                f"E0-MW prohibited temporary/guard exists: {model_id}/{base_seed}"
            )
    prefix = 0
    while prefix < len(complete) and complete[prefix]:
        prefix += 1
    if prefix < 1 or any(complete[prefix:]):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW completed slots do not form the exact adopted prefix"
        )
    registered = any(pointer_presence)
    if registered and (
        not audit_mode or prefix != len(ORDERED_SLOTS) or not all(pointer_presence)
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW pointers require the complete explicit post-registration audit"
        )
    target_reference: Any | None = None
    expected_light_paths: set[str] = set()
    for index, (model_id, base_seed) in enumerate(ORDERED_SLOTS[:prefix]):
        paths = slot_paths[index]
        expected_light_paths.update(_slot_light_paths(paths))
        if index == 0:
            try:
                mv._historical_a0_bundle(
                    repo_root, allow_registered_pointer=registered
                )
            except mv.AnfisAblationModelManifestPatchError as exc:
                raise _translate(exc) from exc
        else:
            if target_reference is None:
                from src.experiments.audit_closure_anfis_ablation_model_bundle import (
                    load_cutoff_target_reference,
                )

                target_reference = load_cutoff_target_reference(repo_root=repo_root)
            _validate_completed_mw_slot(
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
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW progression crossed E0-M/outcome boundary"
        )
    status_lines = [
        line
        for line in _git(
            repo_root, "status", "--porcelain", "--untracked-files=all"
        ).splitlines()
        if line
    ]
    if not registered:
        expected_status = [f"?? {path}" for path in sorted(expected_light_paths)]
        if status_lines != expected_status:
            raise AnfisAblationModelPublicationPatchError(
                f"E0-MW unregistered slot status drifted: {status_lines}"
            )
        return prefix
    allowed_registered_paths = {
        *expected_light_paths,
        *(mt._pointer_path(model, seed).as_posix() for model, seed in ORDERED_SLOTS),
        "models.dvc",
    }
    for line in status_lines:
        if (
            len(line) < 4
            or line[:2] not in {"??", "A ", " M", "M "}
            or line[3:] not in allowed_registered_paths
        ):
            raise AnfisAblationModelPublicationPatchError(
                f"E0-MW post-registration worktree drifted: {line}"
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


def load_effective_anfis_ablation_model_publication_patch_authority(
    *,
    model_id: str | None = None,
    base_seed: int | None = None,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if type(audit_current_unpublished) is not bool:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW audit mode must be an exact boolean"
        )
    target_supplied = model_id is not None or base_seed is not None
    if target_supplied and (model_id is None or base_seed is None):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW target model/seed is incomplete"
        )
    if audit_current_unpublished and not target_supplied:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW audit mode requires one explicit target"
        )
    if target_supplied:
        if type(model_id) is not str or type(base_seed) is not int:
            raise AnfisAblationModelPublicationPatchError(
                "E0-MW target model/seed types drifted"
            )
        try:
            mt.validate_model_seed(model_id, base_seed)
        except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
            raise _translate(exc) from exc
    if verify_remote is not True:
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW effective authority requires live remote verification"
        )
    root = _root(repo_root)
    payload_bytes = _read_regular_bytes(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    payload = _strict_json(payload_bytes, label="P-E0-MW lock")
    if payload_bytes != _canonical_json(payload):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW lock is not canonical JSON"
        )
    pointer_presence = [
        _lexists(root / mt._pointer_path(slot_model, slot_seed))
        for slot_model, slot_seed in ORDERED_SLOTS
    ]
    allow_registered_pointers = audit_current_unpublished and all(pointer_presence)
    validate_anfis_ablation_model_publication_patch_lock_payload(
        payload,
        allow_registered_pointers=allow_registered_pointers,
        repo_root=root,
    )
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="anfis_ablation_model_publication_patch_lock",
        repo_root=root,
    )
    companion_bytes = _read_regular_bytes(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    companion_payload = _strict_json(companion_bytes, label="P-E0-MW companion")
    if (
        companion_bytes != _canonical_json(companion_payload)
        or not _exact_equal(
            companion_payload,
            _expected_companion(payload, lock_record, repo_root=root),
        )
    ):
        raise AnfisAblationModelPublicationPatchError(
            "E0-MW lock companion drifted"
        )
    companion_record = _file_record(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        role="anfis_ablation_model_publication_patch_lock_manifest",
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
        raise AnfisAblationModelPublicationPatchError(
            f"E0-MW target is not in the exact {mode} position"
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
    return load_effective_anfis_ablation_model_publication_patch_authority(
        model_id=model_id,
        base_seed=base_seed,
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


def require_anfis_ablation_model_publication_patch_authority(
    model_id: str,
    base_seed: int,
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    return load_effective_anfis_ablation_model_publication_patch_authority(
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
    return require_anfis_ablation_model_publication_patch_authority(
        model_id,
        base_seed,
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


__all__ = [
    "AnfisAblationModelPublicationPatchError",
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
    "SUPERSEDED_MV_PATHS",
    "build_anfis_ablation_model_publication_patch_lock_payload",
    "collect_anfis_ablation_model_publication_patch_prelock_state",
    "execute_and_publish_anfis_ablation_model_publication_patch_lock_bundle",
    "load_effective_anfis_ablation_model_publication_authority",
    "load_effective_anfis_ablation_model_publication_patch_authority",
    "preflight_anfis_ablation_model_publication_patch_schema",
    "publish_anfis_ablation_model_publication_patch_lock_bundle",
    "require_anfis_ablation_model_publication_authority",
    "require_anfis_ablation_model_publication_patch_authority",
    "run_anfis_ablation_model_publication_patch_verification",
    "validate_anfis_ablation_model_publication_patch_lock_payload",
]
