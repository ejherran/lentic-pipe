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


def test_real_locked_contract_loads_by_default_without_opening_payloads() -> None:
    contract = certification.load_contract(root=ROOT, verify_inputs=True)

    assert contract.closure_source_commit == certification.CLOSURE_SOURCE_COMMIT
    assert contract.r_syn_commit == certification.R_SYN_COMMIT
    assert contract.editorial_commit == certification.EDITORIAL_COMMIT
    assert contract.final_tag == "thesis-closure-v1"
    assert len(contract.h_scope) == 11
    assert len(contract.p_scope) == 2
    assert len(contract.r_scope) == 8
    assert len(contract.anchor_inputs) == 10
    assert len(contract.dvc_pointers) == 8
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
    assert "guard_path" not in contract.raw["isolation"]
    assert "rollback_owned_inodes_only" not in contract.raw["isolation"]
    assert contract.test_suite.status == certification.LOCKED_SUITE_STATUS
    assert (
        contract.test_suite.selector_count
        == certification.LOCKED_SUITE_SELECTOR_COUNT
    )
    assert (
        contract.test_suite.collected_test_count
        == certification.LOCKED_SUITE_COLLECTED_TEST_COUNT
    )
    assert (
        contract.test_suite.nodeids_sha256
        == certification.LOCKED_SUITE_NODEIDS_SHA256
    )
    assert (
        certification.LOCKED_SUITE_NODEIDS_SHA256
        == "583e39e0f1093c51be2421f88df250b2fc84ecd88e52087134a80cc91b8ec5a2"
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
        lambda value: value["topology"].update(
            single_parent_commits_required=False
        ),
        lambda value: value["publication_scopes"]["H-CERT"].update(
            additions=8
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
    assert scopes["H-CERT"]["allOf"][1]["properties"]["additions"][
        "const"
    ] == 9
    assert scopes["H-CERT"]["allOf"][1]["properties"]["modifications"][
        "const"
    ] == 2
    assert scopes["P-CERT"]["allOf"][1]["properties"]["additions"][
        "const"
    ] == 2
    assert scopes["R-CERT"]["allOf"][1]["properties"]["additions"][
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
    assert boundary["no_clobber"] == {"const": True}
    assert boundary["cleanup_before_precommit"] == {"const": True}
    assert "guard_path" not in boundary
    assert "rollback_owned_inodes_only" not in boundary


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
        "h_cert_commit": h_commit,
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
            h_commit: (contract.editorial_commit,),
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
    assert result["authority"] == expected_authority
    assert result["manifest"] == expected_manifest


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
        "collect_anchor_input_records",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        certification,
        "collect_dvc_pointer_records",
        lambda *_args, **_kwargs: [],
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
    assert "guard_path" not in authority["isolation"]
    assert "rollback_owned_inodes_only" not in authority["isolation"]
