from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from src.data import prepare_commit_artifacts as precommit_artifacts
from src.experiments import closure_anfis_ablation_model_manifest_patch as mv
from src.experiments import closure_anfis_ablation_model_publication_patch as patch
from src.experiments import lock_closure_anfis_ablation_model_publication_patch as locker


ROOT = Path(__file__).resolve().parents[1]
H_MV_COMMIT = "455f593fc276dc0b74565e34aea4a09342badb30"
EXPECTED_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_model_publication_patch_lock.schema.json",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_PATCH_1.md",
    "src/experiments/closure_anfis_ablation_model_publication_patch.py",
    "src/experiments/lock_closure_anfis_ablation_model_publication_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
}
EXPECTED_MODIFICATIONS = {
    "src/data/prepare_commit_artifacts.py",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py",
    "src/experiments/train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
    "tests/test_train_closure_anfis_ablation.py",
}
EXPECTED_P_PATHS = {
    "reports/closure_v1/00_protocol/anfis_ablation_model_publication_patch_lock.json",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_model_publication_patch_lock_manifest.json"
    ),
}
EXPECTED_COMPONENT_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
}
BLOCKED_P_MV_RECORDS = {
    "lock": (
        28_403,
        "0704ad83b0cf9c4f2de17c948e32eec889c435164268f815b9a99b05c6fd2b07",
    ),
    "companion": (
        17_033,
        "25fbd11373d420db3127718c6808f57c2e96d05630371956035d69d0ac3d2966",
    ),
    "report": (
        7_451,
        "3146b15569758cd4048e2f649147a0ff90c25b1d9b9d67e905f5fe51b2b4ab77",
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


def test_patch_identity_scope_paths_and_companion_counts_are_exact() -> None:
    assert patch.PATCH_GATE == "E0-MW"
    assert patch.BASE_COMMIT == H_MV_COMMIT
    assert set(patch.PATCH_PATHS) == EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    assert len(patch.PATCH_PATHS) == 10
    assert patch.PATCH_COMPONENT_GIT_MODES == EXPECTED_COMPONENT_GIT_MODES
    assert patch.EXPECTED_COMPANION_INPUT_COUNT == 77
    assert patch.EXPECTED_HISTORICAL_INPUT_COUNT == 5
    assert {
        patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
    } == EXPECTED_P_PATHS


def test_new_lock_is_a_report_and_only_companion_is_a_generic_manifest() -> None:
    lock = patch.DEFAULT_PATCH_LOCK_PATH
    companion = patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    assert "manifest" not in lock.name
    assert companion.name.endswith("_lock_manifest.json")
    assert precommit_artifacts.is_experiment_manifest_path(lock) is False
    assert precommit_artifacts.is_report_artifact_path(lock) is True
    assert precommit_artifacts.is_experiment_manifest_path(companion) is True
    assert precommit_artifacts.is_report_artifact_path(companion) is False

    blocked_lock = Path(
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_model_manifest_patch_lock.json"
    )
    assert precommit_artifacts.is_experiment_manifest_path(blocked_lock) is True
    assert precommit_artifacts.is_report_artifact_path(blocked_lock) is False


def test_generic_precommit_dialect_covers_exactly_one_manifest_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    lock = patch.DEFAULT_PATCH_LOCK_PATH
    companion = patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    script = Path("src/synthetic_e0_mw_locker.py")
    source = Path("configs/synthetic_e0_mw_input.json")
    for path in (lock, companion, script, source):
        path.parent.mkdir(parents=True, exist_ok=True)
    script.write_bytes(b"# synthetic E0-MW locker\n")
    source.write_bytes(b"{}\n")
    lock.write_bytes(b'{"gate":"E0-MW","status":"locked_unpublished"}\n')
    manifest = {
        "manifest_version": "synthetic_e0_mw_lock_manifest_v1",
        "status": "completed",
        "gate": "E0-MW",
        "script": _record(script, role="synthetic_locker"),
        "inputs": [_record(source, role="synthetic_input")],
        "outputs": [_record(lock, role="synthetic_lock")],
        "completion_marker_written_last": True,
    }
    companion.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
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


def test_deferred_precommit_scopes_are_exact_h_mw_and_p_mw() -> None:
    expected_h = {
        path: ("A" if path in EXPECTED_ADDITIONS else "M")
        for path in EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    }
    expected_p = {path: "A" for path in EXPECTED_P_PATHS}
    assert precommit_artifacts.DEFERRED_DVC_H_MW_STAGED_SCOPE == expected_h
    assert precommit_artifacts.DEFERRED_DVC_P_MW_STAGED_SCOPE == expected_p
    assert precommit_artifacts.DEFERRED_DVC_ACTIVE_STAGING_GATES == frozenset(
        {"H-E0-MW", "P-E0-MW"}
    )
    assert (
        precommit_artifacts.require_active_deferred_dvc_staging_gate("H-E0-MW")
        == "H-E0-MW"
    )
    assert (
        precommit_artifacts.require_active_deferred_dvc_staging_gate("P-E0-MW")
        == "P-E0-MW"
    )
    for historical_gate in ("H-E0-MV", "P-E0-MV"):
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="closed to exact H-E0-MW/P-E0-MW",
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
    assert precommit_artifacts.validate_deferred_dvc_staged_scope(h_staged) == (
        "H-E0-MW"
    )
    assert precommit_artifacts.validate_deferred_dvc_staged_scope(p_staged) == (
        "P-E0-MW"
    )

    h_pre_stage = "".join(
        f"{'??' if status == 'A' else ' M'} {path}\n"
        for path, status in sorted(expected_h.items())
    )
    p_pre_stage = "".join(f"?? {path}\n" for path in sorted(expected_p))
    assert precommit_artifacts.validate_deferred_dvc_pre_stage_scope(
        h_pre_stage
    ) == "H-E0-MW"
    assert precommit_artifacts.validate_deferred_dvc_pre_stage_scope(
        p_pre_stage
    ) == "P-E0-MW"


def test_adopted_a0_remains_the_exact_historical_e0_mu_bundle() -> None:
    assert patch.HISTORICAL_A0_FINAL_RECORDS == mv.HISTORICAL_A0_FINAL_RECORDS
    assert len(patch.HISTORICAL_A0_FINAL_RECORDS) == 8
    assert patch.HISTORICAL_A0_AUTHORITY == mv.HISTORICAL_A0_AUTHORITY
    assert patch.HISTORICAL_A0_AUTHORITY["gate"] == "E0-MU"
    assert not {
        str(record["path"]) for record in patch.HISTORICAL_A0_FINAL_RECORDS
    }.intersection(patch.PATCH_PATHS)


def test_schema_closes_h_and_companion_counts() -> None:
    schema = json.loads(patch.DEFAULT_PATCH_LOCK_SCHEMA.read_text(encoding="utf-8"))
    properties = schema["properties"]
    assert properties["gate"]["const"] == "E0-MW"
    definitions = schema["$defs"]
    assert definitions["hPatch"]["properties"]["component_count"]["const"] == 10
    contract = definitions["companionContract"]["properties"]
    assert contract["physical_input_count"]["const"] == 77
    assert contract["historical_input_count"]["const"] == 5
    assert contract["output_count"]["const"] == 1


def test_check_only_is_a_non_writing_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = {"status": "schema_preflight_passed"}
    repository = {"head": "f" * 40}
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_model_publication_patch_schema",
        lambda: schema,
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_model_publication_patch_prelock_state",
        lambda **kwargs: {
            "repository": repository,
            "h_patch": {"component_count": 10},
            "companion_contract": {
                "physical_input_count": 77,
                "historical_input_count": 5,
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
        "gate": "E0-MW",
        "schema_preflight": schema,
        "repository": repository,
        "component_count": 10,
        "physical_input_count": 77,
        "historical_input_count": 5,
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
        return {"gate": "E0-MW"}, {"status": "completed"}

    monkeypatch.setattr(
        patch,
        "execute_and_publish_anfis_ablation_model_publication_patch_lock_bundle",
        execute,
    )
    result = locker.execute_lock()
    assert calls == 1
    assert result["status"] == "locked_unpublished"
    assert result["gate"] == "E0-MW"
    assert result["lock"] == {"gate": "E0-MW"}
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
            "gate": "E0-MW",
            "authorized_model_id": kwargs["model_id"],
            "authorized_base_seed": kwargs["base_seed"],
            "audit_current_unpublished": kwargs["audit_current_unpublished"],
        }

    monkeypatch.setattr(
        patch, "load_effective_anfis_ablation_model_publication_authority", load
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
            patch.AnfisAblationModelPublicationPatchError("closed")
        ),
    )
    assert locker.main(["--check-only"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "closed\n"


def test_public_publishers_accept_no_payload_or_verification_evidence() -> None:
    for function in (
        patch.execute_and_publish_anfis_ablation_model_publication_patch_lock_bundle,
        patch.publish_anfis_ablation_model_publication_patch_lock_bundle,
    ):
        parameters = inspect.signature(function).parameters
        assert set(parameters) == {"repo_root"}


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


def test_document_records_blocked_evidence_and_closed_replacement() -> None:
    document = (
        ROOT / "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_PATCH_1.md"
    ).read_text(encoding="utf-8")
    for byte_count, digest in BLOCKED_P_MV_RECORDS.values():
        assert str(byte_count).replace(",", "") in document
        assert digest in document
    for token in (
        "E0-DLTVM",
        "not contain `manifest`",
        "published, retried, copied back",
        "`5M+5A`",
        "`77` unique current physical `inputs`",
        "`5` Git-bound `historical_inputs`",
        "--defer-dvc-target models",
        "must report `1/1/1`",
        "A0 replay or replacement remains forbidden",
    ):
        assert token in document
    assert patch.DEFAULT_PATCH_LOCK_PATH.as_posix() in document
    assert patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix() in document
