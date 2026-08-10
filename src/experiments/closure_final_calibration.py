"""Lock the development-only final calibration and E7 terminal contract.

E0-MCAL is deliberately separate from E0-M and E0-U.  Its H/P phases inspect
only versioned metadata and the already-registered ANFIS family.  Its effective
authority permits the two closed development-only runners to create eight
lightweight outputs; it never authorizes holdout, post-2021, outcome, DVC, or
network access.
"""

from __future__ import annotations

import hashlib
import csv
import io
import json
import math
import os
import re
import stat
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, cast

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode
from yaml.resolver import BaseResolver

from src.experiments import (
    closure_anfis_ablation_dvc_registration_reproducibility_patch as mze,
)
from src.experiments import closure_anfis_ablation_training_development_patch as mt
from src.experiments import closure_contract
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = "2f46d3e258195315e2473be6cf7d62db22c55bcf"
P_MZE_COMMIT = "e4312b403a4be729051ce2809fb5dcb4c505c509"
H_MZE_COMMIT = "c2df3df886c5fb3591f78fd835a263072eadda4e"
PATCH_GATE = "E0-MCAL"
FINAL_CALIBRATION_GATE = PATCH_GATE
EXPERIMENT_ID = "closure_v1"
RUNTIME_SCHEMA_VERSION = "closure_final_calibration_runtime_v1"
LOCK_SCHEMA_VERSION = "closure_final_calibration_lock_v1"
COMPANION_SCHEMA_VERSION = "closure_final_calibration_lock_manifest_v1"

DEFAULT_RUNTIME_PATH = Path("configs/closure_v1/final_calibration_runtime.yaml")
DEFAULT_RUNTIME_SCHEMA = Path(
    "configs/closure_v1/final_calibration_runtime.schema.json"
)
DEFAULT_LOCK_SCHEMA = Path("configs/closure_v1/final_calibration_lock.schema.json")
DEFAULT_PATCH_LOCK_SCHEMA = DEFAULT_LOCK_SCHEMA
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/final_calibration_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/final_calibration_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_PATH = Path("src/experiments/lock_closure_final_calibration.py")
CALIBRATION_RUNNER_PATH = Path("src/experiments/calibrate_closure_final_models.py")
E7_RUNNER_PATH = Path("src/experiments/run_closure_anfis_learning_curve.py")
LOCKER_GUARD_PATH = Path("tmp/closure_v1_e0_mcal/final_calibration_lock.guard")
CALIBRATION_GUARD_PATH = Path("tmp/closure_v1_e0_mcal/final_calibration.guard")
E7_GUARD_PATH = Path("tmp/closure_v1_e0_mcal/anfis_learning_curve.guard")

PATCH_PATHS = tuple(
    sorted(
        {
            "configs/closure_v1/final_calibration_runtime.yaml",
            "configs/closure_v1/final_calibration_runtime.schema.json",
            "configs/closure_v1/final_calibration_lock.schema.json",
            "docs/closure_v1/E0_M_FINAL_CALIBRATION.md",
            "src/experiments/calibrate_closure_final_models.py",
            "src/experiments/closure_final_calibration.py",
            "src/experiments/lock_closure_final_calibration.py",
            "src/experiments/run_closure_anfis_learning_curve.py",
            "tests/test_calibrate_closure_final_models.py",
            "tests/test_closure_anfis_learning_curve.py",
            "tests/test_closure_final_calibration.py",
            "tests/test_lock_closure_final_calibration.py",
        }
    )
)
PATCH_COMPONENT_ROLES = {path: "final_calibration_h_component" for path in PATCH_PATHS}
PATCH_COMPONENT_GIT_MODES = {path: "100644" for path in PATCH_PATHS}
FINAL_CALIBRATION_H_STAGED_SCOPE = {path: "A" for path in PATCH_PATHS}
FINAL_CALIBRATION_P_STAGED_SCOPE = {
    DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
    DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
}

CALIBRATOR_SPECS_PATH = Path(
    "reports/closure_v1/03_calibration/calibrator_specs.json"
)
CALIBRATION_METRICS_PATH = Path(
    "reports/closure_v1/03_calibration/calibration_metrics.csv"
)
ALERT_THRESHOLDS_PATH = Path(
    "reports/closure_v1/03_calibration/alert_thresholds.csv"
)
ORDINAL_CUTPOINTS_PATH = Path(
    "reports/closure_v1/03_calibration/ordinal_cutpoints.csv"
)
MODEL_AVAILABILITY_PATH = Path(
    "reports/closure_v1/03_calibration/model_availability.csv"
)
FINAL_CALIBRATION_MANIFEST_PATH = Path(
    "reports/closure_v1/03_calibration/final_calibration_manifest.json"
)
ANFIS_LEARNING_CURVE_PATH = Path(
    "reports/closure_v1/07_anfis_ablation/anfis_learning_curve.csv"
)
ANFIS_LEARNING_CURVE_MANIFEST_PATH = Path(
    "reports/closure_v1/07_anfis_ablation/anfis_learning_curve_manifest.json"
)
CALIBRATION_OUTPUT_PATHS = (
    CALIBRATOR_SPECS_PATH,
    CALIBRATION_METRICS_PATH,
    ALERT_THRESHOLDS_PATH,
    ORDINAL_CUTPOINTS_PATH,
    MODEL_AVAILABILITY_PATH,
    FINAL_CALIBRATION_MANIFEST_PATH,
)
E7_OUTPUT_PATHS = (ANFIS_LEARNING_CURVE_PATH, ANFIS_LEARNING_CURVE_MANIFEST_PATH)
R_OUTPUT_PATHS = (*CALIBRATION_OUTPUT_PATHS, *E7_OUTPUT_PATHS)
FINAL_CALIBRATION_R_STAGED_SCOPE = {
    path.as_posix(): "A" for path in R_OUTPUT_PATHS
}

MODEL_IDS = ("B0", "B1", "B2", "F0", "F1", "P0", "P1", "M0", "A0", "A1", "A2")
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
HORIZONS_MONTHS = (1, 2, 3)
Q_C_LEVELS = (0.80, 0.90, 0.95)
CALIBRABLE_MODEL_IDS = ("B0", "B1", "B2", "M0", "A0", "A1")
ORDINAL_MODEL_IDS = ("B0", "B1", "B2")
UNCERTAINTY_MODEL_IDS = ("A0", "A1")
NOT_APPLICABLE_MODEL_IDS = ("F0", "F1")
UNAVAILABLE_MODEL_IDS = ("P0", "P1", "A2")
MODEL_COUNT = 11
BLOOM_GROUP_COUNT = 66
ORDINAL_GROUP_COUNT = 33
ORDINAL_COMPLETED_GROUP_COUNT = 30
ORDINAL_UNAVAILABLE_GROUP_COUNT = 3
UNCERTAINTY_GROUP_COUNT = 30
Q_C_RECORD_COUNT = 90
FAMILY_FINAL_COUNT = 80
FAMILY_RECORDS_SHA256 = mze.FAMILY_RECORDS_SHA256
SELECTION_POINTER_COUNT = 10
REGISTERED_PATH_COUNT = 11
EXPECTED_MODELS_DVC_SHA256 = mze.EXPECTED_MODELS_DVC_SHA256
EXPECTED_COMPANION_INPUT_COUNT = 12
EXPECTED_HISTORICAL_INPUT_COUNT = 0
EXPECTED_COMPANION_OUTPUT_COUNT = 1
SCIENTIFIC_AUTHORITY_RECORD_COUNT = 66
SCIENTIFIC_PAYLOAD_BINDING_COUNT = 94
CALIBRATION_PAYLOAD_BINDING_COUNT = 53
CALIBRATION_LINEAGE_BINDING_COUNT = 2
F1_AVAILABILITY_BINDING_COUNT = 20
E7_RUNTIME_BINDING_COUNT = 9
UNAVAILABLE_TEMPORAL_REPORT_BINDING_COUNT = 10
CALIBRATION_REQUIRED_INPUT_COUNT = 97
E7_REQUIRED_INPUT_COUNT = 15
EXPECTED_DEVELOPMENT_RUNTIME_SCHEMA_VERSION = "closure_development_runtime_v1"
EXPECTED_DEVELOPMENT_RUNTIME_AUDIT_SHA256 = (
    "fbbd1700216d31909bc34173baecb08942be726cb4fd20d59367a89c0de03bd6"
)
P0_P1_PUBLICATION_COMMITS = (
    "f4a6c3367d20deeb7416e9f0d4cbc9c3a9446a3f",
    "118b404cdc98a144fe392aa6085c49f0eb97348d",
    "f27ee8a105a623611220e7c10630efe1a676599a",
    "8d776ce31a13ebb6cc0e6c219de89f5356aed2fd",
    "1a4aa4836548756e74008fb934f56b5251d22491",
    "5d8bbef0fe58e57cd2180570bd6aef5f07923781",
    "5b2c5d6b4f4c296c9485d1cb22561086aeeb6b85",
    "fea057b808e2e454c47da1256a5ec8f68dd9bb80",
    "46daf1e2dd97a3d7e36ad187d4ae1510dfc14fc2",
    "a9aa51aaa1566d0b8e7154697fae69c458c5019f",
)
HISTORICAL_E7_BLOCKER_PATHS = (
    Path("configs/closure_v1/development_runtime.yaml"),
    Path("configs/closure_v1/anfis_ablation_training_development_runtime.yaml"),
    Path("configs/closure_v1/anfis_ablation_sequence_development_runtime.yaml"),
)

TYPE_CHECK_COMMAND = ("poetry", "run", "ty", "check")
FOCUSED_TEST_COMMAND = (
    "poetry",
    "run",
    "pytest",
    "-q",
    "tests/test_closure_final_calibration.py",
    "tests/test_lock_closure_final_calibration.py",
    "tests/test_calibrate_closure_final_models.py",
    "tests/test_closure_anfis_learning_curve.py",
)
FOCUSED_TEST_COUNT = 64
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

UNPUBLISHED_AUTHORIZATIONS = {
    "calibration_development_run_authorized": False,
    "e7_learning_curve_run_authorized": False,
    "holdout_access_authorized": False,
    "post_2021_access_authorized": False,
    "locked_evaluation_authorized": False,
    "outcome_access_authorized": False,
    "e0_m_authorized": False,
    "e0_u_authorized": False,
    "dvc_commands_authorized": False,
    "dvc_push_authorized": False,
    "git_commit_authorized": False,
    "git_push_authorized": False,
    "scientific_network_authorized": False,
    "effective_in_payload": False,
}


class FinalCalibrationError(RuntimeError):
    """Raised when E0-MCAL inputs, boundaries, topology, or outputs drift."""


_P = ParamSpec("_P")
_R = TypeVar("_R")


def _translate(exc: BaseException) -> FinalCalibrationError:
    return FinalCalibrationError(str(exc))


def _error_boundary(function: Callable[_P, _R]) -> Callable[_P, _R]:
    @wraps(function)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return function(*args, **kwargs)
        except FinalCalibrationError:
            raise
        except Exception as exc:
            raise _translate(exc) from exc

    return wrapped


