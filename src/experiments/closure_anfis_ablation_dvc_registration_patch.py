"""Fail-closed E0-MY authority for the ten-slot ANFIS DVC registration.

E0-MY is administrative and development-only.  H/P-E0-MY never invoke DVC,
fit a model, open calibration targets, evaluate a model, or access outcomes.
After an exact P publication the effective loader authorizes only the closed
local ``dvc add`` target set consumed by the publication assistant.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

import yaml

from src.experiments import (
    closure_anfis_ablation_model_publication_adoption_patch as mx,
)
from src.experiments import closure_anfis_ablation_training_development_patch as mt
from src.experiments import closure_contract
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = mx.PROJECT_ROOT
BASE_COMMIT = "c73b8ebe11d942631d24e43b0eac2f4b2e72e400"
BASE_H_MX_COMMIT = "8b4452bdca930a7b1ac1a7094f0c2b36e7d5d559"
PATCH_GATE = "E0-MY"
SCHEMA_VERSION = "closure_anfis_ablation_dvc_registration_patch_lock_v1"
COMPANION_VERSION = (
    "closure_anfis_ablation_dvc_registration_patch_lock_manifest_v1"
)

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/anfis_ablation_dvc_registration_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_PATH = Path(
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_patch.py"
)
LOCKER_GUARD_PATH = Path("tmp/closure_v1_e0_my_locker/registration_patch.lock")
REGISTRATION_GUARD_PATH = Path(
    "tmp/closure_v1_anfis_ablation_dvc_registration.guard"
)
REGISTRATION_MODELS_BACKUP_PATH = Path(
    "tmp/closure_v1_anfis_ablation_models_dvc_baseline"
)
REGISTRATION_MODELS_BYTES_BACKUP_PATH = Path(
    "tmp/closure_v1_anfis_ablation_models_dvc_baseline_bytes"
)
REGISTRATION_DVC_GLOBAL_CONFIG_PATH = Path(
    "tmp/closure_v1_anfis_ablation_dvc_global_config"
)
REGISTRATION_DVC_SYSTEM_CONFIG_PATH = Path(
    "tmp/closure_v1_anfis_ablation_dvc_system_config"
)

PATCH_COMPONENT_ROLES = {
    "configs/closure_v1/anfis_ablation_dvc_registration_patch_lock.schema.json": (
        "anfis_ablation_dvc_registration_patch_schema"
    ),
    "configs/closure_v1/dvc_artifacts_post_lock.yaml": (
        "closure_v1_post_lock_dvc_inventory"
    ),
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_PATCH_1.md": (
        "anfis_ablation_dvc_registration_patch_protocol"
    ),
    "src/data/prepare_commit_artifacts.py": "precommit_artifact_assistant",
    "src/experiments/closure_anfis_ablation_dvc_registration_patch.py": (
        "anfis_ablation_dvc_registration_patch_validator"
    ),
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_patch.py": (
        "anfis_ablation_dvc_registration_patch_locker"
    ),
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py": (
        "anfis_ablation_dvc_registration_patch_test"
    ),
    "tests/test_closure_anfis_ablation_model_publication_patch.py": (
        "anfis_ablation_model_publication_patch_test"
    ),
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py": (
        "anfis_ablation_model_publication_adoption_patch_test"
    ),
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_ADDED_PATHS = tuple(
    path
    for path in PATCH_PATHS
    if path
    not in {
        "configs/closure_v1/dvc_artifacts_post_lock.yaml",
        "src/data/prepare_commit_artifacts.py",
        "tests/test_closure_anfis_ablation_model_publication_patch.py",
        "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
    }
)
PATCH_MODIFIED_PATHS = tuple(
    path for path in PATCH_PATHS if path not in set(PATCH_ADDED_PATHS)
)
PATCH_COMPONENT_GIT_MODES = {
    path: "100755" if path == "src/data/prepare_commit_artifacts.py" else "100644"
    for path in PATCH_PATHS
}
ANFIS_ABLATION_H_MY_STAGED_SCOPE = {
    path: ("A" if path in set(PATCH_ADDED_PATHS) else "M") for path in PATCH_PATHS
}
ANFIS_ABLATION_P_MY_STAGED_SCOPE = {
    DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
    DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
}

BASE_MX_LOCK_PATH = mx.DEFAULT_PATCH_LOCK_PATH
BASE_MX_COMPANION_PATH = mx.DEFAULT_PATCH_LOCK_MANIFEST_PATH
DVC_INVENTORY_PATH = Path("configs/closure_v1/dvc_artifacts_post_lock.yaml")
DVC_CONFIG_PATH = Path(".dvc/config")
DVC_CONFIG_LOCAL_PATH = Path(".dvc/config.local")
MODELS_DVC_PATH = Path("models.dvc")
MODELS_PATH = Path("models")
OUTCOME_ACCESS_LOG = mx.OUTCOME_ACCESS_LOG
E0_M_PATHS = mx.E0_M_PATHS
ORDERED_SLOTS = mx.ORDERED_SLOTS
SLOT_ROLE_ORDER = (
    "model",
    "checkpoint",
    "preprocessor",
    "training_curve",
    "selection_predictions",
    "selection_metrics",
    "report",
    "manifest",
)
LIGHT_SLOT_ROLES = frozenset(
    {"preprocessor", "training_curve", "selection_metrics", "report", "manifest"}
)
HEAVY_SLOT_ROLES = frozenset({"model", "checkpoint", "selection_predictions"})
FAMILY_FINAL_COUNT = 80
FAMILY_LIGHT_COUNT = 50
FAMILY_TRACKED_LIGHT_COUNT = 5
FAMILY_UNTRACKED_LIGHT_COUNT = 45
FAMILY_HEAVY_COUNT = 30
FAMILY_POINTER_COUNT = 10
FAMILY_RECORDS_SHA256 = (
    "e625add8f8af1746f7deda9ff13a84a4d4f4c27b47e3b6312922db419508dd8e"
)
ANFIS_ABLATION_R_MY_STAGED_SCOPE = {
    **{
        f"reports/closure_v1/02_models/{model_id}/seed_{base_seed}_{suffix}": "A"
        for model_id, base_seed in ORDERED_SLOTS
        for suffix in (
            "preprocessor.json",
            "training_curve.csv",
            "selection_metrics.csv",
            "report.md",
            "manifest.json",
        )
        if not (model_id == "A0" and base_seed == 1729)
    },
    **{
        (
            "data/closure_v1/development/anfis_ablation/"
            f"{model_id}/seed_{base_seed}_selection_predictions.parquet.dvc"
        ): "A"
        for model_id, base_seed in ORDERED_SLOTS
    },
    "models.dvc": "M",
}

GENERAL_ARTIFACT_COUNT = 23
REGISTRATION_ARTIFACT_COUNT = 10
REGISTRATION_INVENTORY_KEY = "anfis_ablation_registration_artifacts"
REGISTRATION_ARTIFACT_TYPE = "closure_anfis_ablation_selection_predictions"
REGISTRATION_GITHUB_POLICY = (
    "pointer_only_keep_manifest_and_lightweight_reports_in_git"
)

BASE_MODELS_DVC_BYTES = 109
BASE_MODELS_DVC_SHA256 = (
    "fcb93f78cc3e60c1c7f5bcc94a1765080358e0a5176880f1efa6245fa5365e5d"
)
BASE_MODELS_DIR_MD5 = "fc60851634c1345cc5dc2c9169be9e1c"
BASE_MODELS_SIZE = 124_717_666
BASE_MODELS_NFILES = 248
EXPECTED_MODELS_DIR_MD5 = "6b8d7c0a8efcd8de2888d684a0cb285b"
EXPECTED_MODELS_SIZE = 127_680_846
EXPECTED_MODELS_NFILES = 268
EXPECTED_MODELS_DVC_BYTES = 109
EXPECTED_MODELS_DVC_SHA256 = (
    "5fbe07e09ddae260b9fa395b8bfaf15a7b71445e3e179e2734bfa4b345964b74"
)

EXPECTED_COMPANION_INPUT_COUNT = 11
EXPECTED_HISTORICAL_INPUT_COUNT = 4
EXPECTED_REGISTRATION_GIT_PATH_COUNT = 56
EXPECTED_REGISTRATION_ADDED_COUNT = 55
EXPECTED_REGISTRATION_MODIFIED_COUNT = 1
DVC_CONFIG_BYTES = 43
DVC_CONFIG_SHA256 = (
    "cb08c869a906d07c5b1ccf593299a0f253e0ce03303c43070b6a68124b27fda0"
)
DVC_CONFIG_LOCAL_BYTES = 211
DVC_CONFIG_LOCAL_SHA256 = (
    "a912c374690215c7753070f68d7dfdaff8c1224b01c336aa887d6731a3bb2287"
)

TYPE_CHECK_COMMAND = ("poetry", "run", "ty", "check")
FOCUSED_TEST_COMMAND = (
    "poetry",
    "run",
    "pytest",
    "-q",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
    "tests/test_prepare_commit_artifacts.py",
)
# Synchronized after the H tests are collected; the validator also rejects a
# summary whose count differs from the evidence embedded by the locker.
FOCUSED_TEST_COUNT = 116
FOCUSED_PYTEST_ENVIRONMENT = {
    "PYTEST_ADDOPTS": "",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PYTEST_PLUGINS": "",
    "PY_COLORS": "0",
}
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MD5_RE = re.compile(r"^[0-9a-f]{32}$")
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
FOCUSED_SUMMARY_RE = re.compile(
    r"^(?P<count>[1-9][0-9]*) passed in (?P<seconds>[0-9]+(?:\.[0-9]+)?)s"
    r"(?: \([0-9]+:[0-5][0-9]:[0-5][0-9]\))?$"
)
FORBIDDEN_FOCUSED_SUMMARY_RE = re.compile(
    r"\b(?:warning|warnings|failed|error|errors|skipped|deselected|xfailed|xpassed)\b",
    re.IGNORECASE,
)

UNPUBLISHED_AUTHORIZATIONS = {
    "dvc_add_models_and_selection_predictions_authorized": False,
    "dvc_push_authorized": False,
    "git_commit_authorized": False,
    "git_push_authorized": False,
    "model_fit_authorized": False,
    "model_replay_or_replacement_authorized": False,
    "calibration_authorized": False,
    "calibration_target_access_authorized": False,
    "evaluation_authorized": False,
    "e0_m_authorized": False,
    "e0_u_authorized": False,
    "outcome_access_authorized": False,
    "scientific_network_authorized": False,
}
LOCK_SEALS = {
    "complete_ten_slot_family_required": True,
    "exact_eighty_finals_required": True,
    "exact_ten_selection_pointers_absent_at_lock": True,
    "models_dvc_base_pointer_unchanged_at_lock": True,
    "registration_is_administrative_only": True,
    "registration_target_set_closed": True,
    "dvc_add_no_relink_required": True,
    "dvc_config_isolation_required": True,
    "registration_requires_published_p_my": True,
    "h_p_run_no_dvc_commands": True,
    "h_p_run_no_model_fit": True,
    "calibration_and_evaluation_closed": True,
    "e0_m_and_e0_u_closed": True,
    "outcomes_closed": True,
    "manifest_written_last": True,
}


class AnfisAblationDvcRegistrationPatchError(RuntimeError):
    """Raised when E0-MY authority, artifacts, or topology drift."""


def _translate(exc: BaseException) -> AnfisAblationDvcRegistrationPatchError:
    return AnfisAblationDvcRegistrationPatchError(str(exc))


def _root(repo_root: Path | None) -> Path:
    return PROJECT_ROOT if repo_root is None else repo_root.resolve()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8") + b"\n"


def _digest_records(records: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(
            list(records),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _md5_bytes(payload: bytes) -> str:
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


def _exact_equal(left: Any, right: Any) -> bool:
    return type(left) is type(right) and _canonical_json(left) == _canonical_json(right)


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _temporary_path(path: Path) -> Path:
    return Path(f"{path.as_posix()}.tmp")


def _read_regular_bytes(
    path: Path, *, repo_root: Path, require_nlink_one: bool = True
) -> bytes:
    if path.is_absolute() or ".." in path.parts:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY path must remain repository-relative: {path.as_posix()}"
        )
    parent = repo_root
    for component in path.parts[:-1]:
        parent /= component
        try:
            parent_metadata = parent.lstat()
        except FileNotFoundError as exc:
            raise AnfisAblationDvcRegistrationPatchError(
                f"Required E0-MY parent is absent: {path.as_posix()}"
            ) from exc
        if not stat.S_ISDIR(parent_metadata.st_mode):
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY path has a non-directory or symlink ancestor: {path.as_posix()}"
            )
    candidate = repo_root / path
    try:
        metadata = candidate.lstat()
    except FileNotFoundError as exc:
        raise AnfisAblationDvcRegistrationPatchError(
            f"Required E0-MY path is absent: {path.as_posix()}"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o644
        or (require_nlink_one and metadata.st_nlink != 1)
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY path is not a regular 0644 file: {path.as_posix()}"
        )
    payload = candidate.read_bytes()
    post = candidate.lstat()
    if (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    ) != (
        post.st_dev,
        post.st_ino,
        post.st_mode,
        post.st_nlink,
        post.st_size,
        post.st_mtime_ns,
        post.st_ctime_ns,
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY path changed while read: {path.as_posix()}"
        )
    return payload


def _file_record(
    path: Path,
    *,
    role: str,
    repo_root: Path,
    require_nlink_one: bool = True,
) -> dict[str, Any]:
    payload = _read_regular_bytes(
        path, repo_root=repo_root, require_nlink_one=require_nlink_one
    )
    return {
        "role": role,
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _git(repo_root: Path, *arguments: str) -> str:
    return mx._git(repo_root, *arguments)


def _git_head(repo_root: Path, ref: str = "HEAD") -> str:
    return mx._git_head(repo_root, ref)


def _single_parent(repo_root: Path, commit: str, *, context: str) -> str:
    return mx._single_parent(repo_root, commit, context=context)


def _git_scope(repo_root: Path, parent: str, head: str) -> dict[str, Any]:
    return mx._git_scope(repo_root, parent, head)


def _git_blob_bytes(repo_root: Path, commit: str, path: Path) -> bytes:
    result = subprocess.run(
        ["git", "-C", repo_root.as_posix(), "show", f"{commit}:{path.as_posix()}"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0 or result.stderr:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY cannot reconstruct Git blob {commit}:{path.as_posix()}"
        )
    return result.stdout


def _live_remote_main_head(repo_root: Path) -> str:
    return mx._live_remote_main_head(repo_root)


def _historical_git_blob_record(
    path: str, *, role: str, commit: str, repo_root: Path
) -> dict[str, Any]:
    record = mx._historical_git_blob_record(
        repo_root, commit, path, role=role
    )
    return dict(record)


def _load_json(path: Path, *, repo_root: Path) -> dict[str, Any]:
    payload = _read_regular_bytes(path, repo_root=repo_root)
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY JSON cannot be decoded: {path.as_posix()}"
        ) from exc
    if not isinstance(value, dict):
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY JSON must be an object: {path.as_posix()}"
        )
    return value


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise AnfisAblationDvcRegistrationPatchError("E0-MY timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY timestamp is malformed"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY timestamp must be timezone-aware"
        )


def _slot_paths(model_id: str, base_seed: int) -> dict[str, Path]:
    paths = mt.anfis_ablation_training_slot_paths(model_id, base_seed)
    if set(paths) != set(SLOT_ROLE_ORDER):
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY slot path roles drifted: {model_id}/{base_seed}"
        )
    return paths


def _family_records(
    repo_root: Path,
    *,
    registered: bool = False,
    allow_locker_guard: bool = False,
    registration_transaction: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    _validate_family_namespace(
        registered=registered,
        repo_root=repo_root,
        allow_locker_guard=allow_locker_guard,
        registration_transaction=registration_transaction,
    )
    records: list[dict[str, Any]] = []
    for model_id, base_seed in ORDERED_SLOTS:
        paths = _slot_paths(model_id, base_seed)
        slot_records = [
            _file_record(
                paths[role], role=role, repo_root=repo_root, require_nlink_one=True
            )
            for role in SLOT_ROLE_ORDER
        ]
        manifest_stat = (repo_root / paths["manifest"]).lstat()
        other_mtimes = [
            (repo_root / paths[role]).lstat().st_mtime_ns
            for role in SLOT_ROLE_ORDER
            if role != "manifest"
        ]
        if manifest_stat.st_mtime_ns <= max(other_mtimes):
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY manifest-last order drifted: {model_id}/{base_seed}"
            )
        records.extend(slot_records)
    if len(records) != FAMILY_FINAL_COUNT or _digest_records(records) != FAMILY_RECORDS_SHA256:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY exact eighty-final family digest drifted"
        )
    return records


def _family_physical_snapshot(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Capture the exact local identity of all eighty immutable finals."""
    snapshot: list[dict[str, Any]] = []
    for model_id, base_seed in ORDERED_SLOTS:
        paths = _slot_paths(model_id, base_seed)
        for role in SLOT_ROLE_ORDER:
            path = paths[role]
            candidate = repo_root / path
            payload = _read_regular_bytes(
                path, repo_root=repo_root, require_nlink_one=True
            )
            metadata = candidate.lstat()
            snapshot.append(
                {
                    "path": path.as_posix(),
                    "device": int(metadata.st_dev),
                    "inode": int(metadata.st_ino),
                    "mode": int(metadata.st_mode),
                    "nlink": int(metadata.st_nlink),
                    "mtime_ns": int(metadata.st_mtime_ns),
                    "ctime_ns": int(metadata.st_ctime_ns),
                    "size": len(payload),
                    "sha256": _sha256_bytes(payload),
                }
            )
    if len(snapshot) != FAMILY_FINAL_COUNT:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY physical family snapshot must contain exact80 identities"
        )
    return tuple(snapshot)


