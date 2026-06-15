# PIPE Neural ODE Protocol

This note opens the Neural ODE branch of PIPE. It is a temporal variant of the
robust PIPE line, not a replacement for PIPE/GRU-D and not a shortcut around
adaptive ANFIS or MIFAL.

## Position In The Project

The project compares several temporal surfaces over compatible state vectors:

- lightweight PIPE with expert/refined fuzzy state;
- no-current-Chl-a lightweight PIPE for stricter early warning;
- robust PIPE with adaptive ANFIS state;
- PIPE Neural ODE as an alternative temporal transition model;
- MIFAL-ED/T2 as a required comparison family.

Neural ODE must be attempted and evaluated. If it is unstable, does not
converge, or does not improve useful metrics, that result is documented as
negative or inconclusive rather than omitted. A failure does not block thesis
closure, but the attempt and evidence are part of the planned work.

## Model Definition

The v0 model uses the frozen PIPE sequence schema and predicts the next monthly
state:

```text
S(t) -> S(t + 1)
dS/dt = f_theta(S, season, tau)
```

Where:

- `S(t)` is the 9-dimensional PIPE state:
  `yN`, `yF`, `yT`, `sigma_N`, `sigma_F`, `sigma_T`, `delta_yN`,
  `delta_yF`, `delta_yT`;
- `season` is the monthly annual and semiannual sine/cosine context already
  emitted by `build_pipe_sequences.py`;
- `tau` is the normalized integration time inside the monthly transition;
- outputs are a mean next state and diagonal Gaussian uncertainty.

The first implementation is intentionally one-step. Recursive rollouts,
calibration, 2B policy comparison, and controlled degradation are later gates
that should only run after one-step and real-data smoke checks are healthy.

## Stability Guardrails

The v0 runner applies conservative guardrails:

- bounded state channels for `y*` and `sigma_*` in `[0, 1]`;
- bounded `delta_*` channels in `[-1, 1]`;
- derivative scaling through `tanh`;
- gradient clipping;
- validation-selected checkpoint;
- validation-selected output blend against persistence.

The output blend has the same interpretation as the PIPE/GRU-D runner:
`blend_weight = 0` means pure persistence and `blend_weight = 1` means pure
Neural ODE prediction. This makes early Neural ODE evidence comparable with
the existing temporal baselines while avoiding overclaiming unstable channels.

## Gates

Gate 1, synthetic smoke:

- use `--synthetic-smoke`;
- verify that the script writes model, checkpoint, metrics, comparison,
  examples, report, and manifest;
- require status `completed`;
- require non-empty train, validation, and test transitions;
- inspect whether validation loss decreases when epochs are increased.

Gate 2, real bounded smoke:

- use the adaptive WQP-focused sequence dataset first:
  `data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet`;
- keep a small epoch count and bounded sampled windows;
- compare one-step validation/test against persistence;
- do not promote artifacts until the report and manifest are reviewed.

Gate 3, full one-step run:

- scale sampled windows and epochs only if Gate 2 is numerically stable;
- compare against the full adaptive PIPE/GRU-D one-step evidence;
- preserve a clear negative result if persistence or PIPE/GRU-D dominates.

Gate 4, recursive evaluation:

- implement Neural ODE rollouts only after a sane full one-step run;
- reuse row-level backtest columns where possible so calibration and 2B policy
  tools can compare Neural ODE with PIPE/GRU-D.

Gate 5, synthesis:

- compare Neural ODE with persistence, lightweight PIPE/GRU-D, no-current
  lightweight PIPE/GRU-D, adaptive PIPE/GRU-D, and later MIFAL;
- include controlled degradation only after Neural ODE row-level rollouts exist.

## Initial Commands

Synthetic smoke:

```bash
poetry run python src/experiments/train_pipe_neural_ode.py \
  --synthetic-smoke \
  --synthetic-sites 16 \
  --synthetic-months-per-split 24 \
  --epochs 20 \
  --batch-size 128 \
  --hidden-dim 64 \
  --depth 2 \
  --ode-method rk4 \
  --ode-step-size 0.25 \
  --report reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_report.md \
  --manifest reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_manifest.json \
  --metrics reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_metrics.csv \
  --persistence-metrics reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_persistence_metrics.csv \
  --comparison reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_persistence_comparison.csv \
  --blend-weights reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_output_blend_weights.csv \
  --blend-search reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_output_blend_search.csv \
  --training-curve reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_training_curve.csv \
  --examples reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_prediction_examples.csv \
  --model models/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_model_v0.pt \
  --checkpoint models/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_checkpoint_v0.pt
```

Real bounded smoke:

```bash
poetry run python src/experiments/train_pipe_neural_ode.py \
  --sequences data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet \
  --sequence-manifest reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_manifest.json \
  --epochs 3 \
  --batch-size 2048 \
  --hidden-dim 64 \
  --depth 2 \
  --max-train-windows 50000 \
  --max-eval-windows 20000 \
  --report reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_report.md \
  --manifest reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_manifest.json \
  --metrics reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_metrics.csv \
  --persistence-metrics reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_persistence_metrics.csv \
  --comparison reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_persistence_comparison.csv \
  --blend-weights reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_output_blend_weights.csv \
  --blend-search reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_output_blend_search.csv \
  --training-curve reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_training_curve.csv \
  --examples reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_prediction_examples.csv \
  --model models/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_model_v0.pt \
  --checkpoint models/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_checkpoint_v0.pt
```

## Evidence To Review

After each run, inspect:

- `pipe_neural_ode_report.md`;
- `pipe_neural_ode_manifest.json`;
- `pipe_neural_ode_training_curve.csv`;
- `pipe_neural_ode_persistence_comparison.csv`;
- `pipe_neural_ode_output_blend_weights.csv`;
- `pipe_neural_ode_prediction_examples.csv`.

Promotion requires a clean report, a reproducible manifest, and an explicit
decision about whether Neural ODE is learning useful temporal signal or only
falling back to persistence.

## Gate 1 Synthetic Smoke Result

