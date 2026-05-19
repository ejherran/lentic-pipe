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
from typing import Any

import yaml


DEFAULT_DVC_MANIFEST = Path("configs/dvc_artifacts.yaml")
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
REGENERABLE_IGNORED_PATHS = {
    "data/interim/observations/observations_summary.csv",
}
REPORT_ARTIFACT_SUFFIXES = {".csv", ".json", ".md", ".parquet", ".txt"}
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
    return text.startswith("reports/") and path.suffix == ".json" and "manifest" in path.name


def is_report_artifact_path(path: Path) -> bool:
    text = path.as_posix()
    if not text.startswith("reports/"):
        return False
    if text.startswith("reports/data/"):
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
        expected_bytes = record.get("bytes")
        if isinstance(expected_bytes, int):
            actual_bytes = actual_path.stat().st_size
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

        actual_bytes = actual_path.stat().st_size
        should_hash = force_hash or (require_hash and actual_bytes <= max_hash_bytes)
        if should_hash:
            actual_sha = sha256_file(actual_path)
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
    for path in staged_paths:
        if not is_report_artifact_path(path):
            continue
        if not path.parent.exists():
            continue
        for candidate in path.parent.glob("*manifest*.json"):
            if not is_experiment_manifest_path(candidate):
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            outputs = payload.get("outputs") if isinstance(payload, dict) else None
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

        if isinstance(payload, dict) and payload.get("status") not in {None, "completed"}:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    f"Experiment manifest status is `{payload.get('status')}`, expected `completed`.",
                )
            )

        outputs = payload.get("outputs") if isinstance(payload, dict) else None
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

        for record in outputs:
            record_path = verify_manifest_file_record(
                record=record,
                manifest_path=manifest_path,
                section="output",
                findings=findings,
                max_hash_bytes=max_hash_bytes,
                require_hash=True,
            )
            if record_path is not None:
                covered_outputs.setdefault(record_path, []).append(manifest_path)
                checked_outputs += 1

        script = payload.get("script") if isinstance(payload, dict) else None
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
        else:
            findings.append(
                ReproducibilityFinding(
                    "warn",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest does not record the generating script.",
                )
            )

        inputs = payload.get("inputs") if isinstance(payload, dict) else None
        if isinstance(inputs, list):
            for record in inputs:
                verify_manifest_file_record(
                    record=record,
                    manifest_path=manifest_path,
                    section="input",
                    findings=findings,
                    max_hash_bytes=max_hash_bytes,
                    require_hash=verify_manifest_inputs,
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
    findings: list[ReproducibilityFinding] = []

    if sensitive_paths:
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

    if changed_freeze_outputs and changed_freeze_outputs != FREEZE_REQUIRED_OUTPUTS:
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
    artifacts = load_dvc_artifacts(args.manifest)

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
