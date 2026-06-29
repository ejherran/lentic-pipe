from typing import Literal

from fastapi import APIRouter, Query

from src.api.core.dependencies import CurrentUser, DBDep
from src.api.core.openapi import HTTP_401
from src.api.models.experiment import ExperimentStatus
from src.api.schemas.workspace import WorkspaceCatalogResponse
from src.api.services.workspace_catalog import get_workspace_catalog

router = APIRouter(prefix="/workspace", tags=["Workspace"])


@router.get(
    "/catalog",
    response_model=WorkspaceCatalogResponse,
    summary="Catalog workspace resources",
    description=(
        "Return an authenticated, metadata-only catalog of experiments visible "
        "to the caller, including dataset/run counts, latest resources, and "
        "scientific output views discoverable from completed run results. Admins "
        "see all experiments; other users see only collaborations."
    ),
    responses={**HTTP_401},
)
async def get_catalog(
    current_user: CurrentUser,
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Zero-based page offset"),
    status_filter: ExperimentStatus | None = Query(None, alias="status"),
    q: str | None = Query(None, description="Case-insensitive substring search on experiment title"),
    sort_by: Literal["created_at", "updated_at", "title", "status"] = Query("updated_at"),
    order: Literal["asc", "desc"] = Query("desc"),
) -> WorkspaceCatalogResponse:
    return await get_workspace_catalog(
        db,
        current_user,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
        q=q,
        sort_by=sort_by,
        order=order,
    )
