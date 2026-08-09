from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from src.data import prepare_commit_artifacts as precommit_artifacts
from src.experiments import (
    closure_anfis_ablation_dvc_registration_patch as patch,
)
from src.experiments import (
    closure_anfis_ablation_dvc_registration_adoption_patch as mz_patch,
)
from src.experiments import (
    lock_closure_anfis_ablation_dvc_registration_patch as locker,
)


ROOT = Path(__file__).resolve().parents[1]
P_MX_COMMIT = "c73b8ebe11d942631d24e43b0eac2f4b2e72e400"
FAMILY_RECORDS_SHA256 = (
    "e625add8f8af1746f7deda9ff13a84a4d4f4c27b47e3b6312922db419508dd8e"
)
MODELS_DVC_SHA256 = (
    "fcb93f78cc3e60c1c7f5bcc94a1765080358e0a5176880f1efa6245fa5365e5d"
)
ORDERED_SLOTS = (
    ("A0", 1729),
    ("A1", 1729),
    ("A0", 20260612),
    ("A1", 20260612),
    ("A0", 20260613),
    ("A1", 20260613),
    ("A0", 20260614),
    ("A1", 20260614),
    ("A0", 314159),
    ("A1", 314159),
)
EXPECTED_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_dvc_registration_patch_lock.schema.json",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_PATCH_1.md",
    "src/experiments/closure_anfis_ablation_dvc_registration_patch.py",
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
}
EXPECTED_MODIFICATIONS = {
    "configs/closure_v1/dvc_artifacts_post_lock.yaml",
    "src/data/prepare_commit_artifacts.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
}
EXPECTED_P_PATHS = {
    "reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_patch_lock.json",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_patch_lock_manifest.json"
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slot_paths(model_id: str, base_seed: int) -> tuple[tuple[str, Path], ...]:
    report_root = Path(f"reports/closure_v1/02_models/{model_id}")
    return (
        (
            "model",
            Path(
                "models/closure_v1/anfis_ablation/"
                f"{model_id}/seed_{base_seed}.pt"
            ),
        ),
        (
            "checkpoint",
            Path(
                "models/closure_v1/anfis_ablation/"
                f"{model_id}/seed_{base_seed}.checkpoint.pt"
            ),
        ),
        ("preprocessor", report_root / f"seed_{base_seed}_preprocessor.json"),
        ("training_curve", report_root / f"seed_{base_seed}_training_curve.csv"),
        (
            "selection_predictions",
            Path(
                "data/closure_v1/development/anfis_ablation/"
                f"{model_id}/seed_{base_seed}_selection_predictions.parquet"
            ),
        ),
        (
            "selection_metrics",
            report_root / f"seed_{base_seed}_selection_metrics.csv",
        ),
        ("report", report_root / f"seed_{base_seed}_report.md"),
        ("manifest", report_root / f"seed_{base_seed}_manifest.json"),
    )


def _family_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for model_id, base_seed in ORDERED_SLOTS:
        for role, relative in _slot_paths(model_id, base_seed):
            path = ROOT / relative
            metadata = path.lstat()
            records.append(
                {
                    "role": role,
                    "path": relative.as_posix(),
                    "bytes": metadata.st_size,
                    "sha256": _sha256(path),
                }
            )
    return records


def _records_sha256(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        records,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _record(path: Path, *, role: str) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.as_posix(),
        "role": role,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def test_patch_identity_and_h_p_r_scopes_are_exact() -> None:
    expected_h = {
        path: ("A" if path in EXPECTED_ADDITIONS else "M")
        for path in EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    }
    expected_p = {path: "A" for path in EXPECTED_P_PATHS}
    expected_r = {
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

    assert patch.PATCH_GATE == "E0-MY"
    assert patch.BASE_COMMIT == P_MX_COMMIT
    assert set(patch.PATCH_PATHS) == EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    assert len(patch.PATCH_PATHS) == 9
    assert patch.PATCH_COMPONENT_GIT_MODES == {
        path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
        for path in EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    }
    assert patch.EXPECTED_COMPANION_INPUT_COUNT == 11
    assert patch.EXPECTED_HISTORICAL_INPUT_COUNT == 4
    assert {
        patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
    } == EXPECTED_P_PATHS

    assert precommit_artifacts.DEFERRED_DVC_H_MY_STAGED_SCOPE == expected_h
    assert patch.ANFIS_ABLATION_H_MY_STAGED_SCOPE == expected_h
    assert patch.ANFIS_ABLATION_H_MY_STAGED_SCOPE == (
        precommit_artifacts.DEFERRED_DVC_H_MY_STAGED_SCOPE
    )
    assert precommit_artifacts.DEFERRED_DVC_P_MY_STAGED_SCOPE == expected_p
    assert precommit_artifacts.ANFIS_ABLATION_R_MY_STAGED_SCOPE == expected_r
    assert len(expected_h) == 9
    assert len(expected_p) == 2
    assert len(expected_r) == 56
    assert list(expected_r.values()).count("A") == 55
    assert list(expected_r.values()).count("M") == 1
    expected_r_mz = {
        **{
            path: "A"
            for path in precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS
        },
        "models.dvc": "M",
    }
    assert precommit_artifacts.ANFIS_ABLATION_R_MZ_STAGED_SCOPE == expected_r_mz
    assert len(expected_r_mz) == 11
    assert precommit_artifacts.DEFERRED_DVC_ACTIVE_STAGING_GATES == frozenset(
        {"H-E0-MZ", "P-E0-MZ"}
    )
    for gate in ("H-E0-MZ", "P-E0-MZ"):
        assert precommit_artifacts.require_active_deferred_dvc_staging_gate(gate) == gate
    for gate in ("H-E0-MY", "P-E0-MY"):
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="closed to exact H-E0-MZ/P-E0-MZ",
        ):
            precommit_artifacts.require_active_deferred_dvc_staging_gate(gate)


def test_registration_inventory_is_separate_exact_and_ordered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory_path = ROOT / "configs/closure_v1/dvc_artifacts_post_lock.yaml"
    inventory = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    assert isinstance(inventory, dict)
    assert len(inventory["artifacts"]) == 23
    records = inventory["anfis_ablation_registration_artifacts"]
    assert isinstance(records, list) and len(records) == 10

    expected_paths = [
        (
            "data/closure_v1/development/anfis_ablation/"
            f"{model_id}/seed_{base_seed}_selection_predictions.parquet"
        )
        for model_id, base_seed in ORDERED_SLOTS
    ]
    assert [record["path"] for record in records] == expected_paths
    assert [
        (record["model_id"], record["base_seed"]) for record in records
    ] == list(ORDERED_SLOTS)
    assert len({record["artifact_id"] for record in records}) == 10
    assert len({record["path"] for record in records}) == 10
    assert all(
        record["type"] == "closure_anfis_ablation_selection_predictions"
        and record["source_id"] == "wqp"
        and record["dvc"] is True
        and record["github_policy"]
        == "pointer_only_keep_manifest_and_lightweight_reports_in_git"
        for record in records
    )
    loaded = precommit_artifacts.load_anfis_ablation_registration_artifacts(
        inventory_path
    )
    assert [artifact.path.as_posix() for artifact in loaded] == expected_paths
    assert [path.as_posix() for path in precommit_artifacts.ANFIS_ABLATION_REGISTRATION_DVC_TARGETS[:-1]] == expected_paths
    assert precommit_artifacts.ANFIS_ABLATION_REGISTRATION_DVC_TARGETS[-1] == Path(
        "models"
    )
    assert patch._dvc_add_commands() == [
        ["dvc", "add", "--no-relink", path]
        for path in (*expected_paths, "models")
    ]
    dvc_configuration = patch._dvc_configuration_contract(ROOT)
    assert dvc_configuration["cache_type"] == "reflink,hardlink,copy"
    assert dvc_configuration["no_relink_required"] is True

    current_payload = inventory_path.read_bytes()
    prefix, marker, artifacts = current_payload.partition(b"\nartifacts:\n")
    assert marker and b"source_id: wqp" in artifacts
    mutated_payload = prefix + marker + artifacts.replace(
        b"source_id: wqp", b"source_id: forged", 1
    )
    synthetic = tmp_path / patch.DVC_INVENTORY_PATH
    synthetic.parent.mkdir(parents=True)
    synthetic.write_bytes(mutated_payload)
    synthetic.chmod(0o644)
    historical = subprocess.run(
        [
            "git",
            "-C",
            ROOT.as_posix(),
            "show",
            f"{P_MX_COMMIT}:{patch.DVC_INVENTORY_PATH.as_posix()}",
        ],
        check=True,
        capture_output=True,
    ).stdout
    monkeypatch.setattr(
        patch,
        "_git_blob_bytes",
        lambda *args, **kwargs: historical,
    )
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationPatchError,
        match="inventory",
    ):
        patch._registration_inventory(tmp_path)


def test_registration_helper_cli_and_lazy_authority_loader_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert set(
        inspect.signature(
            patch.load_effective_anfis_ablation_dvc_registration_patch_authority
        ).parameters
    ) == {"audit_current_unpublished", "verify_remote", "repo_root"}
    assert set(
        inspect.signature(
            patch.load_effective_anfis_ablation_dvc_registration_patch
        ).parameters
    ) == {"audit_current_unpublished", "verify_remote", "repo_root"}
    assert set(
        inspect.signature(
            patch.require_anfis_ablation_dvc_registration_patch_authority
        ).parameters
    ) == {"audit_current_unpublished", "verify_remote", "repo_root"}
    assert set(
        inspect.signature(
            patch._load_effective_anfis_ablation_dvc_registration_patch_during_registration
        ).parameters
    ) == {"transaction_record", "verify_remote", "repo_root"}
    assert set(
        inspect.signature(
            patch.validate_anfis_ablation_dvc_registration_patch_lock_payload
        ).parameters
    ) == {"payload", "allow_registered_state", "repo_root"}
    assert (
        "_load_effective_anfis_ablation_dvc_registration_patch_during_registration"
        not in patch.__all__
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
    valid_environment = {
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
        args, env=valid_environment
    )
    for name in ("HOME", "XDG_CONFIG_HOME", "XDG_CONFIG_DIRS"):
        missing = dict(valid_environment)
        missing.pop(name)
        precommit_artifacts.validate_anfis_ablation_registration_invocation(
            args, env=missing
        )
        overridden = dict(valid_environment)
        overridden[name] = "/tmp/forged-e0-my-config"
        with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
            precommit_artifacts.validate_anfis_ablation_registration_invocation(
                args, env=overridden
            )
    args.allow_unmanaged = True
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="register-anfis-ablation-model-family",
    ):
        precommit_artifacts.validate_anfis_ablation_registration_invocation(
            args, env=valid_environment
        )

    observed: list[dict[str, Any]] = []

    def load(**kwargs: Any) -> dict[str, Any]:
        observed.append(kwargs)
        return {"gate": "E0-MZ", "status": "effective_preflight_passed"}

    monkeypatch.setattr(
        mz_patch,
        "load_effective_anfis_ablation_dvc_registration_adoption_patch_authority",
        load,
    )
    authority = precommit_artifacts._load_effective_anfis_ablation_dvc_registration_authority(
        audit_current_unpublished=False, repo_root=ROOT
    )
    assert authority == {"gate": "E0-MZ", "status": "effective_preflight_passed"}
    assert observed == [
        {
            "audit_current_unpublished": False,
            "verify_remote": True,
            "repo_root": ROOT,
        }
    ]

    repo_root = tmp_path / "index-rollback"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    subprocess.run(["git", "init", "-q"], check=True)
    baseline_models = (
        "outs:\n"
        "- md5: fc60851634c1345cc5dc2c9169be9e1c.dir\n"
        "  size: 124717666\n"
        "  nfiles: 248\n"
        "  hash: md5\n"
        "  path: models\n"
    ).encode("utf-8")
    Path("models.dvc").write_bytes(baseline_models)
    Path("models.dvc").chmod(0o644)
    subprocess.run(["git", "add", "models.dvc"], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=E0-MY Test",
            "-c",
            "user.email=e0-my@example.invalid",
            "commit",
            "-q",
            "-m",
            "baseline",
        ],
        check=True,
    )
    baseline_index = subprocess.run(
        ["git", "ls-files", "-s", "--", "models.dvc"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    transaction = precommit_artifacts._AnfisAblationRegistrationTransaction(
        repo_root=repo_root, manage_git_index=True
    )
    transaction.__enter__()
    transaction.begin_dvc_mutation()
    for payload_path, raw_pointer in zip(
        precommit_artifacts.ANFIS_ABLATION_SELECTION_PREDICTION_PATHS,
        precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS,
        strict=True,
    ):
        pointer = Path(raw_pointer)
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_bytes(f"pointer:{raw_pointer}\n".encode("utf-8"))
        pointer.chmod(0o644)
        transaction.capture_target(Path(payload_path))
    transaction.prepare_models_registration()
    Path("models.dvc").unlink()
    Path("models.dvc").write_bytes(patch._expected_models_dvc_bytes())
    Path("models.dvc").chmod(0o644)
    transaction.capture_target(Path("models"))
    subprocess.run(
        [
            "git",
            "add",
            "-A",
            "--",
            *sorted(precommit_artifacts.ANFIS_ABLATION_R_MZ_STAGED_SCOPE),
        ],
        check=True,
    )
    transaction.mark_staging_owned()
    assert subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines() == sorted(
        precommit_artifacts.ANFIS_ABLATION_R_MZ_STAGED_SCOPE
    )

    synthetic_failure = RuntimeError("post-git-add failure")
    transaction.__exit__(
        type(synthetic_failure), synthetic_failure, synthetic_failure.__traceback__
    )
    assert subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout == ""
    assert subprocess.run(
        [
            "git",
            "ls-files",
            "-s",
            "--",
            *sorted(precommit_artifacts.ANFIS_ABLATION_R_MZ_STAGED_SCOPE),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout == baseline_index
    assert Path("models.dvc").read_bytes() == baseline_models
    assert Path("models.dvc").stat().st_nlink == 1
    assert not any(
        Path(path).exists()
        for path in precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS
    )
    assert not Path(
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_GUARD
    ).exists()
    assert not Path(precommit_artifacts.ANFIS_ABLATION_MODELS_DVC_BACKUP).exists()

    backup = Path("models.dvc.hardlink")
    os.link(Path("models.dvc"), backup)
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationPatchError,
        match=r"not a regular 0644 file: models\.dvc",
    ):
        patch._validate_registered_state(
            {
                "expected_registration": {
                    "pointers": [],
                    "models_dvc": {
                        "bytes": len(baseline_models),
                        "sha256": hashlib.sha256(baseline_models).hexdigest(),
                    },
                }
            },
            repo_root=repo_root,
        )
    backup.unlink()


def test_complete_family_is_exactly_80_bound_regular_finals() -> None:
    records = _family_records()
    assert len(records) == 80
    assert sum(record["bytes"] for record in records) == 3_790_938
    assert _records_sha256(records) == FAMILY_RECORDS_SHA256
    assert sum(record["role"] in {"model", "checkpoint"} for record in records) == 20
    assert sum(record["role"] == "selection_predictions" for record in records) == 10
    assert sum(
        record["role"]
        in {
            "preprocessor",
            "training_curve",
            "selection_metrics",
            "report",
            "manifest",
        }
        for record in records
    ) == 50

    expected_paths = {record["path"] for record in records}
    actual_paths: set[str] = set()
    for root in (
        ROOT / "models/closure_v1/anfis_ablation",
        ROOT / "reports/closure_v1/02_models/A0",
        ROOT / "reports/closure_v1/02_models/A1",
        ROOT / "data/closure_v1/development/anfis_ablation",
    ):
        actual_paths.update(
            path.relative_to(ROOT).as_posix()
            for path in root.rglob("*")
            if path.is_file() or path.is_symlink()
        )
    pointer_paths = set(precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS)
    registration_metadata = actual_paths - expected_paths
    assert registration_metadata in (set(), pointer_paths)
    assert actual_paths - registration_metadata == expected_paths

    by_path = {record["path"]: record for record in records}
    for record in records:
        path = ROOT / record["path"]
        metadata = path.lstat()
        assert stat.S_ISREG(metadata.st_mode)
        assert stat.S_IMODE(metadata.st_mode) == 0o644
        assert metadata.st_nlink == 1
        assert not path.is_symlink()

    for model_id, base_seed in ORDERED_SLOTS:
        slot = dict(_slot_paths(model_id, base_seed))
        manifest = json.loads((ROOT / slot["manifest"]).read_text(encoding="utf-8"))
        assert manifest["manifest_version"] == "closure_anfis_ablation_model_manifest_v1"
        assert manifest["status"] == "completed"
        assert manifest["slot_status"] == "available"
        assert manifest["fit_status"] == "passed"
        assert manifest["model_id"] == model_id
        assert manifest["base_seed"] == base_seed
        assert manifest["future_outcomes_accessed"] is False
        assert manifest["calibration_authorized"] is False
        assert manifest["evaluation_authorized"] is False
        assert manifest["e0_m_authorized"] is False
        assert manifest["e0_u_authorized"] is False
        assert manifest["dvc_command_executed"] is False
        assert manifest["completion_marker_written_last"] is True
        expected_outputs = [by_path[path.as_posix()] for role, path in _slot_paths(model_id, base_seed) if role != "manifest"]
        assert manifest["outputs"] == expected_outputs


def test_registration_namespace_is_one_exact_pre_or_post_state(
    tmp_path: Path,
) -> None:
    finals = [path for slot in ORDERED_SLOTS for _, path in _slot_paths(*slot)]
    temporaries = [Path(f"{path.as_posix()}.tmp") for path in finals]
    pointers = [
        Path(f"{path}.dvc")
        for path in precommit_artifacts.ANFIS_ABLATION_SELECTION_PREDICTION_PATHS
    ]
    pointer_temporaries = [Path(f"{path.as_posix()}.tmp") for path in pointers]
    guards = [
        Path(f"tmp/closure_v1_anfis_ablation_training/{model_id}_seed_{base_seed}.guard")
        for model_id, base_seed in ORDERED_SLOTS
    ]
    assert not [
        path.as_posix()
        for path in (*temporaries, *pointer_temporaries, *guards)
        if (ROOT / path).exists() or (ROOT / path).is_symlink()
    ]
    present_pointers = [
        path for path in pointers if (ROOT / path).exists() or (ROOT / path).is_symlink()
    ]
    assert present_pointers in ([], pointers)
    registered = present_pointers == pointers
    if registered:
        for payload_path, pointer_path in zip(
            precommit_artifacts.ANFIS_ABLATION_SELECTION_PREDICTION_PATHS,
            pointers,
            strict=True,
        ):
            physical = ROOT / pointer_path
            metadata = physical.lstat()
            assert stat.S_ISREG(metadata.st_mode)
            assert stat.S_IMODE(metadata.st_mode) == 0o644
            assert metadata.st_nlink == 1
            assert physical.read_bytes() == patch._expected_pointer_bytes(
                Path(payload_path), repo_root=ROOT
            )
    patch._validate_family_namespace(registered=registered, repo_root=ROOT)

    models_dvc = ROOT / "models.dvc"
    metadata = models_dvc.lstat()
    assert stat.S_ISREG(metadata.st_mode)
    assert stat.S_IMODE(metadata.st_mode) == 0o644
    assert metadata.st_nlink == 1
    assert metadata.st_size == 109
    if registered:
        assert _sha256(models_dvc) == patch.EXPECTED_MODELS_DVC_SHA256
        assert models_dvc.read_bytes() == patch._expected_models_dvc_bytes()
    else:
        assert _sha256(models_dvc) == MODELS_DVC_SHA256
        assert models_dvc.read_text(encoding="utf-8") == (
            "outs:\n"
            "- md5: fc60851634c1345cc5dc2c9169be9e1c.dir\n"
            "  size: 124717666\n"
            "  nfiles: 248\n"
            "  hash: md5\n"
            "  path: models\n"
        )

    synthetic = tmp_path / "closed-namespace"
    synthetic.mkdir()
    for path in finals:
        physical = synthetic / path
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(b"")
        physical.chmod(0o644)
    patch._validate_family_namespace(registered=False, repo_root=synthetic)

    for forbidden in patch._forbidden_family_namespace_paths():
        physical = synthetic / forbidden
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.symlink_to("absent-e0-my-target")
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationPatchError,
            match="namespace|symlink|nonregular|foreign",
        ):
            patch._validate_family_namespace(
                registered=False, repo_root=synthetic
            )
        physical.unlink()

    for extra in (
        Path("models/closure_v1/anfis_ablation/A0/ignored-extra.bin"),
        Path("reports/closure_v1/02_models/A1/ignored-extra.bin"),
        Path(
            "data/closure_v1/development/anfis_ablation/"
            "A0/ignored-extra.bin"
        ),
    ):
        physical = synthetic / extra
        physical.write_bytes(b"foreign\n")
        physical.chmod(0o644)
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationPatchError,
            match="foreign|unexpected",
        ):
            patch._validate_family_namespace(
                registered=False, repo_root=synthetic
            )
        physical.unlink()

    symlinked_final = synthetic / finals[0]
    symlinked_final.unlink()
    symlinked_final.symlink_to("absent-final")
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationPatchError,
        match="symlink|nonregular",
    ):
        patch._validate_family_namespace(registered=False, repo_root=synthetic)
    symlinked_final.unlink()
    symlinked_final.write_bytes(b"")
    symlinked_final.chmod(0o644)

    for pointer in pointers:
        physical = synthetic / pointer
        physical.write_bytes(b"pointer\n")
        physical.chmod(0o644)
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationPatchError,
        match="foreign|namespace",
    ):
        patch._validate_family_namespace(registered=False, repo_root=synthetic)
    patch._validate_family_namespace(registered=True, repo_root=synthetic)

    guard_payload = b"E0-MY exact ANFIS-ablation DVC registration\n"
    coordination_payloads = {
        patch.REGISTRATION_GUARD_PATH: (0o600, guard_payload),
        patch.REGISTRATION_MODELS_BYTES_BACKUP_PATH: (
            0o600,
            patch._base_models_dvc_bytes(),
        ),
        patch.REGISTRATION_MODELS_BACKUP_PATH: (
            0o644,
            patch._base_models_dvc_bytes(),
        ),
    }
    for path, (mode, payload) in coordination_payloads.items():
        physical = synthetic / path
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(payload)
        physical.chmod(mode)
    for path in (
        patch.REGISTRATION_DVC_GLOBAL_CONFIG_PATH,
        patch.REGISTRATION_DVC_SYSTEM_CONFIG_PATH,
    ):
        physical = synthetic / path
        physical.mkdir(mode=0o700)
        physical.chmod(0o700)
    transaction_record = {
        "mode": "atomic_replace",
        "guard": patch._coordination_identity_record(
            patch.REGISTRATION_GUARD_PATH,
            expected_mode=0o600,
            expected_payload=guard_payload,
            repo_root=synthetic,
        ),
        "bytes_backup": patch._coordination_identity_record(
            patch.REGISTRATION_MODELS_BYTES_BACKUP_PATH,
            expected_mode=0o600,
            expected_payload=patch._base_models_dvc_bytes(),
            repo_root=synthetic,
        ),
        "anchor": patch._coordination_identity_record(
            patch.REGISTRATION_MODELS_BACKUP_PATH,
            expected_mode=0o644,
            expected_payload=patch._base_models_dvc_bytes(),
            repo_root=synthetic,
        ),
        "global_config_dir": patch._coordination_directory_record(
            patch.REGISTRATION_DVC_GLOBAL_CONFIG_PATH, repo_root=synthetic
        ),
        "system_config_dir": patch._coordination_directory_record(
            patch.REGISTRATION_DVC_SYSTEM_CONFIG_PATH, repo_root=synthetic
        ),
    }
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationPatchError,
        match="namespace",
    ):
        patch._validate_family_namespace(registered=True, repo_root=synthetic)
    patch._validate_family_namespace(
        registered=True,
        repo_root=synthetic,
        registration_transaction=transaction_record,
    )
    forged_record = json.loads(json.dumps(transaction_record))
    forged_record["guard"]["inode"] += 1
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationPatchError,
        match="record",
    ):
        patch._validate_family_namespace(
            registered=True,
            repo_root=synthetic,
            registration_transaction=forged_record,
        )
    for record_name in ("guard", "global_config_dir"):
        for field in ("mtime_ns", "ctime_ns"):
            typed_drift = json.loads(json.dumps(transaction_record))
            typed_drift[record_name][field] = float(
                typed_drift[record_name][field]
            )
            with pytest.raises(
                patch.AnfisAblationDvcRegistrationPatchError,
                match="record",
            ):
                patch._validate_family_namespace(
                    registered=True,
                    repo_root=synthetic,
                    registration_transaction=typed_drift,
                )

    (synthetic / patch.REGISTRATION_MODELS_BACKUP_PATH).unlink()
    in_place_record: dict[str, Any] = dict(transaction_record)
    in_place_record["mode"] = "in_place"
    in_place_record["anchor"] = None
    patch._validate_family_namespace(
        registered=True,
        repo_root=synthetic,
        registration_transaction=in_place_record,
    )


