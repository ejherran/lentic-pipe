from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from src.data.prepare_commit_artifacts import (
    has_failing_findings,
    validate_experiment_manifests,
)
from src.experiments import audit_closure_p0_model_availability as availability


def _manifest(seed: int = 314159) -> dict[str, Any]:
    return json.loads(
        Path(
            f"reports/closure_v1/02_models/P0/seed_{seed}_manifest.json"
        ).read_text(encoding="utf-8")
    )


def _record(path: Path, *, role: str | None = None) -> dict[str, Any]:
    payload = path.read_bytes()
    record: dict[str, Any] = {
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    if role is not None:
        record["role"] = role
    return record


def _fake_git_bound(path: str | Path, commit: str = "a" * 40) -> dict[str, Any]:
    return {
        **availability._file_record(path),
        "git_commit": commit,
        "git_blob": "b" * 40,
        "git_mode": "100644",
    }


def test_public_policy_and_five_published_slots_pass_read_only_audit() -> None:
    policy = availability.load_and_validate_policy()
    summary = availability.audit_repository(policy)

    assert policy["gate"] == "E0-MA"
    assert summary["status"] == "ready_to_register"
    assert summary["seed_slots"] == list(availability.EXPECTED_SEEDS)
    assert summary["slot_status_counts"] == {"model_unavailable": 5}
    assert summary["available_fit_role_sequences_per_slot"] == 8925
    assert summary["unavailable_fit_role_sequences_per_slot"] == 488
    assert summary["p1_materialized_path_count"] == 0
    assert summary["e0_m_output_count"] == 0
    assert summary["outcome_access_log_current_e0_ma_state"] == "absent"
    assert summary["outcome_access_log_required_e0_m_state"] == "present_empty"
    assert summary["side_effects"] == {
        "writes_performed": False,
        "network_commands_executed": False,
        "dvc_commands_executed": False,
        "outcome_paths_opened": False,
    }


def test_p0_evidence_chain_and_git_blobs_are_exact() -> None:
    summary = availability.audit_repository()
    slots = summary["slots"]

    assert [slot["base_seed"] for slot in slots] == list(availability.EXPECTED_SEEDS)
    assert [slot["evidence_commit"]["commit"] for slot in slots] == [
        "f4a6c3367d20deeb7416e9f0d4cbc9c3a9446a3f",
        "118b404cdc98a144fe392aa6085c49f0eb97348d",
        "f27ee8a105a623611220e7c10630efe1a676599a",
        "8d776ce31a13ebb6cc0e6c219de89f5356aed2fd",
        "1a4aa4836548756e74008fb934f56b5251d22491",
    ]
    assert all(slot["evidence_commit"]["exact_addition_count"] == 2 for slot in slots)
    assert all(slot["manifest"]["git_mode"] == "100644" for slot in slots)
    assert all(slot["report"]["git_mode"] == "100644" for slot in slots)
    assert all(len(slot["manifest"]["git_blob"]) == 40 for slot in slots)
    assert all(len(slot["report"]["git_blob"]) == 40 for slot in slots)


def test_denominator_authority_reconstructs_role_and_fit_counts() -> None:
    denominator = availability.audit_repository()["denominator_authority"]

    assert denominator["intent_origins"] == 9732
    assert denominator["successful_origins"] == 9227
    assert denominator["failed_origins"] == 505
    assert denominator["role_status_counts"] == {
        "training": {"success": 7909, "autoregressive_target_unavailable": 443},
        "model_selection": {
            "success": 1016,
            "autoregressive_target_unavailable": 45,
        },
        "calibration_threshold": {
            "success": 302,
            "autoregressive_target_unavailable": 17,
        },
    }
    assert denominator["fit_role_intent_origins"] == 9413
    assert denominator["available_fit_role_sequences"] == 8925
    assert denominator["unavailable_fit_role_sequences"] == 488
    assert denominator["holdout_overlap"] == 0
    assert denominator["post_2021_rows"] == 0
    assert denominator["per_seed_counts_must_not_be_summed_as_ecological_denominator"]


@pytest.mark.parametrize(
    ("field", "invalid_value", "message"),
    [
        ("slot_status", "available", "slot_status"),
        ("fit_status", "passed", "fit_status"),
        ("failure_reason", "", "failure_reason"),
        ("model_artifact_emitted", True, "model_artifact_emitted"),
        ("failed_slot_replaced", True, "failed_slot_replaced"),
        ("future_outcomes_accessed", True, "future_outcomes_accessed"),
    ],
)
def test_manifest_semantics_fail_closed(
    field: str,
    invalid_value: Any,
    message: str,
) -> None:
    payload = _manifest()
    payload[field] = invalid_value

    with pytest.raises(availability.P0ModelAvailabilityError, match=message):
        availability.validate_p0_manifest_semantics(payload, seed=314159)


def test_manifest_denominator_mutation_is_rejected() -> None:
    payload = _manifest()
    payload["fit_status_counts"]["autoregressive_target_unavailable"] = 487

    with pytest.raises(availability.P0ModelAvailabilityError, match="denominator"):
        availability.validate_p0_manifest_semantics(payload, seed=314159)


def test_manifest_extra_or_placeholder_key_is_rejected() -> None:
    payload = _manifest()
    payload["placeholder_checkpoint_hash"] = None

    with pytest.raises(availability.P0ModelAvailabilityError, match="keys drifted"):
        availability.validate_p0_manifest_semantics(payload, seed=314159)


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("comparison_policy", "substitution", "best_available_seed"),
        ("comparison_policy", "denominator_adjustment", "drop_unavailable"),
        ("outcome_access", "evaluation_authorized", True),
        ("registry_bundle", "registry_commit_exact_additions", 1),
    ],
)
def test_closed_schema_rejects_policy_mutations(
    section: str,
    key: str,
    value: Any,
) -> None:
    policy = availability.load_and_validate_policy()
    schema = json.loads(availability._secure_read_bytes(availability.DEFAULT_SCHEMA))
    mutated = copy.deepcopy(policy)
    mutated[section][key] = value

    with pytest.raises(Exception):
        availability.validate_json_schema(
            mutated,
            schema,
            instance_path="$.model_lock_availability_policy",
        )


