"""Authenticated workspace catalog over experiment-scoped API metadata."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.permissions import is_admin
from src.api.models.experiment import (
    Dataset,
    Experiment,
    ExperimentCollaborator,
    ExperimentStatus,
)
from src.api.models.run import Run, RunStatus
from src.api.models.user import User
from src.api.schemas.workspace import (
    WorkspaceCatalogResponse,
    WorkspaceCatalogSummary,
    WorkspaceDatasetSummary,
    WorkspaceExperimentCatalogEntry,
    WorkspaceRunOutputSummary,
    WorkspaceRunSummary,
)

WorkspaceSortField = Literal["created_at", "updated_at", "title", "status"]

_SORT_FIELDS: dict[WorkspaceSortField, Any] = {
    "created_at": Experiment.created_at,
    "updated_at": Experiment.updated_at,
    "title": Experiment.title,
    "status": Experiment.status,
}
_PREDICTION_ARTIFACTS = frozenset(
    {
        "fuzzy_state_scores.csv",
        "pipe_grud_reference_rollouts.csv",
        "pipe_neural_ode_reference_rollouts.csv",
        "mifal_scores.csv",
    }
)
_ALERT_ARTIFACTS = frozenset(
    {
        "fuzzy_state_scores.csv",
        "pipe_grud_reference_alerts.csv",
        "pipe_neural_ode_reference_alerts.csv",
        "mifal_alerts.csv",
    }
)


async def get_workspace_catalog(
    db: AsyncSession,
    current_user: User,
    *,
    limit: int,
    offset: int,
    status_filter: ExperimentStatus | None = None,
    q: str | None = None,
    sort_by: WorkspaceSortField = "updated_at",
    order: Literal["asc", "desc"] = "desc",
) -> WorkspaceCatalogResponse:
    """Return a paginated, metadata-only catalog for experiments visible to a user."""

    base = _visible_experiment_select(current_user)
    if status_filter is not None:
        base = base.where(Experiment.status == status_filter)
    if q:
        base = base.where(Experiment.title.ilike(f"%{q}%"))

    total = (
        await db.execute(select(func.count()).select_from(base.order_by(None).subquery()))
    ).scalar_one()

    order_clause = asc(_SORT_FIELDS[sort_by]) if order == "asc" else desc(_SORT_FIELDS[sort_by])
    experiments = list(
        (await db.execute(base.order_by(order_clause).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    experiment_ids = [experiment.id for experiment in experiments]
    if not experiment_ids:
        return WorkspaceCatalogResponse(
            items=[],
            total=total,
            limit=limit,
            offset=offset,
            summary=WorkspaceCatalogSummary(
                visible_experiments=total,
                page_experiments=0,
                page_datasets=0,
                page_runs=0,
                page_scientific_runs=0,
                page_run_status_counts=_empty_run_status_counts(),
                page_output_view_counts=_empty_output_view_counts(),
            ),
        )

    datasets_by_experiment = await _datasets_by_experiment(db, experiment_ids)
    runs_by_experiment = await _runs_by_experiment(db, experiment_ids)
    roles_by_experiment = await _roles_by_experiment(db, current_user, experiment_ids)

    items = [
        build_workspace_catalog_entry(
            experiment,
            role=roles_by_experiment.get(experiment.id),
            datasets=datasets_by_experiment.get(experiment.id, []),
            runs=runs_by_experiment.get(experiment.id, []),
        )
        for experiment in experiments
    ]

    return WorkspaceCatalogResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        summary=build_workspace_catalog_summary(total, items),
    )


def build_workspace_catalog_entry(
    experiment: Experiment,
    *,
    role: str | None,
    datasets: Sequence[Dataset],
    runs: Sequence[Run],
) -> WorkspaceExperimentCatalogEntry:
    """Build one catalog entry from already-loaded SQL metadata rows."""

    sorted_datasets = sorted(datasets, key=lambda item: item.created_at, reverse=True)
    sorted_runs = sorted(runs, key=lambda item: item.created_at, reverse=True)
    run_summaries = [_run_summary(run) for run in sorted_runs]
    scientific_run_summaries = [
        summary for summary in run_summaries if summary.outputs.plan_id is not None
    ]
    views = sorted(
        view
        for view, count in _output_view_counter(run_summaries).items()
        if count > 0
    )

    return WorkspaceExperimentCatalogEntry(
        id=experiment.id,
        title=experiment.title,
        description=experiment.description,
        status=experiment.status,
        role=role,
        created_by=experiment.created_by,
        created_at=experiment.created_at,
        updated_at=experiment.updated_at,
        dataset_count=len(datasets),
        run_count=len(runs),
        run_status_counts=_run_status_counter(runs),
        latest_dataset=_dataset_summary(sorted_datasets[0]) if sorted_datasets else None,
        latest_run=run_summaries[0] if run_summaries else None,
        latest_scientific_run=scientific_run_summaries[0] if scientific_run_summaries else None,
        available_views=views,
    )


def build_workspace_catalog_summary(
    visible_experiments: int,
    items: Sequence[WorkspaceExperimentCatalogEntry],
) -> WorkspaceCatalogSummary:
    """Build page-level summary counters for a catalog response."""

    run_status_counts: Counter[str] = Counter()
    output_view_counts: Counter[str] = Counter()
    page_scientific_runs = 0
    for item in items:
        run_status_counts.update(item.run_status_counts)
        for view in item.available_views:
            output_view_counts[view] += 1
        if item.latest_scientific_run is not None:
            page_scientific_runs += 1

    return WorkspaceCatalogSummary(
        visible_experiments=visible_experiments,
        page_experiments=len(items),
        page_datasets=sum(item.dataset_count for item in items),
        page_runs=sum(item.run_count for item in items),
        page_scientific_runs=page_scientific_runs,
        page_run_status_counts=_complete_run_status_counts(run_status_counts),
        page_output_view_counts=_complete_output_view_counts(output_view_counts),
    )


def _visible_experiment_select(current_user: User):
    if is_admin(current_user.system_role):
        return select(Experiment)
    return (
        select(Experiment)
        .join(ExperimentCollaborator, ExperimentCollaborator.experiment_id == Experiment.id)
        .where(ExperimentCollaborator.user_id == current_user.id)
    )


async def _datasets_by_experiment(
    db: AsyncSession,
    experiment_ids: Sequence[Any],
) -> dict[Any, list[Dataset]]:
    rows = list(
        (
            await db.execute(
                select(Dataset)
                .where(Dataset.experiment_id.in_(experiment_ids))
                .order_by(Dataset.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    grouped: dict[Any, list[Dataset]] = defaultdict(list)
    for row in rows:
        grouped[row.experiment_id].append(row)
    return grouped


async def _runs_by_experiment(
    db: AsyncSession,
    experiment_ids: Sequence[Any],
) -> dict[Any, list[Run]]:
    rows = list(
        (
            await db.execute(
                select(Run)
                .where(Run.experiment_id.in_(experiment_ids))
                .order_by(Run.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    grouped: dict[Any, list[Run]] = defaultdict(list)
    for row in rows:
        grouped[row.experiment_id].append(row)
    return grouped


async def _roles_by_experiment(
    db: AsyncSession,
    current_user: User,
    experiment_ids: Sequence[Any],
) -> dict[Any, str]:
    if is_admin(current_user.system_role):
        return {experiment_id: "admin" for experiment_id in experiment_ids}
    rows = list(
        (
            await db.execute(
                select(ExperimentCollaborator)
                .where(ExperimentCollaborator.experiment_id.in_(experiment_ids))
                .where(ExperimentCollaborator.user_id == current_user.id)
            )
        )
        .scalars()
        .all()
    )
    return {row.experiment_id: row.role.value for row in rows}


def _dataset_summary(dataset: Dataset) -> WorkspaceDatasetSummary:
    meta = _mapping(dataset.meta)
    return WorkspaceDatasetSummary(
        id=dataset.id,
        name=dataset.name,
        source_id=dataset.source_id,
        file_path=dataset.file_path,
        scientific_dataset_id=_string_or_none(meta.get("scientific_dataset_id")),
        validation_outcome=_string_or_none(meta.get("validation_outcome")),
        created_at=dataset.created_at,
    )


def _run_summary(run: Run) -> WorkspaceRunSummary:
    return WorkspaceRunSummary(
        id=run.id,
        name=run.name,
        model_type=run.model_type,
        status=run.status,
        workflow=_run_workflow(run),
        execution_mode=_run_execution_mode(run),
        outputs=_run_outputs(run),
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _run_outputs(run: Run) -> WorkspaceRunOutputSummary:
    plan_id = _scientific_plan_id(run)
    artifact_names = _run_artifact_names(run)
    has_artifacts = (
        run.status == RunStatus.completed
        and plan_id is not None
        and bool(artifact_names)
    )
    return WorkspaceRunOutputSummary(
        plan_id=plan_id,
        artifacts=has_artifacts,
        result_summary=has_artifacts,
        predictions=has_artifacts and bool(_PREDICTION_ARTIFACTS.intersection(artifact_names)),
        alerts=has_artifacts and bool(_ALERT_ARTIFACTS.intersection(artifact_names)),
    )


def _scientific_plan_id(run: Run) -> str | None:
    results = _mapping(run.results)
    plan = _mapping(results.get("plan"))
    execution = _mapping(results.get("execution"))
    return _string_or_none(plan.get("plan_id")) or _string_or_none(execution.get("plan_id"))


def _run_artifact_names(run: Run) -> set[str]:
    execution = _mapping(_mapping(run.results).get("execution"))
    artifacts = execution.get("artifacts")
    if not isinstance(artifacts, list):
        return set()
    names: set[str] = set()
    for artifact in artifacts:
        artifact_map = _mapping(artifact)
        name = _string_or_none(artifact_map.get("name"))
        if name:
            names.add(name)
    return names


def _run_workflow(run: Run) -> str | None:
    config = _mapping(run.config)
    results = _mapping(run.results)
    execution = _mapping(results.get("execution"))
    plan = _mapping(results.get("plan"))
    metrics = _mapping(results.get("metrics"))
    return (
        _string_or_none(execution.get("workflow"))
        or _string_or_none(plan.get("workflow"))
        or _string_or_none(metrics.get("workflow"))
        or _string_or_none(config.get("workflow"))
        or _string_or_none(config.get("science_workflow"))
    )


def _run_execution_mode(run: Run) -> str | None:
    config = _mapping(run.config)
    parameters = _mapping(config.get("parameters"))
    if mode := _string_or_none(parameters.get("execution_mode")):
        return mode

    results = _mapping(run.results)
    summary = _mapping(results.get("summary"))
    summaries = _mapping(summary.get("summaries"))
    for value in summaries.values():
        section = _mapping(value)
        if mode := _string_or_none(section.get("execution_mode")):
            return mode
    return None


def _run_status_counter(runs: Sequence[Run]) -> dict[str, int]:
    counts = Counter(run.status.value for run in runs)
    return _complete_run_status_counts(counts)


def _output_view_counter(run_summaries: Sequence[WorkspaceRunSummary]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for summary in run_summaries:
        outputs = summary.outputs
        if outputs.artifacts:
            counts["artifacts"] += 1
        if outputs.result_summary:
            counts["result_summary"] += 1
        if outputs.predictions:
            counts["predictions"] += 1
        if outputs.alerts:
            counts["alerts"] += 1
    return counts


def _empty_run_status_counts() -> dict[str, int]:
    return {status.value: 0 for status in RunStatus}


def _complete_run_status_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {status.value: int(counts.get(status.value, 0)) for status in RunStatus}


def _empty_output_view_counts() -> dict[str, int]:
    return {"artifacts": 0, "result_summary": 0, "predictions": 0, "alerts": 0}


def _complete_output_view_counts(counts: Mapping[str, int]) -> dict[str, int]:
    base = _empty_output_view_counts()
    for key in base:
        base[key] = int(counts.get(key, 0))
    return base


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)
