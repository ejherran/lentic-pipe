from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.experiments.closure_v2 import build_certification as certification


def _junit(
    path: Path,
    *,
    passed: int,
    failed: int = 0,
    skipped: int = 0,
    namespace: str = "tests",
) -> None:
    suite = ET.Element("testsuite")
    for index in range(passed):
        ET.SubElement(suite, "testcase", {"classname": f"{namespace}.ok", "name": f"test_{index}"})
    for index in range(failed):
        case = ET.SubElement(suite, "testcase", {"classname": f"{namespace}.failed", "name": f"test_{index}"})
        ET.SubElement(case, "failure")
    for index in range(skipped):
        case = ET.SubElement(suite, "testcase", {"classname": f"{namespace}.skipped", "name": f"test_{index}"})
        ET.SubElement(case, "skipped")
    path.write_bytes(ET.tostring(suite, encoding="utf-8", xml_declaration=True))


def test_output_universe_is_exact_and_manifest_last() -> None:
    assert len(certification.OUTPUTS) == 8
    assert certification.OUTPUTS[-1] == certification.MANIFEST
    assert len(set(certification.OUTPUTS)) == 8


def test_amendment_keeps_three_certification_predicates_separate() -> None:
    text = certification.AMENDMENT_PATH.read_text(encoding="utf-8")
    assert "closure_v2_scope_certified = true" in text
    assert "global_repository_certified = false" in text
    assert "efficacy_certified = false" in text


def test_junit_parser_retains_failures_and_skips(tmp_path: Path) -> None:
    path = tmp_path / "suite.xml"
    _junit(path, passed=3, failed=2, skipped=1)
    result = certification.parse_junit(path)
    assert result["tests"] == 6
    assert result["passed"] == 3
    assert result["failed"] == 2
    assert result["skipped"] == 1
    assert len(result["failed_test_ids"]) == 2


def test_effective_junit_is_deterministic_and_rejects_failures(tmp_path: Path) -> None:
    v2 = tmp_path / "v2.xml"
    e2e = tmp_path / "e2e.xml"
    _junit(v2, passed=2)
    _junit(e2e, passed=1, namespace="e2e")
    first = certification.canonical_public_junit(v2, e2e)
    second = certification.canonical_public_junit(v2, e2e)
    assert first == second
    assert certification.parse_junit_bytes(first) == {"tests": 3, "failed": 0, "skipped": 0}
    _junit(e2e, passed=0, failed=1)
    with pytest.raises(certification.CertificationError, match="contains a failure"):
        certification.canonical_public_junit(v2, e2e)


def test_global_publication_diagnostic_is_exact(tmp_path: Path) -> None:
    path = tmp_path / "publication.txt"
    lines = [
        "Checking tracked files before publication...",
        "",
        "Local absolute paths found in versionable files:",
        "a", "b", "c", "",
        "Non-English repository text found in versionable files:",
        *(f"line-{index}" for index in range(376)),
        "", "Publication readiness check failed.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = certification.parse_publication_diagnostic(path)
    assert result["local_absolute_paths"] == 3
    assert result["non_english_text"] == 376


def test_scoped_scan_rejects_paths_credentials_and_private_urls() -> None:
    assert certification.scan_payloads([(Path("safe.txt"), b"public deterministic text")])["status"] == "passed"
    for payload in (
        b"/home/" + b"zero/repository",
        b'{"type":"' + b'service_account"}',
        b"https://" + b"private.example/data",
    ):
        with pytest.raises(certification.CertificationError, match="scoped publication scan"):
            certification.scan_payloads([(Path("bad.txt"), payload)])


def test_openapi_contract_is_valid_and_stable() -> None:
    payload, summary = certification.build_openapi()
    value = json.loads(payload)
    assert value["openapi"] == "3.1.0"
    assert summary["status"] == "passed"
    assert summary["path_count"] == 69
    assert summary["operation_count"] == 83
    assert summary["unique_operation_id_count"] == 83


def test_restoration_receipt_requires_exact_pointer_universe() -> None:
    records = []
    for pointer in certification.V2_POINTERS:
        records.append({
            "pointer": pointer,
            "md5": "0" * 32 + (".dir" if pointer == "models.dvc" else ""),
            "size": 1,
        })
    value = {
        "schema_version": "closure_v2_p18_restoration_receipt_v1",
        "clean_clone": True,
        "empty_cache": True,
        "pull_exit_zero": True,
        "all_pointer_hashes_and_sizes_matched": True,
        "parquet_opened_in_python": False,
        "temporary_credentials_removed": True,
        "pointers": records,
    }
    assert certification._validate_restoration_receipt(value)["clean_clone"] is True
    value["pointers"] = records[:-1]
    with pytest.raises(certification.CertificationError, match="universe or order"):
        certification._validate_restoration_receipt(value)


def test_reports_do_not_conflate_scope_or_efficacy() -> None:
    evidence = {
        "global_workspace_diagnostic": {"passed": 3352, "failed": 83, "skipped": 1},
        "historical_curated_diagnostic": {"passed": 336, "failed": 1, "skipped": 10},
        "closure_v2_suite": {"passed": 101},
        "restoration": {"pointers": [{}] * 11},
    }
    final = certification._final_report(
        evidence,
        {"openapi_version": "3.1.0", "path_count": 69, "operation_count": 83},
    ).decode("utf-8")
    assert "global historical repository is not certified" in final
    assert "efficacy is not certified" in final
    assert "83 failed" in final


def test_environment_has_no_timestamp_or_absolute_path() -> None:
    value = json.loads(certification._environment())
    assert value["timestamps_recorded"] is False
    assert value["absolute_paths_recorded"] is False
    assert not any(str(item).startswith("/") for item in value.values())
