import asyncio
import uuid
from pathlib import Path
from typing import Any, cast

from httpx import ASGITransport, AsyncClient

from src.api.core.dependencies import get_current_user
from src.api.database import get_db
from src.api.main import create_app
from src.api.models.run import ModelType, Run, RunStatus
from src.api.models.user import SystemRole, User
from src.api.schemas.dataset import DatasetValidationRequest
from src.api.services.dataset_repository import register_dataset_request
from src.api.services.scientific_workflow_adapters import run_scientific_workflow_job


class _FakeRunDb:
    def __init__(self, run: Run) -> None:
        self.run = run

    async def get(self, model: type[Any], item_id: uuid.UUID) -> object | None:
        if model is Run and item_id == self.run.id:
            return self.run
        return None


def _admin_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="admin@example.test",
        username="admin",
        hashed_password="not-used",
        system_role=SystemRole.admin,
        is_active=True,
    )


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
        "dataset_name": "Run Output Lake",
        "requested_workflow": "fuzzy_state",
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


def _completed_scientific_run(results: dict[str, Any]) -> Run:
    return Run(
        id=uuid.uuid4(),
        experiment_id=uuid.uuid4(),
        name="run-scientific-outputs",
        model_type=ModelType.pipe_grud,
        config={"workflow": "fuzzy_state"},
        status=RunStatus.completed,
        results=results,
        created_by=uuid.uuid4(),
    )


def test_api_exposes_scientific_artifacts_predictions_and_alerts_by_run_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(DatasetValidationRequest.model_validate(_fuzzy_payload()))
    results = run_scientific_workflow_job(
        ModelType.pipe_grud,
        {"dataset_id": dataset.dataset_id, "workflow": "fuzzy_state"},
    )
    run = _completed_scientific_run(results)
    admin = _admin_user()

    async def request() -> dict[str, dict[str, Any]]:
        app = create_app()

        async def override_get_db():
            yield _FakeRunDb(run)

        async def override_current_user() -> User:
            return admin

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_current_user
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                artifacts = await client.get(f"/runs/{run.id}/artifacts")
                preview = await client.get(
                    f"/runs/{run.id}/artifacts/fuzzy_state_scores.csv/preview",
                    params={"limit": 1},
                )
                summary = await client.get(f"/runs/{run.id}/results/summary")
                predictions = await client.get(
                    f"/runs/{run.id}/predictions",
                    params={"limit": 2},
                )
                alerts = await client.get(
                    f"/runs/{run.id}/alerts",
                    params={"limit": 2},
                )
        finally:
            app.dependency_overrides.clear()
        return {
            "artifacts": {"status_code": artifacts.status_code, "payload": artifacts.json()},
            "preview": {"status_code": preview.status_code, "payload": preview.json()},
            "summary": {"status_code": summary.status_code, "payload": summary.json()},
            "predictions": {"status_code": predictions.status_code, "payload": predictions.json()},
            "alerts": {"status_code": alerts.status_code, "payload": alerts.json()},
        }

    responses = asyncio.run(request())

    artifacts = cast(dict[str, Any], responses["artifacts"]["payload"])
    assert responses["artifacts"]["status_code"] == 200
    assert artifacts["plan_id"] == results["plan"]["plan_id"]
    assert {
        "fuzzy_state_scores.csv",
        "fuzzy_state_manifest.json",
    } <= {artifact["name"] for artifact in artifacts["artifacts"]}

    preview = cast(dict[str, Any], responses["preview"]["payload"])
    assert responses["preview"]["status_code"] == 200
    assert preview["preview_format"] == "csv"
    assert preview["artifact_name"] == "fuzzy_state_scores.csv"

    summary = cast(dict[str, Any], responses["summary"]["payload"])
    assert responses["summary"]["status_code"] == 200
    assert summary["summaries"]["fuzzy_state"]["rows"] == 2

    predictions = cast(dict[str, Any], responses["predictions"]["payload"])
    assert responses["predictions"]["status_code"] == 200
    assert predictions["prediction_surface"] == "expert_fuzzy_current_state"
    assert len(predictions["predictions"]) == 2

    alerts = cast(dict[str, Any], responses["alerts"]["payload"])
    assert responses["alerts"]["status_code"] == 200
    assert alerts["alert_surface"] == "expert_fuzzy_current_state_threshold"
    assert len(alerts["alerts"]) == 2


def test_api_rejects_run_id_scientific_views_without_plan_result() -> None:
    run = _completed_scientific_run({"status": "stub", "metrics": {}})
    admin = _admin_user()

    async def request() -> tuple[int, dict]:
        app = create_app()

        async def override_get_db():
            yield _FakeRunDb(run)

        async def override_current_user() -> User:
            return admin

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_current_user
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(f"/runs/{run.id}/predictions")
                return response.status_code, response.json()
        finally:
            app.dependency_overrides.clear()

    status_code, payload = asyncio.run(request())

    assert status_code == 409
    assert payload["error"]["code"] == "unsupported_pipeline_for_dataset"
    assert payload["error"]["details"]["expected_result_keys"] == [
        "plan.plan_id",
        "execution.plan_id",
    ]
