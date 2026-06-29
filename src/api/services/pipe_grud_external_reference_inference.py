"""Run calibrated reference-profile PIPE-GRU-D inference for API datasets."""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd

from src.api.schemas.run import RunPlanResponse
from src.api.services.pipe_grud_external_adaptive_surface import (
    EXTERNAL_PIPE_ADAPTIVE_SURFACE_VERSION,
    adaptive_surface_artifacts_available,
    run_external_pipe_adaptive_surface_build,
)
from src.api.services.pipe_grud_external_inference import (
    _empty_rollouts,
    _file_record,
    _inference_args,
    _issue,
    _issue_lines,
    _select_external_windows,
    _serializable_args,
    _write_json,
    _write_text,
)
from src.experiments.build_pipe_sequences import PIPE_STATE_COLUMNS
from src.experiments.rollout_pipe_grud import (
    ROLLOUT_VERSION,
    CalibratorInfo,
    _load_model,
    _require_torch,
    alert_band,
    build_recent_top_alerts,
    build_summary,
    build_top_alerts,
    compute_irc,
    rollout_batch,
)

EXTERNAL_PIPE_GRUD_REFERENCE_INFERENCE_VERSION = "external_pipe_grud_reference_profile_inference_v0"
_REFERENCE_PROFILE = "adaptive_wqp_focused"
_DEFAULT_POLICY_NAME = "closest_pr"
_REFERENCE_MODEL = Path("models/pipe_grud/adaptive_wqp_focused/pipe_grud_model.pt")
_REFERENCE_MODEL_MANIFEST = Path("reports/pipe_grud/adaptive_wqp_focused/pipe_grud_manifest.json")
_ROLLOUT_CALIBRATOR_DIR = Path("models/pipe_grud/adaptive_wqp_focused/rollout_calibrators")
_CALIBRATION_MANIFEST = Path("reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_manifest.json")
_POLICY_MANIFEST = Path("reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_manifest.json")
_POLICY_THRESHOLDS = Path("reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_thresholds.csv")
_TARGET_EVENTS = frozenset({"irc_alert", "bloom_h"})


@dataclass(frozen=True)
class RolloutBloomCalibratorRecord:
    """Loaded rollout bloom calibrator metadata."""

    horizon: int
    score_column: str
    path: Path
    calibrator: Any
    method: str
    threshold: float
    training_rows: int
    positive_rows: int


@dataclass(frozen=True)
class PipeGrudExternalReferenceInferenceResult:
    """Artifacts and manifest payload emitted by calibrated reference inference."""

    manifest: dict[str, object]
    row_counts: dict[str, int]
    output_paths: tuple[Path, ...]


def reference_inference_artifacts_available() -> tuple[bool, list[str]]:
    """Return availability for reviewed artifacts required by reference inference."""

    missing: list[str] = []
    available, adaptive_missing = adaptive_surface_artifacts_available()
    if not available:
        missing.extend(adaptive_missing)
    for name, path in {
        "pipe_grud_model": _REFERENCE_MODEL,
        "pipe_grud_model_manifest": _REFERENCE_MODEL_MANIFEST,
        "pipe_grud_rollout_calibrators": _ROLLOUT_CALIBRATOR_DIR,
        "pipe_grud_rollout_calibration_manifest": _CALIBRATION_MANIFEST,
        "pipe_grud_alert_policy_manifest": _POLICY_MANIFEST,
        "pipe_grud_alert_policy_thresholds": _POLICY_THRESHOLDS,
    }.items():
        if not path.exists():
            missing.append(name)
    for horizon in (1, 2, 3):
        expected = _ROLLOUT_CALIBRATOR_DIR / f"rollout_bloom_h{horizon}_irc_mean_isotonic.joblib"
        if not expected.exists():
            missing.append(f"pipe_grud_rollout_bloom_calibrator_h{horizon}")
    return len(missing) == 0, missing


