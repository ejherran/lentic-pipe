from pathlib import Path

import pytest

from src.api.models.run import ModelType
from src.api.schemas.dataset import DatasetObservation, DatasetValidationRequest
from src.api.services.dataset_repository import register_dataset_request
from src.api.services.scientific_workflow_adapters import (
    ADAPTER_INTERFACE_VERSION,
    UnsupportedScientificWorkflowError,
    adapter_for_workflow,
    executable_scientific_workflows,
    registered_scientific_workflow_adapters,
    run_scientific_workflow_job,
)


def _dataset_request() -> DatasetValidationRequest:
    return DatasetValidationRequest(
        dataset_name="Adapter Registry Lake",
        requested_workflow="monthly_panel",
        observations=[
            DatasetObservation(
                source_id="adapter-registry",
                site_id="lake-a",
                observed_at="2024-01-15",
                variable="TP_ugL",
                value=35.0,
                unit="ug/L",
            ),
            DatasetObservation(
                source_id="adapter-registry",
                site_id="lake-a",
                observed_at="2024-01-15",
                variable="TN_ugL",
                value=800.0,
                unit="ug/L",
            ),
        ],
    )


def test_scientific_adapter_registry_exposes_safe_executable_workflows() -> None:
    adapters = registered_scientific_workflow_adapters()

    assert [adapter.adapter_id for adapter in adapters] == ["local_scientific_workflow_v0"]
    assert executable_scientific_workflows() == frozenset(
        {"canonical_observations", "monthly_panel", "fuzzy_state"}
    )
    assert adapter_for_workflow("monthly_panel").interface_version == ADAPTER_INTERFACE_VERSION


def test_missing_heavy_workflow_adapter_fails_with_clear_error() -> None:
    with pytest.raises(UnsupportedScientificWorkflowError, match="No job-backed adapter"):
        run_scientific_workflow_job(
            ModelType.pipe_grud,
            {
                "dataset_id": "ds_1234567890abcdef",
                "workflow": "pipe_grud",
            },
        )


def test_local_deterministic_adapter_runs_registered_monthly_panel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "monthly_panel",
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "local_scientific_workflow_v0"
    assert result["adapter_interface_version"] == ADAPTER_INTERFACE_VERSION
    assert result["workflow"] == "monthly_panel"
    assert result["metrics"]["row_counts"] == {
        "canonical_observations": 2,
        "monthly_panel": 2,
    }
