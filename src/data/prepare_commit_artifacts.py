#!/usr/bin/env python
"""Prepare Git and DVC artifacts before a manual commit."""

from __future__ import annotations

import argparse
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


def command_text(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


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


def parse_git_status_lines(output: str) -> list[tuple[str, str]]:
    rows = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        rows.append((line[:2], line[3:]))
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
    manual_targets = unique_paths([Path(path) for path in args.target])
    unmanaged_paths = unmanaged_ignored_heavy_paths(artifacts)

    if dvc_status_before and not changed_artifacts and not manual_targets:
        print("DVC status reports changes, but no declared artifact could be matched.", file=sys.stderr)
        print("Review `dvc status` and rerun with one or more `--target PATH` options.", file=sys.stderr)
        return 1

    print("Pre-commit artifact assistant")
    print_artifact_table("DVC-tracked artifacts changed according to dvc status:", changed_artifacts)
    print_path_table("Additional manual DVC targets:", manual_targets)
    print_path_table("Unmanaged ignored heavy paths:", unmanaged_paths)

    selected_dvc_paths = [artifact.path for artifact in changed_artifacts]
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
            staged_status=staged_status,
        )
    else:
        staged_status = "dry run"
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
