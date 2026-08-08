from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.experiments import closure_anfis_ablation_sequence_development_patch as patch
from src.experiments import (
    lock_closure_anfis_ablation_sequence_development_patch as locker,
)


def _record(path: str, role: str, marker: int) -> dict[str, Any]:
    return {
        "path": path,
        "role": role,
        "bytes": marker + 1,
        "sha256": f"{marker % 16:x}" * 64,
    }


def _command_evidence(
    command: tuple[str, ...],
    stdout: str,
    stderr: str = "",
) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": len(stderr.splitlines()),
    }


def _verification_bundle(schema_preflight: dict[str, Any]) -> dict[str, Any]:
    focused = _command_evidence(
        patch.FOCUSED_TEST_COMMAND,
        f"dots\n{patch.FOCUSED_TEST_COUNT} passed in 1.00s\n",
    )
    focused.update(
        {
            "test_count": patch.FOCUSED_TEST_COUNT,
            "skipped_count": 0,
            "deselected_count": 0,
        }
    )
    return {
        "schema_preflight": schema_preflight,
        "full_type_check": _command_evidence(
            patch.TYPE_CHECK_COMMAND, "All checks passed!\n"
        ),
        "focused_tests": focused,
        "poetry_check": _command_evidence(patch.POETRY_CHECK_COMMAND, "All set!\n"),
        "publication_guard": _command_evidence(
            patch.PUBLICATION_GUARD_COMMAND,
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n",
        ),
        "git_diff_check": _command_evidence(patch.DIFF_CHECK_COMMAND, ""),
    }


def _runtime() -> dict[str, Any]:
    return yaml.safe_load(
        (locker.PROJECT_ROOT / patch.DEFAULT_RUNTIME_PATH).read_text(encoding="utf-8")
    )