def test_caller_cannot_replace_the_closed_physical_policy() -> None:
    mutated = copy.deepcopy(availability.load_and_validate_policy())
    mutated["comparison_policy"]["substitution"] = "best_available_seed"

    with pytest.raises(RuntimeError, match="Caller-supplied policy differs"):
        availability._closed_policy(mutated)


def test_p0_namespace_is_exact_and_records_all_absences() -> None:
    paths = availability.p0_slot_paths(1729)
    slot = availability.audit_repository()["slots"][0]

    assert len(paths) == 19
    assert paths["report"].as_posix().endswith("seed_1729_report.md")
    assert paths["manifest"].as_posix().endswith("seed_1729_manifest.json")
    assert paths["model_temporary"].as_posix().endswith("seed_1729.pt.tmp")
    assert paths["guard"].as_posix().endswith("P0_seed_1729.guard")
    assert slot["registered_namespace_path_count"] == 19
    assert slot["present_path_count"] == 2
    assert len(slot["absent_artifacts"]) == 17
    assert {record["state"] for record in slot["absent_artifacts"]} == {"absent"}


def test_p1_preregistry_absence_namespace_is_unique() -> None:
    paths = availability._p1_absence_paths(1729)

    assert len(paths) == 28
    assert len({path.as_posix() for path in paths}) == 28
    assert any(path.as_posix().endswith("sequences/P1/seed_1729.parquet.dvc") for path in paths)
    assert any(path.as_posix().endswith("P1_seed_1729.guard") for path in paths)


def test_registry_namespace_includes_both_finals_temps_and_guards() -> None:
    paths = availability._registry_namespace_paths()

    assert paths == (
        availability.DEFAULT_REGISTRY,
        Path(f"{availability.DEFAULT_REGISTRY}.tmp"),
        availability.DEFAULT_COMPANION,
        Path(f"{availability.DEFAULT_COMPANION}.tmp"),
        *availability.REGISTRY_GUARD_PATHS,
    )