The first synthetic smoke completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_report.md`;
- `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_manifest.json`;
- `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_training_curve.csv`;
- `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_persistence_comparison.csv`;
- `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_output_blend_weights.csv`;
- `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_prediction_examples.csv`.

Status: `completed`.

Geometry:

- train transitions: `384`;
- validation transitions: `384`;
- test transitions: `384`.

Selection:

- best epoch: `10`;
- validation all-state RMSE/MAE: `0.0111` / `0.0087`;
- validation balanced selection objective: `0.7168`.

One-step comparison against persistence:

- train all-state RMSE/MAE improvement: `29.89%` / `25.80%`;
- validation all-state RMSE/MAE improvement: `29.68%` / `26.95%`;
- test all-state RMSE/MAE improvement: `31.57%` / `27.80%`.

Interpretation:

- Gate 1 passes as an implementation and optimization smoke: the runner writes
  complete artifacts, learns the synthetic dynamics, preserves bounded states,
  and improves global one-step error against persistence.
- Several channels select `blend_weight = 0`, which is acceptable in this
  synthetic gate because those channels are nearly persistence-optimal.
- The diagonal uncertainty intervals are intentionally treated as provisional:
  90% coverage is `1.0`, but interval widths are very broad. The real-data
  smoke must inspect interval width and coverage before any uncertainty claim.

Decision: proceed to Gate 2 real bounded smoke over the adaptive WQP-focused
PIPE sequence dataset. Do not promote Neural ODE model artifacts yet.

## Gate 2 Real Bounded Smoke Result

The first real adaptive WQP-focused bounded smoke completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_training_curve.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_persistence_comparison.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_output_blend_weights.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_prediction_examples.csv`.

Status: `completed`.

Geometry:

- available train/validation/test transitions: `808,970` / `91,226` /
  `86,478`;
- sampled train/validation/test transitions: `50,000` / `20,000` / `20,000`.

Selection:

- epochs: `3`;
- best epoch: `3`;
- validation all-state RMSE/MAE: `0.1500` / `0.0855`;
- validation balanced selection objective: `0.9828`.

One-step comparison against persistence:

- train all-state RMSE/MAE improvement: `3.24%` / `-1.11%`;
- validation all-state RMSE/MAE improvement: `3.14%` / `0.29%`;
- test all-state RMSE/MAE improvement: `3.26%` / `0.47%`.

Interpretation:

- Gate 2 passes as a real-data execution smoke: the runner loads the intended
  adaptive WQP-focused sequence dataset, samples the requested transitions, and
  writes complete reproducible artifacts.
- It is not yet strong model evidence. The improvement over persistence is
  small, and most channels select `blend_weight = 0`.
- The clearest learned channel is `delta_yT`, with test RMSE improvement
  `11.59%` and MAE improvement `2.66%`; `delta_yF` and `yT` show small RMSE
  gains with MAE trade-offs.
- Best epoch occurs at the final requested epoch, so the run is under-trained
  for judging convergence.

Decision: run an extended real smoke before any full-scale training or rollout
implementation. Do not promote Neural ODE model artifacts yet.

## Gate 2B Extended Real Smoke Result

The extended adaptive WQP-focused smoke completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_training_curve.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_persistence_comparison.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_output_blend_weights.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_prediction_examples.csv`.

Status: `completed`.

Configuration changes relative to Gate 2:

- hidden dimension increased from `64` to `96`;
- derivative scale increased from `0.25` to `0.5`;
- epochs increased from `3` to `20`;
- sampled train/validation/test transitions increased to
  `200,000` / `50,000` / `50,000`.

Selection:

- best epoch: `11`;
- validation all-state RMSE/MAE: `0.1177` / `0.0678`;
- validation balanced selection objective: `0.7837`.

One-step comparison against persistence:

- train all-state RMSE/MAE improvement: `23.67%` / `18.65%`;
- validation all-state RMSE/MAE improvement: `23.31%` / `19.95%`;
- test all-state RMSE/MAE improvement: `23.74%` / `20.61%`.

Strongest channels on test:

- `delta_yF` RMSE/MAE improvement: `43.16%` / `39.27%`;
- `delta_yN` RMSE/MAE improvement: `41.90%` / `39.77%`;
- `delta_yT` RMSE/MAE improvement: `41.02%` / `36.81%`;
- `yT` RMSE improvement: `9.08%`, with a MAE trade-off of `-4.14%`.

Interpretation:

- Gate 2B shows real temporal signal and is no longer merely a smoke of
  execution.
- The model remains most useful for change channels, while uncertainty channels
  still select persistence.
- Direct comparison to adaptive PIPE/GRU-D remains pending, but the full
  adaptive PIPE/GRU-D one-step test all-state RMSE/MAE was `0.1097` / `0.0677`;
  this extended Neural ODE smoke test is `0.1213` / `0.0709`, so it is promising
  but not yet the stronger temporal model.
- The best epoch is internal, not the last epoch, so the run is sufficiently
  long for a first convergence check.

Decision: proceed to a full one-step adaptive WQP-focused Neural ODE run using
the same configuration family before implementing recursive rollouts.

## Gate 3 Full One-Step Result

The full adaptive WQP-focused one-step run completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_training_curve.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_persistence_comparison.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_output_blend_weights.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_prediction_examples.csv`.

Status: `completed`.

Geometry:

- train transitions: `808,970`;
- validation transitions: `91,226`;
- test transitions: `86,478`.

Selection:

- best epoch: `15`;
- validation all-state RMSE/MAE: `0.1169` / `0.0673`;
- validation balanced selection objective: `0.7794`.

One-step comparison against persistence:

- train all-state RMSE/MAE improvement: `24.13%` / `19.42%`;
- validation all-state RMSE/MAE improvement: `23.76%` / `20.35%`;
- test all-state RMSE/MAE improvement: `24.28%` / `21.10%`.

Strongest channels on test:

- `delta_yF` RMSE/MAE improvement: `43.11%` / `38.90%`;
- `delta_yN` RMSE/MAE improvement: `41.55%` / `42.33%`;
- `delta_yT` RMSE/MAE improvement: `41.06%` / `38.39%`;
- `yT` RMSE improvement: `10.24%`, with a MAE trade-off of `-3.48%`.

Interpretation:

- Full one-step training confirms the extended-smoke signal and improves
  slightly over Gate 2B.
- Neural ODE remains strongest on change channels. Uncertainty channels still
  select persistence in the validation blend.
- Direct one-step comparison remains favorable to adaptive PIPE/GRU-D:
  adaptive PIPE/GRU-D full test all-state RMSE/MAE was `0.1097` / `0.0677`,
  while Neural ODE full test all-state RMSE/MAE is `0.1209` / `0.0708`.
- The result is strong enough to justify recursive rollout evaluation, but not
  strong enough to claim Neural ODE as the best one-step temporal model.

Decision: implement and run recursive Neural ODE rollout backtests over
validation and test before any alert calibration or 2B policy comparison.

## Gate 4 Recursive Rollout Backtest

The Neural ODE rollout evaluator is implemented in
`src/experiments/evaluate_pipe_neural_ode_rollouts.py`. It reuses the same
historical backtest metric builders used by PIPE/GRU-D so Neural ODE can be
compared on compatible state, IRC, and alert tables.

