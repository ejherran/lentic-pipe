from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.experiments import closure_p1_temporal_consumer_patch as module
from src.experiments import lock_closure_p1_temporal_consumer_patch as locker


ZERO_SHA = "0" * 64
ONE_SHA = "1" * 64
PATCH_HEAD = "a" * 40
LOCK_COMMIT = "b" * 40


def _record(path: str, role: str, *, size: int = 1, sha256: str = ZERO_SHA) -> dict[str, Any]:
    return {"path": path, "role": role, "bytes": size, "sha256": sha256}


def _audit_result() -> dict[str, Any]:
    present = [
        module.p1_audit.P1_SEQUENCE_PATH.as_posix(),
        module.p1_audit.P1_POINTER_PATH.as_posix(),
        module.p1_audit.P1_SUMMARY_PATH.as_posix(),
        module.p1_audit.P1_MANIFEST_PATH.as_posix(),
    ]
    outputs = [
        {
            "path": module.p1_audit.P1_SEQUENCE_PATH.as_posix(),
            "bytes": 1_380_222,
            "sha256": "860da77ac60c1aefb88cc9359631badc676864c77fb6df1d4b1ab87e01992069",
        },
        {
            "path": module.p1_audit.P1_SUMMARY_PATH.as_posix(),
            "bytes": 356,
            "sha256": "a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e",
        },
        {
            "path": module.p1_audit.P1_MANIFEST_PATH.as_posix(),
            "bytes": 6_527,
            "sha256": "5f1086b9409dac13625d77759badd8f3e9ba39a140a1d578da5ef6285f0295ea",
        },
    ]
    return {
        "status": "validated",
        "model_id": "P1",
        "base_seed": 1729,
        "outputs": outputs,
        "counts": {"intent_origins": 9_732},
        "fit_availability": {
            "available": False,
            "observed_fit_status_counts": {
                "success": 8_925,
                "autoregressive_target_unavailable": 488,
            },
            "observed_fit_failure_reason_counts": {"missing_target_state": 488},
            "observed_calibration_failure_count": 17,
            "expected_temporal_slot_status": "model_unavailable",
            "expected_fit_status": "not_attempted",
            "expected_failure_reason": "sequence_fit_rows_unavailable",
            "consumer_executed_by_auditor": False,
            "fit_or_model_construction_executed_by_auditor": False,
        },
        "dvc_registration": {
            "state": "post_dvc",
            "pointer_payload_binding_verified": True,
        },
        "namespace_evidence": {
            "progression_observation": {
                "registered_p1_path_count": 140,
                "registered_present_paths": present,
                "consumer_seed_1729_present_paths": [],
                "future_seed_present_paths": [],
                "e0_m_present_paths": [],
                "outcome_access_log_present": False,
                "pre_consumer_and_pre_e0_m_clear_now": True,
            }
        },
        "audited_namespaces_unchanged": True,
        "future_outcomes_accessed_by_auditor": False,
        "one_shot_reconsumed_by_auditor": False,
    }


def _effective_summary() -> dict[str, Any]:
    return {
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_e0_mc_verified": True,
        "nested_historical_e0_mb_verified": True,
        "historical_e0_dltvm_verified": True,
        "historical_dltvm_effective_loader_called": False,
        "p1_sequence_bundle_verified": True,
        "consumer_namespace_absent": True,
        "authorization_effective": True,
        "p1_consumer_authorized": True,
        "p1_fit_authorized": True,
        "sequence_fit_available": False,
        "batch_seed_execution_authorized": False,
        "retry_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "fit_availability": dict(module.FIT_AVAILABILITY),
    }


def _command_evidence(command: tuple[str, ...]) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": ZERO_SHA,
        "stderr_sha256": ZERO_SHA,
        "stdout_line_count": 0,
        "stderr_line_count": 0,
    }


