from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from src.experiments import (
    closure_anfis_ablation_model_publication_adoption_patch as authority_patch,
)
from src.experiments import train_closure_anfis_ablation as trainer


def _tensor(rows: int, dimension: int = 18) -> np.ndarray:
    values = np.zeros((rows, trainer.HISTORY_LENGTH, dimension), dtype=np.float32)
    for channel in range(trainer.RAW_DIMENSION):
        values[:, :, channel] = np.arange(rows * trainer.HISTORY_LENGTH).reshape(
            rows, trainer.HISTORY_LENGTH
        ) + channel
        values[:, :, trainer.MASK_OFFSET + channel] = 1.0
    values[:, :, 14] = 1.0
    if dimension == 27:
        values[:, :, 18:] = 0.5
    return values


def _bundle(rows_per_role: int = 3, dimension: int = 18) -> trainer.TrainingBundle:
    roles = ["training"] * rows_per_role + ["model_selection"] * rows_per_role
    rows = len(roles)
    metadata = pd.DataFrame(
        {
            "source_id": ["wqp"] * rows,
            "site_id": [f"site-{index:02d}" for index in range(rows)],
            "common_origin_id": [f"origin-{index:02d}" for index in range(rows)],
            "time_role": roles,
            "origin_year_month": ["2018-01"] * rows_per_role + ["2019-01"] * rows_per_role,
        }
    )
    bloom = np.tile(np.asarray([[0.0, 1.0, 0.0]], dtype=np.float32), (rows, 1))
    risk = np.tile(np.asarray([[0.2, 0.5, 0.8]], dtype=np.float32), (rows, 1))
    return trainer.TrainingBundle(metadata, _tensor(rows, dimension), bloom, risk)


def test_slot_paths_and_seed_contract(tmp_path: Path) -> None:
    paths = trainer.slot_paths("A1", 1729, repo_root=tmp_path)
    assert paths.model.relative_to(tmp_path).as_posix() == (
        "models/closure_v1/anfis_ablation/A1/seed_1729.pt"
    )
    assert paths.selection_predictions.relative_to(tmp_path).as_posix() == (
        "data/closure_v1/development/anfis_ablation/A1/seed_1729_selection_predictions.parquet"
    )
    assert paths.manifest.name == "seed_1729_manifest.json"
    with pytest.raises(trainer.AnfisAblationTrainingError, match="Unregistered"):
        trainer.slot_paths("A2", 1729, repo_root=tmp_path)


def test_mask_aware_standardizer_uses_only_observed_training_cells() -> None:
    values = _tensor(2)
    values[0, 0, 0] = 999_999.0
    values[0, 0, trainer.MASK_OFFSET] = 0.0
    standardizer = trainer.fit_mask_aware_standardizer(values)
    expected = values[:, :, 0][values[:, :, trainer.MASK_OFFSET] == 1.0].astype(np.float64)
    assert standardizer.counts[0] == expected.size
    assert standardizer.means[0] == pytest.approx(expected.mean())
    transformed = trainer.apply_mask_aware_standardizer(values, standardizer)
    assert transformed[0, 0, 0] == 0.0
    assert transformed.dtype == np.float32
    assert np.isfinite(transformed).all()


