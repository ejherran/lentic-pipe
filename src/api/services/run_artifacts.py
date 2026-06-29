"""Read generated artifacts and lightweight result summaries for API runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, cast

from src.api.config import api_workspace
from src.api.errors import ErrorCode
from src.api.schemas.run import (
    RunArtifactListResponse,
    RunArtifactPreviewFormat,
    RunArtifactPreviewResponse,
    RunExecutionResponse,
    RunPlanArtifact,
    RunResultSummaryResponse,
)
from src.api.services.run_repository import read_run_execution, run_plan_dir

_TEXT_SUFFIXES = {".md", ".txt", ".log"}
_SUMMARY_SCORE_COLUMNS = ("yN", "yF", "yT", "irc1", "irc1_no_chla")


class RunArtifactError(Exception):
    """Expected artifact access failure with a stable API error code."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, object] | None = None,
        http_status: int = 404,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = http_status


def list_run_artifacts(plan_id: str) -> RunArtifactListResponse:
    """List generated artifacts for a completed local run."""

    execution = read_run_execution(plan_id)
    return RunArtifactListResponse(
        plan_id=execution.plan_id,
        execution_id=execution.execution_id,
        dataset_id=execution.dataset_id,
        workflow=execution.workflow,
        artifacts=execution.artifacts,
    )


def preview_run_artifact(plan_id: str, artifact_name: str, *, limit: int) -> RunArtifactPreviewResponse:
    """Return a small JSON-safe preview of a generated artifact."""

    execution = read_run_execution(plan_id)
    artifact = _execution_artifact(execution, artifact_name)
    path = _artifact_path(execution.plan_id, artifact)
    preview_format = _preview_format(path)
    media_type = _media_type(path)

    if preview_format == "csv":
        rows, columns, truncated = _preview_csv(path, limit)
        content: object | None = None
    elif preview_format == "jsonl":
        rows, truncated = _preview_jsonl(path, limit)
        columns = _columns_from_rows(rows)
        content = None
    elif preview_format == "json":
        rows = []
        columns = []
        content, truncated = _preview_json(path)
    elif preview_format == "text":
        rows = []
        columns = []
        content, truncated = _preview_text(path, limit)
    else:
        raise RunArtifactError(
            ErrorCode.invalid_request,
            "Artifact format is not previewable through this endpoint.",
            details={"artifact_name": artifact_name},
            http_status=400,
        )

    return RunArtifactPreviewResponse(
        plan_id=execution.plan_id,
        execution_id=execution.execution_id,
        artifact_name=artifact.name,
        media_type=media_type,
        preview_format=preview_format,
        limit=limit,
        truncated=truncated,
        columns=columns,
        rows=rows,
        content=content,
    )


def summarize_run_results(plan_id: str) -> RunResultSummaryResponse:
    """Return structured summaries for known local run artifacts."""

    execution = read_run_execution(plan_id)
    run_dir = run_plan_dir(execution.plan_id)
    summaries: dict[str, object] = {}

    canonical_path = run_dir / "canonical_observations.csv"
    if canonical_path.exists():
        summaries["canonical_observations"] = _long_observation_summary(canonical_path)

    panel_path = run_dir / "monthly_panel.csv"
    if panel_path.exists():
        summaries["monthly_panel"] = _monthly_panel_summary(panel_path)

    fuzzy_path = run_dir / "fuzzy_state_scores.csv"
    if fuzzy_path.exists():
        summaries["fuzzy_state"] = _fuzzy_state_summary(fuzzy_path)

    return RunResultSummaryResponse(
        plan_id=execution.plan_id,
        execution_id=execution.execution_id,
        dataset_id=execution.dataset_id,
        workflow=execution.workflow,
        row_counts=execution.row_counts,
        summaries=summaries,
    )


def _execution_artifact(execution: RunExecutionResponse, artifact_name: str) -> RunPlanArtifact:
    for artifact in execution.artifacts:
        if artifact.name == artifact_name:
            return artifact
    raise RunArtifactError(
        ErrorCode.resource_not_found,
        "Run artifact does not exist for this execution.",
        details={
            "plan_id": execution.plan_id,
            "artifact_name": artifact_name,
            "available_artifacts": [artifact.name for artifact in execution.artifacts],
        },
    )


def _artifact_path(plan_id: str, artifact: RunPlanArtifact) -> Path:
    path = run_plan_dir(plan_id, workspace=api_workspace()) / artifact.name
    if not path.exists() or not path.is_file():
        raise RunArtifactError(
            ErrorCode.resource_not_found,
            "Run artifact file is not available in the local API workspace.",
            details={"plan_id": plan_id, "artifact_name": artifact.name},
        )
    return path


