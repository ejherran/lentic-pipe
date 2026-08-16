# Closure V1 public test evidence

- Repository commit (H): `9e66478d7c071067a750e7dd9a6a318fa93a2c88`
- Suite kind: `closure_phase3_public`
- Positive selector count: `48`
- Positive selector SHA-256: `ff515f77641ceeafbef4d38f44acd531f16fdcbe0b5fbe3c5a216fd361b82cd9`
- Collected node-id SHA-256: `a7892dc9ef8ad163867e108c60860a154ff7b0693364a693f93d1a0614eb2ec6`
- Exact suite command: `poetry` `run` `pytest` `tests/test_audit_closure_p0_model_availability.py` `tests/test_audit_closure_p0_sequence_bundle.py` `tests/test_build_closure_e10_source_evidence.py` `tests/test_closure_e0_u_activation_lock.py` `tests/test_closure_e0_u_authority.py` `tests/test_closure_e6_e9_unavailable.py` `tests/test_closure_phase3_context.py` `tests/test_closure_phase3_e1_e2_e3_e5_contracts.py` `tests/test_closure_phase3_e4_e7_contracts.py` `tests/test_closure_phase3_e8_locked_uncertainty.py` `tests/test_closure_phase3_input_overlay.py` `tests/test_api_counterfactual_simulation.py` `tests/test_api_dataset_validation.py` `tests/test_api_experiment_scientific_datasets.py` `tests/test_api_job_science_adapters.py` `tests/test_api_minimal_workflow.py` `tests/test_api_predictions_alerts.py` `tests/test_api_run_artifacts.py` `tests/test_api_run_executor.py` `tests/test_api_run_planner.py` `tests/test_api_run_scientific_outputs.py` `tests/test_api_scientific_workflow_adapters.py` `tests/test_api_system.py` `tests/test_api_workspace_catalog.py` `tests/test_prepare_commit_artifacts.py::test_closure_e0_u_precommit_compares_configured_origin_not_live_evidence_url` `tests/test_prepare_commit_artifacts.py::test_closure_e0_u_activation_is_an_exact_authoritative_manifest_without_outputs` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_selector_is_exact13_unstaged_and_parent_scoped` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_selector_is_exact_unstaged_and_base_scoped` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_invocation_forbids_dvc_mutation` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_staged_transaction_binds_exact_modes_and_blobs` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_staged_transaction_binds_patch_and_final_tree` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_main_bypasses_historical_e0_m_selectors` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_main_precedes_full_h_and_historical_selectors` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_transaction_only_stages_exact40_and_runs_generic_checks` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_transaction_end_to_end_synthetic` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_post_add_failure_restores_exact13_unstaged` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_full_h_post_add_failure_restores_exact40_unstaged` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_rollback_failure_reports_primary_and_rollback_errors` `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_rollback_preserves_concurrent_foreign_staged_path` `tests/test_build_closure_holdout.py::test_protocol_lock_requires_the_exact_selector_hash` `tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[assignment_created-holdout_assignment_created=false]` `tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[dirty_locked_repository-worktree_status='clean']` `tests/test_build_closure_holdout.py::test_cli_dry_run_does_not_read_panel_or_write_outputs` `tests/test_closure_final_calibration.py::test_lock_validation_rejects_authorization_and_boundary_drifts` `tests/test_closure_final_calibration.py::test_output_contract_is_exact_manifest_last_and_zero_overlap` `tests/test_closure_anfis_ablation_dvc_registration_patch.py::test_registration_helper_cli_and_lazy_authority_loader_are_exact` `tests/test_closure_anfis_ablation_model_publication_adoption_patch.py::test_mz_registration_transaction_restores_owned_partial_metadata` `tests/test_closure_development_runtime_patch.py::test_full_history_detects_modify_restore_hidden_behind_merge` `-ra` `-p` `src.experiments.build_closure_e10_source_evidence` `-p` `no:cacheprovider` `--junitxml=tmp/closure_v1_e10_source_evidence_outputs/public_tests_raw.xml`
- Exit status: `0`
- Tests: `344`
- Passed: `335`
- Failures: `0`
- Errors: `0`
- Skips: `9`
- Critical skips: `0`
- Pre-E0-U target-dependent skips: `6` collected cases across `5` sealed test bases.
- User-prohibited Git-commit fixture skips: `3` collected cases from an exact sealed registry.
- Former `TEST_DATABASE_URL` HTTP skip: resolved with an explicitly configured PostgreSQL test database.
- Repository-wide pytest discovery: not run; the exact positive Phase 3/API inventory above is the sealed claim.
- Target/outcome guard: enabled via OS filesystem denial plus Python audit hook; no Closure target or outcome path opened.
- Private context guard: enabled; `private/FULL.md` was not opened.
- Raw JUnit SHA-256: `e175b5f769c2dd797bc4a84c3bfe2603e5963a7ea610b07eea2eb16e92043656`
- H-bound JUnit SHA-256: `729cfc089cdac6d05475c6165ef52c54fa50c0607eb9948f86b382391e739bd9`

