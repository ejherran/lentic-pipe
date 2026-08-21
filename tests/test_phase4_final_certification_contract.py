from __future__ import annotations

import copy
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.reporting import phase4_final_certification_contract as certification


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / certification.DEFAULT_CONTRACT_PATH
SCHEMA_PATH = ROOT / certification.DEFAULT_SCHEMA_PATH


def _payload() -> dict[str, Any]:
    decoded = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(decoded, dict)
    return decoded


def _locked_payload() -> dict[str, Any]:
    payload = _payload()
    lock = payload["test_certification"]["suite_lock"]
    lock.update(
        {
            "status": certification.LOCKED_SUITE_STATUS,
            "selector_count": certification.LOCKED_SUITE_SELECTOR_COUNT,
            "collected_test_count": certification.LOCKED_SUITE_COLLECTED_TEST_COUNT,
            "nodeids_sha256": certification.LOCKED_SUITE_NODEIDS_SHA256,
            "allowed_skip_count": certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT,
        }
    )
    return payload


def _pending_payload() -> dict[str, Any]:
    payload = _payload()
    payload["test_certification"]["suite_lock"] = {
        "status": "pending_integration",
        "selector_count": None,
        "collected_test_count": None,
        "nodeids_sha256": None,
        "allowed_skip_count": certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT,
    }
    return payload


def test_real_pending_contract_loads_without_opening_payloads() -> None:
    contract = certification.load_contract(
        root=ROOT,
        verify_inputs=True,
        allow_pending_suite=True,
    )

    assert contract.closure_source_commit == certification.CLOSURE_SOURCE_COMMIT
    assert contract.r_syn_commit == certification.R_SYN_COMMIT
    assert contract.editorial_commit == certification.EDITORIAL_COMMIT
    assert contract.h1_cert_commit == certification.H1_CERT_COMMIT
    assert contract.p1_cert_commit == certification.P1_CERT_COMMIT
    assert contract.h2_cert_commit == certification.H2_CERT_COMMIT
    assert contract.p2_cert_commit == certification.P2_CERT_COMMIT
    assert contract.h3_cert_commit == certification.H3_CERT_COMMIT
    assert contract.p3_cert_commit == certification.P3_CERT_COMMIT
    assert contract.h4_cert_commit == certification.H4_CERT_COMMIT
    assert contract.p4_cert_commit == certification.P4_CERT_COMMIT
    assert contract.h5_cert_commit == certification.H5_CERT_COMMIT
    assert contract.p5_cert_commit == certification.P5_CERT_COMMIT
    assert contract.h6_cert_commit == certification.H6_CERT_COMMIT
    assert contract.p6_cert_commit == certification.P6_CERT_COMMIT
    assert contract.final_tag == "thesis-closure-v1"
    assert len(contract.h_scope) == 11
    assert len(contract.p_scope) == 2
    assert len(contract.h2_scope) == 11
    assert len(contract.p2_scope) == 2
    assert len(contract.h3_scope) == 11
    assert len(contract.p3_scope) == 2
    assert len(contract.h4_scope) == 11
    assert len(contract.p4_scope) == 2
    assert len(contract.h5_scope) == 11
    assert len(contract.p5_scope) == 2
    assert len(contract.h6_scope) == 11
    assert len(contract.p6_scope) == 2
    assert len(contract.r_scope) == 8
    assert len(contract.anchor_inputs) == 10
    assert len(contract.dvc_pointers) == 8
    ordered_pointer_paths = [item.path for item in certification.DVC_POINTERS]
    assert list(contract.post_restore_status_pointer_paths) == ordered_pointer_paths
    assert (
        list(contract.post_verification_status_pointer_paths)
        == ordered_pointer_paths
    )
    assert contract.partial_clone_global_status_authorized is False
    assert certification.expected_dvc_status_policy(contract) == {
        "scope": "exact_eight_published_pointer_paths",
        "target_count": 8,
        "ordered_targets": ordered_pointer_paths,
        "post_restore_status_pointer_paths": ordered_pointer_paths,
        "post_verification_status_pointer_paths": ordered_pointer_paths,
        "global_status_authorized": False,
        "final_status_empty_result_required": True,
    }
    assert contract.output_paths == certification.OUTPUT_PATHS
    assert dict(contract.expected_runtime_versions) == {
        "python": "Python 3.14.7",
        "dvc": "3.67.1",
        "ty": "ty 0.0.37",
        "git": "git version 2.55.0",
        "poetry": "Poetry (version 2.4.1)",
        "bubblewrap": "bubblewrap 0.11.2",
        "docker_client": "29.7.2",
        "docker_server": "29.7.2",
    }
    assert contract.expected_runtime_versions == certification.EXPECTED_RUNTIME_VERSIONS
    assert contract.raw["isolation"]["network_policy"] == {
        "git_live_remote_ref_validation": "allowed",
        "git_clone_from_origin": "allowed",
        "eight_directed_dvc_pulls": "allowed",
        "loopback_postgresql": "allowed",
        "scientific_or_general_network": "forbidden",
    }
    assert contract.concurrency_lock == "flock_retained_git_directory"
    assert (
        contract.legacy_guard_path_must_be_absent
        == certification.GUARD_PATH.as_posix()
    )
    assert contract.guard_path == contract.legacy_guard_path_must_be_absent
    assert contract.external_namespace_mutation_is_stop_condition is True
    assert contract.noncooperating_same_uid_namespace_mutation == "out_of_scope"
    assert contract.identity_revalidated_before_and_after_name_cleanup is True
    assert contract.conditional_unlink_by_inode_claimed is False
    assert contract.no_clobber is True
    assert contract.cleanup_before_precommit is True
    assert contract.raw["isolation"]["post_clone_directory_nlink_delta"] == 1
    assert (
        contract.raw["isolation"]["post_clone_nlink_delta_stage"]
        == "after_git_clone"
    )
    assert contract.raw["isolation"][
        "clone_registered_after_exact_transition_check_before_subsequent_validation"
    ] is True
    assert contract.raw["isolation"][
        "primary_error_preserved_when_safe_cleanup_passes"
    ] is True
    assert contract.raw["isolation"]["superseded_p1_retry_authorized"] is False
    assert contract.raw["isolation"]["superseded_p2_retry_authorized"] is False
    assert contract.raw["isolation"]["superseded_p3_retry_authorized"] is False
    assert contract.raw["isolation"]["superseded_p4_retry_authorized"] is False
    assert contract.raw["isolation"]["superseded_p5_retry_authorized"] is False
    assert contract.raw["isolation"]["superseded_p6_retry_authorized"] is False
    assert contract.raw["isolation"]["postgres_portable_path_policy"] == (
        certification.expected_postgres_portable_path_policy()
    )
    assert dict(contract.postgres_portable_path_policy) == (
        certification.expected_postgres_portable_path_policy()
    )
    assert contract.raw["isolation"]["credential_path_rebased_to_retained_fd"] is True
    site_cache = contract.raw["isolation"]
    assert site_cache["owned_site_cache_count"] == 2
    assert site_cache["owned_site_cache_roles"] == [
        "runtime_version",
        "restore_status",
    ]
    assert site_cache["owned_site_cache_filesystem_mode"] == "0700"
    assert site_cache["owned_site_caches_separated"] is True
    assert site_cache["owned_site_cache_paths_serialized"] is False
    assert site_cache["version_seal_before_private_config_or_pull"] is True
    assert site_cache[
        "single_dvc_runtime_retained_through_final_status_and_version_probe"
    ] is True
    assert site_cache["dvc_runtime_cross_call_identity_revalidated"] is True
    assert site_cache[
        "operational_cache_fields_normalized_before_section_set_equivalence"
    ] is True
    assert site_cache["only_owned_cache_dir_and_type_may_differ"] is True
    assert site_cache["credential_fds_passed_to_dvc_config_commands"] is False
    assert site_cache["first_credential_fd_subprocess_exposure"] == (
        "first_directed_dvc_pull"
    )
    assert site_cache["used_by_all_isolated_dvc_commands"] is True
    assert site_cache["copied_core_site_cache_dir_used"] is False
    assert site_cache[
        "main_dvc_site_cache_metadata_inode_inventory_unchanged"
    ] is True
    assert site_cache["main_dvc_command_run"] is False
    assert "main_dvc_site_cache_must_remain_unchanged" not in site_cache
    assert certification.expected_environment_dvc_record() == {
        "restored_pointer_count": 8,
        "cache_initially_empty": True,
        "one_pointer_per_pull": True,
        "main_dvc_command_run": False,
        "main_dvc_status_command_run": False,
        "main_dvc_static_reconstruction_from_git_and_published_pointers": True,
        "owned_site_cache_count": 2,
        "owned_site_cache_roles": ["runtime_version", "restore_status"],
        "owned_site_cache_filesystem_mode": "0700",
        "owned_site_caches_separated": True,
        "owned_site_cache_paths_serialized": False,
        "version_seal_before_private_config_or_pull": True,
        "single_dvc_runtime_retained_through_final_status_and_version_probe": True,
        "dvc_runtime_cross_call_identity_revalidated": True,
        "operational_cache_fields_normalized_before_section_set_equivalence": True,
        "only_owned_cache_dir_and_type_may_differ": True,
        "credential_fds_passed_to_dvc_config_commands": False,
        "first_credential_fd_subprocess_exposure": "first_directed_dvc_pull",
        "post_restore_status_pointer_paths": ordered_pointer_paths,
        "post_verification_status_pointer_paths": ordered_pointer_paths,
        "partial_clone_global_status_authorized": False,
        "main_dvc_site_cache_metadata_inode_inventory_unchanged": True,
        "payloads_opened_by_python": False,
        "payloads_decoded": False,
        "dvc_add_or_push": False,
        "main_worktree_written": False,
    }
    assert certification.expected_manifest_clone_dvc_site_caches_record() == {
        "owned_site_cache_count": 2,
        "owned_site_cache_roles": ["runtime_version", "restore_status"],
        "owned_site_cache_filesystem_mode": "0700",
        "owned_site_caches_separated": True,
        "used_by_all_isolated_dvc_commands": True,
        "copied_core_site_cache_dir_used": False,
        "owned_site_cache_paths_serialized": False,
        "version_seal_before_private_config_or_pull": True,
        "single_dvc_runtime_retained_through_final_status_and_version_probe": True,
        "dvc_runtime_cross_call_identity_revalidated": True,
        "operational_cache_fields_normalized_before_section_set_equivalence": True,
        "only_owned_cache_dir_and_type_may_differ": True,
        "credential_fds_passed_to_dvc_config_commands": False,
        "first_credential_fd_subprocess_exposure": "first_directed_dvc_pull",
        "post_restore_status_pointer_paths": ordered_pointer_paths,
        "post_verification_status_pointer_paths": ordered_pointer_paths,
        "partial_clone_global_status_authorized": False,
    }
    assert contract.raw["topology"]["main_worktree_dvc_status_executed"] is False
    assert contract.raw["topology"][
        "main_worktree_dvc_static_boundary_verified"
    ] is True
    assert contract.raw["dvc_restoration"][
        "main_worktree_dvc_state_source"
    ] == "git_and_versioned_dvc_pointers"
    assert contract.raw["isolation"]["real_dvc_execution_scope"] == (
        "isolated_r_cert_clone_only"
    )
    assert contract.raw["isolation"][
        "failed_dvc_partial_tree_not_adopted_for_cleanup"
    ] is True
    assert contract.raw["isolation"]["nonexact_cleanup_preserves_namespace"] is True
    assert contract.failure_diagnostics == certification.FAILURE_DIAGNOSTICS_POLICY
    assert "guard_path" not in contract.raw["isolation"]
    assert "rollback_owned_inodes_only" not in contract.raw["isolation"]
    assert contract.test_suite.status == certification.LOCKED_SUITE_STATUS
    assert contract.test_suite.selector_count == 39
    assert contract.test_suite.collected_test_count == 944
    assert contract.test_suite.nodeids_sha256 == (
        "8422082eca90068bf6d6fff4f1e4d9b9964535e12c8fd6b0844658bbdf683349"
    )
    assert (
        contract.test_suite.allowed_skip_count
        == certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT
    )


