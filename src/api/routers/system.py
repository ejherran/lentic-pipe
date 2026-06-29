import asyncio

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from src.api.config import PIPELINE_REGISTRY, api_metadata, settings
from src.api.core.blocklist import get_redis_client
from src.api.core.dependencies import DBDep
from src.api.errors import error_catalog, warning_catalog

router = APIRouter(tags=["System"])


async def _check_redis() -> str:
    try:
        r = get_redis_client()
        await asyncio.wait_for(r.ping(), timeout=1.0)
        return "ok"
    except Exception:
        return "error"


@router.get(
    "/health/live",
    summary="Liveness probe",
    description=(
        "Always returns `200 ok` as long as the process is running. "
        "Use this for liveness checks — it does **not** verify database or Redis connectivity. "
        "Does not require authentication."
    ),
)
async def health_live():
    return {"status": "ok"}


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description=(
        "Check the connectivity status of the database and Redis. "
        "Returns `status: ok` only when both services are reachable. "
        "Returns `status: degraded` with `503` when any dependency is unavailable. "
        "Use this for readiness/load-balancer probes. "
        "Does not require authentication."
    ),
)
async def health_ready(db: DBDep):
    if not settings.STRICT_READINESS_CHECKS:
        return {
            "status": "ok",
            "database": "not_checked",
            "redis": "not_checked",
            "components": {"api": "ok", "database": "not_checked", "redis": "not_checked"},
            "environment": settings.APP_ENV,
        }

    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=1.0)
        db_status = "ok"
    except Exception:
        db_status = "error"

    redis_status = await _check_redis()

    all_ok = db_status == "ok" and redis_status == "ok"
    payload = {
        "status": "ok" if all_ok else "degraded",
        "database": db_status,
        "redis": redis_status,
        "components": {"api": "ok", "database": db_status, "redis": redis_status},
        "environment": settings.APP_ENV,
    }
    from fastapi.responses import JSONResponse

    return JSONResponse(payload, status_code=200 if all_ok else 503)


@router.get(
    "/health",
    summary="Health check (alias for /health/ready)",
    description=(
        "Alias for `/health/ready`. Kept for backward compatibility. "
        "Does not require authentication."
    ),
    include_in_schema=False,
)
async def health(db: DBDep):
    return await health_ready(db)


@router.get(
    "/version",
    summary="API version and model registry",
    description=(
        "Return the API version string and the implementation status of every registered "
        "model type. Does not require authentication.\n\n"
        "Status values: `planned` (stub only), `beta` (under validation), `stable`."
    ),
)
async def version():
    metadata = api_metadata()
    return {
        "version": settings.APP_VERSION,
        "api_version": metadata["api_version"],
        "project": metadata["project"],
        "stage": metadata["stage"],
        "supported_horizons": metadata["supported_horizons"],
        "environment": settings.APP_ENV,
        "documents": {
            "protocol": metadata["protocol"],
            "dataset_contract": metadata["dataset_contract"],
            "error_contract": metadata["error_contract"],
        },
        "workflows": [
            {
                "name": workflow.name,
                "status": workflow.status,
                "description": workflow.description,
                "notes": list(workflow.notes),
            }
            for workflow in PIPELINE_REGISTRY
        ],
        "models": {
            "PIPE_GRUD": "planned",
            "PIPE_NEURAL_ODE": "planned",
            "MIFAL": "planned",
            "BASELINE_CONSTANT": "planned",
            "BASELINE_LOGISTIC": "planned",
            "BASELINE_RF": "planned",
            "BASELINE_GB": "planned",
        },
    }


@router.get(
    "/errors",
    summary="Scientific error and warning catalog",
    description=(
        "Return the machine-readable error and warning catalog used by the scientific "
        "dataset and workflow layer."
    ),
)
async def errors():
    return {"errors": error_catalog(), "warnings": warning_catalog()}


@router.get("/metrics", include_in_schema=False)
async def metrics():
    """Return Prometheus metrics without request middleware coupling."""

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
