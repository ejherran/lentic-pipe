"""FastAPI application scaffold for lentic-pipe."""

from __future__ import annotations

from fastapi import FastAPI

from src.api import API_VERSION
from src.api.routers import datasets, runs, system

_TAGS = [
    {
        "name": "System",
        "description": "Health, version, and API contract catalog endpoints.",
    },
    {
        "name": "Datasets",
        "description": "External dataset validation and workflow eligibility endpoints.",
    },
    {
        "name": "Runs",
        "description": "Synchronous dry-run planning for registered dataset workflows.",
    },
]


def create_app() -> FastAPI:
    """Create the FastAPI application."""

    app = FastAPI(
        title="Lentic Pipe API",
        version=API_VERSION,
        description=(
            "Reproducible workflow API for external lentic water-body datasets. "
            "The API validates submitted data, reports workflow eligibility, and "
            "runs scientific pipelines only when documented preconditions are met."
        ),
        openapi_tags=_TAGS,
    )
    app.include_router(datasets.router)
    app.include_router(runs.router)
    app.include_router(system.router)
    return app


app = create_app()
