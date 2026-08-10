from __future__ import annotations

import hashlib
import inspect
import json
import os
import shutil
import stat
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml
from scmrepo.git import Git

from src.data import prepare_commit_artifacts as precommit_artifacts
from src.experiments import (
    closure_anfis_ablation_dvc_registration_reproducibility_patch as patch,
)
from src.experiments import (
    closure_anfis_ablation_dvc_registration_status_patch as mzd,
)
from src.experiments import (
    lock_closure_anfis_ablation_dvc_registration_reproducibility_patch as locker,
)


ROOT = Path(__file__).resolve().parents[1]
H_MZD_COMMIT = "21ea7cb6978d93e356fa50c963c739337cbfd2d6"
P_MZD_COMMIT = "33b84bc8aa7a9968947f4b670dbd0aae10fbfa74"
FAMILY_RECORDS_SHA256 = (
    "e625add8f8af1746f7deda9ff13a84a4d4f4c27b47e3b6312922db419508dd8e"
)
EXPECTED_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_dvc_registration_reproducibility_patch.schema.json",
    "docs/closure_v1/ANFIS_ABLATION_DVC_REGISTRATION_REPRODUCIBILITY_PATCH.md",
    "src/experiments/closure_anfis_ablation_dvc_registration_reproducibility_patch.py",
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_reproducibility_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_reproducibility_patch.py",
}
EXPECTED_MODIFICATIONS = {
    "src/data/prepare_commit_artifacts.py",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_namespace_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_gitignore_patch.py",
    "tests/test_closure_anfis_ablation_dvc_registration_status_patch.py",
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


def _copy_family_tree(repo_root: Path) -> None:
    """Copy the sealed 80 finals into an isolated namespace fixture."""

    for model_id, base_seed in patch.ORDERED_SLOTS:
        for raw_path in precommit_artifacts._anfis_ablation_slot_final_paths(
            model_id, base_seed
        ):
            source = ROOT / raw_path
            target = repo_root / raw_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _write_pointer(repo_root: Path, index: int) -> Path:
    payload = Path(precommit_artifacts.ANFIS_ABLATION_SELECTION_PREDICTION_PATHS[index])
    pointer = repo_root / precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS[index]
    pointer.write_bytes(patch._expected_pointer_bytes(payload, repo_root=repo_root))
    pointer.chmod(0o644)
    return pointer


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

    assert patch.PATCH_GATE == "E0-MZE"
    assert patch.H_MZD_COMMIT == H_MZD_COMMIT
    assert patch.P_MZD_COMMIT == P_MZD_COMMIT
    assert patch.BASE_COMMIT == P_MZD_COMMIT
    assert set(patch.PATCH_ADDED_PATHS) == EXPECTED_ADDITIONS
    assert set(patch.PATCH_MODIFIED_PATHS) == EXPECTED_MODIFICATIONS
    assert set(patch.PATCH_PATHS) == EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    assert len(patch.PATCH_PATHS) == 14
    assert patch.PATCH_COMPONENT_GIT_MODES == {
        path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
        for path in patch.PATCH_PATHS
    }
    assert patch.ANFIS_ABLATION_H_MZE_STAGED_SCOPE == expected_h
    assert patch.ANFIS_ABLATION_P_MZE_STAGED_SCOPE == expected_p
    assert patch.ANFIS_ABLATION_R_MZE_STAGED_SCOPE == expected_r
    assert precommit_artifacts.DEFERRED_DVC_H_MZE_STAGED_SCOPE == expected_h
    assert precommit_artifacts.DEFERRED_DVC_P_MZE_STAGED_SCOPE == expected_p
    assert precommit_artifacts.ANFIS_ABLATION_R_MZE_STAGED_SCOPE == expected_r
    assert len(expected_h) == 14
    assert len(expected_p) == 2
    assert len(expected_r) == 11
    assert list(expected_r.values()).count("A") == 10
    assert list(expected_r.values()).count("M") == 1
    assert precommit_artifacts.DEFERRED_DVC_ACTIVE_STAGING_GATES == frozenset(
        {"H-E0-MZE", "P-E0-MZE"}
    )
    assert (
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_COMMIT
        == patch.HISTORICAL_TRAINER_COMMIT
    )
    assert (
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_BLOB_OID
        == patch.HISTORICAL_TRAINER_GIT_OID
    )
    assert (
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_BYTES
        == patch.HISTORICAL_TRAINER_BYTES
    )
    assert (
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_SHA256
        == patch.HISTORICAL_TRAINER_SHA256
    )
    assert (
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_COMMIT
        == patch.CURRENT_TRAINER_COMMIT
    )
    assert (
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_BLOB_OID
        == patch.CURRENT_TRAINER_GIT_OID
    )
    assert (
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_BYTES
        == patch.CURRENT_TRAINER_BYTES
    )
    assert (
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_SHA256
        == patch.CURRENT_TRAINER_SHA256
    )


def test_p_mzd_authority_and_historical_mzd_partition_are_exact() -> None:
    base = patch._base_mzd_authority(ROOT)
    history = patch._historical_h_mzd_authority(ROOT)
    historical_inputs = patch._historical_inputs(ROOT)

    assert base["gate"] == "E0-MZD"
    assert base["p_head"] == P_MZD_COMMIT
    assert base["h_head"] == H_MZD_COMMIT
    assert base["publication_reconstructed_from_git"] is True
    assert base["effective_loader_called"] is False
    assert base["lock"]["path"] == patch.BASE_MZD_LOCK_PATH.as_posix()
    assert base["companion"]["path"] == patch.BASE_MZD_COMPANION_PATH.as_posix()
    assert len(base["historical_inputs"]) == mzd.EXPECTED_HISTORICAL_INPUT_COUNT == 34

    assert history["gate"] == "E0-MZD"
    assert history["head"] == H_MZD_COMMIT
    assert history["parent"] == mzd.BASE_COMMIT
    assert history["scope"] == {"added": 5, "modified": 8, "deleted": 0}
    assert history["paths"] == list(mzd.PATCH_PATHS)
    assert history["preserved_component_count"] == 4
    assert history["superseded_component_count"] == 9
    assert {record["path"] for record in history["preserved_components"]} == set(
        patch.PRESERVED_MZD_PATHS
    )
    assert {record["path"] for record in history["superseded_components"]} == set(
        patch.SUPERSEDED_MZD_PATHS
    )

    assert len(historical_inputs) == patch.EXPECTED_HISTORICAL_INPUT_COUNT == 43
    assert len(
        {(record["commit"], record["path"], record["role"]) for record in historical_inputs}
    ) == 43
    assert historical_inputs[:34] == base["historical_inputs"]
    assert sum(record["commit"] == H_MZD_COMMIT for record in historical_inputs) == 9
    assert all(
        record["role"].startswith("superseded_h_mzd_")
        for record in historical_inputs[34:]
    )
    assert not any(record["path"] == ".gitignore" for record in historical_inputs)


def test_companion_physical_and_historical_partitions_are_exact(
) -> None:
    history = patch._historical_h_mzd_authority(ROOT)
    base_mzd = patch._base_mzd_authority(ROOT)
    h_components = [
        {"path": path, "role": patch.PATCH_COMPONENT_ROLES[path]}
        for path in patch.PATCH_PATHS
    ]
    physical = patch._companion_physical_inputs(
        h_components=h_components,
        base_mzd=base_mzd,
        historical_h_mzd=history,
    )
    historical = patch._historical_inputs(ROOT)

    assert len(physical) == patch.EXPECTED_COMPANION_INPUT_COUNT == 20
    assert len({(record["path"], record["role"]) for record in physical}) == 20
    assert len(historical) == patch.EXPECTED_HISTORICAL_INPUT_COUNT == 43
    assert len(
        {(record["commit"], record["path"], record["role"]) for record in historical}
    ) == 43
    assert sum(record["commit"] == H_MZD_COMMIT for record in historical) == 9
    assert {record["path"] for record in physical} == {
        patch.BASE_MZD_LOCK_PATH.as_posix(),
        patch.BASE_MZD_COMPANION_PATH.as_posix(),
        *patch.PRESERVED_MZD_PATHS,
        *patch.PATCH_PATHS,
    }
    assert not any(record["path"] == ".gitignore" for record in physical)
    assert not any(record["path"] == ".gitignore" for record in historical)


def test_registration_inventory_set_validation_and_canonical_commands_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    configured = precommit_artifacts.load_configured_dvc_artifacts(
        precommit_artifacts.DEFAULT_DVC_MANIFEST
    )
    registration = precommit_artifacts.load_anfis_ablation_registration_artifacts()
    discovered = precommit_artifacts.declared_artifacts_missing_pointers(
        [*configured, *registration]
    )
    discovered_paths = [artifact.path.as_posix() for artifact in discovered]
    assert discovered_paths == sorted(expected_payloads)
    assert discovered_paths != expected_payloads
    assert (
        precommit_artifacts.validate_anfis_ablation_registration_missing_pointer_set(
            discovered
        )
        == discovered
    )

    extra = precommit_artifacts.DvcArtifact(
        artifact_id="synthetic_extra",
        path=Path("data/closure_v1/development/anfis_ablation/A2/extra.parquet"),
        artifact_type=patch.REGISTRATION_ARTIFACT_TYPE,
        source_id="wqp",
        dvc=True,
    )
    malformed = (
        discovered[:-1],
        [*discovered[:-1], discovered[0]],
        [*discovered[:-1], extra],
        [*discovered, discovered[0]],
    )
    for candidate in malformed:
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="missing-pointer set is not the exact ten predictions",
        ):
            precommit_artifacts.validate_anfis_ablation_registration_missing_pointer_set(
                candidate
            )

    assert patch._dvc_add_commands() == [
        ["dvc", "add", "--no-relink", path]
        for path in (*expected_payloads, "models")
    ]
    assert [path.as_posix() for path in precommit_artifacts.ANFIS_ABLATION_REGISTRATION_DVC_TARGETS] == [
        *expected_payloads,
        "models",
    ]
    registration_source = inspect.getsource(
        precommit_artifacts._run_anfis_ablation_model_family_registration
    )
    assert "validate_anfis_ablation_registration_missing_pointer_set(missing)" in (
        registration_source
    )
    assert (
        "selected_dvc_paths = list(ANFIS_ABLATION_REGISTRATION_DVC_TARGETS)"
        in registration_source
    )

    pointer_paths = list(precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS)

    def short_status(
        mapping: dict[str, str], *, tracked_first: bool = False
    ) -> str:
        ordered = sorted(
            mapping.items(),
            key=(
                (lambda item: (item[1] == "??", item[0]))
                if tracked_first
                else (lambda item: item[0])
            ),
        )
        return "".join(f"{status_code} {path}\n" for path, status_code in ordered)

    # Every owned pointer-prefix phase is an exact map.  Record order is not
    # authority; a tracked models.dvc record is permitted only at final N=10.
    for pointer_count in range(11):
        prefix = {path: "??" for path in pointer_paths[:pointer_count]}
        lexical = short_status(prefix)
        reversed_rows = "".join(reversed(lexical.splitlines(keepends=True)))
        assert precommit_artifacts.validate_anfis_ablation_git_short_status_map(
            lexical,
            expected=prefix,
            context=f"synthetic prefix {pointer_count}",
        ) == prefix
        assert precommit_artifacts.validate_anfis_ablation_git_short_status_map(
            reversed_rows,
            expected=prefix,
            context=f"synthetic reversed prefix {pointer_count}",
        ) == prefix

    final_pre_stage = {
        **{path: "??" for path in pointer_paths},
        "models.dvc": " M",
    }
    tracked_first = short_status(final_pre_stage, tracked_first=True)
    lexical_final = short_status(final_pre_stage)
    assert tracked_first.splitlines()[0] == " M models.dvc"
    assert lexical_final.splitlines()[-1] == " M models.dvc"
    assert precommit_artifacts.validate_anfis_ablation_registration_pre_stage_scope(
        tracked_first
    ) == "R-E0-MZE"
    assert precommit_artifacts.validate_anfis_ablation_registration_pre_stage_scope(
        lexical_final
    ) == "R-E0-MZE"

    transaction = precommit_artifacts._AnfisAblationRegistrationTransaction(
        repo_root=ROOT,
        manage_git_index=True,
    )
    monkeypatch.setattr(transaction, "_require_guard", lambda: None)
    monkeypatch.setattr(transaction, "_require_gitignore", lambda: None)
    observed_progress = ""

    def git_output(repo_root: Path, *arguments: str) -> str:
        del repo_root, arguments
        return observed_progress

    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    for pointer_count in range(11):
        observed_progress = short_status(
            {path: "??" for path in pointer_paths[:pointer_count]}
        )
        transaction.verify_progress_scope(
            pointer_count=pointer_count,
            models_registered=False,
        )
    observed_progress = tracked_first
    transaction.verify_progress_scope(pointer_count=10, models_registered=True)
    for pointer_count in range(10):
        observed_progress = short_status(
            {
                **{path: "??" for path in pointer_paths[:pointer_count]},
                "models.dvc": " M",
            },
            tracked_first=True,
        )
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
        ):
            transaction.verify_progress_scope(
                pointer_count=pointer_count,
                models_registered=True,
            )

    staged_map = {
        **{path: "A " for path in pointer_paths},
        "models.dvc": "M ",
    }
    staged_tracked_first = short_status(staged_map, tracked_first=True)
    assert precommit_artifacts.validate_anfis_ablation_git_short_status_map(
        staged_tracked_first,
        expected=staged_map,
        context="synthetic staged scope",
    ) == staged_map
    assert precommit_artifacts.validate_anfis_ablation_registration_staged_scope(
        "M\tmodels.dvc\n"
        + "".join(f"A\t{path}\n" for path in reversed(pointer_paths))
    ) == "R-E0-MZE"

    exact_one = f"?? {pointer_paths[0]}\n"
    malformed_short_statuses = (
        "x\n",
        "?? \n",
        f"??X{pointer_paths[0]}\n",
        exact_one + exact_one,
        exact_one + "?? foreign.txt\n",
        f"R  {pointer_paths[0]} -> foreign.txt\n",
        f" D {pointer_paths[0]}\n",
        f"M  {pointer_paths[0]}\n",
        "",
    )
    for malformed_status in malformed_short_statuses:
        with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
            precommit_artifacts.validate_anfis_ablation_git_short_status_map(
                malformed_status,
                expected={pointer_paths[0]: "??"},
                context="synthetic malformed scope",
            )

    malformed_name_statuses = (
        "M\tmodels.dvc\n" + "".join(f"A\t{path}\n" for path in pointer_paths[:-1]),
        "M\tmodels.dvc\n"
        + "".join(f"A\t{path}\n" for path in pointer_paths)
        + "A\tforeign.txt\n",
        "M\tmodels.dvc\n"
        + "".join(f"A\t{path}\n" for path in pointer_paths)
        + f"A\t{pointer_paths[0]}\n",
        "R100\told\tmodels.dvc\n"
        + "".join(f"A\t{path}\n" for path in pointer_paths),
        "D\tmodels.dvc\n" + "".join(f"A\t{path}\n" for path in pointer_paths),
        "M\tmodels.dvc\n"
        + "".join(f"A\t{path}\n" for path in pointer_paths)
        + "malformed\n",
    )
    for malformed_status in malformed_name_statuses:
        with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
            precommit_artifacts.validate_anfis_ablation_registration_staged_scope(
                malformed_status
            )

    deferred_gate, deferred_scope = next(
        iter(precommit_artifacts._deferred_dvc_staged_scopes().items())
    )
    deferred_name_status = "".join(
        f"{status_code}\t{path}\n"
        for path, status_code in reversed(tuple(deferred_scope.items()))
    )
    assert (
        precommit_artifacts.validate_deferred_dvc_staged_scope(
            deferred_name_status
        )
        == deferred_gate
    )
    with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
        precommit_artifacts.validate_deferred_dvc_staged_scope(
            deferred_name_status + "malformed\n"
        )

    progress_source = inspect.getsource(
        precommit_artifacts._AnfisAblationRegistrationTransaction.verify_progress_scope
    )
    pre_stage_source = inspect.getsource(
        precommit_artifacts.validate_anfis_ablation_registration_pre_stage_scope
    )
    staged_binding_source = inspect.getsource(
        precommit_artifacts.validate_anfis_ablation_registration_staged_bindings
    )
    assert "validate_anfis_ablation_git_short_status_map" in progress_source
    assert "validate_anfis_ablation_git_short_status_map" in pre_stage_source
    assert "validate_anfis_ablation_git_short_status_map" in staged_binding_source
    assert "splitlines() !=" not in progress_source + pre_stage_source + staged_binding_source

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
    invocation_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": precommit_artifacts.ANFIS_ABLATION_EXPECTED_HOME.as_posix(),
        "XDG_CONFIG_HOME": (
            precommit_artifacts.ANFIS_ABLATION_EXPECTED_XDG_CONFIG_HOME.as_posix()
        ),
        "XDG_CONFIG_DIRS": (
            precommit_artifacts.ANFIS_ABLATION_EXPECTED_XDG_CONFIG_DIRS
        ),
        "DVC_NO_ANALYTICS": "1",
        "GIT_PAGER": "cat",
    }
    with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
        precommit_artifacts.validate_anfis_ablation_registration_invocation(
            args, env=invocation_env
        )
    del invocation_env["GIT_PAGER"]
    precommit_artifacts.validate_anfis_ablation_registration_invocation(
        args, env=invocation_env
    )

    configuration = patch._dvc_configuration_contract(ROOT)
    assert configuration["cache_type"] == "reflink,hardlink,copy"
    assert configuration["no_relink_required"] is True
    assert configuration["local_cache_override_absent"] is True
    assert configuration["autostage_override_absent"] is True

    gitignore = ROOT / patch.GITIGNORE_PATH
    adopted = gitignore.read_bytes()
    base = subprocess.run(
        ["git", "-C", ROOT.as_posix(), "show", f"{P_MZD_COMMIT}:.gitignore"],
        check=True,
        capture_output=True,
    ).stdout
    assert len(base) == patch.P_MZD_GITIGNORE_BYTES == 6_630
    assert hashlib.sha256(base).hexdigest() == patch.P_MZD_GITIGNORE_SHA256
    assert adopted == base
    assert len(adopted) == patch.ADOPTED_GITIGNORE_BYTES == 6_630
    assert hashlib.sha256(adopted).hexdigest() == patch.ADOPTED_GITIGNORE_SHA256
    assert adopted.splitlines().count(patch.GITIGNORE_ENTRY.encode("ascii")) == 1
    assert adopted.endswith(patch.GITIGNORE_SUFFIX)
    before = gitignore.stat()
    assert stat.S_ISREG(before.st_mode)
    assert stat.S_IMODE(before.st_mode) == 0o644
    assert before.st_nlink == 1
    assert subprocess.run(
        ["git", "-C", ROOT.as_posix(), "check-ignore", "--quiet", "--no-index", "models"],
        check=False,
    ).returncode == 0
    assert subprocess.run(
        ["git", "-C", ROOT.as_posix(), "check-ignore", "--quiet", "--no-index", "models.dvc"],
        check=False,
    ).returncode == 1
    assert subprocess.run(
        ["git", "-C", ROOT.as_posix(), "ls-files", "--", "models"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout == ""
    after = gitignore.stat()
    assert (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ) == (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )

    class AlreadyIgnored:
        appended = False

        def _get_gitignore(self, path: str) -> tuple[str, str]:
            del path
            return "/models", gitignore.as_posix()

        def is_ignored(self, path: str) -> bool:
            del path
            return True

        def _add_entry_to_gitignore(self, entry: str, path: str) -> None:
            del entry, path
            self.appended = True

    synthetic = AlreadyIgnored()
    assert Git.ignore(cast(Any, synthetic), (ROOT / "models").as_posix()) is None
    assert synthetic.appended is False
    scm_source = inspect.getsource(Git.ignore)
    assert scm_source.index("if self.is_ignored(path)") < scm_source.index(
        "self._add_entry_to_gitignore(entry, gitignore)"
    )


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

    prefix_root = tmp_path / "prefix-family"
    prefix_root.mkdir()
    _copy_family_tree(prefix_root)
    baseline = precommit_artifacts.snapshot_anfis_ablation_family_bundle(
        repo_root=prefix_root,
        expected_pointer_count=0,
    )
    assert len(baseline) == 80

    cache_sentinel = (
        prefix_root / ".dvc/cache/files/md5/fc/acd5a53249548a36399a611f34e7eb"
    )
    cache_sentinel.parent.mkdir(parents=True)
    cache_sentinel.write_bytes(b"local-cache-is-not-authority\n")
    cache_sentinel.chmod(0o444)
    assert (
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root,
            expected_pointer_count=0,
        )
        == baseline
    )

    for count in range(1, 11):
        _write_pointer(prefix_root, count - 1)
        observed = precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root,
            expected_pointer_count=count,
            _allow_in_progress_prefix=count < 10,
        )
        assert observed == baseline
    assert (
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root,
            expected_pointer_count=10,
        )
        == baseline
    )

    for malformed_count in (True, -1, 11):
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="requires an exact pre/post registration pointer set",
        ):
            precommit_artifacts.snapshot_anfis_ablation_family_bundle(
                repo_root=prefix_root,
                expected_pointer_count=malformed_count,
                _allow_in_progress_prefix=True,
            )
    malformed_policy: Any = 1
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="requires an exact boolean in-progress policy",
    ):
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root,
            expected_pointer_count=10,
            _allow_in_progress_prefix=malformed_policy,
        )

    prediction_root = prefix_root / precommit_artifacts.ANFIS_ABLATION_SELECTION_ROOT
    extra = prediction_root / "A0/foreign.bin"
    extra.write_bytes(b"foreign\n")
    extra.chmod(0o644)
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="exact ten payloads plus canonical pointer prefix",
    ):
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root, expected_pointer_count=10
        )
    extra.unlink()

    payload = prefix_root / precommit_artifacts.ANFIS_ABLATION_SELECTION_PREDICTION_PATHS[0]
    payload.unlink()
    with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root, expected_pointer_count=10
        )
    shutil.copy2(
        ROOT / precommit_artifacts.ANFIS_ABLATION_SELECTION_PREDICTION_PATHS[0],
        payload,
    )

    first_pointer = prefix_root / precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS[0]
    first_pointer.unlink()
    first_pointer.symlink_to(payload.name)
    with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root, expected_pointer_count=10
        )
    first_pointer.unlink()
    _write_pointer(prefix_root, 0)

    hardlink_alias = first_pointer.with_name(f"{first_pointer.name}.foreign")
    os.link(first_pointer, hardlink_alias)
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="pointer must have one hard link",
    ):
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root, expected_pointer_count=10
        )
    hardlink_alias.unlink()

    first_pointer.chmod(0o600)
    with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root, expected_pointer_count=10
        )
    first_pointer.chmod(0o644)

    for raw_path in precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS[3:]:
        (prefix_root / raw_path).unlink()
    _write_pointer(prefix_root, 4)
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="out-of-prefix pointer",
    ):
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root,
            expected_pointer_count=3,
            _allow_in_progress_prefix=True,
        )
    (prefix_root / precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS[4]).unlink()
    second_pointer = prefix_root / precommit_artifacts.ANFIS_ABLATION_SELECTION_POINTER_PATHS[1]
    second_pointer.unlink()
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="post-registration pointer is absent",
    ):
        precommit_artifacts.snapshot_anfis_ablation_family_bundle(
            repo_root=prefix_root,
            expected_pointer_count=3,
            _allow_in_progress_prefix=True,
        )
    _write_pointer(prefix_root, 1)
    with monkeypatch.context() as unowned_prefix:
        transaction = precommit_artifacts._AnfisAblationRegistrationTransaction(
            repo_root=prefix_root
        )
        unowned_prefix.setattr(transaction, "_require_guard", lambda: None)
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="does not own the exact pointer prefix",
        ):
            transaction.verify_family(3, baseline)
    assert cache_sentinel.read_bytes() == b"local-cache-is-not-authority\n"
    rollback_source = inspect.getsource(
        precommit_artifacts._AnfisAblationRegistrationTransaction._rollback
    )
    assert ".dvc/cache" not in rollback_source
    assert "cache/files/md5" not in rollback_source

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

    correction_source = inspect.getsource(mzd._status_order_correction)
    assert correction_source.count("_read_regular_bytes_and_metadata(") == 1
    assert "_file_record(" not in correction_source
    assert "current_payload" in correction_source
    provenance_source = inspect.getsource(patch._manifest_script_provenance_validation)
    assert "manifest.get(\"script\")" in provenance_source
    assert "manifest.get(\"source_code\")" in provenance_source
    assert "[expected_script]" in provenance_source
    assert provenance_source.count("_read_regular_bytes(") == 1

    gitignore_snapshot_source = inspect.getsource(
        precommit_artifacts.snapshot_anfis_ablation_registration_gitignore
    )
    registration_identity_source = inspect.getsource(
        precommit_artifacts._registration_file_identity
    )
    assert ".read_bytes()" not in gitignore_snapshot_source
    assert "sha256_file(path)" not in registration_identity_source
    for token in ("os.open(", "O_NOFOLLOW", "os.fstat("):
        assert token in registration_identity_source
    assert "dir_fd=" in registration_identity_source

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

    with monkeypatch.context() as gitignore_checks:
        repo_root = tmp_path / "gitignore-contract"
        repo_root.mkdir()
        base = subprocess.run(
            ["git", "-C", ROOT.as_posix(), "show", f"{mzd.P_MZC_COMMIT}:.gitignore"],
            check=True,
            capture_output=True,
        ).stdout
        physical = repo_root / patch.GITIGNORE_PATH
        physical.write_bytes(base)
        physical.chmod(0o644)
        h_head = "f" * 40

        def git_blob(repo_root: Path, commit: str, path: Path) -> bytes:
            del repo_root, commit, path
            return base

        def git(repo_root: Path, *arguments: str) -> str:
            del repo_root
            assert arguments[0] == "rev-parse"
            return mzd.P_MZC_GITIGNORE_GIT_OID + "\n"

        gitignore_checks.setattr(mzd, "_git_blob_bytes", git_blob)
        gitignore_checks.setattr(mzd, "_git", git)
        gitignore_checks.setattr(mzd, "_git_head", lambda repo_root: h_head)
        correction = mzd._status_order_correction(repo_root)
        assert correction["gitignore"] == {
            "role": "unchanged_dvc_models_gitignore_contract",
            "path": ".gitignore",
            "bytes": mzd.P_MZC_GITIGNORE_BYTES,
            "sha256": mzd.P_MZC_GITIGNORE_SHA256,
        }
        assert correction["dvc_add_command_count"] == 11
        assert correction["completed_target_count"] == 11
        assert correction["models_add_command_completed"] is True
        assert correction["pointer_count_at_failure"] == 10
        assert correction["exact_path_status_map_matched"] is True
        assert correction["legacy_expected_lines"][-1] == " M models.dvc"
        assert correction["observed_lines"][0] == " M models.dvc"
        assert set(correction["legacy_expected_lines"]) == set(
            correction["observed_lines"]
        )
        assert correction["expected_final_status_map"] == (
            correction["observed_final_status_map"]
        )
        assert correction["pre_stage_validator_reached"] is False
        assert correction["pre_stage_validator_has_same_order_bug"] is True
        assert correction["gitignore_unchanged"] is True
        assert correction["local_dvc_cache_authoritative"] is False

        physical.write_bytes(base + patch.GITIGNORE_SUFFIX)
        with pytest.raises(
            mzd.AnfisAblationDvcRegistrationStatusPatchError,
            match="exact unchanged .gitignore/Git binding drifted",
        ):
            mzd._status_order_correction(repo_root)
        physical.write_bytes(base)
        physical.chmod(0o600)
        with pytest.raises(mzd.AnfisAblationDvcRegistrationStatusPatchError):
            mzd._status_order_correction(repo_root)
        physical.chmod(0o644)
        alias = repo_root / "gitignore-hardlink"
        os.link(physical, alias)
        with pytest.raises(mzd.AnfisAblationDvcRegistrationStatusPatchError):
            mzd._status_order_correction(repo_root)
        alias.unlink()
        target = repo_root / "gitignore-target"
        target.write_bytes(base)
        target.chmod(0o644)
        physical.unlink()
        physical.symlink_to(target.name)
        with pytest.raises(mzd.AnfisAblationDvcRegistrationStatusPatchError):
            mzd._status_order_correction(repo_root)
        gitignore_checks.setattr(
            mzd, "_status_order_correction", lambda repo_root: correction
        )
        porcelain = patch._porcelain_scope_validation()
        assert locker._porcelain_scope_validation(porcelain) == porcelain
        for drifted in (
            {**porcelain, "raw_line_order_authoritative": True},
            {**porcelain, "duplicate_paths_rejected": False},
            {**porcelain, "progress_pointer_counts": list(range(10))},
            {**porcelain, "unexpected": False},
        ):
            with pytest.raises(
                patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
                match="porcelain scope-validation contract drifted",
            ):
                locker._porcelain_scope_validation(drifted)


