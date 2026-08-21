from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import stat
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, cast

import pytest

from src.reporting import build_phase4_final_certification as builder
from src.reporting import phase4_final_certification_contract as contract_module


ROOT = Path(__file__).resolve().parents[1]
P_COMMIT = "a" * 40
H_COMMIT = "b" * 40


def _write_fake_dvc(root: Path) -> Path:
    executable = root / ".venv/bin/dvc"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    launcher = executable.parent / "python"
    if not launcher.exists():
        launcher.symlink_to(Path(cast(str, getattr(sys, "_base_executable", sys.executable))))
    return executable


def _locked_contract(
    *,
    nodes: tuple[str, ...] = (
        "tests/test_alpha.py::test_pass",
        "tests/test_beta.py::test_skip",
    ),
    skipped: tuple[str, ...] = ("tests/test_beta.py::test_skip",),
) -> contract_module.FinalCertificationContract:
    contract = contract_module.load_contract(root=ROOT, allow_pending_suite=True)
    suite = replace(
        contract.test_suite,
        positive_test_paths=tuple(node.split("::", 1)[0] for node in nodes),
        exact_skipped_nodes=skipped,
        status="locked",
        selector_count=len(nodes),
        collected_test_count=len(nodes),
        nodeids_sha256=contract_module.digest_strings(sorted(nodes)),
        allowed_skip_count=len(skipped),
    )
    return replace(contract, test_suite=suite)


def _junit(
    *,
    reason: str,
    duplicate_skip: bool = False,
    include_time: bool = True,
) -> bytes:
    time_attribute = ' time="0.321" timestamp="2026-01-01" hostname="host"' if include_time else ""
    skipped = (
        f'<testcase classname="tests.test_beta" name="test_skip"{time_attribute}>'
        f'<skipped type="pytest.skip" message="{reason}" /></testcase>'
    )
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        f'<testsuites{time_attribute}><testsuite tests="{3 if duplicate_skip else 2}"{time_attribute}>'
        f'<testcase classname="tests.test_alpha" name="test_pass"{time_attribute} />'
        f"{skipped}{skipped if duplicate_skip else ''}"
        "</testsuite></testsuites>\n"
    ).encode()


def _authority() -> dict[str, Any]:
    return {
        "status": "effective",
        "gate": "P-CERT",
        "p_cert_commit": P_COMMIT,
        "h_cert_commit": H_COMMIT,
        "p4_cert_commit": P_COMMIT,
        "h4_cert_commit": H_COMMIT,
        "p3_cert_commit": contract_module.P3_CERT_COMMIT,
        "h3_cert_commit": contract_module.H3_CERT_COMMIT,
        "p2_cert_commit": contract_module.P2_CERT_COMMIT,
        "h2_cert_commit": contract_module.H2_CERT_COMMIT,
        "p1_cert_commit": contract_module.P1_CERT_COMMIT,
        "h1_cert_commit": contract_module.H1_CERT_COMMIT,
        "repository": {"HEAD": P_COMMIT},
        "authority": {"authority_version": "synthetic"},
        "authority_bytes": 123,
        "authority_sha256": "c" * 64,
        "manifest": {"manifest_version": "synthetic"},
        "manifest_bytes": 456,
        "manifest_sha256": "d" * 64,
    }


def _records(prefix: str, count: int) -> list[dict[str, Any]]:
    return [
        {
            "path": f"{prefix}/{index}",
            "bytes": index + 1,
            "sha256": hashlib.sha256(str(index).encode()).hexdigest(),
        }
        for index in range(count)
    ]


def _anchor_records(
    contract: contract_module.FinalCertificationContract,
) -> list[dict[str, Any]]:
    return [
        {
            "path": spec.path,
            "bytes": index + 1,
            "sha256": hashlib.sha256(spec.path.encode()).hexdigest(),
        }
        for index, spec in enumerate(contract.anchor_inputs)
    ]


def _pointer_records(
    contract: contract_module.FinalCertificationContract,
) -> list[dict[str, Any]]:
    return [
        {
            "path": spec.path,
            "role": spec.role,
            "output_path": spec.output_path,
            "payload_md5": spec.md5,
            "payload_bytes": spec.size,
            "bytes": index + 1,
            "sha256": hashlib.sha256(spec.path.encode()).hexdigest(),
        }
        for index, spec in enumerate(contract.dvc_pointers)
    ]


def _static_boundary_records(
    contract: contract_module.FinalCertificationContract,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    anchors = _anchor_records(contract)
    for record in anchors:
        record["repository_commit"] = contract.editorial_commit
    anchors[0]["git_blob_oid"] = "e" * 40
    pointers = _pointer_records(contract)
    for record in pointers:
        record["repository_commit"] = contract.editorial_commit
        record["parquet_payload_opened"] = False
    return anchors, pointers


def _validate_payloads(
    *,
    contract: contract_module.FinalCertificationContract,
    artifacts: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    execution_commit: str = P_COMMIT,
) -> None:
    """Run the production validator with synthetic effective P inputs."""

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            builder,
            "_authority_loader",
            lambda *args, **kwargs: _authority(),
        )
        monkeypatch.setattr(
            builder,
            "collect_anchor_input_records",
            lambda *args, **kwargs: _anchor_records(contract),
        )
        monkeypatch.setattr(
            builder,
            "collect_dvc_pointer_records",
            lambda *args, **kwargs: _pointer_records(contract),
        )
        builder.validate_final_certification_payloads(
            contract=contract,
            artifacts=artifacts,
            manifest=manifest,
            execution_commit=execution_commit,
            repo_root=ROOT,
        )


def _products(
    contract: contract_module.FinalCertificationContract,
    *,
    runtime_versions: Mapping[str, str] | None = None,
    authority: Mapping[str, Any] | None = None,
) -> builder.ExecutionProducts:
    from src.api.main import create_app

    raw = _junit(reason=contract.test_suite.exact_skip_reason)
    junit = builder.normalize_junit_xml(
        raw,
        execution_commit=P_COMMIT,
        suite=contract.test_suite,
    )
    anchors = _anchor_records(contract)
    pointers = _pointer_records(contract)
    restores = [
        {
            "ordinal": index + 1,
            "pointer_path": spec.path,
            "output_path": spec.output_path,
            "role": spec.role,
            "pointer_declared_md5": spec.md5,
            "pointer_declared_bytes": spec.size,
            "pointer_sha256": hashlib.sha256(spec.path.encode()).hexdigest(),
            "pull_command": {
                "argv": [
                    ".venv/bin/dvc",
                    "pull",
                    "--no-run-cache",
                    "-j",
                    "1",
                    spec.path,
                ],
                "returncode": 0,
            },
            "directed_status_command": {
                "argv": [
                    ".venv/bin/dvc",
                    "status",
                    "--json",
                    spec.path,
                ],
                "returncode": 0,
            },
            "one_pointer_per_command": True,
            "restored_output_regular_single_link": True,
            "cache_object_path_from_declared_md5": True,
            "dvc_transport_authentication_passed": True,
            "payload_opened_by_python": False,
            "payload_decoded": False,
        }
        for index, spec in enumerate(contract.dvc_pointers)
    ]
    openapi = copy.deepcopy(create_app().openapi())
    openapi["x-closure-phase4-final-certification"] = {
        "execution_commit": P_COMMIT,
        "scientific_efficacy_claimed": False,
        "forbidden_paths_opened": False,
    }
    openapi_payload = contract_module.canonical_json_bytes(openapi)
    openapi_validation = builder.validate_openapi_document(
        openapi, root=ROOT, contract=contract
    )
    totals, skips = builder._parse_junit(junit)
    e2e_totals = {
        "tests": 3,
        "passed": 3,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }
    sandbox = {
        "backend": "bubblewrap",
        "argv_template_prefix": builder._expected_bwrap_template(contract),
        "network": "unshared",
        "postgresql_transport": "owned_unix_socket_only",
        "source_tree": "read_only",
        "host_virtualenv": "read_only",
        "effect_sources_retained_by_fd": True,
        "python_console_scripts_interpreter_retained_by_fd": True,
        "private_dvc_configuration_masked": True,
        "forbidden_prefixes_masked": list(contract.forbidden_read_prefixes),
        "forbidden_paths_masked": list(contract.forbidden_read_paths),
        "restored_payloads_masked": [
            spec.output_path for spec in contract.dvc_pointers
        ],
    }
    verification_artifacts = {
        "public_tests.xml": junit,
        "test_report.md": builder._build_test_report(
            execution_commit=P_COMMIT,
            command=builder._public_command(contract),
            totals=totals,
            skip_ledger=skips,
            suite=contract.test_suite,
        ),
        "openapi.json": openapi_payload,
        "openapi_contract_report.md": builder._build_openapi_report(
            execution_commit=P_COMMIT,
            validation=openapi_validation,
            openapi_sha256=contract_module.sha256_bytes(openapi_payload),
        ),
        "end_to_end_report.md": builder._build_e2e_report(
            execution_commit=P_COMMIT,
            command=builder._e2e_command(contract),
            totals=e2e_totals,
        ),
    }
    return builder.build_final_certification_payloads(
        contract=contract,
        execution_commit=P_COMMIT,
        authority=_authority() if authority is None else authority,
        anchor_records=anchors,
        pointer_records=pointers,
        restore_records=restores,
        clone_record={
            "command": {
                "argv": [
                    "git",
                    "clone",
                    "--no-local",
                    "--no-hardlinks",
                    "--single-branch",
                    "--branch",
                    "main",
                    "<LIVE_ORIGIN_MAIN>",
                    "<OWNED_CLONE>",
                ],
                "returncode": 0,
            },
            "execution_commit": P_COMMIT,
            "initially_clean": True,
            "single_parent": True,
            "source": "live_origin_main",
            "remote_url_serialized": False,
            "local_dvc_remote_configuration": {
                "present": True,
                "regular_file": True,
                "single_link": True,
                "git_ignored": True,
                "source_mode_accepted": "0600_or_0644",
                "clone_mode": "0600",
                "copied_only_into_owned_clone": True,
                "content_read_only_for_private_rebase": True,
                "credential_path_rebased_to_retained_fd": True,
                "credential_target_regular_single_link": True,
                "credential_target_group_or_other_writable": False,
                "effective_configuration_equivalent_except_owned_cache": True,
                "content_path_remote_url_and_credentials_serialized": False,
            },
            "dvc_site_caches": (
                contract_module.expected_manifest_clone_dvc_site_caches_record()
            ),
            "dvc_cache": {
                "object_count": 8,
                "declared_payload_bytes": sum(
                    spec.size for spec in contract.dvc_pointers
                ),
                "exact_pointer_objects_only": True,
                "content_addressed_paths_from_declared_md5": True,
                "payload_objects_opened_by_python": False,
                "payloads_decoded": False,
            },
        },
        verification_artifacts=verification_artifacts,
        verification={
            "commands": {
                "public_tests": {
                    "argv": list(builder._public_command(contract)),
                    "returncode": 0,
                },
                "openapi_generation": {
                    "argv": [
                        ".venv/bin/python",
                        "-B",
                        "src/reporting/build_phase4_final_certification.py",
                        "--emit-openapi",
                        "tmp/openapi-raw.json",
                        "--execution-commit",
                        P_COMMIT,
                    ],
                    "returncode": 0,
                },
                "end_to_end": {
                    "argv": list(builder._e2e_command(contract)),
                    "returncode": 0,
                },
                "ty_check": {"argv": [".venv/bin/ty", "check"], "returncode": 0},
                "poetry_lock_check": {
                    "argv": ["poetry", "check", "--lock"],
                    "returncode": 0,
                },
            },
            "public_test_totals": totals,
            "public_skip_ledger": skips,
            "e2e_totals": e2e_totals,
            "openapi_validation": openapi_validation,
            "sandbox": sandbox,
        },
        database={
            "image": builder.POSTGRES_IMAGE,
            "network": "none",
            "cleaned_after_execution": True,
        },
        runtime_versions=(
            contract.expected_runtime_versions
            if runtime_versions is None
            else runtime_versions
        ),
    )


def _publication_root(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    (root / "reports/closure_v1").mkdir(parents=True)
    (root / ".git").mkdir()
    return root


def test_junit_normalization_is_deterministic_and_redacted() -> None:
    contract = _locked_contract()
    first = builder.normalize_junit_xml(
        _junit(reason=contract.test_suite.exact_skip_reason),
        execution_commit=P_COMMIT,
        suite=contract.test_suite,
        clone_root=Path("/tmp/private-clone"),
    )
    second = builder.normalize_junit_xml(
        _junit(reason=contract.test_suite.exact_skip_reason),
        execution_commit=P_COMMIT,
        suite=contract.test_suite,
        clone_root=Path("/tmp/private-clone"),
    )
    assert first == second
    assert b"timestamp=" not in first
    assert b"hostname=" not in first
    assert b" time=" not in first
    assert b"/tmp/private-clone" not in first
    assert P_COMMIT.encode() in first
    root = builder.ET.fromstring(first)
    assert root.tag == "testsuites"
    assert root.attrib == {
        "tests": "2",
        "failures": "0",
        "errors": "0",
        "skipped": "1",
    }
    suite_node = list(root)
    assert len(suite_node) == 1
    assert suite_node[0].attrib == {
        "name": builder.PUBLIC_SUITE_KIND,
        **root.attrib,
    }
    assert [node.tag for node in suite_node[0]] == [
        "properties",
        "testcase",
        "testcase",
    ]
    assert len(list(suite_node[0][0])) == 5


def test_junit_builder_sorts_records_and_rejects_nonsemantic_raw_nodes() -> None:
    contract = _locked_contract()
    raw = builder.ET.fromstring(
        _junit(reason=contract.test_suite.exact_skip_reason)
    )
    suite_node = list(raw)[0]
    cases = [node for node in suite_node if node.tag == "testcase"]
    for case in cases:
        suite_node.remove(case)
    suite_node.extend(reversed(cases))
    reordered = builder.ET.tostring(raw, encoding="utf-8", xml_declaration=True)
    expected = builder.normalize_junit_xml(
        _junit(reason=contract.test_suite.exact_skip_reason),
        execution_commit=P_COMMIT,
        suite=contract.test_suite,
    )
    assert builder.normalize_junit_xml(
        reordered,
        execution_commit=P_COMMIT,
        suite=contract.test_suite,
    ) == expected

    builder.ET.SubElement(suite_node, "system-out").text = "not evidence"
    polluted = builder.ET.tostring(raw, encoding="utf-8", xml_declaration=True)
    with pytest.raises(builder.FinalCertificationBuildError, match="JUnit"):
        builder.normalize_junit_xml(
            polluted,
            execution_commit=P_COMMIT,
            suite=contract.test_suite,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "system_out",
        "root_counter",
        "suite_counter",
        "property_value",
        "property_order",
        "nested_testcase",
        "classname_alias",
        "testcase_order",
        "multiple_suites",
        "root_extra_attribute",
        "testcase_extra_attribute",
        "pass_child",
        "skip_text",
        "noncanonical_whitespace",
    ],
)
def test_reconstructive_validator_rejects_noncanonical_junit_grammar(
    mutation: str,
) -> None:
    contract = _locked_contract()
    products = _products(contract)
    artifacts = dict(products.artifacts)
    manifest = copy.deepcopy(dict(products.manifest))
    root = builder.ET.fromstring(artifacts["public_tests.xml"])
    suite_node = list(root)[0]
    properties = list(suite_node)[0]
    cases = [node for node in suite_node if node.tag == "testcase"]
    passing = next(case for case in cases if not list(case))
    skipped = next(case for case in cases if list(case))
    if mutation == "system_out":
        builder.ET.SubElement(suite_node, "system-out").text = "not evidence"
    elif mutation == "root_counter":
        root.attrib["tests"] = "3"
    elif mutation == "suite_counter":
        suite_node.attrib["skipped"] = "0"
    elif mutation == "property_value":
        list(properties)[2].attrib["value"] = "loopback"
    elif mutation == "property_order":
        first = list(properties)[0]
        properties.remove(first)
        properties.append(first)
    elif mutation == "nested_testcase":
        suite_node.remove(passing)
        builder.ET.SubElement(suite_node, "group").append(passing)
    elif mutation == "classname_alias":
        passing.attrib["classname"] = passing.attrib["classname"].replace(".", "/")
    elif mutation == "testcase_order":
        for case in cases:
            suite_node.remove(case)
        suite_node.extend(reversed(cases))
    elif mutation == "multiple_suites":
        root.append(copy.deepcopy(suite_node))
    elif mutation == "root_extra_attribute":
        root.attrib["name"] = "pytest tests"
    elif mutation == "testcase_extra_attribute":
        passing.attrib["time"] = "0"
    elif mutation == "pass_child":
        builder.ET.SubElement(passing, "system-out")
    elif mutation == "skip_text":
        list(skipped)[0].text = "historical path"
    elif mutation == "noncanonical_whitespace":
        suite_node.text = "\n"
    else:  # pragma: no cover - the parameter list is closed above.
        raise AssertionError(mutation)
    changed = builder.ET.tostring(root, encoding="utf-8", xml_declaration=True)
    artifacts["public_tests.xml"] = changed + (
        b"" if changed.endswith(b"\n") else b"\n"
    )
    _rebind_artifact(
        manifest,
        contract,
        "public_tests.xml",
        artifacts["public_tests.xml"],
    )
    with pytest.raises(builder.FinalCertificationBuildError, match="JUnit"):
        _validate_payloads(
            contract=contract,
            artifacts=artifacts,
            manifest=manifest,
        )


