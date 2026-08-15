#!/usr/bin/env python3
"""Close P0 model availability before any Closure V1 P1 materialization.

E0-MA is additive.  It does not mutate the sealed benchmark or analysis plan,
does not read evaluation outcomes, and does not authorize E0-M.  Check-only
mode is local and read-only.  Registry generation is a separately authorized,
manifest-last, two-file transaction whose result becomes effective only after
the strict post-publication loader passes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import (  # noqa: E402
    lock_closure_development_runtime_temporal_consumer_patch as hardened,
)
from src.experiments.closure_contract import validate_json_schema  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = Path("configs/closure_v1/model_lock_availability_policy.yaml")
DEFAULT_SCHEMA = Path("configs/closure_v1/model_lock_availability_policy.schema.json")
DEFAULT_REGISTRY = Path(
    "reports/closure_v1/00_protocol/p0_model_availability_registry.json"
)
DEFAULT_COMPANION = Path(
    "reports/closure_v1/00_protocol/p0_model_availability_registry_manifest.json"
)
DEFAULT_DOCUMENTATION = Path("docs/closure_v1/E0_M_MODEL_AVAILABILITY_POLICY.md")
DEFAULT_TEST = Path("tests/test_audit_closure_p0_model_availability.py")
DEFAULT_AUDITOR = Path("src/experiments/audit_closure_p0_model_availability.py")
HARDENED_WRITER = Path(
    "src/experiments/lock_closure_development_runtime_temporal_consumer_patch.py"
)
REGISTRY_GUARD_DIRECTORY = Path("tmp/closure_v1_e0_ma_registry")
REGISTRY_GUARD_PATHS = (
    REGISTRY_GUARD_DIRECTORY / "p0_model_availability_registry.guard",
    REGISTRY_GUARD_DIRECTORY / "p0_model_availability_registry_manifest.guard",
)

EXPECTED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
P0_CLOSURE_HEAD = "1a4aa4836548756e74008fb934f56b5251d22491"
EXPECTED_SUCCESS_COUNT = 8_925
EXPECTED_UNAVAILABLE_COUNT = 488
EXPECTED_INPUT_RECORDS = 23
EXPECTED_SOURCE_RECORDS = 10
EXPECTED_NAMESPACE_PATHS = 19
EXPECTED_PRESENT_PATHS = 2

P0_SEQUENCE_MANIFEST = Path(
    "reports/closure_v1/01_surface/sequences/P0/expert_no_current_manifest.json"
)
P0_SEQUENCE_SUMMARY = Path(
    "reports/closure_v1/01_surface/sequences/P0/expert_no_current_summary.csv"
)
OUTCOME_ACCESS_LOG = Path("reports/closure_v1/00_protocol/outcome_access_log.jsonl")
E0_M_OUTPUTS = (
    Path("reports/closure_v1/00_protocol/model_lock.yaml"),
    Path("reports/closure_v1/00_protocol/calibration_lock.yaml"),
    Path("reports/closure_v1/00_protocol/hypothesis_registry.csv"),
    Path("reports/closure_v1/00_protocol/locked_batch_command.txt"),
)
H_SLICE_COMPONENTS = (
    DEFAULT_POLICY,
    DEFAULT_SCHEMA,
    DEFAULT_AUDITOR,
    DEFAULT_DOCUMENTATION,
    DEFAULT_TEST,
)

MANIFEST_KEYS = {
    "manifest_version",
    "status",
    "slot_status",
    "fit_status",
    "failure_reason",
    "generated_at_utc",
    "experiment_id",
    "surface_id",
    "model_id",
    "base_seed",
    "device",
    "future_outcomes_accessed",
    "evaluation_authorized",
    "e0_u_authorized",
    "failed_slot_replaced",
    "replacement_used",
    "model_artifact_emitted",
    "fit_status_counts",
    "failure_reason_counts",
    "script",
    "cpu_execution_policy",
    "config",
    "input_state_mapping",
    "target_state_mapping",
    "target_to_next_input_mapping",
    "inputs",
    "source_code",
    "outputs",
    "completion_marker_written_last",
}


class P0ModelAvailabilityError(RuntimeError):
    """Raised when the additive availability gate fails closed."""


def _relative_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(PROJECT_ROOT)
        except ValueError as exc:
            raise P0ModelAvailabilityError(
                f"Path escapes the repository: {path}"
            ) from exc
    if not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise P0ModelAvailabilityError(f"Unsafe repository path: {path}")
    return candidate


def _absolute_repo_path(path: str | Path) -> Path:
    return PROJECT_ROOT / _relative_repo_path(path)


def _repo_path(path: str | Path) -> str:
    return _relative_repo_path(path).as_posix()


def _open_repository_root() -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(PROJECT_ROOT, flags)
    except OSError as exc:
        raise P0ModelAvailabilityError(
            "Repository root is unavailable or linked"
        ) from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise P0ModelAvailabilityError("Repository root is not a directory")
    return descriptor


def _open_repo_directory(
    relative: Path,
    *,
    context: str,
    missing_ok: bool = False,
) -> int | None:
    directory = _relative_repo_path(relative) if relative.parts else Path()
    descriptor = _open_repository_root()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        for component in directory.parts:
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if missing_ok:
                    os.close(descriptor)
                    return None
                raise P0ModelAvailabilityError(
                    f"Missing directory in {context}: {directory.as_posix()}"
                ) from None
            except OSError as exc:
                raise P0ModelAvailabilityError(
                    f"{context} contains a linked or invalid ancestor"
                ) from exc
            metadata = os.fstat(child)
            if not stat.S_ISDIR(metadata.st_mode):
                os.close(child)
                raise P0ModelAvailabilityError(
                    f"{context} contains a non-directory ancestor"
                )
            parent = descriptor
            descriptor = child
            os.close(parent)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _entry_metadata(path: str | Path) -> os.stat_result | None:
    relative = _relative_repo_path(path)
    parent = _open_repo_directory(
        relative.parent,
        context=f"entry parent for {relative.as_posix()}",
        missing_ok=True,
    )
    if parent is None:
        return None
    try:
        try:
            return os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return None
    finally:
        os.close(parent)


def _path_entry_exists(path: str | Path) -> bool:
    return _entry_metadata(path) is not None


def _secure_read_bytes(path: str | Path, *, context: str = "artifact") -> bytes:
    relative = _relative_repo_path(path)
    parent = _open_repo_directory(
        relative.parent,
        context=f"{context} parent",
        missing_ok=False,
    )
    assert parent is not None
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        try:
            descriptor = os.open(relative.name, flags, dir_fd=parent)
        except OSError as exc:
            raise P0ModelAvailabilityError(
                f"Missing, linked, or unreadable {context}: {relative.as_posix()}"
            ) from exc
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise P0ModelAvailabilityError(
                    f"{context} is not a regular file: {relative.as_posix()}"
                )
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
            after = os.fstat(descriptor)
            current = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
            before_identity = (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            after_identity = (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            current_identity = (
                current.st_dev,
                current.st_ino,
                current.st_mode,
                current.st_size,
                current.st_mtime_ns,
                current.st_ctime_ns,
            )
            if (
                before_identity != after_identity
                or before_identity != current_identity
                or not stat.S_ISREG(current.st_mode)
            ):
                raise P0ModelAvailabilityError(
                    f"{context} identity drifted while reading: {relative.as_posix()}"
                )
            payload = b"".join(chunks)
            if len(payload) != after.st_size:
                raise P0ModelAvailabilityError(
                    f"{context} size drifted while reading: {relative.as_posix()}"
                )
            return payload
        finally:
            os.close(descriptor)
    finally:
        os.close(parent)


def _file_record(path: str | Path) -> dict[str, Any]:
    relative = _relative_repo_path(path)
    payload = _secure_read_bytes(relative)
    return {
        "path": relative.as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


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


def _records_digest(records: Sequence[Mapping[str, Any]]) -> str:
    encoded = json.dumps(
        list(records),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_git(*arguments: str, binary: bool = False) -> str | bytes:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=not binary,
    )
    if result.returncode != 0:
        operation = " ".join(arguments)
        raise P0ModelAvailabilityError(
            f"Bounded Git command failed: {operation} (exit {result.returncode})"
        )
    if binary:
        return cast(bytes, result.stdout)
    return cast(str, result.stdout).strip()


def _git(*arguments: str) -> str:
    return cast(str, _run_git(*arguments))


def _git_bytes(*arguments: str) -> bytes:
    return cast(bytes, _run_git(*arguments, binary=True))


def _require_exact_commit(commit: str) -> None:
    if _git("rev-parse", "--verify", f"{commit}^{{commit}}") != commit:
        raise P0ModelAvailabilityError(f"Git commit identity drifted: {commit}")


def _commit_parent(commit: str) -> str:
    _require_exact_commit(commit)
    lineage = _git("rev-list", "--parents", "-n", "1", commit).split()
    if len(lineage) != 2 or lineage[0] != commit:
        raise P0ModelAvailabilityError(
            f"Commit must have exactly one parent: {commit}"
        )
    return lineage[1]


def _commit_additions(commit: str) -> list[dict[str, str]]:
    output = _git("diff-tree", "--root", "--no-commit-id", "--name-status", "-r", commit)
    records: list[dict[str, str]] = []
    if not output:
        return records
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] != "A":
            raise P0ModelAvailabilityError(
                f"Commit {commit} is not an additions-only bundle: {line}"
            )
        records.append({"status": fields[0], "path": fields[1]})
    return records


def _git_blob_record(commit: str, path: str | Path) -> dict[str, Any]:
    relative = _relative_repo_path(path)
    _require_exact_commit(commit)
    tree = _git("ls-tree", commit, "--", relative.as_posix())
    lines = tree.splitlines()
    if len(lines) != 1 or "\t" not in lines[0]:
        raise P0ModelAvailabilityError(
            f"Git blob is missing at {commit}:{relative.as_posix()}"
        )
    metadata, observed_path = lines[0].split("\t", 1)
    fields = metadata.split()
    if len(fields) != 3 or fields[0] != "100644" or fields[1] != "blob":
        raise P0ModelAvailabilityError(
            f"Git entry is not a regular 100644 blob: {commit}:{relative.as_posix()}"
        )
    if observed_path != relative.as_posix():
        raise P0ModelAvailabilityError("Git blob path drifted")
    payload = _git_bytes("show", f"{commit}:{relative.as_posix()}")
    return {
        "path": relative.as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "git_commit": commit,
        "git_blob": fields[2],
        "git_mode": fields[0],
    }


def _git_bound_record(commit: str, path: str | Path) -> dict[str, Any]:
    physical = _file_record(path)
    git_record = _git_blob_record(commit, path)
    if physical != {key: git_record[key] for key in ("path", "bytes", "sha256")}:
        raise P0ModelAvailabilityError(
            f"Physical artifact differs from Git authority: {physical['path']}"
        )
    return git_record


def _generic_record(record: Mapping[str, Any], *, role: str | None = None) -> dict[str, Any]:
    generic = {key: record[key] for key in ("path", "bytes", "sha256")}
    if role is not None:
        generic["role"] = role
    return generic


def _closed_json_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise P0ModelAvailabilityError(f"Duplicate JSON object key: {key}")
        payload[key] = value
    return payload


def _load_json(path: str | Path) -> dict[str, Any]:
    relative = _relative_repo_path(path)
    try:
        payload = json.loads(
            _secure_read_bytes(relative).decode("utf-8"),
            object_pairs_hook=_closed_json_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P0ModelAvailabilityError(
            f"Cannot parse JSON: {relative.as_posix()}"
        ) from exc
    if not isinstance(payload, dict):
        raise P0ModelAvailabilityError(
            f"JSON root must be an object: {relative.as_posix()}"
        )
    return cast(dict[str, Any], payload)


def load_and_validate_policy() -> dict[str, Any]:
    """Load the closed additive policy through no-follow file descriptors."""
    try:
        raw_policy = yaml.safe_load(_secure_read_bytes(DEFAULT_POLICY).decode("utf-8"))
        raw_schema = json.loads(
            _secure_read_bytes(DEFAULT_SCHEMA).decode("utf-8"),
            object_pairs_hook=_closed_json_object,
        )
    except (UnicodeDecodeError, yaml.YAMLError, json.JSONDecodeError) as exc:
        raise P0ModelAvailabilityError("Cannot parse the E0-MA policy bundle") from exc
    if not isinstance(raw_policy, dict) or not isinstance(raw_schema, dict):
        raise P0ModelAvailabilityError("E0-MA policy and schema must be objects")
    policy = cast(dict[str, Any], raw_policy)
    schema = cast(dict[str, Any], raw_schema)
    try:
        validate_json_schema(policy, schema, instance_path="$.model_lock_availability_policy")
    except Exception as exc:
        raise P0ModelAvailabilityError(
            "Model-lock availability policy failed its schema"
        ) from exc

    if tuple(policy.get("seed_slots", ())) != EXPECTED_SEEDS:
        raise P0ModelAvailabilityError("Availability policy seed order drifted")
    p0 = cast(Mapping[str, Any], policy["p0_closure"])
    if (
        p0.get("published_closure_head") != P0_CLOSURE_HEAD
        or p0.get("expected_available_fit_role_sequences") != EXPECTED_SUCCESS_COUNT
        or p0.get("expected_unavailable_fit_role_sequences") != EXPECTED_UNAVAILABLE_COUNT
        or p0.get("exact_registered_namespace_paths_per_seed") != EXPECTED_NAMESPACE_PATHS
        or p0.get("exact_present_paths_per_seed") != EXPECTED_PRESENT_PATHS
    ):
        raise P0ModelAvailabilityError("P0 closure policy drifted")
    bundle = cast(Mapping[str, Any], policy["registry_bundle"])
    expected_bundle_paths = {
        "registry_path": DEFAULT_REGISTRY.as_posix(),
        "companion_manifest_path": DEFAULT_COMPANION.as_posix(),
        "guard_directory": REGISTRY_GUARD_DIRECTORY.as_posix(),
        "hardened_writer_dependency": HARDENED_WRITER.as_posix(),
    }
    if any(bundle.get(key) != value for key, value in expected_bundle_paths.items()):
        raise P0ModelAvailabilityError("Registry bundle paths drifted")
    if tuple(bundle.get("guard_paths", ())) != tuple(
        path.as_posix() for path in REGISTRY_GUARD_PATHS
    ):
        raise P0ModelAvailabilityError("Registry guard paths drifted")
    return policy


def _closed_policy(candidate: Mapping[str, Any] | None = None) -> dict[str, Any]:
    policy = load_and_validate_policy()
    if candidate is not None and dict(candidate) != policy:
        raise P0ModelAvailabilityError(
            "Caller-supplied policy differs from the closed physical policy"
        )
    return policy


def p0_slot_paths(seed: int) -> dict[str, Path]:
    """Return the exact 19-path final/temp/guard namespace for one P0 slot."""
    report_root = Path("reports/closure_v1/02_models/P0")
    model_root = Path("models/closure_v1/pipe/P0")
    finals = {
        "model": model_root / f"seed_{seed}.pt",
        "checkpoint": model_root / f"seed_{seed}.checkpoint.pt",
        "preprocessor": report_root / f"seed_{seed}_preprocessor.json",
        "metrics": report_root / f"seed_{seed}_metrics.csv",
        "training_curve": report_root / f"seed_{seed}_training_curve.csv",
        "blend_weights": report_root / f"seed_{seed}_blend_weights.csv",
        "blend_search": report_root / f"seed_{seed}_blend_search.csv",
        "report": report_root / f"seed_{seed}_report.md",
        "manifest": report_root / f"seed_{seed}_manifest.json",
    }
    namespace = dict(finals)
    namespace.update(
        {
            f"{role}_temporary": path.with_suffix(path.suffix + ".tmp")
            for role, path in finals.items()
        }
    )
    namespace["guard"] = Path(
        f"tmp/closure_v1_temporal_consumer/P0_seed_{seed}.guard"
    )
    if len(namespace) != EXPECTED_NAMESPACE_PATHS:
        raise P0ModelAvailabilityError("Internal P0 namespace cardinality drifted")
    return namespace


def _p1_absence_paths(seed: int) -> tuple[Path, ...]:
    sequence = Path(f"data/closure_v1/development/sequences/P1/seed_{seed}.parquet")
    summary = Path(
        f"reports/closure_v1/01_surface/sequences/P1/seed_{seed}_summary.csv"
    )
    manifest = Path(
        f"reports/closure_v1/01_surface/sequences/P1/seed_{seed}_manifest.json"
    )
    sequence_paths = (
        sequence,
        sequence.with_suffix(sequence.suffix + ".tmp"),
        Path(f"{sequence.as_posix()}.dvc"),
        Path(f"{sequence.as_posix()}.dvc.tmp"),
        summary,
        summary.with_suffix(summary.suffix + ".tmp"),
        manifest,
        manifest.with_suffix(manifest.suffix + ".tmp"),
        Path(f"tmp/closure_v1_sequence_builder/P1_seed_{seed}.guard"),
    )
    remapped = tuple(
        Path(path.as_posix().replace("/P0/", "/P1/").replace("P0_seed_", "P1_seed_"))
        for path in p0_slot_paths(seed).values()
    )
    paths = sequence_paths + remapped
    if len(paths) != 28 or len({path.as_posix() for path in paths}) != 28:
        raise P0ModelAvailabilityError("Internal P1 preregistry namespace drifted")
    return paths


def _registry_namespace_paths() -> tuple[Path, ...]:
    return (
        DEFAULT_REGISTRY,
        DEFAULT_REGISTRY.with_suffix(DEFAULT_REGISTRY.suffix + ".tmp"),
        DEFAULT_COMPANION,
        DEFAULT_COMPANION.with_suffix(DEFAULT_COMPANION.suffix + ".tmp"),
        *REGISTRY_GUARD_PATHS,
    )


def _validate_physical_records(
    raw_records: Any,
    *,
    expected_count: int,
    context: str,
) -> list[dict[str, Any]]:
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
        raise P0ModelAvailabilityError(f"{context} must be an array")
    if len(raw_records) != expected_count:
        raise P0ModelAvailabilityError(
            f"{context} must contain {expected_count} records, observed {len(raw_records)}"
        )
    observed: list[dict[str, Any]] = []
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, Mapping) or set(raw_record) != {
            "path",
            "bytes",
            "sha256",
        }:
            raise P0ModelAvailabilityError(f"{context}[{index}] record dialect drifted")
        record = cast(Mapping[str, Any], raw_record)
        physical = _file_record(str(record["path"]))
        if dict(record) != physical:
            raise P0ModelAvailabilityError(
                f"{context}[{index}] differs from physical artifact: {physical['path']}"
            )
        observed.append(physical)
    return observed


def _validate_historical_git_records(
    raw_records: Any,
    *,
    expected_count: int,
    context: str,
    evidence_commit: str,
) -> list[dict[str, Any]]:
    """Validate immutable source records against their slot's Git authority.

    P0 manifests are historical evidence. Their code inputs intentionally bind
    the implementation that produced the slot, while later hardening overlays
    may change the corresponding worktree files. The evidence commit therefore
    owns these records; current physical bytes do not.
    """
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
        raise P0ModelAvailabilityError(f"{context} must be an array")
    if len(raw_records) != expected_count:
        raise P0ModelAvailabilityError(
            f"{context} must contain {expected_count} records, observed {len(raw_records)}"
        )
    _require_exact_commit(evidence_commit)
    observed: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, Mapping) or set(raw_record) != {
            "path",
            "bytes",
            "sha256",
        }:
            raise P0ModelAvailabilityError(f"{context}[{index}] record dialect drifted")
        record = dict(cast(Mapping[str, Any], raw_record))
        path = _repo_path(str(record["path"]))
        if path in seen_paths:
            raise P0ModelAvailabilityError(f"{context} repeats source path: {path}")
        seen_paths.add(path)
        git_record = _git_blob_record(evidence_commit, path)
        expected = _generic_record(git_record)
        if record != expected:
            raise P0ModelAvailabilityError(
                f"{context}[{index}] differs from sealed Git blob: {path}"
            )
        observed.append(expected)
    return observed


def _validate_slot_input_records(
    raw_records: Any,
    *,
    expected_count: int,
    context: str,
    historical_sources: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Validate data/config physically and duplicated source records historically."""
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
        raise P0ModelAvailabilityError(f"{context} must be an array")
    if len(raw_records) != expected_count:
        raise P0ModelAvailabilityError(
            f"{context} must contain {expected_count} records, observed {len(raw_records)}"
        )
    source_by_path = {
        str(record["path"]): dict(record) for record in historical_sources
    }
    if len(source_by_path) != len(historical_sources):
        raise P0ModelAvailabilityError(f"{context} historical source paths repeat")
    observed: list[dict[str, Any]] = []
    observed_paths: set[str] = set()
    observed_source_paths: set[str] = set()
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, Mapping) or set(raw_record) != {
            "path",
            "bytes",
            "sha256",
        }:
            raise P0ModelAvailabilityError(f"{context}[{index}] record dialect drifted")
        record = dict(cast(Mapping[str, Any], raw_record))
        path = _repo_path(str(record["path"]))
        if path in observed_paths:
            raise P0ModelAvailabilityError(f"{context} repeats input path: {path}")
        observed_paths.add(path)
        if path in source_by_path:
            if record != source_by_path[path]:
                raise P0ModelAvailabilityError(
                    f"{context}[{index}] differs from sealed source record: {path}"
                )
            observed_source_paths.add(path)
            observed.append(record)
            continue
        if path.startswith("src/") or Path(path).suffix == ".py":
            raise P0ModelAvailabilityError(
                f"{context}[{index}] code input lacks sealed source authority: {path}"
            )
        physical = _file_record(path)
        if record != physical:
            raise P0ModelAvailabilityError(
                f"{context}[{index}] differs from physical artifact: {path}"
            )
        observed.append(physical)
    if observed_source_paths != set(source_by_path):
        missing = sorted(set(source_by_path) - observed_source_paths)
        raise P0ModelAvailabilityError(
            f"{context} omits sealed source records: {missing}"
        )
    return observed


