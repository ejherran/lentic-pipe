#!/usr/bin/env python
"""Build auditable cross-source waterbody match candidates from site metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.adapters.common import load_yaml
from src.pandas_utils import dataframe_rows


DEFAULT_SITE_ID_PREFIX_RULES: dict[str, tuple[str, ...]] = {
    "wqp": ("NARS_WQX-",),
}
DEFAULT_SITE_REGISTRY = Path("data/interim/site_registry.parquet")
DEFAULT_SITE_RESOLUTION_CONFIG = Path("configs/site_resolution.yaml")
DEFAULT_OUTPUT_PARQUET = Path("data/interim/waterbody_crosswalk_candidates_v0.parquet")
DEFAULT_OUTPUT_CSV = Path("data/interim/waterbody_crosswalk_candidates_v0.csv")
DEFAULT_REPORT = Path("reports/data/waterbody_crosswalk_candidates_report.md")
DEFAULT_MANIFEST = Path("reports/data/waterbody_crosswalk_candidates_manifest.json")
HASH_CHUNK_SIZE = 16 * 1024 * 1024

OUTPUT_COLUMNS = [
    "candidate_id",
    "review_tier",
    "confidence",
    "match_method",
    "match_notes",
    "id_match_rule",
    "distance_m",
    "distance_review_band",
    "review_action",
    "name_similarity",
    "left_source_id",
    "left_site_id",
    "left_site_id_source",
    "left_site_id_source_normalized",
    "left_site_name",
    "left_latitude",
    "left_longitude",
    "left_row_count",
    "right_source_id",
    "right_site_id",
    "right_site_id_source",
    "right_site_id_source_normalized",
    "right_site_name",
    "right_latitude",
    "right_longitude",
    "right_row_count",
]

CONFIDENCE_ORDER = {
    "exact": 3,
    "strong": 2,
    "candidate": 1,
}

REVIEW_TIERS = {
    "shared_source_site_identifier": 1,
    "provider_prefix_normalized_site_identifier": 1,
    "same_coordinates_different_identifier": 2,
    "very_close_coordinates": 3,
    "very_close_coordinates_and_name": 3,
    "close_coordinates_and_name": 3,
    "nearby_coordinates": 4,
}

GENERIC_NAME_TOKENS = {
    "lake",
    "lakes",
    "reservoir",
    "res",
    "pond",
    "site",
    "station",
    "nr",
    "near",
    "at",
    "the",
}

DISTANCE_REVIEW_BANDS: tuple[tuple[float, str], ...] = (
    (0.001, "same_coordinate"),
    (1.0, "near_exact_<=1m"),
    (10.0, "very_near_<=10m"),
    (50.0, "very_close_<=50m"),
    (250.0, "close_<=250m"),
    (500.0, "offset_<=500m"),
)


@dataclass(frozen=True)
class MatchConfig:
    max_distance_m: float
    strong_distance_m: float
    very_close_distance_m: float
    same_coordinate_tolerance_m: float
    exact_id_max_distance_m: float
    name_similarity_threshold: float
    candidate_grid_deg: float
    site_id_prefix_rules: dict[str, tuple[str, ...]]


DEFAULT_MATCH_CONFIG = MatchConfig(
    max_distance_m=1_000.0,
    strong_distance_m=250.0,
    very_close_distance_m=50.0,
    same_coordinate_tolerance_m=0.001,
    exact_id_max_distance_m=5_000.0,
    name_similarity_threshold=0.75,
    candidate_grid_deg=0.05,
    site_id_prefix_rules=DEFAULT_SITE_ID_PREFIX_RULES,
)


def _format_int(value: int) -> str:
    return f"{value:,}"


def _format_float(value: float | None, digits: int = 4) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.{digits}f}"


def _repo_relative(path: Path) -> Path:
    if not path.is_absolute():
        return path
    try:
        return path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return path


def _sha256_file(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    path = _repo_relative(path)
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _existing_file_records(paths: list[Path | None]) -> list[dict[str, Any]]:
    return [_file_record(path) for path in paths if path is not None and path.exists()]


def normalize_name(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [token for token in text.split() if token not in GENERIC_NAME_TOKENS]
    return " ".join(tokens)


def name_similarity(left: Any, right: Any) -> float | None:
    left_name = normalize_name(left)
    right_name = normalize_name(right)
    if not left_name or not right_name:
        return None
    return float(SequenceMatcher(None, left_name, right_name).ratio())


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return float(2.0 * radius_m * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)))


def stable_id(prefix: str, *parts: Any, length: int = 16) -> str:
    payload = "\x1f".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def review_tier_for_match_method(match_method: str) -> int:
    return REVIEW_TIERS.get(match_method, 9)


def distance_review_band(distance_m: float) -> str:
    for threshold_m, label in DISTANCE_REVIEW_BANDS:
        if distance_m <= threshold_m:
            return label
    return "offset_>500m"


def review_action(review_tier: int, match_method: str, distance_m: float, config: MatchConfig) -> str:
    if review_tier == 1:
        if distance_m <= config.same_coordinate_tolerance_m:
            return "alias_same_coordinate"
        if distance_m <= config.very_close_distance_m:
            return "alias_coordinate_close"
        return "alias_coordinate_offset_review"
    if match_method == "same_coordinates_different_identifier":
        return "same_coordinate_identifier_review"
    if review_tier == 3:
        return "spatial_candidate_manual_review"
    if review_tier == 4:
        return "exploratory_review"
    return "manual_review"


def _raw_site_id_source(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().lower()


def normalize_site_id_source(source_id: Any, site_id_source: Any, config: MatchConfig) -> tuple[str, str]:
    normalized = _raw_site_id_source(site_id_source)
    if not normalized:
        return "", "none"
    source_key = str(source_id).strip().lower()
    for prefix in config.site_id_prefix_rules.get(source_key, ()):
        prefix_normalized = str(prefix).strip().lower()
        if prefix_normalized and normalized.startswith(prefix_normalized):
            return normalized[len(prefix_normalized) :], f"remove_prefix:{prefix}"
    return normalized, "none"


def _site_id_source_match(left: pd.Series, right: pd.Series, config: MatchConfig) -> tuple[str, str, str] | None:
    left_raw = _raw_site_id_source(left.get("site_id_source"))
    right_raw = _raw_site_id_source(right.get("site_id_source"))
    if left_raw and right_raw and left_raw == right_raw:
        return (
            "literal",
            "shared_source_site_identifier",
            "Source-native site identifiers match and coordinates are compatible.",
        )

    left_normalized, left_rule = normalize_site_id_source(left.get("source_id"), left.get("site_id_source"), config)
    right_normalized, right_rule = normalize_site_id_source(right.get("source_id"), right.get("site_id_source"), config)
    if left_normalized and right_normalized and left_normalized == right_normalized and (left_rule != "none" or right_rule != "none"):
        return (
            "source_prefix_normalized",
            "provider_prefix_normalized_site_identifier",
            "Source identifiers match after configured provider-prefix normalization and coordinates are compatible.",
        )
    return None


def _site_id_prefix_rules(payload: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    raw_rules = (
        payload.get("candidate_generation", {})
        .get("site_id_normalization", {})
        .get("remove_source_prefixes", DEFAULT_SITE_ID_PREFIX_RULES)
    )
    if not isinstance(raw_rules, dict):
        return DEFAULT_SITE_ID_PREFIX_RULES
    rules: dict[str, tuple[str, ...]] = {}
    for source_id, prefixes in raw_rules.items():
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        if not isinstance(prefixes, list):
            continue
        rules[str(source_id).strip().lower()] = tuple(str(prefix) for prefix in prefixes)
    return rules or DEFAULT_SITE_ID_PREFIX_RULES


def load_match_config(path: Path | None = DEFAULT_SITE_RESOLUTION_CONFIG) -> MatchConfig:
    if path is None or not path.exists():
        return DEFAULT_MATCH_CONFIG
    payload = load_yaml(path)
    defaults = payload.get("candidate_generation", {}).get("default_thresholds", {})
    return MatchConfig(
        max_distance_m=float(defaults.get("max_distance_m", DEFAULT_MATCH_CONFIG.max_distance_m)),
        strong_distance_m=float(defaults.get("strong_distance_m", DEFAULT_MATCH_CONFIG.strong_distance_m)),
        very_close_distance_m=float(defaults.get("very_close_distance_m", DEFAULT_MATCH_CONFIG.very_close_distance_m)),
        same_coordinate_tolerance_m=float(defaults.get("same_coordinate_tolerance_m", DEFAULT_MATCH_CONFIG.same_coordinate_tolerance_m)),
        exact_id_max_distance_m=float(defaults.get("exact_id_max_distance_m", DEFAULT_MATCH_CONFIG.exact_id_max_distance_m)),
        name_similarity_threshold=float(defaults.get("name_similarity_threshold", DEFAULT_MATCH_CONFIG.name_similarity_threshold)),
        candidate_grid_deg=float(defaults.get("candidate_grid_deg", DEFAULT_MATCH_CONFIG.candidate_grid_deg)),
        site_id_prefix_rules=_site_id_prefix_rules(payload),
    )


def override_match_config(
    config: MatchConfig,
    *,
    max_distance_m: float | None = None,
    strong_distance_m: float | None = None,
    very_close_distance_m: float | None = None,
    same_coordinate_tolerance_m: float | None = None,
    exact_id_max_distance_m: float | None = None,
    name_similarity_threshold: float | None = None,
    candidate_grid_deg: float | None = None,
) -> MatchConfig:
    return MatchConfig(
        max_distance_m=config.max_distance_m if max_distance_m is None else max_distance_m,
        strong_distance_m=config.strong_distance_m if strong_distance_m is None else strong_distance_m,
        very_close_distance_m=config.very_close_distance_m if very_close_distance_m is None else very_close_distance_m,
        same_coordinate_tolerance_m=config.same_coordinate_tolerance_m if same_coordinate_tolerance_m is None else same_coordinate_tolerance_m,
        exact_id_max_distance_m=config.exact_id_max_distance_m if exact_id_max_distance_m is None else exact_id_max_distance_m,
        name_similarity_threshold=config.name_similarity_threshold if name_similarity_threshold is None else name_similarity_threshold,
        candidate_grid_deg=config.candidate_grid_deg if candidate_grid_deg is None else candidate_grid_deg,
        site_id_prefix_rules=config.site_id_prefix_rules,
    )


def classify_candidate(left: pd.Series, right: pd.Series, distance_m: float, similarity: float | None, config: MatchConfig) -> tuple[str, str, str]:
    site_id_match = _site_id_source_match(left, right, config)
    if site_id_match is not None and distance_m <= config.exact_id_max_distance_m:
        _rule, method, notes = site_id_match
        return "exact", method, notes
    if distance_m <= config.same_coordinate_tolerance_m:
        return (
            "strong",
            "same_coordinates_different_identifier",
            "Coordinates are identical within the configured tolerance, but source identifiers differ.",
        )
    if distance_m <= config.very_close_distance_m:
        if similarity is not None and similarity >= config.name_similarity_threshold:
            return "strong", "very_close_coordinates_and_name", "Coordinates are very close and normalized names are similar."
        return "strong", "very_close_coordinates", "Coordinates are very close; name evidence is missing or weak."
    if distance_m <= config.strong_distance_m and similarity is not None and similarity >= config.name_similarity_threshold:
        return "strong", "close_coordinates_and_name", "Coordinates are close and normalized names are similar."
    return "candidate", "nearby_coordinates", "Coordinates are within the candidate search radius; review before merging."


def _valid_sites(registry: pd.DataFrame) -> pd.DataFrame:
    frame = registry.copy()
    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")
    frame["row_count"] = pd.to_numeric(frame["row_count"], errors="coerce").fillna(0).astype(int)
    frame = frame[
        frame["source_id"].notna()
        & frame["site_id"].notna()
        & frame["latitude"].between(-90, 90)
        & frame["longitude"].between(-180, 180)
    ].copy()
    frame["source_id"] = frame["source_id"].astype(str)
    frame["site_id"] = frame["site_id"].astype(str)
    frame["site_id_source"] = frame["site_id_source"].fillna("").astype(str)
    return frame.reset_index(drop=True)


def _source_pairs(sources: list[str], requested_pairs: list[str] | None) -> list[tuple[str, str]]:
    if requested_pairs:
        pairs = []
        for item in requested_pairs:
            if ":" not in item:
                raise ValueError(f"Invalid source pair {item!r}; expected left:right")
            left, right = item.split(":", 1)
            if left == right:
                raise ValueError(f"Source pair {item!r} must use two different sources")
            pairs.append(tuple(sorted((left, right))))
        return sorted(set(pairs))
    return [(left, right) for index, left in enumerate(sources) for right in sources[index + 1 :]]


def _grid_key(lat: float, lon: float, cell_deg: float) -> tuple[int, int]:
    return (math.floor(lat / cell_deg), math.floor(lon / cell_deg))


def _build_grid(frame: pd.DataFrame, cell_deg: float) -> dict[tuple[int, int], list[int]]:
    grid: dict[tuple[int, int], list[int]] = {}
    for row in dataframe_rows(frame.reset_index()):
        key = _grid_key(float(row.latitude), float(row.longitude), cell_deg)
        grid.setdefault(key, []).append(int(row.index))
    return grid


def _neighbor_keys(lat: float, lon: float, cell_deg: float, max_distance_m: float) -> list[tuple[int, int]]:
    center_lat, center_lon = _grid_key(lat, lon, cell_deg)
    cos_lat = max(abs(math.cos(math.radians(lat))), 0.25)
    lat_radius = math.ceil((max_distance_m / 111_320.0) / cell_deg) + 1
    lon_radius = math.ceil((max_distance_m / (111_320.0 * cos_lat)) / cell_deg) + 1
    return [
        (center_lat + lat_delta, center_lon + lon_delta)
        for lat_delta in range(-lat_radius, lat_radius + 1)
        for lon_delta in range(-lon_radius, lon_radius + 1)
    ]


def _candidate_row(left: pd.Series, right: pd.Series, config: MatchConfig) -> dict[str, Any] | None:
    distance = haversine_m(float(left["latitude"]), float(left["longitude"]), float(right["latitude"]), float(right["longitude"]))
    if distance > config.max_distance_m:
        return None
    similarity = name_similarity(left.get("site_name"), right.get("site_name"))
    confidence, method, notes = classify_candidate(left, right, distance, similarity, config)
    left_key = (left["source_id"], left["site_id"])
    right_key = (right["source_id"], right["site_id"])
    if left_key > right_key:
        left, right = right, left
        left_key, right_key = right_key, left_key

    id_match = _site_id_source_match(left, right, config)
    id_match_rule = id_match[0] if id_match is not None else "none"
    tier = review_tier_for_match_method(method)
    left_site_id_source_normalized, _left_normalization_rule = normalize_site_id_source(
        left["source_id"],
        left.get("site_id_source"),
        config,
    )
    right_site_id_source_normalized, _right_normalization_rule = normalize_site_id_source(
        right["source_id"],
        right.get("site_id_source"),
        config,
    )
    candidate_id = stable_id("crosswalk", left["source_id"], left["site_id"], right["source_id"], right["site_id"])
    return {
        "candidate_id": candidate_id,
        "review_tier": tier,
        "confidence": confidence,
        "match_method": method,
        "match_notes": notes,
        "id_match_rule": id_match_rule,
        "distance_m": round(distance, 3),
        "distance_review_band": distance_review_band(distance),
        "review_action": review_action(tier, method, distance, config),
        "name_similarity": None if similarity is None else round(similarity, 6),
        "left_source_id": left["source_id"],
        "left_site_id": left["site_id"],
        "left_site_id_source": left["site_id_source"],
        "left_site_id_source_normalized": left_site_id_source_normalized,
        "left_site_name": left.get("site_name"),
        "left_latitude": float(left["latitude"]),
        "left_longitude": float(left["longitude"]),
        "left_row_count": int(left["row_count"]),
        "right_source_id": right["source_id"],
        "right_site_id": right["site_id"],
        "right_site_id_source": right["site_id_source"],
        "right_site_id_source_normalized": right_site_id_source_normalized,
        "right_site_name": right.get("site_name"),
        "right_latitude": float(right["latitude"]),
        "right_longitude": float(right["longitude"]),
        "right_row_count": int(right["row_count"]),
    }


def build_candidates(
    registry: pd.DataFrame,
    config: MatchConfig,
    *,
    source_pairs: list[str] | None = None,
    max_sites_per_source: int | None = None,
) -> pd.DataFrame:
    sites = _valid_sites(registry)
    if max_sites_per_source is not None:
        sites = (
            sites.sort_values(["source_id", "row_count"], ascending=[True, False])
            .groupby("source_id", group_keys=False)
            .head(max_sites_per_source)
            .reset_index(drop=True)
        )
    sources = sorted(sites["source_id"].unique())
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for left_source, right_source in _source_pairs(sources, source_pairs):
        left_frame = sites[sites["source_id"] == left_source].reset_index(drop=True)
        right_frame = sites[sites["source_id"] == right_source].reset_index(drop=True)
        if left_frame.empty or right_frame.empty:
            continue
        right_grid = _build_grid(right_frame, config.candidate_grid_deg)
        for left in dataframe_rows(left_frame):
            left_series = pd.Series(left._asdict())
            for key in _neighbor_keys(float(left.latitude), float(left.longitude), config.candidate_grid_deg, config.max_distance_m):
                for right_index in right_grid.get(key, []):
                    right_series = right_frame.iloc[right_index]
                    row = _candidate_row(left_series, right_series, config)
                    if row is None or row["candidate_id"] in seen:
                        continue
                    seen.add(str(row["candidate_id"]))
                    rows.append(row)

    if not rows:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    output = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    output["_confidence_rank"] = output["confidence"].map(CONFIDENCE_ORDER).fillna(0).astype(int)
    output = output.sort_values(["review_tier", "_confidence_rank", "distance_m", "candidate_id"], ascending=[True, False, True, True])
    return output.drop(columns=["_confidence_rank"]).reset_index(drop=True)


def load_site_registry(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path)
    return pd.read_parquet(path)


def write_outputs(candidates: pd.DataFrame, parquet_path: Path, csv_path: Path) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_parquet(parquet_path, index=False)
    candidates.to_csv(csv_path, index=False)


def write_report(candidates: pd.DataFrame, registry: pd.DataFrame, report_path: Path, config: MatchConfig) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Waterbody Crosswalk Candidates",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Purpose",
        "",
        "This report lists cross-source site pairs that may represent the same waterbody. "
        "It is an audit layer only: it does not merge observations, change site IDs, or alter the monthly panel.",
        "",
        "## Search Configuration",
        "",
        f"- Candidate maximum distance: `{_format_float(config.max_distance_m, 1)} m`",
        f"- Strong distance threshold: `{_format_float(config.strong_distance_m, 1)} m`",
        f"- Very close distance threshold: `{_format_float(config.very_close_distance_m, 1)} m`",
        f"- Same-coordinate tolerance: `{_format_float(config.same_coordinate_tolerance_m, 3)} m`",
        f"- Exact ID maximum distance: `{_format_float(config.exact_id_max_distance_m, 1)} m`",
        f"- Name similarity threshold: `{_format_float(config.name_similarity_threshold, 2)}`",
        f"- Site ID prefix normalization: `{json.dumps(config.site_id_prefix_rules, sort_keys=True)}`",
        "",
        "## Summary",
        "",
        f"- Source-scoped sites in input registry: `{_format_int(len(registry))}`",
        f"- Candidate pairs: `{_format_int(len(candidates))}`",
        "",
    ]
    if not candidates.empty:
        tier_counts = candidates["review_tier"].value_counts().to_dict()
        lines.extend(["| review_tier | pairs |", "|---:|---:|"])
        for tier in sorted(tier_counts):
            lines.append(f"| `{int(tier)}` | {_format_int(int(tier_counts.get(tier, 0)))} |")
        lines.append("")
        confidence_counts = candidates["confidence"].value_counts().to_dict()
        lines.extend(["| confidence | pairs |", "|---|---:|"])
        for confidence in ("exact", "strong", "candidate"):
            lines.append(f"| `{confidence}` | {_format_int(int(confidence_counts.get(confidence, 0)))} |")
        lines.extend(["", "## By Source Pair", "", "| source_pair | pairs | min_distance_m | median_distance_m |", "|---|---:|---:|---:|"])
        source_pair = candidates["left_source_id"] + " - " + candidates["right_source_id"]
        for pair, group in candidates.assign(source_pair=source_pair).groupby("source_pair", sort=True):
            lines.append(
                f"| `{pair}` | {_format_int(len(group))} | "
                f"{_format_float(float(group['distance_m'].min()), 1)} | {_format_float(float(group['distance_m'].median()), 1)} |"
            )
        lines.extend(["", "## By Match Method", "", "| match_method | pairs |", "|---|---:|"])
        method_counts = candidates["match_method"].value_counts().to_dict()
        for method, count in sorted(method_counts.items(), key=lambda item: (-int(item[1]), str(item[0]))):
            lines.append(f"| `{method}` | {_format_int(int(count))} |")
        lines.extend(["", "## By Distance Review Band", "", "| distance_review_band | pairs |", "|---|---:|"])
        band_counts = candidates["distance_review_band"].value_counts().to_dict()
        ordered_bands = [label for _threshold, label in DISTANCE_REVIEW_BANDS] + ["offset_>500m"]
        for band in ordered_bands:
            lines.append(f"| `{band}` | {_format_int(int(band_counts.get(band, 0)))} |")
        tier1 = candidates[candidates["review_tier"] == 1]
        if not tier1.empty:
            lines.extend(["", "## Tier 1 Coordinate Offset", "", "| distance_review_band | pairs |", "|---|---:|"])
            tier1_band_counts = tier1["distance_review_band"].value_counts().to_dict()
            for band in ordered_bands:
                lines.append(f"| `{band}` | {_format_int(int(tier1_band_counts.get(band, 0)))} |")
        lines.extend(
            [
                "",
                "## Top Candidates",
                "",
                "| tier | confidence | method | distance_m | left | right |",
                "|---:|---|---|---:|---|---|",
            ]
        )
        for row in dataframe_rows(candidates.head(25)):
            left_label = f"{row.left_source_id}:{row.left_site_id_source}"
            right_label = f"{row.right_source_id}:{row.right_site_id_source}"
            lines.append(
                f"| `{int(row.review_tier)}` | `{row.confidence}` | `{row.match_method}` | "
                f"{float(row.distance_m):.1f} | `{left_label}` | `{right_label}` |"
            )

    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- Preserve `source_id` and source-scoped `site_id` in all downstream tables.",
            "- Treat `candidate` rows as review items, not accepted merges.",
            "- Promote a candidate to an accepted waterbody crosswalk only after documenting the match evidence.",
            "- Re-check temporal splits before using linked waterbodies in modeling, because cross-source links can create leakage if the same waterbody appears in different splits through different sources.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def write_manifest(candidates: pd.DataFrame, manifest_path: Path, config: MatchConfig, args: argparse.Namespace) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "site_registry": args.site_registry.as_posix(),
        "site_resolution_config": args.site_resolution_config.as_posix() if args.site_resolution_config is not None else None,
        "output_parquet": args.output_parquet.as_posix(),
        "output_csv": args.output_csv.as_posix(),
        "report": args.report.as_posix(),
        "candidate_count": int(len(candidates)),
        "inputs": _existing_file_records([args.site_registry, args.site_resolution_config]),
        "outputs": _existing_file_records([args.output_parquet, args.output_csv, args.report]),
        "script": _file_record(Path(__file__)),
        "config": {
            "max_distance_m": config.max_distance_m,
            "strong_distance_m": config.strong_distance_m,
            "very_close_distance_m": config.very_close_distance_m,
            "same_coordinate_tolerance_m": config.same_coordinate_tolerance_m,
            "exact_id_max_distance_m": config.exact_id_max_distance_m,
            "name_similarity_threshold": config.name_similarity_threshold,
            "candidate_grid_deg": config.candidate_grid_deg,
            "site_id_prefix_rules": config.site_id_prefix_rules,
            "source_pairs": args.source_pair,
            "max_sites_per_source": args.max_sites_per_source,
        },
    }
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cross-source waterbody match candidates from site_registry.")
    parser.add_argument("--site-registry", type=Path, default=DEFAULT_SITE_REGISTRY)
    parser.add_argument("--site-resolution-config", type=Path, default=DEFAULT_SITE_RESOLUTION_CONFIG)
    parser.add_argument("--output-parquet", type=Path, default=DEFAULT_OUTPUT_PARQUET)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--max-distance-m", type=float, default=None)
    parser.add_argument("--strong-distance-m", type=float, default=None)
    parser.add_argument("--very-close-distance-m", type=float, default=None)
    parser.add_argument("--same-coordinate-tolerance-m", type=float, default=None)
    parser.add_argument("--exact-id-max-distance-m", type=float, default=None)
    parser.add_argument("--name-similarity-threshold", type=float, default=None)
    parser.add_argument("--grid-deg", type=float, default=None)
    parser.add_argument("--source-pair", action="append", help="Limit to one source pair, formatted left:right. Can repeat.")
    parser.add_argument("--max-sites-per-source", type=int, default=None, help="Development/testing limit by largest row_count sites per source.")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing outputs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    registry = load_site_registry(args.site_registry)
    config = override_match_config(
        load_match_config(args.site_resolution_config),
        max_distance_m=args.max_distance_m,
        strong_distance_m=args.strong_distance_m,
        very_close_distance_m=args.very_close_distance_m,
        same_coordinate_tolerance_m=args.same_coordinate_tolerance_m,
        exact_id_max_distance_m=args.exact_id_max_distance_m,
        name_similarity_threshold=args.name_similarity_threshold,
        candidate_grid_deg=args.grid_deg,
    )
    candidates = build_candidates(
        registry,
        config,
        source_pairs=args.source_pair,
        max_sites_per_source=args.max_sites_per_source,
    )
    print(f"site registry rows: {len(registry):,}")
    print(f"candidate pairs: {len(candidates):,}")
    if not candidates.empty:
        print(candidates["confidence"].value_counts().to_string())
    if args.dry_run:
        return
    write_outputs(candidates, args.output_parquet, args.output_csv)
    write_report(candidates, registry, args.report, config)
    write_manifest(candidates, args.manifest, config, args)
    print(f"crosswalk candidates written: {args.output_parquet}")
    print(f"crosswalk candidates csv written: {args.output_csv}")
    print(f"crosswalk report written: {args.report}")
    print(f"crosswalk manifest written: {args.manifest}")


if __name__ == "__main__":
    main()
