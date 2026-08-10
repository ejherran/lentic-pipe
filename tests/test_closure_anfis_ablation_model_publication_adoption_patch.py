from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace
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
EXPECTED_MY_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_dvc_registration_patch_lock.schema.json",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_PATCH_1.md",
    "src/experiments/closure_anfis_ablation_dvc_registration_patch.py",
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
}
EXPECTED_MY_MODIFICATIONS = {
    "configs/closure_v1/dvc_artifacts_post_lock.yaml",
    "src/data/prepare_commit_artifacts.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
}
EXPECTED_MY_P_PATHS = {
    "reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_patch_lock.json",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_patch_lock_manifest.json"
    ),
}
EXPECTED_MZ_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_dvc_registration_adoption_patch_lock.schema.json",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_ADOPTION_PATCH_1.md",
    "src/experiments/closure_anfis_ablation_dvc_registration_adoption_patch.py",
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_adoption_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py",
}
EXPECTED_MZ_MODIFICATIONS = {
    "src/data/prepare_commit_artifacts.py",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
}
EXPECTED_MZ_P_PATHS = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_adoption_patch_lock.json"
    ),
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_adoption_patch_lock_manifest.json"
    ),
}
EXPECTED_MZA_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_dvc_registration_order_patch_lock.schema.json",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_ORDER_PATCH_1.md",
    "src/experiments/closure_anfis_ablation_dvc_registration_order_patch.py",
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_order_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py",
}
EXPECTED_MZA_MODIFICATIONS = {
    "src/data/prepare_commit_artifacts.py",
    "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
}
EXPECTED_MZA_P_PATHS = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_order_patch_lock.json"
    ),
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_order_patch_lock_manifest.json"
    ),
}
EXPECTED_MZB_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_dvc_registration_namespace_patch_lock.schema.json",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_NAMESPACE_PATCH_1.md",
    "src/experiments/closure_anfis_ablation_dvc_registration_namespace_patch.py",
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_namespace_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_namespace_patch.py",
}
EXPECTED_MZB_MODIFICATIONS = {
    "src/data/prepare_commit_artifacts.py",
    "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
}
EXPECTED_MZB_P_PATHS = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_namespace_patch_lock.json"
    ),
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_namespace_patch_lock_manifest.json"
    ),
}
EXPECTED_MZC_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_dvc_registration_gitignore_patch.schema.json",
    "docs/closure_v1/ANFIS_ABLATION_DVC_REGISTRATION_GITIGNORE_PATCH.md",
    "src/experiments/closure_anfis_ablation_dvc_registration_gitignore_patch.py",
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_gitignore_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_gitignore_patch.py",
}
EXPECTED_MZC_MODIFICATIONS = {
    ".gitignore",
    "src/data/prepare_commit_artifacts.py",
    "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_namespace_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
}
EXPECTED_MZC_P_PATHS = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_gitignore_patch_lock.json"
    ),
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_gitignore_patch_lock_manifest.json"
    ),
}
EXPECTED_MZD_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_dvc_registration_status_patch.schema.json",
    "docs/closure_v1/ANFIS_ABLATION_DVC_REGISTRATION_STATUS_PATCH.md",
    "src/experiments/closure_anfis_ablation_dvc_registration_status_patch.py",
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_status_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_status_patch.py",
}
EXPECTED_MZD_MODIFICATIONS = {
    "src/data/prepare_commit_artifacts.py",
    "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_gitignore_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_namespace_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
}
EXPECTED_MZD_P_PATHS = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_status_patch_lock.json"
    ),
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_status_patch_lock_manifest.json"
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
    historical_mx_h = {
        path: ("A" if path in EXPECTED_ADDITIONS else "M")
        for path in EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    }
    historical_mx_p = {path: "A" for path in EXPECTED_P_PATHS}
    historical_my_h = {
        path: ("A" if path in EXPECTED_MY_ADDITIONS else "M")
        for path in EXPECTED_MY_ADDITIONS | EXPECTED_MY_MODIFICATIONS
    }
    historical_my_p = {path: "A" for path in EXPECTED_MY_P_PATHS}
    historical_my_r = {
        **{
            path: "A"
            for path in precommit_artifacts.ANFIS_ABLATION_UNTRACKED_LIGHT_PATHS
        },
        **{
            path: "A"
            for path in precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS
        },
        "models.dvc": "M",
    }
    historical_mz_h = {
        path: ("A" if path in EXPECTED_MZ_ADDITIONS else "M")
        for path in EXPECTED_MZ_ADDITIONS | EXPECTED_MZ_MODIFICATIONS
    }
    historical_mz_p = {path: "A" for path in EXPECTED_MZ_P_PATHS}
    historical_mz_r = {
        **{
            path: "A"
            for path in precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS
        },
        "models.dvc": "M",
    }
    historical_mza_h = {
        path: ("A" if path in EXPECTED_MZA_ADDITIONS else "M")
        for path in EXPECTED_MZA_ADDITIONS | EXPECTED_MZA_MODIFICATIONS
    }
    historical_mza_p = {path: "A" for path in EXPECTED_MZA_P_PATHS}
    historical_mzb_h = {
        path: ("A" if path in EXPECTED_MZB_ADDITIONS else "M")
        for path in EXPECTED_MZB_ADDITIONS | EXPECTED_MZB_MODIFICATIONS
    }
    historical_mzb_p = {path: "A" for path in EXPECTED_MZB_P_PATHS}
    historical_mzc_h = {
        path: ("A" if path in EXPECTED_MZC_ADDITIONS else "M")
        for path in EXPECTED_MZC_ADDITIONS | EXPECTED_MZC_MODIFICATIONS
    }
    historical_mzc_p = {path: "A" for path in EXPECTED_MZC_P_PATHS}
    current_h = {
        path: ("A" if path in EXPECTED_MZD_ADDITIONS else "M")
        for path in EXPECTED_MZD_ADDITIONS | EXPECTED_MZD_MODIFICATIONS
    }
    current_p = {path: "A" for path in EXPECTED_MZD_P_PATHS}
    current_r = dict(historical_mz_r)
    assert precommit_artifacts.DEFERRED_DVC_H_MX_STAGED_SCOPE == historical_mx_h
    assert precommit_artifacts.DEFERRED_DVC_P_MX_STAGED_SCOPE == historical_mx_p
    assert precommit_artifacts.DEFERRED_DVC_H_MY_STAGED_SCOPE == historical_my_h
    assert precommit_artifacts.DEFERRED_DVC_P_MY_STAGED_SCOPE == historical_my_p
    assert precommit_artifacts.ANFIS_ABLATION_R_MY_STAGED_SCOPE == historical_my_r
    assert precommit_artifacts.DEFERRED_DVC_H_MZ_STAGED_SCOPE == historical_mz_h
    assert precommit_artifacts.DEFERRED_DVC_P_MZ_STAGED_SCOPE == historical_mz_p
    assert precommit_artifacts.ANFIS_ABLATION_R_MZ_STAGED_SCOPE == historical_mz_r
    assert precommit_artifacts.DEFERRED_DVC_H_MZA_STAGED_SCOPE == historical_mza_h
    assert precommit_artifacts.DEFERRED_DVC_P_MZA_STAGED_SCOPE == historical_mza_p
    assert precommit_artifacts.ANFIS_ABLATION_R_MZA_STAGED_SCOPE == current_r
    assert precommit_artifacts.DEFERRED_DVC_H_MZB_STAGED_SCOPE == historical_mzb_h
    assert precommit_artifacts.DEFERRED_DVC_P_MZB_STAGED_SCOPE == historical_mzb_p
    assert precommit_artifacts.ANFIS_ABLATION_R_MZB_STAGED_SCOPE == current_r
    assert (
        precommit_artifacts.DEFERRED_DVC_H_MZC_STAGED_SCOPE == historical_mzc_h
    )
    assert (
        precommit_artifacts.DEFERRED_DVC_P_MZC_STAGED_SCOPE == historical_mzc_p
    )
    assert precommit_artifacts.ANFIS_ABLATION_R_MZC_STAGED_SCOPE == current_r
    assert precommit_artifacts.DEFERRED_DVC_H_MZD_STAGED_SCOPE == current_h
    assert precommit_artifacts.DEFERRED_DVC_P_MZD_STAGED_SCOPE == current_p
    assert precommit_artifacts.ANFIS_ABLATION_R_MZD_STAGED_SCOPE == current_r
    assert len(historical_mz_h) == 9
    assert len(historical_mz_p) == 2
    assert len(historical_mz_r) == 11
    assert len(historical_mza_h) == 10
    assert len(historical_mza_p) == 2
    assert len(historical_mzb_h) == 11
    assert len(historical_mzb_p) == 2
    assert len(historical_mzc_h) == 13
    assert len(historical_mzc_p) == 2
    assert len(current_h) == 13
    assert len(current_p) == 2
    assert len(current_r) == 11
    assert precommit_artifacts.DEFERRED_DVC_ACTIVE_STAGING_GATES == frozenset(
        {"H-E0-MZD", "P-E0-MZD"}
    )
    for current_gate in ("H-E0-MZD", "P-E0-MZD"):
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
        "H-E0-MX",
        "P-E0-MX",
        "H-E0-MY",
        "P-E0-MY",
        "H-E0-MZ",
        "P-E0-MZ",
        "H-E0-MZA",
        "P-E0-MZA",
        "H-E0-MZB",
        "P-E0-MZB",
        "H-E0-MZC",
        "P-E0-MZC",
    ):
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="closed to exact H-E0-MZD/P-E0-MZD",
        ):
            precommit_artifacts.require_active_deferred_dvc_staging_gate(
                historical_gate
            )

    h_staged = "".join(
        f"{status}\t{path}\n" for path, status in sorted(current_h.items())
    )
    p_staged = "".join(
        f"{status}\t{path}\n" for path, status in sorted(current_p.items())
    )
    h_pre_stage = "".join(
        f"{'??' if status == 'A' else ' M'} {path}\n"
        for path, status in sorted(current_h.items())
    )
    p_pre_stage = "".join(f"?? {path}\n" for path in sorted(current_p))
    assert precommit_artifacts.validate_deferred_dvc_staged_scope(h_staged) == (
        "H-E0-MZD"
    )
    assert precommit_artifacts.validate_deferred_dvc_staged_scope(p_staged) == (
        "P-E0-MZD"
    )
    assert precommit_artifacts.validate_deferred_dvc_pre_stage_scope(
        h_pre_stage
    ) == "H-E0-MZD"
    assert precommit_artifacts.validate_deferred_dvc_pre_stage_scope(
        p_pre_stage
    ) == "P-E0-MZD"

    r_pre_stage = "".join(
        f"{'??' if status == 'A' else ' M'} {path}\n"
        for path, status in sorted(current_r.items())
    )
    r_staged = "".join(
        f"{status}\t{path}\n" for path, status in sorted(current_r.items())
    )
    assert (
        precommit_artifacts.validate_anfis_ablation_registration_pre_stage_scope(
            r_pre_stage
        )
        == "R-E0-MZD"
    )
    assert (
        precommit_artifacts.validate_anfis_ablation_registration_staged_scope(
            r_staged
        )
        == "R-E0-MZD"
    )


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
    assert precommit_artifacts.ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_COMMIT == (
        "2f0643ab6f634fdcce71f0ee0d847c448d2c61f5"
    )
    assert precommit_artifacts.ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_PARENT == (
        "af233a89e22ce380f7b1f2094cdf4a92eb95b83d"
    )
    assert set(precommit_artifacts.ANFIS_ABLATION_MZ_TRACKED_LIGHT_PATHS) == set(
        precommit_artifacts.ANFIS_ABLATION_LIGHT_REPORT_PATHS
    )
    assert len(precommit_artifacts.ANFIS_ABLATION_MZ_TRACKED_LIGHT_PATHS) == 50
    assert precommit_artifacts.ANFIS_ABLATION_MZ_UNTRACKED_LIGHT_PATHS == ()
    precommit_artifacts._validate_anfis_ablation_mz_git_tracking(ROOT)
    pointer_count = sum(
        os.path.lexists(ROOT / path)
        for path in precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS
    )
    assert pointer_count in {0, 10}
    snapshot = precommit_artifacts.snapshot_anfis_ablation_family_bundle(
        repo_root=ROOT, expected_pointer_count=pointer_count
    )
    assert len(snapshot) == 80
    assert all(record.nlink == 1 and record.ctime_ns > 0 for record in snapshot)
    assert replace(snapshot[0], nlink=2) != snapshot[0]
    assert replace(snapshot[0], ctime_ns=snapshot[0].ctime_ns + 1) != snapshot[0]
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="exact pre/post registration pointer set",
    ):
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=ROOT, expected_pointer_count=1
        )


