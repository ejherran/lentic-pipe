# Controlled Degradation Report

Generated at UTC: `2026-06-12T16:31:10.281081+00:00`

## Scope

This report evaluates controlled-degradation scenarios on precomputed alert score rows.
Scenarios that modify predictor evidence are skipped unless passthrough-score evaluation is explicitly enabled.

## Configuration

- Config: `configs/degradation_scenarios.yaml`
- Scored rows: `reports/pipe_grud/pipe_rollout_calibrated_backtest_rows.parquet`
- Thresholds: `reports/pipe_grud/pipe_rollout_policy_2b_thresholds.csv`
- Scenario set: `smoke`
- Policies: `['closest_pr', 'fixed', 'fbeta']`
- Evaluation splits: `['validation', 'test']`
- Default policy: `closest_pr`
- Passthrough precomputed scores: `False`

## Scenario Summary

| scenario | status | seed | output rows | retained | metrics rows | reason |
|---|---|---:|---:|---:|---:|---|
| `ablate_chlorophyll_memory` | `skipped_requires_model_recompute` | NA | 0 | NA | 0 | scenario changes predictor evidence and requires model score recomputation |
| `control_observed` | `evaluated` | NA | 88,761 | 1.0000 | 144 |  |
| `random_dropout_mcar_25` | `skipped_requires_model_recompute` | NA | 0 | NA | 0 | scenario changes predictor evidence and requires model score recomputation |
| `site_retention_50` | `evaluated` | 20260612 | 44,601 | 0.5025 | 144 |  |
| `site_retention_50` | `evaluated` | 20260613 | 43,383 | 0.4888 | 144 |  |
| `site_retention_50` | `evaluated` | 20260614 | 44,841 | 0.5052 | 144 |  |
| `source_scope_wqp_only` | `evaluated` | NA | 33,642 | 0.3790 | 72 |  |
| `temporal_blocks_3m_rate_10` | `skipped_requires_model_recompute` | NA | 0 | NA | 0 | scenario changes predictor evidence and requires model score recomputation |

## Default-Policy Test Metrics

