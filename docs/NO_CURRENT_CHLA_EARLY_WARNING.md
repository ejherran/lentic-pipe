# No-Current-Chl-a Early-Warning Surface

This document defines the first formal no-current-Chl-a early-warning surface.
It is a protocol and execution guide, not a result report.

## Purpose

The controlled-degradation factorial showed that the current frozen
monitoring/nowcasting surface can rely strongly on current Chl-a memory or
target-proximal Chl-a evidence. That result does not imply that nutrients are
ecologically unimportant. It means strict early-warning claims require a model
surface that excludes current observed Chl-a before fitting, calibration, and
threshold selection.

This surface asks:

> Can the project estimate future Chl-a-derived state and bloom risk without
> using current observed Chl-a as an input?

## Input Surface

The sequence builder supports two surfaces:

- `full`: canonical PIPE inputs, including `yT`, `sigma_T`, and `delta_yT`
  derived from temperature plus current Chl-a pressure;
- `no_current_chla`: PIPE inputs where the current thermal/biological channels
  are replaced by their no-Chl-a fuzzy variants.

The no-current-Chl-a input mapping is:

| PIPE input channel | state-vector source |
|---|---|
| `x_yT` | `yT_no_chla` |
| `x_sigma_T` | `sigma_T_no_chla` |
| `x_delta_yT` | `delta_yT_no_chla` |

Targets remain the full next-month fuzzy state. This is intentional: observed
future Chl-a-derived state is the evaluation target, not a current predictor.
For rollout backtests, observed future state must therefore be built from
target columns only.

## Guardrails

- Do not overwrite canonical PIPE/GRU-D artifacts.
- Do not use `origin_and_target` observed-state reconstruction for no-current
  Chl-a backtests; use `--observed-state-source target`.
- Treat the first runs as a new surface, not a degradation scenario.
- Fit model weights, rollout bloom calibrators, and policy thresholds only from
  the no-current-Chl-a surface.
- Select thresholds on validation and evaluate on test.
- Report failures as first-class evidence.

## Smoke Execution

Start with bounded smoke commands. These commands create a parallel artifact
tree under `no_current_chla/` and do not overwrite promoted PIPE artifacts.

Build the sequence surface:

```bash
poetry run python src/experiments/build_pipe_sequences.py \
  --input-surface no_current_chla \
  --sequences data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet \
  --summary reports/pipe_grud/no_current_chla/pipe_sequence_summary.csv \
  --discarded reports/pipe_grud/no_current_chla/pipe_sequence_discarded_summary.csv \
  --report reports/pipe_grud/no_current_chla/pipe_sequence_report.md \
  --manifest reports/pipe_grud/no_current_chla/pipe_sequence_manifest.json
```

Train a bounded smoke model:

```bash
poetry run python src/experiments/train_pipe_grud.py \
  --sequences data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet \
  --sequence-manifest reports/pipe_grud/no_current_chla/pipe_sequence_manifest.json \
  --model models/pipe_grud/no_current_chla/pipe_grud_model_smoke.pt \
  --checkpoint models/pipe_grud/no_current_chla/pipe_grud_checkpoint_smoke.pt \
  --metrics reports/pipe_grud/no_current_chla/pipe_grud_metrics_smoke.csv \
  --persistence-metrics reports/pipe_grud/no_current_chla/pipe_grud_persistence_metrics_smoke.csv \
  --comparison reports/pipe_grud/no_current_chla/pipe_grud_persistence_comparison_smoke.csv \
  --blend-weights reports/pipe_grud/no_current_chla/pipe_grud_output_blend_weights_smoke.csv \
  --blend-search reports/pipe_grud/no_current_chla/pipe_grud_output_blend_search_smoke.csv \
  --training-curve reports/pipe_grud/no_current_chla/pipe_grud_training_curve_smoke.csv \
  --examples reports/pipe_grud/no_current_chla/pipe_grud_prediction_examples_smoke.csv \
  --report reports/pipe_grud/no_current_chla/pipe_grud_report_smoke.md \
  --manifest reports/pipe_grud/no_current_chla/pipe_grud_manifest_smoke.json \
  --history-length 12 \
  --hidden-dim 96 \
  --mse-weight 1.0 \
  --epochs 2 \
  --batch-size 2048 \
  --max-train-windows 50000 \
  --max-eval-windows 20000 \
  --max-examples 200 \
  --progress-every-batches 25
```