def _require_family_physical_snapshot(
    expected: Sequence[Mapping[str, Any]], *, repo_root: Path, context: str
) -> None:
    if list(expected) != list(_family_physical_snapshot(repo_root)):
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY exact80 physical family changed {context}"
        )


def _light_paths() -> tuple[str, ...]:
    return tuple(
        _slot_paths(model_id, base_seed)[role].as_posix()
        for model_id, base_seed in ORDERED_SLOTS
        for role in SLOT_ROLE_ORDER
        if role in LIGHT_SLOT_ROLES
    )


def _selection_payload_paths() -> tuple[Path, ...]:
    return tuple(
        _slot_paths(model_id, base_seed)["selection_predictions"]
        for model_id, base_seed in ORDERED_SLOTS
    )


def _selection_pointer_paths() -> tuple[Path, ...]:
    return tuple(mt._pointer_path(model_id, base_seed) for model_id, base_seed in ORDERED_SLOTS)


def _dvc_add_commands() -> list[list[str]]:
    return [
        ["dvc", "add", "--no-relink", path.as_posix()]
        for path in (*_selection_payload_paths(), MODELS_PATH)
    ]


def _dvc_configuration_contract(repo_root: Path) -> dict[str, Any]:
    config = _file_record(
        DVC_CONFIG_PATH,
        role="dvc_repository_cache_configuration",
        repo_root=repo_root,
    )
    local = _file_record(
        DVC_CONFIG_LOCAL_PATH,
        role="dvc_local_remote_configuration",
        repo_root=repo_root,
    )
    if (
        config["bytes"] != DVC_CONFIG_BYTES
        or config["sha256"] != DVC_CONFIG_SHA256
        or local["bytes"] != DVC_CONFIG_LOCAL_BYTES
        or local["sha256"] != DVC_CONFIG_LOCAL_SHA256
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY DVC repository/local configuration drifted"
        )
    config_payload = _read_regular_bytes(DVC_CONFIG_PATH, repo_root=repo_root)
    local_payload = _read_regular_bytes(DVC_CONFIG_LOCAL_PATH, repo_root=repo_root)
    if config_payload != b'[cache]\n    type = "reflink,hardlink,copy"\n':
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY DVC cache-type policy drifted"
        )
    lowered_local = local_payload.lower()
    if b"[cache]" in lowered_local or b"autostage" in lowered_local:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY local DVC cache/autostage override is forbidden"
        )
    return {
        "repository_config": config,
        "local_config": local,
        "cache_type": "reflink,hardlink,copy",
        "no_relink_required": True,
        "local_cache_override_absent": True,
        "autostage_override_absent": True,
    }


