from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Mapping, cast

import pytest

from src.data.prepare_commit_artifacts import (
    has_failing_findings,
    validate_experiment_manifests,
)
from src.experiments import closure_p1_sequence_builder_patch as patch
from src.experiments import lock_closure_p1_sequence_builder_patch as locker
from src.experiments.closure_contract import validate_json_schema


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, dict)
    return payload


def _command_evidence(command: tuple[str, ...]) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": "0" * 64,
        "stderr_sha256": "1" * 64,
        "stdout_line_count": 1,
        "stderr_line_count": 0,
    }


def _verification() -> dict[str, Any]:
    focused = _command_evidence(patch.FOCUSED_TEST_COMMAND)
    focused.update(
        {
            "test_count": patch.FOCUSED_TEST_COUNT,
            "skipped_count": 0,
            "deselected_count": 0,
        }
    )
    return {
        "full_type_check": _command_evidence(patch.TYPE_CHECK_COMMAND),
        "focused_tests": focused,
        "poetry_check": _command_evidence(patch.POETRY_CHECK_COMMAND),
        "publication_guard": _command_evidence(patch.PUBLICATION_GUARD_COMMAND),
        "git_diff_check": _command_evidence(patch.DIFF_CHECK_COMMAND),
    }


def _component_records() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "role": patch.PATCH_COMPONENT_ROLES[path],
            "bytes": index,
            "sha256": f"{index:064x}",
        }
        for index, path in enumerate(patch.PATCH_PATHS, start=1)
    ]


def _schema_prelock() -> dict[str, Any]:
    head = "a" * 40
    records = _component_records()
    entries = [
        {
            "status": "M" if path in patch.PATCH_MODIFIED_PATHS else "A",
            "path": path,
        }
        for path in patch.PATCH_PATHS
    ]
    sequence_paths = [path.as_posix() for path in patch.p1_sequence_namespace_paths()]
    return {
        "patch_repository": {
            "head": head,
            "parent": patch.PATCH_BASE_COMMIT,
            "branch": "main",
            "published_ref": patch.PUBLISHED_REF,
            "published_head": head,
            "remote_main_oid": head,
            "worktree_status": "clean",
            "exact_diff_verified": True,
        },
        "git_diff": {
            "base_commit": patch.PATCH_BASE_COMMIT,
            "patch_head": head,
            "modified_count": 2,
            "added_count": 5,
            "entries": entries,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "only_allowed_additions_and_modifications": True,
        },
        "patch_components": {
            "count": len(records),
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "records": records,
            "records_sha256": patch._record_digest(records),
        },
        "base_authorities": {
            "e0_dltvm": {
                "lock": {
                    "path": patch.dltvm.DEFAULT_PATCH_LOCK_PATH.as_posix(),
                    "role": "external_development_runtime_temporal_validation_dialect_patch_lock",
                    "bytes": 10,
                    "sha256": "b" * 64,
                },
                "companion_manifest": {
                    "path": patch.dltvm.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
                    "role": "development_runtime_temporal_validation_manifest_patch_companion",
                    "bytes": 11,
                    "sha256": "c" * 64,
                },
                "superseded_components": {
                    "records": [
                        {
                            "path": path,
                            "role": patch.dltvm.PATCH_COMPONENT_ROLES[path],
                            "bytes": 12,
                            "sha256": "d" * 64,
                        }
                        for path in patch.SUPERSEDED_DLTVM_COMPONENT_PATHS
                    ]
                },
            },
            "e0_ma": {
                "registry": {
                    "path": patch.availability.DEFAULT_REGISTRY.as_posix(),
                    "role": "p0_model_availability_registry",
                    "bytes": 13,
                    "sha256": "e" * 64,
                },
                "companion_manifest": {
                    "path": patch.availability.DEFAULT_COMPANION.as_posix(),
                    "role": "p0_model_availability_registry_companion",
                    "bytes": 14,
                    "sha256": "f" * 64,
                },
            },
        },
        "current_runtime_builder_record": {
            "path": "src/experiments/build_closure_pipe_sequences.py",
            "role": "current_runtime_builder",
            "bytes": 15,
            "sha256": "1" * 64,
        },
        "sequence_prelock": {
            "model_id": "P1",
            "base_seed": 1729,
            "count": 28,
            "paths": sequence_paths,
            "paths_sha256": patch._path_digest(sequence_paths),
            "all_absent_at_lock": True,
        },
        "progression_prelock": {
            "p1_seed_order": list(patch.availability.EXPECTED_SEEDS),
            "p1_path_count": 140,
            "p1_paths_sha256": "2" * 64,
            "p1_all_absent": True,
            "e0_m_output_count": 0,
            "outcome_access_log_state": "absent",
            "future_outcomes_accessed": False,
        },
    }