def test_public_private_loader_api_and_helper_alias_are_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert set(
        inspect.signature(
            patch.load_effective_anfis_ablation_dvc_registration_reproducibility_patch_authority
        ).parameters
    ) == {"audit_current_unpublished", "verify_remote", "repo_root"}
    assert set(
        inspect.signature(
            patch._load_effective_anfis_ablation_dvc_registration_reproducibility_patch_during_registration
        ).parameters
    ) == {"transaction_record", "verify_remote", "repo_root"}
    assert set(
        inspect.signature(patch.require_anfis_ablation_dvc_registration_authority).parameters
    ) == {"verify_remote", "repo_root"}
    assert (
        "_load_effective_anfis_ablation_dvc_registration_reproducibility_patch_during_registration"
        not in patch.__all__
    )

    with monkeypatch.context() as translated_git:
        def fail_nested_git(*args: Any, **kwargs: Any) -> str:
            del args, kwargs
            raise RuntimeError("nested MX failure")

        translated_git.setattr(patch.mx, "_git", fail_nested_git)
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="nested MX failure",
        ):
            patch._git(ROOT, "status")

    with monkeypatch.context() as translated_history:
        def fail_inherited_status(repo_root: Path) -> dict[str, Any]:
            del repo_root
            raise RuntimeError("synthetic inherited status failure")

        translated_history.setattr(
            patch.mzd, "_status_order_correction", fail_inherited_status
        )
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="synthetic inherited status failure",
        ):
            patch._manifest_script_provenance_validation(ROOT)

    with monkeypatch.context() as translated_public:
        def fail_public_loader(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            raise ValueError("synthetic public boundary failure")

        translated_public.setattr(
            patch,
            "_load_effective_anfis_ablation_dvc_registration_reproducibility_patch_authority",
            fail_public_loader,
        )
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="synthetic public boundary failure",
        ):
            patch.load_effective_anfis_ablation_dvc_registration_reproducibility_patch_authority(
                repo_root=tmp_path
            )

    malformed_lock_root = tmp_path / "malformed-lock"
    malformed_lock = malformed_lock_root / patch.DEFAULT_PATCH_LOCK_PATH
    malformed_lock.parent.mkdir(parents=True)
    malformed_lock.write_bytes(b"\xff")
    malformed_lock.chmod(0o644)
    with pytest.raises(
        patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
        match="lock is not valid UTF-8 JSON",
    ):
        patch.load_effective_anfis_ablation_dvc_registration_reproducibility_patch_authority(
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
            "_validate_anfis_ablation_dvc_registration_reproducibility_patch_lock_payload",
            lambda *args, **kwargs: None,
        )
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="companion is not valid UTF-8 JSON",
        ):
            patch.load_effective_anfis_ablation_dvc_registration_reproducibility_patch_authority(
                repo_root=malformed_companion_root
            )

    calls: list[tuple[str, dict[str, Any]]] = []

    def public(**kwargs: Any) -> dict[str, Any]:
        calls.append(("public", kwargs))
        return {"gate": "E0-MZE", "mode": "public"}

    def private(**kwargs: Any) -> dict[str, Any]:
        calls.append(("private", kwargs))
        return {"gate": "E0-MZE", "mode": "private"}

    monkeypatch.setattr(
        patch,
        "load_effective_anfis_ablation_dvc_registration_reproducibility_patch_authority",
        public,
    )
    assert precommit_artifacts._load_effective_anfis_ablation_dvc_registration_authority(
        audit_current_unpublished=False, repo_root=ROOT
    ) == {"gate": "E0-MZE", "mode": "public"}
    transaction = {"mode": "atomic_replace"}
    monkeypatch.setattr(
        patch,
        "_load_effective_anfis_ablation_dvc_registration_reproducibility_patch_during_registration",
        private,
    )
    assert precommit_artifacts._load_effective_anfis_ablation_dvc_registration_authority(
        audit_current_unpublished=True,
        repo_root=ROOT,
        registration_transaction=transaction,
    ) == {"gate": "E0-MZE", "mode": "private"}
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


