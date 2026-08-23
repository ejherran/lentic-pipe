#!/usr/bin/env python
"""Calibrate Closure V2 temporal families using development outcomes from 2021 only."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import torch

from src.experiments.calibrate_closure_final_models import (
    apply_calibrator_spec,
    brier_score,
    expected_calibration_error,
    fit_calibrator_spec,
    select_alert_threshold,
    select_calibration_method,
)
from src.experiments.closure_contract import load_json_mapping, load_yaml_mapping, validate_json_schema
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT, audit_repository
from src.experiments.closure_v2.build_eligibility import (
    EXPECTED_SEEDS,
    IDENTITY_COLUMNS,
    INPUT_COLUMNS,
    LEDGER_OUTPUT,
    TARGET_COLUMNS,
)
from src.experiments.closure_v2.hashing import canonical_json_bytes, file_record, sha256_file
from src.experiments.closure_v2.summarize_temporal import MODELS_POINTER, validate_models_pointer
from src.experiments.closure_v2.train_temporal import (
    DEVELOPMENT_LOCK,
    ELIGIBILITY_MANIFEST,
    FAMILY_MANIFEST,
    MODEL_IDS,
    TemporalTrainingError,
    _csv_bytes,
    _exclusive_bundle,
    _require_regular,
    _sequence_path,
    _slot_paths,
    _virtual_record,
    validate_development_authority,
)
from src.experiments.train_pipe_grud import STATE_TARGET_NAMES, apply_output_blend, make_model


CALIBRATION_CONFIG = Path("configs/closure_v2/calibration.yaml")
CALIBRATION_SCHEMA = Path("configs/closure_v2/calibration.schema.json")
ANALYSIS_PLAN = Path("configs/closure_v2/analysis_plan.yaml")
TARGETS_PATH = Path("data/targets/monthly_targets_model_v0.parquet")
ASSIGNMENT_PATH = Path("data/closure_v1/closure_holdout_assignment.csv")
OUTPUT_ROOT = Path("reports/closure_v2/03_calibration")
SPECS_PATH = OUTPUT_ROOT / "calibrator_specs.json"
METRICS_PATH = OUTPUT_ROOT / "calibration_metrics.csv"
THRESHOLDS_PATH = OUTPUT_ROOT / "alert_thresholds.csv"
CONFORMAL_PATH = OUTPUT_ROOT / "conformal_quantiles.csv"
AVAILABILITY_PATH = OUTPUT_ROOT / "model_availability.csv"
MANIFEST_PATH = OUTPUT_ROOT / "calibration_manifest.json"
OUTPUT_PATHS = (
    SPECS_PATH,
    METRICS_PATH,
    THRESHOLDS_PATH,
    CONFORMAL_PATH,
    AVAILABILITY_PATH,
    MANIFEST_PATH,
)
HORIZONS = (1, 2, 3)
CALIBRATION_HEAD = "1bf9b553dd1234b309fa6172a92d536d143499dc"


class CalibrationError(TemporalTrainingError):
    """Raised when calibration crosses a sealed Closure V2 boundary."""


def _git(*args: str, root: Path = PROJECT_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def validate_runtime(path: Path = CALIBRATION_CONFIG) -> dict[str, Any]:
    runtime = dict(load_yaml_mapping(path))
    validate_json_schema(
        runtime,
        load_json_mapping(CALIBRATION_SCHEMA),
        instance_path="$.calibration_runtime",
    )
    expected = {
        "models": ["P0", "P1"],
        "seeds": EXPECTED_SEEDS,
        "horizons": [1, 2, 3],
        "data_role": "calibration_threshold",
    }
    for key, value in expected.items():
        if runtime.get(key) != value:
            raise CalibrationError(f"Calibration runtime drifted: {key}")
    if runtime.get("raw_bloom_score") != {
        "method": "irc_from_predicted_state",
        "alpha_yN": 0.5,
        "beta_one_minus_yF": 0.5,
        "gamma_yT": 2.0,
        "clip": [0.0, 1.0],
    }:
        raise CalibrationError("Raw bloom-score contract drifted")
    if runtime.get("calibrator_selection") != {
        "candidates": ["identity", "platt_logistic", "isotonic_regression"],
        "primary_metric": "brier",
        "secondary_metric": "ece10",
        "brier_tolerance": 0.001,
        "assessment": "calibration_threshold_2021_in_sample_no_unregistered_subsplit",
    }:
        raise CalibrationError("Calibrator-selection contract drifted")
    if runtime.get("conformal") != {
        "score": "absolute_state_residual",
        "quantile_method": "higher",
        "coverages": [0.8, 0.9, 0.95],
    }:
        raise CalibrationError("Conformal contract drifted")
    if runtime.get("authorization_thresholds") != {
        "minimum_shared_calibration_rows_per_slot": 200,
        "minimum_shared_calibration_locations_per_slot": 30,
        "metric_evaluable_support_per_horizon": "positive",
    }:
        raise CalibrationError("Calibration authorization thresholds drifted")
    return runtime


def validate_authority(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    validate_runtime(root / CALIBRATION_CONFIG)
    development = validate_development_authority(root)
    head = _git("rev-parse", "HEAD", root=root)
    remote = _git("rev-parse", "origin/closure-v2", root=root)
    if head != CALIBRATION_HEAD or remote != head:
        raise CalibrationError("Calibration requires the published temporal-family commit")
    family = load_json_mapping(_require_regular(root, FAMILY_MANIFEST))
    if (
        family.get("status") != "completed"
        or family.get("slot_count") != 10
        or family.get("selection_metric_rows") != 90
    ):
        raise CalibrationError("Temporal family manifest is not complete")
    for model_id in MODEL_IDS:
        for seed in EXPECTED_SEEDS:
            manifest = load_json_mapping(_require_regular(root, _slot_paths(model_id, seed)["manifest"]))
            if manifest.get("status") != "completed":
                raise CalibrationError(f"Temporal slot is unavailable: {model_id}/{seed}")
    validate_models_pointer(root=root)
    v1 = audit_repository(root)
    if v1["protected_v1_changes"]:
        raise CalibrationError(f"Closure V1 drift detected: {v1['protected_v1_changes']}")
    return {
        "status": "calibration_authorized",
        "head": head,
        "development_commit": development["development_commit"],
        "temporal_family_commit": CALIBRATION_HEAD,
        "evaluation_authorized": False,
        "post_2021_outcomes_authorized": False,
    }


def _month_add(value: str, horizon: int) -> str:
    period = cast(pd.Period, pd.Period(value, freq="M")) + horizon
    return f"{period.year:04d}-{period.month:02d}"


def _season(months: Sequence[str]) -> np.ndarray:
    month = np.asarray([int(value[5:7]) for value in months], dtype=np.float32)
    radians = 2.0 * np.pi * (month - 1.0) / 12.0
    return np.column_stack(
        [np.sin(radians), np.cos(radians), np.sin(2.0 * radians), np.cos(2.0 * radians)]
    ).astype(np.float32)


def _shared_calibration_origins(
    model_id: str, seed: int, *, root: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ledger = pq.read_table(_require_regular(root, LEDGER_OUTPUT)).to_pandas()
    slot = ledger.loc[
        ledger["model_id"].eq(model_id)
        & ledger["base_seed"].eq(seed)
        & ledger["shared_calibration_eligible"]
    ].copy()
    if len(slot) != 302 or slot["site_id"].nunique() != 58:
        raise CalibrationError(f"Shared calibration denominator drifted: {model_id}/{seed}")
    source = pq.read_table(_require_regular(root, _sequence_path(model_id, seed))).to_pandas()
    source_role = source.loc[source["time_role"].eq("calibration_threshold")].copy()
    keys = set(slot[IDENTITY_COLUMNS].itertuples(index=False, name=None))
    selected = source_role.loc[
        source_role[IDENTITY_COLUMNS].apply(tuple, axis=1).isin(keys)
    ].copy()
    if (
        len(selected) != 302
        or set(selected["assignment_role"].astype(str)) != {"development"}
        or selected["origin_year_month"].astype(str).min() < "2021-01"
        or selected["target_year_month"].astype(str).max() > "2021-12"
    ):
        raise CalibrationError(f"Calibration sequence boundary drifted: {model_id}/{seed}")
    selected = selected.sort_values(IDENTITY_COLUMNS, kind="stable").reset_index(drop=True)
    return selected, source_role


def scan_calibration_targets(
    development_sites: Sequence[str], *, root: Path
) -> tuple[pd.DataFrame, dict[str, Any]]:
    target_path = _require_regular(root, TARGETS_PATH)
    dataset = ds.dataset(target_path.as_posix(), format="parquet")
    columns = [
        "source_id",
        "site_id",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
        "has_target",
        "bloom_h",
        "target_risk_chla_h",
    ]
    predicate = (
        (ds.field("source_id") == "wqp")
        & ds.field("site_id").isin(list(development_sites))
        & (ds.field("origin_year_month") >= "2021-01")
        & (ds.field("origin_year_month") <= "2021-11")
        & (ds.field("target_year_month") >= "2021-02")
        & (ds.field("target_year_month") <= "2021-12")
        & ds.field("has_target")
    )
    frame = dataset.scanner(columns=columns, filter=predicate).to_table().to_pandas()
    if (
        frame.empty
        or set(frame["source_id"].astype(str)) != {"wqp"}
        or frame["origin_year_month"].astype(str).min() < "2021-01"
        or frame["target_year_month"].astype(str).max() > "2021-12"
        or not set(frame["site_id"].astype(str)).issubset(set(development_sites))
        or frame[["bloom_h", "target_risk_chla_h"]].isna().any().any()
    ):
        raise CalibrationError("Predicate-pushed 2021 calibration targets crossed a boundary")
    key_columns = ["source_id", "site_id", "origin_year_month", "horizon_months"]
    if frame.duplicated(key_columns).any():
        raise CalibrationError("Calibration target identities are duplicated")
    audit = {
        "scanner": "pyarrow_dataset_predicate_pushdown",
        "predicate": "source=wqp; assignment=development; origin=2021-01..2021-11; target=2021-02..2021-12; has_target=true",
        "rows_materialized": len(frame),
        "locations_materialized": int(frame["site_id"].nunique()),
        "origin_min": str(frame["origin_year_month"].min()),
        "origin_max": str(frame["origin_year_month"].max()),
        "target_min": str(frame["target_year_month"].min()),
        "target_max": str(frame["target_year_month"].max()),
        "post_2021_rows_materialized": 0,
        "holdout_rows_materialized": 0,
    }
    return frame, audit


def _load_model(model_id: str, seed: int, *, root: Path) -> tuple[Any, Any, Mapping[str, Any]]:
    payload = torch.load(
        _require_regular(root, _slot_paths(model_id, seed)["model"]),
        map_location="cpu",
        weights_only=False,
    )
    if not isinstance(payload, Mapping) or payload.get("model_id") != model_id or payload.get("base_seed") != seed:
        raise CalibrationError(f"Model payload identity drifted: {model_id}/{seed}")
    architecture = cast(Mapping[str, Any], payload["architecture"])
    model = make_model(
        int(architecture["input_dimension"]),
        int(architecture["target_dimension"]),
        int(architecture["hidden_dimension"]),
        int(architecture["recurrent_layers"]),
        float(architecture["dropout"]),
        str(architecture["residual_mode"]),
    )
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    blend_map = cast(Mapping[str, Any], payload["output_blend_weights"])
    blend = torch.tensor([float(blend_map[name]) for name in STATE_TARGET_NAMES], dtype=torch.float32)
    return model, blend, payload


def recursive_predictions(
    selected: pd.DataFrame,
    model: Any,
    blend: Any,
) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    matrices = []
    for row in selected.to_dict(orient="records"):
        columns = [np.asarray(row[column], dtype=np.float32) for column in INPUT_COLUMNS]
        if any(value.shape != (12,) or not np.isfinite(value).all() for value in columns):
            raise CalibrationError("Calibration input sequence is nonfinite")
        matrices.append(np.column_stack(columns))
    history = torch.from_numpy(np.stack(matrices).astype(np.float32, copy=False))
    outputs: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    with torch.no_grad():
        for horizon in HORIZONS:
            mu, logvar = model(history)
            mu = apply_output_blend(mu, history, blend)
            sigma = torch.sqrt(torch.exp(torch.clamp(logvar, min=-10.0, max=2.0)))
            state = mu.detach().cpu().numpy().astype(np.float64)
            outputs[horizon] = (state, sigma.detach().cpu().numpy().astype(np.float64))
            target_months = [
                _month_add(value, horizon)
                for value in selected["origin_year_month"].astype(str)
            ]
            next_input = np.column_stack([state.astype(np.float32), _season(target_months)])
            history = torch.cat([history[:, 1:, :], torch.from_numpy(next_input)[:, None, :]], dim=1)
    return outputs


def _irc_probability(state: np.ndarray) -> np.ndarray:
    return np.clip((0.5 * state[:, 0] + 0.5 * (1.0 - state[:, 1]) + 2.0 * state[:, 2]) / 3.0, 0.0, 1.0)


def _state_targets(
    source_role: pd.DataFrame,
    selected: pd.DataFrame,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    lookup = source_role[["source_id", "site_id", "target_year_month", *TARGET_COLUMNS]].copy()
    lookup = lookup.dropna(subset=TARGET_COLUMNS)
    if lookup.duplicated(["source_id", "site_id", "target_year_month"]).any():
        raise CalibrationError("Calibration state target lookup is duplicated")
    wanted = selected[["source_id", "site_id", "origin_year_month"]].copy()
    wanted["target_year_month"] = [
        _month_add(value, horizon) for value in wanted["origin_year_month"].astype(str)
    ]
    joined = wanted.merge(
        lookup,
        on=["source_id", "site_id", "target_year_month"],
        how="left",
        validate="many_to_one",
    )
    mask = joined[TARGET_COLUMNS].notna().all(axis=1).to_numpy(dtype=bool)
    return joined[TARGET_COLUMNS].to_numpy(dtype=np.float64), mask


def _higher_quantile(values: np.ndarray, coverage: float) -> float:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or not len(array) or not np.isfinite(array).all():
        raise CalibrationError("Conformal scores must be finite and nonempty")
    return float(np.quantile(array, coverage, method="higher"))


def calibrate(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_authority(root)
    for relative in OUTPUT_PATHS:
        if (root / relative).exists() or (root / relative).is_symlink():
            raise CalibrationError(f"Refusing to overwrite calibration output: {relative}")
    guard = root / "tmp/closure_v2_calibration.guard"
    guard.parent.mkdir(parents=True, exist_ok=True)
    try:
        guard.mkdir()
    except FileExistsError as error:
        raise CalibrationError("Calibration guard already exists") from error
    try:
        assignment = pd.read_csv(_require_regular(root, ASSIGNMENT_PATH))
        development_sites = sorted(
            assignment.loc[assignment["assignment_role"].astype(str).eq("development"), "site_id"]
            .astype(str)
            .unique()
        )
        holdout_sites = set(
            assignment.loc[assignment["assignment_role"].astype(str).eq("holdout"), "site_id"].astype(str)
        )
        targets, target_scan = scan_calibration_targets(development_sites, root=root)
        if set(targets["site_id"].astype(str)) & holdout_sites:
            raise CalibrationError("Calibration targets overlap holdout")

        specs: list[dict[str, Any]] = []
        metric_rows: list[dict[str, Any]] = []
        threshold_rows: list[dict[str, Any]] = []
        conformal_rows: list[dict[str, Any]] = []
        availability_rows: list[dict[str, Any]] = []
        input_records: list[dict[str, Any]] = []
        for model_id in MODEL_IDS:
            for seed in EXPECTED_SEEDS:
                selected, source_role = _shared_calibration_origins(model_id, seed, root=root)
                model, blend, payload = _load_model(model_id, seed, root=root)
                rollouts = recursive_predictions(selected, model, blend)
                model_path = root / _slot_paths(model_id, seed)["model"]
                checkpoint_path = root / _slot_paths(model_id, seed)["checkpoint"]
                input_records.extend(
                    [
                        file_record(model_path, root=root, role="temporal_model"),
                        file_record(checkpoint_path, root=root, role="raw_best_checkpoint"),
                    ]
                )
                for horizon in HORIZONS:
                    predicted_state, _predicted_sigma = rollouts[horizon]
                    identities = selected[["source_id", "site_id", "origin_year_month"]].copy()
                    identities["horizon_months"] = horizon
                    joined = identities.merge(
                        targets,
                        on=["source_id", "site_id", "origin_year_month", "horizon_months"],
                        how="left",
                        validate="one_to_one",
                    )
                    bloom_mask = joined["bloom_h"].notna().to_numpy(dtype=bool)
                    state_target, state_mask = _state_targets(source_role, selected, horizon)
                    usable = bloom_mask & state_mask
                    rows = int(usable.sum())
                    locations = int(joined.loc[usable, "site_id"].nunique())
                    if rows <= 0 or locations <= 0:
                        raise CalibrationError(
                            f"Calibration horizon has no evaluable support: {model_id}/{seed}/h{horizon}"
                        )
                    labels = joined.loc[usable, "bloom_h"].astype("int8").to_numpy()
                    raw = _irc_probability(predicted_state[usable])
                    selected_method, evidence = select_calibration_method(
                        raw, labels, raw, labels, tolerance=0.001
                    )
                    final_spec = fit_calibrator_spec(selected_method, raw, labels)
                    calibrated = apply_calibrator_spec(final_spec, raw)
                    selected_threshold = select_alert_threshold(calibrated, labels, beta=2.0)
                    group_id = f"{model_id}/seed_{seed}/h{horizon}"
                    specs.append(
                        {
                            "group_id": group_id,
                            "model_id": model_id,
                            "base_seed": seed,
                            "horizon_months": horizon,
                            "selected_method": selected_method,
                            "spec": final_spec,
                            "raw_score": "irc_0p5_0p5_2p0_from_recursive_predicted_state",
                            "fit_rows": rows,
                            "fit_locations": locations,
                            "assessment": "calibration_threshold_2021_in_sample_no_unregistered_subsplit",
                        }
                    )
                    for candidate in evidence:
                        metric_rows.append(
                            {
                                "model_id": model_id,
                                "base_seed": seed,
                                "horizon_months": horizon,
                                "candidate_method": candidate["method"],
                                "selected": candidate["method"] == selected_method,
                                "rows": rows,
                                "locations": locations,
                                "brier": candidate["brier"],
                                "ece10": candidate["ece10"],
                                "assessment": "calibration_threshold_2021_in_sample_no_unregistered_subsplit",
                            }
                        )
                    threshold_rows.append(
                        {
                            "model_id": model_id,
                            "base_seed": seed,
                            "horizon_months": horizon,
                            "calibrator_method": selected_method,
                            "threshold": selected_threshold["threshold"],
                            "f2": selected_threshold["f2"],
                            "recall": selected_threshold["recall"],
                            "precision": selected_threshold["precision"],
                            "rows": rows,
                            "locations": locations,
                        }
                    )
                    residual = np.abs(state_target[usable] - predicted_state[usable])
                    for target_index, target_name in enumerate(STATE_TARGET_NAMES):
                        for coverage in (0.8, 0.9, 0.95):
                            conformal_rows.append(
                                {
                                    "model_id": model_id,
                                    "base_seed": seed,
                                    "horizon_months": horizon,
                                    "target": target_name,
                                    "coverage": coverage,
                                    "quantile": _higher_quantile(residual[:, target_index], coverage),
                                    "score": "absolute_state_residual",
                                    "quantile_method": "higher",
                                    "rows": rows,
                                }
                            )
                    availability_rows.append(
                        {
                            "model_id": model_id,
                            "base_seed": seed,
                            "status": "available",
                            "selected_profile": payload["profile"],
                            "calibrated_horizons": "1|2|3",
                            "minimum_calibration_rows": rows,
                            "minimum_calibration_locations": locations,
                            "replacement_used": False,
                        }
                    ) if horizon == 3 else None

        if len(specs) != 30 or len(metric_rows) != 90 or len(threshold_rows) != 30 or len(conformal_rows) != 810 or len(availability_rows) != 10:
            raise CalibrationError("Calibration output cardinality drifted")
        spec_payload = {
            "schema_version": "closure_v2_calibrator_specs_v1",
            "experiment_id": "closure_v2",
            "status": "completed",
            "selection_rule": "minimum_brier_within_0.001_then_ece10_then_simplicity",
            "groups": specs,
        }
        specs_bytes = canonical_json_bytes(spec_payload)
        metrics_bytes = _csv_bytes(pd.DataFrame(metric_rows))
        thresholds_bytes = _csv_bytes(pd.DataFrame(threshold_rows))
        conformal_bytes = _csv_bytes(pd.DataFrame(conformal_rows))
        availability_bytes = _csv_bytes(pd.DataFrame(availability_rows))
        output_records = [
            _virtual_record(SPECS_PATH, specs_bytes, "calibrator_specs"),
            _virtual_record(METRICS_PATH, metrics_bytes, "calibration_metrics"),
            _virtual_record(THRESHOLDS_PATH, thresholds_bytes, "alert_thresholds"),
            _virtual_record(CONFORMAL_PATH, conformal_bytes, "conformal_quantiles"),
            _virtual_record(AVAILABILITY_PATH, availability_bytes, "model_availability"),
        ]
        manifest = {
            "schema_version": "closure_v2_calibration_manifest_v1",
            "experiment_id": "closure_v2",
            "status": "completed",
            "authority": authority,
            "models": {"P0": "5/5_available", "P1": "5/5_available"},
            "group_count": 30,
            "candidate_metric_rows": 90,
            "threshold_rows": 30,
            "conformal_rows": 810,
            "target_scan": target_scan,
            "script": file_record(
                root / Path("src/experiments/closure_v2/calibrate_temporal.py"),
                root=root,
                role="calibration_writer",
            ),
            "inputs": [
                file_record(root / CALIBRATION_CONFIG, root=root, role="calibration_runtime"),
                file_record(root / ANALYSIS_PLAN, root=root, role="analysis_plan"),
                file_record(root / DEVELOPMENT_LOCK, root=root, role="development_lock"),
                file_record(root / ELIGIBILITY_MANIFEST, root=root, role="eligibility_manifest"),
                file_record(root / FAMILY_MANIFEST, root=root, role="temporal_family_manifest"),
                file_record(root / MODELS_POINTER, root=root, role="models_dvc_pointer"),
                file_record(root / TARGETS_PATH, root=root, role="development_target_store_predicate_scanned"),
                *input_records,
            ],
            "outputs": output_records,
            "evaluation_paths_opened": False,
            "post_2021_outcomes_opened": False,
            "holdout_rows_materialized": 0,
            "recalibration_after_evaluation": False,
            "replacement_used": False,
            "manifest_written_last": True,
        }
        _exclusive_bundle(
            [
                (SPECS_PATH, specs_bytes),
                (METRICS_PATH, metrics_bytes),
                (THRESHOLDS_PATH, thresholds_bytes),
                (CONFORMAL_PATH, conformal_bytes),
                (AVAILABILITY_PATH, availability_bytes),
                (MANIFEST_PATH, canonical_json_bytes(manifest)),
            ],
            root=root,
        )
        return manifest
    finally:
        guard.rmdir()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    authority = validate_authority()
    if args.execute:
        result = calibrate()
    else:
        result = {
            "status": "ready_to_calibrate",
            "authority": authority,
            "outputs_written": False,
            "registered_groups": 30,
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
