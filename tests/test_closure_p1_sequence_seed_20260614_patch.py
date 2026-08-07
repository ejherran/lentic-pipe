from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from typing import Any, cast

import pytest

from src.experiments import build_closure_pipe_sequences as sequence_builder
from src.experiments import closure_contract
from src.experiments import closure_p1_sequence_seed_20260613_patch as e0_mj
from src.experiments import (
    closure_p1_temporal_consumer_seed_20260613_patch as e0_mk,
)
from src.experiments import closure_p1_sequence_seed_20260614_patch as patch
from src.experiments import lock_closure_p1_sequence_seed_20260614_patch as locker


PATCH_HEAD = "a" * 40


def _record(path: str, role: str, token: str = "0") -> dict[str, Any]:
    return {
        "path": path,
        "role": role,
        "bytes": 1,
        "sha256": token * 64,
    }


def _effective_summary() -> dict[str, Any]:
    return {
        "status": "published_p1_sequence_seed_20260614_patch_valid",
        "gate": patch.PATCH_GATE,
        "patch_head": PATCH_HEAD,
        "lock_commit": "b" * 40,
        "execution_head": "b" * 40,
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_e0_mj_verified": True,
        "historical_e0_mk_verified": True,
        "p1_1729_publication_verified": True,
        "p1_20260612_publication_verified": True,
        "p1_20260613_publication_verified": True,
        "anfis_20260614_state_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": True,
        "progression_prelock_verified": True,
        "authorization_inputs": [
            _record(
                patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
                "external_p1_sequence_seed_20260614_patch_lock",
                "a",
            ),
            _record(
                patch.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
                "p1_sequence_seed_20260614_patch_companion",
                "b",
            ),
        ],
        **patch.EFFECTIVE_AUTHORIZATIONS,
    }


def _command_evidence(command: tuple[str, ...]) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": "a" * 64,
        "stderr_sha256": "b" * 64,
        "stdout_line_count": 1,
        "stderr_line_count": 0,
    }


def _verification(*, focused_count: int) -> dict[str, Any]:
    focused = _command_evidence(patch.FOCUSED_TEST_COMMAND)
    focused.update(
        {
            "test_count": focused_count,
            "skipped_count": 0,
            "deselected_count": 0,
        }
    )
    return {
        "schema_subset_preflight": (
            patch.preflight_p1_sequence_seed_20260614_patch_schema()
        ),
        "full_type_check": _command_evidence(patch.TYPE_CHECK_COMMAND),
        "focused_tests": focused,
        "poetry_check": _command_evidence(patch.POETRY_CHECK_COMMAND),
        "publication_guard": _command_evidence(patch.PUBLICATION_GUARD_COMMAND),
        "git_diff_check": _command_evidence(patch.DIFF_CHECK_COMMAND),
    }


def test_h_patch_scope_is_exact_two_modified_plus_five_added() -> None:
    assert patch.PATCH_BASE_COMMIT == patch.P1_20260613_CONSUMER_COMMIT
    assert patch.PATCH_MODIFIED_PATHS == (
        "src/experiments/build_closure_pipe_sequences.py",
        "tests/test_build_closure_pipe_sequences.py",
    )
    assert len(patch.PATCH_PATHS) == 7
    assert len(patch.PATCH_ADDED_PATHS) == 5
    assert set(patch.PATCH_MODIFIED_PATHS).isdisjoint(patch.PATCH_ADDED_PATHS)


def test_authority_is_exclusive_to_the_next_p1_builder_slot() -> None:
    assert patch.AUTHORIZED_MODEL_ID == "P1"
    assert patch.AUTHORIZED_BASE_SEED == 20_260_614
    assert patch.PATCH_AUTHORIZATIONS["p1_sequence_builder_authorized"] is False
    assert patch.EFFECTIVE_AUTHORIZATIONS["p1_sequence_builder_authorized"] is True
    assert patch.PATCH_AUTHORIZATIONS["publication_required"] is True
    for field in (
        "batch_seed_execution_authorized",
        "retry_authorized",
        "p1_consumer_authorized",
        "p1_fit_authorized",
        "fit_attempt_authorized",
        "replacement_authorized",
        "dvc_commands_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "future_outcomes_accessed",
    ):
        assert patch.EFFECTIVE_AUTHORIZATIONS[field] is False