def _family_final_paths() -> tuple[Path, ...]:
    return tuple(
        _slot_paths(model_id, base_seed)[role]
        for model_id, base_seed in ORDERED_SLOTS
        for role in SLOT_ROLE_ORDER
    )


def _training_guard_paths() -> tuple[Path, ...]:
    return tuple(
        Path(
            "tmp/closure_v1_anfis_ablation_training/"
            f"{model_id}_seed_{base_seed}.guard"
        )
        for model_id, base_seed in ORDERED_SLOTS
    )


def _forbidden_family_namespace_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            {
                *(_temporary_path(path) for path in _family_final_paths()),
                *(_temporary_path(path) for path in _selection_pointer_paths()),
                *_training_guard_paths(),
                _temporary_path(DEFAULT_PATCH_LOCK_PATH),
                _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
                LOCKER_GUARD_PATH,
                REGISTRATION_GUARD_PATH,
                REGISTRATION_MODELS_BACKUP_PATH,
                REGISTRATION_MODELS_BYTES_BACKUP_PATH,
                REGISTRATION_DVC_GLOBAL_CONFIG_PATH,
                REGISTRATION_DVC_SYSTEM_CONFIG_PATH,
            },
            key=lambda path: path.as_posix(),
        )
    )


def _require_exact_regular_tree(
    root_path: Path,
    expected_paths: Sequence[Path],
    *,
    repo_root: Path,
    context: str,
) -> None:
    expected_files: set[Path] = set()
    expected_directories: set[Path] = set()
    for path in expected_paths:
        try:
            relative = path.relative_to(root_path)
        except ValueError as exc:
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY {context} expected path escaped its root"
            ) from exc
        if relative == Path("."):
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY {context} expected file path is malformed"
            )
        expected_files.add(relative)
        parent = relative.parent
        while parent != Path("."):
            expected_directories.add(parent)
            parent = parent.parent

    directory = repo_root
    for component in root_path.parts:
        directory /= component
        try:
            metadata = directory.lstat()
        except FileNotFoundError as exc:
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY {context} root is absent: {root_path.as_posix()}"
            ) from exc
        if not stat.S_ISDIR(metadata.st_mode):
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY {context} root has a symlink/non-directory ancestor"
            )

    observed_files: set[Path] = set()
    observed_directories: set[Path] = set()

    def walk(physical: Path, relative_parent: Path) -> None:
        try:
            entries = sorted(os.scandir(physical), key=lambda entry: entry.name)
        except OSError as exc:
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY cannot walk exact {context} root"
            ) from exc
        for entry in entries:
            relative = (
                Path(entry.name)
                if relative_parent == Path(".")
                else relative_parent / entry.name
            )
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                if relative not in expected_directories:
                    raise AnfisAblationDvcRegistrationPatchError(
                        f"E0-MY {context} contains an unexpected directory: {relative}"
                    )
                observed_directories.add(relative)
                walk(Path(entry.path), relative)
            elif stat.S_ISREG(metadata.st_mode):
                if (
                    relative not in expected_files
                    or stat.S_IMODE(metadata.st_mode) != 0o644
                    or metadata.st_nlink != 1
                ):
                    raise AnfisAblationDvcRegistrationPatchError(
                        f"E0-MY {context} contains a foreign/non-0644 file: {relative}"
                    )
                observed_files.add(relative)
            else:
                raise AnfisAblationDvcRegistrationPatchError(
                    f"E0-MY {context} contains a symlink/nonregular entry: {relative}"
                )

    walk(repo_root / root_path, Path("."))
    if observed_files != expected_files or observed_directories != expected_directories:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY {context} tree does not contain its exact closed namespace"
        )


def _validate_family_namespace(
    *,
    registered: bool,
    repo_root: Path,
    allow_locker_guard: bool = False,
    registration_transaction: Mapping[str, Any] | None = None,
) -> None:
    if type(registered) is not bool or type(allow_locker_guard) is not bool:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY namespace policy must use exact booleans"
        )
    if registration_transaction is not None and not registered:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY transaction coordination is post-registration only"
        )
    model_root = Path("models/closure_v1/anfis_ablation")
    model_paths = tuple(
        _slot_paths(model_id, base_seed)[role]
        for model_id, base_seed in ORDERED_SLOTS
        for role in ("model", "checkpoint")
    )
    _require_exact_regular_tree(
        model_root,
        model_paths,
        repo_root=repo_root,
        context="model family",
    )
    for model_id in ("A0", "A1"):
        report_root = Path(f"reports/closure_v1/02_models/{model_id}")
        report_paths = tuple(
            _slot_paths(slot_model_id, base_seed)[role]
            for slot_model_id, base_seed in ORDERED_SLOTS
            if slot_model_id == model_id
            for role in SLOT_ROLE_ORDER
            if role in LIGHT_SLOT_ROLES
        )
        _require_exact_regular_tree(
            report_root,
            report_paths,
            repo_root=repo_root,
            context=f"{model_id} report family",
        )
    prediction_root = Path("data/closure_v1/development/anfis_ablation")
    prediction_paths = (
        (*_selection_payload_paths(), *_selection_pointer_paths())
        if registered
        else _selection_payload_paths()
    )
    _require_exact_regular_tree(
        prediction_root,
        prediction_paths,
        repo_root=repo_root,
        context="selection prediction family",
    )
    allowed_coordination = (
        _validate_registration_transaction_record(
            registration_transaction, repo_root=repo_root
        )
        if registration_transaction is not None
        else set()
    )
    occupied = []
    for path in _forbidden_family_namespace_paths():
        if path == LOCKER_GUARD_PATH and allow_locker_guard:
            guard = repo_root / path
            if _lexists(guard):
                metadata = guard.lstat()
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or stat.S_IMODE(metadata.st_mode) != 0o600
                    or metadata.st_nlink != 1
                ):
                    occupied.append(path.as_posix())
            continue
        if path in allowed_coordination:
            continue
        if _lexists(repo_root / path):
            occupied.append(path.as_posix())
    if occupied:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY ignored/coordination namespace is occupied: {occupied}"
        )


def _expected_pointer_bytes(payload_path: Path, *, repo_root: Path) -> bytes:
    payload = _read_regular_bytes(payload_path, repo_root=repo_root, require_nlink_one=True)
    return (
        "outs:\n"
        f"- md5: {_md5_bytes(payload)}\n"
        f"  size: {len(payload)}\n"
        "  hash: md5\n"
        f"  path: {payload_path.name}\n"
    ).encode("utf-8")


def _expected_models_dvc_bytes() -> bytes:
    return (
        "outs:\n"
        f"- md5: {EXPECTED_MODELS_DIR_MD5}.dir\n"
        f"  size: {EXPECTED_MODELS_SIZE}\n"
        f"  nfiles: {EXPECTED_MODELS_NFILES}\n"
        "  hash: md5\n"
        "  path: models\n"
    ).encode("utf-8")


def _base_models_dvc_bytes() -> bytes:
    payload = (
        "outs:\n"
        f"- md5: {BASE_MODELS_DIR_MD5}.dir\n"
        f"  size: {BASE_MODELS_SIZE}\n"
        f"  nfiles: {BASE_MODELS_NFILES}\n"
        "  hash: md5\n"
        "  path: models\n"
    ).encode("utf-8")
    if len(payload) != BASE_MODELS_DVC_BYTES or _sha256_bytes(payload) != BASE_MODELS_DVC_SHA256:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY sealed base models.dvc constants drifted"
        )
    return payload


def _coordination_identity_record(
    path: Path,
    *,
    expected_mode: int,
    expected_payload: bytes,
    repo_root: Path,
) -> dict[str, Any]:
    if path.is_absolute() or ".." in path.parts:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY coordination path escaped the repository"
        )
    parent = repo_root
    for component in path.parts[:-1]:
        parent /= component
        try:
            parent_metadata = parent.lstat()
        except FileNotFoundError as exc:
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY coordination parent is absent: {path.as_posix()}"
            ) from exc
        if not stat.S_ISDIR(parent_metadata.st_mode):
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY coordination ancestor is not a real directory: {path.as_posix()}"
            )
    candidate = repo_root / path
    try:
        before = candidate.lstat()
    except FileNotFoundError as exc:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY transaction coordination is absent: {path.as_posix()}"
        ) from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_IMODE(before.st_mode) != expected_mode
        or before.st_nlink != 1
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY transaction coordination identity drifted: {path.as_posix()}"
        )
    payload = candidate.read_bytes()
    after = candidate.lstat()
    identity = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    if identity != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ) or payload != expected_payload:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY transaction coordination bytes drifted: {path.as_posix()}"
        )
    return {
        "path": path.as_posix(),
        "device": int(after.st_dev),
        "inode": int(after.st_ino),
        "mode": stat.S_IMODE(after.st_mode),
        "nlink": int(after.st_nlink),
        "size": len(payload),
        "mtime_ns": int(after.st_mtime_ns),
        "ctime_ns": int(after.st_ctime_ns),
        "sha256": _sha256_bytes(payload),
    }