The evaluator is Markovian over `S(t)` and season features. It does not require
a GRU-D history window, but it still selects origins with observed future states
for every requested horizon unless `--allow-partial-horizons` is set.

All-eligible validation backtest:

- completed on 2026-06-15;
- useful as a Neural ODE diagnostic over every Markovian origin with complete
  h1-h3 observed future states;
- not a fair direct model comparison against PIPE/GRU-D because PIPE/GRU-D
  requires a history window and therefore evaluates fewer origins.

Matched-origin validation backtest:

```bash
poetry run python src/experiments/evaluate_pipe_neural_ode_rollouts.py \
  --sequences data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet \
  --splits data/splits/monthly_model_splits_v0.parquet \
  --model models/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_model_v0.pt \
  --model-manifest reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_manifest.json \
  --reference-backtest-rows reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet \
  --split validation \
  --observed-state-source target \
  --samples 128 \
  --batch-size 256 \
  --rollout-horizon 3 \
  --backtest-rows reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_rows_matched_grud_validation.parquet \
  --metrics reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_metrics_matched_grud_validation.csv \
  --alert-metrics reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_alert_metrics_matched_grud_validation.csv \
  --examples reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_examples_matched_grud_validation.csv \
  --report reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_report_matched_grud_validation.md \
  --manifest reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_manifest_matched_grud_validation.json
```

Matched-origin validation result:

- completed on 2026-06-15;
- selected origins: `5,069`;
- evaluated rollout rows: `15,207`;
- all-state RMSE improvement h1/h2/h3 against persistence:
  `25.29%` / `18.33%` / `17.06%`;
- IRC RMSE improvement h1/h2/h3 against persistence:
  `8.45%` / `14.16%` / `19.34%`;
- `irc_alert` PR-AUC h1/h2/h3:
  `0.8632` / `0.8214` / `0.7907`;
- `bloom_h` PR-AUC h1/h2/h3:
  `0.5542` / `0.5107` / `0.4550`.

Comparison with adaptive PIPE/GRU-D on the same validation origins:

- adaptive PIPE/GRU-D all-state RMSE improvement h1/h2/h3:
  `26.27%` / `19.29%` / `19.87%`;
- adaptive PIPE/GRU-D IRC RMSE improvement h1/h2/h3:
  `9.06%` / `15.17%` / `19.90%`;
- adaptive PIPE/GRU-D `irc_alert` PR-AUC h1/h2/h3:
  `0.8703` / `0.8217` / `0.7910`;
- adaptive PIPE/GRU-D `bloom_h` PR-AUC h1/h2/h3:
  `0.5814` / `0.5531` / `0.5115`.

Interpretation:

- Neural ODE preserves useful recursive signal after origin matching.
- Adaptive PIPE/GRU-D remains slightly stronger on validation state RMSE and
  calibrated bloom metrics.
- `irc_alert` behavior is very close: Neural ODE is only marginally below
  PIPE/GRU-D in PR-AUC and has competitive macro-F1.
- Proceed to matched-origin test before deciding whether Neural ODE needs
  dedicated calibration or architectural tuning.

Matched-origin test backtest:

```bash
poetry run python src/experiments/evaluate_pipe_neural_ode_rollouts.py \
  --sequences data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet \
  --splits data/splits/monthly_model_splits_v0.parquet \
  --model models/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_model_v0.pt \
  --model-manifest reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_manifest.json \
  --reference-backtest-rows reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_test.parquet \
  --split test \
  --observed-state-source target \
  --samples 128 \
  --batch-size 256 \
  --rollout-horizon 3 \
  --backtest-rows reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_rows_matched_grud_test.parquet \
  --metrics reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_metrics_matched_grud_test.csv \
  --alert-metrics reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_alert_metrics_matched_grud_test.csv \
  --examples reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_examples_matched_grud_test.csv \
  --report reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_report_matched_grud_test.md \
  --manifest reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_manifest_matched_grud_test.json
```

Matched-origin test result:

- completed on 2026-06-15;
- selected origins: `6,145`;
- evaluated rollout rows: `18,435`;
- all-state RMSE improvement h1/h2/h3 against persistence:
  `24.83%` / `19.11%` / `16.21%`;
- IRC RMSE improvement h1/h2/h3 against persistence:
  `8.54%` / `14.63%` / `19.02%`;
- `irc_alert` PR-AUC h1/h2/h3:
  `0.8952` / `0.8549` / `0.8529`;
- `bloom_h` PR-AUC h1/h2/h3:
  `0.6282` / `0.5883` / `0.5781`.

Comparison with adaptive PIPE/GRU-D on the same test origins:

- adaptive PIPE/GRU-D all-state RMSE improvement h1/h2/h3:
  `25.03%` / `20.66%` / `20.31%`;
- adaptive PIPE/GRU-D IRC RMSE improvement h1/h2/h3:
  `9.58%` / `15.86%` / `19.71%`;
- adaptive PIPE/GRU-D `irc_alert` PR-AUC h1/h2/h3:
  `0.9013` / `0.8630` / `0.8547`;
- adaptive PIPE/GRU-D `bloom_h` PR-AUC h1/h2/h3:
  `0.6559` / `0.6131` / `0.5983`.

Interpretation:

- Neural ODE is a valid temporal extension: it improves persistence in
  recursive h1-h3 rollouts and remains close to adaptive PIPE/GRU-D for IRC
  alert discrimination.
- Adaptive PIPE/GRU-D remains the stronger default for state RMSE and calibrated
  bloom metrics in both validation and test.
- Neural ODE uncertainty intervals have higher empirical coverage than
  PIPE/GRU-D, but they are substantially wider; this is useful as a cautionary
  uncertainty signal, not evidence of sharper calibration.
- Neural ODE should proceed to dedicated calibration/policy checks only as an
  extension and comparison branch, not as a replacement for the adaptive
  PIPE/GRU-D default.

## Gate 5 Alert Calibration

