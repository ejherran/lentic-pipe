from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from src.experiments import closure_development_runtime_lock as runtime_lock
from src.experiments import closure_development_runtime_patch as runtime_patch
from src.experiments.closure_contract import load_json_mapping
from src.experiments.closure_development_runtime_lock import (
    DEFAULT_LOCK_SCHEMA,
    DevelopmentRuntimeLockError,
    environment_payload,
    recursive_runtime_dependency_paths,
    require_development_fit_authorized,
    validate_development_runtime_lock_payload,
)
from src.experiments.build_closure_expert_state import expert_lineage_audit
from src.experiments.closure_development_guard import DevelopmentScanAudit


SHA = "a" * 64
HEAD = "b" * 40
EXECUTION_HEAD = "d" * 40
PUBLISHED_HEAD = "e" * 40


def _file(path: str, role: str) -> dict[str, Any]:
    return {"path": path, "role": role, "bytes": 1, "sha256": SHA}


def _planned_records() -> list[dict[str, Any]]:
    return [
        {
            "path": f"reports/closure_v1/planned/{index:03d}.json",
            "artifact_class": "lightweight",
            "materialized_at_lock": False,
            "owner_strategy": "git_when_materialized",
            "owner_path": None,
            "bytes": None,
            "sha256": None,
            "pointer_verified": False,
        }
        for index in range(201)
    ]


def _semantic_audit() -> dict[str, Any]:
    return {
        "audit_version": "closure_expert_no_current_state_semantic_audit_v1",
        "schema_allowlist_verified": True,
        "exact_development_locations_verified": True,
        "zero_holdout_overlap": True,
        "zero_unknown_assignment_overlap": True,
        "locked_time_roles_verified": True,
        "unit_interval_values_verified": True,
        "signed_deltas_verified": True,
        "exact_month_delta_recomputation_verified": True,
        "no_post_2021_materialization": True,
        "future_outcomes_accessed": False,
        "rows": 353,
        "locations": 353,
        "minimum_year_month": "2021-12",
        "maximum_year_month": "2021-12",
        "role_counts": {
            "training": 0,
            "model_selection": 0,
            "calibration_threshold": 353,
        },
        "delta_previous_month_missing_count": 353,
        "source_projection": ["source_id", "site_id", "year_month"],
        "output_allowlist": ["source_id", "site_id", "year_month", "time_role"],
    }


def _dvc_artifact(
    path: str,
    completion: str,
    *,
    expert: bool = False,
) -> dict[str, Any]:
    completion_records = [_file(completion, "completion_manifest")]
    if expert:
        completion_records.append(
            _file(
                "reports/closure_v1/01_surface/expert/expert_no_current_state_lineage_audit.json",
                "expert_state_lineage_audit",
            )
        )
    result: dict[str, Any] = {
        "artifact": _file(path, "artifact"),
        "completion_records": completion_records,
        "dvc": {
            "pointer_path": f"{path}.dvc",
            "pointer_bytes": 1,
            "pointer_sha256": SHA,
            "owner_strategy": "explicit_pointer",
            "hash_name": "md5",
            "hash_value": "c" * 32,
            "size": 1,
            "pointer_metadata_verified": True,
            "payload_verified_at_lock": True,
        },
    }
    if expert:
        result["semantic_audit"] = _semantic_audit()
    return result


def _dvc_remote_evidence(
    common_origin: dict[str, Any],
    expert_state: dict[str, Any],
) -> dict[str, Any]:
    targets = []
    for role, artifact in (
        ("common_origin", common_origin),
        ("expert_state", expert_state),
    ):
        pointer = artifact["dvc"]
        targets.append(
            {
                "artifact_role": role,
                "pointer_path": pointer["pointer_path"],
                "pointer_sha256": pointer["pointer_sha256"],
                "hash_name": pointer["hash_name"],
                "hash_value": pointer["hash_value"],
                "size": pointer["size"],
            }
        )
    return {
        "method": "two_targeted_idempotent_pushes_v1",
        "command": [
            "poetry",
            "run",
            "dvc",
            "push",
            "-j",
            "1",
            "-r",
            "gcsremote",
            common_origin["dvc"]["pointer_path"],
            expert_state["dvc"]["pointer_path"],
        ],
        "environment": {"LC_ALL": "C", "LANG": "C", "DVC_NO_ANALYTICS": "1"},
        "remote_name": "gcsremote",
        "remote_url_sha256": SHA,
        "targets": targets,
        "attempts": [
            {
                "attempt": attempt,
                "exit_code": 0,
                "stdout_sha256": SHA,
                "stderr_sha256": SHA,
                "normalized_result": "everything_up_to_date",
            }
            for attempt in (1, 2)
        ],
        "dvc_remote_verified_at_lock": True,
    }


def _command(command: list[str]) -> dict[str, Any]:
    return {
        "command": command,
        "exit_code": 0,
        "stdout_sha256": SHA,
        "stderr_sha256": SHA,
        "passed": True,
    }