def _coordination_directory_record(
    path: Path, *, repo_root: Path
) -> dict[str, Any]:
    parent = repo_root
    for component in path.parts[:-1]:
        parent /= component
        try:
            parent_metadata = parent.lstat()
        except FileNotFoundError as exc:
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY coordination directory parent is absent: {path.as_posix()}"
            ) from exc
        if not stat.S_ISDIR(parent_metadata.st_mode):
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY coordination directory ancestor drifted: {path.as_posix()}"
            )
    candidate = repo_root / path
    try:
        before = candidate.lstat()
        entries = tuple(os.scandir(candidate))
        after = candidate.lstat()
    except OSError as exc:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY coordination directory is absent/unreadable: {path.as_posix()}"
        ) from exc
    if (
        not stat.S_ISDIR(before.st_mode)
        or stat.S_IMODE(before.st_mode) != 0o700
        or before.st_nlink != 2
        or entries
        or (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY coordination directory identity drifted: {path.as_posix()}"
        )
    return {
        "path": path.as_posix(),
        "device": int(after.st_dev),
        "inode": int(after.st_ino),
        "mode": stat.S_IMODE(after.st_mode),
        "nlink": int(after.st_nlink),
        "mtime_ns": int(after.st_mtime_ns),
        "ctime_ns": int(after.st_ctime_ns),
        "entry_count": 0,
    }


def _validate_registration_transaction_record(
    value: Mapping[str, Any], *, repo_root: Path
) -> set[Path]:
    if not isinstance(value, Mapping) or set(value) != {
        "mode",
        "guard",
        "bytes_backup",
        "anchor",
        "global_config_dir",
        "system_config_dir",
    }:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY private transaction record dialect drifted"
        )
    mode = value.get("mode")
    if mode not in {"in_place", "atomic_replace"}:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY private transaction mode drifted"
        )
    expected_guard = _coordination_identity_record(
        REGISTRATION_GUARD_PATH,
        expected_mode=0o600,
        expected_payload=b"E0-MY exact ANFIS-ablation DVC registration\n",
        repo_root=repo_root,
    )
    expected_bytes_backup = _coordination_identity_record(
        REGISTRATION_MODELS_BYTES_BACKUP_PATH,
        expected_mode=0o600,
        expected_payload=_base_models_dvc_bytes(),
        repo_root=repo_root,
    )
    if not _exact_equal(value.get("guard"), expected_guard) or not _exact_equal(
        value.get("bytes_backup"), expected_bytes_backup
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY private transaction identity record drifted"
        )
    expected_global_config = _coordination_directory_record(
        REGISTRATION_DVC_GLOBAL_CONFIG_PATH, repo_root=repo_root
    )
    expected_system_config = _coordination_directory_record(
        REGISTRATION_DVC_SYSTEM_CONFIG_PATH, repo_root=repo_root
    )
    if not _exact_equal(
        value.get("global_config_dir"), expected_global_config
    ) or not _exact_equal(value.get("system_config_dir"), expected_system_config):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY private DVC config-isolation record drifted"
        )
    allowed = {
        REGISTRATION_GUARD_PATH,
        REGISTRATION_MODELS_BYTES_BACKUP_PATH,
        REGISTRATION_DVC_GLOBAL_CONFIG_PATH,
        REGISTRATION_DVC_SYSTEM_CONFIG_PATH,
    }
    if mode == "in_place":
        if value.get("anchor") is not None or _lexists(
            repo_root / REGISTRATION_MODELS_BACKUP_PATH
        ):
            raise AnfisAblationDvcRegistrationPatchError(
                "E0-MY in-place transaction retained a hardlink anchor"
            )
    else:
        expected_anchor = _coordination_identity_record(
            REGISTRATION_MODELS_BACKUP_PATH,
            expected_mode=0o644,
            expected_payload=_base_models_dvc_bytes(),
            repo_root=repo_root,
        )
        if not _exact_equal(value.get("anchor"), expected_anchor):
            raise AnfisAblationDvcRegistrationPatchError(
                "E0-MY atomic transaction anchor record drifted"
            )
        allowed.add(REGISTRATION_MODELS_BACKUP_PATH)
    return allowed


def _expected_registration_records(repo_root: Path) -> dict[str, Any]:
    pointers: list[dict[str, Any]] = []
    for payload_path, pointer_path in zip(
        _selection_payload_paths(), _selection_pointer_paths(), strict=True
    ):
        pointer = _expected_pointer_bytes(payload_path, repo_root=repo_root)
        pointers.append(
            {
                "role": "selection_predictions_dvc_pointer",
                "path": pointer_path.as_posix(),
                "bytes": len(pointer),
                "sha256": _sha256_bytes(pointer),
                "payload_path": payload_path.as_posix(),
                "payload_md5": _md5_bytes(
                    _read_regular_bytes(
                        payload_path, repo_root=repo_root, require_nlink_one=True
                    )
                ),
            }
        )
    models = _expected_models_dvc_bytes()
    if len(models) != EXPECTED_MODELS_DVC_BYTES or _sha256_bytes(models) != EXPECTED_MODELS_DVC_SHA256:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY expected models.dvc dialect drifted"
        )
    return {
        "pointer_count": len(pointers),
        "pointers": pointers,
        "pointers_sha256": _digest_records(pointers),
        "models_dvc": {
            "role": "models_dvc_owner_after_registration",
            "path": MODELS_DVC_PATH.as_posix(),
            "bytes": len(models),
            "sha256": _sha256_bytes(models),
            "directory_md5": EXPECTED_MODELS_DIR_MD5,
            "size": EXPECTED_MODELS_SIZE,
            "nfiles": EXPECTED_MODELS_NFILES,
        },
    }


def _registration_inventory(repo_root: Path) -> dict[str, Any]:
    payload = _read_regular_bytes(DVC_INVENTORY_PATH, repo_root=repo_root)
    try:
        decoded = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY DVC ownership overlay cannot be decoded"
        ) from exc
    if not isinstance(decoded, dict) or set(decoded) != {
        "schema_version",
        "inventory_id",
        "description",
        "sealed_base_inventory",
        "artifacts",
        REGISTRATION_INVENTORY_KEY,
    }:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY DVC ownership overlay top-level dialect drifted"
        )
    historical_payload = _git_blob_bytes(
        repo_root, BASE_COMMIT, DVC_INVENTORY_PATH
    )
    try:
        historical = yaml.safe_load(historical_payload)
    except yaml.YAMLError as exc:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY historical DVC ownership inventory cannot be decoded"
        ) from exc
    if not isinstance(historical, dict):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY historical DVC ownership inventory is not an object"
        )
    base_current = {
        key: value
        for key, value in decoded.items()
        if key != REGISTRATION_INVENTORY_KEY
    }
    if not _exact_equal(base_current, historical):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY general DVC inventory differs from its P-E0-MX authority"
        )
    registration_marker = (
        f"\n{REGISTRATION_INVENTORY_KEY}:\n".encode("utf-8")
    )
    artifacts_marker = b"\nartifacts:\n"
    if payload.count(registration_marker) != 1:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY registration inventory byte overlay is not unique"
        )
    prefix, registration_tail = payload.split(registration_marker, maxsplit=1)
    if registration_tail.count(artifacts_marker) != 1:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY registration inventory byte boundary drifted"
        )
    _, historical_suffix = registration_tail.split(artifacts_marker, maxsplit=1)
    reconstructed_historical = prefix + artifacts_marker + historical_suffix
    if reconstructed_historical != historical_payload:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY P-E0-MX inventory bytes changed outside the additive key"
        )
    general = decoded.get("artifacts")
    registration = decoded.get(REGISTRATION_INVENTORY_KEY)
    if not isinstance(general, list) or len(general) != GENERAL_ARTIFACT_COUNT:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY general DVC inventory must remain exact23"
        )
    expected: list[dict[str, Any]] = []
    for model_id, base_seed in ORDERED_SLOTS:
        path = _slot_paths(model_id, base_seed)["selection_predictions"]
        expected.append(
            {
                "artifact_id": (
                    f"closure_v1_anfis_ablation_{model_id.lower()}_seed_"
                    f"{base_seed}_selection_predictions"
                ),
                "path": path.as_posix(),
                "type": REGISTRATION_ARTIFACT_TYPE,
                "source_id": "wqp",
                "model_id": model_id,
                "base_seed": base_seed,
                "dvc": True,
                "github_policy": REGISTRATION_GITHUB_POLICY,
            }
        )
    if registration != expected:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY registration inventory differs from exact ten-slot order"
        )
    return {
        "overlay": _file_record(
            DVC_INVENTORY_PATH,
            role="closure_v1_post_lock_dvc_inventory",
            repo_root=repo_root,
        ),
        "general_artifact_count": len(general),
        "registration_artifact_count": len(expected),
        "registration_artifacts": expected,
        "registration_artifacts_sha256": _digest_records(expected),
        "separate_top_level_registration_inventory": True,
    }


def _base_models_owner(repo_root: Path) -> dict[str, Any]:
    record = _file_record(
        MODELS_DVC_PATH, role="models_dvc_owner_before_registration", repo_root=repo_root
    )
    if record["bytes"] != BASE_MODELS_DVC_BYTES or record["sha256"] != BASE_MODELS_DVC_SHA256:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY base models.dvc changed before registration"
        )
    expected = _base_models_dvc_bytes()
    if _read_regular_bytes(MODELS_DVC_PATH, repo_root=repo_root) != expected:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY base models.dvc payload dialect drifted"
        )
    return {
        **record,
        "directory_md5": BASE_MODELS_DIR_MD5,
        "size": BASE_MODELS_SIZE,
        "nfiles": BASE_MODELS_NFILES,
    }


def _sealed_base_models_owner_record() -> dict[str, Any]:
    """Return the lock-time baseline without consulting evolved physical bytes."""
    return {
        "role": "models_dvc_owner_before_registration",
        "path": MODELS_DVC_PATH.as_posix(),
        "bytes": BASE_MODELS_DVC_BYTES,
        "sha256": BASE_MODELS_DVC_SHA256,
        "directory_md5": BASE_MODELS_DIR_MD5,
        "size": BASE_MODELS_SIZE,
        "nfiles": BASE_MODELS_NFILES,
    }


