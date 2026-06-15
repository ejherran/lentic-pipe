# Raw-Predictor Degradation Smoke

This note records the first raw-predictor recomputation smoke for controlled
degradation. It is a smoke-scale diagnostic, not a final robustness result.

## Purpose

The raw-predictor recomputation path asks a different question from the earlier
precomputed-score and PIPE-state stress tests:

> If monthly environmental predictors are removed upstream, how does the frozen
> fuzzy-state plus PIPE/GRU-D alert pipeline respond?

The run degrades predictors in the monthly panel, rebuilds the deterministic
fuzzy state, rebuilds PIPE sequence inputs, and recomputes frozen PIPE/GRU-D
rollouts. Labels, observed future states, model weights, calibrators, and alert
thresholds remain fixed.

## Current Status

Implemented artifacts:

- `src/experiments/evaluate_raw_degraded_pipe_grud_rollouts.py`;
- `tests/test_evaluate_raw_degraded_pipe_grud_rollouts.py`;
- `raw_predictor_rebuild_smoke`, `raw_predictor_rebuild_core`,
  `raw_predictor_no_chla_factorial`, `no_current_raw_smoke`, and
  `no_current_raw_core` scenario sets in `configs/degradation_scenarios.yaml`;
- configurable degraded-sequence rebuilds through `--input-surface` and
  optional `--source-ids`.

The first smoke was run with:

```bash
poetry run python src/experiments/evaluate_raw_degraded_pipe_grud_rollouts.py \
  --scenario-set raw_predictor_rebuild_smoke \
  --output-name raw_predictor_rebuild_smoke \
  --deterministic \
  --max-origins 512 \
  --batch-size 256 \
  --require-calibrators \
  --require-rollout-calibrators
```

The diagnostic smoke was regenerated on 2026-06-12 with 512 selected test
origins and three scenarios: `control_observed`, `ablate_nutrients`, and
`ablate_chlorophyll_memory`.

Reproducibility summary:

- generated at UTC: `2026-06-12T18:14:18.842832+00:00`;
- selected origins: `512`;
- evaluated runs: `3`;
- state metric rows: `396`;
- alert metric rows: `72`;
- policy metric rows: `216`;
- diagnostic rows: `75`;
- internal backtest rows: `4,608`;
- script SHA-256:
  `e371746c73ce651a27a56a8af3859aa1606043c56fd40f5cadbee0d888ddf380`;
- diagnostics SHA-256:
  `bd03993a48a7eaf301a79ec39fcddb11a88ec3f7e6a4f643cf575a11e902e995`;
- report SHA-256:
  `2174ee07b45787423b277af02a3a22deb92a3c8e8083097332b02c5c63f98c53`.

## Interpretation Guardrail

The smoke should not be read as a causal ecological experiment. It measures
dependence of the current frozen pipeline.

The strongest smoke-scale signal was that removing Chl-a memory/proxy
predictors substantially degrades alert behavior. Removing nutrient predictors
did not degrade the alert policy in the same way on this monitoring surface.
Under `closest_pr`, `source_id=all`, and `split=test`, mean metrics across
horizons were:

| scenario | event | mean F2 | mean delta F2 vs control | mean recall | mean precision |
|---|---|---:|---:|---:|---:|
| `ablate_chlorophyll_memory` | `bloom_h` | 0.2624 | -0.4272 | 0.2491 | 0.3517 |
| `ablate_chlorophyll_memory` | `irc_alert` | 0.4759 | -0.2072 | 0.4517 | 0.6253 |
| `ablate_nutrients` | `bloom_h` | 0.6915 | 0.0019 | 0.7439 | 0.5493 |
| `ablate_nutrients` | `irc_alert` | 0.7160 | 0.0329 | 0.6942 | 0.8199 |

Input diagnostics explain this behavior. On the selected windows, Chl-a-memory
ablation changes `x_yT` and moves the IRC basis upward, while nutrient ablation
changes `x_yN` but barely changes the IRC basis because the current frozen
weights give more weight to `yT`.

| scenario | input | changed rows | mean delta | mean absolute delta |
|---|---|---:|---:|---:|
| `ablate_chlorophyll_memory` | `x_yT` | 4,857 | 0.1848 | 0.3354 |
| `ablate_chlorophyll_memory` | `x_irc_basis` | 4,857 | 0.1232 | 0.2236 |
| `ablate_nutrients` | `x_yN` | 2,097 | -0.0017 | 0.1078 |
| `ablate_nutrients` | `x_irc_basis` | 2,097 | -0.0003 | 0.0180 |

