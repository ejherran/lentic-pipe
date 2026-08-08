from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from src.experiments import audit_closure_anfis_ablation_model_bundle as auditor
from src.experiments import closure_anfis_ablation_model_manifest_patch as authority_patch
from src.experiments import train_closure_anfis_ablation as trainer


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _record(path: Path, *, repo_root: Path, role: str) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "role": role,
        "path": path.relative_to(repo_root).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _authority(
    *, model_id: str = "A0", base_seed: int = 1729, prefix_count: int = 10
) -> dict[str, Any]:
    slot_index = auditor.BUNDLE_SLOTS.index((model_id, base_seed))
    authority: dict[str, Any] = {
        "gate": "E0-MV",
        "status": "effective_preflight_passed",
        "authorized_model_id": model_id,
        "authorized_base_seed": base_seed,
        "completed_prefix_count": prefix_count,
        "slot_creation_prefix_count": slot_index,
        "h_patch_head": "1" * 40,
        "p_patch_head": "2" * 40,
        "h_components_sha256": "3" * 64,
        "physical_inputs_sha256": "4" * 64,
        "runtime_sha256": "5" * 64,
        "lock_sha256": "6" * 64,
        "companion_sha256": "7" * 64,
        "model_bundle_audit_authorized": True,
        "target_access_through_2020_authorized": True,
        "selection_diagnostics_authorized": True,
        "a0_development_fit_authorized": False,
        "a1_development_fit_authorized": False,
        "batch_slot_execution_authorized": False,
        "calibration_authorized": False,
        "calibration_target_access_authorized": False,
        "final_e7_metrics_authorized": False,
        "rollout_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "scientific_network_authorized": False,
        "outcome_access_authorized": False,
        "future_outcomes_accessed": False,
    }
    authority["slot_manifest_authority"] = {
        key: authority[key] for key in auditor.AUTHORITY_BINDING_KEYS
    }
    authority["slot_manifest_authority"]["completed_prefix_count"] = slot_index
    authority["slot_source_record"] = {
        "role": "trainer",
        "path": "src/experiments/train_closure_anfis_ablation.py",
        "bytes": 1,
        "sha256": "a" * 64,
    }
    return authority


def _runtime() -> dict[str, Any]:
    target_record = {
        "role": "development_targets",
        "path": "data/targets/monthly_targets_model_v0.parquet",
        "bytes": 999,
        "sha256": "8" * 64,
    }
    target_manifest_record = {
        "role": "target_manifest",
        "path": "data/targets/target_manifest_v0.json",
        "bytes": 111,
        "sha256": "9" * 64,
    }
    return {
        "schema_version": "closure_anfis_ablation_training_development_runtime_v1",
        "experiment_id": "closure_v1",
        "surface_id": trainer.SURFACE_ID,
        "status": "ready_to_lock",
        "gate": "E0-MT",
        "authority": {"physical_inputs": [target_record, target_manifest_record]},
        "roles": {
            "model_selection_end": "2020-12",
        },
        "targets": {
            "join_columns": list(trainer.TARGET_JOIN_COLUMNS),
            "exact_projection": list(trainer.TARGET_PROJECTION),
            "horizons_months": list(trainer.HORIZONS),
            "training": {"origins": 2, "rows": 6},
            "model_selection": {"origins": 2, "rows": 6},
            "calibration_threshold_closed": {"origins": 1, "rows": 3},
        },
        "inputs": {
            "history_length_months": trainer.HISTORY_LENGTH,
            "A0": {"input_dimension": len(trainer.A0_INPUT_COLUMNS)},
            "A1": {"input_dimension": len(trainer.A1_INPUT_COLUMNS)},
        },
        "preprocessing": {
            "fit_role": "training",
            "raw_values": "mask_aware_training_standard_scaler_ddof0",
            "fit_outside_training": "forbidden",
        },
        "model": {
            "family": "direct_multitask_probabilistic_gru",
            "common_architecture": {
                "hidden_dimension": 96,
                "recurrent_layers": 1,
                "add_last": False,
            },
            "loss": {"bloom": "binary_cross_entropy_with_logits"},
            "selection": {"role": "model_selection", "calibration_applied": False},
            "optimization": {"batch_size": 2048, "maximum_epochs": 20},
            "execution": {"device": "cpu", "threadpool_limit": 1},
        },
        "slots": {"pairing_policy": "same_model_seed_pair_A0_then_A1"},
    }