def test_junit_nodeid_reconstruction_handles_modules_classes_and_parameters() -> None:
    assert builder._junit_nodeid("tests.test_module", "test_case[x]") == (
        "tests/test_module.py::test_case[x]"
    )
    assert builder._junit_nodeid("tests.test_module.TestAPI", "test_case") == (
        "tests/test_module.py::TestAPI::test_case"
    )


@pytest.mark.parametrize("duplicate,reason", [(True, "exact"), (False, "drift")])
def test_skip_ledger_rejects_duplicate_nodes_and_reason_drift(
    duplicate: bool, reason: str
) -> None:
    contract = _locked_contract()
    payload = _junit(
        reason=(contract.test_suite.exact_skip_reason if reason == "exact" else reason),
        duplicate_skip=duplicate,
    )
    _, ledger = builder._parse_junit(payload)
    with pytest.raises(builder.FinalCertificationBuildError, match="skip"):
        builder._validate_skip_ledger(ledger, contract.test_suite)


def test_skip_ledger_rejects_order_drift() -> None:
    nodes = (
        "tests/test_alpha.py::test_skip_alpha",
        "tests/test_beta.py::test_skip_beta",
    )
    contract = _locked_contract(nodes=nodes, skipped=nodes)
    reversed_ledger = [
        {
            "nodeid": nodeid,
            "reason": contract.test_suite.exact_skip_reason,
        }
        for nodeid in reversed(nodes)
    ]
    with pytest.raises(builder.FinalCertificationBuildError, match="skip"):
        builder._validate_skip_ledger(reversed_ledger, contract.test_suite)


def test_serialization_guard_rejects_urls_credentials_and_absolute_paths() -> None:
    for payload in (
        b"postgresql+asyncpg://user:pass@host/db",
        b"https://example.invalid/repo",
        b"token=secret",
        b"path /home/person/project",
    ):
        with pytest.raises(builder.FinalCertificationBuildError):
            builder._assert_serialization_safe(payload)


def test_forbidden_path_guard_covers_private_targets_outcomes_and_payloads(
    tmp_path: Path,
) -> None:
    contract = _locked_contract()
    root = tmp_path / "repo"
    root.mkdir()
    forbidden = [
        "private/FULL.md",
        "data/targets/future.parquet",
        "data/closure_v1/evaluation_outcomes/x",
        contract.dvc_pointers[0].output_path,
    ]
    assert all(builder._is_forbidden_path(root / path, root, contract) for path in forbidden)
    assert not builder._is_forbidden_path(root / "docs/API_PROTOCOL.md", root, contract)


def test_openapi_current_application_matches_public_documents() -> None:
    from src.api.main import create_app

    contract = _locked_contract()
    result = builder.validate_openapi_document(
        create_app().openapi(), root=ROOT, contract=contract
    )
    assert result["valid"] is True
    assert result["openapi_path_count"] == 69
    assert result["openapi_operation_count"] == 83
    assert result["documented_operation_count"] == 38


def test_openapi_validator_rejects_operation_id_and_path_count_drift() -> None:
    from src.api.main import create_app

    contract = _locked_contract()
    document = copy.deepcopy(create_app().openapi())
    operations = [
        operation
        for path_item in document["paths"].values()
        for method, operation in path_item.items()
        if method in builder.HTTP_METHODS
    ]
    operations[1]["operationId"] = operations[0]["operationId"]
    with pytest.raises(builder.FinalCertificationBuildError, match="OpenAPI"):
        builder.validate_openapi_document(document, root=ROOT, contract=contract)

    document = copy.deepcopy(create_app().openapi())
    document["paths"].pop(next(iter(document["paths"])))
    with pytest.raises(builder.FinalCertificationBuildError, match="OpenAPI"):
        builder.validate_openapi_document(document, root=ROOT, contract=contract)


def test_payload_builder_and_validator_bind_exact8_and_claim_boundary() -> None:
    contract = _locked_contract()
    products = _products(contract)
    assert list(products.artifacts) == [Path(path).name for path in contract.output_paths[:-1]]
    assert products.manifest["status"] == "completed"
    assert products.manifest["execution_commit"] == P_COMMIT
    assert products.manifest["paths_outside_exact8_equal_p_cert"] is True
    assert products.manifest["scientific_boundary"]["scientific_efficacy_claimed"] is False
    assert products.manifest["p_cert_authority"] == {
        "path": contract_module.AUTHORITY_PATH.as_posix(),
        "bytes": 123,
        "sha256": "c" * 64,
        "p_cert_commit": P_COMMIT,
        "h_cert_commit": H_COMMIT,
        "p4_cert_commit": P_COMMIT,
        "h4_cert_commit": H_COMMIT,
        "p3_cert_commit": contract_module.P3_CERT_COMMIT,
        "h3_cert_commit": contract_module.H3_CERT_COMMIT,
        "p2_cert_commit": contract_module.P2_CERT_COMMIT,
        "h2_cert_commit": contract_module.H2_CERT_COMMIT,
        "p1_cert_commit": contract_module.P1_CERT_COMMIT,
        "h1_cert_commit": contract_module.H1_CERT_COMMIT,
    }
    assert products.manifest["p_cert_companion_manifest"] == {
        "path": contract_module.AUTHORITY_MANIFEST_PATH.as_posix(),
        "bytes": 456,
        "sha256": "d" * 64,
        "p_cert_commit": P_COMMIT,
        "h_cert_commit": H_COMMIT,
        "p4_cert_commit": P_COMMIT,
        "h4_cert_commit": H_COMMIT,
        "p3_cert_commit": contract_module.P3_CERT_COMMIT,
        "h3_cert_commit": contract_module.H3_CERT_COMMIT,
        "p2_cert_commit": contract_module.P2_CERT_COMMIT,
        "h2_cert_commit": contract_module.H2_CERT_COMMIT,
        "p1_cert_commit": contract_module.P1_CERT_COMMIT,
        "h1_cert_commit": contract_module.H1_CERT_COMMIT,
    }
    assert "authority" not in products.manifest
    environment = json.loads(products.artifacts["environment.json"])
    assert environment["dvc"]["main_dvc_command_run"] is False
    assert environment["dvc"]["main_dvc_status_command_run"] is False
    assert (
        environment["dvc"][
            "main_dvc_static_reconstruction_from_git_and_published_pointers"
        ]
        is True
    )
    assert environment["dvc"][
        "main_dvc_site_cache_metadata_inode_inventory_unchanged"
    ] is True
    assert environment["dvc"]["owned_site_cache_count"] == 2
    assert environment["dvc"]["owned_site_cache_roles"] == [
        "runtime_version",
        "restore_status",
    ]
    assert environment["dvc"]["owned_site_cache_filesystem_mode"] == "0700"
    assert environment["dvc"]["owned_site_caches_separated"] is True
    assert environment["dvc"]["owned_site_cache_paths_serialized"] is False
    assert environment["dvc"]["version_seal_before_private_config_or_pull"] is True
    assert environment["dvc"][
        "single_dvc_runtime_retained_through_final_status_and_version_probe"
    ] is True
    assert environment["dvc"]["dvc_runtime_cross_call_identity_revalidated"] is True
    assert "main_dvc_status" not in environment["dvc"]
    assert b"no DVC command, including version/status/pull, ran there" in products.artifacts[
        "FINAL_DOCTORAL_CERTIFICATION_REPORT.md"
    ]
    _validate_payloads(
        contract=contract,
        artifacts=products.artifacts,
        manifest=products.manifest,
        execution_commit=P_COMMIT,
    )


def test_payload_builder_requires_complete_exact_cert4_commit_lineage() -> None:
    contract = _locked_contract()
    for field in (
        "p_cert_commit",
        "h_cert_commit",
        "p4_cert_commit",
        "h4_cert_commit",
        "p3_cert_commit",
        "h3_cert_commit",
        "p2_cert_commit",
        "h2_cert_commit",
        "p1_cert_commit",
        "h1_cert_commit",
    ):
        missing = _authority()
        missing.pop(field)
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="authority commit binding",
        ):
            _products(contract, authority=missing)

        drifted = _authority()
        drifted[field] = "9" * 40
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="authority commit binding",
        ):
            _products(contract, authority=drifted)


def test_reconstructive_validator_rejects_cert4_lineage_omission_and_drift() -> None:
    contract = _locked_contract()
    products = _products(contract)
    fields = (
        "p_cert_commit",
        "h_cert_commit",
        "p4_cert_commit",
        "h4_cert_commit",
        "p3_cert_commit",
        "h3_cert_commit",
        "p2_cert_commit",
        "h2_cert_commit",
        "p1_cert_commit",
        "h1_cert_commit",
    )
    for binding in ("p_cert_authority", "p_cert_companion_manifest"):
        for field in fields:
            missing = copy.deepcopy(dict(products.manifest))
            missing[binding].pop(field)
            with pytest.raises(
                builder.FinalCertificationBuildError,
                match="effective binding",
            ):
                _validate_payloads(
                    contract=contract,
                    artifacts=products.artifacts,
                    manifest=missing,
                )

            drifted = copy.deepcopy(dict(products.manifest))
            drifted[binding][field] = "8" * 40
            with pytest.raises(
                builder.FinalCertificationBuildError,
                match="effective binding",
            ):
                _validate_payloads(
                    contract=contract,
                    artifacts=products.artifacts,
                    manifest=drifted,
                )


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda value: value.__setitem__("status", "completed_unpublished"), "status"),
        (
            lambda value: value["p_cert_authority"].__setitem__("sha256", "0" * 64),
            "p_cert_authority",
        ),
        (
            lambda value: value["p_cert_companion_manifest"].__setitem__(
                "h_cert_commit", "e" * 40
            ),
            "p_cert_companion",
        ),
        (
            lambda value: value["scientific_boundary"].__setitem__(
                "scientific_efficacy_claimed", True
            ),
            "boundary",
        ),
        (lambda value: value["dvc_restores"].pop(), "dvc_restores"),
    ],
)
def test_manifest_validator_rejects_topology_authority_boundary_and_restore_drift(
    mutator: Any, match: str
) -> None:
    contract = _locked_contract()
    products = _products(contract)
    changed = copy.deepcopy(products.manifest)
    mutator(changed)
    with pytest.raises(builder.FinalCertificationBuildError, match=match):
        _validate_payloads(
            contract=contract,
            artifacts=products.artifacts,
            manifest=changed,
            execution_commit=P_COMMIT,
        )


@pytest.mark.parametrize(
    "binding,field,replacement",
    [
        ("p_cert_authority", "sha256", "e" * 64),
        ("p_cert_authority", "bytes", 124),
        ("p_cert_companion_manifest", "sha256", "f" * 64),
        ("p_cert_companion_manifest", "bytes", 457),
    ],
)
def test_reconstructive_validator_rejects_valid_but_wrong_effective_authority_binding(
    binding: str,
    field: str,
    replacement: Any,
) -> None:
    contract = _locked_contract()
    products = _products(contract)
    manifest = copy.deepcopy(dict(products.manifest))
    manifest[binding][field] = replacement
    with pytest.raises(builder.FinalCertificationBuildError, match="effective binding"):
        _validate_payloads(
            contract=contract,
            artifacts=products.artifacts,
            manifest=manifest,
        )


def test_reconstructive_validator_rejects_rehashed_valid_anchor_sha_drift() -> None:
    contract = _locked_contract()
    products = _products(contract)
    manifest = copy.deepcopy(dict(products.manifest))
    manifest["published_anchors"][0]["sha256"] = "e" * 64
    manifest["published_anchor_records_sha256"] = contract_module.digest_records(
        manifest["published_anchors"]
    )
    with pytest.raises(builder.FinalCertificationBuildError, match="anchors"):
        _validate_payloads(
            contract=contract,
            artifacts=products.artifacts,
            manifest=manifest,
        )


def test_reconstructive_validator_rejects_rehashed_pointer_and_restore_sha_drift() -> None:
    contract = _locked_contract()
    products = _products(contract)
    manifest = copy.deepcopy(dict(products.manifest))
    manifest["dvc_pointer_records"][0]["sha256"] = "f" * 64
    manifest["dvc_restores"][0]["pointer_sha256"] = "f" * 64
    manifest["dvc_pointer_records_sha256"] = contract_module.digest_records(
        manifest["dvc_pointer_records"]
    )
    manifest["dvc_restore_records_sha256"] = contract_module.digest_records(
        manifest["dvc_restores"]
    )
    with pytest.raises(builder.FinalCertificationBuildError, match="pointer records"):
        _validate_payloads(
            contract=contract,
            artifacts=products.artifacts,
            manifest=manifest,
        )


def _rebind_artifact(
    manifest: dict[str, Any],
    contract: contract_module.FinalCertificationContract,
    key: str,
    payload: bytes,
) -> None:
    path = next(path for path in contract.output_paths[:-1] if Path(path).name == key)
    record = next(item for item in manifest["artifacts"] if item["path"] == path)
    record["bytes"] = len(payload)
    record["sha256"] = contract_module.sha256_bytes(payload)
    manifest["artifact_records_sha256"] = contract_module.digest_records(
        manifest["artifacts"]
    )


def test_reconstructive_validator_rejects_rehashed_valid_runtime_version_drift() -> None:
    contract = _locked_contract()
    products = _products(contract)
    artifacts = dict(products.artifacts)
    manifest = copy.deepcopy(dict(products.manifest))
    environment = json.loads(artifacts["environment.json"])
    environment["runtime_versions"]["python"] = "Python 9.9.9"
    artifacts["environment.json"] = contract_module.canonical_json_bytes(environment)
    _rebind_artifact(manifest, contract, "environment.json", artifacts["environment.json"])
    with pytest.raises(builder.FinalCertificationBuildError, match="runtime"):
        _validate_payloads(
            contract=contract,
            artifacts=artifacts,
            manifest=manifest,
        )


def test_payload_builder_rejects_runtime_probe_drift_before_outputs() -> None:
    contract = _locked_contract()
    drifted = dict(contract.expected_runtime_versions)
    drifted["python"] = "Python 9.9.9"
    with pytest.raises(builder.FinalCertificationBuildError, match="runtime version"):
        _products(contract, runtime_versions=drifted)