def run_external_pipe_grud_reference_profile_inference(
    *,
    dataset_id: str,
    plan: RunPlanResponse,
    run_dir: Path,
    workspace: Path,
    execution_id: str,
    adapter_id: str,
    adapter_interface_version: str,
    started_at: str,
    parameters: Mapping[str, object],
) -> PipeGrudExternalReferenceInferenceResult:
    """Build the adaptive surface, run PIPE-GRU-D rollouts, and apply reviewed alert policy."""

    torch = _require_torch()
    device = torch.device("cpu")
    model, model_config, model_payload, blend_weights = _load_model(_REFERENCE_MODEL, device)
    history_length = int(model_config["history_length"])
    args = _inference_args(parameters)
    policy_name = _policy_name(parameters)

    surface_parameters = dict(parameters)
    surface_parameters["history_length"] = history_length
    adaptive_surface = run_external_pipe_adaptive_surface_build(
        dataset_id=dataset_id,
        plan=plan,
        run_dir=run_dir,
        workspace=workspace,
        execution_id=execution_id,
        adapter_id=adapter_id,
        adapter_interface_version=adapter_interface_version,
        started_at=started_at,
        parameters=surface_parameters,
    )

    state_surface = pd.read_parquet(run_dir / "pipe_state_surface.parquet")
    origins = pd.read_parquet(run_dir / "pipe_inference_origins.parquet")
    x_windows, selected_origins = _select_external_windows(
        state_surface,
        origins,
        history_length=history_length,
        scope=args.scope,
        max_origins=args.max_origins,
    )
    calibrator_records = _load_rollout_bloom_calibrators(
        calibrator_dir=_ROLLOUT_CALIBRATOR_DIR,
        rollout_horizon=args.rollout_horizon,
    )
    rollout_calibrators = {
        horizon: CalibratorInfo(path=record.path, calibrator=record.calibrator, threshold=record.threshold)
        for horizon, record in calibrator_records.items()
    }
    policy_thresholds = _load_policy_thresholds(
        policy_name=policy_name,
        rollout_horizon=args.rollout_horizon,
    )

    if len(selected_origins) == 0:
        rollouts = _empty_reference_rollouts()
    else:
        rollouts = _run_reference_rollouts(
            x_windows=x_windows,
            selected_origins=selected_origins,
            model=model,
            blend_weights=blend_weights,
            args=args,
            device=device,
            calibrators=rollout_calibrators,
        )
        rollouts = _apply_rollout_bloom_calibrators(rollouts, calibrator_records)
        rollouts = _apply_policy_thresholds(rollouts, policy_thresholds, policy_name=policy_name)

    summary = build_summary(rollouts) if not rollouts.empty else pd.DataFrame()
    policy_summary = _build_policy_summary(rollouts)
    alerts = _build_reference_alerts(rollouts, policy_name=policy_name)
    top_alerts = build_top_alerts(rollouts, args.top_n) if not rollouts.empty else pd.DataFrame()
    recent_top_alerts = (
        build_recent_top_alerts(rollouts, top_n=args.top_n, recent_months=args.recent_months)
        if not rollouts.empty
        else pd.DataFrame()
    )

    output_paths = _write_reference_outputs(
        run_dir=run_dir,
        rollouts=rollouts,
        summary=summary,
        policy_summary=policy_summary,
        alerts=alerts,
        top_alerts=top_alerts,
        recent_top_alerts=recent_top_alerts,
    )
    threshold_coverage = _threshold_coverage(
        policy_thresholds,
        horizons=sorted(int(value) for value in rollouts["rollout_horizon_months"].dropna().unique())
        if "rollout_horizon_months" in rollouts
        else [],
    )
    calibrator_coverage = _calibrator_coverage(
        calibrator_records,
        horizons=sorted(int(value) for value in rollouts["rollout_horizon_months"].dropna().unique())
        if "rollout_horizon_months" in rollouts
        else [],
    )
    row_counts = {
        **{f"adaptive_surface_{key}": value for key, value in adaptive_surface.row_counts.items()},
        "selected_origins": int(len(selected_origins)),
        "rollout_rows": int(len(rollouts)),
        "summary_rows": int(len(summary)),
        "policy_summary_rows": int(len(policy_summary)),
        "alert_rows": int(len(alerts)),
        "top_alert_rows": int(len(top_alerts)),
        "recent_top_alert_rows": int(len(recent_top_alerts)),
        "loaded_bloom_calibrators": int(len(calibrator_records)),
        "policy_threshold_rows": int(len(policy_thresholds)),
        "generated_reports": 2,
    }
    readiness = {
        "surface_contract": EXTERNAL_PIPE_ADAPTIVE_SURFACE_VERSION,
        "reference_profile": _REFERENCE_PROFILE,
        "adaptive_reference_transform_applied": True,
        "adaptive_surface_ready": bool(
            cast(Mapping[str, object], adaptive_surface.manifest.get("readiness", {})).get(
                "ready_for_reference_inference"
            )
        ),
        "state_surface_matches_reference_profile": True,
        "reference_model_loaded": True,
        "reference_bloom_calibrators_applied": calibrator_coverage["complete"],
        "policy_thresholds_applied": threshold_coverage["complete"],
        "rollout_generated": len(rollouts) > 0,
        "ready_for_reference_inference": bool(
            len(rollouts) > 0 and calibrator_coverage["complete"] and threshold_coverage["complete"]
        ),
        "history_length": history_length,
        "rollout_horizon": args.rollout_horizon,
        "policy_name": policy_name,
    }
    blockers = _reference_blockers(
        row_counts=row_counts,
        readiness=readiness,
        threshold_coverage=threshold_coverage,
        calibrator_coverage=calibrator_coverage,
        adaptive_surface=adaptive_surface.manifest,
    )
    warnings = _reference_warnings(adaptive_surface.manifest)
    manifest: dict[str, object] = {
        "execution_id": execution_id,
        "plan_id": plan.plan_id,
        "dataset_id": dataset_id,
        "workflow": plan.workflow,
        "adapter": adapter_id,
        "adapter_interface_version": adapter_interface_version,
        "status": "completed",
        "execution_mode": "infer_reference_profile",
        "inference_version": EXTERNAL_PIPE_GRUD_REFERENCE_INFERENCE_VERSION,
        "rollout_version": ROLLOUT_VERSION,
        "reference_profile": _REFERENCE_PROFILE,
        "surface_contract": EXTERNAL_PIPE_ADAPTIVE_SURFACE_VERSION,
        "policy_name": policy_name,
        "outcome": "completed_reference_profile" if bool(readiness["ready_for_reference_inference"]) else "not_ready",
        "started_at": started_at,
        "completed_at": _now_utc(),
        "parameters": {**_serializable_args(args), "policy_name": policy_name},
        "row_counts": row_counts,
        "readiness": readiness,
        "blockers": blockers,
        "warnings": warnings,
        "threshold_coverage": threshold_coverage,
        "calibrator_coverage": calibrator_coverage,
        "model": _file_record(_REFERENCE_MODEL, workspace=Path(".")),
        "model_manifest": _file_record(_REFERENCE_MODEL_MANIFEST, workspace=Path("."))
        if _REFERENCE_MODEL_MANIFEST.exists()
        else None,
        "calibration_manifest": _file_record(_CALIBRATION_MANIFEST, workspace=Path("."))
        if _CALIBRATION_MANIFEST.exists()
        else None,
        "policy_manifest": _file_record(_POLICY_MANIFEST, workspace=Path("."))
        if _POLICY_MANIFEST.exists()
        else None,
        "policy_thresholds": _file_record(_POLICY_THRESHOLDS, workspace=Path(".")) if _POLICY_THRESHOLDS.exists() else None,
        "rollout_calibrators": _directory_record(_ROLLOUT_CALIBRATOR_DIR),
        "adaptive_surface_build": {
            "surface_version": adaptive_surface.manifest.get("surface_version"),
            "outcome": adaptive_surface.manifest.get("outcome"),
            "readiness": adaptive_surface.manifest.get("readiness", {}),
            "manifest": "pipe_adaptive_surface_manifest.json",
        },
        "model_payload": {
            "model_version": model_payload.get("model_version"),
            "history_length": history_length,
            "input_columns": model_payload.get("input_columns"),
            "target_columns": model_payload.get("target_columns"),
        },
        "limitations": [
            "This mode applies the reviewed adaptive WQP-focused reference transform, frozen PIPE-GRU-D model, rollout bloom calibrators, and 2B policy thresholds to an uploaded dataset.",
            "Predictive skill and field transferability are not guaranteed for a new water body.",
            "Outputs are model-derived early-warning indicators, not official environmental advisories.",
            "The 2B alert policy is a selected operating profile, not causal field evidence.",
        ],
        "artifacts": [_file_record(path, workspace=workspace) for path in (*adaptive_surface.output_paths, *output_paths)],
    }
    report_path = run_dir / "pipe_grud_reference_inference_report.md"
    manifest_path = run_dir / "pipe_grud_reference_inference_manifest.json"
    _write_text(report_path, _reference_report(manifest))
    _write_json(manifest_path, manifest)
    output_paths = (*adaptive_surface.output_paths, *output_paths, report_path, manifest_path)
    manifest["artifacts"] = [_file_record(path, workspace=workspace) for path in output_paths]
    _write_json(manifest_path, manifest)
    return PipeGrudExternalReferenceInferenceResult(
        manifest=manifest,
        row_counts=row_counts,
        output_paths=output_paths,
    )