def _prediction_frame(model_id: str, base_seed: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for origin_index in range(2):
        for horizon in trainer.HORIZONS:
            positive = int(origin_index == 1)
            rows.append(
                {
                    "surface_id": trainer.SURFACE_ID,
                    "model_id": model_id,
                    "base_seed": base_seed,
                    "source_id": "wqp",
                    "site_id": f"site-{origin_index}",
                    "common_origin_id": f"origin-{origin_index}",
                    "time_role": "model_selection",
                    "origin_year_month": "2020-08",
                    "target_year_month": f"2020-{8 + horizon:02d}",
                    "horizon_months": horizon,
                    "observed_bloom": positive,
                    "observed_risk": float(positive),
                    "predicted_bloom_probability": trainer.EXPECTED_TRAINING_BLOOM_PRIORS[
                        horizon - 1
                    ],
                    "predicted_risk": trainer.EXPECTED_TRAINING_RISK_PRIORS[
                        horizon - 1
                    ],
                    "predicted_risk_sigma": 1.0,
                    "availability_status": "success",
                    "failure_reason": "",
                    "score_semantics": "direct_bloom_probability_and_risk_distribution",
                }
            )
    return pd.DataFrame(rows, columns=trainer.PREDICTION_COLUMNS)


def _write_runtime(repo_root: Path, runtime: dict[str, Any]) -> None:
    payload = yaml.safe_dump(runtime, sort_keys=False).encode("utf-8")
    _write(repo_root / auditor.DEFAULT_RUNTIME, payload)


def _prepare_bundle(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    model_id: str = "A0",
    base_seed: int = 1729,
) -> tuple[trainer.SlotPaths, dict[str, Any], dict[str, Any]]:
    monkeypatch.setattr(trainer, "EXPECTED_TRAINING_ORIGINS", 2)
    monkeypatch.setattr(trainer, "EXPECTED_TRAINING_TARGET_ROWS", 6)
    monkeypatch.setattr(trainer, "EXPECTED_SELECTION_ORIGINS", 2)
    monkeypatch.setattr(trainer, "EXPECTED_SELECTION_TARGET_ROWS", 6)
    monkeypatch.setattr(trainer, "EXPECTED_SELECTION_BLOOM_POSITIVES", (1, 1, 1))
    monkeypatch.setattr(trainer, "EXPECTED_SELECTION_RISK_MEANS", (0.5, 0.5, 0.5))
    runtime = _runtime()
    target_path = repo_root / trainer.TARGET_ARTIFACT
    target_manifest_path = repo_root / trainer.TARGET_MANIFEST
    target_rows = [
        {
            "source_id": "wqp",
            "site_id": f"site-{origin_index}",
            "origin_year_month": "2020-08",
            "target_year_month": f"2020-{8 + horizon:02d}",
            "horizon_months": horizon,
            "bloom_h": int(origin_index == 1),
            "target_risk_chla_h": float(origin_index == 1),
        }
        for origin_index in range(2)
        for horizon in trainer.HORIZONS
    ]
    target_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pandas(pd.DataFrame(target_rows), preserve_index=False),
        target_path,
    )
    _write(target_manifest_path, b'{"fixture":"target_manifest"}\n')
    runtime["authority"]["physical_inputs"] = [
        _record(
            target_path,
            repo_root=repo_root,
            role="development_targets",
        ),
        _record(
            target_manifest_path,
            repo_root=repo_root,
            role="target_manifest",
        ),
    ]
    _write_runtime(repo_root, runtime)
    authority = _authority(model_id=model_id, base_seed=base_seed)
    authority_records: list[dict[str, Any]] = []
    for key, role, relative in trainer.AUTHORITY_RECORD_SPECS:
        path = repo_root / relative
        if key != "runtime":
            _write(path, (json.dumps({"fixture": key}) + "\n").encode("utf-8"))
        record = _record(path, repo_root=repo_root, role=role)
        authority[key] = record
        authority[f"{key}_sha256"] = record["sha256"]
        authority["slot_manifest_authority"][f"{key}_sha256"] = record[
            "sha256"
        ]
        authority_records.append(record)
    monkeypatch.setattr(
        auditor,
        "_require_audit_authority",
        lambda *args, **kwargs: authority,
    )

    sequence, sequence_pointer, sequence_summary, sequence_manifest = (
        trainer.sequence_paths(model_id, base_seed, repo_root=repo_root)
    )
    common = repo_root / "data/closure_v1/common_origin_manifest.parquet"
    common_pointer = repo_root / "data/closure_v1/common_origin_manifest.parquet.dvc"
    common_manifest = (
        repo_root / "reports/closure_v1/01_surface/common_origin_manifest.json"
    )
    targets_pointer = repo_root / "data/targets.dvc"
    for path in (
        sequence,
        sequence_pointer,
        sequence_summary,
        sequence_manifest,
        common,
        common_pointer,
        common_manifest,
        targets_pointer,
    ):
        _write(path, f"synthetic {path.name}\n".encode("utf-8"))
    common_rows = [
        {
            "source_id": "wqp",
            "site_id": f"training-site-{origin_index}",
            "common_origin_id": f"training-origin-{origin_index}",
            "assignment_role": "development",
            "time_role": "training",
            "origin_year_month": "2018-08",
            "target_year_month": f"2018-{8 + horizon:02d}",
            "horizon_months": horizon,
            "complete_targets_evaluable": True,
        }
        for origin_index in range(2)
        for horizon in trainer.HORIZONS
    ]
    common_rows.extend(
        {
            "source_id": "wqp",
            "site_id": f"site-{origin_index}",
            "common_origin_id": f"origin-{origin_index}",
            "assignment_role": "development",
            "time_role": "model_selection",
            "origin_year_month": "2020-08",
            "target_year_month": f"2020-{8 + horizon:02d}",
            "horizon_months": horizon,
            "complete_targets_evaluable": True,
        }
        for origin_index in range(2)
        for horizon in trainer.HORIZONS
    )
    pq.write_table(
        pa.Table.from_pandas(pd.DataFrame(common_rows), preserve_index=False), common
    )
    source = repo_root / "src/experiments/train_closure_anfis_ablation.py"
    _write(source, b"# synthetic trainer source\n")
    target_records = {
        str(record["role"]): copy.deepcopy(record)
        for record in runtime["authority"]["physical_inputs"]
    }
    prefix = model_id.lower()
    inputs = [
        _record(sequence, repo_root=repo_root, role=f"{prefix}_sequence"),
        _record(
            sequence_pointer,
            repo_root=repo_root,
            role=f"{prefix}_sequence_pointer",
        ),
        _record(
            sequence_summary,
            repo_root=repo_root,
            role=f"{prefix}_sequence_summary",
        ),
        _record(
            sequence_manifest,
            repo_root=repo_root,
            role=f"{prefix}_sequence_manifest",
        ),
        _record(common, repo_root=repo_root, role="common_origin"),
        _record(
            common_pointer, repo_root=repo_root, role="common_origin_pointer"
        ),
        _record(
            common_manifest, repo_root=repo_root, role="common_origin_manifest"
        ),
        target_records["development_targets"],
        _record(targets_pointer, repo_root=repo_root, role="targets_pointer"),
        target_records["target_manifest"],
    ]
    source_code = [_record(source, repo_root=repo_root, role="trainer")]
    authority["slot_source_record"] = copy.deepcopy(source_code[0])

    sequence_rows: list[dict[str, Any]] = []
    for origin_index in range(2):
        row: dict[str, Any] = {
            "source_id": "wqp",
            "site_id": f"site-{origin_index}",
            "common_origin_id": f"origin-{origin_index}",
            "time_role": "model_selection",
            "origin_year_month": "2020-08",
        }
        for column in trainer.input_columns(model_id):
            if column in trainer.EXPECTED_RAW_STANDARDIZATION:
                value = trainer.EXPECTED_RAW_STANDARDIZATION[column][1]
            elif column in trainer.RAW_MASK_COLUMNS:
                value = 1.0
            else:
                value = 0.0
            row[column] = [value] * trainer.HISTORY_LENGTH
        sequence_rows.append(row)
    sequence_frame = pd.DataFrame(sequence_rows)
    monkeypatch.setattr(
        trainer,
        "_sequence_frame",
        lambda **kwargs: (sequence_frame.copy(deep=True), [], []),
    )

    paths = trainer.slot_paths(model_id, base_seed, repo_root=repo_root)
    preprocessor = {
        "version": "closure_mask_aware_training_standardization_v1",
        "fit_role": "training",
        "calculation_dtype": "float64",
        "serialization_dtype": "float32",
        "variance_ddof": 0,
        "epsilon": trainer.PREPROCESSOR_EPSILON,
        "missing_transport_after_transform": 0.0,
        "columns": [
            {
                "column": column,
                "observed_count": values[0],
                "mean": values[1],
                "standard_deviation": values[2],
            }
            for column, values in trainer.EXPECTED_RAW_STANDARDIZATION.items()
        ],
        "model_id": model_id,
        "base_seed": base_seed,
        "input_columns": list(trainer.input_columns(model_id)),
        "identity_channels": list(
            trainer.input_columns(model_id)[trainer.RAW_DIMENSION :]
        ),
        "bloom_training_priors": list(trainer.EXPECTED_TRAINING_BLOOM_PRIORS),
        "risk_training_priors": list(trainer.EXPECTED_TRAINING_RISK_PRIORS),
        "calibration_used": False,
    }
    _write(
        paths.preprocessor,
        auditor._canonical_json(preprocessor),
    )
    torch = pytest.importorskip("torch")
    model = trainer.make_anfis_ablation_model(
        input_dimension=len(trainer.input_columns(model_id)),
        bloom_priors=np.asarray(trainer.EXPECTED_TRAINING_BLOOM_PRIORS),
        risk_priors=np.asarray(trainer.EXPECTED_TRAINING_RISK_PRIORS),
    )
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
    state_dict = {
        name: value.detach().cpu().clone()
        for name, value in model.state_dict().items()
    }
    prediction = _prediction_frame(model_id, base_seed)
    with torch.no_grad():
        bloom_logits, risk_mu, risk_logvar = model(
            torch.zeros(
                (1, trainer.HISTORY_LENGTH, len(trainer.input_columns(model_id))),
                dtype=torch.float32,
            )
        )
        bloom_values = torch.sigmoid(bloom_logits)[0].cpu().numpy().astype(np.float64)
        risk_values = risk_mu[0].cpu().numpy().astype(np.float64)
        sigma_values = np.exp(0.5 * risk_logvar[0].cpu().numpy().astype(np.float64))
    for index, horizon in enumerate(trainer.HORIZONS):
        selected_horizon = prediction["horizon_months"].eq(horizon)
        prediction.loc[selected_horizon, "predicted_bloom_probability"] = bloom_values[index]
        prediction.loc[selected_horizon, "predicted_risk"] = risk_values[index]
        prediction.loc[selected_horizon, "predicted_risk_sigma"] = sigma_values[index]
    paths.selection_predictions.parent.mkdir(parents=True, exist_ok=True)
    trainer.prediction_arrow_table(prediction).to_pandas()
    pq.write_table(
        trainer.prediction_arrow_table(prediction),
        paths.selection_predictions,
        compression="zstd",
        use_dictionary=False,
    )
    metadata = (
        prediction.loc[prediction["horizon_months"].eq(1)]
        .loc[:, ["source_id", "site_id", "common_origin_id", "time_role", "origin_year_month"]]
        .reset_index(drop=True)
    )
    bloom = prediction.pivot(
        index="common_origin_id", columns="horizon_months", values="observed_bloom"
    ).loc[metadata["common_origin_id"], list(trainer.HORIZONS)].to_numpy(dtype="float64")
    risk = prediction.pivot(
        index="common_origin_id", columns="horizon_months", values="observed_risk"
    ).loc[metadata["common_origin_id"], list(trainer.HORIZONS)].to_numpy(dtype="float64")
    bloom_prediction = prediction.pivot(
        index="common_origin_id",
        columns="horizon_months",
        values="predicted_bloom_probability",
    ).loc[metadata["common_origin_id"], list(trainer.HORIZONS)].to_numpy(dtype="float64")
    risk_prediction = prediction.pivot(
        index="common_origin_id", columns="horizon_months", values="predicted_risk"
    ).loc[metadata["common_origin_id"], list(trainer.HORIZONS)].to_numpy(dtype="float64")
    sigma = prediction.pivot(
        index="common_origin_id", columns="horizon_months", values="predicted_risk_sigma"
    ).loc[metadata["common_origin_id"], list(trainer.HORIZONS)].to_numpy(dtype="float64")
    synthetic_bundle = trainer.TrainingBundle(
        metadata,
        np.zeros((2, 12, len(trainer.input_columns(model_id))), dtype="float32"),
        bloom,
        risk,
    )
    metrics, objective = trainer._selection_metrics(
        synthetic_bundle,
        model_id=model_id,
        base_seed=base_seed,
        bloom_probability=bloom_prediction,
        risk_mu=risk_prediction,
        risk_logvar=2.0 * np.log(sigma),
        bloom_priors=np.asarray(trainer.EXPECTED_TRAINING_BLOOM_PRIORS),
        risk_priors=np.asarray(trainer.EXPECTED_TRAINING_RISK_PRIORS),
    )
    artifact = {
        "model_version": trainer.MODEL_VERSION,
        "experiment_id": "closure_v1",
        "surface_id": trainer.SURFACE_ID,
        "gate": "E0-MT",
        "model_id": model_id,
        "base_seed": base_seed,
        "upstream_state_seed": base_seed if model_id == "A1" else None,
        "device": trainer.LOCKED_DEVICE,
        "config": trainer._model_config(model_id),
        "bloom_training_priors": list(trainer.EXPECTED_TRAINING_BLOOM_PRIORS),
        "risk_training_priors": list(trainer.EXPECTED_TRAINING_RISK_PRIORS),
        "best_epoch": 1,
        "best_model_selection_objective": objective,
        "model_state_dict": state_dict,
    }
    _write(
        paths.model,
        trainer._torch_bytes(
            {**artifact, "artifact_role": "final_restored_model"}
        ),
    )
    _write(
        paths.checkpoint,
        trainer._torch_bytes(
            {**artifact, "artifact_role": "raw_best_checkpoint"}
        ),
    )
    training_metadata = auditor._reconstruct_training_metadata(repo_root=repo_root)
    history = pd.DataFrame(
        [
            {
                "epoch": epoch,
                "training_loss": 1.0,
                "model_selection_objective": objective,
                "best_objective": objective,
                "best_epoch": 1,
                "epochs_without_improvement": epoch - 1,
                "batch_order_sha256": trainer.canonical_epoch_batches(
                    training_metadata,
                    base_seed=base_seed,
                    epoch=epoch,
                )[1],
            }
            for epoch in range(1, trainer.EARLY_STOPPING_PATIENCE + 2)
        ]
    )
    _write(paths.training_curve, trainer._csv_bytes(history))
    _write(paths.selection_metrics, trainer._csv_bytes(metrics))
    _write(
        paths.report,
        auditor._expected_report(
            model_id=model_id,
            base_seed=base_seed,
            best_epoch=1,
            best_objective=objective,
        ),
    )
    outputs = [
        _record(getattr(paths, role), repo_root=repo_root, role=role)
        for role in trainer.MODEL_OUTPUT_NAMES
    ]

    canonical_prediction = trainer.canonical_prediction_frame(prediction)
    identity_columns = (
        "source_id",
        "site_id",
        "common_origin_id",
        "time_role",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
    )
    selection_identity = auditor._digest_rows(canonical_prediction, identity_columns)
    selection_targets = auditor._digest_rows(
        canonical_prediction,
        (*identity_columns, "observed_bloom", "observed_risk"),
    )
    training_identity = auditor._reconstruct_training_identity_sha256(
        repo_root=repo_root
    )
    target_contract, role_counts, architecture, preprocessing = (
        auditor._expected_contract_sections(runtime, model_id=model_id)
    )
    manifest: dict[str, Any] = {
        "manifest_version": trainer.MANIFEST_VERSION,
        "status": "completed",
        "slot_status": "available",
        "fit_status": "passed",
        "generated_at_utc": "2026-08-08T12:00:00+00:00",
        "experiment_id": "closure_v1",
        "surface_id": trainer.SURFACE_ID,
        "model_id": model_id,
        "base_seed": base_seed,
        "device": "cpu",
        "future_outcomes_accessed": False,
        "calibration_authorized": False,
        "calibration_target_accessed": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "dvc_command_executed": False,
        "target_contract": target_contract,
        "role_counts": role_counts,
        "architecture": architecture,
        "preprocessing": preprocessing,
        "pairing": {
            "policy": runtime["slots"]["pairing_policy"],
            "paired_model_ids": list(trainer.MODEL_IDS),
            "base_seed": base_seed,
            "training_identity_sha256": training_identity,
            "selection_identity_sha256": selection_identity,
            "selection_target_sha256": selection_targets,
        },
        "authority": auditor._authority_manifest_binding(authority),
        "authority_records": authority_records,
        "script": source_code[0],
        "inputs": inputs,
        "source_code": source_code,
        "outputs": outputs,
        "completion_marker_written_last": True,
    }
    _write(paths.manifest, auditor._canonical_json(manifest))
    return paths, authority, runtime