def test_reconstructive_validator_rejects_rehashed_bwrap_template_drift() -> None:
    contract = _locked_contract()
    products = _products(contract)
    artifacts = dict(products.artifacts)
    manifest = copy.deepcopy(dict(products.manifest))
    replacement = [
        "/usr/bin/bwrap",
        "--unshare-all",
        "--ro-bind",
        "<OWNED_CLONE>",
        "/workspace",
    ]
    manifest["verification"]["sandbox"]["argv_template_prefix"] = replacement
    environment = json.loads(artifacts["environment.json"])
    environment["isolation"]["argv_template_prefix"] = replacement
    artifacts["environment.json"] = contract_module.canonical_json_bytes(environment)
    _rebind_artifact(manifest, contract, "environment.json", artifacts["environment.json"])
    with pytest.raises(builder.FinalCertificationBuildError, match="sandbox"):
        _validate_payloads(
            contract=contract,
            artifacts=artifacts,
            manifest=manifest,
        )


def test_reconstructive_validator_rejects_rehashed_passing_junit_nodeid_drift() -> None:
    contract = _locked_contract()
    products = _products(contract)
    artifacts = dict(products.artifacts)
    manifest = copy.deepcopy(dict(products.manifest))
    root = builder.ET.fromstring(artifacts["public_tests.xml"])
    passing = next(case for case in root.iter("testcase") if case.find("skipped") is None)
    passing.attrib["name"] = "test_other"
    changed = builder.ET.tostring(root, encoding="utf-8", xml_declaration=True)
    artifacts["public_tests.xml"] = changed + (b"" if changed.endswith(b"\n") else b"\n")
    _rebind_artifact(
        manifest,
        contract,
        "public_tests.xml",
        artifacts["public_tests.xml"],
    )
    with pytest.raises(builder.FinalCertificationBuildError, match="node-id"):
        _validate_payloads(
            contract=contract,
            artifacts=artifacts,
            manifest=manifest,
        )


@pytest.mark.parametrize(
    "key",
    [
        "public_tests.xml",
        "test_report.md",
        "openapi.json",
        "openapi_contract_report.md",
        "end_to_end_report.md",
        "environment.json",
        "FINAL_DOCTORAL_CERTIFICATION_REPORT.md",
    ],
)
def test_reconstructive_validator_rejects_each_rehashed_artifact_tamper(
    key: str,
) -> None:
    contract = _locked_contract()
    products = _products(contract)
    artifacts = dict(products.artifacts)
    manifest = copy.deepcopy(dict(products.manifest))
    if key == "openapi.json":
        value = json.loads(artifacts[key])
        value["info"]["title"] = "tampered"
        artifacts[key] = contract_module.canonical_json_bytes(value)
    elif key == "environment.json":
        value = json.loads(artifacts[key])
        value["database"]["network"] = "bridge"
        artifacts[key] = contract_module.canonical_json_bytes(value)
    else:
        artifacts[key] += b"\n"
    _rebind_artifact(manifest, contract, key, artifacts[key])
    with pytest.raises(builder.FinalCertificationBuildError):
        _validate_payloads(
            contract=contract,
            artifacts=artifacts,
            manifest=manifest,
            execution_commit=P_COMMIT,
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value["verification"]["commands"]["public_tests"]["argv"].append("-x"),
        lambda value: value["verification"]["e2e_totals"].__setitem__("tests", 4),
        lambda value: value["verification"]["sandbox"].__setitem__("network", "shared"),
        lambda value: value["verification"]["openapi_validation"].__setitem__(
            "openapi_path_count", 68
        ),
        lambda value: value["clone"].__setitem__("source", "local_worktree"),
        lambda value: value["clone"]["local_dvc_remote_configuration"].__setitem__(
            "credential_path_rebased_to_retained_fd", False
        ),
        lambda value: value["clone"]["dvc_site_caches"].__setitem__(
            "used_by_all_isolated_dvc_commands", False
        ),
    ],
)
def test_reconstructive_validator_rejects_verification_clone_and_isolation_tamper(
    mutator: Any,
) -> None:
    contract = _locked_contract()
    products = _products(contract)
    manifest = copy.deepcopy(dict(products.manifest))
    mutator(manifest)
    with pytest.raises(builder.FinalCertificationBuildError):
        _validate_payloads(
            contract=contract,
            artifacts=products.artifacts,
            manifest=manifest,
            execution_commit=P_COMMIT,
        )


def test_reconstructive_validator_rejects_rehashed_restore_record_tamper() -> None:
    contract = _locked_contract()
    products = _products(contract)
    manifest = copy.deepcopy(dict(products.manifest))
    manifest["dvc_restores"][0]["role"] = "invented"
    manifest["dvc_restore_records_sha256"] = contract_module.digest_records(
        manifest["dvc_restores"]
    )
    with pytest.raises(builder.FinalCertificationBuildError, match="restore"):
        _validate_payloads(
            contract=contract,
            artifacts=products.artifacts,
            manifest=manifest,
            execution_commit=P_COMMIT,
        )


def test_reconstructive_validator_rejects_pointer_restore_identity_drift() -> None:
    contract = _locked_contract()
    products = _products(contract)
    manifest = copy.deepcopy(dict(products.manifest))
    manifest["dvc_restores"][0]["pointer_sha256"] = "9" * 64
    manifest["dvc_restore_records_sha256"] = contract_module.digest_records(
        manifest["dvc_restores"]
    )
    with pytest.raises(builder.FinalCertificationBuildError, match="pointer/restore"):
        _validate_payloads(
            contract=contract,
            artifacts=products.artifacts,
            manifest=manifest,
            execution_commit=P_COMMIT,
        )


def test_manifest_projects_exact_cooperative_concurrency_boundary() -> None:
    contract = _locked_contract()
    publication = _products(contract).manifest["publication"]
    assert publication == {
        "ordered_paths": list(contract.output_paths),
        "output_count": 8,
        "manifest_written_last": True,
        "no_clobber": True,
        "concurrency_lock": "flock_retained_git_directory",
        "legacy_guard_path_must_be_absent": (
            "tmp/closure_v1_phase4_final_certification/certification.guard"
        ),
        "external_namespace_mutation_is_stop_condition": True,
        "noncooperating_same_uid_namespace_mutation": "out_of_scope",
        "identity_revalidated_before_and_after_name_cleanup": True,
        "conditional_unlink_by_inode_claimed": False,
        "cleanup_before_precommit": True,
    }
    assert "guard_path" not in publication
    assert "rollback_owned_inodes_only" not in publication


def test_publication_is_exact_manifest_last_single_link_and_cleans_namespace(
    tmp_path: Path,
) -> None:
    contract = _locked_contract()
    products = _products(contract)
    root = _publication_root(tmp_path)
    stages: list[str] = []
    result = builder.publish_final_certification_bundle(
        repo_root=root,
        contract=contract,
        products=products,
        publication_validator=stages.append,
    )
    assert result["status"] == "certification_bundle_written_unpublished"
    assert stages == [
        "before_first_link",
        "before_manifest_link",
        "after_all_links",
        "after_run_namespace_cleanup",
        "before_success_return",
        "after_final_readback",
    ]
    output = root / contract_module.CERTIFICATION_ROOT
    assert {path.name for path in output.iterdir()} == {
        Path(path).name for path in contract.output_paths
    }
    for path in output.iterdir():
        metadata = path.lstat()
        assert stat.S_ISREG(metadata.st_mode)
        assert metadata.st_nlink == 1
        assert stat.S_IMODE(metadata.st_mode) == 0o644
    assert json.loads((output / "final_certification_manifest.json").read_bytes())[
        "status"
    ] == "completed"
    assert not (root / "tmp/closure_v1_phase4_final_certification").exists()


@pytest.mark.parametrize("failure_after", [1, 7, 8])
def test_publication_failure_rolls_back_every_owned_output_and_guard(
    tmp_path: Path, failure_after: int
) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    with pytest.raises(builder.FinalCertificationBuildError, match="synthetic"):
        builder.publish_final_certification_bundle(
            repo_root=root,
            contract=contract,
            products=_products(contract),
            failure_after_links=failure_after,
        )
    assert not (root / contract_module.CERTIFICATION_ROOT).exists()
    assert not (root / "tmp/closure_v1_phase4_final_certification").exists()


def test_publication_rejects_existing_or_symlink_namespace_without_clobber(
    tmp_path: Path,
) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    output = root / contract_module.CERTIFICATION_ROOT
    output.mkdir()
    sentinel = output / "sentinel"
    sentinel.write_text("keep")
    with pytest.raises(builder.FinalCertificationBuildError, match="already exists"):
        builder.publish_final_certification_bundle(
            repo_root=root, contract=contract, products=_products(contract)
        )
    assert sentinel.read_text() == "keep"

    output.rmdir() if not any(output.iterdir()) else None
    sentinel.unlink()
    output.rmdir()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "sentinel").write_text("keep")
    output.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(builder.FinalCertificationBuildError, match="already exists"):
        builder.publish_final_certification_bundle(
            repo_root=root, contract=contract, products=_products(contract)
        )
    assert (foreign / "sentinel").read_text() == "keep"


def test_publication_preserves_foreign_replacement_and_fails_closed(
    tmp_path: Path,
) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)

    def replace(stage: str) -> None:
        if stage == "before_manifest_link":
            target = root / contract.output_paths[0]
            target.unlink()
            target.write_text("foreign")

    with pytest.raises(builder.FinalCertificationBuildError, match="cleanup"):
        builder.publish_final_certification_bundle(
            repo_root=root,
            contract=contract,
            products=_products(contract),
            publication_validator=replace,
        )
    assert (root / contract.output_paths[0]).read_text() == "foreign"


def test_publication_final_rebind_detects_parent_swap_and_rolls_back_owned_exact8(
    tmp_path: Path,
) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    moved_reports = root / "reports-owned"

    def swap_parent(stage: str) -> None:
        if stage == "after_all_links":
            (root / "reports").rename(moved_reports)
            (root / "reports/closure_v1").mkdir(parents=True)
            (root / "reports/closure_v1/sentinel").write_text("foreign")

    with pytest.raises(builder.FinalCertificationBuildError, match="R-CERT"):
        builder.publish_final_certification_bundle(
            repo_root=root,
            contract=contract,
            products=_products(contract),
            publication_validator=swap_parent,
        )
    assert (root / "reports/closure_v1/sentinel").read_text() == "foreign"
    assert not (moved_reports / "closure_v1/12_certification").exists()


def test_guard_is_whole_run_exclusive_and_symlink_safe(tmp_path: Path) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    first = builder._acquire_run_guard(root, contract)
    try:
        assert not (root / contract.legacy_guard_path_must_be_absent).exists()
        with pytest.raises(builder.FinalCertificationBuildError, match="cooperative lock"):
            builder._acquire_run_guard(root, contract)
    finally:
        first.release()
        first.close()
    assert not (root / "tmp").exists()

    foreign = tmp_path / "foreign-guard"
    foreign.mkdir()
    (root / "tmp").symlink_to(foreign, target_is_directory=True)
    with pytest.raises(builder.FinalCertificationBuildError, match="work namespace"):
        builder._acquire_run_guard(root, contract)
    assert list(foreign.iterdir()) == []


def test_flock_survives_namespace_release_and_legacy_guard_is_never_mutated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    legacy_name = Path(contract.legacy_guard_path_must_be_absent).name
    original_create = builder._create_owned_file_at
    original_unlink = builder._unlink_owned_at

    def create(parent: Any, name: str, *args: Any, **kwargs: Any) -> Any:
        assert name != legacy_name
        return original_create(parent, name, *args, **kwargs)

    def unlink(entry: Any, *args: Any, **kwargs: Any) -> Any:
        assert entry.name != legacy_name
        return original_unlink(entry, *args, **kwargs)

    monkeypatch.setattr(builder, "_create_owned_file_at", create)
    monkeypatch.setattr(builder, "_unlink_owned_at", unlink)
    first = builder._acquire_run_guard(root, contract)
    first.release()
    assert not (root / contract.legacy_guard_path_must_be_absent).exists()
    with pytest.raises(builder.FinalCertificationBuildError, match="cooperative lock"):
        builder._acquire_run_guard(root, contract)
    first.close()
    second = builder._acquire_run_guard(root, contract)
    second.release()
    second.close()
    assert not (root / "tmp").exists()


def test_guard_work_cleanup_preserves_foreign_name_replacement(tmp_path: Path) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    lease = builder._acquire_run_guard(root, contract)
    work, identity = lease.create_work_directory()
    lease.seal_work_inventory()
    detached_owned = work.with_name("detached-owned")
    work.rename(detached_owned)
    work.mkdir()
    sentinel = work / "sentinel"
    sentinel.write_text("foreign")
    try:
        with pytest.raises(builder.FinalCertificationBuildError, match="identity"):
            lease.remove_work_directory(work, identity)
        assert sentinel.read_text() == "foreign"
    finally:
        sentinel.unlink()
        work.rmdir()
        detached_owned.rmdir()
        lease.release()
        lease.close()
    assert not (root / "tmp").exists()


@pytest.mark.parametrize("long_stage", ["clone", "dvc_pull", "verification"])
def test_work_namespace_binding_detects_transient_swap_restore(
    tmp_path: Path, long_stage: str
) -> None:
    del long_stage
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    lease = builder._acquire_run_guard(root, contract)
    work, identity = lease.create_work_directory()
    parent_before = builder._directory_binding(lease.parent)
    saved = work.with_name("saved-owned-work")
    work.rename(saved)
    work.mkdir()
    work.rmdir()
    saved.rename(work)
    lease.revalidate_work_namespace(context="post-command")
    assert builder._directory_binding(lease.parent) != parent_before
    lease.seal_work_inventory()
    lease.remove_work_directory(work, identity)
    lease.release()
    lease.close()


def test_repository_root_lease_detects_transient_root_swap_restore(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    root = parent / "repository"
    parent.mkdir()
    root.mkdir()
    lease = builder._open_repository_root_lease(root)
    saved = parent / "saved-repository"
    root.rename(saved)
    root.mkdir()
    root.rmdir()
    saved.rename(root)
    try:
        with pytest.raises(builder.FinalCertificationBuildError, match="namespace"):
            lease.revalidate(context="post transient root swap")
    finally:
        lease.close()


@pytest.mark.parametrize("injection_stage", ["pre_recursive", "during_recursive"])
def test_sealed_work_cleanup_detects_and_preserves_injected_foreign_inode(
    tmp_path: Path, injection_stage: str
) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    lease = builder._acquire_run_guard(root, contract)
    work, identity = lease.create_work_directory()
    (work / "a-owned").write_text("a")
    (work / "z-owned").write_text("z")
    lease.seal_work_inventory()
    owned_remove_calls = 0

    def inject(stage: str) -> None:
        nonlocal owned_remove_calls
        should_inject = stage == "after_root_detach" and injection_stage == "pre_recursive"
        if stage.startswith("before_owned_remove:"):
            owned_remove_calls += 1
            should_inject = (
                injection_stage == "during_recursive" and owned_remove_calls == 2
            )
        if should_inject:
            assert lease.work is not None
            descriptor = os.open(
                "foreign",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=lease.work.fd,
            )
            os.write(descriptor, b"foreign")
            os.close(descriptor)

    try:
        with pytest.raises(builder.FinalCertificationBuildError, match="gained|lost"):
            lease.remove_work_directory(
                work,
                identity,
                cleanup_callback=inject,
            )
        assert (work / "foreign").read_bytes() == b"foreign"
    finally:
        for path in work.iterdir():
            path.unlink()
        work.rmdir()
        lease.release()
        lease.close()
    assert not (root / "tmp").exists()


@pytest.mark.parametrize("entry_kind", ["file", "directory"])
@pytest.mark.parametrize("capture_boundary", [1, 3])
def test_atomic_cleanup_secondary_capture_preserves_post_detach_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry_kind: str,
    capture_boundary: int,
) -> None:
    parent_path = tmp_path / "parent"
    parent_path.mkdir()
    canonical = parent_path / "owned"
    saved = parent_path / "saved-owned"
    if entry_kind == "file":
        canonical.write_text("owned")
    else:
        canonical.mkdir()
    metadata = canonical.lstat()
    parent_fd = os.open(parent_path, os.O_RDONLY | os.O_DIRECTORY)
    parent_meta = os.fstat(parent_fd)
    parent = builder.DirectoryHandle(
        parent_path,
        parent_fd,
        parent_meta.st_dev,
        parent_meta.st_ino,
    )
    original_rename = builder._rename_noreplace_at
    injected = False
    capture_count = 0

    def swap_after_first_capture(
        source_parent_fd: int,
        source_name: str,
        target_parent_fd: int,
        target_name: str,
    ) -> None:
        nonlocal capture_count, injected
        original_rename(
            source_parent_fd,
            source_name,
            target_parent_fd,
            target_name,
        )
        if source_name == "owned" or source_name.startswith(".owned-cleanup-"):
            capture_count += 1
        if capture_count == capture_boundary and not injected:
            os.rename(
                target_name,
                saved.name,
                src_dir_fd=target_parent_fd,
                dst_dir_fd=target_parent_fd,
            )
            if entry_kind == "file":
                (parent_path / target_name).write_text("foreign")
            else:
                (parent_path / target_name).mkdir()
                (parent_path / target_name / "marker").write_text("foreign")
            injected = True

    monkeypatch.setattr(builder, "_rename_noreplace_at", swap_after_first_capture)
    try:
        with pytest.raises(builder.FinalCertificationBuildError, match="replacement"):
            if entry_kind == "file":
                builder._unlink_owned_at(
                    builder.OwnedFileAt(
                        parent,
                        canonical.name,
                        metadata.st_dev,
                        metadata.st_ino,
                    ),
                    context="post-detach file probe",
                )
            else:
                builder._remove_owned_empty_directory_at(
                    parent,
                    canonical.name,
                    device=metadata.st_dev,
                    inode=metadata.st_ino,
                    context="post-detach directory probe",
                )
        if entry_kind == "file":
            assert canonical.read_text() == "foreign"
            assert saved.read_text() == "owned"
        else:
            assert (canonical / "marker").read_text() == "foreign"
            assert saved.is_dir()
        assert not list(parent_path.glob(".owned-cleanup-*"))
    finally:
        parent.close()


