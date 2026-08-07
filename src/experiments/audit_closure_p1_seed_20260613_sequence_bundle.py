#!/usr/bin/env python
"""Reopen and audit the immutable Closure V1 P1 seed 20260613 sequence bundle."""

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

from src.experiments import audit_closure_p1_sequence_bundle as historical
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

AUDIT_VERSION = "closure_p1_seed_20260613_sequence_bundle_audit_v1"
CHECK_ONLY_FLAG = "--check-only"
MODEL_ID = "P1"
BASE_SEED = 20260613

P1_STATE_PATH = Path(
    "data/closure_v1/development/anfis/seed_20260613/"
    "adaptive_no_current_state.parquet"
)
P1_STATE_POINTER_PATH = Path(f"{P1_STATE_PATH.as_posix()}.dvc")
P1_STATE_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/anfis/seed_20260613/manifest.json"
)
P1_SEQUENCE_PATH = Path(
    "data/closure_v1/development/sequences/P1/seed_20260613.parquet"
)
P1_POINTER_PATH = Path(f"{P1_SEQUENCE_PATH.as_posix()}.dvc")
P1_SUMMARY_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P1/seed_20260613_summary.csv"
)
P1_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/sequences/P1/seed_20260613_manifest.json"
)
P1_GUARD_DIRECTORY = Path("tmp/closure_v1_sequence_builder")
E0_MJ_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/p1_sequence_seed_20260613_patch_lock.json"
)
E0_MJ_COMPANION_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "p1_sequence_seed_20260613_patch_lock_manifest.json"
)
AUDITOR_PATH = Path(
    "src/experiments/audit_closure_p1_seed_20260613_sequence_bundle.py"
)

REGISTERED_BASE_SEEDS = historical.REGISTERED_BASE_SEEDS
REGISTERED_P1_PATHS = historical.REGISTERED_P1_PATHS
P1_SLOT_PATHS = historical._registered_seed_paths(BASE_SEED)
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
P1_1729_PATHS = (
    Path("data/closure_v1/development/sequences/P1/seed_1729.parquet"),
    Path("data/closure_v1/development/sequences/P1/seed_1729.parquet.dvc"),
    Path("reports/closure_v1/01_surface/sequences/P1/seed_1729_summary.csv"),
    Path("reports/closure_v1/01_surface/sequences/P1/seed_1729_manifest.json"),
    Path("reports/closure_v1/02_models/P1/seed_1729_report.md"),
    Path("reports/closure_v1/02_models/P1/seed_1729_manifest.json"),
)
P1_20260612_PATHS = (
    Path("data/closure_v1/development/sequences/P1/seed_20260612.parquet"),
    Path("data/closure_v1/development/sequences/P1/seed_20260612.parquet.dvc"),
    Path("reports/closure_v1/01_surface/sequences/P1/seed_20260612_summary.csv"),
    Path("reports/closure_v1/01_surface/sequences/P1/seed_20260612_manifest.json"),
    Path("reports/closure_v1/02_models/P1/seed_20260612_report.md"),
    Path("reports/closure_v1/02_models/P1/seed_20260612_manifest.json"),
)
PRIOR_P1_PATHS = (*P1_1729_PATHS, *P1_20260612_PATHS)
LATER_P1_PATHS = tuple(
    path
    for seed in REGISTERED_BASE_SEEDS
    if seed not in {1729, 20260612, BASE_SEED}
    for path in historical._registered_seed_paths(seed)
)

E0_M_OUTPUT_PATHS = historical.E0_M_OUTPUT_PATHS
OUTCOME_ACCESS_LOG_PATH = historical.OUTCOME_ACCESS_LOG_PATH

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
        "bytes": 127_846,
        "sha256": "d1af38a75dc40be60b89f23f9c4aedbea38a300902f81cbc4417fda49567a7b9",
    },
    {
        "path": P1_STATE_MANIFEST_PATH.as_posix(),
        "bytes": 20_881,
        "sha256": "c40c9ef87729d135933ef37ffce7236523b6b8fe957d90e33dde4837e5a2bd00",
    },
    {
        "path": E0_MJ_LOCK_PATH.as_posix(),
        "bytes": 28_541,
        "sha256": "4d525e8032c202a689d8ab27d444d8117528f2e0bd90ecb9d155aabab14a5ea1",
    },
    {
        "path": E0_MJ_COMPANION_PATH.as_posix(),
        "bytes": 7_835,
        "sha256": "81a02be5697e39ec26a04a28c52345d02871946974f5b070809518aa2f371d63",
    },
    {
        "path": P1_STATE_PATH.as_posix(),
        "bytes": 1_215_359,
        "sha256": "53f9a733e660d1968f8cf45916b1947ffa902346c16fabe2f07df9d27c4618a2",
    },
)

EXPECTED_SUPPORT_RECORDS: tuple[dict[str, Any], ...] = (
    *historical.EXPECTED_SUPPORT_RECORDS,
    {
        "path": "src/experiments/audit_closure_p1_sequence_bundle.py",
        "bytes": 65_825,
        "sha256": "095992ba27f93692e1c92ba6d1ff8375ed954375e2fc5a7d436d0e93eb555753",
    },
)

EXPECTED_P1_1729_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "path": PRIOR_P1_PATHS[0].as_posix(),
        "role": "p1_1729_1",
        "bytes": 1_380_222,
        "sha256": "860da77ac60c1aefb88cc9359631badc676864c77fb6df1d4b1ab87e01992069",
    },
    {
        "path": PRIOR_P1_PATHS[1].as_posix(),
        "role": "p1_1729_2",
        "bytes": 100,
        "sha256": "2281aee7f23f714837bf441b10b7c1c43829b830d4841ffe0513f9abbcf83db6",
    },
    {
        "path": PRIOR_P1_PATHS[2].as_posix(),
        "role": "p1_1729_3",
        "bytes": 356,
        "sha256": "a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e",
    },
    {
        "path": PRIOR_P1_PATHS[3].as_posix(),
        "role": "p1_1729_4",
        "bytes": 6_527,
        "sha256": "5f1086b9409dac13625d77759badd8f3e9ba39a140a1d578da5ef6285f0295ea",
    },
    {
        "path": PRIOR_P1_PATHS[4].as_posix(),
        "role": "p1_1729_5",
        "bytes": 174,
        "sha256": "aea483a6ba91d448fa0b743825ea9cb2284878f6b2b097fce53f6711216bfa6d",
    },
    {
        "path": PRIOR_P1_PATHS[5].as_posix(),
        "role": "p1_1729_6",
        "bytes": 13_416,
        "sha256": "3e95ee94ef1ae076d969bf7782b58a79b30a8e3d537e62efb16248e39b95e36a",
    },
)