def _rewrite_manifest(paths: trainer.SlotPaths, mutate: Any) -> None:
    payload = json.loads(paths.manifest.read_text(encoding="utf-8"))
    mutate(payload)
    paths.manifest.write_bytes(auditor._canonical_json(payload))


def _refresh_output_records(
    paths: trainer.SlotPaths, *, repo_root: Path, roles: set[str]
) -> None:
    def mutate(payload: dict[str, Any]) -> None:
        refreshed = {
            role: _record(
                getattr(paths, role), repo_root=repo_root, role=role
            )
            for role in roles
        }
        payload["outputs"] = [
            refreshed.get(str(record["role"]), record)
            for record in payload["outputs"]
        ]

    _rewrite_manifest(paths, mutate)


def test_strict_json_and_canonicality_fail_closed() -> None:
    with pytest.raises(auditor.AnfisAblationModelAuditError, match="duplicate"):
        auditor._strict_json(b'{"a":1,"a":2}\n', label="fixture")
    with pytest.raises(auditor.AnfisAblationModelAuditError, match="non-finite"):
        auditor._strict_json(b'{"a":NaN}\n', label="fixture")
    assert auditor._canonical_json({"a": 1}) == b'{\n  "a": 1\n}\n'


def test_historical_slot_binding_and_source_record_are_preserved(
    tmp_path: Path,
) -> None:
    authority = _authority(prefix_count=1)
    historical = copy.deepcopy(authority["slot_manifest_authority"])
    historical["gate"] = "E0-MU"
    historical["h_patch_head"] = "8" * 40
    historical["p_patch_head"] = "9" * 40
    authority["slot_manifest_authority"] = historical
    historical_source = {
        "role": "trainer",
        "path": "src/experiments/train_closure_anfis_ablation.py",
        "bytes": 3,
        "sha256": hashlib.sha256(b"old").hexdigest(),
    }
    authority["slot_source_record"] = historical_source

    assert auditor._authority_manifest_binding(authority) == historical
    assert auditor._authority_record_specs(historical) == (
        auditor.HISTORICAL_AUTHORITY_RECORD_SPECS
    )
    assert auditor._slot_source_record(authority) == historical_source

    physical = tmp_path / historical_source["path"]
    _write(physical, b"current")
    assert auditor._verify_source_records(
        [historical_source],
        repo_root=tmp_path,
        slot_source_record=historical_source,
        allow_historical_source=True,
    ) == [historical_source]
    with pytest.raises(
        auditor.AnfisAblationModelAuditError, match="Physical source record"
    ):
        auditor._verify_source_records(
            [historical_source],
            repo_root=tmp_path,
            slot_source_record=historical_source,
            allow_historical_source=False,
        )


