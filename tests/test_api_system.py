import asyncio

from httpx import ASGITransport, AsyncClient
import pytest


@pytest.fixture
def app():
    pytest.importorskip("fastapi")

    from src.api.main import create_app

    return create_app()


def _get_json(app, path: str) -> tuple[int, dict]:
    async def request() -> tuple[int, dict]:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(path)
            return response.status_code, response.json()

    return asyncio.run(request())


def test_health_endpoints(app) -> None:
    live_status, live_payload = _get_json(app, "/health/live")
    ready_status, ready_payload = _get_json(app, "/health/ready")

    assert live_status == 200
    assert live_payload["status"] == "ok"
    assert ready_status == 200
    assert ready_payload["components"]["api"] == "ok"


def test_version_exposes_contracts_and_workflows(app) -> None:
    status_code, payload = _get_json(app, "/version")

    assert status_code == 200
    assert payload["project"] == "lentic-pipe"
    assert payload["stage"] == "local_workflow_api"
    assert payload["supported_horizons"] == ["h1", "h2", "h3"]
    assert payload["documents"]["dataset_contract"] == "docs/API_DATASET_CONTRACT.md"
    workflows = {workflow["name"]: workflow for workflow in payload["workflows"]}
    assert {
        "dataset_validation",
        "fuzzy_state",
        "current_state_counterfactual",
        "pipe_grud",
        "counterfactual_planning",
    } <= set(workflows)
    assert workflows["fuzzy_state"]["status"] == "local_executor"
    assert workflows["current_state_counterfactual"]["status"] == "local_simulation"
    assert workflows["pipe_grud"]["status"] == "calibrated_reference_inference_adapter"
    assert workflows["pipe_neural_ode"]["status"] == "reference_preflight_adapter"
    assert workflows["mifal_ed_t2"]["status"] == "observable_execution_adapter"
    assert workflows["counterfactual_planning"]["status"] == "upstream_preflight_reference_adapter"
    assert payload["job_adapters"]["interface_version"] == "job_adapter_interface_v1"
    adapters = {adapter["adapter_id"]: adapter for adapter in payload["job_adapters"]["registered"]}
    assert adapters["local_scientific_workflow_v0"]["workflows"] == [
        "canonical_observations",
        "fuzzy_state",
        "monthly_panel",
    ]
    assert adapters["pipe_grud_reference_workflow_v0"]["workflows"] == ["pipe_grud"]
    assert adapters["pipe_neural_ode_reference_workflow_v0"]["workflows"] == ["pipe_neural_ode"]
    assert adapters["mifal_observable_workflow_v0"]["workflows"] == ["mifal_ed_t2"]
    assert adapters["counterfactual_planning_workflow_v0"]["workflows"] == ["counterfactual_planning"]


def test_error_catalog_endpoint(app) -> None:
    status_code, payload = _get_json(app, "/errors")

    assert status_code == 200
    error_codes = {item["code"] for item in payload["errors"]}
    assert "schema_validation_failed" in error_codes
    assert "unsupported_pipeline_for_dataset" in error_codes
    assert "counterfactual_not_causal" in payload["warnings"]


def test_openapi_is_available(app) -> None:
    status_code, payload = _get_json(app, "/openapi.json")

    assert status_code == 200
    assert payload["info"]["title"] == "Lentic Pipe API"
    assert "/health/live" in payload["paths"]
    assert "/version" in payload["paths"]
    assert "/datasets" in payload["paths"]
    assert "/datasets/{dataset_id}" in payload["paths"]
    assert "/datasets/validate" in payload["paths"]
    assert "/workspace/catalog" in payload["paths"]
    assert "/runs/plan" in payload["paths"]
    assert "/runs/plans/{plan_id}" in payload["paths"]
    assert "/runs/plans/{plan_id}/execute" in payload["paths"]
    assert "/runs/plans/{plan_id}/execution" in payload["paths"]
    assert "/runs/plans/{plan_id}/artifacts" in payload["paths"]
    assert "/runs/plans/{plan_id}/artifacts/{artifact_name}/preview" in payload["paths"]
    assert "/runs/plans/{plan_id}/results/summary" in payload["paths"]
    assert "/runs/plans/{plan_id}/predictions" in payload["paths"]
    assert "/runs/plans/{plan_id}/alerts" in payload["paths"]
    assert "/runs/plans/{plan_id}/simulations/counterfactual" in payload["paths"]
    assert "/runs/{run_id}/artifacts" in payload["paths"]
    assert "/runs/{run_id}/artifacts/{artifact_name}/preview" in payload["paths"]
    assert "/runs/{run_id}/results/summary" in payload["paths"]
    assert "/runs/{run_id}/predictions" in payload["paths"]
    assert "/runs/{run_id}/alerts" in payload["paths"]