def _run_reference_rollouts(
    *,
    x_windows: np.ndarray,
    selected_origins: pd.DataFrame,
    model: Any,
    blend_weights: Any | None,
    args: Namespace,
    device: Any,
    calibrators: dict[int, CalibratorInfo],
) -> pd.DataFrame:
    torch = _require_torch()
    generator = torch.Generator(device=device)
    generator.manual_seed(int(args.random_seed))
    parts: list[pd.DataFrame] = []
    for start in range(0, len(selected_origins), args.batch_size):
        end = start + int(args.batch_size)
        batch_info = selected_origins.iloc[start:end].reset_index(drop=True)
        batch_windows = x_windows[start:end]
        batch_parts = rollout_batch(
            model=model,
            blend_weights=blend_weights,
            x_windows=batch_windows,
            origin_months=batch_info["origin_year_month"],
            args=args,
            device=device,
            generator=generator,
            calibrators=calibrators,
        )
        identity = batch_info[["source_id", "site_id", "split", "origin_year_month"]].copy()
        origin_states = batch_windows[:, -1, : len(PIPE_STATE_COLUMNS)]
        identity["origin_irc1_rollout_basis"] = compute_irc(
            origin_states,
            alpha=args.irc_alpha,
            beta=args.irc_beta,
            gamma=args.irc_gamma,
        )
        for column_index, column in enumerate(PIPE_STATE_COLUMNS):
            identity[f"origin_{column}"] = origin_states[:, column_index]
        for batch_part in batch_parts:
            parts.append(pd.concat([identity.reset_index(drop=True), batch_part.reset_index(drop=True)], axis=1))
    rollouts = pd.concat(parts, ignore_index=True) if parts else _empty_reference_rollouts()
    rollouts.insert(0, "rollout_version", EXTERNAL_PIPE_GRUD_REFERENCE_INFERENCE_VERSION)
    rollouts["surface_contract"] = EXTERNAL_PIPE_ADAPTIVE_SURFACE_VERSION
    rollouts["reference_profile"] = _REFERENCE_PROFILE
    rollouts["deterministic"] = bool(args.deterministic)
    rollouts["predicted_alert_h"] = rollouts["alert_probability_irc"] >= args.alert_prob_threshold
    rollouts["alert_band"] = alert_band(rollouts["alert_probability_irc"])
    return rollouts


