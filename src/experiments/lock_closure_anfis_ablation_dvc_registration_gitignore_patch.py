#!/usr/bin/env python
"""Check and publish the outcome-closed E0-MZC Git-ignore authority."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import (  # noqa: E402
    closure_anfis_ablation_dvc_registration_gitignore_patch as patch,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _count(value: Any, name: str) -> int:
    """Read one required exact integer summary without accepting booleans."""

    if isinstance(value, Mapping) and type(value.get(name)) is int:
        return int(value[name])
    raise patch.AnfisAblationDvcRegistrationGitignorePatchError(
        f"E0-MZC check-only summary is missing exact integer: {name}"
    )


def _missing_pointer_validation(value: Any) -> dict[str, Any]:
    """Require exact discovery as a set and canonical interleaved execution."""

    expected = {
        "count": patch.FAMILY_POINTER_COUNT,
        "unique_count": patch.FAMILY_POINTER_COUNT,
        "set_exact": True,
        "discovery_order": "lexical_path",
        "canonical_execution_order": "alternating_a0_a1_within_seed",
    }
    if not isinstance(value, Mapping) or not patch._exact_equal(dict(value), expected):
        raise patch.AnfisAblationDvcRegistrationGitignorePatchError(
            "E0-MZC missing-pointer validation contract drifted"
        )
    return expected


def _in_progress_namespace_validation(value: Any) -> dict[str, Any]:
    """Require the guarded exact-prefix policy preserved from E0-MZB."""

    expected = {
        "payload_count": patch.FAMILY_POINTER_COUNT,
        "public_pointer_counts": [0, patch.FAMILY_POINTER_COUNT],
        "transaction_pointer_counts": list(range(patch.FAMILY_POINTER_COUNT + 1)),
        "tree_policy": "exact_ten_payloads_plus_canonical_pointer_prefix",
        "pointer_prefix_order": "alternating_a0_a1_within_seed",
        "transaction_guard_required": True,
        "transaction_pointer_ownership_required": True,
        "nonprefix_entries_rejected": True,
    }
    if not isinstance(value, Mapping) or not patch._exact_equal(dict(value), expected):
        raise patch.AnfisAblationDvcRegistrationGitignorePatchError(
            "E0-MZC in-progress namespace validation contract drifted"
        )
    return expected


def _gitignore_correction(value: Any) -> dict[str, Any]:
    """Require the exact R-MZB incident and adopted no-touch postimage."""

    expected = patch._gitignore_correction(PROJECT_ROOT)
    if not isinstance(value, Mapping) or not patch._exact_equal(dict(value), expected):
        raise patch.AnfisAblationDvcRegistrationGitignorePatchError(
            "E0-MZC Git-ignore incident/correction contract drifted"
        )
    return expected


def check_only() -> dict[str, Any]:
    """Run the schema-first, non-writing H-E0-MZC preflight."""

    schema = patch.preflight_anfis_ablation_dvc_registration_gitignore_patch_schema()
    prelock = patch.collect_anfis_ablation_dvc_registration_gitignore_patch_prelock_state(
        verify_remote=True
    )
    h_patch = prelock.get("h_patch", {})
    companion = prelock.get("companion_contract", {})
    family = prelock.get("completed_family", {})
    inventory = prelock.get("artifact_inventory", {})
    registration = prelock.get("registration_plan", {})
    namespace = prelock.get("prelock", {})
    correction = _gitignore_correction(prelock.get("gitignore_correction"))
    missing_pointer_validation = _missing_pointer_validation(
        registration.get("missing_pointer_validation")
        if isinstance(registration, Mapping)
        else None
    )
    in_progress_namespace_validation = _in_progress_namespace_validation(
        registration.get("in_progress_namespace_validation")
        if isinstance(registration, Mapping)
        else None
    )
    counts = {
        "component_count": _count(h_patch, "component_count"),
        "physical_input_count": _count(companion, "physical_input_count"),
        "historical_input_count": _count(companion, "historical_input_count"),
        "completed_slot_count": _count(family, "slot_count"),
        "family_final_count": _count(family, "final_count"),
        "lightweight_final_count": _count(family, "light_final_count"),
        "tracked_light_count": _count(family, "tracked_light_count"),
        "untracked_light_count": _count(family, "untracked_light_count"),
        "heavy_final_count": _count(family, "heavy_final_count"),
        "registration_artifact_count": _count(
            inventory, "registration_artifact_count"
        ),
        "general_artifact_count": _count(inventory, "general_artifact_count"),
        "registration_git_path_count": _count(
            registration.get("registration_git_scope", {}), "path_count"
        ),
        "prediction_pointer_count": _count(
            namespace, "selection_pointer_present_count"
        ),
    }
    expected_counts = {
        "component_count": len(patch.PATCH_PATHS),
        "physical_input_count": patch.EXPECTED_COMPANION_INPUT_COUNT,
        "historical_input_count": patch.EXPECTED_HISTORICAL_INPUT_COUNT,
        "completed_slot_count": patch.FAMILY_FINAL_COUNT
        // len(patch.SLOT_ROLE_ORDER),
        "family_final_count": patch.FAMILY_FINAL_COUNT,
        "lightweight_final_count": patch.FAMILY_LIGHT_COUNT,
        "tracked_light_count": patch.FAMILY_TRACKED_LIGHT_COUNT,
        "untracked_light_count": patch.FAMILY_UNTRACKED_LIGHT_COUNT,
        "heavy_final_count": patch.FAMILY_HEAVY_COUNT,
        "registration_artifact_count": patch.REGISTRATION_ARTIFACT_COUNT,
        "general_artifact_count": patch.GENERAL_ARTIFACT_COUNT,
        "registration_git_path_count": patch.EXPECTED_REGISTRATION_GIT_PATH_COUNT,
        "prediction_pointer_count": 0,
    }
    if counts != expected_counts:
        raise patch.AnfisAblationDvcRegistrationGitignorePatchError(
            f"E0-MZC check-only counts drifted: {counts}"
        )
    return {
        "status": "ready_to_lock",
        "gate": patch.PATCH_GATE,
        "schema_preflight": schema,
        "repository": prelock.get("repository"),
        "base_p_mzb_commit": patch.P_MZB_COMMIT,
        "missing_pointer_validation": missing_pointer_validation,
        "in_progress_namespace_validation": in_progress_namespace_validation,
        "gitignore_correction": correction,
        **counts,
        "writes_performed": False,
        "verification_commands_run": False,
        "trainer_entrypoint_run": False,
        "model_fit_or_optimization_run": False,
        "auditor_entrypoint_run": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "calibration_targets_read": False,
        "future_outcomes_accessed": False,
    }


def execute_lock() -> dict[str, Any]:
    """Run trusted verification once and publish only lock plus companion."""

    lock, companion = (
        patch.publish_anfis_ablation_dvc_registration_gitignore_patch_lock_bundle()
    )
    return {
        "status": "locked_unpublished",
        "gate": patch.PATCH_GATE,
        "lock": lock,
        "companion": companion,
        "trainer_entrypoint_run": False,
        "model_fit_or_optimization_run": False,
        "auditor_entrypoint_run": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "calibration_targets_read": False,
        "future_outcomes_accessed": False,
    }


def check_effective() -> dict[str, Any]:
    """Inspect the exact published Git-ignore-patch authority."""

    return patch.load_effective_anfis_ablation_dvc_registration_gitignore_patch_authority(
        verify_remote=True
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute-lock", action="store_true")
    mode.add_argument("--check-effective", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.check_only:
            payload = check_only()
        elif args.execute_lock:
            payload = execute_lock()
        else:
            payload = check_effective()
    except patch.AnfisAblationDvcRegistrationGitignorePatchError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(patch._canonical_json(payload).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
