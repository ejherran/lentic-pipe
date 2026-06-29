"""Dataset validation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from src.api.errors import ApiErrorResponse, ApiProblem, ErrorCode
from src.api.schemas.dataset import (
    DatasetRegistrationResponse,
    DatasetValidationRequest,
    DatasetValidationResponse,
)
from src.api.services.dataset_repository import (
    DatasetNotFoundError,
    read_registered_dataset,
    register_dataset_request,
)
from src.api.services.dataset_validation import validate_dataset_request

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.post("/validate", response_model=DatasetValidationResponse)
async def validate_dataset(request: DatasetValidationRequest) -> DatasetValidationResponse:
    """Validate an external long-form dataset without creating artifacts."""

    return validate_dataset_request(request)


@router.post(
    "",
    response_model=DatasetRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_dataset(request: DatasetValidationRequest) -> DatasetRegistrationResponse:
    """Validate and register an external dataset with reproducibility artifacts."""

    return register_dataset_request(request)


@router.get(
    "/{dataset_id}",
    response_model=DatasetRegistrationResponse,
    responses={404: {"model": ApiErrorResponse}},
)
async def get_dataset(dataset_id: str) -> DatasetRegistrationResponse | JSONResponse:
    """Fetch a previously registered dataset manifest and validation result."""

    try:
        return read_registered_dataset(dataset_id)
    except DatasetNotFoundError:
        return _not_found(dataset_id)


def _not_found(dataset_id: str) -> JSONResponse:
    response = ApiErrorResponse(
        error=ApiProblem(
            code=ErrorCode.resource_not_found,
            message="Dataset registry entry does not exist.",
            details={"dataset_id": dataset_id},
        )
    )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=response.model_dump(mode="json"),
    )
