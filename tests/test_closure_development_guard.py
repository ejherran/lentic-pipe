from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from src.experiments.closure_development_guard import (
    DevelopmentGuardError,
    assert_development_frame,
    assign_pair_roles,
    assign_point_roles,
    load_development_gate,
    scan_development_rows,
    validate_assignment_frame,
)


ASSIGNMENT_PATH = Path("data/closure_v1/closure_holdout_assignment.csv")
HOLDOUT_MANIFEST_PATH = Path("reports/closure_v1/00_protocol/holdout_manifest.json")
PROTOCOL_LOCK_PATH = Path("reports/closure_v1/00_protocol/protocol_lock.json")


def _selection_rank(site_id: str) -> str:
    payload = f"20260802\x1fwqp\x1f{site_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _assignment_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "development-site",
                "holdout_group_id": "wqp::development-site",
                "assignment_role": "development",
                "stratum_id": "bloom=0|coverage=high|length=long",
                "historical_bloom_presence": False,
                "precursor_coverage_fraction": 1.0,
                "precursor_coverage_band": "high",
                "series_length_months": 72,
                "series_length_band": "long",
                "deterministic_rank_sha256": _selection_rank("development-site"),
            },
            {
                "source_id": "wqp",
                "site_id": "holdout-site",
                "holdout_group_id": "wqp::holdout-site",
                "assignment_role": "internal_holdout",
                "stratum_id": "bloom=1|coverage=medium|length=medium",
                "historical_bloom_presence": True,
                "precursor_coverage_fraction": 0.5,
                "precursor_coverage_band": "medium",
                "series_length_months": 36,
                "series_length_band": "medium",
                "deterministic_rank_sha256": _selection_rank("holdout-site"),
            },
        ]
    )


def _expected_counts() -> dict[str, int]:
    return {
        "eligible_locations": 2,
        "holdout_locations": 1,
        "development_locations": 1,
    }


def test_real_locked_assignment_hash_and_counts_load_without_repository_probe() -> None:
    manifest = json.loads(HOLDOUT_MANIFEST_PATH.read_text(encoding="utf-8"))
    assignment_record = next(
        output for output in manifest["outputs"] if output["path"] == ASSIGNMENT_PATH.as_posix()
    )

    gate = load_development_gate(validate_repository=False)
    assignment = gate.assignment

    assert hashlib.sha256(ASSIGNMENT_PATH.read_bytes()).hexdigest() == assignment_record["sha256"]
    assert len(assignment) == 441
    assert assignment["assignment_role"].value_counts().to_dict() == {
        "development": 353,
        "internal_holdout": 88,
    }
    assert gate.expected_counts == {
        "eligible_locations": 441,
        "holdout_locations": 88,
        "development_locations": 353,
    }
    assert len(gate.development_keys) == 353
    assert len(gate.holdout_keys) == 88
    assert gate.development_keys.isdisjoint(gate.holdout_keys)


def test_real_gate_validates_tracked_locked_artifacts_by_default() -> None:
    gate = load_development_gate()

    assert gate.repository_validated is True
    assert gate.assignment_path == ASSIGNMENT_PATH.resolve()
    assert gate.holdout_manifest_path == HOLDOUT_MANIFEST_PATH.resolve()
    assert gate.protocol_lock_path == PROTOCOL_LOCK_PATH.resolve()


def test_assignment_frame_accepts_the_exact_locked_schema_and_counts() -> None:
    validate_assignment_frame(_assignment_frame(), expected_counts=_expected_counts())


@pytest.mark.parametrize("column", ["source_id", "site_id", "assignment_role"])
def test_assignment_frame_rejects_missing_required_column(column: str) -> None:
    with pytest.raises(DevelopmentGuardError, match="column|schema"):
        validate_assignment_frame(_assignment_frame().drop(columns=column))


def test_assignment_frame_rejects_duplicate_source_site_group() -> None:
    assignment = pd.concat([_assignment_frame(), _assignment_frame().iloc[[0]]], ignore_index=True)

    with pytest.raises(DevelopmentGuardError, match="duplicate|unique|one assignment"):
        validate_assignment_frame(assignment)