def _h_components(head: str, repo_root: Path) -> list[dict[str, Any]]:
    records = [
        _file_record(Path(path), role=PATCH_COMPONENT_ROLES[path], repo_root=repo_root)
        for path in PATCH_PATHS
    ]
    for record in records:
        git_record = _historical_git_blob_record(
            str(record["path"]),
            role=str(record["role"]),
            commit=head,
            repo_root=repo_root,
        )
        if (
            git_record.get("bytes") != record.get("bytes")
            or git_record.get("sha256") != record.get("sha256")
        ):
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY H component differs from Git: {record['path']}"
            )
    return records


def _historical_inputs(repo_root: Path) -> list[dict[str, Any]]:
    return [
        _historical_git_blob_record(
            path,
            role=f"superseded_p_mx_{PATCH_COMPONENT_ROLES[path]}",
            commit=BASE_COMMIT,
            repo_root=repo_root,
        )
        for path in PATCH_MODIFIED_PATHS
    ]


def _base_mx_authority(repo_root: Path) -> dict[str, Any]:
    if (
        _single_parent(repo_root, BASE_COMMIT, context="P-E0-MX") != BASE_H_MX_COMMIT
        or _git_scope(repo_root, BASE_H_MX_COMMIT, BASE_COMMIT)
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "paths": sorted(
                (BASE_MX_LOCK_PATH.as_posix(), BASE_MX_COMPANION_PATH.as_posix())
            ),
        }
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY base P-E0-MX topology drifted"
        )
    lock = _file_record(
        BASE_MX_LOCK_PATH,
        role="anfis_ablation_model_publication_adoption_patch_lock",
        repo_root=repo_root,
    )
    companion = _file_record(
        BASE_MX_COMPANION_PATH,
        role="anfis_ablation_model_publication_adoption_patch_lock_manifest",
        repo_root=repo_root,
    )
    return {
        "gate": "E0-MX",
        "p_head": BASE_COMMIT,
        "h_head": BASE_H_MX_COMMIT,
        "lock": lock,
        "companion": companion,
        "publication_reconstructed_from_git": True,
        "effective_loader_called": False,
    }


def _companion_physical_inputs(
    *, h_components: Sequence[Mapping[str, Any]], base_mx: Mapping[str, Any]
) -> list[dict[str, Any]]:
    records = [
        dict(cast(Mapping[str, Any], base_mx["lock"])),
        dict(cast(Mapping[str, Any], base_mx["companion"])),
        *(dict(record) for record in h_components),
    ]
    identities = {(record["path"], record["role"]) for record in records}
    if len(records) != EXPECTED_COMPANION_INPUT_COUNT or len(identities) != len(records):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY companion physical inputs must be exact11"
        )
    return records


def _expected_untracked_light_status(repo_root: Path) -> list[str]:
    tracked = set(_git(repo_root, "ls-files", "--", *_light_paths()).splitlines())
    expected_tracked = {
        path
        for path in _light_paths()
        if path.startswith("reports/closure_v1/02_models/A0/seed_1729_")
    }
    if tracked != expected_tracked or len(tracked) != FAMILY_TRACKED_LIGHT_COUNT:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY tracked light prefix must remain exact A0/1729 five"
        )
    return [f"?? {path}" for path in sorted(set(_light_paths()) - tracked)]


def _scientific_boundaries(repo_root: Path) -> dict[str, bool]:
    return {
        "e0_m_paths_absent": not any(_lexists(repo_root / path) for path in E0_M_PATHS),
        "outcome_access_log_absent": not _lexists(repo_root / OUTCOME_ACCESS_LOG),
        "calibration_outputs_absent": not _lexists(
            repo_root / "reports/closure_v1/03_calibration"
        ),
        "evaluation_outputs_absent": not _lexists(
            repo_root / "reports/closure_v1/04_evaluation"
        ),
    }


def preflight_anfis_ablation_dvc_registration_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    forbidden = {"minimum", "maximum", "format", "minLength", "maxLength"}
    observed: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            observed.update(str(key) for key in value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(schema)
    unsupported = sorted(forbidden.intersection(observed))
    if unsupported:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY schema exceeds the supported subset: {unsupported}"
        )
    subset_validator = getattr(
        closure_contract, "_assert_supported_json_schema", None
    )
    if not callable(subset_validator):
        raise AnfisAblationDvcRegistrationPatchError(
            "Closure JSON-schema definition validator is unavailable"
        )
    try:
        subset_validator(schema)
    except ClosureContractError as exc:
        raise AnfisAblationDvcRegistrationPatchError(str(exc)) from exc
    encoded = _canonical_json(schema)
    return {
        "schema_path": DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
        "canonical_schema_bytes": len(encoded),
        "canonical_schema_sha256": _sha256_bytes(encoded),
        "supported_subset_verified": True,
        "unsupported_semantic_keywords": [],
    }


def collect_anfis_ablation_dvc_registration_patch_prelock_state(
    *,
    verify_remote: bool = True,
    repo_root: Path | None = None,
    _allow_locker_guard: bool = False,
) -> dict[str, Any]:
    if type(verify_remote) is not bool or type(_allow_locker_guard) is not bool:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY prelock policies must be exact booleans"
        )
    root = _root(repo_root)
    preflight_anfis_ablation_dvc_registration_patch_schema(repo_root=root)
    head = _git_head(root)
    expected_scope = {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "paths": list(PATCH_PATHS),
    }
    if (
        _single_parent(root, head, context="H-E0-MY") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, head) != expected_scope
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "H-E0-MY must be the exact 4M+5A child of P-E0-MX"
        )
    mx._require_exact_git_modes(
        root, head, PATCH_COMPONENT_GIT_MODES, context="H-E0-MY"
    )
    branch = _git(root, "branch", "--show-current").strip()
    tracking = _git_head(root, "origin/main")
    remote = _live_remote_main_head(root) if verify_remote else tracking
    if branch != "main" or tracking != head or remote != head:
        raise AnfisAblationDvcRegistrationPatchError(
            "H-E0-MY refs are not aligned with main"
        )
    status = [
        line
        for line in _git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
        if line
    ]
    expected_status = _expected_untracked_light_status(root)
    if status != expected_status:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY prelock worktree must contain exact45 light reports: {status}"
        )
    family = _family_records(
        root,
        registered=False,
        allow_locker_guard=_allow_locker_guard,
    )
    occupied_outputs = [
        path.as_posix()
        for path in (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        if _lexists(root / path)
    ]
    if occupied_outputs:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY prelock output namespace is occupied: {occupied_outputs}"
        )
    inventory = _registration_inventory(root)
    dvc_configuration = _dvc_configuration_contract(root)
    models_before = _base_models_owner(root)
    expected_registration = _expected_registration_records(root)
    h_components = _h_components(head, root)
    base_mx = _base_mx_authority(root)
    physical_inputs = _companion_physical_inputs(
        h_components=h_components, base_mx=base_mx
    )
    historical_inputs = _historical_inputs(root)
    if len(historical_inputs) != EXPECTED_HISTORICAL_INPUT_COUNT:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY historical inputs must be exact4"
        )
    boundaries = _scientific_boundaries(root)
    if not all(boundaries.values()):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY scientific boundary drifted"
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
            "worktree_scope": "exact_45_untracked_light_outputs",
        },
        "h_patch": {
            "base_commit": BASE_COMMIT,
            "head": head,
            "parent": BASE_COMMIT,
            "component_count": len(h_components),
            "components": h_components,
            "components_sha256": _digest_records(h_components),
            "components_git_modes": dict(PATCH_COMPONENT_GIT_MODES),
            "scope": {"added": 5, "modified": 4, "deleted": 0},
        },
        "base_mx_authority": base_mx,
        "artifact_inventory": inventory,
        "completed_family": {
            "slot_count": len(ORDERED_SLOTS),
            "final_count": len(family),
            "light_final_count": FAMILY_LIGHT_COUNT,
            "tracked_light_count": FAMILY_TRACKED_LIGHT_COUNT,
            "untracked_light_count": FAMILY_UNTRACKED_LIGHT_COUNT,
            "heavy_final_count": FAMILY_HEAVY_COUNT,
            "records": family,
            "records_sha256": _digest_records(family),
            "ordered_slots": [
                {"model_id": model_id, "base_seed": base_seed}
                for model_id, base_seed in ORDERED_SLOTS
            ],
            "role_order": list(SLOT_ROLE_ORDER),
            "manifest_last_verified": True,
        },
        "models_owner_transition": {
            "before": models_before,
            "added_model_file_count": 20,
            "added_model_bytes": EXPECTED_MODELS_SIZE - BASE_MODELS_SIZE,
            "after": expected_registration["models_dvc"],
            "strictly_additive": True,
        },
        "registration_plan": {
            "payload_target_count": 11,
            "payload_targets": [
                *(path.as_posix() for path in _selection_payload_paths()),
                MODELS_PATH.as_posix(),
            ],
            "dvc_add_commands": _dvc_add_commands(),
            "dvc_configuration": dvc_configuration,
            "selection_payload_count": len(_selection_payload_paths()),
            "selection_pointer_count": FAMILY_POINTER_COUNT,
            "expected_registration": expected_registration,
            "registration_git_scope": {
                "added": EXPECTED_REGISTRATION_ADDED_COUNT,
                "modified": EXPECTED_REGISTRATION_MODIFIED_COUNT,
                "deleted": 0,
                "path_count": EXPECTED_REGISTRATION_GIT_PATH_COUNT,
            },
            "light_report_addition_count": FAMILY_UNTRACKED_LIGHT_COUNT,
            "dvc_add_via_publication_assistant_only": True,
            "dvc_push_separate": True,
        },
        "companion_contract": {
            "physical_input_count": len(physical_inputs),
            "historical_input_count": len(historical_inputs),
            "output_count": 1,
            "script_path": LOCKER_PATH.as_posix(),
            "physical_inputs_sha256": _digest_records(physical_inputs),
            "historical_inputs_sha256": _digest_records(historical_inputs),
            "family_finals_in_companion_inputs": False,
            "family_finals_sealed_in_lock": True,
            "manifest_written_last": True,
        },
        "prelock": {
            "complete_slot_count": len(ORDERED_SLOTS),
            "family_final_count": len(family),
            "family_records_sha256": _digest_records(family),
            "untracked_light_count": FAMILY_UNTRACKED_LIGHT_COUNT,
            "ignored_heavy_count": FAMILY_HEAVY_COUNT,
            "selection_pointer_present_count": 0,
            "models_dvc_before_sha256": models_before["sha256"],
            "general_inventory_count": inventory["general_artifact_count"],
            "registration_inventory_count": inventory[
                "registration_artifact_count"
            ],
            "scientific_boundaries": boundaries,
            "dvc_commands_run": False,
            "outcome_paths_opened": False,
            "writes_performed": False,
        },
    }


