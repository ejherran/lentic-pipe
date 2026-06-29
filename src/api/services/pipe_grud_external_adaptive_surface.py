"""Build adaptive ANFIS PIPE state artifacts for external API datasets."""

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
from src.api.services.dataset_repository import read_dataset_request
from src.api.services.dataset_validation import load_canonical_variables
from src.api.services.pipe_grud_external_sequences import (
    _eligible_inference_origins,
    _filter_external_sequences,
)
from src.api.services.run_executor import (
    _canonical_rows,
    _monthly_panel_rows,
    _wide_panel_frame,
)
from src.experiments.build_adaptive_anfis_state import adaptive_state_from_predictions
from src.experiments.build_pipe_sequences import (
    ADAPTIVE_STATE_MAPPING,
    INPUT_COLUMNS,
    OPTIONAL_CONTEXT_COLUMNS,
    PIPE_STATE_COLUMNS,
    SEASON_COLUMNS,
    TARGET_COLUMNS,
    build_sequence_candidates,
    summarize_discarded,
    summarize_sequences,
)
from src.experiments.run_adaptive_anfis_real_smoke import (
    MODULE_SPECS,
    add_module_features,
)
from src.fuzzy.adaptive_anfis import _require_torch, make_adaptive_anfis

EXTERNAL_PIPE_ADAPTIVE_SURFACE_VERSION = "external_adaptive_anfis_pipe_state_surface_v0"
_REFERENCE_PROFILE = "adaptive_wqp_focused"
_DEFAULT_HISTORY_LENGTH = 12
_DEFAULT_MAX_GAP_MONTHS = 1
_DEFAULT_PREDICT_BATCH_ROWS = 32768
_DEFAULT_MODELS_DIR = Path("models/anfis/adaptive")
_DEFAULT_MANIFEST = Path("reports/anfis/adaptive_anfis_state_manifest.json")
_MODULE_CHECKPOINTS = {
    "ANFIS-N": "n.pt",
    "ANFIS-F": "f.pt",
    "ANFIS-T": "t.pt",
    "ANFIS-T-no-current": "t_no_current.pt",
}
_KEY_COLUMNS = ["source_id", "site_id", "year_month"]
_ADAPTIVE_SEQUENCE_STATE_COLUMNS = _KEY_COLUMNS + sorted(set(ADAPTIVE_STATE_MAPPING.values()))
_CANONICAL_STATE_COLUMNS = _KEY_COLUMNS + PIPE_STATE_COLUMNS + [
    "irc1",
    "irc1_no_chla",
]


@dataclass(frozen=True)
class PipeGrudExternalAdaptiveSurfaceResult:
    """Artifacts and manifest payload emitted by the adaptive surface builder."""

    manifest: dict[str, object]
    row_counts: dict[str, int]
    output_paths: tuple[Path, ...]