EXPECTED_P1_20260612_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "path": P1_20260612_PATHS[0].as_posix(),
        "role": "p1_20260612_1",
        "bytes": 1_379_747,
        "sha256": "7c12fe31cece86ecc6a67d86337159a55757bec21b60f7a45d6911e8487a8f6b",
    },
    {
        "path": P1_20260612_PATHS[1].as_posix(),
        "role": "p1_20260612_2",
        "bytes": 104,
        "sha256": "e219bf384487f5f063afbb1933dd4315a99553fe5c6b230a6544588759b2c4c7",
    },
    {
        "path": P1_20260612_PATHS[2].as_posix(),
        "role": "p1_20260612_3",
        "bytes": 356,
        "sha256": "a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e",
    },
    {
        "path": P1_20260612_PATHS[3].as_posix(),
        "role": "p1_20260612_4",
        "bytes": 6_541,
        "sha256": "617b1acc27b90c90229c07fc7a91009e2d978d28d3f26a2c6d513e74cba87003",
    },
    {
        "path": P1_20260612_PATHS[4].as_posix(),
        "role": "p1_20260612_5",
        "bytes": 178,
        "sha256": "0c7b9d939858a54acdd3f88234e62ecc297bfc3ddf7ffc5b9b16124925a62320",
    },
    {
        "path": P1_20260612_PATHS[5].as_posix(),
        "role": "p1_20260612_6",
        "bytes": 14_637,
        "sha256": "2ec319434bab5cfd9c587c82bce841e5609f181841fdd908e0df206250981e5e",
    },
)

EXPECTED_PRIOR_P1_RECORDS: tuple[dict[str, Any], ...] = (
    *EXPECTED_P1_1729_RECORDS,
    *EXPECTED_P1_20260612_RECORDS,
)

EXPECTED_E0_MJ_INPUT_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "path": "configs/closure_v1/p1_sequence_seed_20260613_patch_lock.schema.json",
        "role": "p1_sequence_seed_20260613_patch_lock_schema",
        "bytes": 19_021,
        "sha256": "b0bf89ca3c04a956b5c30c854cda55e0e518b36af136c7d1e6ec8be7f74898fc",
    },
    {
        "path": P1_STATE_PATH.as_posix(),
        "role": "anfis_20260613_state_parquet",
        "bytes": 1_215_359,
        "sha256": "53f9a733e660d1968f8cf45916b1947ffa902346c16fabe2f07df9d27c4618a2",
    },
    {
        "path": P1_STATE_POINTER_PATH.as_posix(),
        "role": "anfis_20260613_state_pointer",
        "bytes": 116,
        "sha256": "7afddc7b3b22d07e9630a90d851e3d7cc5972b0d94904678cf49eee0168a9e93",
    },
    *EXPECTED_P1_1729_RECORDS[:2],
    *EXPECTED_P1_20260612_RECORDS[:2],
    {
        "path": "reports/closure_v1/00_protocol/p1_sequence_seed_20260612_patch_lock.json",
        "role": "external_p1_sequence_seed_20260612_patch_lock",
        "bytes": 25_333,
        "sha256": "2d4386300e6c44977ac5a85df0157d217c624c0ec44df0e1f6bf4f67725b4b17",
    },
    {
        "path": "reports/closure_v1/00_protocol/p1_sequence_seed_20260612_patch_lock_manifest.json",
        "role": "p1_sequence_seed_20260612_patch_companion",
        "bytes": 6_365,
        "sha256": "887a717ac16b3ab84d628b9e7dc0a8b85e9a7f45c40b3a00409a380c2748125e",
    },
    {
        "path": "reports/closure_v1/00_protocol/p1_temporal_consumer_seed_20260612_patch_lock.json",
        "role": "external_p1_temporal_consumer_seed_20260612_patch_lock",
        "bytes": 37_901,
        "sha256": "494ff320e6019c7bf8330f5c65f05344e97daabfa169aa434c2a44dd393d9f94",
    },
    {
        "path": "reports/closure_v1/00_protocol/p1_temporal_consumer_seed_20260612_patch_lock_manifest.json",
        "role": "p1_temporal_consumer_seed_20260612_patch_companion",
        "bytes": 8_850,
        "sha256": "9a165cd88cc6a2fa351215e493b1832a4402c52cefd2c588a62545014e992ce1",
    },
    {
        "path": P1_STATE_MANIFEST_PATH.as_posix(),
        "role": "anfis_20260613_state_manifest",
        "bytes": 20_881,
        "sha256": "c40c9ef87729d135933ef37ffce7236523b6b8fe957d90e33dde4837e5a2bd00",
    },
    *EXPECTED_P1_1729_RECORDS[3:4],
    *EXPECTED_P1_1729_RECORDS[2:3],
    *EXPECTED_P1_20260612_RECORDS[3:4],
    *EXPECTED_P1_20260612_RECORDS[2:3],
    *EXPECTED_P1_1729_RECORDS[5:6],
    *EXPECTED_P1_1729_RECORDS[4:5],
    *EXPECTED_P1_20260612_RECORDS[5:6],
    *EXPECTED_P1_20260612_RECORDS[4:5],
    {
        "path": "src/experiments/build_closure_pipe_sequences.py",
        "role": "current_runtime_builder",
        "bytes": 127_846,
        "sha256": "d1af38a75dc40be60b89f23f9c4aedbea38a300902f81cbc4417fda49567a7b9",
    },
    {
        "path": "src/experiments/closure_p1_sequence_seed_20260613_patch.py",
        "role": "p1_sequence_seed_20260613_patch_validator",
        "bytes": 78_355,
        "sha256": "704021e2da49d63e95f1d49c6b786f42df1983e54a2917c68577d9319a76aa06",
    },
)

