from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, cast

import pytest

from src.experiments import build_closure_e10_source_evidence as evidence
from src.reporting import build_closure_evidence_matrix as final_evidence


H_COMMIT = "1" * 40
OTHER_COMMIT = "2" * 40


def _command(
    argv: list[str],
    environment_overrides: dict[str, str] | None = None,
    *,
    timeout_seconds: int = 300,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> dict[str, Any]:
    return {
        "argv": argv,
        "returncode": 0,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": len(stderr.splitlines()),
        "environment_overrides": {
            "PYTHONDONTWRITEBYTECODE": "1",
            **(environment_overrides or {}),
        },
        "timeout_seconds": timeout_seconds,
    }


def _commands() -> dict[str, dict[str, Any]]:
    public_junit = f"{evidence.SANDBOX_OUTPUT_PATH}/public_tests_raw.xml"
    e2e_junit = f"{evidence.SANDBOX_OUTPUT_PATH}/e2e_raw.xml"
    openapi_path = f"{evidence.SANDBOX_OUTPUT_PATH}/openapi_raw.json"
    isolated = dict(evidence.ISOLATED_ENVIRONMENT_VALUES)
    probe_results = evidence._expected_denial_probe_results()
    return {
        "filesystem_denial_probe": _command(
            [
                ".venv/bin/python",
                "-B",
                "-c",
                evidence.ISOLATION_PROBE_CODE,
            ],
            isolated,
            stdout=evidence._canonical_json(probe_results),
        ),
        "public_tests": _command(
            [*evidence.PUBLIC_TEST_COMMAND_PREFIX, f"--junitxml={public_junit}"],
            {
                **isolated,
                "CLOSURE_E10_OUTCOME_GUARD": "1",
                "CLOSURE_E10_REPO_ROOT": ".",
                "CLOSURE_E10_SUITE_KIND": evidence.PUBLIC_SUITE_KIND,
                "TEST_DATABASE_URL": f"redacted_sha256:{'3' * 64}",
            },
            timeout_seconds=1800,
        ),
        "openapi_generation": _command(
            [
                ".venv/bin/python",
                "-B",
                "src/experiments/build_closure_e10_source_evidence.py",
                "--emit-openapi",
                openapi_path,
                "--repository-commit",
                H_COMMIT,
            ],
            {
                **isolated,
                "CLOSURE_E10_OUTCOME_GUARD": "1",
                "CLOSURE_E10_REPO_ROOT": ".",
            },
        ),
        "end_to_end": _command(
            [
                "poetry",
                "run",
                "pytest",
                *evidence.E2E_TEST_NODES,
                "-q",
                "-p",
                "src.experiments.build_closure_e10_source_evidence",
                "-p",
                "no:cacheprovider",
                f"--junitxml={e2e_junit}",
            ],
            {
                **isolated,
                "CLOSURE_E10_OUTCOME_GUARD": "1",
                "CLOSURE_E10_REPO_ROOT": ".",
                "CLOSURE_E10_SUITE_KIND": "synthetic_e2e",
            },
        ),
        "exact_h_git_archive": _command(
            [
                "git",
                "archive",
                "--format=tar",
                "--output=tmp/closure_v1_e10_source_evidence_fixture/exact_h_snapshot.tar",
                H_COMMIT,
                "--",
                ".",
                *(
                    f":(exclude,top){path}"
                    for path in evidence.FORBIDDEN_VERIFICATION_PREFIXES
                ),
            ],
            {"GIT_OPTIONAL_LOCKS": "0"},
        ),
        "exact_h_dvc_inventory": _command(
            [
                "git",
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "-z",
                evidence.EMPTY_GIT_TREE_SHA1,
                H_COMMIT,
                "--",
                "data/closure_v1",
                "models.dvc",
                *(
                    f":(exclude,top){path}"
                    for path in evidence.FORBIDDEN_VERIFICATION_PREFIXES
                ),
            ],
            {"GIT_OPTIONAL_LOCKS": "0"},
        ),
        "exact_h_tree_inventory": _command(
            [
                "git",
                "diff-tree",
                "--no-commit-id",
                "--raw",
                "-r",
                "-z",
                evidence.EMPTY_GIT_TREE_SHA1,
                H_COMMIT,
                "--",
                ".",
                *(
                    f":(exclude,top){path}"
                    for path in evidence.FORBIDDEN_VERIFICATION_PREFIXES
                ),
            ],
            {"GIT_OPTIONAL_LOCKS": "0"},
        ),
        "runtime_probe": _command(
            [
                ".venv/bin/python",
                "-B",
                "src/experiments/build_closure_e10_source_evidence.py",
                "--runtime-probe",
            ],
            {
                **isolated,
                "CLOSURE_E10_OUTCOME_GUARD": "1",
                "CLOSURE_E10_REPO_ROOT": ".",
            },
        ),
        "poetry_lock_check": _command(["poetry", "check", "--lock"]),
        "python_version": _command([".venv/bin/python", "--version"]),
        "poetry_version": _command(["poetry", "--version"]),
        "pytest_version": _command(["poetry", "run", "pytest", "--version"]),
        "dvc_version": _command([".venv/bin/dvc", "--version"]),
        "git_version": _command(["git", "--version"]),
    }


def _repository_state() -> dict[str, Any]:
    return {
        "branch": "main",
        "repository_commit": H_COMMIT,
        "refs": {
            "head": H_COMMIT,
            "main": H_COMMIT,
            "origin_main": H_COMMIT,
            "origin_head": H_COMMIT,
        },
        "clean_worktree": True,
        "builder_source": {
            "path": "src/experiments/build_closure_e10_source_evidence.py",
            "bytes": 1,
            "sha256": "a" * 64,
            "physical_equals_h_blob": True,
        },
    }


def _host_outcome_log_state() -> dict[str, Any]:
    return {
        "path": evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
        "repository_commit": H_COMMIT,
        "entry_type": "regular_file",
        "device": 1,
        "inode": 2,
        "mode": "644",
        "nlink": 1,
        "bytes": 0,
        "mtime_ns": 1,
        "ctime_ns": 1,
        "h_blob_bytes": 0,
        "h_blob_sha256": hashlib.sha256(b"").hexdigest(),
        "h_blob_command": _command(
            [
                "git",
                "show",
                f"{H_COMMIT}:{evidence.OUTCOME_ACCESS_LOG_PATH.as_posix()}",
            ],
            {"GIT_OPTIONAL_LOCKS": "0"},
        ),
        "index_mode": "100644",
        "index_blob_sha1": evidence.EMPTY_GIT_BLOB_SHA1,
        "index_stage": 0,
        "index_entry_command": _command(
            [
                "git",
                "ls-files",
                "--stage",
                "--",
                evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
            ],
            {"GIT_OPTIONAL_LOCKS": "0"},
            stdout=(
                f"100644 {evidence.EMPTY_GIT_BLOB_SHA1} 0\t"
                f"{evidence.OUTCOME_ACCESS_LOG_PATH.as_posix()}\n"
            ).encode("utf-8"),
        ),
        "physical_contents_opened": False,
    }


def _recovery_host_outcome_log_state() -> dict[str, Any]:
    blob_oid = "3" * 40
    state = _host_outcome_log_state()
    state.update(
        {
            "mode": "644",
            "bytes": evidence.RECOVERY_OUTCOME_LOG_BYTES,
            "h_blob_bytes": evidence.RECOVERY_OUTCOME_LOG_BYTES,
            "h_blob_sha256": evidence.RECOVERY_OUTCOME_LOG_SHA256,
            "index_blob_sha1": blob_oid,
        }
    )
    state["h_blob_command"]["stdout_sha256"] = (
        evidence.RECOVERY_OUTCOME_LOG_SHA256
    )
    state["h_blob_command"]["stdout_line_count"] = 1
    expected_index = (
        f"100644 {blob_oid} 0\t{evidence.OUTCOME_ACCESS_LOG_PATH.as_posix()}\n"
    ).encode("utf-8")
    state["index_entry_command"] = _command(
        [
            "git",
            "ls-files",
            "--stage",
            "--",
            evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
        ],
        {"GIT_OPTIONAL_LOCKS": "0"},
        stdout=expected_index,
    )
    return state


def _recovery_record() -> dict[str, Any]:
    host_log_state = _recovery_host_outcome_log_state()
    inherited = [
        {
            "path": path.as_posix(),
            "role": (
                "inherited_p1_source_evidence_bundle"
                if path in evidence.SOURCE_EVIDENCE_PATHS.values()
                or path == evidence.SOURCE_MANIFEST_PATH
                else (
                    "inherited_p1_phase3_dvc_pointer"
                    if path in evidence.PHASE3_OVERLAY_POINTER_PATHS
                    else "inherited_p1_phase3_overlay_manifest"
                )
            ),
            "bytes": 10,
            "sha256": hashlib.sha256(path.as_posix().encode()).hexdigest(),
            "repository_commit": H_COMMIT,
            "physical_equals_h2_git_blob": True,
            "git_blob_command": _command(
                ["git", "show", f"{H_COMMIT}:{path.as_posix()}"],
                {"GIT_OPTIONAL_LOCKS": "0"},
            ),
        }
        for path in evidence.RECOVERY_INHERITED_P1_PATHS
    ]
    receipt = {
        "path": evidence.ATTEMPT_1_FAILURE_RECEIPT_PATH.as_posix(),
        "role": "closure_e0_u_attempt_1_failure_receipt",
        "bytes": evidence.ATTEMPT_1_FAILURE_RECEIPT_BYTES,
        "sha256": evidence.ATTEMPT_1_FAILURE_RECEIPT_SHA256,
        "repository_commit": H_COMMIT,
        "physical_equals_h2_git_blob": True,
        "git_blob_command": _command(
            [
                "git",
                "show",
                f"{H_COMMIT}:{evidence.ATTEMPT_1_FAILURE_RECEIPT_PATH.as_posix()}",
            ],
            {"GIT_OPTIONAL_LOCKS": "0"},
        ),
    }
    log_input = {
        "path": evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
        "role": "sealed_attempt_1_outcome_log_prefix_from_h2_git_blob",
        "bytes": evidence.RECOVERY_OUTCOME_LOG_BYTES,
        "sha256": evidence.RECOVERY_OUTCOME_LOG_SHA256,
        "repository_commit": H_COMMIT,
        "physical_metadata_matches_h2_git_blob_size": True,
        "physical_contents_opened": False,
        "git_blob_command": copy.deepcopy(host_log_state["h_blob_command"]),
    }
    sealed_inputs = [*copy.deepcopy(inherited), copy.deepcopy(receipt), log_input]
    return {
        "mode": evidence.RECOVERY_ATTEMPT_1,
        "repository_commit": H_COMMIT,
        "outcome_access_log_state": (
            "present_exact_consumed_attempt_1_unopened_by_e10"
        ),
        "outcome_access_log_prefix": {
            "path": evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
            "bytes": evidence.RECOVERY_OUTCOME_LOG_BYTES,
            "sha256": evidence.RECOVERY_OUTCOME_LOG_SHA256,
            "source": "exact_h2_git_blob_and_host_lstat_without_host_content_open",
            "physical_contents_opened": False,
        },
        "host_outcome_log_state": host_log_state,
        "attempt_1_failure_receipt": receipt,
        "attempt_1_failure_receipt_payload_sha256": (
            evidence.ATTEMPT_1_FAILURE_RECEIPT_SHA256
        ),
        "inherited_p1_input_count": len(inherited),
        "inherited_p1_inputs": inherited,
        "inherited_p1_inputs_sha256": evidence._records_digest(inherited),
        "sealed_inputs": sealed_inputs,
        "sealed_inputs_sha256": evidence._records_digest(sealed_inputs),
        "p1_inputs_overwritten": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
    }


def _recovery_2_host_outcome_log_state() -> dict[str, Any]:
    blob_oid = "4" * 40
    state = _host_outcome_log_state()
    state.update(
        {
            "mode": "644",
            "bytes": evidence.RECOVERY_2_OUTCOME_LOG_BYTES,
            "h_blob_bytes": evidence.RECOVERY_2_OUTCOME_LOG_BYTES,
            "h_blob_sha256": evidence.RECOVERY_2_OUTCOME_LOG_SHA256,
            "index_blob_sha1": blob_oid,
        }
    )
    state["h_blob_command"]["stdout_sha256"] = (
        evidence.RECOVERY_2_OUTCOME_LOG_SHA256
    )
    state["h_blob_command"]["stdout_line_count"] = 2
    expected_index = (
        f"100644 {blob_oid} 0\t{evidence.OUTCOME_ACCESS_LOG_PATH.as_posix()}\n"
    ).encode("utf-8")
    state["index_entry_command"] = _command(
        [
            "git",
            "ls-files",
            "--stage",
            "--",
            evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
        ],
        {"GIT_OPTIONAL_LOCKS": "0"},
        stdout=expected_index,
    )
    return state


def _attempt_2_receipt_payload() -> bytes:
    return evidence._canonical_json(
        {
            "schema_version": "closure_e0_u_attempt_2_failure_v1",
            "experiment_id": "closure_v1",
            "gate": "E0-U",
            "attempt_ordinal": 2,
            "execution_id": evidence.ATTEMPT_2_EXECUTION_ID,
            "historical_chain": evidence.RECOVERY_2_HISTORICAL_CHAIN,
            "activation": {
                "bytes": evidence.RECOVERY_ACTIVATION_BYTES,
                "git_blob_oid": evidence.RECOVERY_ACTIVATION_GIT_BLOB_OID,
                "path": evidence.RECOVERY_ACTIVATION_PATH.as_posix(),
                "sha256": evidence.RECOVERY_ACTIVATION_SHA256,
            },
            "access_log": {
                "path": evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
                "bytes": evidence.RECOVERY_2_OUTCOME_LOG_BYTES,
                "record_count": 2,
                "sha256": evidence.RECOVERY_2_OUTCOME_LOG_SHA256,
                "attempt_1_prefix": {
                    "bytes": evidence.RECOVERY_OUTCOME_LOG_BYTES,
                    "sha256": evidence.RECOVERY_OUTCOME_LOG_SHA256,
                },
                "record_2": {
                    "bytes": evidence.RECOVERY_2_OUTCOME_LOG_RECORD_2_BYTES,
                    "sha256": evidence.RECOVERY_2_OUTCOME_LOG_RECORD_2_SHA256,
                },
            },
            "guard_observations": evidence._attempt_2_guard_receipt_records(),
            "failure": {
                "component_id": "E4_trophic_evaluation",
                "component_metrics_computed": False,
                "diagnosis_outcome_free": True,
                "diagnosed_source_phase": (
                    "outcome_free_synthetic_e1_to_e4_interface_reproduction"
                ),
                "error": evidence.ATTEMPT_2_FAILURE_ERROR,
                "outcomes_opened": True,
                "process_exit_code": 2,
                "publication_started": False,
                "result_constructed": False,
                "root_cause": (
                    "E1 trophic prediction column order differed from the exact "
                    "E4 prediction input contract"
                ),
            },
            "publication": {
                "expected_output_count": 52,
                "published_output_count": 0,
            },
        }
    )


def _recovery_2_record() -> dict[str, Any]:
    host_log_state = _recovery_2_host_outcome_log_state()
    inherited = [
        {
            "path": path.as_posix(),
            "role": (
                "inherited_p2_source_evidence_bundle"
                if path in evidence.RECOVERY_2_INHERITED_P2_PATHS
                else (
                    "inherited_p1_phase3_dvc_pointer"
                    if path in evidence.PHASE3_OVERLAY_POINTER_PATHS
                    else "inherited_p1_phase3_overlay_manifest"
                )
            ),
            "bytes": 10,
            "sha256": hashlib.sha256(path.as_posix().encode()).hexdigest(),
            "repository_commit": H_COMMIT,
            "physical_equals_h3_git_blob": True,
            "git_blob_command": _command(
                ["git", "show", f"{H_COMMIT}:{path.as_posix()}"],
                {"GIT_OPTIONAL_LOCKS": "0"},
            ),
            "historical_repository_commit": (
                evidence.RECOVERY_2_HISTORICAL_CHAIN["p2_commit"]
                if path in evidence.RECOVERY_2_INHERITED_P2_PATHS
                else evidence.RECOVERY_2_HISTORICAL_CHAIN["p1_commit"]
            ),
            "physical_equals_historical_git_blob": True,
            "historical_git_blob_command": _command(
                [
                    "git",
                    "show",
                    (
                        f"{evidence.RECOVERY_2_HISTORICAL_CHAIN['p2_commit']}:"
                        if path in evidence.RECOVERY_2_INHERITED_P2_PATHS
                        else f"{evidence.RECOVERY_2_HISTORICAL_CHAIN['p1_commit']}:"
                    )
                    + path.as_posix(),
                ],
                {"GIT_OPTIONAL_LOCKS": "0"},
            ),
        }
        for path in evidence.RECOVERY_2_INHERITED_PATHS
    ]
    activation = {
        "path": evidence.RECOVERY_ACTIVATION_PATH.as_posix(),
        "role": "published_u2_recovery_activation",
        "bytes": evidence.RECOVERY_ACTIVATION_BYTES,
        "sha256": evidence.RECOVERY_ACTIVATION_SHA256,
        "repository_commit": H_COMMIT,
        "physical_equals_h3_git_blob": True,
        "git_blob_command": _command(
            [
                "git",
                "show",
                f"{H_COMMIT}:{evidence.RECOVERY_ACTIVATION_PATH.as_posix()}",
            ],
            {"GIT_OPTIONAL_LOCKS": "0"},
        ),
        "historical_repository_commit": evidence.RECOVERY_2_HISTORICAL_CHAIN[
            "u2_commit"
        ],
        "physical_equals_historical_git_blob": True,
        "historical_git_blob_command": _command(
            [
                "git",
                "show",
                (
                    f"{evidence.RECOVERY_2_HISTORICAL_CHAIN['u2_commit']}:"
                    f"{evidence.RECOVERY_ACTIVATION_PATH.as_posix()}"
                ),
            ],
            {"GIT_OPTIONAL_LOCKS": "0"},
        ),
    }
    receipt_payload = _attempt_2_receipt_payload()
    receipt = {
        "path": evidence.ATTEMPT_2_FAILURE_RECEIPT_PATH.as_posix(),
        "role": "closure_e0_u_attempt_2_failure_receipt",
        "bytes": len(receipt_payload),
        "sha256": hashlib.sha256(receipt_payload).hexdigest(),
        "repository_commit": H_COMMIT,
        "physical_equals_h3_git_blob": True,
        "git_blob_command": _command(
            [
                "git",
                "show",
                f"{H_COMMIT}:{evidence.ATTEMPT_2_FAILURE_RECEIPT_PATH.as_posix()}",
            ],
            {"GIT_OPTIONAL_LOCKS": "0"},
        ),
    }
    guards = [
        {
            "path": path.as_posix(),
            "role": (
                "sealed_attempt_1_guard_retained"
                if path == evidence.ATTEMPT_1_GUARD_PATH
                else "sealed_attempt_2_guard_retained"
            ),
            "entry_type": "regular_file",
            "device": identity["device"],
            "inode": identity["inode"],
            "mode": "600",
            "nlink": 1,
            "bytes": 0,
            "sha256": hashlib.sha256(b"").hexdigest(),
            "physical_contents_opened": False,
        }
        for path, identity in evidence.RECOVERY_2_GUARD_IDENTITIES.items()
    ]
    log_input = {
        "path": evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
        "role": "sealed_attempt_2_outcome_log_from_h3_git_blob",
        "bytes": evidence.RECOVERY_2_OUTCOME_LOG_BYTES,
        "sha256": evidence.RECOVERY_2_OUTCOME_LOG_SHA256,
        "repository_commit": H_COMMIT,
        "physical_metadata_matches_h3_git_blob_size": True,
        "physical_contents_opened": False,
        "git_blob_command": copy.deepcopy(host_log_state["h_blob_command"]),
    }
    sealed_inputs = [
        *copy.deepcopy(inherited),
        copy.deepcopy(activation),
        copy.deepcopy(receipt),
        log_input,
        *copy.deepcopy(guards),
    ]
    return {
        "mode": evidence.RECOVERY_ATTEMPT_2,
        "repository_commit": H_COMMIT,
        "historical_chain": copy.deepcopy(evidence.RECOVERY_2_HISTORICAL_CHAIN),
        "outcome_access_log_state": (
            "present_exact_consumed_attempt_2_unopened_by_e10"
        ),
        "outcome_access_log": {
            "path": evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
            "bytes": evidence.RECOVERY_2_OUTCOME_LOG_BYTES,
            "record_count": 2,
            "sha256": evidence.RECOVERY_2_OUTCOME_LOG_SHA256,
            "source": "exact_h3_git_blob_and_host_lstat_without_host_content_open",
            "physical_contents_opened": False,
        },
        "host_outcome_log_state": host_log_state,
        "u2_activation": activation,
        "u2_activation_payload_sha256": evidence.RECOVERY_ACTIVATION_SHA256,
        "attempt_2_failure_receipt": receipt,
        "attempt_2_failure_receipt_payload_sha256": receipt["sha256"],
        "guard_records": guards,
        "guard_records_sha256": evidence._records_digest(guards),
        "inherited_p2_input_count": len(evidence.RECOVERY_2_INHERITED_P2_PATHS),
        "inherited_p1_input_count": len(evidence.RECOVERY_2_INHERITED_P1_PATHS),
        "inherited_inputs": inherited,
        "inherited_inputs_sha256": evidence._records_digest(inherited),
        "sealed_inputs": sealed_inputs,
        "sealed_inputs_sha256": evidence._records_digest(sealed_inputs),
        "p2_inputs_overwritten": False,
        "p1_inputs_overwritten": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
    }


def _filesystem_isolation(
    commands: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    restricted = [dict(spec) for spec in evidence.RESTRICTED_MASK_SPECS]
    return {
        "schema_version": "closure_e10_bubblewrap_exact_h_snapshot_masked_view_v1",
        "backend": evidence.BWRAP_BACKEND,
        "repository_commit": H_COMMIT,
        "worktree_path": "<WORK_DIRECTORY>/exact_h_snapshot",
        "worktree_pre_verification": _repository_state(),
        "worktree_post_verification": _repository_state(),
        "restricted_mask_tree_path": "<MASK_DIRECTORY>",
        "restricted_path_masks": restricted,
        "host_outcome_log_pre_verification": _host_outcome_log_state(),
        "host_outcome_log_post_verification": _host_outcome_log_state(),
        "tracked_empty_log_mask": {
            "path": evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
            "entry_type": "tracked_empty_file",
            "mode": "444",
            "bytes": 0,
            "single_link_regular_file": True,
            "probe_read_result": "synthetic_empty_eof",
            "host_path_opened": False,
        },
        "exact_h_snapshot": _exact_h_snapshot(commands),
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
        "isolated_command_names": list(
            evidence.BWRAP_ISOLATED_COMMAND_NAMES
        ),
        "execution_argv_template_prefix": evidence._bubblewrap_template(restricted),
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
        "denial_probe_results": evidence._expected_denial_probe_results(),
        "static_access_inventory": evidence.STATIC_ACCESS_INVENTORY,
    }


def _exact_h_snapshot(commands: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pointer_paths = [
        *(path.as_posix() for path in evidence.DVC_RESTORE_POINTERS),
        "models.dvc",
    ]
    pointer_paths.sort()
    dvc_records: list[dict[str, Any]] = [
        {
            "pointer_path": path,
            "pointer_bytes": 100,
            "pointer_sha256": "b" * 64,
            "output_path": "models" if path == "models.dvc" else path[:-4],
            "payload_md5": (
                "c" * 32 + ".dir" if path == "models.dvc" else "c" * 32
            ),
            "payload_bytes": 10,
            "payload_file_count": 1,
            "directory_output": path == "models.dvc",
            "declared_nfiles": 1 if path == "models.dvc" else None,
            "payload_sha256": None if path == "models.dvc" else "d" * 64,
            "output_initially_absent": True,
            "restored_from_local_cache": True,
        }
        for path in pointer_paths
    ]
    inventory_records: list[dict[str, Any]] = [
        {
            "path": "data/targets",
            "entry_type": "directory",
        },
        {
            "path": evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(),
            "entry_type": "regular_file",
            "bytes": 0,
            "sha256": evidence._sha256(b""),
        },
        {
            "path": "private/FULL.md",
            "entry_type": "regular_file",
            "bytes": 0,
            "sha256": evidence._sha256(b""),
        },
        {
            "path": evidence.BUILDER_SOURCE_PATH.as_posix(),
            "entry_type": "regular_file",
            "bytes": 1,
            "sha256": "a" * 64,
        }
    ]
    for record in dvc_records:
        inventory_records.append(
            {
                "path": record["pointer_path"],
                "entry_type": "regular_file",
                "bytes": record["pointer_bytes"],
                "sha256": record["pointer_sha256"],
            }
        )
        if record["directory_output"]:
            inventory_records.extend(
                [
                    {"path": record["output_path"], "entry_type": "directory"},
                    {
                        "path": f"{record['output_path']}/fixture.bin",
                        "entry_type": "regular_file",
                        "bytes": record["payload_bytes"],
                        "sha256": "f" * 64,
                    },
                ]
            )
        else:
            inventory_records.append(
                {
                    "path": record["output_path"],
                    "entry_type": "regular_file",
                    "bytes": record["payload_bytes"],
                    "sha256": record["payload_sha256"],
                }
            )
    inventory_records.sort(key=lambda record: cast(str, record["path"]))
    inventory = {
        "schema_version": "closure_e10_exact_h_snapshot_inventory_v1",
        "root_identity": {
            "device": 1,
            "inode": 2,
            "mode": "700",
            "nlink": 2,
            "mtime_ns": 3,
            "ctime_ns": 4,
        },
        "entry_count": len(inventory_records),
        "records_sha256": evidence._sha256(
            evidence._canonical_json(inventory_records)
        ),
        "records": inventory_records,
    }
    return {
        "schema_version": "closure_e10_materialized_exact_h_snapshot_v1",
        "repository_commit": H_COMMIT,
        "tracked_export": {
            "command": commands["exact_h_git_archive"],
            "archive_bytes": 100,
            "archive_sha256": "9" * 64,
            "restricted_pathspec_exclusions": list(
                evidence.FORBIDDEN_VERIFICATION_PREFIXES
            ),
            "tracked_tree_verification": {
                "command": commands["exact_h_tree_inventory"],
                "entry_count": 1,
                "listing_sha256": commands["exact_h_tree_inventory"][
                    "stdout_sha256"
                ],
                "all_nonrestricted_h_paths_and_blobs_exact": True,
            },
        },
        "dvc_restore": {
            "status": "passed",
            "mode": "all_permitted_exact_h_pointers_offline_local_cache_restore",
            "repository_commit": H_COMMIT,
            "network_used": False,
            "main_worktree_written": False,
            "inventory_command": commands["exact_h_dvc_inventory"],
            "pointer_count": len(pointer_paths),
            "restored_file_count": len(pointer_paths),
            "restored_bytes": 10 * len(pointer_paths),
            "records": dvc_records,
        },
        "pre_execution_inventory": inventory,
        "post_execution_inventory": copy.deepcopy(inventory),
        "source_worktree_written": False,
        "network_used": False,
    }


def _dvc_restore(commands: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "passed",
        "mode": "offline_local_dvc_cache_clean_restore",
        "network_used": False,
        "remote_pull_claimed": False,
        "pointer_count": 4,
        "records": [
            {
                "pointer_path": path.as_posix(),
                "pointer_bytes": 100,
                "pointer_sha256": "b" * 64,
                "output_path": path.with_suffix("").name,
                "payload_bytes": 10,
                "payload_md5": "c" * 32,
                "payload_sha256": "d" * 64,
                "destination_initially_absent_in_exact_h_snapshot": True,
                "restored_into_materialized_exact_h_snapshot": True,
            }
            for path in evidence.DVC_RESTORE_POINTERS
        ],
        "snapshot_inventory_command": commands["exact_h_dvc_inventory"],
    }


def _contract() -> dict[str, Any]:
    return {
        "valid": True,
        "openapi_path_count": 1,
        "openapi_operation_count": 1,
        "documented_operation_count": 2,
        "missing_documented_operations": [],
        "operation_ids_unique": True,
        "path_parameters_exact": True,
        "documents": [
            {
                "path": path.as_posix(),
                "bytes": 10,
                "sha256": "e" * 64,
                "documented_operation_count": 1,
            }
            for path in evidence.DOCUMENTED_API_PATHS
        ],
    }


def _fixture_bundle() -> tuple[dict[str, bytes], dict[str, Any]]:
    commands = _commands()
    dvc_restore = _dvc_restore(commands)
    target_cases = [
        (
            f"tests.{Path(nodeid.split('::', 1)[0]).stem}",
            nodeid.split("::", 1)[1],
            evidence.PUBLIC_PRE_E0U_EXCLUSION_REASON,
        )
        for nodeid in evidence.PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES
    ]
    git_cases = [
        (
            f"tests.{Path(nodeid.split('::', 1)[0]).stem}",
            nodeid.split("::", 1)[1],
            evidence.PUBLIC_USER_PROHIBITED_GIT_COMMIT_EXCLUSION_REASON,
        )
        for nodeid in evidence.PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES
    ]
    skipped_xml = "".join(
        f'<testcase classname="{classname}" name="{name}">'
        f'<skipped message="{reason}" />'
        "</testcase>"
        for classname, name, reason in [*target_cases, *git_cases]
    )
    passed_xml = "".join(
        f'<testcase classname="public.fixture" name="pass_{index:03d}" />'
        for index in range(evidence.PUBLIC_PHASE3_EXPECTED_PASS_COUNT)
    )
    public_raw = (
        '<testsuites><testsuite name="public" '
        f'tests="{evidence.PUBLIC_PHASE3_EXPECTED_TEST_COUNT}" failures="0" '
        f'errors="0" skipped="9">{passed_xml}'
        f"{skipped_xml}</testsuite></testsuites>"
    ).encode("utf-8")
    public_totals, public_skips = evidence._parse_junit(public_raw)
    public_skip_ledger = evidence._require_public_test_success(
        public_totals, public_skips
    )
    public_xml = evidence._inject_junit_commit(public_raw, H_COMMIT)
    e2e_totals = {"tests": 3, "failures": 0, "errors": 0, "skipped": 0}
    openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Fixture", "version": "1"},
        "paths": {
            "/health/live": {
                "get": {"operationId": "health_live", "responses": {"200": {"description": "ok"}}}
            }
        },
        "x-closure-e10-source-evidence": {
            "evidence_role": "openapi",
            "outcome_paths_opened": False,
            "private_full_opened": False,
            "repository_commit": H_COMMIT,
        },
    }
    openapi_bytes = evidence._pretty_json(openapi)
    test_report = evidence._build_test_report(
        commit=H_COMMIT,
        command=commands["public_tests"]["argv"],
        totals=public_totals,
        skip_ledger=public_skip_ledger,
        raw_junit_sha256="f" * 64,
        bound_junit_sha256=hashlib.sha256(public_xml).hexdigest(),
    )
    contract = _contract()
    contract_report = evidence._build_contract_report(
        commit=H_COMMIT,
        validation=contract,
        openapi_sha256=hashlib.sha256(openapi_bytes).hexdigest(),
    )
    e2e_report = evidence._build_e2e_report(
        commit=H_COMMIT,
        command=commands["end_to_end"]["argv"],
        totals=e2e_totals,
    )
    repository_state = _repository_state()
    environment_payload = {
        "schema_version": "closure_e10_environment_lock_runtime_v1",
        "repository_commit": H_COMMIT,
        "python": "3.14 fixture",
        "platform": "fixture-platform",
        "python_implementation": "CPython",
        "python_executable": ".venv/bin/python",
        "dependency_lock_sha256": "0" * 64,
        "dependency_lock_bytes": 10,
        "pyproject_sha256": "1" * 64,
        "pyproject_bytes": 10,
        "runtime": {"fastapi": "fixture", "torch": {"available": False}},
        "public_test_database": {
            "dialect": "postgresql_asyncpg",
            "test_database_url": commands["public_tests"]["environment_overrides"][
                "TEST_DATABASE_URL"
            ],
            "formerly_skipped_http_test_required": True,
            "ownership": {
                "schema_version": "closure_e10_owned_postgresql_fixture_v1",
                "host_scope": "loopback_only",
                "database_name": f"closure_e10_{'0' * 20}",
                "database_name_sha256": hashlib.sha256(
                    f"closure_e10_{'0' * 20}".encode("ascii")
                ).hexdigest(),
                "initially_absent": True,
                "created_exclusively_by_generator": True,
                "create_statement": f'CREATE DATABASE "closure_e10_{"0" * 20}"',
                "drop_statement": f'DROP DATABASE "closure_e10_{"0" * 20}"',
                "dropped_after_public_suite": True,
                "absent_after_cleanup": True,
            },
        },
        "tool_versions": {"git": "fixture"},
        "hardware": {"cpu_count": 1},
        "repository_pre_generation": repository_state,
        "repository_post_verification": repository_state,
        "lock_check": commands["poetry_lock_check"],
        "runtime_probe": commands["runtime_probe"],
        "version_commands": {
            key: commands[key]
            for key in (
                "python_version",
                "poetry_version",
                "pytest_version",
                "dvc_version",
                "git_version",
            )
        },
        "dvc_restore_verification": dvc_restore,
        "filesystem_isolation": _filesystem_isolation(commands),
        "outcome_safety": {
            **evidence.E2E_FIXTURE_CONTRACT,
            "guard_enabled": True,
            **evidence._public_suite_contract_record(),
            "pre_e0u_excluded_test_bases": list(
                evidence.PUBLIC_PRE_E0U_EXCLUDED_TEST_BASES
            ),
            "pre_e0u_excluded_test_nodes": list(
                evidence.PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES
            ),
            "pre_e0u_exclusion_reason": evidence.PUBLIC_PRE_E0U_EXCLUSION_REASON,
            "user_prohibited_git_commit_test_nodes": list(
                evidence.PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES
            ),
            "user_prohibited_git_commit_exclusion_reason": (
                evidence.PUBLIC_USER_PROHIBITED_GIT_COMMIT_EXCLUSION_REASON
            ),
            "target_paths_opened": False,
            "outcome_paths_opened": False,
        },
        "generated_at_utc": "2026-08-14T00:00:00+00:00",
    }
    artifacts = {
        "public_tests_xml": public_xml,
        "test_report": test_report,
        "openapi": openapi_bytes,
        "openapi_contract_report": contract_report,
        "end_to_end_report": e2e_report,
        "environment": evidence._pretty_json(environment_payload),
    }
    manifest = evidence.build_closure_e10_source_manifest(
        repository_commit=H_COMMIT,
        artifacts=artifacts,
        repository_state=repository_state,
        commands=commands,
        public_totals=public_totals,
        public_skip_ledger=public_skip_ledger,
        e2e_totals=e2e_totals,
        contract_validation=contract,
        dvc_restore=dvc_restore,
        filesystem_isolation=_filesystem_isolation(commands),
        generated_at_utc="2026-08-14T00:00:00+00:00",
    )
    return artifacts, manifest


def _fixture_recovery_bundle() -> tuple[dict[str, bytes], dict[str, Any]]:
    artifacts, initial_manifest = _fixture_bundle()
    commands = _commands()
    isolation = _filesystem_isolation(commands)
    recovery_host_log = _recovery_host_outcome_log_state()
    isolation["host_outcome_log_pre_verification"] = copy.deepcopy(
        recovery_host_log
    )
    isolation["host_outcome_log_post_verification"] = copy.deepcopy(
        recovery_host_log
    )
    environment = json.loads(artifacts["environment"])
    environment["filesystem_isolation"] = copy.deepcopy(isolation)
    artifacts["environment"] = evidence._pretty_json(environment)
    verification = initial_manifest["verification"]
    recovery = _recovery_record()
    manifest = evidence.build_closure_e10_source_manifest(
        repository_commit=H_COMMIT,
        artifacts=artifacts,
        repository_state=_repository_state(),
        commands=commands,
        public_totals=verification["public_tests"],
        public_skip_ledger=verification["public_skip_ledger"],
        e2e_totals=verification["end_to_end_tests"],
        contract_validation=verification["openapi_contract"],
        dvc_restore=verification["dvc_restore"],
        filesystem_isolation=isolation,
        generated_at_utc="2026-08-16T00:00:00+00:00",
        recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
        recovery=recovery,
    )
    return artifacts, manifest


def _fixture_recovery_2_bundle() -> tuple[dict[str, bytes], dict[str, Any]]:
    artifacts, initial_manifest = _fixture_bundle()
    commands = _commands()
    isolation = _filesystem_isolation(commands)
    recovery_host_log = _recovery_2_host_outcome_log_state()
    isolation["host_outcome_log_pre_verification"] = copy.deepcopy(
        recovery_host_log
    )
    isolation["host_outcome_log_post_verification"] = copy.deepcopy(
        recovery_host_log
    )
    environment = json.loads(artifacts["environment"])
    environment["filesystem_isolation"] = copy.deepcopy(isolation)
    artifacts["environment"] = evidence._pretty_json(environment)
    verification = initial_manifest["verification"]
    recovery = _recovery_2_record()
    manifest = evidence.build_closure_e10_source_manifest(
        repository_commit=H_COMMIT,
        artifacts=artifacts,
        repository_state=_repository_state(),
        commands=commands,
        public_totals=verification["public_tests"],
        public_skip_ledger=verification["public_skip_ledger"],
        e2e_totals=verification["end_to_end_tests"],
        contract_validation=verification["openapi_contract"],
        dvc_restore=verification["dvc_restore"],
        filesystem_isolation=isolation,
        generated_at_utc="2026-08-16T01:00:00+00:00",
        recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
        recovery=recovery,
    )
    return artifacts, manifest


def _repository_layout(root: Path) -> None:
    (root / "reports/closure_v1/00_protocol").mkdir(parents=True)
    (root / "reports/closure_v1/00_protocol/outcome_access_log.jsonl").write_bytes(b"")
    (root / "tmp").mkdir()


def _publish_fixture_bundle(
    *,
    root: Path,
    work: Path,
    artifacts: dict[str, bytes],
    manifest: dict[str, Any],
    recovery_attempt: str | None = None,
) -> dict[str, Any]:
    work_meta = work.lstat()
    work_identity = (work_meta.st_dev, work_meta.st_ino)
    guard = evidence._acquire_guard(root)
    try:
        result = evidence.publish_closure_e10_source_bundle(
            repo_root=root,
            work_directory=work,
            artifacts=artifacts,
            manifest=manifest,
            expected_h_commit=H_COMMIT,
            owned_guard=guard,
            recovery_attempt=recovery_attempt,
        )
        assert guard.removed is True
        return result
    finally:
        if work.name not in guard.removed_work_names:
            guard.remove_owned_work_directory(
                name=work.name,
                identity=work_identity,
                context="fixture publication work cleanup",
            )
        guard.close()


def test_source_namespace_is_distinct_and_loader_api_is_exact() -> None:
    assert evidence.SOURCE_EVIDENCE_DIRECTORY == Path(
        "reports/closure_v1/00_protocol/software_evidence_source"
    )
    assert evidence.SOURCE_MANIFEST_PATH == (
        evidence.SOURCE_EVIDENCE_DIRECTORY
        / "software_evidence_source_manifest.json"
    )
    assert set(evidence.SOURCE_EVIDENCE_PATHS) == {
        "public_tests_xml",
        "test_report",
        "openapi",
        "openapi_contract_report",
        "end_to_end_report",
        "environment",
    }
    assert not any(
        str(path).startswith(str(evidence.FINAL_E10_DIRECTORY))
        for path in evidence.SOURCE_EVIDENCE_PATHS.values()
    )
    assert evidence.RECOVERY_ATTEMPT_1 == "recovery-attempt-1"
    assert evidence.RECOVERY_SOURCE_EVIDENCE_DIRECTORY == Path(
        "reports/closure_v1/00_protocol/software_evidence_source_recovery_1"
    )
    assert evidence.RECOVERY_SOURCE_MANIFEST_PATH == (
        evidence.RECOVERY_SOURCE_EVIDENCE_DIRECTORY
        / "software_evidence_source_manifest.json"
    )
    assert len(evidence.RECOVERY_SOURCE_EVIDENCE_PATHS) == 6
    assert len(evidence.RECOVERY_INHERITED_P1_PATHS) == 10
    assert evidence.RECOVERY_ATTEMPT_2 == "recovery-attempt-2"
    assert evidence.RECOVERY_2_ACTIVATION_PATH == Path(
        "reports/closure_v1/00_protocol/closure_e0_u_recovery_2_activation.json"
    )
    assert evidence.RECOVERY_2_SOURCE_EVIDENCE_DIRECTORY == Path(
        "reports/closure_v1/00_protocol/software_evidence_source_recovery_2"
    )
    assert evidence.RECOVERY_2_SOURCE_MANIFEST_PATH == (
        evidence.RECOVERY_2_SOURCE_EVIDENCE_DIRECTORY
        / "software_evidence_source_manifest.json"
    )
    assert len(evidence.RECOVERY_2_SOURCE_EVIDENCE_PATHS) == 6
    assert len(evidence.RECOVERY_2_INHERITED_P2_PATHS) == 7
    assert len(evidence.RECOVERY_2_INHERITED_P1_PATHS) == 3
    assert len(evidence.RECOVERY_2_INHERITED_PATHS) == 10
    parsed = evidence._parser().parse_args(
        [
            "--check-only",
            "--repository-commit",
            H_COMMIT,
            "--recovery-attempt-1",
        ]
    )
    assert parsed.check_only is True
    assert parsed.recovery_attempt_1 is True
    parsed_2 = evidence._parser().parse_args(
        [
            "--check-only",
            "--repository-commit",
            H_COMMIT,
            "--recovery-attempt-2",
        ]
    )
    assert parsed_2.check_only is True
    assert parsed_2.recovery_attempt_2 is True
    with pytest.raises(SystemExit):
        evidence._parser().parse_args(
            [
                "--check-only",
                "--repository-commit",
                H_COMMIT,
                "--recovery-attempt-1",
                "--recovery-attempt-2",
            ]
        )


def test_pure_payload_validation_returns_exact_e10_dialect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts, manifest = _fixture_bundle()

    assert manifest["status"] == "completed"
    assert manifest["publication_status"] == "source_evidence_written_unpublished"
    assert manifest["script"] == manifest["repository_pre_generation"][
        "builder_source"
    ]
    assert manifest["inputs"] == []
    assert manifest["outputs"] == manifest["source_artifacts"]
    assert manifest["publication"]["canonical_cleanup_atomic_capture"] == (
        "renameat2_noreplace_random_tombstone_fd_verified"
    )
    assert manifest["publication"]["cleanup_concurrency_model"] == (
        "single_writer_after_atomic_tombstone_capture"
    )
    assert manifest["publication"]["same_uid_tombstone_interference_in_scope"] is False

    loaded = evidence.validate_closure_e10_source_payloads(
        artifacts=artifacts,
        manifest=manifest,
        expected_h_commit=H_COMMIT,
    )

    assert set(loaded) == set(evidence.SOURCE_EVIDENCE_KEYS)
    assert loaded["test_report"]["status"] == "passed"
    assert loaded["test_report"]["test_count"] == (
        evidence.PUBLIC_PHASE3_EXPECTED_TEST_COUNT
    )
    assert loaded["test_report"]["skipped_count"] == 9
    assert loaded["openapi_contract_report"]["valid"] is True
    assert loaded["end_to_end_report"]["workflow_successful"] is True
    assert loaded["environment"]["repository_commit"] == H_COMMIT

    recovery_artifacts, recovery_manifest = _fixture_recovery_bundle()
    recovery_loaded = evidence.validate_closure_e10_source_payloads(
        artifacts=recovery_artifacts,
        manifest=recovery_manifest,
        expected_h_commit=H_COMMIT,
        recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
    )
    assert set(recovery_loaded) == set(evidence.SOURCE_EVIDENCE_KEYS)
    assert recovery_loaded["test_report"]["test_count"] == 347
    assert recovery_loaded["test_report"]["skipped_count"] == 9
    assert recovery_manifest["recovery_attempt"] == "recovery-attempt-1"
    assert len(recovery_manifest["inputs"]) == 12
    assert [record["path"] for record in recovery_manifest["outputs"]] == [
        evidence.RECOVERY_SOURCE_EVIDENCE_PATHS[key].as_posix()
        for key in evidence.SOURCE_EVIDENCE_KEYS
    ]
    assert recovery_manifest["recovery"]["p1_inputs_overwritten"] is False
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="manifest keys",
    ):
        evidence.validate_closure_e10_source_payloads(
            artifacts=recovery_artifacts,
            manifest=recovery_manifest,
            expected_h_commit=H_COMMIT,
        )
    changed_recovery = copy.deepcopy(recovery_manifest)
    changed_recovery["recovery"]["outcome_access_log_prefix"]["sha256"] = "0" * 64
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="recovery manifest identity",
    ):
        evidence.validate_closure_e10_source_payloads(
            artifacts=recovery_artifacts,
            manifest=changed_recovery,
            expected_h_commit=H_COMMIT,
            recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
        )

    recovery_2_artifacts, recovery_2_manifest = _fixture_recovery_2_bundle()
    recovery_2_loaded = evidence.validate_closure_e10_source_payloads(
        artifacts=recovery_2_artifacts,
        manifest=recovery_2_manifest,
        expected_h_commit=H_COMMIT,
        recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
    )
    assert set(recovery_2_loaded) == set(evidence.SOURCE_EVIDENCE_KEYS)
    assert recovery_2_manifest["schema_version"] == (
        evidence.RECOVERY_2_SCHEMA_VERSION
    )
    assert recovery_2_manifest["recovery_attempt"] == "recovery-attempt-2"
    assert len(recovery_2_manifest["inputs"]) == 15
    assert [record["path"] for record in recovery_2_manifest["outputs"]] == [
        evidence.RECOVERY_2_SOURCE_EVIDENCE_PATHS[key].as_posix()
        for key in evidence.SOURCE_EVIDENCE_KEYS
    ]
    assert recovery_2_manifest["recovery"]["p2_inputs_overwritten"] is False
    assert recovery_2_manifest["recovery"]["p1_inputs_overwritten"] is False
    changed_recovery_2 = copy.deepcopy(recovery_2_manifest)
    changed_recovery_2["recovery"]["guard_records"][1]["inode"] += 1
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="retained guard records",
    ):
        evidence.validate_closure_e10_source_payloads(
            artifacts=recovery_2_artifacts,
            manifest=changed_recovery_2,
            expected_h_commit=H_COMMIT,
            recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
        )
    changed_historical = copy.deepcopy(recovery_2_manifest)
    changed_historical["recovery"]["inherited_inputs"][0][
        "historical_repository_commit"
    ] = OTHER_COMMIT
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="historical Git input binding drifted",
    ):
        evidence.validate_closure_e10_source_payloads(
            artifacts=recovery_2_artifacts,
            manifest=changed_historical,
            expected_h_commit=H_COMMIT,
            recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
        )
    changed_receipt = json.loads(_attempt_2_receipt_payload())
    changed_receipt["failure"]["publication_started"] = True
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="diagnosis drifted",
    ):
        evidence._validate_attempt_2_failure_receipt(
            evidence._canonical_json(changed_receipt)
        )

    def git_bound_input(
        root: Path,
        commit: str,
        path: Path,
        *,
        role: str,
    ) -> dict[str, Any]:
        del root
        if path == evidence.ATTEMPT_1_FAILURE_RECEIPT_PATH:
            bytes_count = evidence.ATTEMPT_1_FAILURE_RECEIPT_BYTES
            digest = evidence.ATTEMPT_1_FAILURE_RECEIPT_SHA256
        else:
            bytes_count = 10
            digest = hashlib.sha256(path.as_posix().encode()).hexdigest()
        return {
            "path": path.as_posix(),
            "role": role,
            "bytes": bytes_count,
            "sha256": digest,
            "repository_commit": commit,
            "physical_equals_h2_git_blob": True,
            "git_blob_command": _command(
                ["git", "show", f"{commit}:{path.as_posix()}"],
                {"GIT_OPTIONAL_LOCKS": "0"},
            ),
        }

    monkeypatch.setattr(evidence, "_git_bound_recovery_input_record", git_bound_input)
    monkeypatch.setattr(
        evidence,
        "_capture_host_outcome_log_state",
        lambda root, commit, *, recovery_attempt=None: (
            _recovery_2_host_outcome_log_state()
            if recovery_attempt == evidence.RECOVERY_ATTEMPT_2
            else _recovery_host_outcome_log_state()
        ),
    )
    collected_recovery = evidence._collect_recovery_attempt_1_record(
        evidence.PROJECT_ROOT,
        H_COMMIT,
    )
    assert collected_recovery["inherited_p1_input_count"] == 10
    assert collected_recovery["attempt_1_failure_receipt"]["bytes"] == 1501
    assert collected_recovery["outcome_paths_opened"] is False

    receipt_payload = _attempt_2_receipt_payload()
    original_read_regular = evidence._read_regular

    def read_recovery_2_input(
        path: Path,
        *,
        repo_root: Path,
        context: str,
    ) -> bytes:
        if path == evidence.ATTEMPT_2_FAILURE_RECEIPT_PATH:
            return receipt_payload
        return original_read_regular(path, repo_root=repo_root, context=context)

    def git_bound_recovery_2_input(
        root: Path,
        commit: str,
        path: Path,
        *,
        role: str,
    ) -> dict[str, Any]:
        del root
        if path == evidence.RECOVERY_ACTIVATION_PATH:
            bytes_count = evidence.RECOVERY_ACTIVATION_BYTES
            digest = evidence.RECOVERY_ACTIVATION_SHA256
        elif path == evidence.ATTEMPT_2_FAILURE_RECEIPT_PATH:
            bytes_count = len(receipt_payload)
            digest = hashlib.sha256(receipt_payload).hexdigest()
        else:
            bytes_count = 10
            digest = hashlib.sha256(path.as_posix().encode()).hexdigest()
        return {
            "path": path.as_posix(),
            "role": role,
            "bytes": bytes_count,
            "sha256": digest,
            "repository_commit": commit,
            "physical_equals_h3_git_blob": True,
            "git_blob_command": _command(
                ["git", "show", f"{commit}:{path.as_posix()}"],
                {"GIT_OPTIONAL_LOCKS": "0"},
            ),
        }

    def git_bound_recovery_2_historical_input(
        root: Path,
        commit: str,
        historical_commit: str,
        path: Path,
        *,
        role: str,
    ) -> dict[str, Any]:
        record = git_bound_recovery_2_input(
            root,
            commit,
            path,
            role=role,
        )
        return {
            **record,
            "historical_repository_commit": historical_commit,
            "physical_equals_historical_git_blob": True,
            "historical_git_blob_command": _command(
                ["git", "show", f"{historical_commit}:{path.as_posix()}"],
                {"GIT_OPTIONAL_LOCKS": "0"},
            ),
        }

    monkeypatch.setattr(evidence, "_read_regular", read_recovery_2_input)
    monkeypatch.setattr(
        evidence,
        "_git_bound_recovery_2_input_record",
        git_bound_recovery_2_input,
    )
    monkeypatch.setattr(
        evidence,
        "_git_bound_recovery_2_historical_input_record",
        git_bound_recovery_2_historical_input,
    )
    monkeypatch.setattr(
        evidence,
        "_capture_recovery_2_guard_records",
        lambda root: copy.deepcopy(_recovery_2_record()["guard_records"]),
    )
    collected_recovery_2 = evidence._collect_recovery_attempt_2_record(
        evidence.PROJECT_ROOT,
        H_COMMIT,
    )
    assert collected_recovery_2["inherited_p2_input_count"] == 7
    assert collected_recovery_2["inherited_p1_input_count"] == 3
    assert collected_recovery_2["attempt_2_failure_receipt"]["bytes"] == len(
        receipt_payload
    )
    assert collected_recovery_2["guard_records"] == (
        _recovery_2_record()["guard_records"]
    )
    assert collected_recovery_2["outcome_paths_opened"] is False


