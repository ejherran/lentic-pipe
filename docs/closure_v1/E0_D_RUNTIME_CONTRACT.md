# Closure V1 E0-D Runtime Contract

Status: proposed derived implementation contract with machine status
`ready_to_lock`. It does not amend the 13 externally sealed E0-P components.
It does not authorize fitting, scoring, post-2021 outcome access, or E0-U.

## Purpose

The locked protocol fixes the primary no-current-Chl-a surface, models, five
seeds, temporal roles, and evaluation rules. Historical ANFIS and PIPE runners
do not implement those decisions strictly enough for Closure V1. This derived
contract closes the remaining pre-fit implementation details:

1. the exact Chl-a-free raw projection and deterministic ANFIS sample;
2. the exact ANFIS profile and one-to-one seed plan;
3. the exact nine-channel input, target, and recursive-rollout lineage;
4. the P0/P1 optimization, early stopping, blend, and rollout profile; and
5. the evidence paths and external pre-fit implementation-lock lifecycle.

The machine-readable authority is:

- `configs/closure_v1/development_runtime.yaml`;
- `configs/closure_v1/development_runtime.schema.json`; and
- `src/experiments/closure_runtime_contract.py`.

The schema is closed: a changed epoch count, training size, sampling algorithm,
module, seed, mapping, role, architecture, output policy, or outcome-access
flag requires a new schema and explicit review. The validator also recomputes
every sealed protocol-component hash and cross-checks the E0-C assignment,
locked analysis plan, primary surface, model benchmark, locked target metadata,
and the exact historical ANFIS and PIPE reference-manifest hashes.

## Common-Origin Completion Gate

The common-origin table is a separate, outcome-independent E0-D artifact. Its
completion manifest must bind exactly one Parquet output to the five locked
source records, five repository-local code dependencies, eight transitively
read Closure configuration files, and three E0-P/E0-C parent artifacts. The
manifest records the base Git HEAD and tracked worktree state honestly; the
file-record SHA-256 values, rather than a dirty base HEAD, identify the source
tree used for materialization.

Runtime validation requires the exact no-current-Chl-a panel projection, the
five target key columns only, the cutoff predicates, scan conservation,
role/horizon availability counts, 353 development locations, zero holdout
overlap, and no row after 2021-12. Every recorded code, configuration, parent,
and restored output hash is recomputed. A source-only clone may validate the
committed completion manifest while reporting the DVC payload as absent; any
fit gate must additionally require both `common_origin_materialized=true` and
`common_origin_output_verified=true`.

The protocol-locked base DVC inventory remains byte-for-byte unchanged.
Post-lock Closure artifacts are declared in the anchored
`configs/closure_v1/dvc_artifacts_post_lock.yaml` overlay. The precommit
assistant must validate the completion manifest whenever either it or the
common-origin DVC pointer changes.

## Why The Historical Mapping Is Denied

The historical `adaptive_no_current_chla` sequence mode changes the thermal
input channels to no-current-Chl-a sources, but leaves the target channels on
the full adaptive state. In particular:

```text
target_delta_yT(t+1)
= yT_adaptive(t+1) - yT_adaptive(t)
```

The second term contains observed Chl-a lineage from the origin month. The
historical rollout then recycles all nine predicted targets as the next input,
so a full-state target and a no-current input do not have the same semantics.
This is valid historical evidence, but it is not the strict primary Closure V1
surface.

This is an implementation clarification of protocol v1.1, not a new scientific
endpoint or a protocol amendment. The sealed primary surface already requires
the explicitly no-Chl-a trophic state and its uncertainty/change channels, and
the historical rollout recycles each predicted target into the next input.
Using the full T-state targets would therefore violate the sealed input lineage
from horizon 2 onward. A v1.2 amendment would be required only to permit that
full state, change the scientific endpoints, or replace the recursive
architecture.

The Closure adapter must not call the legacy mapping directly. It must read the
derived contract, validate it, and persist its config/schema hashes in every
state, sequence, and model manifest. Each sequence manifest must persist three
separate, exactly equal contracts where applicable: `input_state_mapping`,
`target_state_mapping`, and `target_to_next_input_mapping`.

## Fixed ANFIS Profile

The primary surface fits exactly three modules:

