# lentic-pipe

Reproducible system for simulation, alerting, and counterfactual planning of
algal proliferation and trophic state in lentic water bodies.

The project follows a frozen-data architecture with SHA-256 traceability,
leakage-safe temporal splits, baselines before complex models, expert
ANFIS/fuzzy state scoring, PIPE/GRU-D, controlled degradation, and DVC-backed
artifacts.

## Requirements

- Python `>=3.14,<3.15`
- Poetry as the only dependency manager
- DVC with GCS support to recover or publish heavy artifacts
- Authorized access to the private bucket if you need `dvc pull` or `dvc push`

Install Poetry if it is not available:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

`poetry.toml` keeps the virtual environment inside the repository:

```text
.venv/
```

That directory is not versioned.

## Installation

Core development install (does not include API or modeling extras):

```bash
poetry install --with dev
```

Development install for the complete public test suite:

```bash
poetry install --with dev,api,modeling
```

Full install for API, data, modeling, and DVC workflows:

```bash
poetry install --with dev,api,modeling,sources,data-versioning
```

Verify the environment:

```bash
.venv/bin/python --version
poetry run ty check
poetry run pytest
.venv/bin/dvc --version
```

Add dependencies with Poetry:

```bash
poetry add pandas
poetry add --group dev pytest
poetry add --group modeling scikit-learn
```

After dependency changes, update and version the lock file:

```bash
poetry lock
```

## Data And DVC

Raw data lives under `data/raw/` and must not be versioned as Git blobs. GitHub
should contain code, tests, configs, documentation, manifests, hashes, small
reports, and `.dvc` pointer files.

Heavy artifacts live in private DVC/GCS storage:

- complete raw sources
- canonical observations
- panels, targets, and splits
- large diagnostics
- fuzzy state and large operational score exports
- PIPE/GRU-D datasets
- binary models

The real GCS bucket must not be written into versioned files. Use placeholders
only, such as:

```text
gs://YOUR_PRIVATE_BUCKET/dvc
```

Use this entry point to configure, upload, download, and diagnose DVC data:

```bash
scripts/dvc_data_assistant.sh --help
```

## Recover Data On Another Machine

After cloning the repository on an authorized machine:

```bash
git clone <repo>
cd lentic-pipe
poetry install --with dev,api,modeling,sources,data-versioning
mkdir -p private
```

Copy the service-account JSON to a Git-ignored path, for example:

```text
private/YOUR_SERVICE_ACCOUNT.json
```

Then configure DVC and download the artifacts:

```bash
scripts/dvc_data_assistant.sh setup \
  --bucket YOUR_PRIVATE_BUCKET \
  --credentialpath private/YOUR_SERVICE_ACCOUNT.json

scripts/dvc_data_assistant.sh pull
```

After pulling data, regenerate all lightweight reproducibility artifacts:

```bash
scripts/reproduce_data_workspace.sh
scripts/dvc_data_assistant.sh doctor
```

The recovery assistant rebuilds source manifests, canonical observation
summaries, and the data freeze. It also fails if the derived-manifest path set
changes unexpectedly, so a missing regenerated file cannot silently disappear
from the freeze.

## Publish Or Update Data

When a machine creates or updates heavy artifacts:

```bash
scripts/prepare_commit_artifacts.sh
scripts/list_publication_candidates.sh
scripts/check_repo_publication_ready.sh
```

The pre-commit artifact assistant detects DVC-tracked data changes, asks before
adding unmanaged ignored data paths to DVC, runs `dvc add`, runs `dvc push`,
stages Git changes, validates DVC pointers, checks experiment manifest hashes,
flags stale data-freeze risk, and writes a timestamped upload preparation report
under ignored `tmp/`.

Commit only code, configs, docs, manifests, small reports, and `.dvc` pointer
files. Do not commit `.dvc/config.local`, raw data, model binaries, heavy
exports, or credential JSON files.

## Main Documentation