def test_filesystem_denial_probe_and_read_only_policy_are_fail_closed() -> None:
    commands = _commands()
    policy = _filesystem_isolation(commands)

    evidence._validate_filesystem_isolation(
        policy,
        repository_commit=H_COMMIT,
        commands=commands,
    )
    recovery_2_policy = copy.deepcopy(policy)
    recovery_2_log = _recovery_2_host_outcome_log_state()
    recovery_2_policy["host_outcome_log_pre_verification"] = copy.deepcopy(
        recovery_2_log
    )
    recovery_2_policy["host_outcome_log_post_verification"] = copy.deepcopy(
        recovery_2_log
    )
    evidence._validate_filesystem_isolation(
        recovery_2_policy,
        repository_commit=H_COMMIT,
        commands=commands,
        recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
    )
    changed_recovery_2_policy = copy.deepcopy(recovery_2_policy)
    changed_recovery_2_policy["host_outcome_log_pre_verification"][
        "h_blob_command"
    ]["stdout_line_count"] = 1
    changed_recovery_2_policy["host_outcome_log_post_verification"] = (
        copy.deepcopy(
            changed_recovery_2_policy["host_outcome_log_pre_verification"]
        )
    )
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="host outcome-log H command drifted",
    ):
        evidence._validate_filesystem_isolation(
            changed_recovery_2_policy,
            repository_commit=H_COMMIT,
            commands=commands,
            recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
        )

    changed = copy.deepcopy(policy)
    changed["denial_probe_results"][0]["read_errno"] = 0
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="denial probe result drifted",
    ):
        evidence._validate_filesystem_isolation(
            changed,
            repository_commit=H_COMMIT,
            commands=commands,
        )

    changed = copy.deepcopy(policy)
    changed["execution_argv_template_prefix"].insert(-1, "--unexpected")
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="argv template drifted",
    ):
        evidence._validate_filesystem_isolation(
            changed,
            repository_commit=H_COMMIT,
            commands=commands,
        )


