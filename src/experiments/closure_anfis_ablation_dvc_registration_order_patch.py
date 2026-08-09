"""Repair the pre-DVC missing-pointer order comparison under E0-MZA.

E0-MZA is an additive governance overlay over published P-E0-MZ.  It records
that the blocked R-E0-MZ attempt stopped before DVC because discovery returns
the exact ten paths in lexical order while execution is deliberately sealed in
alternating A0/A1 slot order.  H/P-E0-MZA never fit, rewrite, register, or push
anything.  Only published P-E0-MZA can authorize the unchanged exact R scope.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Mapping, ParamSpec, Sequence, TypeVar, cast

from src.experiments import (
    closure_anfis_ablation_model_publication_adoption_patch as mx,
)
from src.experiments import closure_anfis_ablation_dvc_registration_patch as my
from src.experiments import closure_anfis_ablation_dvc_registration_adoption_patch as mz
from src.experiments import closure_anfis_ablation_training_development_patch as mt
from src.experiments import closure_contract
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = mz.PROJECT_ROOT
H_MZ_COMMIT = "ab1d7189ab8ce549a2517a71fef61ea66e2dcf7f"
P_MZ_COMMIT = "74410ceb42cbea471b4a3cf8d1bd4e2f197ad058"
BASE_COMMIT = P_MZ_COMMIT
PATCH_GATE = "E0-MZA"
SCHEMA_VERSION = "closure_anfis_ablation_dvc_registration_order_patch_lock_v1"
COMPANION_VERSION = (
    "closure_anfis_ablation_dvc_registration_order_patch_lock_manifest_v1"
)

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/anfis_ablation_dvc_registration_order_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_order_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_order_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_PATH = Path(
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_order_patch.py"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mza_locker/registration_order_patch.lock"
)
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
    "configs/closure_v1/anfis_ablation_dvc_registration_order_patch_lock.schema.json": (
        "anfis_ablation_dvc_registration_order_patch_schema"
    ),
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_ORDER_PATCH_1.md": (
        "anfis_ablation_dvc_registration_order_patch_protocol"
    ),
    "src/data/prepare_commit_artifacts.py": "precommit_artifact_assistant",
    "src/experiments/closure_anfis_ablation_dvc_registration_order_patch.py": (
        "anfis_ablation_dvc_registration_order_patch_validator"
    ),
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_order_patch.py": (
        "anfis_ablation_dvc_registration_order_patch_locker"
    ),
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py": (
        "anfis_ablation_dvc_registration_order_patch_test"
    ),
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py": (
        "anfis_ablation_dvc_registration_patch_order_regression_test"
    ),
    "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py": (
        "anfis_ablation_dvc_registration_adoption_patch_order_regression_test"
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
        "src/data/prepare_commit_artifacts.py",
        "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
        "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py",
        "tests/test_closure_anfis_ablation_model_publication_patch.py",
        "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
    }
)
PATCH_MODIFIED_PATHS = tuple(
    path for path in PATCH_PATHS if path not in set(PATCH_ADDED_PATHS)
)
SUPERSEDED_MZ_PATHS = PATCH_MODIFIED_PATHS
PRESERVED_MZ_PATHS = tuple(
    path for path in mz.PATCH_PATHS if path not in set(SUPERSEDED_MZ_PATHS)
)
PATCH_COMPONENT_GIT_MODES = {
    path: "100755" if path == "src/data/prepare_commit_artifacts.py" else "100644"
    for path in PATCH_PATHS
}
ANFIS_ABLATION_H_MZA_STAGED_SCOPE = {
    path: ("A" if path in set(PATCH_ADDED_PATHS) else "M") for path in PATCH_PATHS
}
ANFIS_ABLATION_P_MZA_STAGED_SCOPE = {
    DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
    DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
}
BASE_MZ_LOCK_PATH = mz.DEFAULT_PATCH_LOCK_PATH
BASE_MZ_COMPANION_PATH = mz.DEFAULT_PATCH_LOCK_MANIFEST_PATH
BASE_MZ_LOCK_BYTES = 53_495
BASE_MZ_LOCK_SHA256 = "ab82d4389dde3eb2cec7c8042417d3739a3a4ef30bd11d9d40fece11688b4aa9"
BASE_MZ_COMPANION_BYTES = 7_621
BASE_MZ_COMPANION_SHA256 = "d12d5b2ddbc012def6caf5909183014c7de8a17cec42abf3f94e18479abb6fbf"
DVC_INVENTORY_PATH = Path("configs/closure_v1/dvc_artifacts_post_lock.yaml")
DVC_CONFIG_PATH = Path(".dvc/config")
DVC_CONFIG_LOCAL_PATH = Path(".dvc/config.local")
MODELS_DVC_PATH = Path("models.dvc")
MODELS_PATH = Path("models")
OUTCOME_ACCESS_LOG = mz.OUTCOME_ACCESS_LOG
E0_M_PATHS = mz.E0_M_PATHS
ORDERED_SLOTS = mz.ORDERED_SLOTS
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
FAMILY_TRACKED_LIGHT_COUNT = 50
FAMILY_UNTRACKED_LIGHT_COUNT = 0
FAMILY_HEAVY_COUNT = 30
FAMILY_POINTER_COUNT = 10
FAMILY_RECORDS_SHA256 = (
    "e625add8f8af1746f7deda9ff13a84a4d4f4c27b47e3b6312922db419508dd8e"
)
ANFIS_ABLATION_R_MZA_STAGED_SCOPE = {
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

EXPECTED_COMPANION_INPUT_COUNT = 16
EXPECTED_HISTORICAL_INPUT_COUNT = 13
EXPECTED_REGISTRATION_GIT_PATH_COUNT = 11
EXPECTED_REGISTRATION_ADDED_COUNT = 10
EXPECTED_REGISTRATION_MODIFIED_COUNT = 1
EXPECTED_MISSING_POINTER_COUNT = 10
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
    "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
    "tests/test_prepare_commit_artifacts.py",
)
# Synchronized after the H tests are collected; the validator also rejects a
# summary whose count differs from the evidence embedded by the locker.
FOCUSED_TEST_COUNT = 148
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
    "registration_requires_published_p_mza": True,
    "published_p_mz_reconstructed": True,
    "historical_h_mz_reconstructed": True,
    "blocked_r_mz_attempt_had_no_side_effects": True,
    "missing_pointer_count_unique_set_exact": True,
    "lexical_discovery_separate_from_canonical_execution": True,
    "all_fifty_light_outputs_already_tracked": True,
    "h_p_run_no_dvc_commands": True,
    "h_p_run_no_model_fit": True,
    "calibration_and_evaluation_closed": True,
    "e0_m_and_e0_u_closed": True,
    "outcomes_closed": True,
    "manifest_written_last": True,
}


class AnfisAblationDvcRegistrationOrderPatchError(RuntimeError):
    """Raised when E0-MZA authority, artifacts, or topology drift."""


def _translate(exc: BaseException) -> AnfisAblationDvcRegistrationOrderPatchError:
    return AnfisAblationDvcRegistrationOrderPatchError(str(exc))


_P = ParamSpec("_P")
_R = TypeVar("_R")


def _mza_error_boundary(function: Callable[_P, _R]) -> Callable[_P, _R]:
    @wraps(function)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return function(*args, **kwargs)
        except AnfisAblationDvcRegistrationOrderPatchError:
            raise
        except Exception as exc:
            raise _translate(exc) from exc

    return wrapped


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


def _permissions_from_git_mode(value: str) -> int:
    if re.fullmatch(r"100[0-7]{3}", value) is None:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA unsupported regular-file Git mode: {value!r}"
        )
    return int(value[-3:], 8)


def _open_anchored_parent(path: Path, *, repo_root: Path) -> tuple[int, str]:
    if path.is_absolute() or not path.parts or any(
        component in {"", ".", ".."} for component in path.parts
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA path must remain repository-relative: {path.as_posix()}"
        )
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(repo_root, directory_flags)
    try:
        for component in path.parts[:-1]:
            child = os.open(component, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor, path.name
    except BaseException:
        os.close(descriptor)
        raise


def _read_regular_bytes_and_metadata(
    path: Path,
    *,
    repo_root: Path,
    require_nlink_one: bool = True,
    expected_mode: int = 0o644,
) -> tuple[bytes, os.stat_result]:
    descriptor: int | None = None
    file_descriptor: int | None = None
    try:
        descriptor, name = _open_anchored_parent(path, repo_root=repo_root)
        file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        file_flags |= getattr(os, "O_NOFOLLOW", 0)
        file_descriptor = os.open(name, file_flags, dir_fd=descriptor)
        before = os.fstat(file_descriptor)
        named_before = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(named_before.st_mode)
            or (before.st_dev, before.st_ino)
            != (named_before.st_dev, named_before.st_ino)
            or stat.S_IMODE(before.st_mode) != expected_mode
            or stat.S_IMODE(named_before.st_mode) != expected_mode
            or (require_nlink_one and (before.st_nlink != 1 or named_before.st_nlink != 1))
        ):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA path is not one stable regular {expected_mode:04o} file: "
                f"{path.as_posix()}"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(file_descriptor)
        named_after = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        named_identity = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_mode,
            named_after.st_nlink,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if identity_before != identity_after or identity_after != named_identity:
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA path changed while read: {path.as_posix()}"
            )
        return b"".join(chunks), after
    except AnfisAblationDvcRegistrationOrderPatchError:
        raise
    except (FileNotFoundError, NotADirectoryError, OSError) as exc:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"Required stable E0-MZA input is unavailable: {path.as_posix()}"
        ) from exc
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if descriptor is not None:
            os.close(descriptor)


def _read_regular_bytes(
    path: Path,
    *,
    repo_root: Path,
    require_nlink_one: bool = True,
    expected_mode: int = 0o644,
) -> bytes:
    payload, _ = _read_regular_bytes_and_metadata(
        path,
        repo_root=repo_root,
        require_nlink_one=require_nlink_one,
        expected_mode=expected_mode,
    )
    return payload


def _file_record_and_metadata(
    path: Path,
    *,
    role: str,
    repo_root: Path,
    require_nlink_one: bool = True,
    expected_mode: int = 0o644,
) -> tuple[dict[str, Any], os.stat_result]:
    payload, metadata = _read_regular_bytes_and_metadata(
        path,
        repo_root=repo_root,
        require_nlink_one=require_nlink_one,
        expected_mode=expected_mode,
    )
    return (
        {
            "role": role,
            "path": path.as_posix(),
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        },
        metadata,
    )


def _file_record(
    path: Path,
    *,
    role: str,
    repo_root: Path,
    require_nlink_one: bool = True,
    expected_mode: int = 0o644,
) -> dict[str, Any]:
    record, _ = _file_record_and_metadata(
        path,
        role=role,
        repo_root=repo_root,
        require_nlink_one=require_nlink_one,
        expected_mode=expected_mode,
    )
    return record


def _git(repo_root: Path, *arguments: str) -> str:
    try:
        return mx._git(repo_root, *arguments)
    except Exception as exc:
        raise _translate(exc) from exc


def _git_head(repo_root: Path, ref: str = "HEAD") -> str:
    try:
        return mx._git_head(repo_root, ref)
    except Exception as exc:
        raise _translate(exc) from exc


def _single_parent(repo_root: Path, commit: str, *, context: str) -> str:
    try:
        return mx._single_parent(repo_root, commit, context=context)
    except Exception as exc:
        raise _translate(exc) from exc


def _git_scope(repo_root: Path, parent: str, head: str) -> dict[str, Any]:
    try:
        return mx._git_scope(repo_root, parent, head)
    except Exception as exc:
        raise _translate(exc) from exc


def _require_exact_git_modes(
    repo_root: Path,
    commit: str,
    expected_modes: Mapping[str, str],
    *,
    context: str,
) -> None:
    try:
        mx._require_exact_git_modes(
            repo_root, commit, expected_modes, context=context
        )
    except Exception as exc:
        raise _translate(exc) from exc


def _git_blob_bytes(repo_root: Path, commit: str, path: Path) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", repo_root.as_posix(), "show", f"{commit}:{path.as_posix()}"],
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise _translate(exc) from exc
    if result.returncode != 0 or result.stderr:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA cannot reconstruct Git blob {commit}:{path.as_posix()}"
        )
    return result.stdout


def _live_remote_main_head(repo_root: Path) -> str:
    try:
        return mx._live_remote_main_head(repo_root)
    except Exception as exc:
        raise _translate(exc) from exc


def _historical_git_blob_record(
    path: str, *, role: str, commit: str, repo_root: Path
) -> dict[str, Any]:
    try:
        record = mx._historical_git_blob_record(
            repo_root, commit, path, role=role
        )
    except Exception as exc:
        raise _translate(exc) from exc
    return dict(record)


def _load_json(path: Path, *, repo_root: Path) -> dict[str, Any]:
    payload = _read_regular_bytes(path, repo_root=repo_root)
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA JSON cannot be decoded: {path.as_posix()}"
        ) from exc
    if not isinstance(value, dict):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA JSON must be an object: {path.as_posix()}"
        )
    return value


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise AnfisAblationDvcRegistrationOrderPatchError("E0-MZA timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA timestamp is malformed"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA timestamp must be timezone-aware"
        )


def _slot_paths(model_id: str, base_seed: int) -> dict[str, Path]:
    paths = mt.anfis_ablation_training_slot_paths(model_id, base_seed)
    if set(paths) != set(SLOT_ROLE_ORDER):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA slot path roles drifted: {model_id}/{base_seed}"
        )
    return paths


def _expected_ordered_slots() -> list[dict[str, Any]]:
    return [
        {"model_id": model_id, "base_seed": base_seed}
        for model_id, base_seed in ORDERED_SLOTS
    ]


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
        slot_records: list[dict[str, Any]] = []
        slot_mtimes: dict[str, int] = {}
        for role in SLOT_ROLE_ORDER:
            record, metadata = _file_record_and_metadata(
                paths[role],
                role=role,
                repo_root=repo_root,
                require_nlink_one=True,
            )
            slot_records.append(record)
            slot_mtimes[role] = metadata.st_mtime_ns
        if slot_mtimes["manifest"] <= max(
            mtime for role, mtime in slot_mtimes.items() if role != "manifest"
        ):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA manifest-last order drifted: {model_id}/{base_seed}"
            )
        records.extend(slot_records)
    if len(records) != FAMILY_FINAL_COUNT or _digest_records(records) != FAMILY_RECORDS_SHA256:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA exact eighty-final family digest drifted"
        )
    return records


def _family_physical_snapshot(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Capture the exact local identity of all eighty immutable finals."""
    snapshot: list[dict[str, Any]] = []
    for model_id, base_seed in ORDERED_SLOTS:
        paths = _slot_paths(model_id, base_seed)
        for role in SLOT_ROLE_ORDER:
            path = paths[role]
            payload, metadata = _read_regular_bytes_and_metadata(
                path, repo_root=repo_root, require_nlink_one=True
            )
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA physical family snapshot must contain exact80 identities"
        )
    return tuple(snapshot)


