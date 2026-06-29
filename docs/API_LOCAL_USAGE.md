# API Local Usage

This guide shows the current reproducible local API workflow. The API now uses
the former prototype platform as its base: authentication, users, experiments,
collaborators, API keys, SQL persistence, Taskiq/Redis jobs, cancellation, and
metrics are part of the public `src/api` tree. The scientific layer currently
validates external long-form observations, registers a dataset, plans a
workflow, and executes only the initial safe workflows:

- `canonical_observations`
- `monthly_panel`
- `fuzzy_state`

Temporal/model workflows such as PIPE-GRU-D, Neural ODE, MIFAL-ED/T2, and
counterfactual planning are not executed by the local synchronous executor yet.
They are reported as planned, blocked, or unsupported until their adapters are
integrated and reviewed.

## Install

Install the API dependency group:

```bash
poetry install --with api
```

For the full production-like shell, start PostgreSQL and Redis with the checked
in Compose file and configure `.env` from `.env.example`:

```bash
cp .env.example .env
docker compose up -d
poetry run alembic upgrade head
```

For lightweight local scientific endpoint tests, no external infrastructure is
required; the default development settings do not run strict readiness checks.
Set `STRICT_READINESS_CHECKS=true` when deployment probes must verify DB and
Redis connectivity.

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

To run asynchronous jobs, start a worker in a second terminal:

```bash
poetry run taskiq worker \
  src.api.tasks.broker:broker \
  src.api.tasks.training \
  src.api.tasks.simulation
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

For `fuzzy_state`, the executor also writes:

```text
$LENTIC_API_WORKSPACE/runs/{plan_id}/monthly_panel_wide.csv
$LENTIC_API_WORKSPACE/runs/{plan_id}/fuzzy_state_scores.csv
$LENTIC_API_WORKSPACE/runs/{plan_id}/fuzzy_state_trace.csv
$LENTIC_API_WORKSPACE/runs/{plan_id}/fuzzy_state_manifest.json
```

Fetch the persisted execution response:

```bash
curl -sS http://127.0.0.1:8000/runs/plans/{plan_id}/execution
```

## Register Inside An Experiment

The compatibility `/datasets` flow is useful for local reproducibility. The
experiment-owned path validates the same payload and also creates a SQL dataset
row that can be used by async jobs:

```bash
curl -sS \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  --data @/tmp/lentic-dataset.json \
  http://127.0.0.1:8000/experiments/{experiment_id}/datasets/register
```

The response contains:

```json
{
  "dataset": {
    "id": "{experiment_dataset_id}",
    "experiment_id": "{experiment_id}",
    "file_path": "datasets/{dataset_id}/manifest.json",
    "meta": {
      "scientific_dataset_id": "{dataset_id}",
      "content_sha256": "..."
    }
  },
  "scientific_dataset": {
    "dataset_id": "{dataset_id}",
    "artifacts": []
  }
}
```

Use `dataset.id` as `config.experiment_dataset_id` for experiment-scoped jobs.
Use `scientific_dataset.dataset_id` only for the compatibility `/runs/plan`
surface.

## Execute Through The Job System

The compatibility endpoints above are useful for local reproducibility checks.
The production architecture should submit heavy work through experiment-scoped
jobs. After registering or logging in a user, creating an experiment, and
registering the scientific dataset inside it, launch a run with a scientific
workflow config:

```json
{
  "name": "lake-alpha-canonical",
  "model_type": "PIPE_GRUD",
  "config": {
    "experiment_dataset_id": "{experiment_dataset_id}",
    "workflow": "canonical_observations",
    "parameters": {}
  }
}
```

Submit it:

```bash
curl -sS \
  -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  --data @/tmp/lentic-run-job.json \
  http://127.0.0.1:8000/experiments/{experiment_id}/runs