def test_final_e10_consumer_revalidates_exact_h_and_operational_bindings() -> None:
    artifacts, manifest = _fixture_bundle()
    loaded = evidence.validate_closure_e10_source_payloads(
        artifacts=artifacts,
        manifest=manifest,
        expected_h_commit=H_COMMIT,
    )

    _, totals = final_evidence._validate_junit(
        loaded["public_tests_xml"], expected_h_commit=H_COMMIT
    )
    final_evidence._validate_test_report(
        loaded["test_report"],
        junit_totals=totals,
        expected_h_commit=H_COMMIT,
    )
    openapi = final_evidence._validate_openapi(
        loaded["openapi"], expected_h_commit=H_COMMIT
    )
    final_evidence._validate_contract_report(
        loaded["openapi_contract_report"],
        expected_h_commit=H_COMMIT,
        openapi=openapi,
    )
    final_evidence._validate_e2e(
        loaded["end_to_end_report"], expected_h_commit=H_COMMIT
    )
    final_evidence._validate_environment(
        loaded["environment"], expected_h_commit=H_COMMIT
    )


def test_public_environment_validator_is_pure_and_reconstructs_four_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts, _ = _fixture_bundle()
    environment = json.loads(artifacts["environment"])

    def forbidden_io(*args: object, **kwargs: object) -> Any:
        del args, kwargs
        raise AssertionError("pure environment validation attempted I/O")

    monkeypatch.setattr(evidence, "_run", forbidden_io)
    monkeypatch.setattr(evidence, "_read_regular", forbidden_io)
    validated = evidence.validate_closure_e10_environment_payload(
        environment,
        expected_h_commit=H_COMMIT,
    )
    commands = evidence._environment_exact_h_commands(
        environment["filesystem_isolation"],
        repository_commit=H_COMMIT,
    )

    assert validated == environment
    assert set(commands) == {
        "filesystem_denial_probe",
        "exact_h_git_archive",
        "exact_h_tree_inventory",
        "exact_h_dvc_inventory",
    }