def test_pending_suite_is_an_explicit_fail_closed_placeholder() -> None:
    payload = _pending_payload()

    with pytest.raises(
        certification.FinalCertificationContractError,
        match="pending integration",
    ):
        certification.validate_contract_payload(
            payload,
            root=ROOT,
            verify_inputs=False,
        )

    contract = certification.validate_contract_payload(
        payload,
        root=ROOT,
        verify_inputs=False,
        allow_pending_suite=True,
    )
    assert contract.test_suite.status == "pending_integration"
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="fully locked",
    ):
        certification.test_suite_record(contract)


def test_locked_suite_identity_has_exact_nonduplicating_selectors() -> None:
    contract = certification.validate_contract_payload(
        _locked_payload(),
        root=ROOT,
        verify_inputs=False,
    )
    state_bound_node = (
        "tests/test_build_closure_synthesis.py::"
        "test_check_only_before_p_syn_is_non_writing"
    )

    assert len(contract.test_suite.positive_test_paths) == 33
    assert len(contract.test_suite.exact_skipped_nodes) == 7
    assert len(contract.test_suite.supplemental_skipped_nodes) == 6
    assert len(contract.suite_selectors) == 39
    assert len(set(contract.suite_selectors)) == 39
    assert state_bound_node in contract.test_suite.exact_skipped_nodes
    assert "tests/test_build_closure_synthesis.py" in contract.suite_selectors
    assert state_bound_node not in contract.suite_selectors
    assert contract.test_suite.command_template.count("-p") == 2
    assert contract.test_suite.static_commands == (
        (".venv/bin/ty", "check"),
        ("poetry", "check", "--lock"),
    )
    record = certification.test_suite_record(contract)
    assert record["suite_lock"] == {
        "status": certification.LOCKED_SUITE_STATUS,
        "selector_count": certification.LOCKED_SUITE_SELECTOR_COUNT,
        "collected_test_count": certification.LOCKED_SUITE_COLLECTED_TEST_COUNT,
        "nodeids_sha256": certification.LOCKED_SUITE_NODEIDS_SHA256,
        "allowed_skip_count": certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT,
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(contract_version="closure_v2"),
        lambda value: value["authorities"].update(final_tag="wrong"),
        lambda value: value["authorities"].update(p2_cert_commit="0" * 40),
        lambda value: value["topology"].update(
            single_parent_commits_required=False
        ),
        lambda value: value["publication_scopes"]["H-CERT4"].update(
            additions=8
        ),
        lambda value: value["publication_scopes"]["P-CERT2"].update(
            additions=1
        ),
        lambda value: value["anchor_inputs"].reverse(),
        lambda value: value["dvc_restoration"].update(
            tracked_config_contains_remote=True
        ),
        lambda value: value["test_certification"]["command_template"].pop(),
        lambda value: value["openapi_certification"].update(
            expected_operation_count=82
        ),
        lambda value: value["isolation"]["forbidden_read_prefixes"].pop(),
        lambda value: value["isolation"]["expected_runtime_versions"].update(
            python="Python 3.14.8"
        ),
        lambda value: value["isolation"]["expected_runtime_versions"].update(
            foreign="1.0"
        ),
        lambda value: value["isolation"]["expected_runtime_versions"].pop(
            "docker_server"
        ),
        lambda value: value["isolation"].update(concurrency_lock="path_guard"),
        lambda value: value["isolation"].update(
            legacy_guard_path_must_be_absent="tmp/foreign.guard"
        ),
        lambda value: value["isolation"].update(
            external_namespace_mutation_is_stop_condition=False
        ),
        lambda value: value["isolation"].update(
            conditional_unlink_by_inode_claimed=True
        ),
        lambda value: value["isolation"].update(
            noncooperating_same_uid_namespace_mutation="claimed_safe"
        ),
        lambda value: value["isolation"].update(
            identity_revalidated_before_and_after_name_cleanup=False
        ),
        lambda value: value["isolation"].update(no_clobber=False),
        lambda value: value["isolation"].update(cleanup_before_precommit=False),
        lambda value: value["failure_diagnostics"].update(
            raw_stderr_preservation_authorized=True
        ),
        lambda value: value["outputs"]["ordered_paths"].reverse(),
        lambda value: value["stop_rules"].pop(),
    ],
)
def test_every_contract_boundary_fails_closed(
    mutate: Callable[[dict[str, Any]], Any],
) -> None:
    payload = _locked_payload()
    mutate(payload)
    with pytest.raises(certification.FinalCertificationContractError):
        certification.validate_contract_payload(
            payload,
            root=ROOT,
            verify_inputs=False,
        )