- `ANFIS-N` from nutrient-pressure features;
- `ANFIS-F` from physicochemical-condition features; and
- `ANFIS-T-no-current` from temperature favorability only.

`ANFIS-T`, which consumes current Chl-a pressure, is forbidden in the primary
runner, input projection, state artifact, and checkpoint directory. It may be
implemented only later under the secondary A2 namespace.

The fixed primary profile is the completed WQP configuration recorded in
`reports/anfis/adaptive_anfis_state_manifest.json`:

| Decision | Fixed value |
|---|---:|
| Training rows per module | 4,096 |
| Memberships per input | 3 |
| Center constraint | `unit` |
| Epochs | 60 |
| Learning rate | 0.03 |
| Minimum width | 0.03 |
| Minimum center gap | 0.0001 |
| Gradient clip | 1.0 |
| Optimizer | AdamW, zero weight decay |
| Loss | Full-batch anchor MSE |
| Output activation | Sigmoid |
| Missing-feature imputation | 0.5, clipped to `[0, 1]` |
| Maximum training missing fraction | 0.5 |
| Minimum output standard deviation | 0.0001 |
| Prediction batch rows | 32,768 |

Model construction is also fixed: initial Gaussian width 0.25, unit-center
margin 0.05, zero Sugeno consequent weights/biases, and normalized firing
strength floor `1e-12`. For `R` rules, the model's unnormalized float32 firing
strengths `f_r` are quantized to float32 and then cast to float64 before
summation; wider caller numerics cannot bypass that boundary. The proxy is then
computed entirely in float64 as:

```text
denominator = max(fsum_r(f_r), 1e-12)
p_r = f_r / denominator
p_safe = clip(p_r, 1e-12, 1)
H = -sum_r(p_r * ln(p_safe))
H_norm = H / ln(R) if R > 1 else 0
uncertainty = clip(0.10 + 0.45 * H_norm + 0.35 * missing_fraction, 0, 1)
```

The missing fraction and final arithmetic are float64. An all-zero firing row
therefore keeps all `p_r=0` and has zero entropy; substituting a uniform rule
distribution is forbidden. The production adapter is module-aware and requires
exactly 27, 81, or 3 firing strengths for ANFIS-N, ANFIS-F, or
ANFIS-T-no-current. Golden vectors cover normalization, the one-rule case, and
the all-zero floor edge case.

The current generic CLI default of 80 epochs is not the promoted WQP profile
and is rejected. There is no hyperparameter search and no best-seed selection.
The E7 sizes 4,096, 16,384, and 65,536 remain a separate sensitivity analysis;
they cannot replace the fixed primary fit retrospectively.

Training candidates pass one fixed pipeline: raw projection at Parquet read;
WQP development/training filtering through 2018-12; an audited expert-anchor
join; allowed feature construction; finite module-anchor filtering;
per-module feature-missingness filtering at `<=0.5`; and only then SHA-256
ranking. The panel projection reads the exact key `(source_id, site_id,
year_month)` plus exactly eight raw fields: TP, TN, TN:TP ratio, dissolved
oxygen, pH, turbidity, Secchi depth, and temperature. The expert-anchor
projection reads only the same exact key and `yN`, `yF`, and `yT_no_chla`.

Both projected key sets must be non-null and unique, and both are constrained
by the WQP/development/training-through-2018-12 guard before joining. Duplicate
keys fail. The filtered frames are joined with `inner` semantics and
`one_to_one` validation. The join audit persists the panel-row, anchor-row,
matched, panel-only, and anchor-only counts and deterministic identities and
digests for each key set. It must verify both conservation equations:

```text
panel_rows = matched_rows + panel_only_rows
anchor_rows = matched_rows + anchor_only_rows
```

Only matched rows may enter feature construction or ranking; unmatched rows
cannot become silently eligible. The generic historical feature builder is
denied because it materializes current Chl-a before discarding its derived
feature. No scientific outcome or observed-Chl-a value, derivative, count, QC,
missingness, provenance, state sibling, or alias may reach adapter logic.

The eight derived transformations are also closed, not merely their parent
columns: TP and TN use log ramps (`10--100`, epsilon `0.1`; `300--1500`,
epsilon `0.1`); ratio imbalance is the maximum of a ramp down over `8--16` and
a ramp up over `50--100`; DO and pH use trapezoids `5/7/12/15` and
`6.5/7/8.6/9.5`; turbidity and Secchi use ramps `5--50` down and `0.5--3` up;
and temperature uses trapezoid `15/22/30/35`. Invalid, nonfinite, and negative
log inputs become missing. Outputs are float64 in `[0,1]`. Golden vectors are
mandatory for the strict adapter.