def test_public_environment_validator_rejects_cross_bindings() -> None:
    artifacts, _ = _fixture_bundle()
    environment = json.loads(artifacts["environment"])
    changed_dvc = copy.deepcopy(environment)
    changed_dvc["dvc_restore_verification"]["records"][0][
        "payload_sha256"
    ] = "e" * 64

    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="does not match exact-H snapshot",
    ):
        evidence.validate_closure_e10_environment_payload(
            changed_dvc,
            expected_h_commit=H_COMMIT,
        )

    changed_database = copy.deepcopy(environment)
    changed_database["public_test_database"]["ownership"][
        "absent_after_cleanup"
    ] = False
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="PostgreSQL evidence drifted",
    ):
        evidence.validate_closure_e10_environment_payload(
            changed_database,
            expected_h_commit=H_COMMIT,
        )

    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="identity drifted",
    ):
        evidence.validate_closure_e10_environment_payload(
            environment,
            expected_h_commit=OTHER_COMMIT,
        )


def test_final_e10_consumer_rejects_cross_commit_environment() -> None:
    artifacts, manifest = _fixture_bundle()
    loaded = evidence.validate_closure_e10_source_payloads(
        artifacts=artifacts,
        manifest=manifest,
        expected_h_commit=H_COMMIT,
    )
    environment = copy.deepcopy(loaded["environment"])
    environment["repository_commit"] = OTHER_COMMIT

    with pytest.raises(
        final_evidence.ClosureEvidenceMatrixError,
        match="source-bound E10 environment validation failed",
    ):
        final_evidence._validate_environment(
            environment, expected_h_commit=H_COMMIT
        )


@pytest.mark.parametrize(
    "key",
    [
        "public_tests_xml",
        "test_report",
        "openapi",
        "openapi_contract_report",
        "end_to_end_report",
        "environment",
    ],
)
def test_each_source_blob_must_embed_exact_h_even_if_manifest_is_rehashed(
    key: str,
) -> None:
    artifacts, manifest = _fixture_bundle()
    mutated = dict(artifacts)
    if key == "openapi":
        value = json.loads(mutated[key])
        value["x-closure-e10-source-evidence"]["repository_commit"] = OTHER_COMMIT
        mutated[key] = evidence._pretty_json(value)
    elif key == "environment":
        value = json.loads(mutated[key])
        value["repository_commit"] = OTHER_COMMIT
        mutated[key] = evidence._pretty_json(value)
    else:
        mutated[key] = mutated[key].replace(
            H_COMMIT.encode("ascii"), OTHER_COMMIT.encode("ascii")
        )
    rebuilt = evidence.build_closure_e10_source_manifest(
        repository_commit=H_COMMIT,
        artifacts=mutated,
        repository_state=manifest["repository_pre_generation"],
        commands=manifest["verification"]["commands"],
        public_totals=manifest["verification"]["public_tests"],
        public_skip_ledger=manifest["verification"]["public_skip_ledger"],
        e2e_totals=manifest["verification"]["end_to_end_tests"],
        contract_validation=manifest["verification"]["openapi_contract"],
        dvc_restore=manifest["verification"]["dvc_restore"],
        filesystem_isolation=manifest["verification"]["filesystem_isolation"],
        generated_at_utc=manifest["generated_at_utc"],
    )

    with pytest.raises(evidence.ClosureE10SourceEvidenceError):
        evidence.validate_closure_e10_source_payloads(
            artifacts=mutated,
            manifest=rebuilt,
            expected_h_commit=H_COMMIT,
        )


def test_check_only_is_zero_write_and_does_not_launch_suites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test-user:test-password@127.0.0.1/closure_e10",
    )
    monkeypatch.setattr(
        evidence,
        "_collect_exact_h_repository_state",
        lambda root, commit: _repository_state(),
    )
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    result = evidence.check_closure_e10_source_evidence(
        repo_root=tmp_path,
        expected_h_commit=H_COMMIT,
    )

    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert before == after
    assert result["status"] == "ready_to_generate"
    assert result["writes_performed"] is False
    assert result["verification_commands_run"] is False
    assert result["dvc_commands_run"] is False
    assert result["public_test_database_configured"] is True
    assert result["target_paths_opened"] is False
    assert result["outcome_paths_opened"] is False

    for directory, paths, manifest_path in (
        (
            evidence.SOURCE_EVIDENCE_DIRECTORY,
            evidence.SOURCE_EVIDENCE_PATHS,
            evidence.SOURCE_MANIFEST_PATH,
        ),
        (
            evidence.RECOVERY_SOURCE_EVIDENCE_DIRECTORY,
            evidence.RECOVERY_SOURCE_EVIDENCE_PATHS,
            evidence.RECOVERY_SOURCE_MANIFEST_PATH,
        ),
    ):
        bundle = tmp_path / directory
        bundle.mkdir()
        for path in paths.values():
            (bundle / path.name).write_bytes(b"fixture")
        (bundle / manifest_path.name).write_bytes(b"fixture")
    (tmp_path / evidence.OUTCOME_ACCESS_LOG_PATH).write_bytes(
        b"x" * evidence.RECOVERY_2_OUTCOME_LOG_BYTES
    )
    namespace_before = sorted(
        path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")
    )
    evidence._require_pre_generation_namespace(
        tmp_path,
        recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
    )
    assert namespace_before == sorted(
        path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")
    )
    extra = (
        tmp_path / evidence.RECOVERY_SOURCE_EVIDENCE_DIRECTORY / "extra.json"
    )
    extra.write_bytes(b"{}")
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="not exact seven",
    ):
        evidence._require_pre_generation_namespace(
            tmp_path,
            recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
        )
    extra.unlink()

    monkeypatch.setattr(
        evidence,
        "_require_pre_generation_namespace",
        lambda root, *, recovery_attempt=None: None,
    )
    monkeypatch.setattr(
        evidence,
        "_collect_recovery_attempt_1_record",
        lambda root, commit: _recovery_record(),
    )
    monkeypatch.setattr(
        evidence,
        "_collect_recovery_attempt_2_record",
        lambda root, commit: _recovery_2_record(),
    )
    recovery_result = evidence.check_closure_e10_source_evidence(
        repo_root=tmp_path,
        expected_h_commit=H_COMMIT,
        recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
    )
    assert recovery_result["recovery_attempt"] == "recovery-attempt-1"
    assert recovery_result["outcome_access_log_state"] == (
        "present_exact_consumed_attempt_1_unopened_by_e10"
    )
    assert recovery_result["manifest_path"] == (
        evidence.RECOVERY_SOURCE_MANIFEST_PATH.as_posix()
    )
    assert recovery_result["writes_performed"] is False
    recovery_2_result = evidence.check_closure_e10_source_evidence(
        repo_root=tmp_path,
        expected_h_commit=H_COMMIT,
        recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
    )
    assert recovery_2_result["recovery_attempt"] == "recovery-attempt-2"
    assert recovery_2_result["outcome_access_log_state"] == (
        "present_exact_consumed_attempt_2_unopened_by_e10"
    )
    assert recovery_2_result["manifest_path"] == (
        evidence.RECOVERY_2_SOURCE_MANIFEST_PATH.as_posix()
    )
    assert recovery_2_result["writes_performed"] is False


def test_publication_is_exclusive_manifest_last_and_loadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}test"
    work.mkdir()
    artifacts, manifest = _fixture_bundle()
    order: list[str] = []
    original = evidence._link_exclusive_at

    def recording_link(
        source_fd: int, source_name: str, target_fd: int, target_name: str
    ) -> tuple[int, int]:
        order.append(target_name)
        return original(source_fd, source_name, target_fd, target_name)

    monkeypatch.setattr(evidence, "_link_exclusive_at", recording_link)
    result = _publish_fixture_bundle(
        root=tmp_path,
        work=work,
        artifacts=artifacts,
        manifest=manifest,
    )

    assert result["source_artifact_count"] == 6
    assert order[-1] == evidence.SOURCE_MANIFEST_PATH.name
    published = tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY
    assert sorted(path.name for path in published.iterdir()) == sorted(
        [
            *(path.name for path in evidence.SOURCE_EVIDENCE_PATHS.values()),
            evidence.SOURCE_MANIFEST_PATH.name,
        ]
    )
    assert all(path.stat().st_nlink == 1 for path in published.iterdir())

    def subprocess_forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"sealed loader launched a subprocess: {args} {kwargs}")

    monkeypatch.setattr(evidence, "_git", subprocess_forbidden)
    monkeypatch.setattr(evidence, "_run", subprocess_forbidden)
    loaded = evidence.load_closure_e10_software_evidence(
        repo_root=tmp_path,
        expected_h_commit=H_COMMIT,
        require_git_publication=False,
    )
    assert set(loaded) == set(evidence.SOURCE_EVIDENCE_KEYS)
    loaded_with_snapshot = evidence.load_closure_e10_software_evidence(
        repo_root=tmp_path,
        expected_h_commit=H_COMMIT,
        require_git_publication=False,
        include_source_snapshot=True,
    )
    assert loaded_with_snapshot["software_evidence"] == loaded
    snapshot = loaded_with_snapshot["source_snapshot"]
    assert snapshot["repository_commit"] == H_COMMIT
    assert snapshot["file_count"] == 7
    assert [record["path"] for record in snapshot["files"]] == [
        *(path.as_posix() for path in evidence.SOURCE_EVIDENCE_PATHS.values()),
        evidence.SOURCE_MANIFEST_PATH.as_posix(),
    ]
    assert snapshot["bundle_sha256"] == hashlib.sha256(
        evidence._canonical_json(snapshot["files"])
    ).hexdigest()

    original_bytes = {
        path.name: path.read_bytes() for path in published.iterdir()
    }
    work.mkdir()
    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="already exists"):
        _publish_fixture_bundle(
            root=tmp_path,
            work=work,
            artifacts=artifacts,
            manifest=manifest,
        )
    assert original_bytes == {
        path.name: path.read_bytes() for path in published.iterdir()
    }

    recovery_artifacts, recovery_manifest = _fixture_recovery_bundle()
    (tmp_path / evidence.OUTCOME_ACCESS_LOG_PATH).write_bytes(
        b"x" * evidence.RECOVERY_OUTCOME_LOG_BYTES
    )
    (tmp_path / evidence.OUTCOME_ACCESS_LOG_PATH).chmod(0o644)
    monkeypatch.setattr(
        evidence,
        "_capture_host_outcome_log_state",
        lambda root, commit, *, recovery_attempt=None: (
            _recovery_2_host_outcome_log_state()
            if recovery_attempt == evidence.RECOVERY_ATTEMPT_2
            else _recovery_host_outcome_log_state()
        ),
    )
    monkeypatch.setattr(
        evidence,
        "_collect_recovery_attempt_1_record",
        lambda root, commit: _recovery_record(),
    )
    order.clear()
    work.mkdir()
    recovery_result = _publish_fixture_bundle(
        root=tmp_path,
        work=work,
        artifacts=recovery_artifacts,
        manifest=recovery_manifest,
        recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
    )
    assert recovery_result["status"] == (
        "source_evidence_recovery_written_unpublished"
    )
    assert recovery_result["recovery_attempt"] == "recovery-attempt-1"
    assert order[-1] == evidence.RECOVERY_SOURCE_MANIFEST_PATH.name
    recovery_published = tmp_path / evidence.RECOVERY_SOURCE_EVIDENCE_DIRECTORY
    assert len(list(recovery_published.iterdir())) == 7
    assert original_bytes == {
        path.name: path.read_bytes() for path in published.iterdir()
    }
    recovery_loaded = evidence.load_closure_e10_software_evidence(
        repo_root=tmp_path,
        expected_h_commit=H_COMMIT,
        require_git_publication=False,
        recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
    )
    assert set(recovery_loaded) == set(evidence.SOURCE_EVIDENCE_KEYS)
    auto_recovery_loaded = evidence.load_closure_e10_software_evidence(
        repo_root=tmp_path,
        expected_h_commit=H_COMMIT,
        require_git_publication=False,
    )
    assert auto_recovery_loaded == recovery_loaded

    recovery_bytes = {
        path.name: path.read_bytes() for path in recovery_published.iterdir()
    }
    recovery_2_artifacts, recovery_2_manifest = _fixture_recovery_2_bundle()
    (tmp_path / evidence.OUTCOME_ACCESS_LOG_PATH).write_bytes(
        b"x" * evidence.RECOVERY_2_OUTCOME_LOG_BYTES
    )
    monkeypatch.setattr(
        evidence,
        "_collect_recovery_attempt_2_record",
        lambda root, commit: _recovery_2_record(),
    )
    order.clear()
    work.mkdir()
    recovery_2_result = _publish_fixture_bundle(
        root=tmp_path,
        work=work,
        artifacts=recovery_2_artifacts,
        manifest=recovery_2_manifest,
        recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
    )
    assert recovery_2_result["status"] == (
        "source_evidence_recovery_written_unpublished"
    )
    assert recovery_2_result["recovery_attempt"] == "recovery-attempt-2"
    assert order[-1] == evidence.RECOVERY_2_SOURCE_MANIFEST_PATH.name
    recovery_2_published = (
        tmp_path / evidence.RECOVERY_2_SOURCE_EVIDENCE_DIRECTORY
    )
    assert len(list(recovery_2_published.iterdir())) == 7
    assert recovery_bytes == {
        path.name: path.read_bytes() for path in recovery_published.iterdir()
    }
    recovery_2_loaded = evidence.load_closure_e10_software_evidence(
        repo_root=tmp_path,
        expected_h_commit=H_COMMIT,
        require_git_publication=False,
        recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
    )
    assert set(recovery_2_loaded) == set(evidence.SOURCE_EVIDENCE_KEYS)
    auto_recovery_2_loaded = evidence.load_closure_e10_software_evidence(
        repo_root=tmp_path,
        expected_h_commit=H_COMMIT,
        require_git_publication=False,
    )
    assert auto_recovery_2_loaded == recovery_2_loaded


def test_owned_postgresql_fixture_is_fresh_unique_and_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Connection:
        exists = False
        statements: list[str] = []

        async def fetchval(self, query: str, database_name: str) -> int | None:
            del query, database_name
            return 1 if self.exists else None

        async def execute(self, query: str, *args: object) -> str:
            del args
            self.statements.append(query)
            if query.startswith("CREATE DATABASE"):
                self.exists = True
            elif query.startswith("DROP DATABASE"):
                self.exists = False
            return "OK"

        async def close(self) -> None:
            return None

    connection = Connection()

    class Asyncpg:
        async def connect(self, url: str) -> Connection:
            assert url.endswith("/postgres")
            return connection

    monkeypatch.setitem(sys.modules, "asyncpg", Asyncpg())
    base_url = (
        "postgresql+asyncpg://fixture-user:fixture-password@127.0.0.1/"
        "closure_e10"
    )
    owned_url, ownership = evidence._create_owned_postgresql_database(
        base_url,
        repository_commit=H_COMMIT,
        run_name="fixture-run",
    )

    assert owned_url.endswith(f"/{ownership['database_name']}")
    assert ownership["initially_absent"] is True
    assert connection.exists is True
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="unexpectedly exists",
    ):
        evidence._create_owned_postgresql_database(
            base_url,
            repository_commit=H_COMMIT,
            run_name="fixture-run",
        )

    cleaned = evidence._drop_owned_postgresql_database(base_url, ownership)

    assert connection.exists is False
    assert cleaned["dropped_after_public_suite"] is True
    assert cleaned["absent_after_cleanup"] is True


def test_owned_postgresql_duplicate_create_never_drops_foreign_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DuplicateDatabaseCollision(Exception):
        pass

    class Connection:
        exists = False
        statements: list[str] = []

        async def fetchval(self, query: str, database_name: str) -> int | None:
            del query, database_name
            return 1 if self.exists else None

        async def execute(self, query: str, *args: object) -> str:
            del args
            self.statements.append(query)
            if query.startswith("CREATE DATABASE"):
                # Model another actor winning between the absence check and
                # this CREATE.  The resulting database is not generator-owned.
                self.exists = True
                raise DuplicateDatabaseCollision("duplicate database")
            if query.startswith("DROP DATABASE"):
                self.exists = False
            return "OK"

        async def close(self) -> None:
            return None

    connection = Connection()

    class Asyncpg:
        DuplicateDatabaseError = DuplicateDatabaseCollision

        async def connect(self, url: str) -> Connection:
            assert url.endswith("/postgres")
            return connection

    monkeypatch.setitem(sys.modules, "asyncpg", Asyncpg())
    base_url = (
        "postgresql+asyncpg://fixture-user:fixture-password@127.0.0.1/"
        "closure_e10"
    )

    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="creation failed",
    ):
        evidence._create_owned_postgresql_database(
            base_url,
            repository_commit=H_COMMIT,
            run_name="duplicate-fixture-run",
        )

    assert connection.exists is True
    assert not any(
        statement.startswith("DROP DATABASE")
        for statement in connection.statements
    )