def build_anfis_ablation_dvc_registration_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    required = {
        "repository",
        "h_patch",
        "base_mx_authority",
        "artifact_inventory",
        "completed_family",
        "models_owner_transition",
        "registration_plan",
        "companion_contract",
        "prelock",
    }
    if set(prelock) != required:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY prelock bundle dialect drifted"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "locked_unpublished",
        "gate": PATCH_GATE,
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
        **{key: json.loads(json.dumps(prelock[key])) for key in required},
        "verification": json.loads(json.dumps(verification)),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
        "seals": dict(LOCK_SEALS),
    }


def _validate_command_evidence(
    value: Any,
    *,
    expected_command: Sequence[str],
    context: str,
    exact_stdout: str | None,
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
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY {context} evidence dialect drifted"
        )
    if (
        value.get("command") != list(expected_command)
        or type(value.get("returncode")) is not int
        or value.get("returncode") != 0
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY {context} command/result drifted"
        )
    if (
        value.get("stderr_sha256") != EMPTY_SHA256
        or any(
            type(value.get(key)) is not int or int(value[key]) < 0
            for key in ("stdout_line_count", "stderr_line_count")
        )
        or value.get("stderr_line_count") != 0
        or not isinstance(value.get("stdout_sha256"), str)
        or SHA256_RE.fullmatch(str(value["stdout_sha256"])) is None
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY {context} digest/line evidence drifted"
        )
    if exact_stdout is not None and (
        value.get("stdout_sha256") != _sha256_bytes(exact_stdout.encode("utf-8"))
        or value.get("stdout_line_count") != len(exact_stdout.splitlines())
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY {context} stdout evidence drifted"
        )


def _validate_verification(value: Any, *, repo_root: Path) -> None:
    if not isinstance(value, Mapping):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY verification evidence is absent"
        )
    required = {
        "schema_preflight",
        "type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "diff_check",
        "family_semantic_audit",
        "execution_boundaries",
    }
    if set(value) != required:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY verification evidence key set drifted"
        )
    expected_schema = preflight_anfis_ablation_dvc_registration_patch_schema(
        repo_root=repo_root
    )
    if not _exact_equal(value.get("schema_preflight"), expected_schema):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY schema-preflight evidence drifted"
        )
    _validate_command_evidence(
        value.get("type_check"),
        expected_command=TYPE_CHECK_COMMAND,
        context="type check",
        exact_stdout="All checks passed!\n",
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
        value.get("diff_check"),
        expected_command=DIFF_CHECK_COMMAND,
        context="diff check",
        exact_stdout="",
    )
    tests = value.get("focused_tests")
    focused_base_keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    if (
        not isinstance(tests, Mapping)
        or set(tests)
        != {
            *focused_base_keys,
            "stdout_text",
            "test_count",
            "warnings",
            "skipped",
            "deselected",
        }
        or any(
            type(tests.get(key)) is not int
            for key in ("test_count", "warnings", "skipped", "deselected")
        )
        or tests.get("test_count") != FOCUSED_TEST_COUNT
        or tests.get("warnings") != 0
        or tests.get("skipped") != 0
        or tests.get("deselected") != 0
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY focused pytest evidence drifted"
        )
    base_focused = {key: tests[key] for key in focused_base_keys}
    _validate_command_evidence(
        base_focused,
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused tests",
        exact_stdout=None,
    )
    stdout_text = tests.get("stdout_text")
    if not isinstance(stdout_text, str):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY focused pytest stdout text is absent"
        )
    parsed = _parse_focused_summary(stdout_text, "")
    if (
        parsed.get("test_count") != FOCUSED_TEST_COUNT
        or tests.get("stdout_sha256") != _sha256_bytes(stdout_text.encode("utf-8"))
        or tests.get("stdout_line_count") != len(stdout_text.splitlines())
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY focused pytest stdout binding drifted"
        )
    audit = value.get("family_semantic_audit")
    if (
        not isinstance(audit, Mapping)
        or audit.get("status") != "passed"
        or type(audit.get("slot_count")) is not int
        or audit.get("slot_count") != 10
        or audit.get("dvc_command_executed") is not False
        or audit.get("future_outcomes_accessed") is not False
        or audit.get("writes_performed") is not False
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY family semantic audit evidence drifted"
        )
    boundaries = value.get("execution_boundaries")
    expected_boundaries = {
        "dvc_commands_run": False,
        "model_fit_run": False,
        "calibration_targets_read": False,
        "evaluation_run": False,
        "e0_m_run": False,
        "e0_u_run": False,
        "outcome_paths_opened": False,
        "scientific_network_run": False,
        "pytest_environment": dict(FOCUSED_PYTEST_ENVIRONMENT),
    }
    if not _exact_equal(boundaries, expected_boundaries):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY verification execution boundaries drifted"
        )


def _validate_anfis_ablation_dvc_registration_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    allow_registered_state: bool = False,
    repo_root: Path | None = None,
    _registration_transaction: Mapping[str, Any] | None = None,
) -> None:
    if type(allow_registered_state) is not bool:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY registered-state policy must be an exact boolean"
        )
    if _registration_transaction is not None and not allow_registered_state:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY private transaction record requires registered-state audit"
        )
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise AnfisAblationDvcRegistrationPatchError(str(exc)) from exc
    _validate_timestamp(payload.get("created_at_utc"))
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("gate") != PATCH_GATE:
        raise AnfisAblationDvcRegistrationPatchError("E0-MY lock identity drifted")
    if not _exact_equal(payload.get("authorizations"), UNPUBLISHED_AUTHORIZATIONS):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY unpublished authorizations drifted"
        )
    if not _exact_equal(payload.get("seals"), LOCK_SEALS):
        raise AnfisAblationDvcRegistrationPatchError("E0-MY seals drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(repository.get("head"), str):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY repository binding is absent"
        )
    h_head = str(repository["head"])
    if (
        SHA1_RE.fullmatch(h_head) is None
        or repository.get("parent") != BASE_COMMIT
        or _single_parent(root, h_head, context="H-E0-MY") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, h_head)
        != {"added": 5, "modified": 4, "deleted": 0, "paths": list(PATCH_PATHS)}
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY repository/H topology drifted"
        )
    h_components = _h_components(h_head, root)
    h_patch = payload.get("h_patch")
    expected_h = {
        "base_commit": BASE_COMMIT,
        "head": h_head,
        "parent": BASE_COMMIT,
        "component_count": 9,
        "components": h_components,
        "components_sha256": _digest_records(h_components),
        "components_git_modes": dict(PATCH_COMPONENT_GIT_MODES),
        "scope": {"added": 5, "modified": 4, "deleted": 0},
    }
    if not _exact_equal(h_patch, expected_h):
        raise AnfisAblationDvcRegistrationPatchError("E0-MY H binding drifted")
    base_mx = _base_mx_authority(root)
    if not _exact_equal(payload.get("base_mx_authority"), base_mx):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY P-E0-MX reconstruction drifted"
        )
    inventory = _registration_inventory(root)
    if not _exact_equal(payload.get("artifact_inventory"), inventory):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY registration inventory binding drifted"
        )
    family = _family_records(
        root,
        registered=allow_registered_state,
        registration_transaction=_registration_transaction,
    )
    completed = payload.get("completed_family")
    if (
        not isinstance(completed, Mapping)
        or completed.get("slot_count") != 10
        or completed.get("final_count") != FAMILY_FINAL_COUNT
        or completed.get("records") != family
        or completed.get("records_sha256") != FAMILY_RECORDS_SHA256
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY completed family binding drifted"
        )
    models_before = (
        _sealed_base_models_owner_record()
        if allow_registered_state
        else _base_models_owner(root)
    )
    expected_registration = _expected_registration_records(root)
    expected_transition = {
        "before": models_before,
        "added_model_file_count": 20,
        "added_model_bytes": EXPECTED_MODELS_SIZE - BASE_MODELS_SIZE,
        "after": expected_registration["models_dvc"],
        "strictly_additive": True,
    }
    if not _exact_equal(payload.get("models_owner_transition"), expected_transition):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY models.dvc transition drifted"
        )
    plan = payload.get("registration_plan")
    expected_targets = [
        *(path.as_posix() for path in _selection_payload_paths()),
        MODELS_PATH.as_posix(),
    ]
    if (
        not isinstance(plan, Mapping)
        or plan.get("payload_targets") != expected_targets
        or plan.get("dvc_add_commands") != _dvc_add_commands()
        or not _exact_equal(
            plan.get("dvc_configuration"), _dvc_configuration_contract(root)
        )
        or not _exact_equal(plan.get("expected_registration"), expected_registration)
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY exact registration plan drifted"
        )
    physical = _companion_physical_inputs(h_components=h_components, base_mx=base_mx)
    historical = _historical_inputs(root)
    expected_contract = {
        "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
        "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
        "output_count": 1,
        "script_path": LOCKER_PATH.as_posix(),
        "physical_inputs_sha256": _digest_records(physical),
        "historical_inputs_sha256": _digest_records(historical),
        "family_finals_in_companion_inputs": False,
        "family_finals_sealed_in_lock": True,
        "manifest_written_last": True,
    }
    if not _exact_equal(payload.get("companion_contract"), expected_contract):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY companion contract drifted"
        )
    prelock = payload.get("prelock")
    if (
        not isinstance(prelock, Mapping)
        or prelock.get("family_records_sha256") != FAMILY_RECORDS_SHA256
        or prelock.get("selection_pointer_present_count") != 0
        or prelock.get("models_dvc_before_sha256") != BASE_MODELS_DVC_SHA256
        or prelock.get("general_inventory_count") != GENERAL_ARTIFACT_COUNT
        or prelock.get("registration_inventory_count") != REGISTRATION_ARTIFACT_COUNT
        or prelock.get("dvc_commands_run") is not False
        or prelock.get("outcome_paths_opened") is not False
        or prelock.get("writes_performed") is not False
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY prelock evidence drifted"
        )
    _validate_verification(payload.get("verification"), repo_root=root)


