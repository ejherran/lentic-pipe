from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import inspect
import json
import os
from pathlib import Path
from typing import Any

import pytest

from src.data import prepare_commit_artifacts as precommit_artifacts
from src.experiments import (
    closure_anfis_ablation_model_publication_adoption_patch as patch,
)
from src.experiments import (
    lock_closure_anfis_ablation_model_publication_adoption_patch as locker,
)


ROOT = Path(__file__).resolve().parents[1]
H_MW_COMMIT = "68107147c1a67c30ecfa64c862dd39531e574a9a"
LIGHT_PUBLICATION_COMMIT = "5b24549f2d4791f6500e661f9ee404c0dc7a0866"
EXPECTED_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_model_publication_adoption_patch_lock.schema.json",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_ADOPTION_PATCH_1.md",
    "src/experiments/closure_anfis_ablation_model_publication_adoption_patch.py",
    "src/experiments/lock_closure_anfis_ablation_model_publication_adoption_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
}
EXPECTED_MODIFICATIONS = {
    "src/data/prepare_commit_artifacts.py",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py",
    "src/experiments/train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
    "tests/test_train_closure_anfis_ablation.py",
}
EXPECTED_P_PATHS = {
    "reports/closure_v1/00_protocol/anfis_ablation_model_publication_adoption_patch_lock.json",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_model_publication_adoption_patch_lock_manifest.json"
    ),
}
EXPECTED_COMPONENT_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
}
EXPECTED_LIGHT_GIT_OIDS = {
    "reports/closure_v1/02_models/A0/seed_1729_manifest.json": (
        "9d554bc0b560b2a4e817f2eb8d07ef48424dd51a"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_preprocessor.json": (
        "b59088160da3c8d36efb984260f021959d52dddb"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_report.md": (
        "740ef989b27bcbb44c22b81d4d90f9722d8f55b3"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_selection_metrics.csv": (
        "90ee68a227fd02d5554b6a256f8bde6927ec36a6"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_training_curve.csv": (
        "6b0a676116a34a41d36956696ba945c9632abecd"
    ),
}