def test_sealed_loader_recaptures_all_seven_entries_across_bundle_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}recapture"
    work.mkdir()
    artifacts, manifest = _fixture_bundle()
    _publish_fixture_bundle(
        root=tmp_path,
        work=work,
        artifacts=artifacts,
        manifest=manifest,
    )
    first_path = tmp_path / evidence.SOURCE_EVIDENCE_PATHS["public_tests_xml"]
    original = evidence._read_regular_from_directory_fd

    def replace_after_manifest(
        name: str,
        *,
        directory_fd: int,
        context: str,
        require_nlink_one: bool,
    ) -> tuple[bytes, tuple[int, ...]]:
        result = original(
            name,
            directory_fd=directory_fd,
            context=context,
            require_nlink_one=require_nlink_one,
        )
        if name == evidence.SOURCE_MANIFEST_PATH.name:
            first_path.unlink()
            first_path.write_bytes(artifacts["public_tests_xml"])
        return result

    monkeypatch.setattr(
        evidence, "_read_regular_from_directory_fd", replace_after_manifest
    )
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="changed across the seven-file read",
    ):
        evidence.load_closure_e10_software_evidence(
            repo_root=tmp_path,
            expected_h_commit=H_COMMIT,
            require_git_publication=False,
        )


def test_sealed_loader_rejects_symlinked_source_file(
    tmp_path: Path,
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}symlink"
    work.mkdir()
    artifacts, manifest = _fixture_bundle()
    _publish_fixture_bundle(
        root=tmp_path,
        work=work,
        artifacts=artifacts,
        manifest=manifest,
    )
    target = tmp_path / evidence.SOURCE_EVIDENCE_PATHS["public_tests_xml"]
    replacement = tmp_path / "replacement.xml"
    replacement.write_bytes(artifacts["public_tests_xml"])
    target.unlink()
    target.symlink_to(replacement)

    with pytest.raises(evidence.ClosureE10SourceEvidenceError):
        evidence.load_closure_e10_software_evidence(
            repo_root=tmp_path,
            expected_h_commit=H_COMMIT,
            require_git_publication=False,
        )


def test_git_publication_binds_same_initial_seven_file_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}same_capture"
    work.mkdir()
    artifacts, manifest = _fixture_bundle()
    builder_payload = b"x"
    lock_payload = b"lock-bytes"
    project_payload = b"project-bytes"
    builder_record = {
        "path": evidence.BUILDER_SOURCE_PATH.as_posix(),
        "bytes": len(builder_payload),
        "sha256": hashlib.sha256(builder_payload).hexdigest(),
        "physical_equals_h_blob": True,
    }
    manifest["script"] = copy.deepcopy(builder_record)
    manifest["repository_pre_generation"]["builder_source"] = copy.deepcopy(
        builder_record
    )
    manifest["verification"]["repository_post_verification"][
        "builder_source"
    ] = copy.deepcopy(builder_record)
    isolation = manifest["verification"]["filesystem_isolation"]
    isolation["worktree_pre_verification"]["builder_source"] = copy.deepcopy(
        builder_record
    )
    isolation["worktree_post_verification"]["builder_source"] = copy.deepcopy(
        builder_record
    )
    snapshot_inventory = isolation["exact_h_snapshot"][
        "pre_execution_inventory"
    ]
    snapshot_builder = next(
        record
        for record in snapshot_inventory["records"]
        if record["path"] == evidence.BUILDER_SOURCE_PATH.as_posix()
    )
    snapshot_builder["bytes"] = len(builder_payload)
    snapshot_builder["sha256"] = hashlib.sha256(builder_payload).hexdigest()
    snapshot_inventory["records_sha256"] = evidence._sha256(
        evidence._canonical_json(snapshot_inventory["records"])
    )
    isolation["exact_h_snapshot"]["post_execution_inventory"] = copy.deepcopy(
        snapshot_inventory
    )
    environment = json.loads(artifacts["environment"])
    environment["repository_pre_generation"]["builder_source"] = copy.deepcopy(
        builder_record
    )
    environment["repository_post_verification"]["builder_source"] = copy.deepcopy(
        builder_record
    )
    environment["filesystem_isolation"] = copy.deepcopy(isolation)
    environment["dependency_lock_bytes"] = len(lock_payload)
    environment["dependency_lock_sha256"] = hashlib.sha256(lock_payload).hexdigest()
    environment["pyproject_bytes"] = len(project_payload)
    environment["pyproject_sha256"] = hashlib.sha256(project_payload).hexdigest()
    artifacts["environment"] = evidence._pretty_json(environment)
    records = [
        evidence._source_record(key, artifacts[key], H_COMMIT)
        for key in evidence.SOURCE_EVIDENCE_KEYS
    ]
    manifest["outputs"] = copy.deepcopy(records)
    manifest["source_artifacts"] = records
    manifest["source_artifacts_sha256"] = evidence._records_digest(records)
    _publish_fixture_bundle(
        root=tmp_path,
        work=work,
        artifacts=artifacts,
        manifest=manifest,
    )
    original_load = evidence._load_source_files
    captured_payloads = {
        path: artifacts[key]
        for key, path in evidence.SOURCE_EVIDENCE_PATHS.items()
    }
    captured_payloads[evidence.SOURCE_MANIFEST_PATH] = evidence._pretty_json(manifest)

    def capture_then_swap(
        root: Path,
    ) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
        loaded = original_load(root)
        swapped = root / evidence.SOURCE_EVIDENCE_PATHS["public_tests_xml"]
        swapped.unlink()
        swapped.write_bytes(b"replacement after capture")
        return loaded

    def fake_git(root: Path, *args: str) -> str:
        del root
        if args[:2] == ("branch", "--show-current"):
            return "main"
        if args and args[0] == "status":
            return ""
        if args[:2] == ("merge-base", "--is-ancestor"):
            return ""
        return OTHER_COMMIT

    def fake_run(
        argv: object, *, repo_root: Path, **kwargs: object
    ) -> tuple[dict[str, Any], str, str]:
        del repo_root, kwargs
        command = list(cast(Any, argv))
        spec = command[-1]
        if command[:3] == ["git", "ls-files", "--stage"]:
            return (
                {},
                f"100644 {evidence.EMPTY_GIT_BLOB_SHA1} 0\t"
                f"{evidence.OUTCOME_ACCESS_LOG_PATH.as_posix()}\n",
                "",
            )
        if spec == f"{H_COMMIT}:{evidence.BUILDER_SOURCE_PATH.as_posix()}":
            payload = builder_payload
        elif spec == f"{H_COMMIT}:poetry.lock":
            payload = lock_payload
        elif spec == f"{H_COMMIT}:pyproject.toml":
            payload = project_payload
        elif spec == f"{H_COMMIT}:{evidence.OUTCOME_ACCESS_LOG_PATH.as_posix()}":
            payload = b""
        elif isinstance(spec, str) and spec.startswith(f"{OTHER_COMMIT}:"):
            payload = captured_payloads[
                Path(spec.removeprefix(f"{OTHER_COMMIT}:"))
            ]
        else:
            raise AssertionError(command)
        return ({}, payload.decode("utf-8"), "")

    monkeypatch.setattr(evidence, "_load_source_files", capture_then_swap)
    monkeypatch.setattr(evidence, "_git", fake_git)
    monkeypatch.setattr(evidence, "_run", fake_run)

    loaded = evidence.load_closure_e10_software_evidence(
        repo_root=tmp_path,
        expected_h_commit=H_COMMIT,
        require_git_publication=True,
    )

    assert set(loaded) == set(evidence.SOURCE_EVIDENCE_KEYS)


def test_publication_failure_rolls_back_only_owned_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}rollback"
    work.mkdir()
    artifacts, manifest = _fixture_bundle()
    original = evidence._link_exclusive_at
    calls = 0

    def fail_third(
        source_fd: int, source_name: str, target_fd: int, target_name: str
    ) -> tuple[int, int]:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise evidence.ClosureE10SourceEvidenceError("synthetic link failure")
        return original(source_fd, source_name, target_fd, target_name)

    monkeypatch.setattr(evidence, "_link_exclusive_at", fail_third)
    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="synthetic"):
        _publish_fixture_bundle(
            root=tmp_path,
            work=work,
            artifacts=artifacts,
            manifest=manifest,
        )

    assert not os.path.lexists(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
    assert (tmp_path / evidence.OUTCOME_ACCESS_LOG_PATH).stat().st_size == 0


def test_staged_cleanup_failure_after_seven_links_rolls_back_final_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}staged_cleanup"
    work.mkdir()
    work_meta = work.lstat()
    work_identity = (work_meta.st_dev, work_meta.st_ino)
    artifacts, manifest = _fixture_bundle()
    guard = evidence._acquire_guard(tmp_path)
    original_remove = evidence._remove_owned_name_atomic
    linked_names: list[str] = []
    original_link = evidence._link_exclusive_at
    staged_cleanup_reached = False

    def record_link(
        source_fd: int, source_name: str, target_fd: int, target_name: str
    ) -> tuple[int, int]:
        linked_names.append(target_name)
        return original_link(source_fd, source_name, target_fd, target_name)

    def fail_after_exact_staged_cleanup(
        directory_fd: int,
        name: str,
        identity: tuple[int, int],
        *,
        context: str,
        missing_is_error: bool,
        owned_fd: int | None = None,
        expected_directory: bool = False,
    ) -> None:
        nonlocal staged_cleanup_reached
        original_remove(
            directory_fd,
            name,
            identity,
            context=context,
            missing_is_error=missing_is_error,
            owned_fd=owned_fd,
            expected_directory=expected_directory,
        )
        if context == "staged publication cleanup":
            staged_cleanup_reached = True
            raise evidence.ClosureE10SourceEvidenceError(
                "synthetic staged publication cleanup postcheck failure"
            )

    monkeypatch.setattr(evidence, "_link_exclusive_at", record_link)
    monkeypatch.setattr(
        evidence, "_remove_owned_name_atomic", fail_after_exact_staged_cleanup
    )
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="rollback/cleanup failed closed",
        ):
            evidence.publish_closure_e10_source_bundle(
                repo_root=tmp_path,
                work_directory=work,
                artifacts=artifacts,
                manifest=manifest,
                expected_h_commit=H_COMMIT,
                owned_guard=guard,
            )
        assert staged_cleanup_reached is True
        assert linked_names == [
            *(path.name for path in evidence.SOURCE_EVIDENCE_PATHS.values()),
            evidence.SOURCE_MANIFEST_PATH.name,
        ]
        assert guard.removed is True
        assert not os.path.lexists(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
        assert not os.path.lexists(work / "publication")
        assert work.name in guard.removed_work_names
        assert not os.path.lexists(work)
    finally:
        guard.close()

    assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
    assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))


def test_work_cleanup_failure_after_seven_links_rolls_back_final_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}work_cleanup"
    work.mkdir()
    artifacts, manifest = _fixture_bundle()
    guard = evidence._acquire_guard(tmp_path)
    original_remove_work = guard.remove_owned_work_directory
    original_link = evidence._link_exclusive_at
    linked_names: list[str] = []
    work_cleanup_reached = False

    def record_link(
        source_fd: int, source_name: str, target_fd: int, target_name: str
    ) -> tuple[int, int]:
        linked_names.append(target_name)
        return original_link(source_fd, source_name, target_fd, target_name)

    def fail_after_exact_work_cleanup(
        *, name: str, identity: tuple[int, int], context: str
    ) -> None:
        nonlocal work_cleanup_reached
        original_remove_work(name=name, identity=identity, context=context)
        if context == "source publication work cleanup":
            work_cleanup_reached = True
            raise evidence.ClosureE10SourceEvidenceError(
                "synthetic source publication work cleanup postcheck failure"
            )

    monkeypatch.setattr(evidence, "_link_exclusive_at", record_link)
    monkeypatch.setattr(
        guard, "remove_owned_work_directory", fail_after_exact_work_cleanup
    )
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="rollback/cleanup failed closed",
        ):
            evidence.publish_closure_e10_source_bundle(
                repo_root=tmp_path,
                work_directory=work,
                artifacts=artifacts,
                manifest=manifest,
                expected_h_commit=H_COMMIT,
                owned_guard=guard,
            )
        assert work_cleanup_reached is True
        assert linked_names == [
            *(path.name for path in evidence.SOURCE_EVIDENCE_PATHS.values()),
            evidence.SOURCE_MANIFEST_PATH.name,
        ]
        assert guard.removed is True
        assert work.name in guard.removed_work_names
        assert not os.path.lexists(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
        assert not os.path.lexists(work)
    finally:
        guard.close()

    assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
    assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))


def test_predelete_work_cleanup_fault_retries_before_releasing_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}work_predelete_once"
    work.mkdir()
    artifacts, manifest = _fixture_bundle()
    guard = evidence._acquire_guard(tmp_path)
    original_remove_work = guard.remove_owned_work_directory
    original_unlink_guard = guard.unlink_strict
    cleanup_contexts: list[str] = []
    guard_cleanup_contexts: list[str] = []

    def fail_first_work_cleanup(
        *, name: str, identity: tuple[int, int], context: str
    ) -> None:
        cleanup_contexts.append(context)
        if len(cleanup_contexts) == 1:
            raise evidence.ClosureE10SourceEvidenceError(
                "synthetic pre-delete work cleanup failure"
            )
        original_remove_work(name=name, identity=identity, context=context)

    def require_work_absent_before_guard_release(*, context: str) -> None:
        assert work.name in guard.removed_work_names
        assert not os.path.lexists(work)
        guard_cleanup_contexts.append(context)
        original_unlink_guard(context=context)

    monkeypatch.setattr(
        guard, "remove_owned_work_directory", fail_first_work_cleanup
    )
    monkeypatch.setattr(
        guard, "unlink_strict", require_work_absent_before_guard_release
    )
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="rollback/cleanup failed closed",
        ):
            evidence.publish_closure_e10_source_bundle(
                repo_root=tmp_path,
                work_directory=work,
                artifacts=artifacts,
                manifest=manifest,
                expected_h_commit=H_COMMIT,
                owned_guard=guard,
            )
        assert cleanup_contexts == [
            "source publication work cleanup",
            "source publication outer work cleanup",
        ]
        assert guard_cleanup_contexts == [
            "source publication outer guard cleanup"
        ]
        assert guard.removed is True
        assert not os.path.lexists(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
        assert not os.path.lexists(work)
    finally:
        guard.close()

    assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
    assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))


def test_persistent_predelete_work_cleanup_fault_preserves_guard_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}work_predelete_persistent"
    work.mkdir()
    work_meta = work.lstat()
    work_identity = (work_meta.st_dev, work_meta.st_ino)
    artifacts, manifest = _fixture_bundle()
    guard = evidence._acquire_guard(tmp_path)
    original_remove_work = guard.remove_owned_work_directory

    def fail_every_work_cleanup(
        *, name: str, identity: tuple[int, int], context: str
    ) -> None:
        del name, identity, context
        raise evidence.ClosureE10SourceEvidenceError(
            "synthetic persistent pre-delete work cleanup failure"
        )

    monkeypatch.setattr(
        guard, "remove_owned_work_directory", fail_every_work_cleanup
    )
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="guard/work cleanup failed closed",
        ):
            evidence.publish_closure_e10_source_bundle(
                repo_root=tmp_path,
                work_directory=work,
                artifacts=artifacts,
                manifest=manifest,
                expected_h_commit=H_COMMIT,
                owned_guard=guard,
            )
        assert guard.removed is False
        assert work.name not in guard.removed_work_names
        assert os.path.isdir(work)
        assert not os.path.lexists(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
        guard.require_exact(
            repository_root=tmp_path,
            context="persistent work-cleanup fault retained lease",
        )
        monkeypatch.setattr(
            guard, "remove_owned_work_directory", original_remove_work
        )
        guard.remove_owned_work_directory(
            name=work.name,
            identity=work_identity,
            context="persistent work-cleanup fault recovery",
        )
        guard.unlink_strict(
            context="persistent work-cleanup fault guard recovery"
        )
    finally:
        guard.close()

    assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
    assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))


def test_descriptor_close_error_after_commit_is_best_effort_not_false_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}close_fault"
    work.mkdir()
    artifacts, manifest = _fixture_bundle()
    guard = evidence._acquire_guard(tmp_path)
    guard_descriptor = guard.guard_fd
    original_close = os.close
    close_fault_raised = False

    def close_then_raise_once(fd: int) -> None:
        nonlocal close_fault_raised
        original_close(fd)
        if guard.removed and fd != guard_descriptor and not close_fault_raised:
            close_fault_raised = True
            raise OSError("synthetic descriptor close postcondition failure")

    monkeypatch.setattr(os, "close", close_then_raise_once)
    try:
        result = evidence.publish_closure_e10_source_bundle(
            repo_root=tmp_path,
            work_directory=work,
            artifacts=artifacts,
            manifest=manifest,
            expected_h_commit=H_COMMIT,
            owned_guard=guard,
        )
        assert result["status"] == "source_evidence_written_unpublished"
        assert close_fault_raised is True
        assert guard.removed is True
        assert work.name in guard.removed_work_names
    finally:
        guard.close()

    assert os.path.isdir(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
    assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
    assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))


def test_work_descriptor_close_error_cannot_strand_guard_after_work_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}work_close_fault"
    work.mkdir()
    artifacts, manifest = _fixture_bundle()
    guard = evidence._acquire_guard(tmp_path)
    original_open = os.open
    original_close = os.close
    work_descriptors: list[int] = []
    close_fault_raised = False

    def record_work_descriptor(*args: Any, **kwargs: Any) -> int:
        fd = original_open(*args, **kwargs)
        if (
            args
            and args[0] == work.name
            and kwargs.get("dir_fd") == guard.tmp_fd
        ):
            work_descriptors.append(fd)
        return fd

    def close_then_raise_for_retained_work_descriptor(fd: int) -> None:
        nonlocal close_fault_raised
        original_close(fd)
        if (
            not close_fault_raised
            and len(work_descriptors) >= 2
            and fd == work_descriptors[-1]
        ):
            close_fault_raised = True
            raise OSError("synthetic retained-work descriptor close failure")

    monkeypatch.setattr(os, "open", record_work_descriptor)
    monkeypatch.setattr(os, "close", close_then_raise_for_retained_work_descriptor)
    try:
        result = evidence.publish_closure_e10_source_bundle(
            repo_root=tmp_path,
            work_directory=work,
            artifacts=artifacts,
            manifest=manifest,
            expected_h_commit=H_COMMIT,
            owned_guard=guard,
        )
        assert result["status"] == "source_evidence_written_unpublished"
        assert close_fault_raised is True
        assert guard.removed is True
        assert work.name in guard.removed_work_names
    finally:
        guard.close()

    assert os.path.isdir(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
    assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
    assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))


