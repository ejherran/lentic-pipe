import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select

from src.api.core.audit import fire_audit
from src.api.core.dependencies import CurrentUser, DBDep, require_experiment_role
from src.api.core.openapi import HTTP_401, HTTP_403, HTTP_404, HTTP_409, HTTP_422
from src.api.core.permissions import can_create_experiments, is_admin
from src.api.models.audit_log import AuditAction
from src.api.models.experiment import (
    CollaboratorRole,
    Dataset,
    Experiment,
    ExperimentCollaborator,
    ExperimentStatus,
)
from src.api.models.run import Run
from src.api.models.user import User
from src.api.schemas.common import Page
from src.api.schemas.experiment import (
    AddCollaboratorRequest,
    CollaboratorResponse,
    DatasetCreateRequest,
    DatasetResponse,
    ExperimentCreateRequest,
    ExperimentImportRequest,
    ExperimentResponse,
    ExperimentUpdateRequest,
    UpdateCollaboratorRequest,
)

router = APIRouter(prefix="/experiments", tags=["Experiments"])


def _dt(v: object) -> str | None:
    return v.isoformat() if isinstance(v, datetime) else None  # type: ignore[union-attr]

_EXP_SORT_FIELDS: dict[str, Any] = {
    "created_at": Experiment.created_at,
    "updated_at": Experiment.updated_at,
    "title": Experiment.title,
    "status": Experiment.status,
}

OwnerDep = require_experiment_role(CollaboratorRole.owner)
EditorDep = require_experiment_role(CollaboratorRole.editor)
ViewerDep = require_experiment_role(CollaboratorRole.viewer)


