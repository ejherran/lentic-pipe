from __future__ import annotations

import copy
import inspect
import json
import os
from pathlib import Path
from typing import Any, Mapping, cast

import pytest

from src.experiments import closure_development_runtime_patch as dlp
from src.experiments import closure_p1_sequence_builder_patch as e0_mb
from src.experiments import closure_p1_sequence_historical_anfis_patch as patch
from src.experiments import lock_closure_p1_sequence_historical_anfis_patch as locker


def _real_seed_manifest() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            (patch.PROJECT_ROOT / dlp.SEED_MANIFEST_PATH).read_text(
                encoding="utf-8"
            )
        ),
    )


def _record(path: str, role: str, token: str = "a") -> dict[str, Any]:
    return {
        "path": path,
        "role": role,
        "bytes": 1,
        "sha256": token * 64,
    }


def _effective_summary() -> dict[str, Any]:
    return {
        "status": "published_p1_sequence_historical_anfis_patch_valid",
        "gate": patch.PATCH_GATE,
        "authorized_model_id": patch.AUTHORIZED_MODEL_ID,
        "authorized_base_seed": patch.AUTHORIZED_BASE_SEED,
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_e0_mb_verified": True,
        "historical_e0_dlp_verified": True,
        "historical_anfis_context_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": True,
        "prior_one_shot_authorization_consumed": True,
        "p1_sequence_retry_authorized": True,
        "p1_sequence_builder_authorized": True,
        "authorization_effective": True,
        "batch_seed_execution_authorized": False,
        "retry_under_previous_authority_authorized": False,
        "effective_in_payload": False,
        "publication_required": False,
        "p1_fit_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authorization_inputs": [
            _record(
                patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
                "external_p1_sequence_historical_anfis_patch_lock",
            ),
            _record(
                patch.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
                "p1_sequence_historical_anfis_patch_companion",
                "b",
            ),
        ],
    }


def _verification(*, focused_count: int) -> dict[str, Any]:
    def evidence(command: tuple[str, ...]) -> dict[str, Any]:
        return {
            "command": list(command),
            "returncode": 0,
            "stdout_sha256": "a" * 64,
            "stderr_sha256": "b" * 64,
            "stdout_line_count": 1,
            "stderr_line_count": 0,
        }

    focused = evidence(patch.FOCUSED_TEST_COMMAND)
    focused.update(
        {
            "test_count": focused_count,
            "skipped_count": 0,
            "deselected_count": 0,
        }
    )
    return {
        "full_type_check": evidence(patch.TYPE_CHECK_COMMAND),
        "focused_tests": focused,
        "poetry_check": evidence(patch.POETRY_CHECK_COMMAND),
        "publication_guard": evidence(patch.PUBLICATION_GUARD_COMMAND),
        "git_diff_check": evidence(patch.DIFF_CHECK_COMMAND),
    }


def test_h_patch_scope_is_exact_two_modified_plus_five_added() -> None:
    assert patch.PATCH_BASE_COMMIT == "34c0b4e3203eca32bee69732a823519f2b0e61eb"
    assert patch.PATCH_MODIFIED_PATHS == (
        "src/experiments/build_closure_pipe_sequences.py",
        "tests/test_build_closure_pipe_sequences.py",
    )
    assert len(patch.PATCH_PATHS) == 7
    assert len(patch.PATCH_ADDED_PATHS) == 5
    assert set(patch.PATCH_MODIFIED_PATHS).isdisjoint(patch.PATCH_ADDED_PATHS)


def test_historical_partitions_are_closed() -> None:
    assert patch.E0_MB_SUPERSEDED_PATHS == patch.PATCH_MODIFIED_PATHS
    assert len(patch.E0_MB_PRESERVED_PATHS) == 5
    assert patch.E0_DLP_SUPERSEDED_PATHS == patch.PATCH_MODIFIED_PATHS
    assert len(patch.E0_DLP_PRESERVED_DRIFT_PATHS) == 4
    assert set(patch.E0_DLP_SUPERSEDED_PATHS).isdisjoint(
        patch.E0_DLP_PRESERVED_DRIFT_PATHS
    )