def test_mask_cleanup_failure_prevents_publication_and_leaves_no_mask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    work = tmp_path / "tmp" / f"{evidence.WORK_PREFIX}mask_cleanup"
    work.mkdir()
    work_meta = work.lstat()
    work_identity = (work_meta.st_dev, work_meta.st_ino)
    artifacts, manifest = _fixture_bundle()
    guard = evidence._acquire_guard(tmp_path)
    mask_path = Path(
        tempfile.mkdtemp(prefix=evidence.MASK_WORK_PREFIX, dir="/tmp")
    ).resolve()
    mask_meta = mask_path.lstat()
    mask_work = evidence.OwnedMaskWorkDirectory(
        mask_path, (mask_meta.st_dev, mask_meta.st_ino)
    )
    evidence._create_restricted_mask_tree(mask_path)
    original_mask_remove = mask_work.remove
    publisher_called = False

    def fail_after_exact_mask_cleanup() -> None:
        original_mask_remove()
        raise evidence.ClosureE10SourceEvidenceError(
            "synthetic mask cleanup postcheck failure"
        )

    def record_forbidden_publication(**kwargs: object) -> dict[str, Any]:
        nonlocal publisher_called
        publisher_called = True
        raise AssertionError(f"publication ran after mask cleanup failure: {kwargs}")

    monkeypatch.setattr(mask_work, "remove", fail_after_exact_mask_cleanup)
    monkeypatch.setattr(
        evidence, "publish_closure_e10_source_bundle", record_forbidden_publication
    )
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="synthetic mask cleanup postcheck failure",
        ):
            evidence._publish_verified_e10_source_bundle(
                repo_root=tmp_path,
                work_directory=work,
                mask_work=mask_work,
                artifacts=artifacts,
                manifest=manifest,
                expected_h_commit=H_COMMIT,
                owned_guard=guard,
            )
        assert publisher_called is False
        assert mask_work.removed is True
        assert not os.path.lexists(mask_path)
        assert not os.path.lexists(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
        guard.require_exact(
            repository_root=tmp_path,
            context="synthetic post-mask-cleanup failure",
        )
        guard.remove_owned_work_directory(
            name=work.name,
            identity=work_identity,
            context="synthetic mask-cleanup failure work cleanup",
        )
        guard.unlink_strict(context="synthetic mask-cleanup failure guard cleanup")
    finally:
        guard.close()

    assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
    assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))


@pytest.mark.parametrize("replacement_kind", ["directory", "regular", "symlink"])
def test_mask_cleanup_atomic_capture_restores_boundary_replacement(
    monkeypatch: pytest.MonkeyPatch,
    replacement_kind: str,
) -> None:
    mask_path = Path(
        tempfile.mkdtemp(prefix=evidence.MASK_WORK_PREFIX, dir="/tmp")
    ).resolve()
    mask_metadata = mask_path.lstat()
    mask_identity = (mask_metadata.st_dev, mask_metadata.st_ino)
    evidence._create_restricted_mask_tree(mask_path)
    owned_moved = Path(
        tempfile.mkdtemp(
            prefix=f"{evidence.MASK_WORK_PREFIX}boundary_owned_",
            dir="/tmp",
        )
    ).resolve()
    owned_moved.rmdir()
    original_rename = evidence._rename_noreplace_at
    captured_tombstones: list[Path] = []
    replaced_at_boundary = False

    def replace_canonical_before_mask_capture(
        source_directory_fd: int,
        source_name: str,
        target_directory_fd: int,
        target_name: str,
    ) -> None:
        nonlocal replaced_at_boundary
        if source_name == mask_path.name and not replaced_at_boundary:
            captured_tombstones.append(Path("/tmp") / target_name)
            os.rename(
                source_name,
                owned_moved.name,
                src_dir_fd=source_directory_fd,
                dst_dir_fd=source_directory_fd,
            )
            if replacement_kind == "directory":
                mask_path.mkdir(mode=0o700)
                (mask_path / "foreign.marker").write_bytes(
                    b"foreign mask replacement\n"
                )
            elif replacement_kind == "regular":
                mask_path.write_bytes(b"foreign regular mask replacement\n")
            else:
                mask_path.symlink_to("foreign-dangling-mask-target")
            replaced_at_boundary = True
        original_rename(
            source_directory_fd,
            source_name,
            target_directory_fd,
            target_name,
        )

    monkeypatch.setattr(
        evidence, "_rename_noreplace_at", replace_canonical_before_mask_capture
    )
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="foreign entry was restored",
        ):
            evidence._safe_remove_mask_work_directory(mask_path, mask_identity)
        assert replaced_at_boundary is True
        if replacement_kind == "directory":
            assert (mask_path / "foreign.marker").read_bytes() == (
                b"foreign mask replacement\n"
            )
        elif replacement_kind == "regular":
            assert mask_path.read_bytes() == b"foreign regular mask replacement\n"
        else:
            assert mask_path.is_symlink()
            assert os.readlink(mask_path) == "foreign-dangling-mask-target"
        evidence._validate_restricted_mask_tree(
            owned_moved / "restricted_mask_tree"
        )
        assert len(captured_tombstones) == 1
        assert not os.path.lexists(captured_tombstones[0])
    finally:
        monkeypatch.setattr(evidence, "_rename_noreplace_at", original_rename)
        if os.path.lexists(owned_moved):
            evidence._safe_remove_mask_work_directory(
                owned_moved,
                mask_identity,
            )
        if os.path.lexists(mask_path):
            if mask_path.is_symlink() or mask_path.is_file():
                mask_path.unlink()
            else:
                shutil.rmtree(mask_path)


def test_owned_guard_missing_leaf_is_a_strict_cleanup_error(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    _repository_layout(root)
    guard = evidence._acquire_guard(root)
    guard_path = root / evidence.GUARD_PATH
    guard_path.unlink()

    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="missing during cleanup",
        ):
            guard.unlink_strict(context="synthetic missing-guard cleanup")
        assert guard.removed is False
        assert not os.path.lexists(guard_path)
    finally:
        guard.close()


def test_owned_guard_replacement_is_rejected_and_not_deleted(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    _repository_layout(root)
    guard = evidence._acquire_guard(root)
    guard_path = root / evidence.GUARD_PATH
    guard_path.unlink()
    guard_path.write_bytes(b"foreign replacement\n")

    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="replaced during cleanup",
        ):
            guard.unlink_strict(context="synthetic replaced-guard cleanup")
        assert guard.removed is False
        assert guard_path.read_bytes() == b"foreign replacement\n"
    finally:
        guard.close()
        guard_path.unlink()


def test_owned_guard_atomic_cleanup_restores_boundary_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    _repository_layout(root)
    guard = evidence._acquire_guard(root)
    guard_path = root / evidence.GUARD_PATH
    original_rename = evidence._rename_noreplace_at
    replaced_at_boundary = False

    def replace_immediately_before_atomic_rename(
        source_directory_fd: int,
        source_name: str,
        target_directory_fd: int,
        target_name: str,
    ) -> None:
        nonlocal replaced_at_boundary
        if source_name == evidence.GUARD_PATH.name and not replaced_at_boundary:
            os.unlink(source_name, dir_fd=source_directory_fd)
            replacement_fd = os.open(
                source_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=source_directory_fd,
            )
            try:
                os.write(replacement_fd, b"foreign at rename boundary\n")
                os.fsync(replacement_fd)
            finally:
                os.close(replacement_fd)
            replaced_at_boundary = True
        original_rename(
            source_directory_fd,
            source_name,
            target_directory_fd,
            target_name,
        )

    monkeypatch.setattr(
        evidence, "_rename_noreplace_at", replace_immediately_before_atomic_rename
    )
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="foreign entry was restored",
        ):
            guard.unlink_strict(context="synthetic guard boundary cleanup")
        assert replaced_at_boundary is True
        assert guard.removed is False
        assert guard_path.read_bytes() == b"foreign at rename boundary\n"
        assert not list((root / "tmp").glob(".closure_e10_owned_cleanup_*"))
    finally:
        guard.close()
        guard_path.unlink()


def test_publisher_owned_entry_cleanup_restores_boundary_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "publication"
    directory.mkdir()
    owned = directory / "artifact.json"
    owned.write_bytes(b"owned")
    owned_meta = owned.lstat()
    identity = (owned_meta.st_dev, owned_meta.st_ino)
    directory_fd = os.open(
        directory,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    original_rename = evidence._rename_noreplace_at
    replaced_at_boundary = False

    def replace_immediately_before_atomic_rename(
        source_directory_fd: int,
        source_name: str,
        target_directory_fd: int,
        target_name: str,
    ) -> None:
        nonlocal replaced_at_boundary
        if source_name == owned.name and not replaced_at_boundary:
            os.unlink(source_name, dir_fd=source_directory_fd)
            replacement_fd = os.open(
                source_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=source_directory_fd,
            )
            try:
                os.write(replacement_fd, b"foreign publication entry")
                os.fsync(replacement_fd)
            finally:
                os.close(replacement_fd)
            replaced_at_boundary = True
        original_rename(
            source_directory_fd,
            source_name,
            target_directory_fd,
            target_name,
        )

    monkeypatch.setattr(
        evidence, "_rename_noreplace_at", replace_immediately_before_atomic_rename
    )
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="foreign entry was restored",
        ):
            evidence._unlink_owned_at(directory_fd, owned.name, identity)
        assert replaced_at_boundary is True
        assert owned.read_bytes() == b"foreign publication entry"
        assert not list(directory.glob(".closure_e10_owned_cleanup_*"))
    finally:
        os.close(directory_fd)


@pytest.mark.parametrize("replacement", [False, True])
def test_guard_leaf_drift_during_publish_rolls_back_every_owned_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement: bool,
) -> None:
    root = tmp_path / "repository"
    _repository_layout(root)
    work = root / "tmp" / f"{evidence.WORK_PREFIX}guard_drift"
    work.mkdir()
    work_meta = work.lstat()
    work_identity = (work_meta.st_dev, work_meta.st_ino)
    guard = evidence._acquire_guard(root)
    guard_path = root / evidence.GUARD_PATH
    artifacts, manifest = _fixture_bundle()
    original_link = evidence._link_exclusive_at
    mutated = False

    def mutate_guard_after_first_link(
        source_fd: int, source_name: str, target_fd: int, target_name: str
    ) -> tuple[int, int]:
        nonlocal mutated
        identity = original_link(source_fd, source_name, target_fd, target_name)
        if not mutated:
            mutated = True
            guard_path.unlink()
            if replacement:
                guard_path.write_bytes(b"foreign replacement\n")
        return identity

    monkeypatch.setattr(evidence, "_link_exclusive_at", mutate_guard_after_first_link)
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="guard/work cleanup failed closed",
        ):
            evidence.publish_closure_e10_source_bundle(
                repo_root=root,
                work_directory=work,
                artifacts=artifacts,
                manifest=manifest,
                expected_h_commit=H_COMMIT,
                owned_guard=guard,
            )
        assert mutated is True
        assert guard.removed is False
        assert work.name in guard.removed_work_names
        assert not os.path.lexists(work)
    finally:
        guard.close()

    assert not os.path.lexists(root / evidence.SOURCE_EVIDENCE_DIRECTORY)
    assert not list((root / "tmp").glob(f"{evidence.WORK_PREFIX}*"))
    if replacement:
        assert guard_path.read_bytes() == b"foreign replacement\n"
        guard_path.unlink()
    else:
        assert not os.path.lexists(guard_path)


def test_root_swap_between_guard_and_publish_leaves_no_owned_temp_or_bundle(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    displaced_root = tmp_path / "repository-displaced"
    _repository_layout(root)
    guard = evidence._acquire_guard(root)
    work, _ = guard.create_work_directory(
        context="synthetic pre-publication work allocation"
    )
    artifacts, manifest = _fixture_bundle()
    root.rename(displaced_root)
    _repository_layout(root)

    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="guard/work cleanup failed closed",
        ):
            evidence.publish_closure_e10_source_bundle(
                repo_root=root,
                work_directory=work,
                artifacts=artifacts,
                manifest=manifest,
                expected_h_commit=H_COMMIT,
                owned_guard=guard,
            )
        assert guard.removed is True
        assert work.name in guard.removed_work_names
    finally:
        guard.close()

    for candidate_root in (root, displaced_root):
        assert not os.path.lexists(
            candidate_root / evidence.SOURCE_EVIDENCE_DIRECTORY
        )
        assert not os.path.lexists(candidate_root / evidence.GUARD_PATH)
        assert not list(
            (candidate_root / "tmp").glob(f"{evidence.WORK_PREFIX}*")
        )


def test_root_swap_during_publish_rolls_back_bundle_in_both_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    displaced_root = tmp_path / "repository-displaced"
    _repository_layout(root)
    work = root / "tmp" / f"{evidence.WORK_PREFIX}root_swap"
    work.mkdir()
    guard = evidence._acquire_guard(root)
    artifacts, manifest = _fixture_bundle()
    original_link = evidence._link_exclusive_at
    swapped = False

    def swap_root_after_first_link(
        source_fd: int, source_name: str, target_fd: int, target_name: str
    ) -> tuple[int, int]:
        nonlocal swapped
        identity = original_link(source_fd, source_name, target_fd, target_name)
        if not swapped:
            swapped = True
            root.rename(displaced_root)
            _repository_layout(root)
        return identity

    monkeypatch.setattr(evidence, "_link_exclusive_at", swap_root_after_first_link)
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="rollback/cleanup failed closed",
        ):
            evidence.publish_closure_e10_source_bundle(
                repo_root=root,
                work_directory=work,
                artifacts=artifacts,
                manifest=manifest,
                expected_h_commit=H_COMMIT,
                owned_guard=guard,
            )
        assert swapped is True
        assert guard.removed is True
        assert work.name in guard.removed_work_names
    finally:
        guard.close()

    for candidate_root in (root, displaced_root):
        assert not os.path.lexists(
            candidate_root / evidence.SOURCE_EVIDENCE_DIRECTORY
        )
        assert not os.path.lexists(candidate_root / evidence.GUARD_PATH)
        assert not list(
            (candidate_root / "tmp").glob(f"{evidence.WORK_PREFIX}*")
        )


def test_root_swap_immediately_after_guard_cleanup_rolls_back_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    displaced_root = tmp_path / "repository-displaced"
    _repository_layout(root)
    work = root / "tmp" / f"{evidence.WORK_PREFIX}cleanup_swap"
    work.mkdir()
    guard = evidence._acquire_guard(root)
    artifacts, manifest = _fixture_bundle()
    original_unlink = guard.unlink_strict
    swapped = False

    def unlink_then_swap(*, context: str) -> None:
        nonlocal swapped
        original_unlink(context=context)
        if context == "source publication guard cleanup":
            root.rename(displaced_root)
            _repository_layout(root)
            swapped = True

    monkeypatch.setattr(guard, "unlink_strict", unlink_then_swap)
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="rollback/cleanup failed closed",
        ):
            evidence.publish_closure_e10_source_bundle(
                repo_root=root,
                work_directory=work,
                artifacts=artifacts,
                manifest=manifest,
                expected_h_commit=H_COMMIT,
                owned_guard=guard,
            )
        assert swapped is True
        assert guard.removed is True
        assert work.name in guard.removed_work_names
    finally:
        guard.close()

    for candidate_root in (root, displaced_root):
        assert not os.path.lexists(
            candidate_root / evidence.SOURCE_EVIDENCE_DIRECTORY
        )
        assert not os.path.lexists(candidate_root / evidence.GUARD_PATH)
        assert not list(
            (candidate_root / "tmp").glob(f"{evidence.WORK_PREFIX}*")
        )


def test_link_postcheck_failure_removes_only_the_new_owned_inode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_parent = tmp_path / "source"
    target_parent = tmp_path / "target"
    source_parent.mkdir()
    target_parent.mkdir()
    source = source_parent / "source.bin"
    target = target_parent / "target.bin"
    source.write_bytes(b"owned")
    real_link = evidence.os.link
    real_stat = evidence.os.stat
    linked = False
    corrupted_once = False

    def recording_link(*args: Any, **kwargs: Any) -> None:
        nonlocal linked
        real_link(*args, **kwargs)
        linked = True

    def corrupt_first_target_postcheck(
        path: Any, *args: Any, **kwargs: Any
    ) -> os.stat_result:
        nonlocal corrupted_once
        result = real_stat(path, *args, **kwargs)
        if linked and not corrupted_once and path == target.name:
            corrupted_once = True
            values = list(result)
            values[1] = result.st_ino + 1
            return os.stat_result(values)
        return result

    monkeypatch.setattr(evidence.os, "link", recording_link)
    monkeypatch.setattr(evidence.os, "stat", corrupt_first_target_postcheck)
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="hardlink publication identity drifted",
    ):
        evidence._link_exclusive(source, target)

    assert not os.path.lexists(target)
    assert source.read_bytes() == b"owned"


def test_outcome_guard_classifies_only_restricted_repository_namespaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert evidence._is_forbidden_outcome_path(
        "data/targets/monthly_targets_model_v0.parquet", tmp_path
    )
    assert evidence._is_forbidden_outcome_path(
        "reports/closure_v1/00_protocol/outcome_access_log.jsonl", tmp_path
    )
    assert evidence._is_forbidden_outcome_path("private/FULL.md", tmp_path)
    assert not evidence._is_forbidden_outcome_path(
        "tests/test_api_minimal_workflow.py", tmp_path
    )
    assert not evidence._is_forbidden_outcome_path(
        tmp_path.parent / "unrelated" / "data/targets/example.parquet", tmp_path
    )

    fixture = tmp_path.parent / "benign-fixture"
    fixture.mkdir()
    monkeypatch.chdir(fixture)
    assert not evidence._is_forbidden_outcome_path(
        "data/targets/example.parquet", tmp_path
    )
    assert not evidence._is_forbidden_outcome_path(
        "reports/closure_v1/00_protocol/outcome_access_log.jsonl", tmp_path
    )


