"""Safe synchronous executors for initial local API workflows."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, cast

import pandas as pd

from src.api.config import api_workspace
from src.api.errors import ErrorCode
from src.api.schemas.run import RunExecutionResponse, RunPlanArtifact, RunPlanResponse
from src.api.services.dataset_repository import read_dataset_request
from src.api.services.dataset_validation import (
    CanonicalVariable,
    load_canonical_variables,
    parse_observed_year_month,
)
from src.api.services.run_repository import (
    RunExecutionNotFoundError,
    read_run_execution,
    read_run_plan,
    run_plan_dir,
    save_run_execution,
)
from src.fuzzy.expert import build_expert_state

_EXECUTABLE_WORKFLOWS = {"canonical_observations", "monthly_panel", "fuzzy_state"}
_FUZZY_MANIFEST_PATH = Path("reports/anfis/fuzzy_manifest.json")


class RunExecutionError(Exception):
    """Expected execution refusal with a stable API error code."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, object] | None = None,
        http_status: int = 409,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = http_status


def execute_run_plan(plan_id: str) -> RunExecutionResponse:
    """Execute a safe local workflow from a persisted dry-run plan."""

    try:
        return read_run_execution(plan_id)
    except RunExecutionNotFoundError:
        pass

    plan = read_run_plan(plan_id)
    _assert_executable(plan)

    started_at = _now_utc()
    workspace = api_workspace()
    run_dir = run_plan_dir(plan.plan_id, workspace=workspace)
    dataset_request = read_dataset_request(plan.dataset_id, workspace=workspace)
    variables = load_canonical_variables()

    canonical_rows = _canonical_rows(dataset_request.observations, variables)
    canonical_jsonl = run_dir / "canonical_observations.jsonl"
    canonical_csv = run_dir / "canonical_observations.csv"
    _write_jsonl(canonical_jsonl, canonical_rows)
    _write_csv(canonical_csv, canonical_rows, _CANONICAL_FIELDS)

    output_paths = [canonical_jsonl, canonical_csv]
    row_counts = {"canonical_observations": len(canonical_rows)}

    if plan.workflow in {"monthly_panel", "fuzzy_state"}:
        panel_rows = _monthly_panel_rows(canonical_rows, variables)
        if not panel_rows:
            raise RunExecutionError(
                ErrorCode.no_valid_monthly_panel,
                "Canonical observations could not produce usable monthly panel rows.",
                details={"plan_id": plan.plan_id, "dataset_id": plan.dataset_id},
            )
        monthly_panel_csv = run_dir / "monthly_panel.csv"
        _write_csv(monthly_panel_csv, panel_rows, _PANEL_FIELDS)
        output_paths.append(monthly_panel_csv)
        row_counts["monthly_panel"] = len(panel_rows)

    if plan.workflow == "fuzzy_state":
        wide_panel = _wide_panel_frame(panel_rows, canonical_rows)
        if wide_panel.empty:
            raise RunExecutionError(
                ErrorCode.no_valid_monthly_panel,
                "Canonical observations could not produce fuzzy state input rows.",
                details={"plan_id": plan.plan_id, "dataset_id": plan.dataset_id},
            )
        fuzzy_settings = _load_fuzzy_settings()
        irc_weights = fuzzy_settings["irc_weights"]
        state, trace = build_expert_state(wide_panel, irc_weights=irc_weights)
        monthly_panel_wide_csv = run_dir / "monthly_panel_wide.csv"
        fuzzy_state_csv = run_dir / "fuzzy_state_scores.csv"
        fuzzy_trace_csv = run_dir / "fuzzy_state_trace.csv"
        fuzzy_manifest_path = run_dir / "fuzzy_state_manifest.json"
        _write_dataframe_csv(monthly_panel_wide_csv, wide_panel)
        _write_dataframe_csv(fuzzy_state_csv, state)
        _write_dataframe_csv(fuzzy_trace_csv, trace)
        fuzzy_manifest_payload = {
            "plan_id": plan.plan_id,
            "dataset_id": plan.dataset_id,
            "workflow": plan.workflow,
            "state_version": "expert_fuzzy_state_v0",
            "scoring_function": "src.fuzzy.expert.build_expert_state",
            "weights_source": _FUZZY_MANIFEST_PATH.as_posix(),
            "irc_weights": irc_weights,
            "alert_threshold": fuzzy_settings["threshold"],
            "alert_policy_version": "expert_fuzzy_state_v0_threshold",
            "row_counts": {
                "monthly_panel_wide": int(len(wide_panel)),
                "fuzzy_state": int(len(state)),
                "fuzzy_trace": int(len(trace)),
            },
            "notes": [
                "This executor computes deterministic expert fuzzy state scores.",
                "It does not retrain adaptive ANFIS or run temporal alert models.",
            ],
        }
        _write_json(fuzzy_manifest_path, fuzzy_manifest_payload)
        output_paths.extend([monthly_panel_wide_csv, fuzzy_state_csv, fuzzy_trace_csv, fuzzy_manifest_path])
        row_counts.update(
            {
                "monthly_panel_wide": int(len(wide_panel)),
                "fuzzy_state": int(len(state)),
                "fuzzy_trace": int(len(trace)),
            }
        )

    completed_at = _now_utc()
    execution_id = _execution_id(plan.plan_id)
    artifacts = [_artifact(workspace, path, role="output") for path in output_paths]

    manifest_path = run_dir / "execution_manifest.json"
    manifest_payload = {
        "execution_id": execution_id,
        "plan_id": plan.plan_id,
        "dataset_id": plan.dataset_id,
        "workflow": plan.workflow,
        "status": "completed",
        "started_at": started_at,
        "completed_at": completed_at,
        "row_counts": row_counts,
        "artifacts": [artifact.model_dump(mode="json", exclude_none=True) for artifact in artifacts],
    }
    _write_json(manifest_path, manifest_payload)
    artifacts.append(_artifact(workspace, manifest_path, role="manifest"))

    execution = RunExecutionResponse(
        execution_id=execution_id,
        plan_id=plan.plan_id,
        dataset_id=plan.dataset_id,
        workflow=plan.workflow,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        row_counts=row_counts,
        warnings=plan.warnings,
        artifacts=artifacts,
    )
    return save_run_execution(execution, workspace=workspace)


