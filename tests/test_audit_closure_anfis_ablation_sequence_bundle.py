from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
import pytest

from src.experiments import audit_closure_anfis_ablation_sequence_bundle as auditor
from src.experiments import build_closure_anfis_ablation_sequences as builder


def _common() -> pd.DataFrame:
    base = {
        "surface_id": builder.SURFACE_ID,
        "source_id": "wqp",
        "site_id": "site-1",
        "common_origin_id": "origin-1",
        "holdout_group_id": "group-1",
        "assignment_role": "development",
        "time_role": "training",
        "origin_year_month": "2021-12",
        "history_start_year_month": "2021-01",
        "history_end_year_month": "2021-12",
        "history_length_months": 12,
    }
    return pd.DataFrame([{**base, "horizon_months": horizon} for horizon in (1, 2, 3)])


def _panel() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, month in enumerate(pd.period_range("2021-01", "2021-12", freq="M")):
        row: dict[str, Any] = {
            "source_id": "wqp",
            "site_id": "site-1",
            "year_month": str(month),
        }
        for feature_index, (mean_column, n_obs_column) in enumerate(
            zip(builder.RAW_MEAN_COLUMNS, builder.RAW_N_OBS_COLUMNS, strict=True)
        ):
            row[mean_column] = float(100 * feature_index + index)
            row[n_obs_column] = 1
        rows.append(row)
    return pd.DataFrame(rows)


def _authority(*, prefix_count: int = 1) -> dict[str, Any]:
    authority: dict[str, Any] = {
        "gate": "E0-MS",
        "status": "effective_preflight_passed",
        "sequence_bundle_audit_authorized": False,
        "temporal_fit_authorized": False,
        "target_access_authorized": False,
        "calibration_authorized": False,
        "metrics_authorized": False,
        "rollout_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "scientific_network_authorized": False,
        "outcome_access_authorized": False,
        "future_outcomes_accessed": False,
        "authorized_model_id": "A0",
        "authorized_base_seed": None,
        "completed_prefix_count": prefix_count,
        "slot_creation_prefix_count": 0,
        "audit_current_unpublished": True,
        "h_patch_head": "h" * 40,
        "p_patch_head": "p" * 40,
        "h_components_sha256": "1" * 64,
        "physical_inputs_sha256": "2" * 64,
        "builder_sha256": "3" * 64,
        "auditor_sha256": "4" * 64,
    }
    for key in ("runtime", "lock", "companion"):
        authority[key] = {
            "path": f"reports/{key}.json",
            "role": key,
            "bytes": 1,
            "sha256": "5" * 64,
        }
    return authority


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _prepare_synthetic_a0_bundle(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    completed_prefix_count: int = 1,
) -> tuple[builder.BundlePaths, dict[str, Any]]:
    common = _common()
    panel = _panel()

    common_path = repo_root / builder.DEFAULT_COMMON_ORIGINS
    panel_path = repo_root / builder.DEFAULT_PANEL
    common_path.parent.mkdir(parents=True, exist_ok=True)
    panel_path.parent.mkdir(parents=True, exist_ok=True)
    common.to_parquet(common_path, index=False)
    panel.to_parquet(panel_path, index=False)
    _write(repo_root / builder.DEFAULT_COMMON_POINTER, b"synthetic common pointer\n")
    _write(repo_root / builder.DEFAULT_COMMON_MANIFEST, b"{}\n")
    _write(repo_root / builder.DEFAULT_PANEL_POINTER, b"synthetic panel pointer\n")
    _write(repo_root / auditor.BUILDER_PATH, b"# synthetic pinned builder\n")

    monkeypatch.setattr(auditor, "EXPECTED_COMMON_ROWS", 3)
    monkeypatch.setattr(auditor, "EXPECTED_INTENT_ORIGINS", 1)
    monkeypatch.setattr(auditor, "EXPECTED_DEVELOPMENT_LOCATIONS", 1)
    monkeypatch.setattr(auditor, "EXPECTED_ROLE_COUNTS", {"training": 1})
    authority = _authority(prefix_count=completed_prefix_count)
    monkeypatch.setattr(auditor, "_require_audit_authority", lambda *args, **kwargs: authority)
    monkeypatch.setattr(auditor, "_load_runtime_after_gate", lambda *args, **kwargs: {})

    frame, build_audit = builder.build_anfis_ablation_sequences(
        common,
        panel,
        model_id="A0",
        base_seed=None,
        expected_common_rows=3,
        expected_intent_origins=1,
        expected_development_locations=1,
        expected_source_ids={"wqp"},
        expected_role_counts={"training": 1},
    )
    table = builder.sequence_arrow_table(frame, model_id="A0")
    paths = builder.bundle_paths("A0", None, repo_root=repo_root)
    paths.parquet.parent.mkdir(parents=True, exist_ok=True)
    paths.summary.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, paths.parquet, compression="zstd", use_dictionary=False)
    _write(paths.summary, builder._summary_bytes(frame))

    _, _, _, input_records, _ = builder._read_input_frames(
        model_id="A0",
        base_seed=None,
        repo_root=repo_root,
    )
    source_record = builder._stable_file_record(repo_root / auditor.BUILDER_PATH, repo_root=repo_root)
    sequence_record = builder._stable_file_record(paths.parquet, repo_root=repo_root)
    summary_record = builder._stable_file_record(paths.summary, repo_root=repo_root)
    build_authority = builder._authority_manifest_binding(authority)
    build_authority["completed_prefix_count"] = 0
    manifest = builder._manifest_payload(
        model_id="A0",
        base_seed=None,
        audit=build_audit,
        authority=build_authority,
        inputs=input_records,
        source_code=[source_record],
        outputs=[sequence_record, summary_record],
    )
    _write(paths.manifest, builder._json_bytes(manifest))
    return paths, authority


