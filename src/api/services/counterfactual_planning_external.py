"""Run counterfactual planning V1 scenarios for API datasets."""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any, cast

import pandas as pd

from src.api.schemas.run import RunPlanResponse
from src.api.services.pipe_grud_external_inference import _file_record, _issue, _issue_lines, _write_json
from src.api.services.run_repository import read_run_execution, run_plan_dir
from src.experiments.evaluate_counterfactual_planning import _write_csv_atomic
from src.experiments.evaluate_counterfactual_planning_v1 import (
    DEFAULT_CONFIG,
    DEFAULT_VARIABLES_CONFIG,
    NON_CAUSAL_GUARDRAIL,
    PLANNING_VERSION,
    _origin_rows,
    _refresh_derived_columns,
    _state_for_origins,
    build_examples,
    build_metric_rows,
    build_pareto,
    build_raw_scenarios,
    build_summary,
    build_support_lookup,
    evaluate_scenario,
    load_config,
    manifest_payload,
    output_paths,
    prepare_planning_rows,
    variable_ranges,
    write_report,
)

EXTERNAL_COUNTERFACTUAL_PLANNING_VERSION = "external_counterfactual_planning_raw_proxy_v1"
_DEFAULT_OUTPUT_NAME = "counterfactual"
_COMPATIBLE_ROLLOUT_FILES = (
    "pipe_neural_ode_reference_rollouts.parquet",
    "pipe_neural_ode_reference_rollouts.csv",
    "pipe_grud_reference_rollouts.parquet",
    "pipe_grud_reference_rollouts.csv",
)
_COMPATIBLE_PANEL_FILES = (
    "pipe_monthly_panel_wide.csv",
    "monthly_panel_wide.csv",
)


@dataclass(frozen=True)
class CounterfactualPlanningExternalResult:
    """Artifacts and manifest payload emitted by API planning execution."""

    manifest: dict[str, object]
    row_counts: dict[str, int]
    output_paths: tuple[Path, ...]


