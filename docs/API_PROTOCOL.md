# Lentic API Protocol

This document defines the public API direction for `lentic-pipe`. The API is a
reproducible workflow interface for external lentic water-body datasets. It is
not only a report browser and it is not a claim that every external dataset is
sufficient for every model.

For the current local command workflow, see `docs/API_LOCAL_USAGE.md`.

## Architecture Baseline

The public API now uses the former `private/api` prototype as its architectural
baseline. That platform provides the non-scientific surface required for real
use: JWT authentication, refresh-token rotation, API keys, users, system roles,
experiment collaborators, audit logging, request IDs, timeout middleware,
PostgreSQL/Alembic persistence, Redis/Taskiq workers, job status transitions,
result storage, cancellation, CSV exports, queue metrics, and Prometheus
metrics.

The scientific code added in this repository is an extension of that platform,
not a replacement. Dataset validation, deterministic planning, safe local
execution, artifact previews, current-state fuzzy alerts, and minimal
counterfactual recomputation are exposed as scientific workflow services and as
initial adapters behind the job system.

## Purpose

The API must let a user submit data for a lake, lagoon, reservoir, or other
lentic water body and run the same reproducible processing family used in this
project when the submitted data satisfy documented preconditions.

The API must:

- validate external datasets before running scientific workflows;
- canonicalize supported variables and units;
- build auditable monthly panels and feature surfaces;
- run eligible pipelines as asynchronous jobs;
- produce reports, manifests, hashes, warnings, and downloadable artifacts;
- expose clear errors when inputs or preconditions are insufficient;
- document scientific interpretation limits in OpenAPI and reports.

## Non-Goals

The API must not silently coerce unsuitable data into apparently valid results.
It must not present counterfactual simulations as field causal effects. It must
not promise that PIPE, MIFAL-ED/T2, Neural ODE, or counterfactual planning are
universally applicable without a dataset-quality diagnostic.

## Workflow Model

Every external execution follows the same high-level lifecycle:

1. **Dataset registration or upload**
   - Store a content hash.
   - Preserve original filename, media type, source notes, and submitter
     metadata.

2. **Dataset validation**
   - Check schema, dates, variables, units, site identifiers, numeric ranges,
     and missingness.
   - Return actionable errors for invalid inputs.
   - Return warnings for technically valid but scientifically weak inputs.

3. **Canonicalization**
   - Convert supported units to canonical units.
   - Emit canonical observation rows and a validation report.
   - Preserve rejected rows with reasons when practical.

4. **Panel construction**
   - Aggregate observations into a source/site/month panel.
   - Report coverage by variable, month, site, and source.
   - Decide which downstream pipelines are eligible.

5. **Pipeline execution**
   - Run eligible workflows asynchronously.
   - Store status transitions, logs, reports, manifests, and artifacts.
   - Return `completed`, `completed_with_warnings`, `failed`, or
     `not_eligible` with explicit reasons.

6. **Result access**
   - Provide structured summaries and downloadable artifacts.
   - Keep hashes and configuration snapshots for reproducibility.

## Endpoint Families

The intended public surface is:

| Family | Purpose | Runtime |
|---|---|---|
| `GET /health/live` | Process liveness. | Synchronous |
| `GET /health/ready` | Dependency/readiness check. | Synchronous |
| `GET /version` | API and scientific workflow registry. | Synchronous |
| `GET /errors` | Machine-readable error catalog. | Synchronous |
| `/experiments` | Reproducible workspace metadata. | Synchronous |
| `GET /workspace/catalog` | Authenticated metadata catalog for visible experiments, datasets, runs, and output views. | Synchronous |
| `/datasets` | Upload, register, validate, and inspect external datasets. | Mixed |
| `/runs` | Plan, launch, and inspect processing/modeling jobs. | Mixed |
| `/runs/.../artifacts` | Query run-scoped reports, manifests, and generated files. | Synchronous |
| `/runs/.../predictions` | Query run-scoped prediction or state-score surfaces. | Synchronous |
| `/runs/.../alerts` | Query run-scoped alert views derived from available surfaces. | Synchronous |
| `/runs/.../simulations` | Run-scoped bounded simulations when preconditions hold. | Synchronous |