def _verification_evidence() -> dict[str, Any]:
    focused = {
        **_command_evidence(module.FOCUSED_TEST_COMMAND),
        "test_count": module.FOCUSED_TEST_COUNT,
        "skipped_count": 0,
        "deselected_count": 0,
    }
    first = {
        **_command_evidence(module.DVC_PUSH_COMMAND),
        "terminal_status": "Everything is up to date.",
    }
    second = dict(first)
    return {
        "full_type_check": _command_evidence(module.TYPE_CHECK_COMMAND),
        "focused_tests": focused,
        "poetry_check": _command_evidence(module.POETRY_CHECK_COMMAND),
        "publication_guard": _command_evidence(module.PUBLICATION_GUARD_COMMAND),
        "git_diff_check": _command_evidence(module.DIFF_CHECK_COMMAND),
        "p1_bundle_audit": _command_evidence(module.P1_AUDIT_COMMAND),
        "dvc_push_first": first,
        "dvc_push_second": second,
    }


def test_closed_scope_is_exact_two_modifications_and_five_additions() -> None:
    assert module.PATCH_BASE_COMMIT == module.P1_BUNDLE_COMMIT
    assert module.PATCH_MODIFIED_PATHS == (
        "src/experiments/train_closure_pipe.py",
        "tests/test_train_closure_pipe.py",
    )
    assert len(module.PATCH_ADDED_PATHS) == 5
    assert len(module.PATCH_PATHS) == 7
    assert set(module.PATCH_ADDED_PATHS).isdisjoint(module.PATCH_MODIFIED_PATHS)


def test_schema_is_strict_and_parses() -> None:
    schema = json.loads(module.DEFAULT_PATCH_LOCK_SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["gate"] == {"const": "E0-MD"}
    focused = schema["$defs"]["focusedCommandEvidence"]
    assert focused["additionalProperties"] is False
    assert {"test_count", "skipped_count", "deselected_count"}.issubset(
        focused["properties"]
    )


def test_patch_git_diff_requires_exact_direct_child(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "_require_commit", lambda value, **_: value)
    monkeypatch.setattr(
        module,
        "_git",
        lambda *args: f"{PATCH_HEAD} {module.PATCH_BASE_COMMIT}",
    )
    expected = [
        {
            "status": "M" if path in module.PATCH_MODIFIED_PATHS else "A",
            "path": path,
        }
        for path in module.PATCH_PATHS
    ]
    monkeypatch.setattr(module, "_observed_diff_entries", lambda *args: expected)
    observed = module.patch_git_diff_payload(PATCH_HEAD)
    assert observed["added_count"] == 5
    assert observed["modified_count"] == 2
    assert observed["entries"] == expected


def test_patch_git_diff_rejects_scope_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "_require_commit", lambda value, **_: value)
    monkeypatch.setattr(
        module,
        "_git",
        lambda *args: f"{PATCH_HEAD} {module.PATCH_BASE_COMMIT}",
    )
    monkeypatch.setattr(
        module,
        "_observed_diff_entries",
        lambda *args: [{"status": "A", "path": "unexpected"}],
    )
    with pytest.raises(module.P1TemporalConsumerPatchError, match=r"2M\+5A"):
        module.patch_git_diff_payload(PATCH_HEAD)


def test_patch_component_bundle_binds_all_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "_require_commit", lambda value, **_: value)
    monkeypatch.setattr(
        module,
        "_git_record",
        lambda commit, path, role: _record(path, role),
    )
    observed = module.patch_component_bundle(PATCH_HEAD)
    assert observed["count"] == 7
    assert observed["paths"] == list(module.PATCH_PATHS)
    assert [item["role"] for item in observed["records"]] == [
        module.PATCH_COMPONENT_ROLES[path] for path in module.PATCH_PATHS
    ]


