import uuid
from datetime import datetime, timezone
from typing import Any

from src.api.models.experiment import Dataset, Experiment, ExperimentStatus
from src.api.models.run import ModelType, Run, RunStatus
from src.api.services.workspace_catalog import (
    build_workspace_catalog_entry,
    build_workspace_catalog_summary,
)


def _dt(month: int, day: int) -> datetime:
    return datetime(2026, month, day, tzinfo=timezone.utc)


def _experiment() -> Experiment:
    return Experiment(
        id=uuid.uuid4(),
        title="Workspace Lake",
        description="External lake workspace",
        status=ExperimentStatus.active,
        created_by=uuid.uuid4(),
        created_at=_dt(1, 1),
        updated_at=_dt(1, 5),
    )


def _dataset(experiment_id: uuid.UUID, *, day: int = 2) -> Dataset:
    return Dataset(
        id=uuid.uuid4(),
        experiment_id=experiment_id,
        name="Registered Lake Dataset",
        source_id="upload-a",
        file_path="datasets/science-123/manifest.json",
        meta={
            "kind": "lentic_scientific_dataset",
            "scientific_dataset_id": "science-123",
            "validation_outcome": "valid_with_warnings",
        },
        created_at=_dt(1, day),
    )


def _run(
    experiment_id: uuid.UUID,
    *,
    status: RunStatus,
    name: str,
    results: dict[str, Any] | None,
    created_day: int,
) -> Run:
    return Run(
        id=uuid.uuid4(),
        experiment_id=experiment_id,
        name=name,
        model_type=ModelType.pipe_grud,
        config={
            "workflow": "pipe_grud",
            "parameters": {"execution_mode": "infer_reference_profile"},
        },
        status=status,
        results=results,
        created_at=_dt(1, created_day),
        started_at=_dt(1, created_day),
        completed_at=_dt(1, created_day) if status == RunStatus.completed else None,
    )


def test_workspace_catalog_entry_summarizes_scientific_outputs() -> None:
    experiment = _experiment()
    scientific_results = {
        "plan": {"plan_id": "plan_abc123", "workflow": "pipe_grud"},
        "execution": {
            "plan_id": "plan_abc123",
            "workflow": "pipe_grud",
            "artifacts": [
                {"name": "pipe_grud_reference_rollouts.csv"},
                {"name": "pipe_grud_reference_alerts.csv"},
            ],
        },
        "summary": {
            "summaries": {
                "pipe_grud_reference": {
                    "execution_mode": "infer_reference_profile",
                }
            }
        },
    }

    entry = build_workspace_catalog_entry(
        experiment,
        role="owner",
        datasets=[_dataset(experiment.id)],
        runs=[
            _run(
                experiment.id,
                status=RunStatus.completed,
                name="reference inference",
                results=scientific_results,
                created_day=4,
            ),
            _run(
                experiment.id,
                status=RunStatus.pending,
                name="queued placeholder",
                results=None,
                created_day=3,
            ),
        ],
    )

    assert entry.role == "owner"
    assert entry.dataset_count == 1
    assert entry.run_count == 2
    assert entry.latest_dataset is not None
    assert entry.latest_dataset.scientific_dataset_id == "science-123"
    assert entry.latest_run is not None
    assert entry.latest_run.name == "reference inference"
    assert entry.latest_scientific_run is not None
    assert entry.latest_scientific_run.outputs.plan_id == "plan_abc123"
    assert entry.latest_scientific_run.outputs.predictions is True
    assert entry.latest_scientific_run.outputs.alerts is True
    assert entry.latest_scientific_run.execution_mode == "infer_reference_profile"
    assert entry.available_views == ["alerts", "artifacts", "predictions", "result_summary"]


def test_workspace_catalog_summary_counts_page_views() -> None:
    experiment = _experiment()
    entry = build_workspace_catalog_entry(
        experiment,
        role="admin",
        datasets=[_dataset(experiment.id)],
        runs=[
            _run(
                experiment.id,
                status=RunStatus.completed,
                name="fuzzy state",
                results={
                    "plan": {"plan_id": "plan_fuzzy"},
                    "execution": {
                        "plan_id": "plan_fuzzy",
                        "workflow": "fuzzy_state",
                        "artifacts": [{"name": "fuzzy_state_scores.csv"}],
                    },
                },
                created_day=6,
            )
        ],
    )

    summary = build_workspace_catalog_summary(visible_experiments=3, items=[entry])

    assert summary.visible_experiments == 3
    assert summary.page_experiments == 1
    assert summary.page_datasets == 1
    assert summary.page_runs == 1
    assert summary.page_scientific_runs == 1
    assert summary.page_run_status_counts["completed"] == 1
    assert summary.page_output_view_counts == {
        "artifacts": 1,
        "result_summary": 1,
        "predictions": 1,
        "alerts": 1,
    }
