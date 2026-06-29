from pathlib import Path

import pytest

from src.api.models.run import ModelType
from src.api.schemas.dataset import DatasetObservation, DatasetValidationRequest
from src.api.services.dataset_repository import register_dataset_request
from src.api.services.scientific_workflow_adapters import (
    ADAPTER_INTERFACE_VERSION,
    ScientificWorkflowAdapterError,
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


def _pipe_grud_dataset_request() -> DatasetValidationRequest:
    return DatasetValidationRequest(
        dataset_name="PIPE Reference Lake",
        requested_workflow="pipe_grud",
        observations=[
            DatasetObservation(
                source_id="pipe-reference",
                site_id="lake-a",
                observed_at="2024-01-15",
                variable="TP_ugL",
                value=35.0,
                unit="ug/L",
            ),
            DatasetObservation(
                source_id="pipe-reference",
                site_id="lake-a",
                observed_at="2024-02-15",
                variable="TP_ugL",
                value=33.0,
                unit="ug/L",
            ),
            DatasetObservation(
                source_id="pipe-reference",
                site_id="lake-a",
                observed_at="2024-03-15",
                variable="TP_ugL",
                value=31.0,
                unit="ug/L",
            ),
        ],
    )


def _pipe_grud_sequence_dataset_request() -> DatasetValidationRequest:
    observations: list[DatasetObservation] = []
    for month in range(1, 14):
        observed_at = f"2024-{month:02d}-15" if month <= 12 else "2025-01-15"
        values = {
            "TP_ugL": 25.0 + month,
            "TN_ugL": 600.0 + month * 8.0,
            "DO_mgL": 7.5 - month * 0.03,
            "pH": 7.2,
            "temperature_C": 18.0 + month * 0.2,
            "secchi_depth_m": 1.2,
            "chlorophyll_a_ugL": 12.0 + month * 0.5,
        }
        units = {
            "TP_ugL": "ug/L",
            "TN_ugL": "ug/L",
            "DO_mgL": "mg/L",
            "pH": "dimensionless",
            "temperature_C": "deg C",
            "secchi_depth_m": "m",
            "chlorophyll_a_ugL": "ug/L",
        }
        for variable, value in values.items():
            observations.append(
                DatasetObservation(
                    source_id="pipe-sequence",
                    site_id="lake-a",
                    observed_at=observed_at,
                    variable=variable,
                    value=value,
                    unit=units[variable],
                )
            )
    return DatasetValidationRequest(
        dataset_name="PIPE Sequence Lake",
        requested_workflow="pipe_grud",
        observations=observations,
    )


def test_scientific_adapter_registry_exposes_safe_executable_workflows() -> None:
    adapters = registered_scientific_workflow_adapters()

    assert [adapter.adapter_id for adapter in adapters] == [
        "local_scientific_workflow_v0",
        "pipe_grud_reference_workflow_v0",
    ]
    assert executable_scientific_workflows() == frozenset(
        {"canonical_observations", "monthly_panel", "fuzzy_state", "pipe_grud"}
    )
    assert adapter_for_workflow("monthly_panel").interface_version == ADAPTER_INTERFACE_VERSION
    assert adapter_for_workflow("pipe_grud").adapter_id == "pipe_grud_reference_workflow_v0"


def test_missing_heavy_workflow_adapter_fails_with_clear_error() -> None:
    with pytest.raises(UnsupportedScientificWorkflowError, match="No job-backed adapter"):
        run_scientific_workflow_job(
            ModelType.pipe_neural_ode,
            {
                "dataset_id": "ds_1234567890abcdef",
                "workflow": "pipe_neural_ode",
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


def test_pipe_grud_reference_adapter_requires_explicit_artifact_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_dataset_request())

    with pytest.raises(ScientificWorkflowAdapterError, match="requires parameters.execution_mode"):
        run_scientific_workflow_job(
            ModelType.pipe_grud,
            {
                "dataset_id": dataset.dataset_id,
                "workflow": "pipe_grud",
            },
        )


def test_pipe_grud_preflight_adapter_writes_dataset_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "pipe_grud",
            "parameters": {"execution_mode": "preflight"},
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "pipe_grud_reference_workflow_v0"
    assert result["workflow"] == "pipe_grud"
    assert result["execution"]["row_counts"]["months"] == 3
    assert result["execution"]["row_counts"]["max_contiguous_site_months"] == 3
    summary = result["summary"]["summaries"]["pipe_grud_preflight"]
    assert summary["execution_mode"] == "preflight"
    assert summary["outcome"] == "not_ready"
    assert summary["readiness"]["ready_for_pipe_grud_inference"] is False
    blocker_codes = {blocker["code"] for blocker in summary["blockers"]}
    assert {"history_window_too_short", "pipe_state_surface_not_available"} <= blocker_codes
    artifact_names = {artifact["name"] for artifact in result["execution"]["artifacts"]}
    assert artifact_names == {
        "pipe_grud_preflight_report.md",
        "pipe_grud_preflight_manifest.json",
    }


def test_pipe_grud_sequence_build_adapter_writes_external_sequence_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_sequence_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "pipe_grud",
            "parameters": {"execution_mode": "build_sequences"},
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "pipe_grud_reference_workflow_v0"
    row_counts = result["execution"]["row_counts"]
    assert row_counts["pipe_state_surface"] == 13
    assert row_counts["kept_sequence_rows"] == 12
    assert row_counts["inference_candidate_origins"] == 2
    summary = result["summary"]["summaries"]["pipe_grud_sequence_build"]
    assert summary["execution_mode"] == "build_sequences"
    assert summary["outcome"] == "built_with_limitations"
    assert summary["readiness"]["ready_for_sequence_build"] is True
    assert summary["readiness"]["ready_for_reference_inference"] is False
    blocker_codes = {blocker["code"] for blocker in summary["blockers"]}
    assert "adaptive_reference_surface_not_available" in blocker_codes
    artifact_names = {artifact["name"] for artifact in result["execution"]["artifacts"]}
    assert {
        "pipe_state_surface.parquet",
        "pipe_sequences.parquet",
        "pipe_inference_origins.parquet",
        "pipe_sequence_build_report.md",
        "pipe_sequence_build_manifest.json",
    } <= artifact_names


def test_pipe_grud_reference_adapter_writes_manifest_and_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "pipe_grud",
            "parameters": {"execution_mode": "artifact_reference"},
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "pipe_grud_reference_workflow_v0"
    assert result["workflow"] == "pipe_grud"
    assert result["execution"]["row_counts"]["reference_test_rollout_rows"] > 0
    assert result["summary"]["summaries"]["pipe_grud_reference"]["execution_mode"] == "artifact_reference"
    artifact_names = {artifact["name"] for artifact in result["execution"]["artifacts"]}
    assert artifact_names == {"pipe_grud_run_report.md", "pipe_grud_run_manifest.json"}