def test_real_historical_e0_mj_authority_avoids_effective_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        e0_mj,
        "load_and_validate_p1_sequence_seed_20260613_patch_lock",
        lambda: pytest.fail("effective E0-MJ loader must not run"),
    )
    authority = patch._historical_e0_mj_authority(
        execution_head=patch._git("rev-parse", "HEAD")
    )
    assert authority["patch_head"] == patch.E0_MJ_H_COMMIT
    assert authority["lock_commit"] == patch.E0_MJ_P_COMMIT
    assert authority["superseded_components"]["count"] == 2
    assert authority["preserved_components"]["count"] == 5
    assert authority["effective_loader_called"] is False


def test_real_historical_e0_mk_authority_avoids_effective_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        e0_mk,
        "load_and_validate_p1_temporal_consumer_seed_20260613_patch_lock",
        lambda: pytest.fail("effective E0-MK loader must not run"),
    )
    authority = patch._historical_e0_mk_authority(
        execution_head=patch._git("rev-parse", "HEAD")
    )
    assert authority["patch_head"] == patch.E0_MK_H_COMMIT
    assert authority["lock_commit"] == patch.E0_MK_P_COMMIT
    assert authority["preserved_components"]["count"] == len(e0_mk.PATCH_PATHS)
    assert authority["effective_loader_called"] is False


def test_real_p1_1729_publication_is_bound_as_model_unavailable() -> None:
    publication = patch._published_p1_1729_bundle(
        execution_head=patch._git("rev-parse", "HEAD")
    )
    assert publication["sequence_commit"] == e0_mj.P1_1729_SEQUENCE_COMMIT
    assert publication["consumer_commit"] == patch.P1_1729_CONSUMER_COMMIT
    assert len(publication["records"]) == 6
    assert publication["model_unavailable_semantics_verified"] is True
    assert publication["completion_marker_written_last"] is True
    assert publication["future_outcomes_accessed"] is False


def test_real_p1_20260612_publication_is_bound_as_model_unavailable() -> None:
    publication = patch._published_p1_20260612_bundle(
        execution_head=patch._git("rev-parse", "HEAD")
    )
    assert publication["sequence_commit"] == patch.P1_20260612_SEQUENCE_COMMIT
    assert publication["consumer_commit"] == patch.P1_20260612_CONSUMER_COMMIT
    assert len(publication["records"]) == 6
    assert publication["model_unavailable_semantics_verified"] is True
    assert publication["completion_marker_written_last"] is True
    assert publication["future_outcomes_accessed"] is False


def test_real_p1_20260613_publication_is_bound_as_model_unavailable() -> None:
    publication = patch._published_p1_20260613_bundle(
        execution_head=patch._git("rev-parse", "HEAD")
    )
    assert publication["sequence_commit"] == patch.P1_20260613_SEQUENCE_COMMIT
    assert publication["consumer_commit"] == patch.P1_20260613_CONSUMER_COMMIT
    assert len(publication["records"]) == 6
    assert publication["model_unavailable_semantics_verified"] is True
    assert publication["completion_marker_written_last"] is True
    assert publication["future_outcomes_accessed"] is False


def test_p1_1729_publication_rejects_semantic_manifest_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = json.loads(
        patch.P1_1729_MODEL_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    manifest["fit_status"] = "passed"
    monkeypatch.setattr(patch, "_load_regular_json", lambda *_args, **_kwargs: manifest)
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="model-unavailable manifest drifted",
    ):
        patch._published_p1_1729_bundle(
            execution_head=patch._git("rev-parse", "HEAD")
        )


def test_p1_20260612_publication_rejects_denominator_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = json.loads(
        patch.P1_20260612_MODEL_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    manifest["fit_status_counts"]["success"] = 8_924
    monkeypatch.setattr(patch, "_load_regular_json", lambda *_args, **_kwargs: manifest)
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="model-unavailable manifest drifted",
    ):
        patch._published_p1_20260612_bundle(
            execution_head=patch._git("rev-parse", "HEAD")
        )


def test_p1_20260613_publication_rejects_semantic_manifest_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = json.loads(
        patch.P1_20260613_MODEL_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    manifest["failure_reason"] = "drifted"
    monkeypatch.setattr(patch, "_load_regular_json", lambda *_args, **_kwargs: manifest)
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="model-unavailable manifest drifted",
    ):
        patch._published_p1_20260613_bundle(
            execution_head=patch._git("rev-parse", "HEAD")
        )


