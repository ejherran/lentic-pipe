"""Build external PIPE-GRU-D state and sequence artifacts for API datasets."""

from __future__ import annotations

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
from src.api.services.run_executor import (
    _canonical_rows,
    _load_fuzzy_settings,
    _monthly_panel_rows,
    _wide_panel_frame,
)
from src.experiments.build_pipe_sequences import (
    INPUT_COLUMNS,
    OPTIONAL_CONTEXT_COLUMNS,
    PIPE_STATE_COLUMNS,
    SEASON_COLUMNS,
    TARGET_COLUMNS,
    build_sequence_candidates,
    summarize_discarded,
    summarize_sequences,
)
from src.fuzzy.expert import build_expert_state

EXTERNAL_PIPE_SEQUENCE_BUILD_VERSION = "external_pipe_sequence_builder_v0"
EXTERNAL_PIPE_STATE_SURFACE_VERSION = "expert_fuzzy_pipe_state_surface_v0"
_REFERENCE_PROFILE = "adaptive_wqp_focused"
_DEFAULT_MAX_GAP_MONTHS = 1
_DEFAULT_HISTORY_LENGTH = 12
_KEY_COLUMNS = ["source_id", "site_id", "year_month"]
_STATE_SURFACE_COLUMNS = _KEY_COLUMNS + PIPE_STATE_COLUMNS + [
    "irc1",
    "irc1_no_chla",
    "evidence_N",
    "evidence_F",
    "evidence_T",
    "evidence_T_no_chla",
    "missing_N",
    "missing_F",
    "missing_T",
    "missing_T_no_chla",
]


@dataclass(frozen=True)
class PipeGrudExternalSequenceBuildResult:
    """Artifacts and manifest payload emitted by the external sequence builder."""

    manifest: dict[str, object]
    row_counts: dict[str, int]
    output_paths: tuple[Path, ...]


def build_external_pipe_sequence_artifacts(
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
) -> PipeGrudExternalSequenceBuildResult:
    """Build external PIPE state/sequences without running PIPE-GRU-D inference."""

    history_length = _int_parameter(parameters, "history_length", _DEFAULT_HISTORY_LENGTH)
    max_gap_months = _int_parameter(parameters, "max_gap_months", _DEFAULT_MAX_GAP_MONTHS)
    request = read_dataset_request(dataset_id, workspace=workspace)
    variables = load_canonical_variables()

    canonical_rows = _canonical_rows(request.observations, variables)
    panel_rows = _monthly_panel_rows(canonical_rows, variables)
    wide_panel = _wide_panel_frame(panel_rows, canonical_rows)
    fuzzy_settings = _load_fuzzy_settings()
    state, _trace = build_expert_state(wide_panel, irc_weights=fuzzy_settings["irc_weights"])
    state_surface = _pipe_state_surface(state)
    candidates = build_sequence_candidates(state_surface)
    sequences, discarded = _filter_external_sequences(candidates, max_gap_months=max_gap_months)
    summary = summarize_sequences(sequences)
    discarded_summary = summarize_discarded(discarded)
    origins = _eligible_inference_origins(state_surface, history_length=history_length)

    output_paths = _write_external_sequence_outputs(
        run_dir=run_dir,
        panel_rows=panel_rows,
        wide_panel=wide_panel,
        state_surface=state_surface,
        sequences=sequences,
        summary=summary,
        discarded_summary=discarded_summary,
        origins=origins,
    )
    row_counts = {
        "canonical_observations": len(canonical_rows),
        "monthly_panel": len(panel_rows),
        "monthly_panel_wide": int(len(wide_panel)),
        "pipe_state_surface": int(len(state_surface)),
        "candidate_transitions": int(len(candidates)),
        "kept_sequence_rows": int(len(sequences)),
        "discarded_candidate_rows": int(len(discarded)),
        "sequence_summary_rows": int(len(summary)),
        "discarded_summary_rows": int(len(discarded_summary)),
        "inference_candidate_origins": int(len(origins)),
        "generated_reports": 2,
    }
    readiness = {
        "state_surface_mode": EXTERNAL_PIPE_STATE_SURFACE_VERSION,
        "reference_profile": _REFERENCE_PROFILE,
        "sequence_schema_compatible": _sequence_schema_compatible(state_surface),
        "state_surface_matches_reference_profile": False,
        "ready_for_sequence_build": len(sequences) > 0 or len(origins) > 0,
        "ready_for_reference_inference": False,
        "history_length": history_length,
        "max_gap_months": max_gap_months,
    }
    blockers = _sequence_build_blockers(
        row_counts=row_counts,
        readiness=readiness,
        plan=plan,
    )
    warnings = _sequence_build_warnings(row_counts=row_counts, plan=plan)
    manifest: dict[str, object] = {
        "execution_id": execution_id,
        "plan_id": plan.plan_id,
        "dataset_id": dataset_id,
        "workflow": plan.workflow,
        "adapter": adapter_id,
        "adapter_interface_version": adapter_interface_version,
        "status": "completed",
        "execution_mode": "build_sequences",
        "build_version": EXTERNAL_PIPE_SEQUENCE_BUILD_VERSION,
        "state_surface_version": EXTERNAL_PIPE_STATE_SURFACE_VERSION,
        "reference_profile": _REFERENCE_PROFILE,
        "outcome": "built_with_limitations" if readiness["ready_for_sequence_build"] else "not_ready",
        "started_at": started_at,
        "completed_at": _now_utc(),
        "parameters": {
            "history_length": history_length,
            "max_gap_months": max_gap_months,
        },
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
        },
        "limitations": [
            "This build creates an expert-fuzzy external PIPE state surface, not the reviewed adaptive WQP-focused state surface.",
            "It does not run PIPE-GRU-D model inference, rollout calibration, or alert policy application.",
            "Reference-profile inference must stay disabled until an adaptive-compatible external state adapter is reviewed.",
        ],
        "artifacts": [_file_record(path, workspace=workspace) for path in output_paths],
    }
    report_path = run_dir / "pipe_sequence_build_report.md"
    manifest_path = run_dir / "pipe_sequence_build_manifest.json"
    _write_text(report_path, _sequence_build_report(manifest))
    _write_json(manifest_path, manifest)
    output_paths = (*output_paths, report_path, manifest_path)
    manifest["artifacts"] = [_file_record(path, workspace=workspace) for path in output_paths]
    _write_json(manifest_path, manifest)
    return PipeGrudExternalSequenceBuildResult(
        manifest=manifest,
        row_counts=row_counts,
        output_paths=output_paths,
    )