def test_audit_authority_requires_exact_read_only_flag_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    valid = _authority()
    monkeypatch.setattr(
        authority_patch,
        "require_anfis_ablation_model_manifest_authority",
        lambda *args, **kwargs: copy.deepcopy(valid),
    )
    assert auditor._require_audit_authority(
        tmp_path, model_id="A0", base_seed=1729
    )["model_bundle_audit_authorized"] is True

    stale_gate = copy.deepcopy(valid)
    stale_gate["gate"] = "E0-MU"
    monkeypatch.setattr(
        authority_patch,
        "require_anfis_ablation_model_manifest_authority",
        lambda *args, **kwargs: copy.deepcopy(stale_gate),
    )
    with pytest.raises(auditor.AnfisAblationModelAuditError, match="E0-MV"):
        auditor._require_audit_authority(
            tmp_path, model_id="A0", base_seed=1729
        )

    for field in ("slot_manifest_authority", "slot_source_record"):
        incomplete = copy.deepcopy(valid)
        incomplete.pop(field)
        monkeypatch.setattr(
            authority_patch,
            "require_anfis_ablation_model_manifest_authority",
            lambda *args, payload=incomplete, **kwargs: copy.deepcopy(payload),
        )
        with pytest.raises(
            auditor.AnfisAblationModelAuditError,
            match="slot-manifest|slot_source_record",
        ):
            auditor._require_audit_authority(
                tmp_path, model_id="A0", base_seed=1729
            )

    for key in (
        "model_bundle_audit_authorized",
        "target_access_through_2020_authorized",
        "selection_diagnostics_authorized",
    ):
        mutated = copy.deepcopy(valid)
        mutated[key] = False
        monkeypatch.setattr(
            authority_patch,
            "require_anfis_ablation_model_manifest_authority",
            lambda *args, payload=mutated, **kwargs: copy.deepcopy(payload),
        )
        with pytest.raises(auditor.AnfisAblationModelAuditError, match="matrix"):
            auditor._require_audit_authority(
                tmp_path, model_id="A0", base_seed=1729
            )

    for key in (
        "a0_development_fit_authorized",
        "a1_development_fit_authorized",
        "batch_slot_execution_authorized",
    ):
        mutated = copy.deepcopy(valid)
        mutated[key] = True
        monkeypatch.setattr(
            authority_patch,
            "require_anfis_ablation_model_manifest_authority",
            lambda *args, payload=mutated, **kwargs: copy.deepcopy(payload),
        )
        with pytest.raises(auditor.AnfisAblationModelAuditError, match="matrix"):
            auditor._require_audit_authority(
                tmp_path, model_id="A0", base_seed=1729
            )