def run_external_counterfactual_planning_v1(
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
) -> CounterfactualPlanningExternalResult:
    """Run raw-proxy planning scenarios against a completed API temporal run."""

    args = _planning_args(parameters)
    upstream_execution = read_run_execution(args.upstream_plan_id, workspace=workspace)
    if upstream_execution.dataset_id != dataset_id:
        raise ValueError(
            "Counterfactual planning upstream_plan_id belongs to a different dataset: "
            f"{upstream_execution.dataset_id}"
        )
    upstream_dir = run_plan_dir(args.upstream_plan_id, workspace=workspace)
    rollouts, rollout_path = _read_upstream_rollouts(upstream_dir)
    panel, panel_path = _read_upstream_panel(upstream_dir)
    config = load_config(args.config)
    planning_mode = args.planning_mode or str(config.get("objective", {}).get("default_planning_mode", "normal"))
    evaluation_splits = args.evaluation_splits or ["external"]
    ranges = variable_ranges(args.variables_config)

    run_dir.mkdir(parents=True, exist_ok=True)
    planning_input = _planning_rows_from_rollouts(rollouts)
    planning_rows_path = run_dir / "counterfactual_planning_rows.csv"
    panel_copy_path = run_dir / "counterfactual_panel.csv"
    _write_csv_atomic(planning_input, planning_rows_path)
    _write_csv_atomic(panel, panel_copy_path)

    planning_rows = prepare_planning_rows(
        planning_input,
        config,
        evaluation_splits=evaluation_splits,
        source_ids=args.source_ids,
        max_rows_per_split=args.max_rows_per_split,
    )
    origins = _origin_rows(planning_rows, panel)
    baseline_state = _state_for_origins(_refresh_derived_columns(origins))
    scenarios = build_raw_scenarios(config, planning_mode=planning_mode)
    support_lookup = build_support_lookup(panel, origins, scenarios, config)
    scenario_rows = pd.concat(
        [
            evaluate_scenario(
                planning_rows,
                origins,
                support_lookup,
                baseline_state,
                scenario,
                config,
                ranges,
                planning_mode=planning_mode,
            )
            for scenario in scenarios
        ],
        ignore_index=True,
    )
    metrics = build_metric_rows(scenario_rows, alert_threshold=args.alert_threshold)
    summary = build_summary(metrics)
    pareto = build_pareto(summary)
    examples = build_examples(scenario_rows, examples_per_scenario=args.examples_per_scenario)

    paths = output_paths(run_dir, _DEFAULT_OUTPUT_NAME)
    _write_csv_atomic(metrics, paths["metrics"])
    _write_csv_atomic(summary, paths["summary"])
    _write_csv_atomic(pareto, paths["pareto"])
    _write_csv_atomic(examples, paths["examples"])
    report_args = Namespace(
        config=args.config,
        planning_rows=planning_rows_path,
        panel=panel_copy_path,
        variables_config=args.variables_config,
        output_dir=run_dir,
        output_name=_DEFAULT_OUTPUT_NAME,
        planning_mode=planning_mode,
        evaluation_splits=evaluation_splits,
        source_ids=args.source_ids,
        max_rows_per_split=args.max_rows_per_split,
        examples_per_scenario=args.examples_per_scenario,
        alert_threshold=args.alert_threshold,
    )
    write_report(paths["report"], args=report_args, metrics=metrics, summary=summary, pareto=pareto)

    row_counts = {
        "upstream_rollout_rows": int(len(rollouts)),
        "upstream_panel_rows": int(len(panel)),
        "planning_input_rows": int(len(planning_input)),
        "planning_rows": int(len(planning_rows)),
        "origin_rows": int(len(origins)),
        "scenario_rows": int(len(scenario_rows)),
        "metric_rows": int(len(metrics)),
        "summary_rows": int(len(summary)),
        "pareto_rows": int(len(pareto)),
        "example_rows": int(len(examples)),
        "generated_reports": 2,
    }
    readiness = {
        "upstream_plan_id": args.upstream_plan_id,
        "upstream_workflow": upstream_execution.workflow,
        "compatible_rollout_surface": True,
        "monthly_panel_available": True,
        "planning_rows_available": len(planning_rows) > 0,
        "scenarios_evaluated": len(scenario_rows) > 0,
        "ready_for_planning": len(metrics) > 0 and len(summary) > 0,
        "planning_mode": planning_mode,
        "evaluation_splits": evaluation_splits,
    }
    blockers = _planning_blockers(readiness=readiness, row_counts=row_counts)
    warnings = [
        _issue(
            "counterfactual_not_causal",
            "Counterfactual planning output is model-simulated comparison, not causal field evidence.",
            {"guardrail": NON_CAUSAL_GUARDRAIL},
        )
    ]
    manifest_args = Namespace(
        config=args.config,
        planning_rows=planning_rows_path,
        panel=panel_copy_path,
        variables_config=args.variables_config,
        output_dir=run_dir,
        output_name=_DEFAULT_OUTPUT_NAME,
        planning_mode=planning_mode,
        evaluation_splits=evaluation_splits,
        source_ids=args.source_ids,
        max_rows_per_split=args.max_rows_per_split,
    )
    manifest = manifest_payload(
        args=manifest_args,
        config=config,
        paths=paths,
        metrics=metrics,
        summary=summary,
        pareto=pareto,
        started_at=_parse_started_at(started_at),
    )
    manifest.update(
        {
            "execution_id": execution_id,
            "plan_id": plan.plan_id,
            "dataset_id": dataset_id,
            "workflow": plan.workflow,
            "adapter": adapter_id,
            "adapter_interface_version": adapter_interface_version,
            "execution_mode": "run_scenarios",
            "planning_api_version": EXTERNAL_COUNTERFACTUAL_PLANNING_VERSION,
            "outcome": "completed_planning" if bool(readiness["ready_for_planning"]) else "not_ready",
            "started_at": started_at,
            "completed_at": _now_utc(),
            "row_counts": row_counts,
            "readiness": readiness,
            "blockers": blockers,
            "warnings": warnings,
            "upstream": {
                "plan_id": upstream_execution.plan_id,
                "execution_id": upstream_execution.execution_id,
                "workflow": upstream_execution.workflow,
                "row_counts": upstream_execution.row_counts,
                "rollout_path": _display_path(rollout_path, workspace),
                "panel_path": _display_path(panel_path, workspace),
            },
            "limitations": [
                "Planning scenarios perturb raw monthly panel predictors and recompute fuzzy-state proxies.",
                "Outputs are scenario diagnostics under the configured objective, not causal field intervention evidence.",
                "A compatible upstream temporal run supplies origins and horizons; it does not guarantee transferability.",
            ],
        }
    )
    _write_json(paths["manifest"], manifest)
    output_paths_tuple = (
        planning_rows_path,
        panel_copy_path,
        paths["metrics"],
        paths["summary"],
        paths["pareto"],
        paths["examples"],
        paths["report"],
        paths["manifest"],
    )
    manifest["artifacts"] = [_file_record(path, workspace=workspace) for path in output_paths_tuple]
    _write_json(paths["manifest"], manifest)
    return CounterfactualPlanningExternalResult(
        manifest=manifest,
        row_counts=row_counts,
        output_paths=output_paths_tuple,
    )


def _planning_args(parameters: Mapping[str, object]) -> Namespace:
    upstream_plan_id = str(parameters.get("upstream_plan_id", "")).strip()
    if not upstream_plan_id:
        raise ValueError("Counterfactual planning requires parameters.upstream_plan_id.")
    return Namespace(
        upstream_plan_id=upstream_plan_id,
        config=_path_parameter(parameters, "config", DEFAULT_CONFIG),
        variables_config=_path_parameter(parameters, "variables_config", DEFAULT_VARIABLES_CONFIG),
        planning_mode=_optional_str_parameter(parameters, "planning_mode"),
        evaluation_splits=_optional_str_list_parameter(parameters, "evaluation_splits"),
        source_ids=_optional_str_list_parameter(parameters, "source_ids"),
        max_rows_per_split=_optional_positive_int_parameter(parameters, "max_rows_per_split"),
        examples_per_scenario=_positive_int_parameter(parameters, "examples_per_scenario", 5),
        alert_threshold=_float_parameter(parameters, "alert_threshold", 0.5),
    )


