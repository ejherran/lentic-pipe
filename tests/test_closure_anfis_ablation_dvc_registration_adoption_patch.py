from __future__ import annotations

import hashlib
import inspect
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.data import prepare_commit_artifacts as precommit_artifacts
from src.experiments import (
    closure_anfis_ablation_dvc_registration_adoption_patch as patch,
)
from src.experiments import (
    closure_anfis_ablation_dvc_registration_namespace_patch as mzb_patch,
)
from src.experiments import closure_anfis_ablation_dvc_registration_patch as my
from src.experiments import (
    lock_closure_anfis_ablation_dvc_registration_adoption_patch as locker,
)


ROOT = Path(__file__).resolve().parents[1]
P_MX_COMMIT = "c73b8ebe11d942631d24e43b0eac2f4b2e72e400"
H_MY_COMMIT = "af233a89e22ce380f7b1f2094cdf4a92eb95b83d"
ADOPTED_LIGHT_COMMIT = "2f0643ab6f634fdcce71f0ee0d847c448d2c61f5"
FAMILY_RECORDS_SHA256 = (
    "e625add8f8af1746f7deda9ff13a84a4d4f4c27b47e3b6312922db419508dd8e"
)
EXPECTED_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_dvc_registration_adoption_patch_lock.schema.json",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_ADOPTION_PATCH_1.md",
    "src/experiments/closure_anfis_ablation_dvc_registration_adoption_patch.py",
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_adoption_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py",
}
EXPECTED_MODIFICATIONS = {
    "src/data/prepare_commit_artifacts.py",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py",
    "tests/test_closure_anfis_ablation_model_publication_patch.py",
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(path: Path, *, role: str) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.as_posix(),
        "role": role,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def test_patch_identity_history_and_h_p_r_scopes_are_exact() -> None:
    expected_h = {
        path: ("A" if path in EXPECTED_ADDITIONS else "M")
        for path in EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    }
    expected_p = {
        patch.DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
    }
    expected_r = {
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
    historical_mza_p = {
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_order_patch_lock.json": "A",
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_order_patch_lock_manifest.json": "A",
    }
    current_h = {
        path: ("A" if path in EXPECTED_MZB_ADDITIONS else "M")
        for path in EXPECTED_MZB_ADDITIONS | EXPECTED_MZB_MODIFICATIONS
    }
    current_p = {
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_namespace_patch_lock.json": "A",
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_namespace_patch_lock_manifest.json": "A",
    }

    assert patch.PATCH_GATE == "E0-MZ"
    assert patch.P_MX_COMMIT == P_MX_COMMIT
    assert patch.H_MY_COMMIT == H_MY_COMMIT
    assert patch.ADOPTED_LIGHT_COMMIT == ADOPTED_LIGHT_COMMIT
    assert patch.BASE_COMMIT == ADOPTED_LIGHT_COMMIT
    assert set(patch.PATCH_ADDED_PATHS) == EXPECTED_ADDITIONS
    assert set(patch.PATCH_MODIFIED_PATHS) == EXPECTED_MODIFICATIONS
    assert set(patch.PATCH_PATHS) == EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    assert len(patch.PATCH_PATHS) == 9
    assert patch.PATCH_COMPONENT_GIT_MODES == {
        path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
        for path in patch.PATCH_PATHS
    }
    assert patch.ANFIS_ABLATION_H_MZ_STAGED_SCOPE == expected_h
    assert patch.ANFIS_ABLATION_P_MZ_STAGED_SCOPE == expected_p
    assert patch.ANFIS_ABLATION_R_MZ_STAGED_SCOPE == expected_r
    assert precommit_artifacts.DEFERRED_DVC_H_MZ_STAGED_SCOPE == expected_h
    assert precommit_artifacts.DEFERRED_DVC_P_MZ_STAGED_SCOPE == expected_p
    assert precommit_artifacts.ANFIS_ABLATION_R_MZ_STAGED_SCOPE == expected_r
    assert precommit_artifacts.DEFERRED_DVC_H_MZA_STAGED_SCOPE == historical_mza_h
    assert precommit_artifacts.DEFERRED_DVC_P_MZA_STAGED_SCOPE == historical_mza_p
    assert precommit_artifacts.ANFIS_ABLATION_R_MZA_STAGED_SCOPE == expected_r
    assert precommit_artifacts.DEFERRED_DVC_H_MZB_STAGED_SCOPE == current_h
    assert precommit_artifacts.DEFERRED_DVC_P_MZB_STAGED_SCOPE == current_p
    assert precommit_artifacts.ANFIS_ABLATION_R_MZB_STAGED_SCOPE == expected_r
    assert len(expected_h) == 9
    assert len(expected_p) == 2
    assert len(expected_r) == 11
    assert list(expected_r.values()).count("A") == 10
    assert list(expected_r.values()).count("M") == 1
    assert precommit_artifacts.DEFERRED_DVC_ACTIVE_STAGING_GATES == frozenset(
        {"H-E0-MZB", "P-E0-MZB"}
    )
    assert len(historical_mza_h) == 10
    assert len(historical_mza_p) == 2
    assert len(current_h) == 11
    assert len(current_p) == 2
    for gate in ("H-E0-MZB", "P-E0-MZB"):
        assert precommit_artifacts.require_active_deferred_dvc_staging_gate(gate) == gate
    for gate in ("H-E0-MZ", "P-E0-MZ", "H-E0-MZA", "P-E0-MZA"):
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="closed to exact H-E0-MZB/P-E0-MZB",
        ):
            precommit_artifacts.require_active_deferred_dvc_staging_gate(gate)


def test_historical_my_partition_and_adopted_light_commit_are_exact() -> None:
    history = patch._historical_h_my_authority(ROOT)
    adopted = patch._adopted_light_publication(ROOT)

    assert history["gate"] == "E0-MY"
    assert history["head"] == H_MY_COMMIT
    assert history["parent"] == P_MX_COMMIT
    assert history["scope"] == {"added": 5, "modified": 4, "deleted": 0}
    assert history["paths"] == list(my.PATCH_PATHS)
    assert history["preserved_component_count"] == 5
    assert history["superseded_component_count"] == 4
    assert {record["path"] for record in history["preserved_components"]} == set(
        patch.PRESERVED_MY_PATHS
    )
    assert {record["path"] for record in history["superseded_components"]} == set(
        patch.SUPERSEDED_MY_PATHS
    )
    assert adopted["commit"] == ADOPTED_LIGHT_COMMIT
    assert adopted["parent"] == H_MY_COMMIT
    assert adopted["scope"] == {"added": 45, "modified": 0, "deleted": 0}
    assert adopted["path_count"] == 45
    assert adopted["paths"] == list(patch.ADOPTED_LIGHT_PATHS)
    assert len(adopted["records"]) == 45
    assert adopted["is_valid_r_my"] is False
    assert adopted["adoption_only"] is True


def test_companion_physical_and_historical_partitions_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    history = patch._historical_h_my_authority(ROOT)
    base_mx = patch._base_mx_authority(ROOT)
    h_components = [
        {"path": path, "role": patch.PATCH_COMPONENT_ROLES[path]}
        for path in patch.PATCH_PATHS
    ]
    physical = patch._companion_physical_inputs(
        h_components=h_components,
        base_mx=base_mx,
        historical_h_my=history,
    )
    historical = patch._historical_inputs(ROOT)

    assert len(physical) == patch.EXPECTED_COMPANION_INPUT_COUNT == 16
    assert len({(record["path"], record["role"]) for record in physical}) == 16
    assert len(historical) == patch.EXPECTED_HISTORICAL_INPUT_COUNT == 8
    assert len(
        {(record["commit"], record["path"], record["role"]) for record in historical}
    ) == 8
    assert sum(record["commit"] == P_MX_COMMIT for record in historical) == 4
    assert sum(record["commit"] == H_MY_COMMIT for record in historical) == 4
    assert not set(patch.ADOPTED_LIGHT_PATHS).intersection(
        record["path"] for record in physical
    )

    forged_root = tmp_path / "forged-p-mx"
    forged_root.mkdir()
    for path in (patch.BASE_MX_LOCK_PATH, patch.BASE_MX_COMPANION_PATH):
        candidate = forged_root / path
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(b"forged-physical-authority\n")
        candidate.chmod(0o644)
    monkeypatch.setattr(
        patch, "_single_parent", lambda *args, **kwargs: patch.BASE_H_MX_COMMIT
    )
    monkeypatch.setattr(
        patch,
        "_git_scope",
        lambda *args, **kwargs: {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "paths": sorted(
                (
                    patch.BASE_MX_LOCK_PATH.as_posix(),
                    patch.BASE_MX_COMPANION_PATH.as_posix(),
                )
            ),
        },
    )
    monkeypatch.setattr(
        patch, "_require_exact_git_modes", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        patch, "_git_blob_bytes", lambda *args, **kwargs: b"canonical-git-authority\n"
    )
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationAdoptionPatchError,
        match="P-E0-MX physical input differs from Git",
    ):
        patch._base_mx_authority(forged_root)


