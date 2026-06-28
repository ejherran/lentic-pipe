# Counterfactual Planning Synthesis

This document closes the first counterfactual planning block for `lentic-pipe`.
It summarizes the protocol, implementation, validation evidence, locked
held-out test, and interpretation boundary for the initial state-proxy planning
grid.

The synthesis is intentionally narrow. It reports simulated scenario comparison
under an already-trained learned surface. It does not report field causality,
real intervention effects, or official environmental recommendations.

## Status

Counterfactual planning v0 is complete as a reproducible state-proxy planning
benchmark.

The main result is conditional:

- under `normal` and `budget_constrained` assumptions, `no_action` remains the
  top-ranked option because the tested proxy scenarios reduce simulated risk
  but do not overcome the configured relative-cost penalty;
- under the predeclared `crisis` mode, the same grid identifies positive net
  simulated scenarios in both validation and held-out test;
- the strongest positive scenario is stable across validation and test:
  `state_yN_m0p05_yF_p0p1`, a combined nutrient/clarity state-proxy
  perturbation.

## Scientific Boundary

The planning block answers this question:

```text
Within the learned model and stated assumptions, which scenario reduces
simulated risk compared with no action?
```

It does not answer:

```text
Which real-world intervention will causally reduce eutrophication?
```

The project uses observational secondary data, not randomized field
interventions. Therefore the reported scenarios are decision-support
simulations. They must not be presented as management prescriptions, regulatory
advice, or evidence of causal field effects.

## Planning Surface

The first planning surface is the adaptive WQP-focused PIPE-GRU-D branch,
operating on the already-created adaptive PIPE state channels. The initial
planning grid is deliberately small and uses state proxies rather than raw
field-action variables.

Primary inputs:

- config: `configs/counterfactual_planning.yaml`;
- runner: `src/experiments/evaluate_counterfactual_planning.py`;
- sequence rows:
  `data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet`;
- protocol: `docs/COUNTERFACTUAL_PLANNING_PROTOCOL.md`.

Scenario family:

- `minimal_state_grid`;
- state channels: `x_yN` and `x_yF`;
- required baseline: `no_action`;
- horizons: 1, 2, and 3 months;
- splits: validation first, locked test after validation decisions.

Planning modes:

| Mode | Cost penalty | Cost budget | Role |
|---|---:|---:|---|
| `crisis` | `0.01` | `3.00` | low cost penalty sensitivity |
| `normal` | `0.05` | `2.00` | primary conservative benchmark |
| `budget_constrained` | `0.20` | `1.00` | high cost penalty benchmark |

## Reproducibility Trail

The block was built and evaluated in four committed steps:

| Commit | Purpose |
|---|---|
| `6c3f833` | open protocol, config, runner, synthetic tests, and validation smoke |
| `cf81aea` | add full validation benchmark under `normal` mode |
| `7cc7648` | add validation-only mode sensitivity for `crisis` and `budget_constrained` |
| `bbc6708` | add locked held-out test for all three declared modes |

Each experiment report is paired with a manifest that records script, config,
input, output, and artifact hashes. The pre-commit artifact assistant validated
the staged report artifacts before each commit.

## Evaluation Design

Validation was used to decide whether the initial grid had any planning signal
and which declared mode, if any, should be treated as a positive sensitivity.
Held-out test was run once after those decisions were fixed.

No test-set exploration was performed. The test evaluation reused the same
grid, same config, same objective, same modes, and same runner.

## Results

Validation rows were expanded across the three planning horizons to 273,678
horizon rows per scenario. Held-out test rows were expanded to 259,434 horizon
rows per scenario.

| Split | Mode | Positive completed non-baseline scenarios | Top scenario | Simulated risk reduction | Relative cost | Objective |
|---|---|---:|---|---:|---:|---:|
| validation | `normal` | 0 | `no_action` | `0.0000` | `0.0000` | `0.0000` |
| validation | `crisis` | 15 | `state_yN_m0p05_yF_p0p1` | `0.0389` | `2.6000` | `0.0129` |
| validation | `budget_constrained` | 0 | `no_action` | `0.0000` | `0.0000` | `0.0000` |
| test | `normal` | 0 | `no_action` | `0.0000` | `0.0000` | `0.0000` |
| test | `crisis` | 15 | `state_yN_m0p05_yF_p0p1` | `0.0387` | `2.6000` | `0.0127` |
| test | `budget_constrained` | 0 | `no_action` | `0.0000` | `0.0000` | `0.0000` |

Primary artifacts:

| Split | Mode | Report |
|---|---|---|
| validation smoke | `normal` | `reports/planning/counterfactual_grid_smoke_validation_report.md` |
| validation | `normal` | `reports/planning/counterfactual_grid_validation_report.md` |
| validation | `crisis` | `reports/planning/counterfactual_grid_validation_crisis_report.md` |
| validation | `budget_constrained` | `reports/planning/counterfactual_grid_validation_budget_constrained_report.md` |
| test | `normal` | `reports/planning/counterfactual_grid_test_report.md` |
| test | `crisis` | `reports/planning/counterfactual_grid_test_crisis_report.md` |
| test | `budget_constrained` | `reports/planning/counterfactual_grid_test_budget_constrained_report.md` |

## Interpretation

The validation and test results agree.

The initial state-proxy grid is useful as a cautious simulation layer, but its
planning signal is conditional on the cost assumptions:

- `normal`: negative benchmark. Risk reductions are present, but cost prevents
  action selection over `no_action`.
- `budget_constrained`: stronger negative benchmark. The higher cost penalty
  and lower budget make the grid even more conservative.
- `crisis`: positive sensitivity. With lower cost penalty and larger budget,
  the grid identifies positive simulated scenarios, and the top scenario
  generalizes to held-out test.

This supports a precise doctoral claim:

```text
The architecture can move from alerting to cautious simulated scenario
comparison. In the first state-proxy grid, positive planning utility appears
only under a predeclared crisis mode, while normal and budget-constrained modes
remain conservative and select no action.
```

## Limitations

- The scenarios perturb learned state proxies, not raw management variables.
- The objective uses relative research costs, not monetary estimates.
- Uncertainty channels are propagated unchanged in this first implementation.
- The planning output is not causal and not field-action guidance.
- Neural ODE and MIFAL are not used as first planning surfaces in this block.
- Raw-proxy planning remains future work if the project needs more
  ecologically interpretable scenario levers.

## Closure Decision

Counterfactual planning v0 is closed as a reproducible planning benchmark.

No further exploration should be performed on the held-out test set for this
grid. Future work should either:

- add a raw-proxy scenario family and repeat the validation-first workflow; or
- move to API/OpenAPI packaging using the existing alerting and planning
  artifacts.
