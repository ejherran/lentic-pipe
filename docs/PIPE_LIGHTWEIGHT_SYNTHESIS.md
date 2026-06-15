# PIPE Lightweight Synthesis

Updated: 2026-06-15

This document closes the current PIPE lightweight block as a reproducible
comparison surface. It summarizes what is supported by the expert/refined
fuzzy state, IRC scores, PIPE/GRU-D, rollout alert policies, and the
no-current-Chl-a variants.

This is not the closure of adaptive ANFIS, Neural ODE, MIFAL, counterfactual
planning, or the final thesis evaluation matrix. Those remain separate
project phases.

## Scope

The lightweight PIPE block has three evaluated surfaces:

| Surface | Role | Current Chl-a as input? | Source scope | Primary use |
|---|---|---:|---|---|
| Chl-a-aware PIPE/GRU-D | Monitoring and nowcasting reference | yes | multi-source, excluding NLA targets under the current source-scoped policy | strongest operational comparison surface |
| No-current-Chl-a all-source | Strict early-warning sensitivity surface | no | multi-source | exploratory, limited by source-scoped precursor coverage |
| No-current-Chl-a WQP-focused | Strict early-warning main surface | no | WQP only | fair source-scoped test of non-Chl-a precursor signal |

The no-current surfaces exclude current observed Chl-a before model fitting,
rollout calibration, and threshold selection. Future observed Chl-a-derived
state remains the target used for evaluation.

## Artifact Inventory

Heavy sequence, row-level rollout, calibrated-row, and model artifacts are
managed through DVC pointers. Small reports, manifests, CSV summaries, and this
synthesis remain Git artifacts.

| Surface | Sequence artifact | Model/report evidence | Rollout and policy evidence | DVC status |
|---|---|---|---|---|
| Chl-a-aware | `data/pipe_grud/pipe_sequence_dataset_v0.parquet` | `reports/pipe_grud/pipe_grud_report.md`, `reports/pipe_grud/pipe_grud_manifest.json` | `docs/PIPE_ROLLOUT_ITERATION_2.md`, `reports/pipe_grud/pipe_rollout_policy_2b_report.md` | sequence, row-level rollouts, calibrated rows, and models are pointer-only |
| No-current all-source | `data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet` | `reports/pipe_grud/no_current_chla/pipe_grud_report.md`, `reports/pipe_grud/no_current_chla/pipe_grud_manifest.json` | `reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_report.md`, `reports/pipe_grud/no_current_chla/no_chla_operational_surface_audit_report.md` | sequence, row-level rollouts, calibrated rows, and models are pointer-only |
| No-current WQP-focused | `data/pipe_grud/pipe_sequence_dataset_no_current_chla_wqp_focused_v0.parquet` | `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_report.md`, `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_manifest.json` | `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_policy_2b_report.md`, `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_report.md` | sequence, row-level rollouts, calibrated rows, and models are pointer-only |

The WQP-focused degradation full run did not materialize degraded row-level
backtest parquet output. No additional DVC-tracked degraded row-level artifact
is required for this closure.

## Comparable Evidence

The table below keeps the comparison at the level used for thesis discussion:
state prediction, rollout alert ranking, and validation-selected policies.

| Surface | One-step test state evidence | Test rollout origins | Fixed IRC PR-AUC h1/h2/h3 | 2B `closest_pr` IRC behavior |
|---|---|---:|---|---|
| Chl-a-aware | all-state RMSE `0.1091`; PIPE/GRU-D improves persistence in the promoted surface | `13,327` | `0.8894 / 0.8769 / 0.8702` | recall `0.850 / 0.825 / 0.854`; precision `0.779 / 0.762 / 0.731`; alert rate `0.364 / 0.375 / 0.417`; F2 `0.835 / 0.812 / 0.826` |
| No-current all-source | all-state RMSE `0.1359`; all-state RMSE improves no-current persistence by `30.7%` | `13,327` | `0.6532 / 0.6346 / 0.6147` | mean recall `0.8564`; mean precision `0.4215`; mean alert rate `0.7026`; mean F2 `0.7097` |
| No-current WQP-focused | all-state RMSE `0.1525`; all-state RMSE improves WQP no-current persistence by `31.8%` | `6,145` | `0.7963 / 0.7456 / 0.7276` | recall `0.7636 / 0.8287 / 0.8907`; precision `0.6976 / 0.6903 / 0.6478`; alert rate `0.4973 / 0.5632 / 0.6574`; F2 `0.7494 / 0.7967 / 0.8286` |

Interpretation:

- Chl-a-aware remains the strongest monitoring/nowcasting surface when current
  Chl-a is available.
- The all-source no-current surface retains signal, but its alert burden is
  high because many target-rich rows lack same-source non-Chl-a precursors.
- WQP-focused no-current is the fair strict early-warning surface under the
  current source-scoped policy.

## Controlled Degradation

