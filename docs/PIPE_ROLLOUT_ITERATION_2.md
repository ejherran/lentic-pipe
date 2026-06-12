# PIPE/GRU-D Rollout Alert Calibration - Iteration 2 Protocol

This document defines and records the second rollout-alert iteration. It treats
threshold calibration as an experiment in alert policy, not as a final adoption
decision. After reviewing the Iteration 2B policy frontier, the project adopts
the balanced `closest_pr` policy as the provisional default for downstream
experiments and interfaces. The fixed and F2 policies remain comparison
profiles.

## Purpose

Iteration 1 showed useful ranking signal in recursive PIPE/GRU-D rollouts, but
the fixed binary thresholds were too conservative for alert recall at longer
horizons.

Iteration 2 separates three decisions:

1. generate historical rollout rows;
2. fit rollout-specific bloom calibrators on validation rows;
3. select horizon-specific alert thresholds on validation rows and evaluate
   them on held-out test rows.

The PIPE/GRU-D model is not retrained by this protocol.

## New Artifacts

- `reports/pipe_grud/pipe_rollout_backtest_rows_validation.parquet`
  and `reports/pipe_grud/pipe_rollout_backtest_rows_test.parquet`
  - compact row-level backtest export from `evaluate_pipe_grud_rollouts.py`;
  - DVC-tracked through `.dvc` pointers;
  - used as calibration input.

- `reports/pipe_grud/pipe_rollout_calibration_thresholds.csv`
  - selected thresholds by event and horizon.

- `reports/pipe_grud/pipe_rollout_calibration_metrics.csv`
  - validation/test metrics under the selected thresholds.

- `reports/pipe_grud/pipe_rollout_calibrated_backtest_rows.parquet`
  - row-level calibrated probabilities and decisions;
  - DVC-tracked through a `.dvc` pointer.

- `reports/pipe_grud/pipe_rollout_calibration_report.md`
  - human-readable summary.

- `reports/pipe_grud/pipe_rollout_calibration_manifest.json`
  - SHA-256 traceability for inputs, outputs, calibrators, and script.

- `models/pipe_grud/rollout_calibrators/`
  - rollout-specific bloom calibrators fitted on validation rows.
  - included in the DVC-tracked `models.dvc` artifact.

- `reports/pipe_grud/pipe_rollout_policy_2b_thresholds.csv`
  - automatic threshold frontier selected on validation rows.

- `reports/pipe_grud/pipe_rollout_policy_2b_metrics.csv`
  - validation/test metrics for fixed, sensitive, and balanced policy
    objectives.

- `reports/pipe_grud/pipe_rollout_policy_2b_report.md`
  - human-readable policy-frontier report.

- `reports/pipe_grud/pipe_rollout_policy_2b_manifest.json`
  - SHA-256 traceability for the policy-frontier experiment.

## Recommended Commands

Run validation and test backtests separately. These commands can be expensive
because they simulate recursive rollouts; they should be run by the operator on
the data workstation.

```bash
poetry run python src/experiments/evaluate_pipe_grud_rollouts.py \
  --split validation \
  --rollout-horizon 3 \
  --samples 128 \
  --batch-size 256 \
  --backtest-rows reports/pipe_grud/pipe_rollout_backtest_rows_validation.parquet \
  --metrics reports/pipe_grud/pipe_rollout_backtest_metrics_validation.csv \
  --alert-metrics reports/pipe_grud/pipe_rollout_backtest_alert_metrics_validation.csv \
  --examples reports/pipe_grud/pipe_rollout_backtest_examples_validation.csv \
  --report reports/pipe_grud/pipe_rollout_backtest_report_validation.md \
  --manifest reports/pipe_grud/pipe_rollout_backtest_manifest_validation.json
```

```bash
poetry run python src/experiments/evaluate_pipe_grud_rollouts.py \
  --split test \
  --rollout-horizon 3 \
  --samples 128 \
  --batch-size 256 \
  --backtest-rows reports/pipe_grud/pipe_rollout_backtest_rows_test.parquet \
  --metrics reports/pipe_grud/pipe_rollout_backtest_metrics_test.csv \
  --alert-metrics reports/pipe_grud/pipe_rollout_backtest_alert_metrics_test.csv \
  --examples reports/pipe_grud/pipe_rollout_backtest_examples_test.csv \
  --report reports/pipe_grud/pipe_rollout_backtest_report_test.md \
  --manifest reports/pipe_grud/pipe_rollout_backtest_manifest_test.json
```