def test_suite_lock_rejects_count_digest_and_pending_value_drifts() -> None:
    wrong_selector_count = _locked_payload()
    wrong_selector_count["test_certification"]["suite_lock"][
        "selector_count"
    ] = 40
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="suite identity",
    ):
        certification.validate_contract_payload(
            wrong_selector_count,
            root=ROOT,
            verify_inputs=False,
        )

    wrong_digest = _locked_payload()
    wrong_digest["test_certification"]["suite_lock"]["nodeids_sha256"] = "a" * 64
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="suite identity",
    ):
        certification.validate_contract_payload(
            wrong_digest,
            root=ROOT,
            verify_inputs=False,
        )

    wrong_collected_count = _locked_payload()
    wrong_collected_count["test_certification"]["suite_lock"][
        "collected_test_count"
    ] = certification.LOCKED_SUITE_COLLECTED_TEST_COUNT - 1
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="collected count",
    ):
        certification.validate_contract_payload(
            wrong_collected_count,
            root=ROOT,
            verify_inputs=False,
        )

    wrong_allowed_skip_count = _locked_payload()
    wrong_allowed_skip_count["test_certification"]["suite_lock"][
        "allowed_skip_count"
    ] = certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT - 1
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="skip count",
    ):
        certification.validate_contract_payload(
            wrong_allowed_skip_count,
            root=ROOT,
            verify_inputs=False,
        )

    pending_with_count = _pending_payload()
    pending_with_count["test_certification"]["suite_lock"][
        "selector_count"
    ] = certification.LOCKED_SUITE_SELECTOR_COUNT
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="must use null",
    ):
        certification.validate_contract_payload(
            pending_with_count,
            root=ROOT,
            verify_inputs=False,
            allow_pending_suite=True,
        )


def test_public_anchors_and_dvc_pointers_are_editorial_git_bound() -> None:
    contract = certification.load_contract(
        root=ROOT,
        verify_inputs=False,
        allow_pending_suite=True,
    )
    anchors = certification.collect_anchor_input_records(contract, root=ROOT)
    pointers = certification.collect_dvc_pointer_records(contract, root=ROOT)

    assert [row["path"] for row in anchors] == list(contract.anchor_input_paths)
    assert {row["repository_commit"] for row in anchors} == {
        certification.EDITORIAL_COMMIT
    }
    assert [row["path"] for row in pointers] == list(contract.dvc_pointer_paths)
    assert [row["output_path"] for row in pointers] == list(
        contract.dvc_output_paths
    )
    assert all(row["parquet_payload_opened"] is False for row in pointers)
    assert all(
        row["repository_commit"] == certification.EDITORIAL_COMMIT
        for row in pointers
    )
    boundary = certification.main_dvc_static_boundary_record(
        contract,
        anchor_records=anchors,
        pointer_records=pointers,
    )
    assert boundary == {
        "status_executed": False,
        "state_source": "git_and_versioned_dvc_pointers",
        "static_boundary_verified": True,
        "tracked_config_path": ".dvc/config",
        "tracked_config_git_blob_oid": anchors[0]["git_blob_oid"],
        "versioned_pointer_count": 8,
        "versioned_pointer_records_digest": certification.digest_records(pointers),
        "real_dvc_execution_scope": "isolated_r_cert_clone_only",
    }
    drifted = [dict(record) for record in pointers]
    drifted[0]["repository_commit"] = "0" * 40
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="static boundary pointer reconstruction drifted",
    ):
        certification.main_dvc_static_boundary_record(
            contract,
            anchor_records=anchors,
            pointer_records=drifted,
        )


def test_dvc_pointer_parser_accepts_only_the_sealed_single_file_dialect() -> None:
    pointer = certification.DVC_POINTERS[0]
    payload = (
        "outs:\n"
        f"- md5: {pointer.md5}\n"
        f"  size: {pointer.size}\n"
        "  hash: md5\n"
        "  path: input_history.parquet\n"
    ).encode("utf-8")

    assert certification.parse_dvc_pointer_bytes(payload, pointer.path) == {
        "md5": pointer.md5,
        "size": pointer.size,
        "output_name": "input_history.parquet",
        "output_path": pointer.output_path,
    }
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="dialect drifted",
    ):
        certification.parse_dvc_pointer_bytes(
            payload.replace(b"  hash: md5\n", b""),
            pointer.path,
        )
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="output name drifted",
    ):
        certification.parse_dvc_pointer_bytes(
            payload.replace(b"input_history.parquet", b"other.parquet"),
            pointer.path,
        )


