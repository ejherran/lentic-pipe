"""System endpoint schemas."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health response."""

    status: str
    components: dict[str, str]


class VersionResponse(BaseModel):
    """Version and workflow registry response."""

    api_version: str
    project: str
    stage: str
    supported_horizons: list[str]
    documents: dict[str, str]
    workflows: list[dict[str, object]]