def run_external_pipe_adaptive_surface_build(
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
) -> PipeGrudExternalAdaptiveSurfaceResult:
    """Build a reference-transform adaptive surface and PIPE sequence artifacts."""

    args = _surface_args(parameters)
    request = read_dataset_request(dataset_id, workspace=workspace)
    variables = load_canonical_variables()
    canonical_rows = _canonical_rows(request.observations, variables)
    panel_rows = _monthly_panel_rows(canonical_rows, variables)
    wide_panel = _wide_panel_frame(panel_rows, canonical_rows)
    featured_panel = add_module_features(wide_panel)
    model_bundle = _load_adaptive_models(
        models_dir=args.models_dir,
        manifest_path=args.model_manifest,
    )
    predicted = _predict_external_adaptive_modules(
        models=cast(Mapping[str, Any], model_bundle["models"]),
        frame=featured_panel,
        predict_batch_rows=args.predict_batch_rows,
    )
    adaptive_state = adaptive_state_from_predictions(predicted)
    adaptive_sequence_state = _adaptive_sequence_state(adaptive_state)
    canonical_state_surface = _canonical_surface_from_adaptive(adaptive_state)
    candidates = build_sequence_candidates(adaptive_sequence_state, input_surface="adaptive")
    sequences, discarded = _filter_external_sequences(candidates, max_gap_months=args.max_gap_months)
    summary = summarize_sequences(sequences)
    discarded_summary = summarize_discarded(discarded)
    origins = _eligible_inference_origins(canonical_state_surface, history_length=args.history_length)

    output_paths = _write_outputs(
        run_dir=run_dir,
        panel_rows=panel_rows,
        wide_panel=wide_panel,
        featured_panel=featured_panel,
        adaptive_state=adaptive_state,
        adaptive_sequence_state=adaptive_sequence_state,
        canonical_state_surface=canonical_state_surface,
        sequences=sequences,
        summary=summary,
        discarded_summary=discarded_summary,
        origins=origins,
        module_coverage=_module_coverage(featured_panel),
    )
    row_counts = {
        "canonical_observations": len(canonical_rows),
        "monthly_panel": len(panel_rows),
        "monthly_panel_wide": int(len(wide_panel)),
        "adaptive_feature_rows": int(len(featured_panel)),
        "adaptive_state_surface": int(len(adaptive_state)),
        "pipe_state_surface": int(len(canonical_state_surface)),
        "candidate_transitions": int(len(candidates)),
        "kept_sequence_rows": int(len(sequences)),
        "discarded_candidate_rows": int(len(discarded)),
        "sequence_summary_rows": int(len(summary)),
        "discarded_summary_rows": int(len(discarded_summary)),
        "inference_candidate_origins": int(len(origins)),
        "loaded_adaptive_modules": int(len(cast(Mapping[str, object], model_bundle["models"]))),
        "generated_reports": 2,
    }
    readiness = {
        "state_surface_version": EXTERNAL_PIPE_ADAPTIVE_SURFACE_VERSION,
        "reference_profile": _REFERENCE_PROFILE,
        "adaptive_reference_transform_applied": True,
        "state_surface_matches_reference_schema": _sequence_schema_compatible(canonical_state_surface),
        "state_surface_matches_reference_training_scope": False,
        "sequence_schema_compatible": _sequence_schema_compatible(canonical_state_surface),
        "ready_for_reference_inference": _ready_for_reference_inference(row_counts),
        "history_length": args.history_length,
        "max_gap_months": args.max_gap_months,
    }
    blockers = _blockers(row_counts=row_counts, readiness=readiness, plan=plan)
    warnings = _warnings(row_counts=row_counts, plan=plan)
    manifest: dict[str, object] = {
        "execution_id": execution_id,
        "plan_id": plan.plan_id,
        "dataset_id": dataset_id,
        "workflow": plan.workflow,
        "adapter": adapter_id,
        "adapter_interface_version": adapter_interface_version,
        "status": "completed",
        "execution_mode": "build_adaptive_surface",
        "surface_version": EXTERNAL_PIPE_ADAPTIVE_SURFACE_VERSION,
        "reference_profile": _REFERENCE_PROFILE,
        "outcome": "built_reference_ready" if readiness["ready_for_reference_inference"] else "not_ready",
        "started_at": started_at,
        "completed_at": _now_utc(),
        "parameters": _serializable_args(args),
        "row_counts": row_counts,
        "readiness": readiness,
        "blockers": blockers,
        "warnings": warnings,
        "planner": {
            "plan_id": plan.plan_id,
            "status": str(plan.status),
            "executable": plan.executable,
            "blockers": [issue.model_dump(mode="json") for issue in plan.blockers],
            "warnings": [issue.model_dump(mode="json") for issue in plan.warnings],
        },
        "schema": {
            "pipe_state_columns": PIPE_STATE_COLUMNS,
            "season_columns": SEASON_COLUMNS,
            "input_columns": INPUT_COLUMNS,
            "target_columns": TARGET_COLUMNS,
            "optional_context_columns": OPTIONAL_CONTEXT_COLUMNS,
            "adaptive_state_mapping": ADAPTIVE_STATE_MAPPING,
        },
        "adaptive_models": {
            "models_dir": _file_or_dir_record(args.models_dir),
            "manifest": _file_record(args.model_manifest),
            "checkpoints": [_file_record(path) for path in cast(tuple[Path, ...], model_bundle["checkpoint_paths"])],
            "modules": cast(Mapping[str, object], model_bundle["module_metadata"]),
        },
        "limitations": [
            "This mode applies the reviewed adaptive ANFIS transform to an external dataset without retraining.",
            "The output is schema-compatible with the reviewed adaptive PIPE-GRU-D reference model.",
            "Predictive skill and field transferability are not guaranteed for a new water body.",
            "Bloom calibrators and 2B policy thresholds are not applied in this build step.",
        ],
        "artifacts": [_file_record(path, workspace=workspace) for path in output_paths],
    }
    report_path = run_dir / "pipe_adaptive_surface_report.md"
    manifest_path = run_dir / "pipe_adaptive_surface_manifest.json"
    _write_text(report_path, _report(manifest))
    _write_json(manifest_path, manifest)
    output_paths = (*output_paths, report_path, manifest_path)
    manifest["artifacts"] = [_file_record(path, workspace=workspace) for path in output_paths]
    _write_json(manifest_path, manifest)
    return PipeGrudExternalAdaptiveSurfaceResult(
        manifest=manifest,
        row_counts=row_counts,
        output_paths=output_paths,
    )