def _schema() -> dict[str, Any]:
    return json.loads(
        (locker.PROJECT_ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text(
            encoding="utf-8"
        )
    )


def _patch_locker_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(locker, "PROJECT_ROOT", root)
    monkeypatch.setattr(
        locker,
        "OUTPUT_GUARD_DIRECTORY",
        root / "tmp" / "closure_v1_anfis_ablation_sequence_development_patch",
    )
    monkeypatch.setattr(
        locker,
        "OUTPUT_GUARD_PATH",
        root
        / "tmp"
        / "closure_v1_anfis_ablation_sequence_development_patch"
        / "lock_bundle.guard",
    )


def _synthetic_lock_payload(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    h_head = "1" * 40
    components = [
        _record(path, patch.PATCH_COMPONENT_ROLES[path], index)
        for index, path in enumerate(patch.PATCH_PATHS)
    ]
    physical_inputs = [
        _record(path, patch.PHYSICAL_INPUT_ROLES[path], index + len(components))
        for index, path in enumerate(patch.PHYSICAL_INPUT_PATHS)
    ]
    runtime = patch.load_and_validate_anfis_ablation_sequence_development_runtime(
        verify_physical_pins=False
    )
    runtime_record = next(
        record
        for record in components
        if record["path"] == patch.DEFAULT_RUNTIME_PATH.as_posix()
    )
    prelock = {
        "repository": {
            "head": h_head,
            "parent": patch.PATCH_BASE_COMMIT,
            "branch": "main",
            "tracking_ref": patch.PUBLISHED_REF,
            "tracking_head": h_head,
            "remote_head": h_head,
            "remote_observation_mode": "live_remote_main_verified",
            "worktree_status": "clean",
        },
        "h_patch": {
            "base_commit": patch.PATCH_BASE_COMMIT,
            "added_count": 10,
            "modified_count": 0,
            "deleted_count": 0,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "components": components,
            "components_sha256": patch._record_digest(components),
        },
        "runtime_contract": patch._runtime_contract_binding(
            runtime,
            runtime_record=runtime_record,
            physical_inputs=physical_inputs,
        ),
        "prelock": patch._sealed_prelock_binding(runtime),
    }
    preflight = patch.preflight_anfis_ablation_sequence_development_patch_schema()
    payload = patch.build_anfis_ablation_sequence_development_patch_lock_payload(
        prelock,
        _verification_bundle(preflight),
        created_at_utc="2026-08-07T12:00:00+00:00",
    )

    def fake_git(*args: str, repo_root: Path | None = None) -> str:
        del repo_root
        if args == ("rev-parse", "HEAD"):
            return h_head
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("rev-parse", patch.PUBLISHED_REF):
            return h_head
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return ""
        raise AssertionError(f"Unexpected synthetic Git command: {args}")

    monkeypatch.setattr(patch, "_git", fake_git)
    monkeypatch.setattr(
        patch,
        "_single_parent",
        lambda commit, repo_root=None: patch.PATCH_BASE_COMMIT,
    )
    monkeypatch.setattr(
        patch,
        "_live_remote_main_head",
        lambda repo_root=None: h_head,
    )
    monkeypatch.setattr(
        patch,
        "_reconstruct_h_components",
        lambda value, repo_root=None: copy.deepcopy(components),
    )
    monkeypatch.setattr(
        patch,
        "_verify_runtime_physical_pins",
        lambda value, repo_root=None: copy.deepcopy(physical_inputs),
    )
    return payload


def test_runtime_freezes_exact_h_scope_and_future_p_scope() -> None:
    runtime = _runtime()
    scope = runtime["patch_scope"]
    assert scope["exact_added_count"] == 10
    assert scope["exact_modified_count"] == 0
    assert scope["exact_deleted_count"] == 0
    assert tuple(sorted(scope["paths"])) == patch.PATCH_PATHS
    assert len(set(scope["paths"])) == 10
    assert patch.DEFAULT_PATCH_LOCK_PATH.as_posix() == (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_sequence_development_patch_lock.json"
    )
    assert patch.DEFAULT_PATCH_MANIFEST_PATH.as_posix() == (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_sequence_development_patch_lock_manifest.json"
    )


def test_runtime_freezes_e6_raw_order_masks_and_seasons() -> None:
    runtime = _runtime()
    raw = runtime["features"]["raw_no_current"]
    assert raw["mean_columns"] == [
        "mean_TP_ugL",
        "mean_TN_ugL",
        "mean_DO_mgL",
        "mean_pH",
        "mean_turbidity_NTU",
        "mean_secchi_depth_m",
        "mean_temperature_C",
    ]
    expected_values = [f"x_{name}" for name in raw["mean_columns"]]
    expected_masks = [f"mask_{name}" for name in raw["mean_columns"]]
    seasons = runtime["features"]["common"]["seasonality"]["input_columns"]
    assert raw["serialized_value_columns"] == expected_values
    assert raw["observed_mask_columns"] == expected_masks
    assert raw["exact_input_order"] == expected_values + expected_masks + seasons
    assert raw["observed_mask_formula"] == (
        "corresponding_mean_is_finite_and_corresponding_n_obs_is_finite_and_"
        "greater_than_zero"
    )
    assert raw["missing_mean_serialization"] == (
        "structural_zero_float32_with_corresponding_mask_zero"
    )
    assert raw["structural_zero_is_scientific_imputation"] is False
    assert raw["exact_input_dimension"] == 18
    assert raw["logical_tensor_shape"] == [12, 18]


def test_runtime_freezes_same_seed_a1_state_order() -> None:
    runtime = _runtime()
    adaptive = runtime["features"]["adaptive_state"]
    assert adaptive["upstream_seed_policy"] == "same_seed_slot"
    assert adaptive["exact_state_order"] == list(patch.A1_STATE_COLUMNS)
    assert adaptive["state_source_mapping"] == patch.A1_STATE_SOURCE_MAPPING
    assert adaptive["exact_state_dimension"] == 9
    assert adaptive["full_or_current_chla_state"] == "forbidden"
    assert runtime["features"]["models"]["A1"] == {
        "input_components": [
            "raw_no_current",
            "seasonality",
            "adaptive_state_same_seed",
        ],
        "exact_input_dimension": 27,
        "logical_tensor_shape": [12, 27],
        "upstream_state_seed": "same_as_base_seed",
    }


def test_runtime_freezes_one_row_per_origin_without_target_identity() -> None:
    runtime = _runtime()
    denominators = runtime["denominators"]
    bundles = runtime["bundles"]
    assert denominators["common_origin_rows"] == 29_196
    assert denominators["intent_origins"] == 9_732
    assert denominators["development_locations"] == 353
    assert denominators["horizons_months"] == [1, 2, 3]
    assert denominators["intent_origins_by_role"] == {
        "training": 8_352,
        "model_selection": 1_061,
        "calibration_threshold": 319,
    }
    assert bundles["exact_bundle_count"] == 6
    assert bundles["A0"]["deterministic_shared_bundle"] is True
    assert bundles["A1"]["base_seeds"] == list(patch.REGISTERED_SEEDS)
    identities = bundles["identity_columns"]
    for forbidden in (
        "target_year_month",
        "evaluation_unit_id",
        "horizon_months",
    ):
        assert forbidden not in identities
    parquet_contract = bundles["parquet_contract"]
    identity_fields = parquet_contract["identity_columns"]
    identity_names = [field["name"] for field in identity_fields]
    assert identity_names == list(patch.IDENTITY_COLUMNS)
    assert len(identity_names) == len(set(identity_names)) == 17
    assert parquet_contract["exact_rows_per_bundle"] == 9_732
    assert parquet_contract["row_unit"] == "one_row_per_common_origin"
    assert parquet_contract["forbidden_row_columns"] == [
        "evaluation_unit_id",
        "target_year_month",
        "horizon_months",
    ]
    assert parquet_contract["horizons_manifest_only"] == [1, 2, 3]
    assert parquet_contract["model_channel_order"]["A0"] == list(
        patch.A0_INPUT_COLUMNS
    )
    assert parquet_contract["model_channel_order"]["A1"] == list(
        patch.A1_INPUT_COLUMNS
    )
    assert parquet_contract["channel_arrow_type"] == (
        "fixed_size_list_float32_length_12"
    )
    assert parquet_contract["channel_parent_nullable"] is True
    assert parquet_contract["channel_child_nullable"] is False
    assert parquet_contract["seed_policy"] == {
        "A0": {"base_seed": None, "upstream_state_seed": None},
        "A1": {
            "base_seed": "registered_seed",
            "upstream_state_seed": "equal_base_seed",
        },
    }
    assert runtime["features"]["common"]["target_columns"] == []
    assert runtime["features"]["common"]["target_scan_authorized"] is False


def test_runtime_freezes_closed_six_bundle_namespace() -> None:
    runtime = _runtime()
    outputs = runtime["outputs"]
    assert outputs["exact_final_path_count"] == 18
    assert outputs["exact_pointer_path_count"] == 6
    assert len(patch.ABLATION_SEQUENCE_FINAL_PATHS) == 18
    assert len(set(patch.ABLATION_SEQUENCE_FINAL_PATHS)) == 18
    assert len(patch.ABLATION_SEQUENCE_POINTER_PATHS) == 6
    assert len(set(patch.ABLATION_SEQUENCE_POINTER_PATHS)) == 6
    assert len(patch.ABLATION_SEQUENCE_GUARD_PATHS) == 6
    assert patch.LOCKER_GUARD_PATH.as_posix() == (
        "tmp/closure_v1_anfis_ablation_sequence_development_patch/"
        "lock_bundle.guard"
    )
    assert locker.OUTPUT_GUARD_PATH == locker.PROJECT_ROOT / patch.LOCKER_GUARD_PATH
    transaction = outputs["transaction"]
    assert transaction == {
        "exclusive_guard": True,
        "parent_walk": "dirfd_no_follow",
        "temporary_sibling": True,
        "final_publication": "hardlink_no_clobber",
        "rollback": "owned_inode_only",
        "manifest_written_last": True,
    }


def test_runtime_and_schema_keep_all_lateral_authorizations_false() -> None:
    runtime = _runtime()
    schema = _schema()
    assert runtime["authorizations"] == patch.UNPUBLISHED_AUTHORIZATIONS
    authorizations = schema["$defs"]["authorizations"]
    assert set(authorizations["required"]) == set(patch.UNPUBLISHED_AUTHORIZATIONS)
    for name, expected in patch.UNPUBLISHED_AUTHORIZATIONS.items():
        assert authorizations["properties"][name]["const"] is expected
    assert runtime["seals"] == patch.PATCH_SEALS
    schema_seals = schema["$defs"]["seals"]
    assert set(schema_seals["required"]) == set(patch.PATCH_SEALS)
    for name, expected in patch.PATCH_SEALS.items():
        assert schema_seals["properties"][name]["const"] == expected


def test_schema_freezes_topology_and_namespace_counts() -> None:
    schema = _schema()
    h_patch = schema["$defs"]["hPatch"]["properties"]
    assert h_patch["added_count"]["const"] == 10
    assert h_patch["modified_count"]["const"] == 0
    assert h_patch["deleted_count"]["const"] == 0
    runtime_contract = schema["$defs"]["runtimeContract"]["properties"]
    assert runtime_contract["physical_input_count"]["const"] == 44
    namespace = schema["$defs"]["namespaceEvidence"]["properties"]
    assert namespace["final_path_count"]["const"] == 18
    assert namespace["temporary_path_count"]["const"] == 18
    assert namespace["pointer_path_count"]["const"] == 6
    assert namespace["pointer_temporary_path_count"]["const"] == 6
    assert namespace["guard_path_count"]["const"] == 6


def test_schema_preflight_and_runtime_validator_accept_closed_contract() -> None:
    preflight = patch.preflight_anfis_ablation_sequence_development_patch_schema()
    assert preflight["supported_subset_verified"] is True
    assert preflight["minimum_keyword_absent"] is True
    assert preflight["format_keyword_absent"] is True
    runtime = patch.load_and_validate_anfis_ablation_sequence_development_runtime(
        verify_physical_pins=False
    )
    assert runtime["gate"] == "E0-MS"
    assert runtime["status"] == "ready_to_lock"


def test_physical_reader_rejects_symlink_ancestor(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "input.bin").write_bytes(b"foreign")
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError,
        match="symlinked|unavailable",
    ):
        patch._read_regular_bytes(Path("linked/input.bin"), repo_root=tmp_path)


def test_physical_reader_rejects_named_replacement_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "input.bin"
    target.write_bytes(b"a" * (2 * 1024 * 1024))
    real_read = patch.os.read
    replaced = False

    def replace_after_first_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        chunk = real_read(descriptor, size)
        if not replaced and chunk:
            replaced = True
            target.unlink()
            target.write_bytes(b"foreign")
        return chunk

    monkeypatch.setattr(patch.os, "read", replace_after_first_read)
    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError,
        match="changed during anchored read",
    ):
        patch._read_regular_bytes(Path("input.bin"), repo_root=tmp_path)
    assert target.read_bytes() == b"foreign"


