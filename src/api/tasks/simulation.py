"""Simulation task for counterfactual and rollout jobs."""

import uuid
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult

from src.api.core.email import send_email
from src.api.database import AsyncSessionLocal
from src.api.models.simulation import Simulation, SimulationStatus
from src.api.models.user import User
from src.api.schemas.simulation import CurrentStateCounterfactualRequest
from src.api.services.run_simulations import simulate_current_state_counterfactual
from src.api.tasks.broker import broker


async def _simulate(
    site_id: str,
    year_month: str,
    horizon_days: int,
    n_trajectories: int,
    scenario: dict,
) -> dict[str, Any]:
    """Run a wired simulation scenario or return an explicit placeholder."""

    if scenario.get("type") == "current_state_counterfactual":
        return _simulate_current_state_counterfactual(scenario)
    return {
        "status": "stub",
        "note": (
            "Temporal rollout simulation is not wired yet. Use scenario "
            "type='current_state_counterfactual' for the deterministic fuzzy-state "
            "simulation currently connected to the job system."
        ),
        "scenario_type": scenario.get("type", "unknown"),
        "baseline": {
            "irc_mean": None,
            "irc_p95": None,
            "bloom_probability": None,
            "risk_interval": [None, None],
        },
        "scenario_result": {
            "irc_mean": None,
            "irc_p95": None,
            "bloom_probability": None,
            "risk_interval": [None, None],
            "risk_reduction": None,
        },
        "trajectories_shape": [n_trajectories, horizon_days // 30, 9],
    }


def _simulate_current_state_counterfactual(scenario: dict) -> dict[str, Any]:
    request = CurrentStateCounterfactualRequest(
        scenario_name=scenario.get("scenario_name"),
        interventions=scenario["interventions"],
        limit=scenario.get("limit", 100),
        only_changed_alerts=scenario.get("only_changed_alerts", False),
    )
    response = simulate_current_state_counterfactual(str(scenario["plan_id"]), request)
    return {
        "status": "completed",
        "adapter": "current_state_counterfactual_v0",
        "result": response.model_dump(mode="json"),
    }


@broker.task(timeout=600, max_retries=3)
async def run_simulation_task(simulation_id: str, request_id: str = "") -> None:
    async with AsyncSessionLocal() as db:
        cursor = cast(
            CursorResult[Any],
            await db.execute(
                update(Simulation)
                .where(
                    Simulation.id == uuid.UUID(simulation_id),
                    Simulation.status == SimulationStatus.pending,
                )
                .values(status=SimulationStatus.running)
            ),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return

        sim: Simulation | None = await db.get(Simulation, uuid.UUID(simulation_id))
        if not sim:
            return

        try:
            result = await _simulate(
                sim.site_id,
                sim.year_month,
                sim.horizon_days,
                sim.n_trajectories,
                sim.scenario,
            )
            # Re-read from DB — user may have cancelled while the job was running.
            await db.refresh(sim)
            if sim.status == SimulationStatus.cancelled:
                return
            sim.status = SimulationStatus.completed
            sim.result = result
            sim.completed_at = datetime.now(timezone.utc)
        except Exception as exc:
            await db.refresh(sim)
            if sim.status == SimulationStatus.cancelled:
                return
            sim.status = SimulationStatus.failed
            sim.error_message = str(exc)
            sim.completed_at = datetime.now(timezone.utc)

        final_status = sim.status
        error_message = sim.error_message
        site_id = sim.site_id
        user_id = sim.user_id
        await db.commit()

    async with AsyncSessionLocal() as db:
        user: User | None = await db.get(User, user_id)
        if not user or not user.email_verified:
            return
        if final_status == SimulationStatus.completed and user.notify_on_simulation_completed:
            await send_email(
                to=user.email,
                subject=f"Simulation for site '{site_id}' completed",
                body_text=(
                    f"Your simulation for site '{site_id}' has completed successfully.\n\n"
                    "You can retrieve the results via the Lentic API."
                ),
                body_html=(
                    f"<p>Your simulation for site <strong>{site_id}</strong> has completed successfully.</p>"
                    "<p>You can retrieve the results via the Lentic API.</p>"
                ),
            )
        elif final_status == SimulationStatus.failed and user.notify_on_simulation_failed:
            await send_email(
                to=user.email,
                subject=f"Simulation for site '{site_id}' failed",
                body_text=(
                    f"Your simulation for site '{site_id}' has failed.\n\n"
                    f"Error: {error_message or 'Unknown error'}\n\n"
                    "Please check your simulation parameters and try again."
                ),
                body_html=(
                    f"<p>Your simulation for site <strong>{site_id}</strong> has failed.</p>"
                    f"<p>Error: {error_message or 'Unknown error'}</p>"
                    "<p>Please check your simulation parameters and try again.</p>"
                ),
            )