def test_schema_seals_scopes_suite_dvc_and_manifest_last() -> None:
    schema = json.loads(SCHEMA_PATH.read_bytes())
    properties = schema["properties"]
    scopes = properties["publication_scopes"]["properties"]
    suite = properties["test_certification"]["properties"]
    pending, locked = suite["suite_lock"]["oneOf"]

    assert schema["$schema"].endswith("2020-12/schema")
    assert scopes["H-CERT1"]["allOf"][1]["properties"]["additions"][
        "const"
    ] == 9
    assert scopes["H-CERT1"]["allOf"][1]["properties"]["modifications"][
        "const"
    ] == 2
    assert scopes["H-CERT2"]["allOf"][1]["properties"]["additions"]["const"] == 0
    assert scopes["H-CERT2"]["allOf"][1]["properties"]["modifications"]["const"] == 11
    assert scopes["P-CERT1"]["allOf"][1]["properties"]["additions"]["const"] == 2
    assert scopes["P-CERT2"]["allOf"][1]["properties"]["additions"][
        "const"
    ] == 2
    assert scopes["H-CERT4"]["allOf"][1]["properties"]["modifications"][
        "const"
    ] == 11
    assert scopes["P-CERT4"]["allOf"][1]["properties"]["additions"][
        "const"
    ] == 2
    assert scopes["H-CERT5"]["allOf"][1]["properties"]["modifications"][
        "const"
    ] == 11
    assert scopes["P-CERT5"]["allOf"][1]["properties"]["additions"][
        "const"
    ] == 2
    assert scopes["H-CERT6"]["allOf"][1]["properties"]["modifications"][
        "const"
    ] == 11
    assert scopes["P-CERT6"]["allOf"][1]["properties"]["additions"][
        "const"
    ] == 2
    assert scopes["H-CERT7"]["allOf"][1]["properties"]["modifications"][
        "const"
    ] == 11
    assert scopes["P-CERT7"]["allOf"][1]["properties"]["additions"][
        "const"
    ] == 2
    assert scopes["R-CERT7"]["allOf"][1]["properties"]["additions"][
        "const"
    ] == 8
    assert pending["properties"]["selector_count"] == {"type": "null"}
    assert locked["properties"]["status"] == {
        "const": certification.LOCKED_SUITE_STATUS
    }
    assert locked["properties"]["selector_count"] == {
        "const": certification.LOCKED_SUITE_SELECTOR_COUNT
    }
    assert locked["properties"]["collected_test_count"] == {
        "const": certification.LOCKED_SUITE_COLLECTED_TEST_COUNT
    }
    assert locked["properties"]["nodeids_sha256"] == {
        "const": certification.LOCKED_SUITE_NODEIDS_SHA256
    }
    assert locked["properties"]["allowed_skip_count"] == {
        "const": certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT
    }
    assert suite["static_commands"]["const"].count(
        ["poetry", "check", "--lock"]
    ) == 1
    dvc = properties["dvc_restoration"]["properties"]
    assert dvc["tracked_config_contains_remote"] == {"const": False}
    assert dvc["ignored_local_remote_configuration_required"] == {
        "const": True
    }
    assert dvc["ignored_local_remote_configuration_serialized"] == {
        "const": False
    }
    assert dvc["credential_path_values_serialized"] == {"const": False}
    assert dvc["owned_site_cache_count"] == {"const": 2}
    assert dvc["owned_site_cache_roles"] == {
        "const": ["runtime_version", "restore_status"]
    }
    assert dvc["owned_site_cache_filesystem_mode"] == {"const": "0700"}
    assert dvc["owned_site_caches_separated"] == {"const": True}
    assert dvc["owned_site_cache_paths_serialized"] == {"const": False}
    assert dvc["version_seal_before_private_config_or_pull"] == {"const": True}
    assert dvc[
        "single_dvc_runtime_retained_through_final_status_and_version_probe"
    ] == {"const": True}
    assert dvc["dvc_runtime_cross_call_identity_revalidated"] == {"const": True}
    assert dvc[
        "operational_cache_fields_normalized_before_section_set_equivalence"
    ] == {"const": True}
    assert dvc["only_owned_cache_dir_and_type_may_differ"] == {"const": True}
    assert dvc["credential_fds_passed_to_dvc_config_commands"] == {
        "const": False
    }
    assert dvc["first_credential_fd_subprocess_exposure"] == {
        "const": "first_directed_dvc_pull"
    }
    ordered_pointer_paths = [item.path for item in certification.DVC_POINTERS]
    assert dvc["post_restore_status_pointer_paths"] == {
        "const": ordered_pointer_paths
    }
    assert dvc["post_verification_status_pointer_paths"] == {
        "const": ordered_pointer_paths
    }
    assert dvc["partial_clone_global_status_authorized"] == {"const": False}
    assert dvc["used_by_all_isolated_dvc_commands"] == {"const": True}
    assert dvc["copied_core_site_cache_dir_used"] == {"const": False}
    assert dvc[
        "main_dvc_site_cache_metadata_inode_inventory_unchanged"
    ] == {"const": True}
    assert dvc["main_dvc_command_run"] == {"const": False}
    assert "owned_site_cache_path_serialized" not in dvc
    assert dvc["main_worktree_dvc_status_executed"] == {"const": False}
    assert dvc["main_worktree_dvc_static_boundary_verified"] == {"const": True}
    assert dvc["main_worktree_dvc_state_source"] == {
        "const": "git_and_versioned_dvc_pointers"
    }
    assert dvc["real_dvc_execution_scope"] == {
        "const": "isolated_r_cert_clone_only"
    }
    assert properties["outputs"]["properties"]["manifest_written_last"] == {
        "const": True
    }
    isolation = properties["isolation"]
    boundary = isolation["properties"]
    assert set(isolation["required"]) == set(boundary)
    runtime_versions = boundary["expected_runtime_versions"]
    assert runtime_versions["additionalProperties"] is False
    assert runtime_versions["required"] == list(
        certification.EXPECTED_RUNTIME_VERSIONS
    )
    assert runtime_versions["properties"] == {
        key: {"const": value}
        for key, value in certification.EXPECTED_RUNTIME_VERSIONS.items()
    }
    network_policy = boundary["network_policy"]
    assert network_policy["additionalProperties"] is False
    assert network_policy["required"] == [
        "git_live_remote_ref_validation",
        "git_clone_from_origin",
        "eight_directed_dvc_pulls",
        "loopback_postgresql",
        "scientific_or_general_network",
    ]
    assert network_policy["properties"] == {
        "git_live_remote_ref_validation": {"const": "allowed"},
        "git_clone_from_origin": {"const": "allowed"},
        "eight_directed_dvc_pulls": {"const": "allowed"},
        "loopback_postgresql": {"const": "allowed"},
        "scientific_or_general_network": {"const": "forbidden"},
    }
    assert boundary["concurrency_lock"] == {
        "const": "flock_retained_git_directory"
    }
    assert boundary["legacy_guard_path_must_be_absent"] == {
        "const": certification.GUARD_PATH.as_posix()
    }
    assert boundary["external_namespace_mutation_is_stop_condition"] == {
        "const": True
    }
    assert boundary["noncooperating_same_uid_namespace_mutation"] == {
        "const": "out_of_scope"
    }
    assert boundary["identity_revalidated_before_and_after_name_cleanup"] == {
        "const": True
    }
    assert boundary["conditional_unlink_by_inode_claimed"] == {"const": False}
    assert boundary["post_clone_directory_nlink_delta"] == {"const": 1}
    assert boundary["post_clone_nlink_delta_stage"] == {"const": "after_git_clone"}
    assert boundary[
        "clone_registered_after_exact_transition_check_before_subsequent_validation"
    ] == {
        "const": True
    }
    assert boundary["early_cleanup_inventory_claim_required"] == {"const": True}
    assert boundary["primary_error_preserved_when_safe_cleanup_passes"] == {
        "const": True
    }
    assert boundary["superseded_p1_retry_authorized"] == {"const": False}
    assert boundary["superseded_p2_retry_authorized"] == {"const": False}
    assert boundary["superseded_p4_retry_authorized"] == {"const": False}
    assert boundary["superseded_p5_retry_authorized"] == {"const": False}
    assert boundary["superseded_p6_retry_authorized"] == {"const": False}
    portable = boundary["postgres_portable_path_policy"]
    assert portable["additionalProperties"] is False
    assert portable["properties"] == {
        key: {"const": value}
        for key, value in certification.expected_postgres_portable_path_policy().items()
    }
    assert boundary["post_restore_status_pointer_paths"] == {
        "const": ordered_pointer_paths
    }
    assert boundary["post_verification_status_pointer_paths"] == {
        "const": ordered_pointer_paths
    }
    assert boundary["partial_clone_global_status_authorized"] == {
        "const": False
    }
    assert boundary["owned_site_cache_count"] == {"const": 2}
    assert boundary["owned_site_cache_roles"] == {
        "const": ["runtime_version", "restore_status"]
    }
    assert boundary["owned_site_cache_filesystem_mode"] == {"const": "0700"}
    assert boundary["owned_site_caches_separated"] == {"const": True}
    assert boundary["owned_site_cache_paths_serialized"] == {"const": False}
    assert boundary["version_seal_before_private_config_or_pull"] == {
        "const": True
    }
    assert boundary[
        "single_dvc_runtime_retained_through_final_status_and_version_probe"
    ] == {"const": True}
    assert boundary["dvc_runtime_cross_call_identity_revalidated"] == {
        "const": True
    }
    assert boundary[
        "operational_cache_fields_normalized_before_section_set_equivalence"
    ] == {"const": True}
    assert boundary["only_owned_cache_dir_and_type_may_differ"] == {
        "const": True
    }
    assert boundary["credential_fds_passed_to_dvc_config_commands"] == {
        "const": False
    }
    assert boundary["first_credential_fd_subprocess_exposure"] == {
        "const": "first_directed_dvc_pull"
    }
    assert boundary["used_by_all_isolated_dvc_commands"] == {"const": True}
    assert boundary["copied_core_site_cache_dir_used"] == {"const": False}
    assert boundary[
        "main_dvc_site_cache_metadata_inode_inventory_unchanged"
    ] == {"const": True}
    assert boundary["main_dvc_command_run"] == {"const": False}
    assert "main_dvc_site_cache_must_remain_unchanged" not in boundary
    assert boundary["main_worktree_dvc_status_executed"] == {"const": False}
    assert boundary["main_worktree_dvc_static_boundary_verified"] == {
        "const": True
    }
    assert boundary["failed_dvc_partial_tree_not_adopted_for_cleanup"] == {
        "const": True
    }
    assert boundary["nonexact_cleanup_preserves_namespace"] == {"const": True}
    assert boundary["no_clobber"] == {"const": True}
    assert boundary["cleanup_before_precommit"] == {"const": True}
    assert "guard_path" not in boundary
    assert "rollback_owned_inodes_only" not in boundary
    diagnostics = properties["failure_diagnostics"]
    assert set(diagnostics["required"]) == set(diagnostics["properties"])
    assert diagnostics["properties"] == {
        key: {"const": value}
        for key, value in certification.FAILURE_DIAGNOSTICS_POLICY.items()
    }