def test_input_scaler_uses_all_training_rows_and_targets_collapse_to_three_heads() -> None:
    tensor = _tensor(4)
    tensor[2:, :, 0] += 1_000.0
    sequence = pd.DataFrame(
        {
            "common_origin_id": [f"origin-{index}" for index in range(4)],
            "time_role": ["training"] * 4,
            **{
                column: [tensor[row, :, index] for row in range(4)]
                for index, column in enumerate(trainer.A0_INPUT_COLUMNS)
            },
        }
    )
    standardizer = trainer.fit_sequence_training_standardizer(
        sequence, model_id="A0"
    )
    all_training = trainer.fit_mask_aware_standardizer(tensor)
    supervised_subset = trainer.fit_mask_aware_standardizer(tensor[:2])
    np.testing.assert_array_equal(standardizer.counts, all_training.counts)
    np.testing.assert_allclose(standardizer.means, all_training.means, rtol=0.0, atol=0.0)
    assert standardizer.means[0] != supervised_subset.means[0]
    duplicated_sequence = pd.concat([sequence, sequence.iloc[[0]]], ignore_index=True)
    with pytest.raises(trainer.AnfisAblationTrainingError, match="duplicated"):
        trainer.fit_sequence_training_standardizer(
            duplicated_sequence, model_id="A0"
        )

    target_rows = pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": f"site-{origin}",
                "common_origin_id": f"origin-{origin}",
                "evaluation_unit_id": f"unit-{origin}-h{horizon}",
                "holdout_group_id": f"group-{origin}",
                "assignment_role": "development",
                "time_role": "training",
                "origin_year_month": "2018-01",
                "target_year_month": f"2018-{1 + horizon:02d}",
                "horizon_months": horizon,
                "bloom_h": float(horizon == 2),
                "target_risk_chla_h": float(horizon) / 4.0,
            }
            for origin in range(2)
            for horizon in trainer.HORIZONS
        ]
    )
    origins = trainer.collapse_supervised_origins(target_rows)
    bloom, risk = trainer.supervised_target_matrices(target_rows, origins)
    assert len(origins) == 2
    assert origins["common_origin_id"].is_unique
    assert "evaluation_unit_id" not in origins.columns
    assert bloom.shape == risk.shape == (2, 3)
    np.testing.assert_array_equal(bloom, [[0.0, 1.0, 0.0], [0.0, 1.0, 0.0]])
    np.testing.assert_allclose(risk, [[0.25, 0.5, 0.75], [0.25, 0.5, 0.75]])
    changed_identity = target_rows.copy()
    changed_identity.loc[1, "site_id"] = "different-site"
    with pytest.raises(trainer.AnfisAblationTrainingError, match="changes across"):
        trainer.collapse_supervised_origins(changed_identity)
    duplicate_target = pd.concat([target_rows, target_rows.iloc[[0]]], ignore_index=True)
    with pytest.raises(trainer.AnfisAblationTrainingError, match="duplicated"):
        trainer.supervised_target_matrices(duplicate_target, origins)


def test_physical_a0_loader_uses_frozen_input_scaler_and_unique_supervised_origins() -> None:
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        bundle, standardizer, records, paths = trainer.load_training_bundle(
            model_id="A0", base_seed=1729
        )
    assert captured == []
    training = bundle.subset("training")
    selection = bundle.subset("model_selection")
    assert len(training.metadata) == trainer.EXPECTED_TRAINING_ORIGINS
    assert len(selection.metadata) == trainer.EXPECTED_SELECTION_ORIGINS
    assert bundle.metadata["common_origin_id"].is_unique
    assert training.bloom.shape == (trainer.EXPECTED_TRAINING_ORIGINS, 3)
    assert selection.bloom.shape == (trainer.EXPECTED_SELECTION_ORIGINS, 3)
    temperature_index = standardizer.columns.index("x_mean_temperature_C")
    assert int(standardizer.counts[temperature_index]) == (
        trainer.EXPECTED_SEQUENCE_TRAINING_ORIGINS * trainer.HISTORY_LENGTH
    )
    for index, column in enumerate(standardizer.columns):
        count, mean, standard_deviation = trainer.EXPECTED_RAW_STANDARDIZATION[column]
        assert int(standardizer.counts[index]) == count
        assert float(standardizer.means[index]) == mean
        assert float(standardizer.standard_deviations[index]) == standard_deviation
    assert len(records) == len(paths) == 10
    assert len({str(record["role"]) for record in records}) == 10


def test_mask_and_identity_channels_are_not_scaled() -> None:
    values = _tensor(3, 27)
    standardizer = trainer.fit_mask_aware_standardizer(values)
    transformed = trainer.apply_mask_aware_standardizer(values, standardizer)
    np.testing.assert_array_equal(transformed[:, :, 7:], values[:, :, 7:])


def test_training_priors_are_horizon_specific() -> None:
    bundle = _bundle()
    bloom, risk = trainer.training_priors(bundle)
    np.testing.assert_allclose(bloom, [0.0, 1.0, 0.0])
    np.testing.assert_allclose(risk, [0.2, 0.5, 0.8])


