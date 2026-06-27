# MIFAL vs PIPE Bloom Metric Comparison v0

Generated at UTC: `2026-06-27T17:23:53.483292+00:00`
Target event: `bloom_h`
Splits: `test`
MIFAL metrics: `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_holdout_matched_metrics.csv`
PIPE metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_metrics.csv`

This is a metric-level comparison for `bloom_h` only. MIFAL does not emit the PIPE `irc_alert` target.
Negative delta Brier is favorable for MIFAL; positive deltas for PR-AUC, F-beta, precision, and recall are favorable for MIFAL.

## Comparison

| MIFAL model | split | horizon | rows | delta PR-AUC | delta Brier | delta F-beta | delta precision | delta recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `current_chla` | `test` | 1 | 4,673 | -0.0258 | 0.0059 | -0.0721 | -0.1374 | -0.0164 |
| `current_chla` | `test` | 2 | 4,710 | -0.0464 | 0.0102 | -0.1957 | -0.2125 | -0.0614 |
| `current_chla` | `test` | 3 | 4,757 | -0.0721 | 0.0139 | -0.1996 | -0.2001 | -0.0872 |
| `no_current_chla` | `test` | 1 | 4,673 | -0.2797 | 0.0399 | -0.1110 | -0.1342 | -0.0869 |
| `no_current_chla` | `test` | 2 | 4,710 | -0.2572 | 0.0368 | -0.1336 | -0.0770 | -0.1634 |
| `no_current_chla` | `test` | 3 | 4,757 | -0.2374 | 0.0342 | -0.1520 | -0.0735 | -0.2005 |

## Outputs

- Comparison: `reports/mifal/mifal_vs_pipe_grud_bloom_holdout_comparison_comparison.csv`
- Manifest: `reports/mifal/mifal_vs_pipe_grud_bloom_holdout_comparison_manifest.json`
