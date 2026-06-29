"""Run explicit expert-surface PIPE-GRU-D inference for API datasets."""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from src.api.schemas.run import RunPlanResponse
from src.api.services.pipe_grud_external_sequences import (
    EXTERNAL_PIPE_STATE_SURFACE_VERSION,
    build_external_pipe_sequence_artifacts,
)
from src.experiments.build_pipe_sequences import INPUT_COLUMNS, PIPE_STATE_COLUMNS
from src.experiments.rollout_pipe_grud import (
    ROLLOUT_VERSION,
    _load_model,
    _require_torch,
    alert_band,
    build_recent_top_alerts,
    build_summary,
    build_top_alerts,
    compute_irc,
    rollout_batch,
)

EXTERNAL_PIPE_GRUD_INFERENCE_VERSION = "external_pipe_grud_expert_surface_inference_v0"
_REFERENCE_PROFILE = "adaptive_wqp_focused"
_DEFAULT_ROLLOUT_HORIZON = 3
_DEFAULT_BATCH_SIZE = 256
_DEFAULT_MAX_ORIGINS = 0
_DEFAULT_RANDOM_SEED = 1729
_DEFAULT_TOP_N = 100
_DEFAULT_RECENT_MONTHS = 24
_DEFAULT_IRC_ALPHA = 0.5
_DEFAULT_IRC_BETA = 0.5
_DEFAULT_IRC_GAMMA = 2.0
_DEFAULT_IRC_ALERT_THRESHOLD = 0.5
_DEFAULT_ALERT_PROB_THRESHOLD = 0.5
_REFERENCE_MODEL = Path("models/pipe_grud/adaptive_wqp_focused/pipe_grud_model.pt")
_REFERENCE_MODEL_MANIFEST = Path("reports/pipe_grud/adaptive_wqp_focused/pipe_grud_manifest.json")


@dataclass(frozen=True)
class PipeGrudExternalInferenceResult:
    """Artifacts and manifest payload emitted by expert-surface inference."""

    manifest: dict[str, object]
    row_counts: dict[str, int]
    output_paths: tuple[Path, ...]


