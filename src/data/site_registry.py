#!/usr/bin/env python
"""Build an initial site registry from canonical observations."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

import pandas as pd

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.adapters.common import load_yaml
from src.pandas_utils import group_key_tuple


DEFAULT_SOURCES_CONFIG = Path("configs/sources.yaml")
DEFAULT_OBSERVATIONS_DIR = Path("data/interim/observations")
DEFAULT_PARQUET = Path("data/interim/site_registry.parquet")
DEFAULT_CSV = Path("data/interim/site_registry.csv")
DEFAULT_REPORT = Path("reports/data/site_registry_report.md")

SITE_COLUMNS = [
    "source_id",
    "site_id",
    "site_id_source",
    "site_name",
    "latitude",
    "longitude",
    "row_count",
    "first_year_month",
    "last_year_month",
    "variable_counts_json",
]


def _load_manifest(source_dir: Path) -> dict[str, Any]:
    with (source_dir / "_manifest.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _format_int(value: int) -> str:
    return f"{value:,}"


def _lakebed_site_from_unit(unit_id: str) -> str | None:
    path_part = unit_id.split(":row_group:", 1)[0]
    parts = Path(path_part).parts
    for marker in ("LowFrequency", "HighFrequency"):
        if marker in parts:
            index = parts.index(marker)
            if index + 1 < len(parts):
                return parts[index + 1]
    return None


def build_lakebed_registry(source_config: dict[str, Any], source_dir: Path) -> pd.DataFrame:
    manifest = _load_manifest(source_dir)
    raw_path = Path(source_config["raw_path"])
    info_path = raw_path / "Data" / "Lake_Info.csv"
    lake_info = pd.read_csv(info_path).set_index("lake_id").to_dict(orient="index") if info_path.exists() else {}

    site_rows: dict[str, dict[str, Any]] = {}
    variable_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for chunk in manifest.get("chunks", []):
        site_id_source = _lakebed_site_from_unit(str(chunk.get("unit_id", "")))
        if not site_id_source:
            continue
        site_id = f"lakebed_us_cse:{site_id_source}"
        metadata = lake_info.get(site_id_source, {})
        row = site_rows.setdefault(
            site_id,
            {
                "source_id": "lakebed_us_cse",
                "site_id": site_id,
                "site_id_source": site_id_source,
                "site_name": metadata.get("lake_name"),
                "latitude": metadata.get("latitude"),
                "longitude": metadata.get("longitude"),
                "row_count": 0,
                "first_year_month": None,
                "last_year_month": None,
            },
        )
        row["row_count"] += int(chunk.get("rows", 0))
        for variable, count in chunk.get("variable_counts", {}).items():
            variable_counts[site_id][str(variable)] += int(count)

    rows = []
    for site_id, row in site_rows.items():
        row = dict(row)
        row["variable_counts_json"] = json.dumps(dict(sorted(variable_counts[site_id].items())), sort_keys=True)
        rows.append(row)
    return pd.DataFrame(rows, columns=SITE_COLUMNS)


def _update_site_state(
    states: dict[str, dict[str, Any]],
    variable_counts: dict[str, Counter[str]],
    frame: pd.DataFrame,
) -> None:
    if frame.empty:
        return
    frame = frame.copy()
    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")

    grouped = frame.groupby(["source_id", "site_id", "site_id_source"], dropna=False)
    for key, group in grouped:
        source_id, site_id, site_id_source = group_key_tuple(key)
        key = str(site_id)
        state = states.setdefault(
            key,
            {
                "source_id": source_id,
                "site_id": site_id,
                "site_id_source": site_id_source,
                "site_name": None,
                "latitude": None,
                "longitude": None,
                "row_count": 0,
                "first_year_month": None,
                "last_year_month": None,
            },
        )
        state["row_count"] += int(len(group))
        if state["site_name"] is None:
            names = group["site_name"].dropna()
            state["site_name"] = names.iloc[0] if not names.empty else None
        if state["latitude"] is None:
            latitudes = group["latitude"].dropna()
            state["latitude"] = float(latitudes.iloc[0]) if not latitudes.empty else None
        if state["longitude"] is None:
            longitudes = group["longitude"].dropna()
            state["longitude"] = float(longitudes.iloc[0]) if not longitudes.empty else None
        months = group["year_month"].dropna()
        if not months.empty:
            month_min = str(months.min())
            month_max = str(months.max())
            state["first_year_month"] = month_min if state["first_year_month"] is None else min(state["first_year_month"], month_min)
            state["last_year_month"] = month_max if state["last_year_month"] is None else max(state["last_year_month"], month_max)

    counts = frame.groupby(["site_id", "variable_canonical"], dropna=False).size()
    for key, count in counts.items():
        site_id, variable = group_key_tuple(key)
        variable_counts[str(site_id)][str(variable)] += int(cast(Any, count))


def build_scanned_registry(source_id: str, source_dir: Path, *, progress_every_parts: int) -> pd.DataFrame:
    states: dict[str, dict[str, Any]] = {}
    variable_counts: dict[str, Counter[str]] = defaultdict(Counter)
    part_paths = sorted(source_dir.glob("part-*.parquet"))
    columns = [
        "source_id",
        "site_id",
        "site_id_source",
        "site_name",
        "latitude",
        "longitude",
        "year_month",
        "variable_canonical",
    ]
    for index, part_path in enumerate(part_paths, start=1):
        frame = pd.read_parquet(part_path, columns=columns)
        _update_site_state(states, variable_counts, frame)
        if progress_every_parts and (index == 1 or index % progress_every_parts == 0 or index == len(part_paths)):
            print(f"{source_id}: scanned {index}/{len(part_paths)} parts; sites={len(states):,}", flush=True)

    rows = []
    for site_id, state in states.items():
        row = dict(state)
        row["variable_counts_json"] = json.dumps(dict(sorted(variable_counts[site_id].items())), sort_keys=True)
        rows.append(row)
    return pd.DataFrame(rows, columns=SITE_COLUMNS)


def build_registry(
    sources_config: dict[str, Any],
    observations_dir: Path,
    *,
    progress_every_parts: int,
) -> pd.DataFrame:
    frames = []
    for source_id, source_config in sorted(sources_config["sources"].items()):
        source_dir = observations_dir / source_id
        if not source_dir.exists():
            print(f"{source_id}: missing observations directory; skipping")
            continue
        if source_id == "lakebed_us_cse":
            frame = build_lakebed_registry(source_config, source_dir)
            print(f"{source_id}: registry from manifest; sites={len(frame):,}")
        else:
            frame = build_scanned_registry(source_id, source_dir, progress_every_parts=progress_every_parts)
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=SITE_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def write_report(registry: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    by_source = registry.groupby("source_id").agg(
        sites=("site_id", "count"),
        rows=("row_count", "sum"),
    )
    lines = [
        "# Site Registry Report",
        "",
        f"Total source-scoped sites: `{_format_int(len(registry))}`",
        f"Total canonical observations represented: `{_format_int(int(registry['row_count'].sum()))}`",
        "",
        "## By Source",
        "",
        "| source_id | sites | rows |",
        "|---|---:|---:|",
    ]
    for source_id, row in by_source.iterrows():
        lines.append(f"| `{source_id}` | {_format_int(int(row['sites']))} | {_format_int(int(row['rows']))} |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `site_id` is source-scoped and does not imply cross-source equivalence.",
            "- Cross-source matching is configured in `configs/site_resolution.yaml`; candidate pairs are not accepted merges.",
            "- LakeBeD date ranges are left empty here because the registry is built from manifests to avoid scanning 432M rows.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build initial site registry from canonical observations.")
    parser.add_argument("--sources-config", type=Path, default=DEFAULT_SOURCES_CONFIG)
    parser.add_argument("--observations-dir", type=Path, default=DEFAULT_OBSERVATIONS_DIR)
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--progress-every-parts", type=int, default=25)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sources_config = load_yaml(args.sources_config)
    registry = build_registry(
        sources_config,
        args.observations_dir,
        progress_every_parts=args.progress_every_parts,
    )
    args.parquet.parent.mkdir(parents=True, exist_ok=True)
    registry.to_parquet(args.parquet, index=False)
    registry.to_csv(args.csv, index=False)
    write_report(registry, args.report)
    print(f"site registry written: {args.parquet}")
    print(f"site registry csv written: {args.csv}")
    print(f"site registry report written: {args.report}")


if __name__ == "__main__":
    main()
