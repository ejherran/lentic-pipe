#!/usr/bin/env python
"""Generate a consolidated report for canonical observation datasets."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_OBSERVATIONS_DIR = Path("data/interim/observations")
DEFAULT_CSV = Path("data/interim/observations/observations_summary.csv")
DEFAULT_REPORT = Path("reports/data/observations_report.md")


def format_int(value: int) -> str:
    return f"{value:,}"


def load_manifest(source_dir: Path) -> dict[str, Any]:
    manifest_path = source_dir / "_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_manifests(observations_dir: Path) -> list[dict[str, Any]]:
    manifests = []
    for source_dir in sorted(path for path in observations_dir.iterdir() if path.is_dir()):
        manifests.append(load_manifest(source_dir))
    return manifests


def write_summary_csv(manifests: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for manifest in manifests:
        rows.append(
            {
                "source_id": manifest["source_id"],
                "adapter": manifest["adapter"],
                "status": manifest.get("status"),
                "chunks": len(manifest.get("chunks", [])),
                "row_count": manifest.get("row_count", 0),
                "started_at_utc": manifest.get("started_at_utc"),
                "completed_at_utc": manifest.get("completed_at_utc"),
                "output_dir": manifest.get("output_dir"),
                "variable_counts_json": json.dumps(manifest.get("variable_counts", {}), sort_keys=True),
            }
        )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def write_report(manifests: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_rows = sum(int(manifest.get("row_count", 0)) for manifest in manifests)
    lines = [
        "# Canonical Observations Report",
        "",
        f"Sources: `{len(manifests)}`",
        f"Total canonical observations: `{format_int(total_rows)}`",
        "",
        "## Source Summary",
        "",
        "| source_id | status | chunks | rows | output_dir |",
        "|---|---|---:|---:|---|",
    ]
    for manifest in manifests:
        lines.append(
            f"| `{manifest['source_id']}` | {manifest.get('status')} | "
            f"{len(manifest.get('chunks', []))} | {format_int(int(manifest.get('row_count', 0)))} | "
            f"`{manifest.get('output_dir')}` |"
        )

    lines.extend(["", "## Variable Counts", ""])
    for manifest in manifests:
        lines.extend(
            [
                f"### {manifest['source_id']}",
                "",
                "| variable_canonical | rows |",
                "|---|---:|",
            ]
        )
        variable_counts = manifest.get("variable_counts", {})
        for variable, count in sorted(variable_counts.items(), key=lambda item: item[0]):
            lines.append(f"| `{variable}` | {format_int(int(count))} |")
        lines.append("")

    lines.extend(
        [
            "## Integrity Note",
            "",
            "This report is derived from per-source `_manifest.json` files generated during canonicalization. "
            "Use `src/data/summarize_observations.py --scan` to verify physical parquet row counts against manifests.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate canonical observations report.")
    parser.add_argument("--observations-dir", type=Path, default=DEFAULT_OBSERVATIONS_DIR)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifests = collect_manifests(args.observations_dir)
    write_summary_csv(manifests, args.csv)
    write_report(manifests, args.report)
    print(f"observation summary written: {args.csv}")
    print(f"observation report written: {args.report}")


if __name__ == "__main__":
    main()
