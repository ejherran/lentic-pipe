from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest

import src.experiments.build_closure_holdout as holdout_module
from src.experiments.build_closure_holdout import (
    ASSIGNMENT_HOLDOUT,
    ASSIGNMENT_OUTPUT_COLUMNS,
    HISTORICAL_OUTCOME_READ_COLUMNS,
    PRECURSOR_READ_COLUMNS,
    HoldoutConfig,
    allocate_stratum_quotas,
    assign_holdout_locations,
    build_holdout_selection,
    build_precursor_month_status,
    coverage_band,
    load_holdout_config,
    load_and_validate_target_manifest,
    read_pre_cutoff_panel_projections,
    require_clean_worktree,
    require_tracked_clean_protocol_lock,
    series_length_band,
    validate_protocol_lock,
)


SCRIPT_PATH = Path("src/experiments/build_closure_holdout.py")
CONFIG_PATH = Path("configs/closure_v1/location_holdout.yaml")
TARGETS_PATH = Path("data/targets/monthly_targets_model_v0.parquet")
TARGET_MANIFEST_PATH = Path("data/targets/target_manifest_v0.json")


def _synthetic_frames(site_count: int = 15) -> tuple[pd.DataFrame, pd.DataFrame]:
    precursor_rows: list[dict[str, object]] = []
    outcome_rows: list[dict[str, object]] = []
    months = pd.period_range("2020-01", "2022-03", freq="M")
    for site_index in range(site_count):
        site_id = f"site-{site_index:02d}"
        for month in months:
            month_text = str(month)
            precursor_rows.append(
                {
                    "source_id": "wqp",
                    "site_id": site_id,
                    "year_month": month_text,
                    "mean_TP_ugL": 25.0 + site_index,
                    "mean_TN_ugL": None,
                    "mean_temperature_C": 18.0,
                    "mean_secchi_depth_m": None,
                    "mean_turbidity_NTU": 4.0,
                    "mean_DO_mgL": None,
                    "mean_pH": None,
                }
            )
        for origin in months:
            for horizon in (1, 2, 3):
                target = origin + horizon
                if target > months[-1]:
                    continue
                target_text = str(target)
                bloom = site_index % 2 == 0 and target_text == "2021-06"
                outcome_rows.append(
                    {
                        "source_id": "wqp",
                        "site_id": site_id,
                        "origin_year_month": str(origin),
                        "target_year_month": target_text,
                        "horizon_months": horizon,
                        "bloom_h": bloom,
                    }
                )
    return pd.DataFrame(precursor_rows), pd.DataFrame(outcome_rows)


