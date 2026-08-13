from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.data import prepare_commit_artifacts as precommit


BASE = "81c1fc485902d484264fccc53cf88888c359930d"
H_SCOPE = {
    "configs/closure_v1/locked_evaluation_input_bundle_lock.schema.json": "A",
    "docs/closure_v1/E0_M_LOCKED_EVALUATION_INPUT_BUNDLE.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/closure_locked_evaluation_input_bundle.py": "A",
    "src/experiments/lock_closure_locked_evaluation_input_bundle.py": "A",
    "tests/test_closure_locked_evaluation_input_bundle.py": "A",
}
P_SCOPE = {
    "configs/closure_v1/locked_evaluation_input_bundle_lock.json": "A",
    "configs/closure_v1/locked_evaluation_input_bundle_lock_manifest.json": "A",
}
R_SCOPE = {
    "data/closure_v1/locked_evaluation/input_history.parquet.dvc": "A",
    "data/closure_v1/locked_evaluation/intent_origins.parquet.dvc": "A",
    "data/closure_v1/locked_evaluation/origin_features.parquet.dvc": "A",
    "data/closure_v1/locked_evaluation/sequence_features.parquet.dvc": "A",
    "reports/closure_v1/01_surface/locked_evaluation_input_summary.json": "A",
    "reports/closure_v1/01_surface/locked_evaluation_input_manifest.json": "A",
}
H_GIT_MODES = {
    path: "100755" if path == "src/data/prepare_commit_artifacts.py" else "100644"
    for path in H_SCOPE
}


class CoreError(RuntimeError):
    pass