def run_external_pipe_grud_expert_surface_inference(
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
) -> PipeGrudExternalInferenceResult:
    """Build external sequences and run explicitly limited expert-surface rollouts."""

    model_path = _REFERENCE_MODEL
    model_manifest_path = _REFERENCE_MODEL_MANIFEST
    torch = _require_torch()
    device = torch.device("cpu")
    model, model_config, model_payload, blend_weights = _load_model(model_path, device)
    history_length = int(model_config["history_length"])
    sequence_parameters = dict(parameters)
    sequence_parameters["history_length"] = history_length
    sequence_build = build_external_pipe_sequence_artifacts(
        dataset_id=dataset_id,
        plan=plan,
        run_dir=run_dir,
        workspace=workspace,
        execution_id=execution_id,
        adapter_id=adapter_id,
        adapter_interface_version=adapter_interface_version,
        started_at=started_at,
        parameters=sequence_parameters,
    )

    state_surface = pd.read_parquet(run_dir / "pipe_state_surface.parquet")
    origins = pd.read_parquet(run_dir / "pipe_inference_origins.parquet")
    args = _inference_args(parameters)
    x_windows, selected_origins = _select_external_windows(
        state_surface,
        origins,
        history_length=history_length,
        scope=args.scope,
        max_origins=args.max_origins,
    )

    if len(selected_origins) == 0:
        rollouts = _empty_rollouts()
        summary = pd.DataFrame()
        top_alerts = pd.DataFrame()
        recent_top_alerts = pd.DataFrame()
    else:
        rollouts = _run_rollouts(
            x_windows=x_windows,
            selected_origins=selected_origins,
            model=model,
            blend_weights=blend_weights,
            args=args,
            history_length=history_length,
            device=device,
        )
        summary = build_summary(rollouts)
        top_alerts = build_top_alerts(rollouts, args.top_n)
        recent_top_alerts = build_recent_top_alerts(
            rollouts,
            top_n=args.top_n,
            recent_months=args.recent_months,
        )

    output_paths = _write_inference_outputs(
        run_dir=run_dir,
        rollouts=rollouts,
        summary=summary,
        top_alerts=top_alerts,
        recent_top_alerts=recent_top_alerts,
    )
    row_counts = {
        **{f"sequence_build_{key}": value for key, value in sequence_build.row_counts.items()},
        "selected_origins": int(len(selected_origins)),
        "rollout_rows": int(len(rollouts)),
        "summary_rows": int(len(summary)),
        "top_alert_rows": int(len(top_alerts)),
        "recent_top_alert_rows": int(len(recent_top_alerts)),
        "generated_reports": 2,
    }
    readiness = {
        "surface_contract": EXTERNAL_PIPE_STATE_SURFACE_VERSION,
        "reference_profile": _REFERENCE_PROFILE,
        "state_surface_matches_reference_profile": False,
        "reference_model_loaded": True,
        "reference_bloom_calibrators_applied": False,
        "rollout_generated": len(rollouts) > 0,
        "ready_for_reference_inference": False,
        "history_length": history_length,
        "rollout_horizon": args.rollout_horizon,
    }
    blockers = _inference_blockers(row_counts=row_counts, readiness=readiness)
    warnings = _inference_warnings()
    manifest: dict[str, object] = {
        "execution_id": execution_id,
        "plan_id": plan.plan_id,
        "dataset_id": dataset_id,
        "workflow": plan.workflow,
        "adapter": adapter_id,
        "adapter_interface_version": adapter_interface_version,
        "status": "completed",
        "execution_mode": "infer_expert_surface",
        "inference_version": EXTERNAL_PIPE_GRUD_INFERENCE_VERSION,
        "rollout_version": ROLLOUT_VERSION,
        "reference_profile": _REFERENCE_PROFILE,
        "surface_contract": EXTERNAL_PIPE_STATE_SURFACE_VERSION,
        "outcome": "completed_with_limitations" if len(rollouts) else "not_ready",
        "started_at": started_at,
        "completed_at": _now_utc(),
        "parameters": _serializable_args(args),
        "row_counts": row_counts,
        "readiness": readiness,
        "blockers": blockers,
        "warnings": warnings,
        "model": _file_record(model_path, workspace=Path(".")),
        "model_manifest": _file_record(model_manifest_path, workspace=Path(".")) if model_manifest_path.exists() else None,
        "sequence_build": {
            "build_version": sequence_build.manifest.get("build_version"),
            "outcome": sequence_build.manifest.get("outcome"),
            "readiness": sequence_build.manifest.get("readiness", {}),
            "manifest": "pipe_sequence_build_manifest.json",
        },
        "limitations": [
            "This mode runs the reviewed PIPE-GRU-D model on an external expert-fuzzy state surface.",
            "The reviewed model was selected on adaptive WQP-focused state sequences, so this is diagnostic expert-surface inference, not reference-profile inference.",
            "Reference bloom calibrators and 2B policy thresholds are not applied to this surface.",
        ],
        "artifacts": [_file_record(path, workspace=workspace) for path in (*sequence_build.output_paths, *output_paths)],
    }
    report_path = run_dir / "pipe_grud_external_inference_report.md"
    manifest_path = run_dir / "pipe_grud_external_inference_manifest.json"
    _write_text(report_path, _inference_report(manifest))
    _write_json(manifest_path, manifest)
    output_paths = (*sequence_build.output_paths, *output_paths, report_path, manifest_path)
    manifest["artifacts"] = [_file_record(path, workspace=workspace) for path in output_paths]
    _write_json(manifest_path, manifest)
    return PipeGrudExternalInferenceResult(
        manifest=manifest,
        row_counts=row_counts,
        output_paths=output_paths,
    )


def _inference_args(parameters: Mapping[str, object]) -> Namespace:
    deterministic = _bool_parameter(parameters, "deterministic", True)
    return Namespace(
        scope=str(parameters.get("scope", "latest-sites")),
        max_origins=_optional_int_parameter(parameters, "max_origins", _DEFAULT_MAX_ORIGINS),
        rollout_horizon=_int_parameter(parameters, "rollout_horizon", _DEFAULT_ROLLOUT_HORIZON),
        deterministic=deterministic,
        samples=1 if deterministic else _int_parameter(parameters, "samples", 128),
        batch_size=_int_parameter(parameters, "batch_size", _DEFAULT_BATCH_SIZE),
        random_seed=_int_parameter(parameters, "random_seed", _DEFAULT_RANDOM_SEED),
        irc_alpha=_float_parameter(parameters, "irc_alpha", _DEFAULT_IRC_ALPHA),
        irc_beta=_float_parameter(parameters, "irc_beta", _DEFAULT_IRC_BETA),
        irc_gamma=_float_parameter(parameters, "irc_gamma", _DEFAULT_IRC_GAMMA),
        irc_alert_threshold=_float_parameter(parameters, "irc_alert_threshold", _DEFAULT_IRC_ALERT_THRESHOLD),
        alert_prob_threshold=_float_parameter(parameters, "alert_prob_threshold", _DEFAULT_ALERT_PROB_THRESHOLD),
        top_n=_int_parameter(parameters, "top_n", _DEFAULT_TOP_N),
        recent_months=_int_parameter(parameters, "recent_months", _DEFAULT_RECENT_MONTHS),
    )