def test_audit_rejects_any_preregistered_registry_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = availability.p0_slot_paths(1729)["report"]
    monkeypatch.setattr(availability, "_registry_namespace_paths", lambda: (existing,))

    with pytest.raises(availability.P0ModelAvailabilityError, match="not pristine"):
        availability.audit_repository()


def _publication_fixture(head: str = "a" * 40) -> dict[str, Any]:
    components = [
        {**_fake_git_bound(path, head), "role": "h_slice_component"}
        for path in availability.H_SLICE_COMPONENTS
    ]
    return {
        "h_slice_head": head,
        "h_slice_parent": availability.P0_CLOSURE_HEAD,
        "branch": "main",
        "local_branch_ref": "refs/heads/main",
        "tracking_ref": "origin/main",
        "remote_ref": "refs/heads/main",
        "refs": {
            "head": head,
            "main": head,
            "tracking": head,
            "origin_head": head,
        },
        "remote_main": head,
        "h_slice_diff": [
            {"status": "A", "path": path.as_posix()}
            for path in availability.H_SLICE_COMPONENTS
        ],
        "h_slice_components": components,
        "hardened_writer_dependency": {
            **_fake_git_bound(availability.HARDENED_WRITER, head),
            "role": "hardened_writer_dependency",
        },
    }


def test_registry_payload_is_non_self_authorizing_and_has_no_placeholder_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = availability.load_and_validate_policy()
    audit = availability.audit_repository(policy)
    monkeypatch.setattr(
        availability,
        "_git_bound_record",
        lambda commit, path: _fake_git_bound(path, commit),
    )
    payload = availability.build_registry_payload(
        policy,
        audit,
        _publication_fixture(),
    )

    assert payload["status"] == "completed"
    assert payload["publication_contract"]["effective_in_payload"] is False
    assert payload["publication_contract"]["exact_addition_count"] == 2
    assert payload["comparison_disposition"]["unavailable_status"] == (
        "not_estimable_model_unavailable"
    )
    assert payload["comparison_disposition"]["family_membership_retained"] is True
    assert payload["comparison_disposition"]["p_value_policy"] == "not_emitted"
    assert payload["p1_progression"]["p1_fit_authorized_by_this_policy"] is False
    assert payload["outcome_access"]["evaluation_authorized"] is False

    def walk(value: Any) -> None:
        assert value is not None
        if isinstance(value, Mapping):
            assert "p_value" not in value
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)


def test_companion_uses_generic_completed_manifest_dialect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = availability.load_and_validate_policy()
    audit = availability.audit_repository(policy)
    monkeypatch.setattr(
        availability,
        "_git_bound_record",
        lambda commit, path: _fake_git_bound(path, commit),
    )
    registry = availability.build_registry_payload(
        policy,
        audit,
        _publication_fixture(),
    )
    registry_record = {
        "path": availability.DEFAULT_REGISTRY.as_posix(),
        "bytes": 123,
        "sha256": "c" * 64,
        "role": "p0_model_availability_registry",
    }

    companion = availability.build_companion_payload(registry, registry_record)

    assert companion["status"] == "completed"
    assert companion["script"]["role"] == "generating_script"
    assert companion["inputs"]
    assert companion["outputs"] == [registry_record]
    assert companion["completion_marker_written_last"] is True
    assert companion["registry_effective_in_payload"] is False
    assert all({"path", "bytes", "sha256"}.issubset(record) for record in companion["inputs"])