Neural ODE-specific F2 calibration completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibration_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibration_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibration_thresholds.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibration_metrics.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibrated_backtest_rows.parquet`;
- `models/pipe_neural_ode/adaptive_wqp_focused/rollout_calibrators/`.

Status: `completed`.

Configuration:

- calibration split: `validation`;
- evaluation splits: `validation,test`;
- selection objective: `fbeta`;
- F-beta beta: `2.0`;
- bloom score column: `irc_mean`;
- backtest version: `pipe_neural_ode_rollout_backtest_v0`;
- calibration version: `pipe_neural_ode_rollout_alert_calibration_v0`.

Selected F2 thresholds:

- `irc_alert` h1/h2/h3: `0.1797` / `0.1953` / `0.1719`;
- `bloom_h` h1/h2/h3: `0.1409` / `0.1429` / `0.1304`.

Held-out test metrics:

- `irc_alert` recall h1/h2/h3: `0.9372` / `0.9402` / `0.9759`;
- `irc_alert` precision h1/h2/h3: `0.6699` / `0.6095` / `0.5517`;
- `irc_alert` F2 h1/h2/h3: `0.8680` / `0.8482` / `0.8458`;
- `bloom_h` recall h1/h2/h3: `0.7981` / `0.7822` / `0.8505`;
- `bloom_h` precision h1/h2/h3: `0.4680` / `0.4720` / `0.4158`;
- `bloom_h` F2 h1/h2/h3: `0.6994` / `0.6913` / `0.7034`.

Interpretation:

- Neural ODE can support a sensitive F2 alert profile with high held-out recall.
- The trade-off is a high predicted-positive rate, especially at h3
  (`0.7867` for `irc_alert` and `0.3797` for `bloom_h`).
- The calibrated Neural ODE alert surface should be read as a comparison branch
  against adaptive PIPE/GRU-D, not as the project default.

Policy frontier command:

```bash
poetry run python src/experiments/compare_pipe_rollout_alert_policies.py \
  --calibrated-rows reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibrated_backtest_rows.parquet \
  --thresholds reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_thresholds.csv \
  --metrics reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_metrics.csv \
  --report reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_report.md \
  --manifest reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_manifest.json \
  --model-label "PIPE Neural ODE" \
  --policy-version pipe_neural_ode_rollout_alert_policy_2b_v0 \
  --calibration-split validation \
  --evaluation-splits validation,test \
  --selection-objectives fixed,fbeta,f1,mcc,balanced_accuracy,gmean_pr,closest_pr \
  --fbeta-beta 2.0
```

## Gate 5 2B Policy Frontier Result

The Neural ODE-specific 2B policy frontier completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_thresholds.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_metrics.csv`.

Status: `completed`.

Geometry:

- calibrated rows: `33,642`;
- threshold rows: `42`;
- metric rows: `84`;
- calibration split: `validation`;
- evaluation splits: `validation,test`.

Held-out test frontier highlights:

- For `irc_alert` h1, `closest_pr`, `f1`, `mcc`, and `balanced_accuracy`
  converge to threshold `0.3672`, with recall `0.8737`, precision `0.7908`,
  alert rate `0.4583`, F2 `0.8557`, MCC `0.7020`, and balanced accuracy
  `0.8549`.
- For `irc_alert` h2, `closest_pr` gives recall `0.8497`, precision `0.7256`,
  alert rate `0.5071`, and F2 `0.8216`; `mcc` is more conservative with
  recall `0.7336`, precision `0.8254`, and MCC `0.6263`.
- For `irc_alert` h3, `closest_pr` gives recall `0.8288`, precision `0.7143`,
  alert rate `0.5160`, and F2 `0.8030`; `fbeta` raises recall to `0.9759`
  but increases alert rate to `0.7867`.
- For `bloom_h`, `closest_pr` is a balanced profile at h1-h2, while h3
  converges with `balanced_accuracy`, `gmean_pr`, and `mcc` to recall `0.8448`,
  precision `0.4229`, alert rate `0.3708`, and F2 `0.7043`.
- The fixed policy is more conservative, especially for `bloom_h`, but loses
  substantial recall at h2-h3.

Interpretation:

- Neural ODE supports a calibrated, decision-ready comparison branch. It is not
  merely an unstable extension: it improves persistence in one-step and
  recursive rollouts, supports horizon-specific calibration, and yields a
  usable 2B frontier.
- Adaptive PIPE/GRU-D remains the stronger project default because it is
  slightly better on matched-origin state RMSE, IRC RMSE, and bloom
  discrimination, while Neural ODE is closest on `irc_alert`.
- The Neural ODE `fbeta` profile is useful as a sensitive high-recall policy,
  but it should not be treated as the default because of high alert rates,
  especially `irc_alert` h3.
- The Neural ODE `closest_pr` profile is the recommended balanced Neural ODE
  comparison profile. The project-level adaptive default remains PIPE/GRU-D
  `closest_pr`.

Decision:

- close Neural ODE v0 as a calibrated temporal comparison branch;
- keep adaptive PIPE/GRU-D as the default robust PIPE temporal model;
- preserve Neural ODE artifacts for thesis comparison, controlled degradation,
  and later architecture tuning rather than replacing the current default.

## Neural ODE v1 Refinement Protocol

Neural ODE v0 is a valid comparison branch, but it is structurally disadvantaged
relative to adaptive PIPE/GRU-D because v0 is Markovian over the current state
`S(t)`, while PIPE/GRU-D receives a 12-month history window. The v1 refinement
therefore addresses model capacity and training fairness before any new claim
is made.

The first v1 runner is:

- `src/experiments/train_pipe_neural_ode_v1.py`.

It adds a historical encoder while preserving the same frozen PIPE sequence
schema and one-step evaluation surface:

```text
history window -> GRU encoder -> z(t)
dz/dt = f_theta(z, encoded history, season, tau)
z(t + 1), S(t), season -> S(t + 1)
```

Design choices:

- history length defaults to `12`, matching the adaptive PIPE/GRU-D comparison;
- the ODE evolves a latent state rather than directly evolving the bounded
  fuzzy state;
- the decoder predicts a bounded residual from the last observed `S(t)`;
- output blend against persistence is still selected on validation so v1 can
  be compared directly with v0 and PIPE/GRU-D;
- test remains evaluation-only; all architecture and hyperparameter decisions
  must be made from synthetic smoke and validation evidence.

Gate v1.1, synthetic smoke:

```bash
poetry run python src/experiments/train_pipe_neural_ode_v1.py \
  --synthetic-smoke \
  --synthetic-sites 16 \
  --synthetic-months-per-split 24 \
  --history-length 6 \
  --epochs 10 \
  --batch-size 128 \
  --history-hidden-dim 64 \
  --latent-dim 48 \
  --dynamics-hidden-dim 64 \
  --dynamics-depth 2 \
  --ode-method rk4 \
  --ode-step-size 0.25 \
  --report reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_report.md \
  --manifest reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_manifest.json \
  --metrics reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_metrics.csv \
  --persistence-metrics reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_persistence_metrics.csv \
  --comparison reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_persistence_comparison.csv \
  --blend-weights reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_output_blend_weights.csv \
  --blend-search reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_output_blend_search.csv \
  --training-curve reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_training_curve.csv \
  --examples reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_prediction_examples.csv \
  --model models/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_model_v1.pt \
  --checkpoint models/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_checkpoint_v1.pt
```