The requested 4,096 eligible keys are selected without replacement by
`sha256_rank_json_v1`. Immutable key strings must already be Unicode NFC and
are never rewritten; months must be strict `YYYY-MM`. JSON uses UTF-8,
`ensure_ascii=false`, and compact separators. Each rank is SHA-256 over
`[module_seed, source_id, site_id, year_month]`. Aggregate digests append one
LF byte after every compact JSON key record. The universe is ordered by compact
JSON UTF-8 bytes; selected keys remain in rank order. Ranking tie-breaks by
digest, UTF-8 source/site, and month. Null, non-string, whitespace-bearing,
non-NFC, or duplicate keys fail. The input/exclusion counts, universe and
selected digests, module/base/module seeds, and ranked keys are persisted.
Fewer than 4,096 eligible rows makes the slot unavailable without replacement;
this is a Closure reproducibility rule, distinct from the historical runner's
use of 4,096 as a maximum. The production sampler exposes no row-count
override; the two-row selection exists only inside the fixed golden-vector
helper.

F0 and F1 use the same fixed IRC weights `1/1/1`. Historical weights selected
with all locations are not inherited by the Closure V1 primary fit.

## Five Paired Seed Slots

The ordered base seeds are:

```text
1729, 20260612, 20260613, 20260614, 314159
```

For base seed `s`, both ANFIS sampling and optimization use fixed module
substreams:

```text
ANFIS-N            s + 101
ANFIS-F            s + 202
ANFIS-T-no-current s + 404
```

Offset `303` is reserved for a future secondary current-Chl-a module. Within
each ordered slot, the ANFIS base seed, P0 model seed, and P1 model seed are
identical. The 5-by-5 Cartesian product, best-seed selection, missing-seed
replacement, and reuse of one ANFIS state for all P1 seeds are forbidden.
Each module substream is set before model construction and is reused for that
module's sampling and optimization.

Each ANFIS/P1 seed has separate state, sample-key, checkpoint, and sequence
paths, plus metrics, learning curves, memberships, lineage audits, reports,
and manifests. P0 shares its deterministic expert state and sequence, while
retaining separately seeded temporal models/checkpoints for every paired slot.
A failed slot remains in the failure denominator; it is never silently
replaced.

## Strict Autoregressive State

The 13 inputs remain nine state channels plus four deterministic seasonal
channels. The nine targets must have the same state semantics because every
target is eligible to become the next recursive input.

| Canonical state channel | P0 source for input and target | P1 source for input and target |
|---|---|---|
| `yN` | `yN` | `yN_adaptive` |
| `yF` | `yF` | `yF_adaptive` |
| `yT` | `yT_no_chla` | `yT_no_chla_adaptive` |
| `sigma_N` | `sigma_N` | `sigma_N_adaptive` |
| `sigma_F` | `sigma_F` | `sigma_F_adaptive` |
| `sigma_T` | `sigma_T_no_chla` | `sigma_T_no_chla_adaptive` |
| `delta_yN` | `delta_yN` | `delta_yN_adaptive` |
| `delta_yF` | `delta_yF` | `delta_yF_adaptive` |
| `delta_yT` | `delta_yT_no_chla` | `delta_yT_no_chla_adaptive` |

No optional context column may be serialized. This excludes `x_irc1`,
`x_irc1_adaptive`, observed Chl-a, `risk_chla`, `Chl_prev`, counts, QC fields,
and aliases with the same lineage even when the trainer does not currently read
them.

The four seasonal channels use calendar month `m` with
`r = 2*pi*(m-1)/12`: annual sine/cosine are `sin(r), cos(r)` and semiannual
sine/cosine are `sin(2r), cos(2r)`. They are calculated in float64 and cast to
the model float32 tensor afterward.

