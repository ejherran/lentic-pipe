from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.experiments import build_closure_anfis_ablation_sequences as builder


def _common_row(
    *,
    origin_id: str = "origin-1",
    site_id: str = "site-1",
    origin: str = "2021-12",
    role: str = "training",
) -> dict[str, Any]:
    period_value = pd.Period(origin, freq="M")
    assert isinstance(period_value, pd.Period)
    period = period_value
    return {
        "surface_id": builder.SURFACE_ID,
        "source_id": "wqp",
        "site_id": site_id,
        "common_origin_id": origin_id,
        "holdout_group_id": f"group-{site_id}",
        "assignment_role": "development",
        "time_role": role,
        "origin_year_month": origin,
        "history_start_year_month": str(period - 11),
        "history_end_year_month": origin,
        "history_length_months": 12,
    }


def _common(**kwargs: Any) -> pd.DataFrame:
    base = _common_row(**kwargs)
    return pd.DataFrame([{**base, "horizon_months": horizon} for horizon in (1, 2, 3)])


def _panel(*, site_id: str = "site-1", origin: str = "2021-12") -> pd.DataFrame:
    period_value = pd.Period(origin, freq="M")
    assert isinstance(period_value, pd.Period)
    period = period_value
    rows: list[dict[str, Any]] = []
    for index, month in enumerate((period - offset for offset in range(11, -1, -1))):
        row: dict[str, Any] = {
            "source_id": "wqp",
            "site_id": site_id,
            "year_month": str(month),
        }
        for feature_index, (mean_column, n_obs_column) in enumerate(
            zip(builder.RAW_MEAN_COLUMNS, builder.RAW_N_OBS_COLUMNS, strict=True)
        ):
            row[mean_column] = float(100 * feature_index + index + 1)
            row[n_obs_column] = 1
        rows.append(row)
    return pd.DataFrame(rows)


def _state(*, site_id: str = "site-1", origin: str = "2021-12") -> pd.DataFrame:
    period_value = pd.Period(origin, freq="M")
    assert isinstance(period_value, pd.Period)
    period = period_value
    rows: list[dict[str, Any]] = []
    for index, month in enumerate((period - offset for offset in range(11, -1, -1))):
        row: dict[str, Any] = {
            "source_id": "wqp",
            "site_id": site_id,
            "year_month": str(month),
        }
        for state_index, source_column in enumerate(
            builder.ADAPTIVE_STATE_SOURCE_MAPPING.values()
        ):
            row[source_column] = float(10 * state_index + index)
        rows.append(row)
    return pd.DataFrame(rows)


def _build_a0(
    common: pd.DataFrame | None = None,
    panel: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, builder.SequenceBuildAudit]:
    return builder.build_anfis_ablation_sequences(
        _common() if common is None else common,
        _panel() if panel is None else panel,
        model_id="A0",
        base_seed=None,
    )