def test_legacy_e0_dlp_drift_logic_reproduces_the_incident() -> None:
    base = dlp._base_lock_snapshot(dlp.DEFAULT_LOCK_PATH, dlp.DEFAULT_LOCK_SCHEMA)
    with pytest.raises(
        dlp.DevelopmentRuntimePatchError,
        match=(
            "patched base component differs from Git-at-H: "
            "src/experiments/build_closure_pipe_sequences.py"
        ),
    ):
        dlp._base_component_drift(
            cast(Mapping[str, Any], base["payload"]),
            patch.E0_DLP_H_COMMIT,
        )


def test_real_historical_e0_dlp_reconstruction_avoids_effective_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dlp,
        "load_and_validate_development_runtime_patch_lock",
        lambda *args, **kwargs: pytest.fail("effective E0-DLP loader must not run"),
    )
    authority = patch._reconstruct_historical_e0_dlp_authority(
        execution_head=patch._git("rev-parse", "HEAD"),
        require_physical_artifacts=True,
    )
    assert authority["effective_dlp_loader_called"] is False
    assert authority["superseded_drift_components"]["count"] == 2
    assert authority["preserved_drift_components"]["count"] == 4
    assert authority["preserved_patch_components"]["count"] == 5
    dlp_payload = patch._load_regular_json(
        dlp.DEFAULT_PATCH_LOCK_PATH,
        context="test P-E0-DLP lock",
    )
    assert authority["adopted_seed_manifest"] == cast(
        Mapping[str, Any],
        dlp_payload["adopted_seed_bundle"],
    )["manifest"]


def test_dlp_drift_reconstruction_reads_the_base_lock_snapshot() -> None:
    payload = patch._load_regular_json(
        dlp.DEFAULT_PATCH_LOCK_PATH,
        context="test P-E0-DLP lock",
    )
    records = patch._expected_dlp_drift_records(payload)
    assert len(records) == 6
    assert [record["path"] for record in records] == sorted(
        dlp.BASE_COMPONENT_DRIFT_ALLOWLIST
    )


def test_real_historical_e0_mb_reconstruction_partitions_components() -> None:
    authority = patch._reconstruct_published_e0_mb_historical_authority(
        execution_head=patch._git("rev-parse", "HEAD")
    )
    assert authority["patch_head"] == patch.E0_MB_H_COMMIT
    assert authority["lock_commit"] == patch.E0_MB_P_COMMIT
    assert authority["superseded_components"]["count"] == 2
    assert authority["preserved_components"]["count"] == 5
    assert authority["p1_sequence_builder_authorized"] is False


def test_nonhistorical_manifest_has_no_compatibility_fallback() -> None:
    assert (
        patch.historical_seed_1729_anfis_context(
            {"dependencies": [], "inputs": []},
            authorization=None,
        )
        is None
    )


def test_historical_manifest_requires_explicit_effective_authority() -> None:
    with pytest.raises(
        patch.P1SequenceHistoricalAnfisPatchError,
        match="requires explicit E0-MC authority",
    ):
        patch.historical_seed_1729_anfis_context(
            _real_seed_manifest(),
            authorization=None,
        )


def test_historical_seed_identity_cannot_fall_back_if_both_records_drift() -> None:
    payload = copy.deepcopy(_real_seed_manifest())
    historical_path = str(dlp.HISTORICAL_RUNTIME_VALIDATOR_RECORD["path"])
    for field in ("dependencies", "inputs"):
        target = next(
            record
            for record in payload[field]
            if record.get("path") == historical_path
        )
        target["sha256"] = "0" * 64
    with pytest.raises(
        patch.P1SequenceHistoricalAnfisPatchError,
        match="runtime-validator record is not unique and exact",
    ):
        patch.historical_seed_1729_anfis_context(
            payload,
            authorization=_effective_summary(),
        )


