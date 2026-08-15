from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from src.experiments import closure_phase3_context as context


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _authority_and_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {
            "gate": "E0-U",
            "effective_authority": True,
            "sealed_batch_execution_authorized": True,
            "e0_m_authorized": True,
            "e0_u_authorized": True,
            "evaluation_authorized": True,
            "outcome_access_authorized": True,
            "writes_performed": False,
            "phase3_code_commit": "1" * 40,
        },
        {
            "schema_version": "closure_sealed_evaluation_batch_v1",
            "experiment_id": "closure_v1",
            "evaluation_refit": "forbidden",
            "one_batch_only": True,
            "model_availability": dict(context.MODEL_AVAILABILITY),
        },
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _e10_loader_payload(
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if evidence is None:
        evidence = {
            "public_tests_xml": b"tests",
            "test_report": "report",
            "openapi": {},
            "openapi_contract_report": "contract",
            "end_to_end_report": "e2e",
            "environment": {},
        }
    records = [
        {
            "path": path.as_posix(),
            "bytes": index + 1,
            "sha256": format(index + 1, "x") * 64,
        }
        for index, path in enumerate(context.EVIDENCE_SOURCE_PATHS)
    ]
    return {
        "software_evidence": evidence,
        "source_snapshot": {
            "schema_version": "closure_e10_source_bundle_snapshot_v1",
            "source_directory": context.EVIDENCE_ROOT.as_posix(),
            "file_count": 7,
            "files": records,
            "bundle_sha256": hashlib.sha256(
                context._canonical_json_bytes(records)
            ).hexdigest(),
            "directory_chain_anchored_no_follow": True,
            "single_fd_per_file": True,
            "ancestor_and_entries_recaptured": True,
            "repository_commit": "1" * 40,
        },
    }


def test_real_input_only_registries_are_exact() -> None:
    intents, history, origins = context._load_input_frames(PROJECT_ROOT)
    strata = context._load_e2_site_strata(PROJECT_ROOT, intents)
    calibrators, thresholds, cutpoints, factors = context._load_calibration(
        PROJECT_ROOT
    )
    hypotheses = context._load_hypothesis_registry(PROJECT_ROOT)
    expanded = context._build_intent_table(intents)

    assert (len(intents), len(history), len(origins)) == (4488, 53856, 4488)
    assert intents["base_input_status"].value_counts().to_dict() == {
        "ineligible": 3684,
        "eligible": 804,
    }
    assert len(strata) == 88
    assert (len(calibrators), len(thresholds), len(cutpoints), len(factors)) == (
        66,
        66,
        30,
        90,
    )
    assert len(hypotheses) == 27
    assert len(expanded) == 13464
    assert set(expanded["horizon_months"]) == {1, 2, 3}
    assert set(expanded["evaluation_cohort"]) == {"location_holdout"}
    assert set(expanded["evaluation_role"]) == {"test"}


def test_real_b2_input_only_scoring_accepts_arrow_backed_origin_values() -> None:
    _, _, origins = context._load_input_frames(PROJECT_ROOT)

    scored = context._load_b2_predictions(PROJECT_ROOT, origins)

    assert set(scored) == {("B2", seed) for seed in context.REGISTERED_SEEDS}
    assert all(value["bloom_raw"].shape == (4488, 3) for value in scored.values())


def test_real_r10_eligibility_token_reaches_temporal_slots() -> None:
    intents, history, _ = context._load_input_frames(PROJECT_ROOT)
    state = history.loc[
        :, ["source_id", "site_id", "history_year_month"]
    ].rename(columns={"history_year_month": "year_month"}).drop_duplicates()
    for column in (
        "yN", "yF", "yT", "sigma_N", "sigma_F", "sigma_T",
        "delta_yN", "delta_yF", "delta_yT",
    ):
        state[column] = 0.1

    _, a0_valid, _, a1_valid = context._sequence_tensors(
        history,
        intents,
        {seed: state for seed in context.REGISTERED_SEEDS},
    )

    assert int(a0_valid.sum()) == 804
    assert all(int(valid.sum()) == 804 for valid in a1_valid.values())


def test_adaptive_delta_is_zero_when_exact_previous_physical_month_is_absent(
    monkeypatch: Any,
) -> None:
    month_surface = pd.DataFrame(
        {
            "source_id": ["wqp", "wqp"],
            "site_id": ["site", "site"],
            "year_month": ["2021-01", "2021-02"],
            "row_present": [False, True],
            **{column: [np.nan, 1.0] for column in context.PHYSICAL_COLUMNS},
        }
    )

    monkeypatch.setattr(
        context,
        "_anfis_forward",
        lambda *args, **kwargs: (
            np.asarray([0.2, 0.8], dtype="float64"),
            np.asarray([0.1, 0.1], dtype="float64"),
        ),
    )

    states = context._adaptive_states({}, month_surface)

    assert all(state.loc[1, "delta_yN"] == 0.0 for state in states.values())


def test_context_finishes_inference_before_first_target_open(
    monkeypatch: Any,
) -> None:
    events: list[str] = []
    empty = pd.DataFrame()
    factors = pd.DataFrame()
    intents = pd.DataFrame()
    predictions = pd.DataFrame()
    targets = pd.DataFrame()

    monkeypatch.setattr(
        context, "_load_input_frames", lambda root: (empty, empty, empty)
    )
    monkeypatch.setattr(context, "_load_overlay", lambda root: ({}, empty, {}, {}))
    monkeypatch.setattr(
        context, "_validate_warmup_against_history", lambda *args: None
    )
    monkeypatch.setattr(
        context,
        "_load_calibration",
        lambda root: ({}, {}, {}, factors),
    )
    monkeypatch.setattr(context, "_load_e2_site_strata", lambda root, base: empty)
    monkeypatch.setattr(context, "_load_hypothesis_registry", lambda root: empty)
    evidence_payload = _e10_loader_payload()
    monkeypatch.setattr(
        context,
        "load_closure_e10_software_evidence",
        lambda **kwargs: evidence_payload,
    )

    def score(*args: Any, **kwargs: Any) -> tuple[dict[Any, Any], pd.DataFrame]:
        events.append("score")
        return {}, empty

    def build_intents(base: pd.DataFrame) -> pd.DataFrame:
        events.append("intent")
        return intents

    def build_predictions(*args: Any, **kwargs: Any) -> pd.DataFrame:
        events.append("prediction")
        return predictions

    def open_targets(root: Path, value: pd.DataFrame) -> pd.DataFrame:
        events.append("target_open")
        return targets

    monkeypatch.setattr(context, "_score_models_before_targets", score)
    monkeypatch.setattr(context, "_build_intent_table", build_intents)
    monkeypatch.setattr(context, "_build_prediction_surface", build_predictions)
    monkeypatch.setattr(context, "_open_target_outcomes", open_targets)
    monkeypatch.setattr(
        context,
        "_apply_target_precedence",
        lambda prediction, target: prediction,
    )
    monkeypatch.setattr(
        context, "_future_trophic_indicators", lambda root, intent, target: empty
    )
    monkeypatch.setattr(
        context, "_derive_e7_predictions", lambda prediction, intent, target: empty
    )
    monkeypatch.setattr(
        context, "_derive_e8_evaluation", lambda prediction, intent, target: empty
    )

    authority, contract = _authority_and_contract()
    monkeypatch.setattr(
        context,
        "_PREFLIGHT_ANCHORED_INPUT_RECORDS",
        context._closed_input_snapshot(evidence_payload["source_snapshot"]["files"]),
    )
    result = context.materialize_sealed_batch_context(
        authority=authority,
        sealed_batch_contract=contract,
        repo_root=PROJECT_ROOT,
        execution_id="test-execution",
    )

    assert events == ["score", "intent", "prediction", "target_open"]
    assert set(result["tables"]) == context.EXPECTED_CONTEXT_TABLES
    assert result["stage_results"] == {}


def test_anchored_reader_rejects_leaf_and_parent_symlinks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "real").mkdir(parents=True)
    (repo / "real" / "payload.json").write_text('{"ok":true}\n', encoding="utf-8")
    (repo / "leaf.json").symlink_to(repo / "real" / "payload.json")
    (repo / "linked_parent").symlink_to(repo / "real", target_is_directory=True)

    with pytest.raises(
        context.ClosurePhase3ContextError,
        match="cannot be opened without following names",
    ):
        context._load_json(repo, Path("leaf.json"))
    with pytest.raises(
        context.ClosurePhase3ContextError,
        match="cannot be opened without following names",
    ):
        context._load_json(repo, Path("linked_parent/payload.json"))


