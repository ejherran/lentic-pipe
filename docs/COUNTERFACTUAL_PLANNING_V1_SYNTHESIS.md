# Counterfactual Planning V1 Synthesis

This document closes counterfactual planning v1 for `lentic-pipe`. V1 extends
the v0 state-proxy planning benchmark with a raw-proxy, support-aware scenario
surface.

The result is usable, but deliberately conservative: V1 improves ecological
interpretability and support accounting, but it does not improve the net
planning objective over `no_action`.

## Status

Counterfactual planning v1 is complete as a reproducible raw-proxy,
support-aware planning benchmark.

The locked result is:

- under `normal`, `no_action` remains top-ranked in validation and held-out
  test;
- under `crisis`, `no_action` also remains top-ranked in validation and
  held-out test;
- `budget_constrained` was omitted from held-out testing because it is
  dominated by `crisis` for positive-scenario search: it has a higher cost
  penalty and lower relative-cost budget.

This means that the positive `crisis` utility found in v0 does not survive
when scenarios are required to pass through raw ecological proxy variables and
historical-support penalties.

## Scientific Boundary

The v1 planning block answers this question:

```text
Within the expert fuzzy state surface and declared support constraints, do
raw-proxy scenarios improve simulated risk enough to beat no action?
```

It does not answer:

```text
Which field intervention will causally reduce eutrophication?
```

The reported scenarios are simulation diagnostics over observational data.
They must not be presented as field interventions, regulatory advice, or causal
management prescriptions.

## Planning Surface

V1 uses the monthly panel and the expert fuzzy state builder rather than
directly perturbing learned state channels.

Primary inputs:

- config: `configs/counterfactual_planning_v1.yaml`;
- runner: `src/experiments/evaluate_counterfactual_planning_v1.py`;
- protocol: `docs/COUNTERFACTUAL_PLANNING_V1_PROTOCOL.md`;
- sequence rows:
  `data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet`;
- monthly panel: `data/panel/panel_monthly_v0.parquet`;
- variable ranges: `configs/variables.yaml`.

The declared raw proxies are:

| Proxy | Panel column | Direction |
|---|---|---|
| total phosphorus | `mean_TP_ugL` | decrease |
| total nitrogen | `mean_TN_ugL` | decrease |
| Secchi depth | `mean_secchi_depth_m` | increase |
| turbidity | `mean_turbidity_NTU` | decrease |
| dissolved oxygen | `mean_DO_mgL` | increase |

Chl-a is not used as a direct action lever.

For each scenario, the runner:

- perturbs declared raw panel columns;
- clips to plausible variable ranges;
- recomputes `TN_TP_ratio` after nutrient perturbations;
- recomputes expert fuzzy state channels;
- reports site/source historical-support violations;
- penalizes support violations in the objective;
- writes metrics, summary, Pareto, examples, report, and manifest artifacts.

## Reproducibility Trail

The V1 runner has a CLI completion summary that prints output files and byte
sizes. The synthetic CLI test asserts that this created-file summary appears.

Every real run below has a manifest that records script, config, input, output,
and report hashes. The locked script hash for the real V1 runs is:

```text
6daaf4d66d969447ad73104a74180d19540abd85fc6753760e72ea12c1e429f4
```

## Evaluation Design

V1 restarted the validation-first workflow after V0 was closed. The held-out
test set was used only after the validation decision was locked.

The locked validation decision was:

- evaluate `normal` and `crisis`;
- omit `budget_constrained` from final test because it is dominated by
  `crisis`;
- stop searching for extra scenarios if V1 remains negative.

## Results

Validation rows expand to 273,678 horizon rows per scenario. Held-out test rows
expand to 259,434 horizon rows per scenario.

| Split | Mode | Top scenario | Best non-baseline | Best non-baseline risk reduction | Best non-baseline support violation | Best non-baseline objective |
|---|---|---|---|---:|---:|---:|
| validation | `normal` | `no_action` | `oxygen_support_05` | `0.0021` | `0.0398` | `-0.0299` |
| validation | `crisis` | `no_action` | `oxygen_support_05` | `0.0021` | `0.0398` | `-0.0059` |
| test | `normal` | `no_action` | `oxygen_support_05` | `0.0021` | `0.0487` | `-0.0304` |
| test | `crisis` | `no_action` | `oxygen_support_05` | `0.0021` | `0.0487` | `-0.0064` |

The largest risk-reduction scenarios are also negative after cost and support
penalties:

| Split | Mode | Largest risk-reduction scenario | Risk reduction | Support violation | Objective |
|---|---|---|---:|---:|---:|
| validation | `normal` | `tp_reduction_25` | `0.0104` | `0.1533` | `-0.1225` |
| validation | `crisis` | `nutrient_clarity_strong` | `0.0212` | `0.3116` | `-0.0347` |
| test | `normal` | `tp_reduction_25` | `0.0116` | `0.1522` | `-0.1213` |
| test | `crisis` | `nutrient_clarity_strong` | `0.0217` | `0.3106` | `-0.0341` |

Primary artifacts:

| Split | Mode | Report |
|---|---|---|
| validation smoke | `normal` | `reports/planning/counterfactual_raw_proxy_v1_smoke_validation_report.md` |
| validation | `normal` | `reports/planning/counterfactual_raw_proxy_v1_validation_report.md` |
| validation | `crisis` | `reports/planning/counterfactual_raw_proxy_v1_validation_crisis_report.md` |
| test | `normal` | `reports/planning/counterfactual_raw_proxy_v1_test_report.md` |
| test | `crisis` | `reports/planning/counterfactual_raw_proxy_v1_test_crisis_report.md` |

## Comparison With V0

V0 and V1 answer related but different questions.

| Criterion | V0 state-proxy grid | V1 raw-proxy/support-aware grid |
|---|---|---|
| Scenario surface | learned state channels | raw ecological proxy variables |
| Support penalty | no explicit historical-support penalty | explicit site/source support penalty |
| `normal` validation/test | negative | negative |
| `crisis` validation/test | positive | negative |
| Interpretation | latent planning potential | conservative raw-proxy feasibility screen |

V0 showed that simulated planning utility can appear if learned state channels
are allowed to move directly under a permissive `crisis` objective. V1 shows
that this positive signal does not automatically translate into raw proxy
scenarios once ecological interpretability and historical support are enforced.

## Interpretation

V1 is not a failed result. It is a more conservative planning surface that
clarifies the boundary between latent state sensitivity and defensible
raw-proxy scenario comparison.

The precise doctoral claim is:

```text
Counterfactual planning over raw ecological proxies remains usable as
simulation-based decision support, but under the declared cost and support
constraints it does not select an action over no action. The positive v0 crisis
signal is therefore best interpreted as latent planning potential, not as a
raw-proxy intervention recommendation.
```

## Limitations

- V1 uses the expert fuzzy state builder, not a learned causal response model.
- Relative costs are research weights, not monetary intervention costs.
- Historical support violations are diagnostics and penalties, not physical
  impossibility proofs.
- Scenario effects are simulated over observational data.
- The grid is curated and intentionally small.
- No scenario should be interpreted as official environmental guidance.

## Closure Decision

Counterfactual planning v1 is closed as a reproducible raw-proxy,
support-aware planning benchmark.

No further held-out test exploration should be performed for V1. Future work
should either:

- move to API/OpenAPI packaging using the alerting and planning artifacts; or
- design a new planning family with a new validation-first protocol before any
  additional test-set evaluation.