The current public integration preserves the production shell from the prototype
and adds a deterministic `POST /datasets/validate` endpoint for long-form
observations plus local file-backed dataset registration through
`POST /datasets` and `GET /datasets/{dataset_id}`. Registered datasets create a
payload, validation result, and manifest under the API workspace with SHA-256
hashes. The production path also exposes
`POST /experiments/{experiment_id}/datasets/validate` and
`POST /experiments/{experiment_id}/datasets/register`; registration creates an
experiment-owned SQL dataset row linked to the deterministic scientific
manifest. It also exposes `POST /runs/plan`, a synchronous dry-run planner for
registered datasets, and `GET /runs/plans/{plan_id}` for retrieving persisted
plan records. The first safe executor is exposed through
`POST /runs/plans/{plan_id}/execute` and
`GET /runs/plans/{plan_id}/execution` for `canonical_observations`,
`monthly_panel`, and deterministic expert `fuzzy_state` scoring. Experiment
storage, asynchronous job orchestration, prediction records, and simulation
records are provided by the prototype base. Generated local artifacts can be
listed, previewed, and summarized through run-scoped artifact/result endpoints.

The top-level `/datasets` and `/runs/plan` endpoints are currently retained as
a compatibility surface for reproducible local workflows. The target production
shape is now the recommended path: datasets are owned by experiments, and heavy
scientific execution runs through `/experiments/{experiment_id}/runs` and the
Taskiq worker.

## Workspace Catalog

The catalog endpoint gives clients a lightweight navigation layer over the SQL
workspace:

```http
GET /workspace/catalog
```

It is authenticated and permission-aware. Admin users see all experiments;
other users see only experiments where they are collaborators. The response is
paginated and includes, for each visible experiment, dataset/run counts, run
status counts, the latest dataset, the latest run, the latest job-backed
scientific run, and output views discoverable from persisted `Run.results`
(`artifacts`, `result_summary`, `predictions`, and `alerts`). It does not read
large model outputs or execute scientific code.

## Async Job Architecture

Experiment-scoped runs use the prototype lifecycle:

```http
POST /experiments/{experiment_id}/runs
GET /experiments/{experiment_id}/runs
GET /runs/{run_id}
GET /runs/{run_id}/results
POST /runs/{run_id}/cancel
POST /experiments/{experiment_id}/runs/cancel-all
```

Runs are persisted in SQL with `pending`, `running`, `completed`, `failed`, and
`cancelled` states. `POST /experiments/{experiment_id}/runs` returns
`202 Accepted` and a `task_id`; the Taskiq worker transitions the run and writes
results or an explicit error message.

The first scientific adapter is configured through `Run.config`:

```json
{
  "experiment_dataset_id": "0b8f6b6b-2f1c-4f3a-94af-7ad6d5c73ed2",
  "workflow": "canonical_observations",
  "parameters": {}
}
```

