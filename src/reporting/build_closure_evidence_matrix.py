"""Pure E10 software-evidence composition for the Closure V1 sealed batch.

Operational evidence is supplied by E0-U as in-memory data.  This component
does not launch tests, inspect Git/DVC, read OpenAPI from disk, tag a commit, or
publish anything.  It validates and composes the supplied evidence for the
runner-owned final transaction.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import pandas as pd

from src.experiments.evaluate_anfis_ablation import (
    ClosureAnfisAblationError,
    artifact_envelope,
    validate_batch_context,
    validate_component_boundary,
)


COMPONENT_ID = "E10_evidence_matrix"
STAGE_ID = "E10"
PRIOR_STAGES = tuple(f"E{number}" for number in range(1, 10))
PRIOR_COMPONENTS = MappingProxyType(
    {
        "E1_benchmark_scientific_executor": "E1",
        "E2_site_transfer": "E2",
        "E3_threshold_sensitivity": "E3",
        "E4_composite": "E4",
        "E5_clustered_inference": "E5",
        "E6_matched_degradation": "E6",
        "E7_anfis_ablation": "E7",
        "E8_uncertainty": "E8",
        "E9_planning_inference": "E9",
    }
)
SOFTWARE_EVIDENCE_KEYS = frozenset(
    {
        "public_tests_xml",
        "test_report",
        "openapi",
        "openapi_contract_report",
        "end_to_end_report",
        "environment",
    }
)
OUTPUT_PATHS = (
    "reports/closure_v1/10_api/public_tests.xml",
    "reports/closure_v1/10_api/test_report.md",
    "reports/closure_v1/10_api/openapi.json",
    "reports/closure_v1/10_api/openapi_contract_report.md",
    "reports/closure_v1/10_api/end_to_end_report.md",
    "reports/closure_v1/10_api/environment.json",
)
COMPONENT_CONTRACT = MappingProxyType(
    {
        "schema_version": "closure_e10_evidence_matrix_component_v1",
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "software_evidence_keys": sorted(SOFTWARE_EVIDENCE_KEYS),
        "prior_stages": list(PRIOR_STAGES),
        "prior_components": dict(PRIOR_COMPONENTS),
        "public_test_failures": 0,
        "public_test_errors": 0,
        "critical_skips": "zero_or_explicitly_justified",
        "openapi_contract_valid": True,
        "end_to_end_success": True,
        "operational_commands": "forbidden_in_component",
        "git_tagging": "external_evidence_only",
        "output_paths": list(OUTPUT_PATHS),
        "pure_in_memory": True,
    }
)


class ClosureEvidenceMatrixError(RuntimeError):
    """Raised when E10 receives incomplete or contradictory evidence."""


def _plain_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ClosureEvidenceMatrixError("software evidence contains a non-JSON value")


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _plain_json(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def component_contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_canonical_json_bytes(COMPONENT_CONTRACT)))


def component_contract_sha256() -> str:
    return hashlib.sha256(_canonical_json_bytes(COMPONENT_CONTRACT)).hexdigest()


def _boundary(authority: Mapping[str, Any], contract: Mapping[str, Any]) -> str:
    try:
        return validate_component_boundary(
            authority,
            contract,
            component_id=COMPONENT_ID,
            stage_id=STAGE_ID,
            output_paths=OUTPUT_PATHS,
        )
    except ClosureAnfisAblationError as exc:
        raise ClosureEvidenceMatrixError(str(exc)) from exc


def _require_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ClosureEvidenceMatrixError(f"{context} must be a mapping")
    return cast(Mapping[str, Any], value)


def _validate_junit(value: Any) -> tuple[str | bytes, dict[str, int]]:
    if not isinstance(value, (str, bytes)):
        raise ClosureEvidenceMatrixError("public_tests_xml must be UTF-8 XML")
    try:
        raw = value.encode("utf-8") if isinstance(value, str) else value
        if len(raw) > 10 * 1024 * 1024 or any(
            marker in raw.upper() for marker in (b"<!DOCTYPE", b"<!ENTITY")
        ):
            raise ClosureEvidenceMatrixError(
                "public_tests_xml is oversized or declares an entity"
            )
        root = ET.fromstring(raw)
    except (UnicodeEncodeError, ET.ParseError) as exc:
        raise ClosureEvidenceMatrixError("public_tests_xml is invalid") from exc
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if root.tag not in {"testsuite", "testsuites"} or not suites:
        raise ClosureEvidenceMatrixError("public_tests_xml is not JUnit")
    totals = {name: 0 for name in ("tests", "failures", "errors", "skipped")}
    for suite in suites:
        for name in totals:
            raw_value = suite.attrib.get(name, "0")
            try:
                parsed = int(raw_value)
            except ValueError as exc:
                raise ClosureEvidenceMatrixError("JUnit counters are not integers") from exc
            if parsed < 0:
                raise ClosureEvidenceMatrixError("JUnit counters must be nonnegative")
            totals[name] += parsed
    if totals["tests"] <= 0 or totals["failures"] != 0 or totals["errors"] != 0:
        raise ClosureEvidenceMatrixError("public suite has failures, errors, or no tests")
    return value, totals


def _markdown_from_record(title: str, value: Any) -> tuple[str, Mapping[str, Any]]:
    record = _require_mapping(value, context=title)
    markdown = record.get("markdown")
    if not isinstance(markdown, str) or not markdown.endswith("\n"):
        raise ClosureEvidenceMatrixError(f"{title} must contain newline-terminated markdown")
    return markdown, record


def _validate_test_report(
    value: Any, *, junit_totals: Mapping[str, int]
) -> tuple[str, Mapping[str, Any]]:
    markdown, record = _markdown_from_record("test_report", value)
    required = {
        "status",
        "test_count",
        "failure_count",
        "error_count",
        "skipped_count",
        "critical_skips_justified",
        "markdown",
    }
    if set(record) != required:
        raise ClosureEvidenceMatrixError("test_report keys are not exact")
    expected = {
        "status": "passed",
        "test_count": junit_totals["tests"],
        "failure_count": 0,
        "error_count": 0,
        "skipped_count": junit_totals["skipped"],
    }
    for key, wanted in expected.items():
        if type(record.get(key)) is not type(wanted) or record.get(key) != wanted:
            raise ClosureEvidenceMatrixError(f"test_report field drifted: {key}")
    justified = record.get("critical_skips_justified")
    if type(justified) is not bool:
        raise ClosureEvidenceMatrixError("critical skip justification must be boolean")
    if junit_totals["skipped"] and not justified:
        raise ClosureEvidenceMatrixError("public suite contains unjustified skips")
    return markdown, record


def _validate_openapi(value: Any) -> Mapping[str, Any]:
    document = _require_mapping(value, context="openapi")
    version = document.get("openapi")
    paths = document.get("paths")
    if not isinstance(version, str) or not version.startswith("3."):
        raise ClosureEvidenceMatrixError("OpenAPI version is not 3.x")
    if not isinstance(paths, Mapping) or not paths:
        raise ClosureEvidenceMatrixError("OpenAPI paths are absent")
    _canonical_json_bytes(document)
    return document


def _validate_contract_report(value: Any) -> tuple[str, Mapping[str, Any]]:
    markdown, record = _markdown_from_record("openapi_contract_report", value)
    if set(record) != {"status", "valid", "markdown"}:
        raise ClosureEvidenceMatrixError("openapi_contract_report keys are not exact")
    if record.get("status") != "passed" or record.get("valid") is not True:
        raise ClosureEvidenceMatrixError("OpenAPI contract validation did not pass")
    return markdown, record


def _validate_e2e(value: Any) -> tuple[str, Mapping[str, Any]]:
    markdown, record = _markdown_from_record("end_to_end_report", value)
    if set(record) != {"status", "workflow_successful", "markdown"}:
        raise ClosureEvidenceMatrixError("end_to_end_report keys are not exact")
    if record.get("status") != "passed" or record.get("workflow_successful") is not True:
        raise ClosureEvidenceMatrixError("end-to-end workflow did not pass")
    return markdown, record


def _validate_environment(value: Any) -> Mapping[str, Any]:
    environment = _require_mapping(value, context="environment")
    required = {"python", "platform", "repository_commit", "dependency_lock_sha256"}
    if not required.issubset(environment):
        raise ClosureEvidenceMatrixError("environment identity is incomplete")
    for key in required:
        if not isinstance(environment[key], str) or not environment[key]:
            raise ClosureEvidenceMatrixError(f"environment field is absent: {key}")
    _canonical_json_bytes(environment)
    return environment


def _validate_stage_results(value: Any) -> pd.DataFrame:
    stage_results = _require_mapping(value, context="stage_results")
    rows: list[dict[str, Any]] = []
    observed_components: set[str] = set()
    observed_stages: set[str] = set()
    for component_key, raw in stage_results.items():
        if component_key not in PRIOR_STAGES:
            raise ClosureEvidenceMatrixError("stage_results keys must be strings")
        result = _require_mapping(raw, context=f"stage result {component_key}")
        required = {
            "component_id",
            "stage_id",
            "status",
            "artifacts",
            "tables",
            "diagnostics",
            "outcome_paths_opened",
            "writes_performed",
        }
        if set(result) != required:
            raise ClosureEvidenceMatrixError(f"stage result is not closed: {component_key}")
        stage_id = result.get("stage_id")
        component_id = result.get("component_id")
        if (
            not isinstance(component_id, str)
            or component_key != stage_id
            or PRIOR_COMPONENTS.get(component_id) != stage_id
            or component_id in observed_components
        ):
            raise ClosureEvidenceMatrixError(
                "prior component/stage identity is missing, duplicated, or drifted"
            )
        status = result.get("status")
        if status not in {"completed", "completed_unavailable"}:
            raise ClosureEvidenceMatrixError(f"prior stage is not terminal: {stage_id}")
        if result.get("outcome_paths_opened") is not True:
            raise ClosureEvidenceMatrixError(f"prior stage did not declare outcome access: {stage_id}")
        if result.get("writes_performed") is not False:
            raise ClosureEvidenceMatrixError(f"prior component performed a write: {stage_id}")
        artifacts = _require_mapping(result.get("artifacts"), context=f"{stage_id} artifacts")
        tables = _require_mapping(result.get("tables"), context=f"{stage_id} tables")
        diagnostics = _require_mapping(
            result.get("diagnostics"), context=f"{stage_id} diagnostics"
        )
        component_rows: list[dict[str, Any]] = []
        if component_id == "E4_composite":
            component_rows = _validate_e4_composite(
                status=status,
                artifacts=artifacts,
                tables=tables,
                diagnostics=diagnostics,
            )
        observed_components.add(component_id)
        observed_stages.add(cast(str, stage_id))
        rows.append(
            {
                "stage_id": stage_id,
                "component_id": result.get("component_id"),
                "status": status,
                "artifact_count": len(artifacts),
                "table_count": len(tables),
                "writes_performed": False,
            }
        )
        rows.extend(component_rows)
    if set(stage_results) != set(PRIOR_STAGES) or observed_components != set(
        PRIOR_COMPONENTS
    ) or observed_stages != set(PRIOR_STAGES):
        missing = sorted(set(PRIOR_COMPONENTS).difference(observed_components))
        raise ClosureEvidenceMatrixError(
            f"stage_results lacks an exact E1-E9 component: {missing}"
        )
    return pd.DataFrame(rows).sort_values(
        ["stage_id", "component_id"],
        key=lambda col: (
            col.str[1:].astype(int) if col.name == "stage_id" else col
        ),
        kind="mergesort",
    )


def _validate_e4_composite(
    *,
    status: Any,
    artifacts: Mapping[str, Any],
    tables: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw_summaries = diagnostics.get("component_results")
    if not isinstance(raw_summaries, list) or len(raw_summaries) != 2:
        raise ClosureEvidenceMatrixError(
            "E4 composite diagnostics lacks ordered component_results exact2"
        )
    expected_ids = ("E4_reference_targets", "E4_trophic_evaluation")
    summaries: list[dict[str, Any]] = []
    union_artifacts: set[str] = set()
    union_tables: set[str] = set()
    for index, raw in enumerate(raw_summaries):
        summary = _require_mapping(raw, context=f"E4 component summary {index}")
        if set(summary) != {
            "component_id",
            "status",
            "artifact_paths",
            "table_names",
        }:
            raise ClosureEvidenceMatrixError("E4 component summary is not closed")
        component_id = summary.get("component_id")
        component_status = summary.get("status")
        if component_id != expected_ids[index] or component_status not in {
            "completed",
            "completed_unavailable",
        }:
            raise ClosureEvidenceMatrixError(
                "E4 component summary identity/status drifted"
            )
        artifact_paths = summary.get("artifact_paths")
        table_names = summary.get("table_names")
        if (
            not isinstance(artifact_paths, list)
            or not isinstance(table_names, list)
            or not all(type(path) is str and path for path in artifact_paths)
            or not all(type(name) is str and name for name in table_names)
            or len(set(artifact_paths)) != len(artifact_paths)
            or len(set(table_names)) != len(table_names)
        ):
            raise ClosureEvidenceMatrixError("E4 component summary names drifted")
        if union_artifacts.intersection(artifact_paths) or union_tables.intersection(
            table_names
        ):
            raise ClosureEvidenceMatrixError("E4 composite payloads clobber each other")
        union_artifacts.update(artifact_paths)
        union_tables.update(table_names)
        summaries.append(
            {
                "stage_id": "E4",
                "component_id": component_id,
                "status": component_status,
                "artifact_count": len(artifact_paths),
                "table_count": len(table_names),
                "writes_performed": False,
            }
        )
    if union_artifacts != set(artifacts) or union_tables != set(tables):
        raise ClosureEvidenceMatrixError(
            "E4 composite top-level payload union does not match summaries"
        )
    expected_status = (
        "completed_unavailable"
        if any(row["status"] == "completed_unavailable" for row in summaries)
        else "completed"
    )
    if status != expected_status:
        raise ClosureEvidenceMatrixError("E4 composite terminal status drifted")
    return summaries


def preflight_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    if not isinstance(repo_root, Path):
        raise ClosureEvidenceMatrixError("E10 repository root is not a Path")
    del repo_root
    contract_sha256 = _boundary(authority, sealed_batch_contract)
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "ready",
        "contract_sha256": contract_sha256,
        "outcome_paths_opened": False,
        "writes_performed": False,
    }


def execute_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    batch_context: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    preflight_closure_sealed_batch_component(authority, sealed_batch_contract, repo_root)
    try:
        context = validate_batch_context(batch_context)
    except ClosureAnfisAblationError as exc:
        raise ClosureEvidenceMatrixError(str(exc)) from exc
    availability = cast(Mapping[str, Any], context["model_availability"])
    sealed_availability = sealed_batch_contract.get("model_availability")
    if not isinstance(sealed_availability, Mapping) or dict(availability) != dict(
        sealed_availability
    ):
        raise ClosureEvidenceMatrixError("model availability is not batch-bound")
    evidence = cast(dict[str, Any], context["software_evidence"])
    if set(evidence) != SOFTWARE_EVIDENCE_KEYS:
        raise ClosureEvidenceMatrixError("software_evidence keys are not exact")
    junit, totals = _validate_junit(evidence["public_tests_xml"])
    test_markdown, test_record = _validate_test_report(
        evidence["test_report"], junit_totals=totals
    )
    openapi = _validate_openapi(evidence["openapi"])
    contract_markdown, contract_record = _validate_contract_report(
        evidence["openapi_contract_report"]
    )
    e2e_markdown, e2e_record = _validate_e2e(evidence["end_to_end_report"])
    environment = _validate_environment(evidence["environment"])
    stage_matrix = _validate_stage_results(context["stage_results"])
    artifacts = {
        OUTPUT_PATHS[0]: artifact_envelope("xml", junit),
        OUTPUT_PATHS[1]: artifact_envelope("markdown", test_markdown),
        OUTPUT_PATHS[2]: artifact_envelope("json", dict(openapi)),
        OUTPUT_PATHS[3]: artifact_envelope("markdown", contract_markdown),
        OUTPUT_PATHS[4]: artifact_envelope("markdown", e2e_markdown),
        OUTPUT_PATHS[5]: artifact_envelope("json", dict(environment), manifest_last=True),
    }
    evidence_digest = hashlib.sha256(
        _canonical_json_bytes(
            {
                "test_report": test_record,
                "openapi": openapi,
                "openapi_contract_report": contract_record,
                "end_to_end_report": e2e_record,
                "environment": environment,
                "junit_sha256": hashlib.sha256(
                    junit.encode("utf-8") if isinstance(junit, str) else junit
                ).hexdigest(),
            }
        )
    ).hexdigest()
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "completed",
        "artifacts": artifacts,
        "tables": {"e10_stage_evidence": stage_matrix.copy(deep=True)},
        "diagnostics": {
            "component_contract_sha256": component_contract_sha256(),
            "evidence_sha256": evidence_digest,
            "prior_stage_count": int(stage_matrix["stage_id"].nunique()),
            "prior_component_count": len(stage_matrix) - 1,
            "stage_evidence_row_count": len(stage_matrix),
            "public_test_count": totals["tests"],
            "public_skip_count": totals["skipped"],
            "openapi_path_count": len(cast(Mapping[str, Any], openapi["paths"])),
            "operational_commands_run": 0,
            "git_operations_run": 0,
            "dvc_operations_run": 0,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }
