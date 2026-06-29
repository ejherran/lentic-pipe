"""Local file-backed run planning records."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from src.api.config import api_workspace
from src.api.schemas.run import RunExecutionResponse, RunPlanResponse

_PLAN_ID_PATTERN = re.compile(r"^plan_[a-f0-9]{16}$")


class RunPlanNotFoundError(Exception):
    """Raised when a run plan registry entry does not exist."""


class RunExecutionNotFoundError(Exception):
    """Raised when a run execution registry entry does not exist."""


def save_run_plan(
    plan: RunPlanResponse,
    *,
    workspace: Path | None = None,
) -> RunPlanResponse:
    """Persist a dry-run plan and return the stored representation."""

    root = workspace or api_workspace()
    plan_dir = _plan_dir(plan.plan_id, root)
    plan_path = plan_dir / "plan.json"
    if plan_path.exists():
        return read_run_plan(plan.plan_id, workspace=root)

    plan_dir.mkdir(parents=True, exist_ok=True)
    _write_json(plan_path, plan.model_dump(mode="json", exclude_none=True))
    return read_run_plan(plan.plan_id, workspace=root)


def read_run_plan(
    plan_id: str,
    *,
    workspace: Path | None = None,
) -> RunPlanResponse:
    """Read a persisted dry-run plan."""

    if not _PLAN_ID_PATTERN.fullmatch(plan_id):
        raise RunPlanNotFoundError(plan_id)
    root = workspace or api_workspace()
    plan_path = _plan_dir(plan_id, root) / "plan.json"
    if not plan_path.exists():
        raise RunPlanNotFoundError(plan_id)
    return RunPlanResponse.model_validate(json.loads(plan_path.read_text(encoding="utf-8")))


def save_run_execution(
    execution: RunExecutionResponse,
    *,
    workspace: Path | None = None,
) -> RunExecutionResponse:
    """Persist a synchronous execution response and return the stored representation."""

    root = workspace or api_workspace()
    execution_path = _plan_dir(execution.plan_id, root) / "execution.json"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(execution_path, execution.model_dump(mode="json", exclude_none=True))
    return read_run_execution(execution.plan_id, workspace=root)


def read_run_execution(
    plan_id: str,
    *,
    workspace: Path | None = None,
) -> RunExecutionResponse:
    """Read a persisted synchronous execution response."""

    if not _PLAN_ID_PATTERN.fullmatch(plan_id):
        raise RunExecutionNotFoundError(plan_id)
    root = workspace or api_workspace()
    execution_path = _plan_dir(plan_id, root) / "execution.json"
    if not execution_path.exists():
        raise RunExecutionNotFoundError(plan_id)
    return RunExecutionResponse.model_validate(json.loads(execution_path.read_text(encoding="utf-8")))


def run_plan_dir(plan_id: str, *, workspace: Path | None = None) -> Path:
    """Return the local directory for a persisted plan or execution."""

    root = workspace or api_workspace()
    return _plan_dir(plan_id, root)


def _plan_dir(plan_id: str, workspace: Path) -> Path:
    return workspace / "runs" / plan_id


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
