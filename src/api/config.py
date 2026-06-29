"""API settings and scientific workflow registry."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import TypedDict

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.api import API_VERSION

DEFAULT_API_WORKSPACE = Path("outputs/api")
_INSECURE_DEFAULT_KEY = "insecure-dev-key-change-in-production"
_INSECURE_DEFAULT_ADMIN_PASSWORD = "changeme"


class Settings(BaseSettings):
    """Runtime settings for the production API shell from the prototype."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    APP_VERSION: str = API_VERSION
    SECRET_KEY: str = _INSECURE_DEFAULT_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    REDIS_URL: str = "redis://localhost:6379"

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_TIMEOUT: int = 30

    STARTUP_MAX_RETRIES: int = 5
    STARTUP_RETRY_DELAY_SECONDS: float = 1.0
    REQUEST_TIMEOUT_SECONDS: int = 60
    STRICT_READINESS_CHECKS: bool = False
    AUDIT_LOG_RETAIN_DAYS: int = 90

    FIRST_ADMIN_EMAIL: str = "admin@example.com"
    FIRST_ADMIN_USERNAME: str = "admin"
    FIRST_ADMIN_PASSWORD: str = "changeme"

    LOG_LEVEL: str = "INFO"
    REGISTRATION_ENABLED: bool = True
    CORS_ORIGINS: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@lentic-api.local"
    SMTP_USE_TLS: bool = True

    TRUSTED_PROXIES: str = ""

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        if self.APP_ENV != "production":
            return self
        if self.SECRET_KEY == _INSECURE_DEFAULT_KEY:
            raise ValueError(
                "SECRET_KEY must be changed from the default value before running in production."
            )
        if self.FIRST_ADMIN_PASSWORD == _INSECURE_DEFAULT_ADMIN_PASSWORD:
            raise ValueError(
                "FIRST_ADMIN_PASSWORD must be changed from the default value before running in production."
            )
        return self


@dataclass(frozen=True)
class PipelineInfo:
    """Machine-readable summary for a scientific workflow exposed by the API."""

    name: str
    status: str
    description: str
    notes: tuple[str, ...]


class ApiMetadata(TypedDict):
    """Stable metadata exposed by the system API."""

    api_version: str
    project: str
    stage: str
    supported_horizons: list[str]
    dataset_contract: str
    error_contract: str
    protocol: str


PIPELINE_REGISTRY: tuple[PipelineInfo, ...] = (
    PipelineInfo(
        name="dataset_validation",
        status="available",
        description="Validate external dataset schema, units, dates, ranges, and coverage.",
        notes=("Side-effect-free validation is available through POST /datasets/validate.",),
    ),
    PipelineInfo(
        name="canonical_observations",
        status="local_executor",
        description="Convert supported external observations into canonical long observations.",
        notes=("Available through the safe synchronous local executor.",),
    ),
    PipelineInfo(
        name="monthly_panel",
        status="local_executor",
        description="Aggregate canonical observations into source/site/month panels.",
        notes=("Available through the safe synchronous local executor.",),
    ),
    PipelineInfo(
        name="fuzzy_state",
        status="local_executor",
        description="Compute deterministic expert fuzzy ecological state scores from an eligible monthly panel.",
        notes=(
            "Uses the reviewed src.fuzzy.expert state construction path.",
            "This is expert fuzzy scoring, not adaptive ANFIS retraining.",
        ),
    ),
    PipelineInfo(
        name="current_state_counterfactual",
        status="local_simulation",
        description="Simulate declared current-state input changes over an executed fuzzy state surface.",
        notes=(
            "This is deterministic expert fuzzy recomputation, not causal field evidence.",
            "Requires a completed fuzzy_state run.",
        ),
    ),
    PipelineInfo(
        name="pipe_grud",
        status="planned",
        description="Run PIPE-GRU-D compatible scoring, rollout, and alert workflows.",
        notes=("Requires a compatible temporal panel and model artifacts.",),
    ),
    PipelineInfo(
        name="pipe_neural_ode",
        status="planned",
        description="Run Neural ODE temporal workflows on compatible state histories.",
        notes=("Advanced workflow; eligibility must be checked explicitly.",),
    ),
    PipelineInfo(
        name="mifal_ed_t2",
        status="planned",
        description="Run the MIFAL-ED/T2 eco-fuzzy comparator on observable-minimal inputs.",
        notes=("Comparator workflow; does not emit irc_alert.",),
    ),
    PipelineInfo(
        name="counterfactual_planning",
        status="planned",
        description="Run simulated counterfactual planning on eligible temporal outputs.",
        notes=("Model-simulated comparison only; not causal field intervention evidence.",),
    ),
)


def api_metadata() -> ApiMetadata:
    """Return stable metadata for the initial API scaffold."""

    return {
        "api_version": API_VERSION,
        "project": "lentic-pipe",
        "stage": "local_workflow_api",
        "supported_horizons": ["h1", "h2", "h3"],
        "dataset_contract": "docs/API_DATASET_CONTRACT.md",
        "error_contract": "docs/API_ERRORS.md",
        "protocol": "docs/API_PROTOCOL.md",
    }


def api_workspace() -> Path:
    """Return the local API workspace for generated dataset artifacts."""

    return Path(os.environ.get("LENTIC_API_WORKSPACE", DEFAULT_API_WORKSPACE.as_posix()))


settings = Settings()