def _read_upstream_rollouts(upstream_dir: Path) -> tuple[pd.DataFrame, Path]:
    for filename in _COMPATIBLE_ROLLOUT_FILES:
        path = upstream_dir / filename
        if not path.exists():
            continue
        if path.suffix == ".parquet":
            return pd.read_parquet(path), path
        return pd.read_csv(path), path
    raise ValueError(
        "Counterfactual planning requires a compatible upstream rollout artifact: "
        + ", ".join(_COMPATIBLE_ROLLOUT_FILES)
    )


def _read_upstream_panel(upstream_dir: Path) -> tuple[pd.DataFrame, Path]:
    for filename in _COMPATIBLE_PANEL_FILES:
        path = upstream_dir / filename
        if path.exists():
            return pd.read_csv(path), path
    raise ValueError(
        "Counterfactual planning requires the upstream monthly panel artifact: "
        + ", ".join(_COMPATIBLE_PANEL_FILES)
    )


def _planning_rows_from_rollouts(rollouts: pd.DataFrame) -> pd.DataFrame:
    required = ["source_id", "site_id", "split", "origin_year_month", "rollout_horizon_months"]
    missing = [column for column in required if column not in rollouts.columns]
    if missing:
        raise ValueError(f"Upstream rollout rows are missing required planning columns: {missing}")
    out = rollouts[required].copy()
    out["horizon_months"] = pd.to_numeric(out["rollout_horizon_months"], errors="raise").astype("int64")
    optional_columns = [
        "forecast_year_month",
        "alert_probability_irc",
        "rollout_probability_bloom_calibrated",
        "reference_any_alert_h",
    ]
    for column in optional_columns:
        if column in rollouts.columns:
            out[column] = rollouts[column].to_numpy()
    return (
        out.drop(columns=["rollout_horizon_months"])
        .drop_duplicates(["source_id", "site_id", "split", "origin_year_month", "horizon_months"])
        .sort_values(["source_id", "site_id", "origin_year_month", "horizon_months"], kind="mergesort")
        .reset_index(drop=True)
    )


def _planning_blockers(*, readiness: Mapping[str, object], row_counts: Mapping[str, int]) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []
    if row_counts["planning_rows"] == 0:
        blockers.append(_issue("no_planning_rows", "No planning rows were available after split/source filtering."))
    if row_counts["scenario_rows"] == 0:
        blockers.append(_issue("no_scenario_rows", "No counterfactual scenario rows were generated."))
    if not bool(readiness.get("ready_for_planning")):
        blockers.append(_issue("planning_not_ready", "Counterfactual planning did not produce metrics and summary rows."))
    return blockers


def _path_parameter(parameters: Mapping[str, object], key: str, default: Path) -> Path:
    value = parameters.get(key)
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    return Path(str(value))


def _optional_str_parameter(parameters: Mapping[str, object], key: str) -> str | None:
    value = parameters.get(key)
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return str(value).strip() or None


def _optional_str_list_parameter(parameters: Mapping[str, object], key: str) -> list[str] | None:
    value = parameters.get(key)
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _optional_positive_int_parameter(parameters: Mapping[str, object], key: str) -> int | None:
    value = parameters.get(key)
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    parsed = int(cast(Any, value))
    return parsed if parsed > 0 else None


def _positive_int_parameter(parameters: Mapping[str, object], key: str, default: int) -> int:
    value = parameters.get(key, default)
    if isinstance(value, bool):
        return default
    parsed = int(cast(Any, value))
    return parsed if parsed > 0 else default


def _float_parameter(parameters: Mapping[str, object], key: str, default: float) -> float:
    value = parameters.get(key, default)
    if isinstance(value, bool):
        return default
    return float(cast(Any, value))


def _parse_started_at(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _display_path(path: Path, workspace: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _planning_report(manifest: Mapping[str, object]) -> str:
    row_counts = cast(Mapping[str, object], manifest.get("row_counts", {}))
    readiness = cast(Mapping[str, object], manifest.get("readiness", {}))
    blockers = _issue_lines(manifest.get("blockers", []))
    warnings = _issue_lines(manifest.get("warnings", []))
    return "\n".join(
        [
            "# External Counterfactual Planning V1",
            "",
            f"- adapter: `{manifest['adapter']}`",
            f"- execution mode: `{manifest['execution_mode']}`",
            f"- planning version: `{manifest['planning_version']}`",
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
        ]
    )


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
