from __future__ import annotations

import inspect
import hashlib
import json
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest
import yaml

from src.experiments import (
    closure_final_calibration_platt_parameter_dialect_patch as calibration,
)
from src.experiments import run_closure_anfis_learning_curve as runner
from src.experiments.closure_runtime_contract import (
    anfis_hash_rank_sample,
    anfis_module_substreams,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SIZES = (4096, 16384, 65536)
EXPECTED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
EXPECTED_MODULES = ("ANFIS-N", "ANFIS-F", "ANFIS-T-no-current")
EXPECTED_ELIGIBLE_ROWS = {
    "ANFIS-N": 4757,
    "ANFIS-F": 35273,
    "ANFIS-T-no-current": 35419,
}
EXPECTED_OUTPUTS = (
    "reports/closure_v1/07_anfis_ablation/anfis_learning_curve.csv",
    "reports/closure_v1/07_anfis_ablation/anfis_learning_curve_manifest.json",
)
E7_DVC_POINTER_PATH = Path("inputs/e7/e7_payloads.dvc")
EXPECTED_OWNED_CAPABILITY_KEYS = frozenset(
    {
        "path",
        "device",
        "inode",
        "mode",
        "nlink",
        "size",
        "mtime_ns",
        "ctime_ns",
        "sha256",
    }
)


def _e7_input_payload(index: int) -> bytes:
    return f"E0-MCAL E7 scientific input {index:02d}\n".encode()


def _e7_pointer_payload() -> bytes:
    total = sum(len(_e7_input_payload(index)) for index in range(15))
    return (
        "outs:\n"
        f"- md5: {'0' * 32}.dir\n"
        f"  size: {total}\n"
        "  nfiles: 15\n"
        "  hash: md5\n"
        "  path: payloads\n"
    ).encode()


def _runtime() -> dict[str, Any]:
    payload = yaml.safe_load(
        (ROOT / "configs/closure_v1/final_calibration_runtime.yaml").read_text()
    )
    assert isinstance(payload, dict)
    return payload


def _e7_required_inputs() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index in range(15):
        payload = _e7_input_payload(index)
        records.append(
            {
                "role": f"e7_input_{index:02d}",
                "path": f"inputs/e7/payloads/input_{index:02d}.bin",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return records


def _e7_authority() -> dict[str, Any]:
    records = _e7_required_inputs()
    digest = hashlib.sha256(
        json.dumps(
            records,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "gate": calibration.PATCH_GATE,
        "status": "effective",
        "authority_binding_sha256": "a" * 64,
        "e7_terminal_record": _runtime()["e7_terminal_record"],
        "scientific_input_inventory": {
            "e7_required_input_count": 15,
            "e7_required_inputs": records,
            "e7_required_inputs_sha256": digest,
            "authority_records": [
                {
                    "role": "e7_payload_directory_pointer",
                    "path": E7_DVC_POINTER_PATH.as_posix(),
                    "bytes": len(_e7_pointer_payload()),
                    "sha256": hashlib.sha256(_e7_pointer_payload()).hexdigest(),
                }
            ],
            "payload_bindings": records,
        },
    }


def _materialize_e7_inputs(repo_root: Path) -> None:
    pointer = repo_root / E7_DVC_POINTER_PATH
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_bytes(_e7_pointer_payload())
    pointer.chmod(0o644)
    for index, record in enumerate(_e7_required_inputs()):
        payload = _e7_input_payload(index)
        path = repo_root / record["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if index == 0:
            payload_md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
            cache = (
                repo_root
                / ".dvc/cache/files/md5"
                / payload_md5[:2]
                / payload_md5[2:]
            )
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(payload)
            cache.chmod(0o444)
            os.link(cache, path)
        else:
            path.write_bytes(payload)
            path.chmod(0o644)


def _surface(row_count: int = 5000) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index in range(row_count):
        site_id = f"site-{index % 41:02d}"
        base_month = cast(pd.Period, pd.Period("2000-01", freq="M"))
        year_month = str(base_month + index // 41)
        rows.append(
            {
                "row_id": f"row-{index:06d}",
                "source_id": "wqp",
                "site_id": site_id,
                "year_month": year_month,
                "assignment_role": "development",
                "time_role": "training",
                "yN": float(index % 101) / 100.0,
                "yF": float((index * 3) % 101) / 100.0,
                "yT_no_chla": float((index * 7) % 101) / 100.0,
                "tp_pressure": float(index % 97) / 96.0,
                "tn_pressure": float((index * 5) % 97) / 96.0,
                "ratio_imbalance_pressure": float((index * 11) % 97) / 96.0,
                "do_good": float((index * 13) % 97) / 96.0,
                "ph_good": float((index * 17) % 97) / 96.0,
                "turbidity_good": float((index * 19) % 97) / 96.0,
                "secchi_good": float((index * 23) % 97) / 96.0,
                "temp_favorable": float((index * 29) % 97) / 96.0,
                "feature_value": float(index % 97) / 96.0,
            }
        )
    return pd.DataFrame(rows)


def _terminal_curve(*, failed: set[tuple[int, int]] | None = None) -> pd.DataFrame:
    failures = (
        {(size, seed) for size in EXPECTED_SIZES[1:] for seed in EXPECTED_SEEDS}
        if failed is None
        else failed
    )
    rows: list[dict[str, Any]] = []
    for size in EXPECTED_SIZES:
        for seed in EXPECTED_SEEDS:
            failure = (size, seed) in failures
            row: dict[str, Any] = {
                "training_rows_per_module": size,
                "base_seed": seed,
                "status": "resource_failure_recorded" if failure else "completed",
                "completed_module_fit_count": 0 if failure else 3,
                "resource_limitation": (
                    " | ".join(
                        f"{module}: E7 candidate universe has "
                        f"{EXPECTED_ELIGIBLE_ROWS[module]} rows; "
                        f"{size} are required"
                        for module in EXPECTED_MODULES
                        if size > EXPECTED_ELIGIBLE_ROWS[module]
                    )
                    if failure
                    else ""
                ),
                "resource_failure_timing": (
                    "pre_fit_exact_eligibility_check" if failure else ""
                ),
                "downstream_metrics_status": (
                    "not_estimable_without_separate_temporal_consumers"
                ),
                "saturation_claim_authorized": False,
            }
            if not failure:
                for token in ("anfis_n", "anfis_f", "anfis_t_no_current"):
                    row.update(
                        {
                            f"{token}_final_checkpoint_loss": 0.1,
                            f"{token}_rule_count": 8,
                            f"{token}_epochs": 60,
                            f"{token}_quality_gate_output_standard_deviation": 0.2,
                            f"{token}_maximum_parameter_delta": 0.01,
                            f"{token}_centers_ordered": True,
                            f"{token}_centers_in_unit_interval": True,
                            f"{token}_selected_keys_sha256": "0" * 64,
                            f"{token}_computational_cost_proxy": size * 8 * 60,
                            f"{token}_quality_gate_output_scope": (
                                f"e7_stratified_training_sample_{size}"
                            ),
                        }
                    )
            rows.append(row)
    return pd.DataFrame(rows)


def _execution_policy() -> dict[str, Any]:
    return {
        "torch_cpu_execution_policy": {
            "device": "cpu",
            "torch_num_threads": 1,
            "torch_num_interop_threads": 1,
            "blas_thread_environment_control": "not_locked_by_e0_dl_v1",
            "bitwise_reproducibility_claim": (
                "forbidden_across_processes_or_blas_backends"
            ),
            "torch_num_threads_observed": 1,
            "torch_num_interop_threads_observed": 1,
        },
        "threadpool_limit": 1,
    }


def _success_sample_evidence(
    *, module: str, base_seed: int, training_size: int
) -> dict[str, Any]:
    eligible_rows = EXPECTED_ELIGIBLE_ROWS[module]
    strata = [
        {
            "holdout_group_id": "wqp::site-00",
            "temporal_period": "early",
            "expert_anchor_band": "low",
            "eligible_rows": eligible_rows,
            "selected_rows": training_size,
        }
    ]
    month_period_map = {"2018-01": "early"}
    month_digest = hashlib.sha256(
        runner._canonical_json_bytes({"month_period_map": month_period_map})
    ).hexdigest()
    return {
        "module": module,
        "base_seed": base_seed,
        "training_size": training_size,
        "input_rows": eligible_rows,
        "eligible_rows": eligible_rows,
        "eligible_universe_rows": eligible_rows,
        "eligible_universe_sha256": hashlib.sha256(
            f"{module}:{eligible_rows}".encode()
        ).hexdigest(),
        "selected_rows": training_size,
        "selected_row_count": training_size,
        "selected_keys_sha256": hashlib.sha256(
            f"{module}:{base_seed}:{training_size}".encode()
        ).hexdigest(),
        "sampling_strata": [
            "holdout_group_id",
            "temporal_period",
            "expert_anchor_band",
        ],
        "stratum_count": 1,
        "strata": strata,
        "strata_sha256": hashlib.sha256(
            runner._canonical_json_bytes({"records": strata})
        ).hexdigest(),
        "strata_derivation": {
            "holdout_group_rule": "source_id::site_id",
            "month_period_map": month_period_map,
            "month_period_map_sha256": month_digest,
            "expert_anchor_band_cuts": [0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0],
            "expert_anchor_band_labels": ["low", "middle", "high"],
        },
        "month_period_map": month_period_map,
        "month_period_map_sha256": month_digest,
        "replacement": False,
        "replacement_used": False,
        "module_seed": int(anfis_module_substreams(base_seed)[module]),
    }


def _synthetic_sample(
    *, module: str, base_seed: int, training_size: int
) -> tuple[pd.DataFrame, dict[str, Any]]:
    eligible_rows = EXPECTED_ELIGIBLE_ROWS[module]
    if training_size > eligible_rows:
        raise runner.LearningCurveResourceError(
            f"E7 candidate universe has {eligible_rows} rows; "
            f"{training_size} are required",
            eligible_rows=eligible_rows,
        )
    return pd.DataFrame(
        {
            "source_id": ["wqp"],
            "site_id": ["site-00"],
            "year_month": ["2018-01"],
            "row_id": [f"{module}:{base_seed}:{training_size}"],
            "rank_sha256": ["0" * 64],
        }
    ), _success_sample_evidence(
        module=module,
        base_seed=base_seed,
        training_size=training_size,
    )


def _terminal_evidence() -> dict[str, Any]:
    preflights: list[dict[str, Any]] = []
    for size in EXPECTED_SIZES:
        for seed in EXPECTED_SEEDS:
            for module in EXPECTED_MODULES:
                record: dict[str, Any] = {
                    "module": module,
                    "base_seed": seed,
                    "training_size": size,
                    "eligible_rows": EXPECTED_ELIGIBLE_ROWS[module],
                }
                if size <= EXPECTED_ELIGIBLE_ROWS[module]:
                    record = _success_sample_evidence(
                        module=module,
                        base_seed=seed,
                        training_size=size,
                    )
                else:
                    record.update(
                        {
                            "status": "resource_failure_recorded",
                            "reason": (
                                f"E7 candidate universe has "
                                f"{EXPECTED_ELIGIBLE_ROWS[module]} rows; "
                                f"{size} are required"
                            ),
                        }
                    )
                preflights.append(record)
    return {
        "experiment_id": "E7",
        "terminal_row_count": 15,
        "completed_slot_count": 5,
        "resource_failure_count": 10,
        "completed_module_fit_count": 15,
        "new_e7_fit_count": 15,
        "primary_fit_reuse_count": 0,
        "primary_slots_untouched": True,
        "sample_evidence": preflights,
        "execution_policy": _execution_policy(),
        "silent_omission": False,
        "post_hoc_substitution_performed": False,
        "saturation_claim_authorized": False,
    }


def test_constants_close_exact_sizes_seeds_modules_and_e7_paths() -> None:
    assert runner.TRAINING_SIZES == EXPECTED_SIZES
    assert runner.BASE_SEEDS == EXPECTED_SEEDS
    assert tuple(runner.PRIMARY_MODULES) == EXPECTED_MODULES
    assert tuple(path.relative_to(ROOT).as_posix() for path in runner.OUTPUT_PATHS) == EXPECTED_OUTPUTS
    assert runner.OUTPUT_PATHS[-1] == runner.MANIFEST_PATH
    assert len(EXPECTED_SIZES) * len(EXPECTED_SEEDS) == 15
    source = inspect.getsource(runner)
    assert "locked_hash_ranked_training_sample_4096" not in source
    assert "e7_stratified_training_sample_" in source


def test_cli_is_one_shot_closed_and_translates_domain_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert runner.parse_args(["--check-only"]).check_only is True
    assert runner.parse_args(["--execute-one-shot"]).execute_one_shot is True
    for argv in ([], ["--check-only", "--execute-one-shot"], ["--execute-lock"]):
        with pytest.raises(SystemExit):
            runner.parse_args(argv)
    monkeypatch.setattr(runner, "check_only", lambda: {"status": "ready_to_run_learning_curve"})
    assert runner.main(["--check-only"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ready_to_run_learning_curve"

    def fail() -> dict[str, Any]:
        raise calibration.FinalCalibrationError("closed")

    monkeypatch.setattr(runner, "execute_one_shot", fail)
    assert runner.main(["--execute-one-shot"]) == 2
    assert capsys.readouterr().err.strip() == "closed"


def test_check_only_requires_effective_p_before_io_and_is_nonwriting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert runner.calibration is calibration
    assert calibration.PATCH_GATE == "E0-MCALJ"
    calls: list[tuple[bool, Path]] = []
    events: list[str] = []
    authority = {"gate": calibration.PATCH_GATE, "status": "effective"}

    def require(*, verify_remote: bool, repo_root: Path) -> dict[str, Any]:
        events.append("gate")
        calls.append((verify_remote, repo_root))
        return authority

    namespace = {
        "runner": "e7",
        "r_lifecycle_state": (
            "calibration_completed_unpublished_ready_for_e7_bundle"
        ),
        "calibration_bundle_complete": True,
        "e7_bundle_absent": True,
    }

    def require_namespace(*, runner: str, repo_root: Path) -> dict[str, Any]:
        assert runner == "e7" and repo_root == tmp_path
        events.append("namespace")
        return namespace

    monkeypatch.setattr(
        calibration, "require_final_calibration_authority", require
    )
    monkeypatch.setattr(
        calibration,
        "require_final_calibration_run_namespace",
        require_namespace,
    )
    result = runner.check_only(repo_root=tmp_path)
    assert calls == [(True, tmp_path)]
    assert events == ["gate", "namespace"]
    assert result["namespace"] == namespace
    assert result["training_sizes"] == list(EXPECTED_SIZES)
    assert result["base_seeds"] == list(EXPECTED_SEEDS)
    assert result["slot_count"] == 15
    assert result["output_count"] == 2
    for key in (
        "writes_performed",
        "fit_run",
        "dvc_commands_run",
        "scientific_network_commands_run",
        "holdout_accessed",
        "post_2021_rows_accessed",
        "future_outcomes_accessed",
    ):
        assert result[key] is False
    assert list(tmp_path.iterdir()) == []

    monkeypatch.setattr(
        calibration,
        "require_final_calibration_authority",
        lambda **_: (_ for _ in ()).throw(calibration.FinalCalibrationError("gate")),
    )
    events.clear()
    with pytest.raises(calibration.FinalCalibrationError, match="gate"):
        runner.check_only(repo_root=tmp_path)
    assert events == []
    assert list(tmp_path.iterdir()) == []


def test_public_sampling_run_and_builder_signatures_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = inspect.getsource(runner)
    assert (
        "closure_final_calibration_platt_parameter_dialect_patch as calibration"
        in source
    )
    execution_source = inspect.getsource(
        runner._execute_one_shot_with_pinned_inputs
    )
    assert execution_source.count("require_final_calibration_authority(") == 1
    assert (
        execution_source.count(
            "revalidate_final_calibration_owned_run_publication("
        )
        == 2
    )
    sample = inspect.signature(runner.select_learning_curve_sample).parameters
    assert list(sample) == [
        "rows",
        "module",
        "base_seed",
        "training_size",
        "development_keys",
    ]
    run = inspect.signature(runner.run_learning_curve).parameters
    assert list(run) == ["surface", "runtime", "gate", "fit_slot"]
    build = inspect.signature(runner.build_anfis_learning_curve_bundle).parameters
    assert list(build) == ["authority", "curve", "evidence", "input_records", "repo_root"]

    # The E7 adapter must consume the P-bound MCAL runtime contract without
    # re-entering the obsolete development-runtime effective-Git chain.  That
    # historical chain now (correctly) rejects the post-registration DVC
    # artifact shape, so calling it here would make the published MCAL gate
    # unusable even though its exact runtime bytes are already authorized.
    loader_source = inspect.getsource(runner._load_learning_curve_surface)
    assert "_load_mcal_development_runtime_from_pinned_inputs" in loader_source
    assert "_validate_pinned_historical_e7_blockers" in loader_source
    assert "load_and_validate_development_runtime(" not in loader_source
    assert "load_and_validate_final_calibration_runtime(" not in loader_source
    assert "validate_historical_e7_blockers(repo_root" not in loader_source
    physical_runtime, runtime_audit = (
        runner.calibration_runner._load_mcal_development_runtime(repo_root=ROOT)
    )
    assert physical_runtime["schema_version"] == "closure_development_runtime_v1"
    assert physical_runtime["cpu_execution_policy"] == {
        "device": "cpu",
        "torch_num_threads": 1,
        "torch_num_interop_threads": 1,
        "blas_thread_environment_control": "not_locked_by_e0_dl_v1",
        "bitwise_reproducibility_claim": (
            "forbidden_across_processes_or_blas_backends"
        ),
    }
    assert runtime_audit["validation_scope"] == (
        "exact_schema_contract_under_effective_e0_mcal_authority"
    )
    calls: list[str] = []
    terminal_contract = {
        "historical_e7_blocker_adopted": True,
        "supersession_scope": "e7_only_additive_authority",
        "eligible_rows_by_module": {
            "ANFIS-N": 4757,
            "ANFIS-F": 35273,
            "ANFIS-T-no-current": 35419,
        },
        "expected_completed_slot_count": 5,
        "expected_completed_module_fit_count": 15,
        "expected_resource_failure_record_count": 10,
    }

    class PinnedProbe:
        authority = {
            "historical_e7_blocker_adopted": True,
            "e7_authority_correction": {
                "supersession_scope": "e7_only_additive_authority"
            },
            "e7_expected_completed_slot_count": 5,
            "e7_expected_completed_module_fit_count": 15,
            "e7_expected_resource_failure_record_count": 10,
        }

        def payload(self, path: str) -> bytes:
            calls.append(f"payload:{path}")
            return (ROOT / path).read_bytes()

        def revalidate(self) -> None:
            calls.append("pinned_revalidate")

    pinned = PinnedProbe()
    pinned_runtime, pinned_audit = (
        runner._load_mcal_development_runtime_from_pinned_inputs(
            cast(Any, pinned)
        )
    )
    assert pinned_runtime == physical_runtime
    assert pinned_audit == runtime_audit
    assert calls == [
        "payload:configs/closure_v1/development_runtime.yaml",
        "payload:configs/closure_v1/development_runtime.schema.json",
    ]
    calls.clear()
    monkeypatch.setattr(
        runner,
        "_validate_pinned_historical_e7_blockers",
        lambda observed: (
            calls.append("historical_bindings")
            or [{"role": "sealed"}]
            if observed is pinned
            else pytest.fail("loader changed its pinned authority")
        ),
    )
    gate = SimpleNamespace(development_keys={("wqp", "site-00")})
    monkeypatch.setattr(
        runner,
        "_load_mcal_development_runtime_from_pinned_inputs",
        lambda observed: (
            calls.append("runtime_adapter")
            or (physical_runtime, runtime_audit)
            if observed is pinned
            else pytest.fail("runtime adapter changed its pinned authority")
        ),
    )
    surface = _surface(30)
    monkeypatch.setattr(
        runner,
        "_pinned_development_gate",
        lambda observed: (
            calls.append("development_gate") or gate
            if observed is pinned
            else pytest.fail("gate changed its pinned authority")
        ),
    )
    monkeypatch.setattr(
        runner,
        "_pinned_learning_curve_surface",
        lambda observed, **_: (
            calls.append("surface") or surface
            if observed is pinned
            else pytest.fail("surface changed its pinned authority")
        ),
    )
    loaded = runner._load_learning_curve_surface(
        pinned_inputs=cast(Any, pinned), repo_root=ROOT
    )
    assert calls == [
        "historical_bindings",
        "runtime_adapter",
        "development_gate",
        "surface",
    ]
    assert loaded["surface"] is surface
    assert loaded["runtime"]["e0_mcal_e7_terminal_record"] == terminal_contract
    assert loaded["runtime_audit"] == runtime_audit


def test_sample_is_exact_deterministic_and_preserves_unique_rows() -> None:
    surface = _surface()
    first, first_evidence = runner.select_learning_curve_sample(
        surface,
        module="ANFIS-N",
        base_seed=1729,
        training_size=4096,
    )
    second, second_evidence = runner.select_learning_curve_sample(
        surface,
        module="ANFIS-N",
        base_seed=1729,
        training_size=4096,
    )
    assert len(first) == 4096
    assert first["row_id"].is_unique
    pd.testing.assert_frame_equal(first, second)
    assert first_evidence == second_evidence
    assert first_evidence["training_size"] == 4096
    assert first_evidence["selected_rows"] == 4096
    assert first_evidence["replacement_used"] is False


def test_sample_is_invariant_to_source_row_order() -> None:
    surface = _surface()
    expected, expected_evidence = runner.select_learning_curve_sample(
        surface,
        module="ANFIS-F",
        base_seed=20260612,
        training_size=4096,
    )
    shuffled = surface.sample(frac=1.0, random_state=9).reset_index(drop=True)
    observed, observed_evidence = runner.select_learning_curve_sample(
        shuffled,
        module="ANFIS-F",
        base_seed=20260612,
        training_size=4096,
    )
    pd.testing.assert_frame_equal(expected, observed)
    assert expected_evidence == observed_evidence


def test_sample_is_stratified_by_exact_three_locked_columns() -> None:
    surface = _surface()
    development_keys = {
        (str(source), str(site))
        for source, site in surface[["source_id", "site_id"]].itertuples(
            index=False, name=None
        )
    }
    sample, evidence = runner.select_learning_curve_sample(
        surface,
        module="ANFIS-T-no-current",
        base_seed=314159,
        training_size=4096,
        development_keys=development_keys,
    )
    assert sample["holdout_group_id"].equals(
        sample["source_id"].astype(str) + "::" + sample["site_id"].astype(str)
    )
    months = sorted(surface["year_month"].unique().tolist())
    expected_month_map = {
        month: ("early", "middle", "late")[min(2, 3 * index // len(months))]
        for index, month in enumerate(months)
    }
    derivation = evidence["strata_derivation"]
    assert dict(derivation["month_period_map"]) == expected_month_map
    assert len(derivation["month_period_map_sha256"]) == 64
    assert sample["temporal_period"].equals(
        sample["year_month"].map(expected_month_map)
    )
    expected_bands = pd.cut(
        sample["yT_no_chla"],
        bins=[-float("inf"), 1.0 / 3.0, 2.0 / 3.0, float("inf")],
        labels=["low", "middle", "high"],
        right=False,
    ).astype(str)
    assert sample["expert_anchor_band"].equals(expected_bands)
    assert evidence["stratum_count"] == sample.groupby(
        ["holdout_group_id", "temporal_period", "expert_anchor_band"], dropna=False
    ).ngroups
    assert {
        tuple(record[column] for column in runner.STRATUM_COLUMNS)
        for record in evidence["strata"]
    } == set(
        sample.loc[:, list(runner.STRATUM_COLUMNS)].itertuples(index=False, name=None)
    )
    assert evidence["replacement_used"] is False

    module_seed = anfis_module_substreams(314159)["ANFIS-T-no-current"]
    _, production_audit = anfis_hash_rank_sample(
        surface.to_dict(orient="records"),
        module="ANFIS-T-no-current",
        module_seed=module_seed,
        development_keys=development_keys,
    )
    assert evidence["eligible_universe_rows"] == production_audit[
        "eligible_universe_rows"
    ]
    assert evidence["eligible_universe_sha256"] == production_audit[
        "eligible_universe_sha256"
    ]

    poisoned = surface.assign(
        holdout_group_id="foreign",
        temporal_period="foreign",
        expert_anchor_band="foreign",
    )
    poisoned_sample, poisoned_evidence = runner.select_learning_curve_sample(
        poisoned,
        module="ANFIS-T-no-current",
        base_seed=314159,
        training_size=4096,
        development_keys=development_keys,
    )
    pd.testing.assert_frame_equal(sample, poisoned_sample)
    assert evidence == poisoned_evidence


def test_sample_rejects_non_development_keys_holdout_and_post_2021() -> None:
    surface = _surface()
    development_keys = {
        (str(source), str(site))
        for source, site in surface[["source_id", "site_id"]].itertuples(index=False, name=None)
    }
    runner.select_learning_curve_sample(
        surface,
        module="ANFIS-N",
        base_seed=1729,
        training_size=4096,
        development_keys=development_keys,
    )
    drifts: list[pd.DataFrame] = []
    for column, value in (
        ("assignment_role", "holdout"),
        ("year_month", "2022-01"),
        ("source_id", "foreign"),
    ):
        drift = surface.copy()
        drift.loc[0, column] = value
        drifts.append(drift)
    for drift in drifts:
        with pytest.raises(calibration.FinalCalibrationError):
            runner.select_learning_curve_sample(
                drift,
                module="ANFIS-N",
                base_seed=1729,
                training_size=4096,
                development_keys=development_keys,
            )


def test_sample_rejects_missing_duplicate_and_noncanonical_inputs() -> None:
    surface = _surface()
    cases: list[tuple[pd.DataFrame, str, Any, Any]] = [
        (surface.drop(columns="yN"), "ANFIS-N", 1729, 4096),
        (pd.concat([surface, surface.iloc[[0]]], ignore_index=True), "ANFIS-N", 1729, 4096),
        (surface, "unknown", 1729, 4096),
        (surface, "ANFIS-N", 7, 4096),
        (surface, "ANFIS-N", True, 4096),
        (surface, "ANFIS-N", 1729, 4095),
        (surface, "ANFIS-N", 1729, True),
        (
            pd.DataFrame(
                {
                    "row_id": [f"row-{index}" for index in range(4096)],
                    "source_id": ["wqp"] * 4096,
                    "site_id": [f"site-{index}" for index in range(4096)],
                    "role": ["training"] * 4096,
                    "target_year_month": ["2018-12"] * 4096,
                    "is_holdout": [False] * 4096,
                    "holdout_group_id": ["caller-controlled"] * 4096,
                    "temporal_period": ["caller-controlled"] * 4096,
                    "expert_anchor_band": ["caller-controlled"] * 4096,
                }
            ),
            "ANFIS-N",
            1729,
            4096,
        ),
    ]
    for rows, module, seed, size in cases:
        with pytest.raises(calibration.FinalCalibrationError):
            runner.select_learning_curve_sample(
                rows,
                module=module,
                base_seed=seed,
                training_size=size,
            )


def test_run_uses_canonical_15_slots_with_exact_five_completed_and_ten_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_calls: list[tuple[str, int, int]] = []
    fit_calls: list[tuple[str, int, int]] = []

    def sample(
        _rows: pd.DataFrame,
        *,
        module: str,
        base_seed: int,
        training_size: int,
        development_keys: Any = None,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        assert development_keys is not None
        sample_calls.append((module, base_seed, training_size))
        return _synthetic_sample(
            module=module,
            base_seed=base_seed,
            training_size=training_size,
        )

    def fit_slot(
        surface: pd.DataFrame,
        *,
        runtime: Mapping[str, Any],
        gate: Any,
        module: str,
        base_seed: int,
        prepared_sample: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]],
    ) -> Mapping[str, Any]:
        del surface, runtime, gate
        evidence = prepared_sample[2]
        fit_calls.append((module, base_seed, int(evidence["training_size"])))
        return {
            "status": "passed",
            "final_checkpoint_loss": 0.1,
            "rule_count": 8,
            "epochs": 60,
            "quality_gate_output_standard_deviation": 0.2,
            "maximum_parameter_delta": 0.01,
            "centers_ordered": True,
            "centers_in_unit_interval": True,
        }

    monkeypatch.setattr(runner, "select_learning_curve_sample", sample)
    gate = SimpleNamespace(
        development_keys={
            ("wqp", f"site-{index:02d}") for index in range(41)
        }
    )
    curve, evidence = runner.run_learning_curve(
        _surface(30), runtime=_runtime(), gate=gate, fit_slot=fit_slot
    )
    expected_slots = [(size, seed) for size in EXPECTED_SIZES for seed in EXPECTED_SEEDS]
    assert list(curve[["training_rows_per_module", "base_seed"]].itertuples(index=False, name=None)) == expected_slots
    assert list(curve["status"]) == ["completed"] * 5 + [
        "resource_failure_recorded"
    ] * 10
    assert len(sample_calls) == 45
    assert len(fit_calls) == 15
    assert evidence["terminal_row_count"] == 15
    assert evidence["completed_slot_count"] == 5
    assert evidence["resource_failure_count"] == 10
    assert evidence["completed_module_fit_count"] == 15
    assert evidence["new_e7_fit_count"] == 15
    assert evidence["primary_fit_reuse_count"] == 0
    assert "primary_slots_untouched" not in evidence
    assert len(evidence["sample_evidence"]) == 45
    assert sum(
        "status" not in record for record in evidence["sample_evidence"]
    ) == 25
    assert sum(
        record.get("status") == "resource_failure_recorded"
        for record in evidence["sample_evidence"]
    ) == 20
    assert evidence["saturation_claim_authorized"] is False
    completed = curve[curve["status"].eq("completed")]
    assert completed["downstream_metrics_status"].eq(
        "not_estimable_without_separate_temporal_consumers"
    ).all()
    assert completed["saturation_claim_authorized"].eq(False).all()
    for token in ("anfis_n", "anfis_f", "anfis_t_no_current"):
        assert completed[f"{token}_quality_gate_output_scope"].eq(
            "e7_stratified_training_sample_4096"
        ).all()
        assert completed[f"{token}_final_checkpoint_loss"].notna().all()
        assert completed[f"{token}_selected_keys_sha256"].str.len().eq(64).all()
        assert completed[f"{token}_computational_cost_proxy"].eq(
            4096 * 8 * 60
        ).all()
    assert "locked_hash_ranked_training_sample_4096" not in curve.to_csv(index=False)


def test_run_preflights_all_three_samples_before_any_fit_per_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, str, int, int]] = []

    def sample(
        _rows: pd.DataFrame, *, module: str, base_seed: int, training_size: int, **_: Any
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        events.append(("sample", module, base_seed, training_size))
        return _synthetic_sample(
            module=module,
            base_seed=base_seed,
            training_size=training_size,
        )

    def fit_slot(
        surface: pd.DataFrame,
        *,
        runtime: Mapping[str, Any],
        gate: Any,
        module: str,
        base_seed: int,
        prepared_sample: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]],
    ) -> Mapping[str, Any]:
        del surface, runtime, gate
        events.append(
            ("fit", module, base_seed, int(prepared_sample[2]["training_size"]))
        )
        return {
            "status": "passed",
            "final_checkpoint_loss": 0.1,
            "rule_count": 8,
            "epochs": 60,
            "quality_gate_output_standard_deviation": 0.2,
            "maximum_parameter_delta": 0.01,
            "centers_ordered": True,
            "centers_in_unit_interval": True,
        }

    monkeypatch.setattr(runner, "select_learning_curve_sample", sample)
    runner.run_learning_curve(
        _surface(30),
        runtime=_runtime(),
        gate=SimpleNamespace(development_keys={("wqp", "site-00")}),
        fit_slot=fit_slot,
    )
    for offset in range(0, 30, 6):
        assert [event[0] for event in events[offset : offset + 6]] == [
            "sample",
            "sample",
            "sample",
            "fit",
            "fit",
            "fit",
        ]
    for offset in range(30, 60, 3):
        assert [event[0] for event in events[offset : offset + 3]] == [
            "sample",
            "sample",
            "sample",
        ]


def test_run_records_resource_failures_without_fit_or_post_hoc_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_calls: list[tuple[str, int, int]] = []
    fit_calls: list[tuple[str, int, int]] = []

    def sample(
        _rows: pd.DataFrame, *, module: str, base_seed: int, training_size: int, **_: Any
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        sample_calls.append((module, base_seed, training_size))
        return _synthetic_sample(
            module=module,
            base_seed=base_seed,
            training_size=training_size,
        )

    def fit_slot(
        surface: pd.DataFrame,
        *,
        runtime: Mapping[str, Any],
        gate: Any,
        module: str,
        base_seed: int,
        prepared_sample: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]],
    ) -> Mapping[str, Any]:
        del surface, runtime, gate
        fit_calls.append(
            (module, base_seed, int(prepared_sample[2]["training_size"]))
        )
        return {
            "status": "passed",
            "final_checkpoint_loss": 0.1,
            "rule_count": 8,
            "epochs": 60,
            "quality_gate_output_standard_deviation": 0.2,
            "maximum_parameter_delta": 0.01,
            "centers_ordered": True,
            "centers_in_unit_interval": True,
        }

    monkeypatch.setattr(runner, "select_learning_curve_sample", sample)
    curve, evidence = runner.run_learning_curve(
        _surface(30),
        runtime=_runtime(),
        gate=SimpleNamespace(development_keys={("wqp", "site-00")}),
        fit_slot=fit_slot,
    )
    failed = curve[
        (curve["training_rows_per_module"] == 16384)
        & (curve["base_seed"] == 20260613)
    ].iloc[0]
    assert failed["status"] == "resource_failure_recorded"
    assert failed["completed_module_fit_count"] == 0
    assert len(sample_calls) == 45
    assert len(fit_calls) == 15
    assert not any(size > 4096 for _, _, size in fit_calls)
    assert len(curve) == 15
    assert evidence["completed_slot_count"] == 5
    assert evidence["resource_failure_count"] == 10
    assert evidence["completed_module_fit_count"] == 15
    assert evidence["new_e7_fit_count"] == 15
    assert evidence["primary_fit_reuse_count"] == 0
    assert evidence["saturation_claim_authorized"] is False
    assert evidence["post_hoc_substitution_performed"] is False


def test_run_does_not_relabel_programming_or_scientific_errors_as_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for exception in (
        ValueError("foreign bug"),
        calibration.FinalCalibrationError("scientific failure"),
    ):
        monkeypatch.setattr(
            runner,
            "select_learning_curve_sample",
            lambda *_args, _exception=exception, **_kwargs: (
                _ for _ in ()
            ).throw(_exception),
        )
        with pytest.raises(type(exception), match=str(exception)):
            runner.run_learning_curve(
                _surface(30),
                runtime=_runtime(),
                gate=SimpleNamespace(development_keys={("wqp", "site-00")}),
                fit_slot=lambda *_args, **_kwargs: {},
            )


def test_bundle_is_exact_two_canonical_outputs_and_manifest_last(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    curve = _terminal_curve()
    evidence = _terminal_evidence()
    authority = _e7_authority()
    input_records = _e7_required_inputs()
    payloads, manifest = runner.build_anfis_learning_curve_bundle(
        authority=authority,
        curve=curve,
        evidence=evidence,
        input_records=input_records,
        repo_root=tmp_path,
    )
    assert [path.relative_to(tmp_path).as_posix() for path, _ in payloads] == list(EXPECTED_OUTPUTS)
    assert payloads[-1][0] == tmp_path / EXPECTED_OUTPUTS[-1]
    assert json.loads(payloads[-1][1]) == manifest
    assert manifest["terminal_row_count"] == 15
    assert manifest["terminal_evidence"]["completed_slot_count"] == 5
    assert manifest["terminal_evidence"]["resource_failure_count"] == 10
    assert manifest["terminal_evidence"]["completed_module_fit_count"] == 15
    assert manifest["terminal_evidence"]["new_e7_fit_count"] == 15
    assert manifest["terminal_evidence"]["primary_fit_reuse_count"] == 0
    assert manifest["terminal_evidence"]["primary_slots_untouched"] is True
    assert manifest["terminal_evidence"]["saturation_claim_authorized"] is False
    assert sum(
        "status" not in record
        for record in manifest["terminal_evidence"]["sample_evidence"]
    ) == 25
    assert sum(
        record.get("status") == "resource_failure_recorded"
        for record in manifest["terminal_evidence"]["sample_evidence"]
    ) == 20

    # Parse the actual builder bytes through the strict public-loader parser,
    # then exercise canonical encoding, order, cardinality, evidence dialect,
    # and scientific row semantics independently.
    curve_payload = payloads[0][1]
    terminal_evidence = manifest["terminal_evidence"]
    calibration._validate_e7_csv_output(
        curve_payload,
        terminal_evidence=terminal_evidence,
    )
    reversed_curve = curve.iloc[::-1].reset_index(drop=True)
    short_curve = curve.iloc[:-1].reset_index(drop=True)
    invalid_curve = curve.copy()
    invalid_curve.loc[0, "anfis_n_final_checkpoint_loss"] = -1.0
    resource_drift = curve.copy()
    resource_drift.loc[5, "resource_limitation"] = "different but nonempty"
    float_identity = curve.copy()
    float_identity["base_seed"] = float_identity["base_seed"].astype(object)
    float_identity.loc[0, "base_seed"] = 1729.0
    boolean_identity = curve.copy()
    boolean_identity["training_rows_per_module"] = boolean_identity[
        "training_rows_per_module"
    ].astype(object)
    boolean_identity.loc[0, "training_rows_per_module"] = True
    for payload_drift in (
        curve_payload.replace(b"\n", b"\r\n"),
        runner._csv_bytes(reversed_curve),
        runner._csv_bytes(short_curve),
        runner._csv_bytes(invalid_curve),
        runner._csv_bytes(resource_drift),
        runner._csv_bytes(float_identity),
        runner._csv_bytes(boolean_identity),
    ):
        with pytest.raises(calibration.FinalCalibrationError):
            calibration._validate_e7_csv_output(
                payload_drift,
                terminal_evidence=terminal_evidence,
            )
    evidence_drifts = []
    reversed_preflights = json.loads(json.dumps(terminal_evidence))
    reversed_preflights["sample_evidence"] = list(
        reversed(reversed_preflights["sample_evidence"])
    )
    evidence_drifts.append(reversed_preflights)
    missing_preflight = json.loads(json.dumps(terminal_evidence))
    missing_preflight["sample_evidence"].pop()
    evidence_drifts.append(missing_preflight)
    malformed_preflight = json.loads(json.dumps(terminal_evidence))
    malformed_preflight["sample_evidence"][0]["selected_row_count"] = 4095
    evidence_drifts.append(malformed_preflight)
    extra_terminal_key = {**terminal_evidence, "caller_claim": False}
    evidence_drifts.append(extra_terminal_key)
    for evidence_drift in evidence_drifts:
        with pytest.raises(calibration.FinalCalibrationError):
            calibration._validate_e7_csv_output(
                curve_payload,
                terminal_evidence=evidence_drift,
            )

    monkeypatch.setattr(
        calibration,
        "_scientific_input_inventory",
        lambda **_: {
            "calibration_required_inputs": [],
            "e7_required_inputs": input_records,
        },
    )
    monkeypatch.setattr(
        calibration,
        "_effective_authority_binding_sha256",
        lambda **_: "a" * 64,
    )
    for path, payload in payloads:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        path.chmod(0o644)
    assert calibration._require_exact_output_group(
        calibration.E7_OUTPUT_PATHS,
        manifest_path=calibration.ANFIS_LEARNING_CURVE_MANIFEST_PATH,
        repo_root=tmp_path,
        context="E7",
    ) == 2

    # Rehashing both the altered CSV and its manifest does not turn a
    # semantically impossible loss into valid authority.
    forged_curve = runner._csv_bytes(resource_drift)
    forged_manifest = json.loads(json.dumps(manifest))
    forged_manifest["outputs"][0]["bytes"] = len(forged_curve)
    forged_manifest["outputs"][0]["sha256"] = hashlib.sha256(
        forged_curve
    ).hexdigest()
    payloads[0][0].write_bytes(forged_curve)
    payloads[1][0].write_bytes(runner._canonical_json_bytes(forged_manifest))
    with pytest.raises(calibration.FinalCalibrationError):
        calibration._require_exact_output_group(
            calibration.E7_OUTPUT_PATHS,
            manifest_path=calibration.ANFIS_LEARNING_CURVE_MANIFEST_PATH,
            repo_root=tmp_path,
            context="E7",
        )


def test_incomplete_bundle_retains_all_rows_and_forbids_saturation_claim() -> None:
    curve = _terminal_curve()
    evidence = _terminal_evidence()
    authority = _e7_authority()
    input_records = _e7_required_inputs()
    payloads, manifest = runner.build_anfis_learning_curve_bundle(
        authority=authority,
        curve=curve,
        evidence=evidence,
        input_records=input_records,
    )
    assert manifest["terminal_row_count"] == 15
    assert manifest["terminal_evidence"]["completed_slot_count"] == 5
    assert manifest["terminal_evidence"]["resource_failure_count"] == 10
    assert manifest["terminal_evidence"]["saturation_claim_authorized"] is False
    csv_text = payloads[0][1].decode("utf-8")
    assert "resource_failure_recorded" in csv_text
    assert "E7 candidate universe has 4757 rows; 16384 are required" in csv_text
    for key, value in (
        ("terminal_row_count", 14),
        ("completed_slot_count", 6),
        ("resource_failure_count", 9),
        ("completed_module_fit_count", 14),
        ("new_e7_fit_count", 14),
        ("primary_fit_reuse_count", 1),
        ("primary_slots_untouched", False),
        ("silent_omission", True),
        ("post_hoc_substitution_performed", True),
        ("saturation_claim_authorized", True),
    ):
        drift = {**evidence, key: value}
        with pytest.raises(calibration.FinalCalibrationError):
            runner.build_anfis_learning_curve_bundle(
                authority=authority,
                curve=curve,
                evidence=drift,
                input_records=input_records,
            )
    legacy_only = {
        key: value
        for key, value in evidence.items()
        if key
        not in {
            "terminal_row_count",
            "completed_slot_count",
            "resource_failure_count",
            "post_hoc_substitution_performed",
        }
    }
    legacy_only.update(
        {
            "terminal_record_count": 15,
            "completed_record_count": 5,
            "resource_failure_record_count": 10,
            "post_hoc_substitution": False,
        }
    )
    with pytest.raises(calibration.FinalCalibrationError):
        runner.build_anfis_learning_curve_bundle(
            authority=authority,
            curve=curve,
            evidence=legacy_only,
            input_records=input_records,
        )
    for column, value in (
        ("anfis_n_quality_gate_output_scope", "locked_hash_ranked_training_sample_4096"),
        ("anfis_n_final_checkpoint_loss", float("nan")),
        ("anfis_n_computational_cost_proxy", None),
        ("downstream_metrics_status", "estimated"),
        ("saturation_claim_authorized", True),
    ):
        curve_drift = curve.copy()
        curve_drift.loc[0, column] = value
        with pytest.raises(calibration.FinalCalibrationError):
            runner.build_anfis_learning_curve_bundle(
                authority=authority,
                curve=curve_drift,
                evidence=evidence,
                input_records=input_records,
            )
    with pytest.raises(calibration.FinalCalibrationError):
        runner.build_anfis_learning_curve_bundle(
            authority=authority,
            curve=_terminal_curve(failed=set()),
            evidence={
                **evidence,
                "completed_slot_count": 15,
                "resource_failure_count": 0,
                "completed_module_fit_count": 45,
                "new_e7_fit_count": 45,
            },
            input_records=input_records,
        )


def test_execute_one_shot_gates_before_build_and_publishes_manifest_last(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []
    authority = _e7_authority()
    authority_box: dict[str, Any] = {"value": authority}
    output_paths = tuple(tmp_path / path for path in EXPECTED_OUTPUTS)
    guard_path = tmp_path / runner.GUARD_PATH.relative_to(runner.PROJECT_ROOT)
    calibration_payloads = {
        tmp_path / path: (path.as_posix() + "\n").encode()
        for path in calibration.CALIBRATION_OUTPUT_PATHS
    }

    def require(**_: Any) -> Mapping[str, Any]:
        events.append("gate")
        value = authority_box["value"]
        if isinstance(value, BaseException):
            raise value
        return value

    monkeypatch.setattr(
        calibration, "require_final_calibration_authority", require
    )
    authority_box["value"] = calibration.FinalCalibrationError("gate closed")
    with pytest.raises(calibration.FinalCalibrationError, match="gate closed"):
        runner.execute_one_shot(repo_root=tmp_path)
    assert events == ["gate"]
    assert list(tmp_path.iterdir()) == []

    def namespace(*, runner: str, repo_root: Path) -> dict[str, Any]:
        assert runner == "e7" and repo_root == tmp_path
        events.append("namespace")
        if any(
            not path.is_file() or path.read_bytes() != expected
            for path, expected in calibration_payloads.items()
        ):
            raise calibration.FinalCalibrationError(
                "calibration prerequisite is absent or noncanonical"
            )
        occupied = [
            path
            for path in (*output_paths, guard_path)
            if os.path.lexists(path)
        ]
        if occupied:
            raise calibration.FinalCalibrationError("E7 one-shot namespace occupied")
        return {
            "runner": "e7",
            "calibration_bundle_complete": True,
            "e7_bundle_absent": True,
        }

    monkeypatch.setattr(
        calibration,
        "require_final_calibration_run_namespace",
        namespace,
        raising=False,
    )
    authority_box["value"] = authority
    events.clear()
    with pytest.raises(calibration.FinalCalibrationError, match="calibration prerequisite"):
        runner.execute_one_shot(repo_root=tmp_path)
    assert events == ["gate", "namespace"]
    assert list(tmp_path.iterdir()) == []

    for path, payload in calibration_payloads.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    _materialize_e7_inputs(tmp_path)

    # The E7 snapshot uses the P-derived DVC pointer set and the same strict
    # topology classes as calibration inputs.  One real 0444/nlink=2 cache
    # materialization is accepted; extra/wrong/writable/missing aliases fail
    # both initial capture and later revalidation.
    first_input = _e7_required_inputs()[0]
    first_payload = _e7_input_payload(0)
    first_path = tmp_path / first_input["path"]
    first_md5 = hashlib.md5(first_payload, usedforsecurity=False).hexdigest()
    first_cache = (
        tmp_path / ".dvc/cache/files/md5" / first_md5[:2] / first_md5[2:]
    )
    _, topology_snapshot = runner._snapshot_e7_required_inputs(
        authority,
        repo_root=tmp_path,
    )
    assert topology_snapshot[0]["mode"] == "0444"
    assert topology_snapshot[0]["nlink"] == 2
    runner._revalidate_e7_required_input_snapshot(
        authority,
        topology_snapshot,
        repo_root=tmp_path,
    )
    third_name = tmp_path / "inputs/e7/payloads/foreign-third-name.bin"
    os.link(first_path, third_name)
    with pytest.raises(calibration.FinalCalibrationError):
        runner._snapshot_e7_required_inputs(authority, repo_root=tmp_path)
    with pytest.raises(calibration.FinalCalibrationError):
        runner._revalidate_e7_required_input_snapshot(
            authority,
            topology_snapshot,
            repo_root=tmp_path,
        )
    third_name.unlink()
    first_path.chmod(0o644)
    with pytest.raises(calibration.FinalCalibrationError):
        runner._snapshot_e7_required_inputs(authority, repo_root=tmp_path)
    first_path.chmod(0o444)
    first_cache.unlink()
    with pytest.raises(calibration.FinalCalibrationError):
        runner._snapshot_e7_required_inputs(authority, repo_root=tmp_path)
    os.link(first_path, first_cache)
    wrong_cache = first_cache.with_name(first_cache.name + ".wrong")
    first_cache.rename(wrong_cache)
    first_cache.write_bytes(first_payload)
    first_cache.chmod(0o444)
    with pytest.raises(calibration.FinalCalibrationError):
        runner._snapshot_e7_required_inputs(authority, repo_root=tmp_path)
    first_cache.unlink()
    wrong_cache.rename(first_cache)
    _, topology_snapshot = runner._snapshot_e7_required_inputs(
        authority,
        repo_root=tmp_path,
    )

    family_before = [
        {
            "role": "primary_anfis_family_final",
            "path": f"family/final_{index:02d}",
            "bytes": 100 + index,
            "sha256": f"{index:064x}",
            "mode": "0644",
            "nlink": 1,
            "device": 1,
            "inode": 1000 + index,
            "mtime_ns": 1,
            "ctime_ns": 1,
        }
        for index in range(80)
    ]
    family_box = {"current": [dict(record) for record in family_before]}

    def snapshot(*, repo_root: Path) -> list[dict[str, Any]]:
        assert repo_root == tmp_path
        events.append("family_snapshot")
        return [dict(record) for record in family_box["current"]]

    def revalidate(snapshot: Any, *, repo_root: Path) -> None:
        assert repo_root == tmp_path
        events.append("family_revalidate")
        if snapshot != family_box["current"]:
            raise calibration.FinalCalibrationError("primary family changed")

    gate = SimpleNamespace(development_keys={("wqp", "site-00")})
    runtime = {
        "e0_mcal_e7_terminal_record": _runtime()["e7_terminal_record"]
    }
    monkeypatch.setattr(
        runner,
        "_snapshot_primary_anfis_family",
        snapshot,
    )
    monkeypatch.setattr(
        runner,
        "_revalidate_primary_anfis_family_snapshot",
        revalidate,
    )

    aba_phase = {"enabled": False}

    def load(*, pinned_inputs: Any, repo_root: Path) -> dict[str, Any]:
        assert repo_root == tmp_path
        assert isinstance(pinned_inputs, runner._PinnedE7Inputs)
        assert len(pinned_inputs.records) == len(pinned_inputs.snapshot) == 15
        events.append("load")
        if aba_phase["enabled"]:
            relative = cast(str, _e7_required_inputs()[1]["path"])
            nominal = tmp_path / relative
            retained = nominal.with_name(nominal.name + ".retained")
            original_payload = _e7_input_payload(1)
            foreign_payload = b"X" * (len(original_payload) - 1) + b"\n"
            assert foreign_payload != original_payload
            nominal.rename(retained)
            nominal.write_bytes(foreign_payload)
            nominal.chmod(0o644)
            try:
                assert nominal.read_bytes() == foreign_payload
                assert pinned_inputs.payload(relative) == original_payload
                pinned_inputs.revalidate()
                pytest.fail("E7 ABA replacement passed pinned revalidation")
            finally:
                nominal.unlink()
                retained.rename(nominal)
        return {
            "surface": _surface(30),
            "runtime": runtime,
            "gate": gate,
            "input_records": [],
        }

    monkeypatch.setattr(runner, "_load_learning_curve_surface", load)
    policy_box: dict[str, Any] = {"value": _execution_policy()}

    def cpu_policy(_runtime: Mapping[str, Any]) -> dict[str, Any]:
        events.append("cpu")
        value = policy_box["value"]
        if isinstance(value, BaseException):
            raise value
        return value

    monkeypatch.setattr(runner, "_configure_e7_cpu_policy", cpu_policy)

    def sample(
        _surface: pd.DataFrame,
        *,
        module: str,
        base_seed: int,
        training_size: int,
        **_: Any,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        return _synthetic_sample(
            module=module,
            base_seed=base_seed,
            training_size=training_size,
        )

    fit_calls: list[tuple[str, int]] = []
    mutation_phase = {"value": "none", "done": False}

    def fit_slot(
        _surface: pd.DataFrame,
        *,
        runtime: Mapping[str, Any],
        gate: Any,
        module: str,
        base_seed: int,
        prepared_sample: Any,
    ) -> Mapping[str, Any]:
        del runtime, gate, prepared_sample
        events.append("fit")
        fit_calls.append((module, base_seed))
        if mutation_phase["value"] == "fit" and not mutation_phase["done"]:
            mutation_phase["done"] = True
            family_box["current"][0]["sha256"] = "f" * 64
        return {
            "status": "passed",
            "final_checkpoint_loss": 0.1,
            "rule_count": 8,
            "epochs": 60,
            "quality_gate_output_standard_deviation": 0.2,
            "maximum_parameter_delta": 0.01,
            "centers_ordered": True,
            "centers_in_unit_interval": True,
        }

    monkeypatch.setattr(runner, "select_learning_curve_sample", sample)
    monkeypatch.setattr(runner, "_default_fit_slot", fit_slot)

    owned_failure_phase: dict[str, str | None] = {"value": None}
    owned_calls: list[
        tuple[str, Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]
    ] = []

    def revalidate_owned_publication(
        captured: Mapping[str, Any],
        *,
        runner: str,
        phase: str,
        owned_guard: Mapping[str, Any] | None,
        owned_outputs: Any,
        verify_remote: bool,
        repo_root: Path,
    ) -> dict[str, Any]:
        assert captured is authority
        assert runner == "e7"
        assert phase in {"active_guard", "post_release"}
        assert verify_remote is True and repo_root == tmp_path
        outputs = tuple(owned_outputs)
        assert len(outputs) == 2
        assert tuple(record["path"] for record in outputs) == EXPECTED_OUTPUTS
        if phase == "active_guard":
            assert owned_guard is not None
            assert owned_guard["path"] == runner_guard_path
            capabilities = (owned_guard, *outputs)
        else:
            assert owned_guard is None
            assert not (tmp_path / runner_guard_path).exists()
            capabilities = outputs
        for capability in capabilities:
            assert set(capability) == EXPECTED_OWNED_CAPABILITY_KEYS
            assert type(capability).__name__ == "mappingproxy"
            path = tmp_path / cast(str, capability["path"])
            observed = path.stat()
            assert capability["device"] == observed.st_dev
            assert capability["inode"] == observed.st_ino
            assert capability["mode"] == stat.S_IMODE(observed.st_mode)
            assert capability["nlink"] == observed.st_nlink == 1
            assert capability["size"] == observed.st_size
            assert capability["mtime_ns"] == observed.st_mtime_ns
            assert capability["ctime_ns"] == observed.st_ctime_ns
            assert capability["sha256"] == hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        events.append(f"owned:{phase}")
        owned_calls.append((phase, owned_guard, outputs))
        if owned_failure_phase["value"] == phase:
            raise calibration.FinalCalibrationError(
                f"owned publication rejected at {phase}"
            )
        return {"gate": calibration.PATCH_GATE, "phase": phase, "status": "valid"}

    runner_guard_path = runner.GUARD_PATH.relative_to(
        runner.PROJECT_ROOT
    ).as_posix()
    monkeypatch.setattr(
        calibration,
        "revalidate_final_calibration_owned_run_publication",
        revalidate_owned_publication,
        raising=False,
    )

    for occupied in ((output_paths[0],), output_paths, (guard_path,)):
        for path in occupied:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"foreign\n")
        events.clear()
        before_fit_count = len(fit_calls)
        with pytest.raises(calibration.FinalCalibrationError, match="namespace occupied"):
            runner.execute_one_shot(repo_root=tmp_path)
        assert events == ["gate", "namespace"]
        assert len(fit_calls) == before_fit_count
        for path in occupied:
            assert path.read_bytes() == b"foreign\n"
            path.unlink()
            assert path.parent.is_dir()

    # The namespace probes above deliberately created foreign parents.  A
    # transaction must preserve those parents, so reset only the exact empty
    # fixture directories before testing rollback of transaction-owned dirs.
    for parent in (output_paths[0].parent, guard_path.parent):
        assert parent.is_dir() and not any(parent.iterdir())
        parent.rmdir()
        assert not parent.exists()

    policy_box["value"] = calibration.FinalCalibrationError("CPU policy drift")
    events.clear()
    with pytest.raises(calibration.FinalCalibrationError, match="CPU policy drift"):
        runner.execute_one_shot(repo_root=tmp_path)
    assert events == ["gate", "namespace", "family_snapshot", "load", "cpu"]
    assert fit_calls == []

    policy_box["value"] = _execution_policy()
    aba_phase["enabled"] = True
    events.clear()
    before_aba_fit_count = len(fit_calls)
    with pytest.raises(calibration.FinalCalibrationError):
        runner.execute_one_shot(repo_root=tmp_path)
    assert len(fit_calls) == before_aba_fit_count
    assert all(not path.exists() for path in output_paths)
    aba_phase["enabled"] = False

    mutation_phase.update(value="fit", done=False)
    events.clear()
    with pytest.raises(calibration.FinalCalibrationError, match="primary family changed"):
        runner.execute_one_shot(repo_root=tmp_path)
    assert len(fit_calls) == 15
    assert all(not path.exists() for path in output_paths)

    family_box["current"] = [dict(record) for record in family_before]
    mutation_phase.update(value="publish", done=False)
    transaction_type = runner.calibration_runner.OrderedBundleTransaction
    real_publish = transaction_type.publish

    def publish_with_family_mutation(
        transaction: Any, path: Path, payload: bytes
    ) -> dict[str, Any]:
        record = real_publish(transaction, path, payload)
        if not mutation_phase["done"]:
            mutation_phase["done"] = True
            family_box["current"][0]["sha256"] = "e" * 64
        return record

    monkeypatch.setattr(transaction_type, "publish", publish_with_family_mutation)
    events.clear()
    with pytest.raises(calibration.FinalCalibrationError, match="primary family changed"):
        runner.execute_one_shot(repo_root=tmp_path)
    assert all(not path.exists() for path in output_paths)
    assert not guard_path.exists()
    assert not output_paths[0].parent.exists()
    assert not guard_path.parent.exists()

    family_box["current"] = [dict(record) for record in family_before]
    mutation_phase.update(value="none", done=False)
    monkeypatch.setattr(transaction_type, "publish", real_publish)
    for rejected_phase in ("active_guard", "post_release"):
        owned_failure_phase["value"] = rejected_phase
        events.clear()
        with pytest.raises(
            calibration.FinalCalibrationError,
            match=f"owned publication rejected at {rejected_phase}",
        ):
            runner.execute_one_shot(repo_root=tmp_path)
        assert all(not path.exists() for path in output_paths)
        assert not guard_path.exists()

    owned_failure_phase["value"] = None
    events.clear()
    stable_fit_start = len(fit_calls)
    result = runner.execute_one_shot(repo_root=tmp_path)
    assert len(fit_calls) - stable_fit_start == 15
    assert events.index("cpu") < events.index("fit")
    assert events.count("family_revalidate") >= 3
    assert [phase for phase, _, _ in owned_calls[-2:]] == [
        "active_guard",
        "post_release",
    ]
    assert result["status"] == "completed_unpublished"
    assert result["terminal_row_count"] == 15
    assert result["new_e7_fit_count"] == 15
    assert result["primary_fit_reuse_count"] == 0
    assert result["primary_slots_untouched"] is True
    assert [record["path"] for record in result["records"]] == list(
        EXPECTED_OUTPUTS
    )
    assert json.loads(output_paths[-1].read_bytes()) == result["manifest"]
    assert result["manifest"]["terminal_evidence"][
        "primary_slots_untouched"
    ] is True
    assert family_box["current"] == family_before
    assert all(
        path.read_bytes() == payload for path, payload in calibration_payloads.items()
    )

    before_rerun_fit_count = len(fit_calls)
    events.clear()
    with pytest.raises(calibration.FinalCalibrationError, match="namespace occupied"):
        runner.execute_one_shot(repo_root=tmp_path)
    assert events == ["gate", "namespace"]
    assert len(fit_calls) == before_rerun_fit_count
