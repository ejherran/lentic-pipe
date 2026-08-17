#!/usr/bin/env python
"""Build the deterministic Closure V1 Phase 4 synthesis bundle.

The real R-SYN transaction is disabled until a published P-SYN authority is
present and validates byte-for-byte.  ``--check-only`` is safe before P-SYN:
it validates H-SYN and the source allowlist without creating the synthesis
namespace.  ``--build`` reads only allowlisted structured artifacts and
publishes exact24 with the bundle manifest last.
"""

from __future__ import annotations

import argparse
import csv
import errno
import html
import io
import json
import os
import re
import secrets
import stat
import sys
from collections.abc import Callable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path, PurePosixPath
from typing import Any, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import lock_closure_synthesis as authority_locker  # noqa: E402
from src.reporting.closure_synthesis_contract import (
    AUTHORITY_MANIFEST_PATH,
    AUTHORITY_PATH,
    GIT_COMMIT_RE,
    PROJECT_ROOT,
    SYNTHESIS_ROOT,
    SynthesisContract,
    SynthesisContractError,
    canonical_json_bytes,
    collect_input_records,
    csv_bytes,
    digest_records,
    digest_strings,
    load_contract,
    sha256_bytes,
    validate_claim_evidence_rows,
    validate_final_closure_rows,
)


GUARD_PATH = Path("tmp/closure_v1_phase4_synthesis/materialization.guard")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_INPUT_BINDINGS: ContextVar[
    Mapping[str, tuple[int, str, int]] | None
] = ContextVar("closure_v1_phase4_expected_input_bindings", default=None)
HYPOTHESIS_REGISTRY = "reports/closure_v1/00_protocol/hypothesis_registry.csv"
LOCKED_EVALUATION_SUMMARY = (
    "reports/closure_v1/01_surface/locked_evaluation_input_summary.json"
)
MODEL_AVAILABILITY = "reports/closure_v1/03_calibration/model_availability.csv"
BENCHMARK_MANIFEST = "reports/closure_v1/01_benchmark/benchmark_manifest.json"
MODEL_METRICS = "reports/closure_v1/01_benchmark/model_metrics_long.csv"
MODEL_COMPARISON = "reports/closure_v1/01_benchmark/model_comparison_paired.csv"
GENERALIZATION_GAP = "reports/closure_v1/02_site_transfer/generalization_gap.csv"
LOCATION_HOLDOUT_METRICS = (
    "reports/closure_v1/02_site_transfer/location_holdout_metrics.csv"
)
THRESHOLD_PREVALENCE = "reports/closure_v1/03_thresholds/threshold_prevalence.csv"
RANK_STABILITY = "reports/closure_v1/03_thresholds/rank_stability.csv"
TROPHIC_PROXY = "reports/closure_v1/04_trophic/trophic_proxy_metrics.csv"
CARLSON_METRICS = "reports/closure_v1/04_trophic/carlson_reference_metrics.csv"
NLA_SEMANTIC_METRICS = "reports/closure_v1/04_trophic/nla_semantic_metrics.csv"
MULTIPLICITY_REPORT = "reports/closure_v1/05_inference/multiplicity_report.csv"
FAILURE_REGISTRY = "reports/closure_v1/06_degradation/failure_registry.csv"
ABLATION_METRICS = "reports/closure_v1/07_anfis_ablation_evaluation/ablation_metrics.csv"
ABLATION_PAIRWISE = "reports/closure_v1/07_anfis_ablation_evaluation/ablation_pairwise.csv"
LEARNING_CURVE = "reports/closure_v1/07_anfis_ablation_evaluation/anfis_learning_curve.csv"
MEMBERSHIP_STABILITY = "reports/closure_v1/07_anfis_ablation_evaluation/membership_stability.csv"
UNCERTAINTY_LEDGER = "reports/closure_v1/08_uncertainty/uncertainty_ledger.csv"
CONDITIONAL_COVERAGE = "reports/closure_v1/08_uncertainty/conditional_coverage.csv"
PLANNING_BOOTSTRAP = "reports/closure_v1/09_planning/planning_bootstrap.csv"
PLANNING_SENSITIVITY = "reports/closure_v1/09_planning/planning_sensitivity.csv"
API_ENVIRONMENT = "reports/closure_v1/10_api/environment.json"
API_OPENAPI = "reports/closure_v1/10_api/openapi.json"
SOFTWARE_MANIFEST = (
    "reports/closure_v1/00_protocol/software_evidence_source_recovery_2/"
    "software_evidence_source_manifest.json"
)
E0_U_ACTIVATION = (
    "reports/closure_v1/00_protocol/closure_e0_u_activation.json"
)
E0_U_ATTEMPT_1_FAILURE = (
    "reports/closure_v1/00_protocol/closure_e0_u_attempt_1_failure.json"
)
E0_U_RECOVERY_ACTIVATION = (
    "reports/closure_v1/00_protocol/closure_e0_u_recovery_activation.json"
)
E0_U_ATTEMPT_2_FAILURE = (
    "reports/closure_v1/00_protocol/closure_e0_u_attempt_2_failure.json"
)
E0_U_RECOVERY_2_ACTIVATION = (
    "reports/closure_v1/00_protocol/closure_e0_u_recovery_2_activation.json"
)
PHASE3_U3_COMMIT = "d72bb727f7d524bb423cb7cbaf425104291b7f31"
PHASE3_H4_COMMIT = "d53eaef9eb5aaf90fe02c8e337346879f6403c4d"


ADJUDICATION = {
    "H1": {
        "text": "Interpretable and usable ANFIS",
        "experiments": "E7;E4",
        "verdict": "limited_descriptive_support",
        "limitation": "NO_SATURATION_OR_MEMBERSHIP_STABILITY_EVIDENCE",
    },
    "H2": {
        "text": "PIPE temporal signal",
        "experiments": "E1;E2",
        "verdict": "not_estimable_primary_architecture",
        "limitation": "P0_P1_MODEL_UNAVAILABLE",
    },
    "H3": {
        "text": "Uncertainty and degradation",
        "experiments": "E8;E6",
        "verdict": "partial_descriptive_only",
        "limitation": "CONFIRMATORY_P1_AND_E6_NOT_ESTIMABLE",
    },
    "H4": {
        "text": "MIFAL as a robustness contrast",
        "experiments": "E6",
        "verdict": "not_estimable",
        "limitation": "NO_M0_P1_SHARED_SUCCESS",
    },
    "H5a": {
        "text": "Planning capability",
        "experiments": "E9",
        "verdict": "not_confirmed_scientifically",
        "limitation": "NO_SHARED_SUCCESS_OR_ESTIMABLE_RANKING",
    },
    "H5b": {
        "text": "Net planning benefit",
        "experiments": "E9",
        "verdict": "not_estimable",
        "limitation": "NET_BENEFIT_ENDPOINT_NOT_REGISTERED",
    },
}

MODEL_IDS = ("B0", "B1", "B2", "F0", "F1", "P0", "P1", "M0", "A0", "A1", "A2")
TROPHIC_ENDPOINTS = (
    "macro_f1",
    "quadratic_weighted_kappa",
    "ordinal_mae",
    "severe_error_rate",
)
FINAL_MATRIX_OUTPUT = "reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv"
T07_OUTPUT = (
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T07_trophic_performance.csv"
)
T09_OUTPUT = "reports/closure_v1/11_synthesis/THESIS_TABLES/T09_anfis_ablation.csv"
T12_OUTPUT = (
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T12_software_evidence.csv"
)
FIVE_SEED_SLOTS = {"1729", "20260612", "20260613", "20260614", "314159"}
EXPECTED_RUNTIME_VERSIONS = {
    "python": "3.14.7",
    "fastapi": "0.138.1",
    "dvc": "3.67.1",
}


class SynthesisBuildError(SynthesisContractError):
    """Raised when R-SYN cannot be built without violating its authority."""


def _error(message: str) -> SynthesisBuildError:
    return SynthesisBuildError(message)


def _decode_json(payload: bytes, *, context: str) -> Mapping[str, Any]:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise _error(f"Invalid JSON: {context}") from exc
    if not isinstance(decoded, Mapping):
        raise _error(f"JSON must contain an object: {context}")
    return cast(Mapping[str, Any], decoded)


def _allowed_path(
    contract: SynthesisContract, root: Path, path_text: str
) -> tuple[Path, os.stat_result]:
    if path_text not in contract.allowed_input_paths:
        raise _error(f"Builder attempted a non-allowlisted read: {path_text}")
    relative = Path(path_text)
    cursor = root
    for part in relative.parts[:-1]:
        cursor = cursor / part
        try:
            parent_metadata = cursor.lstat()
        except OSError as exc:
            raise _error(f"Builder input parent is absent: {cursor}") from exc
        if cursor.is_symlink() or not stat.S_ISDIR(parent_metadata.st_mode):
            raise _error(
                f"Builder input parent must be a non-symlink directory: {cursor}"
            )
    path = cursor / relative.parts[-1]
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise _error(f"Builder input is not a regular file: {path_text}")
    if metadata.st_nlink != 1:
        raise _error(f"Builder input must be single-link: {path_text}")
    return path, metadata


def _read_allowed_bytes(
    contract: SynthesisContract, root: Path, path_text: str
) -> bytes:
    path, expected = _allowed_path(contract, root, path_text)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        expected_bindings = _EXPECTED_INPUT_BINDINGS.get()
        binding = (
            expected_bindings.get(path_text)
            if expected_bindings is not None
            else None
        )
        if expected_bindings is not None and binding is None:
            raise _error(f"P-SYN does not bind builder input: {path_text}")
        if (
            not stat.S_ISREG(before.st_mode)
            or (before.st_dev, before.st_ino) != (expected.st_dev, expected.st_ino)
            or (
                binding is not None
                and stat.S_IMODE(before.st_mode) != binding[2]
            )
        ):
            raise _error(f"Builder input identity changed before read: {path_text}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_nlink,
            stat.S_IMODE(after.st_mode),
        ) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            before.st_nlink,
            stat.S_IMODE(before.st_mode),
        ):
            raise _error(f"Builder input identity changed during read: {path_text}")
        payload = b"".join(chunks)
        if binding is not None and (
            len(payload) != binding[0] or sha256_bytes(payload) != binding[1]
        ):
            raise _error(f"Builder input bytes differ from P-SYN: {path_text}")
        return payload
    finally:
        os.close(descriptor)


def _read_allowed_json(
    contract: SynthesisContract, root: Path, path_text: str
) -> Mapping[str, Any]:
    payload = _read_allowed_bytes(contract, root, path_text)
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise _error(f"Invalid JSON: {path_text}") from exc
    if not isinstance(decoded, Mapping):
        raise _error(f"JSON must contain an object: {path_text}")
    return cast(Mapping[str, Any], decoded)


