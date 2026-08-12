from __future__ import annotations

import inspect
import json
import os
import stat
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import pytest

from src.experiments import calibrate_closure_final_models as calibration_runner
from src.experiments import (
    closure_final_calibration_platt_parameter_dialect_patch as patch,
)
from src.experiments import (
    lock_closure_final_calibration_platt_parameter_dialect_patch as locker,
)
from src.experiments import run_closure_anfis_learning_curve as e7_runner


ROOT = Path(__file__).resolve().parents[1]
BASE_P_MCALI = "fbbb9ebb8260c43146ce6407d6629c20ce8cf4d9"
H_MCALI = "495ef14b2f110477318276755e7f6fc7d9ad2229"
EXPECTED_SUPERSEDED = {
    "src/experiments/calibrate_closure_final_models.py",
    "src/experiments/run_closure_anfis_learning_curve.py",
    "tests/test_calibrate_closure_final_models.py",
    "tests/test_closure_anfis_learning_curve.py",
}
EXPECTED_ADDED = {
    "configs/closure_v1/final_calibration_platt_parameter_dialect_patch_lock.schema.json",
    "docs/closure_v1/E0_M_FINAL_CALIBRATION_PLATT_PARAMETER_DIALECT_PATCH_1.md",
    "src/experiments/closure_final_calibration_platt_parameter_dialect_patch.py",
    "src/experiments/lock_closure_final_calibration_platt_parameter_dialect_patch.py",
    "tests/test_closure_final_calibration_platt_parameter_dialect_patch.py",
}
EXPECTED_PATCH_PATHS = EXPECTED_SUPERSEDED | EXPECTED_ADDED
CAPABILITY_KEYS = {
    "path",
    "device",
    "inode",
    "mode",
    "nlink",
    "size",
    "mtime_ns",
    "ctime_ns",
    "sha256",
}
EXPECTED_GUARD_CONTRACT: dict[str, Any] = {
    "supported_runners": ["calibration", "e7"],
    "supported_phases": ["active_guard", "post_release"],
    "capability_keys": [
        "path",
        "device",
        "inode",
        "mode",
        "nlink",
        "size",
        "mtime_ns",
        "ctime_ns",
        "sha256",
    ],
    "capability_integer_fields": [
        "device",
        "inode",
        "mode",
        "nlink",
        "size",
        "mtime_ns",
        "ctime_ns",
    ],
    "guard_paths": {
        "calibration": "tmp/closure_v1_e0_mcal/final_calibration.guard",
        "e7": "tmp/closure_v1_e0_mcal/anfis_learning_curve.guard",
    },
    "guard_payload_utf8": "E0-MCAL active light-output transaction\n",
    "guard_payload_bytes": 40,
    "guard_payload_sha256": (
        "31b7ba37195e14da436932e280b6cd388f8de9083f7429358fe0f374ad2724ef"
    ),
    "guard_mode": 384,
    "output_mode": 420,
    "required_nlink": 1,
    "active_guard_output_counts": {"calibration": 6, "e7": 2},
    "active_guard_transitions": {
        "calibration": [
            "ready_for_calibration_bundle",
            "calibration_completed_unpublished_ready_for_e7_bundle",
        ],
        "e7": [
            "calibration_completed_unpublished_ready_for_e7_bundle",
            "both_bundles_completed_unpublished",
        ],
    },
    "post_release_guard_policy": "absent",
    "public_loader_guard_policy": "reject_all",
    "foreign_guard_authorized": False,
    "partial_output_bundle_authorized": False,
    "data_rewrite_performed": False,
}
EXPECTED_PLATT_CONTRACT: dict[str, Any] = {
    "method": "platt_logistic",
    "parameter_keys": ["coefficient", "intercept", "input"],
    "coefficient_type": "exact_finite_json_float",
    "intercept_type": "exact_finite_json_float",
    "input_key": "input",
    "input_type": "exact_json_string",
    "input_value": "raw_probability",
    "missing_parameter_policy": "reject",
    "extra_parameter_policy": "reject",
    "boolean_or_integer_numeric_policy": "reject",
    "nonfinite_numeric_policy": "reject",
    "historical_parser_adaptation": (
        "deep_copy_remove_input_then_validate_without_mutating_caller"
    ),
    "caller_mutation_performed": False,
    "data_rewrite_performed": False,
    "error_prefix": "E0-MCALJ",
}