- `docs/DATA_SOURCES.md`
- `docs/DATA_LICENSES.md`
- `docs/DATA_ACCESS.md`
- `docs/DATA_VERSIONING.md`
- `docs/SITE_RESOLUTION.md`
- `docs/DVC_GCS_SETUP.md`
- `docs/PUBLICATION_CHECKLIST.md`
- `docs/DATA_FREEZE.md`
- `docs/PIPE_ROLLOUT_ITERATION_1.md`
- `docs/PIPE_ROLLOUT_ITERATION_2.md`
- `docs/PIPE_LIGHTWEIGHT_SYNTHESIS.md`
- `docs/ADAPTIVE_ANFIS_PROTOCOL.md`
- `docs/CONTROLLED_DEGRADATION_PROTOCOL.md`
- `docs/COUNTERFACTUAL_PLANNING_PROTOCOL.md`
- `docs/COUNTERFACTUAL_PLANNING_SYNTHESIS.md`
- `docs/closure_v1/ANALYSIS_PLAN.md`
- `docs/closure_v1/PROTOCOL_AMENDMENT_V1_1.md`
- `docs/closure_v1/E0_D_DEVELOPMENT_GUARD.md`
- `docs/closure_v1/E0_D_RUNTIME_CONTRACT.md`
- `docs/THESIS_EXPERIMENT_TRACEABILITY.md`
- `docs/API_PROTOCOL.md`
- `docs/API_DATASET_CONTRACT.md`
- `docs/API_LOCAL_USAGE.md`

## Current State

- The four raw sources are documented in `configs/sources.yaml`: LakeBeD-US-CSE,
  WQP, AquaMatch Chl-a, and EPA NLA.
- SHA-256 hashes and the data freeze are versioned under `data/catalog/` and
  `data/freeze/`.
- Heavy artifacts are declared in the immutable E0-P inventory
  `configs/dvc_artifacts.yaml` and, for post-lock Closure V1 additions, in
  anchored overlays such as
  `configs/closure_v1/dvc_artifacts_post_lock.yaml`.
- The thesis-wide `closure_v1` benchmark has not been evaluated. E0-P was
  published in `ead7d13`, its external protocol lock in `31230a2`, and the
  cutoff-safe E0-C assignment in `0c283af`. The immutable assignment contains
  441 WQP monitoring locations: 88 internal holdout locations and 353
  development locations, with 8,903 pre-cutoff eligible origins. E0-D's
  assignment/runtime guard and common-origin builder were published in
  `502c955`. A derived ANFIS/PIPE runtime-contract candidate has status
  `ready_to_lock`; it fixes the no-current autoregressive lineage,
  deterministic ANFIS sampling, five paired seeds, and the P0/P1 fit profile.
  The guarded common-origin artifact is now materialized and strictly
  validated: 29,196 horizon rows over 9,732 origins and 353 development
  locations. Commit `c0554bd` publishes its completion manifest and explicit
  DVC pointer, binds the frozen sources and implementation dependencies, and
  has a matching remotely pushed object. The current pre-fit source slice
  implements the strict expert/ANFIS, sequence, temporal-fit, rollout, and
  E0-DL lock adapters, and predeclares the 23 planned Closure Parquets without
  creating data or pointers. It separates the training-only ANFIS join and
  quality gate from full-development state materialization, fixes Torch to a
  single-thread CPU policy, and rejects reuse of completed or partial Closure
  bundles. This implementation must be published as the clean `H0` gate; the
  deterministic expert-state bundle and external lock remain separate gated
  publications. The later lock semantically audits only the outcome-free
  expert state, binds a credential-free canonical Git-origin identity, and
  requires two already-up-to-date targeted DVC pushes. Fitting is not
  authorized.
  Fit-generated heavy artifacts can be registered only after materialization
  and must be registered before E0-M. E0-U remains sealed, and no post-2021
  holdout outcome has been opened for Closure V1.
  Existing model results remain iteration-specific evidence.
  The primary closure surface excludes observed Chl-a and all of its lineage at
  every input lag, and the transfer claim is limited to held-out WQP monitoring
  locations within the frozen cohort.
- Historical files use the `PIPE/GRU-D` and `pipe_grud` labels. The current
  trainer implements a residual probabilistic GRU over engineered/imputed
  state vectors, without the explicit mask and temporal-decay mechanism of a
  canonical GRU-D. Final methodological claims must use that narrower
  description unless the implementation changes.