def test_assignment_frame_rejects_group_id_that_does_not_match_source_site() -> None:
    assignment = _assignment_frame()
    assignment.loc[0, "holdout_group_id"] = "wqp::different-site"

    with pytest.raises(DevelopmentGuardError, match="holdout_group_id|group"):
        validate_assignment_frame(assignment)


def test_assignment_frame_rejects_unlocked_role() -> None:
    assignment = _assignment_frame()
    assignment.loc[0, "assignment_role"] = "validation"

    with pytest.raises(DevelopmentGuardError, match="assignment_role|role"):
        validate_assignment_frame(assignment)


def test_assignment_frame_rejects_expected_count_drift() -> None:
    expected_counts = _expected_counts()
    expected_counts["development_locations"] = 2

    with pytest.raises(DevelopmentGuardError, match="development|count"):
        validate_assignment_frame(_assignment_frame(), expected_counts=expected_counts)


def test_assignment_frame_rejects_malformed_deterministic_rank_hash() -> None:
    assignment = _assignment_frame()
    assignment.loc[0, "deterministic_rank_sha256"] = "not-a-sha256"

    with pytest.raises(DevelopmentGuardError, match="deterministic_rank_sha256|SHA-256|hash"):
        validate_assignment_frame(assignment)


def test_gate_rejects_assignment_artifact_hash_drift(tmp_path: Path) -> None:
    copied_assignment = tmp_path / "closure_holdout_assignment.csv"
    copied_assignment.write_bytes(ASSIGNMENT_PATH.read_bytes() + b"\n")
    manifest = json.loads(HOLDOUT_MANIFEST_PATH.read_text(encoding="utf-8"))
    assignment_record = next(
        output for output in manifest["outputs"] if output["path"] == ASSIGNMENT_PATH.as_posix()
    )
    assignment_record["bytes"] = copied_assignment.stat().st_size
    copied_manifest = tmp_path / "holdout_manifest.json"
    copied_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(DevelopmentGuardError, match="hash|sha256|SHA-256"):
        load_development_gate(
            assignment_path=copied_assignment,
            manifest_path=copied_manifest,
            protocol_lock_path=PROTOCOL_LOCK_PATH,
            validate_repository=False,
        )


def test_point_roles_use_exact_locked_calendar_boundaries() -> None:
    frame = pd.DataFrame(
        {
            "year_month": [
                "1999-01",
                "2018-12",
                "2019-01",
                "2020-12",
                "2021-01",
                "2021-12",
            ]
        }
    )

    roles = assign_point_roles(frame)

    assert roles.tolist() == [
        "training",
        "training",
        "model_selection",
        "model_selection",
        "calibration_threshold",
        "calibration_threshold",
    ]


def test_pair_roles_exclude_every_boundary_crossing() -> None:
    frame = pd.DataFrame(
        {
            "origin_year_month": [
                "2018-11",
                "2018-12",
                "2019-01",
                "2020-12",
                "2021-01",
            ],
            "target_year_month": [
                "2018-12",
                "2019-01",
                "2020-12",
                "2021-01",
                "2021-12",
            ],
        }
    )

    roles = assign_pair_roles(frame)

    assert roles.iloc[0] == "training"
    assert pd.isna(roles.iloc[1])
    assert roles.iloc[2] == "model_selection"
    assert pd.isna(roles.iloc[3])
    assert roles.iloc[4] == "calibration_threshold"


@pytest.mark.parametrize(
    ("frame", "call"),
    [
        (pd.DataFrame({"year_month": ["2022-01"]}), "point"),
        (
            pd.DataFrame(
                {
                    "origin_year_month": ["2021-12"],
                    "target_year_month": ["2022-01"],
                }
            ),
            "pair",
        ),
        (
            pd.DataFrame(
                {
                    "origin_year_month": ["2022-01"],
                    "target_year_month": ["2022-02"],
                }
            ),
            "pair",
        ),
    ],
    ids=["point", "crossing-target", "pair"],
)
def test_role_assignment_rejects_materialized_post_2021_rows(
    frame: pd.DataFrame,
    call: str,
) -> None:
    with pytest.raises(DevelopmentGuardError, match="2021-12|post-2021|locked_evaluation"):
        if call == "point":
            assign_point_roles(frame)
        else:
            assign_pair_roles(frame)