When `experiment_dataset_id` and `workflow` are present, the worker verifies the
dataset row belongs to the run's experiment, resolves it to the linked
scientific `dataset_id`, and dispatches through the registered job-backed
scientific adapter interface. The current interface is
`job_adapter_interface_v1`, exposed by `/version` under `job_adapters`. The
first registered adapter is `local_scientific_workflow_v0`, which executes
`canonical_observations`, `monthly_panel`, and deterministic expert
`fuzzy_state` by reusing the reviewed planner/executor path. The first heavy
adapter is `pipe_grud_reference_workflow_v0`, which supports `pipe_grud` with
six explicit modes: `parameters.execution_mode="preflight"` diagnoses whether
an uploaded external dataset has the minimum temporal coverage, signal
variables, planner readiness, and sequence-surface prerequisites for future
PIPE-GRU-D inference; `parameters.execution_mode="build_sequences"` builds
external expert-fuzzy PIPE state and sequence artifacts with the reviewed PIPE
schema, plus eligible inference origins;
`parameters.execution_mode="build_adaptive_surface"` applies the reviewed
adaptive ANFIS transform and builds schema-compatible adaptive PIPE state and
sequence artifacts;
`parameters.execution_mode="infer_expert_surface"` runs diagnostic PIPE-GRU-D
rollouts over that expert-fuzzy surface;
`parameters.execution_mode="infer_reference_profile"` applies the reviewed
adaptive transform, frozen adaptive WQP-focused PIPE-GRU-D model, rollout bloom
calibrators, and selected 2B policy thresholds to the submitted dataset; and
`parameters.execution_mode="artifact_reference"` validates and reports the
reviewed adaptive PIPE-GRU-D artifact profile.
`build_sequences` and `infer_expert_surface` do not match the adaptive
WQP-focused reference surface. `build_adaptive_surface` is mechanically
compatible with the reviewed adaptive profile but does not apply reference bloom
calibrators or 2B policy thresholds. `infer_reference_profile` is the calibrated
reference-profile inference path; it still reports external-domain warnings
because predictive skill on a new water body is not guaranteed.
Adapters persist the plan,
execution, artifact list, result summary, and row-count metrics in
`Run.results`. Direct `dataset_id` configs remain supported only as a
compatibility path for local checks. Without a usable dataset/workflow pair, the
job system still works but returns an explicit placeholder result. Workflows
without a registered adapter fail with a clear error instead of silently
executing partial scientific logic.

For job-backed scientific runs, clients should prefer the run-id output views:

```http
GET /runs/{run_id}/artifacts
GET /runs/{run_id}/artifacts/{artifact_name}/preview
GET /runs/{run_id}/results/summary
GET /runs/{run_id}/predictions
GET /runs/{run_id}/alerts
```

These endpoints enforce normal run access permissions, resolve the internal
`plan_id` from `Run.results`, and reuse the same artifact, summary, prediction,
and alert readers as the plan-scoped compatibility endpoints. They fail with a
clear error if a run has not completed or if its results do not come from a
job-backed scientific workflow.

Simulation jobs use the prototype simulation lifecycle:

```http
POST /simulations
GET /simulations
GET /simulations/{simulation_id}
POST /simulations/{simulation_id}/cancel
POST /simulations/cancel-all
```

The first wired simulation scenario is:

```json
{
  "type": "current_state_counterfactual",
  "plan_id": "plan_...",
  "interventions": [
    {"variable": "TP_ugL", "operation": "scale", "value": 0.8}
  ]
}
```

That scenario executes the minimal expert-fuzzy current-state counterfactual
adapter behind the asynchronous simulation job. Temporal rollout simulations
remain placeholders until PIPE-GRU-D or Neural ODE adapters are connected.

## Dry-Run Planning

`POST /runs/plan` accepts a registered `dataset_id`, a workflow name, and
optional parameters. It does not execute scientific code. It returns:

- a deterministic `plan_id`;
- `ready`, `not_eligible`, or `blocked` status;
- dataset validation outcome;
- actionable blockers and warnings;
- required input/dependency artifacts;
- planned output artifacts;
- ordered workflow steps.

The plan is persisted as `outputs/api/runs/{plan_id}/plan.json` or under the
configured `LENTIC_API_WORKSPACE`. `GET /runs/plans/{plan_id}` returns the
stored plan. Repeating the same dataset/workflow/parameter request is
idempotent because `plan_id` is deterministic.

`ready` means the dataset passes current eligibility checks and the local
dependencies known to the planner are available. It does not mean an async
worker has executed the workflow. `not_eligible` is used for scientific/data
precondition failures. `blocked` is used for missing upstream artifacts,
invalid dataset records, or dependency gaps.

## Safe Synchronous Execution

`POST /runs/plans/{plan_id}/execute` executes only plans whose workflow is:

- `canonical_observations`;
- `monthly_panel`;
- `fuzzy_state`.

