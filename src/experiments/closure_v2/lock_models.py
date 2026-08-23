#!/usr/bin/env python
"""Freeze Closure V2 models and calibration before any evaluation outcomes are opened."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pandas as pd
import torch

from src.experiments.closure_contract import load_json_mapping, load_yaml_mapping, validate_json_schema
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT, audit_repository
from src.experiments.closure_v2.build_eligibility import EXPECTED_SEEDS
from src.experiments.closure_v2.calibrate_temporal import (
    AVAILABILITY_PATH,
    CALIBRATION_CONFIG,
    CONFORMAL_PATH,
    MANIFEST_PATH as CALIBRATION_MANIFEST,
    METRICS_PATH,
    SPECS_PATH,
    THRESHOLDS_PATH,
)
from src.experiments.closure_v2.hashing import canonical_json_bytes, file_record, sha256_file
from src.experiments.closure_v2.summarize_temporal import MODELS_POINTER, validate_models_pointer
from src.experiments.closure_v2.train_temporal import (
    DEVELOPMENT_LOCK,
    FAMILY_MANIFEST,
    MODEL_IDS,
    TemporalTrainingError,
    _exclusive_bundle,
    _require_regular,
    _slot_paths,
    _verify_record,
    _virtual_record,
)


MODEL_LOCK_SCHEMA = Path("configs/closure_v2/model_lock.schema.json")
MODEL_LOCK_PATH = Path("reports/closure_v2/00_protocol/model_lock.json")
MODEL_LOCK_MANIFEST_PATH = Path("reports/closure_v2/00_protocol/model_lock_manifest.json")
ANALYSIS_PLAN = Path("configs/closure_v2/analysis_plan.yaml")
COHORT_CONFIG = Path("configs/closure_v2/evaluation_cohorts.yaml")
BENCHMARK_CONFIG = Path("configs/closure_v2/model_benchmark.yaml")
SHARED_KEYS_POINTER = Path("data/closure_v2/development/shared_fit_keys.parquet.dvc")
MODEL_LOCK_TAG = "closure-v2-model-lock"
FAMILY_COMMIT = "1bf9b553dd1234b309fa6172a92d536d143499dc"


class ModelLockError(TemporalTrainingError):
    """Raised when model-lock construction or activation violates the protocol."""


def _git(*args: str, root: Path = PROJECT_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _record_matches(record: Mapping[str, Any], *, root: Path) -> None:
    _verify_record(record, root=root)


def validate_lock_inputs(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    head = _git("rev-parse", "HEAD", root=root)
    remote = _git("rev-parse", "origin/closure-v2", root=root)
    if head != FAMILY_COMMIT or remote != head:
        raise ModelLockError("Model lock requires the published temporal-family commit")
    family = load_json_mapping(_require_regular(root, FAMILY_MANIFEST))
    calibration = load_json_mapping(_require_regular(root, CALIBRATION_MANIFEST))
    if family.get("status") != "completed" or family.get("slot_count") != 10:
        raise ModelLockError("Temporal family authority is incomplete")
    if (
        calibration.get("status") != "completed"
        or calibration.get("group_count") != 30
        or calibration.get("evaluation_paths_opened") is not False
        or calibration.get("post_2021_outcomes_opened") is not False
        or calibration.get("holdout_rows_materialized") != 0
    ):
        raise ModelLockError("Calibration authority is incomplete or crossed evaluation")
    _record_matches(cast(Mapping[str, Any], calibration["script"]), root=root)
    for record in cast(Sequence[Mapping[str, Any]], calibration["outputs"]):
        _record_matches(record, root=root)
    validate_models_pointer(root=root)
    for path in (
        SPECS_PATH,
        METRICS_PATH,
        THRESHOLDS_PATH,
        CONFORMAL_PATH,
        AVAILABILITY_PATH,
        ANALYSIS_PLAN,
        COHORT_CONFIG,
        BENCHMARK_CONFIG,
        DEVELOPMENT_LOCK,
        SHARED_KEYS_POINTER,
    ):
        _require_regular(root, path)
    v1 = audit_repository(root)
    if v1["protected_v1_changes"]:
        raise ModelLockError(f"Closure V1 drift detected: {v1['protected_v1_changes']}")
    return {
        "status": "ready_to_lock",
        "authority_head": head,
        "remote": remote,
        "evaluation_authorized": False,
        "post_2021_outcomes_authorized": False,
    }


def _model_records(*, root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for model_id in MODEL_IDS:
        for seed in EXPECTED_SEEDS:
            paths = _slot_paths(model_id, seed)
            manifest_path = _require_regular(root, paths["manifest"])
            manifest = load_json_mapping(manifest_path)
            payload = torch.load(
                _require_regular(root, paths["model"]),
                map_location="cpu",
                weights_only=False,
            )
            if (
                not isinstance(payload, Mapping)
                or payload.get("model_id") != model_id
                or payload.get("base_seed") != seed
                or manifest.get("status") != "completed"
                or manifest.get("selected_profile") != payload.get("profile")
            ):
                raise ModelLockError(f"Model/manifest identity drifted: {model_id}/{seed}")
            output_records = {
                str(record["path"]): record
                for record in cast(Sequence[Mapping[str, Any]], manifest["outputs"])
            }
            for name in ("model", "checkpoint"):
                _record_matches(output_records[paths[name].as_posix()], root=root)
            records.append(
                {
                    "model_id": model_id,
                    "base_seed": seed,
                    "availability": "available",
                    "profile": payload["profile"],
                    "best_epoch": payload["best_epoch"],
                    "best_probabilistic_validation_loss": payload[
                        "best_probabilistic_validation_loss"
                    ],
                    "architecture": payload["architecture"],
                    "output_blend_weights": payload["output_blend_weights"],
                    "model": file_record(
                        root / paths["model"], root=root, role="locked_temporal_model"
                    ),
                    "checkpoint": file_record(
                        root / paths["checkpoint"], root=root, role="locked_raw_best_checkpoint"
                    ),
                    "slot_manifest": file_record(
                        manifest_path, root=root, role="locked_slot_manifest"
                    ),
                }
            )
    if len(records) != 10:
        raise ModelLockError("Locked model cardinality drifted")
    return records


def build_lock_payload(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_lock_inputs(root)
    models = _model_records(root=root)
    development = load_json_mapping(root / DEVELOPMENT_LOCK)
    specs = load_json_mapping(root / SPECS_PATH)
    thresholds = pd.read_csv(root / THRESHOLDS_PATH).to_dict(orient="records")
    conformal = pd.read_csv(root / CONFORMAL_PATH).to_dict(orient="records")
    availability = pd.read_csv(root / AVAILABILITY_PATH).to_dict(orient="records")
    plan = load_yaml_mapping(root / ANALYSIS_PLAN)
    cohorts = load_yaml_mapping(root / COHORT_CONFIG)
    benchmark = load_yaml_mapping(root / BENCHMARK_CONFIG)
    shared_fit_digests = [
        record
        for record in cast(Sequence[Mapping[str, Any]], development["shared_key_digests"])
        if record.get("usage_role") == "fit"
    ]
    if (
        len(shared_fit_digests) != 5
        or {record.get("rows") for record in shared_fit_digests} != {8925}
        or {record.get("identity_sha256") for record in shared_fit_digests}
        != {"5ac41d4ef2c04115ff1178e03b386e98e9496513cfdd441f24d75b19b194a474"}
    ):
        raise ModelLockError("Shared-fit digest authority drifted")
    if len(cast(Sequence[Any], specs.get("groups", ()))) != 30 or len(thresholds) != 30 or len(conformal) != 810:
        raise ModelLockError("Calibration lock cardinality drifted")
    output_contract = {
        "prediction_table": "data/closure_v2/predictions_long.parquet",
        "prediction_pointer": "data/closure_v2/predictions_long.parquet.dvc",
        "required_identity_columns": [
            "evaluation_cohort",
            "model_id",
            "base_seed",
            "source_id",
            "site_id",
            "origin_year_month",
            "target_year_month",
            "horizon_months",
        ],
        "required_status_columns": [
            "intent_to_predict",
            "prediction_status",
            "failure_reason",
            "target_available",
            "metric_evaluable",
            "shared_success",
        ],
        "primary_endpoint": {"id": "bloom_h", "threshold_ug_l": 30},
        "sensitivity_thresholds_ug_l": [25, 30, 33, 50],
        "family_prediction": "mean_probability_over_registered_available_seeds",
        "seed_pseudoreplication": "forbidden",
        "layer_pooling": "forbidden",
        "estimand_pooling": "forbidden",
    }
    sealed_commands = [
        ".venv/bin/python -m src.experiments.closure_v2.build_evaluation_inputs --execute",
        ".venv/bin/python -m src.experiments.closure_v2.activate_evaluation --execute",
        ".venv/bin/python -m src.experiments.closure_v2.evaluate_models --execute",
    ]
    return {
        "schema_version": "closure_v2_model_lock_v1",
        "experiment_id": "closure_v2",
        "status": "locked_unpublished",
        "authority_head": authority["authority_head"],
        "model_lock_effective_after_annotated_tag": MODEL_LOCK_TAG,
        "models": models,
        "shared_fit": {
            "rows_per_seed": 8925,
            "identity_sha256": "5ac41d4ef2c04115ff1178e03b386e98e9496513cfdd441f24d75b19b194a474",
            "digests": shared_fit_digests,
            "pointer": file_record(
                root / SHARED_KEYS_POINTER, root=root, role="shared_fit_keys_dvc_pointer"
            ),
        },
        "calibration": {
            "manifest": file_record(
                root / CALIBRATION_MANIFEST, root=root, role="calibration_manifest"
            ),
            "calibrator_specs": specs,
            "alert_thresholds": thresholds,
            "conformal_quantiles": conformal,
            "model_availability": availability,
            "recalibration_after_evaluation": "forbidden",
        },
        "cohorts": cohorts,
        "hypotheses": {
            "primary_comparisons": benchmark["primary_comparisons"],
            "secondary_comparisons": benchmark["secondary_comparisons"],
            "multiplicity": plan["multiplicity"],
            "global_winner_required": False,
        },
        "output_contract": output_contract,
        "sealed_commands": sealed_commands,
        "authorization": {
            "calibration_authorized": True,
            "model_fit_authorized": False,
            "refit_authorized": False,
            "recalibration_authorized": False,
            "evaluation_authorized": False,
            "post_2021_outcomes_authorized": False,
            "activation_required": True,
            "activation_one_shot": True,
        },
        "manifest_written_last": True,
    }


def execute_lock(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    for path in (MODEL_LOCK_PATH, MODEL_LOCK_MANIFEST_PATH):
        if (root / path).exists() or (root / path).is_symlink():
            raise ModelLockError(f"Refusing to overwrite model-lock output: {path}")
    payload = build_lock_payload(root=root)
    validate_json_schema(
        payload,
        load_json_mapping(root / MODEL_LOCK_SCHEMA),
        instance_path="$.model_lock",
    )
    lock_bytes = canonical_json_bytes(payload)
    lock_record = _virtual_record(MODEL_LOCK_PATH, lock_bytes, "model_lock")
    manifest = {
        "schema_version": "closure_v2_model_lock_manifest_v1",
        "experiment_id": "closure_v2",
        "status": "completed",
        "authority_head": payload["authority_head"],
        "model_lock_effective_after_annotated_tag": MODEL_LOCK_TAG,
        "script": file_record(
            root / Path("src/experiments/closure_v2/lock_models.py"),
            root=root,
            role="model_locker",
        ),
        "inputs": [
            file_record(root / MODEL_LOCK_SCHEMA, root=root, role="model_lock_schema"),
            file_record(root / FAMILY_MANIFEST, root=root, role="temporal_family_manifest"),
            file_record(root / CALIBRATION_MANIFEST, root=root, role="calibration_manifest"),
            file_record(root / ANALYSIS_PLAN, root=root, role="analysis_plan"),
            file_record(root / COHORT_CONFIG, root=root, role="evaluation_cohorts"),
            file_record(root / BENCHMARK_CONFIG, root=root, role="model_benchmark"),
            file_record(root / MODELS_POINTER, root=root, role="models_dvc_pointer"),
        ],
        "outputs": [lock_record],
        "evaluation_authorized": False,
        "post_2021_outcomes_authorized": False,
        "manifest_written_last": True,
    }
    _exclusive_bundle(
        [
            (MODEL_LOCK_PATH, lock_bytes),
            (MODEL_LOCK_MANIFEST_PATH, canonical_json_bytes(manifest)),
        ],
        root=root,
    )
    return manifest


def load_effective_model_lock(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    lock_path = _require_regular(root, MODEL_LOCK_PATH)
    manifest_path = _require_regular(root, MODEL_LOCK_MANIFEST_PATH)
    try:
        tag_type = _git("cat-file", "-t", f"refs/tags/{MODEL_LOCK_TAG}", root=root)
    except subprocess.CalledProcessError as error:
        raise ModelLockError(f"{MODEL_LOCK_TAG} must be an annotated tag") from error
    if tag_type != "tag":
        raise ModelLockError(f"{MODEL_LOCK_TAG} must be an annotated tag")
    peeled = _git("rev-parse", f"{MODEL_LOCK_TAG}^{{}}", root=root)
    head = _git("rev-parse", "HEAD", root=root)
    remote = _git("rev-parse", "origin/closure-v2", root=root)
    if peeled != head or remote != head:
        raise ModelLockError("Published model-lock tag, HEAD and origin must coincide")
    for relative, live in ((MODEL_LOCK_PATH, lock_path), (MODEL_LOCK_MANIFEST_PATH, manifest_path)):
        tagged = subprocess.run(
            ["git", "show", f"{MODEL_LOCK_TAG}:{relative.as_posix()}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        if tagged != live.read_bytes():
            raise ModelLockError(f"Live model-lock authority differs from tag: {relative}")
    lock = dict(load_json_mapping(lock_path))
    manifest = load_json_mapping(manifest_path)
    validate_json_schema(lock, load_json_mapping(root / MODEL_LOCK_SCHEMA), instance_path="$.model_lock")
    output = cast(Sequence[Mapping[str, Any]], manifest["outputs"])[0]
    if output.get("sha256") != sha256_file(lock_path) or output.get("bytes") != lock_path.stat().st_size:
        raise ModelLockError("Model-lock companion hash drifted")
    if lock["authorization"]["evaluation_authorized"] is not False:
        raise ModelLockError("Model lock must require a separate one-shot activation")
    return {
        "status": "model_lock_effective",
        "commit": head,
        "tag": MODEL_LOCK_TAG,
        "model_lock_sha256": sha256_file(lock_path),
        "evaluation_authorized": False,
        "activation_required": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-lock", action="store_true")
    parser.add_argument("--check-effective", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.execute_lock and args.check_effective:
        raise ModelLockError("Choose exactly one model-lock action")
    if args.execute_lock:
        result = execute_lock()
    elif args.check_effective:
        result = load_effective_model_lock()
    else:
        result = {**validate_lock_inputs(), "outputs_written": False}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