Gate v1.2, real bounded smoke:

- use adaptive WQP-focused sequences;
- keep the same history length as PIPE/GRU-D, normally `12`;
- cap sampled windows before full training;
- compare validation one-step RMSE/MAE against both v0 and adaptive PIPE/GRU-D;
- proceed to full training only if validation improves v0 or exposes a clear
  tunable failure mode.

Gate v1.3, full one-step:

- train with the best v1.2 configuration selected on validation;
- evaluate test only once the validation decision is fixed;
- if one-step v1 remains below v0 or PIPE/GRU-D, document the negative result
  before attempting rollouts.

Gate v1.4, recursive rollout support:

- implement history-window rollouts only after v1 one-step is healthy;
- update the history window recursively by appending predicted state and the
  next monthly season features;
- run matched-origin validation/test against PIPE/GRU-D before calibration.

Gate v1.5, multi-step objective:

- add h1-h3 training loss only after the history-encoded one-step baseline is
  understood;
- select any multi-step variant on validation, not on test;
- compare against v1.3 and adaptive PIPE/GRU-D before policy calibration.

## Gate v1.1 Synthetic Smoke Result

The first history-encoded Neural ODE v1 synthetic smoke completed on
2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_report.md`;
- `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_manifest.json`;
- `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_training_curve.csv`;
- `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_persistence_comparison.csv`;
- `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_output_blend_weights.csv`;
- `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_prediction_examples.csv`.

Status: `completed`.

Geometry:

- history length: `6`;
- train/validation/test windows: `304` / `304` / `304`.

Selection:

- best epoch: `7`;
- validation all-state RMSE/MAE: `0.0054` / `0.0041`;
- validation balanced selection objective: `0.4414`.

One-step comparison against persistence:

- train all-state RMSE/MAE improvement: `55.79%` / `54.37%`;
- validation all-state RMSE/MAE improvement: `55.76%` / `55.95%`;
- test all-state RMSE/MAE improvement: `56.65%` / `56.04%`.

Interpretation:

- Gate v1.1 passes as an implementation and optimization smoke: the runner
  writes complete artifacts, uses historical windows, selects an internal best
  epoch, and improves substantially over persistence on synthetic dynamics.
- The best validation RMSE/MAE occurs before the final epoch, while NLL keeps
  decreasing later; this confirms that validation-balanced checkpoint selection
  is needed before interpreting downstream performance.
- As in v0, uncertainty intervals are too wide for a sharp calibration claim:
  90% coverage is `1.0` with large mean widths.

Decision: proceed to Gate v1.2 real bounded smoke over the adaptive WQP-focused
sequence dataset with `history_length=12`, matching PIPE/GRU-D history context.

## Gate v1.2 Real Bounded Smoke Result

The first real adaptive WQP-focused history-encoded Neural ODE v1 smoke
completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_training_curve.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_persistence_comparison.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_output_blend_weights.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_prediction_examples.csv`.

Status: `completed`.

Geometry:

- history length: `12`;
- available train/validation/test windows: `112,470` / `7,079` / `7,582`;
- sampled train/validation/test windows: `50,000` / `7,079` / `7,582`.

Selection:

- epochs: `3`;
- best epoch: `3`;
- validation all-state RMSE/MAE: `0.1389` / `0.0823`;
- validation balanced selection objective: `0.9273`.

One-step comparison against persistence:

- train all-state RMSE/MAE improvement: `10.14%` / `1.09%`;
- validation all-state RMSE/MAE improvement: `9.10%` / `5.45%`;
- test all-state RMSE/MAE improvement: `8.96%` / `5.38%`.

Interpretation:

- Gate v1.2 passes as a real-data smoke: the runner loads the adaptive
  WQP-focused sequence dataset, uses the same history length as adaptive
  PIPE/GRU-D, and improves held-out test error over one-step persistence.
- The real v1 smoke is stronger than the first real v0 bounded smoke, whose
  test all-state RMSE/MAE improvement was `3.26%` / `0.47%`.
- The result is not yet competitive with the trained adaptive PIPE/GRU-D or
  full Neural ODE v0. It is a short 3-epoch smoke, and best validation objective
  occurs at the final requested epoch.
- Change channels select full Neural ODE prediction, while uncertainty channels
  remain persistence-like. This is expected for early training and should be
  revisited after a longer run.

Decision: run an extended/full one-step v1 training pass over all available
history windows before implementing v1 rollouts or multi-step loss.

## Gate v1.3 Extended/Full One-Step Result

The first extended/full adaptive WQP-focused history-encoded Neural ODE v1 run
completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_training_curve.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_persistence_comparison.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_output_blend_weights.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_prediction_examples.csv`.

Status: `completed`.

Geometry:

- history length: `12`;
- available and used train/validation/test windows:
  `112,470` / `7,079` / `7,582`.

Selection:

- epochs: `20`;
- best epoch: `20`;
- validation all-state RMSE/MAE: `0.1187` / `0.0731`;
- validation balanced selection objective: `0.8086`.

One-step comparison against persistence:

- train all-state RMSE/MAE improvement: `24.47%` / `18.57%`;
- validation all-state RMSE/MAE improvement: `22.34%` / `15.95%`;
- test all-state RMSE/MAE improvement: `22.16%` / `15.50%`.

Strongest channels on test:

- `delta_yF` RMSE/MAE improvement: `42.36%` / `33.42%`;
- `delta_yN` RMSE/MAE improvement: `40.41%` / `33.44%`;
- `delta_yT` RMSE/MAE improvement: `37.53%` / `24.77%`;
- direct state channels improve RMSE but still have MAE trade-offs for `yF`
  and `yT`.

Comparison with adaptive PIPE/GRU-D:

- this v1 run uses the same history-window geometry as adaptive PIPE/GRU-D;
- adaptive PIPE/GRU-D full test all-state RMSE/MAE is `0.1097` / `0.0677`;
- Neural ODE v1 extended/full test all-state RMSE/MAE is `0.1148` / `0.0710`;
- adaptive PIPE/GRU-D therefore remains the stronger one-step model on this
  matched history-window surface.

Interpretation:

- Gate v1.3 confirms that the history-encoded Neural ODE learns real temporal
  signal and substantially improves over persistence on the same history-window
  surface used by GRU-D.
- The model is still most useful for change channels, while several uncertainty
  channels remain close to persistence under validation blending.
- The best validation objective occurs at the final requested epoch, and the
  training curve is still improving. This is a training-depth signal, not a
  reason to move immediately to rollouts or multi-step loss.
- Direct comparison to Neural ODE v0 is only approximate because v0 evaluates a
  larger Markovian transition set, while v1 requires a 12-month history window.

Decision: run a longer same-configuration v1 pass selected by validation before
changing architecture, adding rollout support, or adding a multi-step objective.

## Gate v1.3B Same-Configuration Long Run Result

The same-configuration long run completed on 2026-06-15 with `40` requested
epochs.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_training_curve.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_persistence_comparison.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_output_blend_weights.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_prediction_examples.csv`.