def test_recursive_cleanup_uses_secondary_capture_for_each_inode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_path = tmp_path / "work"
    root_path.mkdir()
    owned = root_path / "owned.txt"
    owned.write_text("owned")
    root_fd = os.open(root_path, os.O_RDONLY | os.O_DIRECTORY)
    root_meta = os.fstat(root_fd)
    root = builder.DirectoryHandle(
        root_path, root_fd, root_meta.st_dev, root_meta.st_ino
    )
    inventory = builder._scan_work_inventory(root)
    original_rename = builder._rename_noreplace_at
    injected = False

    def swap_after_first_capture(
        source_parent_fd: int,
        source_name: str,
        target_parent_fd: int,
        target_name: str,
    ) -> None:
        nonlocal injected
        original_rename(
            source_parent_fd,
            source_name,
            target_parent_fd,
            target_name,
        )
        if source_name == "owned.txt" and not injected:
            os.rename(
                target_name,
                "saved-owned.txt",
                src_dir_fd=target_parent_fd,
                dst_dir_fd=target_parent_fd,
            )
            descriptor = os.open(
                target_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=target_parent_fd,
            )
            os.write(descriptor, b"foreign")
            os.close(descriptor)
            injected = True

    monkeypatch.setattr(builder, "_rename_noreplace_at", swap_after_first_capture)
    try:
        with pytest.raises(builder.FinalCertificationBuildError, match="replacement"):
            builder._remove_sealed_work_tree(
                root,
                inventory,
                cleanup_callback=None,
            )
        assert (root_path / "owned.txt").read_bytes() == b"foreign"
        assert (root_path / "saved-owned.txt").read_text() == "owned"
    finally:
        root.close()


def test_work_and_subdirectory_creation_reject_prepublication_foreign_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    lease = builder._acquire_run_guard(root, contract)
    original_rename = builder._rename_noreplace_at
    injected_work: Path | None = None

    def inject_foreign_work(
        source_parent_fd: int,
        source_name: str,
        target_parent_fd: int,
        target_name: str,
    ) -> None:
        nonlocal injected_work
        if source_name.startswith(".owned-dir-") and target_name.startswith("run-"):
            injected_work = lease.parent.path / target_name
            injected_work.mkdir()
            (injected_work / "foreign").write_text("foreign")
        original_rename(
            source_parent_fd,
            source_name,
            target_parent_fd,
            target_name,
        )

    monkeypatch.setattr(builder, "_rename_noreplace_at", inject_foreign_work)
    with pytest.raises(builder.FinalCertificationBuildError, match="already exists"):
        lease.create_work_directory()
    assert injected_work is not None
    assert (injected_work / "foreign").read_text() == "foreign"
    (injected_work / "foreign").unlink()
    injected_work.rmdir()

    monkeypatch.setattr(builder, "_rename_noreplace_at", original_rename)
    work, identity = lease.create_work_directory()
    injected_subdirectory = work / "dvc-cache"

    def inject_foreign_subdirectory(
        source_parent_fd: int,
        source_name: str,
        target_parent_fd: int,
        target_name: str,
    ) -> None:
        if source_name.startswith(".owned-dir-") and target_name == "dvc-cache":
            injected_subdirectory.mkdir()
            (injected_subdirectory / "foreign").write_text("foreign")
        original_rename(
            source_parent_fd,
            source_name,
            target_parent_fd,
            target_name,
        )

    monkeypatch.setattr(
        builder,
        "_rename_noreplace_at",
        inject_foreign_subdirectory,
    )
    with pytest.raises(builder.FinalCertificationBuildError, match="already exists"):
        lease.create_work_subdirectory("dvc-cache", mode=0o700)
    assert (injected_subdirectory / "foreign").read_text() == "foreign"
    (injected_subdirectory / "foreign").unlink()
    injected_subdirectory.rmdir()
    monkeypatch.setattr(builder, "_rename_noreplace_at", original_rename)
    lease.seal_work_inventory()
    lease.remove_work_directory(work, identity)
    lease.release()
    lease.close()


def test_missing_lease_chain_creation_rejects_prepublication_foreign_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    original_rename = builder._rename_noreplace_at

    def inject_component(
        source_parent_fd: int,
        source_name: str,
        target_parent_fd: int,
        target_name: str,
    ) -> None:
        if source_name.startswith(".owned-dir-") and target_name == "tmp":
            (root / "tmp").mkdir()
            (root / "tmp/foreign").write_text("foreign")
        original_rename(
            source_parent_fd,
            source_name,
            target_parent_fd,
            target_name,
        )

    monkeypatch.setattr(builder, "_rename_noreplace_at", inject_component)
    with pytest.raises(builder.FinalCertificationBuildError, match="already exists"):
        builder._open_directory_chain(
            root,
            Path("tmp/closure_v1_phase4_final_certification"),
            create_missing=True,
        )
    assert (root / "tmp/foreign").read_text() == "foreign"


def test_failed_workspace_setup_preserves_unregistered_foreign_subdirectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    repository_lease = builder._open_repository_root_lease(root)
    lease = builder._acquire_run_guard(root, contract)
    original_rename = builder._rename_noreplace_at
    injected: Path | None = None

    def inject_foreign_subdirectory(
        source_parent_fd: int,
        source_name: str,
        target_parent_fd: int,
        target_name: str,
    ) -> None:
        nonlocal injected
        if source_name.startswith(".owned-dir-") and target_name == "dvc-cache":
            assert lease.work is not None
            injected = lease.work.path / target_name
            injected.mkdir()
            (injected / "foreign").write_text("foreign")
        original_rename(
            source_parent_fd,
            source_name,
            target_parent_fd,
            target_name,
        )

    monkeypatch.setattr(
        builder,
        "_rename_noreplace_at",
        inject_foreign_subdirectory,
    )
    with pytest.raises(builder.FinalCertificationBuildError, match="cleanup failed"):
        builder._prepare_owned_workspace(
            root=root,
            lease=lease,
            repository_lease=repository_lease,
        )
    repository_lease.close()
    assert injected is not None
    assert (injected / "foreign").read_text() == "foreign"
    work = injected.parent
    (injected / "foreign").unlink()
    injected.rmdir()
    work.rmdir()
    parent = work.parent
    while parent != root and parent.exists() and not any(parent.iterdir()):
        next_parent = parent.parent
        parent.rmdir()
        parent = next_parent


def _dvc_contract(
    tmp_path: Path,
) -> tuple[contract_module.FinalCertificationContract, dict[str, bytes]]:
    base = _locked_contract()
    payloads = {f"payload-{index}.parquet": f"transport-{index}".encode() for index in range(8)}
    specs = tuple(
        contract_module.DvcPointerSpec(
            path=f"data/payload-{index}.parquet.dvc",
            role="transport",
            output_path=f"data/payload-{index}.parquet",
            md5=hashlib.md5(payloads[f"payload-{index}.parquet"], usedforsecurity=False).hexdigest(),
            size=len(payloads[f"payload-{index}.parquet"]),
        )
        for index in range(8)
    )
    return replace(base, dvc_pointers=specs), payloads


def _prepare_pointers(
    clone: Path,
    contract: contract_module.FinalCertificationContract,
) -> None:
    for spec in contract.dvc_pointers:
        path = clone / spec.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "outs:\n"
            f"- md5: {spec.md5}\n"
            f"  size: {spec.size}\n"
            "  hash: md5\n"
            f"  path: {Path(spec.output_path).name}\n"
        )


def _fake_installed_dvc_configuration() -> SimpleNamespace:
    return SimpleNamespace(
        pass_fds=(),
        bind_owned_cache=lambda _path: None,
        revalidate=lambda **kwargs: None,
    )


def test_private_dvc_config_is_read_for_copy_but_never_serialized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    clone = tmp_path / "clone"
    (source / ".dvc").mkdir(parents=True)
    (clone / ".dvc").mkdir(parents=True)
    credential = source / "private/credential.json"
    credential.parent.mkdir()
    credential.write_bytes(b"opaque-private-credential")
    credential.chmod(0o755)
    private_bytes = (
        b"[core]\n"
        b"    remote = private\n"
        b"['remote \"private\"']\n"
        b"    url = opaque-private-remote\n"
        b"    credentialpath = ../private/credential.json\n"
    )
    source_config = source / contract_module.LOCAL_DVC_CONFIG_PATH
    source_config.write_bytes(private_bytes)
    source_config.chmod(0o644)
    monkeypatch.setattr(
        builder,
        "validate_local_dvc_remote_configuration",
        lambda **kwargs: {
            "present": True,
            "regular_file": True,
            "single_link": True,
            "git_ignored": True,
            "filesystem_mode": "0644",
            "content_opened": False,
            "content_or_path_serialized": False,
        },
    )
    git_calls: list[list[str]] = []

    def ignored(argv: Any, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        git_calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(builder.subprocess, "run", ignored)
    installed = builder._install_local_dvc_remote_configuration(
        source_root=source, clone_root=clone
    )
    try:
        clone_config = clone / contract_module.LOCAL_DVC_CONFIG_PATH
        clone_parser = builder._parse_private_dvc_config(clone_config.read_bytes())
        clone_section = builder._credential_sections(clone_parser)[0]
        bridge = clone_parser.get(clone_section, "credentialpath", raw=True)
        assert bridge == installed.credentials[0].proc_path
        assert os.fstat(installed.credentials[0].fd).st_ino == credential.stat().st_ino
        assert stat.S_IMODE(clone_config.lstat().st_mode) == 0o600
        record = dict(installed.public_record)
        assert record == {
        "present": True,
        "regular_file": True,
        "single_link": True,
        "git_ignored": True,
        "source_mode_accepted": "0600_or_0644",
        "clone_mode": "0600",
        "copied_only_into_owned_clone": True,
        "content_read_only_for_private_rebase": True,
        "credential_path_rebased_to_retained_fd": True,
        "credential_target_regular_single_link": True,
        "credential_target_group_or_other_writable": False,
        "effective_configuration_equivalent_except_owned_cache": True,
        "content_path_remote_url_and_credentials_serialized": False,
        }
        serialized = contract_module.canonical_json_bytes(record)
        assert private_bytes not in serialized
        assert b"opaque-private-remote" not in serialized
        assert b"credential.json" not in serialized
        assert b"/proc/self/fd" not in serialized
    finally:
        installed.close()
    assert git_calls == [
        [
            builder.GIT_EXECUTABLE,
            "check-ignore",
            "--quiet",
            "--",
            contract_module.LOCAL_DVC_CONFIG_PATH.as_posix(),
        ]
    ]


@pytest.mark.parametrize("swap_kind", ["source_ancestor", "destination_name"])
def test_private_dvc_config_copy_detects_ancestor_or_name_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, swap_kind: str
) -> None:
    source = tmp_path / "source"
    clone = tmp_path / "clone"
    (source / ".dvc").mkdir(parents=True)
    (clone / ".dvc").mkdir(parents=True)
    credential = source / "private/credential.json"
    credential.parent.mkdir()
    credential.write_text("sealed credential\n")
    credential.chmod(0o600)
    (source / ".dvc/config.local").write_text(
        '[remote "private"]\ncredentialpath = ../private/credential.json\n'
    )
    (source / ".dvc/config.local").chmod(0o600)
    monkeypatch.setattr(
        builder,
        "validate_local_dvc_remote_configuration",
        lambda **kwargs: {
            "present": True,
            "regular_file": True,
            "single_link": True,
            "filesystem_mode": "0600",
            "git_ignored": True,
            "content_opened": False,
            "content_or_path_serialized": False,
        },
    )

    def swap(*args: Any, **kwargs: Any) -> SimpleNamespace:
        if swap_kind == "source_ancestor":
            (source / ".dvc").rename(source / ".dvc-owned")
            (source / ".dvc").mkdir()
            foreign = source / ".dvc/config.local"
        else:
            (clone / ".dvc/config.local").rename(
                clone / ".dvc/config.local-owned"
            )
            foreign = clone / ".dvc/config.local"
        foreign.write_text("foreign\n")
        foreign.chmod(0o600)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(builder.subprocess, "run", swap)
    with pytest.raises(builder.FinalCertificationBuildError, match="identity|rebind"):
        builder._install_local_dvc_remote_configuration(
            source_root=source, clone_root=clone
        )
    if swap_kind == "source_ancestor":
        assert (source / ".dvc/config.local").read_text() == "foreign\n"
    else:
        assert (clone / ".dvc/config.local").read_text() == "foreign\n"