def _canonical_assignment(
    precursor_rows: pd.DataFrame,
    outcome_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    result = build_holdout_selection(precursor_rows, outcome_rows)
    return result.assignment, result.eligible_origins, result.location_profiles


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _protocol_lock_payload(head: str) -> dict[str, object]:
    return {
        "lock_version": "closure_protocol_lock_v1",
        "status": "locked",
        "experiment_id": "closure_v1",
        "plan_version": "1.1",
        "future_outcomes_accessed": False,
        "outcome_access_definition": (
            "semantic_decoding_inspection_aggregation_or_use_of_outcome_rows"
        ),
        "lock_command_reads_complete_source_bytes_for_sha256": True,
        "lock_command_semantically_decodes_post_2021_outcomes": False,
        "holdout_assignment_created": False,
        "locked_repository": {"head": head, "worktree_status": "clean"},
        "protocol_components": [
            {
                "path": path.as_posix(),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
                "role": role,
            }
            for path, role in (
                (SCRIPT_PATH, "holdout_selector"),
                (CONFIG_PATH, "holdout_config"),
            )
        ],
        "source_artifacts": [
            {
                "path": TARGET_MANIFEST_PATH.as_posix(),
                "sha256": _sha256(TARGET_MANIFEST_PATH),
                "bytes": TARGET_MANIFEST_PATH.stat().st_size,
                "role": "target_manifest",
            }
        ],
    }


def test_assignment_is_invariant_to_input_row_order() -> None:
    precursor_rows, outcome_rows = _synthetic_frames()
    expected = build_holdout_selection(precursor_rows, outcome_rows)
    shuffled = build_holdout_selection(
        precursor_rows.sample(frac=1.0, random_state=91).reset_index(drop=True),
        outcome_rows.sample(frac=1.0, random_state=37).reset_index(drop=True),
    )

    pd.testing.assert_frame_equal(shuffled.assignment, expected.assignment)
    pd.testing.assert_frame_equal(shuffled.eligible_origins, expected.eligible_origins)
    pd.testing.assert_frame_equal(shuffled.quota_summary, expected.quota_summary)


def test_assignment_schema_and_order_match_the_locked_config() -> None:
    config, payload = load_holdout_config(CONFIG_PATH)
    result = build_holdout_selection(*_synthetic_frames())

    assert config == HoldoutConfig()
    assert payload["assignment"]["expected_output_columns"] == ASSIGNMENT_OUTPUT_COLUMNS
    assert result.assignment.columns.tolist() == ASSIGNMENT_OUTPUT_COLUMNS
    assert "rank_within_stratum" not in result.assignment
    assert "stratum_quota" not in result.assignment
    assert "eligible_origin_count" not in result.assignment


def test_holdout_config_rejects_assignment_output_schema_drift(tmp_path: Path) -> None:
    payload = holdout_module.yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["assignment"]["expected_output_columns"] = [
        *ASSIGNMENT_OUTPUT_COLUMNS,
        "rank_within_stratum",
    ]
    config_path = tmp_path / "location_holdout.yaml"
    config_path.write_text(holdout_module.yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="assignment.expected_output_columns"):
        load_holdout_config(config_path)


def test_holdout_config_rejects_post_cutoff_materialization_claim_drift(tmp_path: Path) -> None:
    payload = holdout_module.yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["information_boundary"]["post_cutoff_target_rows_materialized_to_selector_logic"] = True
    config_path = tmp_path / "location_holdout.yaml"
    config_path.write_text(holdout_module.yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="information_boundary.post_cutoff_target_rows_materialized_to_selector_logic",
    ):
        load_holdout_config(config_path)


def test_post_cutoff_changes_and_new_future_only_site_do_not_change_assignment() -> None:
    precursor_rows, outcome_rows = _synthetic_frames()
    expected_assignment, expected_origins, expected_profiles = _canonical_assignment(
        precursor_rows,
        outcome_rows,
    )

    changed_precursors = precursor_rows.copy()
    future_precursor = changed_precursors["year_month"] > "2021-12"
    changed_precursors.loc[future_precursor, "mean_TP_ugL"] = None
    changed_precursors.loc[future_precursor, "mean_temperature_C"] = 99.0
    changed_precursors = pd.concat(
        [
            changed_precursors,
            pd.DataFrame(
                [
                    {
                        "source_id": "wqp",
                        "site_id": "future-only",
                        "year_month": "2022-02",
                        "mean_TP_ugL": 50.0,
                        "mean_TN_ugL": 500.0,
                        "mean_temperature_C": 20.0,
                        "mean_secchi_depth_m": 1.0,
                        "mean_turbidity_NTU": 3.0,
                        "mean_DO_mgL": 8.0,
                        "mean_pH": 7.5,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    changed_outcomes = outcome_rows.copy()
    changed_outcomes.loc[changed_outcomes["target_year_month"] > "2021-12", "bloom_h"] = True
    changed_outcomes = pd.concat(
        [
            changed_outcomes,
            pd.DataFrame(
                [
                    {
                        "source_id": "wqp",
                        "site_id": "future-only",
                        "origin_year_month": "2022-01",
                        "target_year_month": "2022-02",
                        "horizon_months": 1,
                        "bloom_h": True,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    actual_assignment, actual_origins, actual_profiles = _canonical_assignment(
        changed_precursors,
        changed_outcomes,
    )
    pd.testing.assert_frame_equal(actual_assignment, expected_assignment)
    pd.testing.assert_frame_equal(actual_origins, expected_origins)
    pd.testing.assert_frame_equal(actual_profiles, expected_profiles)


def test_eligible_origins_have_complete_pre_cutoff_targets_and_deduplicated_bloom_months() -> None:
    precursor_rows, outcome_rows = _synthetic_frames()
    result = build_holdout_selection(precursor_rows, outcome_rows)

    assert result.eligible_origins["origin_year_month"].max() == "2021-09"
    assert result.eligible_origins["history_length_months"].eq(12).all()
    assert result.eligible_origins["complete_horizons"].all()
    for horizon in (1, 2, 3):
        assert result.eligible_origins[f"target_year_month_h{horizon}"].max() <= "2021-12"

    # The historical stratum uses every unique pre-cutoff WQP target month,
    # including target months that precede the first eligible 12-month origin.
    assert result.location_profiles["eligible_origin_count"].eq(10).all()
    assert result.location_profiles["historical_target_months"].eq(23).all()
    assert result.location_profiles["historical_bloom_events"].isin([0, 1]).all()


def test_historical_bloom_stratum_includes_bloom_before_first_eligible_origin_target() -> None:
    precursor_rows, outcome_rows = _synthetic_frames(site_count=5)
    outcome_rows["bloom_h"] = False
    outcome_rows.loc[outcome_rows["target_year_month"] == "2020-03", "bloom_h"] = True

    result = build_holdout_selection(precursor_rows, outcome_rows)
    site_origins = result.eligible_origins.loc[result.eligible_origins["site_id"] == "site-00"]
    profile = result.location_profiles.loc[result.location_profiles["site_id"] == "site-00"].iloc[0]

    assert site_origins["target_year_month_h1"].min() == "2021-01"
    assert profile["first_historical_target_month"] == "2020-02"
    assert profile["last_historical_target_month"] == "2021-12"
    assert profile["historical_target_months"] == 23
    assert profile["historical_bloom_events"] == 1
    assert bool(profile["historical_bloom_presence"])


@pytest.mark.parametrize(
    "forbidden_column",
    ["mean_chlorophyll_a_ugL", "risk_chla", "Chl", "Chl_prev", "x_irc1"],
)
def test_precursor_contract_rejects_every_chlorophyll_column(forbidden_column: str) -> None:
    precursor_rows, _ = _synthetic_frames(site_count=1)

    assert not any("chlorophyll" in column.lower() or "chla" in column.lower() for column in PRECURSOR_READ_COLUMNS)
    contaminated = precursor_rows.assign(**{forbidden_column: 12.0})
    with pytest.raises(ValueError, match="must not contain chlorophyll-a"):
        build_precursor_month_status(contaminated)


def test_location_coverage_is_fraction_of_fully_covered_months() -> None:
    precursor_rows, outcome_rows = _synthetic_frames(site_count=5)
    required_history = precursor_rows["year_month"].between("2020-10", "2021-09")
    pre_cutoff = precursor_rows["year_month"] <= "2021-12"
    precursor_rows.loc[pre_cutoff & ~required_history, "mean_temperature_C"] = None

    profiles = build_holdout_selection(precursor_rows, outcome_rows).location_profiles
    profile = profiles.loc[profiles["site_id"] == "site-00"].iloc[0]

    assert profile["input_eligible_months"] == 12
    assert profile["series_length_months"] == 24
    assert profile["precursor_coverage_fraction"] == pytest.approx(0.5)
    assert profile["precursor_coverage_band"] == "medium"


def test_assignment_keeps_complete_source_site_groups_in_one_role() -> None:
    precursor_rows, outcome_rows = _synthetic_frames()
    result = build_holdout_selection(precursor_rows, outcome_rows)
    origins_with_role = result.eligible_origins.merge(
        result.assignment[["source_id", "site_id", "assignment_role"]],
        on=["source_id", "site_id"],
        how="left",
        validate="many_to_one",
    )

    assert result.assignment[["source_id", "site_id"]].duplicated().sum() == 0
    assert origins_with_role.groupby(["source_id", "site_id"])["assignment_role"].nunique().eq(1).all()
    selected_sites = result.assignment.loc[
        result.assignment["assignment_role"] == ASSIGNMENT_HOLDOUT,
        ["source_id", "site_id"],
    ]
    selected_origin_count = origins_with_role.merge(
        selected_sites,
        on=["source_id", "site_id"],
        how="inner",
        validate="many_to_one",
    ).groupby(["source_id", "site_id"]).size()
    assert selected_origin_count.eq(10).all()


def test_floor_total_and_largest_remainder_quotas_are_exact_without_replacement() -> None:
    strata = ["a"] * 6 + ["b"] * 4 + ["c"] * 3
    profiles = pd.DataFrame(
        {
            "source_id": "wqp",
            "site_id": [f"q-{index:02d}" for index in range(len(strata))],
            "holdout_group_id": [f"wqp::q-{index:02d}" for index in range(len(strata))],
            "stratum_id": strata,
            "historical_bloom_presence": [False] * len(strata),
            "precursor_coverage_fraction": [0.5] * len(strata),
            "precursor_coverage_band": ["medium"] * len(strata),
            "series_length_months": [24] * len(strata),
            "series_length_band": ["medium"] * len(strata),
        }
    )

    quotas = allocate_stratum_quotas(profiles, holdout_fraction=0.20)
    assignment, assigned_quotas = assign_holdout_locations(
        profiles,
        holdout_fraction=0.20,
        selection_seed=20260802,
    )

    assert quotas.set_index("stratum_id")["holdout_quota"].to_dict() == {"a": 1, "b": 1, "c": 0}
    assert quotas.set_index("stratum_id")["exact_quota"].to_dict() == pytest.approx(
        {"a": 1.2, "b": 0.8, "c": 0.6}
    )
    assert len(assignment[assignment["assignment_role"] == ASSIGNMENT_HOLDOUT]) == 2
    assert assignment.loc[
        assignment["assignment_role"] == ASSIGNMENT_HOLDOUT,
        ["source_id", "site_id"],
    ].duplicated().sum() == 0
    assert assigned_quotas["selected_locations"].tolist() == assigned_quotas["holdout_quota"].tolist()


@pytest.mark.parametrize("location_count", [0, 4])
def test_zero_floor_holdout_fails_the_gate_instead_of_writing_empty_assignment(
    location_count: int,
) -> None:
    profiles = pd.DataFrame(
        {
            "source_id": ["wqp"] * location_count,
            "site_id": [f"small-{index}" for index in range(location_count)],
            "holdout_group_id": [f"wqp::small-{index}" for index in range(location_count)],
            "stratum_id": ["single-stratum"] * location_count,
            "historical_bloom_presence": [False] * location_count,
            "precursor_coverage_fraction": [0.5] * location_count,
            "precursor_coverage_band": ["medium"] * location_count,
            "series_length_months": [24] * location_count,
            "series_length_band": ["medium"] * location_count,
        }
    )

    with pytest.raises(ValueError, match="zero_holdout_policy=fail_gate"):
        assign_holdout_locations(
            profiles,
            holdout_fraction=0.20,
            selection_seed=20260802,
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, "low"), (1.0 / 3.0, "medium"), (2.0 / 3.0, "high"), (1.0, "high")],
)
def test_coverage_band_boundaries(value: float, expected: str) -> None:
    assert coverage_band(value) == expected


@pytest.mark.parametrize(
    ("months", "expected"),
    [(12, "short"), (23, "short"), (24, "medium"), (59, "medium"), (60, "long")],
)
def test_series_length_band_boundaries(months: int, expected: str) -> None:
    assert series_length_band(months) == expected


def test_panel_reader_projects_allowlisted_columns_and_pushes_cutoff_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_read_parquet(path: Path, **kwargs: Any) -> pd.DataFrame:
        calls.append({"path": path, **kwargs})
        columns = kwargs["columns"]
        assert isinstance(columns, list)
        return pd.DataFrame(columns=columns)

    monkeypatch.setattr(pd, "read_parquet", fake_read_parquet)
    precursor_rows, outcomes = read_pre_cutoff_panel_projections(
        Path("panel-not-opened.parquet"),
        Path("targets-not-opened.parquet"),
        HoldoutConfig(),
    )

    assert precursor_rows.columns.tolist() == PRECURSOR_READ_COLUMNS
    assert outcomes.columns.tolist() == HISTORICAL_OUTCOME_READ_COLUMNS
    assert [call["columns"] for call in calls] == [PRECURSOR_READ_COLUMNS, HISTORICAL_OUTCOME_READ_COLUMNS]
    assert ("year_month", "<=", "2021-12") in calls[0]["filters"]
    assert ("target_year_month", "<=", "2021-12") in calls[1]["filters"]
    assert all(("source_id", "==", "wqp") in call["filters"] for call in calls)


def test_target_manifest_binds_completed_targets_and_bloom_threshold(tmp_path: Path) -> None:
    manifest_path = tmp_path / "target_manifest.json"
    payload = {
        "status": "completed",
        "bloom_threshold_chla_ugL": 30.0,
        "model_long_targets": TARGETS_PATH.as_posix(),
    }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    validated = load_and_validate_target_manifest(
        manifest_path,
        targets_path=TARGETS_PATH,
        config=HoldoutConfig(),
    )

    assert validated == payload


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "running", "status must be 'completed'"),
        ("bloom_threshold_chla_ugL", 29.9, "does not match"),
        ("model_long_targets", "data/targets/other.parquet", "does not match"),
    ],
)
def test_target_manifest_rejects_contract_drift(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    manifest_path = tmp_path / "target_manifest.json"
    payload: dict[str, object] = {
        "status": "completed",
        "bloom_threshold_chla_ugL": 30.0,
        "model_long_targets": TARGETS_PATH.as_posix(),
    }
    payload[field] = value
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_and_validate_target_manifest(
            manifest_path,
            targets_path=TARGETS_PATH,
            config=HoldoutConfig(),
        )


def test_locked_source_guard_detects_same_size_content_change(tmp_path: Path) -> None:
    source_path = tmp_path / "source.bin"
    source_path.write_bytes(b"first")
    protocol_lock = {
        "source_artifacts": [
            {
                "path": source_path.as_posix(),
                "role": "test_source",
                "bytes": source_path.stat().st_size,
                "sha256": _sha256(source_path),
            }
        ]
    }
    source_path.write_bytes(b"other")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        holdout_module._locked_source_record(protocol_lock, source_path)


def test_locked_panel_and_targets_are_revalidated_after_projection_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_path = Path("locked-panel.parquet")
    targets_path = Path("locked-targets.parquet")
    validation_calls: list[Path] = []

    def fake_locked_source_record(_: dict[str, object], path: Path) -> dict[str, object]:
        validation_calls.append(path)
        validation_number = validation_calls.count(path)
        digest = "b" * 64 if path == panel_path and validation_number == 2 else "a" * 64
        return {"path": path.as_posix(), "bytes": 10, "sha256": digest}

    def fake_projection_read(
        _: Path,
        __: Path,
        ___: HoldoutConfig,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        return pd.DataFrame(), pd.DataFrame()

    monkeypatch.setattr(holdout_module, "_locked_source_record", fake_locked_source_record)
    monkeypatch.setattr(holdout_module, "read_pre_cutoff_panel_projections", fake_projection_read)

    with pytest.raises(RuntimeError, match="changed while"):
        holdout_module._read_and_revalidate_locked_projections(
            {},
            panel_path,
            targets_path,
            HoldoutConfig(),
        )

    assert validation_calls == [panel_path, targets_path, panel_path, targets_path]


def test_protocol_lock_requires_the_exact_selector_hash(tmp_path: Path) -> None:
    head = "a" * 40
    lock_path = tmp_path / "protocol_lock.json"
    payload = _protocol_lock_payload(head)
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    validated = validate_protocol_lock(lock_path, SCRIPT_PATH)
    assert validated["future_outcomes_accessed"] is False

    raw_components = payload["protocol_components"]
    assert isinstance(raw_components, list)
    assert all(isinstance(component, dict) for component in raw_components)
    protocol_components = cast(list[dict[str, object]], raw_components)
    protocol_components[0]["sha256"] = "0" * 64
    lock_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_protocol_lock(lock_path, SCRIPT_PATH)

    payload = _protocol_lock_payload(head)
    raw_components = payload["protocol_components"]
    assert isinstance(raw_components, list)
    assert all(isinstance(component, dict) for component in raw_components)
    protocol_components = cast(list[dict[str, object]], raw_components)
    protocol_components[1]["sha256"] = "0" * 64
    lock_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="location_holdout.yaml"):
        validate_protocol_lock(lock_path, SCRIPT_PATH)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("assignment_created", "holdout_assignment_created=false"),
        ("dirty_locked_repository", "worktree_status='clean'"),
    ],
)
def test_protocol_lock_requires_pre_assignment_clean_state(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    payload = _protocol_lock_payload("a" * 40)
    if mutation == "assignment_created":
        payload["holdout_assignment_created"] = True
    else:
        raw_locked_repository = payload["locked_repository"]
        assert isinstance(raw_locked_repository, dict)
        locked_repository = cast(dict[str, object], raw_locked_repository)
        locked_repository["worktree_status"] = "dirty"
    lock_path = tmp_path / "protocol_lock.json"
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        validate_protocol_lock(lock_path, SCRIPT_PATH)


def test_real_execution_guard_rejects_dirty_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout=" M README.md\n", stderr="")

    monkeypatch.setattr(holdout_module.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="fully clean worktree"):
        require_clean_worktree()


def test_real_execution_guard_rejects_untracked_protocol_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="not tracked")

    monkeypatch.setattr(holdout_module.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="Git-tracked protocol lock"):
        require_tracked_clean_protocol_lock(Path("reports/closure_v1/00_protocol/protocol_lock.json"))


def test_locked_writer_emits_five_file_bundle_with_manifest_last(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = build_holdout_selection(*_synthetic_frames(site_count=5))
    assignment_path = tmp_path / "data" / "assignment.csv"
    summary_path = tmp_path / "reports" / "summary.csv"
    cohort_flow_path = tmp_path / "reports" / "cohort_flow.csv"
    leakage_audit_path = tmp_path / "reports" / "leakage_audit.json"
    manifest_path = tmp_path / "reports" / "manifest.json"
    lock_path = tmp_path / "protocol_lock.json"
    lock_path.write_text("{}\n", encoding="utf-8")
    protocol_lock = {"locked_repository": {"head": "a" * 40}}
    write_order: list[Path] = []
    original_csv_writer = holdout_module._write_csv_atomic
    original_json_writer = holdout_module._write_json_atomic

    def recording_csv_writer(frame: pd.DataFrame, path: Path) -> None:
        write_order.append(path)
        original_csv_writer(frame, path)

    def recording_json_writer(payload: dict[str, object], path: Path) -> None:
        write_order.append(path)
        original_json_writer(payload, path)

    monkeypatch.setattr(holdout_module, "_write_csv_atomic", recording_csv_writer)
    monkeypatch.setattr(holdout_module, "_write_json_atomic", recording_json_writer)

    holdout_module._write_locked_outputs(
        selection,
        assignment_path=assignment_path,
        summary_path=summary_path,
        cohort_flow_path=cohort_flow_path,
        leakage_audit_path=leakage_audit_path,
        manifest_path=manifest_path,
        config_path=CONFIG_PATH,
        source_records=[],
        protocol_lock_path=lock_path,
        protocol_lock=protocol_lock,
        config=HoldoutConfig(),
    )

    expected_order = [
        assignment_path,
        summary_path,
        cohort_flow_path,
        leakage_audit_path,
        manifest_path,
    ]
    assert write_order == expected_order
    assert all(path.is_file() for path in expected_order)
    written_assignment = pd.read_csv(assignment_path)
    assert written_assignment.columns.tolist() == ASSIGNMENT_OUTPUT_COLUMNS
    cohort_flow = pd.read_csv(cohort_flow_path)
    assert cohort_flow["assignment_role"].tolist() == ["all", "development", "internal_holdout"]
    leakage_audit = json.loads(leakage_audit_path.read_text(encoding="utf-8"))
    assert leakage_audit["status"] == "passed"
    assert all(leakage_audit["checks"].values())
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert [record["path"] for record in manifest["outputs"]] == [
        holdout_module._manifest_path(path) for path in expected_order[:-1]
    ]


def test_locked_writer_cleans_all_final_and_temporary_outputs_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = build_holdout_selection(*_synthetic_frames(site_count=5))
    output_paths = [
        tmp_path / "data" / "assignment.csv",
        tmp_path / "reports" / "summary.csv",
        tmp_path / "reports" / "cohort_flow.csv",
        tmp_path / "reports" / "leakage_audit.json",
        tmp_path / "reports" / "manifest.json",
    ]
    assignment_path, summary_path, cohort_flow_path, leakage_audit_path, manifest_path = output_paths
    lock_path = tmp_path / "protocol_lock.json"
    lock_path.write_text("{}\n", encoding="utf-8")
    original_json_writer = holdout_module._write_json_atomic

    def fail_while_writing_manifest(payload: dict[str, object], path: Path) -> None:
        if path == manifest_path:
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text("partial", encoding="utf-8")
            raise RuntimeError("simulated manifest failure")
        original_json_writer(payload, path)

    monkeypatch.setattr(holdout_module, "_write_json_atomic", fail_while_writing_manifest)

    with pytest.raises(RuntimeError, match="simulated manifest failure"):
        holdout_module._write_locked_outputs(
            selection,
            assignment_path=assignment_path,
            summary_path=summary_path,
            cohort_flow_path=cohort_flow_path,
            leakage_audit_path=leakage_audit_path,
            manifest_path=manifest_path,
            config_path=CONFIG_PATH,
            source_records=[],
            protocol_lock_path=lock_path,
            protocol_lock={"locked_repository": {"head": "a" * 40}},
            config=HoldoutConfig(),
        )

    assert all(not path.exists() for path in output_paths)
    assert all(not path.with_suffix(path.suffix + ".tmp").exists() for path in output_paths)


def test_cli_dry_run_does_not_read_panel_or_write_outputs(tmp_path: Path) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    lock_path = tmp_path / "protocol_lock.json"
    lock_path.write_text(json.dumps(_protocol_lock_payload(head)), encoding="utf-8")
    output_paths = [
        Path("data/closure_v1/closure_holdout_assignment.csv"),
        Path("reports/closure_v1/00_protocol/holdout_summary_pre_cutoff.csv"),
        Path("reports/closure_v1/00_protocol/cohort_flow_preoutcome.csv"),
        Path("reports/closure_v1/00_protocol/holdout_leakage_audit.json"),
        Path("reports/closure_v1/00_protocol/holdout_manifest.json"),
    ]
    before = {
        path: (path.exists(), path.read_bytes() if path.exists() else None)
        for path in output_paths
    }

    completed = subprocess.run(
        [
            sys.executable,
            SCRIPT_PATH.as_posix(),
            "--protocol-lock",
            lock_path.as_posix(),
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "panel was not read" in completed.stdout
    after = {
        path: (path.exists(), path.read_bytes() if path.exists() else None)
        for path in output_paths
    }
    assert after == before