def test_full_synthetic_a0_bundle_passes_without_targets_or_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    namespace = auditor._namespace_paths(paths)
    before = auditor._path_snapshot(namespace)
    targets_before = (tmp_path / trainer.TARGET_ARTIFACT).read_bytes()

    result = auditor.audit_anfis_ablation_model_bundle(
        model_id="A0",
        base_seed=1729,
        repo_root=tmp_path,
        authority=authority,
        runtime=runtime,
    )

    assert result["status"] == "passed"
    assert result["selection"]["rows"] == 6
    assert result["selection"]["origins"] == 2
    assert result["dvc_registration"]["registration_state"] == "pre_dvc"
    assert result["calibration_targets_read"] is False
    assert result["future_outcomes_accessed"] is False
    assert result["writes_performed"] is False
    assert (tmp_path / trainer.TARGET_ARTIFACT).read_bytes() == targets_before
    assert auditor._path_snapshot(namespace) == before


@pytest.mark.parametrize(
    ("artifact", "expected_error"),
    (
        ("report", "hash/size"),
        ("development_target", "Sealed target record differs from disk"),
    ),
)
def test_final_byte_reverification_rejects_late_same_size_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
    expected_error: str,
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    target = (
        paths.report
        if artifact == "report"
        else tmp_path / trainer.TARGET_ARTIFACT
    )
    original_validate_pointer = auditor._validate_pointer

    def mutate_at_final_boundary(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = original_validate_pointer(*args, **kwargs)
        metadata = target.stat()
        changed = bytearray(target.read_bytes())
        changed[0] ^= 1
        target.write_bytes(bytes(changed))
        os.utime(target, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        return result

    monkeypatch.setattr(auditor, "_validate_pointer", mutate_at_final_boundary)
    with pytest.raises(auditor.AnfisAblationModelAuditError, match=expected_error):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


def test_public_audit_rejects_forged_injected_target_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    physical = auditor.load_cutoff_target_reference(repo_root=tmp_path)
    forged_frame = physical.frame.copy(deep=True)
    forged_frame.loc[0, "bloom_h"] = 1 - int(forged_frame.loc[0, "bloom_h"])
    forged = auditor.CutoffTargetReference(
        frame=forged_frame,
        record=copy.deepcopy(physical.record),
        identity=physical.identity,
    )

    with pytest.raises(
        auditor.AnfisAblationModelAuditError,
        match="Injected cutoff target reference",
    ):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
            target_reference=forged,
        )


@pytest.mark.parametrize(
    "mutation",
    ("missing", "extra", "substitution", "reorder"),
)
def test_manifest_requires_exact_ordered_input_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)

    def mutate(payload: dict[str, Any]) -> None:
        records = payload["inputs"]
        if mutation == "missing":
            records.pop(1)
        elif mutation == "extra":
            records.append(copy.deepcopy(records[-1]))
        elif mutation == "substitution":
            records[1] = copy.deepcopy(records[4])
        else:
            records[0], records[1] = records[1], records[0]

    _rewrite_manifest(paths, mutate)
    with pytest.raises(
        auditor.AnfisAblationModelAuditError,
        match="exactly ten|role/path ordering",
    ):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


