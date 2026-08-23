from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.experiments.closure_v2 import audit_v1_inputs as audit


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _synthetic_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "closure-v2")
    _git(repo, "config", "user.email", "closure-v2@example.invalid")
    _git(repo, "config", "user.name", "Closure V2 Test")
    for relative, content in (
        ("configs/closure_v1/a.yaml", "a: 1\n"),
        ("docs/closure_v1/A.md", "A\n"),
        ("reports/closure_v1/a.json", "{}\n"),
    ):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_real_repository_v1_authorities_and_inventory_pass() -> None:
    result = audit.audit_repository(audit.PROJECT_ROOT)
    assert result["status"] == "passed"
    assert result["v1_authorities"]["tag_object"] == audit.EXPECTED_TAG_OBJECT
    assert result["v1_authorities"]["peeled_commit"] == audit.EXPECTED_CERTIFICATION_COMMIT
    assert result["inventory_record_count"] == 604
    assert len(result["inventory_digest_sha256"]) == 64
    assert result["protected_v1_changes"] == []
    assert result["parquet_files_opened"] is False
    assert result["dvc_commands_executed"] is False


def test_inventory_is_path_ordered_and_deterministic(tmp_path: Path) -> None:
    repo, commit = _synthetic_repo(tmp_path)
    first, first_digest = audit.build_v1_inventory(repo, commit)
    second, second_digest = audit.build_v1_inventory(repo, commit)
    assert first == second
    assert first_digest == second_digest
    assert [row["path"] for row in first] == sorted(row["path"] for row in first)


def test_protected_v1_change_is_detected(tmp_path: Path) -> None:
    repo, _ = _synthetic_repo(tmp_path)
    target = repo / "docs/closure_v1/A.md"
    target.write_text("changed\n", encoding="utf-8")
    assert audit.protected_v1_changes(repo) == ["docs/closure_v1/A.md"]


def test_v2_change_is_not_reported_as_v1_drift(tmp_path: Path) -> None:
    repo, _ = _synthetic_repo(tmp_path)
    target = repo / "docs/closure_v2/A.md"
    target.parent.mkdir(parents=True)
    target.write_text("new\n", encoding="utf-8")
    assert audit.protected_v1_changes(repo) == []


def test_receipt_path_guard_rejects_undeclared_path(tmp_path: Path) -> None:
    with pytest.raises(audit.V1AuditError, match="Undeclared"):
        audit._assert_receipt_path(tmp_path, Path("reports/closure_v2/not_allowed.json"))


def test_receipt_payloads_are_byte_deterministic() -> None:
    result = audit.audit_repository(audit.PROJECT_ROOT)
    first = audit.receipt_payloads(result, audit.PROJECT_ROOT)
    second = audit.receipt_payloads(result, audit.PROJECT_ROOT)
    assert first == second
    assert set(first) == {"entry", "reference", "state", "log"}