Status: `completed`.

Geometry:

- history length: `12`;
- available and used train/validation/test windows:
  `112,470` / `7,079` / `7,582`.

Selection:

- epochs: `40`;
- best epoch: `40`;
- validation all-state RMSE/MAE: `0.1128` / `0.0698`;
- validation balanced selection objective: `0.7703`.

One-step comparison against persistence:

- train all-state RMSE/MAE improvement: `27.88%` / `21.95%`;
- validation all-state RMSE/MAE improvement: `26.21%` / `19.72%`;
- test all-state RMSE/MAE improvement: `25.93%` / `19.52%`.

Comparison with adaptive PIPE/GRU-D on the same history-window surface:

- adaptive PIPE/GRU-D validation all-state RMSE/MAE: `0.1130` / `0.0698`;
- Neural ODE v1 long40 validation all-state RMSE/MAE:
  `0.1128` / `0.0698`;
- adaptive PIPE/GRU-D test all-state RMSE/MAE: `0.1097` / `0.0677`;
- Neural ODE v1 long40 test all-state RMSE/MAE: `0.1093` / `0.0677`.

Interpretation:

- Long40 brings the history-encoded Neural ODE v1 into the same one-step
  performance range as the adaptive PIPE/GRU-D default, with a slight advantage
  in aggregate RMSE after validation-selected output blending.
- The advantage is not uniform by channel: adaptive PIPE/GRU-D remains stronger
  on several `delta_*` channels, while Neural ODE v1 improves the direct `yT`
  RMSE channel and uses broader uncertainty intervals with higher empirical
  coverage.
- The best validation objective still occurs at the final requested epoch. The
  next decision should therefore remain validation-driven: one more longer run
  is justified before freezing a v1 checkpoint for recursive rollouts.
- This result updates the prior v1.3 interpretation: v1 is no longer merely
  below GRU-D on one-step aggregate metrics; it is now a competitive one-step
  alternative that still needs rollout evidence.

Decision: run one more same-configuration v1 long pass before implementing
history-window recursive rollouts. If the validation objective plateaus or the
best epoch becomes internal, freeze the best v1 one-step candidate and move to
matched-origin rollout evaluation.

## Gate v1.3C Same-Configuration Long80 Result

The same-configuration `80`-epoch run completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_training_curve.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_persistence_comparison.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_output_blend_weights.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_prediction_examples.csv`.

Status: `completed`.

Geometry:

- history length: `12`;
- available and used train/validation/test windows:
  `112,470` / `7,079` / `7,582`.

Selection:

- epochs: `80`;
- best epoch: `77`;
- validation all-state RMSE/MAE: `0.1102` / `0.0677`;
- validation balanced selection objective: `0.7495`.

One-step comparison against persistence:

- train all-state RMSE/MAE improvement: `30.08%` / `23.75%`;
- validation all-state RMSE/MAE improvement: `27.92%` / `22.18%`;
- test all-state RMSE/MAE improvement: `27.86%` / `22.89%`.

Comparison with adaptive PIPE/GRU-D on the same history-window surface:

- adaptive PIPE/GRU-D validation all-state RMSE/MAE: `0.1130` / `0.0698`;
- Neural ODE v1 long80 validation all-state RMSE/MAE:
  `0.1102` / `0.0677`;
- adaptive PIPE/GRU-D test all-state RMSE/MAE: `0.1097` / `0.0677`;
- Neural ODE v1 long80 test all-state RMSE/MAE: `0.1064` / `0.0648`.

Interpretation:

- Long80 is the first v1 run with an internal best epoch, so it provides a
  reasonable one-step stopping point without selecting the final epoch.
- On aggregate one-step state metrics, Neural ODE v1 now outperforms the
  adaptive PIPE/GRU-D one-step reference on both validation and test.
- The result is not yet a replacement claim for the temporal default: recursive
  rollouts, alert discrimination, calibration, and 2B policy behavior can still
  differ from one-step behavior.

Decision: freeze long80 as the v1 one-step candidate and proceed to
history-window recursive rollout evaluation on matched PIPE/GRU-D origins.
The existing Neural ODE rollout evaluator now supports both v0 Markovian models
and v1 history-encoded models, emitting separate v1 rollout/backtest version
tags.

## Gate v1.4 Recursive Rollout Smoke

The first history-window recursive rollout smoke completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_report_matched_grud_validation_smoke.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_manifest_matched_grud_validation_smoke.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_metrics_matched_grud_validation_smoke.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_alert_metrics_matched_grud_validation_smoke.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_examples_matched_grud_validation_smoke.csv`.

Status: `completed`.

Configuration:

- split: `validation`;
- reference origins: adaptive PIPE/GRU-D validation backtest rows;
- selected origins: `512` sampled from `5,069` matched origins;
- evaluated rollout rows: `1,536`;
- samples per origin: `32`;
- calibrated bloom disabled for this smoke.

Version tags:

- rollout version: `pipe_neural_ode_history_rollout_v1`;
- backtest version: `pipe_neural_ode_history_rollout_backtest_v1`;
- model version: `pipe_neural_ode_history_v1`.

State and IRC metrics:

- all-state RMSE improvement h1/h2/h3 against persistence:
  `31.17%` / `22.44%` / `26.93%`;
- IRC RMSE improvement h1/h2/h3 against persistence:
  `21.59%` / `23.63%` / `33.38%`;
- all-state 90% simulation coverage h1/h2/h3:
  `0.8874` / `0.8928` / `0.9160`.

Alert smoke metrics:

- `irc_alert` PR-AUC h1/h2/h3:
  `0.8806` / `0.8781` / `0.8333`;
- `irc_alert` recall h1/h2/h3:
  `0.7788` / `0.7812` / `0.8028`;
- `irc_alert` macro-F1 h1/h2/h3:
  `0.8383` / `0.8264` / `0.8018`.

Interpretation:

- The v1 rollout path is executable and correctly emits v1-specific version
  tags.
- Recursive behavior remains numerically sane on a matched-origin validation
  subset: state and IRC improvements against persistence are positive for all
  horizons.
- This is not final rollout evidence because the smoke uses a sampled subset,
  fewer Monte Carlo samples, and no calibrated `bloom_h` output.

Decision: scale to the full matched-origin validation backtest with `128`
samples and calibrated bloom enabled before running test or any policy
calibration.