def _preview_format(path: Path) -> RunArtifactPreviewFormat:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        return "json"
    if suffix == ".jsonl":
        return "jsonl"
    if suffix in _TEXT_SUFFIXES:
        return "text"
    raise RunArtifactError(
        ErrorCode.invalid_request,
        "Artifact format is not previewable through this endpoint.",
        details={"artifact_name": path.name, "suffix": suffix},
        http_status=400,
    )


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "text/csv"
    if suffix == ".json":
        return "application/json"
    if suffix == ".jsonl":
        return "application/x-ndjson"
    if suffix == ".md":
        return "text/markdown"
    if suffix in {".txt", ".log"}:
        return "text/plain"
    return "application/octet-stream"


def _preview_csv(path: Path, limit: int) -> tuple[list[dict[str, object]], list[str], bool]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, object]] = []
        truncated = False
        for index, row in enumerate(reader):
            if index >= limit:
                truncated = True
                break
            rows.append(dict(row))
        return rows, list(reader.fieldnames or []), truncated


def _preview_jsonl(path: Path, limit: int) -> tuple[list[dict[str, object]], bool]:
    rows: list[dict[str, object]] = []
    truncated = False
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(line for line in handle if line.strip()):
            if index >= limit:
                truncated = True
                break
            value = json.loads(line)
            rows.append(value if isinstance(value, dict) else {"value": value})
    return rows, truncated


def _preview_json(path: Path) -> tuple[object, bool]:
    return json.loads(path.read_text(encoding="utf-8")), False


def _preview_text(path: Path, limit: int) -> tuple[str, bool]:
    lines = path.read_text(encoding="utf-8").splitlines()
    truncated = len(lines) > limit
    return "\n".join(lines[:limit]), truncated


def _columns_from_rows(rows: list[dict[str, object]]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row:
            if column not in seen:
                seen.add(column)
                columns.append(column)
    return columns


def _long_observation_summary(path: Path) -> dict[str, object]:
    rows = _read_csv_rows(path)
    return {
        "rows": len(rows),
        "sites": len(_unique(rows, "site_id")),
        "months": len(_unique(rows, "year_month")),
        "variables": _unique(rows, "variable"),
        "year_month_min": _min_or_none(row.get("year_month") for row in rows),
        "year_month_max": _max_or_none(row.get("year_month") for row in rows),
    }


def _monthly_panel_summary(path: Path) -> dict[str, object]:
    rows = _read_csv_rows(path)
    return {
        "rows": len(rows),
        "sites": len(_unique(rows, "site_id")),
        "months": len(_unique(rows, "year_month")),
        "variables": _unique(rows, "variable"),
        "year_month_min": _min_or_none(row.get("year_month") for row in rows),
        "year_month_max": _max_or_none(row.get("year_month") for row in rows),
        "observation_count_total": int(
            sum(_float_or_zero(row.get("observation_count")) for row in rows)
        ),
        "aggregation": _unique(rows, "aggregation"),
    }


def _fuzzy_state_summary(path: Path) -> dict[str, object]:
    rows = _read_csv_rows(path)
    return {
        "rows": len(rows),
        "sites": len(_unique(rows, "site_id")),
        "months": len(_unique(rows, "year_month")),
        "year_month_min": _min_or_none(row.get("year_month") for row in rows),
        "year_month_max": _max_or_none(row.get("year_month") for row in rows),
        "score_ranges": {
            column: _range(rows, column)
            for column in _SUMMARY_SCORE_COLUMNS
            if any(row.get(column) not in {None, ""} for row in rows)
        },
        "trophic_state_counts": _value_counts(rows, "state_trophic_expert"),
    }


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _unique(rows: list[dict[str, str]], column: str) -> list[str]:
    return sorted({str(row[column]) for row in rows if row.get(column) not in {None, ""}})


def _min_or_none(values: Any) -> str | None:
    clean = sorted(str(value) for value in values if value not in {None, ""})
    return clean[0] if clean else None


def _max_or_none(values: Any) -> str | None:
    clean = sorted(str(value) for value in values if value not in {None, ""})
    return clean[-1] if clean else None


def _float_or_zero(value: object) -> float:
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return 0.0


def _range(rows: list[dict[str, str]], column: str) -> dict[str, float | None]:
    values = [_float_or_none(row.get(column)) for row in rows]
    clean = [value for value in values if value is not None]
    return {
        "min": min(clean) if clean else None,
        "max": max(clean) if clean else None,
    }


def _float_or_none(value: object) -> float | None:
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return None


def _value_counts(rows: list[dict[str, str]], column: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(column)
        if value in {None, ""}:
            continue
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))