def _pipe_state_surface(state: pd.DataFrame) -> pd.DataFrame:
    frame = state.copy()
    for column in _STATE_SURFACE_COLUMNS:
        if column not in frame.columns:
            frame[column] = np.nan
    return frame[_STATE_SURFACE_COLUMNS].sort_values(_KEY_COLUMNS).reset_index(drop=True)


def _filter_external_sequences(
    candidates: pd.DataFrame,
    *,
    max_gap_months: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = candidates.copy()
    frame["split_reason"] = "kept"
    has_target = frame["target_year_month"].notna()
    frame.loc[~has_target, "split_reason"] = "no_next_state"
    gap_too_large = has_target & (pd.to_numeric(frame["target_gap_months"], errors="coerce") > max_gap_months)
    frame.loc[gap_too_large, "split_reason"] = "gap_too_large"
    state_input_columns = [f"x_{column}" for column in PIPE_STATE_COLUMNS]
    missing_state = frame[state_input_columns + TARGET_COLUMNS].isna().any(axis=1)
    frame.loc[has_target & missing_state, "split_reason"] = "missing_state_values"

    kept = frame[frame["split_reason"] == "kept"].copy()
    if kept.empty:
        ordered_columns = [
            "source_id",
            "site_id",
            "sequence_step",
            "origin_year_month",
            "target_year_month",
            "target_gap_months",
            "split",
            "origin_month",
            *INPUT_COLUMNS,
            *TARGET_COLUMNS,
            *[f"x_{column}" for column in OPTIONAL_CONTEXT_COLUMNS if f"x_{column}" in frame.columns],
        ]
        return pd.DataFrame(columns=ordered_columns), frame.reset_index(drop=True)
    kept["split"] = "external"
    kept["target_gap_months"] = kept["target_gap_months"].astype("int16")
    kept = _add_season_features(kept)
    optional_columns = [f"x_{column}" for column in OPTIONAL_CONTEXT_COLUMNS if f"x_{column}" in kept.columns]
    ordered_columns = [
        "source_id",
        "site_id",
        "sequence_step",
        "origin_year_month",
        "target_year_month",
        "target_gap_months",
        "split",
        "origin_month",
        *INPUT_COLUMNS,
        *TARGET_COLUMNS,
        *optional_columns,
    ]
    return kept[ordered_columns].sort_values(["source_id", "site_id", "origin_year_month"]).reset_index(drop=True), frame[
        frame["split_reason"] != "kept"
    ].reset_index(drop=True)


def _eligible_inference_origins(state_surface: pd.DataFrame, *, history_length: int) -> pd.DataFrame:
    frame = state_surface.copy()
    frame["period_ord"] = _period_ord(frame["year_month"])
    frame = frame.sort_values(["source_id", "site_id", "period_ord"]).reset_index(drop=True)
    rows: list[dict[str, object]] = []
    grouped = cast(Any, frame.groupby(["source_id", "site_id"], sort=False))
    for (_source_id, _site_id), group in grouped:
        records = group.to_dict(orient="records")
        for index, record in enumerate(records):
            start = index - history_length + 1
            if start < 0:
                continue
            window = records[start : index + 1]
            periods = [int(item["period_ord"]) for item in window]
            contiguous = all((right - left) == 1 for left, right in zip(periods, periods[1:], strict=False))
            if not contiguous:
                continue
            if any(_missing_pipe_state_values(item) for item in window):
                continue
            row = {
                "source_id": record["source_id"],
                "site_id": record["site_id"],
                "sequence_step": index,
                "origin_year_month": record["year_month"],
                "history_start_year_month": window[0]["year_month"],
                "history_length": history_length,
                "split": "external",
            }
            for column in PIPE_STATE_COLUMNS:
                row[f"x_{column}"] = record[column]
            rows.append(row)
    origins = pd.DataFrame(rows)
    if origins.empty:
        return pd.DataFrame(
            columns=[
                "source_id",
                "site_id",
                "sequence_step",
                "origin_year_month",
                "history_start_year_month",
                "history_length",
                "split",
                "origin_month",
                *INPUT_COLUMNS,
            ]
        )
    origins = _add_season_features(origins)
    return origins[
        [
            "source_id",
            "site_id",
            "sequence_step",
            "origin_year_month",
            "history_start_year_month",
            "history_length",
            "split",
            "origin_month",
            *INPUT_COLUMNS,
        ]
    ].sort_values(["source_id", "site_id", "origin_year_month"]).reset_index(drop=True)


def _missing_pipe_state_values(row: Mapping[str, object]) -> bool:
    for column in PIPE_STATE_COLUMNS:
        value = row.get(column)
        if value is None or pd.isna(value):
            return True
    return False


def _write_external_sequence_outputs(
    *,
    run_dir: Path,
    panel_rows: list[dict[str, object]],
    wide_panel: pd.DataFrame,
    state_surface: pd.DataFrame,
    sequences: pd.DataFrame,
    summary: pd.DataFrame,
    discarded_summary: pd.DataFrame,
    origins: pd.DataFrame,
) -> tuple[Path, ...]:
    run_dir.mkdir(parents=True, exist_ok=True)
    panel_path = run_dir / "pipe_monthly_panel.csv"
    wide_panel_path = run_dir / "pipe_monthly_panel_wide.csv"
    state_csv_path = run_dir / "pipe_state_surface.csv"
    state_parquet_path = run_dir / "pipe_state_surface.parquet"
    sequences_csv_path = run_dir / "pipe_sequences.csv"
    sequences_parquet_path = run_dir / "pipe_sequences.parquet"
    origins_csv_path = run_dir / "pipe_inference_origins.csv"
    origins_parquet_path = run_dir / "pipe_inference_origins.parquet"
    summary_path = run_dir / "pipe_sequence_summary.csv"
    discarded_summary_path = run_dir / "pipe_sequence_discarded_summary.csv"

    pd.DataFrame(panel_rows).to_csv(panel_path, index=False)
    wide_panel.to_csv(wide_panel_path, index=False)
    state_surface.to_csv(state_csv_path, index=False)
    state_surface.to_parquet(state_parquet_path, index=False)
    sequences.to_csv(sequences_csv_path, index=False)
    sequences.to_parquet(sequences_parquet_path, index=False)
    origins.to_csv(origins_csv_path, index=False)
    origins.to_parquet(origins_parquet_path, index=False)
    summary.to_csv(summary_path, index=False)
    discarded_summary.to_csv(discarded_summary_path, index=False)
    return (
        panel_path,
        wide_panel_path,
        state_csv_path,
        state_parquet_path,
        sequences_csv_path,
        sequences_parquet_path,
        origins_csv_path,
        origins_parquet_path,
        summary_path,
        discarded_summary_path,
    )


def _sequence_build_blockers(
    *,
    row_counts: Mapping[str, int],
    readiness: Mapping[str, object],
    plan: RunPlanResponse,
) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []
    if row_counts["monthly_panel"] == 0:
        blockers.append(_issue("no_monthly_panel", "Dataset did not produce monthly panel rows."))
    if row_counts["pipe_state_surface"] == 0:
        blockers.append(_issue("no_pipe_state_surface", "Dataset did not produce PIPE state surface rows."))
    if row_counts["kept_sequence_rows"] == 0:
        blockers.append(_issue("no_adjacent_sequences", "No adjacent month PIPE sequence rows were built."))
    if row_counts["inference_candidate_origins"] == 0:
        blockers.append(
            _issue(
                "no_inference_origins",
                "No site has enough contiguous complete state history for the configured history length.",
                {"history_length": readiness.get("history_length")},
            )
        )
    blockers.append(
        _issue(
            "adaptive_reference_surface_not_available",
            "The generated surface is expert-fuzzy and does not match the reviewed adaptive WQP-focused reference profile.",
            {
                "state_surface_mode": readiness.get("state_surface_mode"),
                "reference_profile": readiness.get("reference_profile"),
            },
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


def _sequence_build_warnings(*, row_counts: Mapping[str, int], plan: RunPlanResponse) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    if row_counts["kept_sequence_rows"] > 0:
        warnings.append(
            _issue(
                "external_sequences_are_structural",
                "Sequence rows are structurally PIPE-compatible but are not evidence that the reference model is calibrated for this dataset.",
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


def _sequence_schema_compatible(state_surface: pd.DataFrame) -> bool:
    return all(column in state_surface.columns for column in PIPE_STATE_COLUMNS)


def _sequence_build_report(manifest: Mapping[str, object]) -> str:
    row_counts = cast(Mapping[str, object], manifest.get("row_counts", {}))
    readiness = cast(Mapping[str, object], manifest.get("readiness", {}))
    blockers = _issue_lines(manifest.get("blockers", []))
    warnings = _issue_lines(manifest.get("warnings", []))
    return "\n".join(
        [
            "# External PIPE-GRU-D Sequence Build",
            "",
            f"- adapter: `{manifest['adapter']}`",
            f"- execution mode: `{manifest['execution_mode']}`",
            f"- build version: `{manifest['build_version']}`",
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
            "- These artifacts prepare external data for future PIPE-GRU-D inference.",
            "- They do not run the temporal model or emit calibrated alerts.",
            "- Reference-profile inference remains disabled until adaptive-compatible external state construction is reviewed.",
            "",
        ]
    )


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


def _add_season_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    month = out["origin_year_month"].astype(str).str.slice(5, 7).astype("int16")
    radians = 2.0 * np.pi * (month.astype("float64") - 1.0) / 12.0
    out["origin_month"] = month
    out["season_sin_annual"] = np.sin(radians)
    out["season_cos_annual"] = np.cos(radians)
    out["season_sin_semiannual"] = np.sin(2.0 * radians)
    out["season_cos_semiannual"] = np.cos(2.0 * radians)
    return out


def _period_ord(months: pd.Series) -> pd.Series:
    values = pd.PeriodIndex(months.astype(str), freq="M").asi8.astype("int64")
    return pd.Series(values, index=months.index)


def _int_parameter(parameters: Mapping[str, object], key: str, default: int) -> int:
    value = parameters.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        parsed = int(value)
        if parsed > 0:
            return parsed
    return default


def _file_record(path: Path, *, workspace: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(workspace).as_posix(),
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