Deltas mean current state minus the exact previous calendar month. The adapter
never substitutes the previous available row when the exact month is absent.
For a true first observation or a gap, all three deltas are zero and the
audit-only `delta_previous_month_missing=true` flag is set. The flag is outside
the 13 model inputs, and its count is mandatory in the state and sequence
manifests. Interior history gaps make an origin ineligible through the common-
origin contract; an older row is never reused as if it were adjacent.
Level and uncertainty channels are bounded in `[0,1]`, while their signed
current-minus-previous deltas are bounded in `[-1,1]`. A global `[0,1]` clip
would erase every negative change and is therefore forbidden.

State export is limited to development locations and the `training`,
`model_selection`, and `calibration_threshold` roles through 2021-12. It emits
all eligible site-months; bounded exports are forbidden. P0 has one shared,
deterministic expert state. P1 has one adaptive state per ANFIS seed. Their
closed output allowlists omit all full current-Chl-a T-state siblings and IRC
context columns.

The temporal model fits adjacent one-month transitions. Horizons 1--3 are
produced by recursive rollout over the same no-current state semantics.

## Fixed P0/P1 Temporal Profile

P0 and P1 differ only in their state source: P0 reads the deterministic expert
no-current state, while P1 reads the ANFIS no-current state from the same seed
slot. Both are residual probabilistic GRUs, not canonical GRU-D models. The
closed common profile uses 13 inputs, nine targets, history 12, hidden width 96,
one recurrent layer, zero dropout, `batch_first`, and residual `add_last`.

Optimization uses AdamW (`lr=0.001`, weight decay `1e-5`), gradient clip 1,
batch 2,048, and the historically promoted target weights. Log variance is
clipped to `[-10,2]`; weighted diagonal-Gaussian loss is
`0.5*(logvar + squared_error/exp(logvar))`, omitting the constant, and the
weighted MSE is added with weight 1. Both reduce by the arithmetic mean over
all rows and nine targets. All eligible training and model-selection windows
are used; row truncation, resume, nonfinite replacement, test windows, and
holdout windows are forbidden. A supervised endpoint's origin and target must
share its role, but its earlier 12-month input context may come from the
preceding role. Context rows contribute no endpoint loss, and a window cannot
break only because that input history crosses a role boundary.

Before any DataLoader is constructed, each training and model-selection window
table is sorted in ascending order by UTF-8 `source_id`, UTF-8 `site_id`,
`origin_year_month`, and `target_year_month`. Dataset indices are assigned from
that canonical order. Python, NumPy, and Torch are seeded with the paired base
seed before model construction. Training creates a new Torch generator per
one-based epoch with seed `base_seed + epoch` and uses it to permute the
canonical training indices. It uses zero workers and does not drop the final
batch. The complete model-selection set remains in canonical order with no
shuffle. The ordered batch-index digest for every epoch is persisted.

Deterministic Torch/cuDNN settings are mandatory. Automatic device choice is
forbidden: E0-DL records and locks the explicit device, environment, and, for
CUDA, `CUBLAS_WORKSPACE_CONFIG=:4096:8`. No cross-device
numerical-equivalence claim is made. Training loss is computed from the raw
residual-model `mu`, before any output blend with persistence.

At the end of every epoch, the fixed nine-value blend grid is recomputed
independently for each target over all canonical model-selection windows. No
blend weight is carried from a prior epoch, and neither training nor
calibration rows may fit it. The current epoch's selected weights produce the
blended model-selection predictions used for that epoch's checkpoint
objective. Checkpoint selection is half RMSE and half MAE relative to the
persistence all-target mean, with scale floor `1e-12`. Per-target blend
selection is half MAE divided by the minimum-grid MAE and half RMSE divided by
the minimum-grid RMSE, also with floor `1e-12` and the declared tie-break.

Training stops at 20 epochs or after five consecutive completed
model-selection epochs without improvement (`min_delta=0`), with an exact
checkpoint-objective tie favoring the earliest epoch. The earliest best raw
checkpoint is restored, then the nine-value grid is recomputed once over the
complete canonical model-selection set to produce the final locked per-target
blend weights. The historical trainer does not implement this exact cycle and
therefore cannot be invoked directly.