def _select_external_windows(
    state_surface: pd.DataFrame,
    origins: pd.DataFrame,
    *,
    history_length: int,
    scope: str,
    max_origins: int | None,
) -> tuple[np.ndarray, pd.DataFrame]:
    if origins.empty:
        return np.empty((0, history_length, len(INPUT_COLUMNS)), dtype="float32"), origins
    selected = origins.copy()
    selected["_origin_period"] = pd.PeriodIndex(selected["origin_year_month"].astype(str), freq="M").asi8
    selected = selected.sort_values(["_origin_period", "source_id", "site_id"], ascending=[False, True, True])
    if scope == "latest-sites":
        selected = selected.drop_duplicates(["source_id", "site_id"], keep="first")
    elif scope != "all-eligible":
        raise ValueError("scope must be 'latest-sites' or 'all-eligible'")
    if max_origins is not None:
        selected = selected.head(max_origins)
    selected = selected.sort_values(["source_id", "site_id", "_origin_period"]).reset_index(drop=True)

    working = state_surface.copy()
    working["period_ord"] = pd.PeriodIndex(working["year_month"].astype(str), freq="M").asi8
    working = working.sort_values(["source_id", "site_id", "period_ord"]).reset_index(drop=True)
    windows: list[np.ndarray] = []
    kept_rows: list[dict[str, object]] = []
    for row in selected.to_dict(orient="records"):
        site_rows = working[
            (working["source_id"].astype(str) == str(row["source_id"]))
            & (working["site_id"].astype(str) == str(row["site_id"]))
        ].reset_index(drop=True)
        matches = site_rows.index[site_rows["year_month"].astype(str) == str(row["origin_year_month"])].to_list()
        if not matches:
            continue
        end_index = int(matches[-1])
        start_index = end_index - history_length + 1
        if start_index < 0:
            continue
        window = site_rows.iloc[start_index : end_index + 1].copy()
        if len(window) != history_length:
            continue
        periods = window["period_ord"].astype("int64").to_list()
        if not all((right - left) == 1 for left, right in zip(periods, periods[1:], strict=False)):
            continue
        windows.append(_window_features(window))
        kept_rows.append(row)
    kept = pd.DataFrame(kept_rows)
    if not windows:
        return np.empty((0, history_length, len(INPUT_COLUMNS)), dtype="float32"), kept
    return np.stack(windows).astype("float32"), kept


def _window_features(window: pd.DataFrame) -> np.ndarray:
    state_values = window[PIPE_STATE_COLUMNS].to_numpy(dtype="float32")
    month = window["year_month"].astype(str).str.slice(5, 7).astype("float32").to_numpy()
    radians = 2.0 * np.pi * (month - 1.0) / 12.0
    season = np.column_stack(
        [
            np.sin(radians),
            np.cos(radians),
            np.sin(2.0 * radians),
            np.cos(2.0 * radians),
        ]
    ).astype("float32")
    return np.column_stack([state_values, season]).astype("float32")