def _read_allowed_csv(
    contract: SynthesisContract, root: Path, path_text: str
) -> list[dict[str, str]]:
    payload = _read_allowed_bytes(contract, root, path_text)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _error(f"CSV is not UTF-8: {path_text}") from exc
    with io.StringIO(text, newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        if any(field is None or not field for field in reader.fieldnames):
            raise _error(f"CSV has an invalid header: {path_text}")
        return [dict(row) for row in reader]


def _decimal(value: str, places: int = 4) -> str:
    if value == "":
        return ""
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise _error(f"Cannot round non-decimal value: {value!r}") from exc
    quantum = Decimal(1).scaleb(-places)
    rendered = format(number.quantize(quantum, rounding=ROUND_HALF_EVEN), "f")
    if Decimal(rendered) == 0:
        return format(Decimal(0).quantize(quantum), "f")
    return rendered


def _matrix_row(
    contract: SynthesisContract,
    *,
    hypothesis_id: str,
    estimand: str,
    population: str,
    model_or_pair: str,
    availability_state: str,
    attempted: str | int,
    successful: str | int,
    metric: str,
    estimate: str = "",
    uncertainty: str = "",
    family: str = "",
    evidence: Sequence[str],
    limitation: str | None = None,
) -> dict[str, str]:
    base_id = hypothesis_id.split(":", 1)[0]
    adjudication = ADJUDICATION[base_id]
    values = {
        "hypothesis_id": hypothesis_id,
        "hypothesis_text": adjudication["text"],
        "decisive_experiments": adjudication["experiments"],
        "estimand": estimand,
        "population": population,
        "model_or_pair": model_or_pair,
        "availability_state": availability_state,
        "attempted_denominator": str(attempted),
        "successful_denominator": str(successful),
        "metric": metric,
        "estimate": estimate,
        "uncertainty": uncertainty,
        "multiplicity_family": family,
        "verdict": adjudication["verdict"],
        "limitation_code": limitation or adjudication["limitation"],
        "evidence_paths": ";".join(evidence),
        "authority_commit": contract.closure_source_commit,
    }
    return {column: values[column] for column in contract.final_closure_columns}


def _registry_plan_hypothesis(registry_id: str) -> str:
    if registry_id.startswith("H1_") or registry_id.startswith("H_surface_"):
        return "H1"
    if registry_id.startswith("H2_"):
        return "H2"
    if registry_id.startswith("H_D_"):
        return "H5a"
    if registry_id.startswith("H_E_"):
        return "H3"
    if registry_id.startswith("H4_"):
        return "H4"
    raise _error(f"Unknown registered hypothesis: {registry_id}")


def _unique_by(
    rows: Sequence[Mapping[str, str]], key: str, *, context: str
) -> dict[str, Mapping[str, str]]:
    indexed: dict[str, Mapping[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if not value or value in indexed:
            raise _error(f"{context} has a missing or duplicated {key}")
        indexed[value] = row
    return indexed


def _mean_source_value(
    rows: Sequence[Mapping[str, str]], column: str, *, source: str
) -> Decimal:
    if not rows:
        raise _error(f"Cannot summarize an empty source group: {source}")
    values: list[Decimal] = []
    for row in rows:
        raw = row.get(column, "")
        try:
            value = Decimal(raw)
        except InvalidOperation as exc:
            raise _error(f"Invalid {column} in {source}: {raw!r}") from exc
        if not value.is_finite():
            raise _error(f"Non-finite {column} in {source}")
        values.append(value)
    return sum(values, Decimal(0)) / Decimal(len(values))


@dataclass(frozen=True)
class _BenchmarkCell:
    attempted: int
    successful: int
    evaluable: int
    success_rate: Decimal
    evaluable_rate: Decimal
    terminal_status: str
    values: tuple[Decimal, ...]


def _benchmark_cell(
    rows: Sequence[Mapping[str, str]],
    *,
    model_id: str,
    horizon: int,
    estimand: str,
    metric: str,
) -> _BenchmarkCell:
    selected = [
        row
        for row in rows
        if row.get("model_id") == model_id
        and row.get("horizon_months") == str(horizon)
        and row.get("estimand") == estimand
        and row.get("metric") == metric
        and row.get("evaluation_cohort") == "location_holdout"
    ]
    if not selected and model_id == "A2":
        return _BenchmarkCell(
            attempted=0,
            successful=0,
            evaluable=0,
            success_rate=Decimal(0),
            evaluable_rate=Decimal(0),
            terminal_status="not_attempted_no_slots",
            values=(),
        )
    if len(selected) != 5 or {row.get("seed_slot") for row in selected} != FIVE_SEED_SLOTS:
        raise _error(
            "Benchmark availability cell lost its exact five-slot ledger: "
            f"{model_id}/h{horizon}/{estimand}/{metric}"
        )
    statuses = {row.get("terminal_status", "") for row in selected}
    if len(statuses) != 1 or statuses.pop() not in {"estimated", "not_estimable"}:
        raise _error(
            "Benchmark availability cell has inconsistent terminal states: "
            f"{model_id}/h{horizon}/{estimand}/{metric}"
        )
    terminal_status = selected[0]["terminal_status"]
    attempted = sum(
        _integer(row, "origin_count", source=MODEL_METRICS) for row in selected
    )
    successful = sum(
        _integer(row, "successful_origin_count", source=MODEL_METRICS)
        for row in selected
    )
    evaluable = sum(
        _integer(row, "metric_evaluable_origin_count", source=MODEL_METRICS)
        for row in selected
    )
    if attempted != 5 * 4488 or not 0 <= evaluable <= successful <= attempted:
        raise _error(
            "Benchmark availability denominators drifted: "
            f"{model_id}/h{horizon}/{estimand}/{metric}"
        )
    values = tuple(
        _numeric(row, "value", source=MODEL_METRICS)
        for row in selected
        if row.get("value", "")
    )
    if (terminal_status == "estimated") != (len(values) == 5):
        raise _error(
            "Benchmark values disagree with terminal status: "
            f"{model_id}/h{horizon}/{estimand}/{metric}"
        )
    return _BenchmarkCell(
        attempted=attempted,
        successful=successful,
        evaluable=evaluable,
        success_rate=Decimal(successful) / Decimal(attempted),
        evaluable_rate=Decimal(evaluable) / Decimal(attempted),
        terminal_status=terminal_status,
        values=values,
    )


def _median(values: Sequence[Decimal], *, context: str) -> Decimal:
    if not values:
        raise _error(f"Cannot compute an empty median: {context}")
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal(2)


@dataclass(frozen=True)
class _E8PrimaryDiagnostics:
    group_count: int
    raw_within_margin: int
    locked_within_margin: int
    locked_closer: int
    locked_wider: int
    raw_mean_absolute_error: Decimal
    raw_median_absolute_error: Decimal
    locked_mean_absolute_error: Decimal
    locked_median_absolute_error: Decimal


def _e8_primary_diagnostics(
    rows: Sequence[Mapping[str, str]],
) -> _E8PrimaryDiagnostics:
    selected = [
        row
        for row in rows
        if row.get("model_id") in {"A0", "A1"}
        and abs(_numeric(row, "nominal_coverage", source=UNCERTAINTY_LEDGER) - Decimal("0.9"))
        <= Decimal("1e-12")
    ]
    paired: dict[tuple[str, str, str], dict[str, Mapping[str, str]]] = {}
    for row in selected:
        version = row.get("interval_version", "")
        if version not in {"raw_gaussian", "locked_conformal"}:
            raise _error("E8 primary ledger contains an unknown interval version")
        if row.get("status") != "available":
            raise _error("E8 primary ledger contains an unavailable interval cell")
        key = (row["model_id"], row["seed_slot"], row["horizon_months"])
        versions = paired.setdefault(key, {})
        if version in versions:
            raise _error("E8 primary ledger duplicated a model/seed/horizon/version cell")
        versions[version] = row
    if len(paired) != 30 or any(
        set(versions) != {"raw_gaussian", "locked_conformal"}
        for versions in paired.values()
    ):
        raise _error("E8 raw/locked primary ledger drifted from exact30 paired groups")

    raw_errors: list[Decimal] = []
    locked_errors: list[Decimal] = []
    locked_closer = 0
    locked_wider = 0
    for versions in paired.values():
        raw = versions["raw_gaussian"]
        locked = versions["locked_conformal"]
        for column in ("attempted_row_count", "success_row_count", "interval_row_count"):
            if raw[column] != locked[column]:
                raise _error(f"E8 paired denominator drifted: {column}")
        raw_error = _numeric(raw, "absolute_coverage_error", source=UNCERTAINTY_LEDGER)
        locked_error = _numeric(
            locked, "absolute_coverage_error", source=UNCERTAINTY_LEDGER
        )
        raw_errors.append(raw_error)
        locked_errors.append(locked_error)
        locked_closer += locked_error < raw_error
        locked_wider += _numeric(
            locked, "mean_interval_width", source=UNCERTAINTY_LEDGER
        ) > _numeric(raw, "mean_interval_width", source=UNCERTAINTY_LEDGER)

    diagnostics = _E8PrimaryDiagnostics(
        group_count=len(paired),
        raw_within_margin=sum(error <= Decimal("0.05") for error in raw_errors),
        locked_within_margin=sum(
            error <= Decimal("0.05") for error in locked_errors
        ),
        locked_closer=locked_closer,
        locked_wider=locked_wider,
        raw_mean_absolute_error=_mean(raw_errors, context="E8 raw absolute errors"),
        raw_median_absolute_error=_median(raw_errors, context="E8 raw absolute errors"),
        locked_mean_absolute_error=_mean(
            locked_errors, context="E8 locked absolute errors"
        ),
        locked_median_absolute_error=_median(
            locked_errors, context="E8 locked absolute errors"
        ),
    )
    observed = (
        diagnostics.raw_within_margin,
        diagnostics.locked_within_margin,
        diagnostics.locked_closer,
        diagnostics.locked_wider,
        _decimal(format(diagnostics.raw_mean_absolute_error, "f"), 6),
        _decimal(format(diagnostics.raw_median_absolute_error, "f"), 6),
        _decimal(format(diagnostics.locked_mean_absolute_error, "f"), 6),
        _decimal(format(diagnostics.locked_median_absolute_error, "f"), 6),
    )
    expected = (30, 26, 5, 30, "0.015565", "0.013386", "0.032271", "0.030872")
    if observed != expected:
        raise _error(f"E8 raw/locked paired diagnostics drifted: {observed}")
    return diagnostics


def _validated_runtime_versions(environment: Mapping[str, Any]) -> dict[str, str]:
    runtime = environment.get("runtime")
    tool_versions = environment.get("tool_versions")
    if not isinstance(runtime, Mapping) or not isinstance(tool_versions, Mapping):
        raise _error("E10 runtime/tool-version evidence is malformed")
    python_runtime = str(environment.get("python", "")).split(" ", 1)[0]
    python_tool = str(tool_versions.get("python_version", "")).removeprefix("Python ")
    observed = {
        "python": python_runtime,
        "fastapi": str(runtime.get("fastapi", "")),
        "dvc": str(tool_versions.get("dvc_version", "")),
    }
    if (
        observed != EXPECTED_RUNTIME_VERSIONS
        or python_tool != EXPECTED_RUNTIME_VERSIONS["python"]
        or environment.get("python_implementation") != "CPython"
    ):
        raise _error(f"E10 runtime versions drifted: {observed}")
    return observed


def _b2_better_reference_cells(
    rows: Sequence[Mapping[str, str]], *, source: str
) -> tuple[int, int]:
    references = sorted({row["reference"] for row in rows})
    attempted = 0
    successful = 0
    for reference in references:
        for horizon in ("1", "2", "3"):
            means: dict[str, dict[str, Decimal]] = {}
            for model_id in ("B1", "B2"):
                selected = [
                    row
                    for row in rows
                    if row["reference"] == reference
                    and row["horizon_months"] == horizon
                    and row["model_id"] == model_id
                    and row["status"] == "available"
                ]
                if len(selected) != 5 or len({row["seed_slot"] for row in selected}) != 5:
                    raise _error(
                        f"{source} lost an exact five-seed B1/B2 reference cell"
                    )
                means[model_id] = {
                    metric: _mean_source_value(selected, metric, source=source)
                    for metric in TROPHIC_ENDPOINTS
                }
            attempted += 1
            if (
                means["B2"]["macro_f1"] > means["B1"]["macro_f1"]
                and means["B2"]["quadratic_weighted_kappa"]
                > means["B1"]["quadratic_weighted_kappa"]
                and means["B2"]["ordinal_mae"] < means["B1"]["ordinal_mae"]
                and means["B2"]["severe_error_rate"]
                < means["B1"]["severe_error_rate"]
            ):
                successful += 1
    return attempted, successful


def build_final_closure_rows(
    contract: SynthesisContract, *, root: Path = PROJECT_ROOT
) -> list[dict[str, str]]:
    registry = _read_allowed_csv(contract, root, HYPOTHESIS_REGISTRY)
    multiplicity = _read_allowed_csv(contract, root, MULTIPLICITY_REPORT)
    failures = _read_allowed_csv(contract, root, FAILURE_REGISTRY)
    ablation = _read_allowed_csv(contract, root, ABLATION_PAIRWISE)
    uncertainty = _read_allowed_csv(contract, root, UNCERTAINTY_LEDGER)
    generalization = _read_allowed_csv(contract, root, GENERALIZATION_GAP)
    trophic = _read_allowed_csv(contract, root, TROPHIC_PROXY)
    carlson = _read_allowed_csv(contract, root, CARLSON_METRICS)
    learning = _read_allowed_csv(contract, root, LEARNING_CURVE)
    membership = _read_allowed_csv(contract, root, MEMBERSHIP_STABILITY)
    surface = _read_allowed_json(contract, root, LOCKED_EVALUATION_SUMMARY)
    planning_rows = _read_allowed_csv(contract, root, PLANNING_BOOTSTRAP)
    planning = _unique_by(planning_rows, "scenario_id", context=PLANNING_BOOTSTRAP)

    registry_by_id = _unique_by(
        registry, "hypothesis_id", context=HYPOTHESIS_REGISTRY
    )
    multiplicity_by_id = _unique_by(
        multiplicity, "hypothesis_id", context=MULTIPLICITY_REPORT
    )
    if set(registry_by_id) != set(multiplicity_by_id) or len(registry) != 27:
        raise _error("E5 registry and multiplicity report lost their exact bijection")
    registered_family_counts: dict[str, int] = {}
    for hypothesis_id, source in registry_by_id.items():
        family = source["multiplicity_family"]
        registered_family_counts[family] = registered_family_counts.get(family, 0) + 1
        ledger = multiplicity_by_id[hypothesis_id]
        if (
            ledger["multiplicity_family"] != family
            or ledger["multiplicity_universe_size"]
            != source["multiplicity_universe_size"]
            or source["status"] != "not_estimable_model_unavailable"
            or ledger["terminal_status"] != "not_estimable_model_unavailable"
            or any(
                source[field]
                for field in ("p_value", "effect_estimate", "confidence_interval")
            )
            or ledger["raw_p_value"]
            or ledger["holm_p_value"]
            or source["holm_universe_retained"].lower() != "true"
            or ledger["holm_universe_retained"].lower() != "true"
        ):
            raise _error(f"E5 registry/ledger drift for {hypothesis_id}")
        if int(source["multiplicity_universe_size"]) != contract.holm_universes[family]:
            raise _error(f"E5 Holm universe drift for {hypothesis_id}")
    if registered_family_counts != {"A": 3, "B": 13, "C": 1, "D": 9, "E": 1}:
        raise _error("E5 registered hypothesis membership drifted")

    try:
        origin_count = int(str(surface["origin_count"]))
        holdout_count = int(str(surface["holdout_location_count"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise _error("Locked evaluation surface counts drifted") from exc
    if (
        origin_count != 4488
        or holdout_count != 88
        or surface.get("input_only") is not True
        or surface.get("outcome_paths_opened") is not False
    ):
        raise _error("Locked evaluation input-only surface drifted")
    intent_attempts = origin_count * 3

    rows: list[dict[str, str]] = []

    for source in registry:
        family = source["multiplicity_family"]
        if family == "B":
            continue
        plan_hypothesis = _registry_plan_hypothesis(source["hypothesis_id"])
        comparison = source["comparison_id"]
        attempted = intent_attempts
        if family == "D":
            scenario = comparison.removesuffix("_vs_no_action")
            planned = planning.get(scenario)
            if (
                planned is None
                or planned["status"] != "model_unavailable"
                or planned["row_count"] != str(intent_attempts)
            ):
                raise _error(f"Planning action is absent: {scenario}")
            attempted = int(planned["row_count"])
        evidence = [HYPOTHESIS_REGISTRY, MULTIPLICITY_REPORT]
        if plan_hypothesis == "H1":
            evidence.extend((ABLATION_PAIRWISE, TROPHIC_PROXY))
        elif plan_hypothesis == "H2":
            evidence.extend((MODEL_COMPARISON, GENERALIZATION_GAP))
        elif plan_hypothesis == "H3":
            evidence.extend((UNCERTAINTY_LEDGER, FAILURE_REGISTRY))
        elif plan_hypothesis == "H5a":
            evidence.extend((PLANNING_BOOTSTRAP, PLANNING_SENSITIVITY))
        rows.append(
            _matrix_row(
                contract,
                hypothesis_id=f"{plan_hypothesis}:{source['hypothesis_id']}",
                estimand=source["estimand"],
                population=source["evaluation_cohort"],
                model_or_pair=comparison,
                availability_state="model_unavailable",
                attempted=attempted,
                successful=0,
                metric=source["endpoints"],
                family=family,
                evidence=evidence,
                limitation=(
                    "A2_AND_P1_MODEL_UNAVAILABLE"
                    if family == "C"
                    else (
                        "P0_AND_P1_MODEL_UNAVAILABLE_NO_PRIMARY_"
                        "ARCHITECTURE_COMPARISON"
                        if plan_hypothesis == "H1"
                        else None
                    )
                ),
            )
        )
        if family == "D":
            rows.append(
                _matrix_row(
                    contract,
                    hypothesis_id=f"H5b:{source['hypothesis_id']}",
                    estimand=source["estimand"],
                    population=source["evaluation_cohort"],
                    model_or_pair=comparison,
                    availability_state="not_applicable",
                    attempted=attempted,
                    successful=0,
                    metric=source["endpoints"],
                    evidence=evidence,
                    limitation="NET_BENEFIT_ENDPOINT_NOT_REGISTERED_NO_CAUSAL_OR_UTILITY_ESTIMAND",
                )
            )

    expected_failure_cells = {
        (
            source["comparison_id"].removeprefix("M0_vs_P1_"),
            horizon,
            target,
        )
        for source in registry
        if source["multiplicity_family"] == "B"
        for horizon in ("1", "2", "3")
        for target in ("bloom_h", "irc_alert_h")
    }
    observed_failure_cells = {
        (row["scenario_id"], row["horizon_months"], row["target_event"])
        for row in failures
    }
    if (
        len(failures) != 78
        or observed_failure_cells != expected_failure_cells
        or any(
            row["terminal_status"] != "model_unavailable"
            or row["missing_model_id"] != "P1"
            or row["estimable"].lower() != "false"
            or row["available_prediction_row_count"] != "0"
            for row in failures
        )
    ):
        raise _error("E6 failure registry drifted from the exact78 Holm cells")
    for failure in failures:
        rows.append(
            _matrix_row(
                contract,
                hypothesis_id=(
                    "H4:"
                    f"{failure['scenario_id']}:h{failure['horizon_months']}:"
                    f"{failure['target_event']}"
                ),
                estimand="paired_five_seed_mean_delta_by_scenario_horizon_endpoint",
                population=failure["evaluation_cohort"],
                model_or_pair=(
                    "M0_vs_P1:"
                    f"{failure['scenario_id']}:h{failure['horizon_months']}:"
                    f"{failure['target_event']}"
                ),
                availability_state="model_unavailable",
                attempted=failure["intended_prediction_row_count"],
                successful=failure["available_prediction_row_count"],
                metric=failure["target_event"],
                family="B",
                evidence=[HYPOTHESIS_REGISTRY, FAILURE_REGISTRY, MULTIPLICITY_REPORT],
            )
        )

    a1_a0 = [
        source
        for source in ablation
        if source["challenger_model_id"] == "A1"
        and source["reference_model_id"] == "A0"
    ]
    if (
        len(a1_a0) != 3
        or {source["horizon_months"] for source in a1_a0} != {"1", "2", "3"}
        or any(source["status"] != "available" for source in a1_a0)
    ):
        raise _error("E7 A1-A0 exact-common-row contrasts drifted")
    for source in a1_a0:
        for metric in ("delta_pr_auc", "delta_brier", "delta_mae"):
            rows.append(
                _matrix_row(
                    contract,
                    hypothesis_id=f"H1:A1_vs_A0:h{source['horizon_months']}:{metric}",
                    estimand="descriptive_exact_common_rows",
                    population=source["evaluation_cohort"],
                    model_or_pair=f"A1_vs_A0:h{source['horizon_months']}",
                    availability_state="descriptive_available",
                    attempted=source["common_row_count"],
                    successful=source["common_row_count"],
                    metric=metric,
                    estimate=_decimal(source[metric]),
                    evidence=[ABLATION_PAIRWISE],
                )
            )

    proxy_rows = [
        row
        for row in trophic
        if row["model_id"] in {"B1", "B2"} and row["status"] == "available"
    ]
    if len(proxy_rows) != 30 or {row["reference"] for row in proxy_rows} != {
        "future_chla_operational_proxy"
    }:
        raise _error("E4 B1/B2 operational-proxy cells drifted")
    for horizon in ("1", "2", "3"):
        by_model: dict[str, list[dict[str, str]]] = {}
        for model_id in ("B1", "B2"):
            selected = [
                row
                for row in proxy_rows
                if row["model_id"] == model_id
                and row["horizon_months"] == horizon
            ]
            if len(selected) != 5 or len({row["seed_slot"] for row in selected}) != 5:
                raise _error("E4 proxy comparison lost an exact five-seed cell")
            by_model[model_id] = selected
        for metric in TROPHIC_ENDPOINTS:
            delta = _mean_source_value(
                by_model["B2"], metric, source=TROPHIC_PROXY
            ) - _mean_source_value(by_model["B1"], metric, source=TROPHIC_PROXY)
            rows.append(
                _matrix_row(
                    contract,
                    hypothesis_id=f"H1:B2_vs_B1:proxy:h{horizon}:{metric}",
                    estimand="descriptive_five_seed_mean_difference",
                    population="location_holdout_future_chla_operational_proxy",
                    model_or_pair=f"B2_vs_B1:proxy:h{horizon}",
                    availability_state="descriptive_available",
                    attempted=5,
                    successful=5,
                    metric=f"delta_{metric}_B2_minus_B1",
                    estimate=_decimal(format(delta, "f")),
                    evidence=[TROPHIC_PROXY],
                    limitation=(
                        "AUXILIARY_B1_B2_TROPHIC_CONTEXT_DOES_NOT_VALIDATE_"
                        "THE_PRIMARY_ANFIS_BRANCH_OR_EXTERNAL_TRANSFER"
                    ),
                )
            )

    expected_carlson_references = {"tsi_tp_h", "tsi_sd_h", "tsi_non_chla_h", "tsi_all_h"}
    if {row["reference"] for row in carlson} != expected_carlson_references:
        raise _error("E4 Carlson reference membership drifted")
    carlson_attempted, carlson_successful = _b2_better_reference_cells(
        carlson, source=CARLSON_METRICS
    )
    if (carlson_attempted, carlson_successful) != (12, 12):
        raise _error("E4 B2-vs-B1 Carlson direction summary drifted")
    rows.append(
        _matrix_row(
            contract,
            hypothesis_id="H1:B2_vs_B1:Carlson:direction_summary",
            estimand="descriptive_reference_horizon_direction_count",
            population="location_holdout_four_Carlson_references",
            model_or_pair="B2_vs_B1:Carlson_references",
            availability_state="descriptive_available",
            attempted=carlson_attempted,
            successful=carlson_successful,
            metric="reference_horizon_cells_B2_better_on_all_four_ordinal_metrics",
            estimate=_decimal(
                format(Decimal(carlson_successful) / Decimal(carlson_attempted), "f")
            ),
            evidence=[CARLSON_METRICS],
            limitation=(
                "AUXILIARY_B1_B2_CARLSON_CONTEXT_DOES_NOT_VALIDATE_THE_"
                "PRIMARY_ANFIS_BRANCH_OR_EXTERNAL_TRANSFER"
            ),
        )
    )

    if (
        len(generalization) != 1050
        or any(row["estimable"].lower() != "false" for row in generalization)
        or {row["not_estimable_reason"] for row in generalization}
        != {"legacy_evaluation_surface_not_frozen_before_e0_u"}
    ):
        raise _error("E2 site-transfer non-estimability ledger drifted")
    rows.append(
        _matrix_row(
            contract,
            hypothesis_id="H2:E2:legacy_vs_locked_site_transfer",
            estimand="registered_legacy_to_locked_holdout_generalization_gap",
            population="location_holdout_all_registered_available_and_unavailable_models",
            model_or_pair="legacy_surface_vs_locked_location_holdout",
            availability_state="insufficient_support",
            attempted=len(generalization),
            successful=0,
            metric="estimable_site_transfer_cells",
            evidence=[GENERALIZATION_GAP],
            limitation="LEGACY_EVALUATION_SURFACE_NOT_FROZEN_BEFORE_E0_U",
        )
    )

    rows.append(
        _matrix_row(
            contract,
            hypothesis_id="H3:E6:degradation_summary",
            estimand="registered_degradation_cell_availability",
            population="location_holdout_thirteen_scenarios_three_horizons_two_events",
            model_or_pair="M0_vs_P1:all_registered_degradation_cells",
            availability_state="model_unavailable",
            attempted=len(failures),
            successful=0,
            metric="estimable_degradation_cells",
            evidence=[FAILURE_REGISTRY],
            limitation="P1_MODEL_UNAVAILABLE_ALL_78_CELLS",
        )
    )

    e8 = _e8_primary_diagnostics(uncertainty)
    rows.append(
        _matrix_row(
            contract,
            hypothesis_id="H3:locked_conformal_primary_groups",
            estimand="descriptive_group_coverage_within_absolute_margin_0.05",
            population="locked_location_holdout_A0_A1_five_seeds_three_horizons",
            model_or_pair="A0_and_A1_locked_conformal",
            availability_state="descriptive_available",
            attempted=e8.group_count,
            successful=e8.locked_within_margin,
            metric="groups_within_nominal_margin",
            estimate=_decimal(
                str(Decimal(e8.locked_within_margin) / Decimal(e8.group_count))
            ),
            evidence=[UNCERTAINTY_LEDGER],
        )
    )

    expected_training_rows = ("4096", "16384", "65536")
    if (
        tuple(row["training_rows_per_module"] for row in learning)
        != expected_training_rows
        or any(
            row["status"] != "not_available"
            or row["saturation_claim_authorized"].lower() != "false"
            for row in learning
        )
    ):
        raise _error("E7 learning-curve sentinel drifted")
    for source in learning:
        rows.append(
            _matrix_row(
                contract,
                hypothesis_id=f"H1:E7:learning_curve:{source['training_rows_per_module']}",
                estimand="predeclared_training_size_saturation_diagnostic",
                population="closure_v1_development_ANFIS_modules",
                model_or_pair=f"A1:training_rows_{source['training_rows_per_module']}",
                availability_state="insufficient_support",
                attempted=1,
                successful=0,
                metric="learning_curve_completed",
                evidence=[LEARNING_CURVE],
                limitation="TRAINING_SIZE_NOT_COMPLETED_NO_SATURATION_CLAIM",
            )
        )
    if len(membership) != 1 or membership[0]["status"] != "not_available":
        raise _error("E7 membership-stability sentinel drifted")
    rows.append(
        _matrix_row(
            contract,
            hypothesis_id="H1:E7:membership_stability",
            estimand="five_seed_membership_parameter_stability",
            population="closure_v1_development_ANFIS_modules",
            model_or_pair="A1:membership_parameters_across_five_seeds",
            availability_state="insufficient_support",
            attempted=1,
            successful=0,
            metric="membership_stability_completed",
            evidence=[MEMBERSHIP_STABILITY],
            limitation="MEMBERSHIP_STABILITY_NOT_AVAILABLE",
        )
    )

    rows.sort(
        key=lambda row: (
            row["hypothesis_id"],
            row["metric"],
            row["estimand"],
            row["model_or_pair"],
        )
    )
    if len(rows) != contract.final_closure_row_count:
        raise _error(
            "FINAL_CLOSURE_MATRIX row count drifted from "
            f"exact{contract.final_closure_row_count}"
        )
    if not {
        "model_unavailable",
        "descriptive_available",
        "insufficient_support",
        "not_applicable",
    }.issubset({row["availability_state"] for row in rows}):
        raise _error("FINAL_CLOSURE_MATRIX collapsed required non-binary states")
    validate_final_closure_rows(rows, contract)
    return rows


def build_claim_evidence_rows(
    contract: SynthesisContract, *, root: Path = PROJECT_ROOT
) -> list[dict[str, str]]:
    surface = _read_allowed_json(contract, root, LOCKED_EVALUATION_SUMMARY)
    availability = _read_allowed_csv(contract, root, MODEL_AVAILABILITY)
    metrics = _read_allowed_csv(contract, root, MODEL_METRICS)
    comparisons = _read_allowed_csv(contract, root, MODEL_COMPARISON)
    ablation = _read_allowed_csv(contract, root, ABLATION_PAIRWISE)
    generalization = _read_allowed_csv(contract, root, GENERALIZATION_GAP)
    prevalence = _read_allowed_csv(contract, root, THRESHOLD_PREVALENCE)
    trophic = _read_allowed_csv(contract, root, TROPHIC_PROXY)
    carlson = _read_allowed_csv(contract, root, CARLSON_METRICS)
    failures = _read_allowed_csv(contract, root, FAILURE_REGISTRY)
    learning = _read_allowed_csv(contract, root, LEARNING_CURVE)
    membership = _read_allowed_csv(contract, root, MEMBERSHIP_STABILITY)
    uncertainty = _read_allowed_csv(contract, root, UNCERTAINTY_LEDGER)
    planning = _read_allowed_csv(contract, root, PLANNING_BOOTSTRAP)
    multiplicity = _read_allowed_csv(contract, root, MULTIPLICITY_REPORT)
    software = _read_allowed_json(contract, root, SOFTWARE_MANIFEST)
    environment = _read_allowed_json(contract, root, API_ENVIRONMENT)

    if (
        surface.get("holdout_location_count") != 88
        or surface.get("origin_count") != 4488
        or surface.get("input_only") is not True
    ):
        raise _error("Claim C01 surface facts drifted")
    availability_by_model = _unique_by(
        availability, "model_id", context=MODEL_AVAILABILITY
    )
    if tuple(availability_by_model) != MODEL_IDS or {
        model_id: availability_by_model[model_id]["availability"]
        for model_id in ("P0", "P1", "A2")
    } != {"P0": "unavailable", "P1": "unavailable", "A2": "unavailable"}:
        raise _error("Claim C03 model-availability facts drifted")
    for row in metrics:
        try:
            attempted = int(row["origin_count"])
            terminal_total = sum(
                int(row[column])
                for column in (
                    "successful_origin_count",
                    "input_ineligible_origin_count",
                    "target_unavailable_origin_count",
                    "model_unavailable_origin_count",
                    "numerical_failure_origin_count",
                    "infrastructure_failure_origin_count",
                    "not_applicable_origin_count",
                )
            )
        except (KeyError, ValueError) as exc:
            raise _error("Claim C02 intent-to-predict ledger is malformed") from exc
        if attempted != 4488 or terminal_total != attempted:
            raise _error("Claim C02 intent-to-predict denominator partition drifted")

    def benchmark_means(metric: str, horizon: str) -> dict[str, Decimal]:
        grouped: dict[str, list[dict[str, str]]] = {}
        for model_id in ("A0", "A1", "B0", "B1", "B2", "M0"):
            selected = [
                row
                for row in metrics
                if row["model_id"] == model_id
                and row["horizon_months"] == horizon
                and row["metric"] == metric
                and row["estimand"] == "observation_weighted"
                and row["terminal_status"] == "estimated"
            ]
            if len(selected) != 5:
                raise _error("E1 benchmark lost an exact five-slot metric cell")
            grouped[model_id] = selected
        return {
            model_id: _mean_source_value(rows, "value", source=MODEL_METRICS)
            for model_id, rows in grouped.items()
        }

    brier_means = {
        horizon: benchmark_means("brier", horizon)
        for horizon in ("1", "2", "3")
    }
    pr_auc_means = {
        horizon: benchmark_means("pr_auc", horizon)
        for horizon in ("1", "2", "3")
    }
    brier_winners = {
        horizon: min(values, key=lambda model_id: values[model_id])
        for horizon, values in brier_means.items()
    }
    pr_auc_winners = {
        horizon: max(values, key=lambda model_id: values[model_id])
        for horizon, values in pr_auc_means.items()
    }
    if brier_winners != {"1": "B2", "2": "B2", "3": "B2"}:
        raise _error("Claim C04 observation-weighted Brier ranking drifted")
    if pr_auc_winners != {"1": "A1", "2": "B2", "3": "B2"}:
        raise _error("Claim C05 observation-weighted PR-AUC ranking drifted")
    brier_availability = {
        horizon: _benchmark_cell(
            metrics,
            model_id="B2",
            horizon=int(horizon),
            estimand="observation_weighted",
            metric="brier",
        )
        for horizon in ("1", "2", "3")
    }
    pr_auc_availability = {
        horizon: _benchmark_cell(
            metrics,
            model_id=pr_auc_winners[horizon],
            horizon=int(horizon),
            estimand="observation_weighted",
            metric="pr_auc",
        )
        for horizon in ("1", "2", "3")
    }
    if any(
        cell.terminal_status != "estimated"
        for cell in (*brier_availability.values(), *pr_auc_availability.values())
    ):
        raise _error("Claims C04-C05 winning benchmark cells are not estimable")

    f1_f0 = [
        row
        for row in comparisons
        if row["comparison_id"] == "F1_vs_F0"
        and row["metric"] == "absolute_error"
        and row["terminal_status"] == "estimated"
    ]
    if len(f1_f0) != 15 or any(
        Decimal(row["mean_loss_difference_a_minus_b"]) <= 0 for row in f1_f0
    ):
        raise _error("Claim C06 F1-F0 exact-shared-row direction drifted")
    a1_a0 = [
        row
        for row in ablation
        if row["challenger_model_id"] == "A1"
        and row["reference_model_id"] == "A0"
        and row["status"] == "available"
    ]
    if (
        len(a1_a0) != 3
        or sum(Decimal(row["delta_pr_auc"]) > 0 for row in a1_a0) != 3
        or sum(Decimal(row["delta_brier"]) < 0 for row in a1_a0) != 3
        or sum(Decimal(row["delta_mae"]) < 0 for row in a1_a0) != 2
    ):
        raise _error("Claim C07 A1-A0 descriptive direction drifted")
    if (
        len(generalization) != 1050
        or any(row["estimable"].lower() != "false" for row in generalization)
        or len(learning) != 3
        or any(row["status"] != "not_available" for row in learning)
        or len(membership) != 1
        or membership[0]["status"] != "not_available"
    ):
        raise _error("Claims C08-C09 E2/E7 sentinel facts drifted")
    if len(prevalence) != 12 or {row["threshold_ug_l"] for row in prevalence} != {
        "25",
        "30",
        "33",
        "50",
    }:
        raise _error("Claim C10 threshold sensitivity facts drifted")
    proxy_attempted, proxy_successful = _b2_better_reference_cells(
        trophic, source=TROPHIC_PROXY
    )
    carlson_attempted, carlson_successful = _b2_better_reference_cells(
        carlson, source=CARLSON_METRICS
    )
    if (proxy_attempted, proxy_successful, carlson_attempted, carlson_successful) != (
        3,
        3,
        12,
        12,
    ):
        raise _error("Claim C11 B2-B1 trophic direction drifted")
    e8 = _e8_primary_diagnostics(uncertainty)
    family_membership = {
        family: sum(row["multiplicity_family"] == family for row in multiplicity)
        for family in contract.holm_universes
    }
    if (
        len(failures) != 78
        or any(row["terminal_status"] != "model_unavailable" for row in failures)
        or len(planning) != 9
        or any(row["status"] != "model_unavailable" for row in planning)
        or len(multiplicity) != 27
        or any(row["holm_universe_retained"].lower() != "true" for row in multiplicity)
        or family_membership != {"A": 3, "B": 13, "C": 1, "D": 9, "E": 1}
        or any(
            int(row["multiplicity_universe_size"])
            != contract.holm_universes[row["multiplicity_family"]]
            for row in multiplicity
        )
    ):
        raise _error("Claims C12/C14/C15 availability or Holm facts drifted")
    verification = software.get("verification")
    if not isinstance(verification, Mapping):
        raise _error("Claim C16 software verification record drifted")
    public_tests = verification.get("public_tests")
    end_to_end = verification.get("end_to_end_tests")
    openapi_contract = verification.get("openapi_contract")
    if not all(isinstance(value, Mapping) for value in (public_tests, end_to_end, openapi_contract)):
        raise _error("Claim C16 software verification summaries drifted")
    runtime_versions = _validated_runtime_versions(environment)
    if (
        public_tests != {"tests": 347, "errors": 0, "failures": 0, "skipped": 9}
        or end_to_end != {"tests": 3, "errors": 0, "failures": 0, "skipped": 0}
        or openapi_contract.get("openapi_path_count") != 69
        or openapi_contract.get("openapi_operation_count") != 83
        or openapi_contract.get("documented_operation_count") != 38
        or openapi_contract.get("valid") is not True
        or software.get("source_artifact_count") != 6
    ):
        raise _error("Claim C16 software evidence values drifted")

    def benchmark_claim_value(
        means: Mapping[str, Mapping[str, Decimal]],
        winners: Mapping[str, str],
        cells: Mapping[str, _BenchmarkCell],
    ) -> str:
        return "|".join(
            (
                f"h{horizon}={winners[horizon]}:mean="
                f"{_decimal(format(means[horizon][winners[horizon]], 'f'))}:"
                f"success_rate={_decimal(format(cells[horizon].success_rate, 'f'), 6)}:"
                f"evaluable_rate={_decimal(format(cells[horizon].evaluable_rate, 'f'), 6)}"
            )
            for horizon in ("1", "2", "3")
        )

    def benchmark_claim_denominator(
        cells: Mapping[str, _BenchmarkCell],
    ) -> str:
        return "|".join(
            (
                f"h{horizon}:attempted={cells[horizon].attempted}:"
                f"successful={cells[horizon].successful}:"
                f"evaluable={cells[horizon].evaluable}"
            )
            for horizon in ("1", "2", "3")
        )

    brier_winner_ids = {horizon: "B2" for horizon in ("1", "2", "3")}
    e8_value = (
        f"raw_within={e8.raw_within_margin}/{e8.group_count};"
        f"locked_within={e8.locked_within_margin}/{e8.group_count};"
        f"locked_closer={e8.locked_closer}/{e8.group_count};"
        f"locked_wider={e8.locked_wider}/{e8.group_count};"
        "mean_abs_error_raw="
        f"{_decimal(format(e8.raw_mean_absolute_error, 'f'), 6)};"
        "median_abs_error_raw="
        f"{_decimal(format(e8.raw_median_absolute_error, 'f'), 6)};"
        "mean_abs_error_locked="
        f"{_decimal(format(e8.locked_mean_absolute_error, 'f'), 6)};"
        "median_abs_error_locked="
        f"{_decimal(format(e8.locked_median_absolute_error, 'f'), 6)}"
    )

    claims = [
        (
            "C01_holdout_population", "III", "Evaluation surface",
            "Closure V1 evaluated 88 held-out WQP locations, 4,488 origins and 13,464 origin-horizon attempts.",
            "descriptive_available", LOCKED_EVALUATION_SUMMARY, "input-only locked surface",
            "site/origin/attempt counts", "88;4488;13464", "13464",
            "Internal pseudoprospective location holdout.",
            "internal pseudoprospective evaluation", "external validation",
        ),
        (
            "C02_intent_to_predict", "III", "Estimands",
            "Failures and unavailable predictions remained in the intent-to-predict denominator.",
            "descriptive_available", MODEL_METRICS, "all terminal_status rows",
            "attempted versus successful denominator", "retained", "13464",
            "Availability is part of the estimand.",
            "intent-to-predict denominator", "complete-case denominator",
        ),
        (
            "C03_primary_models_unavailable", "IV", "Model availability",
            "P0, P1 and A2 were unavailable and were not substituted.",
            "model_unavailable", MODEL_AVAILABILITY, "model_id in P0,P1,A2",
            "availability_state", "model_unavailable", "3 models",
            "No replacement or imputation is permitted.",
            "P0, P1 and A2 unavailable", "trained or evaluated P0/P1/A2",
        ),
        (
            "C04_brier_observation_weighted", "IV", "Benchmark",
            "B2 had the lowest observation-weighted Brier score at horizons 1, 2 and 3 among estimable branches; each rank is accompanied by its exact attempted, successful and metric-evaluable denominators and rates.",
            "descriptive_available", MODEL_METRICS, "metric=brier;estimand=observation_weighted;terminal_status=estimated",
            "five-seed mean Brier rank/value plus successful and evaluable rates",
            benchmark_claim_value(
                brier_means, brier_winner_ids, brier_availability
            ),
            benchmark_claim_denominator(brier_availability),
            "The ranking is estimand-specific and descriptive.",
            "B2 lowest observation-weighted Brier at h1-h3", "universal winner",
        ),
        (
            "C05_pr_auc_observation_weighted", "IV", "Benchmark",
            "A1 had the highest observation-weighted PR-AUC at horizon 1, while B2 had it at horizons 2 and 3 among estimable branches; each rank is accompanied by its exact attempted, successful and metric-evaluable denominators and rates.",
            "descriptive_available", MODEL_METRICS, "metric=pr_auc;estimand=observation_weighted;terminal_status=estimated",
            "five-seed mean PR-AUC rank/value plus successful and evaluable rates",
            benchmark_claim_value(
                pr_auc_means, pr_auc_winners, pr_auc_availability
            ),
            benchmark_claim_denominator(pr_auc_availability),
            "The horizon-specific ranking is descriptive.",
            "A1 at h1 and B2 at h2-h3 for observation-weighted PR-AUC", "universal superiority",
        ),
        (
            "C06_f1_vs_f0_absolute_error", "IV", "Paired descriptive comparison",
            "F1 had higher absolute error than F0 in all 15 estimated exact-shared-row seed-horizon comparisons.",
            "descriptive_available", MODEL_COMPARISON, "comparison_id=F1_vs_F0;metric=absolute_error;terminal_status=estimated",
            "mean_loss_difference_F1_minus_F0", "positive in 15/15", "15",
            "The comparison has no inferential interval and does not establish universal model superiority.",
            "F1 higher absolute error than F0 in 15 of 15", "F1 inferior for every estimand and metric",
        ),
        (
            "C07_anfis_ablation", "IV", "ANFIS ablation",
            "Relative to A0 on exact common rows, A1 had higher PR-AUC at three horizons, lower Brier at three, and lower MAE at two of three.",
            "descriptive_available", ABLATION_PAIRWISE, "challenger=A1;reference=A0;status=available",
            "delta PR-AUC/Brier/MAE directions", "3/3;3/3;2/3", "3175;3125;3045 common rows",
            "No interval, membership-stability or saturation claim is available.",
            "descriptive A1-A0 changes on exact common rows", "saturated or confirmatorily superior ANFIS",
        ),
        (
            "C08_anfis_missing_diagnostics", "IV", "ANFIS diagnostics",
            "The three prespecified learning-curve sizes and the membership-stability analysis remained unavailable.",
            "insufficient_support", T09_OUTPUT, "4096;16384;65536 plus membership_stability sentinel",
            "completed diagnostics", "0/4", "4",
            "The absence of these diagnostics blocks saturation and membership-stability claims.",
            "E7 diagnostics unavailable", "saturated curve or stable memberships",
        ),
        (
            "C09_site_transfer", "IV", "Site transfer",
            "None of the 1,050 registered legacy-to-holdout site-transfer cells was estimable because the legacy evaluation surface was not frozen before E0-U.",
            "insufficient_support", GENERALIZATION_GAP, "all rows;estimable=False",
            "estimable site-transfer cells", "0", "1050",
            "This is internal WQP transfer and not external geographic validation.",
            "E2 not estimable: 0 of 1050", "absence of a gap or external validation",
        ),
        (
            "C10_thresholds", "IV", "Threshold sensitivity",
            "Threshold sensitivity is reported for 25, 30, 33 and 50 micrograms per litre.",
            "descriptive_available", THRESHOLD_PREVALENCE, "all cutoffs",
            "prevalence/support/rank stability", "25;30;33;50", "reported per cutoff",
            "The 50 threshold has sparse support.",
            "descriptive cutoff sensitivity", "threshold recalibrated after unblinding",
        ),
        (
            "C11_trophic_b2_vs_b1", "IV", "Trophic references",
            "B2 improved on B1 in all four ordinal metrics in each of 15 proxy/reference-by-horizon summaries.",
            "descriptive_available", T07_OUTPUT, "B1/B2;five-seed means;proxy plus four Carlson references",
            "macro-F1/kappa higher and ordinal-MAE/severe-error lower", "15/15", "15 reference-horizon cells",
            "These are internal proxy and derived-reference comparisons, not direct NLA target transfer.",
            "B2 better than B1 on all four ordinal metrics", "external NLA trophic validation",
        ),
        (
            "C12_degradation", "IV", "Controlled degradation",
            "All 78 registered M0-versus-P1 degradation cells were unavailable because P1 was unavailable.",
            "model_unavailable", FAILURE_REGISTRY, "all exact78 failure rows",
            "estimable degradation cells", "0", "78",
            "Unavailable cells are not zero effects and were not reconstructed.",
            "E6 unavailable: 0 of 78 estimable cells", "confirmed robustness or zero effect",
        ),
        (
            "C13_uncertainty", "IV", "Uncertainty",
            "Raw Gaussian was within the sealed 0.05 coverage margin in 30 of 30 primary A0/A1 groups, versus 26 of 30 for locked conformal; locked conformal was closer in 5 of 30 paired groups and wider in all 30.",
            "descriptive_available", UNCERTAINTY_LEDGER,
            "A0/A1 raw_gaussian versus locked_conformal; nominal_coverage=0.90; exact paired model/seed/horizon groups",
            "paired coverage-margin, closeness, width and mean/median absolute-error diagnostics",
            e8_value, "30 paired primary groups",
            "Locked conformal did not improve these diagnostics uniformly and this is not global calibration.",
            "descriptive raw-versus-locked comparison", "conformal always improves;globally calibrated",
        ),
        (
            "C14_multiplicity", "IV", "Inference ledger",
            "Holm universes A=3, B=78, C=1, D=9 and E=1 were retained despite non-estimability.",
            "descriptive_available", MULTIPLICITY_REPORT, "all families",
            "registered universe size", "A3;B78;C1;D9;E1", "92 cells",
            "Non-estimability is not a zero effect.",
            "complete Holm universes", "reduced multiplicity family",
        ),
        (
            "C15_planning", "IV", "Planning",
            "All nine preregistered planning actions were non-estimable.",
            "model_unavailable", PLANNING_BOOTSTRAP, "all actions",
            "delta_objective_vs_no_action/CI/p-value availability", "model_unavailable", "9 actions",
            "No causal, net-benefit or optimality claim is authorized.",
            "planning not estimable", "optimal no-action or official recommendation",
        ),
        (
            "C16_software", "IV", "Software evidence",
            "E10 verified 338 passing public tests with 9 justified skips, three passing end-to-end tests, a valid 69-path/83-operation OpenAPI contract, and the sealed Python 3.14.7, FastAPI 0.138.1 and DVC 3.67.1 environment.",
            "descriptive_available", T12_OUTPUT, "runtime_environment plus recovery_2 verification summaries",
            "tests/OpenAPI/E2E/runtime state",
            "338 pass;9 skip;3 E2E;69 paths;83 operations;38 documented;"
            f"Python {runtime_versions['python']};FastAPI {runtime_versions['fastapi']};DVC {runtime_versions['dvc']}",
            "6 source artifacts",
            "Software verification does not validate scientific utility.",
            "reproducible software contract", "software proves scientific efficacy",
        ),
        (
            "C17_global_verdict_discussion", "V", "Discussion",
            "Closure V1 provides no conclusive predictive corroboration, while preserving a reproducible engineering and methodological contribution.",
            "insufficient_support", FINAL_MATRIX_OUTPUT, "exact130 adjudication rows",
            "global thesis verdict", "no_conclusive_predictive_corroboration", "92 Holm cells plus 38 descriptive/limitation rows",
            "The engineering contribution is distinct from predictive corroboration.",
            "no conclusive predictive corroboration", "total failure or demonstrated efficacy",
        ),
        (
            "C18_summary_boundary", "Summary", "Results",
            "The summary may report descriptive available results and explicit non-estimability, but not replace unavailable P0, P1 or A2.",
            "insufficient_support", FINAL_MATRIX_OUTPUT, "availability_state and model_or_pair",
            "authorized synthesis boundary", "no substitution", "130 adjudication rows",
            "Every unavailable result remains labelled and denominator-preserving.",
            "descriptive results with explicit unavailability", "reconstructed or substituted models",
        ),
        (
            "C19_abstract_boundary", "Abstract", "Conclusion",
            "The abstract may state the internal pseudoprospective scope and non-conclusive verdict, without claiming external validation or causal planning.",
            "insufficient_support", FINAL_MATRIX_OUTPUT, "global verdict and limitation codes",
            "authorized abstract boundary", "internal;non-conclusive;non-causal", "130 adjudication rows",
            "The scope is internal WQP and descriptive where available.",
            "internal evaluation and non-conclusive verdict", "external validation or causal recommendation",
        ),
        (
            "C20_conclusion_boundary", "Conclusion", "Final thesis conclusion",
            "The conclusion may claim reproducibility and methodological traceability, not universal superiority, field causality or official management recommendations.",
            "insufficient_support", FINAL_MATRIX_OUTPUT, "verdict and evidence_paths",
            "authorized conclusion boundary", "reproducible_methodological_contribution", "130 adjudication rows",
            "Reproducibility is not scientific efficacy.",
            "reproducible methodological contribution", "universal superiority, field causality, or official recommendation",
        ),
    ]
    rows: list[dict[str, str]] = []
    for claim in claims:
        values = {
            "claim_id": claim[0],
            "chapter": claim[1],
            "section": claim[2],
            "claim_text": claim[3],
            "claim_status": claim[4],
            "artifact_path": claim[5],
            "row_filter_or_record": claim[6],
            "metric": claim[7],
            "value_or_state": claim[8],
            "denominator": claim[9],
            "authority_commit": contract.closure_source_commit,
            "limitation": claim[10],
            "allowed_wording": claim[11],
            "forbidden_wording": claim[12],
        }
        rows.append({column: values[column] for column in contract.claim_evidence_columns})
    if len(rows) != contract.claim_evidence_row_count:
        raise _error(
            "THESIS_CLAIM_EVIDENCE_MATRIX row count drifted from "
            f"exact{contract.claim_evidence_row_count}"
        )
    validate_claim_evidence_rows(rows, contract)
    return rows


def _table_bytes(
    contract: SynthesisContract,
    table_id: str,
    rows: Sequence[Mapping[str, str]],
    columns: Sequence[str],
) -> bytes:
    """Serialize one typed table after enforcing its frozen row invariant."""

    expected = contract.table_row_counts.get(table_id)
    if expected is None:
        raise _error(f"Missing frozen row-count invariant for {table_id}")
    if len(rows) != expected:
        raise _error(
            f"{table_id} row count drifted: expected {expected}, observed {len(rows)}"
        )
    if not columns or len(columns) != len(set(columns)) or "record_json" in columns:
        raise _error(f"{table_id} does not have a valid typed CSV schema")
    expected_columns = set(columns)
    for index, row in enumerate(rows, start=1):
        if set(row) != expected_columns:
            raise _error(f"{table_id} row {index} does not match its typed schema")
    return csv_bytes(rows, columns)


def _unique_index(
    rows: Sequence[Mapping[str, str]],
    column: str,
    *,
    source: str,
) -> dict[str, Mapping[str, str]]:
    indexed: dict[str, Mapping[str, str]] = {}
    for row in rows:
        key = row.get(column, "")
        if not key or key in indexed:
            raise _error(f"{source} has an empty or duplicated {column}: {key!r}")
        indexed[key] = row
    return indexed


def _child_mapping(
    parent: Mapping[str, Any], field: str, *, source: str
) -> Mapping[str, Any]:
    value = parent.get(field)
    if not isinstance(value, Mapping):
        raise _error(f"{source} field is not an object: {field}")
    return cast(Mapping[str, Any], value)


def _boolean_text(value: Any, *, context: str) -> str:
    if value is True or (isinstance(value, str) and value.lower() == "true"):
        return "true"
    if value is False or (isinstance(value, str) and value.lower() == "false"):
        return "false"
    raise _error(f"{context} is not a boolean")


def _integer_range(
    rows: Sequence[Mapping[str, str]], column: str, *, source: str
) -> tuple[str, str]:
    if not rows:
        return "", ""
    values = [_integer(row, column, source=source) for row in rows]
    return str(min(values)), str(max(values))


def _decimal_mean(
    rows: Sequence[Mapping[str, str]], column: str, *, source: str
) -> str:
    return _render_number(
        _mean(
            [_numeric(row, column, source=source) for row in rows],
            context=f"{source}:{column}",
        )
    )


def _svg_attribute_name(name: str) -> str:
    return name.removesuffix("_").replace("_", "-")


def _svg_attributes(attributes: Mapping[str, str | int]) -> str:
    return " ".join(
        f'{_svg_attribute_name(name)}="{html.escape(str(value), quote=True)}"'
        for name, value in sorted(attributes.items())
    )


class _SvgCanvas:
    """Small deterministic SVG emitter with auditable data attributes."""

    def __init__(
        self,
        artifact_id: str,
        caption: str,
        description: str,
        heading: str,
        *,
        width: int,
        height: int,
    ) -> None:
        self.width = width
        self.height = height
        self._parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
                f'data-artifact-id="{artifact_id}" role="img" '
                'aria-labelledby="figure-title figure-description">'
            ),
            f'<title id="figure-title">{html.escape(caption)}</title>',
            (
                '<desc id="figure-description">'
                f'{html.escape(description)}</desc>'
            ),
            (
                "<style>"
                ".heading{font:700 25px sans-serif;fill:#111827}"
                ".subtitle{font:14px sans-serif;fill:#374151}"
                ".label{font:13px sans-serif;fill:#111827}"
                ".small{font:11px sans-serif;fill:#374151}"
                ".value{font:11px monospace;fill:#111827}"
                ".axis{stroke:#4b5563;stroke-width:1;fill:none}"
                ".grid{stroke:#d1d5db;stroke-width:1;fill:none}"
                ".panel{fill:#f9fafb;stroke:#d1d5db;stroke-width:1}"
                ".na{fill:#e5e7eb;stroke:#6b7280;stroke-width:1}"
                "</style>"
            ),
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
            (
                f'<text class="heading" x="40" y="42">'
                f'{html.escape(heading)}</text>'
            ),
        ]

    def raw(self, value: str) -> None:
        self._parts.append(value)

    def open_group(self, **attributes: str | int) -> None:
        rendered = _svg_attributes(attributes)
        self._parts.append(f"<g {rendered}>" if rendered else "<g>")

    def close_group(self) -> None:
        self._parts.append("</g>")

    def element(
        self,
        tag: str,
        *,
        text: str | None = None,
        title: str | None = None,
        **attributes: str | int,
    ) -> None:
        rendered = _svg_attributes(attributes)
        opening = f"<{tag} {rendered}>" if rendered else f"<{tag}>"
        if text is None and title is None:
            self._parts.append(opening.removesuffix(">") + "/>")
            return
        children = ""
        if title is not None:
            children += f"<title>{html.escape(title)}</title>"
        if text is not None:
            children += html.escape(text)
        self._parts.append(f"{opening}{children}</{tag}>")

    def text(
        self,
        x: int,
        y: int,
        value: str,
        *,
        class_: str = "label",
        **attributes: str,
    ) -> None:
        self.element(
            "text",
            text=value,
            x=x,
            y=y,
            class_=class_,
            **attributes,
        )

    def finish(self) -> bytes:
        self._parts.append("</svg>")
        return ("\n".join(self._parts) + "\n").encode("utf-8")


def _figure_description(
    sources: Sequence[str], *, filters: str
) -> str:
    return "Sources: " + ";".join(sources) + ". Filters: " + filters


def _numeric(
    row: Mapping[str, str], column: str, *, source: str
) -> Decimal:
    raw = row.get(column, "")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise _error(f"Invalid {column} in {source}: {raw!r}") from exc
    if not value.is_finite():
        raise _error(f"Non-finite {column} in {source}: {raw!r}")
    return value


def _integer(
    row: Mapping[str, str], column: str, *, source: str
) -> int:
    value = _numeric(row, column, source=source)
    integral = value.to_integral_value()
    if value != integral or integral < 0:
        raise _error(f"Invalid non-negative integer {column} in {source}")
    return int(integral)


def _mean(values: Sequence[Decimal], *, context: str) -> Decimal:
    if not values:
        raise _error(f"Cannot compute an empty mean: {context}")
    return sum(values, Decimal(0)) / Decimal(len(values))


def _render_number(value: Decimal, places: int = 4) -> str:
    return _decimal(format(value, "f"), places)


def _scale(
    value: Decimal,
    lower: Decimal,
    upper: Decimal,
    start: int,
    span: int,
) -> int:
    if upper <= lower:
        raise _error("SVG scale bounds are not increasing")
    clipped = min(max(value, lower), upper)
    offset = (clipped - lower) * Decimal(span) / (upper - lower)
    return start + int(offset.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def _range_label(values: Sequence[int]) -> str:
    if not values:
        return "N/A"
    low = min(values)
    high = max(values)
    return str(low) if low == high else f"{low}–{high}"


def _heat_color(value: Decimal, lower: Decimal, upper: Decimal) -> str:
    if upper == lower:
        fraction = Decimal("0.5")
    else:
        fraction = (value - lower) / (upper - lower)
    fraction = min(max(fraction, Decimal(0)), Decimal(1))
    red = int((Decimal(239) - Decimal(142) * fraction).quantize(Decimal("1")))
    green = int((Decimal(246) - Decimal(92) * fraction).quantize(Decimal("1")))
    blue = int((Decimal(255) - Decimal(48) * fraction).quantize(Decimal("1")))
    return f"#{red:02x}{green:02x}{blue:02x}"


def _report(
    contract: SynthesisContract,
    matrix_rows: Sequence[Mapping[str, str]],
    claim_rows: Sequence[Mapping[str, str]],
) -> bytes:
    if len(matrix_rows) != contract.final_closure_row_count:
        raise _error("Report received an incomplete FINAL_CLOSURE_MATRIX")
    if len(claim_rows) != contract.claim_evidence_row_count:
        raise _error("Report received an incomplete THESIS_CLAIM_EVIDENCE_MATRIX")
    claims = _unique_by(claim_rows, "claim_id", context="report claims")

    def claim_value(claim_id: str) -> str:
        try:
            return claims[claim_id]["value_or_state"]
        except KeyError as exc:
            raise _error(f"Report-required claim is absent: {claim_id}") from exc

    def claim_denominator(claim_id: str) -> str:
        try:
            return claims[claim_id]["denominator"]
        except KeyError as exc:
            raise _error(f"Report-required claim is absent: {claim_id}") from exc

    def markdown(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    counts: dict[str, int] = {}
    for row in matrix_rows:
        counts[row["availability_state"]] = counts.get(row["availability_state"], 0) + 1
    expected_counts = {
        "model_unavailable": 93,
        "not_applicable": 9,
        "insufficient_support": 5,
        "descriptive_available": 23,
    }
    if counts != expected_counts:
        raise _error(f"Report availability-state census drifted: {counts}")

    family_counts = {
        family: len(
            {
                (
                    row["model_or_pair"],
                    row["metric"],
                    row["population"],
                    row["estimand"],
                )
                for row in matrix_rows
                if row["multiplicity_family"] == family
            }
        )
        for family in contract.holm_universes
    }
    if family_counts != dict(contract.holm_universes):
        raise _error("Report received a reduced Holm ledger")

    a1_a0_rows = [
        row
        for row in matrix_rows
        if row["hypothesis_id"].startswith("H1:A1_vs_A0:")
    ]
    if len(a1_a0_rows) != 9:
        raise _error("Report lost the nine A1-A0 descriptive cells")
    a1_a0_summary = "; ".join(
        f"{row['model_or_pair']} {row['metric']}={row['estimate']} (n={row['successful_denominator']})"
        for row in a1_a0_rows
    )

    experiment_results = (
        (
            "E1",
            "Internal benchmark: observation-weighted Brier "
            f"{claim_value('C04_brier_observation_weighted')} with denominators "
            f"{claim_denominator('C04_brier_observation_weighted')}; PR-AUC observation-weighted "
            f"{claim_value('C05_pr_auc_observation_weighted')} with denominators "
            f"{claim_denominator('C05_pr_auc_observation_weighted')}. "
            "In the paired F1-F0 contrast, the absolute-loss difference was "
            f"{claim_value('C06_f1_vs_f0_absolute_error')}; these results are descriptive, "
            "and the observation_weighted and site_weighted estimands remain separate.",
        ),
        (
            "E2",
            "Internal legacy-to-holdout transfer: "
            f"{claim_value('C09_site_transfer')}/1050 estimable cells. The sealed reason "
            "is `legacy_evaluation_surface_not_frozen_before_e0_u`; this is not evidence "
            "of a zero gap or external geographic validation.",
        ),
        (
            "E3",
            "Preserved descriptive sensitivity for thresholds "
            f"{claim_value('C10_thresholds')} micrograms/L, with prevalence, support, and "
            "Kendall statistics by horizon; no threshold was recalibrated after E0-U.",
        ),
        (
            "E4",
            "Ordinal/trophic B2-B1 comparison: a direction favorable to B2 in "
            f"{claim_value('C11_trophic_b2_vs_b1')} reference-by-horizon summaries "
            "for macro-F1, quadratic kappa, ordinal MAE, and severe error. This is internal "
            "auxiliary proxy/derived-reference evidence; it does not validate the ANFIS "
            "branch, and NLA does not transfer monthly WQP targets.",
        ),
        (
            "E5",
            "Complete inferential ledger: "
            f"{claim_value('C14_multiplicity')} (92 cells). Every registered cell remains "
            "in Holm even when its estimate, confidence interval, and p-value are not estimable.",
        ),
        (
            "E6",
            "Controlled M0-P1 degradation: "
            f"{claim_value('C12_degradation')}/78 estimable cells because P1 remained "
            "model_unavailable. No reconstruction, substitution, or new read occurred.",
        ),
        (
            "E7",
            "A1-A0 ablation on exact common rows: "
            f"{claim_value('C07_anfis_ablation')}. Learning-curve and membership-stability "
            f"diagnostics completed {claim_value('C08_anfis_missing_diagnostics')}; "
            "no saturation or parameter-stability claim is authorized.",
        ),
        (
            "E8",
            "Paired raw-Gaussian versus locked-conformal comparison at nominal 0.90: "
            f"{claim_value('C13_uncertainty')}. Raw was within the absolute 0.05 margin in "
            "30/30 groups and locked in 26/30; locked was closer in 5/30 and wider in "
            "30/30, and its mean/median absolute errors were 0.032271/0.030872 versus "
            "0.015565/0.013386 for raw. Therefore, `conformal always improves` is prohibited. "
            "This is descriptive diagnostics; the confirmatory comparison that depends on "
            "P1 remains non-estimable, and no recalibration occurred.",
        ),
        (
            "E9",
            "Planning: 0/9 actions with an estimable effect, confidence interval, or p-value "
            f"(`{claim_value('C15_planning')}`). The registered endpoint is "
            "`delta_objective_vs_no_action`; net benefit, causality, optimality, and "
            "official recommendations are not authorized.",
        ),
        (
            "E10",
            "Recovery-2 software evidence: "
            f"{claim_value('C16_software')}. This verification establishes artifact "
            "reproducibility, not scientific efficacy or prospective field validation.",
        ),
    )

    lines = [
        "# FINAL CLOSURE REPORT — Closure V1",
        "",
        "## 1. Freeze, commit and environment",
        "",
        f"Closure source commit: `{contract.closure_source_commit}`.",
        "",
        "Sealed topology: `ea8ddce -> H-SYN (exact9A+2M) -> P-SYN (exact2A) -> R-SYN (exact24)`.",
        "E10 environment sealed and validated in T12: Python 3.14.7, FastAPI 0.138.1, and DVC 3.67.1.",
        f"The synthesis uses exactly {len(contract.allowed_inputs)} structured CSV/JSON/YAML inputs and identity-only DVC pointers, and it produces {len(contract.output_paths)} manifest-last artifacts.",
        "It does not read Parquet, `data/targets/`, raw outcomes, or `private/FULL.md`; it does not run refitting, rescoring, recalibration, DVC add/push, or E0-U/E1-E10.",
        "",
        "## 2. Primary surface and holdout",
        "",
        "Internal pseudoprospective WQP surface: 88 held-out locations, 4,488 origins, and 13,464 origin-horizon attempts.",
        "The funnel retains failures and unavailable predictions in the intent-to-predict denominator. The five seeds are algorithmic slots, not ecological replicates.",
        "P0, P1, and A2 remain `model_unavailable` without substitution. This is an internal WQP surface, not external validation.",
        "",
        "## 3. Results E1–E10",
        "",
    ]
    for experiment, result in experiment_results:
        lines.extend((f"### {experiment}", "", result, ""))
    lines.extend(
        [
        "",
        "## 4. Comparisons and non-estimability",
        "",
        "Exact census of 130 rows: 93 `model_unavailable`, 9 `not_applicable`, 5 `insufficient_support`, and 23 `descriptive_available`.",
        "The 92 Holm contrasts retain A=3, B=78, C=1, D=9, and E=1. In a non-estimable row, `estimate` and `uncertainty` are empty by contract: they never represent zero, equivalence, or negative evidence.",
        "Comparisons requiring P0/P1/A2 lack an estimate, confidence interval, and p-value because the required model was unavailable; E2 lacks a gap because no comparable frozen legacy surface exists; E6 lacks an M0-P1 intersection; E9 lacks both an action effect and a registered net-benefit endpoint.",
        "Available A1-A0 deltas are descriptive, with no invented inferential interval:",
        "",
        f"`{a1_a0_summary}`",
        "",
        "E8 reports raw and locked coverage/width/Winkler diagnostics for 30 exact pairs: raw was within the margin in 30/30 and locked in 26/30, locked was closer in 5/30 and wider in 30/30, and mean/median absolute errors were 0.015565/0.013386 for raw and 0.032271/0.030872 for locked. This prohibits claiming that `conformal always improves` and provides neither global confirmation nor permission to recalibrate.",
        "",
        "## 5. Verdict H1–H5",
        "",
        ]
    )
    for hypothesis_id in contract.required_hypotheses:
        record = ADJUDICATION[hypothesis_id]
        state_counts: dict[str, int] = {}
        for row in matrix_rows:
            if row["hypothesis_id"] == hypothesis_id or row["hypothesis_id"].startswith(
                hypothesis_id + ":"
            ):
                state = row["availability_state"]
                state_counts[state] = state_counts.get(state, 0) + 1
        lines.append(
            f"- {hypothesis_id}: `{record['verdict']}` — {record['text']}; "
            f"decisive experiments `{record['experiments']}`; states "
            f"`{json.dumps(state_counts, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}`; "
            f"limitation `{record['limitation']}`."
        )
    lines.extend(
        [
            "",
            "Global verdict: **Closure V1 did not produce conclusive predictive corroboration; it did preserve a reproducible methodological and engineering contribution.**",
            "",
            "## 6. Authorized claims",
            "",
            *[
                f"- `{row['claim_id']}` [{row['claim_status']}]: {row['claim_text']} "
                f"(value/state `{row['value_or_state']}`; denominator `{row['denominator']}`)."
                for row in claim_rows
            ],
            "",
            "## 7. Withdrawn or limited claims",
            "",
            "Claims of external validation, a universal winner, confirmatory B2/A1 superiority, ANFIS saturation or stability, canonical GRU-D, direct monthly NLA-to-WQP transfer, E6 robustness, global calibration, E9 causality/net benefit/optimality, and official recommendations remain withdrawn or limited.",
            "It is also prohibited to interpret `not_estimable` as a zero effect, equivalence, failure, or negative evidence, or to present E10 verification as scientific efficacy.",
            "",
            "## 8. Replacement tables and figures",
            "",
            "T01-T12 and F01-F08 replace earlier Closure V1 results and are deterministic descendants of published structured artifacts. Their sealed captions are:",
            "",
            *[
                f"- **{artifact_id}** — {caption}"
                for artifact_id, caption in contract.artifact_captions.items()
            ],
            "",
            "## 9. LaTeX sections to modify after approval",
            "",
            "Target file, only after formal R-SYN approval: `private/mifal_ed_t2/mifal_ed_modelo_tesis_v5.tex`.",
            "",
            "- Chapter III — `source_id + site_id` unit; cutoff-safe 353/88 split; 12-month history and h1/h2/h3; temporal roles; no-current surface; five seeds as slots; catalog/availability; intent-to-predict; E1-E10; separate estimands; Holm; recoveries; and manifest-last publication.",
            "- Chapter IV — freeze/cohort; funnel; E1; E2; E3; E4; E5; E6; E7; E8; E9; separate E10; H1-H5b matrix, in that order.",
            "- Chapter V — discussion, limitations, no substitution, internal WQP scope, refutability, and global conclusion.",
            "- Summary and abstract — internal scope, bounded descriptive results, unavailable P0/P1/A2, and a non-conclusive verdict.",
            "- Contribution list and general conclusion — separate reproducibility from predictive efficacy.",
            "- Reproducibility appendix — topology, activations/receipts, exact52/exact53, DVC pointers, E10/OpenAPI, Holm, and guards, without turning inodes or local paths into scientific claims.",
            "",
            "## 10. Claim → artifact → metric → limitation",
            "",
            "| claim | destination | state | artifact | metric | value/state | denominator | limitation |",
            "|---|---|---|---|---|---|---|---|",
            *[
                "| "
                + " | ".join(
                    markdown(row[column])
                    for column in (
                        "claim_id",
                        "chapter",
                        "claim_status",
                        "artifact_path",
                        "metric",
                        "value_or_state",
                        "denominator",
                        "limitation",
                    )
                )
                + " |"
                for row in claim_rows
            ],
            "",
            "The machine-readable source for this section is `THESIS_CLAIM_EVIDENCE_MATRIX.csv`. The manuscript remains out of scope until the report, both matrices, and the published R-SYN bundle are approved.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _table_payloads(
    contract: SynthesisContract,
    root: Path,
    matrix_rows: Sequence[Mapping[str, str]],
) -> dict[str, bytes]:
    del matrix_rows  # Tables are reconstructed from their frozen source artifacts.

    availability = _read_allowed_csv(contract, root, MODEL_AVAILABILITY)
    metrics = _read_allowed_csv(contract, root, MODEL_METRICS)
    comparisons = _read_allowed_csv(contract, root, MODEL_COMPARISON)
    location_metrics = _read_allowed_csv(
        contract, root, LOCATION_HOLDOUT_METRICS
    )
    gaps = _read_allowed_csv(contract, root, GENERALIZATION_GAP)
    prevalence = _read_allowed_csv(contract, root, THRESHOLD_PREVALENCE)
    ranks = _read_allowed_csv(contract, root, RANK_STABILITY)
    trophic = _read_allowed_csv(contract, root, TROPHIC_PROXY)
    carlson = _read_allowed_csv(contract, root, CARLSON_METRICS)
    nla_semantic = _read_allowed_csv(contract, root, NLA_SEMANTIC_METRICS)
    registry = _read_allowed_csv(contract, root, HYPOTHESIS_REGISTRY)
    multiplicity = _read_allowed_csv(contract, root, MULTIPLICITY_REPORT)
    ablation_pairs = _read_allowed_csv(contract, root, ABLATION_PAIRWISE)
    learning = _read_allowed_csv(contract, root, LEARNING_CURVE)
    membership = _read_allowed_csv(contract, root, MEMBERSHIP_STABILITY)
    uncertainty = _read_allowed_csv(contract, root, UNCERTAINTY_LEDGER)
    failures = _read_allowed_csv(contract, root, FAILURE_REGISTRY)
    planning = _read_allowed_csv(contract, root, PLANNING_BOOTSTRAP)
    environment = _read_allowed_json(contract, root, API_ENVIRONMENT)
    openapi = _read_allowed_json(contract, root, API_OPENAPI)
    software = _read_allowed_json(contract, root, SOFTWARE_MANIFEST)

    availability_by_model = _unique_index(
        availability, "model_id", source=MODEL_AVAILABILITY
    )
    model_ids = list(availability_by_model)
    if len(model_ids) * 9 != contract.table_row_counts["T01"]:
        raise _error("The frozen T01 model x experiment grid drifted")
    unavailable_models = {
        model_id
        for model_id, row in availability_by_model.items()
        if row["availability"] == "unavailable"
    }
    if unavailable_models != set(contract.required_unavailable_models):
        raise _error("The frozen unavailable-model set drifted")

    # T01: one explicit availability decision for every model x E1--E9 cell.
    benchmark_models = {
        row["model_id"] for row in metrics if row["terminal_status"] == "estimated"
    }
    site_models = {
        row["model_id"]
        for row in location_metrics
        if row["terminal_status"] == "success"
    }
    threshold_models = {
        row["model_id"]
        for row in metrics
        if row["metric"] == "pr_auc" and row["terminal_status"] == "estimated"
    }
    trophic_models = {
        row["model_id"]
        for row in (*trophic, *carlson)
        if row["status"] == "available"
    }
    ablation_models = {
        row["challenger_model_id"]
        for row in ablation_pairs
        if row["status"] == "available"
    } | {
        row["reference_model_id"]
        for row in ablation_pairs
        if row["status"] == "available"
    }
    uncertainty_models = {
        row["model_id"] for row in uncertainty if row["status"] == "available"
    }
    gap_models = {row["model_id"] for row in gaps}
    site_surface_models = {row["model_id"] for row in location_metrics}
    benchmark_surface_models = {row["model_id"] for row in metrics}
    trophic_surface_models = {
        row["model_id"] for row in (*trophic, *carlson)
    }
    ablation_surface_models = {
        row["challenger_model_id"] for row in ablation_pairs
    } | {row["reference_model_id"] for row in ablation_pairs}
    registered_model_scope = {
        model_id
        for row in registry
        for model_id in model_ids
        if re.search(
            rf"(?:^|_){re.escape(model_id)}(?:_|$)", row["comparison_id"]
        )
    }
    experiment_model_scope = {
        "E1": set(model_ids),
        "E2": gap_models | site_surface_models,
        "E3": benchmark_surface_models,
        "E4": trophic_surface_models,
        "E5": registered_model_scope,
        "E6": {"M0", "P1"},
        "E7": ablation_surface_models,
        "E8": {*(row["model_id"] for row in uncertainty), "P1"},
        # E9 is action-level, but its registered predictive dependency is P1.
        "E9": {"P1"},
    }
    if set(experiment_model_scope) != {f"E{index}" for index in range(1, 10)} or any(
        not scoped_models.issubset(set(model_ids))
        for scoped_models in experiment_model_scope.values()
    ):
        raise _error("T01 experiment applicability scope drifted")
    experiment_sources = {
        "E1": MODEL_METRICS,
        "E2": f"{LOCATION_HOLDOUT_METRICS};{GENERALIZATION_GAP}",
        "E3": f"{THRESHOLD_PREVALENCE};{RANK_STABILITY};{MODEL_METRICS}",
        "E4": f"{TROPHIC_PROXY};{CARLSON_METRICS};{NLA_SEMANTIC_METRICS}",
        "E5": f"{HYPOTHESIS_REGISTRY};{MULTIPLICITY_REPORT}",
        "E6": FAILURE_REGISTRY,
        "E7": f"{ABLATION_PAIRWISE};{LEARNING_CURVE};{MEMBERSHIP_STABILITY}",
        "E8": UNCERTAINTY_LEDGER,
        "E9": PLANNING_BOOTSTRAP,
    }
    descriptive_models = {
        "E1": benchmark_models,
        "E2": site_models,
        "E3": threshold_models,
        "E4": trophic_models,
        "E7": ablation_models,
        "E8": uncertainty_models,
    }
    insufficient_models = {
        "E5": {"B1", "B2", "M0"},
        "E6": {"M0"},
    }
    t01_rows: list[dict[str, str]] = []
    for model_id in model_ids:
        source = availability_by_model[model_id]
        for experiment_number in range(1, 10):
            experiment_id = f"E{experiment_number}"
            if model_id not in experiment_model_scope[experiment_id]:
                state = "not_applicable"
                reason = "model_not_applicable_to_registered_experiment_surface"
            elif model_id in unavailable_models:
                state = "model_unavailable"
                reason = source["availability_reason"]
            elif model_id in descriptive_models.get(experiment_id, set()):
                state = "descriptive_available"
                if experiment_id == "E2":
                    reason = (
                        "internal_holdout_descriptive_available_but_legacy_gap_"
                        "insufficient_support_0_of_1050"
                    )
                elif experiment_id == "E7":
                    reason = (
                        "pairwise_ablation_descriptive_available_but_learning_"
                        "curve_and_membership_diagnostics_insufficient_0_of_4"
                    )
                else:
                    reason = "published_descriptive_surface_available"
            elif model_id in insufficient_models.get(experiment_id, set()):
                state = "insufficient_support"
                reason = "required_P1_comparator_is_model_unavailable"
            else:
                state = "not_applicable"
                reason = "model_not_applicable_to_registered_experiment_surface"
            t01_rows.append(
                {
                    "model_id": model_id,
                    "experiment_id": experiment_id,
                    "availability_state": state,
                    "availability_reason": reason,
                    "evidence_paths": (
                        f"{MODEL_AVAILABILITY};{experiment_sources[experiment_id]}"
                    ),
                    "authority_commit": contract.closure_source_commit,
                }
            )

    # Shared horizon denominators come from the benchmark surface and the
    # threshold-30 availability ledger; neither is recomputed from outcomes.
    attempted_by_horizon: dict[int, int] = {}
    for horizon in (1, 2, 3):
        values = {
            _integer(row, "origin_count", source=MODEL_METRICS)
            for row in metrics
            if _integer(row, "horizon_months", source=MODEL_METRICS) == horizon
        }
        if len(values) != 1:
            raise _error(f"T02 attempted denominator drifted for h{horizon}")
        attempted_by_horizon[horizon] = values.pop()
    target_available: dict[int, int] = {}
    for row in prevalence:
        if _numeric(row, "threshold_ug_l", source=THRESHOLD_PREVALENCE) != 30:
            continue
        horizon = _integer(row, "horizon_months", source=THRESHOLD_PREVALENCE)
        if horizon in target_available:
            raise _error(f"T02 duplicated threshold-30 row for h{horizon}")
        target_available[horizon] = _integer(
            row, "origin_count", source=THRESHOLD_PREVALENCE
        )
    if set(target_available) != {1, 2, 3}:
        raise _error("T02 lacks the three threshold-30 availability rows")

    # T02: one funnel per model and horizon.  Continuous-only F0/F1 use MAE;
    # the classification-capable models use PR-AUC as the representative row.
    t02_rows: list[dict[str, str]] = []
    for model_id in model_ids:
        funnel_metric = "mae" if model_id in {"F0", "F1"} else "pr_auc"
        for horizon in (1, 2, 3):
            selected = [
                row
                for row in metrics
                if row["model_id"] == model_id
                and row["metric"] == funnel_metric
                and row["estimand"] == "observation_weighted"
                and row["evaluation_cohort"] == "location_holdout"
                and _integer(row, "horizon_months", source=MODEL_METRICS)
                == horizon
            ]
            if model_id not in unavailable_models and not selected:
                raise _error(f"T02 lacks {model_id} h{horizon} funnel rows")
            if model_id in unavailable_models:
                state = "model_unavailable"
                input_min = input_max = success_min = success_max = ""
                failure_min = failure_max = str(attempted_by_horizon[horizon])
            else:
                estimated = [
                    row for row in selected if row["terminal_status"] == "estimated"
                ]
                state = "descriptive_available" if estimated else "not_applicable"
                intersections: list[int] = []
                successes: list[int] = []
                for row in estimated:
                    ineligible = _integer(
                        row, "input_ineligible_origin_count", source=MODEL_METRICS
                    )
                    if ineligible > target_available[horizon]:
                        raise _error(
                            f"T02 input-ineligible count exceeds target availability: {model_id} h{horizon}"
                        )
                    intersections.append(target_available[horizon] - ineligible)
                    successes.append(
                        _integer(
                            row, "successful_origin_count", source=MODEL_METRICS
                        )
                    )
                input_min = str(min(intersections)) if intersections else ""
                input_max = str(max(intersections)) if intersections else ""
                success_min = str(min(successes)) if successes else ""
                success_max = str(max(successes)) if successes else ""
                failures_for_intent = [
                    attempted_by_horizon[horizon] - value for value in successes
                ]
                failure_min = (
                    str(min(failures_for_intent)) if failures_for_intent else ""
                )
                failure_max = (
                    str(max(failures_for_intent)) if failures_for_intent else ""
                )
            t02_rows.append(
                {
                    "model_id": model_id,
                    "horizon_months": str(horizon),
                    "funnel_metric": funnel_metric,
                    "availability_state": state,
                    "attempted_origin_count": str(attempted_by_horizon[horizon]),
                    "target_available_origin_count": str(
                        target_available[horizon]
                    ),
                    "input_target_intersection_min": input_min,
                    "input_target_intersection_max": input_max,
                    "successful_origin_count_min": success_min,
                    "successful_origin_count_max": success_max,
                    "failed_origin_count_min": failure_min,
                    "failed_origin_count_max": failure_max,
                    "failure_definition": "attempted_minus_successful",
                    "registered_seed_row_count": str(len(selected)),
                    "evidence_paths": (
                        f"{MODEL_AVAILABILITY};{MODEL_METRICS};"
                        f"{THRESHOLD_PREVALENCE}"
                    ),
                }
            )

    # T03: exact 11 x 3 x 2 x 3 dual-estimand benchmark grid.
    t03_rows: list[dict[str, str]] = []
    estimands = (
        ("observation_weighted", "observation_weighted"),
        ("site_weighted", "site_weighted"),
    )
    for model_id in model_ids:
        for horizon in (1, 2, 3):
            for output_estimand, source_estimand in estimands:
                for metric in ("pr_auc", "brier", "f2"):
                    selected = [
                        row
                        for row in metrics
                        if row["model_id"] == model_id
                        and row["horizon_months"] == str(horizon)
                        and row["estimand"] == source_estimand
                        and row["metric"] == metric
                        and row["evaluation_cohort"] == "location_holdout"
                    ]
                    estimated = [
                        row
                        for row in selected
                        if row["terminal_status"] == "estimated" and row["value"]
                    ]
                    if model_id in unavailable_models:
                        state = "model_unavailable"
                    elif estimated:
                        state = "descriptive_available"
                    else:
                        state = "not_applicable"
                    if state == "descriptive_available":
                        evaluable_min, evaluable_max = _integer_range(
                            estimated,
                            "metric_evaluable_origin_count",
                            source=MODEL_METRICS,
                        )
                        value_mean = _decimal_mean(
                            estimated, "value", source=MODEL_METRICS
                        )
                        attempted = {
                            _integer(row, "origin_count", source=MODEL_METRICS)
                            for row in estimated
                        }
                        if len(attempted) != 1:
                            raise _error(
                                f"T03 attempted denominator drifted: {model_id} h{horizon} {metric}"
                            )
                        attempted_text = str(attempted.pop())
                    else:
                        evaluable_min = evaluable_max = value_mean = attempted_text = ""
                    t03_rows.append(
                        {
                            "model_id": model_id,
                            "horizon_months": str(horizon),
                            "estimand": output_estimand,
                            "source_estimand": source_estimand,
                            "metric": metric,
                            "availability_state": state,
                            "registered_seed_row_count": str(len(selected)),
                            "attempted_origin_count": attempted_text,
                            "metric_evaluable_origin_count_min": evaluable_min,
                            "metric_evaluable_origin_count_max": evaluable_max,
                            "value_mean": value_mean,
                            "evidence_path": MODEL_METRICS,
                        }
                    )

    # T04: 15 F1-F0 seed-level absolute-error deltas plus the nine A1-A0
    # horizon x metric descriptive deltas.  No interval is manufactured.
    t04_rows: list[dict[str, str]] = []
    f1_f0 = [
        row
        for row in comparisons
        if row["comparison_id"] == "F1_vs_F0"
        and row["metric"] == "absolute_error"
        and row["terminal_status"] == "estimated"
    ]
    for row in sorted(
        f1_f0, key=lambda item: (int(item["horizon_months"]), item["seed_slot"])
    ):
        t04_rows.append(
            {
                "comparison_id": "F1_vs_F0",
                "horizon_months": row["horizon_months"],
                "seed_slot": row["seed_slot"],
                "metric": "absolute_error",
                "availability_state": "descriptive_available",
                "paired_denominator": row["paired_origin_count"],
                "estimate": _decimal(row["mean_loss_difference_a_minus_b"]),
                "uncertainty": "",
                "estimate_definition": "mean_loss_F1_minus_F0",
                "evidence_path": MODEL_COMPARISON,
            }
        )
    a1_a0 = [
        row
        for row in ablation_pairs
        if row["challenger_model_id"] == "A1"
        and row["reference_model_id"] == "A0"
        and row["status"] == "available"
    ]
    for row in sorted(a1_a0, key=lambda item: int(item["horizon_months"])):
        for metric in ("delta_pr_auc", "delta_brier", "delta_mae"):
            t04_rows.append(
                {
                    "comparison_id": "A1_vs_A0",
                    "horizon_months": row["horizon_months"],
                    "seed_slot": "aggregate_five_slots",
                    "metric": metric,
                    "availability_state": "descriptive_available",
                    "paired_denominator": row["common_row_count"],
                    "estimate": _decimal(row[metric]),
                    "uncertainty": "",
                    "estimate_definition": "challenger_minus_reference",
                    "evidence_path": ABLATION_PAIRWISE,
                }
            )

    # T05: one model-level internal-holdout/site-transfer summary, including
    # the registered-but-unavailable A2 model.
    t05_rows: list[dict[str, str]] = []
    for model_id in model_ids:
        internal = [row for row in location_metrics if row["model_id"] == model_id]
        successful = [row for row in internal if row["terminal_status"] == "success"]
        model_gaps = [row for row in gaps if row["model_id"] == model_id]
        gap_estimable = [
            row for row in model_gaps if row["estimable"].lower() == "true"
        ]
        success_min, success_max = _integer_range(
            successful, "successful_event_count", source=LOCATION_HOLDOUT_METRICS
        )
        if model_id in unavailable_models:
            state = "model_unavailable"
            gap_state = "model_unavailable"
            reason = availability_by_model[model_id]["availability_reason"]
        elif successful:
            state = "descriptive_available"
            gap_state = (
                "descriptive_available" if gap_estimable else "insufficient_support"
            )
            reason = "internal_holdout_available_external_gap_not_estimable"
        else:
            state = "not_applicable"
            gap_state = "insufficient_support"
            reason = "no_applicable_internal_site_metric_and_no_frozen_legacy_surface"
        t05_rows.append(
            {
                "model_id": model_id,
                "availability_state": state,
                "registered_seed_slot_count": str(
                    len({row["seed_slot"] for row in internal})
                ),
                "registered_horizon_count": str(
                    len({row["horizon_months"] for row in internal})
                ),
                "internal_metric_row_count": str(len(internal)),
                "internal_successful_event_count_min": success_min,
                "internal_successful_event_count_max": success_max,
                "generalization_gap_cell_count": str(len(model_gaps)),
                "generalization_gap_estimable_count": str(len(gap_estimable)),
                "generalization_gap_state": gap_state,
                "reason": reason,
                "evidence_paths": (
                    f"{MODEL_AVAILABILITY};{LOCATION_HOLDOUT_METRICS};"
                    f"{GENERALIZATION_GAP}"
                ),
            }
        )

    # T06: twelve prevalence records plus the 36 registered rank comparisons.
    t06_rows: list[dict[str, str]] = []
    for row in prevalence:
        t06_rows.append(
            {
                "record_type": "threshold_prevalence",
                "horizon_months": row["horizon_months"],
                "threshold_ug_l": row["threshold_ug_l"],
                "metric": "",
                "reference_threshold_ug_l": "",
                "origin_count": row["origin_count"],
                "positive_count": row["positive_count"],
                "positive_rate": _decimal(row["positive_rate"]),
                "positive_site_count": row["positive_site_count"],
                "compared_model_count": "",
                "kendall_tau": "",
                "availability_state": "descriptive_available",
                "evidence_path": THRESHOLD_PREVALENCE,
            }
        )
    for row in ranks:
        t06_rows.append(
            {
                "record_type": "rank_stability",
                "horizon_months": row["horizon_months"],
                "threshold_ug_l": row["compared_threshold_ug_l"],
                "metric": row["metric"],
                "reference_threshold_ug_l": row[
                    "reference_threshold_ug_l"
                ],
                "origin_count": "",
                "positive_count": "",
                "positive_rate": "",
                "positive_site_count": "",
                "compared_model_count": row["compared_model_count"],
                "kendall_tau": _decimal(row["kendall_tau"]),
                "availability_state": (
                    "descriptive_available"
                    if row["estimable"].lower() == "true"
                    else "insufficient_support"
                ),
                "evidence_path": RANK_STABILITY,
            }
        )

    # T07: five ordinal references x B1/B2 x three horizons, aggregated over
    # the five frozen seeds, plus the explicit NLA semantic sentinel.
    if nla_semantic:
        raise _error("T07 NLA semantic source must remain an empty sentinel")
    t07_rows: list[dict[str, str]] = []
    trophic_sources = (
        (TROPHIC_PROXY, trophic, ("future_chla_operational_proxy",)),
        (
            CARLSON_METRICS,
            carlson,
            ("tsi_tp_h", "tsi_sd_h", "tsi_non_chla_h", "tsi_all_h"),
        ),
    )
    for source_path, source_rows, references in trophic_sources:
        for reference in references:
            for model_id in ("B1", "B2"):
                for horizon in (1, 2, 3):
                    selected = [
                        row
                        for row in source_rows
                        if row["reference"] == reference
                        and row["model_id"] == model_id
                        and row["horizon_months"] == str(horizon)
                        and row["status"] == "available"
                    ]
                    if not selected:
                        raise _error(
                            f"T07 lacks {reference} {model_id} h{horizon} rows"
                        )
                    evaluation_min, evaluation_max = _integer_range(
                        selected, "evaluation_row_count", source=source_path
                    )
                    t07_rows.append(
                        {
                            "record_type": "ordinal_performance",
                            "reference": reference,
                            "model_id": model_id,
                            "horizon_months": str(horizon),
                            "availability_state": "descriptive_available",
                            "seed_row_count": str(len(selected)),
                            "evaluation_row_count_min": evaluation_min,
                            "evaluation_row_count_max": evaluation_max,
                            "macro_f1_mean": _decimal_mean(
                                selected, "macro_f1", source=source_path
                            ),
                            "quadratic_weighted_kappa_mean": _decimal_mean(
                                selected,
                                "quadratic_weighted_kappa",
                                source=source_path,
                            ),
                            "ordinal_mae_mean": _decimal_mean(
                                selected, "ordinal_mae", source=source_path
                            ),
                            "severe_error_rate_mean": _decimal_mean(
                                selected, "severe_error_rate", source=source_path
                            ),
                            "limitation": "descriptive_internal_WQP_reference_only",
                            "evidence_path": source_path,
                        }
                    )
    t07_rows.append(
        {
            "record_type": "nla_semantic_sentinel",
            "reference": "nla_provenance_only",
            "model_id": "",
            "horizon_months": "",
            "availability_state": "not_applicable",
            "seed_row_count": "0",
            "evaluation_row_count_min": "",
            "evaluation_row_count_max": "",
            "macro_f1_mean": "",
            "quadratic_weighted_kappa_mean": "",
            "ordinal_mae_mean": "",
            "severe_error_rate_mean": "",
            "limitation": "NLA_does_not_validate_monthly_WQP_targets",
            "evidence_path": NLA_SEMANTIC_METRICS,
        }
    )

    # T08: expand the exact registered Holm universe.  Family B expands its
    # 13 registry rows into scenario x horizon x target-event cells (78).
    registry_by_id = _unique_index(
        registry, "hypothesis_id", source=HYPOTHESIS_REGISTRY
    )
    multiplicity_by_id = _unique_index(
        multiplicity, "hypothesis_id", source=MULTIPLICITY_REPORT
    )
    if set(registry_by_id) != set(multiplicity_by_id):
        raise _error("T08 hypothesis and multiplicity registries disagree")
    planning_by_scenario = _unique_index(
        planning, "scenario_id", source=PLANNING_BOOTSTRAP
    )
    t08_rows: list[dict[str, str]] = []
    for registered in registry:
        hypothesis_id = registered["hypothesis_id"]
        family = registered["multiplicity_family"]
        reported = multiplicity_by_id[hypothesis_id]
        expected_universe = contract.holm_universes.get(family)
        if (
            expected_universe is None
            or _integer(
                registered,
                "multiplicity_universe_size",
                source=HYPOTHESIS_REGISTRY,
            )
            != expected_universe
            or _integer(
                reported,
                "multiplicity_universe_size",
                source=MULTIPLICITY_REPORT,
            )
            != expected_universe
            or reported["multiplicity_family"] != family
            or _boolean_text(
                registered["holm_universe_retained"],
                context=f"{HYPOTHESIS_REGISTRY}:{hypothesis_id}",
            )
            != "true"
            or _boolean_text(
                reported["holm_universe_retained"],
                context=f"{MULTIPLICITY_REPORT}:{hypothesis_id}",
            )
            != "true"
        ):
            raise _error(f"T08 Holm registration drifted: {hypothesis_id}")
        common = {
            "hypothesis_id": hypothesis_id,
            "multiplicity_family": family,
            "universe_size": str(expected_universe),
            "comparison_id": registered["comparison_id"],
            "estimand": registered["estimand"],
            "availability_state": "model_unavailable",
            "availability_reason": registered["availability_reason"],
            "status": reported["terminal_status"],
            "raw_p_value": reported["raw_p_value"],
            "holm_p_value": reported["holm_p_value"],
            "holm_universe_retained": "true",
        }
        if common["raw_p_value"] or common["holm_p_value"]:
            raise _error(f"T08 non-estimable cell has a p-value: {hypothesis_id}")
        if family == "B":
            scenario = registered["comparison_id"].removeprefix("M0_vs_P1_")
            scenario_failures = [
                row for row in failures if row["scenario_id"] == scenario
            ]
            if len(scenario_failures) != 6:
                raise _error(f"T08 family-B scenario is not exact6: {scenario}")
            for failure in scenario_failures:
                t08_rows.append(
                    {
                        "cell_id": (
                            f"{hypothesis_id}:h{failure['horizon_months']}:"
                            f"{failure['target_event']}"
                        ),
                        **common,
                        "horizon_months": failure["horizon_months"],
                        "endpoint": failure["target_event"],
                        "attempted_denominator": failure[
                            "intended_prediction_row_count"
                        ],
                        "successful_denominator": failure[
                            "available_prediction_row_count"
                        ],
                        "evidence_paths": (
                            f"{HYPOTHESIS_REGISTRY};{MULTIPLICITY_REPORT};"
                            f"{FAILURE_REGISTRY}"
                        ),
                    }
                )
        else:
            attempted = str(sum(attempted_by_horizon.values()))
            evidence = f"{HYPOTHESIS_REGISTRY};{MULTIPLICITY_REPORT}"
            if family == "D":
                scenario = registered["comparison_id"].removesuffix(
                    "_vs_no_action"
                )
                planned = planning_by_scenario.get(scenario)
                if planned is None:
                    raise _error(f"T08 planning scenario is absent: {scenario}")
                attempted = planned["row_count"]
                evidence += f";{PLANNING_BOOTSTRAP}"
            t08_rows.append(
                {
                    "cell_id": hypothesis_id,
                    **common,
                    "horizon_months": "",
                    "endpoint": registered["endpoints"],
                    "attempted_denominator": attempted,
                    "successful_denominator": "0",
                    "evidence_paths": evidence,
                }
            )
    t08_family_counts = {
        family: sum(row["multiplicity_family"] == family for row in t08_rows)
        for family in contract.holm_universes
    }
    if t08_family_counts != dict(contract.holm_universes):
        raise _error(
            f"T08 Holm cell counts drifted: observed {t08_family_counts}"
        )

    # T09: three A1-A0 horizon summaries, three preregistered learning-size
    # sentinels and one membership-stability sentinel.
    t09_rows: list[dict[str, str]] = []
    for row in sorted(a1_a0, key=lambda item: int(item["horizon_months"])):
        t09_rows.append(
            {
                "record_type": "A1_vs_A0",
                "model_or_pair": "A1_vs_A0",
                "horizon_months": row["horizon_months"],
                "training_rows_per_module": "",
                "module": "",
                "feature": "",
                "availability_state": "descriptive_available",
                "status": row["status"],
                "denominator": row["common_row_count"],
                "delta_pr_auc": _decimal(row["delta_pr_auc"]),
                "delta_brier": _decimal(row["delta_brier"]),
                "delta_mae": _decimal(row["delta_mae"]),
                "saturation_claim_authorized": "",
                "membership_stability_claim_authorized": "",
                "limitation": "descriptive_no_interval",
                "evidence_path": ABLATION_PAIRWISE,
            }
        )
    for row in learning:
        t09_rows.append(
            {
                "record_type": "learning_curve_sentinel",
                "model_or_pair": "A1",
                "horizon_months": "",
                "training_rows_per_module": row["training_rows_per_module"],
                "module": "",
                "feature": "",
                "availability_state": "insufficient_support",
                "status": row["status"],
                "denominator": "",
                "delta_pr_auc": "",
                "delta_brier": "",
                "delta_mae": "",
                "saturation_claim_authorized": _boolean_text(
                    row["saturation_claim_authorized"],
                    context=f"{LEARNING_CURVE}:saturation_claim_authorized",
                ),
                "membership_stability_claim_authorized": "",
                "limitation": row["limitation"],
                "evidence_path": LEARNING_CURVE,
            }
        )
    if len(membership) != 1:
        raise _error("T09 membership-stability sentinel drifted from exact1")
    membership_row = membership[0]
    t09_rows.append(
        {
            "record_type": "membership_stability_sentinel",
            "model_or_pair": membership_row["model_id"],
            "horizon_months": "",
            "training_rows_per_module": "",
            "module": membership_row["module"],
            "feature": membership_row["feature"],
            "availability_state": "insufficient_support",
            "status": membership_row["status"],
            "denominator": membership_row["seed_count"],
            "delta_pr_auc": "",
            "delta_brier": "",
            "delta_mae": "",
            "saturation_claim_authorized": "",
            "membership_stability_claim_authorized": "false",
            "limitation": "membership_stability_not_available",
            "evidence_path": MEMBERSHIP_STABILITY,
        }
    )

    # T10: aggregate five seed rows for each model x version x horizon x
    # nominal-coverage group while preserving denominator ranges.
    uncertainty_groups: dict[
        tuple[str, str, str, str], list[Mapping[str, str]]
    ] = {}
    for row in uncertainty:
        nominal = _render_number(
            _numeric(row, "nominal_coverage", source=UNCERTAINTY_LEDGER)
        )
        key = (
            row["model_id"],
            row["interval_version"],
            row["horizon_months"],
            nominal,
        )
        uncertainty_groups.setdefault(key, []).append(row)
    t10_rows: list[dict[str, str]] = []
    for key in sorted(
        uncertainty_groups,
        key=lambda item: (item[0], item[1], int(item[2]), Decimal(item[3])),
    ):
        selected = uncertainty_groups[key]
        if any(row["status"] != "available" for row in selected):
            raise _error(f"T10 uncertainty group is unavailable: {key}")
        attempted_min, attempted_max = _integer_range(
            selected, "attempted_row_count", source=UNCERTAINTY_LEDGER
        )
        interval_min, interval_max = _integer_range(
            selected, "interval_row_count", source=UNCERTAINTY_LEDGER
        )
        t10_rows.append(
            {
                "model_id": key[0],
                "interval_version": key[1],
                "horizon_months": key[2],
                "nominal_coverage": key[3],
                "availability_state": "descriptive_available",
                "seed_row_count": str(len(selected)),
                "attempted_row_count_min": attempted_min,
                "attempted_row_count_max": attempted_max,
                "interval_row_count_min": interval_min,
                "interval_row_count_max": interval_max,
                "empirical_coverage_mean": _decimal_mean(
                    selected, "empirical_coverage", source=UNCERTAINTY_LEDGER
                ),
                "absolute_coverage_error_mean": _decimal_mean(
                    selected,
                    "absolute_coverage_error",
                    source=UNCERTAINTY_LEDGER,
                ),
                "mean_interval_width_mean": _decimal_mean(
                    selected, "mean_interval_width", source=UNCERTAINTY_LEDGER
                ),
                "winkler_interval_score_mean": _decimal_mean(
                    selected,
                    "winkler_interval_score",
                    source=UNCERTAINTY_LEDGER,
                ),
                "evidence_path": UNCERTAINTY_LEDGER,
            }
        )

    # T11: retain the 78 E6 and nine E9 failed cells as explicit
    # non-estimable records; estimates and intervals remain empty.
    t11_rows: list[dict[str, str]] = []
    for row in failures:
        t11_rows.append(
            {
                "experiment_id": "E6",
                "record_id": (
                    f"E6:{row['scenario_id']}:h{row['horizon_months']}:"
                    f"{row['target_event']}"
                ),
                "scenario_id": row["scenario_id"],
                "horizon_months": row["horizon_months"],
                "endpoint": row["target_event"],
                "availability_state": "model_unavailable",
                "status": row["terminal_status"],
                "attempted_denominator": row["intended_prediction_row_count"],
                "successful_denominator": row["available_prediction_row_count"],
                "estimate": "",
                "ci95_lower": "",
                "ci95_upper": "",
                "p_value": "",
                "limitation": row["reason"],
                "evidence_path": FAILURE_REGISTRY,
            }
        )
    for row in planning:
        t11_rows.append(
            {
                "experiment_id": "E9",
                "record_id": f"E9:{row['scenario_id']}",
                "scenario_id": row["scenario_id"],
                "horizon_months": "",
                "endpoint": "delta_objective_vs_no_action",
                "availability_state": "model_unavailable",
                "status": row["status"],
                "attempted_denominator": row["row_count"],
                "successful_denominator": "0",
                "estimate": row["estimate"],
                "ci95_lower": row["ci95_lower"],
                "ci95_upper": row["ci95_upper"],
                "p_value": row["p_value_greater"],
                "limitation": "P1_model_unavailable_no_action_ranking",
                "evidence_path": PLANNING_BOOTSTRAP,
            }
        )
    if any(
        row[field]
        for row in t11_rows
        for field in ("estimate", "ci95_lower", "ci95_upper", "p_value")
    ):
        raise _error("T11 non-estimable rows contain an estimate, interval or p-value")

    # T12: five typed software-evidence records, distilled only from the three
    # allowlisted E10 JSON artifacts.
    runtime = _child_mapping(environment, "runtime", source=API_ENVIRONMENT)
    tool_versions = _child_mapping(
        environment, "tool_versions", source=API_ENVIRONMENT
    )
    runtime_versions = _validated_runtime_versions(environment)
    environment_safety = _child_mapping(
        environment, "outcome_safety", source=API_ENVIRONMENT
    )
    openapi_paths = _child_mapping(openapi, "paths", source=API_OPENAPI)
    openapi_info = _child_mapping(openapi, "info", source=API_OPENAPI)
    verification = _child_mapping(
        software, "verification", source=SOFTWARE_MANIFEST
    )
    public_tests = _child_mapping(
        verification, "public_tests", source=SOFTWARE_MANIFEST
    )
    e2e_tests = _child_mapping(
        verification, "end_to_end_tests", source=SOFTWARE_MANIFEST
    )
    openapi_contract = _child_mapping(
        verification, "openapi_contract", source=SOFTWARE_MANIFEST
    )
    software_safety = _child_mapping(
        software, "outcome_safety", source=SOFTWARE_MANIFEST
    )

    def test_summary(record: Mapping[str, Any], *, context: str) -> tuple[str, str, str, str]:
        tests = int(record.get("tests", -1))
        failures_count = int(record.get("failures", -1))
        errors_count = int(record.get("errors", -1))
        skips = int(record.get("skipped", -1))
        passes = tests - failures_count - errors_count - skips
        if min(tests, failures_count, errors_count, skips, passes) < 0:
            raise _error(f"{context} has invalid test counts")
        status = "passed" if failures_count == 0 and errors_count == 0 else "failed"
        return status, str(tests), str(passes), str(skips)

    public_status, public_count, public_pass, public_skip = test_summary(
        public_tests, context="T12 public tests"
    )
    e2e_status, e2e_count, e2e_pass, e2e_skip = test_summary(
        e2e_tests, context="T12 end-to-end tests"
    )
    verified_path_count = int(openapi_contract.get("openapi_path_count", -1))
    if verified_path_count != len(openapi_paths):
        raise _error("T12 OpenAPI path count disagrees with the verified contract")
    verified_operation_count = int(
        openapi_contract.get("openapi_operation_count", -1)
    )
    documented_operation_count = int(
        openapi_contract.get("documented_operation_count", -1)
    )
    source_artifact_count = int(software.get("source_artifact_count", -1))
    if (
        verified_operation_count != 83
        or documented_operation_count != 38
        or source_artifact_count != 6
    ):
        raise _error("T12 OpenAPI/source-artifact evidence counts drifted")
    safety_fields = (
        "outcome_paths_opened",
        "target_paths_opened",
        "private_full_opened",
    )
    environment_safety_values = {
        field: _boolean_text(
            environment_safety.get(field), context=f"{API_ENVIRONMENT}:{field}"
        )
        for field in safety_fields
    }
    software_safety_values = {
        field: _boolean_text(
            software_safety.get(field), context=f"{SOFTWARE_MANIFEST}:{field}"
        )
        for field in safety_fields
    }
    if environment_safety_values != software_safety_values:
        raise _error("T12 outcome-safety records disagree")
    t12_rows = [
        {
            "evidence_id": "runtime_environment",
            "status": "captured",
            "repository_commit": str(environment.get("repository_commit", "")),
            "schema_or_version": str(environment.get("schema_version", "")),
            "test_count": "",
            "pass_count": "",
            "skip_count": "",
            "path_count": "",
            "operation_count": "",
            "documented_operation_count": "",
            "source_artifact_count": "",
            "outcome_paths_opened": "",
            "target_paths_opened": "",
            "private_full_opened": "",
            "detail": (
                f"python={runtime_versions['python']};"
                f"fastapi={runtime_versions['fastapi']};"
                f"dvc={runtime_versions['dvc']};"
                f"app={runtime.get('app_version', '')};"
                f"pytest={tool_versions.get('pytest_version', '')}"
            ),
            "evidence_path": API_ENVIRONMENT,
        },
        {
            "evidence_id": "openapi_contract",
            "status": (
                "passed"
                if _boolean_text(
                    openapi_contract.get("valid"),
                    context=f"{SOFTWARE_MANIFEST}:openapi_contract.valid",
                )
                == "true"
                else "failed"
            ),
            "repository_commit": str(environment.get("repository_commit", "")),
            "schema_or_version": str(openapi.get("openapi", "")),
            "test_count": "",
            "pass_count": "",
            "skip_count": "",
            "path_count": str(len(openapi_paths)),
            "operation_count": str(verified_operation_count),
            "documented_operation_count": str(documented_operation_count),
            "source_artifact_count": "",
            "outcome_paths_opened": "",
            "target_paths_opened": "",
            "private_full_opened": "",
            "detail": (
                f"title={openapi_info.get('title', '')};"
                f"version={openapi_info.get('version', '')};"
                f"operation_ids_unique={_boolean_text(openapi_contract.get('operation_ids_unique'), context='T12 operation_ids_unique')}"
            ),
            "evidence_path": f"{API_OPENAPI};{SOFTWARE_MANIFEST}",
        },
        {
            "evidence_id": "public_tests",
            "status": public_status,
            "repository_commit": str(software.get("repository_commit", "")),
            "schema_or_version": str(software.get("schema_version", "")),
            "test_count": public_count,
            "pass_count": public_pass,
            "skip_count": public_skip,
            "path_count": "",
            "operation_count": "",
            "documented_operation_count": "",
            "source_artifact_count": "",
            "outcome_paths_opened": "",
            "target_paths_opened": "",
            "private_full_opened": "",
            "detail": "exact_frozen_public_suite",
            "evidence_path": SOFTWARE_MANIFEST,
        },
        {
            "evidence_id": "synthetic_e2e",
            "status": e2e_status,
            "repository_commit": str(software.get("repository_commit", "")),
            "schema_or_version": str(software.get("schema_version", "")),
            "test_count": e2e_count,
            "pass_count": e2e_pass,
            "skip_count": e2e_skip,
            "path_count": "",
            "operation_count": "",
            "documented_operation_count": "",
            "source_artifact_count": "",
            "outcome_paths_opened": "",
            "target_paths_opened": "",
            "private_full_opened": "",
            "detail": "synthetic_external_non_closure_outcome",
            "evidence_path": SOFTWARE_MANIFEST,
        },
        {
            "evidence_id": "restricted_path_safety",
            "status": (
                "passed"
                if set(software_safety_values.values()) == {"false"}
                else "failed"
            ),
            "repository_commit": str(software.get("repository_commit", "")),
            "schema_or_version": str(software.get("schema_version", "")),
            "test_count": "",
            "pass_count": "",
            "skip_count": "",
            "path_count": "",
            "operation_count": "",
            "documented_operation_count": "",
            "source_artifact_count": str(source_artifact_count),
            **software_safety_values,
            "detail": "restricted_outcome_target_and_private_context_remained_closed",
            "evidence_path": f"{API_ENVIRONMENT};{SOFTWARE_MANIFEST}",
        },
    ]

    return {
        "T01_model_experiment_availability.csv": _table_bytes(
            contract,
            "T01",
            t01_rows,
            (
                "model_id",
                "experiment_id",
                "availability_state",
                "availability_reason",
                "evidence_paths",
                "authority_commit",
            ),
        ),
        "T02_intent_to_predict_funnel.csv": _table_bytes(
            contract,
            "T02",
            t02_rows,
            (
                "model_id",
                "horizon_months",
                "funnel_metric",
                "availability_state",
                "attempted_origin_count",
                "target_available_origin_count",
                "input_target_intersection_min",
                "input_target_intersection_max",
                "successful_origin_count_min",
                "successful_origin_count_max",
                "failed_origin_count_min",
                "failed_origin_count_max",
                "failure_definition",
                "registered_seed_row_count",
                "evidence_paths",
            ),
        ),
        "T03_dual_benchmark.csv": _table_bytes(
            contract,
            "T03",
            t03_rows,
            (
                "model_id",
                "horizon_months",
                "estimand",
                "source_estimand",
                "metric",
                "availability_state",
                "registered_seed_row_count",
                "attempted_origin_count",
                "metric_evaluable_origin_count_min",
                "metric_evaluable_origin_count_max",
                "value_mean",
                "evidence_path",
            ),
        ),
        "T04_descriptive_deltas.csv": _table_bytes(
            contract,
            "T04",
            t04_rows,
            (
                "comparison_id",
                "horizon_months",
                "seed_slot",
                "metric",
                "availability_state",
                "paired_denominator",
                "estimate",
                "uncertainty",
                "estimate_definition",
                "evidence_path",
            ),
        ),
        "T05_site_transfer.csv": _table_bytes(
            contract,
            "T05",
            t05_rows,
            (
                "model_id",
                "availability_state",
                "registered_seed_slot_count",
                "registered_horizon_count",
                "internal_metric_row_count",
                "internal_successful_event_count_min",
                "internal_successful_event_count_max",
                "generalization_gap_cell_count",
                "generalization_gap_estimable_count",
                "generalization_gap_state",
                "reason",
                "evidence_paths",
            ),
        ),
        "T06_threshold_sensitivity.csv": _table_bytes(
            contract,
            "T06",
            t06_rows,
            (
                "record_type",
                "horizon_months",
                "threshold_ug_l",
                "metric",
                "reference_threshold_ug_l",
                "origin_count",
                "positive_count",
                "positive_rate",
                "positive_site_count",
                "compared_model_count",
                "kendall_tau",
                "availability_state",
                "evidence_path",
            ),
        ),
        "T07_trophic_performance.csv": _table_bytes(
            contract,
            "T07",
            t07_rows,
            (
                "record_type",
                "reference",
                "model_id",
                "horizon_months",
                "availability_state",
                "seed_row_count",
                "evaluation_row_count_min",
                "evaluation_row_count_max",
                "macro_f1_mean",
                "quadratic_weighted_kappa_mean",
                "ordinal_mae_mean",
                "severe_error_rate_mean",
                "limitation",
                "evidence_path",
            ),
        ),
        "T08_multiplicity_ledger.csv": _table_bytes(
            contract,
            "T08",
            t08_rows,
            (
                "cell_id",
                "hypothesis_id",
                "multiplicity_family",
                "universe_size",
                "comparison_id",
                "horizon_months",
                "endpoint",
                "estimand",
                "availability_state",
                "availability_reason",
                "status",
                "attempted_denominator",
                "successful_denominator",
                "raw_p_value",
                "holm_p_value",
                "holm_universe_retained",
                "evidence_paths",
            ),
        ),
        "T09_anfis_ablation.csv": _table_bytes(
            contract,
            "T09",
            t09_rows,
            (
                "record_type",
                "model_or_pair",
                "horizon_months",
                "training_rows_per_module",
                "module",
                "feature",
                "availability_state",
                "status",
                "denominator",
                "delta_pr_auc",
                "delta_brier",
                "delta_mae",
                "saturation_claim_authorized",
                "membership_stability_claim_authorized",
                "limitation",
                "evidence_path",
            ),
        ),
        "T10_uncertainty.csv": _table_bytes(
            contract,
            "T10",
            t10_rows,
            (
                "model_id",
                "interval_version",
                "horizon_months",
                "nominal_coverage",
                "availability_state",
                "seed_row_count",
                "attempted_row_count_min",
                "attempted_row_count_max",
                "interval_row_count_min",
                "interval_row_count_max",
                "empirical_coverage_mean",
                "absolute_coverage_error_mean",
                "mean_interval_width_mean",
                "winkler_interval_score_mean",
                "evidence_path",
            ),
        ),
        "T11_e6_e9_unavailability.csv": _table_bytes(
            contract,
            "T11",
            t11_rows,
            (
                "experiment_id",
                "record_id",
                "scenario_id",
                "horizon_months",
                "endpoint",
                "availability_state",
                "status",
                "attempted_denominator",
                "successful_denominator",
                "estimate",
                "ci95_lower",
                "ci95_upper",
                "p_value",
                "limitation",
                "evidence_path",
            ),
        ),
        "T12_software_evidence.csv": _table_bytes(
            contract,
            "T12",
            t12_rows,
            (
                "evidence_id",
                "status",
                "repository_commit",
                "schema_or_version",
                "test_count",
                "pass_count",
                "skip_count",
                "path_count",
                "operation_count",
                "documented_operation_count",
                "source_artifact_count",
                "outcome_paths_opened",
                "target_paths_opened",
                "private_full_opened",
                "detail",
                "evidence_path",
            ),
        ),
    }


def _figure_f01_intent_to_predict(
    contract: SynthesisContract, *, root: Path
) -> bytes:
    metrics = _read_allowed_csv(contract, root, MODEL_METRICS)
    availability_rows = _read_allowed_csv(contract, root, MODEL_AVAILABILITY)
    prevalence = _read_allowed_csv(contract, root, THRESHOLD_PREVALENCE)
    availability = {
        row["model_id"]: row["availability"] for row in availability_rows
    }
    models = list(availability)
    if len(models) != len(set(models)) or not models:
        raise _error("F01 model availability order is empty or duplicated")

    target_available: dict[int, int] = {}
    for row in prevalence:
        if Decimal(row["threshold_ug_l"]) != Decimal(30):
            continue
        horizon = _integer(row, "horizon_months", source=THRESHOLD_PREVALENCE)
        if horizon in target_available:
            raise _error("F01 threshold-30 target availability is duplicated")
        target_available[horizon] = _integer(
            row, "origin_count", source=THRESHOLD_PREVALENCE
        )
    if set(target_available) != {1, 2, 3}:
        raise _error("F01 requires target availability for horizons 1, 2 and 3")

    grouped: dict[tuple[str, int], list[Mapping[str, str]]] = {}
    for row in metrics:
        if (
            row.get("evaluation_cohort") != "location_holdout"
            or row.get("metric") != "mae"
            or row.get("estimand") != "observation_weighted"
        ):
            continue
        horizon = _integer(row, "horizon_months", source=MODEL_METRICS)
        grouped.setdefault((row["model_id"], horizon), []).append(row)

    attempted_by_horizon: dict[int, int] = {}
    for horizon in (1, 2, 3):
        values = {
            _integer(row, "origin_count", source=MODEL_METRICS)
            for (model_id, observed_horizon), rows in grouped.items()
            if observed_horizon == horizon and availability.get(model_id) == "available"
            for row in rows
        }
        if len(values) != 1:
            raise _error(f"F01 attempted denominator drifted for h{horizon}")
        attempted_by_horizon[horizon] = values.pop()
    total_attempts = sum(attempted_by_horizon.values())

    row_height = 29
    header_height = 158
    height = header_height + (len(models) + 1) * 3 * row_height + 80
    description = _figure_description(
        (MODEL_METRICS, MODEL_AVAILABILITY, THRESHOLD_PREVALENCE),
        filters=(
            "model_metrics: evaluation_cohort=location_holdout, metric=mae, "
            "estimand=observation_weighted; threshold_prevalence: "
            "threshold_ug_l=30; input-eligible intersection equals target "
            "available minus input_ineligible_origin_count; ranges preserve "
            "all registered seed slots"
        ),
    )
    canvas = _SvgCanvas(
        "F01",
        contract.artifact_captions["F01"],
        description,
        "F01 - Intent-to-predict funnel by horizon and model",
        width=1500,
        height=height,
    )
    canvas.text(
        40,
        72,
        "Total origin-horizon attempts: " + f"{total_attempts:,}",
        class_="subtitle",
    )
    canvas.text(
        40,
        98,
        "Layers: attempts -> target available (cutoff 30) -> input eligible -> success; N/A is never drawn as zero.",
        class_="small",
    )
    bar_x = 330
    bar_width = 900
    maximum = max(attempted_by_horizon.values())
    for tick in (0, maximum // 2, maximum):
        x = bar_x + tick * bar_width // maximum
        canvas.element(
            "line",
            x1=x,
            y1=120,
            x2=x,
            y2=height - 42,
            class_="grid",
        )
        canvas.text(x, 116, str(tick), class_="small", text_anchor="middle")
    canvas.element(
        "line",
        x1=bar_x,
        y1=124,
        x2=bar_x + bar_width,
        y2=124,
        class_="axis",
    )
    canvas.text(bar_x + bar_width // 2, 112, "origins", class_="small", text_anchor="middle")

    colors = {
        "attempted": "#dbeafe",
        "target": "#93c5fd",
        "input": "#3b82f6",
        "success": "#1e3a8a",
    }
    y = header_height
    for horizon in (1, 2, 3):
        canvas.text(40, y, f"Horizon h{horizon}", class_="label", font_weight="700")
        canvas.text(
            145,
            y,
            f"attempted={attempted_by_horizon[horizon]}; target={target_available[horizon]}",
            class_="small",
        )
        y += row_height
        for model_id in models:
            rows = grouped.get((model_id, horizon), [])
            state = availability[model_id]
            if state == "available" and not rows:
                raise _error(f"F01 available model lacks h{horizon} rows: {model_id}")
            input_values = [
                max(
                    0,
                    target_available[horizon]
                    - _integer(
                        row,
                        "input_ineligible_origin_count",
                        source=MODEL_METRICS,
                    ),
                )
                for row in rows
            ]
            success_values = [
                _integer(row, "successful_origin_count", source=MODEL_METRICS)
                for row in rows
            ]
            attempted = attempted_by_horizon[horizon]
            input_mean = (
                sum(input_values) // len(input_values) if input_values else 0
            )
            success_mean = (
                sum(success_values) // len(success_values) if success_values else 0
            )
            canvas.open_group(
                class_="funnel-series",
                data_series=model_id,
                data_horizon=horizon,
                data_availability=state,
                data_attempted=attempted,
                data_target_available=target_available[horizon],
                data_input_eligible_min=min(input_values) if input_values else "N/A",
                data_input_eligible_max=max(input_values) if input_values else "N/A",
                data_success_min=min(success_values) if success_values else "N/A",
                data_success_max=max(success_values) if success_values else "N/A",
                data_value=(
                    _range_label(success_values)
                    if state == "available"
                    else "N/A"
                ),
                data_seed_count=len(rows),
            )
            canvas.text(64, y + 12, model_id, class_="label")
            canvas.element(
                "rect",
                x=bar_x,
                y=y,
                width=attempted * bar_width // maximum,
                height=15,
                fill=colors["attempted"],
            )
            canvas.element(
                "rect",
                x=bar_x,
                y=y,
                width=target_available[horizon] * bar_width // maximum,
                height=15,
                fill=colors["target"],
            )
            if state == "available":
                canvas.element(
                    "rect",
                    x=bar_x,
                    y=y,
                    width=input_mean * bar_width // maximum,
                    height=15,
                    fill=colors["input"],
                )
                canvas.element(
                    "rect",
                    x=bar_x,
                    y=y + 3,
                    width=success_mean * bar_width // maximum,
                    height=9,
                    fill=colors["success"],
                )
                value_text = (
                    f"{attempted} → {target_available[horizon]} → "
                    f"{_range_label(input_values)} → {_range_label(success_values)}"
                )
            else:
                canvas.element(
                    "rect",
                    x=bar_x + bar_width - 62,
                    y=y - 1,
                    width=62,
                    height=17,
                    class_="na",
                )
                canvas.text(
                    bar_x + bar_width - 31,
                    y + 12,
                    "N/A",
                    class_="value",
                    text_anchor="middle",
                )
                value_text = f"{attempted} → {target_available[horizon]} → N/A → N/A"
            canvas.text(1250, y + 12, value_text, class_="value")
            canvas.close_group()
            y += row_height
        y += row_height

    legend_y = height - 25
    legend_x = 330
    for label, key in (
        ("attempted", "attempted"),
        ("target available", "target"),
        ("input eligible", "input"),
        ("success", "success"),
    ):
        canvas.element(
            "rect", x=legend_x, y=legend_y - 11, width=20, height=11, fill=colors[key]
        )
        canvas.text(legend_x + 27, legend_y, label, class_="small")
        legend_x += 190
    return canvas.finish()


def _figure_f02_benchmark_metrics(
    contract: SynthesisContract, *, root: Path
) -> bytes:
    rows = _read_allowed_csv(contract, root, MODEL_METRICS)
    availability_rows = _read_allowed_csv(contract, root, MODEL_AVAILABILITY)
    availability = {
        row["model_id"]: row["availability"] for row in availability_rows
    }
    models = list(availability)
    if tuple(models) != MODEL_IDS or set(availability.values()) != {
        "available",
        "unavailable",
    }:
        raise _error("F02 model availability order/vocabulary drifted")

    estimands = (
        ("observation_weighted", "observation_weighted"),
        ("site_weighted", "site_weighted"),
    )
    metrics = ("pr_auc", "brier", "f2")
    cells = {
        (estimand, metric, model_id, horizon): _benchmark_cell(
            rows,
            model_id=model_id,
            horizon=horizon,
            estimand=estimand,
            metric=metric,
        )
        for estimand, _display in estimands
        for metric in metrics
        for model_id in models
        for horizon in (1, 2, 3)
    }
    if len(cells) != 198:
        raise _error("F02 benchmark availability grid drifted from exact198")
    horizon_colors = {1: "#1d4ed8", 2: "#7c3aed", 3: "#c2410c"}
    description = _figure_description(
        (MODEL_METRICS, MODEL_AVAILABILITY),
        filters=(
            "evaluation_cohort=location_holdout; metric in pr_auc,brier,f2; "
            "estimand panels observation_weighted and site_weighted; "
            "plotted value is the arithmetic mean over published seed-slot rows; "
            "each exact model/horizon/estimand/metric cell exposes attempted, "
            "successful, metric-evaluable and both rates; bar height is the "
            "metric-evaluable/attempted rate and is never a binary availability proxy"
        ),
    )
    canvas = _SvgCanvas(
        "F02",
        contract.artifact_captions["F02"],
        description,
        "F02 - PR-AUC, Brier, and F2 by estimand",
        width=1660,
        height=1170,
    )
    canvas.text(
        40,
        72,
        "Each point shows the published slot mean; h1/h2/h3 bars encode the evaluable/attempted rate, and unavailable values remain N/A.",
        class_="subtitle",
    )
    panel_width = 760
    panel_height = 300
    plot_left_offset = 66
    plot_width = 640
    for panel_index, (estimand, display_estimand) in enumerate(estimands):
        panel_x = 45 + panel_index * 805
        canvas.text(
            panel_x,
            112,
            display_estimand,
            class_="label",
            font_weight="700",
        )
        for metric_index, metric in enumerate(metrics):
            panel_y = 136 + metric_index * 322
            canvas.element(
                "rect",
                x=panel_x,
                y=panel_y,
                width=panel_width,
                height=panel_height,
                class_="panel",
            )
            canvas.text(panel_x + 12, panel_y + 22, metric, class_="label", font_weight="700")
            plot_left = panel_x + plot_left_offset
            plot_top = panel_y + 38
            plot_bottom = panel_y + 224
            for tick in (Decimal(0), Decimal("0.5"), Decimal(1)):
                tick_y = _scale(Decimal(1) - tick, Decimal(0), Decimal(1), plot_top, plot_bottom - plot_top)
                canvas.element(
                    "line",
                    x1=plot_left,
                    y1=tick_y,
                    x2=plot_left + plot_width,
                    y2=tick_y,
                    class_="grid" if tick != 0 else "axis",
                )
                canvas.text(plot_left - 8, tick_y + 4, _render_number(tick, 1), class_="small", text_anchor="end")
            for horizon in (1, 2, 3):
                points: list[str] = []
                for model_index, model_id in enumerate(models):
                    x = plot_left + model_index * plot_width // max(1, len(models) - 1)
                    cell = cells[(estimand, metric, model_id, horizon)]
                    group = cell.values
                    if not group:
                        continue
                    mean_value = _mean(group, context=f"F02 {estimand}/{metric}/{model_id}/h{horizon}")
                    y = _scale(Decimal(1) - mean_value, Decimal(0), Decimal(1), plot_top, plot_bottom - plot_top)
                    points.append(f"{x},{y}")
                    canvas.element(
                        "circle",
                        cx=x,
                        cy=y,
                        r=4,
                        fill=horizon_colors[horizon],
                        class_="metric-value",
                        data_series=f"h{horizon}",
                        data_estimand=estimand,
                        data_metric=metric,
                        data_model=model_id,
                        data_value=_render_number(mean_value),
                        data_seed_row_count=len(group),
                        title=(
                            f"{model_id}, h{horizon}, {metric}, {estimand}: "
                            f"{_render_number(mean_value)} (n={len(group)} rows)"
                        ),
                    )
                    canvas.text(
                        x,
                        y - 7 - 8 * (horizon - 1),
                        _render_number(mean_value, 3),
                        class_="value",
                        text_anchor="middle",
                    )
                if points:
                    canvas.element(
                        "polyline",
                        points=" ".join(points),
                        fill="none",
                        stroke=horizon_colors[horizon],
                        stroke_width=1,
                        stroke_opacity="0.35",
                        class_="metric-series",
                        data_series=f"h{horizon}",
                        data_estimand=estimand,
                        data_metric=metric,
                    )
            for model_index, model_id in enumerate(models):
                x = plot_left + model_index * plot_width // max(1, len(models) - 1)
                has_value = any(
                    cells[(estimand, metric, model_id, horizon)].values
                    for horizon in (1, 2, 3)
                )
                state = availability[model_id] if not has_value else "estimated"
                if not has_value:
                    canvas.text(x, plot_bottom - 5, "N/A", class_="value", text_anchor="middle", data_state=state)
                for horizon in (1, 2, 3):
                    cell = cells[(estimand, metric, model_id, horizon)]
                    bar_height = int(
                        (cell.evaluable_rate * Decimal(34)).quantize(
                            Decimal("1"), rounding=ROUND_HALF_EVEN
                        )
                    )
                    bar_x = x + (horizon - 2) * 10 - 3
                    canvas.element(
                        "rect",
                        x=bar_x,
                        y=plot_bottom + 17,
                        width=7,
                        height=34,
                        fill="#f3f4f6",
                        class_="availability-track",
                    )
                    canvas.element(
                        "rect",
                        x=bar_x,
                        y=plot_bottom + 51 - bar_height,
                        width=7,
                        height=bar_height,
                        fill=horizon_colors[horizon],
                        class_="availability-bar",
                        data_model=model_id,
                        data_horizon=horizon,
                        data_estimand=estimand,
                        data_metric=metric,
                        data_state=availability[model_id],
                        data_terminal_status=cell.terminal_status,
                        data_attempted=cell.attempted,
                        data_successful=cell.successful,
                        data_evaluable=cell.evaluable,
                        data_success_rate=_render_number(cell.success_rate, 6),
                        data_evaluable_rate=_render_number(cell.evaluable_rate, 6),
                        data_value=_render_number(cell.evaluable_rate, 6),
                        title=(
                            f"{model_id}, h{horizon}, {metric}, {estimand}: "
                            f"attempted={cell.attempted}, successful={cell.successful}, "
                            f"evaluable={cell.evaluable}, "
                            f"success_rate={_render_number(cell.success_rate, 6)}, "
                            f"evaluable_rate={_render_number(cell.evaluable_rate, 6)}"
                        ),
                    )
                canvas.text(
                    x,
                    plot_bottom + 70,
                    model_id,
                    class_="small",
                    text_anchor="middle",
                )
    legend_x = 550
    for horizon in (1, 2, 3):
        canvas.element(
            "circle",
            cx=legend_x,
            cy=1135,
            r=5,
            fill=horizon_colors[horizon],
        )
        canvas.text(legend_x + 10, 1139, f"h{horizon}", class_="small")
        legend_x += 80
    canvas.text(820, 1139, "bar height=evaluable/attempted rate; zero remains zero; N/A=not estimable", class_="small")
    return canvas.finish()


def _figure_f03_descriptive_deltas(
    contract: SynthesisContract, *, root: Path
) -> bytes:
    comparisons = _read_allowed_csv(contract, root, MODEL_COMPARISON)
    ablation = _read_allowed_csv(contract, root, ABLATION_PAIRWISE)
    f_points: dict[int, list[tuple[str, Decimal, int]]] = {1: [], 2: [], 3: []}
    for row in comparisons:
        if (
            row.get("comparison_id") != "F1_vs_F0"
            or row.get("metric") != "absolute_error"
            or row.get("terminal_status") != "estimated"
        ):
            continue
        horizon = _integer(row, "horizon_months", source=MODEL_COMPARISON)
        f_points[horizon].append(
            (
                row["seed_slot"],
                _numeric(
                    row,
                    "mean_loss_difference_a_minus_b",
                    source=MODEL_COMPARISON,
                ),
                _integer(row, "paired_origin_count", source=MODEL_COMPARISON),
            )
        )
    a_points: dict[tuple[str, int], tuple[Decimal, int]] = {}
    for row in ablation:
        if (
            row.get("challenger_model_id") != "A1"
            or row.get("reference_model_id") != "A0"
            or row.get("status") != "available"
        ):
            continue
        horizon = _integer(row, "horizon_months", source=ABLATION_PAIRWISE)
        denominator = _integer(row, "common_row_count", source=ABLATION_PAIRWISE)
        for metric in ("delta_pr_auc", "delta_brier", "delta_mae"):
            a_points[(metric, horizon)] = (
                _numeric(row, metric, source=ABLATION_PAIRWISE),
                denominator,
            )
    if any(not f_points[horizon] for horizon in (1, 2, 3)) or len(a_points) != 9:
        raise _error("F03 exact F1-F0 or A1-A0 descriptive points are incomplete")

    description = _figure_description(
        (MODEL_COMPARISON, ABLATION_PAIRWISE),
        filters=(
            "model_comparison: comparison_id=F1_vs_F0, metric=absolute_error, "
            "terminal_status=estimated; ablation_pairwise: challenger=A1, "
            "reference=A0, status=available; every published seed point and "
            "common-row denominator is retained; no confidence interval is inferred"
        ),
    )
    canvas = _SvgCanvas(
        "F03",
        contract.artifact_captions["F03"],
        description,
        "F03 - Paired descriptive deltas",
        width=1540,
        height=760,
    )
    canvas.text(
        40,
        72,
        "Points are published values; the vertical line is zero; no intervals are drawn.",
        class_="subtitle",
    )

    panels = ((50, 720, "F1-F0 - delta MAE", "fuzzy"), (790, 700, "A1-A0 - three metrics", "anfis"))
    for x, width, label, series in panels:
        canvas.element("rect", x=x, y=105, width=width, height=610, class_="panel")
        canvas.text(x + 18, 135, label, class_="label", font_weight="700")
        canvas.open_group(class_="delta-panel", data_series=series)
        canvas.close_group()

    f_values = [value for points in f_points.values() for _seed, value, _n in points]
    f_limit = max(abs(value) for value in f_values) * Decimal("1.2")
    f_left = 205
    f_width = 515
    f_zero = _scale(Decimal(0), -f_limit, f_limit, f_left, f_width)
    canvas.element("line", x1=f_zero, y1=165, x2=f_zero, y2=650, class_="axis")
    for horizon in (1, 2, 3):
        y = 240 + (horizon - 1) * 150
        canvas.text(75, y + 4, f"h{horizon}", class_="label")
        canvas.element("line", x1=f_left, y1=y, x2=f_left + f_width, y2=y, class_="grid")
        ordered = sorted(f_points[horizon], key=lambda item: int(item[0]))
        for index, (seed, value, denominator) in enumerate(ordered):
            point_x = _scale(value, -f_limit, f_limit, f_left, f_width)
            point_y = y - 12 + index * 6
            canvas.element(
                "circle",
                cx=point_x,
                cy=point_y,
                r=5,
                fill="#7c3aed",
                class_="delta-value",
                data_series="F1-F0",
                data_horizon=horizon,
                data_metric="delta_mae",
                data_seed=seed,
                data_value=_render_number(value),
                data_denominator=denominator,
                title=f"F1-F0 h{horizon}, seed {seed}: {_render_number(value)}; n={denominator}",
            )
        mean_value = _mean(
            [value for _seed, value, _n in ordered],
            context=f"F03 F1-F0 h{horizon}",
        )
        canvas.text(
            f_left + f_width,
            y + 42,
            f"mean={_render_number(mean_value)}; seeds={len(ordered)}; n={_range_label([n for _s, _v, n in ordered])}",
            class_="value",
            text_anchor="end",
        )
    canvas.text(f_left, 680, _render_number(-f_limit), class_="small", text_anchor="middle")
    canvas.text(f_zero, 680, "0", class_="small", text_anchor="middle")
    canvas.text(f_left + f_width, 680, _render_number(f_limit), class_="small", text_anchor="middle")

    a_values = [value for value, _n in a_points.values()]
    a_limit = max(abs(value) for value in a_values) * Decimal("1.25")
    a_left = 980
    a_width = 460
    a_zero = _scale(Decimal(0), -a_limit, a_limit, a_left, a_width)
    canvas.element("line", x1=a_zero, y1=165, x2=a_zero, y2=650, class_="axis")
    metric_labels = (
        ("delta_pr_auc", "delta PR-AUC"),
        ("delta_brier", "delta Brier"),
        ("delta_mae", "delta MAE"),
    )
    metric_colors = {
        "delta_pr_auc": "#1d4ed8",
        "delta_brier": "#c2410c",
        "delta_mae": "#0f766e",
    }
    row_index = 0
    for metric, label in metric_labels:
        for horizon in (1, 2, 3):
            y = 190 + row_index * 50
            value, denominator = a_points[(metric, horizon)]
            point_x = _scale(value, -a_limit, a_limit, a_left, a_width)
            canvas.text(815, y + 4, f"{label} - h{horizon}", class_="small")
            canvas.element("line", x1=a_left, y1=y, x2=a_left + a_width, y2=y, class_="grid")
            canvas.element(
                "circle",
                cx=point_x,
                cy=y,
                r=6,
                fill=metric_colors[metric],
                class_="delta-value",
                data_series="A1-A0",
                data_horizon=horizon,
                data_metric=metric,
                data_value=_render_number(value),
                data_denominator=denominator,
                title=f"A1-A0 {label} h{horizon}: {_render_number(value)}; n={denominator}",
            )
            canvas.text(
                point_x + (10 if value >= 0 else -10),
                y - 8,
                _render_number(value),
                class_="value",
                text_anchor="start" if value >= 0 else "end",
            )
            row_index += 1
    canvas.text(a_left, 680, _render_number(-a_limit), class_="small", text_anchor="middle")
    canvas.text(a_zero, 680, "0", class_="small", text_anchor="middle")
    canvas.text(a_left + a_width, 680, _render_number(a_limit), class_="small", text_anchor="middle")
    return canvas.finish()


def _figure_f04_threshold_sensitivity(
    contract: SynthesisContract, *, root: Path
) -> bytes:
    prevalence = _read_allowed_csv(contract, root, THRESHOLD_PREVALENCE)
    ranks = _read_allowed_csv(contract, root, RANK_STABILITY)
    cutoffs = (25, 30, 33, 50)
    prevalence_points: dict[tuple[int, int], tuple[Decimal, int, int]] = {}
    for row in prevalence:
        horizon = _integer(row, "horizon_months", source=THRESHOLD_PREVALENCE)
        cutoff = _integer(row, "threshold_ug_l", source=THRESHOLD_PREVALENCE)
        if cutoff not in cutoffs:
            continue
        prevalence_points[(horizon, cutoff)] = (
            _numeric(row, "positive_rate", source=THRESHOLD_PREVALENCE),
            _integer(row, "origin_count", source=THRESHOLD_PREVALENCE),
            _integer(row, "positive_count", source=THRESHOLD_PREVALENCE),
        )
    rank_points: dict[tuple[str, int, int], tuple[Decimal, int]] = {}
    for row in ranks:
        if row.get("estimable") != "True":
            continue
        horizon = _integer(row, "horizon_months", source=RANK_STABILITY)
        cutoff = _integer(row, "compared_threshold_ug_l", source=RANK_STABILITY)
        metric = row["metric"]
        if metric in {"pr_auc", "brier", "f2"} and cutoff in cutoffs:
            rank_points[(metric, horizon, cutoff)] = (
                _numeric(row, "kendall_tau", source=RANK_STABILITY),
                _integer(row, "compared_model_count", source=RANK_STABILITY),
            )
    if len(prevalence_points) != 12 or len(rank_points) != 36:
        raise _error("F04 cutoff prevalence/rank grid is not exact12/exact36")

    description = _figure_description(
        (THRESHOLD_PREVALENCE, RANK_STABILITY),
        filters=(
            "threshold_prevalence: evaluation_cohort=location_holdout and "
            "cutoff in 25,30,33,50; rank_stability: estimable=True, reference "
            "cutoff=30, metric in pr_auc,brier,f2; series are kept separate by horizon"
        ),
    )
    canvas = _SvgCanvas(
        "F04",
        contract.artifact_captions["F04"],
        description,
        "F04 - Prevalence and ranking stability by cutoff",
        width=1580,
        height=930,
    )
    canvas.text(40, 72, "Cutoff 50 is retained and marked as a sparse endpoint; Kendall tau uses 30 as the reference.", class_="subtitle")
    colors = {1: "#1d4ed8", 2: "#7c3aed", 3: "#c2410c"}
    left_x = 80
    left_y = 150
    left_width = 610
    left_height = 620
    canvas.element("rect", x=45, y=105, width=700, height=730, class_="panel")
    canvas.text(65, 135, "Positive prevalence", class_="label", font_weight="700")
    for tick_index in range(6):
        tick = Decimal(tick_index) / Decimal(10)
        y = _scale(Decimal("0.5") - tick, Decimal(0), Decimal("0.5"), left_y, left_height)
        canvas.element("line", x1=left_x, y1=y, x2=left_x + left_width, y2=y, class_="grid")
        canvas.text(left_x - 8, y + 4, _render_number(tick, 1), class_="small", text_anchor="end")
    for horizon in (1, 2, 3):
        points: list[str] = []
        for cutoff_index, cutoff in enumerate(cutoffs):
            value, denominator, positives = prevalence_points[(horizon, cutoff)]
            x = left_x + cutoff_index * left_width // 3
            y = _scale(Decimal("0.5") - value, Decimal(0), Decimal("0.5"), left_y, left_height)
            points.append(f"{x},{y}")
            canvas.element(
                "circle",
                cx=x,
                cy=y,
                r=6 if cutoff != 50 else 8,
                fill=colors[horizon],
                stroke="#111827" if cutoff == 50 else colors[horizon],
                stroke_width=2 if cutoff == 50 else 1,
                class_="threshold-value",
                data_series=f"prevalence_h{horizon}",
                data_horizon=horizon,
                data_cutoff=cutoff,
                data_value=_render_number(value),
                data_denominator=denominator,
                data_positive_count=positives,
                title=f"h{horizon}, cutoff {cutoff}: {_render_number(value)} ({positives}/{denominator})",
            )
            canvas.text(x, y - 10, _render_number(value, 3), class_="value", text_anchor="middle")
        canvas.element(
            "polyline",
            points=" ".join(points),
            fill="none",
            stroke=colors[horizon],
            stroke_width=2,
            class_="threshold-series",
            data_series=f"prevalence_h{horizon}",
        )
    for cutoff_index, cutoff in enumerate(cutoffs):
        x = left_x + cutoff_index * left_width // 3
        canvas.text(x, left_y + left_height + 28, str(cutoff), class_="label", text_anchor="middle")
    canvas.text(left_x + left_width // 2, left_y + left_height + 52, "cutoff (micrograms/L)", class_="small", text_anchor="middle")

    right_x = 865
    right_width = 610
    metric_colors = {"pr_auc": "#0f766e", "brier": "#7c3aed", "f2": "#c2410c"}
    canvas.element("rect", x=790, y=105, width=745, height=730, class_="panel")
    canvas.text(810, 135, "Ranking Kendall tau", class_="label", font_weight="700")
    for metric_index, metric in enumerate(("pr_auc", "brier", "f2")):
        top = 165 + metric_index * 210
        bottom = top + 150
        canvas.text(812, top + 12, metric, class_="small", font_weight="700")
        zero_y = _scale(Decimal(1), Decimal(0), Decimal(2), top, bottom - top)
        canvas.element("line", x1=right_x, y1=zero_y, x2=right_x + right_width, y2=zero_y, class_="axis")
        for horizon in (1, 2, 3):
            points = []
            for cutoff_index, cutoff in enumerate(cutoffs):
                value, model_count = rank_points[(metric, horizon, cutoff)]
                x = right_x + cutoff_index * right_width // 3
                y = _scale(Decimal(1) - value, Decimal(0), Decimal(2), top, bottom - top)
                points.append(f"{x},{y}")
                canvas.element(
                    "circle",
                    cx=x,
                    cy=y,
                    r=4 + horizon,
                    fill=metric_colors[metric],
                    fill_opacity=str(Decimal("0.45") + Decimal(horizon) / Decimal(8)),
                    class_="rank-value",
                    data_series=f"{metric}_h{horizon}",
                    data_metric=metric,
                    data_horizon=horizon,
                    data_cutoff=cutoff,
                    data_value=_render_number(value),
                    data_model_count=model_count,
                    title=f"{metric}, h{horizon}, cutoff {cutoff}: τ={_render_number(value)}; models={model_count}",
                )
                canvas.text(x, y - 8, _render_number(value, 2), class_="value", text_anchor="middle")
            canvas.element(
                "polyline",
                points=" ".join(points),
                fill="none",
                stroke=colors[horizon],
                stroke_width=1,
                class_="rank-series",
                data_series=f"{metric}_h{horizon}",
            )
        canvas.text(right_x - 8, top + 4, "1", class_="small", text_anchor="end")
        canvas.text(right_x - 8, zero_y + 4, "0", class_="small", text_anchor="end")
        canvas.text(right_x - 8, bottom + 4, "-1", class_="small", text_anchor="end")
        if metric_index == 2:
            for cutoff_index, cutoff in enumerate(cutoffs):
                x = right_x + cutoff_index * right_width // 3
                canvas.text(x, bottom + 30, str(cutoff), class_="label", text_anchor="middle")
    legend_x = 540
    for horizon in (1, 2, 3):
        canvas.element("circle", cx=legend_x, cy=885, r=5, fill=colors[horizon])
        canvas.text(legend_x + 10, 889, f"h{horizon}", class_="small")
        legend_x += 75
    return canvas.finish()


def _figure_f05_trophic_heatmap(
    contract: SynthesisContract, *, root: Path
) -> bytes:
    proxy_rows = _read_allowed_csv(contract, root, TROPHIC_PROXY)
    carlson_rows = _read_allowed_csv(contract, root, CARLSON_METRICS)
    references = (
        ("future_chla_operational_proxy", "Chl-a proxy"),
        ("tsi_tp_h", "Carlson TP"),
        ("tsi_sd_h", "Carlson Secchi"),
        ("tsi_non_chla_h", "Carlson non-Chl-a"),
        ("tsi_all_h", "Carlson combined"),
    )
    metrics = (
        ("macro_f1", "macro-F1"),
        ("quadratic_weighted_kappa", "quadratic kappa"),
        ("ordinal_mae", "ordinal MAE"),
        ("severe_error_rate", "severe error"),
    )
    grouped: dict[tuple[str, str, int, str], list[Decimal]] = {}
    denominators: dict[tuple[str, str, int], list[int]] = {}
    for row in (*proxy_rows, *carlson_rows):
        reference = row.get("reference", "")
        model_id = row.get("model_id", "")
        if (
            reference not in {item[0] for item in references}
            or model_id not in {"B1", "B2"}
            or row.get("evaluation_cohort") != "location_holdout"
            or row.get("status") != "available"
        ):
            continue
        horizon = _integer(row, "horizon_months", source="E4 trophic CSV")
        denominator_key = (reference, model_id, horizon)
        denominators.setdefault(denominator_key, []).append(
            _integer(row, "evaluation_row_count", source="E4 trophic CSV")
        )
        for metric, _label in metrics:
            grouped.setdefault((reference, model_id, horizon, metric), []).append(
                _numeric(row, metric, source="E4 trophic CSV")
            )
    expected_groups = len(references) * 2 * 3 * len(metrics)
    if len(grouped) != expected_groups:
        raise _error("F05 B1/B2 proxy/Carlson heatmap grid is incomplete")

    metric_ranges: dict[str, tuple[Decimal, Decimal]] = {}
    for metric, _label in metrics:
        metric_values = [
            _mean(values, context=f"F05 {key}")
            for key, values in grouped.items()
            if key[3] == metric
        ]
        metric_ranges[metric] = (min(metric_values), max(metric_values))

    description = _figure_description(
        (TROPHIC_PROXY, CARLSON_METRICS),
        filters=(
            "evaluation_cohort=location_holdout; status=available; model_id "
            "in B1,B2; references=future_chla_operational_proxy plus Carlson "
            "tsi_tp_h,tsi_sd_h,tsi_non_chla_h,tsi_all_h; cells are means over "
            "five published seed slots and intensity is scaled within each metric"
        ),
    )
    row_count = len(references) * 2 * 3
    canvas = _SvgCanvas(
        "F05",
        contract.artifact_captions["F05"],
        description,
        "F05 - B1/B2 ordinal heatmap: Chl-a proxy and Carlson",
        width=1500,
        height=190 + row_count * 38,
    )
    canvas.text(40, 72, "Values are five-slot means; color is relative within each metric column, not an inferential signal.", class_="subtitle")
    label_x = 55
    cell_x = 660
    cell_width = 190
    top = 145
    for metric_index, (_metric, label) in enumerate(metrics):
        x = cell_x + metric_index * cell_width
        canvas.text(x + cell_width // 2, 120, label, class_="label", text_anchor="middle", font_weight="700")
        canvas.element("line", x1=x, y1=128, x2=x, y2=top + row_count * 38, class_="axis")
    row_index = 0
    for reference, reference_label in references:
        for model_id in ("B1", "B2"):
            for horizon in (1, 2, 3):
                y = top + row_index * 38
                denominator_values = denominators[(reference, model_id, horizon)]
                denominator = _range_label(denominator_values)
                canvas.open_group(
                    class_="heatmap-series",
                    data_series=model_id,
                    data_reference=reference,
                    data_horizon=horizon,
                    data_denominator=denominator,
                    data_seed_count=len(denominator_values),
                )
                if horizon == 1:
                    canvas.element(
                        "rect",
                        x=45,
                        y=y - 17,
                        width=1390,
                        height=114,
                        fill="#f9fafb" if model_id == "B1" else "#f3f4f6",
                    )
                canvas.text(label_x, y + 8, f"{reference_label} - {model_id} - h{horizon}", class_="label")
                canvas.text(510, y + 8, f"n={denominator}", class_="value")
                for metric_index, (metric, _label) in enumerate(metrics):
                    values = grouped[(reference, model_id, horizon, metric)]
                    value = _mean(values, context=f"F05 {reference}/{model_id}/h{horizon}/{metric}")
                    lower, upper = metric_ranges[metric]
                    x = cell_x + metric_index * cell_width
                    canvas.element(
                        "rect",
                        x=x + 4,
                        y=y - 16,
                        width=cell_width - 8,
                        height=32,
                        fill=_heat_color(value, lower, upper),
                        stroke="#ffffff",
                        stroke_width=1,
                        class_="heatmap-value",
                        data_series=model_id,
                        data_reference=reference,
                        data_horizon=horizon,
                        data_metric=metric,
                        data_value=_render_number(value),
                        data_seed_count=len(values),
                    )
                    canvas.text(
                        x + cell_width // 2,
                        y + 5,
                        _render_number(value),
                        class_="value",
                        text_anchor="middle",
                    )
                canvas.close_group()
                row_index += 1
    footer_y = top + row_count * 38 + 25
    canvas.text(55, footer_y, "NLA is retained only as a semantic/provenance sentinel; it does not validate monthly WQP targets.", class_="small")
    return canvas.finish()


def _figure_f06_uncertainty(
    contract: SynthesisContract, *, root: Path
) -> bytes:
    rows = _read_allowed_csv(contract, root, UNCERTAINTY_LEDGER)
    availability_rows = _read_allowed_csv(contract, root, MODEL_AVAILABILITY)
    availability = {
        row["model_id"]: row["availability"] for row in availability_rows
    }
    if availability.get("P1") != "unavailable":
        raise _error("F06 requires the published P1 unavailable state")
    fields = (
        ("empirical_coverage", "coverage", Decimal("0.75"), Decimal("1.00")),
        ("mean_interval_width", "mean width", Decimal(0), None),
        ("winkler_interval_score", "Winkler", Decimal(0), None),
    )
    grouped: dict[tuple[str, str, int, str], list[Decimal]] = {}
    denominators: dict[tuple[str, str, int], list[int]] = {}
    for row in rows:
        nominal = _numeric(row, "nominal_coverage", source=UNCERTAINTY_LEDGER)
        model_id = row.get("model_id", "")
        version = row.get("interval_version", "")
        if (
            model_id not in {"A0", "A1"}
            or version not in {"raw_gaussian", "locked_conformal"}
            or row.get("status") != "available"
            or abs(nominal - Decimal("0.9")) > Decimal("1e-12")
        ):
            continue
        horizon = _integer(row, "horizon_months", source=UNCERTAINTY_LEDGER)
        denominators.setdefault((model_id, version, horizon), []).append(
            _integer(row, "interval_row_count", source=UNCERTAINTY_LEDGER)
        )
        for field, _label, _lower, _upper in fields:
            grouped.setdefault((model_id, version, horizon, field), []).append(
                _numeric(row, field, source=UNCERTAINTY_LEDGER)
            )
    if len(grouped) != 2 * 2 * 3 * 3:
        raise _error("F06 raw/locked A0/A1 nominal-0.90 grid is incomplete")

    dynamic_upper: dict[str, Decimal] = {}
    for field, _label, lower, upper in fields:
        if upper is not None:
            dynamic_upper[field] = upper
            continue
        maximum = max(
            _mean(values, context=f"F06 {key}")
            for key, values in grouped.items()
            if key[3] == field
        )
        dynamic_upper[field] = max(maximum * Decimal("1.12"), lower + Decimal(1))

    description = _figure_description(
        (UNCERTAINTY_LEDGER, MODEL_AVAILABILITY),
        filters=(
            "uncertainty_ledger: model_id in A0,A1, nominal_coverage=0.90, "
            "interval_version in raw_gaussian,locked_conformal, status=available; "
            "points are means over five seed slots; h3 receives an outer marker; "
            "P1 confirmatory state comes from model_availability"
        ),
    )
    canvas = _SvgCanvas(
        "F06",
        contract.artifact_captions["F06"],
        description,
        "F06 - Raw versus locked coverage, width, and Winkler score",
        width=1580,
        height=1080,
    )
    canvas.text(40, 72, "Nominal=0.90; h3 is marked with a ring; confirmatory P1 remains N/A.", class_="subtitle")
    canvas.element("rect", x=1190, y=48, width=325, height=34, class_="na", data_state="model_unavailable", data_model="P1")
    canvas.text(1352, 70, "Confirmatory P1: N/A (model_unavailable)", class_="small", text_anchor="middle")
    version_colors = {"raw_gaussian": "#c2410c", "locked_conformal": "#1d4ed8"}
    for model_index, model_id in enumerate(("A0", "A1")):
        panel_x = 50 + model_index * 770
        canvas.text(panel_x, 118, model_id, class_="label", font_weight="700")
        for field_index, (field, label, lower, fixed_upper) in enumerate(fields):
            panel_y = 140 + field_index * 295
            panel_width = 710
            panel_height = 255
            canvas.element("rect", x=panel_x, y=panel_y, width=panel_width, height=panel_height, class_="panel")
            canvas.text(panel_x + 12, panel_y + 23, label, class_="label", font_weight="700")
            plot_left = panel_x + 75
            plot_top = panel_y + 42
            plot_bottom = panel_y + 196
            plot_width = 570
            upper = fixed_upper or dynamic_upper[field]
            for tick in (lower, (lower + upper) / Decimal(2), upper):
                y = _scale(upper - tick, Decimal(0), upper - lower, plot_top, plot_bottom - plot_top)
                canvas.element("line", x1=plot_left, y1=y, x2=plot_left + plot_width, y2=y, class_="grid")
                canvas.text(plot_left - 8, y + 4, _render_number(tick, 2), class_="small", text_anchor="end")
            canvas.element(
                "line",
                x1=plot_left,
                y1=plot_bottom,
                x2=plot_left + plot_width,
                y2=plot_bottom,
                class_="axis",
            )
            if field == "empirical_coverage":
                nominal_y = _scale(upper - Decimal("0.9"), Decimal(0), upper - lower, plot_top, plot_bottom - plot_top)
                canvas.element(
                    "line",
                    x1=plot_left,
                    y1=nominal_y,
                    x2=plot_left + plot_width,
                    y2=nominal_y,
                    stroke="#111827",
                    stroke_width=2,
                    stroke_dasharray="5 4",
                    class_="nominal-line",
                    data_value="0.9000",
                )
            for version_index, version in enumerate(("raw_gaussian", "locked_conformal")):
                points: list[str] = []
                for horizon in (1, 2, 3):
                    x_index = version_index * 3 + horizon - 1
                    x = plot_left + x_index * plot_width // 5
                    values = grouped[(model_id, version, horizon, field)]
                    value = _mean(values, context=f"F06 {model_id}/{version}/h{horizon}/{field}")
                    y = _scale(upper - value, Decimal(0), upper - lower, plot_top, plot_bottom - plot_top)
                    points.append(f"{x},{y}")
                    denominator_values = denominators[(model_id, version, horizon)]
                    canvas.element(
                        "circle",
                        cx=x,
                        cy=y,
                        r=6,
                        fill=version_colors[version],
                        class_="uncertainty-value",
                        data_series=version,
                        data_model=model_id,
                        data_horizon=horizon,
                        data_metric=field,
                        data_value=_render_number(value),
                        data_denominator=_range_label(denominator_values),
                        data_seed_count=len(values),
                        title=f"{model_id}, {version}, h{horizon}, {label}: {_render_number(value)}; n={_range_label(denominator_values)}",
                    )
                    if horizon == 3:
                        canvas.element(
                            "circle",
                            cx=x,
                            cy=y,
                            r=10,
                            fill="none",
                            stroke="#111827",
                            stroke_width=2,
                            class_="h3-marker",
                            data_series=version,
                            data_model=model_id,
                        )
                    canvas.text(x, y - 11, _render_number(value, 3), class_="value", text_anchor="middle")
                    canvas.text(x, plot_bottom + 21, f"{'raw' if version_index == 0 else 'locked'} h{horizon}", class_="small", text_anchor="middle")
                canvas.element(
                    "polyline",
                    points=" ".join(points),
                    fill="none",
                    stroke=version_colors[version],
                    stroke_width=2,
                    class_="uncertainty-series",
                    data_series=version,
                    data_model=model_id,
                    data_metric=field,
                )
    canvas.text(610, 1040, "raw_gaussian", class_="small", fill=version_colors["raw_gaussian"])
    canvas.text(760, 1040, "locked_conformal", class_="small", fill=version_colors["locked_conformal"])
    canvas.text(940, 1040, "ring = h3", class_="small")
    return canvas.finish()


def _holm_counts(
    matrix_rows: Sequence[Mapping[str, str]],
) -> dict[str, int]:
    cells: dict[str, set[tuple[str, str, str, str]]] = {
        family: set() for family in ("A", "B", "C", "D", "E")
    }
    for row in matrix_rows:
        family = row["multiplicity_family"]
        if family:
            cells[family].add(
                (
                    row["model_or_pair"],
                    row["metric"],
                    row["population"],
                    row["estimand"],
                )
            )
    return {family: len(values) for family, values in cells.items()}


def _figure_f07_hypothesis_verdicts(
    contract: SynthesisContract,
    matrix_rows: Sequence[Mapping[str, str]],
) -> bytes:
    state_labels = {
        "limited_descriptive_support": "limited descriptive support",
        "partial_descriptive_only": "partial descriptive only",
        "not_estimable_primary_architecture": "not estimable",
        "not_estimable": "not estimable",
        "not_confirmed_scientifically": "not scientifically confirmed",
    }
    state_colors = {
        "limited descriptive support": "#dbeafe",
        "partial descriptive only": "#ede9fe",
        "not estimable": "#e5e7eb",
        "not scientifically confirmed": "#fef3c7",
    }
    grouped: dict[str, list[Mapping[str, str]]] = {
        hypothesis: [] for hypothesis in contract.required_hypotheses
    }
    for row in matrix_rows:
        hypothesis = row["hypothesis_id"].split(":", 1)[0]
        if hypothesis in grouped:
            grouped[hypothesis].append(row)
    if any(not rows for rows in grouped.values()):
        raise _error("F07 hypothesis matrix is incomplete")
    holm = _holm_counts(matrix_rows)

    description = _figure_description(
        (
            HYPOTHESIS_REGISTRY,
            MULTIPLICITY_REPORT,
            FAILURE_REGISTRY,
            ABLATION_PAIRWISE,
            UNCERTAINTY_LEDGER,
            PLANNING_BOOTSTRAP,
        ),
        filters=(
            "FINAL_CLOSURE_MATRIX rows grouped by hypothesis_id prefix; each "
            "hypothesis must have one consistent verdict; state vocabulary is "
            "non-binary and Holm cells use exact model/metric/population/estimand keys; "
            "H1 partitions 15 direct-ANFIS rows from 13 auxiliary B1/B2 context rows"
        ),
    )
    canvas = _SvgCanvas(
        "F07",
        contract.artifact_captions["F07"],
        description,
        "F07 - H1-H5b verdict matrix",
        width=1480,
        height=680,
    )
    canvas.text(
        40,
        72,
        "Explicit interpretive states; unavailability is not converted into a binary result.",
        class_="subtitle",
    )
    order = tuple(contract.required_hypotheses)
    for index, hypothesis in enumerate(order):
        rows = grouped[hypothesis]
        verdicts = {row["verdict"] for row in rows}
        if len(verdicts) != 1:
            raise _error(f"F07 {hypothesis} has inconsistent verdicts")
        verdict = verdicts.pop()
        state = state_labels.get(verdict)
        if state is None:
            raise _error(f"F07 unknown verdict vocabulary: {verdict}")
        estimated = sum(
            row["availability_state"]
            in {"descriptive_available", "confirmatory_available"}
            for row in rows
        )
        direct_rows: list[Mapping[str, str]] = []
        auxiliary_rows: list[Mapping[str, str]] = []
        direct_available = 0
        direct_unavailable = 0
        if hypothesis == "H1":
            auxiliary_rows = [
                row
                for row in rows
                if row["hypothesis_id"].startswith("H1:B2_vs_B1:")
            ]
            direct_rows = [row for row in rows if row not in auxiliary_rows]
            direct_available = sum(
                row["availability_state"] == "descriptive_available"
                for row in direct_rows
            )
            direct_unavailable = len(direct_rows) - direct_available
            if (
                len(rows) != 28
                or len(direct_rows) != 15
                or direct_available != 9
                or direct_unavailable != 6
                or len(auxiliary_rows) != 13
                or any(
                    row["availability_state"] != "descriptive_available"
                    for row in auxiliary_rows
                )
                or any(
                    "DOES_NOT_VALIDATE_THE_PRIMARY_ANFIS_BRANCH"
                    not in row["limitation_code"]
                    for row in auxiliary_rows
                )
            ):
                raise _error(
                    "F07 H1 direct-ANFIS versus auxiliary B1/B2 evidence "
                    "partition drifted"
                )
        column = index % 3
        row_index = index // 3
        x = 45 + column * 480
        y = 115 + row_index * 250
        group_attributes: dict[str, str | int] = {
            "class_": "hypothesis-state",
            "data_hypothesis": hypothesis,
            "data_verdict": verdict,
            "data_state": state.replace(" ", "_"),
            "data_row_count": len(rows),
            "data_estimable_row_count": (
                direct_available if hypothesis == "H1" else estimated
            ),
        }
        if hypothesis == "H1":
            group_attributes.update(
                {
                    "data_direct_anfis_row_count": len(direct_rows),
                    "data_direct_anfis_available_count": direct_available,
                    "data_direct_anfis_unavailable_count": direct_unavailable,
                    "data_auxiliary_b1_b2_row_count": len(auxiliary_rows),
                    "data_total_descriptive_row_count": estimated,
                }
            )
        canvas.open_group(**group_attributes)
        canvas.element(
            "rect",
            x=x,
            y=y,
            width=445,
            height=210,
            rx=12,
            fill=state_colors[state],
            stroke="#4b5563",
            stroke_width=1,
        )
        canvas.text(x + 22, y + 38, hypothesis, class_="heading")
        canvas.text(x + 22, y + 74, state, class_="label", font_weight="700")
        hypothesis_text = rows[0]["hypothesis_text"]
        canvas.text(x + 22, y + 105, hypothesis_text, class_="small")
        if hypothesis == "H1":
            canvas.text(
                x + 22,
                y + 133,
                f"Direct ANFIS: {direct_available}/{len(direct_rows)}; "
                f"unavailable: {direct_unavailable}",
                class_="value",
            )
            canvas.text(
                x + 22,
                y + 156,
                f"auxiliary B1/B2 context: {len(auxiliary_rows)}; does not validate ANFIS",
                class_="small",
            )
        else:
            canvas.text(
                x + 22,
                y + 139,
                f"available estimands: {estimated}/{len(rows)}",
                class_="value",
            )
        families = sorted({row["multiplicity_family"] for row in rows if row["multiplicity_family"]})
        canvas.text(
            x + 22,
            y + 181,
            "Holm families: " + (", ".join(families) if families else "N/A"),
            class_="small",
        )
        canvas.close_group()
    canvas.text(
        45,
        645,
        "Preserved Holm universes: " + "; ".join(f"{family}={holm[family]}" for family in ("A", "B", "C", "D", "E")),
        class_="label",
    )
    return canvas.finish()


def _nested_mapping(
    payload: Mapping[str, Any], key: str, *, source: str
) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise _error(f"F08 {source} lacks mapping {key}")
    return cast(Mapping[str, Any], value)


def _provenance_text(
    payload: Mapping[str, Any], key: str, *, source: str
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise _error(f"F08 {source} lacks text {key}")
    return value


def _figure_f08_provenance(
    contract: SynthesisContract, *, root: Path
) -> bytes:
    activation_1 = _read_allowed_json(contract, root, E0_U_ACTIVATION)
    failure_1 = _read_allowed_json(contract, root, E0_U_ATTEMPT_1_FAILURE)
    activation_2 = _read_allowed_json(contract, root, E0_U_RECOVERY_ACTIVATION)
    failure_2 = _read_allowed_json(contract, root, E0_U_ATTEMPT_2_FAILURE)
    activation_3 = _read_allowed_json(contract, root, E0_U_RECOVERY_2_ACTIVATION)
    benchmark = _read_allowed_json(contract, root, BENCHMARK_MANIFEST)
    software = _read_allowed_json(contract, root, SOFTWARE_MANIFEST)

    history_1 = _nested_mapping(failure_1, "historical_chain", source=E0_U_ATTEMPT_1_FAILURE)
    recovery_2 = _nested_mapping(activation_2, "recovery_chain", source=E0_U_RECOVERY_ACTIVATION)
    history_2 = _nested_mapping(failure_2, "historical_chain", source=E0_U_ATTEMPT_2_FAILURE)
    recovery_3 = _nested_mapping(activation_3, "recovery_2_chain", source=E0_U_RECOVERY_2_ACTIVATION)
    attempt_3_recovery = _nested_mapping(activation_3, "recovery_chain", source=E0_U_RECOVERY_2_ACTIVATION)
    if (
        activation_2.get("attempt_ordinal") != 2
        or activation_3.get("attempt_ordinal") != 3
        or failure_1.get("attempt_ordinal") != 1
        or failure_2.get("attempt_ordinal") != 2
        or benchmark.get("manifest_last") is not True
        or benchmark.get("execution_id") != activation_3.get("execution_id")
        or PHASE3_U3_COMMIT
        != "d72bb727f7d524bb423cb7cbaf425104291b7f31"
        or PHASE3_H4_COMMIT
        != "d53eaef9eb5aaf90fe02c8e337346879f6403c4d"
        or GIT_COMMIT_RE.fullmatch(PHASE3_U3_COMMIT) is None
        or GIT_COMMIT_RE.fullmatch(PHASE3_H4_COMMIT) is None
    ):
        raise _error("F08 attempt ordinals/execution identity drifted")

    commits = {
        "R": _provenance_text(activation_1, "base_r_commit", source=E0_U_ACTIVATION),
        "H1": _provenance_text(activation_1, "h_commit", source=E0_U_ACTIVATION),
        "P1": _provenance_text(activation_1, "p_commit", source=E0_U_ACTIVATION),
        "U1": _provenance_text(history_1, "u1_commit", source=E0_U_ATTEMPT_1_FAILURE),
        "H2": _provenance_text(recovery_2, "h2_commit", source=E0_U_RECOVERY_ACTIVATION),
        "P2": _provenance_text(recovery_2, "p2_commit", source=E0_U_RECOVERY_ACTIVATION),
        "U2": _provenance_text(history_2, "u2_commit", source=E0_U_ATTEMPT_2_FAILURE),
        "H3": _provenance_text(recovery_3, "h3_commit", source=E0_U_RECOVERY_2_ACTIVATION),
        "P3": _provenance_text(recovery_3, "p3_commit", source=E0_U_RECOVERY_2_ACTIVATION),
    }
    if (
        _provenance_text(attempt_3_recovery, "h2_commit", source=E0_U_RECOVERY_2_ACTIVATION) != commits["H2"]
        or _provenance_text(attempt_3_recovery, "p2_commit", source=E0_U_RECOVERY_2_ACTIVATION) != commits["P2"]
        or _provenance_text(software, "repository_commit", source=SOFTWARE_MANIFEST) != commits["H3"]
    ):
        raise _error("F08 recovery-chain JSON records disagree")
    nodes = (
        ("R", commits["R"], "base"),
        ("H1", commits["H1"], "hardening"),
        ("P1", commits["P1"], "authority"),
        ("U1", commits["U1"], "recorded failure"),
        ("H2", commits["H2"], "recovery hardening"),
        ("P2", commits["P2"], "recovery authority"),
        ("U2", commits["U2"], "recorded failure"),
        ("H3", commits["H3"], "recovery-2 hardening"),
        ("P3", commits["P3"], "recovery-2 authority"),
        ("U3", PHASE3_U3_COMMIT, "only successful attempt"),
        ("H4", PHASE3_H4_COMMIT, "hardening outcome-free"),
        ("F", contract.closure_source_commit, "final freeze"),
    )

    description = _figure_description(
        (
            E0_U_ACTIVATION,
            E0_U_ATTEMPT_1_FAILURE,
            E0_U_RECOVERY_ACTIVATION,
            E0_U_ATTEMPT_2_FAILURE,
            E0_U_RECOVERY_2_ACTIVATION,
            BENCHMARK_MANIFEST,
            SOFTWARE_MANIFEST,
        ),
        filters=(
            "top-level base_r_commit/h_commit/p_commit plus historical_chain, "
            "recovery_chain and recovery_2_chain commit records; attempt_ordinal "
            "1/2/3; benchmark execution_id and manifest_last; software repository_commit; "
            "U3/H4 identities are the exact published Git commits sealed by "
            "H-SYN; H4/F are topology/freeze nodes and are not predictive results"
        ),
    )
    canvas = _SvgCanvas(
        "F08",
        contract.artifact_captions["F08"],
        description,
        "F08 - Activation, recovery, and freeze provenance",
        width=1940,
        height=500,
    )
    canvas.text(40, 72, "R -> H1/P1/U1 -> H2/P2/U2 -> H3/P3/U3 -> H4 -> F; traceability, not performance.", class_="subtitle")
    canvas.raw(
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#6b7280"/></marker></defs>'
    )
    group_specs = (
        (1, 3, "attempt 1 - recorded failure", "#fef3c7"),
        (4, 6, "attempt 2 - recorded failure", "#ffedd5"),
        (7, 9, "attempt 3 - only success", "#dbeafe"),
    )
    x0 = 42
    node_width = 132
    gap = 25
    for start, end, label, fill in group_specs:
        left = x0 + start * (node_width + gap) - 10
        width = (end - start + 1) * node_width + (end - start) * gap + 20
        canvas.element("rect", x=left, y=112, width=width, height=288, rx=14, fill=fill, stroke="#d1d5db", stroke_width=1)
        canvas.text(left + width // 2, 137, label, class_="small", text_anchor="middle", font_weight="700")
    for index in range(len(nodes) - 1):
        x1 = x0 + index * (node_width + gap) + node_width
        x2 = x0 + (index + 1) * (node_width + gap)
        canvas.element("line", x1=x1, y1=255, x2=x2 - 4, y2=255, stroke="#6b7280", stroke_width=2, marker_end="url(#arrow)", class_="provenance-edge")
    for index, (stage, identity, state) in enumerate(nodes):
        x = x0 + index * (node_width + gap)
        is_failure = stage in {"U1", "U2"}
        fill = "#fde68a" if is_failure else ("#bfdbfe" if stage == "U3" else "#f3f4f6")
        canvas.open_group(
            class_="provenance-node",
            data_stage=stage,
            data_identity=identity,
            data_state=state,
        )
        canvas.element("rect", x=x, y=175, width=node_width, height=160, rx=10, fill=fill, stroke="#4b5563", stroke_width=1)
        canvas.text(x + node_width // 2, 215, stage, class_="heading", text_anchor="middle")
        display_identity = identity[:8] if len(identity) >= 40 else (identity[:14] + "…" if len(identity) > 15 else identity)
        canvas.text(x + node_width // 2, 252, display_identity, class_="value", text_anchor="middle")
        words = state.split()
        canvas.text(x + node_width // 2, 285, " ".join(words[:2]), class_="small", text_anchor="middle")
        if len(words) > 2:
            canvas.text(x + node_width // 2, 303, " ".join(words[2:]), class_="small", text_anchor="middle")
        canvas.close_group()
    canvas.text(42, 445, "U1/U2: preserved failures - U3: only materialized scientific result - H4/F: subsequent reproducible closure.", class_="label")
    return canvas.finish()


def _figure_payloads(
    contract: SynthesisContract,
    matrix_rows: Sequence[Mapping[str, str]],
    *,
    root: Path,
) -> dict[str, bytes]:
    return {
        "F01_intent_to_predict_funnel.svg": _figure_f01_intent_to_predict(
            contract, root=root
        ),
        "F02_benchmark_metrics.svg": _figure_f02_benchmark_metrics(
            contract, root=root
        ),
        "F03_descriptive_deltas.svg": _figure_f03_descriptive_deltas(
            contract, root=root
        ),
        "F04_threshold_sensitivity.svg": _figure_f04_threshold_sensitivity(
            contract, root=root
        ),
        "F05_trophic_heatmap.svg": _figure_f05_trophic_heatmap(
            contract, root=root
        ),
        "F06_uncertainty_coverage.svg": _figure_f06_uncertainty(
            contract, root=root
        ),
        "F07_hypothesis_verdicts.svg": _figure_f07_hypothesis_verdicts(
            contract, matrix_rows
        ),
        "F08_provenance.svg": _figure_f08_provenance(contract, root=root),
    }


def _safe_repository_path(
    root: Path, path_text: str, *, expected_mode: int = 0o644
) -> tuple[Path, os.stat_result]:
    if "\\" in path_text or "\x00" in path_text:
        raise _error(f"Repository path is not canonical: {path_text!r}")
    relative = PurePosixPath(path_text)
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise _error(f"Repository path is not relative: {path_text!r}")
    cursor = root
    for part in relative.parts[:-1]:
        cursor = cursor / part
        try:
            metadata = cursor.lstat()
        except OSError as exc:
            raise _error(f"Repository parent is absent: {cursor}") from exc
        if cursor.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
            raise _error(f"Repository parent is not a no-follow directory: {cursor}")
    path = cursor / relative.parts[-1]
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _error(f"Repository file is absent: {path_text}") from exc
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise _error(f"Repository file is not regular: {path_text}")
    if metadata.st_nlink != 1:
        raise _error(f"Repository file must be single-link: {path_text}")
    if stat.S_IMODE(metadata.st_mode) != expected_mode:
        raise _error(f"Repository file mode drifted: {path_text}")
    return path, metadata


def _read_repository_file(
    root: Path, path_text: str, *, expected_mode: int = 0o644
) -> tuple[bytes, dict[str, Any]]:
    path, expected = _safe_repository_path(
        root, path_text, expected_mode=expected_mode
    )
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino) != (expected.st_dev, expected.st_ino)
        ):
            raise _error(f"Repository file identity changed before read: {path_text}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_nlink,
        ) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            before.st_nlink,
        ):
            raise _error(f"Repository file identity changed during read: {path_text}")
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    return payload, {
        "path": path_text,
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "filesystem_mode": stat.S_IMODE(before.st_mode),
        "device": before.st_dev,
        "inode": before.st_ino,
        "link_count": before.st_nlink,
        "mtime_ns": before.st_mtime_ns,
        "ctime_ns": before.st_ctime_ns,
    }


def _git_blob_bytes(
    root: Path, commit: str, path_text: str, *, expected_mode: str = "100644"
) -> bytes:
    output = cast(
        str, authority_locker._git(root, "ls-tree", commit, "--", path_text)
    ).strip()
    fields = output.split(None, 3)
    if (
        len(fields) != 4
        or fields[0] != expected_mode
        or fields[1] != "blob"
        or authority_locker.GIT_OID_RE.fullmatch(fields[2]) is None
        or fields[3] != path_text
    ):
        raise _error(f"P-SYN path is not one exact Git blob: {path_text}")
    return cast(
        bytes,
        authority_locker._git(root, "cat-file", "blob", fields[2], text=False),
    )


def _reconstruct_h_syn_authority(
    root: Path, authority: Mapping[str, Any]
) -> str:
    implementation = authority.get("synthesis_implementation_commit")
    if not isinstance(implementation, str):
        raise _error("P-SYN implementation commit is absent")
    observed_h = authority_locker._validate_published_h(root, implementation)
    if authority.get("h_component_records") != observed_h:
        raise _error("P-SYN H-SYN component records differ from Git/physical bytes")
    for record in observed_h:
        path_text = cast(str, record["path"])
        git_mode = authority_locker.H_GIT_MODES[path_text]
        payload, physical = _read_repository_file(
            root, path_text, expected_mode=int(git_mode[-3:], 8)
        )
        if (
            physical["bytes"] != record["bytes"]
            or physical["sha256"] != record["sha256"]
            or payload
            != _git_blob_bytes(
                root, implementation, path_text, expected_mode=git_mode
            )
        ):
            raise _error(f"P-SYN H-SYN component binding drifted: {path_text}")
    return implementation


def _verify_p_syn_publication(
    root: Path,
    authority: Mapping[str, Any],
    authority_bytes: bytes,
    manifest_bytes: bytes,
    *,
    verify_remote: bool,
    allowed_untracked_paths: Sequence[str] = (),
) -> str:
    implementation = cast(str, authority["synthesis_implementation_commit"])
    head = authority_locker._one_oid(root, "HEAD")
    parents = cast(
        str,
        authority_locker._git(root, "rev-list", "--parents", "-n", "1", head),
    ).split()
    if parents != [head, implementation]:
        raise _error("Effective P-SYN must be the direct, single-parent child of H-SYN")
    expected_scope = {
        AUTHORITY_PATH.as_posix(): "A",
        AUTHORITY_MANIFEST_PATH.as_posix(): "A",
    }
    if authority_locker._commit_scope(root, head) != expected_scope:
        raise _error("Effective P-SYN commit scope is not exact2A")
    status = authority_locker._parse_status(root)
    expected_status = {path: "??" for path in allowed_untracked_paths}
    if status != expected_status:
        if expected_status:
            raise _error(
                "Effective P-SYN worktree differs from the exact R-SYN publication"
            )
        raise _error("Effective P-SYN requires a clean worktree and index")
    authority_locker._validate_refs(root, head, verify_remote=verify_remote)
    for path, expected in (
        (AUTHORITY_PATH, authority_bytes),
        (AUTHORITY_MANIFEST_PATH, manifest_bytes),
    ):
        if _git_blob_bytes(root, head, path.as_posix()) != expected:
            raise _error(f"Effective P-SYN Git/physical bytes differ: {path}")
    return head


def validate_authority(
    contract: SynthesisContract,
    *,
    root: Path = PROJECT_ROOT,
    verify_publication: bool = True,
    verify_remote: bool = True,
    allowed_untracked_paths: Sequence[str] = (),
) -> Mapping[str, Any]:
    authority_bytes, _authority_record = _read_repository_file(
        root, AUTHORITY_PATH.as_posix()
    )
    manifest_bytes, _manifest_record = _read_repository_file(
        root, AUTHORITY_MANIFEST_PATH.as_posix()
    )
    authority = _decode_json(authority_bytes, context=AUTHORITY_PATH.as_posix())
    manifest = _decode_json(
        manifest_bytes, context=AUTHORITY_MANIFEST_PATH.as_posix()
    )
    if (
        canonical_json_bytes(authority) != authority_bytes
        or canonical_json_bytes(manifest) != manifest_bytes
    ):
        raise _error("P-SYN authority bundle is not canonical JSON")
    try:
        authority_locker.validate_authority(authority)
    except SynthesisContractError as exc:
        raise _error(f"P-SYN locker authority validation failed: {exc}") from exc
    implementation = cast(str, authority["synthesis_implementation_commit"])
    expected_manifest = authority_locker._build_manifest(
        authority_bytes, implementation
    )
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("P-SYN companion is not the exact locker manifest")
    _reconstruct_h_syn_authority(root, authority)
    if authority.get("closure_source_commit") != contract.closure_source_commit:
        raise _error("P-SYN closure source commit drifted")
    records = collect_input_records(contract, root=root)
    expected = {
        "allowed_input_paths_digest": digest_strings(contract.allowed_input_paths),
        "allowed_input_records_digest": digest_records(records),
        "output_paths_and_order_digest": digest_strings(contract.output_paths),
    }
    for key, value in expected.items():
        if authority.get(key) != value:
            raise _error(f"P-SYN {key} drifted")
    if authority.get("allowed_input_paths") != list(contract.allowed_input_paths):
        raise _error("P-SYN allowed input path list drifted")
    if authority.get("allowed_input_records") != records:
        raise _error("P-SYN allowed input records differ from source Git/physical bytes")
    if authority.get("ordered_output_paths") != list(contract.output_paths):
        raise _error("P-SYN output path order drifted")
    if verify_publication:
        _verify_p_syn_publication(
            root,
            authority,
            authority_bytes,
            manifest_bytes,
            verify_remote=verify_remote,
            allowed_untracked_paths=allowed_untracked_paths,
        )
    return dict(authority)


def _capture_prepublication_snapshot(
    contract: SynthesisContract,
    *,
    root: Path,
    verify_remote: bool,
    allowed_untracked_paths: Sequence[str] = (),
) -> dict[str, Any]:
    authority = validate_authority(
        contract,
        root=root,
        verify_publication=True,
        verify_remote=verify_remote,
        allowed_untracked_paths=allowed_untracked_paths,
    )
    authority_bytes, authority_file = _read_repository_file(
        root, AUTHORITY_PATH.as_posix()
    )
    manifest_bytes, manifest_file = _read_repository_file(
        root, AUTHORITY_MANIFEST_PATH.as_posix()
    )
    allowed_input_records = collect_input_records(contract, root=root)
    input_modes = {
        cast(str, record["path"]): cast(int, record["filesystem_mode"])
        for record in allowed_input_records
    }
    return {
        "head": authority_locker._one_oid(root, "HEAD"),
        "authority": authority,
        "authority_file": authority_file,
        "authority_bytes_sha256": sha256_bytes(authority_bytes),
        "manifest_file": manifest_file,
        "manifest_bytes_sha256": sha256_bytes(manifest_bytes),
        "allowed_input_records": allowed_input_records,
        "allowed_input_files": [
            _read_repository_file(
                root,
                path_text,
                expected_mode=input_modes[path_text],
            )[1]
            for path_text in contract.allowed_input_paths
        ],
    }


def _expected_input_bindings(
    contract: SynthesisContract, authority: Mapping[str, Any]
) -> dict[str, tuple[int, str, int]]:
    records = authority.get("allowed_input_records")
    if not isinstance(records, list) or [
        record.get("path") if isinstance(record, Mapping) else None
        for record in records
    ] != list(contract.allowed_input_paths):
        raise _error("P-SYN input bindings differ from the ordered allowlist")
    bindings: dict[str, tuple[int, str, int]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise _error("P-SYN input binding is not a record")
        path_text = record.get("path")
        byte_count = record.get("bytes")
        sha256 = record.get("sha256")
        filesystem_mode = record.get("filesystem_mode")
        if (
            not isinstance(path_text, str)
            or isinstance(byte_count, bool)
            or not isinstance(byte_count, int)
            or byte_count < 0
            or not isinstance(sha256, str)
            or SHA256_RE.fullmatch(sha256) is None
            or isinstance(filesystem_mode, bool)
            or not isinstance(filesystem_mode, int)
            or filesystem_mode < 0
            or filesystem_mode > 0o777
            or path_text in bindings
        ):
            raise _error(f"P-SYN input binding is invalid: {path_text!r}")
        bindings[path_text] = (byte_count, sha256, filesystem_mode)
    return bindings


def build_payloads(
    contract: SynthesisContract,
    authority: Mapping[str, Any],
    *,
    p_syn_commit: str,
    authority_manifest_sha256: str,
    root: Path = PROJECT_ROOT,
) -> dict[str, bytes]:
    if GIT_COMMIT_RE.fullmatch(p_syn_commit) is None:
        raise _error("R-SYN P-SYN commit is invalid")
    if SHA256_RE.fullmatch(authority_manifest_sha256) is None:
        raise _error("R-SYN P-SYN companion digest is invalid")
    input_bindings = _expected_input_bindings(contract, authority)
    binding_token = _EXPECTED_INPUT_BINDINGS.set(input_bindings)
    try:
        matrix_rows = build_final_closure_rows(contract, root=root)
        claim_rows = build_claim_evidence_rows(contract, root=root)
        payloads: dict[str, bytes] = {
            "FINAL_CLOSURE_MATRIX.csv": csv_bytes(matrix_rows, contract.final_closure_columns),
            "THESIS_CLAIM_EVIDENCE_MATRIX.csv": csv_bytes(claim_rows, contract.claim_evidence_columns),
            "FINAL_CLOSURE_REPORT.md": _report(contract, matrix_rows, claim_rows),
        }
        tables = _table_payloads(contract, root, matrix_rows)
        payloads.update({f"THESIS_TABLES/{name}": payload for name, payload in tables.items()})
        figures = _figure_payloads(contract, matrix_rows, root=root)
        payloads.update({f"THESIS_FIGURES/{name}": payload for name, payload in figures.items()})
    finally:
        _EXPECTED_INPUT_BINDINGS.reset(binding_token)
    ordered_relative = [str(Path(path).relative_to(SYNTHESIS_ROOT)) for path in contract.output_paths]
    manifest_relative = "synthesis_bundle_manifest.json"
    expected_pre_manifest = ordered_relative[:-1]
    if list(payloads) != expected_pre_manifest:
        raise _error("Builder output construction order drifted")
    output_records = [
        {
            "path": f"{SYNTHESIS_ROOT.as_posix()}/{relative}",
            "bytes": len(payloads[relative]),
            "sha256": sha256_bytes(payloads[relative]),
        }
        for relative in expected_pre_manifest
    ]
    builder_records = [
        record
        for record in authority["h_component_records"]
        if record.get("path") == authority_locker.BUILDER_PATH
    ]
    if len(builder_records) != 1:
        raise _error("P-SYN authority does not bind one exact synthesis builder")
    builder_record = builder_records[0]
    script_record = {
        "path": builder_record["path"],
        "bytes": builder_record["bytes"],
        "sha256": builder_record["sha256"],
    }
    manifest = {
        "schema_version": "closure_v1_phase4_synthesis_bundle_manifest_v1",
        "status": "completed",
        "closure_source_commit": contract.closure_source_commit,
        "synthesis_implementation_commit": authority["synthesis_implementation_commit"],
        "p_syn_commit": p_syn_commit,
        "authority": {
            "path": AUTHORITY_PATH.as_posix(),
            "sha256": sha256_bytes(canonical_json_bytes(authority)),
        },
        "authority_manifest": {
            "path": AUTHORITY_MANIFEST_PATH.as_posix(),
            "sha256": authority_manifest_sha256,
        },
        "captions": dict(contract.artifact_captions),
        "script": script_record,
        "inputs": authority["allowed_input_records"],
        "input_records_digest": authority["allowed_input_records_digest"],
        "output_paths_and_order_digest": digest_strings(contract.output_paths),
        "outputs": output_records,
        "manifest_path": contract.output_paths[-1],
        "manifest_last": True,
        "timestamp_included": False,
        "dvc_required": False,
    }
    payloads[manifest_relative] = canonical_json_bytes(manifest)
    return payloads


@dataclass(frozen=True)
class _OwnedFileAt:
    parent_fd: int
    name: str
    device: int
    inode: int


@dataclass(frozen=True)
class _OwnedDirectoryAt:
    parent_fd: int
    name: str
    fd: int
    device: int
    inode: int


def _open_directory_at(parent_fd: int, name: str, *, context: str) -> int:
    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} has an unsafe directory name")
    try:
        expected = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise _error(f"{context} is absent") from exc
    if not stat.S_ISDIR(expected.st_mode):
        raise _error(f"{context} is not a no-follow directory")
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=parent_fd,
    )
    observed = os.fstat(descriptor)
    if (observed.st_dev, observed.st_ino) != (expected.st_dev, expected.st_ino):
        os.close(descriptor)
        raise _error(f"{context} changed while opening")
    return descriptor


def _stat_optional_at(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _mkdir_owned_at(
    parent_fd: int, name: str, *, mode: int, context: str
) -> _OwnedDirectoryAt:
    try:
        os.mkdir(name, mode=mode, dir_fd=parent_fd)
    except FileExistsError as exc:
        raise _error(f"{context} already exists") from exc
    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode):
        raise _error(f"{context} creation did not produce a directory")
    descriptor: int | None = None
    owner: _OwnedDirectoryAt | None = None
    try:
        descriptor = _open_directory_at(parent_fd, name, context=context)
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        owner = _OwnedDirectoryAt(
            parent_fd, name, descriptor, metadata.st_dev, metadata.st_ino
        )
        _require_owned_directory_at(owner, context=context, mode=mode)
    except BaseException as exc:
        if descriptor is not None:
            os.close(descriptor)
        current = _stat_optional_at(parent_fd, name)
        if current is not None and (
            current.st_dev,
            current.st_ino,
        ) == (metadata.st_dev, metadata.st_ino):
            try:
                os.rmdir(name, dir_fd=parent_fd)
            except BaseException as cleanup_exc:
                raise _error(f"{context} creation cleanup failed") from cleanup_exc
        raise exc
    if owner is None:
        raise _error(f"{context} ownership was not established")
    return owner


def _create_owned_file_at(
    parent_fd: int, name: str, payload: bytes, *, mode: int, context: str
) -> _OwnedFileAt:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, mode, dir_fd=parent_fd)
    metadata = os.fstat(descriptor)
    owner = _OwnedFileAt(parent_fd, name, metadata.st_dev, metadata.st_ino)
    primary: BaseException | None = None
    cleanup: BaseException | None = None
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise _error(f"{context} write made no progress")
            view = view[written:]
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
    except BaseException as exc:
        primary = exc
    try:
        os.close(descriptor)
    except BaseException as exc:
        cleanup = exc
    if primary is not None or cleanup is not None:
        try:
            _unlink_owned_file_at(owner, context=context)
        except BaseException as exc:
            cleanup = exc
        if cleanup is not None:
            raise _error(f"{context} partial-file cleanup failed: {cleanup}") from cleanup
        if primary is not None:
            raise primary
    _require_owned_file_at(owner, context=context, mode=mode)
    return owner


def _require_owned_file_at(
    owner: _OwnedFileAt,
    *,
    context: str,
    link_count: int | None = None,
    mode: int | None = None,
) -> os.stat_result:
    try:
        metadata = os.stat(
            owner.name, dir_fd=owner.parent_fd, follow_symlinks=False
        )
    except OSError as exc:
        raise _error(f"{context} disappeared") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or (metadata.st_dev, metadata.st_ino) != (owner.device, owner.inode)
        or (link_count is not None and metadata.st_nlink != link_count)
        or (mode is not None and stat.S_IMODE(metadata.st_mode) != mode)
    ):
        raise _error(f"{context} ownership/link identity drifted")
    return metadata


def _read_owned_file_at(
    owner: _OwnedFileAt,
    *,
    context: str,
    link_count: int | None = None,
    mode: int | None = None,
) -> bytes:
    expected = _require_owned_file_at(
        owner, context=context, link_count=link_count, mode=mode
    )
    descriptor = os.open(
        owner.name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=owner.parent_fd,
    )
    try:
        before = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (expected.st_dev, expected.st_ino):
            raise _error(f"{context} changed before read")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_nlink,
        ) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_nlink,
        ):
            raise _error(f"{context} changed during read")
    finally:
        os.close(descriptor)
    if link_count is not None and after.st_nlink != link_count:
        raise _error(f"{context} link count drifted during read")
    return b"".join(chunks)


def _unlink_owned_file_at(owner: _OwnedFileAt, *, context: str) -> None:
    current = _stat_optional_at(owner.parent_fd, owner.name)
    if current is None:
        return
    if (
        not stat.S_ISREG(current.st_mode)
        or (current.st_dev, current.st_ino) != (owner.device, owner.inode)
    ):
        raise _error(f"{context} rollback preserved a foreign replacement")
    os.unlink(owner.name, dir_fd=owner.parent_fd)
    if _stat_optional_at(owner.parent_fd, owner.name) is not None:
        raise _error(f"{context} rollback did not establish absence")


def _require_owned_directory_at(
    owner: _OwnedDirectoryAt, *, context: str, mode: int | None = None
) -> None:
    current = _stat_optional_at(owner.parent_fd, owner.name)
    if (
        current is None
        or not stat.S_ISDIR(current.st_mode)
        or (current.st_dev, current.st_ino) != (owner.device, owner.inode)
        or (mode is not None and stat.S_IMODE(current.st_mode) != mode)
    ):
        raise _error(f"{context} ownership/path binding drifted")
    descriptor_metadata = os.fstat(owner.fd)
    if (descriptor_metadata.st_dev, descriptor_metadata.st_ino) != (
        owner.device,
        owner.inode,
    ) or (mode is not None and stat.S_IMODE(descriptor_metadata.st_mode) != mode):
        raise _error(f"{context} descriptor binding drifted")


def _rmdir_owned_at(owner: _OwnedDirectoryAt, *, context: str) -> None:
    current = _stat_optional_at(owner.parent_fd, owner.name)
    if current is None:
        return
    if (
        not stat.S_ISDIR(current.st_mode)
        or (current.st_dev, current.st_ino) != (owner.device, owner.inode)
    ):
        raise _error(f"{context} rollback preserved a foreign directory")
    os.rmdir(owner.name, dir_fd=owner.parent_fd)
    if _stat_optional_at(owner.parent_fd, owner.name) is not None:
        raise _error(f"{context} rollback did not establish absence")


def _publish_payloads(
    payloads: Mapping[str, bytes],
    contract: SynthesisContract,
    *,
    root: Path,
    prepublish_validator: Callable[[], None] | None = None,
    postpublish_validator: Callable[[], None] | None = None,
) -> None:
    expected_relative = [
        str(Path(path).relative_to(SYNTHESIS_ROOT)) for path in contract.output_paths
    ]
    if (
        len(expected_relative) != 24
        or list(payloads) != expected_relative
        or expected_relative[-1] != "synthesis_bundle_manifest.json"
        or any(not isinstance(payload, bytes) for payload in payloads.values())
    ):
        raise _error("R-SYN publication order is not exact24 manifest-last")
    relative_parts: dict[str, tuple[str, ...]] = {}
    for relative in expected_relative:
        path = PurePosixPath(relative)
        if (
            path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or len(path.parts) not in {1, 2}
            or (len(path.parts) == 2 and path.parts[0] not in {"THESIS_TABLES", "THESIS_FIGURES"})
        ):
            raise _error(f"Unsafe R-SYN output path: {relative}")
        relative_parts[relative] = path.parts

    root = root.resolve()
    root_fd = os.open(
        root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    )
    open_fds: list[int] = [root_fd]
    created_directories: list[_OwnedDirectoryAt] = []
    published_files: list[tuple[_OwnedFileAt, bytes]] = []
    temporaries: list[_OwnedFileAt] = []
    guard: _OwnedFileAt | None = None
    coordination: _OwnedDirectoryAt | None = None
    tmp_root_owned: _OwnedDirectoryAt | None = None
    primary_error: BaseException | None = None
    cleanup_errors: list[BaseException] = []
    closure_fd: int | None = None
    tmp_fd: int | None = None
    try:
        reports_fd = _open_directory_at(root_fd, "reports", context="reports root")
        open_fds.append(reports_fd)
        closure_fd = _open_directory_at(
            reports_fd, "closure_v1", context="Closure report root"
        )
        open_fds.append(closure_fd)
        if _stat_optional_at(root_fd, "tmp") is None:
            tmp_root_owned = _mkdir_owned_at(
                root_fd,
                "tmp",
                mode=0o700,
                context="temporary root",
            )
            tmp_fd = tmp_root_owned.fd
            os.fsync(root_fd)
        else:
            tmp_fd = _open_directory_at(root_fd, "tmp", context="temporary root")
        open_fds.append(tmp_fd)
        if _stat_optional_at(closure_fd, SYNTHESIS_ROOT.name) is not None:
            raise _error("Refusing to clobber the R-SYN namespace")
        coordination_name = GUARD_PATH.parent.name
        if _stat_optional_at(tmp_fd, coordination_name) is not None:
            raise _error("R-SYN coordination namespace already exists")

        coordination = _mkdir_owned_at(
            tmp_fd,
            coordination_name,
            mode=0o700,
            context="R-SYN coordination namespace",
        )
        open_fds.append(coordination.fd)
        guard = _create_owned_file_at(
            coordination.fd,
            GUARD_PATH.name,
            canonical_json_bytes(
                {"gate": "R-SYN", "nonce": secrets.token_hex(16), "pid": os.getpid()}
            ),
            mode=0o600,
            context="R-SYN guard",
        )
        for index, relative in enumerate(expected_relative):
            temporaries.append(
                _create_owned_file_at(
                    coordination.fd,
                    f"output.{index:02d}.tmp",
                    payloads[relative],
                    mode=0o644,
                    context=f"R-SYN temporary {relative}",
                )
            )
        os.fsync(coordination.fd)

        # Inputs and P-SYN stay immutable while the exclusive ignored guard is
        # held.  This callback runs after all temporary bytes exist and before
        # even the R-SYN root directory is created.
        if prepublish_validator is not None:
            prepublish_validator()

        final_directory = _mkdir_owned_at(
            closure_fd,
            SYNTHESIS_ROOT.name,
            mode=0o755,
            context="R-SYN output root",
        )
        created_directories.append(final_directory)
        open_fds.append(final_directory.fd)
        child_directories: dict[str, _OwnedDirectoryAt] = {}
        for child_name in ("THESIS_TABLES", "THESIS_FIGURES"):
            child = _mkdir_owned_at(
                final_directory.fd,
                child_name,
                mode=0o755,
                context=f"R-SYN {child_name} directory",
            )
            child_directories[child_name] = child
            created_directories.append(child)
            open_fds.append(child.fd)
        os.fsync(final_directory.fd)
        os.fsync(closure_fd)

        for index, relative in enumerate(expected_relative):
            parts = relative_parts[relative]
            destination_fd = (
                final_directory.fd
                if len(parts) == 1
                else child_directories[parts[0]].fd
            )
            destination_name = parts[-1]
            temporary = temporaries[index]
            try:
                os.link(
                    temporary.name,
                    destination_name,
                    src_dir_fd=coordination.fd,
                    dst_dir_fd=destination_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                raise _error(f"R-SYN output already exists: {relative}") from exc
            except OSError as exc:
                current = _stat_optional_at(destination_fd, destination_name)
                if current is not None and (
                    current.st_dev,
                    current.st_ino,
                ) == (temporary.device, temporary.inode):
                    published_files.append(
                        (
                            _OwnedFileAt(
                                destination_fd,
                                destination_name,
                                temporary.device,
                                temporary.inode,
                            ),
                            payloads[relative],
                        )
                    )
                if exc.errno == errno.EXDEV:
                    raise _error("R-SYN hardlink publication crossed filesystems") from exc
                raise
            output_owner = _OwnedFileAt(
                destination_fd,
                destination_name,
                temporary.device,
                temporary.inode,
            )
            published_files.append((output_owner, payloads[relative]))
            if _read_owned_file_at(
                output_owner,
                context=f"R-SYN output {relative}",
                link_count=2,
                mode=0o644,
            ) != payloads[relative]:
                raise _error(f"R-SYN output bytes drifted: {relative}")
            os.fsync(destination_fd)

        # Revalidate the published P-SYN authority, refs, and all 83 structured
        # inputs after the final (manifest) link exists.  At this point the
        # only permitted Git-status entries are the exact24 owned R-SYN files.
        if postpublish_validator is not None:
            postpublish_validator()

        # Only owned temporary links are removed; output link counts must then
        # be exactly one.  The manifest was the final link in the loop above.
        for temporary in reversed(temporaries):
            _unlink_owned_file_at(temporary, context="R-SYN temporary")
        os.fsync(coordination.fd)
        for owner, expected_bytes in published_files:
            if _read_owned_file_at(
                owner, context="R-SYN final output", link_count=1, mode=0o644
            ) != expected_bytes:
                raise _error("R-SYN final output bytes drifted")

        expected_top = {
            parts[0] for parts in relative_parts.values()
        }
        if set(os.listdir(final_directory.fd)) != expected_top:
            raise _error("R-SYN root contains an unexpected entry")
        for child_name, child in child_directories.items():
            expected_children = {
                parts[1]
                for parts in relative_parts.values()
                if len(parts) == 2 and parts[0] == child_name
            }
            if set(os.listdir(child.fd)) != expected_children:
                raise _error(f"R-SYN {child_name} contains an unexpected entry")
            _require_owned_directory_at(
                child, context=f"R-SYN {child_name}", mode=0o755
            )
            os.fsync(child.fd)
        _require_owned_directory_at(
            final_directory, context="R-SYN output root", mode=0o755
        )
        os.fsync(final_directory.fd)
        os.fsync(closure_fd)

        _unlink_owned_file_at(guard, context="R-SYN guard")
        os.fsync(coordination.fd)
        _rmdir_owned_at(coordination, context="R-SYN coordination namespace")
        os.fsync(tmp_fd)
        if tmp_root_owned is not None:
            _rmdir_owned_at(tmp_root_owned, context="R-SYN temporary root")
            os.fsync(root_fd)

        # Final path/inode/byte revalidation occurs after coordination cleanup.
        _require_owned_directory_at(
            final_directory, context="R-SYN output root", mode=0o755
        )
        for owner, expected_bytes in published_files:
            if _read_owned_file_at(
                owner, context="R-SYN final output", link_count=1, mode=0o644
            ) != expected_bytes:
                raise _error("R-SYN post-cleanup output bytes drifted")
    except BaseException as exc:
        primary_error = exc
        for owner, _payload in reversed(published_files):
            try:
                _unlink_owned_file_at(owner, context="R-SYN output")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        for directory in reversed(created_directories):
            try:
                _rmdir_owned_at(directory, context="R-SYN output directory")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        for temporary in reversed(temporaries):
            try:
                _unlink_owned_file_at(temporary, context="R-SYN temporary")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if guard is not None:
            try:
                _unlink_owned_file_at(guard, context="R-SYN guard")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if coordination is not None:
            try:
                _rmdir_owned_at(coordination, context="R-SYN coordination namespace")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if tmp_root_owned is not None:
            try:
                _rmdir_owned_at(tmp_root_owned, context="R-SYN temporary root")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        for descriptor in (closure_fd, tmp_fd):
            if descriptor is not None:
                try:
                    os.fsync(descriptor)
                except BaseException as cleanup_exc:
                    cleanup_errors.append(cleanup_exc)
    finally:
        for descriptor in reversed(open_fds):
            try:
                os.close(descriptor)
            except OSError:
                pass
    if cleanup_errors:
        cleanup_error = _error(
            "R-SYN cleanup failed closed: "
            + "; ".join(f"{type(exc).__name__}: {exc}" for exc in cleanup_errors)
        )
        if primary_error is not None:
            raise cleanup_error from primary_error
        raise cleanup_error
    if primary_error is not None:
        raise primary_error


def _path_is_present(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def check_only(
    *, root: Path = PROJECT_ROOT, verify_remote: bool = True
) -> dict[str, Any]:
    contract = load_contract(root=root, verify_inputs=True)
    authority_present = _path_is_present(root / AUTHORITY_PATH) or _path_is_present(
        root / AUTHORITY_MANIFEST_PATH
    )
    authority_state = "absent"
    if authority_present:
        validate_authority(contract, root=root, verify_remote=verify_remote)
        authority_state = "valid"
    if _path_is_present(root / SYNTHESIS_ROOT):
        raise _error("R-SYN namespace already exists")
    return {
        "status": "ready_for_r_syn" if authority_state == "valid" else "ready_for_p_syn",
        "writes_performed": False,
        "authority_state": authority_state,
        "allowed_input_count": len(contract.allowed_inputs),
        "output_count": len(contract.output_paths),
        "closure_source_commit": contract.closure_source_commit,
    }


def build_and_publish(
    *, root: Path = PROJECT_ROOT, verify_remote: bool = True
) -> dict[str, Any]:
    """Build exact24 and publish only while P-SYN/input snapshots stay fixed."""

    root = root.resolve()
    contract = load_contract(root=root, verify_inputs=True)
    if _path_is_present(root / SYNTHESIS_ROOT):
        raise _error("R-SYN namespace already exists")
    before = _capture_prepublication_snapshot(
        contract, root=root, verify_remote=verify_remote
    )
    authority = cast(Mapping[str, Any], before["authority"])
    payloads = build_payloads(
        contract,
        authority,
        p_syn_commit=cast(str, before["head"]),
        authority_manifest_sha256=cast(
            str, before["manifest_bytes_sha256"]
        ),
        root=root,
    )
    after_build = _capture_prepublication_snapshot(
        contract, root=root, verify_remote=verify_remote
    )
    if after_build != before:
        raise _error("P-SYN or structured inputs changed while building R-SYN")

    def revalidate_before_link() -> None:
        observed = _capture_prepublication_snapshot(
            contract, root=root, verify_remote=verify_remote
        )
        if observed != before:
            raise _error("P-SYN or structured inputs changed before R-SYN publication")

    def revalidate_after_links() -> None:
        observed = _capture_prepublication_snapshot(
            contract,
            root=root,
            verify_remote=verify_remote,
            allowed_untracked_paths=contract.output_paths,
        )
        if observed != before:
            raise _error("P-SYN or structured inputs changed during R-SYN publication")

    _publish_payloads(
        payloads,
        contract,
        root=root,
        prepublish_validator=revalidate_before_link,
        postpublish_validator=revalidate_after_links,
    )
    return {
        "status": "synthesis_bundle_written_unpublished",
        "output_count": len(payloads),
        "closure_source_commit": contract.closure_source_commit,
        "synthesis_implementation_commit": authority[
            "synthesis_implementation_commit"
        ],
        "dvc_commands_run": False,
        "raw_targets_accessed": False,
        "raw_outcomes_accessed": False,
        "scientific_network_commands_run": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--build", action="store_true")
    args = parser.parse_args(argv)
    if args.check_only:
        print(json.dumps(check_only(), sort_keys=True, separators=(",", ":")))
        return 0
    print(json.dumps(build_and_publish(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
