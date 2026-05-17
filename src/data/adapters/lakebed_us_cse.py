"""Adapter for LakeBeD-US: Computer Science Edition."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from src.data.adapters.common import (
    ObservationChunk,
    convert_canonical_value,
    empty_canonical_frame,
    enforce_schema,
    flags_to_json,
    namespaced_site_id,
    year_month_from_datetime,
)


def _site_from_path(path: Path) -> str:
    return path.parent.name


def _frequency_from_path(path: Path) -> str:
    parts = path.parts
    if "LowFrequency" in parts:
        return "LowFrequency"
    if "HighFrequency" in parts:
        return "HighFrequency"
    return "unknown"


def _source_label_from_file(path: Path) -> str:
    return path.stem


def _read_lake_info(raw_path: Path) -> dict[str, dict[str, Any]]:
    info_path = raw_path / "Data" / "Lake_Info.csv"
    if not info_path.exists():
        return {}
    info = pd.read_csv(info_path)
    by_lake: dict[str, dict[str, Any]] = {}
    for row in info.to_dict(orient="records"):
        lake_id = str(row.get("lake_id", "")).strip()
        if lake_id:
            by_lake[lake_id] = row
    return by_lake


def iter_lakebed_files(raw_path: Path, include_high_frequency: bool = True) -> list[Path]:
    roots = [raw_path / "Data" / "LowFrequency"]
    if include_high_frequency:
        roots.append(raw_path / "Data" / "HighFrequency")
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(root.glob("*/*.parquet")))
    return files


def _available_usecols(path: Path, variables_config: dict[str, Any]) -> tuple[list[str], list[str]]:
    mapping = variables_config["source_mappings"]["lakebed_us_cse"]
    selected_raw_variables = [col for col in mapping["variables"]]
    base_columns = ["datetime", "flag"]
    available_columns = pq.read_schema(path).names
    if "depth" in available_columns:
        base_columns.append("depth")
    usecols = [col for col in base_columns + selected_raw_variables if col in available_columns]
    selected_available = [col for col in selected_raw_variables if col in available_columns]
    return usecols, selected_available


def _row_group_starts(parquet_file: pq.ParquetFile) -> list[int]:
    starts: list[int] = []
    offset = 0
    for index in range(parquet_file.metadata.num_row_groups):
        starts.append(offset)
        offset += parquet_file.metadata.row_group(index).num_rows
    return starts


def convert_file(
    path: Path,
    raw_path: Path,
    variables_config: dict[str, Any],
    lake_info: dict[str, dict[str, Any]],
    *,
    max_rows: int | None = None,
) -> pd.DataFrame:
    usecols, selected_available = _available_usecols(path, variables_config)
    if not selected_available:
        return empty_canonical_frame()

    frame = pd.read_parquet(path, columns=usecols)
    if max_rows is not None:
        frame = frame.head(max_rows)
    return convert_frame(path, variables_config, lake_info, frame, raw_row_offset=0)


def convert_frame(
    path: Path,
    variables_config: dict[str, Any],
    lake_info: dict[str, dict[str, Any]],
    frame: pd.DataFrame,
    *,
    raw_row_offset: int,
) -> pd.DataFrame:
    mapping = variables_config["source_mappings"]["lakebed_us_cse"]
    if frame.empty:
        return empty_canonical_frame()

    site_id_source = _site_from_path(path)
    lake_metadata = lake_info.get(site_id_source, {})
    site_name = lake_metadata.get("lake_name")
    latitude = lake_metadata.get("latitude")
    longitude = lake_metadata.get("longitude")
    frequency = _frequency_from_path(path)
    source_label = _source_label_from_file(path)

    output_frames: list[pd.DataFrame] = []
    for raw_variable, variable_map in mapping["variables"].items():
        if raw_variable not in frame.columns:
            continue
        canonical = variable_map["canonical"]
        unit = variable_map["unit"]
        subset = frame[["datetime", "flag"] + (["depth"] if "depth" in frame.columns else []) + [raw_variable]].copy()
        subset = subset.rename(columns={raw_variable: "value_raw"})
        subset = subset[subset["value_raw"].notna()]
        if subset.empty:
            continue
        subset = subset.reset_index(names="raw_row_index")
        subset["raw_row_index"] = subset["raw_row_index"] + raw_row_offset

        converted = subset["value_raw"].apply(
            lambda value: convert_canonical_value(value, unit, canonical, variables_config)
        )
        subset["value_canonical"] = converted.apply(lambda item: item.value)
        subset["conversion"] = converted.apply(lambda item: item.conversion)
        subset["qc_conversion_flag"] = converted.apply(lambda item: item.qc_flag)

        sample_datetime = pd.to_datetime(subset["datetime"], errors="coerce", utc=True)
        source_row_id = subset["raw_row_index"].astype(str)
        depth_m = subset["depth"] if "depth" in subset.columns else None
        out = pd.DataFrame(
            {
                "source_id": "lakebed_us_cse",
                "source_file": path.as_posix(),
                "source_row_id": source_label + ":" + source_row_id,
                "site_id_source": site_id_source,
                "site_id": namespaced_site_id("lakebed_us_cse", site_id_source),
                "site_name": site_name,
                "sample_datetime": sample_datetime.dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "year_month": year_month_from_datetime(sample_datetime),
                "latitude": latitude,
                "longitude": longitude,
                "depth_m": depth_m,
                "variable_raw": raw_variable,
                "variable_canonical": canonical,
                "value_raw": subset["value_raw"],
                "unit_raw": unit,
                "value_canonical": subset["value_canonical"],
                "unit_canonical": variables_config["canonical_variables"][canonical]["canonical_unit"],
                "conversion": subset["conversion"],
                "qc_flag": subset["qc_conversion_flag"],
                "source_quality": subset["flag"],
                "flags_json": [
                    flags_to_json(
                        {
                            "lakebed_flag": flag,
                            "frequency": frequency,
                            "source_label": source_label,
                            "conversion_qc": conversion_qc,
                        }
                    )
                    for flag, conversion_qc in zip(subset["flag"], subset["qc_conversion_flag"], strict=False)
                ],
            }
        )
        output_frames.append(out)

    if not output_frames:
        return empty_canonical_frame()
    return enforce_schema(pd.concat(output_frames, ignore_index=True))


def _count_lakebed_units(files: list[Path], variables_config: dict[str, Any], max_rows_per_file: int | None) -> int:
    if max_rows_per_file is not None:
        return len(files)
    total = 0
    for path in files:
        _, selected_available = _available_usecols(path, variables_config)
        if not selected_available:
            total += 1
            continue
        total += pq.ParquetFile(path).metadata.num_row_groups
    return total


def build_observations(
    source_config: dict[str, Any],
    variables_config: dict[str, Any],
    *,
    include_high_frequency: bool = True,
    max_files: int | None = None,
    max_rows_per_file: int | None = None,
) -> pd.DataFrame:
    raw_path = Path(source_config["raw_path"])
    lake_info = _read_lake_info(raw_path)
    files = iter_lakebed_files(raw_path, include_high_frequency=include_high_frequency)
    if max_files is not None:
        files = files[:max_files]

    frames = [
        convert_file(
            path,
            raw_path,
            variables_config,
            lake_info,
            max_rows=max_rows_per_file,
        )
        for path in files
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return empty_canonical_frame()
    return enforce_schema(pd.concat(frames, ignore_index=True))


def iter_observation_chunks(
    source_config: dict[str, Any],
    variables_config: dict[str, Any],
    *,
    include_high_frequency: bool = True,
    max_files: int | None = None,
    max_rows_per_file: int | None = None,
    skip_units: set[str] | None = None,
):
    raw_path = Path(source_config["raw_path"])
    lake_info = _read_lake_info(raw_path)
    files = iter_lakebed_files(raw_path, include_high_frequency=include_high_frequency)
    if max_files is not None:
        files = files[:max_files]
    skip_units = skip_units or set()
    total_units = _count_lakebed_units(files, variables_config, max_rows_per_file)
    global_unit_index = 0
    for file_index, path in enumerate(files):
        file_unit_id = path.as_posix()
        if file_unit_id in skip_units:
            if max_rows_per_file is None:
                _, selected_available = _available_usecols(path, variables_config)
                increment = pq.ParquetFile(path).metadata.num_row_groups if selected_available else 1
            else:
                increment = 1
            global_unit_index += increment
            continue

        usecols, selected_available = _available_usecols(path, variables_config)
        if not selected_available:
            print(
                f"lakebed_us_cse: processing file {file_index + 1}/{len(files)} "
                f"{path.name}; no selected canonical variables",
                flush=True,
            )
            yield ObservationChunk(
                frame=empty_canonical_frame(),
                unit_id=file_unit_id,
                unit_index=global_unit_index,
                total_units=total_units,
            )
            global_unit_index += 1
            continue

        if max_rows_per_file is not None:
            print(
                f"lakebed_us_cse: processing file {file_index + 1}/{len(files)} "
                f"{path.name}; max_rows_per_file={max_rows_per_file}",
                flush=True,
            )
            frame = convert_file(
                path,
                raw_path,
                variables_config,
                lake_info,
                max_rows=max_rows_per_file,
            )
            yield ObservationChunk(
                frame=frame,
                unit_id=file_unit_id,
                unit_index=global_unit_index,
                total_units=total_units,
            )
            global_unit_index += 1
            continue

        parquet_file = pq.ParquetFile(path)
        row_group_starts = _row_group_starts(parquet_file)
        for row_group_index in range(parquet_file.metadata.num_row_groups):
            row_group = parquet_file.metadata.row_group(row_group_index)
            raw_start = row_group_starts[row_group_index]
            raw_end = raw_start + row_group.num_rows
            unit_id = f"{file_unit_id}:row_group:{row_group_index}"
            if unit_id in skip_units:
                global_unit_index += 1
                continue
            print(
                f"lakebed_us_cse: processing file {file_index + 1}/{len(files)} "
                f"{path.name}; row_group {row_group_index + 1}/"
                f"{parquet_file.metadata.num_row_groups}; raw_rows={raw_start:,}-{raw_end:,}",
                flush=True,
            )
            table = parquet_file.read_row_group(row_group_index, columns=usecols)
            frame = convert_frame(
                path,
                variables_config,
                lake_info,
                table.to_pandas(),
                raw_row_offset=raw_start,
            )
            yield ObservationChunk(
                frame=frame,
                unit_id=unit_id,
                unit_index=global_unit_index,
                total_units=total_units,
                raw_start=raw_start,
                raw_end=raw_end,
            )
            global_unit_index += 1
