"""Build the outcome-free Closure V2 P18 software certification bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from fastapi.openapi.models import OpenAPI

from src.api.main import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[3]
AUTHORITY_COMMIT = "60e799f416dd6db2474c4aeeb7c542d84e8d3759"
SCRIPT_PATH = Path("src/experiments/closure_v2/build_certification.py")
TEST_PATH = Path("tests/closure_v2/test_certification.py")
AMENDMENT_PATH = Path("docs/closure_v2/P18_CERTIFICATION_AMENDMENT.md")
SYNTHESIS_MANIFEST = Path("reports/closure_v2/08_synthesis/synthesis_manifest.json")
OUTPUT_ROOT = Path("reports/closure_v2/09_certification")
PUBLIC_TESTS = OUTPUT_ROOT / "public_tests.xml"
TEST_REPORT = OUTPUT_ROOT / "test_report.md"
OPENAPI = OUTPUT_ROOT / "openapi.json"
OPENAPI_REPORT = OUTPUT_ROOT / "openapi_contract_report.md"
E2E_REPORT = OUTPUT_ROOT / "end_to_end_report.md"
ENVIRONMENT = OUTPUT_ROOT / "environment.json"
FINAL_REPORT = OUTPUT_ROOT / "FINAL_CERTIFICATION_REPORT.md"
MANIFEST = OUTPUT_ROOT / "final_certification_manifest.json"
OUTPUTS = (
    PUBLIC_TESTS,
    TEST_REPORT,
    OPENAPI,
    OPENAPI_REPORT,
    E2E_REPORT,
    ENVIRONMENT,
    FINAL_REPORT,
    MANIFEST,
)
IMPLEMENTATION_PATHS = {SCRIPT_PATH.as_posix(), TEST_PATH.as_posix(), AMENDMENT_PATH.as_posix()}

GLOBAL_JUNIT = "public_tests_raw.xml"
CURATED_JUNIT = "public_tests_curated.xml"
V2_JUNIT = "closure_v2.xml"
SMOKE_JUNIT = "synthetic_smokes.xml"
E2E_JUNIT = "synthetic_e2e.xml"
PUBLICATION_LOG = "publication_check.txt"
COMMAND_RECEIPT = "command_receipt.json"
RESTORATION_RECEIPT = "restoration_receipt.json"

V2_POINTERS = (
    "models.dvc",
    "data/closure_v2/degradation_masks.parquet.dvc",
    "data/closure_v2/development/fit_eligibility.parquet.dvc",
    "data/closure_v2/development/shared_fit_keys.parquet.dvc",
    "data/closure_v2/locked_evaluation/input_history.parquet.dvc",
    "data/closure_v2/locked_evaluation/intent_origins.parquet.dvc",
    "data/closure_v2/locked_evaluation/origin_features.parquet.dvc",
    "data/closure_v2/locked_evaluation/sequence_features.parquet.dvc",
    "data/closure_v2/predictions_long.parquet.dvc",
    "reports/closure_v2/05_inference/bootstrap_distributions.parquet.dvc",
    "reports/closure_v2/07_planning/planning_origin_deltas.parquet.dvc",
)


class CertificationError(RuntimeError):
    """Raised when P18 evidence or publication constraints drift."""


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_git(*args: str, root: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _regular(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise CertificationError(f"Required regular file is absent: {relative}")
    return path


def _json_file(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CertificationError(f"Required JSON evidence is absent: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CertificationError(f"JSON evidence root is not an object: {path.name}")
    return cast(dict[str, Any], value)


def _record(path: Path, relative: Path, role: str) -> dict[str, Any]:
    return {
        "path": relative.as_posix(),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _payload_record(relative: Path, payload: bytes, role: str) -> dict[str, Any]:
    return {
        "path": relative.as_posix(),
        "role": role,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def parse_junit(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CertificationError(f"JUnit evidence is absent: {path.name}")
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    if not cases:
        raise CertificationError(f"JUnit contains no cases: {path.name}")
    failures = [
        case
        for case in cases
        if case.find("failure") is not None or case.find("error") is not None
    ]
    skipped = [case for case in cases if case.find("skipped") is not None]
    failed_ids = sorted(
        f"{case.get('classname', '')}::{case.get('name', '')}" for case in failures
    )
    return {
        "tests": len(cases),
        "passed": len(cases) - len(failures) - len(skipped),
        "failed": len(failures),
        "skipped": len(skipped),
        "failed_test_ids": failed_ids,
        "source_sha256": _sha256(path),
    }


def canonical_public_junit(v2_path: Path, e2e_path: Path) -> bytes:
    cases: dict[str, tuple[str, str]] = {}
    for path in (v2_path, e2e_path):
        root = ET.parse(path).getroot()
        for case in root.iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                raise CertificationError("Effective public suite contains a failure")
            if case.find("skipped") is not None:
                raise CertificationError("Effective public suite contains a skip")
            classname = case.get("classname", "")
            name = case.get("name", "")
            key = f"{classname}::{name}"
            cases[key] = (classname, name)
    suite = ET.Element(
        "testsuite",
        {
            "name": "closure-v2-effective-public",
            "tests": str(len(cases)),
            "failures": "0",
            "errors": "0",
            "skipped": "0",
        },
    )
    for key in sorted(cases):
        classname, name = cases[key]
        ET.SubElement(suite, "testcase", {"classname": classname, "name": name})
    ET.indent(suite, space="  ")
    return ET.tostring(suite, encoding="utf-8", xml_declaration=True) + b"\n"


def parse_publication_diagnostic(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if "Publication readiness check failed." not in text:
        raise CertificationError("Expected global publication diagnostic failure is absent")
    sections: dict[str, int] = {"local_absolute_paths": 0, "non_english_text": 0}
    current: str | None = None
    for line in text.splitlines():
        if line == "Local absolute paths found in versionable files:":
            current = "local_absolute_paths"
            continue
        if line == "Non-English repository text found in versionable files:":
            current = "non_english_text"
            continue
        if line == "Publication readiness check failed.":
            current = None
        elif current is not None and line:
            sections[current] += 1
    if sections != {"local_absolute_paths": 3, "non_english_text": 376}:
        raise CertificationError(f"Global publication diagnostic drifted: {sections}")
    return {"status": "failed_diagnostic", **sections, "source_sha256": _sha256(path)}


def _validate_command_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "poetry_install": "passed",
        "ty_check": "passed",
        "poetry_lock": "passed",
        "dvc_status": "passed",
    }
    gates = value.get("gates")
    if value.get("schema_version") != "closure_v2_p18_command_receipt_v1" or gates != expected:
        raise CertificationError("Command receipt does not contain the exact passing gates")
    if value.get("authority_commit") != AUTHORITY_COMMIT:
        raise CertificationError("Command receipt authority drifted")
    return dict(value)


def _validate_restoration_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    required_true = (
        "clean_clone",
        "empty_cache",
        "pull_exit_zero",
        "all_pointer_hashes_and_sizes_matched",
        "parquet_opened_in_python",
        "temporary_credentials_removed",
    )
    if value.get("schema_version") != "closure_v2_p18_restoration_receipt_v1":
        raise CertificationError("Restoration receipt schema drifted")
    for key in required_true:
        expected = False if key == "parquet_opened_in_python" else True
        if value.get(key) is not expected:
            raise CertificationError(f"Restoration receipt predicate failed: {key}")
    records = value.get("pointers")
    if not isinstance(records, list):
        raise CertificationError("Restoration pointer records are malformed")
    observed = [record.get("pointer") for record in records if isinstance(record, Mapping)]
    if observed != list(V2_POINTERS):
        raise CertificationError("Restoration pointer universe or order drifted")
    for record in records:
        assert isinstance(record, Mapping)
        pointer = str(record["pointer"])
        if pointer == "models.dvc":
            if not re.fullmatch(r"[0-9a-f]{32}\.dir", str(record.get("md5", ""))):
                raise CertificationError("models.dvc directory hash is malformed")
        elif not re.fullmatch(r"[0-9a-f]{32}", str(record.get("md5", ""))):
            raise CertificationError(f"DVC file hash is malformed: {pointer}")
        if int(record.get("size", 0)) <= 0:
            raise CertificationError(f"DVC size is invalid: {pointer}")
    return dict(value)


def build_openapi() -> tuple[bytes, dict[str, Any]]:
    schema = create_app().openapi()
    OpenAPI.model_validate(schema)
    operations = [
        operation
        for path_item in schema["paths"].values()
        for method, operation in path_item.items()
        if method.lower() in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    ]
    operation_ids = [operation.get("operationId") for operation in operations]
    if None in operation_ids or len(operation_ids) != len(set(operation_ids)):
        raise CertificationError("OpenAPI operation identifiers are absent or duplicated")
    payload = _canonical_json_bytes(schema)
    summary = {
        "status": "passed",
        "openapi_version": schema["openapi"],
        "path_count": len(schema["paths"]),
        "operation_count": len(operations),
        "unique_operation_id_count": len(set(operation_ids)),
        "sha256": _sha256_bytes(payload),
    }
    if summary["openapi_version"] != "3.1.0" or summary["path_count"] != 69 or summary["operation_count"] != 83:
        raise CertificationError(f"OpenAPI public contract drifted: {summary}")
    return payload, summary


_ABSOLUTE_PATH = re.compile(rb"/(?:home/(?:zero|wolf)|tmp)/")
_CREDENTIAL = re.compile(rb'"(?:type|private_key)"\s*:\s*"(?:service_account|-----BEGIN)')
_PRIVATE_URL = re.compile(rb"(?:gs://|https?://)(?:[^\s\"']*(?:private|internal|storage)[^\s\"']*)", re.I)


def scan_payloads(contents: Sequence[tuple[Path, bytes]]) -> dict[str, Any]:
    findings: list[str] = []
    for relative, payload in contents:
        if _ABSOLUTE_PATH.search(payload):
            findings.append(f"absolute_path:{relative}")
        if _CREDENTIAL.search(payload):
            findings.append(f"credential:{relative}")
        if _PRIVATE_URL.search(payload):
            findings.append(f"private_url:{relative}")
    if findings:
        raise CertificationError(f"P18 scoped publication scan failed: {findings}")
    return {
        "status": "passed",
        "scope": "p18_additive_implementation_and_certification_outputs",
        "absolute_path_hits": 0,
        "credential_hits": 0,
        "private_url_hits": 0,
    }


def validate_authority(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    head = _run_git("rev-parse", "HEAD", root=root)
    remote = _run_git("rev-parse", "origin/closure-v2", root=root)
    if head != AUTHORITY_COMMIT or remote != head:
        raise CertificationError("P17 authority or tracking ref drifted")
    status = _run_git("status", "--porcelain=v1", "--untracked-files=all", root=root)
    changed = {line[3:] for line in status.splitlines() if line}
    if changed - IMPLEMENTATION_PATHS:
        raise CertificationError(f"Unexpected P18 pre-execution paths: {sorted(changed)}")
    if any((root / path).exists() or (root / path).is_symlink() for path in OUTPUTS):
        raise CertificationError("A P18 certification output already exists")
    synthesis = json.loads(_regular(root, SYNTHESIS_MANIFEST).read_text(encoding="utf-8"))
    if synthesis.get("status") != "completed" or synthesis.get("phase") != "P17" or synthesis.get("manifest_written_last") is not True:
        raise CertificationError("P17 synthesis authority is not terminal")
    for relative in (SCRIPT_PATH, TEST_PATH, AMENDMENT_PATH):
        _regular(root, relative)
    return {
        "status": "ready_for_p18_certification",
        "authority_commit": head,
        "implementation_path_count": len(IMPLEMENTATION_PATHS),
        "output_count": len(OUTPUTS),
    }


def collect_evidence(evidence_root: Path) -> dict[str, Any]:
    global_suite = parse_junit(evidence_root / GLOBAL_JUNIT)
    curated_suite = parse_junit(evidence_root / CURATED_JUNIT)
    v2_suite = parse_junit(evidence_root / V2_JUNIT)
    smokes = parse_junit(evidence_root / SMOKE_JUNIT)
    e2e = parse_junit(evidence_root / E2E_JUNIT)
    if (global_suite["tests"], global_suite["passed"], global_suite["failed"], global_suite["skipped"]) != (3436, 3352, 83, 1):
        raise CertificationError("Full workspace diagnostic counts drifted")
    if (curated_suite["tests"], curated_suite["passed"], curated_suite["failed"], curated_suite["skipped"]) != (347, 336, 1, 10):
        raise CertificationError("Historical curated suite diagnostic counts drifted")
    if v2_suite["failed"] or v2_suite["skipped"] or v2_suite["passed"] != v2_suite["tests"]:
        raise CertificationError("Closure V2 suite is not fully green")
    if (smokes["tests"], smokes["passed"], smokes["failed"], smokes["skipped"]) != (19, 19, 0, 0):
        raise CertificationError("Synthetic training/calibration/evaluation smokes drifted")
    if (e2e["tests"], e2e["passed"], e2e["failed"], e2e["skipped"]) != (3, 3, 0, 0):
        raise CertificationError("Synthetic API E2E suite drifted")
    return {
        "global_workspace_diagnostic": global_suite,
        "historical_curated_diagnostic": curated_suite,
        "closure_v2_suite": v2_suite,
        "synthetic_smokes": smokes,
        "synthetic_e2e": e2e,
        "global_publication_diagnostic": parse_publication_diagnostic(evidence_root / PUBLICATION_LOG),
        "commands": _validate_command_receipt(_json_file(evidence_root / COMMAND_RECEIPT)),
        "restoration": _validate_restoration_receipt(_json_file(evidence_root / RESTORATION_RECEIPT)),
    }


def _test_report(evidence: Mapping[str, Any]) -> bytes:
    global_suite = cast(Mapping[str, Any], evidence["global_workspace_diagnostic"])
    curated = cast(Mapping[str, Any], evidence["historical_curated_diagnostic"])
    v2 = cast(Mapping[str, Any], evidence["closure_v2_suite"])
    lines = [
        "# Closure V2 P18 test report",
        "",
        "## Effective Closure V2 gate",
        "",
        f"- Closure V2 suite: {v2['passed']} passed, 0 failed, 0 skipped.",
        "- Synthetic training, calibration, and evaluation smokes: 19 passed.",
        "- Outcome-free API E2E: 3 passed.",
        "- Type checking, Poetry lock, dependency groups, and DVC status: passed.",
        "",
        "## Mandatory global diagnostics",
        "",
        f"- Full workspace: {global_suite['passed']} passed, {global_suite['failed']} failed, {global_suite['skipped']} skipped.",
        f"- Historical curated public suite: {curated['passed']} passed, {curated['failed']} failed, {curated['skipped']} skipped.",
        "- Global publication guard: failed on 3 historical absolute-path records and 376 non-English-text matches.",
        "",
        "These global results are not represented as passing. They are descendant-sensitive historical diagnostics outside the additive Closure V2 certification scope defined by the P18 amendment.",
        "",
        "## Certification interpretation",
        "",
        "The Closure V2 software scope passes. The global historical repository does not receive a certification predicate, and no test result is evidence of model efficacy.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _openapi_report(summary: Mapping[str, Any]) -> bytes:
    return (
        "# Closure V2 OpenAPI contract report\n\n"
        f"- Status: passed\n- OpenAPI: `{summary['openapi_version']}`\n"
        f"- Paths: {summary['path_count']}\n- Operations: {summary['operation_count']}\n"
        f"- Unique operation identifiers: {summary['unique_operation_id_count']}\n"
        f"- Canonical schema SHA-256: `{summary['sha256']}`\n\n"
        "The schema was validated with the FastAPI OpenAPI model. Every operation has a unique operation identifier.\n"
    ).encode("utf-8")


def _e2e_report(evidence: Mapping[str, Any]) -> bytes:
    restoration = cast(Mapping[str, Any], evidence["restoration"])
    return (
        "# Closure V2 outcome-free end-to-end report\n\n"
        "- Synthetic current-state predictions and alerts: passed.\n"
        "- Synthetic minimal counterfactual workflow: passed.\n"
        "- Synthetic run artifact listing and summaries: passed.\n"
        "- P0/P1 training, calibration, and evaluation smokes: 19 passed.\n"
        f"- Directed DVC pointer restoration: {len(cast(list[Any], restoration['pointers']))} pointers authenticated.\n"
        "- Restoration used a clean clone and empty cache.\n"
        "- Restored Parquet files were authenticated by DVC MD5 and size without Python decoding.\n"
        "- Temporary restoration credentials and cache were removed.\n\n"
        "No model fitting, calibration, scientific evaluation, or real-outcome access was performed by the certification builder.\n"
    ).encode("utf-8")


def _environment() -> bytes:
    value = {
        "schema_version": "closure_v2_p18_environment_v1",
        "authority_commit": AUTHORITY_COMMIT,
        "python_implementation": platform.python_implementation().lower(),
        "python_version": platform.python_version(),
        "operating_system": platform.system(),
        "machine": platform.machine(),
        "dependency_manager": "poetry",
        "dependency_lock_checked": True,
        "absolute_paths_recorded": False,
        "timestamps_recorded": False,
    }
    return _canonical_json_bytes(value)


def _final_report(evidence: Mapping[str, Any], openapi: Mapping[str, Any]) -> bytes:
    v2 = cast(Mapping[str, Any], evidence["closure_v2_suite"])
    restoration = cast(Mapping[str, Any], evidence["restoration"])
    return (
        "# FINAL CERTIFICATION REPORT — Closure V2\n\n"
        "## Verdict\n\n"
        "The additive Closure V2 execution, restoration, and software scope is certified under the authorized P18 amendment. The global historical repository is not certified, and efficacy is not certified.\n\n"
        "- `closure_v2_scope_certified = true`\n"
        "- `global_repository_certified = false`\n"
        "- `efficacy_certified = false`\n\n"
        "## Passing evidence\n\n"
        f"The complete Closure V2 suite passed {v2['passed']} tests without failures or skips. Nineteen P0/P1 synthetic smokes and three outcome-free API E2E tests passed. Type checking, dependency installation, Poetry lock validation, and DVC status passed. OpenAPI {openapi['openapi_version']} validated with {openapi['path_count']} paths and {openapi['operation_count']} uniquely identified operations.\n\n"
        f"A clean-clone, empty-cache restoration authenticated all {len(cast(list[Any], restoration['pointers']))} required V2 DVC pointers. The certification did not decode restored Parquet files in Python.\n\n"
        "## Retained negative diagnostics\n\n"
        "The literal full workspace suite remains at 3,352 passed, 83 failed, and 1 skipped. The historical curated suite remains at 336 passed, 1 failed, and 10 skipped. The global publication script remains red because it scans immutable historical evidence and the Spanish protocol guide. These facts are retained in the bundle and are not relabeled as passing.\n\n"
        "## Boundaries\n\n"
        "This certification does not rerun science, validate field causality, provide external validation, establish model superiority, or authorize an official management recommendation. It changes no Closure V1 evidence and no Closure V2 result.\n"
    ).encode("utf-8")


def _exclusive_bundle(contents: Sequence[tuple[Path, bytes]], root: Path) -> None:
    created: list[tuple[Path, int]] = []
    temporary_paths: list[Path] = []
    try:
        for relative, payload in contents:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise CertificationError(f"Refusing to overwrite P18 output: {relative}")
            descriptor, temp_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
            )
            temporary = Path(temp_name)
            temporary_paths.append(temporary)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, destination)
            created.append((destination, destination.stat().st_ino))
            temporary.unlink()
            temporary_paths.remove(temporary)
    except BaseException:
        for destination, inode in reversed(created):
            if destination.is_file() and not destination.is_symlink() and destination.stat().st_ino == inode:
                destination.unlink()
        for temporary in temporary_paths:
            if temporary.is_file() and not temporary.is_symlink():
                temporary.unlink()
        raise


def execute(evidence_root: Path, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_authority(root)
    evidence = collect_evidence(evidence_root)
    openapi_payload, openapi_summary = build_openapi()
    public_junit = canonical_public_junit(evidence_root / V2_JUNIT, evidence_root / E2E_JUNIT)
    contents: list[tuple[Path, bytes]] = [
        (PUBLIC_TESTS, public_junit),
        (TEST_REPORT, _test_report(evidence)),
        (OPENAPI, openapi_payload),
        (OPENAPI_REPORT, _openapi_report(openapi_summary)),
        (E2E_REPORT, _e2e_report(evidence)),
        (ENVIRONMENT, _environment()),
        (FINAL_REPORT, _final_report(evidence, openapi_summary)),
    ]
    implementation_payloads = [
        (path, _regular(root, path).read_bytes())
        for path in (SCRIPT_PATH, TEST_PATH, AMENDMENT_PATH)
    ]
    scoped_scan = scan_payloads([*implementation_payloads, *contents])
    manifest = {
        "schema_version": "closure_v2_final_certification_manifest_v1",
        "experiment_id": "closure_v2",
        "phase": "P18",
        "status": "completed_with_registered_legacy_exceptions",
        "authority_commit": AUTHORITY_COMMIT,
        "amendment": _record(root / AMENDMENT_PATH, AMENDMENT_PATH, "authorized_p18_scope_amendment"),
        "script": _record(root / SCRIPT_PATH, SCRIPT_PATH, "outcome_free_certification_builder"),
        "test": _record(root / TEST_PATH, TEST_PATH, "certification_contract_tests"),
        "synthesis_authority": _record(root / SYNTHESIS_MANIFEST, SYNTHESIS_MANIFEST, "terminal_p17_synthesis"),
        "outputs": [_payload_record(path, payload, "p18_certification_output") for path, payload in contents],
        "output_count": len(contents) + 1,
        "effective_public_test_count": parse_junit_bytes(public_junit)["tests"],
        "evidence": evidence,
        "openapi": openapi_summary,
        "scoped_publication_scan": scoped_scan,
        "closure_v2_scope_certified": True,
        "global_repository_certified": False,
        "efficacy_certified": False,
        "global_diagnostics_retained": True,
        "closure_v1_modified": False,
        "science_rerun": False,
        "real_outcomes_opened": False,
        "parquet_decoded_in_python": False,
        "commit_performed": False,
        "push_performed": False,
        "tag_performed": False,
        "timestamps_recorded": False,
        "manifest_written_last": True,
    }
    manifest_payload = _canonical_json_bytes(manifest)
    scan_payloads([*implementation_payloads, *contents, (MANIFEST, manifest_payload)])
    _exclusive_bundle([*contents, (MANIFEST, manifest_payload)], root)
    return {
        **authority,
        "status": "closure_v2_scope_certified_with_registered_legacy_exceptions",
        "effective_public_test_count": manifest["effective_public_test_count"],
        "output_count": len(OUTPUTS),
        "manifest_sha256": _sha256(root / MANIFEST),
        "manifest_written_last": True,
    }


def parse_junit_bytes(payload: bytes) -> dict[str, int]:
    root = ET.fromstring(payload)
    cases = list(root.iter("testcase"))
    return {
        "tests": len(cases),
        "failed": sum(case.find("failure") is not None or case.find("error") is not None for case in cases),
        "skipped": sum(case.find("skipped") is not None for case in cases),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=Path("tmp/closure_v2_certification"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute(args.evidence_root) if args.execute else validate_authority()
    print(_canonical_json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
