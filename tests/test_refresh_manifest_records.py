from __future__ import annotations

import json
from pathlib import Path

from src.data.refresh_manifest_records import refresh_manifest, sha256_file


def test_refresh_manifest_normalizes_repo_absolute_paths(tmp_path: Path) -> None:
    report = tmp_path / "reports" / "example.txt"
    report.parent.mkdir(parents=True)
    report.write_text("updated\n", encoding="utf-8")

    manifest = tmp_path / "reports" / "example_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "outputs": [
                    {
                        "path": report.resolve().as_posix(),
                        "bytes": 1,
                        "sha256": "0" * 64,
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    changed = refresh_manifest(manifest, root=tmp_path, prefixes=("reports/",))

    assert changed
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    record = payload["outputs"][0]
    assert record["path"] == "reports/example.txt"
    assert record["bytes"] == report.stat().st_size
    assert record["sha256"] == sha256_file(report)