def test_strict_json_rejects_duplicate_keys_and_nonfinite_values() -> None:
    with pytest.raises(auditor.AnfisAblationSequenceAuditError, match="duplicate"):
        auditor._strict_json(b'{"a":1,"a":2}\n', label="fixture")
    with pytest.raises(auditor.AnfisAblationSequenceAuditError, match="non-finite"):
        auditor._strict_json(b'{"a":NaN}\n', label="fixture")


def test_pointer_validation_accepts_absent_and_exact_dvc_payload() -> None:
    sequence = b"parquet bytes"
    absent = auditor._validate_pointer(
        None,
        None,
        sequence_payload=sequence,
        sequence_name="raw_no_current.parquet",
    )
    assert absent["registration_state"] == "pre_dvc"

    md5 = hashlib.md5(sequence, usedforsecurity=False).hexdigest()
    pointer = (
        "outs:\n"
        f"- md5: {md5}\n"
        f"  size: {len(sequence)}\n"
        "  hash: md5\n"
        "  path: raw_no_current.parquet\n"
    ).encode("utf-8")
    present = auditor._validate_pointer(
        pointer,
        {"path": "pointer", "bytes": len(pointer), "sha256": "a" * 64},
        sequence_payload=sequence,
        sequence_name="raw_no_current.parquet",
    )
    assert present["registration_state"] == "post_dvc"
    assert present["pointer_payload_binding_verified"] is True

    with pytest.raises(auditor.AnfisAblationSequenceAuditError, match="does not bind"):
        auditor._validate_pointer(
            pointer,
            {},
            sequence_payload=b"changed",
            sequence_name="raw_no_current.parquet",
        )


def test_namespace_requires_three_finals_and_forbids_temps_or_guard(tmp_path: Path) -> None:
    paths = builder.bundle_paths("A0", None, repo_root=tmp_path)
    for final in paths.finals:
        _write(final, b"x")
    snapshot = auditor._path_snapshot(auditor._namespace_paths(paths))
    assert auditor._validate_namespace(snapshot, paths) is False

    _write(paths.guard, b"")
    snapshot = auditor._path_snapshot(auditor._namespace_paths(paths))
    with pytest.raises(auditor.AnfisAblationSequenceAuditError, match="residue"):
        auditor._validate_namespace(snapshot, paths)


