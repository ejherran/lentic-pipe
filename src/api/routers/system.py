"""System endpoints for the public API scaffold."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.config import PIPELINE_REGISTRY, api_metadata
from src.api.errors import error_catalog, warning_catalog
from src.api.schemas.system import HealthResponse, VersionResponse

router = APIRouter(tags=["System"])


@router.get("/health/live", response_model=HealthResponse)
async def health_live() -> HealthResponse:
    """Return process liveness."""

    return HealthResponse(status="ok", components={"api": "ok"})


@router.get("/health/ready", response_model=HealthResponse)
async def health_ready() -> HealthResponse:
    """Return readiness for the scaffold phase."""

    return HealthResponse(status="ok", components={"api": "ok", "storage": "not_configured"})


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health() -> HealthResponse:
    """Backward-compatible health alias."""

    return await health_ready()


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """Return API version and scientific workflow registry."""

    metadata = api_metadata()
    return VersionResponse(
        api_version=str(metadata["api_version"]),
        project=str(metadata["project"]),
        stage=str(metadata["stage"]),
        supported_horizons=list(metadata["supported_horizons"]),
        documents={
            "protocol": str(metadata["protocol"]),
            "dataset_contract": str(metadata["dataset_contract"]),
            "error_contract": str(metadata["error_contract"]),
        },
        workflows=[
            {
                "name": workflow.name,
                "status": workflow.status,
                "description": workflow.description,
                "notes": list(workflow.notes),
            }
            for workflow in PIPELINE_REGISTRY
        ],
    )


@router.get("/errors")
async def errors() -> dict[str, object]:
    """Return machine-readable error and warning catalogs."""

    return {"errors": error_catalog(), "warnings": warning_catalog()}