@pytest.fixture(autouse=True)
def _forbid_real_scientific_payload_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Make every governance node fail if it reaches a scientific reader."""

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("MCALJ governance opened a scientific payload")

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


def _live_capability(root: Path, relative: Path) -> dict[str, Any]:
    target = root / relative
    payload = target.read_bytes()
    metadata = target.stat()
    return {
        "path": relative.as_posix(),
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": metadata.st_nlink,
        "size": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns,
        "ctime_ns": metadata.st_ctime_ns,
        "sha256": patch._sha256_bytes(payload),
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
            "commit": H_MCALI,
        }
        for index in range(4)
    ]
    return {
        "repository": {"h_patch_head": "a" * 40},
        "verification": {"synthetic": True},
        "platt_parameter_dialect_contract": _platt_contract(),
        "p_mcali_authority": {
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


def _guard_contract() -> dict[str, Any]:
    return json.loads(json.dumps(EXPECTED_GUARD_CONTRACT))


def _platt_contract() -> dict[str, Any]:
    return json.loads(json.dumps(EXPECTED_PLATT_CONTRACT))


def _write_synthetic_p_bundle(
    root: Path, payload: dict[str, Any]
) -> tuple[Path, Path, dict[str, Any]]:
    lock = _prepare_parent(root, patch.DEFAULT_PATCH_LOCK_PATH)
    lock.write_bytes(patch._canonical_json_bytes(payload))
    lock_record = patch.mcal._file_record(
        patch.DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_platt_parameter_dialect_patch_lock",
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
        "validate_final_calibration_platt_parameter_dialect_patch_lock_payload",
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
        lambda *, repo_root, owned_guard=None: {
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
            raise patch.FinalCalibrationPlattParameterDialectPatchError(
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
    assert patch.PATCH_GATE == "E0-MCALJ"
    assert patch.BASE_P_MCALI_COMMIT == BASE_P_MCALI
    assert patch.H_MCALI_COMMIT == H_MCALI
    assert patch.H_MCALI_PARENT == "c6dbe43f01e484c7270c6a19f9a69d0b753036c7"
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


def test_h_mcali_partition_and_prior_p_inputs_are_exact() -> None:
    assert set(patch.H_MCALI_SUPERSEDED_PATHS) == EXPECTED_SUPERSEDED
    assert len(patch.H_MCALI_PRESERVED_PATHS) == 5
    assert not set(patch.H_MCALI_PRESERVED_PATHS) & EXPECTED_SUPERSEDED
    assert set(patch.P_MCALI_PATHS) == {
        "reports/closure_v1/00_protocol/"
        "final_calibration_owned_run_guard_revalidation_patch_lock.json",
        "reports/closure_v1/00_protocol/"
        "final_calibration_owned_run_guard_revalidation_patch_lock_manifest.json",
    }
    assert patch.EXPECTED_COMPANION_INPUT_COUNT == 16
    assert patch.EXPECTED_HISTORICAL_INPUT_COUNT == 4
    assert patch.EXPECTED_COMPANION_OUTPUT_COUNT == 1
    authority_source = inspect.getsource(patch._p_mcali_authority)
    for token in (
        "mcali._state_for_h(",
        "mcali._p_mcalh_authority(repo_root=repo_root)",
        "mcali._expected_companion(lock_payload, lock_record)",
        "mcal._git_blob_bytes(",
        "H_MCALI_COMMIT",
        "BASE_P_MCALI_COMMIT",
    ):
        assert token in authority_source
    assert "globals()[" not in authority_source
    git_bound = patch._git_record_at_commit(
        patch.P_MCALI_PATHS[0],
        role="fresh_clone_probe",
        commit=patch.BASE_P_MCALI_COMMIT,
        repo_root=ROOT,
    )
    assert set(git_bound) == {
        "role",
        "path",
        "bytes",
        "sha256",
        "git_oid",
        "git_mode",
    }
    assert not {"device", "inode", "mtime_ns", "ctime_ns"} & set(git_bound)


def test_consumed_failure_is_exact_clean_non_retryable_and_documented() -> None:
    assert patch.FAILED_ATTEMPT == {
        "attempted_gate": "E0-MCALI",
        "status": "failed_closed_rolled_back_no_outputs",
        "phase": "calibration_bundle_active_guard_scientific_output_validation",
        "failure_code": "platt_parameter_input_literal_rejected_by_sealed_two_key_parser",
        "error_message": "E0-MCALII Platt parameters drifted",
        "authorization_consumed": True,
        "retry_authorized": False,
        "scientific_input_reads_performed": True,
        "anfis_inference_slot_count": 10,
        "model_inference_performed": True,
        "calibration_fit_performed": True,
        "bundle_payload_built": True,
        "owned_guard_acquired": True,
        "provisional_output_count": 6,
        "rollback_performed": True,
        "rollback_complete": True,
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
        "E0_M_FINAL_CALIBRATION_PLATT_PARAMETER_DIALECT_PATCH_1.md"
    ).read_text()
    for token in (
        "E0-MCALJ",
        "4M+5A",
        "E0-MCALII Platt parameters drifted",
        "calibration_bundle_active_guard_scientific_output_validation",
        "platt_parameter_input_literal_rejected_by_sealed_two_key_parser",
        "six files provisionally",
        "manifest last",
        "active_guard",
        "retry_authorized=false",
        "raw_probability",
        "exactly three keys",
        "holdout",
        "post-2021",
        "DVC",
    ):
        assert token in text


def test_owned_guard_and_platt_dialects_are_exact_copy_only_and_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = json.loads(
        patch._canonical_json_bytes(patch.OWNED_RUN_GUARD_REVALIDATION_CONTRACT)
    )
    assert contract == EXPECTED_GUARD_CONTRACT
    assert set(contract) == set(EXPECTED_GUARD_CONTRACT)
    assert set(contract["capability_keys"]) == CAPABILITY_KEYS
    assert set(contract["capability_integer_fields"]) == CAPABILITY_KEYS - {
        "path",
        "sha256",
    }
    assert contract["guard_mode"] == 0o600
    assert contract["output_mode"] == 0o644
    assert contract["required_nlink"] == 1
    assert contract["active_guard_output_counts"] == {"calibration": 6, "e7": 2}
    assert contract["public_loader_guard_policy"] == "reject_all"
    assert contract["foreign_guard_authorized"] is False
    assert contract["partial_output_bundle_authorized"] is False
    assert contract["data_rewrite_performed"] is False
    schema = _schema()
    assert schema["$defs"]["ownedRunGuardRevalidationContract"] == {
        "const": EXPECTED_GUARD_CONTRACT
    }
    contract = json.loads(
        patch._canonical_json_bytes(patch.PLATT_PARAMETER_DIALECT_CONTRACT)
    )
    assert contract == EXPECTED_PLATT_CONTRACT
    schema = _schema()
    assert schema["$defs"]["plattParameterDialectContract"] == {
        "const": EXPECTED_PLATT_CONTRACT
    }

    value = {
        "schema_version": "closure_final_calibrator_specs_v1",
        "gate": patch.PATCH_GATE,
        "bloom_calibrators": [
            {
                "model_id": "B1",
                "model_seed": 1729,
                "horizon_months": 1,
                "selected_method": "platt_logistic",
                "refit_spec": {
                    "method": "platt_logistic",
                    "parameters": {
                        "coefficient": 1.25,
                        "intercept": -0.5,
                        "input": "raw_probability",
                    },
                },
            }
        ],
        "split_conformal_q_c": [],
    }
    frozen = json.loads(patch._canonical_json_bytes(value))
    delegated: list[dict[str, Any]] = []

    def predecessor(adapted: Any) -> dict[tuple[str, int, int], Mapping[str, Any]]:
        delegated.append(json.loads(patch._canonical_json_bytes(adapted)))
        record = adapted["bloom_calibrators"][0]
        assert adapted["gate"] == patch.mcali.PATCH_GATE
        assert record["refit_spec"]["parameters"] == {
            "coefficient": 1.25,
            "intercept": -0.5,
        }
        return {("B1", 1729, 1): record}

    with monkeypatch.context() as adapter_patch:
        adapter_patch.setattr(patch.mcali, "_validate_calibrator_specs", predecessor)
        indexed = patch._validate_calibrator_specs(value)
        assert indexed == {("B1", 1729, 1): value["bloom_calibrators"][0]}
    assert value == frozen
    assert len(delegated) == 1

    malformed_parameters: list[Any] = [
        {"coefficient": 1.25, "intercept": -0.5},
        {
            "coefficient": 1.25,
            "intercept": -0.5,
            "input": "probability",
        },
        {
            "coefficient": True,
            "intercept": -0.5,
            "input": "raw_probability",
        },
        {
            "coefficient": 1,
            "intercept": -0.5,
            "input": "raw_probability",
        },
        {
            "coefficient": float("inf"),
            "intercept": -0.5,
            "input": "raw_probability",
        },
        {
            "coefficient": 1.25,
            "intercept": -0.5,
            "input": "raw_probability",
            "extra": False,
        },
    ]
    for malformed in malformed_parameters:
        drift = json.loads(patch._canonical_json_bytes(frozen))
        drift["bloom_calibrators"][0]["refit_spec"]["parameters"] = malformed
        with pytest.raises(
            patch.FinalCalibrationPlattParameterDialectPatchError,
            match=r"^E0-MCALJ",
        ):
            patch._validate_calibrator_specs(drift)

    for historical in (
        "E0-MCAL Platt parameters drifted",
        "E0-MCALI Platt parameters drifted",
        "E0-MCALII Platt parameters drifted",
    ):
        translated = patch._translate_predecessor_error(historical)
        assert translated.startswith("E0-MCALJ ")
        assert not translated.startswith("E0-MCALJJ")


def test_transaction_capabilities_are_immutable_and_identity_exact(
    tmp_path: Path,
) -> None:
    guard = tmp_path / calibration_runner.GUARD_PATH.relative_to(
        calibration_runner.PROJECT_ROOT
    )
    outputs = [tmp_path / path for path in patch.mcal.CALIBRATION_OUTPUT_PATHS]
    transaction = calibration_runner.OrderedBundleTransaction(
        guard_path=guard, repo_root=tmp_path
    )
    proxy_type = type(MappingProxyType({}))
    with transaction:
        guard_capability = transaction.owned_guard_capability()
        assert guard_capability is not None
        assert isinstance(guard_capability, proxy_type)
        assert set(guard_capability) == CAPABILITY_KEYS
        assert guard_capability["path"] == patch.mcal.CALIBRATION_GUARD_PATH.as_posix()
        assert guard_capability["mode"] == 0o600
        assert guard_capability["nlink"] == 1
        assert guard_capability["size"] == len(calibration_runner.GUARD_PAYLOAD)
        assert guard_capability["sha256"] == patch._sha256_bytes(
            calibration_runner.GUARD_PAYLOAD
        )
        mutation_probe: Any = guard_capability
        with pytest.raises(TypeError):
            mutation_probe["inode"] = 0

        for index, output in enumerate(outputs):
            transaction.publish(output, f"payload-{index}\n".encode())
        capabilities = transaction.owned_output_capabilities()
        assert len(capabilities) == 6
        assert [capability["path"] for capability in capabilities] == [
            path.relative_to(tmp_path).as_posix() for path in outputs
        ]
        for capability, output in zip(capabilities, outputs, strict=True):
            assert isinstance(capability, proxy_type)
            assert set(capability) == CAPABILITY_KEYS
            assert capability["mode"] == 0o644
            assert capability["nlink"] == 1
            assert all(
                type(capability[key]) is int
                for key in CAPABILITY_KEYS
                if key not in {"path", "sha256"}
            )
            observed = output.stat()
            assert (capability["device"], capability["inode"]) == (
                observed.st_dev,
                observed.st_ino,
            )
    assert transaction.owned_guard_capability() is None
    assert not guard.exists()
    assert not any(output.exists() for output in outputs)


def test_public_loader_rejects_guards_and_private_api_is_capability_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = _prepare_parent(tmp_path, patch.mcal.CALIBRATION_GUARD_PATH)
    guard.write_bytes(calibration_runner.GUARD_PAYLOAD)
    with pytest.raises(patch.FinalCalibrationError, match="coordination/temporary"):
        patch._validate_effective_namespace(repo_root=tmp_path)
    with monkeypatch.context() as public_patch:

        def public_delegate(
            *, verify_remote: bool, repo_root: Path, owned_guard: object
        ) -> dict[str, Any]:
            del verify_remote
            assert owned_guard is None
            return patch._validate_effective_namespace(
                repo_root=repo_root, owned_guard=owned_guard
            )

        public_patch.setattr(
            patch,
            "_load_effective_final_calibration_platt_parameter_dialect_patch_authority",
            public_delegate,
        )
        with pytest.raises(
            patch.FinalCalibrationError, match="coordination/temporary"
        ):
            patch.load_effective_final_calibration_platt_parameter_dialect_patch_authority(
                verify_remote=False, repo_root=tmp_path
            )

    signature = inspect.signature(
        patch.revalidate_final_calibration_owned_run_publication
    )
    assert tuple(signature.parameters) == (
        "captured",
        "runner",
        "phase",
        "owned_guard",
        "owned_outputs",
        "verify_remote",
        "repo_root",
    )
    source = inspect.getsource(
        patch.revalidate_final_calibration_owned_run_publication
    )
    for token in (
        "active_guard",
        "post_release",
        "calibration",
        "e7",
        "owned_guard",
        "owned_outputs",
        "_validate_owned_guard_capability",
        "_validate_owned_output_capabilities",
        "authority_binding_sha256",
    ):
        assert token in source or token in inspect.getsource(patch)
    assert "path_only" not in source


def test_schema_preflight_and_semantic_payload_chain_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = _schema()
    assert schema["properties"]["gate"]["const"] == "E0-MCALJ"
    result = (
        patch.preflight_final_calibration_platt_parameter_dialect_patch_schema()
    )
    assert result["gate"] == "E0-MCALJ"
    assert result["supported_subset_verified"] is True
    assert result["schema_count"] == 1

    prior_lock_path = patch.mcali.DEFAULT_PATCH_LOCK_PATH
    prior_manifest_path = patch.mcali.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    prior_lock_bytes = (ROOT / prior_lock_path).read_bytes()
    prior_manifest_bytes = (ROOT / prior_manifest_path).read_bytes()
    assert prior_lock_bytes == patch.mcal._git_blob_bytes(
        ROOT, BASE_P_MCALI, prior_lock_path
    )
    assert prior_manifest_bytes == patch.mcal._git_blob_bytes(
        ROOT, BASE_P_MCALI, prior_manifest_path
    )
    prior = json.loads(prior_lock_bytes)
    prior_manifest = json.loads(prior_manifest_bytes)
    assert prior_lock_bytes == patch._canonical_json_bytes(prior)
    assert prior_manifest_bytes == patch._canonical_json_bytes(prior_manifest)
    assert prior_manifest["manifest_written_last"] is True

    prelock = {
        "repository": {
            "base_p_mcali_commit": BASE_P_MCALI,
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
        "p_mcali_authority": {
            "commit": BASE_P_MCALI,
            "lock_payload_sha256": patch._sha256_bytes(prior_lock_bytes),
            "companion_sha256": patch._sha256_bytes(prior_manifest_bytes),
            "manifest_written_last": prior_manifest["manifest_written_last"],
            "sealed_runtime": prior["runtime"],
        },
        "h_patch": {
            "gate": "H-E0-MCALJ",
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
        "owned_run_guard_revalidation_contract": _guard_contract(),
        "platt_parameter_dialect_contract": _platt_contract(),
        "scientific_input_inventory": prior["scientific_input_inventory"],
        "scientific_boundary": prior["scientific_boundary"],
        "model_matrix": prior["model_matrix"],
        "calibration_group_matrix": prior["calibration_group_matrix"],
        "e7_terminal_record": prior["e7_terminal_record"],
        "output_contract": prior["output_contract"],
        "prelock": {
            "git_status_clean": True,
            "base_p_mcali_output_present_count": 2,
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
        patch.build_final_calibration_platt_parameter_dialect_patch_lock_payload(
            prelock, generated_at_utc="2026-08-11T00:00:00+00:00"
        )
    )
    schema_calls: list[str] = []

    def validate_synthetic_schema(value: Any, observed_schema: Any) -> None:
        assert observed_schema == schema
        assert value["gate"] == "E0-MCALJ"
        assert value["owned_run_guard_revalidation_contract"] == (
            EXPECTED_GUARD_CONTRACT
        )
        assert value["platt_parameter_dialect_contract"] == EXPECTED_PLATT_CONTRACT
        schema_calls.append("validated")

    monkeypatch.setattr(patch.mcal, "validate_json_schema", validate_synthetic_schema)
    monkeypatch.setattr(
        patch,
        "collect_final_calibration_platt_parameter_dialect_patch_prelock_state",
        lambda *, verify_remote, repo_root: json.loads(
            patch._canonical_json_bytes(prelock)
        ),
    )
    assert (
        patch.validate_final_calibration_platt_parameter_dialect_patch_lock_payload(
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
                patch.load_effective_final_calibration_platt_parameter_dialect_patch_authority(
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
        with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
            patch.load_effective_final_calibration_platt_parameter_dialect_patch_authority(
                verify_remote=False, repo_root=tmp_path
            )
    manifest.write_text(json.dumps(exact, indent=2))
    with monkeypatch.context() as loader_patch:
        _install_synthetic_loader(loader_patch)
        with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
            patch.load_effective_final_calibration_platt_parameter_dialect_patch_authority(
                verify_remote=False, repo_root=tmp_path
            )


def test_exact_four_superseded_paths_adopt_mcali_and_gate_before_io() -> None:
    assert calibration_runner.calibration is patch
    assert e7_runner.calibration is patch
    for path in EXPECTED_SUPERSEDED:
        text = (ROOT / path).read_text()
        assert "closure_final_calibration_platt_parameter_dialect_patch" in text
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
    for function in (
        calibration_runner.execute_one_shot,
        e7_runner._execute_one_shot_with_pinned_inputs,
    ):
        source = inspect.getsource(function)
        transaction = source.index("OrderedBundleTransaction(")
        active = source.index('phase="active_guard"')
        post_release = source.index('phase="post_release"')
        commit = source.index("transaction.commit(")
        assert transaction < active < post_release < commit
        assert "transaction.owned_guard_capability()" in source
        assert "transaction.owned_output_capabilities()" in source
        assert source.count(
            "revalidate_final_calibration_owned_run_publication("
        ) == 2
        assert "!= authority" in source[:transaction]
        assert "!= authority" not in source[transaction:]
        assert "require_final_calibration_authority(" not in source[transaction:]


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
        "preflight_final_calibration_platt_parameter_dialect_patch_schema",
        "before =",
        "run_final_calibration_platt_parameter_dialect_patch_verification",
        "after =",
        "if before != after:",
        "build_final_calibration_platt_parameter_dialect_patch_lock_payload",
        "validate_final_calibration_platt_parameter_dialect_patch_lock_payload",
        "publish_final_calibration_platt_parameter_dialect_patch_lock_bundle",
    ]
    positions = [source.index(token) for token in ordered]
    assert positions == sorted(positions)


def test_check_only_runs_schema_before_remote_prelock_and_is_nonwriting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        patch,
        "preflight_final_calibration_platt_parameter_dialect_patch_schema",
        lambda: events.append("schema") or {"gate": "E0-MCALJ"},
    )
    monkeypatch.setattr(
        patch,
        "collect_final_calibration_platt_parameter_dialect_patch_prelock_state",
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
    with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
        locker._parse_focused_summary("48 passed, 1 warning in 1.00s\n", "")
    assert patch.FOCUSED_TEST_COMMAND == (
        "poetry",
        "run",
        "pytest",
        "-q",
        "tests/test_calibrate_closure_final_models.py",
        "tests/test_closure_anfis_learning_curve.py",
        "tests/test_closure_final_calibration_platt_parameter_dialect_patch.py",
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
    with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
        patch.load_effective_final_calibration_platt_parameter_dialect_patch_authority(
            verify_remote=False, repo_root=tmp_path
        )
    with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
        patch.require_final_calibration_authority(
            verify_remote=False, repo_root=tmp_path
        )
    namespace = patch.require_final_calibration_run_namespace(
        runner="calibration", repo_root=tmp_path
    )
    assert namespace["r_lifecycle_state"] == "ready_for_calibration_bundle"
    with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
        patch.require_final_calibration_run_namespace(runner="e7", repo_root=tmp_path)
    partial = _prepare_parent(tmp_path, patch.R_OUTPUT_PATHS[0])
    partial.write_bytes(b"partial")
    with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
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
        with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
            patch.require_final_calibration_run_namespace(
                runner="calibration", repo_root=tmp_path
            )
        occupied.unlink()

    capability_root = tmp_path / "capabilities"
    guard_path = _prepare_parent(
        capability_root, patch.mcal.CALIBRATION_GUARD_PATH
    )
    guard_path.write_bytes(calibration_runner.GUARD_PAYLOAD)
    guard_path.chmod(0o600)
    guard_capability = _live_capability(
        capability_root, patch.mcal.CALIBRATION_GUARD_PATH
    )
    assert (
        patch._validate_owned_guard_capability(
            guard_capability, repo_root=capability_root, runner="calibration"
        )
        == patch.mcal.CALIBRATION_GUARD_PATH
    )
    for malformed in (
        {"path": patch.mcal.CALIBRATION_GUARD_PATH.as_posix()},
        {**guard_capability, "inode": True},
        {**guard_capability, "path": patch.mcal.E7_GUARD_PATH.as_posix()},
        {**guard_capability, "mode": 0o644},
    ):
        with pytest.raises(
            patch.FinalCalibrationPlattParameterDialectPatchError
        ):
            patch._validate_owned_guard_capability(
                malformed, repo_root=capability_root, runner="calibration"
            )

    backup = guard_path.with_name("owned.guard.backup")
    guard_path.rename(backup)
    guard_path.write_bytes(calibration_runner.GUARD_PAYLOAD)
    guard_path.chmod(0o600)
    with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
        patch._validate_owned_guard_capability(
            guard_capability, repo_root=capability_root, runner="calibration"
        )

    output_root = tmp_path / "owned-outputs"
    output_capabilities: list[dict[str, Any]] = []
    for index, relative in enumerate(patch.mcal.CALIBRATION_OUTPUT_PATHS):
        output = _prepare_parent(output_root, relative)
        output.write_bytes(f"owned-{index}\n".encode())
        output.chmod(0o644)
        output_capabilities.append(_live_capability(output_root, relative))
    patch._validate_owned_output_capabilities(
        output_capabilities, runner="calibration", repo_root=output_root
    )
    for malformed_outputs in (
        output_capabilities[:-1],
        [*output_capabilities, output_capabilities[-1]],
        [{**output_capabilities[0], "path": "foreign.json"}, *output_capabilities[1:]],
    ):
        with pytest.raises(
            patch.FinalCalibrationPlattParameterDialectPatchError
        ):
            patch._validate_owned_output_capabilities(
                malformed_outputs, runner="calibration", repo_root=output_root
            )
    (output_root / patch.mcal.CALIBRATION_OUTPUT_PATHS[0]).write_bytes(b"drift")
    with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
        patch._validate_owned_output_capabilities(
            output_capabilities, runner="calibration", repo_root=output_root
        )

    def authority(state_name: str, *, binding: str = "sealed") -> dict[str, Any]:
        return {
            **json.loads(
                patch._canonical_json_bytes(
                    patch._LIFECYCLE_AUTHORITY_STATES[state_name]
                )
            ),
            "authority_binding_sha256": binding,
            "immutable_scientific_binding": "science-sealed",
        }

    api_root = tmp_path / "api-active"
    api_guard = _prepare_parent(api_root, patch.mcal.CALIBRATION_GUARD_PATH)
    api_guard.write_bytes(calibration_runner.GUARD_PAYLOAD)
    api_guard.chmod(0o600)
    api_guard_capability = _live_capability(
        api_root, patch.mcal.CALIBRATION_GUARD_PATH
    )
    api_outputs: list[dict[str, Any]] = []
    for index, relative in enumerate(patch.mcal.CALIBRATION_OUTPUT_PATHS):
        target = _prepare_parent(api_root, relative)
        target.write_bytes(f"api-{index}\n".encode())
        target.chmod(0o644)
        api_outputs.append(_live_capability(api_root, relative))
    captured_r0 = authority("ready_for_calibration_bundle")
    current_r6 = authority(
        "calibration_completed_unpublished_ready_for_e7_bundle"
    )
    with monkeypatch.context() as active_patch:
        active_patch.setattr(
            patch,
            "_load_effective_final_calibration_platt_parameter_dialect_patch_authority",
            lambda *, verify_remote, repo_root, owned_guard: current_r6,
        )
        assert patch.revalidate_final_calibration_owned_run_publication(
            captured_r0,
            runner="calibration",
            phase="active_guard",
            owned_guard=api_guard_capability,
            owned_outputs=api_outputs,
            verify_remote=False,
            repo_root=api_root,
        ) == current_r6
        for key, value in (
            ("calibration_output_present_count", False),
            ("calibration_development_run_authorized", 1),
        ):
            malformed_lifecycle = {**captured_r0, key: value}
            with pytest.raises(
                patch.FinalCalibrationPlattParameterDialectPatchError
            ):
                patch.revalidate_final_calibration_owned_run_publication(
                    malformed_lifecycle,
                    runner="calibration",
                    phase="active_guard",
                    owned_guard=api_guard_capability,
                    owned_outputs=api_outputs,
                    verify_remote=False,
                    repo_root=api_root,
                )
        with pytest.raises(
            patch.FinalCalibrationPlattParameterDialectPatchError
        ):
            patch.revalidate_final_calibration_owned_run_publication(
                captured_r0,
                runner="calibration",
                phase="active_guard",
                owned_guard={"path": api_guard_capability["path"]},
                owned_outputs=api_outputs,
                verify_remote=False,
                repo_root=api_root,
            )
    with monkeypatch.context() as lifecycle_patch:
        lifecycle_patch.setattr(
            patch,
            "_load_effective_final_calibration_platt_parameter_dialect_patch_authority",
            lambda *, verify_remote, repo_root, owned_guard: captured_r0,
        )
        with pytest.raises(
            patch.FinalCalibrationPlattParameterDialectPatchError,
            match="lifecycle",
        ):
            patch.revalidate_final_calibration_owned_run_publication(
                captured_r0,
                runner="calibration",
                phase="active_guard",
                owned_guard=api_guard_capability,
                owned_outputs=api_outputs,
                verify_remote=False,
                repo_root=api_root,
            )
    with monkeypatch.context() as binding_patch:
        binding_patch.setattr(
            patch,
            "_load_effective_final_calibration_platt_parameter_dialect_patch_authority",
            lambda *, verify_remote, repo_root, owned_guard: authority(
                "calibration_completed_unpublished_ready_for_e7_bundle",
                binding="drifted-ref-or-science",
            ),
        )
        with pytest.raises(
            patch.FinalCalibrationPlattParameterDialectPatchError,
            match="non-lifecycle authority",
        ):
            patch.revalidate_final_calibration_owned_run_publication(
                captured_r0,
                runner="calibration",
                phase="active_guard",
                owned_guard=api_guard_capability,
                owned_outputs=api_outputs,
                verify_remote=False,
                repo_root=api_root,
            )
    api_guard.unlink()
    with monkeypatch.context() as post_patch:
        post_patch.setattr(
            patch,
            "_load_effective_final_calibration_platt_parameter_dialect_patch_authority",
            lambda *, verify_remote, repo_root, owned_guard: current_r6,
        )
        assert patch.revalidate_final_calibration_owned_run_publication(
            captured_r0,
            runner="calibration",
            phase="post_release",
            owned_guard=None,
            owned_outputs=api_outputs,
            verify_remote=False,
            repo_root=api_root,
        ) == current_r6

    e7_root = tmp_path / "api-e7"
    e7_guard = _prepare_parent(e7_root, patch.mcal.E7_GUARD_PATH)
    e7_guard.write_bytes(calibration_runner.GUARD_PAYLOAD)
    e7_guard.chmod(0o600)
    e7_guard_capability = _live_capability(e7_root, patch.mcal.E7_GUARD_PATH)
    e7_outputs: list[dict[str, Any]] = []
    for index, relative in enumerate(patch.mcal.E7_OUTPUT_PATHS):
        target = _prepare_parent(e7_root, relative)
        target.write_bytes(f"e7-{index}\n".encode())
        target.chmod(0o644)
        e7_outputs.append(_live_capability(e7_root, relative))
    captured_r6 = authority(
        "calibration_completed_unpublished_ready_for_e7_bundle"
    )
    current_r8 = authority("both_bundles_completed_unpublished")
    with monkeypatch.context() as e7_patch:
        e7_patch.setattr(
            patch,
            "_load_effective_final_calibration_platt_parameter_dialect_patch_authority",
            lambda *, verify_remote, repo_root, owned_guard: current_r8,
        )
        assert patch.revalidate_final_calibration_owned_run_publication(
            captured_r6,
            runner="e7",
            phase="active_guard",
            owned_guard=e7_guard_capability,
            owned_outputs=e7_outputs,
            verify_remote=False,
            repo_root=e7_root,
        ) == current_r8

    additional_root = tmp_path / "additional-guard"
    for relative in (patch.mcal.CALIBRATION_GUARD_PATH, patch.mcal.E7_GUARD_PATH):
        target = _prepare_parent(additional_root, relative)
        target.write_bytes(calibration_runner.GUARD_PAYLOAD)
        target.chmod(0o600)
    allowed = _live_capability(additional_root, patch.mcal.CALIBRATION_GUARD_PATH)
    with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
        patch._validate_effective_namespace(
            repo_root=additional_root, owned_guard=allowed
        )
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
                patch.FinalCalibrationPlattParameterDialectPatchError
            ):
                patch.require_final_calibration_run_namespace(
                    runner=runner, repo_root=tmp_path
                )
    loader_source = inspect.getsource(
        patch._load_effective_final_calibration_platt_parameter_dialect_patch_authority
    )
    assert loader_source.count("_require_effective_loading_checkpoint(") == 3
    assert loader_source.count("_parse_canonical_json_with_metadata(") == 6
    checkpoint_source = inspect.getsource(patch._require_effective_loading_checkpoint)
    for token in (
        "_require_repository_checkpoint(",
        "_require_physical_snapshot(",
        "_require_static_effective_boundary(repo_root=repo_root)",
        "_effective_namespace_for_owned_guard(",
    ):
        assert token in checkpoint_source
    boundary_source = inspect.getsource(patch._require_static_effective_boundary)
    for token in (
        "mcal.DEFAULT_PATCH_LOCK_PATH",
        "mcali.mcale.mcalp.LOCKER_GUARD_PATH",
        "mcali.mcale.mcalc.LOCKER_GUARD_PATH",
        "mcali.mcale.mcald.LOCKER_GUARD_PATH",
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

        def mutate_after_namespace(
            *, repo_root: Path, owned_guard: Mapping[str, Any] | None = None
        ) -> dict[str, Any]:
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
        with pytest.raises(patch.FinalCalibrationPlattParameterDialectPatchError):
            patch.load_effective_final_calibration_platt_parameter_dialect_patch_authority(
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
            "validate_final_calibration_platt_parameter_dialect_patch_lock_payload",
            lambda value, *, repo_root, verify_remote: validation_calls.append(1)
            or dict(value),
        )
        observed, companion = (
            patch.publish_final_calibration_platt_parameter_dialect_patch_lock_bundle(
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

    no_clobber_root = tmp_path / "bundle-no-clobber"
    no_clobber_root.mkdir()
    foreign_manifest = _prepare_parent(
        no_clobber_root, patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    )
    foreign_manifest.write_bytes(b"foreign\n")
    with monkeypatch.context() as no_clobber_patch:
        _install_synthetic_publisher(no_clobber_patch)
        no_clobber_patch.setattr(
            patch,
            "_require_repository_checkpoint",
            lambda **kwargs: None,
        )
        with pytest.raises(
            patch.FinalCalibrationPlattParameterDialectPatchError
        ):
            patch.publish_final_calibration_platt_parameter_dialect_patch_lock_bundle(
                payload, repo_root=no_clobber_root
            )
    assert not (no_clobber_root / patch.DEFAULT_PATCH_LOCK_PATH).exists()
    assert foreign_manifest.read_bytes() == b"foreign\n"

    close_root = tmp_path / "bundle-close"
    close_root.mkdir()
    close_calls = 0
    real_close = patch._close_owned_output
    with monkeypatch.context() as close_patch:
        _install_synthetic_publisher(close_patch)

        def close_then_fail(output: patch._OwnedOutput) -> None:
            nonlocal close_calls
            close_calls += 1
            real_close(output)
            raise OSError("simulated post-linearization close failure")

        close_patch.setattr(patch, "_close_owned_output", close_then_fail)
        closed_observed, closed_companion = (
            patch.publish_final_calibration_platt_parameter_dialect_patch_lock_bundle(
                payload, repo_root=close_root
            )
        )
    assert closed_observed == payload and closed_companion["manifest_written_last"]
    assert close_calls == 2
    assert (close_root / patch.DEFAULT_PATCH_LOCK_PATH).is_file()
    assert (close_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).is_file()

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
            "validate_final_calibration_platt_parameter_dialect_patch_lock_payload",
            mutate_after_validation,
        )
        frozen_observed, _ = (
            patch.publish_final_calibration_platt_parameter_dialect_patch_lock_bundle(
                mutable, repo_root=frozen_root
            )
        )
    assert calls == 2
    assert frozen_observed == expected
    assert mutable != expected
    publisher_source = inspect.getsource(
        patch.publish_final_calibration_platt_parameter_dialect_patch_lock_bundle
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
        "mcali._require_owned_identity_set(",
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
