# Closure V2 statistical inference report

P14 used the five-seed family mean already frozen in P13. It resampled `source_id::site_id` clusters with replacement for 2,000 paired bootstrap replicates and never treated seeds as ecological observations.

## Registered fresh-primary contrasts

| registered_hypothesis_id   | comparison_id   |   horizon_months | metric   |    estimate |   ci95_lower |   ci95_upper | adjudication   |   shared_success_rows |   shared_success_clusters |
|:---------------------------|:----------------|-----------------:|:---------|------------:|-------------:|-------------:|:---------------|----------------------:|--------------------------:|
| P1_vs_B2_brier_h1          | P1_vs_B2        |                1 | brier    |  0.0302383  |   0.0147829  |   0.0509671  | inferior       |                   966 |                        89 |
| P1_vs_B2_pr_auc_h1         | P1_vs_B2        |                1 | pr_auc   | -0.281903   |  -0.343884   |  -0.214279   | inferior       |                   966 |                        89 |
| P1_vs_B2_brier_h2          | P1_vs_B2        |                2 | brier    |  0.02351    |   0.0092133  |   0.0396178  | inferior       |                   933 |                        88 |
| P1_vs_B2_pr_auc_h2         | P1_vs_B2        |                2 | pr_auc   | -0.158414   |  -0.21753    |  -0.093247   | inferior       |                   933 |                        88 |
| P1_vs_B2_brier_h3          | P1_vs_B2        |                3 | brier    |  0.024347   |   0.011449   |   0.0388413  | inferior       |                   885 |                        86 |
| P1_vs_B2_pr_auc_h3         | P1_vs_B2        |                3 | pr_auc   | -0.15266    |  -0.238871   |  -0.0661204  | inferior       |                   885 |                        86 |
| P1_vs_P0_brier_h1          | P1_vs_P0        |                1 | brier    |  0.00205587 |  -0.00101164 |   0.00545393 | inconclusive   |                   966 |                        89 |
| P1_vs_P0_pr_auc_h1         | P1_vs_P0        |                1 | pr_auc   | -0.0449765  |  -0.0895626  |  -0.00045566 | inferior       |                   966 |                        89 |
| P1_vs_P0_brier_h2          | P1_vs_P0        |                2 | brier    |  0.0021071  |  -0.0029514  |   0.00719287 | inconclusive   |                   933 |                        88 |
| P1_vs_P0_pr_auc_h2         | P1_vs_P0        |                2 | pr_auc   | -0.0707915  |  -0.11644    |  -0.0167148  | inferior       |                   933 |                        88 |
| P1_vs_P0_brier_h3          | P1_vs_P0        |                3 | brier    |  0.00312567 |  -0.001579   |   0.00785692 | inconclusive   |                   885 |                        86 |
| P1_vs_P0_pr_auc_h3         | P1_vs_P0        |                3 | pr_auc   | -0.0451337  |  -0.0885507  |  -0.00466064 | inferior       |                   885 |                        86 |

## Multiplicity

All registered Holm universes are retained (A=3, B=3, C=6). The protocol did not predeclare a bootstrap p-value formula or directional alternative. Therefore raw and Holm-adjusted p-values remain null; no post-outcome p-value convention was introduced. Scientific adjudication uses the preregistered percentile IC95 rules.

| hypothesis_id      | holm_family   |   holm_universe_size | holm_method   | evaluation_cohort   | estimand             | comparison_id   |   horizon_months | metric   |   effect_estimate |   ci95_lower |   ci95_upper |   raw_p_value |   holm_p_value | multiplicity_status                           | holm_universe_retained   | holm_universe_reduced   | adjudication_from_ci   |
|:-------------------|:--------------|---------------------:|:--------------|:--------------------|:---------------------|:----------------|-----------------:|:---------|------------------:|-------------:|-------------:|--------------:|---------------:|:----------------------------------------------|:-------------------------|:------------------------|:-----------------------|
| P1_vs_B2_brier_h1  | A             |                    3 | holm          | fresh_primary       | observation_weighted | P1_vs_B2        |                1 | brier    |        0.0302383  |   0.0147829  |   0.0509671  |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inferior               |
| P1_vs_B2_brier_h2  | A             |                    3 | holm          | fresh_primary       | observation_weighted | P1_vs_B2        |                2 | brier    |        0.02351    |   0.0092133  |   0.0396178  |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inferior               |
| P1_vs_B2_brier_h3  | A             |                    3 | holm          | fresh_primary       | observation_weighted | P1_vs_B2        |                3 | brier    |        0.024347   |   0.011449   |   0.0388413  |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inferior               |
| P1_vs_P0_brier_h1  | B             |                    3 | holm          | fresh_primary       | observation_weighted | P1_vs_P0        |                1 | brier    |        0.00205587 |  -0.00101164 |   0.00545393 |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inconclusive           |
| P1_vs_P0_brier_h2  | B             |                    3 | holm          | fresh_primary       | observation_weighted | P1_vs_P0        |                2 | brier    |        0.0021071  |  -0.0029514  |   0.00719287 |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inconclusive           |
| P1_vs_P0_brier_h3  | B             |                    3 | holm          | fresh_primary       | observation_weighted | P1_vs_P0        |                3 | brier    |        0.00312567 |  -0.001579   |   0.00785692 |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inconclusive           |
| P1_vs_B2_pr_auc_h1 | C             |                    6 | holm          | fresh_primary       | observation_weighted | P1_vs_B2        |                1 | pr_auc   |       -0.281903   |  -0.343884   |  -0.214279   |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inferior               |
| P1_vs_B2_pr_auc_h2 | C             |                    6 | holm          | fresh_primary       | observation_weighted | P1_vs_B2        |                2 | pr_auc   |       -0.158414   |  -0.21753    |  -0.093247   |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inferior               |
| P1_vs_B2_pr_auc_h3 | C             |                    6 | holm          | fresh_primary       | observation_weighted | P1_vs_B2        |                3 | pr_auc   |       -0.15266    |  -0.238871   |  -0.0661204  |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inferior               |
| P1_vs_P0_pr_auc_h1 | C             |                    6 | holm          | fresh_primary       | observation_weighted | P1_vs_P0        |                1 | pr_auc   |       -0.0449765  |  -0.0895626  |  -0.00045566 |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inferior               |
| P1_vs_P0_pr_auc_h2 | C             |                    6 | holm          | fresh_primary       | observation_weighted | P1_vs_P0        |                2 | pr_auc   |       -0.0707915  |  -0.11644    |  -0.0167148  |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inferior               |
| P1_vs_P0_pr_auc_h3 | C             |                    6 | holm          | fresh_primary       | observation_weighted | P1_vs_P0        |                3 | pr_auc   |       -0.0451337  |  -0.0885507  |  -0.00466064 |           nan |            nan | not_applied_bootstrap_p_value_not_predeclared | True                     | False                   | inferior               |

## Scope

`fresh_primary` supports internal evaluation on WQP monitoring locations unused by V1, not external validation. `legacy_posthoc` remains retrospective/complementary. Cohorts and observation/site-weighted estimands were never pooled. No global winner, equivalence, field causality, or official recommendation is claimed.

- P13 authority commit: `047c614944e66b2ba7e5229cc289ce317ba3602a`
- P13 evaluation manifest SHA-256: `5d3fe8702c29ca27fa6c8565a6a81a013b41555964dd92e0a095476f5344bafb`
- inference script SHA-256: `eccc09d73bd6b9a1ea0e65c27f3b6d5b83350095edae9506b8459f5397903ab6`
