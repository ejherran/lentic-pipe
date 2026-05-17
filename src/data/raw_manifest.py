#!/usr/bin/env python
"""Build an auditable manifest for raw data files.

The manifest is intentionally source-agnostic. It reads configs/sources.yaml,
walks each declared raw path, and records SHA-256 fingerprints before any
harmonization, filtering, or modeling can happen.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = Path("configs/sources.yaml")
DEFAULT_CSV = Path("data/catalog/raw_file_manifest.csv")
DEFAULT_JSON = Path("data/catalog/source_catalog.json")
DEFAULT_REPORT = Path("reports/data/source_inventory.md")
IGNORED_RAW_PATH_PARTS = {".cache", ".dvc", ".git", "__pycache__"}


@dataclass(frozen=True)
class RawFileRecord:
    source_id: str
    source_name: str
    adapter: str
    role: str
    license: str
    provenance_status: str
    path: str
    relative_to_source: str
    file_name: str
    suffix: str
    size_bytes: int
    modified_time_utc: str
    sha256: str


def sha256_file(path: Path, chunk_size: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_existing_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["path"]: row for row in csv.DictReader(handle)}


def load_sources(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or "sources" not in config:
        raise ValueError(f"{config_path} must define a top-level 'sources' mapping")
    return config


def iter_source_files(raw_path: Path) -> list[Path]:
    if raw_path.is_file():
        return [raw_path]
    if raw_path.is_dir():
        return sorted(
            path
            for path in raw_path.rglob("*")
            if path.is_file() and IGNORED_RAW_PATH_PARTS.isdisjoint(path.parts)
        )
    raise FileNotFoundError(f"Raw path does not exist: {raw_path}")


def source_manifest_paths(source: dict[str, Any]) -> list[Path]:
    """Return the raw files/directories that must be fingerprinted for a source."""
    raw_manifest_paths = source.get("raw_manifest_paths")
    if raw_manifest_paths:
        return [Path(path) for path in raw_manifest_paths]
    return [Path(source["raw_path"])]


def build_records(config: dict[str, Any]) -> list[RawFileRecord]:
    return build_records_with_existing(config)[0]


def build_records_with_existing(
    config: dict[str, Any],
    existing_records: dict[str, dict[str, str]] | None = None,
) -> tuple[list[RawFileRecord], dict[str, int]]:
    records: list[RawFileRecord] = []
    stats = {"computed_hashes": 0, "reused_hashes": 0}
    existing_records = existing_records or {}
    for source_id, source in sorted(config["sources"].items()):
        raw_path = Path(source["raw_path"])
        source_root = Path(source.get("local_raw_path", raw_path if raw_path.is_dir() else raw_path.parent))
        source_files: list[Path] = []
        seen_paths: set[Path] = set()
        for manifest_path in source_manifest_paths(source):
            for path in iter_source_files(manifest_path):
                resolved = path.resolve()
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                source_files.append(path)
        for path in source_files:
            stat = path.stat()
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            modified_iso = modified.isoformat()
            existing = existing_records.get(path.as_posix())
            if (
                existing
                and existing.get("sha256")
                and int(existing.get("size_bytes", -1)) == stat.st_size
                and existing.get("modified_time_utc") == modified_iso
            ):
                sha256 = existing["sha256"]
                stats["reused_hashes"] += 1
            else:
                sha256 = sha256_file(path)
                stats["computed_hashes"] += 1
            try:
                relative_to_source = path.relative_to(source_root)
            except ValueError:
                relative_to_source = path
            records.append(
                RawFileRecord(
                    source_id=source_id,
                    source_name=str(source.get("source_name", "")),
                    adapter=str(source.get("adapter", "")),
                    role=str(source.get("role", "")),
                    license=str(source.get("license", "")),
                    provenance_status=str(source.get("provenance_status", "")),
                    path=path.as_posix(),
                    relative_to_source=relative_to_source.as_posix(),
                    file_name=path.name,
                    suffix=path.suffix.lower().lstrip("."),
                    size_bytes=stat.st_size,
                    modified_time_utc=modified_iso,
                    sha256=sha256,
                )
            )
    return records, stats


def write_csv(records: list[RawFileRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(records[0]).keys()) if records else list(RawFileRecord.__dataclass_fields__)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def write_source_catalog(config: dict[str, Any], records: list[RawFileRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    by_source: dict[str, dict[str, Any]] = {}
    for source_id, source in sorted(config["sources"].items()):
        source_records = [record for record in records if record.source_id == source_id]
        by_source[source_id] = {
            "source_name": source.get("source_name"),
            "source_type": source.get("source_type"),
            "access_policy": source.get("access_policy"),
            "raw_path": source.get("raw_path"),
            "local_raw_path": source.get("local_raw_path"),
            "raw_manifest_paths": source.get("raw_manifest_paths"),
            "dvc_track": source.get("dvc_track"),
            "adapter": source.get("adapter"),
            "role": source.get("role"),
            "format": source.get("format"),
            "acquisition": source.get("acquisition"),
            "license": source.get("license"),
            "provenance_status": source.get("provenance_status"),
            "file_count": len(source_records),
            "total_size_bytes": sum(record.size_bytes for record in source_records),
            "files": [
                {
                    "path": record.path,
                    "relative_to_source": record.relative_to_source,
                    "size_bytes": record.size_bytes,
                    "sha256": record.sha256,
                }
                for record in source_records
            ],
        }
    payload = {
        "generated_at_utc": generated_at,
        "config_path": DEFAULT_CONFIG.as_posix(),
        "source_count": len(by_source),
        "file_count": len(records),
        "total_size_bytes": sum(record.size_bytes for record in records),
        "sources": by_source,
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def format_bytes(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def write_report(records: list[RawFileRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    total_size = sum(record.size_bytes for record in records)
    by_source: dict[str, list[RawFileRecord]] = {}
    for record in records:
        by_source.setdefault(record.source_id, []).append(record)

    lines = [
        "# Source Inventory",
        "",
        f"Generated at UTC: `{generated_at}`",
        "",
        f"Total raw files: `{len(records)}`",
        f"Total raw size: `{format_bytes(total_size)}`",
        "",
        "## Sources",
        "",
        "| source_id | files | size | license | provenance_status |",
        "|---|---:|---:|---|---|",
    ]
    for source_id, source_records in sorted(by_source.items()):
        first = source_records[0]
        size = sum(record.size_bytes for record in source_records)
        lines.append(
            f"| `{source_id}` | {len(source_records)} | {format_bytes(size)} | "
            f"{first.license} | {first.provenance_status} |"
        )

    lines.extend(
        [
            "",
            "## Largest Files",
            "",
            "| source_id | path | size | sha256 |",
            "|---|---|---:|---|",
        ]
    )
    for record in sorted(records, key=lambda item: item.size_bytes, reverse=True)[:20]:
        lines.append(
            f"| `{record.source_id}` | `{record.path}` | {format_bytes(record.size_bytes)} | "
            f"`{record.sha256}` |"
        )

    lines.extend(
        [
            "",
            "## Integrity Rule",
            "",
            "These SHA-256 signatures are the reference fingerprints for raw files. "
            "If any raw file changes, the data freeze must be regenerated and the "
            "change must be documented before downstream experiments are trusted.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build raw data manifest with SHA-256 fingerprints.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse SHA-256 values from the existing CSV when path, size, and mtime match.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_sources(args.config)
    existing_records = load_existing_manifest(args.csv) if args.reuse_existing else {}
    records, stats = build_records_with_existing(config, existing_records)
    write_csv(records, args.csv)
    write_source_catalog(config, records, args.json)
    write_report(records, args.report)
    print(f"raw manifest written: {args.csv} ({len(records)} files)")
    print(f"hashes computed={stats['computed_hashes']}, reused={stats['reused_hashes']}")
    print(f"source catalog written: {args.json}")
    print(f"source inventory written: {args.report}")


if __name__ == "__main__":
    main()