def test_outcome_guard_rejects_repository_target_through_symlink(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}_outside"
    outside.mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data/targets").symlink_to(outside, target_is_directory=True)

    assert evidence._is_forbidden_outcome_path(
        tmp_path / "data/targets/hidden.parquet", tmp_path
    )


def test_public_suite_exclusions_are_exact_collected_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Item:
        def __init__(self, nodeid: str) -> None:
            self.nodeid = nodeid
            self.markers: list[object] = []

        def add_marker(self, marker: object) -> None:
            self.markers.append(marker)

    monkeypatch.setenv("CLOSURE_E10_SUITE_KIND", evidence.PUBLIC_SUITE_KIND)
    exact_nodes = [
        *evidence.PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES,
        *evidence.PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES,
    ]
    items = [Item(nodeid) for nodeid in exact_nodes]
    extra_parameter = Item(
        "tests/test_build_closure_holdout.py::"
        "test_protocol_lock_requires_pre_assignment_clean_state[new-case]"
    )
    items.append(extra_parameter)
    items.append(Item("tests/test_api_system.py::test_health"))
    monkeypatch.setattr(
        evidence, "PUBLIC_PHASE3_EXPECTED_TEST_COUNT", len(items)
    )
    monkeypatch.setattr(
        evidence,
        "PUBLIC_TEST_NODEIDS_SHA256",
        hashlib.sha256(
            "\0".join(sorted(item.nodeid for item in items)).encode("utf-8")
        ).hexdigest(),
    )

    evidence.pytest_collection_modifyitems(object(), items)

    assert all(item.markers for item in items[: len(exact_nodes)])
    assert extra_parameter.markers == []
    assert items[-1].markers == []
    changed_nodeid = items[-1].nodeid
    items[-1].nodeid = f"{changed_nodeid}_changed"
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="node-id digest drifted",
    ):
        evidence.pytest_collection_modifyitems(object(), items)
    items[-1].nodeid = changed_nodeid
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="exclusion registry drifted",
    ):
        evidence.pytest_collection_modifyitems(
            object(), [item for item in items if item.nodeid != exact_nodes[1]]
        )


@pytest.mark.parametrize(
    "reason",
    [
        "optional artifact is absent",
        "could not import optional module",
        "platform filesystem unavailable",
    ],
)
def test_public_skip_classifier_has_no_broad_optional_escape(
    reason: str,
) -> None:
    assert evidence._skip_classification(reason) is None


@pytest.mark.parametrize(
    "shell_payload",
    ["git commit -m forbidden", "git push origin main"],
)
def test_outcome_guard_rejects_shell_wrapped_git_mutations(
    shell_payload: str,
) -> None:
    code = (
        "import subprocess\n"
        "from pathlib import Path\n"
        "from src.experiments import build_closure_e10_source_evidence as e\n"
        "e.install_outcome_access_guard(Path.cwd())\n"
        "try:\n"
        f" subprocess.run(['bash', '-c', {shell_payload!r}], check=False)\n"
        "except e.ClosureE10SourceEvidenceError:\n"
        " print('blocked')\n"
        "else:\n"
        " raise SystemExit('opaque shell wrapper was accepted')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=evidence.PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "blocked\n"


def test_prepare_read_only_h_worktree_performs_no_git_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    synthetic_root = tmp_path / "repository"
    (synthetic_root / "tmp").mkdir(parents=True)
    guard = evidence._acquire_guard(synthetic_root)
    work, work_identity = guard.create_work_directory(
        context="synthetic exact-H preparation work allocation"
    )
    work = work.resolve()
    mask_work = Path(
        tempfile.mkdtemp(prefix=evidence.MASK_WORK_PREFIX, dir="/tmp")
    ).resolve()
    mask_meta = mask_work.lstat()
    mask_identity = (mask_meta.st_dev, mask_meta.st_ino)
    mask_tree = evidence._create_restricted_mask_tree(mask_work)
    monkeypatch.setattr(
        evidence,
        "_capture_host_outcome_log_state",
        lambda root, commit: _host_outcome_log_state(),
    )
    commands = _commands()

    def materialize_snapshot(
        *, repo_root: Path, work_directory: Path, repository_commit: str
    ) -> tuple[Path, dict[str, Any]]:
        del repo_root
        assert repository_commit == H_COMMIT
        snapshot = work_directory / "exact_h_snapshot"
        for directory in (
            snapshot / "data/closure_v1",
            snapshot / "data/targets",
            snapshot / evidence.OUTCOME_ACCESS_LOG_PATH.parent,
            snapshot / "private",
            snapshot / ".git",
            snapshot / ".venv",
            snapshot / "tmp",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        (snapshot / evidence.OUTCOME_ACCESS_LOG_PATH).write_bytes(b"")
        (snapshot / "private/FULL.md").write_bytes(b"")
        return snapshot, _exact_h_snapshot(commands)

    monkeypatch.setattr(
        evidence, "_materialize_exact_h_snapshot", materialize_snapshot
    )
    try:
        repository_state = _repository_state()
        _, _, isolation = evidence._prepare_read_only_h_worktree(
            repo_root=synthetic_root.resolve(),
            work_directory=work,
            mask_tree=mask_tree,
            repository_commit=H_COMMIT,
            repository_state=repository_state,
        )

        assert isolation["repository_mount"] == (
            "read_only_materialized_exact_h_snapshot_with_direct_and_opaque_"
            "restricted_masks"
        )
        assert isolation["worktree_pre_verification"] == repository_state
        assert isolation["restricted_path_masks"] == [
            dict(spec) for spec in evidence.RESTRICTED_MASK_SPECS
        ]
        evidence._validate_restricted_mask_tree(
            mask_tree
        )
    finally:
        guard.remove_owned_work_directory(
            name=work.name,
            identity=work_identity,
            context="synthetic exact-H preparation work cleanup",
        )
        guard.unlink_strict(context="synthetic exact-H preparation guard cleanup")
        guard.close()
        evidence._safe_remove_mask_work_directory(mask_work, mask_identity)


def test_materialize_exact_h_snapshot_restores_only_h_bound_local_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repository"
    work = repo_root / "tmp" / f"{evidence.WORK_PREFIX}snapshot"
    work.mkdir(parents=True)
    payloads: dict[Path, bytes] = {
        path: f"payload:{path.name}".encode("ascii")
        for path in evidence.DVC_RESTORE_POINTERS
    }
    model_payload = b"model-payload"
    archive_members: dict[str, bytes] = {
        evidence.BUILDER_SOURCE_PATH.as_posix(): b"builder-at-H",
    }
    pointer_paths: list[Path] = []
    for pointer_path, payload in payloads.items():
        digest = hashlib.md5(payload, usedforsecurity=False).hexdigest()
        pointer = (
            "outs:\n"
            f"- md5: {digest}\n"
            f"  size: {len(payload)}\n"
            "  hash: md5\n"
            f"  path: {pointer_path.with_suffix('').name}\n"
        ).encode("utf-8")
        archive_members[pointer_path.as_posix()] = pointer
        pointer_paths.append(pointer_path)
        cache = repo_root / evidence._dvc_cache_relative(digest)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(payload)
    model_digest = hashlib.md5(model_payload, usedforsecurity=False).hexdigest()
    directory_entries = [
        {
            "md5": model_digest,
            "relpath": "closure/model.joblib",
            "size": len(model_payload),
        }
    ]
    directory_cache = evidence._canonical_json(directory_entries)
    directory_digest = hashlib.md5(
        directory_cache, usedforsecurity=False
    ).hexdigest()
    archive_members["models.dvc"] = (
        "outs:\n"
        f"- md5: {directory_digest}.dir\n"
        f"  size: {len(model_payload)}\n"
        "  nfiles: 1\n"
        "  hash: md5\n"
        "  path: models\n"
    ).encode("utf-8")
    directory_cache_path = repo_root / evidence._dvc_cache_relative(
        directory_digest + ".dir"
    )
    directory_cache_path.parent.mkdir(parents=True, exist_ok=True)
    directory_cache_path.write_bytes(directory_cache)
    model_cache = repo_root / evidence._dvc_cache_relative(model_digest)
    model_cache.parent.mkdir(parents=True, exist_ok=True)
    model_cache.write_bytes(model_payload)
    pointer_paths.append(Path("models.dvc"))

    observed_commands: list[list[str]] = []

    def fake_run(
        argv: Any, *, repo_root: Path, environment: Any = None, **kwargs: Any
    ) -> tuple[dict[str, Any], str, str]:
        del kwargs
        command = [str(item) for item in argv]
        observed_commands.append(command)
        if command[:3] == ["git", "archive", "--format=tar"]:
            output = next(
                item.removeprefix("--output=")
                for item in command
                if item.startswith("--output=")
            )
            archive_path = repo_root / output
            with tarfile.open(archive_path, mode="w") as archive:
                for name, payload in sorted(archive_members.items()):
                    member = tarfile.TarInfo(name)
                    member.size = len(payload)
                    member.mode = 0o644
                    archive.addfile(member, io.BytesIO(payload))
            return _command(command, dict(environment or {})), "", ""
        if command[:4] == [
            "git",
            "diff-tree",
            "--no-commit-id",
            "--name-only",
        ]:
            stdout = "".join(
                f"{path.as_posix()}\0" for path in sorted(pointer_paths)
            )
            return (
                _command(
                    command,
                    dict(environment or {}),
                    stdout=stdout.encode("utf-8"),
                ),
                stdout,
                "",
            )
        if command[:4] == [
            "git",
            "diff-tree",
            "--no-commit-id",
            "--raw",
        ]:
            stdout = "".join(
                ":000000 100644 "
                "0000000000000000000000000000000000000000 "
                f"{evidence._git_blob_sha1(payload)} A\0{name}\0"
                for name, payload in sorted(archive_members.items())
            )
            return (
                _command(
                    command,
                    dict(environment or {}),
                    stdout=stdout.encode("utf-8"),
                ),
                stdout,
                "",
            )
        raise AssertionError(command)

    monkeypatch.setattr(evidence, "_run", fake_run)
    snapshot, record = evidence._materialize_exact_h_snapshot(
        repo_root=repo_root,
        work_directory=work,
        repository_commit=H_COMMIT,
    )

    assert (snapshot / evidence.BUILDER_SOURCE_PATH).read_bytes() == b"builder-at-H"
    assert (snapshot / "models/closure/model.joblib").read_bytes() == model_payload
    for pointer_path, payload in payloads.items():
        assert (
            snapshot / pointer_path.with_suffix("")
        ).read_bytes() == payload
    assert list((snapshot / "data/targets").iterdir()) == []
    assert (snapshot / evidence.OUTCOME_ACCESS_LOG_PATH).read_bytes() == b""
    assert (snapshot / "private/FULL.md").read_bytes() == b""
    assert record["source_worktree_written"] is False
    assert record["network_used"] is False
    assert record["dvc_restore"]["pointer_count"] == len(pointer_paths)
    assert record["pre_execution_inventory"] == record["post_execution_inventory"]
    assert all(
        "commit" not in command[1:2] and "push" not in command[1:2]
        for command in observed_commands
    )


def test_diff_tree_exact_h_inventory_excludes_restricted_tree_without_commit(
    tmp_path: Path,
) -> None:
    if os.environ.get("CLOSURE_E10_SUITE_KIND") == evidence.PUBLIC_SUITE_KIND:
        # Production already ran and recorded these commands before entering
        # the guarded public sandbox.  The focal pre-H run below exercises Git
        # itself without teaching the suite guard to accept path-looking
        # exclusion tokens from arbitrary child commands.
        commands = _commands()
        validated = evidence._validate_exact_commands(
            commands,
            repository_commit=H_COMMIT,
        )
        assert validated["exact_h_tree_inventory"]["argv"][1:5] == [
            "diff-tree",
            "--no-commit-id",
            "--raw",
            "-r",
        ]
        return
    repo_root = tmp_path / "repository"
    snapshot = tmp_path / "snapshot"
    repo_root.mkdir()
    snapshot.mkdir()

    def git(*argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *argv],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=True,
        )

    git("init", "-q")
    allowed = {
        "README.md": b"allowed\n",
        "data/closure_v1/allowed.txt": b"allowed data\n",
    }
    restricted = {
        "data/targets/secret.bin": b"synthetic target fixture\n",
        "data/closure_v1/unblinded/secret.bin": b"synthetic outcome fixture\n",
        "data/closure_v1/evaluation_outcomes/secret.bin": (
            b"synthetic outcome fixture\n"
        ),
        evidence.OUTCOME_ACCESS_LOG_PATH.as_posix(): b"synthetic log fixture\n",
        "private/FULL.md": b"synthetic private fixture\n",
    }
    for path, payload in {**allowed, **restricted}.items():
        destination = repo_root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    git("add", "--", ".")
    tree = git("write-tree").stdout.strip()
    assert len(tree) == 40
    for path, payload in allowed.items():
        destination = snapshot / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    verified = evidence._verify_snapshot_tracked_h(
        repo_root=repo_root,
        snapshot_root=snapshot,
        repository_commit=tree,
    )
    exclusions = [
        f":(exclude,top){path}"
        for path in evidence.FORBIDDEN_VERIFICATION_PREFIXES
    ]
    _, dvc_names, dvc_stderr = evidence._run(
        (
            "git",
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "-z",
            evidence.EMPTY_GIT_TREE_SHA1,
            tree,
            "--",
            "data/closure_v1",
            "models.dvc",
            *exclusions,
        ),
        repo_root=repo_root,
        environment={"GIT_OPTIONAL_LOCKS": "0"},
    )

    assert verified["entry_count"] == len(allowed)
    assert dvc_stderr == ""
    assert dvc_names == "data/closure_v1/allowed.txt\0"
    assert all(path not in dvc_names for path in restricted)


def test_real_bwrap_overlay_denies_existing_and_absent_restricted_paths(
    tmp_path: Path,
) -> None:
    if os.environ.get("CLOSURE_E10_SUITE_KIND") == evidence.PUBLIC_SUITE_KIND:
        # The production denial probe is a separate recorded bwrap command.
        # The outer public sandbox disables nested user namespaces, so this
        # regression executes its nested synthetic sandbox only in the focal
        # pre-H verification run.
        template = evidence._bubblewrap_template(
            [copy.deepcopy(spec) for spec in evidence.RESTRICTED_MASK_SPECS]
        )
        restricted = evidence._restricted_mount_template()
        start = next(
            index
            for index in range(len(template))
            if template[index : index + len(restricted)] == restricted
        )
        assert template[start : start + len(restricted)] == restricted
        return
    synthetic_root = tmp_path / "synthetic_h"
    synthetic_root.mkdir()
    (synthetic_root / "tmp").mkdir()
    (synthetic_root / "README.allowed").write_text("allowed\n", encoding="utf-8")
    (synthetic_root / "data/targets").mkdir(parents=True)
    (synthetic_root / "data/targets/secret.bin").write_bytes(b"secret")
    for name in ("unblinded", "evaluation_outcomes"):
        restricted_directory = synthetic_root / "data/closure_v1" / name
        restricted_directory.mkdir(parents=True)
        (restricted_directory / "secret.bin").write_bytes(b"secret")
    (synthetic_root / "reports/closure_v1/00_protocol").mkdir(parents=True)
    (synthetic_root / evidence.OUTCOME_ACCESS_LOG_PATH).write_bytes(b"secret")
    (synthetic_root / "private").mkdir()
    (synthetic_root / "private/FULL.md").write_text(
        "restricted\n", encoding="utf-8"
    )
    sandbox_tmp = tmp_path / "sandbox_tmp"
    sandbox_tmp.mkdir()
    mask_work = Path(
        tempfile.mkdtemp(prefix=evidence.MASK_WORK_PREFIX, dir="/tmp")
    ).resolve()
    mask_meta = mask_work.lstat()
    mask_identity = (mask_meta.st_dev, mask_meta.st_ino)
    mask_tree = evidence._create_restricted_mask_tree(mask_work)
    verification_code = (
        evidence.ISOLATION_PROBE_CODE
        + "\nassert Path('README.allowed').read_text() == 'allowed\\n'"
        + "\nassert sorted(p.name for p in Path('data/targets').iterdir()) == "
        + repr(
            sorted(
                evidence.RESTRICTED_MASK_SPECS[0]["metadata_placeholders"]
            )
        )
        + "\nassert all((Path('data/targets')/name).is_file() for name in "
        + repr(evidence.RESTRICTED_MASK_SPECS[0]["metadata_placeholders"])
        + ")"
        + "\nassert not os.path.lexists('data/targets/secret.bin')"
        + "\nassert list(Path('data/closure_v1/unblinded').iterdir()) == []"
        + "\nassert list(Path('data/closure_v1/evaluation_outcomes').iterdir()) == []"
        + "\nassert not os.path.lexists('data/closure_v1/unblinded/secret.bin')"
        + "\nassert not os.path.lexists('data/closure_v1/evaluation_outcomes/secret.bin')"
        + "\ntry:\n Path('root_write').write_text('forbidden')"
        + "\nexcept OSError as exc:\n assert exc.errno == 30"
        + "\nelse:\n raise SystemExit('read-only overlay accepted a write')"
        + "\nPath('tmp/writable').write_text('ok')"
    )
    command = [
        evidence.BWRAP_BACKEND,
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
        command.extend(["--ro-bind", system_path, system_path])
    command.extend(
        [
            "--ro-bind",
            os.fspath(synthetic_root),
            "/workspace",
                *(
                    item.replace("<MASK_DIRECTORY>", os.fspath(mask_tree)).replace(
                        "<SNAPSHOT_DIRECTORY>", os.fspath(synthetic_root)
                    )
                    for item in evidence._restricted_mount_template()
                ),
            "--bind",
            os.fspath(sandbox_tmp),
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
            "/usr/bin/python3",
            "-B",
            "-c",
            verification_code,
        ]
    )
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            cwd=synthetic_root,
        )
        assert completed.returncode == 0, completed.stderr
        observed = json.loads(completed.stdout.splitlines()[0])
        assert observed == evidence._expected_denial_probe_results()
        assert (sandbox_tmp / "writable").read_text(encoding="utf-8") == "ok"
    finally:
        evidence._safe_remove_mask_work_directory(mask_work, mask_identity)


def test_required_dvc_evidence_is_projected_from_exact_h_snapshot() -> None:
    commands = _commands()
    snapshot = _exact_h_snapshot(commands)

    result = evidence._required_dvc_restore_evidence(
        snapshot["dvc_restore"]
    )

    assert result["status"] == "passed"
    assert result["network_used"] is False
    assert result["remote_pull_claimed"] is False
    assert result["pointer_count"] == 4
    assert all(
        record["destination_initially_absent_in_exact_h_snapshot"] is True
        and record["restored_into_materialized_exact_h_snapshot"] is True
        for record in result["records"]
    )


def test_required_dvc_evidence_is_exactly_bound_to_snapshot_restore() -> None:
    artifacts, manifest = _fixture_bundle()
    changed = copy.deepcopy(manifest)
    changed_artifacts = dict(artifacts)
    replacement = "e" * 64
    changed["verification"]["dvc_restore"]["records"][0][
        "payload_sha256"
    ] = replacement
    environment = json.loads(changed_artifacts["environment"])
    environment["dvc_restore_verification"]["records"][0][
        "payload_sha256"
    ] = replacement
    changed_artifacts["environment"] = evidence._pretty_json(environment)
    records = [
        evidence._source_record(key, changed_artifacts[key], H_COMMIT)
        for key in evidence.SOURCE_EVIDENCE_KEYS
    ]
    changed["outputs"] = copy.deepcopy(records)
    changed["source_artifacts"] = records
    changed["source_artifacts_sha256"] = evidence._records_digest(records)

    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="DVC restore does not match exact-H snapshot",
    ):
        evidence.validate_closure_e10_source_payloads(
            artifacts=changed_artifacts,
            manifest=changed,
            expected_h_commit=H_COMMIT,
        )