def adaptive_surface_artifacts_available(
    *,
    models_dir: Path = _DEFAULT_MODELS_DIR,
    manifest_path: Path = _DEFAULT_MANIFEST,
) -> tuple[bool, list[str]]:
    """Return availability for adaptive ANFIS artifacts required by API jobs."""

    missing = []
    if not manifest_path.exists():
        missing.append("adaptive_anfis_state_manifest")
    for module, filename in _MODULE_CHECKPOINTS.items():
        if not (models_dir / filename).exists():
            missing.append(f"adaptive_checkpoint:{module}")
    return len(missing) == 0, missing


def _load_adaptive_models(*, models_dir: Path, manifest_path: Path) -> dict[str, object]:
    torch = _require_torch()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config_obj = manifest.get("config", {})
    config = cast(Mapping[str, object], config_obj) if isinstance(config_obj, dict) else {}
    min_width = _float_config(config, "min_width", 0.03)
    min_gap = _float_config(config, "min_gap", 1e-4)
    models: dict[str, Any] = {}
    checkpoint_paths: list[Path] = []
    module_metadata: dict[str, object] = {}
    for module, filename in _MODULE_CHECKPOINTS.items():
        path = models_dir / filename
        payload = torch.load(path, map_location="cpu", weights_only=False)
        if payload.get("module") != module:
            raise ValueError(f"Adaptive ANFIS checkpoint {path} declares unexpected module {payload.get('module')!r}")
        expected_features = list(MODULE_SPECS[module]["feature_columns"])
        checkpoint_features = list(payload.get("feature_columns", []))
        if checkpoint_features != expected_features:
            raise ValueError(
                f"Adaptive ANFIS checkpoint {path} has feature columns {checkpoint_features}; "
                f"expected {expected_features}"
            )
        model = make_adaptive_anfis(
            input_dim=int(payload["input_dim"]),
            membership_count=int(payload["membership_count"]),
            min_width=min_width,
            min_gap=min_gap,
            center_constraint=str(payload.get("center_constraint", config.get("center_constraint", "unit"))),
        )
        model.load_state_dict(payload["state_dict"])
        model.eval()
        models[module] = model
        checkpoint_paths.append(path)
        module_metadata[module] = {
            "checkpoint": path.as_posix(),
            "input_dim": int(payload["input_dim"]),
            "membership_count": int(payload["membership_count"]),
            "rule_count": int(payload["rule_count"]),
            "center_constraint": str(payload.get("center_constraint", "")),
            "feature_columns": checkpoint_features,
            "target_column": str(payload.get("target_column", "")),
        }
    return {
        "models": models,
        "checkpoint_paths": tuple(checkpoint_paths),
        "module_metadata": module_metadata,
    }


def _predict_external_adaptive_modules(
    *,
    models: Mapping[str, Any],
    frame: pd.DataFrame,
    predict_batch_rows: int,
) -> pd.DataFrame:
    out = frame.copy()
    for module, spec in MODULE_SPECS.items():
        predictions = []
        sigmas = []
        for start in range(0, len(out), predict_batch_rows):
            chunk = out.iloc[start : start + predict_batch_rows]
            features, missing_fraction = _module_features(chunk, spec)
            prediction, sigma = _predict_with_sigma(model=models[module], features=features, missing_fraction=missing_fraction)
            predictions.append(prediction)
            sigmas.append(sigma)
        out[spec["output_column"]] = np.concatenate(predictions) if predictions else np.array([], dtype="float64")
        out[spec["sigma_column"]] = np.concatenate(sigmas) if sigmas else np.array([], dtype="float64")
    return out


