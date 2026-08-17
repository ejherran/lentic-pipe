# Closure V1 synthetic API end-to-end evidence

- Repository commit (H): `b768c5b1251bde50b01f0c066be07fb931924537`
- Exact suite command: `poetry` `run` `pytest` `tests/test_api_predictions_alerts.py::test_api_exposes_current_state_predictions_and_alerts` `tests/test_api_counterfactual_simulation.py::test_api_runs_minimal_current_state_counterfactual` `tests/test_api_run_artifacts.py::test_api_lists_previews_and_summarizes_run_artifacts` `-q` `-p` `src.experiments.build_closure_e10_source_evidence` `-p` `no:cacheprovider` `--junitxml=tmp/closure_v1_e10_source_evidence_outputs/e2e_raw.xml`
- Exit status: `0`
- Tests: `3`
- Failures/errors/skips: `0/0/0`
- Workflow status: `passed`
- Fixture: `synthetic_external_non_closure_outcome`.
- Source identity: `external`; no WQP holdout membership.
- Closure targets, future outcomes, outcome access log, and `private/FULL.md`: not opened.

## Covered flow

1. Register a synthetic external dataset and execute deterministic fuzzy scoring.
2. Query the resulting prediction and alert surfaces.
3. Execute a bounded current-state counterfactual simulation.
4. List, preview, and summarize persisted run artifacts.

The simulation is a software workflow check, not field-causal evidence.