@pytest.mark.parametrize(
    "unsafe_kind",
    ["group_writable", "hardlink", "symlink", "ancestor_symlink", "escape"],
)
def test_private_credential_fd_bridge_rejects_unsafe_path_or_inode(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    private = source / "private"
    private.mkdir()
    credential = private / "credential.json"
    credential.write_text("private credential\n", encoding="utf-8")
    credential.chmod(0o600)
    configured = "../private/credential.json"
    if unsafe_kind == "group_writable":
        credential.chmod(0o620)
    elif unsafe_kind == "hardlink":
        os.link(credential, private / "credential-copy.json")
    elif unsafe_kind == "symlink":
        credential.rename(private / "credential-owned.json")
        credential.symlink_to(private / "credential-owned.json")
    elif unsafe_kind == "ancestor_symlink":
        private.rename(source / "private-owned")
        private.symlink_to(source / "private-owned", target_is_directory=True)
    elif unsafe_kind == "escape":
        configured = "../../outside.json"

    with pytest.raises(
        builder.FinalCertificationBuildError,
        match="credential|private/|repository root",
    ) as raised:
        builder._open_retained_private_credential(source, configured)
    assert os.fspath(tmp_path) not in str(raised.value)


def test_private_dvc_effective_equivalence_allows_only_owned_cache_overrides() -> None:
    source = (
        b"[core]\nremote = private\nsite_cache_dir = /opaque/main-site-cache\n"
        b"[cache]\nshared = group\ndir = /opaque/source-cache\ntype = reflink\n"
        b"['remote \"private\"']\nurl = opaque-remote\n"
        b"credentialpath = ../private/credential.json\n"
    )
    clone = (
        b"[core]\nremote = private\nsite_cache_dir = /opaque/main-site-cache\n"
        b"[cache]\nshared = group\ndir = /owned/cache\ntype = copy\n"
        b"['remote \"private\"']\nurl = opaque-remote\n"
        b"credentialpath = /proc/self/fd/41\n"
    )
    builder._require_private_dvc_config_equivalence(
        source,
        clone,
        credential_sections=('\'remote "private"\'',),
        credential_proc_paths=("/proc/self/fd/41",),
        allow_operational_cache=True,
        owned_cache_dir="/owned/cache",
    )
    drifted = clone.replace(b"url = opaque-remote", b"url = different-remote")
    with pytest.raises(
        builder.FinalCertificationBuildError,
        match="effective configuration drifted",
    ) as raised:
        builder._require_private_dvc_config_equivalence(
            source,
            drifted,
            credential_sections=('\'remote "private"\'',),
            credential_proc_paths=("/proc/self/fd/41",),
            allow_operational_cache=True,
            owned_cache_dir="/owned/cache",
        )
    assert "opaque" not in str(raised.value)
    assert "/owned" not in str(raised.value)

    wrong_cache = clone.replace(b"dir = /owned/cache", b"dir = /foreign/cache")
    with pytest.raises(
        builder.FinalCertificationBuildError,
        match="owned cache settings drifted",
    ) as raised:
        builder._require_private_dvc_config_equivalence(
            source,
            wrong_cache,
            credential_sections=('\'remote "private"\'',),
            credential_proc_paths=("/proc/self/fd/41",),
            allow_operational_cache=True,
            owned_cache_dir="/owned/cache",
        )
    assert "/owned" not in str(raised.value)
    assert "/foreign" not in str(raised.value)


def test_main_dvc_static_boundary_proves_private_site_cache_metadata_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _locked_contract()
    anchors, pointers = _static_boundary_records(contract)
    root = tmp_path / "repo"
    site_cache = root / ".dvc/tmp/site-cache"
    site_cache.mkdir(parents=True)
    site_cache.chmod(0o700)
    (site_cache / "sentinel").write_text("unchanged\n", encoding="utf-8")
    (root / ".dvc/config.local").write_text(
        "[core]\n" f"site_cache_dir = {site_cache}\n",
        encoding="utf-8",
    )
    (root / ".dvc/config.local").chmod(0o600)
    monkeypatch.setattr(
        builder,
        "collect_anchor_input_records",
        lambda *args, **kwargs: copy.deepcopy(anchors),
    )
    monkeypatch.setattr(
        builder,
        "collect_dvc_pointer_records",
        lambda *args, **kwargs: copy.deepcopy(pointers),
    )
    dvc_calls: list[str] = []

    def reject_dvc(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        dvc_calls.append("attempted")
        raise AssertionError("main DVC subprocess must not run")

    monkeypatch.setattr(builder, "_dvc_status", reject_dvc)
    monkeypatch.setattr(builder, "_run", reject_dvc)
    before_root = site_cache.stat()
    before_inventory = sorted(path.name for path in site_cache.iterdir())
    lease = builder._open_main_dvc_site_cache_lease(root)
    try:
        observed_anchors, observed_pointers, boundary = (
            builder._reconstruct_main_dvc_static_boundary(
                root=root,
                contract=contract,
                context="adversarial no-main-DVC probe",
                main_site_cache_lease=lease,
            )
        )
        assert observed_anchors == anchors
        assert observed_pointers == pointers
        assert boundary["main_dvc_status_command_run"] is False
        assert (
            boundary[
                "main_dvc_static_reconstruction_from_git_and_published_pointers"
            ]
            is True
        )
        assert boundary["published_dvc_pointer_count"] == 8
        after_root = site_cache.stat()
        assert builder._stat_identity(after_root) == builder._stat_identity(before_root)
        assert sorted(path.name for path in site_cache.iterdir()) == before_inventory
        assert dvc_calls == []

        authority = _authority()
        clean = {
            "head": P_COMMIT,
            "main": P_COMMIT,
            "origin_main": P_COMMIT,
            "origin_head": P_COMMIT,
            "status": "",
            "cached_diff": "",
            "unstaged_diff": "",
        }
        monkeypatch.setattr(
            builder, "_capture_main_state", lambda path: dict(clean)
        )
        monkeypatch.setattr(
            builder,
            "_authority_loader",
            lambda *args, **kwargs: authority,
        )
        monkeypatch.setattr(
            builder,
            "validate_local_dvc_remote_configuration",
            lambda **kwargs: {"present": True},
        )
        builder._revalidate_publication_gate(
            root=root,
            contract=contract,
            execution_commit=P_COMMIT,
            expected_authority=authority,
            expected_anchors=anchors,
            expected_pointers=pointers,
            expected_local_remote={"present": True},
            stage="before_first_link",
            main_site_cache_lease=lease,
        )
        lease.revalidate(context="after static publication gate")
        assert builder._stat_identity(site_cache.stat()) == builder._stat_identity(
            before_root
        )
        assert dvc_calls == []

        def mutate_during_reconstruction(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            transient = site_cache / "transient"
            transient.write_text("drift\n", encoding="utf-8")
            transient.unlink()
            return copy.deepcopy(pointers)

        monkeypatch.setattr(
            builder,
            "collect_dvc_pointer_records",
            mutate_during_reconstruction,
        )
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="site cache root changed",
        ):
            builder._reconstruct_main_dvc_static_boundary(
                root=root,
                contract=contract,
                context="transient main site-cache drift",
                main_site_cache_lease=lease,
            )
        assert dvc_calls == []
    finally:
        lease.close()


@pytest.mark.parametrize("drift_kind", ["root_mode", "transient_root_entry"])
def test_main_dvc_site_cache_snapshot_includes_root_metadata(
    tmp_path: Path,
    drift_kind: str,
) -> None:
    root = tmp_path / "repo"
    site_cache = root / ".dvc/tmp/site-cache"
    site_cache.mkdir(parents=True)
    site_cache.chmod(0o700)
    config = root / ".dvc/config.local"
    config.write_text(
        "[core]\n" f"site_cache_dir = {site_cache}\n",
        encoding="utf-8",
    )
    config.chmod(0o600)
    lease = builder._open_main_dvc_site_cache_lease(root)
    try:
        if drift_kind == "root_mode":
            site_cache.chmod(0o755)
        else:
            transient = site_cache / "transient"
            transient.write_text("drift\n", encoding="utf-8")
            transient.unlink()
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="site cache root changed",
        ) as raised:
            lease.revalidate(context="adversarial root metadata probe")
        assert os.fspath(site_cache) not in str(raised.value)
    finally:
        lease.close()


@pytest.mark.parametrize("drift_kind", ["root_mode", "transient_root_entry"])
def test_owned_dvc_site_cache_checkpoint_rejects_unapproved_root_drift(
    tmp_path: Path,
    drift_kind: str,
) -> None:
    site_cache = tmp_path / "site-cache"
    site_cache.mkdir(mode=0o700)
    chain, _ = builder._open_directory_chain(
        Path("/"), site_cache.relative_to(Path("/")), create_missing=False
    )
    handle = chain[-1]
    try:
        expected = builder._site_cache_root_identity(
            handle,
            expected_mode=0o700,
            context="owned site-cache baseline",
        )
        if drift_kind == "root_mode":
            site_cache.chmod(0o755)
        else:
            transient = site_cache / "transient"
            transient.write_text("drift\n", encoding="utf-8")
            transient.unlink()
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="root (identity or mode|metadata) drifted",
        ):
            builder._revalidate_owned_site_cache_root(
                handle,
                expected,
                allow_successful_dvc_transition=False,
                context="owned site-cache checkpoint",
            )
    finally:
        for item in reversed(chain):
            item.close()


def test_publication_final_readback_catches_late_main_site_cache_drift_and_rolls_back(
    tmp_path: Path,
) -> None:
    contract = _locked_contract()
    root = _publication_root(tmp_path)
    site_cache = root / ".dvc/tmp/site-cache"
    site_cache.mkdir(parents=True)
    site_cache.chmod(0o700)
    config = root / ".dvc/config.local"
    config.write_text(
        "[core]\n" f"site_cache_dir = {site_cache}\n",
        encoding="utf-8",
    )
    config.chmod(0o600)
    lease = builder._open_main_dvc_site_cache_lease(root)
    stages: list[str] = []

    def validate(stage: str) -> None:
        stages.append(stage)
        lease.revalidate(context=f"publication {stage}")
        if stage == "before_success_return":
            transient = site_cache / "late-transient"
            transient.write_text("drift\n", encoding="utf-8")
            transient.unlink()

    try:
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="site cache root changed",
        ):
            builder.publish_final_certification_bundle(
                repo_root=root,
                contract=contract,
                products=_products(contract),
                publication_validator=validate,
            )
    finally:
        lease.close()
    assert stages[-1] == "after_final_readback"
    assert not (root / contract_module.CERTIFICATION_ROOT).exists()
    assert not (root / "tmp/closure_v1_phase4_final_certification").exists()


@pytest.mark.parametrize("hostile_kind", ["filesystem_root", "external", "symlink"])
def test_main_dvc_site_cache_requires_exact_nofollow_owned_path_before_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hostile_kind: str,
) -> None:
    root = tmp_path / "repo"
    config = root / ".dvc/config.local"
    config.parent.mkdir(parents=True)
    expected = root / ".dvc/tmp/site-cache"
    scanned = False

    def scan(_handle: builder.DirectoryHandle) -> dict[str, tuple[int, ...]]:
        nonlocal scanned
        scanned = True
        return {}

    monkeypatch.setattr(builder, "_scan_private_metadata_tree", scan)
    if hostile_kind == "filesystem_root":
        configured = Path("/")
    elif hostile_kind == "external":
        configured = tmp_path / "external-site-cache"
        configured.mkdir()
    else:
        external = tmp_path / "external-site-cache"
        external.mkdir()
        expected.parent.mkdir(parents=True)
        expected.symlink_to(external, target_is_directory=True)
        configured = expected
    config.write_text(
        "[core]\n" f"site_cache_dir = {configured}\n",
        encoding="utf-8",
    )
    config.chmod(0o600)

    with pytest.raises(
        builder.FinalCertificationBuildError,
        match="site-cache path",
    ) as raised:
        builder._open_main_dvc_site_cache_lease(root)
    assert scanned is False
    assert os.fspath(tmp_path) not in str(raised.value)


def test_postgres_startup_failure_attempts_owned_container_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portable_calls: list[list[str]] = []
    container_id = "c" * 64
    active = False

    def run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        nonlocal active
        actual = list(argv)
        portable = list(kwargs["portable_argv"])
        portable_calls.append(portable)
        if actual[1] == "run":
            active = True
            return builder.CommandResult(
                {"argv": portable, "returncode": 0}, container_id, ""
            )
        if actual[1] == "inspect":
            return builder.CommandResult(
                {"argv": portable, "returncode": 0 if active else 1},
                container_id if active else "",
                "",
            )
        if portable[:2] == ["docker", "exec"]:
            raise builder.FinalCertificationBuildError("synthetic readiness failure")
        if actual[1] == "rm":
            active = False
        return builder.CommandResult({"argv": portable, "returncode": 0}, "", "")

    monkeypatch.setattr(builder, "_run", run)
    with pytest.raises(builder.FinalCertificationBuildError, match="readiness"):
        builder._start_owned_postgres(tmp_path)
    prefixes = [call[:3] for call in portable_calls]
    assert ["docker", "run", "--detach"] in prefixes
    assert ["docker", "exec", "<OWNED_CONTAINER>"] in prefixes
    assert ["docker", "rm", "--force"] in prefixes
    assert active is False


def test_postgres_callback_failure_after_run_cleans_exact_container_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container_id = "d" * 64
    active = False
    removed_targets: list[str] = []

    def run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        nonlocal active
        actual = list(argv)
        portable = list(kwargs["portable_argv"])
        if actual[1] == "run":
            active = True
            return builder.CommandResult(
                {"argv": portable, "returncode": 0}, container_id, ""
            )
        if actual[1] == "inspect":
            return builder.CommandResult(
                {"argv": portable, "returncode": 0 if active else 1},
                container_id if active else "",
                "",
            )
        if actual[1] == "rm":
            removed_targets.append(actual[-1])
            active = False
        return builder.CommandResult({"argv": portable, "returncode": 0}, "", "")

    monkeypatch.setattr(builder, "_run", run)

    def callback(stage: str) -> None:
        if stage == "after_postgres_start":
            raise builder.FinalCertificationBuildError("callback failure")

    with pytest.raises(builder.FinalCertificationBuildError, match="callback failure"):
        builder._start_owned_postgres(
            tmp_path,
            namespace_validator=callback,
        )
    assert removed_targets == [container_id]
    assert active is False


def test_postgres_run_timeout_recovers_and_removes_only_bound_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container_id = "7" * 64
    active = False
    removed_targets: list[str] = []

    def run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        nonlocal active
        actual = list(argv)
        portable = list(kwargs["portable_argv"])
        if actual[1] == "run":
            active = True
            raise builder.FinalCertificationBuildError("synthetic Docker timeout")
        if actual[1] == "inspect":
            return builder.CommandResult(
                {"argv": portable, "returncode": 0 if active else 1},
                container_id if active else "",
                "",
            )
        if actual[1] == "rm":
            assert actual[-1] == container_id
            removed_targets.append(actual[-1])
            active = False
        return builder.CommandResult({"argv": portable, "returncode": 0}, "", "")

    monkeypatch.setattr(builder, "_run", run)
    with pytest.raises(builder.FinalCertificationBuildError, match="Docker timeout"):
        builder._start_owned_postgres(tmp_path)
    assert removed_targets == [container_id]
    assert active is False


def test_postgres_run_timeout_preserves_ambiguous_name_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_id = "8" * 64
    foreign_id = "9" * 64
    active = False
    inspect_after_run = 0
    removed_targets: list[str] = []

    def run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        nonlocal active, inspect_after_run
        actual = list(argv)
        portable = list(kwargs["portable_argv"])
        if actual[1] == "run":
            active = True
            raise builder.FinalCertificationBuildError("synthetic Docker timeout")
        if actual[1] == "inspect":
            if not active:
                return builder.CommandResult(
                    {"argv": portable, "returncode": 1}, "", ""
                )
            inspect_after_run += 1
            identity = first_id if inspect_after_run == 1 else foreign_id
            return builder.CommandResult(
                {"argv": portable, "returncode": 0}, identity, ""
            )
        if actual[1] == "rm":
            removed_targets.append(actual[-1])
        return builder.CommandResult({"argv": portable, "returncode": 0}, "", "")

    monkeypatch.setattr(builder, "_run", run)
    with pytest.raises(builder.FinalCertificationBuildError, match="cleanup failed"):
        builder._start_owned_postgres(tmp_path)
    assert removed_targets == []
    assert active is True


def test_postgres_cleanup_preserves_reused_foreign_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owned_id = "e" * 64
    foreign_id = "f" * 64
    owner = builder.OwnedPostgres(
        name="closure-phase4-cert-" + "a" * 24,
        container_id=owned_id,
    )
    state = "owned"
    removed_targets: list[str] = []

    def run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        nonlocal state
        actual = list(argv)
        portable = list(kwargs["portable_argv"])
        if actual[1] == "inspect":
            target = actual[-1]
            if state == "owned":
                return builder.CommandResult(
                    {"argv": portable, "returncode": 0}, owned_id, ""
                )
            if target == owner.name:
                return builder.CommandResult(
                    {"argv": portable, "returncode": 0}, foreign_id, ""
                )
            return builder.CommandResult(
                {"argv": portable, "returncode": 1}, "", ""
            )
        if actual[1] == "rm":
            removed_targets.append(actual[-1])
            state = "foreign"
        return builder.CommandResult({"argv": portable, "returncode": 0}, "", "")

    monkeypatch.setattr(builder, "_run", run)
    with pytest.raises(builder.FinalCertificationBuildError, match="foreign"):
        builder._stop_owned_postgres(owner)
    assert removed_targets == [owned_id]
    assert foreign_id not in removed_targets