def _load_rollout_bloom_calibrators(
    *,
    calibrator_dir: Path,
    rollout_horizon: int,
) -> dict[int, RolloutBloomCalibratorRecord]:
    records: dict[int, RolloutBloomCalibratorRecord] = {}
    for horizon in range(1, rollout_horizon + 1):
        path = calibrator_dir / f"rollout_bloom_h{horizon}_irc_mean_isotonic.joblib"
        if not path.exists():
            continue
        payload = cast(Mapping[str, object], joblib.load(path))
        records[horizon] = RolloutBloomCalibratorRecord(
            horizon=horizon,
            score_column=str(payload.get("score_column", "irc_mean")),
            path=path,
            calibrator=payload["calibrator"],
            method=str(payload.get("method", "isotonic")),
            threshold=_float_or_default(payload.get("threshold"), 0.5),
            training_rows=_int_or_default(payload.get("training_rows"), 0),
            positive_rows=_int_or_default(payload.get("positive_rows"), 0),
        )
    return records


def _apply_rollout_bloom_calibrators(
    rollouts: pd.DataFrame,
    calibrators: Mapping[int, RolloutBloomCalibratorRecord],
) -> pd.DataFrame:
    out = rollouts.copy()
    out["rollout_probability_bloom_calibrated"] = np.nan
    out["rollout_bloom_calibrator_method"] = pd.NA
    for horizon, record in calibrators.items():
        if record.score_column not in out.columns:
            continue
        mask = out["rollout_horizon_months"] == int(horizon)
        score = pd.to_numeric(out.loc[mask, record.score_column], errors="coerce")
        valid_index = score[score.notna()].index
        if len(valid_index) == 0:
            continue
        probability = record.calibrator.predict(_clip01(out.loc[valid_index, record.score_column]))
        out.loc[valid_index, "rollout_probability_bloom_calibrated"] = _clip01(probability)
        out.loc[valid_index, "rollout_bloom_calibrator_method"] = record.method
    return out


