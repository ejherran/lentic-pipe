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


def test_api_lists_previews_and_summarizes_run_artifacts(
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
            executed = await client.post(f"/runs/plans/{plan_id}/execute")
            listed = await client.get(f"/runs/plans/{plan_id}/artifacts")
            csv_preview = await client.get(
                f"/runs/plans/{plan_id}/artifacts/fuzzy_state_scores.csv/preview",
                params={"limit": 1},
            )
            json_preview = await client.get(
                f"/runs/plans/{plan_id}/artifacts/fuzzy_state_manifest.json/preview"
            )
            summary = await client.get(f"/runs/plans/{plan_id}/results/summary")
            missing = await client.get(
                f"/runs/plans/{plan_id}/artifacts/not_real.csv/preview"
            )
            return {
                "executed": {"status_code": executed.status_code, "payload": executed.json()},
                "listed": {"status_code": listed.status_code, "payload": listed.json()},
                "csv_preview": {"status_code": csv_preview.status_code, "payload": csv_preview.json()},
                "json_preview": {"status_code": json_preview.status_code, "payload": json_preview.json()},
                "summary": {"status_code": summary.status_code, "payload": summary.json()},
                "missing": {"status_code": missing.status_code, "payload": missing.json()},
            }

    responses = asyncio.run(request())

    assert responses["executed"]["status_code"] == 200
    assert responses["listed"]["status_code"] == 200
    artifacts = {artifact["name"] for artifact in responses["listed"]["payload"]["artifacts"]}
    assert {
        "monthly_panel_wide.csv",
        "fuzzy_state_scores.csv",
        "fuzzy_state_trace.csv",
        "fuzzy_state_manifest.json",
    }.issubset(artifacts)

    csv_preview = responses["csv_preview"]["payload"]
    assert csv_preview["preview_format"] == "csv"
    assert csv_preview["truncated"] is True
    assert "irc1" in csv_preview["columns"]
    assert len(csv_preview["rows"]) == 1

    json_preview = responses["json_preview"]["payload"]
    assert json_preview["preview_format"] == "json"
    assert json_preview["content"]["weights_source"] == "reports/anfis/fuzzy_manifest.json"
    assert json_preview["content"]["irc_weights"] == {"alpha": 0.5, "beta": 0.5, "gamma": 2.0}

    summary = responses["summary"]["payload"]
    assert summary["workflow"] == "fuzzy_state"
    assert summary["summaries"]["monthly_panel"]["rows"] == 16
    assert summary["summaries"]["fuzzy_state"]["rows"] == 2
    assert summary["summaries"]["fuzzy_state"]["trophic_state_counts"] == {
        "eutrophic": 1,
        "oligotrophic": 1,
    }
    assert summary["summaries"]["fuzzy_state"]["score_ranges"]["irc1"]["max"] > 0

    assert responses["missing"]["status_code"] == 404
    assert responses["missing"]["payload"]["error"]["code"] == "resource_not_found"