def _root(repo_root: Path | None) -> Path:
    return PROJECT_ROOT if repo_root is None else repo_root.resolve()


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_records(records: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_bytes(
        json.dumps(
            list(records),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    )


def _deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _temporary_path(path: Path) -> Path:
    return Path(f"{path.as_posix()}.tmp")


# Implementations follow below; keeping every public spelling here makes the
# H contract importable while the strict authority remains one closed module.


def _open_anchored_parent(path: Path, *, repo_root: Path) -> tuple[int, str]:
    if path.is_absolute() or not path.parts or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise FinalCalibrationError(
            f"E0-MCAL path must be repository-relative: {path.as_posix()}"
        )
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(repo_root, flags)
    try:
        for component in path.parts[:-1]:
            child = os.open(component, flags, dir_fd=descriptor)
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
    expected_mode: int = 0o644,
    require_nlink_one: bool = True,
) -> tuple[bytes, os.stat_result]:
    parent: int | None = None
    descriptor: int | None = None
    try:
        parent, name = _open_anchored_parent(path, repo_root=repo_root)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(name, flags, dir_fd=parent)
        before = os.fstat(descriptor)
        named_before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(named_before.st_mode)
            or (before.st_dev, before.st_ino)
            != (named_before.st_dev, named_before.st_ino)
            or stat.S_IMODE(before.st_mode) != expected_mode
            or stat.S_IMODE(named_before.st_mode) != expected_mode
            or (
                require_nlink_one
                and (before.st_nlink != 1 or named_before.st_nlink != 1)
            )
        ):
            raise FinalCalibrationError(
                f"E0-MCAL path is not one stable regular {expected_mode:04o} file: "
                f"{path.as_posix()}"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        named_after = os.stat(name, dir_fd=parent, follow_symlinks=False)
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
            or (named_before.st_dev, named_before.st_ino)
            != (named_after.st_dev, named_after.st_ino)
        ):
            raise FinalCalibrationError(
                f"E0-MCAL path changed during anchored read: {path.as_posix()}"
            )
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise FinalCalibrationError(
                f"E0-MCAL path produced a short anchored read: {path.as_posix()}"
            )
        return payload, after
    except OSError as exc:
        raise FinalCalibrationError(
            f"E0-MCAL cannot read closed path {path.as_posix()}: {exc}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent is not None:
            os.close(parent)


def _read_regular_bytes(
    path: Path,
    *,
    repo_root: Path,
    expected_mode: int = 0o644,
    require_nlink_one: bool = True,
) -> bytes:
    payload, _ = _read_regular_bytes_and_metadata(
        path,
        repo_root=repo_root,
        expected_mode=expected_mode,
        require_nlink_one=require_nlink_one,
    )
    return payload


def _entry_exists(path: Path, *, repo_root: Path) -> bool:
    parent: int | None = None
    try:
        parent, name = _open_anchored_parent(path, repo_root=repo_root)
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise FinalCalibrationError(
            f"E0-MCAL cannot inspect closed namespace {path.as_posix()}: {exc}"
        ) from exc
    finally:
        if parent is not None:
            os.close(parent)


def _file_record(
    path: Path, *, role: str, repo_root: Path, expected_mode: int = 0o644
) -> dict[str, Any]:
    payload, _ = _read_regular_bytes_and_metadata(
        path, repo_root=repo_root, expected_mode=expected_mode
    )
    return {
        "role": role,
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _git(
    repo_root: Path,
    *args: str,
    input_bytes: bytes | None = None,
    text: bool = True,
) -> str | bytes:
    try:
        result = subprocess.run(
            ["git", "-C", repo_root.as_posix(), *args],
            input=input_bytes,
            capture_output=True,
            check=False,
            text=False,
        )
    except OSError as exc:
        raise FinalCalibrationError(f"E0-MCAL Git invocation failed: {exc}") from exc
    if result.returncode != 0 or result.stderr:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise FinalCalibrationError(
            f"E0-MCAL Git command failed: {' '.join(args)}: {stderr}"
        )
    if text:
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FinalCalibrationError("E0-MCAL Git output is not UTF-8") from exc
    return result.stdout


def _git_head(repo_root: Path, ref: str = "HEAD") -> str:
    value = cast(str, _git(repo_root, "rev-parse", "--verify", ref)).strip()
    if SHA1_RE.fullmatch(value) is None:
        raise FinalCalibrationError(f"E0-MCAL Git ref is malformed: {ref}")
    return value


def _single_parent(repo_root: Path, commit: str, *, context: str) -> str:
    line = cast(str, _git(repo_root, "show", "-s", "--format=%P", commit)).strip()
    parents = line.split()
    if len(parents) != 1 or SHA1_RE.fullmatch(parents[0]) is None:
        raise FinalCalibrationError(f"E0-MCAL {context} must have one exact parent")
    return parents[0]


def _git_scope(repo_root: Path, parent: str, head: str) -> dict[str, Any]:
    raw = cast(
        str,
        _git(
            repo_root,
            "diff",
            "--name-status",
            "--no-renames",
            parent,
            head,
            "--",
        ),
    )
    records: list[tuple[str, str]] = []
    for line in raw.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"A", "M", "D"} or not fields[1]:
            raise FinalCalibrationError("E0-MCAL Git scope dialect drifted")
        records.append((fields[0], fields[1]))
    paths = sorted(path for _, path in records)
    if len(paths) != len(set(paths)):
        raise FinalCalibrationError("E0-MCAL Git scope contains duplicate paths")
    return {
        "added": sum(status == "A" for status, _ in records),
        "modified": sum(status == "M" for status, _ in records),
        "deleted": sum(status == "D" for status, _ in records),
        "path_count": len(records),
        "paths": paths,
    }


def _git_blob_bytes(repo_root: Path, commit: str, path: Path) -> bytes:
    return cast(
        bytes,
        _git(repo_root, "show", f"{commit}:{path.as_posix()}", text=False),
    )


def _git_mode_oid(repo_root: Path, commit: str, path: Path) -> tuple[str, str]:
    raw = cast(
        bytes,
        _git(
            repo_root,
            "ls-tree",
            "-z",
            commit,
            "--",
            path.as_posix(),
            text=False,
        ),
    )
    entries = [entry for entry in raw.split(b"\0") if entry]
    if len(entries) != 1 or b"\t" not in entries[0]:
        raise FinalCalibrationError(
            f"E0-MCAL Git tree binding is absent: {commit}:{path.as_posix()}"
        )
    metadata, raw_path = entries[0].split(b"\t", 1)
    fields = metadata.decode("ascii").split()
    if (
        len(fields) != 3
        or fields[1] != "blob"
        or raw_path.decode("utf-8") != path.as_posix()
        or fields[0] not in {"100644", "100755"}
        or SHA1_RE.fullmatch(fields[2]) is None
    ):
        raise FinalCalibrationError(
            f"E0-MCAL Git tree binding drifted: {commit}:{path.as_posix()}"
        )
    return fields[0], fields[2]


def _blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _git_artifact_record(
    path: Path,
    *,
    role: str,
    repo_root: Path,
    commit: str | None,
    expected_mode: str = "100644",
) -> dict[str, Any]:
    payload = _read_regular_bytes(
        path,
        repo_root=repo_root,
        expected_mode=int(expected_mode[-3:], 8),
    )
    if commit is None:
        mode, oid = expected_mode, _blob_oid(payload)
    else:
        mode, oid = _git_mode_oid(repo_root, commit, path)
        if mode != expected_mode or payload != _git_blob_bytes(repo_root, commit, path):
            raise FinalCalibrationError(
                f"E0-MCAL physical/Git binding drifted: {path.as_posix()}"
            )
    return {
        "role": role,
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "git_oid": oid,
        "git_mode": mode,
    }


def _live_remote_main_head(repo_root: Path) -> str:
    raw = cast(
        str,
        _git(
            repo_root,
            "ls-remote",
            "--exit-code",
            "origin",
            "refs/heads/main",
        ),
    )
    lines = [line for line in raw.splitlines() if line]
    if len(lines) != 1:
        raise FinalCalibrationError("E0-MCAL live remote main is ambiguous")
    fields = lines[0].split("\t")
    if len(fields) != 2 or fields[1] != "refs/heads/main" or SHA1_RE.fullmatch(fields[0]) is None:
        raise FinalCalibrationError("E0-MCAL live remote main response drifted")
    return fields[0]


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _construct_unique_json_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, nested in pairs:
        if key in value:
            raise FinalCalibrationError(f"E0-MCAL JSON duplicate key: {key}")
        value[key] = nested
    return value


def _parse_json_bytes(payload: bytes, *, context: str) -> Any:
    try:
        return json.loads(payload, object_pairs_hook=_construct_unique_json_object)
    except FinalCalibrationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FinalCalibrationError(f"E0-MCAL JSON is malformed: {context}") from exc


def _load_json_object(path: Path, *, repo_root: Path) -> dict[str, Any]:
    payload = _read_regular_bytes(path, repo_root=repo_root)
    value = _parse_json_bytes(payload, context=path.as_posix())
    if not isinstance(value, dict):
        raise FinalCalibrationError(f"E0-MCAL JSON must be an object: {path.as_posix()}")
    return value


def _load_yaml_object(path: Path, *, repo_root: Path) -> dict[str, Any]:
    payload = _read_regular_bytes(path, repo_root=repo_root)
    try:
        value = yaml.load(payload, Loader=_UniqueKeyLoader)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise FinalCalibrationError(
            f"E0-MCAL YAML is malformed: {path.as_posix()}"
        ) from exc
    if not isinstance(value, dict):
        raise FinalCalibrationError(f"E0-MCAL YAML must be an object: {path.as_posix()}")
    return cast(dict[str, Any], value)


def _dvc_pointer_output(
    pointer_path: Path, *, repo_root: Path
) -> tuple[Path, bool]:
    payload, _ = _read_regular_bytes_and_metadata(
        pointer_path, repo_root=repo_root
    )
    try:
        value = yaml.load(payload, Loader=_UniqueKeyLoader)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise FinalCalibrationError(
            f"E0-MCAL DVC pointer is malformed: {pointer_path.as_posix()}"
        ) from exc
    if not isinstance(value, Mapping) or set(value) != {"outs"}:
        raise FinalCalibrationError(
            f"E0-MCAL DVC pointer dialect drifted: {pointer_path.as_posix()}"
        )
    outputs = value.get("outs")
    if not isinstance(outputs, list) or len(outputs) != 1:
        raise FinalCalibrationError(
            f"E0-MCAL DVC pointer output drifted: {pointer_path.as_posix()}"
        )
    output = outputs[0]
    if not isinstance(output, Mapping):
        raise FinalCalibrationError(
            f"E0-MCAL DVC pointer output is malformed: {pointer_path.as_posix()}"
        )
    md5 = output.get("md5")
    output_path = output.get("path")
    byte_count = output.get("size")
    directory = isinstance(md5, str) and md5.endswith(".dir")
    expected_keys = {"md5", "size", "hash", "path"}
    if directory:
        expected_keys.add("nfiles")
    if (
        set(output) != expected_keys
        or not isinstance(md5, str)
        or re.fullmatch(r"[0-9a-f]{32}(?:\.dir)?", md5) is None
        or output.get("hash") != "md5"
        or type(byte_count) is not int
        or int(byte_count) <= 0
        or not isinstance(output_path, str)
        or not output_path
        or Path(output_path).is_absolute()
        or any(part in {"", ".", ".."} for part in Path(output_path).parts)
        or (
            directory
            and (
                type(output.get("nfiles")) is not int
                or int(cast(int, output["nfiles"])) <= 0
            )
        )
    ):
        raise FinalCalibrationError(
            f"E0-MCAL DVC pointer output dialect drifted: {pointer_path.as_posix()}"
        )
    return pointer_path.parent / Path(output_path), directory


def _authorized_dvc_pointer_for_payload(
    path: Path,
    *,
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> Path:
    matches: list[Path] = []
    for pointer_path in authorized_dvc_pointers:
        output_path, directory = _dvc_pointer_output(
            pointer_path, repo_root=repo_root
        )
        if directory:
            try:
                relative = path.relative_to(output_path)
            except ValueError:
                continue
            if not relative.parts:
                continue
            matches.append(pointer_path)
        elif path == output_path:
            matches.append(pointer_path)
    if len(matches) != 1:
        raise FinalCalibrationError(
            "E0-MCAL DVC hardlink payload lacks one exact authorized pointer: "
            f"{path.as_posix()}"
        )
    return matches[0]


def _read_scientific_payload_bytes_and_metadata(
    path: Path,
    *,
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> tuple[bytes, os.stat_result]:
    try:
        return _read_regular_bytes_and_metadata(path, repo_root=repo_root)
    except FinalCalibrationError as regular_error:
        try:
            payload, metadata = _read_regular_bytes_and_metadata(
                path,
                repo_root=repo_root,
                expected_mode=0o444,
                require_nlink_one=False,
            )
        except FinalCalibrationError as dvc_error:
            raise FinalCalibrationError(
                "E0-MCAL scientific payload is neither portable regular nor "
                f"verified DVC-cache materialization: {path.as_posix()}"
            ) from dvc_error
        if metadata.st_nlink != 2:
            raise FinalCalibrationError(
                "E0-MCAL DVC-cache payload must have exactly two names: "
                f"{path.as_posix()}"
            ) from regular_error
        pointer_path = _authorized_dvc_pointer_for_payload(
            path,
            authorized_dvc_pointers=authorized_dvc_pointers,
            repo_root=repo_root,
        )
        payload_md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
        cache_path = Path(".dvc/cache/files/md5") / payload_md5[:2] / payload_md5[2:]
        cache_payload, cache_metadata = _read_regular_bytes_and_metadata(
            cache_path,
            repo_root=repo_root,
            expected_mode=0o444,
            require_nlink_one=False,
        )
        if (
            cache_metadata.st_nlink != 2
            or (metadata.st_dev, metadata.st_ino)
            != (cache_metadata.st_dev, cache_metadata.st_ino)
            or payload != cache_payload
        ):
            raise FinalCalibrationError(
                "E0-MCAL DVC-cache hardlink identity drifted for "
                f"{path.as_posix()} via {pointer_path.as_posix()}"
            )
        reread, reread_metadata = _read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=0o444,
            require_nlink_one=False,
        )
        cache_reread, cache_reread_metadata = _read_regular_bytes_and_metadata(
            cache_path,
            repo_root=repo_root,
            expected_mode=0o444,
            require_nlink_one=False,
        )
        if (
            reread_metadata.st_nlink != 2
            or reread != payload
            or cache_reread_metadata.st_nlink != 2
            or cache_reread != payload
            or (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_mode,
                metadata.st_nlink,
                metadata.st_size,
                metadata.st_mtime_ns,
                metadata.st_ctime_ns,
            )
            != (
                reread_metadata.st_dev,
                reread_metadata.st_ino,
                reread_metadata.st_mode,
                reread_metadata.st_nlink,
                reread_metadata.st_size,
                reread_metadata.st_mtime_ns,
                reread_metadata.st_ctime_ns,
            )
            or (
                cache_metadata.st_dev,
                cache_metadata.st_ino,
                cache_metadata.st_mode,
                cache_metadata.st_nlink,
                cache_metadata.st_size,
                cache_metadata.st_mtime_ns,
                cache_metadata.st_ctime_ns,
            )
            != (
                cache_reread_metadata.st_dev,
                cache_reread_metadata.st_ino,
                cache_reread_metadata.st_mode,
                cache_reread_metadata.st_nlink,
                cache_reread_metadata.st_size,
                cache_reread_metadata.st_mtime_ns,
                cache_reread_metadata.st_ctime_ns,
            )
        ):
            raise FinalCalibrationError(
                f"E0-MCAL DVC-cache payload changed during validation: {path.as_posix()}"
            )
        return payload, metadata


def _scientific_dvc_pointer_paths(
    authority_records: Sequence[Mapping[str, Any]],
    payload_records: Sequence[Mapping[str, Any]],
) -> tuple[Path, ...]:
    paths: set[Path] = set()
    for record in (*authority_records, *payload_records):
        value = record.get("path")
        if isinstance(value, str) and value.endswith(".dvc"):
            paths.add(Path(value))
    if not paths:
        raise FinalCalibrationError("E0-MCAL scientific DVC pointer set is empty")
    return tuple(sorted(paths, key=lambda value: value.as_posix()))


def _scientific_authority_path_roles() -> tuple[tuple[str, Path], ...]:
    records: list[tuple[str, Path]] = [
        ("targets_pointer", Path("data/targets.dvc")),
        (
            "protocol_lock",
            Path("reports/closure_v1/00_protocol/protocol_lock.json"),
        ),
        (
            "common_origin_pointer",
            Path("data/closure_v1/common_origin_manifest.parquet.dvc"),
        ),
        (
            "common_origin_manifest",
            Path("reports/closure_v1/01_surface/common_origin_manifest.json"),
        ),
        (
            "baseline_manifest",
            Path("reports/closure_v1/02_models/baselines/manifest.json"),
        ),
        (
            "b0_raw_scores_pointer",
            Path("data/closure_v1/development/baselines/B0/raw_scores.parquet.dvc"),
        ),
        (
            "b1_raw_scores_pointer",
            Path("data/closure_v1/development/baselines/B1/raw_scores.parquet.dvc"),
        ),
        (
            "b2_raw_scores_pointer",
            Path("data/closure_v1/development/baselines/B2/raw_scores.parquet.dvc"),
        ),
        ("m0_manifest", Path("reports/closure_v1/02_models/M0/manifest.json")),
        (
            "m0_raw_scores_pointer",
            Path("data/closure_v1/development/mifal/M0/raw_scores.parquet.dvc"),
        ),
        ("models_dvc", Path("models.dvc")),
        (
            "a0_sequence_pointer",
            Path("data/closure_v1/development/sequences/A0/raw_no_current.parquet.dvc"),
        ),
        (
            "a0_sequence_manifest",
            Path(
                "reports/closure_v1/01_surface/sequences/A0/raw_no_current_manifest.json"
            ),
        ),
    ]
    for seed in REGISTERED_SEEDS:
        records.extend(
            [
                (
                    "a1_sequence_pointer",
                    Path(
                        f"data/closure_v1/development/sequences/A1/seed_{seed}.parquet.dvc"
                    ),
                ),
                (
                    "a1_sequence_manifest",
                    Path(
                        f"reports/closure_v1/01_surface/sequences/A1/seed_{seed}_manifest.json"
                    ),
                ),
            ]
        )
    for model_id in ("P0", "P1"):
        for seed in REGISTERED_SEEDS:
            records.append(
                (
                    f"{model_id.lower()}_unavailable_manifest_{seed}",
                    Path(
                        f"reports/closure_v1/02_models/{model_id}/seed_{seed}_manifest.json"
                    ),
                )
            )
    for seed in REGISTERED_SEEDS:
        for model_id in ("A0", "A1"):
            token = model_id.lower()
            records.extend(
                [
                    (
                        f"{token}_manifest_seed_{seed}",
                        Path(
                            f"reports/closure_v1/02_models/{model_id}/seed_{seed}_manifest.json"
                        ),
                    ),
                    (
                        f"{token}_selection_predictions_pointer_seed_{seed}",
                        Path(
                            "data/closure_v1/development/anfis_ablation/"
                            f"{model_id}/seed_{seed}_selection_predictions.parquet.dvc"
                        ),
                    ),
                ]
            )
    records.extend(
        [
            ("fuzzy_dvc", Path("data/fuzzy.dvc")),
            (
                "expert_state_manifest",
                Path(
                    "reports/closure_v1/01_surface/expert/"
                    "expert_no_current_state_manifest.json"
                ),
            ),
            (
                "development_runtime_schema",
                Path("configs/closure_v1/development_runtime.schema.json"),
            ),
        ]
    )
    for seed in REGISTERED_SEEDS:
        records.extend(
            [
                (
                    f"f1_state_pointer_{seed}",
                    Path(
                        "data/closure_v1/development/anfis/"
                        f"seed_{seed}/adaptive_no_current_state.parquet.dvc"
                    ),
                ),
                (
                    f"f1_state_manifest_{seed}",
                    Path(
                        f"reports/closure_v1/01_surface/anfis/seed_{seed}/manifest.json"
                    ),
                ),
            ]
        )
    if len(records) != SCIENTIFIC_AUTHORITY_RECORD_COUNT or len(
        {path for _, path in records}
    ) != SCIENTIFIC_AUTHORITY_RECORD_COUNT:
        raise FinalCalibrationError("E0-MCAL scientific authority path set drifted")
    return tuple(records)


def _binding_record(
    value: Any, *, role: str, path: str, binding_source: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("path") != path:
        raise FinalCalibrationError(
            f"E0-MCAL scientific binding path drifted: {path}"
        )
    byte_count = value.get("bytes")
    sha256 = value.get("sha256")
    if (
        type(byte_count) is not int
        or int(byte_count) <= 0
        or not isinstance(sha256, str)
        or SHA256_RE.fullmatch(sha256) is None
    ):
        raise FinalCalibrationError(
            f"E0-MCAL scientific binding record drifted: {path}"
        )
    return {
        "role": role,
        "path": path,
        "bytes": byte_count,
        "sha256": sha256,
        "binding_source": binding_source,
    }


def _direct_manifest_binding(
    records: Any, *, role: str, path: str, binding_source: str
) -> dict[str, Any]:
    if not isinstance(records, list):
        raise FinalCalibrationError(
            f"E0-MCAL manifest records are absent: {binding_source}"
        )
    matches = [record for record in records if isinstance(record, Mapping) and record.get("path") == path]
    if len(matches) != 1:
        raise FinalCalibrationError(
            f"E0-MCAL manifest binding is not unique: {path}"
        )
    return _binding_record(
        matches[0], role=role, path=path, binding_source=binding_source
    )


def _recursive_manifest_binding(
    value: Any, *, role: str, path: str, binding_source: str
) -> dict[str, Any]:
    matches: list[Mapping[str, Any]] = []

    def visit(candidate: Any) -> None:
        if isinstance(candidate, Mapping):
            if candidate.get("path") == path:
                matches.append(candidate)
            for nested in candidate.values():
                visit(nested)
        elif isinstance(candidate, list):
            for nested in candidate:
                visit(nested)

    visit(value)
    canonical = {
        _canonical_json_bytes(
            {key: record.get(key) for key in ("path", "bytes", "sha256")}
        ): record
        for record in matches
    }
    if len(canonical) != 1:
        raise FinalCalibrationError(
            f"E0-MCAL recursive scientific binding is not unique: {path}"
        )
    return _binding_record(
        next(iter(canonical.values())),
        role=role,
        path=path,
        binding_source=binding_source,
    )


def _unavailable_consumer_namespace(model_id: str, seed: int) -> tuple[Path, ...]:
    if model_id not in {"P0", "P1"} or seed not in REGISTERED_SEEDS:
        raise FinalCalibrationError("E0-MCAL unavailable slot identity drifted")
    report_root = Path(f"reports/closure_v1/02_models/{model_id}")
    model_root = Path(f"models/closure_v1/pipe/{model_id}")
    finals = (
        model_root / f"seed_{seed}.pt",
        model_root / f"seed_{seed}.checkpoint.pt",
        report_root / f"seed_{seed}_preprocessor.json",
        report_root / f"seed_{seed}_metrics.csv",
        report_root / f"seed_{seed}_training_curve.csv",
        report_root / f"seed_{seed}_blend_weights.csv",
        report_root / f"seed_{seed}_blend_search.csv",
        report_root / f"seed_{seed}_report.md",
        report_root / f"seed_{seed}_manifest.json",
    )
    temporaries = tuple(
        path.with_suffix(path.suffix + ".tmp") for path in finals
    )
    guard = Path(f"tmp/closure_v1_temporal_consumer/{model_id}_seed_{seed}.guard")
    namespace = (*finals, *temporaries, guard)
    if len(namespace) != 19 or len(set(namespace)) != 19:
        raise FinalCalibrationError("E0-MCAL unavailable namespace drifted")
    return namespace


def _scientific_input_inventory(*, repo_root: Path) -> dict[str, Any]:
    authority_records = [
        _git_artifact_record(
            path,
            role=role,
            repo_root=repo_root,
            commit=BASE_COMMIT,
        )
        for role, path in _scientific_authority_path_roles()
    ]
    baseline_path = Path("reports/closure_v1/02_models/baselines/manifest.json")
    m0_path = Path("reports/closure_v1/02_models/M0/manifest.json")
    expert_path = Path(
        "reports/closure_v1/01_surface/expert/expert_no_current_state_manifest.json"
    )
    protocol_path = Path("reports/closure_v1/00_protocol/protocol_lock.json")
    target_manifest_path = Path("data/targets/target_manifest_v0.json")
    development_lock_path = Path(
        "reports/closure_v1/00_protocol/development_runtime_lock.json"
    )
    baseline = _load_json_object(baseline_path, repo_root=repo_root)
    m0 = _load_json_object(m0_path, repo_root=repo_root)
    expert = _load_json_object(expert_path, repo_root=repo_root)
    protocol = _load_json_object(protocol_path, repo_root=repo_root)
    development_lock = _load_json_object(development_lock_path, repo_root=repo_root)
    payload_records: list[dict[str, Any]] = []

    def direct(
        records: Any, *, role: str, path: str, source: Path
    ) -> None:
        payload_records.append(
            _direct_manifest_binding(
                records,
                role=role,
                path=path,
                binding_source=source.as_posix(),
            )
        )

    direct(
        baseline.get("inputs"),
        role="common_origin",
        path="data/closure_v1/common_origin_manifest.parquet",
        source=baseline_path,
    )
    target_binding = _direct_manifest_binding(
        protocol.get("source_artifacts"),
        role="development_targets",
        path="data/targets/monthly_targets_model_v0.parquet",
        binding_source=protocol_path.as_posix(),
    )
    baseline_target_binding = _direct_manifest_binding(
        baseline.get("inputs"),
        role="development_targets",
        path="data/targets/monthly_targets_model_v0.parquet",
        binding_source=baseline_path.as_posix(),
    )
    if {
        key: target_binding[key] for key in ("path", "bytes", "sha256")
    } != {
        key: baseline_target_binding[key] for key in ("path", "bytes", "sha256")
    }:
        raise FinalCalibrationError("E0-MCAL target authorities disagree")
    payload_records.append(target_binding)
    target_manifest_binding = _direct_manifest_binding(
        protocol.get("source_artifacts"),
        role="target_manifest",
        path=target_manifest_path.as_posix(),
        binding_source=protocol_path.as_posix(),
    )
    target_manifest_payload, _ = _read_scientific_payload_bytes_and_metadata(
        target_manifest_path,
        authorized_dvc_pointers=(Path("data/targets.dvc"),),
        repo_root=repo_root,
    )
    if (
        len(target_manifest_payload) != target_manifest_binding["bytes"]
        or _sha256_bytes(target_manifest_payload) != target_manifest_binding["sha256"]
    ):
        raise FinalCalibrationError(
            "E0-MCAL ignored target manifest differs from its protocol authority"
        )
    payload_records.append(target_manifest_binding)
    for model_id in ("B0", "B1", "B2"):
        direct(
            baseline.get("outputs"),
            role=f"{model_id.lower()}_raw_scores",
            path=f"data/closure_v1/development/baselines/{model_id}/raw_scores.parquet",
            source=baseline_path,
        )
    direct(
        baseline.get("outputs"),
        role="baseline_lineage",
        path="reports/closure_v1/02_models/baselines/lineage_audit.json",
        source=baseline_path,
    )
    direct(
        m0.get("outputs"),
        role="m0_raw_scores",
        path="data/closure_v1/development/mifal/M0/raw_scores.parquet",
        source=m0_path,
    )
    direct(
        m0.get("outputs"),
        role="m0_lineage",
        path="reports/closure_v1/02_models/M0/lineage_audit.json",
        source=m0_path,
    )
    sequence_specs = [
        (
            "a0_sequence",
            Path(
                "reports/closure_v1/01_surface/sequences/A0/"
                "raw_no_current_manifest.json"
            ),
            "data/closure_v1/development/sequences/A0/raw_no_current.parquet",
        )
    ]
    sequence_specs.extend(
        (
            "a1_sequence",
            Path(
                f"reports/closure_v1/01_surface/sequences/A1/seed_{seed}_manifest.json"
            ),
            f"data/closure_v1/development/sequences/A1/seed_{seed}.parquet",
        )
        for seed in REGISTERED_SEEDS
    )
    for role, manifest_path, payload_path in sequence_specs:
        manifest = _load_json_object(manifest_path, repo_root=repo_root)
        direct(
            manifest.get("outputs"),
            role=role,
            path=payload_path,
            source=manifest_path,
        )
    for seed in REGISTERED_SEEDS:
        for model_id in ("A0", "A1"):
            manifest_path = Path(
                f"reports/closure_v1/02_models/{model_id}/seed_{seed}_manifest.json"
            )
            manifest = _load_json_object(manifest_path, repo_root=repo_root)
            outputs = manifest.get("outputs")
            for output_role in (
                "model",
                "checkpoint",
                "preprocessor",
                "selection_predictions",
            ):
                if not isinstance(outputs, list):
                    raise FinalCalibrationError(
                        f"E0-MCAL slot outputs are absent: {manifest_path.as_posix()}"
                    )
                matches = [
                    record
                    for record in outputs
                    if isinstance(record, Mapping)
                    and record.get("role") == output_role
                ]
                if len(matches) != 1 or not isinstance(matches[0].get("path"), str):
                    raise FinalCalibrationError(
                        "E0-MCAL slot scientific role is not unique: "
                        f"{manifest_path.as_posix()}:{output_role}"
                    )
                output_path = cast(str, matches[0]["path"])
                payload_records.append(
                    _binding_record(
                        matches[0],
                        role=(
                            f"{model_id.lower()}_{output_role}_seed_{seed}"
                            if output_role != "selection_predictions"
                            else f"{model_id.lower()}_selection_predictions"
                        ),
                        path=output_path,
                        binding_source=manifest_path.as_posix(),
                    )
                )
    for role, path in (
        ("panel", "data/panel/panel_monthly_v0.parquet"),
        ("panel_pointer", "data/panel/panel_monthly_v0.parquet.dvc"),
        ("holdout_assignment", "data/closure_v1/closure_holdout_assignment.csv"),
        ("holdout_manifest", "reports/closure_v1/00_protocol/holdout_manifest.json"),
        ("protocol_lock", "reports/closure_v1/00_protocol/protocol_lock.json"),
        ("analysis_plan", "configs/closure_v1/analysis_plan.yaml"),
        (
            "development_runtime_lock",
            "reports/closure_v1/00_protocol/development_runtime_lock.json",
        ),
    ):
        direct(baseline.get("inputs"), role=role, path=path, source=baseline_path)
    direct(
        expert.get("dependencies"),
        role="fuzzy_state_vector",
        path="data/fuzzy/state_vector_v0.parquet",
        source=expert_path,
    )
    payload_records.append(
        _recursive_manifest_binding(
            development_lock,
            role="development_runtime_lock_schema",
            path="configs/closure_v1/development_runtime_lock.schema.json",
            binding_source=development_lock_path.as_posix(),
        )
    )
    for seed in REGISTERED_SEEDS:
        manifest_path = Path(
            f"reports/closure_v1/01_surface/anfis/seed_{seed}/manifest.json"
        )
        manifest = _load_json_object(manifest_path, repo_root=repo_root)
        direct(
            manifest.get("outputs"),
            role=f"f1_state_{seed}",
            path=(
                "data/closure_v1/development/anfis/"
                f"seed_{seed}/adaptive_no_current_state.parquet"
            ),
            source=manifest_path,
        )
        for module_id in ("ANFIS-N", "ANFIS-F", "ANFIS-T-no-current"):
            outputs = manifest.get("outputs")
            if not isinstance(outputs, list):
                raise FinalCalibrationError(
                    f"E0-MCAL F1 outputs are absent: {manifest_path.as_posix()}"
                )
            matches = [
                record
                for record in outputs
                if isinstance(record, Mapping)
                and record.get("role") == "anfis_checkpoint"
                and record.get("module") == module_id
            ]
            if len(matches) != 1 or not isinstance(matches[0].get("path"), str):
                raise FinalCalibrationError(
                    "E0-MCAL F1 checkpoint binding is not unique: "
                    f"{seed}:{module_id}"
                )
            payload_records.append(
                _binding_record(
                    matches[0],
                    role=f"f1_checkpoint_{seed}_{module_id}",
                    path=cast(str, matches[0]["path"]),
                    binding_source=manifest_path.as_posix(),
                )
            )
    unavailable_manifest_records: list[dict[str, Any]] = []
    unavailable_namespace_paths: list[Path] = []
    unavailable_present_paths: list[Path] = []
    unavailable_absent_paths: list[Path] = []
    for model_id in ("P0", "P1"):
        for seed in REGISTERED_SEEDS:
            manifest_path = Path(
                f"reports/closure_v1/02_models/{model_id}/seed_{seed}_manifest.json"
            )
            manifest = _load_json_object(manifest_path, repo_root=repo_root)
            if (
                manifest.get("status") != "completed"
                or manifest.get("slot_status") != "model_unavailable"
                or manifest.get("fit_status") != "not_attempted"
                or manifest.get("failure_reason") != "sequence_fit_rows_unavailable"
                or manifest.get("model_artifact_emitted") is not False
                or manifest.get("model_id") != model_id
                or manifest.get("base_seed") != seed
            ):
                raise FinalCalibrationError(
                    "E0-MCAL unavailable temporal manifest drifted: "
                    f"{manifest_path.as_posix()}"
                )
            report_path = (
                f"reports/closure_v1/02_models/{model_id}/seed_{seed}_report.md"
            )
            report_record = _direct_manifest_binding(
                manifest.get("outputs"),
                role=f"{model_id.lower()}_unavailable_report_{seed}",
                path=report_path,
                binding_source=manifest_path.as_posix(),
            )
            payload_records.append(report_record)
            unavailable_manifest_records.append(
                {
                    "model_id": model_id,
                    "base_seed": seed,
                    "manifest_path": manifest_path.as_posix(),
                    "report_path": report_path,
                    "slot_status": "model_unavailable",
                    "fit_status": "not_attempted",
                    "failure_reason": "sequence_fit_rows_unavailable",
                    "model_artifact_emitted": False,
                }
            )
            namespace = _unavailable_consumer_namespace(model_id, seed)
            expected_present = {Path(report_path), manifest_path}
            unavailable_namespace_paths.extend(namespace)
            for path in namespace:
                if path in expected_present:
                    unavailable_present_paths.append(path)
                    if not _entry_exists(path, repo_root=repo_root):
                        raise FinalCalibrationError(
                            "E0-MCAL terminal unavailable record disappeared: "
                            f"{path.as_posix()}"
                        )
                else:
                    unavailable_absent_paths.append(path)
                    if _entry_exists(path, repo_root=repo_root):
                        raise FinalCalibrationError(
                            "E0-MCAL unavailable consumer namespace is occupied: "
                            f"{path.as_posix()}"
                        )
    if (
        len(unavailable_namespace_paths) != 190
        or len(set(unavailable_namespace_paths)) != 190
        or len(unavailable_present_paths) != 20
        or len(unavailable_absent_paths) != 170
    ):
        raise FinalCalibrationError(
            "E0-MCAL unavailable P0/P1 namespace cardinality drifted"
        )
    a2_namespace_paths = [
        Path("data/closure_v1/development/sequences/A2"),
        Path("data/closure_v1/development/anfis_ablation/A2"),
        Path("models/closure_v1/pipe/A2"),
        Path("models/closure_v1/anfis_ablation/A2"),
        Path("reports/closure_v1/01_surface/sequences/A2"),
        Path("reports/closure_v1/02_models/A2"),
    ]
    occupied_a2 = [
        path.as_posix()
        for path in a2_namespace_paths
        if _entry_exists(path, repo_root=repo_root)
    ]
    if occupied_a2:
        raise FinalCalibrationError(
            f"E0-MCAL A2 unavailable namespace drifted: {occupied_a2}"
        )
    for earlier, later in zip(
        P0_P1_PUBLICATION_COMMITS, P0_P1_PUBLICATION_COMMITS[1:]
    ):
        _git(repo_root, "merge-base", "--is-ancestor", earlier, later)
    if len(payload_records) != SCIENTIFIC_PAYLOAD_BINDING_COUNT or len(
        {cast(str, record["path"]) for record in payload_records}
    ) != SCIENTIFIC_PAYLOAD_BINDING_COUNT:
        raise FinalCalibrationError("E0-MCAL scientific payload set drifted")

    authorized_dvc_pointers = _scientific_dvc_pointer_paths(
        authority_records, payload_records
    )
    payload_physical_records: list[dict[str, Any]] = []
    for record in payload_records:
        path = Path(cast(str, record["path"]))
        payload, _ = _read_scientific_payload_bytes_and_metadata(
            path,
            authorized_dvc_pointers=authorized_dvc_pointers,
            repo_root=repo_root,
        )
        if (
            len(payload) != record["bytes"]
            or _sha256_bytes(payload) != record["sha256"]
        ):
            raise FinalCalibrationError(
                "E0-MCAL physical scientific payload differs from its authority: "
                f"{path.as_posix()}"
            )
        payload_physical_records.append(
            {
                "role": record["role"],
                "path": record["path"],
                "bytes": record["bytes"],
                "sha256": record["sha256"],
            }
        )

    def portable(record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: record[key] for key in ("role", "path", "bytes", "sha256")
        }

    evidence_root_roles = {
        "protocol_lock",
        "fuzzy_dvc",
        "expert_state_manifest",
        "development_runtime_schema",
        *(f"{model_id}_unavailable_manifest_{seed}" for model_id in ("p0", "p1") for seed in REGISTERED_SEEDS),
        *(f"f1_state_pointer_{seed}" for seed in REGISTERED_SEEDS),
        *(f"f1_state_manifest_{seed}" for seed in REGISTERED_SEEDS),
    }
    calibration_roots = [
        portable(record)
        for record in authority_records
        if record["role"] not in evidence_root_roles
    ]
    e7_payload_roles = {
        "panel",
        "panel_pointer",
        "holdout_assignment",
        "holdout_manifest",
        "protocol_lock",
        "analysis_plan",
        "development_runtime_lock",
        "fuzzy_state_vector",
        "development_runtime_lock_schema",
    }
    noncalibration_payload_roles = {
        *e7_payload_roles,
        *(f"f1_state_{seed}" for seed in REGISTERED_SEEDS),
        *(f"f1_checkpoint_{seed}_{module_id}" for seed in REGISTERED_SEEDS for module_id in ("ANFIS-N", "ANFIS-F", "ANFIS-T-no-current")),
        *(f"{model_id}_unavailable_report_{seed}" for model_id in ("p0", "p1") for seed in REGISTERED_SEEDS),
    }
    calibration_payloads = [
        portable(record)
        for record in payload_records
        if record["role"] not in noncalibration_payload_roles
    ]
    calibration_required_inputs = sorted(
        [*calibration_roots, *calibration_payloads],
        key=lambda record: cast(str, record["path"]),
    )
    e7_roots = [
        portable(record)
        for record in authority_records
        if record["role"]
        in {"fuzzy_dvc", "expert_state_manifest", "development_runtime_schema"}
    ]
    e7_payloads = [
        portable(record)
        for record in payload_records
        if record["role"] in e7_payload_roles
    ]
    e7_blockers = [
        {
            "role": "historical_e7_blocker",
            "path": record["path"],
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }
        for record in _historical_e7_blockers(repo_root=repo_root)
    ]
    e7_required_inputs = sorted(
        [*e7_blockers, *e7_roots, *e7_payloads],
        key=lambda record: cast(str, record["path"]),
    )
    if (
        len(calibration_required_inputs) != CALIBRATION_REQUIRED_INPUT_COUNT
        or len({record["path"] for record in calibration_required_inputs})
        != CALIBRATION_REQUIRED_INPUT_COUNT
        or len(e7_required_inputs) != E7_REQUIRED_INPUT_COUNT
        or len({record["path"] for record in e7_required_inputs})
        != E7_REQUIRED_INPUT_COUNT
    ):
        raise FinalCalibrationError("E0-MCAL runner input partition drifted")
    return {
        "schema_version": "closure_final_calibration_scientific_input_inventory_v1",
        "authority_record_count": SCIENTIFIC_AUTHORITY_RECORD_COUNT,
        "payload_binding_count": SCIENTIFIC_PAYLOAD_BINDING_COUNT,
        "calibration_payload_binding_count": CALIBRATION_PAYLOAD_BINDING_COUNT,
        "calibration_lineage_binding_count": CALIBRATION_LINEAGE_BINDING_COUNT,
        "f1_availability_binding_count": F1_AVAILABILITY_BINDING_COUNT,
        "e7_runtime_binding_count": E7_RUNTIME_BINDING_COUNT,
        "unavailable_temporal_report_binding_count": UNAVAILABLE_TEMPORAL_REPORT_BINDING_COUNT,
        "authority_records": authority_records,
        "payload_bindings": payload_records,
        "authority_records_sha256": _digest_records(authority_records),
        "payload_bindings_sha256": _digest_records(payload_records),
        "payload_physical_validation_count": len(payload_physical_records),
        "payload_physical_records_sha256": _digest_records(
            payload_physical_records
        ),
        "payload_physical_validation_complete": True,
        "payload_materialization_policy": (
            "regular_0644_nlink1_or_verified_dvc_cache_hardlink_0444_nlink2"
        ),
        "dvc_cache_hardlink_second_name_required": True,
        "dvc_cache_hardlink_third_name_allowed": False,
        "payload_materialization_class_counts_serialized": False,
        "calibration_required_input_count": CALIBRATION_REQUIRED_INPUT_COUNT,
        "e7_required_input_count": E7_REQUIRED_INPUT_COUNT,
        "calibration_required_inputs": calibration_required_inputs,
        "e7_required_inputs": e7_required_inputs,
        "calibration_required_inputs_sha256": _digest_records(
            calibration_required_inputs
        ),
        "e7_required_inputs_sha256": _digest_records(e7_required_inputs),
        "payload_bytes_same_fd_required": True,
        "git_dvc_manifest_chain_verified": True,
        "runtime_input_selection_allowed": False,
        "holdout_or_post_2021_access_authorized": False,
        "unavailable_model_evidence": {
            "p0_p1_manifest_count": 10,
            "p0_p1_report_binding_count": 10,
            "p0_p1_publication_commits": list(P0_P1_PUBLICATION_COMMITS),
            "p0_p1_publication_history_linear": True,
            "p0_p1_records": unavailable_manifest_records,
            "p0_p1_namespace_path_count": len(unavailable_namespace_paths),
            "p0_p1_namespace_present_path_count": len(unavailable_present_paths),
            "p0_p1_namespace_absent_path_count": len(unavailable_absent_paths),
            "p0_p1_namespace_absent_paths": sorted(
                path.as_posix() for path in unavailable_absent_paths
            ),
            "p0_p1_namespace_absent_paths_sha256": _sha256_bytes(
                _canonical_json_bytes(
                    sorted(path.as_posix() for path in unavailable_absent_paths)
                )
            ),
            "p0_p1_namespace_exact": True,
            "a2_namespace_paths": [path.as_posix() for path in a2_namespace_paths],
            "a2_namespace_present_count": 0,
            "a2_substitute_allowed": False,
        },
    }


def _expected_model_records() -> list[dict[str, Any]]:
    five_seeds = list(REGISTERED_SEEDS)
    horizons = list(HORIZONS_MONTHS)
    return [
        {
            "model_id": "B0",
            "availability": "available",
            "availability_reason": "published_deterministic_baseline",
            "seed_policy": "deterministic_technical_seed",
            "calibration_seed_source": "technical_seed",
            "selected_family": False,
            "seeds": [1729],
            "horizons_months": horizons,
            "bloom_score_source": "predicted_bloom_probability",
            "bloom_calibration": "fixed_identity_no_refit",
            "ordinal_calibration": "record_not_available_degenerate_constant_score",
            "uncertainty_calibration": "not_applicable",
        },
        *[
            {
                "model_id": model_id,
                "availability": "available",
                "availability_reason": "published_seeded_baseline_family",
                "seed_policy": "exact_five_prespecified_seeds",
                "calibration_seed_source": (
                    "upstream_state_seed" if model_id == "B1" else "model_seed"
                ),
                "selected_family": model_id == "B2",
                "seeds": five_seeds,
                "horizons_months": horizons,
                "bloom_score_source": "predicted_bloom_probability",
                "bloom_calibration": "select_then_refit",
                "ordinal_calibration": "select_cutpoints",
                "uncertainty_calibration": "not_applicable",
            }
            for model_id in ("B1", "B2")
        ],
        *[
            {
                "model_id": model_id,
                "availability": "available",
                "availability_reason": (
                    "published_static_fuzzy_state"
                    if model_id == "F0"
                    else "published_exact_five_seed_adaptive_state_family"
                ),
                "seed_policy": (
                    "deterministic_technical_seed"
                    if model_id == "F0"
                    else "exact_five_prespecified_seeds"
                ),
                "calibration_seed_source": "not_applicable",
                "selected_family": False,
                "seeds": [1729] if model_id == "F0" else five_seeds,
                "horizons_months": horizons,
                "bloom_score_source": "not_applicable",
                "bloom_calibration": "not_applicable",
                "ordinal_calibration": "not_applicable",
                "uncertainty_calibration": "not_applicable",
            }
            for model_id in ("F0", "F1")
        ],
        *[
            {
                "model_id": model_id,
                "availability": "unavailable",
                "availability_reason": "exact_five_slots_model_unavailable_not_attempted",
                "seed_policy": "exact_five_prespecified_seeds",
                "calibration_seed_source": "not_applicable",
                "selected_family": False,
                "seeds": five_seeds,
                "horizons_months": horizons,
                "bloom_score_source": "not_attempted_upstream_model_unavailable",
                "bloom_calibration": "not_attempted_upstream_model_unavailable",
                "ordinal_calibration": "not_attempted_upstream_model_unavailable",
                "uncertainty_calibration": "not_attempted_upstream_model_unavailable",
            }
            for model_id in ("P0", "P1")
        ],
        {
            "model_id": "M0",
            "availability": "available",
            "availability_reason": "published_raw_uncalibrated_mifal_score",
            "seed_policy": "deterministic_technical_seed",
            "calibration_seed_source": "technical_seed",
            "selected_family": False,
            "seeds": [1729],
            "horizons_months": horizons,
            "bloom_score_source": "raw_score",
            "bloom_calibration": "select_then_refit",
            "ordinal_calibration": "not_applicable",
            "uncertainty_calibration": "not_applicable",
        },
        *[
            {
                "model_id": model_id,
                "availability": "available",
                "availability_reason": "registered_exact_five_seed_anfis_family",
                "seed_policy": "exact_five_prespecified_seeds",
                "calibration_seed_source": "base_seed",
                "selected_family": False,
                "seeds": five_seeds,
                "horizons_months": horizons,
                "bloom_score_source": "predicted_bloom_probability",
                "bloom_calibration": "select_then_refit",
                "ordinal_calibration": "not_applicable",
                "uncertainty_calibration": "symmetric_scaled_sigma_split_conformal",
            }
            for model_id in ("A0", "A1")
        ],
        {
            "model_id": "A2",
            "availability": "unavailable",
            "availability_reason": "model_absent_no_substitute",
            "seed_policy": "no_slots",
            "calibration_seed_source": "not_applicable",
            "selected_family": False,
            "seeds": [],
            "horizons_months": horizons,
            "bloom_score_source": "not_attempted_upstream_model_unavailable",
            "bloom_calibration": "not_attempted_upstream_model_unavailable",
            "ordinal_calibration": "not_attempted_upstream_model_unavailable",
            "uncertainty_calibration": "not_attempted_upstream_model_unavailable",
        },
    ]


def _require_exact_mapping(value: Any, expected: Mapping[str, Any], *, context: str) -> None:
    if not isinstance(value, Mapping) or _canonical_json_bytes(value) != _canonical_json_bytes(expected):
        raise FinalCalibrationError(f"E0-MCAL {context} drifted")


def _validate_runtime_semantics(value: Mapping[str, Any]) -> None:
    identities = {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "status": "ready_to_lock",
        "base_commit": BASE_COMMIT,
    }
    for key, expected in identities.items():
        if value.get(key) != expected:
            raise FinalCalibrationError(f"E0-MCAL runtime identity drifted: {key}")
    boundary = value.get("scientific_boundary")
    expected_boundary = {
        "source_ids": ["wqp"],
        "method_selection_period": {"start": "2019-01", "end": "2019-12"},
        "method_assessment_period": {"start": "2020-01", "end": "2020-12"},
        "calibration_threshold_period": {"start": "2021-01", "end": "2021-12"},
        "calibration_period_axis": "target_year_month",
        "target_identity_join_key": [
            "source_id",
            "site_id",
            "origin_year_month",
            "target_year_month",
            "horizon_months",
        ],
        "target_projection_scan_predicate": (
            "target_year_month_lte_2021_12_and_origin_year_month_lte_2021_12"
        ),
        "target_projection_scan_enforcement": (
            "same_fd_pyarrow_dataset_scanner_predicate_pushdown_before_materialization"
        ),
        "target_projection_post_filter_allowed": False,
        "raw_label_join_policy": "baseline_and_m0_exact_target_identity",
        "development_roles": ["training", "model_selection", "calibration_threshold"],
        "holdout_locations_allowed": False,
        "post_2021_rows_allowed": False,
        "locked_evaluation_rows_allowed": False,
        "outcome_log_access_allowed": False,
        "e0_m_allowed": False,
        "e0_u_allowed": False,
        "scientific_network_allowed": False,
        "dvc_commands_allowed": False,
    }
    _require_exact_mapping(boundary, expected_boundary, context="scientific boundary")
    matrix = value.get("model_matrix")
    if not isinstance(matrix, Mapping):
        raise FinalCalibrationError("E0-MCAL model matrix is absent")
    if (
        matrix.get("ordered_model_ids") != list(MODEL_IDS)
        or type(matrix.get("model_count")) is not int
        or matrix.get("model_count") != MODEL_COUNT
        or matrix.get("available_calibrable_count") != 6
        or matrix.get("available_not_applicable_count") != 2
        or matrix.get("unavailable_count") != 3
        or _canonical_json_bytes(matrix.get("records"))
        != _canonical_json_bytes(_expected_model_records())
    ):
        raise FinalCalibrationError("E0-MCAL exact eleven-model matrix drifted")
    records = cast(list[Mapping[str, Any]], matrix["records"])
    bloom = sum(
        len(cast(Sequence[Any], record["seeds"])) * len(HORIZONS_MONTHS)
        for record in records
        if record["bloom_calibration"]
        in {"fixed_identity_no_refit", "select_then_refit"}
    )
    ordinal = sum(
        len(cast(Sequence[Any], record["seeds"])) * len(HORIZONS_MONTHS)
        for record in records
        if record["ordinal_calibration"]
        in {"select_cutpoints", "record_not_available_degenerate_constant_score"}
    )
    ordinal_completed = sum(
        len(cast(Sequence[Any], record["seeds"])) * len(HORIZONS_MONTHS)
        for record in records
        if record["ordinal_calibration"] == "select_cutpoints"
    )
    ordinal_unavailable = sum(
        len(cast(Sequence[Any], record["seeds"])) * len(HORIZONS_MONTHS)
        for record in records
        if record["ordinal_calibration"]
        == "record_not_available_degenerate_constant_score"
    )
    uncertainty = sum(
        len(cast(Sequence[Any], record["seeds"])) * len(HORIZONS_MONTHS)
        for record in records
        if record["uncertainty_calibration"]
        == "symmetric_scaled_sigma_split_conformal"
    )
    groups = value.get("calibration_group_matrix")
    if not isinstance(groups, Mapping) or (
        bloom,
        ordinal,
        uncertainty,
        uncertainty * len(Q_C_LEVELS),
    ) != (
        BLOOM_GROUP_COUNT,
        ORDINAL_GROUP_COUNT,
        UNCERTAINTY_GROUP_COUNT,
        Q_C_RECORD_COUNT,
    ) or (
        groups.get("bloom_group_count") != bloom
        or groups.get("ordinal_group_count") != ordinal
        or groups.get("ordinal_completed_group_count") != ordinal_completed
        or groups.get("ordinal_unavailable_group_count") != ordinal_unavailable
        or groups.get("ordinal_unavailable_model_ids") != ["B0"]
        or groups.get("ordinal_unavailable_status")
        != "not_available_degenerate_constant_score"
        or groups.get("ordinal_unavailable_cutpoints") is not None
        or groups.get("uncertainty_group_count") != uncertainty
        or groups.get("q_c_levels") != list(Q_C_LEVELS)
        or groups.get("q_c_record_count") != Q_C_RECORD_COUNT
        or groups.get("uncertainty_model_ids") != list(UNCERTAINTY_MODEL_IDS)
        or groups.get("cross_group_pooling") != "no_pooling"
        or groups.get("complete_target_identity_key")
        != [
            "source_id",
            "site_id",
            "origin_year_month",
            "target_year_month",
            "horizon_months",
        ]
        or groups.get("complete_target_counts_by_target_year_horizon")
        != {
            "2019": {"1": 397, "2": 371, "3": 344},
            "2020": {"1": 261, "2": 287, "3": 314},
            "2021": {"1": 224, "2": 224, "3": 224},
        }
        or groups.get("complete_target_count") != 2646
        or groups.get("bloom_groups_with_exact_complete_target_universe") != 66
        or groups.get("bloom_group_target_universe_policy")
        != "exact_identity_set_equality_no_partial_groups"
    ):
        raise FinalCalibrationError("E0-MCAL calibration group matrix drifted")
    protocol = value.get("calibration_protocol")
    if not isinstance(protocol, Mapping) or (
        protocol.get("bloom_score_source_by_model")
        != {
            "B0": "predicted_bloom_probability",
            "B1": "predicted_bloom_probability",
            "B2": "predicted_bloom_probability",
            "M0": "raw_score",
            "A0": "predicted_bloom_probability",
            "A1": "predicted_bloom_probability",
        }
        or protocol.get("bloom_score_value_policy")
        != "finite_closed_unit_interval_reject_nan_no_normalization"
        or protocol.get("fixed_identity_model_ids") != ["B0"]
        or protocol.get("fixed_identity_calibrator_fit_policy")
        != "no_fit_fixed_transform"
        or type(protocol.get("fixed_identity_calibrator_fit_rows")) is not int
        or protocol.get("fixed_identity_calibrator_fit_rows") != 0
        or protocol.get("fixed_identity_calibrator_refit_year") is not None
        or protocol.get("fixed_identity_metrics_period")
        != "calibration_threshold"
        or protocol.get("fixed_identity_alert_threshold_period")
        != "calibration_threshold"
    ):
        raise FinalCalibrationError(
            "E0-MCAL B0 fixed identity no-fit contract drifted"
        )
    e7 = value.get("e7_terminal_record")
    if not isinstance(e7, Mapping) or (
        e7.get("required_training_rows_per_module") != [4096, 16384, 65536]
        or e7.get("base_seeds") != list(REGISTERED_SEEDS)
        or e7.get("sampling_strata")
        != ["holdout_group_id", "temporal_period", "expert_anchor_band"]
        or e7.get("holdout_group_id_derivation")
        != "source_id_double_colon_site_id_verified_against_assignment"
        or e7.get("temporal_period_derivation")
        != "ordered_unique_eligible_month_index_floor_3i_over_n"
        or e7.get("temporal_period_target_scope")
        != "per_target_module_after_eligibility_filter"
        or e7.get("temporal_period_labels") != ["early", "middle", "late"]
        or e7.get("expert_anchor_band_target_scope") != "per_target_module"
        or e7.get("expert_anchor_band_boundaries")
        != [0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0]
        or e7.get("expert_anchor_band_labels") != ["low", "middle", "high"]
        or e7.get("stratum_derivation_evidence")
        != "boundaries_maps_and_sha256_digests_required"
        or e7.get("eligible_rows_by_module")
        != {"ANFIS-N": 4757, "ANFIS-F": 35273, "ANFIS-T-no-current": 35419}
        or e7.get("expected_slot_count") != 15
        or e7.get("preflight_module_count_per_slot") != 3
        or e7.get("expected_preflight_record_count") != 45
        or e7.get("expected_completed_slot_count") != 5
        or e7.get("expected_completed_module_fit_count") != 15
        or e7.get("new_e7_fit_count") != 15
        or e7.get("primary_fit_reuse_count") != 0
        or e7.get("primary_4096_hash_rank_reuse_forbidden") is not True
        or e7.get("primary_fit_scope") != "hash_rank_not_reused"
        or e7.get("e7_fit_identity_key")
        != ["experiment_id", "training_rows_per_module", "base_seed", "module_id"]
        or e7.get("checkpoint_or_model_write_count") != 0
        or e7.get("family80_no_touch") is not True
        or e7.get("completed_semantics")
        != "anfis_module_fit_only_not_downstream_ablation"
        or e7.get("completed_metric_ids")
        != [
            "expert_anchor_fidelity",
            "membership_stability",
            "deterministic_computational_cost_proxy",
        ]
        or e7.get("computational_cost_proxy")
        != "deterministic_update_count_and_sample_count_no_wall_clock"
        or e7.get("wall_clock_metric_authoritative") is not False
        or e7.get("downstream_metrics_status")
        != "not_estimable_without_separate_temporal_consumers"
        or e7.get("downstream_blockers")
        != ["P0_model_unavailable", "P1_model_unavailable"]
        or e7.get("expected_resource_failure_record_count") != 10
        or e7.get("completed_training_rows_per_module") != [4096]
        or e7.get("resource_failure_training_rows_per_module")
        != [16384, 65536]
        or e7.get("resource_failure_timing")
        != "pre_fit_exact_eligibility_check"
        or e7.get("terminal_statuses")
        != ["completed", "resource_failure_recorded"]
        or e7.get("silent_omission_allowed") is not False
        or e7.get("saturation_claim_authorized_if_incomplete") is not False
        or e7.get("retain_completed_sizes_without_post_hoc_substitution") is not True
    ):
        raise FinalCalibrationError("E0-MCAL E7 terminal record drifted")
    outputs = value.get("outputs")
    if not isinstance(outputs, Mapping) or (
        outputs.get("p_lock_paths")
        != [path for path in FINAL_CALIBRATION_P_STAGED_SCOPE]
        or outputs.get("calibration_paths")
        != [path.as_posix() for path in CALIBRATION_OUTPUT_PATHS]
        or outputs.get("e7_paths") != [path.as_posix() for path in E7_OUTPUT_PATHS]
        or outputs.get("r_output_count") != len(R_OUTPUT_PATHS)
        or outputs.get("prediction_parquet_count") != 0
        or outputs.get("dvc_pointer_count") != 0
        or outputs.get("calibration_manifest_written_last") is not True
        or outputs.get("e7_manifest_written_last") is not True
        or outputs.get("registration_execution_order")
        != ["calibration_bundle", "e7_bundle"]
        or outputs.get("rerun_policy")
        != "fail_closed_if_own_bundle_present_or_partial"
        or outputs.get("calibration_pre_io_dependency")
        != "all_eight_r_outputs_absent"
        or outputs.get("e7_pre_io_dependency")
        != "exact_six_complete_canonical_calibration_outputs"
        or outputs.get("allowed_intermediate_state")
        != "calibration_completed_unpublished_e7_absent"
        or outputs.get("failed_e7_retry_policy")
        != "new_audit_and_authority_required"
        or outputs.get("r_final_required_state")
        != "both_bundles_complete_canonical_manifest_last"
        or outputs.get("final_staged_scope_count") != 8
    ):
        raise FinalCalibrationError("E0-MCAL output contract drifted")
    authorizations = value.get("authorizations")
    if not isinstance(authorizations, Mapping) or any(
        authorizations.get(key) is not False
        for key in (
            "holdout_access_authorized",
            "post_2021_access_authorized",
            "locked_evaluation_authorized",
            "outcome_access_authorized",
            "e0_m_authorized",
            "e0_u_authorized",
            "dvc_commands_authorized",
            "dvc_push_authorized",
            "git_commit_authorized",
            "git_push_authorized",
            "scientific_network_authorized",
            "effective_in_payload",
        )
    ):
        raise FinalCalibrationError("E0-MCAL runtime authorization boundary drifted")


@_error_boundary
def preflight_final_calibration_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    records: list[dict[str, Any]] = []
    for path, role in (
        (DEFAULT_RUNTIME_SCHEMA, "final_calibration_runtime_schema"),
        (DEFAULT_LOCK_SCHEMA, "final_calibration_lock_schema"),
    ):
        schema = _load_json_object(path, repo_root=root)
        validator = getattr(closure_contract, "_assert_supported_json_schema", None)
        if not callable(validator):
            raise FinalCalibrationError(
                "E0-MCAL supported JSON-schema validator is unavailable"
            )
        try:
            validator(schema)
        except ClosureContractError as exc:
            raise FinalCalibrationError(str(exc)) from exc
        records.append(_file_record(path, role=role, repo_root=root))
    runtime = _load_yaml_object(DEFAULT_RUNTIME_PATH, repo_root=root)
    runtime_schema = _load_json_object(DEFAULT_RUNTIME_SCHEMA, repo_root=root)
    try:
        validate_json_schema(runtime, runtime_schema)
    except ClosureContractError as exc:
        raise FinalCalibrationError(str(exc)) from exc
    _validate_runtime_semantics(runtime)
    return {
        "status": "schema_ready",
        "gate": PATCH_GATE,
        "schema_count": 2,
        "schemas": records,
        "supported_subset_verified": True,
        "runtime_schema_validated": True,
    }


@_error_boundary
def load_and_validate_final_calibration_runtime(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    runtime = _load_yaml_object(DEFAULT_RUNTIME_PATH, repo_root=root)
    schema = _load_json_object(DEFAULT_RUNTIME_SCHEMA, repo_root=root)
    try:
        validate_json_schema(runtime, schema)
    except ClosureContractError as exc:
        raise FinalCalibrationError(str(exc)) from exc
    _validate_runtime_semantics(runtime)
    return runtime


def _registered_paths() -> tuple[Path, ...]:
    return tuple(Path(path) for path in mze.ANFIS_ABLATION_R_MZE_STAGED_SCOPE)


def _base_r_mze_authority(*, repo_root: Path) -> dict[str, Any]:
    if _single_parent(repo_root, BASE_COMMIT, context="R-E0-MZE") != P_MZE_COMMIT:
        raise FinalCalibrationError("E0-MCAL base R-E0-MZE parent drifted")
    base_scope = _git_scope(repo_root, P_MZE_COMMIT, BASE_COMMIT)
    if base_scope != {
        "added": 10,
        "modified": 1,
        "deleted": 0,
        "path_count": 11,
        "paths": sorted(path.as_posix() for path in _registered_paths()),
    }:
        raise FinalCalibrationError("E0-MCAL base R-E0-MZE scope drifted")
    try:
        family = mze._family_records(repo_root, registered=True)
    except Exception as exc:
        raise _translate(exc) from exc
    if (
        len(family) != FAMILY_FINAL_COUNT
        or _digest_records(family) != FAMILY_RECORDS_SHA256
    ):
        raise FinalCalibrationError("E0-MCAL exact family80 authority drifted")
    registered: list[dict[str, Any]] = []
    for path in _registered_paths():
        role = (
            "registered_models_dvc"
            if path == mze.MODELS_DVC_PATH
            else "registered_anfis_selection_prediction_pointer"
        )
        registered.append(
            _git_artifact_record(
                path,
                role=role,
                repo_root=repo_root,
                commit=BASE_COMMIT,
            )
        )
    models = next(
        record
        for record in registered
        if record["path"] == mze.MODELS_DVC_PATH.as_posix()
    )
    if models["sha256"] != EXPECTED_MODELS_DVC_SHA256:
        raise FinalCalibrationError("E0-MCAL registered models.dvc drifted")
    gitignore = _git_artifact_record(
        Path(".gitignore"),
        role="registered_models_gitignore",
        repo_root=repo_root,
        commit=BASE_COMMIT,
    )
    return {
        "gate": "R-E0-MZE",
        "commit": BASE_COMMIT,
        "parent_p_mze": P_MZE_COMMIT,
        "registration_scope": {
            key: base_scope[key]
            for key in ("added", "modified", "deleted", "path_count")
        },
        "family_final_count": len(family),
        "family_records_sha256": _digest_records(family),
        "family_records": family,
        "selection_pointer_count": sum(
            record["path"].endswith(".parquet.dvc") for record in registered
        ),
        "registered_paths": registered,
        "models_dvc": models,
        "gitignore": gitignore,
    }


def _historical_e7_blockers(*, repo_root: Path) -> list[dict[str, Any]]:
    expected = (
        (
            HISTORICAL_E7_BLOCKER_PATHS[0],
            46_105,
            "0b2588248ee006f7d8e8843291b6a5847201a36fed35422473c9c0aa9492b10d",
            "5970ab73eedb20f464f804a185a3057daba93ab3",
            "blocked_pending_sampling_strata_contract",
            "not_declared",
        ),
        (
            HISTORICAL_E7_BLOCKER_PATHS[1],
            22_694,
            "cf2cec52d9027db895e8859c7ffb321c831b66510132e137759e567b363f6a50",
            "94f84be4346fd4e01fd52d207b932e21022fc436",
            "blocked_for_separate_gate",
            "not_declared",
        ),
        (
            HISTORICAL_E7_BLOCKER_PATHS[2],
            21_827,
            "49d1a3f562f2cd68ff65f29c92ac4e028b3ad407f30a9960ea0d29260df7d56b",
            "f9956fb51a8b0a742831c3400cc9624f4369fe90",
            "blocked_for_separate_gate",
            False,
        ),
    )
    records: list[dict[str, Any]] = []
    for path, byte_count, digest, oid, status, sizes_authorized in expected:
        record = _git_artifact_record(
            path,
            role="historical_e7_blocker",
            repo_root=repo_root,
            commit=BASE_COMMIT,
        )
        if (
            record["bytes"] != byte_count
            or record["sha256"] != digest
            or record["git_oid"] != oid
            or record["git_mode"] != "100644"
        ):
            raise FinalCalibrationError(
                f"E0-MCAL historical E7 blocker binding drifted: {path.as_posix()}"
            )
        runtime = _load_yaml_object(path, repo_root=repo_root)
        if path == HISTORICAL_E7_BLOCKER_PATHS[0]:
            anfis = runtime.get("anfis")
            observed = (
                cast(Mapping[str, Any], anfis)
                .get("e7_training_size_sensitivity", {})
                .get("status")
                if isinstance(anfis, Mapping)
                else None
            )
        else:
            seals = runtime.get("seals")
            observed = (
                cast(Mapping[str, Any], seals).get("e7_learning_curve_status")
                if isinstance(seals, Mapping)
                else None
            )
        if observed != status:
            raise FinalCalibrationError(
                f"E0-MCAL historical E7 blocker status drifted: {path.as_posix()}"
            )
        if path == HISTORICAL_E7_BLOCKER_PATHS[2]:
            seals = cast(Mapping[str, Any], runtime["seals"])
            if seals.get("e7_learning_curve_sizes_authorized") is not False:
                raise FinalCalibrationError(
                    "E0-MCAL historical E7 size authorization drifted"
                )
        records.append(
            {
                "path": path.as_posix(),
                "bytes": byte_count,
                "sha256": digest,
                "git_oid": oid,
                "git_mode": "100644",
                "e7_learning_curve_status": status,
                "e7_learning_curve_sizes_authorized": sizes_authorized,
            }
        )
    return records


def _workspace_status_records(repo_root: Path) -> list[tuple[str, str]]:
    raw = cast(
        bytes,
        _git(
            repo_root,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            text=False,
        ),
    )
    entries = [entry for entry in raw.split(b"\0") if entry]
    records: list[tuple[str, str]] = []
    for entry in entries:
        try:
            text = entry.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FinalCalibrationError("E0-MCAL Git status path is not UTF-8") from exc
        if len(text) < 4 or text[2] != " ":
            raise FinalCalibrationError("E0-MCAL Git status dialect drifted")
        code, path = text[:2], text[3:]
        if code[0] in {"R", "C"} or code[1] in {"R", "C"}:
            raise FinalCalibrationError("E0-MCAL renamed status is forbidden")
        records.append((code, path))
    if len(records) != len({path for _, path in records}):
        raise FinalCalibrationError("E0-MCAL Git status contains duplicate paths")
    return records


def _h_patch_authority(
    *, repo_root: Path, verify_remote: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(verify_remote) is not bool:
        raise FinalCalibrationError("E0-MCAL remote policy must be an exact boolean")
    head = _git_head(repo_root)
    branch = cast(str, _git(repo_root, "branch", "--show-current")).strip()
    if branch != "main":
        raise FinalCalibrationError("E0-MCAL H authority requires branch main")
    candidate = head == BASE_COMMIT
    if candidate:
        status = _workspace_status_records(repo_root)
        if (
            {path for _, path in status} != set(PATCH_PATHS)
            or any(code not in {"??", "A "} for code, _ in status)
        ):
            raise FinalCalibrationError(
                "E0-MCAL candidate H workspace must contain exact12 additions"
            )
        commit_for_components: str | None = None
        scope = {
            "added": 12,
            "modified": 0,
            "deleted": 0,
            "path_count": 12,
            "paths": list(PATCH_PATHS),
        }
        h_head = BASE_COMMIT
    else:
        if _single_parent(repo_root, head, context="H-E0-MCAL") != BASE_COMMIT:
            raise FinalCalibrationError("E0-MCAL H parent/base topology drifted")
        scope = _git_scope(repo_root, BASE_COMMIT, head)
        expected_scope = {
            "added": 12,
            "modified": 0,
            "deleted": 0,
            "path_count": 12,
            "paths": list(PATCH_PATHS),
        }
        if scope != expected_scope or _workspace_status_records(repo_root):
            raise FinalCalibrationError("E0-MCAL published H scope/worktree drifted")
        commit_for_components = head
        h_head = head
    components = [
        _git_artifact_record(
            Path(path),
            role=PATCH_COMPONENT_ROLES[path],
            repo_root=repo_root,
            commit=commit_for_components,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    tracking = _git_head(repo_root, "origin/main")
    if candidate:
        if tracking != BASE_COMMIT:
            raise FinalCalibrationError("E0-MCAL candidate H tracking ref drifted")
        remote = (
            _live_remote_main_head(repo_root) if verify_remote else tracking
        )
        if remote != BASE_COMMIT:
            raise FinalCalibrationError("E0-MCAL candidate H remote base drifted")
    else:
        if tracking != head:
            raise FinalCalibrationError("E0-MCAL published H tracking ref drifted")
        remote = _live_remote_main_head(repo_root) if verify_remote else tracking
        if remote != head:
            raise FinalCalibrationError("E0-MCAL published H remote ref drifted")
    repository = {
        "base_commit": BASE_COMMIT,
        "head": h_head,
        "h_patch_head": h_head,
        "branch": branch,
        "remote_head": remote,
        "publication_state": "candidate_unpublished" if candidate else "published",
        "scope": scope,
    }
    h_patch = {
        "gate": "H-E0-MCAL",
        "component_count": len(components),
        "added_count": 12,
        "modified_count": 0,
        "components": components,
        "components_sha256": _digest_records(components),
    }
    return repository, h_patch


def _namespace_paths() -> tuple[Path, ...]:
    finals = (
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        *R_OUTPUT_PATHS,
    )
    temporaries = tuple(_temporary_path(path) for path in finals)
    return (*finals, *temporaries, LOCKER_GUARD_PATH, CALIBRATION_GUARD_PATH, E7_GUARD_PATH)


def _require_prelock_namespace(*, repo_root: Path) -> None:
    occupied = [
        path.as_posix()
        for path in _namespace_paths()
        if _entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise FinalCalibrationError(
            f"E0-MCAL prelock namespace is occupied: {occupied}"
        )


def _output_contract(runtime: Mapping[str, Any]) -> dict[str, Any]:
    outputs = cast(Mapping[str, Any], runtime["outputs"])
    return {
        **_deep_copy(outputs),
        "calibration_manifest_last_path": FINAL_CALIBRATION_MANIFEST_PATH.as_posix(),
        "e7_manifest_last_path": ANFIS_LEARNING_CURVE_MANIFEST_PATH.as_posix(),
        "manifest_last_policy": "two_independent_atomic_bundles_manifest_last",
    }


@_error_boundary
def collect_final_calibration_prelock_state(
    *, verify_remote: bool = False, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema_preflight = preflight_final_calibration_schema(repo_root=root)
    runtime = load_and_validate_final_calibration_runtime(repo_root=root)
    repository, h_patch = _h_patch_authority(
        repo_root=root, verify_remote=verify_remote
    )
    base = _base_r_mze_authority(repo_root=root)
    historical_e7_blockers = _historical_e7_blockers(repo_root=root)
    scientific_inputs = _scientific_input_inventory(repo_root=root)
    e7_runtime = cast(Mapping[str, Any], runtime["e7_terminal_record"])
    if e7_runtime.get("historical_blockers_adopted") != historical_e7_blockers:
        raise FinalCalibrationError("E0-MCAL historical E7 correction drifted")
    _require_prelock_namespace(repo_root=root)
    outcome_path = Path(mze.OUTCOME_ACCESS_LOG)
    if _entry_exists(outcome_path, repo_root=root):
        raise FinalCalibrationError("E0-MCAL outcome access log must remain absent")
    e0_m_present = [
        path for path in mze.E0_M_PATHS if _entry_exists(Path(path), repo_root=root)
    ]
    if e0_m_present:
        raise FinalCalibrationError(
            f"E0-MCAL final E0-M namespace must remain absent: {e0_m_present}"
        )
    runtime_contract = {
        "physical_input_count": len(PATCH_PATHS),
        "historical_input_count": 0,
        "runtime": next(
            record
            for record in h_patch["components"]
            if record["path"] == DEFAULT_RUNTIME_PATH.as_posix()
        ),
        "runtime_schema": next(
            record
            for record in h_patch["components"]
            if record["path"] == DEFAULT_RUNTIME_SCHEMA.as_posix()
        ),
        "lock_schema": next(
            record
            for record in h_patch["components"]
            if record["path"] == DEFAULT_LOCK_SCHEMA.as_posix()
        ),
        "runtime_payload_sha256": _sha256_bytes(_canonical_json_bytes(runtime)),
        "scientific_authority_record_count": scientific_inputs[
            "authority_record_count"
        ],
        "scientific_payload_binding_count": scientific_inputs[
            "payload_binding_count"
        ],
        "scientific_authority_records_sha256": scientific_inputs[
            "authority_records_sha256"
        ],
        "scientific_payload_bindings_sha256": scientific_inputs[
            "payload_bindings_sha256"
        ],
        "supported_schema_subset_verified": schema_preflight[
            "supported_subset_verified"
        ],
    }
    boundary = {
        **_deep_copy(runtime["scientific_boundary"]),
        "calibration_protocol": _deep_copy(runtime["calibration_protocol"]),
        "holdout_row_count": 0,
        "post_2021_row_count": 0,
        "outcome_path_count": 0,
        "evaluation_batch_authorized": False,
    }
    companion_contract = {
        "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
        "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
        "output_count": EXPECTED_COMPANION_OUTPUT_COUNT,
        "script_path": LOCKER_PATH.as_posix(),
        "manifest_written_last": True,
    }
    prelock = {
        "git_status_clean": True,
        "p_output_present_count": 0,
        "r_output_present_count": 0,
        "temporary_present_count": 0,
        "coordination_present_count": 0,
        "family_final_count": base["family_final_count"],
        "selection_pointer_count": base["selection_pointer_count"],
        "models_dvc_sha256": cast(Mapping[str, Any], base["models_dvc"])["sha256"],
        "outcome_access_log_absent": True,
        "holdout_rows_opened": False,
        "post_2021_rows_opened": False,
        "dvc_commands_run": False,
        "scientific_writes_performed": False,
        "scientific_authority_record_count": scientific_inputs[
            "authority_record_count"
        ],
        "scientific_payload_binding_count": scientific_inputs[
            "payload_binding_count"
        ],
        "scientific_authority_records_sha256": scientific_inputs[
            "authority_records_sha256"
        ],
        "scientific_payload_bindings_sha256": scientific_inputs[
            "payload_bindings_sha256"
        ],
        "base_r_mze_authority": base,
        "calibration_protocol": _deep_copy(runtime["calibration_protocol"]),
        "companion_contract": companion_contract,
    }
    return {
        "repository": repository,
        "h_patch": h_patch,
        "runtime_contract": runtime_contract,
        "scientific_input_inventory": scientific_inputs,
        "scientific_boundary": boundary,
        "model_matrix": _deep_copy(runtime["model_matrix"]),
        "calibration_group_matrix": _deep_copy(runtime["calibration_group_matrix"]),
        "e7_terminal_record": _deep_copy(runtime["e7_terminal_record"]),
        "output_contract": _output_contract(runtime),
        "prelock": prelock,
    }


def _payload_repository(repository: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "base_commit": repository["base_commit"],
        "h_patch_head": repository["h_patch_head"],
        "branch": repository["branch"],
        "remote_head": repository["remote_head"],
        "scope": _deep_copy(repository["scope"]),
    }


def _default_unrun_verification() -> dict[str, Any]:
    return {
        "status": "not_run_by_payload_builder",
        "commands_run": False,
        "scientific_execution_run": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


@_error_boundary
def build_final_calibration_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str | None = None,
    created_at_utc: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    if generated_at_utc is not None and created_at_utc is not None:
        raise FinalCalibrationError("E0-MCAL timestamp aliases are mutually exclusive")
    required = {
        "repository",
        "h_patch",
        "runtime_contract",
        "scientific_input_inventory",
        "scientific_boundary",
        "model_matrix",
        "calibration_group_matrix",
        "e7_terminal_record",
        "output_contract",
        "prelock",
    }
    if set(prelock) != required:
        raise FinalCalibrationError("E0-MCAL prelock dialect drifted")
    timestamp = generated_at_utc or created_at_utc or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": LOCK_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "status": "locked_unpublished",
        "generated_at_utc": timestamp,
        "repository": _payload_repository(cast(Mapping[str, Any], prelock["repository"])),
        "h_patch": _deep_copy(prelock["h_patch"]),
        "runtime": _deep_copy(prelock["runtime_contract"]),
        "scientific_input_inventory": _deep_copy(
            prelock["scientific_input_inventory"]
        ),
        "scientific_boundary": _deep_copy(prelock["scientific_boundary"]),
        "model_matrix": _deep_copy(prelock["model_matrix"]),
        "calibration_group_matrix": _deep_copy(prelock["calibration_group_matrix"]),
        "e7_terminal_record": _deep_copy(prelock["e7_terminal_record"]),
        "output_contract": _deep_copy(prelock["output_contract"]),
        "prelock": _deep_copy(prelock["prelock"]),
        "verification": _deep_copy(
            verification if verification is not None else _default_unrun_verification()
        ),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
    }


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise FinalCalibrationError("E0-MCAL generated timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FinalCalibrationError("E0-MCAL generated timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FinalCalibrationError("E0-MCAL generated timestamp must be timezone-aware")


def _validate_command_evidence(
    value: Any, *, expected_command: Sequence[str], context: str
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
        raise FinalCalibrationError(f"E0-MCAL {context} evidence dialect drifted")
    if (
        value.get("command") != list(expected_command)
        or type(value.get("returncode")) is not int
        or value.get("returncode") != 0
        or type(value.get("stdout_line_count")) is not int
        or int(value["stdout_line_count"]) < 0
        or type(value.get("stderr_line_count")) is not int
        or value.get("stderr_line_count") != 0
        or value.get("stderr_sha256") != EMPTY_SHA256
        or not isinstance(value.get("stdout_sha256"), str)
        or SHA256_RE.fullmatch(str(value["stdout_sha256"])) is None
    ):
        raise FinalCalibrationError(f"E0-MCAL {context} evidence drifted")


def _validate_verification(value: Any, *, repo_root: Path) -> None:
    if not isinstance(value, Mapping):
        raise FinalCalibrationError("E0-MCAL verification evidence is absent")
    if value == _default_unrun_verification():
        return
    expected_keys = {
        "schema_preflight",
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
    }
    if set(value) != expected_keys:
        raise FinalCalibrationError("E0-MCAL verification evidence key set drifted")
    if _canonical_json_bytes(value["schema_preflight"]) != _canonical_json_bytes(
        preflight_final_calibration_schema(repo_root=repo_root)
    ):
        raise FinalCalibrationError("E0-MCAL schema preflight evidence drifted")
    for key, command in (
        ("full_type_check", TYPE_CHECK_COMMAND),
        ("poetry_check", POETRY_CHECK_COMMAND),
        ("publication_guard", PUBLICATION_GUARD_COMMAND),
        ("git_diff_check", DIFF_CHECK_COMMAND),
    ):
        _validate_command_evidence(value[key], expected_command=command, context=key)
    focused = value["focused_tests"]
    if not isinstance(focused, Mapping):
        raise FinalCalibrationError("E0-MCAL focused evidence is absent")
    extras = {"test_count", "skipped_count", "deselected_count"}
    base_keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    if set(focused) != base_keys | extras or any(
        type(focused.get(key)) is not int
        for key in ("test_count", "skipped_count", "deselected_count")
    ) or (
        focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise FinalCalibrationError("E0-MCAL focused count evidence drifted")
    _validate_command_evidence(
        {key: focused[key] for key in base_keys},
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused_tests",
    )


def _payload_expected_from_prelock(
    payload: Mapping[str, Any], state: Mapping[str, Any]
) -> dict[str, Any]:
    return build_final_calibration_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )


@_error_boundary
def validate_final_calibration_lock_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    verify_remote: bool = False,
) -> None:
    root = _root(repo_root)
    if not isinstance(payload, Mapping):
        raise FinalCalibrationError("E0-MCAL lock payload must be an object")
    schema = _load_json_object(DEFAULT_LOCK_SCHEMA, repo_root=root)
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise FinalCalibrationError(str(exc)) from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise FinalCalibrationError("E0-MCAL unpublished authorizations drifted")
    state = collect_final_calibration_prelock_state(
        verify_remote=verify_remote, repo_root=root
    )
    expected = _payload_expected_from_prelock(payload, state)
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise FinalCalibrationError("E0-MCAL lock semantic reconstruction drifted")


def _public_artifact_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in ("role", "path", "bytes", "sha256")
    }


def _expected_companion(
    payload: Mapping[str, Any], lock_record: Mapping[str, Any]
) -> dict[str, Any]:
    components = cast(Sequence[Mapping[str, Any]], cast(Mapping[str, Any], payload["h_patch"])["components"])
    inputs = [_public_artifact_record(record) for record in components]
    inputs.sort(key=lambda record: cast(str, record["path"]))
    script = next(
        record for record in inputs if record["path"] == LOCKER_PATH.as_posix()
    )
    return {
        "schema_version": COMPANION_SCHEMA_VERSION,
        "status": "completed",
        "gate": PATCH_GATE,
        "script": script,
        "inputs": inputs,
        "historical_inputs": [],
        "outputs": [dict(lock_record)],
        "completion_marker_written_last": True,
        "scientific_execution_run": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


def _physical_snapshot(
    repo_root: Path, *, scientific_inventory: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    paths = [Path(path) for path in PATCH_PATHS]
    paths.extend(_registered_paths())
    paths.append(Path(".gitignore"))
    known = set(paths)
    for _, path in _scientific_authority_path_roles():
        if path not in known:
            paths.append(path)
            known.add(path)
    payload_bindings = scientific_inventory.get("payload_bindings")
    authority_records = scientific_inventory.get("authority_records")
    if not isinstance(payload_bindings, list):
        raise FinalCalibrationError(
            "E0-MCAL physical snapshot lacks scientific payload bindings"
        )
    if not isinstance(authority_records, list):
        raise FinalCalibrationError(
            "E0-MCAL physical snapshot lacks scientific authority records"
        )
    payload_paths: set[Path] = set()
    for record in payload_bindings:
        if not isinstance(record, Mapping) or not isinstance(
            record.get("path"), str
        ):
            raise FinalCalibrationError(
                "E0-MCAL physical snapshot payload dialect drifted"
            )
        path = Path(cast(str, record["path"]))
        payload_paths.add(path)
        if path not in known:
            paths.append(path)
            known.add(path)
    if not all(isinstance(record, Mapping) for record in authority_records):
        raise FinalCalibrationError(
            "E0-MCAL physical snapshot authority dialect drifted"
        )
    authorized_dvc_pointers = _scientific_dvc_pointer_paths(
        cast(Sequence[Mapping[str, Any]], authority_records),
        cast(Sequence[Mapping[str, Any]], payload_bindings),
    )
    records: list[dict[str, Any]] = []
    for path in paths:
        if path in payload_paths:
            payload, metadata = _read_scientific_payload_bytes_and_metadata(
                path,
                authorized_dvc_pointers=authorized_dvc_pointers,
                repo_root=repo_root,
            )
        else:
            payload, metadata = _read_regular_bytes_and_metadata(
                path, repo_root=repo_root
            )
        records.append(
            {
                "path": path.as_posix(),
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": int(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "size": len(payload),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
                "sha256": _sha256_bytes(payload),
            }
        )
    try:
        records.extend(dict(record) for record in mze._family_physical_snapshot(repo_root))
    except Exception as exc:
        raise _translate(exc) from exc
    return tuple(records)


def _require_physical_snapshot(
    expected: Sequence[Mapping[str, Any]],
    *,
    scientific_inventory: Mapping[str, Any],
    repo_root: Path,
    context: str,
) -> None:
    if _canonical_json_bytes(expected) != _canonical_json_bytes(
        _physical_snapshot(repo_root, scientific_inventory=scientific_inventory)
    ):
        raise FinalCalibrationError(f"E0-MCAL physical authority changed {context}")


def _rollback_outputs_best_effort(
    outputs: Sequence[mt._OwnedOutput],
) -> FinalCalibrationError | None:
    errors: list[BaseException] = []
    for output in reversed(outputs):
        try:
            mt._rollback_owned_output(output)
        except BaseException as exc:
            errors.append(exc)
    if not errors:
        return None
    error = FinalCalibrationError("E0-MCAL owned-output rollback was incomplete")
    for nested in errors:
        error.add_note(str(nested))
    return error


def _close_outputs_best_effort(outputs: Sequence[mt._OwnedOutput]) -> None:
    errors: list[BaseException] = []
    for output in reversed(outputs):
        try:
            mt._close_owned_output(output)
        except BaseException as exc:
            errors.append(exc)
    if errors:
        error = FinalCalibrationError("E0-MCAL owned-output descriptor cleanup failed")
        for nested in errors:
            error.add_note(str(nested))
        raise error


def _require_publication_verification(payload: Mapping[str, Any], *, repo_root: Path) -> None:
    verification = payload.get("verification")
    if verification == _default_unrun_verification():
        raise FinalCalibrationError(
            "E0-MCAL publication requires the exact frozen verification evidence"
        )
    _validate_verification(verification, repo_root=repo_root)


@_error_boundary
def publish_final_calibration_lock_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or repository.get("h_patch_head") == BASE_COMMIT:
        raise FinalCalibrationError("E0-MCAL H must be published before P publication")
    _require_publication_verification(payload, repo_root=root)
    validate_final_calibration_lock_payload(
        payload, repo_root=root, verify_remote=True
    )
    scientific_inventory = payload.get("scientific_input_inventory")
    if not isinstance(scientific_inventory, Mapping):
        raise FinalCalibrationError("E0-MCAL scientific inventory is absent")
    snapshot = _physical_snapshot(
        root, scientific_inventory=scientific_inventory
    )
    initial_head = _git_head(root)
    initial_tracking = _git_head(root, "origin/main")
    if initial_head != repository.get("h_patch_head") or initial_tracking != initial_head:
        raise FinalCalibrationError("E0-MCAL H refs drifted before publication")
    _require_prelock_namespace(repo_root=root)
    guard: mt._OwnedGuard | None = None
    published: list[mt._OwnedOutput] = []
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MCAL final calibration lock publication in progress\n",
            repo_root=root,
        )
        _require_physical_snapshot(
            snapshot,
            scientific_inventory=scientific_inventory,
            repo_root=root,
            context="after guard acquisition",
        )
        lock_bytes = _canonical_json_bytes(payload)
        lock_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, lock_bytes, repo_root=root
        )
        published.append(lock_output)
        _validate_owned_output_bytes_for_root(
            lock_output, lock_bytes, repo_root=root, context="after lock publication"
        )
        _require_physical_snapshot(
            snapshot,
            scientific_inventory=scientific_inventory,
            repo_root=root,
            context="after lock publication",
        )
        lock_record = {
            "role": "final_calibration_lock",
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "bytes": len(lock_bytes),
            "sha256": _sha256_bytes(lock_bytes),
        }
        companion = _expected_companion(payload, lock_record)
        companion_bytes = _canonical_json_bytes(companion)
        companion_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, companion_bytes, repo_root=root
        )
        published.append(companion_output)
        _validate_owned_output_bytes_for_root(
            lock_output, lock_bytes, repo_root=root, context="after companion publication"
        )
        _validate_owned_output_bytes_for_root(
            companion_output,
            companion_bytes,
            repo_root=root,
            context="after companion publication",
        )
        _require_physical_snapshot(
            snapshot,
            scientific_inventory=scientific_inventory,
            repo_root=root,
            context="after companion publication",
        )
        if _git_head(root) != initial_head or _git_head(root, "origin/main") != initial_tracking:
            raise FinalCalibrationError("E0-MCAL refs changed during publication")
        mt._release_publication_guard(guard)
        guard = None
        _validate_owned_output_bytes_for_root(
            lock_output, lock_bytes, repo_root=root, context="after guard release"
        )
        _validate_owned_output_bytes_for_root(
            companion_output,
            companion_bytes,
            repo_root=root,
            context="after guard release",
        )
        _require_physical_snapshot(
            snapshot,
            scientific_inventory=scientific_inventory,
            repo_root=root,
            context="after guard release",
        )
        committed = True
        return dict(payload), companion
    except BaseException as exc:
        rollback_error = _rollback_outputs_best_effort(published)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            if rollback_error is not None:
                exc.add_note(str(rollback_error))
            raise
        translated = exc if isinstance(exc, FinalCalibrationError) else _translate(exc)
        if rollback_error is not None:
            translated.add_note(str(rollback_error))
        if translated is exc:
            raise
        raise translated from exc
    finally:
        if guard is not None:
            try:
                mt._release_publication_guard(guard, tolerate_foreign=True)
            except Exception:
                pass
        if committed:
            _close_outputs_best_effort(published)


def _validate_owned_output_bytes_for_root(
    output: mt._OwnedOutput,
    expected: bytes,
    *,
    repo_root: Path,
    context: str,
) -> None:
    try:
        mt._validate_owned_output(output)
    except Exception as exc:
        raise _translate(exc) from exc
    payload, metadata = _read_regular_bytes_and_metadata(output.path, repo_root=repo_root)
    if (
        payload != expected
        or (metadata.st_dev, metadata.st_ino) != (output.device, output.inode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise FinalCalibrationError(
            f"E0-MCAL owned output drifted {context}: {output.path.as_posix()}"
        )


@_error_boundary
def execute_and_publish_final_calibration_lock_bundle(
    verification: Mapping[str, Any],
    *,
    generated_at_utc: str | None = None,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    before = collect_final_calibration_prelock_state(
        verify_remote=verify_remote, repo_root=root
    )
    payload = build_final_calibration_lock_payload(
        before,
        verification,
        generated_at_utc=generated_at_utc,
        repo_root=root,
    )
    validate_final_calibration_lock_payload(
        payload, repo_root=root, verify_remote=verify_remote
    )
    return publish_final_calibration_lock_bundle(payload, repo_root=root)


def _parse_canonical_json(path: Path, *, repo_root: Path) -> dict[str, Any]:
    payload = _read_regular_bytes(path, repo_root=repo_root)
    value = _parse_json_bytes(payload, context=path.as_posix())
    if not isinstance(value, dict) or payload != _canonical_json_bytes(value):
        raise FinalCalibrationError(
            f"E0-MCAL published JSON is not canonical: {path.as_posix()}"
        )
    return value


def _effective_authority_binding_sha256(
    *,
    repo_root: Path,
    scientific_inventory: Mapping[str, Any],
    p_patch_head: str | None = None,
    lock_record: Mapping[str, Any] | None = None,
) -> str:
    effective_head = _git_head(repo_root) if p_patch_head is None else p_patch_head
    effective_lock = (
        _file_record(
            DEFAULT_PATCH_LOCK_PATH,
            role="final_calibration_lock",
            repo_root=repo_root,
        )
        if lock_record is None
        else lock_record
    )
    return _sha256_bytes(
        _canonical_json_bytes(
            {
                "gate": PATCH_GATE,
                "p_patch_head": effective_head,
                "lock_sha256": effective_lock["sha256"],
                "scientific_authority_records_sha256": scientific_inventory[
                    "authority_records_sha256"
                ],
                "scientific_payload_bindings_sha256": scientific_inventory[
                    "payload_bindings_sha256"
                ],
            }
        )
    )


def _reconstruct_published_h_state(
    h_head: str, *, repo_root: Path
) -> dict[str, Any]:
    if h_head == BASE_COMMIT or SHA1_RE.fullmatch(h_head) is None:
        raise FinalCalibrationError("E0-MCAL published H commit is absent")
    if _single_parent(repo_root, h_head, context="H-E0-MCAL") != BASE_COMMIT:
        raise FinalCalibrationError("E0-MCAL published H parent drifted")
    scope = _git_scope(repo_root, BASE_COMMIT, h_head)
    expected_scope = {
        "added": 12,
        "modified": 0,
        "deleted": 0,
        "path_count": 12,
        "paths": list(PATCH_PATHS),
    }
    if scope != expected_scope:
        raise FinalCalibrationError("E0-MCAL published H scope drifted")
    components = [
        _git_artifact_record(
            Path(path),
            role=PATCH_COMPONENT_ROLES[path],
            repo_root=repo_root,
            commit=h_head,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    schema_preflight = preflight_final_calibration_schema(repo_root=repo_root)
    runtime = load_and_validate_final_calibration_runtime(repo_root=repo_root)
    base = _base_r_mze_authority(repo_root=repo_root)
    historical_e7_blockers = _historical_e7_blockers(repo_root=repo_root)
    scientific_inputs = _scientific_input_inventory(repo_root=repo_root)
    e7_runtime = cast(Mapping[str, Any], runtime["e7_terminal_record"])
    if e7_runtime.get("historical_blockers_adopted") != historical_e7_blockers:
        raise FinalCalibrationError("E0-MCAL historical E7 correction drifted")
    h_patch = {
        "gate": "H-E0-MCAL",
        "component_count": 12,
        "added_count": 12,
        "modified_count": 0,
        "components": components,
        "components_sha256": _digest_records(components),
    }
    runtime_contract = {
        "physical_input_count": 12,
        "historical_input_count": 0,
        "runtime": next(
            record for record in components if record["path"] == DEFAULT_RUNTIME_PATH.as_posix()
        ),
        "runtime_schema": next(
            record for record in components if record["path"] == DEFAULT_RUNTIME_SCHEMA.as_posix()
        ),
        "lock_schema": next(
            record for record in components if record["path"] == DEFAULT_LOCK_SCHEMA.as_posix()
        ),
        "runtime_payload_sha256": _sha256_bytes(_canonical_json_bytes(runtime)),
        "scientific_authority_record_count": scientific_inputs[
            "authority_record_count"
        ],
        "scientific_payload_binding_count": scientific_inputs[
            "payload_binding_count"
        ],
        "scientific_authority_records_sha256": scientific_inputs[
            "authority_records_sha256"
        ],
        "scientific_payload_bindings_sha256": scientific_inputs[
            "payload_bindings_sha256"
        ],
        "supported_schema_subset_verified": schema_preflight["supported_subset_verified"],
    }
    boundary = {
        **_deep_copy(runtime["scientific_boundary"]),
        "calibration_protocol": _deep_copy(runtime["calibration_protocol"]),
        "holdout_row_count": 0,
        "post_2021_row_count": 0,
        "outcome_path_count": 0,
        "evaluation_batch_authorized": False,
    }
    companion_contract = {
        "physical_input_count": 12,
        "historical_input_count": 0,
        "output_count": 1,
        "script_path": LOCKER_PATH.as_posix(),
        "manifest_written_last": True,
    }
    prelock = {
        "git_status_clean": True,
        "p_output_present_count": 0,
        "r_output_present_count": 0,
        "temporary_present_count": 0,
        "coordination_present_count": 0,
        "family_final_count": 80,
        "selection_pointer_count": 10,
        "models_dvc_sha256": EXPECTED_MODELS_DVC_SHA256,
        "outcome_access_log_absent": True,
        "holdout_rows_opened": False,
        "post_2021_rows_opened": False,
        "dvc_commands_run": False,
        "scientific_writes_performed": False,
        "scientific_authority_record_count": scientific_inputs[
            "authority_record_count"
        ],
        "scientific_payload_binding_count": scientific_inputs[
            "payload_binding_count"
        ],
        "scientific_authority_records_sha256": scientific_inputs[
            "authority_records_sha256"
        ],
        "scientific_payload_bindings_sha256": scientific_inputs[
            "payload_bindings_sha256"
        ],
        "base_r_mze_authority": base,
        "calibration_protocol": _deep_copy(runtime["calibration_protocol"]),
        "companion_contract": companion_contract,
    }
    return {
        "repository": {
            "base_commit": BASE_COMMIT,
            "head": h_head,
            "h_patch_head": h_head,
            "branch": "main",
            "remote_head": h_head,
            "publication_state": "published",
            "scope": scope,
        },
        "h_patch": h_patch,
        "runtime_contract": runtime_contract,
        "scientific_input_inventory": scientific_inputs,
        "scientific_boundary": boundary,
        "model_matrix": _deep_copy(runtime["model_matrix"]),
        "calibration_group_matrix": _deep_copy(runtime["calibration_group_matrix"]),
        "e7_terminal_record": _deep_copy(runtime["e7_terminal_record"]),
        "output_contract": _output_contract(runtime),
        "prelock": prelock,
    }


def _validate_published_lock_payload(
    payload: Mapping[str, Any], *, repo_root: Path
) -> None:
    schema = _load_json_object(DEFAULT_LOCK_SCHEMA, repo_root=repo_root)
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise FinalCalibrationError(str(exc)) from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=repo_root)
    _require_publication_verification(payload, repo_root=repo_root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise FinalCalibrationError("E0-MCAL published lock authorizations drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise FinalCalibrationError("E0-MCAL published H binding is absent")
    state = _reconstruct_published_h_state(
        str(repository["h_patch_head"]), repo_root=repo_root
    )
    expected = _payload_expected_from_prelock(payload, state)
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise FinalCalibrationError("E0-MCAL published lock reconstruction drifted")


def _parse_closed_csv(
    payload: bytes,
    *,
    expected_header: Sequence[str],
    expected_row_count: int,
    context: str,
) -> list[dict[str, str]]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FinalCalibrationError(
            f"E0-MCAL {context} CSV is not UTF-8"
        ) from exc
    if (
        not text.endswith("\n")
        or "\r" in text
        or "\x00" in text
        or text.startswith("\ufeff")
    ):
        raise FinalCalibrationError(
            f"E0-MCAL {context} CSV byte dialect drifted"
        )
    try:
        table = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as exc:
        raise FinalCalibrationError(
            f"E0-MCAL {context} CSV is malformed"
        ) from exc
    header = list(expected_header)
    if (
        not table
        or table[0] != header
        or len(set(table[0])) != len(table[0])
        or len(table) != expected_row_count + 1
        or any(len(row) != len(header) for row in table[1:])
    ):
        raise FinalCalibrationError(
            f"E0-MCAL {context} CSV shape drifted"
        )
    canonical = io.StringIO(newline="")
    writer = csv.writer(canonical, lineterminator="\n")
    writer.writerows(table)
    if canonical.getvalue().encode("utf-8") != payload:
        raise FinalCalibrationError(
            f"E0-MCAL {context} CSV is not canonical"
        )
    return [dict(zip(header, row, strict=True)) for row in table[1:]]


def _csv_integer(value: str, *, context: str) -> int:
    if re.fullmatch(r"0|[1-9][0-9]*", value) is None:
        raise FinalCalibrationError(
            f"E0-MCAL {context} is not one canonical nonnegative integer"
        )
    return int(value)


def _csv_float(value: str, *, context: str) -> float:
    try:
        observed = float(value)
    except ValueError as exc:
        raise FinalCalibrationError(
            f"E0-MCAL {context} is not one canonical finite float"
        ) from exc
    if not math.isfinite(observed) or format(observed, ".17g") != value:
        raise FinalCalibrationError(
            f"E0-MCAL {context} is not one canonical finite float"
        )
    return observed


def _json_float(value: Any, *, context: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise FinalCalibrationError(
            f"E0-MCAL {context} is not one exact finite JSON float"
        )
    return value


def _calibration_group_keys(
    model_ids: Sequence[str] = CALIBRABLE_MODEL_IDS,
) -> list[tuple[str, int, int]]:
    seeds = {
        "B0": (1729,),
        "B1": REGISTERED_SEEDS,
        "B2": REGISTERED_SEEDS,
        "M0": (1729,),
        "A0": REGISTERED_SEEDS,
        "A1": REGISTERED_SEEDS,
    }
    return [
        (model_id, seed, horizon)
        for model_id in sorted(model_ids)
        for seed in sorted(seeds[model_id])
        for horizon in HORIZONS_MONTHS
    ]


def _validate_calibrator_specs(value: Any) -> dict[tuple[str, int, int], Mapping[str, Any]]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "gate",
        "bloom_calibrators",
        "split_conformal_q_c",
    }:
        raise FinalCalibrationError("E0-MCAL calibrator specs dialect drifted")
    calibrators = value.get("bloom_calibrators")
    q_c_records = value.get("split_conformal_q_c")
    if (
        value.get("schema_version") != "closure_final_calibrator_specs_v1"
        or value.get("gate") != PATCH_GATE
        or not isinstance(calibrators, list)
        or len(calibrators) != BLOOM_GROUP_COUNT
        or not isinstance(q_c_records, list)
        or len(q_c_records) != Q_C_RECORD_COUNT
    ):
        raise FinalCalibrationError("E0-MCAL calibrator specs cardinality drifted")
    expected_keys = _calibration_group_keys()
    observed_keys: list[tuple[str, int, int]] = []
    indexed: dict[tuple[str, int, int], Mapping[str, Any]] = {}
    methods = ("identity", "platt_logistic", "isotonic_regression")
    for record in calibrators:
        if not isinstance(record, Mapping) or set(record) != {
            "model_id",
            "model_seed",
            "horizon_months",
            "selection_fit_year",
            "selection_assessment_year",
            "refit_year",
            "refit_status",
            "selected_method",
            "selection_candidates",
            "refit_spec",
        }:
            raise FinalCalibrationError("E0-MCAL bloom calibrator record drifted")
        model_id = record.get("model_id")
        model_seed = record.get("model_seed")
        horizon = record.get("horizon_months")
        if (
            not isinstance(model_id, str)
            or type(model_seed) is not int
            or type(horizon) is not int
        ):
            raise FinalCalibrationError("E0-MCAL bloom calibrator identity drifted")
        identity = (model_id, model_seed, horizon)
        observed_keys.append(identity)
        indexed[identity] = record
        selected_method = record.get("selected_method")
        candidates = record.get("selection_candidates")
        expected_methods = ("identity",) if model_id == "B0" else methods
        if (
            type(record.get("selection_fit_year")) is not int
            or record.get("selection_fit_year") != 2019
            or type(record.get("selection_assessment_year")) is not int
            or record.get("selection_assessment_year") != 2020
            or selected_method not in expected_methods
            or not isinstance(candidates, list)
            or len(candidates) != len(expected_methods)
        ):
            raise FinalCalibrationError(
                f"E0-MCAL bloom selection contract drifted: {identity}"
            )
        normalized_candidates: list[Mapping[str, Any]] = []
        for rank, (candidate, method) in enumerate(
            zip(candidates, expected_methods, strict=True)
        ):
            if not isinstance(candidate, Mapping):
                raise FinalCalibrationError(
                    f"E0-MCAL bloom candidate dialect drifted: {identity}"
                )
            candidate_map = cast(Mapping[str, Any], candidate)
            if (
                set(candidate_map)
                != {"method", "brier", "ece10", "simplicity_rank"}
                or candidate_map.get("method") != method
                or type(candidate_map.get("simplicity_rank")) is not int
                or candidate_map.get("simplicity_rank") != rank
            ):
                raise FinalCalibrationError(
                    f"E0-MCAL bloom candidate dialect drifted: {identity}"
                )
            for metric in ("brier", "ece10"):
                metric_value = _json_float(
                    candidate_map.get(metric), context=f"{identity} {metric}"
                )
                if not 0.0 <= metric_value <= 1.0:
                    raise FinalCalibrationError(
                        f"E0-MCAL bloom candidate range drifted: {identity}"
                    )
            normalized_candidates.append(candidate_map)
        minimum_brier = min(
            cast(float, candidate["brier"])
            for candidate in normalized_candidates
        )
        eligible_candidates = [
            candidate
            for candidate in normalized_candidates
            if cast(float, candidate["brier"]) <= minimum_brier + 0.001
        ]
        expected_selected = min(
            eligible_candidates,
            key=lambda candidate: (
                cast(float, candidate["ece10"]),
                cast(int, candidate["simplicity_rank"]),
            ),
        )["method"]
        if selected_method != expected_selected:
            raise FinalCalibrationError(
                f"E0-MCAL bloom method-selection rule drifted: {identity}"
            )
        refit_spec = record.get("refit_spec")
        if not isinstance(refit_spec, Mapping) or set(refit_spec) != {
            "method",
            "parameters",
            "fit_rows",
        } or refit_spec.get("method") != selected_method:
            raise FinalCalibrationError(
                f"E0-MCAL bloom refit specification drifted: {identity}"
            )
        if model_id == "B0":
            if (
                record.get("refit_year") is not None
                or record.get("refit_status") != "not_applicable_fixed_identity"
                or type(refit_spec.get("fit_rows")) is not int
                or refit_spec.get("fit_rows") != 0
            ):
                raise FinalCalibrationError("E0-MCAL B0 identity refit drifted")
        elif (
            type(record.get("refit_year")) is not int
            or record.get("refit_year") != 2021
            or record.get("refit_status") != "completed"
            or type(refit_spec.get("fit_rows")) is not int
            or refit_spec.get("fit_rows") != 224
        ):
            raise FinalCalibrationError(
                f"E0-MCAL bloom 2021 refit drifted: {identity}"
            )
        parameters = refit_spec.get("parameters")
        if selected_method == "identity":
            if parameters != {}:
                raise FinalCalibrationError("E0-MCAL identity parameters drifted")
        elif selected_method == "platt_logistic":
            if not isinstance(parameters, Mapping) or set(parameters) != {
                "coefficient",
                "intercept",
            }:
                raise FinalCalibrationError("E0-MCAL Platt parameters drifted")
            _json_float(parameters.get("coefficient"), context="Platt coefficient")
            _json_float(parameters.get("intercept"), context="Platt intercept")
        else:
            if not isinstance(parameters, Mapping) or set(parameters) != {
                "out_of_bounds",
                "x_thresholds",
                "y_thresholds",
            } or parameters.get("out_of_bounds") != "clip":
                raise FinalCalibrationError("E0-MCAL isotonic parameters drifted")
            x = parameters.get("x_thresholds")
            y = parameters.get("y_thresholds")
            if (
                not isinstance(x, list)
                or not isinstance(y, list)
                or len(x) != len(y)
                or len(x) < 2
            ):
                raise FinalCalibrationError("E0-MCAL isotonic thresholds drifted")
            x_values = [
                _json_float(item, context="isotonic x threshold") for item in x
            ]
            y_values = [
                _json_float(item, context="isotonic y threshold") for item in y
            ]
            if (
                any(left >= right for left, right in zip(x_values, x_values[1:]))
                or any(left > right for left, right in zip(y_values, y_values[1:]))
                or any(not 0.0 <= item <= 1.0 for item in (*x_values, *y_values))
            ):
                raise FinalCalibrationError("E0-MCAL isotonic monotonicity drifted")
    if observed_keys != expected_keys or len(indexed) != BLOOM_GROUP_COUNT:
        raise FinalCalibrationError("E0-MCAL bloom calibrator group order drifted")

    expected_q_c_keys = [
        (*identity, level)
        for identity in _calibration_group_keys(UNCERTAINTY_MODEL_IDS)
        for level in Q_C_LEVELS
    ]
    observed_q_c_keys: list[tuple[str, int, int, float]] = []
    expected_ranks = {0.80: 180, 0.90: 203, 0.95: 214}
    for record in q_c_records:
        if not isinstance(record, Mapping) or set(record) != {
            "model_id",
            "model_seed",
            "horizon_months",
            "coverage_level",
            "status",
            "finite_rows",
            "q_c",
            "order_statistic_rank",
            "calibration_year",
        }:
            raise FinalCalibrationError("E0-MCAL q_c record dialect drifted")
        model_id = record.get("model_id")
        model_seed = record.get("model_seed")
        horizon = record.get("horizon_months")
        level = record.get("coverage_level")
        if (
            not isinstance(model_id, str)
            or type(model_seed) is not int
            or type(horizon) is not int
            or type(level) is not float
        ):
            raise FinalCalibrationError("E0-MCAL q_c identity drifted")
        observed_q_c_keys.append((model_id, model_seed, horizon, level))
        q_c = _json_float(record.get("q_c"), context="q_c")
        if (
            level not in Q_C_LEVELS
            or record.get("status") != "completed"
            or type(record.get("finite_rows")) is not int
            or record.get("finite_rows") != 224
            or type(record.get("order_statistic_rank")) is not int
            or record.get("order_statistic_rank") != expected_ranks[level]
            or type(record.get("calibration_year")) is not int
            or record.get("calibration_year") != 2021
            or q_c < 0.0
        ):
            raise FinalCalibrationError("E0-MCAL q_c semantics drifted")
    if observed_q_c_keys != expected_q_c_keys:
        raise FinalCalibrationError("E0-MCAL q_c group order drifted")
    return indexed


def _validate_calibration_csv_outputs(
    payloads: Mapping[Path, bytes],
    *,
    calibrators: Mapping[tuple[str, int, int], Mapping[str, Any]],
) -> None:
    identity_columns = ("model_id", "model_seed", "horizon_months")
    expected_bloom_keys = _calibration_group_keys()
    metrics = _parse_closed_csv(
        payloads[CALIBRATION_METRICS_PATH],
        expected_header=(
            *identity_columns,
            "selected_method",
            "selection_brier",
            "selection_ece10",
            "calibration_brier",
            "calibration_ece10",
            "calibration_rows",
        ),
        expected_row_count=66,
        context="calibration metrics",
    )
    thresholds = _parse_closed_csv(
        payloads[ALERT_THRESHOLDS_PATH],
        expected_header=(
            *identity_columns,
            "threshold",
            "f2",
            "recall",
            "precision",
            "selection_year",
        ),
        expected_row_count=66,
        context="alert thresholds",
    )

    def identity(row: Mapping[str, str], *, context: str) -> tuple[str, int, int]:
        return (
            row["model_id"],
            _csv_integer(row["model_seed"], context=f"{context} model seed"),
            _csv_integer(row["horizon_months"], context=f"{context} horizon"),
        )

    if [identity(row, context="metrics") for row in metrics] != expected_bloom_keys:
        raise FinalCalibrationError("E0-MCAL calibration metrics keys drifted")
    if [identity(row, context="threshold") for row in thresholds] != expected_bloom_keys:
        raise FinalCalibrationError("E0-MCAL alert threshold keys drifted")
    for row in metrics:
        key = identity(row, context="metrics")
        calibrator = calibrators[key]
        if row["selected_method"] != calibrator["selected_method"]:
            raise FinalCalibrationError("E0-MCAL metrics method binding drifted")
        candidate = next(
            item
            for item in cast(list[Mapping[str, Any]], calibrator["selection_candidates"])
            if item["method"] == row["selected_method"]
        )
        selection_brier = _csv_float(
            row["selection_brier"], context="selection Brier"
        )
        selection_ece = _csv_float(
            row["selection_ece10"], context="selection ECE"
        )
        calibration_brier = _csv_float(
            row["calibration_brier"], context="calibration Brier"
        )
        calibration_ece = _csv_float(
            row["calibration_ece10"], context="calibration ECE"
        )
        if (
            selection_brier != candidate["brier"]
            or selection_ece != candidate["ece10"]
            or any(
                not 0.0 <= value <= 1.0
                for value in (
                    selection_brier,
                    selection_ece,
                    calibration_brier,
                    calibration_ece,
                )
            )
            or _csv_integer(row["calibration_rows"], context="calibration rows")
            != 224
        ):
            raise FinalCalibrationError("E0-MCAL calibration metrics semantics drifted")
    for row in thresholds:
        values = [
            _csv_float(row[column], context=f"threshold {column}")
            for column in ("threshold", "f2", "recall", "precision")
        ]
        _, f2, recall, precision = values
        denominator = 4.0 * precision + recall
        expected_f2 = (
            5.0 * precision * recall / denominator if denominator else 0.0
        )
        if (
            any(not 0.0 <= value <= 1.0 for value in values)
            or f2 != expected_f2
            or _csv_integer(row["selection_year"], context="threshold year") != 2021
        ):
            raise FinalCalibrationError("E0-MCAL threshold semantics drifted")

    ordinal = _parse_closed_csv(
        payloads[ORDINAL_CUTPOINTS_PATH],
        expected_header=(
            *identity_columns,
            "status",
            "cutpoints",
            "macro_f1",
            "ordinal_mae",
            "selection_year",
        ),
        expected_row_count=33,
        context="ordinal cutpoints",
    )
    expected_ordinal_keys = _calibration_group_keys(ORDINAL_MODEL_IDS)
    if [identity(row, context="ordinal") for row in ordinal] != expected_ordinal_keys:
        raise FinalCalibrationError("E0-MCAL ordinal keys drifted")
    for row in ordinal:
        key = identity(row, context="ordinal")
        if _csv_integer(row["selection_year"], context="ordinal year") != 2021:
            raise FinalCalibrationError("E0-MCAL ordinal year drifted")
        if key[0] == "B0":
            if (
                row["status"] != "not_available_degenerate_constant_score"
                or any(row[column] != "" for column in ("cutpoints", "macro_f1", "ordinal_mae"))
            ):
                raise FinalCalibrationError("E0-MCAL B0 ordinal record drifted")
            continue
        if row["status"] != "completed":
            raise FinalCalibrationError("E0-MCAL completed ordinal status drifted")
        try:
            cutpoints = json.loads(row["cutpoints"])
        except json.JSONDecodeError as exc:
            raise FinalCalibrationError("E0-MCAL ordinal cutpoints are malformed") from exc
        if (
            not isinstance(cutpoints, list)
            or len(cutpoints) != 3
            or row["cutpoints"] != json.dumps(cutpoints)
            or any(type(value) is not float or not math.isfinite(value) for value in cutpoints)
            or any(left >= right for left, right in zip(cutpoints, cutpoints[1:]))
            or any(not 0.0 <= value <= 1.0 for value in cutpoints)
        ):
            raise FinalCalibrationError("E0-MCAL ordinal cutpoint semantics drifted")
        macro_f1 = _csv_float(row["macro_f1"], context="ordinal macro F1")
        ordinal_mae = _csv_float(row["ordinal_mae"], context="ordinal MAE")
        if not 0.0 <= macro_f1 <= 1.0 or not 0.0 <= ordinal_mae <= 3.0:
            raise FinalCalibrationError("E0-MCAL ordinal metric range drifted")

    availability = _parse_closed_csv(
        payloads[MODEL_AVAILABILITY_PATH],
        expected_header=tuple(_expected_model_records()[0]),
        expected_row_count=MODEL_COUNT,
        context="model availability",
    )
    availability_records: list[dict[str, Any]] = []
    for row in availability:
        try:
            seeds = json.loads(row["seeds"])
            horizons = json.loads(row["horizons_months"])
        except json.JSONDecodeError as exc:
            raise FinalCalibrationError(
                "E0-MCAL availability list is malformed"
            ) from exc
        if (
            row["seeds"] != json.dumps(seeds)
            or row["horizons_months"] != json.dumps(horizons)
            or row["selected_family"] not in {"True", "False"}
        ):
            raise FinalCalibrationError("E0-MCAL availability CSV dialect drifted")
        availability_records.append(
            {
                **row,
                "selected_family": row["selected_family"] == "True",
                "seeds": seeds,
                "horizons_months": horizons,
            }
        )
    if availability_records != _expected_model_records():
        raise FinalCalibrationError("E0-MCAL availability matrix drifted")


def _validate_calibration_filter_evidence(value: Any) -> None:
    if not isinstance(value, list) or len(value) != 5:
        raise FinalCalibrationError(
            "E0-MCAL calibration filter evidence cardinality drifted"
        )
    target = value[0]
    target_keys = {
        "role",
        "scanner",
        "predicate",
        "materialized_row_count",
        "minimum_origin_year_month",
        "maximum_origin_year_month",
        "minimum_target_year_month",
        "maximum_target_year_month",
        "boundary_crossing_rows",
        "holdout_rows_materialized",
        "development_site_count",
        "development_site_ids_sha256",
    }
    if (
        not isinstance(target, Mapping)
        or set(target) != target_keys
        or target.get("role") != "target_predicate_scan"
        or target.get("scanner")
        != "pyarrow_dataset_anchored_fd_predicate_pushdown"
        or target.get("predicate")
        != (
            "source_id=wqp AND site_id IN development AND "
            "origin<=2021-12 AND 2019-01<=target<=2021-12"
        )
        or target.get("materialized_row_count") != 2646
        or target.get("minimum_origin_year_month") != "2018-10"
        or target.get("maximum_origin_year_month") != "2021-11"
        or target.get("minimum_target_year_month") != "2019-01"
        or target.get("maximum_target_year_month") != "2021-12"
        or target.get("boundary_crossing_rows") != 0
        or target.get("holdout_rows_materialized") != 0
        or type(target.get("development_site_count")) is not int
        or cast(int, target["development_site_count"]) <= 0
        or SHA256_RE.fullmatch(str(target.get("development_site_ids_sha256")))
        is None
    ):
        raise FinalCalibrationError("E0-MCAL target filter evidence drifted")
    expected = (
        (
            "B0",
            "data/closure_v1/development/baselines/B0/raw_scores.parquet",
            2931,
            2646,
            285,
        ),
        (
            "B1",
            "data/closure_v1/development/baselines/B1/raw_scores.parquet",
            14655,
            13230,
            1425,
        ),
        (
            "B2",
            "data/closure_v1/development/baselines/B2/raw_scores.parquet",
            14655,
            13230,
            1425,
        ),
        (
            "M0",
            "data/closure_v1/development/mifal/M0/raw_scores.parquet",
            2931,
            2646,
            285,
        ),
    )
    record_keys = {
        "model_id",
        "source_path",
        "candidate_row_count",
        "matched_target_row_count",
        "excluded_incomplete_target_row_count",
        "excluded_target_keys_sha256",
    }
    for record, (model_id, path, candidate, matched, excluded) in zip(
        value[1:], expected, strict=True
    ):
        if (
            not isinstance(record, Mapping)
            or set(record) != record_keys
            or record.get("model_id") != model_id
            or record.get("source_path") != path
            or record.get("candidate_row_count") != candidate
            or record.get("matched_target_row_count") != matched
            or record.get("excluded_incomplete_target_row_count") != excluded
            or candidate != matched + excluded
            or SHA256_RE.fullmatch(
                str(record.get("excluded_target_keys_sha256"))
            )
            is None
        ):
            raise FinalCalibrationError(
                f"E0-MCAL raw exclusion evidence drifted: {model_id}"
            )


def _validate_e7_csv_output(
    payload: bytes, *, terminal_evidence: Mapping[str, Any]
) -> None:
    module_tokens = ("anfis_n", "anfis_f", "anfis_t_no_current")
    module_columns = tuple(
        f"{token}_{field}"
        for token in module_tokens
        for field in (
            "final_checkpoint_loss",
            "rule_count",
            "epochs",
            "quality_gate_output_standard_deviation",
            "maximum_parameter_delta",
            "centers_ordered",
            "centers_in_unit_interval",
            "selected_keys_sha256",
            "computational_cost_proxy",
            "quality_gate_output_scope",
        )
    )
    rows = _parse_closed_csv(
        payload,
        expected_header=(
            "training_rows_per_module",
            "base_seed",
            "status",
            "completed_module_fit_count",
            "resource_limitation",
            "resource_failure_timing",
            "downstream_metrics_status",
            "saturation_claim_authorized",
            *module_columns,
        ),
        expected_row_count=15,
        context="E7 learning curve",
    )
    expected_slots = [
        (size, seed)
        for size in (4096, 16384, 65536)
        for seed in REGISTERED_SEEDS
    ]
    observed_slots = [
        (
            _csv_integer(row["training_rows_per_module"], context="E7 size"),
            _csv_integer(row["base_seed"], context="E7 seed"),
        )
        for row in rows
    ]
    if observed_slots != expected_slots:
        raise FinalCalibrationError("E0-MCAL E7 CSV slot order drifted")
    for index, row in enumerate(rows):
        size, _ = observed_slots[index]
        completed = size == 4096
        if (
            row["status"]
            != ("completed" if completed else "resource_failure_recorded")
            or _csv_integer(
                row["completed_module_fit_count"], context="E7 module fit count"
            )
            != (3 if completed else 0)
            or row["downstream_metrics_status"]
            != "not_estimable_without_separate_temporal_consumers"
            or row["saturation_claim_authorized"] != "False"
        ):
            raise FinalCalibrationError("E0-MCAL E7 row status drifted")
        if completed:
            if row["resource_limitation"] or row["resource_failure_timing"]:
                raise FinalCalibrationError("E0-MCAL E7 completed row limitation drifted")
            for token in module_tokens:
                loss = _csv_float(
                    row[f"{token}_final_checkpoint_loss"], context="E7 loss"
                )
                rules = _csv_integer(
                    row[f"{token}_rule_count"], context="E7 rule count"
                )
                epochs = _csv_integer(
                    row[f"{token}_epochs"], context="E7 epoch count"
                )
                deviation = _csv_float(
                    row[f"{token}_quality_gate_output_standard_deviation"],
                    context="E7 output deviation",
                )
                delta = _csv_float(
                    row[f"{token}_maximum_parameter_delta"],
                    context="E7 parameter delta",
                )
                cost = _csv_integer(
                    row[f"{token}_computational_cost_proxy"], context="E7 cost"
                )
                if (
                    loss < 0.0
                    or rules <= 0
                    or epochs <= 0
                    or deviation < 0.0
                    or delta < 0.0
                    or row[f"{token}_centers_ordered"] != "True"
                    or row[f"{token}_centers_in_unit_interval"] != "True"
                    or SHA256_RE.fullmatch(row[f"{token}_selected_keys_sha256"])
                    is None
                    or cost != size * rules * epochs
                    or row[f"{token}_quality_gate_output_scope"]
                    != f"e7_stratified_training_sample_{size}"
                ):
                    raise FinalCalibrationError("E0-MCAL E7 module evidence drifted")
        elif (
            row["resource_limitation"]
            != " | ".join(
                f"{module}: E7 candidate universe has {eligible_rows} rows; "
                f"{size} are required"
                for module, eligible_rows in (
                    ("ANFIS-N", 4757),
                    ("ANFIS-F", 35273),
                    ("ANFIS-T-no-current", 35419),
                )
                if size > eligible_rows
            )
            or row["resource_failure_timing"]
            != "pre_fit_exact_eligibility_check"
            or any(row[column] != "" for column in module_columns)
        ):
            raise FinalCalibrationError("E0-MCAL E7 resource limitation drifted")
    expected_evidence_keys = {
        "experiment_id",
        "terminal_row_count",
        "completed_slot_count",
        "resource_failure_count",
        "completed_module_fit_count",
        "new_e7_fit_count",
        "primary_fit_reuse_count",
        "primary_slots_untouched",
        "sample_evidence",
        "execution_policy",
        "silent_omission",
        "post_hoc_substitution_performed",
        "saturation_claim_authorized",
    }
    sample_evidence = terminal_evidence.get("sample_evidence")
    if (
        set(terminal_evidence) != expected_evidence_keys
        or terminal_evidence.get("experiment_id") != "E7"
        or not isinstance(sample_evidence, list)
        or len(sample_evidence) != 45
    ):
        raise FinalCalibrationError("E0-MCAL E7 terminal evidence dialect drifted")
    modules = ("ANFIS-N", "ANFIS-F", "ANFIS-T-no-current")
    eligible = {"ANFIS-N": 4757, "ANFIS-F": 35273, "ANFIS-T-no-current": 35419}
    expected_preflights = [
        (size, seed, module)
        for size, seed in expected_slots
        for module in modules
    ]
    observed_preflights: list[tuple[int, int, str]] = []
    module_seed_offsets = {
        "ANFIS-N": 101,
        "ANFIS-F": 202,
        "ANFIS-T-no-current": 404,
    }
    success_keys = {
        "module",
        "base_seed",
        "training_size",
        "input_rows",
        "eligible_rows",
        "eligible_universe_rows",
        "eligible_universe_sha256",
        "selected_rows",
        "selected_row_count",
        "selected_keys_sha256",
        "sampling_strata",
        "stratum_count",
        "strata",
        "strata_sha256",
        "strata_derivation",
        "month_period_map",
        "month_period_map_sha256",
        "replacement",
        "replacement_used",
        "module_seed",
    }
    resource_keys = {
        "module",
        "base_seed",
        "training_size",
        "status",
        "reason",
        "eligible_rows",
    }
    for record in sample_evidence:
        if not isinstance(record, Mapping):
            raise FinalCalibrationError("E0-MCAL E7 sample evidence is malformed")
        size = record.get("training_size")
        seed = record.get("base_seed")
        module = record.get("module")
        if (
            type(size) is not int
            or type(seed) is not int
            or not isinstance(module, str)
            or record.get("eligible_rows") != eligible.get(module)
        ):
            raise FinalCalibrationError("E0-MCAL E7 sample evidence identity drifted")
        observed_preflights.append((size, seed, module))
        if size <= eligible[module]:
            if (
                set(record) != success_keys
                or record.get("input_rows") != eligible[module]
                or record.get("eligible_universe_rows") != eligible[module]
                or SHA256_RE.fullmatch(
                    str(record.get("eligible_universe_sha256"))
                )
                is None
                or record.get("selected_rows") != size
                or record.get("selected_row_count") != size
                or SHA256_RE.fullmatch(str(record.get("selected_keys_sha256"))) is None
                or record.get("replacement_used") is not False
                or record.get("replacement") is not False
                or record.get("sampling_strata")
                != ["holdout_group_id", "temporal_period", "expert_anchor_band"]
                or record.get("module_seed") != seed + module_seed_offsets[module]
            ):
                raise FinalCalibrationError("E0-MCAL E7 selected sample drifted")
            strata = record.get("strata")
            stratum_count = record.get("stratum_count")
            if (
                not isinstance(strata, list)
                or type(stratum_count) is not int
                or stratum_count <= 0
                or len(strata) != stratum_count
            ):
                raise FinalCalibrationError("E0-MCAL E7 stratum records drifted")
            previous_key: tuple[str, str, str] | None = None
            eligible_sum = 0
            selected_sum = 0
            for stratum in strata:
                if not isinstance(stratum, Mapping) or set(stratum) != {
                    "holdout_group_id",
                    "temporal_period",
                    "expert_anchor_band",
                    "eligible_rows",
                    "selected_rows",
                }:
                    raise FinalCalibrationError("E0-MCAL E7 stratum dialect drifted")
                group = stratum.get("holdout_group_id")
                period = stratum.get("temporal_period")
                band = stratum.get("expert_anchor_band")
                eligible_rows = stratum.get("eligible_rows")
                selected_rows = stratum.get("selected_rows")
                if (
                    not isinstance(group, str)
                    or not group.startswith("wqp::")
                    or group == "wqp::"
                    or period not in {"early", "middle", "late"}
                    or band not in {"low", "middle", "high"}
                    or type(eligible_rows) is not int
                    or type(selected_rows) is not int
                    or eligible_rows <= 0
                    or selected_rows < 0
                    or selected_rows > eligible_rows
                ):
                    raise FinalCalibrationError("E0-MCAL E7 stratum semantics drifted")
                stratum_key = (group, cast(str, period), cast(str, band))
                if previous_key is not None and stratum_key <= previous_key:
                    raise FinalCalibrationError("E0-MCAL E7 stratum order drifted")
                previous_key = stratum_key
                eligible_sum += eligible_rows
                selected_sum += selected_rows
            if (
                eligible_sum != eligible[module]
                or selected_sum != size
                or record.get("strata_sha256")
                != _sha256_bytes(_canonical_json_bytes({"records": strata}))
            ):
                raise FinalCalibrationError("E0-MCAL E7 stratum digest drifted")
            month_map = record.get("month_period_map")
            derivation = record.get("strata_derivation")
            if (
                not isinstance(month_map, Mapping)
                or not month_map
                or list(month_map) != sorted(month_map)
                or not isinstance(derivation, Mapping)
                or set(derivation) != {
                    "holdout_group_rule",
                    "month_period_map",
                    "month_period_map_sha256",
                    "expert_anchor_band_cuts",
                    "expert_anchor_band_labels",
                }
                or derivation.get("holdout_group_rule") != "source_id::site_id"
                or derivation.get("month_period_map") != month_map
                or derivation.get("expert_anchor_band_cuts")
                != [0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0]
                or derivation.get("expert_anchor_band_labels")
                != ["low", "middle", "high"]
            ):
                raise FinalCalibrationError("E0-MCAL E7 strata derivation drifted")
            months = list(month_map)
            if any(
                not isinstance(month, str)
                or re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month) is None
                for month in months
            ):
                raise FinalCalibrationError("E0-MCAL E7 month key drifted")
            month_names = cast(list[str], months)
            expected_periods = {
                month: ("early", "middle", "late")[
                    min(2, (3 * index) // len(month_names))
                ]
                for index, month in enumerate(month_names)
            }
            month_digest = _sha256_bytes(
                _canonical_json_bytes({"month_period_map": expected_periods})
            )
            if (
                dict(month_map) != expected_periods
                or record.get("month_period_map_sha256") != month_digest
                or derivation.get("month_period_map_sha256") != month_digest
            ):
                raise FinalCalibrationError("E0-MCAL E7 month strata map drifted")
        elif (
            set(record) != resource_keys
            or record.get("status") != "resource_failure_recorded"
            or record.get("reason")
            != f"E7 candidate universe has {eligible[module]} rows; {size} are required"
        ):
            raise FinalCalibrationError("E0-MCAL E7 pre-fit failure evidence drifted")
    if observed_preflights != expected_preflights:
        raise FinalCalibrationError("E0-MCAL E7 preflight order drifted")


def _validate_torch_cpu_execution_policy(value: Any, *, context: str) -> None:
    if value != {
        "device": "cpu",
        "torch_num_threads": 1,
        "torch_num_interop_threads": 1,
        "blas_thread_environment_control": "not_locked_by_e0_dl_v1",
        "bitwise_reproducibility_claim": (
            "forbidden_across_processes_or_blas_backends"
        ),
        "torch_num_threads_observed": 1,
        "torch_num_interop_threads_observed": 1,
    }:
        raise FinalCalibrationError(
            f"E0-MCAL {context} Torch CPU execution policy drifted"
        )


def _require_exact_output_group(
    paths: Sequence[Path], *, manifest_path: Path, repo_root: Path, context: str
) -> int:
    present = [path for path in paths if _entry_exists(path, repo_root=repo_root)]
    if present and len(present) != len(paths):
        raise FinalCalibrationError(f"E0-MCAL {context} output bundle is partial")
    if not present:
        return 0
    payloads: dict[Path, bytes] = {}
    metadata: dict[Path, os.stat_result] = {}
    json_values: dict[Path, Any] = {}
    for path in paths:
        payload, observed_metadata = _read_regular_bytes_and_metadata(
            path, repo_root=repo_root
        )
        payloads[path] = payload
        metadata[path] = observed_metadata
        if path.suffix == ".json":
            value = _parse_json_bytes(payload, context=path.as_posix())
            if payload != _canonical_json_bytes(value):
                raise FinalCalibrationError(
                    f"E0-MCAL {context} JSON output is not canonical: {path.as_posix()}"
                )
            json_values[path] = value
    manifest = json_values.get(manifest_path)
    if not isinstance(manifest, Mapping):
        raise FinalCalibrationError(f"E0-MCAL {context} manifest is absent")
    output_records = [
        {
            "path": path.as_posix(),
            "bytes": len(payloads[path]),
            "sha256": _sha256_bytes(payloads[path]),
        }
        for path in paths
        if path != manifest_path
    ]
    if manifest.get("outputs") != output_records:
        raise FinalCalibrationError(
            f"E0-MCAL {context} manifest output bindings drifted"
        )
    inventory = _scientific_input_inventory(repo_root=repo_root)
    expected_authority_sha256 = _effective_authority_binding_sha256(
        repo_root=repo_root, scientific_inventory=inventory
    )
    common_boundary = {
        "development_only": True,
        "holdout_accessed": False,
        "post_2021_rows_accessed": False,
        "final_evaluation_run": False,
        "future_outcomes_accessed": False,
    }
    if context == "calibration":
        expected_keys = {
            "schema_version",
            "experiment_id",
            "gate",
            "status",
            "authority_sha256",
            "group_counts",
            "temporal_protocol",
            "inputs",
            "input_filter_evidence",
            "execution_policy",
            "outputs",
            "scientific_boundary",
        }
        if (
            set(manifest) != expected_keys
            or manifest.get("schema_version")
            != "closure_final_calibration_manifest_v1"
            or manifest.get("experiment_id") != EXPERIMENT_ID
            or manifest.get("gate") != PATCH_GATE
            or manifest.get("status") != "completed_unpublished"
            or manifest.get("group_counts")
            != {"bloom": 66, "ordinal": 33, "uncertainty": 30, "q_c": 90}
            or manifest.get("temporal_protocol")
            != {
                "fit": "2019",
                "assessment": "2020",
                "refit_threshold_cutpoint_q_c": "2021",
                "time_column": "target_year_month",
            }
            or manifest.get("inputs") != inventory["calibration_required_inputs"]
            or manifest.get("scientific_boundary") != common_boundary
            or manifest.get("authority_sha256") != expected_authority_sha256
            or not isinstance(manifest.get("execution_policy"), Mapping)
        ):
            raise FinalCalibrationError(
                "E0-MCAL calibration manifest scientific dialect drifted"
            )
        evidence = manifest.get("input_filter_evidence")
        if not isinstance(evidence, list):
            raise FinalCalibrationError(
                "E0-MCAL calibration input-filter evidence is absent"
            )
        _validate_calibration_filter_evidence(evidence)
        target_evidence = [
            record
            for record in evidence
            if isinstance(record, Mapping)
            and record.get("role") == "target_predicate_scan"
        ]
        if len(target_evidence) != 1 or (
            target_evidence[0].get("scanner")
            != "pyarrow_dataset_anchored_fd_predicate_pushdown"
            or target_evidence[0].get("predicate")
            != (
                "source_id=wqp AND site_id IN development AND "
                "origin<=2021-12 AND 2019-01<=target<=2021-12"
            )
            or target_evidence[0].get("boundary_crossing_rows") != 0
            or target_evidence[0].get("holdout_rows_materialized") != 0
            or str(target_evidence[0].get("maximum_origin_year_month")) > "2021-12"
            or str(target_evidence[0].get("maximum_target_year_month")) > "2021-12"
        ):
            raise FinalCalibrationError(
                "E0-MCAL target predicate scan evidence drifted"
            )
        execution_policy = cast(Mapping[str, Any], manifest["execution_policy"])
        if set(execution_policy) != {
            "torch_cpu_execution_policy",
            "development_runtime_schema_version",
            "development_runtime_audit_sha256",
            "threadpool_limit",
        } or execution_policy.get("threadpool_limit") != 1 or execution_policy.get(
            "development_runtime_schema_version"
        ) != EXPECTED_DEVELOPMENT_RUNTIME_SCHEMA_VERSION or execution_policy.get(
            "development_runtime_audit_sha256"
        ) != EXPECTED_DEVELOPMENT_RUNTIME_AUDIT_SHA256:
            raise FinalCalibrationError(
                "E0-MCAL calibration execution policy drifted"
            )
        _validate_torch_cpu_execution_policy(
            execution_policy.get("torch_cpu_execution_policy"),
            context="calibration",
        )
        calibrators = _validate_calibrator_specs(
            json_values.get(CALIBRATOR_SPECS_PATH)
        )
        _validate_calibration_csv_outputs(
            payloads, calibrators=calibrators
        )
    elif context == "E7":
        expected_keys = {
            "schema_version",
            "experiment_id",
            "gate",
            "status",
            "authority_sha256",
            "terminal_row_count",
            "completed_slot_count",
            "resource_failure_count",
            "completed_module_fit_count",
            "new_e7_fit_count",
            "primary_fit_reuse_count",
            "primary_slots_untouched",
            "saturation_claim_authorized",
            "post_hoc_substitution_performed",
            "silent_omission",
            "slot_order",
            "terminal_evidence",
            "inputs",
            "outputs",
            "scientific_boundary",
        }
        expected_slot_order = [
            {"training_rows_per_module": size, "base_seed": seed}
            for size in (4096, 16384, 65536)
            for seed in REGISTERED_SEEDS
        ]
        expected_terminal = {
            "terminal_row_count": 15,
            "completed_slot_count": 5,
            "resource_failure_count": 10,
            "completed_module_fit_count": 15,
            "new_e7_fit_count": 15,
            "primary_fit_reuse_count": 0,
            "primary_slots_untouched": True,
            "saturation_claim_authorized": False,
            "post_hoc_substitution_performed": False,
            "silent_omission": False,
        }
        if (
            set(manifest) != expected_keys
            or manifest.get("schema_version")
            != "closure_anfis_learning_curve_manifest_v1"
            or manifest.get("experiment_id") != "E7"
            or manifest.get("gate") != PATCH_GATE
            or manifest.get("status") != "terminal"
            or any(manifest.get(key) != value for key, value in expected_terminal.items())
            or manifest.get("slot_order") != expected_slot_order
            or manifest.get("inputs") != inventory["e7_required_inputs"]
            or manifest.get("scientific_boundary") != common_boundary
            or manifest.get("authority_sha256") != expected_authority_sha256
            or not isinstance(manifest.get("terminal_evidence"), Mapping)
        ):
            raise FinalCalibrationError(
                "E0-MCAL E7 manifest scientific dialect drifted"
            )
        terminal_evidence = cast(Mapping[str, Any], manifest["terminal_evidence"])
        if any(
            terminal_evidence.get(key) != value
            for key, value in expected_terminal.items()
        ) or not isinstance(terminal_evidence.get("sample_evidence"), list) or len(
            cast(list[Any], terminal_evidence["sample_evidence"])
        ) != 45:
            raise FinalCalibrationError("E0-MCAL E7 terminal evidence drifted")
        execution_policy = terminal_evidence.get("execution_policy")
        if not isinstance(execution_policy, Mapping) or set(execution_policy) != {
            "torch_cpu_execution_policy",
            "threadpool_limit",
        } or execution_policy.get("threadpool_limit") != 1:
            raise FinalCalibrationError("E0-MCAL E7 execution policy drifted")
        _validate_torch_cpu_execution_policy(
            execution_policy.get("torch_cpu_execution_policy"), context="E7"
        )
        _validate_e7_csv_output(
            payloads[ANFIS_LEARNING_CURVE_PATH],
            terminal_evidence=terminal_evidence,
        )
    else:
        raise FinalCalibrationError("E0-MCAL output group context drifted")
    if (
        metadata[manifest_path].st_mtime_ns
        <= max(
            value.st_mtime_ns
            for path, value in metadata.items()
            if path != manifest_path
        )
        or metadata[manifest_path].st_ctime_ns
        <= max(
            value.st_ctime_ns
            for path, value in metadata.items()
            if path != manifest_path
        )
    ):
        raise FinalCalibrationError(f"E0-MCAL {context} manifest-last order drifted")
    for path in paths:
        payload, observed_metadata = _read_regular_bytes_and_metadata(
            path, repo_root=repo_root
        )
        before = metadata[path]
        if payload != payloads[path] or (
            observed_metadata.st_dev,
            observed_metadata.st_ino,
            observed_metadata.st_mode,
            observed_metadata.st_nlink,
            observed_metadata.st_size,
            observed_metadata.st_mtime_ns,
            observed_metadata.st_ctime_ns,
        ) != (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ):
            raise FinalCalibrationError(
                f"E0-MCAL {context} output changed during validation"
            )
    return len(paths)


def _validate_effective_namespace(*, repo_root: Path) -> dict[str, Any]:
    forbidden = (
        _temporary_path(DEFAULT_PATCH_LOCK_PATH),
        _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        *( _temporary_path(path) for path in R_OUTPUT_PATHS ),
        LOCKER_GUARD_PATH,
        CALIBRATION_GUARD_PATH,
        E7_GUARD_PATH,
    )
    occupied = [
        path.as_posix() for path in forbidden if _entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise FinalCalibrationError(
            f"E0-MCAL effective coordination/temporary namespace is occupied: {occupied}"
        )
    if _entry_exists(Path(mze.OUTCOME_ACCESS_LOG), repo_root=repo_root):
        raise FinalCalibrationError("E0-MCAL outcome access log appeared")
    if any(_entry_exists(Path(path), repo_root=repo_root) for path in mze.E0_M_PATHS):
        raise FinalCalibrationError("E0-MCAL final E0-M outputs appeared")
    calibration_count = _require_exact_output_group(
        CALIBRATION_OUTPUT_PATHS,
        manifest_path=FINAL_CALIBRATION_MANIFEST_PATH,
        repo_root=repo_root,
        context="calibration",
    )
    e7_count = _require_exact_output_group(
        E7_OUTPUT_PATHS,
        manifest_path=ANFIS_LEARNING_CURVE_MANIFEST_PATH,
        repo_root=repo_root,
        context="E7",
    )
    if (calibration_count, e7_count) not in {(0, 0), (6, 0), (6, 2)}:
        raise FinalCalibrationError("E0-MCAL R bundle order drifted")
    lifecycle = {
        (0, 0): "ready_for_calibration_bundle",
        (6, 0): "calibration_completed_unpublished_ready_for_e7_bundle",
        (6, 2): "both_bundles_completed_unpublished",
    }[(calibration_count, e7_count)]
    return {
        "calibration_output_present_count": calibration_count,
        "e7_output_present_count": e7_count,
        "r_output_present_count": calibration_count + e7_count,
        "r_lifecycle_state": lifecycle,
    }


@_error_boundary
def require_final_calibration_run_namespace(
    *, runner: str, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    if type(runner) is not str or runner not in {"calibration", "e7"}:
        raise FinalCalibrationError(
            "E0-MCAL run namespace requires runner calibration or e7"
        )
    namespace = _validate_effective_namespace(repo_root=root)
    required_state = (
        "ready_for_calibration_bundle"
        if runner == "calibration"
        else "calibration_completed_unpublished_ready_for_e7_bundle"
    )
    if namespace["r_lifecycle_state"] != required_state:
        raise FinalCalibrationError(
            f"E0-MCAL {runner} one-shot namespace is not ready"
        )
    return {
        "gate": PATCH_GATE,
        "runner": runner,
        "status": "ready_before_scientific_io",
        "registration_execution_order": ["calibration_bundle", "e7_bundle"],
        **namespace,
        "own_bundle_present_count": 0,
        "temporary_present_count": 0,
        "coordination_present_count": 0,
        "rerun_allowed": False,
        "scientific_io_performed": False,
    }


def _validate_p_publication(
    payload: Mapping[str, Any], *, verify_remote: bool, repo_root: Path
) -> dict[str, str]:
    if type(verify_remote) is not bool:
        raise FinalCalibrationError("E0-MCAL remote policy must be an exact boolean")
    repository = cast(Mapping[str, Any], payload["repository"])
    h_head = cast(str, repository["h_patch_head"])
    head = _git_head(repo_root)
    if (
        cast(str, _git(repo_root, "branch", "--show-current")).strip() != "main"
        or _single_parent(repo_root, head, context="P-E0-MCAL") != h_head
        or _git_scope(repo_root, h_head, head)
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "path_count": 2,
            "paths": sorted(FINAL_CALIBRATION_P_STAGED_SCOPE),
        }
    ):
        raise FinalCalibrationError("E0-MCAL published P topology drifted")
    tracking = _git_head(repo_root, "origin/main")
    remote = _live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != head or remote != head:
        raise FinalCalibrationError("E0-MCAL published P refs drifted")
    for path in (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH):
        physical = _read_regular_bytes(path, repo_root=repo_root)
        mode, _ = _git_mode_oid(repo_root, head, path)
        if mode != "100644" or physical != _git_blob_bytes(repo_root, head, path):
            raise FinalCalibrationError(
                f"E0-MCAL published P physical/Git binding drifted: {path.as_posix()}"
            )
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


@_error_boundary
def load_effective_final_calibration_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    payload = _parse_canonical_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    _validate_published_lock_payload(payload, repo_root=root)
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH, role="final_calibration_lock", repo_root=root
    )
    companion = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    expected_companion = _expected_companion(payload, lock_record)
    if _canonical_json_bytes(companion) != _canonical_json_bytes(expected_companion):
        raise FinalCalibrationError("E0-MCAL published companion drifted")
    publication = _validate_p_publication(
        payload, verify_remote=verify_remote, repo_root=root
    )
    namespace = _validate_effective_namespace(repo_root=root)
    base = _base_r_mze_authority(repo_root=root)
    scientific_inventory = cast(
        Mapping[str, Any], payload["scientific_input_inventory"]
    )
    lifecycle = cast(str, namespace["r_lifecycle_state"])
    calibration_authorized = lifecycle == "ready_for_calibration_bundle"
    e7_authorized = (
        lifecycle == "calibration_completed_unpublished_ready_for_e7_bundle"
    )
    authority_binding_sha256 = _effective_authority_binding_sha256(
        repo_root=root,
        scientific_inventory=scientific_inventory,
        p_patch_head=publication["p_patch_head"],
        lock_record=lock_record,
    )
    return {
        "gate": PATCH_GATE,
        "status": "effective",
        **publication,
        "lock": lock_record,
        "companion": _file_record(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="final_calibration_lock_manifest",
            repo_root=root,
        ),
        "authority_binding_sha256": authority_binding_sha256,
        "scientific_input_inventory": _deep_copy(scientific_inventory),
        "calibration_required_inputs": _deep_copy(
            scientific_inventory["calibration_required_inputs"]
        ),
        "calibration_required_inputs_sha256": scientific_inventory[
            "calibration_required_inputs_sha256"
        ],
        "e7_required_inputs": _deep_copy(
            scientific_inventory["e7_required_inputs"]
        ),
        "e7_required_inputs_sha256": scientific_inventory[
            "e7_required_inputs_sha256"
        ],
        "model_ids": list(MODEL_IDS),
        "bloom_group_count": BLOOM_GROUP_COUNT,
        "ordinal_group_count": ORDINAL_GROUP_COUNT,
        "uncertainty_group_count": UNCERTAINTY_GROUP_COUNT,
        "q_c_levels": list(Q_C_LEVELS),
        "e7_training_rows_per_module": [4096, 16384, 65536],
        "e7_expected_completed_slot_count": 5,
        "e7_expected_completed_module_fit_count": 15,
        "e7_expected_resource_failure_record_count": 10,
        "historical_e7_blocker_adopted": True,
        "historical_e7_blockers": _historical_e7_blockers(repo_root=root),
        "e7_authority_correction": {
            "historical_blocker_count": 3,
            "historical_e7_blocker_adopted": True,
            "supersession_scope": "e7_only_additive_authority",
            "final_runtime_path": DEFAULT_RUNTIME_PATH.as_posix(),
        },
        "r_output_paths": [path.as_posix() for path in R_OUTPUT_PATHS],
        "family_final_count": base["family_final_count"],
        "family_records_sha256": base["family_records_sha256"],
        **namespace,
        "calibration_development_run_authorized": calibration_authorized,
        "e7_learning_curve_run_authorized": e7_authorized,
        "calibration_one_shot_consumed": not calibration_authorized,
        "e7_one_shot_consumed": lifecycle == "both_bundles_completed_unpublished",
        "r_outputs_ready_for_staging": lifecycle
        == "both_bundles_completed_unpublished",
        "holdout_access_authorized": False,
        "post_2021_access_authorized": False,
        "locked_evaluation_authorized": False,
        "outcome_access_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "dvc_push_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "scientific_network_authorized": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


@_error_boundary
def require_final_calibration_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return load_effective_final_calibration_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


__all__ = [
    "BASE_COMMIT",
    "BLOOM_GROUP_COUNT",
    "CALIBRATION_OUTPUT_PATHS",
    "CALIBRATION_REQUIRED_INPUT_COUNT",
    "DEFAULT_LOCK_SCHEMA",
    "DEFAULT_PATCH_LOCK_MANIFEST_PATH",
    "DEFAULT_PATCH_LOCK_PATH",
    "DEFAULT_RUNTIME_PATH",
    "DEFAULT_RUNTIME_SCHEMA",
    "DIFF_CHECK_COMMAND",
    "E7_OUTPUT_PATHS",
    "E7_REQUIRED_INPUT_COUNT",
    "EXPECTED_DEVELOPMENT_RUNTIME_AUDIT_SHA256",
    "EXPECTED_DEVELOPMENT_RUNTIME_SCHEMA_VERSION",
    "FINAL_CALIBRATION_GATE",
    "FINAL_CALIBRATION_H_STAGED_SCOPE",
    "FINAL_CALIBRATION_P_STAGED_SCOPE",
    "FINAL_CALIBRATION_R_STAGED_SCOPE",
    "FOCUSED_TEST_COMMAND",
    "FOCUSED_TEST_COUNT",
    "FinalCalibrationError",
    "MODEL_IDS",
    "ORDINAL_GROUP_COUNT",
    "PATCH_COMPONENT_GIT_MODES",
    "PATCH_COMPONENT_ROLES",
    "PATCH_GATE",
    "PATCH_PATHS",
    "POETRY_CHECK_COMMAND",
    "PUBLICATION_GUARD_COMMAND",
    "Q_C_LEVELS",
    "R_OUTPUT_PATHS",
    "SCIENTIFIC_AUTHORITY_RECORD_COUNT",
    "SCIENTIFIC_PAYLOAD_BINDING_COUNT",
    "TYPE_CHECK_COMMAND",
    "_canonical_json_bytes",
    "build_final_calibration_lock_payload",
    "collect_final_calibration_prelock_state",
    "execute_and_publish_final_calibration_lock_bundle",
    "load_and_validate_final_calibration_runtime",
    "load_effective_final_calibration_authority",
    "preflight_final_calibration_schema",
    "publish_final_calibration_lock_bundle",
    "require_final_calibration_authority",
    "require_final_calibration_run_namespace",
    "validate_final_calibration_lock_payload",
]