def test_schema_closes_manifest_provenance_history_family_and_registration_scope() -> None:
    schema = json.loads(
        (ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text(encoding="utf-8")
    )
    definitions = schema["$defs"]

    def resolved_property(name: str) -> dict[str, Any]:
        reference = schema["properties"][name]["$ref"]
        return definitions[reference.removeprefix("#/$defs/")]

    assert schema["properties"]["gate"]["const"] == "E0-MZE"
    assert {
        "base_mzd_authority",
        "historical_h_mzd",
        "manifest_provenance_correction",
    } <= set(schema["required"])
    repository = resolved_property("repository")["properties"]
    assert repository["parent"]["const"] == P_MZD_COMMIT
    assert repository["worktree_scope"]["const"] == (
        "clean_all_50_light_outputs_tracked"
    )
    h_patch = resolved_property("h_patch")["properties"]
    assert h_patch["base_commit"]["const"] == P_MZD_COMMIT
    assert h_patch["parent"]["const"] == P_MZD_COMMIT
    assert h_patch["component_count"]["const"] == 14
    modes_ref = h_patch["components_git_modes"]["$ref"].removeprefix("#/$defs/")
    assert set(definitions[modes_ref]["required"]) == set(patch.PATCH_PATHS)

    base = resolved_property("base_mzd_authority")["properties"]
    assert base["gate"]["const"] == "E0-MZD"
    assert base["p_head"]["const"] == P_MZD_COMMIT
    assert base["h_head"]["const"] == H_MZD_COMMIT
    assert base["effective_loader_called"]["const"] is False
    history = resolved_property("historical_h_mzd")["properties"]
    assert history["gate"]["const"] == "E0-MZD"
    assert history["head"]["const"] == H_MZD_COMMIT
    assert history["parent"]["const"] == mzd.BASE_COMMIT
    assert history["preserved_component_count"]["const"] == 4
    assert history["superseded_component_count"]["const"] == 9

    correction_schema = resolved_property("manifest_provenance_correction")
    correction = patch._manifest_provenance_correction(ROOT)
    assert correction_schema["type"] == "object"
    assert correction_schema["const"] == correction
    assert correction["blocked_gate"] == "R-E0-MZD"
    assert correction["published_p_mzd_head"] == P_MZD_COMMIT
    assert correction["completed_target_count"] == 11
    assert correction["failure_phase"] == "post_stage_reproducibility_manifest_validation"
    assert correction["generic_failure_count"] == 2
    assert correction["failing_manifest_count"] == 1
    assert correction["generic_manifest_validation_unchanged"] is True
    assert correction["rollback_versionable_state_completed"] is True
    assert correction["models_dvc_bytes_and_inode_restored"] is True
    assert correction["models_dvc_mtime_ctime_restored"] is False
    assert correction["models_dvc_metadata_drift_authoritative"] is False
    assert correction["local_dvc_cache_metadata_may_change"] is True

    family = resolved_property("completed_family")["properties"]
    assert family["slot_count"]["const"] == 10
    assert family["final_count"]["const"] == 80
    assert family["light_final_count"]["const"] == 50
    assert family["tracked_light_count"]["const"] == 50
    assert family["untracked_light_count"]["const"] == 0
    assert family["heavy_final_count"]["const"] == 30
    expected_slots = patch._expected_ordered_slots()
    assert family["ordered_slots"]["const"] == expected_slots
    assert definitions["familyAudit"]["properties"]["ordered_slots"]["const"] == (
        expected_slots
    )
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
        patch._validate_anfis_ablation_dvc_registration_reproducibility_patch_lock_payload
    )
    assert "_expected_ordered_slots()" in inspect.getsource(
        patch._validate_verification
    )

    companion = resolved_property("companion_contract")["properties"]
    assert companion["physical_input_count"]["const"] == 20
    assert companion["historical_input_count"]["const"] == 43
    assert companion["output_count"]["const"] == 1
    plan = resolved_property("registration_plan")["properties"]
    invariance_ref = plan["gitignore_invariance"]["$ref"].removeprefix("#/$defs/")
    invariance = definitions[invariance_ref]["properties"]
    assert invariance["path"]["const"] == ".gitignore"
    assert invariance["dvc_ignore_entry"]["const"] == "/models"
    assert invariance["bytes"]["const"] == patch.ADOPTED_GITIGNORE_BYTES
    assert invariance["sha256"]["const"] == patch.ADOPTED_GITIGNORE_SHA256
    assert invariance["git_oid"]["const"] == patch.ADOPTED_GITIGNORE_GIT_OID
    assert invariance["git_mode"]["const"] == "100644"
    assert invariance["physical_mode"]["const"] == "0644"
    assert invariance["nlink"]["const"] == 1
    assert invariance["entry_occurrence_count"]["const"] == 1
    assert invariance["entry_preexisting_before_dvc"]["const"] is True
    assert invariance["scmrepo_ignore_result"]["const"] == (
        "already_ignored_no_write"
    )
    assert invariance["must_remain_byte_and_identity_exact"]["const"] is True
    assert invariance["transaction_record_required"]["const"] is True
    assert invariance["staged_in_registration"]["const"] is False

    porcelain_schema = resolved_property("registration_plan")["properties"][
        "porcelain_scope_validation"
    ]
    porcelain_ref = porcelain_schema["$ref"].removeprefix("#/$defs/")
    porcelain = patch._porcelain_scope_validation()
    assert definitions[porcelain_ref]["const"] == porcelain
    assert porcelain["raw_line_order_authoritative"] is False
    assert porcelain["comparison"] == "exact_unique_path_to_status_mapping"
    assert porcelain["progress_pointer_counts"] == list(range(11))
    assert porcelain["models_status_present_only_after_final_add"] is True
    assert porcelain["canonical_dvc_execution_order_unchanged"] is True

    provenance_schema = plan["manifest_script_provenance_validation"]
    provenance_ref = provenance_schema["$ref"].removeprefix("#/$defs/")
    provenance = patch._manifest_script_provenance_validation(ROOT)
    assert definitions[provenance_ref]["const"] == provenance
    assert provenance["manifest_count"] == 10
    assert provenance["historical_script_record_count"] == 1
    assert provenance["current_script_record_count"] == 9
    assert provenance["generic_manifest_validation_unchanged"] is True
    assert provenance["generic_validation_runs_first"] is True
    assert provenance["exact_r_scope_required"] is True
    assert len(provenance["exact_generic_fail_multiset"]) == 2
    assert len(provenance["slot_authorities"]) == 10
    assert provenance["historical_script"]["git_mode"] == "100644"
    assert provenance["current_script"]["git_mode"] == "100644"
    assert all(
        record["trainer_git_mode"] == "100644"
        and type(record["base_seed"]) is int
        for record in provenance["slot_authorities"]
    )

    missing_ref = plan["missing_pointer_validation"]["$ref"].removeprefix(
        "#/$defs/"
    )
    missing = definitions[missing_ref]["properties"]
    assert missing["count"]["const"] == 10
    assert missing["unique_count"]["const"] == 10
    assert missing["set_exact"]["const"] is True
    assert missing["discovery_order"]["const"] == "lexical_path"
    assert missing["canonical_execution_order"]["const"] == (
        "alternating_a0_a1_within_seed"
    )
    namespace_ref = plan["in_progress_namespace_validation"]["$ref"].removeprefix(
        "#/$defs/"
    )
    namespace = definitions[namespace_ref]["properties"]
    assert namespace["payload_count"]["const"] == 10
    assert namespace["public_pointer_counts"]["const"] == [0, 10]
    assert namespace["transaction_pointer_counts"]["const"] == list(range(11))
    assert namespace["tree_policy"]["const"] == (
        "exact_ten_payloads_plus_canonical_pointer_prefix"
    )
    assert namespace["transaction_guard_required"]["const"] is True
    assert namespace["transaction_pointer_ownership_required"]["const"] is True
    scope_ref = plan["registration_git_scope"]["$ref"].removeprefix("#/$defs/")
    registration = definitions[scope_ref]["properties"]
    assert registration["added"]["const"] == 10
    assert registration["modified"]["const"] == 1
    assert registration["deleted"]["const"] == 0
    assert registration["path_count"]["const"] == 11
    assert definitions["focusedTests"]["properties"]["test_count"]["const"] == 212
    assert patch.FOCUSED_TEST_COUNT == 212
    patch.preflight_anfis_ablation_dvc_registration_reproducibility_patch_schema(
        repo_root=ROOT
    )

