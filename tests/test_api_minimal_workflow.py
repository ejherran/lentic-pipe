import asyncio
import csv
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from src.api.main import create_app


def _payload() -> dict[str, object]:
    return {
        "dataset_name": "Lake Alpha",
        "observations": [
            {
                "source_id": "external",
                "site_id": "lake-alpha",
                "observed_at": "2024-01-05",
                "variable": "TP_ugL",
                "value": 0.03,
                "unit": "mg/L",
            },
            {
                "source_id": "external",
                "site_id": "lake-alpha",
                "observed_at": "2024-01-20",
                "variable": "TP_ugL",
                "value": 40.0,
                "unit": "ug/L",
            },
            {
                "source_id": "external",
                "site_id": "lake-alpha",
                "observed_at": "2024-02-15",
                "variable": "TN_ugL",
                "value": 0.9,
                "unit": "mg/L",
            },
        ],
    }


def test_api_minimal_monthly_panel_workflow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))

    async def request() -> dict[str, dict]:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            health = await client.get("/health/live")
            validated = await client.post("/datasets/validate", json=_payload())
            registered = await client.post("/datasets", json=_payload())
            dataset_id = registered.json()["dataset_id"]
            fetched_dataset = await client.get(f"/datasets/{dataset_id}")
            planned = await client.post(
                "/runs/plan",
                json={"dataset_id": dataset_id, "workflow": "monthly_panel"},
            )
            plan_id = planned.json()["plan_id"]
            fetched_plan = await client.get(f"/runs/plans/{plan_id}")
            executed = await client.post(f"/runs/plans/{plan_id}/execute")
            fetched_execution = await client.get(f"/runs/plans/{plan_id}/execution")
            return {
                "health": {"status_code": health.status_code, "payload": health.json()},
                "validated": {"status_code": validated.status_code, "payload": validated.json()},
                "registered": {"status_code": registered.status_code, "payload": registered.json()},
                "fetched_dataset": {"status_code": fetched_dataset.status_code, "payload": fetched_dataset.json()},
                "planned": {"status_code": planned.status_code, "payload": planned.json()},
                "fetched_plan": {"status_code": fetched_plan.status_code, "payload": fetched_plan.json()},
                "executed": {"status_code": executed.status_code, "payload": executed.json()},
                "fetched_execution": {"status_code": fetched_execution.status_code, "payload": fetched_execution.json()},
            }

    responses = asyncio.run(request())

    assert responses["health"]["status_code"] == 200
    assert responses["validated"]["payload"]["outcome"] == "valid_with_warnings"
    assert responses["registered"]["status_code"] == 201
    assert responses["fetched_dataset"]["payload"]["dataset_id"] == responses["registered"]["payload"]["dataset_id"]
    assert responses["planned"]["payload"]["status"] == "ready"
    assert responses["fetched_plan"]["payload"]["plan_id"] == responses["planned"]["payload"]["plan_id"]
    assert responses["executed"]["payload"]["status"] == "completed"
    assert responses["executed"]["payload"]["row_counts"] == {
        "canonical_observations": 3,
        "monthly_panel": 2,
    }
    assert responses["fetched_execution"]["payload"]["execution_id"] == responses["executed"]["payload"]["execution_id"]

    plan_id = responses["planned"]["payload"]["plan_id"]
    run_dir = tmp_path / "runs" / plan_id
    assert (run_dir / "plan.json").exists()
    assert (run_dir / "canonical_observations.jsonl").exists()
    assert (run_dir / "canonical_observations.csv").exists()
    assert (run_dir / "monthly_panel.csv").exists()
    assert (run_dir / "execution_manifest.json").exists()
    assert (run_dir / "execution.json").exists()

    with (run_dir / "monthly_panel.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    tp_row = next(row for row in rows if row["variable"] == "TP_ugL")
    assert float(tp_row["value"]) == 35.0
    assert tp_row["observation_count"] == "2"