def test_registration_inventory_and_exact_no_relink_commands_are_closed() -> None:
    inventory = yaml.safe_load(
        (ROOT / patch.DVC_INVENTORY_PATH).read_text(encoding="utf-8")
    )
    records = inventory[patch.REGISTRATION_INVENTORY_KEY]
    expected_payloads = [
        (
            "data/closure_v1/development/anfis_ablation/"
            f"{model_id}/seed_{base_seed}_selection_predictions.parquet"
        )
        for model_id, base_seed in patch.ORDERED_SLOTS
    ]

    assert len(inventory["artifacts"]) == patch.GENERAL_ARTIFACT_COUNT == 23
    assert len(records) == patch.REGISTRATION_ARTIFACT_COUNT == 10
    assert [record["path"] for record in records] == expected_payloads
    assert [(record["model_id"], record["base_seed"]) for record in records] == list(
        patch.ORDERED_SLOTS
    )
    assert all(
        record["type"] == patch.REGISTRATION_ARTIFACT_TYPE
        and record["source_id"] == "wqp"
        and record["dvc"] is True
        and record["github_policy"] == patch.REGISTRATION_GITHUB_POLICY
        for record in records
    )
    assert patch._dvc_add_commands() == [
        ["dvc", "add", "--no-relink", path]
        for path in (*expected_payloads, "models")
    ]
    assert [path.as_posix() for path in precommit_artifacts.ANFIS_ABLATION_REGISTRATION_DVC_TARGETS] == [
        *expected_payloads,
        "models",
    ]
    configuration = patch._dvc_configuration_contract(ROOT)
    assert configuration["cache_type"] == "reflink,hardlink,copy"
    assert configuration["no_relink_required"] is True
    assert configuration["local_cache_override_absent"] is True
    assert configuration["autostage_override_absent"] is True