@pytest.mark.parametrize("dimension", [18, 27])
def test_direct_prior_residual_gru_has_three_heads(dimension: int) -> None:
    torch = pytest.importorskip("torch")
    model = trainer.make_anfis_ablation_model(
        input_dimension=dimension,
        bloom_priors=np.asarray([0.2, 0.3, 0.4]),
        risk_priors=np.asarray([0.4, 0.5, 0.6]),
    )
    x = torch.zeros((2, 12, dimension), dtype=torch.float32)
    bloom, risk, logvar = model(x)
    assert bloom.shape == risk.shape == logvar.shape == (2, 3)
    assert bool(((risk >= 0.0) & (risk <= 1.0)).all())
    assert bool(((logvar >= trainer.LOGVAR_MIN) & (logvar <= trainer.LOGVAR_MAX)).all())


def test_direct_multitask_loss_is_finite_and_differentiable() -> None:
    torch = pytest.importorskip("torch")
    logits = torch.zeros((2, 3), requires_grad=True)
    means = torch.full((2, 3), 0.5, requires_grad=True)
    logvar = torch.zeros((2, 3), requires_grad=True)
    bloom = torch.tensor([[0.0, 1.0, 0.0], [1.0, 0.0, 1.0]])
    risk = torch.tensor([[0.2, 0.4, 0.6], [0.3, 0.5, 0.7]])
    loss = trainer.direct_multitask_loss(logits, means, logvar, bloom, risk)
    loss.backward()
    assert np.isfinite(float(loss.detach()))
    assert logits.grad is not None and means.grad is not None and logvar.grad is not None


def test_canonical_epoch_batches_are_seeded_and_complete() -> None:
    metadata = _bundle(4).subset("training").metadata
    batches_a, digest_a = trainer.canonical_epoch_batches(
        metadata, base_seed=1729, epoch=1, batch_size=3
    )
    batches_b, digest_b = trainer.canonical_epoch_batches(
        metadata, base_seed=1729, epoch=1, batch_size=3
    )
    assert digest_a == digest_b
    np.testing.assert_array_equal(np.concatenate(batches_a), np.concatenate(batches_b))
    assert sorted(np.concatenate(batches_a).tolist()) == list(range(len(metadata)))


def test_prediction_frame_rejects_calibration_role() -> None:
    row = {
        "surface_id": trainer.SURFACE_ID,
        "model_id": "A0",
        "base_seed": 1729,
        "source_id": "wqp",
        "site_id": "s",
        "common_origin_id": "o",
        "time_role": "calibration_threshold",
        "origin_year_month": "2019-01",
        "target_year_month": "2019-02",
        "horizon_months": 1,
        "observed_bloom": 0,
        "observed_risk": 0.2,
        "predicted_bloom_probability": 0.3,
        "predicted_risk": 0.4,
        "predicted_risk_sigma": 0.5,
        "availability_status": "success",
        "failure_reason": "",
        "score_semantics": "direct_bloom_probability_and_risk_distribution",
    }
    frame = pd.DataFrame([row], columns=trainer.PREDICTION_COLUMNS)
    with pytest.raises(trainer.AnfisAblationTrainingError, match="another role"):
        trainer.canonical_prediction_frame(frame)


def test_preprocessor_payload_is_json_serializable() -> None:
    payload = trainer.fit_mask_aware_standardizer(_tensor(2)).as_dict()
    assert json.loads(json.dumps(payload))["fit_role"] == "training"


def test_prediction_schema_and_metrics_contract_are_exact() -> None:
    assert trainer.prediction_arrow_schema().names == list(trainer.PREDICTION_COLUMNS)
    assert len(trainer.PREDICTION_COLUMNS) == 18
    rows = trainer.EXPECTED_SELECTION_ORIGINS
    metadata = pd.DataFrame(
        {
            "source_id": ["wqp"] * rows,
            "site_id": [f"s-{index:04d}" for index in range(rows)],
            "common_origin_id": [f"o-{index:04d}" for index in range(rows)],
            "time_role": ["model_selection"] * rows,
            "origin_year_month": ["2019-01"] * rows,
        }
    )
    bloom = np.zeros((rows, 3), dtype=np.float64)
    bloom[:136, 0] = 1.0
    bloom[:136, 1] = 1.0
    bloom[:132, 2] = 1.0
    risk = np.tile(np.asarray([[0.2, 0.4, 0.6]]), (rows, 1))
    bundle = trainer.TrainingBundle(metadata, _tensor(rows), bloom, risk)
    probability = np.tile(np.asarray([[0.25, 0.3, 0.35]]), (rows, 1))
    risk_prediction = np.tile(np.asarray([[0.3, 0.5, 0.7]]), (rows, 1))
    logvar = np.zeros((rows, 3), dtype=np.float64)
    metrics, objective = trainer._selection_metrics(
        bundle,
        model_id="A0",
        base_seed=1729,
        bloom_probability=probability,
        risk_mu=risk_prediction,
        risk_logvar=logvar,
        bloom_priors=np.asarray([0.2, 0.3, 0.4]),
        risk_priors=np.asarray([0.4, 0.5, 0.6]),
    )
    assert metrics.columns.tolist() == [
        "model_id",
        "base_seed",
        "horizon_months",
        "time_role",
        "rows",
        "bloom_positive",
        "brier",
        "pr_auc",
        "rmse",
        "mae",
        "prior_brier",
        "prior_rmse",
        "prior_mae",
        "brier_ratio",
        "rmse_ratio",
        "mae_ratio",
        "checkpoint_objective",
    ]
    ratios = metrics[["brier_ratio", "rmse_ratio", "mae_ratio"]].to_numpy()
    assert objective == pytest.approx(float(ratios.mean()))
    assert metrics["checkpoint_objective"].eq(objective).all()