def _require_family_physical_snapshot(
    expected: Sequence[Mapping[str, Any]], *, repo_root: Path, context: str
) -> None:
    if list(expected) != list(_family_physical_snapshot(repo_root)):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA exact80 physical family changed {context}"
        )


def _publication_input_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            {
                *(Path(path) for path in PATCH_PATHS),
                *(Path(path) for path in PRESERVED_MZ_PATHS),
                BASE_MZ_LOCK_PATH,
                BASE_MZ_COMPANION_PATH,
                DVC_CONFIG_PATH,
                DVC_CONFIG_LOCAL_PATH,
                MODELS_DVC_PATH,
            },
            key=lambda path: path.as_posix(),
        )
    )


def _publication_input_snapshot(repo_root: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for path in _publication_input_paths():
        expected_mode = (
            _permissions_from_git_mode(PATCH_COMPONENT_GIT_MODES[path.as_posix()])
            if path.as_posix() in PATCH_COMPONENT_GIT_MODES
            else 0o644
        )
        payload, metadata = _read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            require_nlink_one=True,
            expected_mode=expected_mode,
        )
        records.append(
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
    return tuple(records)


def _publication_git_snapshot(repo_root: Path) -> dict[str, Any]:
    controlled = {
        DEFAULT_PATCH_LOCK_PATH.as_posix(),
        DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
    }
    status = []
    for line in _git(
        repo_root, "status", "--porcelain", "--untracked-files=all"
    ).splitlines():
        if not line:
            continue
        if line.startswith("?? ") and line[3:] in controlled:
            continue
        status.append(line)
    return {
        "head": _git_head(repo_root),
        "main": _git_head(repo_root, "main"),
        "tracking": _git_head(repo_root, "origin/main"),
        "branch": _git(repo_root, "branch", "--show-current").strip(),
        "status_without_owned_outputs": status,
    }


def _require_publication_state(
    physical_snapshot: Sequence[Mapping[str, Any]],
    git_snapshot: Mapping[str, Any],
    *,
    repo_root: Path,
    context: str,
    allow_locker_guard: bool,
) -> None:
    if list(physical_snapshot) != list(_publication_input_snapshot(repo_root)):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA physical governance input changed {context}"
        )
    if not _exact_equal(git_snapshot, _publication_git_snapshot(repo_root)):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA Git publication state changed {context}"
        )
    _validate_family_namespace(
        registered=False,
        repo_root=repo_root,
        allow_locker_guard=allow_locker_guard,
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA DVC repository/local configuration drifted"
        )
    config_payload = _read_regular_bytes(DVC_CONFIG_PATH, repo_root=repo_root)
    local_payload = _read_regular_bytes(DVC_CONFIG_LOCAL_PATH, repo_root=repo_root)
    if config_payload != b'[cache]\n    type = "reflink,hardlink,copy"\n':
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA DVC cache-type policy drifted"
        )
    lowered_local = local_payload.lower()
    if b"[cache]" in lowered_local or b"autostage" in lowered_local:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA local DVC cache/autostage override is forbidden"
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
                mz.SUPERSEDED_P_MY_LOCK_PATH,
                mz.SUPERSEDED_P_MY_COMPANION_PATH,
                _temporary_path(mz.SUPERSEDED_P_MY_LOCK_PATH),
                _temporary_path(mz.SUPERSEDED_P_MY_COMPANION_PATH),
                _temporary_path(BASE_MZ_LOCK_PATH),
                _temporary_path(BASE_MZ_COMPANION_PATH),
                mz.LOCKER_GUARD_PATH,
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
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA {context} expected path escaped its root"
            ) from exc
        if relative == Path("."):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA {context} expected file path is malformed"
            )
        expected_files.add(relative)
        parent = relative.parent
        while parent != Path("."):
            expected_directories.add(parent)
            parent = parent.parent

    observed_files: set[Path] = set()
    observed_directories: set[Path] = set()

    def identity(metadata: os.stat_result) -> tuple[int, ...]:
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )

    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    file_flags |= getattr(os, "O_NOFOLLOW", 0)

    def walk(descriptor: int, relative_parent: Path) -> None:
        before = os.fstat(descriptor)
        if not stat.S_ISDIR(before.st_mode):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA {context} walk escaped its directory root"
            )
        try:
            entries = sorted(os.listdir(descriptor))
        except OSError as exc:
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA cannot walk exact {context} root"
            ) from exc
        for name in entries:
            relative = (
                Path(name)
                if relative_parent == Path(".")
                else relative_parent / name
            )
            metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                if relative not in expected_directories:
                    raise AnfisAblationDvcRegistrationOrderPatchError(
                        f"E0-MZA {context} contains an unexpected directory: {relative}"
                    )
                child = os.open(name, directory_flags, dir_fd=descriptor)
                try:
                    opened = os.fstat(child)
                    if identity(opened) != identity(metadata):
                        raise AnfisAblationDvcRegistrationOrderPatchError(
                            f"E0-MZA {context} directory changed while opened: {relative}"
                        )
                    observed_directories.add(relative)
                    walk(child, relative)
                    named_after = os.stat(
                        name, dir_fd=descriptor, follow_symlinks=False
                    )
                    if identity(os.fstat(child)) != identity(named_after):
                        raise AnfisAblationDvcRegistrationOrderPatchError(
                            f"E0-MZA {context} directory changed while walked: {relative}"
                        )
                finally:
                    os.close(child)
            elif stat.S_ISREG(metadata.st_mode):
                if (
                    relative not in expected_files
                    or stat.S_IMODE(metadata.st_mode) != 0o644
                    or metadata.st_nlink != 1
                ):
                    raise AnfisAblationDvcRegistrationOrderPatchError(
                        f"E0-MZA {context} contains a foreign/non-0644 file: {relative}"
                    )
                file_descriptor = os.open(name, file_flags, dir_fd=descriptor)
                try:
                    opened = os.fstat(file_descriptor)
                    named_after = os.stat(
                        name, dir_fd=descriptor, follow_symlinks=False
                    )
                    if (
                        identity(opened) != identity(metadata)
                        or identity(opened) != identity(named_after)
                    ):
                        raise AnfisAblationDvcRegistrationOrderPatchError(
                            f"E0-MZA {context} file changed while inspected: {relative}"
                        )
                    observed_files.add(relative)
                finally:
                    os.close(file_descriptor)
            else:
                raise AnfisAblationDvcRegistrationOrderPatchError(
                    f"E0-MZA {context} contains a symlink/nonregular entry: {relative}"
                )
        if identity(before) != identity(os.fstat(descriptor)):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA {context} directory changed while walked: {relative_parent}"
            )

    parent_descriptor: int | None = None
    root_descriptor: int | None = None
    try:
        parent_descriptor, root_name = _open_anchored_parent(
            root_path, repo_root=repo_root
        )
        root_descriptor = os.open(
            root_name, directory_flags, dir_fd=parent_descriptor
        )
        root_before = os.fstat(root_descriptor)
        named_before = os.stat(
            root_name, dir_fd=parent_descriptor, follow_symlinks=False
        )
        if identity(root_before) != identity(named_before):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA {context} root changed while opened"
            )
        walk(root_descriptor, Path("."))
        root_after = os.fstat(root_descriptor)
        named_after = os.stat(
            root_name, dir_fd=parent_descriptor, follow_symlinks=False
        )
        if (
            identity(root_before) != identity(root_after)
            or identity(root_after) != identity(named_after)
        ):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA {context} root changed while walked"
            )
    except AnfisAblationDvcRegistrationOrderPatchError:
        raise
    except OSError as exc:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA cannot open exact {context} root without following links"
        ) from exc
    finally:
        if root_descriptor is not None:
            os.close(root_descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)
    if observed_files != expected_files or observed_directories != expected_directories:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA {context} tree does not contain its exact closed namespace"
        )


