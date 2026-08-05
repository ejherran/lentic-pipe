from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.experiments import closure_development_runtime_temporal_validation_manifest_patch as patch
from src.experiments import (
    lock_closure_development_runtime_temporal_validation_manifest_patch as locker,
)
from src.experiments.closure_contract import validate_json_schema
from src.data.prepare_commit_artifacts import (
    has_failing_findings,
    validate_experiment_manifests,
)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


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
    first = _command_evidence(patch.DVC_PUSH_COMMAND)
    first["terminal_status"] = "Everything is up to date."
    second = dict(first)
    return {
        "full_type_check": _command_evidence(patch.TYPE_CHECK_COMMAND),
        "focused_tests": focused,
        "poetry_check": _command_evidence(patch.POETRY_CHECK_COMMAND),
        "publication_guard": _command_evidence(patch.PUBLICATION_GUARD_COMMAND),
        "git_diff_check": _command_evidence(patch.DIFF_CHECK_COMMAND),
        "dvc_push_first": first,
        "dvc_push_second": second,
    }


def _schema_prelock() -> dict[str, Any]:
    head = "a" * 40
    records = [
        {
            "path": path,
            "role": patch.PATCH_COMPONENT_ROLES[path],
            "bytes": 1,
            "sha256": "2" * 64,
        }
        for path in patch.PATCH_PATHS
    ]
    entries = [
        {
            "status": "M" if path in patch.SUPERSEDED_COMPONENT_PATHS else "A",
            "path": path,
        }
        for path in patch.PATCH_PATHS
    ]
    paths = [path.as_posix() for path in patch.dlt.temporal_consumer_output_paths()]
    historical = dict(patch.P0_ARTIFACT_BUILDER_RECORD)
    authority = patch._historical_dltv_authority(
        require_physical_artifacts=False
    )
    h_dltv_runtime = dict(authority["h_dltv_runtime_builder_record"])
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
            "entries": entries,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "only_allowed_additions_and_modifications": True,
        },
        "patch_components": {
            "count": 11,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "records": records,
            "records_sha256": patch._record_digest(records),
        },
        "base_authority": authority,
        "builder_provenance": {
            "p0_artifact_builder_record": historical,
            "h_dltv_runtime_builder_record": h_dltv_runtime,
            "current_runtime_builder_record": {
                "path": historical["path"],
                "bytes": 120_000,
                "sha256": "3" * 64,
            },
            "all_records_are_distinct": True,
            "historical_record_source": "git_blob_at_p0_bundle_commit",
            "h_dltv_record_source": "git_blob_at_h_dltv_commit",
            "runtime_record_source": "physical_bytes_at_h_dltvm_head",
        },
        "consumer_prelock": {
            "model_id": "P0",
            "base_seeds": list(patch.dlt.REGISTERED_SEEDS),
            "count": 95,
            "paths": paths,
            "paths_sha256": patch._path_digest(paths),
            "all_absent_at_lock": True,
        },
    }


def test_closed_topology_and_exact_h_scope() -> None:
    assert patch.PATCH_BASE_COMMIT == "40c0fb08b279383083d129f2228403e5753cddda"
    assert patch.H_DLTV_COMMIT == patch.PATCH_BASE_COMMIT
    assert len(patch.SUPERSEDED_COMPONENT_PATHS) == 6
    assert len(patch.PRESERVED_DLTV_COMPONENT_PATHS) == 5
    assert len(patch.PATCH_PATHS) == 11
    assert len(patch.PATCH_ADDED_PATHS) == 5
    assert set(patch.PATCH_ADDED_PATHS) == {
        "configs/closure_v1/development_runtime_temporal_validation_manifest_patch_lock.schema.json",
        "docs/closure_v1/E0_D_RUNTIME_TEMPORAL_VALIDATION_MANIFEST_PATCH_1.md",
        "src/experiments/closure_development_runtime_temporal_validation_manifest_patch.py",
        "src/experiments/lock_closure_development_runtime_temporal_validation_manifest_patch.py",
        "tests/test_closure_development_runtime_temporal_validation_manifest_patch.py",
    }


def test_historical_builder_record_is_the_exact_p0_git_blob() -> None:
    blob = patch._git_blob(
        patch.P0_BUNDLE_COMMIT,
        str(patch.P0_ARTIFACT_BUILDER_RECORD["path"]),
    )
    assert blob is not None
    assert len(blob) == 110_034
    assert patch._sha256_bytes(blob) == (
        "dc500d94c8ca4b3705d2cb849a037524e33915624cd86f9d355e5c4eebb347f6"
    )


