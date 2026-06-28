# Counterfactual Planning V1 Raw-Proxy Report

Planning version: `counterfactual_planning_raw_proxy_v1`.

## Non-Causal Guardrail

Counterfactual planning is simulation-based decision support, not field causality, and not official environmental advice.

The reported scenarios are raw-input perturbations used for simulated
comparison against no action. They are not field interventions and are
not official environmental recommendations.

## Configuration

- Config: `configs/counterfactual_planning_v1.yaml`
- Planning rows: `data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet`
- Monthly panel: `data/panel/panel_monthly_v0.parquet`
- Variables config: `configs/variables.yaml`
- Planning mode: `normal`
- Evaluation splits: `test`

## Row Counts

- Metric rows: `30`
- Scenario summaries: `10`
- Pareto-front rows: `6`

## Top Scenarios By Objective

| Scenario | Action | Objective | Risk reduction | Cost | Support violation | Pareto |
|---|---|---:|---:|---:|---:|---:|
| `no_action` | `no_action` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | True |
| `oxygen_support_05` | `oxygen_support_proxy` | -0.0304 | 0.0021 | 0.6000 | 0.0487 | True |
| `tn_reduction_10` | `nutrient_reduction_tn` | -0.0422 | 0.0013 | 0.8000 | 0.0711 | False |
| `tp_reduction_10` | `nutrient_reduction_tp` | -0.0497 | 0.0045 | 1.0000 | 0.0821 | True |
| `clarity_mild` | `clarity_improvement` | -0.0721 | 0.0054 | 1.4000 | 0.1471 | True |
| `tp_tn_reduction_10` | `combined_nutrient` | -0.1008 | 0.0060 | 2.0000 | 0.1347 | True |
| `tp_reduction_25` | `nutrient_reduction_tp` | -0.1213 | 0.0116 | 2.5000 | 0.1522 | True |

## Interpretation Boundary

A positive objective means only that the raw-proxy scenario improved the
configured risk-cost-uncertainty-support objective under this fuzzy-state
simulation. Historical support violations are penalized and reported, not
treated as causal evidence.