def _payload() -> dict[str, Any]:
    common_origin = _dvc_artifact(
        "data/closure_v1/common_origin_manifest.parquet",
        "reports/closure_v1/01_surface/common_origin_manifest.json",
    )
    expert_state = _dvc_artifact(
        "data/closure_v1/development/expert/expert_no_current_state.parquet",
        "reports/closure_v1/01_surface/expert/expert_no_current_state_manifest.json",
        expert=True,
    )
    return {
        "lock_version": "closure_development_runtime_lock_v1",
        "status": "locked",
        "gate": "E0-DL",
        "experiment_id": "closure_v1",
        "created_at_utc": "2026-08-03T18:00:00+00:00",
        "locked_repository": {
            "head": HEAD,
            "branch": "main",
            "worktree_status": "clean",
            "dirty_paths": [],
        },
        "canonical_origin": {
            "remote_name": "origin",
            "identity_algorithm": "git_remote_host_path_v1_sha256_utf8",
            "identity_sha256": (
                "475fdf8ad6839d3d291010ff999b4e4c0f8604a0e8d8a09fcebe5ccb843d1905"
            ),
            "fetch_url_count": 1,
            "push_url_count": 1,
            "fetch_push_identity_equal": True,
        },
        "locked_parent_publication": {
            "head": HEAD,
            "tracking_ref": "origin/main",
            "tracking_oid": HEAD,
            "local_tracking_verified": True,
            "remote_ref": "refs/heads/main",
            "remote_oid": HEAD,
            "remote_verified": True,
        },
        "runtime_contract": {
            "config": _file("configs/closure_v1/development_runtime.yaml", "development_runtime_config"),
            "schema": _file(
                "configs/closure_v1/development_runtime.schema.json",
                "development_runtime_schema",
            ),
            "status": "ready_to_lock",
        },
        "components": [_file("src/experiments/adapter.py", "strict_adapter")],
        "runtime_dependencies": [_file("src/fuzzy/expert.py", "runtime_transitive_dependency")],
        "parents": [_file("reports/closure_v1/00_protocol/protocol_lock.json", "protocol_lock")],
        "restored_development_sources": [
            {**_file("data/panel/panel_monthly_v0.parquet", "panel"), "semantic_decode": False},
            {**_file("data/fuzzy/state_vector_v0.parquet", "expert_anchor"), "semantic_decode": False},
        ],
        "common_origin": common_origin,
        "expert_state": expert_state,
        "planned_artifacts": {
            "count": 201,
            "sha256": "833fe57a573db135357a596949728fd0b6a436997ece0ba2c5555b815a42672c",
            "records": _planned_records(),
        },
        "environment": {
            "python_version": "3.12.0",
            "python_implementation": "CPython",
            "python_executable_name": "python",
            "platform": "Linux-test",
            "machine": "x86_64",
            "device": "cpu",
            "cublas_workspace_config": None,
            "cpu_execution_policy": {
                "device": "cpu",
                "torch_num_threads": 1,
                "torch_num_interop_threads": 1,
                "blas_thread_environment_control": "not_locked_by_e0_dl_v1",
                "bitwise_reproducibility_claim": (
                    "forbidden_across_processes_or_blas_backends"
                ),
                "torch_num_threads_observed": 1,
                "torch_num_interop_threads_observed": 1,
            },
            "packages": [{"name": "numpy", "version": "2.0.0"}],
        },
        "dvc_remote_verification": _dvc_remote_evidence(common_origin, expert_state),
        "verification": {
            "full_type_check": _command(["poetry", "run", "ty", "check"]),
            "focused_tests": _command(["poetry", "run", "pytest", "tests/test_adapter.py", "-q"]),
        },
        "audits": {
            "common_origin_validated": True,
            "expert_state_validated": True,
            "expert_state_semantic_audit_verified": True,
            "zero_holdout_overlap": True,
            "no_post_2021_materialization": True,
            "restored_source_hashes_verified": True,
            "component_hashes_verified": True,
            "recursive_dependency_hashes_verified": True,
            "planned_artifact_paths_verified": True,
            "prelock_dvc_ownership_verified": True,
            "dvc_remote_verified_at_lock": True,
            "canonical_origin_identity_verified": True,
            "locked_parent_published_at_lock": True,
            "environment_locked": True,
        },
        "authorizations": {
            "development_fit_authorized": True,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
        },
        "seals": {
            "future_outcomes_accessed": False,
            "post_2021_outcome_semantic_decode": False,
            "lock_generation_semantically_audits_expert_state_rows": True,
            "lock_generation_reads_scientific_outcome_rows": False,
            "lock_generation_reads_post_2021_outcomes": False,
            "does_not_replace_e0_m_model_lock": True,
            "external_lock_bundle_committed_before_fit": True,
        },
    }


