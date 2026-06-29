"""Run planning endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from src.api.errors import ApiErrorResponse, ApiProblem, ErrorCode
from src.api.schemas.run import RunExecutionResponse, RunPlanRequest, RunPlanResponse
from src.api.services.dataset_repository import DatasetNotFoundError
from src.api.services.run_executor import RunExecutionError, execute_run_plan
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