def _assert_executable(plan: RunPlanResponse) -> None:
    if plan.workflow not in _EXECUTABLE_WORKFLOWS:
        raise RunExecutionError(
            ErrorCode.unsupported_pipeline_for_dataset,
            "This workflow is not executable by the initial synchronous executor.",
            details={
                "plan_id": plan.plan_id,
                "workflow": plan.workflow,
                "supported_workflows": sorted(_EXECUTABLE_WORKFLOWS),
            },
        )
    if plan.status != "ready":
        raise RunExecutionError(
            ErrorCode.dependency_not_ready,
            "Run plan is not ready for execution.",
            details={
                "plan_id": plan.plan_id,
                "workflow": plan.workflow,
                "plan_status": plan.status,
                "blockers": [item.model_dump(mode="json", exclude_none=True) for item in plan.blockers],
            },
        )


_CANONICAL_FIELDS = [
    "source_id",
    "site_id",
    "observed_at",
    "year_month",
    "variable",
    "value",
    "unit",
    "original_value",
    "original_unit",
    "latitude",
    "longitude",
    "depth_m",
    "qc_flag",
    "method",
    "notes",
]

_PANEL_FIELDS = [
    "source_id",
    "site_id",
    "year_month",
    "variable",
    "value",
    "unit",
    "observation_count",
    "aggregation",
]

_FUZZY_PANEL_COLUMNS = [
    "source_id",
    "site_id",
    "site_id_source",
    "site_name",
    "year_month",
    "mean_TP_ugL",
    "mean_TN_ugL",
    "TN_TP_ratio",
    "mean_DO_mgL",
    "mean_pH",
    "mean_turbidity_NTU",
    "mean_secchi_depth_m",
    "mean_temperature_C",
    "mean_chlorophyll_a_ugL",
    "risk_chla",
    "qc_ok_rate_TP_ugL",
    "qc_ok_rate_TN_ugL",
    "qc_ok_rate_DO_mgL",
    "qc_ok_rate_pH",
    "qc_ok_rate_turbidity_NTU",
    "qc_ok_rate_secchi_depth_m",
    "qc_ok_rate_temperature_C",
    "qc_ok_rate_chlorophyll_a_ugL",
]