def _load_policy_thresholds(*, policy_name: str, rollout_horizon: int) -> pd.DataFrame:
    thresholds = pd.read_csv(_POLICY_THRESHOLDS)
    selected = thresholds[
        (thresholds["policy_name"].astype(str) == policy_name)
        & (thresholds["target_event"].astype(str).isin(_TARGET_EVENTS))
        & (pd.to_numeric(thresholds["rollout_horizon_months"], errors="coerce") <= int(rollout_horizon))
    ].copy()
    if selected.empty:
        return selected
    selected["rollout_horizon_months"] = pd.to_numeric(
        selected["rollout_horizon_months"], errors="coerce"
    ).astype("int64")
    selected["selected_threshold"] = pd.to_numeric(selected["selected_threshold"], errors="coerce")
    return selected.sort_values(["target_event", "rollout_horizon_months"]).reset_index(drop=True)


def _apply_policy_thresholds(rollouts: pd.DataFrame, thresholds: pd.DataFrame, *, policy_name: str) -> pd.DataFrame:
    out = rollouts.copy()
    out["alert_policy_name"] = policy_name
    out["rollout_alert_probability_threshold_h"] = np.nan
    out["rollout_predicted_irc_alert_h"] = False
    out["rollout_bloom_probability_threshold_h"] = np.nan
    out["rollout_predicted_bloom_h"] = False
    for row in thresholds.to_dict(orient="records"):
        horizon = int(row["rollout_horizon_months"])
        score_column = str(row["score_column"])
        threshold = float(row["selected_threshold"])
        if score_column not in out.columns:
            continue
        mask = out["rollout_horizon_months"] == horizon
        if str(row["target_event"]) == "irc_alert":
            out.loc[mask, "rollout_alert_probability_threshold_h"] = threshold
            out.loc[mask, "rollout_predicted_irc_alert_h"] = pd.to_numeric(
                out.loc[mask, score_column], errors="coerce"
            ) >= threshold
        elif str(row["target_event"]) == "bloom_h":
            out.loc[mask, "rollout_bloom_probability_threshold_h"] = threshold
            out.loc[mask, "rollout_predicted_bloom_h"] = pd.to_numeric(
                out.loc[mask, score_column], errors="coerce"
            ) >= threshold
    out["reference_any_alert_h"] = out["rollout_predicted_irc_alert_h"] | out["rollout_predicted_bloom_h"]
    out["predicted_alert_h"] = out["rollout_predicted_irc_alert_h"]
    return out