def test_complete_family_is_exact80_with_all50_lights_tracked() -> None:
    records = patch._family_records(ROOT, registered=False)
    assert len(records) == patch.FAMILY_FINAL_COUNT == 80
    assert patch._digest_records(records) == FAMILY_RECORDS_SHA256
    assert sum(record["bytes"] for record in records) == 3_790_938
    assert sum(record["role"] in patch.LIGHT_SLOT_ROLES for record in records) == 50
    assert sum(record["role"] in patch.HEAVY_SLOT_ROLES for record in records) == 30
    for record in records:
        metadata = (ROOT / record["path"]).lstat()
        assert stat.S_ISREG(metadata.st_mode)
        assert stat.S_IMODE(metadata.st_mode) == 0o644
        assert metadata.st_nlink == 1

    tracked_lights = subprocess.run(
        ["git", "-C", ROOT.as_posix(), "ls-files", "--", *patch._light_paths()],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    tracked_heavy = subprocess.run(
        [
            "git",
            "-C",
            ROOT.as_posix(),
            "ls-files",
            "--",
            *(record["path"] for record in records if record["role"] in patch.HEAVY_SLOT_ROLES),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert set(tracked_lights) == set(patch._light_paths())
    assert len(tracked_lights) == patch.FAMILY_TRACKED_LIGHT_COUNT == 50
    assert patch.FAMILY_UNTRACKED_LIGHT_COUNT == 0
    assert tracked_heavy == []


def test_pre_registration_namespace_and_models_owner_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch._validate_family_namespace(registered=False, repo_root=ROOT)
    assert not [
        path.as_posix()
        for path in patch._selection_pointer_paths()
        if (ROOT / path).exists() or (ROOT / path).is_symlink()
    ]
    assert not [
        path.as_posix()
        for path in patch._forbidden_family_namespace_paths()
        if (ROOT / path).exists() or (ROOT / path).is_symlink()
    ]
    models_dvc = ROOT / patch.MODELS_DVC_PATH
    metadata = models_dvc.lstat()
    assert stat.S_ISREG(metadata.st_mode)
    assert stat.S_IMODE(metadata.st_mode) == 0o644
    assert metadata.st_nlink == 1
    assert metadata.st_size == patch.BASE_MODELS_DVC_BYTES == 109
    assert _sha256(models_dvc) == patch.BASE_MODELS_DVC_SHA256
    assert models_dvc.read_bytes() == patch._base_models_dvc_bytes()

    reader_source = inspect.getsource(patch._read_regular_bytes_and_metadata)
    tree_source = inspect.getsource(patch._require_exact_regular_tree)
    directory_source = inspect.getsource(patch._coordination_directory_record)
    for source in (reader_source, tree_source, directory_source):
        assert "O_NOFOLLOW" in source
        assert "follow_symlinks=False" in source
    assert "dir_fd=" in reader_source
    assert ".read_bytes()" not in reader_source
    assert "os.listdir(descriptor)" in tree_source
    assert "os.listdir(directory_descriptor)" in directory_source
    assert "os.scandir(" not in tree_source + directory_source

    family_snapshot_source = inspect.getsource(patch._family_physical_snapshot)
    publication_snapshot_source = inspect.getsource(patch._publication_input_snapshot)
    family_records_source = inspect.getsource(patch._family_records)
    file_record_source = inspect.getsource(patch._file_record_and_metadata)
    for source in (family_snapshot_source, publication_snapshot_source):
        assert "_read_regular_bytes_and_metadata" in source
        assert ".lstat()" not in source
    assert "_file_record_and_metadata" in family_records_source
    assert ".lstat()" not in family_records_source
    assert "_read_regular_bytes_and_metadata" in file_record_source

    with monkeypatch.context() as snapshot_race:
        repo_root = tmp_path / "snapshot-race"
        repo_root.mkdir()
        relative = Path("governance/input.bin")
        physical = repo_root / relative
        physical.parent.mkdir(parents=True)
        old_payload = b"old-authority\n"
        new_payload = b"NEW-authority\n"
        assert len(old_payload) == len(new_payload)
        physical.write_bytes(old_payload)
        physical.chmod(0o644)
        old_metadata = physical.lstat()
        real_reader = patch._read_regular_bytes_and_metadata
        replaced = False

        def read_then_replace(
            path: Path,
            *,
            repo_root: Path,
            require_nlink_one: bool = True,
            expected_mode: int = 0o644,
        ) -> tuple[bytes, os.stat_result]:
            nonlocal replaced
            payload, metadata = real_reader(
                path,
                repo_root=repo_root,
                require_nlink_one=require_nlink_one,
                expected_mode=expected_mode,
            )
            if path == relative and not replaced:
                replacement = physical.with_name("replacement.bin")
                replacement.write_bytes(new_payload)
                replacement.chmod(0o644)
                os.replace(replacement, physical)
                replaced = True
            return payload, metadata

        snapshot_race.setattr(patch, "_publication_input_paths", lambda: (relative,))
        snapshot_race.setattr(
            patch, "_read_regular_bytes_and_metadata", read_then_replace
        )
        record = patch._publication_input_snapshot(repo_root)[0]
        current_metadata = physical.lstat()
        assert replaced is True
        assert record["sha256"] == hashlib.sha256(old_payload).hexdigest()
        assert record["inode"] == old_metadata.st_ino
        assert current_metadata.st_ino != old_metadata.st_ino
        assert physical.read_bytes() == new_payload


def test_public_private_loader_api_and_helper_alias_are_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert set(
        inspect.signature(
            patch.load_effective_anfis_ablation_dvc_registration_adoption_patch_authority
        ).parameters
    ) == {"audit_current_unpublished", "verify_remote", "repo_root"}
    assert set(
        inspect.signature(
            patch._load_effective_anfis_ablation_dvc_registration_adoption_patch_during_registration
        ).parameters
    ) == {"transaction_record", "verify_remote", "repo_root"}
    assert set(
        inspect.signature(patch.require_anfis_ablation_dvc_registration_authority).parameters
    ) == {"verify_remote", "repo_root"}
    assert (
        "_load_effective_anfis_ablation_dvc_registration_adoption_patch_during_registration"
        not in patch.__all__
    )

    with monkeypatch.context() as translated_git:
        def fail_nested_git(*args: Any, **kwargs: Any) -> str:
            del args, kwargs
            raise RuntimeError("nested MX failure")

        translated_git.setattr(patch.mx, "_git", fail_nested_git)
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationAdoptionPatchError,
            match="nested MX failure",
        ):
            patch._git(ROOT, "status")

    with monkeypatch.context() as translated_public:
        def fail_public_loader(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            raise ValueError("synthetic public boundary failure")

        translated_public.setattr(
            patch,
            "_load_effective_anfis_ablation_dvc_registration_adoption_patch_authority",
            fail_public_loader,
        )
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationAdoptionPatchError,
            match="synthetic public boundary failure",
        ):
            patch.load_effective_anfis_ablation_dvc_registration_adoption_patch_authority(
                repo_root=tmp_path
            )

    malformed_lock_root = tmp_path / "malformed-lock"
    malformed_lock = malformed_lock_root / patch.DEFAULT_PATCH_LOCK_PATH
    malformed_lock.parent.mkdir(parents=True)
    malformed_lock.write_bytes(b"\xff")
    malformed_lock.chmod(0o644)
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationAdoptionPatchError,
        match="lock is not valid UTF-8 JSON",
    ):
        patch.load_effective_anfis_ablation_dvc_registration_adoption_patch_authority(
            repo_root=malformed_lock_root
        )

    malformed_companion_root = tmp_path / "malformed-companion"
    lock = malformed_companion_root / patch.DEFAULT_PATCH_LOCK_PATH
    companion = malformed_companion_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    lock.parent.mkdir(parents=True)
    lock.write_bytes(patch._canonical_json({}))
    lock.chmod(0o644)
    companion.write_bytes(b"\xff")
    companion.chmod(0o644)
    with monkeypatch.context() as malformed_companion:
        malformed_companion.setattr(
            patch,
            "_validate_anfis_ablation_dvc_registration_adoption_patch_lock_payload",
            lambda *args, **kwargs: None,
        )
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationAdoptionPatchError,
            match="companion is not valid UTF-8 JSON",
        ):
            patch.load_effective_anfis_ablation_dvc_registration_adoption_patch_authority(
                repo_root=malformed_companion_root
            )

    calls: list[tuple[str, dict[str, Any]]] = []

    def public(**kwargs: Any) -> dict[str, Any]:
        calls.append(("public", kwargs))
        return {"gate": "E0-MZB", "mode": "public"}

    def private(**kwargs: Any) -> dict[str, Any]:
        calls.append(("private", kwargs))
        return {"gate": "E0-MZB", "mode": "private"}

    monkeypatch.setattr(
        mzb_patch,
        "load_effective_anfis_ablation_dvc_registration_namespace_patch_authority",
        public,
    )
    assert precommit_artifacts._load_effective_anfis_ablation_dvc_registration_authority(
        audit_current_unpublished=False, repo_root=ROOT
    ) == {"gate": "E0-MZB", "mode": "public"}
    transaction = {"mode": "atomic_replace"}
    monkeypatch.setattr(
        mzb_patch,
        "_load_effective_anfis_ablation_dvc_registration_namespace_patch_during_registration",
        private,
    )
    assert precommit_artifacts._load_effective_anfis_ablation_dvc_registration_authority(
        audit_current_unpublished=True,
        repo_root=ROOT,
        registration_transaction=transaction,
    ) == {"gate": "E0-MZB", "mode": "private"}
    assert calls == [
        (
            "public",
            {
                "audit_current_unpublished": False,
                "verify_remote": True,
                "repo_root": ROOT,
            },
        ),
        (
            "private",
            {
                "transaction_record": transaction,
                "verify_remote": True,
                "repo_root": ROOT,
            },
        ),
    ]


