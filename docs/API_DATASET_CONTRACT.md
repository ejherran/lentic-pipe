# API Dataset Contract

This document defines the input contract for external datasets submitted to the
`lentic-pipe` API.

## Preferred Input Shape

The preferred upload shape is a long table with one row per observation:

| Column | Required | Description |
|---|---:|---|
| `source_id` | yes | User-declared source or provider identifier. |
| `site_id` | yes | Stable identifier for the sampled water body or station. |
| `observed_at` | yes | Observation timestamp or date. ISO-8601 is preferred. |
| `variable` | yes | Canonical variable name or declared source variable. |
| `value` | yes | Numeric observed value before unit conversion. |
| `unit` | yes | Unit string for `value`. |
| `latitude` | no | Decimal degrees, if available. |
| `longitude` | no | Decimal degrees, if available. |
| `depth_m` | no | Sampling depth in meters, if available. |
| `qc_flag` | no | Source quality flag. Missing values are treated as unreviewed. |
| `method` | no | Lab, sensor, or processing method. |
| `notes` | no | Human-readable source notes. |

Wide tables may be accepted later through an explicit mapping object. The first
validation layer should prefer the long form because it preserves variable and
unit provenance row by row.

## Canonical Variables

The API recognizes the canonical variables maintained in
`configs/variables.yaml`.

| Canonical variable | Canonical unit | Role |
|---|---|---|
| `chlorophyll_a_ugL` | `ug/L` | Target, memory, trophic proxy |
| `TP_ugL` | `ug/L` | Nutrient pressure |
| `TN_ugL` | `ug/L` | Nutrient pressure |
| `DO_mgL` | `mg/L` | Physicochemical condition |
| `pH` | `dimensionless` | Physicochemical condition |
| `turbidity_NTU` | `NTU` | Light availability |
| `temperature_C` | `deg C` | Thermal-biological favorability |
| `secchi_depth_m` | `m` | Light availability |

## Accepted Units

Accepted units and conversions are defined by `configs/variables.yaml`.
Unsupported units must fail validation with `unsupported_unit`; they must not
be guessed.

Examples:

| Variable | Accepted examples |
|---|---|
| `chlorophyll_a_ugL` | `ug/L`, `ug/l`, `mg/L`, `mg/l`, `mg/m3` |
| `TP_ugL` | `ug/L`, `ug/l`, `mg/L`, `mg/l`, `ppb`, `ppm` |
| `TN_ugL` | `ug/L`, `ug/l`, `mg/L`, `mg/l`, `ppb`, `ppm` |
| `DO_mgL` | `mg/L`, `mg/l`, `ppm` |
| `pH` | `dimensionless`, `nu`, `standard units` |
| `turbidity_NTU` | `NTU`, `FNU`, `FNRU`, `FTU`, `JCU`, `JTU` |
| `temperature_C` | `deg C`, `C`, `deg F` |
| `secchi_depth_m` | `m`, `ft`, `in` |

## Temporal Contract

The API builds monthly panels. At minimum, `observed_at` must be parseable into
a calendar month. Later workflow stages may require multiple months per site,
contiguous windows, or origin months that align with model horizons.

The API must report:

- parsed month count;
- rejected date rows;
- number of sites;
- number of site-months;
- monthly coverage by canonical variable.

## Validation Levels

Validation should produce a structured report with these levels:

| Level | Meaning |
|---|---|
| `schema` | Required columns, parseable dates, numeric values, accepted variable names. |
| `unit` | Supported units and deterministic conversions. |
| `range` | Plausible and impossible value checks. |
| `panel` | Whether monthly aggregation can produce usable site-month rows. |
| `workflow` | Which scientific workflows are eligible or ineligible. |

## Minimum Outcomes

A dataset validation request returns one of:

| Outcome | Meaning |
|---|---|
| `valid` | Dataset satisfies schema and can be canonicalized. |
| `valid_with_warnings` | Dataset is usable but carries coverage/range/QC warnings. |
| `invalid` | Dataset violates schema, unit, date, or numeric constraints. |
| `not_eligible` | Dataset is valid but insufficient for the requested workflow. |

## Initial Endpoints

The initial API scaffold exposes side-effect-free validation:

```http
POST /datasets/validate
```

The endpoint accepts JSON with this shape:

```json
{
  "dataset_name": "optional name",
  "requested_workflow": "pipe_grud",
  "observations": [
    {
      "source_id": "external",
      "site_id": "lake-alpha",
      "observed_at": "2024-01-15",
      "variable": "TP_ugL",
      "value": 35.0,
      "unit": "ug/L"
    }
  ]
}
```

The API also exposes local persistent registration:

```http
POST /datasets
GET /datasets/{dataset_id}
```

`POST /datasets` accepts the same body as `POST /datasets/validate`, runs the
same deterministic validation logic, and writes three reproducibility artifacts
under the configured API workspace:

| Artifact | Meaning |
|---|---|
| `payload.json` | Normalized request payload. |
| `validation.json` | Validation and workflow eligibility result. |
| `manifest.json` | Dataset id, content hash, validation result, and artifact hashes. |

The `dataset_id` is derived from a SHA-256 hash of the normalized payload, so
submitting the same payload is idempotent. This local file-backed repository is
the first storage layer; later phases can replace it with Postgres/object
storage while preserving the public response semantics.

Registered datasets can be passed to the dry-run planner:

```http
POST /runs/plan
GET /runs/plans/{plan_id}
POST /runs/plans/{plan_id}/execute
GET /runs/plans/{plan_id}/execution
GET /runs/plans/{plan_id}/artifacts
GET /runs/plans/{plan_id}/artifacts/{artifact_name}/preview
GET /runs/plans/{plan_id}/results/summary
GET /runs/plans/{plan_id}/predictions
GET /runs/plans/{plan_id}/alerts
```

The planner references the saved dataset manifest by `dataset_id`, reuses the
validation summary for workflow eligibility, and reports whether the requested
workflow is `ready`, `not_eligible`, or `blocked`. This is a planning boundary:
it does not execute canonicalization, model inference, counterfactual
simulation, or scientific artifact generation. The dry-run plan itself is
persisted as a reproducibility record under the API workspace and can be
retrieved by `plan_id`.

The initial executor supports `canonical_observations`, `monthly_panel`, and
deterministic expert `fuzzy_state` scoring. It converts supported units into
canonical units, writes canonical rows, builds a long monthly panel using
median aggregation, and for `fuzzy_state` builds the wide expert fuzzy input
surface expected by `src.fuzzy.expert.build_expert_state` using the frozen IRC
weights declared in `reports/anfis/fuzzy_manifest.json`.

`fuzzy_state` emits:

| Artifact | Meaning |
|---|---|
| `monthly_panel_wide.csv` | Source/site/month panel with `mean_*` columns and derived `TN_TP_ratio` / `risk_chla` when possible. |
| `fuzzy_state_scores.csv` | Expert fuzzy state outputs including `yN`, `yF`, `yT`, `irc1`, uncertainty/evidence columns, labels, and trophic memberships. |
| `fuzzy_state_trace.csv` | Component-level fuzzy membership and trace columns for audit. |
| `fuzzy_state_manifest.json` | Local reproducibility manifest for the expert fuzzy scoring step. |

This layer is expert fuzzy scoring only. Adaptive ANFIS retraining, PIPE-GRU-D,
Neural ODE, MIFAL-ED/T2, and counterfactual planning are intentionally refused
by the synchronous executor until their scientific adapters are integrated.

Generated artifacts can be listed and previewed after execution. Artifact
previews are intentionally bounded and JSON-safe; they are intended for
inspection, UI rendering, and reproducibility checks, not as a replacement for
downloading complete scientific exports.

For `fuzzy_state`, prediction and alert endpoints expose current-month expert
fuzzy state scores and thresholded current-state indicators. They do not emit
temporal forecasts, official advisories, or model-calibrated early-warning
alerts.

## Privacy And Provenance

The API should not require sensitive or private location metadata beyond what is
needed for reproducible processing. If users submit restricted data, the API
must preserve provenance and artifact hashes without publishing private raw
inputs by default.

## External Dataset Limits

The API can fail gracefully when a dataset lacks required variables, temporal
coverage, or quality. Such failures are expected behavior and should be reported
as actionable validation or eligibility results, not as silent fallbacks.
