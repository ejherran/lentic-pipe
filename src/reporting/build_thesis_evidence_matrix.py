#!/usr/bin/env python
"""Build the thesis experiment evidence traceability matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


REQUIRED_COLUMNS = (
    "component",
    "evidence tier",
    "authority commit",
    "dataset/freeze used",
    "execution date",
    "commit/hash",
    "artifact",
    "split",
    "includes NLA",
    "allowed conclusion",
)
CONFIG_SCHEMA_VERSION = "thesis_evidence_matrix_v1"
ALLOWED_EVIDENCE_TIERS = frozenset(
    {
        "historical_or_infrastructure",
        "closure_v1_final",
    }
)
HISTORICAL_CONCLUSION_PREFIX = (
    "Historical or infrastructure context only; not final Closure V1 evidence. "
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


def load_config_document(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    if payload.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ValueError(
            f"{path} must declare schema_version={CONFIG_SCHEMA_VERSION!r}"
        )
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"{path} must contain an entries list")
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Entry {index} must be a mapping")
    return payload


def load_config(path: Path) -> list[dict[str, Any]]:
    payload = load_config_document(path)
    entries = payload["entries"]
    if not isinstance(entries, list):  # pragma: no cover - validated above
        raise AssertionError("validated entries must be a list")
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


def build_rows(
    entries: list[dict[str, Any]],
    *,
    root: Path,
    default_evidence_tier: str = "historical_or_infrastructure",
    default_authority_commit: str = "row-specific historical provenance; see commit/hash",
) -> list[dict[str, str]]:
    if default_evidence_tier not in ALLOWED_EVIDENCE_TIERS:
        raise ValueError(f"Unsupported default evidence tier: {default_evidence_tier}")
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

        configured_tier = entry.get("evidence_tier", default_evidence_tier)
        if not isinstance(configured_tier, str) or configured_tier not in ALLOWED_EVIDENCE_TIERS:
            raise ValueError(f"{component}: unsupported evidence_tier {configured_tier!r}")
        configured_authority = entry.get("authority_commit", default_authority_commit)
        if not isinstance(configured_authority, str) or not configured_authority.strip():
            raise ValueError(f"{component}: authority_commit must be non-empty")

        allowed_conclusion = require_text(entry, "allowed_conclusion")
        if configured_tier == "historical_or_infrastructure":
            allowed_conclusion = HISTORICAL_CONCLUSION_PREFIX + allowed_conclusion

        row = {
            "component": component,
            "evidence tier": configured_tier,
            "authority commit": configured_authority.strip(),
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
            "allowed conclusion": allowed_conclusion,
        }
        rows.append(row)
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def write_markdown(
    rows: list[dict[str, str]],
    path: Path,
    *,
    config_path: Path,
    closure_source_commit: str,
    synthesis_publication_commit: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Chapter IV Evidence Traceability Matrix",
        "",
        "This table is generated from a curated configuration and experiment manifests.",
        "Only rows marked `closure_v1_final` are final thesis evidence. Rows marked",
        "`historical_or_infrastructure` remain useful for provenance or comparison but",
        "must not be combined with Closure V1 as if they came from the same freeze.",
        "",
        f"Closure source authority: `{closure_source_commit}`.",
        f"Published synthesis authority: `{synthesis_publication_commit}`.",
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
    generated_at_utc: str,
    report_version: str,
    closure_source_commit: str,
    synthesis_publication_commit: str,
    additional_inputs: list[tuple[Path, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    script_path = root / "src/reporting/build_thesis_evidence_matrix.py"
    payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "status": "completed",
        "generated_at_utc": generated_at_utc,
        "report_version": report_version,
        "closure_source_commit": closure_source_commit,
        "synthesis_publication_commit": synthesis_publication_commit,
        "row_counts": {
            "evidence_rows": row_count,
            "columns": len(REQUIRED_COLUMNS),
        },
        "inputs": [
            file_record(config_path, root=root, role="curated_config"),
            *(
                file_record(input_path, root=root, role=role)
                for input_path, role in additional_inputs
            ),
        ],
        "outputs": [
            file_record(csv_path, root=root, role="csv_matrix"),
            file_record(markdown_path, root=root, role="markdown_matrix"),
        ],
        "script": file_record(script_path, root=root),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def require_document_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Configuration must define non-empty {key!r}")
    return value.strip()


def manifest_inputs(payload: dict[str, Any], *, root: Path) -> list[tuple[Path, str]]:
    configured = payload.get("manifest_inputs")
    if not isinstance(configured, list) or not configured:
        raise ValueError("Configuration must define a non-empty manifest_inputs list")
    records: list[tuple[Path, str]] = []
    seen_paths: set[str] = set()
    for index, record in enumerate(configured, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"manifest_inputs entry {index} must be a mapping")
        typed_record = cast(dict[str, Any], record)
        path_text = require_text(typed_record, "path")
        role = require_text(typed_record, "role")
        if path_text in seen_paths:
            raise ValueError(f"Duplicate manifest input path: {path_text}")
        seen_paths.add(path_text)
        input_path = repo_path(path_text, root)
        if not input_path.is_file():
            raise FileNotFoundError(f"Manifest input does not exist: {path_text}")
        records.append((input_path, role))
    return records


def evidence_inputs(
    entries: list[dict[str, Any]],
    *,
    root: Path,
    configured_inputs: list[tuple[Path, str]],
) -> list[tuple[Path, str]]:
    records = list(configured_inputs)
    seen_paths = {path.resolve() for path, _ in records}
    for entry in entries:
        component = require_text(entry, "component")
        for key, role in (("manifest", "evidence_manifest"), ("artifact", "evidence_artifact")):
            value = entry.get(key)
            if value is None and key == "manifest":
                continue
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{component}: {key} must be a non-empty path")
            input_path = repo_path(value.strip(), root)
            resolved = input_path.resolve()
            if resolved in seen_paths:
                continue
            if not input_path.is_file():
                raise FileNotFoundError(f"{component}: {key} does not exist: {value}")
            seen_paths.add(resolved)
            records.append((input_path, role))
    return records


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
    document = load_config_document(config_path)
    entries = document["entries"]
    if not isinstance(entries, list):  # pragma: no cover - validated by loader
        raise AssertionError("validated entries must be a list")
    default_evidence_tier = require_document_text(document, "default_evidence_tier")
    default_authority_commit = require_document_text(document, "default_authority_commit")
    closure_source_commit = require_document_text(document, "closure_source_commit")
    synthesis_publication_commit = require_document_text(
        document, "synthesis_publication_commit"
    )
    generated_at_utc = require_document_text(document, "generated_at_utc")
    report_version = require_document_text(document, "report_version")
    rows = build_rows(
        entries,
        root=root,
        default_evidence_tier=default_evidence_tier,
        default_authority_commit=default_authority_commit,
    )
    write_csv(rows, csv_path)
    write_markdown(
        rows,
        markdown_path,
        config_path=args.config,
        closure_source_commit=closure_source_commit,
        synthesis_publication_commit=synthesis_publication_commit,
    )
    configured_inputs = manifest_inputs(document, root=root)
    write_manifest(
        path=manifest_path,
        root=root,
        config_path=config_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
        row_count=len(rows),
        generated_at_utc=generated_at_utc,
        report_version=report_version,
        closure_source_commit=closure_source_commit,
        synthesis_publication_commit=synthesis_publication_commit,
        additional_inputs=evidence_inputs(
            entries,
            root=root,
            configured_inputs=configured_inputs,
        ),
    )
    print(
        "Wrote "
        f"{len(rows)} evidence rows to {args.csv.as_posix()}, "
        f"{args.markdown.as_posix()}, and {args.manifest.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
