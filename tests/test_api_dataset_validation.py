import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.schemas.dataset import DatasetObservation, DatasetValidationRequest
from src.api.services.dataset_repository import (
    read_registered_dataset,
    register_dataset_request,
)
from src.api.services.dataset_validation import validate_dataset_request


def _valid_observation_payloads() -> list[dict[str, object]]:
    return [
        {
            "source_id": "external",
            "site_id": "lake-alpha",
            "observed_at": "2024-01-15",
            "variable": "TP_ugL",
            "value": 35.0,
            "unit": "ug/L",
        },
        {
            "source_id": "external",
            "site_id": "lake-alpha",
            "observed_at": "2024-02-15",
            "variable": "TN_ugL",
            "value": 800.0,
            "unit": "ug/L",
        },
        {
            "source_id": "external",
            "site_id": "lake-alpha",
            "observed_at": "2024-03-15",
            "variable": "chlorophyll_a_ugL",
            "value": 12.0,
            "unit": "ug/L",
        },
    ]


def _valid_observations() -> list[DatasetObservation]:
    return [DatasetObservation.model_validate(row) for row in _valid_observation_payloads()]


def test_validate_dataset_request_accepts_supported_long_form_rows() -> None:
    request = DatasetValidationRequest(observations=_valid_observations())

    response = validate_dataset_request(request)

    assert response.outcome == "valid"
    assert response.summary.total_rows == 3
    assert response.summary.valid_rows == 3
    assert response.summary.months == 3
    assert response.summary.canonical_variable_counts["TP_ugL"] == 1
    eligibility = {item.workflow: item.eligible for item in response.workflow_eligibility}
    assert eligibility["canonical_observations"]
    assert eligibility["monthly_panel"]
    assert eligibility["pipe_grud"]


def test_validate_dataset_request_reports_unsupported_units() -> None:
    rows = _valid_observations()
    rows[0] = rows[0].model_copy(update={"unit": "bananas"})
    request = DatasetValidationRequest(observations=rows)

    response = validate_dataset_request(request)

    assert response.outcome == "invalid"
    assert response.summary.invalid_rows == 1
    assert response.errors[0].code == "unsupported_unit"
    assert response.errors[0].field == "unit"


def test_validate_dataset_request_reports_workflow_not_eligible() -> None:
    request = DatasetValidationRequest(
        requested_workflow="pipe_neural_ode",
        observations=[_valid_observations()[0]],
    )

    response = validate_dataset_request(request)

    assert response.outcome == "not_eligible"
    assert response.workflow_eligibility[0].workflow == "pipe_neural_ode"
    assert response.workflow_eligibility[0].eligible is False


def test_validate_dataset_endpoint() -> None:
    async def request() -> tuple[int, dict]:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/datasets/validate",
                json={"observations": _valid_observation_payloads()},
            )
            return response.status_code, response.json()

    status_code, payload = asyncio.run(request())

    assert status_code == 200
    assert payload["outcome"] == "valid"
    assert payload["summary"]["valid_rows"] == 3


def test_register_dataset_request_writes_reproducibility_artifacts(tmp_path: Path) -> None:
    request = DatasetValidationRequest(
        dataset_name="Lake Alpha",
        requested_workflow="pipe_grud",
        observations=_valid_observations(),
    )

    response = register_dataset_request(request, workspace=tmp_path)

    assert response.dataset_id.startswith("ds_")
    assert response.status == "registered"
    assert response.content_sha256
    assert response.validation.outcome == "valid"
    assert {artifact.name for artifact in response.artifacts} == {
        "payload",
        "validation",
        "manifest",
    }
    dataset_dir = tmp_path / "datasets" / response.dataset_id
    assert (dataset_dir / "payload.json").exists()
    assert (dataset_dir / "validation.json").exists()
    assert (dataset_dir / "manifest.json").exists()

    reloaded = read_registered_dataset(response.dataset_id, workspace=tmp_path)
    assert reloaded.dataset_id == response.dataset_id
    assert reloaded.content_sha256 == response.content_sha256


def test_dataset_registration_endpoint_round_trips_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))

    async def request() -> tuple[int, dict, int, dict, int, dict]:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            created = await client.post(
                "/datasets",
                json={
                    "dataset_name": "Lake Alpha",
                    "requested_workflow": "pipe_grud",
                    "observations": _valid_observation_payloads(),
                },
            )
            dataset_id = created.json()["dataset_id"]
            fetched = await client.get(f"/datasets/{dataset_id}")
            missing = await client.get("/datasets/ds_0000000000000000")
            return (
                created.status_code,
                created.json(),
                fetched.status_code,
                fetched.json(),
                missing.status_code,
                missing.json(),
            )

    create_status, created_payload, fetch_status, fetched_payload, missing_status, missing_payload = asyncio.run(request())

    assert create_status == 201
    assert created_payload["validation"]["outcome"] == "valid"
    assert fetch_status == 200
    assert fetched_payload["dataset_id"] == created_payload["dataset_id"]
    assert missing_status == 404
    assert missing_payload["error"]["code"] == "resource_not_found"