def test_schema_closes_adoption_history_family_and_registration_scope() -> None:
    schema = json.loads(
        (ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text(encoding="utf-8")
    )
    definitions = schema["$defs"]

    def resolved_property(name: str) -> dict[str, Any]:
        reference = schema["properties"][name]["$ref"]
        return definitions[reference.removeprefix("#/$defs/")]

    assert schema["properties"]["gate"]["const"] == "E0-MZ"
    assert {"historical_h_my", "adopted_light_publication"} <= set(
        schema["required"]
    )
    repository = resolved_property("repository")["properties"]
    assert repository["parent"]["const"] == ADOPTED_LIGHT_COMMIT
    assert repository["worktree_scope"]["const"] == "clean_all_50_light_outputs_tracked"
    h_patch = resolved_property("h_patch")["properties"]
    assert h_patch["base_commit"]["const"] == ADOPTED_LIGHT_COMMIT
    assert h_patch["parent"]["const"] == ADOPTED_LIGHT_COMMIT
    assert h_patch["component_count"]["const"] == 9
    modes_ref = h_patch["components_git_modes"]["$ref"].removeprefix("#/$defs/")
    assert set(definitions[modes_ref]["required"]) == set(patch.PATCH_PATHS)
    family = resolved_property("completed_family")["properties"]
    assert family["slot_count"]["const"] == 10
    assert family["final_count"]["const"] == 80
    assert family["light_final_count"]["const"] == 50
    assert family["tracked_light_count"]["const"] == 50
    assert family["untracked_light_count"]["const"] == 0
    assert family["heavy_final_count"]["const"] == 30
    expected_slots = patch._expected_ordered_slots()
    assert family["ordered_slots"]["const"] == expected_slots
    assert definitions["familyAudit"]["properties"]["ordered_slots"][
        "const"
    ] == expected_slots
    assert definitions["slot"]["properties"]["base_seed"]["type"] == "integer"
    assert definitions["registrationArtifact"]["properties"]["base_seed"][
        "type"
    ] == "integer"
    for seed_schema in (
        definitions["slot"]["properties"]["base_seed"],
        definitions["registrationArtifact"]["properties"]["base_seed"],
    ):
        with pytest.raises(patch.ClosureContractError):
            patch.validate_json_schema(1729.0, seed_schema)
    for ordered_schema in (
        family["ordered_slots"],
        definitions["familyAudit"]["properties"]["ordered_slots"],
    ):
        probe_schema = {"$defs": definitions, **ordered_schema}
        for drifted in (expected_slots[:-1], list(reversed(expected_slots))):
            with pytest.raises(patch.ClosureContractError):
                patch.validate_json_schema(drifted, probe_schema)
    assert "_expected_ordered_slots()" in inspect.getsource(
        patch._validate_anfis_ablation_dvc_registration_adoption_patch_lock_payload
    )
    assert "_expected_ordered_slots()" in inspect.getsource(
        patch._validate_verification
    )
    companion = resolved_property("companion_contract")["properties"]
    assert companion["physical_input_count"]["const"] == 16
    assert companion["historical_input_count"]["const"] == 8
    assert companion["output_count"]["const"] == 1
    plan = resolved_property("registration_plan")["properties"]
    scope_ref = plan["registration_git_scope"]["$ref"].removeprefix("#/$defs/")
    registration = definitions[scope_ref]["properties"]
    assert registration["added"]["const"] == 10
    assert registration["modified"]["const"] == 1
    assert registration["deleted"]["const"] == 0
    assert registration["path_count"]["const"] == 11
    assert plan["light_report_addition_count"]["const"] == 0
    assert definitions["focusedTests"]["properties"]["test_count"]["const"] == (
        patch.FOCUSED_TEST_COUNT
    )
    patch.preflight_anfis_ablation_dvc_registration_adoption_patch_schema(
        repo_root=ROOT
    )


def test_generic_precommit_manifest_dialect_is_one_one_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    lock = patch.DEFAULT_PATCH_LOCK_PATH
    companion = patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    script = Path("src/synthetic_e0_mz_locker.py")
    source = Path("configs/synthetic_e0_mz_input.json")
    for path in (lock, companion, script, source):
        path.parent.mkdir(parents=True, exist_ok=True)
    script.write_bytes(b"# synthetic E0-MZ locker\n")
    source.write_bytes(b"{}\n")
    lock.write_bytes(b'{"gate":"E0-MZ","status":"locked_unpublished"}\n')
    companion.write_text(
        json.dumps(
            {
                "manifest_version": "synthetic_e0_mz_lock_manifest_v1",
                "status": "completed",
                "gate": "E0-MZ",
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
    assert [
        finding.message
        for finding in findings
        if finding.check == "manifest" and finding.path == "-"
    ] == [
        "Checked 1 experiment manifest(s), 1 output record(s), and 1 staged "
        "report artifact(s). 0 covered output(s) are also protected by DVC pointers."
    ]


def test_check_only_is_a_nonwriting_adoption_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = {"status": "schema_preflight_passed"}
    repository = {"head": "f" * 40}
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_dvc_registration_adoption_patch_schema",
        lambda: schema,
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_dvc_registration_adoption_patch_prelock_state",
        lambda **kwargs: {
            "repository": repository,
            "h_patch": {"component_count": 9},
            "companion_contract": {
                "physical_input_count": 16,
                "historical_input_count": 8,
            },
            "completed_family": {
                "slot_count": 10,
                "final_count": 80,
                "light_final_count": 50,
                "tracked_light_count": 50,
                "untracked_light_count": 0,
                "heavy_final_count": 30,
            },
            "artifact_inventory": {
                "registration_artifact_count": 10,
                "general_artifact_count": 23,
            },
            "registration_plan": {"registration_git_scope": {"path_count": 11}},
            "prelock": {"selection_pointer_present_count": 0},
        },
    )
    result = locker.check_only()
    assert result["status"] == "ready_to_lock"
    assert result["gate"] == "E0-MZ"
    assert result["schema_preflight"] == schema
    assert result["repository"] == repository
    assert result["adopted_light_commit"] == ADOPTED_LIGHT_COMMIT
    assert result["adopted_light_count"] == 45
    assert {
        key: result[key]
        for key in (
            "component_count",
            "physical_input_count",
            "historical_input_count",
            "completed_slot_count",
            "family_final_count",
            "lightweight_final_count",
            "tracked_light_count",
            "untracked_light_count",
            "heavy_final_count",
            "registration_artifact_count",
            "general_artifact_count",
            "registration_git_path_count",
            "prediction_pointer_count",
        )
    } == {
        "component_count": 9,
        "physical_input_count": 16,
        "historical_input_count": 8,
        "completed_slot_count": 10,
        "family_final_count": 80,
        "lightweight_final_count": 50,
        "tracked_light_count": 50,
        "untracked_light_count": 0,
        "heavy_final_count": 30,
        "registration_artifact_count": 10,
        "general_artifact_count": 23,
        "registration_git_path_count": 11,
        "prediction_pointer_count": 0,
    }
    assert all(
        result[key] is False
        for key in (
            "writes_performed",
            "verification_commands_run",
            "trainer_entrypoint_run",
            "model_fit_or_optimization_run",
            "auditor_entrypoint_run",
            "dvc_commands_run",
            "scientific_network_commands_run",
            "calibration_targets_read",
            "future_outcomes_accessed",
        )
    )


def test_execute_lock_and_effective_checks_delegate_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def publish(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        calls.append(("publish", kwargs))
        return {"gate": "E0-MZ"}, {"status": "completed"}

    def load(**kwargs: Any) -> dict[str, Any]:
        calls.append(("load", kwargs))
        return {"gate": "E0-MZ", "status": "effective"}

    monkeypatch.setattr(
        patch,
        "publish_anfis_ablation_dvc_registration_adoption_patch_lock_bundle",
        publish,
    )
    monkeypatch.setattr(
        patch,
        "load_effective_anfis_ablation_dvc_registration_adoption_patch_authority",
        load,
    )
    locked = locker.execute_lock()
    effective = locker.check_effective()
    assert calls == [("publish", {}), ("load", {"verify_remote": True})]
    assert locked["status"] == "locked_unpublished"
    assert locked["gate"] == "E0-MZ"
    assert locked["lock"] == {"gate": "E0-MZ"}
    assert locked["companion"] == {"status": "completed"}
    assert effective == {"gate": "E0-MZ", "status": "effective"}


def test_locker_cli_is_closed_and_translates_only_patch_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    assert locker.parse_args(["--execute-lock"]).execute_lock is True
    assert locker.parse_args(["--check-effective"]).check_effective is True
    for invalid in ([], ["--check-only", "--execute-lock"], ["--model-id", "A0"]):
        with pytest.raises(SystemExit):
            locker.parse_args(invalid)
    capsys.readouterr()

    monkeypatch.setattr(
        locker,
        "check_only",
        lambda: (_ for _ in ()).throw(
            patch.AnfisAblationDvcRegistrationAdoptionPatchError("closed")
        ),
    )
    assert locker.main(["--check-only"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "closed\n"


def test_locker_publisher_surface_and_p_git_binding_are_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert set(
        inspect.signature(
            patch.publish_anfis_ablation_dvc_registration_adoption_patch_lock_bundle
        ).parameters
    ) == {"repo_root"}
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

    owned_root = tmp_path / "owned-output"
    owned_root.mkdir()
    owned_path = Path("reports/closure_v1/00_protocol/synthetic_owned.json")
    owned_payload = b'{"ok":true}\n'
    owned = patch.mt._publish_bytes_no_clobber(
        owned_path, owned_payload, repo_root=owned_root
    )
    patch._validate_owned_output_bytes(
        owned, owned_payload, context="at synthetic baseline"
    )
    tampered_payload = b'{"ok":null}\n'
    assert len(tampered_payload) == len(owned_payload)
    (owned_root / owned_path).write_bytes(tampered_payload)
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationAdoptionPatchError,
        match="owned output bytes drifted",
    ):
        patch._validate_owned_output_bytes(
            owned, owned_payload, context="after in-place mutation"
        )
    patch.mt._rollback_owned_output(owned)
    assert not (owned_root / owned_path).exists()

    first = patch.mt._OwnedOutput(
        path=Path("reports/synthetic-first.json"),
        lexical_parent=Path("reports"),
        name="synthetic-first.json",
        parent_descriptor=-1,
        device=0,
        inode=1,
        parent_device=0,
        parent_inode=2,
    )
    second = patch.mt._OwnedOutput(
        path=Path("reports/synthetic-second.json"),
        lexical_parent=Path("reports"),
        name="synthetic-second.json",
        parent_descriptor=-1,
        device=0,
        inode=3,
        parent_device=0,
        parent_inode=2,
    )
    with monkeypatch.context() as best_effort:
        rollback_calls: list[Path] = []

        def rollback(output: Any) -> None:
            rollback_calls.append(output.path)
            if output is second:
                raise RuntimeError("synthetic rollback failure")

        best_effort.setattr(patch.mt, "_rollback_owned_output", rollback)
        rollback_error = patch._rollback_published_outputs_best_effort(
            [first, second]
        )
        assert rollback_calls == [second.path, first.path]
        assert isinstance(
            rollback_error,
            patch.AnfisAblationDvcRegistrationAdoptionPatchError,
        )
        assert "synthetic-second.json" in str(rollback_error)

    with monkeypatch.context() as best_effort_close:
        close_calls: list[Path] = []

        def close(output: Any) -> None:
            close_calls.append(output.path)
            if output is first:
                raise RuntimeError("synthetic close failure")

        best_effort_close.setattr(patch.mt, "_close_owned_output", close)
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationAdoptionPatchError,
            match="synthetic-first.json",
        ):
            patch._close_published_outputs_best_effort([first, second])
        assert close_calls == [first.path, second.path]

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
    monkeypatch.setattr(patch, "_git_head", lambda repo_root, ref="HEAD": p_head)
    monkeypatch.setattr(patch, "_live_remote_main_head", lambda repo_root: p_head)
    monkeypatch.setattr(patch, "_single_parent", lambda *args, **kwargs: h_head)
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
    monkeypatch.setattr(
        patch, "_require_exact_git_modes", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        patch,
        "_git_blob_bytes",
        lambda repo_root, commit, path: physical_payloads[path],
    )
    assert patch._validate_p_publication(
        {"repository": {"head": h_head}}, repo_root=repo_root
    ) == {"h_patch_head": h_head, "p_patch_head": p_head, "remote_head": p_head}
    (repo_root / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).write_bytes(b"drift\n")
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationAdoptionPatchError,
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
    payload = {"gate": "E0-MZ", "status": "locked_unpublished"}
    companion = {
        "manifest_version": "synthetic_e0_mz_lock_manifest_v1",
        "status": "completed",
        "completion_marker_written_last": True,
    }
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_dvc_registration_adoption_patch_prelock_state",
        lambda **kwargs: prelock,
    )
    monkeypatch.setattr(
        patch,
        "_family_physical_snapshot",
        lambda repo_root: ({"path": "synthetic/final.bin", "inode": 1},),
    )
    monkeypatch.setattr(
        patch,
        "_publication_input_snapshot",
        lambda repo_root: ({"path": "synthetic/input.bin", "inode": 2},),
    )
    monkeypatch.setattr(
        patch,
        "_publication_git_snapshot",
        lambda repo_root: {"head": "synthetic-h", "status": []},
    )
    monkeypatch.setattr(
        patch, "_require_family_physical_snapshot", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        patch, "_require_publication_state", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        patch,
        "run_anfis_ablation_dvc_registration_adoption_patch_verification",
        lambda **kwargs: {"status": "passed"},
    )
    monkeypatch.setattr(
        patch,
        "build_anfis_ablation_dvc_registration_adoption_patch_lock_payload",
        lambda *args, **kwargs: payload,
    )
    monkeypatch.setattr(
        patch,
        "validate_anfis_ablation_dvc_registration_adoption_patch_lock_payload",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(patch, "_expected_companion", lambda *args, **kwargs: companion)


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
            patch.AnfisAblationDvcRegistrationAdoptionPatchError,
            match="synthetic companion failure",
        ):
            patch.publish_anfis_ablation_dvc_registration_adoption_patch_lock_bundle(
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
            patch.AnfisAblationDvcRegistrationAdoptionPatchError,
            match="lock namespace is occupied",
        ):
            patch.publish_anfis_ablation_dvc_registration_adoption_patch_lock_bundle(
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


def test_publisher_revalidates_guarded_state_and_post_lock_family(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as guarded:
        repo_root = tmp_path / "guarded-drift"
        repo_root.mkdir()
        _install_synthetic_publisher(repo_root, guarded)
        baseline = {
            "repository": {"head": "h"},
            "prelock": {"writes_performed": False},
        }
        calls = 0

        def collect(**kwargs: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return {"repository": {"head": "drift"}} if calls == 3 else baseline

        guarded.setattr(
            patch,
            "collect_anfis_ablation_dvc_registration_adoption_patch_prelock_state",
            collect,
        )
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationAdoptionPatchError,
            match="guarded prelock state drifted",
        ):
            patch.publish_anfis_ablation_dvc_registration_adoption_patch_lock_bundle(
                repo_root=repo_root
            )
        assert calls == 3
        assert not (repo_root / patch.DEFAULT_PATCH_LOCK_PATH).exists()
        assert not (repo_root / patch.LOCKER_GUARD_PATH).exists()

    with monkeypatch.context() as post_lock:
        repo_root = tmp_path / "post-lock-drift"
        repo_root.mkdir()
        _install_synthetic_publisher(repo_root, post_lock)
        drifted = False
        real_publish = patch.mt._publish_bytes_no_clobber

        def publish_then_drift(path: Path, payload: bytes, *, repo_root: Path) -> Any:
            nonlocal drifted
            output = real_publish(path, payload, repo_root=repo_root)
            if path == patch.DEFAULT_PATCH_LOCK_PATH:
                drifted = True
            return output

        def require_snapshot(expected: Any, *, repo_root: Path, context: str) -> None:
            del expected, repo_root
            if drifted:
                raise patch.AnfisAblationDvcRegistrationAdoptionPatchError(
                    f"E0-MZ family physical snapshot drifted {context}"
                )

        post_lock.setattr(patch.mt, "_publish_bytes_no_clobber", publish_then_drift)
        post_lock.setattr(patch, "_require_family_physical_snapshot", require_snapshot)
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationAdoptionPatchError,
            match="after lock publication",
        ):
            patch.publish_anfis_ablation_dvc_registration_adoption_patch_lock_bundle(
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

    with monkeypatch.context() as in_place_output_drift:
        repo_root = tmp_path / "in-place-output-drift"
        repo_root.mkdir()
        _install_synthetic_publisher(repo_root, in_place_output_drift)
        real_publish = patch.mt._publish_bytes_no_clobber

        def publish_then_mutate_lock(
            path: Path, payload: bytes, *, repo_root: Path
        ) -> Any:
            output = real_publish(path, payload, repo_root=repo_root)
            if path == patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH:
                lock_path = repo_root / patch.DEFAULT_PATCH_LOCK_PATH
                lock_payload = lock_path.read_bytes()
                replacement = (b"X" if lock_payload[:1] != b"X" else b"Y")
                lock_path.write_bytes(replacement + lock_payload[1:])
            return output

        in_place_output_drift.setattr(
            patch.mt, "_publish_bytes_no_clobber", publish_then_mutate_lock
        )
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationAdoptionPatchError,
            match="owned output bytes drifted after companion publication",
        ):
            patch.publish_anfis_ablation_dvc_registration_adoption_patch_lock_bundle(
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


def test_document_closes_adoption_registration_and_external_barriers() -> None:
    document = (
        ROOT
        / "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_ADOPTION_PATCH_1.md"
    ).read_text(encoding="utf-8")
    for token in (
        P_MX_COMMIT,
        H_MY_COMMIT,
        ADOPTED_LIGHT_COMMIT,
        "exact 45A lightweight-family adoption",
        "`4M+5A`",
        "`10A+1M`",
        "80 regular `0644`, single-link finals",
        "50 lightweight Git files",
        "16 current physical inputs and eight",
        "five preserved H-E0-MY",
        "four inherited P-E0-MX blobs",
        "dvc add --no-relink",
        "commit_ready",
        "DVC push",
    ):
        assert token in document
    assert patch.DEFAULT_PATCH_LOCK_PATH.as_posix() in document
    assert patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix() in document