def test_real_anfis_20260614_state_bundle_is_modern_and_available() -> None:
    state = patch._anfis_20260614_state_bundle(
        execution_head=patch._git("rev-parse", "HEAD")
    )
    assert state["publication_commit"] == patch.ANFIS_20260614_COMMIT
    assert len(state["records"]) == 3
    assert state["slot_status"] == "available"
    assert state["fit_status"] == "passed"
    assert state["state_manifest_verified"] is True
    assert state["future_outcomes_accessed"] is False


def test_anfis_20260614_manifest_does_not_activate_the_1729_adapter() -> None:
    manifest = json.loads(
        patch.ANFIS_20260614_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    assert sequence_builder._historical_anfis_consumer_context(
        manifest,
        consumer_authority=None,
    ) is None


def test_real_anfis_20260614_manifest_is_consumable_under_ml_authority() -> None:
    manifest = json.loads(
        patch.ANFIS_20260614_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    assert sequence_builder.validate_state_slot_manifest(
        manifest,
        model_id="P1",
        base_seed=patch.AUTHORIZED_BASE_SEED,
        state_path=patch.ANFIS_20260614_STATE_PATH,
        consumer_authority=_effective_summary(),
    ) == (True, "", False)


def test_anfis_20260614_bundle_rejects_seed_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = json.loads(
        patch.ANFIS_20260614_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    manifest["base_seed"] = 1729
    monkeypatch.setattr(patch, "_load_regular_json", lambda *_args, **_kwargs: manifest)
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="ANFIS 20260614 manifest drifted",
    ):
        patch._anfis_20260614_state_bundle(
            execution_head=patch._git("rev-parse", "HEAD")
        )


def test_target_namespace_is_exactly_28_absent_paths() -> None:
    paths = patch.p1_seed_20260614_namespace_paths()
    contract = patch.p1_seed_20260614_namespace_absence()
    assert len(paths) == len({path.as_posix() for path in paths}) == 28
    assert contract["model_id"] == "P1"
    assert contract["base_seed"] == 20_260_614
    assert contract["paths"] == [path.as_posix() for path in paths]
    assert contract["all_absent_at_lock"] is True


def test_real_progression_has_exactly_three_closed_p1_bundles() -> None:
    progression = patch.closure_progression_prelock()
    assert progression["p1_seed_order"] == [
        1729,
        20_260_612,
        20_260_613,
        20_260_614,
        314159,
    ]
    assert progression["p1_path_count"] == 140
    assert progression["completed_seeds"] == [1729, 20_260_612, 20_260_613]
    assert progression["completed_seed_present_count"] == 18
    assert progression["remaining_absent_count"] == 122
    assert progression["prior_seed_residual_absent_count"] == 66
    assert progression["target_seed_absent_count"] == 28
    assert progression["later_seed_absent_count"] == 28
    assert progression["next_authorized_seed"] == 20_260_614
    assert progression["e0_m_output_count"] == 0
    assert progression["outcome_access_log_state"] == "absent"


def test_target_namespace_rejects_any_preexisting_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = patch.p1_seed_20260614_namespace_paths()[0]
    monkeypatch.setattr(patch, "_path_entry_exists", lambda path: path == target)
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="namespace is not pristine",
    ):
        patch.p1_seed_20260614_namespace_absence()


def test_progression_rejects_an_outcome_access_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_exists = patch._path_entry_exists
    monkeypatch.setattr(
        patch,
        "_path_entry_exists",
        lambda path: path == patch.availability.OUTCOME_ACCESS_LOG or real_exists(path),
    )
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="Closure progression is not pristine",
    ):
        patch.closure_progression_prelock()


def test_progression_rejects_any_e0_m_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_exists = patch._path_entry_exists
    forbidden = patch.availability.E0_M_OUTPUTS[0]
    monkeypatch.setattr(
        patch,
        "_path_entry_exists",
        lambda path: path == forbidden or real_exists(path),
    )
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="Closure progression is not pristine",
    ):
        patch.closure_progression_prelock()


@pytest.mark.parametrize(
    ("model_id", "base_seed"),
    (
        ("P0", 20_260_614),
        ("P1", 1729),
        ("P1", 20_260_612),
        ("P1", 20_260_613),
        ("P1", 314159),
        ("P1", None),
    ),
)
def test_gate_rejects_nonexclusive_identity_before_loading(
    monkeypatch: pytest.MonkeyPatch,
    model_id: str,
    base_seed: int | None,
) -> None:
    monkeypatch.setattr(
        patch,
        "load_and_validate_p1_sequence_seed_20260614_patch_lock",
        lambda: pytest.fail("loader must not run for an unauthorized identity"),
    )
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="only the one-shot P1 sequence build for seed 20260614",
    ):
        patch.require_p1_sequence_seed_20260614_authorized(model_id, base_seed)


