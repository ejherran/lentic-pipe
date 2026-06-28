# Counterfactual Planning Protocol

This document opens the first counterfactual planning block for `lentic-pipe`.
It defines the scientific boundary, initial planning surface, intervention
proxies, constraints, costs, search stages, and expected artifacts. It does not
report executed planning results.

## Purpose

Counterfactual planning asks whether the already-trained project surfaces can
compare a no-action rollout against plausible simulated scenarios. The purpose
is decision-support research, not field intervention advice.

The defensible question is:

```text
Within the learned model and stated assumptions, which scenario reduces
simulated risk compared with no action?
```

The protocol supports the doctoral claim that the system can move from alerting
to cautious simulation while preserving reproducibility, uncertainty reporting,
and explicit limits.

## Scientific Boundary

Counterfactual planning is not causal inference. The project has observational
secondary data, not controlled intervention data. Therefore:

- do not claim that a scenario will reduce eutrophication in the field;
- do not present scenario outputs as official environmental recommendations;
- do not optimize scenarios on held-out test performance;
- do not treat Chl-a as a direct control lever;
- do not create scenarios outside plausible historical or ecological bounds
  unless they are labeled as sensitivity analyses.

Allowed language:

```text
The system compares simulated counterfactual scenarios under the learned model.
```

Disallowed language without independent causal evidence:

```text
The system recommends interventions that reduce real eutrophication.
```

## Initial Surface

The first planning implementation should use the adaptive WQP-focused
PIPE-GRU-D surface as the functional baseline:

- sequence dataset:
  `data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet`;
- model artifacts:
  `models/pipe_grud/adaptive_wqp_focused/`;
- rollout evidence:
  `reports/pipe_grud/adaptive_wqp_focused/`;
- default alert policy:
  `closest_pr` from the adaptive 2B policy frontier.

MIFAL-ED/T2 is not the initial optimization surface. It should be used as an
interpretability and robustness lens for `bloom_h` only because it does not
emit `irc_alert`.

Neural ODE is not the initial planning surface. It remains a calibrated
temporal comparison branch and can be added only after the minimal PIPE-GRU-D
planning path is implemented and reviewed.

## Planning Unit

The planning unit is:

```text
source_id x site_id x origin_year_month x planning_horizon_months
```

The first planning horizon should match the established rollout geometry:

```text
1, 2, and 3 months
```

Planning must preserve source-scoped site identity and existing split
boundaries. Scenario selection uses validation rows. Test rows are reserved for
final, locked evaluation after scenario families and objective weights are
declared.

## No-Action Baseline

Every planning run must include a no-action baseline. The no-action baseline is
the rollout produced by the selected model surface without scenario changes.

Every reported scenario must include:

- absolute simulated risk;
- delta against no action;
- relative cost;
- uncertainty change;
- feasibility flags;
- interpretation boundary.

## Defensible Proxy Actions

The first scenario grid should use observable proxies rather than literal field
actions. These are not causal levers; they are model-input or state-space
perturbations used to test simulated sensitivity.

| Proxy action | Primary representation | Planning interpretation | Guardrail |
|---|---|---|---|
| `nutrient_reduction_tp` | reduce TP-derived evidence or `yN` | lower phosphorus-pressure proxy | Do not claim actual load reduction. |
| `nutrient_reduction_tn` | reduce TN-derived evidence or `yN` | lower nitrogen-pressure proxy | Do not infer real TN:TP response. |
| `clarity_improvement` | increase Secchi / reduce turbidity proxy or improve `yF` | improved light/clarity proxy | Do not claim restoration outcome. |
| `oxygen_support_proxy` | improve DO proxy or `yF` | reduced hypoxia-stress proxy | Do not claim aeration effect without field data. |
| `combined_nutrient_clarity` | joint nutrient and clarity proxies | multi-stressor scenario | Report cost and uncertainty jointly. |
| `no_action` | no perturbation | reference rollout | Required in every run. |

Temperature and seasonality are context variables in the first implementation,
not intervention variables. Chl-a is a state/result variable and may not be
directly optimized as an action.

## Scenario Spaces

The first implementation should support two scenario spaces.

### Raw-Proxy Space

Raw-proxy scenarios perturb monthly panel-derived predictors before rebuilding
the fuzzy state and sequence inputs. This is the more ecologically interpretable
space, but it is more expensive because it requires recomputation.

Initial levels:

| Proxy | Levels |
|---|---|
| TP multiplier | `1.00`, `0.95`, `0.90`, `0.85`, `0.75` |
| TN multiplier | `1.00`, `0.95`, `0.90`, `0.85`, `0.75` |
| Secchi multiplier | `1.00`, `1.05`, `1.10`, `1.20` |
| Turbidity multiplier | `1.00`, `0.95`, `0.90`, `0.80` |
| DO offset mg/L | `0.00`, `0.25`, `0.50`, `1.00` |

The raw-proxy space should be implemented after the state-proxy path unless the
cost of recomputation is already acceptable.

### State-Proxy Space

State-proxy scenarios perturb the PIPE state channels consumed by the temporal
model. This is the minimal implementation path because the adaptive PIPE-GRU-D
model already consumes `S(t)` sequence columns.