## Gate v1.5 Full Matched-Origin Validation Rollout

The full history-window recursive validation backtest completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_report_matched_grud_validation.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_manifest_matched_grud_validation.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_metrics_matched_grud_validation.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_alert_metrics_matched_grud_validation.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_examples_matched_grud_validation.csv`.

Status: `completed`.

Configuration:

- split: `validation`;
- reference origins: adaptive PIPE/GRU-D validation backtest rows;
- selected origins: `5,069`;
- evaluated rollout rows: `15,207`;
- samples per origin: `128`;
- calibrated bloom horizons: `[1, 2, 3]`.

State and IRC metrics:

- all-state RMSE improvement h1/h2/h3 against persistence:
  `31.53%` / `26.29%` / `27.77%`;
- IRC RMSE improvement h1/h2/h3 against persistence:
  `18.79%` / `27.77%` / `33.82%`;
- all-state 90% simulation coverage h1/h2/h3:
  `0.9023` / `0.9164` / `0.9300`.

Alert metrics:

- `irc_alert` PR-AUC h1/h2/h3:
  `0.9094` / `0.8911` / `0.8789`;
- `irc_alert` recall h1/h2/h3:
  `0.8414` / `0.8231` / `0.8176`;
- `irc_alert` macro-F1 h1/h2/h3:
  `0.8585` / `0.8444` / `0.8374`;
- `bloom_h` PR-AUC h1/h2/h3:
  `0.6134` / `0.5886` / `0.5689`.

Matched-origin comparison:

- adaptive PIPE/GRU-D validation all-state RMSE improvement h1/h2/h3:
  `26.27%` / `19.29%` / `19.87%`;
- Neural ODE v0 matched validation all-state RMSE improvement h1/h2/h3:
  `25.29%` / `18.33%` / `17.06%`;
- adaptive PIPE/GRU-D validation `irc_alert` PR-AUC h1/h2/h3:
  `0.8703` / `0.8217` / `0.7910`;
- Neural ODE v0 matched validation `irc_alert` PR-AUC h1/h2/h3:
  `0.8632` / `0.8214` / `0.7907`.

Interpretation:

- On matched validation origins, Neural ODE v1 improves over persistence,
  adaptive PIPE/GRU-D, and Neural ODE v0 for aggregate state RMSE, IRC RMSE,
  and `irc_alert` discrimination across all horizons.
- `bloom_h` PR-AUC also improves over the existing adaptive PIPE/GRU-D and
  Neural ODE v0 validation references, but calibrated bloom recall is still
  policy-sensitive and should not be over-interpreted before test and policy
  calibration.
- The prior project default should not be replaced yet: validation is only the
  model-selection split. The decisive holdout check is matched-origin test.

Decision: proceed to a full matched-origin test backtest with the same v1
long80 checkpoint, `128` samples, and calibrated bloom enabled.

## Gate v1.6 Full Matched-Origin Test Rollout

The full history-window recursive test backtest completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_report_matched_grud_test.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_manifest_matched_grud_test.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_metrics_matched_grud_test.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_alert_metrics_matched_grud_test.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_examples_matched_grud_test.csv`.

Status: `completed`.

Configuration:

- split: `test`;
- reference origins: adaptive PIPE/GRU-D test backtest rows;
- selected origins: `6,145`;
- evaluated rollout rows: `18,435`;
- samples per origin: `128`;
- calibrated bloom horizons: `[1, 2, 3]`.

State and IRC metrics:

- all-state RMSE improvement h1/h2/h3 against persistence:
  `31.64%` / `28.07%` / `29.02%`;
- IRC RMSE improvement h1/h2/h3 against persistence:
  `20.68%` / `30.79%` / `36.31%`;
- all-state 90% simulation coverage h1/h2/h3:
  `0.9080` / `0.9252` / `0.9365`.

Alert metrics:

- `irc_alert` PR-AUC h1/h2/h3:
  `0.9331` / `0.9208` / `0.9238`;
- `irc_alert` recall h1/h2/h3:
  `0.8694` / `0.8598` / `0.8745`;
- `irc_alert` macro-F1 h1/h2/h3:
  `0.8747` / `0.8629` / `0.8642`;
- `bloom_h` PR-AUC h1/h2/h3:
  `0.6691` / `0.6426` / `0.6422`.

Matched-origin comparison:

- adaptive PIPE/GRU-D test all-state RMSE improvement h1/h2/h3:
  `25.03%` / `20.66%` / `20.31%`;
- Neural ODE v0 matched test all-state RMSE improvement h1/h2/h3:
  `24.83%` / `19.11%` / `16.21%`;
- adaptive PIPE/GRU-D test `irc_alert` PR-AUC h1/h2/h3:
  `0.9013` / `0.8630` / `0.8547`;
- Neural ODE v0 matched test `irc_alert` PR-AUC h1/h2/h3:
  `0.8952` / `0.8549` / `0.8529`;
- adaptive PIPE/GRU-D test `bloom_h` PR-AUC h1/h2/h3:
  `0.6559` / `0.6131` / `0.5983`;
- Neural ODE v0 matched test `bloom_h` PR-AUC h1/h2/h3:
  `0.6282` / `0.5883` / `0.5781`.

Interpretation:

- The holdout test confirms the validation result: Neural ODE v1 improves over
  persistence, adaptive PIPE/GRU-D, and Neural ODE v0 on matched-origin state
  RMSE, IRC RMSE, `irc_alert` discrimination, and `bloom_h` PR-AUC across all
  horizons.
- This is strong enough to promote Neural ODE v1 from a secondary exploratory
  branch to a serious candidate robust temporal model.
- A default-policy change still requires Neural ODE v1-specific alert
  calibration and policy-frontier comparison. The current thresholds are the
  inherited generic thresholds used for backtest scoring, not a selected v1
  deployment profile.

Decision: proceed to Neural ODE v1-specific rollout alert calibration on
validation, followed by the 2B policy-frontier comparison against test.

## Gate v1.7 Rollout Alert Calibration