def test_p1_publication_topology_requires_exact_five_additions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "_git",
        lambda *args: f"{module.P1_BUNDLE_COMMIT} {module.E0_MC_P_COMMIT}",
    )
    monkeypatch.setattr(
        module,
        "_observed_diff_entries",
        lambda *args: [{"status": "A", "path": path} for path in module.P1_PUBLICATION_PATHS],
    )
    monkeypatch.setattr(
        module,
        "_git_record",
        lambda commit, path, role: _record(path, role),
    )
    monkeypatch.setattr(module, "_require_git_record_physical", lambda record: None)
    records = module._validate_p1_publication_topology()
    assert len(records) == 5
    assert {record["path"] for record in records} == set(module.P1_PUBLICATION_PATHS)


def test_fit_availability_is_closed_model_unavailable() -> None:
    observed = module._fit_availability_from_audit(_audit_result())
    assert observed == module.FIT_AVAILABILITY
    assert observed["sequence_fit_available"] is False
    assert observed["fit_status_counts"] == {
        "success": 8_925,
        "autoregressive_target_unavailable": 488,
    }
    assert observed["calibration_failure_count"] == 17


def test_fit_availability_rejects_denominator_drift() -> None:
    result = _audit_result()
    observed = dict(result["fit_availability"])
    observed["observed_calibration_failure_count"] = 16
    result["fit_availability"] = observed
    with pytest.raises(module.P1TemporalConsumerPatchError, match="unavailable"):
        module._fit_availability_from_audit(result)


def test_p1_bundle_authority_requires_closed_progression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "_validate_p1_publication_topology",
        lambda: [_record(path, role) for path, role in module.P1_PUBLICATION_ROLES.items()],
    )
    monkeypatch.setattr(module.p1_audit, "audit_p1_sequence_bundle", _audit_result)
    monkeypatch.setattr(
        module.p1_audit,
        "_require_pre_consumer_progression_clear",
        lambda evidence: None,
    )
    authority = module._p1_sequence_bundle_authority()
    assert authority["audit_status"] == "validated"
    assert authority["pre_consumer_progression_gate"] == "passed"
    assert authority["fit_availability"] == module.FIT_AVAILABILITY
    assert len(authority["publication_records"]) == 5
    assert len(authority["physical_output_records"]) == 3


def test_p1_bundle_authority_rejects_consumer_presence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _audit_result()
    progression = result["namespace_evidence"]["progression_observation"]
    progression["consumer_seed_1729_present_paths"] = ["model.pt"]
    progression["pre_consumer_and_pre_e0_m_clear_now"] = False
    monkeypatch.setattr(module, "_validate_p1_publication_topology", lambda: [])
    monkeypatch.setattr(module.p1_audit, "audit_p1_sequence_bundle", lambda: result)
    monkeypatch.setattr(
        module.p1_audit,
        "_require_pre_consumer_progression_clear",
        lambda evidence: (_ for _ in ()).throw(
            module.p1_audit.ClosureP1SequenceAuditError("not clear")
        ),
    )
    with pytest.raises(module.P1TemporalConsumerPatchError, match="not clear"):
        module._p1_sequence_bundle_authority()