The main strict early-warning degradation gate is the WQP-focused no-current
full run:

- report:
  `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_report.md`;
- manifest:
  `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_manifest.json`;
- scenario set: `no_current_raw_core`;
- selected origins: `6,145`;
- samples per origin: `128`;
- evaluated runs: `22`;
- rebuilt input surface: `no_current_chla`;
- rebuilt source filter: `["wqp"]`;
- control rebuild drift: zero missing alignment rows and zero changed sequence
  or selected-window input cells.

Under the default experimental `closest_pr` policy, mean held-out test
`irc_alert` behavior across horizons was:

| Scenario | Mean recall | Mean precision | Mean alert rate | Mean F2 | Mean delta F2 |
|---|---:|---:|---:|---:|---:|
| `control_observed` | `0.8031` | `0.7546` | `0.5727` | `0.7918` | `0.0000` |
| `ablate_light` | `0.4855` | `0.8428` | `0.3088` | `0.5299` | `-0.2619` |
| `ablate_physicochemical` | `0.5138` | `0.7275` | `0.3782` | `0.5452` | `-0.2466` |
| `ablate_nutrients` | `0.8427` | `0.7214` | `0.6292` | `0.8137` | `0.0219` |
| `random_dropout_mcar_10` | `0.7541` | `0.7625` | `0.5317` | `0.7547` | `-0.0371` |
| `random_dropout_mcar_25` | `0.6670` | `0.7734` | `0.4635` | `0.6849` | `-0.1069` |
| `random_dropout_mcar_50` | `0.4781` | `0.7831` | `0.3276` | `0.5178` | `-0.2740` |
| `temporal_blocks_6m_rate_25` | `0.7847` | `0.7556` | `0.5590` | `0.7776` | `-0.0142` |

For direct `bloom_h`, nutrient ablation is more damaging: mean F2 falls from
`0.5280` to `0.3556`. This supports a careful interpretation: nutrients affect
the direct bloom endpoint and the `yN` channel, but the current aggregated
`irc_alert` endpoint is more fragile to light proxies, physicochemistry, and
severe MCAR missingness under frozen IRC weights and frozen thresholds.

## Closure Decision

The lightweight PIPE block can be treated as closed as a comparative baseline
for the next project phase, subject to the normal commit-preparation checks.

Closed within this block:

- expert/refined fuzzy state and IRC as the current interpretable state layer;
- PIPE/GRU-D one-step state prediction;
- recursive rollouts and alert backtests;
- validation-selected 2B policy frontier with `closest_pr` as the provisional
  downstream default;
- no-current-Chl-a all-source exploratory surface;
- no-current-Chl-a WQP-focused strict early-warning surface;
- controlled degradation evidence for the WQP-focused no-current surface.

Not closed by this block:

- adaptive ANFIS-N, ANFIS-F, and ANFIS-T;
- PIPE/GRU-D retraining over an adaptive ANFIS state;
- Neural ODE as a temporal PIPE variant;
- MIFAL-ED/T2 as a required parallel comparator;
- counterfactual planning;
- REST/OpenAPI delivery;
- final thesis-wide evaluation matrix.

## Allowed Claims

- The Chl-a-aware PIPE/GRU-D surface is the strongest evaluated
  monitoring/nowcasting reference in the current lightweight block.
- Strict no-current early warning is feasible under the WQP-focused surface,
  with useful multi-horizon IRC alert skill.
- All-source no-current results are informative but coverage-limited under the
  current source-scoped policy.
- Current Chl-a is operationally informative; removing it lowers precision and
  increases alert burden for comparable recall.
- WQP-focused no-current robustness is most sensitive to light-proxy removal,
  physicochemical removal, and severe random missingness.
- Nutrients remain relevant to the direct bloom endpoint, even though isolated
  nutrient ablation does not degrade aggregate `irc_alert` under the current
  weights and policy.

## Claims To Avoid

- Do not claim that no-current early warning replaces Chl-a-aware monitoring.
- Do not claim that nutrients are ecologically unimportant.
- Do not treat all-source no-current as a fair strict precursor test for every
  source without accepted cross-source equivalences.
- Do not present `closest_pr`, fixed thresholds, or F2 thresholds as official
  environmental alert policies.
- Do not call the current fuzzy layer an adaptive ANFIS.
- Do not imply that Neural ODE, MIFAL, or counterfactual planning are already
  implemented by this closure.

## Next Phase

The next technical phase should move from PIPE lightweight to PIPE
robust/adaptive:

1. audit the current fuzzy/ANFIS code path and reports;
2. design an adaptive ANFIS protocol for `ANFIS-N`, `ANFIS-F`, and `ANFIS-T`;
3. implement a bounded smoke training/evaluation loop;
4. compare expert/refined fuzzy state against adaptive ANFIS state;
5. then re-evaluate PIPE/GRU-D and, separately, attempt Neural ODE.