def validate_anfis_ablation_dvc_registration_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    allow_registered_state: bool = False,
    repo_root: Path | None = None,
) -> None:
    _validate_anfis_ablation_dvc_registration_patch_lock_payload(
        payload,
        allow_registered_state=allow_registered_state,
        repo_root=repo_root,
        _registration_transaction=None,
    )


def _expected_companion(
    payload: Mapping[str, Any],
    lock_record: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    h_patch = payload.get("h_patch")
    base_mx = payload.get("base_mx_authority")
    if not isinstance(h_patch, Mapping) or not isinstance(base_mx, Mapping):
        raise AnfisAblationDvcRegistrationPatchError(
            "Cannot construct E0-MY companion"
        )
    components = h_patch.get("components")
    if not isinstance(components, list):
        raise AnfisAblationDvcRegistrationPatchError(
            "Cannot construct E0-MY companion component list"
        )
    inputs = _companion_physical_inputs(
        h_components=cast(list[dict[str, Any]], components), base_mx=base_mx
    )
    historical = _historical_inputs(root)
    script = next(
        (dict(record) for record in components if record.get("path") == LOCKER_PATH.as_posix()),
        None,
    )
    if script is None:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY companion script is absent"
        )
    output = dict(lock_record)
    if (
        output.get("path") != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or output.get("role") != "anfis_ablation_dvc_registration_patch_lock"
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY companion output record drifted"
        )
    return {
        "manifest_version": COMPANION_VERSION,
        "gate": PATCH_GATE,
        "status": "completed",
        "script": script,
        "inputs": inputs,
        "historical_inputs": historical,
        "historical_inputs_compared_to_current_paths": False,
        "outputs": [output],
        "physical_inputs_only": True,
        "family_finals_in_inputs": False,
        "family_finals_sealed_in_lock": True,
        "manifest_written_last": True,
        "dvc_commands_run": False,
        "model_fit_run": False,
        "calibration_targets_read": False,
        "evaluation_run": False,
        "e0_m_run": False,
        "e0_u_run": False,
        "outcome_paths_opened": False,
        "scientific_network_run": False,
        "completion_marker_written_last": True,
    }


def _command_evidence(command: Sequence[str], result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": result.returncode,
        "stdout_sha256": _sha256_bytes(result.stdout.encode("utf-8")),
        "stderr_sha256": _sha256_bytes(result.stderr.encode("utf-8")),
        "stdout_line_count": len(result.stdout.splitlines()),
        "stderr_line_count": len(result.stderr.splitlines()),
    }


def _run_command(
    command: Sequence[str],
    *,
    repo_root: Path,
    environment: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], str, str]:
    command_environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if environment is not None:
        command_environment.update(environment)
    result = subprocess.run(
        list(command),
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=command_environment,
    )
    evidence = _command_evidence(command, result)
    if result.returncode != 0:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY verification command failed: {list(command)}"
        )
    return evidence, result.stdout, result.stderr


def _parse_focused_summary(stdout: str, stderr: str) -> dict[str, int]:
    if stderr or FORBIDDEN_FOCUSED_SUMMARY_RE.search(stdout):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY focused pytest result is not one clean pass"
        )
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    matches = [FOCUSED_SUMMARY_RE.fullmatch(line) for line in lines]
    matched = [match for match in matches if match is not None]
    if len(matched) != 1 or lines[-1] != matched[0].group(0):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY focused pytest summary is not unique and terminal"
        )
    return {
        "test_count": int(matched[0].group("count")),
        "warnings": 0,
        "skipped": 0,
        "deselected": 0,
    }


def _family_semantic_audit(repo_root: Path) -> dict[str, Any]:
    from src.experiments import audit_closure_anfis_ablation_model_bundle as auditor

    runtime, _ = auditor._load_runtime_contract(repo_root)
    target_reference = auditor.load_cutoff_target_reference(repo_root=repo_root)
    results: list[dict[str, Any]] = []
    for model_id, base_seed in ORDERED_SLOTS:
        manifest_path = _slot_paths(model_id, base_seed)["manifest"]
        manifest = json.loads(_read_regular_bytes(manifest_path, repo_root=repo_root))
        authority = cast(Mapping[str, Any], manifest["authority"])
        source = cast(list[Mapping[str, Any]], manifest["source_code"])[0]
        result = auditor.validate_anfis_ablation_model_bundle_semantics(
            model_id=model_id,
            base_seed=base_seed,
            authority_binding=authority,
            runtime=runtime,
            repo_root=repo_root,
            allow_pointer=False,
            target_reference=target_reference,
            slot_source_record=source,
        )
        results.append(result)
    auditor._validate_paired_results(results)
    return {
        "status": "passed",
        "slot_count": len(results),
        "ordered_slots": [
            {"model_id": model_id, "base_seed": base_seed}
            for model_id, base_seed in ORDERED_SLOTS
        ],
        "dvc_command_executed": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


def run_anfis_ablation_dvc_registration_patch_verification(
    *,
    family_snapshot: Sequence[Mapping[str, Any]] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    baseline = (
        tuple(family_snapshot)
        if family_snapshot is not None
        else _family_physical_snapshot(root)
    )
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="before schema preflight"
    )
    schema = preflight_anfis_ablation_dvc_registration_patch_schema(repo_root=root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after schema preflight"
    )
    type_check, _, _ = _run_command(TYPE_CHECK_COMMAND, repo_root=root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after type check"
    )
    focused, stdout, stderr = _run_command(
        FOCUSED_TEST_COMMAND,
        repo_root=root,
        environment=FOCUSED_PYTEST_ENVIRONMENT,
    )
    focused.update(
        {
            "stdout_text": stdout,
            **_parse_focused_summary(stdout, stderr),
        }
    )
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after focused tests"
    )
    poetry, _, _ = _run_command(POETRY_CHECK_COMMAND, repo_root=root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after poetry check"
    )
    publication, _, _ = _run_command(PUBLICATION_GUARD_COMMAND, repo_root=root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after publication guard"
    )
    diff, _, _ = _run_command(DIFF_CHECK_COMMAND, repo_root=root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after diff check"
    )
    family = _family_semantic_audit(root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after semantic family audit"
    )
    return {
        "schema_preflight": schema,
        "type_check": type_check,
        "focused_tests": focused,
        "poetry_check": poetry,
        "publication_guard": publication,
        "diff_check": diff,
        "family_semantic_audit": family,
        "execution_boundaries": {
            "dvc_commands_run": False,
            "model_fit_run": False,
            "calibration_targets_read": False,
            "evaluation_run": False,
            "e0_m_run": False,
            "e0_u_run": False,
            "outcome_paths_opened": False,
            "scientific_network_run": False,
            "pytest_environment": dict(FOCUSED_PYTEST_ENVIRONMENT),
        },
    }


def execute_and_publish_anfis_ablation_dvc_registration_patch_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    family_snapshot = _family_physical_snapshot(root)
    before = collect_anfis_ablation_dvc_registration_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    verification = run_anfis_ablation_dvc_registration_patch_verification(
        family_snapshot=family_snapshot, repo_root=root
    )
    after = collect_anfis_ablation_dvc_registration_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    if not _exact_equal(before, after):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY prelock state changed during verification"
        )
    _require_family_physical_snapshot(
        family_snapshot, repo_root=root, context="after final prelock collection"
    )
    payload = build_anfis_ablation_dvc_registration_patch_lock_payload(
        before, verification, created_at_utc=datetime.now(timezone.utc).isoformat()
    )
    validate_anfis_ablation_dvc_registration_patch_lock_payload(payload, repo_root=root)
    controlled = (
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        _temporary_path(DEFAULT_PATCH_LOCK_PATH),
        _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        LOCKER_GUARD_PATH,
    )
    occupied = [path.as_posix() for path in controlled if _lexists(root / path)]
    if occupied:
        raise AnfisAblationDvcRegistrationPatchError(
            f"E0-MY lock namespace is occupied: {occupied}"
        )
    guard: mt._OwnedGuard | None = None
    published: list[mt._OwnedOutput] = []
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MY lock bundle publication in progress\n",
            repo_root=root,
        )
        _require_family_physical_snapshot(
            family_snapshot, repo_root=root, context="after guard acquisition"
        )
        if not _exact_equal(
            before,
            collect_anfis_ablation_dvc_registration_patch_prelock_state(
                verify_remote=True,
                repo_root=root,
                _allow_locker_guard=True,
            ),
        ):
            raise AnfisAblationDvcRegistrationPatchError(
                "E0-MY guarded prelock state drifted"
            )
        lock_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, _canonical_json(payload), repo_root=root
        )
        published.append(lock_output)
        _require_family_physical_snapshot(
            family_snapshot, repo_root=root, context="after lock publication"
        )
        lock_record = _file_record(
            DEFAULT_PATCH_LOCK_PATH,
            role="anfis_ablation_dvc_registration_patch_lock",
            repo_root=root,
        )
        companion = _expected_companion(payload, lock_record, repo_root=root)
        companion_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            _canonical_json(companion),
            repo_root=root,
        )
        published.append(companion_output)
        _require_family_physical_snapshot(
            family_snapshot, repo_root=root, context="after companion publication"
        )
        for output in published:
            mt._validate_owned_output(output)
        _require_family_physical_snapshot(
            family_snapshot, repo_root=root, context="before guard release"
        )
        mt._release_publication_guard(guard)
        guard = None
        _require_family_physical_snapshot(
            family_snapshot, repo_root=root, context="after guard release"
        )
        for output in published:
            mt._validate_owned_output(output)
        committed = True
        return payload, companion
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


