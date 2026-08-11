from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.experiments import (
    closure_final_calibration_candidate_semantics_patch as patch,
)
from src.experiments import (
    lock_closure_final_calibration_candidate_semantics_patch as locker,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_P_MCALP = "6b74440e31d67a6b1a26609347639ae2ba33ec01"
H_MCALP = "59225001a8b1c006213b6a3d963126a6b3f73ccf"
EXPECTED_SUPERSEDED = {
    "src/experiments/calibrate_closure_final_models.py",
    "src/experiments/run_closure_anfis_learning_curve.py",
    "tests/test_calibrate_closure_final_models.py",
    "tests/test_closure_anfis_learning_curve.py",
}
EXPECTED_ADDED = {
    "configs/closure_v1/final_calibration_candidate_semantics_patch_lock.schema.json",
    "docs/closure_v1/E0_M_FINAL_CALIBRATION_CANDIDATE_SEMANTICS_PATCH_1.md",
    "src/experiments/closure_final_calibration_candidate_semantics_patch.py",
    "src/experiments/lock_closure_final_calibration_candidate_semantics_patch.py",
    "tests/test_closure_final_calibration_candidate_semantics_patch.py",
}
EXPECTED_PATCH_PATHS = EXPECTED_SUPERSEDED | EXPECTED_ADDED


def _schema() -> dict[str, Any]:
    value = json.loads((ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text())
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


def _synthetic_lock_payload() -> dict[str, Any]:
    preserved = [
        _artifact_record(f"preserved/component_{index}.py", index)
        for index in range(5)
    ]
    prior_p = [
        _artifact_record(f"prior-p/component_{index}.json", index + 5)
        for index in range(2)
    ]
    current_paths = [
        patch.LOCKER_PATH.as_posix(),
        *(f"current/component_{index}.py" for index in range(1, 9)),
    ]
    current = [
        _artifact_record(path, index + 7)
        for index, path in enumerate(current_paths)
    ]
    historical = [
        {
            **_artifact_record(f"historical/component_{index}.py", index + 16),
            "commit": H_MCALP,
        }
        for index in range(4)
    ]
    return {
        "repository": {"h_patch_head": "a" * 40},
        "verification": {"synthetic": True},
        "p_mcalp_authority": {
            "preserved_components": preserved,
            "p_components": prior_p,
            "historical_inputs": historical,
        },
        "h_patch": {"components": current},
        "scientific_input_inventory": {
            "calibration_required_inputs": [],
            "calibration_required_inputs_sha256": "3" * 64,
            "e7_required_inputs": [],
            "e7_required_inputs_sha256": "4" * 64,
        },
    }


def _install_synthetic_publisher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        patch,
        "_require_publication_verification",
        lambda payload, *, repo_root: None,
    )
    monkeypatch.setattr(
        patch,
        "validate_final_calibration_candidate_semantics_patch_lock_payload",
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
    monkeypatch.setattr(
        patch.mcalp.mcal,
        "_git_head",
        lambda repo_root, ref="HEAD": "a" * 40,
    )
    monkeypatch.setattr(
        patch.mcalp.mcal,
        "_git",
        lambda repo_root, *args: "main\n"
        if args == ("branch", "--show-current")
        else "",
    )
    monkeypatch.setattr(
        patch.mcalp.mcal,
        "_live_remote_main_head",
        lambda repo_root: "a" * 40,
    )

    def synthetic_status(repo_root: Path) -> list[tuple[str, str]]:
        return [
            ("??", path.as_posix())
            for path in (
                patch.DEFAULT_PATCH_LOCK_PATH,
                patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            )
            if (repo_root / path).exists()
        ]

    monkeypatch.setattr(
        patch.mcalp.mcal, "_workspace_status_records", synthetic_status
    )
    monkeypatch.setattr(patch, "_require_prelock_namespace", lambda *, repo_root: None)
    monkeypatch.setattr(
        patch,
        "_require_publication_boundary",
        lambda *, repo_root, owned_guard, outputs_present: None,
    )
    monkeypatch.setattr(
        patch.mcalp.mt,
        "_acquire_publication_guard",
        lambda path, payload, *, repo_root: object(),
    )
    monkeypatch.setattr(
        patch.mcalp.mt,
        "_release_publication_guard",
        lambda guard, *, tolerate_foreign=False: None,
    )


def _write_synthetic_p_bundle(
    root: Path, payload: dict[str, Any]
) -> tuple[Path, Path, dict[str, Any]]:
    lock = _prepare_parent(root, patch.DEFAULT_PATCH_LOCK_PATH)
    lock.write_bytes(patch._canonical_json_bytes(payload))
    lock_record = patch.mcalp.mcal._file_record(
        patch.DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_candidate_semantics_patch_lock",
        repo_root=root,
    )
    companion = patch._expected_companion(payload, lock_record)
    manifest = _prepare_parent(root, patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH)
    manifest.write_bytes(patch._canonical_json_bytes(companion))
    return lock, manifest, companion


def _install_synthetic_loader(
    monkeypatch: pytest.MonkeyPatch,
    *,
    snapshot_state: dict[str, int] | None = None,
) -> None:
    state = {"version": 0} if snapshot_state is None else snapshot_state
    monkeypatch.setattr(
        patch, "_validate_published_lock_payload", lambda payload, *, repo_root: None
    )
    monkeypatch.setattr(
        patch,
        "_validate_p_publication",
        lambda payload, *, verify_remote, repo_root: {
            "h_patch_head": "a" * 40,
            "p_patch_head": "f" * 40,
            "remote_head": "f" * 40,
        },
    )
    monkeypatch.setattr(patch, "_require_static_effective_boundary", lambda *, repo_root: None)
    monkeypatch.setattr(
        patch,
        "_validate_effective_namespace",
        lambda *, repo_root: {
            "calibration_output_present_count": 0,
            "e7_output_present_count": 0,
            "r_output_present_count": 0,
            "r_lifecycle_state": "ready_for_calibration_bundle",
        },
    )
    monkeypatch.setattr(
        patch,
        "_physical_snapshot",
        lambda repo_root, *, scientific_inventory: ({"version": state["version"]},),
    )

    def require_snapshot(
        expected: object,
        *,
        scientific_inventory: object,
        repo_root: Path,
        context: str,
    ) -> None:
        observed = ({"version": state["version"]},)
        if expected != observed:
            raise patch.FinalCalibrationCandidateSemanticsPatchError(
                f"synthetic snapshot changed {context}"
            )

    monkeypatch.setattr(patch, "_require_physical_snapshot", require_snapshot)
    monkeypatch.setattr(
        patch.mcalp.mcal,
        "_git_head",
        lambda repo_root, ref="HEAD": "f" * 40,
    )
    monkeypatch.setattr(
        patch.mcalp.mcal,
        "_git",
        lambda repo_root, *args: "main\n"
        if args == ("branch", "--show-current")
        else "",
    )
    monkeypatch.setattr(
        patch.mcalp.mcal,
        "_live_remote_main_head",
        lambda repo_root: "f" * 40,
    )
    monkeypatch.setattr(
        patch.mcalp.mcal, "_workspace_status_records", lambda repo_root: []
    )
    monkeypatch.setattr(
        patch.mcalp.mcal,
        "_base_r_mze_authority",
        lambda *, repo_root: {
            "family_final_count": 12,
            "family_records_sha256": "1" * 64,
        },
    )
    monkeypatch.setattr(
        patch.mcalp.mcal, "_historical_e7_blockers", lambda *, repo_root: []
    )
    monkeypatch.setattr(
        patch,
        "_effective_authority_binding_sha256",
        lambda **kwargs: "2" * 64,
    )


def test_h_p_r_topology_and_published_bases_are_exact() -> None:
    assert patch.PATCH_GATE == "E0-MCALC"
    assert patch.BASE_P_MCALP_COMMIT == BASE_P_MCALP
    assert patch.H_MCALP_COMMIT == H_MCALP
    assert set(patch.PATCH_PATHS) == EXPECTED_PATCH_PATHS
    assert patch.FINAL_CALIBRATION_H_STAGED_SCOPE == {
        path: ("M" if path in EXPECTED_SUPERSEDED else "A")
        for path in sorted(EXPECTED_PATCH_PATHS)
    }
    assert len(patch.FINAL_CALIBRATION_P_STAGED_SCOPE) == 2
    assert len(patch.FINAL_CALIBRATION_R_STAGED_SCOPE) == 8
    assert not (
        set(patch.FINAL_CALIBRATION_H_STAGED_SCOPE)
        & set(patch.FINAL_CALIBRATION_P_STAGED_SCOPE)
    )
    assert not (
        set(patch.FINAL_CALIBRATION_P_STAGED_SCOPE)
        & set(patch.FINAL_CALIBRATION_R_STAGED_SCOPE)
    )


def test_h_mcalp_partition_and_prior_p_inputs_are_exact() -> None:
    assert set(patch.H_MCALP_SUPERSEDED_PATHS) == EXPECTED_SUPERSEDED
    assert len(patch.H_MCALP_PRESERVED_PATHS) == 5
    assert not set(patch.H_MCALP_PRESERVED_PATHS) & EXPECTED_SUPERSEDED
    assert len(patch.P_MCALP_PATHS) == 2
    assert set(patch.P_MCALP_PATHS) == {
        "reports/closure_v1/00_protocol/"
        "final_calibration_publication_guard_patch_lock.json",
        "reports/closure_v1/00_protocol/"
        "final_calibration_publication_guard_patch_lock_manifest.json",
    }


def test_consumed_failure_is_clean_non_retryable_and_documented() -> None:
    assert patch.FAILED_ATTEMPT == {
        "attempted_gate": "E0-MCALP",
        "status": "failed_closed_no_outputs",
        "phase": "development_input_validation",
        "failure_code": "raw_score_candidate_empty_sentinel_rejected",
        "authorization_consumed": True,
        "retry_authorized": False,
        "final_output_count": 0,
        "temporary_output_count": 0,
        "active_guard_count": 0,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
        "holdout_rows_opened": False,
        "post_2021_rows_opened": False,
        "side_effect_count": 0,
    }
    text = (
        ROOT
        / "docs/closure_v1/E0_M_FINAL_CALIBRATION_CANDIDATE_SEMANTICS_PATCH_1.md"
    ).read_text()
    for token in (
        "E0-MCALC",
        "4M+5A",
        "16 physical + 4 historical",
        "29,196",
        "candidate: string, nullable=false",
        "must not be retried",
        "B0",
        "B1",
        "B2",
        "M0",
        "Holdout",
        "post-2021",
        "DVC",
    ):
        assert token in text


def test_candidate_semantics_accept_only_the_producer_mapping() -> None:
    expected = {
        "B0": ("",),
        "B1": ("",),
        "B2": ("logistic_sgd", "hist_gradient_boosting_classifier"),
        "M0": ("mifal_ed_t2_v5_defaults",),
    }
    assert patch.RAW_SCORE_CANDIDATE_VALUES == expected
    for model_id, values in expected.items():
        patch.validate_raw_score_candidate_semantics(model_id, values)
        patch.validate_raw_score_candidate_semantics(model_id, tuple(reversed(values)))


def test_candidate_semantics_reject_every_widened_or_coerced_identity() -> None:
    drifts: tuple[tuple[str, tuple[Any, ...]], ...] = (
        ("B0", ("registered",)),
        ("B1", ("registered",)),
        ("B2", ("",)),
        ("B2", ("logistic_sgd",)),
        (
            "B2",
            ("logistic_sgd", "hist_gradient_boosting_classifier", "foreign"),
        ),
        ("M0", ("",)),
        ("M0", ("foreign",)),
        ("B0", (None,)),
        ("B0", (1,)),
        ("B0", ()),
        ("A0", ("",)),
    )
    for model_id, values in drifts:
        with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
            patch.validate_raw_score_candidate_semantics(model_id, values)


def test_schema_preflight_and_semantic_payload_chain_are_closed() -> None:
    schema = _schema()
    assert schema["properties"]["gate"]["const"] == "E0-MCALC"
    result = patch.preflight_final_calibration_candidate_semantics_patch_schema()
    assert result["gate"] == "E0-MCALC"
    assert result["supported_subset_verified"] is True
    assert result["schema_count"] == 1
    prelock = patch.collect_final_calibration_candidate_semantics_patch_prelock_state(
        verify_remote=False
    )
    payload = patch.build_final_calibration_candidate_semantics_patch_lock_payload(
        prelock, generated_at_utc="2026-08-11T00:00:00+00:00"
    )
    assert (
        patch.validate_final_calibration_candidate_semantics_patch_lock_payload(
            payload, verify_remote=False
        )
        == payload
    )


def test_companion_contract_is_exact_16_physical_4_historical_1_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert patch.EXPECTED_COMPANION_INPUT_COUNT == 16
    assert patch.EXPECTED_HISTORICAL_INPUT_COUNT == 4
    assert patch.EXPECTED_COMPANION_OUTPUT_COUNT == 1
    text = json.dumps(_schema(), sort_keys=True)
    for token in (
        '"physical_input_count": {"const": 16}',
        '"historical_input_count": {"const": 4}',
        '"output_count": {"const": 1}',
        '"manifest_written_last": {"const": true}',
    ):
        assert token in text

    payload = _synthetic_lock_payload()
    lock, manifest, exact_companion = _write_synthetic_p_bundle(tmp_path, payload)
    with monkeypatch.context() as loader_patch:
        _install_synthetic_loader(loader_patch)
        timestamp = 1_800_000_000_000_000_000
        for lock_ns, manifest_ns in (
            (timestamp, timestamp),
            (timestamp + 2_000_000_000, timestamp),
        ):
            os.utime(lock, ns=(lock_ns, lock_ns))
            os.utime(manifest, ns=(manifest_ns, manifest_ns))
            authority = (
                patch.load_effective_final_calibration_candidate_semantics_patch_authority(
                    verify_remote=False, repo_root=tmp_path
                )
            )
            assert authority["status"] == "effective"
            assert authority["r_lifecycle_state"] == "ready_for_calibration_bundle"
            assert authority["calibration_development_run_authorized"] is True
            assert authority["e7_learning_curve_run_authorized"] is False
            assert authority["r_outputs_ready_for_staging"] is False

        drifted_companions: list[dict[str, Any]] = []
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
            with pytest.raises(
                patch.FinalCalibrationCandidateSemanticsPatchError
            ):
                patch.load_effective_final_calibration_candidate_semantics_patch_authority(
                    verify_remote=False, repo_root=tmp_path
                )
        manifest.write_text(json.dumps(exact_companion, indent=2))
        with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
            patch.load_effective_final_calibration_candidate_semantics_patch_authority(
                verify_remote=False, repo_root=tmp_path
            )


def test_exact_four_superseded_runner_paths_adopt_mcalc() -> None:
    for path in EXPECTED_SUPERSEDED:
        text = (ROOT / path).read_text()
        assert "closure_final_calibration_candidate_semantics_patch" in text


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
        "preflight_final_calibration_candidate_semantics_patch_schema",
        lambda: events.append("schema") or {"gate": "E0-MCALC"},
    )
    monkeypatch.setattr(
        patch,
        "collect_final_calibration_candidate_semantics_patch_prelock_state",
        lambda *, verify_remote: events.append(f"prelock:{verify_remote}")
        or {"h_patch": {"component_count": 9}},
    )
    result = locker.check_only()
    assert events == ["schema", "prelock:True"]
    assert result["status"] == "ready_to_lock"
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
    with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
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


def test_effective_loaders_fail_without_p_but_namespace_is_standalone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
        patch.load_effective_final_calibration_candidate_semantics_patch_authority(
            verify_remote=False, repo_root=tmp_path
        )
    with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
        patch.require_final_calibration_authority(
            verify_remote=False, repo_root=tmp_path
        )
    namespace = patch.require_final_calibration_run_namespace(
        runner="calibration", repo_root=tmp_path
    )
    assert namespace["r_lifecycle_state"] == "ready_for_calibration_bundle"
    with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
        patch.require_final_calibration_run_namespace(
            runner="e7", repo_root=tmp_path
        )
    partial = _prepare_parent(tmp_path, patch.R_OUTPUT_PATHS[0])
    partial.write_bytes(b"partial")
    with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
        patch.require_final_calibration_run_namespace(
            runner="calibration", repo_root=tmp_path
        )
    partial.unlink()

    for occupied_path in (
        patch.mcalp.mcal._temporary_path(patch.R_OUTPUT_PATHS[0]),
        patch.mcalp.mcal.CALIBRATION_GUARD_PATH,
        patch.mcalp.mcal.E7_GUARD_PATH,
    ):
        occupied = _prepare_parent(tmp_path, occupied_path)
        occupied.write_bytes(b"occupied")
        with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
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
        for runner in ("calibration", "e7"):
            with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
                patch.require_final_calibration_run_namespace(
                    runner=runner, repo_root=tmp_path
                )

    for calibration_count, e7_count, lifecycle in (
        (6, 0, "calibration_completed_unpublished_ready_for_e7_bundle"),
        (6, 2, "both_bundles_completed_unpublished"),
    ):
        loader_root = tmp_path / f"loader-r-{calibration_count}-{e7_count}"
        loader_root.mkdir()
        _write_synthetic_p_bundle(loader_root, _synthetic_lock_payload())
        expected_paths = [*patch.mcalp.mcal.CALIBRATION_OUTPUT_PATHS]
        if e7_count:
            expected_paths.extend(patch.mcalp.mcal.E7_OUTPUT_PATHS)
        with monkeypatch.context() as lifecycle_loader:
            _install_synthetic_loader(lifecycle_loader)
            lifecycle_loader.setattr(
                patch,
                "_validate_effective_namespace",
                lambda *, repo_root, c=calibration_count, e=e7_count, state=lifecycle: {
                    "calibration_output_present_count": c,
                    "e7_output_present_count": e,
                    "r_output_present_count": c + e,
                    "r_lifecycle_state": state,
                },
            )
            lifecycle_loader.setattr(
                patch.mcalp.mcal,
                "_workspace_status_records",
                lambda repo_root, paths=tuple(expected_paths): [
                    ("??", path.as_posix()) for path in paths
                ],
            )
            authority = (
                patch.load_effective_final_calibration_candidate_semantics_patch_authority(
                    verify_remote=False, repo_root=loader_root
                )
            )
        assert authority["r_lifecycle_state"] == lifecycle
        assert authority["e7_learning_curve_run_authorized"] is (
            e7_count == 0
        )
        assert authority["r_outputs_ready_for_staging"] is (e7_count == 2)

    race_root = tmp_path / "loader-race"
    race_root.mkdir()
    payload = _synthetic_lock_payload()
    _write_synthetic_p_bundle(race_root, payload)
    state = {"version": 0}
    with monkeypatch.context() as race_patch:
        _install_synthetic_loader(race_patch, snapshot_state=state)
        namespace_calls = 0

        def mutate_after_namespace_validation(*, repo_root: Path) -> dict[str, Any]:
            nonlocal namespace_calls
            namespace_calls += 1
            if namespace_calls == 2:
                state["version"] += 1
            return {
                "calibration_output_present_count": 0,
                "e7_output_present_count": 0,
                "r_output_present_count": 0,
                "r_lifecycle_state": "ready_for_calibration_bundle",
            }

        race_patch.setattr(
            patch, "_validate_effective_namespace", mutate_after_namespace_validation
        )
        with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
            patch.load_effective_final_calibration_candidate_semantics_patch_authority(
                verify_remote=False, repo_root=race_root
            )
    assert namespace_calls >= 2


def test_publisher_success_and_existing_final_no_clobber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relative = Path("reports/guard/item.json")
    target = _prepare_parent(tmp_path, relative)
    owner = patch._publish_bytes_no_clobber(relative, b"owned\n", repo_root=tmp_path)
    metadata = target.stat()
    assert target.read_bytes() == b"owned\n"
    assert stat.S_IMODE(metadata.st_mode) == 0o644
    assert metadata.st_nlink == 1
    patch._rollback_owned_output(owner)
    target.write_bytes(b"foreign")
    before = target.stat()
    with pytest.raises(patch.FinalCalibrationError):
        patch._publish_bytes_no_clobber(relative, b"owned", repo_root=tmp_path)
    after = target.stat()
    assert target.read_bytes() == b"foreign"
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)

    payload = _synthetic_lock_payload()
    bundle_root = tmp_path / "bundle-success"
    bundle_root.mkdir()
    validation_calls: list[int] = []
    with monkeypatch.context() as bundle_patch:
        _install_synthetic_publisher(bundle_patch)
        bundle_patch.setattr(
            patch,
            "validate_final_calibration_candidate_semantics_patch_lock_payload",
            lambda value, *, repo_root, verify_remote: validation_calls.append(1)
            or dict(value),
        )
        observed, companion = (
            patch.publish_final_calibration_candidate_semantics_patch_lock_bundle(
                payload, repo_root=bundle_root
            )
        )
    assert observed == payload and len(validation_calls) == 2
    assert companion["manifest_written_last"] is True
    assert (
        bundle_root / patch.DEFAULT_PATCH_LOCK_PATH
    ).read_bytes() == patch._canonical_json_bytes(payload)
    assert (
        bundle_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    ).read_bytes() == patch._canonical_json_bytes(companion)

    immutable_root = tmp_path / "bundle-frozen-input"
    immutable_root.mkdir()
    mutable_payload = _synthetic_lock_payload()
    frozen_expected = json.loads(patch._canonical_json_bytes(mutable_payload))
    mutation_calls = 0
    with monkeypatch.context() as immutable_patch:
        _install_synthetic_publisher(immutable_patch)

        def mutate_caller_after_validation(
            value: Mapping[str, Any], *, repo_root: Path, verify_remote: bool
        ) -> dict[str, Any]:
            nonlocal mutation_calls
            mutation_calls += 1
            if mutation_calls == 1:
                mutable_payload["verification"]["foreign"] = True
            return dict(value)

        immutable_patch.setattr(
            patch,
            "validate_final_calibration_candidate_semantics_patch_lock_payload",
            mutate_caller_after_validation,
        )
        frozen_observed, _ = (
            patch.publish_final_calibration_candidate_semantics_patch_lock_bundle(
                mutable_payload, repo_root=immutable_root
            )
        )
    assert mutation_calls == 2
    assert frozen_observed == frozen_expected
    assert mutable_payload != frozen_expected
    assert (
        immutable_root / patch.DEFAULT_PATCH_LOCK_PATH
    ).read_bytes() == patch._canonical_json_bytes(frozen_expected)

    close_root = tmp_path / "bundle-post-commit-close"
    close_root.mkdir()
    with monkeypatch.context() as close_patch:
        _install_synthetic_publisher(close_patch)
        real_close = patch._close_owned_output

        def close_then_fail(output: patch._OwnedOutput) -> None:
            real_close(output)
            raise OSError("interposed post-commit close failure")

        close_patch.setattr(patch, "_close_owned_output", close_then_fail)
        committed, committed_companion = (
            patch.publish_final_calibration_candidate_semantics_patch_lock_bundle(
                payload, repo_root=close_root
            )
        )
    assert committed == payload
    assert committed_companion["manifest_written_last"] is True
    assert (close_root / patch.DEFAULT_PATCH_LOCK_PATH).is_file()
    assert (close_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).is_file()

    swap_root = tmp_path / "bundle-final-swap"
    swap_root.mkdir()
    swapped = False
    with monkeypatch.context() as swap_patch:
        _install_synthetic_publisher(swap_patch)

        def swap_during_final_snapshot(
            expected: object,
            *,
            scientific_inventory: object,
            repo_root: Path,
            context: str,
        ) -> None:
            nonlocal swapped
            if context == "at final ownership transfer checkpoint" and not swapped:
                swapped = True
                foreign_lock = repo_root / patch.DEFAULT_PATCH_LOCK_PATH
                foreign_lock.unlink()
                foreign_lock.write_bytes(b"foreign")

        swap_patch.setattr(
            patch, "_require_physical_snapshot", swap_during_final_snapshot
        )
        with pytest.raises(patch.FinalCalibrationCandidateSemanticsPatchError):
            patch.publish_final_calibration_candidate_semantics_patch_lock_bundle(
                payload, repo_root=swap_root
            )
    assert swapped is True
    assert (swap_root / patch.DEFAULT_PATCH_LOCK_PATH).read_bytes() == b"foreign"
    assert not (swap_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()


def test_symlinks_and_symlinked_parent_are_rejected_without_following(
    tmp_path: Path,
) -> None:
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"foreign")
    final_relative = Path("final/item.json")
    final = _prepare_parent(tmp_path, final_relative)
    final.symlink_to(foreign)
    with pytest.raises(patch.FinalCalibrationError):
        patch._publish_bytes_no_clobber(
            final_relative, b"owned", repo_root=tmp_path
        )
    temp_relative = Path("temp/item.json")
    temp_final = _prepare_parent(tmp_path, temp_relative)
    temporary = Path(f"{temp_final.as_posix()}.tmp")
    temporary.symlink_to(foreign)
    with pytest.raises(patch.FinalCalibrationError):
        patch._publish_bytes_no_clobber(
            temp_relative, b"owned", repo_root=tmp_path
        )
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(patch.FinalCalibrationError):
        patch._publish_bytes_no_clobber(
            Path("linked/item.json"), b"owned", repo_root=tmp_path
        )
    assert final.is_symlink() and temporary.is_symlink()
    assert foreign.read_bytes() == b"foreign" and list(outside.iterdir()) == []


def test_post_link_foreign_replacement_survives_owned_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    with pytest.raises(patch.FinalCalibrationError):
        patch._publish_bytes_no_clobber(relative, b"owned", repo_root=tmp_path)
    assert target.read_bytes() == b"foreign"
    assert not Path(f"{target.as_posix()}.tmp").exists()


def test_rollback_removes_owned_and_preserves_foreign_replacement(
    tmp_path: Path,
) -> None:
    owned_relative = Path("owned/item.json")
    owned = _prepare_parent(tmp_path, owned_relative)
    owner = patch._publish_bytes_no_clobber(
        owned_relative, b"owned", repo_root=tmp_path
    )
    patch._rollback_owned_output(owner)
    assert not owned.exists() and owner.closed is True

    foreign_relative = Path("foreign-case/item.json")
    foreign = _prepare_parent(tmp_path, foreign_relative)
    foreign_owner = patch._publish_bytes_no_clobber(
        foreign_relative, b"owned", repo_root=tmp_path
    )
    foreign.unlink()
    foreign.write_bytes(b"foreign")
    with pytest.raises(patch.FinalCalibrationError):
        patch._rollback_owned_output(foreign_owner)
    assert foreign.read_bytes() == b"foreign"
    assert foreign_owner.closed is True