def _build_policy_summary(rollouts: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "rollout_horizon_months",
        "rows",
        "irc_alerts",
        "irc_alert_rate",
        "bloom_alerts",
        "bloom_alert_rate",
        "any_alerts",
        "any_alert_rate",
        "mean_alert_probability_irc",
        "mean_rollout_probability_bloom_calibrated",
    ]
    if rollouts.empty:
        return pd.DataFrame(columns=columns)
    grouped = rollouts.groupby("rollout_horizon_months", dropna=False)
    summary = grouped.agg(
        rows=("source_id", "size"),
        irc_alerts=("rollout_predicted_irc_alert_h", "sum"),
        bloom_alerts=("rollout_predicted_bloom_h", "sum"),
        any_alerts=("reference_any_alert_h", "sum"),
        mean_alert_probability_irc=("alert_probability_irc", "mean"),
        mean_rollout_probability_bloom_calibrated=("rollout_probability_bloom_calibrated", "mean"),
    ).reset_index()
    for numerator, output in [
        ("irc_alerts", "irc_alert_rate"),
        ("bloom_alerts", "bloom_alert_rate"),
        ("any_alerts", "any_alert_rate"),
    ]:
        summary[output] = summary[numerator] / summary["rows"]
    return summary[columns].sort_values("rollout_horizon_months").reset_index(drop=True)