def test_effective_gate_preserves_builder_only_false_seals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = _effective_summary()
    monkeypatch.setattr(
        patch,
        "load_and_validate_p1_sequence_seed_20260614_patch_lock",
        lambda: ({}, summary),
    )
    monkeypatch.setattr(patch, "p1_seed_20260614_namespace_absence", lambda: {})
    monkeypatch.setattr(patch, "closure_progression_prelock", lambda: {})
    observed = patch.require_p1_sequence_seed_20260614_authorized(
        "P1", 20_260_614
    )
    assert observed["p1_sequence_builder_authorized"] is True
    assert observed["authorization_effective"] is True
    assert observed["p1_consumer_authorized"] is False
    assert observed["p1_fit_authorized"] is False
    assert observed["dvc_commands_authorized"] is False
    assert observed["future_outcomes_accessed"] is False


@pytest.mark.parametrize(
    "field",
    (
        "p1_consumer_authorized",
        "p1_fit_authorized",
        "fit_attempt_authorized",
        "replacement_authorized",
        "dvc_commands_authorized",
    ),
)
def test_effective_gate_rejects_broadened_authority(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    summary = {**_effective_summary(), field: True}
    monkeypatch.setattr(
        patch,
        "load_and_validate_p1_sequence_seed_20260614_patch_lock",
        lambda: ({}, summary),
    )
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="fail-closed seals drifted",
    ):
        patch.require_p1_sequence_seed_20260614_authorized("P1", 20_260_614)


def test_effective_loader_has_no_unpublished_bypass_arguments() -> None:
    assert inspect.signature(
        patch.load_and_validate_p1_sequence_seed_20260614_patch_lock
    ).parameters == {}


def test_physical_schema_is_recursively_closed_without_unsupported_keywords() -> None:
    schema = json.loads(patch.DEFAULT_PATCH_LOCK_SCHEMA.read_text(encoding="utf-8"))
    assert len(schema["required"]) == len(set(schema["required"]))

    def assert_closed(node: object) -> None:
        if isinstance(node, dict):
            mapping = cast(dict[str, object], node)
            assert "minimum" not in mapping
            assert "format" not in mapping
            if mapping.get("type") == "object" or "properties" in mapping:
                assert mapping.get("additionalProperties") is False
            for value in mapping.values():
                assert_closed(value)
        elif isinstance(node, list):
            for value in node:
                assert_closed(value)

    assert_closed(schema)
    with pytest.raises(closure_contract.ClosureContractError) as raised:
        closure_contract.validate_json_schema({}, schema, instance_path="$.probe")
    assert "Unsupported JSON Schema keyword" not in str(raised.value)


def test_schema_accepts_real_historical_authority_shapes() -> None:
    execution_head = patch._git("rev-parse", "HEAD")
    component_records = [
        _record(path, patch.PATCH_COMPONENT_ROLES[path], f"{index + 1:x}")
        for index, path in enumerate(patch.PATCH_PATHS)
    ]
    git_entries = [
        {
            "status": "M" if path in patch.PATCH_MODIFIED_PATHS else "A",
            "path": path,
        }
        for path in patch.PATCH_PATHS
    ]
    prelock = {
        "patch_repository": {
            "head": PATCH_HEAD,
            "parent": patch.PATCH_BASE_COMMIT,
            "branch": "main",
            "published_ref": patch.PUBLISHED_REF,
            "published_head": PATCH_HEAD,
            "remote_main_oid": PATCH_HEAD,
            "worktree_status": "clean",
            "exact_diff_verified": True,
        },
        "git_diff": {
            "base_commit": patch.PATCH_BASE_COMMIT,
            "patch_head": PATCH_HEAD,
            "modified_count": 2,
            "added_count": 5,
            "entries": git_entries,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "only_allowed_additions_and_modifications": True,
        },
        "patch_components": {
            "count": 7,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "records": component_records,
            "records_sha256": patch._record_digest(component_records),
        },
        "base_authorities": {
            "e0_mj": patch._historical_e0_mj_authority(
                execution_head=execution_head
            ),
            "e0_mk": patch._historical_e0_mk_authority(
                execution_head=execution_head
            ),
        },
        "p1_1729_publication": patch._published_p1_1729_bundle(
            execution_head=execution_head
        ),
        "p1_20260612_publication": patch._published_p1_20260612_bundle(
            execution_head=execution_head
        ),
        "p1_20260613_publication": patch._published_p1_20260613_bundle(
            execution_head=execution_head
        ),
        "anfis_20260614_state_bundle": patch._anfis_20260614_state_bundle(
            execution_head=execution_head
        ),
        "current_runtime_builder_record": {
            **next(
                record
                for record in component_records
                if record["path"]
                == "src/experiments/build_closure_pipe_sequences.py"
            ),
            "role": "current_runtime_builder",
        },
        "sequence_prelock": patch._sequence_prelock_contract(),
        "progression_prelock": patch._progression_prelock_contract(),
    }
    payload = patch.build_p1_sequence_seed_20260614_patch_lock_payload(
        prelock,
        _verification(focused_count=patch.FOCUSED_TEST_COUNT),
        created_at_utc="2026-08-06T00:00:00Z",
    )
    schema = json.loads(patch.DEFAULT_PATCH_LOCK_SCHEMA.read_text(encoding="utf-8"))
    closure_contract.validate_json_schema(
        payload,
        schema,
        instance_path="$.p1_sequence_seed_20260614_patch_lock",
    )