def _run_rollouts(
    *,
    x_windows: np.ndarray,
    selected_origins: pd.DataFrame,
    model: Any,
    blend_weights: Any | None,
    args: Namespace,
    history_length: int,
    device: Any,
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
            calibrators={},
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
    rollouts = pd.concat(parts, ignore_index=True) if parts else _empty_rollouts()
    rollouts.insert(0, "rollout_version", EXTERNAL_PIPE_GRUD_INFERENCE_VERSION)
    rollouts["surface_contract"] = EXTERNAL_PIPE_STATE_SURFACE_VERSION
    rollouts["deterministic"] = bool(args.deterministic)
    rollouts["predicted_alert_h"] = rollouts["alert_probability_irc"] >= args.alert_prob_threshold
    rollouts["alert_band"] = alert_band(rollouts["alert_probability_irc"])
    return rollouts


def _write_inference_outputs(
    *,
    run_dir: Path,
    rollouts: pd.DataFrame,
    summary: pd.DataFrame,
    top_alerts: pd.DataFrame,
    recent_top_alerts: pd.DataFrame,
) -> tuple[Path, ...]:
    rollouts_csv = run_dir / "pipe_grud_external_rollouts.csv"
    rollouts_parquet = run_dir / "pipe_grud_external_rollouts.parquet"
    summary_path = run_dir / "pipe_grud_external_rollout_summary.csv"
    top_alerts_path = run_dir / "pipe_grud_external_top_alerts.csv"
    recent_top_alerts_path = run_dir / "pipe_grud_external_recent_top_alerts.csv"
    rollouts.to_csv(rollouts_csv, index=False)
    rollouts.to_parquet(rollouts_parquet, index=False)
    summary.to_csv(summary_path, index=False)
    top_alerts.to_csv(top_alerts_path, index=False)
    recent_top_alerts.to_csv(recent_top_alerts_path, index=False)
    return (rollouts_csv, rollouts_parquet, summary_path, top_alerts_path, recent_top_alerts_path)


def _inference_blockers(*, row_counts: Mapping[str, int], readiness: Mapping[str, object]) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = [
        _issue(
            "adaptive_reference_surface_not_available",
            "External inference used an expert-fuzzy surface, not the reviewed adaptive WQP-focused surface.",
            {
                "surface_contract": readiness.get("surface_contract"),
                "reference_profile": readiness.get("reference_profile"),
            },
        )
    ]
    if row_counts["selected_origins"] == 0:
        blockers.append(
            _issue(
                "no_inference_origins",
                "No eligible origins were available for the model history length.",
                {"history_length": readiness.get("history_length")},
            )
        )
    return blockers


def _inference_warnings() -> list[dict[str, object]]:
    return [
        _issue(
            "expert_surface_inference_not_reference_calibrated",
            "Outputs are diagnostic model rollouts over an expert-fuzzy surface; do not interpret them as calibrated reference-profile alerts.",
        )
    ]


def _inference_report(manifest: Mapping[str, object]) -> str:
    row_counts = cast(Mapping[str, object], manifest.get("row_counts", {}))
    readiness = cast(Mapping[str, object], manifest.get("readiness", {}))
    blockers = _issue_lines(manifest.get("blockers", []))
    warnings = _issue_lines(manifest.get("warnings", []))
    return "\n".join(
        [
            "# External PIPE-GRU-D Expert-Surface Inference",
            "",
            f"- adapter: `{manifest['adapter']}`",
            f"- execution mode: `{manifest['execution_mode']}`",
            f"- inference version: `{manifest['inference_version']}`",
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
            "- These rollouts are diagnostic expert-surface inference.",
            "- They are not reference-profile calibrated alerts.",
            "- Bloom calibrators and 2B policy thresholds are intentionally not applied.",
            "",
        ]
    )


def _empty_rollouts() -> pd.DataFrame:
    columns = [
        "rollout_version",
        "source_id",
        "site_id",
        "split",
        "origin_year_month",
        "origin_irc1_rollout_basis",
        *[f"origin_{column}" for column in PIPE_STATE_COLUMNS],
        "forecast_year_month",
        "rollout_horizon_months",
        "samples",
        "irc_mean",
        "irc_p05",
        "irc_p50",
        "irc_p95",
        "alert_irc_threshold",
        "alert_probability_irc",
        "alert_probability_threshold",
        "probability_bloom_mean",
        "probability_bloom_p05",
        "probability_bloom_p50",
        "probability_bloom_p95",
        "bloom_probability_threshold_h",
        "predicted_bloom_alert_h",
        *[f"{column}_mean" for column in PIPE_STATE_COLUMNS],
        *[f"{column}_p05" for column in PIPE_STATE_COLUMNS],
        *[f"{column}_p95" for column in PIPE_STATE_COLUMNS],
        "surface_contract",
        "deterministic",
        "predicted_alert_h",
        "alert_band",
    ]
    return pd.DataFrame(columns=columns)


def _serializable_args(args: Namespace) -> dict[str, object]:
    return {
        "scope": args.scope,
        "max_origins": args.max_origins,
        "rollout_horizon": args.rollout_horizon,
        "deterministic": args.deterministic,
        "samples": args.samples,
        "batch_size": args.batch_size,
        "random_seed": args.random_seed,
        "irc_alpha": args.irc_alpha,
        "irc_beta": args.irc_beta,
        "irc_gamma": args.irc_gamma,
        "irc_alert_threshold": args.irc_alert_threshold,
        "alert_prob_threshold": args.alert_prob_threshold,
        "top_n": args.top_n,
        "recent_months": args.recent_months,
    }


def _issue_lines(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for item in value:
        if isinstance(item, dict):
            issue = cast(Mapping[str, object], item)
            lines.append(f"- {issue.get('code', 'unknown')}: {issue.get('message', '')}")
    return lines


def _issue(code: str, message: str, details: Mapping[str, object] | None = None) -> dict[str, object]:
    return {"code": code, "message": message, "details": dict(details or {})}


def _int_parameter(parameters: Mapping[str, object], key: str, default: int) -> int:
    value = parameters.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        parsed = int(value)
        if parsed > 0:
            return parsed
    return default


def _optional_int_parameter(parameters: Mapping[str, object], key: str, default: int) -> int | None:
    value = _int_parameter(parameters, key, default)
    return None if value <= 0 else value


def _float_parameter(parameters: Mapping[str, object], key: str, default: float) -> float:
    value = parameters.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        return float(value)
    return default


def _bool_parameter(parameters: Mapping[str, object], key: str, default: bool) -> bool:
    value = parameters.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return default


def _file_record(path: Path, *, workspace: Path) -> dict[str, object]:
    resolved = path.resolve()
    try:
        display_path = resolved.relative_to(workspace.resolve()).as_posix()
    except ValueError:
        display_path = path.as_posix()
    return {
        "path": display_path,
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
