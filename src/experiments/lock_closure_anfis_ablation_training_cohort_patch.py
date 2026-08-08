#!/usr/bin/env python
"""Check and publish the outcome-closed E0-MU cohort correction authority."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import (  # noqa: E402
    closure_anfis_ablation_training_cohort_patch as patch,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def check_only() -> dict[str, Any]:
    schema = patch.preflight_anfis_ablation_training_cohort_patch_schema()
    prelock = patch.collect_anfis_ablation_training_cohort_patch_prelock_state(
        verify_remote=True
    )
    return {
        "status": "ready_to_lock",
        "gate": "E0-MU",
        "schema_preflight": schema,
        "repository": prelock["repository"],
        "component_count": prelock["h_patch"]["component_count"],
        "physical_input_count": prelock["companion_contract"][
            "physical_input_count"
        ],
        "historical_input_count": prelock["companion_contract"][
            "historical_input_count"
        ],
        "writes_performed": False,
        "verification_commands_run": False,
        "development_preflight_loader_run": False,
        "development_targets_through_2020_read_during_verification": False,
        "development_preprocessing_and_priors_reconstructed_during_verification": False,
        "trainer_entrypoint_run": False,
        "model_fit_or_optimization_run": False,
        "auditor_entrypoint_run": False,
        "calibration_2021_targets_read_during_verification": False,
        "holdout_or_post_2021_targets_read_during_verification": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "future_outcomes_accessed": False,
    }


def execute_lock() -> dict[str, Any]:
    lock, companion = (
        patch.execute_and_publish_anfis_ablation_training_cohort_lock_bundle()
    )
    return {
        "status": "locked_unpublished",
        "gate": "E0-MU",
        "lock": lock,
        "companion": companion,
        "development_preflight_loader_run": True,
        "development_targets_through_2020_read_during_verification": True,
        "development_preprocessing_and_priors_reconstructed_during_verification": True,
        "trainer_entrypoint_run": False,
        "model_fit_or_optimization_run": False,
        "auditor_entrypoint_run": False,
        "calibration_2021_targets_read_during_verification": False,
        "holdout_or_post_2021_targets_read_during_verification": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "future_outcomes_accessed": False,
    }


def check_effective(*, model_id: str, base_seed: int) -> dict[str, Any]:
    return patch.load_effective_anfis_ablation_training_cohort_authority(
        model_id=model_id,
        base_seed=base_seed,
        audit_current_unpublished=False,
        verify_remote=True,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute-lock", action="store_true")
    mode.add_argument("--check-effective", action="store_true")
    parser.add_argument("--model-id", choices=("A0", "A1"))
    parser.add_argument("--base-seed", type=int)
    args = parser.parse_args(argv)
    target_supplied = args.model_id is not None or args.base_seed is not None
    if args.check_effective:
        if args.model_id is None or args.base_seed is None:
            parser.error("--check-effective requires --model-id and --base-seed")
    elif target_supplied:
        parser.error("--model-id/--base-seed are only valid with --check-effective")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.check_only:
            payload = check_only()
        elif args.execute_lock:
            payload = execute_lock()
        else:
            payload = check_effective(
                model_id=str(args.model_id), base_seed=int(args.base_seed)
            )
    except patch.AnfisAblationTrainingCohortPatchError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(patch._canonical_json(payload).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