Backtest validation and test with target-only observed states. The first
bounded backtest may be deterministic to verify state behavior quickly:

```bash
poetry run python src/experiments/evaluate_pipe_grud_rollouts.py \
  --sequences data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet \
  --model models/pipe_grud/no_current_chla/pipe_grud_model_smoke.pt \
  --model-manifest reports/pipe_grud/no_current_chla/pipe_grud_manifest_smoke.json \
  --split validation \
  --observed-state-source target \
  --rollout-horizon 3 \
  --deterministic \
  --max-origins 512 \
  --batch-size 256 \
  --disable-calibrated-bloom \
  --metrics reports/pipe_grud/no_current_chla/pipe_rollout_backtest_metrics_validation_smoke.csv \
  --alert-metrics reports/pipe_grud/no_current_chla/pipe_rollout_backtest_alert_metrics_validation_smoke.csv \
  --examples reports/pipe_grud/no_current_chla/pipe_rollout_backtest_examples_validation_smoke.csv \
  --backtest-rows reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation_smoke.parquet \
  --report reports/pipe_grud/no_current_chla/pipe_rollout_backtest_report_validation_smoke.md \
  --manifest reports/pipe_grud/no_current_chla/pipe_rollout_backtest_manifest_validation_smoke.json
```

```bash
poetry run python src/experiments/evaluate_pipe_grud_rollouts.py \
  --sequences data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet \
  --model models/pipe_grud/no_current_chla/pipe_grud_model_smoke.pt \
  --model-manifest reports/pipe_grud/no_current_chla/pipe_grud_manifest_smoke.json \
  --split test \
  --observed-state-source target \
  --rollout-horizon 3 \
  --deterministic \
  --max-origins 512 \
  --batch-size 256 \
  --disable-calibrated-bloom \
  --metrics reports/pipe_grud/no_current_chla/pipe_rollout_backtest_metrics_test_smoke.csv \
  --alert-metrics reports/pipe_grud/no_current_chla/pipe_rollout_backtest_alert_metrics_test_smoke.csv \
  --examples reports/pipe_grud/no_current_chla/pipe_rollout_backtest_examples_test_smoke.csv \
  --backtest-rows reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test_smoke.parquet \
  --report reports/pipe_grud/no_current_chla/pipe_rollout_backtest_report_test_smoke.md \
  --manifest reports/pipe_grud/no_current_chla/pipe_rollout_backtest_manifest_test_smoke.json
```

Calibrate rollout bloom probabilities and policy thresholds on validation:

```bash
poetry run python src/experiments/calibrate_pipe_rollout_alerts.py \
  --backtest-rows reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation_smoke.parquet \
  --backtest-rows reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test_smoke.parquet \
  --calibrator-dir models/pipe_grud/no_current_chla/rollout_calibrators_smoke \
  --thresholds reports/pipe_grud/no_current_chla/pipe_rollout_calibration_thresholds_smoke.csv \
  --metrics reports/pipe_grud/no_current_chla/pipe_rollout_calibration_metrics_smoke.csv \
  --calibrated-rows reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows_smoke.parquet \
  --report reports/pipe_grud/no_current_chla/pipe_rollout_calibration_report_smoke.md \
  --manifest reports/pipe_grud/no_current_chla/pipe_rollout_calibration_manifest_smoke.json \
  --selection-objective fbeta \
  --fbeta-beta 2.0
```

Compare alert policies:

```bash
poetry run python src/experiments/compare_pipe_rollout_alert_policies.py \
  --calibrated-rows reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows_smoke.parquet \
  --thresholds reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_thresholds_smoke.csv \
  --metrics reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_metrics_smoke.csv \
  --report reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_report_smoke.md \
  --manifest reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_manifest_smoke.json
```

If the deterministic policy frontier degenerates, rerun the validation and test
backtests with stochastic rollouts before interpreting alert-policy tradeoffs.
With a single deterministic sample, `alert_probability_irc` is binary (`0` or
`1`), so `irc_alert` policy selection can collapse to either alert-none/subset
or alert-all behavior.

Stochastic validation smoke:

```bash
poetry run python src/experiments/evaluate_pipe_grud_rollouts.py \
  --sequences data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet \
  --model models/pipe_grud/no_current_chla/pipe_grud_model_smoke.pt \
  --model-manifest reports/pipe_grud/no_current_chla/pipe_grud_manifest_smoke.json \
  --split validation \
  --observed-state-source target \
  --rollout-horizon 3 \
  --samples 128 \
  --max-origins 512 \
  --batch-size 256 \
  --disable-calibrated-bloom \
  --metrics reports/pipe_grud/no_current_chla/pipe_rollout_backtest_metrics_validation_stochastic_smoke.csv \
  --alert-metrics reports/pipe_grud/no_current_chla/pipe_rollout_backtest_alert_metrics_validation_stochastic_smoke.csv \
  --examples reports/pipe_grud/no_current_chla/pipe_rollout_backtest_examples_validation_stochastic_smoke.csv \
  --backtest-rows reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation_stochastic_smoke.parquet \
  --report reports/pipe_grud/no_current_chla/pipe_rollout_backtest_report_validation_stochastic_smoke.md \
  --manifest reports/pipe_grud/no_current_chla/pipe_rollout_backtest_manifest_validation_stochastic_smoke.json
```

Stochastic test smoke:

```bash
poetry run python src/experiments/evaluate_pipe_grud_rollouts.py \
  --sequences data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet \
  --model models/pipe_grud/no_current_chla/pipe_grud_model_smoke.pt \
  --model-manifest reports/pipe_grud/no_current_chla/pipe_grud_manifest_smoke.json \
  --split test \
  --observed-state-source target \
  --rollout-horizon 3 \
  --samples 128 \
  --max-origins 512 \
  --batch-size 256 \
  --disable-calibrated-bloom \
  --metrics reports/pipe_grud/no_current_chla/pipe_rollout_backtest_metrics_test_stochastic_smoke.csv \
  --alert-metrics reports/pipe_grud/no_current_chla/pipe_rollout_backtest_alert_metrics_test_stochastic_smoke.csv \
  --examples reports/pipe_grud/no_current_chla/pipe_rollout_backtest_examples_test_stochastic_smoke.csv \
  --backtest-rows reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test_stochastic_smoke.parquet \
  --report reports/pipe_grud/no_current_chla/pipe_rollout_backtest_report_test_stochastic_smoke.md \
  --manifest reports/pipe_grud/no_current_chla/pipe_rollout_backtest_manifest_test_stochastic_smoke.json
```

Calibrate and compare policies on stochastic rows:

```bash
poetry run python src/experiments/calibrate_pipe_rollout_alerts.py \
  --backtest-rows reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation_stochastic_smoke.parquet \
  --backtest-rows reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test_stochastic_smoke.parquet \
  --calibrator-dir models/pipe_grud/no_current_chla/rollout_calibrators_stochastic_smoke \
  --thresholds reports/pipe_grud/no_current_chla/pipe_rollout_calibration_thresholds_stochastic_smoke.csv \
  --metrics reports/pipe_grud/no_current_chla/pipe_rollout_calibration_metrics_stochastic_smoke.csv \
  --calibrated-rows reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows_stochastic_smoke.parquet \
  --report reports/pipe_grud/no_current_chla/pipe_rollout_calibration_report_stochastic_smoke.md \
  --manifest reports/pipe_grud/no_current_chla/pipe_rollout_calibration_manifest_stochastic_smoke.json \
  --selection-objective fbeta \
  --fbeta-beta 2.0
```

```bash
poetry run python src/experiments/compare_pipe_rollout_alert_policies.py \
  --calibrated-rows reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows_stochastic_smoke.parquet \
  --thresholds reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_thresholds_stochastic_smoke.csv \
  --metrics reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_metrics_stochastic_smoke.csv \
  --report reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_report_stochastic_smoke.md \
  --manifest reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_manifest_stochastic_smoke.json
```

## Smoke Snapshot

The bounded no-current-Chl-a smoke run is technically valid and
methodologically informative, but it is not strong enough to support a final
operational claim.

The stochastic backtests fix the deterministic policy-frontier collapse:
`alert_probability_irc` has many unique values per horizon instead of binary
`0/1` outputs. On held-out test rows, IRC alert PR-AUC is approximately
`0.53`, `0.54`, and `0.50` for horizons 1, 2, and 3. This is materially better
than the deterministic smoke frontier and gives automatic policies a real
threshold surface.