@pytest.mark.parametrize("mutation", ("missing", "reorder", "digest"))
def test_manifest_requires_exact_physical_authority_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)

    def mutate(payload: dict[str, Any]) -> None:
        records = payload["authority_records"]
        if mutation == "missing":
            records.pop()
        elif mutation == "reorder":
            records[0], records[1] = records[1], records[0]
        else:
            records[0]["sha256"] = "f" * 64

    _rewrite_manifest(paths, mutate)
    with pytest.raises(
        auditor.AnfisAblationModelAuditError,
        match="authority_records|authority record|Physical authority",
    ):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


def test_manifest_must_be_physically_newer_than_every_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    oldest = min(path.stat().st_mtime_ns for path in paths.finals if path != paths.manifest)
    os.utime(paths.manifest, ns=(oldest - 1, oldest - 1))

    with pytest.raises(auditor.AnfisAblationModelAuditError, match="physically after"):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


def test_exact_selection_pointer_is_bound_without_running_dvc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    payload = paths.selection_predictions.read_bytes()
    md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    _write(
        paths.pointer,
        (
            "outs:\n"
            f"- md5: {md5}\n"
            f"  size: {len(payload)}\n"
            "  hash: md5\n"
            f"  path: {paths.selection_predictions.name}\n"
        ).encode("utf-8"),
    )

    result = auditor.audit_anfis_ablation_model_bundle(
        model_id="A0",
        base_seed=1729,
        repo_root=tmp_path,
        authority=authority,
        runtime=runtime,
    )

    assert result["dvc_registration"]["registration_state"] == "post_dvc"
    assert result["dvc_registration"]["pointer_payload_binding_verified"] is True


def test_output_hash_drift_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    paths.report.write_bytes(b"changed report\n")
    _rewrite_manifest(paths, lambda payload: None)

    with pytest.raises(auditor.AnfisAblationModelAuditError, match="hash/size"):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


def test_finite_state_mutation_cannot_claim_existing_predictions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    torch = pytest.importorskip("torch")
    for role in ("model", "checkpoint"):
        artifact = torch.load(
            getattr(paths, role), map_location="cpu", weights_only=True
        )
        artifact["model_state_dict"]["risk_delta.bias"] = (
            artifact["model_state_dict"]["risk_delta.bias"] + 0.01
        )
        getattr(paths, role).write_bytes(trainer._torch_bytes(artifact))
    _refresh_output_records(
        paths, repo_root=tmp_path, roles={"model", "checkpoint"}
    )

    with pytest.raises(
        auditor.AnfisAblationModelAuditError,
        match="do not come from the restored model",
    ):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


@pytest.mark.parametrize("artifact", ("training_curve", "report"))
def test_curve_and_report_semantics_survive_self_consistent_hash_updates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    if artifact == "training_curve":
        frame = pd.read_csv(paths.training_curve)
        frame.loc[0, "best_epoch"] = 2
        paths.training_curve.write_bytes(trainer._csv_bytes(frame))
        expected = "early-stopping recurrence"
    else:
        paths.report.write_bytes(b"# self-consistent but false report\n")
        expected = "deterministic content"
    _refresh_output_records(paths, repo_root=tmp_path, roles={artifact})

    with pytest.raises(auditor.AnfisAblationModelAuditError, match=expected):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


def test_training_curve_batch_digests_bind_exact_cohort_and_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    frame = pd.read_csv(paths.training_curve)
    frame.loc[0, "batch_order_sha256"] = "f" * 64
    paths.training_curve.write_bytes(trainer._csv_bytes(frame))
    _refresh_output_records(
        paths, repo_root=tmp_path, roles={"training_curve"}
    )

    with pytest.raises(
        auditor.AnfisAblationModelAuditError,
        match="sealed cohort/seed",
    ):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


def test_selection_metrics_csv_requires_canonical_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    paths.selection_metrics.write_bytes(
        paths.selection_metrics.read_bytes().replace(b"\n", b"\r\n")
    )
    _refresh_output_records(
        paths, repo_root=tmp_path, roles={"selection_metrics"}
    )

    with pytest.raises(
        auditor.AnfisAblationModelAuditError,
        match="byte-canonical",
    ):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


def test_selection_labels_are_bound_to_physical_cutoff_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    frame = pq.read_table(paths.selection_predictions).to_pandas()
    horizon_one = frame.index[frame["horizon_months"].eq(1)].tolist()
    frame.loc[horizon_one[0], "observed_bloom"] = 1
    frame.loc[horizon_one[1], "observed_bloom"] = 0
    table = trainer.prediction_arrow_table(frame)
    pq.write_table(
        table,
        paths.selection_predictions,
        compression="zstd",
        use_dictionary=False,
    )
    canonical = trainer.canonical_prediction_frame(frame)
    identity_columns = (
        "source_id",
        "site_id",
        "common_origin_id",
        "time_role",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
    )

    def mutate(payload: dict[str, Any]) -> None:
        payload["pairing"]["selection_target_sha256"] = auditor._digest_rows(
            canonical,
            (*identity_columns, "observed_bloom", "observed_risk"),
        )
        payload["outputs"] = [
            _record(
                paths.selection_predictions,
                repo_root=tmp_path,
                role="selection_predictions",
            )
            if record["role"] == "selection_predictions"
            else record
            for record in payload["outputs"]
        ]

    _rewrite_manifest(paths, mutate)
    with pytest.raises(
        auditor.AnfisAblationModelAuditError,
        match="sealed <=2020 target projection",
    ):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


