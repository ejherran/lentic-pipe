from __future__ import annotations

import copy
import hashlib
import json
import inspect
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from collections.abc import Generator
from typing import Any

import pytest

from src.experiments import closure_e0_u_authority as authority
from src.experiments import run_closure_benchmark as runner


def _phase3_numpy_export_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    sources = {
        spec["source_path"]: {
            "path": spec["source_path"],
            "sha256": hashlib.sha256(spec["source_path"].encode("utf-8")).hexdigest(),
        }
        for spec in authority._phase3_overlay_checkpoint_specs()
    }
    checkpoints: list[dict[str, Any]] = []
    arrays: list[dict[str, Any]] = []
    for spec in authority._phase3_overlay_checkpoint_specs():
        source = sources[spec["source_path"]]
        state_arrays: list[dict[str, Any]] = []
        for state_key, shape in sorted(
            authority._phase3_overlay_state_shapes(spec).items()
        ):
            element_count = 1
            for dimension in shape:
                element_count *= dimension
            npz_key = spec["identity_prefix"] + "/" + state_key
            record = {
                "npz_key": npz_key,
                "state_key": state_key,
                "dtype": "<i8" if state_key == "rule_indices" else "<f4",
                "shape": shape,
                "element_count": element_count,
                "data_sha256": hashlib.sha256((npz_key + ":data").encode()).hexdigest(),
                "npy_sha256": hashlib.sha256((npz_key + ":npy").encode()).hexdigest(),
                "origin_path": spec["source_path"],
                "origin_sha256": source["sha256"],
                "checkpoint_family": spec["family"],
                "surface_model_id": spec["surface_model_id"],
                "seed": spec["seed"],
                "module": spec["module"],
                "model_id": spec["model_id"],
            }
            state_arrays.append(record)
            arrays.append(record)
        if spec["family"] == "anfis":
            module = spec["module"]
            identity = {
                "checkpoint_version": "closure_anfis_module_v1",
                "experiment_id": "closure_v1",
                "module": {
                    "N": "ANFIS-N",
                    "F": "ANFIS-F",
                    "T": "ANFIS-T-no-current",
                }[module],
                "base_seed": spec["seed"],
                "module_seed": spec["seed"] + 1,
                "feature_columns": {
                    "N": ["tp_pressure", "tn_pressure", "ratio_imbalance_pressure"],
                    "F": ["do_good", "ph_good", "turbidity_good", "secchi_good"],
                    "T": ["temp_favorable"],
                }[module],
                "target_column": {"N": "yN", "F": "yF", "T": "yT_no_chla"}[
                    module
                ],
                "configuration": {
                    "memberships_per_input": 3,
                    "center_constraint": "unit",
                    "min_width": 0.03,
                    "min_gap": 0.0001,
                    "output_activation": "sigmoid",
                },
            }
            fixture_shape = [7, {"N": 3, "F": 4, "T": 1}[module]]
            output_names = ["prediction"]
            output_shape = [7]
        else:
            model_id = spec["model_id"]
            identity = {
                "model_version": "closure_anfis_ablation_direct_multitask_v1",
                "experiment_id": "closure_v1",
                "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
                "gate": "E0-MT",
                "artifact_role": "raw_best_checkpoint",
                "model_id": model_id,
                "base_seed": spec["seed"],
                "upstream_state_seed": spec["seed"] if model_id == "A1" else None,
                "device": "cpu",
                "config": {
                    "family": "direct_multitask_probabilistic_gru",
                    "model_id": model_id,
                    "input_dimension": {"A0": 18, "A1": 27}[model_id],
                    "hidden_dimension": 96,
                    "recurrent_layers": 1,
                    "history_length_months": 12,
                    "risk_logvar_clamp": [-10.0, 2.0],
                },
                "bloom_training_priors": [0.1, 0.2, 0.3],
                "risk_training_priors": [0.4, 0.5, 0.6],
            }
            fixture_shape = [4, 12, {"A0": 18, "A1": 27}[model_id]]
            output_names = [
                "bloom_logit_h1",
                "bloom_logit_h2",
                "bloom_logit_h3",
                "risk_mean_h1",
                "risk_mean_h2",
                "risk_mean_h3",
                "risk_logvar_h1",
                "risk_logvar_h2",
                "risk_logvar_h3",
            ]
            output_shape = [4, 9]
        parity = {
            "fixture_version": authority.PHASE3_OVERLAY_PARITY_FIXTURE_VERSION,
            "fixture_shape": fixture_shape,
            "fixture_dtype": "<f4",
            "output_names": output_names,
            "output_shape": output_shape,
            "atol": authority.PHASE3_OVERLAY_PARITY_ATOL,
            "rtol": authority.PHASE3_OVERLAY_PARITY_RTOL,
            "maximum_absolute_error": 0.0,
            "passed": True,
        }
        checkpoints.append(
            {
                "family": spec["family"],
                "surface_model_id": spec["surface_model_id"],
                "seed": spec["seed"],
                "module": spec["module"],
                "model_id": spec["model_id"],
                "source_path": spec["source_path"],
                "source_sha256": source["sha256"],
                "identity": identity,
                "state_dict_key_count": len(state_arrays),
                "state_dict_arrays": state_arrays,
                "parity": parity,
            }
        )
    arrays.sort(key=lambda record: record["npz_key"])
    archive_keys = sorted(["__manifest_json__", *[record["npz_key"] for record in arrays]])
    export = {
        "format_version": authority.PHASE3_OVERLAY_NPZ_INDEX_VERSION,
        "internal_manifest_key": "__manifest_json__",
        "internal_manifest_encoding": "uint8_utf8_canonical_json",
        "internal_manifest_bytes": 1,
        "internal_manifest_sha256": "a" * 64,
        "key_dialect": {
            "anfis": "anfis/{seed}/{module}/{state_key}",
            "anfis_modules": ["N", "F", "T"],
            "gru": "gru/{model_id}/{seed}/{state_key}",
            "gru_model_ids": ["A0", "A1"],
            "state_key_encoding": "literal_utf8_no_slash",
        },
        "checkpoint_count": 25,
        "anfis_checkpoint_count": 15,
        "anfis_f1_checkpoint_count": 15,
        "gru_checkpoint_count": 10,
        "state_dict_array_count": len(arrays),
        "archive_array_count": len(archive_keys),
        "archive_keys": archive_keys,
        "arrays": arrays,
        "checkpoints": checkpoints,
        "parity": {
            "fixture_version": authority.PHASE3_OVERLAY_PARITY_FIXTURE_VERSION,
            "atol": authority.PHASE3_OVERLAY_PARITY_ATOL,
            "rtol": authority.PHASE3_OVERLAY_PARITY_RTOL,
            "checkpoint_count": 25,
            "passed_checkpoint_count": 25,
            "maximum_absolute_error": 0.0,
            "anfis_maximum_absolute_error": 0.0,
            "gru_maximum_absolute_error": 0.0,
            "passed": True,
        },
    }
    return export, sources


def _reset_state() -> None:
    authority._STATE.clear()
    authority._STATE.update(
        {
            "required": False,
            "recovery": False,
            "run_guard_path": authority.RUN_GUARD_PATH,
            "opened": False,
            "published": False,
            "failed": False,
            "repo_root": None,
            "repo_root_identity": None,
            "manifest": None,
            "public_authority": None,
            "contract_sha256": None,
            "execution_id": None,
            "expected_artifact_paths": None,
            "expected_publication_order": None,
            "manifest_last_paths": None,
            "stage_count": None,
            "guard_fd": None,
            "guard_record": None,
            "guard_parent_anchor": None,
            "guard_owned_directories": None,
            "published_records": None,
            "publication_receipt": None,
            "access_log_identity": None,
            "access_log_lease": None,
        }
    )


@pytest.fixture(autouse=True)
def _isolated_authority_state() -> Generator[None, None, None]:
    _reset_state()
    yield
    descriptor = authority._STATE.get("guard_fd")
    if type(descriptor) is int:
        try:
            import os

            os.close(descriptor)
        except OSError:
            pass
    authority._close_parent_directory_anchor(
        authority._STATE.get("guard_parent_anchor")
    )
    authority._close_access_log_lease(authority._STATE.get("access_log_lease"))
    published_records = authority._STATE.get("published_records")
    if isinstance(published_records, list):
        authority._close_publication_anchors(published_records)
    _reset_state()


def _phase3_overlay_deep_validation_receipt(
    h_commit: str = "1" * 40,
) -> dict[str, Any]:
    sources = [
        {
            "role": spec["role"],
            "path": spec["path"],
            "bytes": index + 1,
            "sha256": f"{index + 1:064x}",
        }
        for index, spec in enumerate(authority._phase3_overlay_source_specs())
    ]
    return {
        "schema_version": "closure_phase3_input_overlay_deep_validation_v1",
        "status": "passed",
        "experiment_id": authority.EXPERIMENT_ID,
        "surface_id": "closure_v1_phase3_input_overlay",
        "gate": "pre_E0-U",
        "expected_h_commit": h_commit,
        "builder_source": {
            "role": "phase3_input_overlay_builder",
            "path": authority.PHASE3_OVERLAY_BUILDER_PATH,
            "bytes": 100,
            "sha256": "f" * 64,
        },
        "source_inputs": sources,
        "source_input_count": 27,
        "source_inputs_sha256": hashlib.sha256(
            authority._canonical_json_bytes(sources)
        ).hexdigest(),
        "manifest": {
            "path": authority.PHASE3_OVERLAY_MANIFEST_PATH,
            "bytes": 200,
            "sha256": "e" * 64,
        },
        "physical_outputs": [
            {"path": path, "bytes": 300 + index, "sha256": str(index + 1) * 64}
            for index, (path, _role) in enumerate(authority.PHASE3_OVERLAY_OUTPUTS)
        ],
        "checkpoint_count": 25,
        "state_dict_array_count": 195,
        "warmup_row_count": 88,
        "warmup_site_count": 88,
        "npz_regenerated_byte_equality": True,
        "warmup_regenerated_byte_equality": True,
        "manifest_regenerated_byte_equality": True,
        "checkpoint_identity_revalidated": True,
        "numpy_torch_parity_recomputed": True,
        "warmup_projection_recomputed": True,
        "history_projection": list(authority.PHASE3_OVERLAY_HISTORY_PROJECTION),
        "panel_projection": list(authority.PHASE3_OVERLAY_PANEL_PROJECTION),
        "projection_contains_chlorophyll": False,
        "projection_contains_target": False,
        "opened_outcome_path_count": 0,
        "opened_target_path_count": 0,
        "writes_performed": False,
    }


