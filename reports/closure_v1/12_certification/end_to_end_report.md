# Phase 4 final synthetic API end-to-end certification

- Executable commit (P-CERT): `3f58cfda567f6885085a360c08194322ee551aaf`
- Command: `.venv/bin/python` `-m` `pytest` `tests/test_api_predictions_alerts.py::test_api_exposes_current_state_predictions_and_alerts` `tests/test_api_counterfactual_simulation.py::test_api_runs_minimal_current_state_counterfactual` `tests/test_api_run_artifacts.py::test_api_lists_previews_and_summarizes_run_artifacts` `-q` `-p` `src.reporting.build_phase4_final_certification` `-p` `no:cacheprovider` `--junitxml=tmp/e2e-raw.xml`
- Tests/passed/failures/errors/skips: `3/3/0/0/0`
- Workflow status: `passed`
- Fixture scope: `synthetic_external_non_closure_outcome`
- Covered flows: prediction/alert, bounded current-state counterfactual, and run-artifact list/preview/summary.
- Closure outcomes, targets, restored Parquets, and private context were not opened.

This checks software behavior only; the counterfactual is not field-causal evidence.
