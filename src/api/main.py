import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import select, text

from src.api.config import settings
from src.api.core.request_id import RequestIDMiddleware
from src.api.core.security import hash_password
from src.api.core.timeout import TimeoutMiddleware
from src.api.database import AsyncSessionLocal
from src.api.models.user import SystemRole, User
from src.api.core.logging import setup_logging
from src.api.routers import (
    admin,
    api_keys,
    auth,
    datasets,
    email_verification,
    experiments,
    predictions,
    runs,
    science,
    simulations,
    system,
    users,
)
from src.api.tasks.broker import broker
from src.api.tasks.maintenance import purge_expired_email_codes, purge_expired_tokens_now, purge_old_audit_log, refresh_queue_metrics

setup_logging(level=settings.LOG_LEVEL)

_logger = logging.getLogger(__name__)


async def _token_cleanup_loop() -> None:
    """Purge expired refresh tokens and audit log every 6 hours."""
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            deleted = await purge_expired_tokens_now()
            _logger.info("purge_expired_tokens", extra={"deleted": deleted})
        except Exception:
            _logger.exception("purge_expired_tokens failed")
        try:
            await purge_old_audit_log()
        except Exception:
            _logger.exception("purge_old_audit_log failed")
        try:
            await purge_expired_email_codes()
        except Exception:
            _logger.exception("purge_expired_email_codes failed")


async def _metrics_loop() -> None:
    """Refresh Prometheus queue-depth gauges every 5 minutes."""
    while True:
        await asyncio.sleep(5 * 60)
        try:
            await refresh_queue_metrics()
        except Exception:
            _logger.exception("refresh_queue_metrics failed")


async def _wait_for_db() -> None:
    for attempt in range(settings.STARTUP_MAX_RETRIES):
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
            _logger.info("db_ready")
            return
        except Exception:
            if attempt == settings.STARTUP_MAX_RETRIES - 1:
                _logger.error("db_unavailable_giving_up")
                raise
            delay = settings.STARTUP_RETRY_DELAY_SECONDS * (2**attempt)
            _logger.warning("db_not_ready", extra={"attempt": attempt + 1, "retry_in": delay})
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _wait_for_db()
    await broker.startup()
    await _create_first_admin()
    try:
        await refresh_queue_metrics()
    except Exception:
        _logger.warning("initial refresh_queue_metrics failed — gauges will start at 0")
    cleanup_task = asyncio.create_task(_token_cleanup_loop())
    metrics_task = asyncio.create_task(_metrics_loop())
    yield
    cleanup_task.cancel()
    metrics_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await cleanup_task
    with contextlib.suppress(asyncio.CancelledError):
        await metrics_task
    await broker.shutdown()


async def _create_first_admin() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                (User.username == settings.FIRST_ADMIN_USERNAME)
                | (User.email == settings.FIRST_ADMIN_EMAIL)
            )
        )
        if result.scalar_one_or_none():
            return

        admin = User(
            email=settings.FIRST_ADMIN_EMAIL,
            username=settings.FIRST_ADMIN_USERNAME,
            hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
            full_name="System Admin",
            system_role=SystemRole.admin,
        )
        db.add(admin)
        await db.commit()


_TAGS = [
    {
        "name": "System",
        "description": "Health check, version, and Prometheus metrics. No authentication required.",
    },
    {
        "name": "Auth",
        "description": (
            "Registration, login, token refresh, and session management. "
            "Access tokens expire after **30 minutes**. Refresh tokens are **single-use** "
            "and expire after **7 days** — each `/auth/refresh` call issues a new pair and "
            "invalidates the old refresh token."
        ),
    },
    {
        "name": "Users",
        "description": "User account management. All endpoints require `system_role: admin`.",
    },
    {
        "name": "Experiments",
        "description": (
            "Primary organizational unit grouping datasets, training runs, and collaborators. "
            "The creator is automatically assigned the `owner` experiment role.\n\n"
            "**Experiment roles:** `owner` > `editor` > `viewer`."
        ),
    },
    {
        "name": "Datasets",
        "description": (
            "Scientific dataset validation and local reproducibility artifacts. "
            "These endpoints preserve the existing dataset contract while the workflows are "
            "being attached to experiment-scoped jobs."
        ),
    },
    {
        "name": "Runs",
        "description": (
            "Async model training jobs. A run is created with `202 Accepted` and transitions "
            "through `pending → running → completed | failed` as the Taskiq worker processes it.\n\n"
            "PIPE models require `horizon_days` and `seed` in the `config` field. "
            "Baseline and MIFAL models need no config."
        ),
    },
    {
        "name": "Predictions",
        "description": (
            "Synchronous single-point inference. Results are returned inline in the `201` response "
            "and stored persistently for later retrieval.\n\n"
            "> ML inference is currently a **stub** — output fields will be `null` until model "
            "implementations are connected."
        ),
    },
    {
        "name": "Simulations",
        "description": (
            "Async counterfactual trajectory rollouts. Submit a scenario and a site state; "
            "the worker generates probabilistic trajectories comparing baseline vs. intervention.\n\n"
            "> Results are simulated counterfactuals under the learned model — **not** causal "
            "predictions of real-world interventions.\n\n"
            "> Simulation execution is currently a **stub**."
        ),
    },
    {
        "name": "Scientific Workflows",
        "description": (
            "Deterministic dataset planning, safe local execution, artifact previews, current "
            "state alerts, and minimal counterfactual recomputation from the scientific layer."
        ),
    },
]

app = FastAPI(
    title="Lentic Pipe API",
    description=(
        "Reproducible computational architecture for **algal bloom simulation**, "
        "trophic state prediction, and counterfactual planning in lentic water bodies "
        "(lakes, lagoons, and reservoirs).\n\n"
        "## Authentication\n\n"
        "All endpoints except `/health`, `/version`, and `/metrics` require a Bearer token:\n\n"
        "```\nAuthorization: Bearer <access_token>\n```\n\n"
        "Obtain a token pair via `POST /auth/login`. Rotate it before expiry with `POST /auth/refresh`.\n\n"
        "## Roles\n\n"
        "**System roles** (per account): `admin` > `researcher` > `viewer`.\n\n"
        "**Experiment roles** (per experiment): `owner` > `editor` > `viewer`.\n\n"
        "## Rate limits\n\n"
        "| Endpoint | Limit |\n"
        "|---|---|\n"
        "| `POST /auth/register` | 10 / hour / IP |\n"
        "| `POST /auth/login` | 20 / min; 100 / hour / IP |\n"
        "| All other endpoints | 200 / min / IP |\n\n"
        "Exceeded limits return `429 Too Many Requests`.\n\n"
        "## Pagination\n\n"
        "All list endpoints return `{ items, total, limit, offset }`. "
        "Use `?limit=` (max 200) and `?offset=` to page through results."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    openapi_tags=_TAGS,
    contact={"name": "Javier Herran", "email": "ejherran.c@gmail.com"},
    license_info={"name": "Research software — doctoral thesis project"},
)

app.add_middleware(TimeoutMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)

_cors_origins = (
    [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    if settings.CORS_ORIGINS
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(email_verification.router)
app.include_router(users.router)
app.include_router(datasets.router)
app.include_router(experiments.router)
app.include_router(science.router)
app.include_router(runs.router)
app.include_router(predictions.router)
app.include_router(simulations.router)


def create_app() -> FastAPI:
    """Return the configured application instance.

    The prototype architecture owns application construction; this function keeps
    the public test and local-run contract used by the scientific API layer.
    """

    return app