def test_companion_separates_physical_and_historical_inputs() -> None:
    component_records = [
        _record(path, patch.PATCH_COMPONENT_ROLES[path], f"{index:x}")
        for index, path in enumerate(patch.PATCH_PATHS)
    ]
    mj_superseded = [
        _record(path, e0_mj.PATCH_COMPONENT_ROLES[path], token)
        for path, token in zip(patch.E0_MJ_SUPERSEDED_PATHS, ("c", "d"))
    ]
    publication_records = [
        _record(path.as_posix(), f"p1_1729_{index}", "e")
        for index, path in enumerate(patch.P1_1729_PRESENT_PATHS, start=1)
    ]
    state_records = [
        _record(path.as_posix(), f"anfis_20260614_{index}", "f")
        for index, path in enumerate(
            (
                patch.ANFIS_20260614_STATE_PATH,
                patch.ANFIS_20260614_POINTER_PATH,
                patch.ANFIS_20260614_MANIFEST_PATH,
            ),
            start=1,
        )
    ]
    payload = {
        "created_at_utc": "2026-08-06T00:00:00Z",
        "patch_components": {"records": component_records},
        "base_authorities": {
            "e0_mj": {
                "lock": _record(
                    e0_mj.DEFAULT_PATCH_LOCK_PATH.as_posix(),
                    "external_p1_sequence_seed_20260613_patch_lock",
                    "1",
                ),
                "companion_manifest": _record(
                    e0_mj.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
                    "p1_sequence_seed_20260613_patch_companion",
                    "2",
                ),
                "superseded_components": {"records": mj_superseded},
            },
            "e0_mk": {
                "lock": _record(
                    e0_mk.DEFAULT_PATCH_LOCK_PATH.as_posix(),
                    "external_p1_temporal_consumer_seed_20260613_patch_lock",
                    "3",
                ),
                "companion_manifest": _record(
                    e0_mk.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
                    "p1_temporal_consumer_seed_20260613_patch_companion",
                    "4",
                ),
            },
        },
        "p1_1729_publication": {"records": publication_records},
        "p1_20260612_publication": {
            "records": [
                _record(path.as_posix(), f"p1_20260612_{index}", "a")
                for index, path in enumerate(
                    patch.P1_20260612_PRESENT_PATHS, start=1
                )
            ]
        },
        "p1_20260613_publication": {
            "records": [
                _record(path.as_posix(), f"p1_20260613_{index}", "b")
                for index, path in enumerate(
                    patch.P1_20260613_PRESENT_PATHS, start=1
                )
            ]
        },
        "anfis_20260614_state_bundle": {"records": state_records},
    }
    lock_record = _record(
        patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "external_p1_sequence_seed_20260614_patch_lock",
        "5",
    )
    companion = patch._expected_companion(payload, lock_record=lock_record)
    assert companion["outputs"] == [lock_record]
    assert len(companion["inputs"]) == 28
    assert len({record["path"] for record in companion["inputs"]}) == 28
    assert len(companion["historical_inputs"]) == 2
    assert {
        record["path"] for record in companion["historical_inputs"]
    } == set(patch.E0_MJ_SUPERSEDED_PATHS)
    assert all(
        record["commit"] == patch.E0_MJ_H_COMMIT
        and record["hash_source"] == "git_blob_at_commit"
        for record in companion["historical_inputs"]
    )
    assert companion["physical_inputs_only"] is True
    assert companion["historical_inputs_compared_to_current_paths"] is False
    assert companion["authoritative_contract"] is False


