import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient
import pytest

from src.api.main import create_app
from src.api.models.run import ModelType
from src.api.schemas.dataset import DatasetObservation, DatasetValidationRequest
from src.api.services.dataset_repository import register_dataset_request
from src.api.services.mifal_external import mifal_reference_artifacts_available
from src.api.services.pipe_grud_external_reference_inference import reference_inference_artifacts_available
from src.api.services.pipe_neural_ode_external_reference_inference import (
    neural_ode_reference_inference_artifacts_available,
)
from src.api.services.scientific_workflow_adapters import run_scientific_workflow_job


def _skip_if_unavailable(label: str, availability: tuple[bool, list[str]]) -> None:
    available, missing = availability
    if not available:
        pytest.skip(f"{label} requires DVC-managed artifacts: {', '.join(sorted(missing))}")


def _fuzzy_payload() -> dict[str, object]:
    values_by_month = {
        "2024-01": {
            "TP_ugL": (8.0, "ug/L"),
            "TN_ugL": (250.0, "ug/L"),
            "DO_mgL": (9.0, "mg/L"),
            "pH": (7.6, "dimensionless"),
            "turbidity_NTU": (2.0, "NTU"),
            "secchi_depth_m": (4.0, "m"),
            "temperature_C": (10.0, "deg C"),
            "chlorophyll_a_ugL": (1.0, "ug/L"),
        },
        "2024-02": {
            "TP_ugL": (150.0, "ug/L"),
            "TN_ugL": (2500.0, "ug/L"),
            "DO_mgL": (2.0, "mg/L"),
            "pH": (10.0, "dimensionless"),
            "turbidity_NTU": (90.0, "NTU"),
            "secchi_depth_m": (0.2, "m"),
            "temperature_C": (26.0, "deg C"),
            "chlorophyll_a_ugL": (45.0, "ug/L"),
        },
    }
    return {
        "dataset_name": "Lake Alpha",
        "observations": [
            {
                "source_id": "external",
                "site_id": "lake-alpha",
                "observed_at": f"{year_month}-15",
                "variable": variable,
                "value": value,
                "unit": unit,
                "qc_flag": "ok",
            }
            for year_month, variables in values_by_month.items()
            for variable, (value, unit) in variables.items()
        ],
    }


def _minimal_payload() -> dict[str, object]:
    return {
        "dataset_name": "Lake Alpha",
        "observations": [
            {
                "source_id": "external",
                "site_id": "lake-alpha",
                "observed_at": "2024-01-15",
                "variable": "TP_ugL",
                "value": 30.0,
                "unit": "ug/L",
            }
        ],
    }


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


def test_api_exposes_current_state_predictions_and_alerts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))

    async def request() -> dict[str, dict]:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            registered = await client.post("/datasets", json=_fuzzy_payload())
            dataset_id = registered.json()["dataset_id"]
            planned = await client.post(
                "/runs/plan",
                json={"dataset_id": dataset_id, "workflow": "fuzzy_state"},
            )
            plan_id = planned.json()["plan_id"]
            await client.post(f"/runs/plans/{plan_id}/execute")
            predictions = await client.get(
                f"/runs/plans/{plan_id}/predictions",
                params={"limit": 2},
            )
            alerts = await client.get(
                f"/runs/plans/{plan_id}/alerts",
                params={"limit": 2},
            )
            only_alerts = await client.get(
                f"/runs/plans/{plan_id}/alerts",
                params={"only_alerts": True},
            )
            return {
                "predictions": {"status_code": predictions.status_code, "payload": predictions.json()},
                "alerts": {"status_code": alerts.status_code, "payload": alerts.json()},
                "only_alerts": {"status_code": only_alerts.status_code, "payload": only_alerts.json()},
            }

    responses = asyncio.run(request())

    predictions = responses["predictions"]["payload"]
    assert responses["predictions"]["status_code"] == 200
    assert predictions["prediction_surface"] == "expert_fuzzy_current_state"
    assert len(predictions["predictions"]) == 2
    assert predictions["predictions"][0]["horizon_months"] == 0
    assert predictions["predictions"][0]["score_kind"] == "expert_score"
    assert predictions["predictions"][0]["target"] == "current_irc_risk"
    assert "not temporal forecasts" in " ".join(predictions["interpretation_limits"])

    alerts = responses["alerts"]["payload"]
    assert responses["alerts"]["status_code"] == 200
    assert alerts["alert_surface"] == "expert_fuzzy_current_state_threshold"
    assert alerts["threshold"] == 0.5
    assert alerts["alerts"][0]["rank"] == 1
    assert alerts["alerts"][0]["year_month"] == "2024-02"
    assert alerts["alerts"][0]["is_alert"] is True
    assert alerts["alerts"][0]["severity"] == "alert"

    only_alerts = responses["only_alerts"]["payload"]["alerts"]
    assert len(only_alerts) == 1
    assert only_alerts[0]["year_month"] == "2024-02"


