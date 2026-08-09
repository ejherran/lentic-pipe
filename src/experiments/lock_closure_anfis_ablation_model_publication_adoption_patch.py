#!/usr/bin/env python
"""Check and publish the outcome-closed E0-MX model authority."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import (  # noqa: E402
    closure_anfis_ablation_model_publication_adoption_patch as patch,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def check_only() -> dict[str, Any]:
    """Run the schema-first, non-writing H-E0-MX preflight."""

    schema = patch.preflight_anfis_ablation_model_publication_adoption_patch_schema()
    prelock = (
        patch.collect_anfis_ablation_model_publication_adoption_patch_prelock_state(
            verify_remote=True
        )
    )
    h_patch = prelock.get("h_patch", {})
    companion = prelock.get("companion_contract", {})
    adopted = prelock.get("adopted_a0_bundle", {})
    return {
        "status": "ready_to_lock",
        "gate": patch.PATCH_GATE,
        "schema_preflight": schema,
        "repository": prelock.get("repository"),
        "component_count": h_patch.get("component_count"),
        "physical_input_count": companion.get("physical_input_count"),
        "historical_input_count": companion.get("historical_input_count"),
        "tracked_light_commit": patch.ADOPTED_LIGHT_COMMIT,
        "tracked_light_count": len(patch.HISTORICAL_A0_LIGHT_PATHS),
        "adopted_model_id": adopted.get("model_id"),
        "adopted_base_seed": adopted.get("base_seed"),
        "adopted_output_count": adopted.get(
            "output_count", adopted.get("final_count")
        ),
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
        patch.execute_and_publish_anfis_ablation_model_publication_adoption_patch_lock_bundle()
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


def check_effective(
    *, model_id: str, base_seed: int, audit_current_unpublished: bool
) -> dict[str, Any]:
    """Inspect one exact published audit/build authorization."""

    return (
        patch.load_effective_anfis_ablation_model_publication_adoption_patch_authority(
            model_id=model_id,
            base_seed=base_seed,
            audit_current_unpublished=audit_current_unpublished,
            verify_remote=True,
        )
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute-lock", action="store_true")
    mode.add_argument("--check-effective", action="store_true")
    parser.add_argument("--model-id", choices=("A0", "A1"))
    parser.add_argument("--base-seed", type=int)
    parser.add_argument("--audit-current-unpublished", action="store_true")
    args = parser.parse_args(argv)
    target_supplied = args.model_id is not None or args.base_seed is not None
    if args.check_effective:
        if args.model_id is None or args.base_seed is None:
            parser.error("--check-effective requires --model-id and --base-seed")
    elif target_supplied or args.audit_current_unpublished:
        parser.error(
            "target/audit arguments are only valid with --check-effective"
        )
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
                model_id=str(args.model_id),
                base_seed=int(args.base_seed),
                audit_current_unpublished=bool(args.audit_current_unpublished),
            )
    except patch.AnfisAblationModelPublicationAdoptionPatchError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(patch._canonical_json(payload).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