def test_real_historical_manifest_passes_only_the_new_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dlp,
        "load_and_validate_development_runtime_patch_lock",
        lambda *args, **kwargs: pytest.fail("legacy effective loader must not run"),
    )
    context = patch.historical_seed_1729_anfis_context(
        _real_seed_manifest(),
        authorization=_effective_summary(),
    )
    assert context is not None
    assert context["base_seed"] == 1729
    assert context["historical_uppercase_artifact_paths"] is True
    assert context["effective_dlp_loader_called"] is False
    assert set(context["historical_source_records"]) == {
        "generating_script",
        "strict_anfis_state_adapter",
        "runtime_lock_validator",
    }


def test_historical_context_rejects_every_broadened_or_incomplete_authority() -> None:
    mutations = {
        "batch_seed_execution_authorized": True,
        "effective_in_payload": True,
        "publication_required": True,
        "transactional_builder_verified": False,
        "sequence_namespace_absent": False,
    }
    for field, value in mutations.items():
        authority = {**_effective_summary(), field: value}
        with pytest.raises(
            patch.P1SequenceHistoricalAnfisPatchError,
            match="historical context authorization drifted",
        ):
            patch.historical_seed_1729_anfis_context(
                _real_seed_manifest(),
                authorization=authority,
            )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("seed", "frozen seed-1729 manifest"),
        ("runtime_record", "runtime-validator record is not unique and exact"),
        ("fitter_record", "fitter provenance is not unique and exact"),
    ),
)
def test_historical_manifest_near_matches_fail_closed(
    mutation: str,
    message: str,
) -> None:
    payload = copy.deepcopy(_real_seed_manifest())
    if mutation == "seed":
        payload["base_seed"] = 20260612
    elif mutation == "runtime_record":
        target = next(
            record
            for record in payload["dependencies"]
            if record.get("role") == "runtime_lock_validator"
        )
        target["sha256"] = "0" * 64
    else:
        target = next(
            record
            for record in payload["dependencies"]
            if record.get("role") == "strict_anfis_state_adapter"
        )
        target["sha256"] = "0" * 64
    with pytest.raises(patch.P1SequenceHistoricalAnfisPatchError, match=message):
        patch.historical_seed_1729_anfis_context(
            payload,
            authorization=_effective_summary(),
        )


@pytest.mark.parametrize(
    ("model_id", "base_seed"),
    (("P0", 1729), ("P1", None), ("P1", 20260612), ("P2", 1729)),
)
def test_gate_rejects_every_non_authorized_identity_before_loading(
    monkeypatch: pytest.MonkeyPatch,
    model_id: str,
    base_seed: int | None,
) -> None:
    monkeypatch.setattr(
        patch,
        "load_and_validate_p1_sequence_historical_anfis_patch_lock",
        lambda: pytest.fail("loader must not run"),
    )
    with pytest.raises(
        patch.P1SequenceHistoricalAnfisPatchError,
        match="only the one-shot P1 sequence build for seed 1729",
    ):
        patch.require_p1_sequence_historical_anfis_authorized(model_id, base_seed)


def test_effective_gate_preserves_all_false_seals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = _effective_summary()
    monkeypatch.setattr(
        patch,
        "load_and_validate_p1_sequence_historical_anfis_patch_lock",
        lambda: ({}, summary),
    )
    monkeypatch.setattr(patch, "p1_sequence_namespace_absence", lambda: {})
    monkeypatch.setattr(patch, "closure_progression_namespace_absence", lambda: {})
    observed = patch.require_p1_sequence_historical_anfis_authorized("P1", 1729)
    assert observed["p1_sequence_builder_authorized"] is True
    assert observed["p1_fit_authorized"] is False
    assert observed["e0_m_authorized"] is False
    assert observed["evaluation_authorized"] is False
    assert observed["e0_u_authorized"] is False
    assert observed["future_outcomes_accessed"] is False


