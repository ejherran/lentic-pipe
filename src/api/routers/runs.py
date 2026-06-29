"""Run planning endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from src.api.errors import ApiErrorResponse, ApiProblem, ErrorCode
from src.api.schemas.run import (
    RunArtifactListResponse,
    RunArtifactPreviewResponse,
    RunExecutionResponse,
    RunPlanRequest,
    RunPlanResponse,
    RunResultSummaryResponse,
)
from src.api.schemas.prediction import RunAlertResponse, RunPredictionResponse
from src.api.services.dataset_repository import DatasetNotFoundError
from src.api.services.run_artifacts import (
    RunArtifactError,
    list_run_artifacts,
    preview_run_artifact,
    summarize_run_results,
)
from src.api.services.run_executor import RunExecutionError, execute_run_plan
from src.api.services.run_predictions import (
    RunPredictionError,
    list_run_alerts,
    list_run_predictions,
)
from src.api.services.run_planner import plan_run_request
from src.api.services.run_repository import (
    RunExecutionNotFoundError,
    RunPlanNotFoundError,
    read_run_execution,
    read_run_plan,
    save_run_plan,
)

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.post(
    "/plan",
    response_model=RunPlanResponse,
    responses={404: {"model": ApiErrorResponse}},
)
async def plan_run(request: RunPlanRequest) -> RunPlanResponse | JSONResponse:
    """Create and persist a synchronous dry-run plan for a registered dataset workflow."""

    try:
        return save_run_plan(plan_run_request(request))
    except DatasetNotFoundError:
        return _not_found(request.dataset_id)


@router.get(
    "/plans/{plan_id}",
    response_model=RunPlanResponse,
    responses={404: {"model": ApiErrorResponse}},
)
async def get_run_plan(plan_id: str) -> RunPlanResponse | JSONResponse:
    """Fetch a previously persisted dry-run plan."""

    try:
        return read_run_plan(plan_id)
    except RunPlanNotFoundError:
        return _not_found(plan_id)


@router.post(
    "/plans/{plan_id}/execute",
    response_model=RunExecutionResponse,
    responses={404: {"model": ApiErrorResponse}, 409: {"model": ApiErrorResponse}},
)
async def execute_plan(plan_id: str) -> RunExecutionResponse | JSONResponse:
    """Execute a persisted plan when it targets an initial safe local workflow."""

    try:
        return execute_run_plan(plan_id)
    except (DatasetNotFoundError, RunPlanNotFoundError):
        return _not_found(plan_id)
    except RunExecutionError as error:
        return _error_response(error)


@router.get(
    "/plans/{plan_id}/execution",
    response_model=RunExecutionResponse,
    responses={404: {"model": ApiErrorResponse}},
)
async def get_plan_execution(plan_id: str) -> RunExecutionResponse | JSONResponse:
    """Fetch a persisted synchronous execution response for a plan."""

    try:
        return read_run_execution(plan_id)
    except RunExecutionNotFoundError:
        return _not_found(plan_id)


@router.get(
    "/plans/{plan_id}/artifacts",
    response_model=RunArtifactListResponse,
    responses={404: {"model": ApiErrorResponse}},
)
async def get_plan_artifacts(plan_id: str) -> RunArtifactListResponse | JSONResponse:
    """List generated artifacts for a completed local run execution."""

    try:
        return list_run_artifacts(plan_id)
    except RunExecutionNotFoundError:
        return _not_found(plan_id)


@router.get(
    "/plans/{plan_id}/artifacts/{artifact_name}/preview",
    response_model=RunArtifactPreviewResponse,
    responses={400: {"model": ApiErrorResponse}, 404: {"model": ApiErrorResponse}},
)
async def preview_plan_artifact(
    plan_id: str,
    artifact_name: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> RunArtifactPreviewResponse | JSONResponse:
    """Return a bounded JSON-safe preview of a generated run artifact."""

    try:
        return preview_run_artifact(plan_id, artifact_name, limit=limit)
    except RunExecutionNotFoundError:
        return _not_found(plan_id)
    except RunArtifactError as error:
        return _artifact_error_response(error)


@router.get(
    "/plans/{plan_id}/results/summary",
    response_model=RunResultSummaryResponse,
    responses={404: {"model": ApiErrorResponse}},
)
async def get_plan_result_summary(plan_id: str) -> RunResultSummaryResponse | JSONResponse:
    """Return structured summaries for generated local run results."""

    try:
        return summarize_run_results(plan_id)
    except RunExecutionNotFoundError:
        return _not_found(plan_id)


@router.get(
    "/plans/{plan_id}/predictions",
    response_model=RunPredictionResponse,
    responses={404: {"model": ApiErrorResponse}, 409: {"model": ApiErrorResponse}},
)
async def get_plan_predictions(
    plan_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
) -> RunPredictionResponse | JSONResponse:
    """Return run-scoped prediction/state-score records when available."""

    try:
        return list_run_predictions(plan_id, limit=limit)
    except RunExecutionNotFoundError:
        return _not_found(plan_id)
    except RunPredictionError as error:
        return _prediction_error_response(error)


@router.get(
    "/plans/{plan_id}/alerts",
    response_model=RunAlertResponse,
    responses={404: {"model": ApiErrorResponse}, 409: {"model": ApiErrorResponse}},
)
async def get_plan_alerts(
    plan_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    only_alerts: bool = Query(default=False),
) -> RunAlertResponse | JSONResponse:
    """Return run-scoped alert records when an alert surface is available."""

    try:
        return list_run_alerts(plan_id, limit=limit, only_alerts=only_alerts)
    except RunExecutionNotFoundError:
        return _not_found(plan_id)
    except RunPredictionError as error:
        return _prediction_error_response(error)


def _not_found(resource_id: str) -> JSONResponse:
    response = ApiErrorResponse(
        error=ApiProblem(
            code=ErrorCode.resource_not_found,
            message="Requested API registry entry does not exist.",
            details={"resource_id": resource_id},
        )
    )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=response.model_dump(mode="json"),
    )


def _error_response(error: RunExecutionError) -> JSONResponse:
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