def _validate_family_namespace(
    *,
    registered: bool,
    repo_root: Path,
    allow_locker_guard: bool = False,
    registration_transaction: Mapping[str, Any] | None = None,
) -> None:
    if type(registered) is not bool or type(allow_locker_guard) is not bool:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA namespace policy must use exact booleans"
        )
    if registration_transaction is not None and not registered:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA transaction coordination is post-registration only"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA ignored/coordination namespace is occupied: {occupied}"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA sealed base models.dvc constants drifted"
        )
    return payload


def _coordination_identity_record(
    path: Path,
    *,
    expected_mode: int,
    expected_payload: bytes,
    repo_root: Path,
) -> dict[str, Any]:
    payload, metadata = _read_regular_bytes_and_metadata(
        path,
        repo_root=repo_root,
        require_nlink_one=True,
        expected_mode=expected_mode,
    )
    if payload != expected_payload:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA transaction coordination bytes drifted: {path.as_posix()}"
        )
    return {
        "path": path.as_posix(),
        "device": int(metadata.st_dev),
        "inode": int(metadata.st_ino),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
        "size": len(payload),
        "mtime_ns": int(metadata.st_mtime_ns),
        "ctime_ns": int(metadata.st_ctime_ns),
        "sha256": _sha256_bytes(payload),
    }


