"""Deterministic hashing helpers for Closure V2 artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize a mapping with the canonical Closure V2 JSON dialect."""
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a regular file without following symlinks."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    """Return the content MD5 required to verify a single-file DVC pointer."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular file: {path}")
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def key_digest(rows: Iterable[Sequence[Any]]) -> str:
    """Hash ordered key rows without locale- or CSV-dependent formatting."""
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(list(row), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def file_record(path: Path, *, root: Path, role: str) -> dict[str, Any]:
    """Build a portable, content-addressed record for a repository artifact."""
    relative = path.relative_to(root)
    return {
        "path": relative.as_posix(),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
