# API Error And Warning Contract

This document defines standard API errors and warnings for reproducible
scientific workflows.

## Error Response Shape

All non-2xx errors should use this shape:

```json
{
  "error": {
    "code": "insufficient_coverage",
    "message": "Dataset has too few valid monthly observations for the requested workflow.",
    "details": {
      "required_months": 12,
      "observed_months": 4
    },
    "run_id": "optional-run-id",
    "report_uri": "optional-report-uri"
  }
}
```

Warnings inside successful responses should use:

```json
{
  "warnings": [
    {
      "code": "low_variable_coverage",
      "message": "TP_ugL is present in fewer than 30% of eligible site-months.",
      "details": {
        "variable": "TP_ugL",
        "coverage": 0.18
      }
    }
  ]
}
```

## Error Codes

| HTTP | Code | Meaning |
|---:|---|---|
| 400 | `invalid_request` | Request is syntactically valid JSON but semantically malformed. |
| 401 | `authentication_required` | Endpoint requires credentials. |
| 403 | `permission_denied` | Caller is authenticated but lacks permission. |
| 404 | `resource_not_found` | Requested experiment, dataset, run, or artifact does not exist. |
| 409 | `insufficient_coverage` | Dataset is valid but lacks enough temporal/variable coverage. |
| 409 | `unsupported_pipeline_for_dataset` | Requested workflow is not eligible for this dataset. |
| 409 | `no_valid_monthly_panel` | Canonical observations could not produce usable monthly rows. |
| 409 | `upstream_artifact_missing` | A required upstream artifact is missing or unavailable. |
| 422 | `schema_validation_failed` | Required columns, types, or date formats are invalid. |
| 422 | `unsupported_unit` | A provided unit is not in the declared conversion table. |
| 422 | `value_out_of_range` | Values violate impossible or declared plausible ranges. |
| 424 | `dependency_not_ready` | A required service, model artifact, or job dependency is unavailable. |
| 500 | `pipeline_execution_failed` | Unexpected technical failure during workflow execution. |

## Warning Codes

| Code | Meaning |
|---|---|
| `low_variable_coverage` | A variable is present but sparse. |
| `high_missingness` | Missingness may materially affect interpretation. |
| `limited_temporal_history` | Temporal window is shorter than recommended. |
| `low_site_count` | Dataset has few sites or stations. |
| `unit_conversion_approximate` | Conversion is accepted but approximate. |
| `current_chla_dependency` | Workflow uses current-month Chl-a and is closer to monitoring than early warning. |
| `counterfactual_not_causal` | Counterfactual planning output is model-simulated, not causal field evidence. |
| `model_outside_validation_domain` | Submitted data are outside the strongest validation support. |

## Status Mapping

| API/job status | Interpretation |
|---|---|
| `completed` | Workflow completed without material warnings. |
| `completed_with_warnings` | Workflow completed but output needs caution. |
| `not_eligible` | Valid dataset, unsupported workflow. |
| `ready` | Dry-run plan has no current eligibility or dependency blockers. |
| `blocked` | Dry-run plan cannot proceed because a dependency, upstream artifact, or valid dataset record is missing. |
| `failed` | Technical failure. |

The API must distinguish `not_eligible` from `failed`. A valid dataset that is
scientifically insufficient is not a server crash.