def _adaptive_sequence_state(adaptive_state: pd.DataFrame) -> pd.DataFrame:
    frame = adaptive_state.copy()
    for column in _ADAPTIVE_SEQUENCE_STATE_COLUMNS:
        if column not in frame.columns:
            frame[column] = np.nan
    return frame[_ADAPTIVE_SEQUENCE_STATE_COLUMNS].sort_values(_KEY_COLUMNS).reset_index(drop=True)


def _canonical_surface_from_adaptive(adaptive_state: pd.DataFrame) -> pd.DataFrame:
    frame = adaptive_state.copy()
    out = frame[_KEY_COLUMNS].copy()
    reverse_mapping = {canonical: adaptive for canonical, adaptive in ADAPTIVE_STATE_MAPPING.items()}
    for column in PIPE_STATE_COLUMNS:
        out[column] = pd.to_numeric(frame[reverse_mapping[column]], errors="coerce").clip(0.0, 1.0)
    out["irc1"] = pd.to_numeric(frame["irc1_adaptive"], errors="coerce").clip(0.0, 1.0)
    out["irc1_no_chla"] = pd.to_numeric(frame["irc1_no_chla_adaptive"], errors="coerce").clip(0.0, 1.0)
    return out[_CANONICAL_STATE_COLUMNS].sort_values(_KEY_COLUMNS).reset_index(drop=True)


def _module_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for module, spec in MODULE_SPECS.items():
        raw_features = frame[spec["feature_columns"]].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        _features, missing_fraction = _module_features(frame, spec)
        rows.append(
            {
                "module": module,
                "rows": int(len(frame)),
                "feature_columns": ",".join(spec["feature_columns"]),
                "mean_missing_fraction": float(missing_fraction.mean()) if len(missing_fraction) else float("nan"),
                "complete_feature_rows": int(raw_features.notna().all(axis=1).sum()),
            }
        )
    return pd.DataFrame(rows)


def _module_features(frame: pd.DataFrame, spec: Mapping[str, object]) -> tuple[pd.DataFrame, pd.Series]:
    feature_columns = list(cast(list[str], spec["feature_columns"]))
    features = frame[feature_columns].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    missing_fraction = features.isna().mean(axis=1)
    filled = features.fillna(0.5).clip(0.0, 1.0)
    writable = pd.DataFrame(
        np.array(filled.to_numpy(dtype="float32"), dtype="float32", copy=True),
        columns=feature_columns,
        index=filled.index,
    )
    return writable, missing_fraction


def _predict_with_sigma(
    *,
    model: Any,
    features: pd.DataFrame,
    missing_fraction: pd.Series,
) -> tuple[np.ndarray, np.ndarray]:
    torch = _require_torch()
    values = np.array(features.to_numpy(dtype="float32"), dtype="float32", copy=True)
    x = torch.as_tensor(values, dtype=torch.float32)
    with torch.no_grad():
        details = model(x, return_details=True)
    prediction = details["prediction"].detach().cpu().numpy()
    normalized = details["normalized_firing_strengths"].detach().cpu().numpy()
    entropy = -(normalized * np.log(np.clip(normalized, 1e-12, 1.0))).sum(axis=1)
    if normalized.shape[1] > 1:
        entropy = entropy / np.log(normalized.shape[1])
    sigma = np.clip(0.10 + 0.45 * entropy + 0.35 * missing_fraction.to_numpy(dtype="float64"), 0.0, 1.0)
    return prediction, sigma