def _normalized_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(payload))
    normalized.pop("generated_at_utc", None)
    normalized.pop("base_seed", None)
    outputs = normalized.get("outputs")
    if isinstance(outputs, list) and len(outputs) == 1 and isinstance(outputs[0], dict):
        outputs[0] = {"artifact_role": outputs[0].get("artifact_role")}
    return cast(dict[str, Any], normalized)


def validate_p0_manifest_semantics(payload: Mapping[str, Any], *, seed: int) -> None:
    """Validate terminal P0 status without interpreting any evaluation row."""
    if set(payload) != MANIFEST_KEYS:
        raise P0ModelAvailabilityError(f"P0 seed {seed} manifest keys drifted")
    expected_scalars = {
        "manifest_version": "closure_pipe_model_manifest_v1",
        "status": "completed",
        "slot_status": "model_unavailable",
        "fit_status": "not_attempted",
        "failure_reason": "sequence_fit_rows_unavailable",
        "experiment_id": "closure_v1",
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "model_id": "P0",
        "base_seed": seed,
        "device": "cpu",
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "model_artifact_emitted": False,
        "completion_marker_written_last": True,
    }
    for field, expected in expected_scalars.items():
        observed = payload.get(field)
        if observed != expected or type(observed) is not type(expected):
            raise P0ModelAvailabilityError(
                f"P0 seed {seed} manifest field {field!r} drifted"
            )
    if payload.get("fit_status_counts") != {
        "success": EXPECTED_SUCCESS_COUNT,
        "autoregressive_target_unavailable": EXPECTED_UNAVAILABLE_COUNT,
    }:
        raise P0ModelAvailabilityError(f"P0 seed {seed} fit denominator drifted")
    if payload.get("failure_reason_counts") != {
        "missing_target_state": EXPECTED_UNAVAILABLE_COUNT
    }:
        raise P0ModelAvailabilityError(f"P0 seed {seed} failure denominator drifted")