def _authority(*, model_id: str = "A0", base_seed: int | None = None) -> dict[str, Any]:
    prefix_count = builder.BUNDLE_SLOTS.index((model_id, base_seed))
    authority: dict[str, Any] = {
        "gate": "E0-MS",
        "status": "effective_preflight_passed",
        "a0_sequence_build_authorized": True,
        "a1_sequence_build_authorized": True,
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
        "authorized_model_id": model_id,
        "authorized_base_seed": base_seed,
        "completed_prefix_count": prefix_count,
        "slot_creation_prefix_count": prefix_count,
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


def test_a0_uses_exact_e6_order_masks_transport_zero_and_seasonality() -> None:
    panel = _panel()
    panel.loc[0, "mean_TP_ugL"] = np.nan
    panel.loc[1, "n_obs_TN_ugL"] = 0
    frame, audit = _build_a0(panel=panel)

    assert frame.columns.tolist() == list(builder.IDENTITY_COLUMNS + builder.A0_INPUT_COLUMNS)
    assert frame.loc[0, "base_seed"] is None
    assert frame.loc[0, "upstream_state_seed"] is None
    assert frame.loc[0, "sequence_status"] == "success"
    assert frame.loc[0, "x_mean_TP_ugL"][0] == np.float32(0.0)
    assert frame.loc[0, "mask_mean_TP_ugL"][0] == np.float32(0.0)
    assert frame.loc[0, "x_mean_TN_ugL"][1] == np.float32(0.0)
    assert frame.loc[0, "mask_mean_TN_ugL"][1] == np.float32(0.0)
    assert frame.loc[0, "mask_mean_DO_mgL"] == [np.float32(1.0)] * 12
    assert frame.loc[0, "season_sin_annual"][0] == pytest.approx(0.0, abs=1e-7)
    assert frame.loc[0, "season_cos_annual"][0] == pytest.approx(1.0, abs=1e-7)
    assert audit.observed_raw_value_counts["mean_TP_ugL"] == 11
    assert audit.masked_raw_value_counts["mean_TP_ugL"] == 1
    assert not {"evaluation_unit_id", "target_year_month", "horizon_months"}.intersection(frame)


def test_a1_adds_exact_same_seed_state_channels() -> None:
    state = _state()
    frame, _ = builder.build_anfis_ablation_sequences(
        _common(),
        _panel(),
        model_id="A1",
        base_seed=1729,
        adaptive_state=state,
    )

    assert frame.columns.tolist() == list(builder.IDENTITY_COLUMNS + builder.A1_INPUT_COLUMNS)
    assert int(frame.loc[0, "base_seed"]) == 1729
    assert int(frame.loc[0, "upstream_state_seed"]) == 1729
    for index, (output_column, source_column) in enumerate(
        builder.ADAPTIVE_STATE_SOURCE_MAPPING.items()
    ):
        assert frame.loc[0, output_column] == [
            np.float32(value) for value in state[source_column].tolist()
        ]
        assert frame.loc[0, output_column][0] == np.float32(10 * index)


@pytest.mark.parametrize(
    ("model_id", "base_seed", "panel_rows", "state_rows", "expected_status"),
    [
        ("A0", None, 11, None, "input_history_unavailable"),
        ("A1", 1729, 12, 11, "model_slot_unavailable"),
        ("A1", 1729, 12, None, "model_slot_unavailable"),
    ],
)
def test_failure_rows_are_retained_with_every_tensor_parent_null(
    model_id: str,
    base_seed: int | None,
    panel_rows: int,
    state_rows: int | None,
    expected_status: str,
) -> None:
    state = None if state_rows is None else _state().iloc[:state_rows].copy()
    frame, _ = builder.build_anfis_ablation_sequences(
        _common(),
        _panel().iloc[:panel_rows].copy(),
        model_id=model_id,
        base_seed=base_seed,
        adaptive_state=state,
    )
    assert len(frame) == 1
    assert frame.loc[0, "sequence_status"] == expected_status
    assert all(frame.loc[0, column] is None for column in builder.input_columns(model_id))

    table = builder.sequence_arrow_table(frame, model_id=model_id)
    for column in builder.input_columns(model_id):
        assert table[column].to_pylist() == [None]
        assert table.schema.field(column).nullable is True
        assert table.schema.field(column).type.value_field.nullable is False


def test_common_origin_collapse_requires_invariant_exact_h1_h3() -> None:
    common = _common()
    common.loc[1, "site_id"] = "drifted"
    with pytest.raises(builder.AnfisAblationSequenceBuildError, match="drifts across horizons"):
        builder.collapse_common_origins(common)

    missing = _common().loc[lambda frame: frame["horizon_months"].ne(2)]
    with pytest.raises(builder.AnfisAblationSequenceBuildError, match="exact h1-h3"):
        builder.collapse_common_origins(missing)


def test_rows_are_sorted_by_utf8_site_origin_and_common_id() -> None:
    common = pd.concat(
        [
            _common(origin_id="z", site_id="site-b"),
            _common(origin_id="a", site_id="site-a"),
        ],
        ignore_index=True,
    )
    panel = pd.concat([_panel(site_id="site-b"), _panel(site_id="site-a")], ignore_index=True)
    frame, _ = _build_a0(common=common, panel=panel)
    assert frame["common_origin_id"].tolist() == ["a", "z"]


def test_physical_denominator_checks_fail_closed() -> None:
    with pytest.raises(builder.AnfisAblationSequenceBuildError, match="row denominator"):
        builder.build_anfis_ablation_sequences(
            _common(),
            _panel(),
            model_id="A0",
            base_seed=None,
            expected_common_rows=29_196,
        )
    with pytest.raises(builder.AnfisAblationSequenceBuildError, match="source denominator"):
        builder.build_anfis_ablation_sequences(
            _common(),
            _panel(),
            model_id="A0",
            base_seed=None,
            expected_source_ids={"other"},
        )


def test_arrow_schema_is_exact_and_has_no_target_or_horizon_columns() -> None:
    frame, _ = _build_a0()
    table = builder.sequence_arrow_table(frame, model_id="A0")
    assert table.schema.names == list(builder.IDENTITY_COLUMNS + builder.A0_INPUT_COLUMNS)
    assert table.schema.field("base_seed").type == pa.int64()
    assert table.schema.field("history_length_months").type == pa.int16()
    for column in builder.A0_INPUT_COLUMNS:
        assert table.schema.field(column).type == pa.list_(
            pa.field("element", pa.float32(), nullable=False), 12
        )


def test_manifest_is_completed_input_only_and_completion_marker_is_last() -> None:
    frame, audit = _build_a0()
    authority = builder._authority_manifest_binding(_authority())
    payload = builder._manifest_payload(
        model_id="A0",
        base_seed=None,
        audit=audit,
        authority=authority,
        inputs=[{"path": "in", "bytes": 1, "sha256": "a" * 64}],
        source_code=[{"path": "script", "bytes": 1, "sha256": "b" * 64}],
        outputs=[{"path": "out", "bytes": 1, "sha256": "c" * 64}],
    )
    assert payload["status"] == "completed"
    assert payload["targets_read"] is False
    assert payload["tensor_contract"]["target_columns"] == []
    assert payload["horizons_months"] == [1, 2, 3]
    assert next(reversed(payload)) == "completion_marker_written_last"
    assert json.loads(builder._json_bytes(payload))["completion_marker_written_last"] is True


def test_output_transaction_rolls_back_only_its_owned_inode(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "value.bin"
    with pytest.raises(RuntimeError, match="stop"):
        with builder.OutputTransaction(tmp_path) as transaction:
            transaction.publish_bytes(b"owned", output)
            raise RuntimeError("stop")
    assert not output.exists()

    output.parent.mkdir(parents=True, exist_ok=True)
    with pytest.raises(RuntimeError, match="stop"):
        with builder.OutputTransaction(tmp_path) as transaction:
            transaction.publish_bytes(b"owned", output)
            output.unlink()
            output.write_bytes(b"foreign")
            raise RuntimeError("stop")
    assert output.read_bytes() == b"foreign"


def test_output_transaction_refuses_no_clobber(tmp_path: Path) -> None:
    output = tmp_path / "value.bin"
    output.write_bytes(b"existing")
    with pytest.raises(builder.AnfisAblationSequenceBuildError, match="overwrite"):
        with builder.OutputTransaction(tmp_path) as transaction:
            transaction.publish_bytes(b"new", output)
    assert output.read_bytes() == b"existing"


def test_parquet_reader_uses_a_pinned_file_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "input.parquet"
    pq.write_table(pa.table({"value": [1, 2]}), path)
    real_read_table = builder.pq.read_table
    seen: list[bool] = []

    def wrapped(source: Any, *args: Any, **kwargs: Any) -> pa.Table:
        seen.append(not isinstance(source, (str, Path)))
        return real_read_table(source, *args, **kwargs)

    monkeypatch.setattr(builder.pq, "read_table", wrapped)
    frame, record = builder._read_regular_parquet(
        path,
        columns=["value"],
        repo_root=tmp_path,
    )
    assert seen == [True]
    assert frame["value"].tolist() == [1, 2]
    assert record["path"] == "input.parquet"


def test_target_aware_gate_forwards_slot_and_checks_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(model_id="A1", base_seed=1729)
    from src.experiments import closure_anfis_ablation_sequence_development_patch as contract

    observed: list[tuple[str, int | None, Path]] = []

    def require(model_id: str, base_seed: int | None, *, repo_root: Path) -> dict[str, Any]:
        observed.append((model_id, base_seed, repo_root))
        return authority

    monkeypatch.setattr(contract, "require_anfis_ablation_sequence_development_authority", require)
    assert builder._require_effective_authority(
        tmp_path,
        model_id="A1",
        base_seed=1729,
    ) == authority
    assert observed == [("A1", 1729, tmp_path)]

    drifted = {**authority, "completed_prefix_count": 6}
    monkeypatch.setattr(
        contract,
        "require_anfis_ablation_sequence_development_authority",
        lambda *args, **kwargs: drifted,
    )
    with pytest.raises(builder.AnfisAblationSequenceBuildError, match="target-slot"):
        builder._require_effective_authority(tmp_path, model_id="A1", base_seed=1729)


def test_materializer_always_calls_gate_before_validation_or_injected_bypass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class GateReached(RuntimeError):
        pass

    def gate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise GateReached

    monkeypatch.setattr(builder, "_require_effective_authority", gate)
    with pytest.raises(GateReached):
        builder.materialize_anfis_ablation_sequence_bundle(
            model_id="invalid",
            base_seed=None,
            repo_root=tmp_path,
            authority={"bypass": True},
        )


def _patch_small_materializer(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], builder.BundlePaths]:
    frame, audit = _build_a0()
    authority = _authority()
    input_path = repo_root / "synthetic-input.bin"
    input_path.write_bytes(b"input")

    def stable(path: Path, *, repo_root: Path) -> dict[str, Any]:
        candidate = Path(path)
        try:
            relative = candidate.relative_to(repo_root).as_posix()
        except ValueError:
            relative = "src/experiments/build_closure_anfis_ablation_sequences.py"
        return {"path": relative, "bytes": 5, "sha256": "f" * 64}

    input_record = stable(input_path, repo_root=repo_root)
    monkeypatch.setattr(builder, "_require_effective_authority", lambda *args, **kwargs: authority)
    monkeypatch.setattr(builder, "_load_runtime_after_gate", lambda *args, **kwargs: {})
    monkeypatch.setattr(builder, "_stable_file_record", stable)
    monkeypatch.setattr(
        builder,
        "_read_input_frames",
        lambda **kwargs: (_common(), _panel(), None, [input_record], [input_path]),
    )
    monkeypatch.setattr(
        builder,
        "build_anfis_ablation_sequences",
        lambda *args, **kwargs: (frame, audit),
    )
    return authority, builder.bundle_paths("A0", None, repo_root=repo_root)


def test_guard_release_failure_rolls_back_all_three_finals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, paths = _patch_small_materializer(tmp_path, monkeypatch)
    real_release = builder._release_guard

    def release_then_fail(guard: builder.OwnedGuard) -> None:
        real_release(guard)
        raise builder.AnfisAblationSequenceBuildError("injected release failure")

    monkeypatch.setattr(builder, "_release_guard", release_then_fail)
    with pytest.raises(builder.AnfisAblationSequenceBuildError, match="release failure"):
        builder.materialize_anfis_ablation_sequence_bundle(
            model_id="A0",
            base_seed=None,
            repo_root=tmp_path,
            authority=authority,
        )
    assert all(not path.exists() for path in paths.finals)
    assert not paths.guard.exists()


def test_foreign_guard_replacement_is_preserved_while_finals_roll_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, paths = _patch_small_materializer(tmp_path, monkeypatch)
    real_release = builder._release_guard

    def replace_then_release(guard: builder.OwnedGuard) -> None:
        os.unlink(guard.path.name, dir_fd=guard.directory_descriptor)
        guard.path.write_bytes(b"foreign")
        real_release(guard)

    monkeypatch.setattr(builder, "_release_guard", replace_then_release)
    with pytest.raises(builder.AnfisAblationSequenceBuildError, match="guard cleanup"):
        builder.materialize_anfis_ablation_sequence_bundle(
            model_id="A0",
            base_seed=None,
            repo_root=tmp_path,
            authority=authority,
        )
    assert all(not path.exists() for path in paths.finals)
    assert paths.guard.read_bytes() == b"foreign"


@pytest.mark.parametrize("injected_kind", ["pointer_tmp", "outcome_log"])
def test_post_write_forbidden_side_effect_rolls_back_owned_finals_only(
    injected_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, paths = _patch_small_materializer(tmp_path, monkeypatch)
    injected = (
        Path(f"{paths.pointer.as_posix()}.tmp")
        if injected_kind == "pointer_tmp"
        else tmp_path / builder.OUTCOME_ACCESS_LOG
    )
    real_publish = builder.OutputTransaction.publish_bytes

    def publish_and_inject(
        transaction: builder.OutputTransaction,
        payload: bytes,
        path: Path,
    ) -> builder.OwnedOutput:
        owned = real_publish(transaction, payload, path)
        if path == paths.manifest:
            injected.parent.mkdir(parents=True, exist_ok=True)
            injected.write_bytes(b"foreign")
        return owned

    monkeypatch.setattr(builder.OutputTransaction, "publish_bytes", publish_and_inject)
    with pytest.raises(builder.AnfisAblationSequenceBuildError, match="Forbidden side effect"):
        builder.materialize_anfis_ablation_sequence_bundle(
            model_id="A0",
            base_seed=None,
            repo_root=tmp_path,
            authority=authority,
        )
    assert all(not path.exists() for path in paths.finals)
    assert not paths.guard.exists()
    assert injected.read_bytes() == b"foreign"


def test_bundle_paths_match_the_six_closed_namespaces(tmp_path: Path) -> None:
    a0 = builder.bundle_paths("A0", None, repo_root=tmp_path)
    assert a0.guard.relative_to(tmp_path).as_posix() == (
        "tmp/closure_v1_anfis_ablation_sequences/A0_raw_no_current.guard"
    )
    for seed in builder.REGISTERED_SEEDS:
        a1 = builder.bundle_paths("A1", seed, repo_root=tmp_path)
        assert a1.parquet.relative_to(tmp_path).as_posix().endswith(f"A1/seed_{seed}.parquet")
        assert a1.guard.relative_to(tmp_path).as_posix().endswith(f"A1_seed_{seed}.guard")