def test_patch_diff_contract_is_exact_direct_child_two_m_plus_five_a(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = [
        {"status": "M" if path in patch.PATCH_MODIFIED_PATHS else "A", "path": path}
        for path in patch.PATCH_PATHS
    ]
    monkeypatch.setattr(patch, "_require_commit", lambda value, **_kwargs: value)
    monkeypatch.setattr(
        patch,
        "_git",
        lambda *_args: f"{PATCH_HEAD} {patch.PATCH_BASE_COMMIT}",
    )
    monkeypatch.setattr(patch, "_observed_diff_entries", lambda *_args: expected)
    observed = patch.patch_git_diff_payload(PATCH_HEAD)
    assert observed["modified_count"] == 2
    assert observed["added_count"] == 5
    assert observed["entries"] == expected
    assert observed["only_allowed_additions_and_modifications"] is True


def test_future_p_topology_requires_two_regular_blob_additions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_commit = "b" * 40
    mode = "100644"
    expected = [
        {"status": "A", "path": patch.DEFAULT_PATCH_LOCK_PATH.as_posix()},
        {"status": "A", "path": patch.DEFAULT_PATCH_MANIFEST_PATH.as_posix()},
    ]

    def git(*args: str) -> str:
        if args[0] == "rev-list":
            return f"{lock_commit} {PATCH_HEAD}"
        if args[0] == "ls-tree":
            return f"{mode} blob {'c' * 40}\t{args[-1]}"
        raise AssertionError(args)

    monkeypatch.setattr(patch, "_introduced_commit", lambda _path: lock_commit)
    monkeypatch.setattr(patch, "_git", git)
    monkeypatch.setattr(patch, "_observed_diff_entries", lambda *_args: expected)
    monkeypatch.setattr(patch, "_require_ancestor", lambda *_args: None)
    monkeypatch.setattr(
        patch,
        "_assert_paths_untouched",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        patch,
        "_file_record",
        lambda path, *, role: _record(path.as_posix(), role),
    )
    payload = {"patch_repository": {"head": PATCH_HEAD}}
    observed = patch._validate_p_commit_topology(
        payload,
        execution_head=lock_commit,
    )
    assert observed[0] == lock_commit

    mode = "100755"
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="publication mode drifted",
    ):
        patch._validate_p_commit_topology(payload, execution_head=lock_commit)


def test_verification_contract_is_exact_and_rejects_dvc_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch, "FOCUSED_TEST_COUNT", 30)
    evidence = _verification(focused_count=30)
    patch.validate_p1_sequence_seed_20260614_patch_verification(evidence)
    evidence["dvc_push"] = _command_evidence(("dvc", "push"))
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="verification fields drifted",
    ):
        patch.validate_p1_sequence_seed_20260614_patch_verification(evidence)


def test_verification_preflights_schema_before_any_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    schema_preflight = patch.preflight_p1_sequence_seed_20260614_patch_schema()
    monkeypatch.setattr(locker, "FOCUSED_TEST_COUNT", 1)
    monkeypatch.setattr(
        locker,
        "_preflight_schema",
        lambda: events.append("schema") or schema_preflight,
    )
    monkeypatch.setattr(
        locker.hardened,
        "_require_fixed_venv_executable",
        lambda *_args: None,
    )

    def run(
        command: tuple[str, ...],
        **_kwargs: Any,
    ) -> tuple[dict[str, Any], str, str]:
        events.append("command")
        evidence = _command_evidence(command)
        if command == locker.TYPE_CHECK_COMMAND:
            return evidence, "All checks passed!\n", ""
        if command == locker.FOCUSED_TEST_COMMAND:
            return evidence, "1 passed in 0.01s\n", ""
        if command == locker.POETRY_CHECK_COMMAND:
            return evidence, "All set!\n", ""
        return evidence, "", ""

    monkeypatch.setattr(locker, "_run_command", run)
    observed = locker.run_p1_sequence_seed_20260614_patch_verification(
        expected_schema_preflight=schema_preflight
    )
    assert events[0] == "schema"
    assert events.count("command") == 5
    assert observed["schema_subset_preflight"] == schema_preflight
    command_records = [
        record
        for record in observed.values()
        if isinstance(record, dict) and "command" in record
    ]
    assert all(
        "dvc" not in str(record["command"]).lower()
        for record in command_records
    )


