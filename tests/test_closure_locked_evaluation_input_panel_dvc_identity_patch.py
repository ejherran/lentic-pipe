from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.data import prepare_commit_artifacts as precommit
from src.experiments import (
    closure_locked_evaluation_input_panel_dvc_identity_patch as core,
)


BASE = "ddd00ae96fa8cb589f368cb2f7b98d9e2561491d"
H_SCOPE = dict(core.LOCKED_EVALUATION_INPUT_PANEL_DVC_IDENTITY_H_STAGED_SCOPE)
P_SCOPE = dict(core.LOCKED_EVALUATION_INPUT_PANEL_DVC_IDENTITY_P_STAGED_SCOPE)
R_SCOPE = dict(core.LOCKED_EVALUATION_INPUT_PANEL_DVC_IDENTITY_R_STAGED_SCOPE)
PANEL_CONTRACT = core.PANEL_DVC_IDENTITY_CONTRACT


def _short(scope: dict[str, str], *, staged: bool = False) -> str:
    return "".join(
        f"{f'{status} ' if staged else '??' if status == 'A' else ' M'} {path}\n"
        for path, status in reversed(tuple(scope.items()))
    )


def _prelock() -> dict[str, Any]:
    return {
        "repository": {"base_p_mib_commit": BASE},
        "h_patch": {
            "gate": "H-E0-MIC",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
        },
        "base_authority": {
            "gate": "E0-MIB",
            "status": "published_p_mib_authority_validated",
            "p_components": [{}, {}],
        },
        "input_contract": {},
        "r_contract": {},
        "panel_dvc_identity_contract": PANEL_CONTRACT,
        "panel_dvc_identity_verified": True,
        "prelock": {
            "p_output_present_count": 0,
            "r_output_present_count": 0,
            "coordination_present_count": 0,
            "component_count": 6,
            "scientific_execution_run": False,
            "panel_bytes_opened": True,
            "assignment_bytes_opened": True,
            "panel_rows_decoded": False,
            "assignment_rows_decoded": False,
            "target_namespace_opened": False,
            "outcome_paths_opened": False,
            "dvc_commands_run": False,
        },
        "historical_inputs": [{}, {}, {}, {}, {}, {}],
        "historical_inputs_sha256": "a" * 64,
        "coordination_namespace": {
            "current_lock_present_count": 0,
            "coordination_present_count": 0,
            "r_state": "absent",
            "formal_e0_m_output_present_count": 0,
            "outcome_access_log_absent": True,
        },
        "schema_preflight": {
            "gate": "E0-MIC",
            "status": "schema_ready",
            "schema_count": 1,
        },
    }


def _unpublished(stage: str = "untracked") -> dict[str, Any]:
    return {
        "gate": "E0-MIC",
        "status": "locked_unpublished",
        "p_stage_state": stage,
        "p_output_count": 2,
        "physical_input_count": 16,
        "historical_input_count": 6,
        "companion_output_count": 1,
        "coordination_present_count": 0,
        "r_state": "absent",
        "panel_dvc_identity_contract": PANEL_CONTRACT,
        "panel_dvc_identity_verified": True,
        "effective_authority": False,
        "input_bundle_execution_authorized": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }


def _authority(stage: str = "physical_and_light_untracked") -> dict[str, Any]:
    return {
        "gate": "E0-MIC",
        "status": "effective",
        "r_stage_state": stage,
        "r_state": "complete" if stage == "exact6_staged" else "physical_and_light",
        "r_physical_output_count": 4,
        "r_tracked_output_count": 6 if stage == "exact6_staged" else 0,
        "input_bundle_execution_authorized": False,
        "input_bundle_run_consumed": True,
        "effective_authority": True,
        "panel_dvc_identity_contract": PANEL_CONTRACT,
        "panel_dvc_identity_verified": True,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "dvc_commands_authorized": False,
        "dvc_push_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }


def _r_validation(staged: bool = False) -> dict[str, Any]:
    return {
        "gate": "E0-MIC",
        "status": "input_bundle_validated",
        "r_stage_state": "exact6_staged" if staged else "physical_and_light_untracked",
        "physical_output_count": 4,
        "tracked_output_count": 6,
        "pointer_count": 4,
        "summary_count": 1,
        "manifest_count": 1,
        "manifest_written_last": True,
        "input_only": True,
        "panel_dvc_identity_contract": PANEL_CONTRACT,
        "panel_dvc_identity_verified": True,
        "target_paths_opened": False,
        "target_availability_inspected": False,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "writes_performed": False,
    }


def _fake(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "PATCH_GATE": "E0-MIC",
        "BASE_P_MIB_COMMIT": BASE,
        "PATCH_COMPONENT_GIT_MODES": dict(core.PATCH_COMPONENT_GIT_MODES),
        "LOCKED_EVALUATION_INPUT_PANEL_DVC_IDENTITY_H_STAGED_SCOPE": H_SCOPE,
        "LOCKED_EVALUATION_INPUT_PANEL_DVC_IDENTITY_P_STAGED_SCOPE": P_SCOPE,
        "LOCKED_EVALUATION_INPUT_PANEL_DVC_IDENTITY_R_STAGED_SCOPE": R_SCOPE,
        "ClosureLockedEvaluationInputPanelDvcIdentityPatchError": RuntimeError,
        "_source_identity_snapshot": lambda root: ("source",),
        "_physical_snapshot": lambda root: ("physical",),
        "collect_closure_locked_evaluation_input_panel_dvc_identity_patch_prelock_state": lambda **kwargs: _prelock(),
        "validate_locked_evaluation_input_panel_dvc_identity_patch_unpublished_lock_bundle": lambda **kwargs: _unpublished(),
        "require_locked_evaluation_input_panel_dvc_identity_patch_authority": lambda **kwargs: _authority(),
        "validate_locked_evaluation_input_panel_dvc_identity_patch": lambda **kwargs: _r_validation(bool(kwargs["require_staged"])),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _args(gate: str) -> SimpleNamespace:
    targets = (
        [path.removesuffix(".dvc") for path in R_SCOPE if path.endswith(".dvc")]
        if gate == "R-E0-MI"
        else []
    )
    return SimpleNamespace(
        no_push=True,
        yes=False,
        dry_run=False,
        skip_publication_check=False,
        jobs=None,
        dvc_bin=None,
        manifest=precommit.DEFAULT_DVC_MANIFEST,
        report=None,
        allow_unmanaged=True,
        target=targets,
        defer_dvc_target=[],
        register_anfis_ablation_model_family=False,
        verify_manifest_inputs=False,
        max_manifest_hash_bytes=precommit.DEFAULT_MAX_MANIFEST_HASH_BYTES,
    )


def test_mic_topology_is_exact_h6_p2_r6() -> None:
    assert core.BASE_P_MIB_COMMIT == BASE
    assert len(H_SCOPE) == 6 and list(H_SCOPE.values()).count("M") == 1
    assert len(P_SCOPE) == 2 and len(R_SCOPE) == 6
    assert not set(H_SCOPE) & set(P_SCOPE)
    assert not set(H_SCOPE) & set(R_SCOPE)
    assert not set(P_SCOPE) & set(R_SCOPE)
    assert core.PATCH_COMPONENT_GIT_MODES[precommit.__file__.removeprefix(str(Path.cwd()) + "/")] == "100755"


def test_mic_selector_routes_h_before_mib(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_panel_dvc_identity_patch_module", _fake)
    monkeypatch.setattr(precommit, "_require_closure_locked_evaluation_input_panel_dvc_identity_stage_base", lambda *a, **k: None)
    result = precommit.closure_locked_evaluation_input_panel_dvc_identity_pre_stage_scope(_short(H_SCOPE))
    assert result == ("H-E0-MIC", tuple(sorted(H_SCOPE)))
    source = Path(precommit.__file__).read_text(encoding="utf-8")
    main = source[source.index("def main() -> int:") :]
    assert main.index("closure_locked_evaluation_input_panel_dvc_identity_pre_stage_scope(") < main.index("closure_locked_evaluation_input_bundle_pre_stage_scope(")


def test_mic_selector_routes_p_and_r(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_panel_dvc_identity_patch_module", _fake)
    monkeypatch.setattr(precommit, "_require_closure_locked_evaluation_input_panel_dvc_identity_stage_base", lambda *a, **k: None)
    p_result = precommit.closure_locked_evaluation_input_panel_dvc_identity_pre_stage_scope(_short(P_SCOPE))
    assert p_result is not None and p_result[0] == "P-E0-MIC"
    light = {path: value for path, value in R_SCOPE.items() if not path.endswith(".dvc")}
    result = precommit.closure_locked_evaluation_input_panel_dvc_identity_pre_stage_scope(_short(light))
    assert result == ("R-E0-MI", tuple(sorted(R_SCOPE)))


def test_mic_selector_rejects_partial_extra_duplicate_and_malformed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_panel_dvc_identity_patch_module", _fake)
    for status in (
        _short(H_SCOPE).splitlines(keepends=True)[0],
        _short(H_SCOPE) + "?? extra\n",
        _short(H_SCOPE) + _short(H_SCOPE).splitlines(keepends=True)[0],
        _short(H_SCOPE) + "broken\n",
    ):
        with pytest.raises(precommit.ClosureLockedEvaluationInputPanelDvcIdentityAdapterError):
            precommit.closure_locked_evaluation_input_panel_dvc_identity_pre_stage_scope(status)


def test_non_mic_status_remains_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_panel_dvc_identity_patch_module", _fake)
    assert precommit.closure_locked_evaluation_input_panel_dvc_identity_pre_stage_scope("") is None
    assert precommit.closure_locked_evaluation_input_panel_dvc_identity_pre_stage_scope("?? unrelated\n") is None


def test_invocation_is_closed_for_h_p_and_exact_r(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_panel_dvc_identity_patch_module", _fake)
    for gate in ("H-E0-MIC", "P-E0-MIC", "R-E0-MI"):
        args = _args(gate)
        precommit.validate_closure_locked_evaluation_input_panel_dvc_identity_invocation(args, gate=gate, env={"DVC_NO_ANALYTICS": "1"})
        args.skip_publication_check = True
        with pytest.raises(precommit.ClosureLockedEvaluationInputPanelDvcIdentityAdapterError):
            precommit.validate_closure_locked_evaluation_input_panel_dvc_identity_invocation(args, gate=gate, env={"DVC_NO_ANALYTICS": "1"})


def test_scopes_and_bindings_are_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_panel_dvc_identity_patch_module", _fake)
    for gate, scope in (("H-E0-MIC", H_SCOPE), ("P-E0-MIC", P_SCOPE), ("R-E0-MI", R_SCOPE)):
        precommit.validate_closure_locked_evaluation_input_panel_dvc_identity_staged_scope("".join(f"{v}\t{k}\n" for k, v in scope.items()), gate=gate)
        precommit.validate_closure_locked_evaluation_input_panel_dvc_identity_workspace_scope(_short(scope, staged=True), gate=gate)
        with pytest.raises(precommit.ClosureLockedEvaluationInputPanelDvcIdentityAdapterError):
            precommit.validate_closure_locked_evaluation_input_panel_dvc_identity_workspace_scope(_short(scope, staged=True) + "?? extra\n", gate=gate)


def test_prelock_requires_exact_panel_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    prelock = _prelock()
    precommit._validate_closure_locked_evaluation_input_panel_dvc_identity_prelock_result(prelock, patch=_fake())
    prelock["panel_dvc_identity_verified"] = False
    with pytest.raises(precommit.ClosureLockedEvaluationInputPanelDvcIdentityAdapterError):
        precommit._validate_closure_locked_evaluation_input_panel_dvc_identity_prelock_result(prelock, patch=_fake())

    source_snapshots = iter((("source-before",), ("source-after",)))
    racing = _fake(_source_identity_snapshot=lambda root: next(source_snapshots))
    with pytest.raises(
        precommit.ClosureLockedEvaluationInputPanelDvcIdentityAdapterError,
        match="source identity drifted",
    ):
        precommit._require_closure_locked_evaluation_input_panel_dvc_identity_prelock(
            patch=racing,
            repo_root=Path("."),
        )
    monkeypatch.setattr(
        core,
        "_source_identity_snapshot",
        lambda root: ({"path": "source", "sha256": "9" * 64},),
    )
    with pytest.raises(
        core.ClosureLockedEvaluationInputPanelDvcIdentityPatchError,
        match="source identities changed",
    ):
        core._require_source_identity_snapshot(
            ({"path": "source", "sha256": "8" * 64},),
            repo_root=Path("."),
            context="at a sealed boundary",
        )


def test_unpublished_authority_and_r_results_are_closed() -> None:
    precommit._require_closure_locked_evaluation_input_panel_dvc_identity_unpublished_validation(patch=_fake(), repo_root=Path("."), expected_stage_state="untracked")
    precommit._require_closure_locked_evaluation_input_panel_dvc_identity_authority(patch=_fake(), repo_root=Path("."), expected_stage_state="physical_and_light_untracked")
    precommit._require_closure_locked_evaluation_input_panel_dvc_identity_r_validation(patch=_fake(), repo_root=Path("."), require_staged=False)
    with pytest.raises(precommit.ClosureLockedEvaluationInputPanelDvcIdentityAdapterError):
        precommit._require_closure_locked_evaluation_input_panel_dvc_identity_authority(patch=_fake(require_locked_evaluation_input_panel_dvc_identity_patch_authority=lambda **k: {**_authority(), "panel_dvc_identity_verified": False}), repo_root=Path("."), expected_stage_state="physical_and_light_untracked")


def test_panel_real_0444_nlink2_cache_identity_is_accepted() -> None:
    result = core._validate_panel_dvc_identity(repo_root=Path(".").resolve())
    assert result == PANEL_CONTRACT
    metadata = (Path(core.mib.PANEL_PATH)).stat()
    cache = Path(core.PANEL_CACHE_PATH).stat()
    assert (metadata.st_mode & 0o777, metadata.st_nlink) == (0o444, 2)
    assert (metadata.st_dev, metadata.st_ino) == (cache.st_dev, cache.st_ino)


def test_panel_portable_0644_nlink1_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"x"
    metadata = SimpleNamespace(st_mode=0o100644, st_nlink=1)
    monkeypatch.setattr(core.mcal, "_read_scientific_payload_bytes_and_metadata", lambda *a, **k: (payload, metadata))
    with pytest.raises(core.ClosureLockedEvaluationInputPanelDvcIdentityPatchError):
        core._read_panel_dvc_bytes_and_metadata(repo_root=Path("."))


def test_panel_link3_wrong_cache_and_pointer_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = core.mcal._read_scientific_payload_bytes_and_metadata
    for message in ("third link", "wrong cache", "pointer drift"):
        monkeypatch.setattr(core.mcal, "_read_scientific_payload_bytes_and_metadata", lambda *a, message=message, **k: (_ for _ in ()).throw(core.mcal.FinalCalibrationError(message)))
        with pytest.raises(core.ClosureLockedEvaluationInputPanelDvcIdentityPatchError):
            core._read_panel_dvc_bytes_and_metadata(repo_root=Path("."))
    monkeypatch.setattr(core.mcal, "_read_scientific_payload_bytes_and_metadata", original)


def test_panel_symlink_is_rejected(tmp_path: Path) -> None:
    panel = tmp_path / core.mib.PANEL_PATH
    panel.parent.mkdir(parents=True)
    panel.symlink_to("missing")
    with pytest.raises(core.ClosureLockedEvaluationInputPanelDvcIdentityPatchError):
        core._read_panel_dvc_bytes_and_metadata(repo_root=tmp_path)


def test_patched_mib_reader_restores_monkeypatches() -> None:
    original_load = core.mib._load_input_projections
    original_recapture = core.mib._recapture_scientific_source_snapshots
    with core._patched_mib_panel_reader(repo_root=Path(".")):
        assert core.mib._load_input_projections is not original_load
        assert core.mib._recapture_scientific_source_snapshots is not original_recapture
    assert core.mib._load_input_projections is original_load
    assert core.mib._recapture_scientific_source_snapshots is original_recapture


def test_publisher_loader_and_r_wrapper_call_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = Path(core.__file__).read_text(encoding="utf-8")
    assert source.count("_source_identity_snapshot(") >= 6
    assert source.count("_require_source_identity_snapshot(") >= 5
    assert "with _patched_mib_panel_reader(repo_root=repo_root):" in source
    assert "mib.validate_locked_evaluation_input_bundle(" in source
    assert "publish_closure_locked_evaluation_input_panel_dvc_identity_patch_lock_bundle" in source
    assert core.INPUT_BUNDLE_COMMAND[-2:] == (core.CORE_PATH, "--execute-input-bundle")
    post_return = source.split(
        "result = mib.execute_locked_evaluation_input_bundle", 1
    )[1].split("return {", 1)[0]
    assert "_require_" not in post_return
    assert "load_effective" not in post_return
    assert "_snapshot" not in post_return

    mic_snapshot: list[dict[str, Any]] = [{"path": "p-mic", "sha256": "1" * 64}]
    mib_snapshot: list[dict[str, Any]] = [{"path": "p-mib", "sha256": "2" * 64}]
    authority = {
        "authority_binding_sha256": "a" * 64,
        "base_mib_authority_binding_sha256": "b" * 64,
        "input_contract": {"input_only": True},
        "panel_dvc_identity_contract": PANEL_CONTRACT,
    }
    lock = {
        "repository": {"h_patch_head": "h" * 40},
        "input_contract": authority["input_contract"],
    }
    monkeypatch.setattr(core, "_p_pair_snapshot", lambda root: tuple(mic_snapshot))
    monkeypatch.setattr(
        core.mib, "_p_pair_snapshot", lambda root: tuple(mib_snapshot)
    )
    monkeypatch.setattr(
        core,
        "_parse_canonical_json",
        lambda *args, **kwargs: (lock, b"{}", SimpleNamespace()),
    )
    monkeypatch.setattr(
        core,
        "_validate_p_publication_state",
        lambda **kwargs: {"r_state": "absent"},
    )
    monkeypatch.setattr(
        core,
        "_require_namespace",
        lambda **kwargs: {"coordination_present_count": 0},
    )
    monkeypatch.setattr(
        core, "_validate_panel_dvc_identity", lambda **kwargs: PANEL_CONTRACT
    )
    monkeypatch.setattr(
        core,
        "_source_identity_snapshot",
        lambda root: ({"path": "source", "sha256": "5" * 64},),
    )
    monkeypatch.setattr(
        core, "_require_source_identity_snapshot", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        core,
        "_physical_snapshot",
        lambda root: ({"path": "physical", "sha256": "6" * 64},),
    )
    monkeypatch.setattr(
        core, "_require_physical_snapshot", lambda *args, **kwargs: None
    )
    dynamic_authorities = iter(
        (
            {
                **authority,
                "input_bundle_run_consumed": False,
                "r_outputs_sha256": None,
            },
            {
                **authority,
                "input_bundle_run_consumed": True,
                "r_outputs_sha256": "c" * 64,
            },
        )
    )
    monkeypatch.setattr(
        core,
        "require_locked_evaluation_input_panel_dvc_identity_patch_authority",
        lambda **kwargs: next(dynamic_authorities),
    )

    guard_path = Path("tmp/mic-test/owned.guard")
    guard = core.mib.mt._acquire_publication_guard(
        guard_path, b"owned\n", repo_root=tmp_path
    )
    try:
        with core._patched_mib_execution_authority(authority, repo_root=tmp_path):
            checkpoint = core.mib._require_execution_authority_checkpoint
            before = core.mib.require_locked_evaluation_input_bundle_authority(
                verify_remote=True,
                repo_root=tmp_path,
            )
            after = core.mib.require_locked_evaluation_input_bundle_authority(
                verify_remote=True,
                repo_root=tmp_path,
            )
            assert before["input_bundle_run_consumed"] is False
            assert before["r_outputs_sha256"] is None
            assert after["input_bundle_run_consumed"] is True
            assert after["r_outputs_sha256"] == "c" * 64
            assert checkpoint(
                authority,
                tuple(mib_snapshot),
                owned_run_guard=guard,
                repo_root=tmp_path,
            ) == {"r_state": "absent"}

            mic_snapshot[0] = {"path": "p-mic", "sha256": "3" * 64}
            with pytest.raises(
                core.ClosureLockedEvaluationInputPanelDvcIdentityPatchError,
                match="P identity changed under the run guard",
            ):
                checkpoint(
                    authority,
                    tuple(mib_snapshot),
                    owned_run_guard=guard,
                    repo_root=tmp_path,
                )
            mic_snapshot[0] = {"path": "p-mic", "sha256": "1" * 64}

            mib_snapshot[0] = {"path": "p-mib", "sha256": "4" * 64}
            with pytest.raises(
                core.ClosureLockedEvaluationInputPanelDvcIdentityPatchError,
                match="P identity changed under the run guard",
            ):
                checkpoint(
                    authority,
                    ({"path": "p-mib", "sha256": "2" * 64},),
                    owned_run_guard=guard,
                    repo_root=tmp_path,
                )
            mib_snapshot[0] = {"path": "p-mib", "sha256": "2" * 64}
    finally:
        core.mib.mt._release_publication_guard(guard)

    foreign = core.mib.mt._acquire_publication_guard(
        guard_path, b"owned\n", repo_root=tmp_path
    )
    foreign_path = tmp_path / guard_path
    foreign_path.unlink()
    foreign_path.write_bytes(b"foreign\n")
    try:
        with core._patched_mib_execution_authority(authority, repo_root=tmp_path):
            with pytest.raises(core.mcal.FinalCalibrationError, match="guard identity"):
                core.mib._require_execution_authority_checkpoint(
                    authority,
                    tuple(mib_snapshot),
                    owned_run_guard=foreign,
                    repo_root=tmp_path,
                )
    finally:
        core.mib.mt._release_publication_guard(foreign, tolerate_foreign=True)
        foreign_path.unlink()


def test_transactions_use_mic_not_mib(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    fake = _fake(
        collect_closure_locked_evaluation_input_panel_dvc_identity_patch_prelock_state=lambda **k: calls.append("h") or _prelock(),
        validate_locked_evaluation_input_panel_dvc_identity_patch_unpublished_lock_bundle=lambda **k: calls.append("p") or _unpublished("staged"),
        require_locked_evaluation_input_panel_dvc_identity_patch_authority=lambda **k: calls.append("r") or _authority("exact6_staged"),
        validate_locked_evaluation_input_panel_dvc_identity_patch=lambda **k: calls.append("bundle") or _r_validation(True),
    )
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_panel_dvc_identity_patch_module", lambda: fake)
    monkeypatch.setattr(precommit, "validate_closure_locked_evaluation_input_panel_dvc_identity_staged_scope", lambda *a, **k: None)
    monkeypatch.setattr(precommit, "validate_closure_locked_evaluation_input_panel_dvc_identity_workspace_scope", lambda *a, **k: None)
    monkeypatch.setattr(precommit, "validate_closure_locked_evaluation_input_panel_dvc_identity_staged_bindings", lambda *a, **k: ())
    monkeypatch.setattr(precommit, "snapshot_closure_locked_evaluation_input_physical_outputs", lambda **k: ())
    monkeypatch.setattr(precommit, "_git_output", lambda root, *args: BASE + "\n" if args == ("rev-parse", "HEAD") else "scope\n")
    for gate in ("H-E0-MIC", "P-E0-MIC", "R-E0-MI"):
        precommit.revalidate_closure_locked_evaluation_input_panel_dvc_identity_transaction(gate=gate, staged_status="scope\n", expected_physical_snapshot=() if gate == "R-E0-MI" else None)
    assert calls == ["h", "h", "p", "r", "bundle"]