EXPECTED_E0_MJ_PATCH_RECORDS: tuple[dict[str, Any], ...] = (
    EXPECTED_E0_MJ_INPUT_RECORDS[0],
    {
        "path": "docs/closure_v1/E0_M_P1_SEQUENCE_SEED_20260613_PATCH_1.md",
        "role": "p1_sequence_seed_20260613_patch_protocol",
        "bytes": 3_900,
        "sha256": "9baea121e824677e05a276ef123ec74f8fcfeb07e07537a9c7623efb9942d2d2",
    },
    {
        **historical._physical_record(EXPECTED_INPUT_RECORDS[8]),
        "role": "p1_sequence_seed_20260613_gate_routing",
    },
    EXPECTED_E0_MJ_INPUT_RECORDS[-1],
    {
        "path": "src/experiments/lock_closure_p1_sequence_seed_20260613_patch.py",
        "role": "p1_sequence_seed_20260613_patch_locker",
        "bytes": 36_016,
        "sha256": "09c3a11993de1765f7eb04b186de59e4703798fce7d35100b280aa3ad7c285ea",
    },
    {
        "path": "tests/test_build_closure_pipe_sequences.py",
        "role": "p1_sequence_seed_20260613_builder_gate_tests",
        "bytes": 76_105,
        "sha256": "f6da67cf6674e6e494b88ba500bed3798a9f658c3fb0a588b6346afa4bea14e5",
    },
    {
        "path": "tests/test_closure_p1_sequence_seed_20260613_patch.py",
        "role": "p1_sequence_seed_20260613_patch_tests",
        "bytes": 36_537,
        "sha256": "1855416536c74ad92ccac0921f43b4757051c23c5d8f01c76e32a9751a8f095e",
    },
)

EXPECTED_HISTORICAL_INPUTS: tuple[dict[str, Any], ...] = (
    {
        "path": "src/experiments/build_closure_pipe_sequences.py",
        "role": "p1_sequence_seed_20260612_gate_routing",
        "bytes": 127_842,
        "sha256": "6783dc9322f1869879c7a4cde0b02aef8d62785623e6dc8d4cccedc54d4e98ea",
        "commit": "16662cdd5f258a1aa035c0f192145b3bd4d30fab",
        "hash_source": "git_blob_at_commit",
    },
    {
        "path": "tests/test_build_closure_pipe_sequences.py",
        "role": "p1_sequence_seed_20260612_builder_gate_tests",
        "bytes": 76_105,
        "sha256": "eccdc55a19e77d2a872ca57920ebab85d02dca33d2226c91d83d2884c4560402",
        "commit": "16662cdd5f258a1aa035c0f192145b3bd4d30fab",
        "hash_source": "git_blob_at_commit",
    },
)

EXPECTED_BUNDLE_RECORDS: dict[str, dict[str, Any]] = {
    P1_SEQUENCE_PATH.as_posix(): {
        "path": P1_SEQUENCE_PATH.as_posix(),
        "bytes": 1_379_656,
        "sha256": "4dfd3ec12e061d29730fbf005e2e4c7e24a922335da5d4512a9b8c5eb847171a",
    },
    P1_SUMMARY_PATH.as_posix(): {
        "path": P1_SUMMARY_PATH.as_posix(),
        "bytes": 356,
        "sha256": "a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e",
    },
    P1_MANIFEST_PATH.as_posix(): {
        "path": P1_MANIFEST_PATH.as_posix(),
        "bytes": 6_541,
        "sha256": "d2ecb7b9b25b0b60a6534d64679db44d77e2484f6e3f269c7ae3db020bcfbac3",
    },
}

EXPECTED_STATUS_COUNTS = dict(historical.EXPECTED_STATUS_COUNTS)
EXPECTED_FAILURE_REASON_COUNTS = dict(historical.EXPECTED_FAILURE_REASON_COUNTS)
EXPECTED_ROLE_COUNTS = dict(historical.EXPECTED_ROLE_COUNTS)
EXPECTED_FIT_STATUS_COUNTS = dict(historical.EXPECTED_FIT_STATUS_COUNTS)
EXPECTED_FIT_FAILURE_REASON_COUNTS = dict(
    historical.EXPECTED_FIT_FAILURE_REASON_COUNTS
)
EXPECTED_CALIBRATION_FAILURES = historical.EXPECTED_CALIBRATION_FAILURES
EXPECTED_DELTA_MISSING_HISTORY = historical.EXPECTED_DELTA_MISSING_HISTORY
FIT_ROLES = historical.FIT_ROLES

DVC_POINTER_PATTERN = re.compile(
    rb"outs:\n"
    rb"- md5: (?P<md5>[0-9a-f]{32})\n"
    rb"  size: (?P<size>0|[1-9][0-9]*)\n"
    rb"  hash: md5\n"
    rb"  path: seed_20260613\.parquet\n"
)

MANIFEST_KEYS = historical.MANIFEST_KEYS
MANIFEST_COUNT_KEYS = historical.MANIFEST_COUNT_KEYS


class ClosureP1Seed20260613SequenceAuditError(ValueError):
    """Raised when the physical P1/20260613 bundle differs from closed evidence."""


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
        raise ClosureP1Seed20260613SequenceAuditError(
            f"JSON contains a non-finite constant in {path}: {value}"
        )

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ClosureP1Seed20260613SequenceAuditError(
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
        raise ClosureP1Seed20260613SequenceAuditError(
            f"JSON cannot be decoded strictly: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ClosureP1Seed20260613SequenceAuditError(
            f"JSON root must be an object: {path}"
        )
    return payload


def _assert_canonical_json(
    payload_bytes: bytes,
    payload: Mapping[str, Any],
    *,
    path: str,
    sort_keys: bool = False,
) -> None:
    expected = (
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=sort_keys) + "\n"
    ).encode("utf-8")
    if payload_bytes != expected:
        raise ClosureP1Seed20260613SequenceAuditError(
            f"JSON serialization is not canonical: {path}"
        )


def _physical_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": record["path"],
        "bytes": record["bytes"],
        "sha256": record["sha256"],
    }


def _assert_pinned_record(pinned: Any, expected: Mapping[str, Any]) -> dict[str, Any]:
    if not _typed_equal(pinned.record, dict(expected)):
        raise ClosureP1Seed20260613SequenceAuditError(
            f"Closed file record drifted: {pinned.record['path']}"
        )
    return pinned.record


def _path_digest(paths: Sequence[Path]) -> str:
    return hashlib.sha256(
        "\n".join(path.as_posix() for path in paths).encode("utf-8")
    ).hexdigest()