def test_canonical_json_and_digest_helpers_are_deterministic() -> None:
    payload = certification.canonical_json_bytes({"z": 1, "a": [2, 3]})
    assert payload == b'{"a":[2,3],"z":1}\n'
    assert certification.sha256_bytes(payload) == certification.sha256_bytes(
        payload
    )
    assert certification.digest_strings(["b", "a"]) != (
        certification.digest_strings(["a", "b"])
    )
    with pytest.raises(ValueError, match="Out of range float values"):
        certification.canonical_json_bytes({"invalid": float("nan")})


def test_local_dvc_remote_is_metadata_only_and_never_an_authority_input() -> None:
    record = certification.validate_local_dvc_remote_configuration(root=ROOT)

    mode = record.pop("filesystem_mode")
    assert mode in {"0600", "0644"}
    assert record == {
        "present": True,
        "regular_file": True,
        "single_link": True,
        "git_ignored": True,
        "content_opened": False,
        "content_or_path_serialized": False,
    }
    serialized = certification.canonical_json_bytes(record)
    assert b"config.local" not in serialized
    assert b"remote" not in serialized


@pytest.mark.parametrize("unsafe_kind", ["symlink", "hardlink"])
def test_local_dvc_remote_rejects_unsafe_files(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    dvc = tmp_path / ".dvc"
    dvc.mkdir()
    target = tmp_path / "target"
    target.write_text("not inspected\n", encoding="utf-8")
    local = dvc / "config.local"
    if unsafe_kind == "symlink":
        local.symlink_to(target)
    else:
        os.link(target, local)

    with pytest.raises(
        certification.FinalCertificationContractError,
        match="single-link regular file",
    ):
        certification.validate_local_dvc_remote_configuration(root=tmp_path)


def test_contract_reader_rejects_parent_swap_after_fd_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    contract_parent = repository / "configs/closure_v1"
    contract_parent.mkdir(parents=True)
    contract_path = contract_parent / "contract.yaml"
    contract_path.write_bytes(b"contract_version: fixture\n")
    moved_configs = repository / "configs.retained"
    original_read = certification.os.read
    swapped = False

    def swap_parent_then_read(descriptor: int, count: int) -> bytes:
        nonlocal swapped
        if not swapped:
            os.rename(repository / "configs", moved_configs)
            (repository / "configs").symlink_to(
                moved_configs,
                target_is_directory=True,
            )
            swapped = True
        return original_read(descriptor, count)

    monkeypatch.setattr(certification.os, "read", swap_parent_then_read)
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="ancestor binding drifted",
    ):
        certification._read_contract_file(  # noqa: SLF001
            repository,
            "configs/closure_v1/contract.yaml",
        )

    assert swapped is True
    assert (moved_configs / "closure_v1/contract.yaml").read_bytes() == (
        b"contract_version: fixture\n"
    )
    assert (repository / "configs").is_symlink()


def test_contract_reader_rejects_final_name_swap_after_fd_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    contract_path = repository / "contract.yaml"
    contract_path.write_bytes(b"owned contract\n")
    retained = repository / "contract.retained"
    original_stat = certification.os.stat
    named_file_stats = 0
    swapped = False

    def swap_before_final_name_rebind(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: Any,
        **kwargs: Any,
    ) -> os.stat_result:
        nonlocal named_file_stats, swapped
        if path == contract_path.name and kwargs.get("dir_fd") is not None:
            named_file_stats += 1
        if named_file_stats == 3 and not swapped:
            os.rename(contract_path, retained)
            contract_path.write_bytes(b"foreign contract\n")
            swapped = True
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(
        certification.os,
        "stat",
        swap_before_final_name_rebind,
    )
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="name or identity drifted",
    ):
        certification._read_contract_file(  # noqa: SLF001
            repository,
            "contract.yaml",
        )

    assert swapped is True
    assert retained.read_bytes() == b"owned contract\n"
    assert contract_path.read_bytes() == b"foreign contract\n"


