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
- `raw_predictor_rebuild_smoke`, `raw_predictor_rebuild_core`, and
  `raw_predictor_no_chla_factorial` scenario sets in
  `configs/degradation_scenarios.yaml`.

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