The executor reads the persisted dataset payload, applies declared unit
conversions from `configs/variables.yaml`, writes canonical long-form rows, and
for `monthly_panel` aggregates valid observations by source/site/month/variable
with the declared median aggregation. For `fuzzy_state`, it pivots the monthly
panel into the reviewed wide panel shape, computes derived `TN_TP_ratio` and
current chlorophyll-a risk when possible, then calls
`src.fuzzy.expert.build_expert_state` with frozen IRC weights from
`reports/anfis/fuzzy_manifest.json`. This is deterministic expert fuzzy state
scoring; it does not retrain adaptive ANFIS and it does not run temporal alert
models. It writes lightweight local artifacts:

| Workflow | Outputs |
|---|---|
| `canonical_observations` | `canonical_observations.jsonl`, `canonical_observations.csv`, `execution_manifest.json` |
| `monthly_panel` | canonical outputs plus `monthly_panel.csv` |
| `fuzzy_state` | canonical and monthly outputs plus `monthly_panel_wide.csv`, `fuzzy_state_scores.csv`, `fuzzy_state_trace.csv`, `fuzzy_state_manifest.json` |

Execution artifacts are stored under `outputs/api/runs/{plan_id}` or
`LENTIC_API_WORKSPACE`. `GET /runs/plans/{plan_id}/execution` retrieves the
persisted execution response.

Temporal/model workflows remain deliberately non-executable in the synchronous
local executor. PIPE-GRU-D is reachable through the asynchronous job adapter for
preflight diagnostics, external sequence artifact builds, adaptive-surface
builds, diagnostic expert-surface rollouts, calibrated adaptive
reference-profile inference, and reviewed artifact-reference reporting.
Neural ODE, MIFAL-ED/T2, and
counterfactual planning must remain planned-only until their adapters, artifact
dependencies, and diagnostics are wired and reviewed.

## Artifact And Result Access

Completed local executions expose generated outputs through run-scoped
endpoints:

```http
GET /runs/plans/{plan_id}/artifacts
GET /runs/plans/{plan_id}/artifacts/{artifact_name}/preview
GET /runs/plans/{plan_id}/results/summary
```

Experiment-scoped async scientific runs expose equivalent views by `run_id`:

```http
GET /runs/{run_id}/artifacts
GET /runs/{run_id}/artifacts/{artifact_name}/preview
GET /runs/{run_id}/results/summary
```

The artifact list is derived from the persisted execution record and includes
artifact names, relative URIs, bytes, and SHA-256 hashes. The preview endpoint
only reads artifacts already declared by the execution response, and only for
bounded text-safe formats: CSV, JSON, JSONL, Markdown, plain text, or logs. CSV
and JSONL previews return rows and columns; JSON previews return the parsed
payload; text previews return the first bounded lines.

The result summary endpoint reports structured summaries for known local
outputs, currently canonical observations, monthly panels, and expert fuzzy
state scores. It is a convenience view over generated artifacts, not a new
scientific computation.

## Prediction And Alert Access

Completed local `fuzzy_state` executions expose a first prediction/alert query
surface:

```http
GET /runs/plans/{plan_id}/predictions
GET /runs/plans/{plan_id}/alerts
```

Async scientific runs expose equivalent views by `run_id`:

```http
GET /runs/{run_id}/predictions
GET /runs/{run_id}/alerts
```

For `fuzzy_state`, predictions are current-month expert fuzzy state scores
derived from `fuzzy_state_scores.csv`. The current surface emits `irc1` as an
expert composite state-risk score with `horizon_months = 0`. It is not a
temporal forecast and it is not a calibrated probability.

Alerts are thresholded current-state risk indicators derived from the same
expert fuzzy score and the frozen threshold recorded in
`fuzzy_state_manifest.json` / `reports/anfis/fuzzy_manifest.json`. They are not
official advisories and they are not PIPE-GRU-D or Neural ODE early-warning
alerts.