Rollout uses horizons 1--3, 128 diagonal-Gaussian samples per origin, and batch
512. Each origin reinitializes NumPy `PCG64` from the first 128 SHA-256 bits of
compact JSON `["closure_v1", base_seed, source_id, site_id,
origin_year_month]`. P0/P1 share common random numbers within a paired slot,
and a `(3,128,9)` float64 standard-normal tensor is drawn in
horizon/sample/channel order before batching. Thus origin ordering and batch
size cannot change draws. This complete PCG64 predraw remains float64 for the
audit. Its golden record includes the base seed and origin identity plus the
SHA-256 digest of the full C-contiguous, little-endian IEEE-754 float64 byte
representation in horizon/sample/channel order; the complete digest, rather
than selected epsilon sentinels, locks the tensor.

For every trajectory and channel, rollout computes
`mu_blend = persistence + w*(mu-persistence)`, then
`sigma = exp(0.5*clip(logvar,-10,2))`, and finally
`sample = mu_blend + sigma*epsilon`. Model inputs and raw `mu/logvar` outputs
are float32. The scalar kernel explicitly quantizes persistence, `mu`, and
`logvar` to float32 before casting them to float64; the grid blend weight is
already float64. Blend, variance, sampling, and clipping then remain float64,
including epsilon. The clipped sampled state is cast exactly once to float32
before recycling. Seasonality is computed in float64 and cast exactly once to
float32 before it is appended, so every next model window is float32.

The rollout clips levels/uncertainties to `[0,1]` and signed deltas to
`[-1,1]`, recycles each sampled trajectory independently, drops the oldest
window row, and advances exactly one month. Recycling an aggregate/mean
trajectory is forbidden. In addition to the full predraw digest, a fixed
two-horizon scalar fixture supplies `mu`, `logvar`, persistence, blend weights,
and epsilon values. Its two exact float32 recycled states lock the cast point
and recursive use of the preceding state. Closure IRC weights are `1/1/1`;
historical rollout weights `0.5/0.5/2.0` are not inherited.

## Scientific Outcomes Stay Separate

The scientific outcomes are not autoregressive state targets:

| Canonical outcome | Frozen target source |
|---|---|
| `future_chla_ugL` | `future_chlorophyll_a_ugL` |
| `bloom_h` | `bloom_h` |
| `future_risk` | `target_risk_chla_h` |
| `future_operational_trophic_state` | `target_trophic_state_h` |

They are joined only after the state sequence is frozen, on the exact common
key `(source_id, site_id, origin_year_month, target_year_month,
horizon_months)`. The common-origin/intent-to-predict table is the left frame;
the target join must validate `one_to_one`, fail on duplicate target keys,
retain unmatched origins with `target_unavailable`, and verify that target month
equals origin plus horizon. An inner join or silent target-unavailable row drop
is forbidden. The join requires a separate manifest.

These four columns are not independent outcomes. `bloom_h`, future risk, and
the operational trophic label are deterministic transforms of the same future
monthly Chl-a value. E4A is therefore explicitly a future-Chl-a trophic proxy.
The non-Chl-a Carlson references E4B and the separate cross-sectional NLA
reference E4C remain pending separate contracts and artifacts; neither exists
in this runtime gate.

The outcomes cannot enter the input tensor, recursive state, ANFIS row
selection, preprocessing, or model-fit predictors.

During E0-D, the storage-level cutoff remains target month 2021-12. Post-2021
outcome values, availability, QC, counts, nullness, and summaries remain sealed
until E0-U. The runtime validator does not semantically decode the historical
target manifest or the promoted ANFIS/PIPE manifests because they contain
legacy aggregate metrics. It checks their exact accepted hashes as opaque
bytes; the target policy needed here is duplicated in the closed runtime.

## Manifest And Lock Requirements

Every dependent artifact must record hashes for the runtime config, schema and
external E0-DL lock, plus the protocol lock, assignment, common-origin
manifest, inputs, code, and outputs.
The common-origin completion manifest is hashed separately from its Parquet.
Sequence manifests must also record the exact input, target, and target-to-next-
input mappings. All manifests must attest, as applicable:

- zero holdout overlap;
- the exact seed slot and module substreams;
- exact feature and state mappings;
- exact raw Parquet projections and closed state allowlists;
- exact common keys;
- one-month delta geometry;
- the `delta_previous_month_missing` count;
- left-join target cardinality and retained target-unavailable rows;
- zero optional context columns; and
- zero post-2021 materialization.

Heavy state, sequence, and model artifacts are DVC-managed. JSON, CSV, and
Markdown audits may remain in Git when small.

