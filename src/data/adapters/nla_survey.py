"""Adapter for EPA National Lakes Assessment survey-level data."""

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
from src.pandas_utils import dataframe_rows


COMBINED_USECOLS = [
    "PUBLICATION_DATE",
    "UNIQUE_ID",
    "UID",
    "SITE_ID",
    "VISIT_NO",
    "IND_DOMAIN",
    "DSGN_CYCLE",
    "PSTL_CODE",
    "AG_ECO9",
    "AG_ECO9_NM",
    "AG_ECO3",
    "AG_ECO3_NM",
    "EPA_REG",
    "MAJ_BASIN",
    "MAJ_BAS_NM",
    "MIS_BASIN",
    "MIS_BAS_NM",
    "LAT_DD83",
    "LON_DD83",
    "LAKE_ORGN",
    "TNT_CAT",
    "CHLA_COND",
    "DIS_O2_CLS",
    "PTL_COND",
    "NTL_COND",
    "TROPHIC_STATE",
    "CHLA_MDL",
    "CHLA_NARS_FLAG",
    "CHLA_RESULT",
    "DO_SURF",
    "NTL_MDL",
    "NTL_NARS_FLAG",
    "NTL_RESULT",
    "PTL_MDL",
    "PTL_NARS_FLAG",
    "PTL_RESULT",
]


SITE_METADATA_2007_USECOLS = [
    "SITE_ID",
    "VISIT_NO",
    "NHDNAME",
    "LAKENAME",
    "HUC_8",
    "REACHCODE",
    "COM_ID",
]

VARIABLE_SPECS: list[dict[str, str | None]] = [
    {
        "raw": "CHLA_RESULT",
        "canonical": "chlorophyll_a_ugL",
        "unit": "ug/L",
        "flag": "CHLA_NARS_FLAG",
        "mdl": "CHLA_MDL",
        "condition": "CHLA_COND",
    },
    {
        "raw": "NTL_RESULT",
        "canonical": "TN_ugL",
        "unit": "mg/L",
        "flag": "NTL_NARS_FLAG",
        "mdl": "NTL_MDL",
        "condition": "NTL_COND",
    },
    {
        "raw": "PTL_RESULT",
        "canonical": "TP_ugL",
        "unit": "ug/L",
        "flag": "PTL_NARS_FLAG",
        "mdl": "PTL_MDL",
        "condition": "PTL_COND",
    },
    {
        "raw": "DO_SURF",
        "canonical": "DO_mgL",
        "unit": "mg/L",
        "flag": None,
        "mdl": None,
        "condition": "DIS_O2_CLS",
    },
]


DateLookup = dict[str, dict[tuple[str, ...], tuple[str, str]]]
SiteMetadataLookup = dict[tuple[str, str, str], dict[str, str | None]]


def _main_file(source_config: dict[str, Any]) -> Path:
    raw_root = Path(source_config["raw_path"])
    return raw_root / source_config["format"]["main_files"]["combined_population_estimates"]


