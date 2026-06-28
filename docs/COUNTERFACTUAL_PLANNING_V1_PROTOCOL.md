# Counterfactual Planning V1 Protocol

This document opens counterfactual planning v1 for `lentic-pipe`. V0 remains
frozen as the state-proxy planning benchmark documented in
`docs/COUNTERFACTUAL_PLANNING_SYNTHESIS.md`.

V1 exists because V0 is useful but intentionally limited: it perturbs learned
state channels directly. V1 adds a more interpretable raw-proxy scenario family
and explicit historical-support accounting. It still remains simulation-based
decision support, not field causality or environmental advice.

## Boundary

The v1 question is:

```text
Within the learned fuzzy-state surface and declared support constraints, which
raw-proxy scenario improves simulated risk relative to no action?
```

V1 must not be interpreted as:

```text
A field intervention recommendation that will causally reduce eutrophication.
```

The held-out test set used by V0 is closed for the v0 grid. V1 must restart the
validation-first workflow:

1. declare the v1 protocol and config;
2. implement synthetic tests;
3. run only bounded validation smoke;
4. review validation;
5. decide whether full validation is justified;
6. use held-out test only once after v1 decisions are locked.

## V1 Surface

The first v1 implementation uses the monthly panel and the expert fuzzy state
builder. It does not train or refit a temporal model.

Inputs:

- monthly panel: `data/panel/panel_monthly_v0.parquet`;
- planning rows:
  `data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet`;
- variable ranges: `configs/variables.yaml`;
- v1 config: `configs/counterfactual_planning_v1.yaml`.

The v1 runner recomputes fuzzy state channels after raw-proxy perturbations:

- `yN` for nutrient pressure;
- `yF` for physicochemical condition;
- `yT` unchanged except for any non-intervened raw context already present;
- uncertainty from the fuzzy state builder.

## Raw-Proxy Scenario Family

The initial v1 family is `raw_proxy_support_grid`. It uses a small curated set
of interpretable scenarios instead of a large Cartesian search.

Allowed proxy variables:

| Proxy | Panel column | Direction |
|---|---|---|
| total phosphorus | `mean_TP_ugL` | decrease |
| total nitrogen | `mean_TN_ugL` | decrease |
| Secchi depth | `mean_secchi_depth_m` | increase |
| turbidity | `mean_turbidity_NTU` | decrease |
| dissolved oxygen | `mean_DO_mgL` | increase |

Chl-a remains prohibited as a direct action lever.

## Historical Support

V1 must report whether a scenario stays inside historical support.

For each raw proxy, support is computed as:

- site-level p05..p95 when a site has at least 24 non-missing months;
- source-level p01..p99 fallback otherwise.

Support violations are not automatically field infeasibility. They are a
scenario diagnostic and an objective penalty. This keeps the report useful when
an informative scenario is slightly outside historical support while preventing
unsupported scenarios from silently ranking too high.

## Objective

V1 keeps the v0 risk-cost-uncertainty objective and adds a support penalty:

```text
objective =
  weighted_risk_reduction
  - lambda_cost * relative_cost
  - lambda_uncertainty * max(0, scenario_uncertainty - baseline_uncertainty)
  - lambda_support * support_violation
```

Where `support_violation` is row-level `0` or `1` when any modified raw proxy is
outside the selected historical envelope.

The first v1 value is:

```text
lambda_support = 0.05
```

## Required Outputs

The v1 runner must produce:

- metrics CSV;
- summary CSV;
- Pareto CSV;
- example rows CSV;
- Markdown report;
- JSON manifest with script/config/input/output hashes.

Reports must include:

- no-action baseline;
- scenario status;
- cost;
- support violation rows/rate;
- risk reduction;
- objective;
- non-causal interpretation.

## Initial Validation Command

After code review and lightweight checks, the first real run should be a
bounded validation-only smoke. It must not use held-out test rows:

```bash
poetry run python src/experiments/evaluate_counterfactual_planning_v1.py \
  --config configs/counterfactual_planning_v1.yaml \
  --planning-rows data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet \
  --panel data/panel/panel_monthly_v0.parquet \
  --variables-config configs/variables.yaml \
  --output-dir reports/planning \
  --output-name counterfactual_raw_proxy_v1_smoke_validation \
  --evaluation-splits validation \
  --max-rows-per-split 128 \
  --examples-per-scenario 5
```

If the smoke succeeds and the report is coherent, full validation can be run
with the same command after removing `--max-rows-per-split 128` and changing
the output name to `counterfactual_raw_proxy_v1_validation`.

## Initial Smoke Result

The bounded validation smoke was executed with `max_rows_per_split=128` and
produced the following files. The CLI also prints this file list at the end of
the run, so a completed execution is visible in the terminal as well as in the
manifest.

- `reports/planning/counterfactual_raw_proxy_v1_smoke_validation_metrics.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_smoke_validation_summary.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_smoke_validation_pareto.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_smoke_validation_examples.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_smoke_validation_report.md`;
- `reports/planning/counterfactual_raw_proxy_v1_smoke_validation_manifest.json`.

Smoke counts:

- metric rows: `30`;
- scenario summaries: `10`;
- Pareto-front rows: `6`;
- evaluated rows per scenario: `384`.

Under the normal planning objective, `no_action` remains top-ranked. The best
completed non-baseline scenario is `oxygen_support_05`, with simulated risk
reduction `0.0044`, relative cost `0.6000`, support violation rate `0.0312`,
and objective `-0.0272`. This is a coherent engineering smoke and a cautious
negative result for the normal v1 objective on the sampled validation subset;
it is not a held-out test result.

## Full Validation Result