def test_focused_summary_parser_accepts_only_one_clean_exact_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(locker, "FOCUSED_TEST_COUNT", 30)
    assert locker._parse_focused_summary("30 passed in 1.25s\n", "") == 30
    assert (
        locker._parse_focused_summary(
            "30 passed in 60.00s (0:01:00)\n",
            "",
        )
        == 30
    )
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="duration clock drifted",
    ):
        locker._parse_focused_summary(
            "30 passed in 60.00s (0:00:59)\n",
            "",
        )
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="not one exact clean result",
    ):
        locker._parse_focused_summary(
            "30 passed, 1 warning in 1.25s\n",
            "",
        )


def test_locker_exposes_three_mutually_exclusive_modes() -> None:
    assert locker._parse_args(["--check-only"]).check_only is True
    assert locker._parse_args(["--execute-lock"]).execute_lock is True
    assert locker._parse_args(["--check-effective"]).check_effective is True
    with pytest.raises(SystemExit):
        locker._parse_args(["--check-only", "--execute-lock"])
    assert (
        inspect.getsource(locker._execute_lock).count(
            '"prior_p1_20260612_slot_completed": True'
        )
        == 1
    )
    assert (
        inspect.getsource(locker._execute_lock).count(
            '"prior_p1_20260613_slot_completed": True'
        )
        == 1
    )
    execute_source = inspect.getsource(locker._execute_lock)
    assert '"fit_attempt_authorized": False' in execute_source
    assert '"replacement_authorized": False' in execute_source


def test_check_only_runs_no_verification_or_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    refusal_calls: list[tuple[Path, Path]] = []
    schema_preflight = {
        "gate": "E0-ML",
        "schema_path": patch.DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
        "schema_bytes": 1,
        "schema_sha256": "a" * 64,
        "supported_subset_verified": True,
        "minimum_keyword_absent": True,
        "format_keyword_absent": True,
    }
    prelock = {
        "patch_repository": {"head": PATCH_HEAD},
        "patch_components": {"count": 7},
        "sequence_prelock": {"count": 28},
        "progression_prelock": {"remaining_absent_count": 122},
    }
    monkeypatch.setattr(
        locker,
        "_preflight_schema",
        lambda: events.append("schema") or schema_preflight,
    )
    monkeypatch.setattr(
        locker,
        "_refuse_existing_outputs",
        lambda output, companion: (
            events.append("refuse"),
            refusal_calls.append((output, companion)),
        ),
    )
    monkeypatch.setattr(
        locker,
        "collect_p1_sequence_seed_20260614_patch_prelock_state",
        lambda **_kwargs: events.append("prelock") or prelock,
    )
    monkeypatch.setattr(
        locker,
        "run_p1_sequence_seed_20260614_patch_verification",
        lambda: pytest.fail("check-only must not run verification"),
    )
    result = locker._check_only(
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_MANIFEST_PATH,
    )
    assert len(refusal_calls) == 1
    assert events == ["schema", "refuse", "prelock"]
    assert result["status"] == "ready_to_lock"
    assert result["prior_p1_1729_slot_completed"] is True
    assert result["prior_p1_20260612_slot_completed"] is True
    assert result["prior_p1_20260613_slot_completed"] is True
    assert result["fit_attempt_authorized"] is False
    assert result["replacement_authorized"] is False
    assert result["schema_subset_preflight"] == schema_preflight
    assert result["writes_performed"] is False
    assert result["verification_commands_run"] is False
    assert result["dvc_commands_run"] is False
    assert result["outcome_paths_opened"] is False


