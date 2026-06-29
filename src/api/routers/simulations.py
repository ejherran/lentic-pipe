import uuid
from datetime import datetime, timezone
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select, update
from sqlalchemy.engine import CursorResult

from src.api.core.dependencies import CurrentUser, DBDep
from src.api.core.openapi import HTTP_401, HTTP_403, HTTP_404, HTTP_422
from src.api.core.permissions import is_admin
from src.api.core.request_id import get_request_id
from src.api.models.simulation import Simulation, SimulationStatus
from src.api.schemas.common import CancelledResponse, Page
from src.api.schemas.simulation import SimulationCreateRequest, SimulationResponse
from src.api.tasks.simulation import run_simulation_task

router = APIRouter(prefix="/simulations", tags=["Simulations"])

_SIM_SORT_FIELDS: dict[str, Any] = {
    "created_at": Simulation.created_at,
    "site_id": Simulation.site_id,
    "status": Simulation.status,
    "completed_at": Simulation.completed_at,
}


@router.post(
    "",
    response_model=SimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Launch a counterfactual simulation",
    description=(
        "Queue an async counterfactual simulation. Returns `202 Accepted` with `status: pending`. "
        "The Taskiq worker processes the job and produces trajectory rollouts.\n\n"
        "> **Interpretation:** Results are simulated counterfactuals under the learned model — "
        "they are **not** causal predictions of real-world interventions.\n\n"
        "> **Note:** Simulation execution is currently a stub. `result` will be `null` until "
        "rollout implementations are connected.\n\n"
        "**Supported scenario types:**\n\n"
        "| Type | Key parameters |\n"
        "|---|---|\n"
        "| `no_action` | *(none)* — baseline trajectory |\n"
        "| `nutrient_reduction` | `TP_factor` [0–1], `TN_factor` [0–1] |\n"
        "| `aeration` | `intensity` [0–1] |\n"
        "| `combined` | `TP_factor`, `TN_factor`, `temperature_delta` [±5°C], `pH_delta` [±1] |\n\n"
        "**Valid `horizon_days` values:** `30`, `60`, `90`."
    ),
    responses={
        422: {
            "description": (
                "`year_month` not in YYYY-MM format, `horizon_days` not in {30, 60, 90}, "
                "or `n_trajectories` out of range [1, 200]."
            )
        },
        **HTTP_401,
    },
)
async def create_simulation(
    body: SimulationCreateRequest, current_user: CurrentUser, db: DBDep
):
    simulation = Simulation(
        user_id=current_user.id,
        experiment_id=body.experiment_id,
        site_id=body.site_id,
        year_month=body.year_month,
        horizon_days=body.horizon_days,
        n_trajectories=body.n_trajectories,
        scenario=body.scenario.model_dump(),
    )
    db.add(simulation)
    await db.flush()

    task = await run_simulation_task.kiq(simulation_id=str(simulation.id), request_id=get_request_id())
    simulation.task_id = task.task_id

    await db.commit()
    await db.refresh(simulation)
    return simulation


@router.get(
    "",
    response_model=Page[SimulationResponse],
    summary="List simulations",
    description=(
        "Paginated list of simulations, ordered by `created_at` descending.\n\n"
        "- Regular users see only their own simulations.\n"
        "- Admins see all simulations.\n\n"
        "**Filters:** `?site_id=`, `?status=pending|running|completed|failed`."
    ),
    responses={**HTTP_401},
)
async def list_simulations(
    current_user: CurrentUser,
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Zero-based page offset"),
    site_id: str | None = Query(None, description="Filter by exact site ID"),
    status_filter: SimulationStatus | None = Query(None, alias="status", description="Filter by simulation status"),
    sort_by: Literal["created_at", "site_id", "status", "completed_at"] = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="Sort order: asc | desc"),
):
    base = select(Simulation)
    count_base = select(func.count()).select_from(Simulation)

    if not is_admin(current_user.system_role):
        base = base.where(Simulation.user_id == current_user.id)
        count_base = count_base.where(Simulation.user_id == current_user.id)
    if site_id:
        base = base.where(Simulation.site_id == site_id)
        count_base = count_base.where(Simulation.site_id == site_id)
    if status_filter:
        base = base.where(Simulation.status == status_filter)
        count_base = count_base.where(Simulation.status == status_filter)

    col = _SIM_SORT_FIELDS[sort_by]
    order_clause = desc(col) if order.lower() != "asc" else asc(col)

    total = (await db.execute(count_base)).scalar_one()
    items = list(
        (await db.execute(base.order_by(order_clause).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/cancel-all",
    response_model=CancelledResponse,
    summary="Cancel all active simulations",
    description=(
        "Cancel every simulation that is still `pending` or `running`. "
        "Regular users cancel only their own; admins cancel all. "
        "Returns the count of cancelled simulations."
    ),
    responses={**HTTP_401},
)
async def cancel_all_simulations(current_user: CurrentUser, db: DBDep):
    now = datetime.now(timezone.utc)
    stmt = (
        update(Simulation)
        .where(Simulation.status.in_([SimulationStatus.pending, SimulationStatus.running]))
        .values(status=SimulationStatus.cancelled, completed_at=now)
    )
    if not is_admin(current_user.system_role):
        stmt = stmt.where(Simulation.user_id == current_user.id)
    cursor = cast(CursorResult[Any], await db.execute(stmt))
    await db.commit()
    return CancelledResponse(cancelled=cursor.rowcount)


@router.get(
    "/{simulation_id}",
    response_model=SimulationResponse,
    summary="Get simulation",
    description=(
        "Retrieve a simulation and its current status and results. Only the owner or an admin can access.\n\n"
        "`result` is `null` until the job completes. "
        "`error_message` is populated when `status` is `failed`."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def get_simulation(simulation_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    simulation = await db.get(Simulation, simulation_id)
    if not simulation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    if not is_admin(current_user.system_role) and simulation.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return simulation


@router.post(
    "/{simulation_id}/cancel",
    response_model=SimulationResponse,
    summary="Cancel a simulation",
    description=(
        "Cancel a simulation that is still `pending` or `running`. "
        "The status transitions to `cancelled` immediately in the database.\n\n"
        "Only the owner or an admin can cancel a simulation."
    ),
    responses={
        400: {"description": "Simulation is already completed, failed, or cancelled."},
        **HTTP_401,
        **HTTP_403,
        **HTTP_404,
    },
)
async def cancel_simulation(simulation_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    simulation = await db.get(Simulation, simulation_id)
    if not simulation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    if not is_admin(current_user.system_role) and simulation.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if simulation.status not in (SimulationStatus.pending, SimulationStatus.running):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel a simulation with status '{simulation.status}'",
        )
    simulation.status = SimulationStatus.cancelled
    simulation.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(simulation)
    return simulation