def test_training_identity_digest_is_reconstructed_from_common_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    _rewrite_manifest(
        paths,
        lambda payload: payload["pairing"].__setitem__(
            "training_identity_sha256", "f" * 64
        ),
    )
    with pytest.raises(
        auditor.AnfisAblationModelAuditError,
        match="Training identity digest differs",
    ):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


def test_calibration_access_or_count_mutation_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    _rewrite_manifest(paths, lambda payload: payload.__setitem__("calibration_target_accessed", True))

    with pytest.raises(auditor.AnfisAblationModelAuditError, match="calibration_target_accessed"):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )

    _rewrite_manifest(
        paths,
        lambda payload: (
            payload.__setitem__("calibration_target_accessed", False),
            payload["role_counts"].__setitem__("calibration_target_rows_read", 1),
        ),
    )
    with pytest.raises(auditor.AnfisAblationModelAuditError, match="role_counts"):
        auditor.audit_anfis_ablation_model_bundle(
            model_id="A0",
            base_seed=1729,
            repo_root=tmp_path,
            authority=authority,
            runtime=runtime,
        )


def test_manifest_scalar_dialect_requires_recursive_exact_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, _, runtime = _prepare_bundle(tmp_path, monkeypatch)
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    pairing = manifest["pairing"]
    mutations: list[tuple[str, Any]] = [
        *[
            (field, lambda payload, key=field: payload.__setitem__(key, 0))
            for field in (
                "future_outcomes_accessed",
                "calibration_authorized",
                "calibration_target_accessed",
                "evaluation_authorized",
                "e0_m_authorized",
                "e0_u_authorized",
                "dvc_command_executed",
            )
        ],
        (
            "completion_marker_written_last",
            lambda payload: payload.__setitem__(
                "completion_marker_written_last", 1
            ),
        ),
        ("base_seed", lambda payload: payload.__setitem__("base_seed", 1729.0)),
        (
            "target_contract",
            lambda payload: payload["target_contract"].__setitem__(
                "calibration_target_values_opened", 0
            ),
        ),
        (
            "role_counts",
            lambda payload: payload["role_counts"].__setitem__(
                "calibration_target_rows_read", False
            ),
        ),
        (
            "architecture",
            lambda payload: payload["architecture"].__setitem__(
                "history_length_months", 12.0
            ),
        ),
        (
            "pairing",
            lambda payload: payload["pairing"].__setitem__(
                "base_seed", 1729.0
            ),
        ),
    ]
    for label, mutate in mutations:
        mutated = copy.deepcopy(manifest)
        mutate(mutated)
        with pytest.raises(auditor.AnfisAblationModelAuditError, match=label):
            auditor._validate_manifest_semantics(
                mutated,
                model_id="A0",
                base_seed=1729,
                runtime=runtime,
                authority_binding=manifest["authority"],
                training_identity_sha256=pairing["training_identity_sha256"],
                selection_identity_sha256=pairing["selection_identity_sha256"],
                selection_target_sha256=pairing["selection_target_sha256"],
            )


def test_preprocessor_and_torch_scalar_dialects_reject_numeric_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, _, _ = _prepare_bundle(tmp_path, monkeypatch)
    preprocessor = json.loads(paths.preprocessor.read_text(encoding="utf-8"))
    preprocessor_mutations: list[tuple[str, Any]] = [
        (
            "calibration_used",
            lambda payload: payload.__setitem__("calibration_used", 0),
        ),
        ("base_seed", lambda payload: payload.__setitem__("base_seed", 1729.0)),
        (
            "missing_transport_after_transform",
            lambda payload: payload.__setitem__(
                "missing_transport_after_transform", 0
            ),
        ),
        (
            "raw statistic",
            lambda payload: payload["columns"][0].__setitem__(
                "observed_count",
                float(payload["columns"][0]["observed_count"]),
            ),
        ),
    ]
    for label, mutate in preprocessor_mutations:
        changed = copy.deepcopy(preprocessor)
        mutate(changed)
        with pytest.raises(auditor.AnfisAblationModelAuditError, match=label):
            auditor._validate_preprocessor_json(
                auditor._canonical_json(changed), model_id="A0", base_seed=1729
            )

    torch = pytest.importorskip("torch")
    artifact = torch.load(paths.model, map_location="cpu", weights_only=True)
    torch_mutations: list[tuple[str, Any]] = [
        ("base_seed", lambda payload: payload.__setitem__("base_seed", 1729.0)),
        (
            "upstream_state_seed",
            lambda payload: payload.__setitem__("upstream_state_seed", False),
        ),
        (
            "config",
            lambda payload: payload["config"].__setitem__("add_last", 0),
        ),
        (
            "config",
            lambda payload: payload["config"].__setitem__(
                "history_length_months", 12.0
            ),
        ),
        (
            "checkpoint selection",
            lambda payload: payload.__setitem__(
                "best_model_selection_objective", 1
            ),
        ),
    ]
    for label, mutate in torch_mutations:
        changed = copy.deepcopy(artifact)
        mutate(changed)
        with pytest.raises(auditor.AnfisAblationModelAuditError, match=label):
            auditor._load_torch_artifact(
                trainer._torch_bytes(changed),
                artifact_role="final_restored_model",
                model_id="A0",
                base_seed=1729,
            )