def _coordination_directory_record(
    path: Path, *, repo_root: Path
) -> dict[str, Any]:
    parent_descriptor: int | None = None
    directory_descriptor: int | None = None
    try:
        parent_descriptor, name = _open_anchored_parent(path, repo_root=repo_root)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        directory_descriptor = os.open(
            name, directory_flags, dir_fd=parent_descriptor
        )
        before = os.fstat(directory_descriptor)
        named_before = os.stat(
            name, dir_fd=parent_descriptor, follow_symlinks=False
        )
        entries = tuple(os.listdir(directory_descriptor))
        after = os.fstat(directory_descriptor)
        named_after = os.stat(
            name, dir_fd=parent_descriptor, follow_symlinks=False
        )
    except OSError as exc:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA coordination directory is absent/unreadable: {path.as_posix()}"
        ) from exc
    finally:
        if directory_descriptor is not None:
            os.close(directory_descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)
    identities = {
        (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )
        for metadata in (before, named_before, after, named_after)
    }
    if (
        len(identities) != 1
        or not stat.S_ISDIR(after.st_mode)
        or stat.S_IMODE(after.st_mode) != 0o700
        or after.st_nlink != 2
        or entries
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA coordination directory identity drifted: {path.as_posix()}"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA private transaction record dialect drifted"
        )
    mode = value.get("mode")
    if mode not in {"in_place", "atomic_replace"}:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA private transaction mode drifted"
        )
    expected_guard = _coordination_identity_record(
        REGISTRATION_GUARD_PATH,
        expected_mode=0o600,
        expected_payload=b"E0-MZA exact ANFIS-ablation DVC registration\n",
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA private transaction identity record drifted"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA private DVC config-isolation record drifted"
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
            raise AnfisAblationDvcRegistrationOrderPatchError(
                "E0-MZA in-place transaction retained a hardlink anchor"
            )
    else:
        expected_anchor = _coordination_identity_record(
            REGISTRATION_MODELS_BACKUP_PATH,
            expected_mode=0o644,
            expected_payload=_base_models_dvc_bytes(),
            repo_root=repo_root,
        )
        if not _exact_equal(value.get("anchor"), expected_anchor):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                "E0-MZA atomic transaction anchor record drifted"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA expected models.dvc dialect drifted"
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
    try:
        return mz._registration_inventory(repo_root)
    except Exception as exc:
        raise _translate(exc) from exc


def _base_models_owner(repo_root: Path) -> dict[str, Any]:
    try:
        return mz._base_models_owner(repo_root)
    except Exception as exc:
        raise _translate(exc) from exc


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
        _file_record(
            Path(path),
            role=PATCH_COMPONENT_ROLES[path],
            repo_root=repo_root,
            expected_mode=_permissions_from_git_mode(PATCH_COMPONENT_GIT_MODES[path]),
        )
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
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA H component differs from Git: {record['path']}"
            )
    return records


def _historical_inputs(repo_root: Path) -> list[dict[str, Any]]:
    base_mz = _base_mz_authority(repo_root)
    inherited = [
        dict(record)
        for record in cast(
            Sequence[Mapping[str, Any]], base_mz["historical_inputs"]
        )
    ]
    superseded = [
        _historical_git_blob_record(
            path,
            role=f"superseded_h_mz_{mz.PATCH_COMPONENT_ROLES[path]}",
            commit=H_MZ_COMMIT,
            repo_root=repo_root,
        )
        for path in SUPERSEDED_MZ_PATHS
    ]
    records = [*inherited, *superseded]
    identities = {(record["commit"], record["path"], record["role"]) for record in records}
    if len(records) != EXPECTED_HISTORICAL_INPUT_COUNT or len(identities) != len(records):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA historical companion inputs must be exact13"
        )
    return records


def _historical_h_mz_authority(repo_root: Path) -> dict[str, Any]:
    expected_scope = {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "paths": list(mz.PATCH_PATHS),
    }
    if (
        _single_parent(repo_root, H_MZ_COMMIT, context="historical H-E0-MZ")
        != mz.BASE_COMMIT
        or _git_scope(repo_root, mz.BASE_COMMIT, H_MZ_COMMIT) != expected_scope
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA historical H-E0-MZ topology drifted"
        )
    _require_exact_git_modes(
        repo_root,
        H_MZ_COMMIT,
        mz.PATCH_COMPONENT_GIT_MODES,
        context="historical H-E0-MZ",
    )
    preserved: list[dict[str, Any]] = []
    for path in PRESERVED_MZ_PATHS:
        role = mz.PATCH_COMPONENT_ROLES[path]
        current = _file_record(Path(path), role=role, repo_root=repo_root)
        historical = _historical_git_blob_record(
            path, role=role, commit=H_MZ_COMMIT, repo_root=repo_root
        )
        if current["bytes"] != historical["bytes"] or current["sha256"] != historical["sha256"]:
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA preserved H-E0-MZ component drifted: {path}"
            )
        preserved.append(current)
    superseded = [
        _historical_git_blob_record(
            path,
            role=f"superseded_h_mz_{mz.PATCH_COMPONENT_ROLES[path]}",
            commit=H_MZ_COMMIT,
            repo_root=repo_root,
        )
        for path in SUPERSEDED_MZ_PATHS
    ]
    if len(preserved) != 4 or len(superseded) != 5:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA H-E0-MZ preserved/superseded partition drifted"
        )
    return {
        "gate": "E0-MZ",
        "head": H_MZ_COMMIT,
        "parent": mz.BASE_COMMIT,
        "scope": {"added": 5, "modified": 4, "deleted": 0},
        "paths": list(mz.PATCH_PATHS),
        "preserved_component_count": len(preserved),
        "preserved_components": preserved,
        "preserved_components_sha256": _digest_records(preserved),
        "superseded_component_count": len(superseded),
        "superseded_components": superseded,
        "superseded_components_sha256": _digest_records(superseded),
    }


def _base_mz_authority(repo_root: Path) -> dict[str, Any]:
    if (
        _single_parent(repo_root, P_MZ_COMMIT, context="P-E0-MZ") != H_MZ_COMMIT
        or _git_scope(repo_root, H_MZ_COMMIT, P_MZ_COMMIT)
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "paths": sorted(
                (BASE_MZ_LOCK_PATH.as_posix(), BASE_MZ_COMPANION_PATH.as_posix())
            ),
        }
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA base P-E0-MZ topology drifted"
        )
    lock = _file_record(
        BASE_MZ_LOCK_PATH,
        role="anfis_ablation_dvc_registration_adoption_patch_lock",
        repo_root=repo_root,
    )
    companion = _file_record(
        BASE_MZ_COMPANION_PATH,
        role="anfis_ablation_dvc_registration_adoption_patch_lock_manifest",
        repo_root=repo_root,
    )
    _require_exact_git_modes(
        repo_root,
        P_MZ_COMMIT,
        {
            BASE_MZ_LOCK_PATH.as_posix(): "100644",
            BASE_MZ_COMPANION_PATH.as_posix(): "100644",
        },
        context="P-E0-MZ authority",
    )
    for path, record in (
        (BASE_MZ_LOCK_PATH, lock),
        (BASE_MZ_COMPANION_PATH, companion),
    ):
        git_payload = _git_blob_bytes(repo_root, P_MZ_COMMIT, path)
        if record["bytes"] != len(git_payload) or record["sha256"] != _sha256_bytes(git_payload):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA P-E0-MZ physical input differs from Git: {path.as_posix()}"
            )
    if (
        lock["bytes"] != BASE_MZ_LOCK_BYTES
        or lock["sha256"] != BASE_MZ_LOCK_SHA256
        or companion["bytes"] != BASE_MZ_COMPANION_BYTES
        or companion["sha256"] != BASE_MZ_COMPANION_SHA256
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA sealed P-E0-MZ output hashes drifted"
        )
    lock_payload = _load_json(BASE_MZ_LOCK_PATH, repo_root=repo_root)
    companion_payload = _load_json(BASE_MZ_COMPANION_PATH, repo_root=repo_root)
    historical_inputs = companion_payload.get("historical_inputs")
    if (
        lock_payload.get("gate") != "E0-MZ"
        or lock_payload.get("status") != "locked_unpublished"
        or cast(Mapping[str, Any], lock_payload.get("repository", {})).get("head")
        != H_MZ_COMMIT
        or not isinstance(historical_inputs, list)
        or len(historical_inputs) != mz.EXPECTED_HISTORICAL_INPUT_COUNT
        or not _exact_equal(historical_inputs, mz._historical_inputs(repo_root))
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA P-E0-MZ semantic/history binding drifted"
        )
    return {
        "gate": "E0-MZ",
        "p_head": P_MZ_COMMIT,
        "h_head": H_MZ_COMMIT,
        "lock": lock,
        "companion": companion,
        "historical_inputs": [dict(record) for record in historical_inputs],
        "publication_reconstructed_from_git": True,
        "effective_loader_called": False,
    }