def test_runtime_alignment_rejects_add_last() -> None:
    runtime_path = Path("configs/closure_v1/anfis_ablation_training_development_runtime.yaml")
    runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
    trainer._validate_runtime_alignment(runtime)
    runtime["model"]["common_architecture"]["add_last"] = True
    with pytest.raises(trainer.AnfisAblationTrainingError, match="architecture"):
        trainer._validate_runtime_alignment(runtime)


def test_cutoff_safe_target_projection_filters_2021(tmp_path: Path) -> None:
    target = tmp_path / "target.parquet"
    frame = pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "s",
                "origin_year_month": "2020-10",
                "target_year_month": "2020-11",
                "horizon_months": 1,
                "bloom_h": 0,
                "target_risk_chla_h": 0.2,
            },
            {
                "source_id": "wqp",
                "site_id": "s",
                "origin_year_month": "2021-01",
                "target_year_month": "2021-02",
                "horizon_months": 1,
                "bloom_h": 1,
                "target_risk_chla_h": 0.9,
            },
        ]
    )
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), target)
    projected, record = trainer._read_target_projection(
        target, development_site_ids=["s"], repo_root=tmp_path
    )
    assert len(projected) == 1
    assert projected.iloc[0]["target_year_month"] == "2020-11"
    assert record["path"] == "target.parquet"


def test_fit_origin_and_target_months_must_share_sealed_role() -> None:
    valid = pd.DataFrame(
        [
            {
                "time_role": "training",
                "origin_year_month": "2018-10",
                "target_year_month": "2018-12",
            },
            {
                "time_role": "model_selection",
                "origin_year_month": "2019-01",
                "target_year_month": "2019-03",
            },
        ]
    )
    trainer.validate_fit_role_months(valid)
    invalid = valid.copy()
    invalid.loc[1, "origin_year_month"] = "2018-12"
    with pytest.raises(trainer.AnfisAblationTrainingError, match="sealed time role"):
        trainer.validate_fit_role_months(invalid)


def test_stable_input_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "regular.bin"
    target.write_bytes(b"pinned")
    linked = tmp_path / "linked.bin"
    linked.symlink_to(target.name)
    with pytest.raises((trainer.AnfisAblationTrainingError, OSError)):
        trainer._stable_file_record(linked, repo_root=tmp_path)