def _closed_paths(*, pointer_present: bool) -> tuple[Path, ...]:
    candidates = (
        *(Path(str(record["path"])) for record in EXPECTED_INPUT_RECORDS),
        *(Path(str(record["path"])) for record in EXPECTED_SUPPORT_RECORDS),
        *(Path(str(record["path"])) for record in EXPECTED_E0_MJ_INPUT_RECORDS),
        *(Path(str(record["path"])) for record in EXPECTED_E0_MJ_PATCH_RECORDS),
        *(Path(str(record["path"])) for record in EXPECTED_PRIOR_P1_RECORDS),
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
        raise ClosureP1Seed20260613SequenceAuditError(
            f"P1 namespace snapshot drifted: {key}"
        )
    if len(value) != len(set(value)):
        raise ClosureP1Seed20260613SequenceAuditError(
            f"P1 namespace has duplicate entries: {key}"
        )
    return set(cast(list[str], value))


def _validate_closed_namespace(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if set(snapshot) != set(NAMESPACE_DIRECTORIES):
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 namespace snapshot dialect drifted"
        )
    entries = {
        key: _namespace_entries(snapshot, key) for key in NAMESPACE_DIRECTORIES
    }
    if snapshot["data"] is None or snapshot["reports"] is None:
        raise ClosureP1Seed20260613SequenceAuditError(
            "Required P1 sequence namespace is absent"
        )

    registered_by_parent = _registered_paths_by_parent()
    dedicated = ("data", "reports", "model_files", "model_reports")
    for key in dedicated:
        allowed = registered_by_parent[NAMESPACE_DIRECTORIES[key]]
        unexpected = sorted(entries[key] - allowed)
        if unexpected:
            raise ClosureP1Seed20260613SequenceAuditError(
                "Unregistered entries exist in the dedicated P1 namespace "
                f"{key}: {unexpected}"
            )
    for key in ("sequence_guards", "consumer_guards"):
        allowed = registered_by_parent[NAMESPACE_DIRECTORIES[key]]
        unexpected = sorted(
            name
            for name in entries[key]
            if name.startswith("P1_seed_") and name not in allowed
        )
        if unexpected:
            raise ClosureP1Seed20260613SequenceAuditError(
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
        raise ClosureP1Seed20260613SequenceAuditError(
            f"P1/20260613 sequence bundle is incomplete: {missing_required}"
        )
    forbidden_sequence = sorted(
        path.as_posix() for path in set(P1_SEQUENCE_TEMPORARY_PATHS) & present
    )
    if forbidden_sequence:
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 bundle has temporary or guard state: "
            f"{forbidden_sequence}"
        )

    prior_present = set(PRIOR_P1_PATHS) & present
    if prior_present != set(PRIOR_P1_PATHS):
        missing = sorted(path.as_posix() for path in set(PRIOR_P1_PATHS) - prior_present)
        raise ClosureP1Seed20260613SequenceAuditError(
            f"P1 closed predecessor bundles drifted: {missing}"
        )
    for seed, expected_paths in (
        (1729, P1_1729_PATHS),
        (20260612, P1_20260612_PATHS),
    ):
        registered = set(historical._registered_seed_paths(seed))
        unexpected = sorted(
            path.as_posix() for path in (registered & present) - set(expected_paths)
        )
        if unexpected:
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/{seed} has unexpected residual paths: {unexpected}"
            )

    current_consumer = sorted(
        path.as_posix() for path in set(P1_CONSUMER_PATHS) & present
    )
    later_present = sorted(path.as_posix() for path in set(LATER_P1_PATHS) & present)
    protocol_entries = entries["protocol"]
    e0_m_present = sorted(
        path.as_posix() for path in E0_M_OUTPUT_PATHS if path.name in protocol_entries
    )
    outcome_present = OUTCOME_ACCESS_LOG_PATH.name in protocol_entries
    progression_clear = not (
        current_consumer or later_present or e0_m_present or outcome_present
    )
    current_present = sorted(path.as_posix() for path in set(P1_SLOT_PATHS) & present)
    current_absent = sorted(path.as_posix() for path in set(P1_SLOT_PATHS) - present)
    registered_present = sorted(
        path.as_posix() for path in set(REGISTERED_P1_PATHS) & present
    )
    registered_absent = sorted(
        path.as_posix() for path in set(REGISTERED_P1_PATHS) - present
    )
    return {
        "pointer_present": P1_POINTER_PATH in present,
        "registered_namespace": {
            "registered_path_count": len(REGISTERED_P1_PATHS),
            "registered_present_count": len(registered_present),
            "registered_absent_count": len(registered_absent),
            "registered_present_paths": registered_present,
            "registered_absent_paths_sha256": _path_digest(
                tuple(Path(path) for path in registered_absent)
            ),
        },
        "slot_integrity": {
            "required_sequence_outputs_present": True,
            "sequence_temporary_or_guard_paths_present": [],
            "registered_slot_path_count": len(P1_SLOT_PATHS),
            "registered_slot_paths_sha256": _path_digest(P1_SLOT_PATHS),
            "registered_slot_present_paths": current_present,
            "registered_slot_absent_paths": current_absent,
            "registered_slot_present_count": len(current_present),
            "registered_slot_absent_count": len(current_absent),
        },
        "progression_observation": {
            "scope": "presence_only_no_authorization_or_content_inference",
            "prior_seeds": [1729, 20260612],
            "prior_seed_present_paths": sorted(
                path.as_posix() for path in prior_present
            ),
            "prior_seed_present_count": len(prior_present),
            "current_seed": BASE_SEED,
            "current_consumer_present_paths": current_consumer,
            "later_seed_present_paths": later_present,
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
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 pre-consumer CLI gate requires its consumer, later P1, "
            "E0-M, and outcome namespaces to remain absent"
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
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 explicit DVC pointer dialect drifted"
        )
    expected_md5 = hashlib.md5(sequence.payload, usedforsecurity=False).hexdigest()
    observed_md5 = match.group("md5").decode("ascii")
    observed_size = int(match.group("size"))
    if observed_md5 != expected_md5 or observed_size != len(sequence.payload):
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 DVC pointer does not bind the physical Parquet"
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
        return historical._load_assignment(payload)
    except historical.ClosureP1SequenceAuditError as exc:
        raise ClosureP1Seed20260613SequenceAuditError(str(exc)) from exc


def _derive_boundary_evidence(
    frame: pd.DataFrame,
    assignment: pd.DataFrame,
) -> dict[str, int]:
    try:
        return historical._derive_boundary_evidence(frame, assignment)
    except historical.ClosureP1SequenceAuditError as exc:
        raise ClosureP1Seed20260613SequenceAuditError(str(exc)) from exc


def _summary_bytes(frame: pd.DataFrame) -> bytes:
    return historical._summary_bytes(frame)


def _manifest_counts(
    audit: SequenceBuildAudit,
    boundary: Mapping[str, int],
) -> dict[str, Any]:
    return historical._manifest_counts(audit, boundary)


def _parquet_table(pinned: Any) -> tuple[pa.Schema, pa.Table]:
    try:
        reader = pq.ParquetFile(pa.BufferReader(pinned.payload), pre_buffer=False)
        try:
            schema = reader.schema_arrow
            table = reader.read(use_threads=False)
        finally:
            reader.close()
    except (OSError, ValueError, pa.ArrowException) as exc:
        raise ClosureP1Seed20260613SequenceAuditError(
            f"Parquet cannot be decoded from pinned bytes: {pinned.record['path']}"
        ) from exc
    return schema, table


def _validate_physical_schema(schema: pa.Schema) -> None:
    if schema.names != list(SEQUENCE_COLUMNS):
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 Parquet columns/order drifted"
        )
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
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/20260613 physical schema drifted: {column}"
            )