def test_companion_binds_fifty_four_unique_physical_inputs_and_locker() -> None:
    components = [
        _record(path, patch.PATCH_COMPONENT_ROLES[path], index)
        for index, path in enumerate(patch.PATCH_PATHS)
    ]
    physical_inputs = [
        _record(path, patch.PHYSICAL_INPUT_ROLES[path], index + len(components))
        for index, path in enumerate(patch.PHYSICAL_INPUT_PATHS)
    ]
    payload = {
        "h_patch": {
            "base_commit": patch.PATCH_BASE_COMMIT,
            "added_count": 10,
            "modified_count": 0,
            "deleted_count": 0,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "components": components,
            "components_sha256": patch._record_digest(components),
        },
        "runtime_contract": {"physical_inputs": physical_inputs},
    }
    lock_record = _record(
        patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "anfis_ablation_sequence_development_patch_lock",
        70,
    )
    companion = patch._expected_companion(payload, lock_record)
    assert companion["manifest_version"] == (
        "closure_anfis_ablation_sequence_development_patch_lock_manifest_v1"
    )
    assert companion["gate"] == "E0-MS"
    assert companion["status"] == "completed"
    assert len(companion["inputs"]) == 54
    assert len({record["path"] for record in companion["inputs"]}) == 54
    assert companion["script"] in companion["inputs"]
    assert companion["script"]["path"] == (
        "src/experiments/lock_closure_anfis_ablation_sequence_development_patch.py"
    )
    assert companion["outputs"] == [lock_record]
    assert companion["historical_inputs"] == []
    assert companion["physical_inputs_only"] is True
    assert companion["manifest_written_last"] is True
    assert companion["dvc_commands_run"] is False
    assert companion["network_commands_run"] is True
    assert companion["data_execution_run"] is False
    assert companion["future_outcomes_accessed"] is False


