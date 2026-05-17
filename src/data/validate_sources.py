#!/usr/bin/env python
"""Validate source registry metadata without hashing raw data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.build_observations import ADAPTER_MODULES


DEFAULT_CONFIG = Path("configs/sources.yaml")


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    if not isinstance(config.get("sources"), dict):
        raise ValueError(f"{path} must define a top-level sources mapping")
    return config


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_fields = config.get("source_contract", {}).get("required_fields", [])
    if not required_fields:
        errors.append("source_contract.required_fields is missing or empty")

    for source_id, source in sorted(config["sources"].items()):
        if not isinstance(source, dict):
            errors.append(f"{source_id}: source entry must be a mapping")
            continue
        for field in required_fields:
            if field not in source:
                errors.append(f"{source_id}: missing required field {field}")

        if source.get("source_id") != source_id:
            errors.append(f"{source_id}: source_id field must match mapping key")

        adapter = source.get("adapter")
        if adapter and adapter not in ADAPTER_MODULES:
            errors.append(f"{source_id}: adapter {adapter!r} is not registered")

        raw_path = Path(str(source.get("raw_path", "")))
        if not raw_path.exists():
            errors.append(f"{source_id}: raw_path does not exist: {raw_path}")

        local_raw_path = source.get("local_raw_path")
        if local_raw_path is not None and not Path(str(local_raw_path)).exists():
            errors.append(f"{source_id}: local_raw_path does not exist: {local_raw_path}")

        raw_manifest_paths = source.get("raw_manifest_paths", [])
        if raw_manifest_paths and not isinstance(raw_manifest_paths, list):
            errors.append(f"{source_id}: raw_manifest_paths must be a list")
        for manifest_path in raw_manifest_paths or []:
            if not Path(str(manifest_path)).exists():
                errors.append(f"{source_id}: raw_manifest_path does not exist: {manifest_path}")

        acquisition = source.get("acquisition")
        if not isinstance(acquisition, dict):
            errors.append(f"{source_id}: acquisition must be a mapping")
            acquisition = {}
        script_hint = acquisition.get("script_hint")
        if script_hint and not Path(str(script_hint)).exists():
            errors.append(f"{source_id}: acquisition.script_hint does not exist: {script_hint}")
        script_hints = acquisition.get("script_hints", [])
        if script_hints and not isinstance(script_hints, list):
            errors.append(f"{source_id}: acquisition.script_hints must be a list")
        for script_path in script_hints or []:
            if not Path(str(script_path)).exists():
                errors.append(f"{source_id}: acquisition.script_hints path does not exist: {script_path}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate configs/sources.yaml without hashing raw files.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    errors = validate_config(config)
    source_count = len(config["sources"])
    print(f"validated {source_count} source entries from {args.config}")
    if errors:
        print("source validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("OK: source registry is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