Completed `pipe_grud` runs produced with
`parameters.execution_mode="infer_reference_profile"` expose temporal rollout
records through the same query endpoints. `/predictions` returns two target
surfaces per rollout horizon when available: `irc_alert` with
`score_kind="model_probability"` from the rollout alert probability, and
`bloom_h` with `score_kind="calibrated_probability"` from the reviewed rollout
bloom calibrator. `/alerts` returns horizon- and event-specific 2B policy
threshold decisions from `pipe_grud_reference_alerts.csv`; the per-record
threshold is authoritative. These outputs are model-derived early-warning
indicators, not official advisories or causal field evidence.

## Minimal Counterfactual Simulation

Completed local `fuzzy_state` executions expose a minimal current-state
counterfactual endpoint:

```http
POST /runs/plans/{plan_id}/simulations/counterfactual
```

The request declares simple interventions over canonical variables, using
`scale`, `add`, or `set`. The endpoint applies those interventions to the
generated `monthly_panel_wide.csv`, recomputes derived `TN_TP_ratio` and
chlorophyll-a risk, reruns deterministic expert fuzzy scoring, and compares the
simulated `irc1` state-risk score against the baseline `fuzzy_state_scores.csv`.
The response includes score deltas, baseline/simulated alert flags, alert
change labels, a deterministic `simulation_id`, and a lightweight JSON result
artifact under the run workspace.

This is not causal field evidence, temporal planning, or a PIPE-GRU-D/Neural
ODE rollout. It is a bounded "what changes in the current expert fuzzy state
score if these input assumptions are applied?" simulation.

## Pipeline Eligibility

Eligibility is a first-class API result. The API should report why a workflow is
available or unavailable for a dataset.

| Workflow | Minimum requirement |
|---|---|
| Dataset validation | Required schema fields and supported date parsing. |
| Canonical observations | Supported canonical variables and units. |
| Monthly panel | At least one valid source/site/month observation after QC. |
| Fuzzy/ANFIS state scoring | Sufficient canonical variables for at least one state module. |
| PIPE-GRU-D rollouts | A compatible temporal panel and model artifact availability. |
| Neural ODE | A compatible historical state surface and model artifact availability. |
| MIFAL-ED/T2 | Observable-minimal variables required by the MIFAL adapter. |
| Controlled degradation | A completed baseline workflow output to perturb or recompute. |
| Counterfactual planning | A completed temporal state/alert surface and declared intervention proxies. |

Eligibility is not the same as executable adapter availability. `/version`
reports currently registered job adapters and their executable workflows. As of
`job_adapter_interface_v1`, executable job workflows are
`canonical_observations`, `monthly_panel`, `fuzzy_state`, and `pipe_grud` in
preflight/sequence-build/adaptive-surface/expert-surface-inference/
reference-profile-inference/artifact-reference modes.
Neural ODE, MIFAL-ED/T2, and
counterfactual planning remain planned until their job adapters are reviewed and
connected.

## Status Semantics

Jobs should use these status values:

| Status | Meaning |
|---|---|
| `pending` | Accepted but not started. |
| `running` | Worker is executing the job. |
| `completed` | Finished without warnings that affect interpretation. |
| `completed_with_warnings` | Finished, but output carries important coverage or scientific limitations. |
| `not_eligible` | Dataset is valid, but cannot support the requested workflow. |
| `failed` | Technical or unexpected execution failure. |
| `cancelled` | User or system cancelled the job. |

## Reproducibility Requirements

Every non-trivial job must emit:

- input dataset identifier and SHA-256 hash;
- API version and code version if available;
- config snapshot;
- command or internal workflow identifier;
- start and completion timestamps;
- status and warnings;
- manifest of generated artifacts;
- report path or URI;
- failure code and actionable detail when not successful.

## Scientific Interpretation Guardrails

API documentation and responses must distinguish:

- invalid input data;
- valid but insufficient data;
- completed workflow with weak coverage;
- negative scientific result;
- technical failure.

Counterfactual outputs are simulated model comparisons, not causal field
intervention estimates. Model outputs are conditional on the submitted data,
the canonicalization rules, and the eligibility surface used by the workflow.