def _record(path: Path, *, role: str) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.as_posix(),
        "role": role,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _install_synthetic_adopted_a0(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    records: list[dict[str, Any]] = []
    for index in range(8):
        relative = Path(f"sealed/a0/final_{index}.bin")
        path = repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"sealed-a0-{index}".encode("ascii")
        path.write_bytes(payload)
        path.chmod(0o644)
        records.append(
            {
                "path": relative.as_posix(),
                "role": f"synthetic_final_{index}",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    monkeypatch.setattr(patch, "HISTORICAL_A0_FINAL_RECORDS", tuple(records))
    return repo_root / str(records[0]["path"])


def _patch_synthetic_publisher(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    target = _install_synthetic_adopted_a0(repo_root, monkeypatch)
    prelock = {
        "repository": {"head": "h"},
        "h_patch": {"component_count": 11},
        "base_mw_authority": {"status": "published"},
    }
    payload = {"gate": "E0-MX", **prelock}
    companion = {"status": "completed", "completion_marker_written_last": True}
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_model_publication_adoption_patch_schema",
        lambda **kwargs: {"status": "supported_subset_passed"},
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_model_publication_adoption_patch_prelock_state",
        lambda **kwargs: prelock,
    )
    monkeypatch.setattr(
        patch,
        "_run_anfis_ablation_model_publication_adoption_patch_verification",
        lambda **kwargs: {"status": "passed"},
    )
    monkeypatch.setattr(
        patch,
        "build_anfis_ablation_model_publication_adoption_patch_lock_payload",
        lambda *args, **kwargs: payload,
    )
    monkeypatch.setattr(
        patch,
        "validate_anfis_ablation_model_publication_adoption_patch_lock_payload",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda *args, **kwargs: companion,
    )
    monkeypatch.setattr(
        patch,
        "_revalidate_publication_state_under_guard",
        lambda *args, **kwargs: None,
    )
    return target


def test_patch_identity_scope_paths_and_companion_counts_are_exact() -> None:
    assert patch.PATCH_GATE == "E0-MX"
    assert patch.H_MW_HEAD == H_MW_COMMIT
    assert patch.ADOPTED_LIGHT_COMMIT == LIGHT_PUBLICATION_COMMIT
    assert patch.ADOPTED_LIGHT_PARENT == H_MW_COMMIT
    assert patch.BASE_COMMIT == LIGHT_PUBLICATION_COMMIT
    assert set(patch.PATCH_PATHS) == EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    assert len(patch.PATCH_PATHS) == 11
    assert patch.PATCH_COMPONENT_GIT_MODES == EXPECTED_COMPONENT_GIT_MODES
    assert patch.EXPECTED_COMPANION_INPUT_COUNT == 87
    assert patch.EXPECTED_HISTORICAL_INPUT_COUNT == 11
    assert {
        patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
    } == EXPECTED_P_PATHS

    expected_seal_keys = {
        "historical_a0_bundle_preserved",
        "historical_a0_bundle_rewrite_forbidden",
        "historical_mu_authority_preserved",
        "published_h_mv_preserved",
        "published_h_mw_preserved",
        "adopted_light_commit_preserved",
        "adopted_light_outputs_rewrite_forbidden",
        "p_mw_superseded_unmaterialized",
        "blocked_p_mv_rejected_as_authority",
        "blocked_p_mv_not_required",
        "model_manifest_dialect",
        "completion_marker_written_last",
        "compact_sorted_manifest_dialect_rejected",
        "next_slot",
        "target_access_end",
        "calibration_2021_closed",
        "holdout_and_post_2021_closed",
        "ten_slots_individual_only",
        "dvc_absent",
        "outcomes_absent",
        "historical_inputs_compared_to_current_paths",
    }
    assert set(patch.LOCK_SEALS) == expected_seal_keys
    source_tree = ast.parse(inspect.getsource(patch))
    seal_assignments = [
        node
        for node in source_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "LOCK_SEALS"
            for target in node.targets
        )
    ]
    assert len(seal_assignments) == 1
    seal_literal = seal_assignments[0].value
    assert isinstance(seal_literal, ast.Dict)
    assert all(key is not None for key in seal_literal.keys)
    literal_keys = [
        ast.literal_eval(key) for key in seal_literal.keys if key is not None
    ]
    assert len(literal_keys) == len(set(literal_keys))
    assert set(literal_keys) == expected_seal_keys


def test_new_lock_is_one_report_and_only_companion_is_a_manifest() -> None:
    lock = patch.DEFAULT_PATCH_LOCK_PATH
    companion = patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    assert "manifest" not in lock.name
    assert companion.name.endswith("_lock_manifest.json")
    assert precommit_artifacts.is_experiment_manifest_path(lock) is False
    assert precommit_artifacts.is_report_artifact_path(lock) is True
    assert precommit_artifacts.is_experiment_manifest_path(companion) is True
    assert precommit_artifacts.is_report_artifact_path(companion) is False


def test_generic_precommit_dialect_is_exactly_one_one_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    lock = patch.DEFAULT_PATCH_LOCK_PATH
    companion = patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    script = Path("src/synthetic_e0_mx_locker.py")
    source = Path("configs/synthetic_e0_mx_input.json")
    for path in (lock, companion, script, source):
        path.parent.mkdir(parents=True, exist_ok=True)
    script.write_bytes(b"# synthetic E0-MX locker\n")
    source.write_bytes(b"{}\n")
    lock.write_bytes(b'{"gate":"E0-MX","status":"locked_unpublished"}\n')
    companion.write_text(
        json.dumps(
            {
                "manifest_version": "synthetic_e0_mx_lock_manifest_v1",
                "status": "completed",
                "gate": "E0-MX",
                "script": _record(script, role="synthetic_locker"),
                "inputs": [_record(source, role="synthetic_input")],
                "outputs": [_record(lock, role="synthetic_lock")],
                "completion_marker_written_last": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    findings = precommit_artifacts.validate_experiment_manifests(
        staged_paths={lock, companion},
        artifacts=[],
        max_hash_bytes=1_000_000,
        verify_manifest_inputs=True,
    )
    assert not [finding for finding in findings if finding.level != "ok"]
    summaries = [
        finding.message
        for finding in findings
        if finding.check == "manifest" and finding.path == "-"
    ]
    assert summaries == [
        "Checked 1 experiment manifest(s), 1 output record(s), and 1 staged "
        "report artifact(s). 0 covered output(s) are also protected by DVC pointers."
    ]


def test_deferred_precommit_scopes_and_current_boundary_are_exact() -> None:
    expected_h = {
        path: ("A" if path in EXPECTED_ADDITIONS else "M")
        for path in EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    }
    expected_p = {path: "A" for path in EXPECTED_P_PATHS}
    assert precommit_artifacts.DEFERRED_DVC_H_MX_STAGED_SCOPE == expected_h
    assert precommit_artifacts.DEFERRED_DVC_P_MX_STAGED_SCOPE == expected_p
    assert precommit_artifacts.DEFERRED_DVC_ACTIVE_STAGING_GATES == frozenset(
        {"H-E0-MX", "P-E0-MX"}
    )
    for current_gate in ("H-E0-MX", "P-E0-MX"):
        assert (
            precommit_artifacts.require_active_deferred_dvc_staging_gate(
                current_gate
            )
            == current_gate
        )
    for historical_gate in (
        "H-E0-MV",
        "P-E0-MV",
        "H-E0-MW",
        "P-E0-MW",
    ):
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="closed to exact H-E0-MX/P-E0-MX",
        ):
            precommit_artifacts.require_active_deferred_dvc_staging_gate(
                historical_gate
            )

    h_staged = "".join(
        f"{status}\t{path}\n" for path, status in sorted(expected_h.items())
    )
    p_staged = "".join(
        f"{status}\t{path}\n" for path, status in sorted(expected_p.items())
    )
    h_pre_stage = "".join(
        f"{'??' if status == 'A' else ' M'} {path}\n"
        for path, status in sorted(expected_h.items())
    )
    p_pre_stage = "".join(f"?? {path}\n" for path in sorted(expected_p))
    assert precommit_artifacts.validate_deferred_dvc_staged_scope(h_staged) == (
        "H-E0-MX"
    )
    assert precommit_artifacts.validate_deferred_dvc_staged_scope(p_staged) == (
        "P-E0-MX"
    )
    assert precommit_artifacts.validate_deferred_dvc_pre_stage_scope(
        h_pre_stage
    ) == "H-E0-MX"
    assert precommit_artifacts.validate_deferred_dvc_pre_stage_scope(
        p_pre_stage
    ) == "P-E0-MX"


def test_tracked_light_publication_is_git_bound_and_heavy_finals_are_not() -> None:
    assert (
        precommit_artifacts.DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT
        == LIGHT_PUBLICATION_COMMIT
    )
    assert (
        precommit_artifacts.DEFERRED_DVC_A0_LIGHT_PUBLICATION_PARENT
        == H_MW_COMMIT
    )
    assert precommit_artifacts.DEFERRED_DVC_A0_LIGHT_GIT_OIDS == (
        EXPECTED_LIGHT_GIT_OIDS
    )
    assert precommit_artifacts.DEFERRED_DVC_A0_LIGHT_EXCLUDE_PATTERNS == tuple(
        f"/{path}" for path in sorted(EXPECTED_LIGHT_GIT_OIDS)
    )
    precommit_artifacts._validate_deferred_a0_git_tracking(ROOT)
    snapshot = precommit_artifacts.snapshot_deferred_dvc_models_bundle(
        repo_root=ROOT
    )
    assert len(snapshot) == 8
    assert all(record.nlink == 1 and record.ctime_ns > 0 for record in snapshot)
    assert replace(snapshot[0], nlink=2) != snapshot[0]
    assert replace(snapshot[0], ctime_ns=snapshot[0].ctime_ns + 1) != snapshot[0]


def test_tracked_light_binding_fails_closed_on_head_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_git_output = precommit_artifacts._git_output
    drift_path = sorted(EXPECTED_LIGHT_GIT_OIDS)[0]

    def drift(repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", f"HEAD:{drift_path}"):
            return "0" * 40 + "\n"
        return real_git_output(repo_root, *args)

    monkeypatch.setattr(precommit_artifacts, "_git_output", drift)
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="lightweight Git binding drifted",
    ):
        precommit_artifacts._validate_deferred_a0_git_tracking(ROOT)


def test_schema_closes_h_and_companion_counts() -> None:
    schema = json.loads(patch.DEFAULT_PATCH_LOCK_SCHEMA.read_text(encoding="utf-8"))
    properties = schema["properties"]
    assert properties["gate"]["const"] == "E0-MX"
    definitions = schema["$defs"]
    assert definitions["hPatch"]["properties"]["component_count"]["const"] == 11
    contract = definitions["companionContract"]["properties"]
    assert contract["physical_input_count"]["const"] == 87
    assert contract["historical_input_count"]["const"] == 11
    assert contract["output_count"]["const"] == 1


def test_check_only_is_a_non_writing_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = {"status": "schema_preflight_passed"}
    repository = {"head": "f" * 40}
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_model_publication_adoption_patch_schema",
        lambda: schema,
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_model_publication_adoption_patch_prelock_state",
        lambda **kwargs: {
            "repository": repository,
            "h_patch": {"component_count": 11},
            "companion_contract": {
                "physical_input_count": 87,
                "historical_input_count": 11,
            },
            "adopted_a0_bundle": {
                "model_id": "A0",
                "base_seed": 1729,
                "output_count": 8,
            },
        },
    )
    result = locker.check_only()
    assert result == {
        "status": "ready_to_lock",
        "gate": "E0-MX",
        "schema_preflight": schema,
        "repository": repository,
        "component_count": 11,
        "physical_input_count": 87,
        "historical_input_count": 11,
        "tracked_light_commit": LIGHT_PUBLICATION_COMMIT,
        "tracked_light_count": 5,
        "adopted_model_id": "A0",
        "adopted_base_seed": 1729,
        "adopted_output_count": 8,
        "writes_performed": False,
        "verification_commands_run": False,
        "trainer_entrypoint_run": False,
        "model_fit_or_optimization_run": False,
        "auditor_entrypoint_run": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "calibration_targets_read": False,
        "future_outcomes_accessed": False,
    }


def test_execute_lock_delegates_to_the_closed_public_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def execute() -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal calls
        calls += 1
        return {"gate": "E0-MX"}, {"status": "completed"}

    monkeypatch.setattr(
        patch,
        "execute_and_publish_anfis_ablation_model_publication_adoption_patch_lock_bundle",
        execute,
    )
    result = locker.execute_lock()
    assert calls == 1
    assert result["status"] == "locked_unpublished"
    assert result["gate"] == "E0-MX"
    assert result["lock"] == {"gate": "E0-MX"}
    assert result["companion"] == {"status": "completed"}
    for key in (
        "trainer_entrypoint_run",
        "model_fit_or_optimization_run",
        "auditor_entrypoint_run",
        "dvc_commands_run",
        "scientific_network_commands_run",
        "calibration_targets_read",
        "future_outcomes_accessed",
    ):
        assert result[key] is False


def test_effective_cli_forwards_the_exact_target_and_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[dict[str, Any]] = []

    def load(**kwargs: Any) -> dict[str, Any]:
        observed.append(kwargs)
        return {
            "gate": "E0-MX",
            "authorized_model_id": kwargs["model_id"],
            "authorized_base_seed": kwargs["base_seed"],
            "audit_current_unpublished": kwargs["audit_current_unpublished"],
        }

    monkeypatch.setattr(
        patch,
        "load_effective_anfis_ablation_model_publication_adoption_patch_authority",
        load,
    )
    result = locker.check_effective(
        model_id="A0", base_seed=1729, audit_current_unpublished=True
    )
    assert observed == [
        {
            "model_id": "A0",
            "base_seed": 1729,
            "audit_current_unpublished": True,
            "verify_remote": True,
        }
    ]
    assert result["audit_current_unpublished"] is True


def test_locker_cli_modes_are_closed_and_target_aware() -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    assert locker.parse_args(["--execute-lock"]).execute_lock is True
    effective = locker.parse_args(
        ["--check-effective", "--model-id", "A1", "--base-seed", "1729"]
    )
    assert (effective.model_id, effective.base_seed) == ("A1", 1729)
    for invalid in (
        ["--check-effective"],
        ["--check-only", "--model-id", "A0", "--base-seed", "1729"],
        ["--execute-lock", "--audit-current-unpublished"],
    ):
        with pytest.raises(SystemExit):
            locker.parse_args(invalid)


def test_locker_main_translates_only_the_closed_patch_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        locker,
        "check_only",
        lambda: (_ for _ in ()).throw(
            patch.AnfisAblationModelPublicationAdoptionPatchError("closed")
        ),
    )
    assert locker.main(["--check-only"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "closed\n"


def test_public_publishers_accept_no_payload_and_close_a0_toctou(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for function in (
        patch.execute_and_publish_anfis_ablation_model_publication_adoption_patch_lock_bundle,
        patch.publish_anfis_ablation_model_publication_adoption_patch_lock_bundle,
    ):
        assert set(inspect.signature(function).parameters) == {"repo_root"}

    real_publish = patch.mt._publish_bytes_no_clobber
    with monkeypatch.context() as transaction_patch:
        repo_root = tmp_path / "inode-replacement"
        repo_root.mkdir()
        target = _patch_synthetic_publisher(repo_root, transaction_patch)
        original_bytes = target.read_bytes()

        def publish_then_replace(
            path: Path, payload: bytes, *, repo_root: Path
        ) -> Any:
            output = real_publish(path, payload, repo_root=repo_root)
            if path == patch.DEFAULT_PATCH_LOCK_PATH:
                replacement = target.with_name(f"{target.name}.replacement")
                replacement.write_bytes(original_bytes)
                replacement.chmod(0o644)
                os.replace(replacement, target)
            return output

        transaction_patch.setattr(
            patch.mt, "_publish_bytes_no_clobber", publish_then_replace
        )
        with pytest.raises(
            patch.AnfisAblationModelPublicationAdoptionPatchError,
            match="immediately after lock publication",
        ):
            patch.execute_and_publish_anfis_ablation_model_publication_adoption_patch_lock_bundle(
                repo_root=repo_root
            )
        assert target.read_bytes() == original_bytes
        for path in (
            patch.DEFAULT_PATCH_LOCK_PATH,
            patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            patch.LOCKER_GUARD_PATH,
            patch.mt._temporary_path(patch.DEFAULT_PATCH_LOCK_PATH),
            patch.mt._temporary_path(patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        ):
            assert not (repo_root / path).exists()

    with monkeypatch.context() as verification_patch:
        repo_root = tmp_path / "metadata-restoration"
        repo_root.mkdir()
        target = _install_synthetic_adopted_a0(repo_root, verification_patch)
        baseline = patch._adopted_a0_physical_snapshot(repo_root)
        assert len(baseline) == 8
        assert all(len(record) == 9 for record in baseline)
        before = target.stat()
        before_bytes = target.read_bytes()
        schema_preflight = {"status": "supported_subset_passed"}
        verification_patch.setattr(
            patch,
            "preflight_anfis_ablation_model_publication_adoption_patch_schema",
            lambda **kwargs: schema_preflight,
        )

        def touch_restore_then_return(
            *args: Any, **kwargs: Any
        ) -> tuple[dict[str, Any], str, str]:
            del args, kwargs
            target.chmod(0o600)
            os.utime(
                target,
                ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000),
            )
            target.chmod(0o644)
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            restored = target.stat()
            assert target.read_bytes() == before_bytes
            assert restored.st_mode == before.st_mode
            assert restored.st_mtime_ns == before.st_mtime_ns
            assert restored.st_ctime_ns != before.st_ctime_ns
            return ({}, "All checks passed!\n", "")

        verification_patch.setattr(patch, "_run_command", touch_restore_then_return)
        with pytest.raises(
            patch.AnfisAblationModelPublicationAdoptionPatchError,
            match="after full type check",
        ):
            patch._run_anfis_ablation_model_publication_adoption_patch_verification(
                adopted_snapshot=baseline,
                expected_schema_preflight=schema_preflight,
                repo_root=repo_root,
            )
        assert target.read_bytes() == before_bytes
        assert not (repo_root / patch.DEFAULT_PATCH_LOCK_PATH).exists()
        assert not (repo_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
        assert not (repo_root / patch.LOCKER_GUARD_PATH).exists()


def test_locker_source_cannot_train_audit_fit_or_run_dvc() -> None:
    source = inspect.getsource(locker)
    for forbidden in (
        "train_closure_anfis_ablation.py",
        "audit_closure_anfis_ablation_model_bundle.py",
        "dvc add",
        "dvc push",
        "execute_one_shot",
        "read_parquet",
    ):
        assert forbidden not in source


def test_document_records_exact_adoption_and_deferred_contract() -> None:
    document = (
        ROOT
        / "docs/closure_v1/"
        "E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_ADOPTION_PATCH_1.md"
    ).read_text(encoding="utf-8")
    for token in (
        H_MW_COMMIT,
        LIGHT_PUBLICATION_COMMIT,
        "`6M+5A`",
        "`87` unique current physical `inputs`",
        "`11` Git-bound `historical_inputs`",
        "--defer-dvc-target models",
        "exactly one manifest, one covered output, and one staged report",
        "A0 replay or replacement remains forbidden",
    ):
        assert token in document
    assert patch.DEFAULT_PATCH_LOCK_PATH.as_posix() in document
    assert patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix() in document