def test_effective_gate_rejects_a_self_authorized_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = {**_effective_summary(), "p1_fit_authorized": True}
    monkeypatch.setattr(
        patch,
        "load_and_validate_p1_sequence_historical_anfis_patch_lock",
        lambda: ({}, summary),
    )
    with pytest.raises(
        patch.P1SequenceHistoricalAnfisPatchError,
        match="fail-closed seals drifted",
    ):
        patch.require_p1_sequence_historical_anfis_authorized("P1", 1729)


def test_effective_loader_exposes_no_arguments_or_unpublished_bypass() -> None:
    assert inspect.signature(
        patch.load_and_validate_p1_sequence_historical_anfis_patch_lock
    ).parameters == {}
    assert patch.PATCH_AUTHORIZATIONS["p1_sequence_builder_authorized"] is False
    assert patch.PATCH_AUTHORIZATIONS["publication_required"] is True


def test_verification_contract_has_no_dvc_or_outcome_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch, "FOCUSED_TEST_COUNT", 1)
    evidence = _verification(focused_count=1)
    patch.validate_p1_sequence_historical_anfis_patch_verification(evidence)
    evidence["dvc_push"] = {
        "command": ["dvc", "push"],
        "returncode": 0,
    }
    with pytest.raises(
        patch.P1SequenceHistoricalAnfisPatchError,
        match="verification fields drifted",
    ):
        patch.validate_p1_sequence_historical_anfis_patch_verification(evidence)


def test_companion_separates_current_and_historical_inputs() -> None:
    component_records = [
        _record(path, role, "abcdef0"[index])
        for index, (path, role) in enumerate(patch.PATCH_COMPONENT_ROLES.items())
    ]
    by_path = {record["path"]: record for record in component_records}
    mb_superseded = [
        _record(path, e0_mb.PATCH_COMPONENT_ROLES[path], "c")
        for path in patch.E0_MB_SUPERSEDED_PATHS
    ]
    dlp_superseded = [
        {
            "path": path,
            "base_bytes": 1,
            "base_sha256": "d" * 64,
            "patch_bytes": 2,
            "patch_sha256": "e" * 64,
        }
        for path in patch.E0_DLP_SUPERSEDED_PATHS
    ]
    payload = {
        "created_at_utc": "2026-08-05T00:00:00Z",
        "patch_components": {"records": component_records},
        "base_authorities": {
            "e0_mb": {
                "lock": _record(
                    e0_mb.DEFAULT_PATCH_LOCK_PATH.as_posix(),
                    "external_p1_sequence_builder_patch_lock",
                    "f",
                ),
                "companion_manifest": _record(
                    e0_mb.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
                    "p1_sequence_builder_patch_companion",
                    "1",
                ),
                "superseded_components": {"records": mb_superseded},
            },
            "e0_dlp": {
                "lock": _record(
                    dlp.DEFAULT_PATCH_LOCK_PATH.as_posix(),
                    "external_development_runtime_patch_lock",
                    "2",
                ),
                "companion_manifest": _record(
                    dlp.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
                    "development_runtime_patch_companion",
                    "3",
                ),
                "superseded_drift_components": {"records": dlp_superseded},
            },
        },
    }
    companion = patch._expected_companion(
        payload,
        lock_record=_record(
            patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "external_p1_sequence_historical_anfis_patch_lock",
            "4",
        ),
    )
    physical_paths = {record["path"] for record in companion["inputs"]}
    historical = companion["historical_inputs"]
    assert len(physical_paths) == 7
    assert len(historical) == 4
    assert all("commit" in record and "hash_source" in record for record in historical)
    assert by_path[patch.DEFAULT_PATCH_LOCK_SCHEMA.as_posix()]["path"] in physical_paths
    assert companion["historical_inputs_compared_to_current_paths"] is False
    assert companion["authoritative_contract"] is False


