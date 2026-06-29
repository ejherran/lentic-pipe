import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import asc, desc, func, select, update
from sqlalchemy.engine import CursorResult

from src.api.core.dependencies import CurrentUser, DBDep, require_experiment_role
from src.api.core.openapi import HTTP_401, HTTP_403, HTTP_404, HTTP_422
from src.api.core.permissions import is_admin
from src.api.core.request_id import get_request_id
from src.api.errors import ApiErrorResponse, ApiProblem, ErrorCode
from src.api.models.experiment import CollaboratorRole, ExperimentCollaborator
from src.api.models.run import ModelType, Run, RunStatus
from src.api.schemas.common import CancelledResponse, Page
from src.api.schemas.prediction import RunAlertResponse, RunPredictionResponse
from src.api.schemas.run import (
    RunArtifactListResponse,
    RunArtifactPreviewResponse,
    RunCompareRequest,
    RunCompareResponse,
    RunCreateRequest,
    RunResultSummaryResponse,
    RunResponse,
    RunResultsResponse,
)
from src.api.services.run_artifacts import (
    RunArtifactError,
    list_run_artifacts,
    preview_run_artifact,
    summarize_run_results,
)
from src.api.services.run_predictions import (
    RunPredictionError,
    list_run_alerts,
    list_run_predictions,
)
from src.api.services.run_repository import RunExecutionNotFoundError
from src.api.tasks.training import train_model_task

_RUN_SORT_FIELDS: dict[str, Any] = {
    "created_at": Run.created_at,
    "name": Run.name,
    "status": Run.status,
    "model_type": Run.model_type,
}

router = APIRouter(tags=["Runs"])

EditorDep = require_experiment_role(CollaboratorRole.editor)
ViewerDep = require_experiment_role(CollaboratorRole.viewer)


class RunScientificOutputError(Exception):
    """Expected failure while resolving scientific output for a persisted Run."""

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