def _ordering_correction() -> dict[str, Any]:
    canonical = [path.as_posix() for path in _selection_payload_paths()]
    lexical = sorted(canonical)
    if (
        len(canonical) != EXPECTED_MISSING_POINTER_COUNT
        or len(set(canonical)) != EXPECTED_MISSING_POINTER_COUNT
        or set(canonical) != set(lexical)
        or canonical == lexical
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA sealed discovery/execution order distinction drifted"
        )
    return {
        "blocked_gate": "E0-MZ",
        "published_p_mz_head": P_MZ_COMMIT,
        "status": "blocked_pre_dvc_order_only",
        "missing_pointer_count": EXPECTED_MISSING_POINTER_COUNT,
        "missing_pointer_unique_count": EXPECTED_MISSING_POINTER_COUNT,
        "missing_pointer_set_exact": True,
        "discovery_order": "lexical_path",
        "discovered_paths": lexical,
        "execution_order": "alternating_a0_a1_within_seed",
        "canonical_execution_paths": canonical,
        "order_only_mismatch": True,
        "dvc_commands_run": False,
        "writes_performed": False,
        "pointers_created": 0,
        "models_dvc_changed": False,
    }


def _companion_physical_inputs(
    *,
    h_components: Sequence[Mapping[str, Any]],
    base_mz: Mapping[str, Any],
    historical_h_mz: Mapping[str, Any],
) -> list[dict[str, Any]]:
    records = [
        dict(cast(Mapping[str, Any], base_mz["lock"])),
        dict(cast(Mapping[str, Any], base_mz["companion"])),
        *(
            dict(record)
            for record in cast(
                Sequence[Mapping[str, Any]], historical_h_mz["preserved_components"]
            )
        ),
        *(dict(record) for record in h_components),
    ]
    identities = {(record["path"], record["role"]) for record in records}
    if len(records) != EXPECTED_COMPANION_INPUT_COUNT or len(identities) != len(records):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA companion physical inputs must be exact16"
        )
    return records


def _expected_untracked_light_status(repo_root: Path) -> list[str]:
    tracked = set(_git(repo_root, "ls-files", "--", *_light_paths()).splitlines())
    expected_tracked = set(_light_paths())
    if tracked != expected_tracked or len(tracked) != FAMILY_TRACKED_LIGHT_COUNT:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA all fifty light outputs must remain tracked"
        )
    return []


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


@_mza_error_boundary
def preflight_anfis_ablation_dvc_registration_order_patch_schema(
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA schema exceeds the supported subset: {unsupported}"
        )
    subset_validator = getattr(
        closure_contract, "_assert_supported_json_schema", None
    )
    if not callable(subset_validator):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "Closure JSON-schema definition validator is unavailable"
        )
    try:
        subset_validator(schema)
    except ClosureContractError as exc:
        raise AnfisAblationDvcRegistrationOrderPatchError(str(exc)) from exc
    encoded = _canonical_json(schema)
    return {
        "schema_path": DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
        "canonical_schema_bytes": len(encoded),
        "canonical_schema_sha256": _sha256_bytes(encoded),
        "supported_subset_verified": True,
        "unsupported_semantic_keywords": [],
    }


@_mza_error_boundary
def collect_anfis_ablation_dvc_registration_order_patch_prelock_state(
    *,
    verify_remote: bool = True,
    repo_root: Path | None = None,
    _allow_locker_guard: bool = False,
) -> dict[str, Any]:
    if type(verify_remote) is not bool or type(_allow_locker_guard) is not bool:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA prelock policies must be exact booleans"
        )
    root = _root(repo_root)
    preflight_anfis_ablation_dvc_registration_order_patch_schema(repo_root=root)
    head = _git_head(root)
    expected_scope = {
        "added": 5,
        "modified": 5,
        "deleted": 0,
        "paths": list(PATCH_PATHS),
    }
    if (
        _single_parent(root, head, context="H-E0-MZA") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, head) != expected_scope
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "H-E0-MZA must be the exact 5M+5A child of published P-E0-MZ"
        )
    _require_exact_git_modes(
        root, head, PATCH_COMPONENT_GIT_MODES, context="H-E0-MZA"
    )
    branch = _git(root, "branch", "--show-current").strip()
    tracking = _git_head(root, "origin/main")
    remote = _live_remote_main_head(root) if verify_remote else tracking
    if branch != "main" or tracking != head or remote != head:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "H-E0-MZA refs are not aligned with main"
        )
    status = [
        line
        for line in _git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
        if line
    ]
    expected_status = _expected_untracked_light_status(root)
    if status != expected_status:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA prelock worktree must be clean with all fifty lights tracked: {status}"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA prelock output namespace is occupied: {occupied_outputs}"
        )
    inventory = _registration_inventory(root)
    dvc_configuration = _dvc_configuration_contract(root)
    models_before = _base_models_owner(root)
    expected_registration = _expected_registration_records(root)
    h_components = _h_components(head, root)
    base_mz = _base_mz_authority(root)
    historical_h_mz = _historical_h_mz_authority(root)
    ordering = _ordering_correction()
    physical_inputs = _companion_physical_inputs(
        h_components=h_components,
        base_mz=base_mz,
        historical_h_mz=historical_h_mz,
    )
    historical_inputs = _historical_inputs(root)
    if len(historical_inputs) != EXPECTED_HISTORICAL_INPUT_COUNT:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA historical inputs must be exact13"
        )
    boundaries = _scientific_boundaries(root)
    if not all(boundaries.values()):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA scientific boundary drifted"
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
            "worktree_scope": "clean_all_50_light_outputs_tracked",
        },
        "h_patch": {
            "base_commit": BASE_COMMIT,
            "head": head,
            "parent": BASE_COMMIT,
            "component_count": len(h_components),
            "components": h_components,
            "components_sha256": _digest_records(h_components),
            "components_git_modes": dict(PATCH_COMPONENT_GIT_MODES),
            "scope": {"added": 5, "modified": 5, "deleted": 0},
        },
        "base_mz_authority": base_mz,
        "historical_h_mz": historical_h_mz,
        "ordering_correction": ordering,
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
            "ordered_slots": _expected_ordered_slots(),
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
            "missing_pointer_validation": {
                "count": EXPECTED_MISSING_POINTER_COUNT,
                "unique_count": EXPECTED_MISSING_POINTER_COUNT,
                "set_exact": True,
                "discovery_order": "lexical_path",
                "canonical_execution_order": "alternating_a0_a1_within_seed",
            },
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
            "light_report_addition_count": 0,
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


@_mza_error_boundary
def build_anfis_ablation_dvc_registration_order_patch_lock_payload(
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
        "base_mz_authority",
        "historical_h_mz",
        "ordering_correction",
        "artifact_inventory",
        "completed_family",
        "models_owner_transition",
        "registration_plan",
        "companion_contract",
        "prelock",
    }
    if set(prelock) != required:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA prelock bundle dialect drifted"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA {context} evidence dialect drifted"
        )
    if (
        value.get("command") != list(expected_command)
        or type(value.get("returncode")) is not int
        or value.get("returncode") != 0
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA {context} command/result drifted"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA {context} digest/line evidence drifted"
        )
    if exact_stdout is not None and (
        value.get("stdout_sha256") != _sha256_bytes(exact_stdout.encode("utf-8"))
        or value.get("stdout_line_count") != len(exact_stdout.splitlines())
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA {context} stdout evidence drifted"
        )


