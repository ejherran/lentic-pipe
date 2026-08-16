from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from src.experiments import lock_closure_e0_u_activation as activation
from src.experiments import run_closure_benchmark as runner


def _scope(path: str, status: str = "A") -> dict[str, Any]:
    return {
        "path": path,
        "status": status,
        "mode": "100644",
        "bytes": 1,
        "sha256": "a" * 64,
    }


def _material(paths: list[str]) -> dict[str, Any]:
    heavy = sorted(paths[:4])
    direct = sorted(paths[4:])
    return {
        "sealed_batch_contract_sha256": "b" * 64,
        "expected_artifact_paths_sha256": "c" * 64,
        "expected_publication_order_sha256": "d" * 64,
        "runner_source_record": {"path": activation.RUNNER_PATH.as_posix()},
        "context_builder_source_record": {
            "source_path": "src/experiments/closure_phase3_context.py"
        },
        "component_source_records": [{"status": "ready"}] * 10,
        "support_source_records": [{"status": "ready"}] * 3,
        "runtime_environment_record": {"status": "sealed"},
        "dvc_policy": {
            "direct_git_artifact_paths": direct,
            "dvc_pointer_paths": sorted(path + ".dvc" for path in heavy),
            "heavy_artifact_paths": heavy,
            "dvc_add_after_success_only": True,
            "dvc_push_after_audit_only": True,
            "implicit_dvc_forbidden": True,
        },
    }


def _overlay_record() -> dict[str, Any]:
    return {
        "manifest": {
            "path": activation.PHASE3_OVERLAY_MANIFEST_PATH,
            "bytes": 101,
            "sha256": "a" * 64,
        },
        "physical_outputs": [
            {
                "path": path,
                "bytes": 202 + index,
                "sha256": str(index + 1) * 64,
            }
            for index, path in enumerate(activation.PHASE3_OVERLAY_OUTPUT_PATHS)
        ],
    }