The direct `bloom_h` signal remains weak. Test PR-AUC is approximately `0.19`,
`0.21`, and `0.17`, with precision often close to the base rate unless the
policy becomes very conservative. This should be reported as a limitation of
the bounded smoke run, not hidden behind high-recall thresholds.

On test `irc_alert`, the stochastic frontier shows three useful operating
regions:

- `fbeta`: very high recall (`~0.99`) but near alert-all behavior
  (`~0.99` alert rate);
- `closest_pr`: high recall (`~0.82`) with modest precision (`~0.36`) and high
  alert rate (`~0.79`);
- `balanced_accuracy`/`mcc`: lower recall (`~0.20-0.42`) with higher precision
  (`~0.49-0.72`) and lower alert rate (`~0.10-0.31`).

The next justified step is a thesis-scale no-current-Chl-a run focused on IRC
alert behavior and explicit comparison against the Chl-a-aware surface. Direct
`bloom_h` prediction should remain a secondary diagnostic until a full run
shows stronger evidence.

## Full Training Snapshot

The thesis-scale no-current-Chl-a PIPE/GRU-D training run used the same core
configuration as the promoted Chl-a-aware model: history length `12`, hidden
dimension `96`, MSE weight `1.0`, batch size `2048`, and `20` epochs. It used
all available windows: `378,557` train, `22,087` validation, and `17,420` test.

Held-out test performance shows useful signal without current observed Chl-a:

- all-state RMSE improves over no-current persistence by `30.7%`;
- all-state MAE improves over no-current persistence by `35.3%`;
- `yT` RMSE improves by `18.1%` and MAE by `20.1%`;
- `sigma_T` RMSE improves by `62.7%` and MAE by `70.7%`;
- `delta_yT` RMSE improves by `17.1%` and MAE by `11.5%`.

The no-current model is still worse than the promoted Chl-a-aware model on
biological/thermal channels. On test, all-state RMSE is `0.1359` versus
`0.1091`; `yT` RMSE is `0.3354` versus `0.2037`; and `sigma_T` RMSE is
`0.1576` versus `0.0758`. This is expected and important: removing current
Chl-a makes the problem harder, but the model does not collapse to persistence.

The next full-stage evidence must come from stochastic rollout backtests,
rollout calibration, and policy-frontier comparison using the full no-current
model.

## Full Rollout Snapshot

The full stochastic no-current-Chl-a rollout backtests were run with
`samples=128`, `observed_state_source=target`, no `max_origins` cap, and no
calibrated bloom probabilities. Validation used `16,260` complete-horizon
origins (`48,780` rollout rows), and test used `13,327` complete-horizon
origins (`39,981` rollout rows).

Held-out test state behavior remains positive against no-current persistence:

- all-state RMSE improvement is `28.9%`, `22.6%`, and `21.1%` at horizons
  1, 2, and 3;
- `irc1` RMSE improvement is `16.8%`, `19.5%`, and `19.9%`;
- `yT` RMSE improvement is `17.5%`, `20.0%`, and `20.0%`;
- `sigma_T` RMSE improvement is `63.2%`, `40.1%`, and `37.5%`.

The fixed `irc_alert` threshold is useful but conservative. On test, PR-AUC is
`0.6532`, `0.6346`, and `0.6147`; Brier is `0.1805`, `0.1852`, and `0.1967`;
and recall is `0.4777`, `0.3724`, and `0.2931` at horizons 1, 2, and 3.
`alert_probability_irc` remains continuous enough for policy selection, with
`129`, `116`, and `111` unique values by test horizon.

The Chl-a-aware full surface remains substantially stronger. On the same test
origin counts, its `irc_alert` PR-AUC is `0.8894`, `0.8769`, and `0.8702`, with
fixed-threshold recall `0.7826`, `0.7244`, and `0.6853`. Therefore the
no-current result should be framed as retained early-warning signal, not as a
replacement for Chl-a-aware monitoring.

The next step is full no-current rollout calibration and policy-frontier
comparison. Only after that comparison should artifacts be promoted through
DVC.

## Full Calibration And Policy Snapshot