def _validate_verification(value: Any, *, repo_root: Path) -> None:
    if not isinstance(value, Mapping):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA verification evidence is absent"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA verification evidence key set drifted"
        )
    expected_schema = preflight_anfis_ablation_dvc_registration_order_patch_schema(
        repo_root=repo_root
    )
    if not _exact_equal(value.get("schema_preflight"), expected_schema):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA schema-preflight evidence drifted"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA focused pytest evidence drifted"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA focused pytest stdout text is absent"
        )
    parsed = _parse_focused_summary(stdout_text, "")
    if (
        parsed.get("test_count") != FOCUSED_TEST_COUNT
        or tests.get("stdout_sha256") != _sha256_bytes(stdout_text.encode("utf-8"))
        or tests.get("stdout_line_count") != len(stdout_text.splitlines())
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA focused pytest stdout binding drifted"
        )
    audit = value.get("family_semantic_audit")
    if (
        not isinstance(audit, Mapping)
        or audit.get("status") != "passed"
        or type(audit.get("slot_count")) is not int
        or audit.get("slot_count") != 10
        or not _exact_equal(audit.get("ordered_slots"), _expected_ordered_slots())
        or audit.get("dvc_command_executed") is not False
        or audit.get("future_outcomes_accessed") is not False
        or audit.get("writes_performed") is not False
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA family semantic audit evidence drifted"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA verification execution boundaries drifted"
        )


def _validate_anfis_ablation_dvc_registration_order_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    allow_registered_state: bool = False,
    repo_root: Path | None = None,
    _registration_transaction: Mapping[str, Any] | None = None,
) -> None:
    if type(allow_registered_state) is not bool:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA registered-state policy must be an exact boolean"
        )
    if _registration_transaction is not None and not allow_registered_state:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA private transaction record requires registered-state audit"
        )
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise AnfisAblationDvcRegistrationOrderPatchError(str(exc)) from exc
    _validate_timestamp(payload.get("created_at_utc"))
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("gate") != PATCH_GATE:
        raise AnfisAblationDvcRegistrationOrderPatchError("E0-MZA lock identity drifted")
    if not _exact_equal(payload.get("authorizations"), UNPUBLISHED_AUTHORIZATIONS):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA unpublished authorizations drifted"
        )
    if not _exact_equal(payload.get("seals"), LOCK_SEALS):
        raise AnfisAblationDvcRegistrationOrderPatchError("E0-MZA seals drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(repository.get("head"), str):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA repository binding is absent"
        )
    h_head = str(repository["head"])
    if (
        SHA1_RE.fullmatch(h_head) is None
        or repository.get("parent") != BASE_COMMIT
        or _single_parent(root, h_head, context="H-E0-MZA") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, h_head)
        != {"added": 5, "modified": 5, "deleted": 0, "paths": list(PATCH_PATHS)}
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA repository/H topology drifted"
        )
    h_components = _h_components(h_head, root)
    h_patch = payload.get("h_patch")
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
        raise AnfisAblationDvcRegistrationOrderPatchError("E0-MZA H binding drifted")
    base_mz = _base_mz_authority(root)
    if not _exact_equal(payload.get("base_mz_authority"), base_mz):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA published P-E0-MZ reconstruction drifted"
        )
    historical_h_mz = _historical_h_mz_authority(root)
    if not _exact_equal(payload.get("historical_h_mz"), historical_h_mz):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA historical H-E0-MZ reconstruction drifted"
        )
    ordering = _ordering_correction()
    if not _exact_equal(payload.get("ordering_correction"), ordering):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA blocked R-E0-MZ order incident binding drifted"
        )
    inventory = _registration_inventory(root)
    if not _exact_equal(payload.get("artifact_inventory"), inventory):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA registration inventory binding drifted"
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
        or completed.get("light_final_count") != FAMILY_LIGHT_COUNT
        or completed.get("tracked_light_count") != FAMILY_TRACKED_LIGHT_COUNT
        or completed.get("untracked_light_count") != FAMILY_UNTRACKED_LIGHT_COUNT
        or completed.get("heavy_final_count") != FAMILY_HEAVY_COUNT
        or completed.get("records") != family
        or completed.get("records_sha256") != FAMILY_RECORDS_SHA256
        or not _exact_equal(
            completed.get("ordered_slots"), _expected_ordered_slots()
        )
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA completed family binding drifted"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA models.dvc transition drifted"
        )
    plan = payload.get("registration_plan")
    expected_targets = [
        *(path.as_posix() for path in _selection_payload_paths()),
        MODELS_PATH.as_posix(),
    ]
    expected_missing_validation = {
        "count": EXPECTED_MISSING_POINTER_COUNT,
        "unique_count": EXPECTED_MISSING_POINTER_COUNT,
        "set_exact": True,
        "discovery_order": "lexical_path",
        "canonical_execution_order": "alternating_a0_a1_within_seed",
    }
    if (
        not isinstance(plan, Mapping)
        or plan.get("payload_target_count") != EXPECTED_REGISTRATION_GIT_PATH_COUNT
        or plan.get("payload_targets") != expected_targets
        or plan.get("dvc_add_commands") != _dvc_add_commands()
        or not _exact_equal(
            plan.get("missing_pointer_validation"), expected_missing_validation
        )
        or not _exact_equal(
            plan.get("dvc_configuration"), _dvc_configuration_contract(root)
        )
        or not _exact_equal(plan.get("expected_registration"), expected_registration)
        or plan.get("light_report_addition_count") != 0
        or plan.get("registration_git_scope")
        != {
            "added": EXPECTED_REGISTRATION_ADDED_COUNT,
            "modified": EXPECTED_REGISTRATION_MODIFIED_COUNT,
            "deleted": 0,
            "path_count": EXPECTED_REGISTRATION_GIT_PATH_COUNT,
        }
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA exact registration plan drifted"
        )
    physical = _companion_physical_inputs(
        h_components=h_components,
        base_mz=base_mz,
        historical_h_mz=historical_h_mz,
    )
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA companion contract drifted"
        )
    prelock = payload.get("prelock")
    if (
        not isinstance(prelock, Mapping)
        or prelock.get("family_records_sha256") != FAMILY_RECORDS_SHA256
        or prelock.get("untracked_light_count") != 0
        or prelock.get("ignored_heavy_count") != FAMILY_HEAVY_COUNT
        or prelock.get("selection_pointer_present_count") != 0
        or prelock.get("models_dvc_before_sha256") != BASE_MODELS_DVC_SHA256
        or prelock.get("general_inventory_count") != GENERAL_ARTIFACT_COUNT
        or prelock.get("registration_inventory_count") != REGISTRATION_ARTIFACT_COUNT
        or prelock.get("dvc_commands_run") is not False
        or prelock.get("outcome_paths_opened") is not False
        or prelock.get("writes_performed") is not False
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA prelock evidence drifted"
        )
    _validate_verification(payload.get("verification"), repo_root=root)


@_mza_error_boundary
def validate_anfis_ablation_dvc_registration_order_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    allow_registered_state: bool = False,
    repo_root: Path | None = None,
) -> None:
    _validate_anfis_ablation_dvc_registration_order_patch_lock_payload(
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
    base_mz = payload.get("base_mz_authority")
    historical_h_mz = payload.get("historical_h_mz")
    if (
        not isinstance(h_patch, Mapping)
        or not isinstance(base_mz, Mapping)
        or not isinstance(historical_h_mz, Mapping)
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "Cannot construct E0-MZA companion"
        )
    components = h_patch.get("components")
    if not isinstance(components, list):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "Cannot construct E0-MZA companion component list"
        )
    inputs = _companion_physical_inputs(
        h_components=cast(list[dict[str, Any]], components),
        base_mz=base_mz,
        historical_h_mz=historical_h_mz,
    )
    historical = _historical_inputs(root)
    script = next(
        (dict(record) for record in components if record.get("path") == LOCKER_PATH.as_posix()),
        None,
    )
    if script is None:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA companion script is absent"
        )
    output = dict(lock_record)
    if (
        output.get("path") != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or output.get("role") != "anfis_ablation_dvc_registration_order_patch_lock"
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA companion output record drifted"
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
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA verification command failed: {list(command)}"
        )
    return evidence, result.stdout, result.stderr


def _parse_focused_summary(stdout: str, stderr: str) -> dict[str, int]:
    if stderr or FORBIDDEN_FOCUSED_SUMMARY_RE.search(stdout):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA focused pytest result is not one clean pass"
        )
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    matches = [FOCUSED_SUMMARY_RE.fullmatch(line) for line in lines]
    matched = [match for match in matches if match is not None]
    if len(matched) != 1 or lines[-1] != matched[0].group(0):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA focused pytest summary is not unique and terminal"
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
        "ordered_slots": _expected_ordered_slots(),
        "dvc_command_executed": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