def test_assert_development_frame_accepts_only_development_keys_and_roles() -> None:
    gate = load_development_gate(validate_repository=False)
    source_id, site_id = sorted(gate.development_keys)[0]
    frame = pd.DataFrame(
        {
            "source_id": [source_id, source_id],
            "site_id": [site_id, site_id],
            "development_role": ["training", "calibration_threshold"],
        }
    )

    assert_development_frame(
        frame,
        gate,
        role_column="development_role",
        allowed_roles={"training", "calibration_threshold"},
    )


@pytest.mark.parametrize("key_kind", ["holdout", "unknown"])
def test_assert_development_frame_rejects_holdout_and_unknown_keys(key_kind: str) -> None:
    gate = load_development_gate(validate_repository=False)
    if key_kind == "holdout":
        source_id, site_id = sorted(gate.holdout_keys)[0]
    else:
        source_id, site_id = "wqp", "site-not-in-locked-assignment"
    frame = pd.DataFrame({"source_id": [source_id], "site_id": [site_id]})

    with pytest.raises(DevelopmentGuardError, match="holdout|unknown|development"):
        assert_development_frame(frame, gate)


def test_assert_development_frame_rejects_role_outside_requested_stage() -> None:
    gate = load_development_gate(validate_repository=False)
    source_id, site_id = sorted(gate.development_keys)[0]
    frame = pd.DataFrame(
        {
            "source_id": [source_id],
            "site_id": [site_id],
            "development_role": ["calibration_threshold"],
        }
    )

    with pytest.raises(DevelopmentGuardError, match="role|training"):
        assert_development_frame(
            frame,
            gate,
            role_column="development_role",
            allowed_roles={"training"},
        )


def test_scanner_filters_to_development_locations_and_pre_2022_point_rows(
    tmp_path: Path,
) -> None:
    assignment = _assignment_frame()
    gate = load_development_gate(
        assignment_path=_write_assignment_bundle(tmp_path, assignment),
        manifest_path=tmp_path / "holdout_manifest.json",
        protocol_lock_path=PROTOCOL_LOCK_PATH,
        validate_repository=False,
    )
    input_path = tmp_path / "synthetic_points.parquet"
    pd.DataFrame(
        {
            "source_id": ["wqp", "wqp", "wqp", "wqp", "wqp"],
            "site_id": [
                "development-site",
                "development-site",
                "development-site",
                "holdout-site",
                "unknown-site",
            ],
            "year_month": ["2018-12", "2021-12", "2022-01", "2020-06", "2020-06"],
            "synthetic_value": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    ).to_parquet(input_path, index=False)

    rows, audit = scan_development_rows(
        input_path,
        gate,
        columns=["source_id", "site_id", "year_month", "synthetic_value"],
        point_month_column="year_month",
    )

    assert rows[["site_id", "year_month", "time_role"]].to_dict("records") == [
        {
            "site_id": "development-site",
            "year_month": "2018-12",
            "time_role": "training",
        },
        {
            "site_id": "development-site",
            "year_month": "2021-12",
            "time_role": "calibration_threshold",
        },
    ]
    assert audit.returned_rows == 2
    assert audit.boundary_crossing_rows == 0
    assert audit.role_counts == {"calibration_threshold": 1, "training": 1}
    assert audit.materialized_rows < 5


def _write_assignment_bundle(tmp_path: Path, assignment: pd.DataFrame) -> Path:
    assignment_path = tmp_path / "closure_holdout_assignment.csv"
    assignment.to_csv(assignment_path, index=False)
    assignment_hash = hashlib.sha256(assignment_path.read_bytes()).hexdigest()
    manifest = json.loads(HOLDOUT_MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["counts"].update(_expected_counts())
    assignment_record = next(
        output for output in manifest["outputs"] if output["path"] == ASSIGNMENT_PATH.as_posix()
    )
    assignment_record.update(
        {
            "bytes": assignment_path.stat().st_size,
            "sha256": assignment_hash,
        }
    )
    (tmp_path / "holdout_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return assignment_path