def _unpublished(stage_state: str = "untracked") -> dict[str, Any]:
    return {
        "gate": "E0-MIB",
        "status": "locked_unpublished",
        "p_stage_state": stage_state,
        "p_output_count": 2,
        "physical_input_count": 16,
        "historical_input_count": 6,
        "companion_output_count": 1,
        "coordination_present_count": 0,
        "r_state": "absent",
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


def _authority(stage_state: str = "physical_and_light_untracked") -> dict[str, Any]:
    complete = stage_state == "exact6_staged"
    return {
        "gate": "E0-MIB",
        "status": "effective",
        "r_stage_state": stage_state,
        "r_state": "complete" if complete else "physical_and_light",
        "r_physical_output_count": 4,
        "r_tracked_output_count": 6 if complete else 0,
        "input_bundle_execution_authorized": False,
        "input_bundle_run_consumed": True,
        "effective_authority": True,
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


def _prelock() -> dict[str, Any]:
    return {
        "repository": {"base_p_mcalm_commit": BASE},
        "h_patch": {
            "gate": "H-E0-MIB",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
        },
        "base_authority": {
            "gate": "E0-MCALM",
            "status": "published_p_mcalm_authority_validated",
            "p_components": [{}, {}],
            "scientific_inputs_rehashed": False,
            "outcome_paths_opened": False,
        },
        "input_contract": {
            "panel_projection_count": 41,
            "physical_feature_count": 38,
            "derived_calendar_count": 4,
            "locked_evaluation_origin_start": "2022-01",
            "target_months_materialized": False,
            "target_availability_inspected": False,
            "target_namespace_opened": False,
            "outcome_access_log_opened": False,
            "source_records": [{}, {}, {}, {}],
        },
        "r_contract": {
            "gate": "R-E0-MI",
            "physical_output_count": 4,
            "pointer_output_count": 4,
            "light_output_count": 2,
            "tracked_output_count": 6,
            "manifest_written_last": True,
        },
        "prelock": {
            "p_output_present_count": 0,
            "r_output_present_count": 0,
            "coordination_present_count": 0,
            "component_count": 6,
            "scientific_execution_run": False,
            "panel_opened": False,
            "assignment_opened": False,
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
            "gate": "E0-MIB",
            "status": "schema_ready",
            "schema_count": 1,
        },
    }


def _r_validation(*, staged: bool = False) -> dict[str, Any]:
    return {
        "gate": "E0-MIB",
        "status": "input_bundle_validated",
        "r_stage_state": "exact6_staged" if staged else "physical_and_light_untracked",
        "physical_output_count": 4,
        "tracked_output_count": 6,
        "pointer_count": 4,
        "summary_count": 1,
        "manifest_count": 1,
        "manifest_written_last": True,
        "input_only": True,
        "target_paths_opened": False,
        "target_availability_inspected": False,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "writes_performed": False,
    }


def _fake_patch(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "PATCH_GATE": "E0-MIB",
        "BASE_P_MCALM_COMMIT": BASE,
        "LOCKED_EVALUATION_INPUT_H_STAGED_SCOPE": H_SCOPE,
        "LOCKED_EVALUATION_INPUT_P_STAGED_SCOPE": P_SCOPE,
        "LOCKED_EVALUATION_INPUT_R_STAGED_SCOPE": R_SCOPE,
        "PATCH_COMPONENT_GIT_MODES": H_GIT_MODES,
        "ClosureLockedEvaluationInputBundleError": CoreError,
        "_physical_snapshot": lambda repo_root: ("physical",),
        "collect_closure_locked_evaluation_input_bundle_prelock_state": (
            lambda **kwargs: _prelock()
        ),
        "validate_locked_evaluation_input_bundle_unpublished_lock_bundle": (
            lambda **kwargs: _unpublished()
        ),
        "require_locked_evaluation_input_bundle_authority": (
            lambda **kwargs: _authority()
        ),
        "validate_locked_evaluation_input_bundle": (
            lambda **kwargs: _r_validation(staged=bool(kwargs["require_staged"]))
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _short(scope: dict[str, str], *, staged: bool = False) -> str:
    rows: list[str] = []
    for path, status in reversed(tuple(scope.items())):
        code = f"{status} " if staged else "??" if status == "A" else " M"
        rows.append(f"{code} {path}\n")
    return "".join(rows)


def _staged(scope: dict[str, str]) -> str:
    return "".join(
        f"{status}\t{path}\n" for path, status in reversed(tuple(scope.items()))
    )


def _args(*, gate: str) -> SimpleNamespace:
    targets: list[str] = []
    if gate == "R-E0-MI":
        targets = [path.removesuffix(".dvc") for path in R_SCOPE if path.endswith(".dvc")]
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


def test_mib_topology_is_h6_p2_r6() -> None:
    from src.experiments import closure_locked_evaluation_input_bundle as core

    assert len(H_SCOPE) == 6 and list(H_SCOPE.values()).count("M") == 1
    assert len(P_SCOPE) == 2 and set(P_SCOPE.values()) == {"A"}
    assert len(R_SCOPE) == 6 and set(R_SCOPE.values()) == {"A"}
    assert sum(path.endswith(".parquet.dvc") for path in R_SCOPE) == 4
    assert not set(H_SCOPE) & set(P_SCOPE)
    assert not set(H_SCOPE) & set(R_SCOPE)
    assert not set(P_SCOPE) & set(R_SCOPE)
    assert core.PATCH_GATE == "E0-MIB"
    assert core.BASE_P_MCALM_COMMIT == BASE
    assert core.LOCKED_EVALUATION_INPUT_H_STAGED_SCOPE == H_SCOPE
    assert core.LOCKED_EVALUATION_INPUT_P_STAGED_SCOPE == P_SCOPE
    assert core.LOCKED_EVALUATION_INPUT_R_STAGED_SCOPE == R_SCOPE
    assert core.PATCH_COMPONENT_GIT_MODES == H_GIT_MODES
    assert len(core.PANEL_PROJECTION) == 41
    assert len(core.PHYSICAL_FEATURE_COLUMNS) == 38
    assert len(set(core.PHYSICAL_FEATURE_COLUMNS)) == 38
    assert core.DERIVED_CALENDAR_COLUMNS == (
        "season_sin_annual",
        "season_cos_annual",
        "season_sin_semiannual",
        "season_cos_semiannual",
    )
    assert core.HISTORY_LENGTH == 12 and core.HORIZONS == (1, 2, 3)
    assert core.LOCKED_EVALUATION_START == "2022-01"
    assert tuple(path.as_posix() for path in core.R_PUBLICATION_ORDER) == (
        *(path.removesuffix(".dvc") for path in R_SCOPE if path.endswith(".dvc")),
        "reports/closure_v1/01_surface/locked_evaluation_input_summary.json",
        "reports/closure_v1/01_surface/locked_evaluation_input_manifest.json",
    )
    import_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "from src.experiments import closure_locked_evaluation_input_bundle; "
                "forbidden={'pandas','pyarrow','torch','sklearn'} & set(sys.modules); "
                "sys.exit(','.join(sorted(forbidden)) if forbidden else 0)"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert import_probe.returncode == 0, import_probe.stderr

    assignments = [
        {
            "source_id": "wqp",
            "site_id": f"site-{index:03d}",
            "holdout_group_id": f"group-{index:03d}",
            "assignment_role": "internal_holdout",
        }
        for index in range(88)
    ]
    panel = [
        {
            "source_id": "wqp",
            "site_id": assignment["site_id"],
            "year_month": "2022-01",
            **{column: 1.0 for column in core.PHYSICAL_FEATURE_COLUMNS},
        }
        for assignment in assignments
    ]
    built = core.build_locked_evaluation_input_bundle_records(assignments, panel)
    assert built["summary"] == {
        "holdout_location_count": 88,
        "origin_count": 88,
        "eligible_origin_count": 0,
        "ineligible_origin_count": 88,
        "history_row_count": 88 * 12,
        "origin_start": "2022-01",
        "origin_end": "2022-01",
    }
    assert len(built["input_history"]) == 88 * 12
    assert len(built["intent_origins"]) == 88
    assert all(
        len(row["sequence_row_present"]) == 12
        for row in built["sequence_features"]
    )
    with pytest.raises(
        core.ClosureLockedEvaluationInputBundleError,
        match="assignment projection dialect drifted",
    ):
        core.build_locked_evaluation_input_bundle_records(
            [{**assignments[0], "target_chla": 1.0}, *assignments[1:]],
            panel,
        )


def test_h_pre_stage_routes_exact_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    fake = _fake_patch(
        collect_closure_locked_evaluation_input_bundle_prelock_state=(
            lambda **kwargs: calls.append(kwargs)
            or _prelock()
        )
    )
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_bundle_module", lambda: fake)
    monkeypatch.setattr(precommit, "_git_output", lambda *args: BASE + "\n")
    assert precommit.closure_locked_evaluation_input_bundle_pre_stage_scope(
        _short(H_SCOPE)
    ) == ("H-E0-MIB", tuple(sorted(H_SCOPE)))
    assert calls == [
        {"repo_root": Path("."), "verify_remote": True},
        {"repo_root": Path("."), "verify_remote": True},
    ]
    for drifted in ({}, {**_prelock(), "unexpected": True}):
        with pytest.raises(
            precommit.ClosureLockedEvaluationInputBundleAdapterError
        ):
            precommit._validate_closure_locked_evaluation_input_prelock_result(
                drifted,
                patch=fake,
            )
    drifted = _prelock()
    drifted["prelock"] = {**drifted["prelock"], "panel_opened": True}
    with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
        precommit._validate_closure_locked_evaluation_input_prelock_result(
            drifted,
            patch=fake,
        )

    from src.experiments import closure_locked_evaluation_input_bundle as core
    from src.experiments import lock_closure_locked_evaluation_input_bundle as locker

    def forbidden_science(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("H/check-only must not open input science")

    direct = _prelock()
    direct["h_patch"] = {
        **direct["h_patch"],
        "components": [],
        "components_sha256": "b" * 64,
    }
    direct["base_authority"] = {
        **direct["base_authority"],
        "p_components": [{}, {}],
    }
    direct["input_contract"] = {
        **direct["input_contract"],
        "source_records": [{}, {}, {}, {}],
        "source_records_sha256": "c" * 64,
    }
    monkeypatch.setattr(core, "_load_input_projections", forbidden_science)
    monkeypatch.setattr(core, "_read_parquet_contract", forbidden_science)
    monkeypatch.setattr(core, "execute_locked_evaluation_input_bundle", forbidden_science)
    monkeypatch.setattr(
        core,
        "_h_patch_authority",
        lambda **kwargs: (direct["repository"], direct["h_patch"]),
    )
    monkeypatch.setattr(
        core,
        "preflight_closure_locked_evaluation_input_bundle_schema",
        lambda **kwargs: direct["schema_preflight"],
    )
    monkeypatch.setattr(core, "_base_p_mcalm_authority", lambda **kwargs: direct["base_authority"])
    monkeypatch.setattr(core, "_historical_h_mcalm_records", lambda **kwargs: direct["historical_inputs"])
    monkeypatch.setattr(core, "_require_namespace", lambda **kwargs: direct["coordination_namespace"])
    monkeypatch.setattr(core, "_input_source_records", lambda **kwargs: direct["input_contract"]["source_records"])
    collected = core.collect_closure_locked_evaluation_input_bundle_prelock_state(
        verify_remote=True,
        repo_root=Path("."),
    )
    assert collected["prelock"]["panel_opened"] is False
    assert collected["prelock"]["assignment_opened"] is False
    assert collected["prelock"]["outcome_paths_opened"] is False
    monkeypatch.setattr(core, "_physical_snapshot", lambda *args, **kwargs: tuple(range(16)))
    check_only = locker.check_only()
    assert check_only["status"] == "ready_to_lock"
    assert check_only["physical_input_count"] == 16
    assert check_only["writes_performed"] is False
    assert check_only["verification_commands_run"] is False
    assert check_only["future_outcomes_accessed"] is False


def test_p_pre_stage_routes_and_validates_unpublished(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    fake = _fake_patch(
        validate_locked_evaluation_input_bundle_unpublished_lock_bundle=(
            lambda **kwargs: calls.append(kwargs) or _unpublished()
        )
    )
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_bundle_module", lambda: fake)

    def git_output(repo_root: Path, *args: str) -> str:
        del repo_root
        if args == ("rev-parse", "HEAD"):
            return "h" * 40 + "\n"
        if args == ("rev-parse", "HEAD^"):
            return BASE + "\n"
        return _staged(H_SCOPE)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    assert precommit.closure_locked_evaluation_input_bundle_pre_stage_scope(
        _short(P_SCOPE)
    ) == ("P-E0-MIB", tuple(sorted(P_SCOPE)))
    assert calls == [{"repo_root": Path("."), "verify_remote": True}]


def test_r_pre_dvc_routes_two_light_outputs_and_requires_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    fake = _fake_patch(
        require_locked_evaluation_input_bundle_authority=(
            lambda **kwargs: calls.append(("authority", kwargs)) or _authority()
        ),
        validate_locked_evaluation_input_bundle=(
            lambda **kwargs: calls.append(("bundle", kwargs)) or _r_validation()
        ),
    )
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_bundle_module", lambda: fake)
    monkeypatch.setattr(precommit, "_git_output", lambda *args: "p" * 40 + "\n")
    light = {path: value for path, value in R_SCOPE.items() if not path.endswith(".dvc")}
    assert precommit.closure_locked_evaluation_input_bundle_pre_stage_scope(
        _short(light)
    ) == ("R-E0-MI", tuple(sorted(R_SCOPE)))
    assert calls == [
        ("authority", {"repo_root": Path("."), "verify_remote": True}),
        (
            "bundle",
            {
                "repo_root": Path("."),
                "require_staged": False,
                "verify_remote": True,
            },
        ),
    ]


def test_pre_stage_rejects_partial_extra_duplicate_and_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_patch()
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_bundle_module", lambda: fake)
    monkeypatch.setattr(precommit, "_git_output", lambda *args: BASE + "\n")
    exact = _short(H_SCOPE)
    for candidate in (
        "".join(exact.splitlines(keepends=True)[:-1]),
        exact + "?? extra.txt\n",
        exact + exact.splitlines(keepends=True)[0],
        exact + "malformed\n",
        exact.replace("?? ", " M", 1),
    ):
        with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
            precommit.closure_locked_evaluation_input_bundle_pre_stage_scope(candidate)
    drifted = _fake_patch(
        LOCKED_EVALUATION_INPUT_R_STAGED_SCOPE={**R_SCOPE, "extra": "A"}
    )
    monkeypatch.setattr(
        precommit,
        "_closure_locked_evaluation_input_bundle_module",
        lambda: drifted,
    )
    with pytest.raises(
        precommit.ClosureLockedEvaluationInputBundleAdapterError,
        match="H6/P2/R6 scope contract drifted",
    ):
        precommit.closure_locked_evaluation_input_bundle_pre_stage_scope(
            _short(H_SCOPE)
        )


def test_non_mib_status_remains_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        precommit, "_closure_locked_evaluation_input_bundle_module", _fake_patch
    )
    assert precommit.closure_locked_evaluation_input_bundle_pre_stage_scope("") is None
    assert precommit.closure_locked_evaluation_input_bundle_pre_stage_scope(
        "?? unrelated.txt\n"
    ) is None


def test_stage_base_rejects_wrong_h_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_patch()
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_bundle_module", lambda: fake)
    monkeypatch.setattr(precommit, "_git_output", lambda *args: "0" * 40 + "\n")
    with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
        precommit.closure_locked_evaluation_input_bundle_pre_stage_scope(_short(H_SCOPE))


def test_unpublished_validation_is_fail_closed() -> None:
    fake = _fake_patch(
        validate_locked_evaluation_input_bundle_unpublished_lock_bundle=(
            lambda **kwargs: {**_unpublished(), "status": "wrong"}
        )
    )
    with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
        precommit._require_closure_locked_evaluation_input_unpublished_validation(
            patch=fake, repo_root=Path("."), expected_stage_state="untracked"
        )


def test_effective_authority_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_patch(
        require_locked_evaluation_input_bundle_authority=(
            lambda **kwargs: {**_authority(), "status": "wrong"}
        )
    )
    with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
        precommit._require_closure_locked_evaluation_input_authority(
            patch=fake,
            repo_root=Path("."),
            expected_stage_state="physical_and_light_untracked",
        )
    for field, value in (
        ("r_stage_state", "wrong"),
        ("r_physical_output_count", 3),
        ("input_bundle_execution_authorized", True),
        ("outcome_access_authorized", True),
        ("dvc_commands_authorized", True),
    ):
        fake = _fake_patch(
            require_locked_evaluation_input_bundle_authority=(
                lambda field=field, value=value, **kwargs: {
                    **_authority(),
                    field: value,
                }
            )
        )
        with pytest.raises(
            precommit.ClosureLockedEvaluationInputBundleAdapterError
        ):
            precommit._require_closure_locked_evaluation_input_authority(
                patch=fake,
                repo_root=Path("."),
                expected_stage_state="physical_and_light_untracked",
            )

    from src.experiments import closure_locked_evaluation_input_bundle as core

    lock = {"input_contract": {"source_records": []}}
    companion = {"status": "completed"}
    metadata = SimpleNamespace(identity="stable")

    def parse(path: Path, **kwargs: Any) -> tuple[dict[str, Any], bytes, Any]:
        del kwargs
        value = lock if path == core.DEFAULT_PATCH_LOCK_PATH else companion
        return value, core._canonical_json_bytes(value), metadata

    publication = {
        "h_patch_head": "1" * 40,
        "p_patch_head": "2" * 40,
        "r_patch_head": None,
        "remote_head": "2" * 40,
        "r_state": "absent",
        "r_stage_state": "absent",
    }
    monkeypatch.setattr(core, "_parse_canonical_json", parse)
    monkeypatch.setattr(core, "_validate_published_lock_payload", lambda *a, **k: None)
    monkeypatch.setattr(
        core,
        "_file_record",
        lambda path, *, role, repo_root: {
            "path": path.as_posix(),
            "role": role,
            "sha256": "3" * 64,
        },
    )
    monkeypatch.setattr(core, "_expected_companion", lambda *a, **k: companion)
    monkeypatch.setattr(
        core, "_validate_p_publication_state", lambda *a, **k: publication
    )
    monkeypatch.setattr(core, "_physical_snapshot", lambda *a, **k: ())
    monkeypatch.setattr(core, "_require_physical_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(
        core.mcalm.mcall.mcalk.mcalj,
        "_metadata_identity",
        lambda value: value.identity,
    )
    namespace = {"coordination_present_count": 0, "r_state": "absent"}
    monkeypatch.setattr(core, "_require_namespace", lambda **kwargs: namespace)

    effective = core.load_effective_closure_locked_evaluation_input_bundle_authority(
        repo_root=Path("."), verify_remote=True
    )
    assert effective["status"] == "effective"
    assert effective["input_bundle_execution_authorized"] is True
    assert effective["input_bundle_run_consumed"] is False
    assert effective["r_outputs_published"] is False
    assert effective["r_physical_output_count"] == 0
    assert effective["r_tracked_output_count"] == 0
    for field in (
        "evaluation_authorized",
        "e0_m_authorized",
        "e0_u_authorized",
        "outcome_access_authorized",
        "holdout_outcome_access_authorized",
        "post_2021_outcome_access_authorized",
        "writes_performed",
    ):
        assert effective[field] is False

    namespace_calls = 0

    def namespace_race(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        nonlocal namespace_calls
        namespace_calls += 1
        if namespace_calls == 2:
            raise core.ClosureLockedEvaluationInputBundleError(
                "E0-MIB temporary appeared during effective loading"
            )
        return namespace

    monkeypatch.setattr(core, "_require_namespace", namespace_race)
    with pytest.raises(
        core.ClosureLockedEvaluationInputBundleError,
        match="temporary appeared",
    ):
        core.load_effective_closure_locked_evaluation_input_bundle_authority(
            repo_root=Path("."), verify_remote=True
        )

    binding_sha256 = effective["authority_binding_sha256"]
    publication.update(
        {
            "r_patch_head": "4" * 40,
            "r_state": "complete",
            "r_stage_state": "published",
        }
    )
    terminal_namespace = {
        "coordination_present_count": 0,
        "r_state": "complete",
    }
    source_snapshots = [{"path": "assignment"}, {"path": "panel"}]
    public_records = [{"path": "rebuilt-terminal"}]
    summary = {"origin_count": 88}
    manifest = {"authority_binding_sha256": binding_sha256}
    materialization = {
        "source_snapshots": source_snapshots,
        "public_records": public_records,
        "summary": summary,
        "manifest": manifest,
    }
    terminal_semantics = {
        "physical_outputs": public_records,
        "summary": summary,
        "manifest": manifest,
        "r_outputs_sha256": "5" * 64,
    }
    pointer_requirements: list[bool] = []

    def terminal_semantic(*, pointers_required: bool, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        pointer_requirements.append(pointers_required)
        return terminal_semantics

    monkeypatch.setattr(core, "_require_namespace", lambda **kwargs: terminal_namespace)
    monkeypatch.setattr(
        core,
        "_recapture_scientific_source_snapshots",
        lambda **kwargs: source_snapshots,
    )
    monkeypatch.setattr(
        core,
        "_validate_scientific_source_bindings",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        core,
        "_build_expected_r_materialization",
        lambda *args, **kwargs: materialization,
    )
    monkeypatch.setattr(core, "_validate_r_bundle_semantics", terminal_semantic)
    terminal = core.load_effective_closure_locked_evaluation_input_bundle_authority(
        repo_root=Path("."), verify_remote=True
    )
    assert pointer_requirements == [True, True]
    assert terminal["input_bundle_execution_authorized"] is False
    assert terminal["input_bundle_run_consumed"] is True
    assert terminal["r_outputs_published"] is True
    assert terminal["r_physical_output_count"] == 4
    assert terminal["r_tracked_output_count"] == 6
    assert terminal["r_outputs_sha256"] == "5" * 64

    terminal_drift = iter(
        (
            terminal_semantics,
            {**terminal_semantics, "r_outputs_sha256": "6" * 64},
        )
    )
    monkeypatch.setattr(
        core,
        "_validate_r_bundle_semantics",
        lambda **kwargs: next(terminal_drift),
    )
    with pytest.raises(
        core.ClosureLockedEvaluationInputBundleError,
        match="semantics changed",
    ):
        core.load_effective_closure_locked_evaluation_input_bundle_authority(
            repo_root=Path("."), verify_remote=True
        )

    def terminal_pointer_drift(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["pointers_required"] is True
        raise core.ClosureLockedEvaluationInputBundleError(
            "E0-MIB DVC pointer binding drifted"
        )

    monkeypatch.setattr(
        core, "_validate_r_bundle_semantics", terminal_pointer_drift
    )
    with pytest.raises(
        core.ClosureLockedEvaluationInputBundleError,
        match="pointer binding drifted",
    ):
        core.load_effective_closure_locked_evaluation_input_bundle_authority(
            repo_root=Path("."), verify_remote=True
        )


def test_r_dvc_targets_are_exact_four(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        precommit, "_closure_locked_evaluation_input_bundle_module", _fake_patch
    )
    targets = precommit.closure_locked_evaluation_input_dvc_targets()
    assert len(targets) == 4
    assert {f"{path.as_posix()}.dvc" for path in targets} == {
        path for path in R_SCOPE if path.endswith(".dvc")
    }
    assert precommit.closure_locked_evaluation_input_dvc_add_command(
        precommit.DEFAULT_DVC_BIN.as_posix(), targets[0]
    ) == [
        precommit.DEFAULT_DVC_BIN.as_posix(),
        "add",
        "--no-relink",
        targets[0].as_posix(),
    ]
    with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
        precommit.closure_locked_evaluation_input_dvc_add_command("dvc", targets[0])
    inodes = {path.as_posix(): index for index, path in enumerate(targets, start=1)}

    def identity(path: Path, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        return SimpleNamespace(
            path=path.as_posix(),
            device=1,
            inode=inodes[path.as_posix()],
            mode=0o644,
            nlink=1,
            size=10,
            sha256=f"{inodes[path.as_posix()]:064x}",
            mtime_ns=1,
            ctime_ns=1,
        )

    monkeypatch.setattr(
        precommit,
        "_registration_file_identity",
        identity,
    )
    before = precommit.snapshot_closure_locked_evaluation_input_physical_outputs()
    assert len(before) == 4
    inodes[targets[0].as_posix()] += 100
    assert precommit.snapshot_closure_locked_evaluation_input_physical_outputs() != before

    from src.experiments import closure_locked_evaluation_input_bundle as core

    published_order: list[Path] = []
    rollback_count = 0
    released = False
    guarded_events: list[str] = []

    def authority(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        return {
            "input_bundle_execution_authorized": not released,
            "input_bundle_run_consumed": released,
            "authority_binding_sha256": "a" * 64,
        }

    def namespace(
        *,
        current_lock_state: str,
        r_state: str,
        owned_run_guard: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        del current_lock_state, kwargs
        if released and r_state == "physical_and_light" and owned_run_guard is None:
            raise core.ClosureLockedEvaluationInputBundleError(
                "E0-MIB temporary appeared after run guard release"
            )
        return {"coordination_present_count": 0}

    def release(*args: Any, **kwargs: Any) -> None:
        nonlocal released
        del args, kwargs
        assert guarded_events.count("semantic") == 1
        assert guarded_events.count("owned_bytes") == 6
        assert guarded_events.count("owned_identity") == 1
        assert guarded_events.count("authority_checkpoint") == 2
        released = True

    def publish(path: Path, payload: bytes, *, repo_root: Path) -> SimpleNamespace:
        target = repo_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        published_order.append(path)
        return SimpleNamespace(path=path)

    def rollback(outputs: list[SimpleNamespace]) -> None:
        nonlocal rollback_count
        rollback_count = len(outputs)
        for output in outputs:
            (tmp_path / output.path).unlink(missing_ok=True)
        return None

    def authority_checkpoint(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args
        assert kwargs.get("owned_run_guard") is not None
        assert released is False
        guarded_events.append("authority_checkpoint")
        return {"r_state": "absent"}

    monkeypatch.setattr(core, "require_locked_evaluation_input_bundle_authority", authority)
    monkeypatch.setattr(core, "_require_namespace", namespace)
    monkeypatch.setattr(core, "_physical_snapshot", lambda *args, **kwargs: ())
    monkeypatch.setattr(core, "_require_physical_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(core, "_p_pair_snapshot", lambda *args, **kwargs: ())
    monkeypatch.setattr(
        core,
        "_require_execution_authority_checkpoint",
        authority_checkpoint,
    )
    monkeypatch.setattr(core.mt, "_acquire_publication_guard", lambda *args, **kwargs: object())
    monkeypatch.setattr(core.mt, "_release_publication_guard", release)
    payloads = (b"p0", b"p1", b"p2", b"p3")
    public_records = [{"path": path.as_posix()} for path in core.R_PHYSICAL_OUTPUT_PATHS]
    summary = {"status": "completed_unpublished"}
    manifest = {
        "status": "completed_unpublished",
        "authority_binding_sha256": "a" * 64,
    }
    materialization = {
        "source_snapshots": [{}, {}],
        "payloads": payloads,
        "public_records": public_records,
        "summary": summary,
        "summary_bytes": b"summary",
        "manifest": manifest,
        "manifest_bytes": b"manifest",
    }
    semantic = {
        "physical_outputs": public_records,
        "summary": summary,
        "manifest": manifest,
        "r_outputs_sha256": "b" * 64,
    }

    def validate_semantic(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        assert released is False
        guarded_events.append("semantic")
        return semantic

    def guarded_event(name: str) -> None:
        assert released is False
        guarded_events.append(name)

    monkeypatch.setattr(
        core,
        "_build_expected_r_materialization",
        lambda *args, **kwargs: materialization,
    )
    monkeypatch.setattr(
        core,
        "_validate_r_bundle_semantics",
        validate_semantic,
    )
    monkeypatch.setattr(core, "_recapture_scientific_source_snapshots", lambda **kwargs: [{}, {}])
    monkeypatch.setattr(core, "_public_source_snapshot", lambda record: {})
    monkeypatch.setattr(core, "_locked_input_contract", lambda **kwargs: {})
    monkeypatch.setattr(core.mcalm.mcall.mcalk, "_publish_bytes_no_clobber", publish)
    monkeypatch.setattr(core, "_current_r_state", lambda **kwargs: "physical_and_light")
    monkeypatch.setattr(core, "_rollback_owned_outputs", rollback)
    monkeypatch.setattr(
        core.mcalm.mcall.mcalk.mcalj,
        "_validate_owned_output_bytes",
        lambda *args, **kwargs: guarded_event("owned_bytes"),
    )
    monkeypatch.setattr(
        core.mcalm.mcall.mcalk.mcalj.mcali,
        "_require_owned_identity_set",
        lambda *args, **kwargs: guarded_event("owned_identity"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [str(tmp_path / core.CORE_PATH), "--execute-input-bundle"],
    )
    with pytest.raises(
        core.ClosureLockedEvaluationInputBundleError,
        match="temporary appeared after run guard release",
    ):
        core.execute_locked_evaluation_input_bundle(repo_root=tmp_path)
    assert published_order == list(core.R_PUBLICATION_ORDER)
    assert published_order[-1] == core.R_MANIFEST_PATH
    assert rollback_count == 6
    assert all(not (tmp_path / path).exists() for path in core.R_PUBLICATION_ORDER)


def test_h_and_p_invocations_forbid_every_dvc_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        precommit, "_closure_locked_evaluation_input_bundle_module", _fake_patch
    )
    for gate in ("H-E0-MIB", "P-E0-MIB"):
        valid = _args(gate=gate)
        precommit.validate_closure_locked_evaluation_input_bundle_invocation(
            valid, gate=gate, env={"DVC_NO_ANALYTICS": "1"}
        )
        valid.target = ["x"]
        with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
            precommit.validate_closure_locked_evaluation_input_bundle_invocation(
                valid, gate=gate, env={"DVC_NO_ANALYTICS": "1"}
            )
    binary_checks: list[tuple[str, int | None]] = []
    monkeypatch.setattr(
        precommit,
        "_require_no_symlink_ancestors",
        lambda path, *, anchor: binary_checks.append(
            (f"{anchor.as_posix()}:{path.as_posix()}", None)
        ),
    )
    monkeypatch.setattr(
        precommit,
        "_require_regular_file",
        lambda path, *, mode: binary_checks.append((path.as_posix(), mode)),
    )
    precommit.validate_closure_locked_evaluation_input_dvc_binary(
        precommit.DEFAULT_DVC_BIN.as_posix()
    )
    assert binary_checks == [
        (".:.venv/bin/dvc", None),
        (".venv/bin/dvc", 0o755),
    ]
    with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
        precommit.validate_closure_locked_evaluation_input_dvc_binary("dvc")


def test_r_invocation_requires_exact_four_targets_and_no_push(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        precommit, "_closure_locked_evaluation_input_bundle_module", _fake_patch
    )
    valid = _args(gate="R-E0-MI")
    precommit.validate_closure_locked_evaluation_input_bundle_invocation(
        valid, gate="R-E0-MI", env={"DVC_NO_ANALYTICS": "1"}
    )
    for targets in (valid.target[:-1], [*valid.target, "extra"], [valid.target[0]] * 4):
        candidate = SimpleNamespace(**vars(valid))
        candidate.target = targets
        with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
            precommit.validate_closure_locked_evaluation_input_bundle_invocation(
                candidate, gate="R-E0-MI", env={"DVC_NO_ANALYTICS": "1"}
            )
    precommit.validate_closure_locked_evaluation_input_unmanaged_namespace(
        [
            Path("data/closure_v1/locked_evaluation"),
            Path("data/panel/_monthly_partials"),
            Path("data/splits/monthly_model_splits_discarded_v0.parquet"),
        ]
    )
    for unmanaged in (
        [],
        [Path("data/closure_v1/locked_evaluation/extra")],
        [
            Path("data/closure_v1/locked_evaluation"),
            Path("data/closure_v1/locked_evaluation/extra"),
        ],
    ):
        with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
            precommit.validate_closure_locked_evaluation_input_unmanaged_namespace(
                unmanaged
            )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        precommit,
        "write_report",
        lambda report_path, **kwargs: captured.update(
            {"report_path": report_path, **kwargs}
        ),
    )
    failed = precommit.CommandResult(
        command=[".venv/bin/dvc", "add", "--no-relink", valid.target[1]],
        returncode=2,
        stdout="",
        stderr="failed",
    )
    precommit.write_closure_locked_evaluation_input_dvc_failure_report(
        report_path=Path("tmp/pre_commit_artifacts_failure.md"),
        selected_dvc_paths=[Path(path) for path in valid.target],
        rejected_unmanaged_paths=[Path("data/panel/_monthly_partials")],
        git_status_before="status",
        dvc_status_before={},
        dvc_add_results=[
            precommit.CommandResult(
                command=[".venv/bin/dvc", "add", "--no-relink", valid.target[0]],
                returncode=0,
                stdout="",
                stderr="",
            ),
            failed,
        ],
        failed_target_index=2,
    )
    assert captured["exclusive"] is True
    assert captured["git_add_result"] is None
    assert captured["dvc_push_result"] is None
    findings = captured["reproducibility_findings"]
    assert len(findings) == 1 and findings[0].level == "fail"
    assert "partial pointer evidence was preserved" in findings[0].message


def test_staged_scope_is_exact_for_h_p_and_r(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        precommit, "_closure_locked_evaluation_input_bundle_module", _fake_patch
    )
    for gate, scope in (("H-E0-MIB", H_SCOPE), ("P-E0-MIB", P_SCOPE), ("R-E0-MI", R_SCOPE)):
        precommit.validate_closure_locked_evaluation_input_bundle_staged_scope(
            _staged(scope), gate=gate
        )
        with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
            precommit.validate_closure_locked_evaluation_input_bundle_staged_scope(
                _staged(scope) + "A\textra\n", gate=gate
            )

    observed_modes: dict[str, int] = {}

    def git_output(repo_root: Path, *args: str) -> str:
        del repo_root
        raw_path = args[-1]
        if args[:2] == ("ls-files", "-s"):
            return f"{H_GIT_MODES[raw_path]} {'a' * 40} 0\t{raw_path}\n"
        if args[:2] == ("hash-object", "--no-filters"):
            return "a" * 40 + "\n"
        raise AssertionError(args)

    def identity(path: Path, *, repo_root: Path, mode: int) -> SimpleNamespace:
        del repo_root
        observed_modes[path.as_posix()] = mode
        return SimpleNamespace(path=path.as_posix(), nlink=1)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    monkeypatch.setattr(precommit, "_registration_file_identity", identity)
    assert len(
        precommit.validate_closure_locked_evaluation_input_bundle_staged_bindings(
            gate="H-E0-MIB"
        )
    ) == 6
    assert observed_modes == {
        path: 0o755 if mode == "100755" else 0o644
        for path, mode in H_GIT_MODES.items()
    }


def test_workspace_scope_is_exact_for_h_p_and_r(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        precommit, "_closure_locked_evaluation_input_bundle_module", _fake_patch
    )
    for gate, scope in (("H-E0-MIB", H_SCOPE), ("P-E0-MIB", P_SCOPE), ("R-E0-MI", R_SCOPE)):
        precommit.validate_closure_locked_evaluation_input_bundle_workspace_scope(
            _short(scope, staged=True), gate=gate
        )
        with pytest.raises(precommit.ClosureLockedEvaluationInputBundleAdapterError):
            precommit.validate_closure_locked_evaluation_input_bundle_workspace_scope(
                _short(scope, staged=True) + "?? extra\n", gate=gate
            )


def test_transactions_revalidate_remote_p_and_r(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    fake = _fake_patch(
        collect_closure_locked_evaluation_input_bundle_prelock_state=(
            lambda **kwargs: calls.append(("h", kwargs)) or _prelock()
        ),
        validate_locked_evaluation_input_bundle_unpublished_lock_bundle=(
            lambda **kwargs: calls.append(("p", kwargs)) or _unpublished("staged")
        ),
        require_locked_evaluation_input_bundle_authority=(
            lambda **kwargs: calls.append(("r", kwargs))
            or _authority("exact6_staged")
        ),
        validate_locked_evaluation_input_bundle=(
            lambda **kwargs: calls.append(("bundle", kwargs))
            or _r_validation(staged=True)
        ),
    )
    monkeypatch.setattr(precommit, "_closure_locked_evaluation_input_bundle_module", lambda: fake)
    monkeypatch.setattr(
        precommit, "validate_closure_locked_evaluation_input_bundle_staged_scope", lambda *a, **k: None
    )
    monkeypatch.setattr(
        precommit, "validate_closure_locked_evaluation_input_bundle_workspace_scope", lambda *a, **k: None
    )
    monkeypatch.setattr(
        precommit,
        "validate_closure_locked_evaluation_input_bundle_staged_bindings",
        lambda *a, **k: (),
    )
    monkeypatch.setattr(
        precommit,
        "snapshot_closure_locked_evaluation_input_physical_outputs",
        lambda **kwargs: (),
    )
    monkeypatch.setattr(
        precommit,
        "_git_output",
        lambda repo_root, *args: BASE + "\n"
        if args == ("rev-parse", "HEAD")
        else "scope\n",
    )
    for gate in ("H-E0-MIB", "P-E0-MIB", "R-E0-MI"):
        precommit.revalidate_closure_locked_evaluation_input_bundle_transaction(
            gate=gate,
            staged_status="scope\n",
            expected_physical_snapshot=() if gate == "R-E0-MI" else None,
        )
    assert calls == [
        ("h", {"repo_root": Path("."), "verify_remote": True}),
        ("h", {"repo_root": Path("."), "verify_remote": True}),
        ("p", {"repo_root": Path("."), "verify_remote": True}),
        ("r", {"repo_root": Path("."), "verify_remote": True}),
        (
            "bundle",
            {
                "repo_root": Path("."),
                "require_staged": True,
                "verify_remote": True,
            },
        ),
    ]

    from src.experiments import closure_locked_evaluation_input_bundle as core

    binding_sha256 = "4" * 64
    source_snapshots = [{"path": "a"}, {"path": "b"}]
    public_records = [{"path": "rebuilt"}]
    expected_summary = {"origin_count": 88}
    expected_manifest = {"authority_binding_sha256": binding_sha256}
    expected_materialization = {
        "source_snapshots": source_snapshots,
        "public_records": public_records,
        "summary": expected_summary,
        "manifest": expected_manifest,
    }
    semantics = {
        "physical_outputs": public_records,
        "summary": expected_summary,
        "manifest": expected_manifest,
        "r_outputs_sha256": "5" * 64,
    }
    monkeypatch.setattr(
        core,
        "require_locked_evaluation_input_bundle_authority",
        lambda **kwargs: {
            "input_bundle_run_consumed": True,
            "authority_binding_sha256": binding_sha256,
            "input_contract": {"source_records": [{}, {}, {}, {}]},
        },
    )
    monkeypatch.setattr(
        core,
        "_validate_r_repository_state",
        lambda **kwargs: "exact6_staged",
    )
    namespace = {"coordination_present_count": 0, "r_state": "complete"}
    monkeypatch.setattr(core, "_require_namespace", lambda **kwargs: namespace)
    materialization_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        core,
        "_build_expected_r_materialization",
        lambda authority, **kwargs: (
            materialization_calls.append(dict(authority))
            or expected_materialization
        ),
    )
    monkeypatch.setattr(
        core,
        "_recapture_scientific_source_snapshots",
        lambda **kwargs: source_snapshots,
    )
    monkeypatch.setattr(
        core,
        "_validate_scientific_source_bindings",
        lambda *args, **kwargs: None,
    )
    pointer_requirements: list[bool] = []

    def stable_semantics(*, pointers_required: bool, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        pointer_requirements.append(pointers_required)
        return semantics

    monkeypatch.setattr(core, "_validate_r_bundle_semantics", stable_semantics)
    validated = core.validate_locked_evaluation_input_bundle(
        repo_root=Path("."), require_staged=True, verify_remote=True
    )
    assert len(materialization_calls) == 1
    assert pointer_requirements == [True, True]
    assert validated["status"] == "input_bundle_validated"
    assert validated["r_stage_state"] == "exact6_staged"
    assert (
        validated["physical_output_count"],
        validated["tracked_output_count"],
        validated["pointer_count"],
        validated["summary_count"],
        validated["manifest_count"],
    ) == (4, 6, 4, 1, 1)
    assert validated["manifest_written_last"] is True
    assert validated["input_only"] is True
    for field in (
        "target_paths_opened",
        "target_availability_inspected",
        "outcome_paths_opened",
        "future_outcomes_accessed",
        "evaluation_authorized",
        "e0_m_authorized",
        "e0_u_authorized",
        "writes_performed",
    ):
        assert validated[field] is False

    forged_semantics = {
        **semantics,
        "physical_outputs": [{"path": "coherently-forged"}],
    }
    monkeypatch.setattr(
        core,
        "_validate_r_bundle_semantics",
        lambda **kwargs: forged_semantics,
    )
    with pytest.raises(
        core.ClosureLockedEvaluationInputBundleError,
        match="source reconstruction",
    ):
        core.validate_locked_evaluation_input_bundle(
            repo_root=Path("."), require_staged=True, verify_remote=True
        )

    drifted_semantics = iter(
        (semantics, {**semantics, "r_outputs_sha256": "6" * 64})
    )
    monkeypatch.setattr(
        core,
        "_validate_r_bundle_semantics",
        lambda **kwargs: next(drifted_semantics),
    )
    with pytest.raises(
        core.ClosureLockedEvaluationInputBundleError,
        match="semantics changed",
    ):
        core.validate_locked_evaluation_input_bundle(
            repo_root=Path("."), require_staged=True, verify_remote=True
        )

    def pointer_drift(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        raise core.ClosureLockedEvaluationInputBundleError(
            "E0-MIB DVC pointer binding drifted"
        )

    monkeypatch.setattr(core, "_validate_r_bundle_semantics", pointer_drift)
    with pytest.raises(
        core.ClosureLockedEvaluationInputBundleError,
        match="pointer binding drifted",
    ):
        core.validate_locked_evaluation_input_bundle(
            repo_root=Path("."), require_staged=True, verify_remote=True
        )

    monkeypatch.setattr(core, "_validate_r_bundle_semantics", stable_semantics)
    stage_states = iter(("exact6_staged", "wrong"))
    monkeypatch.setattr(
        core,
        "_validate_r_repository_state",
        lambda **kwargs: next(stage_states),
    )
    with pytest.raises(
        core.ClosureLockedEvaluationInputBundleError,
        match="stage state changed",
    ):
        core.validate_locked_evaluation_input_bundle(
            repo_root=Path("."), require_staged=True, verify_remote=True
        )


def test_main_routes_mib_before_legacy_gates_and_keeps_generic_fallback() -> None:
    source = Path(precommit.__file__).read_text(encoding="utf-8")
    main = source[source.index("def main() -> int:") :]
    assert isinstance(
        precommit._final_calibration_stage_adapter_error("H-E0-MIB", "x"),
        precommit.ClosureLockedEvaluationInputBundleAdapterError,
    )
    assert "closure_locked_evaluation_input_bundle_pre_stage_scope(" in main
    assert main.index("closure_locked_evaluation_input_bundle_pre_stage_scope(") < main.index(
        "final_calibration_r8_post_publication_authority_pre_stage_scope("
    )
    assert 'else:\n            reproducibility_findings = reproducibility_checks(' in main