def test_api_exposes_pipe_grud_reference_predictions_and_alerts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pytest.importorskip("torch")
    pytest.importorskip("joblib")
    _skip_if_unavailable("PIPE-GRU-D reference predictions", reference_inference_artifacts_available())
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
    plan_id = result["plan"]["plan_id"]

    async def request() -> dict[str, dict]:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            predictions = await client.get(
                f"/runs/plans/{plan_id}/predictions",
                params={"limit": 4},
            )
            alerts = await client.get(
                f"/runs/plans/{plan_id}/alerts",
                params={"limit": 4},
            )
            return {
                "predictions": {"status_code": predictions.status_code, "payload": predictions.json()},
                "alerts": {"status_code": alerts.status_code, "payload": alerts.json()},
            }

    responses = asyncio.run(request())

    predictions = responses["predictions"]["payload"]
    assert responses["predictions"]["status_code"] == 200
    assert predictions["prediction_surface"] == "pipe_grud_adaptive_reference_rollout"
    assert len(predictions["predictions"]) == 4
    assert {record["target"] for record in predictions["predictions"]} == {"irc_alert", "bloom_h"}
    assert {record["horizon_months"] for record in predictions["predictions"]} == {1, 2}
    score_kind_by_target = {record["target"]: record["score_kind"] for record in predictions["predictions"]}
    assert score_kind_by_target == {
        "irc_alert": "model_probability",
        "bloom_h": "calibrated_probability",
    }

    alerts = responses["alerts"]["payload"]
    assert responses["alerts"]["status_code"] == 200
    assert alerts["alert_surface"] == "pipe_grud_adaptive_reference_policy_2b"
    assert alerts["policy_version"] == "closest_pr"
    assert len(alerts["alerts"]) == 4
    assert {record["target_event"] for record in alerts["alerts"]} == {"irc_alert", "bloom_h"}
    assert all(record["threshold"] >= 0.0 for record in alerts["alerts"])


def test_api_exposes_neural_ode_reference_predictions_and_alerts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pytest.importorskip("torch")
    pytest.importorskip("torchdiffeq")
    pytest.importorskip("joblib")
    _skip_if_unavailable(
        "Neural ODE reference predictions",
        neural_ode_reference_inference_artifacts_available(),
    )
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
    plan_id = result["plan"]["plan_id"]

    async def request() -> dict[str, dict]:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            predictions = await client.get(
                f"/runs/plans/{plan_id}/predictions",
                params={"limit": 4},
            )
            alerts = await client.get(
                f"/runs/plans/{plan_id}/alerts",
                params={"limit": 4},
            )
            return {
                "predictions": {"status_code": predictions.status_code, "payload": predictions.json()},
                "alerts": {"status_code": alerts.status_code, "payload": alerts.json()},
            }

    responses = asyncio.run(request())

    predictions = responses["predictions"]["payload"]
    assert responses["predictions"]["status_code"] == 200
    assert predictions["prediction_surface"] == "pipe_neural_ode_adaptive_reference_rollout"
    assert len(predictions["predictions"]) == 4
    assert {record["target"] for record in predictions["predictions"]} == {"irc_alert", "bloom_h"}
    assert {record["horizon_months"] for record in predictions["predictions"]} == {1, 2}
    assert "Neural ODE" in predictions["predictions"][0]["interpretation"]

    alerts = responses["alerts"]["payload"]
    assert responses["alerts"]["status_code"] == 200
    assert alerts["alert_surface"] == "pipe_neural_ode_adaptive_reference_policy_2b"
    assert alerts["policy_version"] == "closest_pr"
    assert len(alerts["alerts"]) == 4
    assert {record["target_event"] for record in alerts["alerts"]} == {"irc_alert", "bloom_h"}
    assert all(record["threshold"] >= 0.0 for record in alerts["alerts"])


def test_api_exposes_mifal_predictions_and_alerts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _skip_if_unavailable(
        "MIFAL calibrated predictions",
        mifal_reference_artifacts_available("observable_no_current_chla"),
    )
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
    plan_id = result["plan"]["plan_id"]

    async def request() -> dict[str, dict]:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            predictions = await client.get(
                f"/runs/plans/{plan_id}/predictions",
                params={"limit": 4},
            )
            alerts = await client.get(
                f"/runs/plans/{plan_id}/alerts",
                params={"limit": 4},
            )
            return {
                "predictions": {"status_code": predictions.status_code, "payload": predictions.json()},
                "alerts": {"status_code": alerts.status_code, "payload": alerts.json()},
            }

    responses = asyncio.run(request())

    predictions = responses["predictions"]["payload"]
    assert responses["predictions"]["status_code"] == 200
    assert predictions["prediction_surface"] == "mifal_ed_t2_observable_bloom_risk"
    assert len(predictions["predictions"]) == 4
    assert {record["target"] for record in predictions["predictions"]} == {"bloom_h"}
    assert {record["score_kind"] for record in predictions["predictions"]} == {"calibrated_probability"}
    assert {record["horizon_months"] for record in predictions["predictions"]} == {1, 2}

    alerts = responses["alerts"]["payload"]
    assert responses["alerts"]["status_code"] == 200
    assert alerts["alert_surface"] == "mifal_ed_t2_observable_bloom_policy"
    assert len(alerts["alerts"]) == 4
    assert {record["target_event"] for record in alerts["alerts"]} == {"bloom_h"}
    assert all(record["threshold"] >= 0.0 for record in alerts["alerts"])


def test_api_rejects_predictions_when_surface_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))

    async def request() -> tuple[int, dict]:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            registered = await client.post("/datasets", json=_minimal_payload())
            dataset_id = registered.json()["dataset_id"]
            planned = await client.post(
                "/runs/plan",
                json={"dataset_id": dataset_id, "workflow": "monthly_panel"},
            )
            plan_id = planned.json()["plan_id"]
            await client.post(f"/runs/plans/{plan_id}/execute")
            response = await client.get(f"/runs/plans/{plan_id}/predictions")
            return response.status_code, response.json()

    status_code, payload = asyncio.run(request())

    assert status_code == 409
    assert payload["error"]["code"] == "unsupported_pipeline_for_dataset"
    assert payload["error"]["details"]["supported_workflows"] == [
        "fuzzy_state",
        "pipe_grud",
        "pipe_neural_ode",
        "mifal_ed_t2",
    ]