def _deep_validation_receipt(
    *,
    h_commit: str = "1" * 40,
    overlay_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overlay = _overlay_record() if overlay_record is None else overlay_record
    sources = [
        {
            "role": role,
            "path": path,
            "bytes": 300 + index,
            "sha256": f"{index + 3:064x}",
        }
        for index, (role, path) in enumerate(
            activation.PHASE3_OVERLAY_SOURCE_IDENTITIES
        )
    ]
    return {
        "schema_version": "closure_phase3_input_overlay_deep_validation_v1",
        "status": "passed",
        "experiment_id": "closure_v1",
        "surface_id": "closure_v1_phase3_input_overlay",
        "gate": "pre_E0-U",
        "expected_h_commit": h_commit,
        "builder_source": {
            "role": "phase3_input_overlay_builder",
            "path": activation.PHASE3_OVERLAY_BUILDER_PATH.as_posix(),
            "bytes": 1234,
            "sha256": "f" * 64,
        },
        "source_inputs": sources,
        "source_input_count": 27,
        "source_inputs_sha256": activation._sha256_bytes(
            activation._canonical_json_bytes(sources)
        ),
        "manifest": copy.deepcopy(overlay["manifest"]),
        "physical_outputs": copy.deepcopy(overlay["physical_outputs"]),
        "checkpoint_count": 25,
        "state_dict_array_count": 195,
        "warmup_row_count": 88,
        "warmup_site_count": 88,
        "npz_regenerated_byte_equality": True,
        "warmup_regenerated_byte_equality": True,
        "manifest_regenerated_byte_equality": True,
        "checkpoint_identity_revalidated": True,
        "numpy_torch_parity_recomputed": True,
        "warmup_projection_recomputed": True,
        "history_projection": list(activation.PHASE3_OVERLAY_HISTORY_PROJECTION),
        "panel_projection": list(activation.PHASE3_OVERLAY_PANEL_PROJECTION),
        "projection_contains_chlorophyll": False,
        "projection_contains_target": False,
        "opened_outcome_path_count": 0,
        "opened_target_path_count": 0,
        "writes_performed": False,
    }


def _builder_git_record() -> dict[str, Any]:
    return {
        "path": activation.PHASE3_OVERLAY_BUILDER_PATH.as_posix(),
        "bytes": 1234,
        "sha256": "f" * 64,
        "mode": "100644",
    }


def test_overlay_preflight_record_is_exact_manifest_and_two_payloads() -> None:
    record = _overlay_record()
    assert activation._validate_overlay_preflight_record(record) == record

    for drifted in (
        {**record, "physical_outputs": record["physical_outputs"][:-1]},
        {
            **record,
            "manifest": {**record["manifest"], "sha256": "A" * 64},
        },
        {
            **record,
            "physical_outputs": [
                {**record["physical_outputs"][0], "path": "wrong"},
                record["physical_outputs"][1],
            ],
        },
    ):
        with pytest.raises(activation.ActivationLockError, match="preflight result"):
            activation._validate_overlay_preflight_record(drifted)


def test_deep_overlay_receipt_is_exact_and_rejects_count_or_order_drift() -> None:
    overlay_record = _overlay_record()
    receipt = _deep_validation_receipt(overlay_record=overlay_record)
    assert activation._validate_phase3_overlay_deep_validation(
        receipt,
        expected_h_commit="1" * 40,
        expected_builder_record=_builder_git_record(),
        expected_overlay_record=overlay_record,
    ) == receipt

    checkpoint_24 = {**receipt, "checkpoint_count": 24}
    arrays_194 = {**receipt, "state_dict_array_count": 194}
    warmup_87 = {**receipt, "warmup_row_count": 87}
    reordered = copy.deepcopy(receipt)
    reordered["source_inputs"][0], reordered["source_inputs"][1] = (
        reordered["source_inputs"][1],
        reordered["source_inputs"][0],
    )
    reordered["source_inputs_sha256"] = activation._sha256_bytes(
        activation._canonical_json_bytes(reordered["source_inputs"])
    )
    for drifted in (checkpoint_24, arrays_194, warmup_87, reordered):
        with pytest.raises(
            activation.ActivationLockError,
            match="deep-validation",
        ):
            activation._validate_phase3_overlay_deep_validation(
                drifted,
                expected_h_commit="1" * 40,
                expected_builder_record=_builder_git_record(),
                expected_overlay_record=overlay_record,
            )


def test_source_namespace_can_be_bound_to_exact_git_bytes(tmp_path: Path) -> None:
    path = Path("sealed_builder.py")
    payload = b"VALUE = 7\n"
    (tmp_path / path).write_bytes(payload)
    record = {
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": activation._sha256_bytes(payload),
        "mode": "100644",
    }
    namespace = activation._load_source_namespace(
        path,
        repo_root=tmp_path,
        module_name="closure_activation_authenticated_source",
        expected_git_record=record,
    )
    assert namespace["VALUE"] == 7

    with pytest.raises(activation.ActivationLockError, match="differs from Git"):
        activation._load_source_namespace(
            path,
            repo_root=tmp_path,
            module_name="closure_activation_drifted_source",
            expected_git_record={**record, "sha256": "0" * 64},
        )


def test_activation_preflight_requires_git_published_e10_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topology = {"h_commit": "1" * 40, "p_commit": "2" * 40}
    overlay_record = _overlay_record()
    deep_receipt = _deep_validation_receipt(overlay_record=overlay_record)
    contract: dict[str, Any] = {}
    material = {
        "sealed_batch_contract_sha256": activation._sha256_bytes(
            activation._canonical_json_bytes(contract)
        )
    }
    authority = {"_validate_phase3_overlay_bundle": lambda *_args: overlay_record}
    calls: list[dict[str, Any]] = []
    deep_calls: list[dict[str, Any]] = []

    def validate_overlay(**kwargs: Any) -> dict[str, Any]:
        deep_calls.append(kwargs)
        return deep_receipt

    def load_evidence(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "public_tests_xml": b"tests",
            "test_report": "report",
            "openapi": {},
            "openapi_contract_report": "contract",
            "end_to_end_report": "e2e",
            "environment": {},
        }

    runner_module = ModuleType("closure_phase3_activation_runner")
    runner_module.__dict__["EXPECTED_ARTIFACT_PATHS"] = ()
    runner_module.__dict__["EXPECTED_ARTIFACT_FORMATS"] = {}
    monkeypatch.setitem(
        sys.modules,
        "closure_phase3_activation_runner",
        runner_module,
    )
    monkeypatch.setattr(activation, "_topology", lambda **_kwargs: topology)
    monkeypatch.setattr(
        activation,
        "_capture_material",
        lambda **_kwargs: (material, contract, authority),
    )
    def load_namespace(path: Path, **_kwargs: Any) -> dict[str, Any]:
        if path == activation.PHASE3_OVERLAY_BUILDER_PATH:
            return {"validate_materialized_phase3_input_overlay": validate_overlay}
        if path == activation.E10_SOURCE_EVIDENCE_PATH:
            return {"load_closure_e10_software_evidence": load_evidence}
        raise AssertionError(f"unexpected namespace: {path}")

    monkeypatch.setattr(activation, "_load_source_namespace", load_namespace)
    monkeypatch.setattr(
        activation,
        "_git_blob_record",
        lambda *_args, **_kwargs: _builder_git_record(),
    )
    monkeypatch.setattr(activation, "_manifest", lambda **_kwargs: {"ok": True})

    value, observed_topology = activation._expected_manifest(
        repo_root=tmp_path,
        published_u=False,
        verify_remote=True,
    )

    assert value == {"ok": True}
    assert observed_topology == topology
    assert deep_calls == [
        {"repo_root": tmp_path, "expected_h_commit": "1" * 40}
    ]
    assert calls == [
        {
            "repo_root": tmp_path,
            "expected_h_commit": "1" * 40,
            "require_git_publication": True,
        }
    ]


def test_manifest_is_exact_and_authority_validated() -> None:
    paths = [f"reports/closure_v1/result_{index}.csv" for index in range(52)]
    formats = {path: ("parquet" if index < 4 else "csv") for index, path in enumerate(paths)}
    calls: list[str] = []

    def validate_shape(value: Any) -> Any:
        calls.append("shape")
        assert set(value) == set(activation._load_source_namespace(
            activation.AUTHORITY_PATH,
            repo_root=activation.PROJECT_ROOT,
            module_name="closure_activation_test_authority",
        )["ACTIVATION_MANIFEST_KEYS"])
        return value

    def validate_dvc(value: Any, expected: Any, observed_formats: Any) -> Any:
        calls.append("dvc")
        assert tuple(expected) == tuple(paths)
        assert dict(observed_formats) == formats
        return value

    topology = {
        "h_commit": "1" * 40,
        "p_commit": "2" * 40,
        "h_scope": [
            _scope("src/experiments/closure_e0_u_authority.py"),
            _scope("src/experiments/closure_phase3_context.py"),
            _scope("src/experiments/run_closure_benchmark.py", "M"),
        ],
        "p_scope": [_scope(path) for path in activation.EXPECTED_P_SCOPE_PATHS],
    }
    manifest = activation._manifest(
        topology=topology,
        material=_material(paths),
        authority={
            "_validate_activation_without_contract": validate_shape,
            "_validate_dvc_policy": validate_dvc,
        },
        phase3_overlay_deep_validation=_deep_validation_receipt(),
        expected_artifact_paths=paths,
        expected_artifact_formats=formats,
    )
    assert calls == ["shape", "dvc"]
    assert manifest["base_r_commit"] == activation.BASE_R_COMMIT
    assert manifest["h_commit"] == "1" * 40
    assert manifest["p_commit"] == "2" * 40
    assert manifest["phase3_overlay_deep_validation"]["checkpoint_count"] == 25
    assert manifest["execution_id"] == "closure-v1-e0-u-" + "2" * 16 + "-" + "b" * 16
    payload = activation._canonical_json_bytes(manifest)
    assert payload.endswith(b"\n")
    assert activation._canonical_json_bytes(json.loads(payload)) == payload

    receipt_payload = activation.ATTEMPT_1_FAILURE_RECEIPT_PATH.read_bytes()
    receipt = json.loads(receipt_payload)
    recovery_material = {
        **_material(paths),
        "recovery_attempt": "recovery-attempt-1",
        "attempt_ordinal": 2,
        "first_attempt": False,
        "sealed_recovery_batch_command": activation.RECOVERY_SEALED_BATCH_COMMAND,
        "recovery_guard_path": (
            "tmp/closure_v1_e0_u_recovery_1/sealed_batch.guard"
        ),
        "outcome_access_log_prefix": {
            "path": activation.ACCESS_LOG_PATH.as_posix(),
            "bytes": activation.ATTEMPT_1_ACCESS_LOG_BYTES,
            "sha256": activation.ATTEMPT_1_ACCESS_LOG_SHA256,
            "record_count": 1,
            "first_execution_id": activation.ATTEMPT_1_EXECUTION_ID,
        },
    }
    recovery_topology = {
        "r_commit": activation.BASE_R_COMMIT,
        "h1_commit": activation.HISTORICAL_H1_COMMIT,
        "p1_commit": activation.HISTORICAL_P1_COMMIT,
        "u1_commit": activation.HISTORICAL_U1_COMMIT,
        "h2_commit": "3" * 40,
        "p2_commit": "4" * 40,
        "h2_scope": [
            _scope(path, status)
            for path, status in activation.EXPECTED_RECOVERY_H_SCOPE
        ],
        "p2_scope": [
            _scope(path) for path in activation.EXPECTED_RECOVERY_P_SCOPE_PATHS
        ],
    }

    def validate_recovery_shape(value: Any) -> Any:
        authority_namespace = activation._load_source_namespace(
            activation.AUTHORITY_PATH,
            repo_root=activation.PROJECT_ROOT,
            module_name="closure_recovery_activation_test_authority",
        )
        assert set(value) == set(
            authority_namespace["RECOVERY_ACTIVATION_MANIFEST_KEYS"]
        )
        return value

    recovery_manifest = activation._recovery_manifest(
        repo_root=activation.PROJECT_ROOT,
        topology=recovery_topology,
        material=recovery_material,
        authority={
            "_validate_recovery_activation_without_contract": (
                validate_recovery_shape
            ),
            "_validate_dvc_policy": validate_dvc,
        },
        authority_source_record={"path": activation.AUTHORITY_PATH.as_posix()},
        receipt=receipt,
        receipt_record={
            "path": activation.ATTEMPT_1_FAILURE_RECEIPT_PATH.as_posix(),
            "bytes": len(receipt_payload),
            "sha256": activation._sha256_bytes(receipt_payload),
        },
        recovery_source_records=[
            {
                "path": path,
                "bytes": 1,
                "sha256": "a" * 64,
                "mode": 0o644,
            }
            for path in (
                activation.RECOVERY_ACTIVATION_SCHEMA_PATH.as_posix(),
                activation.RECOVERY_DOCUMENT_PATH.as_posix(),
                activation.ATTEMPT_1_FAILURE_RECEIPT_PATH.as_posix(),
                activation.RECOVERY_COMMAND_PATH.as_posix(),
                "src/experiments/lock_closure_e0_u_activation.py",
            )
        ],
        phase3_overlay_deep_validation=_deep_validation_receipt(
            h_commit=activation.HISTORICAL_H1_COMMIT
        ),
        expected_artifact_paths=paths,
        expected_artifact_formats=formats,
    )
    assert recovery_manifest["attempt_ordinal"] == 2
    assert recovery_manifest["first_attempt"] is False
    assert recovery_manifest["historical_chain"]["u1_commit"] == (
        activation.HISTORICAL_U1_COMMIT
    )
    assert recovery_manifest["recovery_chain"]["h2_commit"] == "3" * 40
    assert recovery_manifest["recovery_chain"]["p2_commit"] == "4" * 40
    assert recovery_manifest["attempt_1_failure_receipt"]["decoded"] == receipt


def test_topology_separates_configured_origin_from_live_https(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r_commit = activation.BASE_R_COMMIT
    h_commit = "1" * 40
    p_commit = "2" * 40
    configured_url = [activation.CONFIGURED_ORIGIN_URL]
    oid_by_expression = {
        "HEAD^{commit}": p_commit,
        "refs/heads/main^{commit}": p_commit,
        "refs/remotes/origin/main^{commit}": p_commit,
        "refs/remotes/origin/HEAD^{commit}": p_commit,
        "HEAD~1^{commit}": h_commit,
        "HEAD~2^{commit}": r_commit,
    }

    def git_text(_root: Path, arguments: tuple[str, ...]) -> str:
        if arguments == ("symbolic-ref", "--quiet", "HEAD"):
            return "refs/heads/main\n"
        if arguments == (
            "symbolic-ref",
            "--quiet",
            "refs/remotes/origin/HEAD",
        ):
            return "refs/remotes/origin/main\n"
        if arguments == ("remote", "get-url", "origin"):
            return configured_url[0] + "\n"
        if arguments[:3] == ("rev-list", "--parents", "-n"):
            child = arguments[-1]
            parent = r_commit if child == h_commit else h_commit
            return f"{child} {parent}\n"
        raise AssertionError(arguments)

    h_scope = [
        {"path": path, "status": status}
        for path, status in activation.REQUIRED_H_SCOPE.items()
    ]
    p_scope = [
        {"path": path, "status": "A"}
        for path in activation.EXPECTED_P_SCOPE_PATHS
    ]
    monkeypatch.setattr(
        activation,
        "_git_oid",
        lambda _root, expression: oid_by_expression[expression],
    )
    monkeypatch.setattr(activation, "_git_text", git_text)
    monkeypatch.setattr(activation, "_require_clean_repository", lambda _root: None)
    monkeypatch.setattr(
        activation,
        "_git_diff_scope",
        lambda _root, parent, _child: h_scope if parent == r_commit else p_scope,
    )
    monkeypatch.setattr(activation, "_regular_bytes", lambda *_args, **_kwargs: b"")

    topology = activation._topology(
        repo_root=tmp_path,
        published_u=False,
        verify_remote=False,
    )
    assert topology["head"] == p_commit
    assert activation.CONFIGURED_ORIGIN_URL == (
        "git@github.com:ejherran/lentic-pipe.git"
    )
    assert activation.LIVE_REMOTE_URL == (
        "https://github.com/ejherran/lentic-pipe.git"
    )

    configured_url[0] = activation.LIVE_REMOTE_URL
    with pytest.raises(activation.ActivationLockError, match="remote topology"):
        activation._topology(
            repo_root=tmp_path,
            published_u=False,
            verify_remote=False,
        )

    remote_calls: list[tuple[str, ...]] = []

    def live_git(_root: Path, arguments: tuple[str, ...]) -> bytes:
        remote_calls.append(arguments)
        return f"{p_commit}\trefs/heads/main\n".encode("ascii")

    monkeypatch.setattr(activation, "_git", live_git)
    activation._verify_live_remote(tmp_path, p_commit)
    assert remote_calls == [
        ("ls-remote", "--heads", activation.LIVE_REMOTE_URL, "refs/heads/main")
    ]


def test_public_runner_activation_material_is_exact_and_outcome_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = {"path": runner.SCRIPT_PATH.as_posix(), "sha256": "a" * 64}
    readiness = {
        "missing_component_count": 0,
        "component_source_records": [{"status": "ready"}] * 10,
        "context_builder_source_record": {"status": "ready"},
        "support_source_records": [{"status": "ready"}] * 3,
    }
    monkeypatch.setattr(runner, "runner_source_record", lambda **_kwargs: source)
    monkeypatch.setattr(
        runner,
        "collect_sealed_batch_component_readiness",
        lambda **_kwargs: readiness,
    )
    monkeypatch.setattr(
        runner,
        "_runtime_environment_record",
        lambda **_kwargs: {
            "schema_version": "closure_sealed_runtime_environment_v1"
        },
    )
    material = runner.collect_e0_u_activation_material()
    assert material["status"] == "e0_u_activation_material_ready"
    assert material["runner_source_record"] == source
    assert len(material["dvc_policy"]["heavy_artifact_paths"]) == 4
    assert len(material["dvc_policy"]["direct_git_artifact_paths"]) == 48
    assert material["outcome_paths_opened"] is False
    assert material["future_outcomes_accessed"] is False
    assert material["writes_performed"] is False

    prefix = {
        "path": runner.OUTCOME_ACCESS_LOG_PATH.as_posix(),
        "bytes": runner.ATTEMPT_1_ACCESS_LOG_BYTES,
        "sha256": runner.ATTEMPT_1_ACCESS_LOG_SHA256,
        "record_count": 1,
        "first_execution_id": runner.ATTEMPT_1_EXECUTION_ID,
    }
    monkeypatch.setattr(
        runner,
        "_attempt_1_access_log_prefix",
        lambda **_kwargs: prefix,
    )
    recovery = runner.collect_e0_u_activation_material(recovery_attempt=True)
    recovery_contract = runner.sealed_batch_contract(recovery_attempt=True)
    assert recovery["status"] == "e0_u_recovery_activation_material_ready"
    assert recovery["attempt_ordinal"] == 2
    assert recovery["first_attempt"] is False
    assert recovery["outcome_access_log_prefix"] == prefix
    assert recovery["recovery_guard_path"] == runner.RECOVERY_RUN_GUARD_PATH
    assert recovery["sealed_recovery_batch_command"] == (
        runner.SEALED_RECOVERY_BATCH_COMMAND
    )
    assert recovery_contract["sealed_command"] == (
        runner.SEALED_RECOVERY_BATCH_COMMAND
    )
    assert recovery_contract["authority_context_factory_api"] == (
        runner.E0_U_RECOVERY_CONTEXT_FACTORY_API
    )
    assert runner.validate_sealed_batch_contract(recovery_contract) == (
        recovery_contract
    )

    adapter_calls: list[dict[str, Any]] = []
    context_module = ModuleType("synthetic_recovery_context")
    context_module.__dict__["EVIDENCE_ROOT"] = runner.LEGACY_E10_SOURCE_DIRECTORY
    context_module.__dict__["EVIDENCE_MANIFEST_PATH"] = (
        runner.LEGACY_E10_SOURCE_PATHS[-1]
    )
    context_module.__dict__["EVIDENCE_SOURCE_PATHS"] = (
        runner.LEGACY_E10_SOURCE_PATHS
    )

    def legacy_loader(**kwargs: Any) -> dict[str, Any]:
        adapter_calls.append(kwargs)
        return {"ok": True}

    context_module.__dict__["load_closure_e10_software_evidence"] = legacy_loader
    expected_adapter_bindings = runner._configure_recovery_context_e10_adapter(
        context_module
    )
    runner._recapture_recovery_context_e10_adapter(
        context_module, expected_adapter_bindings
    )
    assert context_module.__dict__["load_closure_e10_software_evidence"](
        value=1
    ) == {
        "ok": True
    }
    assert adapter_calls == [
        {"value": 1, "recovery_attempt": runner.RECOVERY_ATTEMPT}
    ]
    context_module.__dict__["EVIDENCE_ROOT"] = Path(
        runner.RECOVERY_E10_SOURCE_DIRECTORY.as_posix()
    )
    with pytest.raises(runner.ClosureBenchmarkError, match="adapter changed"):
        runner._recapture_recovery_context_e10_adapter(
            context_module, expected_adapter_bindings
        )


def test_activation_publication_is_no_clobber_and_canonical(tmp_path: Path) -> None:
    (tmp_path / activation.ACTIVATION_PATH.parent).mkdir(parents=True)
    (tmp_path / "tmp").mkdir()
    directory, created = activation._ensure_directory(
        activation.TEMP_DIRECTORY,
        repo_root=tmp_path,
    )
    assert created is True
    payload = activation._canonical_json_bytes({"gate": "E0-U", "value": 1})
    record = activation._publish_activation(payload, repo_root=tmp_path)
    output = tmp_path / activation.ACTIVATION_PATH
    assert output.read_bytes() == payload
    metadata = os.lstat(output)
    assert metadata.st_nlink == 1
    assert record == {
        "path": activation.ACTIVATION_PATH.as_posix(),
        "bytes": len(payload),
        "sha256": activation._sha256_bytes(payload),
        "manifest_written_last": True,
        "no_clobber": True,
    }
    with pytest.raises(FileExistsError):
        activation._publish_activation(payload, repo_root=tmp_path)
    assert output.read_bytes() == payload
    assert not list(directory.glob("*.tmp"))


def test_activation_reader_rejects_symlinked_ancestor(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "payload.json").write_text('{"outside":true}\n', encoding="utf-8")
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(activation.ActivationLockError, match="directory chain"):
        activation._regular_bytes(
            Path("linked/payload.json"),
            repo_root=tmp_path,
        )


def test_activation_reader_recaptures_renamed_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "sealed"
    parent.mkdir()
    payload = b'{"sealed":true}\n'
    (parent / "payload.json").write_bytes(payload)
    original_read = activation.os.read
    swapped = False

    def rename_after_read(descriptor: int, count: int) -> bytes:
        nonlocal swapped
        chunk = original_read(descriptor, count)
        if chunk and not swapped:
            swapped = True
            parent.rename(tmp_path / "sealed.original")
            parent.mkdir()
            (parent / "payload.json").write_bytes(payload)
        return chunk

    monkeypatch.setattr(activation.os, "read", rename_after_read)
    with pytest.raises(activation.ActivationLockError, match="ancestor"):
        activation._regular_bytes(
            Path("sealed/payload.json"),
            repo_root=tmp_path,
        )


def test_activation_publication_rolls_back_owned_inode_after_parent_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = tmp_path / activation.ACTIVATION_PATH.parent
    protocol.mkdir(parents=True)
    (tmp_path / "tmp").mkdir()
    activation._ensure_directory(activation.TEMP_DIRECTORY, repo_root=tmp_path)
    original_link = activation.os.link

    def link_then_replace_parent(*args: Any, **kwargs: Any) -> None:
        original_link(*args, **kwargs)
        protocol.rename(protocol.with_name("00_protocol.original"))
        protocol.mkdir()

    monkeypatch.setattr(activation.os, "link", link_then_replace_parent)
    with pytest.raises(activation.ActivationLockError, match="ancestor"):
        activation._publish_activation(
            activation._canonical_json_bytes({"gate": "E0-U"}),
            repo_root=tmp_path,
        )

    original_protocol = protocol.with_name("00_protocol.original")
    assert not (original_protocol / activation.ACTIVATION_PATH.name).exists()
    assert not (protocol / activation.ACTIVATION_PATH.name).exists()
    assert not list((tmp_path / activation.TEMP_DIRECTORY).glob("*.tmp"))


def test_activation_rollback_capture_restores_boundary_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = tmp_path / activation.ACTIVATION_PATH.parent
    protocol.mkdir(parents=True)
    (tmp_path / activation.TEMP_DIRECTORY).mkdir(parents=True)
    payload = activation._canonical_json_bytes({"gate": "E0-U"})
    publication = activation._publish_activation(
        payload,
        repo_root=tmp_path,
        retain_anchor=True,
    )
    assert isinstance(publication, tuple)
    lease = publication[1]
    original_rename = activation.os.rename
    moved_leaf = activation.ACTIVATION_PATH.name + ".owned-moved"
    foreign_payload = b"foreign-activation\n"
    swapped = False

    def replace_at_capture(
        source: str,
        destination: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        nonlocal swapped
        if source == activation.ACTIVATION_PATH.name and not swapped:
            swapped = True
            parent_fd = kwargs["src_dir_fd"]
            original_rename(
                source,
                moved_leaf,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            descriptor = os.open(
                source,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o644,
                dir_fd=parent_fd,
            )
            try:
                os.write(descriptor, foreign_payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(activation.os, "rename", replace_at_capture)
    with pytest.raises(
        activation.ActivationLockError,
        match="rollback was not exact",
    ):
        activation._rollback_activation_publication(lease)

    assert (protocol / activation.ACTIVATION_PATH.name).read_bytes() == foreign_payload
    assert (protocol / moved_leaf).read_bytes() == payload
    assert not list(protocol.glob(".closure-owned-capture-*"))


def test_activation_rollback_restores_directory_boundary_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = tmp_path / activation.ACTIVATION_PATH.parent
    protocol.mkdir(parents=True)
    (tmp_path / activation.TEMP_DIRECTORY).mkdir(parents=True)
    publication = activation._publish_activation(
        activation._canonical_json_bytes({"gate": "E0-U"}),
        repo_root=tmp_path,
        retain_anchor=True,
    )
    assert isinstance(publication, tuple)
    lease = publication[1]
    original_rename = activation.os.rename
    swapped = False

    def replace_at_capture(
        source: str,
        destination: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        nonlocal swapped
        if source == activation.ACTIVATION_PATH.name and not swapped:
            swapped = True
            parent_fd = kwargs["src_dir_fd"]
            os.unlink(source, dir_fd=parent_fd)
            os.mkdir(source, 0o700, dir_fd=parent_fd)
        original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(activation.os, "rename", replace_at_capture)
    with pytest.raises(
        activation.ActivationLockError,
        match="rollback was not exact",
    ):
        activation._rollback_activation_publication(lease)

    assert (protocol / activation.ACTIVATION_PATH.name).is_dir()
    assert not list(protocol.glob(".closure-owned-capture-*"))


def test_guard_is_exclusive_and_recoverable(tmp_path: Path) -> None:
    (tmp_path / "tmp").mkdir()
    first = activation._acquire_guard(repo_root=tmp_path)
    assert first.directory_created is True
    with pytest.raises(activation.ActivationLockError, match="guard"):
        activation._acquire_guard(repo_root=tmp_path)
    activation._release_guard_lease(first)
    assert first.closed is True
    second = activation._acquire_guard(repo_root=tmp_path)
    assert second.directory_created is True
    activation._release_guard_lease(second)
    assert second.closed is True


def test_guard_parent_directory_boundary_replacement_is_restored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "tmp").mkdir()
    guard = activation._acquire_guard(repo_root=tmp_path)
    original_rename = activation.os.rename
    moved_name = activation.TEMP_DIRECTORY.name + ".owned-moved"
    swapped = False

    def replace_at_capture(
        source: str,
        destination: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        nonlocal swapped
        if source == activation.TEMP_DIRECTORY.name and not swapped:
            swapped = True
            parent_fd = kwargs["src_dir_fd"]
            original_rename(
                source,
                moved_name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            os.mkdir(source, 0o700, dir_fd=parent_fd)
        original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(activation.os, "rename", replace_at_capture)
    with pytest.raises(activation.ActivationLockError, match="guard release"):
        activation._release_guard_lease(guard)

    canonical = tmp_path / activation.TEMP_DIRECTORY
    assert canonical.is_dir()
    assert (canonical.parent / moved_name).is_dir()
    assert not (tmp_path / activation.GUARD_PATH).exists()
    assert not list(canonical.parent.glob(".closure-owned-directory-capture-*"))


def test_temporary_directory_setup_cleanup_restores_boundary_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "tmp").mkdir()
    original_rename = activation.os.rename
    moved_name = activation.TEMP_DIRECTORY.name + ".owned-moved"
    swapped = False

    def fail_recapture(**_kwargs: Any) -> None:
        raise activation.ActivationLockError("synthetic recapture failure")

    def replace_at_capture(
        source: str,
        destination: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        nonlocal swapped
        if source == activation.TEMP_DIRECTORY.name and not swapped:
            swapped = True
            parent_fd = kwargs["src_dir_fd"]
            original_rename(
                source,
                moved_name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            os.mkdir(source, 0o700, dir_fd=parent_fd)
            (tmp_path / activation.TEMP_DIRECTORY / "foreign.keep").write_text(
                "foreign\n",
                encoding="utf-8",
            )
        original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(activation, "_recapture_directory_chain", fail_recapture)
    monkeypatch.setattr(activation.os, "rename", replace_at_capture)
    with pytest.raises(
        activation.ActivationLockError,
        match="setup and cleanup failed closed",
    ):
        activation._ensure_directory_record(
            activation.TEMP_DIRECTORY,
            repo_root=tmp_path,
        )

    canonical = tmp_path / activation.TEMP_DIRECTORY
    assert (canonical / "foreign.keep").read_text(encoding="utf-8") == "foreign\n"
    assert (canonical.parent / moved_name).is_dir()
    assert not list(canonical.parent.glob(".closure-owned-directory-capture-*"))


def test_owned_unlink_does_not_follow_replaced_guard_ancestor(tmp_path: Path) -> None:
    (tmp_path / "tmp").mkdir()
    guard = activation._acquire_guard(repo_root=tmp_path)
    original_directory = tmp_path / activation.TEMP_DIRECTORY
    moved_directory = original_directory.with_name("activation.original")
    original_directory.rename(moved_directory)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_guard = outside / activation.GUARD_PATH.name
    outside_guard.write_text("foreign\n", encoding="utf-8")
    original_directory.symlink_to(outside, target_is_directory=True)

    with pytest.raises(activation.ActivationLockError, match="guard release"):
        activation._release_guard_lease(guard)

    assert outside_guard.read_text(encoding="utf-8") == "foreign\n"
    assert not (moved_directory / activation.GUARD_PATH.name).exists()
    assert guard.closed is True


def test_generate_commits_only_after_exact_guard_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / activation.ACTIVATION_PATH.parent).mkdir(parents=True)
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(
        activation,
        "_expected_manifest",
        lambda **_kwargs: (
            {"gate": "E0-U", "synthetic": True},
            {"h_commit": "1" * 40, "p_commit": "2" * 40},
        ),
    )

    result = activation.generate(repo_root=tmp_path, verify_remote=False)

    assert result["status"] == "activation_written_unpublished"
    assert (tmp_path / activation.ACTIVATION_PATH).is_file()
    assert not (tmp_path / activation.GUARD_PATH).exists()
    assert not (tmp_path / activation.TEMP_DIRECTORY).exists()


def test_post_commit_descriptor_close_error_does_not_report_false_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / activation.ACTIVATION_PATH.parent).mkdir(parents=True)
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(
        activation,
        "_expected_manifest",
        lambda **_kwargs: (
            {"gate": "E0-U", "synthetic": True},
            {"h_commit": "1" * 40, "p_commit": "2" * 40},
        ),
    )
    real_release = activation._release_guard_lease
    real_close = os.close
    guard_released = False
    injected = False

    def release_then_enable_close_probe(guard: activation.GuardLease) -> None:
        nonlocal guard_released
        real_release(guard)
        guard_released = True

    def close_then_report(descriptor: int) -> None:
        nonlocal injected
        real_close(descriptor)
        if guard_released and not injected:
            injected = True
            raise OSError("synthetic post-commit close report")

    monkeypatch.setattr(
        activation,
        "_release_guard_lease",
        release_then_enable_close_probe,
    )
    monkeypatch.setattr(os, "close", close_then_report)

    result = activation.generate(repo_root=tmp_path, verify_remote=False)

    assert injected is True
    assert result["status"] == "activation_written_unpublished"
    assert (tmp_path / activation.ACTIVATION_PATH).is_file()
    assert not (tmp_path / activation.GUARD_PATH).exists()


def test_activation_byte_mutation_after_guard_release_is_rolled_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / activation.ACTIVATION_PATH.parent).mkdir(parents=True)
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(
        activation,
        "_expected_manifest",
        lambda **_kwargs: (
            {"gate": "E0-U", "synthetic": True},
            {"h_commit": "1" * 40, "p_commit": "2" * 40},
        ),
    )
    original_release = activation._release_guard_lease

    def release_then_mutate(guard: activation.GuardLease) -> None:
        original_release(guard)
        path = tmp_path / activation.ACTIVATION_PATH
        payload = path.read_bytes()
        path.write_bytes(b"[" + payload[1:])

    monkeypatch.setattr(activation, "_release_guard_lease", release_then_mutate)
    with pytest.raises(activation.ActivationLockError, match="replaced"):
        activation.generate(repo_root=tmp_path, verify_remote=False)

    assert not (tmp_path / activation.ACTIVATION_PATH).exists()
    assert not list(tmp_path.rglob("activation.*.tmp"))


@pytest.mark.parametrize(
    "mutation",
    (
        "guard_disappeared",
        "guard_replaced",
        "root_replaced",
        "ancestor_replaced",
        "root_replaced_after_publish",
        "ancestor_replaced_after_publish",
    ),
)
def test_guard_publish_composite_failure_rolls_back_activation_everywhere(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / activation.ACTIVATION_PATH.parent).mkdir(parents=True)
    (repo / "tmp").mkdir()
    monkeypatch.setattr(
        activation,
        "_expected_manifest",
        lambda **_kwargs: (
            {"gate": "E0-U", "synthetic": True},
            {"h_commit": "1" * 40, "p_commit": "2" * 40},
        ),
    )
    original_publish = activation._publish_activation
    old_repo = tmp_path / "repo-original"
    moved_guard_parent = repo / "tmp" / "activation-guard-original"
    foreign_guard_payload = b"foreign-guard\n"

    def hostile_publish(*args: Any, **kwargs: Any) -> Any:
        if mutation == "root_replaced":
            repo.rename(old_repo)
            (repo / activation.ACTIVATION_PATH.parent).mkdir(parents=True)
            (repo / "tmp").mkdir()
            return original_publish(*args, **kwargs)
        if mutation == "ancestor_replaced":
            guard_parent = repo / activation.TEMP_DIRECTORY
            guard_parent.rename(moved_guard_parent)
            guard_parent.mkdir()
            return original_publish(*args, **kwargs)
        result = original_publish(*args, **kwargs)
        if mutation == "root_replaced_after_publish":
            repo.rename(old_repo)
            (repo / activation.ACTIVATION_PATH.parent).mkdir(parents=True)
            (repo / "tmp").mkdir()
            return result
        if mutation == "ancestor_replaced_after_publish":
            guard_parent = repo / activation.TEMP_DIRECTORY
            guard_parent.rename(moved_guard_parent)
            guard_parent.mkdir()
            return result
        guard_path = repo / activation.GUARD_PATH
        guard_path.unlink()
        if mutation == "guard_replaced":
            guard_path.write_bytes(foreign_guard_payload)
        return result

    monkeypatch.setattr(activation, "_publish_activation", hostile_publish)
    with pytest.raises(activation.ActivationLockError):
        activation.generate(repo_root=repo, verify_remote=False)

    namespaces = [repo]
    if old_repo.exists():
        namespaces.append(old_repo)
    for namespace in namespaces:
        assert not (namespace / activation.ACTIVATION_PATH).exists()
        assert not list(namespace.rglob("activation.*.tmp"))
    if mutation in {"ancestor_replaced", "ancestor_replaced_after_publish"}:
        assert not list(moved_guard_parent.glob("activation.*.tmp"))
    if mutation == "guard_replaced":
        assert (repo / activation.GUARD_PATH).read_bytes() == foreign_guard_payload


def test_commands_preserve_isolated_outcome_free_boundary() -> None:
    for command in (
        activation.CHECK_ONLY_COMMAND,
        activation.GENERATION_COMMAND,
        activation.VALIDATE_COMMAND,
        activation.RECOVERY_CHECK_ONLY_COMMAND,
        activation.RECOVERY_GENERATION_COMMAND,
        activation.RECOVERY_VALIDATE_COMMAND,
    ):
        assert command.startswith("/usr/bin/env -i LANG=C LC_ALL=C ")
        assert ".venv/bin/python -I -S -B " in command
        assert "run_closure_benchmark.py --execute-sealed-batch" not in command
    assert activation.RECOVERY_SEALED_BATCH_COMMAND == (
        activation.RECOVERY_COMMAND_PATH.read_text(encoding="utf-8")
    )
    assert runner.parse_args(
        [runner.SEALED_RECOVERY_BATCH_MODE]
    ).execute_sealed_recovery_batch is True
    assert activation._parser().parse_args(
        ["--check-recovery"]
    ).check_recovery is True
    assert activation._parser().parse_args(
        ["--generate-recovery"]
    ).generate_recovery is True
    assert activation._parser().parse_args(
        ["--validate-published-recovery"]
    ).validate_published_recovery is True


def test_direct_parent_guard_rejects_merge_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = "1" * 40
    parent = "2" * 40
    monkeypatch.setattr(
        activation,
        "_git_text",
        lambda *_args, **_kwargs: f"{child} {parent} {'3' * 40}\n",
    )
    with pytest.raises(activation.ActivationLockError, match="direct non-merge"):
        activation._require_direct_parent(
            Path.cwd(), child=child, expected_parent=parent, label="P"
        )


def test_public_schema_matches_authority_manifest_keys() -> None:
    schema_path = Path("configs/closure_v1/closure_e0_u_activation.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    authority_namespace = activation._load_source_namespace(
        activation.AUTHORITY_PATH,
        repo_root=activation.PROJECT_ROOT,
        module_name="closure_activation_schema_authority",
    )
    assert schema["additionalProperties"] is False
    assert tuple(authority_namespace["EXPECTED_P_SCOPE_PATHS"]) == (
        activation.EXPECTED_P_SCOPE_PATHS
    )
    p_scope_overlay = schema["properties"]["p_scope"]["allOf"][1]
    assert (p_scope_overlay["minItems"], p_scope_overlay["maxItems"]) == (10, 10)
    assert tuple(p_scope_overlay["items"]["properties"]["path"]["enum"]) == (
        activation.EXPECTED_P_SCOPE_PATHS
    )
    assert p_scope_overlay["items"]["properties"]["status"]["const"] == "A"
    assert p_scope_overlay["items"]["properties"]["mode"]["const"] == "100644"
    assert set(schema["required"]) == set(
        authority_namespace["ACTIVATION_MANIFEST_KEYS"]
    )
    assert schema["properties"]["base_r_commit"]["const"] == activation.BASE_R_COMMIT
    deep = schema["properties"]["phase3_overlay_deep_validation"]
    assert deep["additionalProperties"] is False
    assert set(deep["required"]) == activation.PHASE3_OVERLAY_DEEP_VALIDATION_KEYS
    assert deep["properties"]["checkpoint_count"]["const"] == 25
    assert deep["properties"]["state_dict_array_count"]["const"] == 195
    assert deep["properties"]["warmup_row_count"]["const"] == 88
    assert deep["properties"]["warmup_site_count"]["const"] == 88
    assert deep["properties"]["source_inputs"]["minItems"] == 27
    assert deep["properties"]["source_inputs"]["maxItems"] == 27
    assert deep["properties"]["history_projection"]["const"] == list(
        activation.PHASE3_OVERLAY_HISTORY_PROJECTION
    )
    assert deep["properties"]["panel_projection"]["const"] == list(
        activation.PHASE3_OVERLAY_PANEL_PROJECTION
    )
    assert schema["properties"]["sealed_batch_command"]["const"] == (
        "/usr/bin/env -i LANG=C LC_ALL=C .venv/bin/python -I -S -B "
        "src/experiments/run_closure_benchmark.py --execute-sealed-batch\n"
    )
    recovery_schema = json.loads(
        activation.RECOVERY_ACTIVATION_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    assert recovery_schema["additionalProperties"] is False
    assert set(recovery_schema["required"]) == set(
        authority_namespace["RECOVERY_ACTIVATION_MANIFEST_KEYS"]
    )
    assert recovery_schema["properties"]["attempt_ordinal"]["const"] == 2
    assert recovery_schema["properties"]["first_attempt"]["const"] is False
    assert tuple(authority_namespace["EXPECTED_RECOVERY_H_SCOPE"]) == (
        activation.EXPECTED_RECOVERY_H_SCOPE
    )
    assert tuple(authority_namespace["EXPECTED_RECOVERY_P_SCOPE_PATHS"]) == (
        activation.EXPECTED_RECOVERY_P_SCOPE_PATHS
    )