def _activation_preview() -> dict[str, Any]:
    h_scope = [
        {
            "path": path,
            "status": status,
            "mode": "100644",
            "bytes": 1,
            "sha256": "a" * 64,
        }
        for path, status in (
            (authority.AUTHORITY_SOURCE_PATH, "A"),
            (authority.CONTEXT_BUILDER_SOURCE_PATH, "A"),
            (authority.RUNNER_SOURCE_PATH, "M"),
        )
    ]
    h_scope.sort(key=lambda record: str(record["path"]))
    p_scope = [
        {
            "path": path,
            "status": "A",
            "mode": "100644",
            "bytes": 1,
            "sha256": "b" * 64,
        }
        for path in authority.EXPECTED_P_SCOPE_PATHS
    ]
    return {
        "base_r_commit": authority.BASE_R_COMMIT,
        "dvc_policy": {},
        "execution_id": "closure-v1-e0-u-fixed",
        "experiment_id": authority.EXPERIMENT_ID,
        "expected_artifact_paths_sha256": "c" * 64,
        "expected_publication_order_sha256": "d" * 64,
        "gate": authority.GATE,
        "git_remote_url": authority.LIVE_REMOTE_URL,
        "h_commit": "1" * 40,
        "h_scope": h_scope,
        "p_commit": "2" * 40,
        "p_scope": p_scope,
        "phase3_overlay_deep_validation": (
            _phase3_overlay_deep_validation_receipt()
        ),
        "schema_version": authority.ACTIVATION_SCHEMA_VERSION,
        "sealed_batch_command": authority.SEALED_BATCH_COMMAND,
        "sealed_batch_contract_sha256": "e" * 64,
        "sealed_component_source_records": {},
        "sealed_context_builder_source_record": {},
        "sealed_runner_source_record": {},
        "sealed_runtime_environment_record": {},
        "sealed_support_source_records": {},
    }


def _valid_context_input_preflight() -> dict[str, Any]:
    overlay_record = {
        "manifest": {
            "path": runner.PHASE3_OVERLAY_MANIFEST_PATH.as_posix(),
            "bytes": 101,
            "sha256": "b" * 64,
        },
        "physical_outputs": [
            {
                "path": path.as_posix(),
                "bytes": 202 + index,
                "sha256": str(index + 1) * 64,
            }
            for index, path in enumerate(runner.PHASE3_OVERLAY_OUTPUT_PATHS)
        ],
    }
    return {
        "status": "sealed_phase3_context_inputs_ready",
        "gate": "E0-U",
        "input_only": True,
        "outcome_access_performed": False,
        "writes_performed": False,
        "refit_performed": False,
        "snapshot_reuse_authorized": False,
        "post_append_revalidation_required": True,
        "anchored_input_read_count": 31,
        "input_snapshot_sha256": "a" * 64,
        "phase3_overlay_record": overlay_record,
        "holdout_site_count": 88,
        "origin_count": 4488,
        "history_row_count": 53856,
        "origin_feature_row_count": 4488,
        "eligible_origin_count": 804,
        "ineligible_origin_count": 3684,
        "expanded_intent_count": 13464,
        "pretarget_prediction_count": 673200,
        "overlay_array_count": 123,
        "warmup_site_count": 88,
        "calibrator_count": 66,
        "threshold_count": 66,
        "cutpoint_count": 30,
        "conformal_factor_count": 90,
        "site_strata_count": 88,
        "hypothesis_count": 27,
        "software_evidence_artifact_count": 6,
        "scored_model_slot_count": 28,
        "registered_seed_count": 5,
        "outcome_bearing_paths_opened": [],
    }


def test_runner_requires_complete_anchored_context_input_preflight() -> None:
    expected = _valid_context_input_preflight()
    overlay_record = expected["phase3_overlay_record"]

    assert runner._validate_phase3_context_input_preflight(
        expected,
        expected_overlay_record=overlay_record,
    ) == expected
    for mutation in (
        {"anchored_input_read_count": 0},
        {"input_snapshot_sha256": "A" * 64},
        {"outcome_bearing_paths_opened": ["data/targets"]},
    ):
        drifted = {**expected, **mutation}
        with pytest.raises(
            runner.ClosureBenchmarkError,
            match="input preflight diagnostics drifted",
        ):
            runner._validate_phase3_context_input_preflight(
                drifted,
                expected_overlay_record=overlay_record,
            )
    missing = dict(expected)
    missing.pop("input_snapshot_sha256")
    with pytest.raises(
        runner.ClosureBenchmarkError,
        match="input preflight diagnostics drifted",
    ):
        runner._validate_phase3_context_input_preflight(
            missing,
            expected_overlay_record=overlay_record,
        )
    swapped_overlay = json.loads(json.dumps(expected))
    swapped_overlay["phase3_overlay_record"]["physical_outputs"][0]["sha256"] = (
        "f" * 64
    )
    with pytest.raises(
        runner.ClosureBenchmarkError,
        match="input preflight diagnostics drifted",
    ):
        runner._validate_phase3_context_input_preflight(
            swapped_overlay,
            expected_overlay_record=overlay_record,
        )


def test_activation_preview_requires_exact_ten_path_additive_p_scope() -> None:
    exact = _activation_preview()
    assert authority._validate_activation_without_contract(exact) == exact

    missing = {**exact, "p_scope": exact["p_scope"][:-1]}
    extra_record = {
        "path": "reports/closure_v1/00_protocol/unexpected.json",
        "status": "A",
        "mode": "100644",
        "bytes": 1,
        "sha256": "f" * 64,
    }
    extra = {
        **exact,
        "p_scope": sorted(
            [*exact["p_scope"], extra_record], key=lambda record: record["path"]
        ),
    }
    mutated_records = [dict(record) for record in exact["p_scope"]]
    mutated_records[0]["status"] = "M"
    mutated = {**exact, "p_scope": mutated_records}

    for candidate in (missing, extra, mutated):
        with pytest.raises(RuntimeError, match="code-then-data-only"):
            authority._validate_activation_without_contract(candidate)


def test_authority_requires_exact_transitive_phase3_overlay_receipt() -> None:
    receipt = _phase3_overlay_deep_validation_receipt()
    expected_overlay = {
        "manifest": receipt["manifest"],
        "physical_outputs": receipt["physical_outputs"],
    }
    assert authority._validate_phase3_overlay_deep_validation(
        receipt,
        "1" * 40,
        expected_overlay,
    ) == receipt

    mutations: list[dict[str, Any]] = []
    for key, value in (
        ("checkpoint_count", 24),
        ("state_dict_array_count", 194),
        ("warmup_site_count", 87),
        ("npz_regenerated_byte_equality", False),
    ):
        mutations.append({**receipt, key: value})
    reordered = copy.deepcopy(receipt)
    reordered["source_inputs"][0], reordered["source_inputs"][1] = (
        reordered["source_inputs"][1],
        reordered["source_inputs"][0],
    )
    reordered["source_inputs_sha256"] = hashlib.sha256(
        authority._canonical_json_bytes(reordered["source_inputs"])
    ).hexdigest()
    mutations.append(reordered)
    for candidate in mutations:
        with pytest.raises(RuntimeError, match="deep-validation"):
            authority._validate_phase3_overlay_deep_validation(
                candidate,
                "1" * 40,
                expected_overlay,
            )


def test_direct_parent_guard_rejects_merge_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    child = "1" * 40
    parent = "2" * 40
    monkeypatch.setattr(
        authority,
        "_git_text",
        lambda *_args, **_kwargs: f"{child} {parent} {'3' * 40}\n",
    )
    with pytest.raises(RuntimeError, match="direct non-merge"):
        authority._require_direct_parent(Path.cwd(), child, parent, "H")


