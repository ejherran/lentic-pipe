#!/usr/bin/env python
"""Summarize canonical observation datasets written by build_observations.py."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pyarrow.dataset as ds


DEFAULT_OBSERVATIONS_DIR = Path("data/interim/observations")


def _load_manifest(source_dir: Path) -> dict:
    manifest_path = source_dir / "_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _scan_counts(source_dir: Path) -> tuple[int, Counter[str], Counter[str]]:
    dataset = ds.dataset(source_dir, format="parquet", ignore_prefixes=["_", "."])
    row_count = dataset.count_rows()
    variable_counts: Counter[str] = Counter()
    qc_counts: Counter[str] = Counter()
    scanner = dataset.scanner(columns=["variable_canonical", "qc_flag"])
    for batch in scanner.to_batches():
        variable_counts.update(str(value.as_py()) for value in batch.column("variable_canonical"))
        qc_counts.update(str(value.as_py()) for value in batch.column("qc_flag"))
    return row_count, variable_counts, qc_counts


def summarize_source(source_dir: Path, *, scan: bool) -> None:
    manifest = _load_manifest(source_dir)
    print(f"\nSOURCE {manifest['source_id']}")
    print(f"  output_dir: {manifest['output_dir']}")
    print(f"  chunks: {len(manifest['chunks'])}")
    print(f"  manifest_rows: {manifest['row_count']:,}")
    print(f"  manifest_variable_counts: {manifest['variable_counts']}")
    if not scan:
        return
    physical_rows, variable_counts, qc_counts = _scan_counts(source_dir)
    print(f"  physical_rows: {physical_rows:,}")
    print(f"  physical_variable_counts: {dict(variable_counts)}")
    print(f"  physical_qc_counts_top10: {dict(qc_counts.most_common(10))}")
    if physical_rows != manifest["row_count"]:
        raise SystemExit(
            f"Row-count mismatch for {manifest['source_id']}: "
            f"manifest={manifest['row_count']} physical={physical_rows}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize canonical observation parquet datasets.")
    parser.add_argument("--observations-dir", type=Path, default=DEFAULT_OBSERVATIONS_DIR)
    parser.add_argument("--source", action="append", help="Source id to summarize. Defaults to all source dirs.")
    parser.add_argument("--scan", action="store_true", help="Scan parquet files to verify physical counts.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dirs = [args.observations_dir / source for source in args.source] if args.source else sorted(
        path for path in args.observations_dir.iterdir() if path.is_dir()
    )
    if not source_dirs:
        raise SystemExit(f"No observation datasets found under {args.observations_dir}")
    for source_dir in source_dirs:
        summarize_source(source_dir, scan=args.scan)


if __name__ == "__main__":
    main()