def test_schema_is_recursively_closed() -> None:
    schema = json.loads(
        (patch.PROJECT_ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text(
            encoding="utf-8"
        )
    )

    def assert_closed(node: object) -> None:
        if isinstance(node, dict):
            mapping = cast(dict[str, object], node)
            if mapping.get("type") == "object" or "properties" in mapping:
                assert mapping.get("additionalProperties") is False
            for value in mapping.values():
                assert_closed(value)
        elif isinstance(node, list):
            for value in node:
                assert_closed(value)

    assert_closed(schema)


def test_locker_exposes_three_mutually_exclusive_modes() -> None:
    assert locker._parse_args(["--check-only"]).check_only is True
    assert locker._parse_args(["--execute-lock"]).execute_lock is True
    assert locker._parse_args(["--check-effective"]).check_effective is True
    with pytest.raises(SystemExit):
        locker._parse_args(["--check-only", "--execute-lock"])


def test_check_effective_is_read_only_and_revalidates_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities = ((1, 2, 1, "a" * 64), (4, 5, 1, "b" * 64))
    calls: list[tuple[int, Path, Path]] = []

    def identity(
        directory_descriptor: int,
        output: Path,
        companion: Path,
    ) -> tuple[object, object]:
        calls.append((directory_descriptor, output, companion))
        return identities

    monkeypatch.setattr(locker, "_effective_bundle_identities", identity)
    monkeypatch.setattr(
        locker,
        "require_p1_sequence_historical_anfis_authorized",
        lambda **kwargs: _effective_summary(),
    )
    monkeypatch.setattr(locker, "p1_sequence_namespace_absence", lambda: {})
    monkeypatch.setattr(locker, "closure_progression_namespace_absence", lambda: {})
    result = locker._check_effective(
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_MANIFEST_PATH,
    )
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert result["status"] == "effective_preflight_passed"
    assert result["writes_performed"] is False
    assert result["dvc_commands_run"] is False
    assert result["outcome_paths_opened"] is False


def test_check_effective_rejects_bundle_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations = iter(
        [
            ((1, 2, 1, "a" * 64), (4, 5, 1, "b" * 64)),
            ((1, 2, 1, "a" * 64), (4, 5, 2, "b" * 64)),
        ]
    )
    monkeypatch.setattr(
        locker,
        "_effective_bundle_identities",
        lambda _descriptor, _output, _companion: next(observations),
    )
    monkeypatch.setattr(
        locker,
        "require_p1_sequence_historical_anfis_authorized",
        lambda **kwargs: _effective_summary(),
    )
    with pytest.raises(
        patch.P1SequenceHistoricalAnfisPatchError,
        match="lock bundle changed",
    ):
        locker._check_effective(
            patch.DEFAULT_PATCH_LOCK_PATH,
            patch.DEFAULT_PATCH_MANIFEST_PATH,
        )


def test_check_effective_binds_loader_inputs_to_anchored_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities = ((1, 2, 1, "a" * 64), (4, 5, 1, "b" * 64))
    monkeypatch.setattr(
        locker,
        "_effective_bundle_identities",
        lambda _descriptor, _output, _companion: identities,
    )
    summary = _effective_summary()
    summary["authorization_inputs"][0]["sha256"] = "c" * 64
    monkeypatch.setattr(
        locker,
        "require_p1_sequence_historical_anfis_authorized",
        lambda **_kwargs: summary,
    )
    with pytest.raises(
        patch.P1SequenceHistoricalAnfisPatchError,
        match="anchored authority input differs from loader",
    ):
        locker._check_effective(
            patch.DEFAULT_PATCH_LOCK_PATH,
            patch.DEFAULT_PATCH_MANIFEST_PATH,
        )


def test_anchored_identity_rejects_a_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    linked = tmp_path / "linked.json"
    linked.symlink_to(target.name)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(tmp_path, flags)
    try:
        with pytest.raises(
            patch.P1SequenceHistoricalAnfisPatchError,
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
    guard_directory = project_root / "tmp" / "closure_v1_e0_mc_locker"
    output = project_root / patch.DEFAULT_PATCH_LOCK_PATH
    companion = project_root / patch.DEFAULT_PATCH_MANIFEST_PATH
    prelock = {"stable": True}
    payload = {
        "created_at_utc": "2026-08-05T00:00:00Z",
        "patch_repository": {"head": "a" * 40},
    }
    monkeypatch.setattr(locker, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker.hardened, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)
    monkeypatch.setattr(
        locker,
        "collect_p1_sequence_historical_anfis_patch_prelock_state",
        lambda **_kwargs: prelock,
    )
    monkeypatch.setattr(
        locker,
        "run_p1_sequence_historical_anfis_patch_verification",
        lambda: {},
    )
    monkeypatch.setattr(locker, "p1_sequence_namespace_absence", lambda: {})
    monkeypatch.setattr(locker, "closure_progression_namespace_absence", lambda: {})
    monkeypatch.setattr(
        locker,
        "build_p1_sequence_historical_anfis_patch_lock_payload",
        lambda *_args, **_kwargs: payload,
    )
    monkeypatch.setattr(locker, "_load_regular_json", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        locker,
        "validate_p1_sequence_historical_anfis_patch_lock_payload",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        locker,
        "_expected_companion",
        lambda *_args, **_kwargs: {"status": "completed"},
    )
    monkeypatch.setattr(
        locker,
        "_load_unpublished_p1_sequence_historical_anfis_patch_lock",
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
        patch.P1SequenceHistoricalAnfisPatchError,
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


def _owner_for_path(path: Path) -> Any:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path.parent, flags)
    metadata = path.stat()
    return locker.hardened._OwnedFile(
        path=path,
        device=metadata.st_dev,
        inode=metadata.st_ino,
        directory_file_descriptor=descriptor,
    )


def test_failed_cleanup_unlinks_owned_final_through_anchored_parent(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "reports" / "protocol"
    parent.mkdir(parents=True)
    final = parent / "lock.json"
    final.write_bytes(b"owned\n")
    owner = _owner_for_path(final)
    displaced = tmp_path / "displaced"
    parent.rename(displaced)
    parent.mkdir(parents=True)
    foreign = parent / final.name
    foreign.write_bytes(b"foreign\n")

    locker._cleanup_lock_resources(
        (owner,),
        (),
        succeeded=False,
        active_error=RuntimeError("injected failure"),
    )
    assert not (displaced / final.name).exists()
    assert foreign.read_bytes() == b"foreign\n"


def test_success_cleanup_revalidates_finals_after_guard_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(locker.hardened, "PROJECT_ROOT", tmp_path)
    parent = tmp_path / "reports" / "protocol"
    parent.mkdir(parents=True)
    final = parent / "lock.json"
    final.write_bytes(b"owned\n")
    owner = _owner_for_path(final)
    displaced = tmp_path / "displaced"
    parent.rename(displaced)
    parent.mkdir(parents=True)
    foreign = parent / final.name
    foreign.write_bytes(b"foreign\n")

    with pytest.raises(
        patch.P1SequenceHistoricalAnfisPatchError,
        match="cleanup failed closed",
    ):
        locker._cleanup_lock_resources(
            (owner,),
            (),
            succeeded=True,
            active_error=None,
        )
    assert not (displaced / final.name).exists()
    assert foreign.read_bytes() == b"foreign\n"


def test_success_cleanup_rolls_back_if_guard_is_lost(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repository"
    (project_root / patch.DEFAULT_PATCH_LOCK_PATH.parent).mkdir(parents=True)
    guard_directory = project_root / "tmp" / "closure_v1_e0_mc_locker"
    output = project_root / patch.DEFAULT_PATCH_LOCK_PATH
    monkeypatch.setattr(locker, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker.hardened, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)
    guards = locker._acquire_guards(
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_MANIFEST_PATH,
    )
    owner = locker._publish_guarded_bytes(
        b"owned lock\n",
        output,
        patch.DEFAULT_PATCH_LOCK_PATH,
        guards[0],
    )
    guards[0].path.unlink()
    with pytest.raises(
        patch.P1SequenceHistoricalAnfisPatchError,
        match="cleanup failed closed",
    ):
        locker._cleanup_lock_resources(
            (owner,),
            guards,
            succeeded=True,
            active_error=None,
        )
    assert not output.exists()