def test_check_effective_revalidates_anchored_identity_without_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    identities = ((1, 2, 1, "a" * 64), (3, 4, 1, "b" * 64))
    observations: list[tuple[int, Path, Path]] = []
    descriptor = os.open(
        tmp_path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0),
    )

    def observed_identities(
        directory_descriptor: int,
        output: Path,
        companion: Path,
    ) -> tuple[tuple[int, int, int, str], tuple[int, int, int, str]]:
        observations.append((directory_descriptor, output, companion))
        return identities

    monkeypatch.setattr(locker, "_open_effective_bundle_parent", lambda: descriptor)
    monkeypatch.setattr(locker, "_require_effective_parent_current", lambda _fd: None)
    monkeypatch.setattr(locker, "_effective_bundle_identities", observed_identities)
    monkeypatch.setattr(
        locker,
        "require_p1_sequence_seed_20260614_authorized",
        lambda **_kwargs: _effective_summary(),
    )
    monkeypatch.setattr(locker, "p1_sequence_namespace_absence", lambda: {})
    monkeypatch.setattr(locker, "closure_progression_namespace_absence", lambda: {})
    result = locker._check_effective(
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_MANIFEST_PATH,
    )
    assert len(observations) == 2
    assert observations[0][0] == observations[1][0]
    assert result["status"] == "effective_preflight_passed"
    assert result["prior_p1_1729_slot_completed"] is True
    assert result["prior_p1_20260612_slot_completed"] is True
    assert result["prior_p1_20260613_slot_completed"] is True
    assert result["fit_attempt_authorized"] is False
    assert result["replacement_authorized"] is False
    assert result["writes_performed"] is False
    assert result["dvc_commands_run"] is False
    assert result["outcome_paths_opened"] is False


def test_anchored_final_identity_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    linked = tmp_path / "linked.json"
    linked.symlink_to(target.name)
    descriptor = os.open(
        tmp_path,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        with pytest.raises(
            patch.P1SequenceSeed20260614PatchError,
            match="regular non-symlink file",
        ):
            locker._regular_final_identity(
                descriptor,
                linked.name,
                context="test linked lock",
            )
    finally:
        os.close(descriptor)


def test_execute_lock_rolls_back_if_companion_publication_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repository"
    (project_root / patch.DEFAULT_PATCH_LOCK_PATH.parent).mkdir(parents=True)
    guard_directory = project_root / "tmp" / "closure_v1_e0_ml_locker"
    output = project_root / patch.DEFAULT_PATCH_LOCK_PATH
    companion = project_root / patch.DEFAULT_PATCH_MANIFEST_PATH
    prelock = {"stable": True}
    payload = {
        "created_at_utc": "2026-08-06T00:00:00Z",
        "patch_repository": {"head": PATCH_HEAD},
    }
    monkeypatch.setattr(locker, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker.hardened, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)
    monkeypatch.setattr(
        locker,
        "collect_p1_sequence_seed_20260614_patch_prelock_state",
        lambda **_kwargs: prelock,
    )
    monkeypatch.setattr(
        locker,
        "run_p1_sequence_seed_20260614_patch_verification",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(locker, "p1_sequence_namespace_absence", lambda: {})
    monkeypatch.setattr(locker, "closure_progression_namespace_absence", lambda: {})
    monkeypatch.setattr(
        locker,
        "build_p1_sequence_seed_20260614_patch_lock_payload",
        lambda *_args, **_kwargs: payload,
    )
    monkeypatch.setattr(locker, "_load_regular_json", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        locker,
        "validate_p1_sequence_seed_20260614_patch_lock_payload",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        locker,
        "_expected_companion",
        lambda *_args, **_kwargs: {"status": "completed"},
    )
    monkeypatch.setattr(
        locker,
        "_load_unpublished_p1_sequence_seed_20260614_patch_lock",
        lambda: ({}, {}),
    )
    real_publish = locker._publish_guarded_bytes

    def fail_companion(
        content: bytes,
        destination: Path,
        expected: Path,
        guard: Any,
    ) -> Any:
        if destination == companion:
            raise RuntimeError("injected companion publication failure")
        return real_publish(content, destination, expected, guard)

    monkeypatch.setattr(locker, "_publish_guarded_bytes", fail_companion)
    with pytest.raises(
        patch.P1SequenceSeed20260614PatchError,
        match="transaction failed",
    ):
        locker._execute_lock(
            patch.DEFAULT_PATCH_LOCK_PATH,
            patch.DEFAULT_PATCH_MANIFEST_PATH,
        )
    reserved = (
        output,
        output.with_suffix(output.suffix + ".tmp"),
        companion,
        companion.with_suffix(companion.suffix + ".tmp"),
        *(guard_directory / name for name in locker.OUTPUT_GUARD_NAMES),
    )
    assert all(not os.path.lexists(path) for path in reserved)