def publish_anfis_ablation_dvc_registration_patch_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    return execute_and_publish_anfis_ablation_dvc_registration_patch_lock_bundle(
        repo_root=repo_root
    )


def _validate_p_publication(
    payload: Mapping[str, Any], *, repo_root: Path
) -> dict[str, str]:
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(repository.get("head"), str):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY H repository binding is absent"
        )
    h_head = str(repository["head"])
    head = _git_head(repo_root)
    tracking = _git_head(repo_root, "origin/main")
    remote = _live_remote_main_head(repo_root)
    expected_paths = sorted(
        (DEFAULT_PATCH_LOCK_PATH.as_posix(), DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix())
    )
    if (
        _git(repo_root, "branch", "--show-current").strip() != "main"
        or _single_parent(repo_root, head, context="P-E0-MY") != h_head
        or tracking != head
        or remote != head
        or _git_scope(repo_root, h_head, head)
        != {"added": 2, "modified": 0, "deleted": 0, "paths": expected_paths}
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "Published P-E0-MY topology/refs drifted"
        )
    mx._require_git_modes(repo_root, head, expected_paths, context="P-E0-MY")
    for raw_path in expected_paths:
        path = Path(raw_path)
        physical = _read_regular_bytes(
            path, repo_root=repo_root, require_nlink_one=True
        )
        if physical != _git_blob_bytes(repo_root, head, path):
            raise AnfisAblationDvcRegistrationPatchError(
                f"Published P-E0-MY physical bytes differ from Git: {raw_path}"
            )
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


def _validate_registered_state(
    plan: Mapping[str, Any], *, repo_root: Path
) -> dict[str, Any]:
    expected = cast(Mapping[str, Any], plan["expected_registration"])
    pointers = cast(list[Mapping[str, Any]], expected["pointers"])
    for record in pointers:
        path = Path(str(record["path"]))
        payload = _read_regular_bytes(path, repo_root=repo_root, require_nlink_one=True)
        if len(payload) != record["bytes"] or _sha256_bytes(payload) != record["sha256"]:
            raise AnfisAblationDvcRegistrationPatchError(
                f"E0-MY registered pointer drifted: {path.as_posix()}"
            )
    models = cast(Mapping[str, Any], expected["models_dvc"])
    payload = _read_regular_bytes(
        MODELS_DVC_PATH, repo_root=repo_root, require_nlink_one=True
    )
    if len(payload) != models["bytes"] or _sha256_bytes(payload) != models["sha256"]:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY registered models.dvc drifted"
        )
    return {
        "selection_pointer_count": len(pointers),
        "models_dvc_sha256": _sha256_bytes(payload),
        "registration_state": "post_dvc_unpublished",
    }


def _load_effective_anfis_ablation_dvc_registration_patch_authority(
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
    _registration_transaction: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if type(audit_current_unpublished) is not bool or verify_remote is not True:
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY effective authority requires exact audit mode and live remote"
        )
    root = _root(repo_root)
    payload_bytes = _read_regular_bytes(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    payload = json.loads(payload_bytes)
    if not isinstance(payload, dict) or payload_bytes != _canonical_json(payload):
        raise AnfisAblationDvcRegistrationPatchError(
            "Published E0-MY lock is not canonical JSON"
        )
    # The lock was generated in pre-DVC state.  Validation reconstructs every
    # immutable binding directly and does not permit pointers yet.
    _validate_anfis_ablation_dvc_registration_patch_lock_payload(
        payload,
        allow_registered_state=audit_current_unpublished,
        repo_root=root,
        _registration_transaction=_registration_transaction,
    )
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="anfis_ablation_dvc_registration_patch_lock",
        repo_root=root,
    )
    companion_bytes = _read_regular_bytes(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root)
    companion = json.loads(companion_bytes)
    expected_companion = _expected_companion(payload, lock_record, repo_root=root)
    if (
        not isinstance(companion, dict)
        or companion_bytes != _canonical_json(companion)
        or not _exact_equal(companion, expected_companion)
    ):
        raise AnfisAblationDvcRegistrationPatchError(
            "Published E0-MY companion drifted"
        )
    publication = _validate_p_publication(payload, repo_root=root)
    plan = cast(Mapping[str, Any], payload["registration_plan"])
    if audit_current_unpublished:
        state = _validate_registered_state(plan, repo_root=root)
        dvc_add_authorized = False
    else:
        _base_models_owner(root)
        state = {
            "selection_pointer_count": 0,
            "models_dvc_sha256": BASE_MODELS_DVC_SHA256,
            "registration_state": "pre_dvc",
        }
        dvc_add_authorized = True
    return {
        "gate": PATCH_GATE,
        "status": "effective_preflight_passed",
        **publication,
        "lock": lock_record,
        "companion": _file_record(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="anfis_ablation_dvc_registration_patch_lock_manifest",
            repo_root=root,
        ),
        "family_records_sha256": FAMILY_RECORDS_SHA256,
        "family_final_count": FAMILY_FINAL_COUNT,
        "registration_inventory_sha256": cast(Mapping[str, Any], payload["artifact_inventory"])[
            "registration_artifacts_sha256"
        ],
        "dvc_add_payload_targets": list(plan["payload_targets"]),
        "dvc_add_commands": [list(command) for command in plan["dvc_add_commands"]],
        "dvc_configuration": dict(
            cast(Mapping[str, Any], plan["dvc_configuration"])
        ),
        "selection_pointer_paths": [
            path.as_posix() for path in _selection_pointer_paths()
        ],
        "expected_registration": dict(
            cast(Mapping[str, Any], plan["expected_registration"])
        ),
        "registration_git_scope": dict(
            cast(Mapping[str, Any], plan["registration_git_scope"])
        ),
        "audit_current_unpublished": audit_current_unpublished,
        **state,
        "dvc_add_models_and_selection_predictions_authorized": dvc_add_authorized,
        "dvc_push_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "model_fit_authorized": False,
        "model_replay_or_replacement_authorized": False,
        "calibration_authorized": False,
        "calibration_target_access_authorized": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "scientific_network_authorized": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


def load_effective_anfis_ablation_dvc_registration_patch_authority(
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Public authority loader; transaction coordination must be absent."""
    return _load_effective_anfis_ablation_dvc_registration_patch_authority(
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
        _registration_transaction=None,
    )


def _load_effective_anfis_ablation_dvc_registration_patch_during_registration(
    *,
    transaction_record: Mapping[str, Any],
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Internal R-E0-MY audit while durable rollback coordination is owned."""
    if not isinstance(transaction_record, Mapping):
        raise AnfisAblationDvcRegistrationPatchError(
            "E0-MY internal transaction record is absent"
        )
    return _load_effective_anfis_ablation_dvc_registration_patch_authority(
        audit_current_unpublished=True,
        verify_remote=verify_remote,
        repo_root=repo_root,
        _registration_transaction=transaction_record,
    )


def require_anfis_ablation_dvc_registration_patch_authority(
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    return load_effective_anfis_ablation_dvc_registration_patch_authority(
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


def require_anfis_ablation_dvc_registration_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    """Exact lazy-loader API consumed by the precommit registration profile."""
    return require_anfis_ablation_dvc_registration_patch_authority(
        audit_current_unpublished=False,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


def load_effective_anfis_ablation_dvc_registration_patch(
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Compatibility spelling used by the publication assistant."""
    return load_effective_anfis_ablation_dvc_registration_patch_authority(
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


__all__ = [
    "AnfisAblationDvcRegistrationPatchError",
    "ANFIS_ABLATION_H_MY_STAGED_SCOPE",
    "ANFIS_ABLATION_P_MY_STAGED_SCOPE",
    "ANFIS_ABLATION_R_MY_STAGED_SCOPE",
    "BASE_COMMIT",
    "DEFAULT_PATCH_LOCK_MANIFEST_PATH",
    "DEFAULT_PATCH_LOCK_PATH",
    "DEFAULT_PATCH_LOCK_SCHEMA",
    "DEFAULT_PATCH_MANIFEST_PATH",
    "FOCUSED_TEST_COMMAND",
    "FOCUSED_TEST_COUNT",
    "LOCKER_GUARD_PATH",
    "LOCKER_PATH",
    "REGISTRATION_GUARD_PATH",
    "REGISTRATION_MODELS_BACKUP_PATH",
    "REGISTRATION_MODELS_BYTES_BACKUP_PATH",
    "REGISTRATION_DVC_GLOBAL_CONFIG_PATH",
    "REGISTRATION_DVC_SYSTEM_CONFIG_PATH",
    "PATCH_ADDED_PATHS",
    "PATCH_COMPONENT_GIT_MODES",
    "PATCH_COMPONENT_ROLES",
    "PATCH_GATE",
    "PATCH_PATHS",
    "build_anfis_ablation_dvc_registration_patch_lock_payload",
    "collect_anfis_ablation_dvc_registration_patch_prelock_state",
    "execute_and_publish_anfis_ablation_dvc_registration_patch_lock_bundle",
    "load_effective_anfis_ablation_dvc_registration_patch_authority",
    "load_effective_anfis_ablation_dvc_registration_patch",
    "preflight_anfis_ablation_dvc_registration_patch_schema",
    "publish_anfis_ablation_dvc_registration_patch_lock_bundle",
    "require_anfis_ablation_dvc_registration_authority",
    "require_anfis_ablation_dvc_registration_patch_authority",
    "run_anfis_ablation_dvc_registration_patch_verification",
    "validate_anfis_ablation_dvc_registration_patch_lock_payload",
]