def _string_values(table: pa.Table, column: str) -> list[str]:
    return [str(value) for value in table.column(column).to_pylist()]


def _validate_physical_payload(table: pa.Table) -> dict[str, int]:
    _validate_physical_schema(table.schema)
    row_count = int(table.num_rows)
    if row_count != EXPECTED_INTENT_ORIGINS:
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 Parquet intent denominator drifted"
        )

    statuses = np.asarray(_string_values(table, "sequence_status"), dtype=object)
    if set(statuses.tolist()) != set(EXPECTED_STATUS_COUNTS):
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 physical status vocabulary drifted"
        )
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
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/20260613 physical metadata drifted: {column}"
            )
    if set(table.column("history_length_months").to_pylist()) != {HISTORY_LENGTH}:
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 physical history length drifted"
        )
    seeds = table.column("base_seed").to_pylist()
    if any(seed is None for seed in seeds) or set(seeds) != {BASE_SEED}:
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 physical base_seed drifted"
        )

    reasons = np.asarray(_string_values(table, "failure_reason"), dtype=object)
    if bool((reasons[success] != "").any()) or (
        failure.any() and bool((reasons[failure] != "missing_target_state").any())
    ):
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 physical failure reasons drifted"
        )
    roles = pd.Series(_string_values(table, "time_role"), dtype="string").value_counts()
    observed_roles = {str(key): int(value) for key, value in roles.items()}
    if observed_roles != EXPECTED_ROLE_COUNTS:
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 physical role counts drifted"
        )

    failed_input_tensors = 0
    for column in INPUT_COLUMNS:
        values = table.column(column).combine_chunks()
        if values.null_count:
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/20260613 input list parents must remain valid: {column}"
            )
        child_null = np.asarray(values.values.is_null().to_pylist(), dtype=bool).reshape(
            row_count, HISTORY_LENGTH
        )
        if bool(child_null[success].any()) or (
            failure.any() and not bool(child_null[failure].all())
        ):
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/20260613 input null policy drifted: {column}"
            )
        child_values = np.asarray(values.values.to_pylist(), dtype=np.float64).reshape(
            row_count, HISTORY_LENGTH
        )
        if not bool(np.isfinite(child_values[success]).all()):
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/20260613 successful input is non-finite: {column}"
            )
        failed_input_tensors += int(failure.sum())

    failed_targets = 0
    for column in TARGET_COLUMNS:
        values = table.column(column).combine_chunks()
        nulls = np.asarray(values.is_null().to_pylist(), dtype=bool)
        if bool(nulls[success].any()) or (
            failure.any() and not bool(nulls[failure].all())
        ):
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/20260613 target null policy drifted: {column}"
            )
        successful = [
            value
            for value, keep in zip(values.to_pylist(), success, strict=True)
            if keep
        ]
        if not bool(np.isfinite(np.asarray(successful, dtype=np.float64)).all()):
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/20260613 successful target is non-finite: {column}"
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
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/20260613 state manifest field drifted: {field}"
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
    if matches != [{**dict(state_record), "role": "adaptive_no_current_state"}]:
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 state manifest does not bind its adaptive state"
        )