def _clean_key(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _add_uid_lookup(lookup: DateLookup, *, cycle: str, uid: Any, date_raw: Any, source_file: Path) -> None:
    uid_key = _clean_key(uid)
    date_text = _clean_key(date_raw)
    if uid_key and date_text:
        lookup["uid"][(cycle, uid_key)] = (date_text, source_file.as_posix())


def _add_site_visit_lookup(
    lookup: DateLookup,
    *,
    cycle: str,
    site_id: Any,
    visit_no: Any,
    date_raw: Any,
    source_file: Path,
) -> None:
    site_key = _clean_key(site_id)
    visit_key = _clean_key(visit_no)
    date_text = _clean_key(date_raw)
    if site_key and visit_key and date_text:
        lookup["site_visit"][(cycle, site_key, visit_key)] = (date_text, source_file.as_posix())


def _load_date_lookup(source_config: dict[str, Any]) -> DateLookup:
    raw_root = Path(source_config["raw_path"])
    lookup: DateLookup = {"uid": {}, "site_visit": {}}

    sample_grid_2022 = raw_root / source_config["format"]["date_files"]["sample_grid_2022"]
    if sample_grid_2022.exists():
        frame = pd.read_csv(
            sample_grid_2022,
            usecols=["UID", "SITE_ID", "VISIT_NO", "DATE_COL"],
            low_memory=False,
        )
        for row in dataframe_rows(frame):
            _add_uid_lookup(lookup, cycle="2022", uid=row.UID, date_raw=row.DATE_COL, source_file=sample_grid_2022)
            _add_site_visit_lookup(
                lookup,
                cycle="2022",
                site_id=row.SITE_ID,
                visit_no=row.VISIT_NO,
                date_raw=row.DATE_COL,
                source_file=sample_grid_2022,
            )

    sampled_lake_2007 = raw_root / source_config["format"]["date_files"]["sampled_lake_information_2007"]
    if sampled_lake_2007.exists():
        frame = pd.read_csv(
            sampled_lake_2007,
            usecols=["SITE_ID", "VISIT_NO", "DATE_COL"],
            low_memory=False,
        )
        for row in dataframe_rows(frame):
            _add_site_visit_lookup(
                lookup,
                cycle="2007",
                site_id=row.SITE_ID,
                visit_no=row.VISIT_NO,
                date_raw=row.DATE_COL,
                source_file=sampled_lake_2007,
            )

    return lookup


def _clean_optional_text(value: Any) -> str | None:
    text = _clean_key(value)
    if not text or text.upper() in {"NA", "N/A", "NONE", "NULL", "NAN"}:
        return None
    return text


def _best_site_name(metadata: dict[str, str | None] | None) -> str | None:
    if metadata is None:
        return None
    return metadata.get("lake_name_field") or metadata.get("lake_name_nhd")


def _load_site_metadata_lookup(source_config: dict[str, Any]) -> SiteMetadataLookup:
    raw_root = Path(source_config["raw_path"])
    lookup: SiteMetadataLookup = {}
    sampled_lake_2007 = raw_root / source_config["format"]["date_files"]["sampled_lake_information_2007"]
    if not sampled_lake_2007.exists():
        return lookup

    frame = pd.read_csv(
        sampled_lake_2007,
        usecols=lambda column: column in SITE_METADATA_2007_USECOLS,
        dtype=str,
        low_memory=False,
    )
    required = {"SITE_ID", "VISIT_NO"}
    if not required.issubset(frame.columns):
        return lookup

    for row in dataframe_rows(frame):
        site_key = _clean_key(row.SITE_ID)
        visit_key = _clean_key(row.VISIT_NO)
        if not site_key or not visit_key:
            continue
        metadata = {
            "lake_name_nhd": _clean_optional_text(getattr(row, "NHDNAME", None)),
            "lake_name_field": _clean_optional_text(getattr(row, "LAKENAME", None)),
            "huc_8": _clean_optional_text(getattr(row, "HUC_8", None)),
            "reachcode": _clean_optional_text(getattr(row, "REACHCODE", None)),
            "com_id": _clean_optional_text(getattr(row, "COM_ID", None)),
        }
        lookup[("2007", site_key, visit_key)] = metadata
    return lookup


def _metadata_for_chunk(chunk: pd.DataFrame, metadata_lookup: SiteMetadataLookup) -> list[dict[str, str | None]]:
    metadata_rows = []
    for row in dataframe_rows(chunk):
        cycle = _clean_key(getattr(row, "DSGN_CYCLE"))
        site_id = _clean_key(getattr(row, "SITE_ID"))
        visit_no = _clean_key(getattr(row, "VISIT_NO"))
        metadata_rows.append(metadata_lookup.get((cycle, site_id, visit_no), {}))
    return metadata_rows


def _sample_date_fields(chunk: pd.DataFrame, date_lookup: DateLookup) -> pd.DataFrame:
    raw_dates: list[str | None] = []
    date_sources: list[str | None] = []
    policies: list[str] = []
    datetime_labels: list[str | None] = []

    for row in dataframe_rows(chunk):
        cycle = _clean_key(getattr(row, "DSGN_CYCLE"))
        uid = _clean_key(getattr(row, "UID"))
        site_id = _clean_key(getattr(row, "SITE_ID"))
        visit_no = _clean_key(getattr(row, "VISIT_NO"))

        match = date_lookup["uid"].get((cycle, uid)) if uid else None
        if match is None and site_id and visit_no:
            match = date_lookup["site_visit"].get((cycle, site_id, visit_no))

        if match is not None:
            date_text, date_source = match
            raw_dates.append(date_text)
            date_sources.append(date_source)
            policies.append("exact_date_col_joined")
            datetime_labels.append(date_text)
            continue

        raw_dates.append(None)
        date_sources.append(None)
        policies.append("survey_year_nominal_month")
        datetime_labels.append(f"{cycle}-07-01" if cycle else None)

    sample_datetime = pd.to_datetime(datetime_labels, errors="coerce", utc=True, format="mixed")
    return pd.DataFrame(
        {
            "sample_datetime": sample_datetime,
            "sample_date_raw": raw_dates,
            "sample_date_source_file": date_sources,
            "sample_date_policy": policies,
        },
        index=chunk.index,
    )


def _site_id_source(chunk: pd.DataFrame) -> pd.Series:
    unique_id = chunk["UNIQUE_ID"].astype("string")
    site_id = chunk["SITE_ID"].astype("string")
    return unique_id.where(unique_id.notna() & (unique_id.str.len() > 0), site_id)


def _series_or_none(chunk: pd.DataFrame, column: str | None) -> pd.Series:
    if column and column in chunk.columns:
        return chunk[column]
    return pd.Series([None] * len(chunk), index=chunk.index)


def _convert_variable(
    chunk: pd.DataFrame,
    variables_config: dict[str, Any],
    source_file: Path,
    spec: dict[str, str | None],
    date_fields: pd.DataFrame,
    site_metadata: list[dict[str, str | None]],
) -> pd.DataFrame:
    raw_column = str(spec["raw"])
    canonical = str(spec["canonical"])
    unit = str(spec["unit"])
    flag_column = spec.get("flag")
    mdl_column = spec.get("mdl")
    condition_column = spec.get("condition")

    converted = chunk.apply(
        lambda row: convert_canonical_value(
            row[raw_column],
            unit,
            canonical,
            variables_config,
        ),
        axis=1,
    )

    site_id_source = _site_id_source(chunk)
    source_quality = _series_or_none(chunk, flag_column).fillna(_series_or_none(chunk, condition_column))

    flags_json = [
        flags_to_json(
            {
                "uid": uid,
                "site_id": raw_site_id,
                "visit_no": visit_no,
                "survey_cycle": survey_cycle,
                "publication_date": publication_date,
                "indicator_domain": indicator_domain,
                "target_status": target_status,
                "state": state,
                "epa_region": epa_region,
                "ag_eco3": ag_eco3,
                "ag_eco3_name": ag_eco3_name,
                "ag_eco9": ag_eco9,
                "ag_eco9_name": ag_eco9_name,
                "major_basin": major_basin,
                "major_basin_name": major_basin_name,
                "mississippi_basin": mississippi_basin,
                "mississippi_basin_name": mississippi_basin_name,
                "lake_origin": lake_origin,
                "lake_name_nhd": metadata.get("lake_name_nhd"),
                "lake_name_field": metadata.get("lake_name_field"),
                "huc_8": metadata.get("huc_8"),
                "reachcode": metadata.get("reachcode"),
                "com_id": metadata.get("com_id"),
                "nars_flag": nars_flag,
                "method_detection_limit": method_detection_limit,
                "condition": condition,
                "sample_date_policy": sample_date_policy,
                "sample_date_raw": sample_date_raw,
                "sample_date_source_file": sample_date_source_file,
                "conversion_qc": conversion_qc,
            }
        )
        for uid,
        raw_site_id,
        visit_no,
        survey_cycle,
        publication_date,
        indicator_domain,
        target_status,
        state,
        epa_region,
        ag_eco3,
        ag_eco3_name,
        ag_eco9,
        ag_eco9_name,
        major_basin,
        major_basin_name,
        mississippi_basin,
        mississippi_basin_name,
        lake_origin,
        metadata,
        nars_flag,
        method_detection_limit,
        condition,
        sample_date_policy,
        sample_date_raw,
        sample_date_source_file,
        conversion_qc in zip(
            chunk["UID"],
            chunk["SITE_ID"],
            chunk["VISIT_NO"],
            chunk["DSGN_CYCLE"],
            chunk["PUBLICATION_DATE"],
            chunk["IND_DOMAIN"],
            chunk["TNT_CAT"],
            chunk["PSTL_CODE"],
            chunk["EPA_REG"],
            chunk["AG_ECO3"],
            chunk["AG_ECO3_NM"],
            chunk["AG_ECO9"],
            chunk["AG_ECO9_NM"],
            chunk["MAJ_BASIN"],
            chunk["MAJ_BAS_NM"],
            chunk["MIS_BASIN"],
            chunk["MIS_BAS_NM"],
            chunk["LAKE_ORGN"],
            site_metadata,
            _series_or_none(chunk, flag_column),
            _series_or_none(chunk, mdl_column),
            _series_or_none(chunk, condition_column),
            date_fields["sample_date_policy"],
            date_fields["sample_date_raw"],
            date_fields["sample_date_source_file"],
            converted.apply(lambda item: item.qc_flag),
            strict=False,
        )
    ]

    out = pd.DataFrame(
        {
            "source_id": "nla",
            "source_file": source_file.as_posix(),
            "source_row_id": (
                "nla_population_estimates:"
                + chunk["raw_row_index"].astype(str)
                + ":"
                + raw_column
            ),
            "site_id_source": site_id_source,
            "site_id": site_id_source.apply(lambda value: namespaced_site_id("nla", value)),
            "site_name": pd.Series([_best_site_name(metadata) for metadata in site_metadata], index=chunk.index),
            "sample_datetime": date_fields["sample_datetime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "year_month": year_month_from_datetime(date_fields["sample_datetime"]),
            "latitude": pd.to_numeric(chunk["LAT_DD83"], errors="coerce"),
            "longitude": pd.to_numeric(chunk["LON_DD83"], errors="coerce"),
            "depth_m": None,
            "variable_raw": raw_column,
            "variable_canonical": canonical,
            "value_raw": chunk[raw_column],
            "unit_raw": unit,
            "value_canonical": converted.apply(lambda item: item.value),
            "unit_canonical": variables_config["canonical_variables"][canonical]["canonical_unit"],
            "conversion": converted.apply(lambda item: item.conversion),
            "qc_flag": converted.apply(lambda item: item.qc_flag),
            "source_quality": source_quality,
            "flags_json": flags_json,
        }
    )
    return enforce_schema(out)


def _convert_chunk(
    chunk: pd.DataFrame,
    variables_config: dict[str, Any],
    source_file: Path,
    date_lookup: DateLookup,
    metadata_lookup: SiteMetadataLookup,
    *,
    row_offset: int,
) -> pd.DataFrame:
    chunk = chunk.copy()
    chunk["raw_row_index"] = range(row_offset, row_offset + len(chunk))
    date_fields = _sample_date_fields(chunk, date_lookup)
    site_metadata = _metadata_for_chunk(chunk, metadata_lookup)
    frames = [_convert_variable(chunk, variables_config, source_file, spec, date_fields, site_metadata) for spec in VARIABLE_SPECS]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return empty_canonical_frame()
    return enforce_schema(pd.concat(frames, ignore_index=True))


def build_observations(
    source_config: dict[str, Any],
    variables_config: dict[str, Any],
    *,
    chunksize: int = 250_000,
    max_rows: int | None = None,
) -> pd.DataFrame:
    raw_path = _main_file(source_config)
    date_lookup = _load_date_lookup(source_config)
    metadata_lookup = _load_site_metadata_lookup(source_config)
    frames: list[pd.DataFrame] = []
    rows_seen = 0
    for chunk in pd.read_csv(raw_path, usecols=COMBINED_USECOLS, chunksize=chunksize, nrows=max_rows, low_memory=False):
        frames.append(
            _convert_chunk(
                chunk,
                variables_config,
                raw_path,
                date_lookup,
                metadata_lookup,
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
    raw_path = _main_file(source_config)
    date_lookup = _load_date_lookup(source_config)
    metadata_lookup = _load_site_metadata_lookup(source_config)
    rows_seen = skip_rows
    if max_rows is not None and skip_rows >= max_rows:
        return
    nrows = None if max_rows is None else max_rows - skip_rows
    skiprows = list(range(1, skip_rows + 1)) if skip_rows else None
    for chunk_index, chunk in enumerate(
        pd.read_csv(
            raw_path.as_posix(),
            usecols=list(COMBINED_USECOLS),
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
            date_lookup,
            metadata_lookup,
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
