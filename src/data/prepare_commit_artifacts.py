#!/usr/bin/env python
"""Prepare Git and DVC artifacts before a manual commit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml


DEFAULT_DVC_MANIFEST = Path("configs/dvc_artifacts.yaml")
DEFAULT_CLOSURE_DVC_MANIFEST = Path(
    "configs/closure_v1/dvc_artifacts_post_lock.yaml"
)
DEFAULT_REPORT_DIR = Path("tmp")
DEFAULT_DVC_BIN = Path(".venv/bin/dvc")
DEFAULT_DVC_SITE_CACHE_DIR = Path(".dvc/tmp/site-cache")
HASH_CHUNK_SIZE = 16 * 1024 * 1024
DEFAULT_MAX_MANIFEST_HASH_BYTES = 512 * 1024 * 1024

HEAVY_PREFIXES = (
    "data/raw/",
    "data/interim/",
    "data/cache/",
    "data/panel/",
    "data/targets/",
    "data/splits/",
    "data/diagnostics/",
    "data/fuzzy/",
    "data/pipe_grud/",
    "data/closure_v1/",
    "models/",
    "checkpoints/",
    "outputs/",
    "artifacts/",
    "runs/",
    "mlruns/",
    "wandb/",
)
IGNORED_PREFIXES_TO_SKIP = (
    ".dvc/cache/",
    ".dvc/tmp/",
    ".pytest_cache/",
    ".venv/",
    "private/",
)
IGNORED_PATH_PARTS_TO_SKIP = {
    "__pycache__",
    ".ipynb_checkpoints",
}
REPORT_SMOKE_PARQUET_SUFFIXES = ("_smoke.parquet", "_stochastic_smoke.parquet")
REGENERABLE_IGNORED_PATHS = {
    "data/interim/observations/observations_summary.csv",
}
REPORT_ARTIFACT_SUFFIXES = {".csv", ".json", ".md", ".parquet", ".txt"}
CLOSURE_PROTOCOL_LOCK_PATH = Path("reports/closure_v1/00_protocol/protocol_lock.json")
CLOSURE_PROTOCOL_LOCK_VERSION = "closure_protocol_lock_v1"
CLOSURE_PROTOCOL_LOCK_SCRIPT = Path("src/experiments/lock_closure_protocol.py")
CLOSURE_COMMON_ORIGIN_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/common_origin_manifest.json"
)
CLOSURE_COMMON_ORIGIN_MANIFEST_VERSION = "closure_common_origin_manifest_v1"
CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT = Path(
    "src/experiments/build_common_origin_manifest.py"
)
CLOSURE_COMMON_ORIGIN_OUTPUT_PATH = Path(
    "data/closure_v1/common_origin_manifest.parquet"
)
CLOSURE_COMMON_ORIGIN_CODE_PATHS = (
    CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT,
    Path("src/experiments/build_closure_holdout.py"),
    Path("src/experiments/closure_contract.py"),
    Path("src/experiments/closure_development_guard.py"),
    Path("src/pandas_utils.py"),
)
CLOSURE_COMMON_ORIGIN_CONFIG_PATHS = (
    Path("configs/closure_v1/analysis_plan.yaml"),
    Path("configs/closure_v1/analysis_plan.schema.json"),
    Path("configs/closure_v1/surface_primary.yaml"),
    Path("configs/closure_v1/surface_secondary.yaml"),
    Path("configs/closure_v1/location_holdout.yaml"),
    Path("configs/closure_v1/model_benchmark.yaml"),
    Path("configs/closure_v1/experimental_matrix.yaml"),
    Path("configs/counterfactual_planning_v1.yaml"),
)
CLOSURE_COMMON_ORIGIN_SOURCE_PATHS = (
    Path("data/panel/panel_monthly_v0.parquet"),
    Path("data/splits/monthly_model_splits_v0.parquet"),
    Path("data/targets/monthly_targets_model_v0.parquet"),
    Path("data/targets/target_manifest_v0.json"),
    Path("data/splits/split_manifest.json"),
)
CLOSURE_COMMON_ORIGIN_SOURCE_ROLES = (
    "cutoff_safe_input_history_source",
    "canonical_leakage_safe_temporal_rows",
    "historical_stratification_and_later_evaluation_targets",
    "canonical_target_provenance_and_threshold_manifest",
    "temporal_split_provenance",
)
CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES = (
    (Path("reports/closure_v1/00_protocol/protocol_lock.json"), "protocol_lock"),
    (Path("reports/closure_v1/00_protocol/holdout_manifest.json"), "holdout_manifest"),
    (Path("data/closure_v1/closure_holdout_assignment.csv"), "holdout_assignment"),
)
CLOSURE_COMMON_ORIGIN_REPRODUCTION_COMMAND = [
    "poetry",
    "run",
    "python",
    CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT.as_posix(),
    "--panel",
    CLOSURE_COMMON_ORIGIN_SOURCE_PATHS[0].as_posix(),
    "--splits",
    CLOSURE_COMMON_ORIGIN_SOURCE_PATHS[1].as_posix(),
    "--output",
    CLOSURE_COMMON_ORIGIN_OUTPUT_PATH.as_posix(),
    "--manifest",
    CLOSURE_COMMON_ORIGIN_MANIFEST_PATH.as_posix(),
]
FREEZE_ARTIFACT_PATHS = {
    Path("data/freeze/derived_file_manifest_v0.csv"),
    Path("data/freeze/data_freeze_manifest_v0.json"),
    Path("data/freeze/DATA_FREEZE.md"),
}
FREEZE_REQUIRED_OUTPUTS = {
    Path("data/freeze/derived_file_manifest_v0.csv"),
    Path("data/freeze/data_freeze_manifest_v0.json"),
    Path("data/freeze/DATA_FREEZE.md"),
}
FREEZE_DOCUMENTATION_OUTPUTS = {
    Path("data/freeze/data_freeze_manifest_v0.json"),
    Path("data/freeze/DATA_FREEZE.md"),
}
FREEZE_SENSITIVE_EXACT_PATHS = {
    "configs/sources.yaml",
    "configs/site_resolution.yaml",
    "src/data/build_observations.py",
    "src/data/build_waterbody_crosswalk.py",
    "src/data/build_panel.py",
    "src/data/build_targets.py",
    "src/data/diagnose_panel_targets.py",
    "src/data/freeze.py",
    "src/data/raw_manifest.py",
    "src/data/report_observations.py",
    "src/data/site_registry.py",
    "src/data/validate_sources.py",
}
FREEZE_SENSITIVE_PREFIXES = (
    "data/catalog/",
    "data/interim/",
    "data/panel/",
    "data/targets/",
    "data/diagnostics/",
    "data/scripts/",
)
DEFAULT_DVC_ARTIFACT_INVENTORY = Path("configs/dvc_artifacts.yaml")


@dataclass(frozen=True)
class DvcArtifact:
    artifact_id: str
    path: Path
    artifact_type: str
    source_id: str
    dvc: bool


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ReproducibilityFinding:
    level: str
    check: str
    path: str
    message: str


def command_text(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def sha256_file(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
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


def run_command(command: list[str], *, check: bool = True, env: dict[str, str] | None = None) -> CommandResult:
    process = subprocess.run(command, check=False, text=True, capture_output=True, env=env)
    result = CommandResult(
        command=command,
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )
    if check and result.returncode != 0:
        print(f"Command failed: {command_text(command)}", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def dvc_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("DVC_SITE_CACHE_DIR", DEFAULT_DVC_SITE_CACHE_DIR.as_posix())
    return env


def resolve_dvc_bin(explicit_path: str | None) -> str:
    candidates = [
        explicit_path,
        os.environ.get("DVC_BIN"),
        DEFAULT_DVC_BIN.as_posix(),
        "dvc",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            return path.as_posix()
        resolved = run_command(["bash", "-lc", f"command -v {shlex.quote(candidate)}"], check=False)
        if resolved.returncode == 0 and resolved.stdout.strip():
            return resolved.stdout.strip()
    raise SystemExit("Could not find dvc. Expected .venv/bin/dvc or set DVC_BIN.")


def ensure_repo_root() -> None:
    if not Path(".git").is_dir():
        raise SystemExit("Run this from the repository root.")


def load_dvc_artifacts(manifest_path: Path) -> list[DvcArtifact]:
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path} must contain a YAML mapping")

    artifacts = []
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


def validate_closure_dvc_overlay_anchor(
    overlay_path: Path = DEFAULT_CLOSURE_DVC_MANIFEST,
) -> None:
    """Require the post-lock overlay to extend the exact E0-P base inventory."""
    with overlay_path.open("r", encoding="utf-8") as handle:
        overlay = yaml.safe_load(handle)
    anchor = overlay.get("sealed_base_inventory") if isinstance(overlay, dict) else None
    if not isinstance(anchor, dict):
        raise ValueError(f"{overlay_path} must declare sealed_base_inventory")
    expected_anchor = {
        "path": DEFAULT_DVC_MANIFEST.as_posix(),
        "bytes": 18841,
        "sha256": "3304fd61978604ecfba5f99f1a9b3d04e4655f45f97f92954081751346143605",
        "authority": CLOSURE_PROTOCOL_LOCK_PATH.as_posix(),
    }
    if anchor != expected_anchor:
        raise ValueError(f"{overlay_path} sealed_base_inventory differs from E0-P")

    protocol_lock = json.loads(CLOSURE_PROTOCOL_LOCK_PATH.read_text(encoding="utf-8"))
    source_records = protocol_lock.get("source_artifacts") if isinstance(protocol_lock, dict) else None
    matching_records = (
        [
            record
            for record in source_records
            if isinstance(record, dict) and record.get("path") == DEFAULT_DVC_MANIFEST.as_posix()
        ]
        if isinstance(source_records, list)
        else []
    )
    if len(matching_records) != 1:
        raise ValueError("Closure protocol lock must contain the sealed base DVC inventory")
    locked_record = matching_records[0]
    if (
        locked_record.get("bytes") != anchor["bytes"]
        or locked_record.get("sha256") != anchor["sha256"]
    ):
        raise ValueError("Closure DVC overlay anchor differs from the protocol-lock source record")
    if (
        DEFAULT_DVC_MANIFEST.stat().st_size != anchor["bytes"]
        or sha256_file(DEFAULT_DVC_MANIFEST) != anchor["sha256"]
    ):
        raise ValueError("Protocol-locked base DVC inventory changed")


def load_configured_dvc_artifacts(manifest_path: Path) -> list[DvcArtifact]:
    """Load the sealed base inventory plus its derived Closure V1 overlay."""
    manifest_paths = [manifest_path]
    if manifest_path.resolve() == DEFAULT_DVC_MANIFEST.resolve():
        validate_closure_dvc_overlay_anchor()
        manifest_paths.append(DEFAULT_CLOSURE_DVC_MANIFEST)
    artifacts = [
        artifact
        for configured_path in manifest_paths
        for artifact in load_dvc_artifacts(configured_path)
    ]
    artifact_ids = [artifact.artifact_id for artifact in artifacts]
    artifact_paths = [artifact.path for artifact in artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("DVC artifact inventories contain duplicate artifact_id values")
    if len(artifact_paths) != len(set(artifact_paths)):
        raise ValueError("DVC artifact inventories contain duplicate paths")
    return artifacts


def dvc_pointer_path(path: Path) -> Path:
    if path.is_dir():
        return path.with_name(path.name + ".dvc")
    return Path(path.as_posix() + ".dvc")


def path_text(path: Path) -> str:
    return path.as_posix().rstrip("/")


def is_same_or_inside(candidate: str, parent: Path) -> bool:
    parent_text = path_text(parent)
    candidate = candidate.rstrip("/")
    return candidate == parent_text or candidate.startswith(parent_text + "/")


def is_artifact_covered(candidate: str, artifacts: list[DvcArtifact]) -> bool:
    for artifact in artifacts:
        if not artifact.dvc:
            continue
        if is_same_or_inside(candidate, artifact.path):
            return True
        if candidate == dvc_pointer_path(artifact.path).as_posix():
            return True
    return False


def has_local_dvc_pointer(candidate: Path) -> bool:
    """Return true when a path is protected by a local DVC pointer file."""
    for path in [candidate, *candidate.parents]:
        if path == Path("."):
            break
        if dvc_pointer_path(path).exists():
            return True
    return False


def collect_strings(value: Any) -> set[str]:
    strings: set[str] = set()
    if isinstance(value, str):
        strings.add(value)
    elif isinstance(value, dict):
        for key, nested in value.items():
            strings.update(collect_strings(key))
            strings.update(collect_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            strings.update(collect_strings(nested))
    return strings


def dvc_status_json(dvc_bin: str) -> dict[str, Any]:
    result = run_command([dvc_bin, "status", "--json"], env=dvc_environment())
    if not result.stdout.strip():
        return {}
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        return {}
    return payload


def dvc_status_candidates(status_payload: dict[str, Any], artifacts: list[DvcArtifact]) -> list[DvcArtifact]:
    if not status_payload:
        return []
    status_strings = collect_strings(status_payload)
    candidates = []
    for artifact in artifacts:
        if not artifact.dvc or not artifact.path.exists():
            continue
        pointer = dvc_pointer_path(artifact.path).as_posix()
        for item in status_strings:
            if item == pointer or is_same_or_inside(item, artifact.path):
                candidates.append(artifact)
                break
    return sorted(set(candidates), key=lambda artifact: artifact.path.as_posix())


def declared_artifacts_missing_pointers(artifacts: list[DvcArtifact]) -> list[DvcArtifact]:
    candidates = []
    for artifact in artifacts:
        if not artifact.dvc:
            continue
        if not artifact.path.exists():
            continue
        if dvc_pointer_path(artifact.path).exists():
            continue
        candidates.append(artifact)
    return sorted(candidates, key=lambda artifact: artifact.path.as_posix())


def parse_git_status_lines(output: str) -> list[tuple[str, str]]:
    rows = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        rows.append((line[:2], line[3:]))
    return rows


def parse_git_name_status(output: str) -> list[tuple[str, Path]]:
    rows = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        rows.append((parts[0], Path(parts[-1])))
    return rows


def should_skip_ignored_path(path: str) -> bool:
    if path in REGENERABLE_IGNORED_PATHS:
        return True
    if any(path.startswith(prefix) for prefix in IGNORED_PREFIXES_TO_SKIP):
        return True
    if path.startswith("reports/") and path.endswith(REPORT_SMOKE_PARQUET_SUFFIXES):
        return True
    return any(part in IGNORED_PATH_PARTS_TO_SKIP for part in Path(path).parts)


def is_heavy_ignored_path(path: str) -> bool:
    if should_skip_ignored_path(path):
        return False
    if any(path.startswith(prefix) for prefix in HEAVY_PREFIXES):
        return True
    if path.startswith("reports/") and path.endswith(".parquet"):
        return True
    return path == "reports/anfis/operational_site_review_summary.csv"


def unmanaged_ignored_heavy_paths(artifacts: list[DvcArtifact]) -> list[Path]:
    result = run_command(["git", "status", "--short", "--ignored", "--untracked-files=normal"])
    paths = []
    for status, path in parse_git_status_lines(result.stdout):
        normalized = path.rstrip("/")
        if status != "!!":
            continue
        if not is_heavy_ignored_path(normalized):
            continue
        if is_artifact_covered(normalized, artifacts):
            continue
        if has_local_dvc_pointer(Path(normalized)):
            continue
        paths.append(Path(normalized))
    return sorted(set(paths), key=lambda path: path.as_posix())


def versionable_changes() -> str:
    return run_command(["git", "status", "--short", "--untracked-files=normal"]).stdout


def normalize_repo_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        return path
    repo_root = Path.cwd().resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root)
    except ValueError:
        return path


def is_experiment_manifest_path(path: Path) -> bool:
    text = path.as_posix()
    if path.name.endswith("_promotion_manifest.json"):
        return False
    if path == CLOSURE_PROTOCOL_LOCK_PATH:
        return True
    if path.name == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH.name:
        return path == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH
    return text.startswith("reports/") and path.suffix == ".json" and "manifest" in path.name


def is_report_artifact_path(path: Path) -> bool:
    text = path.as_posix()
    if not text.startswith("reports/"):
        return False
    if text.startswith("reports/data/"):
        return False
    if path.name.endswith("_promotion_manifest.json"):
        return False
    if is_experiment_manifest_path(path):
        return False
    return path.suffix in REPORT_ARTIFACT_SUFFIXES


def manifest_record_path(record: Any) -> Path | None:
    if not isinstance(record, dict):
        return None
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    return normalize_repo_path(raw_path)


def record_display_path(path: Path) -> str:
    return path.as_posix() if not path.is_absolute() else str(path)


def manifest_output_records(payload: Any, manifest_path: Path) -> Any:
    if not isinstance(payload, dict):
        return None
    if manifest_path == CLOSURE_PROTOCOL_LOCK_PATH:
        return payload.get("generated_lock_companions")
    if manifest_path == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH:
        return [payload.get("output")]
    return payload.get("outputs")


def verify_manifest_file_record(
    *,
    record: Any,
    manifest_path: Path,
    section: str,
    findings: list[ReproducibilityFinding],
    max_hash_bytes: int,
    require_hash: bool,
    force_hash: bool = False,
) -> Path | None:
    record_path = manifest_record_path(record)
    if record_path is None:
        findings.append(
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                f"{section} record is missing a valid path.",
            )
        )
        return None

    actual_path = record_path
    display_path = record_display_path(record_path)
    if not actual_path.exists():
        findings.append(
            ReproducibilityFinding(
                "fail",
                "manifest",
                display_path,
                f"{manifest_path} lists this {section} path, but it does not exist.",
            )
        )
        return record_path

    if isinstance(record, dict):
        if actual_path.is_dir():
            actual_bytes, actual_sha = sha256_directory(actual_path)
        else:
            actual_bytes = actual_path.stat().st_size
            actual_sha = None

        expected_bytes = record.get("bytes")
        if isinstance(expected_bytes, int):
            if actual_bytes != expected_bytes:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        display_path,
                        f"{section} byte count changed: manifest={expected_bytes}, current={actual_bytes}.",
                    )
                )

        expected_sha = record.get("sha256")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    display_path,
                    f"{section} record is missing a 64-character SHA-256 hash.",
                )
            )
            return record_path

        should_hash = force_hash or (require_hash and actual_bytes <= max_hash_bytes)
        if should_hash:
            actual_sha = actual_sha or sha256_file(actual_path)
            if actual_sha != expected_sha:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        display_path,
                        f"{section} SHA-256 changed: manifest={expected_sha}, current={actual_sha}.",
                    )
                )
        elif require_hash:
            findings.append(
                ReproducibilityFinding(
                    "warn",
                    "manifest",
                    display_path,
                    (
                        f"{section} is {actual_bytes} bytes, above --max-manifest-hash-bytes="
                        f"{max_hash_bytes}; byte count was checked, SHA-256 was not recomputed."
                    ),
                )
            )

    return record_path


def discover_relevant_manifest_paths(staged_paths: set[Path]) -> list[Path]:
    manifest_paths = {path for path in staged_paths if is_experiment_manifest_path(path)}
    if dvc_pointer_path(CLOSURE_COMMON_ORIGIN_OUTPUT_PATH) in staged_paths:
        manifest_paths.add(CLOSURE_COMMON_ORIGIN_MANIFEST_PATH)
    for path in staged_paths:
        if not is_report_artifact_path(path):
            continue
        if not path.parent.exists():
            continue
        candidates = set(path.parent.glob("*manifest*.json"))
        closure_lock_candidate = path.parent / CLOSURE_PROTOCOL_LOCK_PATH.name
        if closure_lock_candidate == CLOSURE_PROTOCOL_LOCK_PATH and closure_lock_candidate.exists():
            candidates.add(closure_lock_candidate)
        for candidate in candidates:
            if not is_experiment_manifest_path(candidate):
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            outputs = manifest_output_records(payload, candidate)
            if not isinstance(outputs, list):
                continue
            output_paths = {record_path for record in outputs if (record_path := manifest_record_path(record)) is not None}
            if path in output_paths:
                manifest_paths.add(candidate)
    return sorted(manifest_paths, key=lambda path: path.as_posix())


def validate_experiment_manifests(
    *,
    staged_paths: set[Path],
    artifacts: list[DvcArtifact],
    max_hash_bytes: int,
    verify_manifest_inputs: bool,
) -> list[ReproducibilityFinding]:
    findings: list[ReproducibilityFinding] = []
    report_artifacts = sorted(
        {path for path in staged_paths if is_report_artifact_path(path)},
        key=lambda path: path.as_posix(),
    )
    manifest_paths = discover_relevant_manifest_paths(staged_paths)
    covered_outputs: dict[Path, list[Path]] = {}
    checked_outputs = 0

    if not report_artifacts and not manifest_paths:
        return [
            ReproducibilityFinding(
                "ok",
                "manifest",
                "-",
                "No staged report artifacts require experiment-manifest validation.",
            )
        ]

    for manifest_path in manifest_paths:
        if not manifest_path.exists():
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest is referenced by staged reports but does not exist.",
                )
            )
            continue

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    f"Experiment manifest is not valid JSON: {exc}.",
                )
            )
            continue

        is_closure_protocol_lock = manifest_path == CLOSURE_PROTOCOL_LOCK_PATH
        is_closure_common_origin_manifest = (
            manifest_path == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH
        )
        if is_closure_protocol_lock:
            lock_version = payload.get("lock_version") if isinstance(payload, dict) else None
            status = payload.get("status") if isinstance(payload, dict) else None
            if lock_version != CLOSURE_PROTOCOL_LOCK_VERSION:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        (
                            f"Closure protocol lock version is `{lock_version}`, "
                            f"expected `{CLOSURE_PROTOCOL_LOCK_VERSION}`."
                        ),
                    )
                )
            if status != "locked":
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        f"Closure protocol lock status is `{status}`, expected `locked`.",
                    )
                )
            for field in (
                "future_outcomes_accessed",
                "lock_command_semantically_decodes_post_2021_outcomes",
                "holdout_assignment_created",
            ):
                value = payload.get(field) if isinstance(payload, dict) else None
                if value is not False:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            f"Closure protocol lock requires `{field}=false`.",
                        )
                    )
            locked_repository = payload.get("locked_repository") if isinstance(payload, dict) else None
            if (
                not isinstance(locked_repository, dict)
                or locked_repository.get("worktree_status") != "clean"
                or locked_repository.get("dirty_paths") != []
            ):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure protocol lock must record a clean repository with no dirty paths.",
                    )
                )
        elif is_closure_common_origin_manifest:
            if not isinstance(payload, dict):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure common-origin manifest must contain a JSON object.",
                    )
                )
            else:
                manifest_version = payload.get("manifest_version")
                if manifest_version != CLOSURE_COMMON_ORIGIN_MANIFEST_VERSION:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            (
                                f"Closure common-origin manifest version is `{manifest_version}`, "
                                f"expected `{CLOSURE_COMMON_ORIGIN_MANIFEST_VERSION}`."
                            ),
                        )
                    )
                for field, expected in (
                    ("status", "completed"),
                    ("experiment_id", "closure_v1"),
                    ("surface_id", "closure_v1_wqp_adaptive_no_current_chla"),
                    ("future_outcomes_accessed", False),
                    ("target_values_projected", []),
                    ("target_parquet_semantically_opened", False),
                    ("post_cutoff_target_rows_materialized", 0),
                    ("target_availability_used_for_origin_selection", False),
                    ("availability_join", "left_after_intent_freeze"),
                ):
                    value = payload.get(field)
                    matches = value == expected
                    if expected is False:
                        matches = value is False
                    elif field == "post_cutoff_target_rows_materialized":
                        matches = type(value) is int and value == 0
                    if not matches:
                        findings.append(
                            ReproducibilityFinding(
                                "fail",
                                "manifest",
                                manifest_path.as_posix(),
                                (
                                    "Closure common-origin manifest requires "
                                    f"`{field}={json.dumps(expected)}`."
                                ),
                            )
                        )
                execution = payload.get("execution")
                repository = execution.get("repository") if isinstance(execution, dict) else None
                base_head = repository.get("base_head") if isinstance(repository, dict) else None
                status = (
                    repository.get("tracked_worktree_status")
                    if isinstance(repository, dict)
                    else None
                )
                status_lines = (
                    repository.get("tracked_status_lines")
                    if isinstance(repository, dict)
                    else None
                )
                valid_head = (
                    isinstance(base_head, str)
                    and len(base_head) in {40, 64}
                    and set(base_head).issubset(set("0123456789abcdef"))
                )
                valid_status = (
                    status in {"clean", "dirty"}
                    and isinstance(status_lines, list)
                    and all(isinstance(line, str) and line for line in status_lines)
                    and status == ("dirty" if status_lines else "clean")
                )
                if (
                    not isinstance(execution, dict)
                    or set(execution)
                    != {
                        "repository",
                        "source_tree_identity",
                        "reproduction_command",
                        "future_outcomes_semantically_decoded",
                    }
                    or not isinstance(repository, dict)
                    or set(repository)
                    != {
                        "base_head",
                        "base_head_is_complete_source_identity",
                        "tracked_worktree_status",
                        "tracked_status_lines",
                    }
                    or not valid_head
                    or repository.get("base_head_is_complete_source_identity") is not False
                    or not valid_status
                    or execution.get("source_tree_identity")
                    != "code_config_parent_sha256_records"
                    or execution.get("future_outcomes_semantically_decoded") is not False
                    or execution.get("reproduction_command")
                    != CLOSURE_COMMON_ORIGIN_REPRODUCTION_COMMAND
                ):
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            "Closure common-origin manifest has an invalid sealed execution record.",
                        )
                    )
        elif isinstance(payload, dict) and payload.get("status") not in {None, "completed"}:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    f"Experiment manifest status is `{payload.get('status')}`, expected `completed`.",
                )
            )

        outputs = manifest_output_records(payload, manifest_path)
        if not isinstance(outputs, list) or not outputs:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest must contain a non-empty `outputs` list.",
                )
            )
            continue

        if is_closure_common_origin_manifest:
            output_paths = tuple(manifest_record_path(record) for record in outputs)
            if output_paths != (CLOSURE_COMMON_ORIGIN_OUTPUT_PATH,):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        (
                            "Closure common-origin manifest must contain exactly the output "
                            f"`{CLOSURE_COMMON_ORIGIN_OUTPUT_PATH}`."
                        ),
                    )
                )

        for record in outputs:
            record_path = verify_manifest_file_record(
                record=record,
                manifest_path=manifest_path,
                section="output",
                findings=findings,
                max_hash_bytes=max_hash_bytes,
                require_hash=True,
                force_hash=is_closure_common_origin_manifest,
            )
            if record_path is not None:
                covered_outputs.setdefault(record_path, []).append(manifest_path)
                checked_outputs += 1

        if is_closure_protocol_lock:
            protocol_components = payload.get("protocol_components") if isinstance(payload, dict) else None
            source_artifacts = payload.get("source_artifacts") if isinstance(payload, dict) else None
            lock_scripts = (
                [
                    record
                    for record in protocol_components
                    if manifest_record_path(record) == CLOSURE_PROTOCOL_LOCK_SCRIPT
                ]
                if isinstance(protocol_components, list)
                else []
            )
            if len(lock_scripts) != 1:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure protocol lock must contain exactly one generating-script record.",
                    )
                )
            script = lock_scripts[0] if len(lock_scripts) == 1 else None
            if not isinstance(protocol_components, list) or not isinstance(source_artifacts, list):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure protocol lock must contain protocol-components and source-artifacts lists.",
                    )
                )
                inputs: Any = []
            else:
                inputs = [*protocol_components, *source_artifacts]
        elif is_closure_common_origin_manifest:
            code = payload.get("code") if isinstance(payload, dict) else None
            configs = payload.get("configs") if isinstance(payload, dict) else None
            source_inputs = payload.get("source_inputs") if isinstance(payload, dict) else None
            parent_artifacts = payload.get("parent_artifacts") if isinstance(payload, dict) else None
            common_origin_sections = (
                ("code", code, CLOSURE_COMMON_ORIGIN_CODE_PATHS),
                ("configs", configs, CLOSURE_COMMON_ORIGIN_CONFIG_PATHS),
                ("source_inputs", source_inputs, CLOSURE_COMMON_ORIGIN_SOURCE_PATHS),
                (
                    "parent_artifacts",
                    parent_artifacts,
                    tuple(path for path, _ in CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES),
                ),
            )
            inputs = []
            for section_name, records, expected_paths in common_origin_sections:
                if not isinstance(records, list) or not records:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            (
                                "Closure common-origin manifest must contain a non-empty "
                                f"`{section_name}` list."
                            ),
                        )
                    )
                    continue
                observed_paths = tuple(manifest_record_path(record) for record in records)
                if observed_paths != expected_paths:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            (
                                f"Closure common-origin `{section_name}` paths must equal "
                                f"{[path.as_posix() for path in expected_paths]}."
                            ),
                        )
                    )
                inputs.extend(records)

            if isinstance(source_inputs, list):
                for raw_record, expected_role in zip(
                    source_inputs,
                    CLOSURE_COMMON_ORIGIN_SOURCE_ROLES,
                    strict=False,
                ):
                    record = cast(dict[str, Any], raw_record) if isinstance(raw_record, dict) else None
                    if (
                        record is None
                        or record.get("role") != expected_role
                        or record.get("hash_source") != "protocol_lock"
                    ):
                        findings.append(
                            ReproducibilityFinding(
                                "fail",
                                "manifest",
                                manifest_path.as_posix(),
                                "Closure common-origin source roles/hash_source are invalid.",
                            )
                        )
                        break

            if isinstance(parent_artifacts, list):
                for raw_record, (_, expected_role) in zip(
                    parent_artifacts,
                    CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES,
                    strict=False,
                ):
                    record = cast(dict[str, Any], raw_record) if isinstance(raw_record, dict) else None
                    if record is None or record.get("role") != expected_role:
                        findings.append(
                            ReproducibilityFinding(
                                "fail",
                                "manifest",
                                manifest_path.as_posix(),
                                "Closure common-origin parent roles are invalid.",
                            )
                        )
                        break

            assignment = payload.get("assignment") if isinstance(payload, dict) else None
            assignment_parent = (
                parent_artifacts[2]
                if isinstance(parent_artifacts, list) and len(parent_artifacts) == 3
                else None
            )
            if (
                not isinstance(assignment, dict)
                or assignment.get("path")
                != CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES[2][0].as_posix()
                or type(assignment.get("bytes")) is not int
                or assignment.get("bytes", -1) < 0
                or not isinstance(assignment.get("sha256"), str)
                or assignment.get("eligible_locations") != 441
                or assignment.get("development_locations") != 353
                or assignment.get("holdout_locations") != 88
                or assignment.get("holdout_fit_overlap_count") != 0
                or not isinstance(assignment_parent, dict)
                or assignment_parent.get("bytes") != assignment.get("bytes")
                or assignment_parent.get("sha256") != assignment.get("sha256")
            ):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure common-origin assignment provenance is invalid.",
                    )
                )

            generating_scripts = (
                [
                    record
                    for record in code
                    if manifest_record_path(record)
                    == CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT
                ]
                if isinstance(code, list)
                else []
            )
            if len(generating_scripts) != 1:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        (
                            "Closure common-origin manifest must contain exactly one "
                            "generating-script record for "
                            f"`{CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT}`."
                        ),
                    )
                )
            script = generating_scripts[0] if len(generating_scripts) == 1 else None
        else:
            script = payload.get("script") if isinstance(payload, dict) else None
            inputs = payload.get("inputs") if isinstance(payload, dict) else None

        if isinstance(script, dict):
            verify_manifest_file_record(
                record=script,
                manifest_path=manifest_path,
                section="script",
                findings=findings,
                max_hash_bytes=max_hash_bytes,
                require_hash=True,
                force_hash=True,
            )
        elif not is_closure_protocol_lock and not is_closure_common_origin_manifest:
            findings.append(
                ReproducibilityFinding(
                    "warn",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest does not record the generating script.",
                )
            )

        if isinstance(inputs, list):
            for record in inputs:
                verify_manifest_file_record(
                    record=record,
                    manifest_path=manifest_path,
                    section="input",
                    findings=findings,
                    max_hash_bytes=max_hash_bytes,
                    require_hash=(
                        verify_manifest_inputs or is_closure_common_origin_manifest
                    ),
                    force_hash=is_closure_common_origin_manifest,
                )
        elif inputs is None:
            findings.append(
                ReproducibilityFinding(
                    "warn",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest does not record inputs.",
                )
            )
        else:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest `inputs` field must be a list when present.",
                )
            )

    for path in report_artifacts:
        if path not in covered_outputs:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    path.as_posix(),
                    "Staged report artifact is not listed in any experiment manifest output.",
                )
            )

    staged_dvc_outputs = [
        path
        for path in covered_outputs
        if is_artifact_covered(path.as_posix(), artifacts) and dvc_pointer_path(path).exists()
    ]
    findings.append(
        ReproducibilityFinding(
            "ok",
            "manifest",
            "-",
            (
                f"Checked {len(manifest_paths)} experiment manifest(s), {checked_outputs} output record(s), "
                f"and {len(report_artifacts)} staged report artifact(s). "
                f"{len(staged_dvc_outputs)} covered output(s) are also protected by DVC pointers."
            ),
        )
    )
    return findings


def validate_dvc_pointers(staged_paths: set[Path], selected_dvc_paths: list[Path]) -> list[ReproducibilityFinding]:
    findings: list[ReproducibilityFinding] = []
    pointer_paths = {path for path in staged_paths if path.suffix == ".dvc"}
    pointer_paths.update(dvc_pointer_path(path) for path in selected_dvc_paths)

    if not pointer_paths:
        return [ReproducibilityFinding("ok", "dvc", "-", "No DVC pointer files need pointer-structure validation.")]

    for pointer_path in sorted(pointer_paths, key=lambda path: path.as_posix()):
        if not pointer_path.exists():
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "dvc",
                    pointer_path.as_posix(),
                    "Expected DVC pointer file does not exist.",
                )
            )
            continue
        try:
            payload = yaml.safe_load(pointer_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "dvc",
                    pointer_path.as_posix(),
                    f"DVC pointer is not valid YAML: {exc}.",
                )
            )
            continue
        outs = payload.get("outs") if isinstance(payload, dict) else None
        if not isinstance(outs, list) or not outs:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "dvc",
                    pointer_path.as_posix(),
                    "DVC pointer must contain a non-empty `outs` list.",
                )
            )
            continue
        for out in outs:
            if not isinstance(out, dict) or not out.get("path") or not out.get("md5"):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "dvc",
                        pointer_path.as_posix(),
                        "Each DVC pointer output must include `path` and `md5`.",
                    )
                )
                break

    if not any(finding.level == "fail" and finding.check == "dvc" for finding in findings):
        findings.append(
            ReproducibilityFinding(
                "ok",
                "dvc",
                "-",
                f"Validated {len(pointer_paths)} DVC pointer file(s).",
            )
        )
    return findings


def is_freeze_sensitive_path(path: Path) -> bool:
    text = path.as_posix()
    if path in FREEZE_ARTIFACT_PATHS:
        return False
    if text in FREEZE_SENSITIVE_EXACT_PATHS:
        return True
    return any(text.startswith(prefix) for prefix in FREEZE_SENSITIVE_PREFIXES)


def validate_freeze_freshness(staged_rows: list[tuple[str, Path]]) -> list[ReproducibilityFinding]:
    changed_paths = {path for _, path in staged_rows}
    sensitive_paths = sorted(
        {path for path in changed_paths if is_freeze_sensitive_path(path)},
        key=lambda path: path.as_posix(),
    )
    changed_freeze_outputs = changed_paths.intersection(FREEZE_REQUIRED_OUTPUTS)
    freeze_documentation_only = (
        sensitive_paths == [Path("src/data/freeze.py")]
        and bool(changed_freeze_outputs)
        and changed_freeze_outputs.issubset(FREEZE_DOCUMENTATION_OUTPUTS)
    )
    findings: list[ReproducibilityFinding] = []

    if sensitive_paths:
        if freeze_documentation_only:
            findings.append(
                ReproducibilityFinding(
                    "ok",
                    "freeze",
                    "src/data/freeze.py",
                    "Freeze generator documentation changes are paired with freeze Markdown/JSON metadata; derived file hashes are not required.",
                )
            )
        else:
            missing_freeze_outputs = sorted(FREEZE_REQUIRED_OUTPUTS - changed_paths, key=lambda path: path.as_posix())
            if missing_freeze_outputs:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "freeze",
                        ", ".join(path.as_posix() for path in sensitive_paths[:5]),
                        (
                            "Freeze-sensitive data pipeline changes are staged, but not all required "
                            f"freeze outputs are staged: {', '.join(path.as_posix() for path in missing_freeze_outputs)}."
                        ),
                    )
                )
            else:
                findings.append(
                    ReproducibilityFinding(
                        "ok",
                        "freeze",
                        "-",
                        f"Freeze-sensitive changes are paired with {len(FREEZE_REQUIRED_OUTPUTS)} required freeze outputs.",
                    )
                )
    else:
        findings.append(
            ReproducibilityFinding(
                "ok",
                "freeze",
                "-",
                "No freeze-sensitive data pipeline changes are staged.",
            )
        )

    if changed_freeze_outputs and changed_freeze_outputs != FREEZE_REQUIRED_OUTPUTS and not freeze_documentation_only:
        findings.append(
            ReproducibilityFinding(
                "fail",
                "freeze",
                ", ".join(path.as_posix() for path in sorted(changed_freeze_outputs, key=lambda path: path.as_posix())),
                "A data-freeze update must stage derived CSV, JSON manifest, and DATA_FREEZE.md together.",
            )
        )

    if DEFAULT_DVC_ARTIFACT_INVENTORY in changed_paths and not sensitive_paths:
        findings.append(
            ReproducibilityFinding(
                "ok",
                "freeze",
                DEFAULT_DVC_ARTIFACT_INVENTORY.as_posix(),
                (
                    "DVC artifact inventory changed, but no freeze-sensitive data pipeline paths "
                    "are staged; data-freeze regeneration is not required by this check."
                ),
            )
        )

    return findings


def reproducibility_checks(
    *,
    staged_status: str,
    selected_dvc_paths: list[Path],
    artifacts: list[DvcArtifact],
    max_manifest_hash_bytes: int,
    verify_manifest_inputs: bool,
) -> list[ReproducibilityFinding]:
    staged_rows = parse_git_name_status(staged_status)
    staged_paths = {path for status, path in staged_rows if not status.startswith("D")}
    findings: list[ReproducibilityFinding] = []
    findings.extend(validate_dvc_pointers(staged_paths, selected_dvc_paths))
    findings.extend(
        validate_experiment_manifests(
            staged_paths=staged_paths,
            artifacts=artifacts,
            max_hash_bytes=max_manifest_hash_bytes,
            verify_manifest_inputs=verify_manifest_inputs,
        )
    )
    findings.extend(validate_freeze_freshness(staged_rows))
    return findings


def has_failing_findings(findings: list[ReproducibilityFinding]) -> bool:
    return any(finding.level == "fail" for finding in findings)


def prompt_yes_no(question: str, *, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def print_artifact_table(title: str, artifacts: list[DvcArtifact]) -> None:
    print()
    print(title)
    if not artifacts:
        print("  none")
        return
    for artifact in artifacts:
        print(f"  - {artifact.path} ({artifact.artifact_id}, {artifact.artifact_type})")


def print_path_table(title: str, paths: list[Path]) -> None:
    print()
    print(title)
    if not paths:
        print("  none")
        return
    for path in paths:
        print(f"  - {path}")


def unique_paths(paths: list[Path]) -> list[Path]:
    return sorted(set(paths), key=lambda path: path.as_posix())


def default_report_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_REPORT_DIR / f"pre_commit_artifacts_{timestamp}.md"


def write_report(
    report_path: Path,
    *,
    dry_run: bool,
    selected_dvc_paths: list[Path],
    rejected_unmanaged_paths: list[Path],
    git_status_before: str,
    dvc_status_before: dict[str, Any],
    cloud_status_before: CommandResult | None,
    dvc_add_results: list[CommandResult],
    dvc_push_result: CommandResult | None,
    git_add_result: CommandResult | None,
    publication_check_result: CommandResult | None,
    reproducibility_findings: list[ReproducibilityFinding],
    staged_status: str,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pre-Commit Artifact Preparation Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Dry run: `{dry_run}`",
        "",
        "## Selected DVC Targets",
        "",
    ]
    if selected_dvc_paths:
        lines.extend(f"- `{path.as_posix()}`" for path in selected_dvc_paths)
    else:
        lines.append("- none")

    lines.extend(["", "## Rejected Unmanaged Heavy Paths", ""])
    if rejected_unmanaged_paths:
        lines.extend(f"- `{path.as_posix()}`" for path in rejected_unmanaged_paths)
    else:
        lines.append("- none")

    lines.extend(["", "## Git Status Before", "", "```text", git_status_before.rstrip() or "clean", "```"])
    lines.extend(
        [
            "",
            "## DVC Status Before",
            "",
            "```json",
            json.dumps(dvc_status_before, indent=2, sort_keys=True),
            "```",
        ]
    )

    lines.extend(["", "## DVC Cloud Status Before Push", ""])
    if cloud_status_before is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                f"Command: `{command_text(cloud_status_before.command)}`",
                "",
                "```text",
                cloud_status_before.stdout.rstrip() or cloud_status_before.stderr.rstrip() or "(no output)",
                "```",
            ]
        )

    lines.extend(["", "## DVC Add Commands", ""])
    if dvc_add_results:
        for result in dvc_add_results:
            lines.extend(
                [
                    f"### `{command_text(result.command)}`",
                    "",
                    f"Exit code: `{result.returncode}`",
                    "",
                    "```text",
                    (result.stdout + result.stderr).rstrip() or "(no output)",
                    "```",
                    "",
                ]
            )
    else:
        lines.append("No DVC add commands were run.")

    lines.extend(["", "## DVC Push", ""])
    if dvc_push_result is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                f"Command: `{command_text(dvc_push_result.command)}`",
                "",
                f"Exit code: `{dvc_push_result.returncode}`",
                "",
                "```text",
                (dvc_push_result.stdout + dvc_push_result.stderr).rstrip() or "(no output)",
                "```",
            ]
        )

    lines.extend(["", "## Git Add", ""])
    if git_add_result is None:
        lines.append("Not run.")
    else:
        lines.extend([f"Command: `{command_text(git_add_result.command)}`", f"Exit code: `{git_add_result.returncode}`"])

    lines.extend(["", "## Publication Check", ""])
    if publication_check_result is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                f"Command: `{command_text(publication_check_result.command)}`",
                "",
                f"Exit code: `{publication_check_result.returncode}`",
                "",
                "```text",
                (publication_check_result.stdout + publication_check_result.stderr).rstrip() or "(no output)",
                "```",
            ]
        )

    lines.extend(["", "## Reproducibility Checks", ""])
    if reproducibility_findings:
        for finding in reproducibility_findings:
            lines.append(
                f"- `{finding.level.upper()}` `{finding.check}` `{finding.path}`: {finding.message}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Staged Status After Preparation", "", "```text", staged_status.rstrip() or "none", "```", ""])
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Git and DVC artifacts before a manual commit.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_DVC_MANIFEST)
    parser.add_argument("--dvc-bin", default=None)
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Local report path. Defaults to a timestamped file under ignored tmp/.",
    )
    parser.add_argument("--target", action="append", default=[], help="Additional path to track with dvc add.")
    parser.add_argument("--jobs", default=None, help="DVC push jobs.")
    parser.add_argument("--yes", action="store_true", help="Accept DVC add prompts.")
    parser.add_argument("--dry-run", action="store_true", help="Print and report actions without changing Git/DVC.")
    parser.add_argument("--no-push", action="store_true", help="Run dvc add and git add, but skip dvc push.")
    parser.add_argument("--allow-unmanaged", action="store_true", help="Do not fail if unmanaged heavy paths are rejected.")
    parser.add_argument("--skip-publication-check", action="store_true")
    parser.add_argument(
        "--max-manifest-hash-bytes",
        type=int,
        default=DEFAULT_MAX_MANIFEST_HASH_BYTES,
        help="Maximum file size for recomputing experiment-manifest SHA-256 outputs.",
    )
    parser.add_argument(
        "--verify-manifest-inputs",
        action="store_true",
        help="Also recompute SHA-256 hashes for experiment-manifest inputs within the size limit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_repo_root()
    report_path = args.report or default_report_path()
    dvc_bin = resolve_dvc_bin(args.dvc_bin)
    artifacts = load_configured_dvc_artifacts(args.manifest)

    git_status_before = versionable_changes()
    dvc_status_before = dvc_status_json(dvc_bin)
    changed_artifacts = dvc_status_candidates(dvc_status_before, artifacts)
    missing_pointer_artifacts = declared_artifacts_missing_pointers(artifacts)
    manual_targets = unique_paths([Path(path) for path in args.target])
    unmanaged_paths = unmanaged_ignored_heavy_paths(artifacts)

    if dvc_status_before and not changed_artifacts and not missing_pointer_artifacts and not manual_targets:
        print("DVC status reports changes, but no declared artifact could be matched.", file=sys.stderr)
        print("Review `dvc status` and rerun with one or more `--target PATH` options.", file=sys.stderr)
        return 1

    print("Pre-commit artifact assistant")
    print_artifact_table("DVC-tracked artifacts changed according to dvc status:", changed_artifacts)
    print_artifact_table("Declared DVC artifacts missing pointer files:", missing_pointer_artifacts)
    print_path_table("Additional manual DVC targets:", manual_targets)
    print_path_table("Unmanaged ignored heavy paths:", unmanaged_paths)

    selected_dvc_paths = [artifact.path for artifact in changed_artifacts]
    selected_dvc_paths.extend(artifact.path for artifact in missing_pointer_artifacts)
    selected_dvc_paths.extend(manual_targets)

    rejected_unmanaged: list[Path] = []
    if unmanaged_paths:
        if args.yes:
            selected_dvc_paths.extend(unmanaged_paths)
        else:
            for path in unmanaged_paths:
                if prompt_yes_no(f"Add ignored heavy path to DVC: {path}?", default=False):
                    selected_dvc_paths.append(path)
                else:
                    rejected_unmanaged.append(path)

    selected_dvc_paths = unique_paths(selected_dvc_paths)

    if changed_artifacts and not args.yes:
        if not prompt_yes_no("Run dvc add for the changed DVC-tracked artifacts?", default=True):
            print("DVC changes were detected but not accepted for dvc add.", file=sys.stderr)
            return 1

    if rejected_unmanaged and not args.allow_unmanaged:
        print("Unmanaged heavy paths were rejected. Use --allow-unmanaged only if this is intentional.", file=sys.stderr)
        return 1

    print_path_table("Selected DVC add targets:", selected_dvc_paths)

    cloud_status_before: CommandResult | None = None
    dvc_add_results: list[CommandResult] = []
    dvc_push_result: CommandResult | None = None
    git_add_result: CommandResult | None = None
    publication_check_result: CommandResult | None = None
    reproducibility_findings: list[ReproducibilityFinding] = []

    if args.dry_run:
        print()
        print("Dry run. No Git or DVC mutations will be made.")
        for path in selected_dvc_paths:
            print(f"would run: {command_text([dvc_bin, 'add', path.as_posix()])}")
        if not args.no_push:
            print(f"would run: {command_text([dvc_bin, 'push'])}")
        print("would run: git add -A")
    else:
        for path in selected_dvc_paths:
            if not path.exists():
                print(f"Selected DVC target does not exist: {path}", file=sys.stderr)
                return 2
            dvc_add_results.append(run_command([dvc_bin, "add", path.as_posix()], env=dvc_environment()))

        if not args.no_push:
            cloud_status_before = run_command([dvc_bin, "status", "--cloud"], check=False, env=dvc_environment())
            push_command = [dvc_bin, "push"]
            if args.jobs:
                push_command.extend(["--jobs", str(args.jobs)])
            dvc_push_result = run_command(push_command, env=dvc_environment())

    if not args.dry_run:
        publication_check_result = None
        if not args.skip_publication_check:
            publication_check_result = run_command(["scripts/check_repo_publication_ready.sh"], check=False)
            if publication_check_result.returncode != 0:
                print(publication_check_result.stdout)
                print(publication_check_result.stderr, file=sys.stderr)
                print("Publication check failed; not staging changes.", file=sys.stderr)
                return publication_check_result.returncode

        git_add_result = run_command(["git", "add", "-A"])
        staged_status = run_command(["git", "diff", "--cached", "--name-status"]).stdout
        reproducibility_findings = reproducibility_checks(
            staged_status=staged_status,
            selected_dvc_paths=selected_dvc_paths,
            artifacts=artifacts,
            max_manifest_hash_bytes=args.max_manifest_hash_bytes,
            verify_manifest_inputs=args.verify_manifest_inputs,
        )
        write_report(
            report_path,
            dry_run=args.dry_run,
            selected_dvc_paths=selected_dvc_paths,
            rejected_unmanaged_paths=rejected_unmanaged,
            git_status_before=git_status_before,
            dvc_status_before=dvc_status_before,
            cloud_status_before=cloud_status_before,
            dvc_add_results=dvc_add_results,
            dvc_push_result=dvc_push_result,
            git_add_result=git_add_result,
            publication_check_result=publication_check_result,
            reproducibility_findings=reproducibility_findings,
            staged_status=staged_status,
        )
        if has_failing_findings(reproducibility_findings):
            print()
            print("Reproducibility checks failed; fix the findings and rerun the assistant.", file=sys.stderr)
            print(f"Report written: {report_path}", file=sys.stderr)
            return 1
    else:
        staged_status = "dry run"
        reproducibility_findings = [
            ReproducibilityFinding(
                "warn",
                "reproducibility",
                "-",
                "Dry run: final staged reproducibility checks were not executed.",
            )
        ]
        write_report(
            report_path,
            dry_run=args.dry_run,
            selected_dvc_paths=selected_dvc_paths,
            rejected_unmanaged_paths=rejected_unmanaged,
            git_status_before=git_status_before,
            dvc_status_before=dvc_status_before,
            cloud_status_before=None,
            dvc_add_results=[],
            dvc_push_result=None,
            git_add_result=None,
            publication_check_result=None,
            reproducibility_findings=reproducibility_findings,
            staged_status=staged_status,
        )

    print()
    print(f"Report written: {report_path}")
    if not args.dry_run:
        print("Changes are staged. Review with:")
        print("  git diff --cached --stat")
        print("  git diff --cached --name-status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