def _build_reference_alerts(rollouts: pd.DataFrame, *, policy_name: str) -> pd.DataFrame:
    columns = [
        "rank",
        "source_id",
        "site_id",
        "split",
        "origin_year_month",
        "forecast_year_month",
        "rollout_horizon_months",
        "target_event",
        "score_name",
        "score",
        "threshold",
        "is_alert",
        "severity",
        "policy_name",
        "policy_version",
        "interpretation",
    ]
    if rollouts.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, object]] = []
    for row in rollouts.to_dict(orient="records"):
        base = {
            "source_id": row.get("source_id", ""),
            "site_id": row.get("site_id", ""),
            "split": row.get("split", ""),
            "origin_year_month": row.get("origin_year_month", ""),
            "forecast_year_month": row.get("forecast_year_month", ""),
            "rollout_horizon_months": int(row.get("rollout_horizon_months", 0)),
            "policy_name": policy_name,
            "policy_version": "pipe_grud_rollout_alert_policy_2b_v0",
        }
        rows.append(
            {
                **base,
                "target_event": "irc_alert",
                "score_name": "alert_probability_irc",
                "score": _float_or_default(row.get("alert_probability_irc"), float("nan")),
                "threshold": _float_or_default(row.get("rollout_alert_probability_threshold_h"), float("nan")),
                "is_alert": bool(row.get("rollout_predicted_irc_alert_h", False)),
                "interpretation": "2B policy threshold applied to PIPE-GRU-D IRC alert probability.",
            }
        )
        rows.append(
            {
                **base,
                "target_event": "bloom_h",
                "score_name": "rollout_probability_bloom_calibrated",
                "score": _float_or_default(row.get("rollout_probability_bloom_calibrated"), float("nan")),
                "threshold": _float_or_default(row.get("rollout_bloom_probability_threshold_h"), float("nan")),
                "is_alert": bool(row.get("rollout_predicted_bloom_h", False)),
                "interpretation": "2B policy threshold applied to rollout-calibrated bloom probability.",
            }
        )
    alerts = pd.DataFrame(rows)
    alerts = alerts[alerts["score"].notna() & alerts["threshold"].notna()].copy()
    alerts["severity"] = [
        _severity(float(score), float(threshold)) for score, threshold in zip(alerts["score"], alerts["threshold"], strict=False)
    ]
    alerts = alerts.sort_values(
        ["is_alert", "score", "rollout_horizon_months", "target_event", "source_id", "site_id"],
        ascending=[False, False, True, True, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    alerts.insert(0, "rank", np.arange(1, len(alerts) + 1))
    return alerts[columns]


def _write_reference_outputs(
    *,
    run_dir: Path,
    rollouts: pd.DataFrame,
    summary: pd.DataFrame,
    policy_summary: pd.DataFrame,
    alerts: pd.DataFrame,
    top_alerts: pd.DataFrame,
    recent_top_alerts: pd.DataFrame,
) -> tuple[Path, ...]:
    rollouts_csv = run_dir / "pipe_grud_reference_rollouts.csv"
    rollouts_parquet = run_dir / "pipe_grud_reference_rollouts.parquet"
    summary_path = run_dir / "pipe_grud_reference_rollout_summary.csv"
    policy_summary_path = run_dir / "pipe_grud_reference_policy_summary.csv"
    alerts_csv = run_dir / "pipe_grud_reference_alerts.csv"
    alerts_parquet = run_dir / "pipe_grud_reference_alerts.parquet"
    top_alerts_path = run_dir / "pipe_grud_reference_top_alerts.csv"
    recent_top_alerts_path = run_dir / "pipe_grud_reference_recent_top_alerts.csv"
    rollouts.to_csv(rollouts_csv, index=False)
    rollouts.to_parquet(rollouts_parquet, index=False)
    summary.to_csv(summary_path, index=False)
    policy_summary.to_csv(policy_summary_path, index=False)
    alerts.to_csv(alerts_csv, index=False)
    alerts.to_parquet(alerts_parquet, index=False)
    top_alerts.to_csv(top_alerts_path, index=False)
    recent_top_alerts.to_csv(recent_top_alerts_path, index=False)
    return (
        rollouts_csv,
        rollouts_parquet,
        summary_path,
        policy_summary_path,
        alerts_csv,
        alerts_parquet,
        top_alerts_path,
        recent_top_alerts_path,
    )


def _empty_reference_rollouts() -> pd.DataFrame:
    out = _empty_rollouts()
    out["reference_profile"] = pd.Series(dtype="object")
    out["rollout_probability_bloom_calibrated"] = pd.Series(dtype="float64")
    out["rollout_bloom_calibrator_method"] = pd.Series(dtype="object")
    out["alert_policy_name"] = pd.Series(dtype="object")
    out["rollout_alert_probability_threshold_h"] = pd.Series(dtype="float64")
    out["rollout_predicted_irc_alert_h"] = pd.Series(dtype="bool")
    out["rollout_bloom_probability_threshold_h"] = pd.Series(dtype="float64")
    out["rollout_predicted_bloom_h"] = pd.Series(dtype="bool")
    out["reference_any_alert_h"] = pd.Series(dtype="bool")
    return out


def _threshold_coverage(thresholds: pd.DataFrame, *, horizons: list[int]) -> dict[str, object]:
    missing: list[dict[str, object]] = []
    for horizon in horizons:
        for event in sorted(_TARGET_EVENTS):
            current = thresholds[
                (thresholds["rollout_horizon_months"] == int(horizon))
                & (thresholds["target_event"].astype(str) == event)
            ]
            if current.empty:
                missing.append({"horizon": horizon, "target_event": event})
    return {"complete": len(missing) == 0 and bool(horizons), "missing": missing}


def _calibrator_coverage(
    calibrators: Mapping[int, RolloutBloomCalibratorRecord],
    *,
    horizons: list[int],
) -> dict[str, object]:
    missing = [horizon for horizon in horizons if horizon not in calibrators]
    return {"complete": len(missing) == 0 and bool(horizons), "missing_horizons": missing}


def _reference_blockers(
    *,
    row_counts: Mapping[str, int],
    readiness: Mapping[str, object],
    threshold_coverage: Mapping[str, object],
    calibrator_coverage: Mapping[str, object],
    adaptive_surface: Mapping[str, object],
) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []
    if not bool(readiness.get("adaptive_surface_ready")):
        blockers.append(
            _issue(
                "adaptive_surface_not_reference_ready",
                "The adaptive surface build did not produce a reference-ready state history.",
                {"adaptive_surface_outcome": adaptive_surface.get("outcome")},
            )
        )
    if row_counts["selected_origins"] == 0:
        blockers.append(
            _issue(
                "no_inference_origins",
                "No eligible origins were available for the model history length.",
                {"history_length": readiness.get("history_length")},
            )
        )
    if not bool(calibrator_coverage.get("complete")):
        blockers.append(
            _issue(
                "missing_bloom_calibrators",
                "One or more rollout horizons lack reviewed bloom calibrators.",
                calibrator_coverage,
            )
        )
    if not bool(threshold_coverage.get("complete")):
        blockers.append(
            _issue(
                "missing_policy_thresholds",
                "One or more rollout horizons lack reviewed 2B policy thresholds.",
                threshold_coverage,
            )
        )
    return blockers


def _reference_warnings(adaptive_surface: Mapping[str, object]) -> list[dict[str, object]]:
    warnings = [
        _issue(
            "external_domain_not_validated",
            "The reviewed reference profile is applied mechanically; skill on this external water body is not guaranteed.",
            {"reference_profile": _REFERENCE_PROFILE},
        )
    ]
    surface_warnings = adaptive_surface.get("warnings", [])
    if isinstance(surface_warnings, list):
        warnings.extend(
            cast(dict[str, object], item)
            for item in surface_warnings
            if isinstance(item, dict)
        )
    return warnings


def _reference_report(manifest: Mapping[str, object]) -> str:
    row_counts = cast(Mapping[str, object], manifest.get("row_counts", {}))
    readiness = cast(Mapping[str, object], manifest.get("readiness", {}))
    blockers = _issue_lines(manifest.get("blockers", []))
    warnings = _issue_lines(manifest.get("warnings", []))
    return "\n".join(
        [
            "# External PIPE-GRU-D Reference-Profile Inference",
            "",
            f"- adapter: `{manifest['adapter']}`",
            f"- execution mode: `{manifest['execution_mode']}`",
            f"- inference version: `{manifest['inference_version']}`",
            f"- reference profile: `{manifest['reference_profile']}`",
            f"- policy name: `{manifest['policy_name']}`",
            f"- outcome: `{manifest['outcome']}`",
            f"- dataset id: `{manifest['dataset_id']}`",
            f"- plan id: `{manifest['plan_id']}`",
            "",
            "## Readiness",
            "",
            *[f"- {key}: {value}" for key, value in sorted(readiness.items())],
            "",
            "## Row Counts",
            "",
            *[f"- {key}: {value}" for key, value in sorted(row_counts.items())],
            "",
            "## Blockers",
            "",
            *(blockers or ["- none"]),
            "",
            "## Warnings",
            "",
            *(warnings or ["- none"]),
            "",
            "## Interpretation",
            "",
            "- The uploaded dataset was transformed through the adaptive ANFIS reference surface before PIPE-GRU-D rollout.",
            "- Bloom probabilities use the reviewed rollout calibrators.",
            "- Alert flags use the selected 2B policy thresholds.",
            "- These results are model-derived indicators, not official advisories or causal field evidence.",
            "",
        ]
    )


def _directory_record(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": path.as_posix(), "type": "directory", "available": False}
    digest = hashlib.sha256()
    files: list[dict[str, object]] = []
    total_bytes = 0
    for file_path in sorted(item for item in path.rglob("*") if item.is_file() and not item.name.endswith(".tmp")):
        file_hash = _sha256_file(file_path)
        relative_path = file_path.relative_to(path).as_posix()
        file_bytes = file_path.stat().st_size
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
        total_bytes += file_bytes
        files.append(
            {
                "path": file_path.as_posix(),
                "relative_path": relative_path,
                "bytes": file_bytes,
                "sha256": file_hash,
            }
        )
    return {
        "path": path.as_posix(),
        "type": "directory",
        "available": True,
        "bytes": total_bytes,
        "sha256": digest.hexdigest(),
        "files": files,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _policy_name(parameters: Mapping[str, object]) -> str:
    value = str(parameters.get("policy_name", _DEFAULT_POLICY_NAME)).strip()
    return value or _DEFAULT_POLICY_NAME


def _severity(score: float, threshold: float) -> str:
    if score >= threshold:
        return "alert"
    if score >= max(0.0, threshold * 0.66):
        return "watch"
    return "low"


def _clip01(values: object) -> np.ndarray:
    return np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0)


def _float_or_default(value: object, default: float) -> float:
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return default


def _int_or_default(value: object, default: int) -> int:
    try:
        return int(cast(Any, value))
    except (TypeError, ValueError):
        return default


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
