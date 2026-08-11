from __future__ import annotations

import inspect
import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from src.experiments import closure_final_calibration as mcal
from src.experiments import (
    closure_final_calibration_publication_guard_patch as patch,
)
from src.experiments import (
    lock_closure_final_calibration_publication_guard_patch as locker,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_H_MCAL = "5d096e8ca560a592a65ab231ae173c4d3b5a4ff6"
EXPECTED_SUPERSEDED = {
    "src/experiments/calibrate_closure_final_models.py",
    "src/experiments/run_closure_anfis_learning_curve.py",
    "tests/test_calibrate_closure_final_models.py",
    "tests/test_closure_anfis_learning_curve.py",
}
EXPECTED_PATCH_PATHS = {
    "configs/closure_v1/final_calibration_publication_guard_patch_lock.schema.json",
    "docs/closure_v1/E0_M_FINAL_CALIBRATION_PUBLICATION_GUARD_PATCH_1.md",
    *EXPECTED_SUPERSEDED,
    "src/experiments/closure_final_calibration_publication_guard_patch.py",
    "src/experiments/lock_closure_final_calibration_publication_guard_patch.py",
    "tests/test_closure_final_calibration_publication_guard_patch.py",
}


def _schema() -> dict[str, Any]:
    value = json.loads(
        (
            ROOT
            / "configs/closure_v1/final_calibration_publication_guard_patch_lock.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert isinstance(value, dict)
    return value


def _prepare_parent(root: Path, relative: Path) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _artifact_record(path: str, index: int) -> dict[str, Any]:
    return {
        "role": f"component_{index}",
        "path": path,
        "bytes": index + 1,
        "sha256": f"{index + 1:064x}",
    }


def _synthetic_p_payload() -> dict[str, Any]:
    preserved = [
        _artifact_record(f"preserved/component_{index}.py", index)
        for index in range(8)
    ]
    current_paths = [
        patch.LOCKER_PATH.as_posix(),
        *(f"current/component_{index}.py" for index in range(1, 9)),
    ]
    current = [
        _artifact_record(path, index + 8)
        for index, path in enumerate(current_paths)
    ]
    historical = [
        {
            **_artifact_record(f"historical/component_{index}.py", index + 17),
            "git_commit": BASE_H_MCAL,
            "git_blob": f"{index + 21:040x}",
        }
        for index in range(4)
    ]
    return {
        "repository": {"h_patch_head": "a" * 40},
        "verification": {"synthetic": True},
        "h_mcal_authority": {
            "preserved_components": preserved,
            "historical_inputs": historical,
        },
        "h_patch": {"components": current},
        "scientific_input_inventory": {
            "authority_records_sha256": "b" * 64,
            "payload_bindings_sha256": "c" * 64,
            "calibration_required_inputs": [],
            "calibration_required_inputs_sha256": "d" * 64,
            "e7_required_inputs": [],
            "e7_required_inputs_sha256": "e" * 64,
        },
    }


def _write_synthetic_p_bundle(
    root: Path, payload: dict[str, Any]
) -> tuple[Path, Path, dict[str, Any]]:
    lock = _prepare_parent(root, patch.DEFAULT_PATCH_LOCK_PATH)
    lock.write_bytes(patch._canonical_json_bytes(payload))
    lock_record = mcal._file_record(
        patch.DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_publication_guard_patch_lock",
        repo_root=root,
    )
    companion = patch._expected_companion(payload, lock_record)
    manifest = _prepare_parent(root, patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH)
    manifest.write_bytes(patch._canonical_json_bytes(companion))
    return lock, manifest, companion


def _install_synthetic_publisher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        patch,
        "_require_publication_verification",
        lambda payload, *, repo_root: None,
    )
    monkeypatch.setattr(
        patch,
        "validate_final_calibration_publication_guard_patch_lock_payload",
        lambda payload, *, repo_root, verify_remote: dict(payload),
    )
    monkeypatch.setattr(
        patch,
        "_physical_snapshot",
        lambda repo_root, *, scientific_inventory: (),
    )
    monkeypatch.setattr(
        patch,
        "_require_physical_snapshot",
        lambda expected, *, scientific_inventory, repo_root, context: None,
    )
    monkeypatch.setattr(mcal, "_git_head", lambda repo_root, ref="HEAD": "a" * 40)
    monkeypatch.setattr(patch, "_require_prelock_namespace", lambda *, repo_root: None)
    monkeypatch.setattr(
        patch.mt,
        "_acquire_publication_guard",
        lambda path, payload, *, repo_root: object(),
    )
    monkeypatch.setattr(
        patch.mt,
        "_release_publication_guard",
        lambda guard, *, tolerate_foreign=False: None,
    )


def test_h_p_r_topology_and_historical_partition_are_exact() -> None:
    schema = _schema()
    definitions = schema["$defs"]
    scope = definitions["scope"]["properties"]
    history = definitions["hMcalAuthority"]["properties"]
    assert schema["properties"]["gate"]["const"] == "E0-MCALP"
    assert definitions["repository"]["properties"]["base_h_mcal_commit"][
        "const"
    ] == BASE_H_MCAL
    assert (scope["added"]["const"], scope["modified"]["const"]) == (5, 4)
    assert set(scope["paths"]["const"]) == EXPECTED_PATCH_PATHS
    assert (
        history["component_count"]["const"],
        history["preserved_count"]["const"],
        history["superseded_count"]["const"],
    ) == (12, 8, 4)
    assert len(patch.FINAL_CALIBRATION_P_STAGED_SCOPE) == 2
    assert len(patch.FINAL_CALIBRATION_R_STAGED_SCOPE) == 8
    assert set(patch.PATCH_PATHS) == EXPECTED_PATCH_PATHS


def test_interrupted_attempt_is_indeterminate_clean_and_not_authority() -> None:
    properties = _schema()["$defs"]["interruptedAttempt"]["properties"]
    expected = {
        "attempted_gate": "E0-MCAL",
        "status": "interrupted_no_authority",
        "phase": "indeterminate",
        "authority_created": False,
        "final_output_count": 0,
        "temporary_output_count": 0,
        "active_guard_count": 0,
        "scientific_execution_run": False,
        "dvc_commands_run": False,
        "side_effect_count": 0,
    }
    assert {key: value["const"] for key, value in properties.items()} == expected
    assert patch.INTERRUPTED_ATTEMPT == expected
    text = (
        ROOT
        / "docs/closure_v1/E0_M_FINAL_CALIBRATION_PUBLICATION_GUARD_PATCH_1.md"
    ).read_text(encoding="utf-8")
    for token in (
        "E0-MCALP",
        "4M+5A",
        "8 preserved + 4 superseded",
        "17 physical + 4 historical + 1 output",
        "Ctrl-C",
        "indeterminate",
        "temp_identity",
        "foreign final survives",
        "P-E0-MCALP",
        "R bundle",
        "Holdout",
        "post-2021",
        "E0-M",
        "E0-U",
        "DVC",
    ):
        assert token in text
    assert "old `P-E0-MCAL` never existed" in text
    assert "completion companion remains the last publication" in text


def test_schema_preflight_accepts_only_the_supported_closed_schema() -> None:
    result = patch.preflight_final_calibration_publication_guard_patch_schema()
    assert result["gate"] == "E0-MCALP"
    assert result["supported_subset_verified"] is True
    assert result["schema_count"] == 1
    prelock = (
        patch.collect_final_calibration_publication_guard_patch_prelock_state(
            verify_remote=False
        )
    )
    assert prelock["h_patch"]["component_count"] == 9
    payload = patch.build_final_calibration_publication_guard_patch_lock_payload(
        prelock, generated_at_utc="2026-08-11T00:00:00+00:00"
    )
    assert (
        patch.validate_final_calibration_publication_guard_patch_lock_payload(
            payload, verify_remote=False
        )
        == payload
    )
    drifted = json.loads(patch._canonical_json_bytes(payload))
    drifted["authorizations"]["git_commit_authorized"] = True
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch.validate_final_calibration_publication_guard_patch_lock_payload(
            drifted, verify_remote=False
        )


def test_companion_contract_is_exact_17_physical_4_historical_1_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    companion = _schema()["$defs"]["prelock"]["properties"][
        "companion_contract"
    ]["properties"]
    assert companion["physical_input_count"]["const"] == 17
    assert companion["historical_input_count"]["const"] == 4
    assert companion["output_count"]["const"] == 1
    assert companion["manifest_written_last"]["const"] is True
    assert companion["script_path"]["const"] == (
        "src/experiments/lock_closure_final_calibration_publication_guard_patch.py"
    )
    assert patch.EXPECTED_COMPANION_INPUT_COUNT == 17
    assert patch.EXPECTED_HISTORICAL_INPUT_COUNT == 4
    assert patch.EXPECTED_COMPANION_OUTPUT_COUNT == 1

    payload = _synthetic_p_payload()
    lock, manifest, exact_companion = _write_synthetic_p_bundle(tmp_path, payload)
    monkeypatch.setattr(
        patch, "_validate_published_lock_payload", lambda value, *, repo_root: None
    )
    monkeypatch.setattr(
        patch,
        "_validate_p_publication",
        lambda value, *, verify_remote, repo_root: {"p_patch_head": "f" * 40},
    )
    monkeypatch.setattr(
        mcal,
        "_base_r_mze_authority",
        lambda *, repo_root: {
            "family_final_count": 12,
            "family_records_sha256": "1" * 64,
        },
    )
    monkeypatch.setattr(mcal, "_historical_e7_blockers", lambda *, repo_root: [])

    timestamp = 1_800_000_000_000_000_000
    for lock_ns, manifest_ns in (
        (timestamp, timestamp),
        (timestamp + 2_000_000_000, timestamp),
    ):
        os.utime(lock, ns=(lock_ns, lock_ns))
        os.utime(manifest, ns=(manifest_ns, manifest_ns))
        authority = (
            patch.load_effective_final_calibration_publication_guard_patch_authority(
                verify_remote=False, repo_root=tmp_path
            )
        )
        assert authority["status"] == "effective"
        assert authority["r_lifecycle_state"] == "ready_for_calibration_bundle"
        assert authority["calibration_development_run_authorized"] is True
        assert authority["e7_learning_curve_run_authorized"] is False
        assert authority["r_outputs_ready_for_staging"] is False

    for counts, lifecycle, calibration_allowed, e7_allowed, staging_ready in (
        (
            (6, 0),
            "calibration_completed_unpublished_ready_for_e7_bundle",
            False,
            True,
            False,
        ),
        ((6, 2), "both_bundles_completed_unpublished", False, False, True),
    ):
        with monkeypatch.context() as lifecycle_patch:
            lifecycle_patch.setattr(
                patch,
                "_validate_effective_namespace",
                lambda *, repo_root, c=counts, state=lifecycle: {
                    "calibration_output_present_count": c[0],
                    "e7_output_present_count": c[1],
                    "r_output_present_count": sum(c),
                    "r_lifecycle_state": state,
                },
            )
            authority = (
                patch.load_effective_final_calibration_publication_guard_patch_authority(
                    verify_remote=False, repo_root=tmp_path
                )
            )
        assert authority["r_lifecycle_state"] == lifecycle
        assert (
            authority["calibration_development_run_authorized"]
            is calibration_allowed
        )
        assert authority["e7_learning_curve_run_authorized"] is e7_allowed
        assert authority["r_outputs_ready_for_staging"] is staging_ready

    for forbidden_path in (
        mcal.DEFAULT_PATCH_LOCK_PATH,
        mcal._temporary_path(mcal.DEFAULT_PATCH_LOCK_PATH),
        mcal.LOCKER_GUARD_PATH,
        Path(mcal.mze.OUTCOME_ACCESS_LOG),
        Path(mcal.mze.E0_M_PATHS[0]),
    ):
        forbidden = _prepare_parent(tmp_path, forbidden_path)
        forbidden.write_bytes(b"forbidden")
        with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
            patch.load_effective_final_calibration_publication_guard_patch_authority(
                verify_remote=False, repo_root=tmp_path
            )
        forbidden.unlink()
        restored = (
            patch.load_effective_final_calibration_publication_guard_patch_authority(
                verify_remote=False, repo_root=tmp_path
            )
        )
        assert restored["status"] == "effective"

    drifted_companions = []
    for section, field, value in (
        ("script", "role", "foreign_script"),
        ("inputs", "sha256", "0" * 64),
        ("outputs", "sha256", "9" * 64),
    ):
        drifted = json.loads(patch._canonical_json_bytes(exact_companion))
        if section == "script":
            drifted[section][field] = value
        else:
            drifted[section][0][field] = value
        drifted_companions.append(drifted)
    marker_drift = json.loads(patch._canonical_json_bytes(exact_companion))
    marker_drift["manifest_written_last"] = False
    drifted_companions.append(marker_drift)
    for drifted in drifted_companions:
        manifest.write_bytes(patch._canonical_json_bytes(drifted))
        with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
            patch.load_effective_final_calibration_publication_guard_patch_authority(
                verify_remote=False, repo_root=tmp_path
            )
    manifest.write_text(json.dumps(exact_companion, indent=2), encoding="utf-8")
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch.load_effective_final_calibration_publication_guard_patch_authority(
            verify_remote=False, repo_root=tmp_path
        )


def test_exact_four_superseded_runner_paths_adopt_mcalp() -> None:
    for path in EXPECTED_SUPERSEDED:
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "closure_final_calibration_publication_guard_patch" in text
    assert set(patch.H_MCAL_SUPERSEDED_PATHS) == EXPECTED_SUPERSEDED
    assert len(patch.H_MCAL_PRESERVED_PATHS) == 8
    assert not set(patch.H_MCAL_PRESERVED_PATHS) & EXPECTED_SUPERSEDED
    validator_source = inspect.getsource(patch._require_exact_output_group)
    assert "manifest-last order" not in validator_source
    assert "st_mtime_ns <=" not in validator_source
    assert "output changed during validation" in validator_source


def test_cli_modes_are_closed_and_mutually_exclusive() -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    assert locker.parse_args(["--execute-lock"]).execute_lock is True
    assert locker.parse_args(["--check-effective"]).check_effective is True
    for argv in (
        [],
        ["--check-only", "--execute-lock"],
        ["--execute-lock", "--check-effective"],
        ["--unknown"],
    ):
        with pytest.raises(SystemExit):
            locker.parse_args(argv)


def test_check_only_runs_schema_before_remote_prelock_and_is_nonwriting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        patch,
        "preflight_final_calibration_publication_guard_patch_schema",
        lambda: events.append("schema") or {"gate": "E0-MCALP"},
    )
    monkeypatch.setattr(
        patch,
        "collect_final_calibration_publication_guard_patch_prelock_state",
        lambda *, verify_remote: events.append(f"prelock:{verify_remote}")
        or {"h_patch": {"component_count": 9}},
    )
    result = locker.check_only()
    assert events == ["schema", "prelock:True"]
    assert result["status"] == "ready_to_lock"
    assert result["gate"] == "E0-MCALP"
    assert result["component_count"] == 9
    assert all(
        result[key] is False
        for key in (
            "writes_performed",
            "verification_commands_run",
            "calibration_run",
            "learning_curve_run",
            "dvc_commands_run",
            "scientific_network_commands_run",
            "future_outcomes_accessed",
        )
    )


def test_focused_suite_is_exact_48_and_excludes_science_dvc_and_outcomes() -> None:
    assert patch.FOCUSED_TEST_COUNT == 48
    assert locker._parse_focused_summary("48 passed in 1.00s\n", "") == {
        "test_count": 48,
        "skipped_count": 0,
        "deselected_count": 0,
    }
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        locker._parse_focused_summary("48 passed, 1 warning in 1.00s\n", "")
    command_text = "\n".join(
        " ".join(command)
        for command in (
            patch.TYPE_CHECK_COMMAND,
            patch.FOCUSED_TEST_COMMAND,
            patch.POETRY_CHECK_COMMAND,
            patch.PUBLICATION_GUARD_COMMAND,
            patch.DIFF_CHECK_COMMAND,
        )
    ).lower()
    assert "dvc" not in command_text
    assert "outcome" not in command_text
    assert "src/experiments/calibrate_closure_final_models.py" not in command_text
    assert "src/experiments/run_closure_anfis_learning_curve.py" not in command_text


def test_effective_loaders_fail_closed_when_p_mcalp_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch.load_effective_final_calibration_publication_guard_patch_authority(
            repo_root=tmp_path
        )
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch.require_final_calibration_authority(repo_root=tmp_path)
    namespace = patch.require_final_calibration_run_namespace(
        runner="calibration", repo_root=tmp_path
    )
    assert namespace["r_lifecycle_state"] == "ready_for_calibration_bundle"
    assert namespace["r_output_present_count"] == 0
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch.require_final_calibration_run_namespace(runner="e7", repo_root=tmp_path)

    partial = _prepare_parent(tmp_path, mcal.CALIBRATION_OUTPUT_PATHS[0])
    partial.write_bytes(b"partial")
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch.require_final_calibration_run_namespace(
            runner="calibration", repo_root=tmp_path
        )
    partial.unlink()

    for occupied_path in (
        mcal._temporary_path(mcal.CALIBRATION_OUTPUT_PATHS[0]),
        mcal.CALIBRATION_GUARD_PATH,
        patch.LOCKER_GUARD_PATH,
    ):
        occupied = _prepare_parent(tmp_path, occupied_path)
        occupied.write_bytes(b"occupied")
        with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
            patch.require_final_calibration_run_namespace(
                runner="calibration", repo_root=tmp_path
            )
        occupied.unlink()

    for counts, lifecycle, ready_runner in (
        ((0, 0), "ready_for_calibration_bundle", "calibration"),
        (
            (6, 0),
            "calibration_completed_unpublished_ready_for_e7_bundle",
            "e7",
        ),
    ):
        with monkeypatch.context() as lifecycle_patch:
            lifecycle_patch.setattr(
                patch,
                "_require_exact_output_group",
                lambda paths, *, manifest_path, repo_root, context, c=counts: (
                    c[0] if context == "calibration" else c[1]
                ),
            )
            ready = patch.require_final_calibration_run_namespace(
                runner=ready_runner, repo_root=tmp_path
            )
            assert ready["r_lifecycle_state"] == lifecycle
            assert ready["r_output_present_count"] == sum(counts)

    with monkeypatch.context() as complete_patch:
        complete_patch.setattr(
            patch,
            "_require_exact_output_group",
            lambda paths, *, manifest_path, repo_root, context: (
                6 if context == "calibration" else 2
            ),
        )
        complete = patch._validate_effective_namespace(repo_root=tmp_path)
        assert complete["r_lifecycle_state"] == "both_bundles_completed_unpublished"
        assert complete["r_output_present_count"] == 8
        for runner_name in ("calibration", "e7"):
            with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
                patch.require_final_calibration_run_namespace(
                    runner=runner_name, repo_root=tmp_path
                )

    with monkeypatch.context() as out_of_order_patch:
        out_of_order_patch.setattr(
            patch,
            "_require_exact_output_group",
            lambda paths, *, manifest_path, repo_root, context: (
                0 if context == "calibration" else 2
            ),
        )
        with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
            patch._validate_effective_namespace(repo_root=tmp_path)


def test_publisher_success_uses_one_0644_single_link_owned_inode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relative = Path("reports/guard/item.json")
    target = _prepare_parent(tmp_path, relative)
    owner = patch._publish_bytes_no_clobber(relative, b"owned\n", repo_root=tmp_path)
    metadata = target.stat()
    assert target.read_bytes() == b"owned\n"
    assert stat.S_IMODE(metadata.st_mode) == 0o644
    assert metadata.st_nlink == 1
    assert (metadata.st_dev, metadata.st_ino) == (owner.device, owner.inode)
    assert not Path(f"{target.as_posix()}.tmp").exists()
    patch._rollback_owned_output(owner)
    assert not target.exists()

    close_root = tmp_path / "close-failure"
    close_root.mkdir()
    close_target = _prepare_parent(close_root, relative)
    real_close = os.close
    failed_descriptors: list[int] = []

    def fail_first_regular_close(descriptor: int) -> None:
        metadata = os.fstat(descriptor)
        if stat.S_ISREG(metadata.st_mode) and not failed_descriptors:
            failed_descriptors.append(descriptor)
            raise OSError("interposed close failure")
        real_close(descriptor)

    with monkeypatch.context() as close_patch:
        close_patch.setattr(patch.os, "close", fail_first_regular_close)
        with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
            patch._publish_bytes_no_clobber(
                relative, b"owned", repo_root=close_root
            )
    assert failed_descriptors
    with pytest.raises(OSError):
        os.fstat(failed_descriptors[0])
    assert not close_target.exists()
    assert not Path(f"{close_target.as_posix()}.tmp").exists()

    payload = _synthetic_p_payload()
    publish_root = tmp_path / "bundle-success"
    publish_root.mkdir()
    with monkeypatch.context() as publish_patch:
        _install_synthetic_publisher(publish_patch)
        observed_payload, companion = (
            patch.publish_final_calibration_publication_guard_patch_lock_bundle(
                payload, repo_root=publish_root
            )
        )
    assert observed_payload == payload
    assert companion["manifest_written_last"] is True
    assert (
        publish_root / patch.DEFAULT_PATCH_LOCK_PATH
    ).read_bytes() == patch._canonical_json_bytes(payload)
    assert (
        publish_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    ).read_bytes() == patch._canonical_json_bytes(companion)

    swap_root = tmp_path / "bundle-swap"
    swap_root.mkdir()
    with monkeypatch.context() as swap_patch:
        _install_synthetic_publisher(swap_patch)
        validate_owned = patch._validate_owned_output_bytes

        def replace_lock_during_joint_checkpoint(
            output: patch._OwnedOutput,
            expected: bytes,
            *,
            repo_root: Path,
            context: str,
        ) -> os.stat_result:
            metadata = validate_owned(
                output, expected, repo_root=repo_root, context=context
            )
            if (
                context == "joint ownership transfer pass 2"
                and output.path == patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
            ):
                foreign = repo_root / patch.DEFAULT_PATCH_LOCK_PATH
                foreign.unlink()
                foreign.write_bytes(b"foreign")
            return metadata

        swap_patch.setattr(
            patch, "_validate_owned_output_bytes", replace_lock_during_joint_checkpoint
        )
        with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
            patch.publish_final_calibration_publication_guard_patch_lock_bundle(
                payload, repo_root=swap_root
            )
    assert (swap_root / patch.DEFAULT_PATCH_LOCK_PATH).read_bytes() == b"foreign"
    assert not (swap_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()

    committed_root = tmp_path / "bundle-committed-close-failure"
    committed_root.mkdir()
    with monkeypatch.context() as committed_patch:
        _install_synthetic_publisher(committed_patch)
        committed_patch.setattr(
            patch,
            "_close_owned_output",
            lambda output: (_ for _ in ()).throw(OSError("late close failure")),
        )
        committed_payload, committed_companion = (
            patch.publish_final_calibration_publication_guard_patch_lock_bundle(
                payload, repo_root=committed_root
            )
        )
    assert committed_payload == payload
    assert committed_companion["manifest_written_last"] is True
    assert (committed_root / patch.DEFAULT_PATCH_LOCK_PATH).is_file()
    assert (committed_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).is_file()


def test_existing_final_is_never_clobbered(
    tmp_path: Path,
) -> None:
    relative = Path("reports/guard/item.json")
    target = _prepare_parent(tmp_path, relative)
    target.write_bytes(b"foreign")
    before = target.stat()
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch._publish_bytes_no_clobber(relative, b"owned", repo_root=tmp_path)
    after = target.stat()
    assert target.read_bytes() == b"foreign"
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
    assert not Path(f"{target.as_posix()}.tmp").exists()


def test_final_and_temporary_symlinks_are_preserved_without_following(
    tmp_path: Path,
) -> None:
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"foreign")
    final_relative = Path("final-case/item.json")
    final = _prepare_parent(tmp_path, final_relative)
    final.symlink_to(foreign)
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch._publish_bytes_no_clobber(
            final_relative, b"owned", repo_root=tmp_path
        )
    assert final.is_symlink() and foreign.read_bytes() == b"foreign"

    temp_relative = Path("temp-case/item.json")
    temp_final = _prepare_parent(tmp_path, temp_relative)
    temporary = Path(f"{temp_final.as_posix()}.tmp")
    temporary.symlink_to(foreign)
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch._publish_bytes_no_clobber(
            temp_relative, b"owned", repo_root=tmp_path
        )
    assert temporary.is_symlink() and foreign.read_bytes() == b"foreign"


def test_symlinked_parent_is_rejected_without_outside_write(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "reports").symlink_to(outside, target_is_directory=True)
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch._publish_bytes_no_clobber(
            Path("reports/item.json"), b"owned", repo_root=tmp_path
        )
    assert list(outside.iterdir()) == []


def test_post_link_foreign_replacement_survives_and_owned_temp_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative = Path("reports/guard/item.json")
    target = _prepare_parent(tmp_path, relative)
    real_link = os.link

    def link_then_replace(
        source: str,
        destination: str,
        *,
        src_dir_fd: int,
        dst_dir_fd: int,
        follow_symlinks: bool,
    ) -> None:
        real_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )
        os.unlink(destination, dir_fd=dst_dir_fd)
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o644,
            dir_fd=dst_dir_fd,
        )
        try:
            os.write(descriptor, b"foreign")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    monkeypatch.setattr(patch.os, "link", link_then_replace)
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch._publish_bytes_no_clobber(relative, b"owned", repo_root=tmp_path)
    assert target.read_bytes() == b"foreign"
    assert not Path(f"{target.as_posix()}.tmp").exists()


def test_rollback_removes_exact_owned_output(
    tmp_path: Path,
) -> None:
    relative = Path("reports/guard/item.json")
    target = _prepare_parent(tmp_path, relative)
    owner = patch._publish_bytes_no_clobber(relative, b"owned", repo_root=tmp_path)
    patch._rollback_owned_output(owner)
    assert not target.exists()
    assert owner.closed is True


def test_rollback_preserves_foreign_replacement(
    tmp_path: Path,
) -> None:
    relative = Path("reports/guard/item.json")
    target = _prepare_parent(tmp_path, relative)
    owner = patch._publish_bytes_no_clobber(relative, b"owned", repo_root=tmp_path)
    target.unlink()
    target.write_bytes(b"foreign")
    with pytest.raises(patch.FinalCalibrationPublicationGuardPatchError):
        patch._rollback_owned_output(owner)
    assert target.read_bytes() == b"foreign"
    assert owner.closed is True