@_mza_error_boundary
def run_anfis_ablation_dvc_registration_order_patch_verification(
    *,
    family_snapshot: Sequence[Mapping[str, Any]] | None = None,
    publication_input_snapshot: Sequence[Mapping[str, Any]] | None = None,
    publication_git_snapshot: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    baseline = (
        tuple(family_snapshot)
        if family_snapshot is not None
        else _family_physical_snapshot(root)
    )
    input_baseline = (
        tuple(publication_input_snapshot)
        if publication_input_snapshot is not None
        else _publication_input_snapshot(root)
    )
    git_baseline = (
        dict(publication_git_snapshot)
        if publication_git_snapshot is not None
        else _publication_git_snapshot(root)
    )
    _require_publication_state(
        input_baseline,
        git_baseline,
        repo_root=root,
        context="before schema preflight",
        allow_locker_guard=False,
    )
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="before schema preflight"
    )
    schema = preflight_anfis_ablation_dvc_registration_order_patch_schema(repo_root=root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after schema preflight"
    )
    _require_publication_state(input_baseline, git_baseline, repo_root=root, context="after schema preflight", allow_locker_guard=False)
    type_check, _, _ = _run_command(TYPE_CHECK_COMMAND, repo_root=root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after type check"
    )
    _require_publication_state(input_baseline, git_baseline, repo_root=root, context="after type check", allow_locker_guard=False)
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
    _require_publication_state(input_baseline, git_baseline, repo_root=root, context="after focused tests", allow_locker_guard=False)
    poetry, _, _ = _run_command(POETRY_CHECK_COMMAND, repo_root=root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after poetry check"
    )
    _require_publication_state(input_baseline, git_baseline, repo_root=root, context="after poetry check", allow_locker_guard=False)
    publication, _, _ = _run_command(PUBLICATION_GUARD_COMMAND, repo_root=root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after publication guard"
    )
    _require_publication_state(input_baseline, git_baseline, repo_root=root, context="after publication guard", allow_locker_guard=False)
    diff, _, _ = _run_command(DIFF_CHECK_COMMAND, repo_root=root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after diff check"
    )
    _require_publication_state(input_baseline, git_baseline, repo_root=root, context="after diff check", allow_locker_guard=False)
    family = _family_semantic_audit(root)
    _require_family_physical_snapshot(
        baseline, repo_root=root, context="after semantic family audit"
    )
    _require_publication_state(input_baseline, git_baseline, repo_root=root, context="after semantic family audit", allow_locker_guard=False)
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


def _rollback_published_outputs_best_effort(
    published: Sequence[mt._OwnedOutput],
) -> AnfisAblationDvcRegistrationOrderPatchError | None:
    first_error: AnfisAblationDvcRegistrationOrderPatchError | None = None
    for output in reversed(published):
        try:
            mt._rollback_owned_output(output)
        except Exception as exc:
            if first_error is None:
                first_error = AnfisAblationDvcRegistrationOrderPatchError(
                    "E0-MZA owned-output rollback failed for "
                    f"{output.path.as_posix()}: {exc}"
                )
    return first_error


def _close_published_outputs_best_effort(
    published: Sequence[mt._OwnedOutput],
) -> None:
    first_error: AnfisAblationDvcRegistrationOrderPatchError | None = None
    for output in published:
        try:
            mt._close_owned_output(output)
        except Exception as exc:
            if first_error is None:
                first_error = AnfisAblationDvcRegistrationOrderPatchError(
                    "E0-MZA owned-output descriptor close failed for "
                    f"{output.path.as_posix()}: {exc}"
                )
    if first_error is not None:
        raise first_error


def _validate_owned_output_bytes(
    output: mt._OwnedOutput,
    expected_payload: bytes,
    *,
    context: str,
) -> None:
    descriptor: int | None = None
    try:
        mt._validate_owned_output(output)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(
            output.name, flags, dir_fd=output.parent_descriptor
        )
        before = os.fstat(descriptor)
        named_before = os.stat(
            output.name,
            dir_fd=output.parent_descriptor,
            follow_symlinks=False,
        )
        expected_identity = (output.device, output.inode)
        if (
            (before.st_dev, before.st_ino) != expected_identity
            or (named_before.st_dev, named_before.st_ino) != expected_identity
            or not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o644
            or before.st_nlink != 1
            or before.st_size != len(expected_payload)
        ):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA owned output identity/metadata drifted {context}: "
                f"{output.path.as_posix()}"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        named_after = os.stat(
            output.name,
            dir_fd=output.parent_descriptor,
            follow_symlinks=False,
        )
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        named_identity = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_mode,
            named_after.st_nlink,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if (
            before_identity != after_identity
            or after_identity != named_identity
            or b"".join(chunks) != expected_payload
        ):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA owned output bytes drifted {context}: "
                f"{output.path.as_posix()}"
            )
        mt._validate_owned_output(output)
    except AnfisAblationDvcRegistrationOrderPatchError:
        raise
    except Exception as exc:
        raise _translate(exc) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


@_mza_error_boundary
def execute_and_publish_anfis_ablation_dvc_registration_order_patch_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    family_snapshot = _family_physical_snapshot(root)
    input_snapshot = _publication_input_snapshot(root)
    git_snapshot = _publication_git_snapshot(root)
    before = collect_anfis_ablation_dvc_registration_order_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    verification = run_anfis_ablation_dvc_registration_order_patch_verification(
        family_snapshot=family_snapshot,
        publication_input_snapshot=input_snapshot,
        publication_git_snapshot=git_snapshot,
        repo_root=root,
    )
    after = collect_anfis_ablation_dvc_registration_order_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    if not _exact_equal(before, after):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA prelock state changed during verification"
        )
    _require_family_physical_snapshot(
        family_snapshot, repo_root=root, context="after final prelock collection"
    )
    _require_publication_state(input_snapshot, git_snapshot, repo_root=root, context="after final prelock collection", allow_locker_guard=False)
    payload = build_anfis_ablation_dvc_registration_order_patch_lock_payload(
        before, verification, created_at_utc=datetime.now(timezone.utc).isoformat()
    )
    validate_anfis_ablation_dvc_registration_order_patch_lock_payload(payload, repo_root=root)
    controlled = (
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        _temporary_path(DEFAULT_PATCH_LOCK_PATH),
        _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        LOCKER_GUARD_PATH,
    )
    occupied = [path.as_posix() for path in controlled if _lexists(root / path)]
    if occupied:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            f"E0-MZA lock namespace is occupied: {occupied}"
        )
    guard: mt._OwnedGuard | None = None
    published: list[mt._OwnedOutput] = []
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MZA lock bundle publication in progress\n",
            repo_root=root,
        )
        _require_family_physical_snapshot(
            family_snapshot, repo_root=root, context="after guard acquisition"
        )
        _require_publication_state(input_snapshot, git_snapshot, repo_root=root, context="after guard acquisition", allow_locker_guard=True)
        if not _exact_equal(
            before,
            collect_anfis_ablation_dvc_registration_order_patch_prelock_state(
                verify_remote=True,
                repo_root=root,
                _allow_locker_guard=True,
            ),
        ):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                "E0-MZA guarded prelock state drifted"
            )
        lock_bytes = _canonical_json(payload)
        lock_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, lock_bytes, repo_root=root
        )
        published.append(lock_output)
        _validate_owned_output_bytes(
            lock_output, lock_bytes, context="after lock publication"
        )
        _require_family_physical_snapshot(
            family_snapshot, repo_root=root, context="after lock publication"
        )
        _require_publication_state(input_snapshot, git_snapshot, repo_root=root, context="after lock publication", allow_locker_guard=True)
        _validate_owned_output_bytes(
            lock_output, lock_bytes, context="before companion construction"
        )
        lock_record = {
            "role": "anfis_ablation_dvc_registration_order_patch_lock",
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "bytes": len(lock_bytes),
            "sha256": _sha256_bytes(lock_bytes),
        }
        companion = _expected_companion(payload, lock_record, repo_root=root)
        companion_bytes = _canonical_json(companion)
        companion_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            companion_bytes,
            repo_root=root,
        )
        published.append(companion_output)
        _validate_owned_output_bytes(
            lock_output, lock_bytes, context="after companion publication"
        )
        _validate_owned_output_bytes(
            companion_output,
            companion_bytes,
            context="after companion publication",
        )
        _require_family_physical_snapshot(
            family_snapshot, repo_root=root, context="after companion publication"
        )
        _require_publication_state(input_snapshot, git_snapshot, repo_root=root, context="after companion publication", allow_locker_guard=True)
        _validate_owned_output_bytes(
            lock_output, lock_bytes, context="before guard release"
        )
        _validate_owned_output_bytes(
            companion_output, companion_bytes, context="before guard release"
        )
        _require_family_physical_snapshot(
            family_snapshot, repo_root=root, context="before guard release"
        )
        _require_publication_state(input_snapshot, git_snapshot, repo_root=root, context="before guard release", allow_locker_guard=True)
        mt._release_publication_guard(guard)
        guard = None
        _require_family_physical_snapshot(
            family_snapshot, repo_root=root, context="after guard release"
        )
        _require_publication_state(input_snapshot, git_snapshot, repo_root=root, context="after guard release", allow_locker_guard=False)
        _validate_owned_output_bytes(
            lock_output, lock_bytes, context="after guard release"
        )
        _validate_owned_output_bytes(
            companion_output, companion_bytes, context="after guard release"
        )
        committed = True
        return payload, companion
    except BaseException as exc:
        rollback_error = _rollback_published_outputs_best_effort(published)
        if isinstance(exc, AnfisAblationDvcRegistrationOrderPatchError):
            translated = exc
        elif isinstance(exc, Exception):
            translated = _translate(exc)
        else:
            if rollback_error is not None:
                exc.add_note(str(rollback_error))
            raise
        if rollback_error is not None:
            translated.add_note(str(rollback_error))
        if translated is exc:
            raise
        raise translated from exc
    finally:
        if guard is not None:
            mt._release_publication_guard(guard, tolerate_foreign=True)
        if committed:
            _close_published_outputs_best_effort(published)


