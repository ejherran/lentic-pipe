#!/usr/bin/env python
"""Build the Closure V2 fresh-primary input-only evaluation bundle.

The builder has two deliberate publication stages. ``--materialize-data``
writes only the four heavy Parquet payloads. After DVC pointers have been
created, ``--execute`` reconstructs and verifies every byte, then publishes
the cohort records and completion manifest. Neither stage opens the target
namespace, observed Chl-a columns, target availability, or outcome values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import math
import os
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.experiments.closure_contract import ClosureContractError, load_yaml_mapping
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT
from src.experiments.closure_v2.contracts import validate_evaluation_cohorts
from src.experiments.closure_v2.hashing import canonical_json_bytes, file_record, md5_file, sha256_file
from src.experiments.closure_v2.lock_models import MODEL_LOCK_PATH, load_effective_model_lock


COHORT_CONFIG = Path("configs/closure_v2/evaluation_cohorts.yaml")
ASSIGNMENT_PATH = Path("data/closure_v1/closure_holdout_assignment.csv")
PANEL_PATH = Path("data/panel/panel_monthly_v0.parquet")
OUTCOME_LOG = Path("reports/closure_v2/00_protocol/outcome_access_log.jsonl")

INVENTORY_PATH = Path("reports/closure_v2/00_protocol/fresh_candidate_inventory.csv")
DECISION_PATH = Path("reports/closure_v2/00_protocol/fresh_cohort_decision.json")
COHORT_MANIFEST_PATH = Path("reports/closure_v2/00_protocol/fresh_cohort_manifest.json")
INPUT_MANIFEST_PATH = Path("reports/closure_v2/01_surface/locked_evaluation_input_manifest.json")

PHYSICAL_PATHS = (
    Path("data/closure_v2/locked_evaluation/input_history.parquet"),
    Path("data/closure_v2/locked_evaluation/intent_origins.parquet"),
    Path("data/closure_v2/locked_evaluation/origin_features.parquet"),
    Path("data/closure_v2/locked_evaluation/sequence_features.parquet"),
)
POINTER_PATHS = tuple(path.with_suffix(path.suffix + ".dvc") for path in PHYSICAL_PATHS)
LIGHT_PATHS = (INVENTORY_PATH, DECISION_PATH, COHORT_MANIFEST_PATH, INPUT_MANIFEST_PATH)

HISTORY_LENGTH = 12
HORIZONS = (1, 2, 3)
EXPECTED_LOCATIONS = 137
EXPECTED_ORIGINS = 2_286
EXPECTED_KEY_DIGEST = "347bb61867813327351cdc4c896cd50695ab02a84fa52d256a31e8a280323952"

NUTRIENT_ELIGIBILITY_COLUMNS = ("mean_TP_ugL", "mean_TN_ugL", "TN_TP_ratio")
PHYSICOCHEMICAL_ELIGIBILITY_COLUMNS = (
    "mean_DO_mgL",
    "mean_pH",
    "mean_turbidity_NTU",
    "mean_secchi_depth_m",
)
THERMAL_ELIGIBILITY_COLUMNS = ("mean_temperature_C",)
PHYSICAL_FEATURE_COLUMNS = (
    "mean_TP_ugL", "std_TP_ugL", "n_obs_TP_ugL", "n_bad_TP_ugL", "qc_ok_rate_TP_ugL",
    "mean_TN_ugL", "std_TN_ugL", "n_obs_TN_ugL", "n_bad_TN_ugL", "qc_ok_rate_TN_ugL",
    "mean_temperature_C", "std_temperature_C", "n_obs_temperature_C", "n_bad_temperature_C", "qc_ok_rate_temperature_C",
    "mean_secchi_depth_m", "std_secchi_depth_m", "n_obs_secchi_depth_m", "n_bad_secchi_depth_m", "qc_ok_rate_secchi_depth_m",
    "mean_turbidity_NTU", "std_turbidity_NTU", "n_obs_turbidity_NTU", "n_bad_turbidity_NTU", "qc_ok_rate_turbidity_NTU",
    "mean_DO_mgL", "std_DO_mgL", "n_obs_DO_mgL", "n_bad_DO_mgL", "qc_ok_rate_DO_mgL",
    "mean_pH", "std_pH", "n_obs_pH", "n_bad_pH", "qc_ok_rate_pH",
    "log_TP", "log_TN", "TN_TP_ratio",
)
CALENDAR_COLUMNS = (
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
)
PANEL_PROJECTION = ("source_id", "site_id", "year_month", *PHYSICAL_FEATURE_COLUMNS)
COMMON_COLUMNS = (
    "origin_id",
    "source_id",
    "site_id",
    "evaluation_cohort",
    "cohort_route",
    "origin_year_month",
    "base_input_status",
    "base_input_reason",
)
INTENT_COLUMNS = (
    *COMMON_COLUMNS,
    "history_start_year_month",
    "history_end_year_month",
    "history_length_months",
    "history_row_count",
    "missing_history_row_count",
)
HISTORY_COLUMNS = (
    *COMMON_COLUMNS,
    "history_year_month",
    "history_offset_months",
    "row_present",
    *PHYSICAL_FEATURE_COLUMNS,
    *CALENDAR_COLUMNS,
)
ORIGIN_COLUMNS = (*COMMON_COLUMNS, "row_present", *PHYSICAL_FEATURE_COLUMNS, *CALENDAR_COLUMNS)
SEQUENCE_COLUMNS = (
    *COMMON_COLUMNS,
    "sequence_length",
    "sequence_row_present",
    *(f"sequence_{column}" for column in (*PHYSICAL_FEATURE_COLUMNS, *CALENDAR_COLUMNS)),
)
TABLE_KEYS = ("input_history", "intent_origins", "origin_features", "sequence_features")
TABLE_COLUMNS = dict(zip(TABLE_KEYS, (HISTORY_COLUMNS, INTENT_COLUMNS, ORIGIN_COLUMNS, SEQUENCE_COLUMNS), strict=True))
FORBIDDEN_COLUMN_TOKENS = (
    "target", "chlorophyll", "chla", "outcome", "availability", "evaluable",
    "prediction", "metric", "horizon", "chl_a",
)


class EvaluationInputError(ClosureContractError):
    """Raised when the fresh-primary input-only contract cannot be certified."""


def _require_regular(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise EvaluationInputError(f"Required regular file is absent: {relative}")
    return path


def _month_index(value: Any) -> int:
    text = str(value)[:7]
    try:
        year, month = (int(part) for part in text.split("-"))
    except (TypeError, ValueError) as error:
        raise EvaluationInputError(f"Malformed year_month: {value!r}") from error
    if len(text) != 7 or month < 1 or month > 12:
        raise EvaluationInputError(f"Malformed year_month: {value!r}")
    return year * 12 + month - 1


def _month_text(index: int) -> str:
    year, month = divmod(index, 12)
    return f"{year:04d}-{month + 1:02d}"


def _finite(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def input_month_eligible(row: Mapping[str, Any]) -> bool:
    """Require observable support for N, F, and no-current thermal modules."""
    required = {
        *NUTRIENT_ELIGIBILITY_COLUMNS,
        *PHYSICOCHEMICAL_ELIGIBILITY_COLUMNS,
        *THERMAL_ELIGIBILITY_COLUMNS,
    }
    if not required.issubset(row):
        raise EvaluationInputError("Input-month projection is missing a module feature")
    return (
        any(_finite(row[column]) for column in NUTRIENT_ELIGIBILITY_COLUMNS)
        and any(_finite(row[column]) for column in PHYSICOCHEMICAL_ELIGIBILITY_COLUMNS)
        and all(_finite(row[column]) for column in THERMAL_ELIGIBILITY_COLUMNS)
    )


def _calendar_features(month_index: int) -> dict[str, float]:
    phase = 2.0 * math.pi * (month_index % 12) / 12.0
    return {
        "season_sin_annual": math.sin(phase),
        "season_cos_annual": math.cos(phase),
        "season_sin_semiannual": math.sin(2.0 * phase),
        "season_cos_semiannual": math.cos(2.0 * phase),
    }


def _feature_value(value: Any) -> float | None:
    return float(value) if _finite(value) else None


def _origin_id(source_id: str, site_id: str, origin: str) -> str:
    return hashlib.sha256("\x00".join((source_id, site_id, origin)).encode("utf-8")).hexdigest()


def _candidate_digest(keys: Sequence[tuple[str, str, str]]) -> str:
    digest = hashlib.sha256()
    for key in keys:
        digest.update("\x00".join(key).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _source_hashes(root: Path, audit: Mapping[str, Any]) -> dict[str, str]:
    observed = {
        "panel_sha256": sha256_file(_require_regular(root, PANEL_PATH)),
        "v1_assignment_sha256": sha256_file(_require_regular(root, ASSIGNMENT_PATH)),
    }
    for key, value in observed.items():
        if value != audit.get(key):
            raise EvaluationInputError(f"Fresh-primary source hash drifted: {key}")
    return observed


def _load_inputs(root: Path) -> tuple[set[tuple[str, str]], list[dict[str, Any]]]:
    assignment = _require_regular(root, ASSIGNMENT_PATH)
    with assignment.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"source_id", "site_id"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise EvaluationInputError("V1 assignment key projection drifted")
        v1_keys = {(str(row["source_id"]), str(row["site_id"])) for row in reader}
    if len(v1_keys) != 441:
        raise EvaluationInputError(f"V1 location universe drifted: {len(v1_keys)}")

    panel = _require_regular(root, PANEL_PATH)
    table = pq.read_table(
        panel,
        columns=list(PANEL_PROJECTION),
        filters=[("source_id", "=", "wqp")],
    )
    if tuple(table.column_names) != PANEL_PROJECTION:
        raise EvaluationInputError("Panel scanner projection drifted")
    return v1_keys, [cast(dict[str, Any], row) for row in table.to_pylist()]


def reconstruct_fresh_primary(
    v1_keys: set[tuple[str, str]],
    panel_rows: Sequence[Mapping[str, Any]],
    *,
    origin_start: str,
    origin_end: str,
) -> dict[str, Any]:
    """Reconstruct the predeclared cohort using input/provenance fields only."""
    panel_by_key: dict[tuple[str, str, int], dict[str, float | None]] = {}
    site_months: dict[tuple[str, str], set[int]] = defaultdict(set)
    eligible_months: dict[tuple[str, str], set[int]] = defaultdict(set)
    for raw in panel_rows:
        if set(raw) != set(PANEL_PROJECTION):
            raise EvaluationInputError("Panel row projection dialect drifted")
        source_id, site_id = str(raw["source_id"]), str(raw["site_id"])
        month = _month_index(raw["year_month"])
        key = (source_id, site_id, month)
        if key in panel_by_key:
            raise EvaluationInputError("Panel contains duplicate source/site/month rows")
        panel_by_key[key] = {column: _feature_value(raw[column]) for column in PHYSICAL_FEATURE_COLUMNS}
        site_key = (source_id, site_id)
        site_months[site_key].add(month)
        if input_month_eligible(raw):
            eligible_months[site_key].add(month)

    start, end = _month_index(origin_start), _month_index(origin_end)
    candidate_keys: list[tuple[str, str, str]] = []
    for site_key in sorted(site_months, key=lambda key: (key[0].encode("utf-8"), key[1].encode("utf-8"))):
        if site_key in v1_keys:
            continue
        observed = site_months[site_key]
        eligible = eligible_months[site_key]
        upper = max(observed)
        for origin_index in range(start, end + 1):
            history = range(origin_index - HISTORY_LENGTH + 1, origin_index + 1)
            if origin_index + max(HORIZONS) <= upper and all(month in eligible for month in history):
                candidate_keys.append((site_key[0], site_key[1], _month_text(origin_index)))

    digest = _candidate_digest(candidate_keys)
    locations = {key[:2] for key in candidate_keys}
    if len(locations) != EXPECTED_LOCATIONS or len(candidate_keys) != EXPECTED_ORIGINS:
        raise EvaluationInputError(
            "Fresh-primary reconstruction contradicted the sealed counts: "
            f"locations={len(locations)}, origins={len(candidate_keys)}"
        )
    if digest != EXPECTED_KEY_DIGEST:
        raise EvaluationInputError(f"Fresh-primary candidate digest drifted: {digest}")
    if locations & v1_keys:
        raise EvaluationInputError("Fresh-primary overlaps the V1 location universe")

    intents: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    origin_rows: list[dict[str, Any]] = []
    sequence_rows: list[dict[str, Any]] = []
    by_site: dict[tuple[str, str], list[str]] = defaultdict(list)
    for source_id, site_id, origin in candidate_keys:
        by_site[(source_id, site_id)].append(origin)
        origin_index = _month_index(origin)
        month_indices = list(range(origin_index - HISTORY_LENGTH + 1, origin_index + 1))
        common = {
            "origin_id": _origin_id(source_id, site_id, origin),
            "source_id": source_id,
            "site_id": site_id,
            "evaluation_cohort": "fresh_primary",
            "cohort_route": "fresh_location",
            "origin_year_month": origin,
            "base_input_status": "eligible",
            "base_input_reason": "complete_input_history_with_module_coverage",
        }
        intents.append({
            **common,
            "history_start_year_month": _month_text(month_indices[0]),
            "history_end_year_month": origin,
            "history_length_months": HISTORY_LENGTH,
            "history_row_count": HISTORY_LENGTH,
            "missing_history_row_count": 0,
        })
        current = panel_by_key[(source_id, site_id, origin_index)]
        origin_rows.append({
            **common,
            "row_present": True,
            **current,
            **_calendar_features(origin_index),
        })
        sequence: dict[str, Any] = {
            **common,
            "sequence_length": HISTORY_LENGTH,
            "sequence_row_present": [True] * HISTORY_LENGTH,
        }
        for column in (*PHYSICAL_FEATURE_COLUMNS, *CALENDAR_COLUMNS):
            sequence[f"sequence_{column}"] = []
        for offset, month in enumerate(month_indices):
            features = panel_by_key[(source_id, site_id, month)]
            calendar = _calendar_features(month)
            history_rows.append({
                **common,
                "history_year_month": _month_text(month),
                "history_offset_months": offset - HISTORY_LENGTH + 1,
                "row_present": True,
                **features,
                **calendar,
            })
            for column in PHYSICAL_FEATURE_COLUMNS:
                cast(list[Any], sequence[f"sequence_{column}"]).append(features[column])
            for column in CALENDAR_COLUMNS:
                cast(list[Any], sequence[f"sequence_{column}"]).append(calendar[column])
        sequence_rows.append(sequence)

    inventory = pd.DataFrame([
        {
            "source_id": source_id,
            "site_id": site_id,
            "evaluation_cohort": "fresh_primary",
            "cohort_route": "fresh_location",
            "v1_location_overlap": False,
            "intent_origin_count_per_horizon": len(origins),
            "origin_start": min(origins),
            "origin_end": max(origins),
            "history_length_months": HISTORY_LENGTH,
            "horizons": "1|2|3",
            "selection_uses_input_and_provenance_only": True,
        }
        for (source_id, site_id), origins in sorted(
            by_site.items(), key=lambda item: (item[0][0].encode("utf-8"), item[0][1].encode("utf-8"))
        )
    ])
    return {
        "candidate_keys": candidate_keys,
        "candidate_digest": digest,
        "inventory": inventory,
        "input_history": history_rows,
        "intent_origins": intents,
        "origin_features": origin_rows,
        "sequence_features": sequence_rows,
    }


def _validate_columns(columns: Sequence[str]) -> None:
    for column in columns:
        lowered = column.lower()
        if any(token in lowered for token in FORBIDDEN_COLUMN_TOKENS):
            raise EvaluationInputError(f"Forbidden input-bundle column: {column}")


def _arrow_type(column: str) -> pa.DataType:
    if column in set(COMMON_COLUMNS) | {"history_start_year_month", "history_end_year_month", "history_year_month"}:
        return pa.string()
    if column in {"history_length_months", "history_row_count", "missing_history_row_count", "history_offset_months", "sequence_length"}:
        return pa.int64()
    if column == "row_present":
        return pa.bool_()
    if column == "sequence_row_present":
        return pa.list_(pa.bool_())
    if column.startswith("sequence_"):
        return pa.list_(pa.float64())
    if column in (*PHYSICAL_FEATURE_COLUMNS, *CALENDAR_COLUMNS):
        return pa.float64()
    raise EvaluationInputError(f"Missing Arrow type contract: {column}")


def _parquet_bytes(records: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> bytes:
    if not records:
        raise EvaluationInputError("Refusing to serialize an empty input-only table")
    _validate_columns(columns)
    if any(tuple(row) != tuple(columns) for row in records):
        raise EvaluationInputError("Constructed table column order drifted")
    schema = pa.schema([pa.field(column, _arrow_type(column), nullable=True) for column in columns])
    table = pa.Table.from_pylist([dict(row) for row in records], schema=schema)
    buffer = io.BytesIO()
    pq.write_table(
        table,
        buffer,
        compression="zstd",
        use_dictionary=False,
        write_statistics=True,
        data_page_version="1.0",
    )
    return buffer.getvalue()


def _exclusive_files(contents: Sequence[tuple[Path, bytes]], *, root: Path) -> None:
    created: list[tuple[Path, int]] = []
    temporaries: list[Path] = []
    try:
        for relative, payload in contents:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise EvaluationInputError(f"Refusing to overwrite Closure V2 output: {relative}")
            temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
            temporaries.append(temporary)
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, destination)
            created.append((destination, destination.stat().st_ino))
            temporary.unlink()
    except Exception:
        for destination, inode in reversed(created):
            if destination.is_file() and not destination.is_symlink() and destination.stat().st_ino == inode:
                destination.unlink()
        raise
    finally:
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)


def _dvc_record(relative: Path, *, root: Path) -> dict[str, Any]:
    physical = _require_regular(root, relative)
    pointer_relative = relative.with_suffix(relative.suffix + ".dvc")
    pointer = _require_regular(root, pointer_relative)
    payload = yaml.safe_load(pointer.read_text(encoding="utf-8"))
    outs = payload.get("outs") if isinstance(payload, Mapping) else None
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise EvaluationInputError(f"Invalid DVC pointer: {pointer_relative}")
    output = outs[0]
    if output.get("path") != relative.name or output.get("size") != physical.stat().st_size:
        raise EvaluationInputError(f"DVC pointer path/size mismatch: {pointer_relative}")
    if output.get("md5") != md5_file(physical):
        raise EvaluationInputError(f"DVC pointer hash mismatch: {pointer_relative}")
    return {
        "path": relative.as_posix(),
        "bytes": physical.stat().st_size,
        "sha256": sha256_file(physical),
        "rows": pq.read_metadata(physical).num_rows,
        "dvc_pointer": pointer_relative.as_posix(),
        "dvc_pointer_bytes": pointer.stat().st_size,
        "dvc_pointer_sha256": sha256_file(pointer),
        "dvc_md5": str(output["md5"]),
        "dvc_size": int(output["size"]),
    }


def _virtual_record(relative: Path, payload: bytes, role: str) -> dict[str, Any]:
    return {
        "path": relative.as_posix(),
        "role": role,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _reconstruct(root: Path) -> tuple[dict[str, Any], Mapping[str, Any], Mapping[str, Any], dict[str, str]]:
    authority = load_effective_model_lock(root=root)
    if (root / OUTCOME_LOG).exists() or (root / OUTCOME_LOG).is_symlink():
        raise EvaluationInputError("Outcome access log must not exist before P12 activation")
    cohorts = validate_evaluation_cohorts()
    fresh = cast(Mapping[str, Any], cohorts["fresh_location"])
    audit = cast(Mapping[str, Any], fresh["prelock_input_only_feasibility_audit"])
    source_hashes = _source_hashes(root, audit)
    v1_keys, panel_rows = _load_inputs(root)
    origin_range = cast(Sequence[str], audit["origin_range"])
    built = reconstruct_fresh_primary(
        v1_keys,
        panel_rows,
        origin_start=str(origin_range[0]),
        origin_end=str(origin_range[1]),
    )
    return built, cohorts, authority, source_hashes


def preflight(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    built, _cohorts, authority, _hashes = _reconstruct(root)
    present = [path.as_posix() for path in (*PHYSICAL_PATHS, *POINTER_PATHS, *LIGHT_PATHS) if (root / path).exists()]
    return {
        "status": "ready_to_materialize" if not present else "outputs_present",
        "model_lock": authority,
        "fresh_primary": "fresh_location",
        "candidate_location_count": len(built["inventory"]),
        "intent_origins_per_horizon": len(built["candidate_keys"]),
        "candidate_key_digest_sha256": built["candidate_digest"],
        "present_outputs": present,
        "outcome_values_opened": False,
        "target_availability_inspected": False,
        "chla_columns_read": False,
    }


def materialize_data(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    built, _cohorts, authority, source_hashes = _reconstruct(root)
    if any((root / path).exists() or (root / path).is_symlink() for path in (*PHYSICAL_PATHS, *POINTER_PATHS, *LIGHT_PATHS)):
        raise EvaluationInputError("P11 namespace is not empty; refusing one-shot materialization")
    payloads = [
        _parquet_bytes(cast(Sequence[Mapping[str, Any]], built[key]), TABLE_COLUMNS[key])
        for key in TABLE_KEYS
    ]
    _exclusive_files(list(zip(PHYSICAL_PATHS, payloads, strict=True)), root=root)
    return {
        "status": "physical_data_written_unpublished",
        "model_lock": authority,
        "source_hashes": source_hashes,
        "candidate_location_count": len(built["inventory"]),
        "intent_origins_per_horizon": len(built["candidate_keys"]),
        "physical_outputs": [
            {"path": path.as_posix(), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            for path, payload in zip(PHYSICAL_PATHS, payloads, strict=True)
        ],
        "outcome_values_opened": False,
        "target_availability_inspected": False,
        "chla_columns_read": False,
    }


def execute(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    built, cohorts, authority, source_hashes = _reconstruct(root)
    if any((root / path).exists() or (root / path).is_symlink() for path in LIGHT_PATHS):
        raise EvaluationInputError("P11 light namespace is not empty; refusing finalization")
    expected_payloads = [
        _parquet_bytes(cast(Sequence[Mapping[str, Any]], built[key]), TABLE_COLUMNS[key])
        for key in TABLE_KEYS
    ]
    for path, expected in zip(PHYSICAL_PATHS, expected_payloads, strict=True):
        if _require_regular(root, path).read_bytes() != expected:
            raise EvaluationInputError(f"Physical input-only payload differs from reconstruction: {path}")
    data_records = [_dvc_record(path, root=root) for path in PHYSICAL_PATHS]

    inventory_bytes = cast(pd.DataFrame, built["inventory"]).to_csv(index=False, lineterminator="\n").encode("utf-8")
    decision = {
        "schema_version": "closure_v2_fresh_cohort_decision_v1",
        "experiment_id": "closure_v2",
        "status": "selected_unpublished",
        "evaluation_cohort": "fresh_primary",
        "decision_order": ["fresh_location", "forward_temporal", "external", "insufficient_support"],
        "routes": {
            "fresh_location": {
                "status": "selected",
                "candidate_location_count": EXPECTED_LOCATIONS,
                "intent_origins_per_horizon": EXPECTED_ORIGINS,
                "minimum_new_locations": 40,
                "minimum_intent_origins_per_horizon": 500,
                "v1_location_overlap_count": 0,
            },
            "forward_temporal": {"status": "not_reached"},
            "external": {"status": "not_reached"},
            "insufficient_support": {"status": "not_reached"},
        },
        "candidate_key_digest_sha256": built["candidate_digest"],
        "origin_range": ["2022-01", "2024-09"],
        "target_geometry_range": ["2022-02", "2024-12"],
        "selection_uses_input_and_provenance_only": True,
        "replacement_used": False,
        "target_values_opened": False,
        "target_availability_inspected": False,
        "outcome_values_opened": False,
        "chla_columns_read": False,
    }
    decision_bytes = canonical_json_bytes(decision)
    pointer_records = [file_record(root / path, root=root, role="locked_evaluation_input_dvc_pointer") for path in POINTER_PATHS]
    cohort_manifest = {
        "schema_version": "closure_v2_fresh_cohort_manifest_v1",
        "experiment_id": "closure_v2",
        "status": "completed",
        "evaluation_cohort": "fresh_primary",
        "selected_route": "fresh_location",
        "script": file_record(
            root / Path("src/experiments/closure_v2/build_evaluation_inputs.py"),
            root=root,
            role="input_only_builder",
        ),
        "inputs": [
            file_record(root / COHORT_CONFIG, root=root, role="evaluation_cohorts"),
            file_record(root / MODEL_LOCK_PATH, root=root, role="effective_model_lock"),
        ],
        "model_lock": authority,
        "source_inputs": [
            file_record(root / COHORT_CONFIG, root=root, role="evaluation_cohorts"),
            file_record(root / ASSIGNMENT_PATH, root=root, role="v1_location_universe"),
            file_record(root / PANEL_PATH, root=root, role="input_only_panel"),
            file_record(root / MODEL_LOCK_PATH, root=root, role="effective_model_lock"),
        ],
        "source_hashes": source_hashes,
        "candidate_location_count": EXPECTED_LOCATIONS,
        "intent_origins_per_horizon": EXPECTED_ORIGINS,
        "candidate_key_digest_sha256": built["candidate_digest"],
        "outputs": [
            _virtual_record(INVENTORY_PATH, inventory_bytes, "fresh_candidate_inventory"),
            _virtual_record(DECISION_PATH, decision_bytes, "fresh_cohort_decision"),
            *pointer_records,
        ],
        "data_artifacts": data_records,
        "target_values_opened": False,
        "target_availability_inspected": False,
        "outcome_values_opened": False,
        "chla_columns_read": False,
        "replacement_used": False,
        "manifest_written_last": True,
    }
    cohort_manifest_bytes = canonical_json_bytes(cohort_manifest)
    input_manifest = {
        "schema_version": "closure_v2_locked_evaluation_input_manifest_v1",
        "experiment_id": "closure_v2",
        "status": "completed",
        "evaluation_cohort": "fresh_primary",
        "selected_route": "fresh_location",
        "script": file_record(root / Path("src/experiments/closure_v2/build_evaluation_inputs.py"), root=root, role="input_only_builder"),
        "inputs": [
            file_record(root / COHORT_CONFIG, root=root, role="evaluation_cohorts"),
            file_record(root / MODEL_LOCK_PATH, root=root, role="effective_model_lock"),
        ],
        "source_inputs": cohort_manifest["source_inputs"],
        "outputs": [
            *pointer_records,
            _virtual_record(INVENTORY_PATH, inventory_bytes, "fresh_candidate_inventory"),
            _virtual_record(DECISION_PATH, decision_bytes, "fresh_cohort_decision"),
            _virtual_record(COHORT_MANIFEST_PATH, cohort_manifest_bytes, "fresh_cohort_manifest"),
        ],
        "data_artifacts": data_records,
        "table_contract": {path.as_posix(): list(TABLE_COLUMNS[key]) for path, key in zip(PHYSICAL_PATHS, TABLE_KEYS, strict=True)},
        "candidate_location_count": EXPECTED_LOCATIONS,
        "intent_origins_per_horizon": EXPECTED_ORIGINS,
        "attempted_intent_rows_all_horizons": EXPECTED_ORIGINS * len(HORIZONS),
        "candidate_key_digest_sha256": built["candidate_digest"],
        "model_lock_sha256": authority["model_lock_sha256"],
        "model_lock_commit": authority["commit"],
        "target_values_opened": False,
        "target_availability_inspected": False,
        "outcome_values_opened": False,
        "chla_columns_read": False,
        "replacement_used": False,
        "evaluation_authorized": False,
        "activation_required": True,
        "manifest_written_last": True,
    }
    input_manifest_bytes = canonical_json_bytes(input_manifest)
    _exclusive_files(
        [
            (INVENTORY_PATH, inventory_bytes),
            (DECISION_PATH, decision_bytes),
            (COHORT_MANIFEST_PATH, cohort_manifest_bytes),
            (INPUT_MANIFEST_PATH, input_manifest_bytes),
        ],
        root=root,
    )
    return {
        "status": "fresh_primary_input_bundle_completed_unpublished",
        "evaluation_cohort": "fresh_primary",
        "selected_route": "fresh_location",
        "candidate_location_count": EXPECTED_LOCATIONS,
        "intent_origins_per_horizon": EXPECTED_ORIGINS,
        "candidate_key_digest_sha256": built["candidate_digest"],
        "outcome_values_opened": False,
        "target_availability_inspected": False,
        "chla_columns_read": False,
        "activation_required": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--materialize-data", action="store_true")
    group.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.materialize_data:
        result = materialize_data()
    elif args.execute:
        result = execute()
    else:
        result = preflight()
    print(canonical_json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
