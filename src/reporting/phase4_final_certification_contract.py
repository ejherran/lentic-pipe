#!/usr/bin/env python
"""Strict public contract for the final Closure V1 Phase 4 certification.

This module is deliberately outcome-free.  It validates the static H/P/R-CERT
topology, the exact public evidence anchors, the eight identity-only DVC
pointers, the closed public-test inventory and the exact eight-file result
namespace.  It never resolves a DVC pointer and never opens a Parquet payload,
raw target, outcome namespace, private manuscript, or outcome-access log.

The public test suite is sealed to the exact selector count, collected-node
count and ordered-node digest reproduced by two independent outcome-free
collections.  The explicit ``pending_integration`` state remains available
only to integration fixtures; production authority and execution callers
reject it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = Path(
    "configs/closure_v1/phase4_final_certification.yaml"
)
DEFAULT_SCHEMA_PATH = Path(
    "configs/closure_v1/phase4_final_certification.schema.json"
)
H1_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority.json"
)
H1_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest.json"
)
AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v2.json"
)
AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v2.json"
)
CERTIFICATION_ROOT = Path("reports/closure_v1/12_certification")
GUARD_PATH = Path(
    "tmp/closure_v1_phase4_final_certification/certification.guard"
)
LOCAL_DVC_CONFIG_PATH = Path(".dvc/config.local")

CONTRACT_VERSION = "closure_v1_phase4_final_certification_v2"
CLOSURE_SOURCE_COMMIT = "ea8ddce7f8edb9a61db97e29178e52603fa371b1"
R_SYN_COMMIT = "528dcb74a7c08b65f262901e4562a67b784db8c9"
EDITORIAL_COMMIT = "d1daa3059462854d6ddf5199fbc05515cec76982"
H1_CERT_COMMIT = "003ca2282af5d7156b5814b59d8f1ddfb7fc681e"
P1_CERT_COMMIT = "67983d8ea823a59eb4af55b59da04fb4ae298dcb"
FINAL_TAG = "thesis-closure-v1"
AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v2"
AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v2"
)
H1_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v1"
H1_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v1"
)
HASH_CHUNK_SIZE = 1024 * 1024
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MD5_RE = re.compile(r"^[0-9a-f]{32}$")

OUTPUT_PATHS = (
    "reports/closure_v1/12_certification/public_tests.xml",
    "reports/closure_v1/12_certification/test_report.md",
    "reports/closure_v1/12_certification/openapi.json",
    "reports/closure_v1/12_certification/openapi_contract_report.md",
    "reports/closure_v1/12_certification/end_to_end_report.md",
    "reports/closure_v1/12_certification/environment.json",
    "reports/closure_v1/12_certification/FINAL_DOCTORAL_CERTIFICATION_REPORT.md",
    "reports/closure_v1/12_certification/final_certification_manifest.json",
)
EXPECTED_RUNTIME_VERSIONS: Mapping[str, str] = {
    "python": "Python 3.14.7",
    "dvc": "3.67.1",
    "ty": "ty 0.0.37",
    "git": "git version 2.55.0",
    "poetry": "Poetry (version 2.4.1)",
    "bubblewrap": "bubblewrap 0.11.2",
    "docker_client": "29.7.2",
    "docker_server": "29.7.2",
}
LOCKED_SUITE_STATUS = "locked"
LOCKED_SUITE_SELECTOR_COUNT = 39
LOCKED_SUITE_COLLECTED_TEST_COUNT = 905
LOCKED_SUITE_NODEIDS_SHA256 = (
    "679cfd4e62e6eb9f7eb14e9ba1739f7b427fe56a65dab92ac3b39c0ddff42c03"
)
LOCKED_SUITE_ALLOWED_SKIP_COUNT = 7


class FinalCertificationContractError(RuntimeError):
    """Raised when the final Phase 4 certification contract drifts."""


@dataclass(frozen=True)
class PublicationPathSpec:
    path: str
    status: str
    git_mode: str


@dataclass(frozen=True)
class AnchorInputSpec:
    path: str
    role: str


@dataclass(frozen=True)
class DvcPointerSpec:
    path: str
    role: str
    output_path: str
    md5: str
    size: int


@dataclass(frozen=True)
class TestSuiteSpec:
    suite_kind: str
    positive_test_paths: tuple[str, ...]
    exact_skipped_nodes: tuple[str, ...]
    exact_skip_reason: str
    e2e_nodes: tuple[str, ...]
    command_template: tuple[str, ...]
    static_commands: tuple[tuple[str, ...], ...]
    status: str
    selector_count: int | None
    collected_test_count: int | None
    nodeids_sha256: str | None
    allowed_skip_count: int

    @property
    def supplemental_skipped_nodes(self) -> tuple[str, ...]:
        """Skipped nodes whose files are not already positive selectors."""

        selected_files = set(self.positive_test_paths)
        return tuple(
            node
            for node in self.exact_skipped_nodes
            if node.split("::", 1)[0] not in selected_files
        )

    @property
    def selectors(self) -> tuple[str, ...]:
        """Exact non-duplicating pytest selectors in command order."""

        return (*self.positive_test_paths, *self.supplemental_skipped_nodes)


@dataclass(frozen=True)
class FinalCertificationContract:
    path: Path
    raw: Mapping[str, Any]
    closure_source_commit: str
    r_syn_commit: str
    editorial_commit: str
    h1_cert_commit: str
    p1_cert_commit: str
    final_tag: str
    h1_scope: tuple[PublicationPathSpec, ...]
    p1_scope: tuple[PublicationPathSpec, ...]
    h_scope: tuple[PublicationPathSpec, ...]
    p_scope: tuple[PublicationPathSpec, ...]
    r_scope: tuple[PublicationPathSpec, ...]
    anchor_inputs: tuple[AnchorInputSpec, ...]
    dvc_pointers: tuple[DvcPointerSpec, ...]
    dvc_pull_command_template: tuple[str, ...]
    test_suite: TestSuiteSpec
    expected_openapi_path_count: int
    expected_openapi_operation_count: int
    expected_documented_operation_count: int
    forbidden_read_prefixes: tuple[str, ...]
    forbidden_read_paths: tuple[str, ...]
    output_paths: tuple[str, ...]
    expected_runtime_versions: Mapping[str, str]
    concurrency_lock: str
    legacy_guard_path_must_be_absent: str
    external_namespace_mutation_is_stop_condition: bool
    noncooperating_same_uid_namespace_mutation: str
    identity_revalidated_before_and_after_name_cleanup: bool
    conditional_unlink_by_inode_claimed: bool
    no_clobber: bool
    cleanup_before_precommit: bool
    stop_rules: tuple[str, ...]

    @property
    def guard_path(self) -> str:
        """Compatibility alias for the forbidden legacy guard path."""

        return self.legacy_guard_path_must_be_absent

    @property
    def anchor_input_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.anchor_inputs)

    @property
    def dvc_pointer_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.dvc_pointers)

    @property
    def dvc_output_paths(self) -> tuple[str, ...]:
        return tuple(item.output_path for item in self.dvc_pointers)

    @property
    def suite_selectors(self) -> tuple[str, ...]:
        return self.test_suite.selectors


H1_SCOPE = (
    PublicationPathSpec(
        "configs/closure_v1/phase4_final_certification.schema.json",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "configs/closure_v1/phase4_final_certification.yaml", "A", "100644"
    ),
    PublicationPathSpec(
        "docs/closure_v1/PHASE4_FINAL_CERTIFICATION.md", "A", "100644"
    ),
    PublicationPathSpec(
        "src/data/prepare_commit_artifacts.py", "M", "100755"
    ),
    PublicationPathSpec(
        "src/experiments/lock_phase4_final_certification.py", "A", "100644"
    ),
    PublicationPathSpec(
        "src/reporting/build_phase4_final_certification.py", "A", "100644"
    ),
    PublicationPathSpec(
        "src/reporting/phase4_final_certification_contract.py",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "tests/test_build_phase4_final_certification.py", "A", "100644"
    ),
    PublicationPathSpec(
        "tests/test_lock_phase4_final_certification.py", "A", "100644"
    ),
    PublicationPathSpec(
        "tests/test_phase4_final_certification_contract.py", "A", "100644"
    ),
    PublicationPathSpec(
        "tests/test_prepare_commit_artifacts.py", "M", "100644"
    ),
)
P1_SCOPE = (
    PublicationPathSpec(H1_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H1_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P_SCOPE = (
    PublicationPathSpec(AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
R_SCOPE = tuple(
    PublicationPathSpec(path, "A", "100644") for path in OUTPUT_PATHS
)

ANCHOR_INPUTS = (
    AnchorInputSpec(".dvc/config", "tracked_dvc_cache_configuration"),
    AnchorInputSpec("docs/API_DATASET_CONTRACT.md", "documented_api_contract"),
    AnchorInputSpec("docs/API_PROTOCOL.md", "documented_api_contract"),
    AnchorInputSpec("poetry.lock", "dependency_lock"),
    AnchorInputSpec("pyproject.toml", "project_and_tool_configuration"),
    AnchorInputSpec(
        "reports/closure_v1/11_synthesis/THESIS_CLAIM_EVIDENCE_MATRIX.csv",
        "approved_claim_boundary",
    ),
    AnchorInputSpec(
        "reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json",
        "published_r_syn_manifest",
    ),
    AnchorInputSpec(
        "reports/thesis/chapter_iv_evidence_matrix_manifest.json",
        "published_editorial_matrix_manifest",
    ),
    AnchorInputSpec(
        "reports/thesis/phase4_manuscript_build_receipt.json",
        "published_private_manuscript_attestation",
    ),
    AnchorInputSpec(
        "reports/thesis/phase4_manuscript_build_receipt_manifest.json",
        "published_private_manuscript_attestation_manifest",
    ),
)

DVC_POINTERS = (
    DvcPointerSpec(
        "data/closure_v1/locked_evaluation/input_history.parquet.dvc",
        "locked_evaluation_scientific_input",
        "data/closure_v1/locked_evaluation/input_history.parquet",
        "d02d1b0b94f740ce990d06a7a949b09c",
        480855,
    ),
    DvcPointerSpec(
        "data/closure_v1/locked_evaluation/intent_origins.parquet.dvc",
        "locked_evaluation_scientific_input",
        "data/closure_v1/locked_evaluation/intent_origins.parquet",
        "b9bad06b799f342f9bf54eb0a2cbec7a",
        171047,
    ),
    DvcPointerSpec(
        "data/closure_v1/locked_evaluation/origin_features.parquet.dvc",
        "locked_evaluation_scientific_input",
        "data/closure_v1/locked_evaluation/origin_features.parquet",
        "da118c0515bdbd9705539bce1305bf11",
        238955,
    ),
    DvcPointerSpec(
        "data/closure_v1/locked_evaluation/sequence_features.parquet.dvc",
        "locked_evaluation_scientific_input",
        "data/closure_v1/locked_evaluation/sequence_features.parquet",
        "f858efff8a4c2e25f4c5b287258f0176",
        436677,
    ),
    DvcPointerSpec(
        "data/closure_v1/degradation_masks.parquet.dvc",
        "final_scientific_output",
        "data/closure_v1/degradation_masks.parquet",
        "c483aab92229b79d5f77d4024c768be6",
        6037,
    ),
    DvcPointerSpec(
        "data/closure_v1/predictions_long.parquet.dvc",
        "final_scientific_output",
        "data/closure_v1/predictions_long.parquet",
        "8674d3247c5aa1a866199881c1389332",
        1794498,
    ),
    DvcPointerSpec(
        "reports/closure_v1/05_inference/bootstrap_distributions.parquet.dvc",
        "final_scientific_output",
        "reports/closure_v1/05_inference/bootstrap_distributions.parquet",
        "59ea9456ed60a49013fee3e0d0088711",
        2380,
    ),
    DvcPointerSpec(
        "reports/closure_v1/09_planning/planning_origin_deltas.parquet.dvc",
        "final_scientific_output",
        "reports/closure_v1/09_planning/planning_origin_deltas.parquet",
        "f67f23c22af0056b67852cc645703d19",
        7788,
    ),
)

DVC_PULL_COMMAND_TEMPLATE = (
    ".venv/bin/dvc",
    "pull",
    "--no-run-cache",
    "-j",
    "1",
    "{pointer_path}",
)

POSITIVE_TEST_PATHS = (
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
    "tests/test_audit_closure_p0_model_availability.py",
    "tests/test_audit_closure_p0_sequence_bundle.py",
    "tests/test_build_closure_e10_source_evidence.py",
    "tests/test_build_closure_synthesis.py",
    "tests/test_build_phase4_final_certification.py",
    "tests/test_build_thesis_evidence_matrix.py",
    "tests/test_closure_e0_u_activation_lock.py",
    "tests/test_closure_e0_u_authority.py",
    "tests/test_closure_e6_e9_unavailable.py",
    "tests/test_closure_phase3_context.py",
    "tests/test_closure_phase3_e1_e2_e3_e5_contracts.py",
    "tests/test_closure_phase3_e4_e7_contracts.py",
    "tests/test_closure_phase3_e8_locked_uncertainty.py",
    "tests/test_closure_phase3_input_overlay.py",
    "tests/test_closure_synthesis_contract.py",
    "tests/test_lock_closure_synthesis.py",
    "tests/test_lock_phase4_final_certification.py",
    "tests/test_phase4_final_certification_contract.py",
    "tests/test_prepare_commit_artifacts.py",
    "tests/test_validate_phase4_manuscript.py",
)

EXACT_SKIPPED_NODES = (
    "tests/test_build_closure_holdout.py::test_protocol_lock_requires_the_exact_selector_hash",
    "tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[assignment_created-holdout_assignment_created=false]",
    "tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[dirty_locked_repository-worktree_status='clean']",
    "tests/test_build_closure_holdout.py::test_cli_dry_run_does_not_read_panel_or_write_outputs",
    "tests/test_build_closure_synthesis.py::test_check_only_before_p_syn_is_non_writing",
    "tests/test_closure_final_calibration.py::test_lock_validation_rejects_authorization_and_boundary_drifts",
    "tests/test_closure_final_calibration.py::test_output_contract_is_exact_manifest_last_and_zero_overlap",
)
EXACT_SKIP_REASON = "final_certification_raw_or_historical_state_prohibited"
E2E_NODES = (
    "tests/test_api_predictions_alerts.py::test_api_exposes_current_state_predictions_and_alerts",
    "tests/test_api_counterfactual_simulation.py::test_api_runs_minimal_current_state_counterfactual",
    "tests/test_api_run_artifacts.py::test_api_lists_previews_and_summarizes_run_artifacts",
)
TEST_COMMAND_TEMPLATE = (
    ".venv/bin/python",
    "-m",
    "pytest",
    "{selectors}",
    "-ra",
    "-p",
    "src.reporting.build_phase4_final_certification",
    "-p",
    "no:cacheprovider",
    "--junitxml={junit_path}",
)
STATIC_COMMANDS = ((".venv/bin/ty", "check"), ("poetry", "check", "--lock"))

FORBIDDEN_READ_PREFIXES = (
    "private/",
    "data/targets/",
    "data/closure_v1/unblinded/",
    "data/closure_v1/evaluation_outcomes/",
)
FORBIDDEN_READ_PATHS = (
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl",
)

STOP_RULES = (
    "refs_or_live_remote_drift",
    "topology_scope_mode_or_blob_drift",
    "pending_or_changed_test_suite_lock",
    "attempt_to_execute_from_superseded_p1",
    "unexpected_clone_directory_nlink_delta",
    "primary_error_loss_after_safe_cleanup_or_unowned_cleanup",
    "non_pristine_clone_or_cache",
    "forbidden_path_or_parquet_open",
    "dvc_pull_scope_or_pointer_drift",
    "test_failure_error_or_unregistered_skip",
    "openapi_or_e2e_contract_drift",
    "existing_partial_or_extra_output",
    "credential_remote_url_database_url_or_absolute_path_leak",
    "source_git_or_dvc_mutation",
    "attempt_to_run_e0_u_e1_e10_fit_score_or_calibration",
    "attempt_to_begin_post_phase4_work",
)

AUTHORIZATION_POLICY: Mapping[str, bool] = {
    "certification_execution_authorized_after_publication": True,
    "isolated_clone_authorized": True,
    "directed_dvc_pull_authorized": True,
    "public_test_execution_authorized": True,
    "openapi_generation_authorized": True,
    "synthetic_e2e_authorized": True,
    "loopback_postgresql_fixture_authorized": True,
    "main_worktree_dvc_mutation_authorized": False,
    "dvc_add_authorized": False,
    "dvc_push_authorized": False,
    "git_commit_push_tag_authorized": False,
    "raw_outcome_access_authorized": False,
    "raw_target_access_authorized": False,
    "parquet_open_or_decode_authorized": False,
    "model_fit_or_reconstruction_authorized": False,
    "rescore_or_recalibrate_authorized": False,
    "rerun_e0_u_or_e1_e10_authorized": False,
    "post_phase4_work_authorized": False,
}
PROHIBITIONS: Mapping[str, bool] = {
    "main_worktree_mutation": True,
    "raw_or_outcome_access": True,
    "parquet_open_or_decode": True,
    "dvc_add_or_push": True,
    "model_fit_reconstruction_rescore_or_recalibration": True,
    "rerun_e0_u_or_e1_e10": True,
    "git_commit_push_or_tag_by_orchestrator": True,
    "post_phase4_work": True,
}


def _error(message: str) -> FinalCertificationContractError:
    return FinalCertificationContractError(message)


def canonical_json_bytes(payload: Any) -> bytes:
    """Encode canonical JSON with one trailing LF and no NaN values."""

    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def digest_strings(values: Sequence[str]) -> str:
    return sha256_bytes(canonical_json_bytes(list(values)))


def digest_records(records: Sequence[Mapping[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(list(records)))


def expected_h_scope() -> dict[str, str]:
    """Return the operational H-CERT2 scope (legacy adapter alias)."""

    return {item.path: item.status for item in H_SCOPE}


def expected_p_scope() -> dict[str, str]:
    """Return the operational P-CERT2 scope (legacy adapter alias)."""

    return {item.path: item.status for item in P_SCOPE}


def expected_r_scope() -> dict[str, str]:
    return {item.path: item.status for item in R_SCOPE}


def expected_h1_scope() -> dict[str, str]:
    return {item.path: item.status for item in H1_SCOPE}


def expected_p1_scope() -> dict[str, str]:
    return {item.path: item.status for item in P1_SCOPE}


def expected_h_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H_SCOPE}


def expected_p_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P_SCOPE}


def expected_r_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in R_SCOPE}


def expected_h1_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H1_SCOPE}


def expected_p1_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P1_SCOPE}


def _require_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error(f"{context} must be a mapping")
    return cast(Mapping[str, Any], value)


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], *, context: str
) -> None:
    observed = set(value)
    if observed != expected:
        raise _error(
            f"{context} keys drifted: expected {sorted(expected)}, "
            f"observed {sorted(observed)}"
        )


def _require_list(value: Any, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise _error(f"{context} must be a list")
    return value


def _require_text(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise _error(f"{context} must be non-empty trimmed text")
    return value


def _require_int(value: Any, *, context: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise _error(f"{context} must be an integer >= {minimum}")
    return value


def _require_string_tuple(value: Any, *, context: str) -> tuple[str, ...]:
    result = _require_string_sequence(value, context=context)
    if len(result) != len(set(result)):
        raise _error(f"{context} contains duplicates")
    return result


def _require_string_sequence(value: Any, *, context: str) -> tuple[str, ...]:
    """Parse an ordered string sequence whose command flags may repeat."""

    return tuple(
        _require_text(item, context=f"{context}[{index}]")
        for index, item in enumerate(_require_list(value, context=context))
    )


def _safe_relative_path(value: str, *, context: str) -> PurePosixPath:
    if "\\" in value or "\x00" in value or any(
        marker in value for marker in ("*", "?", "[", "]", "{", "}")
    ):
        raise _error(f"{context} is not one literal POSIX path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise _error(f"{context} is not a normalized repository-relative path")
    return path


def _parse_scope(
    value: Any,
    *,
    stage: str,
    expected: tuple[PublicationPathSpec, ...],
) -> tuple[PublicationPathSpec, ...]:
    mapping = _require_mapping(value, context=f"publication_scopes.{stage}")
    _require_exact_keys(
        mapping,
        {"additions", "modifications", "ordered_paths"},
        context=f"publication_scopes.{stage}",
    )
    rows = _require_list(
        mapping["ordered_paths"],
        context=f"publication_scopes.{stage}.ordered_paths",
    )
    parsed: list[PublicationPathSpec] = []
    for index, raw in enumerate(rows):
        row = _require_mapping(raw, context=f"{stage} scope row {index}")
        _require_exact_keys(
            row, {"path", "status", "git_mode"}, context=f"{stage} scope row {index}"
        )
        path = _require_text(row["path"], context=f"{stage} scope path")
        _safe_relative_path(path, context=f"{stage} scope path")
        status = _require_text(row["status"], context=f"{stage} scope status")
        mode = _require_text(row["git_mode"], context=f"{stage} scope mode")
        if status not in {"A", "M"} or mode not in {"100644", "100755"}:
            raise _error(f"{stage} scope status or mode drifted")
        parsed.append(PublicationPathSpec(path, status, mode))
    result = tuple(parsed)
    additions = sum(item.status == "A" for item in result)
    modifications = sum(item.status == "M" for item in result)
    if (
        additions != _require_int(mapping["additions"], context=f"{stage} additions")
        or modifications
        != _require_int(mapping["modifications"], context=f"{stage} modifications")
        or result != expected
    ):
        raise _error(f"{stage} publication scope drifted")
    return result


def _parse_anchor_inputs(value: Any) -> tuple[AnchorInputSpec, ...]:
    records: list[AnchorInputSpec] = []
    for index, raw in enumerate(_require_list(value, context="anchor_inputs")):
        row = _require_mapping(raw, context=f"anchor_inputs[{index}]")
        _require_exact_keys(row, {"path", "role"}, context=f"anchor_inputs[{index}]")
        path = _require_text(row["path"], context=f"anchor_inputs[{index}].path")
        _safe_relative_path(path, context="anchor input path")
        records.append(
            AnchorInputSpec(
                path,
                _require_text(row["role"], context=f"anchor_inputs[{index}].role"),
            )
        )
    result = tuple(records)
    if result != ANCHOR_INPUTS:
        raise _error("Final-certification anchor input allowlist drifted")
    return result


def _parse_dvc_specs(value: Any) -> tuple[DvcPointerSpec, ...]:
    records: list[DvcPointerSpec] = []
    for index, raw in enumerate(_require_list(value, context="DVC pointers")):
        row = _require_mapping(raw, context=f"DVC pointer {index}")
        _require_exact_keys(
            row,
            {"path", "role", "output_path", "md5", "size"},
            context=f"DVC pointer {index}",
        )
        path = _require_text(row["path"], context=f"DVC pointer {index} path")
        output_path = _require_text(
            row["output_path"], context=f"DVC pointer {index} output"
        )
        _safe_relative_path(path, context="DVC pointer path")
        _safe_relative_path(output_path, context="DVC output path")
        md5 = _require_text(row["md5"], context=f"DVC pointer {index} md5")
        if not path.endswith(".parquet.dvc") or not output_path.endswith(".parquet"):
            raise _error("Final-certification DVC path dialect drifted")
        if MD5_RE.fullmatch(md5) is None:
            raise _error("Final-certification DVC md5 drifted")
        records.append(
            DvcPointerSpec(
                path,
                _require_text(row["role"], context=f"DVC pointer {index} role"),
                output_path,
                md5,
                _require_int(row["size"], context=f"DVC pointer {index} size", minimum=1),
            )
        )
    result = tuple(records)
    if result != DVC_POINTERS:
        raise _error("Final-certification exact-eight DVC inventory drifted")
    return result


def _parse_static_commands(value: Any) -> tuple[tuple[str, ...], ...]:
    commands = tuple(
        _require_string_tuple(raw, context=f"static_commands[{index}]")
        for index, raw in enumerate(
            _require_list(value, context="test_certification.static_commands")
        )
    )
    if commands != STATIC_COMMANDS:
        raise _error("Final-certification static command registry drifted")
    return commands


def _parse_test_suite(
    value: Any, *, allow_pending_suite: bool
) -> TestSuiteSpec:
    mapping = _require_mapping(value, context="test_certification")
    _require_exact_keys(
        mapping,
        {
            "suite_kind",
            "positive_test_paths",
            "exact_skipped_nodes",
            "exact_skip_reason",
            "e2e_nodes",
            "command_template",
            "static_commands",
            "loopback_postgresql_required",
            "unexpected_skips_authorized",
            "failures_or_errors_authorized",
            "suite_lock",
        },
        context="test_certification",
    )
    positive = _require_string_tuple(
        mapping["positive_test_paths"], context="positive_test_paths"
    )
    skipped = _require_string_tuple(
        mapping["exact_skipped_nodes"], context="exact_skipped_nodes"
    )
    e2e = _require_string_tuple(mapping["e2e_nodes"], context="e2e_nodes")
    command = _require_string_sequence(
        mapping["command_template"], context="test command template"
    )
    static_commands = _parse_static_commands(mapping["static_commands"])
    if (
        mapping["suite_kind"] != "closure_phase4_final_public"
        or positive != POSITIVE_TEST_PATHS
        or skipped != EXACT_SKIPPED_NODES
        or mapping["exact_skip_reason"] != EXACT_SKIP_REASON
        or e2e != E2E_NODES
        or command != TEST_COMMAND_TEMPLATE
        or static_commands != STATIC_COMMANDS
        or mapping["loopback_postgresql_required"] is not True
        or mapping["unexpected_skips_authorized"] is not False
        or mapping["failures_or_errors_authorized"] is not False
    ):
        raise _error("Final-certification public test contract drifted")
    lock = _require_mapping(mapping["suite_lock"], context="suite_lock")
    _require_exact_keys(
        lock,
        {
            "status",
            "selector_count",
            "collected_test_count",
            "nodeids_sha256",
            "allowed_skip_count",
        },
        context="suite_lock",
    )
    status = _require_text(lock["status"], context="suite_lock.status")
    allowed_skips = _require_int(
        lock["allowed_skip_count"], context="suite_lock.allowed_skip_count"
    )
    if (
        allowed_skips != LOCKED_SUITE_ALLOWED_SKIP_COUNT
        or allowed_skips != len(EXACT_SKIPPED_NODES)
    ):
        raise _error("Final-certification skip count drifted")

    selected_files = set(positive)
    supplemental = tuple(
        node for node in skipped if node.split("::", 1)[0] not in selected_files
    )
    exact_selector_count = len(positive) + len(supplemental)
    if status == "pending_integration":
        if any(
            lock[key] is not None
            for key in ("selector_count", "collected_test_count", "nodeids_sha256")
        ):
            raise _error("Pending suite lock must use null count and digest fields")
        if not allow_pending_suite:
            raise _error(
                "Final-certification suite lock is pending integration; "
                "seal count and node-id digest before H-CERT publication"
            )
        selector_count: int | None = None
        collected_test_count: int | None = None
        nodeids_sha256: str | None = None
    elif status == LOCKED_SUITE_STATUS:
        selector_count = _require_int(
            lock["selector_count"], context="suite_lock.selector_count", minimum=1
        )
        collected_test_count = _require_int(
            lock["collected_test_count"],
            context="suite_lock.collected_test_count",
            minimum=allowed_skips + 1,
        )
        nodeids_sha256 = _require_text(
            lock["nodeids_sha256"], context="suite_lock.nodeids_sha256"
        )
        if (
            selector_count != LOCKED_SUITE_SELECTOR_COUNT
            or exact_selector_count != LOCKED_SUITE_SELECTOR_COUNT
            or nodeids_sha256 != LOCKED_SUITE_NODEIDS_SHA256
            or SHA256_RE.fullmatch(nodeids_sha256) is None
        ):
            raise _error("Locked final-certification suite identity drifted")
        if collected_test_count != LOCKED_SUITE_COLLECTED_TEST_COUNT:
            raise _error("Locked final-certification collected count drifted")
    else:
        raise _error("Final-certification suite status is unsupported")

    return TestSuiteSpec(
        suite_kind="closure_phase4_final_public",
        positive_test_paths=positive,
        exact_skipped_nodes=skipped,
        exact_skip_reason=EXACT_SKIP_REASON,
        e2e_nodes=e2e,
        command_template=command,
        static_commands=static_commands,
        status=status,
        selector_count=selector_count,
        collected_test_count=collected_test_count,
        nodeids_sha256=nodeids_sha256,
        allowed_skip_count=allowed_skips,
    )


def _expected_topology() -> Mapping[str, Any]:
    return {
        "ordered_stages": ["H-CERT1", "P-CERT1", "H-CERT", "P-CERT", "R-CERT"],
        "H-CERT1": {
            "role": "historical_initial_implementation_schema_tests_and_freeze",
            "commit": "h1_cert_commit",
            "direct_parent": "editorial_commit",
            "certification_execution_authorized": False,
        },
        "P-CERT1": {
            "role": "superseded_failed_final_certification_authority",
            "commit": "p1_cert_commit",
            "requires_published_H_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "after_git_clone_namespace_validation",
            "dvc_pull_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "manifest_written_last": True,
        },
        "H-CERT": {
            "role": "corrective_runtime_contract_tests_and_freeze",
            "direct_parent": "p1_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "post_clone_nlink_delta_exact_one",
                "clone_registered_for_early_cleanup",
                "primary_error_preserved_when_safe_cleanup_passes",
            ],
        },
        "P-CERT": {
            "role": "data_only_final_certification_authority_v2",
            "requires_published_H_CERT": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized_while_unpublished": False,
            "manifest_written_last": True,
        },
        "R-CERT": {
            "role": "final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT": True,
            "output_count": 8,
            "manifest_written_last": True,
        },
        "single_parent_commits_required": True,
        "closure_source_commit_must_remain_ancestor": True,
        "aligned_refs_and_live_remote_required": True,
        "clean_worktree_and_index_required_at_each_gate": True,
        "main_dvc_status_must_equal_empty_object": True,
        "git_commit_push_and_tag_are_manual_user_actions": True,
    }


def _expected_dvc_controls() -> Mapping[str, Any]:
    return {
        "mode": "remote_pull_in_isolated_clone_with_initially_empty_cache",
        "pointer_count": 8,
        "pull_command_template": list(DVC_PULL_COMMAND_TEMPLATE),
        "one_pointer_per_command": True,
        "tracked_config_contains_remote": False,
        "ignored_local_remote_configuration_required": True,
        "ignored_local_remote_configuration_serialized": False,
        "cache_initially_empty": True,
        "main_worktree_written": False,
        "dvc_add_authorized": False,
        "dvc_push_authorized": False,
        "parquet_open_or_decode_authorized": False,
    }


def _expected_isolation() -> Mapping[str, Any]:
    return {
        "clone_source": "live_origin_main",
        "clone_must_be_exact_p_cert": True,
        "clone_must_be_initially_clean": True,
        "clone_and_cache_under_owned_temporary_root": True,
        "source_worktree_read_only_during_verification": True,
        "host_virtualenv_read_only": True,
        "expected_runtime_versions": dict(EXPECTED_RUNTIME_VERSIONS),
        "network_policy": {
            "git_clone_from_origin": "allowed",
            "eight_directed_dvc_pulls": "allowed",
            "loopback_postgresql": "allowed",
            "scientific_or_general_network": "forbidden",
        },
        "forbidden_read_prefixes": list(FORBIDDEN_READ_PREFIXES),
        "forbidden_read_paths": list(FORBIDDEN_READ_PATHS),
        "restored_parquet_payloads_are_transport_evidence_only": True,
        "absolute_paths_serialized": False,
        "remote_urls_serialized": False,
        "credentials_serialized": False,
        "database_urls_serialized": False,
        "orchestrator_git_commit_push_tag_authorized": False,
        "fixture_git_commits_only_in_owned_tmp_repositories": True,
        "rerun_e0_u_or_e1_e10_authorized": False,
        "refit_rescore_recalibrate_authorized": False,
        "concurrency_lock": "flock_retained_git_directory",
        "legacy_guard_path_must_be_absent": GUARD_PATH.as_posix(),
        "external_namespace_mutation_is_stop_condition": True,
        "noncooperating_same_uid_namespace_mutation": "out_of_scope",
        "identity_revalidated_before_and_after_name_cleanup": True,
        "conditional_unlink_by_inode_claimed": False,
        "no_clobber": True,
        "cleanup_before_precommit": True,
        "post_clone_directory_nlink_delta": 1,
        "post_clone_nlink_delta_stage": "after_git_clone",
        "clone_registered_after_exact_transition_check_before_subsequent_validation": True,
        "early_cleanup_inventory_claim_required": True,
        "primary_error_preserved_when_safe_cleanup_passes": True,
        "superseded_p1_retry_authorized": False,
    }


def _expected_outputs() -> Mapping[str, Any]:
    return {
        "root": CERTIFICATION_ROOT.as_posix(),
        "output_count": len(OUTPUT_PATHS),
        "manifest_written_last": True,
        "ordered_paths": list(OUTPUT_PATHS),
        "final_manifest_status": "completed",
        "final_report_claim_boundary": (
            "software_restorability_and_reproducibility_not_scientific_efficacy"
        ),
    }


def validate_contract_payload(
    payload: Any,
    *,
    path: Path = DEFAULT_CONTRACT_PATH,
    root: Path = PROJECT_ROOT,
    verify_inputs: bool = True,
    allow_pending_suite: bool = False,
) -> FinalCertificationContract:
    """Validate an already-decoded contract and return its typed projection."""

    mapping = _require_mapping(payload, context="final-certification contract")
    _require_exact_keys(
        mapping,
        {
            "contract_version",
            "authorities",
            "topology",
            "publication_scopes",
            "anchor_inputs",
            "dvc_restoration",
            "test_certification",
            "openapi_certification",
            "isolation",
            "outputs",
            "stop_rules",
        },
        context="final-certification contract",
    )
    if mapping["contract_version"] != CONTRACT_VERSION:
        raise _error("Final-certification contract version drifted")

    authorities = _require_mapping(mapping["authorities"], context="authorities")
    expected_authorities = {
        "closure_source_commit": CLOSURE_SOURCE_COMMIT,
        "r_syn_commit": R_SYN_COMMIT,
        "editorial_commit": EDITORIAL_COMMIT,
        "h1_cert_commit": H1_CERT_COMMIT,
        "p1_cert_commit": P1_CERT_COMMIT,
        "final_tag": FINAL_TAG,
        "certification_target": "published_P_CERT_v2_commit",
        "r_cert_executable_tree_must_equal_p_cert": True,
    }
    if dict(authorities) != expected_authorities:
        raise _error("Final-certification authority identities drifted")
    if not all(
        COMMIT_RE.fullmatch(str(authorities[key]))
        for key in (
            "closure_source_commit",
            "r_syn_commit",
            "editorial_commit",
            "h1_cert_commit",
            "p1_cert_commit",
        )
    ):
        raise _error("Final-certification commit syntax drifted")

    topology = _require_mapping(mapping["topology"], context="topology")
    if dict(topology) != _expected_topology():
        raise _error("Final-certification topology drifted")

    scopes = _require_mapping(
        mapping["publication_scopes"], context="publication_scopes"
    )
    _require_exact_keys(
        scopes,
        {"H-CERT1", "P-CERT1", "H-CERT", "P-CERT", "R-CERT"},
        context="publication_scopes",
    )
    h1_scope = _parse_scope(
        scopes["H-CERT1"], stage="H-CERT1", expected=H1_SCOPE
    )
    p1_scope = _parse_scope(
        scopes["P-CERT1"], stage="P-CERT1", expected=P1_SCOPE
    )
    h_scope = _parse_scope(scopes["H-CERT"], stage="H-CERT", expected=H_SCOPE)
    p_scope = _parse_scope(scopes["P-CERT"], stage="P-CERT", expected=P_SCOPE)
    r_scope = _parse_scope(scopes["R-CERT"], stage="R-CERT", expected=R_SCOPE)

    anchors = _parse_anchor_inputs(mapping["anchor_inputs"])

    dvc = _require_mapping(mapping["dvc_restoration"], context="dvc_restoration")
    _require_exact_keys(
        dvc,
        {*_expected_dvc_controls(), "pointers"},
        context="dvc_restoration",
    )
    controls = {key: dvc[key] for key in _expected_dvc_controls()}
    if controls != _expected_dvc_controls():
        raise _error("Final-certification DVC restoration controls drifted")
    dvc_pointers = _parse_dvc_specs(dvc["pointers"])

    test_suite = _parse_test_suite(
        mapping["test_certification"],
        allow_pending_suite=allow_pending_suite,
    )

    openapi = _require_mapping(
        mapping["openapi_certification"], context="openapi_certification"
    )
    expected_openapi = {
        "version_prefix": "3.",
        "expected_path_count": 69,
        "expected_operation_count": 83,
        "expected_documented_operation_count": 38,
        "operation_ids_unique": True,
        "path_parameters_exact": True,
        "missing_documented_operations": 0,
    }
    if dict(openapi) != expected_openapi:
        raise _error("Final-certification OpenAPI expectations drifted")

    isolation = _require_mapping(mapping["isolation"], context="isolation")
    if dict(isolation) != _expected_isolation():
        raise _error("Final-certification isolation boundary drifted")

    outputs = _require_mapping(mapping["outputs"], context="outputs")
    if dict(outputs) != _expected_outputs():
        raise _error("Final-certification output order or claim boundary drifted")

    stop_rules = _require_string_tuple(mapping["stop_rules"], context="stop_rules")
    if stop_rules != STOP_RULES:
        raise _error("Final-certification STOP rules drifted")

    contract = FinalCertificationContract(
        path=path,
        raw=mapping,
        closure_source_commit=CLOSURE_SOURCE_COMMIT,
        r_syn_commit=R_SYN_COMMIT,
        editorial_commit=EDITORIAL_COMMIT,
        h1_cert_commit=H1_CERT_COMMIT,
        p1_cert_commit=P1_CERT_COMMIT,
        final_tag=FINAL_TAG,
        h1_scope=h1_scope,
        p1_scope=p1_scope,
        h_scope=h_scope,
        p_scope=p_scope,
        r_scope=r_scope,
        anchor_inputs=anchors,
        dvc_pointers=dvc_pointers,
        dvc_pull_command_template=DVC_PULL_COMMAND_TEMPLATE,
        test_suite=test_suite,
        expected_openapi_path_count=69,
        expected_openapi_operation_count=83,
        expected_documented_operation_count=38,
        forbidden_read_prefixes=FORBIDDEN_READ_PREFIXES,
        forbidden_read_paths=FORBIDDEN_READ_PATHS,
        output_paths=OUTPUT_PATHS,
        expected_runtime_versions=EXPECTED_RUNTIME_VERSIONS,
        concurrency_lock="flock_retained_git_directory",
        legacy_guard_path_must_be_absent=GUARD_PATH.as_posix(),
        external_namespace_mutation_is_stop_condition=True,
        noncooperating_same_uid_namespace_mutation="out_of_scope",
        identity_revalidated_before_and_after_name_cleanup=True,
        conditional_unlink_by_inode_claimed=False,
        no_clobber=True,
        cleanup_before_precommit=True,
        stop_rules=STOP_RULES,
    )
    if verify_inputs:
        collect_anchor_input_records(contract, root=root)
        collect_dvc_pointer_records(contract, root=root)
    return contract


@dataclass(frozen=True)
class _DirectoryBinding:
    parent_fd: int
    name: str
    fd: int
    device: int
    inode: int
    mode: int


@dataclass(frozen=True)
class _AnchoredRegularFile:
    path: Path
    root_parent_fd: int
    directories: tuple[_DirectoryBinding, ...]
    parent_fd: int
    name: str
    fd: int
    metadata: os.stat_result
    context: str


def _file_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_nlink,
        stat.S_IMODE(metadata.st_mode),
    )


def _open_directory_binding(
    parent_fd: int,
    name: str,
    *,
    context: str,
) -> _DirectoryBinding:
    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} directory name is unsafe")
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise _error(f"{context} directory is unavailable: {name}") from exc
    if stat.S_ISLNK(named.st_mode) or not stat.S_ISDIR(named.st_mode):
        raise _error(f"{context} directory is not no-follow: {name}")
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=parent_fd,
    )
    observed = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(observed.st_mode)
        or (observed.st_dev, observed.st_ino) != (named.st_dev, named.st_ino)
    ):
        os.close(descriptor)
        raise _error(f"{context} directory changed while opening: {name}")
    return _DirectoryBinding(
        parent_fd,
        name,
        descriptor,
        observed.st_dev,
        observed.st_ino,
        stat.S_IMODE(observed.st_mode),
    )


def _open_anchored_regular_file(
    root: Path,
    path_text: str,
    *,
    expected_modes: frozenset[int] | None,
    context: str,
) -> _AnchoredRegularFile:
    relative = _safe_relative_path(path_text, context=f"{context} path")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise _error(f"{context} repository root is unavailable") from exc
    if resolved_root == resolved_root.parent:
        raise _error(f"{context} repository root cannot be the filesystem root")
    root_parent_fd = os.open(
        resolved_root.parent,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    directories: list[_DirectoryBinding] = []
    file_fd: int | None = None
    try:
        root_binding = _open_directory_binding(
            root_parent_fd,
            resolved_root.name,
            context=context,
        )
        directories.append(root_binding)
        current_fd = root_binding.fd
        for part in relative.parts[:-1]:
            binding = _open_directory_binding(current_fd, part, context=context)
            directories.append(binding)
            current_fd = binding.fd
        name = relative.parts[-1]
        try:
            named = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
        except OSError as exc:
            raise _error(f"{context} is unavailable: {path_text}") from exc
        mode = stat.S_IMODE(named.st_mode)
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or named.st_nlink != 1
            or (expected_modes is not None and mode not in expected_modes)
        ):
            raise _error(
                f"{context} must be a permitted single-link regular file: "
                f"{path_text}"
            )
        file_fd = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=current_fd,
        )
        opened = os.fstat(file_fd)
        if not stat.S_ISREG(opened.st_mode) or _file_identity(opened) != _file_identity(
            named
        ):
            raise _error(f"{context} changed while opening: {path_text}")
        return _AnchoredRegularFile(
            resolved_root.joinpath(*relative.parts),
            root_parent_fd,
            tuple(directories),
            current_fd,
            name,
            file_fd,
            opened,
            context,
        )
    except BaseException:
        if file_fd is not None:
            os.close(file_fd)
        for binding in reversed(directories):
            os.close(binding.fd)
        os.close(root_parent_fd)
        raise


def _revalidate_anchored_file(anchored: _AnchoredRegularFile) -> os.stat_result:
    for binding in anchored.directories:
        try:
            named = os.stat(
                binding.name,
                dir_fd=binding.parent_fd,
                follow_symlinks=False,
            )
            opened = os.fstat(binding.fd)
        except OSError as exc:
            raise _error(
                f"{anchored.context} ancestor disappeared during validation"
            ) from exc
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISDIR(named.st_mode)
            or not stat.S_ISDIR(opened.st_mode)
            or (named.st_dev, named.st_ino, stat.S_IMODE(named.st_mode))
            != (binding.device, binding.inode, binding.mode)
            or (opened.st_dev, opened.st_ino, stat.S_IMODE(opened.st_mode))
            != (binding.device, binding.inode, binding.mode)
        ):
            raise _error(f"{anchored.context} ancestor binding drifted")
    try:
        named_file = os.stat(
            anchored.name,
            dir_fd=anchored.parent_fd,
            follow_symlinks=False,
        )
        opened_file = os.fstat(anchored.fd)
    except OSError as exc:
        raise _error(f"{anchored.context} name disappeared during validation") from exc
    if (
        stat.S_ISLNK(named_file.st_mode)
        or not stat.S_ISREG(named_file.st_mode)
        or _file_identity(named_file) != _file_identity(opened_file)
        or _file_identity(opened_file) != _file_identity(anchored.metadata)
    ):
        raise _error(f"{anchored.context} name or identity drifted")
    return opened_file


def _close_anchored_file(anchored: _AnchoredRegularFile) -> None:
    os.close(anchored.fd)
    for binding in reversed(anchored.directories):
        os.close(binding.fd)
    os.close(anchored.root_parent_fd)


def _read_stable_file(anchored: _AnchoredRegularFile) -> bytes:
    before = _revalidate_anchored_file(anchored)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(anchored.fd, HASH_CHUNK_SIZE)
        if not chunk:
            break
        chunks.append(chunk)
    after = os.fstat(anchored.fd)
    if _file_identity(after) != _file_identity(before):
        raise _error(f"{anchored.context} changed while reading")
    _revalidate_anchored_file(anchored)
    return b"".join(chunks)


def _read_contract_file(root: Path, path_text: str) -> bytes:
    anchored = _open_anchored_regular_file(
        root,
        path_text,
        expected_modes=frozenset({0o644}),
        context="Final-certification contract",
    )
    try:
        return _read_stable_file(anchored)
    finally:
        _close_anchored_file(anchored)


def load_contract(
    *,
    root: Path = PROJECT_ROOT,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    verify_inputs: bool = True,
    allow_pending_suite: bool = False,
) -> FinalCertificationContract:
    """Load and strictly validate the final Phase 4 certification contract."""

    if contract_path.is_absolute():
        try:
            relative_contract = contract_path.relative_to(root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise _error("Final-certification contract must remain below root") from exc
    else:
        relative_contract = contract_path
    payload = _read_contract_file(root, relative_contract.as_posix())
    try:
        decoded = yaml.safe_load(payload.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise _error("Final-certification contract is not valid UTF-8 YAML") from exc
    return validate_contract_payload(
        decoded,
        path=contract_path,
        root=root,
        verify_inputs=verify_inputs,
        allow_pending_suite=allow_pending_suite,
    )


def parse_dvc_pointer_bytes(
    payload: bytes, pointer_path: str | Path
) -> dict[str, Any]:
    """Parse one exact, single-file MD5 DVC pointer without resolving it."""

    raw_path = Path(pointer_path).as_posix()
    _safe_relative_path(raw_path, context="DVC pointer path")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _error(f"DVC pointer is not UTF-8: {raw_path}") from exc
    match = re.fullmatch(
        r"outs:\n"
        r"- md5: ([0-9a-f]{32})\n"
        r"  size: ([1-9][0-9]*)\n"
        r"  hash: md5\n"
        r"  path: ([A-Za-z0-9_.-]+)\n",
        text,
    )
    if match is None:
        raise _error(f"DVC pointer dialect drifted: {raw_path}")
    md5, size_text, output_name = match.groups()
    expected_name = Path(raw_path).with_suffix("").name
    if output_name != expected_name or not output_name.endswith(".parquet"):
        raise _error(f"DVC pointer output name drifted: {raw_path}")
    output_path = (Path(raw_path).parent / output_name).as_posix()
    return {
        "md5": md5,
        "size": int(size_text),
        "output_name": output_name,
        "output_path": output_path,
    }


def _run_git(root: Path, *args: str, text: bool) -> str | bytes:
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=text,
        env=environment,
    )
    if process.returncode != 0:
        stderr = (
            cast(str, process.stderr).strip()
            if text
            else cast(bytes, process.stderr).decode("utf-8", "replace").strip()
        )
        raise _error(f"git {' '.join(args)} failed: {stderr}")
    return process.stdout


def _git_blob_identity(root: Path, commit: str, path_text: str) -> tuple[str, str]:
    output = cast(
        str, _run_git(root, "ls-tree", commit, "--", path_text, text=True)
    ).strip()
    fields = output.split(None, 3)
    if (
        len(fields) != 4
        or fields[0] != "100644"
        or fields[1] != "blob"
        or not re.fullmatch(r"[0-9a-f]{40,64}", fields[2])
        or fields[3] != path_text
    ):
        raise _error(f"Public anchor is not one exact editorial Git blob: {path_text}")
    return fields[0], fields[2]


def _regular_repo_file(root: Path, path_text: str) -> _AnchoredRegularFile:
    return _open_anchored_regular_file(
        root,
        path_text,
        expected_modes=frozenset({0o644}),
        context="Public anchor",
    )


def _collect_git_bound_file(
    root: Path, *, path_text: str, role: str, commit: str
) -> tuple[dict[str, Any], bytes]:
    anchored = _regular_repo_file(root, path_text)
    try:
        payload = _read_stable_file(anchored)
        git_mode, git_blob_oid = _git_blob_identity(root, commit, path_text)
        git_payload = cast(
            bytes,
            _run_git(
                root,
                "cat-file",
                "blob",
                f"{commit}:{path_text}",
                text=False,
            ),
        )
        _revalidate_anchored_file(anchored)
        if payload != git_payload:
            raise _error(f"Public anchor differs from editorial Git: {path_text}")
        return (
            {
                "path": path_text,
                "role": role,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "git_mode": git_mode,
                "git_blob_oid": git_blob_oid,
                "repository_commit": commit,
            },
            payload,
        )
    finally:
        _close_anchored_file(anchored)


def collect_anchor_input_records(
    contract: FinalCertificationContract, *, root: Path = PROJECT_ROOT
) -> list[dict[str, Any]]:
    """Collect exact editorial-Git identities for the ten public anchors."""

    records = [
        _collect_git_bound_file(
            root,
            path_text=spec.path,
            role=spec.role,
            commit=contract.editorial_commit,
        )[0]
        for spec in contract.anchor_inputs
    ]
    if tuple(record["path"] for record in records) != contract.anchor_input_paths:
        raise _error("Public anchor record order drifted")
    return records


def collect_dvc_pointer_records(
    contract: FinalCertificationContract, *, root: Path = PROJECT_ROOT
) -> list[dict[str, Any]]:
    """Validate the eight Git-bound pointers without opening their payloads."""

    records: list[dict[str, Any]] = []
    for spec in contract.dvc_pointers:
        base, payload = _collect_git_bound_file(
            root,
            path_text=spec.path,
            role=spec.role,
            commit=contract.editorial_commit,
        )
        parsed = parse_dvc_pointer_bytes(payload, spec.path)
        if (
            parsed["md5"] != spec.md5
            or parsed["size"] != spec.size
            or parsed["output_path"] != spec.output_path
        ):
            raise _error(f"DVC pointer declaration drifted: {spec.path}")
        records.append(
            {
                **base,
                "output_path": spec.output_path,
                "payload_md5": spec.md5,
                "payload_bytes": spec.size,
                "parquet_payload_opened": False,
            }
        )
    if tuple(record["path"] for record in records) != contract.dvc_pointer_paths:
        raise _error("DVC pointer record order drifted")
    return records


def test_suite_record(contract: FinalCertificationContract) -> dict[str, Any]:
    """Return the exact canonical P-CERT projection of the locked suite."""

    suite = contract.test_suite
    if (
        suite.status != "locked"
        or suite.selector_count is None
        or suite.collected_test_count is None
        or suite.nodeids_sha256 is None
    ):
        raise _error("P-CERT requires a fully locked final-certification suite")
    return {
        "suite_kind": suite.suite_kind,
        "positive_test_paths": list(suite.positive_test_paths),
        "exact_skipped_nodes": list(suite.exact_skipped_nodes),
        "exact_skip_reason": suite.exact_skip_reason,
        "e2e_nodes": list(suite.e2e_nodes),
        "selectors": list(suite.selectors),
        "command_template": list(suite.command_template),
        "static_commands": [list(command) for command in suite.static_commands],
        "suite_lock": {
            "status": suite.status,
            "selector_count": suite.selector_count,
            "collected_test_count": suite.collected_test_count,
            "nodeids_sha256": suite.nodeids_sha256,
            "allowed_skip_count": suite.allowed_skip_count,
        },
    }


def _publication_file_record_and_payload(
    root: Path,
    *,
    commit: str,
    spec: PublicationPathSpec,
) -> tuple[dict[str, Any], bytes]:
    expected_mode = int(spec.git_mode[-3:], 8)
    anchored = _open_anchored_regular_file(
        root,
        spec.path,
        expected_modes=frozenset({expected_mode}),
        context="Published certification component",
    )
    try:
        payload = _read_stable_file(anchored)
        output = cast(
            str, _run_git(root, "ls-tree", commit, "--", spec.path, text=True)
        ).strip()
        fields = output.split(None, 3)
        if (
            len(fields) != 4
            or fields[0] != spec.git_mode
            or fields[1] != "blob"
            or not re.fullmatch(r"[0-9a-f]{40,64}", fields[2])
            or fields[3] != spec.path
        ):
            raise _error(f"H-CERT component Git identity drifted: {spec.path}")
        git_payload = cast(
            bytes, _run_git(root, "cat-file", "blob", fields[2], text=False)
        )
        _revalidate_anchored_file(anchored)
        if payload != git_payload:
            raise _error(
                f"H-CERT component differs from published Git: {spec.path}"
            )
        return (
            {
                "path": spec.path,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "git_mode": spec.git_mode,
                "git_blob_oid": fields[2],
                "filesystem_mode": stat.S_IMODE(anchored.metadata.st_mode),
            },
            payload,
        )
    finally:
        _close_anchored_file(anchored)


def _publication_file_record(
    root: Path,
    *,
    commit: str,
    spec: PublicationPathSpec,
) -> dict[str, Any]:
    return _publication_file_record_and_payload(
        root,
        commit=commit,
        spec=spec,
    )[0]


def _git_publication_file_record_and_payload(
    root: Path,
    *,
    commit: str,
    spec: PublicationPathSpec,
    context: str,
) -> tuple[dict[str, Any], bytes]:
    """Reconstruct a historical component from Git without using live bytes."""

    output = cast(
        str, _run_git(root, "ls-tree", commit, "--", spec.path, text=True)
    ).strip()
    fields = output.split(None, 3)
    if (
        len(fields) != 4
        or fields[0] != spec.git_mode
        or fields[1] != "blob"
        or not re.fullmatch(r"[0-9a-f]{40,64}", fields[2])
        or fields[3] != spec.path
    ):
        raise _error(f"{context} is not one exact Git blob: {spec.path}")
    payload = cast(
        bytes, _run_git(root, "cat-file", "blob", fields[2], text=False)
    )
    if not payload:
        raise _error(f"{context} is empty: {spec.path}")
    return (
        {
            "path": spec.path,
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
            "git_mode": spec.git_mode,
            "git_blob_oid": fields[2],
        },
        payload,
    )


def collect_git_component_records(
    scope: Sequence[PublicationPathSpec],
    *,
    commit: str,
    root: Path = PROJECT_ROOT,
    context: str = "Historical certification component",
) -> list[dict[str, Any]]:
    if COMMIT_RE.fullmatch(commit) is None:
        raise _error(f"{context} commit syntax drifted")
    return [
        _git_publication_file_record_and_payload(
            root, commit=commit, spec=spec, context=context
        )[0]
        for spec in scope
    ]


def collect_h_component_records(
    contract: FinalCertificationContract,
    *,
    h_cert_commit: str,
    root: Path = PROJECT_ROOT,
) -> list[dict[str, Any]]:
    """Reconstruct every H-CERT component from physical and Git identities."""

    if COMMIT_RE.fullmatch(h_cert_commit) is None:
        raise _error("H-CERT commit syntax drifted")
    return [
        _publication_file_record(root, commit=h_cert_commit, spec=spec)
        for spec in contract.h_scope
    ]


def _decode_canonical_public_json(
    root: Path, relative: Path, *, commit: str
) -> tuple[Mapping[str, Any], bytes]:
    spec = PublicationPathSpec(relative.as_posix(), "A", "100644")
    _record, payload = _publication_file_record_and_payload(
        root,
        commit=commit,
        spec=spec,
    )
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _error(f"P-CERT JSON cannot be decoded: {relative}") from exc
    mapping = _require_mapping(decoded, context=relative.as_posix())
    if canonical_json_bytes(mapping) != payload:
        raise _error(f"P-CERT JSON is not canonical: {relative}")
    return mapping, payload


def _commit_parents(root: Path, commit: str) -> tuple[str, ...]:
    fields = cast(
        str, _run_git(root, "rev-list", "--parents", "-n", "1", commit, text=True)
    ).strip().split()
    if not fields or fields[0] != commit:
        raise _error(f"Cannot resolve commit parents: {commit}")
    return tuple(fields[1:])


def _commit_scope(root: Path, commit: str) -> dict[str, str]:
    output = cast(
        str,
        _run_git(
            root,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "--no-renames",
            "-r",
            f"{commit}^",
            commit,
            text=True,
        ),
    )
    result: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"A", "M"} or fields[1] in result:
            raise _error(f"Unsupported publication diff at {commit}")
        result[fields[1]] = fields[0]
    return result


def _one_commit(root: Path, ref: str) -> str:
    value = cast(
        str, _run_git(root, "rev-parse", "--verify", f"{ref}^{{commit}}", text=True)
    ).strip()
    if COMMIT_RE.fullmatch(value) is None:
        raise _error(f"Git ref is not one commit: {ref}")
    return value


def _require_effective_refs(
    root: Path, expected: str, *, verify_remote: bool
) -> dict[str, str]:
    refs = {
        "head": _one_commit(root, "HEAD"),
        "main": _one_commit(root, "main"),
        "origin_main": _one_commit(root, "origin/main"),
        "origin_head": _one_commit(root, "origin/HEAD"),
    }
    if set(refs.values()) != {expected}:
        raise _error("P-CERT local/tracking refs are not aligned")
    if verify_remote:
        output = cast(
            str,
            _run_git(
                root,
                "ls-remote",
                "--exit-code",
                "origin",
                "HEAD",
                "refs/heads/main",
                text=True,
            ),
        )
        remote: dict[str, str] = {}
        for line in output.splitlines():
            fields = line.split("\t")
            if (
                len(fields) != 2
                or COMMIT_RE.fullmatch(fields[0]) is None
                or fields[1] in remote
            ):
                raise _error("P-CERT live remote refs are malformed")
            remote[fields[1]] = fields[0]
        if (
            set(remote) != {"HEAD", "refs/heads/main"}
            or set(remote.values()) != {expected}
        ):
            raise _error("P-CERT live remote HEAD/main are not aligned")
        refs["remote_main"] = expected
    return refs


def _require_clean_git_state(root: Path) -> None:
    output = cast(
        str,
        _run_git(
            root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            text=True,
        ),
    )
    if output:
        raise _error("Effective P-CERT loader requires a clean worktree and index")


def _historical_h1_p1_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct the superseded H1/P1 chain without treating it as effective."""

    if (
        _commit_parents(root, contract.h1_cert_commit)
        != (contract.editorial_commit,)
        or _commit_scope(root, contract.h1_cert_commit) != expected_h1_scope()
        or _commit_parents(root, contract.p1_cert_commit)
        != (contract.h1_cert_commit,)
        or _commit_scope(root, contract.p1_cert_commit) != expected_p1_scope()
        or _commit_parents(root, contract.editorial_commit)
        != (contract.r_syn_commit,)
    ):
        raise _error("Historical H1/P1/editorial topology or scope drifted")
    h1_records = collect_git_component_records(
        contract.h1_scope,
        commit=contract.h1_cert_commit,
        root=root,
        context="Historical H-CERT1 component",
    )
    physical_p1_payloads = [
        _publication_file_record_and_payload(
            root,
            commit=contract.p1_cert_commit,
            spec=spec,
        )[1]
        for spec in contract.p1_scope
    ]
    authority, authority_bytes = _decode_canonical_public_json(
        root, H1_AUTHORITY_PATH, commit=contract.p1_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H1_AUTHORITY_MANIFEST_PATH, commit=contract.p1_cert_commit
    )
    if physical_p1_payloads != [authority_bytes, manifest_bytes]:
        raise _error("Historical P-CERT1 physical/Git bytes drifted")
    topology = authority.get("topology")
    if (
        authority.get("authority_version") != H1_AUTHORITY_VERSION
        or authority.get("gate") != "P-CERT"
        or authority.get("status") != "locked_unpublished"
        or not isinstance(topology, Mapping)
        or topology.get("h_cert_commit") != contract.h1_cert_commit
        or topology.get("p_cert_commit") is not None
        or authority.get("h_scope") != expected_h1_scope()
    ):
        raise _error("Historical P-CERT1 authority identity drifted")
    authority_record = {
        "path": H1_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    if manifest != {
        "manifest_version": H1_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h_cert_commit": contract.h1_cert_commit,
        "manifest_last": True,
        "ordered_paths": [
            H1_AUTHORITY_PATH.as_posix(),
            H1_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }:
        raise _error("Historical P-CERT1 companion identity drifted")
    p1_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p1_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p1_cert_commit,
            spec=spec,
            context="Historical P-CERT1 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT1 physical/Git bytes drifted")
        p1_records.append(record)
    return h1_records, p1_records


def _expected_effective_authority(
    contract: FinalCertificationContract,
    *,
    root: Path,
    h_cert_commit: str,
) -> dict[str, Any]:
    components = collect_h_component_records(
        contract, h_cert_commit=h_cert_commit, root=root
    )
    h1_records, p1_records = _historical_h1_p1_records(contract, root=root)
    anchors = collect_anchor_input_records(contract, root=root)
    pointers = collect_dvc_pointer_records(contract, root=root)
    suite = test_suite_record(contract)
    outputs = list(contract.output_paths)
    return {
        "authority_version": AUTHORITY_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "topology": {
            "closure_source_commit": contract.closure_source_commit,
            "r_syn_commit": contract.r_syn_commit,
            "editorial_commit": contract.editorial_commit,
            "h1_cert_commit": contract.h1_cert_commit,
            "p1_cert_commit": contract.p1_cert_commit,
            "h_cert_commit": h_cert_commit,
            "p_cert_commit": None,
            "r_cert_executable_tree_must_equal_p_cert": True,
        },
        "p1_failure": {
            "status": "superseded_failed",
            "failure_stage": "after_git_clone_namespace_validation",
            "dvc_pull_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
        },
        "h1_scope": expected_h1_scope(),
        "h1_component_records": h1_records,
        "h1_component_records_digest": digest_records(h1_records),
        "p1_scope": expected_p1_scope(),
        "p1_component_records": p1_records,
        "p1_component_records_digest": digest_records(p1_records),
        "h_scope": expected_h_scope(),
        "h_component_records": components,
        "h_component_records_digest": digest_records(components),
        "anchor_input_records": anchors,
        "anchor_input_records_digest": digest_records(anchors),
        "dvc_pointer_records": pointers,
        "dvc_pointer_records_digest": digest_records(pointers),
        "test_suite": suite,
        "test_suite_digest": sha256_bytes(canonical_json_bytes(suite)),
        "ordered_r_cert_output_paths": outputs,
        "r_cert_output_paths_digest": digest_strings(outputs),
        "isolation": dict(_expected_isolation()),
        "authorizations": dict(AUTHORIZATION_POLICY),
        "prohibitions": dict(PROHIBITIONS),
    }


def load_effective_authority(
    contract: FinalCertificationContract | None = None,
    *,
    root: Path = PROJECT_ROOT,
    verify_remote: bool = True,
    require_clean: bool = True,
) -> dict[str, Any]:
    """Load and independently reconstruct one published effective P-CERT2.

    The stored authority deliberately has ``p_cert_commit=null`` because it is
    generated before its publication commit exists.  Effectiveness is derived
    here from the observed exact P commit, direct H parent, exact scopes,
    canonical bytes, aligned refs and (by default) live remote.
    """

    active_contract = contract or load_contract(root=root)
    if active_contract.test_suite.status != "locked":
        raise _error("Effective P-CERT requires a locked public-test suite")
    if require_clean:
        _require_clean_git_state(root)
    p_cert_commit = _one_commit(root, "HEAD")
    parents = _commit_parents(root, p_cert_commit)
    if len(parents) != 1:
        raise _error("P-CERT2 must have exactly one H-CERT2 parent")
    h_cert_commit = parents[0]
    if (
        _commit_parents(root, h_cert_commit) != (active_contract.p1_cert_commit,)
        or _commit_scope(root, h_cert_commit) != expected_h_scope()
        or _commit_scope(root, p_cert_commit) != expected_p_scope()
    ):
        raise _error("Effective P-CERT2 H2/P2 topology or scope drifted")
    _historical_h1_p1_records(active_contract, root=root)
    ancestor = subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            active_contract.closure_source_commit,
            p_cert_commit,
        ],
        cwd=root,
        check=False,
        capture_output=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if ancestor.returncode != 0 or ancestor.stdout or ancestor.stderr:
        raise _error("Closure source is not a clean ancestor of effective P-CERT")
    refs = _require_effective_refs(root, p_cert_commit, verify_remote=verify_remote)
    authority, authority_bytes = _decode_canonical_public_json(
        root, AUTHORITY_PATH, commit=p_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, AUTHORITY_MANIFEST_PATH, commit=p_cert_commit
    )
    expected_authority = _expected_effective_authority(
        active_contract, root=root, h_cert_commit=h_cert_commit
    )
    if authority != expected_authority or authority_bytes != canonical_json_bytes(
        expected_authority
    ):
        raise _error("Published P-CERT authority is not independently reproducible")
    authority_record = {
        "path": AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": active_contract.h1_cert_commit,
        "p1_cert_commit": active_contract.p1_cert_commit,
        "h_cert_commit": h_cert_commit,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [AUTHORITY_PATH.as_posix(), AUTHORITY_MANIFEST_PATH.as_posix()],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Published P-CERT companion is not independently reproducible")
    return {
        "status": "effective",
        "gate": "P-CERT",
        "p_cert_commit": p_cert_commit,
        "h_cert_commit": h_cert_commit,
        "p2_cert_commit": p_cert_commit,
        "h2_cert_commit": h_cert_commit,
        "p1_cert_commit": active_contract.p1_cert_commit,
        "h1_cert_commit": active_contract.h1_cert_commit,
        "repository": refs,
        "authority": authority,
        "authority_bytes": authority_bytes,
        "authority_sha256": sha256_bytes(authority_bytes),
        "manifest": manifest,
        "manifest_bytes": manifest_bytes,
        "manifest_sha256": sha256_bytes(manifest_bytes),
    }


def validate_local_dvc_remote_configuration(
    *, root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Validate local DVC remote metadata without reading or hashing its contents.

    The returned projection intentionally omits the path, bytes, remote name,
    URL and credentials.  It is operational preflight state, never an
    authority input or public manifest record.
    """

    anchored = _open_anchored_regular_file(
        root,
        LOCAL_DVC_CONFIG_PATH.as_posix(),
        expected_modes=frozenset({0o600, 0o644}),
        context="Ignored local DVC remote configuration",
    )
    try:
        _revalidate_anchored_file(anchored)
        ignored = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                "--",
                LOCAL_DVC_CONFIG_PATH.as_posix(),
            ],
            cwd=root,
            check=False,
            capture_output=True,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        _revalidate_anchored_file(anchored)
        if ignored.returncode != 0 or ignored.stdout or ignored.stderr:
            raise _error("Local DVC remote configuration is not cleanly Git-ignored")
        return {
            "present": True,
            "regular_file": True,
            "single_link": True,
            "filesystem_mode": format(
                stat.S_IMODE(anchored.metadata.st_mode),
                "04o",
            ),
            "git_ignored": True,
            "content_opened": False,
            "content_or_path_serialized": False,
        }
    finally:
        _close_anchored_file(anchored)