_FUZZY_MEAN_COLUMN_BY_VARIABLE = {
    "TP_ugL": "mean_TP_ugL",
    "TN_ugL": "mean_TN_ugL",
    "DO_mgL": "mean_DO_mgL",
    "pH": "mean_pH",
    "turbidity_NTU": "mean_turbidity_NTU",
    "secchi_depth_m": "mean_secchi_depth_m",
    "temperature_C": "mean_temperature_C",
    "chlorophyll_a_ugL": "mean_chlorophyll_a_ugL",
}

_QC_GOOD_FLAGS = {"1", "accepted", "good", "ok", "pass", "passed", "true", "valid", "y", "yes"}
_QC_BAD_FLAGS = {"0", "bad", "fail", "failed", "false", "invalid", "n", "no", "reject", "rejected", "suspect"}


def _canonical_rows(observations: list[Any], variables: dict[str, CanonicalVariable]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for observation in observations:
        variable = variables[observation.variable]
        canonical_value = _convert_value(
            observation.value,
            variable.conversions.get(observation.unit, "identity"),
        )
        rows.append(
            {
                "source_id": observation.source_id,
                "site_id": observation.site_id,
                "observed_at": observation.observed_at,
                "year_month": parse_observed_year_month(observation.observed_at),
                "variable": observation.variable,
                "value": canonical_value,
                "unit": variable.canonical_unit,
                "original_value": observation.value,
                "original_unit": observation.unit,
                "latitude": observation.latitude,
                "longitude": observation.longitude,
                "depth_m": observation.depth_m,
                "qc_flag": observation.qc_flag,
                "method": observation.method,
                "notes": observation.notes,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["source_id"]),
            str(row["site_id"]),
            str(row["year_month"]),
            str(row["variable"]),
            str(row["observed_at"]),
        ),
    )


def _monthly_panel_rows(
    canonical_rows: list[dict[str, object]],
    variables: dict[str, CanonicalVariable],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], list[float]] = {}
    for row in canonical_rows:
        key = (
            str(row["source_id"]),
            str(row["site_id"]),
            str(row["year_month"]),
            str(row["variable"]),
        )
        value = row["value"]
        if not isinstance(value, int | float):
            raise RunExecutionError(
                ErrorCode.pipeline_execution_failed,
                "Canonical observation value is not numeric.",
                details={"value": value, "variable": row["variable"]},
                http_status=500,
            )
        grouped.setdefault(key, []).append(float(value))

    panel_rows: list[dict[str, object]] = []
    for source_id, site_id, year_month, variable_name in sorted(grouped):
        variable = variables[variable_name]
        values = grouped[(source_id, site_id, year_month, variable_name)]
        panel_rows.append(
            {
                "source_id": source_id,
                "site_id": site_id,
                "year_month": year_month,
                "variable": variable_name,
                "value": median(values),
                "unit": variable.canonical_unit,
                "observation_count": len(values),
                "aggregation": "median",
            }
        )
    return panel_rows


def _wide_panel_frame(
    panel_rows: list[dict[str, object]],
    canonical_rows: list[dict[str, object]],
) -> pd.DataFrame:
    records: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in panel_rows:
        variable = str(row["variable"])
        mean_column = _FUZZY_MEAN_COLUMN_BY_VARIABLE.get(variable)
        if mean_column is None:
            continue
        key = (str(row["source_id"]), str(row["site_id"]), str(row["year_month"]))
        record = records.setdefault(
            key,
            {
                "source_id": key[0],
                "site_id": key[1],
                "site_id_source": key[1],
                "site_name": key[1],
                "year_month": key[2],
            },
        )
        value = _optional_float(row.get("value"))
        if value is None:
            continue
        record[mean_column] = value

    qc_scores: dict[tuple[str, str, str, str], list[float]] = {}
    for row in canonical_rows:
        score = _qc_score(row.get("qc_flag"))
        if score is None:
            continue
        variable = str(row["variable"])
        if variable not in _FUZZY_MEAN_COLUMN_BY_VARIABLE:
            continue
        key = (
            str(row["source_id"]),
            str(row["site_id"]),
            str(row["year_month"]),
            variable,
        )
        qc_scores.setdefault(key, []).append(score)

    for source_id, site_id, year_month, variable in sorted(qc_scores):
        record = records.get((source_id, site_id, year_month))
        if record is None:
            continue
        values = qc_scores[(source_id, site_id, year_month, variable)]
        record[f"qc_ok_rate_{variable}"] = sum(values) / len(values)

    for record in records.values():
        tp = _optional_float(record.get("mean_TP_ugL"))
        tn = _optional_float(record.get("mean_TN_ugL"))
        if tp is not None and tp > 0.0 and tn is not None:
            record["TN_TP_ratio"] = tn / tp
        chla = _optional_float(record.get("mean_chlorophyll_a_ugL"))
        if chla is not None:
            record["risk_chla"] = _chlorophyll_risk(chla)

    frame = pd.DataFrame(list(records.values()))
    if frame.empty:
        return frame
    for column in _FUZZY_PANEL_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[_FUZZY_PANEL_COLUMNS].sort_values(["source_id", "site_id", "year_month"]).reset_index(drop=True)


