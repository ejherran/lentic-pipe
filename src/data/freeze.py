#!/usr/bin/env python
"""Create a data freeze document and derived artifact manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pandas_utils import dataframe_rows


DEFAULT_RAW_MANIFEST = Path("data/catalog/raw_file_manifest.csv")
DEFAULT_SOURCE_CATALOG = Path("data/catalog/source_catalog.json")
DEFAULT_OBSERVATIONS_DIR = Path("data/interim/observations")
DEFAULT_SITE_REGISTRY = Path("data/interim/site_registry.parquet")
DEFAULT_PANEL_MANIFEST = Path("data/panel/monthly_panel_manifest_v0.json")
DEFAULT_TARGET_MANIFEST = Path("data/targets/target_manifest_v0.json")
DEFAULT_DIAGNOSTIC_MANIFEST = Path("data/diagnostics/diagnostic_manifest_v0.json")
DEFAULT_OUTPUT_DIR = Path("data/freeze")
DEFAULT_DERIVED_MANIFEST = DEFAULT_OUTPUT_DIR / "derived_file_manifest_v0.csv"
DEFAULT_FREEZE_JSON = DEFAULT_OUTPUT_DIR / "data_freeze_manifest_v0.json"
DEFAULT_FREEZE_MD = DEFAULT_OUTPUT_DIR / "DATA_FREEZE.md"


HASH_CHUNK_SIZE = 16 * 1024 * 1024

EXACT_GENERATION_COMMANDS = [
    ".venv/bin/python src/data/validate_sources.py",
    ".venv/bin/python src/data/raw_manifest.py --reuse-existing",
    ".venv/bin/python src/data/build_observations.py --source lakebed_us_cse --chunksize 250000 --overwrite",
    ".venv/bin/python src/data/build_observations.py --source aquamatch_chla --chunksize 250000 --overwrite",
    ".venv/bin/python src/data/build_observations.py --source wqp --chunksize 250000 --overwrite",
    ".venv/bin/python src/data/report_observations.py",
    ".venv/bin/python src/data/site_registry.py",
    ".venv/bin/python src/data/build_panel.py --overwrite --progress-every-parts 25",
    ".venv/bin/python src/data/build_targets.py --overwrite",
    ".venv/bin/python src/data/diagnose_panel_targets.py --overwrite",
    ".venv/bin/python src/data/freeze.py --overwrite",
]


@dataclass(frozen=True)
class FileRecord:
    category: str
    path: str
    size_bytes: int
    modified_time_utc: str
    sha256: str


def sha256_file(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def format_bytes(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def format_int(value: int) -> str:
    return f"{value:,}"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unavailable"


def git_dirty_status() -> str:
    status = git_value("status", "--short")
    return status or "clean"


def collect_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            files.append(path)
        else:
            files.extend(sorted(item for item in path.rglob("*") if item.is_file()))
    return sorted(
        set(
            path
            for path in files
            if "__pycache__" not in path.parts and path.suffix != ".pyc" and not path.name.endswith(".tmp")
        )
    )


def category_for_path(path: Path) -> str:
    text = path.as_posix()
    if text.startswith("configs/"):
        return "config"
    if text.startswith("data/scripts/"):
        return "source_download_script"
    if text.startswith("scripts/"):
        return "repo_script"
    if text.startswith("docs/"):
        return "documentation"
    if text.startswith("src/"):
        return "script"
    if text.startswith("data/catalog/"):
        return "catalog"
    if text.startswith("data/interim/observations/"):
        return "canonical_observations"
    if text.startswith("data/interim/"):
        return "interim"
    if text.startswith("data/panel/") and "_monthly_partials" not in text:
        return "panel"
    if text.startswith("data/targets/"):
        return "targets"
    if text.startswith("data/diagnostics/"):
        return "diagnostics"
    if text.startswith("reports/data/"):
        return "reports"
    if text.startswith("reports/repo_audit/"):
        return "repo_audit"
    if text in {"pyproject.toml", "poetry.lock", "poetry.toml", "README.md"}:
        return "environment"
    return "other"


def build_file_records(paths: list[Path]) -> list[FileRecord]:
    records = []
    for index, path in enumerate(paths, start=1):
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        print(f"hashing {index}/{len(paths)} {path}", flush=True)
        records.append(
            FileRecord(
                category=category_for_path(path),
                path=path.as_posix(),
                size_bytes=stat.st_size,
                modified_time_utc=modified.isoformat(),
                sha256=sha256_file(path),
            )
        )
    return records


def write_records_csv(records: list[FileRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    fieldnames = list(asdict(records[0]).keys()) if records else list(FileRecord.__dataclass_fields__)
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))
    tmp_path.replace(path)


def write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    tmp_path.replace(path)


def load_observation_manifests(observations_dir: Path) -> list[dict[str, Any]]:
    manifests = []
    for manifest_path in sorted(observations_dir.glob("*/_manifest.json")):
        manifests.append(read_json(manifest_path))
    return manifests


def source_date_ranges() -> pd.DataFrame:
    coverage_path = Path("data/diagnostics/coverage_by_source.csv")
    if coverage_path.exists():
        return pd.read_csv(coverage_path)
    return pd.DataFrame(columns=["source_id", "site_month_rows", "sites", "start_year_month", "end_year_month"])


def derived_summary(records: list[FileRecord]) -> list[dict[str, Any]]:
    rows = []
    for category in sorted({record.category for record in records}):
        subset = [record for record in records if record.category == category]
        rows.append(
            {
                "category": category,
                "files": len(subset),
                "size_bytes": sum(record.size_bytes for record in subset),
            }
        )
    return rows


def write_freeze_md(
    path: Path,
    payload: dict[str, Any],
    source_catalog: dict[str, Any],
    raw_manifest_stats: dict[str, Any],
    observation_manifests: list[dict[str, Any]],
    date_ranges: pd.DataFrame,
    panel_manifest: dict[str, Any],
    target_manifest: dict[str, Any],
    diagnostic_manifest: dict[str, Any],
    records: list[FileRecord],
) -> None:
    by_category = derived_summary(records)
    lines = [
        "# DATA_FREEZE v0",
        "",
        f"Generated at UTC: `{payload['generated_at_utc']}`",
        f"Repository commit: `{payload['git_commit']}`",
        f"Worktree status: `{payload['git_dirty_state']}`",
        f"Python constraint: `{payload['python_constraint']}`",
        "",
        "## Scope",
        "",
        "This freeze captures the current raw fingerprints, canonical observations, monthly panel, target tables, and diagnostics used before temporal splits and baselines.",
        "",
        "Downstream experiments must reference this freeze. If raw files, canonicalization logic, panel logic, target logic, or diagnostics change, regenerate this freeze before trusting new results.",
        "",
        "## Raw Sources",
        "",
        f"Raw manifest: `{payload['raw_manifest']}`",
        f"Raw source catalog: `{payload['source_catalog']}`",
        f"Raw files: `{format_int(raw_manifest_stats['file_count'])}`",
        f"Raw total size: `{format_bytes(raw_manifest_stats['total_size_bytes'])}`",
        "",
        "| source_id | files | size | license | provenance_status | raw_path |",
        "|---|---:|---:|---|---|---|",
    ]
    for source_id, source in source_catalog["sources"].items():
        lines.append(
            f"| `{source_id}` | {format_int(int(source['file_count']))} | {format_bytes(int(source['total_size_bytes']))} | "
            f"{source.get('license')} | {source.get('provenance_status')} | `{source.get('raw_path')}` |"
        )

    lines.extend(
        [
            "",
            "## Canonical Observations",
            "",
            "| source_id | adapter | status | chunks | rows | output_dir |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    for manifest in observation_manifests:
        lines.append(
            f"| `{manifest['source_id']}` | `{manifest['adapter']}` | {manifest.get('status')} | "
            f"{format_int(len(manifest.get('chunks', [])))} | {format_int(int(manifest.get('row_count', 0)))} | "
            f"`{manifest.get('output_dir')}` |"
        )

    lines.extend(["", "## Source-Site-Month Coverage", "", "| source_id | site-month rows | sites | start | end |", "|---|---:|---:|---|---|"])
    for row in dataframe_rows(date_ranges):
        lines.append(
            f"| `{row.source_id}` | {format_int(int(row.site_month_rows))} | {format_int(int(row.sites))} | "
            f"`{row.start_year_month}` | `{row.end_year_month}` |"
        )

    lines.extend(
        [
            "",
            "## Panel And Targets",
            "",
            "| artifact | rows | path |",
            "|---|---:|---|",
            f"| monthly long panel | {format_int(int(panel_manifest['long_rows']))} | `{panel_manifest['long_panel']}` |",
            f"| monthly wide panel | {format_int(int(panel_manifest['wide_rows']))} | `{panel_manifest['wide_panel']}` |",
            f"| target candidates | {format_int(int(target_manifest['target_candidate_rows']))} | `{target_manifest['long_targets']}` |",
            f"| model targets | {format_int(int(target_manifest['model_target_rows']))} | `{target_manifest['model_long_targets']}` |",
            f"| panel with targets | {format_int(int(target_manifest['panel_rows']))} | `{target_manifest['panel_with_targets']}` |",
        ]
    )

    lines.extend(
        [
            "",
            "## Target Policy",
            "",
            f"- Horizons: `{target_manifest['horizons_months']}` months.",
            f"- Bloom threshold: `{target_manifest['bloom_threshold_chla_ugL']} ug/L`.",
            f"- Risk policy: `{target_manifest['risk_policy']}`.",
            f"- Trophic state proxy: `{target_manifest['trophic_state_proxy']}`.",
            "- Targets are source-scoped by `source_id` and `site_id`; no cross-source site equivalence is assumed.",
            "",
            "## Diagnostics",
            "",
            f"Diagnostic report: `{diagnostic_manifest['report']}`",
            f"Rows with target: `{format_int(int(diagnostic_manifest['target_rows']))}`",
            f"Bloom-positive target rows across all horizons: `{format_int(int(diagnostic_manifest['bloom_positive_rows']))}`",
            "",
            "## Derived Artifact Hashes",
            "",
            f"Derived manifest: `{payload['derived_manifest']}`",
            "",
            "| category | files | size |",
            "|---|---:|---:|",
        ]
    )
    for row in by_category:
        lines.append(f"| `{row['category']}` | {format_int(int(row['files']))} | {format_bytes(int(row['size_bytes']))} |")

    important_paths = [
        "data/panel/monthly_long_v0.parquet",
        "data/panel/panel_monthly_v0.parquet",
        "data/targets/monthly_targets_long_v0.parquet",
        "data/targets/monthly_targets_model_v0.parquet",
        "data/targets/panel_monthly_with_targets_v0.parquet",
        "data/diagnostics/diagnostic_manifest_v0.json",
    ]
    by_path = {record.path: record for record in records}
    lines.extend(["", "### Key Derived SHA-256", "", "| path | sha256 |", "|---|---|"])
    for item in important_paths:
        record = by_path.get(item)
        if record:
            lines.append(f"| `{record.path}` | `{record.sha256}` |")

    lines.extend(
        [
            "",
            "## Exact Generation Commands",
            "",
            "```bash",
            *EXACT_GENERATION_COMMANDS,
            "```",
            "",
            "## Inclusion And Exclusion Criteria",
            "",
            "- Include only declared sources from `configs/sources.yaml`.",
            "- Preserve raw files unchanged under `data/raw` and trust only files recorded in `data/catalog/raw_file_manifest.csv`.",
            "- Canonical observations include mapped variables from `configs/variables.yaml` after unit conversion and QC flagging.",
            "- Monthly panel values use only `qc_flag == ok` and non-null canonical values.",
            "- Bad observations are retained as counts but do not contribute to monthly means.",
            "- WQP date parsing uses mixed date formats; pH blank units are accepted as assumed dimensionless with trace `assume_blank_unit_dimensionless`.",
            "- Targets require future monthly mean Chl-a for the same source-scoped site.",
            "",
            "## Integrity Rule",
            "",
            "Do not train baselines, PIPE, or MIFAL against data that differs from this freeze. Any change to raw files, canonical adapters, panel construction, target construction, or diagnostics requires a new freeze.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text("\n".join(lines), encoding="utf-8")
    tmp_path.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create DATA_FREEZE.md and derived file hashes.")
    parser.add_argument("--raw-manifest", type=Path, default=DEFAULT_RAW_MANIFEST)
    parser.add_argument("--source-catalog", type=Path, default=DEFAULT_SOURCE_CATALOG)
    parser.add_argument("--observations-dir", type=Path, default=DEFAULT_OBSERVATIONS_DIR)
    parser.add_argument("--site-registry", type=Path, default=DEFAULT_SITE_REGISTRY)
    parser.add_argument("--panel-manifest", type=Path, default=DEFAULT_PANEL_MANIFEST)
    parser.add_argument("--target-manifest", type=Path, default=DEFAULT_TARGET_MANIFEST)
    parser.add_argument("--diagnostic-manifest", type=Path, default=DEFAULT_DIAGNOSTIC_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--derived-manifest", type=Path, default=DEFAULT_DERIVED_MANIFEST)
    parser.add_argument("--freeze-json", type=Path, default=DEFAULT_FREEZE_JSON)
    parser.add_argument("--freeze-md", type=Path, default=DEFAULT_FREEZE_MD)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = [args.derived_manifest, args.freeze_json, args.freeze_md]
    existing = [path for path in outputs if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"Output exists: {existing}. Use --overwrite to replace freeze outputs.")

    source_catalog = read_json(args.source_catalog)
    panel_manifest = read_json(args.panel_manifest)
    target_manifest = read_json(args.target_manifest)
    diagnostic_manifest = read_json(args.diagnostic_manifest)
    observation_manifests = load_observation_manifests(args.observations_dir)
    date_ranges = source_date_ranges()
    raw_manifest_df = pd.read_csv(args.raw_manifest)
    raw_manifest_stats = {
        "file_count": int(len(raw_manifest_df)),
        "total_size_bytes": int(raw_manifest_df["size_bytes"].sum()),
    }

    paths_to_hash = collect_files(
        [
            Path("configs"),
            Path("data/scripts"),
            Path("docs"),
            Path("scripts"),
            Path("src/data"),
            Path("README.md"),
            Path("pyproject.toml"),
            Path("poetry.lock"),
            Path("poetry.toml"),
            args.raw_manifest,
            args.source_catalog,
            args.observations_dir,
            args.site_registry,
            Path("data/interim/site_registry.csv"),
            Path("data/interim/observations/observations_summary.csv"),
            Path("data/panel/monthly_long_v0.parquet"),
            Path("data/panel/panel_monthly_v0.parquet"),
            args.panel_manifest,
            Path("data/targets"),
            Path("data/diagnostics"),
            Path("reports/data"),
            Path("reports/repo_audit"),
        ]
    )
    paths_to_hash = [path for path in paths_to_hash if not path.as_posix().startswith("data/panel/_monthly_partials/")]
    records = build_file_records(paths_to_hash)
    write_records_csv(records, args.derived_manifest)

    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "status": "completed",
        "generated_at_utc": generated_at,
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_dirty_state": git_dirty_status(),
        "python_constraint": ">=3.14,<3.15",
        "raw_manifest": args.raw_manifest.as_posix(),
        "source_catalog": args.source_catalog.as_posix(),
        "derived_manifest": args.derived_manifest.as_posix(),
        "data_freeze_md": args.freeze_md.as_posix(),
        "raw_manifest_stats": raw_manifest_stats,
        "derived_summary": derived_summary(records),
        "panel_manifest": panel_manifest,
        "target_manifest": target_manifest,
        "diagnostic_manifest": diagnostic_manifest,
    }
    write_json_atomic(payload, args.freeze_json)
    write_freeze_md(
        args.freeze_md,
        payload,
        source_catalog,
        raw_manifest_stats,
        observation_manifests,
        date_ranges,
        panel_manifest,
        target_manifest,
        diagnostic_manifest,
        records,
    )
    print(f"derived manifest written: {args.derived_manifest}")
    print(f"freeze manifest written: {args.freeze_json}")
    print(f"DATA_FREEZE written: {args.freeze_md}")


if __name__ == "__main__":
    main()
