from __future__ import annotations

import builtins
import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from src.data import prepare_commit_artifacts as precommit_artifacts
from src.data.prepare_commit_artifacts import (
    CLOSURE_COMMON_ORIGIN_CODE_PATHS,
    CLOSURE_COMMON_ORIGIN_CONFIG_PATHS,
    CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES,
    CLOSURE_COMMON_ORIGIN_REPRODUCTION_COMMAND,
    CLOSURE_COMMON_ORIGIN_SOURCE_PATHS,
    CLOSURE_COMMON_ORIGIN_SOURCE_ROLES,
    CLOSURE_DEVELOPMENT_RUNTIME_LOCK_PATH,
    CLOSURE_DEVELOPMENT_RUNTIME_LOCK_SCHEMA,
    CLOSURE_EXPERT_STATE_MANIFEST_PATH,
    CLOSURE_EXPERT_STATE_OUTPUT_PATH,
    CommandResult,
    DEFAULT_DVC_MANIFEST,
    DvcArtifact,
    declared_artifacts_missing_pointers,
    discover_relevant_manifest_paths,
    dvc_pointer_path,
    has_failing_findings,
    has_local_dvc_pointer,
    is_experiment_manifest_path,
    is_report_artifact_path,
    load_configured_dvc_artifacts,
    reproducibility_checks,
    sha256_directory,
    sha256_file,
    unmanaged_ignored_heavy_paths,
    validate_experiment_manifests,
    validate_closure_expert_state_manifest,
    validate_freeze_freshness,
)


def test_direct_entrypoint_bootstrap_makes_project_root_importable(
    monkeypatch,
) -> None:
    filtered_path = [
        entry
        for entry in precommit_artifacts.sys.path
        if Path(entry or ".").resolve() != precommit_artifacts.PROJECT_ROOT
    ]
    monkeypatch.setattr(precommit_artifacts.sys, "path", filtered_path)

    precommit_artifacts._ensure_project_root_importable()

    assert precommit_artifacts.sys.path[0] == str(precommit_artifacts.PROJECT_ROOT)


def _expected_closure_dvc_artifacts() -> dict[str, DvcArtifact]:
    seeds = (1729, 20260612, 20260613, 20260614, 314159)
    expected = {
        "closure_v1_common_origin_manifest": DvcArtifact(
            "closure_v1_common_origin_manifest",
            Path("data/closure_v1/common_origin_manifest.parquet"),
            "closure_common_origin_manifest",
            "wqp",
            True,
        ),
        "closure_v1_expert_no_current_state": DvcArtifact(
            "closure_v1_expert_no_current_state",
            Path("data/closure_v1/development/expert/expert_no_current_state.parquet"),
            "closure_expert_no_current_state",
            "wqp",
            True,
        ),
        "closure_v1_p0_expert_sequence": DvcArtifact(
            "closure_v1_p0_expert_sequence",
            Path("data/closure_v1/development/sequences/P0/expert_no_current.parquet"),
            "closure_pipe_sequence",
            "wqp",
            True,
        ),
    }
    for seed in seeds:
        expected[f"closure_v1_anfis_state_seed_{seed}"] = DvcArtifact(
            f"closure_v1_anfis_state_seed_{seed}",
            Path(
                f"data/closure_v1/development/anfis/seed_{seed}/"
                "adaptive_no_current_state.parquet"
            ),
            "closure_anfis_state",
            "wqp",
            True,
        )
        expected[f"closure_v1_p1_sequence_seed_{seed}"] = DvcArtifact(
            f"closure_v1_p1_sequence_seed_{seed}",
            Path(f"data/closure_v1/development/sequences/P1/seed_{seed}.parquet"),
            "closure_pipe_sequence",
            "wqp",
            True,
        )
        for model_id in ("P0", "P1"):
            artifact_id = f"closure_v1_{model_id.lower()}_rollout_seed_{seed}"
            expected[artifact_id] = DvcArtifact(
                artifact_id,
                Path(
                    f"data/closure_v1/development/rollouts/{model_id}/"
                    f"seed_{seed}.parquet"
                ),
                "closure_pipe_rollout",
                "wqp",
                True,
            )
    return expected


def test_default_dvc_inventory_loads_all_planned_post_lock_closure_parquets() -> None:
    artifacts = load_configured_dvc_artifacts(DEFAULT_DVC_MANIFEST)
    matches = {
        artifact.artifact_id: artifact
        for artifact in artifacts
        if artifact.artifact_id.startswith("closure_v1_")
    }

    assert matches == _expected_closure_dvc_artifacts()
    assert len(matches) == 23


def test_declared_artifacts_missing_pointers_selects_existing_declared_targets(tmp_path: Path) -> None:
    existing = tmp_path / "data" / "pipe_grud" / "rollouts.parquet"
    existing.parent.mkdir(parents=True)
    existing.write_text("placeholder", encoding="utf-8")
    tracked = tmp_path / "data" / "pipe_grud" / "sequence.parquet"
    tracked.write_text("placeholder", encoding="utf-8")
    dvc_pointer_path(tracked).write_text("outs: []\n", encoding="utf-8")
    missing = tmp_path / "data" / "pipe_grud" / "future.parquet"

    artifacts = [
        DvcArtifact("rollouts", existing, "pipe_rollout_alerts", "multi_source", True),
        DvcArtifact("sequence", tracked, "pipe_sequence_dataset", "multi_source", True),
        DvcArtifact("future", missing, "future", "multi_source", True),
        DvcArtifact("small", tmp_path / "reports" / "small.md", "report", "multi_source", False),
    ]

    selected = declared_artifacts_missing_pointers(artifacts)

    assert selected == [artifacts[0]]


def test_unmanaged_ignored_heavy_paths_skips_paths_with_local_dvc_pointer(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    managed = Path("reports/pipe/full_rows.parquet")
    unmanaged = Path("reports/pipe/untracked_rows.parquet")
    managed.parent.mkdir(parents=True)
    managed.write_text("managed", encoding="utf-8")
    unmanaged.write_text("unmanaged", encoding="utf-8")
    dvc_pointer_path(managed).write_text(
        "outs:\n"
        "- md5: abc123\n"
        "  size: 7\n"
        "  hash: md5\n"
        "  path: full_rows.parquet\n",
        encoding="utf-8",
    )

    def fake_run_command(command: list[str], **_: object) -> CommandResult:
        assert command == ["git", "status", "--short", "--ignored", "--untracked-files=normal"]
        return CommandResult(
            command=command,
            returncode=0,
            stdout=(
                "!! reports/pipe/full_rows.parquet\n"
                "!! reports/pipe/untracked_rows.parquet\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("src.data.prepare_commit_artifacts.run_command", fake_run_command)

    assert has_local_dvc_pointer(managed)
    assert not has_local_dvc_pointer(unmanaged)
    assert unmanaged_ignored_heavy_paths([]) == [unmanaged]


def _manifest_record(path: Path) -> dict[str, object]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _closure_protocol_lock_payload(companion: Path, script: Path) -> dict[str, object]:
    return {
        "lock_version": "closure_protocol_lock_v1",
        "status": "locked",
        "generated_lock_companions": [_manifest_record(companion)],
        "protocol_components": [_manifest_record(script)],
        "source_artifacts": [],
        "locked_repository": {"worktree_status": "clean", "dirty_paths": []},
        "future_outcomes_accessed": False,
        "lock_command_semantically_decodes_post_2021_outcomes": False,
        "holdout_assignment_created": False,
    }


def _closure_common_origin_payload(
    *,
    output: Path,
    code: list[Path],
    configs: list[Path],
    source_inputs: list[Path],
    parent_artifacts: list[Path],
) -> dict[str, object]:
    parent_records = [
        {**_manifest_record(path), "role": role}
        for path, (_, role) in zip(
            parent_artifacts,
            CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES,
            strict=True,
        )
    ]
    assignment = dict(parent_records[2])
    assignment.pop("role")
    assignment.update(
        {
            "eligible_locations": 441,
            "development_locations": 353,
            "holdout_locations": 88,
            "holdout_fit_overlap_count": 0,
        }
    )
    return {
        "manifest_version": "closure_common_origin_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "future_outcomes_accessed": False,
        "target_values_projected": [],
        "target_parquet_semantically_opened": False,
        "post_cutoff_target_rows_materialized": 0,
        "target_availability_used_for_origin_selection": False,
        "availability_join": "left_after_intent_freeze",
        "execution": {
            "repository": {
                "base_head": "a" * 40,
                "base_head_is_complete_source_identity": False,
                "tracked_worktree_status": "dirty",
                "tracked_status_lines": [" M src/experiments/build_common_origin_manifest.py"],
            },
            "source_tree_identity": "code_config_parent_sha256_records",
            "reproduction_command": CLOSURE_COMMON_ORIGIN_REPRODUCTION_COMMAND,
            "future_outcomes_semantically_decoded": False,
        },
        "assignment": assignment,
        "output": _manifest_record(output),
        "code": [_manifest_record(path) for path in code],
        "configs": [_manifest_record(path) for path in configs],
        "source_inputs": [
            {
                **_manifest_record(path),
                "role": role,
                "hash_source": "protocol_lock",
            }
            for path, role in zip(source_inputs, CLOSURE_COMMON_ORIGIN_SOURCE_ROLES, strict=True)
        ],
        "parent_artifacts": parent_records,
    }


def _write_closure_common_origin_fixture(
    root: Path,
) -> tuple[Path, dict[str, object], tuple[Path, ...]]:
    output = root / "data/closure_v1/common_origin_manifest.parquet"
    code = [root / path for path in CLOSURE_COMMON_ORIGIN_CODE_PATHS]
    configs = [root / path for path in CLOSURE_COMMON_ORIGIN_CONFIG_PATHS]
    source_inputs = [root / path for path in CLOSURE_COMMON_ORIGIN_SOURCE_PATHS]
    parent_artifacts = [
        root / path for path, _ in CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES
    ]
    all_records = [output, *code, *configs, *source_inputs, *parent_artifacts]
    for path in all_records:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {path.relative_to(root).as_posix()}\n", encoding="utf-8")

    manifest = root / "reports/closure_v1/01_surface/common_origin_manifest.json"
    manifest.parent.mkdir(parents=True)
    payload = _closure_common_origin_payload(
        output=output.relative_to(root),
        code=[path.relative_to(root) for path in code],
        configs=[path.relative_to(root) for path in configs],
        source_inputs=[path.relative_to(root) for path in source_inputs],
        parent_artifacts=[path.relative_to(root) for path in parent_artifacts],
    )
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return (
        manifest.relative_to(root),
        payload,
        tuple(path.relative_to(root) for path in all_records),
    )


def _write_closure_mifal_development_fixture(
    root: Path,
) -> tuple[Path, dict[str, Any], tuple[Path, ...], tuple[Path, ...]]:
    raw_contract: dict[str, Any] = {
        "columns": [
            {"name": f"column_{index}", "dtype": "string", "nullable": False}
            for index in range(28)
        ],
        "fixture": "exact_raw_contract",
    }
    input_records: list[dict[str, Any]] = []
    input_by_path: dict[Path, dict[str, Any]] = {}
    input_paths: list[Path] = []
    for path, role in precommit_artifacts.CLOSURE_MIFAL_DEVELOPMENT_INPUT_PATHS_AND_ROLES:
        physical = root / path
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_text(f"input fixture: {path.as_posix()}\n", encoding="utf-8")
        record = {**_manifest_record(path), "artifact_role": role}
        input_records.append(record)
        input_by_path[path] = record
        input_paths.append(path)

    output_records: list[dict[str, Any]] = []
    output_paths: list[Path] = []
    for path in precommit_artifacts.CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS:
        physical = root / path
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_text(f"output fixture: {path.as_posix()}\n", encoding="utf-8")
        output_records.append(_manifest_record(path))
        output_paths.append(path)

    authority = {
        **precommit_artifacts.CLOSURE_MIFAL_EXPECTED_AUTHORITY,
        "raw_prediction_contract": raw_contract,
    }
    model_spec = precommit_artifacts.CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS[1]
    lineage = precommit_artifacts.CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS[2]
    payload: dict[str, Any] = {
        "schema_version": precommit_artifacts.CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_SCHEMA_VERSION,
        "experiment_id": "closure_v1",
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "model_id": "M0",
        "gate": "E0-MR",
        "status": precommit_artifacts.CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_STATUS,
        "started_at_utc": "2026-08-07T23:13:12.949966+00:00",
        "counts": dict(precommit_artifacts.CLOSURE_MIFAL_EXPECTED_COUNTS),
        "raw_prediction_contract": raw_contract,
        "model_spec_sha256": input_by_path.get(model_spec, output_records[1])["sha256"],
        "lineage_audit_sha256": input_by_path.get(lineage, output_records[2])["sha256"],
        "runtime_versions": {
            "python": "3.14.6",
            "numpy": "2.4.5",
            "pandas": "3.0.3",
            "pyarrow": "24.0.0",
            "threadpoolctl": "3.6.0",
            "threadpool_limit": 1,
            "mifal_core": "5.0.0",
        },
        "effective_authority": authority,
        "inputs": input_records,
        "script": input_by_path[
            precommit_artifacts.CLOSURE_MIFAL_DEVELOPMENT_SCRIPT
        ],
        "source_code": [
            input_by_path[path]
            for path in precommit_artifacts.CLOSURE_MIFAL_DEVELOPMENT_SOURCE_PATHS
        ],
        "outputs": output_records,
        "manifest_written_last": True,
        "tuning_performed": False,
        "targets_opened": False,
        "calibration_performed": False,
        "metrics_computed": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_run": False,
        "network_calls_made": False,
        "future_outcomes_accessed": False,
        "outcome_access_log_state": "absent",
        "completion_marker_written_last": True,
    }
    manifest = precommit_artifacts.CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_PATH
    physical_manifest = root / manifest
    physical_manifest.parent.mkdir(parents=True, exist_ok=True)
    physical_manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest, payload, tuple(input_paths), tuple(output_paths)


def _validate_closure_mifal_fixture(
    manifest: Path,
    outputs: tuple[Path, ...],
) -> list[precommit_artifacts.ReproducibilityFinding]:
    staged = {manifest}
    staged.update(
        path for path in outputs if path.as_posix().startswith("reports/")
    )
    return validate_experiment_manifests(
        staged_paths=staged,
        artifacts=[],
        max_hash_bytes=0,
        verify_manifest_inputs=False,
    )


def _bind_closure_mifal_fixture_raw_contract(
    monkeypatch,
    payload: dict[str, Any],
) -> None:
    digest = precommit_artifacts._canonical_json_sha256(
        payload["raw_prediction_contract"]
    )
    assert digest is not None
    monkeypatch.setattr(
        precommit_artifacts,
        "CLOSURE_MIFAL_RAW_PREDICTION_CONTRACT_SHA256",
        digest,
    )


def test_closure_mifal_development_manifest_adapts_exact_unpublished_dialect(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, payload, _, outputs = _write_closure_mifal_development_fixture(
        tmp_path
    )
    _bind_closure_mifal_fixture_raw_contract(monkeypatch, payload)

    findings = _validate_closure_mifal_fixture(manifest, outputs)

    assert not has_failing_findings(findings)
    assert not any(finding.level == "warn" for finding in findings)
    assert any(
        "28 inputs, three source records, five outputs" in finding.message
        for finding in findings
    )


def test_closure_mifal_development_status_compatibility_is_exact_path_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _, payload, _, _ = _write_closure_mifal_development_fixture(tmp_path)
    _bind_closure_mifal_fixture_raw_contract(monkeypatch, payload)
    alternate = Path("reports/other/M0/manifest.json")
    alternate.parent.mkdir(parents=True, exist_ok=True)
    alternate.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    findings = validate_experiment_manifests(
        staged_paths={alternate},
        artifacts=[],
        max_hash_bytes=0,
        verify_manifest_inputs=False,
    )

    assert has_failing_findings(findings)
    assert any("expected `completed`" in finding.message for finding in findings)


def test_closure_mifal_development_manifest_rejects_contract_mutation_matrix(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, payload, _, outputs = _write_closure_mifal_development_fixture(
        tmp_path
    )
    _bind_closure_mifal_fixture_raw_contract(monkeypatch, payload)
    mutations: list[tuple[str, dict[str, Any]]] = []

    mutated = deepcopy(payload)
    mutated["schema_version"] = "wrong_schema"
    mutations.append(("schema", mutated))

    mutated = deepcopy(payload)
    mutated["status"] = "completed"
    mutations.append(("status", mutated))

    mutated = deepcopy(payload)
    mutated["model_id"] = "M1"
    mutations.append(("identity", mutated))

    mutated = deepcopy(payload)
    cast(dict[str, Any], mutated["counts"])["eligible_origins"] = 9731
    mutations.append(("counts", mutated))

    mutated = deepcopy(payload)
    cast(dict[str, Any], mutated["effective_authority"])[
        "e0_m_authorized"
    ] = True
    mutations.append(("authority", mutated))

    mutated = deepcopy(payload)
    cast(dict[str, Any], mutated["raw_prediction_contract"])["fixture"] = "drift"
    mutations.append(("raw_contract", mutated))

    mutated = deepcopy(payload)
    inputs = cast(list[dict[str, Any]], mutated["inputs"])
    inputs[1] = deepcopy(inputs[0])
    mutations.append(("input_duplicate", mutated))

    mutated = deepcopy(payload)
    cast(list[dict[str, Any]], mutated["source_code"]).reverse()
    mutations.append(("source_triplet", mutated))

    mutated = deepcopy(payload)
    cast(list[dict[str, Any]], mutated["outputs"]).reverse()
    mutations.append(("output_order", mutated))

    mutated = deepcopy(payload)
    mutated["model_spec_sha256"] = "0" * 64
    mutations.append(("cross_hash", mutated))

    mutated = deepcopy(payload)
    mutated["targets_opened"] = True
    mutations.append(("false_flag", mutated))

    mutated = deepcopy(payload)
    marker = mutated.pop("completion_marker_written_last")
    mutated = {"completion_marker_written_last": marker, **mutated}
    mutations.append(("last_key", mutated))

    mutated = deepcopy(payload)
    mutated["script"] = deepcopy(cast(list[dict[str, Any]], mutated["inputs"])[0])
    mutations.append(("script", mutated))

    for label, mutated_payload in mutations:
        manifest.write_text(
            json.dumps(mutated_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        findings = _validate_closure_mifal_fixture(manifest, outputs)
        assert has_failing_findings(findings), label


def test_closure_mifal_development_manifest_forces_physical_hash_checks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, payload, inputs, outputs = _write_closure_mifal_development_fixture(
        tmp_path
    )
    _bind_closure_mifal_fixture_raw_contract(monkeypatch, payload)

    for path in (inputs[0], outputs[0]):
        original = path.read_bytes()
        path.write_bytes(original + b"drift\n")
        findings = _validate_closure_mifal_fixture(manifest, outputs)
        assert has_failing_findings(findings), path
        assert any(
            finding.path == path.as_posix()
            and "SHA-256 changed" in finding.message
            for finding in findings
        ), path
        path.write_bytes(original)


def test_closure_protocol_lock_is_a_strict_experiment_manifest() -> None:
    path = Path("reports/closure_v1/00_protocol/protocol_lock.json")

    assert is_experiment_manifest_path(path)
    assert not is_report_artifact_path(path)
    assert not is_experiment_manifest_path(Path("reports/other/protocol_lock.json"))


def test_closure_e0_u_precommit_compares_configured_origin_not_live_evidence_url() -> None:
    class ActivationStub:
        CONFIGURED_ORIGIN_URL = "git@github.com:ejherran/lentic-pipe.git"
        LIVE_REMOTE_URL = "https://github.com/ejherran/lentic-pipe.git"
        observed = CONFIGURED_ORIGIN_URL

        @classmethod
        def _git_text(cls, _repo_root: Path, args: tuple[str, ...]) -> str:
            assert args == ("remote", "get-url", "origin")
            return cls.observed + "\n"

    assert precommit_artifacts._closure_e0_u_configured_origin_matches(
        ActivationStub,
        repo_root=Path("."),
    )

    ActivationStub.observed = ActivationStub.LIVE_REMOTE_URL
    assert not precommit_artifacts._closure_e0_u_configured_origin_matches(
        ActivationStub,
        repo_root=Path("."),
    )


def test_closure_e0_u_activation_is_an_exact_authoritative_manifest_without_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.experiments import closure_e0_u_authority as authority
    from src.experiments import run_closure_benchmark as runner

    activation = precommit_artifacts.CLOSURE_E0_U_ACTIVATION_PATH
    alternate = Path("reports/other/closure_e0_u_activation.json")
    assert is_experiment_manifest_path(activation)
    assert not is_report_artifact_path(activation)
    assert not is_experiment_manifest_path(alternate)
    assert is_report_artifact_path(alternate)

    schema_bytes = (
        precommit_artifacts.PROJECT_ROOT
        / precommit_artifacts.CLOSURE_E0_U_ACTIVATION_SCHEMA_PATH
    ).read_bytes()
    monkeypatch.chdir(tmp_path)
    schema_path = precommit_artifacts.CLOSURE_E0_U_ACTIVATION_SCHEMA_PATH
    schema_path.parent.mkdir(parents=True)
    schema_path.write_bytes(schema_bytes)

    def scope_record(path: str, status: str) -> dict[str, Any]:
        return {
            "bytes": 1,
            "mode": "100644",
            "path": path,
            "sha256": "a" * 64,
            "status": status,
        }

    def source_record(path: str) -> dict[str, Any]:
        return {
            "path": path,
            "bytes": 1,
            "mode": 0o644,
            "nlink": 1,
            "sha256": "b" * 64,
        }

    layout = authority._contract_layout(runner.sealed_batch_contract())
    heavy = sorted(
        path
        for path, format_name in layout["formats_by_path"].items()
        if format_name == "parquet"
    )
    direct = sorted(set(layout["expected_paths"]) - set(heavy))
    deep_sources = [
        {
            "role": spec["role"],
            "path": spec["path"],
            "bytes": index + 1,
            "sha256": f"{index + 1:064x}",
        }
        for index, spec in enumerate(authority._phase3_overlay_source_specs())
    ]
    payload: dict[str, Any] = {
        "schema_version": "closure_e0_u_activation_v1",
        "experiment_id": "closure_v1",
        "gate": "E0-U",
        "base_r_commit": authority.BASE_R_COMMIT,
        "h_commit": "c" * 40,
        "p_commit": "d" * 40,
        "execution_id": "closure-e0-u-test",
        "git_remote_url": authority.LIVE_REMOTE_URL,
        "sealed_batch_command": authority.SEALED_BATCH_COMMAND,
        "h_scope": sorted(
            (
                scope_record(authority.AUTHORITY_SOURCE_PATH, "A"),
                scope_record(authority.CONTEXT_BUILDER_SOURCE_PATH, "A"),
                scope_record(authority.RUNNER_SOURCE_PATH, "M"),
            ),
            key=lambda record: cast(str, record["path"]),
        ),
        "p_scope": [
            scope_record(path, "A") for path in authority.EXPECTED_P_SCOPE_PATHS
        ],
        "phase3_overlay_deep_validation": {
            "schema_version": "closure_phase3_input_overlay_deep_validation_v1",
            "status": "passed",
            "experiment_id": "closure_v1",
            "surface_id": "closure_v1_phase3_input_overlay",
            "gate": "pre_E0-U",
            "expected_h_commit": "c" * 40,
            "builder_source": {
                "role": "phase3_input_overlay_builder",
                "path": authority.PHASE3_OVERLAY_BUILDER_PATH,
                "bytes": 100,
                "sha256": "f" * 64,
            },
            "source_inputs": deep_sources,
            "source_input_count": 27,
            "source_inputs_sha256": authority._sha256_bytes(
                authority._canonical_json_bytes(deep_sources)
            ),
            "manifest": {
                "path": authority.PHASE3_OVERLAY_MANIFEST_PATH,
                "bytes": 200,
                "sha256": "e" * 64,
            },
            "physical_outputs": [
                {
                    "path": path,
                    "bytes": 300 + index,
                    "sha256": str(index + 1) * 64,
                }
                for index, (path, _role) in enumerate(
                    authority.PHASE3_OVERLAY_OUTPUTS
                )
            ],
            "checkpoint_count": 25,
            "state_dict_array_count": 195,
            "warmup_row_count": 88,
            "warmup_site_count": 88,
            "npz_regenerated_byte_equality": True,
            "warmup_regenerated_byte_equality": True,
            "manifest_regenerated_byte_equality": True,
            "checkpoint_identity_revalidated": True,
            "numpy_torch_parity_recomputed": True,
            "warmup_projection_recomputed": True,
            "history_projection": list(
                authority.PHASE3_OVERLAY_HISTORY_PROJECTION
            ),
            "panel_projection": list(authority.PHASE3_OVERLAY_PANEL_PROJECTION),
            "projection_contains_chlorophyll": False,
            "projection_contains_target": False,
            "opened_outcome_path_count": 0,
            "opened_target_path_count": 0,
            "writes_performed": False,
        },
        "sealed_batch_contract_sha256": layout["contract_sha256"],
        "expected_artifact_paths_sha256": authority._sha256_bytes(
            authority._canonical_json_bytes(list(layout["expected_paths"]))
        ),
        "expected_publication_order_sha256": authority._sha256_bytes(
            authority._canonical_json_bytes(list(layout["publication_order"]))
        ),
        "sealed_runner_source_record": source_record(
            "src/experiments/run_closure_benchmark.py"
        ),
        "sealed_context_builder_source_record": source_record(
            "src/experiments/closure_phase3_context.py"
        ),
        "sealed_component_source_records": [
            source_record(f"src/experiments/component_{index}.py")
            for index in range(10)
        ],
        "sealed_support_source_records": [
            source_record(f"src/experiments/support_{index}.py")
            for index in range(3)
        ],
        "sealed_runtime_environment_record": {"python": "/usr/bin/python3"},
        "dvc_policy": {
            "direct_git_artifact_paths": direct,
            "dvc_pointer_paths": [f"{path}.dvc" for path in heavy],
            "heavy_artifact_paths": heavy,
            "dvc_add_after_success_only": True,
            "dvc_push_after_audit_only": True,
            "implicit_dvc_forbidden": True,
        },
    }
    activation.parent.mkdir(parents=True)

    def write_activation() -> None:
        activation.write_bytes(authority._canonical_json_bytes(payload))

    observed: list[tuple[Path, set[Path]]] = []

    def topology_adapter(
        value: Mapping[str, Any],
        *,
        manifest_path: Path,
        staged_paths: set[Path],
        repo_root: Path,
        physical_payload: bytes,
    ) -> None:
        assert dict(value) == payload
        assert repo_root == tmp_path
        assert physical_payload == authority._canonical_json_bytes(payload)
        observed.append((manifest_path, staged_paths))

    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_e0_u_activation_staged_topology",
        topology_adapter,
    )
    write_activation()
    findings = validate_experiment_manifests(
        staged_paths={activation},
        artifacts=[],
        max_hash_bytes=0,
        verify_manifest_inputs=False,
    )
    assert not has_failing_findings(findings), "\n".join(
        f"{finding.level}:{finding.check}:{finding.message}" for finding in findings
    )
    assert not any(finding.level == "warn" for finding in findings)
    assert observed == [(activation, {activation})]
    assert any(
        "passed without an outputs list" in finding.message for finding in findings
    )

    payload["sealed_runner_source_record"]["mode"] = 0o600
    write_activation()
    findings = validate_experiment_manifests(
        staged_paths={activation},
        artifacts=[],
        max_hash_bytes=0,
        verify_manifest_inputs=False,
    )
    assert has_failing_findings(findings)
    assert any("schema const rejected" in finding.message for finding in findings)


def test_closure_e0_u_final_batch_uses_exact53_transaction_and_covers_reports(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.experiments import closure_e0_u_authority as authority
    from src.experiments import run_closure_benchmark as runner

    monkeypatch.chdir(tmp_path)
    expected, formats, direct, heavy, pointers = (
        precommit_artifacts._closure_e0_u_final_layout()
    )
    assert len(expected) == 52
    assert len(direct) == 48
    assert len(heavy) == len(pointers) == 4
    assert all(formats[path] == "parquet" for path in heavy)

    for index, path in enumerate(direct):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"direct-{index}:{path.as_posix()}\n".encode())
    for index, (output_path, pointer_path) in enumerate(
        zip(heavy, pointers, strict=True)
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_payload = f"parquet-{index}:{output_path.as_posix()}\n".encode()
        output_path.write_bytes(output_payload)
        pointer_path.write_text(
            "outs:\n"
            f"- md5: {hashlib.md5(output_payload, usedforsecurity=False).hexdigest()}\n"
            f"  size: {len(output_payload)}\n"
            "  hash: md5\n"
            f"  path: {output_path.name}\n",
            encoding="utf-8",
        )
    hardlink_cache = tmp_path / "synthetic-dvc-cache-object"
    os.link(heavy[0], hardlink_cache)
    heavy[0].chmod(0o444)
    assert heavy[0].stat().st_nlink == 2

    execution_id = "closure-e0-u-final-test"
    manifest_path = precommit_artifacts.CLOSURE_E0_U_FINAL_BENCHMARK_MANIFEST_PATH
    e1_paths = next(
        stage.output_paths for stage in runner.BATCH_STAGES if stage.stage_id == "E1"
    )
    manifest_payload = {
        "schema_version": "closure_e1_benchmark_manifest_v1",
        "execution_id": execution_id,
        "rng_seed": runner.RNG_SEED,
        "model_ids": list(runner.MODEL_IDS),
        "registered_seed_slots": list(runner.REGISTERED_SEEDS),
        "model_availability": dict(runner.CURRENT_MODEL_AVAILABILITY),
        "prediction_row_count": runner.LOCKED_PREDICTION_ROW_COUNT,
        "metric_row_count": 1,
        "comparison_row_count": 1,
        "prediction_sha256": "a" * 64,
        "metrics_sha256": "b" * 64,
        "comparisons_sha256": "c" * 64,
        "output_paths": list(e1_paths),
        "evaluation_refit_performed": False,
        "failed_model_replacement_performed": False,
        "silent_row_deletion_performed": False,
        "manifest_last": True,
    }
    manifest_path.write_bytes(runner._canonical_json_bytes(manifest_payload))

    access_log = precommit_artifacts.CLOSURE_E0_U_OUTCOME_ACCESS_LOG_PATH
    access_log.parent.mkdir(parents=True, exist_ok=True)
    access_log_payload = authority._canonical_json_bytes(
        {
            "event": "sealed_outcome_context_opened",
            "execution_id": execution_id,
            "experiment_id": authority.EXPERIMENT_ID,
            "gate": authority.GATE,
            "one_shot_consumed": True,
            "outcome_access_authorized": True,
            "schema_version": authority.ACCESS_LOG_SCHEMA_VERSION,
        }
    )
    access_log.write_bytes(access_log_payload)

    monkeypatch.setattr(
        precommit_artifacts,
        "_load_closure_e0_u_final_activation_authority",
        lambda *, repo_root: {"execution_id": execution_id},
    )
    observed_scopes: list[dict[str, str]] = []

    def validate_git_scope(
        *, expected_scope: Mapping[str, str], repo_root: Path
    ) -> None:
        assert repo_root == tmp_path
        assert len(expected_scope) == 53
        assert sum(status == "A" for status in expected_scope.values()) == 52
        assert sum(status == "M" for status in expected_scope.values()) == 1
        assert expected_scope[access_log.as_posix()] == "M"
        observed_scopes.append(dict(expected_scope))

    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_e0_u_final_git_scope",
        validate_git_scope,
    )
    staged_paths = {*direct, *pointers, access_log}

    def validate(paths: set[Path] = staged_paths):
        staged_status = "\n".join(
            f"{'M' if path == access_log else 'A'}\t{path.as_posix()}"
            for path in sorted(paths, key=Path.as_posix)
        )
        return precommit_artifacts.reproducibility_checks(
            staged_status=staged_status,
            selected_dvc_paths=list(heavy),
            artifacts=[],
            max_manifest_hash_bytes=0,
            verify_manifest_inputs=False,
        )

    findings = validate()
    assert not has_failing_findings(findings)
    assert not any(finding.level == "warn" for finding in findings)
    assert len(observed_scopes) == 2
    assert observed_scopes[0] == observed_scopes[1]
    assert any("final exact53 staging" in finding.message for finding in findings)
    assert any("52 output record(s)" in finding.message for finding in findings)
    assert not any(
        "not listed in any experiment manifest output" in finding.message
        for finding in findings
    )

    extra = Path("reports/closure_v1/09_planning/unsealed_extra.json")
    extra.write_text("{}\n", encoding="utf-8")
    findings = validate(staged_paths | {extra})
    assert has_failing_findings(findings)
    assert any("staging is not exact53" in finding.message for finding in findings)

    heavy[0].chmod(0o600)
    findings = validate()
    assert has_failing_findings(findings)
    assert any("DVC output identity is unsafe" in finding.message for finding in findings)
    heavy[0].chmod(0o444)

    pointer_payload = pointers[0].read_bytes()
    pointers[0].write_bytes(pointer_payload.replace(b"- md5: ", b"- md5: 0", 1))
    findings = validate()
    assert has_failing_findings(findings)
    assert any("DVC pointer" in finding.message for finding in findings)
    pointers[0].write_bytes(pointer_payload)

    access_log.write_bytes(access_log_payload + access_log_payload)
    findings = validate()
    assert has_failing_findings(findings)
    assert any("outcome access log" in finding.message for finding in findings)

    recovery_execution_id = (
        precommit_artifacts.CLOSURE_PHASE3_RECOVERY_2_ATTEMPT_3_EXECUTION_ID
    )
    recovery_log = authority._recovery_2_access_log_payload(recovery_execution_id)
    assert len(recovery_log) == 1_237
    assert len(recovery_log.splitlines()) == 3
    assert hashlib.sha256(recovery_log).hexdigest() == (
        precommit_artifacts.CLOSURE_PHASE3_RECOVERY_2_FINAL_LOG_SHA256
    )
    access_log.write_bytes(recovery_log)
    manifest_payload["execution_id"] = recovery_execution_id
    manifest_path.write_bytes(runner._canonical_json_bytes(manifest_payload))
    monkeypatch.setattr(
        precommit_artifacts,
        "_load_closure_e0_u_final_activation_authority",
        lambda *, repo_root: {
            "schema_version": "closure_e0_u_recovery_2_activation_v1",
            "execution_id": recovery_execution_id,
        },
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_2_guards",
        lambda **_kwargs: ((1, 2, 0o600, 1, 0), (1, 3, 0o600, 1, 0)),
    )
    findings = validate()
    assert not has_failing_findings(findings)
    access_log.write_bytes(recovery_log[:-1])
    assert has_failing_findings(validate())


def test_closure_development_runtime_lock_is_an_exact_authoritative_manifest() -> None:
    path = CLOSURE_DEVELOPMENT_RUNTIME_LOCK_PATH

    assert is_experiment_manifest_path(path)
    assert not is_report_artifact_path(path)
    assert not is_experiment_manifest_path(
        Path("reports/other/development_runtime_lock.json")
    )


def test_closure_development_runtime_lock_uses_strict_prepublication_validator(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lock = CLOSURE_DEVELOPMENT_RUNTIME_LOCK_PATH
    lock.parent.mkdir(parents=True)
    lock.write_text("{}\n", encoding="utf-8")

    def valid_loader(
        lock_path: Path,
        lock_schema: Path,
        *,
        require_published: bool,
        require_physical_artifacts: bool,
    ) -> tuple[dict[str, object], dict[str, object]]:
        assert lock_path == lock
        assert lock_schema == CLOSURE_DEVELOPMENT_RUNTIME_LOCK_SCHEMA
        assert require_published is False
        assert require_physical_artifacts is True
        return {}, {
            "lock_version": "closure_development_runtime_lock_v1",
            "status": "locked",
            "publication_verified": False,
            "physical_artifacts_verified": True,
            "canonical_origin_identity_verified": True,
            "dvc_remote_verified_at_lock": True,
            "dvc_remote_verified": True,
            "locked_parent_published_at_lock": True,
            "payload_development_fit_authorized": True,
            "development_fit_authorized": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "fit_authorized": False,
            "future_outcomes_accessed": False,
        }

    monkeypatch.setattr(
        "src.experiments.closure_development_runtime_lock."
        "load_and_validate_development_runtime_lock",
        valid_loader,
    )
    findings = validate_experiment_manifests(
        staged_paths={lock},
        artifacts=[],
        max_hash_bytes=0,
        verify_manifest_inputs=False,
    )

    assert not has_failing_findings(findings)
    assert not any(finding.level == "warn" for finding in findings)

    def invalid_loader(*_: object, **__: object) -> tuple[dict[str, object], dict[str, object]]:
        raise ValueError("sealed hash drift")

    monkeypatch.setattr(
        "src.experiments.closure_development_runtime_lock."
        "load_and_validate_development_runtime_lock",
        invalid_loader,
    )
    findings = validate_experiment_manifests(
        staged_paths={lock},
        artifacts=[],
        max_hash_bytes=0,
        verify_manifest_inputs=False,
    )

    assert has_failing_findings(findings)
    assert any("sealed hash drift" in finding.message for finding in findings)


def test_closure_protocol_lock_validation_checks_seal_and_companion_hashes(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    companion = Path("reports/closure_v1/00_protocol/environment.json")
    companion.parent.mkdir(parents=True)
    companion.write_text('{"python": "3.14"}\n', encoding="utf-8")
    script = Path("src/experiments/lock_closure_protocol.py")
    script.parent.mkdir(parents=True)
    script.write_text("print('lock')\n", encoding="utf-8")
    lock = Path("reports/closure_v1/00_protocol/protocol_lock.json")
    payload = _closure_protocol_lock_payload(companion, script)
    lock.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    findings = validate_experiment_manifests(
        staged_paths={companion, lock},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert not has_failing_findings(findings)

    companion.write_text('{"python": "changed"}\n', encoding="utf-8")
    findings = validate_experiment_manifests(
        staged_paths={companion, lock},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert has_failing_findings(findings)
    assert any("SHA-256 changed" in finding.message for finding in findings)

    companion.write_text('{"python": "3.14"}\n', encoding="utf-8")
    payload["status"] = "completed"
    payload["future_outcomes_accessed"] = True
    lock.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    findings = validate_experiment_manifests(
        staged_paths={companion, lock},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert has_failing_findings(findings)
    assert any("expected `locked`" in finding.message for finding in findings)
    assert any("future_outcomes_accessed=false" in finding.message for finding in findings)


def test_closure_common_origin_manifest_adapts_strict_dialect(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, _, _ = _write_closure_common_origin_fixture(tmp_path)

    findings = validate_experiment_manifests(
        staged_paths={manifest},
        artifacts=[],
        max_hash_bytes=0,
        verify_manifest_inputs=False,
    )

    assert not has_failing_findings(findings)
    assert not any(finding.level == "warn" for finding in findings)


def test_closure_common_origin_manifest_dialect_is_exact_path_only(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _, payload, _ = _write_closure_common_origin_fixture(tmp_path)
    manifest = Path("reports/other/common_origin_manifest.json")
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    assert not is_experiment_manifest_path(manifest)

    findings = validate_experiment_manifests(
        staged_paths={manifest},
        artifacts=[],
        max_hash_bytes=0,
        verify_manifest_inputs=False,
    )

    assert has_failing_findings(findings)
    assert any("not listed in any experiment manifest" in finding.message for finding in findings)


def test_closure_common_origin_manifest_rejects_contract_mutations(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, payload, _ = _write_closure_common_origin_fixture(tmp_path)
    mutations = (
        ("manifest_version", "wrong_version", "manifest version"),
        ("status", "ready", "`status=\"completed\"`"),
        ("experiment_id", "other", "`experiment_id=\"closure_v1\"`"),
        ("future_outcomes_accessed", True, "`future_outcomes_accessed=false`"),
        ("target_values_projected", ["target"], "`target_values_projected=[]`"),
        (
            "target_parquet_semantically_opened",
            True,
            "`target_parquet_semantically_opened=false`",
        ),
        (
            "post_cutoff_target_rows_materialized",
            False,
            "`post_cutoff_target_rows_materialized=0`",
        ),
        (
            "target_availability_used_for_origin_selection",
            True,
            "`target_availability_used_for_origin_selection=false`",
        ),
    )

    for field, value, expected_message in mutations:
        mutated = deepcopy(payload)
        mutated[field] = value
        manifest.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
        findings = validate_experiment_manifests(
            staged_paths={manifest},
            artifacts=[],
            max_hash_bytes=0,
            verify_manifest_inputs=False,
        )

        assert has_failing_findings(findings), field
        assert any(expected_message in finding.message for finding in findings), field


def test_closure_common_origin_manifest_requires_all_strict_record_sections(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, payload, _ = _write_closure_common_origin_fixture(tmp_path)

    for section in ("code", "configs", "source_inputs", "parent_artifacts"):
        mutated = deepcopy(payload)
        mutated[section] = []
        manifest.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
        findings = validate_experiment_manifests(
            staged_paths={manifest},
            artifacts=[],
            max_hash_bytes=0,
            verify_manifest_inputs=False,
        )

        assert has_failing_findings(findings), section
        assert any(
            f"non-empty `{section}` list" in finding.message for finding in findings
        ), section


def test_closure_common_origin_manifest_requires_sealed_execution_record(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, payload, _ = _write_closure_common_origin_fixture(tmp_path)
    execution = payload["execution"]
    assert isinstance(execution, dict)

    for field, value in (
        ("future_outcomes_semantically_decoded", True),
        ("reproduction_command", ["python", "wrong.py"]),
    ):
        mutated = deepcopy(payload)
        mutated_execution = cast(dict[str, Any], mutated["execution"])
        mutated_execution[field] = value
        manifest.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
        findings = validate_experiment_manifests(
            staged_paths={manifest},
            artifacts=[],
            max_hash_bytes=0,
            verify_manifest_inputs=False,
        )

        assert has_failing_findings(findings), field
        assert any("invalid sealed execution record" in finding.message for finding in findings)


def test_closure_common_origin_manifest_rejects_exact_provenance_drift(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, payload, _ = _write_closure_common_origin_fixture(tmp_path)
    mutations: list[tuple[str, dict[str, object], str]] = []

    wrong_output = Path("data/closure_v1/wrong.parquet")
    wrong_output.parent.mkdir(parents=True, exist_ok=True)
    wrong_output.write_text("wrong\n", encoding="utf-8")
    mutated = deepcopy(payload)
    mutated["output"] = _manifest_record(wrong_output)
    mutations.append(("output", mutated, "exactly the output"))

    for section in ("code", "configs", "source_inputs", "parent_artifacts"):
        mutated = deepcopy(payload)
        records = mutated[section]
        assert isinstance(records, list)
        records.reverse()
        mutations.append((section, mutated, f"`{section}` paths"))

    mutated = deepcopy(payload)
    sources = cast(list[dict[str, Any]], mutated["source_inputs"])
    sources[0]["hash_source"] = "unlocked"
    mutations.append(("source_role", mutated, "source roles/hash_source"))

    mutated = deepcopy(payload)
    parents = cast(list[dict[str, Any]], mutated["parent_artifacts"])
    parents[0]["role"] = "wrong"
    mutations.append(("parent_role", mutated, "parent roles"))

    mutated = deepcopy(payload)
    assignment = cast(dict[str, Any], mutated["assignment"])
    assignment["development_locations"] = 352
    mutations.append(("assignment", mutated, "assignment provenance"))

    for label, mutated_payload, expected_message in mutations:
        manifest.write_text(json.dumps(mutated_payload, indent=2) + "\n", encoding="utf-8")
        findings = validate_experiment_manifests(
            staged_paths={manifest},
            artifacts=[],
            max_hash_bytes=0,
            verify_manifest_inputs=False,
        )

        assert has_failing_findings(findings), label
        assert any(expected_message in finding.message for finding in findings), label


def test_common_origin_pointer_always_discovers_completion_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, _, _ = _write_closure_common_origin_fixture(tmp_path)
    pointer = dvc_pointer_path(Path("data/closure_v1/common_origin_manifest.parquet"))
    pointer.write_text("outs:\n- md5: abc\n  path: common_origin_manifest.parquet\n", encoding="utf-8")

    assert discover_relevant_manifest_paths({pointer}) == [manifest]


def test_expert_state_pointer_always_discovers_completion_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = CLOSURE_EXPERT_STATE_MANIFEST_PATH
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}\n", encoding="utf-8")
    pointer = dvc_pointer_path(CLOSURE_EXPERT_STATE_OUTPUT_PATH)
    pointer.parent.mkdir(parents=True)
    pointer.write_text(
        "outs:\n- md5: abc\n  path: expert_no_current_state.parquet\n",
        encoding="utf-8",
    )

    assert discover_relevant_manifest_paths({pointer}) == [manifest]


def test_exact_expert_manifest_runs_strict_bundle_and_semantic_validator(
    monkeypatch,
) -> None:
    calls: list[bool] = []

    def valid(runtime: object, *, require_physical_artifact: bool) -> dict[str, object]:
        del runtime
        calls.append(require_physical_artifact)
        return {
            "completion_records": [
                {"path": CLOSURE_EXPERT_STATE_MANIFEST_PATH.as_posix()}
            ]
        }

    monkeypatch.setattr(
        "src.experiments.closure_development_runtime_lock.expert_state_lock_record",
        valid,
    )
    findings = validate_closure_expert_state_manifest(
        CLOSURE_EXPERT_STATE_MANIFEST_PATH
    )
    assert calls == [True]
    assert not has_failing_findings(findings)

    monkeypatch.setattr(
        "src.experiments.closure_development_runtime_lock.expert_state_lock_record",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("semantic drift")),
    )
    findings = validate_closure_expert_state_manifest(
        CLOSURE_EXPERT_STATE_MANIFEST_PATH
    )
    assert has_failing_findings(findings)
    assert any("semantic drift" in finding.message for finding in findings)


def test_closure_common_origin_manifest_requires_exact_generating_script(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, payload, _ = _write_closure_common_origin_fixture(tmp_path)
    code_records = payload["code"]
    assert isinstance(code_records, list)
    builder_record = deepcopy(code_records[0])

    for code in (
        code_records[1:],
        [builder_record, builder_record, *code_records[1:]],
    ):
        mutated = deepcopy(payload)
        mutated["code"] = code
        manifest.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
        findings = validate_experiment_manifests(
            staged_paths={manifest},
            artifacts=[],
            max_hash_bytes=0,
            verify_manifest_inputs=False,
        )

        assert has_failing_findings(findings)
        assert any(
            "exactly one generating-script record" in finding.message
            for finding in findings
        )


def test_closure_common_origin_manifest_forces_all_record_hash_checks(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, payload, records = _write_closure_common_origin_fixture(tmp_path)

    for record_path in records:
        original = record_path.read_text(encoding="utf-8")
        record_path.write_text(original + "changed\n", encoding="utf-8")
        findings = validate_experiment_manifests(
            staged_paths={manifest},
            artifacts=[],
            max_hash_bytes=0,
            verify_manifest_inputs=False,
        )

        assert has_failing_findings(findings), record_path
        assert any(
            finding.path == record_path.as_posix()
            and "SHA-256 changed" in finding.message
            for finding in findings
        ), record_path
        record_path.write_text(original, encoding="utf-8")

    mutated = deepcopy(payload)
    mutated["output"] = None
    manifest.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
    findings = validate_experiment_manifests(
        staged_paths={manifest},
        artifacts=[],
        max_hash_bytes=0,
        verify_manifest_inputs=False,
    )
    assert has_failing_findings(findings)
    assert any("output record is missing a valid path" in finding.message for finding in findings)


def test_experiment_manifest_validation_checks_output_and_script_hashes(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    report = Path("reports/pipe/report.csv")
    report.parent.mkdir(parents=True)
    report.write_text("value\n1\n", encoding="utf-8")
    script = Path("src/experiments/example.py")
    script.parent.mkdir(parents=True)
    script.write_text("print('ok')\n", encoding="utf-8")
    manifest = Path("reports/pipe/report_manifest.json")
    manifest.write_text(
        (
            "{\n"
            '  "status": "completed",\n'
            f'  "outputs": [{_manifest_record(report)!r}],\n'
            f'  "script": {_manifest_record(script)!r},\n'
            '  "inputs": []\n'
            "}\n"
        ).replace("'", '"'),
        encoding="utf-8",
    )

    findings = validate_experiment_manifests(
        staged_paths={report, manifest},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert not has_failing_findings(findings)

    report.write_text("value\n2\n", encoding="utf-8")

    findings = validate_experiment_manifests(
        staged_paths={report, manifest},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert has_failing_findings(findings)
    assert any("SHA-256 changed" in finding.message for finding in findings)


def test_experiment_manifest_validation_checks_directory_records(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = Path("reports/pipe/scores.parquet")
    output_dir.mkdir(parents=True)
    part = output_dir / "part-000.parquet"
    part.write_text("score\n", encoding="utf-8")
    script = Path("src/experiments/example.py")
    script.parent.mkdir(parents=True)
    script.write_text("print('ok')\n", encoding="utf-8")
    total_bytes, directory_hash = sha256_directory(output_dir)
    manifest = Path("reports/pipe/scores_manifest.json")
    manifest.write_text(
        json.dumps(
            {
                "status": "completed",
                "outputs": [
                    {
                        "path": output_dir.as_posix(),
                        "type": "directory",
                        "bytes": total_bytes,
                        "sha256": directory_hash,
                    }
                ],
                "script": _manifest_record(script),
                "inputs": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    findings = validate_experiment_manifests(
        staged_paths={manifest},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert not has_failing_findings(findings)


def test_experiment_manifest_validation_requires_staged_reports_to_be_listed(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    report = Path("reports/pipe/unlisted.csv")
    report.parent.mkdir(parents=True)
    report.write_text("value\n1\n", encoding="utf-8")

    findings = validate_experiment_manifests(
        staged_paths={report},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert has_failing_findings(findings)
    assert any("not listed in any experiment manifest" in finding.message for finding in findings)


def test_data_governance_reports_are_not_experiment_artifacts() -> None:
    assert not is_report_artifact_path(Path("reports/data/PANEL_REPORT_v0.md"))
    assert not is_report_artifact_path(Path("reports/data/waterbody_crosswalk_candidates_report.md"))
    assert is_report_artifact_path(Path("reports/pipe_grud/pipe_sequence_report.md"))


def test_promotion_manifests_are_not_experiment_manifests() -> None:
    path = Path("reports/pipe_grud/pipe_grud_promotion_manifest.json")

    assert not is_experiment_manifest_path(path)
    assert not is_report_artifact_path(path)


def test_freeze_freshness_requires_freeze_outputs_for_data_pipeline_changes() -> None:
    findings = validate_freeze_freshness([("M", Path("src/data/build_panel.py"))])

    assert has_failing_findings(findings)

    findings = validate_freeze_freshness(
        [
            ("M", Path("src/data/build_panel.py")),
            ("M", Path("data/freeze/derived_file_manifest_v0.csv")),
            ("M", Path("data/freeze/data_freeze_manifest_v0.json")),
            ("M", Path("data/freeze/DATA_FREEZE.md")),
        ]
    )

    assert not has_failing_findings(findings)


def test_dvc_inventory_only_change_does_not_warn_about_freeze() -> None:
    findings = validate_freeze_freshness([("M", Path("configs/dvc_artifacts.yaml"))])

    assert not has_failing_findings(findings)
    assert not any(finding.level == "warn" for finding in findings)
    assert any("data-freeze regeneration is not required" in finding.message for finding in findings)


def test_freeze_documentation_update_does_not_require_derived_manifest() -> None:
    findings = validate_freeze_freshness(
        [
            ("M", Path("src/data/freeze.py")),
            ("M", Path("data/freeze/data_freeze_manifest_v0.json")),
            ("M", Path("data/freeze/DATA_FREEZE.md")),
        ]
    )

    assert not has_failing_findings(findings)
    assert any("derived file hashes are not required" in finding.message for finding in findings)


def test_reproducibility_checks_validate_dvc_pointer_structure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    pointer = Path("data/example.parquet.dvc")
    pointer.parent.mkdir(parents=True)
    pointer.write_text(
        "outs:\n"
        "- md5: abc123\n"
        "  size: 10\n"
        "  hash: md5\n"
        "  path: example.parquet\n",
        encoding="utf-8",
    )

    findings = reproducibility_checks(
        staged_status="A\tdata/example.parquet.dvc\n",
        selected_dvc_paths=[],
        artifacts=[],
        max_manifest_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert not has_failing_findings(findings)


def _closure_phase3_h_args() -> Any:
    return precommit_artifacts.argparse.Namespace(
        manifest=DEFAULT_DVC_MANIFEST,
        dvc_bin=None,
        report=None,
        target=[],
        defer_dvc_target=[],
        register_anfis_ablation_model_family=False,
        jobs=None,
        yes=False,
        dry_run=False,
        no_push=True,
        allow_unmanaged=True,
        skip_publication_check=False,
        max_manifest_hash_bytes=(
            precommit_artifacts.DEFAULT_MAX_MANIFEST_HASH_BYTES
        ),
        verify_manifest_inputs=False,
    )


def _closure_phase3_h_short_status(*, staged: bool) -> str:
    expected = precommit_artifacts._closure_phase3_h_expected_short_scope(
        staged=staged
    )
    return "\n".join(
        f"{status_code} {path}" for path, status_code in sorted(expected.items())
    )


def _closure_phase3_h_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE3_H_STAGED_SCOPE.items()
        )
    )


def _closure_phase3_h_amend_short_status(*, staged: bool) -> str:
    expected = (
        precommit_artifacts._closure_phase3_h_amend_expected_short_scope(
            staged=staged
        )
    )
    return "\n".join(
        f"{status_code} {path}"
        for path, status_code in sorted(expected.items())
    )


def _closure_phase3_h_amend_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE3_H_AMEND_STAGED_SCOPE.items()
        )
    )


def _closure_phase3_h_import_repair_short_status(*, staged: bool) -> str:
    expected = (
        precommit_artifacts._closure_phase3_h_import_repair_expected_short_scope(
            staged=staged
        )
    )
    return "\n".join(
        f"{status_code} {path}" for path, status_code in sorted(expected.items())
    )


def _closure_phase3_h_import_repair_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE3_H_IMPORT_REPAIR_STAGED_SCOPE.items()
        )
    )


def _closure_phase3_h_authority_rewrite_short_status(*, staged: bool) -> str:
    expected = (
        precommit_artifacts._closure_phase3_h_authority_rewrite_expected_short_scope(
            staged=staged
        )
    )
    return "\n".join(
        f"{status_code} {path}" for path, status_code in sorted(expected.items())
    )


def _closure_phase3_h_authority_rewrite_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_STAGED_SCOPE.items()
        )
    )


def _closure_phase3_h_runner_rewrite_short_status(*, staged: bool) -> str:
    expected = (
        precommit_artifacts._closure_phase3_h_runner_rewrite_expected_short_scope(
            staged=staged
        )
    )
    return "\n".join(
        f"{status_code} {path}" for path, status_code in sorted(expected.items())
    )


def _closure_phase3_h_runner_rewrite_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_STAGED_SCOPE.items()
        )
    )


def _closure_phase3_recovery_short_status(*, staged: bool) -> str:
    expected = precommit_artifacts._closure_phase3_recovery_expected_short_scope(
        staged=staged
    )
    return "\n".join(
        f"{status_code} {path}" for path, status_code in sorted(expected.items())
    )


def _closure_phase3_recovery_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_STAGED_SCOPE.items()
        )
    )


def _closure_phase3_recovery_p2_short_status(*, staged: bool) -> str:
    expected = (
        precommit_artifacts._closure_phase3_recovery_p2_expected_short_scope(
            staged=staged
        )
    )
    return "\n".join(
        f"{status_code} {path}" for path, status_code in sorted(expected.items())
    )


def _closure_phase3_recovery_p2_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_STAGED_SCOPE.items()
        )
    )


def _closure_phase3_recovery_u2_short_status(*, staged: bool) -> str:
    expected = (
        precommit_artifacts._closure_phase3_recovery_u2_expected_short_scope(
            staged=staged
        )
    )
    return "\n".join(
        f"{status_code} {path}" for path, status_code in sorted(expected.items())
    )


def _closure_phase3_recovery_u2_name_status() -> str:
    return (
        "A\t"
        + precommit_artifacts.CLOSURE_E0_U_RECOVERY_ACTIVATION_PATH.as_posix()
    )


def _closure_phase3_recovery_2_h3_short_status(*, staged: bool) -> str:
    expected = (
        precommit_artifacts._closure_phase3_recovery_2_h3_expected_short_scope(
            staged=staged
        )
    )
    return "\n".join(
        f"{status_code} {path}" for path, status_code in sorted(expected.items())
    )


def _closure_phase3_recovery_2_h3_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_2_STAGED_SCOPE.items()
        )
    )


def _closure_phase3_recovery_2_p3_short_status(*, staged: bool) -> str:
    expected = (
        precommit_artifacts._closure_phase3_recovery_2_p3_expected_short_scope(
            staged=staged
        )
    )
    return "\n".join(
        f"{status_code} {path}" for path, status_code in sorted(expected.items())
    )


def _closure_phase3_recovery_2_p3_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_2_STAGED_SCOPE.items()
        )
    )


def _closure_phase3_recovery_2_u3_short_status(*, staged: bool) -> str:
    expected = (
        precommit_artifacts._closure_phase3_recovery_2_u3_expected_short_scope(
            staged=staged
        )
    )
    return "\n".join(
        f"{status_code} {path}" for path, status_code in sorted(expected.items())
    )


def _closure_phase3_recovery_2_u3_name_status() -> str:
    return (
        "A\t"
        + precommit_artifacts.CLOSURE_E0_U_RECOVERY_2_ACTIVATION_PATH.as_posix()
    )


def _closure_phase3_h4_short_status(*, staged: bool) -> str:
    expected = precommit_artifacts._closure_phase3_final_expected_short_scope(
        h4=True,
        staged=staged,
    )
    return "\n".join(
        f"{status} {path}" for path, status in sorted(expected.items())
    )


def _closure_phase3_h4_name_status() -> str:
    return "\n".join(
        f"{status}\t{path}"
        for path, status in sorted(precommit_artifacts.CLOSURE_PHASE3_H4_STAGED_SCOPE.items())
    )


def _closure_phase3_recovery_ref_output(*args: str) -> str:
    u_commit = precommit_artifacts.CLOSURE_PHASE3_U_RECOVERY_COMMIT
    p_commit = precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_COMMIT
    h_commit = precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_COMMIT
    r_commit = precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT
    if args and args[0] == "rev-parse":
        return u_commit + "\n"
    if args == ("symbolic-ref", "--quiet", "HEAD"):
        return "refs/heads/main\n"
    if args == (
        "symbolic-ref",
        "--quiet",
        "refs/remotes/origin/HEAD",
    ):
        return "refs/remotes/origin/main\n"
    for commit, parent in (
        (u_commit, p_commit),
        (p_commit, h_commit),
        (h_commit, r_commit),
    ):
        if args == ("rev-list", "--parents", "-n", "1", commit):
            return f"{commit} {parent}\n"
    if args == (
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "--no-renames",
        "-r",
        h_commit,
    ):
        return _closure_phase3_h_name_status()
    if args == (
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "--no-renames",
        "-r",
        p_commit,
    ):
        return "\n".join(
            f"A\t{path}"
            for path in sorted(
                precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_SCOPE
            )
        )
    if args == (
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "--no-renames",
        "-r",
        u_commit,
    ):
        return (
            "A\t"
            + precommit_artifacts.CLOSURE_E0_U_ACTIVATION_PATH.as_posix()
            + "\n"
        )
    raise AssertionError(args)


def _closure_phase3_h_runner_rewrite_ref_output(*args: str) -> str:
    u_commit = precommit_artifacts.CLOSURE_PHASE3_U_RUNNER_REWRITE_COMMIT
    p_commit = precommit_artifacts.CLOSURE_PHASE3_P_RUNNER_REWRITE_COMMIT
    h_commit = precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_COMMIT
    r_commit = precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT
    if args and args[0] == "rev-parse":
        return u_commit + "\n"
    if args == ("symbolic-ref", "--quiet", "HEAD"):
        return "refs/heads/main\n"
    if args == (
        "symbolic-ref",
        "--quiet",
        "refs/remotes/origin/HEAD",
    ):
        return "refs/remotes/origin/main\n"
    for commit, parent in (
        (u_commit, p_commit),
        (p_commit, h_commit),
        (h_commit, r_commit),
    ):
        if args == ("rev-list", "--parents", "-n", "1", commit):
            return f"{commit} {parent}\n"
    if args == (
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "--no-renames",
        "-r",
        h_commit,
    ):
        return _closure_phase3_h_name_status()
    if args == (
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "--no-renames",
        "-r",
        p_commit,
    ):
        return "\n".join(
            f"A\t{path}"
            for path in sorted(
                precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_SCOPE
            )
        )
    if args == (
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "--no-renames",
        "-r",
        u_commit,
    ):
        return f"A\t{precommit_artifacts.CLOSURE_E0_U_ACTIVATION_PATH.as_posix()}\n"
    raise AssertionError(args)


def _closure_phase3_h_authority_rewrite_ref_output(*args: str) -> str:
    p_commit = precommit_artifacts.CLOSURE_PHASE3_P_AUTHORITY_REWRITE_COMMIT
    h_commit = precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_COMMIT
    r_commit = precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT
    if args and args[0] == "rev-parse":
        return p_commit + "\n"
    if args == ("symbolic-ref", "--quiet", "HEAD"):
        return "refs/heads/main\n"
    if args == (
        "symbolic-ref",
        "--quiet",
        "refs/remotes/origin/HEAD",
    ):
        return "refs/remotes/origin/main\n"
    if args == ("rev-list", "--parents", "-n", "1", p_commit):
        return f"{p_commit} {h_commit}\n"
    if args == ("rev-list", "--parents", "-n", "1", h_commit):
        return f"{h_commit} {r_commit}\n"
    if args == (
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "--no-renames",
        "-r",
        h_commit,
    ):
        return _closure_phase3_h_name_status()
    if args == (
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "--no-renames",
        "-r",
        p_commit,
    ):
        return "\n".join(
            f"A\t{path}"
            for path in sorted(
                precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_SCOPE
            )
        )
    raise AssertionError(args)


def _closure_phase3_h_ref_output(*args: str) -> str:
    if args[:2] == ("rev-parse", "HEAD^{commit}"):
        return precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT + "\n"
    if args and args[0] == "rev-parse":
        return precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT + "\n"
    if args == ("symbolic-ref", "--quiet", "HEAD"):
        return "refs/heads/main\n"
    if args == (
        "symbolic-ref",
        "--quiet",
        "refs/remotes/origin/HEAD",
    ):
        return "refs/remotes/origin/main\n"
    raise AssertionError(args)


def _closure_phase3_h_amend_ref_output(*args: str) -> str:
    if args == ("rev-parse", "HEAD^1^{commit}"):
        return precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT + "\n"
    if args and args[0] == "rev-parse":
        return precommit_artifacts.CLOSURE_PHASE3_H_HISTORICAL_COMMIT + "\n"
    if args == ("symbolic-ref", "--quiet", "HEAD"):
        return "refs/heads/main\n"
    if args == (
        "symbolic-ref",
        "--quiet",
        "refs/remotes/origin/HEAD",
    ):
        return "refs/remotes/origin/main\n"
    raise AssertionError(args)


def _closure_phase3_h_import_repair_ref_output(*args: str) -> str:
    h_commit = precommit_artifacts.CLOSURE_PHASE3_H_IMPORT_REPAIR_COMMIT
    pre_import_h_commit = (
        precommit_artifacts.CLOSURE_PHASE3_H_PRE_IMPORT_REPAIR_COMMIT
    )
    p_commit = precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_COMMIT
    r_commit = precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT
    if args == ("rev-parse", "HEAD^{commit}") or args == (
        "rev-parse",
        "refs/heads/main^{commit}",
    ):
        return h_commit + "\n"
    if args in {
        ("rev-parse", "refs/remotes/origin/main^{commit}"),
        ("rev-parse", "refs/remotes/origin/HEAD^{commit}"),
    }:
        return h_commit + "\n"
    if args == ("symbolic-ref", "--quiet", "HEAD"):
        return "refs/heads/main\n"
    if args == (
        "symbolic-ref",
        "--quiet",
        "refs/remotes/origin/HEAD",
    ):
        return "refs/remotes/origin/main\n"
    if args == ("rev-list", "--parents", "-n", "1", h_commit):
        return f"{h_commit} {r_commit}\n"
    if args == (
        "rev-list",
        "--parents",
        "-n",
        "1",
        pre_import_h_commit,
    ):
        return f"{pre_import_h_commit} {r_commit}\n"
    if args == ("rev-list", "--parents", "-n", "1", p_commit):
        return f"{p_commit} {pre_import_h_commit}\n"
    if args == (
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "--no-renames",
        "-r",
        p_commit,
    ):
        return "\n".join(
            f"A\t{path}"
            for path in sorted(
                precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_SCOPE
            )
        )
    if args[:5] == ("ls-tree", "-r", "--full-tree", p_commit, "--"):
        assert tuple(args[5:]) == tuple(
            sorted(precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_SCOPE)
        )
        return "\n".join(
            f"100644 blob {'a' * 40}\t{path}"
            for path in sorted(
                precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_SCOPE
            )
        )
    raise AssertionError(args)


def test_closure_phase3_recovery_selector_binds_consumed_chain_and_exact14(
    monkeypatch,
) -> None:
    status = _closure_phase3_recovery_short_status(staged=False)
    expected_scope = {
        "configs/closure_v1/closure_e0_u_recovery_activation.schema.json": "A",
        "docs/closure_v1/E0_U_PHASE3_RECOVERY_BATCH.md": "A",
        "reports/closure_v1/00_protocol/closure_e0_u_attempt_1_failure.json": "A",
        "reports/closure_v1/00_protocol/locked_recovery_batch_command.txt": "A",
        "reports/closure_v1/00_protocol/outcome_access_log.jsonl": "M",
        "src/data/prepare_commit_artifacts.py": "M",
        "src/experiments/build_closure_e10_source_evidence.py": "M",
        "src/experiments/closure_e0_u_authority.py": "M",
        "src/experiments/lock_closure_e0_u_activation.py": "M",
        "src/experiments/run_closure_benchmark.py": "M",
        "tests/test_build_closure_e10_source_evidence.py": "M",
        "tests/test_closure_e0_u_activation_lock.py": "M",
        "tests/test_closure_e0_u_authority.py": "M",
        "tests/test_prepare_commit_artifacts.py": "M",
    }
    assert precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_STAGED_SCOPE == (
        expected_scope
    )
    assert sum(value == "M" for value in expected_scope.values()) == 10
    assert sum(value == "A" for value in expected_scope.values()) == 4
    assert precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_COMMIT == (
        "9e66478d7c071067a750e7dd9a6a318fa93a2c88"
    )
    assert precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_COMMIT == (
        "caaf2d6d0a00a31febeed89b54ea078b60d7f92a"
    )
    assert precommit_artifacts.CLOSURE_PHASE3_U_RECOVERY_COMMIT == (
        "4aecf19cd913b82a6a3d26669f09684e67efda8a"
    )
    assert precommit_artifacts.CLOSURE_PHASE3_RECOVERY_OUTCOME_LOG_BYTES == 256
    assert precommit_artifacts.CLOSURE_PHASE3_RECOVERY_OUTCOME_LOG_SHA256 == (
        "ae3e47dd6ad1f05cd79e6a494174f951f1c71fa9336514640bd4c15855c1b038"
    )
    assert precommit_artifacts.CLOSURE_PHASE3_RECOVERY_ATTEMPT_1_GUARD_DEVICE == 2069
    assert precommit_artifacts.CLOSURE_PHASE3_RECOVERY_ATTEMPT_1_GUARD_INODE == 80609290
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: _closure_phase3_recovery_ref_output(*args),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_log_identity",
        lambda **_kwargs: "sealed-log",
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_guard",
        lambda **_kwargs: (2069, 80609290, 0o600, 1, 0),
    )

    assert precommit_artifacts.closure_phase3_recovery_pre_stage_scope(
        status,
        "",
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="empty Git index",
    ):
        precommit_artifacts.closure_phase3_recovery_pre_stage_scope(
            status,
            "M\tsrc/data/prepare_commit_artifacts.py\n",
        )

    partial = status.replace(
        " M src/experiments/run_closure_benchmark.py\n", ""
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact14",
    ):
        precommit_artifacts.closure_phase3_recovery_pre_stage_scope(
            partial,
            "",
        )

    report_message = (
        "Staged report artifact is not listed in any experiment manifest output."
    )
    direct_paths = (
        precommit_artifacts.CLOSURE_PHASE3_RECOVERY_RECEIPT_PATH,
        precommit_artifacts.CLOSURE_PHASE3_RECOVERY_COMMAND_PATH,
    )
    findings = [
        precommit_artifacts.ReproducibilityFinding(
            "fail", "manifest", path.as_posix(), report_message
        )
        for path in direct_paths
    ]
    compensated = (
        precommit_artifacts._compensate_closure_phase3_recovery_manifest_findings(
            findings
        )
    )
    assert {finding.path for finding in compensated} == {
        path.as_posix() for path in direct_paths
    }
    assert all(finding.level == "ok" for finding in compensated)
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="not exact2",
    ):
        precommit_artifacts._compensate_closure_phase3_recovery_manifest_findings(
            findings[:1]
        )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="duplicated",
    ):
        precommit_artifacts._compensate_closure_phase3_recovery_manifest_findings(
            [*findings, findings[0]]
        )


def test_closure_phase3_recovery_p2_selector_is_exact7_and_h2_scoped(
    monkeypatch,
) -> None:
    h2_commit = "2" * 40
    calls: list[tuple[str, Any]] = []
    expected_paths = {
        (
            "reports/closure_v1/00_protocol/"
            "software_evidence_source_recovery_1/" + name
        ): "A"
        for name in (
            "end_to_end_report.md",
            "environment.json",
            "openapi.json",
            "openapi_contract_report.md",
            "public_tests.xml",
            "software_evidence_source_manifest.json",
            "test_report.md",
        )
    }
    assert precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_STAGED_SCOPE == (
        expected_paths
    )
    assert set(precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_PHYSICAL_MODES) == (
        set(expected_paths)
    )
    assert set(
        precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_PHYSICAL_MODES.values()
    ) == {0o600}

    def git_output(_root: Path, *args: str) -> str:
        if args == ("rev-parse", "HEAD^{commit}"):
            return h2_commit + "\n"
        if args == ("rev-list", "--parents", "-n", "1", h2_commit):
            return (
                h2_commit
                + " "
                + precommit_artifacts.CLOSURE_PHASE3_U_RECOVERY_COMMIT
                + "\n"
            )
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_h2_history",
        lambda **kwargs: calls.append(("history", kwargs)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_refs_at",
        lambda **kwargs: calls.append(("refs", kwargs)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_log_head_identity",
        lambda **kwargs: calls.append(("log", kwargs)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_guard",
        lambda **kwargs: calls.append(("guard", kwargs)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_post_h2_paths_absent",
        lambda **kwargs: calls.append(("future", kwargs)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase3_recovery_p2_bundle",
        lambda **kwargs: calls.append(("bundle", kwargs)),
    )
    status = _closure_phase3_recovery_p2_short_status(staged=False)
    assert precommit_artifacts.closure_phase3_recovery_p2_pre_stage_scope(
        status, ""
    )
    assert ("history", {"repo_root": Path("."), "h2_commit": h2_commit}) in calls
    assert any(label == "bundle" for label, _kwargs in calls)

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="empty Git index",
    ):
        precommit_artifacts.closure_phase3_recovery_p2_pre_stage_scope(
            status, "A\tunexpected\n"
        )
    partial = "\n".join(status.splitlines()[1:])
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact7A",
    ):
        precommit_artifacts.closure_phase3_recovery_p2_pre_stage_scope(
            partial, ""
        )


def test_closure_phase3_recovery_u2_selector_is_exact1_and_p2_scoped(
    monkeypatch,
) -> None:
    h2_commit = "2" * 40
    p2_commit = "3" * 40
    calls: list[tuple[str, Any]] = []
    assert precommit_artifacts.CLOSURE_PHASE3_U_RECOVERY_STAGED_SCOPE == {
        (
            "reports/closure_v1/00_protocol/"
            "closure_e0_u_recovery_activation.json"
        ): "A"
    }
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            p2_commit + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_p2_history",
        lambda **kwargs: (
            calls.append(("history", kwargs)) or h2_commit
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_refs_at",
        lambda **kwargs: calls.append(("refs", kwargs)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_log_head_identity",
        lambda **kwargs: calls.append(("log", kwargs)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_guard",
        lambda **kwargs: calls.append(("guard", kwargs)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_post_h2_paths_absent",
        lambda **kwargs: calls.append(("future", kwargs)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase3_recovery_p2_bundle",
        lambda **kwargs: calls.append(("bundle", kwargs)),
    )
    status = _closure_phase3_recovery_u2_short_status(staged=False)
    assert precommit_artifacts.closure_phase3_recovery_u2_pre_stage_scope(
        status, ""
    )
    assert (
        "future",
        {"repo_root": Path("."), "allow_recovery_activation": True},
    ) in calls
    assert (
        "bundle",
        {
            "repo_root": Path("."),
            "h2_commit": h2_commit,
            "require_git_publication": True,
            "allowed_dirty_paths": (
                precommit_artifacts.CLOSURE_E0_U_RECOVERY_ACTIVATION_PATH.as_posix(),
            ),
        },
    ) in calls

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="empty Git index",
    ):
        precommit_artifacts.closure_phase3_recovery_u2_pre_stage_scope(
            status, "A\tunexpected\n"
        )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact1A",
    ):
        precommit_artifacts.closure_phase3_recovery_u2_pre_stage_scope(
            (
                " M "
                + precommit_artifacts.CLOSURE_E0_U_RECOVERY_ACTIVATION_PATH.as_posix()
                + "\n"
            ),
            "",
        )

    u3_commit = precommit_artifacts.CLOSURE_PHASE3_H4_PARENT_U3_COMMIT
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            u3_commit + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_final_pointer_state",
        lambda **_kwargs: "raw",
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_final_boundary",
        lambda **_kwargs: None,
    )
    h4_status = _closure_phase3_h4_short_status(staged=False)
    assert precommit_artifacts.closure_phase3_h4_pre_stage_scope(h4_status, "")
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact2M",
    ):
        precommit_artifacts.closure_phase3_h4_pre_stage_scope(
            h4_status + "\n?? reports/closure_v1/unexpected.json", ""
        )

    h4_commit = "5" * 40
    pointer_state = {"value": "raw"}
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            h4_commit + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else f"{h4_commit} {u3_commit}\n"
            if args == ("rev-list", "--parents", "-n", "1", h4_commit)
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_final_pointer_state",
        lambda **_kwargs: pointer_state["value"],
    )
    for registered in (False, True):
        pointer_state["value"] = "registered" if registered else "raw"
        expected = precommit_artifacts._closure_phase3_final_expected_short_scope(
            registered=registered
        )
        rendered = "\n".join(
            f"{status} {path}" for path, status in sorted(expected.items())
        )
        assert precommit_artifacts.closure_phase3_final_pre_stage_scope(
            rendered, ""
        ) == pointer_state["value"]

    unexpected = "6" * 40
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            unexpected + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else f"{unexpected} {'7' * 40}\n"
            if args == ("rev-list", "--parents", "-n", "1", unexpected)
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="final-bundle markers",
    ):
        precommit_artifacts.closure_phase3_h4_pre_stage_scope(h4_status, "")
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="published exact2M H4",
    ):
        precommit_artifacts.closure_phase3_final_pre_stage_scope(h4_status, "")

    from src.experiments import lock_closure_e0_u_activation as activation

    raw_path = precommit_artifacts.CLOSURE_E0_U_RECOVERY_2_ACTIVATION_PATH.as_posix()
    u3_payload = activation._git(
        Path("."),
        (
            "cat-file",
            "blob",
            f"{precommit_artifacts.CLOSURE_PHASE3_H4_PARENT_U3_COMMIT}:{raw_path}",
        ),
    )
    monkeypatch.setattr(activation, "_git_oid", lambda *_args: h4_commit)
    monkeypatch.setattr(activation, "_git", lambda *_args: u3_payload)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_2_p3_history",
        lambda **_kwargs: precommit_artifacts.CLOSURE_PHASE3_H4_PARENT_H3_COMMIT,
    )

    def h4_history_output(_root: Path, *args: str) -> str:
        if args[0:1] == ("rev-parse",):
            return h4_commit + "\n"
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            return "refs/heads/main\n"
        if args == ("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"):
            return "refs/remotes/origin/main\n"
        if args == ("rev-list", "--parents", "-n", "1", h4_commit):
            return f"{h4_commit} {u3_commit}\n"
        if args == ("rev-list", "--parents", "-n", "1", u3_commit):
            return f"{u3_commit} {precommit_artifacts.CLOSURE_PHASE3_H4_PARENT_P3_COMMIT}\n"
        if args[:3] == ("ls-tree", h4_commit, "--"):
            path = args[3]
            mode = precommit_artifacts.CLOSURE_PHASE3_H4_GIT_MODES[path]
            return f"{mode} blob {'a' * 40}\t{path}\n"
        if args[-1:] == (h4_commit,):
            return _closure_phase3_h4_name_status()
        if args[-1:] == (u3_commit,):
            return _closure_phase3_recovery_2_u3_name_status()
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", h4_history_output)
    loaded = (
        precommit_artifacts._load_closure_e0_u_recovery_2_final_activation_authority(
            repo_root=Path(".")
        )
    )
    assert loaded["execution_id"] == (
        precommit_artifacts.CLOSURE_PHASE3_RECOVERY_2_ATTEMPT_3_EXECUTION_ID
    )
    valid_h4_history_output = h4_history_output

    def wrong_mode_output(_root: Path, *args: str) -> str:
        if args[:3] == ("ls-tree", h4_commit, "--"):
            path = args[3]
            return f"100644 blob {'a' * 40}\t{path}\n"
        return valid_h4_history_output(_root, *args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", wrong_mode_output)
    with pytest.raises(
        precommit_artifacts.ClosureE0UFinalBatchManifestAdapterError,
        match="mode/blob drifted",
    ):
        precommit_artifacts._load_closure_e0_u_recovery_2_final_activation_authority(
            repo_root=Path(".")
        )


def test_closure_phase3_recovery_2_h3_selector_is_exact15_on_consumed_u2(
    monkeypatch,
) -> None:
    status = _closure_phase3_recovery_2_h3_short_status(staged=False)
    scope = precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_2_STAGED_SCOPE
    assert len(scope) == 15
    assert list(scope.values()).count("M") == 11
    assert list(scope.values()).count("A") == 4
    assert precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_2_PARENT_COMMIT == (
        "a4f39173ec14aa7cd80d0fd38fb720f98cf88159"
    )
    assert precommit_artifacts.CLOSURE_PHASE3_RECOVERY_2_OUTCOME_LOG_BYTES == 738
    assert precommit_artifacts.CLOSURE_PHASE3_RECOVERY_2_LOG_RECORD_BYTES == 482
    calls: list[str] = []

    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_2_PARENT_COMMIT + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    for name in (
        "_require_closure_phase3_recovery_2_history",
        "_require_closure_phase3_recovery_refs_at",
        "_closure_phase3_recovery_2_log_identity",
        "_snapshot_closure_phase3_recovery_2_u2",
        "_require_closure_phase3_recovery_2_guards",
        "_require_closure_phase3_recovery_2_future_paths_absent",
    ):
        monkeypatch.setattr(
            precommit_artifacts,
            name,
            lambda *args, _name=name, **kwargs: calls.append(_name),
        )
    assert precommit_artifacts.closure_phase3_recovery_2_h3_pre_stage_scope(
        status, ""
    )
    assert len(calls) == 6

    partial = status.replace(
        " M tests/test_closure_phase3_e4_e7_contracts.py", ""
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact15",
    ):
        precommit_artifacts.closure_phase3_recovery_2_h3_pre_stage_scope(
            partial, ""
        )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="empty Git index",
    ):
        precommit_artifacts.closure_phase3_recovery_2_h3_pre_stage_scope(
            status, "M\tsrc/data/prepare_commit_artifacts.py\n"
        )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact15",
    ):
        precommit_artifacts.closure_phase3_recovery_2_h3_pre_stage_scope(
            status.replace(
                " M src/data/prepare_commit_artifacts.py",
                "AM src/data/prepare_commit_artifacts.py",
            ),
            "",
        )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact15",
    ):
        precommit_artifacts.closure_phase3_recovery_2_h3_pre_stage_scope(
            status + "\n?? reports/closure_v1/00_protocol/unexpected.json",
            "",
        )


def test_closure_phase3_recovery_2_p3_selector_is_exact7_on_published_h3(
    monkeypatch,
) -> None:
    h3_commit = "3" * 40
    scope = precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_2_STAGED_SCOPE
    assert len(scope) == 7
    assert set(scope.values()) == {"A"}
    assert set(precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_2_PHYSICAL_MODES.values()) == {
        0o600
    }
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            h3_commit + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    for name in (
        "_require_closure_phase3_recovery_2_h3_history",
        "_require_closure_phase3_recovery_refs_at",
        "_closure_phase3_recovery_2_log_head_identity",
        "_snapshot_closure_phase3_recovery_2_u2",
        "_require_closure_phase3_recovery_2_guards",
        "_require_closure_phase3_recovery_2_future_paths_absent",
        "_validate_closure_phase3_recovery_2_p3_bundle",
    ):
        monkeypatch.setattr(
            precommit_artifacts,
            name,
            lambda *args, _name=name, **kwargs: calls.append((_name, kwargs)),
        )
    status = _closure_phase3_recovery_2_p3_short_status(staged=False)
    assert precommit_artifacts.closure_phase3_recovery_2_p3_pre_stage_scope(
        status, ""
    )
    assert any(name.endswith("p3_bundle") for name, _kwargs in calls)
    assert (
        "_require_closure_phase3_recovery_2_future_paths_absent",
        {"repo_root": Path("."), "allow_p3": True},
    ) in calls

    first = sorted(scope)[0]
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact7A",
    ):
        precommit_artifacts.closure_phase3_recovery_2_p3_pre_stage_scope(
            status.replace(f"?? {first}", f" M {first}"), ""
        )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact7A",
    ):
        precommit_artifacts.closure_phase3_recovery_2_p3_pre_stage_scope(
            status + f"\n?? {first}", ""
        )


def test_closure_phase3_recovery_2_u3_selector_is_exact1_on_published_p3(
    monkeypatch,
) -> None:
    h3_commit = "3" * 40
    p3_commit = "4" * 40
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            p3_commit + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_2_p3_history",
        lambda **kwargs: calls.append(("history", kwargs)) or h3_commit,
    )
    for name in (
        "_require_closure_phase3_recovery_refs_at",
        "_closure_phase3_recovery_2_log_head_identity",
        "_snapshot_closure_phase3_recovery_2_u2",
        "_require_closure_phase3_recovery_2_guards",
        "_require_closure_phase3_recovery_2_future_paths_absent",
        "_validate_closure_phase3_recovery_2_p3_bundle",
    ):
        monkeypatch.setattr(
            precommit_artifacts,
            name,
            lambda *args, _name=name, **kwargs: calls.append((_name, kwargs)),
        )
    status = _closure_phase3_recovery_2_u3_short_status(staged=False)
    assert precommit_artifacts.closure_phase3_recovery_2_u3_pre_stage_scope(
        status, ""
    )
    marker = precommit_artifacts.CLOSURE_E0_U_RECOVERY_2_ACTIVATION_PATH.as_posix()
    assert (
        "_validate_closure_phase3_recovery_2_p3_bundle",
        {
            "repo_root": Path("."),
            "h3_commit": h3_commit,
            "require_git_publication": True,
            "allowed_dirty_paths": (marker,),
        },
    ) in calls
    assert (
        "_require_closure_phase3_recovery_2_future_paths_absent",
        {"repo_root": Path("."), "allow_p3": True, "allow_u3": True},
    ) in calls

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact1A",
    ):
        precommit_artifacts.closure_phase3_recovery_2_u3_pre_stage_scope(
            f" M {marker}\n", ""
        )
    assert not precommit_artifacts.closure_phase3_recovery_2_u3_pre_stage_scope(
        "", ""
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact1A",
    ):
        precommit_artifacts.closure_phase3_recovery_2_u3_pre_stage_scope(
            f"AM {marker}\n", ""
        )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact1A",
    ):
        precommit_artifacts.closure_phase3_recovery_2_u3_pre_stage_scope(
            f"?? {marker}\n?? reports/closure_v1/00_protocol/unexpected.json\n",
            "",
        )


def test_closure_phase3_h_runner_rewrite_selector_binds_current_u_p_h_r(
    monkeypatch,
) -> None:
    status = _closure_phase3_h_runner_rewrite_short_status(staged=False)
    assert precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_COMMIT == (
        "22cf63d58298e4eb769a437c0cfae3fbfa69ecb5"
    )
    assert precommit_artifacts.CLOSURE_PHASE3_P_RUNNER_REWRITE_COMMIT == (
        "116b33ad2c63792750f0fb021e7ed9208d8c0742"
    )
    assert precommit_artifacts.CLOSURE_PHASE3_U_RUNNER_REWRITE_COMMIT == (
        "0ff9a7d88fe60810a61f76543413b73e4f6ac85d"
    )
    assert precommit_artifacts.CLOSURE_PHASE3_U_RUNNER_REWRITE_BYTES == 34368
    assert precommit_artifacts.CLOSURE_PHASE3_U_RUNNER_REWRITE_SHA256 == (
        "6b1f149e53e5304e846794a98e06f2ad7b87800d05c4ae6059c9107d2af7c137"
    )
    assert precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_STAGED_SCOPE == {
        "src/data/prepare_commit_artifacts.py": "M",
        "src/experiments/run_closure_benchmark.py": "M",
        "tests/test_closure_e0_u_authority.py": "M",
        "tests/test_prepare_commit_artifacts.py": "M",
    }
    assert set(
        precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_STAGED_SCOPE
    ).issubset(precommit_artifacts.CLOSURE_PHASE3_H_STAGED_SCOPE)
    assert not (
        set(precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_STAGED_SCOPE)
        & set(precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_SCOPE)
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: _closure_phase3_h_runner_rewrite_ref_output(
            *args
        ),
    )

    assert precommit_artifacts.closure_phase3_h_runner_rewrite_pre_stage_scope(
        status,
        "",
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="empty Git index",
    ):
        precommit_artifacts.closure_phase3_h_runner_rewrite_pre_stage_scope(
            status,
            "M\tsrc/data/prepare_commit_artifacts.py\n",
        )

    partial = status.replace(
        " M src/experiments/run_closure_benchmark.py\n", ""
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact4M",
    ):
        precommit_artifacts.closure_phase3_h_runner_rewrite_pre_stage_scope(
            partial,
            "",
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            f"{'f' * 40}\n"
            if args
            == (
                "rev-list",
                "--parents",
                "-n",
                "1",
                precommit_artifacts.CLOSURE_PHASE3_U_RUNNER_REWRITE_COMMIT,
            )
            else _closure_phase3_h_runner_rewrite_ref_output(*args)
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="R 4c92ed7 -> H 22cf63d -> P 116b33a -> U 0ff9a7d",
    ):
        precommit_artifacts.closure_phase3_h_runner_rewrite_pre_stage_scope(
            status,
            "",
        )


def test_closure_phase3_h_runner_rewrite_live_remote_is_current_u(
    monkeypatch,
) -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        return precommit_artifacts.CommandResult(
            command,
            0,
            (
                precommit_artifacts.CLOSURE_PHASE3_U_RUNNER_REWRITE_COMMIT
                + "\trefs/heads/main\n"
            ),
            "",
        )

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    precommit_artifacts._require_closure_phase3_h_runner_rewrite_live_remote(
        repo_root=Path(".")
    )
    assert commands == [
        [
            "git",
            "-C",
            ".",
            "ls-remote",
            "--heads",
            precommit_artifacts.CLOSURE_PHASE3_LIVE_REMOTE_URL,
            "refs/heads/main",
        ]
    ]


@pytest.mark.parametrize(
    "guard_path",
    precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_FORBIDDEN_GUARDS,
)
def test_closure_phase3_h_runner_rewrite_rejects_each_runtime_guard(
    tmp_path: Path,
    guard_path: Path,
) -> None:
    assert (
        precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_FORBIDDEN_GUARDS
        == (
            Path("tmp/closure_v1_e10_source_evidence.guard"),
            Path("tmp/closure_phase3_input_overlay.guard"),
            Path("tmp/closure_v1_e0_u_activation/activation.guard"),
            Path("tmp/closure_v1_e0_u/sealed_batch.guard"),
        )
    )
    precommit_artifacts._require_closure_phase3_h_runner_rewrite_future_paths_absent(
        repo_root=tmp_path
    )
    physical = tmp_path / guard_path
    physical.parent.mkdir(parents=True, exist_ok=True)
    physical.write_text("owned\n", encoding="utf-8")

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match=guard_path.name,
    ):
        precommit_artifacts._require_closure_phase3_h_runner_rewrite_future_paths_absent(
            repo_root=tmp_path
        )


def _closure_phase3_h_runner_rewrite_publication_failure(
    payload: bytes,
    *,
    path: str | None = None,
    extra_section: str = "",
) -> Any:
    payload_line = payload[:-1].decode("utf-8")
    raw_path = (
        precommit_artifacts.CLOSURE_E0_U_ACTIVATION_PATH.as_posix()
        if path is None
        else path
    )
    stdout = (
        "Checking tracked files before publication...\n\n"
        "Local absolute paths found in versionable files:\n"
        f"{raw_path}:1:{payload_line}\n"
        f"{extra_section}\n"
        "Publication readiness check failed.\n"
    )
    command = ["scripts/check_repo_publication_ready.sh"]
    return precommit_artifacts.CommandResult(command, 1, stdout, "")


def _closure_phase3_h_runner_rewrite_activation_payload() -> bytes:
    """Build the canonical two-path U shape without requiring published U."""

    repository_root = "/" + "home" + "/" + "zero/repos/lentic-pipe"
    manifest = {
        "sealed_runtime_environment_record": {
            "purelib_path": repository_root
            + "/.venv/lib/python3.14/site-packages",
            "python_executable": {
                "link_path": repository_root + "/.venv/bin/python"
            },
        }
    }
    return (
        json.dumps(
            manifest,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_absolute_path",
        "extra_section",
        "wrong_file",
        "service_account",
        "private_key",
        "bucket",
    ],
)
def test_closure_phase3_h_runner_rewrite_publication_compensation_is_exact(
    mutation: str,
) -> None:
    payload = _closure_phase3_h_runner_rewrite_activation_payload()
    exact = _closure_phase3_h_runner_rewrite_publication_failure(payload)
    assert (
        precommit_artifacts._validate_closure_phase3_h_runner_rewrite_publication_result(
            exact,
            activation_payload=payload,
        )
        is True
    )

    candidate_payload = payload
    candidate_result = exact
    if mutation in {
        "extra_absolute_path",
        "service_account",
        "private_key",
        "bucket",
    }:
        manifest = json.loads(payload)
        injected = {
            "extra_absolute_path": "/" + "home" + "/" + "zero/forbidden",
            "service_account": {"type": "service_" + "account"},
            "private_" + "key": {"private_" + "key": "secret"},
            "bucket": "gs:" + "//forbidden-bucket/object",
        }[mutation]
        manifest["synthetic_mutation"] = injected
        candidate_payload = (
            json.dumps(
                manifest,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        candidate_result = _closure_phase3_h_runner_rewrite_publication_failure(
            candidate_payload
        )
    elif mutation == "extra_section":
        candidate_result = _closure_phase3_h_runner_rewrite_publication_failure(
            payload,
            extra_section="\nTracked secret-looking files:\nsynthetic",
        )
    elif mutation == "wrong_file":
        candidate_result = _closure_phase3_h_runner_rewrite_publication_failure(
            payload,
            path="reports/other.json",
        )

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="publication",
    ):
        precommit_artifacts._validate_closure_phase3_h_runner_rewrite_publication_result(
            candidate_result,
            activation_payload=candidate_payload,
        )


def test_closure_phase3_h_authority_rewrite_selector_binds_current_p_h_r(
    monkeypatch,
) -> None:
    status = _closure_phase3_h_authority_rewrite_short_status(staged=False)
    assert precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_STAGED_SCOPE == {
        "src/data/prepare_commit_artifacts.py": "M",
        "src/experiments/closure_e0_u_authority.py": "M",
        "tests/test_closure_e0_u_authority.py": "M",
        "tests/test_prepare_commit_artifacts.py": "M",
    }
    assert set(
        precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_STAGED_SCOPE
    ).issubset(precommit_artifacts.CLOSURE_PHASE3_H_STAGED_SCOPE)
    assert not (
        set(precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_STAGED_SCOPE)
        & set(precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_SCOPE)
    )
    assert sorted(
        precommit_artifacts.CLOSURE_PHASE3_P_AUTHORITY_REWRITE_PHYSICAL_MODES.values()
    ) == [0o600] * 7 + [0o644] * 3
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: _closure_phase3_h_authority_rewrite_ref_output(
            *args
        ),
    )

    assert precommit_artifacts.closure_phase3_h_authority_rewrite_pre_stage_scope(
        status,
        "",
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="empty Git index",
    ):
        precommit_artifacts.closure_phase3_h_authority_rewrite_pre_stage_scope(
            status,
            "M\tsrc/data/prepare_commit_artifacts.py\n",
        )

    partial = status.replace(
        " M src/experiments/closure_e0_u_authority.py\n", ""
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact4M",
    ):
        precommit_artifacts.closure_phase3_h_authority_rewrite_pre_stage_scope(
            partial,
            "",
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            f"{'f' * 40}\n"
            if args
            == (
                "rev-list",
                "--parents",
                "-n",
                "1",
                precommit_artifacts.CLOSURE_PHASE3_P_AUTHORITY_REWRITE_COMMIT,
            )
            else _closure_phase3_h_authority_rewrite_ref_output(*args)
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="R -> H 203b320 -> P 1cbef2a",
    ):
        precommit_artifacts.closure_phase3_h_authority_rewrite_pre_stage_scope(
            status,
            "",
        )


def test_closure_phase3_h_authority_rewrite_live_remote_is_current_p(
    monkeypatch,
) -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        return precommit_artifacts.CommandResult(
            command,
            0,
            (
                precommit_artifacts.CLOSURE_PHASE3_P_AUTHORITY_REWRITE_COMMIT
                + "\trefs/heads/main\n"
            ),
            "",
        )

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    precommit_artifacts._require_closure_phase3_h_authority_rewrite_live_remote(
        repo_root=Path(".")
    )
    assert commands == [
        [
            "git",
            "-C",
            ".",
            "ls-remote",
            "--heads",
            precommit_artifacts.CLOSURE_PHASE3_LIVE_REMOTE_URL,
            "refs/heads/main",
        ]
    ]

    monkeypatch.setattr(
        precommit_artifacts,
        "run_command",
        lambda command, **_kwargs: precommit_artifacts.CommandResult(
            command,
            0,
            f"{'f' * 40}\trefs/heads/main\n",
            "",
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="live remote main",
    ):
        precommit_artifacts._require_closure_phase3_h_authority_rewrite_live_remote(
            repo_root=Path(".")
        )


@pytest.mark.parametrize(
    "guard_path",
    precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_FORBIDDEN_GUARDS,
)
def test_closure_phase3_h_authority_rewrite_rejects_each_runtime_guard(
    tmp_path: Path,
    guard_path: Path,
) -> None:
    assert (
        precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_FORBIDDEN_GUARDS
        == (
            Path("tmp/closure_v1_e0_u_activation/activation.guard"),
            Path("tmp/closure_v1_e0_u/sealed_batch.guard"),
        )
    )
    precommit_artifacts._require_closure_phase3_h_authority_rewrite_future_paths_absent(
        repo_root=tmp_path
    )
    physical = tmp_path / guard_path
    physical.parent.mkdir(parents=True, exist_ok=True)
    physical.write_text("owned\n", encoding="utf-8")

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match=guard_path.name,
    ):
        precommit_artifacts._require_closure_phase3_h_authority_rewrite_future_paths_absent(
            repo_root=tmp_path
        )


def test_closure_phase3_h_import_repair_selector_binds_exact5_and_historical_p(
    monkeypatch,
) -> None:
    status = _closure_phase3_h_import_repair_short_status(staged=False)
    assert precommit_artifacts.CLOSURE_PHASE3_H_IMPORT_REPAIR_STAGED_SCOPE == {
        "docs/closure_v1/E0_U_PHASE3_SEALED_BATCH.md": "M",
        "src/data/prepare_commit_artifacts.py": "M",
        "src/experiments/build_closure_e10_source_evidence.py": "M",
        "tests/test_build_closure_e10_source_evidence.py": "M",
        "tests/test_prepare_commit_artifacts.py": "M",
    }
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            "f" * 40 + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    assert not precommit_artifacts.closure_phase3_h_import_repair_pre_stage_scope(
        status,
        "",
    )

    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: _closure_phase3_h_import_repair_ref_output(*args),
    )

    assert precommit_artifacts.closure_phase3_h_import_repair_pre_stage_scope(
        status,
        "",
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="empty Git index",
    ):
        precommit_artifacts.closure_phase3_h_import_repair_pre_stage_scope(
            status,
            "M\tsrc/data/prepare_commit_artifacts.py\n",
        )

    partial = status.replace(
        " M src/experiments/build_closure_e10_source_evidence.py\n", ""
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact5M",
    ):
        precommit_artifacts.closure_phase3_h_import_repair_pre_stage_scope(
            partial,
            "",
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            f"{precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_COMMIT} "
            f"{'f' * 40}\n"
            if args
            == (
                "rev-list",
                "--parents",
                "-n",
                "1",
                precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_COMMIT,
            )
            else _closure_phase3_h_import_repair_ref_output(*args)
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="historical R -> pre-import-H -> P histories",
    ):
        precommit_artifacts.closure_phase3_h_import_repair_pre_stage_scope(
            status,
            "",
        )


def test_closure_phase3_h_import_repair_live_remote_is_canonical_and_exact(
    monkeypatch,
) -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        return precommit_artifacts.CommandResult(
            command,
            0,
            (
                precommit_artifacts.CLOSURE_PHASE3_H_IMPORT_REPAIR_COMMIT
                + "\trefs/heads/main\n"
            ),
            "",
        )

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    precommit_artifacts._require_closure_phase3_h_import_repair_live_remote(
        repo_root=Path(".")
    )
    assert commands == [
        [
            "git",
            "-C",
            ".",
            "ls-remote",
            "--heads",
            precommit_artifacts.CLOSURE_PHASE3_LIVE_REMOTE_URL,
            "refs/heads/main",
        ]
    ]

    monkeypatch.setattr(
        precommit_artifacts,
        "run_command",
        lambda command, **_kwargs: precommit_artifacts.CommandResult(
            command,
            0,
            f"{'f' * 40}\trefs/heads/main\n",
            "",
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="live remote main",
    ):
        precommit_artifacts._require_closure_phase3_h_import_repair_live_remote(
            repo_root=Path(".")
        )


def test_closure_phase3_h_amend_selector_is_exact13_unstaged_and_parent_scoped(
    monkeypatch,
) -> None:
    status = _closure_phase3_h_amend_short_status(staged=False)
    e10_amendment_paths = {
        "src/experiments/build_closure_e10_source_evidence.py",
        "tests/test_build_closure_e10_source_evidence.py",
    }
    assert {
        path: precommit_artifacts.CLOSURE_PHASE3_H_AMEND_STAGED_SCOPE[path]
        for path in e10_amendment_paths
    } == {path: "M" for path in e10_amendment_paths}
    assert {
        precommit_artifacts.CLOSURE_PHASE3_H_AMEND_GIT_MODES[path]
        for path in e10_amendment_paths
    } == {"100644"}
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: _closure_phase3_h_amend_ref_output(*args),
    )

    assert precommit_artifacts.closure_phase3_h_amend_pre_stage_scope(
        status,
        "",
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="empty Git index",
    ):
        precommit_artifacts.closure_phase3_h_amend_pre_stage_scope(
            status,
            "M\t.gitignore\n",
        )

    partial = status.replace(
        " M src/experiments/build_closure_e10_source_evidence.py\n", ""
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact13M",
    ):
        precommit_artifacts.closure_phase3_h_amend_pre_stage_scope(
            partial,
            "",
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            "f" * 40 + "\n"
            if args == ("rev-parse", "HEAD^1^{commit}")
            else _closure_phase3_h_amend_ref_output(*args)
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="direct parent R",
    ):
        precommit_artifacts.closure_phase3_h_amend_pre_stage_scope(
            status,
            "",
        )


def test_closure_phase3_h_selector_is_exact_unstaged_and_base_scoped(
    monkeypatch,
) -> None:
    status = _closure_phase3_h_short_status(staged=False)
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: _closure_phase3_h_ref_output(*args),
    )

    assert precommit_artifacts.closure_phase3_h_pre_stage_scope(status, "")

    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="empty Git index",
    ):
        precommit_artifacts.closure_phase3_h_pre_stage_scope(
            status,
            "M\tsrc/data/prepare_commit_artifacts.py\n",
        )

    partial = status.replace(
        "?? configs/closure_v1/closure_e0_u_activation.schema.json\n", ""
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="exact40",
    ):
        precommit_artifacts.closure_phase3_h_pre_stage_scope(partial, "")

    later_head = "f" * 40
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            later_head + "\n"
            if args[:2] == ("rev-parse", "HEAD^{commit}")
            else _closure_phase3_h_ref_output(*args)
        ),
    )
    one_marker = " M src/experiments/closure_e0_u_authority.py\n"
    assert not precommit_artifacts.closure_phase3_h_pre_stage_scope(
        one_marker, ""
    )


def test_closure_phase3_h_invocation_forbids_dvc_mutation() -> None:
    args = _closure_phase3_h_args()
    env = {"DVC_NO_ANALYTICS": "1"}

    precommit_artifacts.validate_closure_phase3_h_invocation(args, env=env)

    args.target = ["models"]
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="empty DVC target set",
    ):
        precommit_artifacts.validate_closure_phase3_h_invocation(args, env=env)


def test_closure_phase3_h_staged_transaction_binds_exact_modes_and_blobs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    blob_oids: dict[str, str] = {}
    for raw_path, git_mode in precommit_artifacts.CLOSURE_PHASE3_H_GIT_MODES.items():
        path = tmp_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"phase3-h:{raw_path}\n".encode()
        path.write_bytes(payload)
        path.chmod(0o755 if git_mode == "100755" else 0o644)
        blob_oids[raw_path] = hashlib.sha1(
            f"blob {len(payload)}\0".encode() + payload,
            usedforsecurity=False,
        ).hexdigest()
    index_oids = dict(blob_oids)

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase3_h_name_status()
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_h_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        if args[:3] == ("ls-files", "-s", "--"):
            raw_path = args[3]
            return (
                f"{precommit_artifacts.CLOSURE_PHASE3_H_GIT_MODES[raw_path]} "
                f"{index_oids[raw_path]} 0\t{raw_path}\n"
            )
        if args[:3] == ("hash-object", "--no-filters", "--"):
            return blob_oids[args[3]] + "\n"
        return _closure_phase3_h_ref_output(*args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    records = precommit_artifacts.validate_closure_phase3_h_staged_transaction(
        repo_root=tmp_path
    )
    assert len(records) == 40
    assert sum(record.mode == 0o755 for record in records) == 1
    assert all(record.nlink == 1 for record in records)

    index_oids["src/experiments/run_closure_benchmark.py"] = "0" * 40
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="mode/blob binding drifted",
    ):
        precommit_artifacts.validate_closure_phase3_h_staged_transaction(
            repo_root=tmp_path
        )


def test_closure_phase3_h_authority_rewrite_staged_transaction_binds_future_h(
    tmp_path: Path,
    monkeypatch,
) -> None:
    blob_oids: dict[str, str] = {}
    all_git_modes = {
        **{
            path: "100644"
            for path in precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_SCOPE
        },
        **precommit_artifacts.CLOSURE_PHASE3_H_GIT_MODES,
    }
    for raw_path, git_mode in all_git_modes.items():
        path = tmp_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"phase3-authority-rewrite:{raw_path}\n".encode()
        path.write_bytes(payload)
        if raw_path in precommit_artifacts.CLOSURE_PHASE3_P_HISTORICAL_SCOPE:
            path.chmod(
                precommit_artifacts.CLOSURE_PHASE3_P_AUTHORITY_REWRITE_PHYSICAL_MODES[
                    raw_path
                ]
            )
        else:
            path.chmod(0o755 if git_mode == "100755" else 0o644)
        blob_oids[raw_path] = hashlib.sha1(
            f"blob {len(payload)}\0".encode() + payload,
            usedforsecurity=False,
        ).hexdigest()
    prospective = _closure_phase3_h_name_status()
    prospective_command = (
        "diff",
        "--cached",
        "--name-status",
        "--no-renames",
        precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT,
        "--",
        *sorted(precommit_artifacts.CLOSURE_PHASE3_H_STAGED_SCOPE),
    )

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase3_h_authority_rewrite_name_status()
        if args == prospective_command:
            return prospective
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_h_authority_rewrite_short_status(
                staged=True
            )
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        if args[:3] == ("ls-files", "-s", "--"):
            raw_path = args[3]
            return (
                f"{all_git_modes[raw_path]} {blob_oids[raw_path]} "
                f"0\t{raw_path}\n"
            )
        if args[:3] == ("hash-object", "--no-filters", "--"):
            return blob_oids[args[3]] + "\n"
        if args[0] == "rev-parse" and ":" in args[1]:
            raw_path = args[1].split(":", 1)[1]
            return blob_oids[raw_path] + "\n"
        return _closure_phase3_h_authority_rewrite_ref_output(*args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    records = (
        precommit_artifacts.validate_closure_phase3_h_authority_rewrite_staged_transaction(
            repo_root=tmp_path
        )
    )
    assert len(records) == 40
    assert sum(record.mode == 0o755 for record in records) == 1
    assert all(record.nlink == 1 for record in records)

    prospective = _closure_phase3_h_authority_rewrite_name_status()
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="prospective exact40",
    ):
        precommit_artifacts.validate_closure_phase3_h_authority_rewrite_staged_transaction(
            repo_root=tmp_path
        )

    prospective = _closure_phase3_h_name_status()
    restricted_p_path = next(
        path
        for path, mode in (
            precommit_artifacts.CLOSURE_PHASE3_P_AUTHORITY_REWRITE_PHYSICAL_MODES.items()
        )
        if mode == 0o600
    )
    (tmp_path / restricted_p_path).chmod(0o644)
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="file/name/parent identity changed",
    ):
        precommit_artifacts.validate_closure_phase3_h_authority_rewrite_staged_transaction(
            repo_root=tmp_path
        )


def test_closure_phase3_h_amend_staged_transaction_binds_patch_and_final_tree(
    tmp_path: Path,
    monkeypatch,
) -> None:
    blob_oids: dict[str, str] = {}
    for raw_path, git_mode in precommit_artifacts.CLOSURE_PHASE3_H_GIT_MODES.items():
        path = tmp_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"phase3-h-amended:{raw_path}\n".encode()
        path.write_bytes(payload)
        path.chmod(0o755 if git_mode == "100755" else 0o644)
        blob_oids[raw_path] = hashlib.sha1(
            f"blob {len(payload)}\0".encode() + payload,
            usedforsecurity=False,
        ).hexdigest()
    index_oids = dict(blob_oids)
    prospective = _closure_phase3_h_name_status()

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase3_h_amend_name_status()
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
            precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT,
        ):
            return prospective
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_h_amend_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        if args[:3] == ("ls-files", "-s", "--"):
            raw_path = args[3]
            return (
                f"{precommit_artifacts.CLOSURE_PHASE3_H_GIT_MODES[raw_path]} "
                f"{index_oids[raw_path]} 0\t{raw_path}\n"
            )
        if args[:3] == ("hash-object", "--no-filters", "--"):
            return blob_oids[args[3]] + "\n"
        return _closure_phase3_h_amend_ref_output(*args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    records = (
        precommit_artifacts.validate_closure_phase3_h_amend_staged_transaction(
            repo_root=tmp_path
        )
    )
    assert len(records) == 40
    assert all(record.nlink == 1 for record in records)

    prospective = _closure_phase3_h_amend_name_status()
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="prospective exact40",
    ):
        precommit_artifacts.validate_closure_phase3_h_amend_staged_transaction(
            repo_root=tmp_path
        )

    prospective = _closure_phase3_h_name_status()
    index_oids[".gitignore"] = "0" * 40
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="mode/blob binding drifted",
    ):
        precommit_artifacts.validate_closure_phase3_h_amend_staged_transaction(
            repo_root=tmp_path
        )


def test_closure_phase3_h_import_repair_staged_transaction_binds_exact40(
    tmp_path: Path,
    monkeypatch,
) -> None:
    blob_oids: dict[str, str] = {}
    for raw_path, git_mode in precommit_artifacts.CLOSURE_PHASE3_H_GIT_MODES.items():
        path = tmp_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"phase3-h-import-repair:{raw_path}\n".encode()
        path.write_bytes(payload)
        path.chmod(0o755 if git_mode == "100755" else 0o644)
        blob_oids[raw_path] = hashlib.sha1(
            f"blob {len(payload)}\0".encode() + payload,
            usedforsecurity=False,
        ).hexdigest()
    prospective = _closure_phase3_h_name_status()

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase3_h_import_repair_name_status()
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
            precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT,
        ):
            return prospective
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_h_import_repair_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        if args[:3] == ("ls-files", "-s", "--"):
            raw_path = args[3]
            return (
                f"{precommit_artifacts.CLOSURE_PHASE3_H_GIT_MODES[raw_path]} "
                f"{blob_oids[raw_path]} 0\t{raw_path}\n"
            )
        if args[:3] == ("hash-object", "--no-filters", "--"):
            return blob_oids[args[3]] + "\n"
        return _closure_phase3_h_import_repair_ref_output(*args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    records = (
        precommit_artifacts.validate_closure_phase3_h_import_repair_staged_transaction(
            repo_root=tmp_path
        )
    )
    assert len(records) == 40
    assert all(record.nlink == 1 for record in records)

    prospective = _closure_phase3_h_import_repair_name_status()
    with pytest.raises(
        precommit_artifacts.ClosurePhase3HPrecommitAdapterError,
        match="prospective exact40",
    ):
        precommit_artifacts.validate_closure_phase3_h_import_repair_staged_transaction(
            repo_root=tmp_path
        )


def test_closure_phase3_h_main_bypasses_historical_e0_m_selectors(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_h_precommit",
        lambda *_args, **_kwargs: 73,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_formal_model_lock_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("historical E0-M selector must not run")
        ),
    )

    assert precommit_artifacts.main() == 73


def test_closure_phase3_h_amend_main_precedes_full_h_and_historical_selectors(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_amend_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_h_amend_precommit",
        lambda *_args, **_kwargs: 79,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("full-H selector must not run after amend match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_formal_model_lock_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("historical E0-M selector must not run")
        ),
    )

    assert precommit_artifacts.main() == 79


def test_closure_phase3_h_import_repair_main_precedes_other_h_selectors(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_import_repair_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_h_import_repair_precommit",
        lambda *_args, **_kwargs: 83,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_amend_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("older H amendment selector must not run")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("full-H selector must not run")
        ),
    )

    assert precommit_artifacts.main() == 83


def test_closure_phase3_recovery_main_precedes_historical_selectors(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_recovery_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_recovery_precommit",
        lambda *_args, **_kwargs: 103,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_runner_rewrite_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("historical runner rewrite selector must not run")
        ),
    )

    assert precommit_artifacts.main() == 103


def test_closure_phase3_recovery_p2_main_precedes_u2_and_historical_selectors(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_recovery_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_recovery_p2_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_recovery_p2_precommit",
        lambda *_args, **_kwargs: 107,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_recovery_u2_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("U2 selector must not run after P2 match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_runner_rewrite_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("historical selector must not run after P2 match")
        ),
    )

    assert precommit_artifacts.main() == 107


def test_closure_phase3_recovery_u2_main_precedes_historical_selectors(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_recovery_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_recovery_p2_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_recovery_u2_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_recovery_u2_precommit",
        lambda *_args, **_kwargs: 109,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_runner_rewrite_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("historical selector must not run after U2 match")
        ),
    )

    assert precommit_artifacts.main() == 109


def test_closure_phase3_h_runner_rewrite_main_precedes_all_h_selectors(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_runner_rewrite_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_h_runner_rewrite_precommit",
        lambda *_args, **_kwargs: 97,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_authority_rewrite_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("older H authority selector must not run")
        ),
    )

    assert precommit_artifacts.main() == 97


def test_closure_phase3_h_authority_rewrite_main_precedes_all_h_selectors(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_authority_rewrite_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_h_authority_rewrite_precommit",
        lambda *_args, **_kwargs: 89,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_import_repair_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("older H repair selector must not run")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_amend_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("older H amendment selector must not run")
        ),
    )

    assert precommit_artifacts.main() == 89


def test_closure_phase3_h_transaction_only_stages_exact40_and_runs_generic_checks(
    monkeypatch,
) -> None:
    args = _closure_phase3_h_args()
    initial_status = _closure_phase3_h_short_status(staged=False)
    staged = False
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    generic_calls: list[str] = []
    physical = ("sealed-physical-snapshot",)
    outcome = (1, 2, 0o644, 1, 0, 3, 4, "a" * 40)
    unmanaged = [Path("data/closure_v1/locked_evaluation")]

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: outcome,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_unpublished_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: unmanaged,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_staged_transaction",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase3-h-test.md"),
    )

    def git_output(_root: Path, *command: str) -> str:
        if command[:4] == ("status", "--short", "--untracked-files=all"):
            return (
                _closure_phase3_h_short_status(staged=True)
                if staged
                else initial_status
            )
        if command[:3] == (
            "diff",
            "--cached",
            "--name-status",
        ):
            return _closure_phase3_h_name_status() if staged else ""
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        nonlocal staged
        commands.append(command)
        if command == ["scripts/check_repo_publication_ready.sh"]:
            return precommit_artifacts.CommandResult(command, 0, "PASS", "")
        if command[:4] == ["git", "add", "-A", "--"]:
            staged = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)

    def generic(**kwargs: Any) -> list[Any]:
        generic_calls.append(kwargs["staged_status"])
        return [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "generic checks passed"
            )
        ]

    monkeypatch.setattr(precommit_artifacts, "reproducibility_checks", generic)
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase3_h_precommit(
            args,
            initial_status=initial_status,
        )
        == 0
    )
    assert len(commands) == 2
    assert commands[0] == ["scripts/check_repo_publication_ready.sh"]
    assert commands[1] == [
        "git",
        "add",
        "-A",
        "--",
        *sorted(precommit_artifacts.CLOSURE_PHASE3_H_STAGED_SCOPE),
    ]
    assert generic_calls == [_closure_phase3_h_name_status()]
    assert reports[0]["rejected_unmanaged_paths"] == unmanaged
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_push_result"] is None
    assert all("push" not in command for command in commands)



def test_closure_phase3_recovery_p2_staged_transaction_is_exact7(
    monkeypatch,
) -> None:
    h2_commit = "2" * 40
    identity = precommit_artifacts.RegistrationFileIdentity(
        "p2", 1, 2, 0o600, 1, 7, "a" * 64, 3, 4
    )
    snapshot = {"p2": identity}

    def git_output(_root: Path, *args: str) -> str:
        if args == ("diff", "--cached", "--name-status", "--no-renames"):
            return _closure_phase3_recovery_p2_name_status()
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_recovery_p2_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        if args == ("rev-parse", "HEAD^{commit}"):
            return h2_commit + "\n"
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_h2_history",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_refs_at",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_p2_files",
        lambda **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase3_recovery_p2_index_bindings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_log_head_identity",
        lambda **_kwargs: identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_guard",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_post_h2_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase3_recovery_p2_bundle",
        lambda **_kwargs: {},
    )

    assert precommit_artifacts.validate_closure_phase3_recovery_p2_staged_transaction() == snapshot


def test_closure_phase3_recovery_u2_staged_transaction_is_exact1(
    monkeypatch,
) -> None:
    h2_commit = "2" * 40
    p2_commit = "3" * 40
    payload = b'{"sealed":true}\n'
    identity = precommit_artifacts.RegistrationFileIdentity(
        "u2", 1, 2, 0o644, 1, len(payload), "a" * 64, 3, 4
    )

    def git_output(_root: Path, *args: str) -> str:
        if args == ("diff", "--cached", "--name-status", "--no-renames"):
            return _closure_phase3_recovery_u2_name_status()
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_recovery_u2_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        if args == ("rev-parse", "HEAD^{commit}"):
            return p2_commit + "\n"
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_p2_history",
        lambda **_kwargs: h2_commit,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_refs_at",
        lambda **_kwargs: None,
    )

    def snapshot_u2(**kwargs: Any) -> Any:
        kwargs["_payload_sink"].append(payload)
        return identity

    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_u2_file",
        snapshot_u2,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase3_recovery_u2_index_binding",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_log_head_identity",
        lambda **_kwargs: identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_guard",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_post_h2_paths_absent",
        lambda **_kwargs: None,
    )
    bundle_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase3_recovery_p2_bundle",
        lambda **kwargs: bundle_calls.append(kwargs) or {},
    )

    assert precommit_artifacts.validate_closure_phase3_recovery_u2_staged_transaction() == identity
    assert bundle_calls == [
        {
            "repo_root": Path("."),
            "h2_commit": h2_commit,
            "require_git_publication": True,
            "allowed_dirty_paths": (
                precommit_artifacts.CLOSURE_E0_U_RECOVERY_ACTIVATION_PATH.as_posix(),
            ),
        }
    ]

    tuple_schema: dict[str, Any] = {
        "type": "array",
        "prefixItems": [{"const": "first"}, {"const": "second"}],
        "items": False,
    }
    precommit_artifacts._validate_closure_e0_u_schema_node(
        ["first", "second"],
        tuple_schema,
        root_schema=tuple_schema,
        instance_path="$",
    )
    with pytest.raises(
        precommit_artifacts.ClosureE0UActivationManifestAdapterError,
        match=r"schema const rejected \$\[0\]",
    ):
        precommit_artifacts._validate_closure_e0_u_schema_node(
            ["wrong", "second"],
            tuple_schema,
            root_schema=tuple_schema,
            instance_path="$",
        )
    with pytest.raises(
        precommit_artifacts.ClosureE0UActivationManifestAdapterError,
        match=r"schema rejected \$\[2\]",
    ):
        precommit_artifacts._validate_closure_e0_u_schema_node(
            ["first", "second", "extra"],
            tuple_schema,
            root_schema=tuple_schema,
            instance_path="$",
        )


def test_closure_phase3_recovery_2_staged_transactions_are_exact15_7_1(
    monkeypatch,
) -> None:
    identity = precommit_artifacts.RegistrationFileIdentity(
        "candidate", 1, 2, 0o644, 1, 17, "a" * 64, 3, 4
    )
    h3_snapshot = {"h3": identity}
    p3_snapshot = {"p3": identity}
    h4_snapshot = {"h4": identity}
    final_boundary = (identity, {"output": (17, "a" * 64)}, ((1, 2, 384, 1, 0), (1, 3, 384, 1, 0)))
    h3_commit = "3" * 40
    p3_commit = "4" * 40

    for name in (
        "_validate_closure_phase3_recovery_2_index_bindings",
        "_require_closure_phase3_recovery_2_history",
        "_require_closure_phase3_recovery_refs_at",
        "_closure_phase3_recovery_2_log_identity",
        "_closure_phase3_recovery_2_log_head_identity",
        "_snapshot_closure_phase3_recovery_2_u2",
        "_require_closure_phase3_recovery_2_guards",
        "_require_closure_phase3_recovery_2_future_paths_absent",
        "_require_closure_phase3_recovery_2_h3_history",
        "_validate_closure_phase3_recovery_2_p3_bundle",
    ):
        monkeypatch.setattr(
            precommit_artifacts,
            name,
            lambda *args, **kwargs: None,
        )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_2_h3_files",
        lambda **_kwargs: h3_snapshot,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_2_p3_files",
        lambda **_kwargs: p3_snapshot,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_2_p3_history",
        lambda **_kwargs: h3_commit,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h4_files",
        lambda **_kwargs: h4_snapshot,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_final_boundary",
        lambda **_kwargs: final_boundary,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_final_pointer_state",
        lambda **_kwargs: "raw",
    )

    stage = "H3"

    def git_output(_root: Path, *args: str) -> str:
        if args == ("diff", "--cached", "--name-status", "--no-renames"):
            return {
                "H3": _closure_phase3_recovery_2_h3_name_status(),
                "P3": _closure_phase3_recovery_2_p3_name_status(),
                "U3": _closure_phase3_recovery_2_u3_name_status(),
                "H4": _closure_phase3_h4_name_status(),
            }[stage]
        if args == ("status", "--short", "--untracked-files=all"):
            return {
                "H3": _closure_phase3_recovery_2_h3_short_status(staged=True),
                "P3": _closure_phase3_recovery_2_p3_short_status(staged=True),
                "U3": _closure_phase3_recovery_2_u3_short_status(staged=True),
                "H4": _closure_phase3_h4_short_status(staged=True),
            }[stage]
        if args == ("diff", "--name-status", "--no-renames"):
            return (
                f"M\t{precommit_artifacts.CLOSURE_E0_U_OUTCOME_ACCESS_LOG_PATH}"
                if stage == "H4"
                else ""
            )
        if args == ("rev-parse", "HEAD^{commit}"):
            return (h3_commit if stage == "P3" else p3_commit) + "\n"
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    assert (
        precommit_artifacts.validate_closure_phase3_recovery_2_h3_staged_transaction()
        == h3_snapshot
    )
    stage = "P3"
    assert (
        precommit_artifacts.validate_closure_phase3_recovery_2_p3_staged_transaction()
        == p3_snapshot
    )
    stage = "U3"

    def snapshot_u3(**kwargs: Any) -> Any:
        kwargs["_payload_sink"].append(b'{"sealed":true}\n')
        return identity

    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_2_u3_file",
        snapshot_u3,
    )
    assert (
        precommit_artifacts.validate_closure_phase3_recovery_2_u3_staged_transaction()
        == identity
    )
    stage = "H4"
    assert precommit_artifacts.validate_closure_phase3_h4_staged_transaction() == (
        h4_snapshot,
        final_boundary,
    )


@pytest.mark.parametrize(
    ("stage", "scope", "name_status", "short_status"),
    (
        (
            "H3",
            precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_2_STAGED_SCOPE,
            _closure_phase3_recovery_2_h3_name_status,
            _closure_phase3_recovery_2_h3_short_status,
        ),
        (
            "P3",
            precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_2_STAGED_SCOPE,
            _closure_phase3_recovery_2_p3_name_status,
            _closure_phase3_recovery_2_p3_short_status,
        ),
        (
            "U3",
            precommit_artifacts.CLOSURE_PHASE3_U_RECOVERY_2_STAGED_SCOPE,
            _closure_phase3_recovery_2_u3_name_status,
            _closure_phase3_recovery_2_u3_short_status,
        ),
    ),
)
def test_closure_phase3_recovery_2_precommit_stages_only_exact_scope(
    monkeypatch,
    capsys,
    stage: str,
    scope: dict[str, str],
    name_status: Callable[[], str],
    short_status: Callable[..., str],
) -> None:
    args = _closure_phase3_h_args()
    state = {"staged": False}
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    candidate = {"H3": {"h3": "sealed"}, "P3": {"p3": "sealed"}, "U3": "sealed"}[
        stage
    ]
    identity = precommit_artifacts.RegistrationFileIdentity(
        "sealed", 1, 2, 0o644, 1, 738, "a" * 64, 3, 4
    )
    head = "9" * 40

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_invocation",
        lambda _args: None,
    )
    for name in (
        "closure_phase3_recovery_2_h3_pre_stage_scope",
        "closure_phase3_recovery_2_p3_pre_stage_scope",
        "closure_phase3_recovery_2_u3_pre_stage_scope",
    ):
        monkeypatch.setattr(
            precommit_artifacts,
            name,
            lambda *_args, **_kwargs: True,
        )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_2_p3_history",
        lambda **_kwargs: "8" * 40,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_2_snapshot_candidate",
        lambda **_kwargs: candidate,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_2_log_identity",
        lambda **_kwargs: identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_2_log_head_identity",
        lambda **_kwargs: identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_2_u2",
        lambda **_kwargs: identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_2_guards",
        lambda **_kwargs: ((2069, 1, 0o600, 1, 0), (2069, 2, 0o600, 1, 0)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_2_require_future_boundary",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_live_remote_at",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/recovery-2-report.md"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_recovery_2_publication_check",
        lambda **_kwargs: precommit_artifacts.CommandResult(
            ["scripts/check_repo_publication_ready.sh"], 1, "expected", ""
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_recovery_2_h3_staged_transaction",
        lambda **_kwargs: candidate,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_recovery_2_p3_staged_transaction",
        lambda **_kwargs: candidate,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_recovery_2_u3_staged_transaction",
        lambda **_kwargs: candidate,
    )

    def git_output(_root: Path, *git_args: str) -> str:
        if git_args == ("diff", "--cached", "--name-status", "--no-renames"):
            return name_status() if state["staged"] else ""
        if git_args == ("rev-parse", "HEAD^{commit}"):
            return head + "\n"
        if git_args == ("status", "--short", "--untracked-files=all"):
            return short_status(staged=state["staged"])
        raise AssertionError(git_args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        if command[:4] == ["git", "add", "-A", "--"]:
            state["staged"] = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)

    def findings(**_kwargs: Any) -> list[Any]:
        result = [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "passed"
            )
        ]
        if stage == "H3":
            message = (
                "Staged report artifact is not listed in any experiment manifest output."
            )
            result.extend(
                precommit_artifacts.ReproducibilityFinding(
                    "fail", "manifest", path.as_posix(), message
                )
                for path in (
                    precommit_artifacts.CLOSURE_PHASE3_RECOVERY_2_RECEIPT_PATH,
                    precommit_artifacts.CLOSURE_PHASE3_RECOVERY_2_COMMAND_PATH,
                )
            )
        return result

    monkeypatch.setattr(precommit_artifacts, "reproducibility_checks", findings)
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase3_recovery_2_precommit(
            args,
            stage=stage,
            initial_status=short_status(staged=False),
        )
        == 0
    )
    assert commands == [["git", "add", "-A", "--", *sorted(scope)]]
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_push_result"] is None
    assert all("push" not in command for command in commands)

    if stage == "U3":
        boundary = (
            identity,
            {"output": (7, "b" * 64)},
            ((1, 2, 0o600, 1, 0), (1, 3, 0o600, 1, 0)),
        )
        candidate_h4 = {"h4": identity}
        state = {"staged": False}
        commands.clear()
        monkeypatch.setattr(
            precommit_artifacts,
            "closure_phase3_h4_pre_stage_scope",
            lambda *_args, **_kwargs: True,
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "_snapshot_closure_phase3_h4_files",
            lambda **_kwargs: candidate_h4,
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "_require_closure_phase3_final_boundary",
            lambda **_kwargs: boundary,
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "validate_closure_phase3_h4_staged_transaction",
            lambda **_kwargs: (candidate_h4, boundary),
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "_git_output",
            lambda _root, *git_args: (
                _closure_phase3_h4_name_status()
                if state["staged"]
                else ""
            ),
        )

        def h4_run(command: list[str], **_kwargs: Any) -> Any:
            commands.append(command)
            assert command[:4] == ["git", "add", "-A", "--"]
            state["staged"] = True
            return precommit_artifacts.CommandResult(command, 0, "", "")

        monkeypatch.setattr(precommit_artifacts, "run_command", h4_run)
        assert precommit_artifacts._run_closure_phase3_h4_precommit(
            args,
            initial_status=_closure_phase3_h4_short_status(staged=False),
        ) == 0
        assert commands == [
            [
                "git",
                "add",
                "-A",
                "--",
                *sorted(precommit_artifacts.CLOSURE_PHASE3_H4_STAGED_SCOPE),
            ]
        ]

        from src.experiments import lock_closure_e0_u_activation as activation

        _all, _formats, direct, heavy, pointers = (
            precommit_artifacts._closure_e0_u_final_layout()
        )
        final = {"dvc": 0, "staged": False}
        commands.clear()
        monkeypatch.setattr(
            precommit_artifacts,
            "closure_phase3_final_pre_stage_scope",
            lambda *_args, **_kwargs: (
                "registered" if final["dvc"] == 4 else "raw"
            ),
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "_closure_phase3_final_pointer_state",
            lambda **_kwargs: "registered" if final["dvc"] == 4 else "raw",
        )
        monkeypatch.setattr(
            precommit_artifacts.os.path,
            "lexists",
            lambda value: any(
                Path(value).as_posix().endswith(path.as_posix())
                for path in pointers[: final["dvc"]]
            ),
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "_snapshot_closure_phase3_final_outputs",
            lambda **_kwargs: boundary[1],
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "_read_closure_e0_u_final_dvc_output",
            lambda *_args, **_kwargs: b"heavy",
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "_validate_closure_e0_u_final_dvc_pointer",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            activation,
            "_regular_bytes",
            lambda *_args, **_kwargs: b"pointer",
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "validate_closure_phase3_final_staged_transaction",
            lambda **_kwargs: boundary,
        )

        def final_git_output(_root: Path, *git_args: str) -> str:
            if git_args == ("status", "--short", "--untracked-files=all"):
                return "registered"
            return "staged" if final["staged"] else ""

        monkeypatch.setattr(precommit_artifacts, "_git_output", final_git_output)

        def final_run(command: list[str], **_kwargs: Any) -> Any:
            commands.append(command)
            if command[:2] == [
                precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
                "add",
            ]:
                assert command[2] == heavy[final["dvc"]].as_posix()
                final["dvc"] += 1
            elif command[:4] == ["git", "add", "-A", "--"]:
                final["staged"] = True
            else:
                raise AssertionError(command)
            return precommit_artifacts.CommandResult(command, 0, "", "")

        monkeypatch.setattr(precommit_artifacts, "run_command", final_run)
        assert precommit_artifacts._run_closure_phase3_final_precommit(
            args,
            initial_status="raw",
            initial_state="raw",
        ) == 0
        assert [command[2] for command in commands[:4]] == [
            path.as_posix() for path in heavy
        ]
        assert "--yes" not in {part for command in commands for part in command}
        assert all("push" not in command for command in commands)

        capsys.readouterr()
        state["staged"] = False
        commands.clear()

        def h4_partial_add(command: list[str], **_kwargs: Any) -> Any:
            commands.append(command)
            if command[:4] == ["git", "add", "-A", "--"]:
                state["staged"] = True
                return precommit_artifacts.CommandResult(command, 1, "", "partial")
            if command[:3] == ["git", "restore", "--staged"]:
                state["staged"] = False
                return precommit_artifacts.CommandResult(command, 0, "", "")
            raise AssertionError(command)

        monkeypatch.setattr(precommit_artifacts, "run_command", h4_partial_add)
        monkeypatch.setattr(
            precommit_artifacts,
            "_git_output",
            lambda _root, *git_args: (
                _closure_phase3_h4_name_status()
                if state["staged"]
                else ""
            ),
        )
        assert precommit_artifacts._run_closure_phase3_h4_precommit(
            args,
            initial_status=_closure_phase3_h4_short_status(staged=False),
        ) == 2
        assert commands[-1] == [
            "git",
            "restore",
            "--staged",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE3_H4_STAGED_SCOPE),
        ]
        assert "rollback recaptured exact index/status/boundary/DVC" in (
            capsys.readouterr().err
        )

        state["staged"] = False
        commands.clear()

        def h4_restore_rc(command: list[str], **_kwargs: Any) -> Any:
            commands.append(command)
            if command[:4] == ["git", "add", "-A", "--"]:
                state["staged"] = True
                return precommit_artifacts.CommandResult(command, 1, "", "partial")
            if command[:3] == ["git", "restore", "--staged"]:
                return precommit_artifacts.CommandResult(command, 7, "", "blocked")
            raise AssertionError(command)

        monkeypatch.setattr(precommit_artifacts, "run_command", h4_restore_rc)
        assert precommit_artifacts._run_closure_phase3_h4_precommit(
            args,
            initial_status=_closure_phase3_h4_short_status(staged=False),
        ) == 2
        failure = capsys.readouterr().err
        assert "H4 directed git add failed" in failure
        assert "ROLLBACK AUDIT FAILED: directed restore exited 7" in failure
        assert "index/status did not return to exact H4 pre-stage state" in failure

        state["staged"] = False
        commands.clear()

        def h4_restore_raise(command: list[str], **_kwargs: Any) -> Any:
            commands.append(command)
            if command[:4] == ["git", "add", "-A", "--"]:
                state["staged"] = True
                return precommit_artifacts.CommandResult(command, 1, "", "partial")
            if command[:3] == ["git", "restore", "--staged"]:
                raise RuntimeError("restore boom")
            raise AssertionError(command)

        monkeypatch.setattr(precommit_artifacts, "run_command", h4_restore_raise)
        assert precommit_artifacts._run_closure_phase3_h4_precommit(
            args,
            initial_status=_closure_phase3_h4_short_status(staged=False),
        ) == 2
        failure = capsys.readouterr().err
        assert "H4 directed git add failed" in failure
        assert "ROLLBACK AUDIT FAILED: directed restore raised: restore boom" in failure
        assert "index/status did not return to exact H4 pre-stage state" in failure

        final.update({"dvc": 4, "staged": False})
        commands.clear()
        monkeypatch.setattr(precommit_artifacts, "_git_output", final_git_output)

        def final_partial_add(command: list[str], **_kwargs: Any) -> Any:
            commands.append(command)
            if command[:4] == ["git", "add", "-A", "--"]:
                final["staged"] = True
                return precommit_artifacts.CommandResult(command, 1, "", "partial")
            if command[:3] == ["git", "restore", "--staged"]:
                final["staged"] = False
                return precommit_artifacts.CommandResult(command, 0, "", "")
            raise AssertionError(command)

        monkeypatch.setattr(precommit_artifacts, "run_command", final_partial_add)
        assert precommit_artifacts._run_closure_phase3_final_precommit(
            args,
            initial_status="registered",
            initial_state="registered",
        ) == 2
        assert commands[-1][:3] == ["git", "restore", "--staged"]
        assert "rollback recaptured exact index/status/boundary/DVC" in (
            capsys.readouterr().err
        )

        final.update({"dvc": 4, "staged": False})
        commands.clear()

        def final_restore_raise(command: list[str], **_kwargs: Any) -> Any:
            commands.append(command)
            if command[:4] == ["git", "add", "-A", "--"]:
                final["staged"] = True
                return precommit_artifacts.CommandResult(command, 1, "", "partial")
            if command[:3] == ["git", "restore", "--staged"]:
                raise RuntimeError("final restore boom")
            raise AssertionError(command)

        monkeypatch.setattr(precommit_artifacts, "run_command", final_restore_raise)
        assert precommit_artifacts._run_closure_phase3_final_precommit(
            args,
            initial_status="registered",
            initial_state="registered",
        ) == 2
        failure = capsys.readouterr().err
        assert "final directed exact53 git add failed" in failure
        assert (
            "ROLLBACK AUDIT FAILED: directed restore raised: final restore boom"
            in failure
        )
        assert "index/status did not return to registered pre-stage state" in failure

        final.update({"dvc": 0, "staged": False})
        commands.clear()

        def partial_status() -> str:
            scope = {
                **{path.as_posix(): "A" for path in direct},
                **{path.as_posix(): "A" for path in pointers[: final["dvc"]]},
                precommit_artifacts.CLOSURE_E0_U_OUTCOME_ACCESS_LOG_PATH.as_posix(): "M",
            }
            expected = precommit_artifacts._expected_short_scope(
                scope, staged=False
            )
            return "\n".join(
                f"{status} {path}" for path, status in sorted(expected.items())
            )

        monkeypatch.setattr(
            precommit_artifacts,
            "_git_output",
            lambda _root, *git_args: (
                partial_status()
                if git_args == ("status", "--short", "--untracked-files=all")
                else ""
            ),
        )

        def failed_dvc_add(command: list[str], **_kwargs: Any) -> Any:
            commands.append(command)
            assert command[:2] == [
                precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
                "add",
            ]
            final["dvc"] = 1
            return precommit_artifacts.CommandResult(command, 9, "", "failed")

        monkeypatch.setattr(precommit_artifacts, "run_command", failed_dvc_add)
        assert precommit_artifacts._run_closure_phase3_final_precommit(
            args,
            initial_status="raw",
            initial_state="raw",
        ) == 2
        failure = capsys.readouterr().err
        assert "audited fail-closed ordered DVC prefix 1/1" in failure
        assert "DVC FAILURE STATE AUDIT FAILED" not in failure

        final.update({"dvc": 0, "staged": False})
        commands.clear()
        monkeypatch.setattr(
            precommit_artifacts.os.path,
            "lexists",
            lambda value: Path(value).as_posix().endswith(pointers[1].as_posix()),
        )
        monkeypatch.setattr(precommit_artifacts, "run_command", failed_dvc_add)
        assert precommit_artifacts._run_closure_phase3_final_precommit(
            args,
            initial_status="raw",
            initial_state="raw",
        ) == 2
        failure = capsys.readouterr().err
        assert "DVC add 1/4 returned 9" in failure
        assert "DVC FAILURE STATE AUDIT FAILED" in failure
        assert "not a valid ordered prefix" in failure
        assert "audited fail-closed ordered DVC prefix" not in failure


@pytest.mark.parametrize(
    ("stage", "scope", "short_status"),
    (
        (
            "H3",
            precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_2_STAGED_SCOPE,
            _closure_phase3_recovery_2_h3_short_status,
        ),
        (
            "P3",
            precommit_artifacts.CLOSURE_PHASE3_P_RECOVERY_2_STAGED_SCOPE,
            _closure_phase3_recovery_2_p3_short_status,
        ),
        (
            "U3",
            precommit_artifacts.CLOSURE_PHASE3_U_RECOVERY_2_STAGED_SCOPE,
            _closure_phase3_recovery_2_u3_short_status,
        ),
    ),
)
def test_closure_phase3_recovery_2_rollback_is_directed_and_recaptured(
    monkeypatch,
    stage: str,
    scope: dict[str, str],
    short_status: Callable[..., str],
) -> None:
    identity = precommit_artifacts.RegistrationFileIdentity(
        "sealed", 1, 2, 0o644, 1, 738, "a" * 64, 3, 4
    )
    candidate = {"h3": identity}
    guards = ((2069, 1, 0o600, 1, 0), (2069, 2, 0o600, 1, 0))
    restored = {"value": False}
    commands: list[list[str]] = []
    for selector in (
        "closure_phase3_recovery_2_h3_pre_stage_scope",
        "closure_phase3_recovery_2_p3_pre_stage_scope",
        "closure_phase3_recovery_2_u3_pre_stage_scope",
    ):
        monkeypatch.setattr(
            precommit_artifacts,
            selector,
            lambda *_args, **_kwargs: True,
        )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_2_snapshot_candidate",
        lambda **_kwargs: candidate,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_2_log_identity",
        lambda **_kwargs: identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_2_log_head_identity",
        lambda **_kwargs: identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_2_u2",
        lambda **_kwargs: identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_2_guards",
        lambda **_kwargs: guards,
    )
    for name in (
        "_require_closure_phase3_recovery_refs_at",
        "_require_closure_phase3_recovery_live_remote_at",
        "_closure_phase3_recovery_2_require_future_boundary",
        "_validate_closure_phase3_recovery_2_p3_bundle",
    ):
        monkeypatch.setattr(
            precommit_artifacts,
            name,
            lambda **_kwargs: None,
        )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )

    def git_output(_root: Path, *args: str) -> str:
        if args == ("status", "--short", "--untracked-files=all"):
            assert restored["value"]
            return short_status(staged=False)
        if args == ("diff", "--cached", "--name-status", "--no-renames"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        restored["value"] = True
        return precommit_artifacts.CommandResult(command, 0, "", "")

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    assert (
        precommit_artifacts._rollback_closure_phase3_recovery_2_staging(
            stage=stage,
            candidate_before=candidate,
            log_before=identity,
            u2_before=identity,
            guards_before=guards,
            head_commit=precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_2_PARENT_COMMIT,
            h3_commit=None if stage == "H3" else "3" * 40,
            p3_commit="4" * 40 if stage == "U3" else None,
            dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            dvc_status_before={},
            artifacts=[],
            unmanaged_before=[],
            repo_root=Path("."),
        )
        is None
    )
    assert commands == [
        [
            "git",
            "restore",
            "--staged",
            "--",
            *sorted(scope),
        ]
    ]


def test_closure_phase3_recovery_transaction_stages_only_exact14(
    monkeypatch,
) -> None:
    args = _closure_phase3_h_args()
    initial_status = _closure_phase3_recovery_short_status(staged=False)
    state = {"staged": False}
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    candidate_identity = precommit_artifacts.RegistrationFileIdentity(
        "sealed-recovery-exact14", 1, 2, 0o644, 1, 1, "a" * 64, 3, 4
    )
    candidate = {"sealed": candidate_identity}
    log_identity = precommit_artifacts.RegistrationFileIdentity(
        "sealed-256-byte-prefix", 1, 3, 0o644, 1, 256, "b" * 64, 4, 5
    )
    u1_identity = precommit_artifacts.RegistrationFileIdentity(
        "sealed-consumed-u1", 1, 4, 0o644, 1, 34368, "c" * 64, 5, 6
    )
    guard_identity = (2069, 80609290, 0o600, 1, 0)

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_recovery_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_candidate_files",
        lambda **_kwargs: candidate,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_log_identity",
        lambda **_kwargs: log_identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_u1",
        lambda **_kwargs: u1_identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_guard",
        lambda **_kwargs: guard_identity,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_future_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_live_remote",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_recovery_staged_transaction",
        lambda **_kwargs: candidate,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase3-recovery-test.md"),
    )

    def publication(**_kwargs: Any) -> tuple[Any, bool]:
        command = ["scripts/check_repo_publication_ready.sh"]
        commands.append(command)
        return precommit_artifacts.CommandResult(
            command, 1, "exact consumed U1", ""
        ), True

    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_recovery_publication_check",
        publication,
    )

    def git_output(_root: Path, *command: str) -> str:
        if command == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_recovery_short_status(
                staged=state["staged"]
            )
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase3_recovery_name_status() if state["staged"] else ""
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        assert command == [
            "git",
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_STAGED_SCOPE),
        ]
        state["staged"] = True
        return precommit_artifacts.CommandResult(command, 0, "", "")

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(
        precommit_artifacts,
        "reproducibility_checks",
        lambda **_kwargs: [
            precommit_artifacts.ReproducibilityFinding(
                "fail",
                "manifest",
                precommit_artifacts.CLOSURE_PHASE3_RECOVERY_RECEIPT_PATH.as_posix(),
                "Staged report artifact is not listed in any experiment manifest output.",
            ),
            precommit_artifacts.ReproducibilityFinding(
                "fail",
                "manifest",
                precommit_artifacts.CLOSURE_PHASE3_RECOVERY_COMMAND_PATH.as_posix(),
                "Staged report artifact is not listed in any experiment manifest output.",
            ),
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "generic checks passed"
            )
        ],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase3_recovery_precommit(
            args,
            initial_status=initial_status,
        )
        == 0
    )
    assert commands == [
        ["scripts/check_repo_publication_ready.sh"],
        [
            "git",
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_STAGED_SCOPE),
        ],
    ]
    assert reports[0]["staged_status"] == _closure_phase3_recovery_name_status()
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_push_result"] is None
    assert any(
        finding.check == "phase3_recovery_attempt_1"
        and "old guard was not removed or reused" in finding.message
        for finding in reports[0]["reproducibility_findings"]
    )
    assert all("push" not in command for command in commands)


def test_closure_phase3_h_runner_rewrite_transaction_stages_only_exact4(
    monkeypatch,
) -> None:
    args = _closure_phase3_h_args()
    initial_status = _closure_phase3_h_runner_rewrite_short_status(
        staged=False
    )
    state = {"staged": False}
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    generic_calls: list[str] = []
    physical = ("sealed-future-h-exact40",)
    rewrite = ("sealed-runner-rewrite-exact4",)
    p_physical = ("sealed-current-p-exact10",)
    u_physical = ("sealed-current-u-exact1",)
    outcome = (1, 2, 0o644, 1, 0, 3, 4, "a" * 40)

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_runner_rewrite_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_runner_rewrite_files",
        lambda **_kwargs: rewrite,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_p_runner_rewrite_files",
        lambda **_kwargs: p_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_u_runner_rewrite_file",
        lambda **_kwargs: u_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: outcome,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_runner_rewrite_future_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_runner_rewrite_live_remote",
        lambda **_kwargs: None,
    )

    def publication_check(**_kwargs: Any) -> tuple[Any, bool]:
        command = ["scripts/check_repo_publication_ready.sh"]
        commands.append(command)
        return (
            precommit_artifacts.CommandResult(command, 1, "exact U", ""),
            True,
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase3_h_runner_rewrite_publication_check",
        publication_check,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_runner_rewrite_staged_transaction",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase3-h-runner-rewrite-test.md"),
    )

    prospective_command = (
        "diff",
        "--cached",
        "--name-status",
        "--no-renames",
        precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT,
        "--",
        *sorted(precommit_artifacts.CLOSURE_PHASE3_H_STAGED_SCOPE),
    )

    def git_output(_root: Path, *command: str) -> str:
        if command == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_h_runner_rewrite_short_status(
                staged=state["staged"]
            )
        if command == prospective_command:
            assert state["staged"]
            return _closure_phase3_h_name_status()
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return (
                _closure_phase3_h_runner_rewrite_name_status()
                if state["staged"]
                else ""
            )
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        if command == [
            "git",
            "add",
            "-A",
            "--",
            *sorted(
                precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_STAGED_SCOPE
            ),
        ]:
            state["staged"] = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)

    def generic(**kwargs: Any) -> list[Any]:
        generic_calls.append(kwargs["staged_status"])
        return [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "generic checks passed"
            )
        ]

    monkeypatch.setattr(precommit_artifacts, "reproducibility_checks", generic)
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase3_h_runner_rewrite_precommit(
            args,
            initial_status=initial_status,
        )
        == 0
    )
    assert commands == [
        ["scripts/check_repo_publication_ready.sh"],
        [
            "git",
            "add",
            "-A",
            "--",
            *sorted(
                precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_STAGED_SCOPE
            ),
        ],
    ]
    assert generic_calls == [_closure_phase3_h_name_status()]
    assert reports[0]["staged_status"] == (
        _closure_phase3_h_runner_rewrite_name_status()
    )
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_push_result"] is None
    publication_report = reports[0]["publication_check_result"]
    assert publication_report.returncode == 0
    assert publication_report.stdout == (
        "OK: exact current-U two-path publication exception compensated; "
        "no other findings.\n"
    )
    assert any(
        finding.check == "phase3_h_runner_rewrite_topology"
        and "drop stale P exact10 and U exact1" in finding.message
        and "regenerate and republish P followed by U" in finding.message
        for finding in reports[0]["reproducibility_findings"]
    )
    assert any(
        finding.check == "phase3_h_runner_rewrite_publication_guard"
        and "real rc=1" in finding.message
        and "compensated only" in finding.message
        for finding in reports[0]["reproducibility_findings"]
    )
    report_text = publication_report.stdout + "\n".join(
        finding.message for finding in reports[0]["reproducibility_findings"]
    )
    assert "WARN" not in report_text
    assert "FAIL" not in report_text
    assert all("push" not in command for command in commands)


def test_closure_phase3_h_authority_rewrite_transaction_stages_only_exact4(
    monkeypatch,
) -> None:
    args = _closure_phase3_h_args()
    initial_status = _closure_phase3_h_authority_rewrite_short_status(
        staged=False
    )
    state = {"staged": False}
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    generic_calls: list[str] = []
    physical = ("sealed-future-h-exact40",)
    rewrite = ("sealed-authority-rewrite-exact4",)
    p_physical = ("sealed-current-p-exact10",)
    outcome = (1, 2, 0o644, 1, 0, 3, 4, "a" * 40)

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_authority_rewrite_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_authority_rewrite_files",
        lambda **_kwargs: rewrite,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_p_authority_rewrite_files",
        lambda **_kwargs: p_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: outcome,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_authority_rewrite_future_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_authority_rewrite_live_remote",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_authority_rewrite_staged_transaction",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase3-h-authority-rewrite-test.md"),
    )

    prospective_command = (
        "diff",
        "--cached",
        "--name-status",
        "--no-renames",
        precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT,
        "--",
        *sorted(precommit_artifacts.CLOSURE_PHASE3_H_STAGED_SCOPE),
    )

    def git_output(_root: Path, *command: str) -> str:
        if command == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_h_authority_rewrite_short_status(
                staged=state["staged"]
            )
        if command == prospective_command:
            assert state["staged"]
            return _closure_phase3_h_name_status()
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return (
                _closure_phase3_h_authority_rewrite_name_status()
                if state["staged"]
                else ""
            )
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        if command == ["scripts/check_repo_publication_ready.sh"]:
            return precommit_artifacts.CommandResult(command, 0, "PASS", "")
        if command == [
            "git",
            "add",
            "-A",
            "--",
            *sorted(
                precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_STAGED_SCOPE
            ),
        ]:
            state["staged"] = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)

    def generic(**kwargs: Any) -> list[Any]:
        generic_calls.append(kwargs["staged_status"])
        return [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "generic checks passed"
            )
        ]

    monkeypatch.setattr(precommit_artifacts, "reproducibility_checks", generic)
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase3_h_authority_rewrite_precommit(
            args,
            initial_status=initial_status,
        )
        == 0
    )
    assert commands == [
        ["scripts/check_repo_publication_ready.sh"],
        [
            "git",
            "add",
            "-A",
            "--",
            *sorted(
                precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_STAGED_SCOPE
            ),
        ],
    ]
    assert generic_calls == [_closure_phase3_h_name_status()]
    assert reports[0]["staged_status"] == (
        _closure_phase3_h_authority_rewrite_name_status()
    )
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_push_result"] is None
    assert any(
        finding.check == "phase3_h_authority_rewrite_topology"
        and "drop stale P exact10" in finding.message
        for finding in reports[0]["reproducibility_findings"]
    )
    assert all("push" not in command for command in commands)


@pytest.mark.parametrize("drift", [None, "log", "u1", "guard"])
def test_closure_phase3_recovery_rollback_preserves_durable_attempt_1(
    monkeypatch,
    capsys,
    drift: str | None,
) -> None:
    state = {"staged": True}
    commands: list[list[str]] = []
    candidate_identity = precommit_artifacts.RegistrationFileIdentity(
        "sealed-recovery-exact14", 1, 2, 0o644, 1, 1, "a" * 64, 3, 4
    )
    candidate = {"sealed": candidate_identity}
    log_identity = precommit_artifacts.RegistrationFileIdentity(
        "sealed-256-byte-prefix", 1, 3, 0o644, 1, 256, "b" * 64, 4, 5
    )
    u1_identity = precommit_artifacts.RegistrationFileIdentity(
        "sealed-consumed-u1", 1, 4, 0o644, 1, 34368, "c" * 64, 5, 6
    )
    guard_identity = (2069, 80609290, 0o600, 1, 0)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        assert command == [
            "git",
            "restore",
            "--staged",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE3_H_RECOVERY_STAGED_SCOPE),
        ]
        state["staged"] = False
        return precommit_artifacts.CommandResult(command, 0, "", "")

    def git_output(_root: Path, *command: str) -> str:
        if command == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_recovery_short_status(
                staged=state["staged"]
            )
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase3_recovery_name_status() if state["staged"] else ""
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_recovery_pre_stage_scope",
        lambda *_args, **_kwargs: not state["staged"],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_candidate_files",
        lambda **_kwargs: candidate,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_recovery_log_identity",
        lambda **_kwargs: (
            candidate_identity if drift == "log" else log_identity
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_recovery_u1",
        lambda **_kwargs: (
            candidate_identity if drift == "u1" else u1_identity
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_guard",
        lambda **_kwargs: (
            (2069, 999, 0o600, 1, 0)
            if drift == "guard"
            else guard_identity
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_future_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_recovery_live_remote",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )

    assert (
        precommit_artifacts._abort_closure_phase3_recovery_post_add(
            RuntimeError("synthetic recovery failure"),
            candidate_before=candidate,
            log_before=log_identity,
            u1_before=u1_identity,
            guard_before=guard_identity,
            dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            dvc_status_before={},
            artifacts=[],
            unmanaged_before=[],
            repo_root=Path("."),
        )
        == 2
    )
    stderr = capsys.readouterr().err
    if drift is None:
        assert "directed index rollback restored exact14" in stderr
    else:
        assert "ROLLBACK FAILED CLOSED" in stderr
        assert drift.replace("u1", "U1") in stderr or drift in stderr
    assert len(commands) == 1


@pytest.mark.parametrize("drift", [None, "p", "u"])
def test_closure_phase3_h_runner_rewrite_rollback_binds_current_p_and_u(
    monkeypatch,
    capsys,
    drift: str | None,
) -> None:
    state = {"staged": True}
    commands: list[list[str]] = []
    physical = ("sealed-future-h-exact40",)
    rewrite = ("sealed-runner-rewrite-exact4",)
    p_physical = ("sealed-current-p-exact10",)
    u_physical = ("sealed-current-u-exact1",)
    outcome = (1, 2, 0o644, 1, 0, 3, 4, "a" * 40)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        assert command == [
            "git",
            "restore",
            "--staged",
            "--",
            *sorted(
                precommit_artifacts.CLOSURE_PHASE3_H_RUNNER_REWRITE_STAGED_SCOPE
            ),
        ]
        state["staged"] = False
        return precommit_artifacts.CommandResult(command, 0, "", "")

    def git_output(_root: Path, *command: str) -> str:
        if command == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_h_runner_rewrite_short_status(
                staged=state["staged"]
            )
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return (
                _closure_phase3_h_runner_rewrite_name_status()
                if state["staged"]
                else ""
            )
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_runner_rewrite_pre_stage_scope",
        lambda *_args, **_kwargs: not state["staged"],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_runner_rewrite_files",
        lambda **_kwargs: rewrite,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_p_runner_rewrite_files",
        lambda **_kwargs: ("drifted-current-p",)
        if drift == "p"
        else p_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_u_runner_rewrite_file",
        lambda **_kwargs: ("drifted-current-u",)
        if drift == "u"
        else u_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: outcome,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_runner_rewrite_future_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_runner_rewrite_live_remote",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )

    assert (
        precommit_artifacts._abort_closure_phase3_h_post_add(
            RuntimeError("synthetic runner rewrite failure"),
            mode="runner_rewrite",
            physical_before=physical,
            amend_before=rewrite,
            outcome_log_before=outcome,
            dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            dvc_status_before={},
            artifacts=[],
            unmanaged_before=[],
            repo_root=Path("."),
            p_before=p_physical,
            u_before=u_physical,
        )
        == 2
    )
    stderr = capsys.readouterr().err
    if drift is not None:
        assert "ROLLBACK FAILED CLOSED" in stderr
        assert f"current {drift.upper()} snapshot drifted" in stderr
    else:
        assert "directed index rollback restored" in stderr
    assert len(commands) == 1


@pytest.mark.parametrize("p_drift", [False, True])
def test_closure_phase3_h_authority_rewrite_rollback_is_exact_and_directed(
    monkeypatch,
    capsys,
    p_drift: bool,
) -> None:
    state = {"staged": True}
    commands: list[list[str]] = []
    physical = ("sealed-future-h-exact40",)
    rewrite = ("sealed-authority-rewrite-exact4",)
    p_physical = ("sealed-current-p-exact10",)
    outcome = (1, 2, 0o644, 1, 0, 3, 4, "a" * 40)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        expected = [
            "git",
            "restore",
            "--staged",
            "--",
            *sorted(
                precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_STAGED_SCOPE
            ),
        ]
        assert command == expected
        state["staged"] = False
        return precommit_artifacts.CommandResult(command, 0, "", "")

    def git_output(_root: Path, *command: str) -> str:
        if command == ("status", "--short", "--untracked-files=all"):
            return _closure_phase3_h_authority_rewrite_short_status(
                staged=state["staged"]
            )
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return (
                _closure_phase3_h_authority_rewrite_name_status()
                if state["staged"]
                else ""
            )
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_authority_rewrite_pre_stage_scope",
        lambda *_args, **_kwargs: not state["staged"],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_authority_rewrite_files",
        lambda **_kwargs: rewrite,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_p_authority_rewrite_files",
        lambda **_kwargs: ("drifted-current-p",) if p_drift else p_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: outcome,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_authority_rewrite_future_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_authority_rewrite_live_remote",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )

    assert (
        precommit_artifacts._abort_closure_phase3_h_post_add(
            RuntimeError("synthetic authority rewrite failure"),
            mode="authority_rewrite",
            physical_before=physical,
            amend_before=rewrite,
            outcome_log_before=outcome,
            dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            dvc_status_before={},
            artifacts=[],
            unmanaged_before=[],
            repo_root=Path("."),
            p_before=p_physical,
        )
        == 2
    )
    assert commands == [
        [
            "git",
            "restore",
            "--staged",
            "--",
            *sorted(
                precommit_artifacts.CLOSURE_PHASE3_H_AUTHORITY_REWRITE_STAGED_SCOPE
            ),
        ]
    ]
    assert state["staged"] is False
    error = capsys.readouterr().err
    if p_drift:
        assert "ROLLBACK FAILED CLOSED" in error
        assert "post-rollback exact10 P worktree snapshot drifted" in error
    else:
        assert "restored the exact unstaged scope" in error


def test_closure_phase3_h_amend_transaction_end_to_end_synthetic(
    monkeypatch,
) -> None:
    args = _closure_phase3_h_args()
    initial_status = _closure_phase3_h_amend_short_status(staged=False)
    staged = False
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    generic_calls: list[str] = []
    physical = ("sealed-final-exact40",)
    amend_physical = ("sealed-amend-exact13",)
    outcome = (1, 2, 0o644, 1, 0, 3, 4, "a" * 40)
    unmanaged = [Path("data/closure_v1/locked_evaluation")]

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_amend_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_amend_files",
        lambda **_kwargs: amend_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: outcome,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_unpublished_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: unmanaged,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_amend_staged_transaction",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase3-h-amend-test.md"),
    )

    def git_output(_root: Path, *command: str) -> str:
        if command == ("status", "--short", "--untracked-files=all"):
            return (
                _closure_phase3_h_amend_short_status(staged=True)
                if staged
                else initial_status
            )
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase3_h_amend_name_status() if staged else ""
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
            precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT,
        ):
            assert staged
            return _closure_phase3_h_name_status()
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        nonlocal staged
        commands.append(command)
        if command == ["scripts/check_repo_publication_ready.sh"]:
            return precommit_artifacts.CommandResult(command, 0, "PASS", "")
        if command[:4] == ["git", "add", "-A", "--"]:
            staged = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)

    def generic(**kwargs: Any) -> list[Any]:
        generic_calls.append(kwargs["staged_status"])
        return [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "generic checks passed"
            )
        ]

    monkeypatch.setattr(precommit_artifacts, "reproducibility_checks", generic)
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase3_h_amend_precommit(
            args,
            initial_status=initial_status,
        )
        == 0
    )
    assert commands == [
        ["scripts/check_repo_publication_ready.sh"],
        [
            "git",
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE3_H_AMEND_STAGED_SCOPE),
        ],
    ]
    assert generic_calls == [_closure_phase3_h_name_status()]
    assert reports[0]["staged_status"] == _closure_phase3_h_amend_name_status()
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_push_result"] is None
    assert all("push" not in command for command in commands)


def test_closure_phase3_h_import_repair_transaction_stages_only_exact5(
    monkeypatch,
) -> None:
    args = _closure_phase3_h_args()
    initial_status = _closure_phase3_h_import_repair_short_status(staged=False)
    state = {"staged": False}
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    generic_calls: list[str] = []
    physical = ("sealed-final-exact40",)
    repair_physical = ("sealed-e10-inventory-repair-exact5",)
    outcome = (1, 2, 0o644, 1, 0, 3, 4, "a" * 40)

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_import_repair_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_import_repair_files",
        lambda **_kwargs: repair_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: outcome,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_unpublished_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_import_repair_live_remote",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_import_repair_staged_transaction",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase3-h-import-repair-test.md"),
    )

    def git_output(_root: Path, *command: str) -> str:
        if command == ("status", "--short", "--untracked-files=all"):
            return (
                _closure_phase3_h_import_repair_short_status(staged=True)
                if state["staged"]
                else initial_status
            )
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return (
                _closure_phase3_h_import_repair_name_status()
                if state["staged"]
                else ""
            )
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
            precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT,
        ):
            assert state["staged"]
            return _closure_phase3_h_name_status()
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        if command == ["scripts/check_repo_publication_ready.sh"]:
            return precommit_artifacts.CommandResult(command, 0, "PASS", "")
        if command == [
            "git",
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE3_H_IMPORT_REPAIR_STAGED_SCOPE),
        ]:
            state["staged"] = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)

    def generic(**kwargs: Any) -> list[Any]:
        generic_calls.append(kwargs["staged_status"])
        return [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "generic checks passed"
            )
        ]

    monkeypatch.setattr(precommit_artifacts, "reproducibility_checks", generic)
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase3_h_import_repair_precommit(
            args,
            initial_status=initial_status,
        )
        == 0
    )
    assert commands == [
        ["scripts/check_repo_publication_ready.sh"],
        [
            "git",
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE3_H_IMPORT_REPAIR_STAGED_SCOPE),
        ],
    ]
    assert generic_calls == [_closure_phase3_h_name_status()]
    assert reports[0]["staged_status"] == (
        _closure_phase3_h_import_repair_name_status()
    )
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_push_result"] is None
    assert all("push" not in command for command in commands)


def test_closure_phase3_h_import_repair_rollback_is_directed(
    monkeypatch,
    capsys,
) -> None:
    commands: list[list[str]] = []
    physical = ("sealed-final-exact40",)
    repair_physical = ("sealed-e10-inventory-repair-exact5",)
    outcome = (1, 2, 0o644, 1, 0, 3, 4, "a" * 40)

    monkeypatch.setattr(
        precommit_artifacts,
        "run_command",
        lambda command, **_kwargs: (
            commands.append(command)
            or precommit_artifacts.CommandResult(command, 0, "", "")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *command: (
            _closure_phase3_h_import_repair_short_status(staged=False)
            if command == ("status", "--short", "--untracked-files=all")
            else ""
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_import_repair_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_import_repair_files",
        lambda **_kwargs: repair_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: outcome,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_unpublished_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )

    assert (
        precommit_artifacts._abort_closure_phase3_h_post_add(
            RuntimeError("synthetic import repair failure"),
            mode="import_repair",
            physical_before=physical,
            amend_before=repair_physical,
            outcome_log_before=outcome,
            dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            dvc_status_before={},
            artifacts=[],
            unmanaged_before=[],
            repo_root=Path("."),
        )
        == 2
    )
    assert commands == [
        [
            "git",
            "restore",
            "--staged",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE3_H_IMPORT_REPAIR_STAGED_SCOPE),
        ]
    ]
    assert "restored the exact unstaged scope" in capsys.readouterr().err


def _exercise_phase3_h_post_add_rollback(
    monkeypatch,
    *,
    mode: str,
    failure: str,
) -> tuple[int, list[list[str]], dict[str, bool]]:
    args = _closure_phase3_h_args()
    is_amend = mode == "amend"
    initial_status = (
        _closure_phase3_h_amend_short_status(staged=False)
        if is_amend
        else _closure_phase3_h_short_status(staged=False)
    )
    state = {"staged": False, "report_written": False}
    commands: list[list[str]] = []
    physical = ("sealed-final-exact40",)
    amend_physical = ("sealed-amend-exact13",)
    outcome = (1, 2, 0o644, 1, 0, 3, 4, "a" * 40)
    validation_calls = 0

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase3_h_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_amend_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_h_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_amend_files",
        lambda **_kwargs: amend_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: outcome,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_unpublished_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path(f"tmp/phase3-h-{mode}-rollback-test.md"),
    )

    def validate_staged(**_kwargs: Any) -> tuple[str, ...]:
        nonlocal validation_calls
        validation_calls += 1
        if failure == "recapture" and validation_calls == 2:
            raise OSError("synthetic post-report recapture failure")
        return physical

    monkeypatch.setattr(
        precommit_artifacts,
        (
            "validate_closure_phase3_h_amend_staged_transaction"
            if is_amend
            else "validate_closure_phase3_h_staged_transaction"
        ),
        validate_staged,
    )

    def git_output(_root: Path, *command: str) -> str:
        if command == ("status", "--short", "--untracked-files=all"):
            if is_amend:
                return _closure_phase3_h_amend_short_status(
                    staged=state["staged"]
                )
            return _closure_phase3_h_short_status(staged=state["staged"])
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            if not state["staged"]:
                return ""
            return (
                _closure_phase3_h_amend_name_status()
                if is_amend
                else _closure_phase3_h_name_status()
            )
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
            precommit_artifacts.CLOSURE_PHASE3_H_BASE_COMMIT,
        ):
            assert is_amend and state["staged"]
            return _closure_phase3_h_name_status()
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    expected_scope = (
        precommit_artifacts.CLOSURE_PHASE3_H_AMEND_STAGED_SCOPE
        if is_amend
        else precommit_artifacts.CLOSURE_PHASE3_H_STAGED_SCOPE
    )

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        if command == ["scripts/check_repo_publication_ready.sh"]:
            return precommit_artifacts.CommandResult(command, 0, "PASS", "")
        if command == ["git", "add", "-A", "--", *sorted(expected_scope)]:
            state["staged"] = True
            return precommit_artifacts.CommandResult(
                command,
                7 if failure == "git_add" else 0,
                "",
                "synthetic partial git add" if failure == "git_add" else "",
            )
        if command == [
            "git",
            "restore",
            "--staged",
            "--",
            *sorted(expected_scope),
        ]:
            state["staged"] = False
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)

    def generic(**_kwargs: Any) -> list[Any]:
        level = "warn" if failure == "generic" else "ok"
        return [
            precommit_artifacts.ReproducibilityFinding(
                level,
                "synthetic",
                "-",
                "synthetic generic finding",
            )
        ]

    monkeypatch.setattr(precommit_artifacts, "reproducibility_checks", generic)

    def write_report(_path: Path, **_kwargs: Any) -> None:
        if failure == "write_report":
            raise OSError("synthetic report failure")
        state["report_written"] = True

    monkeypatch.setattr(precommit_artifacts, "write_report", write_report)
    runner = (
        precommit_artifacts._run_closure_phase3_h_amend_precommit
        if is_amend
        else precommit_artifacts._run_closure_phase3_h_precommit
    )
    result = runner(args, initial_status=initial_status)
    return result, commands, state


@pytest.mark.parametrize(
    "failure",
    ["git_add", "generic", "write_report", "recapture"],
)
def test_closure_phase3_h_amend_post_add_failure_restores_exact13_unstaged(
    monkeypatch,
    capsys,
    failure: str,
) -> None:
    result, commands, state = _exercise_phase3_h_post_add_rollback(
        monkeypatch,
        mode="amend",
        failure=failure,
    )
    expected_restore = [
        "git",
        "restore",
        "--staged",
        "--",
        *sorted(precommit_artifacts.CLOSURE_PHASE3_H_AMEND_STAGED_SCOPE),
    ]
    assert result == 2
    assert commands[-1] == expected_restore
    assert state["staged"] is False
    assert all("reset" not in command and "checkout" not in command for command in commands)
    assert "restored the exact unstaged scope" in capsys.readouterr().err


def test_closure_phase3_full_h_post_add_failure_restores_exact40_unstaged(
    monkeypatch,
    capsys,
) -> None:
    result, commands, state = _exercise_phase3_h_post_add_rollback(
        monkeypatch,
        mode="full",
        failure="generic",
    )
    expected_restore = [
        "git",
        "restore",
        "--staged",
        "--",
        *sorted(precommit_artifacts.CLOSURE_PHASE3_H_STAGED_SCOPE),
    ]
    assert result == 2
    assert commands[-1] == expected_restore
    assert state["staged"] is False
    assert "restored the exact unstaged scope" in capsys.readouterr().err


def test_closure_phase3_h_rollback_failure_reports_primary_and_rollback_errors(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        precommit_artifacts,
        "run_command",
        lambda command, **_kwargs: precommit_artifacts.CommandResult(
            command,
            9,
            "",
            "synthetic restore rejection",
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda *_args: "M\tforeign-path\n",
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: ("drifted",),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_amend_files",
        lambda **_kwargs: ("drifted",),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: (1, 2, 0o644, 1, 0, 3, 4, "a" * 40),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_unpublished_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )

    result = precommit_artifacts._abort_closure_phase3_h_post_add(
        RuntimeError("primary synthetic failure"),
        mode="amend",
        physical_before=("sealed",),
        amend_before=("sealed-amend",),
        outcome_log_before=(1, 2, 0o644, 1, 0, 3, 4, "a" * 40),
        dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
        dvc_status_before={},
        artifacts=[],
        unmanaged_before=[],
        repo_root=Path("."),
    )
    error = capsys.readouterr().err
    assert result == 2
    assert "primary synthetic failure" in error
    assert "ROLLBACK FAILED CLOSED" in error
    assert "synthetic restore rejection" in error


def test_closure_phase3_h_rollback_preserves_concurrent_foreign_staged_path(
    monkeypatch,
    capsys,
) -> None:
    commands: list[list[str]] = []
    foreign_staged = {"present": True}
    physical = ("sealed-final-exact40",)
    amend_physical = ("sealed-amend-exact13",)
    outcome = (1, 2, 0o644, 1, 0, 3, 4, "a" * 40)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        assert "foreign-path" not in command
        return precommit_artifacts.CommandResult(command, 0, "", "")

    def git_output(_root: Path, *command: str) -> str:
        if command == ("status", "--short", "--untracked-files=all"):
            return "M  foreign-path\n"
        if command == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            assert foreign_staged["present"]
            return "M\tforeign-path\n"
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase3_h_amend_files",
        lambda **_kwargs: amend_physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase3_h_outcome_log_identity",
        lambda **_kwargs: outcome,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase3_h_unpublished_paths_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "unmanaged_ignored_heavy_paths",
        lambda _artifacts: [],
    )

    result = precommit_artifacts._abort_closure_phase3_h_post_add(
        RuntimeError("primary synthetic failure"),
        mode="amend",
        physical_before=physical,
        amend_before=amend_physical,
        outcome_log_before=outcome,
        dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
        dvc_status_before={},
        artifacts=[],
        unmanaged_before=[],
        repo_root=Path("."),
    )

    assert result == 2
    assert foreign_staged["present"]
    assert commands == [
        [
            "git",
            "restore",
            "--staged",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE3_H_AMEND_STAGED_SCOPE),
        ]
    ]
    error = capsys.readouterr().err
    assert "primary synthetic failure" in error
    assert "ROLLBACK FAILED CLOSED" in error
    assert "did not restore the exact fully-unstaged scope" in error


def _closure_phase4_h_syn_short_status(*, staged: bool) -> str:
    expected = precommit_artifacts._closure_phase4_h_syn_expected_short_scope(
        staged=staged
    )
    return "\n".join(
        f"{status_code} {path}"
        for path, status_code in sorted(expected.items())
    )


def _closure_phase4_h_syn_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE4_H_SYN_STAGED_SCOPE.items()
        )
    )


def _closure_phase4_h_syn_ref_output(*args: str) -> str:
    if args and args[0] == "rev-parse":
        return precommit_artifacts.CLOSURE_PHASE4_SOURCE_COMMIT + "\n"
    if args == ("symbolic-ref", "--quiet", "HEAD"):
        return "refs/heads/main\n"
    if args == (
        "symbolic-ref",
        "--quiet",
        "refs/remotes/origin/HEAD",
    ):
        return "refs/remotes/origin/main\n"
    raise AssertionError(args)


def test_closure_phase4_h_syn_selector_is_exact9a2m_on_phase3_source(
    monkeypatch,
) -> None:
    scope = precommit_artifacts.CLOSURE_PHASE4_H_SYN_STAGED_SCOPE
    assert precommit_artifacts.CLOSURE_PHASE4_SOURCE_COMMIT == (
        "ea8ddce7f8edb9a61db97e29178e52603fa371b1"
    )
    assert len(scope) == 11
    assert sum(status == "A" for status in scope.values()) == 9
    assert sum(status == "M" for status in scope.values()) == 2
    assert precommit_artifacts.CLOSURE_PHASE4_H_SYN_MARKER_PATHS == frozenset(
        scope
    )
    assert (
        precommit_artifacts.CLOSURE_PHASE4_H_SYN_GIT_MODES[
            "src/data/prepare_commit_artifacts.py"
        ]
        == "100755"
    )
    assert all(
        mode == "100644"
        for path, mode in (
            precommit_artifacts.CLOSURE_PHASE4_H_SYN_GIT_MODES.items()
        )
        if path != "src/data/prepare_commit_artifacts.py"
    )
    assert precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_PRECOMMIT_GUARD == Path(
        "tmp/closure_v1_phase4_editorial_precommit.guard"
    )
    assert not precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_PRECOMMIT_GUARD.is_relative_to(
        precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_BUILD_ROOT
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: _closure_phase4_h_syn_ref_output(*args),
    )
    status = _closure_phase4_h_syn_short_status(staged=False)
    assert precommit_artifacts.closure_phase4_h_syn_pre_stage_scope(
        status,
        "",
    )

    missing = sorted(
        precommit_artifacts.CLOSURE_PHASE4_H_SYN_MARKER_PATHS
    )[0]
    partial = "\n".join(
        line for line in status.splitlines() if not line.endswith(missing)
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4HSynPrecommitAdapterError,
        match=r"exact 9A\+2M",
    ):
        precommit_artifacts.closure_phase4_h_syn_pre_stage_scope(partial, "")


def test_closure_phase4_h_syn_selector_rejects_wrong_parent_before_generic(
    monkeypatch,
) -> None:
    wrong = "0" * 40
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            wrong + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4HSynPrecommitAdapterError,
        match="not based on exact source",
    ):
        precommit_artifacts.closure_phase4_h_syn_pre_stage_scope(
            _closure_phase4_h_syn_short_status(staged=False),
            "",
        )


def test_closure_phase4_live_remote_requires_exact_head_and_main(
    monkeypatch,
) -> None:
    expected = precommit_artifacts.CLOSURE_PHASE4_SOURCE_COMMIT
    observed: list[list[str]] = []

    def exact_remote(command: list[str], **_kwargs: Any) -> Any:
        observed.append(command)
        return precommit_artifacts.CommandResult(
            command,
            0,
            f"{expected}\tHEAD\n{expected}\trefs/heads/main\n",
            "",
        )

    monkeypatch.setattr(precommit_artifacts, "run_command", exact_remote)
    precommit_artifacts._require_closure_phase4_h_syn_live_remote(
        repo_root=Path(".")
    )
    precommit_artifacts._require_closure_phase4_live_remote(
        expected,
        repo_root=Path("."),
    )
    assert observed[0] == [
        "git",
        "-C",
        ".",
        "ls-remote",
        "origin",
        "HEAD",
        "refs/heads/main",
    ]

    def main_only(command: list[str], **_kwargs: Any) -> Any:
        return precommit_artifacts.CommandResult(
            command,
            0,
            f"{expected}\trefs/heads/main\n",
            "",
        )

    monkeypatch.setattr(precommit_artifacts, "run_command", main_only)
    with pytest.raises(
        precommit_artifacts.ClosurePhase4HSynPrecommitAdapterError,
        match="HEAD and main",
    ):
        precommit_artifacts._require_closure_phase4_h_syn_live_remote(
            repo_root=Path(".")
        )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match="HEAD and main",
    ):
        precommit_artifacts._require_closure_phase4_live_remote(
            expected,
            repo_root=Path("."),
        )


def test_closure_phase4_h_syn_invocation_forbids_dvc_mutation() -> None:
    args = _closure_phase3_h_args()
    environment = {"DVC_NO_ANALYTICS": "1"}
    precommit_artifacts.validate_closure_phase4_h_syn_invocation(
        args,
        env=environment,
    )

    args.target = ["data/forbidden.parquet"]
    with pytest.raises(
        precommit_artifacts.ClosurePhase4HSynPrecommitAdapterError,
        match="empty DVC target set",
    ):
        precommit_artifacts.validate_closure_phase4_h_syn_invocation(
            args,
            env=environment,
        )


def test_closure_phase4_h_syn_forbids_every_future_namespace(
    tmp_path: Path,
) -> None:
    for forbidden in (
        precommit_artifacts.CLOSURE_PHASE4_H_SYN_FORBIDDEN_FUTURE_PATHS
    ):
        root = tmp_path / forbidden.as_posix().replace("/", "_")
        root.mkdir()
        candidate = root / forbidden
        candidate.parent.mkdir(parents=True)
        if forbidden.suffix:
            candidate.write_text("premature\n", encoding="utf-8")
        else:
            candidate.mkdir()
        with pytest.raises(
            precommit_artifacts.ClosurePhase4HSynPrecommitAdapterError,
            match="premature P-SYN/R-SYN",
        ):
            precommit_artifacts._require_closure_phase4_h_syn_future_namespace_absent(
                repo_root=root
            )


def test_closure_phase4_h_syn_future_namespace_walk_does_not_follow_symlinks(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "repo"
    root.mkdir()
    (root / "configs").symlink_to(outside, target_is_directory=True)

    with pytest.raises(
        precommit_artifacts.ClosurePhase4HSynPrecommitAdapterError,
        match="unsafe non-directory ancestor",
    ):
        precommit_artifacts._require_closure_phase4_h_syn_future_namespace_absent(
            repo_root=root
        )


def test_closure_phase4_h_syn_staged_transaction_binds_modes_and_blobs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    blob_oids: dict[str, str] = {}
    for raw_path, git_mode in (
        precommit_artifacts.CLOSURE_PHASE4_H_SYN_GIT_MODES.items()
    ):
        path = tmp_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"phase4-h-syn:{raw_path}\n".encode()
        path.write_bytes(payload)
        path.chmod(0o755 if git_mode == "100755" else 0o644)
        blob_oids[raw_path] = hashlib.sha1(
            f"blob {len(payload)}\0".encode() + payload,
            usedforsecurity=False,
        ).hexdigest()

    index_oids = dict(blob_oids)

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase4_h_syn_name_status()
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase4_h_syn_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        if args[:3] == ("ls-files", "-s", "--"):
            raw_path = args[3]
            return (
                f"{precommit_artifacts.CLOSURE_PHASE4_H_SYN_GIT_MODES[raw_path]} "
                f"{index_oids[raw_path]} 0\t{raw_path}\n"
            )
        if args[:3] == ("hash-object", "--no-filters", "--"):
            return blob_oids[args[3]] + "\n"
        return _closure_phase4_h_syn_ref_output(*args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    records = (
        precommit_artifacts.validate_closure_phase4_h_syn_staged_transaction(
            repo_root=tmp_path
        )
    )
    assert len(records) == 11
    assert sum(record.mode == 0o755 for record in records) == 1
    assert all(record.nlink == 1 for record in records)

    first = sorted(index_oids)[0]
    index_oids[first] = "0" * 40
    with pytest.raises(
        precommit_artifacts.ClosurePhase4HSynPrecommitAdapterError,
        match="mode/blob binding drifted",
    ):
        precommit_artifacts.validate_closure_phase4_h_syn_staged_transaction(
            repo_root=tmp_path
        )


def test_closure_phase4_h_syn_main_precedes_phase3_and_generic(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_h2_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_h_syn_precommit",
        lambda *_args, **_kwargs: 113,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase3_recovery_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Phase 3 selector must not run after H-SYN match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "versionable_changes",
        lambda: (_ for _ in ()).throw(
            AssertionError("generic flow must not run after H-SYN match")
        ),
    )

    assert precommit_artifacts.main() == 113


def test_closure_phase4_h_syn_transaction_stages_only_exact11_without_dvc(
    monkeypatch,
) -> None:
    args = _closure_phase3_h_args()
    initial_status = _closure_phase4_h_syn_short_status(staged=False)
    state = {"staged": False}
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    physical = tuple(
        precommit_artifacts.RegistrationFileIdentity(
            path,
            1,
            index + 1,
            0o755
            if path == "src/data/prepare_commit_artifacts.py"
            else 0o644,
            1,
            10,
            "a" * 64,
            20,
            30,
        )
        for index, path in enumerate(
            sorted(precommit_artifacts.CLOSURE_PHASE4_H_SYN_STAGED_SCOPE)
        )
    )

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_h_syn_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_h_syn_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_future_namespace_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_live_remote",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_h_syn_staged_transaction",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase4-h-syn-test.md"),
    )
    publication_calls: list[Path] = []

    def publication_check(*, repo_root: Path) -> Any:
        publication_calls.append(repo_root)
        command = ["scripts/check_repo_publication_ready.sh"]
        return precommit_artifacts.CommandResult(
            command,
            1,
            "exact sealed-runtime exception",
            "",
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_h_syn_publication_check",
        publication_check,
    )

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return (
                _closure_phase4_h_syn_name_status()
                if state["staged"]
                else ""
            )
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase4_h_syn_short_status(
                staged=state["staged"]
            )
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        if command[:4] == ["git", "add", "-A", "--"]:
            state["staged"] = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(
        precommit_artifacts,
        "reproducibility_checks",
        lambda **_kwargs: [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "passed"
            )
        ],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase4_h_syn_precommit(
            args,
            initial_status=initial_status,
        )
        == 0
    )
    assert publication_calls == [Path(".")]
    assert commands == [
        [
            "git",
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE4_H_SYN_STAGED_SCOPE),
        ],
    ]
    assert all("dvc" not in part and "push" not in part for cmd in commands for part in cmd)
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_push_result"] is None
    assert reports[0]["exclusive"] is True
    assert reports[0]["publication_check_result"].returncode == 0
    assert "U1/U2/U3" in reports[0]["publication_check_result"].stdout


def test_closure_phase4_h_syn_publication_fails_beyond_exact_u1_u2_u3(
    monkeypatch,
    capsys,
) -> None:
    args = _closure_phase3_h_args()
    initial_status = _closure_phase4_h_syn_short_status(staged=False)
    physical = tuple(
        precommit_artifacts.RegistrationFileIdentity(
            path,
            1,
            index + 1,
            0o755
            if path == "src/data/prepare_commit_artifacts.py"
            else 0o644,
            1,
            10,
            "a" * 64,
            20,
            30,
        )
        for index, path in enumerate(
            sorted(precommit_artifacts.CLOSURE_PHASE4_H_SYN_STAGED_SCOPE)
        )
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_h_syn_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_live_remote",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_h_syn_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_future_namespace_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            ""
            if args
            == ("diff", "--cached", "--name-status", "--no-renames")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_h_syn_publication_check",
        lambda **_kwargs: (_ for _ in ()).throw(
            precommit_artifacts.ClosurePhase4HSynPrecommitAdapterError(
                "unexpected non-English text"
            )
        ),
    )

    assert (
        precommit_artifacts._run_closure_phase4_h_syn_precommit(
            args,
            initial_status=initial_status,
        )
        == 2
    )
    error = capsys.readouterr().err
    assert "failed beyond the exact published U1/U2/U3" in error
    assert "unexpected non-English text" in error


def test_closure_phase4_h_syn_sealed_runtime_exception_is_exact(
    monkeypatch,
) -> None:
    sealed_home = "/" + "home" + "/" + "zero"
    payload = (
        json.dumps(
            {
                "sealed_runtime_environment_record": {
                    "purelib_path": (
                        sealed_home
                        + "/repos/lentic-pipe/.venv/lib/python3.14/site-packages"
                    ),
                    "python_executable": {
                        "link_path": (
                            sealed_home + "/repos/lentic-pipe/.venv/bin/python"
                        )
                    },
                }
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()

    paths = sorted(
        (
            precommit_artifacts.CLOSURE_E0_U_ACTIVATION_PATH.as_posix(),
            precommit_artifacts.CLOSURE_E0_U_RECOVERY_ACTIVATION_PATH.as_posix(),
            precommit_artifacts.CLOSURE_E0_U_RECOVERY_2_ACTIVATION_PATH.as_posix(),
        )
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_h_syn_publication_payloads",
        lambda **_kwargs: {path: payload for path in paths},
    )
    payload_line = payload[:-1].decode()
    expected_stdout = (
        "Checking tracked files before publication...\n\n"
        "Local absolute paths found in versionable files:\n"
        + "\n".join(f"{path}:1:{payload_line}" for path in paths)
        + "\n\nPublication readiness check failed.\n"
    )
    extra_finding = {"present": False}

    def run(command: list[str], **_kwargs: Any) -> Any:
        assert command == ["scripts/check_repo_publication_ready.sh"]
        stdout = expected_stdout
        if extra_finding["present"]:
            stdout = stdout.replace(
                "\nPublication readiness check failed.\n",
                "\nNon-English repository text found in versionable files:\n"
                "candidate.py:1:unexpected\n\n"
                "Publication readiness check failed.\n",
            )
        return precommit_artifacts.CommandResult(command, 1, stdout, "")

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    result = (
        precommit_artifacts._run_closure_phase4_h_syn_publication_check(
            repo_root=Path("."),
        )
    )
    assert result.stdout == expected_stdout

    extra_finding["present"] = True
    with pytest.raises(
        precommit_artifacts.ClosurePhase4HSynPrecommitAdapterError,
        match="failed beyond the exact Git-bound U1/U2/U3",
    ):
        precommit_artifacts._run_closure_phase4_h_syn_publication_check(
            repo_root=Path("."),
        )


def test_closure_phase4_h_syn_rollback_is_directed_and_preserves_foreign(
    monkeypatch,
) -> None:
    commands: list[list[str]] = []
    physical = tuple()

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        assert "foreign-path" not in command
        return precommit_artifacts.CommandResult(command, 0, "", "")

    def git_output(_root: Path, *args: str) -> str:
        if args == ("status", "--short", "--untracked-files=all"):
            return "M  foreign-path\n"
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return "M\tforeign-path\n"
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_h_syn_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_future_namespace_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})

    error = precommit_artifacts._rollback_closure_phase4_h_syn_staging(
        physical_before=physical,
        dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
        dvc_status_before={},
        repo_root=Path("."),
    )
    assert error is not None
    assert "exact11 fully unstaged" in error
    assert commands == [
        [
            "git",
            "restore",
            "--staged",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE4_H_SYN_STAGED_SCOPE),
        ]
    ]


def _closure_phase4_h_syn_h2_short_status(*, staged: bool) -> str:
    expected = (
        precommit_artifacts._closure_phase4_h_syn_h2_expected_short_scope(
            staged=staged
        )
    )
    return "\n".join(
        f"{status_code} {path}"
        for path, status_code in sorted(expected.items())
    )


def _closure_phase4_h_syn_h2_name_status() -> str:
    return "\n".join(
        f"{status_code}\t{path}"
        for path, status_code in sorted(
            precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_STAGED_SCOPE.items()
        )
    )


def test_closure_phase4_h_syn_h2_selector_is_exact5m_on_published_h1(
    monkeypatch,
) -> None:
    scope = precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_STAGED_SCOPE
    assert precommit_artifacts.CLOSURE_PHASE4_H_SYN_H1_COMMIT == (
        "89f931aea9a4eeb8c468b697cd858eacbfd268f6"
    )
    assert len(scope) == 5
    assert set(scope.values()) == {"M"}
    assert set(scope).issubset(
        precommit_artifacts.CLOSURE_PHASE4_H_SYN_STAGED_SCOPE
    )
    assert precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_MARKER_PATHS == (
        frozenset(scope)
    )
    assert (
        precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_GIT_MODES[
            "src/data/prepare_commit_artifacts.py"
        ]
        == "100755"
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            precommit_artifacts.CLOSURE_PHASE4_H_SYN_H1_COMMIT + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_h2_base_refs",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_h2_aggregate_scope",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_future_namespace_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_h2_live_remote",
        lambda **_kwargs: None,
    )
    exact = _closure_phase4_h_syn_h2_short_status(staged=False)
    assert precommit_artifacts.closure_phase4_h_syn_h2_pre_stage_scope(
        exact,
        "",
    )

    partial = "\n".join(exact.splitlines()[:-1])
    with pytest.raises(
        precommit_artifacts.ClosurePhase4HSynH2PrecommitAdapterError,
        match="exact5M",
    ):
        precommit_artifacts.closure_phase4_h_syn_h2_pre_stage_scope(
            partial,
            "",
        )


def test_closure_phase4_h_syn_h2_binds_h1_refs_remote_and_aggregate(
    monkeypatch,
) -> None:
    observed: list[tuple[str, Any]] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_h1_history",
        lambda **_kwargs: observed.append(("history", None)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_publication_refs",
        lambda commit, **_kwargs: observed.append(("refs", commit)),
    )
    precommit_artifacts._require_closure_phase4_h_syn_h2_base_refs(
        repo_root=Path(".")
    )
    assert observed == [
        ("history", None),
        ("refs", precommit_artifacts.CLOSURE_PHASE4_H_SYN_H1_COMMIT),
    ]

    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            _closure_phase4_h_syn_name_status()
            if args
            == (
                "diff",
                "--name-status",
                "--no-renames",
                precommit_artifacts.CLOSURE_PHASE4_SOURCE_COMMIT,
                "--",
            )
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    precommit_artifacts._require_closure_phase4_h_syn_h2_aggregate_scope(
        repo_root=Path(".")
    )

    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_live_remote_matches",
        lambda commit, **_kwargs: commit
        == precommit_artifacts.CLOSURE_PHASE4_H_SYN_H1_COMMIT,
    )
    precommit_artifacts._require_closure_phase4_h_syn_h2_live_remote(
        repo_root=Path(".")
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_live_remote_matches",
        lambda *_args, **_kwargs: False,
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4HSynH2PrecommitAdapterError,
        match="live origin HEAD and main",
    ):
        precommit_artifacts._require_closure_phase4_h_syn_h2_live_remote(
            repo_root=Path(".")
        )


def test_closure_phase4_h_syn_h2_staged_transaction_binds_exact5_blobs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    blob_oids: dict[str, str] = {}
    for raw_path, git_mode in (
        precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_GIT_MODES.items()
    ):
        path = tmp_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"phase4-h-syn-h2:{raw_path}\n".encode()
        path.write_bytes(payload)
        path.chmod(0o755 if git_mode == "100755" else 0o644)
        blob_oids[raw_path] = hashlib.sha1(
            f"blob {len(payload)}\0".encode() + payload,
            usedforsecurity=False,
        ).hexdigest()
    index_oids = dict(blob_oids)

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase4_h_syn_h2_name_status()
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase4_h_syn_h2_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        if args[:3] == ("ls-files", "-s", "--"):
            raw_path = args[3]
            mode = precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_GIT_MODES[
                raw_path
            ]
            return f"{mode} {index_oids[raw_path]} 0\t{raw_path}\n"
        if args[:3] == ("hash-object", "--no-filters", "--"):
            return blob_oids[args[3]] + "\n"
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_h2_base_refs",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_h2_aggregate_scope",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_future_namespace_absent",
        lambda **_kwargs: None,
    )
    records = (
        precommit_artifacts.validate_closure_phase4_h_syn_h2_staged_transaction(
            repo_root=tmp_path
        )
    )
    assert len(records) == 5
    assert sum(record.mode == 0o755 for record in records) == 1

    first = sorted(index_oids)[0]
    index_oids[first] = "0" * 40
    with pytest.raises(
        precommit_artifacts.ClosurePhase4HSynH2PrecommitAdapterError,
        match="staged mode/blob binding drifted",
    ):
        precommit_artifacts.validate_closure_phase4_h_syn_h2_staged_transaction(
            repo_root=tmp_path
        )


def test_closure_phase4_published_h_requires_h1_then_h2_and_final_bindings(
    monkeypatch,
) -> None:
    h2 = "2" * 40
    calls: list[str] = []

    def parents(commit: str, **_kwargs: Any) -> tuple[str, ...]:
        if commit == precommit_artifacts.CLOSURE_PHASE4_H_SYN_H1_COMMIT:
            return (precommit_artifacts.CLOSURE_PHASE4_SOURCE_COMMIT,)
        if commit == h2:
            return (precommit_artifacts.CLOSURE_PHASE4_H_SYN_H1_COMMIT,)
        raise AssertionError(commit)

    def scope(commit: str, **_kwargs: Any) -> dict[str, str]:
        if commit == precommit_artifacts.CLOSURE_PHASE4_H_SYN_H1_COMMIT:
            return dict(precommit_artifacts.CLOSURE_PHASE4_H_SYN_STAGED_SCOPE)
        if commit == h2:
            return dict(
                precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_STAGED_SCOPE
            )
        raise AssertionError(commit)

    monkeypatch.setattr(
        precommit_artifacts, "_closure_phase4_commit_parents", parents
    )
    monkeypatch.setattr(
        precommit_artifacts, "_closure_phase4_commit_scope", scope
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_range_scope",
        lambda base, tip, **_kwargs: (
            dict(precommit_artifacts.CLOSURE_PHASE4_H_SYN_STAGED_SCOPE)
            if (
                base == precommit_artifacts.CLOSURE_PHASE4_SOURCE_COMMIT
                and tip == h2
            )
            else (_ for _ in ()).throw(AssertionError((base, tip)))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_h2_final_bindings",
        lambda commit, **_kwargs: calls.append(commit),
    )
    precommit_artifacts._require_closure_phase4_published_h(
        h2,
        repo_root=Path("."),
    )
    assert calls == [h2]

    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_range_scope",
        lambda *_args, **_kwargs: {},
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match=r"cumulative 9A\+2M",
    ):
        precommit_artifacts._require_closure_phase4_published_h(
            h2,
            repo_root=Path("."),
        )


def test_closure_phase4_h_syn_h2_final_bindings_use_h2_tree_blobs(
    monkeypatch,
) -> None:
    h2 = "2" * 40
    oids = {
        path: f"{index + 1:040x}"
        for index, path in enumerate(
            sorted(precommit_artifacts.CLOSURE_PHASE4_H_SYN_GIT_MODES)
        )
    }
    drift = {"path": None}

    def git_output(_root: Path, *args: str) -> str:
        if args[:2] == ("ls-tree", h2):
            raw_path = args[3]
            oid = oids[raw_path]
            mode = precommit_artifacts.CLOSURE_PHASE4_H_SYN_GIT_MODES[
                raw_path
            ]
            return f"{mode} blob {oid}\t{raw_path}\n"
        if args[:3] == ("ls-files", "-s", "--"):
            raw_path = args[3]
            oid = "0" * 40 if drift["path"] == raw_path else oids[raw_path]
            mode = precommit_artifacts.CLOSURE_PHASE4_H_SYN_GIT_MODES[
                raw_path
            ]
            return f"{mode} {oid} 0\t{raw_path}\n"
        if args[:3] == ("hash-object", "--no-filters", "--"):
            return oids[args[3]] + "\n"
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    precommit_artifacts._require_closure_phase4_h_syn_h2_final_bindings(
        h2,
        repo_root=Path("."),
    )
    drift["path"] = sorted(oids)[0]
    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match="final H-SYN H2 mode/blob binding drifted",
    ):
        precommit_artifacts._require_closure_phase4_h_syn_h2_final_bindings(
            h2,
            repo_root=Path("."),
        )


def test_closure_phase4_h_syn_h2_main_precedes_h1_and_generic(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_syn_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_p_syn_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_h2_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_h_syn_h2_precommit",
        lambda *_args, **_kwargs: 137,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("H1 selector must not run after H2 match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "versionable_changes",
        lambda: (_ for _ in ()).throw(
            AssertionError("generic flow must not run after H2 match")
        ),
    )
    assert precommit_artifacts.main() == 137


def test_closure_phase4_h_syn_h2_transaction_exact5m_no_dvc(
    monkeypatch,
) -> None:
    args = _closure_phase3_h_args()
    initial_status = _closure_phase4_h_syn_h2_short_status(staged=False)
    state = {"staged": False}
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    physical = tuple(
        precommit_artifacts.RegistrationFileIdentity(
            path,
            1,
            index + 1,
            0o755
            if path == "src/data/prepare_commit_artifacts.py"
            else 0o644,
            1,
            10,
            "a" * 64,
            20,
            30,
        )
        for index, path in enumerate(
            sorted(precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_STAGED_SCOPE)
        )
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_h_syn_h2_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_h2_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_h2_live_remote",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_h_syn_h2_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_h_syn_h2_staged_transaction",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase4-h-syn-h2-test.md"),
    )
    publication_calls: list[Path] = []

    def publication_check(*, repo_root: Path) -> Any:
        publication_calls.append(repo_root)
        command = ["scripts/check_repo_publication_ready.sh"]
        return precommit_artifacts.CommandResult(
            command, 1, "exact U1/U2/U3", ""
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_h_syn_publication_check",
        publication_check,
    )

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return (
                _closure_phase4_h_syn_h2_name_status()
                if state["staged"]
                else ""
            )
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase4_h_syn_h2_short_status(
                staged=state["staged"]
            )
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        if command[:4] == ["git", "add", "-A", "--"]:
            state["staged"] = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(
        precommit_artifacts,
        "reproducibility_checks",
        lambda **_kwargs: [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "passed"
            )
        ],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase4_h_syn_h2_precommit(
            args,
            initial_status=initial_status,
        )
        == 0
    )
    assert publication_calls == [Path(".")]
    assert commands == [
        [
            "git",
            "add",
            "-A",
            "--",
            *sorted(
                precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_STAGED_SCOPE
            ),
        ]
    ]
    assert reports[0]["publication_check_result"].returncode == 0
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_push_result"] is None


def test_closure_phase4_h_syn_h2_rollback_preserves_foreign_index(
    monkeypatch,
) -> None:
    scope = precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_STAGED_SCOPE
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        assert "foreign-path" not in command
        return precommit_artifacts.CommandResult(command, 0, "", "")

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return "M\tforeign-path\n"
        if args == ("status", "--short", "--untracked-files=all"):
            return (
                _closure_phase4_h_syn_h2_short_status(staged=False)
                + "\nM  foreign-path\n"
            )
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_h_syn_h2_files",
        lambda **_kwargs: tuple(),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_future_namespace_absent",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    assert (
        precommit_artifacts._rollback_closure_phase4_h_syn_h2_staging(
            physical_before=tuple(),
            dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            dvc_status_before={},
            repo_root=Path("."),
        )
        is None
    )
    assert commands == [
        ["git", "restore", "--staged", "--", *sorted(scope)]
    ]


def _closure_phase4_publication_short_status(
    scope: Mapping[str, str], *, staged: bool
) -> str:
    expected = precommit_artifacts._expected_short_scope(
        scope,
        staged=staged,
    )
    return "\n".join(
        f"{status_code} {path}"
        for path, status_code in sorted(expected.items())
    )


def test_closure_phase4_p_syn_selector_requires_exact2a(
    monkeypatch,
) -> None:
    scope = precommit_artifacts.CLOSURE_PHASE4_P_SYN_STAGED_SCOPE
    assert scope == {
        "configs/closure_v1/phase4_synthesis_authority.json": "A",
        "configs/closure_v1/phase4_synthesis_authority_manifest.json": "A",
    }
    head = "1" * 40
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            head + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_published_h",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_publication_refs",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_live_remote",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_p_syn_no_temps",
        lambda **_kwargs: None,
    )
    status = _closure_phase4_publication_short_status(
        scope,
        staged=False,
    )
    assert precommit_artifacts.closure_phase4_p_syn_pre_stage_scope(
        status,
        "",
    )

    partial = "\n".join(status.splitlines()[:-1])
    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match="exact2A",
    ):
        precommit_artifacts.closure_phase4_p_syn_pre_stage_scope(
            partial,
            "",
        )


def test_closure_phase4_r_syn_selector_rejects_partial_and_extra(
    monkeypatch,
) -> None:
    scope = {
        "reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv": "A",
        "reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json": "A",
    }
    head = "2" * 40
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_r_syn_scope",
        lambda **_kwargs: scope,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            head + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_published_p",
        lambda *_args, **_kwargs: "1" * 40,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_publication_refs",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_live_remote",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_r_syn_namespace_exact",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_coordination_absent",
        lambda **_kwargs: None,
    )
    exact = _closure_phase4_publication_short_status(scope, staged=False)
    assert precommit_artifacts.closure_phase4_r_syn_pre_stage_scope(
        exact,
        "",
    )

    for invalid in (
        exact.splitlines()[0],
        exact + "\n?? reports/closure_v1/11_synthesis/extra.tmp",
    ):
        with pytest.raises(
            precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
            match="exact24",
        ):
            precommit_artifacts.closure_phase4_r_syn_pre_stage_scope(
                invalid,
                "",
            )


def test_closure_phase4_publication_history_rejects_false_parent(
    monkeypatch,
) -> None:
    h_commit = "1" * 40
    wrong_parent = "0" * 40
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_h_syn_h1_history",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_parents",
        lambda *_args, **_kwargs: (wrong_parent,),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_scope",
        lambda *_args, **_kwargs: dict(
            precommit_artifacts.CLOSURE_PHASE4_H_SYN_H2_STAGED_SCOPE
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_range_scope",
        lambda *_args, **_kwargs: dict(
            precommit_artifacts.CLOSURE_PHASE4_H_SYN_STAGED_SCOPE
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match=r"ea8ddce -> H1",
    ):
        precommit_artifacts._require_closure_phase4_published_h(
            h_commit,
            repo_root=Path("."),
        )

    p_commit = "2" * 40
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_parents",
        lambda *_args, **_kwargs: tuple(),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match="exactly one H-SYN parent",
    ):
        precommit_artifacts._require_closure_phase4_published_p(
            p_commit,
            repo_root=Path("."),
        )


def test_closure_phase4_publication_snapshot_rejects_symlink(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    raw_path = "configs/closure_v1/phase4_synthesis_authority.json"
    candidate = tmp_path / raw_path
    candidate.parent.mkdir(parents=True)
    candidate.symlink_to(outside)

    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match="regular|symlink",
    ):
        precommit_artifacts._snapshot_closure_phase4_publication_files(
            {raw_path: "A"},
            repo_root=tmp_path,
        )


def test_closure_phase4_r_syn_namespace_rejects_extras_and_symlinks(
    tmp_path: Path,
) -> None:
    root = tmp_path / precommit_artifacts.CLOSURE_PHASE4_SYNTHESIS_ROOT
    root.mkdir(parents=True)
    expected_path = (
        precommit_artifacts.CLOSURE_PHASE4_SYNTHESIS_ROOT
        / "FINAL_CLOSURE_MATRIX.csv"
    ).as_posix()
    (tmp_path / expected_path).write_text("header\n", encoding="utf-8")
    extra = root / "extra.tmp"
    extra.write_text("extra\n", encoding="utf-8")
    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match="exact24",
    ):
        precommit_artifacts._require_closure_phase4_r_syn_namespace_exact(
            {expected_path: "A"},
            repo_root=tmp_path,
        )

    extra.unlink()
    outside = tmp_path / "outside"
    outside.write_text("outside\n", encoding="utf-8")
    (root / "unsafe.svg").symlink_to(outside)
    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match="forbids symlinks",
    ):
        precommit_artifacts._require_closure_phase4_r_syn_namespace_exact(
            {expected_path: "A"},
            repo_root=tmp_path,
        )


def test_closure_phase4_publication_rollback_is_directed_and_preserves_foreign(
    monkeypatch,
) -> None:
    scope = dict(precommit_artifacts.CLOSURE_PHASE4_P_SYN_STAGED_SCOPE)
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        assert "foreign-path" not in command
        return precommit_artifacts.CommandResult(command, 0, "", "")

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            "M\tforeign-path\n"
            if args
            == (
                "diff",
                "--cached",
                "--name-status",
                "--no-renames",
            )
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_publication_files",
        lambda *_args, **_kwargs: tuple(),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})

    error = precommit_artifacts._rollback_closure_phase4_publication_staging(
        scope=scope,
        physical_before=tuple(),
        dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
        dvc_status_before={},
        repo_root=Path("."),
    )
    assert error is None
    assert commands == [
        ["git", "restore", "--staged", "--", *sorted(scope)]
    ]


def test_closure_phase4_r_then_p_selectors_precede_h_and_generic(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_syn_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_r_syn_precommit",
        lambda *_args, **_kwargs: 127,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_p_syn_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("P-SYN selector must not run after R-SYN match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("H-SYN selector must not run after R-SYN match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_h2_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("H2 selector must not run after R-SYN match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "versionable_changes",
        lambda: (_ for _ in ()).throw(
            AssertionError("generic flow must not run after R-SYN match")
        ),
    )
    assert precommit_artifacts.main() == 127


def test_closure_phase4_p_selector_precedes_h_and_generic(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_syn_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_p_syn_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_p_syn_precommit",
        lambda *_args, **_kwargs: 131,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("H-SYN selector must not run after P-SYN match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_h2_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("H2 selector must not run after P-SYN match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "versionable_changes",
        lambda: (_ for _ in ()).throw(
            AssertionError("generic flow must not run after P-SYN match")
        ),
    )
    assert precommit_artifacts.main() == 131


@pytest.mark.parametrize("gate", ["P-SYN", "R-SYN"])
def test_closure_phase4_publication_transaction_stages_only_owned_without_dvc(
    gate: str,
    monkeypatch,
) -> None:
    args = _closure_phase3_h_args()
    r_scope = {
        "reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv": "A",
        "reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json": "A",
    }
    scope = (
        precommit_artifacts.CLOSURE_PHASE4_P_SYN_STAGED_SCOPE
        if gate == "P-SYN"
        else r_scope
    )
    initial_status = _closure_phase4_publication_short_status(
        scope,
        staged=False,
    )
    physical = tuple(
        precommit_artifacts.RegistrationFileIdentity(
            path,
            1,
            index + 1,
            0o644,
            1,
            10,
            "a" * 64,
            20,
            30,
        )
        for index, path in enumerate(sorted(scope))
    )
    state = {"staged": False}
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_synthesis_publication_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_r_syn_scope",
        lambda **_kwargs: r_scope,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_p_syn_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_syn_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_publication_files",
        lambda *_args, **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_p_syn_payload",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_r_syn_payload",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_p_syn_staged_transaction",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_r_syn_staged_transaction",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase4-publication-test.md"),
    )
    publication_calls: list[Path] = []

    def publication_check(*, repo_root: Path) -> Any:
        publication_calls.append(repo_root)
        command = ["scripts/check_repo_publication_ready.sh"]
        return precommit_artifacts.CommandResult(
            command,
            1,
            "exact Git-bound U1/U2/U3 sealed-runtime exception",
            "",
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_h_syn_publication_check",
        publication_check,
    )

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            if not state["staged"]:
                return ""
            return "\n".join(
                f"A\t{path}" for path in sorted(scope)
            )
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase4_publication_short_status(
                scope,
                staged=state["staged"],
            )
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        if command[:4] == ["git", "add", "-A", "--"]:
            state["staged"] = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(
        precommit_artifacts,
        "reproducibility_checks",
        lambda **_kwargs: [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "passed"
            )
        ],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase4_publication_precommit(
            args,
            gate=gate,
            initial_status=initial_status,
            repo_root=Path("."),
        )
        == 0
    )
    assert publication_calls == [Path(".")]
    assert commands == [
        ["git", "add", "-A", "--", *sorted(scope)],
    ]
    assert all(
        "dvc" not in part.lower() and "push" not in part.lower()
        for command in commands
        for part in command
    )
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_push_result"] is None
    assert reports[0]["publication_check_result"].returncode == 0
    assert "U1/U2/U3" in reports[0]["publication_check_result"].stdout


@pytest.mark.parametrize("gate", ["P-SYN", "R-SYN"])
def test_closure_phase4_publication_fails_closed_on_extra_publication_finding(
    gate: str,
    monkeypatch,
    capsys,
) -> None:
    args = _closure_phase3_h_args()
    r_scope = {
        "reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv": "A",
        "reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json": "A",
    }
    scope = (
        precommit_artifacts.CLOSURE_PHASE4_P_SYN_STAGED_SCOPE
        if gate == "P-SYN"
        else r_scope
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_synthesis_publication_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_r_syn_scope",
        lambda **_kwargs: r_scope,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_p_syn_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_syn_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_publication_files",
        lambda *_args, **_kwargs: tuple(),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_p_syn_payload",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_r_syn_payload",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            ""
            if args
            == ("diff", "--cached", "--name-status", "--no-renames")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_h_syn_publication_check",
        lambda **_kwargs: (_ for _ in ()).throw(
            precommit_artifacts.ClosurePhase4HSynPrecommitAdapterError(
                "unexpected extra publication finding"
            )
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "run_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("no staging command is allowed after guard drift")
        ),
    )

    assert (
        precommit_artifacts._run_closure_phase4_publication_precommit(
            args,
            gate=gate,
            initial_status=_closure_phase4_publication_short_status(
                scope,
                staged=False,
            ),
            repo_root=Path("."),
        )
        == 2
    )
    error = capsys.readouterr().err
    assert f"{gate} publication check failed beyond" in error
    assert "unexpected extra publication finding" in error


def _phase4_payload_validator_contract() -> SimpleNamespace:
    from src.reporting import closure_synthesis_contract as synthesis

    return SimpleNamespace(
        allowed_input_paths=tuple(),
        output_paths=tuple(synthesis.OUTPUT_PATHS),
        required_unavailable_models=("P0", "P1", "A2"),
        required_hypotheses=("H1", "H2", "H3", "H4", "H5a", "H5b"),
        holm_universes={"A": 3, "B": 78, "C": 1, "D": 9, "E": 1},
        final_closure_row_count=130,
        claim_evidence_row_count=20,
        table_row_counts={f"T{index:02d}": index for index in range(1, 13)},
    )


def test_closure_phase4_p_payload_reconstruction_passes_all_sealed_counts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.experiments import lock_closure_synthesis as locker
    from src.reporting import build_closure_synthesis as builder
    from src.reporting import closure_synthesis_contract as synthesis

    contract = _phase4_payload_validator_contract()
    authority_path = tmp_path / locker.AUTHORITY_PATH
    manifest_path = tmp_path / locker.MANIFEST_PATH
    authority_path.parent.mkdir(parents=True)
    authority_path.write_bytes(synthesis.canonical_json_bytes({}))
    manifest_path.write_bytes(synthesis.canonical_json_bytes({}))
    captured: dict[str, Any] = {}

    monkeypatch.setattr(synthesis, "load_contract", lambda **_kwargs: contract)
    monkeypatch.setattr(synthesis, "collect_input_records", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(locker, "H_SCOPE", {})
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            "1" * 40 + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )

    def spy_build_authority(state: Mapping[str, Any]) -> Mapping[str, Any]:
        captured.update(state)
        raise RuntimeError("stop after P-SYN expected_state capture")

    monkeypatch.setattr(locker, "_build_authority", spy_build_authority)
    monkeypatch.setattr(locker, "validate_authority", lambda _payload: None)
    monkeypatch.setattr(builder, "validate_authority", lambda *_args, **_kwargs: {})

    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match="expected_state capture",
    ):
        precommit_artifacts._validate_closure_phase4_p_syn_payload(
            repo_root=tmp_path
        )

    assert captured["final_closure_row_count"] == 130
    assert captured["claim_evidence_row_count"] == 20
    assert captured["table_row_counts"] == contract.table_row_counts


def test_closure_phase4_r_payload_passes_counts_and_p_authority_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.experiments import lock_closure_synthesis as locker
    from src.reporting import build_closure_synthesis as builder
    from src.reporting import closure_synthesis_contract as synthesis

    contract = _phase4_payload_validator_contract()
    p_commit = "2" * 40
    h_commit = "1" * 40
    authority: dict[str, Any] = {}
    manifest = {"manifest": "P-SYN"}
    authority_bytes = synthesis.canonical_json_bytes(authority)
    manifest_bytes = synthesis.canonical_json_bytes(manifest)
    authority_path = tmp_path / locker.AUTHORITY_PATH
    manifest_path = tmp_path / locker.MANIFEST_PATH
    authority_path.parent.mkdir(parents=True)
    authority_path.write_bytes(authority_bytes)
    manifest_path.write_bytes(manifest_bytes)
    captured_state: dict[str, Any] = {}
    captured_build: dict[str, Any] = {}

    monkeypatch.setattr(synthesis, "load_contract", lambda **_kwargs: contract)
    monkeypatch.setattr(synthesis, "collect_input_records", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(locker, "H_SCOPE", {})
    monkeypatch.setattr(locker, "validate_authority", lambda _payload: None)
    monkeypatch.setattr(builder, "validate_authority", lambda *_args, **_kwargs: authority)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_published_p",
        lambda *_args, **_kwargs: h_commit,
    )

    def git_output(_root: Path, *args: str) -> str:
        if args == ("rev-parse", "HEAD^{commit}"):
            return p_commit + "\n"
        if args[:2] == ("ls-tree", p_commit):
            raw_path = args[-1]
            return f"100644 blob {'a' * 40}\t{raw_path}\n"
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def spy_build_authority(state: Mapping[str, Any]) -> Mapping[str, Any]:
        captured_state.update(state)
        return authority

    monkeypatch.setattr(locker, "_build_authority", spy_build_authority)
    monkeypatch.setattr(
        locker,
        "_build_manifest",
        lambda _authority_bytes, _h_commit: manifest,
    )

    def subprocess_run(command: list[str], **_kwargs: Any) -> Any:
        raw_path = command[-1].split(":", 1)[1]
        payload = (
            authority_bytes
            if raw_path == locker.AUTHORITY_PATH.as_posix()
            else manifest_bytes
        )
        return SimpleNamespace(returncode=0, stdout=payload, stderr=b"")

    monkeypatch.setattr(precommit_artifacts.subprocess, "run", subprocess_run)

    def spy_build_payloads(
        _contract: Any,
        _authority: Mapping[str, Any],
        **kwargs: Any,
    ) -> Mapping[str, bytes]:
        captured_build.update(kwargs)
        raise RuntimeError("stop after R-SYN build signature capture")

    monkeypatch.setattr(builder, "build_payloads", spy_build_payloads)

    with pytest.raises(
        precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError,
        match="build signature capture",
    ):
        precommit_artifacts._validate_closure_phase4_r_syn_payload(
            repo_root=tmp_path
        )

    assert captured_state["final_closure_row_count"] == 130
    assert captured_state["claim_evidence_row_count"] == 20
    assert captured_state["table_row_counts"] == contract.table_row_counts
    assert captured_build["p_syn_commit"] == p_commit
    assert captured_build["authority_manifest_sha256"] == (
        synthesis.sha256_bytes(manifest_bytes)
    )
    assert captured_build["root"] == tmp_path


def test_closure_phase4_r_native_manifest_passes_generic_reproducibility_exact24(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.experiments import lock_closure_synthesis as locker
    from src.reporting import build_closure_synthesis as builder
    from src.reporting import closure_synthesis_contract as synthesis

    repository_root = precommit_artifacts.PROJECT_ROOT
    contract = synthesis.load_contract(
        root=repository_root,
        verify_inputs=True,
    )
    input_records = synthesis.collect_input_records(
        contract,
        root=repository_root,
    )
    assert len(input_records) == 83
    for record in input_records:
        path_text = record["path"]
        source = repository_root / path_text
        destination = tmp_path / path_text
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        destination.chmod(int(record["filesystem_mode"]))

    builder_source = repository_root / locker.BUILDER_PATH
    builder_destination = tmp_path / locker.BUILDER_PATH
    builder_destination.parent.mkdir(parents=True, exist_ok=True)
    builder_bytes = builder_source.read_bytes()
    builder_destination.write_bytes(builder_bytes)
    authority = {
        "synthesis_implementation_commit": "1" * 40,
        "allowed_input_records": input_records,
        "allowed_input_records_digest": synthesis.digest_records(input_records),
        "h_component_records": [
            {
                "path": locker.BUILDER_PATH,
                "bytes": len(builder_bytes),
                "sha256": synthesis.sha256_bytes(builder_bytes),
            }
        ],
    }
    payloads = builder.build_payloads(
        contract,
        authority,
        p_syn_commit="2" * 40,
        authority_manifest_sha256="3" * 64,
        root=tmp_path,
    )
    expected_relative_paths = [
        str(Path(path).relative_to(synthesis.SYNTHESIS_ROOT))
        for path in contract.output_paths
    ]
    assert list(payloads) == expected_relative_paths
    assert len(payloads) == 24

    for relative_path, payload in payloads.items():
        destination = tmp_path / synthesis.SYNTHESIS_ROOT / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    manifest = json.loads(payloads[expected_relative_paths[-1]])
    assert manifest["script"] == authority["h_component_records"][0]
    assert manifest["inputs"] == input_records
    assert len(manifest["inputs"]) == 83
    assert [record["path"] for record in manifest["outputs"]] == list(
        contract.output_paths[:-1]
    )

    monkeypatch.chdir(tmp_path)
    staged_status = "\n".join(
        f"A\t{path}" for path in contract.output_paths
    )
    findings = reproducibility_checks(
        staged_status=staged_status,
        selected_dvc_paths=[],
        artifacts=[],
        max_manifest_hash_bytes=1 << 30,
        verify_manifest_inputs=True,
    )

    assert findings
    assert all(finding.level == "ok" for finding in findings), findings


def _closure_phase4_editorial_short_status(*, staged: bool) -> str:
    expected = precommit_artifacts._closure_phase4_editorial_expected_short_scope(
        staged=staged
    )
    return "\n".join(
        f"{status_code} {path}"
        for path, status_code in sorted(expected.items())
    )


def _closure_phase4_editorial_name_status() -> str:
    return "\n".join(
        f"{status}\t{path}"
        for path, status in sorted(
            precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_STAGED_SCOPE.items()
        )
    )


def _write_closure_phase4_editorial_build_namespace(root: Path) -> None:
    for directory in precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_BUILD_DIRS:
        destination = root / directory
        destination.mkdir(parents=True, exist_ok=True)
        for filename in sorted(
            precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_BUILD_FILENAMES
        ):
            (destination / filename).write_text(
                f"{directory.name}:{filename}\n",
                encoding="utf-8",
            )


def test_closure_phase4_editorial_contract_is_exact12_8m4a() -> None:
    scope = precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_STAGED_SCOPE
    precommit_artifacts._require_closure_phase4_editorial_contract()
    assert len(scope) == 12
    assert sum(status == "M" for status in scope.values()) == 8
    assert sum(status == "A" for status in scope.values()) == 4
    assert scope[
        "reports/thesis/phase4_manuscript_build_receipt_manifest.json"
    ] == "A"
    assert precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_GIT_MODES[
        "src/data/prepare_commit_artifacts.py"
    ] == "100755"
    assert all(
        mode == "100644"
        for path, mode in precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_GIT_MODES.items()
        if path != "src/data/prepare_commit_artifacts.py"
    )


def test_closure_phase4_editorial_selector_requires_exact_unstaged_scope(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            precommit_artifacts.CLOSURE_PHASE4_R_SYN_COMMIT + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    base_calls: list[Path] = []
    index_calls: list[Path] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_base",
        lambda *, repo_root: base_calls.append(repo_root),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_pre_index_bindings",
        lambda *, repo_root: index_calls.append(repo_root),
    )
    exact = _closure_phase4_editorial_short_status(staged=False)
    assert precommit_artifacts.closure_phase4_editorial_pre_stage_scope(
        exact,
        "",
    )
    assert base_calls == [Path(".")]
    assert index_calls == [Path(".")]

    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="exact12",
    ):
        precommit_artifacts.closure_phase4_editorial_pre_stage_scope(
            "\n".join(exact.splitlines()[:-1]),
            "",
        )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="empty Git index",
    ):
        precommit_artifacts.closure_phase4_editorial_pre_stage_scope(
            exact,
            "M\tforeign-index-entry",
        )


def test_closure_phase4_editorial_selector_rejects_unique_marker_on_wrong_parent(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            "0" * 40 + "\n"
            if args == ("rev-parse", "HEAD^{commit}")
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="R-SYN",
    ):
        precommit_artifacts.closure_phase4_editorial_pre_stage_scope(
            "?? reports/thesis/phase4_manuscript_build_receipt.json",
            "",
        )


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "../escape.json",
        "private/FULL.md",
        "private/mifal_ed_t2/manuscript.tex",
        "data/targets/targets.parquet",
        "data/closure_v1/locked_evaluation/outcomes.json",
        "reports/closure_v1/input.parquet",
        "reports//thesis/x.json",
        "reports/./thesis/x.json",
        "tmp/hidden.json",
    ],
)
def test_closure_phase4_editorial_public_record_path_boundary(path: str) -> None:
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="boundary|normalized",
    ):
        precommit_artifacts._phase4_editorial_safe_public_path(
            path,
            context="adversarial test",
        )


def test_closure_phase4_editorial_canonical_json_rejects_reordered_bytes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "record.json"
    path.write_text('{"z": 1, "a": 2}\n', encoding="utf-8")
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="byte-canonical",
    ):
        precommit_artifacts._phase4_editorial_read_canonical_json(
            Path("record.json"),
            repo_root=tmp_path,
            context="test record",
        )


def test_closure_phase4_editorial_matrix_rejects_wrong_cardinality_before_reads(
    monkeypatch,
) -> None:
    payload = {
        "schema_version": "thesis_evidence_matrix_v1",
        "status": "completed",
        "closure_source_commit": precommit_artifacts.CLOSURE_PHASE4_SOURCE_COMMIT,
        "synthesis_publication_commit": precommit_artifacts.CLOSURE_PHASE4_R_SYN_COMMIT,
        "row_counts": {"columns": 10, "evidence_rows": 31},
        "inputs": [],
        "outputs": [],
    }
    identity = precommit_artifacts.RegistrationFileIdentity(
        "reports/thesis/chapter_iv_evidence_matrix_manifest.json",
        1,
        2,
        0o644,
        1,
        2,
        "a" * 64,
        3,
        4,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_phase4_editorial_read_canonical_json",
        lambda *_args, **_kwargs: (payload, identity, b"{}\n"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_phase4_editorial_validate_file_record",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("records must not be read after cardinality failure")
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="32 rows/10 columns/52 inputs/2 outputs",
    ):
        precommit_artifacts._phase4_editorial_matrix_payloads(
            repo_root=Path(".")
        )


def test_closure_phase4_editorial_payload_returns_comprehensive_bound_snapshot(
    monkeypatch,
) -> None:
    staged_paths = set(
        precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_STAGED_SCOPE
    )
    private_paths = {
        path.as_posix()
        for path in precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_PRIVATE_BINDINGS.values()
    }
    figure_paths = {
        path.as_posix()
        for binding in precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_FIGURE_BINDINGS.values()
        for path in binding
    }
    build_paths = {
        (directory / filename).as_posix()
        for directory in precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_BUILD_DIRS
        for filename in precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_BUILD_FILENAMES
    }
    all_paths = staged_paths | private_paths | figure_paths | build_paths

    def identity(raw_path: str) -> Any:
        return precommit_artifacts.RegistrationFileIdentity(
            raw_path,
            1,
            len(raw_path),
            (
                0o755
                if raw_path == "src/data/prepare_commit_artifacts.py"
                else 0o644
            ),
            1,
            len(raw_path),
            hashlib.sha256(raw_path.encode()).hexdigest(),
            20,
            30,
        )

    staged = tuple(identity(path) for path in sorted(staged_paths))
    semantic = tuple(identity(path) for path in sorted(all_paths - staged_paths))
    recaptured: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: staged,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_phase4_editorial_matrix_payloads",
        lambda **_kwargs: ({}, semantic),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_reconstruct_closure_phase4_editorial_matrix",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_receipt",
        lambda **_kwargs: tuple(),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_receipt_manifest",
        lambda **_kwargs: tuple(),
    )

    def recapture(expected: tuple[Any, ...], **_kwargs: Any) -> tuple[Any, ...]:
        recaptured.append(expected)
        return expected

    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_snapshot",
        recapture,
    )
    observed = precommit_artifacts._validate_closure_phase4_editorial_payload(
        repo_root=Path(".")
    )
    assert {record.path for record in observed} == all_paths
    assert observed == recaptured[0]
    assert len(observed) == len(all_paths)


def test_closure_phase4_editorial_receipt_rejects_serialized_private_path(
    monkeypatch,
) -> None:
    payload = {
        "authorities": {},
        "declared_build_parameters": {},
        "figure_bindings": [],
        "private_bindings": [],
        "schema_version": "phase4_manuscript_build_receipt_v1",
        "status": "completed",
        "validated_build_evidence": {},
        "validation": {},
    }
    identity = precommit_artifacts.RegistrationFileIdentity(
        "reports/thesis/phase4_manuscript_build_receipt.json",
        1,
        2,
        0o644,
        1,
        2,
        "a" * 64,
        3,
        4,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_phase4_editorial_read_canonical_json",
        lambda *_args, **_kwargs: (
            payload,
            identity,
            b'{"leak":"private/mifal_ed_t2/manuscript.tex"}\n',
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="path-redaction",
    ):
        precommit_artifacts._validate_closure_phase4_editorial_receipt(
            repo_root=Path(".")
        )


def test_closure_phase4_editorial_companion_rejects_generator_overclaim(
    monkeypatch,
) -> None:
    payload = {
        "generated_at_utc": "2026-08-20T13:54:59+00:00",
        "inputs": [{}, {}, {}],
        "manifest_version": "phase4_manuscript_build_receipt_manifest_v1",
        "outputs": [{}],
        "script": {},
        "script_role": "receipt_generator",
        "status": "completed",
    }
    identity = precommit_artifacts.RegistrationFileIdentity(
        "reports/thesis/phase4_manuscript_build_receipt_manifest.json",
        1,
        2,
        0o644,
        1,
        2,
        "a" * 64,
        3,
        4,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_phase4_editorial_read_canonical_json",
        lambda *_args, **_kwargs: (payload, identity, b"{}\n"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_phase4_editorial_validate_file_record",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("records must not be read after role failure")
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="structure",
    ):
        precommit_artifacts._validate_closure_phase4_editorial_receipt_manifest(
            repo_root=Path(".")
        )


@pytest.mark.parametrize(
    "noncanonical_path",
    ["reports//thesis/x.json", "reports/./thesis/x.json"],
)
def test_closure_phase4_editorial_companion_rejects_lexically_noncanonical_path(
    noncanonical_path: str,
    monkeypatch,
) -> None:
    record = {
        "bytes": 1,
        "path": noncanonical_path,
        "role": "published_r_syn_manifest",
        "sha256": "a" * 64,
    }
    payload = {
        "generated_at_utc": "2026-08-20T13:54:59+00:00",
        "inputs": [record, record, record],
        "manifest_version": "phase4_manuscript_build_receipt_manifest_v1",
        "outputs": [record],
        "script": {
            "bytes": 1,
            "path": "src/reporting/validate_phase4_manuscript.py",
            "sha256": "a" * 64,
        },
        "script_role": "receipt_validator",
        "status": "completed",
    }
    identity = precommit_artifacts.RegistrationFileIdentity(
        "reports/thesis/phase4_manuscript_build_receipt_manifest.json",
        1,
        2,
        0o644,
        1,
        2,
        "a" * 64,
        3,
        4,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_phase4_editorial_read_canonical_json",
        lambda *_args, **_kwargs: (payload, identity, b"{}\n"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_registration_file_identity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("noncanonical path must fail before filesystem access")
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="boundary",
    ):
        precommit_artifacts._validate_closure_phase4_editorial_receipt_manifest(
            repo_root=Path(".")
        )


def test_closure_phase4_editorial_build_namespace_rejects_extra_and_symlink(
    tmp_path: Path,
    monkeypatch,
) -> None:
    build_root = tmp_path / "tmp/closure_v1_phase4_editorial"
    _write_closure_phase4_editorial_build_namespace(tmp_path)
    monkeypatch.setattr(
        precommit_artifacts,
        "_phase4_editorial_require_ignored_untracked",
        lambda *_args, **_kwargs: None,
    )
    assert len(
        precommit_artifacts._snapshot_closure_phase4_editorial_build_evidence(
            repo_root=tmp_path
        )
    ) == 12

    extra = build_root / "build_a/extra.tmp"
    extra.write_text("extra\n", encoding="utf-8")
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="exact six",
    ):
        precommit_artifacts._snapshot_closure_phase4_editorial_build_evidence(
            repo_root=tmp_path
        )
    extra.unlink()
    target = build_root / "build_a/mifal_ed_modelo_tesis_v5.aux"
    target.unlink()
    target.symlink_to(build_root / "build_b/mifal_ed_modelo_tesis_v5.aux")
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="identity|file",
    ):
        precommit_artifacts._snapshot_closure_phase4_editorial_build_evidence(
            repo_root=tmp_path
        )


def test_closure_phase4_editorial_light_recapture_brackets_build_namespace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_closure_phase4_editorial_build_namespace(tmp_path)
    monkeypatch.setattr(
        precommit_artifacts,
        "_phase4_editorial_require_ignored_untracked",
        lambda *_args, **_kwargs: None,
    )
    target = (
        tmp_path
        / precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_BUILD_DIRS[0]
        / "mifal_ed_modelo_tesis_v5.aux"
    )
    expected = (
        precommit_artifacts._registration_file_identity(
            target,
            repo_root=tmp_path,
            mode=0o644,
        ),
    )
    snapshot_build = (
        precommit_artifacts._snapshot_closure_phase4_editorial_build_evidence
    )
    calls = 0

    def mutate_before_second_snapshot(**kwargs: Any) -> tuple[Any, ...]:
        nonlocal calls
        calls += 1
        if calls == 2:
            target.write_text("build drift\n", encoding="utf-8")
        return snapshot_build(**kwargs)

    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_build_evidence",
        mutate_before_second_snapshot,
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="build namespace changed during recapture",
    ):
        precommit_artifacts._recapture_closure_phase4_editorial_snapshot(
            expected,
            repo_root=tmp_path,
            context="build race regression",
        )
    assert calls == 2


def test_closure_phase4_editorial_builder_reconstructs_public_outputs() -> None:
    precommit_artifacts._reconstruct_closure_phase4_editorial_matrix(
        repo_root=precommit_artifacts.PROJECT_ROOT
    )


def test_closure_phase4_editorial_main_precedes_h_and_generic(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_syn_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_p_syn_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_editorial_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_editorial_precommit",
        lambda *_args, **_kwargs: 139,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_syn_h2_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("H2 selector must not run after editorial match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "versionable_changes",
        lambda: (_ for _ in ()).throw(
            AssertionError("generic flow must not run after editorial match")
        ),
    )
    assert precommit_artifacts.main() == 139


def test_closure_phase4_editorial_guard_is_exclusive_and_cleanup_is_owned(
    tmp_path: Path,
) -> None:
    (tmp_path / "tmp").mkdir()
    guard_path = (
        tmp_path
        / precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_PRECOMMIT_GUARD
    )
    assert not guard_path.is_relative_to(
        tmp_path / precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_BUILD_ROOT
    )
    guard_fd, ownership = (
        precommit_artifacts._acquire_closure_phase4_editorial_precommit_guard(
            repo_root=tmp_path
        )
    )
    metadata = guard_path.lstat()
    assert metadata.st_mode & 0o777 == 0o600
    assert metadata.st_nlink == 1
    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="concurrent|stale|symlink|hardlink",
    ):
        precommit_artifacts._acquire_closure_phase4_editorial_precommit_guard(
            repo_root=tmp_path
        )
    assert (
        precommit_artifacts._release_closure_phase4_editorial_precommit_guard(
            guard_fd,
            ownership,
            repo_root=tmp_path,
        )
        is None
    )
    assert not os.path.lexists(guard_path)


@pytest.mark.parametrize("foreign_kind", ["stale", "symlink", "hardlink"])
def test_closure_phase4_editorial_guard_rejects_and_preserves_foreign_nodes(
    foreign_kind: str,
    tmp_path: Path,
) -> None:
    (tmp_path / "tmp").mkdir()
    guard_path = (
        tmp_path
        / precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_PRECOMMIT_GUARD
    )
    foreign = tmp_path / "foreign-guard-node"
    foreign.write_text("foreign\n", encoding="utf-8")
    foreign.chmod(0o600)
    if foreign_kind == "stale":
        guard_path.write_text("stale\n", encoding="utf-8")
        guard_path.chmod(0o600)
    elif foreign_kind == "symlink":
        guard_path.symlink_to(foreign)
    else:
        os.link(foreign, guard_path)

    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="already exists",
    ):
        precommit_artifacts._acquire_closure_phase4_editorial_precommit_guard(
            repo_root=tmp_path
        )
    assert os.path.lexists(guard_path)
    if foreign_kind == "stale":
        assert guard_path.read_text(encoding="utf-8") == "stale\n"
    else:
        assert foreign.read_text(encoding="utf-8") == "foreign\n"


def test_closure_phase4_editorial_guard_cleanup_preserves_foreign_swap(
    tmp_path: Path,
) -> None:
    (tmp_path / "tmp").mkdir()
    guard_path = (
        tmp_path
        / precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_PRECOMMIT_GUARD
    )
    guard_fd, ownership = (
        precommit_artifacts._acquire_closure_phase4_editorial_precommit_guard(
            repo_root=tmp_path
        )
    )
    guard_path.unlink()
    guard_path.write_text("foreign replacement\n", encoding="utf-8")
    guard_path.chmod(0o600)

    error = (
        precommit_artifacts._release_closure_phase4_editorial_precommit_guard(
            guard_fd,
            ownership,
            repo_root=tmp_path,
        )
    )
    assert error is not None
    assert "failed closed" in error
    assert guard_path.read_text(encoding="utf-8") == "foreign replacement\n"


def test_closure_phase4_editorial_runner_rejects_present_guard_before_commands(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "tmp").mkdir()
    guard_path = (
        tmp_path
        / precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_PRECOMMIT_GUARD
    )
    guard_path.write_text("stale foreign guard\n", encoding="utf-8")
    guard_path.chmod(0o600)
    calls: list[str] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        precommit_artifacts,
        "run_command",
        lambda *_args, **_kwargs: calls.append("command"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_editorial_invocation",
        lambda *_args, **_kwargs: calls.append("invocation"),
    )

    assert (
        precommit_artifacts._run_closure_phase4_editorial_precommit(
            _closure_phase3_h_args(),
            initial_status="",
            repo_root=Path("."),
        )
        == 2
    )
    assert calls == []
    assert guard_path.read_text(encoding="utf-8") == "stale foreign guard\n"


def _install_closure_phase4_editorial_runner_harness(
    monkeypatch,
) -> dict[str, Any]:
    args = _closure_phase3_h_args()
    scope = precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_STAGED_SCOPE
    physical = tuple(
        precommit_artifacts.RegistrationFileIdentity(
            path,
            1,
            index + 1,
            (
                0o755
                if path == "src/data/prepare_commit_artifacts.py"
                else 0o644
            ),
            1,
            10,
            "a" * 64,
            20,
            30,
        )
        for index, path in enumerate(sorted(scope))
    )
    state = {"staged": False}
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    dvc_calls: list[int] = []
    final_local_calls: list[str] = []
    guard = precommit_artifacts.RegistrationOwnedNode(
        precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_PRECOMMIT_GUARD.as_posix(),
        1,
        2,
        0o600,
        1,
    )

    monkeypatch.setattr(
        precommit_artifacts,
        "_acquire_closure_phase4_editorial_precommit_guard",
        lambda **_kwargs: (91, guard),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_release_closure_phase4_editorial_precommit_guard",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_editorial_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_editorial_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_payload",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_snapshot",
        lambda *_args, **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_base",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )

    def dvc_status(_bin: str) -> dict[str, Any]:
        dvc_calls.append(len(dvc_calls) + 1)
        return {}

    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", dvc_status)
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase4-editorial-runner-test.md"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_h_syn_publication_check",
        lambda **_kwargs: precommit_artifacts.CommandResult(
            ["scripts/check_repo_publication_ready.sh"],
            1,
            "exact U1/U2/U3",
            "",
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_editorial_staged_transaction",
        lambda **_kwargs: physical,
    )

    def final_local(**_kwargs: Any) -> tuple[Any, ...]:
        final_local_calls.append("local")
        return physical

    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_local_staged_state",
        final_local,
    )

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return (
                _closure_phase4_editorial_name_status()
                if state["staged"]
                else ""
            )
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase4_editorial_short_status(
                staged=state["staged"]
            )
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        if command[:6] == ["git", "-C", ".", "add", "-A", "--"]:
            state["staged"] = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        if command[:5] == ["git", "-C", ".", "restore", (
            "--source=" + precommit_artifacts.CLOSURE_PHASE4_R_SYN_COMMIT
        )]:
            state["staged"] = False
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(
        precommit_artifacts,
        "reproducibility_checks",
        lambda **_kwargs: [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "passed"
            )
        ],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )
    return {
        "args": args,
        "commands": commands,
        "dvc_calls": dvc_calls,
        "final_local_calls": final_local_calls,
        "initial_status": _closure_phase4_editorial_short_status(staged=False),
        "physical": physical,
        "reports": reports,
        "state": state,
    }


def test_closure_phase4_editorial_transaction_stages_exact12_without_dvc(
    monkeypatch,
) -> None:
    args = _closure_phase3_h_args()
    scope = precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_STAGED_SCOPE
    initial_status = _closure_phase4_editorial_short_status(staged=False)
    physical = tuple(
        precommit_artifacts.RegistrationFileIdentity(
            path,
            1,
            index + 1,
            (
                0o755
                if path == "src/data/prepare_commit_artifacts.py"
                else 0o644
            ),
            1,
            10,
            "a" * 64,
            20,
            30,
        )
        for index, path in enumerate(sorted(scope))
    )
    state = {"staged": False}
    commands: list[list[str]] = []
    reports: list[dict[str, Any]] = []
    guard = precommit_artifacts.RegistrationOwnedNode(
        precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_PRECOMMIT_GUARD.as_posix(),
        1,
        2,
        0o600,
        1,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_acquire_closure_phase4_editorial_precommit_guard",
        lambda **_kwargs: (91, guard),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_release_closure_phase4_editorial_precommit_guard",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_editorial_invocation",
        lambda _args: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_editorial_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: physical,
    )
    semantic_calls: list[Path] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_payload",
        lambda *, repo_root: semantic_calls.append(repo_root) or physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda _path: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_precommit_dvc_observation",
        lambda *_args, **_kwargs: (
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            {},
        ),
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/phase4-editorial-test.md"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_h_syn_publication_check",
        lambda **_kwargs: precommit_artifacts.CommandResult(
            ["scripts/check_repo_publication_ready.sh"],
            1,
            "exact U1/U2/U3",
            "",
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_editorial_staged_transaction",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_local_staged_state",
        lambda **_kwargs: physical,
    )

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase4_editorial_name_status() if state["staged"] else ""
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase4_editorial_short_status(staged=state["staged"])
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        if command[:6] == ["git", "-C", ".", "add", "-A", "--"]:
            state["staged"] = True
            return precommit_artifacts.CommandResult(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(
        precommit_artifacts,
        "reproducibility_checks",
        lambda **_kwargs: [
            precommit_artifacts.ReproducibilityFinding(
                "ok", "generic", "-", "passed"
            )
        ],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "write_report",
        lambda _path, **kwargs: reports.append(kwargs),
    )

    assert (
        precommit_artifacts._run_closure_phase4_editorial_precommit(
            args,
            initial_status=initial_status,
        )
        == 0
    )
    assert commands == [
        ["git", "-C", ".", "add", "-A", "--", *sorted(scope)]
    ]
    assert semantic_calls == [Path("."), Path(".")]
    assert reports[0]["selected_dvc_paths"] == []
    assert reports[0]["dvc_add_results"] == []
    assert reports[0]["dvc_push_result"] is None
    assert "U1/U2/U3" in reports[0]["publication_check_result"].stdout


def test_closure_phase4_editorial_runner_rechecks_local_state_after_final_dvc(
    monkeypatch,
) -> None:
    harness = _install_closure_phase4_editorial_runner_harness(monkeypatch)
    events: list[str] = []
    state = cast(dict[str, bool], harness["state"])
    dvc_count = 0
    staged_count = 0

    def dvc_status(_bin: str) -> dict[str, Any]:
        nonlocal dvc_count
        dvc_count += 1
        events.append(f"dvc-{dvc_count}")
        if dvc_count == 4:
            state["late_local_drift"] = True
        return {}

    def staged_validation(**_kwargs: Any) -> tuple[Any, ...]:
        nonlocal staged_count
        staged_count += 1
        events.append(f"full-{staged_count}")
        return cast(tuple[Any, ...], harness["physical"])

    def write_report(_path: Path, **_kwargs: Any) -> None:
        events.append("report")

    def final_local(**_kwargs: Any) -> tuple[Any, ...]:
        events.append("local-final")
        if state.get("late_local_drift"):
            raise precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError(
                "local evidence drift during final DVC observation"
            )
        return cast(tuple[Any, ...], harness["physical"])

    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", dvc_status)
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_editorial_staged_transaction",
        staged_validation,
    )
    monkeypatch.setattr(precommit_artifacts, "write_report", write_report)
    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_local_staged_state",
        final_local,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_release_closure_phase4_editorial_precommit_guard",
        lambda *_args, **_kwargs: events.append("guard-release")
        or (
            None
            if state["staged"] is False
            else (_ for _ in ()).throw(
                AssertionError("guard released before rollback completed")
            )
        ),
    )

    assert (
        precommit_artifacts._run_closure_phase4_editorial_precommit(
            harness["args"],
            initial_status=cast(str, harness["initial_status"]),
        )
        == 2
    )
    report_index = events.index("report")
    assert events[report_index : report_index + 5] == [
        "report",
        "dvc-3",
        "full-2",
        "dvc-4",
        "local-final",
    ]
    assert events[-2:] == ["dvc-5", "guard-release"]
    assert state["staged"] is False
    commands = cast(list[list[str]], harness["commands"])
    assert commands[0][:6] == ["git", "-C", ".", "add", "-A", "--"]
    assert commands[1][:4] == ["git", "-C", ".", "restore"]


def test_closure_phase4_editorial_runner_rejects_divergent_repo_root_before_command(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "run_command",
        lambda *_args, **_kwargs: calls.append("command"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_editorial_invocation",
        lambda *_args, **_kwargs: calls.append("invocation"),
    )

    assert (
        precommit_artifacts._run_closure_phase4_editorial_precommit(
            _closure_phase3_h_args(),
            initial_status="",
            repo_root=tmp_path,
        )
        == 2
    )
    assert calls == []


def test_closure_phase4_editorial_success_print_failure_triggers_rollback(
    monkeypatch,
) -> None:
    harness = _install_closure_phase4_editorial_runner_harness(monkeypatch)
    real_print = builtins.print
    raised = False

    def print_with_one_broken_pipe(*args: Any, **kwargs: Any) -> None:
        nonlocal raised
        if not raised and not args:
            raised = True
            raise BrokenPipeError("closed success output")
        real_print(*args, **kwargs)

    monkeypatch.setattr(builtins, "print", print_with_one_broken_pipe)
    assert (
        precommit_artifacts._run_closure_phase4_editorial_precommit(
            harness["args"],
            initial_status=cast(str, harness["initial_status"]),
        )
        == 2
    )
    assert raised
    assert cast(dict[str, bool], harness["state"])["staged"] is False
    commands = cast(list[list[str]], harness["commands"])
    assert commands[-1][:4] == ["git", "-C", ".", "restore"]


def test_closure_phase4_editorial_guard_cleanup_failure_rolls_back_staging(
    monkeypatch,
) -> None:
    harness = _install_closure_phase4_editorial_runner_harness(monkeypatch)
    cleanup_calls = 0

    def fail_cleanup(*_args: Any, **_kwargs: Any) -> str:
        nonlocal cleanup_calls
        cleanup_calls += 1
        return "guard foreign-swap cleanup failed closed"

    monkeypatch.setattr(
        precommit_artifacts,
        "_release_closure_phase4_editorial_precommit_guard",
        fail_cleanup,
    )
    assert (
        precommit_artifacts._run_closure_phase4_editorial_precommit(
            harness["args"],
            initial_status=cast(str, harness["initial_status"]),
        )
        == 2
    )
    assert cleanup_calls == 1
    assert cast(dict[str, bool], harness["state"])["staged"] is False
    commands = cast(list[list[str]], harness["commands"])
    assert commands[-1][:4] == ["git", "-C", ".", "restore"]


def test_closure_phase4_editorial_rollback_is_directed_and_preserves_foreign(
    monkeypatch,
) -> None:
    scope = precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_STAGED_SCOPE
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        assert "foreign-path" not in command
        return precommit_artifacts.CommandResult(command, 0, "", "")

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            "M\tforeign-path\n"
            if args
            == (
                "diff",
                "--cached",
                "--name-status",
                "--no-renames",
            )
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: tuple(),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_snapshot",
        lambda *_args, **_kwargs: tuple(),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_base",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    assert (
        precommit_artifacts._rollback_closure_phase4_editorial_staging(
            physical_before=tuple(),
            comprehensive_before=tuple(),
            dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            dvc_status_before={},
            repo_root=Path("."),
        )
        is None
    )
    assert commands == [
        [
            "git",
            "-C",
            ".",
            "restore",
            (
                "--source="
                + precommit_artifacts.CLOSURE_PHASE4_R_SYN_COMMIT
            ),
            "--staged",
            "--",
            *sorted(scope),
        ]
    ]


def test_closure_phase4_editorial_rollback_reports_base_drift_before_local_recaptures(
    monkeypatch,
) -> None:
    events: list[str] = []

    def run(command: list[str], **_kwargs: Any) -> Any:
        events.append("restore")
        assert (
            f"--source={precommit_artifacts.CLOSURE_PHASE4_R_SYN_COMMIT}"
            in command
        )
        return precommit_artifacts.CommandResult(command, 0, "", "")

    def require_base(**_kwargs: Any) -> None:
        events.append("base")
        raise precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError(
            "remote authority drift"
        )

    def dvc_status(_bin: str) -> dict[str, Any]:
        events.append("dvc")
        return {}

    def git_output(_root: Path, *args: str) -> str:
        events.append("local-index")
        assert args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        )
        return ""

    monkeypatch.setattr(precommit_artifacts, "run_command", run)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_base",
        require_base,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", dvc_status)
    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: events.append("local-exact12") or tuple(),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_snapshot",
        lambda *_args, **_kwargs: events.append("local-comprehensive")
        or tuple(),
    )

    error = precommit_artifacts._rollback_closure_phase4_editorial_staging(
        physical_before=tuple(),
        comprehensive_before=tuple(),
        dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
        dvc_status_before={},
        repo_root=Path("."),
    )
    assert error is not None
    assert "base/remote validation failed" in error
    assert events == [
        "restore",
        "base",
        "dvc",
        "local-index",
        "local-exact12",
        "local-comprehensive",
        "local-index",
        "local-exact12",
    ]


def test_closure_phase4_editorial_abort_reports_failed_closed_on_private_build_drift(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        precommit_artifacts,
        "run_command",
        lambda command, **_kwargs: precommit_artifacts.CommandResult(
            command, 0, "", ""
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_base",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            ""
            if args
            == (
                "diff",
                "--cached",
                "--name-status",
                "--no-renames",
            )
            else (_ for _ in ()).throw(AssertionError(args))
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: tuple(),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError(
                "private/build evidence drift"
            )
        ),
    )

    assert (
        precommit_artifacts._abort_closure_phase4_editorial_post_add(
            RuntimeError("primary failure"),
            physical_before=tuple(),
            comprehensive_before=tuple(),
            dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            dvc_status_before={},
            repo_root=Path("."),
        )
        == 2
    )
    assert "ROLLBACK FAILED CLOSED" in capsys.readouterr().err


def test_closure_phase4_editorial_rollback_rejects_index_mutation_during_comprehensive_recapture(
    monkeypatch,
) -> None:
    state = {"index_drift": False}
    owned_path = sorted(
        precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_STAGED_SCOPE
    )[0]
    monkeypatch.setattr(
        precommit_artifacts,
        "run_command",
        lambda command, **_kwargs: precommit_artifacts.CommandResult(
            command, 0, "", ""
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_base",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(precommit_artifacts, "dvc_status_json", lambda _bin: {})
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            f"M\t{owned_path}\n" if state["index_drift"] else ""
        )
        if args
        == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        )
        else (_ for _ in ()).throw(AssertionError(args)),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: tuple(),
    )

    def mutate_index(*_args: Any, **_kwargs: Any) -> tuple[Any, ...]:
        state["index_drift"] = True
        return tuple()

    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_snapshot",
        mutate_index,
    )

    error = precommit_artifacts._rollback_closure_phase4_editorial_staging(
        physical_before=tuple(),
        comprehensive_before=tuple(),
        dvc_bin=precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
        dvc_status_before={},
        repo_root=Path("."),
    )
    assert error is not None
    assert "final directed rollback left owned staged paths" in error


def test_closure_phase4_editorial_staged_validation_rejects_payload_worktree_mutation(
    monkeypatch,
) -> None:
    before = (
        precommit_artifacts.RegistrationFileIdentity(
            "reports/thesis/phase4_manuscript_build_receipt.json",
            1,
            2,
            0o644,
            1,
            10,
            "a" * 64,
            20,
            30,
        ),
    )
    after = (
        precommit_artifacts.RegistrationFileIdentity(
            "reports/thesis/phase4_manuscript_build_receipt.json",
            1,
            2,
            0o644,
            1,
            11,
            "b" * 64,
            21,
            31,
        ),
    )
    snapshots = iter((before, after))

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase4_editorial_name_status()
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase4_editorial_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_base",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: next(snapshots),
    )
    binding_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_index_bindings",
        lambda physical, **_kwargs: binding_calls.append(physical),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_payload",
        lambda **_kwargs: before,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_snapshot",
        lambda *_args, **_kwargs: before,
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="worktree changed",
    ):
        precommit_artifacts.validate_closure_phase4_editorial_staged_transaction()
    assert binding_calls == [before]


def test_closure_phase4_editorial_staged_validation_rejects_payload_index_mutation(
    monkeypatch,
) -> None:
    physical = (
        precommit_artifacts.RegistrationFileIdentity(
            "reports/thesis/phase4_manuscript_build_receipt.json",
            1,
            2,
            0o644,
            1,
            10,
            "a" * 64,
            20,
            30,
        ),
    )
    state = {"payload_validated": False}

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            exact = _closure_phase4_editorial_name_status()
            return (
                exact + "\nM\tforeign-index-entry"
                if state["payload_validated"]
                else exact
            )
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase4_editorial_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_base",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_index_bindings",
        lambda *_args, **_kwargs: None,
    )

    def mutate_index(**_kwargs: Any) -> Any:
        state["payload_validated"] = True
        return physical

    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_payload",
        mutate_index,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_snapshot",
        lambda *_args, **_kwargs: physical,
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="Git state changed",
    ):
        precommit_artifacts.validate_closure_phase4_editorial_staged_transaction()


def test_closure_phase4_editorial_staged_validation_rechecks_late_authority(
    monkeypatch,
) -> None:
    physical = (
        precommit_artifacts.RegistrationFileIdentity(
            "reports/thesis/phase4_manuscript_build_receipt.json",
            1,
            2,
            0o644,
            1,
            10,
            "a" * 64,
            20,
            30,
        ),
    )
    events: list[str] = []

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            events.append("cached")
            return _closure_phase4_editorial_name_status()
        if args == ("status", "--short", "--untracked-files=all"):
            events.append("short")
            return _closure_phase4_editorial_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            events.append("unstaged")
            return ""
        raise AssertionError(args)

    authority_calls: list[Path] = []

    def require_authority(*, repo_root: Path) -> None:
        authority_calls.append(repo_root)
        events.append(f"authority-{len(authority_calls)}")
        if len(authority_calls) == 2:
            raise precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError(
                "late authority drift"
            )

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_base",
        require_authority,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: events.append("snapshot") or physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_index_bindings",
        lambda *_args, **_kwargs: events.append("index"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_payload",
        lambda **_kwargs: events.append("payload") or physical,
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="late authority drift",
    ):
        precommit_artifacts.validate_closure_phase4_editorial_staged_transaction()
    assert authority_calls == [Path("."), Path(".")]
    assert events == [
        "cached",
        "short",
        "unstaged",
        "authority-1",
        "snapshot",
        "index",
        "payload",
        "authority-2",
    ]


@pytest.mark.parametrize("evidence_kind", ["private", "build"])
def test_closure_phase4_editorial_staged_validation_rejects_evidence_drift_during_second_base(
    evidence_kind: str,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_closure_phase4_editorial_build_namespace(tmp_path)
    if evidence_kind == "private":
        relative = precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_PRIVATE_BINDINGS[
            "doctoral_manuscript_tex"
        ]
        evidence = tmp_path / relative
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("private evidence\n", encoding="utf-8")
    else:
        relative = (
            precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_BUILD_DIRS[0]
            / "mifal_ed_modelo_tesis_v5.aux"
        )
        evidence = tmp_path / relative
    expected_evidence = precommit_artifacts._registration_file_identity(
        evidence,
        repo_root=tmp_path,
        mode=0o644,
    )
    physical = (
        precommit_artifacts.RegistrationFileIdentity(
            "reports/thesis/phase4_manuscript_build_receipt.json",
            1,
            2,
            0o644,
            1,
            10,
            "a" * 64,
            20,
            30,
        ),
    )

    def git_output(_root: Path, *args: str) -> str:
        if args == (
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
        ):
            return _closure_phase4_editorial_name_status()
        if args == ("status", "--short", "--untracked-files=all"):
            return _closure_phase4_editorial_short_status(staged=True)
        if args == ("diff", "--name-status", "--no-renames"):
            return ""
        raise AssertionError(args)

    authority_calls = 0

    def require_base(**_kwargs: Any) -> None:
        nonlocal authority_calls
        authority_calls += 1
        if authority_calls == 2:
            evidence.write_text(
                f"{evidence_kind} evidence drifted\n",
                encoding="utf-8",
            )

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_base",
        require_base,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_index_bindings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_payload",
        lambda **_kwargs: (expected_evidence,),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_phase4_editorial_require_ignored_untracked",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="comprehensive evidence snapshot drifted",
    ):
        precommit_artifacts.validate_closure_phase4_editorial_staged_transaction(
            repo_root=tmp_path
        )
    assert authority_calls == 2


def test_closure_phase4_editorial_local_recheck_rejects_private_drift_during_git_checks(
    monkeypatch,
) -> None:
    physical = (
        precommit_artifacts.RegistrationFileIdentity(
            "reports/thesis/phase4_manuscript_build_receipt.json",
            1,
            2,
            0o644,
            1,
            10,
            "a" * 64,
            20,
            30,
        ),
    )
    state = {"private_drift": False, "recaptures": 0}

    def recapture(*_args: Any, **_kwargs: Any) -> Any:
        state["recaptures"] += 1
        if state["private_drift"]:
            raise precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError(
                "private evidence drift"
            )
        return physical

    def git_state(**_kwargs: Any) -> None:
        state["private_drift"] = True

    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_snapshot",
        recapture,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_exact_staged_git_state",
        git_state,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_index_bindings",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="private evidence drift",
    ):
        precommit_artifacts._recapture_closure_phase4_editorial_local_staged_state(
            physical_before=physical,
            comprehensive_before=physical,
            repo_root=Path("."),
            context="race regression",
        )
    assert state["recaptures"] == 2


@pytest.mark.parametrize("mutation_recapture", [1, 2])
def test_closure_phase4_editorial_local_recheck_rejects_index_drift_during_comprehensive_recapture(
    mutation_recapture: int,
    monkeypatch,
) -> None:
    physical = (
        precommit_artifacts.RegistrationFileIdentity(
            "reports/thesis/phase4_manuscript_build_receipt.json",
            1,
            2,
            0o644,
            1,
            10,
            "a" * 64,
            20,
            30,
        ),
    )
    state = {"index_drift": False, "recaptures": 0, "git_checks": 0}

    def recapture(*_args: Any, **_kwargs: Any) -> Any:
        state["recaptures"] += 1
        if state["recaptures"] == mutation_recapture:
            state["index_drift"] = True
        return physical

    def git_state(**_kwargs: Any) -> None:
        state["git_checks"] += 1
        if state["index_drift"]:
            raise precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError(
                "index drift during comprehensive recapture"
            )

    monkeypatch.setattr(
        precommit_artifacts,
        "_recapture_closure_phase4_editorial_snapshot",
        recapture,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_editorial_exact_staged_git_state",
        git_state,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_editorial_files",
        lambda **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_editorial_index_bindings",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(
        precommit_artifacts.ClosurePhase4EditorialPrecommitAdapterError,
        match="index drift during comprehensive recapture",
    ):
        precommit_artifacts._recapture_closure_phase4_editorial_local_staged_state(
            physical_before=physical,
            comprehensive_before=physical,
            repo_root=Path("."),
            context="race regression",
        )
    assert state["recaptures"] == mutation_recapture
    assert state["git_checks"] == mutation_recapture


def _phase4_cert_short_status(gate: str, *, staged: bool) -> str:
    scope = precommit_artifacts._closure_phase4_cert_scope(gate)
    rows = []
    for path, code in sorted(scope.items()):
        if staged:
            rows.append(f"{code}  {path}")
        elif code == "A":
            rows.append(f"?? {path}")
        else:
            rows.append(f" M {path}")
    return "\n".join(rows) + "\n"


def _phase4_cert_name_status(gate: str) -> str:
    return "\n".join(
        f"{code}\t{path}"
        for path, code in sorted(
            precommit_artifacts._closure_phase4_cert_scope(gate).items()
        )
    )


def _phase4_cert_identity(path: str = "cert.txt") -> Any:
    return precommit_artifacts.RegistrationFileIdentity(
        path,
        1,
        2,
        0o644,
        1,
        10,
        "a" * 64,
        20,
        30,
    )


def test_closure_phase4_certification_scopes_modes_and_precedence_are_exact(
    monkeypatch,
) -> None:
    assert len(precommit_artifacts.CLOSURE_PHASE4_H_CERT_STAGED_SCOPE) == 11
    assert set(
        precommit_artifacts.CLOSURE_PHASE4_H_CERT_STAGED_SCOPE.values()
    ) == {"M"}
    assert (
        precommit_artifacts.CLOSURE_PHASE4_H_CERT_STAGED_SCOPE
        == precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_STAGED_SCOPE
    )
    assert list(
        precommit_artifacts.CLOSURE_PHASE4_H_CERT_V1_STAGED_SCOPE.values()
    ).count("A") == 9
    assert list(
        precommit_artifacts.CLOSURE_PHASE4_H_CERT_V1_STAGED_SCOPE.values()
    ).count("M") == 2
    assert len(precommit_artifacts.CLOSURE_PHASE4_P_CERT_STAGED_SCOPE) == 2
    assert set(
        precommit_artifacts.CLOSURE_PHASE4_P_CERT_STAGED_SCOPE.values()
    ) == {"A"}
    assert set(precommit_artifacts.CLOSURE_PHASE4_P_CERT_STAGED_SCOPE) == {
        "configs/closure_v1/phase4_final_certification_authority_v3.json",
        "configs/closure_v1/phase4_final_certification_authority_manifest_v3.json",
    }
    assert set(precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_STAGED_SCOPE) == {
        "configs/closure_v1/phase4_final_certification_authority_v2.json",
        "configs/closure_v1/phase4_final_certification_authority_manifest_v2.json",
    }
    assert set(precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_STAGED_SCOPE) == {
        "configs/closure_v1/phase4_final_certification_authority.json",
        "configs/closure_v1/phase4_final_certification_authority_manifest.json",
    }
    assert len(precommit_artifacts.CLOSURE_PHASE4_R_CERT_STAGED_SCOPE) == 8
    assert list(precommit_artifacts.CLOSURE_PHASE4_R_CERT_STAGED_SCOPE)[-1].endswith(
        "final_certification_manifest.json"
    )
    assert (
        precommit_artifacts.CLOSURE_PHASE4_H_CERT_GIT_MODES[
            "src/data/prepare_commit_artifacts.py"
        ]
        == "100755"
    )
    assert (
        precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_COMMIT
        == "8e01709c54330502aee318500ab9248e90fe17c5"
    )
    assert (
        precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT
        == "72273b52d47df83acc7618fe98a887b74d690a13"
    )

    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_cert_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_r_cert_precommit",
        lambda *_args, **_kwargs: 241,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_p_cert_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("P-CERT selector ran after R-CERT match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_cert_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("H-CERT3 selector ran after R-CERT match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_syn_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("R-SYN selector ran before R-CERT")
        ),
    )
    assert precommit_artifacts.main() == 241


def test_closure_phase4_h_cert_main_precedes_editorial_and_historical(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_cert_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_p_cert_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_cert_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_h_cert_precommit",
        lambda *_args, **_kwargs: 242,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_syn_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("R-SYN selector ran after H-CERT match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_editorial_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("editorial selector ran after H-CERT match")
        ),
    )
    assert precommit_artifacts.main() == 242


def test_closure_phase4_p_cert_main_precedes_h_cert_and_historical(
    monkeypatch,
) -> None:
    monkeypatch.setattr(precommit_artifacts, "parse_args", _closure_phase3_h_args)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: "")
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_cert_pre_stage_scope",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_p_cert_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_p_cert_precommit",
        lambda *_args, **_kwargs: 243,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_h_cert_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("H-CERT selector ran after P-CERT match")
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_r_syn_pre_stage_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("R-SYN selector ran after P-CERT match")
        ),
    )
    assert precommit_artifacts.main() == 243


def test_closure_phase4_h_cert_selector_is_exact_and_rejects_guard_extra_pending(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "tmp").mkdir()
    exact = _phase4_cert_short_status("H-CERT", staged=False)
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT
            if args[:2] == ("rev-parse", "HEAD^{commit}")
            else ""
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_v2_history",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_refs",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_runtime_namespaces",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_contract",
        lambda **_kwargs: SimpleNamespace(test_suite=SimpleNamespace(status="locked")),
    )
    assert precommit_artifacts.closure_phase4_h_cert_pre_stage_scope(
        exact,
        "",
        repo_root=tmp_path,
    )
    assert not precommit_artifacts.closure_phase4_h_cert_pre_stage_scope(
        "",
        "",
        repo_root=tmp_path,
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="exact",
    ):
        precommit_artifacts.closure_phase4_h_cert_pre_stage_scope(
            exact + "?? foreign.txt\n",
            "",
            repo_root=tmp_path,
        )
    guard = (
        tmp_path
        / precommit_artifacts.CLOSURE_PHASE4_FINAL_CERTIFICATION_PRECOMMIT_GUARD
    )
    guard.write_text("foreign\n", encoding="utf-8")
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="guard already exists",
    ):
        precommit_artifacts.closure_phase4_h_cert_pre_stage_scope(
            exact,
            "",
            repo_root=tmp_path,
        )
    guard.unlink()

    def pending(**_kwargs: Any) -> Any:
        raise precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError(
            "suite pending_integration"
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_contract",
        pending,
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="pending_integration",
    ):
        precommit_artifacts.closure_phase4_h_cert_pre_stage_scope(
            exact,
            "",
            repo_root=tmp_path,
        )


def test_closure_phase4_cert_published_h_rejects_wrong_parent_and_scope(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_v2_history",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_parents",
        lambda *_args, **_kwargs: ("f" * 40,),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="direct single-parent",
    ):
        precommit_artifacts._require_closure_phase4_published_h_cert(
            "a" * 40,
            repo_root=Path("."),
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_parents",
        lambda *_args, **_kwargs: (
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT,
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_scope",
        lambda *_args, **_kwargs: {},
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="scope drifted",
    ):
        precommit_artifacts._require_closure_phase4_published_h_cert(
            "a" * 40,
            repo_root=Path("."),
        )


def test_closure_phase4_h_cert3_selector_rejects_superseded_base(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "tmp").mkdir()
    status = _phase4_cert_short_status("H-CERT", staged=False)
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda *_args: precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_COMMIT,
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="H-CERT3.*P-CERT2",
    ):
        precommit_artifacts.closure_phase4_h_cert_pre_stage_scope(
            status,
            "",
            repo_root=tmp_path,
        )


def test_closure_phase4_p_cert3_selector_accepts_git_lexical_status_order(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "tmp").mkdir()
    lines = _phase4_cert_short_status("P-CERT", staged=False).splitlines()
    assert lines[0].endswith("authority_manifest_v3.json")
    assert lines[1].endswith("authority_v3.json")
    reversed_status = "\n".join(reversed(lines)) + "\n"
    h3_commit = "a" * 40
    observed: list[str] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda _root, *args: (
            h3_commit if args[:2] == ("rev-parse", "HEAD^{commit}") else ""
        ),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_published_h_cert",
        lambda commit, **_kwargs: observed.append(commit),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_refs",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_runtime_namespaces",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_contract",
        lambda **_kwargs: SimpleNamespace(test_suite=SimpleNamespace(status="locked")),
    )
    assert precommit_artifacts.closure_phase4_p_cert_pre_stage_scope(
        "\n".join(lines) + "\n",
        "",
        repo_root=tmp_path,
    )
    assert precommit_artifacts.closure_phase4_p_cert_pre_stage_scope(
        reversed_status,
        "",
        repo_root=tmp_path,
    )
    assert observed == [h3_commit, h3_commit]


@pytest.mark.parametrize(
    "commit,scope,modes,label,validator_name",
    [
        (
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_COMMIT,
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_STAGED_SCOPE,
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_GIT_MODES,
            "P-CERT1",
            "_require_closure_phase4_p1_files_intact",
        ),
        (
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT,
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_STAGED_SCOPE,
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_GIT_MODES,
            "P-CERT2",
            "_require_closure_phase4_p2_files_intact",
        ),
    ],
)
def test_closure_phase4_cert_historical_authority_files_are_byte_intact(
    tmp_path: Path,
    monkeypatch,
    commit: str,
    scope: Mapping[str, str],
    modes: Mapping[str, str],
    label: str,
    validator_name: str,
) -> None:
    payloads = {
        path: f"historical:{path}\n".encode()
        for path in scope
    }
    expected_oids = {
        path: hashlib.sha1(
            f"blob {len(payload)}\0".encode("ascii") + payload,
            usedforsecurity=False,
        ).hexdigest()
        for path, payload in payloads.items()
    }
    for path, payload in payloads.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    def git_output(_root: Path, *args: str) -> str:
        assert args[:2] == ("ls-tree", commit)
        path = args[-1]
        return f"{modes[path]} blob {expected_oids[path]}\t{path}\n"

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    validator = getattr(precommit_artifacts, validator_name)
    validator(repo_root=tmp_path)

    mutated = next(iter(payloads))
    (tmp_path / mutated).write_bytes(b"tampered\n")
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match=rf"{label} authority bytes drifted",
    ):
        validator(repo_root=tmp_path)


def test_closure_phase4_cert_v2_history_binds_exact_topology_and_scopes(
    monkeypatch,
) -> None:
    parents = {
        precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_COMMIT: (
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_COMMIT,
        ),
        precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT: (
            precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_COMMIT,
        ),
    }
    observed: list[tuple[str, Mapping[str, str], Mapping[str, str], str]] = []
    p2_intact = 0
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_v1_history",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_parents",
        lambda commit, **_kwargs: parents[commit],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_historical_commit",
        lambda commit, *, expected_scope, expected_modes, label, **_kwargs: (
            observed.append((commit, expected_scope, expected_modes, label))
        ),
    )

    def intact(**_kwargs: Any) -> None:
        nonlocal p2_intact
        p2_intact += 1

    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_p2_files_intact",
        intact,
    )
    precommit_artifacts._require_closure_phase4_cert_v2_history(
        repo_root=Path(".")
    )
    assert observed == [
        (
            precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_COMMIT,
            precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_STAGED_SCOPE,
            precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_GIT_MODES,
            "H-CERT2",
        ),
        (
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT,
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_STAGED_SCOPE,
            precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_GIT_MODES,
            "P-CERT2",
        ),
    ]
    assert p2_intact == 1

    parents[precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT] = (
        precommit_artifacts.CLOSURE_PHASE4_H_CERT_V1_COMMIT,
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="H1 -> P1 -> H2 -> P2",
    ):
        precommit_artifacts._require_closure_phase4_cert_v2_history(
            repo_root=Path(".")
        )


@pytest.mark.parametrize(
    "p_commit",
    [
        precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_COMMIT,
        precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT,
    ],
)
def test_closure_phase4_cert_historical_p_cannot_authorize_r_cert(
    monkeypatch, p_commit: str
) -> None:
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_v2_history",
        lambda **_kwargs: None,
    )

    def parents(commit: str, **_kwargs: Any) -> tuple[str, ...]:
        if commit == precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_COMMIT:
            return (precommit_artifacts.CLOSURE_PHASE4_H_CERT_V1_COMMIT,)
        if commit == precommit_artifacts.CLOSURE_PHASE4_H_CERT_V1_COMMIT:
            return (precommit_artifacts.CLOSURE_PHASE4_EDITORIAL_COMMIT,)
        if commit == precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT:
            return (precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_COMMIT,)
        if commit == precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_COMMIT:
            return (precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_COMMIT,)
        raise AssertionError(f"unexpected commit: {commit}")

    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_commit_parents",
        parents,
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="H-CERT3.*P-CERT2",
    ):
        precommit_artifacts._require_closure_phase4_published_p_cert(
            p_commit,
            repo_root=Path("."),
        )


def test_closure_phase4_cert_refs_fail_closed_on_local_or_live_remote_drift(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_publication_refs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError(
                "origin/HEAD drift"
            )
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="origin/HEAD drift",
    ):
        precommit_artifacts._require_closure_phase4_cert_refs(
            "a" * 40,
            repo_root=Path("."),
        )

    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_publication_refs",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_live_remote",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            precommit_artifacts.ClosurePhase4SynthesisPublicationAdapterError(
                "live remote main drift"
            )
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="live remote main drift",
    ):
        precommit_artifacts._require_closure_phase4_cert_refs(
            "a" * 40,
            repo_root=Path("."),
        )

def test_closure_phase4_cert_safe_reader_rejects_symlink_hardlink_and_toctou(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "cert.json"
    target.write_bytes(b"payload")
    assert (
        precommit_artifacts._read_closure_phase4_cert_file(
            "cert.json", repo_root=tmp_path
        )
        == b"payload"
    )
    linked = tmp_path / "linked.json"
    os.link(target, linked)
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="single-link",
    ):
        precommit_artifacts._read_closure_phase4_cert_file(
            "cert.json", repo_root=tmp_path
        )
    linked.unlink()
    target.unlink()
    target.symlink_to(tmp_path / "missing")
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError
    ):
        precommit_artifacts._read_closure_phase4_cert_file(
            "cert.json", repo_root=tmp_path
        )
    target.unlink()
    target.write_bytes(b"payload")
    original_read = precommit_artifacts.os.read
    calls = 0

    def racing_read(fd: int, size: int) -> bytes:
        nonlocal calls
        payload = original_read(fd, size)
        calls += 1
        if calls == 1:
            target.write_bytes(b"changed")
        return payload

    monkeypatch.setattr(precommit_artifacts.os, "read", racing_read)
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="changed|cannot be read safely",
    ):
        precommit_artifacts._read_closure_phase4_cert_file(
            "cert.json", repo_root=tmp_path
        )


def test_closure_phase4_cert_safe_reader_rejects_ancestor_symlink_swap(
    tmp_path: Path, monkeypatch
) -> None:
    parent = tmp_path / "stable"
    parent.mkdir()
    (parent / "cert.json").write_bytes(b"owned")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "cert.json").write_bytes(b"foreign")
    moved = tmp_path / "stable.retained"
    original_open = precommit_artifacts.os.open
    swapped = False

    def racing_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal swapped
        if path == "cert.json" and not swapped:
            swapped = True
            parent.rename(moved)
            parent.symlink_to(foreign, target_is_directory=True)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(precommit_artifacts.os, "open", racing_open)
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="directory binding drifted",
    ):
        precommit_artifacts._read_closure_phase4_cert_file(
            "stable/cert.json", repo_root=tmp_path
        )


def test_closure_phase4_cert_rejects_runtime_authority_and_cleanup_namespaces(
    tmp_path: Path,
) -> None:
    (tmp_path / "tmp").mkdir()
    config_parent = tmp_path / "configs/closure_v1"
    config_parent.mkdir(parents=True)
    (tmp_path / "reports/closure_v1").mkdir(parents=True)

    cleanup = (
        config_parent
        / f"{precommit_artifacts.CLOSURE_PHASE4_FINAL_CERTIFICATION_AUTHORITY_CLEANUP_PREFIX}foreign"
    )
    cleanup.write_text("foreign\n", encoding="utf-8")
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="authority temp",
    ):
        precommit_artifacts._require_closure_phase4_cert_runtime_namespaces(
            "H-CERT", repo_root=tmp_path
        )
    cleanup.unlink()

    runtime = (
        tmp_path
        / precommit_artifacts.CLOSURE_PHASE4_FINAL_CERTIFICATION_RUNTIME_GUARD.parent
    )
    runtime.mkdir(parents=True)
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="runtime guard/temp namespace",
    ):
        precommit_artifacts._require_closure_phase4_cert_runtime_namespaces(
            "H-CERT", repo_root=tmp_path
        )
    runtime.rmdir()

    for label, scope in (
        ("P1", precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_STAGED_SCOPE),
        ("P2", precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_STAGED_SCOPE),
    ):
        for raw_path in scope:
            (tmp_path / raw_path).write_text(
                f"historical {label}\n", encoding="utf-8"
            )
    precommit_artifacts._require_closure_phase4_cert_runtime_namespaces(
        "H-CERT", repo_root=tmp_path
    )

    authority = (
        tmp_path
        / next(iter(precommit_artifacts.CLOSURE_PHASE4_P_CERT_STAGED_SCOPE))
    )
    authority.write_text("premature\n", encoding="utf-8")
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="premature P-CERT",
    ):
        precommit_artifacts._require_closure_phase4_cert_runtime_namespaces(
            "H-CERT", repo_root=tmp_path
        )


def test_closure_phase4_cert_namespace_rejects_parent_symlink_swap(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "tmp").mkdir()
    (tmp_path / "configs/closure_v1").mkdir(parents=True)
    (tmp_path / "reports/closure_v1").mkdir(parents=True)
    retained = tmp_path / "tmp.retained"
    foreign = tmp_path / "foreign-tmp"
    foreign.mkdir()
    original_listdir = precommit_artifacts.os.listdir
    swapped = False

    def racing_listdir(path: Any) -> list[str]:
        nonlocal swapped
        if isinstance(path, int) and not swapped:
            swapped = True
            (tmp_path / "tmp").rename(retained)
            (tmp_path / "tmp").symlink_to(foreign, target_is_directory=True)
        return list(original_listdir(path))

    monkeypatch.setattr(precommit_artifacts.os, "listdir", racing_listdir)
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="directory binding drifted",
    ):
        precommit_artifacts._require_closure_phase4_cert_runtime_namespaces(
            "H-CERT", repo_root=tmp_path
        )


def test_closure_phase4_r_cert_namespace_is_exact_flat_single_link(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path / precommit_artifacts.CLOSURE_PHASE4_FINAL_CERTIFICATION_ROOT
    )
    root.mkdir(parents=True)
    paths = tuple(precommit_artifacts.CLOSURE_PHASE4_R_CERT_STAGED_SCOPE)
    for raw_path in paths:
        (tmp_path / raw_path).write_text("certification\n", encoding="utf-8")
    precommit_artifacts._require_closure_phase4_r_cert_namespace_exact(
        repo_root=tmp_path
    )

    extra = root / "foreign.txt"
    extra.write_text("foreign\n", encoding="utf-8")
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="exact8",
    ):
        precommit_artifacts._require_closure_phase4_r_cert_namespace_exact(
            repo_root=tmp_path
        )
    extra.unlink()

    victim = tmp_path / paths[0]
    sibling = tmp_path / "foreign-link"
    os.link(victim, sibling)
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="unsafe entry",
    ):
        precommit_artifacts._require_closure_phase4_r_cert_namespace_exact(
            repo_root=tmp_path
        )
    sibling.unlink()
    victim.unlink()
    victim.symlink_to(tmp_path / paths[1])
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="unsafe entry",
    ):
        precommit_artifacts._require_closure_phase4_r_cert_namespace_exact(
            repo_root=tmp_path
        )


def test_closure_phase4_r_cert_namespace_rejects_root_rename_swap(
    tmp_path: Path, monkeypatch
) -> None:
    root = (
        tmp_path / precommit_artifacts.CLOSURE_PHASE4_FINAL_CERTIFICATION_ROOT
    )
    root.mkdir(parents=True)
    for raw_path in precommit_artifacts.CLOSURE_PHASE4_R_CERT_STAGED_SCOPE:
        (tmp_path / raw_path).write_text("certification\n", encoding="utf-8")
    moved = root.with_name("12_certification.retained")
    foreign = root.with_name("12_certification.foreign")
    foreign.mkdir()
    original_listdir = precommit_artifacts.os.listdir
    swapped = False

    def racing_listdir(path: Any) -> list[str]:
        nonlocal swapped
        if isinstance(path, int) and not swapped:
            swapped = True
            root.rename(moved)
            root.symlink_to(foreign, target_is_directory=True)
        return list(original_listdir(path))

    monkeypatch.setattr(precommit_artifacts.os, "listdir", racing_listdir)
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="directory binding drifted",
    ):
        precommit_artifacts._require_closure_phase4_r_cert_namespace_exact(
            repo_root=tmp_path
        )


def _open_phase4_cert_guard_test_tree(
    repo_root: Path,
) -> Any:
    (repo_root / ".git").mkdir(parents=True)
    (repo_root / "tmp").mkdir()
    return precommit_artifacts._open_closure_phase4_cert_tree_lease(
        repo_root=repo_root,
        relative_directories=(".git", "tmp"),
        context="test certification flock",
    )


def _try_phase4_cert_flock(path: Path) -> int:
    probe = (
        "import fcntl, os, sys; "
        "fd=os.open(sys.argv[1], os.O_RDONLY|os.O_DIRECTORY); "
        "\ntry: fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)"
        "\nexcept BlockingIOError: raise SystemExit(23)"
        "\nelse: fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)"
    )
    return precommit_artifacts.subprocess.run(
        [precommit_artifacts.sys.executable, "-c", probe, os.fspath(path)],
        check=False,
        capture_output=True,
        text=True,
    ).returncode


def test_closure_phase4_cert_flock_is_exclusive_and_releases_without_names(
    tmp_path: Path,
) -> None:
    tree = _open_phase4_cert_guard_test_tree(tmp_path)
    legacy_guard = (
        tmp_path
        / precommit_artifacts.CLOSURE_PHASE4_FINAL_CERTIFICATION_PRECOMMIT_GUARD
    )
    try:
        guard_fd, lease = (
            precommit_artifacts._acquire_closure_phase4_cert_precommit_guard(
                repo_root=tmp_path,
                tree_lease=tree,
            )
        )
        assert not legacy_guard.exists()
        assert _try_phase4_cert_flock(tmp_path / ".git") == 23
        assert (
            precommit_artifacts._release_closure_phase4_cert_precommit_guard(
                guard_fd,
                lease,
                tree_lease=tree,
            )
            is None
        )
        assert not legacy_guard.exists()
        assert _try_phase4_cert_flock(tmp_path / ".git") == 0
    finally:
        precommit_artifacts._close_closure_phase4_cert_tree_lease(tree)


def test_closure_phase4_cert_flock_rejects_legacy_guard_without_touching_it(
    tmp_path: Path,
) -> None:
    tree = _open_phase4_cert_guard_test_tree(tmp_path)
    legacy_guard = (
        tmp_path
        / precommit_artifacts.CLOSURE_PHASE4_FINAL_CERTIFICATION_PRECOMMIT_GUARD
    )
    legacy_guard.write_text("foreign\n", encoding="utf-8")
    before = legacy_guard.stat()
    try:
        with pytest.raises(
            precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
            match="must be absent",
        ):
            precommit_artifacts._acquire_closure_phase4_cert_precommit_guard(
                repo_root=tmp_path,
                tree_lease=tree,
            )
    finally:
        precommit_artifacts._close_closure_phase4_cert_tree_lease(tree)
    after = legacy_guard.stat()
    assert legacy_guard.read_text(encoding="utf-8") == "foreign\n"
    assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)


def test_closure_phase4_cert_flock_git_swap_releases_without_touching_foreign(
    tmp_path: Path,
) -> None:
    tree = _open_phase4_cert_guard_test_tree(tmp_path)
    guard_fd, lease = (
        precommit_artifacts._acquire_closure_phase4_cert_precommit_guard(
            repo_root=tmp_path,
            tree_lease=tree,
        )
    )
    git_dir = tmp_path / ".git"
    retained = tmp_path / ".git.retained"
    git_dir.rename(retained)
    git_dir.mkdir()
    foreign_marker = git_dir / "foreign-index"
    foreign_marker.write_text("foreign\n", encoding="utf-8")
    foreign_before = foreign_marker.stat()

    error = precommit_artifacts._release_closure_phase4_cert_precommit_guard(
        guard_fd,
        lease,
        tree_lease=tree,
    )

    assert error is not None
    assert "binding validation failed" in error
    foreign_after = foreign_marker.stat()
    assert foreign_marker.read_text(encoding="utf-8") == "foreign\n"
    assert (foreign_before.st_dev, foreign_before.st_ino) == (
        foreign_after.st_dev,
        foreign_after.st_ino,
    )
    assert _try_phase4_cert_flock(retained) == 0
    assert not (
        tmp_path
        / precommit_artifacts.CLOSURE_PHASE4_FINAL_CERTIFICATION_PRECOMMIT_GUARD
    ).exists()
    precommit_artifacts._close_closure_phase4_cert_tree_lease(tree)


def test_closure_phase4_cert_flock_root_swap_releases_without_foreign_effect(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repository"
    tree = _open_phase4_cert_guard_test_tree(repo)
    guard_fd, lease = (
        precommit_artifacts._acquire_closure_phase4_cert_precommit_guard(
            repo_root=repo,
            tree_lease=tree,
        )
    )
    retained = tmp_path / "repository.retained"
    repo.rename(retained)
    (repo / ".git").mkdir(parents=True)
    (repo / "tmp").mkdir()
    foreign_marker = repo / ".git" / "foreign-index"
    foreign_marker.write_text("foreign\n", encoding="utf-8")
    foreign_before = foreign_marker.stat()

    error = precommit_artifacts._release_closure_phase4_cert_precommit_guard(
        guard_fd,
        lease,
        tree_lease=tree,
    )

    assert error is not None
    assert "directory binding drifted" in error
    foreign_after = foreign_marker.stat()
    assert foreign_marker.read_text(encoding="utf-8") == "foreign\n"
    assert (foreign_before.st_dev, foreign_before.st_ino) == (
        foreign_after.st_dev,
        foreign_after.st_ino,
    )
    assert _try_phase4_cert_flock(retained / ".git") == 0
    precommit_artifacts._close_closure_phase4_cert_tree_lease(tree)


def _phase4_cert_test_git(repo_root: Path, *args: str) -> Any:
    return precommit_artifacts.subprocess.run(
        ["git", "-C", os.fspath(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _initialize_phase4_cert_test_git(repo_root: Path) -> None:
    repo_root.mkdir()
    _phase4_cert_test_git(repo_root, "init", "-q")
    (repo_root / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    _phase4_cert_test_git(repo_root, "add", "baseline.txt")
    _phase4_cert_test_git(
        repo_root,
        "-c",
        "user.name=Certification Test",
        "-c",
        "user.email=certification@example.invalid",
        "commit",
        "-q",
        "-m",
        "baseline",
    )


def test_closure_phase4_cert_git_add_uses_owned_fds_across_git_swap(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repository"
    _initialize_phase4_cert_test_git(repo)
    (repo / "cert.txt").write_text("certificate\n", encoding="utf-8")
    tree = precommit_artifacts._open_closure_phase4_cert_tree_lease(
        repo_root=repo,
        relative_directories=(".git",),
        context="test capability Git add",
    )
    retained = repo / ".git.retained"
    foreign_marker = repo / ".git" / "foreign-index"
    original_run = precommit_artifacts.run_command
    observed: dict[str, Any] = {}

    def racing_run(command: list[str], **kwargs: Any) -> CommandResult:
        observed["command"] = command
        observed["pass_fds"] = kwargs.get("pass_fds")
        (repo / ".git").rename(retained)
        (repo / ".git").mkdir()
        foreign_marker.write_text("foreign\n", encoding="utf-8")
        return original_run(command, **kwargs)

    monkeypatch.setattr(precommit_artifacts, "run_command", racing_run)
    try:
        result = precommit_artifacts._run_closure_phase4_cert_git_mutation(
            ["add", "-A", "--", "cert.txt"],
            tree_lease=tree,
        )
        assert result.returncode == 0
        with pytest.raises(
            precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
            match="directory binding drifted",
        ):
            precommit_artifacts._require_closure_phase4_cert_tree_binding(
                tree,
                context="post-add swap",
            )
    finally:
        precommit_artifacts._close_closure_phase4_cert_tree_lease(tree)
    assert observed["command"][1].startswith("--git-dir=/proc/self/fd/")
    assert observed["command"][2].startswith("--work-tree=/proc/self/fd/")
    assert len(observed["pass_fds"]) == 2
    assert foreign_marker.read_text(encoding="utf-8") == "foreign\n"
    staged = precommit_artifacts.subprocess.run(
        [
            "git",
            f"--git-dir={retained}",
            f"--work-tree={repo}",
            "diff",
            "--cached",
            "--name-only",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert staged == "cert.txt\n"


def test_closure_phase4_cert_git_restore_uses_owned_fds_across_git_swap(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repository"
    _initialize_phase4_cert_test_git(repo)
    (repo / "baseline.txt").write_text("changed\n", encoding="utf-8")
    _phase4_cert_test_git(repo, "add", "baseline.txt")
    tree = precommit_artifacts._open_closure_phase4_cert_tree_lease(
        repo_root=repo,
        relative_directories=(".git",),
        context="test capability Git restore",
    )
    retained = repo / ".git.retained"
    original_run = precommit_artifacts.run_command
    foreign_index_sha256 = ""

    def racing_run(command: list[str], **kwargs: Any) -> CommandResult:
        nonlocal foreign_index_sha256
        (repo / ".git").rename(retained)
        _phase4_cert_test_git(repo, "init", "-q")
        (repo / "foreign.txt").write_text("foreign\n", encoding="utf-8")
        _phase4_cert_test_git(repo, "add", "foreign.txt")
        foreign_index_sha256 = hashlib.sha256(
            (repo / ".git" / "index").read_bytes()
        ).hexdigest()
        return original_run(command, **kwargs)

    monkeypatch.setattr(precommit_artifacts, "run_command", racing_run)
    try:
        result = precommit_artifacts._run_closure_phase4_cert_git_mutation(
            ["restore", "--source=HEAD", "--staged", "--", "baseline.txt"],
            tree_lease=tree,
        )
        assert result.returncode == 0
    finally:
        precommit_artifacts._close_closure_phase4_cert_tree_lease(tree)
    assert hashlib.sha256((repo / ".git" / "index").read_bytes()).hexdigest() == (
        foreign_index_sha256
    )
    retained_staged = precommit_artifacts.subprocess.run(
        [
            "git",
            f"--git-dir={retained}",
            f"--work-tree={repo}",
            "diff",
            "--cached",
            "--name-only",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert retained_staged == ""


def test_closure_phase4_cert_staged_double_recapture_rejects_semantic_drift(
    monkeypatch,
) -> None:
    physical = (_phase4_cert_identity(),)
    semantic = iter(("before", "after"))
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_staged_git_state",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda *_args: precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_v2_history",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_refs",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_runtime_namespaces",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_cert_files",
        lambda *_args, **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_closure_phase4_cert_index_bindings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_cert_semantic_digest",
        lambda *_args, **_kwargs: next(semantic),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="double recapture",
    ):
        precommit_artifacts.validate_closure_phase4_cert_staged_transaction(
            "H-CERT"
        )


def test_closure_phase4_p_cert_semantic_digest_requires_exact_reconstruction(
    monkeypatch,
) -> None:
    from src.experiments import lock_phase4_final_certification as locker
    from src.reporting import phase4_final_certification_contract as contract_module

    head = "a" * 40
    contract = SimpleNamespace(test_suite=SimpleNamespace(status="locked"))
    authority = {"gate": "P-CERT", "status": "locked_unpublished"}
    manifest = {
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "manifest_last": True,
    }
    expected = {
        contract_module.AUTHORITY_PATH.as_posix(): (
            contract_module.canonical_json_bytes(authority)
        ),
        contract_module.AUTHORITY_MANIFEST_PATH.as_posix(): (
            contract_module.canonical_json_bytes(manifest)
        ),
    }
    validated: list[Any] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_contract",
        lambda **_kwargs: contract,
    )
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: head)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_published_h_cert",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(locker, "_validate_published_h", lambda *_args: [])
    monkeypatch.setattr(locker, "_collect_contract_state", lambda *_args: {})
    monkeypatch.setattr(locker, "_build_authority", lambda *_args: authority)
    monkeypatch.setattr(locker, "_build_manifest", lambda *_args: manifest)
    monkeypatch.setattr(locker, "validate_authority", validated.append)
    monkeypatch.setattr(
        precommit_artifacts,
        "_read_closure_phase4_cert_file",
        lambda path, **_kwargs: expected[path],
    )

    digest = precommit_artifacts._closure_phase4_cert_semantic_digest(
        "P-CERT", repo_root=Path(".")
    )
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert validated == [authority]

    expected[contract_module.AUTHORITY_PATH.as_posix()] = (
        contract_module.canonical_json_bytes(
            {"gate": "P-CERT", "status": "tampered"}
        )
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="differs from exact canonical",
    ):
        precommit_artifacts._closure_phase4_cert_semantic_digest(
            "P-CERT", repo_root=Path(".")
        )


def test_closure_phase4_h_cert_semantic_digest_requires_read_only_h3_preflight(
    monkeypatch,
) -> None:
    from src.experiments import lock_phase4_final_certification as locker
    from src.reporting import phase4_final_certification_contract as contract_module

    suite = SimpleNamespace(
        status="locked",
        selector_count=39,
        collected_test_count=905,
        nodeids_sha256="a" * 64,
        allowed_skip_count=7,
    )
    contract = SimpleNamespace(test_suite=suite, output_paths=("one", "two"))
    result = {
        "status": "ready_to_publish_h",
        "h1_cert_commit": precommit_artifacts.CLOSURE_PHASE4_H_CERT_V1_COMMIT,
        "p1_cert_commit": precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_COMMIT,
        "h2_cert_commit": precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_COMMIT,
        "p2_cert_commit": precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT,
        "h_cert_commit": None,
        "h3_cert_commit": None,
        "writes_performed": False,
        "dvc_status_checked": False,
        "dvc_pull_commands_run": False,
        "test_commands_run": False,
        "parquet_payloads_opened": False,
        "raw_targets_accessed": False,
        "raw_outcomes_accessed": False,
        "git_publication_commands_run": False,
    }
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_contract",
        lambda **_kwargs: contract,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda *_args: precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT,
    )
    monkeypatch.setattr(locker, "check_only", lambda **_kwargs: result)
    monkeypatch.setattr(
        contract_module,
        "collect_anchor_input_records",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        contract_module,
        "collect_dvc_pointer_records",
        lambda *_args, **_kwargs: [],
    )
    digest = precommit_artifacts._closure_phase4_cert_semantic_digest(
        "H-CERT", repo_root=Path(".")
    )
    assert re.fullmatch(r"[0-9a-f]{64}", digest)

    result["dvc_status_checked"] = True
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="not publication-ready",
    ):
        precommit_artifacts._closure_phase4_cert_semantic_digest(
            "H-CERT", repo_root=Path(".")
        )


def test_closure_phase4_cert_rollback_is_parent_directed_and_preserves_foreign(
    monkeypatch,
) -> None:
    commands: list[list[str]] = []
    physical = (_phase4_cert_identity(),)

    def run(command: list[str], **_kwargs: Any) -> CommandResult:
        commands.append(command)
        return CommandResult(command, 0, "", "")

    def git_output(_root: Path, *args: str) -> str:
        if args[:3] == ("diff", "--cached", "--name-status"):
            return "A\tforeign.txt\n"
        if args[:2] == ("status", "--short"):
            return _phase4_cert_short_status("P-CERT", staged=False) + "A  foreign.txt\n"
        return ""

    monkeypatch.setattr(precommit_artifacts, "run_command", run)

    def git_mutation(args: Any, **_kwargs: Any) -> CommandResult:
        command = ["git-capability", *list(args)]
        commands.append(command)
        return CommandResult(command, 0, "", "")

    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_cert_git_mutation",
        git_mutation,
    )
    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_cert_files",
        lambda *_args, **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_cert_semantic_digest",
        lambda *_args, **_kwargs: "semantic",
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_transaction_tree",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_cert_dvc_status",
        lambda *_args, **_kwargs: {},
    )
    assert (
        precommit_artifacts._rollback_closure_phase4_cert_staging(
            gate="P-CERT",
            parent_commit="b" * 40,
            physical_before=physical,
            semantic_before="semantic",
            dvc_runtime=cast(Any, SimpleNamespace()),
            dvc_status_before={},
            repo_root=Path("."),
            tree_lease=cast(Any, SimpleNamespace()),
        )
        is None
    )
    assert commands == [
        [
            "git-capability",
            "restore",
            f"--source={'b' * 40}",
            "--staged",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE4_P_CERT_STAGED_SCOPE),
        ]
    ]


def _install_phase4_cert_runner_harness(
    monkeypatch: Any,
    gate: str = "P-CERT",
    *,
    real_tree: bool = False,
) -> dict[str, Any]:
    physical = (_phase4_cert_identity(),)
    state: dict[str, Any] = {"staged": False, "commands": [], "released": 0}
    monkeypatch.setattr(
        precommit_artifacts,
        "_acquire_closure_phase4_cert_precommit_guard",
        lambda **_kwargs: (31, SimpleNamespace()),
    )

    def release(*_args: Any, **_kwargs: Any) -> None:
        state["released"] += 1
        return None

    monkeypatch.setattr(
        precommit_artifacts,
        "_release_closure_phase4_cert_precommit_guard",
        release,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_precommit_guard_binding",
        lambda *_args, **_kwargs: None,
    )
    if not real_tree:
        monkeypatch.setattr(
            precommit_artifacts,
            "_open_closure_phase4_cert_transaction_tree",
            lambda *_args, **_kwargs: SimpleNamespace(),
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "_require_closure_phase4_cert_tree_binding",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            precommit_artifacts,
            "_close_closure_phase4_cert_tree_lease",
            lambda *_args, **_kwargs: None,
        )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_cert_invocation",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "closure_phase4_cert_pre_stage_scope",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_snapshot_closure_phase4_cert_files",
        lambda *_args, **_kwargs: physical,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_cert_semantic_digest",
        lambda *_args, **_kwargs: "semantic",
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "load_configured_dvc_artifacts",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_initialize_closure_phase4_cert_dvc_observation",
        lambda *_args, **_kwargs: (SimpleNamespace(), {}),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_cert_dvc_status",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_close_closure_phase4_cert_dvc_runtime",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_cert_publication_check",
        lambda **_kwargs: CommandResult(["publication-check"], 1, "", "U1 U2 U3"),
    )

    def git_output(_root: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD^{commit}"):
            return "c" * 40
        if args[:3] == ("diff", "--cached", "--name-status"):
            return _phase4_cert_name_status(gate) if state["staged"] else ""
        if args[:2] == ("status", "--short"):
            return _phase4_cert_short_status(gate, staged=state["staged"])
        return ""

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)

    def run(command: list[str], **_kwargs: Any) -> CommandResult:
        state["commands"].append(command)
        return CommandResult(command, 0, "", "")

    monkeypatch.setattr(precommit_artifacts, "run_command", run)

    def git_mutation(args: Any, **_kwargs: Any) -> CommandResult:
        command = ["git-capability", *list(args)]
        state["commands"].append(command)
        if command[1:2] == ["add"]:
            state["staged"] = True
        return CommandResult(command, 0, "", "")

    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_cert_git_mutation",
        git_mutation,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_closure_phase4_cert_staged_transaction",
        lambda *_args, **_kwargs: (physical, "semantic"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "reproducibility_checks",
        lambda **_kwargs: [
            precommit_artifacts.ReproducibilityFinding("ok", "manifest", "-", "ok")
        ],
    )
    monkeypatch.setattr(precommit_artifacts, "write_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        precommit_artifacts,
        "default_report_path",
        lambda: Path("tmp/cert-report.md"),
    )
    return state


def _make_phase4_cert_transaction_directories(
    repo_root: Path, gate: str = "P-CERT"
) -> None:
    for raw_directory in (
        precommit_artifacts._closure_phase4_cert_transaction_directories(gate)
    ):
        (repo_root / raw_directory).mkdir(parents=True, exist_ok=True)


@pytest.mark.parametrize(
    "boundary",
    ("semantic", "index", "status", "remote", "dvc"),
)
@pytest.mark.parametrize("gate", ("H-CERT", "P-CERT", "R-CERT"))
def test_closure_phase4_cert_runner_rejects_parent_swap_at_external_boundaries(
    gate: str,
    boundary: str,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _make_phase4_cert_transaction_directories(tmp_path, gate)
    monkeypatch.chdir(tmp_path)
    state = _install_phase4_cert_runner_harness(
        monkeypatch,
        gate,
        real_tree=True,
    )
    config_parent = tmp_path / "configs"
    retained = tmp_path / "configs.retained"
    foreign = tmp_path / "configs.foreign"
    foreign.mkdir()
    swapped = False

    def swap_parent() -> None:
        nonlocal swapped
        if swapped:
            return
        swapped = True
        config_parent.rename(retained)
        config_parent.symlink_to(foreign, target_is_directory=True)

    if boundary == "semantic":
        monkeypatch.setattr(
            precommit_artifacts,
            "_closure_phase4_cert_semantic_digest",
            lambda *_args, **_kwargs: (swap_parent() or "semantic"),
        )
    elif boundary in {"index", "status"}:
        original_git_output = precommit_artifacts._git_output

        def racing_git_output(root: Path, *args: str) -> str:
            result = original_git_output(root, *args)
            if (
                boundary == "index"
                and args[:3] == ("diff", "--cached", "--name-status")
            ) or (
                boundary == "status"
                and args[:2] == ("status", "--short")
            ):
                swap_parent()
            return result

        monkeypatch.setattr(
            precommit_artifacts,
            "_git_output",
            racing_git_output,
        )
    elif boundary == "remote":
        monkeypatch.setattr(
            precommit_artifacts,
            "closure_phase4_cert_pre_stage_scope",
            lambda *_args, **_kwargs: (swap_parent() or True),
        )
    else:
        monkeypatch.setattr(
            precommit_artifacts,
            "_initialize_closure_phase4_cert_dvc_observation",
            lambda *_args, **_kwargs: (
                swap_parent() or (SimpleNamespace(), {})
            ),
        )

    result = precommit_artifacts._run_closure_phase4_cert_precommit(
        _closure_phase3_h_args(),
        gate=gate,
        initial_status=_phase4_cert_short_status(gate, staged=False),
        repo_root=Path("."),
    )
    assert result == 2
    assert swapped is True
    assert state["staged"] is False
    assert state["released"] == 1
    assert config_parent.is_symlink()
    assert retained.is_dir()


def test_closure_phase4_cert_rollback_refuses_replaced_parent_without_mutation(
    tmp_path: Path, monkeypatch
) -> None:
    _make_phase4_cert_transaction_directories(tmp_path)
    lease = precommit_artifacts._open_closure_phase4_cert_transaction_tree(
        "P-CERT",
        repo_root=tmp_path,
        require_cwd=False,
    )
    config_parent = tmp_path / "configs"
    retained = tmp_path / "configs.retained"
    foreign = tmp_path / "configs.foreign"
    foreign.mkdir()
    config_parent.rename(retained)
    config_parent.symlink_to(foreign, target_is_directory=True)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "run_command",
        lambda command, **_kwargs: commands.append(command)
        or CommandResult(command, 0, "", ""),
    )
    try:
        error = precommit_artifacts._rollback_closure_phase4_cert_staging(
            gate="P-CERT",
            parent_commit="c" * 40,
            physical_before=(_phase4_cert_identity(),),
            semantic_before="semantic",
            dvc_runtime=cast(Any, SimpleNamespace()),
            dvc_status_before={},
            repo_root=tmp_path,
            tree_lease=lease,
        )
    finally:
        precommit_artifacts._close_closure_phase4_cert_tree_lease(lease)
    assert error is not None
    assert "refused" in error
    assert commands == []
    assert config_parent.is_symlink()
    assert retained.is_dir()


def test_closure_phase4_cert_runner_rejects_cwd_switch_during_semantics(
    tmp_path: Path, monkeypatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _make_phase4_cert_transaction_directories(repository)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    monkeypatch.chdir(repository)
    state = _install_phase4_cert_runner_harness(
        monkeypatch,
        real_tree=True,
    )

    def switch_cwd(*_args: Any, **_kwargs: Any) -> str:
        os.chdir(foreign)
        return "semantic"

    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_cert_semantic_digest",
        switch_cwd,
    )
    result = precommit_artifacts._run_closure_phase4_p_cert_precommit(
        _closure_phase3_h_args(),
        initial_status=_phase4_cert_short_status("P-CERT", staged=False),
        repo_root=Path("."),
    )
    assert result == 2
    assert state["staged"] is False
    assert state["released"] == 1


@pytest.mark.parametrize("swap_target", ("dvc", "python"))
def test_closure_phase4_cert_dvc_runtime_executes_owned_fds_not_foreign(
    swap_target: str, tmp_path: Path, monkeypatch
) -> None:
    _make_phase4_cert_transaction_directories(tmp_path)
    base_python = Path(
        cast(
            str,
            getattr(
                precommit_artifacts.sys,
                "_base_executable",
                precommit_artifacts.sys.executable,
            ),
        )
    )
    python_path = tmp_path / ".venv/bin/python"
    python_path.symlink_to(base_python)
    (tmp_path / ".venv/pyvenv.cfg").write_text(
        f"home = {base_python.parent.as_posix()}\n"
        "include-system-site-packages = false\n"
        f"version = {precommit_artifacts.sys.version_info.major}."
        f"{precommit_artifacts.sys.version_info.minor}\n",
        encoding="utf-8",
    )
    dvc_path = tmp_path / precommit_artifacts.DEFAULT_DVC_BIN
    dvc_path.write_text("#!/usr/bin/env python\nprint('{}')\n", encoding="utf-8")
    dvc_path.chmod(0o755)
    foreign = dvc_path.with_name("dvc.foreign")
    marker = tmp_path / "foreign-runtime-ran"
    foreign.write_text(
        f"#!/usr/bin/env python\nfrom pathlib import Path\n"
        f"Path({marker.as_posix()!r}).touch()\nprint('{{}}')\n",
        encoding="utf-8",
    )
    foreign.chmod(0o755)
    retained_dvc = dvc_path.with_name("dvc.retained")
    foreign_python = tmp_path / "foreign-python"
    foreign_python.write_text(
        f"#!/bin/sh\ntouch {marker.as_posix()}\nexit 97\n",
        encoding="utf-8",
    )
    foreign_python.chmod(0o755)
    foreign_launcher = python_path.with_name("python.foreign")
    foreign_launcher.symlink_to(foreign_python)
    retained_python = python_path.with_name("python.retained")
    tree = precommit_artifacts._open_closure_phase4_cert_transaction_tree(
        "P-CERT",
        repo_root=tmp_path,
        require_cwd=False,
    )
    script = precommit_artifacts._open_closure_phase4_cert_executable(
        precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
        tree_lease=tree,
        context="test DVC",
    )
    interpreter = (
        precommit_artifacts._open_closure_phase4_cert_python_interpreter(
            tree_lease=tree,
        )
    )
    runtime = precommit_artifacts.ClosurePhase4FinalCertificationDvcRuntimeLease(
        script=script,
        interpreter=interpreter,
    )
    venv_fd = precommit_artifacts._closure_phase4_cert_tree_directory_fd(
        tree,
        ".venv",
    )
    original_run = precommit_artifacts.run_command
    observed: dict[str, Any] = {}

    def racing_run(command: list[str], **kwargs: Any) -> CommandResult:
        observed["command"] = command
        observed["pass_fds"] = kwargs.get("pass_fds")
        if swap_target == "dvc":
            dvc_path.rename(retained_dvc)
            foreign.rename(dvc_path)
        else:
            python_path.rename(retained_python)
            foreign_launcher.rename(python_path)
        return original_run(command, **kwargs)

    monkeypatch.setattr(precommit_artifacts, "run_command", racing_run)
    try:
        with pytest.raises(
            precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
            match="binding drifted",
        ):
            precommit_artifacts._closure_phase4_cert_dvc_status(
                runtime,
                tree_lease=tree,
            )
    finally:
        precommit_artifacts._close_closure_phase4_cert_dvc_runtime(runtime)
        precommit_artifacts._close_closure_phase4_cert_tree_lease(tree)
    assert observed["command"][0].startswith("/proc/self/fd/")
    assert observed["command"][1].startswith("/proc/self/fd/")
    assert set(observed["pass_fds"]) == {
        script.fd,
        interpreter.fd,
        venv_fd,
    }
    assert not marker.exists()


def test_closure_phase4_cert_checker_executes_owned_fd_not_foreign_replacement(
    tmp_path: Path, monkeypatch
) -> None:
    _make_phase4_cert_transaction_directories(tmp_path)
    checker = tmp_path / "scripts/check_repo_publication_ready.sh"
    checker.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    checker.chmod(0o755)
    foreign = checker.with_name("checker.foreign")
    marker = tmp_path / "foreign-checker-ran"
    foreign.write_text(
        f"#!/bin/sh\ntouch {marker.as_posix()}\nexit 1\n",
        encoding="utf-8",
    )
    foreign.chmod(0o755)
    retained = checker.with_name("checker.retained")
    tree = precommit_artifacts._open_closure_phase4_cert_transaction_tree(
        "P-CERT",
        repo_root=tmp_path,
        require_cwd=False,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_h_syn_publication_payloads",
        lambda **_kwargs: {"sealed.json": b"{}\n"},
    )
    original_run = precommit_artifacts.run_command
    observed: dict[str, Any] = {}

    def racing_run(command: list[str], **kwargs: Any) -> CommandResult:
        observed["command"] = command
        observed["pass_fds"] = kwargs.get("pass_fds")
        checker.rename(retained)
        foreign.rename(checker)
        return original_run(command, **kwargs)

    monkeypatch.setattr(precommit_artifacts, "run_command", racing_run)
    try:
        with pytest.raises(
            precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
            match="executable name/inode binding drifted",
        ):
            precommit_artifacts._run_closure_phase4_cert_publication_check(
                repo_root=tmp_path,
                tree_lease=tree,
            )
    finally:
        precommit_artifacts._close_closure_phase4_cert_tree_lease(tree)
    assert observed["command"][0] == "/bin/bash"
    assert observed["command"][1].startswith("/proc/self/fd/")
    assert len(observed["pass_fds"]) == 1
    assert not marker.exists()


def test_closure_phase4_cert_runner_stages_only_exact_scope_without_execution(
    monkeypatch, capsys
) -> None:
    state = _install_phase4_cert_runner_harness(monkeypatch)
    args = _closure_phase3_h_args()
    initial = _phase4_cert_short_status("P-CERT", staged=False)
    assert (
        precommit_artifacts._run_closure_phase4_p_cert_precommit(
            args,
            initial_status=initial,
            repo_root=Path("."),
        )
        == 0
    )
    assert state["released"] == 1
    assert state["commands"] == [
        [
            "git-capability",
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.CLOSURE_PHASE4_P_CERT_STAGED_SCOPE),
        ]
    ]
    assert "no certification or DVC mutation ran" in capsys.readouterr().out


def test_closure_phase4_cert_runner_never_rolls_back_after_flock_release(
    monkeypatch,
) -> None:
    state = _install_phase4_cert_runner_harness(monkeypatch)
    rollback_calls: list[str] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_rollback_closure_phase4_cert_staging",
        lambda **kwargs: rollback_calls.append(kwargs["gate"]) or None,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_close_closure_phase4_cert_tree_lease",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic post-unlock descriptor-close failure")
        ),
    )

    result = precommit_artifacts._run_closure_phase4_p_cert_precommit(
        _closure_phase3_h_args(),
        initial_status=_phase4_cert_short_status("P-CERT", staged=False),
        repo_root=Path("."),
    )

    assert result == 2
    assert state["staged"] is True
    assert state["released"] == 1
    assert rollback_calls == []


def test_closure_phase4_cert_runner_rolls_back_on_post_add_dvc_drift(
    monkeypatch,
) -> None:
    state = _install_phase4_cert_runner_harness(monkeypatch)
    calls = 0

    def dvc(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {} if calls == 1 else {"changed": ["models"]}

    monkeypatch.setattr(
        precommit_artifacts,
        "_closure_phase4_cert_dvc_status",
        dvc,
    )
    rolled_back: list[str] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_rollback_closure_phase4_cert_staging",
        lambda **kwargs: rolled_back.append(kwargs["gate"]) or None,
    )
    assert (
        precommit_artifacts._run_closure_phase4_p_cert_precommit(
            _closure_phase3_h_args(),
            initial_status=_phase4_cert_short_status("P-CERT", staged=False),
            repo_root=Path("."),
        )
        == 2
    )
    assert state["staged"] is True
    assert rolled_back == ["P-CERT"]
    assert state["released"] == 1


def test_closure_phase4_cert_runner_rejects_extra_generic_finding_and_rolls_back(
    monkeypatch,
) -> None:
    state = _install_phase4_cert_runner_harness(monkeypatch)
    monkeypatch.setattr(
        precommit_artifacts,
        "reproducibility_checks",
        lambda **_kwargs: [
            precommit_artifacts.ReproducibilityFinding(
                "warn", "manifest", "foreign", "extra checker finding"
            )
        ],
    )
    rolled_back: list[str] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_rollback_closure_phase4_cert_staging",
        lambda **kwargs: rolled_back.append(kwargs["gate"]) or None,
    )
    assert (
        precommit_artifacts._run_closure_phase4_p_cert_precommit(
            _closure_phase3_h_args(),
            initial_status=_phase4_cert_short_status("P-CERT", staged=False),
            repo_root=Path("."),
        )
        == 2
    )
    assert state["staged"] is True
    assert rolled_back == ["P-CERT"]


def test_closure_phase4_cert_runner_rejects_publication_checker_extra_before_add(
    monkeypatch,
) -> None:
    state = _install_phase4_cert_runner_harness(monkeypatch)
    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_cert_publication_check",
        lambda **_kwargs: (_ for _ in ()).throw(
            precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError(
                "unexpected publication finding"
            )
        ),
    )
    assert (
        precommit_artifacts._run_closure_phase4_p_cert_precommit(
            _closure_phase3_h_args(),
            initial_status=_phase4_cert_short_status("P-CERT", staged=False),
            repo_root=Path("."),
        )
        == 2
    )
    assert state["commands"] == []
    assert state["released"] == 1


def test_closure_phase4_cert_runner_rolls_back_on_post_add_publication_extra(
    monkeypatch,
) -> None:
    state = _install_phase4_cert_runner_harness(monkeypatch)
    calls = 0

    def publication(**_kwargs: Any) -> CommandResult:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError(
                "new staged publication finding"
            )
        return CommandResult(["publication-check"], 1, "", "U1 U2 U3")

    monkeypatch.setattr(
        precommit_artifacts,
        "_run_closure_phase4_cert_publication_check",
        publication,
    )
    rolled_back: list[str] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_rollback_closure_phase4_cert_staging",
        lambda **kwargs: rolled_back.append(kwargs["gate"]) or None,
    )
    assert (
        precommit_artifacts._run_closure_phase4_p_cert_precommit(
            _closure_phase3_h_args(),
            initial_status=_phase4_cert_short_status("P-CERT", staged=False),
            repo_root=Path("."),
        )
        == 2
    )
    assert calls == 2
    assert state["staged"] is True
    assert rolled_back == ["P-CERT"]
    assert state["released"] == 1


def test_closure_phase4_cert_runner_rejects_divergent_repo_root_before_guard(
    tmp_path: Path, monkeypatch
) -> None:
    calls = 0

    def acquire(**_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("guard must not be acquired for divergent root")

    monkeypatch.setattr(
        precommit_artifacts,
        "_acquire_closure_phase4_cert_precommit_guard",
        acquire,
    )
    assert (
        precommit_artifacts._run_closure_phase4_p_cert_precommit(
            _closure_phase3_h_args(),
            initial_status="",
            repo_root=tmp_path,
        )
        == 2
    )
    assert calls == 0


def test_closure_phase4_final_manifest_generic_dialect_has_no_warning(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    output_paths = [
        Path(path)
        for path in precommit_artifacts.CLOSURE_PHASE4_R_CERT_STAGED_SCOPE
    ]
    for index, path in enumerate(output_paths[:-1]):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"artifact-{index}\n".encode())
    input_paths = [Path("docs/anchor.md"), Path("data/pointer.parquet.dvc")]
    for index, path in enumerate(input_paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"input-{index}\n".encode())

    def record(path: Path) -> dict[str, Any]:
        payload = path.read_bytes()
        return {
            "path": path.as_posix(),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    manifest = {
        "status": "completed",
        "artifacts": [record(path) for path in output_paths[:-1]],
        "published_anchors": [record(input_paths[0])],
        "dvc_pointer_records": [record(input_paths[1])],
    }
    output_paths[-1].write_text(json.dumps(manifest), encoding="utf-8")
    findings = validate_experiment_manifests(
        staged_paths=set(output_paths),
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )
    assert findings
    assert {finding.level for finding in findings} == {"ok"}
    assert "Checked 1 experiment manifest" in findings[-1].message

    manifest["status"] = "completed_unpublished"
    output_paths[-1].write_text(json.dumps(manifest), encoding="utf-8")
    drifted = validate_experiment_manifests(
        staged_paths=set(output_paths),
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )
    assert any(
        finding.level == "fail" and "expected `completed`" in finding.message
        for finding in drifted
    )


def test_closure_phase4_r_cert_delegates_mutated_report_to_custom_validator(
    monkeypatch,
) -> None:
    from src.reporting import build_phase4_final_certification as builder
    from src.reporting import phase4_final_certification_contract as contract_module

    head = "a" * 40
    output_paths = tuple(
        precommit_artifacts.CLOSURE_PHASE4_R_CERT_STAGED_SCOPE
    )
    contract = SimpleNamespace(output_paths=output_paths, dvc_pointers=())
    manifest_bytes = contract_module.canonical_json_bytes({"status": "completed"})
    observed: dict[str, bytes] = {}

    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_contract",
        lambda **_kwargs: contract,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_git_output",
        lambda *_args: head,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_published_p_cert",
        lambda *_args, **_kwargs: "b" * 40,
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_r_cert_namespace_exact",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        contract_module,
        "load_effective_authority",
        lambda *_args, **_kwargs: {
            "p_cert_commit": head,
            "p3_cert_commit": head,
            "h_cert_commit": "b" * 40,
            "h3_cert_commit": "b" * 40,
            "p2_cert_commit": (
                precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT
            ),
            "h2_cert_commit": (
                precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_COMMIT
            ),
            "p1_cert_commit": (
                precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_COMMIT
            ),
            "h1_cert_commit": (
                precommit_artifacts.CLOSURE_PHASE4_H_CERT_V1_COMMIT
            ),
        },
    )

    mutated_path = "reports/closure_v1/12_certification/test_report.md"

    def read(path: str, **_kwargs: Any) -> bytes:
        if path == output_paths[-1]:
            return manifest_bytes
        if path == mutated_path:
            return b"# tests\nMUTATED VERIFICATION\n"
        return f"payload:{path}\n".encode()

    monkeypatch.setattr(
        precommit_artifacts,
        "_read_closure_phase4_cert_file",
        read,
    )

    def validate(*, artifacts: Any, **_kwargs: Any) -> None:
        observed.update(artifacts)
        if artifacts["test_report.md"] != b"# tests\n":
            raise builder.FinalCertificationBuildError(
                "published test report reconstruction drifted"
            )

    monkeypatch.setattr(
        builder,
        "validate_final_certification_payloads",
        validate,
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match="test report reconstruction drifted",
    ):
        precommit_artifacts._closure_phase4_cert_semantic_digest(
            "R-CERT", repo_root=Path(".")
        )
    assert observed["test_report.md"] == b"# tests\nMUTATED VERIFICATION\n"


def _phase4_r_cert_adapter_payloads() -> tuple[Any, dict[str, Any], list[Any], list[Any], dict[str, Any]]:
    from src.reporting import phase4_final_certification_contract as contract_module

    head = "a" * 40
    specs = tuple(
        SimpleNamespace(
            path=f"data/pointer-{index}.parquet.dvc",
            output_path=f"data/pointer-{index}.parquet",
            role=f"role-{index}",
            md5=f"{index + 1:032x}",
            size=100 + index,
        )
        for index in range(8)
    )
    contract = SimpleNamespace(
        output_paths=tuple(precommit_artifacts.CLOSURE_PHASE4_R_CERT_STAGED_SCOPE),
        dvc_pointers=specs,
    )
    anchors = [
        {"path": "docs/anchor.md", "bytes": 1, "sha256": "1" * 64}
    ]
    pointers = [
        {
            "path": spec.path,
            "role": spec.role,
            "output_path": spec.output_path,
            "payload_md5": spec.md5,
            "payload_bytes": spec.size,
            "sha256": f"{index + 1:064x}",
        }
        for index, spec in enumerate(specs)
    ]
    effective = {
        "p_cert_commit": head,
        "p3_cert_commit": head,
        "h_cert_commit": "b" * 40,
        "h3_cert_commit": "b" * 40,
        "p2_cert_commit": precommit_artifacts.CLOSURE_PHASE4_P_CERT_V2_COMMIT,
        "h2_cert_commit": precommit_artifacts.CLOSURE_PHASE4_H_CERT_V2_COMMIT,
        "p1_cert_commit": precommit_artifacts.CLOSURE_PHASE4_P_CERT_V1_COMMIT,
        "h1_cert_commit": precommit_artifacts.CLOSURE_PHASE4_H_CERT_V1_COMMIT,
        "authority_bytes": b"authority\n",
        "authority_sha256": hashlib.sha256(b"authority\n").hexdigest(),
        "manifest_bytes": b"companion\n",
        "manifest_sha256": hashlib.sha256(b"companion\n").hexdigest(),
    }
    restores = [
        {
            "ordinal": index,
            "pointer_path": spec.path,
            "output_path": spec.output_path,
            "role": spec.role,
            "pointer_declared_md5": spec.md5,
            "pointer_declared_bytes": spec.size,
            "pointer_sha256": pointer["sha256"],
            "pull_command": {
                "argv": [
                    ".venv/bin/dvc",
                    "pull",
                    "--no-run-cache",
                    "-j",
                    "1",
                    spec.path,
                ],
                "returncode": 0,
            },
            "directed_status_command": {
                "argv": [".venv/bin/dvc", "status", "--json", spec.path],
                "returncode": 0,
            },
            "one_pointer_per_command": True,
            "restored_output_regular_single_link": True,
            "cache_object_path_from_declared_md5": True,
            "dvc_transport_authentication_passed": True,
            "payload_opened_by_python": False,
            "payload_decoded": False,
        }
        for index, (spec, pointer) in enumerate(
            zip(specs, pointers, strict=True), start=1
        )
    ]
    manifest = {
        "status": "completed",
        "p_cert_authority": {
            "path": contract_module.AUTHORITY_PATH.as_posix(),
            "bytes": len(effective["authority_bytes"]),
            "sha256": effective["authority_sha256"],
            "p_cert_commit": head,
            "h_cert_commit": effective["h_cert_commit"],
            "p3_cert_commit": head,
            "h3_cert_commit": effective["h3_cert_commit"],
            "p2_cert_commit": effective["p2_cert_commit"],
            "h2_cert_commit": effective["h2_cert_commit"],
            "p1_cert_commit": effective["p1_cert_commit"],
            "h1_cert_commit": effective["h1_cert_commit"],
        },
        "p_cert_companion_manifest": {
            "path": contract_module.AUTHORITY_MANIFEST_PATH.as_posix(),
            "bytes": len(effective["manifest_bytes"]),
            "sha256": effective["manifest_sha256"],
            "p_cert_commit": head,
            "h_cert_commit": effective["h_cert_commit"],
            "p3_cert_commit": head,
            "h3_cert_commit": effective["h3_cert_commit"],
            "p2_cert_commit": effective["p2_cert_commit"],
            "h2_cert_commit": effective["h2_cert_commit"],
            "p1_cert_commit": effective["p1_cert_commit"],
            "h1_cert_commit": effective["h1_cert_commit"],
        },
        "published_anchors": anchors,
        "published_anchor_records_sha256": contract_module.digest_records(anchors),
        "dvc_pointer_records": pointers,
        "dvc_pointer_records_sha256": contract_module.digest_records(pointers),
        "dvc_restores": restores,
        "clone": {
            "command": {
                "argv": [
                    "git",
                    "clone",
                    "--no-local",
                    "--no-hardlinks",
                    "--single-branch",
                    "--branch",
                    "main",
                    "<LIVE_ORIGIN_MAIN>",
                    "<OWNED_CLONE>",
                ],
                "returncode": 0,
            },
            "execution_commit": head,
            "initially_clean": True,
            "single_parent": True,
            "source": "live_origin_main",
            "remote_url_serialized": False,
            "local_dvc_remote_configuration": {
                "present": True,
                "regular_file": True,
                "single_link": True,
                "git_ignored": True,
                "source_mode_accepted": "0600_or_0644",
                "clone_mode": "0600",
                "copied_only_into_owned_clone": True,
                "content_read_only_for_private_copy": True,
                "content_path_remote_url_and_credentials_serialized": False,
            },
            "dvc_cache": {
                "object_count": 8,
                "declared_payload_bytes": sum(spec.size for spec in specs),
                "exact_pointer_objects_only": True,
                "content_addressed_paths_from_declared_md5": True,
                "payload_objects_opened_by_python": False,
                "payloads_decoded": False,
            },
        },
    }
    return contract, effective, anchors, pointers, manifest


@pytest.mark.parametrize(
    "mutator,match",
    [
        (
            lambda value: value["p_cert_authority"].__setitem__(
                "sha256", "0" * 64
            ),
            "authority/anchor/pointer",
        ),
        (
            lambda value: value.pop("p_cert_companion_manifest"),
            "authority/anchor/pointer",
        ),
        (
            lambda value: value["p_cert_authority"].__setitem__(
                "p1_cert_commit", "0" * 40
            ),
            "authority/anchor/pointer",
        ),
        (
            lambda value: value["p_cert_companion_manifest"].__setitem__(
                "p2_cert_commit", "0" * 40
            ),
            "authority/anchor/pointer",
        ),
        (
            lambda value: value["p_cert_authority"].__setitem__(
                "p3_cert_commit", "0" * 40
            ),
            "authority/anchor/pointer",
        ),
        (
            lambda value: value["p_cert_companion_manifest"].__setitem__(
                "h3_cert_commit", "0" * 40
            ),
            "authority/anchor/pointer",
        ),
        (
            lambda value: value["clone"][
                "local_dvc_remote_configuration"
            ].__setitem__("clone_mode", "0644"),
            "isolated clone",
        ),
        (
            lambda value: value["clone"].__setitem__("legacy_alias", True),
            "isolated clone",
        ),
    ],
)
def test_closure_phase4_r_cert_positive_path_binds_split_authority_and_clone_exactly(
    mutator: Any,
    match: str,
    monkeypatch,
) -> None:
    from src.reporting import build_phase4_final_certification as builder
    from src.reporting import phase4_final_certification_contract as contract_module

    contract, effective, anchors, pointers, manifest = (
        _phase4_r_cert_adapter_payloads()
    )
    head = effective["p_cert_commit"]
    output_paths = contract.output_paths
    validator_calls = 0
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_cert_contract",
        lambda **_kwargs: contract,
    )
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *_args: head)
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_published_p_cert",
        lambda *_args, **_kwargs: effective["h_cert_commit"],
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_require_closure_phase4_r_cert_namespace_exact",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        contract_module,
        "load_effective_authority",
        lambda *_args, **_kwargs: effective,
    )
    monkeypatch.setattr(
        contract_module,
        "collect_anchor_input_records",
        lambda *_args, **_kwargs: anchors,
    )
    monkeypatch.setattr(
        contract_module,
        "collect_dvc_pointer_records",
        lambda *_args, **_kwargs: pointers,
    )

    def validate(**_kwargs: Any) -> None:
        nonlocal validator_calls
        validator_calls += 1

    monkeypatch.setattr(builder, "validate_final_certification_payloads", validate)
    valid_bytes = contract_module.canonical_json_bytes(manifest)

    def read(path: str, **_kwargs: Any) -> bytes:
        if path == output_paths[-1]:
            return valid_bytes
        return f"payload:{path}\n".encode()

    monkeypatch.setattr(precommit_artifacts, "_read_closure_phase4_cert_file", read)
    digest = precommit_artifacts._closure_phase4_cert_semantic_digest(
        "R-CERT", repo_root=Path(".")
    )
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert validator_calls == 1

    mutator(manifest)
    drifted_bytes = contract_module.canonical_json_bytes(manifest)
    monkeypatch.setattr(
        precommit_artifacts,
        "_read_closure_phase4_cert_file",
        lambda path, **_kwargs: (
            drifted_bytes
            if path == output_paths[-1]
            else f"payload:{path}\n".encode()
        ),
    )
    with pytest.raises(
        precommit_artifacts.ClosurePhase4FinalCertificationPrecommitAdapterError,
        match=match,
    ):
        precommit_artifacts._closure_phase4_cert_semantic_digest(
            "R-CERT", repo_root=Path(".")
        )
    assert validator_calls == 2


def test_closure_phase4_cert_adapter_source_has_no_execution_or_mutation_calls() -> None:
    import inspect

    source = inspect.getsource(
        precommit_artifacts._run_closure_phase4_cert_precommit
    )
    semantic = inspect.getsource(
        precommit_artifacts._closure_phase4_cert_semantic_digest
    )
    forbidden = (
        "build_phase4_final_certification(",
        "check_phase4_final_certification(",
        '"dvc", "add"',
        '"dvc", "push"',
        "pytest",
        "read_parquet",
        "data/targets",
        "evaluation_outcomes",
    )
    for token in forbidden:
        assert token not in source
        assert token not in semantic
    # R-CERT validates the serialized argv of the eight historical pulls, but
    # the precommit runner itself never executes a pull.
    assert '"pull"' not in source
    assert "subprocess.run" not in semantic
    assert "config.local" not in semantic
    assert "builder.validate_final_certification_payloads(" in semantic
