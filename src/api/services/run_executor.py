"""Safe synchronous executors for initial local API workflows."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from statistics import median
from typing import Any

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

_EXECUTABLE_WORKFLOWS = {"canonical_observations", "monthly_panel"}


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

    if plan.workflow == "monthly_panel":
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