def test_my_registration_inventory_is_closed_without_expanding_general_inventory() -> None:
    registration = precommit_artifacts.load_anfis_ablation_registration_artifacts()
    assert len(registration) == 10
    assert tuple(artifact.path for artifact in registration) == tuple(
        Path(path)
        for path in precommit_artifacts.ANFIS_ABLATION_SELECTION_PREDICTION_PATHS
    )
    assert len({artifact.artifact_id for artifact in registration}) == 10
    general = precommit_artifacts.load_configured_dvc_artifacts(
        precommit_artifacts.DEFAULT_DVC_MANIFEST
    )
    closure_general = [
        artifact
        for artifact in general
        if artifact.artifact_id.startswith("closure_v1_")
    ]
    assert len(closure_general) == 23
    assert not set(registration) & set(general)


def test_my_family_exclude_and_registration_cli_are_exact(tmp_path: Path) -> None:
    exclude = tmp_path / "family-excludes"
    payload = "".join(
        f"{pattern}\n"
        for pattern in precommit_artifacts.ANFIS_ABLATION_LIGHT_EXCLUDE_PATTERNS
    )
    exclude.write_text(payload, encoding="utf-8")
    exclude.chmod(0o600)
    environment = {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.excludesFile",
        "GIT_CONFIG_VALUE_0": exclude.as_posix(),
    }
    metadata = exclude.lstat()
    assert len(precommit_artifacts.ANFIS_ABLATION_LIGHT_EXCLUDE_PATTERNS) == 45
    assert precommit_artifacts.validate_anfis_ablation_family_git_exclude_environment(
        env=environment
    ) == (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mtime_ns,
        hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    )
    assert precommit_artifacts.validate_anfis_ablation_adoption_git_environment(
        env={}
    ) == (0, 0, 0, hashlib.sha256(b"").hexdigest())
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="default Git visibility",
    ):
        precommit_artifacts.validate_anfis_ablation_adoption_git_environment(
            env=environment
        )

    args = SimpleNamespace(
        register_anfis_ablation_model_family=True,
        allow_unmanaged=False,
        no_push=True,
        yes=False,
        dry_run=False,
        skip_publication_check=False,
        jobs=None,
        dvc_bin=None,
        manifest=precommit_artifacts.DEFAULT_DVC_MANIFEST,
        report=None,
        target=[],
        defer_dvc_target=[],
    )
    valid_registration_environment = {
        "DVC_NO_ANALYTICS": "1",
        "HOME": precommit_artifacts.ANFIS_ABLATION_EXPECTED_HOME.as_posix(),
        "XDG_CONFIG_HOME": (
            precommit_artifacts.ANFIS_ABLATION_EXPECTED_XDG_CONFIG_HOME.as_posix()
        ),
        "XDG_CONFIG_DIRS": (
            precommit_artifacts.ANFIS_ABLATION_EXPECTED_XDG_CONFIG_DIRS
        ),
    }
    precommit_artifacts.validate_anfis_ablation_registration_invocation(
        args, env=valid_registration_environment
    )
    precommit_artifacts.validate_anfis_ablation_registration_invocation(
        args, env={"DVC_NO_ANALYTICS": "1"}
    )
    precommit_artifacts.validate_anfis_ablation_registration_invocation(
        args,
        env={
            **valid_registration_environment,
            "DVC_SITE_CACHE_DIR": (
                precommit_artifacts.DEFAULT_DVC_SITE_CACHE_DIR.as_posix()
            ),
        },
    )
    for field, value in (
        ("allow_unmanaged", True),
        ("no_push", False),
        ("yes", True),
        ("target", ["models"]),
        ("defer_dvc_target", ["models"]),
    ):
        invalid = SimpleNamespace(**vars(args))
        setattr(invalid, field, value)
        with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
            precommit_artifacts.validate_anfis_ablation_registration_invocation(
                invalid, env=valid_registration_environment
            )
    for redirected_name in (
        "DVC_ROOT",
        "DVC_GLOBAL_CONFIG_DIR",
        "DVC_SYSTEM_CONFIG_DIR",
        "DVC_DIR",
    ):
        with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
            precommit_artifacts.validate_anfis_ablation_registration_invocation(
                args,
                env={
                    **valid_registration_environment,
                    redirected_name: "/tmp/redirected-dvc",
                },
            )
    for redirected_name in (
        "PYTHONPATH",
        "PYTHONFAKE",
        "LD_PRELOAD",
        "GIT_EXEC_PATH",
    ):
        with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
            precommit_artifacts.validate_anfis_ablation_registration_invocation(
                args,
                env={
                    **valid_registration_environment,
                    redirected_name: "/tmp/redirected-runtime",
                },
            )
    with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
        precommit_artifacts.validate_anfis_ablation_registration_invocation(
            args,
            env={
                **valid_registration_environment,
                "PATH": "/tmp/fake-bin",
            },
        )
    for redirected_name in ("HOME", "XDG_CONFIG_HOME", "XDG_CONFIG_DIRS"):
        redirected_environment = dict(valid_registration_environment)
        redirected_environment[redirected_name] = "/tmp/redirected-config"
        with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
            precommit_artifacts.validate_anfis_ablation_registration_invocation(
                args, env=redirected_environment
            )

    dvc_add_commands = tuple(
        precommit_artifacts.anfis_ablation_registration_dvc_add_command(
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(), target
        )
        for target in precommit_artifacts.ANFIS_ABLATION_REGISTRATION_DVC_TARGETS
    )
    assert len(dvc_add_commands) == 11
    assert dvc_add_commands == tuple(
        [
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
            "add",
            "--no-relink",
            target.as_posix(),
        ]
        for target in precommit_artifacts.ANFIS_ABLATION_REGISTRATION_DVC_TARGETS
    )
    with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
        precommit_artifacts.anfis_ablation_registration_dvc_add_command(
            precommit_artifacts.DEFAULT_DVC_BIN.as_posix(), Path("data")
        )

    repo_config, local_config = (
        precommit_artifacts.snapshot_anfis_ablation_dvc_configuration(
            repo_root=ROOT
        )
    )
    assert (repo_config.size, repo_config.sha256, repo_config.nlink) == (
        43,
        "cb08c869a906d07c5b1ccf593299a0f253e0ce03303c43070b6a68124b27fda0",
        1,
    )
    assert (local_config.size, local_config.sha256, local_config.nlink) == (
        211,
        "a912c374690215c7753070f68d7dfdaff8c1224b01c336aa887d6731a3bb2287",
        1,
    )
    runtime_identity = precommit_artifacts.snapshot_anfis_ablation_dvc_runtime(
        repo_root=ROOT
    )
    expected_wrapper = (
        precommit_artifacts.expected_anfis_ablation_dvc_wrapper_bytes(ROOT)
    )
    assert (
        runtime_identity.wrapper.size,
        runtime_identity.wrapper.sha256,
        runtime_identity.wrapper.nlink,
    ) == (
        len(expected_wrapper),
        hashlib.sha256(expected_wrapper).hexdigest(),
        1,
    )
    assert runtime_identity.python_link.target == "/usr/bin/python3.14"
    assert (
        runtime_identity.python_target.size,
        runtime_identity.python_target.sha256,
        runtime_identity.git.size,
        runtime_identity.git.sha256,
    ) == (
        14_424,
        "2700be1aabe3687bd597f21b0eac3b9bbdf7417e93035255a9286c67935b59bd",
        4_899_632,
        "93473c28694fd72bd889364107cd2770514de59780885a6a4aafca4d602e30ad",
    )
    registration_source = inspect.getsource(
        precommit_artifacts._run_anfis_ablation_model_family_registration
    )
    assert registration_source.index("transaction.__enter__()") < (
        registration_source.index("dvc_status_before = dvc_status_json")
    )
    assert "dvc_status_json(dvc_bin)" not in registration_source
    runtime_probe = tmp_path / "runtime-probe"
    runtime_bin = runtime_probe / ".venv/bin"
    runtime_bin.mkdir(parents=True)
    runtime_wrapper = runtime_bin / "dvc"
    runtime_wrapper.write_bytes(
        precommit_artifacts.expected_anfis_ablation_dvc_wrapper_bytes(
            runtime_probe
        )
    )
    runtime_wrapper.chmod(0o755)
    (runtime_bin / "python").symlink_to(
        precommit_artifacts.ANFIS_ABLATION_DVC_PYTHON_TARGET
    )
    runtime_before = precommit_artifacts.snapshot_anfis_ablation_dvc_runtime(
        repo_root=runtime_probe
    )
    wrapper_metadata = runtime_wrapper.stat()
    os.utime(
        runtime_wrapper,
        ns=(wrapper_metadata.st_atime_ns, wrapper_metadata.st_mtime_ns + 1_000_000),
    )
    runtime_after = precommit_artifacts.snapshot_anfis_ablation_dvc_runtime(
        repo_root=runtime_probe
    )
    assert runtime_after != runtime_before
    runtime_wrapper.write_bytes(b"#!/bin/false\n")
    runtime_wrapper.chmod(0o755)
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="DVC wrapper identity drifted",
    ):
        precommit_artifacts.snapshot_anfis_ablation_dvc_runtime(
            repo_root=runtime_probe
        )
    config_probe = tmp_path / "config-probe"
    (config_probe / ".dvc").mkdir(parents=True)
    for raw_path in (
        precommit_artifacts.ANFIS_ABLATION_REPO_DVC_CONFIG,
        precommit_artifacts.ANFIS_ABLATION_LOCAL_DVC_CONFIG,
    ):
        target = config_probe / raw_path
        target.write_bytes((ROOT / raw_path).read_bytes())
        target.chmod(0o644)
    config_before = precommit_artifacts.snapshot_anfis_ablation_dvc_configuration(
        repo_root=config_probe
    )
    touched_config = config_probe / precommit_artifacts.ANFIS_ABLATION_LOCAL_DVC_CONFIG
    touched_metadata = touched_config.stat()
    os.utime(
        touched_config,
        ns=(touched_metadata.st_atime_ns, touched_metadata.st_mtime_ns + 1_000_000),
    )
    config_after = precommit_artifacts.snapshot_anfis_ablation_dvc_configuration(
        repo_root=config_probe
    )
    assert config_after != config_before

    directory_probe = tmp_path / "empty-config-dir"
    directory_probe.mkdir(mode=0o700)
    directory_before = precommit_artifacts._registration_directory_identity(
        directory_probe, repo_root=tmp_path
    )
    transient = directory_probe / "config"
    transient.write_bytes(b"transient\n")
    transient.unlink()
    directory_after = precommit_artifacts._registration_directory_identity(
        directory_probe, repo_root=tmp_path
    )
    assert directory_after != directory_before

    guard_probe = tmp_path / "guard-probe"
    guard_probe.write_bytes(b"guard\n")
    guard_probe.chmod(0o600)
    guard_before = precommit_artifacts._registration_file_identity(
        guard_probe, repo_root=tmp_path, mode=0o600
    )
    guard_alias = tmp_path / "guard-alias"
    os.link(guard_probe, guard_alias)
    guard_after = precommit_artifacts._registration_file_identity(
        guard_probe, repo_root=tmp_path, mode=0o600
    )
    assert guard_after.nlink == 2
    assert not precommit_artifacts._same_registration_exact(
        guard_after, guard_before
    )
    guard_alias.unlink()

    deferred_args = SimpleNamespace(**vars(args))
    deferred_args.allow_unmanaged = True
    precommit_artifacts.validate_deferred_dvc_invocation(
        deferred_args,
        [precommit_artifacts.DEFERRED_DVC_MODELS_TARGET],
        env={"DVC_NO_ANALYTICS": "1"},
    )
    deferred_args.allow_unmanaged = False
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="requires --allow-unmanaged",
    ):
        precommit_artifacts.validate_deferred_dvc_invocation(
            deferred_args,
            [precommit_artifacts.DEFERRED_DVC_MODELS_TARGET],
            env={"DVC_NO_ANALYTICS": "1"},
        )