def _complete_registry_contract(
    monkeypatch: pytest.MonkeyPatch,
    *,
    h_slice_head: str = "a" * 40,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    policy = availability.load_and_validate_policy()
    audit = availability.audit_repository(policy)
    publication = _publication_fixture(h_slice_head)
    monkeypatch.setattr(
        availability,
        "_git_bound_record",
        lambda commit, path: _fake_git_bound(path, commit),
    )
    registry = availability.build_registry_payload(
        policy,
        audit,
        publication,
        created_at_utc="2026-08-05T00:00:00Z",
    )
    registry_bytes = availability._canonical_json(registry)
    registry_record = {
        "path": availability.DEFAULT_REGISTRY.as_posix(),
        "role": "p0_model_availability_registry",
        "bytes": len(registry_bytes),
        "sha256": hashlib.sha256(registry_bytes).hexdigest(),
    }
    companion = availability.build_companion_payload(registry, registry_record)
    return policy, audit, publication, registry, companion, registry_record


def _replace_nested(payload: dict[str, Any], path: tuple[Any, ...], value: Any) -> None:
    target: Any = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def test_registry_bundle_validator_reconstructs_every_authoritative_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy, audit, publication, registry, companion, registry_record = (
        _complete_registry_contract(monkeypatch)
    )
    mutations = [
        ("registry", ("denominator_authority", "intent_origins"), 0),
        ("registry", ("slot_count",), 4),
        ("registry", ("slots",), []),
        (
            "registry",
            ("comparison_disposition", "unavailable_status"),
            "estimable",
        ),
        ("registry", ("p1_progression", "p1_fit_authorized_by_this_policy"), True),
        ("registry", ("e0_m_status",), "completed"),
        ("registry", ("outcome_access", "evaluation_authorized"), True),
        ("registry", ("sealed_authorities",), []),
        ("registry", ("repository_binding", "h_slice_components"), []),
        ("registry", ("repository_binding", "hardened_writer_dependency"), {}),
        ("companion", ("script",), {}),
        ("companion", ("inputs",), []),
        ("companion", ("outputs",), []),
        ("companion", ("completion_marker_written_last",), False),
    ]

    for target_name, path, value in mutations:
        mutated_registry = copy.deepcopy(registry)
        mutated_companion = copy.deepcopy(companion)
        target = mutated_registry if target_name == "registry" else mutated_companion
        _replace_nested(target, path, value)
        with pytest.raises(RuntimeError):
            availability.validate_registry_bundle_payloads(
                policy,
                audit,
                publication,
                mutated_registry,
                mutated_companion,
                registry_record,
            )


def test_registry_bundle_validator_accepts_exact_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy, audit, publication, registry, companion, registry_record = (
        _complete_registry_contract(monkeypatch)
    )

    result = availability.validate_registry_bundle_payloads(
        policy,
        audit,
        publication,
        registry,
        companion,
        registry_record,
    )

    assert result["status"] == "registry_bundle_payloads_valid"
    assert result["slot_count"] == 5


def test_generic_precommit_manifest_covers_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    registry = Path("reports/closure_v1/00_protocol/p0_model_availability_registry.json")
    companion = Path(
        "reports/closure_v1/00_protocol/p0_model_availability_registry_manifest.json"
    )
    script = Path("src/experiments/audit_closure_p0_model_availability.py")
    source = Path("configs/closure_v1/model_lock_availability_policy.yaml")
    registry.parent.mkdir(parents=True)
    script.parent.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    registry.write_text('{"status":"completed"}\n', encoding="utf-8")
    script.write_text("print('ok')\n", encoding="utf-8")
    source.write_text("status: ready_to_lock\n", encoding="utf-8")
    companion.write_text(
        json.dumps(
            {
                "status": "completed",
                "script": _record(script),
                "inputs": [_record(source)],
                "outputs": [_record(registry)],
                "completion_marker_written_last": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    findings = validate_experiment_manifests(
        staged_paths={registry, companion},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=True,
    )

    assert not has_failing_findings(findings)


def test_cli_has_closed_modes_and_rejects_path_overrides() -> None:
    assert availability.parse_args(["--check-only"]).check_only
    assert availability.parse_args(["--generate"]).generate
    assert availability.parse_args(["--validate-published"]).validate_published
    with pytest.raises(SystemExit):
        availability.parse_args(["--check-only", "--output", "elsewhere.json"])


def test_h_slice_publication_binding_requires_exact_direct_child_and_5a(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "a" * 40
    policy = availability.load_and_validate_policy()
    bundle = policy["registry_bundle"]

    def git(*arguments: str) -> str:
        if arguments and arguments[0] == "status":
            return ""
        if arguments[:2] == ("rev-parse", "HEAD"):
            return head
        if arguments[:2] in {
            ("rev-parse", "main"),
            ("rev-parse", "origin/main"),
            ("rev-parse", "origin/HEAD"),
        }:
            return head
        if arguments[:3] == ("symbolic-ref", "--quiet", "--short"):
            return "main"
        if arguments and arguments[0] == "ls-remote":
            return f"{head}\trefs/heads/main"
        raise AssertionError(f"unexpected git call: {arguments}")

    monkeypatch.setattr(availability, "_git", git)
    monkeypatch.setattr(
        availability,
        "_commit_parent",
        lambda commit: availability.P0_CLOSURE_HEAD,
    )
    monkeypatch.setattr(
        availability,
        "_commit_additions",
        lambda commit: [
            {"status": "A", "path": path}
            for path in bundle["h_slice_paths"]
        ],
    )
    monkeypatch.setattr(
        availability,
        "_git_bound_record",
        lambda commit, path: _fake_git_bound(path, commit),
    )

    publication = availability._require_h_slice_published(policy)

    assert publication["h_slice_head"] == head
    assert publication["h_slice_parent"] == availability.P0_CLOSURE_HEAD
    assert len(publication["h_slice_diff"]) == 5
    assert len(publication["h_slice_components"]) == 5


def test_h_slice_publication_binding_rejects_non_direct_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = availability.load_and_validate_policy()

    def git(*arguments: str) -> str:
        if arguments and arguments[0] == "status":
            return ""
        if arguments[:2] == ("rev-parse", "HEAD"):
            return "a" * 40
        raise AssertionError(f"unexpected git call: {arguments}")

    monkeypatch.setattr(availability, "_git", git)
    monkeypatch.setattr(availability, "_commit_parent", lambda _commit: "b" * 40)

    with pytest.raises(RuntimeError, match="direct child"):
        availability._require_h_slice_published(policy)


def test_generation_revalidation_rejects_any_unowned_worktree_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = availability.load_and_validate_policy()
    publication = _publication_fixture()
    monkeypatch.setattr(
        availability,
        "_reconstruct_h_slice_publication",
        lambda *_a, **_k: publication,
    )
    monkeypatch.setattr(
        availability,
        "_git",
        lambda *_arguments: "\n".join(
            (
                f"?? {availability.DEFAULT_REGISTRY.as_posix()}",
                f"?? {availability.DEFAULT_COMPANION.as_posix()}",
                "?? unrelated.txt",
            )
        ),
    )

    with pytest.raises(RuntimeError, match="beyond the owned two-file bundle"):
        availability._revalidate_h_slice_during_generation(policy, publication)


def _patch_writer_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(availability, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(availability.hardened, "PROJECT_ROOT", tmp_path)
    (tmp_path / availability.DEFAULT_REGISTRY.parent).mkdir(parents=True)


def _patch_generation_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_writer_root(tmp_path, monkeypatch)
    monkeypatch.setattr(availability, "load_and_validate_policy", lambda: {})
    audit = {"stable": True}
    publication = {"stable": True}
    registry = {
        "registry_version": "closure_p0_model_availability_registry_v1",
        "status": "completed",
        "created_at_utc": "2026-08-05T00:00:00Z",
        "repository_binding": {
            "h_slice_components": [],
            "hardened_writer_dependency": {
                "path": "dependency.py",
                "bytes": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            },
        },
        "sealed_authorities": [],
        "denominator_authority": {
            "sequence_manifest": {
                "path": "denominator.json",
                "bytes": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            },
            "sequence_summary": {
                "path": "denominator.csv",
                "bytes": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            },
        },
        "slots": [],
    }
    monkeypatch.setattr(availability, "audit_repository", lambda *_a, **_k: audit)
    monkeypatch.setattr(
        availability,
        "_require_h_slice_published",
        lambda *_a, **_k: publication,
    )
    monkeypatch.setattr(
        availability,
        "_revalidate_h_slice_during_generation",
        lambda *_a, **_k: publication,
    )
    monkeypatch.setattr(
        availability,
        "build_registry_payload",
        lambda *_a, **_k: registry,
    )

    def companion(_registry: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "manifest_version": "closure_p0_model_availability_registry_manifest_v1",
            "status": "completed",
            "script": dict(record),
            "inputs": [dict(record)],
            "outputs": [dict(record)],
            "completion_marker_written_last": True,
        }

    monkeypatch.setattr(availability, "build_companion_payload", companion)
    monkeypatch.setattr(
        availability,
        "validate_registry_bundle_payloads",
        lambda *_a, **_k: {"status": "mechanical_writer_fixture_valid"},
    )


def test_registry_transaction_writes_two_files_manifest_last_and_releases_guards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_generation_inputs(tmp_path, monkeypatch)
    real_publish = availability.hardened._publish_guarded_bytes
    order: list[str] = []

    def tracked_publish(*args: Any, **kwargs: Any) -> Any:
        destination = args[1]
        order.append(Path(destination).name)
        return real_publish(*args, **kwargs)

    monkeypatch.setattr(availability.hardened, "_publish_guarded_bytes", tracked_publish)

    result = availability.generate_registry_bundle()

    assert result["status"] == "registry_bundle_written_unpublished"
    assert result["registry_effective"] is False
    assert order == [availability.DEFAULT_REGISTRY.name, availability.DEFAULT_COMPANION.name]
    assert (tmp_path / availability.DEFAULT_REGISTRY).is_file()
    assert (tmp_path / availability.DEFAULT_COMPANION).is_file()
    assert not (tmp_path / f"{availability.DEFAULT_REGISTRY}.tmp").exists()
    assert not (tmp_path / f"{availability.DEFAULT_COMPANION}.tmp").exists()
    assert all(not (tmp_path / path).exists() for path in availability.REGISTRY_GUARD_PATHS)


def test_registry_transaction_is_exclusive_and_no_clobber(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_writer_root(tmp_path, monkeypatch)
    guards = availability._acquire_registry_guards()
    try:
        with pytest.raises(RuntimeError, match="existing E0-MA registry namespace"):
            availability._acquire_registry_guards()
    finally:
        for guard in reversed(guards):
            availability.hardened._release_guard(guard)

    output = tmp_path / availability.DEFAULT_REGISTRY
    output.write_text("third party\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="existing E0-MA registry namespace"):
        availability._acquire_registry_guards()
    assert output.read_text(encoding="utf-8") == "third party\n"


def test_registry_guard_rejects_symlinked_tmp_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_writer_root(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "tmp").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="linked or invalid ancestor"):
        availability._acquire_registry_guards()
    assert not any(outside.iterdir())


def test_registry_transaction_rolls_back_after_second_publication_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_generation_inputs(tmp_path, monkeypatch)
    real_publish = availability.hardened._publish_guarded_bytes
    calls = 0

    def fail_second(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected companion failure")
        return real_publish(*args, **kwargs)

    monkeypatch.setattr(availability.hardened, "_publish_guarded_bytes", fail_second)

    with pytest.raises(RuntimeError, match="registry transaction failed"):
        availability.generate_registry_bundle()

    assert not (tmp_path / availability.DEFAULT_REGISTRY).exists()
    assert not (tmp_path / availability.DEFAULT_COMPANION).exists()
    assert all(not (tmp_path / path).exists() for path in availability.REGISTRY_GUARD_PATHS)


def test_registry_transaction_rolls_back_when_final_reconstruction_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_generation_inputs(tmp_path, monkeypatch)

    def reject_reconstruction(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise availability.P0ModelAvailabilityError(
            "injected final reconstruction failure"
        )

    monkeypatch.setattr(
        availability,
        "validate_registry_bundle_payloads",
        reject_reconstruction,
    )

    with pytest.raises(RuntimeError, match="final reconstruction failure"):
        availability.generate_registry_bundle()

    assert not (tmp_path / availability.DEFAULT_REGISTRY).exists()
    assert not (tmp_path / availability.DEFAULT_COMPANION).exists()
    assert all(not (tmp_path / path).exists() for path in availability.REGISTRY_GUARD_PATHS)


def test_registry_rollback_preserves_a_replacement_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_generation_inputs(tmp_path, monkeypatch)
    real_publish = availability.hardened._publish_guarded_bytes
    calls = 0
    replacement = b"third-party replacement\n"

    def replace_then_fail(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            registry = tmp_path / availability.DEFAULT_REGISTRY
            registry.unlink()
            registry.write_bytes(replacement)
            raise RuntimeError("injected replacement race")
        return real_publish(*args, **kwargs)

    monkeypatch.setattr(
        availability.hardened,
        "_publish_guarded_bytes",
        replace_then_fail,
    )

    with pytest.raises(RuntimeError, match="registry transaction failed"):
        availability.generate_registry_bundle()

    assert (tmp_path / availability.DEFAULT_REGISTRY).read_bytes() == replacement
    assert not (tmp_path / availability.DEFAULT_COMPANION).exists()


@pytest.mark.parametrize("broken", [False, True])
def test_secure_reader_rejects_final_symlinks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    broken: bool,
) -> None:
    monkeypatch.setattr(availability, "PROJECT_ROOT", tmp_path)
    artifact = tmp_path / "reports/artifact.json"
    artifact.parent.mkdir(parents=True)
    target = tmp_path / "target.json"
    if not broken:
        target.write_text("{}\n", encoding="utf-8")
    artifact.symlink_to(target)

    with pytest.raises(RuntimeError, match="linked"):
        availability._secure_read_bytes(Path("reports/artifact.json"))


def test_secure_reader_rejects_symlinked_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(availability, "PROJECT_ROOT", tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "artifact.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "reports").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="linked or invalid ancestor"):
        availability._secure_read_bytes(Path("reports/artifact.json"))


def test_secure_reader_rejects_same_inode_metadata_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(availability, "PROJECT_ROOT", tmp_path)
    artifact = tmp_path / "reports/artifact.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b'{"stable":true}\n')
    initial = artifact.stat()
    real_read = os.read
    mutated = False

    def mutate_after_first_read(descriptor: int, size: int) -> bytes:
        nonlocal mutated
        payload = real_read(descriptor, size)
        if payload and not mutated:
            mutated = True
            os.utime(
                artifact,
                ns=(initial.st_atime_ns, initial.st_mtime_ns + 1_000_000_000),
            )
        return payload

    monkeypatch.setattr(availability.os, "read", mutate_after_first_read)

    with pytest.raises(RuntimeError, match="identity drifted"):
        availability._secure_read_bytes(Path("reports/artifact.json"))


def test_check_only_never_invokes_remote_or_dvc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_run = subprocess.run
    commands: list[tuple[str, ...]] = []

    def tracked_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(command, list):
            commands.append(tuple(str(part) for part in command))
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(availability.subprocess, "run", tracked_run)

    summary = availability.audit_repository()

    assert summary["side_effects"]["network_commands_executed"] is False
    assert all("ls-remote" not in command for command in commands)
    assert all(not command or command[0] != "dvc" for command in commands)


def _published_loader_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    remote_matches: bool = True,
    audit_error: str | None = None,
) -> dict[str, Any]:
    registry_commit = "c" * 40
    h_head = "b" * 40
    policy, audit, publication, registry, companion, registry_record = (
        _complete_registry_contract(monkeypatch, h_slice_head=h_head)
    )
    companion_bytes = availability._canonical_json(companion)
    registry_git_record = {
        **registry_record,
        "git_commit": registry_commit,
        "git_blob": "1" * 40,
        "git_mode": "100644",
    }
    registry_git_record.pop("role")
    companion_git_record = {
        "path": availability.DEFAULT_COMPANION.as_posix(),
        "bytes": len(companion_bytes),
        "sha256": hashlib.sha256(companion_bytes).hexdigest(),
        "git_commit": registry_commit,
        "git_blob": "2" * 40,
        "git_mode": "100644",
    }
    monkeypatch.setattr(availability, "load_and_validate_policy", lambda: policy)
    monkeypatch.setattr(
        availability,
        "_load_canonical_json",
        lambda path, **_kwargs: (
            registry if path == availability.DEFAULT_REGISTRY else companion
        ),
    )
    git_calls: list[tuple[str, ...]] = []

    def git(*arguments: str) -> str:
        git_calls.append(arguments)
        if arguments[:3] == ("log", "-1", "--format=%H"):
            return registry_commit
        if arguments[:2] == ("rev-parse", "HEAD"):
            return registry_commit
        if arguments[:2] in {
            ("rev-parse", "main"),
            ("rev-parse", "origin/main"),
            ("rev-parse", "origin/HEAD"),
        }:
            return registry_commit
        if arguments[:3] == ("symbolic-ref", "--quiet", "--short"):
            return "main"
        if arguments and arguments[0] == "status":
            return ""
        if arguments and arguments[0] == "ls-remote":
            remote = registry_commit if remote_matches else "e" * 40
            return f"{remote}\trefs/heads/main"
        raise AssertionError(f"unexpected git call: {arguments}")

    monkeypatch.setattr(availability, "_git", git)
    monkeypatch.setattr(
        availability,
        "_commit_parent",
        lambda commit: h_head if commit == registry_commit else availability.P0_CLOSURE_HEAD,
    )

    def additions(commit: str) -> list[dict[str, str]]:
        if commit == registry_commit:
            paths = (availability.DEFAULT_REGISTRY, availability.DEFAULT_COMPANION)
        else:
            paths = availability.H_SLICE_COMPONENTS
        return [{"status": "A", "path": path.as_posix()} for path in paths]

    monkeypatch.setattr(availability, "_commit_additions", additions)

    def bound_record(commit: str, path: str | Path) -> dict[str, Any]:
        relative = Path(path)
        if relative == availability.DEFAULT_REGISTRY:
            return registry_git_record
        if relative == availability.DEFAULT_COMPANION:
            return companion_git_record
        return _fake_git_bound(relative, commit)

    monkeypatch.setattr(
        availability,
        "_git_bound_record",
        bound_record,
    )
    audit_calls: list[tuple[Path, ...]] = []

    def repeated_audit(
        _policy: Mapping[str, Any] | None = None,
        *,
        allowed_registry_entries: tuple[Path, ...] = (),
    ) -> dict[str, Any]:
        audit_calls.append(tuple(allowed_registry_entries))
        if audit_error is not None:
            raise availability.P0ModelAvailabilityError(audit_error)
        return audit

    monkeypatch.setattr(availability, "audit_repository", repeated_audit)
    monkeypatch.setattr(
        availability,
        "_reconstruct_h_slice_publication",
        lambda _policy, *, h_slice_head: publication,
    )
    return {
        "git_calls": git_calls,
        "audit_calls": audit_calls,
        "registry_commit": registry_commit,
    }


def test_published_loader_is_the_only_effective_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _published_loader_fixture(monkeypatch)

    result = availability.load_published_registry()

    assert result["registry_effective"] is True
    assert result["p1_sequence_builder_authorized"] is True
    assert result["first_authorized_p1_sequence_seed"] == 1729
    assert result["p1_fit_authorized"] is False
    assert result["e0_m_authorized"] is False
    assert result["evaluation_authorized"] is False
    assert result["reconstruction"]["status"] == "registry_bundle_payloads_valid"
    assert fixture["audit_calls"] == [
        (availability.DEFAULT_REGISTRY, availability.DEFAULT_COMPANION)
    ]
    assert any(call and call[0] == "ls-remote" for call in fixture["git_calls"])


def test_published_loader_rejects_live_remote_divergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _published_loader_fixture(monkeypatch, remote_matches=False)

    with pytest.raises(RuntimeError, match="Live remote main differs"):
        availability.load_published_registry()


def test_published_loader_has_no_remote_verification_bypass() -> None:
    assert "verify_remote" not in inspect.signature(
        availability.load_published_registry
    ).parameters


@pytest.mark.parametrize(
    "message",
    [
        "P1 materialization predates the P0 registry",
        "E0-M outputs already exist",
        "Outcome access log must remain absent",
        "Registry bundle namespace is not pristine",
    ],
)
def test_published_loader_rechecks_all_post_registry_absence_gates(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
) -> None:
    _published_loader_fixture(monkeypatch, audit_error=message)

    with pytest.raises(RuntimeError, match=message):
        availability.load_published_registry()
