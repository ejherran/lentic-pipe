# Phase 4 final public test certification

- Executable commit (P-CERT): `3f58cfda567f6885085a360c08194322ee551aaf`
- Suite: `closure_phase4_final_public`
- Locked selectors: `39`
- Locked collected node IDs: `944`
- Node-ID SHA-256: `255beb8438b402199251e435c4d450d9f4d5a9e30aac06216f5daf526327a296`
- Command: `.venv/bin/python` `-m` `pytest` `tests/test_api_counterfactual_simulation.py` `tests/test_api_dataset_validation.py` `tests/test_api_experiment_scientific_datasets.py` `tests/test_api_job_science_adapters.py` `tests/test_api_minimal_workflow.py` `tests/test_api_predictions_alerts.py` `tests/test_api_run_artifacts.py` `tests/test_api_run_executor.py` `tests/test_api_run_planner.py` `tests/test_api_run_scientific_outputs.py` `tests/test_api_scientific_workflow_adapters.py` `tests/test_api_system.py` `tests/test_api_workspace_catalog.py` `tests/test_audit_closure_p0_model_availability.py` `tests/test_audit_closure_p0_sequence_bundle.py` `tests/test_build_closure_e10_source_evidence.py` `tests/test_build_closure_synthesis.py` `tests/test_build_phase4_final_certification.py` `tests/test_build_thesis_evidence_matrix.py` `tests/test_closure_e0_u_activation_lock.py` `tests/test_closure_e0_u_authority.py` `tests/test_closure_e6_e9_unavailable.py` `tests/test_closure_phase3_context.py` `tests/test_closure_phase3_e1_e2_e3_e5_contracts.py` `tests/test_closure_phase3_e4_e7_contracts.py` `tests/test_closure_phase3_e8_locked_uncertainty.py` `tests/test_closure_phase3_input_overlay.py` `tests/test_closure_synthesis_contract.py` `tests/test_lock_closure_synthesis.py` `tests/test_lock_phase4_final_certification.py` `tests/test_phase4_final_certification_contract.py` `tests/test_prepare_commit_artifacts.py` `tests/test_validate_phase4_manuscript.py` `tests/test_build_closure_holdout.py::test_protocol_lock_requires_the_exact_selector_hash` `tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[assignment_created-holdout_assignment_created=false]` `tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[dirty_locked_repository-worktree_status='clean']` `tests/test_build_closure_holdout.py::test_cli_dry_run_does_not_read_panel_or_write_outputs` `tests/test_closure_final_calibration.py::test_lock_validation_rejects_authorization_and_boundary_drifts` `tests/test_closure_final_calibration.py::test_output_contract_is_exact_manifest_last_and_zero_overlap` `-ra` `-q` `-p` `src.reporting.build_phase4_final_certification` `-p` `no:cacheprovider` `--junitxml=tmp/public-tests-raw.xml`
- Passed/skipped/failures/errors: `902/42/0/0`
- Forbidden target, outcome, restored-Parquet, and private reads: `0`.
- General network access: `disabled`; PostgreSQL used an owned Unix socket.

## Exact justified skip ledger

- `tests/test_api_predictions_alerts.py::test_api_exposes_mifal_predictions_and_alerts` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_api_predictions_alerts.py::test_api_exposes_neural_ode_reference_predictions_and_alerts` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_api_predictions_alerts.py::test_api_exposes_pipe_grud_reference_predictions_and_alerts` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_api_scientific_workflow_adapters.py::test_counterfactual_planning_adapter_runs_v1_scenarios_from_upstream_temporal_run` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_api_scientific_workflow_adapters.py::test_neural_ode_preflight_adapter_writes_dataset_diagnostic` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_api_scientific_workflow_adapters.py::test_neural_ode_reference_profile_inference_adapter_writes_calibrated_rollouts` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_api_scientific_workflow_adapters.py::test_pipe_grud_adaptive_surface_adapter_writes_reference_ready_sequences` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_api_scientific_workflow_adapters.py::test_pipe_grud_expert_surface_inference_adapter_writes_diagnostic_rollouts` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_api_scientific_workflow_adapters.py::test_pipe_grud_reference_adapter_writes_manifest_and_report` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_api_scientific_workflow_adapters.py::test_pipe_grud_reference_profile_inference_adapter_writes_calibrated_rollouts` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_audit_rejects_any_preregistered_registry_entry` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_check_only_never_invokes_remote_or_dvc` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_companion_uses_generic_completed_manifest_dialect` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_denominator_authority_reconstructs_role_and_fit_counts` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_p0_evidence_chain_and_git_blobs_are_exact` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_p0_namespace_is_exact_and_records_all_absences` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_public_policy_and_five_published_slots_pass_read_only_audit` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_published_loader_is_the_only_effective_authority` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_published_loader_rechecks_all_post_registry_absence_gates[E0-M outputs already exist]` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_published_loader_rechecks_all_post_registry_absence_gates[Outcome access log must remain absent]` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_published_loader_rechecks_all_post_registry_absence_gates[P1 materialization predates the P0 registry]` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_published_loader_rechecks_all_post_registry_absence_gates[Registry bundle namespace is not pristine]` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_published_loader_rejects_live_remote_divergence` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_registry_bundle_validator_accepts_exact_reconstruction` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_registry_bundle_validator_reconstructs_every_authoritative_section` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_model_availability.py::test_registry_payload_is_non_self_authorizing_and_has_no_placeholder_values` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_failure_is_read_only[early]` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_failure_is_read_only[late]` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_pass_is_read_only` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_cli_is_repeatable_and_read_only` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_physical_schema_matches_closed_fields` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_build_closure_holdout.py::test_cli_dry_run_does_not_read_panel_or_write_outputs` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[assignment_created-holdout_assignment_created=false]` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[dirty_locked_repository-worktree_status='clean']` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_build_closure_holdout.py::test_protocol_lock_requires_the_exact_selector_hash` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_build_closure_synthesis.py::test_check_only_before_p_syn_is_non_writing` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_closure_e0_u_authority.py::test_runner_and_authority_share_exact_capability_and_commit_contracts` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_closure_final_calibration.py::test_lock_validation_rejects_authorization_and_boundary_drifts` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_closure_final_calibration.py::test_output_contract_is_exact_manifest_last_and_zero_overlap` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_closure_phase3_context.py::test_real_b2_input_only_scoring_accepts_arrow_backed_origin_values` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_closure_phase3_context.py::test_real_input_only_registries_are_exact` — `final_certification_sandbox_or_state_incompatible`.
- `tests/test_closure_phase3_context.py::test_real_r10_eligibility_token_reaches_temporal_slots` — `final_certification_sandbox_or_state_incompatible`.

This is software certification evidence. It does not rerun the sealed scientific experiments and does not establish scientific efficacy.
