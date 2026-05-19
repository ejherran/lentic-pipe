from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pandas as pd

from src.data.build_waterbody_crosswalk import MatchConfig, build_candidates, load_match_config, write_manifest


def _config() -> MatchConfig:
    return MatchConfig(
        max_distance_m=1_000.0,
        strong_distance_m=250.0,
        very_close_distance_m=50.0,
        same_coordinate_tolerance_m=0.001,
        exact_id_max_distance_m=5_000.0,
        name_similarity_threshold=0.75,
        candidate_grid_deg=0.05,
        site_id_prefix_rules={"wqp": ("NARS_WQX-",)},
    )


def _site(
    source_id: str,
    site_id_source: str | None,
    site_name: str | None,
    latitude: float,
    longitude: float,
    row_count: int = 10,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "site_id": f"{source_id}:{site_id_source or 'missing'}",
        "site_id_source": site_id_source,
        "site_name": site_name,
        "latitude": latitude,
        "longitude": longitude,
        "row_count": row_count,
        "first_year_month": "2020-01",
        "last_year_month": "2020-12",
        "variable_counts_json": "{}",
    }


def test_build_candidates_scores_exact_and_strong_cross_source_matches() -> None:
    registry = pd.DataFrame(
        [
            _site("wqp", "USGS-123", "Clear Lake", 45.0000, -93.0000),
            _site("aquamatch_chla", "USGS-123", "Clear Lake Station", 45.0004, -93.0003),
            _site("nla", "NLA-001", "Clear Reservoir", 45.0002, -93.0002),
            _site("wqp", "USGS-456", "Clear Lake East", 45.0001, -93.0001),
            _site("lakebed_us_cse", "FAR-1", "Far Lake", 46.0, -94.0),
        ]
    )

    candidates = build_candidates(registry, _config())

    assert set(candidates["confidence"]) == {"exact", "strong"}
    assert (candidates["left_source_id"] != candidates["right_source_id"]).all()
    assert not (
        candidates["left_site_id"].eq("wqp:USGS-123") & candidates["right_site_id"].eq("wqp:USGS-456")
    ).any()

    exact = candidates[candidates["match_method"] == "shared_source_site_identifier"].iloc[0]
    assert exact["confidence"] == "exact"
    assert exact["review_tier"] == 1
    assert {exact["left_source_id"], exact["right_source_id"]} == {"aquamatch_chla", "wqp"}

    strong = candidates[candidates["match_method"].isin(["very_close_coordinates_and_name", "close_coordinates_and_name"])]
    assert {"nla", "wqp"}.issubset(set(strong[["left_source_id", "right_source_id"]].to_numpy().ravel()))


def test_missing_source_site_identifiers_are_not_exact_matches() -> None:
    registry = pd.DataFrame(
        [
            _site("wqp", None, "Mirror Lake", 44.0000, -92.0000),
            _site("nla", None, "Mirror Reservoir", 44.0001, -92.0001),
        ]
    )

    candidates = build_candidates(registry, _config())

    assert len(candidates) == 1
    assert candidates.iloc[0]["confidence"] == "strong"
    assert candidates.iloc[0]["match_method"] != "shared_source_site_identifier"


def test_wqp_nars_prefix_is_normalized_for_nla_matches() -> None:
    registry = pd.DataFrame(
        [
            _site("nla", "NLA_ME-10063", None, 44.43398548, -69.38994854),
            _site("wqp", "NARS_WQX-NLA_ME-10063", "NLA_ME-10063", 44.43398548, -69.38994854),
        ]
    )

    candidates = build_candidates(registry, _config())

    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["confidence"] == "exact"
    assert row["review_tier"] == 1
    assert row["match_method"] == "provider_prefix_normalized_site_identifier"
    assert row["id_match_rule"] == "source_prefix_normalized"
    assert row["left_site_id_source_normalized"] == "nla_me-10063"
    assert row["right_site_id_source_normalized"] == "nla_me-10063"
    assert row["distance_review_band"] == "same_coordinate"
    assert row["review_action"] == "alias_same_coordinate"


def test_identifier_matches_with_coordinate_offsets_are_flagged_for_review() -> None:
    registry = pd.DataFrame(
        [
            _site("nla", "NLA_ID-10016", None, 43.9000, -116.0000),
            _site("wqp", "NARS_WQX-NLA_ID-10016", "NLA_ID-10016", 43.9075, -116.0000),
        ]
    )

    candidates = build_candidates(registry, _config())

    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["confidence"] == "exact"
    assert row["review_tier"] == 1
    assert row["distance_review_band"] == "offset_>500m"
    assert row["review_action"] == "alias_coordinate_offset_review"


