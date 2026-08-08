#!/usr/bin/env python
"""Audit one or all Closure V1 A0/A1 development model bundles read-only."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from sklearn.metrics import average_precision_score
from threadpoolctl import threadpool_limits

from src.experiments import train_closure_anfis_ablation as trainer


AUDIT_VERSION = "closure_anfis_ablation_model_bundle_audit_v1"
DEFAULT_RUNTIME = Path(
    "configs/closure_v1/anfis_ablation_training_development_runtime.yaml"
)
OUTCOME_ACCESS_LOG = Path("reports/closure_v1/00_protocol/outcome_access_log.jsonl")
MODEL_SEEDS = tuple(int(seed) for seed in trainer.REGISTERED_SEEDS)
BUNDLE_SLOTS = tuple(
    (model_id, seed) for seed in MODEL_SEEDS for model_id in trainer.MODEL_IDS
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RECORD_KEYS = frozenset({"role", "path", "bytes", "sha256"})
MANIFEST_KEYS = frozenset(
    {
        "manifest_version",
        "status",
        "slot_status",
        "fit_status",
        "generated_at_utc",
        "experiment_id",
        "surface_id",
        "model_id",
        "base_seed",
        "device",
        "future_outcomes_accessed",
        "calibration_authorized",
        "calibration_target_accessed",
        "evaluation_authorized",
        "e0_m_authorized",
        "e0_u_authorized",
        "dvc_command_executed",
        "target_contract",
        "role_counts",
        "architecture",
        "preprocessing",
        "pairing",
        "authority",
        "authority_records",
        "script",
        "inputs",
        "source_code",
        "outputs",
        "completion_marker_written_last",
    }
)
PAIRING_KEYS = frozenset(
    {
        "policy",
        "paired_model_ids",
        "base_seed",
        "training_identity_sha256",
        "selection_identity_sha256",
        "selection_target_sha256",
    }
)
AUTHORITY_BINDING_KEYS = (
    "gate",
    "status",
    "authorized_model_id",
    "authorized_base_seed",
    "completed_prefix_count",
    "slot_creation_prefix_count",
    "h_patch_head",
    "p_patch_head",
    "h_components_sha256",
    "physical_inputs_sha256",
    "runtime_sha256",
    "lock_sha256",
    "companion_sha256",
)
SEALED_TARGET_ROLES = frozenset({"development_targets", "target_manifest"})
HISTORICAL_AUTHORITY_RECORD_SPECS = (
    (
        "anfis_ablation_training_runtime_contract",
        DEFAULT_RUNTIME,
        "runtime_sha256",
    ),
    (
        "anfis_ablation_training_cohort_patch_lock",
        Path(
            "reports/closure_v1/00_protocol/"
            "anfis_ablation_training_cohort_patch_lock.json"
        ),
        "lock_sha256",
    ),
    (
        "anfis_ablation_training_cohort_patch_lock_manifest",
        Path(
            "reports/closure_v1/00_protocol/"
            "anfis_ablation_training_cohort_patch_lock_manifest.json"
        ),
        "companion_sha256",
    ),
)
AUTHORITY_RECORD_SPECS = (
    (
        "anfis_ablation_training_runtime_contract",
        DEFAULT_RUNTIME,
        "runtime_sha256",
    ),
    (
        "anfis_ablation_model_manifest_patch_lock",
        Path(
            "reports/closure_v1/00_protocol/"
            "anfis_ablation_model_manifest_patch_lock.json"
        ),
        "lock_sha256",
    ),
    (
        "anfis_ablation_model_manifest_patch_lock_manifest",
        Path(
            "reports/closure_v1/00_protocol/"
            "anfis_ablation_model_manifest_patch_lock_manifest.json"
        ),
        "companion_sha256",
    ),
)


class AnfisAblationModelAuditError(ValueError):
    """Raised when an A0/A1 model bundle differs from its closed contract."""


@dataclass(frozen=True)
class CutoffTargetReference:
    frame: pd.DataFrame
    record: dict[str, Any]
    identity: tuple[int, ...]


def _relative_repo_path(path: str | Path, *, repo_root: Path) -> Path:
    candidate = Path(path)
    try:
        root = repo_root.resolve(strict=True)
    except FileNotFoundError as error:
        raise AnfisAblationModelAuditError("Repository root is absent") from error
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(root)
        except ValueError as error:
            raise AnfisAblationModelAuditError(f"Path escapes repository: {path}") from error
    if not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise AnfisAblationModelAuditError(f"Unsafe repository path: {path}")
    return candidate


def _open_repository_parent(path: str | Path, *, repo_root: Path) -> tuple[int, Path]:
    relative = _relative_repo_path(path, repo_root=repo_root)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(repo_root.resolve(strict=True), flags)
    except OSError as error:
        raise AnfisAblationModelAuditError("Repository root is linked or unreadable") from error
    try:
        for component in relative.parent.parts:
            try:
                named = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
                child = os.open(component, flags, dir_fd=descriptor)
            except OSError as error:
                raise AnfisAblationModelAuditError(
                    f"Artifact parent is missing or linked: {relative.parent}"
                ) from error
            opened = os.fstat(child)
            if (
                not stat.S_ISDIR(named.st_mode)
                or not stat.S_ISDIR(opened.st_mode)
                or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                os.close(child)
                raise AnfisAblationModelAuditError(
                    f"Artifact parent identity drifted: {relative.parent}"
                )
            previous = descriptor
            descriptor = child
            os.close(previous)
        return descriptor, relative
    except BaseException:
        os.close(descriptor)
        raise


def _read_regular_bytes(
    path: str | Path,
    *,
    repo_root: Path,
    role: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    parent, relative = _open_repository_parent(path, repo_root=repo_root)
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            named_before = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
            descriptor = os.open(relative.name, flags, dir_fd=parent)
        except OSError as error:
            raise AnfisAblationModelAuditError(
                f"Artifact is absent, linked, or unreadable: {relative.as_posix()}"
            ) from error
        opened_before = os.fstat(descriptor)
        before = (
            opened_before.st_dev,
            opened_before.st_ino,
            opened_before.st_mode,
            opened_before.st_size,
            opened_before.st_mtime_ns,
            opened_before.st_ctime_ns,
        )
        if (
            not stat.S_ISREG(named_before.st_mode)
            or not stat.S_ISREG(opened_before.st_mode)
            or (named_before.st_dev, named_before.st_ino)
            != (opened_before.st_dev, opened_before.st_ino)
        ):
            raise AnfisAblationModelAuditError(
                f"Artifact is not a stable regular file: {relative.as_posix()}"
            )
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
            digest.update(chunk)
        payload = b"".join(chunks)
        opened_after = os.fstat(descriptor)
        named_after = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
        after = (
            opened_after.st_dev,
            opened_after.st_ino,
            opened_after.st_mode,
            opened_after.st_size,
            opened_after.st_mtime_ns,
            opened_after.st_ctime_ns,
        )
        named_identity = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_mode,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if before != after or before != named_identity or len(payload) != opened_after.st_size:
            raise AnfisAblationModelAuditError(
                f"Artifact changed while reading: {relative.as_posix()}"
            )
        record: dict[str, Any] = {
            "path": relative.as_posix(),
            "bytes": len(payload),
            "sha256": digest.hexdigest(),
        }
        if role is not None:
            record = {"role": role, **record}
        return payload, record
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def _strict_json(payload: bytes, *, label: str) -> dict[str, Any]:
    def reject_constant(value: str) -> Any:
        raise AnfisAblationModelAuditError(f"{label} contains non-finite JSON: {value}")

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AnfisAblationModelAuditError(f"{label} contains duplicate key: {key}")
            result[key] = value
        return result

    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=unique_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnfisAblationModelAuditError(f"{label} is not strict JSON") from error
    if not isinstance(decoded, dict):
        raise AnfisAblationModelAuditError(f"{label} must contain a JSON object")
    return decoded


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    try:
        encoded = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise AnfisAblationModelAuditError("JSON payload is not canonicalizable") from error
    return (encoded + "\n").encode("utf-8")


def _exact_typed_equal(observed: Any, expected: Any) -> bool:
    """Compare a decoded value without Python's bool/int/float aliases."""

    if type(observed) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(observed) == set(expected) and all(
            _exact_typed_equal(observed[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, (list, tuple)):
        return len(observed) == len(expected) and all(
            _exact_typed_equal(item, reference)
            for item, reference in zip(observed, expected, strict=True)
        )
    return bool(observed == expected)


def _entry_snapshot(path: Path) -> tuple[int, ...] | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    return (
        int(metadata.st_dev),
        int(metadata.st_ino),
        int(metadata.st_mode),
        int(metadata.st_nlink),
        int(metadata.st_size),
        int(metadata.st_mtime_ns),
        int(metadata.st_ctime_ns),
    )


def _namespace_paths(paths: trainer.SlotPaths) -> tuple[Path, ...]:
    return (*paths.finals, paths.pointer, *paths.temporaries, Path(f"{paths.pointer}.tmp"), paths.guard)


def _path_snapshot(paths: Sequence[Path]) -> dict[str, tuple[int, ...] | None]:
    return {path.as_posix(): _entry_snapshot(path) for path in paths}


def _validate_namespace(
    snapshot: Mapping[str, tuple[int, ...] | None], paths: trainer.SlotPaths
) -> bool:
    for final in paths.finals:
        metadata = snapshot.get(final.as_posix())
        if (
            metadata is None
            or not stat.S_ISREG(metadata[2])
            or stat.S_IMODE(metadata[2]) != 0o644
        ):
            raise AnfisAblationModelAuditError(
                f"Bundle final is absent, non-regular, or not mode 0644: {final.as_posix()}"
            )
    forbidden = (*paths.temporaries, Path(f"{paths.pointer}.tmp"), paths.guard)
    residue = [path.as_posix() for path in forbidden if snapshot.get(path.as_posix()) is not None]
    if residue:
        raise AnfisAblationModelAuditError(f"Bundle has temporary/guard residue: {residue}")
    pointer = snapshot.get(paths.pointer.as_posix())
    if pointer is not None and (
        not stat.S_ISREG(pointer[2]) or stat.S_IMODE(pointer[2]) != 0o644
    ):
        raise AnfisAblationModelAuditError(
            "Selection DVC pointer is non-regular or not mode 0644"
        )
    manifest_metadata = snapshot.get(paths.manifest.as_posix())
    output_metadata = [
        snapshot.get(path.as_posix())
        for path in paths.finals
        if path != paths.manifest
    ]
    if manifest_metadata is None or any(item is None for item in output_metadata):
        raise AnfisAblationModelAuditError("Bundle publication timestamps are incomplete")
    if int(manifest_metadata[5]) <= max(
        int(cast(tuple[int, ...], item)[5]) for item in output_metadata
    ):
        raise AnfisAblationModelAuditError(
            "Model manifest was not published physically after every output"
        )
    return pointer is not None


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise AnfisAblationModelAuditError("Manifest generated_at_utc is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AnfisAblationModelAuditError("Manifest generated_at_utc is malformed") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnfisAblationModelAuditError("Manifest timestamp is not timezone-aware")


def _load_runtime_contract(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, record = _read_regular_bytes(DEFAULT_RUNTIME, repo_root=repo_root)
    try:
        decoded = yaml.safe_load(payload)
    except yaml.YAMLError as error:
        raise AnfisAblationModelAuditError("E0-MT runtime is not valid YAML") from error
    if not isinstance(decoded, dict):
        raise AnfisAblationModelAuditError("E0-MT runtime must contain a mapping")
    if (
        decoded.get("gate") != "E0-MT"
        or decoded.get("status") != "ready_to_lock"
        or decoded.get("schema_version")
        != "closure_anfis_ablation_training_development_runtime_v1"
    ):
        raise AnfisAblationModelAuditError("E0-MT runtime identity/status drifted")
    return decoded, record


def _require_audit_authority(
    repo_root: Path, *, model_id: str, base_seed: int
) -> dict[str, Any]:
    from src.experiments.closure_anfis_ablation_model_manifest_patch import (
        require_anfis_ablation_model_manifest_authority,
    )

    authority = require_anfis_ablation_model_manifest_authority(
        model_id,
        base_seed,
        audit_current_unpublished=True,
        repo_root=repo_root,
    )
    if authority.get("gate") != "E0-MV" or authority.get("status") != "effective_preflight_passed":
        raise AnfisAblationModelAuditError("Effective E0-MV audit authority drifted")
    if (
        authority.get("authorized_model_id") != model_id
        or authority.get("authorized_base_seed") != base_seed
        or type(authority.get("authorized_base_seed")) is not int
        or type(authority.get("completed_prefix_count")) is not int
        or type(authority.get("slot_creation_prefix_count")) is not int
        or (model_id, base_seed) not in BUNDLE_SLOTS
        or int(authority["slot_creation_prefix_count"])
        != BUNDLE_SLOTS.index((model_id, base_seed))
        or not BUNDLE_SLOTS.index((model_id, base_seed))
        < int(authority["completed_prefix_count"])
        <= len(BUNDLE_SLOTS)
    ):
        raise AnfisAblationModelAuditError("E0-MV audit target/prefix binding drifted")
    required_true = (
        "model_bundle_audit_authorized",
        "target_access_through_2020_authorized",
        "selection_diagnostics_authorized",
    )
    forbidden = (
        "a0_development_fit_authorized",
        "a1_development_fit_authorized",
        "batch_slot_execution_authorized",
        "calibration_authorized",
        "calibration_target_access_authorized",
        "final_e7_metrics_authorized",
        "rollout_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "dvc_commands_authorized",
        "scientific_network_authorized",
        "outcome_access_authorized",
        "future_outcomes_accessed",
    )
    if any(authority.get(key) is not True for key in required_true) or any(
        authority.get(key) is not False for key in forbidden
    ):
        raise AnfisAblationModelAuditError("E0-MV audit authority matrix drifted")
    _authority_manifest_binding(authority)
    _slot_source_record(authority)
    return authority


def _authority_manifest_binding(authority: Mapping[str, Any]) -> dict[str, Any]:
    raw = authority.get("slot_manifest_authority")
    if not isinstance(raw, Mapping) or set(raw) != set(AUTHORITY_BINDING_KEYS):
        raise AnfisAblationModelAuditError(
            "E0-MV slot-manifest authority binding is incomplete"
        )
    binding = dict(raw)
    if (
        binding.get("gate") not in {"E0-MU", "E0-MV"}
        or binding.get("status") != "effective_preflight_passed"
        or binding.get("authorized_model_id") != authority.get("authorized_model_id")
        or binding.get("authorized_base_seed") != authority.get("authorized_base_seed")
        or type(binding.get("authorized_base_seed")) is not int
        or type(binding.get("completed_prefix_count")) is not int
        or type(binding.get("slot_creation_prefix_count")) is not int
        or binding.get("completed_prefix_count")
        != binding.get("slot_creation_prefix_count")
    ):
        raise AnfisAblationModelAuditError(
            "E0-MV slot-manifest authority binding drifted"
        )
    return binding


def _authority_record_specs(
    authority_binding: Mapping[str, Any],
) -> tuple[tuple[str, Path, str], ...]:
    gate = authority_binding.get("gate")
    if gate == "E0-MU":
        return HISTORICAL_AUTHORITY_RECORD_SPECS
    if gate == "E0-MV":
        return AUTHORITY_RECORD_SPECS
    raise AnfisAblationModelAuditError(
        "Slot-manifest authority record gate is unsupported"
    )


def _slot_source_record(authority: Mapping[str, Any]) -> dict[str, Any]:
    record = _validate_record_dialect(
        authority.get("slot_source_record"), label="slot_source_record"
    )
    if (
        record.get("role") != "trainer"
        or record.get("path") != "src/experiments/train_closure_anfis_ablation.py"
    ):
        raise AnfisAblationModelAuditError(
            "E0-MV slot source record path/role drifted"
        )
    return record


def _expected_contract_sections(
    runtime: Mapping[str, Any], *, model_id: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    def section(name: str) -> Mapping[str, Any]:
        value = runtime.get(name)
        if not isinstance(value, Mapping):
            raise AnfisAblationModelAuditError(
                f"E0-MT runtime contract section is incomplete: {name}"
            )
        return value

    targets = section("targets")
    inputs = section("inputs")
    preprocessing = section("preprocessing")
    model = section("model")
    roles = section("roles")
    model_inputs = inputs.get(model_id)
    if not isinstance(model_inputs, Mapping):
        raise AnfisAblationModelAuditError(
            f"E0-MT runtime input contract is incomplete: {model_id}"
        )
    target_contract = {
        "join_columns": list(targets["join_columns"]),
        "exact_projection": list(targets["exact_projection"]),
        "horizons_months": list(targets["horizons_months"]),
        "development_target_access_end": str(roles["model_selection_end"]),
        "calibration_target_values_opened": False,
        "raw_chlorophyll_projection": "forbidden",
    }
    role_counts = {
        "training": dict(targets["training"]),
        "model_selection": dict(targets["model_selection"]),
        "calibration_threshold_metadata_only": dict(targets["calibration_threshold_closed"]),
        "calibration_target_rows_read": 0,
        "test_target_rows_read": 0,
        "holdout_target_rows_read": 0,
        "post_2020_target_rows_read": 0,
    }
    architecture = {
        "history_length_months": int(inputs["history_length_months"]),
        "input_dimension": int(model_inputs["input_dimension"]),
        "family": model["family"],
        "common_architecture": dict(model["common_architecture"]),
        "loss": dict(model["loss"]),
        "selection": dict(model["selection"]),
        "optimization": dict(model["optimization"]),
        "execution": dict(model["execution"]),
    }
    return target_contract, role_counts, architecture, dict(preprocessing)


def _validate_record_dialect(record: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(record, Mapping) or set(record) != RECORD_KEYS:
        raise AnfisAblationModelAuditError(f"{label} record dialect drifted")
    role = record.get("role")
    path = record.get("path")
    size = record.get("bytes")
    sha256 = record.get("sha256")
    if (
        not isinstance(role, str)
        or not role
        or not isinstance(path, str)
        or not path
        or type(size) is not int
        or size < 0
        or not isinstance(sha256, str)
        or SHA256_PATTERN.fullmatch(sha256) is None
    ):
        raise AnfisAblationModelAuditError(f"{label} record values drifted")
    return dict(record)


def _runtime_target_records(runtime: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    authority = runtime.get("authority")
    records = authority.get("physical_inputs") if isinstance(authority, Mapping) else None
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise AnfisAblationModelAuditError("Runtime physical input inventory is absent")
    selected: dict[str, dict[str, Any]] = {}
    for raw in records:
        if isinstance(raw, Mapping) and raw.get("role") in SEALED_TARGET_ROLES:
            selected[str(raw["role"])] = dict(raw)
    if set(selected) != SEALED_TARGET_ROLES:
        raise AnfisAblationModelAuditError("Runtime sealed target records are incomplete")
    return selected


def _expected_input_roles_and_paths(
    *, model_id: str, base_seed: int, repo_root: Path
) -> tuple[tuple[str, str], ...]:
    sequence, pointer, summary, manifest = trainer.sequence_paths(
        model_id, base_seed, repo_root=repo_root
    )
    prefix = model_id.lower()
    expected = (
        (f"{prefix}_sequence", sequence),
        (f"{prefix}_sequence_pointer", pointer),
        (f"{prefix}_sequence_summary", summary),
        (f"{prefix}_sequence_manifest", manifest),
        (
            "common_origin",
            repo_root / "data/closure_v1/common_origin_manifest.parquet",
        ),
        (
            "common_origin_pointer",
            repo_root / "data/closure_v1/common_origin_manifest.parquet.dvc",
        ),
        (
            "common_origin_manifest",
            repo_root
            / "reports/closure_v1/01_surface/common_origin_manifest.json",
        ),
        ("development_targets", repo_root / trainer.TARGET_ARTIFACT),
        ("targets_pointer", repo_root / "data/targets.dvc"),
        ("target_manifest", repo_root / trainer.TARGET_MANIFEST),
    )
    return tuple(
        (role, _relative_repo_path(path, repo_root=repo_root).as_posix())
        for role, path in expected
    )


def _verify_input_records(
    records: Any,
    *,
    runtime: Mapping[str, Any],
    model_id: str,
    base_seed: int,
    repo_root: Path,
) -> list[dict[str, Any]]:
    expected = _expected_input_roles_and_paths(
        model_id=model_id, base_seed=base_seed, repo_root=repo_root
    )
    if (
        not isinstance(records, Sequence)
        or isinstance(records, (str, bytes))
        or len(records) != len(expected)
    ):
        raise AnfisAblationModelAuditError(
            "Manifest inputs must bind exactly ten ordered records"
        )
    sealed = _runtime_target_records(runtime)
    verified: list[dict[str, Any]] = []
    for index, ((expected_role, expected_path), raw) in enumerate(
        zip(expected, records, strict=True)
    ):
        record = _validate_record_dialect(raw, label=f"input[{index}]")
        role = str(record["role"])
        path = str(record["path"])
        if role != expected_role or path != expected_path:
            raise AnfisAblationModelAuditError(
                "Manifest input role/path ordering drifted"
            )
        if role in SEALED_TARGET_ROLES:
            if not _exact_typed_equal(record, sealed[role]):
                raise AnfisAblationModelAuditError(f"Sealed target record drifted: {role}")
            try:
                physical = {
                    "role": role,
                    **trainer._stable_file_record(
                        repo_root / expected_path, repo_root=repo_root
                    ),
                }
            except trainer.AnfisAblationTrainingError as error:
                raise AnfisAblationModelAuditError(str(error)) from error
            if not _exact_typed_equal(record, physical):
                raise AnfisAblationModelAuditError(
                    f"Sealed target record differs from disk: {role}"
                )
        else:
            _, physical = _read_regular_bytes(path, repo_root=repo_root, role=role)
            if not _exact_typed_equal(physical, record):
                raise AnfisAblationModelAuditError(f"Physical input record drifted: {path}")
        verified.append(record)
    return verified


def _verify_authority_records(
    records: Any,
    *,
    authority_binding: Mapping[str, Any],
    repo_root: Path,
) -> list[dict[str, Any]]:
    specs = _authority_record_specs(authority_binding)
    if (
        not isinstance(records, Sequence)
        or isinstance(records, (str, bytes))
        or len(records) != len(specs)
    ):
        raise AnfisAblationModelAuditError(
            "Manifest authority_records must bind runtime, lock, and companion"
        )
    verified: list[dict[str, Any]] = []
    for index, ((role, path, digest_key), raw) in enumerate(
        zip(specs, records, strict=True)
    ):
        record = _validate_record_dialect(raw, label=f"authority_records[{index}]")
        expected_path = path.as_posix()
        if record["role"] != role or record["path"] != expected_path:
            raise AnfisAblationModelAuditError(
                "Manifest authority record role/path ordering drifted"
            )
        _, physical = _read_regular_bytes(path, repo_root=repo_root, role=role)
        if not _exact_typed_equal(record, physical):
            raise AnfisAblationModelAuditError(
                f"Physical authority record drifted: {expected_path}"
            )
        if authority_binding.get(digest_key) != record["sha256"]:
            raise AnfisAblationModelAuditError(
                f"Authority record does not bind {digest_key}"
            )
        verified.append(record)
    return verified


def _verify_source_records(
    records: Any,
    *,
    repo_root: Path,
    slot_source_record: Mapping[str, Any] | None = None,
    allow_historical_source: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)) or not records:
        raise AnfisAblationModelAuditError("Manifest source_code must be a non-empty array")
    verified: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(records):
        record = _validate_record_dialect(raw, label=f"source_code[{index}]")
        if record["path"] in seen:
            raise AnfisAblationModelAuditError("Manifest source_code paths must be unique")
        seen.add(str(record["path"]))
        if slot_source_record is not None:
            expected = _validate_record_dialect(
                slot_source_record, label="slot_source_record"
            )
            if not _exact_typed_equal(record, expected):
                raise AnfisAblationModelAuditError(
                    "Manifest source_code differs from its slot source record"
                )
            if not allow_historical_source:
                _, physical = _read_regular_bytes(
                    str(record["path"]),
                    repo_root=repo_root,
                    role=str(record["role"]),
                )
                if not _exact_typed_equal(physical, record):
                    raise AnfisAblationModelAuditError(
                        f"Physical source record drifted: {record['path']}"
                    )
        else:
            _, physical = _read_regular_bytes(
                str(record["path"]), repo_root=repo_root, role=str(record["role"])
            )
            if not _exact_typed_equal(physical, record):
                raise AnfisAblationModelAuditError(
                    f"Physical source record drifted: {record['path']}"
                )
        verified.append(record)
    return verified


def _output_paths_by_role(paths: trainer.SlotPaths) -> dict[str, Path]:
    return {name: getattr(paths, name) for name in trainer.MODEL_OUTPUT_NAMES}


def _verify_output_records(
    records: Any, *, paths: trainer.SlotPaths, repo_root: Path
) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    expected = _output_paths_by_role(paths)
    if (
        not isinstance(records, Sequence)
        or isinstance(records, (str, bytes))
        or len(records) != len(expected)
    ):
        raise AnfisAblationModelAuditError("Manifest outputs must bind exactly seven pre-manifest finals")
    verified: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    for expected_role, raw in zip(expected, records, strict=True):
        record = _validate_record_dialect(raw, label=f"output[{expected_role}]")
        relative = _relative_repo_path(expected[expected_role], repo_root=repo_root).as_posix()
        if record["role"] != expected_role or record["path"] != relative:
            raise AnfisAblationModelAuditError("Manifest output role/path ordering drifted")
        payload, physical = _read_regular_bytes(
            expected[expected_role], repo_root=repo_root, role=expected_role
        )
        if not _exact_typed_equal(physical, record):
            raise AnfisAblationModelAuditError(
                f"Manifest output hash/size drifted: {expected_role}"
            )
        if not payload:
            raise AnfisAblationModelAuditError(f"Bundle output is empty: {expected_role}")
        verified.append(record)
        payloads[expected_role] = payload
    return verified, payloads


def _load_torch_artifact(
    payload: bytes,
    *,
    artifact_role: str,
    model_id: str,
    base_seed: int,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    torch = trainer._require_torch()
    try:
        decoded = torch.load(
            io.BytesIO(payload),
            map_location=torch.device("cpu"),
            weights_only=True,
        )
    except Exception as error:
        raise AnfisAblationModelAuditError(
            f"{artifact_role} cannot be decoded with weights_only"
        ) from error
    expected_keys = {
        "model_version",
        "experiment_id",
        "surface_id",
        "gate",
        "model_id",
        "base_seed",
        "upstream_state_seed",
        "device",
        "config",
        "bloom_training_priors",
        "risk_training_priors",
        "best_epoch",
        "best_model_selection_objective",
        "model_state_dict",
        "artifact_role",
    }
    if not isinstance(decoded, dict) or set(decoded) != expected_keys:
        raise AnfisAblationModelAuditError(
            f"{artifact_role} top-level key set drifted"
        )
    expected_scalars: dict[str, Any] = {
        "model_version": trainer.MODEL_VERSION,
        "experiment_id": "closure_v1",
        "surface_id": trainer.SURFACE_ID,
        "gate": "E0-MT",
        "model_id": model_id,
        "base_seed": base_seed,
        "upstream_state_seed": base_seed if model_id == "A1" else None,
        "device": trainer.LOCKED_DEVICE,
        "config": trainer._model_config(model_id),
        "artifact_role": artifact_role,
    }
    for key, expected in expected_scalars.items():
        if not _exact_typed_equal(decoded.get(key), expected):
            raise AnfisAblationModelAuditError(
                f"{artifact_role} field drifted: {key}"
            )
    for key, expected in (
        ("bloom_training_priors", trainer.EXPECTED_TRAINING_BLOOM_PRIORS),
        ("risk_training_priors", trainer.EXPECTED_TRAINING_RISK_PRIORS),
    ):
        observed = decoded.get(key)
        if not isinstance(observed, list) or len(observed) != len(expected):
            raise AnfisAblationModelAuditError(f"{artifact_role} priors drifted: {key}")
        if any(
            type(value) is not float
            or not math.isclose(
                float(value), float(reference), rel_tol=0.0, abs_tol=1e-15
            )
            for value, reference in zip(observed, expected, strict=True)
        ):
            raise AnfisAblationModelAuditError(f"{artifact_role} priors drifted: {key}")
    best_epoch = decoded.get("best_epoch")
    objective = decoded.get("best_model_selection_objective")
    if (
        type(best_epoch) is not int
        or not 1 <= best_epoch <= trainer.MAXIMUM_EPOCHS
        or type(objective) is not float
        or not math.isfinite(float(objective))
        or float(objective) < 0.0
    ):
        raise AnfisAblationModelAuditError(
            f"{artifact_role} checkpoint selection fields drifted"
        )
    state = decoded.get("model_state_dict")
    expected_shapes = {
        "gru.weight_ih_l0": (3 * trainer.HIDDEN_DIMENSION, len(trainer.input_columns(model_id))),
        "gru.weight_hh_l0": (3 * trainer.HIDDEN_DIMENSION, trainer.HIDDEN_DIMENSION),
        "gru.bias_ih_l0": (3 * trainer.HIDDEN_DIMENSION,),
        "gru.bias_hh_l0": (3 * trainer.HIDDEN_DIMENSION,),
        "bloom_delta.weight": (len(trainer.HORIZONS), trainer.HIDDEN_DIMENSION),
        "bloom_delta.bias": (len(trainer.HORIZONS),),
        "risk_delta.weight": (len(trainer.HORIZONS), trainer.HIDDEN_DIMENSION),
        "risk_delta.bias": (len(trainer.HORIZONS),),
        "risk_logvar.weight": (len(trainer.HORIZONS), trainer.HIDDEN_DIMENSION),
        "risk_logvar.bias": (len(trainer.HORIZONS),),
        "bloom_prior_logits": (len(trainer.HORIZONS),),
        "risk_prior_logits": (len(trainer.HORIZONS),),
    }
    if not isinstance(state, Mapping) or set(state) != set(expected_shapes):
        raise AnfisAblationModelAuditError(f"{artifact_role} state_dict keys drifted")
    for name, shape in expected_shapes.items():
        tensor = state[name]
        if (
            not isinstance(tensor, torch.Tensor)
            or tuple(tensor.shape) != shape
            or tensor.dtype != torch.float32
            or tensor.device.type != "cpu"
            or not bool(torch.isfinite(tensor).all())
        ):
            raise AnfisAblationModelAuditError(
                f"{artifact_role} state tensor drifted: {name}"
            )
    expected_bloom_logits = torch.tensor(
        trainer._logit(np.asarray(trainer.EXPECTED_TRAINING_BLOOM_PRIORS)),
        dtype=torch.float32,
    )
    expected_risk_logits = torch.tensor(
        trainer._logit(np.asarray(trainer.EXPECTED_TRAINING_RISK_PRIORS)),
        dtype=torch.float32,
    )
    if not torch.equal(state["bloom_prior_logits"], expected_bloom_logits) or not torch.equal(
        state["risk_prior_logits"], expected_risk_logits
    ):
        raise AnfisAblationModelAuditError(
            f"{artifact_role} prior buffers drifted"
        )
    return decoded, cast(Mapping[str, Any], state)


def _validate_model_and_checkpoint(
    model_payload: bytes,
    checkpoint_payload: bytes,
    *,
    model_id: str,
    base_seed: int,
    metrics_objective: float,
) -> tuple[int, float, Mapping[str, Any]]:
    model, model_state = _load_torch_artifact(
        model_payload,
        artifact_role="final_restored_model",
        model_id=model_id,
        base_seed=base_seed,
    )
    checkpoint, checkpoint_state = _load_torch_artifact(
        checkpoint_payload,
        artifact_role="raw_best_checkpoint",
        model_id=model_id,
        base_seed=base_seed,
    )
    metadata_keys = set(model) - {"artifact_role", "model_state_dict"}
    if any(
        not _exact_typed_equal(model[key], checkpoint[key])
        for key in metadata_keys
    ):
        raise AnfisAblationModelAuditError(
            "Model/checkpoint metadata differ beyond artifact_role"
        )
    torch = trainer._require_torch()
    if any(
        not torch.equal(model_state[key], checkpoint_state[key])
        for key in model_state
    ):
        raise AnfisAblationModelAuditError(
            "Final model and raw best checkpoint state_dict differ"
        )
    objective = float(model["best_model_selection_objective"])
    if not math.isclose(objective, metrics_objective, rel_tol=0.0, abs_tol=1e-7):
        raise AnfisAblationModelAuditError(
            "Model checkpoint objective differs from selection metrics"
        )
    return int(model["best_epoch"]), objective, model_state


def _validate_predictions_from_restored_model(
    *,
    state_dict: Mapping[str, Any],
    preprocessor: Mapping[str, Any],
    predictions: pd.DataFrame,
    model_id: str,
    base_seed: int,
    repo_root: Path,
) -> None:
    origin_rows = (
        predictions.loc[predictions["horizon_months"].eq(trainer.HORIZONS[0])]
        .loc[
            :,
            [
                "source_id",
                "site_id",
                "common_origin_id",
                "time_role",
                "origin_year_month",
            ],
        ]
        .reset_index(drop=True)
    )
    if len(origin_rows) != trainer.EXPECTED_SELECTION_ORIGINS:
        raise AnfisAblationModelAuditError(
            "Selection origins cannot reconstruct the restored model input"
        )
    sequence, _, _ = trainer._sequence_frame(
        model_id=model_id, base_seed=base_seed, repo_root=repo_root
    )
    sequence_index = sequence.set_index("common_origin_id")
    if not sequence_index.index.is_unique:
        raise AnfisAblationModelAuditError(
            "Sealed sequence common-origin identity is duplicated"
        )
    try:
        selected = sequence_index.loc[
            origin_rows["common_origin_id"].astype(str).tolist()
        ].reset_index()
    except KeyError as error:
        raise AnfisAblationModelAuditError(
            "Selection origin is absent from its sealed sequence bundle"
        ) from error
    for column in ("source_id", "site_id", "time_role", "origin_year_month"):
        if selected[column].astype(str).tolist() != origin_rows[column].astype(str).tolist():
            raise AnfisAblationModelAuditError(
                "Selection prediction/sequence identity drifted"
            )
    raw_columns = preprocessor.get("columns")
    if not isinstance(raw_columns, Sequence) or isinstance(raw_columns, (str, bytes)):
        raise AnfisAblationModelAuditError("Preprocessor raw statistics are unavailable")
    standardizer = trainer.RawStandardizer(
        columns=tuple(str(row["column"]) for row in raw_columns),
        counts=np.asarray([int(row["observed_count"]) for row in raw_columns], dtype=np.int64),
        means=np.asarray([float(row["mean"]) for row in raw_columns], dtype=np.float64),
        standard_deviations=np.asarray(
            [float(row["standard_deviation"]) for row in raw_columns], dtype=np.float64
        ),
    )
    raw_tensor = trainer._tensor_from_sequence(selected, model_id=model_id)
    transformed = trainer.apply_mask_aware_standardizer(raw_tensor, standardizer)
    bloom_priors = np.asarray(
        preprocessor["bloom_training_priors"], dtype=np.float64
    )
    risk_priors = np.asarray(preprocessor["risk_training_priors"], dtype=np.float64)
    model = trainer.make_anfis_ablation_model(
        input_dimension=len(trainer.input_columns(model_id)),
        bloom_priors=bloom_priors,
        risk_priors=risk_priors,
    )
    try:
        model.load_state_dict(dict(state_dict), strict=True)
    except (RuntimeError, ValueError) as error:
        raise AnfisAblationModelAuditError(
            "Restored model state cannot load into the sealed architecture"
        ) from error
    torch = trainer._require_torch()
    torch.set_num_threads(1)
    dummy = np.zeros((len(origin_rows), len(trainer.HORIZONS)), dtype=np.float64)
    selection_bundle = trainer.TrainingBundle(origin_rows, transformed, dummy, dummy)
    with threadpool_limits(limits=1):
        bloom_probability, risk_mu, risk_logvar = trainer._predict_arrays(
            model, selection_bundle, device=torch.device("cpu")
        )
    expected_bloom = predictions.pivot(
        index="common_origin_id",
        columns="horizon_months",
        values="predicted_bloom_probability",
    ).loc[origin_rows["common_origin_id"], list(trainer.HORIZONS)].to_numpy(dtype=np.float64)
    expected_risk = predictions.pivot(
        index="common_origin_id",
        columns="horizon_months",
        values="predicted_risk",
    ).loc[origin_rows["common_origin_id"], list(trainer.HORIZONS)].to_numpy(dtype=np.float64)
    expected_sigma = predictions.pivot(
        index="common_origin_id",
        columns="horizon_months",
        values="predicted_risk_sigma",
    ).loc[origin_rows["common_origin_id"], list(trainer.HORIZONS)].to_numpy(dtype=np.float64)
    recomputed_sigma = np.asarray(
        [
            [
                math.sqrt(
                    math.exp(
                        float(
                            np.clip(
                                risk_logvar[row, column],
                                trainer.LOGVAR_MIN,
                                trainer.LOGVAR_MAX,
                            )
                        )
                    )
                )
                for column in range(len(trainer.HORIZONS))
            ]
            for row in range(len(origin_rows))
        ],
        dtype=np.float64,
    )
    if (
        not np.array_equal(bloom_probability, expected_bloom)
        or not np.array_equal(risk_mu, expected_risk)
        or not np.array_equal(recomputed_sigma, expected_sigma)
    ):
        raise AnfisAblationModelAuditError(
            "Selection predictions do not come from the restored model/preprocessor"
        )


def _validate_training_curve(
    payload: bytes,
    *,
    training_metadata: pd.DataFrame,
    base_seed: int,
    best_epoch: int,
    best_objective: float,
) -> dict[str, Any]:
    try:
        frame = pd.read_csv(io.BytesIO(payload), float_precision="round_trip")
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as error:
        raise AnfisAblationModelAuditError("Training curve CSV cannot be decoded") from error
    expected_columns = [
        "epoch",
        "training_loss",
        "model_selection_objective",
        "best_objective",
        "best_epoch",
        "epochs_without_improvement",
        "batch_order_sha256",
    ]
    if (
        frame.columns.tolist() != expected_columns
        or not 1 <= len(frame) <= trainer.MAXIMUM_EPOCHS
        or payload != trainer._csv_bytes(frame)
    ):
        raise AnfisAblationModelAuditError("Training curve dialect/canonical bytes drifted")
    integer_columns = ("epoch", "best_epoch", "epochs_without_improvement")
    for column in integer_columns:
        if not pd.api.types.is_integer_dtype(frame[column].dtype):
            raise AnfisAblationModelAuditError(
                f"Training curve integer field drifted: {column}"
            )
    if frame["epoch"].tolist() != list(range(1, len(frame) + 1)):
        raise AnfisAblationModelAuditError("Training curve epochs are not contiguous")
    numeric_columns = ("training_loss", "model_selection_objective", "best_objective")
    for column in numeric_columns:
        if not pd.api.types.is_float_dtype(frame[column].dtype):
            raise AnfisAblationModelAuditError(
                f"Training curve floating field drifted: {column}"
            )
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=np.float64)
        if not np.isfinite(values).all():
            raise AnfisAblationModelAuditError(
                f"Training curve contains nonfinite {column}"
            )
    if bool((frame["model_selection_objective"].astype(float) < 0.0).any()):
        raise AnfisAblationModelAuditError("Training curve objective is negative")
    raw_digests = frame["batch_order_sha256"].tolist()
    if any(type(value) is not str for value in raw_digests):
        raise AnfisAblationModelAuditError("Training curve batch digests drifted")
    digests = cast(list[str], raw_digests)
    if any(SHA256_PATTERN.fullmatch(value) is None for value in digests) or len(
        set(digests)
    ) != len(digests):
        raise AnfisAblationModelAuditError("Training curve batch digests drifted")
    expected_digests = [
        trainer.canonical_epoch_batches(
            training_metadata,
            base_seed=base_seed,
            epoch=epoch,
        )[1]
        for epoch in range(1, len(frame) + 1)
    ]
    if digests != expected_digests:
        raise AnfisAblationModelAuditError(
            "Training curve batch digests differ from the sealed cohort/seed"
        )
    expected_best = math.inf
    expected_epoch = 0
    expected_stale = 0
    for index, row in frame.iterrows():
        epoch = int(row["epoch"])
        objective = float(row["model_selection_objective"])
        if objective < expected_best - trainer.EARLY_STOPPING_MINIMUM_DELTA:
            expected_best = objective
            expected_epoch = epoch
            expected_stale = 0
        else:
            expected_stale += 1
        if (
            not math.isclose(
                float(row["best_objective"]), expected_best, rel_tol=0.0, abs_tol=1e-12
            )
            or int(row["best_epoch"]) != expected_epoch
            or int(row["epochs_without_improvement"]) != expected_stale
        ):
            raise AnfisAblationModelAuditError(
                "Training curve early-stopping recurrence drifted"
            )
        if expected_stale >= trainer.EARLY_STOPPING_PATIENCE and index != len(frame) - 1:
            raise AnfisAblationModelAuditError(
                "Training curve continued after early stopping"
            )
    if len(frame) < trainer.MAXIMUM_EPOCHS and expected_stale < trainer.EARLY_STOPPING_PATIENCE:
        raise AnfisAblationModelAuditError(
            "Training curve ended before its fixed stop condition"
        )
    if expected_epoch != best_epoch or not math.isclose(
        expected_best, best_objective, rel_tol=0.0, abs_tol=1e-12
    ):
        raise AnfisAblationModelAuditError(
            "Training curve does not bind the restored checkpoint"
        )
    return {
        "epochs": len(frame),
        "best_epoch": expected_epoch,
        "best_objective": expected_best,
        "batch_order_sha256": digests,
    }


def _expected_report(
    *, model_id: str, base_seed: int, best_epoch: int, best_objective: float
) -> bytes:
    return "\n".join(
        [
            f"# Closure V1 ANFIS ablation {model_id} seed {base_seed}",
            "",
            "Status: `completed`",
            "",
            f"Best epoch: `{best_epoch}`",
            f"Best model-selection objective: `{best_objective:.12g}`",
            f"Training origins: `{trainer.EXPECTED_TRAINING_ORIGINS}`",
            f"Model-selection origins: `{trainer.EXPECTED_SELECTION_ORIGINS}`",
            "",
            "Targets are limited to development rows through 2020-12.",
            "Calibration 2021, holdout, E0-M, E0-U and final E7 claims were not accessed.",
            "",
        ]
    ).encode("utf-8")


def _digest_rows(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for values in frame.loc[:, list(columns)].itertuples(index=False, name=None):
        digest.update(
            json.dumps(list(values), ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(
                "utf-8"
            )
            + b"\n"
        )
    return digest.hexdigest()


def _reconstruct_training_metadata(*, repo_root: Path) -> pd.DataFrame:
    common_path = Path("data/closure_v1/common_origin_manifest.parquet")
    payload, _ = _read_regular_bytes(common_path, repo_root=repo_root)
    columns = (
        "source_id",
        "site_id",
        "common_origin_id",
        "assignment_role",
        "time_role",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
        "complete_targets_evaluable",
    )
    try:
        frame = pq.read_table(pa.BufferReader(payload), columns=list(columns)).to_pandas()
    except (pa.ArrowException, OSError) as error:
        raise AnfisAblationModelAuditError(
            "Common-origin training identity cannot be decoded"
        ) from error
    training = frame.loc[
        frame["assignment_role"].eq("development")
        & frame["time_role"].eq("training")
        & frame["complete_targets_evaluable"].eq(True)
        & frame["origin_year_month"].astype(str).le("2018-12")
        & frame["target_year_month"].astype(str).le("2018-12")
    ].copy()
    if (
        len(training) != trainer.EXPECTED_TRAINING_TARGET_ROWS
        or training["common_origin_id"].nunique() != trainer.EXPECTED_TRAINING_ORIGINS
        or training.duplicated(
            ["source_id", "site_id", "origin_year_month", "horizon_months"]
        ).any()
        or set(pd.to_numeric(training["horizon_months"], errors="coerce").astype(int))
        != set(trainer.HORIZONS)
    ):
        raise AnfisAblationModelAuditError(
            "Common-origin training identity denominator drifted"
        )
    origins = (
        training.loc[
            :,
            [
                "source_id",
                "site_id",
                "common_origin_id",
                "time_role",
                "origin_year_month",
            ],
        ]
        .drop_duplicates()
        .sort_values(
            ["source_id", "site_id", "origin_year_month", "common_origin_id"],
            kind="mergesort",
        )
        .reset_index(drop=True)
    )
    if len(origins) != trainer.EXPECTED_TRAINING_ORIGINS:
        raise AnfisAblationModelAuditError(
            "Common-origin training identity is not one row per origin"
        )
    return origins


def _training_identity_sha256(training_metadata: pd.DataFrame) -> str:
    return _digest_rows(
        training_metadata,
        (
            "source_id",
            "site_id",
            "common_origin_id",
            "time_role",
            "origin_year_month",
        ),
    )


def _reconstruct_training_identity_sha256(*, repo_root: Path) -> str:
    return _training_identity_sha256(
        _reconstruct_training_metadata(repo_root=repo_root)
    )


def load_cutoff_target_reference(*, repo_root: Path) -> CutoffTargetReference:
    """Load the exact WQP development <=2020 target projection once."""

    common_payload, _ = _read_regular_bytes(
        Path("data/closure_v1/common_origin_manifest.parquet"), repo_root=repo_root
    )
    try:
        common = pq.read_table(
            pa.BufferReader(common_payload),
            columns=["source_id", "site_id", "assignment_role"],
        ).to_pandas()
    except (pa.ArrowException, OSError) as error:
        raise AnfisAblationModelAuditError(
            "Development site inventory cannot be decoded"
        ) from error
    development_sites = sorted(
        set(
            common.loc[
                common["source_id"].eq("wqp")
                & common["assignment_role"].eq("development"),
                "site_id",
            ].astype(str)
        )
    )
    if not development_sites:
        raise AnfisAblationModelAuditError("Development site inventory is empty")
    target_path = repo_root / trainer.TARGET_ARTIFACT
    try:
        frame, raw_record = trainer._read_target_projection(
            target_path,
            development_site_ids=development_sites,
            repo_root=repo_root,
        )
    except trainer.AnfisAblationTrainingError as error:
        raise AnfisAblationModelAuditError(str(error)) from error
    identity = _entry_snapshot(target_path)
    if identity is None or not stat.S_ISREG(identity[2]):
        raise AnfisAblationModelAuditError(
            "Development target identity is absent or non-regular"
        )
    record = {"role": "development_targets", **raw_record}
    return CutoffTargetReference(frame=frame, record=record, identity=identity)


def _validate_selection_targets_against_reference(
    predictions: pd.DataFrame,
    *,
    reference: CutoffTargetReference,
    repo_root: Path,
) -> str:
    target_path = repo_root / trainer.TARGET_ARTIFACT
    if _entry_snapshot(target_path) != reference.identity:
        raise AnfisAblationModelAuditError(
            "Development target identity changed during bundle audit"
        )
    observed = predictions.loc[
        :,
        [*trainer.TARGET_JOIN_COLUMNS, "observed_bloom", "observed_risk"],
    ].copy()
    try:
        joined = observed.merge(
            reference.frame,
            on=list(trainer.TARGET_JOIN_COLUMNS),
            how="left",
            validate="one_to_one",
            sort=False,
        )
    except pd.errors.MergeError as error:
        raise AnfisAblationModelAuditError(
            "Selection prediction/target key cardinality drifted"
        ) from error
    if (
        len(joined) != trainer.EXPECTED_SELECTION_TARGET_ROWS
        or joined[["bloom_h", "target_risk_chla_h"]].isna().any().any()
        or not np.array_equal(
            joined["observed_bloom"].to_numpy(dtype=np.int8),
            joined["bloom_h"].to_numpy(dtype=np.int8),
        )
        or not np.array_equal(
            joined["observed_risk"].to_numpy(dtype=np.float64),
            joined["target_risk_chla_h"].to_numpy(dtype=np.float64),
        )
    ):
        raise AnfisAblationModelAuditError(
            "Selection labels differ from the sealed <=2020 target projection"
        )
    canonical = predictions.loc[
        :,
        [
            "source_id",
            "site_id",
            "common_origin_id",
            "time_role",
            "origin_year_month",
            "target_year_month",
            "horizon_months",
            "observed_bloom",
            "observed_risk",
        ],
    ]
    if _entry_snapshot(target_path) != reference.identity:
        raise AnfisAblationModelAuditError(
            "Development target identity changed during label comparison"
        )
    return _digest_rows(canonical, canonical.columns.tolist())


def _validate_selection_predictions(
    payload: bytes, *, model_id: str, base_seed: int
) -> tuple[dict[str, Any], str, str, pd.DataFrame]:
    try:
        table = pq.read_table(pa.BufferReader(payload))
    except (pa.ArrowException, OSError) as error:
        raise AnfisAblationModelAuditError("Selection predictions cannot be decoded") from error
    expected_schema = trainer.prediction_arrow_schema()
    if not table.schema.equals(expected_schema, check_metadata=True):
        raise AnfisAblationModelAuditError("Selection prediction Arrow schema drifted")
    frame = table.to_pandas()
    try:
        canonical = trainer.canonical_prediction_frame(frame)
        expected_table = trainer.prediction_arrow_table(canonical)
    except trainer.AnfisAblationTrainingError as error:
        raise AnfisAblationModelAuditError(str(error)) from error
    if not table.equals(expected_table):
        raise AnfisAblationModelAuditError("Selection predictions are not canonically ordered")
    if len(canonical) != trainer.EXPECTED_SELECTION_TARGET_ROWS:
        raise AnfisAblationModelAuditError("Selection prediction row denominator drifted")
    if canonical["common_origin_id"].nunique() != trainer.EXPECTED_SELECTION_ORIGINS:
        raise AnfisAblationModelAuditError("Selection complete-origin denominator drifted")
    if set(canonical["model_id"].astype(str)) != {model_id} or set(
        canonical["base_seed"].astype(int)
    ) != {base_seed}:
        raise AnfisAblationModelAuditError("Selection prediction slot identity drifted")
    if set(canonical["surface_id"].astype(str)) != {trainer.SURFACE_ID} or set(
        canonical["source_id"].astype(str)
    ) != {"wqp"}:
        raise AnfisAblationModelAuditError("Selection prediction surface/source drifted")
    origin_months = canonical["origin_year_month"].astype(str)
    target_months = canonical["target_year_month"].astype(str)
    if (
        not origin_months.between("2019-01", "2020-12").all()
        or not target_months.between("2019-01", "2020-12").all()
    ):
        raise AnfisAblationModelAuditError(
            "Selection predictions leave the sealed model_selection interval"
        )
    horizon_counts = canonical.groupby("horizon_months", sort=True).size().to_dict()
    if horizon_counts != {horizon: trainer.EXPECTED_SELECTION_ORIGINS for horizon in trainer.HORIZONS}:
        raise AnfisAblationModelAuditError("Selection horizon denominator drifted")
    positives = tuple(
        int(
            canonical.loc[
                canonical["horizon_months"].eq(horizon), "observed_bloom"
            ].sum()
        )
        for horizon in trainer.HORIZONS
    )
    if positives != tuple(trainer.EXPECTED_SELECTION_BLOOM_POSITIVES):
        raise AnfisAblationModelAuditError("Selection bloom denominator/positives drifted")
    risk_means = tuple(
        float(
            canonical.loc[
                canonical["horizon_months"].eq(horizon), "observed_risk"
            ].mean()
        )
        for horizon in trainer.HORIZONS
    )
    if any(
        not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-15)
        for observed, expected in zip(
            risk_means, trainer.EXPECTED_SELECTION_RISK_MEANS, strict=True
        )
    ):
        raise AnfisAblationModelAuditError("Selection risk target means drifted")
    identity_columns = (
        "source_id",
        "site_id",
        "common_origin_id",
        "time_role",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
    )
    selection_identity = _digest_rows(canonical, identity_columns)
    selection_targets = _digest_rows(
        canonical, (*identity_columns, "observed_bloom", "observed_risk")
    )
    return {
        "rows": len(canonical),
        "origins": canonical["common_origin_id"].nunique(),
        "horizon_rows": {str(key): int(value) for key, value in horizon_counts.items()},
        "bloom_positives": {
            str(horizon): value
            for horizon, value in zip(trainer.HORIZONS, positives, strict=True)
        },
        "risk_means": {
            str(horizon): value
            for horizon, value in zip(trainer.HORIZONS, risk_means, strict=True)
        },
    }, selection_identity, selection_targets, canonical


def _validate_preprocessor_json(
    payload: bytes, *, model_id: str, base_seed: int
) -> dict[str, Any]:
    decoded = _strict_json(payload, label="preprocessor")
    if payload != _canonical_json(decoded):
        raise AnfisAblationModelAuditError("Preprocessor JSON is not canonical")
    flattened = json.dumps(decoded, ensure_ascii=False, allow_nan=False).lower()
    if "calibration_threshold" in flattened or "holdout" in flattened or "post_2020" in flattened:
        raise AnfisAblationModelAuditError("Preprocessor contains a forbidden role/outcome binding")
    expected_keys = {
        "version",
        "fit_role",
        "calculation_dtype",
        "serialization_dtype",
        "variance_ddof",
        "epsilon",
        "missing_transport_after_transform",
        "columns",
        "model_id",
        "base_seed",
        "input_columns",
        "identity_channels",
        "bloom_training_priors",
        "risk_training_priors",
        "calibration_used",
    }
    if set(decoded) != expected_keys:
        raise AnfisAblationModelAuditError("Preprocessor key set drifted")
    expected_scalars: dict[str, Any] = {
        "version": "closure_mask_aware_training_standardization_v1",
        "fit_role": "training",
        "calculation_dtype": "float64",
        "serialization_dtype": "float32",
        "variance_ddof": 0,
        "epsilon": trainer.PREPROCESSOR_EPSILON,
        "missing_transport_after_transform": 0.0,
        "model_id": model_id,
        "base_seed": base_seed,
        "input_columns": list(trainer.input_columns(model_id)),
        "identity_channels": list(trainer.input_columns(model_id)[trainer.RAW_DIMENSION :]),
        "calibration_used": False,
    }
    for key, expected in expected_scalars.items():
        if not _exact_typed_equal(decoded.get(key), expected):
            raise AnfisAblationModelAuditError(f"Preprocessor field drifted: {key}")
    for key, expected_values in (
        ("bloom_training_priors", trainer.EXPECTED_TRAINING_BLOOM_PRIORS),
        ("risk_training_priors", trainer.EXPECTED_TRAINING_RISK_PRIORS),
    ):
        observed_values = decoded.get(key)
        if not isinstance(observed_values, list) or len(observed_values) != len(
            expected_values
        ):
            raise AnfisAblationModelAuditError(f"Preprocessor field drifted: {key}")
        for value, reference in zip(observed_values, expected_values, strict=True):
            if type(value) is not float or not math.isclose(
                float(value), float(reference), rel_tol=0.0, abs_tol=1e-15
            ):
                raise AnfisAblationModelAuditError(f"Preprocessor field drifted: {key}")
    columns = decoded.get("columns")
    if not isinstance(columns, list) or len(columns) != trainer.RAW_DIMENSION:
        raise AnfisAblationModelAuditError("Preprocessor raw statistic rows drifted")
    for row, column in zip(columns, trainer.RAW_STANDARDIZATION_COLUMNS, strict=True):
        expected_count, expected_mean, expected_std = trainer.EXPECTED_RAW_STANDARDIZATION[column]
        if not isinstance(row, Mapping) or set(row) != {
            "column",
            "observed_count",
            "mean",
            "standard_deviation",
        }:
            raise AnfisAblationModelAuditError("Preprocessor raw statistic dialect drifted")
        normalized_row = cast(Mapping[str, Any], row)
        count_value = normalized_row.get("observed_count")
        mean_value = normalized_row.get("mean")
        std_value = normalized_row.get("standard_deviation")
        if (
            type(count_value) is not int
            or type(mean_value) is not float
            or type(std_value) is not float
        ):
            raise AnfisAblationModelAuditError("Preprocessor raw statistic is nonnumeric")
        if (
            not _exact_typed_equal(normalized_row.get("column"), column)
            or count_value != expected_count
            or not math.isclose(float(mean_value), expected_mean, rel_tol=0.0, abs_tol=1e-12)
            or not math.isclose(
                float(std_value), expected_std, rel_tol=0.0, abs_tol=1e-12
            )
        ):
            raise AnfisAblationModelAuditError(f"Preprocessor raw statistic drifted: {column}")
    return decoded


def _validate_selection_metrics(
    payload: bytes,
    *,
    model_id: str,
    base_seed: int,
    predictions: pd.DataFrame,
    preprocessor: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        frame = pd.read_csv(io.BytesIO(payload), float_precision="round_trip")
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as error:
        raise AnfisAblationModelAuditError("Selection metrics CSV cannot be decoded") from error
    if payload != trainer._csv_bytes(frame):
        raise AnfisAblationModelAuditError(
            "Selection metrics CSV is not byte-canonical"
        )
    expected_columns = [
        "model_id",
        "base_seed",
        "horizon_months",
        "time_role",
        "rows",
        "bloom_positive",
        "brier",
        "pr_auc",
        "rmse",
        "mae",
        "prior_brier",
        "prior_rmse",
        "prior_mae",
        "brier_ratio",
        "rmse_ratio",
        "mae_ratio",
        "checkpoint_objective",
    ]
    if frame.columns.tolist() != expected_columns or len(frame) != len(trainer.HORIZONS):
        raise AnfisAblationModelAuditError("Selection metrics columns/rows drifted")
    integer_columns = ("base_seed", "horizon_months", "rows", "bloom_positive")
    for column in integer_columns:
        if not pd.api.types.is_integer_dtype(frame[column].dtype):
            raise AnfisAblationModelAuditError(
                f"Selection metrics integer field drifted: {column}"
            )
    floating_columns = (
        "brier",
        "pr_auc",
        "rmse",
        "mae",
        "prior_brier",
        "prior_rmse",
        "prior_mae",
        "brier_ratio",
        "rmse_ratio",
        "mae_ratio",
        "checkpoint_objective",
    )
    for column in floating_columns:
        if not pd.api.types.is_float_dtype(frame[column].dtype):
            raise AnfisAblationModelAuditError(
                f"Selection metrics floating field drifted: {column}"
            )
        values = frame[column].to_numpy(dtype=np.float64)
        if not np.isfinite(values).all():
            raise AnfisAblationModelAuditError(
                f"Selection metrics contains nonfinite {column}"
            )
    if any(type(value) is not str for value in frame["model_id"].tolist()) or any(
        type(value) is not str for value in frame["time_role"].tolist()
    ):
        raise AnfisAblationModelAuditError("Selection metrics string field drifted")
    if not frame["model_id"].eq(model_id).all() or not frame["base_seed"].eq(base_seed).all():
        raise AnfisAblationModelAuditError("Selection metrics slot identity drifted")
    if not frame["time_role"].eq("model_selection").all() or frame[
        "horizon_months"
    ].astype(int).tolist() != list(trainer.HORIZONS):
        raise AnfisAblationModelAuditError("Selection metrics role/horizon drifted")
    bloom_priors = [float(value) for value in preprocessor["bloom_training_priors"]]
    risk_priors = [float(value) for value in preprocessor["risk_training_priors"]]
    recomputed: list[dict[str, float | int]] = []
    ratios: list[float] = []
    for index, horizon in enumerate(trainer.HORIZONS):
        selected = predictions.loc[predictions["horizon_months"].eq(horizon)]
        observed_bloom = selected["observed_bloom"].to_numpy(dtype="float64")
        observed_risk = selected["observed_risk"].to_numpy(dtype="float64")
        predicted_bloom = selected["predicted_bloom_probability"].to_numpy(dtype="float64")
        predicted_risk = selected["predicted_risk"].to_numpy(dtype="float64")
        brier = float(((predicted_bloom - observed_bloom) ** 2).mean())
        error = predicted_risk - observed_risk
        rmse = float((error**2).mean() ** 0.5)
        mae = float(abs(error).mean())
        prior_brier = float(((bloom_priors[index] - observed_bloom) ** 2).mean())
        prior_error = risk_priors[index] - observed_risk
        prior_rmse = float((prior_error**2).mean() ** 0.5)
        prior_mae = float(abs(prior_error).mean())
        row_ratios = (
            brier / max(prior_brier, trainer.PREPROCESSOR_EPSILON),
            rmse / max(prior_rmse, trainer.PREPROCESSOR_EPSILON),
            mae / max(prior_mae, trainer.PREPROCESSOR_EPSILON),
        )
        ratios.extend(row_ratios)
        recomputed.append(
            {
                "rows": len(selected),
                "bloom_positive": int(observed_bloom.sum()),
                "brier": brier,
                "pr_auc": float(average_precision_score(observed_bloom, predicted_bloom)),
                "rmse": rmse,
                "mae": mae,
                "prior_brier": prior_brier,
                "prior_rmse": prior_rmse,
                "prior_mae": prior_mae,
                "brier_ratio": row_ratios[0],
                "rmse_ratio": row_ratios[1],
                "mae_ratio": row_ratios[2],
            }
        )
    objective = sum(ratios) / len(ratios)
    for index, expected in enumerate(recomputed):
        row = frame.iloc[index]
        for key, value in expected.items():
            if type(value) is int:
                valid = int(row[key]) == value
            else:
                valid = math.isclose(
                    float(row[key]), value, rel_tol=0.0, abs_tol=1e-12
                )
            if not valid:
                raise AnfisAblationModelAuditError(f"Selection metric drifted: {key}")
        if not math.isclose(
            float(row["checkpoint_objective"]), objective, rel_tol=0.0, abs_tol=1e-12
        ):
            raise AnfisAblationModelAuditError("Selection checkpoint objective drifted")
    return {"rows": len(frame), "checkpoint_objective": objective}


def _validate_pointer(payload: bytes | None, *, prediction_payload: bytes, prediction_name: str) -> dict[str, Any]:
    if payload is None:
        return {"registration_state": "pre_dvc", "pointer_present": False}
    pattern = re.compile(
        rb"outs:\n- md5: (?P<md5>[0-9a-f]{32})\n"
        rb"  size: (?P<size>0|[1-9][0-9]*)\n"
        rb"  hash: md5\n  path: "
        + re.escape(prediction_name.encode("utf-8"))
        + rb"\n"
    )
    match = pattern.fullmatch(payload)
    expected_md5 = hashlib.md5(prediction_payload, usedforsecurity=False).hexdigest()
    if (
        match is None
        or match.group("md5").decode("ascii") != expected_md5
        or int(match.group("size")) != len(prediction_payload)
    ):
        raise AnfisAblationModelAuditError("Selection DVC pointer does not bind its payload")
    return {
        "registration_state": "post_dvc",
        "pointer_present": True,
        "payload_md5": expected_md5,
        "pointer_payload_binding_verified": True,
    }


def _validate_manifest_semantics(
    manifest: Mapping[str, Any],
    *,
    model_id: str,
    base_seed: int,
    runtime: Mapping[str, Any],
    authority_binding: Mapping[str, Any],
    training_identity_sha256: str,
    selection_identity_sha256: str,
    selection_target_sha256: str,
) -> None:
    if set(manifest) != MANIFEST_KEYS:
        raise AnfisAblationModelAuditError("Model manifest top-level keys drifted")
    expected_scalars = {
        "manifest_version": trainer.MANIFEST_VERSION,
        "status": "completed",
        "slot_status": "available",
        "fit_status": "passed",
        "experiment_id": "closure_v1",
        "surface_id": trainer.SURFACE_ID,
        "model_id": model_id,
        "base_seed": base_seed,
        "device": trainer.LOCKED_DEVICE,
        "future_outcomes_accessed": False,
        "calibration_authorized": False,
        "calibration_target_accessed": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "dvc_command_executed": False,
        "completion_marker_written_last": True,
    }
    for key, expected in expected_scalars.items():
        if not _exact_typed_equal(manifest.get(key), expected):
            raise AnfisAblationModelAuditError(f"Model manifest field drifted: {key}")
    _validate_timestamp(manifest.get("generated_at_utc"))
    target, roles, architecture, preprocessing = _expected_contract_sections(
        runtime, model_id=model_id
    )
    expected_sections = {
        "target_contract": target,
        "role_counts": roles,
        "architecture": architecture,
        "preprocessing": preprocessing,
        "authority": dict(authority_binding),
    }
    for key, expected in expected_sections.items():
        if not _exact_typed_equal(manifest.get(key), expected):
            raise AnfisAblationModelAuditError(f"Model manifest section drifted: {key}")
    pairing = manifest.get("pairing")
    if not isinstance(pairing, Mapping) or set(pairing) != PAIRING_KEYS:
        raise AnfisAblationModelAuditError("Model manifest pairing dialect drifted")
    expected_pairing = {
        "policy": runtime["slots"]["pairing_policy"],
        "paired_model_ids": list(trainer.MODEL_IDS),
        "base_seed": base_seed,
    }
    for key, expected in expected_pairing.items():
        if not _exact_typed_equal(pairing.get(key), expected):
            raise AnfisAblationModelAuditError(f"Model pairing field drifted: {key}")
    for key in (
        "training_identity_sha256",
        "selection_identity_sha256",
        "selection_target_sha256",
    ):
        value = pairing.get(key)
        if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
            raise AnfisAblationModelAuditError(f"Model pairing digest drifted: {key}")
    if pairing["selection_identity_sha256"] != selection_identity_sha256:
        raise AnfisAblationModelAuditError("Selection identity digest differs from Parquet")
    if pairing["selection_target_sha256"] != selection_target_sha256:
        raise AnfisAblationModelAuditError("Selection target digest differs from Parquet")
    if pairing["training_identity_sha256"] != training_identity_sha256:
        raise AnfisAblationModelAuditError(
            "Training identity digest differs from common-origin cohort"
        )


def validate_anfis_ablation_model_bundle_semantics(
    *,
    model_id: str,
    base_seed: int,
    authority_binding: Mapping[str, Any],
    runtime: Mapping[str, Any],
    repo_root: Path = PROJECT_ROOT,
    allow_pointer: bool,
    target_reference: CutoffTargetReference | None = None,
    slot_source_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one physical bundle without consulting the effective loader.

    This is the non-recursive semantic core used by prefix progression.  It is
    deliberately free of Git, remote, DVC-command and authority-loader calls.
    """

    if type(allow_pointer) is not bool:
        raise AnfisAblationModelAuditError(
            "Selection DVC pointer policy must be an exact boolean"
        )
    trainer.validate_model_seed(model_id, base_seed)
    live_runtime, runtime_record = _load_runtime_contract(repo_root)
    if not _exact_typed_equal(dict(runtime), live_runtime):
        raise AnfisAblationModelAuditError(
            "Supplied runtime differs from physical E0-MT runtime"
        )
    if set(authority_binding) != set(AUTHORITY_BINDING_KEYS):
        raise AnfisAblationModelAuditError("Supplied authority binding key set drifted")
    authority_gate = authority_binding.get("gate")
    if authority_gate not in {"E0-MU", "E0-MV"}:
        raise AnfisAblationModelAuditError("Supplied authority binding gate drifted")
    if authority_gate == "E0-MU" and slot_source_record is None:
        raise AnfisAblationModelAuditError(
            "Historical slot source record is required"
        )
    paths = trainer.slot_paths(model_id, base_seed, repo_root=repo_root)
    namespace = _namespace_paths(paths)
    before = _path_snapshot(namespace)
    pointer_present = _validate_namespace(before, paths)
    if pointer_present and not allow_pointer:
        raise AnfisAblationModelAuditError(
            "Selection DVC pointer is forbidden in the current progression state"
        )
    if os.path.lexists(repo_root / OUTCOME_ACCESS_LOG):
        raise AnfisAblationModelAuditError("Outcome access log must remain absent before E0-M")

    manifest_payload, manifest_record = _read_regular_bytes(
        paths.manifest, repo_root=repo_root, role="manifest"
    )
    manifest = _strict_json(manifest_payload, label="model manifest")
    if not manifest or next(reversed(manifest)) != "completion_marker_written_last":
        raise AnfisAblationModelAuditError("Manifest completion marker is not the final key")
    if manifest_payload != _canonical_json(manifest):
        raise AnfisAblationModelAuditError("Model manifest is not canonical JSON")
    verified_inputs = _verify_input_records(
        manifest.get("inputs"),
        runtime=live_runtime,
        model_id=model_id,
        base_seed=base_seed,
        repo_root=repo_root,
    )
    reference = (
        target_reference
        if target_reference is not None
        else load_cutoff_target_reference(repo_root=repo_root)
    )
    sealed_targets = _runtime_target_records(live_runtime)["development_targets"]
    if reference.record != sealed_targets:
        raise AnfisAblationModelAuditError(
            "Cutoff target reference differs from the sealed runtime record"
        )
    verified_authority = _verify_authority_records(
        manifest.get("authority_records"),
        authority_binding=authority_binding,
        repo_root=repo_root,
    )
    verified_source = _verify_source_records(
        manifest.get("source_code"),
        repo_root=repo_root,
        slot_source_record=slot_source_record,
        allow_historical_source=authority_gate == "E0-MU",
    )
    script_record = _validate_record_dialect(manifest.get("script"), label="script")
    if len(verified_source) != 1 or script_record != verified_source[0] or script_record.get(
        "role"
    ) != "trainer" or script_record.get("path") != (
        "src/experiments/train_closure_anfis_ablation.py"
    ):
        raise AnfisAblationModelAuditError("Manifest script/source_code binding drifted")
    _, live_source_record = _read_regular_bytes(
        str(script_record["path"]),
        repo_root=repo_root,
        role=str(script_record["role"]),
    )
    verified_outputs, output_payloads = _verify_output_records(
        manifest.get("outputs"), paths=paths, repo_root=repo_root
    )
    preprocessor = _validate_preprocessor_json(
        output_payloads["preprocessor"], model_id=model_id, base_seed=base_seed
    )
    prediction_counts, selection_identity, selection_targets, prediction_frame = _validate_selection_predictions(
        output_payloads["selection_predictions"], model_id=model_id, base_seed=base_seed
    )
    physical_selection_targets = _validate_selection_targets_against_reference(
        prediction_frame, reference=reference, repo_root=repo_root
    )
    if physical_selection_targets != selection_targets:
        raise AnfisAblationModelAuditError(
            "Selection target digest differs from the physical projection"
        )
    metric_counts = _validate_selection_metrics(
        output_payloads["selection_metrics"],
        model_id=model_id,
        base_seed=base_seed,
        predictions=prediction_frame,
        preprocessor=preprocessor,
    )
    training_metadata = _reconstruct_training_metadata(repo_root=repo_root)
    training_identity = _training_identity_sha256(training_metadata)
    best_epoch, best_objective, model_state = _validate_model_and_checkpoint(
        output_payloads["model"],
        output_payloads["checkpoint"],
        model_id=model_id,
        base_seed=base_seed,
        metrics_objective=float(metric_counts["checkpoint_objective"]),
    )
    _validate_predictions_from_restored_model(
        state_dict=model_state,
        preprocessor=preprocessor,
        predictions=prediction_frame,
        model_id=model_id,
        base_seed=base_seed,
        repo_root=repo_root,
    )
    training_curve = _validate_training_curve(
        output_payloads["training_curve"],
        training_metadata=training_metadata,
        base_seed=base_seed,
        best_epoch=best_epoch,
        best_objective=best_objective,
    )
    if output_payloads["report"] != _expected_report(
        model_id=model_id,
        base_seed=base_seed,
        best_epoch=best_epoch,
        best_objective=best_objective,
    ):
        raise AnfisAblationModelAuditError("Model report deterministic content drifted")
    _validate_manifest_semantics(
        manifest,
        model_id=model_id,
        base_seed=base_seed,
        runtime=live_runtime,
        authority_binding=authority_binding,
        training_identity_sha256=training_identity,
        selection_identity_sha256=selection_identity,
        selection_target_sha256=selection_targets,
    )
    pointer_payload: bytes | None = None
    if pointer_present:
        pointer_payload, _ = _read_regular_bytes(paths.pointer, repo_root=repo_root)
    registration = _validate_pointer(
        pointer_payload,
        prediction_payload=output_payloads["selection_predictions"],
        prediction_name=paths.selection_predictions.name,
    )
    post_manifest_payload, post_manifest_record = _read_regular_bytes(
        paths.manifest, repo_root=repo_root, role="manifest"
    )
    if post_manifest_payload != manifest_payload or not _exact_typed_equal(
        post_manifest_record, manifest_record
    ):
        raise AnfisAblationModelAuditError("Model manifest changed during audit")
    post_inputs = _verify_input_records(
        manifest.get("inputs"),
        runtime=live_runtime,
        model_id=model_id,
        base_seed=base_seed,
        repo_root=repo_root,
    )
    if not _exact_typed_equal(post_inputs, verified_inputs):
        raise AnfisAblationModelAuditError("Model inputs changed during audit")
    post_target = next(
        (
            record
            for record in post_inputs
            if record.get("role") == "development_targets"
        ),
        None,
    )
    if not _exact_typed_equal(post_target, reference.record):
        raise AnfisAblationModelAuditError(
            "Development target digest changed during audit"
        )
    post_authority = _verify_authority_records(
        manifest.get("authority_records"),
        authority_binding=authority_binding,
        repo_root=repo_root,
    )
    if not _exact_typed_equal(post_authority, verified_authority):
        raise AnfisAblationModelAuditError("Model authority records changed during audit")
    post_source = _verify_source_records(
        manifest.get("source_code"),
        repo_root=repo_root,
        slot_source_record=slot_source_record,
        allow_historical_source=authority_gate == "E0-MU",
    )
    if not _exact_typed_equal(post_source, verified_source):
        raise AnfisAblationModelAuditError("Model source records changed during audit")
    _, post_live_source_record = _read_regular_bytes(
        str(script_record["path"]),
        repo_root=repo_root,
        role=str(script_record["role"]),
    )
    if not _exact_typed_equal(post_live_source_record, live_source_record):
        raise AnfisAblationModelAuditError("Physical trainer source changed during audit")
    post_outputs, _ = _verify_output_records(
        manifest.get("outputs"), paths=paths, repo_root=repo_root
    )
    if not _exact_typed_equal(post_outputs, verified_outputs):
        raise AnfisAblationModelAuditError("Model outputs changed during audit")
    if pointer_present:
        post_pointer_payload, _ = _read_regular_bytes(
            paths.pointer, repo_root=repo_root
        )
        if post_pointer_payload != pointer_payload:
            raise AnfisAblationModelAuditError(
                "Selection DVC pointer changed during audit"
            )
    _, post_runtime = _read_regular_bytes(DEFAULT_RUNTIME, repo_root=repo_root)
    if not _exact_typed_equal(post_runtime, runtime_record):
        raise AnfisAblationModelAuditError("E0-MT runtime changed during audit")
    if os.path.lexists(repo_root / OUTCOME_ACCESS_LOG):
        raise AnfisAblationModelAuditError("Outcome access log appeared during audit")
    if _entry_snapshot(repo_root / trainer.TARGET_ARTIFACT) != reference.identity:
        raise AnfisAblationModelAuditError(
            "Development target identity changed before audit completion"
        )
    after = _path_snapshot(namespace)
    if after != before:
        raise AnfisAblationModelAuditError("Selected model namespace changed during audit")
    return {
        "audit_version": AUDIT_VERSION,
        "status": "passed",
        "model_id": model_id,
        "base_seed": base_seed,
        "manifest": manifest_record,
        "inputs": verified_inputs,
        "authority_records": verified_authority,
        "source_code": verified_source,
        "outputs": verified_outputs,
        "training_curve": training_curve,
        "selection": prediction_counts,
        "selection_metrics": metric_counts,
        "pairing": dict(manifest["pairing"]),
        "dvc_registration": registration,
        "schema_exact": True,
        "hash_bindings_verified": True,
        "calibration_targets_read": False,
        "test_or_holdout_targets_read": False,
        "future_outcomes_accessed": False,
        "dvc_command_executed": False,
        "scientific_network_egress": False,
        "writes_performed": False,
    }


def audit_anfis_ablation_model_bundle(
    *,
    model_id: str,
    base_seed: int,
    repo_root: Path = PROJECT_ROOT,
    authority: Mapping[str, Any] | None = None,
    runtime: Mapping[str, Any] | None = None,
    target_reference: CutoffTargetReference | None = None,
) -> dict[str, Any]:
    """Validate one completed slot behind the published read-only authority."""

    effective = _require_audit_authority(
        repo_root, model_id=model_id, base_seed=base_seed
    )
    if authority is not None and not _exact_typed_equal(dict(authority), effective):
        raise AnfisAblationModelAuditError(
            "Injected authority differs from live E0-MV authority"
        )
    live_runtime, _ = _load_runtime_contract(repo_root)
    if runtime is not None and not _exact_typed_equal(dict(runtime), live_runtime):
        raise AnfisAblationModelAuditError(
            "Injected runtime differs from physical E0-MT runtime"
        )
    live_target_reference = load_cutoff_target_reference(repo_root=repo_root)
    if target_reference is not None and (
        type(target_reference) is not CutoffTargetReference
        or not _exact_typed_equal(
            target_reference.record, live_target_reference.record
        )
        or not _exact_typed_equal(
            target_reference.identity, live_target_reference.identity
        )
        or not target_reference.frame.equals(live_target_reference.frame)
    ):
        raise AnfisAblationModelAuditError(
            "Injected cutoff target reference differs from physical targets"
        )
    return validate_anfis_ablation_model_bundle_semantics(
        model_id=model_id,
        base_seed=base_seed,
        authority_binding=_authority_manifest_binding(effective),
        runtime=live_runtime,
        repo_root=repo_root,
        allow_pointer=True,
        target_reference=live_target_reference,
        slot_source_record=_slot_source_record(effective),
    )


def _validate_paired_results(results: Sequence[Mapping[str, Any]]) -> None:
    if [(result.get("model_id"), result.get("base_seed")) for result in results] != list(
        BUNDLE_SLOTS
    ):
        raise AnfisAblationModelAuditError("A0/A1 audit slot order/prefix drifted")
    common_reference: tuple[str, str, str] | None = None
    for index in range(0, len(results), 2):
        a0, a1 = results[index : index + 2]
        pair0 = a0.get("pairing")
        pair1 = a1.get("pairing")
        if not isinstance(pair0, Mapping) or not isinstance(pair1, Mapping):
            raise AnfisAblationModelAuditError("A0/A1 pairing evidence is absent")
        digests0 = (
            str(pair0.get("training_identity_sha256")),
            str(pair0.get("selection_identity_sha256")),
            str(pair0.get("selection_target_sha256")),
        )
        digests1 = (
            str(pair1.get("training_identity_sha256")),
            str(pair1.get("selection_identity_sha256")),
            str(pair1.get("selection_target_sha256")),
        )
        if digests0 != digests1:
            raise AnfisAblationModelAuditError("A0/A1 paired denominators/targets drifted")
        if common_reference is None:
            common_reference = digests0
        elif digests0 != common_reference:
            raise AnfisAblationModelAuditError("Direct target cohort differs across model seeds")


def audit_all_anfis_ablation_model_bundles(
    *, repo_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Audit the exact ten-slot paired family and prove global non-mutation."""

    all_paths = tuple(
        path
        for model_id, base_seed in BUNDLE_SLOTS
        for path in _namespace_paths(trainer.slot_paths(model_id, base_seed, repo_root=repo_root))
    )
    before = _path_snapshot(all_paths)
    target_reference = load_cutoff_target_reference(repo_root=repo_root)
    results = [
        audit_anfis_ablation_model_bundle(
            model_id=model_id,
            base_seed=base_seed,
            repo_root=repo_root,
            target_reference=target_reference,
        )
        for model_id, base_seed in BUNDLE_SLOTS
    ]
    _validate_paired_results(results)
    if _path_snapshot(all_paths) != before:
        raise AnfisAblationModelAuditError("Ten-slot namespace changed during paired audit")
    return {
        "audit_version": AUDIT_VERSION,
        "status": "passed",
        "slot_count": len(results),
        "ordered_slots": [
            {"model_id": model_id, "base_seed": base_seed}
            for model_id, base_seed in BUNDLE_SLOTS
        ],
        "slots": results,
        "paired_target_identity_verified": True,
        "calibration_targets_read": False,
        "future_outcomes_accessed": False,
        "dvc_command_executed": False,
        "scientific_network_egress": False,
        "writes_performed": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true")
    target.add_argument("--model-id", choices=trainer.MODEL_IDS)
    parser.add_argument("--base-seed", type=int)
    parser.add_argument("--check-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    if args.all and args.base_seed is not None:
        parser.error("--base-seed cannot be combined with --all")
    if not args.all and args.base_seed is None:
        parser.error("--base-seed is required with --model-id")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.all:
        result = audit_all_anfis_ablation_model_bundles(repo_root=PROJECT_ROOT)
    else:
        result = audit_anfis_ablation_model_bundle(
            model_id=str(args.model_id),
            base_seed=int(args.base_seed),
            repo_root=PROJECT_ROOT,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