def test_dvc_restore_uses_eight_exact_unit_commands_and_empty_private_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract, payloads = _dvc_contract(tmp_path)
    source = tmp_path / "source"
    clone = tmp_path / "clone"
    cache = tmp_path / "cache"
    site_cache = tmp_path / "site-cache"
    _write_fake_dvc(source)
    clone.mkdir()
    cache.mkdir()
    site_cache.mkdir(mode=0o700)
    _prepare_pointers(clone, contract)
    (clone / ".dvc").mkdir()
    (clone / ".dvc/config.local").write_text("[remote \"private\"]\n")
    (clone / ".dvc/config.local").chmod(0o600)
    commands: list[tuple[str, ...]] = []
    command_environments: list[Mapping[str, str]] = []
    command_pass_fds: list[tuple[int, ...]] = []
    credential = tmp_path / "credential.json"
    credential.write_text("private\n", encoding="utf-8")
    credential_fd = os.open(credential, os.O_RDONLY)

    def run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        portable = tuple(kwargs.get("portable_argv", argv))
        command_environments.append(kwargs["environment"])
        command_pass_fds.append(tuple(kwargs["pass_fds"]))
        if "pull" in portable:
            commands.append(portable)
            spec = next(item for item in contract.dvc_pointers if item.path == portable[-1])
            payload = payloads[Path(spec.output_path).name]
            output = clone / spec.output_path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(payload)
            cache_object = cache / "files/md5" / spec.md5[:2] / spec.md5[2:]
            cache_object.parent.mkdir(parents=True, exist_ok=True)
            cache_object.write_bytes(payload)
            return builder.CommandResult({"argv": list(portable), "returncode": 0}, "", "")
        return builder.CommandResult({"argv": list(portable), "returncode": 0}, "{}", "")

    monkeypatch.setattr(builder, "_run", run)
    try:
        records = builder._restore_dvc_objects(
            source_root=source,
            clone_root=clone,
            cache_root=cache,
            site_cache_root=site_cache,
            installed_configuration=cast(
                builder.InstalledDvcConfiguration,
                SimpleNamespace(
                    pass_fds=(credential_fd,),
                    bind_owned_cache=lambda _path: None,
                    revalidate=lambda **kwargs: None,
                ),
            ),
            contract=contract,
        )
    finally:
        os.close(credential_fd)
    assert len(records) == len(commands) == 8
    assert len(command_environments) == 19
    assert all(env["DVC_NO_ANALYTICS"] == "1" for env in command_environments)
    assert all(
        env["DVC_SITE_CACHE_DIR"] == os.fspath(site_cache)
        for env in command_environments
    )
    assert all(
        env["__PYVENV_LAUNCHER__"].startswith("/proc/self/fd/")
        for env in command_environments
    )
    assert all(credential_fd in descriptors for descriptors in command_pass_fds)
    assert all(len(descriptors) == 4 for descriptors in command_pass_fds)
    assert all(record["pull_command"]["argv"][0] == ".venv/bin/dvc" for record in records)
    assert [command[1:6] for command in commands] == [
        ("pull", "--no-run-cache", "-j", "1", spec.path)
        for spec in contract.dvc_pointers
    ]
    assert [record["directed_status_command"]["argv"] for record in records] == [
        [".venv/bin/dvc", "status", "--json", spec.path]
        for spec in contract.dvc_pointers
    ]
    assert all(record["payload_opened_by_python"] is False for record in records)
    assert all(record["payload_decoded"] is False for record in records)
    assert builder._validate_exact_dvc_cache(cache_root=cache, contract=contract) == {
        "object_count": 8,
        "declared_payload_bytes": sum(spec.size for spec in contract.dvc_pointers),
        "exact_pointer_objects_only": True,
        "content_addressed_paths_from_declared_md5": True,
        "payload_objects_opened_by_python": False,
        "payloads_decoded": False,
    }


def test_global_dvc_status_always_disables_analytics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}
    clone = tmp_path / "clone"
    clone.mkdir()

    def run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        captured.update(kwargs)
        return builder.CommandResult(
            {"argv": list(kwargs["portable_argv"]), "returncode": 0}, "{}", ""
        )

    monkeypatch.setattr(builder, "_run", run)
    _write_fake_dvc(tmp_path)
    assert builder._dvc_status(clone, executable_root=tmp_path) == "{}"
    assert captured["environment"]["DVC_NO_ANALYTICS"] == "1"
    assert captured["environment"]["__PYVENV_LAUNCHER__"].startswith(
        "/proc/self/fd/"
    )
    assert len(captured["pass_fds"]) == 3
    calls: list[str] = []

    def attempted(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        calls.append("attempted")
        raise AssertionError("main DVC runtime/subprocess must not be opened")

    monkeypatch.setattr(builder, "_open_python_script_runtime", attempted)
    monkeypatch.setattr(builder, "_run", attempted)
    with pytest.raises(
        builder.FinalCertificationBuildError,
        match="restricted to the isolated clone",
    ):
        builder._dvc_status(tmp_path, executable_root=tmp_path)
    assert calls == []


def test_isolated_dvc_site_cache_requires_empty_private_0700_directory(
    tmp_path: Path,
) -> None:
    contract, _ = _dvc_contract(tmp_path)
    source = tmp_path / "source"
    clone = tmp_path / "clone"
    cache = tmp_path / "cache"
    site_cache = tmp_path / "site-cache"
    for path in (source, clone, cache, site_cache):
        path.mkdir()
    site_cache.chmod(0o755)
    runtime = cast(
        builder.AnchoredPythonScriptRuntime,
        SimpleNamespace(),
    )
    with pytest.raises(
        builder.FinalCertificationBuildError,
        match="site cache mode drifted",
    ):
        builder._restore_dvc_objects_with_anchored_executable(
            source_root=source,
            clone_root=clone,
            cache_root=cache,
            site_cache_root=site_cache,
            installed_configuration=cast(
                builder.InstalledDvcConfiguration,
                _fake_installed_dvc_configuration(),
            ),
            contract=contract,
            executable=runtime,
        )


def test_dvc_executable_swap_is_detected_after_fd_anchored_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    original = _write_fake_dvc(tmp_path)
    original.write_text("#!/bin/sh\n# owned\nexit 0\n", encoding="utf-8")
    saved = original.with_name("dvc-owned")
    invoked_inode: tuple[int, int] | None = None

    def run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        nonlocal invoked_inode
        executable = Path(list(argv)[1])
        descriptor = int(executable.name)
        metadata = os.fstat(descriptor)
        invoked_inode = (metadata.st_dev, metadata.st_ino)
        original.rename(saved)
        original.write_text("#!/bin/sh\n# foreign\nexit 0\n", encoding="utf-8")
        original.chmod(0o755)
        return builder.CommandResult(
            {"argv": list(kwargs["portable_argv"]), "returncode": 0}, "{}", ""
        )

    expected = original.stat()
    monkeypatch.setattr(builder, "_run", run)
    with pytest.raises(builder.FinalCertificationBuildError, match="binding"):
        builder._dvc_status(clone, executable_root=tmp_path)
    assert invoked_inode == (expected.st_dev, expected.st_ino)
    assert "foreign" in original.read_text()
    assert "owned" in saved.read_text()


def test_dvc_launcher_swap_never_executes_foreign_launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    script = _write_fake_dvc(tmp_path)
    owned_marker = tmp_path / "owned-ran"
    foreign_marker = tmp_path / "foreign-ran"
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(owned_marker)!r}).write_text('owned')\n"
        "print('{}')\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    launcher = tmp_path / ".venv/bin/python"
    saved_launcher = launcher.with_name("python-owned")
    original_run = builder.subprocess.run
    swapped = False

    def swap_then_run(argv: Any, **kwargs: Any) -> Any:
        nonlocal swapped
        if not swapped:
            swapped = True
            launcher.rename(saved_launcher)
            launcher.write_text(
                "#!/bin/sh\n"
                f"printf foreign > {foreign_marker}\n"
                "exit 0\n",
                encoding="utf-8",
            )
            launcher.chmod(0o755)
        return original_run(argv, **kwargs)

    monkeypatch.setattr(builder.subprocess, "run", swap_then_run)
    with pytest.raises(builder.FinalCertificationBuildError, match="launcher/interpreter"):
        builder._dvc_status(clone, executable_root=tmp_path)
    assert owned_marker.read_text() == "owned"
    assert not foreign_marker.exists()


def test_runtime_dvc_version_probe_disables_analytics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    run_root = (
        root
        / "tmp/closure_v1_phase4_final_certification"
        / f"run-{'a' * 32}"
    )
    clone = run_root / "clone"
    site_cache = run_root / "dvc-version-site-cache"
    clone.mkdir(parents=True)
    site_cache.mkdir(mode=0o700)
    calls: list[
        tuple[list[str], list[str], Path, Mapping[str, str] | None]
    ] = []

    def run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        actual = list(argv)
        portable = list(kwargs["portable_argv"])
        cwd = Path(kwargs["cwd"])
        if portable[:2] == [".venv/bin/dvc", "--version"] and cwd == root:
            raise AssertionError("DVC version must never use the main cwd")
        calls.append((actual, portable, cwd, kwargs.get("environment")))
        return builder.CommandResult(
            {"argv": portable, "returncode": 0}, f"{Path(portable[0]).name} 1.0", ""
        )

    monkeypatch.setattr(builder, "_run", run)
    _write_fake_dvc(root)
    ty = root / ".venv/bin/ty"
    ty.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ty.chmod(0o755)
    clone_chain, _ = builder._open_directory_chain(
        Path("/"), clone.relative_to(Path("/")), create_missing=False
    )
    site_cache_chain, _ = builder._open_directory_chain(
        Path("/"), site_cache.relative_to(Path("/")), create_missing=False
    )
    dvc_runtime = builder._open_python_script_runtime(
        root,
        Path(".venv/bin/dvc"),
        context="test retained DVC runtime",
    )
    before_site_cache = builder._stat_identity(site_cache.stat())
    try:
        versions = builder._runtime_versions(
            root,
            dvc_runtime=dvc_runtime,
            dvc_clone_handle=clone_chain[-1],
            dvc_site_cache_handle=site_cache_chain[-1],
        )
        repeated_versions = builder._runtime_versions(
            root,
            dvc_runtime=dvc_runtime,
            dvc_clone_handle=clone_chain[-1],
            dvc_site_cache_handle=site_cache_chain[-1],
        )
        assert repeated_versions == versions
        assert builder._stat_identity(site_cache.stat()) == before_site_cache
        assert not list(site_cache.iterdir())
        successful_call_count = len(calls)
        site_cache.chmod(0o755)
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="owned site cache binding drifted",
        ):
            builder._runtime_versions(
                root,
                dvc_runtime=dvc_runtime,
                dvc_clone_handle=clone_chain[-1],
                dvc_site_cache_handle=site_cache_chain[-1],
            )
        assert len(calls) == successful_call_count
        site_cache.chmod(0o700)

        dvc_script = root / ".venv/bin/dvc"
        retained_script = dvc_script.with_name("dvc-retained")
        dvc_script.rename(retained_script)
        dvc_script.write_text("#!/bin/sh\n# foreign\nexit 0\n", encoding="utf-8")
        dvc_script.chmod(0o755)
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="binding drifted",
        ):
            builder._runtime_versions(
                root,
                dvc_runtime=dvc_runtime,
                dvc_clone_handle=clone_chain[-1],
                dvc_site_cache_handle=site_cache_chain[-1],
            )
        assert len(calls) == successful_call_count
        dvc_script.unlink()
        retained_script.rename(dvc_script)
    finally:
        dvc_runtime.close()
        for chain in (site_cache_chain, clone_chain):
            for handle in reversed(chain):
                handle.close()
    assert set(versions) == {
        "python",
        "dvc",
        "ty",
        "git",
        "poetry",
        "bubblewrap",
        "docker_client",
        "docker_server",
    }
    dvc_calls = [call for call in calls if call[1][0] == ".venv/bin/dvc"]
    assert len(dvc_calls) == 2
    assert dvc_calls[0][0][:2] == dvc_calls[1][0][:2]
    dvc_call = dvc_calls[0]
    assert dvc_call[2] == clone
    assert dvc_call[3] is not None
    assert dvc_call[3]["DVC_NO_ANALYTICS"] == "1"
    assert dvc_call[3]["DVC_SITE_CACHE_DIR"] == os.fspath(site_cache)
    assert dvc_call[3]["__PYVENV_LAUNCHER__"].startswith("/proc/self/fd/")
    assert all(
        cwd != root
        for _, portable, cwd, _ in calls
        if portable[:1] == [".venv/bin/dvc"]
    )
    git_call = next(call for call in calls if call[1] == ["git", "--version"])
    assert git_call[0] == [builder.GIT_EXECUTABLE, "--version"]
    assert git_call[2] == root


def test_sealed_runtime_drift_stops_before_private_config_pull_and_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _locked_contract()
    drifted = dict(contract.expected_runtime_versions)
    drifted["python"] = "Python 9.9.9"
    effects: list[str] = []
    monkeypatch.setattr(builder, "_runtime_versions", lambda *args, **kwargs: drifted)
    with pytest.raises(builder.FinalCertificationBuildError, match="runtime version"):
        placeholder = cast(builder.DirectoryHandle, SimpleNamespace())
        builder._sealed_runtime_versions(
            ROOT,
            contract=contract,
            dvc_runtime=cast(
                builder.AnchoredPythonScriptRuntime, SimpleNamespace()
            ),
            dvc_clone_handle=placeholder,
            dvc_site_cache_handle=placeholder,
        )
        effects.extend(["private_config", "pull", "docker", "tests"])
    assert effects == []


def test_transaction_orders_sealed_runtime_before_and_after_all_effects() -> None:
    source = inspect.getsource(builder.build_phase4_final_certification)
    clone = source.index("_clone_exact_p(")
    runtime_open = source.index('"retained_dvc_runtime_open"')
    before = source.index('"runtime_versions_before_private_config_or_pull"')
    private_config = source.index('"private_dvc_configuration_rebase"')
    version_cache_freeze = source.index(
        'frozen_execution_inventories["DVC version site cache"]'
    )
    restore = source.index("_restore_dvc_objects_with_anchored_executable(")
    after = source.index('"runtime_versions_after_verification"')
    assert clone < runtime_open < before < version_cache_freeze < private_config
    assert private_config < restore < after
    for operation in (
        "_restore_dvc_objects_with_anchored_executable(",
        "_start_owned_postgres(",
        "_run_verification(",
        '"clone_dvc_status_after_verification"',
    ):
        position = source.index(operation)
        assert before < position < after
    assert source.count("dvc_runtime=retained_dvc_runtime") == 2
    assert "executable=retained_dvc_runtime" in source
    assert "_dvc_status_with_executable(" in source
    assert source.count("dvc_clone_handle=clone_handle") == 2
    assert source.count(
        "dvc_site_cache_handle=version_site_cache_handle"
    ) == 2
    assert source.index("dvc_private_pass_fds=()") < private_config
    assert source.index(
        "dvc_private_pass_fds=active_configuration.pass_fds"
    ) > source.index('"clone_dvc_status_after_verification"')
    assert source.index("retained_dvc_runtime.close()") > source.index(
        '"payload_validation"'
    )
    assert source.index("runtime_versions=runtime_before") > after


def test_transaction_retains_original_main_site_cache_lease_through_publication() -> None:
    source = inspect.getsource(builder.build_phase4_final_certification)
    publication = source.index("result = publish_final_certification_bundle(")
    close = source.index("active_main_site_cache_lease.close()")
    assert publication < close
    assert "main_site_cache_lease=active_main_site_cache_lease" in source