def test_mz_registration_transaction_restores_owned_partial_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "tmp").mkdir()
    models_pointer = tmp_path / "models.dvc"
    models_pointer.write_bytes(b"baseline models pointer\n")
    models_pointer.chmod(0o644)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("/tmp/\n/models\n", encoding="utf-8")
    gitignore.chmod(0o644)
    precommit_artifacts.run_command(
        ["git", "-C", tmp_path.as_posix(), "init", "--quiet"]
    )
    precommit_artifacts.run_command(
        [
            "git",
            "-C",
            tmp_path.as_posix(),
            "add",
            "--",
            ".gitignore",
            "models.dvc",
        ]
    )
    precommit_artifacts.run_command(
        [
            "git",
            "-C",
            tmp_path.as_posix(),
            "-c",
            "user.name=E0-MY Test",
            "-c",
            "user.email=e0-my@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "baseline",
        ]
    )
    baseline = models_pointer.lstat()
    baseline_gitignore = gitignore.read_bytes()
    baseline_gitignore_metadata = gitignore.lstat()
    models_root = tmp_path / "models"
    models_root.mkdir()
    from scmrepo.git import Git

    scm = Git(tmp_path)
    assert scm.ignore(models_root.resolve().as_posix()) is None
    observed_gitignore_metadata = gitignore.lstat()
    assert gitignore.read_bytes() == baseline_gitignore
    assert (
        observed_gitignore_metadata.st_dev,
        observed_gitignore_metadata.st_ino,
        observed_gitignore_metadata.st_mode,
        observed_gitignore_metadata.st_nlink,
        observed_gitignore_metadata.st_size,
        observed_gitignore_metadata.st_mtime_ns,
        observed_gitignore_metadata.st_ctime_ns,
    ) == (
        baseline_gitignore_metadata.st_dev,
        baseline_gitignore_metadata.st_ino,
        baseline_gitignore_metadata.st_mode,
        baseline_gitignore_metadata.st_nlink,
        baseline_gitignore_metadata.st_size,
        baseline_gitignore_metadata.st_mtime_ns,
        baseline_gitignore_metadata.st_ctime_ns,
    )
    selected_payloads = tuple(
        Path(path)
        for path in precommit_artifacts.ANFIS_ABLATION_SELECTION_PREDICTION_PATHS
    )
    selected_pointers = tuple(
        tmp_path / path
        for path in precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS
    )
    for pointer in selected_pointers:
        pointer.parent.mkdir(parents=True, exist_ok=True)

    coordination_paths = (
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_GUARD,
        precommit_artifacts.ANFIS_ABLATION_MODELS_DVC_BACKUP,
        precommit_artifacts.ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP,
        precommit_artifacts.ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR,
        precommit_artifacts.ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR,
    )

    def assert_coordination_absent() -> None:
        assert not any(
            os.path.lexists(tmp_path / path) for path in coordination_paths
        )

    real_write = os.write
    with monkeypatch.context() as patcher:
        patcher.setattr(
            precommit_artifacts.os,
            "write",
            lambda file_fd, data: (
                0
                if data
                == precommit_artifacts.ANFIS_ABLATION_REGISTRATION_ACTIVE_PAYLOAD
                else real_write(file_fd, data)
            ),
        )
        guard_failure = precommit_artifacts._AnfisAblationRegistrationTransaction(
            repo_root=tmp_path, manage_git_index=True
        )
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="Short write creating E0-MY guard",
        ):
            guard_failure.__enter__()
    assert_coordination_absent()

    gitignore_drift = precommit_artifacts._AnfisAblationRegistrationTransaction(
        repo_root=tmp_path, manage_git_index=True
    )
    gitignore_drift.__enter__()
    gitignore.write_bytes(baseline_gitignore + b"/foreign-concurrent\n")
    gitignore.chmod(0o644)
    injected_gitignore_drift = RuntimeError("injected .gitignore drift")
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="rollback could not be completed safely",
    ):
        gitignore_drift.__exit__(
            type(injected_gitignore_drift),
            injected_gitignore_drift,
            injected_gitignore_drift.__traceback__,
        )
    assert gitignore.read_bytes() == baseline_gitignore + b"/foreign-concurrent\n"
    assert_coordination_absent()
    gitignore.write_bytes(baseline_gitignore)
    gitignore.chmod(0o644)

    with monkeypatch.context() as patcher:
        patcher.setattr(
            precommit_artifacts.os,
            "write",
            lambda file_fd, data: (
                0
                if data == b"baseline models pointer\n"
                else real_write(file_fd, data)
            ),
        )
        bytes_failure = precommit_artifacts._AnfisAblationRegistrationTransaction(
            repo_root=tmp_path, manage_git_index=True
        )
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="Short write creating E0-MY independent",
        ):
            bytes_failure.__enter__()
    assert_coordination_absent()

    real_directory_identity = (
        precommit_artifacts._registration_directory_identity
    )
    with monkeypatch.context() as patcher:
        patcher.setattr(
            precommit_artifacts,
            "_registration_directory_identity",
            lambda path, *, repo_root: (
                (_ for _ in ()).throw(RuntimeError("injected directory capture"))
                if path.name
                == precommit_artifacts.ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR.name
                else real_directory_identity(path, repo_root=repo_root)
            ),
        )
        capture_failure = precommit_artifacts._AnfisAblationRegistrationTransaction(
            repo_root=tmp_path, manage_git_index=True
        )
        with pytest.raises(RuntimeError, match="directory capture"):
            capture_failure.__enter__()
    assert_coordination_absent()

    real_mkdir = os.mkdir
    with monkeypatch.context() as patcher:
        def mkdir_then_fail(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> None:
            real_mkdir(path, mode, dir_fd=dir_fd)
            if path == precommit_artifacts.ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR.name:
                raise RuntimeError("injected post-mkdir failure")

        patcher.setattr(precommit_artifacts.os, "mkdir", mkdir_then_fail)
        mkdir_failure = precommit_artifacts._AnfisAblationRegistrationTransaction(
            repo_root=tmp_path, manage_git_index=True
        )
        with pytest.raises(RuntimeError, match="post-mkdir"):
            mkdir_failure.__enter__()
    assert_coordination_absent()

    for link_failure_kind in ("post-link", "anchor-capture"):
        link_failure = precommit_artifacts._AnfisAblationRegistrationTransaction(
            repo_root=tmp_path, manage_git_index=True
        )
        link_failure.__enter__()
        link_failure.begin_dvc_mutation()
        with monkeypatch.context() as patcher:
            if link_failure_kind == "post-link":
                real_link = os.link

                def link_then_fail(
                    src: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                    dst: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                    *,
                    src_dir_fd: int | None = None,
                    dst_dir_fd: int | None = None,
                    follow_symlinks: bool = True,
                ) -> None:
                    real_link(
                        src,
                        dst,
                        src_dir_fd=src_dir_fd,
                        dst_dir_fd=dst_dir_fd,
                        follow_symlinks=follow_symlinks,
                    )
                    raise RuntimeError("injected post-link failure")

                patcher.setattr(precommit_artifacts.os, "link", link_then_fail)
            else:
                real_file_identity = precommit_artifacts._registration_file_identity

                def fail_anchor_capture(
                    path: Path, *, repo_root: Path, mode: int
                ) -> precommit_artifacts.RegistrationFileIdentity:
                    if path.name == precommit_artifacts.ANFIS_ABLATION_MODELS_DVC_BACKUP.name:
                        raise RuntimeError("injected anchor capture failure")
                    return real_file_identity(path, repo_root=repo_root, mode=mode)

                patcher.setattr(
                    precommit_artifacts,
                    "_registration_file_identity",
                    fail_anchor_capture,
                )
            with pytest.raises(RuntimeError, match="link|anchor capture"):
                link_failure.prepare_models_registration()
        injected_link = RuntimeError(f"injected {link_failure_kind}")
        link_failure.__exit__(
            type(injected_link), injected_link, injected_link.__traceback__
        )
        assert_coordination_absent()
        assert models_pointer.read_bytes() == b"baseline models pointer\n"
        assert models_pointer.lstat().st_nlink == 1

    foreign_guard_transaction = (
        precommit_artifacts._AnfisAblationRegistrationTransaction(
            repo_root=tmp_path, manage_git_index=True
        )
    )
    foreign_guard_transaction.__enter__()
    foreign_guard = (
        tmp_path / precommit_artifacts.ANFIS_ABLATION_REGISTRATION_GUARD
    )
    foreign_guard.unlink()
    foreign_guard.write_bytes(b"foreign guard replacement\n")
    foreign_guard.chmod(0o600)
    foreign_error = RuntimeError("injected foreign guard replacement")
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="rollback could not be completed safely",
    ):
        foreign_guard_transaction.__exit__(
            type(foreign_error), foreign_error, foreign_error.__traceback__
        )
    assert foreign_guard.read_bytes() == b"foreign guard replacement\n"
    foreign_guard.unlink()
    assert_coordination_absent()

    partial = precommit_artifacts._AnfisAblationRegistrationTransaction(
        repo_root=tmp_path, manage_git_index=True
    )
    partial.__enter__()
    sealed_config = precommit_artifacts.snapshot_anfis_ablation_dvc_configuration(
        repo_root=ROOT
    )
    sealed_runtime = precommit_artifacts.snapshot_anfis_ablation_dvc_runtime(
        repo_root=ROOT
    )
    with monkeypatch.context() as patcher:
        patcher.setattr(
            precommit_artifacts,
            "snapshot_anfis_ablation_dvc_configuration",
            lambda *, repo_root: sealed_config,
        )
        patcher.setattr(
            precommit_artifacts,
            "snapshot_anfis_ablation_dvc_runtime",
            lambda *, repo_root: sealed_runtime,
        )
        patcher.setattr(
            precommit_artifacts,
            "dvc_environment",
            lambda: {
                "DVC_NO_ANALYTICS": "1",
                "DVC_ROOT": "/tmp/forged-root",
                "GIT_EXEC_PATH": "/tmp/forged-git",
                "PYTHONPATH": "/tmp/forged-python",
                "LD_PRELOAD": "/tmp/forged-library",
            },
        )
        isolated_environment = partial.registration_dvc_environment(
            sealed_config, sealed_runtime
        )
    assert isolated_environment["PATH"] == "/usr/bin:/bin"
    assert isolated_environment["PYTHONNOUSERSITE"] == "1"
    assert isolated_environment["PYTHONSAFEPATH"] == "1"
    assert not {
        "DVC_ROOT",
        "GIT_EXEC_PATH",
        "PYTHONPATH",
        "LD_PRELOAD",
    }.intersection(isolated_environment)
    assert isolated_environment["DVC_GLOBAL_CONFIG_DIR"].endswith(
        precommit_artifacts.ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR.as_posix()
    )
    assert isolated_environment["DVC_SYSTEM_CONFIG_DIR"].endswith(
        precommit_artifacts.ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR.as_posix()
    )
    partial.begin_dvc_mutation()
    for payload, pointer in zip(
        selected_payloads[:2], selected_pointers[:2], strict=True
    ):
        pointer.write_bytes(b"outs: []\n")
        pointer.chmod(0o644)
        partial.capture_target(payload)
    precommit_artifacts.run_command(
        [
            "git",
            "-C",
            tmp_path.as_posix(),
            "add",
            "-A",
            "--",
            *(path.relative_to(tmp_path).as_posix() for path in selected_pointers[:2]),
        ]
    )
    injected_partial = RuntimeError("injected partial Git add failure")
    partial.__exit__(
        type(injected_partial), injected_partial, injected_partial.__traceback__
    )
    assert not any(pointer.exists() for pointer in selected_pointers)
    assert not precommit_artifacts._git_output(
        tmp_path, "diff", "--cached", "--name-only"
    ).strip()

    transaction = precommit_artifacts._AnfisAblationRegistrationTransaction(
        repo_root=tmp_path, manage_git_index=True
    )
    transaction.__enter__()
    transaction.begin_dvc_mutation()
    for payload, pointer in zip(
        selected_payloads, selected_pointers, strict=True
    ):
        pointer.write_bytes(b"outs: []\n")
        pointer.chmod(0o644)
        transaction.capture_target(payload)
    transaction.prepare_models_registration()
    models_pointer.write_bytes(b"registered models pointer\n")
    transaction.capture_target(Path("models"))
    registered = models_pointer.lstat()
    assert (registered.st_dev, registered.st_ino) == (
        baseline.st_dev,
        baseline.st_ino,
    )
    assert registered.st_nlink == 1
    precommit_artifacts.run_command(
        [
            "git",
            "-C",
            tmp_path.as_posix(),
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.ANFIS_ABLATION_R_MZB_STAGED_SCOPE),
        ]
    )
    transaction.mark_staging_owned()
    post_stage_report = tmp_path / "tmp" / "post-stage-report.md"
    post_stage_report.write_text("diagnostic report\n", encoding="utf-8")
    injected = RuntimeError("injected post-report failure")
    transaction.__exit__(type(injected), injected, injected.__traceback__)

    audit_transaction = precommit_artifacts._AnfisAblationRegistrationTransaction(
        repo_root=tmp_path, manage_git_index=True
    )
    audit_transaction.__enter__()
    audit_transaction.begin_dvc_mutation()
    for payload, pointer in zip(
        selected_payloads, selected_pointers, strict=True
    ):
        pointer.write_bytes(b"outs: []\n")
        pointer.chmod(0o644)
        audit_transaction.capture_target(payload)
    audit_transaction.prepare_models_registration()
    models_pointer.write_bytes(b"registered models pointer\n")
    audit_transaction.capture_target(Path("models"))
    precommit_artifacts.run_command(
        [
            "git",
            "-C",
            tmp_path.as_posix(),
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.ANFIS_ABLATION_R_MZB_STAGED_SCOPE),
        ]
    )
    audit_transaction.mark_staging_owned()
    audit_record = audit_transaction.effective_audit_record()
    assert set(audit_record) == {
        "mode",
        "guard",
        "bytes_backup",
        "anchor",
        "global_config_dir",
        "system_config_dir",
        "gitignore",
    }
    assert audit_record["mode"] == "in_place"
    assert audit_record["anchor"] is None
    global_config_record = audit_record["global_config_dir"]
    system_config_record = audit_record["system_config_dir"]
    assert isinstance(global_config_record, dict)
    assert isinstance(system_config_record, dict)
    gitignore_record = audit_record["gitignore"]
    assert isinstance(gitignore_record, dict)
    assert gitignore_record["path"] == ".gitignore"
    assert gitignore_record["mode"] == 0o644
    assert gitignore_record["nlink"] == 1
    assert global_config_record["entry_count"] == 0
    assert system_config_record["entry_count"] == 0
    assert os.path.lexists(
        tmp_path / precommit_artifacts.ANFIS_ABLATION_REGISTRATION_GUARD
    )
    assert os.path.lexists(
        tmp_path / precommit_artifacts.ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP
    )
    assert not os.path.lexists(
        tmp_path / precommit_artifacts.ANFIS_ABLATION_MODELS_DVC_BACKUP
    )
    injected_audit = RuntimeError("injected effective-authority failure")
    audit_transaction.__exit__(
        type(injected_audit), injected_audit, injected_audit.__traceback__
    )

    restored = models_pointer.lstat()
    assert models_pointer.read_bytes() == b"baseline models pointer\n"
    assert (restored.st_dev, restored.st_ino) == (baseline.st_dev, baseline.st_ino)
    assert restored.st_nlink == 1
    assert not any(pointer.exists() for pointer in selected_pointers)
    assert gitignore.read_bytes() == baseline_gitignore
    assert not precommit_artifacts._git_output(
        tmp_path, "diff", "--cached", "--name-only"
    ).strip()
    precommit_artifacts.validate_anfis_ablation_registration_initial_scope(
        precommit_artifacts._git_output(
            tmp_path, "status", "--short", "--untracked-files=all"
        )
    )
    assert not (tmp_path / precommit_artifacts.ANFIS_ABLATION_REGISTRATION_GUARD).exists()
    assert not (tmp_path / precommit_artifacts.ANFIS_ABLATION_MODELS_DVC_BACKUP).exists()
    assert not (
        tmp_path / precommit_artifacts.ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP
    ).exists()
    assert not (
        tmp_path / precommit_artifacts.ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR
    ).exists()
    assert not (
        tmp_path / precommit_artifacts.ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR
    ).exists()

    commit_transaction = precommit_artifacts._AnfisAblationRegistrationTransaction(
        repo_root=tmp_path, manage_git_index=True
    )
    commit_transaction.__enter__()
    commit_transaction.begin_dvc_mutation()
    for payload, pointer in zip(
        selected_payloads, selected_pointers, strict=True
    ):
        pointer.write_bytes(b"outs: []\n")
        pointer.chmod(0o644)
        commit_transaction.capture_target(payload)
    commit_transaction.prepare_models_registration()
    models_pointer.write_bytes(b"registered models pointer\n")
    commit_transaction.capture_target(Path("models"))
    precommit_artifacts.run_command(
        [
            "git",
            "-C",
            tmp_path.as_posix(),
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.ANFIS_ABLATION_R_MZB_STAGED_SCOPE),
        ]
    )
    commit_transaction.mark_staging_owned()
    real_owned_unlink = precommit_artifacts._unlink_owned_registration_path
    with monkeypatch.context() as patcher:
        def unlink_then_fail(
            path: Path,
            identity: precommit_artifacts.RegistrationFileIdentity,
            *,
            repo_root: Path,
            expected_nlink: int | None = None,
        ) -> None:
            real_owned_unlink(
                path,
                identity,
                repo_root=repo_root,
                expected_nlink=expected_nlink,
            )
            if path.name == (
                precommit_artifacts.ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP.name
            ):
                raise RuntimeError("injected failure after backup unlink")

        patcher.setattr(
            precommit_artifacts,
            "_unlink_owned_registration_path",
            unlink_then_fail,
        )
        with pytest.raises(RuntimeError, match="after backup unlink"):
            commit_transaction.commit()
    assert commit_transaction.committed is True
    commit_transaction.__exit__(None, None, None)
    assert models_pointer.read_bytes() == b"registered models pointer\n"
    assert all(pointer.exists() for pointer in selected_pointers)
    assert not (
        tmp_path / precommit_artifacts.ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP
    ).exists()
    assert (
        tmp_path / precommit_artifacts.ANFIS_ABLATION_REGISTRATION_GUARD
    ).read_bytes() == (
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_COMMIT_READY_PAYLOAD
    )
    assert precommit_artifacts._git_output(
        tmp_path, "diff", "--cached", "--name-status"
    ).splitlines() == [
        f"{status}\t{path}"
        for path, status in sorted(
            precommit_artifacts.ANFIS_ABLATION_R_MZB_STAGED_SCOPE.items()
        )
    ]


def test_my_prediction_pointer_staging_discovers_all_ten_manifests() -> None:
    staged = {
        Path(path)
        for path in precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS
    }
    manifests = precommit_artifacts.discover_relevant_manifest_paths(staged)
    assert manifests == sorted(
        (Path(path) for path in precommit_artifacts.ANFIS_ABLATION_MANIFEST_PATHS),
        key=lambda path: path.as_posix(),
    )


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
