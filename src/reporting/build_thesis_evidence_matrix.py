#!/usr/bin/env python
"""Build the thesis experiment evidence traceability matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


REQUIRED_COLUMNS = (
    "component",
    "dataset/freeze used",
    "execution date",
    "commit/hash",
    "artifact",
    "split",
    "includes NLA",
    "allowed conclusion",
)
DATE_KEYS = (
    "generated_at_utc",
    "completed_at_utc",
    "created_at_utc",
    "started_at_utc",
)
HASH_CHUNK_SIZE = 1024 * 1024


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(path_text: str, root: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return root / path


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def load_config(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"{path} must contain an entries list")
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Entry {index} must be a mapping")
    return entries


def manifest_date(manifest: dict[str, Any]) -> str | None:
    for key in DATE_KEYS:
        value = manifest.get(key)
        if isinstance(value, str) and value:
            return value
    for value in manifest.values():
        if isinstance(value, dict):
            nested = manifest_date(value)
            if nested:
                return nested
    return None


def iter_file_records(node: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if isinstance(node.get("path"), str) and isinstance(node.get("sha256"), str):
            records.append(node)
        for value in node.values():
            records.extend(iter_file_records(value))
    elif isinstance(node, list):
        for value in node:
            records.extend(iter_file_records(value))
    return records


def manifest_record_hash(manifest: dict[str, Any], path_text: str) -> str | None:
    normalized = path_text.lstrip("./")
    for record in iter_file_records(manifest):
        record_path = str(record["path"]).lstrip("./")
        if record_path == normalized:
            return str(record["sha256"])
    return None


def script_hash(manifest: dict[str, Any]) -> str | None:
    script = manifest.get("script")
    if isinstance(script, dict) and isinstance(script.get("sha256"), str):
        return str(script["sha256"])
    return None


def short_hash(value: str, length: int = 12) -> str:
    return value[:length] if len(value) > length else value


def build_commit_hash(
    *,
    entry: dict[str, Any],
    manifest_path: Path | None,
    manifest: dict[str, Any] | None,
    artifact_path: Path,
    artifact_text: str,
) -> str:
    parts: list[str] = []
    explicit = entry.get("commit_hash")
    if isinstance(explicit, str) and explicit:
        parts.append(explicit)
    if manifest is not None:
        git_commit = manifest.get("git_commit")
        if isinstance(git_commit, str) and git_commit:
            parts.append(f"git:{short_hash(git_commit)}")
        if manifest_path is not None and manifest_path.exists():
            parts.append(f"manifest:{short_hash(sha256_file(manifest_path))}")
        found_script_hash = script_hash(manifest)
        if found_script_hash:
            parts.append(f"script:{short_hash(found_script_hash)}")
        found_artifact_hash = manifest_record_hash(manifest, artifact_text)
        if found_artifact_hash:
            parts.append(f"artifact:{short_hash(found_artifact_hash)}")
    if artifact_path.exists() and not any(part.startswith("artifact:") for part in parts):
        parts.append(f"artifact:{short_hash(sha256_file(artifact_path))}")
    return "; ".join(parts) if parts else "not recorded"


def require_text(entry: dict[str, Any], key: str) -> str:
    value = entry.get(key)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if not isinstance(value, str) or not value.strip():
        component = entry.get("component", "<unknown>")
        raise ValueError(f"Entry {component!r} must define non-empty {key!r}")
    return value.strip()


def build_rows(entries: list[dict[str, Any]], *, root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in entries:
        component = require_text(entry, "component")
        artifact_text = require_text(entry, "artifact")
        artifact_path = repo_path(artifact_text, root)

        manifest: dict[str, Any] | None = None
        manifest_path: Path | None = None
        manifest_text = entry.get("manifest")
        if isinstance(manifest_text, str) and manifest_text:
            manifest_path = repo_path(manifest_text, root)
            if not manifest_path.exists():
                raise FileNotFoundError(f"{component}: manifest does not exist: {manifest_text}")
            manifest = load_json(manifest_path)

        configured_date = entry.get("execution_date")
        execution_date = (
            configured_date.strip()
            if isinstance(configured_date, str) and configured_date.strip()
            else manifest_date(manifest or {}) or "not recorded"
        )

        row = {
            "component": component,
            "dataset/freeze used": require_text(entry, "dataset_freeze_used"),
            "execution date": execution_date,
            "commit/hash": build_commit_hash(
                entry=entry,
                manifest_path=manifest_path,
                manifest=manifest,
                artifact_path=artifact_path,
                artifact_text=artifact_text,
            ),
            "artifact": artifact_text,
            "split": require_text(entry, "split"),
            "includes NLA": require_text(entry, "includes_nla"),
            "allowed conclusion": require_text(entry, "allowed_conclusion"),
        }
        rows.append(row)
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def write_markdown(rows: list[dict[str, str]], path: Path, *, config_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Chapter IV Evidence Traceability Matrix",
        "",
        "This table is generated from a curated configuration and experiment manifests.",
        "It is meant to make the scope of each Chapter IV claim explicit, especially",
        "where a result is reproducible evidence from an earlier iteration rather than",
        "a final evaluation on the NLA-enriched freeze.",
        "",
        f"Source configuration: `{config_path.as_posix()}`.",
        "",
        "| " + " | ".join(REQUIRED_COLUMNS) + " |",
        "| " + " | ".join("---" for _ in REQUIRED_COLUMNS) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(markdown_cell(row[column]) for column in REQUIRED_COLUMNS) + " |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def file_record(path: Path, *, root: Path, role: str | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "path": path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if role is not None:
        record["role"] = role
    return record


def write_manifest(
    *,
    path: Path,
    root: Path,
    config_path: Path,
    csv_path: Path,
    markdown_path: Path,
    row_count: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    script_path = root / "src/reporting/build_thesis_evidence_matrix.py"
    payload = {
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_version": "chapter_iv_evidence_matrix_v0",
        "row_counts": {
            "evidence_rows": row_count,
            "columns": len(REQUIRED_COLUMNS),
        },
        "inputs": [
            file_record(config_path, root=root, role="curated_config"),
        ],
        "outputs": [
            file_record(csv_path, root=root, role="csv_matrix"),
            file_record(markdown_path, root=root, role="markdown_matrix"),
        ],
        "script": file_record(script_path, root=root),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/thesis_evidence_matrix.yaml"),
        help="Curated evidence matrix configuration.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("reports/thesis/chapter_iv_evidence_matrix.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("reports/thesis/chapter_iv_evidence_matrix.md"),
        help="Output Markdown path.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("reports/thesis/chapter_iv_evidence_matrix_manifest.json"),
        help="Output manifest path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    config_path = repo_path(args.config.as_posix(), root)
    csv_path = repo_path(args.csv.as_posix(), root)
    markdown_path = repo_path(args.markdown.as_posix(), root)
    manifest_path = repo_path(args.manifest.as_posix(), root)
    entries = load_config(config_path)
    rows = build_rows(entries, root=root)
    write_csv(rows, csv_path)
    write_markdown(rows, markdown_path, config_path=args.config)
    write_manifest(
        path=manifest_path,
        root=root,
        config_path=config_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
        row_count=len(rows),
    )
    print(
        "Wrote "
        f"{len(rows)} evidence rows to {args.csv.as_posix()}, "
        f"{args.markdown.as_posix()}, and {args.manifest.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