def test_payload_validator_rejects_schema_valid_false_seals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_lock_payload(monkeypatch)
    assert (
        patch.validate_anfis_ablation_sequence_development_patch_lock_payload(
            payload
        )
        == payload
    )

    def mutate_h_component(value: dict[str, Any]) -> None:
        value["h_patch"]["components"][0]["sha256"] = "f" * 64
        value["h_patch"]["components_sha256"] = patch._record_digest(
            value["h_patch"]["components"]
        )

    def mutate_physical_input(value: dict[str, Any]) -> None:
        value["runtime_contract"]["physical_inputs"][0]["sha256"] = "e" * 64
        value["runtime_contract"]["physical_inputs_sha256"] = patch._record_digest(
            value["runtime_contract"]["physical_inputs"]
        )

    def mutate_namespace_path(
        value: dict[str, Any],
        field: str,
        digest_field: str,
        replacement: str,
    ) -> None:
        paths = value["prelock"]["output_namespace"][field]
        paths[0] = replacement
        value["prelock"]["output_namespace"][digest_field] = patch._path_digest(
            paths
        )

    mutations: tuple[tuple[str, Any], ...] = (
        (
            "tracking ref",
            lambda value: value["repository"].__setitem__(
                "tracking_head", "2" * 40
            ),
        ),
        (
            "remote ref",
            lambda value: value["repository"].__setitem__(
                "remote_head", "3" * 40
            ),
        ),
        (
            "parent",
            lambda value: value["repository"].__setitem__("parent", "4" * 40),
        ),
        ("H component", mutate_h_component),
        (
            "runtime record",
            lambda value: value["runtime_contract"]["record"].__setitem__(
                "sha256", "d" * 64
            ),
        ),
        ("physical input", mutate_physical_input),
        (
            "runtime role",
            lambda value: value["runtime_contract"]["roles"].__setitem__(
                "training_end", "2099-12"
            ),
        ),
        (
            "runtime tensor",
            lambda value: value["runtime_contract"]["features"][
                "raw_no_current"
            ].__setitem__("exact_input_dimension", 19),
        ),
        (
            "runtime bundle",
            lambda value: value["runtime_contract"]["bundles"].__setitem__(
                "exact_bundle_count", 7
            ),
        ),
        (
            "runtime output",
            lambda value: value["runtime_contract"]["outputs"].__setitem__(
                "exact_final_path_count", 17
            ),
        ),
        (
            "final namespace",
            lambda value: mutate_namespace_path(
                value,
                "final_paths",
                "final_paths_sha256",
                "data/closure_v1/development/sequences/A0/false.parquet",
            ),
        ),
        (
            "temporary namespace",
            lambda value: mutate_namespace_path(
                value,
                "temporary_paths",
                "temporary_paths_sha256",
                "data/closure_v1/development/sequences/A0/false.parquet.tmp",
            ),
        ),
        (
            "pointer namespace",
            lambda value: mutate_namespace_path(
                value,
                "pointer_paths",
                "pointer_paths_sha256",
                "data/closure_v1/development/sequences/A0/false.parquet.dvc",
            ),
        ),
        (
            "pointer temporary namespace",
            lambda value: mutate_namespace_path(
                value,
                "pointer_temporary_paths",
                "pointer_temporary_paths_sha256",
                "data/closure_v1/development/sequences/A0/false.parquet.dvc.tmp",
            ),
        ),
        (
            "guard namespace",
            lambda value: mutate_namespace_path(
                value,
                "guard_paths",
                "guard_paths_sha256",
                "tmp/closure_v1_anfis_ablation_sequences/false.guard",
            ),
        ),
        (
            "P guard",
            lambda value: value["prelock"]["control_namespace"].__setitem__(
                "p_guard_path", "tmp/false.guard"
            ),
        ),
        (
            "M0 progression",
            lambda value: value["prelock"]["m0_progression"][
                "manifest"
            ].__setitem__("sha256", "c" * 64),
        ),
        (
            "E0-M presence",
            lambda value: value["prelock"].__setitem__("e0_m_paths_present", 1),
        ),
        (
            "outcome presence",
            lambda value: value["prelock"].__setitem__(
                "outcome_access_log_present", True
            ),
        ),
        (
            "DVC flag",
            lambda value: value["prelock"].__setitem__(
                "dvc_commands_run", True
            ),
        ),
        (
            "authorization",
            lambda value: value["authorizations"].__setitem__(
                "temporal_fit_authorized", True
            ),
        ),
        (
            "seal",
            lambda value: value["seals"].__setitem__("targets_absent", False),
        ),
    )
    for context, mutate in mutations:
        candidate = copy.deepcopy(payload)
        mutate(candidate)
        with pytest.raises(patch.AnfisAblationSequenceDevelopmentPatchError):
            patch.validate_anfis_ablation_sequence_development_patch_lock_payload(
                candidate
            )