| scenario | seed | horizon | source | event | rows | recall | precision | alert rate | F2 | delta F2 |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| `control_observed` | NA | 1 | `all` | `bloom_h` | 11,852 | 0.6782 | 0.6088 | 0.1385 | 0.6631 | 0.0000 |
| `control_observed` | NA | 1 | `all` | `irc_alert` | 13,327 | 0.8499 | 0.7788 | 0.3639 | 0.8347 | 0.0000 |
| `control_observed` | NA | 2 | `all` | `bloom_h` | 11,891 | 0.7137 | 0.5357 | 0.1730 | 0.6693 | 0.0000 |
| `control_observed` | NA | 2 | `all` | `irc_alert` | 13,327 | 0.8250 | 0.7622 | 0.3749 | 0.8116 | 0.0000 |
| `control_observed` | NA | 3 | `all` | `bloom_h` | 11,939 | 0.7183 | 0.5037 | 0.1904 | 0.6619 | 0.0000 |
| `control_observed` | NA | 3 | `all` | `irc_alert` | 13,327 | 0.8539 | 0.7305 | 0.4166 | 0.8260 | 0.0000 |
| `site_retention_50` | 20260612 | 1 | `all` | `bloom_h` | 5,936 | 0.6634 | 0.5692 | 0.1388 | 0.6421 | -0.0210 |
| `site_retention_50` | 20260612 | 1 | `all` | `irc_alert` | 6,723 | 0.8546 | 0.7876 | 0.3684 | 0.8403 | 0.0056 |
| `site_retention_50` | 20260612 | 2 | `all` | `bloom_h` | 5,958 | 0.7179 | 0.5214 | 0.1729 | 0.6676 | -0.0017 |
| `site_retention_50` | 20260612 | 2 | `all` | `irc_alert` | 6,723 | 0.8247 | 0.7690 | 0.3786 | 0.8129 | 0.0013 |
| `site_retention_50` | 20260612 | 3 | `all` | `bloom_h` | 5,982 | 0.7299 | 0.4735 | 0.1956 | 0.6586 | -0.0033 |
| `site_retention_50` | 20260612 | 3 | `all` | `irc_alert` | 6,723 | 0.8561 | 0.7353 | 0.4248 | 0.8289 | 0.0029 |
| `site_retention_50` | 20260613 | 1 | `all` | `bloom_h` | 5,687 | 0.6738 | 0.6157 | 0.1528 | 0.6613 | -0.0018 |
| `site_retention_50` | 20260613 | 1 | `all` | `irc_alert` | 6,434 | 0.8489 | 0.7899 | 0.3847 | 0.8364 | 0.0017 |
| `site_retention_50` | 20260613 | 2 | `all` | `bloom_h` | 5,706 | 0.7096 | 0.5433 | 0.1884 | 0.6687 | -0.0006 |
| `site_retention_50` | 20260613 | 2 | `all` | `irc_alert` | 6,434 | 0.8270 | 0.7731 | 0.3959 | 0.8156 | 0.0040 |
| `site_retention_50` | 20260613 | 3 | `all` | `bloom_h` | 5,730 | 0.7160 | 0.5178 | 0.2056 | 0.6651 | 0.0031 |
| `site_retention_50` | 20260613 | 3 | `all` | `irc_alert` | 6,434 | 0.8528 | 0.7386 | 0.4388 | 0.8272 | 0.0012 |
| `site_retention_50` | 20260614 | 1 | `all` | `bloom_h` | 5,949 | 0.6456 | 0.6166 | 0.1197 | 0.6396 | -0.0235 |
| `site_retention_50` | 20260614 | 1 | `all` | `irc_alert` | 6,709 | 0.8413 | 0.7642 | 0.3464 | 0.8247 | -0.0100 |
| `site_retention_50` | 20260614 | 2 | `all` | `bloom_h` | 5,967 | 0.6918 | 0.5288 | 0.1572 | 0.6516 | -0.0177 |
| `site_retention_50` | 20260614 | 2 | `all` | `irc_alert` | 6,709 | 0.8125 | 0.7520 | 0.3582 | 0.7996 | -0.0120 |
| `site_retention_50` | 20260614 | 3 | `all` | `bloom_h` | 5,992 | 0.7007 | 0.4971 | 0.1752 | 0.6476 | -0.0143 |
| `site_retention_50` | 20260614 | 3 | `all` | `irc_alert` | 6,709 | 0.8413 | 0.7226 | 0.4014 | 0.8146 | -0.0114 |
| `source_scope_wqp_only` | NA | 1 | `all` | `bloom_h` | 4,673 | 0.6725 | 0.6242 | 0.1964 | 0.6623 | -0.0008 |
| `source_scope_wqp_only` | NA | 1 | `all` | `irc_alert` | 6,145 | 0.8976 | 0.8071 | 0.5053 | 0.8779 | 0.0432 |
| `source_scope_wqp_only` | NA | 2 | `all` | `bloom_h` | 4,710 | 0.7196 | 0.5486 | 0.2403 | 0.6774 | 0.0081 |
| `source_scope_wqp_only` | NA | 2 | `all` | `irc_alert` | 6,145 | 0.8831 | 0.7831 | 0.5290 | 0.8611 | 0.0495 |
| `source_scope_wqp_only` | NA | 3 | `all` | `bloom_h` | 4,757 | 0.7157 | 0.5271 | 0.2520 | 0.6679 | 0.0060 |
| `source_scope_wqp_only` | NA | 3 | `all` | `irc_alert` | 6,145 | 0.9221 | 0.7424 | 0.5938 | 0.8795 | 0.0535 |

## Guardrails

- Labels are not modified by this evaluator.
- Source-scoped site identity is preserved.
- Predictor-degradation scenarios require model recomputation for scientific performance claims.
- Degraded outputs are stress-test evidence, not official environmental alerts.

## Outputs

- Metrics: `reports/degradation/controlled_degradation_metrics.csv`
- Summary: `reports/degradation/controlled_degradation_summary.csv`
- Manifest: `reports/degradation/controlled_degradation_manifest.json`