def test_h_dltv_builder_record_is_separate_git_provenance() -> None:
    record = patch._builder_record_at_commit(patch.H_DLTV_COMMIT)
    assert record == {
        "path": "src/experiments/build_closure_pipe_sequences.py",
        "bytes": 110_067,
        "sha256": "498c5b8ac673605e2164426624e968cd02c2180c2d2e0135c8e586c76b8ff411",
    }
    assert record != patch.P0_ARTIFACT_BUILDER_RECORD


def test_real_p_dlt_lock_independently_anchors_manifest_builder_triplet() -> None:
    lock = _load_json(patch.PROJECT_ROOT / patch.DEFAULT_DLT_LOCK_PATH)
    observed = patch._validate_p0_artifact_builder_provenance(lock)
    assert observed["p0_artifact_builder_record"] == patch.P0_ARTIFACT_BUILDER_RECORD
    assert observed["manifest_trusted_as_authority"] is False
    assert observed["git_blob_verified"] is True
    assert observed["p_dlt_authority_verified"] is True


def test_p_dlt_builder_anchor_uses_historical_records_not_a_current_alias() -> None:
    lock = _load_json(patch.PROJECT_ROOT / patch.DEFAULT_DLT_LOCK_PATH)
    authority = lock["base_authority"]["superseded_components"]
    assert "historical_records" in authority
    assert "records" not in authority
    corrupted = json.loads(json.dumps(lock))
    records = corrupted["base_authority"]["superseded_components"][
        "historical_records"
    ]
    records[0]["sha256"] = "f" * 64
    with pytest.raises(
        patch.DevelopmentRuntimeTemporalValidationManifestPatchError,
        match="independently anchor",
    ):
        patch._validate_p0_artifact_builder_provenance(corrupted)


def test_manifest_cannot_self_declare_a_different_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = _load_json(patch.PROJECT_ROOT / patch.DEFAULT_DLT_LOCK_PATH)
    real = patch._load_regular_json(
        patch.dlt.P0_MANIFEST_PATH,
        context="P0 sequence manifest",
    )
    drifted = json.loads(json.dumps(real))
    drifted["script"]["sha256"] = "f" * 64

    def fake_load(path: Path, *, context: str) -> dict[str, Any]:
        del context
        if path == patch.dlt.P0_MANIFEST_PATH:
            return drifted
        raise AssertionError(path)

    monkeypatch.setattr(patch, "_load_regular_json", fake_load)
    with pytest.raises(
        patch.DevelopmentRuntimeTemporalValidationManifestPatchError,
        match="historical artifact builder",
    ):
        patch._validate_p0_artifact_builder_provenance(lock)


def test_current_builder_record_is_physical_and_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = b"current runtime builder\n"
    expected = {
        "path": str(patch.P0_ARTIFACT_BUILDER_RECORD["path"]),
        "bytes": len(runtime),
        "sha256": patch._sha256_bytes(runtime),
    }
    monkeypatch.setattr(patch, "_git_blob", lambda _commit, _path: runtime)
    monkeypatch.setattr(
        patch,
        "_file_record",
        lambda _path, *, role: {**expected, "role": role},
    )
    assert patch._current_runtime_builder_record("a" * 40) == expected


def test_current_builder_cannot_collapse_into_historical_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    historical = patch._git_blob(
        patch.P0_BUNDLE_COMMIT,
        str(patch.P0_ARTIFACT_BUILDER_RECORD["path"]),
    )
    assert historical is not None
    monkeypatch.setattr(patch, "_git_blob", lambda _commit, _path: historical)
    monkeypatch.setattr(
        patch,
        "_file_record",
        lambda _path, *, role: {**patch.P0_ARTIFACT_BUILDER_RECORD, "role": role},
    )
    with pytest.raises(
        patch.DevelopmentRuntimeTemporalValidationManifestPatchError,
        match="domains were not separated",
    ):
        patch._current_runtime_builder_record("a" * 40)


def test_partition_requires_exact_six_plus_five() -> None:
    records = [
        {
            "path": path,
            "role": f"role-{index}",
            "bytes": index,
            "sha256": f"{index:064x}",
        }
        for index, path in enumerate(
            (*patch.SUPERSEDED_COMPONENT_PATHS, *patch.PRESERVED_DLTV_COMPONENT_PATHS),
            start=1,
        )
    ]
    superseded, preserved = patch.partition_dltv_component_records(records)
    assert [record["path"] for record in superseded] == list(
        patch.SUPERSEDED_COMPONENT_PATHS
    )
    assert [record["path"] for record in preserved] == list(
        patch.PRESERVED_DLTV_COMPONENT_PATHS
    )
    with pytest.raises(
        patch.DevelopmentRuntimeTemporalValidationManifestPatchError,
        match=r"6\+5 partition",
    ):
        patch.partition_dltv_component_records(records[:-1])