def test_completed_prefix_hash_snapshot_detects_fit_and_publication_drift(
    tmp_path: Path,
) -> None:
    ordered_slots = [
        {"model_id": model_id, "base_seed": base_seed}
        for base_seed in trainer.REGISTERED_SEEDS
        for model_id in trainer.MODEL_IDS
    ]
    authority = {
        "completed_prefix_count": 1,
        "slot_creation_prefix_count": 1,
        "ordered_slots": ordered_slots,
    }
    historical = trainer.slot_paths("A0", 1729, repo_root=tmp_path)
    for index, path in enumerate(historical.finals):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"historical-{index:02d}".encode("ascii"))
        path.chmod(0o644)
    baseline = trainer._completed_prefix_snapshot(authority, repo_root=tmp_path)
    assert len(baseline) == 8
    assert all(
        set(record)
        == {
            "path",
            "bytes",
            "sha256",
            "mode",
            "device",
            "inode",
            "nlink",
            "mtime_ns",
            "ctime_ns",
        }
        and record["nlink"] == 1
        for record in baseline
    )

    mutated_path = historical.report
    original = mutated_path.read_bytes()
    metadata = mutated_path.stat()
    mutated_path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    os.utime(mutated_path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    with pytest.raises(
        trainer.AnfisAblationTrainingError,
        match="completed-prefix artifact changed",
    ):
        trainer._assert_completed_prefix_snapshot(
            baseline, authority=authority, repo_root=tmp_path
        )

    mutated_path.write_bytes(original)
    mutated_path.chmod(0o644)
    mutated_path.chmod(0o600)
    with pytest.raises(
        trainer.AnfisAblationTrainingError,
        match="artifact mode drifted",
    ):
        trainer._assert_completed_prefix_snapshot(
            baseline, authority=authority, repo_root=tmp_path
        )
    mutated_path.chmod(0o644)
    linked = tmp_path / "historical-hardlink"
    os.link(mutated_path, linked)
    with pytest.raises(
        trainer.AnfisAblationTrainingError,
        match="link count drifted",
    ):
        trainer._completed_prefix_snapshot(authority, repo_root=tmp_path)
    linked.unlink()

    identity_baseline = trainer._completed_prefix_snapshot(
        authority, repo_root=tmp_path
    )
    replacement = tmp_path / "identical-replacement"
    replacement.write_bytes(mutated_path.read_bytes())
    replacement.chmod(0o644)
    replacement.replace(mutated_path)
    with pytest.raises(
        trainer.AnfisAblationTrainingError,
        match="completed-prefix artifact changed",
    ):
        trainer._assert_completed_prefix_snapshot(
            identity_baseline, authority=authority, repo_root=tmp_path
        )

    publication_baseline = trainer._completed_prefix_snapshot(
        authority, repo_root=tmp_path
    )
    current = trainer.slot_paths("A1", 1729, repo_root=tmp_path).report
    with pytest.raises(
        trainer.AnfisAblationTrainingError,
        match="completed-prefix artifact changed",
    ):
        with trainer.OutputTransaction(tmp_path) as transaction:
            transaction.publish_bytes(b"current-output", current)
            metadata = mutated_path.stat()
            mutated_path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            os.utime(
                mutated_path,
                ns=(metadata.st_atime_ns, metadata.st_mtime_ns),
            )
            trainer._assert_completed_prefix_snapshot(
                publication_baseline, authority=authority, repo_root=tmp_path
            )
    assert not current.exists()


def test_output_transaction_rolls_back_owned_inode_only(tmp_path: Path) -> None:
    output = tmp_path / "bundle" / "report.md"
    with pytest.raises(RuntimeError, match="abort"):
        with trainer.OutputTransaction(tmp_path) as transaction:
            transaction.publish_bytes(b"owned", output)
            raise RuntimeError("abort")
    assert not output.exists()
    with pytest.raises(RuntimeError, match="foreign"):
        with trainer.OutputTransaction(tmp_path) as transaction:
            transaction.publish_bytes(b"owned", output)
            output.unlink()
            output.write_bytes(b"foreign")
            raise RuntimeError("foreign")
    assert output.read_bytes() == b"foreign"


def test_output_publication_rejects_zero_progress_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trainer.os, "write", lambda *args, **kwargs: 0)
    with pytest.raises(trainer.AnfisAblationTrainingError, match="no progress"):
        trainer._publish_owned(
            tmp_path / "bundle" / "report.md", b"payload", repo_root=tmp_path
        )
    assert not (tmp_path / "bundle" / "report.md").exists()
    assert not (tmp_path / "bundle" / "report.md.tmp").exists()


def test_output_no_clobber_and_linked_parent(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    existing.write_bytes(b"original")
    with pytest.raises(trainer.AnfisAblationTrainingError, match="overwrite"):
        with trainer.OutputTransaction(tmp_path) as transaction:
            transaction.publish_bytes(b"replacement", existing)
    assert existing.read_bytes() == b"original"
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real.name, target_is_directory=True)
    with pytest.raises((trainer.AnfisAblationTrainingError, OSError)):
        with trainer.OutputTransaction(tmp_path) as transaction:
            transaction.publish_bytes(b"payload", linked / "artifact.json")