The history-window Neural ODE v1 rollout alert calibration completed on
2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibration_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibration_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibration_thresholds.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibration_metrics.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibrated_backtest_rows.parquet`;
- `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/rollout_calibrators/`.

Status: `completed`.

Configuration:

- calibration split: `validation`;
- evaluation splits: `validation,test`;
- selection objective: `fbeta`;
- F-beta beta: `2.0`;
- bloom score column: `irc_mean`;
- backtest version: `pipe_neural_ode_history_rollout_backtest_v1`;
- calibration version: `pipe_neural_ode_history_rollout_alert_calibration_v1`;
- concatenated backtest rows: `33,642`;
- selected threshold rows: `6`;
- metric rows: `12`;
- bloom calibrators: `3`.

Selected F2 thresholds:

- `irc_alert` h1/h2/h3:
  `0.2734` / `0.3438` / `0.3125`;
- `bloom_h` h1/h2/h3:
  `0.1429` / `0.1429` / `0.1373`.

Held-out test F2 profile:

- `irc_alert` recall h1/h2/h3:
  `0.9447` / `0.9346` / `0.9583`;
- `irc_alert` precision h1/h2/h3:
  `0.7446` / `0.7460` / `0.7027`;
- `irc_alert` F2 h1/h2/h3:
  `0.8965` / `0.8896` / `0.8933`;
- `bloom_h` recall h1/h2/h3:
  `0.8474` / `0.8111` / `0.9083`;
- `bloom_h` precision h1/h2/h3:
  `0.4797` / `0.5236` / `0.4277`;
- `bloom_h` F2 h1/h2/h3:
  `0.7348` / `0.7308` / `0.7416`.

Matched calibration comparison:

- adaptive PIPE/GRU-D F2 test `irc_alert` h1/h2/h3:
  `0.8679` / `0.8531` / `0.8558`;
- Neural ODE v0 F2 test `irc_alert` h1/h2/h3:
  `0.8680` / `0.8482` / `0.8458`;
- adaptive PIPE/GRU-D F2 test `bloom_h` h1/h2/h3:
  `0.7059` / `0.7257` / `0.7213`;
- Neural ODE v0 F2 test `bloom_h` h1/h2/h3:
  `0.6994` / `0.6913` / `0.7034`.

Interpretation:

- Neural ODE v1 now improves the sensitive F2 alert profile over both adaptive
  PIPE/GRU-D and Neural ODE v0 on `irc_alert` and `bloom_h` across all
  horizons.
- `irc_alert` is the cleaner operational signal: v1 raises precision while
  preserving high recall relative to earlier F2 profiles.
- `bloom_h` also improves in F2, but h3 still pays a higher alert-rate cost and
  should remain a secondary diagnostic until the policy frontier is reviewed.
- A default-policy decision still requires the 2B frontier because F2 is an
  intentionally sensitive profile rather than a balanced deployment profile.

Decision: proceed to the Neural ODE v1 2B policy-frontier comparison using the
v1 calibrated backtest rows.

## Gate v1.8 2B Policy Frontier

The history-window Neural ODE v1 2B policy frontier completed on 2026-06-15.

Artifacts:

- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_policy_2b_report.md`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_policy_2b_manifest.json`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_policy_2b_thresholds.csv`;
- `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_policy_2b_metrics.csv`.

Status: `completed`.

Configuration:

- policy version: `pipe_neural_ode_history_rollout_alert_policy_2b_v1`;
- calibrated rows: `33,642`;
- threshold rows: `42`;
- metric rows: `84`;
- calibration split: `validation`;
- evaluation splits: `validation,test`;
- objectives: `fixed`, `fbeta`, `f1`, `mcc`, `balanced_accuracy`,
  `gmean_pr`, `closest_pr`.

Held-out test `irc_alert` balanced profile:

- `closest_pr` thresholds h1/h2/h3:
  `0.4453` / `0.4531` / `0.4844`;
- `closest_pr` recall h1/h2/h3:
  `0.8905` / `0.8876` / `0.8818`;
- `closest_pr` precision h1/h2/h3:
  `0.8228` / `0.8081` / `0.8194`;
- `closest_pr` alert rate h1/h2/h3:
  `0.4490` / `0.4757` / `0.4786`;
- `closest_pr` F2 h1/h2/h3:
  `0.8761` / `0.8705` / `0.8686`;
- `closest_pr` MCC h1/h2/h3:
  `0.7474` / `0.7209` / `0.7224`.

Held-out test `bloom_h` balanced profile:

- `closest_pr` thresholds h1/h2/h3:
  `0.4074` / `0.3649` / `0.2982`;
- `closest_pr` recall h1/h2/h3:
  `0.5939` / `0.6246` / `0.6840`;
- `closest_pr` precision h1/h2/h3:
  `0.6894` / `0.6153` / `0.5933`;
- `closest_pr` alert rate h1/h2/h3:
  `0.1571` / `0.1860` / `0.2140`;
- `closest_pr` F2 h1/h2/h3:
  `0.6108` / `0.6227` / `0.6637`;
- `closest_pr` MCC h1/h2/h3:
  `0.5669` / `0.5339` / `0.5472`.

Matched policy comparison:

- adaptive PIPE/GRU-D `closest_pr` test `irc_alert` F2 h1/h2/h3:
  `0.8466` / `0.8037` / `0.7906`;
- Neural ODE v0 `closest_pr` test `irc_alert` F2 h1/h2/h3:
  `0.8557` / `0.8216` / `0.8030`;
- Neural ODE v1 `closest_pr` test `irc_alert` F2 h1/h2/h3:
  `0.8761` / `0.8705` / `0.8686`.

Interpretation:

- The 2B frontier confirms the F2 calibration result: Neural ODE v1 is now the
  strongest temporal candidate for `irc_alert` among the compared adaptive
  PIPE/GRU-D, Neural ODE v0, and Neural ODE v1 branches.
- `closest_pr` is the recommended balanced Neural ODE v1 profile. It improves
  recall, precision, F2, MCC, and balanced accuracy over adaptive PIPE/GRU-D
  `closest_pr` across all `irc_alert` horizons while keeping alert rate in a
  similar range.
- `fbeta` remains the sensitive high-recall profile, and `fixed` remains a
  useful reference threshold because it is surprisingly strong for v1
  `irc_alert`.
- `bloom_h` improves most clearly under F2 and h3 `closest_pr`; h1-h2
  `closest_pr` are competitive but not uniformly superior to adaptive
  PIPE/GRU-D on every precision-recall trade-off. It should remain secondary to
  `irc_alert` for operational claims.

Decision: treat Neural ODE v1 `closest_pr` as the leading balanced temporal
candidate for the current adaptive PIPE surface, while preserving adaptive
PIPE/GRU-D as the simpler reproducible benchmark and fallback. Before any final
thesis-wide default claim, promote the required heavy artifacts through DVC and
close the code/docs/report bundle reproducibly.

DVC promotion note:

- `models.dvc` was updated locally to include the Neural ODE v1 long80
  checkpoint/model and rollout calibrators;
- DVC pointers were created for the v1 matched-origin validation/test backtest
  rows and calibrated backtest rows;
- the DVC objects still need to be pushed to the configured private remote
  before the Git commit is finalized.
