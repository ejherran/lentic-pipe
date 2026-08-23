from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.experiments.closure_v2 import train_temporal


def _bundle(*, include_incomplete_intent: bool = True) -> tuple[train_temporal.WindowBundle, pd.DataFrame]:
    rng = np.random.default_rng(10)
    x = rng.normal(0.0, 0.1, size=(16, 12, 13)).astype(np.float32)
    y = (x[:, -1, :9] + 0.01).astype(np.float32)
    metadata = pd.DataFrame(
        {
            "source_id": ["synthetic"] * 16,
            "site_id": [f"site:{index}" for index in range(16)],
            "origin_year_month": ["2018-01"] * 12 + ["2019-01"] * 4,
            "target_year_month": ["2018-02"] * 12 + ["2019-02"] * 4,
            "time_role": ["training"] * 12 + ["model_selection"] * 4,
        }
    )
    ledger = metadata.copy()
    ledger["fit_eligible"] = True
    ledger["exclusion_reason"] = ""
    if include_incomplete_intent:
        extra = ledger.iloc[[0]].copy()
        extra["site_id"] = "site:incomplete"
        extra["fit_eligible"] = False
        extra["exclusion_reason"] = "input_incomplete"
        ledger = pd.concat([ledger, extra], ignore_index=True)
    return train_temporal.WindowBundle(metadata, x, y), ledger


def _profiles() -> tuple[train_temporal.TrainingProfile, ...]:
    return (
        train_temporal.TrainingProfile("v2_primary", 4, 3, 2, 0.0),
        train_temporal.TrainingProfile("legacy_diagnostic", 8, 2, 1, 0.0),
    )


def test_incomplete_intent_row_remains_outside_loss_and_fit_completes() -> None:
    bundle, ledger = _bundle()
    fit = train_temporal.fit_slot(bundle, model_id="P0", base_seed=1729, profiles=_profiles())
    assert len(ledger) == 17
    assert (~ledger["fit_eligible"]).sum() == 1
    assert fit.selected_profile in {"v2_primary", "legacy_diagnostic"}


def test_seed_is_deterministic_and_best_checkpoint_is_restored() -> None:
    bundle, _ = _bundle()
    first = train_temporal.fit_slot(bundle, model_id="P0", base_seed=1729, profiles=_profiles())
    second = train_temporal.fit_slot(bundle, model_id="P0", base_seed=1729, profiles=_profiles())
    first_profile = next(item for item in first.profile_fits if item.profile.name == first.selected_profile)
    second_profile = next(item for item in second.profile_fits if item.profile.name == second.selected_profile)
    assert first.selected_profile == second.selected_profile
    assert first_profile.best_epoch == second_profile.best_epoch
    assert first_profile.best_objective == second_profile.best_objective
    assert all(
        train_temporal._require_torch().equal(
            first_profile.best_state_dict[key], second_profile.best_state_dict[key]
        )
        for key in first_profile.best_state_dict
    )


def test_output_blend_is_finalized_once_for_selected_profile() -> None:
    bundle, _ = _bundle()
    fit = train_temporal.fit_slot(bundle, model_id="P1", base_seed=1729, profiles=_profiles())
    assert len(fit.blend_weights) == 9
    assert set(fit.blend_weights["target"]) == set(train_temporal.STATE_TARGET_NAMES)


def test_runtime_rejects_threshold_or_profile_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = train_temporal.load_yaml_mapping(train_temporal.RUNTIME_CONFIG)
    runtime["profiles"]["v2_primary"]["batch_size"] = 513
    monkeypatch.setattr(train_temporal, "load_yaml_mapping", lambda _: runtime)
    with pytest.raises(train_temporal.TemporalTrainingError, match="profiles"):
        train_temporal.validate_runtime()


def test_no_resume_or_replacement_when_any_slot_artifact_exists(tmp_path: Path) -> None:
    path = tmp_path / "reports/closure_v2/02_models/P0/seed_1729/manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(train_temporal.TemporalTrainingError, match="Resume/replacement"):
        train_temporal.ensure_slot_absent("P0", 1729, root=tmp_path)


def test_atomic_bundle_writes_manifest_last_and_rolls_back(tmp_path: Path) -> None:
    report = Path("reports/slot/report.md")
    manifest = Path("reports/slot/manifest.json")
    train_temporal._exclusive_bundle([(report, b"ok\n"), (manifest, b"{}\n")], root=tmp_path)
    assert (tmp_path / manifest).stat().st_mtime_ns >= (tmp_path / report).stat().st_mtime_ns

    blocked_root = tmp_path / "blocked"
    occupied = blocked_root / manifest
    occupied.parent.mkdir(parents=True)
    occupied.write_text("occupied\n", encoding="utf-8")
    with pytest.raises(train_temporal.TemporalTrainingError):
        train_temporal._exclusive_bundle([(report, b"new\n"), (manifest, b"{}\n")], root=blocked_root)
    assert not (blocked_root / report).exists()
    assert occupied.read_text(encoding="utf-8") == "occupied\n"


def test_failure_manifest_has_no_replacement(tmp_path: Path) -> None:
    train_temporal.write_failed_slot(
        "P0", 1729, error=train_temporal.TemporalTrainingError("synthetic failure"), root=tmp_path
    )
    manifest_path = tmp_path / "reports/closure_v2/02_models/P0/seed_1729/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["replacement_used"] is False
    assert manifest["resume_used"] is False


def test_family_summary_requires_exact_dvc_pointer(tmp_path: Path) -> None:
    artifact = Path("models/closure_v2/P0/seed_1729/model.pt")
    physical = tmp_path / artifact
    physical.parent.mkdir(parents=True)
    physical.write_bytes(b"sealed-model")
    pointer = physical.with_suffix(".pt.dvc")
    pointer.write_text(
        "outs:\n"
        f"- md5: {train_temporal.md5_file(physical)}\n"
        f"  size: {physical.stat().st_size}\n"
        "  hash: md5\n"
        "  path: model.pt\n",
        encoding="utf-8",
    )
    record = train_temporal._validate_dvc_pointer(artifact, root=tmp_path)
    assert record["artifact"]["sha256"] == train_temporal.sha256_file(physical)

    pointer.write_text(pointer.read_text(encoding="utf-8").replace("sealed-model", "drift"), encoding="utf-8")
    pointer.write_text(pointer.read_text(encoding="utf-8").replace("md5:", "md5: drift #"), encoding="utf-8")
    with pytest.raises(train_temporal.TemporalTrainingError, match="does not match"):
        train_temporal._validate_dvc_pointer(artifact, root=tmp_path)