- Chapter IV evidence provenance is generated from
  `configs/thesis_evidence_matrix.yaml` into
  `reports/thesis/chapter_iv_evidence_matrix.md`; it must be consulted before
  combining results from different freezes or experimental iterations.
- Cross-source waterbody matching is handled as an auditable candidate layer via
  `configs/site_resolution.yaml` and `src/data/build_waterbody_crosswalk.py`;
  source-scoped site IDs remain authoritative until a reviewed crosswalk is
  promoted.
- The focused NLA-WQP review is documented in
  `reports/data/nla_wqp_crosswalk_review.md`; WQP is the panel backbone and NLA
  is treated as a validation, provenance, and enrichment layer.
- DVC is initialized; the real remote and credentials live only in
  `.dvc/config.local`.
- `scripts/dvc_data_assistant.sh` is the recommended workflow for configuring,
  uploading, downloading, and diagnosing DVC data.
- `scripts/reproduce_data_workspace.sh` is the recommended workflow for
  regenerating local reproducibility artifacts after `dvc pull`.
- `scripts/prepare_commit_artifacts.sh` is the recommended workflow for
  preparing Git staging and DVC upload before a manual commit.
- `src/experiments/rollout_pipe_grud.py` generates recursive PIPE/GRU-D state
  rollouts and alert summaries from the frozen promoted model.
- `src/experiments/evaluate_pipe_grud_rollouts.py` backtests recursive
  PIPE/GRU-D rollouts against observed future fuzzy states before treating
  alert behavior as thesis evidence.
- `docs/PIPE_ROLLOUT_ITERATION_1.md` records the first reproducible rollout
  iteration, including operational artifacts, historical backtest metrics, and
  the Iteration 2 direction.
- `docs/PIPE_ROLLOUT_ITERATION_2.md` defines the validation/test rollout alert
  calibration protocol, the Iteration 2B policy frontier, and the provisional
  downstream default: the balanced `closest_pr` policy. Conservative fixed
  thresholds and sensitive F2 thresholds remain documented comparison profiles.
- `docs/CONTROLLED_DEGRADATION_PROTOCOL.md` defines the controlled degradation
  scenario families, `configs/degradation_scenarios.yaml` provides the
  machine-readable scenario grid, and
  `src/experiments/evaluate_controlled_degradation.py` provides the first
  reproducible evaluator for precomputed rollout score surfaces. Use
  `--output-name` for follow-up runs that must not overwrite the smoke
  artifacts.
- `src/experiments/evaluate_mifal_controlled_degradation.py` recomputes
  MIFAL-ED/T2 after degrading observable panel evidence while keeping labels,
  validation calibrators, and thresholds fixed. The current MIFAL degradation
  evidence is under `reports/degradation/mifal_controlled_degradation_*` and
  identifies nutrient removal, Chl-a memory removal, and severe MCAR dropout as
  the main observable-evidence stressors.
- `docs/MIFAL_ED_T2_SYNTHESIS.md` closes MIFAL-ED/T2 as an interpretable
  comparator with a negative held-out `bloom_h` result against adaptive
  PIPE/GRU-D, while preserving its value for degradation diagnostics.
- `docs/COUNTERFACTUAL_PLANNING_PROTOCOL.md` opens the counterfactual planning
  block. `configs/counterfactual_planning.yaml` defines the initial adaptive
  PIPE-GRU-D planning surface, defensible proxy actions, constraints, costs,
  search stages, outputs, and the explicit guardrail that planning is simulated
  decision-support research rather than field causality or official
  environmental advice.
- `reports/planning/counterfactual_grid_smoke_validation_report.md` records a
  bounded validation smoke of the first state-proxy grid. The smoke confirms
  the runner/report/manifest path and currently ranks `no_action` above the
  tested proxy scenarios under the normal cost-weighted objective.
- `reports/planning/counterfactual_grid_validation_report.md` records the full
  validation run under the same declared grid and objective. The result remains
  a cautious negative benchmark: tested proxy scenarios reduce simulated risk
  but do not overcome the configured relative-cost penalty, so `no_action`
  remains top-ranked before any test-set evaluation.