def _evidence_chain(policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    p0 = cast(Mapping[str, Any], policy["p0_closure"])
    raw_chain = p0.get("evidence_chain")
    if not isinstance(raw_chain, Sequence) or isinstance(raw_chain, (str, bytes)):
        raise P0ModelAvailabilityError("P0 evidence chain is not an array")
    chain = [dict(cast(Mapping[str, Any], record)) for record in raw_chain]
    if [record.get("base_seed") for record in chain] != list(EXPECTED_SEEDS):
        raise P0ModelAvailabilityError("P0 evidence chain seed order drifted")
    for index, record in enumerate(chain):
        commit = str(record.get("commit"))
        parent = str(record.get("parent"))
        _require_exact_commit(commit)
        if _commit_parent(commit) != parent:
            raise P0ModelAvailabilityError(
                f"P0 seed {record.get('base_seed')} evidence parent drifted"
            )
        if index and parent != chain[index - 1]["commit"]:
            raise P0ModelAvailabilityError("P0 evidence commits are not a linear chain")
    if chain[-1]["commit"] != P0_CLOSURE_HEAD:
        raise P0ModelAvailabilityError("P0 evidence chain does not close at the fixed HEAD")
    return chain


def validate_p0_slot(
    seed: int,
    evidence: Mapping[str, Any],
    *,
    closure_head: str,
) -> dict[str, Any]:
    """Validate one immutable P0 report/manifest pair and all forbidden paths."""
    namespace = p0_slot_paths(seed)
    present_roles = [
        role for role, relative in namespace.items() if _path_entry_exists(relative)
    ]
    if present_roles != ["report", "manifest"]:
        raise P0ModelAvailabilityError(
            f"P0 seed {seed} must retain exactly report+manifest; observed {present_roles}"
        )

    report = namespace["report"]
    manifest = namespace["manifest"]
    commit = str(evidence["commit"])
    parent = str(evidence["parent"])
    if int(evidence["base_seed"]) != seed or _commit_parent(commit) != parent:
        raise P0ModelAvailabilityError(f"P0 seed {seed} evidence binding drifted")
    payload = _load_json(manifest)
    validate_p0_manifest_semantics(payload, seed=seed)
    sources = _validate_historical_git_records(
        payload.get("source_code"),
        expected_count=EXPECTED_SOURCE_RECORDS,
        context=f"P0 seed {seed} source_code",
        evidence_commit=commit,
    )
    inputs = _validate_slot_input_records(
        payload.get("inputs"),
        expected_count=EXPECTED_INPUT_RECORDS,
        context=f"P0 seed {seed} inputs",
        historical_sources=sources,
    )
    expected_report = {**_file_record(report), "artifact_role": "report"}
    if payload.get("outputs") != [expected_report]:
        raise P0ModelAvailabilityError(f"P0 seed {seed} output record drifted")
    script = payload.get("script")
    source_by_path = {str(record["path"]): dict(record) for record in sources}
    expected_script = source_by_path.get("src/experiments/train_closure_pipe.py")
    if not isinstance(script, Mapping) or dict(script) != expected_script:
        raise P0ModelAvailabilityError(f"P0 seed {seed} script record drifted")

    expected_report_text = (
        f"# Closure V1 P0 seed {seed}\n\n"
        "Status: `model_unavailable`\n"
        "Failure reason: `sequence_fit_rows_unavailable`\n\n"
        "No model/checkpoint was emitted and the failed slot was not replaced.\n"
    ).encode("utf-8")
    if _secure_read_bytes(report, context="P0 report") != expected_report_text:
        raise P0ModelAvailabilityError(f"P0 seed {seed} report content drifted")

    expected_paths = sorted((manifest.as_posix(), report.as_posix()))
    additions = _commit_additions(commit)
    if sorted(record["path"] for record in additions) != expected_paths:
        raise P0ModelAvailabilityError(
            f"P0 seed {seed} evidence commit must add exactly report+manifest"
        )
    manifest_record = _git_bound_record(commit, manifest)
    report_record = _git_bound_record(commit, report)
    closure_manifest = _git_bound_record(closure_head, manifest)
    closure_report = _git_bound_record(closure_head, report)
    if (
        _generic_record(manifest_record) != _generic_record(closure_manifest)
        or _generic_record(report_record) != _generic_record(closure_report)
    ):
        raise P0ModelAvailabilityError(
            f"P0 seed {seed} evidence changed before the fixed closure head"
        )
    if _git(
        "status",
        "--short",
        "--untracked-files=all",
        "--",
        manifest.as_posix(),
        report.as_posix(),
    ):
        raise P0ModelAvailabilityError(f"P0 seed {seed} evidence is modified")

    absent = [
        {"artifact_role": role, "path": path.as_posix(), "state": "absent"}
        for role, path in namespace.items()
        if role not in {"report", "manifest"}
    ]
    registered = [
        {
            "artifact_role": role,
            "path": path.as_posix(),
            "state": "present" if role in {"report", "manifest"} else "absent",
        }
        for role, path in namespace.items()
    ]
    return {
        "base_seed": seed,
        "slot_status": "model_unavailable",
        "fit_status": "not_attempted",
        "failure_reason": "sequence_fit_rows_unavailable",
        "available_fit_role_sequences": EXPECTED_SUCCESS_COUNT,
        "unavailable_fit_role_sequences": EXPECTED_UNAVAILABLE_COUNT,
        "failure_code": "missing_target_state",
        "failed_slot_replaced": False,
        "replacement_used": False,
        "model_artifact_emitted": False,
        "calibration_status": "not_attempted_upstream_model_unavailable",
        "calibration_artifacts": "forbidden",
        "evidence_commit": {
            "commit": commit,
            "parent": parent,
            "exact_addition_count": len(additions),
            "additions": additions,
        },
        "manifest": manifest_record,
        "report": report_record,
        "input_record_count": len(inputs),
        "input_records_sha256": _records_digest(inputs),
        "source_code_record_count": len(sources),
        "source_code_records_sha256": _records_digest(sources),
        "registered_namespace_path_count": len(registered),
        "present_path_count": EXPECTED_PRESENT_PATHS,
        "registered_namespace": registered,
        "absent_artifacts": absent,
        "normalized_manifest": _normalized_manifest(payload),
    }


def _audit_denominator_authority(policy: Mapping[str, Any]) -> dict[str, Any]:
    authority = cast(Mapping[str, Any], policy["denominator_authority"])
    source_commit = str(authority["source_commit"])
    _require_exact_commit(source_commit)
    manifest_record = _git_bound_record(source_commit, P0_SEQUENCE_MANIFEST)
    summary_record = _git_bound_record(source_commit, P0_SEQUENCE_SUMMARY)
    if _generic_record(manifest_record) != dict(authority["sequence_manifest"]):
        raise P0ModelAvailabilityError("P0 denominator manifest authority drifted")
    if _generic_record(summary_record) != dict(authority["sequence_summary"]):
        raise P0ModelAvailabilityError("P0 denominator summary authority drifted")
    if (
        _generic_record(_git_bound_record(P0_CLOSURE_HEAD, P0_SEQUENCE_MANIFEST))
        != _generic_record(manifest_record)
        or _generic_record(_git_bound_record(P0_CLOSURE_HEAD, P0_SEQUENCE_SUMMARY))
        != _generic_record(summary_record)
    ):
        raise P0ModelAvailabilityError("P0 denominator authority changed before closure")

    manifest = _load_json(P0_SEQUENCE_MANIFEST)
    counts = manifest.get("counts")
    if not isinstance(counts, Mapping):
        raise P0ModelAvailabilityError("P0 sequence manifest lacks counts")
    expected_count_fields = {
        "intent_origins": authority["intent_origins"],
        "successful_origins": authority["successful_origins"],
        "failed_origins": authority["failed_origins"],
        "holdout_overlap": authority["holdout_overlap"],
        "post_2021_rows": authority["post_2021_rows"],
    }
    if any(counts.get(key) != value for key, value in expected_count_fields.items()):
        raise P0ModelAvailabilityError("P0 sequence denominator counts drifted")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or dict(authority["sequence_summary"]) not in outputs:
        raise P0ModelAvailabilityError("P0 sequence summary is not bound by its manifest")

    summary_text = _secure_read_bytes(P0_SEQUENCE_SUMMARY).decode("utf-8")
    reader = csv.DictReader(io.StringIO(summary_text))
    if reader.fieldnames != ["time_role", "sequence_status", "failure_reason", "rows"]:
        raise P0ModelAvailabilityError("P0 denominator summary columns drifted")
    observed: dict[str, dict[str, int]] = {}
    for row in reader:
        role = row["time_role"]
        status = row["sequence_status"]
        failure = row["failure_reason"]
        if status == "success" and failure:
            raise P0ModelAvailabilityError("Successful P0 summary row has a failure reason")
        if status == "autoregressive_target_unavailable" and failure != "missing_target_state":
            raise P0ModelAvailabilityError("Unavailable P0 summary row cause drifted")
        observed.setdefault(role, {})[status] = int(row["rows"])
    expected_roles = {
        role: dict(cast(Mapping[str, Any], values))
        for role, values in cast(Mapping[str, Any], authority["role_status_counts"]).items()
    }
    if observed != expected_roles:
        raise P0ModelAvailabilityError("P0 role-specific denominators drifted")
    fit_roles = cast(Sequence[str], authority["fit_roles"])
    fit_success = sum(observed[role]["success"] for role in fit_roles)
    fit_unavailable = sum(
        observed[role]["autoregressive_target_unavailable"] for role in fit_roles
    )
    if (
        fit_success != EXPECTED_SUCCESS_COUNT
        or fit_unavailable != EXPECTED_UNAVAILABLE_COUNT
    ):
        raise P0ModelAvailabilityError("P0 fit-role denominator reconstruction drifted")
    return {
        "source_commit": source_commit,
        "sequence_manifest": manifest_record,
        "sequence_summary": summary_record,
        "intent_origins": authority["intent_origins"],
        "successful_origins": authority["successful_origins"],
        "failed_origins": authority["failed_origins"],
        "role_status_counts": expected_roles,
        "fit_roles": list(fit_roles),
        "fit_role_intent_origins": fit_success + fit_unavailable,
        "available_fit_role_sequences": fit_success,
        "unavailable_fit_role_sequences": fit_unavailable,
        "holdout_overlap": 0,
        "post_2021_rows": 0,
        "per_seed_counts_must_not_be_summed_as_ecological_denominator": True,
    }


def audit_p0_closure_snapshot(
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconstruct the immutable P0 closure snapshot without later-phase probes.

    This audit remains meaningful after the registry, P1, and E0-M have been
    published. It validates the five slot bundles, their historical code blobs,
    and the still-physical data/config authorities, but deliberately does not
    inspect any later namespace (including the outcome-access log).
    """
    active_policy = _closed_policy(policy)
    closure_head = str(cast(Mapping[str, Any], active_policy["p0_closure"])["published_closure_head"])
    _require_exact_commit(closure_head)
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", closure_head, "HEAD"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestor.returncode != 0:
        raise P0ModelAvailabilityError("Fixed P0 closure head is not an ancestor of HEAD")

    chain = _evidence_chain(active_policy)
    slots = [
        validate_p0_slot(seed, evidence, closure_head=closure_head)
        for seed, evidence in zip(EXPECTED_SEEDS, chain, strict=True)
    ]
    reference = slots[0]["normalized_manifest"]
    if any(slot["normalized_manifest"] != reference for slot in slots[1:]):
        raise P0ModelAvailabilityError(
            "P0 slot semantics differ beyond seed/timestamp/report metadata"
        )
    for slot in slots:
        slot.pop("normalized_manifest")
    denominator = _audit_denominator_authority(active_policy)

    return {
        "experiment_id": "closure_v1",
        "gate": "E0-MA",
        "status": "ready_to_register",
        "p0_published_closure_head": closure_head,
        "seed_slots": list(EXPECTED_SEEDS),
        "slot_count": len(slots),
        "slot_status_counts": {"model_unavailable": len(slots)},
        "available_fit_role_sequences_per_slot": EXPECTED_SUCCESS_COUNT,
        "unavailable_fit_role_sequences_per_slot": EXPECTED_UNAVAILABLE_COUNT,
        "denominator_authority": denominator,
        "slots": slots,
        "p1_materialized_path_count": 0,
        "e0_m_output_count": 0,
        "outcome_access_log_current_e0_ma_state": "absent",
        "outcome_access_log_required_e0_m_state": "present_empty",
        "outcome_access_log_required_e0_m_records": 0,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "side_effects": {
            "writes_performed": False,
            "network_commands_executed": False,
            "dvc_commands_executed": False,
            "outcome_paths_opened": False,
        },
    }


def audit_repository(
    policy: Mapping[str, Any] | None = None,
    *,
    allowed_registry_entries: Sequence[Path] = (),
) -> dict[str, Any]:
    """Run the strict pre-registry lifecycle gate on the P0 closure snapshot."""
    summary = audit_p0_closure_snapshot(policy)

    allowed = {path.as_posix() for path in allowed_registry_entries}
    existing_registry = [
        path.as_posix()
        for path in _registry_namespace_paths()
        if _path_entry_exists(path) and path.as_posix() not in allowed
    ]
    if existing_registry:
        raise P0ModelAvailabilityError(
            f"Registry bundle namespace is not pristine: {existing_registry}"
        )
    if _path_entry_exists(OUTCOME_ACCESS_LOG):
        raise P0ModelAvailabilityError("Outcome access log must remain absent before E0-U")
    existing_e0_m = [
        path.as_posix() for path in E0_M_OUTPUTS if _path_entry_exists(path)
    ]
    if existing_e0_m:
        raise P0ModelAvailabilityError(f"E0-M outputs already exist: {existing_e0_m}")
    existing_p1 = [
        path.as_posix()
        for seed in EXPECTED_SEEDS
        for path in _p1_absence_paths(seed)
        if _path_entry_exists(path)
    ]
    if existing_p1:
        raise P0ModelAvailabilityError(
            f"P1 materialization predates the P0 registry: {existing_p1}"
        )
    return summary


def _require_h_slice_published(policy: Mapping[str, Any]) -> dict[str, Any]:
    if _git("status", "--short", "--untracked-files=all"):
        raise P0ModelAvailabilityError(
            "Registry generation requires a clean worktree and index"
        )
    bundle = cast(Mapping[str, Any], policy["registry_bundle"])
    head = _git("rev-parse", "HEAD")
    base = str(bundle["h_slice_base_head"])
    if _commit_parent(head) != base:
        raise P0ModelAvailabilityError(
            "The H-slice must be the direct child of the fixed P0 closure head"
        )
    expected_paths = list(cast(Sequence[str], bundle["h_slice_paths"]))
    additions = _commit_additions(head)
    if (
        len(additions) != int(bundle["h_slice_exact_additions"])
        or sorted(record["path"] for record in additions) != sorted(expected_paths)
    ):
        raise P0ModelAvailabilityError("Published H-slice diff is not exactly 5A")
    branch = _git("symbolic-ref", "--quiet", "--short", "HEAD")
    if branch != bundle["branch"]:
        raise P0ModelAvailabilityError("H-slice is not published from the closed branch")
    refs = {
        "head": head,
        "main": _git("rev-parse", "main"),
        "tracking": _git("rev-parse", str(bundle["tracking_ref"])),
        "origin_head": _git("rev-parse", "origin/HEAD"),
    }
    if len(set(refs.values())) != 1:
        raise P0ModelAvailabilityError(f"Local publication refs are not aligned: {refs}")
    remote_output = _git(
        "ls-remote", "--exit-code", "origin", str(bundle["remote_ref"])
    )
    remote_main = remote_output.split()[0] if remote_output else ""
    if remote_main != head:
        raise P0ModelAvailabilityError("Live remote main differs from the H-slice HEAD")
    components = [
        {
            **_git_bound_record(head, path),
            "role": "h_slice_component",
        }
        for path in H_SLICE_COMPONENTS
    ]
    writer_dependency = {
        **_git_bound_record(head, HARDENED_WRITER),
        "role": "hardened_writer_dependency",
    }
    return {
        "h_slice_head": head,
        "h_slice_parent": base,
        "branch": branch,
        "local_branch_ref": "refs/heads/main",
        "tracking_ref": str(bundle["tracking_ref"]),
        "remote_ref": str(bundle["remote_ref"]),
        "refs": refs,
        "remote_main": remote_main,
        "h_slice_diff": additions,
        "h_slice_components": components,
        "hardened_writer_dependency": writer_dependency,
    }


def _reconstruct_h_slice_publication(
    policy: Mapping[str, Any],
    *,
    h_slice_head: str,
) -> dict[str, Any]:
    """Reconstruct the immutable H binding after refs advanced to the 2A commit."""
    bundle = cast(Mapping[str, Any], policy["registry_bundle"])
    base = str(bundle["h_slice_base_head"])
    if _commit_parent(h_slice_head) != base:
        raise P0ModelAvailabilityError(
            "Published H-slice is not the direct child of P0 closure"
        )
    additions = _commit_additions(h_slice_head)
    expected_paths = list(cast(Sequence[str], bundle["h_slice_paths"]))
    if (
        len(additions) != int(bundle["h_slice_exact_additions"])
        or sorted(record["path"] for record in additions) != sorted(expected_paths)
    ):
        raise P0ModelAvailabilityError("Published H-slice diff is not exactly 5A")
    components = [
        {
            **_git_bound_record(h_slice_head, path),
            "role": "h_slice_component",
        }
        for path in H_SLICE_COMPONENTS
    ]
    return {
        "h_slice_head": h_slice_head,
        "h_slice_parent": base,
        "branch": str(bundle["branch"]),
        "local_branch_ref": "refs/heads/main",
        "tracking_ref": str(bundle["tracking_ref"]),
        "remote_ref": str(bundle["remote_ref"]),
        "refs": {
            "head": h_slice_head,
            "main": h_slice_head,
            "tracking": h_slice_head,
            "origin_head": h_slice_head,
        },
        "remote_main": h_slice_head,
        "h_slice_diff": additions,
        "h_slice_components": components,
        "hardened_writer_dependency": {
            **_git_bound_record(h_slice_head, HARDENED_WRITER),
            "role": "hardened_writer_dependency",
        },
    }


def _revalidate_h_slice_during_generation(
    policy: Mapping[str, Any],
    publication: Mapping[str, Any],
) -> dict[str, Any]:
    """Recheck the H publication while the two generated finals are untracked."""
    bundle = cast(Mapping[str, Any], policy["registry_bundle"])
    h_slice_head = str(publication["h_slice_head"])
    reconstructed = _reconstruct_h_slice_publication(
        policy,
        h_slice_head=h_slice_head,
    )
    if reconstructed != dict(publication):
        raise P0ModelAvailabilityError(
            "H-E0-MA physical or Git binding changed during registry generation"
        )
    expected_status = sorted(
        (
            f"?? {DEFAULT_REGISTRY.as_posix()}",
            f"?? {DEFAULT_COMPANION.as_posix()}",
        )
    )
    observed_status = _git("status", "--short", "--untracked-files=all").splitlines()
    if sorted(observed_status) != expected_status:
        raise P0ModelAvailabilityError(
            "Registry generation worktree changed beyond the owned two-file bundle"
        )
    branch = _git("symbolic-ref", "--quiet", "--short", "HEAD")
    refs = {
        "head": _git("rev-parse", "HEAD"),
        "main": _git("rev-parse", "main"),
        "tracking": _git("rev-parse", str(bundle["tracking_ref"])),
        "origin_head": _git("rev-parse", "origin/HEAD"),
    }
    if branch != bundle["branch"] or set(refs.values()) != {h_slice_head}:
        raise P0ModelAvailabilityError(
            f"H-E0-MA refs changed during registry generation: {refs}"
        )
    remote_output = _git(
        "ls-remote", "--exit-code", "origin", str(bundle["remote_ref"])
    )
    remote_main = remote_output.split()[0] if remote_output else ""
    if remote_main != h_slice_head:
        raise P0ModelAvailabilityError(
            "Live remote main changed during registry generation"
        )
    return reconstructed


def build_registry_payload(
    policy: Mapping[str, Any],
    audit: Mapping[str, Any],
    publication: Mapping[str, Any],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build the closed registry; it deliberately declares itself ineffective."""
    head = str(publication["h_slice_head"])
    sealed_records = []
    for role, raw in cast(Mapping[str, Any], policy["sealed_authorities"]).items():
        authority = cast(Mapping[str, Any], raw)
        sealed_records.append(
            {**_git_bound_record(head, str(authority["path"])), "role": role}
        )
    bundle = cast(Mapping[str, Any], policy["registry_bundle"])
    return {
        "registry_version": "closure_p0_model_availability_registry_v1",
        "status": "completed",
        "created_at_utc": created_at_utc
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "experiment_id": "closure_v1",
        "gate": "E0-MA",
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "model_id": "P0",
        "repository_binding": {
            "p0_closure_head": audit["p0_published_closure_head"],
            **dict(publication),
        },
        "publication_contract": {
            "effective_in_payload": False,
            "effective_only_after_published_loader_passes": True,
            "expected_direct_parent": publication["h_slice_head"],
            "exact_addition_count": bundle["registry_commit_exact_additions"],
            "exact_addition_paths": [
                bundle["registry_path"],
                bundle["companion_manifest_path"],
            ],
            "publication_order": list(cast(Sequence[str], bundle["publication_order"])),
            "completion_marker_written_last": True,
            "no_clobber": True,
            "dvc_registration": "forbidden",
        },
        "sealed_authorities": sealed_records,
        "denominator_authority": audit["denominator_authority"],
        "slot_count": audit["slot_count"],
        "seed_slots": audit["seed_slots"],
        "slot_status_counts": audit["slot_status_counts"],
        "slots": audit["slots"],
        "model_lock_hash_policy": policy["model_lock_hash_policy"],
        "comparison_disposition": policy["comparison_policy"],
        "p1_progression": policy["p1_progression"],
        "p1_materialized_path_count": 0,
        "e0_m_status": "not_started",
        "outcome_access": policy["outcome_access"],
        "completion_marker_written_last": True,
    }


def build_companion_payload(
    registry: Mapping[str, Any],
    registry_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the generic precommit companion after the registry is anchored."""
    repository = cast(Mapping[str, Any], registry["repository_binding"])
    candidates: list[tuple[Mapping[str, Any], str]] = []
    for record in cast(Sequence[Mapping[str, Any]], repository["h_slice_components"]):
        if record["path"] != DEFAULT_AUDITOR.as_posix():
            candidates.append((record, "h_slice_component"))
    candidates.append(
        (
            cast(Mapping[str, Any], repository["hardened_writer_dependency"]),
            "hardened_writer_dependency",
        )
    )
    for record in cast(Sequence[Mapping[str, Any]], registry["sealed_authorities"]):
        candidates.append((record, f"sealed_{record['role']}"))
    denominator = cast(Mapping[str, Any], registry["denominator_authority"])
    candidates.extend(
        (
            (cast(Mapping[str, Any], denominator["sequence_manifest"]), "p0_sequence_manifest"),
            (cast(Mapping[str, Any], denominator["sequence_summary"]), "p0_sequence_summary"),
        )
    )
    for slot in cast(Sequence[Mapping[str, Any]], registry["slots"]):
        seed = slot["base_seed"]
        candidates.extend(
            (
                (cast(Mapping[str, Any], slot["manifest"]), f"p0_seed_{seed}_manifest"),
                (cast(Mapping[str, Any], slot["report"]), f"p0_seed_{seed}_report"),
            )
        )
    inputs_by_path: dict[str, dict[str, Any]] = {}
    for record, role in candidates:
        path = str(record["path"])
        inputs_by_path.setdefault(path, _generic_record(record, role=role))
    return {
        "manifest_version": "closure_p0_model_availability_registry_manifest_v1",
        "status": "completed",
        "created_at_utc": registry["created_at_utc"],
        "experiment_id": "closure_v1",
        "gate": "E0-MA",
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "model_id": "P0",
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "registry_effective_in_payload": False,
        "script": _generic_record(
            _file_record(DEFAULT_AUDITOR), role="generating_script"
        ),
        "inputs": [inputs_by_path[path] for path in sorted(inputs_by_path)],
        "outputs": [dict(registry_record)],
        "completion_marker_written_last": True,
    }


REGISTRY_PAYLOAD_KEYS = {
    "registry_version",
    "status",
    "created_at_utc",
    "experiment_id",
    "gate",
    "surface_id",
    "model_id",
    "repository_binding",
    "publication_contract",
    "sealed_authorities",
    "denominator_authority",
    "slot_count",
    "seed_slots",
    "slot_status_counts",
    "slots",
    "model_lock_hash_policy",
    "comparison_disposition",
    "p1_progression",
    "p1_materialized_path_count",
    "e0_m_status",
    "outcome_access",
    "completion_marker_written_last",
}
COMPANION_PAYLOAD_KEYS = {
    "manifest_version",
    "status",
    "created_at_utc",
    "experiment_id",
    "gate",
    "surface_id",
    "model_id",
    "future_outcomes_accessed",
    "evaluation_authorized",
    "e0_u_authorized",
    "registry_effective_in_payload",
    "script",
    "inputs",
    "outputs",
    "completion_marker_written_last",
}


def _assert_no_nulls(value: Any, *, context: str) -> None:
    if value is None:
        raise P0ModelAvailabilityError(f"{context} contains a null placeholder")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _assert_no_nulls(child, context=f"{context}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, child in enumerate(value):
            _assert_no_nulls(child, context=f"{context}[{index}]")


def _validate_registry_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise P0ModelAvailabilityError("Registry timestamp must be explicit UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P0ModelAvailabilityError("Registry timestamp is invalid") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise P0ModelAvailabilityError("Registry timestamp is not UTC")
    return value


def validate_registry_bundle_payloads(
    policy: Mapping[str, Any],
    audit: Mapping[str, Any],
    publication: Mapping[str, Any],
    registry: Mapping[str, Any],
    companion: Mapping[str, Any],
    registry_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Reconstruct and compare every scientific and publication field."""
    if set(registry) != REGISTRY_PAYLOAD_KEYS:
        raise P0ModelAvailabilityError("Registry top-level keys drifted")
    if set(companion) != COMPANION_PAYLOAD_KEYS:
        raise P0ModelAvailabilityError("Registry companion top-level keys drifted")
    timestamp = _validate_registry_timestamp(registry.get("created_at_utc"))
    if companion.get("created_at_utc") != timestamp:
        raise P0ModelAvailabilityError("Registry and companion timestamps differ")
    expected_registry = build_registry_payload(
        policy,
        audit,
        publication,
        created_at_utc=timestamp,
    )
    if dict(registry) != expected_registry:
        raise P0ModelAvailabilityError(
            "Registry differs from the closed policy and reconstructed P0 audit"
        )
    expected_registry_record = {
        "path": DEFAULT_REGISTRY.as_posix(),
        "role": "p0_model_availability_registry",
        "bytes": len(_canonical_json(registry)),
        "sha256": hashlib.sha256(_canonical_json(registry)).hexdigest(),
    }
    if dict(registry_record) != expected_registry_record:
        raise P0ModelAvailabilityError("Registry file record differs from canonical bytes")
    expected_companion = build_companion_payload(registry, registry_record)
    if dict(companion) != expected_companion:
        raise P0ModelAvailabilityError(
            "Registry companion differs from its exact script/input/output contract"
        )
    _assert_no_nulls(registry, context="registry")
    _assert_no_nulls(companion, context="companion")
    return {
        "status": "registry_bundle_payloads_valid",
        "slot_count": registry["slot_count"],
        "companion_input_count": len(cast(Sequence[Any], companion["inputs"])),
        "registry_sha256": expected_registry_record["sha256"],
    }


def _sync_hardened_root() -> None:
    if hardened.PROJECT_ROOT.resolve() != PROJECT_ROOT.resolve():
        raise P0ModelAvailabilityError("Hardened writer repository root drifted")


def _refuse_registry_namespace() -> None:
    existing = [
        path.as_posix() for path in _registry_namespace_paths() if _path_entry_exists(path)
    ]
    if existing:
        raise P0ModelAvailabilityError(
            f"Refusing an existing E0-MA registry namespace: {existing}"
        )


def _registry_guard_paths(*, create_directory: bool) -> tuple[Path, Path]:
    _sync_hardened_root()
    tmp_root = PROJECT_ROOT / "tmp"
    guard_directory = PROJECT_ROOT / REGISTRY_GUARD_DIRECTORY
    if create_directory:
        hardened._ensure_real_directory(
            tmp_root,
            parent=PROJECT_ROOT,
            context="E0-MA tmp root",
        )
        hardened._ensure_real_directory(
            guard_directory,
            parent=tmp_root,
            context="E0-MA guard directory",
        )
    return (
        PROJECT_ROOT / REGISTRY_GUARD_PATHS[0],
        PROJECT_ROOT / REGISTRY_GUARD_PATHS[1],
    )


def _acquire_registry_guards() -> tuple[hardened._OutputGuard, ...]:
    _refuse_registry_namespace()
    guard_paths = _registry_guard_paths(create_directory=True)
    guards: list[hardened._OutputGuard] = []
    try:
        for path in guard_paths:
            guards.append(hardened._open_guard(path))
        destination_parent = hardened._open_repo_directory(
            DEFAULT_REGISTRY.parent,
            context="E0-MA registry parent",
        )
        try:
            destination_device = os.fstat(destination_parent).st_dev
        finally:
            os.close(destination_parent)
        if any(guard.device != destination_device for guard in guards):
            raise P0ModelAvailabilityError(
                "E0-MA guards and registry destination are on different filesystems"
            )
        return tuple(guards)
    except BaseException:
        cleanup_errors: list[Exception] = []
        for guard in reversed(guards):
            try:
                hardened._release_guard(guard)
            except Exception as exc:  # pragma: no cover - defensive aggregation
                cleanup_errors.append(exc)
        if cleanup_errors:
            cleanup = P0ModelAvailabilityError(
                "E0-MA guard acquisition cleanup failed"
            )
            cleanup.add_note(
                "; ".join(f"{type(exc).__name__}: {exc}" for exc in cleanup_errors)
            )
            raise cleanup
        raise


def generate_registry_bundle(policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Generate exactly registry+companion under one exclusive transaction."""
    active_policy = _closed_policy(policy)
    guards = _acquire_registry_guards()
    owners: list[hardened._OwnedFile] = []
    succeeded = False
    active_error: BaseException | None = None
    result: dict[str, Any] | None = None
    try:
        registry_path = PROJECT_ROOT / DEFAULT_REGISTRY
        companion_path = PROJECT_ROOT / DEFAULT_COMPANION
        hardened._assert_lock_namespace(registry_path, companion_path, guards, owners)
        allowed_guards = tuple(REGISTRY_GUARD_PATHS)
        audit = audit_repository(
            active_policy,
            allowed_registry_entries=allowed_guards,
        )
        publication = _require_h_slice_published(active_policy)
        registry = build_registry_payload(active_policy, audit, publication)
        repeated_audit = audit_repository(
            active_policy,
            allowed_registry_entries=allowed_guards,
        )
        repeated_publication = _require_h_slice_published(active_policy)
        if repeated_audit != audit or repeated_publication != publication:
            raise P0ModelAvailabilityError(
                "E0-MA authority changed while the exclusive guards were held"
            )
        hardened._assert_lock_namespace(registry_path, companion_path, guards, owners)

        registry_owner = hardened._publish_guarded_bytes(
            _canonical_json(registry),
            registry_path,
            DEFAULT_REGISTRY,
            guards[0],
        )
        owners.append(registry_owner)
        registry_record = hardened._owned_file_record(
            registry_owner,
            role="p0_model_availability_registry",
        )
        hardened._assert_lock_namespace(registry_path, companion_path, guards, owners)
        companion = build_companion_payload(registry, registry_record)
        companion_owner = hardened._publish_guarded_bytes(
            _canonical_json(companion),
            companion_path,
            DEFAULT_COMPANION,
            guards[1],
        )
        owners.append(companion_owner)
        hardened._assert_lock_namespace(registry_path, companion_path, guards, owners)
        final_audit = audit_repository(
            active_policy,
            allowed_registry_entries=(
                *allowed_guards,
                DEFAULT_REGISTRY,
                DEFAULT_COMPANION,
            ),
        )
        if final_audit != audit:
            raise P0ModelAvailabilityError(
                "E0-MA authority changed after registry publication"
            )
        final_publication = _revalidate_h_slice_during_generation(
            active_policy,
            publication,
        )
        final_registry_record = hardened._owned_file_record(
            registry_owner,
            role="p0_model_availability_registry",
        )
        final_companion_record = hardened._owned_file_record(
            companion_owner,
            role="p0_model_availability_registry_manifest",
        )
        if final_registry_record != registry_record:
            raise P0ModelAvailabilityError(
                "E0-MA registry changed before transaction completion"
            )
        expected_companion_bytes = _canonical_json(companion)
        expected_companion_record = {
            "path": DEFAULT_COMPANION.as_posix(),
            "role": "p0_model_availability_registry_manifest",
            "bytes": len(expected_companion_bytes),
            "sha256": hashlib.sha256(expected_companion_bytes).hexdigest(),
        }
        if final_companion_record != expected_companion_record:
            raise P0ModelAvailabilityError(
                "E0-MA companion differs from canonical bytes"
            )
        validate_registry_bundle_payloads(
            active_policy,
            final_audit,
            final_publication,
            registry,
            companion,
            final_registry_record,
        )
        hardened._assert_lock_namespace(registry_path, companion_path, guards, owners)
        succeeded = True
        result = {
            "status": "registry_bundle_written_unpublished",
            "registry": final_registry_record,
            "companion_manifest": final_companion_record,
            "publication_order": ["registry", "companion_manifest"],
            "registry_effective": False,
            "dvc_commands_executed": False,
            "outcome_paths_opened": False,
        }
    except BaseException as exc:
        active_error = exc
    try:
        hardened._cleanup_lock_resources(
            owners,
            guards,
            succeeded=succeeded,
            active_error=active_error,
        )
    except BaseException as exc:
        raise P0ModelAvailabilityError(
            "E0-MA registry transaction cleanup failed closed"
        ) from exc
    if active_error is not None:
        if isinstance(active_error, P0ModelAvailabilityError):
            raise active_error
        raise P0ModelAvailabilityError("E0-MA registry transaction failed") from active_error
    if result is None:  # pragma: no cover - defensive exhaustiveness
        raise P0ModelAvailabilityError("E0-MA registry transaction produced no result")
    return result


def _load_canonical_json(path: Path, *, context: str) -> dict[str, Any]:
    payload = _load_json(path)
    if _secure_read_bytes(path, context=context) != _canonical_json(payload):
        raise P0ModelAvailabilityError(f"{context} is not canonical JSON")
    return payload


def load_published_registry() -> dict[str, Any]:
    """Return effective=true only for the exact published 2A registry commit."""
    policy = _closed_policy()
    registry = _load_canonical_json(DEFAULT_REGISTRY, context="published registry")
    companion = _load_canonical_json(
        DEFAULT_COMPANION,
        context="published registry companion",
    )
    repository = registry.get("repository_binding")
    publication_contract = registry.get("publication_contract")
    if not isinstance(repository, Mapping) or not isinstance(
        publication_contract, Mapping
    ):
        raise P0ModelAvailabilityError("Published registry lacks repository binding")
    if publication_contract.get("effective_in_payload") is not False:
        raise P0ModelAvailabilityError("Registry payload cannot self-authorize")

    registry_commit = _git(
        "log", "-1", "--format=%H", "--", DEFAULT_REGISTRY.as_posix()
    )
    companion_commit = _git(
        "log", "-1", "--format=%H", "--", DEFAULT_COMPANION.as_posix()
    )
    if not registry_commit or registry_commit != companion_commit:
        raise P0ModelAvailabilityError("Registry and companion are not in one commit")
    h_head = str(repository.get("h_slice_head"))
    if _commit_parent(registry_commit) != h_head:
        raise P0ModelAvailabilityError("Registry commit is not the direct child of H-E0-MA")
    if _commit_parent(h_head) != P0_CLOSURE_HEAD:
        raise P0ModelAvailabilityError("H-E0-MA is not the direct child of P0 closure")
    bundle = cast(Mapping[str, Any], policy["registry_bundle"])
    registry_additions = _commit_additions(registry_commit)
    expected_registry_paths = sorted(
        (DEFAULT_REGISTRY.as_posix(), DEFAULT_COMPANION.as_posix())
    )
    if (
        len(registry_additions) != int(bundle["registry_commit_exact_additions"])
        or sorted(record["path"] for record in registry_additions)
        != expected_registry_paths
    ):
        raise P0ModelAvailabilityError("Published registry commit is not exactly 2A")
    h_additions = _commit_additions(h_head)
    if sorted(record["path"] for record in h_additions) != sorted(
        cast(Sequence[str], bundle["h_slice_paths"])
    ):
        raise P0ModelAvailabilityError("Published H-E0-MA commit is not exactly 5A")

    current_head = _git("rev-parse", "HEAD")
    if current_head != registry_commit:
        raise P0ModelAvailabilityError(
            "Published registry validation requires HEAD at the exact 2A commit"
        )
    branch = _git("symbolic-ref", "--quiet", "--short", "HEAD")
    if branch != bundle["branch"]:
        raise P0ModelAvailabilityError("Published registry branch drifted")
    refs = {
        "head": current_head,
        "main": _git("rev-parse", "main"),
        "tracking": _git("rev-parse", str(bundle["tracking_ref"])),
        "origin_head": _git("rev-parse", "origin/HEAD"),
    }
    if len(set(refs.values())) != 1 or current_head != registry_commit:
        raise P0ModelAvailabilityError(f"Registry publication refs diverged: {refs}")
    output = _git(
        "ls-remote", "--exit-code", "origin", str(bundle["remote_ref"])
    )
    remote_main = output.split()[0] if output else ""
    if remote_main != registry_commit:
        raise P0ModelAvailabilityError("Live remote main differs from registry commit")

    registry_git = _git_bound_record(registry_commit, DEFAULT_REGISTRY)
    companion_git = _git_bound_record(registry_commit, DEFAULT_COMPANION)
    if _git("status", "--short", "--untracked-files=all"):
        raise P0ModelAvailabilityError(
            "Published registry validation requires a clean worktree and index"
        )
    audit = audit_repository(
        policy,
        allowed_registry_entries=(DEFAULT_REGISTRY, DEFAULT_COMPANION),
    )
    publication = _reconstruct_h_slice_publication(
        policy,
        h_slice_head=h_head,
    )
    registry_record = _generic_record(
        registry_git, role="p0_model_availability_registry"
    )
    validation = validate_registry_bundle_payloads(
        policy,
        audit,
        publication,
        registry,
        companion,
        registry_record,
    )

    return {
        "status": "published_registry_valid",
        "registry_effective": True,
        "registry_commit": registry_commit,
        "registry": registry_git,
        "companion_manifest": companion_git,
        "h_slice_head": h_head,
        "current_head": current_head,
        "refs": refs,
        "remote_main": remote_main,
        "reconstruction": validation,
        "p1_sequence_builder_authorized": True,
        "first_authorized_p1_sequence_seed": 1729,
        "p1_fit_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit, generate, or validate the Closure V1 P0 availability registry."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--generate", action="store_true")
    mode.add_argument("--validate-published", action="store_true")
    return parser.parse_args(arguments)


def main() -> None:
    args = parse_args()
    if args.check_only:
        print(json.dumps(audit_repository(), indent=2, ensure_ascii=False))
        return
    if args.generate:
        print(json.dumps(generate_registry_bundle(), indent=2, ensure_ascii=False))
        return
    print(
        json.dumps(
            load_published_registry(),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