Then calibrate and select thresholds:

```bash
poetry run python src/experiments/calibrate_pipe_rollout_alerts.py \
  --backtest-rows reports/pipe_grud/pipe_rollout_backtest_rows_validation.parquet \
  --backtest-rows reports/pipe_grud/pipe_rollout_backtest_rows_test.parquet \
  --calibration-split validation \
  --evaluation-splits validation,test \
  --selection-objective fbeta \
  --fbeta-beta 2.0 \
  --min-recall 0.50
```

If validation recall remains too low, rerun calibration with a more explicit
recall target:

```bash
poetry run python src/experiments/calibrate_pipe_rollout_alerts.py \
  --backtest-rows reports/pipe_grud/pipe_rollout_backtest_rows_validation.parquet \
  --backtest-rows reports/pipe_grud/pipe_rollout_backtest_rows_test.parquet \
  --calibration-split validation \
  --evaluation-splits validation,test \
  --selection-objective recall_target \
  --fbeta-beta 2.0 \
  --min-recall 0.70
```

After the calibrated row-level evidence exists, compare threshold policies
without setting a manual recall target:

```bash
poetry run python src/experiments/compare_pipe_rollout_alert_policies.py \
  --calibrated-rows reports/pipe_grud/pipe_rollout_calibrated_backtest_rows.parquet \
  --thresholds reports/pipe_grud/pipe_rollout_policy_2b_thresholds.csv \
  --metrics reports/pipe_grud/pipe_rollout_policy_2b_metrics.csv \
  --report reports/pipe_grud/pipe_rollout_policy_2b_report.md \
  --manifest reports/pipe_grud/pipe_rollout_policy_2b_manifest.json
```

## Review Criteria

Review results in this order:

1. Check whether validation thresholds satisfy the recall/precision constraint.
2. Compare validation and test recall, precision, PR-AUC, Brier, and F-beta.
3. Inspect horizon-specific failures, especially h2 and h3.
4. Compare the calibrated test metrics against Iteration 1 fixed-threshold
   metrics.
5. Decide whether the improved alert policy is sufficient or whether PIPE-GRU-D
   should be retrained on the current NLA freeze.

## Executed Results

The protocol was executed on 2026-06-12 with validation and test backtests run
separately and threshold selection performed on validation rows only.

Run support:

- validation selected origins: 16,260;
- validation rollout rows: 48,780;
- test selected origins: 13,327;
- test rollout rows: 39,981;
- calibration input rows: 88,761;
- selected threshold rows: 6;
- rollout-specific bloom calibrators: 3.

Selected validation thresholds:

| Event | Horizon | Threshold | Validation recall | Validation precision | Validation F2 | Constraint |
|---|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | 0.1538 | 0.794 | 0.421 | 0.674 | `True` |
| `bloom_h` | 2 | 0.1649 | 0.796 | 0.379 | 0.652 | `True` |
| `bloom_h` | 3 | 0.1300 | 0.830 | 0.336 | 0.642 | `True` |
| `irc_alert` | 1 | 0.1172 | 0.912 | 0.616 | 0.832 | `True` |
| `irc_alert` | 2 | 0.1250 | 0.935 | 0.562 | 0.825 | `True` |
| `irc_alert` | 3 | 0.1641 | 0.920 | 0.574 | 0.821 | `True` |

Held-out test comparison against the fixed-threshold policy:

| Event | Horizon | Fixed recall | Cal recall | Fixed precision | Cal precision | Fixed positive rate | Cal positive rate | Fixed F2 | Cal F2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | 0.608 | 0.824 | 0.675 | 0.468 | 0.112 | 0.219 | 0.621 | 0.715 |
| `bloom_h` | 2 | 0.354 | 0.857 | 0.750 | 0.420 | 0.061 | 0.265 | 0.396 | 0.710 |
| `bloom_h` | 3 | 0.288 | 0.890 | 0.740 | 0.362 | 0.052 | 0.329 | 0.328 | 0.689 |
| `irc_alert` | 1 | 0.783 | 0.939 | 0.834 | 0.626 | 0.313 | 0.500 | 0.792 | 0.853 |
| `irc_alert` | 2 | 0.724 | 0.956 | 0.838 | 0.578 | 0.299 | 0.574 | 0.745 | 0.846 |
| `irc_alert` | 3 | 0.685 | 0.942 | 0.847 | 0.596 | 0.288 | 0.563 | 0.712 | 0.844 |