def test_generic_precommit_manifest_dialect_is_one_one_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    lock = patch.DEFAULT_PATCH_LOCK_PATH
    companion = patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    script = Path("src/synthetic_e0_mze_locker.py")
    source = Path("configs/synthetic_e0_mze_input.json")
    for path in (lock, companion, script, source):
        path.parent.mkdir(parents=True, exist_ok=True)
    script.write_bytes(b"# synthetic E0-MZE locker\n")
    source.write_bytes(b"{}\n")
    lock.write_bytes(b'{"gate":"E0-MZE","status":"locked_unpublished"}\n')
    companion.write_text(
        json.dumps(
            {
                "manifest_version": "synthetic_e0_mze_lock_manifest_v1",
                "status": "completed",
                "gate": "E0-MZE",
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

    canonical = dict(
        precommit_artifacts.ANFIS_ABLATION_REGISTRATION_MANIFEST_SCRIPT_PROVENANCE
    )
    validated = (
        precommit_artifacts.validate_anfis_ablation_registration_manifest_script_provenance(
            repo_root=ROOT,
            provenance=dict(reversed(tuple(canonical.items()))),
        )
    )
    assert len(validated) == 10
    assert [record.manifest_path for record in validated] == list(
        precommit_artifacts.ANFIS_ABLATION_MANIFEST_PATHS
    )
    assert sum(
        record.commit == patch.HISTORICAL_TRAINER_COMMIT for record in validated
    ) == 1
    assert sum(record.commit == patch.CURRENT_TRAINER_COMMIT for record in validated) == 9
    real_subprocess_run = precommit_artifacts.subprocess.run
    with monkeypatch.context() as nonancestor:
        def reject_ancestor(
            arguments: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[bytes]:
            if "merge-base" in arguments:
                return subprocess.CompletedProcess(arguments, 1, b"", b"")
            return cast(
                subprocess.CompletedProcess[bytes],
                real_subprocess_run(arguments, **kwargs),
            )

        nonancestor.setattr(precommit_artifacts.subprocess, "run", reject_ancestor)
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="not an exact P-MZD ancestor",
        ):
            precommit_artifacts.validate_anfis_ablation_registration_manifest_script_provenance(
                repo_root=ROOT, provenance=canonical
            )
    with monkeypatch.context() as missing_object:
        def reject_tree(
            arguments: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[bytes]:
            if "ls-tree" in arguments:
                return subprocess.CompletedProcess(arguments, 128, b"", b"missing")
            return cast(
                subprocess.CompletedProcess[bytes],
                real_subprocess_run(arguments, **kwargs),
            )

        missing_object.setattr(precommit_artifacts.subprocess, "run", reject_tree)
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="commit/mode/blob binding drifted",
        ):
            precommit_artifacts.validate_anfis_ablation_registration_manifest_script_provenance(
                repo_root=ROOT, provenance=canonical
            )

    historical_path = patch.HISTORICAL_MANIFEST_PATH.as_posix()
    historical = canonical[historical_path]
    current_path = next(path for path in canonical if path != historical_path)
    current = canonical[current_path]
    malformed_maps: list[dict[str, Any]] = [
        {key: value for key, value in canonical.items() if key != historical_path},
        {**canonical, "reports/closure_v1/02_models/A2/extra.json": historical},
        {**canonical, current_path: historical},
        {**canonical, historical_path: current, current_path: historical},
    ]
    for field, value in (
        ("manifest_path", current_path),
        ("script_path", "src/experiments/foreign.py"),
        ("commit", patch.CURRENT_TRAINER_COMMIT),
        ("blob_oid", patch.CURRENT_TRAINER_GIT_OID),
        ("git_mode", "100755"),
        ("bytes", True),
        ("bytes", patch.HISTORICAL_TRAINER_BYTES + 1),
        ("sha256", patch.CURRENT_TRAINER_SHA256),
    ):
        malformed_maps.append(
            {**canonical, historical_path: replace(historical, **{field: value})}
        )
    malformed_maps.append({**canonical, historical_path: cast(Any, historical.__dict__)})
    for candidate in malformed_maps:
        with pytest.raises(
            precommit_artifacts.DeferredDvcTargetError,
            match="manifest script provenance",
        ):
            precommit_artifacts.validate_anfis_ablation_registration_manifest_script_provenance(
                repo_root=ROOT,
                provenance=candidate,
            )

    drift_root = tmp_path / "source-code-drift"
    drift_manifest = drift_root / patch.HISTORICAL_MANIFEST_PATH
    drift_manifest.parent.mkdir(parents=True)
    canonical_manifest = json.loads(
        (ROOT / patch.HISTORICAL_MANIFEST_PATH).read_text()
    )
    canonical_script = canonical_manifest["script"]
    manifest_drifts = [
        {**canonical_manifest, "script": {**canonical_script, "role": "foreign"}},
        {
            **canonical_manifest,
            "script": {**canonical_script, "path": "src/experiments/foreign.py"},
        },
        {**canonical_manifest, "script": {**canonical_script, "bytes": True}},
        {
            **canonical_manifest,
            "script": {**canonical_script, "sha256": patch.CURRENT_TRAINER_SHA256},
        },
        {**canonical_manifest, "script": {**canonical_script, "extra": False}},
        {
            **canonical_manifest,
            "source_code": [
                {**canonical_script, "sha256": patch.CURRENT_TRAINER_SHA256}
            ],
        },
        {**canonical_manifest, "source_code": [canonical_script, canonical_script]},
        {**canonical_manifest, "source_code": canonical_script},
        {key: value for key, value in canonical_manifest.items() if key != "source_code"},
    ]
    with monkeypatch.context() as source_code_drift:
        real_run = precommit_artifacts.subprocess.run

        def ancestry_only(
            arguments: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[bytes]:
            if "merge-base" in arguments:
                return subprocess.CompletedProcess(arguments, 0, b"", b"")
            return cast(subprocess.CompletedProcess[bytes], real_run(arguments, **kwargs))

        source_code_drift.setattr(
            precommit_artifacts.subprocess, "run", ancestry_only
        )
        for drifted_payload in manifest_drifts:
            drift_manifest.write_bytes(patch._canonical_json(drifted_payload))
            drift_manifest.chmod(0o644)
            with pytest.raises(
                precommit_artifacts.DeferredDvcTargetError,
                match="trainer/source_code records drifted",
            ):
                precommit_artifacts.validate_anfis_ablation_registration_manifest_script_provenance(
                    repo_root=drift_root,
                    provenance=canonical,
                )

    expected_failures = list(
        precommit_artifacts._expected_anfis_ablation_historical_script_findings()
    )
    adopted = (
        precommit_artifacts.adopt_anfis_ablation_registration_manifest_provenance_findings(
            list(reversed(expected_failures)), repo_root=ROOT
        )
    )
    assert not precommit_artifacts.has_failing_findings(adopted)
    assert [finding.level for finding in adopted] == ["ok"]
    replacement = patch._manifest_script_provenance_validation(ROOT)[
        "replacement_finding"
    ]
    assert {
        "level": adopted[0].level,
        "check": adopted[0].check,
        "path": adopted[0].path,
        "message": adopted[0].message,
    } == replacement

    monkeypatch.setattr(
        precommit_artifacts,
        "validate_anfis_ablation_registration_manifest_script_provenance",
        lambda **kwargs: validated,
    )
    variants = (
        expected_failures[:1],
        [expected_failures[0], expected_failures[0]],
        [
            *expected_failures,
            precommit_artifacts.ReproducibilityFinding(
                "fail", "manifest", "foreign", "third failure"
            ),
        ],
        [replace(expected_failures[0], message="altered"), expected_failures[1]],
        [
            *expected_failures,
            precommit_artifacts.ReproducibilityFinding(
                "warn", "manifest", historical_path, "warning"
            ),
        ],
    )
    for variant in variants:
        observed = (
            precommit_artifacts.adopt_anfis_ablation_registration_manifest_provenance_findings(
                list(variant), repo_root=ROOT
            )
        )
        assert precommit_artifacts.has_failing_findings(observed)
    generic_source = inspect.getsource(precommit_artifacts.reproducibility_checks)
    wrapper_source = inspect.getsource(
        precommit_artifacts.anfis_ablation_registration_reproducibility_checks
    )
    assert "validate_experiment_manifests(" in generic_source
    assert "adopt_anfis_ablation" not in generic_source
    assert "generic = reproducibility_checks(" in wrapper_source
    assert "adopt_anfis_ablation_registration_manifest_provenance_findings" in (
        wrapper_source
    )
    registration_source = inspect.getsource(
        precommit_artifacts._run_anfis_ablation_model_family_registration
    )
    assert registration_source.count(
        "anfis_ablation_registration_reproducibility_checks("
    ) == 1
    assert registration_source.index(
        "validate_anfis_ablation_registration_staged_scope(staged_status)"
    ) < registration_source.index(
        "anfis_ablation_registration_reproducibility_checks("
    )
    assert "ANFIS_ABLATION_R_MZE_STAGED_SCOPE" in registration_source
    assert "R-E0-MZE" in registration_source
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="R-E0-MZE staged scope",
    ):
        precommit_artifacts.anfis_ablation_registration_reproducibility_checks(
            staged_status="A\tforeign.txt\n",
            selected_dvc_paths=[],
            artifacts=[],
            max_manifest_hash_bytes=1_000_000,
            verify_manifest_inputs=True,
            repo_root=ROOT,
        )


def test_check_only_is_a_nonwriting_namespace_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = {"status": "schema_preflight_passed"}
    repository = {"head": "f" * 40}
    provenance_correction = {
        "status": "adopted_exact_historical_manifest_script_provenance_failure",
        "dvc_add_command_count": 11,
        "completed_target_count": 11,
        "generic_failure_count": 2,
        "local_dvc_cache_authoritative": False,
    }
    porcelain = patch._porcelain_scope_validation()
    provenance_validation = {"manifest_count": 10, "exact_r_scope_required": True}
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_dvc_registration_reproducibility_patch_schema",
        lambda: schema,
    )
    monkeypatch.setattr(
        patch,
        "_manifest_provenance_correction",
        lambda repo_root: provenance_correction,
    )
    monkeypatch.setattr(
        patch,
        "_manifest_script_provenance_validation",
        lambda repo_root: provenance_validation,
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_dvc_registration_reproducibility_patch_prelock_state",
        lambda **kwargs: {
            "repository": repository,
            "h_patch": {"component_count": 14},
            "manifest_provenance_correction": provenance_correction,
            "companion_contract": {
                "physical_input_count": 20,
                "historical_input_count": 43,
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
            "registration_plan": {
                "registration_git_scope": {"path_count": 11},
                "missing_pointer_validation": {
                    "count": 10,
                    "unique_count": 10,
                    "set_exact": True,
                    "discovery_order": "lexical_path",
                    "canonical_execution_order": (
                        "alternating_a0_a1_within_seed"
                    ),
                },
                "in_progress_namespace_validation": (
                    patch._in_progress_namespace_validation()
                ),
                "porcelain_scope_validation": porcelain,
                "manifest_script_provenance_validation": provenance_validation,
            },
            "prelock": {"selection_pointer_present_count": 0},
        },
    )
    result = locker.check_only()
    assert result["status"] == "ready_to_lock"
    assert result["gate"] == "E0-MZE"
    assert result["schema_preflight"] == schema
    assert result["repository"] == repository
    assert result["base_p_mzd_commit"] == P_MZD_COMMIT
    assert result["missing_pointer_validation"] == {
        "count": 10,
        "unique_count": 10,
        "set_exact": True,
        "discovery_order": "lexical_path",
        "canonical_execution_order": "alternating_a0_a1_within_seed",
    }
    assert result["in_progress_namespace_validation"] == (
        patch._in_progress_namespace_validation()
    )
    assert result["porcelain_scope_validation"] == porcelain
    assert result["manifest_provenance_correction"] == provenance_correction
    assert result["manifest_script_provenance_validation"] == provenance_validation
    for drifted in (
        {**result["missing_pointer_validation"], "count": True},
        {**result["missing_pointer_validation"], "set_exact": 1},
        {**result["missing_pointer_validation"], "unexpected": False},
    ):
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="missing-pointer validation contract drifted",
        ):
            locker._missing_pointer_validation(drifted)
    for drifted in (
        {
            **result["in_progress_namespace_validation"],
            "transaction_pointer_counts": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        },
        {
            **result["in_progress_namespace_validation"],
            "transaction_guard_required": 1,
        },
        {**result["in_progress_namespace_validation"], "unexpected": False},
    ):
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="in-progress namespace validation contract drifted",
        ):
            locker._in_progress_namespace_validation(drifted)
    for drifted in (
        {**provenance_correction, "completed_target_count": True},
        {**provenance_correction, "generic_failure_count": 3},
        {**provenance_correction, "unexpected": False},
    ):
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="manifest provenance incident/correction contract drifted",
        ):
            locker._manifest_provenance_correction(drifted)
    for drifted in (
        {**provenance_validation, "manifest_count": True},
        {**provenance_validation, "exact_r_scope_required": False},
        {**provenance_validation, "unexpected": False},
    ):
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="manifest script provenance validation contract drifted",
        ):
            locker._manifest_script_provenance_validation(drifted)
    for drifted in (
        {**porcelain, "raw_line_order_authoritative": True},
        {**porcelain, "progress_pointer_counts": list(range(10))},
        {**porcelain, "unexpected": False},
    ):
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="porcelain scope-validation contract drifted",
        ):
            locker._porcelain_scope_validation(drifted)
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
        "component_count": 14,
        "physical_input_count": 20,
        "historical_input_count": 43,
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
        return {"gate": "E0-MZE"}, {"status": "completed"}

    def load(**kwargs: Any) -> dict[str, Any]:
        calls.append(("load", kwargs))
        return {"gate": "E0-MZE", "status": "effective"}

    monkeypatch.setattr(
        patch,
        "publish_anfis_ablation_dvc_registration_reproducibility_patch_lock_bundle",
        publish,
    )
    monkeypatch.setattr(
        patch,
        "load_effective_anfis_ablation_dvc_registration_reproducibility_patch_authority",
        load,
    )
    locked = locker.execute_lock()
    effective = locker.check_effective()
    assert calls == [("publish", {}), ("load", {"verify_remote": True})]
    assert locked["status"] == "locked_unpublished"
    assert locked["gate"] == "E0-MZE"
    assert locked["lock"] == {"gate": "E0-MZE"}
    assert locked["companion"] == {"status": "completed"}
    assert effective == {"gate": "E0-MZE", "status": "effective"}


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
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError("closed")
        ),
    )
    assert locker.main(["--check-only"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "closed\n"

    monkeypatch.setattr(
        locker,
        "check_only",
        lambda: (_ for _ in ()).throw(RuntimeError("foreign")),
    )
    with pytest.raises(RuntimeError, match="foreign"):
        locker.main(["--check-only"])


def test_locker_publisher_surface_and_p_git_binding_are_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert set(
        inspect.signature(
            patch.publish_anfis_ablation_dvc_registration_reproducibility_patch_lock_bundle
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
        patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
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
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
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
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
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
        patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
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
    payload = {"gate": "E0-MZE", "status": "locked_unpublished"}
    companion = {
        "manifest_version": "synthetic_e0_mze_lock_manifest_v1",
        "status": "completed",
        "completion_marker_written_last": True,
    }
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_dvc_registration_reproducibility_patch_prelock_state",
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
        "run_anfis_ablation_dvc_registration_reproducibility_patch_verification",
        lambda **kwargs: {"status": "passed"},
    )
    monkeypatch.setattr(
        patch,
        "build_anfis_ablation_dvc_registration_reproducibility_patch_lock_payload",
        lambda *args, **kwargs: payload,
    )
    monkeypatch.setattr(
        patch,
        "validate_anfis_ablation_dvc_registration_reproducibility_patch_lock_payload",
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
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="synthetic companion failure",
        ):
            patch.publish_anfis_ablation_dvc_registration_reproducibility_patch_lock_bundle(
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
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="lock namespace is occupied",
        ):
            patch.publish_anfis_ablation_dvc_registration_reproducibility_patch_lock_bundle(
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
            "collect_anfis_ablation_dvc_registration_reproducibility_patch_prelock_state",
            collect,
        )
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="guarded prelock state drifted",
        ):
            patch.publish_anfis_ablation_dvc_registration_reproducibility_patch_lock_bundle(
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
                raise patch.AnfisAblationDvcRegistrationReproducibilityPatchError(
                    f"E0-MZE family physical snapshot drifted {context}"
                )

        post_lock.setattr(patch.mt, "_publish_bytes_no_clobber", publish_then_drift)
        post_lock.setattr(patch, "_require_family_physical_snapshot", require_snapshot)
        with pytest.raises(
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="after lock publication",
        ):
            patch.publish_anfis_ablation_dvc_registration_reproducibility_patch_lock_bundle(
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
            patch.AnfisAblationDvcRegistrationReproducibilityPatchError,
            match="owned output bytes drifted after companion publication",
        ):
            patch.publish_anfis_ablation_dvc_registration_reproducibility_patch_lock_bundle(
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


def test_document_closes_manifest_provenance_registration_and_external_barriers() -> None:
    document = (
        ROOT
        / "docs/closure_v1/ANFIS_ABLATION_DVC_REGISTRATION_REPRODUCIBILITY_PATCH.md"
    ).read_text(encoding="utf-8")
    for token in (
        P_MZD_COMMIT,
        H_MZD_COMMIT,
        patch.HISTORICAL_TRAINER_COMMIT,
        patch.HISTORICAL_TRAINER_GIT_OID,
        patch.HISTORICAL_TRAINER_SHA256,
        patch.CURRENT_TRAINER_COMMIT,
        patch.CURRENT_TRAINER_GIT_OID,
        patch.CURRENT_TRAINER_SHA256,
        "exact two-item `FAIL` multiset",
        "generic manifest validator",
        "source_code",
        "one historical record and nine current",
        "anfis_ablation_manifest_provenance",
        "Validated exact one historical and nine current trainer Git blobs.",
        "`models` eleventh and last",
        "`9M+5A`",
        "`10A+1M`",
        "80 regular single-link `0644` finals",
        "50 tracked lightweight files",
        "20 current physical inputs and 43",
        "34 records inherited from",
        "nine H-E0-MZD blobs",
        "never authority",
        "mtime/ctime",
        "metadata touches",
        "Foreign paths",
        "dvc add --no-relink",
        "GIT_PAGER",
        "DVC push",
    ):
        assert token in document
    assert patch.DEFAULT_PATCH_LOCK_PATH.as_posix() in document
    assert patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix() in document