def _optional_float(value: object) -> float | None:
    if value is None or value is pd.NA:
        return None
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _chlorophyll_risk(chla_ugl: float) -> float:
    low = math.log(5.0 + 0.1)
    high = math.log(30.0 + 0.1)
    value = (math.log(max(chla_ugl, 0.0) + 0.1) - low) / (high - low)
    return min(1.0, max(0.0, value))


def _qc_score(raw_flag: object) -> float | None:
    if raw_flag is None:
        return None
    normalized = str(raw_flag).strip().lower()
    if not normalized:
        return None
    if normalized in _QC_GOOD_FLAGS:
        return 1.0
    if normalized in _QC_BAD_FLAGS:
        return 0.0
    return None


def _load_fuzzy_settings() -> dict[str, Any]:
    if not _FUZZY_MANIFEST_PATH.exists():
        raise RunExecutionError(
            ErrorCode.dependency_not_ready,
            "Expert fuzzy manifest is required for reproducible fuzzy state scoring.",
            details={"required_artifact": _FUZZY_MANIFEST_PATH.as_posix()},
        )
    try:
        payload = json.loads(_FUZZY_MANIFEST_PATH.read_text(encoding="utf-8"))
        raw_weights = payload["irc_weights"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RunExecutionError(
            ErrorCode.pipeline_execution_failed,
            "Expert fuzzy manifest does not contain valid IRC weights.",
            details={"required_artifact": _FUZZY_MANIFEST_PATH.as_posix()},
            http_status=500,
        ) from exc

    weights: dict[str, float] = {}
    for name in ("alpha", "beta", "gamma"):
        value = _optional_float(raw_weights.get(name))
        if value is None or value <= 0.0:
            raise RunExecutionError(
                ErrorCode.pipeline_execution_failed,
                "Expert fuzzy manifest contains invalid IRC weights.",
                details={"required_artifact": _FUZZY_MANIFEST_PATH.as_posix(), "weight": name},
                http_status=500,
            )
        weights[name] = value
    threshold = _optional_float(payload.get("threshold"))
    if threshold is None or threshold < 0.0 or threshold > 1.0:
        raise RunExecutionError(
            ErrorCode.pipeline_execution_failed,
            "Expert fuzzy manifest contains an invalid alert threshold.",
            details={"required_artifact": _FUZZY_MANIFEST_PATH.as_posix(), "field": "threshold"},
            http_status=500,
        )
    return {"irc_weights": weights, "threshold": threshold}


def _convert_value(value: float, rule: str) -> float:
    if rule in {"identity", "identity_approximate"}:
        return value
    if rule == "multiply_1000":
        return value * 1000.0
    if rule == "multiply_0_3048":
        return value * 0.3048
    if rule == "multiply_0_0254":
        return value * 0.0254
    if rule == "fahrenheit_to_celsius":
        return (value - 32.0) * 5.0 / 9.0
    raise RunExecutionError(
        ErrorCode.unsupported_unit,
        "Unsupported unit conversion rule.",
        details={"conversion_rule": rule},
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fieldnames})


def _write_dataframe_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _artifact(root: Path, path: Path, *, role: str) -> RunPlanArtifact:
    content = path.read_bytes()
    return RunPlanArtifact(
        name=path.name,
        role=role,
        uri=path.relative_to(root).as_posix(),
        required=False,
        availability="available",
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
    )


def _execution_id(plan_id: str) -> str:
    return f"exec_{hashlib.sha256(plan_id.encode('utf-8')).hexdigest()[:16]}"


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