def test_publication_json_reader_rejects_ancestor_swap_during_git_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    publication_parent = repository / "configs/closure_v1"
    publication_parent.mkdir(parents=True)
    relative = Path("configs/closure_v1/authority.json")
    payload = certification.canonical_json_bytes({"fixture": True})
    (repository / relative).write_bytes(payload)
    retained_configs = repository / "configs.retained"
    replacement_parent = repository / "configs/closure_v1"
    oid = "a" * 40
    swapped = False

    def fake_run_git(
        _root: Path,
        *args: str,
        text: bool,
    ) -> str | bytes:
        nonlocal swapped
        if args[0] == "ls-tree":
            os.rename(repository / "configs", retained_configs)
            replacement_parent.mkdir(parents=True)
            (repository / relative).write_bytes(b'{"foreign":true}\n')
            swapped = True
            return f"100644 blob {oid}\t{relative.as_posix()}\n"
        assert args[:2] == ("cat-file", "blob")
        assert text is False
        return payload

    monkeypatch.setattr(certification, "_run_git", fake_run_git)
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="ancestor binding drifted",
    ):
        certification._decode_canonical_public_json(  # noqa: SLF001
            repository,
            relative,
            commit="b" * 40,
        )

    assert swapped is True
    assert (retained_configs / "closure_v1/authority.json").read_bytes() == payload
    assert (repository / relative).read_bytes() == b'{"foreign":true}\n'


@pytest.mark.parametrize(
    ("swap_kind", "error_pattern"),
    [
        ("file", "name or identity drifted"),
        ("parent", "ancestor binding drifted"),
    ],
)
def test_local_dvc_remote_rebinds_after_git_ignore_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap_kind: str,
    error_pattern: str,
) -> None:
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    (tmp_path / ".gitignore").write_text(
        ".dvc/config.local\n",
        encoding="utf-8",
    )
    dvc_parent = tmp_path / ".dvc"
    dvc_parent.mkdir()
    local = dvc_parent / "config.local"
    local.write_bytes(b"private remote metadata\n")
    local.chmod(0o600)
    original_run = certification.subprocess.run
    injected = False

    def swap_during_check_ignore(*args: Any, **kwargs: Any) -> Any:
        nonlocal injected
        command = args[0]
        if command[:2] == ["git", "check-ignore"] and not injected:
            if swap_kind == "file":
                os.rename(local, dvc_parent / "config.retained")
                local.write_bytes(b"foreign remote metadata\n")
                local.chmod(0o600)
            else:
                retained_parent = tmp_path / ".dvc.retained"
                foreign_parent = tmp_path / ".dvc.foreign"
                foreign_parent.mkdir()
                (foreign_parent / "config.local").write_bytes(b"foreign\n")
                (foreign_parent / "config.local").chmod(0o600)
                os.rename(dvc_parent, retained_parent)
                dvc_parent.symlink_to(foreign_parent, target_is_directory=True)
            injected = True
        return original_run(*args, **kwargs)

    monkeypatch.setattr(certification.subprocess, "run", swap_during_check_ignore)
    with pytest.raises(
        certification.FinalCertificationContractError,
        match=error_pattern,
    ):
        certification.validate_local_dvc_remote_configuration(root=tmp_path)

    assert injected is True
    if swap_kind == "file":
        assert (dvc_parent / "config.retained").read_bytes() == (
            b"private remote metadata\n"
        )
        assert local.read_bytes() == b"foreign remote metadata\n"
    else:
        assert dvc_parent.is_symlink()
        assert (tmp_path / ".dvc.retained/config.local").read_bytes() == (
            b"private remote metadata\n"
        )


def test_effective_authority_loader_checks_topology_and_exact_companion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = certification.validate_contract_payload(
        _locked_payload(),
        root=ROOT,
        verify_inputs=False,
    )
    p_commit = "f" * 40
    h_commit = "e" * 40
    expected_authority = {
        "authority_version": certification.AUTHORITY_VERSION,
        "fixture": "independently_reconstructed",
    }
    authority_bytes = certification.canonical_json_bytes(expected_authority)
    authority_record = {
        "path": certification.AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": certification.sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": certification.AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": contract.p3_cert_commit,
        "h4_cert_commit": contract.h4_cert_commit,
        "p4_cert_commit": contract.p4_cert_commit,
        "h5_cert_commit": contract.h5_cert_commit,
        "p5_cert_commit": contract.p5_cert_commit,
        "h6_cert_commit": contract.h6_cert_commit,
        "p6_cert_commit": contract.p6_cert_commit,
        "h7_cert_commit": h_commit,
        "p7_cert_commit": None,
        "h_cert_commit": h_commit,
        "p_cert_commit": None,
        "supersedes_p6": True,
        "supersedes_p5": True,
        "supersedes_p4": True,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            certification.AUTHORITY_PATH.as_posix(),
            certification.AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(certification.AUTHORIZATION_POLICY),
    }
    manifest_bytes = certification.canonical_json_bytes(expected_manifest)

    def fake_parents(_root: Path, commit: str) -> tuple[str, ...]:
        return {
            p_commit: (h_commit,),
            h_commit: (contract.p6_cert_commit,),
            contract.editorial_commit: (contract.r_syn_commit,),
        }[commit]

    def fake_scope(_root: Path, commit: str) -> dict[str, str]:
        return (
            certification.expected_h_scope()
            if commit == h_commit
            else certification.expected_p_scope()
        )

    def fake_decode(
        _root: Path,
        relative: Path,
        *,
        commit: str,
    ) -> tuple[dict[str, Any], bytes]:
        assert commit == p_commit
        if relative == certification.AUTHORITY_PATH:
            return expected_authority, authority_bytes
        assert relative == certification.AUTHORITY_MANIFEST_PATH
        return expected_manifest, manifest_bytes

    monkeypatch.setattr(certification, "_one_commit", lambda *_args: p_commit)
    monkeypatch.setattr(certification, "_commit_parents", fake_parents)
    monkeypatch.setattr(certification, "_commit_scope", fake_scope)
    monkeypatch.setattr(
        certification,
        "_require_effective_refs",
        lambda *_args, **_kwargs: {"head": p_commit, "main": p_commit},
    )
    monkeypatch.setattr(
        certification,
        "_expected_effective_authority",
        lambda *_args, **_kwargs: expected_authority,
    )
    monkeypatch.setattr(
        certification,
        "_historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_h6_p6_records",
        lambda *_args, **_kwargs: (
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        ),
    )
    monkeypatch.setattr(certification, "_decode_canonical_public_json", fake_decode)
    monkeypatch.setattr(
        certification.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=b"",
            stderr=b"",
        ),
    )

    result = certification.load_effective_authority(
        contract,
        root=tmp_path,
        verify_remote=False,
        require_clean=False,
    )

    assert result["status"] == "effective"
    assert result["p_cert_commit"] == p_commit
    assert result["h_cert_commit"] == h_commit
    assert result["p7_cert_commit"] == p_commit
    assert result["h7_cert_commit"] == h_commit
    assert result["p6_cert_commit"] == contract.p6_cert_commit
    assert result["h6_cert_commit"] == contract.h6_cert_commit
    assert result["p5_cert_commit"] == contract.p5_cert_commit
    assert result["h5_cert_commit"] == contract.h5_cert_commit
    assert result["p4_cert_commit"] == contract.p4_cert_commit
    assert result["h4_cert_commit"] == contract.h4_cert_commit
    assert result["p3_cert_commit"] == contract.p3_cert_commit
    assert result["h3_cert_commit"] == contract.h3_cert_commit
    assert result["p2_cert_commit"] == contract.p2_cert_commit
    assert result["h2_cert_commit"] == contract.h2_cert_commit
    assert result["p1_cert_commit"] == contract.p1_cert_commit
    assert result["h1_cert_commit"] == contract.h1_cert_commit
    assert result["authority"] == expected_authority
    assert result["manifest"] == expected_manifest
    assert result["dvc_status_policy"] == (
        certification.expected_dvc_status_policy(contract)
    )