def _patch_lock_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    payload: dict[str, Any],
    require_physical_artifacts: bool,
    component_record: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Isolate loader orchestration while preserving fail-closed comparisons."""
    logical_lock = Path("reports/closure_v1/00_protocol/test_runtime_lock.json")
    physical_lock = tmp_path / "development_runtime_lock.json"
    physical_lock.write_bytes(b"locked")
    runtime = {"implementation_lock": {}}
    calls: dict[str, Any] = {"ancestors": []}
    real_resolve = runtime_lock._resolve_repo_path
    real_canonical = runtime_lock._canonical_repo_path

    def resolve(path: str | Path) -> Path:
        if Path(path) == logical_lock:
            return physical_lock
        return real_resolve(path)

    def load_json(path: str | Path) -> dict[str, Any]:
        if Path(path) == logical_lock:
            return payload
        return {}

    def canonical(path: str | Path) -> str:
        if Path(path) == logical_lock:
            return logical_lock.as_posix()
        return real_canonical(path)

    def exact_records(
        observed: Any,
        expected: Any,
        *,
        context: str,
    ) -> None:
        if list(observed) != list(expected):
            raise DevelopmentRuntimeLockError(f"{context} record drifted")

    def prelock(
        runtime_payload: Any,
        schema_payload: Any,
        *,
        require_physical_artifacts: bool,
    ) -> dict[str, Any]:
        del runtime_payload, schema_payload
        calls["prelock_physical"] = require_physical_artifacts
        return {}

    def published(
        path: Path,
        *,
        verify_remote: bool,
    ) -> tuple[str, str, str, str, str | None]:
        assert path == logical_lock
        calls["verify_remote"] = verify_remote
        return (
            logical_lock.as_posix(),
            EXECUTION_HEAD,
            "origin/main",
            PUBLISHED_HEAD,
            PUBLISHED_HEAD if verify_remote else None,
        )

    def ancestor(ancestor: str, descendant: str) -> None:
        calls["ancestors"].append((ancestor, descendant))

    def record(path: str | Path, *, role: str) -> dict[str, Any]:
        if role == "development_runtime_config":
            return payload["runtime_contract"]["config"]
        if role == "development_runtime_schema":
            return payload["runtime_contract"]["schema"]
        raise AssertionError(f"unexpected file_record role: {role}")

    def common(
        runtime_payload: Any,
        *,
        require_physical_artifact: bool,
    ) -> dict[str, Any]:
        del runtime_payload
        assert require_physical_artifact is require_physical_artifacts
        return payload["common_origin"]

    def expert(
        runtime_payload: Any,
        *,
        runtime_config: Path,
        runtime_schema: Path,
        require_physical_artifact: bool,
    ) -> dict[str, Any]:
        del runtime_payload, runtime_config, runtime_schema
        assert require_physical_artifact is require_physical_artifacts
        return payload["expert_state"]

    monkeypatch.setattr(runtime_lock, "_resolve_repo_path", resolve)
    monkeypatch.setattr(runtime_lock, "_canonical_repo_path", canonical)
    monkeypatch.setattr(runtime_lock, "load_json_mapping", load_json)
    monkeypatch.setattr(runtime_lock, "load_yaml_mapping", lambda _: runtime)
    monkeypatch.setattr(
        runtime_lock,
        "canonical_origin_identity",
        lambda _: payload["canonical_origin"],
    )
    monkeypatch.setattr(runtime_lock, "validate_development_runtime_lock_payload", lambda *args: None)
    monkeypatch.setattr(runtime_lock, "validate_json_schema", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_lock, "_runtime_paths_match_contract", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_lock, "_validate_runtime_prelock_contract", prelock)
    monkeypatch.setattr(runtime_lock, "_require_lock_published", published)
    monkeypatch.setattr(runtime_lock, "_require_ancestor", ancestor)
    monkeypatch.setattr(runtime_lock, "file_record", record)
    monkeypatch.setattr(runtime_lock, "_require_tracked_records_committed_at_head", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_lock, "_require_records_committed_at_head", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runtime_lock,
        "component_records",
        lambda _: [component_record or payload["components"][0]],
    )
    monkeypatch.setattr(runtime_lock, "runtime_dependency_records", lambda _: payload["runtime_dependencies"])
    monkeypatch.setattr(runtime_lock, "_require_exact_record_set", exact_records)
    monkeypatch.setattr(runtime_lock, "restored_development_source_records", lambda _: payload["restored_development_sources"])
    monkeypatch.setattr(runtime_lock, "_validate_restored_source_lock_metadata", lambda observed, runtime_payload: list(observed))
    monkeypatch.setattr(runtime_lock, "common_origin_lock_record", common)
    monkeypatch.setattr(runtime_lock, "expert_state_lock_record", expert)
    monkeypatch.setattr(
        runtime_lock,
        "validate_dvc_remote_verification_evidence",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(runtime_lock, "_materialized_artifact_git_records", lambda *args, **kwargs: [])
    monkeypatch.setattr(runtime_lock, "parent_records", lambda *args, **kwargs: payload["parents"])
    monkeypatch.setattr(runtime_lock, "_validate_parent_lock_metadata", lambda observed, *args, **kwargs: list(observed))
    monkeypatch.setattr(runtime_lock, "planned_artifact_records", lambda *args, **kwargs: payload["planned_artifacts"])
    monkeypatch.setattr(
        runtime_lock,
        "environment_payload",
        lambda *args, **kwargs: payload["environment"],
    )
    monkeypatch.setattr(runtime_lock, "focused_test_command", lambda _: tuple(payload["verification"]["focused_tests"]["command"]))
    monkeypatch.setattr(runtime_lock, "_sha256_file", lambda _: SHA)
    monkeypatch.setattr(runtime_lock, "_git", lambda *args, **kwargs: EXECUTION_HEAD)
    return logical_lock, calls


def test_lock_schema_accepts_closed_external_payload() -> None:
    validate_development_runtime_lock_payload(
        _payload(),
        load_json_mapping(DEFAULT_LOCK_SCHEMA),
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("authorizations", "development_fit_authorized"), False),
        (("authorizations", "evaluation_authorized"), True),
        (("authorizations", "e0_u_authorized"), True),
        (("seals", "future_outcomes_accessed"), True),
        (("seals", "lock_generation_reads_scientific_outcome_rows"), True),
    ],
)
def test_lock_schema_rejects_authorization_or_seal_drift(
    path: tuple[str, str],
    value: bool,
) -> None:
    payload = _payload()
    payload[path[0]][path[1]] = value

    with pytest.raises(DevelopmentRuntimeLockError):
        validate_development_runtime_lock_payload(
            payload,
            load_json_mapping(DEFAULT_LOCK_SCHEMA),
        )


def test_lock_schema_rejects_self_hash_and_unknown_fields() -> None:
    payload = _payload()
    payload["development_runtime_lock_sha256"] = SHA

    with pytest.raises(DevelopmentRuntimeLockError, match="additionalProperties"):
        validate_development_runtime_lock_payload(
            payload,
            load_json_mapping(DEFAULT_LOCK_SCHEMA),
        )


def test_lock_validator_rejects_duplicate_or_unsorted_planned_paths() -> None:
    payload = _payload()
    payload["planned_artifacts"]["records"][1]["path"] = payload["planned_artifacts"][
        "records"
    ][0]["path"]

    with pytest.raises(DevelopmentRuntimeLockError, match="201 unique"):
        validate_development_runtime_lock_payload(
            payload,
            load_json_mapping(DEFAULT_LOCK_SCHEMA),
        )


def test_required_fit_gate_fails_closed_while_external_patch_lock_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = {
        "implementation_lock": {
            "lock_manifest_path": runtime_lock.DEFAULT_LOCK_PATH.as_posix(),
            "lock_schema_path": runtime_lock.DEFAULT_LOCK_SCHEMA.as_posix(),
        }
    }
    monkeypatch.setattr(runtime_lock, "load_yaml_mapping", lambda _: runtime)
    monkeypatch.setattr(
        runtime_lock,
        "configure_torch_cpu_execution_policy",
        lambda runtime: {},
    )
    calls: list[dict[str, Any]] = []

    def absent_patch(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        assert args == ()
        calls.append(kwargs)
        raise runtime_patch.DevelopmentRuntimePatchError("E0-DLP lock is absent")

    monkeypatch.setattr(
        runtime_patch,
        "load_and_validate_development_runtime_patch_lock",
        absent_patch,
    )

    with pytest.raises(
        runtime_patch.DevelopmentRuntimePatchError,
        match="lock is absent",
    ):
        require_development_fit_authorized()
    assert len(calls) == 1


def test_required_fit_gate_returns_only_validated_development_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = {
        "implementation_lock": {
            "lock_manifest_path": "reports/closure_v1/00_protocol/development_runtime_lock.json",
            "lock_schema_path": "configs/closure_v1/development_runtime_lock.schema.json",
        }
    }
    expected = {
        "physical_artifacts_verified": True,
        "publication_verified": True,
        "remote_publication_verified": True,
        "canonical_origin_identity_verified": True,
        "common_origin_output_verified": True,
        "expert_state_output_verified": True,
        "restored_development_sources_verified": True,
        "dvc_remote_verified_at_lock": True,
        "locked_head_is_ancestor": True,
        "locked_parent_published_at_lock": True,
        "fit_authorized": True,
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "published_ref": "origin/main",
    }
    monkeypatch.setattr(runtime_lock, "load_yaml_mapping", lambda _: runtime)
    monkeypatch.setattr(
        runtime_lock,
        "configure_torch_cpu_execution_policy",
        lambda runtime: {},
    )
    calls: list[dict[str, Any]] = []

    def load_patch(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        assert args == ()
        calls.append(kwargs)
        return {}, expected

    monkeypatch.setattr(
        runtime_patch,
        "load_and_validate_development_runtime_patch_lock",
        load_patch,
    )

    assert require_development_fit_authorized(device="cpu") == expected
    assert calls == [
        {
            "base_lock_path": runtime_lock.DEFAULT_LOCK_PATH,
            "base_lock_schema": runtime_lock.DEFAULT_LOCK_SCHEMA,
            "runtime_config": runtime_lock.DEFAULT_RUNTIME_CONFIG,
            "runtime_schema": runtime_lock.DEFAULT_RUNTIME_SCHEMA,
            "device": "cpu",
            "require_published": True,
            "require_physical_artifacts": True,
        }
    ]


def test_required_fit_gate_rejects_validator_summary_that_opens_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = {
        "implementation_lock": {
            "lock_manifest_path": "reports/closure_v1/00_protocol/development_runtime_lock.json",
            "lock_schema_path": "configs/closure_v1/development_runtime_lock.schema.json",
        }
    }
    summary = {
        "physical_artifacts_verified": True,
        "publication_verified": True,
        "remote_publication_verified": True,
        "canonical_origin_identity_verified": True,
        "common_origin_output_verified": True,
        "expert_state_output_verified": True,
        "restored_development_sources_verified": True,
        "dvc_remote_verified_at_lock": True,
        "locked_head_is_ancestor": True,
        "locked_parent_published_at_lock": True,
        "development_fit_authorized": True,
        "fit_authorized": True,
        "evaluation_authorized": True,
        "e0_u_authorized": False,
    }
    monkeypatch.setattr(runtime_lock, "load_yaml_mapping", lambda _: runtime)
    monkeypatch.setattr(
        runtime_lock,
        "configure_torch_cpu_execution_policy",
        lambda runtime: {},
    )
    monkeypatch.setattr(
        runtime_patch,
        "load_and_validate_development_runtime_patch_lock",
        lambda *args, **kwargs: ({}, summary),
    )

    with pytest.raises(DevelopmentRuntimeLockError, match="evaluation/E0-U"):
        require_development_fit_authorized(device="cpu")


def test_source_only_loader_validates_metadata_but_never_authorizes_fit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload()
    lock_path, calls = _patch_lock_loader(
        monkeypatch,
        tmp_path,
        payload=payload,
        require_physical_artifacts=False,
    )

    _, summary = runtime_lock.load_and_validate_development_runtime_lock(
        lock_path,
        Path("configs/closure_v1/development_runtime_lock.schema.json"),
        require_published=True,
        require_physical_artifacts=False,
    )

    assert calls["prelock_physical"] is False
    assert calls["verify_remote"] is False
    assert calls["ancestors"] == [
        (HEAD, EXECUTION_HEAD),
        (HEAD, PUBLISHED_HEAD),
        (PUBLISHED_HEAD, EXECUTION_HEAD),
    ]
    assert summary["metadata_verified"] is True
    assert summary["physical_artifacts_verified"] is False
    assert summary["common_origin_output_verified"] is False
    assert summary["expert_state_output_verified"] is False
    assert summary["payload_development_fit_authorized"] is True
    assert summary["development_fit_authorized"] is False
    assert summary["fit_authorized"] is False
    assert summary["remote_publication_verified"] is False
    assert summary["canonical_origin_identity_verified"] is True
    assert summary["dvc_remote_verified_at_lock"] is True
    assert summary["dvc_remote_verified"] is True


def test_unpublished_validation_cannot_turn_payload_declaration_into_fit_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload()
    lock_path, calls = _patch_lock_loader(
        monkeypatch,
        tmp_path,
        payload=payload,
        require_physical_artifacts=True,
    )

    _, summary = runtime_lock.load_and_validate_development_runtime_lock(
        lock_path,
        Path("configs/closure_v1/development_runtime_lock.schema.json"),
        require_published=False,
        require_physical_artifacts=True,
    )

    assert "verify_remote" not in calls
    assert summary["physical_artifacts_verified"] is True
    assert summary["publication_verified"] is False
    assert summary["payload_development_fit_authorized"] is True
    assert summary["development_fit_authorized"] is False
    assert summary["fit_authorized"] is False


def test_source_only_loader_still_rejects_component_hash_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload()
    drifted = {**payload["components"][0], "sha256": "f" * 64}
    lock_path, _ = _patch_lock_loader(
        monkeypatch,
        tmp_path,
        payload=payload,
        require_physical_artifacts=False,
        component_record=drifted,
    )

    with pytest.raises(DevelopmentRuntimeLockError, match="components record drifted"):
        runtime_lock.load_and_validate_development_runtime_lock(
            lock_path,
            Path("configs/closure_v1/development_runtime_lock.schema.json"),
            require_published=True,
            require_physical_artifacts=False,
        )


def test_loader_rejects_planned_snapshot_record_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload()
    expected_planned = copy.deepcopy(payload["planned_artifacts"])
    payload["planned_artifacts"]["records"][0]["owner_path"] = (
        "reports/closure_v1/planned/000.json"
    )
    lock_path, _ = _patch_lock_loader(
        monkeypatch,
        tmp_path,
        payload=payload,
        require_physical_artifacts=False,
    )
    monkeypatch.setattr(
        runtime_lock,
        "planned_artifact_records",
        lambda *args, **kwargs: expected_planned,
    )

    with pytest.raises(DevelopmentRuntimeLockError, match="pre-fit snapshot"):
        runtime_lock.load_and_validate_development_runtime_lock(
            lock_path,
            Path("configs/closure_v1/development_runtime_lock.schema.json"),
            require_published=True,
            require_physical_artifacts=False,
        )


def test_recursive_import_closure_includes_shared_validator_and_contract() -> None:
    runtime = {
        "implementation_lock": {
            "required_component_roles": ["runtime_locker"],
            "required_component_paths": {
                "runtime_locker": "src/experiments/lock_closure_development_runtime.py"
            },
            "locker_path": "src/experiments/lock_closure_development_runtime.py",
            "required_legacy_dependency_paths": [],
        }
    }

    paths = recursive_runtime_dependency_paths(runtime)

    assert "src/experiments/lock_closure_development_runtime.py" in paths
    assert "src/experiments/closure_development_runtime_lock.py" in paths
    assert "src/experiments/closure_contract.py" in paths


def test_common_origin_explicit_pointer_matches_local_payload() -> None:
    record = runtime_lock._load_dvc_pointer_for_file(
        "data/closure_v1/common_origin_manifest.parquet"
    )

    assert record == {
        "pointer_path": "data/closure_v1/common_origin_manifest.parquet.dvc",
        "pointer_bytes": 113,
        "pointer_sha256": runtime_lock._sha256_file(
            Path("data/closure_v1/common_origin_manifest.parquet.dvc")
        ),
        "owner_strategy": "explicit_pointer",
        "hash_name": "md5",
        "hash_value": "9e8f21edfc4026ffd8747b3eb1a9774d",
        "size": 2763097,
        "pointer_metadata_verified": True,
        "payload_verified_at_lock": True,
    }


def test_pointer_metadata_validation_does_not_hash_the_dvc_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_lock,
        "_md5_file",
        lambda _: (_ for _ in ()).throw(AssertionError("DVC payload was opened")),
    )

    record = runtime_lock._load_dvc_pointer_metadata(
        "data/closure_v1/common_origin_manifest.parquet"
    )

    assert record["pointer_path"] == (
        "data/closure_v1/common_origin_manifest.parquet.dvc"
    )
    assert record["pointer_metadata_verified"] is True
    assert "payload_verified_at_lock" not in record


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://github.com/ejherran/lentic-pipe.git/",
        "ssh://git@github.com/ejherran/lentic-pipe.git/",
        "git@github.com:ejherran/lentic-pipe.git/",
    ],
)
def test_canonical_git_remote_identity_normalizes_supported_equivalents(
    raw_url: str,
) -> None:
    assert runtime_lock.canonical_git_remote_identity(raw_url) == (
        "github.com/ejherran/lentic-pipe"
    )


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://user:secret@github.com/ejherran/lentic-pipe.git",
        "ssh://git@github.com:22/ejherran/lentic-pipe.git",
        "file:///tmp/lentic-pipe",
        "/tmp/lentic-pipe",
        "https://github.com/ejherran/lentic-pipe.git?token=secret",
        "https://github.com/ejherran/lentic-pipe.git#fragment",
    ],
)
def test_canonical_git_remote_identity_rejects_unsafe_urls_without_echo(
    raw_url: str,
) -> None:
    with pytest.raises(DevelopmentRuntimeLockError) as captured:
        runtime_lock.canonical_git_remote_identity(raw_url)
    assert raw_url not in str(captured.value)
    assert "secret" not in str(captured.value)


def test_canonical_origin_rejects_a_different_repository_without_raw_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = {
        "implementation_lock": {
            "canonical_origin_identity": {
                "remote_name": "origin",
                "expected_identity_sha256": (
                    "475fdf8ad6839d3d291010ff999b4e4c0f8604a0e8d8a09fcebe5ccb843d1905"
                ),
            }
        }
    }
    raw_url = "https://github.com/other/different.git"
    monkeypatch.setattr(
        runtime_lock.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=f"{raw_url}\n"),
    )

    with pytest.raises(DevelopmentRuntimeLockError) as captured:
        runtime_lock.canonical_origin_identity(runtime)
    assert raw_url not in str(captured.value)


def test_dvc_remote_verification_runs_two_exact_up_to_date_pushes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload()
    runtime = {"implementation_lock": {"dvc_remote_name": "gcsremote"}}
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=b"Everything is up to date.\n",
            stderr=b"",
        )

    monkeypatch.setattr(runtime_lock.subprocess, "run", run)
    monkeypatch.setattr(
        runtime_lock,
        "_dvc_remote_configuration_fingerprint",
        lambda remote: {"remote_name": remote, "remote_url_sha256": SHA},
    )

    evidence = runtime_lock.verify_dvc_remote_by_idempotent_push(
        runtime,
        payload["common_origin"],
        payload["expert_state"],
    )

    expected_command = payload["dvc_remote_verification"]["command"]
    assert len(calls) == 2
    assert all(command == expected_command for command, _ in calls)
    assert all(call[1]["env"]["LC_ALL"] == "C" for call in calls)
    assert all(call[1]["env"]["LANG"] == "C" for call in calls)
    assert all(call[1]["env"]["DVC_NO_ANALYTICS"] == "1" for call in calls)
    assert evidence["dvc_remote_verified_at_lock"] is True
    assert [attempt["normalized_result"] for attempt in evidence["attempts"]] == [
        "everything_up_to_date",
        "everything_up_to_date",
    ]


def test_dvc_remote_upload_then_up_to_date_still_runs_twice_and_refuses_lock_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload()
    runtime = {"implementation_lock": {"dvc_remote_name": "gcsremote"}}
    outputs = iter((b"1 file pushed\n", b"Everything is up to date.\n"))
    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        del kwargs
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=next(outputs), stderr=b"")

    monkeypatch.setattr(runtime_lock.subprocess, "run", run)
    monkeypatch.setattr(
        runtime_lock,
        "_dvc_remote_configuration_fingerprint",
        lambda remote: {"remote_name": remote, "remote_url_sha256": SHA},
    )

    with pytest.raises(DevelopmentRuntimeLockError, match="already-up-to-date"):
        runtime_lock.verify_dvc_remote_by_idempotent_push(
            runtime,
            payload["common_origin"],
            payload["expert_state"],
        )
    assert len(calls) == 2


def test_dvc_evidence_rejects_target_and_remote_fingerprint_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload()
    runtime = {"implementation_lock": {"dvc_remote_name": "gcsremote"}}
    evidence = copy.deepcopy(payload["dvc_remote_verification"])
    evidence["targets"][0]["pointer_sha256"] = "f" * 64

    with pytest.raises(DevelopmentRuntimeLockError, match="pointer identities"):
        runtime_lock.validate_dvc_remote_verification_evidence(
            evidence,
            runtime=runtime,
            common_origin=payload["common_origin"],
            expert_state=payload["expert_state"],
            verify_current_remote_config=False,
        )

    evidence = copy.deepcopy(payload["dvc_remote_verification"])
    monkeypatch.setattr(
        runtime_lock,
        "_dvc_remote_configuration_fingerprint",
        lambda remote: {"remote_name": remote, "remote_url_sha256": "f" * 64},
    )
    with pytest.raises(DevelopmentRuntimeLockError, match="fingerprint"):
        runtime_lock.validate_dvc_remote_verification_evidence(
            evidence,
            runtime=runtime,
            common_origin=payload["common_origin"],
            expert_state=payload["expert_state"],
            verify_current_remote_config=True,
        )


def test_publication_guard_binds_lock_bytes_tracking_ref_and_real_remote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "development_runtime_lock.json"
    lock.write_bytes(b"published-lock")
    relative = "reports/closure_v1/00_protocol/development_runtime_lock.json"

    monkeypatch.setattr(runtime_lock, "_require_unmodified", lambda _: relative)
    monkeypatch.setattr(runtime_lock, "_resolve_repo_path", lambda _: lock)

    def git(*args: str, **kwargs: Any) -> str:
        del kwargs
        if args == ("rev-parse", "HEAD"):
            return EXECUTION_HEAD
        if args == ("rev-parse", "origin/main"):
            return PUBLISHED_HEAD
        raise AssertionError(args)

    def run(args: list[str], **kwargs: Any) -> SimpleNamespace:
        del kwargs
        if args[1:3] == ["cat-file", "-e"]:
            return SimpleNamespace(returncode=0, stdout=b"")
        if args[1] == "show":
            return SimpleNamespace(returncode=0, stdout=b"published-lock")
        if args[1:3] == ["ls-remote", "--exit-code"]:
            return SimpleNamespace(
                returncode=0,
                stdout=f"{PUBLISHED_HEAD}\trefs/heads/main\n",
            )
        raise AssertionError(args)

    monkeypatch.setattr(runtime_lock, "_git", git)
    monkeypatch.setattr(runtime_lock.subprocess, "run", run)

    assert runtime_lock._require_lock_published(lock, verify_remote=True) == (
        relative,
        EXECUTION_HEAD,
        "origin/main",
        PUBLISHED_HEAD,
        PUBLISHED_HEAD,
    )


def test_publication_guard_rejects_stale_local_origin_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "development_runtime_lock.json"
    lock.write_bytes(b"published-lock")
    relative = "reports/closure_v1/00_protocol/development_runtime_lock.json"
    remote_head = "f" * 40

    monkeypatch.setattr(runtime_lock, "_require_unmodified", lambda _: relative)
    monkeypatch.setattr(runtime_lock, "_resolve_repo_path", lambda _: lock)
    monkeypatch.setattr(
        runtime_lock,
        "_git",
        lambda *args, **kwargs: (
            EXECUTION_HEAD if args == ("rev-parse", "HEAD") else PUBLISHED_HEAD
        ),
    )

    def run(args: list[str], **kwargs: Any) -> SimpleNamespace:
        del kwargs
        if args[1:3] == ["cat-file", "-e"]:
            return SimpleNamespace(returncode=0, stdout=b"")
        if args[1] == "show":
            return SimpleNamespace(returncode=0, stdout=b"published-lock")
        if args[1:3] == ["ls-remote", "--exit-code"]:
            return SimpleNamespace(
                returncode=0,
                stdout=f"{remote_head}\trefs/heads/main\n",
            )
        raise AssertionError(args)

    monkeypatch.setattr(runtime_lock.subprocess, "run", run)

    with pytest.raises(DevelopmentRuntimeLockError, match="stale"):
        runtime_lock._require_lock_published(lock, verify_remote=True)


def test_locked_parent_publication_requires_local_and_live_remote_equality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_lock,
        "_git",
        lambda *args, **kwargs: HEAD,
    )
    monkeypatch.setattr(
        runtime_lock.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=f"{HEAD}\trefs/heads/main\n",
        ),
    )

    assert runtime_lock.locked_parent_publication_identity(verify_remote=True) == {
        "head": HEAD,
        "tracking_ref": "origin/main",
        "tracking_oid": HEAD,
        "local_tracking_verified": True,
        "remote_ref": "refs/heads/main",
        "remote_oid": HEAD,
        "remote_verified": True,
    }


def test_locked_parent_publication_rejects_stale_tracking_or_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_lock,
        "_git",
        lambda *args, **kwargs: HEAD if args == ("rev-parse", "HEAD") else PUBLISHED_HEAD,
    )
    with pytest.raises(DevelopmentRuntimeLockError, match="local origin/main"):
        runtime_lock.locked_parent_publication_identity(verify_remote=False)

    monkeypatch.setattr(runtime_lock, "_git", lambda *args, **kwargs: HEAD)
    monkeypatch.setattr(
        runtime_lock.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=f"{PUBLISHED_HEAD}\trefs/heads/main\n",
        ),
    )
    with pytest.raises(DevelopmentRuntimeLockError, match="remote main") as captured:
        runtime_lock.locked_parent_publication_identity(verify_remote=True)
    assert "http" not in str(captured.value).lower()


@pytest.mark.parametrize(
    "failure",
    [OSError("network unavailable"), runtime_lock.subprocess.TimeoutExpired("git", 30)],
)
def test_locked_parent_publication_bounds_live_remote_failures_without_url_echo(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    monkeypatch.setattr(runtime_lock, "_git", lambda *args, **kwargs: HEAD)

    def fail(*args: Any, **kwargs: Any) -> SimpleNamespace:
        assert kwargs["timeout"] == 30
        raise failure

    monkeypatch.setattr(runtime_lock.subprocess, "run", fail)
    with pytest.raises(DevelopmentRuntimeLockError) as captured:
        runtime_lock.locked_parent_publication_identity(verify_remote=True)
    assert "cannot be verified" in str(captured.value)
    assert "network unavailable" not in str(captured.value)


def test_critical_parent_tracking_allows_only_explicit_opaque_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_lock.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    record = _file("data/untracked.parquet", "protocol_lock")
    with pytest.raises(DevelopmentRuntimeLockError, match="not Git-tracked"):
        runtime_lock._require_tracked_records_committed_at_head(
            [record],
            HEAD,
            context="parents",
            opaque_dvc_roles=runtime_lock.OPAQUE_DVC_PARENT_ROLES,
        )

    opaque = {**record, "role": "restored_panel"}
    runtime_lock._require_tracked_records_committed_at_head(
        [opaque],
        HEAD,
        context="parents",
        opaque_dvc_roles=runtime_lock.OPAQUE_DVC_PARENT_ROLES,
    )


def test_expert_source_repository_binds_published_h0_as_current_head_ancestor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = _payload()["canonical_origin"]
    source_repository: dict[str, Any] = {
        "head": HEAD,
        "branch": "main",
        "worktree_status_at_start": "clean",
        "canonical_origin": origin,
        "publication": {
            "head": HEAD,
            "tracking_ref": "origin/main",
            "tracking_oid": HEAD,
            "local_tracking_verified": True,
            "remote_ref": "refs/heads/main",
            "remote_oid": HEAD,
            "remote_verified": True,
        },
    }
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(runtime_lock, "canonical_origin_identity", lambda runtime: origin)
    monkeypatch.setattr(runtime_lock, "_git", lambda *args, **kwargs: EXECUTION_HEAD)
    monkeypatch.setattr(
        runtime_lock,
        "_require_ancestor",
        lambda ancestor, descendant: calls.append((ancestor, descendant)),
    )

    runtime_lock._validate_expert_source_repository(
        source_repository,
        runtime={},
    )
    assert calls == [(HEAD, EXECUTION_HEAD)]

    drifted = copy.deepcopy(source_repository)
    drifted["publication"]["remote_oid"] = PUBLISHED_HEAD
    with pytest.raises(DevelopmentRuntimeLockError, match="publication evidence"):
        runtime_lock._validate_expert_source_repository(drifted, runtime={})

    open_ended = copy.deepcopy(source_repository)
    open_ended["publication"]["unexpected"] = True
    with pytest.raises(DevelopmentRuntimeLockError, match="keys drifted"):
        runtime_lock._validate_expert_source_repository(open_ended, runtime={})

    untyped_origin = copy.deepcopy(source_repository)
    untyped_origin["canonical_origin"]["fetch_push_identity_equal"] = 1
    with pytest.raises(DevelopmentRuntimeLockError, match="publication evidence"):
        runtime_lock._validate_expert_source_repository(untyped_origin, runtime={})


def test_ancestry_guard_rejects_unrelated_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_lock.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )

    with pytest.raises(DevelopmentRuntimeLockError, match="not an ancestor"):
        runtime_lock._require_ancestor(HEAD, PUBLISHED_HEAD)


def test_environment_requires_cpu() -> None:
    with pytest.raises(DevelopmentRuntimeLockError, match="device=cpu"):
        environment_payload("auto")

    with pytest.raises(DevelopmentRuntimeLockError, match="device=cpu"):
        environment_payload("cuda:0")

    cpu = environment_payload("cpu")
    assert cpu["device"] == "cpu"
    assert cpu["cublas_workspace_config"] is None
    assert cpu["cpu_execution_policy"]["torch_num_threads_observed"] == 1
    assert cpu["cpu_execution_policy"]["torch_num_interop_threads_observed"] == 1


def test_verification_command_has_fixed_timeout_and_generic_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(*args: Any, **kwargs: Any) -> SimpleNamespace:
        assert kwargs["timeout"] == 3600
        raise runtime_lock.subprocess.TimeoutExpired("poetry", 3600)

    monkeypatch.setattr(runtime_lock.subprocess, "run", timeout)
    with pytest.raises(DevelopmentRuntimeLockError, match="fixed bound") as captured:
        runtime_lock.command_evidence(("poetry", "run", "ty", "check"))
    assert "poetry" not in str(captured.value)


def test_verification_failure_never_echoes_captured_urls_or_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_url = b"https://user:secret-token@example.invalid/private"
    secret_stderr = b"Authorization: Bearer fictional-secret"

    def failed(*args: Any, **kwargs: Any) -> SimpleNamespace:
        del args, kwargs
        return SimpleNamespace(
            returncode=7,
            stdout=secret_url,
            stderr=secret_stderr,
        )

    monkeypatch.setattr(runtime_lock.subprocess, "run", failed)
    with pytest.raises(
        DevelopmentRuntimeLockError,
        match=r"exit_code=7, stdout_sha256=[0-9a-f]{64}, stderr_sha256=[0-9a-f]{64}",
    ) as captured:
        runtime_lock.command_evidence(("poetry", "run", "pytest", "tests/fake.py"))

    message = str(captured.value)
    assert "example.invalid" not in message
    assert "secret-token" not in message
    assert "fictional-secret" not in message
    assert "tests/fake.py" not in message


def test_planned_records_are_recomputed_from_locked_head_not_current_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expert_path = "data/closure_v1/development/expert/expert.parquet"
    future_path = "data/closure_v1/development/pipe/future.parquet"
    model_path = "models/closure_v1/P0/seed_1.pt"
    manifest_path = "reports/closure_v1/02_models/P0/seed_1_manifest.json"
    pointer_blob = b"expert-pointer"
    manifest_blob = b"locked-manifest"
    runtime = {
        "artifacts": {
            "dvc_ownership_plan": {
                "data/closure_v1": "explicit_pointer_per_materialized_parquet",
                "models/closure_v1": "models.dvc_monolithic_parent",
                "reports/closure_v1": "explicit_pointer_per_materialized_parquet",
            },
            "expert_state_path": expert_path,
        }
    }
    expert_state = {
        "artifact": {
            "path": expert_path,
            "role": "expert_state",
            "bytes": 17,
            "sha256": SHA,
        },
        "dvc": {
            "pointer_path": f"{expert_path}.dvc",
            "pointer_bytes": len(pointer_blob),
            "pointer_sha256": runtime_lock.hashlib.sha256(pointer_blob).hexdigest(),
        },
    }
    blobs = {
        f"{expert_path}.dvc": pointer_blob,
        "models.dvc": b"models-parent",
        manifest_path: manifest_blob,
    }
    monkeypatch.setattr(
        runtime_lock,
        "_rendered_runtime_paths",
        lambda _: ([expert_path, future_path, model_path, manifest_path], SHA),
    )
    monkeypatch.setattr(
        runtime_lock,
        "_git_blob_at_head",
        lambda head, path: blobs.get(path),
    )

    snapshot = runtime_lock.planned_artifact_records(
        runtime,
        locked_head=HEAD,
        expert_state=expert_state,
    )

    records = {record["path"]: record for record in snapshot["records"]}
    assert records[expert_path]["materialized_at_lock"] is True
    assert records[expert_path]["pointer_verified"] is True
    assert records[expert_path]["bytes"] == 17
    assert records[future_path]["materialized_at_lock"] is False
    assert records[future_path]["owner_path"] == f"{future_path}.dvc"
    assert records[model_path]["materialized_at_lock"] is False
    assert records[model_path]["owner_path"] == "models.dvc"
    assert records[manifest_path] == {
        "path": manifest_path,
        "artifact_class": "lightweight",
        "materialized_at_lock": True,
        "owner_strategy": "git_when_materialized",
        "owner_path": manifest_path,
        "bytes": len(manifest_blob),
        "sha256": runtime_lock.hashlib.sha256(manifest_blob).hexdigest(),
        "pointer_verified": False,
    }


def test_planned_snapshot_rejects_unexpected_prefit_pointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expert_path = "data/closure_v1/development/expert/expert.parquet"
    future_path = "data/closure_v1/development/pipe/future.parquet"
    pointer_blob = b"expert-pointer"
    runtime = {
        "artifacts": {
            "dvc_ownership_plan": {
                "data/closure_v1": "explicit_pointer_per_materialized_parquet",
                "models/closure_v1": "models.dvc_monolithic_parent",
                "reports/closure_v1": "explicit_pointer_per_materialized_parquet",
            },
            "expert_state_path": expert_path,
        }
    }
    expert_state = {
        "artifact": {
            "path": expert_path,
            "role": "expert_state",
            "bytes": 17,
            "sha256": SHA,
        },
        "dvc": {
            "pointer_path": f"{expert_path}.dvc",
            "pointer_bytes": len(pointer_blob),
            "pointer_sha256": runtime_lock.hashlib.sha256(pointer_blob).hexdigest(),
        },
    }
    monkeypatch.setattr(
        runtime_lock,
        "_rendered_runtime_paths",
        lambda _: ([expert_path, future_path], SHA),
    )
    monkeypatch.setattr(
        runtime_lock,
        "_git_blob_at_head",
        lambda head, path: (
            pointer_blob if path == f"{expert_path}.dvc" else b"unexpected-pointer"
        ),
    )

    with pytest.raises(DevelopmentRuntimeLockError, match="forbidden DVC pointer"):
        runtime_lock.planned_artifact_records(
            runtime,
            locked_head=HEAD,
            expert_state=expert_state,
        )


def _lineage_payload_and_runtime() -> tuple[dict[str, Any], dict[str, Any]]:
    sites = [f"site-{index:03d}" for index in range(353)]
    frame = pd.DataFrame(
        {
            "source_id": ["wqp"] * 353,
            "site_id": sites,
            "year_month": ["2021-12"] * 353,
            "time_role": ["calibration_threshold"] * 353,
            "delta_previous_month_missing": [True] * 353,
        }
    )
    runtime = {
        "primary_autoregressive_state": {
            "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
            "state_export": {
                "p0_source_projection_columns": ["source_id", "site_id", "year_month"],
                "p0_output_columns": list(frame.columns),
            },
        }
    }
    scan = DevelopmentScanAudit(
        materialized_rows=353,
        returned_rows=353,
        boundary_crossing_rows=0,
        _role_counts=(("calibration_threshold", 353),),
    )

    return expert_lineage_audit(frame, runtime=runtime, scan_audit=scan), runtime


def test_lock_lineage_validator_accepts_exact_builder_payload() -> None:
    payload, runtime = _lineage_payload_and_runtime()

    runtime_lock._validate_expert_lineage_payload(payload, runtime=runtime)


def test_lock_lineage_validator_accepts_builder_payload_after_sorted_json_roundtrip() -> None:
    payload, runtime = _lineage_payload_and_runtime()
    serialized = json.dumps(payload, sort_keys=True)
    restored = json.loads(serialized)

    assert tuple(restored["role_counts"]) == (
        "calibration_threshold",
        "model_selection",
        "training",
    )
    runtime_lock._validate_expert_lineage_payload(restored, runtime=runtime)


@pytest.mark.parametrize(
    ("scope", "field", "value"),
    [
        ("root", "unexpected", "open-ended"),
        ("root", "zero_holdout_overlap", 1),
        ("checks", "zero_holdout_overlap", 1),
        ("scan", "unexpected", 0),
    ],
)
def test_lock_lineage_validator_rejects_unknown_or_untyped_fields(
    scope: str,
    field: str,
    value: object,
) -> None:
    payload, runtime = _lineage_payload_and_runtime()
    if scope == "root":
        payload[field] = value
    else:
        payload[scope][field] = value

    with pytest.raises(DevelopmentRuntimeLockError):
        runtime_lock._validate_expert_lineage_payload(payload, runtime=runtime)


def _minimal_expert_completion_payload() -> dict[str, Any]:
    return {
        "manifest_version": "closure_expert_no_current_state_manifest_v1",
        "status": "completed",
        "generated_at_utc": "2026-08-03T12:00:00+00:00",
        "experiment_id": "closure_v1",
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "model_id": "P0",
        "artifact_role": "deterministic_expert_state_pre_e0_dl",
        "future_outcomes_accessed": False,
        "post_2021_outcomes_materialized": False,
        "zero_holdout_overlap": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "runtime": {},
        "state_mapping": {},
        "source_projection": [],
        "output_allowlist": [],
        "time_roles": [],
        "source_repository": {},
        "counts": {},
        "script": {},
        "inputs": [],
        "dependencies": [],
        "completion_marker_written_last": True,
        "outputs": [],
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("future_outcomes_accessed", 0),
        ("zero_holdout_overlap", 1),
        ("completion_marker_written_last", 1),
    ],
)
def test_expert_completion_rejects_integer_boolean_seals_before_file_io(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: int,
) -> None:
    payload = _minimal_expert_completion_payload()
    payload[field] = value
    runtime = {
        "primary_autoregressive_state": {
            "surface_id": payload["surface_id"],
            "state_export": {},
            "model_state_mappings": {"P0": {}},
        },
        "artifacts": {},
    }
    monkeypatch.setattr(runtime_lock, "load_json_mapping", lambda _: payload)

    with pytest.raises(DevelopmentRuntimeLockError, match="requires"):
        runtime_lock._validate_expert_completion(
            "manifest.json",
            "state.parquet",
            "lineage.json",
            runtime=runtime,
            runtime_config=Path("runtime.yaml"),
            runtime_schema=Path("runtime.schema.json"),
            require_physical_artifact=False,
        )


def test_expert_completion_rejects_open_ended_top_level_dialect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _minimal_expert_completion_payload()
    payload["unexpected"] = "open-ended"
    monkeypatch.setattr(runtime_lock, "load_json_mapping", lambda _: payload)

    with pytest.raises(DevelopmentRuntimeLockError, match="keys drifted"):
        runtime_lock._validate_expert_completion(
            "manifest.json",
            "state.parquet",
            "lineage.json",
            runtime={},
            runtime_config=Path("runtime.yaml"),
            runtime_schema=Path("runtime.schema.json"),
            require_physical_artifact=False,
        )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("checks", "zero_holdout_overlap"), False),
        (("checks", "no_post_2021_materialization"), False),
        (("root", "post_2021_outcomes_materialized"), True),
        (("root", "zero_holdout_overlap"), False),
    ],
)
def test_lock_lineage_validator_rejects_builder_seal_drift(
    path: tuple[str, str],
    value: bool,
) -> None:
    payload, runtime = _lineage_payload_and_runtime()
    if path[0] == "root":
        payload[path[1]] = value
    else:
        payload[path[0]][path[1]] = value

    with pytest.raises(DevelopmentRuntimeLockError):
        runtime_lock._validate_expert_lineage_payload(payload, runtime=runtime)


def test_structure_validation_does_not_touch_physical_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = copy.deepcopy(_payload())
    monkeypatch.setattr(
        runtime_lock,
        "_sha256_file",
        lambda _: (_ for _ in ()).throw(AssertionError("physical file read")),
    )

    validate_development_runtime_lock_payload(
        payload,
        load_json_mapping(DEFAULT_LOCK_SCHEMA),
    )