def test_validator_rejects_false_command_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preflight = {"gate": "E0-MS"}
    monkeypatch.setattr(patch, "FOCUSED_TEST_COUNT", 37)
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_sequence_development_patch_schema",
        lambda **kwargs: preflight,
    )
    baseline = _verification_bundle(preflight)
    assert patch._validate_verification_binding(baseline) is None
    commands = {
        "full_type_check": patch.TYPE_CHECK_COMMAND,
        "poetry_check": patch.POETRY_CHECK_COMMAND,
        "publication_guard": patch.PUBLICATION_GUARD_COMMAND,
        "git_diff_check": patch.DIFF_CHECK_COMMAND,
    }
    mutations = (
        ("full_type_check", "false type marker\n", ""),
        ("poetry_check", "false poetry marker\n", ""),
        (
            "publication_guard",
            "Checking tracked files before publication...\n"
            "Repository publication guard passed.\n",
            "",
        ),
        ("git_diff_check", "dirty diff\n", ""),
        ("full_type_check", "All checks passed!\n", "unexpected stderr\n"),
    )
    for field, stdout, stderr in mutations:
        candidate = copy.deepcopy(baseline)
        candidate[field] = _command_evidence(commands[field], stdout, stderr)
        with pytest.raises(patch.AnfisAblationSequenceDevelopmentPatchError):
            patch._validate_verification_binding(candidate)
    false_command = copy.deepcopy(baseline)
    false_command["full_type_check"]["command"] = ["false-evidence"]
    with pytest.raises(patch.AnfisAblationSequenceDevelopmentPatchError):
        patch._validate_verification_binding(false_command)


def test_prefix_validator_accepts_only_exact_ordered_complete_triples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slots = list(patch.ORDERED_BUNDLE_SLOTS)
    first = patch._slot_namespace(*slots[0])
    second = patch._slot_namespace(*slots[1])

    def run_with(
        present: set[str],
        untracked_lights: set[str],
    ) -> tuple[int, list[tuple[str, int | None, int]]]:
        audits: list[tuple[str, int | None, int]] = []

        def fake_lexists(path: Path) -> bool:
            relative = (
                path.relative_to(patch.PROJECT_ROOT).as_posix()
                if path.is_absolute()
                else path.as_posix()
            )
            return relative in present

        monkeypatch.setattr(
            patch,
            "_lexists",
            fake_lexists,
        )
        monkeypatch.setattr(
            patch,
            "_validate_materialized_bundle",
            lambda model_id, base_seed, *, completed_prefix_count, **kwargs: (
                audits.append((model_id, base_seed, completed_prefix_count)) or {}
            ),
        )

        def fake_git(*args: str, repo_root: Path | None = None) -> str:
            del repo_root
            if args == ("status", "--porcelain=v1", "--untracked-files=all"):
                return "\n".join(f"?? {path}" for path in sorted(untracked_lights))
            raise AssertionError(args)

        monkeypatch.setattr(patch, "_git", fake_git)
        return patch._validate_exact_bundle_prefix({}), audits

    first_triple = {first[key] for key in ("sequence", "summary", "manifest")}
    second_triple = {second[key] for key in ("sequence", "summary", "manifest")}
    prefix, audits = run_with(
        first_triple | second_triple,
        {first["summary"], first["manifest"], second["summary"], second["manifest"]},
    )
    assert prefix == 2
    assert audits == [("A0", None, 0), ("A1", 1729, 1)]

    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError, match="partial bundle"
    ):
        run_with({first["sequence"]}, set())
    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError, match="ordered prefix"
    ):
        run_with(second_triple, {second["summary"], second["manifest"]})
    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError,
        match="DVC pointers must be absent",
    ):
        run_with(first_triple | {first["pointer"]}, {first["summary"], first["manifest"]})
    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError,
        match="untracked light-output prefix drifted",
    ):
        run_with(set(), {"reports/closure_v1/false.json"})