Full no-current-Chl-a rollout calibration used validation rows only, with
F-beta beta `2.0` and minimum recall `0.5`. It completed on `88,761`
validation/test rollout rows and fitted three horizon-specific isotonic
calibrators for `bloom_h`.

The F2 calibration confirms the same tradeoff seen in smoke runs. For
`irc_alert`, test recall is very high (`0.9620`, `0.9976`, `1.0000`), but the
alert rate is also very high (`0.8956`, `0.9753`, `0.9923`). For direct
`bloom_h`, test recall is also high (`0.8805`, `0.9469`, `0.9787`), but
precision remains close to prevalence (`0.1437`, `0.1502`, `0.1455`) and the
alert rate is excessive (`0.7616`, `0.8186`, `0.8982`).

The automatic policy frontier is therefore more informative than the F2
calibration alone:

- `irc_alert` `closest_pr`: recall `0.8564`, precision `0.4215`, alert rate
  `0.7026`, F2 `0.7097`;
- `irc_alert` `f1`: recall `0.8250`, precision `0.4347`, alert rate `0.6580`,
  F2 `0.6986`;
- `irc_alert` `balanced_accuracy`: recall `0.5456`, precision `0.6137`, alert
  rate `0.3086`, F2 `0.5575`;
- `irc_alert` `mcc`: recall `0.4768`, precision `0.6711`, alert rate `0.2457`,
  F2 `0.5061`;
- `irc_alert` `fixed`: recall `0.3811`, precision `0.7212`, alert rate
  `0.1834`, F2 `0.4181`.

For `bloom_h`, the best full no-current policies remain weak compared with the
Chl-a-aware surface. The average test PR-AUC is only `0.2716`; the
`balanced_accuracy` profile has recall `0.7807`, precision `0.1794`, and alert
rate `0.5623`; and the `mcc` profile increases precision to `0.4439` only by
dropping recall to `0.1880`.

Compared with the Chl-a-aware policy frontier, the no-current surface can
recover useful `irc_alert` recall only by accepting much higher alert volume
and lower precision. For example, Chl-a-aware `closest_pr` averages recall
`0.8429`, precision `0.7572`, and alert rate `0.3851`, whereas no-current
`closest_pr` averages recall `0.8564`, precision `0.4215`, and alert rate
`0.7026`.

This result is valuable as a thesis-scale early-warning sensitivity surface.
It should not replace the Chl-a-aware operational surface. A defensible reading
is:

- current Chl-a is highly informative for operational alert quality;
- without current Chl-a, nutrients, physicochemistry, seasonality, and
  non-target-proximal history still carry early-warning signal;
- the cost of removing current Chl-a is lower precision and substantially more
  alerts for comparable recall;
- direct `bloom_h` prediction remains a limitation, while `irc_alert` is the
  stronger no-current endpoint.

## Full Execution

After the smoke is reviewed, rerun the same sequence with unbounded or
thesis-scale training settings and without `smoke` suffixes. The full run
should then be promoted through DVC for:

- `data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet`;
- `models/pipe_grud/no_current_chla/**`;
- row-level parquet backtest/calibrated-row outputs under
  `reports/pipe_grud/no_current_chla/`.

Small CSV, JSON, and Markdown reports should remain in Git.

## Minimum Review Questions

- Does the no-current-Chl-a sequence manifest show the expected input mapping?
- Are validation and test backtests using `observed_state_source = target`?
- Does PIPE/GRU-D beat no-current-Chl-a persistence on held-out `all`, `yT`,
  and `irc1` state metrics?
- Are bloom and IRC alert metrics materially worse than the Chl-a-aware
  surface, and by how much?
- Do nutrients and physicochemical variables carry enough signal to justify a
  strict early-warning claim, or is the correct result a documented limitation?

## Operational Coverage Audit

Before designing a stronger no-current-Chl-a model surface, audit whether rows
with Chl-a targets have enough non-Chl-a precursor evidence at the origin
month. This separates ecological interpretation from data-surface coverage.

```bash
poetry run python src/experiments/audit_no_chla_operational_surface.py
```

The audit treats current Chl-a columns as forbidden predictors. They are counted
only as diagnostic references. Evidence bands are defined as:

- `high`: nutrient evidence plus temperature plus either light proxy or
  physicochemical evidence;