def test_same_coordinates_with_different_identifiers_get_specific_method() -> None:
    registry = pd.DataFrame(
        [
            _site("nla", "NLA_OR-10205", None, 44.51261, -122.8876),
            _site("wqp", "OREGONDEQ-38853-ORDEQ", "Cheadle Lake", 44.51261, -122.8876),
        ]
    )

    candidates = build_candidates(registry, _config())

    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["confidence"] == "strong"
    assert row["review_tier"] == 2
    assert row["match_method"] == "same_coordinates_different_identifier"
    assert row["id_match_rule"] == "none"
    assert row["distance_m"] == 0.0
    assert row["review_action"] == "same_coordinate_identifier_review"


def test_review_tier_orders_candidates_by_review_priority() -> None:
    registry = pd.DataFrame(
        [
            _site("nla", "NLA_EXACT", None, 44.0000, -92.0000),
            _site("wqp", "NARS_WQX-NLA_EXACT", "NLA_EXACT", 44.0000, -92.0000),
            _site("nla", "NLA_SAME", None, 45.0000, -93.0000),
            _site("wqp", "STATE-SAME", "Same Lake", 45.0000, -93.0000),
            _site("nla", "NLA_CLOSE", None, 46.0000, -94.0000),
            _site("wqp", "STATE-CLOSE", "Close Lake", 46.0001, -94.0001),
            _site("nla", "NLA_NEAR", None, 47.0000, -95.0000),
            _site("wqp", "STATE-NEAR", "Nearby Lake", 47.0050, -95.0050),
        ]
    )

    candidates = build_candidates(registry, _config())

    assert candidates["review_tier"].tolist() == sorted(candidates["review_tier"].tolist())
    assert candidates["review_tier"].tolist() == [1, 2, 3, 4]


def test_load_match_config_uses_site_resolution_thresholds(tmp_path: Path) -> None:
    config_path = tmp_path / "site_resolution.yaml"
    config_path.write_text(
        """
candidate_generation:
  default_thresholds:
    max_distance_m: 1500
    strong_distance_m: 300
    very_close_distance_m: 60
    same_coordinate_tolerance_m: 0.01
    exact_id_max_distance_m: 6000
    name_similarity_threshold: 0.8
    candidate_grid_deg: 0.1
""".lstrip(),
        encoding="utf-8",
    )

    config = load_match_config(config_path)

    assert config.max_distance_m == 1500
    assert config.strong_distance_m == 300
    assert config.very_close_distance_m == 60
    assert config.same_coordinate_tolerance_m == 0.01
    assert config.exact_id_max_distance_m == 6000
    assert config.name_similarity_threshold == 0.8
    assert config.candidate_grid_deg == 0.1
    assert config.site_id_prefix_rules == {"wqp": ("NARS_WQX-",)}


def test_write_manifest_records_reproducibility_outputs(tmp_path: Path) -> None:
    site_registry = tmp_path / "site_registry.parquet"
    site_registry.write_text("registry", encoding="utf-8")
    resolution_config = tmp_path / "site_resolution.yaml"
    resolution_config.write_text("candidate_generation: {}\n", encoding="utf-8")
    output_parquet = tmp_path / "crosswalk.parquet"
    output_parquet.write_text("parquet-bytes", encoding="utf-8")
    output_csv = tmp_path / "crosswalk.csv"
    output_csv.write_text("csv-bytes", encoding="utf-8")
    report = tmp_path / "crosswalk_report.md"
    report.write_text("# report\n", encoding="utf-8")
    manifest = tmp_path / "crosswalk_manifest.json"

    args = Namespace(
        site_registry=site_registry,
        site_resolution_config=resolution_config,
        output_parquet=output_parquet,
        output_csv=output_csv,
        report=report,
        source_pair=["nla:wqp"],
        max_sites_per_source=None,
    )

    write_manifest(pd.DataFrame({"candidate_id": ["candidate_1"]}), manifest, _config(), args)

    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert payload["status"] == "completed"
    assert {record["path"] for record in payload["outputs"]} == {
        output_parquet.as_posix(),
        output_csv.as_posix(),
        report.as_posix(),
    }
    assert {record["path"] for record in payload["inputs"]} == {
        site_registry.as_posix(),
        resolution_config.as_posix(),
    }
    assert len(payload["script"]["sha256"]) == 64