def test_closed_topology_and_exact_h_scope() -> None:
    assert patch.PATCH_BASE_COMMIT == patch.REGISTRY_COMMIT
    assert patch.REGISTRY_COMMIT == (
        "9851211bdc7b14d07ccfef997e7681a232f1f611"
    )
    assert patch.DLTVM_H_COMMIT == (
        "3ee008faef331f40cf73d1f1e3db59608b0deab1"
    )
    assert patch.DLTVM_LOCK_COMMIT == (
        "4ba5ecd45da7f0b25277c0a13602999413fa2849"
    )
    assert len(patch.PATCH_PATHS) == 7
    assert len(patch.PATCH_MODIFIED_PATHS) == 2
    assert len(patch.PATCH_ADDED_PATHS) == 5
    assert set(patch.PATCH_MODIFIED_PATHS) == {
        "src/experiments/build_closure_pipe_sequences.py",
        "tests/test_build_closure_pipe_sequences.py",
    }
    assert set(patch.SUPERSEDED_DLTVM_COMPONENT_PATHS) == set(
        patch.PATCH_MODIFIED_PATHS
    )
    assert len(patch.PRESERVED_DLTVM_COMPONENT_PATHS) == 9


def test_schema_is_closed_and_accepts_a_structural_payload() -> None:
    schema = _load_json(patch.PROJECT_ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["gate"]["const"] == "E0-MB"
    assert schema["properties"]["authorizations"]["const"] == (
        patch.PATCH_AUTHORIZATIONS
    )
    payload = patch.build_p1_sequence_builder_patch_lock_payload(
        _schema_prelock(),
        _verification(),
        created_at_utc="2026-08-05T00:00:00Z",
    )
    validate_json_schema(payload, schema, instance_path="$.lock")

    def assert_closed(node: object) -> None:
        if isinstance(node, Mapping):
            mapping = cast(Mapping[str, object], node)
            if mapping.get("type") == "object":
                assert mapping.get("additionalProperties") is False
            for value in mapping.values():
                assert_closed(value)
        elif isinstance(node, list):
            for value in node:
                assert_closed(value)

    assert_closed(schema)
    corrupted = json.loads(json.dumps(payload))
    corrupted["patch_repository"]["unexpected"] = True
    with pytest.raises(ValueError, match="additionalProperties"):
        validate_json_schema(corrupted, schema, instance_path="$.lock")


def test_first_seed_namespace_is_exact_and_currently_pristine() -> None:
    paths = patch.p1_sequence_namespace_paths()
    assert len(paths) == 28
    assert len({path.as_posix() for path in paths}) == 28
    assert Path("data/closure_v1/development/sequences/P1/seed_1729.parquet") in paths
    assert Path("data/closure_v1/development/sequences/P1/seed_1729.parquet.dvc") in paths
    assert Path("tmp/closure_v1_sequence_builder/P1_seed_1729.guard") in paths
    result = patch.p1_sequence_namespace_absence()
    assert result["count"] == 28
    assert result["all_absent_at_lock"] is True


def test_progression_namespace_covers_all_five_seeds() -> None:
    result = patch.closure_progression_namespace_absence()
    assert result["p1_seed_order"] == [1729, 20260612, 20260613, 20260614, 314159]
    assert result["p1_path_count"] == 140
    assert result["p1_all_absent"] is True
    assert result["e0_m_output_count"] == 0
    assert result["outcome_access_log_state"] == "absent"


def test_real_e0_ma_registry_reconstructs_from_the_descendant_worktree() -> None:
    execution_head = patch._git("rev-parse", "HEAD")
    authority = patch._historical_registry_authority(execution_head=execution_head)
    assert authority["registry_commit"] == patch.REGISTRY_COMMIT
    assert authority["registry_parent"] == patch.REGISTRY_H_COMMIT
    assert authority["slot_count"] == 5
    assert authority["seed_slots"] == [1729, 20260612, 20260613, 20260614, 314159]
    assert authority["available_fit_role_sequences_per_slot"] == 8925
    assert authority["unavailable_fit_role_sequences_per_slot"] == 488
    assert authority["registry_effective_as_historical_authority"] is True
    assert authority["p1_materialized_path_count"] == 0


def test_real_dltvm_lock_reconstructs_with_only_builder_and_test_superseded() -> None:
    execution_head = patch._git("rev-parse", "HEAD")
    authority = patch._historical_dltvm_authority(execution_head=execution_head)
    assert authority["patch_head"] == patch.DLTVM_H_COMMIT
    assert authority["lock_commit"] == patch.DLTVM_LOCK_COMMIT
    assert authority["superseded_components"]["count"] == 2
    assert authority["preserved_components"]["count"] == 9
    assert authority["historical_development_fit_authorized"] is True
    assert authority["evaluation_authorized"] is False
    assert authority["e0_u_authorized"] is False
    assert authority["future_outcomes_accessed"] is False


def test_schema_accepts_the_real_historical_authority_shapes() -> None:
    execution_head = patch._git("rev-parse", "HEAD")
    prelock = _schema_prelock()
    prelock["base_authorities"] = {
        "e0_dltvm": patch._historical_dltvm_authority(execution_head=execution_head),
        "e0_ma": patch._historical_registry_authority(execution_head=execution_head),
    }
    payload = patch.build_p1_sequence_builder_patch_lock_payload(
        prelock,
        _verification(),
        created_at_utc="2026-08-05T00:00:00Z",
    )
    schema = _load_json(patch.PROJECT_ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA)
    validate_json_schema(payload, schema, instance_path="$.lock")


@pytest.mark.parametrize(
    ("model_id", "base_seed"),
    (("P0", None), ("P1", None), ("P1", 20260612), ("P2", 1729)),
)
def test_gate_rejects_every_non_authorized_slot_before_loading(
    monkeypatch: pytest.MonkeyPatch,
    model_id: str,
    base_seed: int | None,
) -> None:
    monkeypatch.setattr(
        patch,
        "load_and_validate_p1_sequence_builder_patch_lock",
        lambda **_kwargs: pytest.fail("loader must not run"),
    )
    with pytest.raises(
        patch.P1SequenceBuilderPatchError,
        match="only the one-shot P1 sequence build for seed 1729",
    ):
        patch.require_p1_sequence_builder_authorized(
            model_id=model_id,
            base_seed=base_seed,
        )


def test_effective_gate_preserves_all_false_seals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = {
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_dltvm_verified": True,
        "historical_e0_ma_registry_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": True,
        **patch.EFFECTIVE_AUTHORIZATIONS,
        "authorization_inputs": [],
    }
    monkeypatch.setattr(
        patch,
        "load_and_validate_p1_sequence_builder_patch_lock",
        lambda **_kwargs: ({}, summary),
    )
    monkeypatch.setattr(patch, "p1_sequence_namespace_absence", lambda: {})
    monkeypatch.setattr(patch, "closure_progression_namespace_absence", lambda: {})
    observed = patch.require_p1_sequence_builder_authorized(
        model_id="P1",
        base_seed=1729,
    )
    assert observed["p1_sequence_builder_authorized"] is True
    assert observed["p1_fit_authorized"] is False
    assert observed["e0_m_authorized"] is False
    assert observed["evaluation_authorized"] is False
    assert observed["e0_u_authorized"] is False
    assert observed["future_outcomes_accessed"] is False


def test_payload_and_unpublished_loader_cannot_self_authorize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "a" * 40
    payload = {"patch_repository": {"head": head}}
    companion = {"status": "completed"}

    def load(path: Path, *, context: str) -> dict[str, Any]:
        del context
        if path == patch.DEFAULT_PATCH_LOCK_PATH:
            return payload
        if path == patch.DEFAULT_PATCH_MANIFEST_PATH:
            return companion
        return {}

    def record(
        value: Mapping[str, Any],
        path: Path,
        *,
        role: str,
        context: str,
    ) -> dict[str, Any]:
        del value, context
        return {"path": path.as_posix(), "role": role, "bytes": 1, "sha256": "0" * 64}

    monkeypatch.setattr(patch, "_load_regular_json", load)
    monkeypatch.setattr(
        patch,
        "validate_p1_sequence_builder_patch_lock_payload",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(patch, "_canonical_json_record", record)
    monkeypatch.setattr(patch, "_expected_companion", lambda *_args, **_kwargs: companion)
    monkeypatch.setattr(patch, "_git", lambda *_args: head)
    monkeypatch.setattr(
        patch,
        "_require_commit",
        lambda value, **_kwargs: value,
    )
    _, summary = patch._load_unpublished_p1_sequence_builder_patch_lock()
    assert patch.PATCH_AUTHORIZATIONS["p1_sequence_builder_authorized"] is False
    assert summary["p1_sequence_builder_authorized"] is False
    assert summary["authorization_effective"] is False
    assert summary["publication_required"] is True


def test_effective_loader_exposes_no_unpublished_or_remote_bypass() -> None:
    assert inspect.signature(
        patch.load_and_validate_p1_sequence_builder_patch_lock
    ).parameters == {}


def test_gate_rejects_a_self_authorized_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = {
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_dltvm_verified": True,
        "historical_e0_ma_registry_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": True,
        **patch.EFFECTIVE_AUTHORIZATIONS,
        "authorization_inputs": [],
        "p1_fit_authorized": True,
    }
    monkeypatch.setattr(
        patch,
        "load_and_validate_p1_sequence_builder_patch_lock",
        lambda **_kwargs: ({}, summary),
    )
    with pytest.raises(patch.P1SequenceBuilderPatchError, match="seals drifted"):
        patch.require_p1_sequence_builder_authorized(
            model_id="P1",
            base_seed=1729,
        )


def test_verification_contract_has_no_dvc_or_outcome_command() -> None:
    verification = _verification()
    patch.validate_p1_sequence_builder_patch_verification(verification)
    assert set(verification) == {
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
    }
    corrupted = dict(verification)
    corrupted["dvc_push"] = _command_evidence(("dvc", "push"))
    with pytest.raises(patch.P1SequenceBuilderPatchError, match="fields drifted"):
        patch.validate_p1_sequence_builder_patch_verification(corrupted)


def test_companion_separates_current_and_historical_builder_records() -> None:
    prelock = _schema_prelock()
    payload = patch.build_p1_sequence_builder_patch_lock_payload(
        prelock,
        _verification(),
        created_at_utc="2026-08-05T00:00:00Z",
    )
    lock_record = {
        "path": patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "role": "external_p1_sequence_builder_patch_lock",
        "bytes": 2,
        "sha256": "3" * 64,
    }
    companion = patch._expected_companion(payload, lock_record=lock_record)
    assert companion["outputs"] == [lock_record]
    assert companion["script"]["path"] == (
        "src/experiments/lock_closure_p1_sequence_builder_patch.py"
    )
    assert companion["physical_inputs_only"] is True
    assert companion["historical_inputs_compared_to_current_paths"] is False
    assert {record["path"] for record in companion["historical_inputs"]} == set(
        patch.SUPERSEDED_DLTVM_COMPONENT_PATHS
    )
    current_paths = {record["path"] for record in companion["inputs"]}
    assert "src/experiments/build_closure_pipe_sequences.py" in current_paths
    assert all(
        record["commit"] == patch.DLTVM_H_COMMIT
        for record in companion["historical_inputs"]
    )
    assert companion["p1_sequence_builder_authorized"] is False
    assert companion["effective_in_payload"] is False
    assert companion["publication_required"] is True


def test_payload_prelocks_remain_historical_after_physical_namespace_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prelock = _schema_prelock()
    payload = patch.build_p1_sequence_builder_patch_lock_payload(
        prelock,
        _verification(),
        created_at_utc="2026-08-05T00:00:00Z",
    )
    schema = _load_json(patch.PROJECT_ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA)
    head = str(prelock["patch_repository"]["head"])
    monkeypatch.setattr(patch, "patch_git_diff_payload", lambda _head: prelock["git_diff"])
    monkeypatch.setattr(
        patch,
        "patch_component_bundle",
        lambda _head: prelock["patch_components"],
    )
    monkeypatch.setattr(patch, "_git", lambda *_args: head)
    monkeypatch.setattr(
        patch,
        "_require_commit",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(patch, "_require_ancestor", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        patch,
        "_historical_dltvm_authority",
        lambda **_kwargs: prelock["base_authorities"]["e0_dltvm"],
    )
    monkeypatch.setattr(
        patch,
        "_historical_registry_authority",
        lambda **_kwargs: prelock["base_authorities"]["e0_ma"],
    )
    monkeypatch.setattr(
        patch,
        "_locked_builder_record",
        lambda _head: prelock["current_runtime_builder_record"],
    )
    monkeypatch.setattr(
        patch,
        "_sequence_prelock_contract",
        lambda: prelock["sequence_prelock"],
    )
    monkeypatch.setattr(
        patch,
        "_progression_prelock_contract",
        lambda: prelock["progression_prelock"],
    )
    monkeypatch.setattr(
        patch,
        "p1_sequence_namespace_absence",
        lambda: pytest.fail("historical payload validation must not probe current P1 paths"),
    )
    monkeypatch.setattr(
        patch,
        "closure_progression_namespace_absence",
        lambda: pytest.fail("historical payload validation must not probe current closure paths"),
    )
    patch.validate_p1_sequence_builder_patch_lock_payload(
        payload,
        schema,
        require_physical_patch_components=False,
    )


def test_canonical_json_record_rejects_noncanonical_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch.dlt, "PROJECT_ROOT", tmp_path)
    path = tmp_path / "lock.json"
    path.write_bytes(b'{"value":1}\n')
    with pytest.raises(patch.P1SequenceBuilderPatchError, match="not canonical"):
        patch._canonical_json_record(
            {"value": 1},
            Path("lock.json"),
            role="test_lock",
            context="test lock",
        )


def test_effective_publication_rejects_detached_head_and_remote_divergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    payload = {"patch_repository": {"head": "b" * 40}}
    records = (
        {"path": patch.DEFAULT_PATCH_LOCK_PATH.as_posix()},
        {"path": patch.DEFAULT_PATCH_MANIFEST_PATH.as_posix()},
    )
    monkeypatch.setattr(
        patch,
        "_validate_p_commit_topology",
        lambda *_args, **_kwargs: (commit, *records),
    )
    monkeypatch.setattr(
        patch,
        "_require_commit",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(patch, "_git", lambda *_args: "")
    with pytest.raises(patch.P1SequenceBuilderPatchError, match="branch main"):
        patch._validate_effective_publication(payload, execution_head=commit)

    def aligned_git(*args: str) -> str:
        if args == ("branch", "--show-current"):
            return "main"
        if args[0] == "rev-parse":
            return commit
        raise AssertionError(args)

    monkeypatch.setattr(patch, "_git", aligned_git)
    monkeypatch.setattr(patch, "_remote_main_oid", lambda: "c" * 40)
    with pytest.raises(patch.P1SequenceBuilderPatchError, match="live origin/main"):
        patch._validate_effective_publication(payload, execution_head=commit)


def test_generic_precommit_validates_only_current_physical_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lock_path = patch.DEFAULT_PATCH_LOCK_PATH
    companion_path = patch.DEFAULT_PATCH_MANIFEST_PATH
    prelock = _schema_prelock()
    records = cast_records(prelock["patch_components"])
    by_path = {record["path"]: record for record in records}

    physical_paths = {
        patch.DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
        "src/experiments/closure_p1_sequence_builder_patch.py",
        "src/experiments/build_closure_pipe_sequences.py",
        "src/experiments/lock_closure_p1_sequence_builder_patch.py",
        patch.availability.DEFAULT_REGISTRY.as_posix(),
        patch.availability.DEFAULT_COMPANION.as_posix(),
        patch.dltvm.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        patch.dltvm.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
    }
    contents: dict[str, bytes] = {}
    for index, path in enumerate(sorted(physical_paths), start=1):
        content = f"physical-{index}\n".encode()
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        contents[path] = content

    def record(path: str, role: str) -> dict[str, Any]:
        content = contents[path]
        return {
            "path": path,
            "role": role,
            "bytes": len(content),
            "sha256": patch._sha256_bytes(content),
        }

    for path in (
        patch.DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
        "src/experiments/closure_p1_sequence_builder_patch.py",
        "src/experiments/build_closure_pipe_sequences.py",
        "src/experiments/lock_closure_p1_sequence_builder_patch.py",
    ):
        by_path[path] = record(path, patch.PATCH_COMPONENT_ROLES[path])
    prelock["patch_components"]["records"] = list(by_path.values())
    prelock["base_authorities"]["e0_ma"]["registry"] = record(
        patch.availability.DEFAULT_REGISTRY.as_posix(),
        "p0_model_availability_registry",
    )
    prelock["base_authorities"]["e0_ma"]["companion_manifest"] = record(
        patch.availability.DEFAULT_COMPANION.as_posix(),
        "p0_model_availability_registry_companion",
    )
    prelock["base_authorities"]["e0_dltvm"]["lock"] = record(
        patch.dltvm.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "external_development_runtime_temporal_validation_dialect_patch_lock",
    )
    prelock["base_authorities"]["e0_dltvm"]["companion_manifest"] = record(
        patch.dltvm.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        "development_runtime_temporal_validation_manifest_patch_companion",
    )
    payload = patch.build_p1_sequence_builder_patch_lock_payload(
        prelock,
        _verification(),
        created_at_utc="2026-08-05T00:00:00Z",
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_bytes(b'{"status": "locked"}\n')
    lock_record = file_record(lock_path, "external_p1_sequence_builder_patch_lock")
    companion = patch._expected_companion(payload, lock_record=lock_record)
    companion_path.write_text(json.dumps(companion, indent=2) + "\n", encoding="utf-8")
    findings = validate_experiment_manifests(
        staged_paths={lock_path, companion_path},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=True,
    )
    assert len(findings) == 1
    assert findings[0].level == "ok"
    assert not has_failing_findings(findings)

    current_builder = Path("src/experiments/build_closure_pipe_sequences.py")
    current_builder.write_bytes(b"changed current builder\n")
    findings = validate_experiment_manifests(
        staged_paths={lock_path, companion_path},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=True,
    )
    assert has_failing_findings(findings)


def cast_records(bundle: object) -> list[dict[str, Any]]:
    assert isinstance(bundle, dict)
    mapping = cast(dict[str, object], bundle)
    records = mapping.get("records")
    assert isinstance(records, list)
    return [dict(cast(Mapping[str, Any], record)) for record in records]


def file_record(path: Path, role: str) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.as_posix(),
        "role": role,
        "bytes": len(payload),
        "sha256": patch._sha256_bytes(payload),
    }


def test_locker_closed_namespace_and_exact_summary() -> None:
    assert locker._closed_output(
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_LOCK_PATH,
    ) == patch.PROJECT_ROOT / patch.DEFAULT_PATCH_LOCK_PATH
    assert locker.OUTPUT_GUARD_DIRECTORY != locker.hardened.OUTPUT_GUARD_DIRECTORY
    if patch.FOCUSED_TEST_COUNT > 0:
        assert locker._parse_focused_summary(
            f"{patch.FOCUSED_TEST_COUNT} passed in 1.25s\n",
            "",
        ) == patch.FOCUSED_TEST_COUNT


def test_guard_probe_is_fresh_clone_safe_and_non_writing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repository"
    project_root.mkdir()
    guard_directory = project_root / "tmp" / "closure_v1_e0_mb_locker"
    monkeypatch.setattr(locker, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)
    guards = locker._guard_paths(create_directory=False)
    assert guards == tuple(
        guard_directory / name for name in locker.OUTPUT_GUARD_NAMES
    )
    assert not (project_root / "tmp").exists()


def test_guard_probe_rejects_a_symlinked_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repository"
    tmp_root = project_root / "tmp"
    outside = tmp_path / "outside"
    tmp_root.mkdir(parents=True)
    outside.mkdir()
    guard_directory = tmp_root / "closure_v1_e0_mb_locker"
    guard_directory.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(locker, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)
    with pytest.raises(patch.P1SequenceBuilderPatchError, match="guard directory"):
        locker._guard_paths(create_directory=False)


def test_execute_lock_rolls_back_if_companion_publication_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repository"
    (project_root / patch.DEFAULT_PATCH_LOCK_PATH.parent).mkdir(parents=True)
    guard_directory = project_root / "tmp" / "closure_v1_e0_mb_locker"
    output = project_root / patch.DEFAULT_PATCH_LOCK_PATH
    companion = project_root / patch.DEFAULT_PATCH_MANIFEST_PATH
    prelock = _schema_prelock()

    monkeypatch.setattr(locker, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker.hardened, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)
    monkeypatch.setattr(
        locker,
        "collect_p1_sequence_builder_patch_prelock_state",
        lambda **_kwargs: prelock,
    )
    monkeypatch.setattr(locker, "run_p1_sequence_builder_patch_verification", _verification)
    monkeypatch.setattr(locker, "p1_sequence_namespace_absence", lambda: {})
    monkeypatch.setattr(locker, "closure_progression_namespace_absence", lambda: {})
    monkeypatch.setattr(locker, "_load_regular_json", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        locker,
        "validate_p1_sequence_builder_patch_lock_payload",
        lambda *_args, **_kwargs: None,
    )

    real_publish = locker.hardened._publish_guarded_bytes

    def fake_publish(
        payload: bytes,
        path: Path,
        expected: Path,
        guard: Any,
    ) -> Any:
        if path == companion:
            raise RuntimeError("injected companion publication failure")
        return real_publish(payload, path, expected, guard)

    monkeypatch.setattr(locker.hardened, "_publish_guarded_bytes", fake_publish)
    with pytest.raises(
        patch.P1SequenceBuilderPatchError,
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
    assert all(not path.exists() for path in reserved)


@pytest.mark.parametrize("guard_drift", ("missing", "replaced"))
def test_successful_lock_cleanup_rolls_back_if_guard_ownership_is_lost(
    guard_drift: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repository"
    (project_root / patch.DEFAULT_PATCH_LOCK_PATH.parent).mkdir(parents=True)
    guard_directory = project_root / "tmp" / "closure_v1_e0_mb_locker"
    output = project_root / patch.DEFAULT_PATCH_LOCK_PATH
    companion = project_root / patch.DEFAULT_PATCH_MANIFEST_PATH
    monkeypatch.setattr(locker, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker.hardened, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)

    guards = locker._acquire_guards(
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_MANIFEST_PATH,
    )
    owner = locker.hardened._publish_guarded_bytes(
        b"owned lock\n",
        output,
        patch.DEFAULT_PATCH_LOCK_PATH,
        guards[0],
    )
    guards[0].path.unlink()
    if guard_drift == "replaced":
        guards[0].path.write_bytes(b"foreign guard\n")

    with pytest.raises(
        patch.P1SequenceBuilderPatchError,
        match="cleanup failed closed",
    ):
        locker._cleanup_lock_resources(
            (owner,),
            guards,
            succeeded=True,
            active_error=None,
        )

    assert not output.exists()
    assert not companion.exists()
    if guard_drift == "replaced":
        assert guards[0].path.read_bytes() == b"foreign guard\n"
    else:
        assert not guards[0].path.exists()
