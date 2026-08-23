#!/usr/bin/env python
"""Audit the ten immutable Closure V2 fits and write their family summary."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml

from src.experiments.closure_contract import load_json_mapping
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT
from src.experiments.closure_v2.build_eligibility import EXPECTED_SEEDS
from src.experiments.closure_v2.hashing import canonical_json_bytes, file_record, md5_file
from src.experiments.closure_v2.train_temporal import (
    FAMILY_MANIFEST,
    FAMILY_REPORT,
    FAMILY_SUMMARY,
    MODEL_IDS,
    TemporalTrainingError,
    _csv_bytes,
    _exclusive_bundle,
    _require_regular,
    _slot_paths,
    _verify_record,
    _virtual_record,
    validate_development_authority,
)
from src.experiments.train_pipe_grud import STATE_TARGET_NAMES


MODELS_POINTER = Path("models.dvc")


def validate_models_pointer(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    pointer = _require_regular(root, MODELS_POINTER)
    loaded = yaml.safe_load(pointer.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise TemporalTrainingError("models.dvc is not a mapping")
    outs = loaded.get("outs")
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise TemporalTrainingError("models.dvc must expose one directory output")
    output = dict(cast(Mapping[str, Any], outs[0]))
    if (
        output.get("path") != "models"
        or output.get("hash") != "md5"
        or not str(output.get("md5", "")).endswith(".dir")
        or int(output.get("size", 0)) <= 0
        or int(output.get("nfiles", 0)) <= 0
    ):
        raise TemporalTrainingError("models.dvc directory contract drifted")
    status = subprocess.run(
        [".venv/bin/dvc", "status", MODELS_POINTER.as_posix()],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status != "Data and pipelines are up to date.":
        raise TemporalTrainingError(f"models.dvc is not clean: {status}")
    return {
        "pointer": file_record(pointer, root=root, role="models_directory_dvc_pointer"),
        "directory_md5": output["md5"],
        "directory_bytes": int(output["size"]),
        "directory_files": int(output["nfiles"]),
    }


def validate_slot(
    model_id: str, base_seed: int, *, root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    paths = _slot_paths(model_id, base_seed)
    manifest_path = _require_regular(root, paths["manifest"])
    manifest = dict(load_json_mapping(manifest_path))
    identity = {
        "schema_version": "closure_v2_temporal_slot_manifest_v1",
        "status": "completed",
        "model_id": model_id,
        "base_seed": base_seed,
    }
    for key, expected in identity.items():
        if manifest.get(key) != expected:
            raise TemporalTrainingError(f"Slot identity/status mismatch: {model_id}/{base_seed}/{key}")
    if manifest.get("denominators") != {
        "ledger_intent_rows": 9732,
        "fit_intent_rows": 9413,
        "shared_fit_rows": 8925,
        "training_rows": 7909,
        "model_selection_rows": 1016,
        "calibration_rows_excluded_from_fit": 319,
        "retained_fit_failures_outside_loss": 488,
    }:
        raise TemporalTrainingError(f"Slot denominators drifted: {model_id}/{base_seed}")
    for predicate in (
        "evaluation_paths_opened",
        "post_2021_outcomes_opened",
        "current_chla_input_lineage",
        "replacement_used",
        "resume_used",
    ):
        if manifest.get(predicate) is not False:
            raise TemporalTrainingError(f"Forbidden slot predicate: {model_id}/{base_seed}/{predicate}")
    if manifest.get("output_blend_recalculations_after_selected_best_restore") != 1:
        raise TemporalTrainingError(f"Blend count drifted: {model_id}/{base_seed}")

    outputs = cast(Sequence[Mapping[str, Any]], manifest.get("outputs", ()))
    output_by_path = {str(record.get("path")): record for record in outputs}
    for name in ("model", "checkpoint", "curve", "metrics", "blend", "report"):
        relative = paths[name]
        record = output_by_path.get(relative.as_posix())
        if record is None:
            raise TemporalTrainingError(f"Unregistered slot output: {relative}")
        _verify_record(record, root=root)

    model = _require_regular(root, paths["model"])
    checkpoint = _require_regular(root, paths["checkpoint"])
    metrics = pd.read_csv(root / paths["metrics"])
    selection = metrics.loc[
        metrics["record_type"].eq("selected_profile_metric")
        & metrics["time_role"].eq("model_selection")
        & metrics["target"].ne("all")
    ].copy()
    if len(selection) != len(STATE_TARGET_NAMES) or set(selection["target"].astype(str)) != set(STATE_TARGET_NAMES):
        raise TemporalTrainingError(f"Incomplete selection metrics: {model_id}/{base_seed}")
    rows: list[dict[str, Any]] = []
    for metric in selection.sort_values("target", kind="stable").to_dict(orient="records"):
        rows.append(
            {
                "model_id": model_id,
                "base_seed": base_seed,
                "status": "completed",
                "selected_profile": manifest["selected_profile"],
                "best_epoch": manifest["best_epoch"],
                "best_probabilistic_validation_loss": manifest[
                    "best_probabilistic_validation_loss"
                ],
                "ledger_intent_rows": 9732,
                "fit_intent_rows": 9413,
                "shared_fit_rows": 8925,
                "target": metric["target"],
                "selection_rows": int(metric["rows"]),
                "selection_rmse": float(metric["rmse"]),
                "selection_mae": float(metric["mae"]),
                "selection_nll": float(metric["nll"]),
                "selection_interval_90_coverage": float(metric["interval_90_coverage"]),
                "selection_interval_90_mean_width": float(metric["interval_90_mean_width"]),
                "model_sha256": output_by_path[paths["model"].as_posix()]["sha256"],
                "model_md5": md5_file(model),
                "checkpoint_sha256": output_by_path[paths["checkpoint"].as_posix()]["sha256"],
                "checkpoint_md5": md5_file(checkpoint),
                "runtime_seconds": manifest["runtime_seconds"],
                "environment": json.dumps(
                    manifest["environment"], sort_keys=True, separators=(",", ":")
                ),
            }
        )
    inputs = [
        file_record(manifest_path, root=root, role="completed_slot_manifest"),
        file_record(model, root=root, role="temporal_model"),
        file_record(checkpoint, root=root, role="raw_best_checkpoint"),
    ]
    return rows, inputs


def summarize(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    validate_development_authority(root)
    models_pointer = validate_models_pointer(root=root)
    for relative in (FAMILY_SUMMARY, FAMILY_REPORT, FAMILY_MANIFEST):
        if (root / relative).exists() or (root / relative).is_symlink():
            raise TemporalTrainingError(f"Refusing to overwrite family summary: {relative}")
    rows: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = [models_pointer["pointer"]]
    for model_id in MODEL_IDS:
        for base_seed in EXPECTED_SEEDS:
            slot_rows, slot_inputs = validate_slot(model_id, base_seed, root=root)
            rows.extend(slot_rows)
            inputs.extend(slot_inputs)
    summary = pd.DataFrame(rows).sort_values(
        ["model_id", "base_seed", "target"], kind="stable"
    )
    summary_bytes = _csv_bytes(summary)
    report_bytes = (
        "# Closure V2 temporal family summary\n\n"
        "- P0 availability: 5/5 completed slots.\n"
        "- P1 availability: 5/5 completed slots.\n"
        "- Per slot: 9,732 intent rows, 9,413 fit-intent rows and 8,925 shared eligible rows.\n"
        "- Profile/blend selection used model-selection data only.\n"
        "- Seeds remain an ensemble family; no seed was selected, retried or replaced.\n"
        "- Evaluation, post-2021 outcomes and current-Chl-a lineage accessed: no.\n"
        "- Individual SHA-256/MD5 hashes and the repository models.dvc directory pointer are recorded.\n"
    ).encode("utf-8")
    outputs = [
        _virtual_record(FAMILY_SUMMARY, summary_bytes, "family_summary"),
        _virtual_record(FAMILY_REPORT, report_bytes, "family_report"),
    ]
    manifest = {
        "schema_version": "closure_v2_temporal_family_manifest_v1",
        "experiment_id": "closure_v2",
        "status": "completed",
        "models": {"P0": {"completed_slots": 5}, "P1": {"completed_slots": 5}},
        "seeds": EXPECTED_SEEDS,
        "slot_count": 10,
        "selection_metric_rows": len(summary),
        "denominators_per_slot": {
            "ledger_intent_rows": 9732,
            "fit_intent_rows": 9413,
            "shared_fit_rows": 8925,
        },
        "models_dvc": models_pointer,
        "script": file_record(
            root / Path("src/experiments/closure_v2/summarize_temporal.py"),
            root=root,
            role="family_summary_writer",
        ),
        "inputs": inputs,
        "outputs": outputs,
        "seed_selection_used": False,
        "replacement_used": False,
        "evaluation_paths_opened": False,
        "post_2021_outcomes_opened": False,
        "current_chla_input_lineage": False,
        "manifest_written_last": True,
    }
    _exclusive_bundle(
        [
            (FAMILY_SUMMARY, summary_bytes),
            (FAMILY_REPORT, report_bytes),
            (FAMILY_MANIFEST, canonical_json_bytes(manifest)),
        ],
        root=root,
    )
    return manifest


def main() -> int:
    print(json.dumps(summarize(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
