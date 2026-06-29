# API Local Usage

This guide shows the current reproducible local API workflow. The API surface is
still intentionally small: it validates external long-form observations,
registers a dataset, plans a workflow, and executes only the initial safe
workflows:

- `canonical_observations`
- `monthly_panel`

Model workflows such as PIPE-GRU-D, Neural ODE, MIFAL-ED/T2, fuzzy state, and
counterfactual planning are not executed by the local synchronous executor yet.
They are reported as planned, blocked, or unsupported until their adapters are
integrated and reviewed.

## Install

Install the API dependency group:

```bash
poetry install --with api
```

The API writes local reproducibility artifacts under `outputs/api` by default.
For a disposable local run, set an explicit workspace:

```bash
export LENTIC_API_WORKSPACE=/tmp/lentic-pipe-api-demo
```

## Start The API

```bash
poetry run uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```

OpenAPI is available at:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

## Minimal Dataset Payload

Create a long-form dataset payload:

```bash
cat > /tmp/lentic-dataset.json <<'JSON'
{
  "dataset_name": "Lake Alpha",
  "observations": [
    {
      "source_id": "external",
      "site_id": "lake-alpha",
      "observed_at": "2024-01-05",
      "variable": "TP_ugL",
      "value": 0.03,
      "unit": "mg/L"
    },
    {
      "source_id": "external",
      "site_id": "lake-alpha",
      "observed_at": "2024-01-20",
      "variable": "TP_ugL",
      "value": 40.0,
      "unit": "ug/L"
    },
    {
      "source_id": "external",
      "site_id": "lake-alpha",
      "observed_at": "2024-02-15",
      "variable": "TN_ugL",
      "value": 0.9,
      "unit": "mg/L"
    }
  ]
}
JSON
```

## Validate

Validation is side-effect free:

```bash
curl -sS \
  -H "Content-Type: application/json" \
  --data @/tmp/lentic-dataset.json \
  http://127.0.0.1:8000/datasets/validate
```

Expected outcome for the example payload is `valid_with_warnings`, because some
rows require unit conversion.

## Register

Registering the same payload writes local dataset artifacts and returns a
deterministic `dataset_id`:

```bash
curl -sS \
  -H "Content-Type: application/json" \
  --data @/tmp/lentic-dataset.json \
  http://127.0.0.1:8000/datasets
```

Created local artifacts:

```text
$LENTIC_API_WORKSPACE/datasets/{dataset_id}/payload.json
$LENTIC_API_WORKSPACE/datasets/{dataset_id}/validation.json
$LENTIC_API_WORKSPACE/datasets/{dataset_id}/manifest.json
```

Fetch the dataset manifest:

```bash
curl -sS http://127.0.0.1:8000/datasets/{dataset_id}
```

## Plan A Run

Create a dry-run plan for the monthly panel workflow:

```bash
cat > /tmp/lentic-run-plan.json <<'JSON'
{
  "dataset_id": "{dataset_id}",
  "workflow": "monthly_panel"
}
JSON

curl -sS \
  -H "Content-Type: application/json" \
  --data @/tmp/lentic-run-plan.json \
  http://127.0.0.1:8000/runs/plan
```

The response includes a deterministic `plan_id`. The plan is persisted at:

```text
$LENTIC_API_WORKSPACE/runs/{plan_id}/plan.json
```

Fetch the persisted plan:

```bash
curl -sS http://127.0.0.1:8000/runs/plans/{plan_id}
```

## Execute Safe Workflows

Execute the persisted plan:

```bash
curl -sS -X POST http://127.0.0.1:8000/runs/plans/{plan_id}/execute
```

For `monthly_panel`, created local artifacts include:

```text
$LENTIC_API_WORKSPACE/runs/{plan_id}/canonical_observations.jsonl
$LENTIC_API_WORKSPACE/runs/{plan_id}/canonical_observations.csv
$LENTIC_API_WORKSPACE/runs/{plan_id}/monthly_panel.csv
$LENTIC_API_WORKSPACE/runs/{plan_id}/execution_manifest.json
$LENTIC_API_WORKSPACE/runs/{plan_id}/execution.json
```

Fetch the persisted execution response:

```bash
curl -sS http://127.0.0.1:8000/runs/plans/{plan_id}/execution
```

## Interpretation Limits

This local flow only canonicalizes observations and builds a long monthly panel.
It does not run alerts, forecasts, Neural ODE, MIFAL-ED/T2, or counterfactual
planning. A successful monthly panel execution means the input data were
converted and aggregated according to the current API contract; it is not a
model result or environmental decision recommendation.