def test_effective_loader_binds_exact_next_or_current_audit_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        patch,
        "load_and_validate_anfis_ablation_sequence_development_patch_lock",
        lambda **kwargs: ({}, {"lock": {}, "companion": {}}),
    )
    monkeypatch.setattr(
        patch,
        "_static_effective_authority",
        lambda *args, **kwargs: {"gate": "E0-MS", "status": "effective_preflight_passed"},
    )
    prefix = 0
    monkeypatch.setattr(
        patch,
        "_validate_exact_bundle_prefix",
        lambda *args, **kwargs: prefix,
    )

    a0 = patch.require_anfis_ablation_sequence_development_authority("A0", None)
    assert a0["authorized_model_id"] == "A0"
    assert a0["authorized_base_seed"] is None
    assert a0["completed_prefix_count"] == 0
    assert a0["audit_current_unpublished"] is False

    prefix = 1
    a0_audit = patch.load_effective_anfis_ablation_sequence_development_authority(
        "A0", None, audit_current_unpublished=True
    )
    assert a0_audit["authorized_model_id"] == "A0"
    assert a0_audit["audit_current_unpublished"] is True
    next_slot = patch.require_anfis_ablation_sequence_development_authority(
        "A1", 1729
    )
    assert next_slot["authorized_model_id"] == "A1"
    assert next_slot["authorized_base_seed"] == 1729
    assert next_slot["completed_prefix_count"] == 1

    for model_id, base_seed in (
        ("A0", None),
        ("A1", 20260612),
        ("A1", None),
        ("A1", -1),
    ):
        with pytest.raises(patch.AnfisAblationSequenceDevelopmentPatchError):
            patch.require_anfis_ablation_sequence_development_authority(
                model_id, base_seed
            )

    prefix = 2
    implicit = patch.load_effective_anfis_ablation_sequence_development_authority()
    assert (implicit["authorized_model_id"], implicit["authorized_base_seed"]) == (
        "A1",
        20260612,
    )

    prefix = len(patch.ORDERED_BUNDLE_SLOTS)
    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError,
        match="already been consumed",
    ):
        patch.load_effective_anfis_ablation_sequence_development_authority()


def test_publication_guard_accepts_only_exact_two_line_success() -> None:
    locker._require_publication_guard_success(
        "Checking tracked files before publication...\n"
        "OK: tracked files look publication-ready.\n",
        "",
    )


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (
            "Checking tracked files before publication...\n"
            "Repository publication guard passed.\n",
            "",
        ),
        (
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n"
            "OK: tracked files look publication-ready.\n",
            "",
        ),
        (
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n",
            "unexpected stderr",
        ),
        (
            "Checking tracked files before publication...\n\n"
            "OK: tracked files look publication-ready.\n",
            "",
        ),
    ],
)
def test_publication_guard_rejects_old_repeated_ambiguous_or_stderr(
    stdout: str,
    stderr: str,
) -> None:
    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError,
        match="single exact success",
    ):
        locker._require_publication_guard_success(stdout, stderr)


def test_check_only_runs_schema_before_remote_prelock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_sequence_development_patch_schema",
        lambda: events.append("schema") or {"gate": "E0-MS"},
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_sequence_development_patch_prelock_state",
        lambda: events.append("prelock")
        or {
            "repository": {"head": "1" * 40},
            "h_patch": {
                "added_count": 10,
                "modified_count": 0,
                "components": [None] * 10,
            },
        },
    )
    result = locker.check_only()
    assert events == ["schema", "prelock"]
    assert result["component_count"] == 10
    assert result["h_added_count"] == 10
    assert result["h_modified_count"] == 0
    assert result["writes_performed"] is False
    assert result["verification_commands_run"] is False
    assert result["dvc_commands_run"] is False
    assert result["network_commands_run"] is True
    assert result["scientific_network_commands_run"] is False
    assert result["data_execution_run"] is False
    assert result["sequence_builder_run"] is False
    assert result["auditor_run"] is False
    assert result["future_outcomes_accessed"] is False


