#!/usr/bin/env python
"""Run or preview `dvc add` commands from the base and post-lock inventories."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.prepare_commit_artifacts import (
    DEFAULT_CLOSURE_DVC_MANIFEST,
    validate_closure_dvc_overlay_anchor,
)


DEFAULT_MANIFEST = Path("configs/dvc_artifacts.yaml")
DEFAULT_DVC_BIN = Path(".venv/bin/dvc")
DEFAULT_DVC_SITE_CACHE_DIR = Path(".dvc/tmp/site-cache")


@dataclass(frozen=True)
class DvcArtifact:
    artifact_id: str
    path: Path
    artifact_type: str
    source_id: str
    dvc: bool


def load_artifacts(manifest_path: Path) -> list[DvcArtifact]:
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path} must contain a YAML mapping")

    artifacts: list[DvcArtifact] = []
    for raw_artifact in manifest.get("artifacts", []):
        if not isinstance(raw_artifact, dict):
            raise ValueError("Each artifact entry must be a YAML mapping")
        artifacts.append(
            DvcArtifact(
                artifact_id=str(raw_artifact["artifact_id"]),
                path=Path(str(raw_artifact["path"])),
                artifact_type=str(raw_artifact.get("type", "")),
                source_id=str(raw_artifact.get("source_id", "")),
                dvc=bool(raw_artifact.get("dvc", False)),
            )
        )
    return artifacts


def load_configured_artifacts(manifest_path: Path) -> list[DvcArtifact]:
    """Load the immutable base plus the Closure post-lock overlay by default."""
    manifest_paths = [manifest_path]
    if manifest_path.resolve() == DEFAULT_MANIFEST.resolve():
        validate_closure_dvc_overlay_anchor()
        manifest_paths.append(DEFAULT_CLOSURE_DVC_MANIFEST)
    artifacts = [
        artifact
        for configured_path in manifest_paths
        for artifact in load_artifacts(configured_path)
    ]
    artifact_ids = [artifact.artifact_id for artifact in artifacts]
    artifact_paths = [artifact.path for artifact in artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("DVC artifact inventories contain duplicate artifact_id values")
    if len(artifact_paths) != len(set(artifact_paths)):
        raise ValueError("DVC artifact inventories contain duplicate paths")
    return artifacts


def resolve_dvc_bin(explicit_path: str | None = None) -> str:
    candidates = [
        explicit_path,
        os.environ.get("DVC_BIN"),
        DEFAULT_DVC_BIN.as_posix(),
        shutil.which("dvc"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        candidate_path = Path(candidate)
        if candidate_path.exists() and os.access(candidate_path, os.X_OK):
            return candidate_path.as_posix()
        if shutil.which(candidate):
            return candidate
    raise FileNotFoundError("Could not find dvc. Expected .venv/bin/dvc or set DVC_BIN.")


def dvc_add_commands(
    artifacts: list[DvcArtifact],
    *,
    include_missing: bool,
    dvc_bin: str = "dvc",
) -> tuple[list[list[str]], list[DvcArtifact]]:
    commands: list[list[str]] = []
    missing: list[DvcArtifact] = []
    for artifact in artifacts:
        if not artifact.dvc:
            continue
        if not artifact.path.exists():
            missing.append(artifact)
            if not include_missing:
                continue
        commands.append([dvc_bin, "add", artifact.path.as_posix()])
    return commands, missing


def dvc_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("DVC_SITE_CACHE_DIR", DEFAULT_DVC_SITE_CACHE_DIR.as_posix())
    return env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or preview dvc add commands from a manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dvc-bin", default=None, help="Path to dvc executable. Defaults to .venv/bin/dvc.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running dvc.")
    parser.add_argument("--allow-missing", action="store_true", help="Skip missing artifacts instead of failing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts = load_configured_artifacts(args.manifest)
    dvc_bin = resolve_dvc_bin(args.dvc_bin)
    commands, missing = dvc_add_commands(artifacts, include_missing=False, dvc_bin=dvc_bin)

    if missing and not args.allow_missing:
        print("Missing artifacts declared for DVC:", file=sys.stderr)
        for artifact in missing:
            print(f"  - {artifact.artifact_id}: {artifact.path}", file=sys.stderr)
        print("Use --allow-missing only when you intentionally want to skip them.", file=sys.stderr)
        return 2

    if args.allow_missing:
        commands, missing = dvc_add_commands(artifacts, include_missing=False, dvc_bin=dvc_bin)
        for artifact in missing:
            print(f"skip missing: {artifact.artifact_id} -> {artifact.path}")

    for command in commands:
        print(" ".join(command))
        if not args.dry_run:
            subprocess.run(command, check=True, env=dvc_environment())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
