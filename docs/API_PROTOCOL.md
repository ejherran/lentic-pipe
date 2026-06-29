# Lentic API Protocol

This document defines the public API direction for `lentic-pipe`. The API is a
reproducible workflow interface for external lentic water-body datasets. It is
not only a report browser and it is not a claim that every external dataset is
sufficient for every model.

For the current local command workflow, see `docs/API_LOCAL_USAGE.md`.

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
| `/datasets` | Upload, register, validate, and inspect external datasets. | Mixed |
| `/runs` | Plan, launch, and inspect processing/modeling jobs. | Mixed |
| `/artifacts` | Query reports, manifests, and generated files. | Synchronous |
| `/predictions` | Optional point/batch inference on eligible surfaces. | Mixed |
| `/simulations` | Counterfactual or rollout jobs when preconditions hold. | Asynchronous |

The first public integration implements the system endpoints, the contracts, a
deterministic `POST /datasets/validate` endpoint for long-form observations,
and local file-backed dataset registration through `POST /datasets` and
`GET /datasets/{dataset_id}`. Registered datasets create a payload,
validation result, and manifest under the API workspace with SHA-256 hashes.
It also exposes `POST /runs/plan`, a synchronous dry-run planner for registered
datasets, and `GET /runs/plans/{plan_id}` for retrieving persisted plan
records. The first safe executor is exposed through
`POST /runs/plans/{plan_id}/execute` and
`GET /runs/plans/{plan_id}/execution` for `canonical_observations` and
`monthly_panel` only. Experiment storage, asynchronous job orchestration,
model execution, prediction, and simulation routers are added in later phases.

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
- `monthly_panel`.

The executor reads the persisted dataset payload, applies declared unit
conversions from `configs/variables.yaml`, writes canonical long-form rows, and
for `monthly_panel` aggregates valid observations by source/site/month/variable
with the declared median aggregation. It writes lightweight local artifacts:

| Workflow | Outputs |
|---|---|
| `canonical_observations` | `canonical_observations.jsonl`, `canonical_observations.csv`, `execution_manifest.json` |
| `monthly_panel` | canonical outputs plus `monthly_panel.csv` |

Execution artifacts are stored under `outputs/api/runs/{plan_id}` or
`LENTIC_API_WORKSPACE`. `GET /runs/plans/{plan_id}/execution` retrieves the
persisted execution response.

Model workflows remain deliberately non-executable in this layer. PIPE-GRU-D,
Neural ODE, MIFAL-ED/T2, and counterfactual planning must remain planned-only
until their adapters, artifact dependencies, and diagnostics are wired and
reviewed.

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
