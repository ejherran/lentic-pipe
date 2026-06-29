import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.schemas.dataset import DatasetObservation, DatasetValidationRequest
from src.api.schemas.run import RunPlanRequest
from src.api.services.dataset_repository import register_dataset_request
from src.api.services.run_planner import plan_run_request
from src.api.services.run_repository import read_run_plan, save_run_plan


def _observations(months: int = 3) -> list[DatasetObservation]:
    rows = []
    for month in range(1, months + 1):
        rows.append(
            DatasetObservation(
                source_id="external",
                site_id="lake-alpha",
                observed_at=f"2024-{month:02d}-15",
                variable="TP_ugL",
                value=30.0 + month,
                unit="ug/L",
            )
        )
    return rows


def test_plan_run_request_reports_ready_monthly_panel(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(
        DatasetValidationRequest(
            dataset_name="Lake Alpha",
            observations=_observations(months=1),
        )
    )

    response = plan_run_request(
        RunPlanRequest(dataset_id=dataset.dataset_id, workflow="monthly_panel")
    )

    assert response.status == "ready"
    assert response.executable is True
    assert response.plan_id.startswith("plan_")
    assert response.steps[0].status == "available"
    assert any(artifact.name == "monthly_panel.csv" for artifact in response.required_artifacts)


def test_plan_run_request_reports_ready_fuzzy_state_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(
        DatasetValidationRequest(
            dataset_name="Lake Alpha",
            observations=_observations(months=1),
        )
    )

    response = plan_run_request(
        RunPlanRequest(dataset_id=dataset.dataset_id, workflow="fuzzy_state")
    )

    assert response.status == "ready"
    assert response.executable is True
    output_names = {
        artifact.name
        for artifact in response.required_artifacts
        if artifact.role == "output"
    }
    assert {
        "monthly_panel_wide.csv",
        "fuzzy_state_scores.csv",
        "fuzzy_state_trace.csv",
        "fuzzy_state_manifest.json",
    }.issubset(output_names)


def test_save_run_plan_writes_reproducibility_record(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(
        DatasetValidationRequest(
            dataset_name="Lake Alpha",
            observations=_observations(months=1),
        )
    )
    plan = plan_run_request(
        RunPlanRequest(dataset_id=dataset.dataset_id, workflow="monthly_panel")
    )

    saved = save_run_plan(plan, workspace=tmp_path)

    assert saved.plan_id == plan.plan_id
    assert (tmp_path / "runs" / plan.plan_id / "plan.json").exists()
    reloaded = read_run_plan(plan.plan_id, workspace=tmp_path)
    assert reloaded.plan_id == plan.plan_id
    assert reloaded.status == "ready"


def test_plan_run_request_reports_not_eligible_workflow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(
        DatasetValidationRequest(
            dataset_name="Lake Alpha",
            observations=_observations(months=1),
        )
    )

    response = plan_run_request(
        RunPlanRequest(dataset_id=dataset.dataset_id, workflow="pipe_neural_ode")
    )

    assert response.status == "not_eligible"
    assert response.executable is False
    assert response.blockers[0].code == "unsupported_pipeline_for_dataset"


def test_plan_run_request_blocks_invalid_dataset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    invalid_rows = _observations(months=1)
    invalid_rows[0] = invalid_rows[0].model_copy(update={"unit": "bananas"})
    dataset = register_dataset_request(
        DatasetValidationRequest(
            dataset_name="Lake Alpha",
            observations=invalid_rows,
        )
    )

    response = plan_run_request(
        RunPlanRequest(dataset_id=dataset.dataset_id, workflow="monthly_panel")
    )

    assert response.status == "blocked"
    assert response.executable is False
    assert "unsupported_unit" in {blocker.code for blocker in response.blockers}


def test_plan_run_request_blocks_counterfactual_without_upstream_surface(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(
        DatasetValidationRequest(
            dataset_name="Lake Alpha",
            observations=_observations(months=3),
        )
    )

    response = plan_run_request(
        RunPlanRequest(dataset_id=dataset.dataset_id, workflow="counterfactual_planning")
    )

    assert response.status == "blocked"
    assert response.executable is False
    assert response.blockers[0].code == "upstream_artifact_missing"
    assert "counterfactual_not_causal" in {warning.code for warning in response.warnings}


def test_plan_run_endpoint_persists_plan_and_handles_missing_resources(
    tmp_path: Path,
    monkeypatch,
) -> None:
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
                    "observations": [
                        row.model_dump(mode="json", exclude_none=True)
                        for row in _observations(months=1)
                    ],
                },
            )
            dataset_id = created.json()["dataset_id"]
            planned = await client.post(
                "/runs/plan",
                json={"dataset_id": dataset_id, "workflow": "monthly_panel"},
            )
            plan_id = planned.json()["plan_id"]
            fetched = await client.get(f"/runs/plans/{plan_id}")
            missing = await client.post(
                "/runs/plan",
                json={"dataset_id": "ds_0000000000000000", "workflow": "monthly_panel"},
            )
            return (
                planned.status_code,
                planned.json(),
                fetched.status_code,
                fetched.json(),
                missing.status_code,
                missing.json(),
            )

    plan_status, plan_payload, fetch_status, fetched_payload, missing_status, missing_payload = asyncio.run(request())

    assert plan_status == 200
    assert plan_payload["status"] == "ready"
    assert fetch_status == 200
    assert fetched_payload["plan_id"] == plan_payload["plan_id"]
    assert (tmp_path / "runs" / plan_payload["plan_id"] / "plan.json").exists()
    assert missing_status == 404
    assert missing_payload["error"]["code"] == "resource_not_found"
