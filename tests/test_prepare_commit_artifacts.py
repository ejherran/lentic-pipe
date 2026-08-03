from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

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


def test_closure_protocol_lock_is_a_strict_experiment_manifest() -> None:
    path = Path("reports/closure_v1/00_protocol/protocol_lock.json")

    assert is_experiment_manifest_path(path)
    assert not is_report_artifact_path(path)
    assert not is_experiment_manifest_path(Path("reports/other/protocol_lock.json"))


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