def test_new_lock_is_one_report_and_only_companion_is_a_manifest() -> None:
    lock = patch.DEFAULT_PATCH_LOCK_PATH
    companion = patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    assert "manifest" not in lock.name
    assert companion.name.endswith("_lock_manifest.json")
    assert precommit_artifacts.is_experiment_manifest_path(lock) is False
    assert precommit_artifacts.is_report_artifact_path(lock) is True
    assert precommit_artifacts.is_experiment_manifest_path(companion) is True
    assert precommit_artifacts.is_report_artifact_path(companion) is False


def test_schema_closes_family_inventory_companion_and_registration_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = json.loads(
        (ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text(encoding="utf-8")
    )
    assert schema["properties"]["gate"]["const"] == "E0-MY"
    definitions = schema["$defs"]
    assert definitions["scope4m5a"]["properties"] == {
        "added": {"type": "integer", "const": 5},
        "modified": {"type": "integer", "const": 4},
        "deleted": {"type": "integer", "const": 0},
    }
    assert definitions["hPatch"]["properties"]["component_count"]["const"] == 9
    family = definitions["completedFamily"]["properties"]
    assert family["slot_count"]["const"] == 10
    assert family["final_count"]["const"] == 80
    assert family["light_final_count"]["const"] == 50
    assert family["heavy_final_count"]["const"] == 30
    assert family["tracked_light_count"]["const"] == 5
    assert family["untracked_light_count"]["const"] == 45
    assert family["records_sha256"]["const"] == FAMILY_RECORDS_SHA256
    inventory = definitions["artifactInventory"]["properties"]
    assert inventory["general_artifact_count"]["const"] == 23
    assert inventory["registration_artifact_count"]["const"] == 10
    companion = definitions["companionContract"]["properties"]
    assert companion["physical_input_count"]["const"] == 11
    assert companion["historical_input_count"]["const"] == 4
    assert companion["output_count"]["const"] == 1
    registration = definitions["registrationGitScope"]["properties"]
    assert registration["added"]["const"] == 55
    assert registration["modified"]["const"] == 1
    assert registration["deleted"]["const"] == 0
    assert registration["path_count"]["const"] == 56
    assert definitions["focusedTests"]["properties"]["test_count"]["const"] == 116
    plan = definitions["registrationPlan"]
    assert {"dvc_add_commands", "dvc_configuration"} <= set(plan["required"])
    dvc_configuration = definitions["dvcConfiguration"]["properties"]
    assert dvc_configuration["cache_type"]["const"] == "reflink,hardlink,copy"
    assert dvc_configuration["no_relink_required"]["const"] is True

    for keyword, keyword_value in (("default", {}), ("examples", [])):
        unsupported_schema = json.loads(json.dumps(schema))
        unsupported_schema[keyword] = keyword_value
        with monkeypatch.context() as schema_context:
            schema_context.setattr(
                patch,
                "_load_json",
                lambda *args, **kwargs: unsupported_schema,
            )
            with pytest.raises(
                patch.AnfisAblationDvcRegistrationPatchError,
                match=keyword,
            ):
                patch.preflight_anfis_ablation_dvc_registration_patch_schema(
                    repo_root=ROOT
                )

    def command_evidence(command: tuple[str, ...], stdout: str) -> dict[str, Any]:
        return {
            "command": list(command),
            "returncode": 0,
            "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(b"").hexdigest(),
            "stdout_line_count": len(stdout.splitlines()),
            "stderr_line_count": 0,
        }

    valid_type_check = command_evidence(
        patch.TYPE_CHECK_COMMAND, "All checks passed!\n"
    )
    for field in ("returncode", "stdout_line_count", "stderr_line_count"):
        for invalid in (False, float(valid_type_check[field])):
            invalid_evidence = dict(valid_type_check)
            invalid_evidence[field] = invalid
            with pytest.raises(patch.AnfisAblationDvcRegistrationPatchError):
                patch._validate_command_evidence(
                    invalid_evidence,
                    expected_command=patch.TYPE_CHECK_COMMAND,
                    context="synthetic exact-integer regression",
                    exact_stdout="All checks passed!\n",
                )

    focused_stdout = f"{patch.FOCUSED_TEST_COUNT} passed in 1.00s\n"
    focused = {
        **command_evidence(patch.FOCUSED_TEST_COMMAND, focused_stdout),
        "stdout_text": focused_stdout,
        "test_count": patch.FOCUSED_TEST_COUNT,
        "warnings": 0,
        "skipped": 0,
        "deselected": 0,
    }
    verification = {
        "schema_preflight": (
            patch.preflight_anfis_ablation_dvc_registration_patch_schema(
                repo_root=ROOT
            )
        ),
        "type_check": valid_type_check,
        "focused_tests": focused,
        "poetry_check": command_evidence(patch.POETRY_CHECK_COMMAND, "All set!\n"),
        "publication_guard": command_evidence(
            patch.PUBLICATION_GUARD_COMMAND,
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n",
        ),
        "diff_check": command_evidence(patch.DIFF_CHECK_COMMAND, ""),
        "family_semantic_audit": {
            "status": "passed",
            "slot_count": 10,
            "dvc_command_executed": False,
            "future_outcomes_accessed": False,
            "writes_performed": False,
        },
        "execution_boundaries": {
            "dvc_commands_run": False,
            "model_fit_run": False,
            "calibration_targets_read": False,
            "evaluation_run": False,
            "e0_m_run": False,
            "e0_u_run": False,
            "outcome_paths_opened": False,
            "scientific_network_run": False,
            "pytest_environment": dict(patch.FOCUSED_PYTEST_ENVIRONMENT),
        },
    }
    patch._validate_verification(verification, repo_root=ROOT)
    for field in ("test_count", "warnings", "skipped", "deselected"):
        for invalid in (False, float(focused[field])):
            invalid_verification = json.loads(json.dumps(verification))
            invalid_verification["focused_tests"][field] = invalid
            with pytest.raises(patch.AnfisAblationDvcRegistrationPatchError):
                patch._validate_verification(invalid_verification, repo_root=ROOT)
    for invalid in (False, 10.0):
        invalid_verification = json.loads(json.dumps(verification))
        invalid_verification["family_semantic_audit"]["slot_count"] = invalid
        with pytest.raises(patch.AnfisAblationDvcRegistrationPatchError):
            patch._validate_verification(invalid_verification, repo_root=ROOT)


def test_generic_precommit_manifest_dialect_is_one_one_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    lock = patch.DEFAULT_PATCH_LOCK_PATH
    companion = patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    script = Path("src/synthetic_e0_my_locker.py")
    source = Path("configs/synthetic_e0_my_input.json")
    for path in (lock, companion, script, source):
        path.parent.mkdir(parents=True, exist_ok=True)
    script.write_bytes(b"# synthetic E0-MY locker\n")
    source.write_bytes(b"{}\n")
    lock.write_bytes(b'{"gate":"E0-MY","status":"locked_unpublished"}\n')
    companion.write_text(
        json.dumps(
            {
                "manifest_version": "synthetic_e0_my_lock_manifest_v1",
                "status": "completed",
                "gate": "E0-MY",
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


def test_check_only_is_a_non_writing_family_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = {"status": "schema_preflight_passed"}
    repository = {"head": "f" * 40}
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_dvc_registration_patch_schema",
        lambda: schema,
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_dvc_registration_patch_prelock_state",
        lambda **kwargs: {
            "repository": repository,
            "h_patch": {"component_count": 9},
            "companion_contract": {
                "physical_input_count": 11,
                "historical_input_count": 4,
            },
            "completed_family": {
                "slot_count": 10,
                "final_count": 80,
                "light_final_count": 50,
                "heavy_final_count": 30,
            },
            "artifact_inventory": {
                "registration_artifact_count": 10,
                "general_artifact_count": 23,
            },
            "prelock": {"selection_pointer_present_count": 0},
        },
    )
    result = locker.check_only()
    assert result == {
        "status": "ready_to_lock",
        "gate": "E0-MY",
        "schema_preflight": schema,
        "repository": repository,
        "component_count": 9,
        "physical_input_count": 11,
        "historical_input_count": 4,
        "completed_slot_count": 10,
        "family_final_count": 80,
        "lightweight_final_count": 50,
        "heavy_final_count": 30,
        "registration_artifact_count": 10,
        "general_artifact_count": 23,
        "prediction_pointer_count": 0,
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


def test_execute_lock_and_effective_checks_delegate_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def publish(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        calls.append(("publish", kwargs))
        return {"gate": "E0-MY"}, {"status": "completed"}

    def load(**kwargs: Any) -> dict[str, Any]:
        calls.append(("load", kwargs))
        return {"gate": "E0-MY", "status": "effective"}

    monkeypatch.setattr(
        patch,
        "publish_anfis_ablation_dvc_registration_patch_lock_bundle",
        publish,
    )
    monkeypatch.setattr(
        patch,
        "load_effective_anfis_ablation_dvc_registration_patch_authority",
        load,
    )
    locked = locker.execute_lock()
    effective = locker.check_effective()
    assert calls == [("publish", {}), ("load", {"verify_remote": True})]
    assert locked["status"] == "locked_unpublished"
    assert locked["gate"] == "E0-MY"
    assert locked["lock"] == {"gate": "E0-MY"}
    assert locked["companion"] == {"status": "completed"}
    assert effective == {"gate": "E0-MY", "status": "effective"}


def test_locker_cli_is_closed_and_translates_only_patch_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    assert locker.parse_args(["--execute-lock"]).execute_lock is True
    assert locker.parse_args(["--check-effective"]).check_effective is True
    for invalid in (
        [],
        ["--check-only", "--execute-lock"],
        ["--check-effective", "--model-id", "A0"],
    ):
        with pytest.raises(SystemExit):
            locker.parse_args(invalid)
    capsys.readouterr()

    monkeypatch.setattr(
        locker,
        "check_only",
        lambda: (_ for _ in ()).throw(
            patch.AnfisAblationDvcRegistrationPatchError("closed")
        ),
    )
    assert locker.main(["--check-only"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "closed\n"


def test_locker_and_public_publisher_have_no_mutating_payload_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert set(inspect.signature(patch.publish_anfis_ablation_dvc_registration_patch_lock_bundle).parameters) == {"repo_root"}
    assert set(inspect.signature(locker.execute_lock).parameters) == set()
    locker_source = inspect.getsource(locker)
    for forbidden in (
        "train_closure_anfis_ablation.py",
        "audit_closure_anfis_ablation_model_bundle.py",
        "dvc add",
        "dvc push",
        "read_parquet",
        "torch.load",
    ):
        assert forbidden not in locker_source
    patch_source = inspect.getsource(patch)
    for required in (
        "_publish_bytes_no_clobber",
        "_acquire_publication_guard",
        "_release_publication_guard",
        "_rollback_owned_output",
    ):
        assert required in patch_source

    repo_root = tmp_path / "p-git-binding"
    repo_root.mkdir()
    physical_payloads = {
        patch.DEFAULT_PATCH_LOCK_PATH: b"lock-git-bytes\n",
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH: b"companion-git-bytes\n",
    }
    for path, payload in physical_payloads.items():
        physical = repo_root / path
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(payload)
        physical.chmod(0o644)
    h_head = "a" * 40
    p_head = "b" * 40
    monkeypatch.setattr(
        patch,
        "_git_head",
        lambda repo_root, ref="HEAD": p_head,
    )
    monkeypatch.setattr(patch, "_live_remote_main_head", lambda repo_root: p_head)
    monkeypatch.setattr(
        patch, "_single_parent", lambda *args, **kwargs: h_head
    )
    monkeypatch.setattr(
        patch,
        "_git_scope",
        lambda *args, **kwargs: {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "paths": sorted(path.as_posix() for path in physical_payloads),
        },
    )
    monkeypatch.setattr(patch, "_git", lambda *args, **kwargs: "main\n")
    monkeypatch.setattr(patch.mx, "_require_git_modes", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        patch,
        "_git_blob_bytes",
        lambda repo_root, commit, path: physical_payloads[path],
    )
    assert patch._validate_p_publication(
        {"repository": {"head": h_head}}, repo_root=repo_root
    ) == {"h_patch_head": h_head, "p_patch_head": p_head, "remote_head": p_head}
    (repo_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).write_bytes(
        b"coherent-local-drift\n"
    )
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationPatchError,
        match="physical bytes differ from Git",
    ):
        patch._validate_p_publication(
            {"repository": {"head": h_head}}, repo_root=repo_root
        )


def _install_synthetic_publisher(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for parent in (
        patch.DEFAULT_PATCH_LOCK_PATH.parent,
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.parent,
        patch.LOCKER_GUARD_PATH.parent,
    ):
        (repo_root / parent).mkdir(parents=True, exist_ok=True)
    prelock = {"repository": {"head": "h"}, "prelock": {"writes_performed": False}}
    payload = {"gate": "E0-MY", "status": "locked_unpublished"}
    companion = {
        "manifest_version": "synthetic_e0_my_lock_manifest_v1",
        "status": "completed",
        "completion_marker_written_last": True,
    }
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_dvc_registration_patch_prelock_state",
        lambda **kwargs: prelock,
    )
    synthetic_snapshot = ({"path": "synthetic/final.bin", "inode": 1},)
    monkeypatch.setattr(
        patch,
        "_family_physical_snapshot",
        lambda repo_root: synthetic_snapshot,
    )
    monkeypatch.setattr(
        patch,
        "_require_family_physical_snapshot",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        patch,
        "run_anfis_ablation_dvc_registration_patch_verification",
        lambda **kwargs: {"status": "passed"},
    )
    monkeypatch.setattr(
        patch,
        "build_anfis_ablation_dvc_registration_patch_lock_payload",
        lambda *args, **kwargs: payload,
    )
    monkeypatch.setattr(
        patch,
        "validate_anfis_ablation_dvc_registration_patch_lock_payload",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda *args, **kwargs: companion,
    )


def test_publisher_is_no_clobber_and_rolls_back_only_owned_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as transaction:
        repo_root = tmp_path / "rollback"
        repo_root.mkdir()
        _install_synthetic_publisher(repo_root, transaction)
        real_publish = patch.mt._publish_bytes_no_clobber

        def fail_companion(path: Path, payload: bytes, *, repo_root: Path) -> Any:
            if path == patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH:
                raise patch.mt.AnfisAblationTrainingDevelopmentPatchError(
                    "synthetic companion failure"
                )
            return real_publish(path, payload, repo_root=repo_root)

        transaction.setattr(patch.mt, "_publish_bytes_no_clobber", fail_companion)
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationPatchError,
            match="synthetic companion failure",
        ):
            patch.publish_anfis_ablation_dvc_registration_patch_lock_bundle(
                repo_root=repo_root
            )
        for relative in (
            patch.DEFAULT_PATCH_LOCK_PATH,
            patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            patch._temporary_path(patch.DEFAULT_PATCH_LOCK_PATH),
            patch._temporary_path(patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
            patch.LOCKER_GUARD_PATH,
        ):
            assert not (repo_root / relative).exists()

    with monkeypatch.context() as no_clobber:
        repo_root = tmp_path / "foreign"
        repo_root.mkdir()
        _install_synthetic_publisher(repo_root, no_clobber)
        foreign = repo_root / patch.DEFAULT_PATCH_LOCK_PATH
        foreign.write_bytes(b"foreign-authority\n")
        foreign.chmod(0o644)
        before = foreign.stat()
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationPatchError,
            match="lock namespace is occupied",
        ):
            patch.publish_anfis_ablation_dvc_registration_patch_lock_bundle(
                repo_root=repo_root
            )
        after = foreign.stat()
        assert foreign.read_bytes() == b"foreign-authority\n"
        assert (after.st_dev, after.st_ino, after.st_mtime_ns) == (
            before.st_dev,
            before.st_ino,
            before.st_mtime_ns,
        )
        assert not (repo_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
        assert not (repo_root / patch.LOCKER_GUARD_PATH).exists()


def test_publisher_revalidates_state_under_exclusive_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "guarded-drift"
    repo_root.mkdir()
    _install_synthetic_publisher(repo_root, monkeypatch)
    baseline = {"repository": {"head": "h"}, "prelock": {"writes_performed": False}}
    calls = 0

    def collect(**kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 3:
            return {"repository": {"head": "drift"}}
        return baseline

    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_dvc_registration_patch_prelock_state",
        collect,
    )
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationPatchError,
        match="guarded prelock state drifted",
    ):
        patch.publish_anfis_ablation_dvc_registration_patch_lock_bundle(
            repo_root=repo_root
        )
    assert calls == 3
    for relative in (
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        patch.LOCKER_GUARD_PATH,
    ):
        assert not (repo_root / relative).exists()


def test_publisher_rolls_back_if_family_drifts_after_lock_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "post-lock-drift"
    repo_root.mkdir()
    _install_synthetic_publisher(repo_root, monkeypatch)
    drifted = False

    real_publish = patch.mt._publish_bytes_no_clobber

    def publish_then_drift(
        path: Path, payload: bytes, *, repo_root: Path
    ) -> Any:
        nonlocal drifted
        output = real_publish(path, payload, repo_root=repo_root)
        if path == patch.DEFAULT_PATCH_LOCK_PATH:
            drifted = True
        return output

    def require_snapshot(
        expected: Any, *, repo_root: Path, context: str
    ) -> None:
        del expected, repo_root
        if drifted:
            raise patch.AnfisAblationDvcRegistrationPatchError(
                f"E0-MY family physical snapshot drifted {context}"
            )

    monkeypatch.setattr(
        patch, "_require_family_physical_snapshot", require_snapshot
    )
    monkeypatch.setattr(patch.mt, "_publish_bytes_no_clobber", publish_then_drift)
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationPatchError,
        match="after lock publication",
    ):
        patch.publish_anfis_ablation_dvc_registration_patch_lock_bundle(
            repo_root=repo_root
        )
    for relative in (
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        patch._temporary_path(patch.DEFAULT_PATCH_LOCK_PATH),
        patch._temporary_path(patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        patch.LOCKER_GUARD_PATH,
    ):
        assert not (repo_root / relative).exists()


def test_document_closes_registration_and_external_barriers() -> None:
    document = (
        ROOT
        / "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_PATCH_1.md"
    ).read_text(encoding="utf-8")
    for token in (
        P_MX_COMMIT,
        "`4M+5A`",
        "`55A+1M`",
        "`80` regular",
        "`50` lightweight",
        "`20` model/checkpoint",
        "`10` prediction",
        FAMILY_RECORDS_SHA256,
        "anfis_ablation_registration_artifacts",
        "exactly `23` records",
        "--register-anfis-ablation-model-family --no-push",
        "dvc add --no-relink <target>",
        patch.DVC_CONFIG_SHA256,
        patch.DVC_CONFIG_LOCAL_SHA256,
        "before its Git commit and publication",
        "two separately visible",
        "DVC pushes",
    ):
        assert token in document
    assert patch.DEFAULT_PATCH_LOCK_PATH.as_posix() in document
    assert patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix() in document
