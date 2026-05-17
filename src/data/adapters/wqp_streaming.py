"""Streaming adapter for Water Quality Portal WQX3 results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.data.adapters.common import (
    ObservationChunk,
    convert_canonical_value,
    convert_depth_m,
    empty_canonical_frame,
    enforce_schema,
    flags_to_json,
    namespaced_site_id,
    year_month_from_datetime,
)


USECOLS = [
    "Org_Identifier",
    "Org_FormalName",
    "Location_Identifier",
    "Location_Name",
    "Location_Type",
    "Location_State",
    "Location_CountryName",
    "Location_LatitudeStandardized",
    "Location_LongitudeStandardized",
    "Activity_ActivityIdentifier",
    "Activity_TypeCode",
    "Activity_Media",
    "Activity_StartDate",
    "Activity_StartTime",
    "Activity_StartTimeZone",
    "Activity_DepthHeightMeasure",
    "Activity_DepthHeightMeasureUnit",
    "Result_ResultDetectionCondition",
    "Result_Characteristic",
    "Result_CharacteristicComparable",
    "ResultDepthHeight_Measure",
    "ResultDepthHeight_MeasureUnit",
    "Result_MeasureIdentifier",
    "Result_Measure",
    "Result_MeasureUnit",
    "Result_MeasureQualifierCode",
    "Result_MeasureStatusIdentifier",
    "ProviderName",
    "LastChangeDate",
]


def _build_characteristic_map(variables_config: dict[str, Any]) -> dict[str, str]:
    mapping = variables_config["source_mappings"]["wqp"]["variables"]
    characteristic_map: dict[str, str] = {}
    for canonical, spec in mapping.items():
        for characteristic in spec["characteristics"]:
            characteristic_map[characteristic.lower()] = canonical
    return characteristic_map


def _canonical_for_row(row: pd.Series, characteristic_map: dict[str, str]) -> str | None:
    for column in ("Result_Characteristic", "Result_CharacteristicComparable"):
        value = row.get(column)
        if value is None or pd.isna(value):
            continue
        canonical = characteristic_map.get(str(value).strip().lower())
        if canonical:
            return canonical
    return None


def _sample_datetime(chunk: pd.DataFrame) -> pd.Series:
    date = chunk["Activity_StartDate"].fillna("").astype(str).str.strip()
    time = chunk["Activity_StartTime"].fillna("").astype(str).str.strip()
    combined = date.where(time.eq(""), date + " " + time)
    return pd.to_datetime(combined, errors="coerce", utc=True, format="mixed")


def _depth_m(row: pd.Series) -> float | None:
    result_depth = convert_depth_m(row.get("ResultDepthHeight_Measure"), row.get("ResultDepthHeight_MeasureUnit"))
    if result_depth is not None:
        return result_depth
    return convert_depth_m(row.get("Activity_DepthHeightMeasure"), row.get("Activity_DepthHeightMeasureUnit"))


def _convert_chunk(
    chunk: pd.DataFrame,
    variables_config: dict[str, Any],
    source_file: Path,
    characteristic_map: dict[str, str],
    *,
    row_offset: int,
) -> pd.DataFrame:
    chunk = chunk.copy()
    chunk["raw_row_index"] = chunk.index + row_offset
    chunk["variable_canonical"] = chunk.apply(
        lambda row: _canonical_for_row(row, characteristic_map),
        axis=1,
    )
    chunk = chunk[chunk["variable_canonical"].notna()].copy()
    if chunk.empty:
        return empty_canonical_frame()
    chunk = chunk.reset_index(drop=True)

    converted = chunk.apply(
        lambda row: convert_canonical_value(
            row["Result_Measure"],
            row["Result_MeasureUnit"],
            row["variable_canonical"],
            variables_config,
        ),
        axis=1,
    )
    chunk["value_canonical"] = converted.apply(lambda item: item.value)
    chunk["conversion"] = converted.apply(lambda item: item.conversion)
    chunk["qc_conversion_flag"] = converted.apply(lambda item: item.qc_flag)

    sample_datetime = _sample_datetime(chunk)
    site_id_source = chunk["Location_Identifier"].astype(str)
    out = pd.DataFrame(
        {
            "source_id": "wqp",
            "source_file": source_file.as_posix(),
            "source_row_id": "wqp_results:" + chunk["raw_row_index"].astype(str),
            "site_id_source": site_id_source,
            "site_id": site_id_source.apply(lambda value: namespaced_site_id("wqp", value)),
            "site_name": chunk["Location_Name"],
            "sample_datetime": sample_datetime.dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "year_month": year_month_from_datetime(sample_datetime),
            "latitude": pd.to_numeric(chunk["Location_LatitudeStandardized"], errors="coerce"),
            "longitude": pd.to_numeric(chunk["Location_LongitudeStandardized"], errors="coerce"),
            "depth_m": chunk.apply(_depth_m, axis=1),
            "variable_raw": chunk["Result_Characteristic"],
            "variable_canonical": chunk["variable_canonical"],
            "value_raw": chunk["Result_Measure"],
            "unit_raw": chunk["Result_MeasureUnit"],
            "value_canonical": chunk["value_canonical"],
            "unit_canonical": chunk["variable_canonical"].apply(
                lambda variable: variables_config["canonical_variables"][variable]["canonical_unit"]
            ),
            "conversion": chunk["conversion"],
            "qc_flag": chunk["qc_conversion_flag"],
            "source_quality": chunk["Result_MeasureStatusIdentifier"],
            "flags_json": [
                flags_to_json(
                    {
                        "org_identifier": org_identifier,
                        "org_formal_name": org_formal_name,
                        "provider": provider,
                        "location_type": location_type,
                        "state": state,
                        "country": country,
                        "activity_identifier": activity_identifier,
                        "activity_type": activity_type,
                        "activity_media": activity_media,
                        "activity_time_zone": activity_tz,
                        "detection_condition": detection_condition,
                        "measure_qualifier": qualifier,
                        "measure_status": status,
                        "comparable_characteristic": comparable,
                        "last_change_date": last_change,
                        "conversion_qc": conversion_qc,
                    }
                )
                for org_identifier,
                org_formal_name,
                provider,
                location_type,
                state,
                country,
                activity_identifier,
                activity_type,
                activity_media,
                activity_tz,
                detection_condition,
                qualifier,
                status,
                comparable,
                last_change,
                conversion_qc in zip(
                    chunk["Org_Identifier"],
                    chunk["Org_FormalName"],
                    chunk["ProviderName"],
                    chunk["Location_Type"],
                    chunk["Location_State"],
                    chunk["Location_CountryName"],
                    chunk["Activity_ActivityIdentifier"],
                    chunk["Activity_TypeCode"],
                    chunk["Activity_Media"],
                    chunk["Activity_StartTimeZone"],
                    chunk["Result_ResultDetectionCondition"],
                    chunk["Result_MeasureQualifierCode"],
                    chunk["Result_MeasureStatusIdentifier"],
                    chunk["Result_CharacteristicComparable"],
                    chunk["LastChangeDate"],
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
    raw_path = Path(source_config["raw_path"]) / source_config["format"]["main_files"]["results"]
    characteristic_map = _build_characteristic_map(variables_config)
    frames: list[pd.DataFrame] = []
    rows_seen = 0
    for chunk in pd.read_csv(raw_path, usecols=USECOLS, chunksize=chunksize, nrows=max_rows, low_memory=False):
        frames.append(
            _convert_chunk(
                chunk,
                variables_config,
                raw_path,
                characteristic_map,
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
    raw_path = Path(source_config["raw_path"]) / source_config["format"]["main_files"]["results"]
    characteristic_map = _build_characteristic_map(variables_config)
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
            characteristic_map,
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
