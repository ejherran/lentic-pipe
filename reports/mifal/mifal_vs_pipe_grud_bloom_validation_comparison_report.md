# MIFAL vs PIPE Bloom Metric Comparison v0

Generated at UTC: `2026-06-27T17:23:52.919219+00:00`
Target event: `bloom_h`
Splits: `validation`
MIFAL metrics: `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_validation_matched_metrics.csv`
PIPE metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_metrics.csv`

This is a metric-level comparison for `bloom_h` only. MIFAL does not emit the PIPE `irc_alert` target.
Negative delta Brier is favorable for MIFAL; positive deltas for PR-AUC, F-beta, precision, and recall are favorable for MIFAL.

## Comparison

| MIFAL model | split | horizon | rows | delta PR-AUC | delta Brier | delta F-beta | delta precision | delta recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `current_chla` | `validation` | 1 | 3,049 | -0.1633 | 0.0190 | -0.1744 | -0.0936 | -0.2195 |
| `current_chla` | `validation` | 2 | 3,158 | -0.2075 | 0.0231 | -0.1845 | -0.1491 | -0.0884 |
| `current_chla` | `validation` | 3 | 3,184 | -0.2010 | 0.0221 | -0.1838 | -0.1440 | -0.1028 |
| `no_current_chla` | `validation` | 1 | 3,049 | -0.3364 | 0.0317 | -0.1470 | -0.1504 | -0.0902 |
| `no_current_chla` | `validation` | 2 | 3,158 | -0.3267 | 0.0314 | -0.1526 | -0.0959 | -0.1655 |
| `no_current_chla` | `validation` | 3 | 3,184 | -0.2820 | 0.0271 | -0.1398 | -0.0817 | -0.1641 |

## Outputs

- Comparison: `reports/mifal/mifal_vs_pipe_grud_bloom_validation_comparison_comparison.csv`
- Manifest: `reports/mifal/mifal_vs_pipe_grud_bloom_validation_comparison_manifest.json`