The full validation run used the same configuration and removed the bounded
`--max-rows-per-split` smoke limit:

- `reports/planning/counterfactual_raw_proxy_v1_validation_metrics.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_validation_summary.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_validation_pareto.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_validation_examples.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_validation_report.md`;
- `reports/planning/counterfactual_raw_proxy_v1_validation_manifest.json`.

Validation counts:

- metric rows: `30`;
- scenario summaries: `10`;
- Pareto-front rows: `6`;
- evaluated rows per scenario: `273,678`.

Under the normal objective, the full validation result matches the smoke
direction. `no_action` remains top-ranked with objective `0.0000`. The best
completed non-baseline scenario is again `oxygen_support_05`, with simulated
risk reduction `0.0021`, relative cost `0.6000`, support violation rate
`0.0398`, and objective `-0.0299`. The largest completed risk reduction among
normal-feasible scenarios is `tp_reduction_25` with risk reduction `0.0104`,
support violation rate `0.1533`, and objective `-0.1225`.

This is a full validation negative/cautious result for the normal v1 objective:
raw-proxy scenarios can reduce simulated risk, but their normal-mode net
objective remains below `no_action` after cost and support penalties.

## Crisis Sensitivity Result

Validation-only sensitivity was then executed under the declared `crisis`
planning mode:

- `reports/planning/counterfactual_raw_proxy_v1_validation_crisis_metrics.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_validation_crisis_summary.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_validation_crisis_pareto.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_validation_crisis_examples.csv`;
- `reports/planning/counterfactual_raw_proxy_v1_validation_crisis_report.md`;
- `reports/planning/counterfactual_raw_proxy_v1_validation_crisis_manifest.json`.

Crisis validation counts:

- metric rows: `30`;
- scenario summaries: `10`;
- Pareto-front rows: `8`;
- evaluated rows per scenario: `273,678`.

Under `crisis`, all scenarios are feasible because the relative-cost budget is
larger, but `no_action` still remains top-ranked. The best completed
non-baseline scenario is `oxygen_support_05`, with simulated risk reduction
`0.0021`, relative cost `0.6000`, support violation rate `0.0398`, and
objective `-0.0059`. The largest risk reduction is
`nutrient_clarity_strong`, with simulated risk reduction `0.0212`, support
violation rate `0.3116`, and objective `-0.0347`.

This differs from the v0 state-proxy grid: V0 showed positive simulated
utility under `crisis`, while V1 remains negative even in the permissive mode.
The interpretation is that the more interpretable raw-proxy surface is more
conservative under the declared cost/support objective.

## Validation Decision Lock

The v1 validation decision is locked as follows:

- `normal`: negative/cautious; `no_action` remains top-ranked.
- `crisis`: negative/cautious; `no_action` remains top-ranked even when all
  declared scenarios are budget-feasible.
- `budget_constrained`: omitted for held-out testing because it is logically
  dominated by `crisis` for positive-scenario search. It has a higher cost
  penalty and lower relative-cost budget than `crisis`, so it cannot rescue a
  raw-proxy scenario that is already negative under `crisis`.

The held-out test must be used only once after this lock. The locked test
surface is therefore:

```bash
poetry run python src/experiments/evaluate_counterfactual_planning_v1.py \
  --config configs/counterfactual_planning_v1.yaml \
  --planning-rows data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet \
  --panel data/panel/panel_monthly_v0.parquet \
  --variables-config configs/variables.yaml \
  --output-dir reports/planning \
  --output-name counterfactual_raw_proxy_v1_test \
  --evaluation-splits test \
  --planning-mode normal \
  --examples-per-scenario 5

poetry run python src/experiments/evaluate_counterfactual_planning_v1.py \
  --config configs/counterfactual_planning_v1.yaml \
  --planning-rows data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet \
  --panel data/panel/panel_monthly_v0.parquet \
  --variables-config configs/variables.yaml \
  --output-dir reports/planning \
  --output-name counterfactual_raw_proxy_v1_test_crisis \
  --evaluation-splits test \
  --planning-mode crisis \
  --examples-per-scenario 5
```

After those two locked runs are reviewed, v1 should be closed with a synthesis
document rather than further scenario search.

## Held-Out Test Result

The locked held-out test was executed for `normal` and `crisis` only:

- `reports/planning/counterfactual_raw_proxy_v1_test_report.md`;
- `reports/planning/counterfactual_raw_proxy_v1_test_crisis_report.md`.

Test counts:

- `normal`: 30 metric rows, 10 scenario summaries, 6 Pareto-front rows;
- `crisis`: 30 metric rows, 10 scenario summaries, 7 Pareto-front rows;
- evaluated rows per scenario: `259,434`.

The held-out test confirms validation. Under `normal`, `no_action` remains
top-ranked and the best completed non-baseline scenario is `oxygen_support_05`
with simulated risk reduction `0.0021`, support violation rate `0.0487`, and
objective `-0.0304`. Under `crisis`, `no_action` also remains top-ranked; the
best non-baseline scenario is again `oxygen_support_05`, with simulated risk
reduction `0.0021`, support violation rate `0.0487`, and objective `-0.0064`.

The final V1 synthesis is:

- `docs/COUNTERFACTUAL_PLANNING_V1_SYNTHESIS.md`.

## Closure Criteria

V1 validation can be considered minimally complete when:

- synthetic tests pass;
- a bounded validation smoke runs;
- reports include support accounting;
- no held-out test rows are used before validation decisions are documented.

If v1 improves interpretability but does not improve objective ranking, that is
a valid result. It would show that the more ecological raw-proxy surface is
more transparent but not necessarily more prescriptive under the declared
assumptions.