- `reports/planning/counterfactual_grid_validation_crisis_report.md` and
  `reports/planning/counterfactual_grid_validation_budget_constrained_report.md`
  record validation-only sensitivity runs over declared planning modes. The
  crisis mode yields positive objective scenarios under a lower cost penalty;
  the budget-constrained mode keeps `no_action` top-ranked.
- `reports/planning/counterfactual_grid_test_report.md`,
  `reports/planning/counterfactual_grid_test_crisis_report.md`, and
  `reports/planning/counterfactual_grid_test_budget_constrained_report.md`
  record the locked held-out test evaluation. The validation pattern
  generalizes: crisis mode retains positive simulated planning scenarios while
  normal and budget-constrained modes keep `no_action` top-ranked.
- `docs/COUNTERFACTUAL_PLANNING_SYNTHESIS.md` closes counterfactual planning v0
  as a reproducible state-proxy benchmark. It states the conditional result:
  positive simulated planning utility appears only under the predeclared
  `crisis` mode, while `normal` and `budget_constrained` remain conservative
  no-action benchmarks.
- `docs/COUNTERFACTUAL_PLANNING_V1_PROTOCOL.md` opens counterfactual planning
  v1 as a validation-first raw-proxy, support-aware extension of the v0
  benchmark. `configs/counterfactual_planning_v1.yaml` declares the curated
  raw-proxy scenario family, and
  `src/experiments/evaluate_counterfactual_planning_v1.py` recomputes the
  expert fuzzy state after raw input perturbations while reporting historical
  support violations.
- `reports/planning/counterfactual_raw_proxy_v1_smoke_validation_report.md`
  records the first bounded validation smoke for the v1 raw-proxy surface. The
  runner completed and produced support-aware outputs; under the normal
  objective, `no_action` remains top-ranked and all completed non-baseline
  scenarios have negative net objective in the smoke subset.
- `reports/planning/counterfactual_raw_proxy_v1_validation_report.md` records
  the full validation run for the v1 normal objective. The full validation
  result matches the smoke direction: raw-proxy scenarios reduce simulated
  risk but do not overcome relative cost and support penalties, so `no_action`
  remains top-ranked before any v1 held-out test evaluation.
- `reports/planning/counterfactual_raw_proxy_v1_validation_crisis_report.md`
  records validation-only sensitivity under the permissive `crisis` planning
  mode. Unlike the v0 state-proxy grid, v1 remains negative even under crisis:
  all raw-proxy scenarios retain negative net objective after cost and support
  penalties, and `no_action` remains top-ranked.
- `reports/planning/counterfactual_raw_proxy_v1_test_report.md` and
  `reports/planning/counterfactual_raw_proxy_v1_test_crisis_report.md` record
  the locked held-out test evaluation for v1. Test confirms validation:
  `no_action` remains top-ranked under both `normal` and `crisis`.
- `docs/COUNTERFACTUAL_PLANNING_V1_SYNTHESIS.md` closes counterfactual
  planning v1 as a reproducible raw-proxy/support-aware benchmark. It states
  the final result: v1 is more interpretable and support-aware than v0, but it
  does not reproduce v0's positive `crisis` utility.
- `docs/NO_CURRENT_CHLA_EARLY_WARNING.md` defines the first formal
  no-current-Chl-a early-warning surface, including the sequence input mapping,
  target-only backtest guardrail, smoke commands, and full-run promotion
  criteria.
- `docs/PIPE_LIGHTWEIGHT_SYNTHESIS.md` closes the current lightweight PIPE
  comparison block across the Chl-a-aware, no-current all-source, and
  no-current WQP-focused surfaces, while explicitly separating it from
  adaptive ANFIS, Neural ODE, MIFAL, counterfactual planning, and the final
  thesis-wide evaluation.
- `docs/ADAPTIVE_ANFIS_PROTOCOL.md` audits the existing expert/refined fuzzy
  layer and defines the v0 protocol for adaptive `ANFIS-N`, `ANFIS-F`, and
  `ANFIS-T` before any adaptive training result is claimed.
