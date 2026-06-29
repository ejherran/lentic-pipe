"""Run MIFAL-ED/T2 observable workflows for API datasets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from src.api.schemas.run import RunPlanResponse
from src.api.services.dataset_repository import read_dataset_request
from src.api.services.dataset_validation import load_canonical_variables
from src.api.services.run_executor import _canonical_rows, _qc_score
from src.mifal.ed_t2 import MIFALEDT2
from src.mifal.panel_adapter import (
    MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA,
    MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA,
    PANEL_ADAPTER_COLUMNS,
    add_previous_chla_columns,
    panel_row_to_mifal_payload,
    payload_availability,
    validate_surface,
)

EXTERNAL_MIFAL_OBSERVABLE_VERSION = "external_mifal_observable_api_v0"
_DEFAULT_HORIZONS = (1, 2, 3)
_DAYS_PER_MONTH = 30.4375
_KEY_COLUMNS = ["source_id", "site_id", "year_month"]
_MIFAL_VARIABLES = {
    "temperature_C": "temperature_C",
    "TP_ugL": "TP_ugL",
    "TN_ugL": "TN_ugL",
    "secchi_depth_m": "secchi_depth_m",
    "turbidity_NTU": "turbidity_NTU",
    "DO_mgL": "DO_mgL",
    "chlorophyll_a_ugL": "chlorophyll_a_ugL",
}
_CALIBRATION_DIR_BY_SURFACE = {
    MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA: Path(
        "models/mifal/observable_calibrators/current_chla_pipe_grud_validation"
    ),
    MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA: Path(
        "models/mifal/observable_calibrators/no_current_chla_pipe_grud_validation"
    ),
}
_THRESHOLDS_BY_SURFACE = {
    MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA: Path(
        "reports/mifal/mifal_observable_current_chla_pipe_grud_validation_calibration_thresholds.csv"
    ),
    MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA: Path(
        "reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_calibration_thresholds.csv"
    ),
}


@dataclass(frozen=True)
class MifalExternalRunResult:
    """Artifacts and manifest payload emitted by the API MIFAL runner."""

    manifest: dict[str, object]
    row_counts: dict[str, int]
    output_paths: tuple[Path, ...]


def mifal_reference_artifacts_available(surface: str) -> tuple[bool, list[str]]:
    """Return availability for reviewed MIFAL calibration artifacts."""

    surface = validate_surface(surface)
    missing: list[str] = []
    calibrator_dir = _CALIBRATION_DIR_BY_SURFACE[surface]
    if not calibrator_dir.exists():
        missing.append("mifal_observable_calibrator_dir")
    for horizon in _DEFAULT_HORIZONS:
        if not _calibrator_path(surface, horizon).exists():
            missing.append(f"mifal_observable_bloom_calibrator_h{horizon}")
    if not _THRESHOLDS_BY_SURFACE[surface].exists():
        missing.append("mifal_observable_alert_thresholds")
    return len(missing) == 0, missing


def run_external_mifal_observable(
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
) -> MifalExternalRunResult:
    """Run deterministic MIFAL-ED/T2 observable scoring on an API dataset."""

    surface = _surface_parameter(parameters)
    horizons = _horizons_parameter(parameters)
    include_voi = _bool_parameter(parameters, "include_voi", False)
    max_origins = _optional_positive_int(parameters.get("max_origins"))

    request = read_dataset_request(dataset_id, workspace=workspace)
    variables = load_canonical_variables()
    canonical_rows = _canonical_rows(request.observations, variables)
    panel = _mifal_panel_frame(canonical_rows)
    observable_surface = add_previous_chla_columns(panel)
    if max_origins is not None:
        observable_surface = observable_surface.head(max_origins).copy()

    scores = _run_scores(observable_surface, surface=surface, horizons=horizons, include_voi=include_voi)
    scores, calibration_status = _apply_calibration(scores, surface=surface, horizons=horizons)
    alerts = _build_alerts(scores, calibration_status=calibration_status)

    output_paths = _write_outputs(
        run_dir=run_dir,
        canonical_rows=canonical_rows,
        panel=panel,
        observable_surface=observable_surface,
        scores=scores,
        alerts=alerts,
    )
    row_counts = {
        "canonical_observations": len(canonical_rows),
        "monthly_panel": int(len(panel)),
        "mifal_observable_surface": int(len(observable_surface)),
        "mifal_scores": int(len(scores)),
        "mifal_alerts": int(len(alerts)),
        "calibrated_score_rows": int(scores["mifal_probability_bloom_calibrated"].notna().sum())
        if "mifal_probability_bloom_calibrated" in scores
        else 0,
        "generated_reports": 2,
    }
    calibrator_items = _calibration_status_items(calibration_status, "calibrators")
    threshold_items = _calibration_status_items(calibration_status, "thresholds")
    readiness = {
        "surface": surface,
        "horizons": horizons,
        "observable_surface_rows": int(len(observable_surface)),
        "calibrators_complete": all(bool(item.get("available")) for item in calibrator_items),
        "thresholds_complete": all(bool(item.get("available")) for item in threshold_items),
        "alerts_thresholded": int(len(alerts)) > 0,
        "ready_for_mifal_scoring": int(len(scores)) > 0,
    }
    warnings = _warnings(calibration_status=calibration_status, scores=scores)
    manifest: dict[str, object] = {
        "execution_id": execution_id,
        "plan_id": plan.plan_id,
        "dataset_id": dataset_id,
        "workflow": plan.workflow,
        "adapter": adapter_id,
        "adapter_interface_version": adapter_interface_version,
        "status": "completed",
        "execution_mode": "run_observable",
        "mifal_observable_version": EXTERNAL_MIFAL_OBSERVABLE_VERSION,
        "surface": surface,
        "outcome": "completed_with_calibrated_alerts"
        if readiness["alerts_thresholded"]
        else "completed_without_calibrated_alerts",
        "started_at": started_at,
        "completed_at": _now_utc(),
        "parameters": {
            "surface": surface,
            "horizons": horizons,
            "include_voi": include_voi,
            "max_origins": max_origins,
        },
        "row_counts": row_counts,
        "readiness": readiness,
        "warnings": warnings,
        "calibration": calibration_status,
        "planner": {
            "plan_id": plan.plan_id,
            "status": str(plan.status),
            "executable": plan.executable,
            "blockers": [issue.model_dump(mode="json") for issue in plan.blockers],
            "warnings": [issue.model_dump(mode="json") for issue in plan.warnings],
        },
        "limitations": [
            "MIFAL-ED/T2 is a deterministic eco-fuzzy comparator, not a learned temporal state model.",
            "External dataset skill and calibration transferability are not guaranteed for a new water body.",
            "Calibrated alert flags target bloom_h only; this workflow does not emit irc_alert.",
            "Planning and intervention decisions should inspect readiness, warnings, and calibration coverage.",
        ],
        "artifacts": [_file_record(path, workspace=workspace) for path in output_paths],
    }
    report_path = run_dir / "mifal_run_report.md"
    manifest_path = run_dir / "mifal_run_manifest.json"
    _write_text(report_path, _report(manifest))
    _write_json(manifest_path, manifest)
    output_paths = (*output_paths, report_path, manifest_path)
    manifest["artifacts"] = [_file_record(path, workspace=workspace) for path in output_paths]
    _write_json(manifest_path, manifest)
    return MifalExternalRunResult(manifest=manifest, row_counts=row_counts, output_paths=output_paths)


def _mifal_panel_frame(canonical_rows: Sequence[Mapping[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(canonical_rows)
    if frame.empty:
        return pd.DataFrame(columns=PANEL_ADAPTER_COLUMNS)
    frame = frame[frame["year_month"].notna()].copy()
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame[frame["value"].notna()].copy()
    keys = _KEY_COLUMNS
    base = frame[keys].drop_duplicates().sort_values(keys).reset_index(drop=True)
    out = base.copy()
    for variable_name, suffix in _MIFAL_VARIABLES.items():
        subset = frame[frame["variable"].astype(str) == variable_name]
        if subset.empty:
            continue
        stats = subset.groupby(keys, as_index=False).agg(
            mean=("value", "mean"),
            count=("value", "count"),
            std=("value", "std"),
        )
        stats = stats.rename(
            columns={
                "mean": f"mean_{suffix}",
                "count": f"n_obs_{suffix}",
                "std": f"std_{suffix}",
            }
        )
        out = out.merge(stats, on=keys, how="left")

        qc = subset.copy()
        qc["qc_score"] = qc["qc_flag"].map(_qc_score)
        qc = qc[qc["qc_score"].notna()]
        if not qc.empty:
            qc_stats = (
                qc.groupby(keys, as_index=False)["qc_score"]
                .mean()
                .rename(columns={"qc_score": f"qc_ok_rate_{suffix}"})
            )
            out = out.merge(qc_stats, on=keys, how="left")

    for column in PANEL_ADAPTER_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    return out[PANEL_ADAPTER_COLUMNS].sort_values(keys).reset_index(drop=True)


def _run_scores(
    surface_frame: pd.DataFrame,
    *,
    surface: str,
    horizons: list[int],
    include_voi: bool,
) -> pd.DataFrame:
    model = MIFALEDT2()
    rows: list[dict[str, object]] = []
    for origin in surface_frame.to_dict(orient="records"):
        payload = panel_row_to_mifal_payload(origin, surface=surface)
        availability = payload_availability(payload)
        origin_year_month = str(origin.get("origin_year_month", ""))
        if not origin_year_month:
            continue
        for horizon in horizons:
            result = model.step(
                payload,
                dt_days=float(horizon) * _DAYS_PER_MONTH,
                update_state=False,
                compute_voi=include_voi,
            )
            risk_interval = cast(tuple[float, float], result["risk_interval"])
            index_scores = cast(Mapping[str, object], result.get("index_scores", {}))
            rows.append(
                {
                    "mifal_observable_version": EXTERNAL_MIFAL_OBSERVABLE_VERSION,
                    "mifal_model_version": str(result.get("model_version", "")),
                    "surface": surface,
                    "source_id": str(origin.get("source_id", "")),
                    "site_id": str(origin.get("site_id", "")),
                    "origin_year_month": origin_year_month,
                    "forecast_year_month": _forecast_month(origin_year_month, horizon),
                    "horizon_months": horizon,
                    "risk_interval_low": _clip01_float(risk_interval[0]),
                    "risk_interval_high": _clip01_float(risk_interval[1]),
                    "risk_conservative": _clip01_float(result.get("risk_conservative")),
                    "uncertainty": _clip01_float(result.get("uncertainty")),
                    "interval_confidence": _clip01_float(result.get("interval_confidence")),
                    "data_reliability": _clip01_float(result.get("data_reliability")),
                    "confidence": _clip01_float(result.get("confidence")),
                    "alert_class": str(result.get("alert_class", "")),
                    "observation_reliability": _clip01_float(result.get("observation_reliability")),
                    "recommended_sampling": str(result.get("recommended_sampling") or ""),
                    "dominant_factors": _dominant_factors(result.get("dominant_factors")),
                    **{key: bool(value) for key, value in availability.items()},
                    **{
                        f"index_{key.lower()}": _clip01_float(value)
                        for key, value in index_scores.items()
                    },
                }
            )
    if not rows:
        return _empty_scores()
    return pd.DataFrame(rows).sort_values(
        ["source_id", "site_id", "origin_year_month", "horizon_months"]
    ).reset_index(drop=True)


def _apply_calibration(
    scores: pd.DataFrame,
    *,
    surface: str,
    horizons: Sequence[int],
) -> tuple[pd.DataFrame, dict[str, object]]:
    out = scores.copy()
    out["mifal_probability_bloom_calibrated"] = np.nan
    out["mifal_bloom_probability_threshold"] = np.nan
    out["mifal_predicted_bloom_h"] = False
    calibrator_status: list[dict[str, object]] = []
    threshold_status: list[dict[str, object]] = []

    for horizon in horizons:
        calibrator_path = _calibrator_path(surface, horizon)
        if calibrator_path.exists():
            payload = json.loads(calibrator_path.read_text(encoding="utf-8"))
            mask = out["horizon_months"].astype("int64") == int(horizon)
            out.loc[mask, "mifal_probability_bloom_calibrated"] = _apply_json_calibrator(
                out.loc[mask, "risk_conservative"],
                payload,
            )
            calibrator_status.append(
                {
                    "horizon_months": int(horizon),
                    "available": True,
                    "path": calibrator_path.as_posix(),
                    "method": str(payload.get("method", "unknown")),
                    "training_rows": _int_or_zero(payload.get("training_rows")),
                    "positive_rows": _int_or_zero(payload.get("positive_rows")),
                }
            )
        else:
            calibrator_status.append(
                {
                    "horizon_months": int(horizon),
                    "available": False,
                    "path": calibrator_path.as_posix(),
                }
            )

    thresholds = _read_thresholds(surface)
    for horizon in horizons:
        row = thresholds[
            (thresholds["horizon_months"].astype("int64") == int(horizon))
            & (thresholds["target_event"].astype(str) == "bloom_h")
        ]
        if row.empty:
            threshold_status.append(
                {"horizon_months": int(horizon), "available": False, "target_event": "bloom_h"}
            )
            continue
        selected = float(row.iloc[0]["selected_threshold"])
        mask = out["horizon_months"].astype("int64") == int(horizon)
        out.loc[mask, "mifal_bloom_probability_threshold"] = selected
        out.loc[mask, "mifal_predicted_bloom_h"] = (
            pd.to_numeric(out.loc[mask, "mifal_probability_bloom_calibrated"], errors="coerce")
            >= selected
        )
        threshold_status.append(
            {
                "horizon_months": int(horizon),
                "available": True,
                "target_event": "bloom_h",
                "score_column": str(row.iloc[0]["score_column"]),
                "selected_threshold": selected,
                "selection_objective": str(row.iloc[0]["selection_objective"]),
                "calibration_split": str(row.iloc[0]["calibration_split"]),
                "path": _THRESHOLDS_BY_SURFACE[surface].as_posix(),
            }
        )

    return out, {"surface": surface, "calibrators": calibrator_status, "thresholds": threshold_status}


def _build_alerts(scores: pd.DataFrame, *, calibration_status: Mapping[str, object]) -> pd.DataFrame:
    if scores.empty:
        return _empty_alerts()
    rows = scores[scores["mifal_bloom_probability_threshold"].notna()].copy()
    if rows.empty:
        return _empty_alerts()
    rows["score"] = pd.to_numeric(rows["mifal_probability_bloom_calibrated"], errors="coerce").fillna(
        pd.to_numeric(rows["risk_conservative"], errors="coerce")
    )
    rows["threshold"] = pd.to_numeric(rows["mifal_bloom_probability_threshold"], errors="coerce")
    rows["is_alert"] = rows["score"] >= rows["threshold"]
    rows["severity"] = [
        _severity(float(score), float(threshold))
        for score, threshold in zip(rows["score"], rows["threshold"], strict=False)
    ]
    rows = rows.sort_values(
        ["is_alert", "score", "source_id", "site_id", "origin_year_month", "horizon_months"],
        ascending=[False, False, True, True, True, True],
    ).reset_index(drop=True)
    rows.insert(0, "rank", np.arange(1, len(rows) + 1))
    rows["target_event"] = "bloom_h"
    rows["score_name"] = "mifal_probability_bloom_calibrated"
    rows["policy_version"] = _mifal_policy_version(calibration_status)
    rows["interpretation"] = "MIFAL-ED/T2 calibrated bloom risk threshold indicator."
    columns = [
        "rank",
        "source_id",
        "site_id",
        "origin_year_month",
        "forecast_year_month",
        "horizon_months",
        "target_event",
        "score_name",
        "score",
        "threshold",
        "is_alert",
        "severity",
        "policy_version",
        "interpretation",
    ]
    return rows[columns].reset_index(drop=True)


def _write_outputs(
    *,
    run_dir: Path,
    canonical_rows: Sequence[Mapping[str, object]],
    panel: pd.DataFrame,
    observable_surface: pd.DataFrame,
    scores: pd.DataFrame,
    alerts: pd.DataFrame,
) -> tuple[Path, ...]:
    canonical_path = run_dir / "canonical_observations.parquet"
    panel_path = run_dir / "monthly_panel.parquet"
    surface_csv = run_dir / "mifal_observable_surface.csv"
    surface_parquet = run_dir / "mifal_observable_surface.parquet"
    scores_csv = run_dir / "mifal_scores.csv"
    scores_parquet = run_dir / "mifal_scores.parquet"
    alerts_csv = run_dir / "mifal_alerts.csv"
    alerts_parquet = run_dir / "mifal_alerts.parquet"
    pd.DataFrame(canonical_rows).to_parquet(canonical_path, index=False)
    panel.to_parquet(panel_path, index=False)
    observable_surface.to_csv(surface_csv, index=False)
    observable_surface.to_parquet(surface_parquet, index=False)
    scores.to_csv(scores_csv, index=False)
    scores.to_parquet(scores_parquet, index=False)
    alerts.to_csv(alerts_csv, index=False)
    alerts.to_parquet(alerts_parquet, index=False)
    return (
        canonical_path,
        panel_path,
        surface_csv,
        surface_parquet,
        scores_csv,
        scores_parquet,
        alerts_csv,
        alerts_parquet,
    )


def _read_thresholds(surface: str) -> pd.DataFrame:
    path = _THRESHOLDS_BY_SURFACE[surface]
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "target_event",
                "horizon_months",
                "score_column",
                "selected_threshold",
                "selection_objective",
                "calibration_split",
            ]
        )
    return pd.read_csv(path)


def _apply_json_calibrator(scores: pd.Series, payload: Mapping[str, object]) -> np.ndarray:
    values = np.clip(pd.to_numeric(scores, errors="coerce").to_numpy(dtype="float64"), 0.0, 1.0)
    if payload.get("method") == "constant":
        return np.full(len(values), float(cast(Any, payload["constant_probability"])), dtype="float64")
    x_thresholds = np.asarray(payload["x_thresholds"], dtype="float64")
    y_thresholds = np.asarray(payload["y_thresholds"], dtype="float64")
    return np.interp(values, x_thresholds, y_thresholds, left=y_thresholds[0], right=y_thresholds[-1])


def _surface_parameter(parameters: Mapping[str, object]) -> str:
    raw = parameters.get("surface", MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA)
    return validate_surface(str(raw))


def _horizons_parameter(parameters: Mapping[str, object]) -> list[int]:
    raw = parameters.get("horizons")
    if raw is None:
        rollout_horizon = _optional_positive_int(parameters.get("rollout_horizon"))
        if rollout_horizon is not None:
            return list(range(1, rollout_horizon + 1))
        return list(_DEFAULT_HORIZONS)
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("parameters.horizons must be a list of positive integers.")
    horizons = sorted({_int_parameter_value(value) for value in raw})
    if not horizons or min(horizons) < 1:
        raise ValueError("parameters.horizons must contain positive integers.")
    return horizons


def _optional_positive_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    parsed = _int_parameter_value(value)
    if parsed < 1:
        raise ValueError("Expected a positive integer parameter.")
    return parsed


def _int_parameter_value(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Expected an integer parameter, not a boolean.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise ValueError("Expected an integer-compatible parameter.")


def _bool_parameter(parameters: Mapping[str, object], name: str, default: bool) -> bool:
    value = parameters.get(name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _calibrator_path(surface: str, horizon: int) -> Path:
    return _CALIBRATION_DIR_BY_SURFACE[surface] / f"{surface}_h{int(horizon)}_bloom_h_calibrator.json"


def _forecast_month(origin_year_month: str, horizon: int) -> str:
    period = cast(Any, pd.Period(origin_year_month, freq="M"))
    return str(period + int(horizon))


def _clip01_float(value: object) -> float:
    try:
        numeric = float(cast(Any, value))
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(numeric):
        return float("nan")
    return min(1.0, max(0.0, numeric))


def _dominant_factors(value: object) -> str:
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value[:3]:
        if isinstance(item, tuple | list) and len(item) >= 2:
            parts.append(f"{item[0]}={_clip01_float(item[1]):.4f}")
    return ";".join(parts)


def _severity(score: float, threshold: float) -> str:
    if score >= threshold:
        return "alert"
    if score >= max(0.0, threshold * 0.66):
        return "watch"
    return "low"


def _mifal_policy_version(calibration_status: Mapping[str, object]) -> str:
    for item in _calibration_status_items(calibration_status, "thresholds"):
        if bool(item.get("available")):
            objective = str(item.get("selection_objective", "threshold"))
            split = str(item.get("calibration_split", "validation"))
            return f"mifal_observable_alert_calibration_v0:{split}:{objective}"
    return "mifal_observable_unthresholded"


def _warnings(*, calibration_status: Mapping[str, object], scores: pd.DataFrame) -> list[dict[str, object]]:
    warnings = [
        _issue(
            "external_domain_not_validated",
            "MIFAL calibration transferability is not guaranteed for this external water body.",
        )
    ]
    if scores.empty:
        warnings.append(_issue("no_mifal_scores", "No MIFAL score rows were produced."))
    calibrators = _calibration_status_items(calibration_status, "calibrators")
    thresholds = _calibration_status_items(calibration_status, "thresholds")
    if any(not bool(item.get("available")) for item in calibrators):
        warnings.append(_issue("missing_mifal_calibrators", "Some requested horizons lack MIFAL bloom calibrators."))
    if any(not bool(item.get("available")) for item in thresholds):
        warnings.append(_issue("missing_mifal_thresholds", "Some requested horizons lack MIFAL bloom thresholds."))
    return warnings


def _calibration_status_items(
    calibration_status: Mapping[str, object],
    key: str,
) -> list[Mapping[str, object]]:
    value = calibration_status.get(key, [])
    if not isinstance(value, list):
        return []
    return [cast(Mapping[str, object], item) for item in value if isinstance(item, Mapping)]


def _issue(code: str, message: str, details: Mapping[str, object] | None = None) -> dict[str, object]:
    return {"code": code, "message": message, "details": dict(details or {})}


def _empty_scores() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "mifal_observable_version",
            "mifal_model_version",
            "surface",
            "source_id",
            "site_id",
            "origin_year_month",
            "forecast_year_month",
            "horizon_months",
            "risk_conservative",
        ]
    )


def _empty_alerts() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "rank",
            "source_id",
            "site_id",
            "origin_year_month",
            "forecast_year_month",
            "horizon_months",
            "target_event",
            "score_name",
            "score",
            "threshold",
            "is_alert",
            "severity",
            "policy_version",
            "interpretation",
        ]
    )


def _report(manifest: Mapping[str, object]) -> str:
    row_counts = cast(Mapping[str, object], manifest.get("row_counts", {}))
    readiness = cast(Mapping[str, object], manifest.get("readiness", {}))
    warnings = _issue_lines(manifest.get("warnings", []))
    limitations_obj = manifest.get("limitations", [])
    limitations = [str(item) for item in cast(list[object], limitations_obj)] if isinstance(limitations_obj, list) else []
    return "\n".join(
        [
            "# External MIFAL-ED/T2 Observable Run",
            "",
            f"- adapter: `{manifest['adapter']}`",
            f"- execution mode: `{manifest['execution_mode']}`",
            f"- MIFAL observable version: `{manifest['mifal_observable_version']}`",
            f"- surface: `{manifest['surface']}`",
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
            "## Warnings",
            "",
            *(warnings or ["- none"]),
            "",
            "## Interpretation",
            "",
            *[f"- {item}" for item in limitations],
            "",
        ]
    )


def _issue_lines(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            issue = cast(Mapping[str, object], item)
            lines.append(f"- {issue.get('code', 'unknown')}: {issue.get('message', '')}")
    return lines


def _file_record(path: Path, *, workspace: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {
        "path": path.relative_to(workspace).as_posix(),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _json_default(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _int_or_zero(value: object) -> int:
    try:
        return int(cast(Any, value))
    except (TypeError, ValueError):
        return 0


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
