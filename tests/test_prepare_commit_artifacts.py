from __future__ import annotations

from pathlib import Path

from src.data.prepare_commit_artifacts import (
    DvcArtifact,
    declared_artifacts_missing_pointers,
    dvc_pointer_path,
    has_failing_findings,
    reproducibility_checks,
    sha256_file,
    validate_experiment_manifests,
    validate_freeze_freshness,
)


def test_declared_artifacts_missing_pointers_selects_existing_declared_targets(tmp_path: Path) -> None:
    existing = tmp_path / "data" / "pipe_grud" / "rollouts.parquet"
    existing.parent.mkdir(parents=True)
    existing.write_text("placeholder", encoding="utf-8")
    tracked = tmp_path / "data" / "pipe_grud" / "sequence.parquet"
    tracked.write_text("placeholder", encoding="utf-8")
    dvc_pointer_path(tracked).write_text("outs: []\n", encoding="utf-8")
    missing = tmp_path / "data" / "pipe_grud" / "future.parquet"

    artifacts = [
        DvcArtifact("rollouts", existing, "pipe_rollout_alerts", "multi_source", True),
        DvcArtifact("sequence", tracked, "pipe_sequence_dataset", "multi_source", True),
        DvcArtifact("future", missing, "future", "multi_source", True),
        DvcArtifact("small", tmp_path / "reports" / "small.md", "report", "multi_source", False),
    ]

    selected = declared_artifacts_missing_pointers(artifacts)

    assert selected == [artifacts[0]]


def _manifest_record(path: Path) -> dict[str, object]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def test_experiment_manifest_validation_checks_output_and_script_hashes(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    report = Path("reports/pipe/report.csv")
    report.parent.mkdir(parents=True)
    report.write_text("value\n1\n", encoding="utf-8")
    script = Path("src/experiments/example.py")
    script.parent.mkdir(parents=True)
    script.write_text("print('ok')\n", encoding="utf-8")
    manifest = Path("reports/pipe/report_manifest.json")
    manifest.write_text(
        (
            "{\n"
            '  "status": "completed",\n'
            f'  "outputs": [{_manifest_record(report)!r}],\n'
            f'  "script": {_manifest_record(script)!r},\n'
            '  "inputs": []\n'
            "}\n"
        ).replace("'", '"'),
        encoding="utf-8",
    )

    findings = validate_experiment_manifests(
        staged_paths={report, manifest},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert not has_failing_findings(findings)

    report.write_text("value\n2\n", encoding="utf-8")

    findings = validate_experiment_manifests(
        staged_paths={report, manifest},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert has_failing_findings(findings)
    assert any("SHA-256 changed" in finding.message for finding in findings)


def test_experiment_manifest_validation_requires_staged_reports_to_be_listed(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    report = Path("reports/pipe/unlisted.csv")
    report.parent.mkdir(parents=True)
    report.write_text("value\n1\n", encoding="utf-8")

    findings = validate_experiment_manifests(
        staged_paths={report},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert has_failing_findings(findings)
    assert any("not listed in any experiment manifest" in finding.message for finding in findings)


def test_freeze_freshness_requires_freeze_outputs_for_data_pipeline_changes() -> None:
    findings = validate_freeze_freshness([("M", Path("src/data/build_panel.py"))])

    assert has_failing_findings(findings)

    findings = validate_freeze_freshness(
        [
            ("M", Path("src/data/build_panel.py")),
            ("M", Path("data/freeze/derived_file_manifest_v0.csv")),
            ("M", Path("data/freeze/data_freeze_manifest_v0.json")),
            ("M", Path("data/freeze/DATA_FREEZE.md")),
        ]
    )

    assert not has_failing_findings(findings)


def test_dvc_inventory_only_change_does_not_warn_about_freeze() -> None:
    findings = validate_freeze_freshness([("M", Path("configs/dvc_artifacts.yaml"))])

    assert not has_failing_findings(findings)
    assert not any(finding.level == "warn" for finding in findings)
    assert any("data-freeze regeneration is not required" in finding.message for finding in findings)


def test_reproducibility_checks_validate_dvc_pointer_structure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    pointer = Path("data/example.parquet.dvc")
    pointer.parent.mkdir(parents=True)
    pointer.write_text(
        "outs:\n"
        "- md5: abc123\n"
        "  size: 10\n"
        "  hash: md5\n"
        "  path: example.parquet\n",
        encoding="utf-8",
    )

    findings = reproducibility_checks(
        staged_status="A\tdata/example.parquet.dvc\n",
        selected_dvc_paths=[],
        artifacts=[],
        max_manifest_hash_bytes=1024 * 1024,
        verify_manifest_inputs=False,
    )

    assert not has_failing_findings(findings)
