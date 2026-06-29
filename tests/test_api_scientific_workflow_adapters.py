from pathlib import Path

import pytest

from src.api.models.run import ModelType
from src.api.schemas.dataset import DatasetObservation, DatasetValidationRequest
from src.api.services.dataset_repository import register_dataset_request
from src.api.services.scientific_workflow_adapters import (
    ADAPTER_INTERFACE_VERSION,
    ScientificWorkflowAdapterError,
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


def _mifal_dataset_request() -> DatasetValidationRequest:
    observations: list[DatasetObservation] = []
    values_by_month = {
        "2024-01": {
            "TP_ugL": (35.0, "ug/L"),
            "TN_ugL": (900.0, "ug/L"),
            "DO_mgL": (7.5, "mg/L"),
            "temperature_C": (18.0, "deg C"),
            "secchi_depth_m": (1.4, "m"),
            "turbidity_NTU": (8.0, "NTU"),
            "chlorophyll_a_ugL": (12.0, "ug/L"),
        },
        "2024-02": {
            "TP_ugL": (45.0, "ug/L"),
            "TN_ugL": (980.0, "ug/L"),
            "DO_mgL": (6.8, "mg/L"),
            "temperature_C": (19.5, "deg C"),
            "secchi_depth_m": (1.1, "m"),
            "turbidity_NTU": (12.0, "NTU"),
            "chlorophyll_a_ugL": (18.0, "ug/L"),
        },
    }
    for year_month, values in values_by_month.items():
        for variable, (value, unit) in values.items():
            observations.append(
                DatasetObservation(
                    source_id="mifal-observable",
                    site_id="lake-a",
                    observed_at=f"{year_month}-15",
                    variable=variable,
                    value=value,
                    unit=unit,
                    qc_flag="ok",
                )
            )
    return DatasetValidationRequest(
        dataset_name="MIFAL Observable Lake",
        requested_workflow="mifal_ed_t2",
        observations=observations,
    )


def test_scientific_adapter_registry_exposes_safe_executable_workflows() -> None:
    adapters = registered_scientific_workflow_adapters()

    assert [adapter.adapter_id for adapter in adapters] == [
        "local_scientific_workflow_v0",
        "pipe_grud_reference_workflow_v0",
        "pipe_neural_ode_reference_workflow_v0",
        "mifal_observable_workflow_v0",
        "counterfactual_planning_workflow_v0",
    ]
    assert executable_scientific_workflows() == frozenset(
        {
            "canonical_observations",
            "monthly_panel",
            "fuzzy_state",
            "pipe_grud",
            "pipe_neural_ode",
            "mifal_ed_t2",
            "counterfactual_planning",
        }
    )
    assert adapter_for_workflow("monthly_panel").interface_version == ADAPTER_INTERFACE_VERSION
    assert adapter_for_workflow("pipe_grud").adapter_id == "pipe_grud_reference_workflow_v0"
    assert adapter_for_workflow("mifal_ed_t2").adapter_id == "mifal_observable_workflow_v0"


def test_neural_ode_reference_adapter_requires_explicit_mode() -> None:
    with pytest.raises(ScientificWorkflowAdapterError, match="requires parameters.execution_mode"):
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


def test_neural_ode_preflight_adapter_writes_dataset_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_sequence_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.pipe_neural_ode,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "pipe_neural_ode",
            "parameters": {"execution_mode": "preflight"},
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "pipe_neural_ode_reference_workflow_v0"
    assert result["workflow"] == "pipe_neural_ode"
    summary = result["summary"]["summaries"]["pipe_neural_ode_preflight"]
    assert summary["execution_mode"] == "preflight"
    assert summary["outcome"] == "ready_for_inference"
    assert summary["readiness"]["history_candidate"] is True
    assert summary["readiness"]["inference_adapter_available"] is True
    assert summary["readiness"]["ready_for_inference"] is True
    blocker_codes = {blocker["code"] for blocker in summary["blockers"]}
    assert blocker_codes == set()
    artifact_names = {artifact["name"] for artifact in result["execution"]["artifacts"]}
    assert artifact_names == {
        "pipe_neural_ode_preflight_report.md",
        "pipe_neural_ode_preflight_manifest.json",
    }


def test_neural_ode_reference_profile_inference_adapter_writes_calibrated_rollouts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("torch")
    pytest.importorskip("torchdiffeq")
    pytest.importorskip("joblib")
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_sequence_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.pipe_neural_ode,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "pipe_neural_ode",
            "parameters": {
                "execution_mode": "infer_reference_profile",
                "rollout_horizon": 2,
                "max_origins": 1,
                "deterministic": True,
                "policy_name": "closest_pr",
            },
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "pipe_neural_ode_reference_workflow_v0"
    row_counts = result["execution"]["row_counts"]
    assert row_counts["selected_origins"] == 1
    assert row_counts["rollout_rows"] == 2
    assert row_counts["alert_rows"] == 4
    summary = result["summary"]["summaries"]["pipe_neural_ode_reference_profile_inference"]
    assert summary["execution_mode"] == "infer_reference_profile"
    assert summary["outcome"] == "completed_reference_profile"
    assert summary["policy_name"] == "closest_pr"
    assert summary["readiness"]["reference_model_loaded"] is True
    assert summary["readiness"]["reference_bloom_calibrators_applied"] is True
    assert summary["readiness"]["policy_thresholds_applied"] is True
    assert summary["readiness"]["ready_for_reference_inference"] is True
    assert summary["blockers"] == []
    artifact_names = {artifact["name"] for artifact in result["execution"]["artifacts"]}
    assert {
        "pipe_adaptive_surface_manifest.json",
        "pipe_neural_ode_reference_rollouts.parquet",
        "pipe_neural_ode_reference_alerts.csv",
        "pipe_neural_ode_reference_policy_summary.csv",
        "pipe_neural_ode_reference_inference_report.md",
        "pipe_neural_ode_reference_inference_manifest.json",
    } <= artifact_names


def test_mifal_observable_adapter_writes_scores_and_alerts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_mifal_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.mifal,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "mifal_ed_t2",
            "parameters": {
                "execution_mode": "run_observable",
                "surface": "observable_no_current_chla",
                "horizons": [1, 2],
            },
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "mifal_observable_workflow_v0"
    row_counts = result["execution"]["row_counts"]
    assert row_counts["mifal_observable_surface"] == 2
    assert row_counts["mifal_scores"] == 4
    assert row_counts["mifal_alerts"] == 4
    summary = result["summary"]["summaries"]["mifal_observable"]
    assert summary["execution_mode"] == "run_observable"
    assert summary["surface"] == "observable_no_current_chla"
    assert summary["readiness"]["ready_for_mifal_scoring"] is True
    artifact_names = {artifact["name"] for artifact in result["execution"]["artifacts"]}
    assert {
        "mifal_observable_surface.csv",
        "mifal_scores.csv",
        "mifal_alerts.csv",
        "mifal_run_report.md",
        "mifal_run_manifest.json",
    } <= artifact_names


def test_counterfactual_planning_preflight_requires_upstream_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_sequence_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "counterfactual_planning",
            "parameters": {"execution_mode": "preflight"},
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "counterfactual_planning_workflow_v0"
    summary = result["summary"]["summaries"]["counterfactual_planning_preflight"]
    assert summary["execution_mode"] == "preflight"
    assert summary["outcome"] == "not_ready"
    blocker_codes = {blocker["code"] for blocker in summary["blockers"]}
    assert "missing_upstream_plan_id" in blocker_codes


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


def test_pipe_grud_adaptive_surface_adapter_writes_reference_ready_sequences(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("torch")
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_sequence_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "pipe_grud",
            "parameters": {"execution_mode": "build_adaptive_surface"},
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "pipe_grud_reference_workflow_v0"
    row_counts = result["execution"]["row_counts"]
    assert row_counts["adaptive_state_surface"] == 13
    assert row_counts["pipe_state_surface"] == 13
    assert row_counts["kept_sequence_rows"] == 12
    assert row_counts["inference_candidate_origins"] == 2
    summary = result["summary"]["summaries"]["pipe_grud_adaptive_surface_build"]
    assert summary["execution_mode"] == "build_adaptive_surface"
    assert summary["outcome"] == "built_reference_ready"
    assert summary["readiness"]["adaptive_reference_transform_applied"] is True
    assert summary["readiness"]["ready_for_reference_inference"] is True
    assert summary["blockers"] == []
    warning_codes = {warning["code"] for warning in summary["warnings"]}
    assert "external_domain_not_validated" in warning_codes
    artifact_names = {artifact["name"] for artifact in result["execution"]["artifacts"]}
    assert {
        "pipe_adaptive_state_surface.parquet",
        "pipe_adaptive_sequence_state.parquet",
        "pipe_state_surface.parquet",
        "pipe_sequences.parquet",
        "pipe_inference_origins.parquet",
        "pipe_adaptive_surface_report.md",
        "pipe_adaptive_surface_manifest.json",
    } <= artifact_names


def test_pipe_grud_expert_surface_inference_adapter_writes_diagnostic_rollouts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("torch")
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_sequence_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "pipe_grud",
            "parameters": {
                "execution_mode": "infer_expert_surface",
                "rollout_horizon": 2,
                "max_origins": 1,
                "deterministic": True,
            },
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "pipe_grud_reference_workflow_v0"
    row_counts = result["execution"]["row_counts"]
    assert row_counts["selected_origins"] == 1
    assert row_counts["rollout_rows"] == 2
    summary = result["summary"]["summaries"]["pipe_grud_expert_surface_inference"]
    assert summary["execution_mode"] == "infer_expert_surface"
    assert summary["outcome"] == "completed_with_limitations"
    assert summary["readiness"]["rollout_generated"] is True
    assert summary["readiness"]["ready_for_reference_inference"] is False
    blocker_codes = {blocker["code"] for blocker in summary["blockers"]}
    assert "adaptive_reference_surface_not_available" in blocker_codes
    artifact_names = {artifact["name"] for artifact in result["execution"]["artifacts"]}
    assert {
        "pipe_grud_external_rollouts.parquet",
        "pipe_grud_external_rollout_summary.csv",
        "pipe_grud_external_inference_report.md",
        "pipe_grud_external_inference_manifest.json",
    } <= artifact_names


def test_pipe_grud_reference_profile_inference_adapter_writes_calibrated_rollouts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("torch")
    pytest.importorskip("joblib")
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_sequence_dataset_request())

    result = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "pipe_grud",
            "parameters": {
                "execution_mode": "infer_reference_profile",
                "rollout_horizon": 2,
                "max_origins": 1,
                "deterministic": True,
                "policy_name": "closest_pr",
            },
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "pipe_grud_reference_workflow_v0"
    row_counts = result["execution"]["row_counts"]
    assert row_counts["selected_origins"] == 1
    assert row_counts["rollout_rows"] == 2
    assert row_counts["alert_rows"] == 4
    summary = result["summary"]["summaries"]["pipe_grud_reference_profile_inference"]
    assert summary["execution_mode"] == "infer_reference_profile"
    assert summary["outcome"] == "completed_reference_profile"
    assert summary["policy_name"] == "closest_pr"
    assert summary["readiness"]["reference_model_loaded"] is True
    assert summary["readiness"]["reference_bloom_calibrators_applied"] is True
    assert summary["readiness"]["policy_thresholds_applied"] is True
    assert summary["readiness"]["ready_for_reference_inference"] is True
    assert summary["blockers"] == []
    warning_codes = {warning["code"] for warning in summary["warnings"]}
    assert "external_domain_not_validated" in warning_codes
    artifact_names = {artifact["name"] for artifact in result["execution"]["artifacts"]}
    assert {
        "pipe_adaptive_surface_manifest.json",
        "pipe_grud_reference_rollouts.parquet",
        "pipe_grud_reference_alerts.csv",
        "pipe_grud_reference_policy_summary.csv",
        "pipe_grud_reference_inference_report.md",
        "pipe_grud_reference_inference_manifest.json",
    } <= artifact_names


def test_counterfactual_planning_adapter_runs_v1_scenarios_from_upstream_temporal_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("torch")
    pytest.importorskip("joblib")
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(_pipe_grud_sequence_dataset_request())
    upstream = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "pipe_grud",
            "parameters": {
                "execution_mode": "infer_reference_profile",
                "rollout_horizon": 2,
                "max_origins": 1,
                "deterministic": True,
                "policy_name": "closest_pr",
            },
        },
    )

    result = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {
            "dataset_id": dataset.dataset_id,
            "workflow": "counterfactual_planning",
            "parameters": {
                "execution_mode": "run_scenarios",
                "upstream_plan_id": upstream["plan"]["plan_id"],
                "evaluation_splits": ["external"],
                "examples_per_scenario": 2,
            },
        },
    )

    assert result["status"] == "completed"
    assert result["adapter"] == "counterfactual_planning_workflow_v0"
    row_counts = result["execution"]["row_counts"]
    assert row_counts["planning_rows"] == 2
    assert row_counts["summary_rows"] > 0
    assert row_counts["pareto_rows"] > 0
    summary = result["summary"]["summaries"]["counterfactual_planning_v1"]
    assert summary["execution_mode"] == "run_scenarios"
    assert summary["outcome"] == "completed_planning"
    assert summary["readiness"]["upstream_plan_id"] == upstream["plan"]["plan_id"]
    assert summary["readiness"]["ready_for_planning"] is True
    warning_codes = {warning["code"] for warning in summary["warnings"]}
    assert "counterfactual_not_causal" in warning_codes
    artifact_names = {artifact["name"] for artifact in result["execution"]["artifacts"]}
    assert {
        "counterfactual_planning_rows.csv",
        "counterfactual_panel.csv",
        "counterfactual_metrics.csv",
        "counterfactual_summary.csv",
        "counterfactual_pareto.csv",
        "counterfactual_examples.csv",
        "counterfactual_report.md",
        "counterfactual_manifest.json",
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
