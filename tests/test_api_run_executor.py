import asyncio
import csv
import json
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


def _fuzzy_observations() -> list[DatasetObservation]:
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
    return [
        DatasetObservation(
            source_id="external",
            site_id="lake-alpha",
            observed_at=f"{year_month}-15",
            variable=variable,
            value=value,
            unit=unit,
            qc_flag="ok",
        )
        for year_month, variables in values_by_month.items()
        for variable, (value, unit) in variables.items()
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


def test_execute_fuzzy_state_writes_expert_state_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    dataset = register_dataset_request(
        DatasetValidationRequest(
            dataset_name="Lake Alpha",
            observations=_fuzzy_observations(),
        )
    )
    plan = save_run_plan(
        plan_run_request(
            RunPlanRequest(dataset_id=dataset.dataset_id, workflow="fuzzy_state")
        )
    )

    response = execute_run_plan(plan.plan_id)

    assert response.status == "completed"
    assert response.row_counts == {
        "canonical_observations": 16,
        "monthly_panel": 16,
        "monthly_panel_wide": 2,
        "fuzzy_state": 2,
        "fuzzy_trace": 2,
    }
    run_dir = tmp_path / "runs" / plan.plan_id
    assert (run_dir / "monthly_panel_wide.csv").exists()
    assert (run_dir / "fuzzy_state_scores.csv").exists()
    assert (run_dir / "fuzzy_state_trace.csv").exists()
    assert (run_dir / "fuzzy_state_manifest.json").exists()

    manifest = json.loads((run_dir / "fuzzy_state_manifest.json").read_text(encoding="utf-8"))
    assert manifest["weights_source"] == "reports/anfis/fuzzy_manifest.json"
    assert manifest["irc_weights"] == {"alpha": 0.5, "beta": 0.5, "gamma": 2.0}

    with (run_dir / "fuzzy_state_scores.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    low = next(row for row in rows if row["year_month"] == "2024-01")
    high = next(row for row in rows if row["year_month"] == "2024-02")
    assert float(high["yN"]) > float(low["yN"])
    assert float(high["yF"]) < float(low["yF"])
    assert float(high["yT"]) > float(low["yT"])
    assert float(high["irc1"]) > float(low["irc1"])
    assert high["state_trophic_expert"] == "eutrophic"


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


def test_execute_plan_rejects_model_workflow(tmp_path: Path, monkeypatch) -> None:
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
                json={"dataset_id": created.json()["dataset_id"], "workflow": "pipe_grud"},
            )
            response = await client.post(f"/runs/plans/{planned.json()['plan_id']}/execute")
            return response.status_code, response.json()

    status_code, payload = asyncio.run(request())

    assert status_code == 409
    assert payload["error"]["code"] == "unsupported_pipeline_for_dataset"