@_mza_error_boundary
def publish_anfis_ablation_dvc_registration_order_patch_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    return execute_and_publish_anfis_ablation_dvc_registration_order_patch_lock_bundle(
        repo_root=repo_root
    )


def _validate_p_publication(
    payload: Mapping[str, Any], *, repo_root: Path
) -> dict[str, str]:
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(repository.get("head"), str):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA H repository binding is absent"
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
        or _single_parent(repo_root, head, context="P-E0-MZA") != h_head
        or tracking != head
        or remote != head
        or _git_scope(repo_root, h_head, head)
        != {"added": 2, "modified": 0, "deleted": 0, "paths": expected_paths}
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "Published P-E0-MZA topology/refs drifted"
        )
    _require_exact_git_modes(
        repo_root,
        head,
        {path: "100644" for path in expected_paths},
        context="P-E0-MZA",
    )
    for raw_path in expected_paths:
        path = Path(raw_path)
        physical = _read_regular_bytes(
            path, repo_root=repo_root, require_nlink_one=True
        )
        if physical != _git_blob_bytes(repo_root, head, path):
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"Published P-E0-MZA physical bytes differ from Git: {raw_path}"
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
            raise AnfisAblationDvcRegistrationOrderPatchError(
                f"E0-MZA registered pointer drifted: {path.as_posix()}"
            )
    models = cast(Mapping[str, Any], expected["models_dvc"])
    payload = _read_regular_bytes(
        MODELS_DVC_PATH, repo_root=repo_root, require_nlink_one=True
    )
    if len(payload) != models["bytes"] or _sha256_bytes(payload) != models["sha256"]:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA registered models.dvc drifted"
        )
    return {
        "selection_pointer_count": len(pointers),
        "models_dvc_sha256": _sha256_bytes(payload),
        "registration_state": "post_dvc_unpublished",
    }


def _load_effective_anfis_ablation_dvc_registration_order_patch_authority(
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
    _registration_transaction: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if type(audit_current_unpublished) is not bool or verify_remote is not True:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA effective authority requires exact audit mode and live remote"
        )
    root = _root(repo_root)
    payload_bytes = _read_regular_bytes(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    try:
        payload = json.loads(payload_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "Published E0-MZA lock is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(payload, dict) or payload_bytes != _canonical_json(payload):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "Published E0-MZA lock is not canonical JSON"
        )
    # The lock was generated in pre-DVC state.  Validation reconstructs every
    # immutable binding directly and does not permit pointers yet.
    _validate_anfis_ablation_dvc_registration_order_patch_lock_payload(
        payload,
        allow_registered_state=audit_current_unpublished,
        repo_root=root,
        _registration_transaction=_registration_transaction,
    )
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="anfis_ablation_dvc_registration_order_patch_lock",
        repo_root=root,
    )
    companion_bytes = _read_regular_bytes(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root)
    try:
        companion = json.loads(companion_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "Published E0-MZA companion is not valid UTF-8 JSON"
        ) from exc
    expected_companion = _expected_companion(payload, lock_record, repo_root=root)
    if (
        not isinstance(companion, dict)
        or companion_bytes != _canonical_json(companion)
        or not _exact_equal(companion, expected_companion)
    ):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "Published E0-MZA companion drifted"
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
            role="anfis_ablation_dvc_registration_order_patch_lock_manifest",
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


@_mza_error_boundary
def load_effective_anfis_ablation_dvc_registration_order_patch_authority(
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Public authority loader; transaction coordination must be absent."""
    return _load_effective_anfis_ablation_dvc_registration_order_patch_authority(
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
        _registration_transaction=None,
    )


@_mza_error_boundary
def _load_effective_anfis_ablation_dvc_registration_order_patch_during_registration(
    *,
    transaction_record: Mapping[str, Any],
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Internal R-E0-MZA audit while durable rollback coordination is owned."""
    if not isinstance(transaction_record, Mapping):
        raise AnfisAblationDvcRegistrationOrderPatchError(
            "E0-MZA internal transaction record is absent"
        )
    return _load_effective_anfis_ablation_dvc_registration_order_patch_authority(
        audit_current_unpublished=True,
        verify_remote=verify_remote,
        repo_root=repo_root,
        _registration_transaction=transaction_record,
    )


@_mza_error_boundary
def require_anfis_ablation_dvc_registration_order_patch_authority(
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    return load_effective_anfis_ablation_dvc_registration_order_patch_authority(
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


@_mza_error_boundary
def require_anfis_ablation_dvc_registration_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    """Exact lazy-loader API consumed by the precommit registration profile."""
    return require_anfis_ablation_dvc_registration_order_patch_authority(
        audit_current_unpublished=False,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


@_mza_error_boundary
def require_anfis_ablation_dvc_registration_adoption_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    """Compatibility lazy-loader spelling consumed by the registration helper."""
    return require_anfis_ablation_dvc_registration_order_patch_authority(
        audit_current_unpublished=False,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


@_mza_error_boundary
def load_effective_anfis_ablation_dvc_registration_order_patch(
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Compatibility spelling used by the publication assistant."""
    return load_effective_anfis_ablation_dvc_registration_order_patch_authority(
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )


__all__ = [
    "AnfisAblationDvcRegistrationOrderPatchError",
    "ANFIS_ABLATION_H_MZA_STAGED_SCOPE",
    "ANFIS_ABLATION_P_MZA_STAGED_SCOPE",
    "ANFIS_ABLATION_R_MZA_STAGED_SCOPE",
    "BASE_COMMIT",
    "H_MZ_COMMIT",
    "P_MZ_COMMIT",
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
    "build_anfis_ablation_dvc_registration_order_patch_lock_payload",
    "collect_anfis_ablation_dvc_registration_order_patch_prelock_state",
    "execute_and_publish_anfis_ablation_dvc_registration_order_patch_lock_bundle",
    "load_effective_anfis_ablation_dvc_registration_order_patch_authority",
    "load_effective_anfis_ablation_dvc_registration_order_patch",
    "preflight_anfis_ablation_dvc_registration_order_patch_schema",
    "publish_anfis_ablation_dvc_registration_order_patch_lock_bundle",
    "require_anfis_ablation_dvc_registration_authority",
    "require_anfis_ablation_dvc_registration_adoption_authority",
    "require_anfis_ablation_dvc_registration_order_patch_authority",
    "run_anfis_ablation_dvc_registration_order_patch_verification",
    "validate_anfis_ablation_dvc_registration_order_patch_lock_payload",
]