async def _assert_run_access(run: Run, current_user, db: DBDep) -> None:
    """Raise 403 if user is not a collaborator on the run's experiment."""
    if is_admin(current_user.system_role):
        return
    result = await db.execute(
        select(ExperimentCollaborator).where(
            ExperimentCollaborator.experiment_id == run.experiment_id,
            ExperimentCollaborator.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.post(
    "/experiments/{experiment_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[EditorDep],
    summary="Launch a training run",
    description=(
        "Queue an async model training job for the experiment. Returns `202 Accepted` "
        "immediately with `status: pending`. The Taskiq worker picks up the job and "
        "transitions status through `running` → `completed` or `failed`.\n\n"
        "**Config requirements by model type:**\n\n"
        "| Model | Required `config` keys |\n"
        "|---|---|\n"
        "| `PIPE_GRUD` | `horizon_days`, `seed` |\n"
        "| `PIPE_NEURAL_ODE` | `horizon_days`, `seed` |\n"
        "| `MIFAL`, `BASELINE_*` | none |\n\n"
        "Requires at least `editor` experiment role."
    ),
    responses={
        403: {"description": "Caller has only `viewer` role on this experiment."},
        422: {"description": "Required `config` keys missing for the selected model type."},
        **HTTP_401,
        **HTTP_404,
    },
)
async def create_run(
    experiment_id: uuid.UUID, body: RunCreateRequest, current_user: CurrentUser, db: DBDep
):
    run = Run(
        experiment_id=experiment_id,
        name=body.name,
        model_type=body.model_type,
        config=body.config,
        created_by=current_user.id,
    )
    db.add(run)
    await db.flush()

    task = await train_model_task.kiq(run_id=str(run.id), request_id=get_request_id())
    run.task_id = task.task_id

    await db.commit()
    await db.refresh(run)
    return run


@router.get(
    "/experiments/{experiment_id}/runs",
    response_model=Page[RunResponse],
    dependencies=[ViewerDep],
    summary="List runs",
    description=(
        "Paginated list of training runs within the experiment, ordered by `created_at` descending. "
        "Requires at least `viewer` experiment role.\n\n"
        "**Filters:** `?status=pending|running|completed|failed`, `?model_type=PIPE_GRUD|…`, `?name=<substring>`."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def list_runs(
    experiment_id: uuid.UUID,
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Zero-based page offset"),
    status_filter: RunStatus | None = Query(None, alias="status", description="Filter by run status"),
    model_type: ModelType | None = Query(None, description="Filter by model type"),
    name: str | None = Query(None, description="Case-insensitive substring search on run name"),
    sort_by: Literal["created_at", "name", "status", "model_type"] = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="Sort order: asc | desc"),
):
    base = select(Run).where(Run.experiment_id == experiment_id)
    count_stmt = select(func.count()).select_from(Run).where(Run.experiment_id == experiment_id)

    if status_filter is not None:
        base = base.where(Run.status == status_filter)
        count_stmt = count_stmt.where(Run.status == status_filter)
    if model_type is not None:
        base = base.where(Run.model_type == model_type)
        count_stmt = count_stmt.where(Run.model_type == model_type)
    if name is not None:
        pattern = f"%{name}%"
        base = base.where(Run.name.ilike(pattern))
        count_stmt = count_stmt.where(Run.name.ilike(pattern))

    col = _RUN_SORT_FIELDS[sort_by]
    order_clause = desc(col) if order.lower() != "asc" else asc(col)

    total = (await db.execute(count_stmt)).scalar_one()
    items = list(
        (await db.execute(base.order_by(order_clause).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/experiments/{experiment_id}/runs/cancel-all",
    response_model=CancelledResponse,
    summary="Cancel all active runs",
    description=(
        "Cancel every run in the experiment that is still `pending` or `running` in bulk. "
        "Returns the count of cancelled runs. Requires at least `editor` experiment role."
    ),
    dependencies=[EditorDep],
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def cancel_all_runs(experiment_id: uuid.UUID, db: DBDep):
    now = datetime.now(timezone.utc)
    cursor = cast(
        CursorResult[Any],
        await db.execute(
            update(Run)
            .where(
                Run.experiment_id == experiment_id,
                Run.status.in_([RunStatus.pending, RunStatus.running]),
            )
            .values(status=RunStatus.cancelled, completed_at=now)
        ),
    )
    await db.commit()
    return CancelledResponse(cancelled=cursor.rowcount)


@router.get(
    "/runs/{run_id}",
    response_model=RunResponse,
    summary="Get run",
    description=(
        "Return the run object including current status and metadata. "
        "The caller must be a collaborator (any role) on the run's experiment, or an admin."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def get_run(run_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    await _assert_run_access(run, current_user, db)
    return run


@router.post(
    "/runs/{run_id}/cancel",
    response_model=RunResponse,
    summary="Cancel a run",
    description=(
        "Cancel a run that is still `pending` or `running`. "
        "The status transitions to `cancelled` immediately in the database; "
        "if the Taskiq worker has already picked up the job it will complete normally "
        "but its result will be discarded.\n\n"
        "The caller must be a collaborator (any role) on the run's experiment, or an admin."
    ),
    responses={
        400: {"description": "Run is already completed, failed, or cancelled."},
        **HTTP_401,
        **HTTP_403,
        **HTTP_404,
    },
)
async def cancel_run(run_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not is_admin(current_user.system_role):
        result = await db.execute(
            select(ExperimentCollaborator).where(
                ExperimentCollaborator.experiment_id == run.experiment_id,
                ExperimentCollaborator.user_id == current_user.id,
                ExperimentCollaborator.role.in_(
                    [CollaboratorRole.owner, CollaboratorRole.editor]
                ),
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if run.status not in (RunStatus.pending, RunStatus.running):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel a run with status '{run.status}'",
        )
    run.status = RunStatus.cancelled
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run


@router.get(
    "/runs/{run_id}/results",
    response_model=RunResultsResponse,
    summary="Get run results",
    description=(
        "Return the run result object. Available at any status — `results` and `error_message` "
        "are `null` until the job completes or fails.\n\n"
        "The `results.metrics` object is nested by horizon: "
        "`{\"horizon_30\": {\"auc\": 0.87, \"brier\": 0.12}, ...}`."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def get_run_results(run_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    await _assert_run_access(run, current_user, db)
    return run


@router.get(
    "/runs/{run_id}/artifacts",
    response_model=RunArtifactListResponse,
    summary="List scientific run artifacts",
    description=(
        "List generated scientific workflow artifacts for an async run that was "
        "executed through a registered job-backed scientific adapter. This is a "
        "run-id convenience wrapper over the underlying plan-scoped artifact view."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404, 409: {"model": ApiErrorResponse}},
)
async def list_scientific_run_artifacts(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> RunArtifactListResponse | JSONResponse:
    try:
        plan_id = await _scientific_plan_id_for_run(run_id, current_user, db)
        return list_run_artifacts(plan_id)
    except RunScientificOutputError as error:
        return _run_scientific_output_error_response(error)
    except RunExecutionNotFoundError:
        return _run_scientific_output_error_response(_missing_scientific_execution(run_id))


@router.get(
    "/runs/{run_id}/artifacts/{artifact_name}/preview",
    response_model=RunArtifactPreviewResponse,
    summary="Preview a scientific run artifact",
    description=(
        "Preview a bounded number of rows or lines from a generated scientific "
        "workflow artifact for an async run. Only text-safe artifact formats are "
        "previewable."
    ),
    responses={
        **HTTP_401,
        **HTTP_403,
        **HTTP_404,
        400: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
    },
)
async def preview_scientific_run_artifact(
    run_id: uuid.UUID,
    artifact_name: str,
    current_user: CurrentUser,
    db: DBDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> RunArtifactPreviewResponse | JSONResponse:
    try:
        plan_id = await _scientific_plan_id_for_run(run_id, current_user, db)
        return preview_run_artifact(plan_id, artifact_name, limit=limit)
    except RunScientificOutputError as error:
        return _run_scientific_output_error_response(error)
    except RunExecutionNotFoundError:
        return _run_scientific_output_error_response(_missing_scientific_execution(run_id))
    except RunArtifactError as error:
        return _artifact_error_response(error)


@router.get(
    "/runs/{run_id}/results/summary",
    response_model=RunResultSummaryResponse,
    summary="Summarize scientific run results",
    description=(
        "Return structured summaries for generated scientific workflow artifacts "
        "attached to an async run."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404, 409: {"model": ApiErrorResponse}},
)
async def summarize_scientific_run_results(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> RunResultSummaryResponse | JSONResponse:
    try:
        plan_id = await _scientific_plan_id_for_run(run_id, current_user, db)
        return summarize_run_results(plan_id)
    except RunScientificOutputError as error:
        return _run_scientific_output_error_response(error)
    except RunExecutionNotFoundError:
        return _run_scientific_output_error_response(_missing_scientific_execution(run_id))


@router.get(
    "/runs/{run_id}/predictions",
    response_model=RunPredictionResponse,
    summary="List scientific run predictions",
    description=(
        "Return prediction or state-score records generated by a job-backed "
        "scientific workflow run."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404, 409: {"model": ApiErrorResponse}},
)
async def list_scientific_run_predictions(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
    limit: int = Query(default=100, ge=1, le=1000),
) -> RunPredictionResponse | JSONResponse:
    try:
        plan_id = await _scientific_plan_id_for_run(run_id, current_user, db)
        return list_run_predictions(plan_id, limit=limit)
    except RunScientificOutputError as error:
        return _run_scientific_output_error_response(error)
    except RunExecutionNotFoundError:
        return _run_scientific_output_error_response(_missing_scientific_execution(run_id))
    except RunPredictionError as error:
        return _prediction_error_response(error)


@router.get(
    "/runs/{run_id}/alerts",
    response_model=RunAlertResponse,
    summary="List scientific run alerts",
    description=(
        "Return alert records generated by a job-backed scientific workflow run."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404, 409: {"model": ApiErrorResponse}},
)
async def list_scientific_run_alerts(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
    limit: int = Query(default=100, ge=1, le=1000),
    only_alerts: bool = Query(default=False),
) -> RunAlertResponse | JSONResponse:
    try:
        plan_id = await _scientific_plan_id_for_run(run_id, current_user, db)
        return list_run_alerts(plan_id, limit=limit, only_alerts=only_alerts)
    except RunScientificOutputError as error:
        return _run_scientific_output_error_response(error)
    except RunExecutionNotFoundError:
        return _run_scientific_output_error_response(_missing_scientific_execution(run_id))
    except RunPredictionError as error:
        return _prediction_error_response(error)


@router.post(
    "/experiments/{experiment_id}/runs/compare",
    response_model=RunCompareResponse,
    dependencies=[ViewerDep],
    summary="Compare runs",
    description=(
        "Side-by-side metric comparison for 2–10 completed runs within the same experiment. "
        "Requires at least `viewer` experiment role.\n\n"
        "The `metric_table` in the response uses dot-notation keys "
        "(e.g. `horizon_30.auc`) and maps run name (or ID if unnamed) to the metric value. "
        "Missing values are `null`."
    ),
    responses={
        400: {"description": "One or more runs do not belong to this experiment."},
        **HTTP_401,
        **HTTP_403,
        **HTTP_404,
        422: {"description": "Fewer than 2 run IDs, more than 10, or duplicate IDs."},
    },
)
async def compare_runs(
    experiment_id: uuid.UUID, body: RunCompareRequest, db: DBDep
):
    rows = list(
        (
            await db.execute(select(Run).where(Run.id.in_(body.run_ids)))
        )
        .scalars()
        .all()
    )
    found_ids = {r.id for r in rows}
    for run_id in body.run_ids:
        if run_id not in found_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run {run_id} not found",
            )
    runs = []
    for run_id in body.run_ids:
        run = next(r for r in rows if r.id == run_id)
        if run.experiment_id != experiment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Run {run_id} does not belong to this experiment",
            )
        runs.append(run)

    metric_table: dict[str, dict[str, float | None]] = {}
    entries = []

    for run in runs:
        label = str(run.name or run.id)
        metrics = _extract_metrics(run.results)
        entries.append(
            {
                "run_id": run.id,
                "name": run.name,
                "model_type": run.model_type,
                "status": run.status,
                "metrics": metrics,
            }
        )
        for metric_key, value in (metrics or {}).items():
            metric_table.setdefault(metric_key, {})[label] = value

    return RunCompareResponse(
        experiment_id=experiment_id,
        runs=entries,
        metric_table=metric_table,
    )


@router.get(
    "/runs/{run_id}/results.csv",
    summary="Download run results as CSV",
    description=(
        "Download the run's metrics as a CSV file for direct import into notebooks or spreadsheets. "
        "Each row is one metric in dot-notation (e.g. `horizon_30.auc`).\n\n"
        "**Columns:** `run_id`, `run_name`, `model_type`, `status`, `metric`, `value`.\n\n"
        "Returns an empty CSV (header only) when no metrics are available yet."
    ),
    responses={
        200: {"content": {"text/csv": {}}, "description": "CSV file attachment."},
        **HTTP_401,
        **HTTP_403,
        **HTTP_404,
    },
)
async def download_run_results_csv(run_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    await _assert_run_access(run, current_user, db)

    metrics = _extract_metrics(run.results)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["run_id", "run_name", "model_type", "status", "metric", "value"])
    for metric_key, value in metrics.items():
        writer.writerow([run.id, run.name, run.model_type, run.status, metric_key, value])

    buf.seek(0)
    filename = f"run_{run.id}_results.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _extract_metrics(results: dict | None) -> dict[str, float | None]:
    """Flatten the nested metrics dict from a run result into dot-notation keys."""
    if not results:
        return {}
    flat: dict[str, float | None] = {}
    raw = results.get("metrics", {})
    for horizon, horizon_metrics in raw.items():
        if isinstance(horizon_metrics, dict):
            for metric, value in horizon_metrics.items():
                flat[f"{horizon}.{metric}"] = value
    return flat


async def _scientific_plan_id_for_run(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> str:
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    await _assert_run_access(run, current_user, db)
    return _plan_id_from_results(run)


def _plan_id_from_results(run: Run) -> str:
    if run.status != RunStatus.completed:
        raise RunScientificOutputError(
            ErrorCode.dependency_not_ready,
            "Run has not completed a scientific workflow execution yet.",
            details={"run_id": str(run.id), "run_status": run.status.value},
            http_status=424,
        )
    results = run.results
    if not isinstance(results, dict):
        raise _unsupported_scientific_output(run)
    plan = results.get("plan")
    if isinstance(plan, dict) and plan.get("plan_id"):
        return str(plan["plan_id"])
    execution = results.get("execution")
    if isinstance(execution, dict) and execution.get("plan_id"):
        return str(execution["plan_id"])
    raise _unsupported_scientific_output(run)


def _unsupported_scientific_output(run: Run) -> RunScientificOutputError:
    return RunScientificOutputError(
        ErrorCode.unsupported_pipeline_for_dataset,
        "Run results do not include a job-backed scientific workflow plan.",
        details={
            "run_id": str(run.id),
            "run_status": run.status.value,
            "model_type": run.model_type.value,
            "expected_result_keys": ["plan.plan_id", "execution.plan_id"],
        },
    )


def _missing_scientific_execution(run_id: uuid.UUID) -> RunScientificOutputError:
    return RunScientificOutputError(
        ErrorCode.dependency_not_ready,
        "Run results reference a scientific plan whose execution artifacts are not available.",
        details={"run_id": str(run_id)},
        http_status=424,
    )


def _run_scientific_output_error_response(error: RunScientificOutputError) -> JSONResponse:
    response = ApiErrorResponse(
        error=ApiProblem(
            code=error.code,
            message=error.message,
            details=error.details,
        )
    )
    return JSONResponse(
        status_code=error.http_status,
        content=response.model_dump(mode="json"),
    )


def _artifact_error_response(error: RunArtifactError) -> JSONResponse:
    response = ApiErrorResponse(
        error=ApiProblem(
            code=error.code,
            message=error.message,
            details=error.details,
        )
    )
    return JSONResponse(
        status_code=error.http_status,
        content=response.model_dump(mode="json"),
    )


def _prediction_error_response(error: RunPredictionError) -> JSONResponse:
    response = ApiErrorResponse(
        error=ApiProblem(
            code=error.code,
            message=error.message,
            details=error.details,
        )
    )
    return JSONResponse(
        status_code=error.http_status,
        content=response.model_dump(mode="json"),
    )