## Skip ledger

- `tests.test_build_closure_holdout::test_protocol_lock_requires_the_exact_selector_hash` — Closure E10 pre-E0-U public suite excludes this repository-target-dependent historical protocol test; its target-bearing audit is not authorized before the one-shot outcome open (`pre_e0u_repository_target_test_excluded`; justified).
- `tests.test_build_closure_holdout::test_protocol_lock_requires_pre_assignment_clean_state[assignment_created-holdout_assignment_created=false]` — Closure E10 pre-E0-U public suite excludes this repository-target-dependent historical protocol test; its target-bearing audit is not authorized before the one-shot outcome open (`pre_e0u_repository_target_test_excluded`; justified).
- `tests.test_build_closure_holdout::test_protocol_lock_requires_pre_assignment_clean_state[dirty_locked_repository-worktree_status='clean']` — Closure E10 pre-E0-U public suite excludes this repository-target-dependent historical protocol test; its target-bearing audit is not authorized before the one-shot outcome open (`pre_e0u_repository_target_test_excluded`; justified).
- `tests.test_build_closure_holdout::test_cli_dry_run_does_not_read_panel_or_write_outputs` — Closure E10 pre-E0-U public suite excludes this repository-target-dependent historical protocol test; its target-bearing audit is not authorized before the one-shot outcome open (`pre_e0u_repository_target_test_excluded`; justified).
- `tests.test_closure_final_calibration::test_lock_validation_rejects_authorization_and_boundary_drifts` — Closure E10 pre-E0-U public suite excludes this repository-target-dependent historical protocol test; its target-bearing audit is not authorized before the one-shot outcome open (`pre_e0u_repository_target_test_excluded`; justified).
- `tests.test_closure_final_calibration::test_output_contract_is_exact_manifest_last_and_zero_overlap` — Closure E10 pre-E0-U public suite excludes this repository-target-dependent historical protocol test; its target-bearing audit is not authorized before the one-shot outcome open (`pre_e0u_repository_target_test_excluded`; justified).
- `tests.test_closure_anfis_ablation_dvc_registration_patch::test_registration_helper_cli_and_lazy_authority_loader_are_exact` — user_prohibited_git_commit_fixture (`user_prohibited_git_commit_fixture`; justified).
- `tests.test_closure_anfis_ablation_model_publication_adoption_patch::test_mz_registration_transaction_restores_owned_partial_metadata` — user_prohibited_git_commit_fixture (`user_prohibited_git_commit_fixture`; justified).
- `tests.test_closure_development_runtime_patch::test_full_history_detects_modify_restore_hidden_behind_merge` — user_prohibited_git_commit_fixture (`user_prohibited_git_commit_fixture`; justified).

## Positive suite selector registry

- `tests/test_audit_closure_p0_model_availability.py`
- `tests/test_audit_closure_p0_sequence_bundle.py`
- `tests/test_build_closure_e10_source_evidence.py`
- `tests/test_closure_e0_u_activation_lock.py`
- `tests/test_closure_e0_u_authority.py`
- `tests/test_closure_e6_e9_unavailable.py`
- `tests/test_closure_phase3_context.py`
- `tests/test_closure_phase3_e1_e2_e3_e5_contracts.py`
- `tests/test_closure_phase3_e4_e7_contracts.py`
- `tests/test_closure_phase3_e8_locked_uncertainty.py`
- `tests/test_closure_phase3_input_overlay.py`
- `tests/test_api_counterfactual_simulation.py`
- `tests/test_api_dataset_validation.py`
- `tests/test_api_experiment_scientific_datasets.py`
- `tests/test_api_job_science_adapters.py`
- `tests/test_api_minimal_workflow.py`
- `tests/test_api_predictions_alerts.py`
- `tests/test_api_run_artifacts.py`
- `tests/test_api_run_executor.py`
- `tests/test_api_run_planner.py`
- `tests/test_api_run_scientific_outputs.py`
- `tests/test_api_scientific_workflow_adapters.py`
- `tests/test_api_system.py`
- `tests/test_api_workspace_catalog.py`
- `tests/test_prepare_commit_artifacts.py::test_closure_e0_u_precommit_compares_configured_origin_not_live_evidence_url`
- `tests/test_prepare_commit_artifacts.py::test_closure_e0_u_activation_is_an_exact_authoritative_manifest_without_outputs`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_selector_is_exact13_unstaged_and_parent_scoped`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_selector_is_exact_unstaged_and_base_scoped`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_invocation_forbids_dvc_mutation`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_staged_transaction_binds_exact_modes_and_blobs`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_staged_transaction_binds_patch_and_final_tree`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_main_bypasses_historical_e0_m_selectors`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_main_precedes_full_h_and_historical_selectors`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_transaction_only_stages_exact40_and_runs_generic_checks`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_transaction_end_to_end_synthetic`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_amend_post_add_failure_restores_exact13_unstaged`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_full_h_post_add_failure_restores_exact40_unstaged`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_rollback_failure_reports_primary_and_rollback_errors`
- `tests/test_prepare_commit_artifacts.py::test_closure_phase3_h_rollback_preserves_concurrent_foreign_staged_path`
- `tests/test_build_closure_holdout.py::test_protocol_lock_requires_the_exact_selector_hash`
- `tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[assignment_created-holdout_assignment_created=false]`
- `tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[dirty_locked_repository-worktree_status='clean']`
- `tests/test_build_closure_holdout.py::test_cli_dry_run_does_not_read_panel_or_write_outputs`
- `tests/test_closure_final_calibration.py::test_lock_validation_rejects_authorization_and_boundary_drifts`
- `tests/test_closure_final_calibration.py::test_output_contract_is_exact_manifest_last_and_zero_overlap`
- `tests/test_closure_anfis_ablation_dvc_registration_patch.py::test_registration_helper_cli_and_lazy_authority_loader_are_exact`
- `tests/test_closure_anfis_ablation_model_publication_adoption_patch.py::test_mz_registration_transaction_restores_owned_partial_metadata`
- `tests/test_closure_development_runtime_patch.py::test_full_history_detects_modify_restore_hidden_behind_merge`

## Sealed pre-E0-U exclusion registry

- `tests/test_build_closure_holdout.py::test_protocol_lock_requires_the_exact_selector_hash`
- `tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[assignment_created-holdout_assignment_created=false]`
- `tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[dirty_locked_repository-worktree_status='clean']`
- `tests/test_build_closure_holdout.py::test_cli_dry_run_does_not_read_panel_or_write_outputs`
- `tests/test_closure_final_calibration.py::test_lock_validation_rejects_authorization_and_boundary_drifts`
- `tests/test_closure_final_calibration.py::test_output_contract_is_exact_manifest_last_and_zero_overlap`

## User-prohibited Git-commit fixture registry

- `tests/test_closure_anfis_ablation_dvc_registration_patch.py::test_registration_helper_cli_and_lazy_authority_loader_are_exact`
- `tests/test_closure_anfis_ablation_model_publication_adoption_patch.py::test_mz_registration_transaction_restores_owned_partial_metadata`
- `tests/test_closure_development_runtime_patch.py::test_full_history_detects_modify_restore_hidden_behind_merge`

This report is source evidence. The sealed E10 component copies its content into the final transactional namespace without launching tests.
