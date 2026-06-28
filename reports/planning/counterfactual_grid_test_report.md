# Counterfactual Planning Grid Report

Planning version: `counterfactual_planning_grid_v0`.

## Non-Causal Guardrail

Counterfactual planning is simulation-based decision support, not field causality, and not official environmental advice.

The reported scenarios are model-input perturbations used for simulated
comparison against no action. They are not field interventions and are
not official environmental recommendations.

## Configuration

- Config: `configs/counterfactual_planning.yaml`
- Planning rows: `data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet`
- Scenario family: `minimal_state_grid`
- Planning mode: `normal`
- Evaluation splits: `test`
- Alert threshold used for optional label metrics: `0.5000`

## Row Counts

- Metric rows: `60`
- Scenario summaries: `20`
- Pareto-front rows: `8`

## Top Scenarios By Objective

| Scenario | Action | Objective | Risk reduction | Cost | Uncertainty delta | Pareto |
|---|---|---:|---:|---:|---:|---:|
| `no_action` | `no_action` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | True |
| `state_yN_0_yF_p0p025` | `clarity_improvement` | -0.0108 | 0.0067 | 0.3500 | 0.0000 | True |
| `state_yN_m0p025_yF_0` | `nutrient_reduction_tp` | -0.0183 | 0.0067 | 0.5000 | 0.0000 | True |
| `state_yN_0_yF_p0p05` | `clarity_improvement` | -0.0218 | 0.0132 | 0.7000 | 0.0000 | True |
| `state_yN_m0p05_yF_0` | `nutrient_reduction_tp` | -0.0367 | 0.0133 | 1.0000 | 0.0000 | True |
| `state_yN_m0p025_yF_p0p025` | `combined_nutrient_clarity` | -0.0392 | 0.0133 | 1.0500 | 0.0000 | False |
| `state_yN_0_yF_p0p1` | `clarity_improvement` | -0.0447 | 0.0253 | 1.4000 | 0.0000 | True |
| `state_yN_m0p025_yF_p0p05` | `combined_nutrient_clarity` | -0.0501 | 0.0199 | 1.4000 | 0.0000 | False |
| `state_yN_m0p05_yF_p0p025` | `combined_nutrient_clarity` | -0.0575 | 0.0200 | 1.5500 | 0.0000 | False |
| `state_yN_m0p05_yF_p0p05` | `combined_nutrient_clarity` | -0.0685 | 0.0265 | 1.9000 | 0.0000 | True |

## Interpretation Boundary

A positive objective means only that the scenario improved the configured
risk-cost-uncertainty objective under this state-proxy simulation. If no
scenario improves the objective, that is a valid result: the current
surface does not support prescriptive use under the tested assumptions.

Prohibited claim:

> The scenario will reduce real-world eutrophication or should be implemented as an official environmental intervention.
