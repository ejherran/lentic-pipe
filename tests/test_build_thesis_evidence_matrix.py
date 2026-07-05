from __future__ import annotations

import csv
import json
from pathlib import Path

from src.reporting.build_thesis_evidence_matrix import (
    REQUIRED_COLUMNS,
    build_rows,
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


def test_load_config_requires_entries_list(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("entries:\n  - component: Example\n", encoding="utf-8")

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
    )

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["row_counts"] == {"evidence_rows": 0, "columns": len(REQUIRED_COLUMNS)}
    assert [record["role"] for record in payload["outputs"]] == ["csv_matrix", "markdown_matrix"]
    assert payload["script"]["path"] == "src/reporting/build_thesis_evidence_matrix.py"