def test_full_synthetic_a0_audit_passes_pre_dvc_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, authority = _prepare_synthetic_a0_bundle(
        tmp_path,
        monkeypatch,
        completed_prefix_count=6,
    )
    before = auditor._path_snapshot(auditor._namespace_paths(paths))

    result = auditor.audit_anfis_ablation_sequence_bundle(
        model_id="A0",
        base_seed=None,
        repo_root=tmp_path,
        authority=authority,
    )

    assert result["status"] == "passed"
    assert result["counts"]["common_rows"] == 3
    assert result["counts"]["intent_origins"] == 1
    assert result["dvc_registration"]["registration_state"] == "pre_dvc"
    assert result["writes_performed"] is False
    assert result["targets_read"] is False
    assert result["scientific_network_egress"] is False
    assert auditor._path_snapshot(auditor._namespace_paths(paths)) == before


def test_full_synthetic_a0_audit_accepts_exact_post_dvc_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, authority = _prepare_synthetic_a0_bundle(
        tmp_path,
        monkeypatch,
        completed_prefix_count=6,
    )
    sequence = paths.parquet.read_bytes()
    md5 = hashlib.md5(sequence, usedforsecurity=False).hexdigest()
    _write(
        paths.pointer,
        (
            "outs:\n"
            f"- md5: {md5}\n"
            f"  size: {len(sequence)}\n"
            "  hash: md5\n"
            f"  path: {paths.parquet.name}\n"
        ).encode("utf-8"),
    )

    result = auditor.audit_anfis_ablation_sequence_bundle(
        model_id="A0",
        base_seed=None,
        repo_root=tmp_path,
        authority=authority,
    )
    assert result["dvc_registration"]["registration_state"] == "post_dvc"
    assert result["dvc_registration"]["pointer_payload_binding_verified"] is True
    assert result["status"] == "passed"


def test_full_audit_detects_summary_and_sequence_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, authority = _prepare_synthetic_a0_bundle(tmp_path, monkeypatch)
    paths.summary.write_bytes(b"tampered\n")
    with pytest.raises(auditor.AnfisAblationSequenceAuditError, match="summary"):
        auditor.audit_anfis_ablation_sequence_bundle(
            model_id="A0",
            base_seed=None,
            repo_root=tmp_path,
            authority=authority,
        )


def test_full_audit_detects_manifest_authority_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, authority = _prepare_synthetic_a0_bundle(tmp_path, monkeypatch)
    manifest = auditor._strict_json(paths.manifest.read_bytes(), label="fixture")
    manifest["authority"]["builder_sha256"] = "0" * 64
    paths.manifest.write_bytes(builder._json_bytes(manifest))
    with pytest.raises(auditor.AnfisAblationSequenceAuditError, match="manifest"):
        auditor.audit_anfis_ablation_sequence_bundle(
            model_id="A0",
            base_seed=None,
            repo_root=tmp_path,
            authority=authority,
        )


def test_audit_gate_is_first_even_for_invalid_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class GateReached(RuntimeError):
        pass

    def gate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise GateReached

    monkeypatch.setattr(auditor, "_require_audit_authority", gate)
    with pytest.raises(GateReached):
        auditor.audit_anfis_ablation_sequence_bundle(
            model_id="invalid",
            base_seed=None,
            repo_root=tmp_path,
            authority={"bypass": True},
        )


def test_audit_authority_accepts_any_target_inside_completed_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import closure_anfis_ablation_sequence_development_patch as contract

    authority = _authority(prefix_count=6)
    monkeypatch.setattr(
        contract,
        "load_effective_anfis_ablation_sequence_development_authority",
        lambda *args, **kwargs: authority,
    )
    assert auditor._require_audit_authority(
        tmp_path,
        model_id="A0",
        base_seed=None,
    ) == authority

    authority["completed_prefix_count"] = 0
    with pytest.raises(auditor.AnfisAblationSequenceAuditError, match="target binding"):
        auditor._require_audit_authority(tmp_path, model_id="A0", base_seed=None)