```

The API returns `202 Accepted` with `status: pending` and a Taskiq `task_id`.
The worker transitions the run through `running` to `completed` or `failed`.
If the experiment dataset row is missing, belongs to another experiment, or is
metadata-only, the run fails with an explicit `error_message` instead of
silently falling back to another dataset.
Fetch status and results with:

```bash
curl -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://127.0.0.1:8000/runs/{run_id}

curl -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://127.0.0.1:8000/runs/{run_id}/results
```

The first wired run adapter executes the same deterministic planner/executor
used by `POST /runs/plans/{plan_id}/execute`. Model training, temporal
rollouts, Neural ODE, MIFAL-ED/T2, and full counterfactual planning remain
explicit placeholders until their reviewed adapters are connected.

## Inspect Artifacts And Results

List generated artifacts:

```bash
curl -sS http://127.0.0.1:8000/runs/plans/{plan_id}/artifacts
```

Preview a bounded number of CSV or JSONL rows:

```bash
curl -sS \
  "http://127.0.0.1:8000/runs/plans/{plan_id}/artifacts/monthly_panel.csv/preview?limit=5"
```

For `fuzzy_state`, preview expert fuzzy scores:

```bash
curl -sS \
  "http://127.0.0.1:8000/runs/plans/{plan_id}/artifacts/fuzzy_state_scores.csv/preview?limit=5"
```

Fetch a structured result summary:

```bash
curl -sS http://127.0.0.1:8000/runs/plans/{plan_id}/results/summary
```

Artifact previews are bounded inspection views. The execution response and
artifact list remain the reproducibility sources for full artifact names, URIs,
hashes, and byte sizes.

## Query Predictions And Alerts

For `fuzzy_state`, query the current expert fuzzy state-score surface:

```bash
curl -sS \
  "http://127.0.0.1:8000/runs/plans/{plan_id}/predictions?limit=20"
```

Query thresholded current-state risk indicators:

```bash
curl -sS \
  "http://127.0.0.1:8000/runs/plans/{plan_id}/alerts?limit=20"
```

Return only rows that cross the frozen threshold:

```bash
curl -sS \
  "http://127.0.0.1:8000/runs/plans/{plan_id}/alerts?only_alerts=true"
```

These endpoints currently expose `horizon_months = 0` expert fuzzy state
scores. They do not run model inference, temporal forecasts, or official alert
issuance.

## Run A Minimal Counterfactual Simulation

For a completed `fuzzy_state` run, declare current-state input changes and
recompute the expert fuzzy state score:

```bash
cat > /tmp/lentic-counterfactual.json <<'JSON'
{
  "scenario_name": "nutrient-and-bloom-pressure-reduction",
  "interventions": [
    {"variable": "TP_ugL", "operation": "scale", "value": 0.8},
    {"variable": "TN_ugL", "operation": "scale", "value": 0.8},
    {"variable": "chlorophyll_a_ugL", "operation": "scale", "value": 0.7}
  ],
  "only_changed_alerts": false,
  "limit": 20
}
JSON

curl -sS \
  -H "Content-Type: application/json" \
  --data @/tmp/lentic-counterfactual.json \
  http://127.0.0.1:8000/runs/plans/{plan_id}/simulations/counterfactual
```

The response compares baseline and simulated current-state `irc1` scores and
alert flags. The simulation writes a lightweight JSON result under the run
workspace. This is a sensitivity calculation over declared assumptions, not a
causal estimate or temporal intervention plan.

## Interpretation Limits

This local flow canonicalizes observations, builds a long monthly panel, and
can compute deterministic expert fuzzy state scores, thresholded current-state
risk indicators, and bounded current-state counterfactual sensitivity
simulations. It does not run temporal forecasts, adaptive ANFIS retraining,
Neural ODE, MIFAL-ED/T2, or full counterfactual planning. A successful
`fuzzy_state` execution means the input data were converted, aggregated, and
scored by the current expert fuzzy rules and frozen IRC weights in
`reports/anfis/fuzzy_manifest.json`; it is not a temporal model result or
environmental decision recommendation.