@pytest.mark.parametrize(
    ("stderr", "expected_category"),
    [
        (
            "Could not automatically determine credentials; token=RAW_AUTHN "
            "https://storage.invalid/object /home/operator/credential.json",
            "authn",
        ),
        (
            "HTTP 403 Forbidden; RAW_AUTHZ https://storage.invalid/private",
            "authz",
        ),
        (
            "NoSuchKey RAW_MISSING https://storage.invalid/missing-object",
            "remote_object_missing",
        ),
        (
            "connection reset by peer RAW_NETWORK /home/operator/socket",
            "network",
        ),
        (
            "opaque backend failure RAW_NONZERO secret=do-not-retain",
            "nonzero_exit",
        ),
    ],
)
def test_nonzero_command_failure_retains_only_closed_safe_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stderr: str,
    expected_category: str,
) -> None:
    monkeypatch.setattr(
        builder.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=23,
            stdout="RAW_STDOUT_MUST_NOT_SURVIVE",
            stderr=stderr,
        ),
    )
    portable = (
        ".venv/bin/dvc",
        "pull",
        "--no-run-cache",
        "-j",
        "1",
        "data/closure_v1/locked_evaluation/input_history.parquet.dvc",
    )
    with pytest.raises(builder.FinalCertificationBuildError) as raised:
        builder._run(
            ("ignored-runtime",),
            cwd=tmp_path,
            portable_argv=portable,
            failure_stage="directed DVC pull 1",
        )

    expected = builder.CommandFailureEvidence(
        stage="first_directed_dvc_pull",
        sanitized_command=portable,
        returncode=23,
        safe_stderr_category=expected_category,
    )
    assert raised.value.command_failure == expected
    assert raised.value.__cause__ is None
    rendered = str(raised.value)
    assert json.loads(rendered.split(": ", 1)[1]) == expected.as_record()
    for forbidden in (
        "RAW_",
        "RAW_STDOUT_MUST_NOT_SURVIVE",
        "https://",
        "/home/",
        "do-not-retain",
    ):
        assert forbidden not in rendered


def test_cleanup_composite_reports_removed_worktree_truthfully() -> None:
    active = builder._command_failure_error(
        stage="directed DVC pull 1",
        command=(".venv/bin/dvc", "pull", "pointer.dvc"),
        returncode=1,
        stderr="opaque failure",
    )
    composite = builder._execution_cleanup_composite_error(
        active,
        namespace_preserved=False,
    )
    diagnostic = json.loads(str(composite).split(": ", 1)[1])
    assert diagnostic["cleanup"] == {
        "status": "failed_closed",
        "namespace_preserved": False,
        "active_error_was_masked": False,
    }
    assert composite.command_failure is active.command_failure


def test_clone_work_transition_requires_exact_single_directory_link_delta() -> None:
    before = (
        11,
        22,
        100,
        101,
        8,
        0o700,
        (
            "dvc-cache",
            "dvc-site-cache",
            "dvc-version-site-cache",
            "masks",
            "postgres-socket",
            "sandbox-tmp",
        ),
    )
    expected = (
        11,
        22,
        200,
        201,
        9,
        0o700,
        (
            "clone",
            "dvc-cache",
            "dvc-site-cache",
            "dvc-version-site-cache",
            "masks",
            "postgres-socket",
            "sandbox-tmp",
        ),
    )
    builder._require_exact_clone_work_transition(before, expected)

    for drifted in (
        (*expected[:4], 8, *expected[5:]),
        (*expected[:4], 10, *expected[5:]),
        (*expected[:4], 8, 0o755, expected[-1]),
        (*expected[:6], (*expected[-1], "foreign")),
    ):
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="clone transition drifted",
        ):
            builder._require_exact_clone_work_transition(before, drifted)


def _patch_build_through_clone(
    *,
    root: Path,
    contract: contract_module.FinalCertificationContract,
    monkeypatch: pytest.MonkeyPatch,
    inject_foreign_after_registration: bool,
) -> None:
    clean = {
        "head": P_COMMIT,
        "main": P_COMMIT,
        "origin_main": P_COMMIT,
        "origin_head": P_COMMIT,
        "status": "",
        "cached_diff": "",
        "unstaged_diff": "",
    }
    authority = _authority()
    preflight = {
        "status": "ready_to_certify",
        "writes": False,
        "commands_executed": False,
        "execution_commit": P_COMMIT,
        "authority": authority,
        "anchor_inputs": _anchor_records(contract),
        "dvc_pointers": _pointer_records(contract),
        "output_paths": list(contract.output_paths),
        "main_dvc_static_boundary": {
            "main_dvc_status_command_run": False,
            "main_dvc_static_reconstruction_from_git_and_published_pointers": True,
        },
        "local_dvc_remote_configuration": {"present": True},
    }
    later_effects: list[str] = []

    monkeypatch.setattr(builder, "load_contract", lambda **kwargs: contract)
    monkeypatch.setattr(
        builder,
        "check_phase4_final_certification",
        lambda **kwargs: preflight,
    )
    monkeypatch.setattr(builder, "_capture_main_state", lambda path: dict(clean))
    monkeypatch.setattr(builder, "_authority_loader", lambda *args: authority)
    monkeypatch.setattr(
        builder,
        "_sealed_runtime_versions",
        lambda *args, **kwargs: dict(contract.expected_runtime_versions),
    )
    monkeypatch.setattr(
        builder,
        "_open_main_dvc_site_cache_lease",
        lambda root: SimpleNamespace(revalidate=lambda **kwargs: None, close=lambda: None),
    )

    def clone_then_fail(
        *,
        source_root: Path,
        clone_root: Path,
        execution_commit: str,
        namespace_validator: Any,
    ) -> Mapping[str, Any]:
        del source_root, execution_commit
        namespace_validator("before_git_clone")
        clone_root.mkdir()
        (clone_root / ".git").mkdir()
        (clone_root / "tracked.txt").write_text("owned", encoding="utf-8")
        namespace_validator("after_git_clone")
        if inject_foreign_after_registration:
            (clone_root / "foreign.txt").write_text("foreign", encoding="utf-8")
        raise builder.FinalCertificationBuildError("primary post-clone failure")

    monkeypatch.setattr(builder, "_clone_exact_p", clone_then_fail)
    monkeypatch.setattr(
        builder,
        "_install_local_dvc_remote_configuration",
        lambda **kwargs: later_effects.append("config"),
    )
    monkeypatch.setattr(
        builder,
        "_restore_dvc_objects",
        lambda **kwargs: later_effects.append("pull"),
    )

    if inject_foreign_after_registration:
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="temporary cleanup failed closed",
        ):
            builder.build_phase4_final_certification(repo_root=root)
    else:
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="primary post-clone failure",
        ):
            builder.build_phase4_final_certification(repo_root=root)
    assert later_effects == []


def test_post_clone_primary_failure_cleans_registered_clone_exactly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _publication_root(tmp_path)
    _patch_build_through_clone(
        root=root,
        contract=_locked_contract(),
        monkeypatch=monkeypatch,
        inject_foreign_after_registration=False,
    )
    assert not (root / "tmp").exists()


def test_post_clone_cleanup_preserves_unregistered_foreign_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _publication_root(tmp_path)
    _patch_build_through_clone(
        root=root,
        contract=_locked_contract(),
        monkeypatch=monkeypatch,
        inject_foreign_after_registration=True,
    )
    foreign = list(
        (root / "tmp/closure_v1_phase4_final_certification").glob(
            "run-*/clone/foreign.txt"
        )
    )
    assert len(foreign) == 1
    assert foreign[0].read_text(encoding="utf-8") == "foreign"


def test_first_dvc_pull_failure_and_prefreeze_dvc_drift_preserve_composite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _publication_root(tmp_path)
    contract, _ = _dvc_contract(tmp_path)
    clean = {
        "head": P_COMMIT,
        "main": P_COMMIT,
        "origin_main": P_COMMIT,
        "origin_head": P_COMMIT,
        "status": "",
        "cached_diff": "",
        "unstaged_diff": "",
    }
    authority = _authority()
    preflight = {
        "status": "ready_to_certify",
        "writes": False,
        "commands_executed": False,
        "execution_commit": P_COMMIT,
        "authority": authority,
        "anchor_inputs": _anchor_records(contract),
        "dvc_pointers": _pointer_records(contract),
        "output_paths": list(contract.output_paths),
        "main_dvc_static_boundary": {
            "main_dvc_status_command_run": False,
            "main_dvc_static_reconstruction_from_git_and_published_pointers": True,
        },
        "local_dvc_remote_configuration": {"present": True},
    }
    subprocess_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(builder, "load_contract", lambda **kwargs: contract)
    monkeypatch.setattr(
        builder,
        "check_phase4_final_certification",
        lambda **kwargs: preflight,
    )
    monkeypatch.setattr(builder, "_capture_main_state", lambda path: dict(clean))
    monkeypatch.setattr(builder, "_authority_loader", lambda *args: authority)
    monkeypatch.setattr(
        builder,
        "_sealed_runtime_versions",
        lambda *args, **kwargs: dict(contract.expected_runtime_versions),
    )

    def clone_exact_p(
        *,
        source_root: Path,
        clone_root: Path,
        execution_commit: str,
        namespace_validator: Any,
    ) -> Mapping[str, Any]:
        del source_root, execution_commit
        namespace_validator("before_git_clone")
        clone_root.mkdir()
        (clone_root / ".git").mkdir()
        (clone_root / "tracked.txt").write_text("owned", encoding="utf-8")
        _prepare_pointers(clone_root, contract)
        namespace_validator("after_git_clone")
        return {"command": {"argv": ["git", "clone"], "returncode": 0}}

    def install_private_config(
        *, source_root: Path, clone_root: Path
    ) -> SimpleNamespace:
        del source_root
        private_config = clone_root / contract_module.LOCAL_DVC_CONFIG_PATH
        private_config.parent.mkdir(parents=True)
        private_config.write_text("[remote]\n", encoding="utf-8")
        private_config.chmod(0o600)
        return SimpleNamespace(
            public_record={"present": True},
            pass_fds=(),
            bind_owned_cache=lambda _path: None,
            revalidate=lambda **kwargs: None,
            close=lambda: None,
        )

    portable = (
        ".venv/bin/dvc",
        "pull",
        "--no-run-cache",
        "-j",
        "1",
        contract.dvc_pointers[0].path,
    )

    retained_runtime = SimpleNamespace(
        interpreter=SimpleNamespace(
            proc_path="retained-python",
            venv_proc_path="retained-venv",
            fd=0,
            venv_fd=0,
        ),
        script=SimpleNamespace(proc_path="retained-dvc", fd=0),
        revalidate=lambda **kwargs: None,
        close=lambda: None,
    )

    def failed_subprocess(argv: Any, **kwargs: Any) -> Any:
        actual = tuple(argv)
        if "config" in actual:
            private_config = (
                Path(kwargs["cwd"]) / contract_module.LOCAL_DVC_CONFIG_PATH
            )
            private_config.write_text(
                private_config.read_text(encoding="utf-8")
                + "DVC_CONFIG_MUTATION\n",
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "pull" not in actual:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        subprocess_calls.append(actual)
        dvc_tmp = Path(kwargs["cwd"]) / ".dvc/tmp"
        dvc_tmp.mkdir()
        (dvc_tmp / "lock").write_text("DVC_PREFREEZE_RESIDUAL", encoding="utf-8")
        site_cache = Path(kwargs["env"]["DVC_SITE_CACHE_DIR"])
        (site_cache / "repo").mkdir()
        (site_cache / "repo/index").write_text(
            "DVC_SITE_CACHE_RESIDUAL", encoding="utf-8"
        )
        return SimpleNamespace(
            returncode=17,
            stdout="RAW_STDOUT_WITH_/home/operator/private",
            stderr=(
                "Could not automatically determine credentials; token=RAW_TOKEN "
                "https://storage.invalid/private /home/operator/key.json"
            ),
        )

    monkeypatch.setattr(builder, "_clone_exact_p", clone_exact_p)
    monkeypatch.setattr(
        builder,
        "_install_local_dvc_remote_configuration",
        install_private_config,
    )
    monkeypatch.setattr(
        builder,
        "_open_python_script_runtime",
        lambda *args, **kwargs: retained_runtime,
    )
    monkeypatch.setattr(
        builder,
        "_revalidate_retained_dvc_runtime",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        builder,
        "_open_main_dvc_site_cache_lease",
        lambda root: SimpleNamespace(revalidate=lambda **kwargs: None, close=lambda: None),
    )
    monkeypatch.setattr(builder.subprocess, "run", failed_subprocess)

    with pytest.raises(builder.FinalCertificationBuildError) as raised:
        builder.build_phase4_final_certification(repo_root=root)

    diagnostic = json.loads(str(raised.value).split(": ", 1)[1])
    assert diagnostic == {
        "status": "execution_and_cleanup_failed_closed",
        "active_error": {
            "stage": "first_directed_dvc_pull",
            "sanitized_command": list(portable),
            "returncode": 17,
            "safe_stderr_category": "authn",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "cleanup": {
            "status": "failed_closed",
            "namespace_preserved": True,
            "active_error_was_masked": False,
        },
        "retry_authorized": False,
    }
    assert raised.value.command_failure == builder.CommandFailureEvidence(
        stage="first_directed_dvc_pull",
        sanitized_command=portable,
        returncode=17,
        safe_stderr_category="authn",
    )
    assert raised.value.__cause__ is None
    rendered = str(raised.value)
    for forbidden in (
        "RAW_TOKEN",
        "RAW_STDOUT",
        "https://",
        "/home/",
        "storage.invalid",
    ):
        assert forbidden not in rendered
    assert len(subprocess_calls) == 1

    residuals = list(
        (root / "tmp/closure_v1_phase4_final_certification").glob(
            "run-*/clone/.dvc/tmp/lock"
        )
    )
    assert len(residuals) == 1
    assert residuals[0].read_text(encoding="utf-8") == "DVC_PREFREEZE_RESIDUAL"
    assert (
        residuals[0].parent.parent / "config.local"
    ).read_text(encoding="utf-8").count("DVC_CONFIG_MUTATION") == 2
    site_cache_residuals = list(
        (root / "tmp/closure_v1_phase4_final_certification").glob(
            "run-*/dvc-site-cache/repo/index"
        )
    )
    assert len(site_cache_residuals) == 1
    assert site_cache_residuals[0].read_text(encoding="utf-8") == (
        "DVC_SITE_CACHE_RESIDUAL"
    )
    version_site_caches = list(
        (root / "tmp/closure_v1_phase4_final_certification").glob(
            "run-*/dvc-version-site-cache"
        )
    )
    assert len(version_site_caches) == 1
    assert stat.S_IMODE(version_site_caches[0].stat().st_mode) == 0o700
    assert not list(version_site_caches[0].iterdir())
    for output in contract.output_paths:
        assert not os.path.lexists(root / output)


def test_git_queries_ignore_path_and_clone_records_portable_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "foreign-git-ran"
    foreign = fake_bin / "git"
    foreign.write_text(
        "#!/bin/sh\nprintf foreign > \"$FOREIGN_GIT_MARKER\"\nexit 0\n",
        encoding="utf-8",
    )
    foreign.chmod(0o755)
    monkeypatch.setenv("PATH", os.fspath(fake_bin))
    monkeypatch.setenv("FOREIGN_GIT_MARKER", os.fspath(marker))
    assert builder._git(ROOT, "--version").startswith("git version ")
    assert not marker.exists()

    actual_clone: list[str] = []

    def fake_git(root: Path, *args: str) -> str:
        if args == ("config", "--get", "remote.origin.url"):
            return "opaque-origin"
        if args == ("rev-parse", "HEAD"):
            return P_COMMIT
        if args[0] == "status":
            return ""
        if args[0] == "show":
            return H_COMMIT
        raise AssertionError(args)

    def fake_run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        actual_clone.extend(argv)
        portable = list(kwargs["portable_argv"])
        return builder.CommandResult({"argv": portable, "returncode": 0}, "", "")

    monkeypatch.setattr(builder, "_git", fake_git)
    monkeypatch.setattr(builder, "_run", fake_run)
    record = builder._clone_exact_p(
        source_root=ROOT,
        clone_root=tmp_path / "clone",
        execution_commit=P_COMMIT,
    )
    assert actual_clone[0] == builder.GIT_EXECUTABLE
    assert record["command"]["argv"][0] == "git"


def test_bwrap_effect_sources_are_retained_fd_paths_not_mutable_names(
    tmp_path: Path,
) -> None:
    contract = _locked_contract()
    clone_path = tmp_path / "clone"
    sandbox_path = tmp_path / "sandbox"
    socket_path = tmp_path / "socket"
    mask_path = tmp_path / "masks"
    for path in (clone_path, sandbox_path, socket_path, mask_path):
        path.mkdir()
    for prefix in builder.SANDBOX_MASKED_FORBIDDEN_PREFIXES:
        (clone_path / prefix).mkdir(parents=True, exist_ok=True)
    for spec in contract.dvc_pointers:
        output = clone_path / spec.output_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"payload")
    private_config = clone_path / contract_module.LOCAL_DVC_CONFIG_PATH
    private_config.parent.mkdir(parents=True, exist_ok=True)
    private_config.write_text("private")
    handles: list[builder.DirectoryHandle] = []
    runtime: builder.VerificationRuntimeLease | None = None
    try:
        for path in (clone_path, sandbox_path, socket_path, mask_path):
            chain, _ = builder._open_directory_chain(
                path, Path("."), create_missing=False
            )
            assert len(chain) == 1
            handles.append(chain[0])
        clone, sandbox, socket_handle, masks = handles
        builder._prepare_masks(masks)
        runtime = builder._open_verification_runtime(
            source_root=ROOT,
            clone=clone,
            sandbox=sandbox,
            socket_handle=socket_handle,
            mask_root=masks,
        )
        real, template = builder._make_bwrap_prefix(
            runtime=runtime,
            contract=contract,
        )
        assert real[0].startswith("/proc/self/fd/")
        bind_sources = {
            real[index + 2]: real[index + 1]
            for index, token in enumerate(real[:-2])
            if token in {"--ro-bind", "--bind"}
        }
        retained_destinations = {
            "/workspace",
            "/workspace/.venv",
            "/cert-poetry",
            "/cert-python",
            "/cert-ty",
            "/cert-poetry-python",
            "/cert-poetry-script",
            "/workspace/tmp",
            builder.DB_SOCKET_ROOT,
        }
        retained_destinations.update(
            destination
            for destination in bind_sources
            if destination.startswith("/workspace/")
            and destination not in {"/workspace/.venv", "/workspace/tmp"}
        )
        assert all(
            bind_sources[destination].startswith("/proc/self/fd/")
            for destination in retained_destinations
        )
        assert "<OWNED_CLONE>" in template
        assert "<RETAINED_SYSTEM_PYTHON>" in template
        inherited = set(runtime.pass_fds)
        for destination in retained_destinations:
            inherited_fd = int(Path(bind_sources[destination]).name)
            assert inherited_fd in inherited

        saved_clone = tmp_path / "clone-owned"
        clone_path.rename(saved_clone)
        clone_path.mkdir()
        (clone_path / "foreign").write_text("foreign")
        clone_fd = int(Path(bind_sources["/workspace"]).name)
        assert "foreign" not in os.listdir(clone_fd)
        (clone_path / "foreign").unlink()
        clone_path.rmdir()
        saved_clone.rename(clone_path)
    finally:
        if runtime is not None:
            runtime.close()
        for handle in reversed(handles):
            handle.close()


def test_post_verification_clone_status_rejects_suffix_ambiguity() -> None:
    builder._require_clean_clone_status("")
    with pytest.raises(builder.FinalCertificationBuildError, match="Git-visible"):
        builder._require_clean_clone_status(
            "?? evil/reports/closure_v1/09_planning/planning_origin_deltas.parquet"
        )


def test_dvc_restore_never_opens_or_reads_parquet_or_cache_payloads_in_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract, payloads = _dvc_contract(tmp_path)
    source = tmp_path / "source"
    clone = tmp_path / "clone"
    cache = tmp_path / "cache"
    site_cache = tmp_path / "site-cache"
    _write_fake_dvc(source)
    clone.mkdir()
    cache.mkdir()
    site_cache.mkdir(mode=0o700)
    _prepare_pointers(clone, contract)
    (clone / ".dvc").mkdir()
    (clone / ".dvc/config.local").write_text("[remote \"private\"]\n")
    (clone / ".dvc/config.local").chmod(0o600)
    monkeypatch.setattr(
        builder.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=b"", stderr=b""
        ),
    )

    forbidden = {
        *(clone / spec.output_path for spec in contract.dvc_pointers),
        *(
            cache / "files/md5" / spec.md5[:2] / spec.md5[2:]
            for spec in contract.dvc_pointers
        ),
    }
    original_open = os.open
    original_read = os.read
    forbidden_accesses: list[str] = []

    def guarded_open(path: Any, *args: Any, **kwargs: Any) -> int:
        try:
            candidate = Path(os.fsdecode(os.fspath(path)))
        except TypeError:
            candidate = Path(".")
        if candidate in forbidden:
            forbidden_accesses.append(candidate.as_posix())
            raise AssertionError("Python opened a restored/cache payload")
        return original_open(path, *args, **kwargs)

    def guarded_read(descriptor: int, length: int) -> bytes:
        try:
            candidate = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
        except OSError:
            candidate = Path(".")
        if candidate in forbidden:
            forbidden_accesses.append(candidate.as_posix())
            raise AssertionError("Python read a restored/cache payload")
        return original_read(descriptor, length)

    monkeypatch.setattr(builder.os, "open", guarded_open)
    monkeypatch.setattr(builder.os, "read", guarded_read)

    def run(argv: Any, **kwargs: Any) -> builder.CommandResult:
        portable = tuple(kwargs.get("portable_argv", argv))
        if "pull" in portable:
            spec = next(
                item for item in contract.dvc_pointers if item.path == portable[-1]
            )
            payload = payloads[Path(spec.output_path).name]
            output = clone / spec.output_path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(payload)
            cache_object = cache / "files/md5" / spec.md5[:2] / spec.md5[2:]
            cache_object.parent.mkdir(parents=True, exist_ok=True)
            cache_object.write_bytes(payload)
            return builder.CommandResult(
                {"argv": list(portable), "returncode": 0}, "", ""
            )
        return builder.CommandResult(
            {"argv": list(portable), "returncode": 0}, "{}", ""
        )

    monkeypatch.setattr(builder, "_run", run)
    records = builder._restore_dvc_objects(
        source_root=source,
        clone_root=clone,
        cache_root=cache,
        site_cache_root=site_cache,
        installed_configuration=cast(
            builder.InstalledDvcConfiguration,
            _fake_installed_dvc_configuration(),
        ),
        contract=contract,
    )
    assert len(records) == 8
    assert forbidden_accesses == []