def test_verification_is_closed_and_requires_two_idempotent_pushes() -> None:
    verification = _verification()
    patch.validate_temporal_validation_manifest_patch_verification(verification)
    verification["dvc_push_second"]["terminal_status"] = "1 file pushed"
    with pytest.raises(
        patch.DevelopmentRuntimeTemporalValidationManifestPatchError,
        match="dvc_push_second",
    ):
        patch.validate_temporal_validation_manifest_patch_verification(verification)


def test_lock_schema_has_closed_authority_and_provenance_sections() -> None:
    schema = _load_json(patch.PROJECT_ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["lock_version"]["const"] == patch.LOCK_VERSION
    assert schema["properties"]["gate"]["const"] == "E0-DLTVM"
    assert "builder_provenance" in schema["required"]
    assert schema["$defs"]["consumerPrelock"]["properties"]["count"]["const"] == 95


def test_built_payload_validates_against_real_schema() -> None:
    payload = patch.build_temporal_validation_manifest_patch_lock_payload(
        _schema_prelock(),
        _verification(),
        created_at_utc="2026-08-05T00:00:00Z",
    )
    schema = _load_json(patch.PROJECT_ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA)
    validate_json_schema(payload, schema, instance_path="$.lock")


def test_cpu_only_gate_rejects_before_loading_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        patch,
        "load_and_validate_development_runtime_temporal_validation_manifest_patch_lock",
        lambda **_kwargs: pytest.fail("lock loader must not run"),
    )
    with pytest.raises(
        patch.DevelopmentRuntimeTemporalValidationManifestPatchError,
        match="CPU",
    ):
        patch.require_development_fit_authorized_with_temporal_validation_manifest_patch(
            device="cuda"
        )


def test_effective_gate_exposes_both_builder_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = {
        "path": patch.P0_ARTIFACT_BUILDER_RECORD["path"],
        "bytes": 120_000,
        "sha256": "a" * 64,
    }
    summary: dict[str, Any] = {
        "publication_verified": True,
        "remote_publication_verified": True,
        "physical_artifacts_verified": True,
        "historical_authority_verified": True,
        "patch_components_verified": True,
        "builder_provenance_verified": True,
        "companion_dialect_verified": True,
        "locked_head_is_ancestor": True,
        "development_fit_authorized": True,
        "fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "p0_artifact_builder_record": dict(patch.P0_ARTIFACT_BUILDER_RECORD),
        "h_dltv_runtime_builder_record": patch._builder_record_at_commit(
            patch.H_DLTV_COMMIT
        ),
        "current_runtime_builder_record": current,
    }
    monkeypatch.setattr(
        patch,
        "load_and_validate_development_runtime_temporal_validation_manifest_patch_lock",
        lambda **_kwargs: ({}, summary),
    )
    observed = patch.require_development_fit_authorized_with_temporal_validation_manifest_patch(
        device="cpu"
    )
    assert observed["p0_artifact_builder_record"] == patch.P0_ARTIFACT_BUILDER_RECORD
    assert observed["current_runtime_builder_record"] == current


def test_companion_separates_physical_and_historical_inputs() -> None:
    payload = _schema_prelock()
    payload["created_at_utc"] = "2026-08-05T00:00:00Z"
    lock_record = {
        "path": patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "role": "external_development_runtime_temporal_validation_dialect_patch_lock",
        "bytes": 2,
        "sha256": "1" * 64,
    }
    companion = patch._expected_companion(payload, lock_record=lock_record)
    assert companion["outputs"] == [lock_record]
    assert companion["inputs"][0]["path"] == patch.DEFAULT_DLT_LOCK_PATH.as_posix()
    assert companion["physical_inputs_only"] is True
    assert companion["historical_inputs_compared_to_current_paths"] is False
    assert {record["role"] for record in companion["historical_inputs"]} == {
        "historical_p0_artifact_builder",
        "historical_h_dltv_runtime_builder",
    }
    assert all(
        not str(record["role"]).startswith("historical_")
        for record in companion["inputs"]
    )
    assert companion["historical_inputs"][0] == {
        **patch.P0_ARTIFACT_BUILDER_RECORD,
        "role": "historical_p0_artifact_builder",
        "commit": patch.P0_BUNDLE_COMMIT,
        "hash_source": "git_blob_at_commit",
    }
    assert companion["historical_inputs"][1]["role"] == (
        "historical_h_dltv_runtime_builder"
    )


