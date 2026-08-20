from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from src.reporting.build_thesis_evidence_matrix import (
    CONFIG_SCHEMA_VERSION,
    HISTORICAL_CONCLUSION_PREFIX,
    REQUIRED_COLUMNS,
    build_rows,
    evidence_inputs,
    load_config,
    write_csv,
    write_manifest,
)


def test_build_rows_extracts_manifest_date_and_hashes(tmp_path: Path) -> None:
    report = tmp_path / "reports" / "example_report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# Report\n", encoding="utf-8")

    script = tmp_path / "src" / "experiments" / "example.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('ok')\n", encoding="utf-8")

    manifest = tmp_path / "reports" / "example_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "generated_at_utc": "2026-01-01T00:00:00+00:00",
                "script": {
                    "path": "src/experiments/example.py",
                    "sha256": "a" * 64,
                },
                "outputs": [
                    {
                        "path": "reports/example_report.md",
                        "bytes": report.stat().st_size,
                        "sha256": "b" * 64,
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    rows = build_rows(
        [
            {
                "component": "Example component",
                "dataset_freeze_used": "Example freeze",
                "manifest": "reports/example_manifest.json",
                "artifact": "reports/example_report.md",
                "split": "test",
                "includes_nla": "no",
                "allowed_conclusion": "Evidence only.",
            }
        ],
        root=tmp_path,
    )

    assert rows[0]["execution date"] == "2026-01-01T00:00:00+00:00"
    assert rows[0]["evidence tier"] == "historical_or_infrastructure"
    assert rows[0]["authority commit"] == "row-specific historical provenance; see commit/hash"
    assert rows[0]["allowed conclusion"].startswith(HISTORICAL_CONCLUSION_PREFIX)
    assert "script:" in rows[0]["commit/hash"]
    assert "artifact:" in rows[0]["commit/hash"]


def test_write_csv_uses_required_columns(tmp_path: Path) -> None:
    output = tmp_path / "matrix.csv"
    row: dict[str, str] = {column: f"value for {column}" for column in REQUIRED_COLUMNS}

    write_csv([row], output)

    with output.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
    assert tuple(header) == REQUIRED_COLUMNS
    assert b"\r\n" not in output.read_bytes()


def test_load_config_requires_entries_list(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        f"schema_version: {CONFIG_SCHEMA_VERSION}\nentries:\n  - component: Example\n",
        encoding="utf-8",
    )

    entries = load_config(config)

    assert entries == [{"component": "Example"}]


def test_write_manifest_records_outputs_and_script(tmp_path: Path) -> None:
    config = tmp_path / "configs" / "matrix.yaml"
    csv_path = tmp_path / "reports" / "matrix.csv"
    markdown_path = tmp_path / "reports" / "matrix.md"
    script = tmp_path / "src" / "reporting" / "build_thesis_evidence_matrix.py"
    manifest = tmp_path / "reports" / "matrix_manifest.json"
    config.parent.mkdir(parents=True)
    csv_path.parent.mkdir(parents=True)
    script.parent.mkdir(parents=True)
    config.write_text("entries: []\n", encoding="utf-8")
    csv_path.write_text("component\n", encoding="utf-8")
    markdown_path.write_text("# Matrix\n", encoding="utf-8")
    script.write_text("print('ok')\n", encoding="utf-8")

    write_manifest(
        path=manifest,
        root=tmp_path,
        config_path=config,
        csv_path=csv_path,
        markdown_path=markdown_path,
        row_count=0,
        generated_at_utc="2026-08-20T13:54:59+00:00",
        report_version="chapter_iv_evidence_matrix_v1",
        closure_source_commit="a" * 40,
        synthesis_publication_commit="b" * 40,
        additional_inputs=[],
    )

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["schema_version"] == CONFIG_SCHEMA_VERSION
    assert payload["generated_at_utc"] == "2026-08-20T13:54:59+00:00"
    assert payload["closure_source_commit"] == "a" * 40
    assert payload["synthesis_publication_commit"] == "b" * 40
    assert payload["row_counts"] == {"evidence_rows": 0, "columns": len(REQUIRED_COLUMNS)}
    assert [record["role"] for record in payload["outputs"]] == ["csv_matrix", "markdown_matrix"]
    assert payload["script"]["path"] == "src/reporting/build_thesis_evidence_matrix.py"


def test_build_rows_requires_known_evidence_tier(tmp_path: Path) -> None:
    report = tmp_path / "reports" / "example_report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# Report\n", encoding="utf-8")

    try:
        build_rows(
            [
                {
                    "component": "Invalid tier",
                    "evidence_tier": "final_but_unbound",
                    "dataset_freeze_used": "Example freeze",
                    "artifact": "reports/example_report.md",
                    "split": "test",
                    "includes_nla": "no",
                    "allowed_conclusion": "Evidence only.",
                }
            ],
            root=tmp_path,
        )
    except ValueError as exc:
        assert "unsupported evidence_tier" in str(exc)
    else:  # pragma: no cover - assertion aid
        raise AssertionError("Unknown evidence tier must fail closed")


def test_repository_matrix_separates_closure_v1_from_history() -> None:
    root = Path(__file__).resolve().parents[1]
    entries = load_config(root / "configs" / "thesis_evidence_matrix.yaml")
    rows = build_rows(entries, root=root)

    assert len(rows) == 32
    assert Counter(row["evidence tier"] for row in rows) == {
        "historical_or_infrastructure": 19,
        "closure_v1_final": 13,
    }
    closure_rows = [row for row in rows if row["evidence tier"] == "closure_v1_final"]
    assert {row["authority commit"] for row in closure_rows} == {
        "ea8ddce7f8edb9a61db97e29178e52603fa371b1"
    }
    assert all("Closure V1" in row["component"] for row in closure_rows)
    assert any("no conclusive predictive corroboration" in row["allowed conclusion"] for row in closure_rows)


def test_evidence_inputs_bind_every_manifest_and_artifact(tmp_path: Path) -> None:
    manifest = tmp_path / "reports" / "manifest.json"
    artifact = tmp_path / "reports" / "artifact.md"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}\n", encoding="utf-8")
    artifact.write_text("# Artifact\n", encoding="utf-8")

    records = evidence_inputs(
        [
            {
                "component": "Example",
                "manifest": "reports/manifest.json",
                "artifact": "reports/artifact.md",
            }
        ],
        root=tmp_path,
        configured_inputs=[(manifest, "configured_manifest")],
    )

    assert records == [
        (manifest, "configured_manifest"),
        (artifact, "evidence_artifact"),
    ]