def test_consumer_namespace_contract_is_exact(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    observed = module.p1_consumer_namespace_absence()
    assert observed["model_id"] == "P1"
    assert observed["base_seed"] == 1729
    assert observed["count"] == len(module.p1_audit.P1_CONSUMER_PATHS)
    assert observed["all_absent_at_lock"] is True


def test_consumer_namespace_rejects_any_final(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    path = tmp_path / module.p1_audit.P1_CONSUMER_PATHS[0]
    path.parent.mkdir(parents=True)
    path.write_bytes(b"foreign")
    with pytest.raises(module.P1TemporalConsumerPatchError, match="not empty"):
        module.p1_consumer_namespace_absence()


def test_consumer_namespace_rejects_broken_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    path = tmp_path / module.p1_audit.P1_CONSUMER_PATHS[0]
    path.parent.mkdir(parents=True)
    path.symlink_to(path.parent / "absent-target")
    assert not path.exists()
    with pytest.raises(module.P1TemporalConsumerPatchError, match="not empty"):
        module.p1_consumer_namespace_absence()


def test_build_lock_keeps_authorization_ineffective() -> None:
    prelock = {
        "patch_repository": {},
        "git_diff": {},
        "patch_components": {},
        "base_authorities": {},
        "p1_sequence_bundle": {},
        "consumer_prelock": {},
        "fit_availability": module.FIT_AVAILABILITY,
    }
    payload = module.build_p1_temporal_consumer_patch_lock_payload(
        prelock,
        {},
        created_at_utc="2026-08-06T00:00:00Z",
    )
    assert payload["authorizations"] == module.PATCH_AUTHORIZATIONS
    assert payload["authorizations"]["p1_fit_authorized"] is False
    assert payload["fit_availability"]["sequence_fit_available"] is False


def test_e0_mc_reconstruction_policy_is_git_bound_and_not_effective() -> None:
    assert module.PATCH_CORRECTION["historical_e0_mc_loader_mode"] == (
        "git_bound_published_lock_snapshot"
    )
    assert module.PATCH_CORRECTION["historical_dltvm_effective_loader_called"] is False
    assert module.P1_ARTIFACT_BUILDER_RECORD == {
        "path": "src/experiments/build_closure_pipe_sequences.py",
        "bytes": 127_833,
        "sha256": "f0e653b29035acb11e39bc9a7776e7940394996d75f16bf3bccb4da30013c9cf",
    }


def test_real_published_e0_mc_reconstruction_keeps_nested_e0_mb_without_old_loaders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_loader(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("historical/effective E0-MB or E0-MC loader must not run")

    monkeypatch.setattr(
        module.e0_mc,
        "load_published_p1_sequence_historical_anfis_patch_historical_authority",
        forbidden_loader,
    )
    monkeypatch.setattr(
        module.e0_mc.e0_mb,
        "load_published_p1_sequence_builder_patch_historical_authority",
        forbidden_loader,
    )
    execution_head = module._require_commit(
        module._git("rev-parse", "HEAD"),
        context="test execution HEAD",
    )
    authority, context = module._e0_mc_historical_authority(
        execution_head=execution_head
    )
    assert authority["patch_head"] == module.E0_MC_H_COMMIT
    assert authority["lock_commit"] == module.E0_MC_P_COMMIT
    assert authority["nested_e0_mb"]["gate"] == "E0-MB"
    assert authority["nested_e0_mb"]["historical_authority_verified"] is True
    assert authority["effective_one_shot_loader_called"] is False
    assert authority["historical_loader_used"] is False
    assert authority["git_bound_lock_snapshot_used"] is True
    assert context["p1_fit_authorized"] is False


def test_real_historical_dltvm_reconstruction_never_uses_effective_loader() -> None:
    execution_head = module._require_commit(
        module._git("rev-parse", "HEAD"),
        context="test execution HEAD",
    )
    authority = module._historical_dltvm_authority(execution_head=execution_head)
    assert authority["patch_head"] == module.H_DLTVM_COMMIT
    assert authority["lock_commit"] == module.P_DLTVM_COMMIT
    assert authority["historical_effective_loader_called"] is False
    assert set(authority["superseded_components"]["paths"]) == set(
        module.DLTVM_SUPERSEDED_PATHS
    )


def test_real_e0_mc_context_matches_all_thirteen_published_p1_manifest_inputs() -> None:
    from src.experiments import train_closure_pipe as trainer

    execution_head = module._require_commit(
        module._git("rev-parse", "HEAD"),
        context="test execution HEAD",
    )
    _, context = module._e0_mc_historical_authority(execution_head=execution_head)
    published_manifest = json.loads(
        module.p1_audit.P1_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    expected_inputs = tuple(
        dict(record) for record in published_manifest["inputs"]
    )
    assert len(expected_inputs) == 13
    contract = trainer.collect_sequence_input_contract(
        model_id="P1",
        base_seed=1729,
        artifact_builder_record=module.P1_ARTIFACT_BUILDER_RECORD,
        current_runtime_builder_record=module.P1_ARTIFACT_BUILDER_RECORD,
        state_consumer_authority=context,
    )
    before = tuple(dict(record) for record in contract.manifest_input_records)
    assert before == expected_inputs
    trainer.assert_sequence_input_contract_unchanged(contract)
    assert tuple(dict(record) for record in contract.manifest_input_records) == before


def test_require_rejects_any_other_model_seed_or_device() -> None:
    for model_id, base_seed, device in (
        ("P0", 1729, "cpu"),
        ("P1", 20260612, "cpu"),
        ("P1", 1729, "cuda"),
    ):
        with pytest.raises(module.P1TemporalConsumerPatchError, match="only"):
            module.require_p1_temporal_consumer_authorized(
                model_id=model_id,
                base_seed=base_seed,
                device=device,
            )


def test_require_returns_effective_but_scientifically_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = _effective_summary()
    monkeypatch.setattr(
        module,
        "load_and_validate_p1_temporal_consumer_patch_lock",
        lambda **kwargs: ({}, summary),
    )
    observed = module.require_p1_temporal_consumer_authorized(
        model_id="P1",
        base_seed=1729,
        device="cpu",
    )
    assert observed["p1_fit_authorized"] is True
    assert observed["sequence_fit_available"] is False
    assert observed["fit_availability"] == module.FIT_AVAILABILITY


def test_require_rejects_scientific_availability_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = {**_effective_summary(), "sequence_fit_available": True}
    monkeypatch.setattr(
        module,
        "load_and_validate_p1_temporal_consumer_patch_lock",
        lambda **kwargs: ({}, summary),
    )
    with pytest.raises(module.P1TemporalConsumerPatchError, match="seals"):
        module.require_p1_temporal_consumer_authorized(
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )


@pytest.mark.parametrize(
    ("stdout", "expected"),
    (
        ("1 file pushed\n", "1 file pushed"),
        ("Everything is up to date.\n", "Everything is up to date."),
    ),
)
def test_first_targeted_dvc_push_accepts_only_closed_terminal(
    stdout: str,
    expected: str,
) -> None:
    assert locker._dvc_terminal_status(
        stdout,
        "",
        require_idempotent=False,
    ) == expected


def test_second_targeted_dvc_push_requires_exact_idempotence() -> None:
    with pytest.raises(module.P1TemporalConsumerPatchError, match="terminal evidence"):
        locker._dvc_terminal_status(
            "1 file pushed\n",
            "",
            require_idempotent=True,
        )
    assert locker._dvc_terminal_status(
        "Everything is up to date.\n",
        "",
        require_idempotent=True,
    ) == "Everything is up to date."


@pytest.mark.parametrize(
    "stdout",
    (
        "2 files pushed\n",
        "1 file pushed\nEverything is up to date.\n",
    ),
)
def test_targeted_dvc_push_rejects_multi_file_or_ambiguous_output(stdout: str) -> None:
    with pytest.raises(module.P1TemporalConsumerPatchError, match="DVC push"):
        locker._dvc_terminal_status(
            stdout,
            "",
            require_idempotent=False,
        )


def test_verification_rejects_non_idempotent_second_dvc_push() -> None:
    evidence = _verification_evidence()
    evidence["dvc_push_second"] = {
        **evidence["dvc_push_second"],
        "terminal_status": "1 file pushed",
    }
    with pytest.raises(module.P1TemporalConsumerPatchError, match="not idempotent"):
        module.validate_p1_temporal_consumer_patch_verification(evidence)


def test_effective_loader_orders_publication_before_physical_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "patch_repository": {"head": PATCH_HEAD},
        "base_authorities": {
            "e0_mc": {"context_authorization": {"gate": "E0-MC"}},
            "e0_dltvm": {},
        },
        "p1_sequence_bundle": {"commit": module.P1_BUNDLE_COMMIT},
    }
    schema: dict[str, Any] = {}
    companion: dict[str, Any] = {}
    lock_record = _record(
        module.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "external_p1_temporal_consumer_patch_lock",
    )
    companion_record = _record(
        module.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        "p1_temporal_consumer_patch_companion",
    )
    events: list[str] = []

    def load(path: Path, *, context: str) -> dict[str, Any]:
        if path == module.DEFAULT_PATCH_LOCK_PATH:
            return payload
        if path == module.DEFAULT_PATCH_LOCK_SCHEMA:
            return schema
        return companion

    def validate(*args: Any, require_physical_artifacts: bool, **kwargs: Any) -> None:
        events.append("physical" if require_physical_artifacts else "static")

    monkeypatch.setattr(module, "_load_regular_json", load)
    monkeypatch.setattr(module, "validate_p1_temporal_consumer_patch_lock_payload", validate)
    monkeypatch.setattr(
        module,
        "_file_record",
        lambda path, role: lock_record if path == module.DEFAULT_PATCH_LOCK_PATH else companion_record,
    )
    monkeypatch.setattr(module, "_expected_companion", lambda *args, **kwargs: companion)
    monkeypatch.setattr(module, "_require_commit", lambda value, **kwargs: value)
    monkeypatch.setattr(module, "_require_ancestor", lambda *args: None)
    monkeypatch.setattr(module, "_git", lambda *args: "")

    def publication(*args: Any, **kwargs: Any) -> tuple[str, dict[str, Any], dict[str, Any]]:
        events.append("publication")
        return LOCK_COMMIT, lock_record, companion_record

    monkeypatch.setattr(module, "_validate_publication_bundle", publication)
    _, summary = module.load_and_validate_p1_temporal_consumer_patch_lock(
        require_published=True,
        verify_remote=False,
    )
    assert events == ["static", "publication", "physical"]
    assert summary["p1_fit_authorized"] is True
    assert summary["sequence_fit_available"] is False


def test_publication_rejects_divergent_origin_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"patch_repository": {"head": PATCH_HEAD}}
    monkeypatch.setattr(module, "_introduced_commit", lambda path: LOCK_COMMIT)
    monkeypatch.setattr(module, "_require_commit", lambda value, **kwargs: value)
    monkeypatch.setattr(module, "_require_ancestor", lambda *args: None)
    monkeypatch.setattr(module, "_assert_paths_untouched", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "_observed_diff_entries",
        lambda *args: [
            {"status": "A", "path": module.DEFAULT_PATCH_LOCK_PATH.as_posix()},
            {"status": "A", "path": module.DEFAULT_PATCH_MANIFEST_PATH.as_posix()},
        ],
    )

    def git(*args: str) -> str:
        if args[:3] == ("rev-list", "--parents", "-n"):
            return f"{LOCK_COMMIT} {PATCH_HEAD}"
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("rev-parse", "origin/HEAD"):
            return "c" * 40
        if args[0] == "rev-parse":
            return LOCK_COMMIT
        raise AssertionError(args)

    monkeypatch.setattr(module, "_git", git)
    with pytest.raises(module.P1TemporalConsumerPatchError, match="refs diverged"):
        module._validate_publication_bundle(
            payload,
            execution_head=LOCK_COMMIT,
            verify_remote=False,
        )


def test_protocol_documents_no_model_semantics() -> None:
    text = Path("docs/closure_v1/E0_M_P1_TEMPORAL_CONSUMER_PATCH_1.md").read_text(
        encoding="utf-8"
    )
    assert "slot_status=model_unavailable" in text
    assert "fit_status=not_attempted" in text
    assert "sequence_fit_rows_unavailable" in text
    assert "p1_fit_authorized=true" in text
    assert "sequence_fit_available=false" in text
