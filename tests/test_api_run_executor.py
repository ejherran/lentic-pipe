import asyncio
import csv
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.schemas.dataset import DatasetObservation, DatasetValidationRequest
from src.api.schemas.run import RunPlanRequest
from src.api.services.dataset_repository import register_dataset_request
from src.api.services.run_executor import execute_run_plan
from src.api.services.run_planner import plan_run_request
from src.api.services.run_repository import read_run_execution, save_run_plan


def _mixed_unit_observations() -> list[DatasetObservation]:
    return [
        DatasetObservation(
            source_id="external",
            site_id="lake-alpha",
            observed_at="2024-01-05",
            variable="TP_ugL",
            value=0.03,
            unit="mg/L",
        ),
        DatasetObservation(
            source_id="external",
            site_id="lake-alpha",
            observed_at="2024-01-20",
            variable="TP_ugL",
            value=40.0,
            unit="ug/L",
        ),
        DatasetObservation(
            source_id="external",
            site_id="lake-alpha",
            observed_at="2024-02-15",
            variable="TN_ugL",
            value=0.9,
            unit="mg/L",
        ),
    ]


def test_execute_monthly_panel_writes_canonical_and_panel_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(
        DatasetValidationRequest(
            dataset_name="Lake Alpha",
            observations=_mixed_unit_observations(),
        )
    )
    plan = save_run_plan(
        plan_run_request(
            RunPlanRequest(dataset_id=dataset.dataset_id, workflow="monthly_panel")
        )
    )

    response = execute_run_plan(plan.plan_id)

    assert response.status == "completed"
    assert response.row_counts == {"canonical_observations": 3, "monthly_panel": 2}
    run_dir = tmp_path / "runs" / plan.plan_id
    assert (run_dir / "canonical_observations.jsonl").exists()
    assert (run_dir / "canonical_observations.csv").exists()
    assert (run_dir / "monthly_panel.csv").exists()
    assert (run_dir / "execution_manifest.json").exists()
    assert (run_dir / "execution.json").exists()
    assert {artifact.name for artifact in response.artifacts} == {
        "canonical_observations.jsonl",
        "canonical_observations.csv",
        "monthly_panel.csv",
        "execution_manifest.json",
    }

    with (run_dir / "monthly_panel.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    tp_row = next(row for row in rows if row["variable"] == "TP_ugL")
    assert tp_row["year_month"] == "2024-01"
    assert float(tp_row["value"]) == 35.0
    assert tp_row["unit"] == "ug/L"
    assert tp_row["observation_count"] == "2"

    reloaded = read_run_execution(plan.plan_id)
    assert reloaded.execution_id == response.execution_id


def test_execute_canonical_observations_endpoint_and_fetch_execution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))

    async def request() -> tuple[int, dict, int, dict]:
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
                        for row in _mixed_unit_observations()
                    ],
                },
            )
            planned = await client.post(
                "/runs/plan",
                json={
                    "dataset_id": created.json()["dataset_id"],
                    "workflow": "canonical_observations",
                },
            )
            plan_id = planned.json()["plan_id"]
            executed = await client.post(f"/runs/plans/{plan_id}/execute")
            fetched = await client.get(f"/runs/plans/{plan_id}/execution")
            return executed.status_code, executed.json(), fetched.status_code, fetched.json()

    execute_status, execute_payload, fetch_status, fetch_payload = asyncio.run(request())

    assert execute_status == 200
    assert execute_payload["status"] == "completed"
    assert execute_payload["row_counts"] == {"canonical_observations": 3}
    assert fetch_status == 200
    assert fetch_payload["execution_id"] == execute_payload["execution_id"]


def test_execute_plan_rejects_non_initial_workflow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))

    async def request() -> tuple[int, dict]:
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
                        _mixed_unit_observations()[0].model_dump(mode="json", exclude_none=True)
                    ],
                },
            )
            planned = await client.post(
                "/runs/plan",
                json={"dataset_id": created.json()["dataset_id"], "workflow": "fuzzy_state"},
            )
            response = await client.post(f"/runs/plans/{planned.json()['plan_id']}/execute")
            return response.status_code, response.json()

    status_code, payload = asyncio.run(request())

    assert status_code == 409
    assert payload["error"]["code"] == "unsupported_pipeline_for_dataset"