def test_historical_p1_reconstruction_rejects_physical_byte_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = certification.validate_contract_payload(
        _locked_payload(),
        root=ROOT,
        verify_inputs=False,
    )
    original = certification._publication_file_record_and_payload  # noqa: SLF001
    authority_reads = 0

    def drifted_physical(
        root: Path,
        *,
        commit: str,
        spec: certification.PublicationPathSpec,
    ) -> tuple[dict[str, Any], bytes]:
        nonlocal authority_reads
        record, payload = original(root, commit=commit, spec=spec)
        if spec.path == certification.H1_AUTHORITY_PATH.as_posix():
            authority_reads += 1
            if authority_reads == 1:
                decoded = json.loads(payload)
                decoded["fixture_physical_drift"] = True
                payload = certification.canonical_json_bytes(decoded)
        return record, payload

    monkeypatch.setattr(
        certification,
        "_publication_file_record_and_payload",
        drifted_physical,
    )
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="P-CERT1 physical/Git bytes drifted",
    ):
        certification._historical_h1_p1_records(contract, root=ROOT)  # noqa: SLF001


def test_effective_authority_reconstruction_binds_exact_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = certification.validate_contract_payload(
        _locked_payload(),
        root=ROOT,
        verify_inputs=False,
    )
    monkeypatch.setattr(
        certification,
        "collect_h_component_records",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        certification,
        "_historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_h6_p6_records",
        lambda *_args, **_kwargs: (
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        ),
    )
    monkeypatch.setattr(
        certification,
        "collect_anchor_input_records",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        certification,
        "collect_dvc_pointer_records",
        lambda *_args, **_kwargs: [],
    )
    static_boundary = {
        "status_executed": False,
        "state_source": "git_and_versioned_dvc_pointers",
        "static_boundary_verified": True,
        "tracked_config_path": ".dvc/config",
        "tracked_config_git_blob_oid": "a" * 40,
        "versioned_pointer_count": 8,
        "versioned_pointer_records_digest": certification.digest_records([]),
        "real_dvc_execution_scope": "isolated_r_cert_clone_only",
    }
    monkeypatch.setattr(
        certification,
        "main_dvc_static_boundary_record",
        lambda *_args, **_kwargs: static_boundary,
    )
    monkeypatch.setattr(
        certification,
        "test_suite_record",
        lambda *_args, **_kwargs: {"suite_lock": "synthetic"},
    )

    authority = certification._expected_effective_authority(  # noqa: SLF001
        contract,
        root=ROOT,
        h_cert_commit="e" * 40,
    )

    assert authority["isolation"] == certification._expected_isolation()  # noqa: SLF001
    assert authority["isolation"]["expected_runtime_versions"] == dict(
        certification.EXPECTED_RUNTIME_VERSIONS
    )
    assert authority["failure_diagnostics"] == dict(
        certification.FAILURE_DIAGNOSTICS_POLICY
    )
    assert authority["p2_failure"] == certification.expected_p2_failure_record()
    assert authority["p3_failure"] == certification.expected_p3_failure_record()
    assert authority["p4_failure"] == certification.expected_p4_failure_record()
    assert authority["p5_failure"] == certification.expected_p5_failure_record()
    assert authority["p6_failure"] == certification.expected_p6_failure_record()
    assert authority["dvc_status_policy"] == (
        certification.expected_dvc_status_policy(contract)
    )
    assert authority["main_dvc_static_boundary"] == static_boundary
    assert authority["h5_component_records"] == []
    assert authority["p5_component_records"] == []
    assert authority["h6_component_records"] == []
    assert authority["p6_component_records"] == []
    assert authority["h7_component_records"] == authority["h_component_records"]
    assert authority["h7_scope"] == authority["h_scope"]
    assert authority["p7_scope"] == authority["p_scope"]
    assert "guard_path" not in authority["isolation"]
    assert "rollback_owned_inodes_only" not in authority["isolation"]


def test_historical_p2_is_byte_exact_and_diagnostics_are_sanitized() -> None:
    contract = certification.validate_contract_payload(
        _locked_payload(),
        root=ROOT,
        verify_inputs=False,
    )
    h1, p1, h2, p2 = certification._historical_h1_p1_h2_p2_records(  # noqa: SLF001
        contract,
        root=ROOT,
    )

    assert [len(h1), len(p1), len(h2), len(p2)] == [11, 2, 11, 2]
    assert [row["path"] for row in p2] == [
        certification.H2_AUTHORITY_PATH.as_posix(),
        certification.H2_AUTHORITY_MANIFEST_PATH.as_posix(),
    ]
    failure = certification.expected_p2_failure_record()
    assert set(failure) == {"status", "active_error", "cleanup", "retry_authorized"}
    assert failure["active_error"]["returncode"] is None
    assert failure["active_error"]["safe_stderr_category"] == (
        "unavailable_not_persisted"
    )
    assert failure["cleanup"] == {
        "status": "failed_closed",
        "namespace_preserved": True,
        "active_error_was_masked": True,
    }
    assert failure["retry_authorized"] is False