The singular paths in the sealed primary-surface config are logical paths. The
runtime resolves them to five concrete P1 state/sequence paths, one per seed,
and requires every logical-to-concrete record in the external lock. P0 uses one
shared deterministic expert state and sequence. Planned paths also cover ANFIS
sample keys, metrics, curves, memberships, reports and manifests, plus P0/P1
checkpoints, identity-preprocessor contracts, blend evidence, rollouts, and
their manifests. Expansion produces exactly 201 canonical repository-relative
paths under only `data/closure_v1`, `models/closure_v1`, and
`reports/closure_v1`. Their UTF-8 ascending, LF-delimited digest is
`833fe57a573db135357a596949728fd0b6a436997ece0ba2c5555b815a42672c`.
Traversal, aliases, symlink escape, and canonical collisions fail. E0-DL
persists the complete expanded path records and one DVC ownership strategy for
every planned heavy path: either an existing directory owner or a future
explicit pointer. Heavy pre-fit inputs that are already materialized, including
the common-origin and expert-state artifacts, must actually be DVC-registered
and verifiable under that strategy before the lock. An output that does not yet
exist records only its planned owner; it cannot claim a pointer, remote object,
or content hash. Creating empty or stale pointers for such outputs is
forbidden.

ANFIS/PIPE states, models, checkpoints, sequences, and rollouts can only be
materialized after E0-DL authorizes fit. After fit, every newly materialized
heavy output must be added to its declared owner, pushed, and verified before
E0-M and before any commit claims that artifact as published. Its manifest
records the resolved owner or pointer and the artifact content hash. This
post-fit registration does not authorize evaluation or unseal E0-U.

The pre-fit implementation gate is `E0-DL`. The runtime YAML remains
`ready_to_lock` to avoid a circular hash. Once the common-origin artifact,
strict adapters, tests, and locker exist in a clean commit `H`, an external
`development_runtime_lock.json` must record `H`, every parent/config/code/test
hash, expanded seed paths, zero-overlap/no-future audits, and authorization of
development fit only. That lock bundle is reviewed and committed in a clean
descendant `L`. Fit is allowed only when `H` remains an ancestor and all hashes
match. Evaluation and E0-U stay false.

Before generating E0-DL, the full repository type check must pass and the
restored panel/expert-state development sources must match their locked hashes.
The outcome Parquet and target manifest are not restored or opened by that
source check. E0-DL records the recursive repository-local import closure of
the strict adapters. If they reuse historical kernels, hashes must include at
least the expert fuzzy functions, adaptive ANFIS core, feature transforms,
sequence builder, temporal trainer, rollout core, and their local dependencies;
an adapter filename alone is not sufficient provenance.

The real common-origin Parquet and completion manifest now exist and pass the
strict runtime gate: 29,196 horizon rows represent 9,732 origins from all 353
development locations, with no holdout overlap or post-2021 row. The DVC
pointer, completion manifest, and matching remote object must all be published
before this artifact is treated as remotely restorable or consumed by E0-DL.
The strict model adapters, locker, and external E0-DL lock do not yet exist, so
the validator still returns `fit_authorized=false`. E0-DL does not replace
E0-M: checkpoints, calibrators, thresholds, ordinal cutpoints, hypotheses, and
the sealed batch command still require the later model lock before E0-U.

## Validation

Metadata-only validation is:

```bash
poetry run python src/experiments/closure_runtime_contract.py
poetry run pytest tests/test_closure_runtime_contract.py -q
```

This default validation reads configuration, the cutoff-safe assignment,
protocol metadata, Git metadata, and opaque hashes/bytes for accepted legacy
manifests. It does not semantically decode those historical manifests, require
DVC payloads, read panel/target rows, fit a model, emit metrics, or open E0-U.
The separate pre-lock source-byte check is:

```bash
poetry run python src/experiments/closure_runtime_contract.py \
  --require-restored-development-sources
```

That mode hashes only the restored panel and expert-state development sources,
without decoding rows. It still does not touch the outcome Parquet or target
manifest. The full type check is additionally mandatory before E0-DL.

The next gates are to complete publication provenance for the guarded
common-origin artifact, implement the strict expert/ANFIS state, sequence,
temporal-fit, rollout, and lock adapters, and then generate E0-DL from a clean
commit. Historical direct ANFIS, sequence, trainer, and rollout commands remain
denied for Closure V1.