- `medium`: nutrient evidence plus at least one nonseason companion group;
- `low`: at least one nonseason exogenous group, but not enough for `medium`;
- `season_only`: no nonseason exogenous group is available at the origin month.

The output report is
`reports/pipe_grud/no_current_chla/no_chla_operational_surface_audit_report.md`.

## Operational Coverage Audit Snapshot

The full audit was generated at UTC `2026-06-12T22:04:00.174841+00:00`
and checked `4,610,977` source-scoped target rows across `93,310` sites.

Global coverage shows that the full no-current-Chl-a surface is not uniformly
supported by exogenous evidence:

- rows with any nutrient precursor: `0.1644`;
- rows with high precursor readiness: `0.1167`;
- rows with season-only non-Chl-a evidence: `0.6919`;
- rows where forbidden current Chl-a exists but must not be used: `0.9762`.

The source split explains the weak no-current-Chl-a result. AquaMatch supplies
many Chl-a targets, but under the current source-scoped policy it supplies no
origin-month nutrient, temperature, light-proxy, or physicochemical predictors:
`any_nutrient = 0.0000`, `high = 0.0000`, and `season_only = 1.0000` for
validation and test horizons. Those rows are valid target evidence, but they
are not a fair test of nutrient-driven early warning unless cross-source site
equivalence is accepted later.

WQP is the first appropriate source for a strict no-current-Chl-a early-warning
test. In held-out test rows, WQP has strong nutrient coverage:

| horizon | rows | bloom rate | any nutrient | high readiness | season only |
|---:|---:|---:|---:|---:|---:|
| 1 | `55,151` | `0.1620` | `0.8682` | `0.4772` | `0.0075` |
| 2 | `50,423` | `0.1776` | `0.8770` | `0.4705` | `0.0066` |
| 3 | `43,696` | `0.1815` | `0.8916` | `0.4687` | `0.0054` |

LakeBeD-US-CSE also has useful precursor coverage, but the held-out row counts
are small (`163`, `151`, and `143` test rows for horizons 1, 2, and 3).

This audit changes the interpretation of the no-current-Chl-a experiment. The
full-surface weakness should not be read as evidence that nutrients are
ecologically unimportant. It is evidence that the current source-scoped
training surface combines many Chl-a targets with no usable non-Chl-a precursor
information at the same source-site-month. The next fair experiment should
therefore be a WQP-focused no-current-Chl-a surface. A crosswalk-enabled
AquaMatch/WQP expansion should be considered only after accepted site
equivalences are promoted.

## WQP-Focused No-Current-Chl-a Surface

The WQP-focused variant keeps the same no-current-Chl-a input contract but
restricts sequence construction to `source_id = wqp`. This makes the first
strict early-warning refinement focus on rows where nutrient and precursor
coverage are actually available under the source-scoped policy.

Build the filtered sequence surface first:

```bash
poetry run python src/experiments/build_pipe_sequences.py \
  --input-surface no_current_chla \
  --source-ids wqp \
  --sequences data/pipe_grud/pipe_sequence_dataset_no_current_chla_wqp_focused_v0.parquet \
  --summary reports/pipe_grud/no_current_chla_wqp_focused/pipe_sequence_summary.csv \
  --discarded reports/pipe_grud/no_current_chla_wqp_focused/pipe_sequence_discarded_summary.csv \
  --report reports/pipe_grud/no_current_chla_wqp_focused/pipe_sequence_report.md \
  --manifest reports/pipe_grud/no_current_chla_wqp_focused/pipe_sequence_manifest.json
```

Review this sequence manifest before training. It should show:

- `input_surface = no_current_chla`;
- `source_ids = ["wqp"]`;
- only `wqp` rows in `by_source_split`;
- the no-current-Chl-a mapping `x_yT <- yT_no_chla`,
  `x_sigma_T <- sigma_T_no_chla`, and
  `x_delta_yT <- delta_yT_no_chla`.

If the filtered sequence surface is healthy, proceed to a bounded smoke
training run under `reports/pipe_grud/no_current_chla_wqp_focused/` and
`models/pipe_grud/no_current_chla_wqp_focused/`.

## WQP-Focused Full Snapshot