def test_real_openapi_covers_every_operation_declared_by_public_documents() -> None:
    from src.api.main import create_app

    result = evidence._validate_openapi_contract(
        create_app().openapi(),
        repo_root=Path.cwd(),
    )

    assert result["valid"] is True
    assert result["missing_documented_operations"] == []
    assert result["operation_ids_unique"] is True
    assert result["path_parameters_exact"] is True


def test_public_suite_and_e2e_commands_are_closed_and_outcome_guarded() -> None:
    commands = _commands()

    validated = evidence._validate_exact_commands(
        commands,
        repository_commit=H_COMMIT,
    )

    public_argv = validated["public_tests"]["argv"]
    assert public_argv[:3] == ["poetry", "run", "pytest"]
    assert public_argv[3 : 3 + len(evidence.PUBLIC_TEST_SELECTORS)] == list(
        evidence.PUBLIC_TEST_SELECTORS
    )
    assert "tests" not in public_argv
    assert tuple(validated["end_to_end"]["argv"][3:6]) == evidence.E2E_TEST_NODES
    assert evidence.E2E_FIXTURE_CONTRACT["future_target_used"] is False
    assert evidence.E2E_FIXTURE_CONTRACT["outcome_access_log_opened"] is False
    assert evidence.PUBLIC_SUITE_KIND == "closure_phase3_public"
    assert evidence.PUBLIC_PHASE3_EXPECTED_TEST_COUNT == 347
    assert evidence.PUBLIC_PHASE3_EXPECTED_PASS_COUNT == 338
    assert evidence.PUBLIC_PHASE3_EXPECTED_SKIP_COUNT == 9
    assert evidence.PUBLIC_TEST_NODEIDS_SHA256 == (
        "3a37a3fb3b022b2b36f6a64b6571aecd83858a270c8fcf4985036c2633504a42"
    )
    assert len(evidence.PUBLIC_PHASE3_TEST_PATHS) == 11
    assert len(set(evidence.PUBLIC_PHASE3_TEST_PATHS)) == 11
    assert len(evidence.PUBLIC_API_TEST_PATHS) == 13
    assert len(set(evidence.PUBLIC_API_TEST_PATHS)) == 13
    assert len(evidence.PUBLIC_TEST_PATHS) == 24
    assert len(set(evidence.PUBLIC_TEST_PATHS)) == 24
    assert all(
        path.startswith("tests/test_") and path.endswith(".py")
        for path in evidence.PUBLIC_TEST_PATHS
    )
    assert len(evidence.PUBLIC_PHASE3_PRECOMMIT_TEST_NODES) == 15
    assert len(set(evidence.PUBLIC_PHASE3_PRECOMMIT_TEST_NODES)) == 15
    assert len(evidence.PUBLIC_PHASE3_EXTRA_TEST_NODES) == 24
    assert len(set(evidence.PUBLIC_PHASE3_EXTRA_TEST_NODES)) == 24
    selected_files = set(evidence.PUBLIC_TEST_PATHS)
    all_skip_nodes = {
        *evidence.PUBLIC_PRE_E0U_EXCLUDED_TEST_NODES,
        *evidence.PUBLIC_USER_PROHIBITED_GIT_COMMIT_TEST_NODES,
    }
    assert not {
        nodeid.split("::", 1)[0] for nodeid in all_skip_nodes
    }.intersection(selected_files)
    assert set(evidence.PUBLIC_PHASE3_EXTRA_TEST_NODES) == {
        *evidence.PUBLIC_PHASE3_PRECOMMIT_TEST_NODES,
        *all_skip_nodes,
    }
    assert tuple(evidence.PUBLIC_TEST_COMMAND_PREFIX[3:])[:48] == (
        evidence.PUBLIC_TEST_SELECTORS
    )
    assert evidence._public_suite_contract_record()[
        "public_suite_selector_sha256"
    ] == evidence.PUBLIC_TEST_SELECTOR_SHA256


def test_manifest_or_command_drift_is_rejected() -> None:
    artifacts, manifest = _fixture_bundle()
    changed = copy.deepcopy(manifest)
    changed["verification"]["commands"]["public_tests"]["returncode"] = 1

    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="did not pass"):
        evidence.validate_closure_e10_source_payloads(
            artifacts=artifacts,
            manifest=changed,
            expected_h_commit=H_COMMIT,
        )

    for mutate in ("missing", "duplicate"):
        commands = copy.deepcopy(_commands())
        argv = commands["public_tests"]["argv"]
        if mutate == "missing":
            del argv[3]
        else:
            argv.insert(3, argv[3])
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="public suite command drifted",
        ):
            evidence._validate_exact_commands(
                commands,
                repository_commit=H_COMMIT,
            )

    totals, skipped = evidence._parse_junit(artifacts["public_tests_xml"])
    inconsistent_junit = artifacts["public_tests_xml"].replace(
        b'tests="347"', b'tests="346"', 1
    )
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="concrete testcase ledger",
    ):
        evidence._parse_junit(inconsistent_junit)
    for changed_count in (346, 348):
        changed_totals = dict(totals)
        changed_totals["tests"] = changed_count
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="inventory did not pass exactly",
        ):
            evidence._require_public_test_success(changed_totals, skipped)

    changed = copy.deepcopy(manifest)
    changed["outcome_safety"]["public_suite_selectors"] = changed[
        "outcome_safety"
    ]["public_suite_selectors"][:-1]
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="public suite contract drifted",
    ):
        evidence.validate_closure_e10_source_payloads(
            artifacts=artifacts,
            manifest=changed,
            expected_h_commit=H_COMMIT,
        )

    changed = copy.deepcopy(manifest)
    changed["outcome_safety"]["public_suite_nodeids_sha256"] = "0" * 64
    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="public suite contract drifted",
    ):
        evidence.validate_closure_e10_source_payloads(
            artifacts=artifacts,
            manifest=changed,
            expected_h_commit=H_COMMIT,
        )


def test_loader_status_excludes_only_the_separately_bound_outcome_log() -> None:
    log = evidence.OUTCOME_ACCESS_LOG_PATH.as_posix()
    activation = evidence.RECOVERY_ACTIVATION_PATH.as_posix()
    activation_2 = evidence.RECOVERY_2_ACTIVATION_PATH.as_posix()
    evidence._validate_loader_worktree_status("", ())
    evidence._validate_loader_worktree_status("", (log,))
    evidence._validate_loader_worktree_status(
        "", (), recovery_attempt=evidence.RECOVERY_ATTEMPT_1
    )
    evidence._validate_loader_worktree_status(
        "", (), recovery_attempt=evidence.RECOVERY_ATTEMPT_2
    )
    evidence._validate_loader_worktree_status(
        f"?? {activation_2}",
        (activation_2,),
        recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
    )
    evidence._validate_loader_worktree_status(
        f"A  {activation_2}",
        (log, activation_2),
        recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
    )
    evidence._validate_loader_worktree_status(
        f"?? {activation}",
        (activation,),
        recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
    )
    evidence._validate_loader_worktree_status(
        f"A  {activation}",
        (log, activation),
        recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
    )

    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="scope drifted"):
        evidence._validate_loader_worktree_status(f" M {log}", (log,))
    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="invalid"):
        evidence._validate_loader_worktree_status(" M README.md", ("README.md",))
    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="invalid"):
        evidence._validate_loader_worktree_status(
            f"?? {activation}", (activation,)
        )
    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="invalid"):
        evidence._validate_loader_worktree_status(
            f"?? {activation}",
            (activation,),
            recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
        )
    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="invalid"):
        evidence._validate_loader_worktree_status(
            f"?? {activation_2}",
            (activation_2,),
            recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
        )
    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="invalid"):
        evidence._validate_loader_worktree_status(
            f"?? {activation}",
            (activation, activation),
            recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
        )
    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="scope drifted"):
        evidence._validate_loader_worktree_status(
            "",
            (activation,),
            recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
        )
    for status_code in (" M", "AM"):
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError, match="scope drifted"
        ):
            evidence._validate_loader_worktree_status(
                f"{status_code} {activation}",
                (activation,),
                recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
            )
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError, match="scope drifted"
        ):
            evidence._validate_loader_worktree_status(
                f"{status_code} {activation_2}",
                (activation_2,),
                recovery_attempt=evidence.RECOVERY_ATTEMPT_2,
            )
    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="scope drifted"):
        evidence._validate_loader_worktree_status(
            f"?? {activation}\n?? README.md",
            (activation,),
            recovery_attempt=evidence.RECOVERY_ATTEMPT_1,
        )
    with pytest.raises(evidence.ClosureE10SourceEvidenceError, match="scope drifted"):
        evidence._validate_loader_worktree_status(
            f" M {log}\n?? reports/closure_v1/01_benchmark/result.csv",
            (log,),
        )


def test_generation_requires_postgresql_and_cleans_guard_before_any_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    monkeypatch.setattr(
        evidence,
        "_collect_exact_h_repository_state",
        lambda root, commit: _repository_state(),
    )
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    launched: list[object] = []
    monkeypatch.setattr(
        evidence,
        "_run",
        lambda *args, **kwargs: launched.append((args, kwargs)),
    )

    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="PostgreSQL TEST_DATABASE_URL",
    ):
        evidence.generate_closure_e10_source_evidence(
            repo_root=tmp_path,
            expected_h_commit=H_COMMIT,
        )

    assert launched == []
    assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
    assert not os.path.lexists(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
    assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))


def test_generator_mask_cleanup_fault_prevents_publish_and_cleans_repo_leases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    monkeypatch.setattr(
        evidence,
        "_collect_exact_h_repository_state",
        lambda root, commit: _repository_state(),
    )
    database_checks = 0

    def pass_check_then_stop_after_allocation() -> str:
        nonlocal database_checks
        database_checks += 1
        if database_checks == 1:
            return (
                "postgresql+asyncpg://test-user:test-password@127.0.0.1/"
                "closure_e10"
            )
        raise evidence.ClosureE10SourceEvidenceError(
            "synthetic stop after generation lease allocation"
        )

    original_mask_cleanup = evidence._safe_remove_mask_work_directory
    removed_masks: list[Path] = []

    def fail_after_exact_mask_cleanup(
        path: Path, identity: tuple[int, int]
    ) -> None:
        original_mask_cleanup(path, identity)
        removed_masks.append(path)
        raise evidence.ClosureE10SourceEvidenceError(
            "synthetic generator mask cleanup postcheck failure"
        )

    launched: list[object] = []
    monkeypatch.setattr(
        evidence, "_require_postgresql_test_database", pass_check_then_stop_after_allocation
    )
    monkeypatch.setattr(
        evidence, "_safe_remove_mask_work_directory", fail_after_exact_mask_cleanup
    )
    monkeypatch.setattr(
        evidence,
        "_run",
        lambda *args, **kwargs: launched.append((args, kwargs)),
    )

    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="generation cleanup failed closed",
    ):
        evidence.generate_closure_e10_source_evidence(
            repo_root=tmp_path,
            expected_h_commit=H_COMMIT,
        )

    assert database_checks == 2
    assert launched == []
    assert len(removed_masks) == 1
    assert not os.path.lexists(removed_masks[0])
    assert not os.path.lexists(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
    assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
    assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))


def test_generator_mask_boundary_replacement_preserves_foreign_and_owned_trees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    monkeypatch.setattr(
        evidence,
        "_collect_exact_h_repository_state",
        lambda root, commit: _repository_state(),
    )
    database_checks = 0

    def pass_check_then_stop_after_allocation() -> str:
        nonlocal database_checks
        database_checks += 1
        if database_checks == 1:
            return (
                "postgresql+asyncpg://test-user:test-password@127.0.0.1/"
                "closure_e10"
            )
        raise evidence.ClosureE10SourceEvidenceError(
            "synthetic stop after generation lease allocation"
        )

    owned_moved = Path(
        tempfile.mkdtemp(
            prefix=f"{evidence.MASK_WORK_PREFIX}generator_owned_",
            dir="/tmp",
        )
    ).resolve()
    owned_moved.rmdir()
    original_rename = evidence._rename_noreplace_at
    canonical_mask: Path | None = None
    owned_identity: tuple[int, int] | None = None

    def replace_generator_mask_before_capture(
        source_directory_fd: int,
        source_name: str,
        target_directory_fd: int,
        target_name: str,
    ) -> None:
        nonlocal canonical_mask, owned_identity
        if (
            canonical_mask is None
            and source_name.startswith(evidence.MASK_WORK_PREFIX)
            and not source_name.startswith(".closure_e10_")
        ):
            canonical_mask = Path("/tmp") / source_name
            metadata = os.stat(
                source_name,
                dir_fd=source_directory_fd,
                follow_symlinks=False,
            )
            owned_identity = (metadata.st_dev, metadata.st_ino)
            os.rename(
                source_name,
                owned_moved.name,
                src_dir_fd=source_directory_fd,
                dst_dir_fd=source_directory_fd,
            )
            canonical_mask.mkdir(mode=0o700)
            (canonical_mask / "foreign.marker").write_bytes(
                b"foreign generator mask replacement\n"
            )
        original_rename(
            source_directory_fd,
            source_name,
            target_directory_fd,
            target_name,
        )

    launched: list[object] = []
    monkeypatch.setattr(
        evidence, "_require_postgresql_test_database", pass_check_then_stop_after_allocation
    )
    monkeypatch.setattr(
        evidence, "_rename_noreplace_at", replace_generator_mask_before_capture
    )
    monkeypatch.setattr(
        evidence,
        "_run",
        lambda *args, **kwargs: launched.append((args, kwargs)),
    )
    try:
        with pytest.raises(
            evidence.ClosureE10SourceEvidenceError,
            match="generation cleanup failed closed",
        ):
            evidence.generate_closure_e10_source_evidence(
                repo_root=tmp_path,
                expected_h_commit=H_COMMIT,
            )

        assert database_checks == 2
        assert launched == []
        assert canonical_mask is not None
        assert owned_identity is not None
        assert (canonical_mask / "foreign.marker").read_bytes() == (
            b"foreign generator mask replacement\n"
        )
        evidence._validate_restricted_mask_tree(
            owned_moved / "restricted_mask_tree"
        )
        assert not os.path.lexists(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
        assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
        assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))
    finally:
        monkeypatch.setattr(evidence, "_rename_noreplace_at", original_rename)
        if os.path.lexists(owned_moved) and owned_identity is not None:
            evidence._safe_remove_mask_work_directory(
                owned_moved,
                owned_identity,
            )
        if canonical_mask is not None and os.path.lexists(canonical_mask):
            shutil.rmtree(canonical_mask)


def test_generator_work_cleanup_fault_rolls_back_before_releasing_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repository_layout(tmp_path)
    monkeypatch.setattr(
        evidence,
        "_collect_exact_h_repository_state",
        lambda root, commit: _repository_state(),
    )
    database_checks = 0

    def pass_check_then_stop_after_allocation() -> str:
        nonlocal database_checks
        database_checks += 1
        if database_checks == 1:
            return (
                "postgresql+asyncpg://test-user:test-password@127.0.0.1/"
                "closure_e10"
            )
        raise evidence.ClosureE10SourceEvidenceError(
            "synthetic stop after generation lease allocation"
        )

    original_remove_work = evidence.OwnedGuard.remove_owned_work_directory
    removed_work_names: list[str] = []

    def fail_after_exact_generation_work_cleanup(
        self: evidence.OwnedGuard,
        *,
        name: str,
        identity: tuple[int, int],
        context: str,
    ) -> None:
        original_remove_work(
            self,
            name=name,
            identity=identity,
            context=context,
        )
        if context == "E10 source generation work cleanup":
            removed_work_names.append(name)
            raise evidence.ClosureE10SourceEvidenceError(
                "synthetic generator work cleanup postcheck failure"
            )

    launched: list[object] = []
    monkeypatch.setattr(
        evidence, "_require_postgresql_test_database", pass_check_then_stop_after_allocation
    )
    monkeypatch.setattr(
        evidence.OwnedGuard,
        "remove_owned_work_directory",
        fail_after_exact_generation_work_cleanup,
    )
    monkeypatch.setattr(
        evidence,
        "_run",
        lambda *args, **kwargs: launched.append((args, kwargs)),
    )

    with pytest.raises(
        evidence.ClosureE10SourceEvidenceError,
        match="generation cleanup failed closed",
    ):
        evidence.generate_closure_e10_source_evidence(
            repo_root=tmp_path,
            expected_h_commit=H_COMMIT,
        )

    assert database_checks == 2
    assert launched == []
    assert len(removed_work_names) == 1
    assert not os.path.lexists(tmp_path / "tmp" / removed_work_names[0])
    assert not os.path.lexists(tmp_path / evidence.SOURCE_EVIDENCE_DIRECTORY)
    assert not os.path.lexists(tmp_path / evidence.GUARD_PATH)
    assert not list((tmp_path / "tmp").glob(f"{evidence.WORK_PREFIX}*"))
