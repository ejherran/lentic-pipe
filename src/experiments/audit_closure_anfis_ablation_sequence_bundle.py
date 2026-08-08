#!/usr/bin/env python
"""Reconstruct and audit one Closure V1 A0/A1 input-only bundle read-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import pyarrow as pa
import pyarrow.parquet as pq

from src.experiments.build_closure_anfis_ablation_sequences import (
    EXPECTED_COMMON_ROWS,
    EXPECTED_DEVELOPMENT_LOCATIONS,
    EXPECTED_INTENT_ORIGINS,
    EXPECTED_ROLE_COUNTS,
    BUNDLE_SLOTS,
    OUTCOME_ACCESS_LOG,
    AnfisAblationSequenceBuildError,
    BundlePaths,
    _audit_counts,
    _authority_manifest_binding,
    _json_bytes,
    _load_runtime_after_gate,
    _manifest_payload,
    _open_real_repository_parent,
    _read_input_frames,
    _repo_relative,
    _stable_file_record,
    _summary_bytes,
    build_anfis_ablation_sequences,
    bundle_paths,
    sequence_arrow_table,
    validate_model_seed,
)


AUDIT_VERSION = "closure_anfis_ablation_sequence_bundle_audit_v1"
BUILDER_PATH = Path("src/experiments/build_closure_anfis_ablation_sequences.py")


class AnfisAblationSequenceAuditError(ValueError):
    """Raised when a physical A0/A1 bundle differs from reconstruction."""


def _convert_build_error(error: Exception) -> AnfisAblationSequenceAuditError:
    return AnfisAblationSequenceAuditError(str(error))


def _require_audit_authority(
    repo_root: Path,
    *,
    model_id: str,
    base_seed: int | None,
) -> dict[str, Any]:
    from src.experiments.closure_anfis_ablation_sequence_development_patch import (
        load_effective_anfis_ablation_sequence_development_authority,
    )

    authority = load_effective_anfis_ablation_sequence_development_authority(
        model_id,
        base_seed,
        audit_current_unpublished=True,
        repo_root=repo_root,
    )
    if authority.get("gate") != "E0-MS" or authority.get("status") != "effective_preflight_passed":
        raise AnfisAblationSequenceAuditError("Effective E0-MS audit authority drifted")
    # This is a non-mutating reconstruction mode, not a widened experimental
    # authorization.  The published audit flag therefore remains false.
    if authority.get("sequence_bundle_audit_authorized") is not False:
        raise AnfisAblationSequenceAuditError("E0-MS audit flag was unexpectedly broadened")
    forbidden_true = (
        "temporal_fit_authorized",
        "target_access_authorized",
        "calibration_authorized",
        "metrics_authorized",
        "rollout_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "dvc_commands_authorized",
        "scientific_network_authorized",
        "outcome_access_authorized",
        "future_outcomes_accessed",
    )
    if any(authority.get(key) is not False for key in forbidden_true):
        raise AnfisAblationSequenceAuditError("E0-MS audit authority broadened an operation")
    if (
        authority.get("authorized_model_id") != model_id
        or authority.get("authorized_base_seed") != base_seed
        or type(authority.get("completed_prefix_count")) is not int
        or type(authority.get("slot_creation_prefix_count")) is not int
        or (model_id, base_seed) not in BUNDLE_SLOTS
        or not BUNDLE_SLOTS.index((model_id, base_seed))
        < int(authority["completed_prefix_count"])
        <= len(BUNDLE_SLOTS)
        or int(authority["slot_creation_prefix_count"])
        != BUNDLE_SLOTS.index((model_id, base_seed))
        or authority.get("audit_current_unpublished") is not True
    ):
        raise AnfisAblationSequenceAuditError("E0-MS audit target binding drifted")
    return authority


def _read_regular_bytes(path: Path, *, repo_root: Path) -> tuple[bytes, dict[str, Any]]:
    """Read bytes through one O_NOFOLLOW descriptor and bind the live name."""

    try:
        parent_fd, lexical = _open_real_repository_parent(path, repo_root=repo_root, create=False)
    except AnfisAblationSequenceBuildError as error:
        raise _convert_build_error(error) from error
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        named_before = os.stat(lexical.name, dir_fd=parent_fd, follow_symlinks=False)
        descriptor = os.open(lexical.name, flags, dir_fd=parent_fd)
        opened_before = os.fstat(descriptor)
        before = (
            opened_before.st_dev,
            opened_before.st_ino,
            opened_before.st_size,
            opened_before.st_mtime_ns,
            opened_before.st_ctime_ns,
        )
        if not stat.S_ISREG(named_before.st_mode) or not stat.S_ISREG(opened_before.st_mode) or (
            named_before.st_dev,
            named_before.st_ino,
        ) != (opened_before.st_dev, opened_before.st_ino):
            raise AnfisAblationSequenceAuditError(f"Audit input is not a regular file: {path}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        payload = b"".join(chunks)
        opened_after = os.fstat(descriptor)
        named_after = os.stat(lexical.name, dir_fd=parent_fd, follow_symlinks=False)
        if before != (
            opened_after.st_dev,
            opened_after.st_ino,
            opened_after.st_size,
            opened_after.st_mtime_ns,
            opened_after.st_ctime_ns,
        ) or before != (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        ) or len(payload) != opened_after.st_size:
            raise AnfisAblationSequenceAuditError(f"Audit input changed while reading: {path}")
        return payload, {
            "path": _repo_relative(lexical, repo_root),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)


def _strict_json(payload: bytes, *, label: str) -> dict[str, Any]:
    def reject_constant(value: str) -> Any:
        raise AnfisAblationSequenceAuditError(f"{label} contains non-finite JSON: {value}")

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AnfisAblationSequenceAuditError(f"{label} contains duplicate key: {key}")
            result[key] = value
        return result

    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=unique_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnfisAblationSequenceAuditError(f"{label} is not strict JSON") from error
    if not isinstance(decoded, dict):
        raise AnfisAblationSequenceAuditError(f"{label} must contain a JSON object")
    return decoded


def _namespace_paths(paths: BundlePaths) -> tuple[Path, ...]:
    return (
        *paths.finals,
        paths.pointer,
        paths.guard,
        *(Path(f"{path.as_posix()}.tmp") for path in (*paths.finals, paths.pointer)),
    )


def _path_snapshot(paths: Sequence[Path]) -> dict[str, tuple[int, ...] | None]:
    snapshot: dict[str, tuple[int, ...] | None] = {}
    for path in paths:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            snapshot[path.as_posix()] = None
            continue
        snapshot[path.as_posix()] = (
            int(metadata.st_dev),
            int(metadata.st_ino),
            int(metadata.st_mode),
            int(metadata.st_nlink),
            int(metadata.st_size),
            int(metadata.st_mtime_ns),
            int(metadata.st_ctime_ns),
        )
    return snapshot


def _validate_namespace(snapshot: Mapping[str, tuple[int, ...] | None], paths: BundlePaths) -> bool:
    for final in paths.finals:
        metadata = snapshot.get(final.as_posix())
        if metadata is None or not stat.S_ISREG(metadata[2]):
            raise AnfisAblationSequenceAuditError(f"Bundle final is absent or non-regular: {final}")
    pointer = snapshot.get(paths.pointer.as_posix())
    if pointer is not None and not stat.S_ISREG(pointer[2]):
        raise AnfisAblationSequenceAuditError("DVC pointer is not a regular file")
    forbidden = (
        paths.guard,
        *(Path(f"{path.as_posix()}.tmp") for path in (*paths.finals, paths.pointer)),
    )
    present = [path.as_posix() for path in forbidden if snapshot.get(path.as_posix()) is not None]
    if present:
        raise AnfisAblationSequenceAuditError(f"Bundle has temporary/guard residue: {present}")
    return pointer is not None


def _validate_pointer(
    payload: bytes | None,
    record: Mapping[str, Any] | None,
    *,
    sequence_payload: bytes,
    sequence_name: str,
) -> dict[str, Any]:
    if payload is None:
        return {
            "registration_state": "pre_dvc",
            "pointer_present": False,
            "pointer_payload_binding_verified": False,
        }
    pattern = re.compile(
        rb"outs:\n"
        rb"- md5: (?P<md5>[0-9a-f]{32})\n"
        rb"  size: (?P<size>0|[1-9][0-9]*)\n"
        rb"  hash: md5\n"
        + rb"  path: "
        + re.escape(sequence_name.encode("utf-8"))
        + rb"\n"
    )
    match = pattern.fullmatch(payload)
    if match is None:
        raise AnfisAblationSequenceAuditError("DVC pointer dialect drifted")
    expected_md5 = hashlib.md5(sequence_payload, usedforsecurity=False).hexdigest()
    if (
        match.group("md5").decode("ascii") != expected_md5
        or int(match.group("size")) != len(sequence_payload)
    ):
        raise AnfisAblationSequenceAuditError("DVC pointer does not bind the sequence payload")
    return {
        "registration_state": "post_dvc",
        "pointer_present": True,
        "pointer": dict(record or {}),
        "payload_md5": expected_md5,
        "pointer_payload_binding_verified": True,
    }


def _validate_manifest_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise AnfisAblationSequenceAuditError("Bundle manifest timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AnfisAblationSequenceAuditError("Bundle manifest timestamp is malformed") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnfisAblationSequenceAuditError("Bundle manifest timestamp is not timezone-aware")


def audit_anfis_ablation_sequence_bundle(
    *,
    model_id: str,
    base_seed: int | None,
    repo_root: Path = PROJECT_ROOT,
    authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconstruct without writes, DVC, targets, or scientific-network egress."""

    # This effective target-aware loader is deliberately the first operation.
    effective = _require_audit_authority(
        repo_root,
        model_id=model_id,
        base_seed=base_seed,
    )
    if authority is not None and dict(authority) != effective:
        raise AnfisAblationSequenceAuditError("Injected audit authority differs from live authority")
    try:
        _load_runtime_after_gate(repo_root)
        authority_binding = _authority_manifest_binding(effective)
        # The build manifest records the prefix *before* its target.  The
        # read-only audit loader reports the now-completed prefix, which may
        # include later triples, so reconstruct the original slot-local value.
        authority_binding["completed_prefix_count"] = int(
            effective["slot_creation_prefix_count"]
        )
        validate_model_seed(model_id, base_seed)
        paths = bundle_paths(model_id, base_seed, repo_root=repo_root)
    except AnfisAblationSequenceBuildError as error:
        raise _convert_build_error(error) from error

    namespace = _namespace_paths(paths)
    before = _path_snapshot(namespace)
    pointer_present = _validate_namespace(before, paths)
    if os.path.lexists(repo_root / OUTCOME_ACCESS_LOG):
        raise AnfisAblationSequenceAuditError("Outcome access log must remain absent before E0-M")

    try:
        common, panel, state, input_records, input_paths = _read_input_frames(
            model_id=model_id,
            base_seed=base_seed,
            repo_root=repo_root,
        )
        expected_frame, build_audit = build_anfis_ablation_sequences(
            common,
            panel,
            model_id=model_id,
            base_seed=base_seed,
            adaptive_state=state,
            expected_common_rows=EXPECTED_COMMON_ROWS,
            expected_intent_origins=EXPECTED_INTENT_ORIGINS,
            expected_development_locations=EXPECTED_DEVELOPMENT_LOCATIONS,
            expected_source_ids={"wqp"},
            expected_role_counts=EXPECTED_ROLE_COUNTS,
        )
        expected_table = sequence_arrow_table(expected_frame, model_id=model_id)
        source_record = _stable_file_record(repo_root / BUILDER_PATH, repo_root=repo_root)
    except AnfisAblationSequenceBuildError as error:
        raise _convert_build_error(error) from error

    sequence_payload, sequence_record = _read_regular_bytes(paths.parquet, repo_root=repo_root)
    summary_payload, summary_record = _read_regular_bytes(paths.summary, repo_root=repo_root)
    manifest_payload, manifest_record = _read_regular_bytes(paths.manifest, repo_root=repo_root)
    pointer_payload: bytes | None = None
    pointer_record: dict[str, Any] | None = None
    if pointer_present:
        pointer_payload, pointer_record = _read_regular_bytes(paths.pointer, repo_root=repo_root)

    try:
        actual_table = pq.read_table(pa.BufferReader(sequence_payload))
    except (pa.ArrowException, OSError) as error:
        raise AnfisAblationSequenceAuditError("Sequence Parquet cannot be decoded") from error
    if not actual_table.schema.equals(expected_table.schema, check_metadata=True):
        raise AnfisAblationSequenceAuditError("Sequence Arrow schema differs from the exact contract")
    if not actual_table.equals(expected_table):
        raise AnfisAblationSequenceAuditError("Sequence values differ from input-only reconstruction")
    if summary_payload != _summary_bytes(expected_frame):
        raise AnfisAblationSequenceAuditError("Bundle summary differs from reconstruction")

    manifest = _strict_json(manifest_payload, label="bundle manifest")
    if not manifest or next(reversed(manifest)) != "completion_marker_written_last":
        raise AnfisAblationSequenceAuditError("Bundle completion marker is not the final key")
    _validate_manifest_timestamp(manifest.get("generated_at_utc"))
    expected_manifest = _manifest_payload(
        model_id=model_id,
        base_seed=base_seed,
        audit=build_audit,
        authority=authority_binding,
        inputs=input_records,
        source_code=[source_record],
        outputs=[sequence_record, summary_record],
    )
    expected_manifest["generated_at_utc"] = manifest.get("generated_at_utc")
    if manifest != expected_manifest or manifest_payload != _json_bytes(expected_manifest):
        raise AnfisAblationSequenceAuditError("Bundle manifest differs from physical reconstruction")

    registration = _validate_pointer(
        pointer_payload,
        pointer_record,
        sequence_payload=sequence_payload,
        sequence_name=paths.parquet.name,
    )
    try:
        post_inputs = [_stable_file_record(path, repo_root=repo_root) for path in input_paths]
        post_source = _stable_file_record(repo_root / BUILDER_PATH, repo_root=repo_root)
    except AnfisAblationSequenceBuildError as error:
        raise _convert_build_error(error) from error
    if post_inputs != input_records or post_source != source_record:
        raise AnfisAblationSequenceAuditError("Reconstruction inputs/source changed during audit")
    if os.path.lexists(repo_root / OUTCOME_ACCESS_LOG):
        raise AnfisAblationSequenceAuditError("Outcome access log appeared during audit")
    after = _path_snapshot(namespace)
    if after != before:
        raise AnfisAblationSequenceAuditError("Selected bundle namespace changed during audit")

    return {
        "audit_version": AUDIT_VERSION,
        "status": "passed",
        "model_id": model_id,
        "base_seed": base_seed,
        "counts": _audit_counts(build_audit),
        "sequence": sequence_record,
        "summary": summary_record,
        "manifest": manifest_record,
        "dvc_registration": registration,
        "schema_exact": True,
        "values_reconstructed": True,
        "targets_read": False,
        "future_outcomes_accessed": False,
        "dvc_command_executed": False,
        "git_remote_verification": True,
        "network_commands_run": True,
        "scientific_network_egress": False,
        "writes_performed": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", choices=("A0", "A1"), required=True)
    parser.add_argument("--base-seed", type=int)
    parser.add_argument("--check-only", action="store_true", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    # Keep the effective target-aware audit loader first after argument parsing.
    authority = _require_audit_authority(
        PROJECT_ROOT,
        model_id=args.model_id,
        base_seed=args.base_seed,
    )
    result = audit_anfis_ablation_sequence_bundle(
        model_id=args.model_id,
        base_seed=args.base_seed,
        repo_root=PROJECT_ROOT,
        authority=authority,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
