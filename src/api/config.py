"""Static API configuration for the initial public scaffold."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import TypedDict

from src.api import API_VERSION

DEFAULT_API_WORKSPACE = Path("outputs/api")


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
        status="contract",
        description="Validate external dataset schema, units, dates, ranges, and coverage.",
        notes=("First workflow to implement after the API scaffold.",),
    ),
    PipelineInfo(
        name="canonical_observations",
        status="planned",
        description="Convert supported external observations into canonical long observations.",
        notes=("Requires the dataset validation contract.",),
    ),
    PipelineInfo(
        name="monthly_panel",
        status="planned",
        description="Aggregate canonical observations into source/site/month panels.",
        notes=("Reports workflow eligibility by variable and temporal coverage.",),
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
        "stage": "contract_scaffold",
        "supported_horizons": ["h1", "h2", "h3"],
        "dataset_contract": "docs/API_DATASET_CONTRACT.md",
        "error_contract": "docs/API_ERRORS.md",
        "protocol": "docs/API_PROTOCOL.md",
    }


def api_workspace() -> Path:
    """Return the local API workspace for generated dataset artifacts."""

    return Path(os.environ.get("LENTIC_API_WORKSPACE", DEFAULT_API_WORKSPACE.as_posix()))
