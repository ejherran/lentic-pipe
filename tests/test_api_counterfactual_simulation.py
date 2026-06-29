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


def _counterfactual_request() -> dict[str, object]:
    return {
        "scenario_name": "nutrient-and-bloom-pressure-reduction",
        "interventions": [
            {"variable": "TP_ugL", "operation": "scale", "value": 0.1},
            {"variable": "TN_ugL", "operation": "scale", "value": 0.1},
            {"variable": "chlorophyll_a_ugL", "operation": "scale", "value": 0.05},
            {"variable": "DO_mgL", "operation": "set", "value": 9.0},
            {"variable": "pH", "operation": "set", "value": 7.6},
            {"variable": "turbidity_NTU", "operation": "scale", "value": 0.1},
            {"variable": "secchi_depth_m", "operation": "set", "value": 4.0},
            {"variable": "temperature_C", "operation": "set", "value": 10.0},
        ],
        "only_changed_alerts": True,
        "limit": 10,
    }


def test_api_runs_minimal_current_state_counterfactual(
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
            simulated = await client.post(
                f"/runs/plans/{plan_id}/simulations/counterfactual",
                json=_counterfactual_request(),
            )
            return {"simulated": {"status_code": simulated.status_code, "payload": simulated.json()}}

    response = asyncio.run(request())["simulated"]

    assert response["status_code"] == 200
    payload = response["payload"]
    assert payload["simulation_id"].startswith("sim_")
    assert payload["simulation_scope"] == "expert_fuzzy_current_state"
    assert payload["threshold"] == 0.5
    assert "not causal field evidence" in " ".join(payload["interpretation_limits"])
    assert len(payload["rows"]) == 1
    row = payload["rows"][0]
    assert row["year_month"] == "2024-02"
    assert row["baseline_alert"] is True
    assert row["simulated_alert"] is False
    assert row["alert_change"] == "cleared"
    assert row["delta_score"] < 0

    result_path = tmp_path / payload["result_uri"]
    assert result_path.exists()


def test_api_rejects_counterfactual_without_fuzzy_surface(
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
            response = await client.post(
                f"/runs/plans/{plan_id}/simulations/counterfactual",
                json=_counterfactual_request(),
            )
            return response.status_code, response.json()

    status_code, payload = asyncio.run(request())

    assert status_code == 409
    assert payload["error"]["code"] == "unsupported_pipeline_for_dataset"
    assert payload["error"]["details"]["supported_workflows"] == ["fuzzy_state"]