def test_generic_precommit_ignores_strict_historical_inputs_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lock = patch.DEFAULT_PATCH_LOCK_PATH
    manifest = patch.DEFAULT_PATCH_MANIFEST_PATH
    script = Path(
        "src/experiments/"
        "lock_closure_development_runtime_temporal_validation_manifest_patch.py"
    )
    schema = patch.DEFAULT_PATCH_LOCK_SCHEMA
    validator = Path(
        "src/experiments/"
        "closure_development_runtime_temporal_validation_manifest_patch.py"
    )
    base_validator = Path(
        "src/experiments/"
        "closure_development_runtime_temporal_validation_patch.py"
    )
    current_builder = Path("src/experiments/build_closure_pipe_sequences.py")
    for path, content in (
        (lock, b"{\"status\": \"locked\"}\n"),
        (script, b"print('locker')\n"),
        (schema, b"{\"type\": \"object\"}\n"),
        (validator, b"print('validator')\n"),
        (base_validator, b"print('base-validator')\n"),
        (current_builder, b"current-runtime-builder\n"),
        (patch.DEFAULT_DLT_LOCK_PATH, b"{\"status\": \"locked\"}\n"),
        (patch.DEFAULT_DLT_MANIFEST_PATH, b"{\"status\": \"completed\"}\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def record(path: Path, role: str) -> dict[str, Any]:
        payload = path.read_bytes()
        return {
            "path": path.as_posix(),
            "role": role,
            "bytes": len(payload),
            "sha256": patch._sha256_bytes(payload),
        }

    payload = {
        "created_at_utc": "2026-08-05T00:00:00Z",
        "patch_components": {
            "records": [
                record(script, patch.PATCH_COMPONENT_ROLES[script.as_posix()]),
                record(schema, patch.PATCH_COMPONENT_ROLES[schema.as_posix()]),
                record(validator, patch.PATCH_COMPONENT_ROLES[validator.as_posix()]),
                record(
                    current_builder,
                    patch.PATCH_COMPONENT_ROLES[current_builder.as_posix()],
                ),
            ]
        },
        "base_authority": {
            "nested_base_authority": {
                "records": [
                    record(patch.DEFAULT_DLT_LOCK_PATH, "base_lock"),
                    record(patch.DEFAULT_DLT_MANIFEST_PATH, "base_companion"),
                ]
            },
            "component_bundle": {
                "records": [record(base_validator, "base_validator")]
            },
        },
        "builder_provenance": {
            "h_dltv_runtime_builder_record": {
                "path": current_builder.as_posix(),
                "bytes": 110_067,
                "sha256": "498c5b8ac673605e2164426624e968cd02c2180c2d2e0135c8e586c76b8ff411",
            }
        },
    }
    companion = patch._expected_companion(
        payload,
        lock_record=record(
            lock,
            "external_development_runtime_temporal_validation_dialect_patch_lock",
        ),
    )
    manifest.write_text(json.dumps(companion, indent=2) + "\n", encoding="utf-8")
    findings = validate_experiment_manifests(
        staged_paths={lock, manifest},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=True,
    )
    assert len(findings) == 1
    assert findings[0].level == "ok"
    assert findings[0].check == "manifest"
    assert not has_failing_findings(findings)

    current_builder.write_bytes(b"changed-runtime-builder\n")
    findings = validate_experiment_manifests(
        staged_paths={lock, manifest},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=True,
    )
    assert has_failing_findings(findings)


def test_dltvm_locker_uses_closed_namespace_and_exact_summary() -> None:
    assert locker._closed_output(
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_LOCK_PATH,
    ) == patch.PROJECT_ROOT / patch.DEFAULT_PATCH_LOCK_PATH
    assert locker.OUTPUT_GUARD_DIRECTORY != locker.hardened.OUTPUT_GUARD_DIRECTORY
    assert locker._parse_focused_summary(
        f"{patch.FOCUSED_TEST_COUNT} passed in 1.25s\n",
        "",
    ) == patch.FOCUSED_TEST_COUNT
    with pytest.raises(
        patch.DevelopmentRuntimeTemporalValidationManifestPatchError,
        match="one exact clean result",
    ):
        locker._parse_focused_summary(
            f"{patch.FOCUSED_TEST_COUNT - 1} passed in 1.25s\n",
            "",
        )


def test_check_only_rejects_symlinked_guard_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repository"
    tmp_root = project_root / "tmp"
    outside = tmp_path / "outside"
    tmp_root.mkdir(parents=True)
    outside.mkdir()
    guard_directory = tmp_root / "closure_v1_e0_dltvm_locker"
    guard_directory.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(locker, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)

    with pytest.raises(
        patch.DevelopmentRuntimeTemporalValidationManifestPatchError,
        match="guard directory",
    ):
        locker._guard_paths(create_directory=False)


def test_historical_inputs_mutation_matrix_is_rejected_by_strict_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _schema_prelock()
    payload["created_at_utc"] = "2026-08-05T00:00:00Z"
    lock_record = {
        "path": patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "role": "external_development_runtime_temporal_validation_dialect_patch_lock",
        "bytes": 2,
        "sha256": "1" * 64,
    }
    expected = patch._expected_companion(payload, lock_record=lock_record)
    variants: list[dict[str, Any]] = []

    mutated = json.loads(json.dumps(expected))
    mutated["historical_inputs"][0]["sha256"] = "f" * 64
    variants.append(mutated)
    omitted = json.loads(json.dumps(expected))
    omitted["historical_inputs"].pop(0)
    variants.append(omitted)
    duplicated = json.loads(json.dumps(expected))
    duplicated["historical_inputs"].append(
        dict(duplicated["historical_inputs"][0])
    )
    variants.append(duplicated)
    relocated = json.loads(json.dumps(expected))
    relocated["inputs"].append(relocated["historical_inputs"].pop(0))
    variants.append(relocated)

    monkeypatch.setattr(
        patch,
        "validate_development_runtime_temporal_validation_manifest_patch_lock_payload",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        patch,
        "_file_record",
        lambda _path, *, role: {**lock_record, "role": role},
    )
    for companion in variants:
        def fake_load(path: Path, *, context: str) -> dict[str, Any]:
            del context
            if path == patch.DEFAULT_PATCH_LOCK_PATH:
                return payload
            if path == patch.DEFAULT_PATCH_LOCK_SCHEMA:
                return {}
            if path == patch.DEFAULT_PATCH_MANIFEST_PATH:
                return companion
            raise AssertionError(path)

        monkeypatch.setattr(patch, "_load_regular_json", fake_load)
        with pytest.raises(
            patch.DevelopmentRuntimeTemporalValidationManifestPatchError,
            match="companion drifted",
        ):
            patch.load_and_validate_development_runtime_temporal_validation_manifest_patch_lock(
                require_published=False,
                require_physical_artifacts=False,
            )


def test_guard_probe_is_fresh_clone_safe_and_non_writing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repository"
    project_root.mkdir()
    guard_directory = project_root / "tmp" / "closure_v1_e0_dltvm_locker"
    monkeypatch.setattr(locker, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)

    guards = locker._guard_paths(create_directory=False)

    assert guards == tuple(
        guard_directory / name for name in locker.OUTPUT_GUARD_NAMES
    )
    assert not (project_root / "tmp").exists()


def test_execute_lock_rolls_back_after_lock_publication_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repository"
    (project_root / patch.DEFAULT_PATCH_LOCK_PATH.parent).mkdir(parents=True)
    guard_directory = project_root / "tmp" / "closure_v1_e0_dltvm_locker"
    output = project_root / patch.DEFAULT_PATCH_LOCK_PATH
    companion = project_root / patch.DEFAULT_PATCH_MANIFEST_PATH
    prelock = _schema_prelock()

    monkeypatch.setattr(locker, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker.hardened, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)
    monkeypatch.setattr(
        locker,
        "collect_temporal_validation_manifest_patch_prelock_state",
        lambda **_kwargs: prelock,
    )
    monkeypatch.setattr(locker, "run_temporal_validation_manifest_patch_verification", _verification)
    monkeypatch.setattr(locker, "consumer_namespace_absence", lambda: {})
    monkeypatch.setattr(locker, "_load_regular_json", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        locker,
        "validate_development_runtime_temporal_validation_manifest_patch_lock_payload",
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

    with pytest.raises(RuntimeError, match="injected companion publication failure"):
        locker._execute_lock(patch.DEFAULT_PATCH_LOCK_PATH, patch.DEFAULT_PATCH_MANIFEST_PATH)

    reserved = (
        output,
        output.with_suffix(output.suffix + ".tmp"),
        companion,
        companion.with_suffix(companion.suffix + ".tmp"),
        *(guard_directory / name for name in locker.OUTPUT_GUARD_NAMES),
    )
    assert all(not path.exists() for path in reserved)