def test_csv_scalar_dialects_require_exact_integer_and_float_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, _, _ = _prepare_bundle(tmp_path, monkeypatch)
    torch = pytest.importorskip("torch")
    artifact = torch.load(paths.model, map_location="cpu", weights_only=True)
    training_metadata = auditor._reconstruct_training_metadata(repo_root=tmp_path)
    curve = pd.read_csv(paths.training_curve, float_precision="round_trip")
    for column in ("epoch", "best_epoch", "epochs_without_improvement"):
        changed = curve.copy(deep=True)
        changed[column] = changed[column].astype(float)
        with pytest.raises(
            auditor.AnfisAblationModelAuditError,
            match=f"integer field drifted: {column}",
        ):
            auditor._validate_training_curve(
                trainer._csv_bytes(changed),
                training_metadata=training_metadata,
                base_seed=1729,
                best_epoch=artifact["best_epoch"],
                best_objective=artifact["best_model_selection_objective"],
            )
    integer_loss = curve.copy(deep=True)
    integer_loss["training_loss"] = 1
    with pytest.raises(
        auditor.AnfisAblationModelAuditError,
        match="floating field drifted: training_loss",
    ):
        auditor._validate_training_curve(
            trainer._csv_bytes(integer_loss),
            training_metadata=training_metadata,
            base_seed=1729,
            best_epoch=artifact["best_epoch"],
            best_objective=artifact["best_model_selection_objective"],
        )

    preprocessor = auditor._validate_preprocessor_json(
        paths.preprocessor.read_bytes(), model_id="A0", base_seed=1729
    )
    _, _, _, predictions = auditor._validate_selection_predictions(
        paths.selection_predictions.read_bytes(), model_id="A0", base_seed=1729
    )
    metrics = pd.read_csv(paths.selection_metrics, float_precision="round_trip")
    for column in ("base_seed", "horizon_months", "rows", "bloom_positive"):
        changed = metrics.copy(deep=True)
        changed[column] = changed[column].astype(float)
        with pytest.raises(
            auditor.AnfisAblationModelAuditError,
            match=f"integer field drifted: {column}",
        ):
            auditor._validate_selection_metrics(
                trainer._csv_bytes(changed),
                model_id="A0",
                base_seed=1729,
                predictions=predictions,
                preprocessor=preprocessor,
            )


@pytest.mark.parametrize(
    ("origin", "target"),
    (("2020-12", "2021-01"), ("2018-11", "2018-12")),
)
def test_selection_schema_and_role_interval_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    origin: str,
    target: str,
) -> None:
    paths, authority, runtime = _prepare_bundle(tmp_path, monkeypatch)
    frame = _prediction_frame("A0", 1729)
    frame.loc[0, "origin_year_month"] = origin
    frame.loc[0, "target_year_month"] = target

    pq.write_table(
        pa.Table.from_pandas(
            frame, schema=trainer.prediction_arrow_schema(), preserve_index=False
        ).replace_schema_metadata(None),
        paths.selection_predictions,
        compression="zstd",
        use_dictionary=False,
    )
    with pytest.raises(
        auditor.AnfisAblationModelAuditError,
        match="2020 cutoff|model_selection interval",
    ):
        auditor._validate_selection_predictions(
            paths.selection_predictions.read_bytes(), model_id="A0", base_seed=1729
        )


def test_temporary_guard_or_symlinked_final_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, _, _ = _prepare_bundle(tmp_path, monkeypatch)
    _write(paths.guard, b"")
    snapshot = auditor._path_snapshot(auditor._namespace_paths(paths))
    with pytest.raises(auditor.AnfisAblationModelAuditError, match="residue"):
        auditor._validate_namespace(snapshot, paths)

    paths.guard.unlink()
    paths.report.unlink()
    paths.report.symlink_to(paths.model)
    snapshot = auditor._path_snapshot(auditor._namespace_paths(paths))
    with pytest.raises(auditor.AnfisAblationModelAuditError, match="non-regular"):
        auditor._validate_namespace(snapshot, paths)


def test_namespace_requires_exact_mode_0644_for_finals_and_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, _, _ = _prepare_bundle(tmp_path, monkeypatch)
    paths.report.chmod(0o640)
    snapshot = auditor._path_snapshot(auditor._namespace_paths(paths))
    with pytest.raises(auditor.AnfisAblationModelAuditError, match="mode 0644"):
        auditor._validate_namespace(snapshot, paths)

    paths.report.chmod(0o644)
    _write(paths.pointer, b"outs: []\n")
    paths.pointer.chmod(0o600)
    snapshot = auditor._path_snapshot(auditor._namespace_paths(paths))
    with pytest.raises(auditor.AnfisAblationModelAuditError, match="mode 0644"):
        auditor._validate_namespace(snapshot, paths)


def test_semantic_core_requires_exact_boolean_pointer_policy(tmp_path: Path) -> None:
    with pytest.raises(
        auditor.AnfisAblationModelAuditError, match="exact boolean"
    ):
        auditor.validate_anfis_ablation_model_bundle_semantics(
            model_id="A0",
            base_seed=1729,
            authority_binding={},
            runtime={},
            repo_root=tmp_path,
            allow_pointer=cast(Any, 1),
        )


def test_pairing_requires_exact_A0_A1_and_cross_seed_target_identity() -> None:
    results: list[dict[str, Any]] = []
    for model_id, base_seed in auditor.BUNDLE_SLOTS:
        results.append(
            {
                "model_id": model_id,
                "base_seed": base_seed,
                "pairing": {
                    "training_identity_sha256": "a" * 64,
                    "selection_identity_sha256": "b" * 64,
                    "selection_target_sha256": "c" * 64,
                },
            }
        )
    auditor._validate_paired_results(results)

    results[1]["pairing"]["selection_target_sha256"] = "d" * 64
    with pytest.raises(auditor.AnfisAblationModelAuditError, match="paired"):
        auditor._validate_paired_results(results)


def test_cli_requires_check_only_and_exact_target() -> None:
    args = auditor.parse_args(
        ["--model-id", "A1", "--base-seed", "20260612", "--check-only"]
    )
    assert args.model_id == "A1"
    assert args.base_seed == 20260612
    with pytest.raises(SystemExit):
        auditor.parse_args(["--all"])