@router.post(
    "",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create experiment",
    description=(
        "Create a new experiment. The caller is automatically assigned the `owner` role.\n\n"
        "Requires `system_role: researcher` or `admin`. Users with `system_role: viewer` "
        "cannot create experiments."
    ),
    responses={
        403: {"description": "Insufficient system role (viewer cannot create experiments)."},
        **HTTP_401,
        **HTTP_422,
    },
)
async def create_experiment(body: ExperimentCreateRequest, current_user: CurrentUser, db: DBDep):
    if not can_create_experiments(current_user.system_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    experiment = Experiment(
        title=body.title,
        description=body.description,
        config=body.config,
        created_by=current_user.id,
    )
    db.add(experiment)
    await db.flush()

    ownership = ExperimentCollaborator(
        experiment_id=experiment.id,
        user_id=current_user.id,
        role=CollaboratorRole.owner,
        invited_by_id=None,
    )
    db.add(ownership)
    await db.commit()
    await db.refresh(experiment)
    return experiment


@router.post(
    "/import",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import experiment from export",
    description=(
        "Create a new experiment from a JSON document produced by "
        "`GET /experiments/{id}/export`. "
        "The caller becomes the `owner` of the new experiment.\n\n"
        "**What is imported:** `title`, `description`, `config` from the experiment object, "
        "and all dataset metadata records.\n\n"
        "**What is NOT imported:** runs (stale ML artefacts), collaborators "
        "(the importing user becomes the sole owner).\n\n"
        "The title is suffixed with `\" (imported)\"` to distinguish it from the original.\n\n"
        "Requires `system_role: researcher` or `admin`."
    ),
    responses={
        403: {"description": "Insufficient system role."},
        **HTTP_401,
        **HTTP_422,
    },
)
async def import_experiment(
    body: ExperimentImportRequest, current_user: CurrentUser, db: DBDep
):
    if not can_create_experiments(current_user.system_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    exp_data = body.experiment
    title = str(exp_data.get("title", "Untitled")) + " (imported)"
    description = exp_data.get("description")
    config = exp_data.get("config") or {}

    experiment = Experiment(
        title=title,
        description=description,
        config=config,
        created_by=current_user.id,
    )
    db.add(experiment)
    await db.flush()

    ownership = ExperimentCollaborator(
        experiment_id=experiment.id,
        user_id=current_user.id,
        role=CollaboratorRole.owner,
        invited_by_id=None,
    )
    db.add(ownership)

    for ds_data in body.datasets:
        ds = Dataset(
            experiment_id=experiment.id,
            name=str(ds_data.get("name", "dataset")),
            description=ds_data.get("description"),
            source_id=ds_data.get("source_id"),
            file_path=ds_data.get("file_path"),
            meta=ds_data.get("meta"),
            created_by=current_user.id,
        )
        db.add(ds)

    await db.commit()
    await db.refresh(experiment)
    return experiment


@router.get(
    "",
    response_model=Page[ExperimentResponse],
    summary="List experiments",
    description=(
        "Paginated list of experiments the caller has access to.\n\n"
        "- Regular users see only experiments where they are a collaborator.\n"
        "- Admins see all experiments.\n\n"
        "**Filters:** `?status=active|archived` and `?q=<title substring>` (case-insensitive)."
    ),
    responses={**HTTP_401},
)
async def list_experiments(
    current_user: CurrentUser,
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Zero-based page offset"),
    status_filter: ExperimentStatus | None = Query(None, alias="status", description="Filter by experiment status"),
    q: str | None = Query(None, description="Case-insensitive substring search on title"),
    sort_by: str = Query("created_at", description="Sort field: created_at | updated_at | title | status"),
    order: str = Query("desc", description="Sort order: asc | desc"),
):
    if is_admin(current_user.system_role):
        base = select(Experiment)
        count_stmt = select(func.count()).select_from(Experiment)
    else:
        base = (
            select(Experiment)
            .join(ExperimentCollaborator, ExperimentCollaborator.experiment_id == Experiment.id)
            .where(ExperimentCollaborator.user_id == current_user.id)
        )
        count_stmt = (
            select(func.count())
            .select_from(Experiment)
            .join(ExperimentCollaborator, ExperimentCollaborator.experiment_id == Experiment.id)
            .where(ExperimentCollaborator.user_id == current_user.id)
        )

    if status_filter is not None:
        base = base.where(Experiment.status == status_filter)
        count_stmt = count_stmt.where(Experiment.status == status_filter)
    if q:
        pattern = f"%{q}%"
        base = base.where(Experiment.title.ilike(pattern))
        count_stmt = count_stmt.where(Experiment.title.ilike(pattern))

    if sort_by not in _EXP_SORT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sort_by '{sort_by}'. Valid values: {sorted(_EXP_SORT_FIELDS)}",
        )
    col = _EXP_SORT_FIELDS[sort_by]
    order_clause = desc(col) if order.lower() != "asc" else asc(col)

    total = (await db.execute(count_stmt)).scalar_one()
    items = list(
        (await db.execute(base.order_by(order_clause).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{experiment_id}",
    response_model=ExperimentResponse,
    dependencies=[ViewerDep],
    summary="Get experiment",
    description="Return full experiment details. Requires at least `viewer` experiment role.",
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def get_experiment(experiment_id: uuid.UUID, db: DBDep):
    experiment = await db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return experiment


@router.patch(
    "/{experiment_id}",
    response_model=ExperimentResponse,
    dependencies=[OwnerDep],
    summary="Update experiment",
    description=(
        "Update experiment metadata. Requires `owner` role. All fields are optional.\n\n"
        "Set `status: archived` to mark the experiment as read-only for reporting."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404, **HTTP_422},
)
async def update_experiment(
    experiment_id: uuid.UUID, body: ExperimentUpdateRequest, db: DBDep
):
    experiment = await db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

    if body.title is not None:
        experiment.title = body.title
    if body.description is not None:
        experiment.description = body.description
    if body.config is not None:
        experiment.config = body.config
    if body.status is not None:
        experiment.status = body.status

    await db.commit()
    await db.refresh(experiment)
    return experiment


@router.delete(
    "/{experiment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[OwnerDep],
    summary="Delete experiment",
    description=(
        "Permanently delete an experiment and **all associated data**: "
        "collaborators, datasets, and training runs. Requires `owner` role.\n\n"
        "This action cannot be undone."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def delete_experiment(experiment_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    experiment = await db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    fire_audit(
        AuditAction.experiment_deleted,
        user_id=current_user.id,
        resource_type="experiment",
        resource_id=str(experiment_id),
        detail={"title": experiment.title},
    )
    await db.delete(experiment)
    await db.commit()


# ── Export ────────────────────────────────────────────────────────────────────

@router.get(
    "/{experiment_id}/export",
    dependencies=[ViewerDep],
    summary="Export experiment as JSON",
    description=(
        "Export the full experiment as a single JSON document: metadata, collaborators, "
        "datasets, and all runs with their results.\n\n"
        "Intended for backup, reproducibility archiving, and transfer between instances. "
        "Requires at least `viewer` experiment role."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def export_experiment(experiment_id: uuid.UUID, db: DBDep):
    experiment = await db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

    collaborators_result = await db.execute(
        select(ExperimentCollaborator).where(
            ExperimentCollaborator.experiment_id == experiment_id
        )
    )
    collaborators = collaborators_result.scalars().all()

    datasets_result = await db.execute(
        select(Dataset).where(Dataset.experiment_id == experiment_id)
    )
    datasets = datasets_result.scalars().all()

    runs_result = await db.execute(
        select(Run).where(Run.experiment_id == experiment_id).order_by(Run.created_at)
    )
    runs = runs_result.scalars().all()

    return {
        "export_version": "1",
        "experiment": {
            "id": str(experiment.id),
            "title": experiment.title,
            "description": experiment.description,
            "config": experiment.config,
            "status": experiment.status,
            "created_by": str(experiment.created_by),
            "created_at": _dt(experiment.created_at),
            "updated_at": _dt(experiment.updated_at),
        },
        "collaborators": [
            {
                "user_id": str(c.user_id),
                "role": c.role,
                "invited_by_id": str(c.invited_by_id) if c.invited_by_id else None,
                "created_at": _dt(c.created_at),
            }
            for c in collaborators
        ],
        "datasets": [
            {
                "id": str(d.id),
                "name": d.name,
                "description": d.description,
                "source_id": d.source_id,
                "file_path": d.file_path,
                "meta": d.meta,
                "created_by": str(d.created_by),
                "created_at": _dt(d.created_at),
            }
            for d in datasets
        ],
        "runs": [
            {
                "id": str(r.id),
                "name": r.name,
                "model_type": r.model_type,
                "config": r.config,
                "status": r.status,
                "results": r.results,
                "error_message": r.error_message,
                "created_by": str(r.created_by),
                "created_at": _dt(r.created_at),
                "started_at": _dt(r.started_at),
                "completed_at": _dt(r.completed_at),
            }
            for r in runs
        ],
    }


# ── Duplicate ─────────────────────────────────────────────────────────────────

@router.post(
    "/{experiment_id}/duplicate",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ViewerDep],
    summary="Duplicate experiment",
    description=(
        "Create a new experiment copying the `title`, `description`, and `config` of an existing one. "
        "The caller becomes the `owner` of the new experiment. "
        "Datasets, runs, and collaborators are **not** copied.\n\n"
        "Requires at least `viewer` role on the source experiment."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def duplicate_experiment(
    experiment_id: uuid.UUID, current_user: CurrentUser, db: DBDep
):
    source = await db.get(Experiment, experiment_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

    copy = Experiment(
        title=f"{source.title} (copy)",
        description=source.description,
        config=source.config,
        created_by=current_user.id,
    )
    db.add(copy)
    await db.flush()

    ownership = ExperimentCollaborator(
        experiment_id=copy.id,
        user_id=current_user.id,
        role=CollaboratorRole.owner,
        invited_by_id=None,
    )
    db.add(ownership)
    await db.commit()
    await db.refresh(copy)
    return copy


# ── Collaborators ──────────────────────────────────────────────────────────────

@router.get(
    "/{experiment_id}/collaborators",
    response_model=Page[CollaboratorResponse],
    dependencies=[ViewerDep],
    summary="List collaborators",
    description="Return all collaborators on the experiment. Requires at least `viewer` role.",
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def list_collaborators(
    experiment_id: uuid.UUID,
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Zero-based page offset"),
):
    base_where = ExperimentCollaborator.experiment_id == experiment_id
    total = (
        await db.execute(
            select(func.count()).select_from(ExperimentCollaborator).where(base_where)
        )
    ).scalar_one()
    items = list(
        (
            await db.execute(
                select(ExperimentCollaborator)
                .where(base_where)
                .order_by(ExperimentCollaborator.created_at.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/{experiment_id}/collaborators",
    response_model=CollaboratorResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[OwnerDep],
    summary="Add collaborator",
    description=(
        "Invite a registered user as `editor` or `viewer`. Requires `owner` role.\n\n"
        "The `owner` role cannot be assigned through this endpoint — "
        "use `POST /experiments/{id}/transfer-ownership` instead."
    ),
    responses={
        400: {"description": "Attempted to assign the `owner` role."},
        **HTTP_401,
        **HTTP_403,
        **HTTP_404,
        **HTTP_409,
    },
)
async def add_collaborator(
    experiment_id: uuid.UUID, body: AddCollaboratorRequest, current_user: CurrentUser, db: DBDep
):
    if body.role == CollaboratorRole.owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign owner role. Transfer ownership instead.",
        )

    target_user = await db.get(User, body.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(
        select(ExperimentCollaborator).where(
            ExperimentCollaborator.experiment_id == experiment_id,
            ExperimentCollaborator.user_id == body.user_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a collaborator")

    collab = ExperimentCollaborator(
        experiment_id=experiment_id,
        user_id=body.user_id,
        role=body.role,
        invited_by_id=current_user.id,
    )
    db.add(collab)
    await db.commit()
    await db.refresh(collab)
    return collab


@router.patch(
    "/{experiment_id}/collaborators/{user_id}",
    response_model=CollaboratorResponse,
    dependencies=[OwnerDep],
    summary="Update collaborator role",
    description=(
        "Change a collaborator's role between `editor` and `viewer`. Requires `owner` role.\n\n"
        "**Restrictions:**\n"
        "- Cannot assign or change the `owner` role (use transfer-ownership).\n"
        "- Cannot target the current owner.\n"
        "- Cannot target yourself."
    ),
    responses={
        400: {"description": "Role is `owner`, target is the owner, or target is yourself."},
        **HTTP_401,
        **HTTP_403,
        **HTTP_404,
    },
)
async def update_collaborator(
    experiment_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateCollaboratorRequest,
    current_user: CurrentUser,
    db: DBDep,
):
    if body.role == CollaboratorRole.owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign owner role. Transfer ownership instead.",
        )
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")

    result = await db.execute(
        select(ExperimentCollaborator).where(
            ExperimentCollaborator.experiment_id == experiment_id,
            ExperimentCollaborator.user_id == user_id,
        )
    )
    collab = result.scalar_one_or_none()
    if not collab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaborator not found")
    if collab.role == CollaboratorRole.owner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change the owner's role")

    collab.role = body.role
    await db.commit()
    await db.refresh(collab)
    return collab


@router.delete(
    "/{experiment_id}/collaborators/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[OwnerDep],
    summary="Remove collaborator",
    description=(
        "Remove a collaborator from the experiment. Requires `owner` role.\n\n"
        "Cannot remove the owner or yourself."
    ),
    responses={
        400: {"description": "Target is the owner, or you are trying to remove yourself."},
        **HTTP_401,
        **HTTP_403,
        **HTTP_404,
    },
)
async def remove_collaborator(
    experiment_id: uuid.UUID, user_id: uuid.UUID, current_user: CurrentUser, db: DBDep
):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself")

    result = await db.execute(
        select(ExperimentCollaborator).where(
            ExperimentCollaborator.experiment_id == experiment_id,
            ExperimentCollaborator.user_id == user_id,
        )
    )
    collab = result.scalar_one_or_none()
    if not collab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaborator not found")
    if collab.role == CollaboratorRole.owner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the owner")

    await db.delete(collab)
    await db.commit()


@router.post(
    "/{experiment_id}/transfer-ownership",
    response_model=CollaboratorResponse,
    dependencies=[OwnerDep],
    summary="Transfer experiment ownership",
    description=(
        "Transfer the `owner` role to an existing collaborator. Requires `owner` role.\n\n"
        "- The caller is **demoted to `editor`**.\n"
        "- The target collaborator is **promoted to `owner`**.\n"
        "- The target must already be a collaborator on this experiment."
    ),
    responses={
        400: {"description": "Target is the caller (cannot transfer to yourself)."},
        **HTTP_401,
        **HTTP_403,
        404: {"description": "Target user is not a collaborator on this experiment."},
    },
)
async def transfer_ownership(
    experiment_id: uuid.UUID, body: AddCollaboratorRequest, current_user: CurrentUser, db: DBDep
):
    if body.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already the owner",
        )

    result = await db.execute(
        select(ExperimentCollaborator).where(
            ExperimentCollaborator.experiment_id == experiment_id,
            ExperimentCollaborator.user_id == body.user_id,
        )
    )
    target_collab = result.scalar_one_or_none()
    if not target_collab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user is not a collaborator on this experiment",
        )

    owner_result = await db.execute(
        select(ExperimentCollaborator).where(
            ExperimentCollaborator.experiment_id == experiment_id,
            ExperimentCollaborator.user_id == current_user.id,
        )
    )
    owner_collab = owner_result.scalar_one()
    owner_collab.role = CollaboratorRole.editor
    target_collab.role = CollaboratorRole.owner

    await db.commit()
    await db.refresh(target_collab)
    return target_collab


# ── Datasets ──────────────────────────────────────────────────────────────────

@router.post(
    "/{experiment_id}/datasets",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[EditorDep],
    summary="Register a dataset",
    description=(
        "Register a dataset reference on the experiment. Requires at least `editor` role.\n\n"
        "The API stores **metadata only** — actual data files are managed outside the API. "
        "`source_id` can reference an external catalogue (e.g. an EDI package ID). "
        "`file_path` is the path on the server or a remote URI."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404, **HTTP_422},
)
async def create_dataset(
    experiment_id: uuid.UUID, body: DatasetCreateRequest, current_user: CurrentUser, db: DBDep
):
    dataset = Dataset(
        experiment_id=experiment_id,
        name=body.name,
        description=body.description,
        source_id=body.source_id,
        file_path=body.file_path,
        meta=body.meta,
        created_by=current_user.id,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.get(
    "/{experiment_id}/datasets",
    response_model=Page[DatasetResponse],
    dependencies=[ViewerDep],
    summary="List datasets",
    description="Paginated list of datasets registered to the experiment. Requires at least `viewer` role.",
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def list_datasets(
    experiment_id: uuid.UUID,
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Zero-based page offset"),
):
    count_stmt = (
        select(func.count())
        .select_from(Dataset)
        .where(Dataset.experiment_id == experiment_id)
    )
    total = (await db.execute(count_stmt)).scalar_one()
    items = list(
        (
            await db.execute(
                select(Dataset)
                .where(Dataset.experiment_id == experiment_id)
                .order_by(Dataset.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(items=items, total=total, limit=limit, offset=offset)
