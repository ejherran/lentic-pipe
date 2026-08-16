#!/usr/bin/env python
"""Build the outcome-free source evidence consumed by Closure V1 E10.

The six files produced here are *inputs* to the sealed E10 component.  They
live outside the final ``reports/closure_v1/10_api`` namespace so that tests,
OpenAPI generation, the synthetic API workflow, and environment capture all
finish before the first E0-U outcome open.  A seventh file is an atomic bundle
manifest; it is deliberately published last.

Generation is tied to one exact, clean, published H commit.  The check-only
path performs no filesystem writes and launches none of the verification
suites.  The generator never commits, pushes, tags, or opens Closure targets.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import ctypes
import errno
import hashlib
import json
import os
import platform
import re
import secrets
import stat
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict, cast
from urllib.parse import urlsplit, urlunsplit


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    # The evidence commands deliberately use the versioned file entrypoint.
    # Add only this repository root so direct execution resolves ``src.*``.
    sys.path.insert(0, str(PROJECT_ROOT))
SCHEMA_VERSION = "closure_e10_source_evidence_bundle_v1"
RECOVERY_SCHEMA_VERSION = "closure_e10_source_evidence_recovery_bundle_v1"
GATE = "E10-S"
RECOVERY_ATTEMPT_1 = "recovery-attempt-1"
INITIAL_PHASE3_H_COMMIT = "9e66478d7c071067a750e7dd9a6a318fa93a2c88"
BUILDER_SOURCE_PATH = Path(
    "src/experiments/build_closure_e10_source_evidence.py"
)

SOURCE_EVIDENCE_DIRECTORY = Path(
    "reports/closure_v1/00_protocol/software_evidence_source"
)
SOURCE_EVIDENCE_PATHS = {
    "public_tests_xml": SOURCE_EVIDENCE_DIRECTORY / "public_tests.xml",
    "test_report": SOURCE_EVIDENCE_DIRECTORY / "test_report.md",
    "openapi": SOURCE_EVIDENCE_DIRECTORY / "openapi.json",
    "openapi_contract_report": (
        SOURCE_EVIDENCE_DIRECTORY / "openapi_contract_report.md"
    ),
    "end_to_end_report": SOURCE_EVIDENCE_DIRECTORY / "end_to_end_report.md",
    "environment": SOURCE_EVIDENCE_DIRECTORY / "environment.json",
}
SOURCE_EVIDENCE_KEYS = tuple(SOURCE_EVIDENCE_PATHS)
SOURCE_MANIFEST_PATH = (
    SOURCE_EVIDENCE_DIRECTORY / "software_evidence_source_manifest.json"
)
RECOVERY_SOURCE_EVIDENCE_DIRECTORY = Path(
    "reports/closure_v1/00_protocol/software_evidence_source_recovery_1"
)
RECOVERY_SOURCE_EVIDENCE_PATHS = {
    key: RECOVERY_SOURCE_EVIDENCE_DIRECTORY / path.name
    for key, path in SOURCE_EVIDENCE_PATHS.items()
}
RECOVERY_SOURCE_MANIFEST_PATH = (
    RECOVERY_SOURCE_EVIDENCE_DIRECTORY / "software_evidence_source_manifest.json"
)

FINAL_E10_DIRECTORY = Path("reports/closure_v1/10_api")
OUTCOME_ACCESS_LOG_PATH = Path(
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl"
)
RECOVERY_ACTIVATION_PATH = Path(
    "reports/closure_v1/00_protocol/closure_e0_u_recovery_activation.json"
)
ATTEMPT_1_FAILURE_RECEIPT_PATH = Path(
    "reports/closure_v1/00_protocol/closure_e0_u_attempt_1_failure.json"
)
ATTEMPT_1_FAILURE_RECEIPT_BYTES = 1501
ATTEMPT_1_FAILURE_RECEIPT_SHA256 = (
    "57d2a6f7560d40c61a7e4d370825cb68b5cabaaeda6131420a2fd63787ea3b06"
)
RECOVERY_OUTCOME_LOG_BYTES = 256
RECOVERY_OUTCOME_LOG_SHA256 = (
    "ae3e47dd6ad1f05cd79e6a494174f951f1c71fa9336514640bd4c15855c1b038"
)
PHASE3_OVERLAY_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/phase3_input_overlay_manifest.json"
)
PHASE3_OVERLAY_POINTER_PATHS = (
    Path("data/closure_v1/locked_evaluation/phase3_runtime_weights.npz.dvc"),
    Path("data/closure_v1/locked_evaluation/adaptive_state_warmup.parquet.dvc"),
)
RECOVERY_INHERITED_P1_PATHS = (
    *(SOURCE_EVIDENCE_PATHS[key] for key in SOURCE_EVIDENCE_KEYS),
    SOURCE_MANIFEST_PATH,
    *PHASE3_OVERLAY_POINTER_PATHS,
    PHASE3_OVERLAY_MANIFEST_PATH,
)
RECOVERY_HISTORICAL_CHAIN = {
    "base_r_commit": "4c92ed7249a91b7dd541fd22dde68b61574556b2",
    "h1_commit": INITIAL_PHASE3_H_COMMIT,
    "p1_commit": "caaf2d6d0a00a31febeed89b54ea078b60d7f92a",
    "u1_commit": "4aecf19cd913b82a6a3d26669f09684e67efda8a",
}
FORBIDDEN_OUTCOME_PREFIXES = (
    "data/targets",
    "data/closure_v1/unblinded",
    "data/closure_v1/evaluation_outcomes",
    OUTCOME_ACCESS_LOG_PATH.as_posix(),
)
FORBIDDEN_CONTEXT_PREFIXES = ("private/FULL.md",)
FORBIDDEN_VERIFICATION_PREFIXES = (
    *FORBIDDEN_OUTCOME_PREFIXES,
    *FORBIDDEN_CONTEXT_PREFIXES,
)
OUTCOME_FREE_GIT_STATUS_ARGUMENTS = (
    "status",
    "--porcelain=v1",
    "--untracked-files=all",
    "--",
    ".",
    *(f":(exclude,top){path}" for path in FORBIDDEN_VERIFICATION_PREFIXES),
)

GUARD_PATH = Path("tmp/closure_v1_e10_source_evidence.guard")
WORK_PREFIX = "closure_v1_e10_source_evidence_"

PUBLIC_SUITE_KIND = "closure_phase3_public"
PUBLIC_PHASE3_TEST_PATHS = (
    "tests/test_audit_closure_p0_model_availability.py",
    "tests/test_audit_closure_p0_sequence_bundle.py",
    "tests/test_build_closure_e10_source_evidence.py",
    "tests/test_closure_e0_u_activation_lock.py",
    "tests/test_closure_e0_u_authority.py",
    "tests/test_closure_e6_e9_unavailable.py",
    "tests/test_closure_phase3_context.py",
    "tests/test_closure_phase3_e1_e2_e3_e5_contracts.py",
    "tests/test_closure_phase3_e4_e7_contracts.py",
    "tests/test_closure_phase3_e8_locked_uncertainty.py",
    "tests/test_closure_phase3_input_overlay.py",
)
PUBLIC_API_TEST_PATHS = (
    "tests/test_api_counterfactual_simulation.py",
    "tests/test_api_dataset_validation.py",
    "tests/test_api_experiment_scientific_datasets.py",
    "tests/test_api_job_science_adapters.py",
    "tests/test_api_minimal_workflow.py",
    "tests/test_api_predictions_alerts.py",
    "tests/test_api_run_artifacts.py",
    "tests/test_api_run_executor.py",
    "tests/test_api_run_planner.py",
    "tests/test_api_run_scientific_outputs.py",
    "tests/test_api_scientific_workflow_adapters.py",
    "tests/test_api_system.py",
    "tests/test_api_workspace_catalog.py",
)
PUBLIC_PHASE3_PRECOMMIT_TEST_NODES = (
    "tests/test_prepare_commit_artifacts.py::test_closure_e0_u_precommit_compares_configured_origin_not_live_evidence_url",
    "tests/test_prepare_commit_artifacts.py::test_closure_e0_u_activation_is_an_exact_authoritative_manifest_without_outputs",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_selector_is_exact13_unstaged_and_parent_scoped",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_selector_is_exact_unstaged_and_base_scoped",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_invocation_forbids_dvc_mutation",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_staged_transaction_binds_exact_modes_and_blobs",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_staged_transaction_binds_patch_and_final_tree",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_main_bypasses_historical_e0_m_selectors",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_main_precedes_full_h_and_historical_selectors",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_transaction_only_stages_exact40_and_runs_generic_checks",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_transaction_end_to_end_synthetic",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_post_add_failure_restores_exact13_unstaged",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_full_h_post_add_failure_restores_exact40_unstaged",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_rollback_failure_reports_primary_and_rollback_errors",
    "tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_rollback_preserves_concurrent_foreign_staged_path",
)
PUBLIC_PHASE3_EXPECTED_TEST_COUNT = 344
PUBLIC_PHASE3_EXPECTED_PASS_COUNT = 335
PUBLIC_PHASE3_EXPECTED_SKIP_COUNT = 9
PUBLIC_TEST_NODEIDS_SHA256 = (
    "a7892dc9ef8ad163867e108c60860a154ff7b0693364a693f93d1a0614eb2ec6"
)
E2E_TEST_NODES = (
    "tests/test_api_predictions_alerts.py::test_api_exposes_current_state_predictions_and_alerts",
    "tests/test_api_counterfactual_simulation.py::test_api_runs_minimal_current_state_counterfactual",
    "tests/test_api_run_artifacts.py::test_api_lists_previews_and_summarizes_run_artifacts",
)
PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES = (
    "tests/test_build_closure_holdout.py::test_protocol_lock_requires_the_exact_selector_hash",
    "tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[assignment_created-holdout_assignment_created=false]",
    "tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[dirty_locked_repository-worktree_status='clean']",
    "tests/test_build_closure_holdout.py::test_cli_dry_run_does_not_read_panel_or_write_outputs",
    "tests/test_closure_final_calibration.py::test_lock_validation_rejects_authorization_and_boundary_drifts",
    "tests/test_closure_final_calibration.py::test_output_contract_is_exact_manifest_last_and_zero_overlap",
)
PUBLIC_PRE_E0U_EXCLUDED_TEST_BASES = tuple(
    dict.fromkeys(nodeid.split("[", 1)[0] for nodeid in PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES)
)
PUBLIC_PRE_E0U_EXCLUSION_REASON = (
    "Closure E10 pre-E0-U public suite excludes this repository-target-dependent "
    "historical protocol test; its target-bearing audit is not authorized before "
    "the one-shot outcome open"
)
PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES = (
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py::test_registration_helper_cli_and_lazy_authority_loader_are_exact",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py::test_mz_registration_transaction_restores_owned_partial_metadata",
    "tests/test_closure_development_runtime_patch.py::test_full_history_detects_modify_restore_hidden_behind_merge",
)
PUBLIC_USER_PROHIBITED_GIT_COMMIT_EXCLUSION_REASON = (
    "user_prohibited_git_commit_fixture"
)
PUBLIC_PHASE3_EXTRA_TEST_NODES = tuple(
    (
        *PUBLIC_PHASE3_PRECOMMIT_TEST_NODES,
        *PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES,
        *PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES,
    )
)
PUBLIC_TEST_PATHS = (*PUBLIC_PHASE3_TEST_PATHS, *PUBLIC_API_TEST_PATHS)
PUBLIC_TEST_SELECTORS = (*PUBLIC_TEST_PATHS, *PUBLIC_PHASE3_EXTRA_TEST_NODES)
PUBLIC_TEST_SELECTOR_SHA256 = hashlib.sha256(
    "\0".join(PUBLIC_TEST_SELECTORS).encode("utf-8")
).hexdigest()
PUBLIC_TEST_COMMAND_PREFIX = (
    "poetry",
    "run",
    "pytest",
    *PUBLIC_TEST_SELECTORS,
    "-ra",
    "-p",
    "src.experiments.build_closure_e10_source_evidence",
    "-p",
    "no:cacheprovider",
)
E2E_FIXTURE_CONTRACT = {
    "fixture_kind": "synthetic_external_non_closure_outcome",
    "source_id": "external",
    "closure_holdout_member": False,
    "wqp_source_used": False,
    "future_target_used": False,
    "target_namespace_opened": False,
    "outcome_access_log_opened": False,
    "private_full_opened": False,
    "scientific_scope": (
        "dataset registration, deterministic fuzzy current-state scoring, "
        "prediction/alert query, bounded counterfactual simulation, and "
        "artifact/result query"
    ),
}

DOCUMENTED_API_PATHS = (
    Path("docs/API_PROTOCOL.md"),
    Path("docs/API_DATASET_CONTRACT.md"),
)
DVC_RESTORE_POINTERS = (
    Path("data/closure_v1/locked_evaluation/input_history.parquet.dvc"),
    Path("data/closure_v1/locked_evaluation/intent_origins.parquet.dvc"),
    Path("data/closure_v1/locked_evaluation/origin_features.parquet.dvc"),
    Path("data/closure_v1/locked_evaluation/sequence_features.parquet.dvc"),
)

SANDBOX_OUTPUT_PATH = Path("tmp/closure_v1_e10_source_evidence_outputs")
BWRAP_BACKEND = "/usr/bin/bwrap"
MASK_WORK_PREFIX = "closure_v1_e10_mask_"
BWRAP_ISOLATED_COMMAND_NAMES = (
    "filesystem_denial_probe",
    "public_tests",
    "openapi_generation",
    "end_to_end",
    "runtime_probe",
)


class RestrictedMaskSpec(TypedDict):
    path: str
    entry_type: str
    mode: str
    mechanism: str
    metadata_placeholders: list[str]


RESTRICTED_MASK_SPECS: tuple[RestrictedMaskSpec, ...] = (
    {
        "path": "data/targets",
        "entry_type": "metadata_only_directory",
        "mode": "555",
        "mechanism": "synthetic_read_only_bind_hiding_real_target_tree",
        "metadata_placeholders": [
            "monthly_targets_model_v0.parquet",
            "target_manifest_v0.json",
        ],
    },
    {
        "path": "data/closure_v1/unblinded",
        "entry_type": "opaque_empty_directory",
        "mode": "555",
        "mechanism": "synthetic_opaque_empty_read_only_overlay",
        "metadata_placeholders": [],
    },
    {
        "path": "data/closure_v1/evaluation_outcomes",
        "entry_type": "opaque_empty_directory",
        "mode": "555",
        "mechanism": "synthetic_opaque_empty_read_only_overlay",
        "metadata_placeholders": [],
    },
    {
        "path": "reports/closure_v1/00_protocol/outcome_access_log.jsonl",
        "entry_type": "tracked_empty_file",
        "mode": "444",
        "mechanism": "synthetic_tracked_empty_read_only_file_bind",
        "metadata_placeholders": [],
    },
    {
        "path": "private/FULL.md",
        "entry_type": "regular_file",
        "mode": "000",
        "mechanism": "synthetic_empty_read_only_file_bind",
        "metadata_placeholders": [],
    },
)
ISOLATED_ENVIRONMENT_VALUES = {
    "GIT_OPTIONAL_LOCKS": "0",
    "HOME": "/tmp/closure_e10_home",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": (
        "/workspace/.venv/bin:/opt/closure-user-local/bin:"
        "/usr/local/bin:/usr/bin:/bin"
    ),
    "PYTHONHASHSEED": "0",
    "TMPDIR": "/tmp",
    "TZ": "UTC",
    "VIRTUAL_ENV": "/workspace/.venv",
    "XDG_CACHE_HOME": "/tmp/closure_e10_cache",
}
STATIC_ACCESS_INVENTORY = (
    "exact positive Closure Phase 3 public suite inventory: twenty-four sealed "
    "test files plus twenty-four additional exact node selectors; six target-dependent "
    "nodes and three user-prohibited Git-commit fixture nodes remain collected "
    "as explicit skips; exact count, uniqueness and sorted node-id digest are "
    "fail-closed; no repository-wide pytest discovery is claimed or run; "
    "all suite filesystem/subprocess inputs are H-source, tmp fixtures, or "
    "explicitly non-outcome inputs; an exact Git archive of H plus every "
    "permitted H-bound Closure/"
    "model DVC output restored from authenticated local cache is inventoried "
    "before and after and mounted read-only with no ambient ignored files; the "
    "target tree is replaced by exactly "
    "two unreadable metadata placeholders, both outcome directories by opaque "
    "empty read-only views; the tracked empty outcome log is replaced by a "
    "read-only empty mask whose probe returns EOF, and the private context by "
    "an unreadable empty read-only file"
)
ISOLATION_PROBE_CODE = (
    "import errno,json,os,stat;from pathlib import Path;"
    "specs=" + repr(RESTRICTED_MASK_SPECS) + ";rows=[];"
    "\nfor spec in specs:\n"
    " raw=spec['path'];p=Path(raw);kind=spec['entry_type']\n"
    " if kind in ('metadata_only_directory','opaque_empty_directory'):\n"
    "  meta=p.lstat();actual=meta.st_mode;mode=format(actual&0o777,'03o')\n"
    "  if not stat.S_ISDIR(actual) or mode != spec['mode']: "
    "raise SystemExit('restricted mask metadata drifted: '+raw)\n"
    "  entries=sorted(os.listdir(p));expected=sorted(spec['metadata_placeholders'])\n"
    "  if entries != expected: raise SystemExit('restricted directory scope drifted: '+raw)\n"
    "  if kind=='metadata_only_directory':\n"
    "   for leaf in expected:\n"
    "    leaf_meta=(p/leaf).lstat()\n"
    "    if not stat.S_ISREG(leaf_meta.st_mode) or leaf_meta.st_mode&0o777: "
    "raise SystemExit('target metadata placeholder drifted: '+leaf)\n"
    "   candidate=p/expected[0];expected_read=errno.EACCES\n"
    "  else:\n"
    "   candidate=p/'__e10_probe__';expected_read=errno.ENOENT\n"
    "  write_candidate=p/'__e10_probe__';write_flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0);expected_write=errno.EROFS\n"
    " else:\n"
    "  meta=p.lstat();actual=meta.st_mode;mode=format(actual&0o777,'03o')\n"
    "  if not stat.S_ISREG(actual) or mode != spec['mode']: "
    "raise SystemExit('restricted mask metadata drifted: '+raw)\n"
    "  if meta.st_size != 0 or meta.st_nlink != 1: raise SystemExit('restricted file mask identity drifted: '+raw)\n"
    "  candidate=p;write_candidate=p;write_flags=os.O_WRONLY|getattr(os,'O_NOFOLLOW',0);expected_write=errno.EACCES\n"
    "  if kind=='tracked_empty_file':\n"
    "   if candidate.read_bytes() != b'': raise SystemExit('tracked empty mask is not empty: '+raw)\n"
    "   read_errno=0;read_result='synthetic_empty_eof';expected_read=0\n"
    "  else:\n"
    "   expected_read=errno.EACCES\n"
    " if kind!='tracked_empty_file':\n"
    "  try:\n   candidate.open('rb').close()\n"
    "  except OSError as exc:\n   read_errno=exc.errno\n"
    "  else:\n   raise SystemExit('restricted path opened: '+raw)\n"
    "  read_result='denied' if read_errno==errno.EACCES else 'absent_from_opaque_empty_view'\n"
    " try:\n  write_fd=os.open(write_candidate,write_flags,0o600);os.close(write_fd)\n"
    " except OSError as exc:\n  write_errno=exc.errno\n"
    " else:\n  raise SystemExit('restricted path created: '+raw)\n"
    " if read_errno != expected_read or write_errno != expected_write: "
    "raise SystemExit('unexpected denial errno: '+raw+':'"
    "+str(read_errno)+':'+str(write_errno))\n"
    " rows.append({**spec,'read_errno':read_errno,'read_result':read_result,'write_errno':write_errno})\n"
    "print(json.dumps(rows,sort_keys=True,separators=(',',':')))"
)

_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "options", "head"})
_COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
EMPTY_GIT_BLOB_SHA1 = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
EMPTY_GIT_TREE_SHA1 = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
_DOCUMENTED_OPERATION_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+"
    r"(/[A-Za-z0-9_{}./-]+)"
)
_OUTCOME_GUARD_INSTALLED = False


class ClosureE10SourceEvidenceError(RuntimeError):
    """Raised when E10 source evidence cannot be proven or published safely."""


def _require_recovery_attempt(value: str | None) -> str | None:
    if value not in {None, RECOVERY_ATTEMPT_1}:
        raise ClosureE10SourceEvidenceError(
            "E10 source recovery mode is not exact recovery-attempt-1"
        )
    return value


def _source_bundle_layout(
    recovery_attempt: str | None,
) -> tuple[Path, Mapping[str, Path], Path]:
    mode = _require_recovery_attempt(recovery_attempt)
    if mode == RECOVERY_ATTEMPT_1:
        return (
            RECOVERY_SOURCE_EVIDENCE_DIRECTORY,
            RECOVERY_SOURCE_EVIDENCE_PATHS,
            RECOVERY_SOURCE_MANIFEST_PATH,
        )
    return SOURCE_EVIDENCE_DIRECTORY, SOURCE_EVIDENCE_PATHS, SOURCE_MANIFEST_PATH


def _resolve_loader_recovery_attempt(
    repo_root: Path,
    expected_h_commit: str,
    requested: str | None,
) -> str | None:
    mode = _require_recovery_attempt(requested)
    commit = _require_commit(expected_h_commit, context="loader H commit")
    if mode is not None or commit == INITIAL_PHASE3_H_COMMIT:
        return mode
    if os.path.lexists(repo_root / RECOVERY_SOURCE_EVIDENCE_DIRECTORY):
        return RECOVERY_ATTEMPT_1
    return None


def _expected_denial_probe_results() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for spec in RESTRICTED_MASK_SPECS:
        kind = spec["entry_type"]
        if kind == "metadata_only_directory":
            read_errno, read_result, write_errno = 13, "denied", 30
        elif kind == "opaque_empty_directory":
            read_errno, read_result, write_errno = (
                2,
                "absent_from_opaque_empty_view",
                30,
            )
        elif kind == "tracked_empty_file":
            read_errno, read_result, write_errno = (
                0,
                "synthetic_empty_eof",
                13,
            )
        elif kind == "regular_file":
            read_errno, read_result, write_errno = 13, "denied", 13
        else:
            raise ClosureE10SourceEvidenceError(
                "restricted mask type drifted"
            )
        results.append(
            {
                **cast(Mapping[str, Any], spec),
                "read_errno": read_errno,
                "read_result": read_result,
                "write_errno": write_errno,
            }
        )
    return results


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _pretty_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _md5(payload: bytes) -> str:
    # DVC pointer verification must use the algorithm declared by the pointer.
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


def _public_suite_contract_record() -> dict[str, Any]:
    """Return the exact positive selector and expected JUnit contract."""

    skip_nodes = (
        *PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES,
        *PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES,
    )
    return {
        "public_suite_kind": PUBLIC_SUITE_KIND,
        "public_suite_phase3_test_paths": list(PUBLIC_PHASE3_TEST_PATHS),
        "public_suite_api_test_paths": list(PUBLIC_API_TEST_PATHS),
        "public_suite_precommit_test_nodes": list(
            PUBLIC_PHASE3_PRECOMMIT_TEST_NODES
        ),
        "public_suite_skip_test_nodes": list(skip_nodes),
        "public_suite_selectors": list(PUBLIC_TEST_SELECTORS),
        "public_suite_selector_count": len(PUBLIC_TEST_SELECTORS),
        "public_suite_selector_sha256": PUBLIC_TEST_SELECTOR_SHA256,
        "public_suite_nodeids_sha256": PUBLIC_TEST_NODEIDS_SHA256,
        "public_suite_expected_test_count": PUBLIC_PHASE3_EXPECTED_TEST_COUNT,
        "public_suite_expected_pass_count": PUBLIC_PHASE3_EXPECTED_PASS_COUNT,
        "public_suite_expected_skip_count": PUBLIC_PHASE3_EXPECTED_SKIP_COUNT,
    }


def _require_commit(value: str, *, context: str = "repository commit") -> str:
    if not _COMMIT_RE.fullmatch(value):
        raise ClosureE10SourceEvidenceError(f"{context} is not an exact commit")
    return value


def _relative_to_repo(path: Path, repo_root: Path) -> str | None:
    # Python's audit event reports relative paths against the process cwd, not
    # against the repository root captured when the plugin was installed.
    # Tests deliberately chdir into private tmp fixtures; treating those names
    # as repository-relative would both misdescribe the actual open and block
    # benign synthetic files whose basenames resemble Closure paths.
    candidate = path if path.is_absolute() else Path.cwd() / path
    root = repo_root.resolve(strict=True)
    # Normalize ``..`` without following symlinks first.  A repository path
    # remains forbidden even when an attacker replaces one of its parents with
    # a symlink outside the repository.
    try:
        lexical = Path(os.path.abspath(os.fspath(candidate))).relative_to(root)
    except ValueError:
        lexical = None
    if lexical is not None:
        return lexical.as_posix()
    # Also reject an external alias that resolves back into a forbidden
    # repository path.
    try:
        return candidate.resolve(strict=False).relative_to(root).as_posix()
    except (OSError, ValueError):
        return None


def _is_forbidden_outcome_path(path: str | os.PathLike[str], repo_root: Path) -> bool:
    try:
        raw = os.fspath(path)
    except TypeError:
        return False
    if not isinstance(raw, str):
        return False
    relative = _relative_to_repo(Path(raw), repo_root)
    if relative is None:
        return False
    return any(
        relative == prefix or relative.startswith(prefix.rstrip("/") + "/")
        for prefix in FORBIDDEN_VERIFICATION_PREFIXES
    )


def _is_exact_outcome_free_git_status(argv: Sequence[str]) -> bool:
    return (
        len(argv) == len(OUTCOME_FREE_GIT_STATUS_ARGUMENTS) + 1
        and Path(argv[0]).name == "git"
        and tuple(argv[1:]) == OUTCOME_FREE_GIT_STATUS_ARGUMENTS
    )


def _git_subcommand(argv: Sequence[str]) -> str | None:
    git_positions = [
        index for index, token in enumerate(argv) if Path(token).name == "git"
    ]
    if not git_positions:
        return None
    index = git_positions[0] + 1
    options_with_value = {
        "-C",
        "-c",
        "--git-dir",
        "--work-tree",
        "--namespace",
    }
    while index < len(argv):
        token = argv[index]
        if token in options_with_value:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token
    return None


def install_outcome_access_guard(repo_root: Path | None = None) -> None:
    """Reject Python opens and explicit subprocess references to outcomes.

    Pytest loads this module with ``-p`` for the public and E2E suites.  The
    audit hook is process-local and records no paths; it simply fails closed.
    """

    global _OUTCOME_GUARD_INSTALLED
    if _OUTCOME_GUARD_INSTALLED:
        return
    root = (repo_root or Path(os.environ.get("CLOSURE_E10_REPO_ROOT", "."))).resolve()

    def require_safe_process(argv: Any, *, rendered: str) -> None:
        argv_tokens = (
            [str(item) for item in argv]
            if isinstance(argv, (list, tuple))
            else []
        )
        forbidden_tokens = (
            "data/targets",
            "data/closure_v1/unblinded",
            "data/closure_v1/evaluation_outcomes",
            "outcome_access_log",
            "private/FULL.md",
            "--execute-sealed-batch",
        )
        safe_git_status = _is_exact_outcome_free_git_status(argv_tokens)
        if (
            argv_tokens
            and Path(argv_tokens[0]).name
            in {"sh", "bash", "dash", "zsh", "fish", "cmd", "powershell"}
            and any(token in {"-c", "--command", "/c"} for token in argv_tokens[1:])
        ):
            raise ClosureE10SourceEvidenceError(
                "E10 source verification forbids opaque shell command wrappers"
            )
        if (
            any(token in rendered for token in forbidden_tokens)
            and not safe_git_status
        ):
            raise ClosureE10SourceEvidenceError(
                "E10 source verification attempted an outcome-capable process"
            )
        if argv_tokens and _git_subcommand(argv_tokens) in {"commit", "push"}:
            raise ClosureE10SourceEvidenceError(
                "E10 source verification attempted a user-prohibited Git "
                "commit/push"
            )
        if isinstance(argv, (str, bytes)):
            command = argv.decode("utf-8", errors="replace") if isinstance(argv, bytes) else argv
            if re.search(
                r"(?:^|[;&|]\s*)git\s+(?:commit|push)(?:\s|$)",
                command,
            ):
                raise ClosureE10SourceEvidenceError(
                    "E10 source verification attempted a user-prohibited Git "
                    "commit/push"
                )

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event == "open" and args and isinstance(args[0], (str, os.PathLike)):
            if _is_forbidden_outcome_path(args[0], root):
                raise ClosureE10SourceEvidenceError(
                    "E10 source verification attempted to open a restricted "
                    "target/outcome/context path"
                )
        if event == "os.system":
            raise ClosureE10SourceEvidenceError(
                "E10 source verification forbids opaque os.system execution"
            )
        if event in {"os.posix_spawn", "os.posix_spawnp"} and len(args) > 1:
            spawn_argv = args[1]
            require_safe_process(spawn_argv, rendered=str(spawn_argv))
        if event == "subprocess.Popen" and args:
            rendered = " ".join(str(item) for item in args[:2])
            subprocess_argv = args[1] if len(args) > 1 else None
            require_safe_process(subprocess_argv, rendered=rendered)

    sys.addaudithook(audit)
    _OUTCOME_GUARD_INSTALLED = True


def pytest_configure(config: Any) -> None:
    """Install the outcome guard when this module is loaded as a pytest plugin."""

    del config
    if os.environ.get("CLOSURE_E10_OUTCOME_GUARD") != "1":
        raise ClosureE10SourceEvidenceError(
            "E10 pytest plugin requires CLOSURE_E10_OUTCOME_GUARD=1"
        )
    if os.environ.get("CLOSURE_E10_SUITE_KIND") not in {
        PUBLIC_SUITE_KIND,
        "synthetic_e2e",
    }:
        raise ClosureE10SourceEvidenceError(
            "E10 pytest plugin requires an exact CLOSURE_E10_SUITE_KIND"
        )
    install_outcome_access_guard()


def pytest_collection_modifyitems(config: Any, items: Sequence[Any]) -> None:
    """Skip only the sealed, target-dependent tests in the pre-E0-U suite.

    The tests remain collected and therefore appear in JUnit's explicit skip
    ledger.  A renamed or absent test fails closed so this exception cannot
    silently broaden or become stale.  The three synthetic E2E nodes never use
    this policy.
    """

    del config
    if os.environ.get("CLOSURE_E10_SUITE_KIND") != PUBLIC_SUITE_KIND:
        return
    import pytest

    expected_target = set(PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES)
    expected_git = set(PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES)
    observed_nodeids: list[str] = []
    observed_target: set[str] = set()
    observed_git: set[str] = set()
    target_marker = pytest.mark.skip(reason=PUBLIC_PRE_E0U_EXCLUSION_REASON)
    git_marker = pytest.mark.skip(
        reason=PUBLIC_USER_PROHIBITED_GIT_COMMIT_EXCLUSION_REASON
    )
    for item in items:
        nodeid = getattr(item, "nodeid", None)
        if not isinstance(nodeid, str):
            raise ClosureE10SourceEvidenceError(
                "public pytest collection contains a malformed node id"
            )
        observed_nodeids.append(nodeid)
        if nodeid in expected_target:
            item.add_marker(target_marker)
            observed_target.add(nodeid)
        elif nodeid in expected_git:
            item.add_marker(git_marker)
            observed_git.add(nodeid)
    if observed_target != expected_target or observed_git != expected_git:
        raise ClosureE10SourceEvidenceError(
            "public test exclusion registry drifted: "
            f"missing_target={sorted(expected_target.difference(observed_target))}; "
            f"missing_git={sorted(expected_git.difference(observed_git))}"
        )
    if (
        len(observed_nodeids) != PUBLIC_PHASE3_EXPECTED_TEST_COUNT
        or len(set(observed_nodeids)) != PUBLIC_PHASE3_EXPECTED_TEST_COUNT
    ):
        raise ClosureE10SourceEvidenceError(
            "public Phase 3 collection count or uniqueness drifted"
        )
    observed_digest = hashlib.sha256(
        "\0".join(sorted(observed_nodeids)).encode("utf-8")
    ).hexdigest()
    if observed_digest != PUBLIC_TEST_NODEIDS_SHA256:
        raise ClosureE10SourceEvidenceError(
            "public Phase 3 collection node-id digest drifted"
        )


def _metadata_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _open_directory_chain(
    repo_root: Path, directory: Path, *, context: str
) -> tuple[list[int], list[tuple[int, str, int, tuple[int, ...]]], Path]:
    root = repo_root.resolve(strict=True)
    if directory.is_absolute() or ".." in directory.parts:
        raise ClosureE10SourceEvidenceError(f"{context} path escaped repository")
    root_path_metadata = root.lstat()
    if root.is_symlink() or not stat.S_ISDIR(root_path_metadata.st_mode):
        raise ClosureE10SourceEvidenceError(f"{context} root is unsafe")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fds: list[int] = []
    links: list[tuple[int, str, int, tuple[int, ...]]] = []
    try:
        root_fd = os.open(root, flags)
        fds.append(root_fd)
        if _metadata_identity(os.fstat(root_fd)) != _metadata_identity(
            root_path_metadata
        ):
            raise ClosureE10SourceEvidenceError(f"{context} root changed")
        current_fd = root_fd
        for component in directory.parts:
            child_fd = os.open(component, flags, dir_fd=current_fd)
            child_metadata = os.fstat(child_fd)
            if not stat.S_ISDIR(child_metadata.st_mode):
                os.close(child_fd)
                raise ClosureE10SourceEvidenceError(
                    f"{context} parent is not a directory"
                )
            fds.append(child_fd)
            links.append(
                (
                    current_fd,
                    component,
                    child_fd,
                    _metadata_identity(child_metadata),
                )
            )
            current_fd = child_fd
    except OSError as exc:
        for fd in reversed(fds):
            os.close(fd)
        raise ClosureE10SourceEvidenceError(
            f"{context} directory chain cannot be opened"
        ) from exc
    except BaseException:
        for fd in reversed(fds):
            os.close(fd)
        raise
    return fds, links, root


def _recapture_directory_chain(
    *,
    fds: Sequence[int],
    links: Sequence[tuple[int, str, int, tuple[int, ...]]],
    root: Path,
    context: str,
) -> None:
    root_fd_identity = _metadata_identity(os.fstat(fds[0]))
    if _metadata_identity(root.lstat()) != root_fd_identity:
        raise ClosureE10SourceEvidenceError(f"{context} root was replaced")
    for parent_fd, component, child_fd, identity in links:
        if _metadata_identity(os.fstat(child_fd)) != identity:
            raise ClosureE10SourceEvidenceError(
                f"{context} parent changed while anchored"
            )
        entry = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
        if _metadata_identity(entry) != identity or stat.S_ISLNK(entry.st_mode):
            raise ClosureE10SourceEvidenceError(
                f"{context} parent entry was replaced"
            )


def _recapture_directory_chain_locations(
    *,
    fds: Sequence[int],
    links: Sequence[tuple[int, str, int, tuple[int, ...]]],
    root: Path,
    context: str,
) -> None:
    """Recapture directory names while permitting owned child-entry changes."""

    root_fd = os.fstat(fds[0])
    root_entry = root.lstat()
    if (
        stat.S_ISLNK(root_entry.st_mode)
        or not stat.S_ISDIR(root_entry.st_mode)
        or (root_entry.st_dev, root_entry.st_ino)
        != (root_fd.st_dev, root_fd.st_ino)
    ):
        raise ClosureE10SourceEvidenceError(f"{context} root was replaced")
    for parent_fd, component, child_fd, _ in links:
        child = os.fstat(child_fd)
        entry = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
        if (
            stat.S_ISLNK(entry.st_mode)
            or not stat.S_ISDIR(entry.st_mode)
            or (entry.st_dev, entry.st_ino) != (child.st_dev, child.st_ino)
        ):
            raise ClosureE10SourceEvidenceError(
                f"{context} parent entry was replaced"
            )


def _read_regular_from_directory_fd(
    name: str,
    *,
    directory_fd: int,
    context: str,
    require_nlink_one: bool,
) -> tuple[bytes, tuple[int, ...]]:
    if not name or "/" in name or name in {".", ".."}:
        raise ClosureE10SourceEvidenceError(f"{context} filename is unsafe")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise ClosureE10SourceEvidenceError(f"{context} is absent") from exc
    try:
        metadata = os.fstat(fd)
        identity = _metadata_identity(metadata)
        if not stat.S_ISREG(metadata.st_mode) or (
            require_nlink_one and metadata.st_nlink != 1
        ):
            raise ClosureE10SourceEvidenceError(
                f"{context} is not a single-link regular file"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        if len(payload) != metadata.st_size or _metadata_identity(os.fstat(fd)) != identity:
            raise ClosureE10SourceEvidenceError(f"{context} changed while read")
        entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if _metadata_identity(entry) != identity or stat.S_ISLNK(entry.st_mode):
            raise ClosureE10SourceEvidenceError(f"{context} entry was replaced")
        return payload, identity
    except OSError as exc:
        raise ClosureE10SourceEvidenceError(f"{context} cannot be read") from exc
    finally:
        os.close(fd)


def _read_regular(
    path: Path,
    *,
    repo_root: Path,
    context: str,
    require_nlink_one: bool = True,
) -> bytes:
    if path.is_absolute() or not path.name or ".." in path.parts:
        raise ClosureE10SourceEvidenceError(f"{context} path is unsafe: {path}")
    fds, links, root = _open_directory_chain(
        repo_root, path.parent, context=context
    )
    try:
        payload, _ = _read_regular_from_directory_fd(
            path.name,
            directory_fd=fds[-1],
            context=f"{context}: {path}",
            require_nlink_one=require_nlink_one,
        )
        _recapture_directory_chain(
            fds=fds, links=links, root=root, context=context
        )
        return payload
    except OSError as exc:
        raise ClosureE10SourceEvidenceError(
            f"{context} cannot be read: {path}"
        ) from exc
    finally:
        for fd in reversed(fds):
            os.close(fd)


def _run(
    argv: Sequence[str],
    *,
    repo_root: Path,
    environment: Mapping[str, str] | None = None,
    execution_argv: Sequence[str] | None = None,
    inherit_environment: bool = True,
    require_success: bool = True,
    redact_environment_keys: Sequence[str] = (),
    timeout_seconds: int = 300,
) -> tuple[dict[str, Any], str, str]:
    if type(timeout_seconds) is not int or timeout_seconds <= 0:
        raise ClosureE10SourceEvidenceError("command timeout must be a positive integer")
    command_environment = os.environ.copy() if inherit_environment else {}
    command_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment_overrides = {"PYTHONDONTWRITEBYTECODE": "1"}
    if environment:
        command_environment.update(environment)
        environment_overrides.update(environment)
    redacted = set(redact_environment_keys)
    if not redacted.issubset(environment_overrides):
        raise ClosureE10SourceEvidenceError("redacted command environment key is absent")
    recorded_environment = {
        key: (
            f"redacted_sha256:{_sha256(value.encode('utf-8'))}"
            if key in redacted
            else value
        )
        for key, value in environment_overrides.items()
    }
    try:
        completed = subprocess.run(
            list(execution_argv or argv),
            cwd=repo_root,
            env=command_environment,
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ClosureE10SourceEvidenceError(
            f"verification command exceeded {timeout_seconds}s: {list(argv)}"
        ) from exc
    stdout = completed.stdout
    stderr = completed.stderr
    record = {
        "argv": list(argv),
        "returncode": completed.returncode,
        "stdout_sha256": _sha256(stdout.encode("utf-8")),
        "stderr_sha256": _sha256(stderr.encode("utf-8")),
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": len(stderr.splitlines()),
        "environment_overrides": dict(sorted(recorded_environment.items())),
        "timeout_seconds": timeout_seconds,
    }
    if require_success and completed.returncode != 0:
        raise ClosureE10SourceEvidenceError(
            f"verification command failed: {list(argv)}"
        )
    return record, stdout, stderr


def _isolated_command_environment(repo_root: Path) -> dict[str, str]:
    poetry_home = Path.home() / ".local"
    poetry_binary = poetry_home / "bin/poetry"
    virtual_environment = repo_root / ".venv"
    for path, context in (
        (Path(BWRAP_BACKEND), "bubblewrap backend"),
        (poetry_binary, "Poetry launcher"),
        (virtual_environment / "bin/python", "project virtual environment"),
    ):
        try:
            metadata = path.stat()
        except OSError as exc:
            raise ClosureE10SourceEvidenceError(f"{context} is unavailable") from exc
        if not stat.S_ISREG(metadata.st_mode) or not os.access(path, os.X_OK):
            raise ClosureE10SourceEvidenceError(f"{context} is not executable")
    return dict(ISOLATED_ENVIRONMENT_VALUES)


def _create_restricted_mask_tree(work_directory: Path) -> Path:
    """Create synthetic target metadata, opaque outcome, and file masks."""

    mask_root = work_directory / "restricted_mask_tree"
    mask_root.mkdir(mode=0o700)
    for spec in RESTRICTED_MASK_SPECS:
        relative = Path(spec["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ClosureE10SourceEvidenceError("restricted mask path escaped")
        destination = mask_root / relative
        destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if spec["entry_type"] == "metadata_only_directory":
            destination.mkdir(mode=0o700)
            for leaf in cast(Sequence[str], spec["metadata_placeholders"]):
                fd = os.open(
                    destination / leaf,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_NOFOLLOW", 0),
                    0o000,
                )
                os.close(fd)
            destination.chmod(0o555)
        elif spec["entry_type"] == "opaque_empty_directory":
            destination.mkdir(mode=0o700)
            try:
                os.setxattr(
                    destination,
                    "user.overlay.opaque",
                    b"y",
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise ClosureE10SourceEvidenceError(
                    "cannot create an opaque restricted directory"
                ) from exc
            destination.chmod(0o555)
        elif spec["entry_type"] in {"regular_file", "tracked_empty_file"}:
            mode = 0o444 if spec["entry_type"] == "tracked_empty_file" else 0o000
            fd = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                mode,
            )
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        else:
            raise ClosureE10SourceEvidenceError("restricted mask type drifted")
        metadata = destination.lstat()
        expected_type = (
            stat.S_ISDIR(metadata.st_mode)
            if spec["entry_type"]
            in {"metadata_only_directory", "opaque_empty_directory"}
            else stat.S_ISREG(metadata.st_mode)
        )
        if not expected_type or format(stat.S_IMODE(metadata.st_mode), "03o") != spec["mode"]:
            raise ClosureE10SourceEvidenceError(
                f"restricted mask entry drifted: {spec['path']}"
            )
    _validate_restricted_mask_tree(mask_root)
    return mask_root


def _validate_restricted_mask_tree(mask_root: Path) -> None:
    expected_children: dict[Path, set[str]] = {}
    expected_leaves: dict[Path, RestrictedMaskSpec] = {}
    for spec in RESTRICTED_MASK_SPECS:
        relative = Path(spec["path"])
        expected_leaves[relative] = spec
        parent = Path()
        for component in relative.parts:
            expected_children.setdefault(parent, set()).add(component)
            parent /= component
    root_metadata = mask_root.lstat()
    if (
        not stat.S_ISDIR(root_metadata.st_mode)
        or mask_root.is_symlink()
        or stat.S_IMODE(root_metadata.st_mode) != 0o700
    ):
        raise ClosureE10SourceEvidenceError("restricted mask root drifted")
    for relative, names in expected_children.items():
        directory = mask_root / relative
        if relative in expected_leaves:
            continue
        metadata = directory.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise ClosureE10SourceEvidenceError("restricted mask parent drifted")
        observed = {entry.name for entry in os.scandir(directory)}
        if observed != names:
            raise ClosureE10SourceEvidenceError("restricted mask tree scope drifted")
    for relative, spec in expected_leaves.items():
        metadata = (mask_root / relative).lstat()
        type_matches = (
            stat.S_ISDIR(metadata.st_mode)
            if spec["entry_type"]
            in {"metadata_only_directory", "opaque_empty_directory"}
            else stat.S_ISREG(metadata.st_mode)
        )
        if (
            not type_matches
            or format(stat.S_IMODE(metadata.st_mode), "03o") != spec["mode"]
        ):
            raise ClosureE10SourceEvidenceError("restricted mask leaf drifted")
        if spec["entry_type"] in {"regular_file", "tracked_empty_file"} and (
            metadata.st_size != 0 or metadata.st_nlink != 1
        ):
            raise ClosureE10SourceEvidenceError(
                "restricted file mask identity drifted"
            )
        if spec["entry_type"] in {
            "metadata_only_directory",
            "opaque_empty_directory",
        }:
            expected_entries = set(spec["metadata_placeholders"])
            observed_entries = {
                entry.name for entry in os.scandir(mask_root / relative)
            }
            if observed_entries != expected_entries:
                raise ClosureE10SourceEvidenceError(
                    "restricted directory mask scope drifted"
                )
        if spec["entry_type"] == "metadata_only_directory":
            for leaf in cast(Sequence[str], spec["metadata_placeholders"]):
                leaf_metadata = (mask_root / relative / leaf).lstat()
                if (
                    not stat.S_ISREG(leaf_metadata.st_mode)
                    or stat.S_IMODE(leaf_metadata.st_mode) != 0
                ):
                    raise ClosureE10SourceEvidenceError(
                        "target metadata placeholder drifted"
                    )
        elif spec["entry_type"] == "opaque_empty_directory":
            try:
                opaque = os.getxattr(
                    mask_root / relative,
                    "user.overlay.opaque",
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise ClosureE10SourceEvidenceError(
                    "restricted directory opacity marker is absent"
                ) from exc
            if opaque != b"y":
                raise ClosureE10SourceEvidenceError(
                    "restricted directory opacity marker drifted"
                )


def _restricted_mount_template() -> list[str]:
    return [
        "--overlay-src",
        "<SNAPSHOT_DIRECTORY>/data/closure_v1",
        "--overlay-src",
        "<MASK_DIRECTORY>/data/closure_v1",
        "--ro-overlay",
        "/workspace/data/closure_v1",
        "--ro-bind",
        "<MASK_DIRECTORY>/data/targets",
        "/workspace/data/targets",
        "--ro-bind",
        "<MASK_DIRECTORY>/reports/closure_v1/00_protocol/outcome_access_log.jsonl",
        "/workspace/reports/closure_v1/00_protocol/outcome_access_log.jsonl",
        "--ro-bind",
        "<MASK_DIRECTORY>/private/FULL.md",
        "/workspace/private/FULL.md",
    ]


def _bubblewrap_template(
    restricted_paths: Sequence[Mapping[str, Any]],
) -> list[str]:
    template = [
        BWRAP_BACKEND,
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--share-net",
        "--unshare-user",
        "--disable-userns",
        "--cap-drop",
        "ALL",
    ]
    for system_path in ("/usr", "/bin", "/lib", "/lib64", "/etc", "/sys", "/run"):
        template.extend(["--ro-bind", system_path, system_path])
    template.extend(
        [
            "--ro-bind",
            "<HOME>/.local/bin",
            "/opt/closure-user-local/bin",
            "--ro-bind",
            "<HOME>/.local/share/pipx/venvs/poetry",
            "<HOME>/.local/share/pipx/venvs/poetry",
            "--ro-bind",
            "<SNAPSHOT_DIRECTORY>",
            "/workspace",
        ]
    )
    template.extend(_restricted_mount_template())
    template.extend(
        [
            "--ro-bind",
            "<REPOSITORY_ROOT>/.git",
            "/workspace/.git",
            "--ro-bind",
            "<REPOSITORY_ROOT>/.venv",
            "/workspace/.venv",
            "--ro-bind",
            "<REPOSITORY_ROOT>/.venv",
            "<REPOSITORY_ROOT>/.venv",
        ]
    )
    if [dict(record) for record in restricted_paths] != [
        dict(spec) for spec in RESTRICTED_MASK_SPECS
    ]:
        raise ClosureE10SourceEvidenceError(
            "restricted mount records are not ordered and exact"
        )
    template.extend(
        [
            "--bind",
            "<WORK_DIRECTORY>/sandbox_tmp",
            "/workspace/tmp",
            "--tmpfs",
            "/tmp",
            "--dev-bind",
            "/dev",
            "/dev",
            "--proc",
            "/proc",
            "--chdir",
            "/workspace",
            "--",
        ]
    )
    return template


def _bubblewrap_prefix(
    *,
    repo_root: Path,
    work_directory_relative: Path,
    sandbox_tmp_relative: Path,
    mask_tree: Path,
    restricted_paths: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[str]]:
    """Return the real and portable-template bwrap prefixes."""

    if (
        sandbox_tmp_relative != work_directory_relative / "sandbox_tmp"
    ):
        raise ClosureE10SourceEvidenceError(
            "bubblewrap work-directory topology drifted"
        )
    user_local_bin = Path.home() / ".local/bin"
    poetry_environment = Path.home() / ".local/share/pipx/venvs/poetry"
    original_venv = repo_root / ".venv"
    snapshot = repo_root / work_directory_relative / "exact_h_snapshot"
    for path, context in (
        (user_local_bin, "user-local executable tree"),
        (poetry_environment, "Poetry environment"),
        (original_venv, "project virtual environment"),
        (repo_root / ".git", "read-only Git metadata tree"),
        (snapshot, "materialized exact-H snapshot"),
        (snapshot / "data/closure_v1", "snapshot Closure input tree"),
    ):
        if not path.is_dir() or path.is_symlink():
            raise ClosureE10SourceEvidenceError(f"{context} is not a real directory")
    for relative, expected_directory, context in (
        (Path("data/targets"), True, "target mount destination"),
        (OUTCOME_ACCESS_LOG_PATH, False, "outcome-log mount destination"),
        (Path("private/FULL.md"), False, "private-context mount destination"),
    ):
        try:
            metadata = (snapshot / relative).lstat()
        except OSError as exc:
            raise ClosureE10SourceEvidenceError(f"{context} is absent") from exc
        type_matches = (
            stat.S_ISDIR(metadata.st_mode)
            if expected_directory
            else stat.S_ISREG(metadata.st_mode)
        )
        if not type_matches or stat.S_ISLNK(metadata.st_mode):
            raise ClosureE10SourceEvidenceError(f"{context} is unsafe")
    _validate_restricted_mask_tree(mask_tree)
    template = _bubblewrap_template(restricted_paths)
    prefix = [
        item.replace("<REPOSITORY_ROOT>", os.fspath(repo_root))
        .replace("<WORK_DIRECTORY>", work_directory_relative.as_posix())
        .replace("<SNAPSHOT_DIRECTORY>", os.fspath(snapshot))
        .replace("<MASK_DIRECTORY>", os.fspath(mask_tree))
        .replace("<HOME>", os.fspath(Path.home()))
        for item in template
    ]
    return prefix, template


def _prepare_read_only_h_worktree(
    *,
    repo_root: Path,
    work_directory: Path,
    mask_tree: Path,
    repository_commit: str,
    repository_state: Mapping[str, Any],
    recovery_attempt: str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    """Prepare private writable tmp state for a read-only exact-H mount."""

    commit = _require_commit(repository_commit)
    mode = _require_recovery_attempt(recovery_attempt)
    if (
        repository_state.get("repository_commit") != commit
        or repository_state.get("clean_worktree") is not True
    ):
        raise ClosureE10SourceEvidenceError(
            "read-only H worktree precondition drifted"
        )
    try:
        work_relative = work_directory.relative_to(repo_root)
    except ValueError as exc:
        raise ClosureE10SourceEvidenceError(
            "H isolation work directory escaped the repository"
        ) from exc
    sandbox_tmp = work_directory / "sandbox_tmp"
    command_outputs = sandbox_tmp / SANDBOX_OUTPUT_PATH.name
    if os.path.lexists(sandbox_tmp):
        raise ClosureE10SourceEvidenceError("private sandbox tmp is not pristine")
    sandbox_tmp.mkdir()
    command_outputs.mkdir()
    snapshot_root, snapshot_record = _materialize_exact_h_snapshot(
        repo_root=repo_root,
        work_directory=work_directory,
        repository_commit=commit,
    )
    if snapshot_root != work_directory / "exact_h_snapshot":
        raise ClosureE10SourceEvidenceError("exact-H snapshot location drifted")
    _validate_restricted_mask_tree(mask_tree)
    restricted_masks = [dict(spec) for spec in RESTRICTED_MASK_SPECS]
    host_log_state = (
        _capture_host_outcome_log_state(repo_root, commit)
        if mode is None
        else _capture_host_outcome_log_state(
            repo_root,
            commit,
            recovery_attempt=mode,
        )
    )
    isolation = {
        "schema_version": "closure_e10_bubblewrap_exact_h_snapshot_masked_view_v1",
        "backend": BWRAP_BACKEND,
        "repository_commit": commit,
        "worktree_path": "<WORK_DIRECTORY>/exact_h_snapshot",
        "worktree_pre_verification": copy.deepcopy(dict(repository_state)),
        "worktree_post_verification": copy.deepcopy(dict(repository_state)),
        "restricted_mask_tree_path": "<MASK_DIRECTORY>",
        "restricted_path_masks": restricted_masks,
        "host_outcome_log_pre_verification": host_log_state,
        "host_outcome_log_post_verification": copy.deepcopy(host_log_state),
        "tracked_empty_log_mask": {
            "path": OUTCOME_ACCESS_LOG_PATH.as_posix(),
            "entry_type": "tracked_empty_file",
            "mode": "444",
            "bytes": 0,
            "single_link_regular_file": True,
            "probe_read_result": "synthetic_empty_eof",
            "host_path_opened": False,
        },
        "exact_h_snapshot": snapshot_record,
        "repository_mount": (
            "read_only_materialized_exact_h_snapshot_with_direct_and_opaque_"
            "restricted_masks"
        ),
        "command_output_mount": "read_write_private_work_directory_tmp",
        "system_temporary_directory": "private_tmpfs",
        "ambient_environment_inherited": False,
        "network_namespace": "shared_host_network_for_loopback_postgresql_fixture",
        "user_pid_ipc_uts_cgroup_namespaces": "unshared",
        "linux_capabilities": "all_dropped",
        "child_user_namespaces": "disabled",
        "isolated_command_names": list(BWRAP_ISOLATED_COMMAND_NAMES),
        "execution_argv_template_prefix": [],
        "permitted_input_mounts": [
            {
                "path": ".",
                "source": "materialized_tracked_h_plus_authenticated_dvc_snapshot",
                "read_only": True,
            },
            {
                "path": ".git",
                "source": "host_git_metadata_read_only_refs_verified_pre_and_post",
                "read_only": True,
            },
            {
                "path": ".venv",
                "source": "host_runtime_environment_lock_and_versions_recorded",
                "read_only": True,
            },
        ],
        "denial_probe_results": [],
        "static_access_inventory": STATIC_ACCESS_INVENTORY,
    }
    return sandbox_tmp, command_outputs, isolation


def _git(repo_root: Path, *args: str) -> str:
    record, stdout, stderr = _run(
        ("git", *args),
        repo_root=repo_root,
        environment={"GIT_OPTIONAL_LOCKS": "0"},
    )
    del record
    if stderr:
        raise ClosureE10SourceEvidenceError(
            f"Git command emitted stderr: git {' '.join(args)}"
        )
    return stdout.strip()


def _collect_exact_h_repository_state(
    repo_root: Path, expected_h_commit: str
) -> dict[str, Any]:
    expected = _require_commit(expected_h_commit, context="expected H commit")
    refs = {
        "head": _git(repo_root, "rev-parse", "HEAD"),
        "main": _git(repo_root, "rev-parse", "refs/heads/main"),
        "origin_main": _git(repo_root, "rev-parse", "refs/remotes/origin/main"),
        "origin_head": _git(
            repo_root, "rev-parse", "refs/remotes/origin/HEAD^{commit}"
        ),
    }
    if set(refs.values()) != {expected}:
        raise ClosureE10SourceEvidenceError(
            f"E10 source evidence requires exact aligned H refs: {refs}"
        )
    if _git(repo_root, "branch", "--show-current") != "main":
        raise ClosureE10SourceEvidenceError("E10 source evidence requires branch main")
    status_text = _git(repo_root, *OUTCOME_FREE_GIT_STATUS_ARGUMENTS)
    if status_text:
        raise ClosureE10SourceEvidenceError(
            "E10 source evidence requires a clean H worktree"
        )
    module_path = BUILDER_SOURCE_PATH
    physical = _read_regular(module_path, repo_root=repo_root, context="E10 builder")
    blob_record, blob_stdout, _ = _run(
        ("git", "show", f"{expected}:{module_path.as_posix()}"),
        repo_root=repo_root,
    )
    del blob_record
    blob = blob_stdout.encode("utf-8")
    if blob != physical:
        raise ClosureE10SourceEvidenceError(
            "physical E10 builder does not equal its exact H Git blob"
        )
    return {
        "branch": "main",
        "repository_commit": expected,
        "refs": refs,
        "clean_worktree": True,
        "builder_source": {
            "path": module_path.as_posix(),
            "bytes": len(physical),
            "sha256": _sha256(physical),
            "physical_equals_h_blob": True,
        },
    }


def _capture_host_outcome_log_state(
    repo_root: Path,
    repository_commit: str,
    *,
    recovery_attempt: str | None = None,
) -> dict[str, Any]:
    """Bind host-log metadata to its exact Git blob without opening the host leaf."""

    commit = _require_commit(repository_commit)
    mode = _require_recovery_attempt(recovery_attempt)
    expected_bytes = RECOVERY_OUTCOME_LOG_BYTES if mode else 0
    expected_sha256 = RECOVERY_OUTCOME_LOG_SHA256 if mode else _sha256(b"")
    _require_real_directory_chain(repo_root, repo_root / OUTCOME_ACCESS_LOG_PATH.parent)
    path = repo_root / OUTCOME_ACCESS_LOG_PATH
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ClosureE10SourceEvidenceError(
            "host outcome log is absent"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_size != expected_bytes
        or (
            mode == RECOVERY_ATTEMPT_1
            and stat.S_IMODE(metadata.st_mode) != 0o644
        )
    ):
        raise ClosureE10SourceEvidenceError(
            "host outcome log metadata does not match the sealed E10 state"
        )
    command, stdout, stderr = _run(
        ("git", "show", f"{commit}:{OUTCOME_ACCESS_LOG_PATH.as_posix()}"),
        repo_root=repo_root,
        environment={"GIT_OPTIONAL_LOCKS": "0"},
    )
    blob = stdout.encode("utf-8")
    if (
        stderr
        or len(blob) != expected_bytes
        or _sha256(blob) != expected_sha256
    ):
        raise ClosureE10SourceEvidenceError(
            "exact H outcome-log blob does not match the sealed E10 state"
        )
    blob_sha1 = _git_blob_sha1(blob)
    index_command, index_stdout, index_stderr = _run(
        (
            "git",
            "ls-files",
            "--stage",
            "--",
            OUTCOME_ACCESS_LOG_PATH.as_posix(),
        ),
        repo_root=repo_root,
        environment={"GIT_OPTIONAL_LOCKS": "0"},
    )
    expected_index = (
        f"100644 {blob_sha1} 0\t"
        f"{OUTCOME_ACCESS_LOG_PATH.as_posix()}\n"
    )
    if index_stderr or index_stdout != expected_index:
        raise ClosureE10SourceEvidenceError(
            "outcome-log index entry differs from the exact H blob"
        )
    return {
        "path": OUTCOME_ACCESS_LOG_PATH.as_posix(),
        "repository_commit": commit,
        "entry_type": "regular_file",
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": format(stat.S_IMODE(metadata.st_mode), "03o"),
        "nlink": metadata.st_nlink,
        "bytes": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns,
        "ctime_ns": metadata.st_ctime_ns,
        "h_blob_bytes": len(blob),
        "h_blob_sha256": _sha256(blob),
        "h_blob_command": command,
        "index_mode": "100644",
        "index_blob_sha1": blob_sha1,
        "index_stage": 0,
        "index_entry_command": index_command,
        "physical_contents_opened": False,
    }


def _git_bound_recovery_input_record(
    repo_root: Path,
    repository_commit: str,
    path: Path,
    *,
    role: str,
) -> dict[str, Any]:
    physical = _read_regular(path, repo_root=repo_root, context=role)
    command, stdout, stderr = _run(
        ("git", "show", f"{repository_commit}:{path.as_posix()}"),
        repo_root=repo_root,
        environment={"GIT_OPTIONAL_LOCKS": "0"},
    )
    blob = stdout.encode("utf-8")
    if stderr or blob != physical:
        raise ClosureE10SourceEvidenceError(
            f"recovery input differs from exact H2 Git blob: {path}"
        )
    return {
        "path": path.as_posix(),
        "role": role,
        "bytes": len(blob),
        "sha256": _sha256(blob),
        "repository_commit": repository_commit,
        "physical_equals_h2_git_blob": True,
        "git_blob_command": command,
    }


def _collect_recovery_attempt_1_record(
    repo_root: Path, repository_commit: str
) -> dict[str, Any]:
    commit = _require_commit(repository_commit, context="recovery H2 commit")
    inherited: list[dict[str, Any]] = []
    for path in RECOVERY_INHERITED_P1_PATHS:
        if path in SOURCE_EVIDENCE_PATHS.values() or path == SOURCE_MANIFEST_PATH:
            role = "inherited_p1_source_evidence_bundle"
        elif path in PHASE3_OVERLAY_POINTER_PATHS:
            role = "inherited_p1_phase3_dvc_pointer"
        else:
            role = "inherited_p1_phase3_overlay_manifest"
        inherited.append(
            _git_bound_recovery_input_record(
                repo_root,
                commit,
                path,
                role=role,
            )
        )
    if [record["path"] for record in inherited] != [
        path.as_posix() for path in RECOVERY_INHERITED_P1_PATHS
    ]:
        raise ClosureE10SourceEvidenceError(
            "recovery inherited P1 input order drifted"
        )
    receipt = _git_bound_recovery_input_record(
        repo_root,
        commit,
        ATTEMPT_1_FAILURE_RECEIPT_PATH,
        role="closure_e0_u_attempt_1_failure_receipt",
    )
    receipt_payload = _read_regular(
        ATTEMPT_1_FAILURE_RECEIPT_PATH,
        repo_root=repo_root,
        context="attempt-1 failure receipt",
    )
    try:
        decoded_receipt = json.loads(receipt_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClosureE10SourceEvidenceError(
            "attempt-1 failure receipt is not canonical JSON"
        ) from exc
    expected_receipt_keys = {
        "schema_version",
        "experiment_id",
        "gate",
        "attempt_ordinal",
        "execution_id",
        "historical_chain",
        "activation",
        "access_log_prefix",
        "guard_observation",
        "failure",
        "publication",
    }
    if (
        not isinstance(decoded_receipt, Mapping)
        or set(decoded_receipt) != expected_receipt_keys
        or decoded_receipt.get("schema_version")
        != "closure_e0_u_attempt_1_failure_v1"
        or decoded_receipt.get("experiment_id") != "closure_v1"
        or decoded_receipt.get("gate") != "E0-U"
        or decoded_receipt.get("attempt_ordinal") != 1
        or not isinstance(decoded_receipt.get("execution_id"), str)
        or re.fullmatch(
            r"closure-v1-e0-u-[0-9a-f]{16}-[0-9a-f]{16}",
            cast(str, decoded_receipt["execution_id"]),
        )
        is None
        or _canonical_json(dict(decoded_receipt)) != receipt_payload
        or len(receipt_payload) != ATTEMPT_1_FAILURE_RECEIPT_BYTES
        or _sha256(receipt_payload) != ATTEMPT_1_FAILURE_RECEIPT_SHA256
    ):
        raise ClosureE10SourceEvidenceError(
            "attempt-1 failure receipt identity drifted"
        )
    access_log_prefix = decoded_receipt.get("access_log_prefix")
    if not isinstance(access_log_prefix, Mapping):
        raise ClosureE10SourceEvidenceError(
            "attempt-1 failure receipt log prefix is absent"
        )
    if access_log_prefix != {
        "bytes": RECOVERY_OUTCOME_LOG_BYTES,
        "path": OUTCOME_ACCESS_LOG_PATH.as_posix(),
        "record_count": 1,
        "sha256": RECOVERY_OUTCOME_LOG_SHA256,
    }:
        raise ClosureE10SourceEvidenceError(
            "attempt-1 failure receipt does not bind the exact durable log prefix"
        )
    failure = decoded_receipt.get("failure")
    publication = decoded_receipt.get("publication")
    history = decoded_receipt.get("historical_chain")
    activation = decoded_receipt.get("activation")
    guard = decoded_receipt.get("guard_observation")
    if (
        failure
        != {
            "context_materialized": True,
            "diagnosed_source_phase": (
                "after_full_context_validation_before_e1_normalization"
            ),
            "e1_metrics_computed": False,
            "e1_normalization_started": False,
            "error": "E0-U opened logical table scope drifted",
            "outcomes_opened": True,
            "process_exit_code": 2,
            "result_constructed": False,
        }
        or publication
        != {"expected_output_count": 52, "published_output_count": 0}
        or history != RECOVERY_HISTORICAL_CHAIN
        or activation
        != {
            "bytes": 34368,
            "git_blob_oid": "32d90942b8a683aebacf44ca5fe6c2b12d1a3c7c",
            "path": (
                "reports/closure_v1/00_protocol/closure_e0_u_activation.json"
            ),
            "sha256": (
                "8f04bd4429717be662b6166c913fb1d15adaa69b1c0ba147d75162eb0a39bc94"
            ),
        }
        or not isinstance(guard, Mapping)
        or set(guard)
        != {
            "device",
            "file_type",
            "inode",
            "mode",
            "nlink",
            "ownership_identity_recoverable",
            "path",
            "sha256",
            "size",
        }
        or type(guard.get("device")) is not int
        or cast(int, guard["device"]) <= 0
        or type(guard.get("inode")) is not int
        or cast(int, guard["inode"]) <= 0
        or guard.get("file_type") != "regular_file"
        or guard.get("mode") != 0o600
        or guard.get("nlink") != 1
        or guard.get("ownership_identity_recoverable") is not False
        or guard.get("path") != "tmp/closure_v1_e0_u/sealed_batch.guard"
        or guard.get("sha256") != _sha256(b"")
        or guard.get("size") != 0
    ):
        raise ClosureE10SourceEvidenceError(
            "attempt-1 failure receipt scientific history drifted"
        )
    host_log_state = _capture_host_outcome_log_state(
        repo_root,
        commit,
        recovery_attempt=RECOVERY_ATTEMPT_1,
    )
    log_input = {
        "path": OUTCOME_ACCESS_LOG_PATH.as_posix(),
        "role": "sealed_attempt_1_outcome_log_prefix_from_h2_git_blob",
        "bytes": RECOVERY_OUTCOME_LOG_BYTES,
        "sha256": RECOVERY_OUTCOME_LOG_SHA256,
        "repository_commit": commit,
        "physical_metadata_matches_h2_git_blob_size": True,
        "physical_contents_opened": False,
        "git_blob_command": copy.deepcopy(host_log_state["h_blob_command"]),
    }
    sealed_inputs = [*copy.deepcopy(inherited), copy.deepcopy(receipt), log_input]
    return {
        "mode": RECOVERY_ATTEMPT_1,
        "repository_commit": commit,
        "outcome_access_log_state": (
            "present_exact_consumed_attempt_1_unopened_by_e10"
        ),
        "outcome_access_log_prefix": {
            "path": OUTCOME_ACCESS_LOG_PATH.as_posix(),
            "bytes": RECOVERY_OUTCOME_LOG_BYTES,
            "sha256": RECOVERY_OUTCOME_LOG_SHA256,
            "source": "exact_h2_git_blob_and_host_lstat_without_host_content_open",
            "physical_contents_opened": False,
        },
        "host_outcome_log_state": host_log_state,
        "attempt_1_failure_receipt": receipt,
        "attempt_1_failure_receipt_payload_sha256": _sha256(receipt_payload),
        "inherited_p1_input_count": len(inherited),
        "inherited_p1_inputs": inherited,
        "inherited_p1_inputs_sha256": _records_digest(inherited),
        "sealed_inputs": sealed_inputs,
        "sealed_inputs_sha256": _records_digest(sealed_inputs),
        "p1_inputs_overwritten": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
    }


def _require_host_outcome_directories_absent(repo_root: Path) -> None:
    paths = (
        Path("data/closure_v1/unblinded"),
        Path("data/closure_v1/evaluation_outcomes"),
    )
    existing = [path.as_posix() for path in paths if os.path.lexists(repo_root / path)]
    if existing:
        raise ClosureE10SourceEvidenceError(
            f"pre-E0-U host outcome directories are not absent: {existing}"
        )


def _require_pre_generation_namespace(
    repo_root: Path, *, recovery_attempt: str | None = None
) -> None:
    mode = _require_recovery_attempt(recovery_attempt)
    source_directory, _, _ = _source_bundle_layout(mode)
    parent = repo_root / source_directory.parent
    _require_real_directory_chain(repo_root, parent)
    candidates = (
        repo_root / source_directory,
        repo_root / FINAL_E10_DIRECTORY,
        repo_root / GUARD_PATH,
    )
    existing = [str(path.relative_to(repo_root)) for path in candidates if os.path.lexists(path)]
    if existing:
        raise ClosureE10SourceEvidenceError(
            f"E10 source/final namespace is not pristine: {existing}"
        )
    if mode == RECOVERY_ATTEMPT_1:
        original_directory = repo_root / SOURCE_EVIDENCE_DIRECTORY
        _require_real_directory_chain(repo_root, original_directory)
        try:
            original_entries = sorted(
                path.name for path in original_directory.iterdir()
            )
        except OSError as exc:
            raise ClosureE10SourceEvidenceError(
                "recovery requires the inherited P1 source bundle"
            ) from exc
        expected_original_entries = sorted(
            [
                *(path.name for path in SOURCE_EVIDENCE_PATHS.values()),
                SOURCE_MANIFEST_PATH.name,
            ]
        )
        if original_entries != expected_original_entries:
            raise ClosureE10SourceEvidenceError(
                "recovery inherited P1 source bundle is not exact seven"
            )
    log_path = repo_root / OUTCOME_ACCESS_LOG_PATH
    metadata = log_path.lstat()
    expected_log_bytes = RECOVERY_OUTCOME_LOG_BYTES if mode else 0
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_size != expected_log_bytes
        or (
            mode == RECOVERY_ATTEMPT_1
            and stat.S_IMODE(metadata.st_mode) != 0o644
        )
    ):
        raise ClosureE10SourceEvidenceError(
            "E10 source evidence outcome-log metadata does not match its mode"
        )
    _require_host_outcome_directories_absent(repo_root)


def _require_postgresql_test_database() -> str:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value or not value.startswith("postgresql+asyncpg://"):
        raise ClosureE10SourceEvidenceError(
            "generation requires an explicit PostgreSQL TEST_DATABASE_URL using "
            "postgresql+asyncpg"
        )
    parsed = urlsplit(value)
    database_name = parsed.path.lstrip("/")
    if (
        parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.query
        or parsed.fragment
        or "/" in database_name
        or not re.fullmatch(r"closure_e10(?:_[a-z0-9_]+)?", database_name)
    ):
        raise ClosureE10SourceEvidenceError(
            "TEST_DATABASE_URL must be a loopback-only dedicated closure_e10 "
            "database"
        )
    return value


def _owned_postgresql_url(
    base_url: str, *, repository_commit: str, run_name: str
) -> tuple[str, str, str]:
    parsed = urlsplit(base_url)
    token = _sha256(f"{repository_commit}:{run_name}".encode("utf-8"))[:20]
    database_name = f"closure_e10_{token}"
    owned_url = urlunsplit(
        (parsed.scheme, parsed.netloc, f"/{database_name}", "", "")
    )
    admin_url = urlunsplit(
        ("postgresql", parsed.netloc, "/postgres", "", "")
    )
    return owned_url, admin_url, database_name


def _create_owned_postgresql_database(
    base_url: str, *, repository_commit: str, run_name: str
) -> tuple[str, dict[str, Any]]:
    owned_url, admin_url, database_name = _owned_postgresql_url(
        base_url,
        repository_commit=repository_commit,
        run_name=run_name,
    )
    create_statement = f'CREATE DATABASE "{database_name}"'

    async def create() -> None:
        import asyncpg

        connection: Any | None = None
        create_attempted = False
        duplicate_database_collision = False
        primary_error: BaseException | None = None
        try:
            connection = await asyncpg.connect(admin_url)
            exists = await connection.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                database_name,
            )
            if exists:
                raise ClosureE10SourceEvidenceError(
                    "owned E10 PostgreSQL database unexpectedly exists"
                )
            create_attempted = True
            try:
                await connection.execute(create_statement)
            except BaseException as exc:
                duplicate_error = getattr(
                    asyncpg, "DuplicateDatabaseError", ()
                )
                if isinstance(exc, duplicate_error):
                    # Another actor won the CREATE race.  That database is not
                    # ours, so the compensating path must never drop it.
                    duplicate_database_collision = True
                raise
            created = await connection.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                database_name,
            )
            if created != 1:
                raise ClosureE10SourceEvidenceError(
                    "owned E10 PostgreSQL database creation was not durable"
                )
        except BaseException as exc:
            primary_error = exc
        if connection is not None:
            try:
                await connection.close()
            except BaseException as exc:
                primary_error = primary_error or exc
        if primary_error is None:
            return
        if create_attempted and not duplicate_database_collision:
            cleanup_connection: Any | None = None
            if connection is not None:
                connection = None
            try:
                cleanup_connection = await asyncpg.connect(admin_url)
                await cleanup_connection.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = $1 AND pid <> pg_backend_pid()",
                    database_name,
                )
                if await cleanup_connection.fetchval(
                    "SELECT 1 FROM pg_database WHERE datname = $1",
                    database_name,
                ):
                    await cleanup_connection.execute(
                        f'DROP DATABASE "{database_name}"'
                    )
                if await cleanup_connection.fetchval(
                    "SELECT 1 FROM pg_database WHERE datname = $1",
                    database_name,
                ):
                    raise ClosureE10SourceEvidenceError(
                        "compensating PostgreSQL cleanup was not durable"
                    )
            except BaseException as cleanup_error:
                raise ClosureE10SourceEvidenceError(
                    "owned E10 PostgreSQL database creation rollback failed"
                ) from cleanup_error
            finally:
                if cleanup_connection is not None:
                    await cleanup_connection.close()
        raise primary_error

    try:
        asyncio.run(create())
    except ClosureE10SourceEvidenceError:
        raise
    except BaseException as exc:
        raise ClosureE10SourceEvidenceError(
            "owned E10 PostgreSQL database creation failed"
        ) from exc
    return owned_url, {
        "schema_version": "closure_e10_owned_postgresql_fixture_v1",
        "host_scope": "loopback_only",
        "database_name": database_name,
        "database_name_sha256": _sha256(database_name.encode("ascii")),
        "initially_absent": True,
        "created_exclusively_by_generator": True,
        "create_statement": create_statement,
        "drop_statement": f'DROP DATABASE "{database_name}"',
        "dropped_after_public_suite": False,
        "absent_after_cleanup": False,
    }


def _drop_owned_postgresql_database(
    base_url: str, ownership: Mapping[str, Any]
) -> dict[str, Any]:
    database_name = ownership.get("database_name")
    if not isinstance(database_name, str) or not re.fullmatch(
        r"closure_e10_[0-9a-f]{20}", database_name
    ):
        raise ClosureE10SourceEvidenceError("owned PostgreSQL identity drifted")
    _, admin_url, _ = _owned_postgresql_url(
        base_url,
        repository_commit="0" * 40,
        run_name="cleanup",
    )
    drop_statement = f'DROP DATABASE "{database_name}"'
    if ownership.get("drop_statement") != drop_statement:
        raise ClosureE10SourceEvidenceError("owned PostgreSQL drop statement drifted")

    async def drop() -> None:
        import asyncpg

        connection = await asyncpg.connect(admin_url)
        try:
            await connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                database_name,
            )
            exists = await connection.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                database_name,
            )
            if exists != 1:
                raise ClosureE10SourceEvidenceError(
                    "owned E10 PostgreSQL database vanished before cleanup"
                )
            await connection.execute(drop_statement)
            if await connection.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                database_name,
            ):
                raise ClosureE10SourceEvidenceError(
                    "owned E10 PostgreSQL database survived cleanup"
                )
        finally:
            await connection.close()

    try:
        asyncio.run(drop())
    except ClosureE10SourceEvidenceError:
        raise
    except BaseException as exc:
        raise ClosureE10SourceEvidenceError(
            "owned E10 PostgreSQL database cleanup failed"
        ) from exc
    return {
        **dict(ownership),
        "dropped_after_public_suite": True,
        "absent_after_cleanup": True,
    }


def check_closure_e10_source_evidence(
    *,
    repo_root: Path = PROJECT_ROOT,
    expected_h_commit: str,
    recovery_attempt: str | None = None,
) -> dict[str, Any]:
    """Read-only preflight.  It creates no guard, temp, report, or output."""

    root = repo_root.resolve(strict=True)
    mode = _require_recovery_attempt(recovery_attempt)
    _, _, manifest_path = _source_bundle_layout(mode)
    _require_postgresql_test_database()
    _require_pre_generation_namespace(root, recovery_attempt=mode)
    repository = _collect_exact_h_repository_state(root, expected_h_commit)
    recovery = (
        _collect_recovery_attempt_1_record(root, expected_h_commit)
        if mode == RECOVERY_ATTEMPT_1
        else None
    )
    result = {
        "status": "ready_to_generate",
        "gate": GATE,
        "repository": repository,
        "source_artifact_count": 6,
        "manifest_path": manifest_path.as_posix(),
        "outcome_access_log_state": (
            "present_exact_consumed_attempt_1_unopened_by_e10"
            if mode == RECOVERY_ATTEMPT_1
            else "present_empty_unopened"
        ),
        "public_test_database_configured": True,
        "public_test_database_dialect": "postgresql_asyncpg",
        "verification_commands_run": False,
        "dvc_commands_run": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
        "private_full_opened": False,
        "writes_performed": False,
    }
    if recovery is not None:
        result["recovery_attempt"] = RECOVERY_ATTEMPT_1
        result["recovery"] = recovery
    return result


def _parse_junit(payload: bytes) -> tuple[dict[str, int], list[dict[str, str]]]:
    # Keep this cap identical to the sealed E10 consumer.
    if len(payload) > 10 * 1024 * 1024 or any(
        marker in payload.upper() for marker in (b"<!DOCTYPE", b"<!ENTITY")
    ):
        raise ClosureE10SourceEvidenceError("JUnit is oversized or declares entities")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ClosureE10SourceEvidenceError("JUnit XML is invalid") from exc
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if root.tag not in {"testsuite", "testsuites"} or not suites:
        raise ClosureE10SourceEvidenceError("public test evidence is not JUnit")
    totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    observed = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    skipped: list[dict[str, str]] = []
    for suite in suites:
        for key in totals:
            raw = suite.attrib.get(key, "0")
            try:
                value = int(raw)
            except ValueError as exc:
                raise ClosureE10SourceEvidenceError("JUnit counter is not an integer") from exc
            if value < 0:
                raise ClosureE10SourceEvidenceError("JUnit counter is negative")
            totals[key] += value
        for case in suite.iter("testcase"):
            observed["tests"] += 1
            if case.find("failure") is not None:
                observed["failures"] += 1
            if case.find("error") is not None:
                observed["errors"] += 1
            skipped_node = case.find("skipped")
            if skipped_node is None:
                continue
            observed["skipped"] += 1
            reason = (skipped_node.attrib.get("message") or skipped_node.text or "").strip()
            skipped.append(
                {
                    "classname": case.attrib.get("classname", ""),
                    "name": case.attrib.get("name", ""),
                    "reason": reason,
                }
            )
    if totals != observed or totals["skipped"] != len(skipped):
        raise ClosureE10SourceEvidenceError(
            "JUnit counters do not equal the concrete testcase ledger"
        )
    return totals, skipped


def _inject_junit_commit(payload: bytes, repository_commit: str) -> bytes:
    commit = _require_commit(repository_commit)
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ClosureE10SourceEvidenceError("JUnit XML is invalid") from exc
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    for suite in suites:
        properties = suite.find("properties")
        if properties is None:
            properties = ET.Element("properties")
            suite.insert(0, properties)
        for existing in properties.findall("property"):
            if existing.attrib.get("name") == "closure.repository_commit":
                raise ClosureE10SourceEvidenceError(
                    "raw JUnit already contains Closure commit metadata"
                )
        ET.SubElement(
            properties,
            "property",
            {"name": "closure.repository_commit", "value": commit},
        )
        ET.SubElement(
            properties,
            "property",
            {"name": "closure.outcome_guard", "value": "enabled_no_access"},
        )
        ET.SubElement(
            properties,
            "property",
            {"name": "closure.private_full_guard", "value": "enabled_no_access"},
        )
    rendered = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return rendered + (b"" if rendered.endswith(b"\n") else b"\n")


def _validate_junit_commit(payload: bytes, repository_commit: str) -> dict[str, int]:
    totals, _ = _parse_junit(payload)
    root = ET.fromstring(payload)
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    for suite in suites:
        closure_properties = [
            node
            for node in suite.findall("./properties/property")
            if node.attrib.get("name")
            in {
                "closure.repository_commit",
                "closure.outcome_guard",
                "closure.private_full_guard",
            }
        ]
        if len(closure_properties) != 3:
            raise ClosureE10SourceEvidenceError(
                "JUnit Closure properties are missing or duplicated"
            )
        properties = {
            node.attrib.get("name"): node.attrib.get("value")
            for node in suite.findall("./properties/property")
        }
        if properties != {
            **{key: value for key, value in properties.items() if key not in {
                "closure.repository_commit",
                "closure.outcome_guard",
                "closure.private_full_guard",
            }},
            "closure.repository_commit": repository_commit,
            "closure.outcome_guard": "enabled_no_access",
            "closure.private_full_guard": "enabled_no_access",
        }:
            raise ClosureE10SourceEvidenceError("JUnit Closure properties drifted")
        if properties.get("closure.repository_commit") != repository_commit:
            raise ClosureE10SourceEvidenceError("JUnit is not bound to exact H")
        if properties.get("closure.outcome_guard") != "enabled_no_access":
            raise ClosureE10SourceEvidenceError("JUnit outcome guard evidence drifted")
        if properties.get("closure.private_full_guard") != "enabled_no_access":
            raise ClosureE10SourceEvidenceError(
                "JUnit private/FULL.md guard evidence drifted"
            )
    return totals


def _validate_command_record(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "argv",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
        "environment_overrides",
        "timeout_seconds",
    }:
        raise ClosureE10SourceEvidenceError(f"{context} command record is not exact")
    argv = value.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(type(item) is str and item for item in argv)
        or value.get("returncode") != 0
        or type(value.get("returncode")) is not int
    ):
        raise ClosureE10SourceEvidenceError(f"{context} command did not pass")
    for key in ("stdout_sha256", "stderr_sha256"):
        if not isinstance(value.get(key), str) or not re.fullmatch(
            r"[0-9a-f]{64}", cast(str, value[key])
        ):
            raise ClosureE10SourceEvidenceError(f"{context} command hash drifted")
    for key in ("stdout_line_count", "stderr_line_count"):
        if type(value.get(key)) is not int or cast(int, value[key]) < 0:
            raise ClosureE10SourceEvidenceError(f"{context} command count drifted")
    overrides = value.get("environment_overrides")
    if (
        not isinstance(overrides, Mapping)
        or overrides.get("PYTHONDONTWRITEBYTECODE") != "1"
        or not all(type(key) is str and type(item) is str for key, item in overrides.items())
    ):
        raise ClosureE10SourceEvidenceError(f"{context} command environment drifted")
    if type(value.get("timeout_seconds")) is not int or cast(
        int, value["timeout_seconds"]
    ) <= 0:
        raise ClosureE10SourceEvidenceError(f"{context} command timeout drifted")
    return cast(Mapping[str, Any], value)


def _validate_exact_commands(
    value: Any, *, repository_commit: str
) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        raise ClosureE10SourceEvidenceError("verification commands are absent")
    expected_keys = {
        "filesystem_denial_probe",
        "public_tests",
        "openapi_generation",
        "end_to_end",
        "exact_h_git_archive",
        "exact_h_tree_inventory",
        "exact_h_dvc_inventory",
        "runtime_probe",
        "poetry_lock_check",
        "python_version",
        "poetry_version",
        "pytest_version",
        "dvc_version",
        "git_version",
    }
    if set(value) != expected_keys:
        raise ClosureE10SourceEvidenceError("verification command names drifted")
    commands = {
        key: _validate_command_record(raw, context=key)
        for key, raw in value.items()
    }
    setup_exact = {
        "filesystem_denial_probe": [
            ".venv/bin/python",
            "-B",
            "-c",
            ISOLATION_PROBE_CODE,
        ],
    }
    for key, argv in setup_exact.items():
        if commands[key]["argv"] != argv:
            raise ClosureE10SourceEvidenceError(f"{key} command drifted")
    isolated_environment = {
        **ISOLATED_ENVIRONMENT_VALUES,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if commands["filesystem_denial_probe"]["environment_overrides"] != (
        isolated_environment
    ):
        raise ClosureE10SourceEvidenceError(
            "filesystem denial probe environment drifted"
        )
    public = cast(list[str], commands["public_tests"]["argv"])
    if tuple(public[:-1]) != PUBLIC_TEST_COMMAND_PREFIX or public[-1] != (
        f"--junitxml={SANDBOX_OUTPUT_PATH.as_posix()}/public_tests_raw.xml"
    ):
        raise ClosureE10SourceEvidenceError("public suite command drifted")
    public_environment = commands["public_tests"]["environment_overrides"]
    if (
        not isinstance(public_environment, Mapping)
        or public_environment
        != {
            **isolated_environment,
            "CLOSURE_E10_OUTCOME_GUARD": "1",
            "CLOSURE_E10_REPO_ROOT": ".",
            "CLOSURE_E10_SUITE_KIND": PUBLIC_SUITE_KIND,
            "TEST_DATABASE_URL": public_environment.get("TEST_DATABASE_URL"),
        }
        or not re.fullmatch(
            r"redacted_sha256:[0-9a-f]{64}",
            str(public_environment.get("TEST_DATABASE_URL", "")),
        )
        or commands["public_tests"]["timeout_seconds"] != 1800
    ):
        raise ClosureE10SourceEvidenceError("public suite environment drifted")
    openapi = cast(list[str], commands["openapi_generation"]["argv"])
    if (
        openapi[:4]
        != [
            ".venv/bin/python",
            "-B",
            "src/experiments/build_closure_e10_source_evidence.py",
            "--emit-openapi",
        ]
        or len(openapi) != 7
        or openapi[4]
        != f"{SANDBOX_OUTPUT_PATH.as_posix()}/openapi_raw.json"
        or openapi[5:] != ["--repository-commit", repository_commit]
    ):
        raise ClosureE10SourceEvidenceError("OpenAPI generation command drifted")
    e2e = cast(list[str], commands["end_to_end"]["argv"])
    expected_e2e_prefix = [
        "poetry",
        "run",
        "pytest",
        *E2E_TEST_NODES,
        "-q",
        "-p",
        "src.experiments.build_closure_e10_source_evidence",
        "-p",
        "no:cacheprovider",
    ]
    if e2e[:-1] != expected_e2e_prefix or e2e[-1] != (
        f"--junitxml={SANDBOX_OUTPUT_PATH.as_posix()}/e2e_raw.xml"
    ):
        raise ClosureE10SourceEvidenceError("end-to-end command drifted")
    if commands["end_to_end"]["timeout_seconds"] != 300:
        raise ClosureE10SourceEvidenceError("end-to-end timeout drifted")
    for key in ("openapi_generation", "runtime_probe"):
        overrides = commands[key]["environment_overrides"]
        if overrides != {
            **isolated_environment,
            "CLOSURE_E10_OUTCOME_GUARD": "1",
            "CLOSURE_E10_REPO_ROOT": ".",
        }:
            raise ClosureE10SourceEvidenceError(f"{key} guard environment drifted")
    if commands["end_to_end"]["environment_overrides"] != {
        **isolated_environment,
        "CLOSURE_E10_OUTCOME_GUARD": "1",
        "CLOSURE_E10_REPO_ROOT": ".",
        "CLOSURE_E10_SUITE_KIND": "synthetic_e2e",
    }:
        raise ClosureE10SourceEvidenceError(
            "end-to-end guard environment drifted"
        )
    git_snapshot_environment = {
        "GIT_OPTIONAL_LOCKS": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    archive = cast(list[str], commands["exact_h_git_archive"]["argv"])
    expected_exclusions = [
        f":(exclude,top){path}" for path in FORBIDDEN_VERIFICATION_PREFIXES
    ]
    if (
        len(archive) != 7 + len(expected_exclusions)
        or archive[:3] != ["git", "archive", "--format=tar"]
        or re.fullmatch(
            rf"--output=tmp/{re.escape(WORK_PREFIX)}[^/]+/exact_h_snapshot\.tar",
            archive[3],
        )
        is None
        or archive[4:8] != [repository_commit, "--", ".", *expected_exclusions[:1]]
        or archive[8:] != expected_exclusions[1:]
        or commands["exact_h_git_archive"]["environment_overrides"]
        != git_snapshot_environment
    ):
        raise ClosureE10SourceEvidenceError("exact-H Git archive command drifted")
    dvc_inventory = commands["exact_h_dvc_inventory"]
    if (
        dvc_inventory["argv"]
        != [
            "git",
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "-z",
            EMPTY_GIT_TREE_SHA1,
            repository_commit,
            "--",
            "data/closure_v1",
            "models.dvc",
            *expected_exclusions,
        ]
        or dvc_inventory["environment_overrides"] != git_snapshot_environment
    ):
        raise ClosureE10SourceEvidenceError(
            "exact-H DVC inventory command drifted"
        )
    tree_inventory = commands["exact_h_tree_inventory"]
    if (
        tree_inventory["argv"]
        != [
            "git",
            "diff-tree",
            "--no-commit-id",
            "--raw",
            "-r",
            "-z",
            EMPTY_GIT_TREE_SHA1,
            repository_commit,
            "--",
            ".",
            *expected_exclusions,
        ]
        or tree_inventory["environment_overrides"] != git_snapshot_environment
    ):
        raise ClosureE10SourceEvidenceError(
            "exact-H tracked tree command drifted"
        )
    exact = {
        "runtime_probe": [
            ".venv/bin/python",
            "-B",
            "src/experiments/build_closure_e10_source_evidence.py",
            "--runtime-probe",
        ],
        "poetry_lock_check": ["poetry", "check", "--lock"],
        "python_version": [".venv/bin/python", "--version"],
        "poetry_version": ["poetry", "--version"],
        "pytest_version": ["poetry", "run", "pytest", "--version"],
        "dvc_version": [".venv/bin/dvc", "--version"],
        "git_version": ["git", "--version"],
    }
    for key, argv in exact.items():
        if commands[key]["argv"] != argv:
            raise ClosureE10SourceEvidenceError(f"{key} command drifted")
        if key not in {"runtime_probe"} and commands[key]["environment_overrides"] != {
            "PYTHONDONTWRITEBYTECODE": "1"
        }:
            raise ClosureE10SourceEvidenceError(f"{key} command environment drifted")
    return cast(Mapping[str, Mapping[str, Any]], commands)


def _validate_filesystem_isolation(
    value: Any,
    *,
    repository_commit: str,
    commands: Mapping[str, Mapping[str, Any]],
    recovery_attempt: str | None = None,
) -> Mapping[str, Any]:
    mode = _require_recovery_attempt(recovery_attempt)
    expected_log_bytes = RECOVERY_OUTCOME_LOG_BYTES if mode else 0
    expected_log_sha256 = (
        RECOVERY_OUTCOME_LOG_SHA256 if mode else _sha256(b"")
    )
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "backend",
        "repository_commit",
        "worktree_path",
        "worktree_pre_verification",
        "worktree_post_verification",
        "restricted_mask_tree_path",
        "restricted_path_masks",
        "host_outcome_log_pre_verification",
        "host_outcome_log_post_verification",
        "tracked_empty_log_mask",
        "exact_h_snapshot",
        "repository_mount",
        "command_output_mount",
        "system_temporary_directory",
        "ambient_environment_inherited",
        "network_namespace",
        "user_pid_ipc_uts_cgroup_namespaces",
        "linux_capabilities",
        "child_user_namespaces",
        "isolated_command_names",
        "execution_argv_template_prefix",
        "permitted_input_mounts",
        "denial_probe_results",
        "static_access_inventory",
    }:
        raise ClosureE10SourceEvidenceError(
            "filesystem isolation record keys drifted"
        )
    if (
        value.get("schema_version")
        != "closure_e10_bubblewrap_exact_h_snapshot_masked_view_v1"
        or value.get("backend") != BWRAP_BACKEND
        or value.get("repository_commit") != repository_commit
        or value.get("worktree_path")
        != "<WORK_DIRECTORY>/exact_h_snapshot"
        or value.get("restricted_mask_tree_path")
        != "<MASK_DIRECTORY>"
        or value.get("repository_mount")
        != (
            "read_only_materialized_exact_h_snapshot_with_direct_and_opaque_"
            "restricted_masks"
        )
        or value.get("command_output_mount")
        != "read_write_private_work_directory_tmp"
        or value.get("system_temporary_directory") != "private_tmpfs"
        or value.get("ambient_environment_inherited") is not False
        or value.get("network_namespace")
        != "shared_host_network_for_loopback_postgresql_fixture"
        or value.get("user_pid_ipc_uts_cgroup_namespaces") != "unshared"
        or value.get("linux_capabilities") != "all_dropped"
        or value.get("child_user_namespaces") != "disabled"
        or value.get("isolated_command_names")
        != list(BWRAP_ISOLATED_COMMAND_NAMES)
        or value.get("static_access_inventory") != STATIC_ACCESS_INVENTORY
    ):
        raise ClosureE10SourceEvidenceError(
            "filesystem isolation policy drifted"
        )
    restricted_masks = value.get("restricted_path_masks")
    if restricted_masks != [dict(spec) for spec in RESTRICTED_MASK_SPECS]:
        raise ClosureE10SourceEvidenceError(
            "filesystem isolation restricted-path mounts drifted"
        )
    host_log_pre = value.get("host_outcome_log_pre_verification")
    host_log_post = value.get("host_outcome_log_post_verification")
    expected_host_log_keys = {
        "path",
        "repository_commit",
        "entry_type",
        "device",
        "inode",
        "mode",
        "nlink",
        "bytes",
        "mtime_ns",
        "ctime_ns",
        "h_blob_bytes",
        "h_blob_sha256",
        "h_blob_command",
        "index_mode",
        "index_blob_sha1",
        "index_stage",
        "index_entry_command",
        "physical_contents_opened",
    }
    if (
        not isinstance(host_log_pre, Mapping)
        or host_log_pre != host_log_post
        or set(host_log_pre) != expected_host_log_keys
        or host_log_pre.get("path") != OUTCOME_ACCESS_LOG_PATH.as_posix()
        or host_log_pre.get("repository_commit") != repository_commit
        or host_log_pre.get("entry_type") != "regular_file"
        or type(host_log_pre.get("device")) is not int
        or cast(int, host_log_pre["device"]) < 0
        or type(host_log_pre.get("inode")) is not int
        or cast(int, host_log_pre["inode"]) <= 0
        or re.fullmatch(r"[0-7]{3}", str(host_log_pre.get("mode"))) is None
        or int(str(host_log_pre["mode"]), 8) & 0o111
        or (
            mode == RECOVERY_ATTEMPT_1
            and host_log_pre.get("mode") != "644"
        )
        or host_log_pre.get("nlink") != 1
        or host_log_pre.get("bytes") != expected_log_bytes
        or type(host_log_pre.get("mtime_ns")) is not int
        or type(host_log_pre.get("ctime_ns")) is not int
        or host_log_pre.get("h_blob_bytes") != expected_log_bytes
        or host_log_pre.get("h_blob_sha256") != expected_log_sha256
        or host_log_pre.get("index_mode") != "100644"
        or (
            mode is None
            and host_log_pre.get("index_blob_sha1") != EMPTY_GIT_BLOB_SHA1
        )
        or (
            mode == RECOVERY_ATTEMPT_1
            and re.fullmatch(
                r"[0-9a-f]{40}",
                str(host_log_pre.get("index_blob_sha1", "")),
            )
            is None
        )
        or host_log_pre.get("index_stage") != 0
        or host_log_pre.get("physical_contents_opened") is not False
    ):
        raise ClosureE10SourceEvidenceError(
            "host outcome-log isolation binding drifted"
        )
    host_log_command = _validate_command_record(
        host_log_pre["h_blob_command"], context="host outcome-log H blob"
    )
    if (
        host_log_command.get("argv")
        != [
            "git",
            "show",
            f"{repository_commit}:{OUTCOME_ACCESS_LOG_PATH.as_posix()}",
        ]
        or host_log_command.get("environment_overrides")
        != {"GIT_OPTIONAL_LOCKS": "0", "PYTHONDONTWRITEBYTECODE": "1"}
        or host_log_command.get("stdout_sha256") != expected_log_sha256
        or host_log_command.get("stderr_sha256") != _sha256(b"")
        or host_log_command.get("stdout_line_count")
        != (1 if mode == RECOVERY_ATTEMPT_1 else 0)
        or host_log_command.get("stderr_line_count") != 0
    ):
        raise ClosureE10SourceEvidenceError(
            "host outcome-log H command drifted"
        )
    index_command = _validate_command_record(
        host_log_pre["index_entry_command"],
        context="host outcome-log index entry",
    )
    expected_index_stdout = (
        f"100644 {host_log_pre['index_blob_sha1']} 0\t"
        f"{OUTCOME_ACCESS_LOG_PATH.as_posix()}\n"
    ).encode("utf-8")
    if (
        index_command.get("argv")
        != [
            "git",
            "ls-files",
            "--stage",
            "--",
            OUTCOME_ACCESS_LOG_PATH.as_posix(),
        ]
        or index_command.get("environment_overrides")
        != {"GIT_OPTIONAL_LOCKS": "0", "PYTHONDONTWRITEBYTECODE": "1"}
        or index_command.get("stdout_sha256") != _sha256(expected_index_stdout)
        or index_command.get("stderr_sha256") != _sha256(b"")
        or index_command.get("stdout_line_count") != 1
        or index_command.get("stderr_line_count") != 0
    ):
        raise ClosureE10SourceEvidenceError(
            "host outcome-log index command drifted"
        )
    if value.get("tracked_empty_log_mask") != {
        "path": OUTCOME_ACCESS_LOG_PATH.as_posix(),
        "entry_type": "tracked_empty_file",
        "mode": "444",
        "bytes": 0,
        "single_link_regular_file": True,
        "probe_read_result": "synthetic_empty_eof",
        "host_path_opened": False,
    }:
        raise ClosureE10SourceEvidenceError(
            "tracked empty outcome-log mask drifted"
        )
    expected_permitted_mounts = [
        {
            "path": ".",
            "source": "materialized_tracked_h_plus_authenticated_dvc_snapshot",
            "read_only": True,
        },
        {
            "path": ".git",
            "source": "host_git_metadata_read_only_refs_verified_pre_and_post",
            "read_only": True,
        },
        {
            "path": ".venv",
            "source": "host_runtime_environment_lock_and_versions_recorded",
            "read_only": True,
        },
    ]
    if value.get("permitted_input_mounts") != expected_permitted_mounts:
        raise ClosureE10SourceEvidenceError(
            "filesystem isolation permitted input mounts drifted"
        )
    for key in ("worktree_pre_verification", "worktree_post_verification"):
        state = value.get(key)
        if (
            not isinstance(state, Mapping)
            or state.get("branch") != "main"
            or state.get("repository_commit") != repository_commit
            or state.get("clean_worktree") is not True
            or not isinstance(state.get("refs"), Mapping)
            or set(cast(Mapping[str, Any], state["refs"]).values())
            != {repository_commit}
            or not isinstance(state.get("builder_source"), Mapping)
            or cast(Mapping[str, Any], state["builder_source"]).get("path")
            != BUILDER_SOURCE_PATH.as_posix()
            or cast(Mapping[str, Any], state["builder_source"]).get(
                "physical_equals_h_blob"
            )
            is not True
        ):
            raise ClosureE10SourceEvidenceError(
                "filesystem isolation worktree state drifted"
            )
    if value.get("worktree_pre_verification") != value.get(
        "worktree_post_verification"
    ):
        raise ClosureE10SourceEvidenceError(
            "filesystem isolation worktree changed during verification"
        )
    snapshot = value.get("exact_h_snapshot")
    if not isinstance(snapshot, Mapping) or set(snapshot) != {
        "schema_version",
        "repository_commit",
        "tracked_export",
        "dvc_restore",
        "pre_execution_inventory",
        "post_execution_inventory",
        "source_worktree_written",
        "network_used",
    }:
        raise ClosureE10SourceEvidenceError("exact-H snapshot record drifted")
    tracked_export = snapshot.get("tracked_export")
    dvc_restore = snapshot.get("dvc_restore")
    pre_inventory = snapshot.get("pre_execution_inventory")
    post_inventory = snapshot.get("post_execution_inventory")
    if (
        snapshot.get("schema_version")
        != "closure_e10_materialized_exact_h_snapshot_v1"
        or snapshot.get("repository_commit") != repository_commit
        or snapshot.get("source_worktree_written") is not False
        or snapshot.get("network_used") is not False
        or not isinstance(tracked_export, Mapping)
        or set(tracked_export)
        != {
            "command",
            "archive_bytes",
            "archive_sha256",
            "restricted_pathspec_exclusions",
            "tracked_tree_verification",
        }
        or tracked_export.get("command") != commands["exact_h_git_archive"]
        or type(tracked_export.get("archive_bytes")) is not int
        or cast(int, tracked_export["archive_bytes"]) <= 0
        or re.fullmatch(
            r"[0-9a-f]{64}", str(tracked_export.get("archive_sha256"))
        )
        is None
        or tracked_export.get("restricted_pathspec_exclusions")
        != list(FORBIDDEN_VERIFICATION_PREFIXES)
    ):
        raise ClosureE10SourceEvidenceError("exact-H tracked export drifted")
    tree_verification = tracked_export.get("tracked_tree_verification")
    if (
        not isinstance(tree_verification, Mapping)
        or set(tree_verification)
        != {
            "command",
            "entry_count",
            "listing_sha256",
            "all_nonrestricted_h_paths_and_blobs_exact",
        }
        or tree_verification.get("command")
        != commands["exact_h_tree_inventory"]
        or type(tree_verification.get("entry_count")) is not int
        or cast(int, tree_verification["entry_count"]) <= 0
        or re.fullmatch(
            r"[0-9a-f]{64}", str(tree_verification.get("listing_sha256"))
        )
        is None
        or tree_verification.get("listing_sha256")
        != commands["exact_h_tree_inventory"].get("stdout_sha256")
        or tree_verification.get("all_nonrestricted_h_paths_and_blobs_exact")
        is not True
    ):
        raise ClosureE10SourceEvidenceError(
            "exact-H tracked tree verification drifted"
        )
    if (
        not isinstance(dvc_restore, Mapping)
        or set(dvc_restore)
        != {
            "status",
            "mode",
            "repository_commit",
            "network_used",
            "main_worktree_written",
            "inventory_command",
            "pointer_count",
            "restored_file_count",
            "restored_bytes",
            "records",
        }
        or dvc_restore.get("status") != "passed"
        or dvc_restore.get("mode")
        != "all_permitted_exact_h_pointers_offline_local_cache_restore"
        or dvc_restore.get("repository_commit") != repository_commit
        or dvc_restore.get("network_used") is not False
        or dvc_restore.get("main_worktree_written") is not False
        or dvc_restore.get("inventory_command")
        != commands["exact_h_dvc_inventory"]
        or type(dvc_restore.get("pointer_count")) is not int
        or cast(int, dvc_restore["pointer_count"]) < len(DVC_RESTORE_POINTERS) + 1
        or type(dvc_restore.get("restored_file_count")) is not int
        or cast(int, dvc_restore["restored_file_count"]) <= 0
        or type(dvc_restore.get("restored_bytes")) is not int
        or cast(int, dvc_restore["restored_bytes"]) <= 0
        or not isinstance(dvc_restore.get("records"), list)
        or len(cast(list[Any], dvc_restore["records"]))
        != dvc_restore.get("pointer_count")
    ):
        raise ClosureE10SourceEvidenceError("exact-H snapshot DVC restore drifted")
    dvc_records = cast(list[Any], dvc_restore["records"])
    pointer_paths: list[str] = []
    for raw_record in dvc_records:
        if not isinstance(raw_record, Mapping) or set(raw_record) != {
            "pointer_path",
            "pointer_bytes",
            "pointer_sha256",
            "output_path",
            "payload_md5",
            "payload_bytes",
            "payload_file_count",
            "directory_output",
            "declared_nfiles",
            "payload_sha256",
            "output_initially_absent",
            "restored_from_local_cache",
        }:
            raise ClosureE10SourceEvidenceError(
                "exact-H snapshot DVC record drifted"
            )
        pointer_path = raw_record.get("pointer_path")
        output_path = raw_record.get("output_path")
        pointer_candidate = Path(pointer_path) if isinstance(pointer_path, str) else None
        if (
            not isinstance(pointer_path, str)
            or not isinstance(output_path, str)
            or pointer_candidate is None
            or pointer_candidate.is_absolute()
            or ".." in pointer_candidate.parts
            or pointer_candidate.as_posix() != pointer_path
            or not (
                pointer_path == "models.dvc"
                or pointer_path.startswith("data/closure_v1/")
                and pointer_path.endswith(".dvc")
            )
            or re.fullmatch(r"[0-9a-f]{32}(?:\.dir)?", str(raw_record.get("payload_md5")))
            is None
            or str(raw_record.get("payload_md5")).endswith(".dir")
            != (raw_record.get("directory_output") is True)
            or type(raw_record.get("pointer_bytes")) is not int
            or cast(int, raw_record["pointer_bytes"]) <= 0
            or re.fullmatch(r"[0-9a-f]{64}", str(raw_record.get("pointer_sha256")))
            is None
            or type(raw_record.get("payload_bytes")) is not int
            or cast(int, raw_record["payload_bytes"]) <= 0
            or type(raw_record.get("payload_file_count")) is not int
            or cast(int, raw_record["payload_file_count"]) <= 0
            or type(raw_record.get("directory_output")) is not bool
            or (
                raw_record.get("directory_output") is True
                and raw_record.get("declared_nfiles")
                != raw_record.get("payload_file_count")
            )
            or (
                raw_record.get("directory_output") is False
                and (
                    raw_record.get("declared_nfiles") is not None
                    or re.fullmatch(
                        r"[0-9a-f]{64}",
                        str(raw_record.get("payload_sha256")),
                    )
                    is None
                )
            )
            or (
                raw_record.get("directory_output") is True
                and raw_record.get("payload_sha256") is not None
            )
            or raw_record.get("restored_from_local_cache") is not True
            or raw_record.get("output_initially_absent") is not True
            or any(
                output_path == prefix
                or output_path.startswith(prefix.rstrip("/") + "/")
                for prefix in FORBIDDEN_VERIFICATION_PREFIXES
            )
        ):
            raise ClosureE10SourceEvidenceError(
                "exact-H snapshot DVC binding drifted"
            )
        pointer_paths.append(pointer_path)
        expected_output = (
            Path(pointer_path).parent / Path(pointer_path).with_suffix("").name
        ).as_posix()
        if output_path != expected_output:
            raise ClosureE10SourceEvidenceError(
                "exact-H snapshot DVC output path drifted"
            )
    if (
        pointer_paths != sorted(set(pointer_paths))
        or not {
            *(path.as_posix() for path in DVC_RESTORE_POINTERS),
            "models.dvc",
        }.issubset(pointer_paths)
    ):
        raise ClosureE10SourceEvidenceError(
            "exact-H snapshot DVC pointer scope drifted"
        )
    if (
        sum(cast(int, record["payload_file_count"]) for record in dvc_records)
        != dvc_restore.get("restored_file_count")
        or sum(cast(int, record["payload_bytes"]) for record in dvc_records)
        != dvc_restore.get("restored_bytes")
    ):
        raise ClosureE10SourceEvidenceError(
            "exact-H snapshot DVC aggregate drifted"
        )
    if pre_inventory != post_inventory or not isinstance(pre_inventory, Mapping):
        raise ClosureE10SourceEvidenceError(
            "exact-H snapshot changed during verification"
        )
    if set(pre_inventory) != {
        "schema_version",
        "root_identity",
        "entry_count",
        "records_sha256",
        "records",
    }:
        raise ClosureE10SourceEvidenceError("exact-H snapshot inventory drifted")
    inventory_records = pre_inventory.get("records")
    root_identity = pre_inventory.get("root_identity")
    if (
        pre_inventory.get("schema_version")
        != "closure_e10_exact_h_snapshot_inventory_v1"
        or type(pre_inventory.get("entry_count")) is not int
        or cast(int, pre_inventory["entry_count"]) <= 0
        or not isinstance(inventory_records, list)
        or len(inventory_records) != pre_inventory.get("entry_count")
        or pre_inventory.get("records_sha256")
        != _sha256(_canonical_json(inventory_records))
        or not isinstance(root_identity, Mapping)
        or set(root_identity)
        != {"device", "inode", "mode", "nlink", "mtime_ns", "ctime_ns"}
        or type(root_identity.get("device")) is not int
        or type(root_identity.get("inode")) is not int
        or cast(int, root_identity["inode"]) <= 0
        or re.fullmatch(r"[0-7]{3}", str(root_identity.get("mode"))) is None
        or type(root_identity.get("nlink")) is not int
        or type(root_identity.get("mtime_ns")) is not int
        or type(root_identity.get("ctime_ns")) is not int
    ):
        raise ClosureE10SourceEvidenceError("exact-H snapshot inventory drifted")
    inventory_paths = [
        record.get("path") if isinstance(record, Mapping) else None
        for record in inventory_records
    ]
    if (
        not all(isinstance(path, str) for path in inventory_paths)
        or cast(list[str], inventory_paths) != sorted(set(inventory_paths))
    ):
        raise ClosureE10SourceEvidenceError(
            "exact-H snapshot inventory paths drifted"
        )
    inventory_by_path = {
        cast(str, record["path"]): record
        for record in inventory_records
        if isinstance(record, Mapping) and isinstance(record.get("path"), str)
    }
    target_record = inventory_by_path.get("data/targets")
    if (
        not isinstance(target_record, Mapping)
        or target_record.get("entry_type") != "directory"
        or any(
            path.startswith("data/targets/")
            for path in cast(list[str], inventory_paths)
        )
        or any(
            path == prefix or path.startswith(prefix + "/")
            for path in cast(list[str], inventory_paths)
            for prefix in (
                "data/closure_v1/unblinded",
                "data/closure_v1/evaluation_outcomes",
            )
        )
    ):
        raise ClosureE10SourceEvidenceError(
            "exact-H snapshot restricted directories drifted"
        )
    for restricted_file in (
        OUTCOME_ACCESS_LOG_PATH.as_posix(),
        "private/FULL.md",
    ):
        record = inventory_by_path.get(restricted_file)
        if (
            not isinstance(record, Mapping)
            or record.get("entry_type") != "regular_file"
            or record.get("bytes") != 0
            or record.get("sha256") != _sha256(b"")
        ):
            raise ClosureE10SourceEvidenceError(
                "exact-H snapshot restricted file placeholder drifted"
            )
    for dvc_record in dvc_records:
        pointer_record = inventory_by_path.get(
            cast(str, dvc_record["pointer_path"])
        )
        if (
            not isinstance(pointer_record, Mapping)
            or pointer_record.get("entry_type") != "regular_file"
            or pointer_record.get("bytes") != dvc_record.get("pointer_bytes")
            or pointer_record.get("sha256")
            != dvc_record.get("pointer_sha256")
        ):
            raise ClosureE10SourceEvidenceError(
                "exact-H DVC pointer is not bound to snapshot inventory"
            )
        output_path = cast(str, dvc_record["output_path"])
        if dvc_record.get("directory_output") is True:
            output_root = inventory_by_path.get(output_path)
            descendants = [
                record
                for path, record in inventory_by_path.items()
                if path.startswith(output_path.rstrip("/") + "/")
                and record.get("entry_type") == "regular_file"
            ]
            if (
                not isinstance(output_root, Mapping)
                or output_root.get("entry_type") != "directory"
                or len(descendants) != dvc_record.get("payload_file_count")
                or sum(cast(int, record.get("bytes", -1)) for record in descendants)
                != dvc_record.get("payload_bytes")
            ):
                raise ClosureE10SourceEvidenceError(
                    "exact-H DVC directory is not bound to snapshot inventory"
                )
        else:
            output_record = inventory_by_path.get(output_path)
            if (
                not isinstance(output_record, Mapping)
                or output_record.get("entry_type") != "regular_file"
                or output_record.get("bytes") != dvc_record.get("payload_bytes")
                or output_record.get("sha256")
                != dvc_record.get("payload_sha256")
            ):
                raise ClosureE10SourceEvidenceError(
                    "exact-H DVC file is not bound to snapshot inventory"
                )
    builder_records = [
        record
        for record in inventory_records
        if isinstance(record, Mapping)
        and record.get("path") == BUILDER_SOURCE_PATH.as_posix()
    ]
    builder_state = cast(
        Mapping[str, Any],
        cast(Mapping[str, Any], value["worktree_pre_verification"])[
            "builder_source"
        ],
    )
    if (
        len(builder_records) != 1
        or builder_records[0].get("entry_type") != "regular_file"
        or builder_records[0].get("bytes") != builder_state.get("bytes")
        or builder_records[0].get("sha256") != builder_state.get("sha256")
    ):
        raise ClosureE10SourceEvidenceError(
            "exact-H snapshot builder blob drifted"
        )
    template = value.get("execution_argv_template_prefix")
    expected_template = _bubblewrap_template(
        cast(Sequence[Mapping[str, Any]], restricted_masks)
    )
    if template != expected_template:
        raise ClosureE10SourceEvidenceError(
            "bubblewrap execution argv template drifted"
        )
    probe_results = value.get("denial_probe_results")
    if probe_results != _expected_denial_probe_results():
        raise ClosureE10SourceEvidenceError(
            "filesystem denial probe result drifted"
        )
    expected_probe_stdout = _canonical_json(probe_results)
    probe_command = commands["filesystem_denial_probe"]
    if (
        probe_command.get("stdout_sha256") != _sha256(expected_probe_stdout)
        or probe_command.get("stdout_line_count") != 1
        or probe_command.get("stderr_sha256") != _sha256(b"")
        or probe_command.get("stderr_line_count") != 0
    ):
        raise ClosureE10SourceEvidenceError(
            "filesystem denial probe command output drifted"
        )
    return cast(Mapping[str, Any], value)


def _skip_classification(reason: str) -> str | None:
    if reason == PUBLIC_PRE_E0U_EXCLUSION_REASON:
        return "pre_e0u_repository_target_test_excluded"
    if reason == PUBLIC_USER_PROHIBITED_GIT_COMMIT_EXCLUSION_REASON:
        return "user_prohibited_git_commit_fixture"
    return None


def _require_public_test_success(
    totals: Mapping[str, int], skipped: Sequence[Mapping[str, str]]
) -> list[dict[str, Any]]:
    if (
        totals.get("tests") != PUBLIC_PHASE3_EXPECTED_TEST_COUNT
        or totals.get("failures") != 0
        or totals.get("errors") != 0
        or totals.get("skipped") != PUBLIC_PHASE3_EXPECTED_SKIP_COUNT
        or totals.get("tests", 0) - totals.get("skipped", 0)
        != PUBLIC_PHASE3_EXPECTED_PASS_COUNT
    ):
        raise ClosureE10SourceEvidenceError(
            "public Phase 3 suite inventory did not pass exactly"
        )
    ledger: list[dict[str, Any]] = []
    database_test = (
        "test_register_experiment_scientific_dataset_creates_sql_and_science_links"
    )
    expected_target_exclusions = {
        (Path(nodeid.split("::", 1)[0]).stem, nodeid.split("::", 1)[1])
        for nodeid in PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES
    }
    expected_git_exclusions = {
        (Path(nodeid.split("::", 1)[0]).stem, nodeid.split("::", 1)[1])
        for nodeid in PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES
    }
    observed_target_exclusions: set[tuple[str, str]] = set()
    observed_git_exclusions: set[tuple[str, str]] = set()
    for raw in skipped:
        record: dict[str, Any] = {
            key: str(raw.get(key, ""))
            for key in ("classname", "name", "reason")
        }
        if not record["reason"]:
            raise ClosureE10SourceEvidenceError("public suite contains an unjustified skip")
        if record["name"] == database_test:
            raise ClosureE10SourceEvidenceError(
                "the formerly skipped TEST_DATABASE_URL HTTP test is still skipped"
            )
        classification = _skip_classification(record["reason"])
        if classification is None:
            raise ClosureE10SourceEvidenceError(
                "public suite contains an unclassified skip reason"
            )
        if classification == "pre_e0u_repository_target_test_excluded":
            identity = (
                record["classname"].rsplit(".", 1)[-1],
                record["name"],
            )
            if identity not in expected_target_exclusions:
                raise ClosureE10SourceEvidenceError(
                    "public suite target-dependent skip escaped its exact registry"
                )
            observed_target_exclusions.add(identity)
        elif classification == "user_prohibited_git_commit_fixture":
            identity = (
                record["classname"].rsplit(".", 1)[-1],
                record["name"],
            )
            if identity not in expected_git_exclusions:
                raise ClosureE10SourceEvidenceError(
                    "public suite Git-commit skip escaped its exact registry"
                )
            observed_git_exclusions.add(identity)
        record["classification"] = classification
        record["justified"] = True
        ledger.append(record)
    if observed_target_exclusions != expected_target_exclusions:
        raise ClosureE10SourceEvidenceError(
            "public suite target-dependent skip ledger is incomplete"
        )
    if observed_git_exclusions != expected_git_exclusions:
        raise ClosureE10SourceEvidenceError(
            "public suite Git-commit skip ledger is incomplete"
        )
    if len(ledger) != (
        len(PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES)
        + len(PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES)
    ):
        raise ClosureE10SourceEvidenceError("public suite skip ledger contains duplicates")
    return ledger


def _extract_documented_operations(
    *, repo_root: Path
) -> tuple[set[tuple[str, str]], list[dict[str, Any]]]:
    operations: set[tuple[str, str]] = set()
    records: list[dict[str, Any]] = []
    for path in DOCUMENTED_API_PATHS:
        payload = _read_regular(path, repo_root=repo_root, context="API contract document")
        text = payload.decode("utf-8")
        found = {
            (method.lower(), endpoint.rstrip(".,;:)"))
            for method, endpoint in _DOCUMENTED_OPERATION_RE.findall(text)
        }
        operations.update(found)
        records.append(
            {
                "path": path.as_posix(),
                "bytes": len(payload),
                "sha256": _sha256(payload),
                "documented_operation_count": len(found),
            }
        )
    if not operations:
        raise ClosureE10SourceEvidenceError("API documents declare no operations")
    return operations, records


def _validate_openapi_contract(
    openapi: Mapping[str, Any], *, repo_root: Path
) -> dict[str, Any]:
    if not isinstance(openapi.get("openapi"), str) or not str(openapi["openapi"]).startswith("3."):
        raise ClosureE10SourceEvidenceError("OpenAPI version is not 3.x")
    paths = openapi.get("paths")
    if not isinstance(paths, Mapping) or not paths:
        raise ClosureE10SourceEvidenceError("OpenAPI paths are absent")
    operations: set[tuple[str, str]] = set()
    operation_ids: list[str] = []
    for path, raw_path in paths.items():
        if not isinstance(path, str) or not isinstance(raw_path, Mapping):
            raise ClosureE10SourceEvidenceError("OpenAPI path item is malformed")
        for method, operation in raw_path.items():
            if method not in _HTTP_METHODS:
                continue
            if not isinstance(operation, Mapping):
                raise ClosureE10SourceEvidenceError("OpenAPI operation is malformed")
            operations.add((method, path))
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise ClosureE10SourceEvidenceError("OpenAPI operationId is absent")
            operation_ids.append(operation_id)
            parameters = operation.get("parameters", [])
            if not isinstance(parameters, list):
                raise ClosureE10SourceEvidenceError("OpenAPI parameters are malformed")
            declared_path_parameters = {
                str(item.get("name"))
                for item in parameters
                if isinstance(item, Mapping) and item.get("in") == "path"
            }
            encoded_path_parameters = set(re.findall(r"\{([^{}]+)\}", path))
            if declared_path_parameters != encoded_path_parameters:
                raise ClosureE10SourceEvidenceError(
                    f"OpenAPI path parameter drifted: {method.upper()} {path}"
                )
    if len(operation_ids) != len(set(operation_ids)):
        raise ClosureE10SourceEvidenceError("OpenAPI operationId values are not unique")
    documented, document_records = _extract_documented_operations(repo_root=repo_root)
    missing = sorted(documented.difference(operations))
    if missing:
        raise ClosureE10SourceEvidenceError(
            f"documented API operations are missing from OpenAPI: {missing}"
        )
    return {
        "valid": True,
        "openapi_path_count": len(paths),
        "openapi_operation_count": len(operations),
        "documented_operation_count": len(documented),
        "missing_documented_operations": [],
        "operation_ids_unique": True,
        "path_parameters_exact": True,
        "documents": document_records,
    }


def _parse_dvc_pointer(payload: bytes, pointer_path: Path) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClosureE10SourceEvidenceError(
            f"DVC pointer is not UTF-8: {pointer_path}"
        ) from exc
    match = re.fullmatch(
        r"outs:\n"
        r"- md5: ([0-9a-f]{32})(\.dir)?\n"
        r"  size: ([1-9][0-9]*)\n"
        r"(?:  nfiles: ([1-9][0-9]*)\n)?"
        r"  hash: md5\n"
        r"  path: ([A-Za-z0-9_.-]+)\n",
        text,
    )
    if match is None:
        raise ClosureE10SourceEvidenceError(
            f"DVC pointer dialect drifted: {pointer_path}"
        )
    is_directory = match.group(2) is not None
    digest = match.group(1) + (".dir" if is_directory else "")
    size = int(match.group(3))
    nfiles = int(match.group(4)) if match.group(4) is not None else None
    output_name = match.group(5)
    if (
        Path(output_name).name != output_name
        or output_name != pointer_path.with_suffix("").name
        or (is_directory and nfiles is None)
        or (not is_directory and nfiles is not None)
    ):
        raise ClosureE10SourceEvidenceError(f"DVC pointer values drifted: {pointer_path}")
    return {
        "md5": digest,
        "size": size,
        "nfiles": nfiles,
        "path": output_name,
        "is_directory": is_directory,
    }


def _ensure_snapshot_directory(snapshot_root: Path, relative: Path) -> Path:
    """Create one real directory chain below an owned snapshot root."""

    if relative.is_absolute() or ".." in relative.parts:
        raise ClosureE10SourceEvidenceError("snapshot directory escaped")
    current = snapshot_root
    for component in relative.parts:
        current /= component
        if os.path.lexists(current):
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(
                metadata.st_mode
            ):
                raise ClosureE10SourceEvidenceError(
                    "snapshot directory chain is unsafe"
                )
        else:
            current.mkdir(mode=0o700)
    return current


def _dvc_cache_relative(digest: str) -> Path:
    if re.fullmatch(r"[0-9a-f]{32}(?:\.dir)?", digest) is None:
        raise ClosureE10SourceEvidenceError("DVC cache digest drifted")
    plain = digest.removesuffix(".dir")
    suffix = ".dir" if digest.endswith(".dir") else ""
    return Path(".dvc/cache/files/md5") / plain[:2] / (plain[2:] + suffix)


def _restore_dvc_cache_object(
    *,
    repo_root: Path,
    snapshot_root: Path,
    destination: Path,
    digest: str,
    expected_size: int | None,
) -> tuple[int, int]:
    """Restore one authenticated file or directory object into the snapshot."""

    try:
        relative = destination.relative_to(snapshot_root)
    except ValueError as exc:
        raise ClosureE10SourceEvidenceError("DVC restore escaped snapshot") from exc
    if relative.is_absolute() or ".." in relative.parts:
        raise ClosureE10SourceEvidenceError("DVC restore path is unsafe")
    relative_text = relative.as_posix()
    if any(
        relative_text == prefix
        or relative_text.startswith(prefix.rstrip("/") + "/")
        for prefix in FORBIDDEN_VERIFICATION_PREFIXES
    ):
        raise ClosureE10SourceEvidenceError(
            "DVC restore attempted a restricted namespace"
        )
    cache_path = _dvc_cache_relative(digest)
    cache_bytes = _read_regular(
        cache_path,
        repo_root=repo_root,
        context="exact-H DVC cache object",
        require_nlink_one=False,
    )
    if digest.endswith(".dir"):
        if _md5(cache_bytes) != digest.removesuffix(".dir"):
            raise ClosureE10SourceEvidenceError("DVC directory cache hash drifted")
        try:
            entries = json.loads(cache_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ClosureE10SourceEvidenceError(
                "DVC directory cache JSON is invalid"
            ) from exc
        if not isinstance(entries, list) or not entries:
            raise ClosureE10SourceEvidenceError(
                "DVC directory cache entries drifted"
            )
        _ensure_snapshot_directory(snapshot_root, relative)
        total_bytes = 0
        total_files = 0
        previous_relpath: str | None = None
        for raw in entries:
            if not isinstance(raw, Mapping) or set(raw) not in (
                {"md5", "relpath"},
                {"md5", "relpath", "size"},
            ):
                raise ClosureE10SourceEvidenceError(
                    "DVC directory cache entry dialect drifted"
                )
            child_digest = raw.get("md5")
            child_relpath = raw.get("relpath")
            child_size = raw.get("size")
            if (
                not isinstance(child_digest, str)
                or re.fullmatch(r"[0-9a-f]{32}", child_digest) is None
                or not isinstance(child_relpath, str)
                or not child_relpath
                or child_size is not None
                and (type(child_size) is not int or child_size < 0)
            ):
                raise ClosureE10SourceEvidenceError(
                    "DVC directory cache values drifted"
                )
            child_relative = Path(child_relpath)
            if (
                child_relative.is_absolute()
                or ".." in child_relative.parts
                or child_relative.as_posix() != child_relpath
                or previous_relpath is not None
                and child_relpath <= previous_relpath
            ):
                raise ClosureE10SourceEvidenceError(
                    "DVC directory cache order/path drifted"
                )
            previous_relpath = child_relpath
            child_files, child_bytes = _restore_dvc_cache_object(
                repo_root=repo_root,
                snapshot_root=snapshot_root,
                destination=destination / child_relative,
                digest=child_digest,
                expected_size=cast(int | None, child_size),
            )
            total_files += child_files
            total_bytes += child_bytes
        if expected_size is not None and total_bytes != expected_size:
            raise ClosureE10SourceEvidenceError(
                "DVC directory restored size drifted"
            )
        return total_files, total_bytes

    if expected_size is not None and len(cache_bytes) != expected_size:
        raise ClosureE10SourceEvidenceError("DVC file cache size drifted")
    if _md5(cache_bytes) != digest:
        raise ClosureE10SourceEvidenceError("DVC file cache hash drifted")
    _ensure_snapshot_directory(snapshot_root, relative.parent)
    if os.path.lexists(destination):
        raise ClosureE10SourceEvidenceError(
            "exact-H DVC output destination was not initially absent"
        )
    _write_exclusive(destination, cache_bytes)
    destination.chmod(0o444)
    return 1, len(cache_bytes)


def _restore_snapshot_dvc_inputs(
    *, repo_root: Path, snapshot_root: Path, repository_commit: str
) -> dict[str, Any]:
    """Restore every permitted Closure/model DVC output bound by exact H."""

    commit = _require_commit(repository_commit)
    command, stdout, stderr = _run(
        (
            "git",
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "-z",
            EMPTY_GIT_TREE_SHA1,
            commit,
            "--",
            "data/closure_v1",
            "models.dvc",
            *(
                f":(exclude,top){path}"
                for path in FORBIDDEN_VERIFICATION_PREFIXES
            ),
        ),
        repo_root=repo_root,
        environment={"GIT_OPTIONAL_LOCKS": "0"},
    )
    if stderr:
        raise ClosureE10SourceEvidenceError("exact-H DVC inventory emitted stderr")
    listed = [value for value in stdout.split("\0") if value]
    pointer_paths: list[Path] = sorted(
        {
            Path(value)
            for value in listed
            if value == "models.dvc"
            or value.startswith("data/closure_v1/") and value.endswith(".dvc")
        },
        key=lambda item: item.as_posix(),
    )
    required = {*DVC_RESTORE_POINTERS, Path("models.dvc")}
    if not required.issubset(pointer_paths):
        raise ClosureE10SourceEvidenceError(
            "exact-H DVC inventory omits required public-suite inputs"
        )
    records: list[dict[str, Any]] = []
    restored_files = 0
    restored_bytes = 0
    for pointer_path in pointer_paths:
        if any(
            pointer_path.as_posix() == prefix
            or pointer_path.as_posix().startswith(prefix.rstrip("/") + "/")
            for prefix in FORBIDDEN_VERIFICATION_PREFIXES
        ):
            raise ClosureE10SourceEvidenceError(
                "exact-H DVC inventory entered a restricted namespace"
            )
        pointer_bytes = _read_regular(
            pointer_path,
            repo_root=snapshot_root,
            context="exact-H snapshot DVC pointer",
        )
        pointer = _parse_dvc_pointer(pointer_bytes, pointer_path)
        destination = snapshot_root / pointer_path.parent / cast(
            str, pointer["path"]
        )
        output_initially_absent = not os.path.lexists(destination)
        if not output_initially_absent:
            raise ClosureE10SourceEvidenceError(
                "exact-H DVC output destination was not initially absent"
            )
        files, payload_bytes = _restore_dvc_cache_object(
            repo_root=repo_root,
            snapshot_root=snapshot_root,
            destination=destination,
            digest=cast(str, pointer["md5"]),
            expected_size=cast(int, pointer["size"]),
        )
        declared_nfiles = cast(int | None, pointer["nfiles"])
        if cast(bool, pointer["is_directory"]):
            if declared_nfiles != files:
                raise ClosureE10SourceEvidenceError(
                    "DVC directory pointer nfiles drifted"
                )
            payload_sha256: str | None = None
        else:
            if declared_nfiles is not None or files != 1:
                raise ClosureE10SourceEvidenceError(
                    "DVC file pointer cardinality drifted"
                )
            restored_payload = _read_regular(
                destination.relative_to(snapshot_root),
                repo_root=snapshot_root,
                context="restored exact-H DVC payload",
                require_nlink_one=False,
            )
            payload_sha256 = _sha256(restored_payload)
        restored_files += files
        restored_bytes += payload_bytes
        records.append(
            {
                "pointer_path": pointer_path.as_posix(),
                "pointer_bytes": len(pointer_bytes),
                "pointer_sha256": _sha256(pointer_bytes),
                "output_path": destination.relative_to(snapshot_root).as_posix(),
                "payload_md5": pointer["md5"],
                "payload_bytes": payload_bytes,
                "payload_file_count": files,
                "directory_output": pointer["is_directory"],
                "declared_nfiles": declared_nfiles,
                "payload_sha256": payload_sha256,
                "output_initially_absent": output_initially_absent,
                "restored_from_local_cache": True,
            }
        )
    return {
        "status": "passed",
        "mode": "all_permitted_exact_h_pointers_offline_local_cache_restore",
        "repository_commit": commit,
        "network_used": False,
        "main_worktree_written": False,
        "inventory_command": command,
        "pointer_count": len(records),
        "restored_file_count": restored_files,
        "restored_bytes": restored_bytes,
        "records": records,
    }


def _required_dvc_restore_evidence(
    snapshot_restore: Mapping[str, Any],
) -> dict[str, Any]:
    """Project the four locked-evaluation restores from the exact-H snapshot."""

    raw_records = snapshot_restore.get("records")
    inventory_command = snapshot_restore.get("inventory_command")
    if not isinstance(raw_records, list) or not isinstance(
        inventory_command, Mapping
    ):
        raise ClosureE10SourceEvidenceError(
            "exact-H snapshot DVC restore is incomplete"
        )
    by_path = {
        record.get("pointer_path"): record
        for record in raw_records
        if isinstance(record, Mapping)
        and isinstance(record.get("pointer_path"), str)
    }
    records: list[dict[str, Any]] = []
    for pointer_path in DVC_RESTORE_POINTERS:
        raw = by_path.get(pointer_path.as_posix())
        if (
            not isinstance(raw, Mapping)
            or raw.get("directory_output") is not False
            or raw.get("declared_nfiles") is not None
            or raw.get("payload_file_count") != 1
            or not isinstance(raw.get("payload_sha256"), str)
            or raw.get("output_initially_absent") is not True
        ):
            raise ClosureE10SourceEvidenceError(
                "required exact-H DVC restore binding drifted"
            )
        records.append(
            {
                "pointer_path": pointer_path.as_posix(),
                "pointer_bytes": raw["pointer_bytes"],
                "pointer_sha256": raw["pointer_sha256"],
                "output_path": pointer_path.with_suffix("").name,
                "payload_bytes": raw["payload_bytes"],
                "payload_md5": raw["payload_md5"],
                "payload_sha256": raw["payload_sha256"],
                "destination_initially_absent_in_exact_h_snapshot": True,
                "restored_into_materialized_exact_h_snapshot": True,
            }
        )
    return {
        "status": "passed",
        "mode": "offline_local_dvc_cache_clean_restore",
        "network_used": False,
        "remote_pull_claimed": False,
        "pointer_count": len(records),
        "records": records,
        "snapshot_inventory_command": copy.deepcopy(dict(inventory_command)),
    }


def _validate_environment_repository_state(
    value: Any, *, repository_commit: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "repository_commit",
        "branch",
        "clean_worktree",
        "refs",
        "builder_source",
    }:
        raise ClosureE10SourceEvidenceError(
            "environment repository-state keys drifted"
        )
    refs = value.get("refs")
    builder = value.get("builder_source")
    if (
        value.get("repository_commit") != repository_commit
        or value.get("branch") != "main"
        or value.get("clean_worktree") is not True
        or not isinstance(refs, Mapping)
        or set(refs) != {"head", "main", "origin_main", "origin_head"}
        or set(refs.values()) != {repository_commit}
        or not isinstance(builder, Mapping)
        or set(builder)
        != {"path", "bytes", "sha256", "physical_equals_h_blob"}
        or builder.get("path") != BUILDER_SOURCE_PATH.as_posix()
        or type(builder.get("bytes")) is not int
        or cast(int, builder["bytes"]) <= 0
        or re.fullmatch(r"[0-9a-f]{64}", str(builder.get("sha256"))) is None
        or builder.get("physical_equals_h_blob") is not True
    ):
        raise ClosureE10SourceEvidenceError(
            "environment repository state drifted"
        )
    return cast(Mapping[str, Any], value)


def _environment_exact_h_commands(
    filesystem_isolation: Mapping[str, Any], *, repository_commit: str
) -> dict[str, Mapping[str, Any]]:
    snapshot = filesystem_isolation.get("exact_h_snapshot")
    tracked_export = (
        snapshot.get("tracked_export") if isinstance(snapshot, Mapping) else None
    )
    tree_verification = (
        tracked_export.get("tracked_tree_verification")
        if isinstance(tracked_export, Mapping)
        else None
    )
    dvc_restore = (
        snapshot.get("dvc_restore") if isinstance(snapshot, Mapping) else None
    )
    probe_results = filesystem_isolation.get("denial_probe_results")
    if probe_results != _expected_denial_probe_results():
        raise ClosureE10SourceEvidenceError(
            "environment filesystem denial probe drifted"
        )
    expected_probe_stdout = _canonical_json(probe_results)
    raw = {
        "filesystem_denial_probe": {
            "argv": [
                ".venv/bin/python",
                "-B",
                "-c",
                ISOLATION_PROBE_CODE,
            ],
            "returncode": 0,
            "stdout_sha256": _sha256(expected_probe_stdout),
            "stderr_sha256": _sha256(b""),
            "stdout_line_count": 1,
            "stderr_line_count": 0,
            "environment_overrides": {
                **ISOLATED_ENVIRONMENT_VALUES,
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            "timeout_seconds": 300,
        },
        "exact_h_git_archive": (
            tracked_export.get("command")
            if isinstance(tracked_export, Mapping)
            else None
        ),
        "exact_h_tree_inventory": (
            tree_verification.get("command")
            if isinstance(tree_verification, Mapping)
            else None
        ),
        "exact_h_dvc_inventory": (
            dvc_restore.get("inventory_command")
            if isinstance(dvc_restore, Mapping)
            else None
        ),
    }
    commands = {
        key: _validate_command_record(value, context=key)
        for key, value in raw.items()
    }
    exclusions = [
        f":(exclude,top){path}" for path in FORBIDDEN_VERIFICATION_PREFIXES
    ]
    archive = cast(list[str], commands["exact_h_git_archive"]["argv"])
    if (
        len(archive) != 7 + len(exclusions)
        or archive[:3] != ["git", "archive", "--format=tar"]
        or re.fullmatch(
            rf"--output=tmp/{re.escape(WORK_PREFIX)}[^/]+/exact_h_snapshot\.tar",
            archive[3],
        )
        is None
        or archive[4:] != [repository_commit, "--", ".", *exclusions]
    ):
        raise ClosureE10SourceEvidenceError(
            "environment exact-H Git archive command drifted"
        )
    expected_commands = {
        "exact_h_tree_inventory": [
            "git",
            "diff-tree",
            "--no-commit-id",
            "--raw",
            "-r",
            "-z",
            EMPTY_GIT_TREE_SHA1,
            repository_commit,
            "--",
            ".",
            *exclusions,
        ],
        "exact_h_dvc_inventory": [
            "git",
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "-z",
            EMPTY_GIT_TREE_SHA1,
            repository_commit,
            "--",
            "data/closure_v1",
            "models.dvc",
            *exclusions,
        ],
    }
    expected_environment = {
        "GIT_OPTIONAL_LOCKS": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    for key, argv in expected_commands.items():
        if commands[key].get("argv") != argv:
            raise ClosureE10SourceEvidenceError(
                f"environment {key} command drifted"
            )
    for key in (
        "exact_h_git_archive",
        "exact_h_tree_inventory",
        "exact_h_dvc_inventory",
    ):
        command = commands[key]
        if command.get("environment_overrides") != expected_environment:
            raise ClosureE10SourceEvidenceError(
                f"environment {key} command environment drifted"
            )
    return commands


def validate_closure_e10_environment_payload(
    value: Any,
    *,
    expected_h_commit: str,
    recovery_attempt: str | None = None,
) -> Mapping[str, Any]:
    """Purely validate the exact H-bound E10 environment source payload."""

    commit = _require_commit(expected_h_commit, context="expected H commit")
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "repository_commit",
        "python",
        "platform",
        "python_implementation",
        "python_executable",
        "dependency_lock_sha256",
        "dependency_lock_bytes",
        "pyproject_sha256",
        "pyproject_bytes",
        "runtime",
        "public_test_database",
        "tool_versions",
        "hardware",
        "repository_pre_generation",
        "repository_post_verification",
        "lock_check",
        "runtime_probe",
        "version_commands",
        "dvc_restore_verification",
        "filesystem_isolation",
        "outcome_safety",
        "generated_at_utc",
    }:
        raise ClosureE10SourceEvidenceError("environment payload keys drifted")
    if (
        value.get("schema_version")
        != "closure_e10_environment_lock_runtime_v1"
        or value.get("repository_commit") != commit
        or value.get("python_executable") != ".venv/bin/python"
    ):
        raise ClosureE10SourceEvidenceError("environment payload identity drifted")
    for key in (
        "python",
        "platform",
        "python_implementation",
        "generated_at_utc",
    ):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ClosureE10SourceEvidenceError(
                f"environment field is absent: {key}"
            )
    try:
        generated = datetime.fromisoformat(cast(str, value["generated_at_utc"]))
    except ValueError as exc:
        raise ClosureE10SourceEvidenceError(
            "environment timestamp drifted"
        ) from exc
    if generated.tzinfo is None:
        raise ClosureE10SourceEvidenceError(
            "environment timestamp is not timezone-aware"
        )
    for digest_key in ("dependency_lock_sha256", "pyproject_sha256"):
        if re.fullmatch(r"[0-9a-f]{64}", str(value.get(digest_key))) is None:
            raise ClosureE10SourceEvidenceError(
                f"environment hash drifted: {digest_key}"
            )
    for bytes_key in ("dependency_lock_bytes", "pyproject_bytes"):
        if type(value.get(bytes_key)) is not int or cast(int, value[bytes_key]) <= 0:
            raise ClosureE10SourceEvidenceError(
                f"environment byte count drifted: {bytes_key}"
            )
    runtime = value.get("runtime")
    torch_runtime = runtime.get("torch") if isinstance(runtime, Mapping) else None
    if (
        not isinstance(runtime, Mapping)
        or not runtime
        or not isinstance(runtime.get("fastapi"), str)
        or not isinstance(torch_runtime, Mapping)
        or type(torch_runtime.get("available")) is not bool
        or not isinstance(value.get("tool_versions"), Mapping)
        or not value["tool_versions"]
        or not all(
            type(key) is str and type(item) is str and key and item
            for key, item in cast(Mapping[Any, Any], value["tool_versions"]).items()
        )
        or not isinstance(value.get("hardware"), Mapping)
        or not value["hardware"]
    ):
        raise ClosureE10SourceEvidenceError(
            "environment runtime/tool/hardware record drifted"
        )
    pre = _validate_environment_repository_state(
        value.get("repository_pre_generation"), repository_commit=commit
    )
    post = _validate_environment_repository_state(
        value.get("repository_post_verification"), repository_commit=commit
    )
    if dict(pre) != dict(post):
        raise ClosureE10SourceEvidenceError(
            "environment H repository changed during generation"
        )

    lock_check = _validate_command_record(
        value.get("lock_check"), context="environment Poetry lock check"
    )
    runtime_probe = _validate_command_record(
        value.get("runtime_probe"), context="environment runtime probe"
    )
    isolated_environment = {
        **ISOLATED_ENVIRONMENT_VALUES,
        "PYTHONDONTWRITEBYTECODE": "1",
        "CLOSURE_E10_OUTCOME_GUARD": "1",
        "CLOSURE_E10_REPO_ROOT": ".",
    }
    if (
        lock_check.get("argv") != ["poetry", "check", "--lock"]
        or lock_check.get("environment_overrides")
        != {"PYTHONDONTWRITEBYTECODE": "1"}
        or runtime_probe.get("argv")
        != [
            ".venv/bin/python",
            "-B",
            BUILDER_SOURCE_PATH.as_posix(),
            "--runtime-probe",
        ]
        or runtime_probe.get("environment_overrides") != isolated_environment
    ):
        raise ClosureE10SourceEvidenceError(
            "environment command binding drifted"
        )
    versions = value.get("version_commands")
    expected_versions = {
        "python_version": [".venv/bin/python", "--version"],
        "poetry_version": ["poetry", "--version"],
        "pytest_version": ["poetry", "run", "pytest", "--version"],
        "dvc_version": [".venv/bin/dvc", "--version"],
        "git_version": ["git", "--version"],
    }
    if not isinstance(versions, Mapping) or set(versions) != set(
        expected_versions
    ):
        raise ClosureE10SourceEvidenceError(
            "environment version-command scope drifted"
        )
    for key, argv in expected_versions.items():
        command = _validate_command_record(versions[key], context=key)
        if (
            command.get("argv") != argv
            or command.get("environment_overrides")
            != {"PYTHONDONTWRITEBYTECODE": "1"}
        ):
            raise ClosureE10SourceEvidenceError(
                f"environment version command drifted: {key}"
            )

    filesystem_isolation = value.get("filesystem_isolation")
    if not isinstance(filesystem_isolation, Mapping):
        raise ClosureE10SourceEvidenceError(
            "environment filesystem isolation is absent"
        )
    exact_h_commands = _environment_exact_h_commands(
        filesystem_isolation, repository_commit=commit
    )
    mode = _require_recovery_attempt(recovery_attempt)
    host_log_pre = filesystem_isolation.get(
        "host_outcome_log_pre_verification"
    )
    if (
        mode is None
        and isinstance(host_log_pre, Mapping)
        and host_log_pre.get("bytes") == RECOVERY_OUTCOME_LOG_BYTES
        and host_log_pre.get("h_blob_sha256") == RECOVERY_OUTCOME_LOG_SHA256
    ):
        mode = RECOVERY_ATTEMPT_1
    validated_isolation = _validate_filesystem_isolation(
        filesystem_isolation,
        repository_commit=commit,
        commands=exact_h_commands,
        recovery_attempt=mode,
    )
    exact_h_snapshot = validated_isolation.get("exact_h_snapshot")
    snapshot_restore = (
        exact_h_snapshot.get("dvc_restore")
        if isinstance(exact_h_snapshot, Mapping)
        else None
    )
    if not isinstance(snapshot_restore, Mapping):
        raise ClosureE10SourceEvidenceError(
            "environment exact-H DVC restore is absent"
        )
    expected_dvc = _required_dvc_restore_evidence(snapshot_restore)
    if value.get("dvc_restore_verification") != expected_dvc:
        raise ClosureE10SourceEvidenceError(
            "environment DVC restore does not match exact-H snapshot"
        )

    database = value.get("public_test_database")
    ownership = (
        database.get("ownership") if isinstance(database, Mapping) else None
    )
    database_name = (
        ownership.get("database_name") if isinstance(ownership, Mapping) else None
    )
    if (
        not isinstance(database, Mapping)
        or set(database)
        != {
            "dialect",
            "test_database_url",
            "formerly_skipped_http_test_required",
            "ownership",
        }
        or database.get("dialect") != "postgresql_asyncpg"
        or re.fullmatch(
            r"redacted_sha256:[0-9a-f]{64}",
            str(database.get("test_database_url")),
        )
        is None
        or database.get("formerly_skipped_http_test_required") is not True
        or not isinstance(ownership, Mapping)
        or set(ownership)
        != {
            "schema_version",
            "host_scope",
            "database_name",
            "database_name_sha256",
            "initially_absent",
            "created_exclusively_by_generator",
            "create_statement",
            "drop_statement",
            "dropped_after_public_suite",
            "absent_after_cleanup",
        }
        or ownership.get("schema_version")
        != "closure_e10_owned_postgresql_fixture_v1"
        or ownership.get("host_scope") != "loopback_only"
        or not isinstance(database_name, str)
        or re.fullmatch(r"closure_e10_[0-9a-f]{20}", database_name) is None
        or ownership.get("database_name_sha256")
        != _sha256(cast(str, database_name).encode("ascii"))
        or ownership.get("initially_absent") is not True
        or ownership.get("created_exclusively_by_generator") is not True
        or ownership.get("create_statement")
        != f'CREATE DATABASE "{database_name}"'
        or ownership.get("drop_statement")
        != f'DROP DATABASE "{database_name}"'
        or ownership.get("dropped_after_public_suite") is not True
        or ownership.get("absent_after_cleanup") is not True
    ):
        raise ClosureE10SourceEvidenceError(
            "environment public PostgreSQL evidence drifted"
        )
    expected_safety = {
        **E2E_FIXTURE_CONTRACT,
        "guard_enabled": True,
        **_public_suite_contract_record(),
        "pre_e0u_excluded_test_bases": list(
            PUBLIC_PRE_E0U_EXCLUDED_TEST_BASES
        ),
        "pre_e0u_excluded_test_nodes": list(PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES),
        "pre_e0u_exclusion_reason": PUBLIC_PRE_E0U_EXCLUSION_REASON,
        "user_prohibited_git_commit_test_nodes": list(
            PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES
        ),
        "user_prohibited_git_commit_exclusion_reason": (
            PUBLIC_USER_PROHIBITED_GIT_COMMIT_EXCLUSION_REASON
        ),
        "target_paths_opened": False,
        "outcome_paths_opened": False,
    }
    if value.get("outcome_safety") != expected_safety:
        raise ClosureE10SourceEvidenceError(
            "environment outcome-safety binding drifted"
        )
    _canonical_json(dict(value))
    return copy.deepcopy(dict(value))


def _snapshot_inventory(snapshot_root: Path) -> dict[str, Any]:
    """Hash and identity-bind every entry in the private exact-H snapshot."""

    root_metadata = snapshot_root.lstat()
    if snapshot_root.is_symlink() or not stat.S_ISDIR(root_metadata.st_mode):
        raise ClosureE10SourceEvidenceError("exact-H snapshot root is unsafe")
    records: list[dict[str, Any]] = []
    for current, directory_names, file_names in os.walk(
        snapshot_root, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        directory_names.sort()
        file_names.sort()
        safe_directories: list[str] = []
        for name in directory_names:
            candidate = current_path / name
            relative = candidate.relative_to(snapshot_root)
            metadata = candidate.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                target = os.readlink(candidate)
                records.append(
                    {
                        "path": relative.as_posix(),
                        "entry_type": "symlink",
                        "mode": format(stat.S_IMODE(metadata.st_mode), "03o"),
                        "device": metadata.st_dev,
                        "inode": metadata.st_ino,
                        "nlink": metadata.st_nlink,
                        "mtime_ns": metadata.st_mtime_ns,
                        "ctime_ns": metadata.st_ctime_ns,
                        "target_sha256": _sha256(os.fsencode(target)),
                    }
                )
                continue
            if not stat.S_ISDIR(metadata.st_mode):
                raise ClosureE10SourceEvidenceError(
                    "exact-H snapshot contains a special directory entry"
                )
            safe_directories.append(name)
            records.append(
                {
                    "path": relative.as_posix(),
                    "entry_type": "directory",
                    "mode": format(stat.S_IMODE(metadata.st_mode), "03o"),
                    "device": metadata.st_dev,
                    "inode": metadata.st_ino,
                    "nlink": metadata.st_nlink,
                    "mtime_ns": metadata.st_mtime_ns,
                    "ctime_ns": metadata.st_ctime_ns,
                }
            )
        directory_names[:] = safe_directories
        for name in file_names:
            candidate = current_path / name
            relative = candidate.relative_to(snapshot_root)
            metadata = candidate.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                target = os.readlink(candidate)
                records.append(
                    {
                        "path": relative.as_posix(),
                        "entry_type": "symlink",
                        "mode": format(stat.S_IMODE(metadata.st_mode), "03o"),
                        "device": metadata.st_dev,
                        "inode": metadata.st_ino,
                        "nlink": metadata.st_nlink,
                        "mtime_ns": metadata.st_mtime_ns,
                        "ctime_ns": metadata.st_ctime_ns,
                        "target_sha256": _sha256(os.fsencode(target)),
                    }
                )
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise ClosureE10SourceEvidenceError(
                    "exact-H snapshot contains a special file"
                )
            payload = _read_regular(
                relative,
                repo_root=snapshot_root,
                context="exact-H snapshot inventory",
                require_nlink_one=False,
            )
            records.append(
                {
                    "path": relative.as_posix(),
                    "entry_type": "regular_file",
                    "mode": format(stat.S_IMODE(metadata.st_mode), "03o"),
                    "device": metadata.st_dev,
                    "inode": metadata.st_ino,
                    "nlink": metadata.st_nlink,
                    "bytes": len(payload),
                    "mtime_ns": metadata.st_mtime_ns,
                    "ctime_ns": metadata.st_ctime_ns,
                    "sha256": _sha256(payload),
                }
            )
    records.sort(key=lambda item: cast(str, item["path"]))
    return {
        "schema_version": "closure_e10_exact_h_snapshot_inventory_v1",
        "root_identity": {
            "device": root_metadata.st_dev,
            "inode": root_metadata.st_ino,
            "mode": format(stat.S_IMODE(root_metadata.st_mode), "03o"),
            "nlink": root_metadata.st_nlink,
            "mtime_ns": root_metadata.st_mtime_ns,
            "ctime_ns": root_metadata.st_ctime_ns,
        },
        "entry_count": len(records),
        "records_sha256": _sha256(_canonical_json(records)),
        "records": records,
    }


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _verify_snapshot_tracked_h(
    *, repo_root: Path, snapshot_root: Path, repository_commit: str
) -> dict[str, Any]:
    """Require every non-restricted H blob to exist byte-exactly in export."""

    commit = _require_commit(repository_commit)
    exclusions = tuple(
        f":(exclude,top){path}" for path in FORBIDDEN_VERIFICATION_PREFIXES
    )
    command, stdout, stderr = _run(
        (
            "git",
            "diff-tree",
            "--no-commit-id",
            "--raw",
            "-r",
            "-z",
            EMPTY_GIT_TREE_SHA1,
            commit,
            "--",
            ".",
            *exclusions,
        ),
        repo_root=repo_root,
        environment={"GIT_OPTIONAL_LOCKS": "0"},
    )
    if stderr or not stdout.endswith("\0"):
        raise ClosureE10SourceEvidenceError(
            "exact-H tracked tree inventory is invalid"
        )
    fields = stdout[:-1].split("\0")
    if len(fields) % 2:
        raise ClosureE10SourceEvidenceError(
            "exact-H tracked tree raw record cardinality drifted"
        )
    entries = list(zip(fields[::2], fields[1::2], strict=True))
    previous_path: str | None = None
    for header, path_text in entries:
        match = re.fullmatch(
            r":000000 (100644|100755|120000) "
            r"0000000000000000000000000000000000000000 ([0-9a-f]{40}) A",
            header,
        )
        if match is None:
            raise ClosureE10SourceEvidenceError(
                "exact-H tracked tree contains an unsupported entry"
            )
        mode, blob_sha1 = match.groups()
        relative = Path(path_text)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != path_text
            or previous_path is not None
            and path_text <= previous_path
            or any(
                path_text == prefix
                or path_text.startswith(prefix.rstrip("/") + "/")
                for prefix in FORBIDDEN_VERIFICATION_PREFIXES
            )
        ):
            raise ClosureE10SourceEvidenceError(
                "exact-H tracked tree path/order drifted"
            )
        previous_path = path_text
        candidate = snapshot_root / relative
        try:
            metadata = candidate.lstat()
        except OSError as exc:
            raise ClosureE10SourceEvidenceError(
                "Git archive omitted an exact-H tracked path"
            ) from exc
        if mode == "120000":
            if not stat.S_ISLNK(metadata.st_mode):
                raise ClosureE10SourceEvidenceError(
                    "Git archive symlink type drifted"
                )
            payload = os.fsencode(os.readlink(candidate))
        else:
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode)
                != (0o755 if mode == "100755" else 0o644)
            ):
                raise ClosureE10SourceEvidenceError(
                    "Git archive regular-file mode drifted"
                )
            payload = _read_regular(
                relative,
                repo_root=snapshot_root,
                context="exact-H tracked snapshot blob",
                require_nlink_one=False,
            )
        if _git_blob_sha1(payload) != blob_sha1:
            raise ClosureE10SourceEvidenceError(
                "Git archive tracked blob differs from exact H"
            )
    return {
        "command": command,
        "entry_count": len(entries),
        "listing_sha256": _sha256(stdout.encode("utf-8")),
        "all_nonrestricted_h_paths_and_blobs_exact": True,
    }


def _materialize_exact_h_snapshot(
    *, repo_root: Path, work_directory: Path, repository_commit: str
) -> tuple[Path, dict[str, Any]]:
    """Export tracked H, restore H-bound DVC inputs, and inventory all bytes."""

    commit = _require_commit(repository_commit)
    try:
        work_relative = work_directory.relative_to(repo_root)
    except ValueError as exc:
        raise ClosureE10SourceEvidenceError(
            "exact-H snapshot work directory escaped repository"
        ) from exc
    archive_relative = work_relative / "exact_h_snapshot.tar"
    archive_path = repo_root / archive_relative
    snapshot_root = work_directory / "exact_h_snapshot"
    if os.path.lexists(archive_path) or os.path.lexists(snapshot_root):
        raise ClosureE10SourceEvidenceError("exact-H snapshot namespace is not pristine")
    exclusions = tuple(
        f":(exclude,top){path}" for path in FORBIDDEN_VERIFICATION_PREFIXES
    )
    archive_command, _, archive_stderr = _run(
        (
            "git",
            "archive",
            "--format=tar",
            f"--output={archive_relative.as_posix()}",
            commit,
            "--",
            ".",
            *exclusions,
        ),
        repo_root=repo_root,
        environment={"GIT_OPTIONAL_LOCKS": "0"},
    )
    if archive_stderr:
        raise ClosureE10SourceEvidenceError("exact-H Git archive emitted stderr")
    archive_bytes = _read_regular(
        archive_relative,
        repo_root=repo_root,
        context="exact-H Git archive",
    )
    snapshot_root.mkdir(mode=0o700)
    try:
        with tarfile.open(archive_path, mode="r:") as archive:
            for member in archive.getmembers():
                relative = Path(member.name.removeprefix("./"))
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or member.ischr()
                    or member.isblk()
                    or member.isfifo()
                    or any(
                        relative.as_posix() == prefix
                        or relative.as_posix().startswith(
                            prefix.rstrip("/") + "/"
                        )
                        for prefix in FORBIDDEN_VERIFICATION_PREFIXES
                    )
                ):
                    raise ClosureE10SourceEvidenceError(
                        "exact-H Git archive contains an unsafe entry"
                    )
            archive.extractall(snapshot_root, filter="data")
    except (OSError, tarfile.TarError) as exc:
        raise ClosureE10SourceEvidenceError(
            "exact-H Git archive cannot be extracted"
        ) from exc
    tracked_tree = _verify_snapshot_tracked_h(
        repo_root=repo_root,
        snapshot_root=snapshot_root,
        repository_commit=commit,
    )
    archive_path.unlink()
    for directory in (
        Path(".git"),
        Path(".venv"),
        Path("tmp"),
        Path("data/targets"),
        OUTCOME_ACCESS_LOG_PATH.parent,
        Path("private"),
    ):
        _ensure_snapshot_directory(snapshot_root, directory)
    for relative in (OUTCOME_ACCESS_LOG_PATH, Path("private/FULL.md")):
        destination = snapshot_root / relative
        if os.path.lexists(destination):
            raise ClosureE10SourceEvidenceError(
                "restricted placeholder unexpectedly exists in Git archive"
            )
        _write_exclusive(destination, b"")
    dvc_restore = _restore_snapshot_dvc_inputs(
        repo_root=repo_root,
        snapshot_root=snapshot_root,
        repository_commit=commit,
    )
    inventory = _snapshot_inventory(snapshot_root)
    return snapshot_root, {
        "schema_version": "closure_e10_materialized_exact_h_snapshot_v1",
        "repository_commit": commit,
        "tracked_export": {
            "command": archive_command,
            "archive_bytes": len(archive_bytes),
            "archive_sha256": _sha256(archive_bytes),
            "restricted_pathspec_exclusions": list(
                FORBIDDEN_VERIFICATION_PREFIXES
            ),
            "tracked_tree_verification": tracked_tree,
        },
        "dvc_restore": dvc_restore,
        "pre_execution_inventory": inventory,
        "post_execution_inventory": copy.deepcopy(inventory),
        "source_worktree_written": False,
        "network_used": False,
    }


def _command_markdown(argv: Sequence[str]) -> str:
    return " ".join(f"`{part}`" for part in argv)


def _build_test_report(
    *,
    commit: str,
    command: Sequence[str],
    totals: Mapping[str, int],
    skip_ledger: Sequence[Mapping[str, Any]],
    raw_junit_sha256: str,
    bound_junit_sha256: str,
) -> bytes:
    target_dependent_skip_count = sum(
        record.get("classification")
        == "pre_e0u_repository_target_test_excluded"
        for record in skip_ledger
    )
    prohibited_git_skip_count = sum(
        record.get("classification") == "user_prohibited_git_commit_fixture"
        for record in skip_ledger
    )
    lines = [
        "# Closure V1 public test evidence",
        "",
        f"- Repository commit (H): `{commit}`",
        f"- Suite kind: `{PUBLIC_SUITE_KIND}`",
        f"- Positive selector count: `{len(PUBLIC_TEST_SELECTORS)}`",
        f"- Positive selector SHA-256: `{PUBLIC_TEST_SELECTOR_SHA256}`",
        f"- Collected node-id SHA-256: `{PUBLIC_TEST_NODEIDS_SHA256}`",
        f"- Exact suite command: {_command_markdown(command)}",
        "- Exit status: `0`",
        f"- Tests: `{totals['tests']}`",
        f"- Passed: `{totals['tests'] - totals['skipped']}`",
        "- Failures: `0`",
        "- Errors: `0`",
        f"- Skips: `{totals['skipped']}`",
        "- Critical skips: `0`",
        f"- Pre-E0-U target-dependent skips: `{target_dependent_skip_count}` "
        f"collected cases across `{len(PUBLIC_PRE_E0U_EXCLUDED_TEST_BASES)}` "
        "sealed test bases.",
        f"- User-prohibited Git-commit fixture skips: `{prohibited_git_skip_count}` "
        "collected cases from an exact sealed registry.",
        "- Former `TEST_DATABASE_URL` HTTP skip: resolved with an explicitly configured PostgreSQL test database.",
        "- Repository-wide pytest discovery: not run; the exact positive Phase 3/API inventory above is the sealed claim.",
        "- Target/outcome guard: enabled via OS filesystem denial plus Python audit hook; no Closure target or outcome path opened.",
        "- Private context guard: enabled; `private/FULL.md` was not opened.",
        f"- Raw JUnit SHA-256: `{raw_junit_sha256}`",
        f"- H-bound JUnit SHA-256: `{bound_junit_sha256}`",
        "",
        "## Skip ledger",
        "",
    ]
    if not skip_ledger:
        lines.append("No tests were skipped.")
    else:
        for record in skip_ledger:
            lines.append(
                "- `{}::{}` — {} (`{}`; justified).".format(
                    record["classname"],
                    record["name"],
                    record["reason"].replace("\n", " "),
                    record["classification"],
                )
            )
    lines.extend(
        [
            "",
            "## Positive suite selector registry",
            "",
            *(f"- `{selector}`" for selector in PUBLIC_TEST_SELECTORS),
            "",
            "## Sealed pre-E0-U exclusion registry",
            "",
            *(
                f"- `{nodeid}`"
                for nodeid in PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES
            ),
            "",
            "## User-prohibited Git-commit fixture registry",
            "",
            *(
                f"- `{nodeid}`"
                for nodeid in PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES
            ),
            "",
            "This report is source evidence. The sealed E10 component copies its "
            "content into the final transactional namespace without launching tests.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _build_contract_report(
    *, commit: str, validation: Mapping[str, Any], openapi_sha256: str
) -> bytes:
    documents = cast(Sequence[Mapping[str, Any]], validation["documents"])
    lines = [
        "# Closure V1 OpenAPI contract evidence",
        "",
        f"- Repository commit (H): `{commit}`",
        "- Status: `passed`",
        "- Contract validator: `validate_openapi_against_api_documents_v1`",
        f"- OpenAPI SHA-256: `{openapi_sha256}`",
        f"- OpenAPI paths: `{validation['openapi_path_count']}`",
        f"- OpenAPI operations: `{validation['openapi_operation_count']}`",
        f"- Documented operations checked: `{validation['documented_operation_count']}`",
        "- Missing documented operations: `0`",
        "- Unique operation IDs: `true`",
        "- Exact path parameters: `true`",
        "",
        "## Bound contract documents",
        "",
    ]
    for record in documents:
        lines.append(
            f"- `{record['path']}` — `{record['sha256']}` "
            f"({record['documented_operation_count']} operations)."
        )
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _build_e2e_report(
    *, commit: str, command: Sequence[str], totals: Mapping[str, int]
) -> bytes:
    lines = [
        "# Closure V1 synthetic API end-to-end evidence",
        "",
        f"- Repository commit (H): `{commit}`",
        f"- Exact suite command: {_command_markdown(command)}",
        "- Exit status: `0`",
        f"- Tests: `{totals['tests']}`",
        "- Failures/errors/skips: `0/0/0`",
        "- Workflow status: `passed`",
        "- Fixture: `synthetic_external_non_closure_outcome`.",
        "- Source identity: `external`; no WQP holdout membership.",
        "- Closure targets, future outcomes, outcome access log, and `private/FULL.md`: not opened.",
        "",
        "## Covered flow",
        "",
        "1. Register a synthetic external dataset and execute deterministic fuzzy scoring.",
        "2. Query the resulting prediction and alert surfaces.",
        "3. Execute a bounded current-state counterfactual simulation.",
        "4. List, preview, and summarize persisted run artifacts.",
        "",
        "The simulation is a software workflow check, not field-causal evidence.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _memory_bytes() -> int | None:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError):
        return None
    if type(pages) is not int or type(page_size) is not int:
        return None
    return pages * page_size


def _source_record(
    key: str,
    payload: bytes,
    commit: str,
    *,
    recovery_attempt: str | None = None,
) -> dict[str, Any]:
    formats = {
        "public_tests_xml": "xml",
        "test_report": "markdown",
        "openapi": "json",
        "openapi_contract_report": "markdown",
        "end_to_end_report": "markdown",
        "environment": "json",
    }
    _, source_paths, _ = _source_bundle_layout(recovery_attempt)
    return {
        "key": key,
        "path": source_paths[key].as_posix(),
        "format": formats[key],
        "bytes": len(payload),
        "sha256": _sha256(payload),
        "repository_commit": commit,
        "embedded_repository_commit_verified": True,
    }


def _records_digest(records: Sequence[Mapping[str, Any]]) -> str:
    return _sha256(_canonical_json(list(records)))


def build_closure_e10_source_manifest(
    *,
    repository_commit: str,
    artifacts: Mapping[str, bytes],
    repository_state: Mapping[str, Any],
    commands: Mapping[str, Mapping[str, Any]],
    public_totals: Mapping[str, int],
    public_skip_ledger: Sequence[Mapping[str, Any]],
    e2e_totals: Mapping[str, int],
    contract_validation: Mapping[str, Any],
    dvc_restore: Mapping[str, Any],
    filesystem_isolation: Mapping[str, Any],
    generated_at_utc: str,
    recovery_attempt: str | None = None,
    recovery: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    commit = _require_commit(repository_commit)
    mode = _require_recovery_attempt(recovery_attempt)
    if set(artifacts) != set(SOURCE_EVIDENCE_KEYS):
        raise ClosureE10SourceEvidenceError("source evidence artifact keys are not exact")
    if mode == RECOVERY_ATTEMPT_1 and (
        not isinstance(recovery, Mapping)
        or not isinstance(recovery.get("sealed_inputs"), list)
    ):
        raise ClosureE10SourceEvidenceError(
            "recovery manifest requires its exact attempt-1 record"
        )
    records = [
        _source_record(
            key,
            artifacts[key],
            commit,
            recovery_attempt=mode,
        )
        for key in SOURCE_EVIDENCE_KEYS
    ]
    builder_source = copy.deepcopy(dict(repository_state.get("builder_source", {})))
    manifest = {
        "schema_version": (
            RECOVERY_SCHEMA_VERSION if mode == RECOVERY_ATTEMPT_1 else SCHEMA_VERSION
        ),
        "status": "completed",
        "publication_status": (
            "source_evidence_recovery_written_unpublished"
            if mode == RECOVERY_ATTEMPT_1
            else "source_evidence_written_unpublished"
        ),
        "gate": GATE,
        "repository_commit": commit,
        "generated_at_utc": generated_at_utc,
        "script": builder_source,
        "inputs": (
            copy.deepcopy(list(cast(Mapping[str, Any], recovery)["sealed_inputs"]))
            if mode == RECOVERY_ATTEMPT_1
            else []
        ),
        "outputs": copy.deepcopy(records),
        "repository_pre_generation": copy.deepcopy(dict(repository_state)),
        "source_artifact_count": 6,
        "source_artifacts": records,
        "source_artifacts_sha256": _records_digest(records),
        "verification": {
            "commands": copy.deepcopy(dict(commands)),
            "repository_post_verification": copy.deepcopy(dict(repository_state)),
            "public_tests": dict(public_totals),
            "public_skip_ledger": copy.deepcopy(list(public_skip_ledger)),
            "end_to_end_tests": dict(e2e_totals),
            "openapi_contract": copy.deepcopy(dict(contract_validation)),
            "dvc_restore": copy.deepcopy(dict(dvc_restore)),
            "filesystem_isolation": copy.deepcopy(dict(filesystem_isolation)),
        },
        "outcome_safety": {
            **copy.deepcopy(E2E_FIXTURE_CONTRACT),
            "guard_enabled_for_public_suite": True,
            "guard_enabled_for_e2e_suite": True,
            "forbidden_prefixes": list(FORBIDDEN_VERIFICATION_PREFIXES),
            **_public_suite_contract_record(),
            "pre_e0u_excluded_test_bases": list(
                PUBLIC_PRE_E0U_EXCLUDED_TEST_BASES
            ),
            "pre_e0u_excluded_test_nodes": list(
                PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES
            ),
            "pre_e0u_exclusion_reason": PUBLIC_PRE_E0U_EXCLUSION_REASON,
            "user_prohibited_git_commit_test_nodes": list(
                PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES
            ),
            "user_prohibited_git_commit_exclusion_reason": (
                PUBLIC_USER_PROHIBITED_GIT_COMMIT_EXCLUSION_REASON
            ),
            "target_paths_opened": False,
            "outcome_paths_opened": False,
        },
        "publication": {
            "exclusive_no_clobber": True,
            "temporary_files_fsynced": True,
            "directory_entries_fsynced": True,
            "hardlink_publication": True,
            "rollback_owned_inodes_only": True,
            "canonical_cleanup_atomic_capture": (
                "renameat2_noreplace_random_tombstone_fd_verified"
            ),
            "cleanup_concurrency_model": (
                "single_writer_after_atomic_tombstone_capture"
            ),
            "same_uid_tombstone_interference_in_scope": False,
            "manifest_written_last": True,
            "final_e10_namespace_written": False,
            "git_read_verification_performed": True,
            "main_repository_git_mutations_performed": False,
            "temporary_git_metadata_writes_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "dvc_push_performed": False,
        },
    }
    if mode == RECOVERY_ATTEMPT_1:
        if not isinstance(recovery, Mapping):
            raise ClosureE10SourceEvidenceError(
                "recovery manifest requires its exact attempt-1 record"
            )
        manifest["recovery_attempt"] = RECOVERY_ATTEMPT_1
        manifest["recovery"] = copy.deepcopy(dict(recovery))
    elif recovery is not None:
        raise ClosureE10SourceEvidenceError(
            "initial source manifest cannot carry recovery evidence"
        )
    return manifest


def _validate_markdown_binding(payload: bytes, commit: str, *, context: str) -> str:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClosureE10SourceEvidenceError(f"{context} is not UTF-8") from exc
    if not text.endswith("\n") or f"Repository commit (H): `{commit}`" not in text:
        raise ClosureE10SourceEvidenceError(f"{context} is not bound to exact H")
    return text


def _validate_recovery_attempt_1_manifest_record(
    value: Any, *, repository_commit: str
) -> dict[str, Any]:
    expected_keys = {
        "mode",
        "repository_commit",
        "outcome_access_log_state",
        "outcome_access_log_prefix",
        "host_outcome_log_state",
        "attempt_1_failure_receipt",
        "attempt_1_failure_receipt_payload_sha256",
        "inherited_p1_input_count",
        "inherited_p1_inputs",
        "inherited_p1_inputs_sha256",
        "sealed_inputs",
        "sealed_inputs_sha256",
        "p1_inputs_overwritten",
        "target_paths_opened",
        "outcome_paths_opened",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise ClosureE10SourceEvidenceError("recovery manifest record keys drifted")
    prefix = value.get("outcome_access_log_prefix")
    inherited = value.get("inherited_p1_inputs")
    receipt = value.get("attempt_1_failure_receipt")
    sealed_inputs = value.get("sealed_inputs")
    if (
        value.get("mode") != RECOVERY_ATTEMPT_1
        or value.get("repository_commit") != repository_commit
        or value.get("outcome_access_log_state")
        != "present_exact_consumed_attempt_1_unopened_by_e10"
        or prefix
        != {
            "path": OUTCOME_ACCESS_LOG_PATH.as_posix(),
            "bytes": RECOVERY_OUTCOME_LOG_BYTES,
            "sha256": RECOVERY_OUTCOME_LOG_SHA256,
            "source": (
                "exact_h2_git_blob_and_host_lstat_without_host_content_open"
            ),
            "physical_contents_opened": False,
        }
        or value.get("inherited_p1_input_count") != len(RECOVERY_INHERITED_P1_PATHS)
        or not isinstance(inherited, list)
        or len(inherited) != len(RECOVERY_INHERITED_P1_PATHS)
        or not isinstance(receipt, Mapping)
        or not isinstance(sealed_inputs, list)
        or value.get("p1_inputs_overwritten") is not False
        or value.get("target_paths_opened") is not False
        or value.get("outcome_paths_opened") is not False
    ):
        raise ClosureE10SourceEvidenceError("recovery manifest identity drifted")
    if [
        record.get("path") for record in inherited if isinstance(record, Mapping)
    ] != [path.as_posix() for path in RECOVERY_INHERITED_P1_PATHS]:
        raise ClosureE10SourceEvidenceError("recovery inherited P1 paths drifted")
    for record in [*inherited, receipt]:
        if (
            not isinstance(record, Mapping)
            or record.get("repository_commit") != repository_commit
            or type(record.get("bytes")) is not int
            or cast(int, record["bytes"]) <= 0
            or re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", "")))
            is None
            or record.get("physical_equals_h2_git_blob") is not True
            or not isinstance(record.get("git_blob_command"), Mapping)
        ):
            raise ClosureE10SourceEvidenceError(
                "recovery Git-bound input record drifted"
            )
    if (
        receipt.get("path") != ATTEMPT_1_FAILURE_RECEIPT_PATH.as_posix()
        or receipt.get("role") != "closure_e0_u_attempt_1_failure_receipt"
        or receipt.get("bytes") != ATTEMPT_1_FAILURE_RECEIPT_BYTES
        or receipt.get("sha256") != ATTEMPT_1_FAILURE_RECEIPT_SHA256
        or value.get("attempt_1_failure_receipt_payload_sha256")
        != receipt.get("sha256")
        or value.get("inherited_p1_inputs_sha256") != _records_digest(inherited)
    ):
        raise ClosureE10SourceEvidenceError("recovery input hashes drifted")
    host_log_state = value.get("host_outcome_log_state")
    if not isinstance(host_log_state, Mapping):
        raise ClosureE10SourceEvidenceError("recovery host log state is absent")
    expected_log_input = {
        "path": OUTCOME_ACCESS_LOG_PATH.as_posix(),
        "role": "sealed_attempt_1_outcome_log_prefix_from_h2_git_blob",
        "bytes": RECOVERY_OUTCOME_LOG_BYTES,
        "sha256": RECOVERY_OUTCOME_LOG_SHA256,
        "repository_commit": repository_commit,
        "physical_metadata_matches_h2_git_blob_size": True,
        "physical_contents_opened": False,
        "git_blob_command": copy.deepcopy(host_log_state.get("h_blob_command")),
    }
    expected_sealed_inputs = [
        *copy.deepcopy(inherited),
        dict(receipt),
        expected_log_input,
    ]
    if (
        sealed_inputs != expected_sealed_inputs
        or value.get("sealed_inputs_sha256") != _records_digest(sealed_inputs)
    ):
        raise ClosureE10SourceEvidenceError("recovery sealed inputs drifted")
    return copy.deepcopy(dict(value))


def validate_closure_e10_source_payloads(
    *,
    artifacts: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    expected_h_commit: str,
    recovery_attempt: str | None = None,
) -> dict[str, Any]:
    commit = _require_commit(expected_h_commit, context="expected H commit")
    mode = _require_recovery_attempt(recovery_attempt)
    if set(artifacts) != set(SOURCE_EVIDENCE_KEYS):
        raise ClosureE10SourceEvidenceError("source artifact keys are not exact")
    required_manifest_keys = {
        "schema_version",
        "status",
        "publication_status",
        "gate",
        "repository_commit",
        "generated_at_utc",
        "script",
        "inputs",
        "outputs",
        "repository_pre_generation",
        "source_artifact_count",
        "source_artifacts",
        "source_artifacts_sha256",
        "verification",
        "outcome_safety",
        "publication",
    }
    if mode == RECOVERY_ATTEMPT_1:
        required_manifest_keys.update({"recovery_attempt", "recovery"})
    if set(manifest) != required_manifest_keys:
        raise ClosureE10SourceEvidenceError("source manifest keys are not exact")
    if (
        manifest.get("schema_version")
        != (RECOVERY_SCHEMA_VERSION if mode else SCHEMA_VERSION)
        or manifest.get("status") != "completed"
        or manifest.get("publication_status")
        != (
            "source_evidence_recovery_written_unpublished"
            if mode
            else "source_evidence_written_unpublished"
        )
        or manifest.get("gate") != GATE
        or manifest.get("repository_commit") != commit
        or manifest.get("source_artifact_count") != 6
    ):
        raise ClosureE10SourceEvidenceError("source manifest identity drifted")
    try:
        generated = datetime.fromisoformat(str(manifest["generated_at_utc"]))
    except ValueError as exc:
        raise ClosureE10SourceEvidenceError("source manifest timestamp drifted") from exc
    if generated.tzinfo is None:
        raise ClosureE10SourceEvidenceError("source manifest timestamp is not aware")
    repository_state = manifest.get("repository_pre_generation")
    if (
        not isinstance(repository_state, Mapping)
        or repository_state.get("repository_commit") != commit
        or repository_state.get("branch") != "main"
        or repository_state.get("clean_worktree") is not True
        or not isinstance(repository_state.get("refs"), Mapping)
        or set(cast(Mapping[str, Any], repository_state["refs"]).values()) != {commit}
    ):
        raise ClosureE10SourceEvidenceError("pre-generation H repository state drifted")
    builder_source = repository_state.get("builder_source")
    if (
        not isinstance(builder_source, Mapping)
        or builder_source.get("path")
        != "src/experiments/build_closure_e10_source_evidence.py"
        or type(builder_source.get("bytes")) is not int
        or cast(int, builder_source["bytes"]) <= 0
        or not re.fullmatch(r"[0-9a-f]{64}", str(builder_source.get("sha256", "")))
        or builder_source.get("physical_equals_h_blob") is not True
    ):
        raise ClosureE10SourceEvidenceError("H-bound builder source record drifted")
    recovery_record = None
    if mode == RECOVERY_ATTEMPT_1:
        if manifest.get("recovery_attempt") != RECOVERY_ATTEMPT_1:
            raise ClosureE10SourceEvidenceError("source recovery mode drifted")
        recovery_record = _validate_recovery_attempt_1_manifest_record(
            manifest.get("recovery"),
            repository_commit=commit,
        )
    if manifest.get("script") != builder_source or manifest.get("inputs") != (
        recovery_record["sealed_inputs"] if recovery_record is not None else []
    ):
        raise ClosureE10SourceEvidenceError("generic manifest script/inputs drifted")
    records = manifest.get("source_artifacts")
    if not isinstance(records, list) or len(records) != 6:
        raise ClosureE10SourceEvidenceError("source manifest records drifted")
    expected_records = [
        _source_record(
            key,
            artifacts[key],
            commit,
            recovery_attempt=mode,
        )
        for key in SOURCE_EVIDENCE_KEYS
    ]
    if (
        records != expected_records
        or manifest.get("outputs") != expected_records
        or manifest.get("source_artifacts_sha256") != _records_digest(expected_records)
    ):
        raise ClosureE10SourceEvidenceError("source evidence hashes drifted")
    publication = manifest.get("publication")
    if not isinstance(publication, Mapping) or publication != {
        "exclusive_no_clobber": True,
        "temporary_files_fsynced": True,
        "directory_entries_fsynced": True,
        "hardlink_publication": True,
        "rollback_owned_inodes_only": True,
        "canonical_cleanup_atomic_capture": (
            "renameat2_noreplace_random_tombstone_fd_verified"
        ),
        "cleanup_concurrency_model": (
            "single_writer_after_atomic_tombstone_capture"
        ),
        "same_uid_tombstone_interference_in_scope": False,
        "manifest_written_last": True,
        "final_e10_namespace_written": False,
        "git_read_verification_performed": True,
        "main_repository_git_mutations_performed": False,
        "temporary_git_metadata_writes_performed": False,
        "git_commit_performed": False,
        "git_push_performed": False,
        "dvc_push_performed": False,
    }:
        raise ClosureE10SourceEvidenceError("source publication contract drifted")
    safety = manifest.get("outcome_safety")
    suite_contract = _public_suite_contract_record()
    if not isinstance(safety, Mapping) or any(
        safety.get(key) != expected for key, expected in suite_contract.items()
    ):
        raise ClosureE10SourceEvidenceError("source public suite contract drifted")
    if (
        safety.get("fixture_kind")
        != "synthetic_external_non_closure_outcome"
        or safety.get("closure_holdout_member") is not False
        or safety.get("wqp_source_used") is not False
        or safety.get("future_target_used") is not False
        or safety.get("guard_enabled_for_public_suite") is not True
        or safety.get("guard_enabled_for_e2e_suite") is not True
        or safety.get("forbidden_prefixes")
        != list(FORBIDDEN_VERIFICATION_PREFIXES)
        or safety.get("pre_e0u_excluded_test_bases")
        != list(PUBLIC_PRE_E0U_EXCLUDED_TEST_BASES)
        or safety.get("pre_e0u_excluded_test_nodes")
        != list(PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES)
        or safety.get("pre_e0u_exclusion_reason")
        != PUBLIC_PRE_E0U_EXCLUSION_REASON
        or safety.get("user_prohibited_git_commit_test_nodes")
        != list(PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES)
        or safety.get("user_prohibited_git_commit_exclusion_reason")
        != PUBLIC_USER_PROHIBITED_GIT_COMMIT_EXCLUSION_REASON
        or safety.get("target_paths_opened") is not False
        or safety.get("outcome_paths_opened") is not False
        or safety.get("private_full_opened") is not False
    ):
        raise ClosureE10SourceEvidenceError("source outcome-safety record drifted")

    public_totals = _validate_junit_commit(artifacts["public_tests_xml"], commit)
    _, public_skips = _parse_junit(artifacts["public_tests_xml"])
    expected_skip_ledger = _require_public_test_success(
        public_totals, public_skips
    )
    if public_totals["failures"] or public_totals["errors"] or not public_totals["tests"]:
        raise ClosureE10SourceEvidenceError("bound public JUnit is not successful")
    test_markdown = _validate_markdown_binding(
        artifacts["test_report"], commit, context="test report"
    )
    for marker in (
        f"- Suite kind: `{PUBLIC_SUITE_KIND}`",
        f"- Positive selector count: `{len(PUBLIC_TEST_SELECTORS)}`",
        f"- Positive selector SHA-256: `{PUBLIC_TEST_SELECTOR_SHA256}`",
        f"- Collected node-id SHA-256: `{PUBLIC_TEST_NODEIDS_SHA256}`",
        f"- Tests: `{public_totals['tests']}`",
        f"- Passed: `{PUBLIC_PHASE3_EXPECTED_PASS_COUNT}`",
        "- Failures: `0`",
        "- Errors: `0`",
        f"- Skips: `{public_totals['skipped']}`",
        "- Critical skips: `0`",
        "Target/outcome guard: enabled",
        "Private context guard: enabled",
        "Pre-E0-U target-dependent skips:",
        "Repository-wide pytest discovery: not run",
        *(f"`{selector}`" for selector in PUBLIC_TEST_SELECTORS),
        *(f"`{nodeid}`" for nodeid in PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES),
        *(f"`{nodeid}`" for nodeid in PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES),
    ):
        if marker not in test_markdown:
            raise ClosureE10SourceEvidenceError("test report counters drifted")
    openapi = json.loads(artifacts["openapi"].decode("utf-8"))
    if not isinstance(openapi, Mapping):
        raise ClosureE10SourceEvidenceError("OpenAPI is not a mapping")
    binding = openapi.get("x-closure-e10-source-evidence")
    if binding != {
        "evidence_role": "openapi",
        "outcome_paths_opened": False,
        "private_full_opened": False,
        "repository_commit": commit,
    }:
        raise ClosureE10SourceEvidenceError("OpenAPI is not bound to exact H")
    if _pretty_json(dict(openapi)) != artifacts["openapi"]:
        raise ClosureE10SourceEvidenceError("OpenAPI JSON is not canonical")
    contract_markdown = _validate_markdown_binding(
        artifacts["openapi_contract_report"],
        commit,
        context="OpenAPI contract report",
    )
    e2e_markdown = _validate_markdown_binding(
        artifacts["end_to_end_report"], commit, context="end-to-end report"
    )
    if (
        "- Workflow status: `passed`" not in e2e_markdown
        or "- Tests: `3`" not in e2e_markdown
        or "- Failures/errors/skips: `0/0/0`" not in e2e_markdown
        or "synthetic_external_non_closure_outcome" not in e2e_markdown
    ):
        raise ClosureE10SourceEvidenceError("end-to-end report drifted")
    environment = json.loads(artifacts["environment"].decode("utf-8"))
    if not isinstance(environment, Mapping) or environment.get("repository_commit") != commit:
        raise ClosureE10SourceEvidenceError("environment is not bound to exact H")
    environment_safety = environment.get("outcome_safety")
    if not isinstance(environment_safety, Mapping) or any(
        environment_safety.get(key) != expected
        for key, expected in _public_suite_contract_record().items()
    ):
        raise ClosureE10SourceEvidenceError(
            "environment public suite contract drifted"
        )
    for required in ("python", "platform", "dependency_lock_sha256"):
        if not isinstance(environment.get(required), str) or not environment[required]:
            raise ClosureE10SourceEvidenceError(f"environment field is absent: {required}")
    if (
        environment.get("schema_version")
        != "closure_e10_environment_lock_runtime_v1"
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(environment.get("dependency_lock_sha256", ""))
        )
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(environment.get("pyproject_sha256", ""))
        )
        or environment.get("repository_pre_generation") != repository_state
        or environment.get("repository_post_verification") != repository_state
        or cast(Mapping[str, Any], environment_safety).get(
            "target_paths_opened"
        )
        is not False
        or cast(Mapping[str, Any], environment_safety).get(
            "outcome_paths_opened"
        )
        is not False
        or cast(Mapping[str, Any], environment_safety).get(
            "private_full_opened"
        )
        is not False
        or cast(Mapping[str, Any], environment_safety).get(
            "pre_e0u_excluded_test_bases"
        )
        != list(PUBLIC_PRE_E0U_EXCLUDED_TEST_BASES)
        or cast(Mapping[str, Any], environment_safety).get(
            "pre_e0u_excluded_test_nodes"
        )
        != list(PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES)
        or cast(Mapping[str, Any], environment_safety).get(
            "pre_e0u_exclusion_reason"
        )
        != PUBLIC_PRE_E0U_EXCLUSION_REASON
        or cast(Mapping[str, Any], environment_safety).get(
            "user_prohibited_git_commit_test_nodes"
        )
        != list(PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES)
        or cast(Mapping[str, Any], environment_safety).get(
            "user_prohibited_git_commit_exclusion_reason"
        )
        != PUBLIC_USER_PROHIBITED_GIT_COMMIT_EXCLUSION_REASON
        or _pretty_json(dict(environment)) != artifacts["environment"]
    ):
        raise ClosureE10SourceEvidenceError("environment lock/runtime record drifted")
    verification = manifest.get("verification")
    if not isinstance(verification, Mapping) or set(verification) != {
        "commands",
        "repository_post_verification",
        "public_tests",
        "public_skip_ledger",
        "end_to_end_tests",
        "openapi_contract",
        "dvc_restore",
        "filesystem_isolation",
    }:
        raise ClosureE10SourceEvidenceError("source verification record drifted")
    if verification.get("public_tests") != public_totals:
        raise ClosureE10SourceEvidenceError("public test totals drifted")
    if verification.get("public_skip_ledger") != expected_skip_ledger:
        raise ClosureE10SourceEvidenceError("public test skip ledger drifted")
    if verification.get("repository_post_verification") != repository_state:
        raise ClosureE10SourceEvidenceError(
            "post-verification H repository state drifted"
        )
    commands = _validate_exact_commands(
        verification.get("commands"), repository_commit=commit
    )
    expected_public_command_line = (
        "- Exact suite command: "
        + _command_markdown(cast(Sequence[str], commands["public_tests"]["argv"]))
    )
    expected_e2e_command_line = (
        "- Exact suite command: "
        + _command_markdown(cast(Sequence[str], commands["end_to_end"]["argv"]))
    )
    if (
        expected_public_command_line not in test_markdown.splitlines()
        or (
            f"- H-bound JUnit SHA-256: `{_sha256(artifacts['public_tests_xml'])}`"
        )
        not in test_markdown.splitlines()
        or expected_e2e_command_line not in e2e_markdown.splitlines()
    ):
        raise ClosureE10SourceEvidenceError(
            "source reports do not bind their exact commands/payloads"
        )
    filesystem_isolation = _validate_filesystem_isolation(
        verification.get("filesystem_isolation"),
        repository_commit=commit,
        commands=commands,
        recovery_attempt=mode,
    )
    if recovery_record is not None and recovery_record.get(
        "host_outcome_log_state"
    ) != filesystem_isolation.get("host_outcome_log_pre_verification"):
        raise ClosureE10SourceEvidenceError(
            "recovery host outcome-log binding drifted"
        )
    if environment.get("filesystem_isolation") != filesystem_isolation:
        raise ClosureE10SourceEvidenceError(
            "environment filesystem-isolation evidence drifted"
        )
    validated_environment = validate_closure_e10_environment_payload(
        environment,
        expected_h_commit=commit,
        recovery_attempt=mode,
    )
    if dict(validated_environment) != dict(environment):
        raise ClosureE10SourceEvidenceError(
            "environment pure-validator projection drifted"
        )
    e2e_totals = verification.get("end_to_end_tests")
    if not isinstance(e2e_totals, Mapping) or e2e_totals != {
        "errors": 0,
        "failures": 0,
        "skipped": 0,
        "tests": 3,
    }:
        raise ClosureE10SourceEvidenceError("end-to-end totals drifted")
    dvc = verification.get("dvc_restore")
    exact_h_snapshot = filesystem_isolation.get("exact_h_snapshot")
    exact_h_snapshot_restore = (
        exact_h_snapshot.get("dvc_restore")
        if isinstance(exact_h_snapshot, Mapping)
        else None
    )
    if not isinstance(exact_h_snapshot_restore, Mapping):
        raise ClosureE10SourceEvidenceError(
            "exact-H snapshot DVC restore evidence is absent"
        )
    expected_dvc = _required_dvc_restore_evidence(exact_h_snapshot_restore)
    if (
        not isinstance(dvc, Mapping)
        or dvc.get("status") != "passed"
        or dvc.get("mode") != "offline_local_dvc_cache_clean_restore"
        or dvc.get("network_used") is not False
        or dvc.get("remote_pull_claimed") is not False
        or dvc.get("pointer_count") != len(DVC_RESTORE_POINTERS)
        or dvc.get("snapshot_inventory_command")
        != commands["exact_h_dvc_inventory"]
        or not isinstance(dvc.get("records"), list)
        or [record.get("pointer_path") for record in dvc["records"]]
        != [path.as_posix() for path in DVC_RESTORE_POINTERS]
        or dvc != expected_dvc
    ):
        raise ClosureE10SourceEvidenceError("DVC restore verification drifted")
    if environment.get("dvc_restore_verification") != dvc:
        raise ClosureE10SourceEvidenceError("environment DVC evidence drifted")
    if environment.get("lock_check") != commands["poetry_lock_check"]:
        raise ClosureE10SourceEvidenceError("environment lock command drifted")
    if environment.get("runtime_probe") != commands["runtime_probe"]:
        raise ClosureE10SourceEvidenceError("environment runtime command drifted")
    database = environment.get("public_test_database")
    ownership = (
        database.get("ownership") if isinstance(database, Mapping) else None
    )
    database_name = (
        ownership.get("database_name") if isinstance(ownership, Mapping) else None
    )
    if (
        not isinstance(database, Mapping)
        or set(database)
        != {
            "dialect",
            "test_database_url",
            "formerly_skipped_http_test_required",
            "ownership",
        }
        or database.get("dialect") != "postgresql_asyncpg"
        or database.get("test_database_url")
        != cast(Mapping[str, Any], commands["public_tests"]["environment_overrides"])[
            "TEST_DATABASE_URL"
        ]
        or database.get("formerly_skipped_http_test_required") is not True
        or not isinstance(ownership, Mapping)
        or set(ownership)
        != {
            "schema_version",
            "host_scope",
            "database_name",
            "database_name_sha256",
            "initially_absent",
            "created_exclusively_by_generator",
            "create_statement",
            "drop_statement",
            "dropped_after_public_suite",
            "absent_after_cleanup",
        }
        or ownership.get("schema_version")
        != "closure_e10_owned_postgresql_fixture_v1"
        or ownership.get("host_scope") != "loopback_only"
        or not isinstance(database_name, str)
        or not re.fullmatch(r"closure_e10_[0-9a-f]{20}", database_name)
        or ownership.get("database_name_sha256")
        != _sha256(cast(str, database_name).encode("ascii"))
        or ownership.get("initially_absent") is not True
        or ownership.get("created_exclusively_by_generator") is not True
        or ownership.get("create_statement")
        != f'CREATE DATABASE "{database_name}"'
        or ownership.get("drop_statement")
        != f'DROP DATABASE "{database_name}"'
        or ownership.get("dropped_after_public_suite") is not True
        or ownership.get("absent_after_cleanup") is not True
    ):
        raise ClosureE10SourceEvidenceError("public test database evidence drifted")
    if environment.get("version_commands") != {
        key: commands[key]
        for key in (
            "python_version",
            "poetry_version",
            "pytest_version",
            "dvc_version",
            "git_version",
        )
    }:
        raise ClosureE10SourceEvidenceError("environment version commands drifted")
    contract = verification.get("openapi_contract")
    if (
        not isinstance(contract, Mapping)
        or contract.get("valid") is not True
        or contract.get("missing_documented_operations") != []
        or contract.get("operation_ids_unique") is not True
        or contract.get("path_parameters_exact") is not True
        or type(contract.get("openapi_path_count")) is not int
        or contract.get("openapi_path_count") != len(cast(Mapping[str, Any], openapi["paths"]))
        or not isinstance(contract.get("documents"), list)
        or [record.get("path") for record in contract["documents"]]
        != [path.as_posix() for path in DOCUMENTED_API_PATHS]
    ):
        raise ClosureE10SourceEvidenceError("OpenAPI contract evidence drifted")
    for marker in (
        "- Status: `passed`",
        f"- OpenAPI paths: `{contract['openapi_path_count']}`",
        "- Missing documented operations: `0`",
        "- Unique operation IDs: `true`",
        "- Exact path parameters: `true`",
    ):
        if marker not in contract_markdown:
            raise ClosureE10SourceEvidenceError("OpenAPI contract report drifted")
    return {
        "public_tests_xml": artifacts["public_tests_xml"],
        "test_report": {
            "status": "passed",
            "test_count": public_totals["tests"],
            "failure_count": 0,
            "error_count": 0,
            "skipped_count": public_totals["skipped"],
            "critical_skips_justified": True,
            "markdown": test_markdown,
        },
        "openapi": copy.deepcopy(dict(openapi)),
        "openapi_contract_report": {
            "status": "passed",
            "valid": True,
            "markdown": contract_markdown,
        },
        "end_to_end_report": {
            "status": "passed",
            "workflow_successful": True,
            "markdown": e2e_markdown,
        },
        "environment": copy.deepcopy(dict(environment)),
    }


def _ensure_real_directory(path: Path, *, parent: Path, create: bool = False) -> None:
    if create and not os.path.lexists(path):
        path.mkdir(mode=0o700)
    metadata = path.lstat()
    if path.parent != parent or path.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise ClosureE10SourceEvidenceError(f"unsafe directory: {path}")


def _require_real_directory_chain(repo_root: Path, directory: Path) -> None:
    root = repo_root.resolve(strict=True)
    try:
        parts = directory.relative_to(root).parts
    except ValueError as exc:
        raise ClosureE10SourceEvidenceError("directory escaped repository") from exc
    current = root
    root_meta = current.lstat()
    if current.is_symlink() or not stat.S_ISDIR(root_meta.st_mode):
        raise ClosureE10SourceEvidenceError("repository root is not a real directory")
    for part in parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ClosureE10SourceEvidenceError(
                f"required directory is absent: {current}"
            ) from exc
        if current.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
            raise ClosureE10SourceEvidenceError(
                f"directory chain contains a non-directory/symlink: {current}"
            )


def _write_exclusive(path: Path, payload: bytes) -> tuple[int, int]:
    parent_meta = path.parent.lstat()
    if path.parent.is_symlink() or not stat.S_ISDIR(parent_meta.st_mode):
        raise ClosureE10SourceEvidenceError("temporary evidence parent is unsafe")
    parent_fd = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    fd: int | None = None
    identity: tuple[int, int] | None = None
    try:
        if _metadata_identity(os.fstat(parent_fd)) != _metadata_identity(parent_meta):
            raise ClosureE10SourceEvidenceError("temporary evidence parent changed")
        fd = os.open(
            path.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
        initial = os.fstat(fd)
        identity = (initial.st_dev, initial.st_ino)
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise ClosureE10SourceEvidenceError(
                    "temporary evidence write made no progress"
                )
            offset += written
        os.fsync(fd)
        final = os.fstat(fd)
        named = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(final.st_mode)
            or final.st_nlink != 1
            or final.st_size != len(payload)
            or (final.st_dev, final.st_ino) != identity
            or (named.st_dev, named.st_ino) != identity
            or stat.S_ISLNK(named.st_mode)
        ):
            raise ClosureE10SourceEvidenceError("temporary evidence file is unsafe")
        return identity
    except BaseException:
        if identity is not None:
            _remove_owned_name_atomic(
                parent_fd,
                path.name,
                identity,
                context="temporary evidence rollback",
                missing_is_error=True,
                owned_fd=fd,
            )
        raise
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent_fd)


def _fsync_directory(path: Path) -> None:
    metadata = path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise ClosureE10SourceEvidenceError(
            f"refusing to fsync an unsafe directory: {path}"
        )
    fd = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        observed = os.fstat(fd)
        if (observed.st_dev, observed.st_ino) != (
            metadata.st_dev,
            metadata.st_ino,
        ):
            raise ClosureE10SourceEvidenceError(
                f"directory changed before fsync: {path}"
            )
        os.fsync(fd)
    finally:
        os.close(fd)


def _rename_noreplace_at(
    source_directory_fd: int,
    source_name: str,
    target_directory_fd: int,
    target_name: str,
) -> None:
    """Atomically rename one entry without replacing the destination."""

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise ClosureE10SourceEvidenceError(
            "atomic no-replace cleanup requires renameat2"
        )
    renameat2 = cast(Any, renameat2)
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        source_directory_fd,
        os.fsencode(source_name),
        target_directory_fd,
        os.fsencode(target_name),
        1,  # RENAME_NOREPLACE
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(
            error_number,
            os.strerror(error_number),
            source_name,
            target_name,
        )


def _close_fd_noexcept(fd: int) -> None:
    """Release a descriptor without turning a completed transaction into failure."""

    try:
        os.close(fd)
    except BaseException:
        # Descriptor release has no remaining canonical filesystem effect.  In
        # particular, a synthetic close error after the kernel already closed
        # the FD must not report failure after publication committed.
        pass


def _remove_owned_name_atomic(
    directory_fd: int,
    name: str,
    identity: tuple[int, int],
    *,
    context: str,
    missing_is_error: bool,
    owned_fd: int | None = None,
    expected_directory: bool = False,
) -> None:
    """Retire a canonical name under the sealed single-writer cleanup model.

    ``renameat2(RENAME_NOREPLACE)`` captures the canonical entry into an
    unpredictable tombstone before identity checks.  A foreign entry captured
    at that boundary is restored without clobber.  Once the verified tombstone
    FD is held, deliberate same-UID interference with that random tombstone is
    outside the declared single-writer model; Linux has no compare-and-unlink
    primitive by inode.
    """

    if not name or "/" in name or name in {".", ".."}:
        raise ClosureE10SourceEvidenceError(f"{context} name is unsafe")
    tombstone: str | None = None
    for _ in range(128):
        candidate = f".closure_e10_owned_cleanup_{secrets.token_hex(16)}"
        try:
            _rename_noreplace_at(directory_fd, name, directory_fd, candidate)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                continue
            if exc.errno == errno.ENOENT:
                if missing_is_error:
                    raise ClosureE10SourceEvidenceError(
                        f"{context} owned entry is missing during cleanup"
                    ) from exc
                return
            raise ClosureE10SourceEvidenceError(
                f"{context} atomic cleanup rename failed"
            ) from exc
        tombstone = candidate
        break
    if tombstone is None:
        raise ClosureE10SourceEvidenceError(
            f"{context} could not allocate an exclusive cleanup tombstone"
        )
    os.fsync(directory_fd)

    tombstone_fd: int | None = None
    try:
        tombstone_entry = os.stat(
            tombstone,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        observed_pair = (tombstone_entry.st_dev, tombstone_entry.st_ino)
        entry_type_matches = (
            stat.S_ISDIR(tombstone_entry.st_mode)
            if expected_directory
            else stat.S_ISREG(tombstone_entry.st_mode)
        )
        if (
            observed_pair != identity
            or stat.S_ISLNK(tombstone_entry.st_mode)
            or not entry_type_matches
        ):
            try:
                _rename_noreplace_at(
                    directory_fd,
                    tombstone,
                    directory_fd,
                    name,
                )
                os.fsync(directory_fd)
            except OSError as exc:
                raise ClosureE10SourceEvidenceError(
                    f"{context} foreign replacement was preserved at {tombstone} "
                    "because its original name reappeared"
                ) from exc
            raise ClosureE10SourceEvidenceError(
                f"{context} owned entry was replaced during cleanup; "
                "the foreign entry was restored"
            )
        tombstone_fd = os.open(
            tombstone,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | (
                getattr(os, "O_DIRECTORY", 0)
                if expected_directory
                else 0
            ),
            dir_fd=directory_fd,
        )
        anchored = os.fstat(tombstone_fd)
        anchored_type_matches = (
            stat.S_ISDIR(anchored.st_mode)
            if expected_directory
            else stat.S_ISREG(anchored.st_mode)
        )
        if (
            (anchored.st_dev, anchored.st_ino) != identity
            or not anchored_type_matches
        ):
            raise ClosureE10SourceEvidenceError(
                f"{context} cleanup tombstone changed while opening"
            )
        if owned_fd is not None:
            owned = os.fstat(owned_fd)
            if (owned.st_dev, owned.st_ino) != identity:
                raise ClosureE10SourceEvidenceError(
                    f"{context} retained owned FD identity drifted"
                )
        repeated = os.stat(
            tombstone,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if (
            (repeated.st_dev, repeated.st_ino) != identity
            or stat.S_ISLNK(repeated.st_mode)
        ):
            raise ClosureE10SourceEvidenceError(
                f"{context} cleanup tombstone was replaced"
            )
        if expected_directory:
            if os.listdir(tombstone_fd):
                raise ClosureE10SourceEvidenceError(
                    f"{context} owned cleanup directory is not empty"
                )
            os.rmdir(tombstone, dir_fd=directory_fd)
            os.fsync(directory_fd)
            if os.fstat(tombstone_fd).st_nlink != 0:
                raise ClosureE10SourceEvidenceError(
                    f"{context} owned cleanup did not remove its exact directory"
                )
        else:
            link_count_before_unlink = anchored.st_nlink
            if link_count_before_unlink < 1:
                raise ClosureE10SourceEvidenceError(
                    f"{context} cleanup tombstone has no owned link"
                )
            os.unlink(tombstone, dir_fd=directory_fd)
            os.fsync(directory_fd)
            if os.fstat(tombstone_fd).st_nlink != link_count_before_unlink - 1:
                raise ClosureE10SourceEvidenceError(
                    f"{context} owned cleanup did not remove its exact inode"
                )
    finally:
        if tombstone_fd is not None:
            os.close(tombstone_fd)


def _link_exclusive(source: Path, target: Path) -> tuple[int, int]:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    source_parent_fd = os.open(source.parent, flags)
    target_parent_fd = os.open(target.parent, flags)
    linked_identity: tuple[int, int] | None = None
    try:
        source_meta = os.stat(
            source.name, dir_fd=source_parent_fd, follow_symlinks=False
        )
        if not stat.S_ISREG(source_meta.st_mode) or stat.S_ISLNK(source_meta.st_mode):
            raise ClosureE10SourceEvidenceError("hardlink source is unsafe")
        source_identity = (source_meta.st_dev, source_meta.st_ino)
        try:
            os.stat(target.name, dir_fd=target_parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ClosureE10SourceEvidenceError(f"refusing to clobber {target}")
        os.link(
            source.name,
            target.name,
            src_dir_fd=source_parent_fd,
            dst_dir_fd=target_parent_fd,
            follow_symlinks=False,
        )
        linked_identity = source_identity
        target_meta = os.stat(
            target.name, dir_fd=target_parent_fd, follow_symlinks=False
        )
        repeated_source = os.stat(
            source.name, dir_fd=source_parent_fd, follow_symlinks=False
        )
        if (
            not stat.S_ISREG(target_meta.st_mode)
            or (target_meta.st_dev, target_meta.st_ino) != source_identity
            or (repeated_source.st_dev, repeated_source.st_ino) != source_identity
        ):
            raise ClosureE10SourceEvidenceError(
                "hardlink publication identity drifted"
            )
        os.fsync(target_parent_fd)
        return source_identity
    except BaseException:
        if linked_identity is not None:
            _remove_owned_name_atomic(
                target_parent_fd,
                target.name,
                linked_identity,
                context="hardlink publication rollback",
                missing_is_error=True,
            )
        raise
    finally:
        os.close(source_parent_fd)
        os.close(target_parent_fd)


def _write_exclusive_at(
    directory_fd: int, name: str, payload: bytes
) -> tuple[int, int]:
    if not name or "/" in name or name in {".", ".."}:
        raise ClosureE10SourceEvidenceError("anchored publication name is unsafe")
    fd: int | None = None
    identity: tuple[int, int] | None = None
    try:
        fd = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_fd,
        )
        initial = os.fstat(fd)
        identity = (initial.st_dev, initial.st_ino)
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise ClosureE10SourceEvidenceError(
                    "anchored publication write made no progress"
                )
            offset += written
        os.fsync(fd)
        final = os.fstat(fd)
        named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(final.st_mode)
            or final.st_nlink != 1
            or final.st_size != len(payload)
            or (final.st_dev, final.st_ino) != identity
            or (named.st_dev, named.st_ino) != identity
            or stat.S_ISLNK(named.st_mode)
        ):
            raise ClosureE10SourceEvidenceError(
                "anchored publication file drifted"
            )
        return identity
    except BaseException:
        if identity is not None:
            _remove_owned_name_atomic(
                directory_fd,
                name,
                identity,
                context="anchored publication write rollback",
                missing_is_error=True,
                owned_fd=fd,
            )
        raise
    finally:
        if fd is not None:
            os.close(fd)


def _link_exclusive_at(
    source_directory_fd: int,
    source_name: str,
    target_directory_fd: int,
    target_name: str,
) -> tuple[int, int]:
    if any(
        not name or "/" in name or name in {".", ".."}
        for name in (source_name, target_name)
    ):
        raise ClosureE10SourceEvidenceError("anchored hardlink name is unsafe")
    linked_identity: tuple[int, int] | None = None
    try:
        source_meta = os.stat(
            source_name,
            dir_fd=source_directory_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(source_meta.st_mode)
            or stat.S_ISLNK(source_meta.st_mode)
            or source_meta.st_nlink != 1
        ):
            raise ClosureE10SourceEvidenceError(
                "anchored hardlink source is unsafe"
            )
        source_identity = (source_meta.st_dev, source_meta.st_ino)
        try:
            os.stat(
                target_name,
                dir_fd=target_directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise ClosureE10SourceEvidenceError(
                f"refusing to clobber anchored target {target_name}"
            )
        os.link(
            source_name,
            target_name,
            src_dir_fd=source_directory_fd,
            dst_dir_fd=target_directory_fd,
            follow_symlinks=False,
        )
        linked_identity = source_identity
        target_meta = os.stat(
            target_name,
            dir_fd=target_directory_fd,
            follow_symlinks=False,
        )
        repeated_source = os.stat(
            source_name,
            dir_fd=source_directory_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(target_meta.st_mode)
            or (target_meta.st_dev, target_meta.st_ino) != source_identity
            or (repeated_source.st_dev, repeated_source.st_ino)
            != source_identity
            or target_meta.st_nlink != 2
            or repeated_source.st_nlink != 2
        ):
            raise ClosureE10SourceEvidenceError(
                "anchored hardlink publication identity drifted"
            )
        os.fsync(target_directory_fd)
        return source_identity
    except BaseException:
        if linked_identity is not None:
            _remove_owned_name_atomic(
                target_directory_fd,
                target_name,
                linked_identity,
                context="anchored hardlink publication rollback",
                missing_is_error=True,
            )
        raise


def _unlink_owned_at(
    directory_fd: int, name: str, identity: tuple[int, int]
) -> None:
    _remove_owned_name_atomic(
        directory_fd,
        name,
        identity,
        context=f"anchored publication cleanup for {name}",
        missing_is_error=True,
    )


def _require_directory_entry_identity(
    parent_fd: int,
    name: str,
    directory_fd: int,
    identity: tuple[int, int],
    *,
    context: str,
) -> None:
    entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    anchored = os.fstat(directory_fd)
    if (
        not stat.S_ISDIR(entry.st_mode)
        or stat.S_ISLNK(entry.st_mode)
        or (entry.st_dev, entry.st_ino) != identity
        or (anchored.st_dev, anchored.st_ino) != identity
    ):
        raise ClosureE10SourceEvidenceError(f"{context} directory was replaced")


def _remove_directory_contents_anchored(directory_fd: int) -> None:
    """Remove an owned tree without ever following a replaced child entry."""

    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    for name in os.listdir(directory_fd):
        if not name or "/" in name or name in {".", ".."}:
            raise ClosureE10SourceEvidenceError(
                "owned cleanup encountered an unsafe entry name"
            )
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        identity = (metadata.st_dev, metadata.st_ino)
        if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
            child_fd = os.open(name, flags, dir_fd=directory_fd)
            try:
                child = os.fstat(child_fd)
                if (child.st_dev, child.st_ino) != identity:
                    raise ClosureE10SourceEvidenceError(
                        "owned cleanup directory changed while opening"
                    )
                _remove_directory_contents_anchored(child_fd)
                entry = os.stat(
                    name, dir_fd=directory_fd, follow_symlinks=False
                )
                if (
                    stat.S_ISLNK(entry.st_mode)
                    or not stat.S_ISDIR(entry.st_mode)
                    or (entry.st_dev, entry.st_ino) != identity
                    or (os.fstat(child_fd).st_dev, os.fstat(child_fd).st_ino)
                    != identity
                ):
                    raise ClosureE10SourceEvidenceError(
                        "owned cleanup directory was replaced"
                    )
                _remove_owned_name_atomic(
                    directory_fd,
                    name,
                    identity,
                    context="owned recursive directory cleanup",
                    missing_is_error=True,
                    owned_fd=child_fd,
                    expected_directory=True,
                )
            finally:
                os.close(child_fd)
        else:
            repeated = os.stat(
                name, dir_fd=directory_fd, follow_symlinks=False
            )
            if (repeated.st_dev, repeated.st_ino) != identity:
                raise ClosureE10SourceEvidenceError(
                    "owned cleanup entry was replaced"
                )
            if stat.S_ISLNK(repeated.st_mode) or not stat.S_ISREG(
                repeated.st_mode
            ):
                raise ClosureE10SourceEvidenceError(
                    "owned cleanup entry is not a regular file"
                )
            _remove_owned_name_atomic(
                directory_fd,
                name,
                identity,
                context="owned recursive file cleanup",
                missing_is_error=True,
            )
    os.fsync(directory_fd)


class OwnedGuard:
    """FD-anchored ownership capability for one generation transaction."""

    def __init__(
        self,
        *,
        root_path: Path,
        root_parent_path: Path,
        root_name: str,
        root_parent_fd: int,
        root_fd: int,
        tmp_fd: int,
        guard_fd: int,
        root_parent_identity: tuple[int, ...],
        root_identity: tuple[int, ...],
        tmp_identity: tuple[int, int],
        guard_identity: tuple[int, ...],
        guard_name: str,
    ) -> None:
        self.root_path = root_path
        self.root_parent_path = root_parent_path
        self.root_name = root_name
        self.root_parent_fd = root_parent_fd
        self.root_fd = root_fd
        self.tmp_fd = tmp_fd
        self.guard_fd = guard_fd
        self.root_parent_identity = root_parent_identity
        self.root_identity = root_identity
        self.tmp_identity = tmp_identity
        self.guard_identity = guard_identity
        self.guard_name = guard_name
        self.removed = False
        self.removed_work_names: set[str] = set()
        self.closed = False

    @staticmethod
    def _directory_pair(metadata: os.stat_result) -> tuple[int, int]:
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ClosureE10SourceEvidenceError(
                "owned guard ancestor is not a real directory"
            )
        return metadata.st_dev, metadata.st_ino

    def _require_open(self) -> None:
        if self.closed:
            raise ClosureE10SourceEvidenceError("owned guard is already closed")

    def _require_ancestry_exact(self, *, context: str) -> None:
        self._require_open()
        try:
            parent_fd_meta = os.fstat(self.root_parent_fd)
            root_fd_meta = os.fstat(self.root_fd)
            tmp_fd_meta = os.fstat(self.tmp_fd)
            parent_path_meta = self.root_parent_path.lstat()
            root_entry = os.stat(
                self.root_name,
                dir_fd=self.root_parent_fd,
                follow_symlinks=False,
            )
            tmp_entry = os.stat("tmp", dir_fd=self.root_fd, follow_symlinks=False)
            root_path_meta = self.root_path.lstat()
            tmp_path_meta = (self.root_path / "tmp").lstat()
        except OSError as exc:
            raise ClosureE10SourceEvidenceError(
                f"{context} owned guard ancestry is absent"
            ) from exc
        if (
            _metadata_identity(parent_fd_meta) != self.root_parent_identity
            or _metadata_identity(parent_path_meta) != self.root_parent_identity
            or _metadata_identity(root_fd_meta) != self.root_identity
            or _metadata_identity(root_entry) != self.root_identity
            or _metadata_identity(root_path_meta) != self.root_identity
            or self._directory_pair(tmp_fd_meta) != self.tmp_identity
            or self._directory_pair(tmp_entry) != self.tmp_identity
            or self._directory_pair(tmp_path_meta) != self.tmp_identity
        ):
            raise ClosureE10SourceEvidenceError(
                f"{context} owned guard ancestry was replaced"
            )

    def require_exact(
        self, *, repository_root: Path | None = None, context: str
    ) -> None:
        self._require_ancestry_exact(context=context)
        if repository_root is not None:
            try:
                supplied_root = repository_root.resolve(strict=True)
            except OSError as exc:
                raise ClosureE10SourceEvidenceError(
                    f"{context} repository root is absent"
                ) from exc
            if supplied_root != self.root_path:
                raise ClosureE10SourceEvidenceError(
                    f"{context} repository root differs from owned guard"
                )
        if self.removed:
            raise ClosureE10SourceEvidenceError(
                f"{context} owned guard was already removed"
            )
        try:
            guard_fd_meta = os.fstat(self.guard_fd)
            guard_entry = os.stat(
                self.guard_name,
                dir_fd=self.tmp_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise ClosureE10SourceEvidenceError(
                f"{context} owned guard leaf is absent"
            ) from exc
        if (
            not stat.S_ISREG(guard_fd_meta.st_mode)
            or stat.S_ISLNK(guard_entry.st_mode)
            or not stat.S_ISREG(guard_entry.st_mode)
            or guard_fd_meta.st_nlink != 1
            or guard_entry.st_nlink != 1
            or _metadata_identity(guard_fd_meta) != self.guard_identity
            or _metadata_identity(guard_entry) != self.guard_identity
        ):
            raise ClosureE10SourceEvidenceError(
                f"{context} owned guard leaf was replaced"
            )

    def create_work_directory(self, *, context: str) -> tuple[Path, tuple[int, int]]:
        """Create one private work tree through the retained ``tmp`` FD."""

        self.require_exact(repository_root=self.root_path, context=context)
        flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        for _ in range(128):
            name = f"{WORK_PREFIX}{secrets.token_hex(12)}"
            try:
                os.mkdir(name, mode=0o700, dir_fd=self.tmp_fd)
            except FileExistsError:
                continue
            work_fd: int | None = None
            identity: tuple[int, int] | None = None
            try:
                entry = os.stat(name, dir_fd=self.tmp_fd, follow_symlinks=False)
                identity = (entry.st_dev, entry.st_ino)
                work_fd = os.open(name, flags, dir_fd=self.tmp_fd)
                anchored = os.fstat(work_fd)
                if (
                    stat.S_ISLNK(entry.st_mode)
                    or not stat.S_ISDIR(entry.st_mode)
                    or (anchored.st_dev, anchored.st_ino) != identity
                ):
                    raise ClosureE10SourceEvidenceError(
                        f"{context} owned work directory changed while opening"
                    )
                os.fsync(self.tmp_fd)
                self.require_exact(
                    repository_root=self.root_path,
                    context=f"{context} post-create",
                )
                return self.root_path / "tmp" / name, identity
            except BaseException:
                if work_fd is not None and identity is not None:
                    try:
                        anchored = os.fstat(work_fd)
                        entry = os.stat(
                            name,
                            dir_fd=self.tmp_fd,
                            follow_symlinks=False,
                        )
                        if (
                            stat.S_ISDIR(anchored.st_mode)
                            and not stat.S_ISLNK(entry.st_mode)
                            and stat.S_ISDIR(entry.st_mode)
                            and (anchored.st_dev, anchored.st_ino) == identity
                            and (entry.st_dev, entry.st_ino) == identity
                        ):
                            _remove_directory_contents_anchored(work_fd)
                            _remove_owned_name_atomic(
                                self.tmp_fd,
                                name,
                                identity,
                                context=f"{context} allocation rollback",
                                missing_is_error=True,
                                owned_fd=work_fd,
                                expected_directory=True,
                            )
                    except OSError:
                        pass
                raise
            finally:
                if work_fd is not None:
                    os.close(work_fd)
        raise ClosureE10SourceEvidenceError(
            f"{context} could not allocate an exclusive work directory"
        )

    def unlink_strict(self, *, context: str) -> None:
        """Remove only the anchored guard; path drift is still an error."""

        ancestry_error: BaseException | None = None
        try:
            self._require_ancestry_exact(context=context)
        except BaseException as exc:
            ancestry_error = exc
        self._require_open()
        if self.removed:
            raise ClosureE10SourceEvidenceError(
                f"{context} owned guard is already absent"
            )
        try:
            anchored = os.fstat(self.guard_fd)
            entry = os.stat(
                self.guard_name,
                dir_fd=self.tmp_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise ClosureE10SourceEvidenceError(
                f"{context} owned guard leaf is missing during cleanup"
            ) from exc
        if (
            not stat.S_ISREG(anchored.st_mode)
            or stat.S_ISLNK(entry.st_mode)
            or not stat.S_ISREG(entry.st_mode)
            or _metadata_identity(anchored) != self.guard_identity
            or _metadata_identity(entry) != self.guard_identity
        ):
            raise ClosureE10SourceEvidenceError(
                f"{context} owned guard leaf was replaced during cleanup"
            )
        _remove_owned_name_atomic(
            self.tmp_fd,
            self.guard_name,
            (self.guard_identity[0], self.guard_identity[1]),
            context=f"{context} owned guard",
            missing_is_error=True,
            owned_fd=self.guard_fd,
        )
        self.removed = True
        _close_fd_noexcept(self.guard_fd)
        self.guard_fd = -1
        if ancestry_error is not None:
            raise ClosureE10SourceEvidenceError(
                f"{context} owned guard ancestry changed during cleanup"
            ) from ancestry_error

    def remove_owned_work_directory(
        self, *, name: str, identity: tuple[int, int], context: str
    ) -> None:
        """Remove one exact work tree through the retained tmp descriptor."""

        if (
            not name.startswith(WORK_PREFIX)
            or "/" in name
            or name in {".", ".."}
        ):
            raise ClosureE10SourceEvidenceError(
                f"{context} work-directory name is unsafe"
            )
        ancestry_error: BaseException | None = None
        try:
            self._require_ancestry_exact(context=context)
        except BaseException as exc:
            ancestry_error = exc
        self._require_open()
        flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            entry = os.stat(name, dir_fd=self.tmp_fd, follow_symlinks=False)
            work_fd = os.open(name, flags, dir_fd=self.tmp_fd)
        except OSError as exc:
            raise ClosureE10SourceEvidenceError(
                f"{context} owned work directory is absent"
            ) from exc
        try:
            anchored = os.fstat(work_fd)
            if (
                stat.S_ISLNK(entry.st_mode)
                or not stat.S_ISDIR(entry.st_mode)
                or (entry.st_dev, entry.st_ino) != identity
                or (anchored.st_dev, anchored.st_ino) != identity
            ):
                raise ClosureE10SourceEvidenceError(
                    f"{context} owned work directory was replaced"
                )
            _remove_directory_contents_anchored(work_fd)
            repeated = os.stat(
                name, dir_fd=self.tmp_fd, follow_symlinks=False
            )
            if (
                stat.S_ISLNK(repeated.st_mode)
                or not stat.S_ISDIR(repeated.st_mode)
                or (repeated.st_dev, repeated.st_ino) != identity
                or (os.fstat(work_fd).st_dev, os.fstat(work_fd).st_ino)
                != identity
            ):
                raise ClosureE10SourceEvidenceError(
                    f"{context} owned work directory changed during cleanup"
                )
            try:
                _remove_owned_name_atomic(
                    self.tmp_fd,
                    name,
                    identity,
                    context=context,
                    missing_is_error=True,
                    owned_fd=work_fd,
                    expected_directory=True,
                )
            except BaseException:
                try:
                    os.stat(name, dir_fd=self.tmp_fd, follow_symlinks=False)
                except FileNotFoundError:
                    anchored_after = os.fstat(work_fd)
                    if (
                        (anchored_after.st_dev, anchored_after.st_ino)
                        == identity
                        and anchored_after.st_nlink == 0
                    ):
                        self.removed_work_names.add(name)
                raise
        finally:
            _close_fd_noexcept(work_fd)
        self.removed_work_names.add(name)
        if ancestry_error is not None:
            raise ClosureE10SourceEvidenceError(
                f"{context} owned guard ancestry changed during work cleanup"
            ) from ancestry_error

    def close(self) -> None:
        if self.closed:
            return
        for attribute in ("guard_fd", "tmp_fd", "root_fd", "root_parent_fd"):
            fd = cast(int, getattr(self, attribute))
            if fd >= 0:
                _close_fd_noexcept(fd)
                setattr(self, attribute, -1)
        self.closed = True


class OwnedMaskWorkDirectory:
    """Single-writer lease for the external restricted-mask work tree."""

    def __init__(self, path: Path, identity: tuple[int, int]) -> None:
        self.path = path
        self.identity = identity
        self.removed = False

    def remove(self) -> None:
        if self.removed:
            raise ClosureE10SourceEvidenceError(
                "mask work directory is already removed"
            )
        _safe_remove_mask_work_directory(self.path, self.identity)
        self.removed = True


def _publish_closure_e10_source_bundle_transaction(
    *,
    repo_root: Path,
    work_directory: Path,
    artifacts: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    expected_h_commit: str,
    owned_guard: OwnedGuard,
    recovery_attempt: str | None = None,
) -> dict[str, Any]:
    """Publish six artifacts and then the manifest without replacing any path."""

    owned_guard.require_exact(
        repository_root=repo_root,
        context="source publication preflight",
    )
    root = owned_guard.root_path
    mode = _require_recovery_attempt(recovery_attempt)
    source_directory, source_paths, manifest_path = _source_bundle_layout(mode)
    validate_closure_e10_source_payloads(
        artifacts=artifacts,
        manifest=manifest,
        expected_h_commit=expected_h_commit,
        recovery_attempt=mode,
    )
    expected_recovery_record = (
        cast(Mapping[str, Any], manifest["recovery"])
        if mode == RECOVERY_ATTEMPT_1
        else None
    )
    if mode == RECOVERY_ATTEMPT_1 and _collect_recovery_attempt_1_record(
        root,
        expected_h_commit,
    ) != expected_recovery_record:
        raise ClosureE10SourceEvidenceError(
            "recovery source publication inputs drifted before transaction"
        )
    final_directory = root / source_directory
    if os.path.lexists(final_directory):
        raise ClosureE10SourceEvidenceError("source evidence directory already exists")
    if os.path.lexists(root / FINAL_E10_DIRECTORY):
        raise ClosureE10SourceEvidenceError(
            "final E10 namespace must remain absent during source publication"
        )
    if mode == RECOVERY_ATTEMPT_1:
        publication_log_state = _capture_host_outcome_log_state(
            root,
            expected_h_commit,
            recovery_attempt=mode,
        )
        if publication_log_state != cast(
            Mapping[str, Any], manifest["recovery"]
        ).get("host_outcome_log_state"):
            raise ClosureE10SourceEvidenceError(
                "recovery source publication log binding drifted"
            )
    else:
        outcome_log = root / OUTCOME_ACCESS_LOG_PATH
        outcome_log_meta = outcome_log.lstat()
        if (
            not stat.S_ISREG(outcome_log_meta.st_mode)
            or outcome_log_meta.st_size != 0
        ):
            raise ClosureE10SourceEvidenceError(
                "source publication requires the unopened zero-byte outcome log"
            )
    parent = final_directory.parent
    _require_real_directory_chain(root, parent)
    try:
        work_relative = work_directory.relative_to(root / "tmp")
    except ValueError as exc:
        raise ClosureE10SourceEvidenceError(
            "publication work directory escaped repository tmp"
        ) from exc
    if len(work_relative.parts) != 1 or not work_directory.name.startswith(
        WORK_PREFIX
    ):
        raise ClosureE10SourceEvidenceError("publication work directory is unsafe")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    work_meta = os.stat(
        work_directory.name,
        dir_fd=owned_guard.tmp_fd,
        follow_symlinks=False,
    )
    if stat.S_ISLNK(work_meta.st_mode) or not stat.S_ISDIR(work_meta.st_mode):
        raise ClosureE10SourceEvidenceError("publication work directory is unsafe")
    work_fd = os.open(work_directory.name, flags, dir_fd=owned_guard.tmp_fd)
    parent_fds, parent_links, parent_root = _open_directory_chain(
        root, source_directory.parent, context="source publication"
    )
    parent_fd = parent_fds[-1]
    staged_fd: int | None = None
    final_fd: int | None = None
    staged_identity: tuple[int, int] | None = None
    final_identity: tuple[int, int] | None = None
    staged_created = False
    final_created = False
    staged_owners: dict[str, tuple[int, int]] = {}
    final_owners: list[tuple[str, tuple[int, int]]] = []
    active_error: BaseException | None = None
    publication_validated = False
    succeeded = False
    cleanup_error: BaseException | None = None
    try:
        owned_guard.require_exact(
            repository_root=root,
            context="source publication transaction start",
        )
        if _metadata_identity(os.fstat(work_fd)) != _metadata_identity(work_meta):
            raise ClosureE10SourceEvidenceError(
                "publication work directory changed before anchoring"
            )
        os.mkdir("publication", mode=0o700, dir_fd=work_fd)
        staged_created = True
        staged_entry = os.stat(
            "publication", dir_fd=work_fd, follow_symlinks=False
        )
        staged_identity = (staged_entry.st_dev, staged_entry.st_ino)
        staged_fd = os.open("publication", flags, dir_fd=work_fd)
        staged_meta = os.fstat(staged_fd)
        if (staged_meta.st_dev, staged_meta.st_ino) != staged_identity:
            raise ClosureE10SourceEvidenceError(
                "staged publication changed while opening"
            )
        _require_directory_entry_identity(
            work_fd,
            "publication",
            staged_fd,
            staged_identity,
            context="staged publication",
        )
        for key in SOURCE_EVIDENCE_KEYS:
            name = source_paths[key].name
            staged_owners[name] = _write_exclusive_at(
                staged_fd, name, artifacts[key]
            )
        manifest_name = manifest_path.name
        staged_owners[manifest_name] = _write_exclusive_at(
            staged_fd, manifest_name, _pretty_json(dict(manifest))
        )
        os.fsync(staged_fd)
        owned_guard.require_exact(
            repository_root=root,
            context="source publication after staging",
        )

        try:
            os.stat(
                final_directory.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise ClosureE10SourceEvidenceError(
                "source evidence directory appeared during publication"
            )
        os.mkdir(final_directory.name, mode=0o755, dir_fd=parent_fd)
        final_created = True
        final_entry = os.stat(
            final_directory.name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        final_identity = (final_entry.st_dev, final_entry.st_ino)
        final_fd = os.open(final_directory.name, flags, dir_fd=parent_fd)
        final_meta = os.fstat(final_fd)
        if (final_meta.st_dev, final_meta.st_ino) != final_identity:
            raise ClosureE10SourceEvidenceError(
                "final publication changed while opening"
            )
        _require_directory_entry_identity(
            parent_fd,
            final_directory.name,
            final_fd,
            final_identity,
            context="final publication",
        )
        os.fsync(parent_fd)
        owned_guard.require_exact(
            repository_root=root,
            context="source publication after final-directory creation",
        )
        for key in SOURCE_EVIDENCE_KEYS:
            name = source_paths[key].name
            owned_guard.require_exact(
                repository_root=root,
                context=f"source publication before data link {name}",
            )
            identity = _link_exclusive_at(staged_fd, name, final_fd, name)
            final_owners.append((name, identity))
            _unlink_owned_at(staged_fd, name, identity)
            staged_owners.pop(name)
            owned_guard.require_exact(
                repository_root=root,
                context=f"source publication after data link {name}",
            )
        # The six data entries are durable before the manifest link is made.
        os.fsync(final_fd)
        os.fsync(staged_fd)
        owned_guard.require_exact(
            repository_root=root,
            context="source publication before manifest link",
        )
        manifest_identity = _link_exclusive_at(
            staged_fd, manifest_name, final_fd, manifest_name
        )
        final_owners.append((manifest_name, manifest_identity))
        _unlink_owned_at(staged_fd, manifest_name, manifest_identity)
        staged_owners.pop(manifest_name)
        os.fsync(final_fd)
        os.fsync(staged_fd)
        owned_guard.require_exact(
            repository_root=root,
            context="source publication after manifest link",
        )
        _require_directory_entry_identity(
            parent_fd,
            final_directory.name,
            final_fd,
            final_identity,
            context="final publication",
        )
        _recapture_directory_chain_locations(
            fds=parent_fds,
            links=parent_links,
            root=parent_root,
            context="source publication",
        )
        loaded = load_closure_e10_software_evidence(
            repo_root=root,
            expected_h_commit=expected_h_commit,
            require_git_publication=False,
            recovery_attempt=mode,
        )
        if set(loaded) != set(SOURCE_EVIDENCE_KEYS):
            raise ClosureE10SourceEvidenceError("post-publication load drifted")
        if mode == RECOVERY_ATTEMPT_1 and _collect_recovery_attempt_1_record(
            root,
            expected_h_commit,
        ) != expected_recovery_record:
            raise ClosureE10SourceEvidenceError(
                "recovery inherited P1 inputs changed during publication"
            )
        _require_directory_entry_identity(
            parent_fd,
            final_directory.name,
            final_fd,
            final_identity,
            context="final publication",
        )
        owned_guard.require_exact(
            repository_root=root,
            context="source publication post-load",
        )
        publication_validated = True
    except BaseException as exc:
        active_error = exc
    if staged_fd is not None and staged_identity is not None:
        for name, identity in tuple(staged_owners.items()):
            try:
                _unlink_owned_at(staged_fd, name, identity)
            except BaseException as exc:
                cleanup_error = cleanup_error or exc
        try:
            _require_directory_entry_identity(
                work_fd,
                "publication",
                staged_fd,
                staged_identity,
                context="staged publication cleanup",
            )
            _remove_owned_name_atomic(
                work_fd,
                "publication",
                staged_identity,
                context="staged publication cleanup",
                missing_is_error=True,
                owned_fd=staged_fd,
                expected_directory=True,
            )
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    elif staged_created and staged_identity is not None:
        try:
            entry = os.stat(
                "publication", dir_fd=work_fd, follow_symlinks=False
            )
            if (
                stat.S_ISLNK(entry.st_mode)
                or not stat.S_ISDIR(entry.st_mode)
                or (entry.st_dev, entry.st_ino) != staged_identity
            ):
                raise ClosureE10SourceEvidenceError(
                    "staged publication was replaced before cleanup"
                )
            _remove_owned_name_atomic(
                work_fd,
                "publication",
                staged_identity,
                context="unopened staged publication cleanup",
                missing_is_error=True,
                expected_directory=True,
            )
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    try:
        owned_guard.require_exact(
            repository_root=root,
            context="source publication before work cleanup",
        )
    except BaseException as exc:
        cleanup_error = cleanup_error or exc
    if work_directory.name not in owned_guard.removed_work_names:
        try:
            owned_guard.remove_owned_work_directory(
                name=work_directory.name,
                identity=(work_meta.st_dev, work_meta.st_ino),
                context="source publication work cleanup",
            )
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    try:
        owned_guard.require_exact(
            repository_root=root,
            context="source publication after work cleanup",
        )
    except BaseException as exc:
        cleanup_error = cleanup_error or exc
    if publication_validated and cleanup_error is None:
        if final_fd is None or final_identity is None:
            cleanup_error = ClosureE10SourceEvidenceError(
                "validated source publication lost its final ownership anchors"
            )
        else:
            try:
                owned_guard.unlink_strict(
                    context="source publication guard cleanup"
                )
                owned_guard._require_ancestry_exact(
                    context="source publication after guard cleanup"
                )
                _require_directory_entry_identity(
                    parent_fd,
                    final_directory.name,
                    final_fd,
                    final_identity,
                    context="final publication after guard cleanup",
                )
                _recapture_directory_chain_locations(
                    fds=parent_fds,
                    links=parent_links,
                    root=parent_root,
                    context="source publication after guard cleanup",
                )
                succeeded = True
            except BaseException as exc:
                cleanup_error = cleanup_error or exc
    if not succeeded and final_fd is not None and final_identity is not None:
        for name, identity in reversed(final_owners):
            try:
                _unlink_owned_at(final_fd, name, identity)
            except BaseException as exc:
                cleanup_error = cleanup_error or exc
        try:
            _require_directory_entry_identity(
                parent_fd,
                final_directory.name,
                final_fd,
                final_identity,
                context="final publication rollback",
            )
            _remove_owned_name_atomic(
                parent_fd,
                final_directory.name,
                final_identity,
                context="final publication rollback",
                missing_is_error=True,
                owned_fd=final_fd,
                expected_directory=True,
            )
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    elif not succeeded and final_created and final_identity is not None:
        try:
            entry = os.stat(
                final_directory.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
            if (
                stat.S_ISLNK(entry.st_mode)
                or not stat.S_ISDIR(entry.st_mode)
                or (entry.st_dev, entry.st_ino) != final_identity
            ):
                raise ClosureE10SourceEvidenceError(
                    "final publication was replaced before cleanup"
                )
            _remove_owned_name_atomic(
                parent_fd,
                final_directory.name,
                final_identity,
                context="unopened final publication rollback",
                missing_is_error=True,
                expected_directory=True,
            )
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    if (
        not owned_guard.removed
        and work_directory.name in owned_guard.removed_work_names
    ):
        try:
            owned_guard.unlink_strict(
                context="failed source publication guard cleanup"
            )
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    if final_fd is not None:
        _close_fd_noexcept(final_fd)
    if staged_fd is not None:
        _close_fd_noexcept(staged_fd)
    for fd in reversed(parent_fds):
        _close_fd_noexcept(fd)
    _close_fd_noexcept(work_fd)
    if cleanup_error is not None:
        raise ClosureE10SourceEvidenceError(
            "E10 source publication rollback/cleanup failed closed"
        ) from cleanup_error
    if not succeeded:
        if isinstance(active_error, ClosureE10SourceEvidenceError):
            raise active_error
        raise ClosureE10SourceEvidenceError(
            "E10 source publication failed"
        ) from active_error
    return {
        "status": (
            "source_evidence_recovery_written_unpublished"
            if mode == RECOVERY_ATTEMPT_1
            else "source_evidence_written_unpublished"
        ),
        "gate": GATE,
        "repository_commit": expected_h_commit,
        "source_artifact_count": 6,
        "manifest_written_last": True,
        "paths": [
            *(source_paths[key].as_posix() for key in SOURCE_EVIDENCE_KEYS),
            manifest_path.as_posix(),
        ],
        "git_commit_performed": False,
        "git_push_performed": False,
        "dvc_push_performed": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
        "private_full_opened": False,
        "writes_performed": True,
        **(
            {"recovery_attempt": RECOVERY_ATTEMPT_1}
            if mode == RECOVERY_ATTEMPT_1
            else {}
        ),
    }


def publish_closure_e10_source_bundle(
    *,
    repo_root: Path,
    work_directory: Path,
    artifacts: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    expected_h_commit: str,
    owned_guard: OwnedGuard,
    recovery_attempt: str | None = None,
) -> dict[str, Any]:
    """Run one guard-bound publication and fail closed on guard cleanup."""

    work_identity: tuple[int, int] | None = None
    try:
        relative = work_directory.relative_to(owned_guard.root_path / "tmp")
        if (
            len(relative.parts) == 1
            and work_directory.name.startswith(WORK_PREFIX)
        ):
            metadata = os.stat(
                work_directory.name,
                dir_fd=owned_guard.tmp_fd,
                follow_symlinks=False,
            )
            if not stat.S_ISLNK(metadata.st_mode) and stat.S_ISDIR(
                metadata.st_mode
            ):
                work_identity = (metadata.st_dev, metadata.st_ino)
    except (OSError, ValueError):
        pass
    active_error: BaseException | None = None
    try:
        return _publish_closure_e10_source_bundle_transaction(
            repo_root=repo_root,
            work_directory=work_directory,
            artifacts=artifacts,
            manifest=manifest,
            expected_h_commit=expected_h_commit,
            owned_guard=owned_guard,
            recovery_attempt=recovery_attempt,
        )
    except BaseException as exc:
        active_error = exc
    cleanup_error: BaseException | None = None
    if (
        work_identity is not None
        and work_directory.name not in owned_guard.removed_work_names
    ):
        try:
            owned_guard.remove_owned_work_directory(
                name=work_directory.name,
                identity=work_identity,
                context="source publication outer work cleanup",
            )
        except BaseException as exc:
            cleanup_error = exc
    work_cleanup_complete = (
        work_identity is not None
        and work_directory.name in owned_guard.removed_work_names
    )
    if not owned_guard.removed and work_cleanup_complete:
        try:
            owned_guard.unlink_strict(
                context="source publication outer guard cleanup"
            )
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    if cleanup_error is not None:
        raise ClosureE10SourceEvidenceError(
            "E10 source publication guard/work cleanup failed closed"
        ) from cleanup_error
    if isinstance(active_error, ClosureE10SourceEvidenceError):
        raise active_error
    raise ClosureE10SourceEvidenceError(
        "E10 source publication failed"
    ) from active_error


def _publish_verified_e10_source_bundle(
    *,
    repo_root: Path,
    work_directory: Path,
    mask_work: OwnedMaskWorkDirectory,
    artifacts: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    expected_h_commit: str,
    owned_guard: OwnedGuard,
    recovery_attempt: str | None = None,
) -> dict[str, Any]:
    """Commit only after the no-longer-needed mask tree is removed."""

    mask_work.remove()
    return publish_closure_e10_source_bundle(
        repo_root=repo_root,
        work_directory=work_directory,
        artifacts=artifacts,
        manifest=manifest,
        expected_h_commit=expected_h_commit,
        owned_guard=owned_guard,
        recovery_attempt=recovery_attempt,
    )


def _load_source_files(
    repo_root: Path,
    *,
    recovery_attempt: str | None = None,
) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
    mode = _require_recovery_attempt(recovery_attempt)
    source_directory, source_paths, manifest_path = _source_bundle_layout(mode)
    fds, links, root = _open_directory_chain(
        repo_root,
        source_directory,
        context="E10 source bundle",
    )
    artifacts: dict[str, bytes] = {}
    file_records: list[dict[str, Any]] = []
    file_identities: dict[str, tuple[int, ...]] = {}
    manifest_bytes = b""
    try:
        for key in SOURCE_EVIDENCE_KEYS:
            path = source_paths[key]
            payload, identity = _read_regular_from_directory_fd(
                path.name,
                directory_fd=fds[-1],
                context=f"E10 source {key}",
                require_nlink_one=True,
            )
            artifacts[key] = payload
            file_identities[path.name] = identity
            file_records.append(
                {
                    "path": path.as_posix(),
                    "bytes": len(payload),
                    "sha256": _sha256(payload),
                }
            )
        manifest_bytes, manifest_identity = _read_regular_from_directory_fd(
            manifest_path.name,
            directory_fd=fds[-1],
            context="E10 source manifest",
            require_nlink_one=True,
        )
        file_identities[manifest_path.name] = manifest_identity
        file_records.append(
            {
                "path": manifest_path.as_posix(),
                "bytes": len(manifest_bytes),
                "sha256": _sha256(manifest_bytes),
            }
        )
        for name, identity in file_identities.items():
            entry = os.stat(name, dir_fd=fds[-1], follow_symlinks=False)
            if _metadata_identity(entry) != identity or stat.S_ISLNK(entry.st_mode):
                raise ClosureE10SourceEvidenceError(
                    "E10 source bundle changed across the seven-file read"
                )
        _recapture_directory_chain(
            fds=fds,
            links=links,
            root=root,
            context="E10 source bundle",
        )
    except OSError as exc:
        raise ClosureE10SourceEvidenceError(
            "E10 source bundle cannot be read"
        ) from exc
    finally:
        for fd in reversed(fds):
            os.close(fd)
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClosureE10SourceEvidenceError("E10 source manifest is invalid") from exc
    if not isinstance(manifest, Mapping):
        raise ClosureE10SourceEvidenceError("E10 source manifest is not a mapping")
    if _pretty_json(dict(manifest)) != manifest_bytes:
        raise ClosureE10SourceEvidenceError("E10 source manifest is not canonical")
    snapshot = {
        "schema_version": "closure_e10_source_bundle_snapshot_v1",
        "source_directory": source_directory.as_posix(),
        "file_count": 7,
        "files": file_records,
        "bundle_sha256": _sha256(_canonical_json(file_records)),
        "directory_chain_anchored_no_follow": True,
        "single_fd_per_file": True,
        "ancestor_and_entries_recaptured": True,
    }
    return artifacts, dict(manifest), snapshot


def _validate_loader_worktree_status(
    status: str,
    allowed_dirty_paths: Sequence[str],
    *,
    recovery_attempt: str | None = None,
) -> None:
    mode = _require_recovery_attempt(recovery_attempt)
    allowed = list(allowed_dirty_paths)
    permitted = {OUTCOME_ACCESS_LOG_PATH.as_posix()}
    if mode == RECOVERY_ATTEMPT_1:
        permitted.add(RECOVERY_ACTIVATION_PATH.as_posix())
    if len(allowed) != len(set(allowed)) or any(
        path not in permitted for path in allowed
    ):
        raise ClosureE10SourceEvidenceError(
            "published E10 source loader received an invalid dirty-path allowance"
        )
    observed_status = status.splitlines() if status else []
    activation = RECOVERY_ACTIVATION_PATH.as_posix()
    activation_allowed = mode == RECOVERY_ATTEMPT_1 and activation in allowed
    accepted_recovery_status = len(observed_status) == 1 and observed_status[0] in {
        f"?? {activation}",
        f"A  {activation}",
    }
    if (activation_allowed and not accepted_recovery_status) or (
        not activation_allowed and observed_status
    ):
        raise ClosureE10SourceEvidenceError(
            "published E10 source evidence worktree scope drifted"
        )


def _capture_published_loader_state(repo_root: Path) -> dict[str, Any]:
    refs = {
        "head": _require_commit(
            _git(repo_root, "rev-parse", "HEAD"), context="loader HEAD"
        ),
        "main": _require_commit(
            _git(repo_root, "rev-parse", "refs/heads/main"),
            context="loader main",
        ),
        "origin_main": _require_commit(
            _git(repo_root, "rev-parse", "refs/remotes/origin/main"),
            context="loader origin/main",
        ),
        "origin_head": _require_commit(
            _git(repo_root, "rev-parse", "refs/remotes/origin/HEAD^{commit}"),
            context="loader origin/HEAD",
        ),
    }
    return {
        "refs": refs,
        "branch": _git(repo_root, "branch", "--show-current"),
        "status": _git(repo_root, *OUTCOME_FREE_GIT_STATUS_ARGUMENTS),
    }


def load_closure_e10_software_evidence(
    *,
    repo_root: Path = PROJECT_ROOT,
    expected_h_commit: str,
    require_git_publication: bool = True,
    allowed_dirty_paths: Sequence[str] = (),
    include_source_snapshot: bool = False,
    recovery_attempt: str | None = None,
) -> dict[str, Any]:
    """Load the six objects in the exact in-memory dialect expected by E10.

    Before E0-U, callers should keep ``require_git_publication=True`` to bind
    the bundle to published Git blobs and to enforce the clean-tree policy.
    After E0-U has made its first durable outcome-log append, the sealed
    context builder must pass ``require_git_publication=False``: that path
    performs no subprocess calls, never inspects the worktree or opens the
    log, and validates only the seven regular source-evidence files already
    approved by the pre-open authority.  ``allowed_dirty_paths`` exists only
    for an external Git-aware audit and is not needed by the sealed loader.
    ``include_source_snapshot=True`` returns the logical evidence plus exact
    seven-file path/byte/hash records and a bundle digest so E0-U can compare
    the same anchored source snapshot before and after its durable append.
    """

    root = repo_root.resolve(strict=True)
    mode = _resolve_loader_recovery_attempt(
        root,
        expected_h_commit,
        recovery_attempt,
    )
    _, source_paths, manifest_path = _source_bundle_layout(mode)
    artifacts, manifest, source_snapshot = (
        _load_source_files(root)
        if mode is None
        else _load_source_files(root, recovery_attempt=mode)
    )
    evidence = validate_closure_e10_source_payloads(
        artifacts=artifacts,
        manifest=manifest,
        expected_h_commit=expected_h_commit,
        recovery_attempt=mode,
    )
    if require_git_publication:
        _require_host_outcome_directories_absent(root)
        host_log_state = (
            _capture_host_outcome_log_state(root, expected_h_commit)
            if mode is None
            else _capture_host_outcome_log_state(
                root,
                expected_h_commit,
                recovery_attempt=mode,
            )
        )
        published_state = _capture_published_loader_state(root)
        published_refs = cast(Mapping[str, str], published_state["refs"])
        head = published_refs["head"]
        if set(published_refs.values()) != {head}:
            raise ClosureE10SourceEvidenceError(
                f"published E10 source refs are not aligned: {published_refs}"
            )
        if published_state["branch"] != "main":
            raise ClosureE10SourceEvidenceError(
                "published E10 source validation requires branch main"
            )
        if _git(root, "merge-base", "--is-ancestor", expected_h_commit, head):
            # ``git merge-base --is-ancestor`` prints nothing on success.  The
            # wrapper already checked return code; a nonempty result is drift.
            raise ClosureE10SourceEvidenceError("unexpected ancestor command output")
        _validate_loader_worktree_status(
            cast(str, published_state["status"]),
            allowed_dirty_paths,
            recovery_attempt=mode,
        )
        repository_state = cast(
            Mapping[str, Any], manifest["repository_pre_generation"]
        )
        builder_record = cast(Mapping[str, Any], repository_state["builder_source"])
        _, h_builder_stdout, _ = _run(
            (
                "git",
                "show",
                f"{expected_h_commit}:{builder_record['path']}",
            ),
            repo_root=root,
        )
        h_builder = h_builder_stdout.encode("utf-8")
        if (
            len(h_builder) != builder_record["bytes"]
            or _sha256(h_builder) != builder_record["sha256"]
        ):
            raise ClosureE10SourceEvidenceError(
                "source manifest does not bind the exact H builder blob"
            )
        environment = cast(Mapping[str, Any], evidence["environment"])
        for path, hash_key, bytes_key in (
            ("poetry.lock", "dependency_lock_sha256", "dependency_lock_bytes"),
            ("pyproject.toml", "pyproject_sha256", "pyproject_bytes"),
        ):
            _, h_stdout, _ = _run(
                ("git", "show", f"{expected_h_commit}:{path}"), repo_root=root
            )
            h_payload = h_stdout.encode("utf-8")
            if (
                len(h_payload) != environment.get(bytes_key)
                or _sha256(h_payload) != environment.get(hash_key)
            ):
                raise ClosureE10SourceEvidenceError(
                    f"environment does not bind exact H {path}"
                )
        captured_source_payloads = {
            **{source_paths[key]: artifacts[key] for key in SOURCE_EVIDENCE_KEYS},
            manifest_path: _pretty_json(manifest),
        }
        for path, captured_payload in captured_source_payloads.items():
            _, stdout, _ = _run(
                ("git", "show", f"{head}:{path.as_posix()}"),
                repo_root=root,
            )
            if stdout.encode("utf-8") != captured_payload:
                raise ClosureE10SourceEvidenceError(
                    f"captured E10 source differs from anchored HEAD: {path}"
                )
        repeated_published_state = _capture_published_loader_state(root)
        if repeated_published_state != published_state:
            raise ClosureE10SourceEvidenceError(
                "published E10 source refs/worktree changed during validation"
            )
        _require_host_outcome_directories_absent(root)
        repeated_host_log_state = (
            _capture_host_outcome_log_state(root, expected_h_commit)
            if mode is None
            else _capture_host_outcome_log_state(
                root,
                expected_h_commit,
                recovery_attempt=mode,
            )
        )
        if repeated_host_log_state != host_log_state:
            raise ClosureE10SourceEvidenceError(
                "host outcome log changed during published source validation"
            )
    if include_source_snapshot:
        return {
            "software_evidence": evidence,
            "source_snapshot": {
                **source_snapshot,
                "repository_commit": expected_h_commit,
            },
        }
    return evidence


def _acquire_guard(repo_root: Path) -> OwnedGuard:
    root = repo_root.resolve(strict=True)
    if root == root.parent or not root.name or GUARD_PATH.parent != Path("tmp"):
        raise ClosureE10SourceEvidenceError("owned guard repository root is unsafe")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    root_parent_fd = -1
    root_fd = -1
    tmp_fd = -1
    guard_fd = -1
    created_guard_pair: tuple[int, int] | None = None
    guard_identity: tuple[int, ...] | None = None
    try:
        root_parent_meta = root.parent.lstat()
        root_parent_fd = os.open(root.parent, flags)
        root_parent_anchored = os.fstat(root_parent_fd)
        if (
            stat.S_ISLNK(root_parent_meta.st_mode)
            or not stat.S_ISDIR(root_parent_meta.st_mode)
            or (root_parent_anchored.st_dev, root_parent_anchored.st_ino)
            != (root_parent_meta.st_dev, root_parent_meta.st_ino)
        ):
            raise ClosureE10SourceEvidenceError(
                "owned guard repository parent changed while opening"
            )
        root_entry = os.stat(
            root.name, dir_fd=root_parent_fd, follow_symlinks=False
        )
        root_fd = os.open(root.name, flags, dir_fd=root_parent_fd)
        root_anchored = os.fstat(root_fd)
        if (
            stat.S_ISLNK(root_entry.st_mode)
            or not stat.S_ISDIR(root_entry.st_mode)
            or (root_anchored.st_dev, root_anchored.st_ino)
            != (root_entry.st_dev, root_entry.st_ino)
        ):
            raise ClosureE10SourceEvidenceError(
                "owned guard repository root changed while opening"
            )
        try:
            tmp_entry = os.stat("tmp", dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            os.mkdir("tmp", mode=0o700, dir_fd=root_fd)
            os.fsync(root_fd)
            tmp_entry = os.stat("tmp", dir_fd=root_fd, follow_symlinks=False)
        tmp_fd = os.open("tmp", flags, dir_fd=root_fd)
        tmp_anchored = os.fstat(tmp_fd)
        if (
            stat.S_ISLNK(tmp_entry.st_mode)
            or not stat.S_ISDIR(tmp_entry.st_mode)
            or (tmp_anchored.st_dev, tmp_anchored.st_ino)
            != (tmp_entry.st_dev, tmp_entry.st_ino)
        ):
            raise ClosureE10SourceEvidenceError(
                "owned guard tmp directory changed while opening"
            )
        guard_fd = os.open(
            GUARD_PATH.name,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=tmp_fd,
        )
        created_guard_meta = os.fstat(guard_fd)
        created_guard_pair = (
            created_guard_meta.st_dev,
            created_guard_meta.st_ino,
        )
        payload = f"pid={os.getpid()}\n".encode("ascii")
        offset = 0
        while offset < len(payload):
            written = os.write(guard_fd, payload[offset:])
            if written <= 0:
                raise ClosureE10SourceEvidenceError(
                    "owned guard write made no progress"
                )
            offset += written
        os.fsync(guard_fd)
        guard_anchored = os.fstat(guard_fd)
        guard_entry = os.stat(
            GUARD_PATH.name,
            dir_fd=tmp_fd,
            follow_symlinks=False,
        )
        guard_identity = _metadata_identity(guard_anchored)
        if (
            stat.S_ISLNK(guard_entry.st_mode)
            or not stat.S_ISREG(guard_anchored.st_mode)
            or not stat.S_ISREG(guard_entry.st_mode)
            or guard_anchored.st_nlink != 1
            or guard_entry.st_nlink != 1
            or _metadata_identity(guard_entry) != guard_identity
        ):
            raise ClosureE10SourceEvidenceError(
                "owned guard changed while being acquired"
            )
        os.fsync(tmp_fd)
        root_parent_final = os.fstat(root_parent_fd)
        root_final = os.fstat(root_fd)
        owned = OwnedGuard(
            root_path=root,
            root_parent_path=root.parent,
            root_name=root.name,
            root_parent_fd=root_parent_fd,
            root_fd=root_fd,
            tmp_fd=tmp_fd,
            guard_fd=guard_fd,
            root_parent_identity=_metadata_identity(root_parent_final),
            root_identity=_metadata_identity(root_final),
            tmp_identity=(tmp_anchored.st_dev, tmp_anchored.st_ino),
            guard_identity=guard_identity,
            guard_name=GUARD_PATH.name,
        )
        owned.require_exact(repository_root=root, context="owned guard acquisition")
        return owned
    except BaseException:
        cleanup_error: BaseException | None = None
        if created_guard_pair is not None and tmp_fd >= 0:
            try:
                _remove_owned_name_atomic(
                    tmp_fd,
                    GUARD_PATH.name,
                    created_guard_pair,
                    context="owned guard acquisition rollback",
                    missing_is_error=True,
                    owned_fd=guard_fd if guard_fd >= 0 else None,
                )
            except BaseException as exc:
                cleanup_error = exc
        for fd in (guard_fd, tmp_fd, root_fd, root_parent_fd):
            if fd >= 0:
                os.close(fd)
        if cleanup_error is not None:
            raise ClosureE10SourceEvidenceError(
                "owned guard acquisition cleanup failed closed"
            ) from cleanup_error
        raise


def _safe_remove_mask_work_directory(
    path: Path, identity: tuple[int, int]
) -> None:
    if path.parent != Path("/tmp") or not path.name.startswith(MASK_WORK_PREFIX):
        raise ClosureE10SourceEvidenceError("refusing unsafe mask cleanup")
    parent_fd = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    captured_name: str | None = None
    captured_fd: int | None = None
    try:
        for _ in range(128):
            candidate = f".closure_e10_mask_cleanup_{secrets.token_hex(16)}"
            try:
                _rename_noreplace_at(
                    parent_fd,
                    path.name,
                    parent_fd,
                    candidate,
                )
            except OSError as exc:
                if exc.errno == errno.EEXIST:
                    continue
                if exc.errno == errno.ENOENT:
                    raise ClosureE10SourceEvidenceError(
                        "owned mask work directory is missing during cleanup"
                    ) from exc
                raise ClosureE10SourceEvidenceError(
                    "owned mask work directory atomic capture failed"
                ) from exc
            captured_name = candidate
            break
        if captured_name is None:
            raise ClosureE10SourceEvidenceError(
                "owned mask cleanup could not allocate an exclusive tombstone"
            )
        os.fsync(parent_fd)
        metadata = os.stat(
            captured_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            (metadata.st_dev, metadata.st_ino) != identity
            or stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
        ):
            try:
                _rename_noreplace_at(
                    parent_fd,
                    captured_name,
                    parent_fd,
                    path.name,
                )
                os.fsync(parent_fd)
                captured_name = None
            except OSError as exc:
                raise ClosureE10SourceEvidenceError(
                    "foreign mask replacement was preserved under its cleanup "
                    "tombstone because the canonical name reappeared"
                ) from exc
            raise ClosureE10SourceEvidenceError(
                "owned mask work directory was replaced during atomic capture; "
                "the foreign entry was restored"
            )
        flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        captured_fd = os.open(captured_name, flags, dir_fd=parent_fd)
        anchored = os.fstat(captured_fd)
        if (
            (anchored.st_dev, anchored.st_ino) != identity
            or not stat.S_ISDIR(anchored.st_mode)
        ):
            raise ClosureE10SourceEvidenceError(
                "owned mask cleanup tombstone changed while opening"
            )
        captured_path = path.parent / captured_name
        mask_root = captured_path / "restricted_mask_tree"
        _validate_restricted_mask_tree(mask_root)
        repeated = os.stat(
            captured_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            (repeated.st_dev, repeated.st_ino) != identity
            or stat.S_ISLNK(repeated.st_mode)
            or not stat.S_ISDIR(repeated.st_mode)
        ):
            raise ClosureE10SourceEvidenceError(
                "owned mask cleanup tombstone was replaced during validation"
            )
        for spec in RESTRICTED_MASK_SPECS:
            if spec["entry_type"] in {
                "metadata_only_directory",
                "opaque_empty_directory",
            }:
                os.chmod(
                    mask_root / spec["path"],
                    0o700,
                    follow_symlinks=False,
                )
                for leaf in cast(
                    Sequence[str], spec["metadata_placeholders"]
                ):
                    os.chmod(
                        mask_root / spec["path"] / leaf,
                        0o600,
                        follow_symlinks=False,
                    )
            else:
                os.chmod(
                    mask_root / spec["path"],
                    0o600,
                    follow_symlinks=False,
                )
        _remove_directory_contents_anchored(captured_fd)
        _remove_owned_name_atomic(
            parent_fd,
            captured_name,
            identity,
            context="owned mask work cleanup",
            missing_is_error=True,
            owned_fd=captured_fd,
            expected_directory=True,
        )
        captured_name = None
    except BaseException:
        if captured_name is not None:
            try:
                _rename_noreplace_at(
                    parent_fd,
                    captured_name,
                    parent_fd,
                    path.name,
                )
                os.fsync(parent_fd)
                captured_name = None
            except OSError as exc:
                raise ClosureE10SourceEvidenceError(
                    "owned mask cleanup failed and its captured entry could not "
                    "be restored without clobber"
                ) from exc
        raise
    finally:
        if captured_fd is not None:
            _close_fd_noexcept(captured_fd)
        _close_fd_noexcept(parent_fd)


def _emit_openapi(path: Path, repository_commit: str) -> None:
    install_outcome_access_guard(Path.cwd())
    from src.api.main import create_app

    document = copy.deepcopy(create_app().openapi())
    document["x-closure-e10-source-evidence"] = {
        "evidence_role": "openapi",
        "outcome_paths_opened": False,
        "private_full_opened": False,
        "repository_commit": _require_commit(repository_commit),
    }
    _write_exclusive(path, _pretty_json(document))


def _runtime_probe() -> dict[str, Any]:
    install_outcome_access_guard(Path.cwd())
    import fastapi
    import httpx
    import pytest
    import sqlalchemy

    from src.api.main import create_app

    app = create_app()
    torch_record: dict[str, Any]
    try:
        import torch
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cuda_available = bool(torch.cuda.is_available())
            cuda_device_count = int(torch.cuda.device_count())
        torch_record = {
            "available": True,
            "version": torch.__version__,
            "cuda_available": cuda_available,
            "cuda_device_count": cuda_device_count,
            "cuda_version": torch.version.cuda,
            "probe_warning_count": len(caught),
            "probe_warnings": [str(item.message) for item in caught],
        }
    except ImportError:
        torch_record = {
            "available": False,
            "version": None,
            "cuda_available": False,
            "cuda_device_count": 0,
            "cuda_version": None,
            "probe_warning_count": 0,
            "probe_warnings": [],
        }
    return {
        "fastapi": fastapi.__version__,
        "httpx": httpx.__version__,
        "pytest": pytest.__version__,
        "sqlalchemy": sqlalchemy.__version__,
        "app_title": app.title,
        "app_version": app.version,
        "openapi_version": str(app.openapi().get("openapi")),
        "torch": torch_record,
    }


def generate_closure_e10_source_evidence(
    *,
    repo_root: Path = PROJECT_ROOT,
    expected_h_commit: str,
    recovery_attempt: str | None = None,
) -> dict[str, Any]:
    """Execute and atomically publish the outcome-free E10 source bundle."""

    root = repo_root.resolve(strict=True)
    mode = _require_recovery_attempt(recovery_attempt)
    check = check_closure_e10_source_evidence(
        repo_root=root,
        expected_h_commit=expected_h_commit,
        recovery_attempt=mode,
    )
    repository_state = cast(Mapping[str, Any], check["repository"])
    recovery_record = (
        copy.deepcopy(cast(Mapping[str, Any], check["recovery"]))
        if mode == RECOVERY_ATTEMPT_1
        else None
    )
    owned_guard: OwnedGuard | None = None
    work_directory = root / "tmp" / f"{WORK_PREFIX}uninitialized"
    work_identity: tuple[int, int] | None = None
    mask_work_directory = Path("/tmp") / f"{MASK_WORK_PREFIX}uninitialized"
    mask_work: OwnedMaskWorkDirectory | None = None
    mask_tree = mask_work_directory / "restricted_mask_tree"
    succeeded = False
    active_error: BaseException | None = None
    result: dict[str, Any] | None = None
    try:
        owned_guard = _acquire_guard(root)
        work_directory, work_identity = owned_guard.create_work_directory(
            context="E10 source generation work allocation"
        )
        mask_work_directory = Path(
            tempfile.mkdtemp(prefix=MASK_WORK_PREFIX, dir="/tmp")
        ).resolve()
        mask_work_meta = mask_work_directory.lstat()
        mask_work = OwnedMaskWorkDirectory(
            mask_work_directory,
            (mask_work_meta.st_dev, mask_work_meta.st_ino),
        )
        mask_tree = _create_restricted_mask_tree(mask_work_directory)
        base_test_database_url = _require_postgresql_test_database()
        sandbox_tmp, command_outputs, filesystem_isolation = (
            _prepare_read_only_h_worktree(
                repo_root=root,
                work_directory=work_directory,
                mask_tree=mask_tree,
                repository_commit=expected_h_commit,
                repository_state=repository_state,
                recovery_attempt=mode,
            )
        )
        work_directory_relative = work_directory.relative_to(root)
        sandbox_tmp_relative = sandbox_tmp.relative_to(root)
        exact_h_snapshot = cast(
            Mapping[str, Any], filesystem_isolation["exact_h_snapshot"]
        )
        tracked_export = cast(
            Mapping[str, Any], exact_h_snapshot["tracked_export"]
        )
        snapshot_dvc_restore = cast(
            Mapping[str, Any], exact_h_snapshot["dvc_restore"]
        )
        exact_h_archive_record = cast(
            Mapping[str, Any], tracked_export["command"]
        )
        exact_h_tree_inventory_record = cast(
            Mapping[str, Any],
            cast(Mapping[str, Any], tracked_export["tracked_tree_verification"])[
                "command"
            ],
        )
        exact_h_dvc_inventory_record = cast(
            Mapping[str, Any], snapshot_dvc_restore["inventory_command"]
        )
        dvc_restore = _required_dvc_restore_evidence(
            snapshot_dvc_restore
        )
        bwrap_prefix, bwrap_template = _bubblewrap_prefix(
            repo_root=root,
            work_directory_relative=work_directory_relative,
            sandbox_tmp_relative=sandbox_tmp_relative,
            mask_tree=mask_tree,
            restricted_paths=cast(
                Sequence[Mapping[str, Any]],
                filesystem_isolation["restricted_path_masks"],
            ),
        )
        filesystem_isolation["execution_argv_template_prefix"] = bwrap_template
        isolated_base_environment = _isolated_command_environment(root)
        probe_command = (
            ".venv/bin/python",
            "-B",
            "-c",
            ISOLATION_PROBE_CODE,
        )
        probe_record, probe_stdout, _ = _run(
            probe_command,
            repo_root=root,
            environment=isolated_base_environment,
            execution_argv=(*bwrap_prefix, *probe_command),
            inherit_environment=False,
        )
        try:
            probe_results = json.loads(probe_stdout)
        except json.JSONDecodeError as exc:
            raise ClosureE10SourceEvidenceError(
                "filesystem denial probe output is invalid"
            ) from exc
        expected_probe_results = _expected_denial_probe_results()
        if probe_results != expected_probe_results:
            raise ClosureE10SourceEvidenceError(
                "filesystem denial probe did not deny every restricted path"
            )
        filesystem_isolation["denial_probe_results"] = probe_results

        test_database_url, database_ownership = (
            _create_owned_postgresql_database(
                base_test_database_url,
                repository_commit=expected_h_commit,
                run_name=work_directory.name,
            )
        )
        public_junit_path = SANDBOX_OUTPUT_PATH / "public_tests_raw.xml"
        public_command = (
            *PUBLIC_TEST_COMMAND_PREFIX,
            f"--junitxml={public_junit_path.as_posix()}",
        )
        public_environment = {
            **isolated_base_environment,
            "CLOSURE_E10_OUTCOME_GUARD": "1",
            "CLOSURE_E10_REPO_ROOT": ".",
            "CLOSURE_E10_SUITE_KIND": PUBLIC_SUITE_KIND,
            "TEST_DATABASE_URL": test_database_url,
        }
        try:
            public_record, _, _ = _run(
                public_command,
                repo_root=root,
                environment=public_environment,
                execution_argv=(*bwrap_prefix, *public_command),
                inherit_environment=False,
                redact_environment_keys=("TEST_DATABASE_URL",),
                timeout_seconds=1800,
            )
        finally:
            database_ownership = _drop_owned_postgresql_database(
                base_test_database_url,
                database_ownership,
            )
        raw_junit = _read_regular(
            Path("public_tests_raw.xml"),
            repo_root=command_outputs,
            context="raw public JUnit",
        )
        totals, skipped = _parse_junit(raw_junit)
        skip_ledger = _require_public_test_success(totals, skipped)
        bound_junit = _inject_junit_commit(raw_junit, expected_h_commit)

        openapi_path = SANDBOX_OUTPUT_PATH / "openapi_raw.json"
        openapi_command = (
            ".venv/bin/python",
            "-B",
            "src/experiments/build_closure_e10_source_evidence.py",
            "--emit-openapi",
            openapi_path.as_posix(),
            "--repository-commit",
            expected_h_commit,
        )
        openapi_record, _, _ = _run(
            openapi_command,
            repo_root=root,
            environment={
                **isolated_base_environment,
                "CLOSURE_E10_OUTCOME_GUARD": "1",
                "CLOSURE_E10_REPO_ROOT": ".",
            },
            execution_argv=(*bwrap_prefix, *openapi_command),
            inherit_environment=False,
        )
        openapi_bytes = _read_regular(
            Path("openapi_raw.json"),
            repo_root=command_outputs,
            context="generated OpenAPI",
        )
        openapi = json.loads(openapi_bytes.decode("utf-8"))
        if not isinstance(openapi, Mapping):
            raise ClosureE10SourceEvidenceError("generated OpenAPI is not a mapping")
        contract_validation = _validate_openapi_contract(openapi, repo_root=root)

        e2e_junit_path = SANDBOX_OUTPUT_PATH / "e2e_raw.xml"
        e2e_command = (
            "poetry",
            "run",
            "pytest",
            *E2E_TEST_NODES,
            "-q",
            "-p",
            "src.experiments.build_closure_e10_source_evidence",
            "-p",
            "no:cacheprovider",
            f"--junitxml={e2e_junit_path.as_posix()}",
        )
        e2e_record, _, _ = _run(
            e2e_command,
            repo_root=root,
            environment={
                **isolated_base_environment,
                "CLOSURE_E10_OUTCOME_GUARD": "1",
                "CLOSURE_E10_REPO_ROOT": ".",
                "CLOSURE_E10_SUITE_KIND": "synthetic_e2e",
            },
            execution_argv=(*bwrap_prefix, *e2e_command),
            inherit_environment=False,
        )
        e2e_junit = _read_regular(
            Path("e2e_raw.xml"),
            repo_root=command_outputs,
            context="raw end-to-end JUnit",
        )
        e2e_totals, e2e_skipped = _parse_junit(e2e_junit)
        if e2e_totals != {"tests": 3, "failures": 0, "errors": 0, "skipped": 0} or e2e_skipped:
            raise ClosureE10SourceEvidenceError("synthetic E2E suite is not exact 3/0/0/0")

        runtime_command = (
            ".venv/bin/python",
            "-B",
            "src/experiments/build_closure_e10_source_evidence.py",
            "--runtime-probe",
        )
        runtime_record, runtime_stdout, _ = _run(
            runtime_command,
            repo_root=root,
            environment={
                **isolated_base_environment,
                "CLOSURE_E10_OUTCOME_GUARD": "1",
                "CLOSURE_E10_REPO_ROOT": ".",
            },
            execution_argv=(*bwrap_prefix, *runtime_command),
            inherit_environment=False,
        )
        try:
            runtime = json.loads(runtime_stdout)
        except json.JSONDecodeError as exc:
            raise ClosureE10SourceEvidenceError("runtime probe JSON is invalid") from exc

        lock_command = ("poetry", "check", "--lock")
        lock_record, _, _ = _run(lock_command, repo_root=root)
        version_commands = {
            "python_version": (".venv/bin/python", "--version"),
            "poetry_version": ("poetry", "--version"),
            "pytest_version": ("poetry", "run", "pytest", "--version"),
            "dvc_version": (".venv/bin/dvc", "--version"),
            "git_version": ("git", "--version"),
        }
        version_records: dict[str, Mapping[str, Any]] = {}
        version_strings: dict[str, str] = {}
        for name, command in version_commands.items():
            record, stdout, stderr = _run(command, repo_root=root)
            version_records[name] = record
            version_strings[name] = (stdout or stderr).strip()

        repeated_repository_state = _collect_exact_h_repository_state(
            root, expected_h_commit
        )
        if repeated_repository_state != repository_state:
            raise ClosureE10SourceEvidenceError(
                "H repository state changed during E10 source verification"
            )
        if repeated_repository_state != filesystem_isolation[
            "worktree_pre_verification"
        ]:
            raise ClosureE10SourceEvidenceError(
                "read-only H worktree precondition changed during verification"
            )
        filesystem_isolation["worktree_post_verification"] = (
            repeated_repository_state
        )
        repeated_host_log_state = (
            _capture_host_outcome_log_state(root, expected_h_commit)
            if mode is None
            else _capture_host_outcome_log_state(
                root,
                expected_h_commit,
                recovery_attempt=mode,
            )
        )
        if repeated_host_log_state != filesystem_isolation[
            "host_outcome_log_pre_verification"
        ]:
            raise ClosureE10SourceEvidenceError(
                "host outcome log changed during E10 source verification"
            )
        filesystem_isolation["host_outcome_log_post_verification"] = (
            repeated_host_log_state
        )
        if mode == RECOVERY_ATTEMPT_1:
            repeated_recovery = _collect_recovery_attempt_1_record(
                root,
                expected_h_commit,
            )
            if repeated_recovery != recovery_record:
                raise ClosureE10SourceEvidenceError(
                    "recovery inputs changed during E10 source verification"
                )
        _validate_restricted_mask_tree(mask_tree)
        repeated_snapshot_inventory = _snapshot_inventory(
            work_directory / "exact_h_snapshot"
        )
        if repeated_snapshot_inventory != exact_h_snapshot[
            "pre_execution_inventory"
        ]:
            raise ClosureE10SourceEvidenceError(
                "materialized exact-H snapshot changed during verification"
            )
        cast(dict[str, Any], exact_h_snapshot)[
            "post_execution_inventory"
        ] = repeated_snapshot_inventory

        test_report = _build_test_report(
            commit=expected_h_commit,
            command=public_command,
            totals=totals,
            skip_ledger=skip_ledger,
            raw_junit_sha256=_sha256(raw_junit),
            bound_junit_sha256=_sha256(bound_junit),
        )
        contract_report = _build_contract_report(
            commit=expected_h_commit,
            validation=contract_validation,
            openapi_sha256=_sha256(openapi_bytes),
        )
        e2e_report = _build_e2e_report(
            commit=expected_h_commit,
            command=e2e_command,
            totals=e2e_totals,
        )
        lock_bytes = _read_regular(
            Path("poetry.lock"), repo_root=root, context="Poetry lock"
        )
        pyproject_bytes = _read_regular(
            Path("pyproject.toml"), repo_root=root, context="project configuration"
        )
        torch_runtime = cast(Mapping[str, Any], cast(Mapping[str, Any], runtime)["torch"])
        environment = {
            "schema_version": "closure_e10_environment_lock_runtime_v1",
            "repository_commit": expected_h_commit,
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "python_implementation": platform.python_implementation(),
            "python_executable": ".venv/bin/python",
            "dependency_lock_sha256": _sha256(lock_bytes),
            "dependency_lock_bytes": len(lock_bytes),
            "pyproject_sha256": _sha256(pyproject_bytes),
            "pyproject_bytes": len(pyproject_bytes),
            "runtime": runtime,
            "public_test_database": {
                "dialect": "postgresql_asyncpg",
                "test_database_url": cast(
                    Mapping[str, Any], public_record["environment_overrides"]
                )["TEST_DATABASE_URL"],
                "formerly_skipped_http_test_required": True,
                "ownership": database_ownership,
            },
            "tool_versions": version_strings,
            "hardware": {
                "machine": platform.machine(),
                "processor": platform.processor(),
                "cpu_count": os.cpu_count(),
                "memory_bytes": _memory_bytes(),
                "gpu_probe": "torch_runtime_reports_cpu_or_cuda_availability",
                "torch_available": torch_runtime["available"],
                "torch_cuda_available": torch_runtime["cuda_available"],
                "torch_cuda_device_count": torch_runtime["cuda_device_count"],
                "torch_cuda_version": torch_runtime["cuda_version"],
            },
            "repository_pre_generation": repository_state,
            "repository_post_verification": repeated_repository_state,
            "lock_check": lock_record,
            "runtime_probe": runtime_record,
            "version_commands": version_records,
            "dvc_restore_verification": dvc_restore,
            "filesystem_isolation": filesystem_isolation,
            "outcome_safety": {
                **E2E_FIXTURE_CONTRACT,
                "guard_enabled": True,
                **_public_suite_contract_record(),
                "pre_e0u_excluded_test_bases": list(
                    PUBLIC_PRE_E0U_EXCLUDED_TEST_BASES
                ),
                "pre_e0u_excluded_test_nodes": list(
                    PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES
                ),
                "pre_e0u_exclusion_reason": PUBLIC_PRE_E0U_EXCLUSION_REASON,
                "user_prohibited_git_commit_test_nodes": list(
                    PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES
                ),
                "user_prohibited_git_commit_exclusion_reason": (
                    PUBLIC_USER_PROHIBITED_GIT_COMMIT_EXCLUSION_REASON
                ),
                "target_paths_opened": False,
                "outcome_paths_opened": False,
            },
            "generated_at_utc": datetime.now(UTC).isoformat(),
        }
        artifacts = {
            "public_tests_xml": bound_junit,
            "test_report": test_report,
            "openapi": openapi_bytes,
            "openapi_contract_report": contract_report,
            "end_to_end_report": e2e_report,
            "environment": _pretty_json(environment),
        }
        commands: dict[str, Mapping[str, Any]] = {
            "filesystem_denial_probe": probe_record,
            "public_tests": public_record,
            "openapi_generation": openapi_record,
            "end_to_end": e2e_record,
            "exact_h_git_archive": exact_h_archive_record,
            "exact_h_tree_inventory": exact_h_tree_inventory_record,
            "exact_h_dvc_inventory": exact_h_dvc_inventory_record,
            "runtime_probe": runtime_record,
            "poetry_lock_check": lock_record,
            **version_records,
        }
        manifest = build_closure_e10_source_manifest(
            repository_commit=expected_h_commit,
            artifacts=artifacts,
            repository_state=repository_state,
            commands=commands,
            public_totals=totals,
            public_skip_ledger=skip_ledger,
            e2e_totals=e2e_totals,
            contract_validation=contract_validation,
            dvc_restore=dvc_restore,
            filesystem_isolation=filesystem_isolation,
            generated_at_utc=datetime.now(UTC).isoformat(),
            recovery_attempt=mode,
            recovery=recovery_record,
        )
        validate_closure_e10_source_payloads(
            artifacts=artifacts,
            manifest=manifest,
            expected_h_commit=expected_h_commit,
            recovery_attempt=mode,
        )
        if mask_work is None:
            raise ClosureE10SourceEvidenceError(
                "E10 source mask work lease is absent before publication"
            )
        result = _publish_verified_e10_source_bundle(
            repo_root=root,
            work_directory=work_directory,
            mask_work=mask_work,
            artifacts=artifacts,
            manifest=manifest,
            expected_h_commit=expected_h_commit,
            owned_guard=owned_guard,
            recovery_attempt=mode,
        )
        succeeded = True
    except BaseException as exc:
        active_error = exc
    cleanup_error: BaseException | None = None
    if mask_work is not None and not mask_work.removed:
        try:
            mask_work.remove()
        except BaseException as exc:
            cleanup_error = exc
    if (
        work_identity is not None
        and (
            owned_guard is None
            or work_directory.name not in owned_guard.removed_work_names
        )
    ):
        try:
            if owned_guard is None:
                raise ClosureE10SourceEvidenceError(
                    "owned work directory exists without its guard capability"
                )
            owned_guard.remove_owned_work_directory(
                name=work_directory.name,
                identity=work_identity,
                context="E10 source generation work cleanup",
            )
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    work_cleanup_complete = (
        work_identity is None
        or (
            owned_guard is not None
            and work_directory.name in owned_guard.removed_work_names
        )
    )
    if (
        owned_guard is not None
        and not owned_guard.removed
        and work_cleanup_complete
    ):
        try:
            owned_guard.unlink_strict(
                context="E10 source generation guard cleanup"
            )
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    if owned_guard is not None:
        try:
            owned_guard.close()
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    if cleanup_error is not None:
        raise ClosureE10SourceEvidenceError(
            "E10 source generation cleanup failed closed"
        ) from cleanup_error
    if not succeeded:
        if isinstance(active_error, ClosureE10SourceEvidenceError):
            raise active_error
        raise ClosureE10SourceEvidenceError("E10 source generation failed") from active_error
    if result is None:
        raise ClosureE10SourceEvidenceError("E10 source generation returned no result")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-only", action="store_true")
    modes.add_argument("--generate", action="store_true")
    modes.add_argument("--validate", action="store_true")
    modes.add_argument("--emit-openapi", type=Path)
    modes.add_argument("--runtime-probe", action="store_true")
    parser.add_argument("--repository-commit")
    parser.add_argument("--recovery-attempt-1", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    recovery_attempt = (
        RECOVERY_ATTEMPT_1 if args.recovery_attempt_1 else None
    )
    if recovery_attempt is not None and (
        args.runtime_probe or args.emit_openapi is not None
    ):
        raise ClosureE10SourceEvidenceError(
            "--recovery-attempt-1 is only valid with check/generate/validate"
        )
    if args.runtime_probe:
        print(_canonical_json(_runtime_probe()).decode("utf-8"), end="")
        return 0
    if args.emit_openapi is not None:
        if not args.repository_commit:
            raise ClosureE10SourceEvidenceError("--emit-openapi requires --repository-commit")
        _emit_openapi(args.emit_openapi, args.repository_commit)
        return 0
    if not args.repository_commit:
        raise ClosureE10SourceEvidenceError("an exact --repository-commit is required")
    if args.check_only:
        result = check_closure_e10_source_evidence(
            expected_h_commit=args.repository_commit,
            recovery_attempt=recovery_attempt,
        )
    elif args.generate:
        result = generate_closure_e10_source_evidence(
            expected_h_commit=args.repository_commit,
            recovery_attempt=recovery_attempt,
        )
    else:
        evidence = load_closure_e10_software_evidence(
            expected_h_commit=args.repository_commit,
            require_git_publication=True,
            recovery_attempt=recovery_attempt,
        )
        result = {
            "status": "published_source_evidence_valid",
            "gate": GATE,
            "repository_commit": args.repository_commit,
            "software_evidence_keys": sorted(evidence),
            "target_paths_opened": False,
            "outcome_paths_opened": False,
            "private_full_opened": False,
            "writes_performed": False,
            **(
                {"recovery_attempt": RECOVERY_ATTEMPT_1}
                if recovery_attempt == RECOVERY_ATTEMPT_1
                else {}
            ),
        }
    print(_pretty_json(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