def test_anchored_parquet_decode_recaptures_named_inode(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    relative = Path("sealed.parquet")
    path = repo / relative
    pd.DataFrame({"value": [1, 2]}).to_parquet(path, index=False)
    expected_sha256 = _sha256(path)
    real_read_parquet = pd.read_parquet
    decoded_from_stream = False

    def replacing_decoder(source: Any, *args: Any, **kwargs: Any) -> pd.DataFrame:
        nonlocal decoded_from_stream
        decoded_from_stream = hasattr(source, "read") and not isinstance(source, Path)
        path.rename(repo / "original.parquet")
        pd.DataFrame({"value": [99]}).to_parquet(path, index=False)
        return real_read_parquet(source, *args, **kwargs)

    monkeypatch.setattr(context.pd, "read_parquet", replacing_decoder)

    with pytest.raises(
        context.ClosurePhase3ContextError,
        match="changed during anchored read",
    ):
        context._read_parquet_anchored(
            repo,
            relative,
            label="synthetic target surrogate",
            expected_sha256=expected_sha256,
        )
    assert decoded_from_stream is True


def test_anchored_reader_recaptures_renamed_ancestor(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    parent = repo / "sealed_parent"
    parent.mkdir(parents=True)
    relative = Path("sealed_parent/payload.json")
    (repo / relative).write_text('{"version":1}\n', encoding="utf-8")

    with pytest.raises(
        context.ClosurePhase3ContextError,
        match="ancestor changed during anchored read",
    ):
        with context._anchored_regular_stream(
            repo,
            relative,
            label="synthetic ancestor",
        ) as (stream, _):
            assert json.loads(stream.read().decode("utf-8")) == {"version": 1}
            parent.rename(repo / "original_parent")
            parent.mkdir()
            (repo / relative).write_text('{"version":2}\n', encoding="utf-8")


def test_anchored_reader_recaptures_replaced_repository_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    relative = Path("payload.json")
    (repo / relative).write_text('{"version":1}\n', encoding="utf-8")

    with pytest.raises(
        context.ClosurePhase3ContextError,
        match="repository root changed during anchored read",
    ):
        with context._anchored_regular_stream(
            repo,
            relative,
            label="synthetic root",
        ) as (stream, _):
            assert json.loads(stream.read().decode("utf-8")) == {"version": 1}
            repo.rename(tmp_path / "original_repo")
            repo.mkdir()
            (repo / relative).write_text('{"version":2}\n', encoding="utf-8")


def test_warmup_rows_are_bound_to_r10_identity_calendar_and_summary() -> None:
    history_rows: list[dict[str, Any]] = []
    warmup_rows: list[dict[str, Any]] = []
    raw_physical = tuple(
        column for column in context.PHYSICAL_COLUMNS if column not in context.SEASON_COLUMNS
    )
    annual = 2.0 * np.pi * 11.0 / 12.0
    calendar = {
        "season_sin_annual": np.sin(annual),
        "season_cos_annual": np.cos(annual),
        "season_sin_semiannual": np.sin(2.0 * annual),
        "season_cos_semiannual": np.cos(2.0 * annual),
    }
    first_records: list[dict[str, str]] = []
    for index in range(88):
        site_id = f"site-{index:03d}"
        group_id = f"group-{index:03d}"
        history_rows.append(
            {
                "source_id": "wqp",
                "site_id": site_id,
                "holdout_group_id": group_id,
                "history_year_month": "2021-01",
            }
        )
        present = index % 2 == 0
        warmup_rows.append(
            {
                "source_id": "wqp",
                "site_id": site_id,
                "year_month": "2020-12",
                "row_present": present,
                **{
                    column: float(index) if present else np.nan
                    for column in raw_physical
                },
                **calendar,
            }
        )
        first_records.append(
            {
                "source_id": "wqp",
                "site_id": site_id,
                "holdout_group_id": group_id,
                "first_history_year_month": "2021-01",
                "warmup_year_month": "2020-12",
            }
        )
    warmup = pd.DataFrame(warmup_rows).loc[
        :, ["source_id", "site_id", "year_month", "row_present", *context.PHYSICAL_COLUMNS]
    ]
    summary = {
        "site_count": 88,
        "row_count": 88,
        "row_present_count": 44,
        "row_missing_count": 44,
        "source_ids": ["wqp"],
        "assignment_roles": ["internal_holdout"],
        "holdout_group_count": 88,
        "first_history_months_sha256": hashlib.sha256(
            context._canonical_json_bytes(first_records)[:-1]
        ).hexdigest(),
        "physical_missing_counts": {
            column: 44 for column in raw_physical
        },
        "calendar_missing_counts": {
            column: 0 for column in context.SEASON_COLUMNS
        },
    }
    history = pd.DataFrame(history_rows)

    context._validate_warmup_against_history(warmup, history, summary)

    forged = warmup.copy()
    forged.loc[0, "season_cos_annual"] = 0.0
    with pytest.raises(context.ClosurePhase3ContextError, match="calendar derivation"):
        context._validate_warmup_against_history(forged, history, summary)

    wrong_site = warmup.copy()
    wrong_site.loc[0, "site_id"] = "foreign-site"
    with pytest.raises(context.ClosurePhase3ContextError, match="keys do not match"):
        context._validate_warmup_against_history(wrong_site, history, summary)


def test_overlay_npz_and_warmup_decode_from_authenticated_streams(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = tmp_path / "repo"
    weights_relative = Path("data/runtime_weights.npz")
    warmup_relative = Path("data/warmup.parquet")
    manifest_relative = Path("reports/overlay.json")
    for relative in (weights_relative, warmup_relative, manifest_relative):
        (repo / relative).parent.mkdir(parents=True, exist_ok=True)

    weights = np.asarray([0.25, 0.75], dtype="float64")
    npy_buffer = io.BytesIO()
    np.lib.format.write_array(npy_buffer, weights, allow_pickle=False)
    array_record = {
        "npz_key": "synthetic_weights",
        "dtype": weights.dtype.str,
        "shape": list(weights.shape),
        "element_count": int(weights.size),
        "data_sha256": hashlib.sha256(weights.tobytes(order="C")).hexdigest(),
        "npy_sha256": hashlib.sha256(npy_buffer.getvalue()).hexdigest(),
    }
    internal = {
        "format_version": "synthetic_npz_v1",
        "key_dialect": {"synthetic": True},
        "checkpoint_count": 0,
        "state_dict_array_count": 1,
        "array_keys": ["synthetic_weights"],
        "arrays": [array_record],
        "checkpoints": [],
    }
    internal_payload = context._canonical_json_bytes(internal)[:-1]
    np.savez(
        repo / weights_relative,
        __manifest_json__=np.frombuffer(internal_payload, dtype="uint8"),
        synthetic_weights=weights,
    )
    pd.DataFrame(
        {
            "source_id": ["wqp"] * 88,
            "site_id": [f"site-{index:03d}" for index in range(88)],
        }
    ).to_parquet(repo / warmup_relative, index=False)
    cache_dir = repo / "dvc-cache"
    cache_dir.mkdir()
    for index, relative in enumerate((weights_relative, warmup_relative)):
        os.link(repo / relative, cache_dir / f"object-{index}")
        (repo / relative).chmod(0o444)
        assert (repo / relative).stat().st_nlink == 2
    binding_records = [
        {
            "path": relative.as_posix(),
            "bytes": (repo / relative).stat().st_size,
            "sha256": _sha256(repo / relative),
        }
        for relative in (weights_relative, warmup_relative)
    ]
    output_records = [
        {
            **binding_records[0],
            "archive_keys": ["__manifest_json__", "synthetic_weights"],
        },
        {
            **binding_records[1],
            "row_count": 88,
            "site_count": 88,
            "columns": ["source_id", "site_id"],
        },
    ]
    numpy_export = {
        "format_version": internal["format_version"],
        "key_dialect": internal["key_dialect"],
        "checkpoint_count": 0,
        "state_dict_array_count": 1,
        "archive_array_count": 2,
        "archive_keys": ["__manifest_json__", "synthetic_weights"],
        "arrays": [array_record],
        "checkpoints": [],
        "internal_manifest_key": "__manifest_json__",
        "internal_manifest_encoding": "uint8_utf8_canonical_json",
        "internal_manifest_bytes": len(internal_payload),
        "internal_manifest_sha256": hashlib.sha256(internal_payload).hexdigest(),
    }
    (repo / manifest_relative).write_text(
        json.dumps(
            {
                "physical_outputs": output_records,
                "numpy_export": numpy_export,
                "warmup": {},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(context, "WEIGHTS_PATH", weights_relative)
    monkeypatch.setattr(context, "WARMUP_PATH", warmup_relative)
    monkeypatch.setattr(context, "OVERLAY_MANIFEST_PATH", manifest_relative)
    real_np_load = np.load
    real_read_parquet = pd.read_parquet
    observed = {"npz_stream": False, "parquet_stream": False}

    def checked_np_load(source: Any, *args: Any, **kwargs: Any) -> Any:
        observed["npz_stream"] = hasattr(source, "read") and not isinstance(source, Path)
        return real_np_load(source, *args, **kwargs)

    def checked_read_parquet(source: Any, *args: Any, **kwargs: Any) -> pd.DataFrame:
        observed["parquet_stream"] = hasattr(source, "read") and not isinstance(source, Path)
        return real_read_parquet(source, *args, **kwargs)

    monkeypatch.setattr(context.np, "load", checked_np_load)
    monkeypatch.setattr(context.pd, "read_parquet", checked_read_parquet)

    arrays, warmup, overlay_record, warmup_summary = context._load_overlay(repo)

    assert observed == {"npz_stream": True, "parquet_stream": True}
    assert arrays["synthetic_weights"].tolist() == [0.25, 0.75]
    assert len(warmup) == 88
    assert warmup_summary == {}
    assert overlay_record == {
        "manifest": {
            "path": manifest_relative.as_posix(),
            "bytes": (repo / manifest_relative).stat().st_size,
            "sha256": _sha256(repo / manifest_relative),
        },
        "physical_outputs": binding_records,
    }
    (repo / weights_relative).chmod(0o600)
    with pytest.raises(
        context.ClosurePhase3ContextError,
        match="not one anchored regular file",
    ):
        context._load_overlay(repo)


def test_target_and_panel_readers_preserve_anchored_digest_contract(
    monkeypatch: Any,
) -> None:
    intents = pd.DataFrame(
        {
            "source_id": ["wqp"],
            "site_id": ["site-1"],
            "holdout_group_id": ["holdout-1"],
            "common_origin_id": ["origin-1"],
            "origin_year_month": ["2021-12"],
            "target_year_month": ["2022-01"],
            "horizon_months": [1],
            "evaluation_cohort": ["location_holdout"],
            "evaluation_role": ["test"],
        }
    )
    physical_target = pd.DataFrame(
        {
            "source_id": ["wqp"],
            "site_id": ["site-1"],
            "origin_year_month": ["2021-12"],
            "target_year_month": ["2022-01"],
            "horizon_months": [1],
            "target_month_exists": [True],
            "has_target": [True],
            "future_chlorophyll_a_ugL": [40.0],
            "bloom_h": [1.0],
            "target_risk_chla_h": [0.8],
            "target_trophic_state_h": ["eutrophic"],
        }
    )
    physical_panel = pd.DataFrame(
        {
            "source_id": ["wqp"],
            "site_id": ["site-1"],
            "year_month": ["2022-01"],
            "mean_TP_ugL": [20.0],
            "mean_secchi_depth_m": [1.5],
        }
    )
    calls: list[tuple[Path, str | None]] = []

    def anchored_reader(
        root: Path,
        relative_path: Path,
        **kwargs: Any,
    ) -> pd.DataFrame:
        calls.append((relative_path, kwargs.get("expected_sha256")))
        if relative_path == context.TARGET_PATH:
            return physical_target.copy()
        if relative_path == context.PANEL_PATH:
            return physical_panel.copy()
        raise AssertionError(relative_path)

    monkeypatch.setattr(context, "_read_parquet_anchored", anchored_reader)

    targets = context._open_target_outcomes(PROJECT_ROOT, intents)
    indicators = context._future_trophic_indicators(PROJECT_ROOT, intents, targets)

    assert calls == [
        (context.TARGET_PATH, context.TARGET_SHA256),
        (context.PANEL_PATH, context.PANEL_SHA256),
    ]
    assert targets.loc[0, "target_status"] == "available"
    assert indicators.loc[0, "future_chlorophyll_a_ugL"] == 40.0


def test_input_preflight_scores_without_target_panel_or_writes(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    site_ids = np.asarray([f"site-{index % 88:03d}" for index in range(4488)])
    statuses = np.asarray(["eligible"] * 804 + ["ineligible"] * 3684)
    base = pd.DataFrame(
        {
            "source_id": ["wqp"] * 4488,
            "site_id": site_ids,
            "base_input_status": statuses,
        }
    )
    history = pd.DataFrame(index=range(53856))
    origins = pd.DataFrame(index=range(4488))
    warmup = pd.DataFrame(index=range(88))
    factors = pd.DataFrame(index=range(90))
    strata = pd.DataFrame(index=range(88))
    hypotheses = pd.DataFrame(index=range(27))
    expanded = pd.DataFrame(index=range(13464))
    predictions = pd.DataFrame(index=range(673200))
    evidence = {
        "public_tests_xml": b"tests",
        "test_report": "report",
        "openapi": {},
        "openapi_contract_report": "contract",
        "end_to_end_report": "e2e",
        "environment": {},
    }
    evidence_payload = _e10_loader_payload(evidence)
    events: list[str] = []

    monkeypatch.setattr(
        context,
        "_load_input_frames",
        lambda root: (base, history, origins),
    )
    overlay_record = {
        "manifest": {
            "path": context.OVERLAY_MANIFEST_PATH.as_posix(),
            "bytes": 101,
            "sha256": "a" * 64,
        },
        "physical_outputs": [
            {
                "path": context.WEIGHTS_PATH.as_posix(),
                "bytes": 202,
                "sha256": "b" * 64,
            },
            {
                "path": context.WARMUP_PATH.as_posix(),
                "bytes": 303,
                "sha256": "c" * 64,
            },
        ],
    }
    monkeypatch.setattr(
        context,
        "_load_overlay",
        lambda root: (
            {"one": np.asarray([1.0]), "two": np.asarray([2.0])},
            warmup,
            overlay_record,
            {},
        ),
    )
    monkeypatch.setattr(
        context, "_validate_warmup_against_history", lambda *args: None
    )
    monkeypatch.setattr(
        context,
        "_load_calibration",
        lambda root: (
            {index: {} for index in range(66)},
            {index: 0.5 for index in range(66)},
            {index: (0.1, 0.2, 0.3) for index in range(30)},
            factors,
        ),
    )
    monkeypatch.setattr(context, "_load_e2_site_strata", lambda root, value: strata)
    monkeypatch.setattr(context, "_load_hypothesis_registry", lambda root: hypotheses)

    def load_evidence(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["require_git_publication"] is True
        assert kwargs["include_source_snapshot"] is True
        return evidence_payload

    def score(*args: Any, **kwargs: Any) -> tuple[dict[int, Any], pd.DataFrame]:
        events.append("score")
        return {index: {} for index in range(28)}, pd.DataFrame()

    def build_intents(value: pd.DataFrame) -> pd.DataFrame:
        events.append("intent")
        return expanded

    def build_predictions(*args: Any, **kwargs: Any) -> pd.DataFrame:
        events.append("prediction")
        return predictions

    monkeypatch.setattr(context, "load_closure_e10_software_evidence", load_evidence)
    monkeypatch.setattr(context, "_score_models_before_targets", score)
    monkeypatch.setattr(context, "_build_intent_table", build_intents)
    monkeypatch.setattr(context, "_build_prediction_surface", build_predictions)
    monkeypatch.setattr(
        context,
        "_open_target_outcomes",
        lambda *args, **kwargs: pytest.fail("preflight opened targets"),
    )
    monkeypatch.setattr(
        context,
        "_future_trophic_indicators",
        lambda *args, **kwargs: pytest.fail("preflight opened panel"),
    )
    authority, contract = _authority_and_contract()
    before = tuple(tmp_path.rglob("*"))

    diagnosis = context.preflight_sealed_phase3_context_inputs(
        authority,
        contract,
        tmp_path,
    )

    assert tuple(tmp_path.rglob("*")) == before
    assert events == ["score", "intent", "prediction"]
    assert diagnosis == {
        "status": "sealed_phase3_context_inputs_ready",
        "gate": "E0-U",
        "input_only": True,
        "outcome_access_performed": False,
        "writes_performed": False,
        "refit_performed": False,
        "snapshot_reuse_authorized": False,
        "post_append_revalidation_required": True,
        "anchored_input_read_count": 7,
        "input_snapshot_sha256": context._input_snapshot_sha256(
            context._closed_input_snapshot(
                evidence_payload["source_snapshot"]["files"]
            )
        ),
        "phase3_overlay_record": overlay_record,
        "holdout_site_count": 88,
        "origin_count": 4488,
        "history_row_count": 53856,
        "origin_feature_row_count": 4488,
        "eligible_origin_count": 804,
        "ineligible_origin_count": 3684,
        "expanded_intent_count": 13464,
        "pretarget_prediction_count": 673200,
        "overlay_array_count": 2,
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


def test_builder_rejects_complete_input_replacement_across_outcome_log(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    relative = Path("sealed_input.json")
    path = tmp_path / relative
    path.write_text('{"version":1}\n', encoding="utf-8")
    before = (
        (
            relative.as_posix(),
            path.stat().st_size,
            _sha256(path),
        ),
    )
    path.write_text('{"version":2}\n', encoding="utf-8")

    def read_replaced_input(**kwargs: Any) -> dict[str, Any]:
        context._load_json(kwargs["repo_root"], relative)
        return {}

    monkeypatch.setattr(context, "_PREFLIGHT_ANCHORED_INPUT_RECORDS", before)
    monkeypatch.setattr(context, "_ACTIVE_ANCHORED_INPUT_RECORDS", None)
    monkeypatch.setattr(context, "_materialize_pretarget_context", read_replaced_input)
    monkeypatch.setattr(
        context,
        "_open_target_outcomes",
        lambda *args, **kwargs: pytest.fail("builder opened targets after input drift"),
    )
    authority, contract = _authority_and_contract()

    with pytest.raises(
        context.ClosurePhase3ContextError,
        match="changed across the durable outcome log",
    ):
        context.materialize_sealed_batch_context(
            authority=authority,
            sealed_batch_contract=contract,
            repo_root=tmp_path,
            execution_id="synthetic-cross-log-drift",
        )
