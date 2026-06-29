import asyncio
from pathlib import Path

from src.api.models.run import ModelType
from src.api.schemas.dataset import DatasetObservation, DatasetValidationRequest
from src.api.schemas.run import RunCreateRequest
from src.api.schemas.simulation import SimulationCreateRequest
from src.api.services.dataset_repository import register_dataset_request
from src.api.tasks.training import _run_model_or_workflow


def _dataset_request() -> DatasetValidationRequest:
    return DatasetValidationRequest(
        dataset_name="Adapter Lake",
        requested_workflow="canonical_observations",
        observations=[
            DatasetObservation(
                source_id="adapter",
                site_id="lake-a",
                observed_at="2021-06-15",
                variable="TP_ugL",
                value=30.0,
                unit="ug/L",
            ),
            DatasetObservation(
                source_id="adapter",
                site_id="lake-a",
                observed_at="2021-06-15",
                variable="TN_ugL",
                value=800.0,
                unit="ug/L",
            ),
        ],
    )


def test_run_create_request_allows_scientific_workflow_config() -> None:
    request = RunCreateRequest(
        model_type=ModelType.pipe_grud,
        config={
            "dataset_id": "ds_1234567890abcdef",
            "workflow": "canonical_observations",
        },
    )

    assert request.config is not None
    assert request.config["workflow"] == "canonical_observations"


def test_simulation_request_accepts_current_state_counterfactual_scenario() -> None:
    request = SimulationCreateRequest.model_validate(
        {
            "site_id": "lake-a",
            "year_month": "2021-06",
            "horizon_days": 30,
            "scenario": {
                "type": "current_state_counterfactual",
                "plan_id": "plan_1234567890abcdef",
                "interventions": [
                    {"variable": "TP_ugL", "operation": "scale", "value": 0.8},
                ],
            },
        }
    )

    assert request.scenario.type == "current_state_counterfactual"


def test_training_task_adapter_executes_registered_scientific_workflow(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_dataset_request())

    result = asyncio.run(
        _run_model_or_workflow(
            ModelType.pipe_grud,
            {
                "dataset_id": dataset.dataset_id,
                "workflow": "canonical_observations",
            },
        )
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "local_scientific_workflow_v0"
    assert result["adapter_interface_version"] == "job_adapter_interface_v1"
    assert result["execution"]["workflow"] == "canonical_observations"
    assert result["execution"]["row_counts"]["canonical_observations"] == 2
