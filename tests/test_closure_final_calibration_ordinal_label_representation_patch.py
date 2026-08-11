from __future__ import annotations

import inspect
import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import pytest

from src.experiments import calibrate_closure_final_models as calibration_runner
from src.experiments import (
    closure_final_calibration_ordinal_label_representation_patch as patch,
)
from src.experiments import (
    lock_closure_final_calibration_ordinal_label_representation_patch as locker,
)
from src.experiments import run_closure_anfis_learning_curve as e7_runner


ROOT = Path(__file__).resolve().parents[1]
BASE_P_MCALF = "11a130809c2ad5d37c100e681d1f7a03c611603d"
H_MCALF = "12099beebe63997403aa086820d1a059498d23e3"
EXPECTED_SUPERSEDED = {
    "src/experiments/calibrate_closure_final_models.py",
    "src/experiments/run_closure_anfis_learning_curve.py",
    "tests/test_calibrate_closure_final_models.py",
    "tests/test_closure_anfis_learning_curve.py",
}
EXPECTED_ADDED = {
    "configs/closure_v1/final_calibration_ordinal_label_representation_patch_lock.schema.json",
    "docs/closure_v1/E0_M_FINAL_CALIBRATION_ORDINAL_LABEL_REPRESENTATION_PATCH_1.md",
    "src/experiments/closure_final_calibration_ordinal_label_representation_patch.py",
    "src/experiments/lock_closure_final_calibration_ordinal_label_representation_patch.py",
    "tests/test_closure_final_calibration_ordinal_label_representation_patch.py",
}
EXPECTED_PATCH_PATHS = EXPECTED_SUPERSEDED | EXPECTED_ADDED
EXPECTED_REPRESENTATION_CONTRACT: dict[str, Any] = {
    "source_column": "target_trophic_state_h",
    "source_arrow_type": "large_string",
    "source_token_order": [
        "oligotrophic",
        "mesotrophic",
        "eutrophic",
        "hypereutrophic",
    ],
    "normalized_column": "ordinal_label",
    "normalized_pandas_dtype": "Int8",
    "ordinal_model_ids": ["B0", "B1", "B2"],
    "ordinal_code_by_token": {
        "oligotrophic": 0,
        "mesotrophic": 1,
        "eutrophic": 2,
        "hypereutrophic": 3,
    },
    "ordinal_values": [0, 1, 2, 3],
    "ordinal_null_policy": "non_null_exact_integer",
    "nonordinal_model_ids": ["M0", "A0", "A1"],
    "nonordinal_value": None,
    "nonordinal_null_policy": "exact_na",
    "rejected_scalar_types": ["bool", "float", "string"],
    "fractional_values_authorized": False,
    "data_rewrite_performed": False,
}