def test_historical_p3_is_byte_exact_and_failure_is_sanitized() -> None:
    contract = certification.validate_contract_payload(
        _locked_payload(), root=ROOT, verify_inputs=False
    )
    records = certification._historical_h1_p1_h2_p2_h3_p3_records(  # noqa: SLF001
        contract, root=ROOT
    )
    assert [len(group) for group in records] == [11, 2, 11, 2, 11, 2]
    assert [row["path"] for row in records[-1]] == [
        certification.H3_AUTHORITY_PATH.as_posix(),
        certification.H3_AUTHORITY_MANIFEST_PATH.as_posix(),
    ]
    failure = certification.expected_p3_failure_record()
    assert failure["status"] == "execution_and_cleanup_failed_closed"
    assert failure["active_error"]["returncode"] == 1
    assert failure["active_error"]["safe_stderr_category"] == "nonzero_exit"
    assert set(failure["evidence_counts"].values()) == {0}
    assert failure["cleanup"] == {
        "status": "failed_closed",
        "namespace_preserved": True,
        "active_error_was_masked": False,
    }
    assert failure["archive_is_authority"] is False
    assert failure["retry_authorized"] is False

    complete = (
        certification._historical_h1_p1_h2_p2_h3_p3_h4_p4_records(  # noqa: SLF001
            contract,
            root=ROOT,
        )
    )
    assert [len(group) for group in complete] == [11, 2, 11, 2, 11, 2, 11, 2]
    assert [row["path"] for row in complete[-1]] == [
        certification.H4_AUTHORITY_PATH.as_posix(),
        certification.H4_AUTHORITY_MANIFEST_PATH.as_posix(),
    ]
    p4_failure = certification.expected_p4_failure_record()
    assert set(p4_failure) == {
        "status",
        "attempt",
        "active_error",
        "cleanup",
        "evidence_counts",
        "credential_fd_read_or_egress_evidence_preserved",
        "verifiable_dvc_payload_egress_commands",
        "absolute_network_egress_claimed",
        "archived_under_ignored_tmp",
        "archive_is_authority",
        "retry_authorized",
    }
    assert p4_failure["status"] == "execution_failed_closed_cleanup_succeeded"
    assert p4_failure["attempt"] == "R-CERT4"
    assert p4_failure["active_error"] == {
        "stage": "private_dvc_configuration_after_owned_cache_settings",
        "safe_error": "private DVC configuration section set drifted",
        "failure_kind": "in_process_validation",
        "sanitized_command": [],
        "returncode": None,
        "raw_stdout_preserved": False,
        "raw_stderr_preserved": False,
        "credentials_preserved": False,
        "private_configuration_values_preserved": False,
        "absolute_paths_preserved": False,
    }
    assert p4_failure["cleanup"] == {
        "status": "succeeded_exact",
        "namespace_preserved": False,
        "active_error_was_masked": False,
    }
    counts = p4_failure["evidence_counts"]
    assert set(counts) == {
        "live_remote_and_refs_validated",
        "isolated_git_clones",
        "dvc_version_commands",
        "dvc_local_config_commands",
        "dvc_config_commands_receiving_credential_fd_set",
        "successful_directed_dvc_pulls",
        "directed_dvc_status_checks",
        "dvc_cache_objects",
        "restored_payloads",
        "parquet_payloads_opened_or_decoded",
        "raw_target_or_outcome_reads",
        "public_test_runs",
        "postgresql_fixture_starts",
        "docker_version_commands",
        "docker_container_runs",
        "openapi_generations",
        "synthetic_e2e_runs",
        "r_cert_outputs",
    }
    assert counts["live_remote_and_refs_validated"] is True
    assert counts["isolated_git_clones"] == 1
    assert counts["dvc_version_commands"] == 1
    assert counts["dvc_local_config_commands"] == 2
    assert counts["dvc_config_commands_receiving_credential_fd_set"] == 2
    assert counts["docker_version_commands"] == 2
    assert all(
        counts[key] == 0
        for key in (
            "successful_directed_dvc_pulls",
            "directed_dvc_status_checks",
            "dvc_cache_objects",
            "restored_payloads",
            "parquet_payloads_opened_or_decoded",
            "raw_target_or_outcome_reads",
            "public_test_runs",
            "postgresql_fixture_starts",
            "docker_container_runs",
            "openapi_generations",
            "synthetic_e2e_runs",
            "r_cert_outputs",
        )
    )
    assert p4_failure["credential_fd_read_or_egress_evidence_preserved"] is False
    assert p4_failure["verifiable_dvc_payload_egress_commands"] == 0
    assert p4_failure["absolute_network_egress_claimed"] is False
    assert p4_failure["archived_under_ignored_tmp"] is False
    assert p4_failure["archive_is_authority"] is False
    assert p4_failure["retry_authorized"] is False

    complete_v5 = (
        certification._historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_records(  # noqa: SLF001
            contract,
            root=ROOT,
        )
    )
    assert [len(group) for group in complete_v5] == [
        11,
        2,
        11,
        2,
        11,
        2,
        11,
        2,
        11,
        2,
    ]
    assert [row["path"] for row in complete_v5[-1]] == [
        certification.H5_AUTHORITY_PATH.as_posix(),
        certification.H5_AUTHORITY_MANIFEST_PATH.as_posix(),
    ]
    p5_failure = certification.expected_p5_failure_record()
    assert p5_failure["status"] == "execution_and_cleanup_failed_closed"
    assert p5_failure["attempt"] == "R-CERT5"
    assert p5_failure["active_error"] == {
        "stage": "execution",
        "sanitized_command": [],
        "returncode": None,
        "safe_stderr_category": "unavailable_not_persisted",
        "raw_stdout_preserved": False,
        "raw_stderr_preserved": False,
        "credentials_preserved": False,
        "absolute_paths_preserved": False,
    }
    assert p5_failure["cleanup"] == {
        "status": "failed_closed",
        "namespace_preserved": True,
        "active_error_was_masked": False,
    }
    p5_counts = p5_failure["evidence_counts"]
    assert p5_counts["successful_directed_dvc_pulls"] == 8
    assert p5_counts["dvc_cache_objects"] == 8
    assert p5_counts["restored_checkouts"] == 8
    assert p5_counts["directed_dvc_status_checks_confirmed_minimum"] == 7
    assert p5_counts["directed_dvc_status_checks_confirmed_maximum"] == 8
    assert p5_counts["exact_directed_dvc_status_count_claimed"] is False
    assert all(
        p5_counts[key] == 0
        for key in (
            "parquet_payloads_opened_or_decoded_by_python",
            "raw_target_or_outcome_reads",
            "public_test_runs",
            "postgresql_fixture_starts",
            "docker_container_runs",
            "openapi_generations",
            "synthetic_e2e_runs",
            "r_cert_outputs",
        )
    )
    assert p5_failure["namespace_archived_under_ignored_tmp"] is True
    assert p5_failure["namespace_path_or_run_id_serialized"] is False
    assert p5_failure["archive_is_authority"] is False
    assert p5_failure["retry_authorized"] is False

    complete_v6 = (
        certification._historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_h6_p6_records(  # noqa: SLF001
            contract,
            root=ROOT,
        )
    )
    assert [len(group) for group in complete_v6] == [
        11,
        2,
        11,
        2,
        11,
        2,
        11,
        2,
        11,
        2,
        11,
        2,
    ]
    assert complete_v6[-1] == [
        {
            "path": certification.H6_AUTHORITY_PATH.as_posix(),
            "bytes": certification.H6_AUTHORITY_BYTES,
            "sha256": certification.H6_AUTHORITY_SHA256,
            "git_blob_oid": complete_v6[-1][0]["git_blob_oid"],
            "git_mode": "100644",
        },
        {
            "path": certification.H6_AUTHORITY_MANIFEST_PATH.as_posix(),
            "bytes": certification.H6_AUTHORITY_MANIFEST_BYTES,
            "sha256": certification.H6_AUTHORITY_MANIFEST_SHA256,
            "git_blob_oid": complete_v6[-1][1]["git_blob_oid"],
            "git_mode": "100644",
        },
    ]
    p6_failure = certification.expected_p6_failure_record()
    assert p6_failure["status"] == "execution_failed_closed_cleanup_succeeded"
    assert p6_failure["attempt"] == "R-CERT6"
    assert p6_failure["active_error"] == {
        "stage": "postgres_start_portable_command_serialization",
        "safe_error": "absolute command paths may not be serialized",
        "failure_kind": "in_process_portable_command_serialization",
        "sanitized_command": [],
        "returncode": None,
        "safe_stderr_category": "unavailable_not_persisted",
        "raw_stdout_preserved": False,
        "raw_stderr_preserved": False,
        "credentials_preserved": False,
        "absolute_paths_preserved": False,
    }
    assert p6_failure["cleanup"] == {
        "status": "succeeded_exact",
        "namespace_preserved": False,
        "active_error_was_masked": False,
    }
    p6_counts = p6_failure["evidence_counts"]
    assert p6_counts["successful_directed_dvc_pulls"] == 8
    assert p6_counts["dvc_cache_objects"] == 8
    assert p6_counts["restored_checkouts"] == 8
    assert p6_counts["directed_dvc_unit_status_checks"] == 8
    assert p6_counts["post_restore_exact_eight_status_checks"] == 1
    assert all(
        p6_counts[key] == 0
        for key in (
            "post_verification_exact_eight_status_checks",
            "global_dvc_status_commands",
            "parquet_payloads_opened_or_decoded_by_python",
            "raw_target_or_outcome_reads",
            "postgresql_fixture_starts",
            "docker_container_runs",
            "public_test_runs",
            "openapi_generations",
            "synthetic_e2e_runs",
            "r_cert_payload_builds",
            "r_cert_outputs",
        )
    )
    assert p6_failure["archived_under_ignored_tmp"] is False
    assert p6_failure["archive_is_authority"] is False
    assert p6_failure["retry_authorized"] is False