def _validate_e0_mj_reference(
    lock: Mapping[str, Any],
    companion: Mapping[str, Any],
    *,
    lock_record: Mapping[str, Any],
    physical_records: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    lock_digest = hashlib.sha256(
        (
            json.dumps(lock, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8")
    ).hexdigest()
    companion_digest = hashlib.sha256(
        (
            json.dumps(companion, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8")
    ).hexdigest()
    if lock_digest != EXPECTED_INPUT_RECORDS[10]["sha256"]:
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ canonical lock payload drifted"
        )
    if companion_digest != EXPECTED_INPUT_RECORDS[11]["sha256"]:
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ canonical companion payload drifted"
        )
    expected_lock_identity = {
        "lock_version": "closure_p1_sequence_seed_20260613_patch_lock_v1",
        "status": "locked",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "gate": "E0-MJ",
        "patch_id": "p1_sequence_seed_20260613_authority_patch_1",
    }
    for field, value in expected_lock_identity.items():
        if not _typed_equal(lock.get(field), value):
            raise ClosureP1Seed20260613SequenceAuditError(
                f"E0-MJ lock identity drifted: {field}"
            )
    expected_authorizations = {
        "authorized_base_seed": BASE_SEED,
        "authorized_model_id": MODEL_ID,
        "batch_seed_execution_authorized": False,
        "dvc_commands_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "effective_in_payload": False,
        "evaluation_authorized": False,
        "fit_attempt_authorized": False,
        "future_outcomes_accessed": False,
        "p1_consumer_authorized": False,
        "p1_fit_authorized": False,
        "p1_sequence_builder_authorized": False,
        "prior_p1_1729_slot_completed": True,
        "prior_p1_20260612_slot_completed": True,
        "publication_required": True,
        "replacement_authorized": False,
        "retry_authorized": False,
    }
    if not _typed_equal(lock.get("authorizations"), expected_authorizations):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ authorization seals drifted"
        )

    expected_repository = {
        "branch": "main",
        "exact_diff_verified": True,
        "head": "3b86b75edcfa5d11eab6bb97ab7cfd71df468fab",
        "parent": "5b2c5d6b4f4c296c9485d1cb22561086aeeb6b85",
        "published_head": "3b86b75edcfa5d11eab6bb97ab7cfd71df468fab",
        "published_ref": "origin/main",
        "remote_main_oid": "3b86b75edcfa5d11eab6bb97ab7cfd71df468fab",
        "worktree_status": "clean",
    }
    if not _typed_equal(lock.get("patch_repository"), expected_repository):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ publication topology seal drifted"
        )

    for expected in (*EXPECTED_E0_MJ_INPUT_RECORDS, *EXPECTED_E0_MJ_PATCH_RECORDS):
        path = str(expected["path"])
        observed = physical_records.get(path)
        if observed is None or not _typed_equal(dict(observed), _physical_record(expected)):
            raise ClosureP1Seed20260613SequenceAuditError(
                f"E0-MJ physical record drifted: {path}"
            )
    expected_builder = {
        **_physical_record(EXPECTED_INPUT_RECORDS[8]),
        "role": "current_runtime_builder",
    }
    if not _typed_equal(lock.get("current_runtime_builder_record"), expected_builder):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ current builder binding drifted"
        )

    expected_anfis = {
        "fit_status": "passed",
        "future_outcomes_accessed": False,
        "publication_commit": "f197780c3b5d215b45738ce425fd5ff639d76bab",
        "records": [
            dict(EXPECTED_E0_MJ_INPUT_RECORDS[index]) for index in (1, 2, 11)
        ],
        "records_sha256": "6c821c5af6f96ca3623761239903300e293254ec661505dfb892194c58eba3ec",
        "slot_status": "available",
        "state_manifest_verified": True,
    }
    if not _typed_equal(lock.get("anfis_20260613_state_bundle"), expected_anfis):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ ANFIS 20260613 binding drifted"
        )

    prior = lock.get("p1_1729_publication")
    if not isinstance(prior, Mapping) or not _typed_equal(
        prior.get("records"), [dict(record) for record in EXPECTED_P1_1729_RECORDS]
    ):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ predecessor P1/1729 records drifted"
        )
    expected_prior_fields = {
        "completion_marker_written_last": True,
        "consumer_commit": "5d8bbef0fe58e57cd2180570bd6aef5f07923781",
        "consumer_commit_scope_verified": True,
        "future_outcomes_accessed": False,
        "model_unavailable_semantics_verified": True,
        "records_sha256": "2f12aab857838c5e58d7257a952e0296721b5380958b641b312986d1aeda6895",
        "sequence_commit": "82c0bc10a8b17ab700a8f0c28491a60572a11d81",
        "sequence_commit_scope_verified": True,
    }
    if any(not _typed_equal(prior.get(key), value) for key, value in expected_prior_fields.items()):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ predecessor P1/1729 semantic seals drifted"
        )

    prior_20260612 = lock.get("p1_20260612_publication")
    if not isinstance(prior_20260612, Mapping) or not _typed_equal(
        prior_20260612.get("records"),
        [dict(record) for record in EXPECTED_P1_20260612_RECORDS],
    ):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ predecessor P1/20260612 records drifted"
        )
    expected_prior_20260612_fields = {
        "completion_marker_written_last": True,
        "consumer_commit": "5b2c5d6b4f4c296c9485d1cb22561086aeeb6b85",
        "consumer_commit_scope_verified": True,
        "future_outcomes_accessed": False,
        "model_unavailable_semantics_verified": True,
        "records_sha256": "afaa74803cd3816c167d63f8e0f59223a8d071d0c0d64f5bc058bccf19a405a5",
        "sequence_commit": "b448e1fb0ee75b6135da11f0ea9a8877d89e0ee1",
        "sequence_commit_scope_verified": True,
    }
    if any(
        not _typed_equal(prior_20260612.get(key), value)
        for key, value in expected_prior_20260612_fields.items()
    ):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ predecessor P1/20260612 semantic seals drifted"
        )

    components = lock.get("patch_components")
    if not isinstance(components, Mapping) or not _typed_equal(
        components.get("records"), [dict(record) for record in EXPECTED_E0_MJ_PATCH_RECORDS]
    ):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ patch component bindings drifted"
        )
    if components.get("count") != len(EXPECTED_E0_MJ_PATCH_RECORDS):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ patch component count drifted"
        )

    sequence_prelock = lock.get("sequence_prelock")
    if not isinstance(sequence_prelock, Mapping) or any(
        not _typed_equal(sequence_prelock.get(field), value)
        for field, value in {
            "all_absent_at_lock": True,
            "base_seed": BASE_SEED,
            "count": len(P1_SLOT_PATHS),
            "model_id": MODEL_ID,
            "paths": [path.as_posix() for path in P1_SLOT_PATHS],
            "paths_sha256": _path_digest(P1_SLOT_PATHS),
        }.items()
    ):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ target namespace prelock seal drifted"
        )
    expected_seals = {
        "anfis_20260613_state_bundle_preserved": True,
        "does_not_replace_e0_m": True,
        "e0_mh_preserved_as_historical_authority": True,
        "e0_mi_preserved_as_historical_authority": True,
        "holdout_accessed": False,
        "later_seed_namespaces_absent_at_lock": True,
        "only_builder_and_test_superseded_from_e0_mh": True,
        "p1_1729_consumer_bundle_preserved": True,
        "p1_1729_sequence_bundle_preserved": True,
        "p1_20260612_consumer_bundle_preserved": True,
        "p1_20260612_sequence_bundle_preserved": True,
        "post_2021_outcomes_accessed": False,
        "scientific_sequence_contract_changed": False,
        "seed_order_changed": False,
        "target_seed_namespace_absent_at_lock": True,
    }
    if not _typed_equal(lock.get("seals"), expected_seals):
        raise ClosureP1Seed20260613SequenceAuditError("E0-MJ scientific seals drifted")
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
        "publication_order": [
            "sequence_parquet",
            "summary_csv",
            "manifest_json",
        ],
        "rollback": "reverse_owned_inode_only",
        "sigkill_between_distinct_directories_is_detected_not_atomic": True,
        "temporary_creation": "exclusive_regular_inode",
        "uncoordinated_external_dvc_creator_excluded": False,
    }
    if not _typed_equal(lock.get("sequence_atomicity"), expected_atomicity):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ sequence atomicity contract drifted"
        )

    expected_companion_identity = {
        "manifest_version": "closure_p1_sequence_seed_20260613_patch_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "gate": "E0-MJ",
        "patch_id": "p1_sequence_seed_20260613_authority_patch_1",
        "authoritative_contract": False,
        "authoritative_lock_path": E0_MJ_LOCK_PATH.as_posix(),
        "authorized_model_id": MODEL_ID,
        "authorized_base_seed": BASE_SEED,
        "batch_seed_execution_authorized": False,
        "dvc_commands_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "fit_attempt_authorized": False,
        "future_outcomes_accessed": False,
        "p1_consumer_authorized": False,
        "p1_fit_authorized": False,
        "p1_sequence_builder_authorized": False,
        "prior_p1_1729_slot_completed": True,
        "prior_p1_20260612_slot_completed": True,
        "publication_required": True,
        "replacement_authorized": False,
        "retry_authorized": False,
        "effective_in_payload": False,
        "physical_inputs_only": True,
        "historical_inputs_compared_to_current_paths": False,
        "completion_marker_written_last": True,
    }
    for field, value in expected_companion_identity.items():
        if not _typed_equal(companion.get(field), value):
            raise ClosureP1Seed20260613SequenceAuditError(
                f"E0-MJ companion identity drifted: {field}"
            )
    if not _typed_equal(
        companion.get("inputs"), [dict(record) for record in EXPECTED_E0_MJ_INPUT_RECORDS]
    ):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ companion physical inputs drifted"
        )
    if not _typed_equal(
        companion.get("historical_inputs"),
        [dict(record) for record in EXPECTED_HISTORICAL_INPUTS],
    ):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ companion historical inputs drifted"
        )
    expected_script = {
        **_physical_record(EXPECTED_E0_MJ_PATCH_RECORDS[4]),
        "role": "generating_script",
    }
    if not _typed_equal(companion.get("script"), expected_script):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ companion script binding drifted"
        )
    expected_output = {
        **dict(lock_record),
        "role": "external_p1_sequence_seed_20260613_patch_lock",
    }
    if not _typed_equal(companion.get("outputs"), [expected_output]):
        raise ClosureP1Seed20260613SequenceAuditError(
            "E0-MJ companion lock binding drifted"
        )
    return {
        "validation_scope": "exact_physical_records_and_locked_semantic_seals",
        "lock_record": dict(lock_record),
        "physical_input_count": len(EXPECTED_E0_MJ_INPUT_RECORDS),
        "physical_patch_component_count": len(EXPECTED_E0_MJ_PATCH_RECORDS),
        "historical_inputs_compared_to_current_paths": False,
        "state_bundle_physically_reconciled": True,
        "prior_p1_1729_physically_reconciled": True,
        "prior_p1_20260612_physically_reconciled": True,
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
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 manifest top-level dialect drifted"
        )
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
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/20260613 manifest field drifted: {field}"
            )
    generated_at = payload.get("generated_at_utc")
    if not isinstance(generated_at, str):
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 manifest timestamp is absent"
        )
    try:
        parsed = datetime.fromisoformat(generated_at)
    except ValueError as exc:
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 manifest timestamp is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 manifest timestamp must be timezone-aware"
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
            raise ClosureP1Seed20260613SequenceAuditError(
                f"P1/20260613 manifest section drifted: {field}"
            )
    counts = payload.get("counts")
    if not isinstance(counts, Mapping) or set(counts) != MANIFEST_COUNT_KEYS:
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 manifest count dialect drifted"
        )
    if not _typed_equal(dict(counts), _manifest_counts(audit, boundary)):
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 manifest counts differ from reconstruction"
        )