def test_execute_lock_recollects_before_two_output_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    prelock = {
        "repository": {"head": "1" * 40},
        "h_patch": {
            "added_count": 10,
            "modified_count": 0,
            "components": [None] * 10,
        },
    }
    verification = {"focused_tests": {"test_count": 1}}
    payload = {"gate": "E0-MS"}
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_sequence_development_patch_schema",
        lambda: events.append("schema") or {"gate": "E0-MS"},
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_sequence_development_patch_prelock_state",
        lambda: events.append("prelock") or prelock,
    )
    monkeypatch.setattr(
        locker,
        "run_anfis_ablation_sequence_development_patch_verification",
        lambda **kwargs: events.append("verify") or verification,
    )

    def build(
        observed_prelock: dict[str, Any],
        observed_verification: dict[str, Any],
        *,
        created_at_utc: str,
    ) -> dict[str, Any]:
        assert observed_prelock is prelock
        assert observed_verification is verification
        assert created_at_utc.endswith("+00:00")
        events.append("build")
        return payload

    monkeypatch.setattr(
        patch,
        "build_anfis_ablation_sequence_development_patch_lock_payload",
        build,
    )
    monkeypatch.setattr(
        patch,
        "validate_anfis_ablation_sequence_development_patch_lock_payload",
        lambda value: events.append("validate") or value,
    )
    monkeypatch.setattr(
        locker,
        "_publish_lock_bundle",
        lambda value: events.append("publish") or (value, {}),
    )
    result = locker.execute_lock()
    assert events == [
        "schema",
        "prelock",
        "verify",
        "prelock",
        "build",
        "validate",
        "publish",
    ]
    assert result["published_output_count"] == 2
    assert result["anfis_ablation_sequence_builder_authorized"] is False
    assert result["model_fit_authorized"] is False
    assert result["metrics_authorized"] is False
    assert result["dvc_commands_run"] is False
    assert result["scientific_network_commands_run"] is False
    assert result["data_execution_run"] is False
    assert result["sequence_builder_run"] is False
    assert result["auditor_run"] is False
    assert result["future_outcomes_accessed"] is False


def test_focused_summary_requires_one_exact_clean_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch, "FOCUSED_TEST_COUNT", 41)
    assert locker._parse_focused_summary("41 passed in 12.34s\n", "") == {
        "test_count": 41,
        "skipped_count": 0,
        "deselected_count": 0,
    }
    for stdout, stderr in (
        ("41 passed, 1 warning in 12.34s\n", ""),
        ("41 passed in 12.34s\n", "unexpected"),
        ("40 passed in 12.34s\n", ""),
        ("41 passed in 12.34s\n41 passed in 12.35s\n", ""),
    ):
        with pytest.raises(patch.AnfisAblationSequenceDevelopmentPatchError):
            locker._parse_focused_summary(stdout, stderr)


def test_locker_commands_exclude_sequences_science_dvc_and_outcomes() -> None:
    commands = (
        patch.TYPE_CHECK_COMMAND,
        patch.FOCUSED_TEST_COMMAND,
        patch.POETRY_CHECK_COMMAND,
        patch.PUBLICATION_GUARD_COMMAND,
        patch.DIFF_CHECK_COMMAND,
    )
    command_text = "\n".join(" ".join(command) for command in commands).lower()
    for forbidden in ("dvc", "outcome_access_log"):
        assert forbidden not in command_text
    forbidden_entrypoints = {
        "src/experiments/build_closure_anfis_ablation_sequences.py",
        "src/experiments/audit_closure_anfis_ablation_sequence_bundle.py",
    }
    assert all(
        token not in forbidden_entrypoints
        for command in commands
        for token in command
    )


def test_guard_parent_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "tmp").symlink_to(outside, target_is_directory=True)
    with pytest.raises(patch.AnfisAblationSequenceDevelopmentPatchError):
        locker._acquire_guard()


def test_guard_write_failure_removes_only_owned_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)

    def fail_write(descriptor: int, payload: bytes, *, context: str) -> None:
        del descriptor, payload, context
        raise OSError("injected guard write failure")

    monkeypatch.setattr(locker, "_write_all", fail_write)
    with pytest.raises(OSError, match="injected"):
        locker._acquire_guard()
    assert not os.path.lexists(locker.OUTPUT_GUARD_PATH)


def test_guard_write_failure_preserves_foreign_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)

    def replace_then_fail(descriptor: int, payload: bytes, *, context: str) -> None:
        del descriptor, payload, context
        locker.OUTPUT_GUARD_PATH.unlink()
        locker.OUTPUT_GUARD_PATH.write_bytes(b"foreign")
        raise OSError("injected replacement")

    monkeypatch.setattr(locker, "_write_all", replace_then_fail)
    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError,
        match="cleanup failed closed",
    ):
        locker._acquire_guard()
    assert locker.OUTPUT_GUARD_PATH.read_bytes() == b"foreign"