def test_guard_replacement_is_not_deleted(tmp_path: Path) -> None:
    guard_path = tmp_path / "tmp" / "slot.guard"
    guard = trainer._acquire_guard(guard_path, repo_root=tmp_path)
    with pytest.raises(FileExistsError):
        os.open(guard_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    guard_path.unlink()
    guard_path.write_bytes(b"foreign")
    with pytest.raises(trainer.AnfisAblationTrainingError, match="identity"):
        trainer._release_guard(guard)
    assert guard_path.read_bytes() == b"foreign"


def test_importable_execute_cannot_bypass_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    def reject_gate(**_: object) -> dict[str, object]:
        events.append("gate")
        raise trainer.AnfisAblationTrainingError("closed")

    monkeypatch.setattr(trainer, "_require_effective_authority", reject_gate)
    monkeypatch.setattr(
        trainer,
        "slot_paths",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("path before gate")),
    )
    with pytest.raises(trainer.AnfisAblationTrainingError, match="closed"):
        trainer.execute_one_shot(model_id="A0", base_seed=1729, repo_root=tmp_path)
    assert events == ["gate"]


def test_effective_authority_is_routed_exclusively_through_e0_mx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert trainer.AUTHORITY_RECORD_SPECS == (
        (
            "runtime",
            "anfis_ablation_training_runtime_contract",
            Path("configs/closure_v1/anfis_ablation_training_development_runtime.yaml"),
        ),
        (
            "lock",
            "anfis_ablation_model_publication_adoption_patch_lock",
            Path(
                "reports/closure_v1/00_protocol/"
                "anfis_ablation_model_publication_adoption_patch_lock.json"
            ),
        ),
        (
            "companion",
            "anfis_ablation_model_publication_adoption_patch_lock_manifest",
            Path(
                "reports/closure_v1/00_protocol/"
                "anfis_ablation_model_publication_adoption_patch_lock_manifest.json"
            ),
        ),
    )
    binding = {
        "gate": "E0-MX",
        "status": "effective_preflight_passed",
        "authorized_model_id": "A1",
        "authorized_base_seed": 1729,
        "completed_prefix_count": 1,
        "slot_creation_prefix_count": 1,
        "h_patch_head": "1" * 40,
        "p_patch_head": "2" * 40,
        "h_components_sha256": "3" * 64,
        "physical_inputs_sha256": "4" * 64,
        "runtime_sha256": "5" * 64,
        "lock_sha256": "6" * 64,
        "companion_sha256": "7" * 64,
    }
    payload = {**binding, "slot_manifest_authority": dict(binding)}
    monkeypatch.setattr(
        authority_patch,
        "require_anfis_ablation_model_publication_authority",
        lambda *args, **kwargs: dict(payload),
    )
    assert trainer._require_effective_authority(
        repo_root=tmp_path, model_id="A1", base_seed=1729
    ) == payload
    assert trainer._authority_binding(payload) == binding

    monkeypatch.setattr(
        authority_patch,
        "require_anfis_ablation_model_publication_authority",
        lambda *args, **kwargs: {**payload, "gate": "E0-MW"},
    )
    with pytest.raises(trainer.AnfisAblationTrainingError, match="E0-MX"):
        trainer._require_effective_authority(
            repo_root=tmp_path, model_id="A1", base_seed=1729
        )

    incomplete = dict(payload)
    incomplete.pop("slot_manifest_authority")
    with pytest.raises(trainer.AnfisAblationTrainingError, match="slot-manifest"):
        trainer._authority_binding(incomplete)


def test_main_calls_gate_before_check_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        trainer,
        "parse_args",
        lambda argv=None: type(
            "Args",
            (),
            {
                "model_id": "A0",
                "base_seed": 1729,
                "device": "cpu",
                "check_only": True,
                "execute_one_shot": False,
            },
        )(),
    )

    def reject_gate(**_: object) -> dict[str, object]:
        events.append("gate")
        raise trainer.AnfisAblationTrainingError("closed")

    monkeypatch.setattr(trainer, "_require_effective_authority", reject_gate)
    monkeypatch.setattr(
        trainer,
        "check_only",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("check before gate")),
    )
    with pytest.raises(trainer.AnfisAblationTrainingError, match="closed"):
        trainer.main([])
    assert events == ["gate"]