def _fit_evidence(frame: pd.DataFrame) -> dict[str, Any]:
    try:
        return historical._fit_evidence(frame)
    except historical.ClosureP1SequenceAuditError as exc:
        raise ClosureP1Seed20260613SequenceAuditError(str(exc)) from exc


def _manifest_last_evidence(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if manifest.get("completion_marker_written_last") is not True:
        raise ClosureP1Seed20260613SequenceAuditError(
            "P1/20260613 completion marker seal drifted"
        )
    return {
        "publication_order": [
            P1_SEQUENCE_PATH.as_posix(),
            P1_SUMMARY_PATH.as_posix(),
            P1_MANIFEST_PATH.as_posix(),
        ],
        "e0_mj_atomicity_contract_reconciled": True,
        "exact_bundle_hashes_reconciled": True,
        "completion_marker_written_last": True,
        "filesystem_mtime_used_as_evidence": False,
    }


def _audit_p1_seed_20260613_sequence_bundle() -> dict[str, Any]:
    result: dict[str, Any]
    with historical.secure_reads._RepoReadSession(PROJECT_ROOT) as session:
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
            _assert_pinned_record(file_for(Path(str(expected["path"]))), expected)
            for expected in EXPECTED_INPUT_RECORDS
        ]
        support_records = [
            _assert_pinned_record(file_for(Path(str(expected["path"]))), expected)
            for expected in EXPECTED_SUPPORT_RECORDS
        ]
        e0_mj_physical_records: dict[str, dict[str, Any]] = {}
        for expected in (*EXPECTED_E0_MJ_INPUT_RECORDS, *EXPECTED_E0_MJ_PATCH_RECORDS):
            path = Path(str(expected["path"]))
            observed = _assert_pinned_record(file_for(path), _physical_record(expected))
            e0_mj_physical_records[path.as_posix()] = observed
        for expected in EXPECTED_PRIOR_P1_RECORDS:
            _assert_pinned_record(
                file_for(Path(str(expected["path"]))), _physical_record(expected)
            )
        bundle_records = {
            path: _assert_pinned_record(file_for(Path(path)), expected)
            for path, expected in EXPECTED_BUNDLE_RECORDS.items()
        }

        sequence_file = file_for(P1_SEQUENCE_PATH)
        pointer_file = file_for(P1_POINTER_PATH) if pointer_present else None
        dvc_registration = _validate_dvc_pointer(sequence_file, pointer_file)

        state_file = file_for(P1_STATE_PATH)
        state_manifest_file = file_for(P1_STATE_MANIFEST_PATH)
        state_manifest = _decode_strict_json(
            state_manifest_file.payload,
            path=P1_STATE_MANIFEST_PATH.as_posix(),
        )
        _assert_canonical_json(
            state_manifest_file.payload,
            state_manifest,
            path=P1_STATE_MANIFEST_PATH.as_posix(),
        )
        _validate_state_manifest(state_manifest, state_record=state_file.record)

        mj_lock_file = file_for(E0_MJ_LOCK_PATH)
        mj_companion_file = file_for(E0_MJ_COMPANION_PATH)
        mj_lock = _decode_strict_json(
            mj_lock_file.payload,
            path=E0_MJ_LOCK_PATH.as_posix(),
        )
        mj_companion = _decode_strict_json(
            mj_companion_file.payload,
            path=E0_MJ_COMPANION_PATH.as_posix(),
        )
        _assert_canonical_json(
            mj_lock_file.payload,
            mj_lock,
            path=E0_MJ_LOCK_PATH.as_posix(),
            sort_keys=True,
        )
        _assert_canonical_json(
            mj_companion_file.payload,
            mj_companion,
            path=E0_MJ_COMPANION_PATH.as_posix(),
            sort_keys=True,
        )
        e0_mj = _validate_e0_mj_reference(
            mj_lock,
            mj_companion,
            lock_record=mj_lock_file.record,
            physical_records=e0_mj_physical_records,
        )

        assignment = _load_assignment(file_for(DEFAULT_ASSIGNMENT).payload)
        common = pd.read_parquet(
            io.BytesIO(file_for(Path(str(EXPECTED_INPUT_RECORDS[0]["path"]))).payload),
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
            raise ClosureP1Seed20260613SequenceAuditError(
                "P1/20260613 reconstructed role counts drifted"
            )
        if build_audit.status_counts != EXPECTED_STATUS_COUNTS:
            raise ClosureP1Seed20260613SequenceAuditError(
                "P1/20260613 reconstructed status counts drifted"
            )
        if build_audit.failure_reason_counts != EXPECTED_FAILURE_REASON_COUNTS:
            raise ClosureP1Seed20260613SequenceAuditError(
                "P1/20260613 reconstructed failure reasons drifted"
            )
        if (
            build_audit.delta_previous_month_missing_history_values
            != EXPECTED_DELTA_MISSING_HISTORY
            or build_audit.delta_previous_month_missing_target_values != 0
        ):
            raise ClosureP1Seed20260613SequenceAuditError(
                "P1/20260613 reconstructed delta audit drifted"
            )

        expected_table = sequence_arrow_table(expected_frame)
        physical_schema, actual_table = _parquet_table(sequence_file)
        if physical_schema.names != list(SEQUENCE_COLUMNS):
            raise ClosureP1Seed20260613SequenceAuditError(
                "P1/20260613 Parquet schema has extra or reordered columns"
            )
        physical = _validate_physical_payload(actual_table)
        differing_columns = [
            column
            for column in SEQUENCE_COLUMNS
            if not actual_table.column(column).equals(expected_table.column(column))
        ]
        if differing_columns or actual_table.num_rows != expected_table.num_rows:
            raise ClosureP1Seed20260613SequenceAuditError(
                "P1/20260613 rows differ from sealed reconstruction: "
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
            raise ClosureP1Seed20260613SequenceAuditError(
                "P1/20260613 physical null evidence drifted"
            )

        boundary_columns = [
            "source_id",
            "site_id",
            "holdout_group_id",
            "assignment_role",
            "target_year_month",
        ]
        boundary = _derive_boundary_evidence(
            actual_table.select(boundary_columns).to_pandas(), assignment
        )
        summary_file = file_for(P1_SUMMARY_PATH)
        if summary_file.payload != _summary_bytes(expected_frame):
            raise ClosureP1Seed20260613SequenceAuditError(
                "P1/20260613 summary bytes differ from reconstruction"
            )

        manifest_file = file_for(P1_MANIFEST_PATH)
        manifest = _decode_strict_json(
            manifest_file.payload,
            path=P1_MANIFEST_PATH.as_posix(),
        )
        _assert_canonical_json(
            manifest_file.payload, manifest, path=P1_MANIFEST_PATH.as_posix()
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
        publication = _manifest_last_evidence(manifest)
        fit = _fit_evidence(expected_frame)

        namespace_after = _namespace_snapshot(session)
        if namespace_before != namespace_after:
            raise ClosureP1Seed20260613SequenceAuditError(
                "P1/20260613 audit namespace changed during readback"
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
            "e0_mj": e0_mj,
            "outputs": [
                bundle_records[path.as_posix()]
                for path in (P1_SEQUENCE_PATH, P1_SUMMARY_PATH, P1_MANIFEST_PATH)
            ],
            "counts": _manifest_counts(build_audit, boundary),
            "development_boundary": boundary,
            "physical_evidence": physical,
            "fit_availability": fit,
            "publication_evidence": publication,
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
            "e0_m_authorized": False,
            "e0_u_authorized": False,
            "bundle_future_outcomes_accessed": False,
            "future_outcomes_accessed_by_auditor": False,
        }
    result["pinned_read_session_verified"] = True
    return result


def audit_p1_seed_20260613_sequence_bundle() -> dict[str, Any]:
    """Audit the closed P1/20260613 bundle without mutating repository state."""
    try:
        return _audit_p1_seed_20260613_sequence_bundle()
    except ClosureP1Seed20260613SequenceAuditError:
        raise
    except historical.ClosureP1SequenceAuditError as exc:
        raise ClosureP1Seed20260613SequenceAuditError(str(exc)) from exc
    except historical.secure_reads.ClosureP0SequenceAuditError as exc:
        raise ClosureP1Seed20260613SequenceAuditError(
            str(exc).replace("P0", "P1/20260613")
        ) from exc


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only audit of the closed Closure V1 P1/20260613 sequence bundle."
        )
    )
    parser.add_argument(
        CHECK_ONLY_FLAG,
        action="store_true",
        required=True,
        help="Reopen and validate the fixed P1/20260613 bundle without writing outputs.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    parse_args(argv)
    try:
        result = audit_p1_seed_20260613_sequence_bundle()
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