def _write_outputs(
    *,
    run_dir: Path,
    panel_rows: list[dict[str, object]],
    wide_panel: pd.DataFrame,
    featured_panel: pd.DataFrame,
    adaptive_state: pd.DataFrame,
    adaptive_sequence_state: pd.DataFrame,
    canonical_state_surface: pd.DataFrame,
    sequences: pd.DataFrame,
    summary: pd.DataFrame,
    discarded_summary: pd.DataFrame,
    origins: pd.DataFrame,
    module_coverage: pd.DataFrame,
) -> tuple[Path, ...]:
    run_dir.mkdir(parents=True, exist_ok=True)
    panel_path = run_dir / "pipe_monthly_panel.csv"
    wide_panel_path = run_dir / "pipe_monthly_panel_wide.csv"
    features_path = run_dir / "pipe_adaptive_features.csv"
    adaptive_csv_path = run_dir / "pipe_adaptive_state_surface.csv"
    adaptive_parquet_path = run_dir / "pipe_adaptive_state_surface.parquet"
    adaptive_sequence_csv_path = run_dir / "pipe_adaptive_sequence_state.csv"
    adaptive_sequence_parquet_path = run_dir / "pipe_adaptive_sequence_state.parquet"
    state_csv_path = run_dir / "pipe_state_surface.csv"
    state_parquet_path = run_dir / "pipe_state_surface.parquet"
    sequences_csv_path = run_dir / "pipe_sequences.csv"
    sequences_parquet_path = run_dir / "pipe_sequences.parquet"
    origins_csv_path = run_dir / "pipe_inference_origins.csv"
    origins_parquet_path = run_dir / "pipe_inference_origins.parquet"
    summary_path = run_dir / "pipe_sequence_summary.csv"
    discarded_summary_path = run_dir / "pipe_sequence_discarded_summary.csv"
    coverage_path = run_dir / "pipe_adaptive_module_coverage.csv"

    pd.DataFrame(panel_rows).to_csv(panel_path, index=False)
    wide_panel.to_csv(wide_panel_path, index=False)
    featured_panel.to_csv(features_path, index=False)
    adaptive_state.to_csv(adaptive_csv_path, index=False)
    adaptive_state.to_parquet(adaptive_parquet_path, index=False)
    adaptive_sequence_state.to_csv(adaptive_sequence_csv_path, index=False)
    adaptive_sequence_state.to_parquet(adaptive_sequence_parquet_path, index=False)
    canonical_state_surface.to_csv(state_csv_path, index=False)
    canonical_state_surface.to_parquet(state_parquet_path, index=False)
    sequences.to_csv(sequences_csv_path, index=False)
    sequences.to_parquet(sequences_parquet_path, index=False)
    origins.to_csv(origins_csv_path, index=False)
    origins.to_parquet(origins_parquet_path, index=False)
    summary.to_csv(summary_path, index=False)
    discarded_summary.to_csv(discarded_summary_path, index=False)
    module_coverage.to_csv(coverage_path, index=False)
    return (
        panel_path,
        wide_panel_path,
        features_path,
        adaptive_csv_path,
        adaptive_parquet_path,
        adaptive_sequence_csv_path,
        adaptive_sequence_parquet_path,
        state_csv_path,
        state_parquet_path,
        sequences_csv_path,
        sequences_parquet_path,
        origins_csv_path,
        origins_parquet_path,
        summary_path,
        discarded_summary_path,
        coverage_path,
    )


def _blockers(
    *,
    row_counts: Mapping[str, int],
    readiness: Mapping[str, object],
    plan: RunPlanResponse,
) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []
    if row_counts["monthly_panel"] == 0:
        blockers.append(_issue("no_monthly_panel", "Dataset did not produce monthly panel rows."))
    if row_counts["adaptive_state_surface"] == 0:
        blockers.append(_issue("no_adaptive_state_surface", "Dataset did not produce adaptive state surface rows."))
    if row_counts["kept_sequence_rows"] == 0:
        blockers.append(_issue("no_adjacent_sequences", "No adjacent month adaptive PIPE sequence rows were built."))
    if row_counts["inference_candidate_origins"] == 0:
        blockers.append(
            _issue(
                "no_inference_origins",
                "No site has enough contiguous complete adaptive state history for the configured history length.",
                {"history_length": readiness.get("history_length")},
            )
        )
    if not bool(readiness.get("state_surface_matches_reference_schema")):
        blockers.append(
            _issue(
                "adaptive_surface_schema_mismatch",
                "The generated adaptive surface is not compatible with the reviewed PIPE-GRU-D input schema.",
            )
        )
    if plan.blockers:
        blockers.append(
            _issue(
                "planner_not_ready",
                "The dry-run planner has blockers that must be reviewed before model inference.",
                {"blocker_count": len(plan.blockers), "plan_status": str(plan.status)},
            )
        )
    return blockers