def test_temporary_fsync_failure_rolls_back_owned_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    expected = Path("reports/closure_v1/00_protocol/item.tmp")
    real_fsync = locker.os.fsync
    calls = 0

    def fail_once(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(locker.os, "fsync", fail_once)
    with pytest.raises(OSError, match="injected"):
        locker._write_temp(tmp_path / expected, expected, b"owned")
    assert not os.path.lexists(tmp_path / expected)


def test_temp_symlink_is_not_followed_or_clobbered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"foreign")
    expected = Path("reports/closure_v1/00_protocol/item.tmp")
    (tmp_path / expected).symlink_to(foreign)
    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError, match="clobber"
    ):
        locker._write_temp(tmp_path / expected, expected, b"owned")
    assert foreign.read_bytes() == b"foreign"


def test_owned_rollback_preserves_foreign_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    expected = Path("reports/closure_v1/00_protocol/item.tmp")
    owner = locker._write_temp(tmp_path / expected, expected, b"owned")
    os.unlink(owner.path.name, dir_fd=owner.directory_file_descriptor)
    (tmp_path / expected).write_bytes(b"foreign")
    try:
        with pytest.raises(
            patch.AnfisAblationSequenceDevelopmentPatchError, match="foreign"
        ):
            locker._rollback_if_owned(owner, context="test")
        assert (tmp_path / expected).read_bytes() == b"foreign"
    finally:
        locker._close_owner(owner)


def test_publication_refuses_existing_final_without_losing_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    guard = locker._acquire_guard()
    temp_expected = Path("reports/closure_v1/00_protocol/item.tmp")
    final_expected = Path("reports/closure_v1/00_protocol/item.json")
    temp = locker._write_temp(tmp_path / temp_expected, temp_expected, b"owned")
    (tmp_path / final_expected).write_bytes(b"foreign")
    try:
        with pytest.raises(
            patch.AnfisAblationSequenceDevelopmentPatchError, match="clobber"
        ):
            locker._publish_temp(
                temp,
                tmp_path / final_expected,
                final_expected,
                guard,
            )
        assert (tmp_path / final_expected).read_bytes() == b"foreign"
        assert locker._owner_state(temp) == "owned"
    finally:
        locker._rollback_if_owned(temp, context="test temporary")
        locker._close_owner(temp)
        locker._release_guard(guard)


def test_lock_bundle_publishes_companion_last_and_cleans_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    lock_path = Path("reports/closure_v1/00_protocol/lock.json")
    manifest_path = Path("reports/closure_v1/00_protocol/lock_manifest.json")
    monkeypatch.setattr(patch, "DEFAULT_PATCH_LOCK_PATH", lock_path)
    monkeypatch.setattr(patch, "DEFAULT_PATCH_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda payload, record: {
            "payload_sha256": record["sha256"],
            "manifest_written_last": True,
        },
    )
    locker._publish_lock_bundle({"gate": "E0-MS"})
    assert (tmp_path / lock_path).is_file()
    assert (tmp_path / manifest_path).is_file()
    assert (tmp_path / manifest_path).stat().st_mtime_ns >= (
        tmp_path / lock_path
    ).stat().st_mtime_ns
    assert not os.path.lexists(Path((tmp_path / lock_path).as_posix() + ".tmp"))
    assert not os.path.lexists(Path((tmp_path / manifest_path).as_posix() + ".tmp"))
    assert not os.path.lexists(locker.OUTPUT_GUARD_PATH)


def test_guard_release_failure_rolls_back_both_published_finals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    lock_path = Path("reports/closure_v1/00_protocol/lock.json")
    manifest_path = Path("reports/closure_v1/00_protocol/lock_manifest.json")
    monkeypatch.setattr(patch, "DEFAULT_PATCH_LOCK_PATH", lock_path)
    monkeypatch.setattr(patch, "DEFAULT_PATCH_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda payload, record: {
            "payload_sha256": record["sha256"],
            "manifest_written_last": True,
        },
    )
    real_release = locker._release_guard

    def release_then_fail(guard: locker.OutputGuard) -> None:
        real_release(guard)
        raise OSError("injected release failure")

    monkeypatch.setattr(locker, "_release_guard", release_then_fail)
    with pytest.raises(
        patch.AnfisAblationSequenceDevelopmentPatchError,
        match="cleanup failed closed",
    ):
        locker._publish_lock_bundle({"gate": "E0-MS"})
    assert not os.path.lexists(tmp_path / lock_path)
    assert not os.path.lexists(tmp_path / manifest_path)
    assert not os.path.lexists(Path((tmp_path / lock_path).as_posix() + ".tmp"))
    assert not os.path.lexists(Path((tmp_path / manifest_path).as_posix() + ".tmp"))
    assert not os.path.lexists(locker.OUTPUT_GUARD_PATH)


def test_cli_modes_are_mutually_exclusive() -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    with pytest.raises(SystemExit):
        locker.parse_args(["--check-only", "--execute-lock"])
