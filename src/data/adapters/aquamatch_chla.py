"""Adapter for AquaMatch harmonized chlorophyll-a extract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.data.adapters.common import (
    ObservationChunk,
    convert_canonical_value,
    empty_canonical_frame,
    enforce_schema,
    flags_to_json,
    namespaced_site_id,
    year_month_from_datetime,
)


USECOLS = [
    "parameter",
    "OrganizationIdentifier",
    "MonitoringLocationIdentifier",
    "MonitoringLocationTypeName",
    "ResolvedMonitoringLocationTypeName",
    "harmonized_utc",
    "ActivityStartDateTime",
    "harmonized_discrete_depth_value",
    "harmonized_discrete_depth_unit",
    "depth_flag",
    "mdl_flag",
    "approx_flag",
    "greater_flag",
    "tier",
    "field_flag",
    "harmonized_units",
    "harmonized_value",
    "harmonized_value_cv",
    "lat",
    "lon",
    "datum",
]


def _convert_chunk(
    chunk: pd.DataFrame,
    variables_config: dict[str, Any],
    source_file: Path,
    *,
    row_offset: int,
) -> pd.DataFrame:
    mapping = variables_config["source_mappings"]["aquamatch_chla"]
    parameter_map = mapping["variables"]
    accepted_parameters = set(parameter_map)

    chunk = chunk.copy()
    chunk["raw_row_index"] = chunk.index + row_offset
    chunk = chunk[chunk["parameter"].isin(accepted_parameters)].copy()
    if chunk.empty:
        return empty_canonical_frame()
    chunk = chunk.reset_index(drop=True)

    canonical = parameter_map["chlorophyll"]["canonical"]
    converted = chunk.apply(
        lambda row: convert_canonical_value(
            row["harmonized_value"],
            row["harmonized_units"],
            canonical,
            variables_config,
        ),
        axis=1,
    )
    chunk["value_canonical"] = converted.apply(lambda item: item.value)
    chunk["conversion"] = converted.apply(lambda item: item.conversion)
    chunk["qc_conversion_flag"] = converted.apply(lambda item: item.qc_flag)

    sample_datetime = pd.to_datetime(
        chunk["harmonized_utc"].fillna(chunk["ActivityStartDateTime"]),
        errors="coerce",
        utc=True,
    )
    site_id_source = chunk["MonitoringLocationIdentifier"].astype(str)
    out = pd.DataFrame(
        {
            "source_id": "aquamatch_chla",
            "source_file": source_file.as_posix(),
            "source_row_id": "chla_harmonized_final:" + chunk["raw_row_index"].astype(str),
            "site_id_source": site_id_source,
            "site_id": site_id_source.apply(lambda value: namespaced_site_id("aquamatch_chla", value)),
            "site_name": None,
            "sample_datetime": sample_datetime.dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "year_month": year_month_from_datetime(sample_datetime),
            "latitude": chunk["lat"],
            "longitude": chunk["lon"],
            "depth_m": pd.to_numeric(chunk["harmonized_discrete_depth_value"], errors="coerce"),
            "variable_raw": chunk["parameter"],
            "variable_canonical": canonical,
            "value_raw": chunk["harmonized_value"],
            "unit_raw": chunk["harmonized_units"],
            "value_canonical": chunk["value_canonical"],
            "unit_canonical": variables_config["canonical_variables"][canonical]["canonical_unit"],
            "conversion": chunk["conversion"],
            "qc_flag": chunk["qc_conversion_flag"],
            "source_quality": chunk["tier"],
            "flags_json": [
                flags_to_json(
                    {
                        "organization": organization,
                        "location_type": location_type,
                        "resolved_location_type": resolved_location_type,
                        "depth_flag": depth_flag,
                        "mdl_flag": mdl_flag,
                        "approx_flag": approx_flag,
                        "greater_flag": greater_flag,
                        "tier": tier,
                        "field_flag": field_flag,
                        "datum": datum,
                        "conversion_qc": conversion_qc,
                    }
                )
                for organization,
                location_type,
                resolved_location_type,
                depth_flag,
                mdl_flag,
                approx_flag,
                greater_flag,
                tier,
                field_flag,
                datum,
                conversion_qc in zip(
                    chunk["OrganizationIdentifier"],
                    chunk["MonitoringLocationTypeName"],
                    chunk["ResolvedMonitoringLocationTypeName"],
                    chunk["depth_flag"],
                    chunk["mdl_flag"],
                    chunk["approx_flag"],
                    chunk["greater_flag"],
                    chunk["tier"],
                    chunk["field_flag"],
                    chunk["datum"],
                    chunk["qc_conversion_flag"],
                    strict=False,
                )
            ],
        }
    )
    return enforce_schema(out)


def build_observations(
    source_config: dict[str, Any],
    variables_config: dict[str, Any],
    *,
    chunksize: int = 250_000,
    max_rows: int | None = None,
) -> pd.DataFrame:
    raw_path = Path(source_config["raw_path"])
    frames: list[pd.DataFrame] = []
    rows_seen = 0
    for chunk in pd.read_csv(raw_path, usecols=USECOLS, chunksize=chunksize, nrows=max_rows, low_memory=False):
        frames.append(
            _convert_chunk(
                chunk,
                variables_config,
                raw_path,
                row_offset=rows_seen,
            )
        )
        rows_seen += len(chunk)

    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return empty_canonical_frame()
    return enforce_schema(pd.concat(frames, ignore_index=True))


def iter_observation_chunks(
    source_config: dict[str, Any],
    variables_config: dict[str, Any],
    *,
    chunksize: int = 250_000,
    max_rows: int | None = None,
    skip_rows: int = 0,
):
    raw_path = Path(source_config["raw_path"])
    rows_seen = skip_rows
    if max_rows is not None and skip_rows >= max_rows:
        return
    nrows = None if max_rows is None else max_rows - skip_rows
    skiprows = list(range(1, skip_rows + 1)) if skip_rows else None
    for chunk_index, chunk in enumerate(
        pd.read_csv(
            raw_path.as_posix(),
            usecols=list(USECOLS),
            chunksize=chunksize,
            nrows=nrows,
            skiprows=skiprows,
            low_memory=False,
        )
    ):
        raw_start = rows_seen
        raw_end = rows_seen + len(chunk)
        frame = _convert_chunk(
            chunk,
            variables_config,
            raw_path,
            row_offset=rows_seen,
        )
        rows_seen = raw_end
        yield ObservationChunk(
            frame=frame,
            unit_id=f"{raw_path.as_posix()}:{raw_start}:{raw_end}",
            unit_index=chunk_index,
            raw_start=raw_start,
            raw_end=raw_end,
        )