def _warnings(*, row_counts: Mapping[str, int], plan: RunPlanResponse) -> list[dict[str, object]]:
    warnings = [
        _issue(
            "external_domain_not_validated",
            "The adaptive transform is the reviewed reference transform, but skill on this external water body is not guaranteed.",
            {"reference_profile": _REFERENCE_PROFILE},
        )
    ]
    if row_counts["kept_sequence_rows"] > 0:
        warnings.append(
            _issue(
                "calibrated_alerts_not_applied",
                "This mode builds adaptive state/sequences only; calibrated bloom alerts require a separate inference mode.",
            )
        )
    if plan.warnings:
        warnings.append(
            _issue(
                "planner_warnings_present",
                "The dry-run planner emitted warnings for this dataset.",
                {"warning_count": len(plan.warnings)},
            )
        )
    return warnings


def _ready_for_reference_inference(row_counts: Mapping[str, int]) -> bool:
    return (
        row_counts["adaptive_state_surface"] > 0
        and row_counts["pipe_state_surface"] > 0
        and row_counts["inference_candidate_origins"] > 0
        and row_counts["loaded_adaptive_modules"] == len(_MODULE_CHECKPOINTS)
    )


def _sequence_schema_compatible(state_surface: pd.DataFrame) -> bool:
    return all(column in state_surface.columns for column in PIPE_STATE_COLUMNS)


def _report(manifest: Mapping[str, object]) -> str:
    row_counts = cast(Mapping[str, object], manifest.get("row_counts", {}))
    readiness = cast(Mapping[str, object], manifest.get("readiness", {}))
    blockers = _issue_lines(manifest.get("blockers", []))
    warnings = _issue_lines(manifest.get("warnings", []))
    return "\n".join(
        [
            "# External PIPE-GRU-D Adaptive Surface Build",
            "",
            f"- adapter: `{manifest['adapter']}`",
            f"- execution mode: `{manifest['execution_mode']}`",
            f"- surface version: `{manifest['surface_version']}`",
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
            "- These artifacts apply the reviewed adaptive ANFIS transform to the uploaded dataset.",
            "- They are mechanically compatible with the adaptive PIPE-GRU-D reference profile when readiness is true.",
            "- They do not apply calibrated bloom probabilities or 2B alert policy thresholds.",
            "",
        ]
    )


def _surface_args(parameters: Mapping[str, object]) -> Namespace:
    return Namespace(
        history_length=_int_parameter(parameters, "history_length", _DEFAULT_HISTORY_LENGTH),
        max_gap_months=_int_parameter(parameters, "max_gap_months", _DEFAULT_MAX_GAP_MONTHS),
        predict_batch_rows=_int_parameter(parameters, "predict_batch_rows", _DEFAULT_PREDICT_BATCH_ROWS),
        models_dir=Path(str(parameters.get("adaptive_models_dir", _DEFAULT_MODELS_DIR.as_posix()))),
        model_manifest=Path(str(parameters.get("adaptive_model_manifest", _DEFAULT_MANIFEST.as_posix()))),
    )


def _serializable_args(args: Namespace) -> dict[str, object]:
    return {
        "history_length": args.history_length,
        "max_gap_months": args.max_gap_months,
        "predict_batch_rows": args.predict_batch_rows,
        "adaptive_models_dir": args.models_dir.as_posix(),
        "adaptive_model_manifest": args.model_manifest.as_posix(),
    }


def _int_parameter(parameters: Mapping[str, object], key: str, default: int) -> int:
    value = parameters.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        parsed = int(value)
        if parsed > 0:
            return parsed
    return default


def _float_config(config: Mapping[str, object], key: str, default: float) -> float:
    value = config.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        return float(value)
    return default


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


def _file_record(path: Path, *, workspace: Path | None = None) -> dict[str, object]:
    resolved = path.resolve()
    display_path = path.as_posix()
    if workspace is not None:
        try:
            display_path = resolved.relative_to(workspace.resolve()).as_posix()
        except ValueError:
            display_path = path.as_posix()
    return {
        "path": display_path,
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _file_or_dir_record(path: Path) -> dict[str, object]:
    if path.is_file():
        return _file_record(path)
    digest = hashlib.sha256()
    files = []
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


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