Initial state channels:

| Channel | Direction | Levels |
|---|---|---|
| `x_yN` | decrease nutrient pressure | `0.00`, `-0.025`, `-0.05`, `-0.10`, `-0.15` |
| `x_yF` | improve functional/physicochemical condition | `0.00`, `0.025`, `0.05`, `0.10` |
| `x_yT` | derived trophic state proxy | no direct action |

State perturbations must be clipped to `[0, 1]`. Uncertainty channels may be
propagated unchanged in the first implementation; later sensitivity runs may
increase uncertainty when a scenario is far from observed support.

## Constraints

Every scenario must pass feasibility constraints before it is ranked.

Minimum constraints:

- all bounded state channels remain in `[0, 1]`;
- raw variables remain within the plausible ranges in `configs/variables.yaml`;
- scenario levels stay within historical site quantile envelopes when raw
  predictors are used;
- no scenario may use future observed target values;
- no scenario may change split assignment, labels, calibrators, or alert
  thresholds during evaluation;
- combined action cost must not exceed the configured budget for the selected
  planning mode.

Recommended historical envelope for the first raw-proxy implementation:

```text
site-level p05..p95 if at least 24 observed months are available,
otherwise source-level p01..p99.
```

## Relative Costs

Costs are relative research weights, not monetary estimates. They are used to
prevent the optimizer from selecting only extreme scenarios.

Initial cost weights:

| Proxy action | Unit cost |
|---|---:|
| `nutrient_reduction_tp` | `1.00` |
| `nutrient_reduction_tn` | `0.80` |
| `clarity_improvement` | `0.70` |
| `oxygen_support_proxy` | `0.60` |
| `combined_nutrient_clarity` | sum of component costs plus `0.20` coordination cost |

Planning modes:

| Mode | Cost penalty |
|---|---:|
| `crisis` | `0.01` |
| `normal` | `0.05` |
| `budget_constrained` | `0.20` |

## Objective

The first objective should balance simulated `irc_alert` risk reduction,
simulated `bloom_h` probability reduction, cost, and uncertainty.

For scenario `s`:

```text
risk_gain(s) =
  w_irc   * (irc_risk_no_action - irc_risk_s)
  + w_bloom * (bloom_probability_no_action - bloom_probability_s)

objective(s) =
  risk_gain(s)
  - lambda_cost * relative_cost(s)
  - lambda_uncertainty * max(0, uncertainty_s - uncertainty_no_action)
```

Initial weights:

```text
w_irc = 0.60
w_bloom = 0.40
lambda_cost = selected planning-mode penalty
lambda_uncertainty = 0.10
```

The first implementation may rank by mean objective and then report Pareto
fronts for:

- risk reduction;
- cost;
- uncertainty change;
- maximum horizon risk.

## Search Stages

The implementation order should be conservative.

1. Grid search over a small declared scenario grid.
2. Random shooting over the same declared bounds after grid output is reviewed.
3. Cross-entropy method only if grid/random shooting reveal a smooth enough
   objective surface and the run budget is explicitly approved.

Reinforcement learning is out of scope for the current doctoral work package.

## Metrics

Every planning report should include metrics by split, horizon, source, and
scenario family where possible:

- rows evaluated;
- feasible rows;
- infeasible rows and reasons;
- baseline `irc_alert` probability or score;
- scenario `irc_alert` probability or score;
- baseline `bloom_h` probability;
- scenario `bloom_h` probability;
- absolute and relative simulated risk reduction;
- relative cost;
- uncertainty delta;
- objective value;
- Pareto rank;
- alert-policy behavior under the locked `closest_pr` profile.

When test is evaluated, report validation-selected scenario families separately
from held-out test metrics.

## Artifact Plan

Recommended first artifacts:

```text
configs/counterfactual_planning.yaml
reports/planning/counterfactual_grid_metrics.csv
reports/planning/counterfactual_grid_summary.csv
reports/planning/counterfactual_grid_pareto.csv
reports/planning/counterfactual_grid_examples.csv
reports/planning/counterfactual_grid_report.md
reports/planning/counterfactual_grid_manifest.json
```

If row-level scenario outputs are materialized, they are heavy artifacts and
must be tracked through DVC rather than Git.

## Reproducibility Rules

- The config file is the source of truth for scenario definitions.
- All runs must record script hash, config hash, input artifact hashes, model
  artifact references, and output hashes.
- Scenario selection must use validation only.
- Test evaluation must be a locked follow-up using previously declared
  scenario families and objective weights.
- The report must include negative results: scenarios with no simulated
  improvement, high cost, infeasibility, or increased uncertainty.

## Closure Criteria

Corte 12 can be considered minimally closed when the repository has:

- a public protocol and machine-readable config;
- an implemented grid-search runner;
- a no-action baseline and at least one feasible scenario family;
- validation ranking and held-out test evaluation under locked scenario
  definitions;
- cost and uncertainty reporting;
- Pareto output;
- explicit non-causal language in the report.

If scenarios do not reduce simulated risk, that is a valid doctoral result:
the current learned surface does not support prescriptive use under the tested
assumptions.