The WQP-focused full run evaluates the strict no-current-Chl-a contract on the
source where precursor nutrient evidence is actually available under the
source-scoped policy. This is a different surface from the full all-source
no-current-Chl-a run above and should be reported separately.

The sequence manifest is
`reports/pipe_grud/no_current_chla_wqp_focused/pipe_sequence_manifest.json`.
It records `986,674` kept sequence rows from `43,715` source-scoped sites:
`808,970` train rows, `91,226` validation rows, and `86,478` test rows.

The full training manifest is
`reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_manifest.json`.
It used history length `12`, hidden dimension `96`, MSE weight `1.0`, batch
size `2048`, `20` epochs, and all available windows. Held-out test performance
improved over WQP-focused no-current persistence:

- all-state RMSE improvement `31.8%` and MAE improvement `30.8%`;
- `yT` RMSE improvement `25.8%` and MAE improvement `26.7%`;
- `sigma_T` RMSE improvement `59.5%` and MAE improvement `60.8%`;
- `delta_yT` RMSE improvement `34.1%` and MAE improvement `28.6%`.

Full stochastic rollout backtests used `samples=128`,
`observed_state_source=target`, rollout horizon `3`, and no `max_origins` cap.
The validation manifest is
`reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_manifest_validation.json`
(`5,069` complete-horizon origins, `15,207` rollout rows). The test manifest is
`reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_manifest_test.json`
(`6,145` complete-horizon origins, `18,435` rollout rows).

Held-out test rollout state behavior is positive at all horizons:

| horizon | all RMSE improvement | irc1 RMSE improvement | irc1 MAE improvement |
|---:|---:|---:|---:|
| 1 | `0.3107` | `0.2378` | `0.2196` |
| 2 | `0.2592` | `0.2658` | `0.2740` |
| 3 | `0.2264` | `0.2901` | `0.3082` |

With the fixed `0.5` IRC alert threshold, held-out test alert quality remains
useful through horizon 3:

| horizon | PR-AUC | ROC-AUC | Brier | recall | precision | alert rate |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | `0.7963` | `0.8335` | `0.1684` | `0.7579` | `0.7007` | `0.4915` |
| 2 | `0.7456` | `0.8176` | `0.1754` | `0.6903` | `0.7456` | `0.4343` |
| 3 | `0.7276` | `0.8048` | `0.1857` | `0.6283` | `0.7441` | `0.4037` |

Full calibration and policy-frontier comparison were written to:

- `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibration_manifest.json`;
- `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_policy_2b_manifest.json`.

The F2 calibration remains a high-recall sensitivity profile rather than a
default policy. On held-out test rows, it reaches recall `0.9620`, `0.9941`,
and `0.9894`, but alert rates are also high: `0.7707`, `0.8923`, and `0.8788`
for horizons 1, 2, and 3.

The 2B frontier is more suitable for operational interpretation:

| policy | h1 recall / precision / alert rate | h2 recall / precision / alert rate | h3 recall / precision / alert rate |
|---|---|---|---|
| `closest_pr` | `0.7636 / 0.6976 / 0.4973` | `0.8287 / 0.6903 / 0.5632` | `0.8907 / 0.6478 / 0.6574` |
| `balanced_accuracy` | `0.7350 / 0.7155 / 0.4667` | `0.7461 / 0.7324 / 0.4779` | `0.7941 / 0.7148 / 0.5312` |
| `fixed` | `0.7579 / 0.7007 / 0.4915` | `0.6903 / 0.7456 / 0.4343` | `0.6283 / 0.7441 / 0.4037` |
| `fbeta` | `0.9620 / 0.5671 / 0.7707` | `0.9941 / 0.5227 / 0.8923` | `0.9894 / 0.5383 / 0.8788` |

The provisional interpretation is:

- WQP-focused no-current-Chl-a is the fair source-scoped test of nutrient and
  physicochemical early-warning signal;
- it retains useful multi-horizon IRC alert skill without current Chl-a;
- `closest_pr` remains a defensible experimental 2B default when recall is
  prioritized without accepting F2's alert volume;
- `balanced_accuracy`/`mcc` should be reported as conservative operational
  alternatives, especially if alert burden matters;
- direct `bloom_h` calibration now has real support, but it remains secondary
  to `irc_alert` for the no-current-Chl-a claim.