- `docs/PIPE_NEURAL_ODE_PROTOCOL.md` documents the Neural ODE branch as a
  temporal PIPE variant over the same sequence schema used by PIPE/GRU-D,
  including one-step training, recursive rollout backtests, calibration, and
  2B policy-frontier evidence. The v1 refinement runner
  `src/experiments/train_pipe_neural_ode_v1.py` adds a history encoder and
  latent ODE for methodical comparison against the GRU-D history window; its
  current matched-origin rollout and 2B alert evidence make it the leading
  temporal candidate for `irc_alert`, with PIPE/GRU-D retained as the simpler
  benchmark and fallback.
  Recursive rollout evaluation is handled by
  `src/experiments/evaluate_pipe_neural_ode_rollouts.py`, which supports both
  v0 Markovian and v1 history-encoded Neural ODE artifacts.
- `docs/MIFAL_ED_T2_PROTOCOL.md` opens MIFAL-ED/T2 as a structurally separate
  interval type-2 eco-fuzzy comparator. The first public gate is input
  availability, implemented in `src/experiments/audit_mifal_inputs.py`; it
  should be run before any MIFAL calibration or comparison claim. The first
  observable adapter lives in `src/mifal/panel_adapter.py`, with an isolated
  smoke runner in `src/experiments/evaluate_mifal_observable.py`. Validation
  calibration is handled separately by
  `src/experiments/calibrate_mifal_observable_alerts.py`, which fits
  per-horizon calibrators and thresholds on validation only. Matched-surface
  diagnostics are handled by `src/experiments/evaluate_mifal_matched_surface.py`;
  these intersect calibrated MIFAL predictions, and optionally a reference
  backtest surface, before any comparison claim is made. Metric-level `bloom_h`
  comparison against PIPE is handled by
  `src/experiments/compare_mifal_pipe_bloom_metrics.py`; MIFAL does not emit the
  PIPE `irc_alert` target.
- `docs/API_PROTOCOL.md` defines the REST API direction. The public `src/api`
  tree now uses the full prototype architecture as its base: authentication,
  users, experiment collaboration, SQL persistence, Taskiq/Redis jobs,
  cancellation, metrics, and Alembic migrations. The existing scientific API
  work is preserved as a workflow layer for dataset validation, experiment-owned
  scientific dataset registration, planning, safe local execution, artifact
  previews, workspace catalog navigation, run-id prediction/alert views,
  current-state alerts, and minimal counterfactual recomputation.
  Async runs should prefer `config.experiment_dataset_id` so the worker can
  resolve a validated dataset owned by the same experiment. Registered
  job-backed adapters are reported by `/version`; the initial adapter interface
  executes `canonical_observations`, `monthly_panel`, `fuzzy_state`, PIPE-GRU-D
  preflight/sequence/adaptive-surface/inference modes, Neural ODE
  preflight/calibrated reference-profile inference/reference modes, MIFAL
  observable scoring/reference modes, and counterfactual-planning
  preflight/V1 scenario execution/reference modes. PIPE-GRU-D
  `infer_reference_profile` runs calibrated adaptive reference-profile rollouts
  with bloom calibrators and selected 2B policy thresholds; Neural ODE
  `infer_reference_profile` does the same with the reviewed history Neural ODE
  v1 branch. MIFAL `run_observable` writes observable bloom-risk scores and
  calibrated `bloom_h` alerts. Counterfactual planning `run_scenarios` uses a
  completed compatible temporal upstream run to evaluate V1 raw-proxy scenario
  diagnostics; these are not causal intervention claims.
  `GET /workspace/catalog` provides an authenticated metadata-only view of
  visible experiments, registered datasets, runs, and discoverable scientific
  output views so clients do not need to inspect internal workspace paths.
- A lightweight source ZIP does not include DVC-managed model checkpoints,
  calibrator directories, or row-level parquet exports. API tests and workflows
  that only validate, plan, canonicalize, build panels, score fuzzy state, or
  run preflight diagnostics can run from the source checkout after installing
  dependencies. Reference-profile inference for PIPE-GRU-D and Neural ODE, and
  calibrated MIFAL alert views, require restoring the referenced DVC artifacts;
  artifact-dependent tests skip with an explicit reason when those files are
  absent.
- `scripts/check_repo_publication_ready.sh` must pass before publishing to
  GitHub.
- `poetry run ty check` and `poetry run pytest` must pass before publishing
  code changes.
