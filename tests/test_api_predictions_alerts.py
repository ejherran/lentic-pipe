import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from src.api.main import create_app


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
    assert payload["error"]["details"]["supported_workflows"] == ["fuzzy_state"]