Interpretation:

- Horizon-specific thresholds substantially increase recall, especially for
  `bloom_h` at h2 and h3.
- The improvement is not free: precision decreases and the predicted positive
  rate increases. This is a direct alert-policy tradeoff.
- F2 improves on held-out test for all evaluated event/horizon combinations,
  which supports the experiment as useful evidence for sensitive early warning.
- A more conservative policy can be evaluated later if operational precision is
  preferred over recall.

## Iteration 2B: Automatic Policy Frontier

Iteration 2B was added to search for a third, more balanced policy without
manually choosing a recall target. The experiment compares validation-selected
objectives: `fixed`, `fbeta`, `f1`, `mcc`, `balanced_accuracy`, `gmean_pr`, and
`closest_pr`. Test is still evaluation-only.

Reproducibility summary:

- calibrated input rows: 88,761;
- selected policy rows: 42;
- metric rows: 84;
- calibrated row input SHA-256:
  `88486e1bd1af4010a5a9a8f12b0b0946df806e6db1bb87d6ea38cf634954d215`;
- threshold output SHA-256:
  `283acee1c7692b697e7a89085d9724b3f3386a7da433293ebe3f5a281384cc6a`;
- metric output SHA-256:
  `44109318431db2d4c2788a9242ce857775199232df64d3336a7c579e13deaae8`;
- report output SHA-256:
  `5b91827a2cb517f7d4133eaa0330fe6da5625bcdaddd06869483b9a3224e13d9`.

Representative held-out test policies:

| Event | Horizon | Policy | Recall | Precision | Alert rate | F1 | F2 | MCC |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `closest_pr` | 0.678 | 0.609 | 0.138 | 0.642 | 0.663 | 0.589 |
| `bloom_h` | 2 | `f1` | 0.688 | 0.554 | 0.161 | 0.614 | 0.657 | 0.554 |
| `bloom_h` | 3 | `closest_pr` | 0.718 | 0.504 | 0.190 | 0.592 | 0.662 | 0.528 |
| `irc_alert` | 1 | `mcc` | 0.801 | 0.822 | 0.325 | 0.811 | 0.805 | 0.719 |
| `irc_alert` | 2 | `mcc` | 0.795 | 0.790 | 0.349 | 0.792 | 0.794 | 0.682 |
| `irc_alert` | 3 | `f1`/`mcc`/`closest_pr` | 0.854 | 0.731 | 0.417 | 0.787 | 0.826 | 0.660 |

Interpretation:

- There is no free policy that dominates both fixed thresholds and F2-sensitive
  thresholds on every metric.
- The automatic frontier does produce a defensible middle profile: it recovers
  much more recall than fixed thresholds for `bloom_h` h2/h3 while avoiding the
  largest alert-rate increase of the F2-sensitive policy.
- For `irc_alert`, MCC is a strong precision-preserving balance at h1/h2, while
  h3 benefits from the shared `f1`/`mcc`/`closest_pr` threshold.
- This supports keeping three explicit policy profiles for thesis discussion:
  conservative fixed thresholds, sensitive F2 thresholds, and balanced
  validation-selected thresholds.

The policy-frontier script preserves missing bloom labels as missing values
rather than converting them into negatives. This keeps the `bloom_h` evaluation
denominators aligned with the calibrated-row evidence.

## Default Policy For Downstream Work

The provisional downstream default is Iteration 2B with `selection_objective =
closest_pr`. This rule selects, on validation rows, the threshold with the
smallest Euclidean distance to the ideal precision-recall point `(1, 1)`.

This default was chosen for three reasons:

- it is a single rule that can be applied across events and horizons;
- it avoids post-hoc horizon-by-horizon selection from held-out test results;
- it gives a balanced operating point between the conservative fixed thresholds
  and the sensitive F2 thresholds.

Held-out test performance for the default `closest_pr` policy:

| Event | Horizon | Threshold | Recall | Precision | Alert rate | F1 | F2 | MCC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | 0.2927 | 0.678 | 0.609 | 0.138 | 0.642 | 0.663 | 0.589 |
| `bloom_h` | 2 | 0.2632 | 0.714 | 0.536 | 0.173 | 0.612 | 0.669 | 0.552 |
| `bloom_h` | 3 | 0.2714 | 0.718 | 0.504 | 0.190 | 0.592 | 0.662 | 0.528 |
| `irc_alert` | 1 | 0.3594 | 0.850 | 0.779 | 0.364 | 0.813 | 0.835 | 0.714 |
| `irc_alert` | 2 | 0.3594 | 0.825 | 0.762 | 0.375 | 0.792 | 0.812 | 0.677 |
| `irc_alert` | 3 | 0.3281 | 0.854 | 0.731 | 0.417 | 0.787 | 0.826 | 0.660 |

Policy roles after this decision:

- `fixed`: conservative comparison profile with fewer alerts and higher
  precision.
- `fbeta`: sensitive comparison profile for early-warning screening.
- `closest_pr`: provisional default for downstream experiments, API design, and
  operational summaries unless a later validation protocol supersedes it.

This is not an official environmental alert policy. It is the repository's
default decision rule for reproducible downstream experimentation.

## Data Scope

This experiment was run after NLA had been integrated into the repository data
architecture, but the evaluated PIPE/GRU-D rows do not include `source_id =
nla`. Under the current conservative source-site policy, NLA is used as a
validation, provenance, and enrichment layer. It is not yet used to transfer
monthly targets through the candidate NLA/WQP crosswalk.

The evaluated row-level sources are `aquamatch_chla`, `lakebed_us_cse`, and
`wqp`.

## Reproducibility Status

The small report artifacts are intended for Git:

- `reports/pipe_grud/pipe_rollout_backtest_metrics_validation.csv`
- `reports/pipe_grud/pipe_rollout_backtest_metrics_test.csv`
- `reports/pipe_grud/pipe_rollout_backtest_alert_metrics_validation.csv`
- `reports/pipe_grud/pipe_rollout_backtest_alert_metrics_test.csv`
- `reports/pipe_grud/pipe_rollout_backtest_examples_validation.csv`
- `reports/pipe_grud/pipe_rollout_backtest_examples_test.csv`
- `reports/pipe_grud/pipe_rollout_backtest_report_validation.md`
- `reports/pipe_grud/pipe_rollout_backtest_report_test.md`
- `reports/pipe_grud/pipe_rollout_backtest_manifest_validation.json`
- `reports/pipe_grud/pipe_rollout_backtest_manifest_test.json`
- `reports/pipe_grud/pipe_rollout_calibration_thresholds.csv`
- `reports/pipe_grud/pipe_rollout_calibration_metrics.csv`
- `reports/pipe_grud/pipe_rollout_calibration_report.md`
- `reports/pipe_grud/pipe_rollout_calibration_manifest.json`
- `reports/pipe_grud/pipe_rollout_policy_2b_thresholds.csv`
- `reports/pipe_grud/pipe_rollout_policy_2b_metrics.csv`
- `reports/pipe_grud/pipe_rollout_policy_2b_report.md`
- `reports/pipe_grud/pipe_rollout_policy_2b_manifest.json`

The row-level parquet files and model calibrators are promoted DVC artifacts:

- `reports/pipe_grud/pipe_rollout_backtest_rows_validation.parquet`
- `reports/pipe_grud/pipe_rollout_backtest_rows_test.parquet`
- `reports/pipe_grud/pipe_rollout_calibrated_backtest_rows.parquet`
- `models/pipe_grud/rollout_calibrators/`

Their `.dvc` pointers make the exact experimental evidence recoverable through
the normal DVC workflow. This promotion freezes the evidence; it does not adopt
the F2 threshold policy as the final operational policy. The downstream default
is the Iteration 2B `closest_pr` profile.

## Guardrails

- Validation selects thresholds and fits calibrators.
- Test evaluates only; never tune thresholds from test.
- Bloom calibrators are rollout-specific and must not be confused with the
  previous fuzzy `irc1` calibrators.
- `closest_pr` is the provisional downstream default; `fixed` and `fbeta`
  remain documented comparison profiles.
- Do not present any profile as an official environmental alert.
