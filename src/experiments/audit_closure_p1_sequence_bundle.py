#!/usr/bin/env python
"""Reopen and audit the immutable Closure V1 P1 seed 1729 sequence bundle."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.experiments import audit_closure_p0_sequence_bundle as secure_reads
from src.experiments.build_closure_pipe_sequences import (
    COMMON_ORIGIN_REQUIRED_COLUMNS,
    DEFAULT_ASSIGNMENT,
    EXPECTED_INTENT_ORIGINS,
    EXPECTED_INTENT_ORIGINS_BY_ROLE,
    HISTORY_LENGTH,
    INPUT_COLUMNS,
    MODEL_STATE_MAPPINGS,
    SEQUENCE_COLUMNS,
    SEQUENCE_VERSION,
    SURFACE_ID,
    TARGET_COLUMNS,
    TARGET_TO_NEXT_INPUT_MAPPING,
    SequenceBuildAudit,
    build_closure_pipe_sequences,
    expected_cpu_execution_policy_record,
    sequence_arrow_table,
    state_projection_columns,
)

AUDIT_VERSION = "closure_p1_seed_1729_sequence_bundle_audit_v1"
CHECK_ONLY_FLAG = "--check-only"
MODEL_ID = "P1"
BASE_SEED = 1729

P1_STATE_PATH = Path(
    "data/closure_v1/development/anfis/seed_1729/adaptive_no_current_state.parquet"
)
P1_STATE_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/anfis/seed_1729/manifest.json"
)
P1_SEQUENCE_PATH = Path(
    "data/closure_v1/development/sequences/P1/seed_1729.parquet"
)
P1_POINTER_PATH = Path(f"{P1_SEQUENCE_PATH.as_posix()}.dvc")
P1_SUMMARY_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P1/seed_1729_summary.csv"
)
P1_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P1/seed_1729_manifest.json"
)
P1_GUARD_DIRECTORY = Path("tmp/closure_v1_sequence_builder")
E0_MC_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/p1_sequence_historical_anfis_patch_lock.json"
)
E0_MC_COMPANION_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "p1_sequence_historical_anfis_patch_lock_manifest.json"
)
AUDITOR_PATH = Path("src/experiments/audit_closure_p1_sequence_bundle.py")

REGISTERED_BASE_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
E0_M_OUTPUT_PATHS = (
    Path("reports/closure_v1/00_protocol/model_lock.yaml"),
    Path("reports/closure_v1/00_protocol/calibration_lock.yaml"),
    Path("reports/closure_v1/00_protocol/hypothesis_registry.csv"),
    Path("reports/closure_v1/00_protocol/locked_batch_command.txt"),
)
OUTCOME_ACCESS_LOG_PATH = Path(
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl"
)


def _registered_seed_paths(base_seed: int) -> tuple[Path, ...]:
    sequence = Path(
        f"data/closure_v1/development/sequences/P1/seed_{base_seed}.parquet"
    )
    summary = Path(
        f"reports/closure_v1/01_surface/sequences/P1/seed_{base_seed}_summary.csv"
    )
    manifest = Path(
        f"reports/closure_v1/01_surface/sequences/P1/seed_{base_seed}_manifest.json"
    )
    model = Path(f"models/closure_v1/pipe/P1/seed_{base_seed}.pt")
    checkpoint = Path(
        f"models/closure_v1/pipe/P1/seed_{base_seed}.checkpoint.pt"
    )
    model_reports = tuple(
        Path(f"reports/closure_v1/02_models/P1/seed_{base_seed}_{suffix}")
        for suffix in (
            "preprocessor.json",
            "metrics.csv",
            "training_curve.csv",
            "blend_weights.csv",
            "blend_search.csv",
            "report.md",
            "manifest.json",
        )
    )
    consumer_finals = (model, checkpoint, *model_reports)
    return (
        sequence,
        Path(f"{sequence.as_posix()}.tmp"),
        Path(f"{sequence.as_posix()}.dvc"),
        Path(f"{sequence.as_posix()}.dvc.tmp"),
        summary,
        Path(f"{summary.as_posix()}.tmp"),
        manifest,
        Path(f"{manifest.as_posix()}.tmp"),
        Path(f"tmp/closure_v1_sequence_builder/P1_seed_{base_seed}.guard"),
        *consumer_finals,
        *(Path(f"{path.as_posix()}.tmp") for path in consumer_finals),
        Path(f"tmp/closure_v1_temporal_consumer/P1_seed_{base_seed}.guard"),
    )


REGISTERED_P1_PATHS = tuple(
    path
    for registered_seed in REGISTERED_BASE_SEEDS
    for path in _registered_seed_paths(registered_seed)
)
P1_SLOT_PATHS = _registered_seed_paths(BASE_SEED)
P1_SEQUENCE_TEMPORARY_PATHS = (
    Path(f"{P1_SEQUENCE_PATH.as_posix()}.tmp"),
    Path(f"{P1_POINTER_PATH.as_posix()}.tmp"),
    Path(f"{P1_SUMMARY_PATH.as_posix()}.tmp"),
    Path(f"{P1_MANIFEST_PATH.as_posix()}.tmp"),
    P1_GUARD_DIRECTORY / f"P1_seed_{BASE_SEED}.guard",
)
P1_CONSUMER_PATHS = tuple(
    path
    for path in P1_SLOT_PATHS
    if path
    not in {
        P1_SEQUENCE_PATH,
        Path(f"{P1_SEQUENCE_PATH.as_posix()}.tmp"),
        P1_POINTER_PATH,
        Path(f"{P1_POINTER_PATH.as_posix()}.tmp"),
        P1_SUMMARY_PATH,
        Path(f"{P1_SUMMARY_PATH.as_posix()}.tmp"),
        P1_MANIFEST_PATH,
        Path(f"{P1_MANIFEST_PATH.as_posix()}.tmp"),
        P1_GUARD_DIRECTORY / f"P1_seed_{BASE_SEED}.guard",
    }
)

EXPECTED_E0_MC_INPUT_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "path": "configs/closure_v1/p1_sequence_historical_anfis_patch_lock.schema.json",
        "role": "p1_sequence_historical_anfis_patch_lock_schema",
        "bytes": 17_387,
        "sha256": "f3d92b3cfc6214f403d82d60315b44d5ed25af4dcb4bb1f3946ab9850975d4b4",
    },
    {
        "path": "reports/closure_v1/00_protocol/development_runtime_patch_lock.json",
        "role": "external_development_runtime_patch_lock",
        "bytes": 92_714,
        "sha256": "d15a471ca293de0b48e5b52c1b52527640f2bd1ac1233e6b0796c4afa127fac4",
    },
    {
        "path": "reports/closure_v1/00_protocol/development_runtime_patch_lock_manifest.json",
        "role": "development_runtime_patch_companion",
        "bytes": 2_052,
        "sha256": "ac0c84f0fffa458a64df351ad6c51d450bb8b7b4991d8ac38fa51c049b711b46",
    },
    {
        "path": "reports/closure_v1/00_protocol/p1_sequence_builder_patch_lock.json",
        "role": "external_p1_sequence_builder_patch_lock",
        "bytes": 19_709,
        "sha256": "8a9a3e7cff21d2a0d4defe246019e31896e17410608102b23957ccdbf4719e52",
    },
    {
        "path": "reports/closure_v1/00_protocol/p1_sequence_builder_patch_lock_manifest.json",
        "role": "p1_sequence_builder_patch_companion",
        "bytes": 4_004,
        "sha256": "2ce1e48c3ca2aff69b16d683749e95bedff1668367d1f5300424ab76346343c9",
    },
    {
        "path": "src/experiments/build_closure_pipe_sequences.py",
        "role": "current_runtime_builder",
        "bytes": 127_833,
        "sha256": "f0e653b29035acb11e39bc9a7776e7940394996d75f16bf3bccb4da30013c9cf",
    },
    {
        "path": "src/experiments/closure_p1_sequence_historical_anfis_patch.py",
        "role": "p1_sequence_historical_anfis_patch_validator",
        "bytes": 64_044,
        "sha256": "f8daf21d907e4bbccd6f4601fea0ab65f043aee8f6057c219e6a9ff98526150c",
    },
)

EXPECTED_E0_MC_PATCH_RECORDS: tuple[dict[str, Any], ...] = (
    EXPECTED_E0_MC_INPUT_RECORDS[0],
    {
        "path": "docs/closure_v1/E0_M_P1_SEQUENCE_HISTORICAL_ANFIS_PATCH_1.md",
        "role": "p1_sequence_historical_anfis_patch_protocol",
        "bytes": 8_775,
        "sha256": "ab15cd36385433fb2b8469ca810974fcbd06423d1fec0a4eaf894cc71ceedaba",
    },
    {
        **EXPECTED_E0_MC_INPUT_RECORDS[5],
        "role": "historical_anfis_aware_p1_sequence_builder",
    },
    EXPECTED_E0_MC_INPUT_RECORDS[6],
    {
        "path": "src/experiments/lock_closure_p1_sequence_historical_anfis_patch.py",
        "role": "p1_sequence_historical_anfis_patch_locker",
        "bytes": 32_115,
        "sha256": "4a3cd483bfb912b8c0892407b410ca5e11a7b08e64bd3b03e0a69f48bd8ee304",
    },
    {
        "path": "tests/test_build_closure_pipe_sequences.py",
        "role": "historical_anfis_aware_p1_sequence_builder_tests",
        "bytes": 76_127,
        "sha256": "fffdf4a08ccf935acf18554a4b120dca1aa2b65f02d19cc5a023e5b0b57c1d01",
    },
    {
        "path": "tests/test_closure_p1_sequence_historical_anfis_patch.py",
        "role": "p1_sequence_historical_anfis_patch_tests",
        "bytes": 27_164,
        "sha256": "f9e58d45f2af8f7909f16bccf350ea02355ed75730149a9a69a80f9f895fd656",
    },
)

EXPECTED_INPUT_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "path": "data/closure_v1/common_origin_manifest.parquet",
        "bytes": 2_763_097,
        "sha256": "eb658a55ef6d3b8c0d909a8cf5e40f6bf6fff431997941056560b24cbf76f2f0",
    },
    {
        "path": "reports/closure_v1/01_surface/common_origin_manifest.json",
        "bytes": 11_524,
        "sha256": "19ef692b1efb05d45339e492db9459a234c4af1501e31ef4fc56e5a4dbc04b05",
    },
    {
        "path": "configs/closure_v1/development_runtime.yaml",
        "bytes": 46_105,
        "sha256": "0b2588248ee006f7d8e8843291b6a5847201a36fed35422473c9c0aa9492b10d",
    },
    {
        "path": "configs/closure_v1/development_runtime.schema.json",
        "bytes": 55_502,
        "sha256": "1abb28734ab3dc4ef2cdc68ce13876741ee42b4b5a8de35aadb332e95aee9709",
    },
    {
        "path": "reports/closure_v1/00_protocol/development_runtime_lock.json",
        "bytes": 95_285,
        "sha256": "5d858028ff5df561cc4a5e6086d9f83d08ac4c5ef6ffe27e844001f9fa495a81",
    },
    {
        "path": "data/closure_v1/closure_holdout_assignment.csv",
        "bytes": 89_635,
        "sha256": "b090994b9ec9a3cd6af8e3261879872a12efe301e02fe1727ded519b46ebedef",
    },
    {
        "path": "reports/closure_v1/00_protocol/holdout_manifest.json",
        "bytes": 3_440,
        "sha256": "b05e7767c35630806258494bcfac49ac26f7e628fea5d4185c5f9545ca480bc1",
    },
    {
        "path": "reports/closure_v1/00_protocol/protocol_lock.json",
        "bytes": 8_279,
        "sha256": "7b6530dd3b918a61b55e26b54d5cd68919e9cf6919e3521b452f7b05e2ded9c6",
    },
    {
        "path": "src/experiments/build_closure_pipe_sequences.py",
        "bytes": 127_833,
        "sha256": "f0e653b29035acb11e39bc9a7776e7940394996d75f16bf3bccb4da30013c9cf",
    },
    {
        "path": P1_STATE_MANIFEST_PATH.as_posix(),
        "bytes": 20_768,
        "sha256": "b38e54d21dd64edbf5a5968d9bee505569ea72b9f03c6750baf9a54114e9ef82",
    },
    {
        "path": E0_MC_LOCK_PATH.as_posix(),
        "bytes": 25_211,
        "sha256": "434f94b89c42b226fced57e2c6d02b6a1aaea8d772d4437d703274cba5808088",
    },
    {
        "path": E0_MC_COMPANION_PATH.as_posix(),
        "bytes": 4_814,
        "sha256": "9ac3538ed8076117f34fd94112582e1927e68ee8e298fae26b3d0f714d6e7b63",
    },
    {
        "path": P1_STATE_PATH.as_posix(),
        "bytes": 1_215_081,
        "sha256": "c1987e31edb5b0f830f433120715f2abb7d7a375f8f38e6ad24056fc12447c69",
    },
)

EXPECTED_SUPPORT_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "path": "src/experiments/build_closure_holdout.py",
        "bytes": 67_719,
        "sha256": "a79c746c2fa0468637744a5c5aa71dacfea8843130edfe6e9104a2d9ea0abd9e",
    },
    {
        "path": "src/experiments/closure_contract.py",
        "bytes": 87_743,
        "sha256": "c3d0ea8b1ff74ddb31a8bbe1a12875eb5423b379dd834c5ed9d87cfc7529d9b8",
    },
    {
        "path": "src/experiments/closure_development_guard.py",
        "bytes": 30_856,
        "sha256": "98115a235a88ce41b356260c8c3d953064c01bbd3d56e9b131e71c2e1eed7683",
    },
    {
        "path": "src/experiments/closure_runtime_contract.py",
        "bytes": 113_626,
        "sha256": "4639e003e482682aef0da69816e71f8c9d77a38fc3fb4965fd416f0569ce3432",
    },
    {
        "path": "src/experiments/audit_closure_p0_sequence_bundle.py",
        "bytes": 56_843,
        "sha256": "07c40c63282c9de623e2fb0dc38de6e8735cd85fb3a9a1d932cd05a7ea5273b7",
    },
)

EXPECTED_BUNDLE_RECORDS: dict[str, dict[str, Any]] = {
    P1_SEQUENCE_PATH.as_posix(): {
        "path": P1_SEQUENCE_PATH.as_posix(),
        "bytes": 1_380_222,
        "sha256": "860da77ac60c1aefb88cc9359631badc676864c77fb6df1d4b1ab87e01992069",
    },
    P1_SUMMARY_PATH.as_posix(): {
        "path": P1_SUMMARY_PATH.as_posix(),
        "bytes": 356,
        "sha256": "a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e",
    },
    P1_MANIFEST_PATH.as_posix(): {
        "path": P1_MANIFEST_PATH.as_posix(),
        "bytes": 6_527,
        "sha256": "5f1086b9409dac13625d77759badd8f3e9ba39a140a1d578da5ef6285f0295ea",
    },
}

EXPECTED_STATUS_COUNTS = {
    "success": 9_227,
    "autoregressive_target_unavailable": 505,
}
EXPECTED_FAILURE_REASON_COUNTS = {"missing_target_state": 505}
EXPECTED_ROLE_COUNTS = {
    "training": 8_352,
    "model_selection": 1_061,
    "calibration_threshold": 319,
}
EXPECTED_FIT_STATUS_COUNTS = {
    "success": 8_925,
    "autoregressive_target_unavailable": 488,
}
EXPECTED_FIT_FAILURE_REASON_COUNTS = {"missing_target_state": 488}
EXPECTED_CALIBRATION_FAILURES = 17
EXPECTED_DELTA_MISSING_HISTORY = 496
FIT_ROLES = ("training", "model_selection")

DVC_POINTER_PATTERN = re.compile(
    rb"outs:\n"
    rb"- md5: (?P<md5>[0-9a-f]{32})\n"
    rb"  size: (?P<size>0|[1-9][0-9]*)\n"
    rb"  hash: md5\n"
    rb"  path: seed_1729\.parquet\n"
)

MANIFEST_KEYS = {
    "manifest_version",
    "status",
    "generated_at_utc",
    "experiment_id",
    "surface_id",
    "model_id",
    "base_seed",
    "future_outcomes_accessed",
    "evaluation_authorized",
    "e0_u_authorized",
    "script",
    "cpu_execution_policy",
    "input_state_mapping",
    "target_state_mapping",
    "target_to_next_input_mapping",
    "input_columns",
    "target_columns",
    "optional_context_columns",
    "serialization",
    "counts",
    "inputs",
    "source_code",
    "outputs",
    "completion_marker_written_last",
}
MANIFEST_COUNT_KEYS = {
    "intent_origins",
    "successful_origins",
    "failed_origins",
    "role_counts",
    "status_counts",
    "failure_reason_counts",
    "delta_previous_month_missing_count",
    "delta_previous_month_missing_history_values",
    "delta_previous_month_missing_target_values",
    "holdout_overlap",
    "post_2021_rows",
}


class ClosureP1SequenceAuditError(ValueError):
    """Raised when the physical P1/1729 bundle differs from closed evidence."""


def _typed_equal(observed: Any, expected: Any) -> bool:
    if type(observed) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(observed) == set(expected) and all(
            _typed_equal(observed[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(observed) == len(expected) and all(
            _typed_equal(left, right)
            for left, right in zip(observed, expected, strict=True)
        )
    return bool(observed == expected)


def _decode_strict_json(payload_bytes: bytes, *, path: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ClosureP1SequenceAuditError(
            f"JSON contains a non-finite constant in {path}: {value}"
        )

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ClosureP1SequenceAuditError(
                    f"JSON contains a duplicate key in {path}: {key}"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(
            payload_bytes.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ClosureP1SequenceAuditError(
            f"JSON cannot be decoded strictly: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ClosureP1SequenceAuditError(f"JSON root must be an object: {path}")
    return payload


def _assert_pinned_record(pinned: Any, expected: Mapping[str, Any]) -> dict[str, Any]:
    record = pinned.record
    if not _typed_equal(record, dict(expected)):
        raise ClosureP1SequenceAuditError(f"Closed file record drifted: {record['path']}")
    return record


def _physical_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": record["path"],
        "bytes": record["bytes"],
        "sha256": record["sha256"],
    }


def _path_digest(paths: Sequence[Path]) -> str:
    return hashlib.sha256(
        "\n".join(path.as_posix() for path in paths).encode("utf-8")
    ).hexdigest()


def _input_paths() -> tuple[Path, ...]:
    return tuple(Path(record["path"]) for record in EXPECTED_INPUT_RECORDS)


def _support_paths() -> tuple[Path, ...]:
    return tuple(Path(record["path"]) for record in EXPECTED_SUPPORT_RECORDS)


def _e0_mc_physical_paths() -> tuple[Path, ...]:
    return tuple(
        Path(record["path"])
        for record in (*EXPECTED_E0_MC_INPUT_RECORDS, *EXPECTED_E0_MC_PATCH_RECORDS)
    )


def _closed_paths(*, pointer_present: bool) -> tuple[Path, ...]:
    candidates = (
        *_input_paths(),
        *_support_paths(),
        *_e0_mc_physical_paths(),
        P1_SEQUENCE_PATH,
        P1_SUMMARY_PATH,
        P1_MANIFEST_PATH,
        AUDITOR_PATH,
    )
    if pointer_present:
        candidates = (*candidates, P1_POINTER_PATH)
    return tuple(dict.fromkeys(candidates))


NAMESPACE_DIRECTORIES = {
    "data": P1_SEQUENCE_PATH.parent,
    "reports": P1_SUMMARY_PATH.parent,
    "sequence_guards": P1_GUARD_DIRECTORY,
    "model_files": Path("models/closure_v1/pipe/P1"),
    "model_reports": Path("reports/closure_v1/02_models/P1"),
    "consumer_guards": Path("tmp/closure_v1_temporal_consumer"),
    "protocol": Path("reports/closure_v1/00_protocol"),
}


def _list_optional_directory(session: Any, relative: Path) -> list[str] | None:
    current = PROJECT_ROOT
    for part in relative.parts:
        entries = session.list_directory(current)
        if part not in entries:
            return None
        current /= part
    return session.list_directory(current)


def _namespace_snapshot(session: Any) -> dict[str, Any]:
    return {
        key: _list_optional_directory(session, path)
        for key, path in NAMESPACE_DIRECTORIES.items()
    }


def _registered_paths_by_parent() -> dict[Path, set[str]]:
    result: dict[Path, set[str]] = {}
    for path in REGISTERED_P1_PATHS:
        result.setdefault(path.parent, set()).add(path.name)
    return result


def _namespace_entries(snapshot: Mapping[str, Any], key: str) -> set[str]:
    value = snapshot.get(key)
    if value is None:
        return set()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ClosureP1SequenceAuditError(f"P1 namespace snapshot drifted: {key}")
    if len(value) != len(set(value)):
        raise ClosureP1SequenceAuditError(f"P1 namespace has duplicate entries: {key}")
    return set(cast(list[str], value))


def _validate_closed_namespace(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if set(snapshot) != set(NAMESPACE_DIRECTORIES):
        raise ClosureP1SequenceAuditError("P1 namespace snapshot dialect drifted")
    entries = {
        key: _namespace_entries(snapshot, key) for key in NAMESPACE_DIRECTORIES
    }
    if snapshot["data"] is None or snapshot["reports"] is None:
        raise ClosureP1SequenceAuditError("Required P1 sequence namespace is absent")

    registered_by_parent = _registered_paths_by_parent()
    dedicated = ("data", "reports", "model_files", "model_reports")
    for key in dedicated:
        allowed = registered_by_parent[NAMESPACE_DIRECTORIES[key]]
        unexpected = sorted(entries[key] - allowed)
        if unexpected:
            raise ClosureP1SequenceAuditError(
                f"Unregistered entries exist in the dedicated P1 namespace {key}: {unexpected}"
            )
    for key in ("sequence_guards", "consumer_guards"):
        allowed = registered_by_parent[NAMESPACE_DIRECTORIES[key]]
        unexpected = sorted(
            name for name in entries[key] if name.startswith("P1_seed_") and name not in allowed
        )
        if unexpected:
            raise ClosureP1SequenceAuditError(
                f"Unregistered P1 guard entries exist in {key}: {unexpected}"
            )

    present: set[Path] = set()
    for key in dedicated + ("sequence_guards", "consumer_guards"):
        parent = NAMESPACE_DIRECTORIES[key]
        present.update(
            parent / name
            for name in entries[key]
            if name in registered_by_parent[parent]
        )

    required = {P1_SEQUENCE_PATH, P1_SUMMARY_PATH, P1_MANIFEST_PATH}
    missing_required = sorted(path.as_posix() for path in required - present)
    if missing_required:
        raise ClosureP1SequenceAuditError(
            f"P1/1729 sequence bundle is incomplete: {missing_required}"
        )
    forbidden_sequence_state = sorted(
        path.as_posix() for path in set(P1_SEQUENCE_TEMPORARY_PATHS) & present
    )
    if forbidden_sequence_state:
        raise ClosureP1SequenceAuditError(
            "P1/1729 sequence bundle has temporary or guard state: "
            f"{forbidden_sequence_state}"
        )

    pointer_present = P1_POINTER_PATH in present
    current_consumer_present = sorted(
        path.as_posix() for path in set(P1_CONSUMER_PATHS) & present
    )
    future_registered = set(REGISTERED_P1_PATHS) - set(P1_SLOT_PATHS)
    future_present = sorted(path.as_posix() for path in future_registered & present)
    protocol_entries = entries["protocol"]
    e0_m_present = sorted(
        path.as_posix() for path in E0_M_OUTPUT_PATHS if path.name in protocol_entries
    )
    outcome_present = OUTCOME_ACCESS_LOG_PATH.name in protocol_entries
    progression_clear = not (
        current_consumer_present or future_present or e0_m_present or outcome_present
    )
    present_sorted = sorted(path.as_posix() for path in present)
    absent_sorted = sorted(
        path.as_posix() for path in set(REGISTERED_P1_PATHS) - present
    )
    slot_present = sorted(path.as_posix() for path in set(P1_SLOT_PATHS) & present)
    slot_absent = sorted(
        path.as_posix() for path in set(P1_SLOT_PATHS) - present
    )
    return {
        "pointer_present": pointer_present,
        "slot_integrity": {
            "required_sequence_outputs_present": True,
            "sequence_temporary_or_guard_paths_present": [],
            "registered_slot_path_count": len(P1_SLOT_PATHS),
            "registered_slot_paths_sha256": _path_digest(P1_SLOT_PATHS),
            "registered_slot_present_paths": slot_present,
            "registered_slot_absent_paths": slot_absent,
            "registered_slot_present_count": len(slot_present),
            "registered_slot_absent_count": len(slot_absent),
        },
        "progression_observation": {
            "scope": "presence_only_no_authorization_or_content_inference",
            "registered_p1_path_count": len(REGISTERED_P1_PATHS),
            "registered_p1_paths_sha256": _path_digest(REGISTERED_P1_PATHS),
            "registered_present_paths": present_sorted,
            "registered_absent_paths": absent_sorted,
            "consumer_seed_1729_present_paths": current_consumer_present,
            "future_seed_present_paths": future_present,
            "e0_m_present_paths": e0_m_present,
            "outcome_access_log_present": outcome_present,
            "pre_consumer_and_pre_e0_m_clear_now": progression_clear,
        },
    }


def _require_pre_consumer_progression_clear(
    namespace_evidence: Mapping[str, Any],
) -> None:
    progression = namespace_evidence.get("progression_observation")
    if not isinstance(progression, Mapping) or (
        progression.get("pre_consumer_and_pre_e0_m_clear_now") is not True
    ):
        raise ClosureP1SequenceAuditError(
            "P1/1729 pre-consumer CLI gate requires consumer, future P1, E0-M, "
            "and outcome namespaces to remain absent"
        )


def _validate_dvc_pointer(sequence: Any, pointer: Any | None) -> dict[str, Any]:
    if pointer is None:
        return {
            "state": "pre_dvc",
            "pointer_present": False,
            "pointer_payload_binding_verified": False,
            "cache_verified": False,
            "remote_verified": False,
            "dvc_command_executed_by_auditor": False,
        }
    match = DVC_POINTER_PATTERN.fullmatch(pointer.payload)
    if match is None:
        raise ClosureP1SequenceAuditError("P1/1729 explicit DVC pointer dialect drifted")
    expected_md5 = hashlib.md5(sequence.payload, usedforsecurity=False).hexdigest()
    observed_md5 = match.group("md5").decode("ascii")
    observed_size = int(match.group("size"))
    if observed_md5 != expected_md5 or observed_size != len(sequence.payload):
        raise ClosureP1SequenceAuditError(
            "P1/1729 DVC pointer does not bind the physical Parquet"
        )
    return {
        "state": "post_dvc",
        "pointer_present": True,
        "pointer": pointer.record,
        "payload_md5": observed_md5,
        "payload_bytes": observed_size,
        "pointer_payload_binding_verified": True,
        "cache_verified": False,
        "remote_verified": False,
        "dvc_command_executed_by_auditor": False,
    }


def _load_assignment(payload: bytes) -> pd.DataFrame:
    try:
        return secure_reads._load_assignment(payload)
    except secure_reads.ClosureP0SequenceAuditError as exc:
        raise ClosureP1SequenceAuditError(str(exc).replace("P0", "P1")) from exc


def _derive_boundary_evidence(
    frame: pd.DataFrame,
    assignment: pd.DataFrame,
) -> dict[str, int]:
    if set(frame["source_id"].astype(str)) != {"wqp"}:
        raise ClosureP1SequenceAuditError("P1 sequence source scope drifted")
    try:
        evidence = secure_reads._derive_boundary_evidence(frame, assignment)
    except secure_reads.ClosureP0SequenceAuditError as exc:
        raise ClosureP1SequenceAuditError(str(exc).replace("P0", "P1")) from exc
    if evidence["unknown_assignment_locations"] != 0:
        raise ClosureP1SequenceAuditError("P1 sequence contains unknown assignments")
    return evidence


def _summary_frame(frame: pd.DataFrame) -> pd.DataFrame:
    summary = cast(
        pd.DataFrame,
        frame.groupby(
            ["time_role", "sequence_status", "failure_reason"],
            dropna=False,
            as_index=False,
        ).size(),
    )
    return summary.rename(columns={"size": "rows"}).sort_values(
        ["time_role", "sequence_status", "failure_reason"],
        kind="mergesort",
    )


def _summary_bytes(frame: pd.DataFrame) -> bytes:
    return _summary_frame(frame).to_csv(index=False, lineterminator="\n").encode("utf-8")


def _manifest_counts(
    audit: SequenceBuildAudit,
    boundary: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "intent_origins": audit.intent_origins,
        "successful_origins": audit.successful_origins,
        "failed_origins": audit.failed_origins,
        "role_counts": audit.role_counts,
        "status_counts": audit.status_counts,
        "failure_reason_counts": audit.failure_reason_counts,
        "delta_previous_month_missing_count": (
            audit.delta_previous_month_missing_history_values
        ),
        "delta_previous_month_missing_history_values": (
            audit.delta_previous_month_missing_history_values
        ),
        "delta_previous_month_missing_target_values": (
            audit.delta_previous_month_missing_target_values
        ),
        "holdout_overlap": boundary["holdout_overlap"],
        "post_2021_rows": boundary["post_2021_rows"],
    }


def _parquet_table(pinned: Any) -> tuple[pa.Schema, pa.Table]:
    try:
        reader = pq.ParquetFile(pa.BufferReader(pinned.payload), pre_buffer=False)
        try:
            schema = reader.schema_arrow
            table = reader.read(use_threads=False)
        finally:
            reader.close()
    except (OSError, ValueError, pa.ArrowException) as exc:
        raise ClosureP1SequenceAuditError(
            f"Parquet cannot be decoded from pinned bytes: {pinned.record['path']}"
        ) from exc
    return schema, table


def _validate_physical_schema(schema: pa.Schema) -> None:
    if schema.names != list(SEQUENCE_COLUMNS):
        raise ClosureP1SequenceAuditError("P1 Parquet columns/order drifted")
    for column in SEQUENCE_COLUMNS:
        field = schema.field(column)
        if column in INPUT_COLUMNS:
            valid = (
                pa.types.is_fixed_size_list(field.type)
                and field.type.list_size == HISTORY_LENGTH
                and field.type.value_type == pa.float32()
                and field.type.value_field.name in {"item", "element"}
                and field.nullable
            )
        elif column in TARGET_COLUMNS:
            valid = field.type == pa.float32() and field.nullable
        elif column == "base_seed":
            valid = field.type == pa.int64() and field.nullable
        elif column == "history_length_months":
            valid = field.type == pa.int16() and not field.nullable
        else:
            valid = field.type == pa.string() and not field.nullable
        if not valid:
            raise ClosureP1SequenceAuditError(
                f"P1 physical schema drifted: {column}"
            )


def _string_values(table: pa.Table, column: str) -> list[str]:
    return [str(value) for value in table.column(column).to_pylist()]


def _validate_physical_payload(table: pa.Table) -> dict[str, int]:
    _validate_physical_schema(table.schema)
    row_count = int(table.num_rows)
    if row_count != EXPECTED_INTENT_ORIGINS:
        raise ClosureP1SequenceAuditError("P1 Parquet intent denominator drifted")

    statuses = np.asarray(_string_values(table, "sequence_status"), dtype=object)
    if set(statuses.tolist()) != set(EXPECTED_STATUS_COUNTS):
        raise ClosureP1SequenceAuditError("P1 physical status vocabulary drifted")
    success = statuses == "success"
    failure = ~success

    metadata_expectations = {
        "sequence_version": {SEQUENCE_VERSION},
        "surface_id": {SURFACE_ID},
        "model_id": {MODEL_ID},
        "source_id": {"wqp"},
        "assignment_role": {"development"},
    }
    for column, expected in metadata_expectations.items():
        if set(_string_values(table, column)) != expected:
            raise ClosureP1SequenceAuditError(
                f"P1 physical metadata drifted: {column}"
            )
    history_lengths = table.column("history_length_months").to_pylist()
    if set(history_lengths) != {HISTORY_LENGTH}:
        raise ClosureP1SequenceAuditError("P1 physical history length drifted")
    seeds = table.column("base_seed").to_pylist()
    if any(seed is None for seed in seeds) or set(seeds) != {BASE_SEED}:
        raise ClosureP1SequenceAuditError("P1 physical base_seed drifted")

    reasons = np.asarray(_string_values(table, "failure_reason"), dtype=object)
    if bool((reasons[success] != "").any()) or (
        failure.any() and bool((reasons[failure] != "missing_target_state").any())
    ):
        raise ClosureP1SequenceAuditError("P1 physical failure reasons drifted")

    role_counts = pd.Series(
        _string_values(table, "time_role"), dtype="string"
    ).value_counts()
    observed_roles = {str(key): int(value) for key, value in role_counts.items()}
    if observed_roles != EXPECTED_ROLE_COUNTS:
        raise ClosureP1SequenceAuditError("P1 physical role counts drifted")

    failed_input_tensors = 0
    for column in INPUT_COLUMNS:
        values = table.column(column).combine_chunks()
        field = table.schema.field(column)
        if (
            not pa.types.is_fixed_size_list(field.type)
            or field.type.list_size != HISTORY_LENGTH
            or field.type.value_type != pa.float32()
            or not field.nullable
        ):
            raise ClosureP1SequenceAuditError(f"P1 input schema drifted: {column}")
        if values.null_count:
            raise ClosureP1SequenceAuditError(
                f"P1 input list parents must remain physically valid: {column}"
            )
        child_null = np.asarray(
            values.values.is_null().to_pylist(), dtype=bool
        ).reshape(row_count, HISTORY_LENGTH)
        if bool(child_null[success].any()):
            raise ClosureP1SequenceAuditError(
                f"Successful P1 input contains nulls: {column}"
            )
        if failure.any() and not bool(child_null[failure].all()):
            raise ClosureP1SequenceAuditError(
                f"Unavailable P1 input is not an exact all-null tensor: {column}"
            )
        child_values = np.asarray(
            values.values.to_pylist(), dtype=np.float64
        ).reshape(row_count, HISTORY_LENGTH)
        if not bool(np.isfinite(child_values[success]).all()):
            raise ClosureP1SequenceAuditError(
                f"Successful P1 input contains a non-finite value: {column}"
            )
        failed_input_tensors += int(failure.sum())

    failed_targets = 0
    for column in TARGET_COLUMNS:
        values = table.column(column).combine_chunks()
        field = table.schema.field(column)
        nulls = np.asarray(values.is_null().to_pylist(), dtype=bool)
        if field.type != pa.float32() or not field.nullable:
            raise ClosureP1SequenceAuditError(f"P1 target schema drifted: {column}")
        if bool(nulls[success].any()) or (
            failure.any() and not bool(nulls[failure].all())
        ):
            raise ClosureP1SequenceAuditError(
                f"P1 target null policy drifted: {column}"
            )
        success_values = [
            value
            for value, keep in zip(values.to_pylist(), success, strict=True)
            if keep
        ]
        if not bool(np.isfinite(np.asarray(success_values, dtype=np.float64)).all()):
            raise ClosureP1SequenceAuditError(
                f"Successful P1 target contains a non-finite value: {column}"
            )
        failed_targets += int(failure.sum())

    return {
        "rows": row_count,
        "successful_rows": int(success.sum()),
        "failed_rows": int(failure.sum()),
        "failed_input_tensors_all_null": failed_input_tensors,
        "failed_targets_null": failed_targets,
    }


def _validate_state_manifest(
    payload: Mapping[str, Any],
    *,
    state_record: Mapping[str, Any],
) -> None:
    expected = {
        "manifest_version": "closure_anfis_seed_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "F1",
        "consumer_model_id": MODEL_ID,
        "base_seed": BASE_SEED,
        "slot_status": "available",
        "fit_status": "passed",
        "failure_reason": "",
        "failed_slot_replaced": False,
        "fit_attempted": True,
        "state_artifact_emitted": True,
        "state_output_materialized": True,
        "checkpoint_outputs_materialized": True,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
    }
    for field, value in expected.items():
        if not _typed_equal(payload.get(field), value):
            raise ClosureP1SequenceAuditError(
                f"P1 state manifest field drifted: {field}"
            )
    outputs = payload.get("outputs")
    matches = (
        [
            record
            for record in outputs
            if isinstance(record, Mapping)
            and record.get("path") == P1_STATE_PATH.as_posix()
            and record.get("role") == "adaptive_no_current_state"
        ]
        if isinstance(outputs, list)
        else []
    )
    expected_record = {**dict(state_record), "role": "adaptive_no_current_state"}
    if matches != [expected_record]:
        raise ClosureP1SequenceAuditError(
            "P1 state manifest does not bind the physical adaptive state"
        )


def _validate_e0_mc_reference(
    lock: Mapping[str, Any],
    companion: Mapping[str, Any],
    *,
    lock_record: Mapping[str, Any],
    physical_records: Mapping[str, Mapping[str, Any]],
    state_manifest_record: Mapping[str, Any],
) -> dict[str, Any]:
    expected_lock = {
        "lock_version": "closure_p1_sequence_historical_anfis_patch_lock_v1",
        "status": "locked",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "gate": "E0-MC",
        "patch_id": "p1_sequence_historical_anfis_authority_patch_1",
    }
    for field, value in expected_lock.items():
        if not _typed_equal(lock.get(field), value):
            raise ClosureP1SequenceAuditError(f"E0-MC lock identity drifted: {field}")
    authorizations = lock.get("authorizations")
    expected_authorizations = {
        "authorized_base_seed": BASE_SEED,
        "authorized_model_id": MODEL_ID,
        "batch_seed_execution_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "effective_in_payload": False,
        "evaluation_authorized": False,
        "future_outcomes_accessed": False,
        "p1_fit_authorized": False,
        "p1_sequence_builder_authorized": False,
        "p1_sequence_retry_authorized": False,
        "prior_one_shot_authorization_consumed": True,
        "publication_required": True,
        "retry_under_previous_authority_authorized": False,
    }
    if not isinstance(authorizations, Mapping) or not _typed_equal(
        dict(authorizations), expected_authorizations
    ):
        raise ClosureP1SequenceAuditError("E0-MC lock authorization seals drifted")

    physical_role_records: dict[str, dict[str, Any]] = {}
    for expected in EXPECTED_E0_MC_INPUT_RECORDS:
        path = str(expected["path"])
        observed = physical_records.get(path)
        if observed is None or not _typed_equal(
            dict(observed), _physical_record(expected)
        ):
            raise ClosureP1SequenceAuditError(
                f"E0-MC physical input record drifted: {path}"
            )
        physical_role_records[path] = dict(expected)
    for expected in EXPECTED_E0_MC_PATCH_RECORDS:
        path = str(expected["path"])
        observed = physical_records.get(path)
        if observed is None or not _typed_equal(
            dict(observed), _physical_record(expected)
        ):
            raise ClosureP1SequenceAuditError(
                f"E0-MC physical patch component drifted: {path}"
            )

    builder_path = "src/experiments/build_closure_pipe_sequences.py"
    if not _typed_equal(
        lock.get("current_runtime_builder_record"),
        physical_role_records[builder_path],
    ):
        raise ClosureP1SequenceAuditError(
            "E0-MC current runtime builder does not bind the physical builder"
        )
    state_manifest_role_record = {
        **dict(state_manifest_record),
        "role": "seed_1729_completion_manifest",
    }
    historical_anfis = lock.get("historical_anfis_contract")
    if not isinstance(historical_anfis, Mapping) or not _typed_equal(
        historical_anfis.get("manifest"), state_manifest_role_record
    ):
        raise ClosureP1SequenceAuditError(
            "E0-MC historical ANFIS contract does not bind the physical manifest"
        )
    if historical_anfis.get("effective_dlp_loader_called") is not False:
        raise ClosureP1SequenceAuditError("E0-MC historical loader seal drifted")

    base_authorities = lock.get("base_authorities")
    if not isinstance(base_authorities, Mapping):
        raise ClosureP1SequenceAuditError("E0-MC base authorities are absent")
    e0_dlp = base_authorities.get("e0_dlp")
    e0_mb = base_authorities.get("e0_mb")
    if not isinstance(e0_dlp, Mapping) or not isinstance(e0_mb, Mapping):
        raise ClosureP1SequenceAuditError("E0-MC base authority dialect drifted")
    expected_base_records = {
        "e0_dlp_lock": physical_role_records[
            "reports/closure_v1/00_protocol/development_runtime_patch_lock.json"
        ],
        "e0_dlp_companion": physical_role_records[
            "reports/closure_v1/00_protocol/development_runtime_patch_lock_manifest.json"
        ],
        "e0_mb_lock": physical_role_records[
            "reports/closure_v1/00_protocol/p1_sequence_builder_patch_lock.json"
        ],
        "e0_mb_companion": physical_role_records[
            "reports/closure_v1/00_protocol/p1_sequence_builder_patch_lock_manifest.json"
        ],
    }
    base_checks = (
        (e0_dlp.get("lock"), expected_base_records["e0_dlp_lock"]),
        (
            e0_dlp.get("companion_manifest"),
            expected_base_records["e0_dlp_companion"],
        ),
        (e0_dlp.get("adopted_seed_manifest"), state_manifest_role_record),
        (e0_mb.get("lock"), expected_base_records["e0_mb_lock"]),
        (
            e0_mb.get("companion_manifest"),
            expected_base_records["e0_mb_companion"],
        ),
    )
    if any(not _typed_equal(observed, expected) for observed, expected in base_checks):
        raise ClosureP1SequenceAuditError(
            "E0-MC base authority does not bind its physical records"
        )

    expected_correction = {
        "classification": "historical_provenance_adapter_only",
        "denominator_changed": False,
        "e0_dlp_preserved_drift_component_count": 4,
        "e0_dlp_superseded_drift_component_count": 2,
        "e0_mb_preserved_component_count": 5,
        "e0_mb_superseded_component_count": 2,
        "issue_id": "historical_anfis_effective_loader_domain_mismatch_1",
        "legacy_effective_dlp_loader_used_for_historical_manifest": False,
        "outcome_access_changed": False,
        "replacement": "git_bound_historical_e0_dlp_reconstruction",
        "scientific_sequence_contract_changed": False,
        "state_mapping_changed": False,
    }
    expected_seals = {
        "denominator_changed": False,
        "does_not_replace_e0_m": True,
        "e0_dlp_lock_rewritten": False,
        "e0_dlp_preserved_as_historical_authority": True,
        "e0_mb_lock_rewritten": False,
        "e0_mb_preserved_as_historical_authority": True,
        "holdout_accessed": False,
        "only_builder_and_test_superseded_in_e0_dlp_drift": True,
        "only_builder_and_test_superseded_in_e0_mb": True,
        "post_2021_outcomes_accessed": False,
        "scientific_sequence_contract_changed": False,
        "seed_order_changed": False,
        "state_mapping_changed": False,
    }
    if not _typed_equal(lock.get("correction"), expected_correction):
        raise ClosureP1SequenceAuditError("E0-MC correction seals drifted")
    if not _typed_equal(lock.get("seals"), expected_seals):
        raise ClosureP1SequenceAuditError("E0-MC scientific seals drifted")

    sequence_prelock = lock.get("sequence_prelock")
    expected_sequence_prelock = {
            "all_absent_at_lock": True,
            "model_id": MODEL_ID,
            "base_seed": BASE_SEED,
            "count": len(P1_SLOT_PATHS),
            "paths": [path.as_posix() for path in P1_SLOT_PATHS],
            "paths_sha256": _path_digest(P1_SLOT_PATHS),
    }
    if not isinstance(sequence_prelock, Mapping) or not _typed_equal(
        dict(sequence_prelock), expected_sequence_prelock
    ):
        raise ClosureP1SequenceAuditError("E0-MC sequence prelock drifted")

    expected_progression_prelock = {
        "e0_m_output_count": 0,
        "future_outcomes_accessed": False,
        "outcome_access_log_state": "absent",
        "p1_all_absent": True,
        "p1_path_count": len(REGISTERED_P1_PATHS),
        "p1_paths_sha256": _path_digest(REGISTERED_P1_PATHS),
        "p1_seed_order": list(REGISTERED_BASE_SEEDS),
    }
    if not _typed_equal(lock.get("progression_prelock"), expected_progression_prelock):
        raise ClosureP1SequenceAuditError("E0-MC progression prelock drifted")

    expected_atomicity = {
        "bundle_outputs": ["sequence_parquet", "summary_csv", "manifest_json"],
        "completion_marker": "manifest_json",
        "completion_marker_written_last": True,
        "dependencies_revalidated_at_commit": True,
        "directory_fsync": True,
        "dvc_pointer_checks": [
            "preflight",
            "before_manifest",
            "after_manifest",
            "transaction_commit_before_output_rehash",
            "transaction_commit_after_dependency_revalidation",
        ],
        "exclusive_slot_guard": True,
        "foreign_replacement_preserved": True,
        "owned_bytes_rehashed_at_commit": True,
        "parent_walk_no_follow": True,
        "publication": "hardlink_no_clobber",
        "publication_order": ["sequence_parquet", "summary_csv", "manifest_json"],
        "rollback": "reverse_owned_inode_only",
        "sigkill_between_distinct_directories_is_detected_not_atomic": True,
        "temporary_creation": "exclusive_regular_inode",
        "uncoordinated_external_dvc_creator_excluded": False,
    }
    if not _typed_equal(lock.get("sequence_atomicity"), expected_atomicity):
        raise ClosureP1SequenceAuditError("E0-MC sequence atomicity seals drifted")

    expected_patch_components = {
        "count": len(EXPECTED_E0_MC_PATCH_RECORDS),
        "paths": [str(record["path"]) for record in EXPECTED_E0_MC_PATCH_RECORDS],
        "paths_sha256": "ff5ad66c07c357ff33ea0ffee6e0b8b0bed685a380da54fbff9b2ee253623500",
        "records": [dict(record) for record in EXPECTED_E0_MC_PATCH_RECORDS],
        "records_sha256": "69d124e63bcdeb96cf4e0a828822f61a1f36d0e12222c28dfb6f749303a1fee8",
    }
    if not _typed_equal(lock.get("patch_components"), expected_patch_components):
        raise ClosureP1SequenceAuditError("E0-MC patch components drifted")

    expected_lock_artifact = {
        "path": E0_MC_LOCK_PATH.as_posix(),
        "role": "external_p1_sequence_historical_anfis_patch_lock",
        "self_hash_policy": "verified_from_committed_and_published_bytes",
    }
    if not _typed_equal(lock.get("lock_artifact"), expected_lock_artifact):
        raise ClosureP1SequenceAuditError("E0-MC lock artifact identity drifted")

    expected_companion = {
        "manifest_version": "closure_p1_sequence_historical_anfis_patch_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "gate": "E0-MC",
        "patch_id": "p1_sequence_historical_anfis_authority_patch_1",
        "authoritative_contract": False,
        "authoritative_lock_path": E0_MC_LOCK_PATH.as_posix(),
        "authorized_model_id": MODEL_ID,
        "authorized_base_seed": BASE_SEED,
        "p1_fit_authorized": False,
        "p1_sequence_builder_authorized": False,
        "p1_sequence_retry_authorized": False,
        "prior_one_shot_authorization_consumed": True,
        "publication_required": True,
        "retry_under_previous_authority_authorized": False,
        "effective_in_payload": False,
        "physical_inputs_only": True,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "completion_marker_written_last": True,
    }
    for field, value in expected_companion.items():
        if not _typed_equal(companion.get(field), value):
            raise ClosureP1SequenceAuditError(
                f"E0-MC companion identity drifted: {field}"
            )
    expected_inputs = [dict(record) for record in EXPECTED_E0_MC_INPUT_RECORDS]
    if not _typed_equal(companion.get("inputs"), expected_inputs):
        raise ClosureP1SequenceAuditError(
            "E0-MC companion inputs do not bind the physical records"
        )
    if companion.get("historical_inputs_compared_to_current_paths") is not False:
        raise ClosureP1SequenceAuditError(
            "E0-MC companion historical input comparison policy drifted"
        )
    historical_inputs = companion.get("historical_inputs")
    if not isinstance(historical_inputs, list) or len(historical_inputs) != 4 or any(
        not isinstance(record, Mapping)
        or record.get("hash_source") != "git_blob_at_commit"
        for record in historical_inputs
    ):
        raise ClosureP1SequenceAuditError("E0-MC historical input dialect drifted")

    locker_physical = _physical_record(EXPECTED_E0_MC_PATCH_RECORDS[4])
    expected_script = {**locker_physical, "role": "generating_script"}
    if not _typed_equal(companion.get("script"), expected_script):
        raise ClosureP1SequenceAuditError(
            "E0-MC companion script does not bind the physical locker"
        )
    expected_output = {**dict(lock_record), "role": "external_p1_sequence_historical_anfis_patch_lock"}
    if not _typed_equal(companion.get("outputs"), [expected_output]):
        raise ClosureP1SequenceAuditError("E0-MC companion does not bind the exact lock")
    return {
        "validation_scope": "exact_physical_records_and_locked_semantic_seals",
        "lock_record": dict(lock_record),
        "physical_input_count": len(EXPECTED_E0_MC_INPUT_RECORDS),
        "physical_patch_component_count": len(EXPECTED_E0_MC_PATCH_RECORDS),
        "historical_inputs_compared_to_current_paths": False,
        "state_manifest_physically_reconciled": True,
        "base_authorities_physically_reconciled": True,
        "publication_reexecuted": False,
        "remote_publication_reexecuted": False,
        "effective_loader_called_by_auditor": False,
        "one_shot_reconsumed_by_auditor": False,
    }


def _validate_manifest(
    payload: Mapping[str, Any],
    *,
    builder_record: Mapping[str, Any],
    input_records: Sequence[Mapping[str, Any]],
    output_records: Sequence[Mapping[str, Any]],
    audit: SequenceBuildAudit,
    boundary: Mapping[str, int],
) -> None:
    if set(payload) != MANIFEST_KEYS:
        raise ClosureP1SequenceAuditError("P1 manifest top-level dialect drifted")
    expected_identity = {
        "manifest_version": "closure_pipe_sequence_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": MODEL_ID,
        "base_seed": BASE_SEED,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
    }
    for field, value in expected_identity.items():
        if not _typed_equal(payload.get(field), value):
            raise ClosureP1SequenceAuditError(f"P1 manifest field drifted: {field}")
    generated_at = payload.get("generated_at_utc")
    if not isinstance(generated_at, str):
        raise ClosureP1SequenceAuditError("P1 manifest timestamp is absent")
    try:
        parsed_time = datetime.fromisoformat(generated_at)
    except ValueError as exc:
        raise ClosureP1SequenceAuditError("P1 manifest timestamp is invalid") from exc
    if parsed_time.tzinfo is None:
        raise ClosureP1SequenceAuditError(
            "P1 manifest timestamp must be timezone-aware"
        )

    expected_script = dict(builder_record)
    exact_sections = {
        "script": expected_script,
        "source_code": [expected_script],
        "cpu_execution_policy": expected_cpu_execution_policy_record(),
        "input_state_mapping": MODEL_STATE_MAPPINGS[MODEL_ID],
        "target_state_mapping": MODEL_STATE_MAPPINGS[MODEL_ID],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
        "input_columns": list(INPUT_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "optional_context_columns": [],
        "serialization": {
            "rows_per_common_origin": 1,
            "input_physical_type": "fixed_size_list<float32>[12]",
            "target_physical_type": "float32",
            "canonical_order": [
                "source_id",
                "site_id",
                "origin_year_month",
                "target_year_month",
            ],
        },
        "inputs": [dict(record) for record in input_records],
        "outputs": [dict(record) for record in output_records],
    }
    for field, expected in exact_sections.items():
        if not _typed_equal(payload.get(field), expected):
            raise ClosureP1SequenceAuditError(f"P1 manifest section drifted: {field}")
    counts = payload.get("counts")
    if not isinstance(counts, Mapping) or set(counts) != MANIFEST_COUNT_KEYS:
        raise ClosureP1SequenceAuditError("P1 manifest count dialect drifted")
    if not _typed_equal(dict(counts), _manifest_counts(audit, boundary)):
        raise ClosureP1SequenceAuditError(
            "P1 manifest counts differ from physical reconstruction"
        )


def _fit_evidence(frame: pd.DataFrame) -> dict[str, Any]:
    total_statuses = {
        str(key): int(value)
        for key, value in frame["sequence_status"].value_counts().items()
    }
    total_failures = {
        str(key): int(value)
        for key, value in frame.loc[
            ~frame["sequence_status"].eq("success"), "failure_reason"
        ].value_counts().items()
    }
    if total_statuses != EXPECTED_STATUS_COUNTS:
        raise ClosureP1SequenceAuditError("P1 total availability evidence drifted")
    if total_failures != EXPECTED_FAILURE_REASON_COUNTS:
        raise ClosureP1SequenceAuditError("P1 total failure reasons drifted")
    fit = frame.loc[frame["time_role"].isin(FIT_ROLES)]
    statuses = {
        str(key): int(value)
        for key, value in fit["sequence_status"].value_counts().items()
    }
    failures = {
        str(key): int(value)
        for key, value in fit.loc[
            ~fit["sequence_status"].eq("success"), "failure_reason"
        ].value_counts().items()
    }
    calibration_failures = int(
        (
            frame["time_role"].eq("calibration_threshold")
            & ~frame["sequence_status"].eq("success")
        ).sum()
    )
    if statuses != EXPECTED_FIT_STATUS_COUNTS:
        raise ClosureP1SequenceAuditError("P1 fit status evidence drifted")
    if failures != EXPECTED_FIT_FAILURE_REASON_COUNTS:
        raise ClosureP1SequenceAuditError("P1 fit failure evidence drifted")
    if calibration_failures != EXPECTED_CALIBRATION_FAILURES:
        raise ClosureP1SequenceAuditError(
            "P1 calibration failure count drifted"
        )
    return {
        "available": False,
        "observed_total_status_counts": total_statuses,
        "observed_total_failure_reason_counts": total_failures,
        "observed_fit_status_counts": statuses,
        "observed_fit_failure_reason_counts": failures,
        "observed_calibration_failure_count": calibration_failures,
        "expected_fit_status": "not_attempted",
        "expected_temporal_slot_status": "model_unavailable",
        "expected_failure_reason": "sequence_fit_rows_unavailable",
        "availability_inferred_from_closed_counts": True,
        "consumer_executed_by_auditor": False,
        "fit_or_model_construction_executed_by_auditor": False,
    }


def _audit_p1_sequence_bundle() -> dict[str, Any]:
    result: dict[str, Any]
    with secure_reads._RepoReadSession(PROJECT_ROOT) as session:
        namespace_before = _namespace_snapshot(session)
        namespace_evidence = _validate_closed_namespace(namespace_before)
        pointer_present = bool(namespace_evidence["pointer_present"])
        pinned = {
            path.as_posix(): session.pin(PROJECT_ROOT / path)
            for path in _closed_paths(pointer_present=pointer_present)
        }

        def file_for(path: Path) -> Any:
            return pinned[path.as_posix()]

        input_records = [
            _assert_pinned_record(file_for(Path(expected["path"])), expected)
            for expected in EXPECTED_INPUT_RECORDS
        ]
        support_records = [
            _assert_pinned_record(file_for(Path(expected["path"])), expected)
            for expected in EXPECTED_SUPPORT_RECORDS
        ]
        e0_mc_physical_records: dict[str, dict[str, Any]] = {}
        for expected in (*EXPECTED_E0_MC_INPUT_RECORDS, *EXPECTED_E0_MC_PATCH_RECORDS):
            path = Path(str(expected["path"]))
            observed = _assert_pinned_record(
                file_for(path),
                _physical_record(expected),
            )
            e0_mc_physical_records[path.as_posix()] = observed
        bundle_records = {
            path: _assert_pinned_record(file_for(Path(path)), expected)
            for path, expected in EXPECTED_BUNDLE_RECORDS.items()
        }

        sequence_file = file_for(P1_SEQUENCE_PATH)
        pointer_file = file_for(P1_POINTER_PATH) if pointer_present else None
        dvc_registration = _validate_dvc_pointer(sequence_file, pointer_file)

        state_file = file_for(P1_STATE_PATH)
        state_manifest = _decode_strict_json(
            file_for(P1_STATE_MANIFEST_PATH).payload,
            path=P1_STATE_MANIFEST_PATH.as_posix(),
        )
        _validate_state_manifest(state_manifest, state_record=state_file.record)

        e0_mc_lock = _decode_strict_json(
            file_for(E0_MC_LOCK_PATH).payload,
            path=E0_MC_LOCK_PATH.as_posix(),
        )
        e0_mc_companion = _decode_strict_json(
            file_for(E0_MC_COMPANION_PATH).payload,
            path=E0_MC_COMPANION_PATH.as_posix(),
        )
        e0_mc = _validate_e0_mc_reference(
            e0_mc_lock,
            e0_mc_companion,
            lock_record=file_for(E0_MC_LOCK_PATH).record,
            physical_records=e0_mc_physical_records,
            state_manifest_record=file_for(P1_STATE_MANIFEST_PATH).record,
        )

        assignment = _load_assignment(file_for(DEFAULT_ASSIGNMENT).payload)
        common = pd.read_parquet(
            io.BytesIO(file_for(Path(EXPECTED_INPUT_RECORDS[0]["path"])).payload),
            engine="pyarrow",
            columns=list(COMMON_ORIGIN_REQUIRED_COLUMNS),
        )
        state = pd.read_parquet(
            io.BytesIO(state_file.payload),
            engine="pyarrow",
            columns=state_projection_columns(MODEL_ID),
        )
        expected_frame, build_audit = build_closure_pipe_sequences(
            state,
            common,
            model_id=MODEL_ID,
            base_seed=BASE_SEED,
            expected_origin_count=EXPECTED_INTENT_ORIGINS,
            expected_role_counts=EXPECTED_INTENT_ORIGINS_BY_ROLE,
        )
        if build_audit.role_counts != EXPECTED_ROLE_COUNTS:
            raise ClosureP1SequenceAuditError("P1 reconstructed role counts drifted")
        if build_audit.status_counts != EXPECTED_STATUS_COUNTS:
            raise ClosureP1SequenceAuditError("P1 reconstructed status counts drifted")
        if build_audit.failure_reason_counts != EXPECTED_FAILURE_REASON_COUNTS:
            raise ClosureP1SequenceAuditError(
                "P1 reconstructed failure reasons drifted"
            )
        if (
            build_audit.delta_previous_month_missing_history_values
            != EXPECTED_DELTA_MISSING_HISTORY
            or build_audit.delta_previous_month_missing_target_values != 0
        ):
            raise ClosureP1SequenceAuditError("P1 reconstructed delta audit drifted")

        expected_table = sequence_arrow_table(expected_frame)
        physical_schema, actual_table = _parquet_table(sequence_file)
        if physical_schema.names != list(SEQUENCE_COLUMNS):
            raise ClosureP1SequenceAuditError(
                "P1 physical Parquet schema has extra or reordered columns"
            )
        physical = _validate_physical_payload(actual_table)
        differing_columns = [
            column
            for column in SEQUENCE_COLUMNS
            if not actual_table.column(column).equals(expected_table.column(column))
        ]
        if differing_columns or actual_table.num_rows != expected_table.num_rows:
            raise ClosureP1SequenceAuditError(
                "P1 Parquet rows differ from sealed in-memory reconstruction: "
                f"columns={differing_columns}"
            )
        expected_physical = {
            "rows": EXPECTED_INTENT_ORIGINS,
            "successful_rows": EXPECTED_STATUS_COUNTS["success"],
            "failed_rows": EXPECTED_STATUS_COUNTS[
                "autoregressive_target_unavailable"
            ],
            "failed_input_tensors_all_null": (
                EXPECTED_STATUS_COUNTS["autoregressive_target_unavailable"]
                * len(INPUT_COLUMNS)
            ),
            "failed_targets_null": (
                EXPECTED_STATUS_COUNTS["autoregressive_target_unavailable"]
                * len(TARGET_COLUMNS)
            ),
        }
        if physical != expected_physical:
            raise ClosureP1SequenceAuditError("P1 physical null evidence drifted")

        boundary_columns = [
            "source_id",
            "site_id",
            "holdout_group_id",
            "assignment_role",
            "target_year_month",
        ]
        boundary = _derive_boundary_evidence(
            actual_table.select(boundary_columns).to_pandas(),
            assignment,
        )
        if file_for(P1_SUMMARY_PATH).payload != _summary_bytes(expected_frame):
            raise ClosureP1SequenceAuditError(
                "P1 summary bytes differ from reconstructed rows"
            )

        manifest = _decode_strict_json(
            file_for(P1_MANIFEST_PATH).payload,
            path=P1_MANIFEST_PATH.as_posix(),
        )
        builder_record = file_for(
            Path("src/experiments/build_closure_pipe_sequences.py")
        ).record
        _validate_manifest(
            manifest,
            builder_record=builder_record,
            input_records=input_records,
            output_records=(
                bundle_records[P1_SEQUENCE_PATH.as_posix()],
                bundle_records[P1_SUMMARY_PATH.as_posix()],
            ),
            audit=build_audit,
            boundary=boundary,
        )
        fit = _fit_evidence(expected_frame)

        namespace_after = _namespace_snapshot(session)
        if namespace_before != namespace_after:
            raise ClosureP1SequenceAuditError(
                "P1 audit namespace changed during readback"
            )
        session.verify_unchanged()
        result = {
            "audit_version": AUDIT_VERSION,
            "status": "validated",
            "experiment_id": "closure_v1",
            "model_id": MODEL_ID,
            "base_seed": BASE_SEED,
            "sequence_bundle_status": "completed",
            "auditor": file_for(AUDITOR_PATH).record,
            "support_sources": support_records,
            "e0_mc": e0_mc,
            "outputs": [
                bundle_records[path.as_posix()]
                for path in (P1_SEQUENCE_PATH, P1_SUMMARY_PATH, P1_MANIFEST_PATH)
            ],
            "counts": _manifest_counts(build_audit, boundary),
            "development_boundary": boundary,
            "physical_evidence": physical,
            "fit_availability": fit,
            "dvc_registration": dvc_registration,
            "dvc_pointer_present": pointer_present,
            "namespace_evidence": namespace_evidence,
            "closed_logical_schema_exact": True,
            "arrow_child_field_label_equality_claimed": False,
            "rows_equal_reconstruction": True,
            "summary_reconciled": True,
            "manifest_reconciled": True,
            "state_manifest_reconciled": True,
            "builder_reconstruction_executed": True,
            "builder_cli_executed": False,
            "effective_loader_called_by_auditor": False,
            "one_shot_reconsumed_by_auditor": False,
            "fit_or_model_construction_executed_by_auditor": False,
            "inputs_unchanged": True,
            "outputs_unchanged": True,
            "audited_namespaces_unchanged": True,
            "dvc_operation_executed_by_auditor": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "bundle_future_outcomes_accessed": False,
            "future_outcomes_accessed_by_auditor": False,
        }
    result["pinned_read_session_verified"] = True
    return result


def audit_p1_sequence_bundle() -> dict[str, Any]:
    """Audit the closed P1/1729 bundle without mutating repository state."""
    try:
        return _audit_p1_sequence_bundle()
    except ClosureP1SequenceAuditError:
        raise
    except secure_reads.ClosureP0SequenceAuditError as exc:
        raise ClosureP1SequenceAuditError(
            str(exc).replace("P0", "P1")
        ) from exc


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only audit of the closed Closure V1 P1/1729 sequence bundle."
    )
    parser.add_argument(
        CHECK_ONLY_FLAG,
        action="store_true",
        required=True,
        help="Reopen and validate the fixed P1/1729 bundle without writing outputs.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    parse_args(argv)
    try:
        result = audit_p1_sequence_bundle()
        _require_pre_consumer_progression_clear(result["namespace_evidence"])
        result["pre_consumer_progression_gate"] = "passed"
    except Exception as exc:
        failure = {
            "audit_version": AUDIT_VERSION,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