def test_dvc_cache_and_payload_metadata_drift_fail_closed(tmp_path: Path) -> None:
    contract, payloads = _dvc_contract(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    for spec in contract.dvc_pointers:
        payload = payloads[Path(spec.output_path).name]
        path = cache / "files/md5" / spec.md5[:2] / spec.md5[2:]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    (cache / "extra").write_text("drift")
    with pytest.raises(builder.FinalCertificationBuildError, match="inventory"):
        builder._validate_exact_dvc_cache(cache_root=cache, contract=contract)

    payload = tmp_path / "payload.parquet"
    payload.write_bytes(b"wrong")
    with pytest.raises(builder.FinalCertificationBuildError, match="size"):
        builder._restored_payload_identity(
            payload, expected_size=99, context="restored payload"
        )


def test_authority_loader_projects_hashes_without_raw_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _locked_contract()
    fake = {
        **_authority(),
        "authority_bytes": b"authority",
        "manifest_bytes": b"manifest",
    }
    monkeypatch.setattr(builder, "load_effective_authority", lambda *args, **kwargs: fake)
    result = builder._authority_loader(ROOT, contract)
    assert result["authority_bytes"] == len(b"authority")
    assert result["manifest_bytes"] == len(b"manifest")
    assert {
        field: result[field]
        for field in (
            "p_cert_commit",
            "h_cert_commit",
            "p4_cert_commit",
            "h4_cert_commit",
            "p3_cert_commit",
            "h3_cert_commit",
            "p2_cert_commit",
            "h2_cert_commit",
            "p1_cert_commit",
            "h1_cert_commit",
        )
    } == {
        field: fake[field]
        for field in (
            "p_cert_commit",
            "h_cert_commit",
            "p4_cert_commit",
            "h4_cert_commit",
            "p3_cert_commit",
            "h3_cert_commit",
            "p2_cert_commit",
            "h2_cert_commit",
            "p1_cert_commit",
            "h1_cert_commit",
        )
    }
    assert not any(isinstance(value, bytes) for value in result.values())

    for field in (
        "p_cert_commit",
        "h_cert_commit",
        "p4_cert_commit",
        "h4_cert_commit",
        "p3_cert_commit",
        "h3_cert_commit",
        "p2_cert_commit",
        "h2_cert_commit",
        "p1_cert_commit",
        "h1_cert_commit",
    ):
        incomplete = dict(fake)
        incomplete.pop(field)
        monkeypatch.setattr(
            builder,
            "load_effective_authority",
            lambda *args, payload=incomplete, **kwargs: payload,
        )
        with pytest.raises(
            builder.FinalCertificationBuildError,
            match="authority commit binding",
        ):
            builder._authority_loader(ROOT, contract)


def test_check_only_is_non_writing_and_requires_effective_p_cert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    contract = _locked_contract()
    anchors, pointers = _static_boundary_records(contract)
    clean = {
        "head": P_COMMIT,
        "main": P_COMMIT,
        "origin_main": P_COMMIT,
        "origin_head": P_COMMIT,
        "status": "",
        "cached_diff": "",
        "unstaged_diff": "",
    }
    monkeypatch.setattr(builder, "load_contract", lambda **kwargs: contract)
    monkeypatch.setattr(builder, "_capture_main_state", lambda path: clean)
    monkeypatch.setattr(
        builder,
        "_git",
        lambda *args: f"{P_COMMIT}\trefs/heads/main",
    )
    dvc_calls: list[str] = []

    def reject_dvc(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        dvc_calls.append("attempted")
        raise AssertionError("check-only must not invoke DVC")

    monkeypatch.setattr(builder, "_dvc_status", reject_dvc)
    monkeypatch.setattr(builder, "_run", reject_dvc)
    monkeypatch.setattr(builder.subprocess, "run", reject_dvc)
    monkeypatch.setattr(
        builder,
        "_open_main_dvc_site_cache_lease",
        lambda root: SimpleNamespace(revalidate=lambda **kwargs: None, close=lambda: None),
    )
    monkeypatch.setattr(
        builder,
        "validate_local_dvc_remote_configuration",
        lambda **kwargs: {"present": True},
    )
    monkeypatch.setattr(
        builder,
        "collect_anchor_input_records",
        lambda *args, **kwargs: copy.deepcopy(anchors),
    )
    monkeypatch.setattr(
        builder,
        "collect_dvc_pointer_records",
        lambda *args, **kwargs: copy.deepcopy(pointers),
    )
    before = list(root.iterdir())
    result = builder.check_phase4_final_certification(
        repo_root=root,
        authority_validator=lambda path, sealed: _authority(),
    )
    assert result["status"] == "ready_to_certify"
    assert result["writes"] is False
    assert result["main_dvc_static_boundary"]["main_dvc_status_command_run"] is False
    assert (
        result["main_dvc_static_boundary"][
            "main_dvc_static_reconstruction_from_git_and_published_pointers"
        ]
        is True
    )
    assert "main_dvc_status" not in result
    assert dvc_calls == []
    assert list(root.iterdir()) == before


class _Item:
    def __init__(self, nodeid: str) -> None:
        self.nodeid = nodeid
        self.markers: list[Any] = []

    def add_marker(self, marker: Any) -> None:
        self.markers.append(marker)


def test_pytest_collection_hook_enforces_digest_and_exact_skip_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nodes = ("tests/test_alpha.py::test_pass", "tests/test_beta.py::test_skip")
    contract = _locked_contract(nodes=nodes)
    monkeypatch.setenv(builder.PLUGIN_MODE_ENV, builder.PUBLIC_SUITE_KIND)
    monkeypatch.setenv(builder.PLUGIN_ROOT_ENV, os.fspath(ROOT))
    monkeypatch.setattr(builder, "load_contract", lambda **kwargs: contract)
    items = [_Item(node) for node in nodes]
    builder.pytest_collection_modifyitems(None, items)
    assert not items[0].markers
    assert len(items[1].markers) == 1

    with pytest.raises(builder.FinalCertificationBuildError, match="missing"):
        builder.pytest_collection_modifyitems(None, items[:1])


def test_e2e_collection_hook_is_exact_and_does_not_add_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _locked_contract()
    monkeypatch.setenv(builder.PLUGIN_MODE_ENV, builder.E2E_SUITE_KIND)
    monkeypatch.setenv(builder.PLUGIN_ROOT_ENV, os.fspath(ROOT))
    monkeypatch.setattr(builder, "load_contract", lambda **kwargs: contract)
    items = [_Item(node) for node in contract.test_suite.e2e_nodes]
    builder.pytest_collection_modifyitems(None, items)
    assert all(not item.markers for item in items)
    with pytest.raises(builder.FinalCertificationBuildError, match="E2E"):
        builder.pytest_collection_modifyitems(None, items[:-1])


def test_public_and_e2e_commands_are_exact_and_do_not_run_scientific_stages() -> None:
    contract = _locked_contract()
    public = builder._public_command(contract)
    e2e = builder._e2e_command(contract)
    assert tuple(contract.test_suite.selectors) == public[3 : 3 + len(contract.test_suite.selectors)]
    assert tuple(contract.test_suite.e2e_nodes) == e2e[3 : 3 + len(contract.test_suite.e2e_nodes)]
    rendered = " ".join((*public, *e2e)).lower()
    assert "e0-u" not in rendered
    assert "--build" not in rendered
    assert "--execute" not in rendered
    assert "dvc" not in rendered


def test_public_environment_activates_safe_historical_e10_compatibility() -> None:
    public = builder._suite_environment(builder.PUBLIC_SUITE_KIND)
    assert public["CLOSURE_E10_OUTCOME_GUARD"] == "1"
    assert public["CLOSURE_E10_REPO_ROOT"] == "/workspace"
    assert public["CLOSURE_E10_SUITE_KIND"] == "closure_phase3_public"
    e2e = builder._suite_environment(builder.E2E_SUITE_KIND)
    assert "CLOSURE_E10_SUITE_KIND" not in e2e


def test_process_guard_allows_safe_git_status_and_owned_local_fixtures_only() -> None:
    builder._guard_process(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--",
            ":(exclude)private/**",
        ],
        "/workspace",
    )
    builder._guard_process(["git", "init", "--quiet"], "/tmp/fixture")
    builder._guard_process(["git", "push", "origin", "main"], "/tmp/fixture")
    builder._guard_process(
        ["/usr/bin/env", "-i", "LANG=C", ".venv/bin/python", "-B", "-c", "pass"],
        "/workspace",
    )
    with pytest.raises(builder.FinalCertificationBuildError, match="mutation"):
        builder._guard_process(["git", "push", "origin", "main"], "/workspace")
    with pytest.raises(builder.FinalCertificationBuildError, match="prohibited"):
        builder._guard_process(
            ["git", "show", "HEAD:private/FULL.md"], "/workspace"
        )
    with pytest.raises(builder.FinalCertificationBuildError, match="DVC"):
        builder._guard_process(
            ["/usr/bin/env", "-i", ".venv/bin/dvc", "status"], "/workspace"
        )