@pytest.fixture(autouse=True)
def _forbid_real_scientific_payload_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Make every governance node fail if it reaches a scientific reader."""

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("MCALG governance opened a scientific payload")

    for owner, name in (
        (patch, "_scientific_input_inventory"),
        (patch.mcal, "_scientific_input_inventory"),
        (patch.mcal, "_read_scientific_payload_bytes_and_metadata"),
        (calibration_runner, "_read_parquet_frame"),
        (calibration_runner, "_read_filtered_target_frame"),
    ):
        monkeypatch.setattr(owner, name, forbidden)


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
            "commit": H_MCALF,
        }
        for index in range(4)
    ]
    return {
        "repository": {"h_patch_head": "a" * 40},
        "verification": {"synthetic": True},
        "p_mcalf_authority": {
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


def _representation_contract() -> dict[str, Any]:
    return json.loads(json.dumps(EXPECTED_REPRESENTATION_CONTRACT))


def _write_synthetic_p_bundle(
    root: Path, payload: dict[str, Any]
) -> tuple[Path, Path, dict[str, Any]]:
    lock = _prepare_parent(root, patch.DEFAULT_PATCH_LOCK_PATH)
    lock.write_bytes(patch._canonical_json_bytes(payload))
    lock_record = patch.mcal._file_record(
        patch.DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_ordinal_label_representation_patch_lock",
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
        "validate_final_calibration_ordinal_label_representation_patch_lock_payload",
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
        patch.mcal,
        "_git_head",
        lambda repo_root, ref="HEAD": "a" * 40,
    )
    monkeypatch.setattr(
        patch.mcal,
        "_git",
        lambda repo_root, *args: "main\n"
        if args == ("branch", "--show-current")
        else "",
    )
    monkeypatch.setattr(
        patch.mcal,
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

    monkeypatch.setattr(patch.mcal, "_workspace_status_records", synthetic_status)
    monkeypatch.setattr(patch, "_require_prelock_namespace", lambda *, repo_root: None)
    monkeypatch.setattr(
        patch,
        "_require_publication_boundary",
        lambda *, repo_root, owned_guard, outputs_present: None,
    )
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
    monkeypatch.setattr(
        patch, "_require_static_effective_boundary", lambda *, repo_root: None
    )
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
            raise patch.FinalCalibrationOrdinalLabelRepresentationPatchError(
                f"synthetic snapshot changed {context}"
            )

    monkeypatch.setattr(patch, "_require_physical_snapshot", require_snapshot)
    monkeypatch.setattr(
        patch.mcal,
        "_git_head",
        lambda repo_root, ref="HEAD": "f" * 40,
    )
    monkeypatch.setattr(
        patch.mcal,
        "_git",
        lambda repo_root, *args: "main\n"
        if args == ("branch", "--show-current")
        else "",
    )
    monkeypatch.setattr(
        patch.mcal,
        "_live_remote_main_head",
        lambda repo_root: "f" * 40,
    )
    monkeypatch.setattr(patch.mcal, "_workspace_status_records", lambda repo_root: [])
    monkeypatch.setattr(
        patch.mcal,
        "_base_r_mze_authority",
        lambda *, repo_root: {
            "family_final_count": 12,
            "family_records_sha256": "1" * 64,
        },
    )
    monkeypatch.setattr(
        patch.mcal, "_historical_e7_blockers", lambda *, repo_root: []
    )
    monkeypatch.setattr(
        patch,
        "_effective_authority_binding_sha256",
        lambda **kwargs: "2" * 64,
    )


def test_h_p_r_topology_and_published_bases_are_exact() -> None:
    assert patch.PATCH_GATE == "E0-MCALG"
    assert patch.BASE_P_MCALF_COMMIT == BASE_P_MCALF
    assert patch.H_MCALF_COMMIT == H_MCALF
    assert patch.H_MCALF_PARENT == "79e799343e06d718797b61e8eee44d4af42bb1ca"
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


def test_h_mcalf_partition_and_prior_p_inputs_are_exact() -> None:
    assert set(patch.H_MCALF_SUPERSEDED_PATHS) == EXPECTED_SUPERSEDED
    assert len(patch.H_MCALF_PRESERVED_PATHS) == 5
    assert not set(patch.H_MCALF_PRESERVED_PATHS) & EXPECTED_SUPERSEDED
    assert set(patch.P_MCALF_PATHS) == {
        "reports/closure_v1/00_protocol/"
        "final_calibration_raw_exclusion_evidence_patch_lock.json",
        "reports/closure_v1/00_protocol/"
        "final_calibration_raw_exclusion_evidence_patch_lock_manifest.json",
    }
    assert patch.EXPECTED_COMPANION_INPUT_COUNT == 16
    assert patch.EXPECTED_HISTORICAL_INPUT_COUNT == 4
    assert patch.EXPECTED_COMPANION_OUTPUT_COUNT == 1
    authority_source = inspect.getsource(patch._p_mcalf_authority)
    for token in (
        "mcalf._state_for_h(",
        "mcalf._p_mcale_authority(repo_root=repo_root)",
        "mcalf._expected_companion(lock_payload, lock_record)",
        "mcal._git_blob_bytes(",
        "H_MCALF_COMMIT",
        "BASE_P_MCALF_COMMIT",
    ):
        assert token in authority_source
    assert "globals()[" not in authority_source


def test_consumed_failure_is_exact_clean_non_retryable_and_documented() -> None:
    assert patch.FAILED_ATTEMPT == {
        "attempted_gate": "E0-MCALF",
        "status": "failed_closed_no_outputs",
        "phase": "normalized_calibration_frame_validation",
        "failure_code": "ordinal_label_nullable_integer_representation_drift",
        "authorization_consumed": True,
        "retry_authorized": False,
        "scientific_input_reads_performed": True,
        "anfis_inference_slot_count": 10,
        "model_inference_performed": True,
        "calibration_fit_performed": False,
        "bundle_payload_built": False,
        "final_output_count": 0,
        "temporary_output_count": 0,
        "active_guard_count": 0,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
        "holdout_rows_opened": False,
        "post_2021_rows_opened": False,
        "filesystem_side_effect_count": 0,
    }
    text = (
        ROOT
        / "docs/closure_v1/"
        "E0_M_FINAL_CALIBRATION_ORDINAL_LABEL_REPRESENTATION_PATCH_1.md"
    ).read_text()
    for token in (
        "E0-MCALG",
        "4M+5A",
        "E0-MCAL ordinal labels must be exact integer classes",
        "normalized_calibration_frame_validation",
        "Int8",
        "float64",
        "pd.NA",
        "retry_authorized=false",
        "holdout",
        "post-2021",
        "DVC",
    ):
        assert token in text


def test_ordinal_label_representation_contract_is_exact_and_schema_closed() -> None:
    contract = json.loads(
        patch._canonical_json_bytes(patch.ORDINAL_LABEL_REPRESENTATION_CONTRACT)
    )
    assert contract == EXPECTED_REPRESENTATION_CONTRACT
    assert set(contract) == {
        "source_column",
        "source_arrow_type",
        "source_token_order",
        "normalized_column",
        "normalized_pandas_dtype",
        "ordinal_model_ids",
        "ordinal_code_by_token",
        "ordinal_values",
        "ordinal_null_policy",
        "nonordinal_model_ids",
        "nonordinal_value",
        "nonordinal_null_policy",
        "rejected_scalar_types",
        "fractional_values_authorized",
        "data_rewrite_performed",
    }
    assert contract["ordinal_code_by_token"] == dict(
        zip(contract["source_token_order"], contract["ordinal_values"], strict=True)
    )
    assert contract["normalized_pandas_dtype"] == "Int8"
    assert contract["ordinal_model_ids"] == ["B0", "B1", "B2"]
    assert contract["nonordinal_model_ids"] == ["M0", "A0", "A1"]
    assert contract["nonordinal_value"] is None
    assert contract["fractional_values_authorized"] is False
    assert contract["data_rewrite_performed"] is False
    schema = _schema()
    definition = schema["$defs"]["ordinalLabelRepresentationContract"]
    assert definition == {"const": EXPECTED_REPRESENTATION_CONTRACT}


def test_runner_constructors_and_concats_preserve_exact_nullable_int8() -> None:
    ordinal = pd.DataFrame({"model_id": ["B0", "B1", "B2"]})
    ordinal["ordinal_label"] = calibration_runner._exact_ordinal_label_array(
        [0, 1, 3], context="governance ordinal"
    )
    nonordinal = pd.DataFrame({"model_id": ["M0", "A0", "A1"]})
    nonordinal["ordinal_label"] = calibration_runner._missing_ordinal_label_array(
        len(nonordinal), context="governance nonordinal"
    )
    calibration_runner._require_ordinal_label_representation(
        ordinal, context="governance ordinal"
    )
    calibration_runner._require_ordinal_label_representation(
        nonordinal, context="governance nonordinal"
    )
    combined = calibration_runner._concat_prediction_frames(
        [ordinal, nonordinal], context="governance mixed"
    )
    assert str(combined["ordinal_label"].dtype) == "Int8"
    ordinal_mask = combined["model_id"].isin(("B0", "B1", "B2"))
    assert combined.loc[ordinal_mask, "ordinal_label"].tolist() == [0, 1, 3]
    assert combined.loc[~ordinal_mask, "ordinal_label"].isna().all()
    calibration_runner._require_ordinal_label_representation(
        combined, context="governance final"
    )
    target_source = inspect.getsource(calibration_runner._target_projection)
    baseline_source = inspect.getsource(calibration_runner._baseline_predictions)
    selection_source = inspect.getsource(
        calibration_runner._anfis_selection_predictions
    )
    inference_source = inspect.getsource(
        calibration_runner._anfis_calibration_predictions
    )
    loader_source = inspect.getsource(calibration_runner._load_final_calibration_inputs)
    for source in (target_source, baseline_source):
        assert "_exact_ordinal_label_array(" in source
    for source in (baseline_source, selection_source, inference_source):
        assert "_missing_ordinal_label_array(" in source
    assert loader_source.count("_concat_prediction_frames(") >= 1
    assert "closure_final_calibration_ordinal_label_representation_patch" in (
        inspect.getsource(calibration_runner)
    )


def test_float_bool_string_fractional_and_applicability_drifts_fail_closed() -> None:
    for value in (1.0, 1.5, True, "1", None, -1, 4):
        with pytest.raises(patch.FinalCalibrationError):
            calibration_runner._exact_ordinal_label_array(
                [value], context="governance drift"
            )
    wrong_frames = [
        pd.DataFrame(
            {
                "model_id": ["B0"],
                "ordinal_label": pd.Series([1.0], dtype="float64"),
            }
        ),
        pd.DataFrame(
            {
                "model_id": ["B0"],
                "ordinal_label": pd.array([pd.NA], dtype="Int8"),
            }
        ),
        pd.DataFrame(
            {
                "model_id": ["M0"],
                "ordinal_label": pd.array([1], dtype="Int8"),
            }
        ),
        pd.DataFrame(
            {
                "model_id": ["B9"],
                "ordinal_label": pd.array([1], dtype="Int8"),
            }
        ),
    ]
    for frame in wrong_frames:
        with pytest.raises(patch.FinalCalibrationError):
            calibration_runner._require_ordinal_label_representation(
                frame, context="governance drift"
            )
    constructor_source = inspect.getsource(
        calibration_runner._exact_ordinal_label_array
    )
    for forbidden in ("to_numeric(", "round(", "astype("):
        assert forbidden not in constructor_source


def test_schema_preflight_and_semantic_payload_chain_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = _schema()
    assert schema["properties"]["gate"]["const"] == "E0-MCALG"
    result = (
        patch.preflight_final_calibration_ordinal_label_representation_patch_schema()
    )
    assert result["gate"] == "E0-MCALG"
    assert result["supported_subset_verified"] is True
    assert result["schema_count"] == 1

    prior_lock_path = patch.mcalf.DEFAULT_PATCH_LOCK_PATH
    prior_manifest_path = patch.mcalf.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    prior_lock_bytes = (ROOT / prior_lock_path).read_bytes()
    prior_manifest_bytes = (ROOT / prior_manifest_path).read_bytes()
    assert prior_lock_bytes == patch.mcal._git_blob_bytes(
        ROOT, BASE_P_MCALF, prior_lock_path
    )
    assert prior_manifest_bytes == patch.mcal._git_blob_bytes(
        ROOT, BASE_P_MCALF, prior_manifest_path
    )
    prior = json.loads(prior_lock_bytes)
    prior_manifest = json.loads(prior_manifest_bytes)
    assert prior_lock_bytes == patch._canonical_json_bytes(prior)
    assert prior_manifest_bytes == patch._canonical_json_bytes(prior_manifest)
    assert prior_manifest["manifest_written_last"] is True

    prelock = {
        "repository": {
            "base_p_mcalf_commit": BASE_P_MCALF,
            "h_patch_head": "a" * 40,
            "branch": "main",
            "remote_head": "a" * 40,
            "scope": {
                "added": 5,
                "modified": 4,
                "deleted": 0,
                "path_count": 9,
                "paths": sorted(EXPECTED_PATCH_PATHS),
            },
        },
        "failed_attempt": dict(patch.FAILED_ATTEMPT),
        "p_mcalf_authority": {
            "commit": BASE_P_MCALF,
            "lock_payload_sha256": patch._sha256_bytes(prior_lock_bytes),
            "companion_sha256": patch._sha256_bytes(prior_manifest_bytes),
            "manifest_written_last": prior_manifest["manifest_written_last"],
            "sealed_runtime": prior["runtime"],
        },
        "h_patch": {
            "gate": "H-E0-MCALG",
            "component_count": 9,
            "added_count": 5,
            "modified_count": 4,
            "components": [
                _artifact_record(path, index)
                for index, path in enumerate(sorted(EXPECTED_PATCH_PATHS))
            ],
            "components_sha256": "1" * 64,
        },
        "runtime": prior["runtime"],
        "ordinal_label_representation_contract": _representation_contract(),
        "scientific_input_inventory": prior["scientific_input_inventory"],
        "scientific_boundary": prior["scientific_boundary"],
        "model_matrix": prior["model_matrix"],
        "calibration_group_matrix": prior["calibration_group_matrix"],
        "e7_terminal_record": prior["e7_terminal_record"],
        "output_contract": prior["output_contract"],
        "prelock": {
            "git_status_clean": True,
            "base_p_mcalf_output_present_count": 2,
            "p_output_present_count": 0,
            "r_output_present_count": 0,
            "temporary_present_count": 0,
            "coordination_present_count": 0,
            "outcome_access_log_absent": True,
            "holdout_rows_opened": False,
            "post_2021_rows_opened": False,
            "dvc_commands_run": False,
            "scientific_writes_performed": False,
            "failed_attempt_retry_authorized": False,
            "companion_contract": {
                "physical_input_count": 16,
                "historical_input_count": 4,
                "output_count": 1,
                "script_path": patch.LOCKER_PATH.as_posix(),
                "manifest_written_last": True,
            },
        },
    }

    science_calls: list[str] = []

    def forbid_science(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        science_calls.append("forbidden")
        raise AssertionError("governance verification opened scientific payloads")

    for owner, name in (
        (patch, "_scientific_input_inventory"),
        (patch.mcal, "_scientific_input_inventory"),
        (patch.mcal, "_read_scientific_payload_bytes_and_metadata"),
        (calibration_runner, "_read_parquet_frame"),
        (calibration_runner, "_read_filtered_target_frame"),
    ):
        monkeypatch.setattr(owner, name, forbid_science)

    payload = (
        patch.build_final_calibration_ordinal_label_representation_patch_lock_payload(
            prelock, generated_at_utc="2026-08-11T00:00:00+00:00"
        )
    )
    schema_calls: list[str] = []

    def validate_synthetic_schema(value: Any, observed_schema: Any) -> None:
        assert observed_schema == schema
        assert value["gate"] == "E0-MCALG"
        assert value["ordinal_label_representation_contract"] == (
            EXPECTED_REPRESENTATION_CONTRACT
        )
        schema_calls.append("validated")

    monkeypatch.setattr(patch.mcal, "validate_json_schema", validate_synthetic_schema)
    monkeypatch.setattr(
        patch,
        "collect_final_calibration_ordinal_label_representation_patch_prelock_state",
        lambda *, verify_remote, repo_root: json.loads(
            patch._canonical_json_bytes(prelock)
        ),
    )
    assert (
        patch.validate_final_calibration_ordinal_label_representation_patch_lock_payload(
            payload, verify_remote=False
        )
        == payload
    )
    assert schema_calls == ["validated"]
    assert science_calls == []


def test_companion_is_exact_16_physical_4_historical_1_output_and_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = json.dumps(_schema(), sort_keys=True)
    for token in (
        '"physical_input_count": {"const": 16}',
        '"historical_input_count": {"const": 4}',
        '"output_count": {"const": 1}',
        '"manifest_written_last": {"const": true}',
    ):
        assert token in text
    payload = _synthetic_lock_payload()
    lock, manifest, exact = _write_synthetic_p_bundle(tmp_path, payload)
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
                patch.load_effective_final_calibration_ordinal_label_representation_patch_authority(
                    verify_remote=False, repo_root=tmp_path
                )
            )
            assert authority["status"] == "effective"
            assert authority["r_lifecycle_state"] == "ready_for_calibration_bundle"
            assert authority["calibration_development_run_authorized"] is True
            assert authority["e7_learning_curve_run_authorized"] is False
    drifted = json.loads(patch._canonical_json_bytes(exact))
    drifted["manifest_written_last"] = False
    manifest.write_bytes(patch._canonical_json_bytes(drifted))
    with monkeypatch.context() as loader_patch:
        _install_synthetic_loader(loader_patch)
        with pytest.raises(patch.FinalCalibrationOrdinalLabelRepresentationPatchError):
            patch.load_effective_final_calibration_ordinal_label_representation_patch_authority(
                verify_remote=False, repo_root=tmp_path
            )
    manifest.write_text(json.dumps(exact, indent=2))
    with monkeypatch.context() as loader_patch:
        _install_synthetic_loader(loader_patch)
        with pytest.raises(patch.FinalCalibrationOrdinalLabelRepresentationPatchError):
            patch.load_effective_final_calibration_ordinal_label_representation_patch_authority(
                verify_remote=False, repo_root=tmp_path
            )


def test_exact_four_superseded_paths_adopt_mcalf_and_gate_before_io() -> None:
    assert calibration_runner.calibration is patch
    assert e7_runner.calibration is patch
    for path in EXPECTED_SUPERSEDED:
        text = (ROOT / path).read_text()
        assert "closure_final_calibration_ordinal_label_representation_patch" in text
    for function, namespace_marker in (
        (
            calibration_runner.execute_one_shot,
            "require_final_calibration_run_namespace",
        ),
        (e7_runner.execute_one_shot, "_require_e7_run_namespace"),
    ):
        source = inspect.getsource(function)
        authority = source.index("require_final_calibration_authority")
        namespace = source.index(namespace_marker)
        assert authority < namespace
        for marker in (
            "_load_final_calibration_inputs",
            "_load_learning_curve_inputs",
            "_PinnedE7Inputs",
            "OrderedBundleTransaction",
        ):
            if marker in source:
                assert namespace < source.index(marker)
    e7_namespace_source = inspect.getsource(e7_runner._require_e7_run_namespace)
    assert "require_final_calibration_run_namespace" in e7_namespace_source
    calibration_source = inspect.getsource(
        calibration_runner._anfis_calibration_predictions
    )
    assert "_anfis_calibration_threshold_prediction_frame" in calibration_source
    assert "anfis_training._selection_prediction_frame" not in calibration_source


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
    source = inspect.getsource(locker.execute_lock)
    ordered = [
        "preflight_final_calibration_ordinal_label_representation_patch_schema",
        "before =",
        "run_final_calibration_ordinal_label_representation_patch_verification",
        "after =",
        "if before != after:",
        "build_final_calibration_ordinal_label_representation_patch_lock_payload",
        "validate_final_calibration_ordinal_label_representation_patch_lock_payload",
        "publish_final_calibration_ordinal_label_representation_patch_lock_bundle",
    ]
    positions = [source.index(token) for token in ordered]
    assert positions == sorted(positions)


def test_check_only_runs_schema_before_remote_prelock_and_is_nonwriting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        patch,
        "preflight_final_calibration_ordinal_label_representation_patch_schema",
        lambda: events.append("schema") or {"gate": "E0-MCALG"},
    )
    monkeypatch.setattr(
        patch,
        "collect_final_calibration_ordinal_label_representation_patch_prelock_state",
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
    with pytest.raises(patch.FinalCalibrationOrdinalLabelRepresentationPatchError):
        locker._parse_focused_summary("48 passed, 1 warning in 1.00s\n", "")
    assert patch.FOCUSED_TEST_COMMAND == (
        "poetry",
        "run",
        "pytest",
        "-q",
        "tests/test_calibrate_closure_final_models.py",
        "tests/test_closure_anfis_learning_curve.py",
        "tests/test_closure_final_calibration_ordinal_label_representation_patch.py",
    )
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


def test_effective_loader_and_run_namespace_close_zero_six_eight_and_races(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(patch.FinalCalibrationOrdinalLabelRepresentationPatchError):
        patch.load_effective_final_calibration_ordinal_label_representation_patch_authority(
            verify_remote=False, repo_root=tmp_path
        )
    with pytest.raises(patch.FinalCalibrationOrdinalLabelRepresentationPatchError):
        patch.require_final_calibration_authority(
            verify_remote=False, repo_root=tmp_path
        )
    namespace = patch.require_final_calibration_run_namespace(
        runner="calibration", repo_root=tmp_path
    )
    assert namespace["r_lifecycle_state"] == "ready_for_calibration_bundle"
    with pytest.raises(patch.FinalCalibrationOrdinalLabelRepresentationPatchError):
        patch.require_final_calibration_run_namespace(runner="e7", repo_root=tmp_path)
    partial = _prepare_parent(tmp_path, patch.R_OUTPUT_PATHS[0])
    partial.write_bytes(b"partial")
    with pytest.raises(patch.FinalCalibrationOrdinalLabelRepresentationPatchError):
        patch.require_final_calibration_run_namespace(
            runner="calibration", repo_root=tmp_path
        )
    partial.unlink()
    for occupied_path in (
        patch.mcal._temporary_path(patch.R_OUTPUT_PATHS[0]),
        patch.mcal.CALIBRATION_GUARD_PATH,
        patch.mcal.E7_GUARD_PATH,
    ):
        occupied = _prepare_parent(tmp_path, occupied_path)
        occupied.write_bytes(b"occupied")
        with pytest.raises(patch.FinalCalibrationOrdinalLabelRepresentationPatchError):
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
    with monkeypatch.context() as completed_patch:
        completed_patch.setattr(
            patch,
            "_require_exact_output_group",
            lambda paths, *, manifest_path, repo_root, context: (
                6 if context == "calibration" else 2
            ),
        )
        completed = patch._validate_effective_namespace(repo_root=tmp_path)
        assert completed == {
            "calibration_output_present_count": 6,
            "e7_output_present_count": 2,
            "r_output_present_count": 8,
            "r_lifecycle_state": "both_bundles_completed_unpublished",
        }
        for runner in ("calibration", "e7"):
            with pytest.raises(
                patch.FinalCalibrationOrdinalLabelRepresentationPatchError
            ):
                patch.require_final_calibration_run_namespace(
                    runner=runner, repo_root=tmp_path
                )
    loader_source = inspect.getsource(
        patch.load_effective_final_calibration_ordinal_label_representation_patch_authority
    )
    assert loader_source.count("_require_effective_loading_checkpoint(") == 3
    assert loader_source.count("_parse_canonical_json_with_metadata(") == 6
    checkpoint_source = inspect.getsource(patch._require_effective_loading_checkpoint)
    for token in (
        "_require_repository_checkpoint(",
        "_require_physical_snapshot(",
        "_require_static_effective_boundary(repo_root=repo_root)",
        "_validate_effective_namespace(repo_root=repo_root)",
    ):
        assert token in checkpoint_source
    boundary_source = inspect.getsource(patch._require_static_effective_boundary)
    for token in (
        "mcal.DEFAULT_PATCH_LOCK_PATH",
        "mcalf.mcale.mcalp.LOCKER_GUARD_PATH",
        "mcalf.mcale.mcalc.LOCKER_GUARD_PATH",
        "mcalf.mcale.mcald.LOCKER_GUARD_PATH",
        "mcal.mze.OUTCOME_ACCESS_LOG",
        "mcal.mze.E0_M_PATHS",
    ):
        assert token in boundary_source
    race_root = tmp_path / "loader-race"
    race_root.mkdir()
    _write_synthetic_p_bundle(race_root, _synthetic_lock_payload())
    state = {"version": 0}
    with monkeypatch.context() as race_patch:
        _install_synthetic_loader(race_patch, snapshot_state=state)
        calls = 0

        def mutate_after_namespace(*, repo_root: Path) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            if calls == 2:
                state["version"] += 1
            return {
                "calibration_output_present_count": 0,
                "e7_output_present_count": 0,
                "r_output_present_count": 0,
                "r_lifecycle_state": "ready_for_calibration_bundle",
            }

        race_patch.setattr(patch, "_validate_effective_namespace", mutate_after_namespace)
        with pytest.raises(patch.FinalCalibrationOrdinalLabelRepresentationPatchError):
            patch.load_effective_final_calibration_ordinal_label_representation_patch_authority(
                verify_remote=False, repo_root=race_root
            )
    assert calls >= 2


def test_full_publisher_is_canonical_manifest_last_frozen_and_no_clobber(
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
            "validate_final_calibration_ordinal_label_representation_patch_lock_payload",
            lambda value, *, repo_root, verify_remote: validation_calls.append(1)
            or dict(value),
        )
        observed, companion = (
            patch.publish_final_calibration_ordinal_label_representation_patch_lock_bundle(
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

    frozen_root = tmp_path / "bundle-frozen"
    frozen_root.mkdir()
    mutable = _synthetic_lock_payload()
    expected = json.loads(patch._canonical_json_bytes(mutable))
    calls = 0
    with monkeypatch.context() as frozen_patch:
        _install_synthetic_publisher(frozen_patch)

        def mutate_after_validation(
            value: Mapping[str, Any], *, repo_root: Path, verify_remote: bool
        ) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            if calls == 1:
                mutable["verification"]["foreign"] = True
            return dict(value)

        frozen_patch.setattr(
            patch,
            "validate_final_calibration_ordinal_label_representation_patch_lock_payload",
            mutate_after_validation,
        )
        frozen_observed, _ = (
            patch.publish_final_calibration_ordinal_label_representation_patch_lock_bundle(
                mutable, repo_root=frozen_root
            )
        )
    assert calls == 2
    assert frozen_observed == expected
    assert mutable != expected
    publisher_source = inspect.getsource(
        patch.publish_final_calibration_ordinal_label_representation_patch_lock_bundle
    )
    assert publisher_source.index("DEFAULT_PATCH_LOCK_PATH, lock_bytes") < (
        publisher_source.index("DEFAULT_PATCH_LOCK_MANIFEST_PATH, companion_bytes")
    )
    for token in (
        "frozen_payload = json.loads(lock_bytes)",
        "for pass_index in (1, 2):",
        "_require_repository_checkpoint(",
        "_require_physical_snapshot(",
        "_require_publication_boundary(",
        "mcalf._require_owned_identity_set(",
        "committed = True",
    ):
        assert token in publisher_source


def test_symlinks_and_post_link_foreign_replacement_fail_without_clobber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"foreign")
    final_relative = Path("final/item.json")
    final = _prepare_parent(tmp_path, final_relative)
    final.symlink_to(foreign)
    with pytest.raises(patch.FinalCalibrationError):
        patch._publish_bytes_no_clobber(final_relative, b"owned", repo_root=tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(patch.FinalCalibrationError):
        patch._publish_bytes_no_clobber(
            Path("linked/item.json"), b"owned", repo_root=tmp_path
        )

    swapped_relative = Path("reports/guard/item.json")
    swapped = _prepare_parent(tmp_path, swapped_relative)
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
        patch._publish_bytes_no_clobber(
            swapped_relative, b"owned", repo_root=tmp_path
        )
    assert swapped.read_bytes() == b"foreign"
    assert not Path(f"{swapped.as_posix()}.tmp").exists()
    assert foreign.read_bytes() == b"foreign" and list(outside.iterdir()) == []


def test_rollback_removes_only_owned_identity_and_preserves_foreign(
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
