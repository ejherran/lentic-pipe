#!/usr/bin/env python
"""Refresh JSON manifest file-record paths, byte counts, and hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


HASH_CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_directory(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    total_bytes = 0
    for file_path in sorted(item for item in path.rglob("*") if item.is_file() and not item.name.endswith(".tmp")):
        relative_path = file_path.relative_to(path).as_posix()
        file_hash = sha256_file(file_path)
        file_bytes = file_path.stat().st_size
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
        total_bytes += file_bytes
    return total_bytes, digest.hexdigest()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def repo_relative_text(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_record_path(raw_path: str, root: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return root / path


def should_refresh(path_text: str, prefixes: tuple[str, ...]) -> bool:
    normalized = path_text.lstrip("./")
    return any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in prefixes)


def refresh_node(
    node: Any,
    *,
    root: Path,
    manifest_path: Path,
    prefixes: tuple[str, ...],
) -> bool:
    changed = False
    if isinstance(node, dict):
        raw_path = node.get("path")
        if (
            isinstance(raw_path, str)
            and "bytes" in node
            and "sha256" in node
        ):
            record_path = resolve_record_path(raw_path, root)
            path_text = repo_relative_text(record_path, root)
            if (
                should_refresh(path_text, prefixes)
                and record_path.exists()
                and record_path.resolve() != manifest_path.resolve()
            ):
                if record_path.is_dir():
                    bytes_count, digest = sha256_directory(record_path)
                else:
                    bytes_count = record_path.stat().st_size
                    digest = sha256_file(record_path)
                updates = {"path": path_text, "bytes": bytes_count, "sha256": digest}
                for key, value in updates.items():
                    if node.get(key) != value:
                        node[key] = value
                        changed = True
        for value in node.values():
            changed = refresh_node(value, root=root, manifest_path=manifest_path, prefixes=prefixes) or changed
    elif isinstance(node, list):
        for value in node:
            changed = refresh_node(value, root=root, manifest_path=manifest_path, prefixes=prefixes) or changed
    return changed


def manifest_paths(paths: list[Path]) -> list[Path]:
    selected: list[Path] = []
    for path in paths:
        if path.is_dir():
            selected.extend(sorted(path.rglob("*.json")))
        elif path.suffix == ".json":
            selected.append(path)
    return selected


def refresh_manifest(path: Path, *, root: Path, prefixes: tuple[str, ...]) -> bool:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    changed = refresh_node(payload, root=root, manifest_path=path, prefixes=prefixes)
    if changed:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="JSON manifests or directories containing manifests.")
    parser.add_argument(
        "--record-prefix",
        action="append",
        default=[],
        help="Refresh only records whose manifest path starts with this prefix.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Repeat passes to refresh hashes of manifests that reference other refreshed manifests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prefixes = tuple(args.record_prefix)
    if not prefixes:
        print("At least one --record-prefix is required.", file=sys.stderr)
        return 2

    root = repo_root()
    paths = manifest_paths(args.paths)
    total_changed: set[Path] = set()
    for _ in range(args.iterations):
        changed_this_pass = {
            path for path in paths if refresh_manifest(path, root=root, prefixes=prefixes)
        }
        total_changed.update(changed_this_pass)
        if not changed_this_pass:
            break

    for path in sorted(total_changed):
        print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