The correct interpretation is:

> The current alert surface appears able to rely strongly on current Chl-a
> memory, which is target-proximal evidence for future Chl-a/bloom labels.

This does not imply that nutrients are ecologically unimportant. Nutrients are
upstream drivers of algal proliferation; current Chl-a is closer to the target
definition and can dominate a monitoring/nowcasting model.

## Early-Warning Implication

The project should distinguish:

- monitoring/nowcasting mode, where current Chl-a may be an observed input;
- no-current-Chl-a early-warning mode, where observed Chl-a is used as the
  future target for evaluation, not as a dominant current predictor.

The next factorial stress test should include:

- `control_observed`;
- `ablate_chlorophyll_memory`;
- `ablate_nutrients`;
- `ablate_chlorophyll_memory_and_nutrients`.

If nutrients become critical when current Chl-a is unavailable, that supports
the ecological precursor interpretation. If not, the project should inspect
data support, horizon choice, target construction, fuzzy weights, and model
architecture before making early-warning claims.

## No-Current-Chl-a Factorial Smoke

The factorial smoke was run on 2026-06-12 to separate Chl-a-memory dependence
from nutrient dependence on the frozen raw-predictor recomputation surface:

```bash
poetry run python src/experiments/evaluate_raw_degraded_pipe_grud_rollouts.py \
  --scenario-set raw_predictor_no_chla_factorial \
  --output-name raw_predictor_no_chla_factorial_smoke \
  --deterministic \
  --max-origins 512 \
  --batch-size 256 \
  --require-calibrators \
  --require-rollout-calibrators
```

Reproducibility summary:

- generated at UTC: `2026-06-12T18:23:58.876343+00:00`;
- selected origins: `512`;
- evaluated runs: `4`;
- state metric rows: `528`;
- alert metric rows: `96`;
- policy metric rows: `288`;
- diagnostic rows: `95`;
- internal backtest rows: `6,144`;
- script SHA-256:
  `e371746c73ce651a27a56a8af3859aa1606043c56fd40f5cadbee0d888ddf380`;
- diagnostics SHA-256:
  `5c114d72bd9e6c587acec810a488bd436da3fa9eee673482b240c07b4c2881a1`;
- report SHA-256:
  `5492e7536297025c96dd1da7c0e8c35ea32795cf6947adbc9a2da3af47603ae1`.

The undegraded control rebuild again had zero drift:

- canonical sequence rows: `2,069,024`;
- rebuilt state rows: `3,390,728`;
- rebuilt sequence rows: `2,069,024`;
- alignment missing rows: `0`;
- sequence cells changed: `0`;
- selected-window cells changed: `0`.

Under `closest_pr`, `source_id=all`, and `split=test`, mean metrics across
horizons were:

| scenario | event | mean F2 | mean delta F2 vs control | mean recall | mean precision | mean alert rate |
|---|---|---:|---:|---:|---:|---:|
| `control_observed` | `bloom_h` | 0.6896 | 0.0000 | 0.7333 | 0.5640 | 0.1750 |
| `control_observed` | `irc_alert` | 0.6831 | 0.0000 | 0.6531 | 0.8400 | 0.2689 |
| `ablate_chlorophyll_memory` | `bloom_h` | 0.2624 | -0.4272 | 0.2491 | 0.3517 | 0.0950 |
| `ablate_chlorophyll_memory` | `irc_alert` | 0.4759 | -0.2072 | 0.4517 | 0.6253 | 0.2552 |
| `ablate_nutrients` | `bloom_h` | 0.6915 | 0.0019 | 0.7439 | 0.5493 | 0.1829 |
| `ablate_nutrients` | `irc_alert` | 0.7160 | 0.0329 | 0.6942 | 0.8199 | 0.2930 |
| `ablate_chlorophyll_memory_and_nutrients` | `bloom_h` | 0.2485 | -0.4411 | 0.2545 | 0.2408 | 0.1403 |
| `ablate_chlorophyll_memory_and_nutrients` | `irc_alert` | 0.5002 | -0.1829 | 0.4908 | 0.5517 | 0.3125 |

Selected-window diagnostics show why the nutrient-only ablation did not degrade
alerts on this frozen surface:

| scenario | input | changed rows | mean delta | mean absolute delta |
|---|---|---:|---:|---:|
| `ablate_chlorophyll_memory` | `x_yT` | 4,857 | 0.1848 | 0.3354 |
| `ablate_chlorophyll_memory` | `x_irc_basis` | 4,857 | 0.1232 | 0.2236 |
| `ablate_nutrients` | `x_yN` | 2,097 | -0.0017 | 0.1078 |
| `ablate_nutrients` | `x_irc_basis` | 2,097 | -0.0003 | 0.0180 |
| `ablate_chlorophyll_memory_and_nutrients` | `x_yT` | 4,857 | 0.1848 | 0.3354 |
| `ablate_chlorophyll_memory_and_nutrients` | `x_yN` | 2,097 | -0.0017 | 0.1078 |
| `ablate_chlorophyll_memory_and_nutrients` | `x_irc_basis` | 5,313 | 0.1229 | 0.2365 |

The factorial confirms that the current frozen monitoring surface is dominated
by Chl-a memory or proxy evidence. Nutrient ablation strongly changes `yN`
state errors, but it barely moves the IRC basis under the current frozen
weights. The combined ablation mostly follows the Chl-a-removal failure mode,
with additional precision loss.

This is a useful negative result for early-warning claims. It does not imply
that nutrients are ecologically unimportant. It means the current trained and
calibrated surface is not yet a strict no-current-Chl-a early-warning model.
The next methodological step is to define, train, calibrate, and evaluate a
formal no-current-Chl-a surface where current Chl-a is excluded from predictors
before model fitting and threshold selection.

## No-Current-Chl-a Degradation Readiness

The no-current-Chl-a surface has now been trained and calibrated separately, so
the raw-predictor degradation evaluator can be reused against that frozen
surface instead of the Chl-a-aware monitoring surface.

Use `--input-surface no_current_chla` whenever the degraded monthly panel is
rebuilt for this experiment. Without this option, the raw-predictor rebuild
would reconstruct the full PIPE input surface and would no longer match the
trained no-current-Chl-a model contract. For source-focused experiments such as
WQP-focused no-current-Chl-a, also pass `--source-ids wqp` so the degraded
rebuild preserves the same source scope as the canonical sequence/model.

The configured no-current scenario sets are:

- `no_current_raw_smoke`: bounded technical check with observed control,
  nutrient ablation, light-proxy ablation, MCAR dropout, and temporal blocks;
- `no_current_raw_core`: broader robustness grid that adds physicochemical
  ablation and stronger random/temporal missingness.

These scenarios intentionally avoid `ablate_chlorophyll_memory`: the no-current
surface already excludes current observed Chl-a from model inputs. The
appropriate question is whether non-Chl-a precursor groups and missingness
patterns degrade the frozen early-warning surface.

Before interpreting any no-current degradation result, verify that
`control_observed` has no material rebuild drift. If the undegraded no-current
rebuild changes sequence inputs, fix the surface contract before making
scientific claims.

The WQP-focused no-current core full run was completed on 2026-06-15 with
`6,145` selected origins, `samples=128`, `22` evaluated runs, and zero
undegraded rebuild drift. The report is
`reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_report.md`.
It confirms that the WQP-focused strict early-warning surface is most fragile
to light-proxy ablation, physicochemical ablation, and severe MCAR missingness.
Isolated nutrient ablation degrades direct `bloom_h` more than `irc_alert`,
which should be reported as endpoint-specific behavior rather than ecological
irrelevance of nutrients.

## Reproducibility Notes

The current monthly panel includes NLA rows, but the canonical PIPE sequence
surface does not include NLA under the current conservative policy. The
raw-predictor evaluator aligns rebuilt sequences back to canonical PIPE
sequence keys, so NLA panel rows do not enter the evaluated rollout surface.

The regenerated smoke verifies this explicitly:

| source | panel rows | canonical sequence rows | selected origins | panel rows without sequence origin |
|---|---:|---:|---:|---:|
| `aquamatch_chla` | 1,755,072 | 1,078,238 | 290 | 676,834 |
| `lakebed_us_cse` | 4,932 | 4,112 | 1 | 820 |
| `nla` | 4,052 | 0 | 0 | 4,052 |
| `wqp` | 1,626,672 | 986,674 | 221 | 639,998 |

The undegraded control rebuild also showed zero drift against canonical PIPE
inputs:

- canonical sequence rows: `2,069,024`;
- rebuilt state rows: `3,390,728`;
- rebuilt sequence rows: `2,069,024`;
- alignment missing rows: `0`;
- sequence cells changed: `0`;
- selected-window cells changed: `0`.

The evaluator now writes diagnostics for:

- source-level panel versus canonical sequence coverage;
- undegraded control-rebuild drift against canonical sequence inputs;
- selected-window input changes for fuzzy-state channels and IRC basis.

These diagnostics should be regenerated before any full raw-predictor run is
committed.