def test_authority_separates_configured_origin_from_live_https(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r_commit = authority.BASE_R_COMMIT
    h_commit = "1" * 40
    p_commit = "2" * 40
    u_commit = "3" * 40
    manifest = _activation_preview()
    configured_url = [authority.CONFIGURED_ORIGIN_URL]
    oid_by_expression = {
        "HEAD^{commit}": u_commit,
        "refs/heads/main^{commit}": u_commit,
        "refs/remotes/origin/main^{commit}": u_commit,
        "refs/remotes/origin/HEAD^{commit}": u_commit,
        "HEAD~1^{commit}": p_commit,
        "HEAD~2^{commit}": h_commit,
        "HEAD~3^{commit}": r_commit,
    }

    def git_text(_root: Path, arguments: list[str]) -> str:
        if arguments == ["symbolic-ref", "--quiet", "HEAD"]:
            return "refs/heads/main\n"
        if arguments == [
            "symbolic-ref",
            "--quiet",
            "refs/remotes/origin/HEAD",
        ]:
            return "refs/remotes/origin/main\n"
        if arguments == ["remote", "get-url", "origin"]:
            return configured_url[0] + "\n"
        if arguments[:4] == ["rev-list", "--parents", "-n", "1"]:
            child = arguments[-1]
            parent = {
                h_commit: r_commit,
                p_commit: h_commit,
                u_commit: p_commit,
            }[child]
            return child + " " + parent + "\n"
        raise AssertionError(arguments)

    activation_blob = {"bytes": 101, "sha256": "f" * 64}
    u_scope = [
        {
            "path": authority.ACTIVATION_MANIFEST_PATH,
            "status": "A",
            "mode": "100644",
            **activation_blob,
        }
    ]

    def diff_scope(_root: Path, parent: str, _child: str) -> list[dict[str, Any]]:
        if parent == r_commit:
            return manifest["h_scope"]
        if parent == h_commit:
            return manifest["p_scope"]
        if parent == p_commit:
            return u_scope
        raise AssertionError(parent)

    git_calls: list[list[str]] = []

    def sealed_git(_root: Path, arguments: list[str], accepted_codes: Any = (0,)) -> bytes:
        del accepted_codes
        git_calls.append(arguments)
        if arguments[0] == "status":
            return b""
        if arguments[0] == "ls-remote":
            return f"{u_commit}\trefs/heads/main\n".encode("ascii")
        raise AssertionError(arguments)

    monkeypatch.setattr(
        authority,
        "_git_oid",
        lambda _root, expression: oid_by_expression[expression],
    )
    monkeypatch.setattr(authority, "_git_text", git_text)
    monkeypatch.setattr(authority, "_git_diff_scope", diff_scope)
    monkeypatch.setattr(
        authority,
        "_git_blob_record",
        lambda *_args: dict(activation_blob),
    )
    monkeypatch.setattr(authority, "_git", sealed_git)
    monkeypatch.setattr(authority, "_https_helper_record", lambda: {"sealed": True})

    assert authority._validate_git_topology(
        tmp_path,
        manifest,
        verify_remote=True,
    ) == u_commit
    assert manifest["git_remote_url"] == authority.LIVE_REMOTE_URL
    assert authority.CONFIGURED_ORIGIN_URL == (
        "git@github.com:ejherran/lentic-pipe.git"
    )
    assert [
        "ls-remote",
        "--heads",
        authority.LIVE_REMOTE_URL,
        "refs/heads/main",
    ] in git_calls

    configured_url[0] = authority.LIVE_REMOTE_URL
    with pytest.raises(RuntimeError, match="topology or refs drifted"):
        authority._validate_git_topology(
            tmp_path,
            manifest,
            verify_remote=False,
        )


def test_runner_recaptures_clean_repository_immediately_before_outcome_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    activation_commit = "3" * 40
    status = b""

    def sealed_git(*arguments: str, **_kwargs: Any) -> bytes:
        nonlocal status
        if arguments[0] == "rev-parse":
            return (activation_commit + "\n").encode("ascii")
        if arguments[:2] == ("symbolic-ref", "--quiet"):
            if arguments[2] == "HEAD":
                return b"refs/heads/main\n"
            return b"refs/remotes/origin/main\n"
        if arguments[0] == "status":
            return status
        raise AssertionError(arguments)

    monkeypatch.setattr(runner, "_sealed_git", sealed_git)
    receipt = runner._require_clean_repository_snapshot_before_outcome_log(
        {"phase3_activation_commit": activation_commit}
    )
    assert receipt == {
        "phase3_activation_commit": activation_commit,
        "refs_aligned": True,
        "head_ref": "refs/heads/main",
        "origin_head_ref": "refs/remotes/origin/main",
        "worktree_clean": True,
        "index_clean": True,
        "untracked_paths_absent": True,
        "double_recapture_equal": True,
    }

    status = b" M src/experiments/run_closure_benchmark.py\0"
    with pytest.raises(runner.ClosureBenchmarkError, match="published and clean"):
        runner._require_clean_repository_snapshot_before_outcome_log(
            {"phase3_activation_commit": activation_commit}
        )


def test_authority_reader_recaptures_renamed_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "sealed_parent"
    parent.mkdir()
    relative = "sealed_parent/payload.json"
    (tmp_path / relative).write_text('{"version":1}\n', encoding="utf-8")
    real_read = os.read
    replaced = False

    def replacing_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        payload = real_read(descriptor, size)
        if payload and not replaced:
            replaced = True
            parent.rename(tmp_path / "original_parent")
            parent.mkdir()
            (tmp_path / relative).write_text('{"version":2}\n', encoding="utf-8")
        return payload

    monkeypatch.setattr(os, "read", replacing_read)
    with pytest.raises(RuntimeError, match="ancestor changed"):
        authority._read_regular_relative(tmp_path, relative, 0o644, 1)


def test_authority_reader_recaptures_replaced_repository_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    relative = "payload.json"
    (repo / relative).write_text('{"version":1}\n', encoding="utf-8")
    real_read = os.read
    replaced = False

    def replacing_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        payload = real_read(descriptor, size)
        if payload and not replaced:
            replaced = True
            repo.rename(tmp_path / "original_repo")
            repo.mkdir()
            (repo / relative).write_text('{"version":2}\n', encoding="utf-8")
        return payload

    monkeypatch.setattr(os, "read", replacing_read)
    with pytest.raises(RuntimeError, match="repository root changed"):
        authority._read_regular_relative(repo, relative, 0o644, 1)


def test_authority_reader_keeps_strict_files_and_accepts_dvc_hardlinks(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "payload.parquet"
    cache = tmp_path / "cache-object"
    payload.write_bytes(b"dvc-payload")
    os.link(payload, cache)
    payload.chmod(0o444)

    observed, metadata = authority._read_regular_relative(
        tmp_path,
        "payload.parquet",
        None,
        None,
    )
    assert observed == b"dvc-payload"
    assert metadata.st_nlink == 2
    with pytest.raises(RuntimeError, match="identity drifted"):
        authority._read_regular_relative(
            tmp_path,
            "payload.parquet",
            0o644,
            1,
        )
    payload.chmod(0o600)
    with pytest.raises(RuntimeError, match="identity drifted"):
        authority._read_regular_relative(
            tmp_path,
            "payload.parquet",
            None,
            None,
        )


def test_runner_validates_e10_source_evidence_before_context_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [
        {
            "support_id": spec["support_id"],
            "module_name": spec["module_name"],
            "source_path": spec["source_path"],
            "required_symbols": list(spec["required_symbols"]),
            "missing_symbols": [],
            "status": "ready",
        }
        for spec in runner.SEALED_SUPPORT_SOURCES
    ]
    calls: list[str] = []

    def execute_module(**kwargs: Any) -> tuple[SimpleNamespace, dict[str, Any]]:
        module_name = str(kwargs["module_name"])
        if module_name == "src.mifal.ed_t2":
            module = SimpleNamespace(MIFALEDT2=lambda: None)
        elif module_name == "src.mifal.closure_panel_adapter":
            module = SimpleNamespace(
                panel_row_to_closure_mifal_payload=lambda: None,
                payload_is_eligible=lambda: None,
            )
        else:
            def load_evidence(**_kwargs: Any) -> dict[str, bytes]:
                calls.append("e10_validated")
                return {key: b"sealed" for key in runner.SOFTWARE_EVIDENCE_KEYS}

            module = SimpleNamespace(
                load_closure_e10_software_evidence=load_evidence,
                validate_closure_e10_environment_payload=lambda **_kwargs: None,
            )
        return module, dict(kwargs["expected_source_record"])

    monkeypatch.setattr(runner, "_execute_sealed_source_module", execute_module)
    monkeypatch.setattr(
        runner, "_normalize_sealed_dependency_import_environment", lambda: None
    )
    monkeypatch.setattr(runner, "_require_source_identity", lambda *a, **k: None)
    result = runner._load_ready_support_sources(
        {"support_source_records": records},
        {
            "sealed_support_source_records": records,
            "phase3_code_commit": "1" * 40,
        },
    )
    assert result == tuple(records)
    assert calls == ["e10_validated"]


def test_overlay_numpy_export_contract_rejects_empty_or_mutated_provenance() -> None:
    export, sources = _phase3_numpy_export_fixture()
    internal = authority._validate_phase3_numpy_export(export, sources)
    assert internal["checkpoint_count"] == 25
    assert internal["state_dict_array_count"] == 195

    with pytest.raises(RuntimeError, match="NumPy export header"):
        authority._validate_phase3_numpy_export({}, sources)

    empty_checkpoints = copy.deepcopy(export)
    empty_checkpoints["checkpoints"] = []
    with pytest.raises(RuntimeError, match="NumPy registries"):
        authority._validate_phase3_numpy_export(empty_checkpoints, sources)

    forged_origin = copy.deepcopy(export)
    forged_origin["checkpoints"][0]["state_dict_arrays"][0]["origin_sha256"] = (
        "f" * 64
    )
    with pytest.raises(RuntimeError, match="state-array binding"):
        authority._validate_phase3_numpy_export(forged_origin, sources)


def test_overlay_bundle_is_validated_before_outcome_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    h_commit = "1" * 40
    p_commit = "2" * 40
    builder_payload = b"sealed overlay builder\n"
    output_payloads = {
        path: f"sealed:{role}\n".encode("utf-8")
        for path, role in authority.PHASE3_OVERLAY_OUTPUTS
    }
    archive_keys = ["__manifest_json__", *[f"array-{index:03d}" for index in range(195)]]
    expected_arrow = [
        {
            "name": column,
            "type": (
                "string"
                if column in ("source_id", "site_id", "year_month")
                else "bool"
                if column == "row_present"
                else "double"
            ),
            "nullable": True,
        }
        for column in authority.PHASE3_OVERLAY_WARMUP_COLUMNS
    ]
    output_records = [
        {
            "role": role,
            "path": path,
            "bytes": len(output_payloads[path]),
            "sha256": authority._sha256_bytes(output_payloads[path]),
            **(
                {
                    "checkpoint_count": 25,
                    "state_dict_array_count": 195,
                    "archive_array_count": 196,
                    "archive_keys": archive_keys,
                }
                if role == "phase3_runtime_weights"
                else {
                    "row_count": 88,
                    "site_count": 88,
                    "columns": list(authority.PHASE3_OVERLAY_WARMUP_COLUMNS),
                    "arrow_schema": expected_arrow,
                }
            ),
        }
        for path, role in authority.PHASE3_OVERLAY_OUTPUTS
    ]
    source_records = []
    for index, spec in enumerate(authority._phase3_overlay_source_specs()):
        payload = f"sealed-source-{index}\n".encode("utf-8")
        physical = tmp_path / spec["path"]
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(payload)
        source_records.append(
            {
                "role": spec["role"],
                "path": spec["path"],
                "bytes": len(payload),
                "sha256": authority._sha256_bytes(payload),
            }
        )
    manifest = {
        "manifest_version": "closure_phase3_input_overlay_manifest_v1",
        "experiment_id": authority.EXPERIMENT_ID,
        "surface_id": "closure_v1_phase3_input_overlay",
        "gate": "pre_E0-U",
        "status": "completed",
        "publication_status": "materialized_unpublished",
        "repository_head": h_commit,
        "input_only": True,
        "script": {
            "role": "phase3_input_overlay_builder",
            "path": authority.PHASE3_OVERLAY_BUILDER_PATH,
            "bytes": len(builder_payload),
            "sha256": authority._sha256_bytes(builder_payload),
        },
        "inputs": source_records,
        "outputs": output_records,
        "source_inputs": [
            {
                "role": "phase3_input_overlay_builder",
                "path": authority.PHASE3_OVERLAY_BUILDER_PATH,
                "bytes": len(builder_payload),
                "sha256": authority._sha256_bytes(builder_payload),
            },
            *source_records,
        ],
        "physical_outputs": output_records,
        "numpy_export": {"archive_keys": archive_keys},
        "warmup": {"site_count": 88},
        "outcome_isolation": {
            "opened_outcome_path_count": 0,
            "opened_target_path_count": 0,
            "outcome_paths": [],
            "target_paths": [],
            "panel_projection_contains_chlorophyll": False,
            "panel_projection_contains_target": False,
            "scientific_outcomes_accessed": False,
            "e0_u_authorized": False,
            "evaluation_authorized": False,
        },
        "publication": {
            "exclusive_guard": "tmp/closure_phase3_input_overlay.guard",
            "no_clobber": True,
            "temporary_files_exclusive": True,
            "publication_primitive": "temporary_regular_file_then_hardlink",
            "rollback_policy": "current_process_device_inode_only",
            "manifest_written_last": True,
            "publication_order": [
                authority.PHASE3_OVERLAY_OUTPUTS[0][0],
                authority.PHASE3_OVERLAY_OUTPUTS[1][0],
                authority.PHASE3_OVERLAY_MANIFEST_PATH,
            ],
        },
    }
    manifest_payload = authority._canonical_json_bytes(manifest)
    committed_payloads = {
        authority.PHASE3_OVERLAY_MANIFEST_PATH: manifest_payload,
        authority.PHASE3_OVERLAY_BUILDER_PATH: builder_payload,
    }
    for path, payload in output_payloads.items():
        output = tmp_path / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        digest = hashlib.md5(payload, usedforsecurity=False).hexdigest()
        pointer_path = path + ".dvc"
        pointer_payload = (
            "outs:\n"
            f"- md5: {digest}\n"
            f"  size: {len(payload)}\n"
            "  hash: md5\n"
            f"  path: {Path(path).name}\n"
        ).encode("utf-8")
        pointer = tmp_path / pointer_path
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_bytes(pointer_payload)
        committed_payloads[pointer_path] = pointer_payload
    manifest_path = tmp_path / authority.PHASE3_OVERLAY_MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(manifest_payload)

    def git_blob(_root: Path, commit: str, path: str) -> dict[str, Any]:
        payload = (
            builder_payload
            if path == authority.PHASE3_OVERLAY_BUILDER_PATH
            else committed_payloads[path]
        )
        assert commit in {h_commit, p_commit}
        return {
            "path": path,
            "bytes": len(payload),
            "sha256": authority._sha256_bytes(payload),
            "mode": 0o644,
            "git_mode": "100644",
            "git_oid": "a" * 40,
            "payload": payload,
        }

    monkeypatch.setattr(authority, "_git_blob_record", git_blob)
    validated = {"numpy": False, "warmup": False}

    def validate_numpy(value: Any, source_by_path: dict[str, Any]) -> None:
        assert value == {"archive_keys": archive_keys}
        assert set(source_by_path) == {record["path"] for record in source_records}
        validated["numpy"] = True

    def validate_warmup(value: Any) -> None:
        assert value == {"site_count": 88}
        validated["warmup"] = True

    monkeypatch.setattr(authority, "_validate_phase3_numpy_export", validate_numpy)
    monkeypatch.setattr(authority, "_validate_phase3_warmup", validate_warmup)

    empty_sources = copy.deepcopy(manifest)
    empty_sources["inputs"] = []
    empty_sources["source_inputs"] = []
    empty_payload = authority._canonical_json_bytes(empty_sources)
    manifest_path.write_bytes(empty_payload)
    committed_payloads[authority.PHASE3_OVERLAY_MANIFEST_PATH] = empty_payload
    with pytest.raises(RuntimeError, match="source registry"):
        authority._validate_phase3_overlay_bundle(tmp_path, h_commit, p_commit)
    manifest_path.write_bytes(manifest_payload)
    committed_payloads[authority.PHASE3_OVERLAY_MANIFEST_PATH] = manifest_payload

    result = authority._validate_phase3_overlay_bundle(
        tmp_path, h_commit, p_commit
    )
    assert validated == {"numpy": True, "warmup": True}
    assert result == {
        "manifest": {
            "path": authority.PHASE3_OVERLAY_MANIFEST_PATH,
            "bytes": len(manifest_payload),
            "sha256": authority._sha256_bytes(manifest_payload),
        },
        "physical_outputs": [
            {
                "path": path,
                "bytes": len(output_payloads[path]),
                "sha256": authority._sha256_bytes(output_payloads[path]),
            }
            for path, _role in authority.PHASE3_OVERLAY_OUTPUTS
        ],
    }

    first_output = tmp_path / authority.PHASE3_OVERLAY_OUTPUTS[0][0]
    first_output.write_bytes(b"corrupt\n")
    with pytest.raises(RuntimeError, match="physical bytes"):
        authority._validate_phase3_overlay_bundle(tmp_path, h_commit, p_commit)


def _contract() -> dict[str, Any]:
    stages: list[dict[str, Any]] = [
        {
            "stage_id": "E0-U",
            "role": "irreversible_gate",
            "requires_outcomes": False,
            "output_root": "reports/closure_v1/00_protocol",
            "output_paths": [],
        }
    ]
    artifact_contracts: list[dict[str, Any]] = []
    parquet_remaining = 4
    for stage_number in range(1, 11):
        count = 6 if stage_number <= 2 else 5
        stage_id = f"E{stage_number}"
        paths = [
            f"reports/closure_v1/test_e0_u/{stage_id}/artifact_{index}.csv"
            for index in range(count - 1)
        ]
        terminal = f"reports/closure_v1/test_e0_u/{stage_id}/manifest.json"
        paths.append(terminal)
        stages.append(
            {
                "stage_id": stage_id,
                "role": "test",
                "requires_outcomes": True,
                "output_root": f"reports/closure_v1/test_e0_u/{stage_id}",
                "output_paths": paths,
            }
        )
        formats = []
        for _ in range(count - 1):
            if parquet_remaining:
                formats.append("parquet")
                parquet_remaining -= 1
            else:
                formats.append("csv")
        artifact_contracts.append(
            {
                "component_id": f"{stage_id}_component",
                "stage_id": stage_id,
                "artifact_paths": paths,
                "artifact_formats": formats + ["json"],
                "manifest_last_path": terminal,
            }
        )
    return {
        "schema_version": "test_sealed_batch_v1",
        "stages": stages,
        "component_artifact_contracts": artifact_contracts,
    }


def _prepare_root(tmp_path: Path) -> None:
    log = tmp_path / authority.OUTCOME_ACCESS_LOG_PATH
    log.parent.mkdir(parents=True)
    log.write_bytes(b"")
    log.chmod(0o644)


def _prime(tmp_path: Path, contract: dict[str, Any]) -> dict[str, Any]:
    _prepare_root(tmp_path)
    layout = authority._contract_layout(contract)
    heavy = sorted(
        path
        for path, format_name in layout["formats_by_path"].items()
        if format_name == "parquet"
    )
    direct = sorted(set(layout["expected_paths"]) - set(heavy))
    manifest = {
        "expected_artifact_paths_sha256": authority._sha256_bytes(
            authority._canonical_json_bytes(list(layout["expected_paths"]))
        ),
        "expected_publication_order_sha256": authority._sha256_bytes(
            authority._canonical_json_bytes(list(layout["publication_order"]))
        ),
        "dvc_policy": {
            "direct_git_artifact_paths": direct,
            "dvc_add_after_success_only": True,
            "dvc_pointer_paths": sorted(path + ".dvc" for path in heavy),
            "dvc_push_after_audit_only": True,
            "heavy_artifact_paths": heavy,
            "implicit_dvc_forbidden": True,
        },
    }
    public = {
        "gate": "E0-U",
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
    }
    authority._STATE.update(
        {
            "required": True,
            "repo_root": tmp_path.resolve(),
            "repo_root_identity": authority._repository_root_identity(tmp_path),
            "manifest": manifest,
            "public_authority": public,
            "contract_sha256": layout["contract_sha256"],
            "execution_id": "closure-v1-e0-u-test-execution",
        }
    )
    return public


def _open(
    tmp_path: Path,
    contract: dict[str, Any],
    public: dict[str, Any],
) -> dict[str, Any]:
    return authority.open_sealed_batch_context(
        authority=public,
        sealed_batch_contract=contract,
        repo_root=tmp_path,
        context_builder=lambda **kwargs: {
            "execution_id": kwargs["execution_id"],
            "rng_seed": 1729,
            "tables": {},
            "stage_results": {},
            "model_availability": {},
            "software_evidence": {},
        },
    )


def _artifacts(contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bytes]]:
    layout = authority._contract_layout(contract)
    terminal = set(layout["manifest_by_stage"].values())
    artifacts: dict[str, Any] = {}
    serialized: dict[str, bytes] = {}
    for path in layout["expected_paths"]:
        format_name = layout["formats_by_path"][path]
        artifacts[path] = {
            "format": format_name,
            "payload": {"path": path} if format_name == "json" else object(),
            "manifest_last": path in terminal,
        }
        serialized[path] = (
            json.dumps({"path": path}, sort_keys=True, separators=(",", ":"))
            + "\n"
            if format_name == "json"
            else "value\n"
        ).encode("utf-8")
    return artifacts, serialized


def test_authority_source_is_stdlib_only_and_definition_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = runner.E0_U_AUTHORITY_PATH
    source, metadata = runner._read_regular_source(
        source_path,
        repo_root=runner.PROJECT_ROOT,
    )
    runner._require_stdlib_only_authority_source(source)
    assert b"pandas" not in source
    assert b"importlib" not in source
    assert b"sys.modules" not in source
    expected = runner._source_identity_record(source_path, source, metadata)
    monkeypatch.setitem(sys.modules, runner.E0_U_AUTHORITY_MODULE, authority)

    module, observed = runner._execute_sealed_source_module(
        module_name=runner.E0_U_AUTHORITY_MODULE,
        source_path=source_path,
        repo_root=runner.PROJECT_ROOT,
        expected_source_record=expected,
    )

    assert observed == expected
    assert module.GATE == "E0-U"
    assert sys.modules[runner.E0_U_AUTHORITY_MODULE] is module
    sealed_import = module.__dict__["__builtins__"]["__import__"]
    assert sealed_import("__future__", {}, {}, ("annotations",), 0).__name__ == (
        "__future__"
    )
    for name, fromlist in (
        ("__future__", ()),
        ("__future__", ("division",)),
        ("__future__", ("annotations", "division")),
        ("__future__.annotations", ("annotations",)),
        ("importlib", ()),
    ):
        with pytest.raises(ImportError):
            sealed_import(name, {}, {}, fromlist, 0)


def test_runner_and_authority_share_exact_capability_and_commit_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pandas as pd

    assert set(authority.AUTHORITY_RESULT_KEYS) == runner.E0_U_AUTHORITY_RESULT_KEYS
    assert runner.HISTORICAL_E0_M_COMMIT == authority.BASE_R_COMMIT
    assert runner.E0_U_COMMIT_BINDING_KEYS == (
        "historical_e0_m_commit",
        "phase3_code_commit",
        "phase3_evidence_commit",
        "phase3_activation_commit",
    )
    source_execution = runner.sealed_batch_contract()["source_execution"]
    assert source_execution["authority_commit_binding_keys"] == list(
        runner.E0_U_COMMIT_BINDING_KEYS
    )
    assert source_execution["historical_e0_m_commit"] == authority.BASE_R_COMMIT
    assert source_execution["context_builder_preflight_api"] == (
        runner.E0_U_CONTEXT_PREFLIGHT_API
    )
    assert source_execution["context_builder_and_preflight_same_sealed_module"] is True
    assert source_execution["context_input_preflight"] == {
        "timing": "before_first_durable_outcome_access_log_append",
        "outcome_access_performed": False,
        "writes_performed": False,
        "complete_pretarget_scoring_performed": True,
        "phase3_overlay_authority_record_compared": True,
        "anchored_source_evidence_file_count": 7,
        "cross_append_policy": (
            "reopen_rehash_redecode_rescore_and_compare_exact_path_bytes_sha256"
        ),
        "snapshot_reuse_authorized": False,
    }
    authority_require = runner.sealed_batch_contract()["startup_contract"][
        "authority_require"
    ]
    assert authority_require["public_result_keys"] == sorted(
        runner.E0_U_AUTHORITY_RESULT_KEYS
    )
    assert authority_require["commit_binding_keys"] == list(
        runner.E0_U_COMMIT_BINDING_KEYS
    )
    assert [spec["support_id"] for spec in runner.SEALED_SUPPORT_SOURCES] == [
        "mifal_ed_t2",
        "mifal_closure_panel_adapter",
        "closure_e10_source_evidence",
    ]
    assert tuple(
        inspect.signature(authority.open_sealed_batch_context).parameters
    ) == (
        "authority",
        "sealed_batch_contract",
        "repo_root",
        "context_builder",
    )
    assert tuple(
        inspect.signature(authority.publish_sealed_batch_artifacts).parameters
    ) == (
        "authority",
        "sealed_batch_contract",
        "batch_context",
        "stage_results",
        "artifacts",
        "serialized_artifacts",
        "repo_root",
    )
    assert tuple(
        inspect.signature(
            authority.validate_published_sealed_batch_artifacts
        ).parameters
    ) == (
        "authority",
        "sealed_batch_contract",
        "batch_context",
        "stage_results",
        "artifacts",
        "serialized_artifacts",
        "publication_receipt",
        "repo_root",
    )

    commits = {
        "HEAD~3^{commit}": authority.BASE_R_COMMIT,
        "HEAD~2^{commit}": "1" * 40,
        "HEAD~1^{commit}": "2" * 40,
        "HEAD^{commit}": "3" * 40,
    }
    monkeypatch.setattr(
        runner,
        "_sealed_git",
        lambda command, option, expression: (commits[expression] + "\n").encode(),
    )
    public = {
        "historical_e0_m_commit": authority.BASE_R_COMMIT,
        "phase3_code_commit": "1" * 40,
        "phase3_evidence_commit": "2" * 40,
        "phase3_activation_commit": "3" * 40,
    }
    assert runner._validate_authority_commit_bindings(
        public,
        {"git_head": "3" * 40},
    ) == public
    public["phase3_code_commit"] = "4" * 40
    with pytest.raises(runner.ClosureBenchmarkError, match="commit binding"):
        runner._validate_authority_commit_bindings(
            public,
            {"git_head": "3" * 40},
        )

    full_tables = {
        table_name: pd.DataFrame({"table_name": [table_name]})
        for table_name in runner.OPENED_CONTEXT_TABLES
    }
    full_context = runner._validate_opened_batch_context(
        {
            "execution_id": "synthetic-e1-least-privilege-view",
            "rng_seed": runner.RNG_SEED,
            "tables": full_tables,
            "stage_results": {},
            "model_availability": dict(runner.CURRENT_MODEL_AVAILABILITY),
            "software_evidence": {
                key: f"synthetic-{key}" for key in runner.SOFTWARE_EVIDENCE_KEYS
            },
        }
    )
    e1_view = runner._component_context(
        full_context,
        component_id="E1_benchmark_scientific_executor",
    )
    assert len(full_context["tables"]) == 9
    assert set(full_context["tables"]) == runner.OPENED_CONTEXT_TABLES
    assert len(e1_view["tables"]) == 3
    assert set(e1_view["tables"]) == set(runner.E1_INPUT_TABLES)
    assert e1_view["software_evidence"] == {}
    with pytest.raises(
        runner.ClosureBenchmarkError,
        match="opened logical table scope",
    ):
        runner._validate_opened_batch_context(e1_view)
    observed_e1_table_views: list[set[str]] = []

    class E1ViewReached(RuntimeError):
        pass

    def normalize_e1_view(tables: dict[str, Any]) -> Any:
        observed_e1_table_views.append(set(tables))
        raise E1ViewReached

    monkeypatch.setattr(runner, "_normalize_e1_prediction_surface", normalize_e1_view)
    with pytest.raises(E1ViewReached):
        runner._execute_e1_locked_benchmark_stage(
            {
                "gate": runner.UNBLINDING_GATE,
                "effective_authority": True,
                "sealed_batch_execution_authorized": True,
                "e0_m_authorized": True,
                "e0_u_authorized": True,
                "evaluation_authorized": True,
                "outcome_access_authorized": True,
            },
            runner.sealed_batch_contract(),
            e1_view,
            Path("."),
        )
    assert observed_e1_table_views == [set(runner.E1_INPUT_TABLES)]

    context_module = ModuleType("synthetic_recovery_context")

    def legacy_e10_loader(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"args": args, "kwargs": kwargs}

    context_module.__dict__["EVIDENCE_ROOT"] = runner.LEGACY_E10_SOURCE_DIRECTORY
    context_module.__dict__["EVIDENCE_MANIFEST_PATH"] = (
        runner.LEGACY_E10_SOURCE_PATHS[-1]
    )
    context_module.__dict__["EVIDENCE_SOURCE_PATHS"] = (
        runner.LEGACY_E10_SOURCE_PATHS
    )
    context_module.__dict__["load_closure_e10_software_evidence"] = (
        legacy_e10_loader
    )
    expected_adapter_bindings = runner._configure_recovery_context_e10_adapter(
        context_module
    )
    runner._recapture_recovery_context_e10_adapter(
        context_module, expected_adapter_bindings
    )
    foreign_loader = lambda *_args, **_kwargs: {"foreign": True}
    context_module.__dict__["load_closure_e10_software_evidence"] = foreign_loader
    context_module.__dict__["_RECOVERY_E10_ADAPTER_BINDINGS"] = {
        "root": runner.RECOVERY_E10_SOURCE_DIRECTORY,
        "manifest": runner.RECOVERY_E10_SOURCE_PATHS[-1],
        "paths": runner.RECOVERY_E10_SOURCE_PATHS,
        "loader": foreign_loader,
    }
    with pytest.raises(
        runner.ClosureBenchmarkError,
        match="recovery context E10 adapter changed",
    ):
        runner._recapture_recovery_context_e10_adapter(
            context_module, expected_adapter_bindings
        )

    import subprocess

    runtime_probe = (
        'import sys,types; '
        'p="src/experiments/run_closure_benchmark.py"; '
        'm=types.ModuleType("sealed_runtime_binding_probe"); '
        'm.__file__=p; sys.modules[m.__name__]=m; '
        'exec(compile(open(p,"rb").read(),p,"exec"),m.__dict__); '
        'n=m.__dict__; '
        'b=n["collect_e0_u_activation_material"]()['
        '"runtime_environment_record"]; '
        'a=types.ModuleType(n["E0_U_AUTHORITY_MODULE"]); '
        'sys.modules[n["E0_U_AUTHORITY_MODULE"]]=a; '
        'E=n["ClosureBenchmarkError"]; '
        'x=dict(b); x["bootstrap_import_state"]=n['
        '"_bootstrap_import_state_record"](); '
        'extra_rejected=False; '
        'exec("try:\\n'
        ' n[\\"_activate_sealed_runtime_environment\\"]('
        '{n[\\"E0_U_RUNTIME_ENVIRONMENT_RECORD_KEY\\"]:x})\\n'
        'except E:\\n'
        ' extra_rejected=True"); '
        'runpy_absent="runpy" not in sys.modules; '
        's=n["_activate_sealed_runtime_environment"]('
        '{n["E0_U_RUNTIME_ENVIRONMENT_RECORD_KEY"]:b}); '
        'r=n["collect_sealed_batch_component_readiness"]('
        'repo_root=n["PROJECT_ROOT"]); '
        'c=n["_load_ready_components"](r); '
        'u=[]; '
        'exec("for spec,record in zip('
        'n[\\"SEALED_SUPPORT_SOURCES\\"],r[\\"support_source_records\\"],'
        'strict=True):\\n'
        ' module,observed=n[\\"_execute_sealed_source_module\\"]('
        'module_name=spec[\\"module_name\\"],'
        'source_path=n[\\"Path\\"](spec[\\"source_path\\"]),'
        'repo_root=n[\\"PROJECT_ROOT\\"],expected_source_record=record)\\n'
        ' n[\\"_normalize_sealed_dependency_import_environment\\"]()\\n'
        ' n[\\"_require_source_identity\\"]('
        'record,observed,context=spec[\\"support_id\\"])\\n'
        ' assert all(callable(getattr(module,symbol,None)) '
        'for symbol in spec[\\"required_symbols\\"])\\n'
        ' u.append(module)"); '
        'd=r["context_builder_source_record"]; '
        'v,o=n["_execute_sealed_source_module"]('
        'module_name=n["E0_U_CONTEXT_BUILDER_MODULE"],'
        'source_path=n["E0_U_CONTEXT_BUILDER_PATH"],'
        'repo_root=n["PROJECT_ROOT"],expected_source_record=d); '
        'n["_normalize_sealed_dependency_import_environment"](); '
        'n["_require_source_identity"]('
        'd,o,context="phase3_context_builder"); '
        'assert all(callable(getattr(v,symbol,None)) for symbol in ('
        'n["E0_U_CONTEXT_BUILDER_API"],n["E0_U_CONTEXT_PREFLIGHT_API"])); '
        'deny=lambda *args,**kwargs:(_ for _ in ()).throw('
        'AssertionError("outcome or panel opened during input preflight")); '
        'v._open_target_outcomes=deny; v._future_trophic_indicators=deny; '
        'inputs=v._load_input_frames(n["PROJECT_ROOT"]); '
        'origins=inputs[2]; '
        'timeit_absent="timeit" not in sys.modules; '
        'b2=v._load_b2_predictions(n["PROJECT_ROOT"],origins); '
        'timeit_present="timeit" in sys.modules; '
        'assert len(origins)==4488; '
        'assert set(b2)=={("B2",seed) for seed in v.REGISTERED_SEEDS}; '
        'assert all(value["bloom_raw"].shape==(4488,3) for value in b2.values()); '
        'assert all(value["ordinal"].shape==(4488,3) for value in b2.values()); '
        'assert all(value["valid"].shape==(4488,3) for value in b2.values()); '
        'assert timeit_absent and timeit_present; '
        'n["_recapture_runtime_environment"](s); '
        'q=dict(s["record"]); z=q.pop("bootstrap_import_state",None); '
        'print(extra_rejected,"bootstrap_import_state" not in b,'
        'isinstance(z,dict),q==b,runpy_absent,len(c),'
        'len(u),int(v is not None),"runpy" in sys.modules,'
        'timeit_absent,timeit_present,len(origins),len(b2))'
    )
    isolated = subprocess.run(
        (
            "/usr/bin/env",
            "-i",
            "LANG=C",
            "LC_ALL=C",
            ".venv/bin/python",
            "-I",
            "-S",
            "-B",
            "-c",
            runtime_probe,
        ),
        cwd=Path("."),
        check=False,
        capture_output=True,
        text=True,
    )
    assert isolated.returncode == 0, isolated.stderr
    assert isolated.stdout == (
        "True True True True True 10 3 1 True True True 4488 5\n"
    )


def test_require_exposes_exact_r_h_p_u_and_all_sealed_source_bindings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    h_commit = "1" * 40
    p_commit = "2" * 40
    u_commit = "3" * 40
    h_scope = [
        {
            "path": authority.AUTHORITY_SOURCE_PATH,
            "status": "A",
            "mode": "100644",
            "bytes": 1,
            "sha256": "a" * 64,
        },
        {
            "path": authority.CONTEXT_BUILDER_SOURCE_PATH,
            "status": "A",
            "mode": "100644",
            "bytes": 1,
            "sha256": "b" * 64,
        },
        {
            "path": authority.RUNNER_SOURCE_PATH,
            "status": "M",
            "mode": "100644",
            "bytes": 1,
            "sha256": "c" * 64,
        },
    ]
    h_scope.sort(key=lambda record: record["path"])
    p_scope = [
        {
            "path": path,
            "status": "A",
            "mode": "100644",
            "bytes": 1,
            "sha256": "d" * 64,
        }
        for path in authority.EXPECTED_P_SCOPE_PATHS
    ]
    manifest = {
        "base_r_commit": authority.BASE_R_COMMIT,
        "dvc_policy": {},
        "execution_id": "closure-v1-e0-u-fixed",
        "experiment_id": "closure_v1",
        "expected_artifact_paths_sha256": "4" * 64,
        "expected_publication_order_sha256": "5" * 64,
        "gate": "E0-U",
        "git_remote_url": authority.LIVE_REMOTE_URL,
        "h_commit": h_commit,
        "h_scope": h_scope,
        "p_commit": p_commit,
        "p_scope": p_scope,
        "phase3_overlay_deep_validation": (
            _phase3_overlay_deep_validation_receipt(h_commit)
        ),
        "schema_version": authority.ACTIVATION_SCHEMA_VERSION,
        "sealed_batch_command": authority.SEALED_BATCH_COMMAND,
        "sealed_batch_contract_sha256": "6" * 64,
        "sealed_component_source_records": {},
        "sealed_context_builder_source_record": {},
        "sealed_runner_source_record": {},
        "sealed_runtime_environment_record": {},
        "sealed_support_source_records": {},
    }
    payload = authority._canonical_json_bytes(manifest)
    executable = {"path": "/sealed", "sha256": "7" * 64}
    bindings = (
        {"path": authority.RUNNER_SOURCE_PATH},
        {"path": authority.CONTEXT_BUILDER_SOURCE_PATH},
        [{"component_id": "component", "path": "component.py"}],
        [{"support_id": "support", "path": "support.py"}],
        {"runtime": "sealed"},
    )
    monkeypatch.setattr(authority, "_resolved_repo_root", lambda value: tmp_path)
    monkeypatch.setattr(
        authority,
        "_absolute_executable_record",
        lambda path, digest: dict(executable),
    )
    monkeypatch.setattr(
        authority,
        "_read_regular_relative",
        lambda *args: (payload, SimpleNamespace(st_size=len(payload))),
    )
    monkeypatch.setattr(
        authority,
        "_validate_git_topology",
        lambda root, value, verify: u_commit,
    )
    monkeypatch.setattr(
        authority,
        "_git_diff_scope",
        lambda root, parent, child: h_scope if parent == authority.BASE_R_COMMIT else p_scope,
    )
    monkeypatch.setattr(
        authority,
        "_validate_manifest_bindings",
        lambda root, head, value: bindings,
    )
    monkeypatch.setattr(
        authority,
        "_validate_phase3_overlay_bundle",
        lambda root, h_commit, p_commit: {
            "manifest": {
                "path": authority.PHASE3_OVERLAY_MANIFEST_PATH,
                "bytes": 101,
                "sha256": "8" * 64,
            },
            "physical_outputs": [
                {
                    "path": path,
                    "bytes": 202 + index,
                    "sha256": str(index + 1) * 64,
                }
                for index, (path, _role) in enumerate(
                    authority.PHASE3_OVERLAY_OUTPUTS
                )
            ],
        },
    )
    monkeypatch.setattr(authority, "_require_empty_access_log", lambda root: None)
    monkeypatch.setattr(
        authority,
        "_validate_phase3_overlay_deep_validation",
        lambda value, *_args: dict(value),
    )
    monkeypatch.setattr(
        authority,
        "_git_bound_authority_source_record",
        lambda root, head, verify: {"path": authority.AUTHORITY_SOURCE_PATH},
    )
    result = authority.require_closure_e0_u_authority(
        verify_remote=True,
        repo_root=tmp_path,
    )
    assert set(result) == set(authority.AUTHORITY_RESULT_KEYS)
    assert result["historical_e0_m_commit"] == authority.BASE_R_COMMIT
    assert result["phase3_code_commit"] == h_commit
    assert result["phase3_evidence_commit"] == p_commit
    assert result["phase3_activation_commit"] == u_commit
    assert result["sealed_support_source_records"] == bindings[3]
    assert result["writes_performed"] is False
    assert authority._STATE["repo_root_identity"] == (
        authority._repository_root_identity(tmp_path)
    )


def test_activation_binding_accepts_exact_ten_components_and_three_supports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    component_specs = (
        ("E2_site_transfer", "src.experiments.evaluate_site_transfer"),
        (
            "E3_threshold_sensitivity",
            "src.experiments.evaluate_threshold_sensitivity",
        ),
        (
            "E4_reference_targets",
            "src.experiments.build_trophic_reference_targets",
        ),
        ("E4_trophic_evaluation", "src.experiments.evaluate_trophic_state"),
        ("E5_clustered_inference", "src.experiments.compare_models_clustered"),
        (
            "E6_matched_degradation",
            "src.experiments.evaluate_matched_degradation",
        ),
        ("E7_anfis_ablation", "src.experiments.evaluate_anfis_ablation"),
        (
            "E8_uncertainty",
            "src.experiments.calibrate_uncertainty_closure",
        ),
        (
            "E9_planning_inference",
            "src.experiments.evaluate_planning_inference",
        ),
        (
            "E10_evidence_matrix",
            "src.reporting.build_closure_evidence_matrix",
        ),
    )
    components = [
        {
            "component_id": component_id,
            "module_name": module_name,
            "source_path": module_name.replace(".", "/") + ".py",
            "status": "ready",
        }
        for component_id, module_name in component_specs
    ]
    supports = [
        {
            "support_id": "mifal_ed_t2",
            "module_name": "src.mifal.ed_t2",
            "source_path": "src/mifal/ed_t2.py",
            "status": "ready",
        },
        {
            "support_id": "mifal_closure_panel_adapter",
            "module_name": "src.mifal.closure_panel_adapter",
            "source_path": "src/mifal/closure_panel_adapter.py",
            "status": "ready",
        },
        {
            "support_id": "closure_e10_source_evidence",
            "module_name": "src.experiments.build_closure_e10_source_evidence",
            "source_path": "src/experiments/build_closure_e10_source_evidence.py",
            "status": "ready",
        },
    ]
    manifest = {
        "sealed_runner_source_record": {"path": authority.RUNNER_SOURCE_PATH},
        "sealed_context_builder_source_record": {
            "source_path": authority.CONTEXT_BUILDER_SOURCE_PATH
        },
        "sealed_component_source_records": components,
        "sealed_support_source_records": supports,
        "sealed_runtime_environment_record": {"status": "sealed"},
    }
    monkeypatch.setattr(
        authority,
        "_validate_source_record",
        lambda root, head, value, expected: dict(value),
    )
    bindings = authority._validate_manifest_bindings(tmp_path, "f" * 40, manifest)
    assert bindings[2] == components
    assert bindings[3] == supports
    assert bindings[4] == {"status": "sealed"}
    components[-1]["module_name"] = "src.reporting.unsealed_component"
    with pytest.raises(RuntimeError, match="component module name"):
        authority._validate_manifest_bindings(tmp_path, "f" * 40, manifest)
    components[-1]["module_name"] = "src.experiments.unsealed_component"
    with pytest.raises(RuntimeError, match="component module name"):
        authority._validate_manifest_bindings(tmp_path, "f" * 40, manifest)
    components[-1]["module_name"] = "src.reporting.build_closure_evidence_matrix"
    components[0], components[1] = components[1], components[0]
    with pytest.raises(RuntimeError, match="component module name"):
        authority._validate_manifest_bindings(tmp_path, "f" * 40, manifest)
    components[0], components[1] = components[1], components[0]
    manifest["sealed_support_source_records"] = supports[:2]
    with pytest.raises(RuntimeError, match="support source record scope"):
        authority._validate_manifest_bindings(tmp_path, "f" * 40, manifest)

    receipt = json.loads(
        Path(authority.ATTEMPT_1_FAILURE_RECEIPT_PATH).read_text(
            encoding="utf-8"
        )
    )
    assert authority._validate_attempt_1_failure_receipt(receipt) == receipt
    repository_root = Path.cwd().resolve()
    historical_guard_present = os.path.lexists(
        repository_root / authority.RUN_GUARD_PATH
    )
    assert authority._validate_historical_guard_policy(
        repository_root,
        receipt,
    ) == {
        "path": authority.RUN_GUARD_PATH,
        "state": (
            "present_matches_origin_observation"
            if historical_guard_present
            else "absent_fresh_clone_compatible"
        ),
        "receipt_is_authority": True,
    }
    assert authority._validate_historical_guard_policy(tmp_path, receipt) == {
        "path": authority.RUN_GUARD_PATH,
        "state": "absent_fresh_clone_compatible",
        "receipt_is_authority": True,
    }
    drifted_receipt = copy.deepcopy(receipt)
    drifted_receipt["guard_observation"]["inode"] += 1
    with pytest.raises(RuntimeError, match="stale-guard observation"):
        authority._validate_attempt_1_failure_receipt(drifted_receipt)


def test_context_builder_runs_only_after_durable_first_record(tmp_path: Path) -> None:
    contract = _contract()
    public = _prime(tmp_path, contract)
    observations: list[dict[str, Any]] = []

    def builder(**kwargs: Any) -> dict[str, Any]:
        log = (tmp_path / authority.OUTCOME_ACCESS_LOG_PATH).read_bytes()
        observations.append(
            {
                "log": log,
                "guard": (tmp_path / authority.RUN_GUARD_PATH).is_file(),
            }
        )
        return {
            "execution_id": kwargs["execution_id"],
            "rng_seed": 1729,
            "tables": {},
            "stage_results": {},
            "model_availability": {},
            "software_evidence": {},
        }

    context = authority.open_sealed_batch_context(
        authority=public,
        sealed_batch_contract=contract,
        repo_root=tmp_path,
        context_builder=builder,
    )
    assert context["execution_id"] == "closure-v1-e0-u-test-execution"
    assert observations[0]["guard"] is True
    record = json.loads(observations[0]["log"])
    assert record == {
        "event": "sealed_outcome_context_opened",
        "execution_id": "closure-v1-e0-u-test-execution",
        "experiment_id": "closure_v1",
        "gate": "E0-U",
        "one_shot_consumed": True,
        "outcome_access_authorized": True,
        "schema_version": "closure_e0_u_access_log_v1",
    }
    with pytest.raises(RuntimeError, match="exactly once"):
        authority.open_sealed_batch_context(
            authority=public,
            sealed_batch_contract=contract,
            repo_root=tmp_path,
            context_builder=builder,
        )


def test_access_log_leaf_replacement_after_append_blocks_context_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = _contract()
    public = _prime(tmp_path, contract)
    original_append = authority._append_first_access_record
    canonical_log = tmp_path / authority.OUTCOME_ACCESS_LOG_PATH
    durable_log = canonical_log.with_name("outcome_access_log.durable.jsonl")
    builder_called = False

    def replace_after_append(repo_root: Path, execution_id: str) -> Any:
        result = original_append(repo_root, execution_id)
        canonical_log.rename(durable_log)
        canonical_log.write_bytes(b"")
        canonical_log.chmod(0o644)
        return result

    def builder(**kwargs: Any) -> dict[str, Any]:
        nonlocal builder_called
        builder_called = True
        return {"execution_id": kwargs["execution_id"]}

    monkeypatch.setattr(
        authority,
        "_append_first_access_record",
        replace_after_append,
    )
    with pytest.raises(RuntimeError, match="access log leaf or bytes drifted"):
        authority.open_sealed_batch_context(
            authority=public,
            sealed_batch_contract=contract,
            repo_root=tmp_path,
            context_builder=builder,
        )

    assert builder_called is False
    durable_record = json.loads(durable_log.read_bytes())
    assert durable_record["event"] == "sealed_outcome_context_opened"
    assert durable_record["one_shot_consumed"] is True
    assert canonical_log.read_bytes() == b""
    assert authority._STATE["access_log_identity"] is not None
    assert authority._STATE["access_log_lease"] is None
    assert authority._STATE["failed"] is True
    assert (tmp_path / authority.RUN_GUARD_PATH).is_file()


def test_repository_replacement_between_guard_and_append_never_reaches_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    original_repo = tmp_path / "repo-original"
    contract = _contract()
    public = _prime(repo, contract)
    original_append = authority._append_first_access_record
    builder_called = False

    def replace_root(repo_root: Path, execution_id: str) -> Any:
        repo.rename(original_repo)
        _prepare_root(repo)
        return original_append(repo_root, execution_id)

    def builder(**kwargs: Any) -> dict[str, Any]:
        nonlocal builder_called
        builder_called = True
        return {"execution_id": kwargs["execution_id"]}

    monkeypatch.setattr(authority, "_append_first_access_record", replace_root)
    with pytest.raises(RuntimeError, match="changed after authority require"):
        authority.open_sealed_batch_context(
            authority=public,
            sealed_batch_contract=contract,
            repo_root=repo,
            context_builder=builder,
        )

    assert builder_called is False
    assert (original_repo / authority.OUTCOME_ACCESS_LOG_PATH).read_bytes() == b""
    assert (repo / authority.OUTCOME_ACCESS_LOG_PATH).read_bytes() == b""
    assert not (original_repo / authority.RUN_GUARD_PATH).exists()
    assert not (repo / authority.RUN_GUARD_PATH).exists()
    assert authority._STATE["access_log_identity"] is None
    assert authority._STATE["failed"] is True


def test_repository_replacement_after_require_before_guard_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    original_repo = tmp_path / "repo-original"
    contract = _contract()
    public = _prime(repo, contract)
    original_create_guard = authority._create_guard
    builder_called = False

    def replace_before_guard(
        repo_root: Path,
        expected_root_identity: tuple[int, ...],
    ) -> Any:
        repo.rename(original_repo)
        _prepare_root(repo)
        return original_create_guard(repo_root, expected_root_identity)

    def builder(**kwargs: Any) -> dict[str, Any]:
        nonlocal builder_called
        builder_called = True
        return {"execution_id": kwargs["execution_id"]}

    monkeypatch.setattr(authority, "_create_guard", replace_before_guard)
    with pytest.raises(RuntimeError, match="changed after authority require"):
        authority.open_sealed_batch_context(
            authority=public,
            sealed_batch_contract=contract,
            repo_root=repo,
            context_builder=builder,
        )

    assert builder_called is False
    assert (original_repo / authority.OUTCOME_ACCESS_LOG_PATH).read_bytes() == b""
    assert (repo / authority.OUTCOME_ACCESS_LOG_PATH).read_bytes() == b""
    assert not (original_repo / authority.RUN_GUARD_PATH).exists()
    assert not (repo / authority.RUN_GUARD_PATH).exists()
    assert authority._STATE["guard_fd"] is None
    assert authority._STATE["guard_parent_anchor"] is None
    assert authority._STATE["access_log_identity"] is None
    assert authority._STATE["failed"] is True


def test_builder_failure_consumes_open_and_nonempty_log_blocks_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    public = _prime(tmp_path, contract)

    def fail_after_log(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        assert (tmp_path / authority.OUTCOME_ACCESS_LOG_PATH).stat().st_size > 0
        raise ValueError("intentional builder failure")

    with pytest.raises(ValueError, match="intentional"):
        authority.open_sealed_batch_context(
            authority=public,
            sealed_batch_contract=contract,
            repo_root=tmp_path,
            context_builder=fail_after_log,
        )
    assert (tmp_path / authority.OUTCOME_ACCESS_LOG_PATH).stat().st_size > 0
    assert authority._STATE["failed"] is True
    with pytest.raises(RuntimeError, match="exactly once"):
        authority.open_sealed_batch_context(
            authority=public,
            sealed_batch_contract=contract,
            repo_root=tmp_path,
            context_builder=fail_after_log,
        )

    _reset_state()
    recovery_root = tmp_path / "recovery"
    recovery_root.mkdir()
    recovery_public = _prime(recovery_root, contract)
    recovery_log = recovery_root / authority.OUTCOME_ACCESS_LOG_PATH
    recovery_log.write_bytes(authority._attempt_1_access_log_payload())
    old_guard = recovery_root / authority.RUN_GUARD_PATH
    old_guard.parent.mkdir(parents=True, exist_ok=True)
    old_guard.write_bytes(b"")
    old_guard.chmod(0o600)
    authority._STATE.update(
        {
            "recovery": True,
            "run_guard_path": authority.RECOVERY_RUN_GUARD_PATH,
            "execution_id": "closure-v1-e0-u-recovery-test-execution",
        }
    )
    monkeypatch.setattr(
        authority,
        "_load_attempt_1_failure_receipt",
        lambda *_args, **_kwargs: ({"guard_observation": {}}, {}),
    )
    monkeypatch.setattr(
        authority,
        "_validate_historical_guard_policy",
        lambda *_args, **_kwargs: {"state": "test-sealed"},
    )

    def fail_recovery_after_log(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        assert recovery_log.read_bytes() == authority._recovery_access_log_payload(
            "closure-v1-e0-u-recovery-test-execution"
        )
        assert old_guard.exists()
        raise ValueError("intentional recovery builder failure")

    with pytest.raises(ValueError, match="intentional recovery"):
        authority.open_sealed_recovery_batch_context(
            authority=recovery_public,
            sealed_batch_contract=contract,
            repo_root=recovery_root,
            context_builder=fail_recovery_after_log,
        )
    assert recovery_log.read_bytes().startswith(
        authority._attempt_1_access_log_payload()
    )
    assert old_guard.exists()
    assert (recovery_root / authority.RECOVERY_RUN_GUARD_PATH).exists()


def test_guard_cleanup_capture_restores_boundary_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = _contract()
    public = _prime(tmp_path, contract)
    _open(tmp_path, contract, public)
    guard = tmp_path / authority.RUN_GUARD_PATH
    moved = guard.with_name(guard.name + ".owned-moved")
    foreign_payload = b"foreign-guard\n"
    original_rename = os.rename
    swapped = False

    def replace_at_capture(
        source: str,
        destination: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        nonlocal swapped
        if source == guard.name and not swapped:
            swapped = True
            parent_fd = kwargs["src_dir_fd"]
            original_rename(
                source,
                moved.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            descriptor = os.open(
                source,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
            try:
                os.write(descriptor, foreign_payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "rename", replace_at_capture)
    with pytest.raises(RuntimeError, match="replaced at cleanup boundary"):
        authority._release_owned_guard(False)

    assert guard.read_bytes() == foreign_payload
    assert moved.read_bytes() == b""
    assert not list(guard.parent.glob(".closure-owned-capture-*"))


def test_guard_owned_directory_intrusion_is_preserved_and_reported(
    tmp_path: Path,
) -> None:
    contract = _contract()
    public = _prime(tmp_path, contract)
    _open(tmp_path, contract, public)
    guard_parent = (tmp_path / authority.RUN_GUARD_PATH).parent
    foreign = guard_parent / "foreign.keep"
    foreign.write_bytes(b"foreign")

    with pytest.raises(RuntimeError, match="directory cleanup was incomplete"):
        authority._release_owned_guard(True)

    assert foreign.read_bytes() == b"foreign"
    assert not (tmp_path / authority.RUN_GUARD_PATH).exists()
    assert authority._STATE["guard_fd"] is None


def test_guard_cleanup_restores_directory_boundary_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = _contract()
    public = _prime(tmp_path, contract)
    _open(tmp_path, contract, public)
    guard = tmp_path / authority.RUN_GUARD_PATH
    moved = guard.with_name(guard.name + ".owned-moved-directory-case")
    original_rename = os.rename
    swapped = False

    def replace_at_capture(
        source: str,
        destination: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        nonlocal swapped
        if source == guard.name and not swapped:
            swapped = True
            parent_fd = kwargs["src_dir_fd"]
            original_rename(
                source,
                moved.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            os.mkdir(source, 0o700, dir_fd=parent_fd)
        original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "rename", replace_at_capture)
    with pytest.raises(RuntimeError, match="replaced at cleanup boundary"):
        authority._release_owned_guard(False)

    assert guard.is_dir()
    assert moved.is_file()
    assert not list(guard.parent.glob(".closure-owned-capture-*"))


def test_publish_and_physical_audit_use_runner_serialized_bytes_manifest_last(
    tmp_path: Path,
) -> None:
    contract = _contract()
    public = _prime(tmp_path, contract)
    context = _open(tmp_path, contract, public)
    artifacts, serialized = _artifacts(contract)
    stage_results = {f"E{index}": {} for index in range(1, 11)}
    receipt = authority.publish_sealed_batch_artifacts(
        authority=public,
        sealed_batch_contract=contract,
        batch_context=context,
        stage_results=stage_results,
        artifacts=artifacts,
        serialized_artifacts=serialized,
        repo_root=tmp_path,
    )
    assert receipt["artifact_count"] == 52
    assert receipt["stage_count"] == 10
    assert receipt["manifest_written_last"] is True
    assert receipt["guard_released"] is True
    assert not (tmp_path / authority.RUN_GUARD_PATH).exists()
    for path, payload in serialized.items():
        physical = tmp_path / path
        assert physical.read_bytes() == payload
        assert physical.stat().st_nlink == 1
        assert physical.stat().st_mode & 0o777 == 0o644
    audit = authority.validate_published_sealed_batch_artifacts(
        authority=public,
        sealed_batch_contract=contract,
        batch_context=context,
        stage_results=stage_results,
        artifacts=artifacts,
        serialized_artifacts=serialized,
        publication_receipt=receipt,
        repo_root=tmp_path,
    )
    layout = authority._contract_layout(contract)
    assert audit["artifact_count"] == 52
    assert audit["physical_records"] == sorted(
        audit["physical_records"], key=lambda record: record["path"]
    )
    assert audit["publication_order"] == list(layout["publication_order"])
    for stage in contract["stages"][1:]:
        assert layout["publication_order"].index(stage["output_paths"][-1]) > max(
            layout["publication_order"].index(path)
            for path in stage["output_paths"][:-1]
        )


def test_mid_publication_collision_rolls_back_only_owned_inodes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = _contract()
    public = _prime(tmp_path, contract)
    context = _open(tmp_path, contract, public)
    artifacts, serialized = _artifacts(contract)
    layout = authority._contract_layout(contract)
    first, second = layout["publication_order"][:2]
    original = authority._publish_one
    calls = 0

    def collide(
        repo_root: Path,
        relative_path: str,
        payload: bytes,
        execution_id: str,
        owned_directories: list[dict[str, Any]],
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            foreign = repo_root / relative_path
            foreign.parent.mkdir(parents=True, exist_ok=True)
            foreign.write_bytes(b"foreign\n")
        return original(
            repo_root,
            relative_path,
            payload,
            execution_id,
            owned_directories,
        )

    monkeypatch.setattr(authority, "_publish_one", collide)
    with pytest.raises(RuntimeError, match="rollback was incomplete"):
        authority.publish_sealed_batch_artifacts(
            authority=public,
            sealed_batch_contract=contract,
            batch_context=context,
            stage_results={f"E{index}": {} for index in range(1, 11)},
            artifacts=artifacts,
            serialized_artifacts=serialized,
            repo_root=tmp_path,
        )
    assert not (tmp_path / first).exists()
    assert (tmp_path / second).read_bytes() == b"foreign\n"
    assert authority._STATE["failed"] is True
    assert (tmp_path / authority.OUTCOME_ACCESS_LOG_PATH).stat().st_size > 0


def test_publication_temp_capture_restores_boundary_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = _contract()
    _prime(tmp_path, contract)
    parent = tmp_path / "reports" / "synthetic"
    parent.mkdir(parents=True)
    relative_path = "reports/synthetic/result.json"
    execution_id = "boundary"
    temporary_leaf = ".result.json.closure-e0-u-boundary.tmp"
    moved_leaf = temporary_leaf + ".owned-moved"
    payload = b"owned-output\n"
    foreign_payload = b"foreign-temporary\n"
    original_rename = os.rename
    swapped = False

    def replace_at_capture(
        source: str,
        destination: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        nonlocal swapped
        if source == temporary_leaf and not swapped:
            swapped = True
            parent_fd = kwargs["src_dir_fd"]
            original_rename(
                source,
                moved_leaf,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            descriptor = os.open(
                source,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
            try:
                os.write(descriptor, foreign_payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "rename", replace_at_capture)
    with pytest.raises(RuntimeError, match="cleanup was incomplete"):
        authority._publish_one(
            tmp_path,
            relative_path,
            payload,
            execution_id,
            [],
        )

    assert not (tmp_path / relative_path).exists()
    assert (parent / temporary_leaf).read_bytes() == foreign_payload
    assert (parent / moved_leaf).read_bytes() == payload
    assert not list(parent.glob(".closure-owned-capture-*"))


def test_publication_output_capture_restores_boundary_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = _contract()
    _prime(tmp_path, contract)
    parent = tmp_path / "reports" / "synthetic"
    parent.mkdir(parents=True)
    relative_path = "reports/synthetic/result.json"
    payload = b"owned-output\n"
    record = authority._publish_one(
        tmp_path,
        relative_path,
        payload,
        "boundary",
        [],
    )
    output = tmp_path / relative_path
    moved = output.with_name(output.name + ".owned-moved")
    foreign_payload = b"foreign-output\n"
    original_rename = os.rename
    swapped = False

    def replace_at_capture(
        source: str,
        destination: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        nonlocal swapped
        if source == output.name and not swapped:
            swapped = True
            parent_fd = kwargs["src_dir_fd"]
            original_rename(
                source,
                moved.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            descriptor = os.open(
                source,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o644,
                dir_fd=parent_fd,
            )
            try:
                os.write(descriptor, foreign_payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "rename", replace_at_capture)
    try:
        with pytest.raises(RuntimeError, match="replaced at cleanup boundary"):
            authority._unlink_owned_leaf(tmp_path, record)
    finally:
        authority._close_publication_anchors([record])

    assert output.read_bytes() == foreign_payload
    assert moved.read_bytes() == payload
    assert not list(parent.glob(".closure-owned-capture-*"))


def test_ancestor_replacement_between_outputs_rolls_back_original_inode_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = _contract()
    public = _prime(tmp_path, contract)
    context = _open(tmp_path, contract, public)
    artifacts, serialized = _artifacts(contract)
    layout = authority._contract_layout(contract)
    first, second = layout["publication_order"][:2]
    original = authority._publish_one
    calls = 0
    moved_parent: Path | None = None
    replacement_payload = b"replacement-owned-by-someone-else\n"

    def replace_ancestor_then_fail(
        repo_root: Path,
        relative_path: str,
        payload: bytes,
        execution_id: str,
        owned_directories: list[dict[str, Any]],
    ) -> dict[str, Any]:
        nonlocal calls, moved_parent
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic later output failure")
        result = original(
            repo_root,
            relative_path,
            payload,
            execution_id,
            owned_directories,
        )
        first_parent = repo_root / Path(relative_path).parent
        moved_parent = first_parent.with_name(first_parent.name + "-original")
        first_parent.rename(moved_parent)
        first_parent.mkdir()
        (first_parent / Path(relative_path).name).write_bytes(replacement_payload)
        return result

    monkeypatch.setattr(authority, "_publish_one", replace_ancestor_then_fail)
    with pytest.raises(RuntimeError, match="rollback was incomplete"):
        authority.publish_sealed_batch_artifacts(
            authority=public,
            sealed_batch_contract=contract,
            batch_context=context,
            stage_results={f"E{index}": {} for index in range(1, 11)},
            artifacts=artifacts,
            serialized_artifacts=serialized,
            repo_root=tmp_path,
        )

    assert moved_parent is not None
    assert not (moved_parent / Path(first).name).exists()
    assert (tmp_path / first).read_bytes() == replacement_payload
    assert not (moved_parent / Path(second).name).exists()
    assert authority._STATE["failed"] is True
    assert not (tmp_path / authority.RUN_GUARD_PATH).exists()


def test_guard_parent_symlink_fails_before_consuming_log(tmp_path: Path) -> None:
    contract = _contract()
    public = _prime(tmp_path, contract)
    linked = tmp_path / "linked"
    linked.mkdir()
    guard_parent = tmp_path / "tmp" / "closure_v1_e0_u"
    guard_parent.parent.mkdir()
    guard_parent.symlink_to(linked, target_is_directory=True)
    with pytest.raises(OSError):
        _open(tmp_path, contract, public)
    assert (tmp_path / authority.OUTCOME_ACCESS_LOG_PATH).read_bytes() == b""


def test_dvc_policy_must_partition_exact52() -> None:
    contract = _contract()
    layout = authority._contract_layout(contract)
    paths = list(layout["expected_paths"])
    heavy = sorted(
        path
        for path, format_name in layout["formats_by_path"].items()
        if format_name == "parquet"
    )
    policy = {
        "direct_git_artifact_paths": sorted(paths[4:]),
        "dvc_add_after_success_only": True,
        "dvc_pointer_paths": sorted(path + ".dvc" for path in heavy),
        "dvc_push_after_audit_only": True,
        "heavy_artifact_paths": heavy,
        "implicit_dvc_forbidden": True,
    }
    assert authority._validate_dvc_policy(
        policy,
        layout["expected_paths"],
        layout["formats_by_path"],
    ) == policy
    policy["direct_git_artifact_paths"].append(heavy[0])
    policy["direct_git_artifact_paths"].sort()
    with pytest.raises(RuntimeError, match="partition exact52"):
        authority._validate_dvc_policy(
            policy,
            layout["expected_paths"],
            layout["formats_by_path"],
        )
