#!/usr/bin/env python
"""Build canonical observation parquet files from declared raw sources."""

from __future__ import annotations

import argparse
import importlib
import json
import signal
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.adapters.common import ObservationChunk, load_yaml


DEFAULT_SOURCES_CONFIG = Path("configs/sources.yaml")
DEFAULT_VARIABLES_CONFIG = Path("configs/variables.yaml")
DEFAULT_OUTPUT_DIR = Path("data/interim/observations")


ADAPTER_MODULES = {
    "lakebed_us_cse": "src.data.adapters.lakebed_us_cse",
    "aquamatch_chla": "src.data.adapters.aquamatch_chla",
    "wqp_streaming": "src.data.adapters.wqp_streaming",
}


STOP_REQUESTED = False


class ControlledStop(Exception):
    """Raised when the user requested a clean stop at a checkpoint."""


def _request_stop(signum: int, _frame: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    signal_name = signal.Signals(signum).name
    print(
        f"\nReceived {signal_name}. Stopping at the next safe checkpoint; "
        "the current chunk will not be marked complete.",
        file=sys.stderr,
        flush=True,
    )


def _stop_file(args: argparse.Namespace) -> Path:
    return args.stop_file or (args.output_dir / "STOP_REQUESTED")


def _should_stop(args: argparse.Namespace) -> bool:
    return STOP_REQUESTED or _stop_file(args).exists()


def load_adapter(adapter_name: str):
    module_name = ADAPTER_MODULES.get(adapter_name)
    if module_name is None:
        raise ValueError(f"No adapter module registered for adapter={adapter_name!r}")
    return importlib.import_module(module_name)


def build_source(
    source_id: str,
    source_config: dict[str, Any],
    variables_config: dict[str, Any],
    args: argparse.Namespace,
) -> pd.DataFrame:
    adapter = load_adapter(source_config["adapter"])
    kwargs: dict[str, Any] = {}
    if source_config["adapter"] == "lakebed_us_cse":
        kwargs["include_high_frequency"] = not args.no_high_frequency
        kwargs["max_files"] = args.max_files
        kwargs["max_rows_per_file"] = args.max_rows_per_file
    elif source_config["adapter"] in {"aquamatch_chla", "wqp_streaming"}:
        kwargs["chunksize"] = args.chunksize
        kwargs["max_rows"] = args.max_rows
    return adapter.build_observations(source_config, variables_config, **kwargs)


def iter_source_chunks(
    source_config: dict[str, Any],
    variables_config: dict[str, Any],
    args: argparse.Namespace,
):
    adapter = load_adapter(source_config["adapter"])
    kwargs: dict[str, Any] = {}
    if source_config["adapter"] == "lakebed_us_cse":
        kwargs["include_high_frequency"] = not args.no_high_frequency
        kwargs["max_files"] = args.max_files
        kwargs["max_rows_per_file"] = args.max_rows_per_file
        kwargs["skip_units"] = args._skip_units
    elif source_config["adapter"] in {"aquamatch_chla", "wqp_streaming"}:
        kwargs["chunksize"] = args.chunksize
        kwargs["max_rows"] = args.max_rows
        kwargs["skip_rows"] = args._skip_rows

    if hasattr(adapter, "iter_observation_chunks"):
        for item in adapter.iter_observation_chunks(source_config, variables_config, **kwargs):
            if isinstance(item, ObservationChunk):
                yield item
            else:
                yield ObservationChunk(frame=item, unit_id=f"{source_config['adapter']}:unknown", unit_index=0)
        return
    frame = adapter.build_observations(source_config, variables_config, **kwargs)
    yield ObservationChunk(frame=frame, unit_id=f"{source_config['adapter']}:all", unit_index=0)


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_manifest_atomic(manifest: dict[str, Any], manifest_path: Path) -> None:
    tmp_path = manifest_path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    tmp_path.replace(manifest_path)


def _cleanup_stale_temp_files(source_output_dir: Path) -> None:
    for pattern in ("part-*.parquet.tmp", "_manifest.json.tmp"):
        for temp_path in source_output_dir.glob(pattern):
            temp_path.unlink(missing_ok=True)


def _write_part_atomic(frame: pd.DataFrame, part_path: Path) -> None:
    temp_path = part_path.with_name(f"{part_path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    try:
        frame.to_parquet(temp_path, index=False)
        temp_path.replace(part_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _empty_manifest(source_id: str, source_config: dict[str, Any], source_output_dir: Path) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    return {
        "source_id": source_id,
        "adapter": source_config["adapter"],
        "output_dir": source_output_dir.as_posix(),
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": None,
        "status": "running",
        "chunks": [],
        "row_count": 0,
        "variable_counts": {},
        "completed_units": [],
        "last_raw_end": 0,
        "next_part_index": 0,
    }


def _recover_manifest_from_parts(
    source_id: str,
    source_config: dict[str, Any],
    source_output_dir: Path,
) -> dict[str, Any]:
    manifest = _empty_manifest(source_id, source_config, source_output_dir)
    part_paths = sorted(source_output_dir.glob("part-*.parquet"))
    max_part_index = -1
    for part_path in part_paths:
        try:
            part_index = int(part_path.stem.split("-")[-1])
        except ValueError:
            part_index = max_part_index + 1
        max_part_index = max(max_part_index, part_index)
        frame = pd.read_parquet(part_path, columns=["source_file", "source_row_id", "variable_canonical"])
        variable_counts = frame["variable_canonical"].value_counts(dropna=False).to_dict()
        source_files = sorted(str(value) for value in frame["source_file"].dropna().unique())
        raw_indices = []
        for value in frame["source_row_id"].dropna():
            try:
                raw_indices.append(int(str(value).rsplit(":", 1)[-1]))
            except ValueError:
                pass
        last_raw_end = max(raw_indices) + 1 if raw_indices else manifest["last_raw_end"]
        manifest["chunks"].append(
            {
                "part": part_path.name,
                "rows": int(len(frame)),
                "variable_counts": {str(key): int(value) for key, value in variable_counts.items()},
                "unit_id": source_files[0] if len(source_files) == 1 else None,
                "raw_start": None,
                "raw_end": last_raw_end if source_config["adapter"] in {"aquamatch_chla", "wqp_streaming"} else None,
                "recovered": True,
            }
        )
        manifest["row_count"] += int(len(frame))
        for variable, count in variable_counts.items():
            variable_key = str(variable)
            manifest["variable_counts"][variable_key] = int(manifest["variable_counts"].get(variable_key, 0)) + int(count)
        if source_config["adapter"] == "lakebed_us_cse":
            manifest["completed_units"].extend(source_files)
        else:
            manifest["last_raw_end"] = max(int(manifest["last_raw_end"]), int(last_raw_end))
    manifest["completed_units"] = sorted(set(manifest["completed_units"]))
    manifest["next_part_index"] = max_part_index + 1
    manifest["status"] = "recovered"
    return manifest


def _prepare_output_dir(output_dir: Path, source_id: str, source_config: dict[str, Any], overwrite: bool, resume: bool) -> tuple[Path, dict[str, Any]]:
    source_output_dir = output_dir / source_id
    if source_output_dir.exists():
        if overwrite and resume:
            raise ValueError("--overwrite and --resume are mutually exclusive")
        if overwrite:
            shutil.rmtree(source_output_dir)
        elif not resume:
            raise FileExistsError(
                f"Output already exists: {source_output_dir}. "
                "Use --resume to continue or --overwrite to replace this source output."
            )
    source_output_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_stale_temp_files(source_output_dir)
    manifest_path = source_output_dir / "_manifest.json"
    manifest = _load_manifest(manifest_path)
    if manifest is None:
        if resume and list(source_output_dir.glob("part-*.parquet")):
            manifest = _recover_manifest_from_parts(source_id, source_config, source_output_dir)
            _write_manifest_atomic(manifest, manifest_path)
        else:
            manifest = _empty_manifest(source_id, source_config, source_output_dir)
    manifest.setdefault("completed_units", [])
    manifest.setdefault("last_raw_end", 0)
    manifest.setdefault("next_part_index", len(manifest.get("chunks", [])))
    manifest["status"] = "running"
    _write_manifest_atomic(manifest, manifest_path)
    return source_output_dir, manifest


def write_source_dataset(
    source_id: str,
    source_config: dict[str, Any],
    variables_config: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    source_output_dir, manifest = _prepare_output_dir(
        args.output_dir,
        source_id,
        source_config,
        args.overwrite,
        args.resume,
    )
    manifest_path = source_output_dir / "_manifest.json"
    args._skip_units = set(manifest.get("completed_units", [])) if args.resume else set()
    args._skip_rows = int(manifest.get("last_raw_end", 0)) if args.resume else 0
    part_index = int(manifest.get("next_part_index", 0))

    if args.resume:
        print(
            f"{source_id}: resuming from {source_output_dir}; "
            f"existing_rows={manifest['row_count']:,}, next_part={part_index:06d}, "
            f"skip_units={len(args._skip_units)}, skip_rows={args._skip_rows:,}"
        )

    try:
        for chunk in iter_source_chunks(source_config, variables_config, args):
            if _should_stop(args):
                raise ControlledStop

            frame = chunk.frame
            unit_label = f"{chunk.unit_index + 1}/{chunk.total_units}" if chunk.total_units else str(chunk.unit_index + 1)
            raw_label = ""
            if chunk.raw_start is not None and chunk.raw_end is not None:
                raw_label = f" raw_rows={chunk.raw_start:,}-{chunk.raw_end:,}"

            if _should_stop(args):
                raise ControlledStop

            if frame.empty:
                if source_config["adapter"] == "lakebed_us_cse":
                    manifest["completed_units"] = sorted(set(manifest.get("completed_units", []) + [chunk.unit_id]))
                if chunk.raw_end is not None:
                    manifest["last_raw_end"] = max(int(manifest.get("last_raw_end", 0)), int(chunk.raw_end))
                manifest["chunks"].append(
                    {
                        "part": None,
                        "rows": 0,
                        "variable_counts": {},
                        "unit_id": chunk.unit_id,
                        "unit_index": chunk.unit_index,
                        "raw_start": chunk.raw_start,
                        "raw_end": chunk.raw_end,
                        "empty": True,
                    }
                )
                _write_manifest_atomic(manifest, manifest_path)
                print(f"{source_id}: checkpoint unit {unit_label}{raw_label}; no canonical rows", flush=True)
                continue

            part_path = source_output_dir / f"part-{part_index:06d}.parquet"
            _write_part_atomic(frame, part_path)

            if _should_stop(args):
                part_path.unlink(missing_ok=True)
                raise ControlledStop

            variable_counts = frame["variable_canonical"].value_counts(dropna=False).to_dict()
            manifest["chunks"].append(
                {
                    "part": part_path.name,
                    "rows": int(len(frame)),
                    "variable_counts": {str(key): int(value) for key, value in variable_counts.items()},
                    "unit_id": chunk.unit_id,
                    "unit_index": chunk.unit_index,
                    "raw_start": chunk.raw_start,
                    "raw_end": chunk.raw_end,
                    "empty": False,
                }
            )
            manifest["row_count"] += int(len(frame))
            for variable, count in variable_counts.items():
                variable_key = str(variable)
                manifest["variable_counts"][variable_key] = int(manifest["variable_counts"].get(variable_key, 0)) + int(count)
            if source_config["adapter"] == "lakebed_us_cse":
                manifest["completed_units"] = sorted(set(manifest.get("completed_units", []) + [chunk.unit_id]))
            if chunk.raw_end is not None:
                manifest["last_raw_end"] = max(int(manifest.get("last_raw_end", 0)), int(chunk.raw_end))
            part_index += 1
            manifest["next_part_index"] = part_index
            _write_manifest_atomic(manifest, manifest_path)
            elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(manifest["started_at_utc"])
            print(
                f"{source_id}: unit {unit_label}{raw_label}; wrote {part_path} "
                f"({len(frame):,} rows); total={manifest['row_count']:,}; elapsed={elapsed}",
                flush=True,
            )
    except (KeyboardInterrupt, ControlledStop):
        _cleanup_stale_temp_files(source_output_dir)
        manifest["status"] = "interrupted"
        manifest["interrupted_at_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["completed_at_utc"] = None
        manifest["next_part_index"] = part_index
        _write_manifest_atomic(manifest, manifest_path)
        print(
            f"{source_id}: interrupted. Current chunk discarded; "
            f"previous completed rows remain {manifest['row_count']:,}. "
            f"Resume with --resume. Remove {_stop_file(args)} before resuming if it exists.",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(130)

    manifest["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["status"] = "completed"
    _write_manifest_atomic(manifest, manifest_path)
    print(f"{source_id}: wrote {manifest_path}")
    print(f"{source_id}: total {manifest['row_count']:,} canonical observations")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical observations from raw source adapters.")
    parser.add_argument("--sources-config", type=Path, default=DEFAULT_SOURCES_CONFIG)
    parser.add_argument("--variables-config", type=Path, default=DEFAULT_VARIABLES_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--source",
        action="append",
        help="Source id to build. Can be repeated. Defaults to all sources.",
    )
    parser.add_argument("--chunksize", type=int, default=250_000)
    parser.add_argument("--max-rows", type=int, default=None, help="Maximum CSV rows to read for chunked adapters.")
    parser.add_argument("--max-files", type=int, default=None, help="Maximum LakeBeD parquet files to read.")
    parser.add_argument("--max-rows-per-file", type=int, default=None, help="Maximum rows per LakeBeD parquet file.")
    parser.add_argument("--no-high-frequency", action="store_true", help="Skip LakeBeD HighFrequency files.")
    parser.add_argument("--dry-run", action="store_true", help="Build frames but do not write parquet files.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing source output directory.")
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted source output directory.")
    parser.add_argument(
        "--stop-file",
        type=Path,
        default=None,
        help="Path whose presence requests a clean stop. Defaults to <output-dir>/STOP_REQUESTED.",
    )
    return parser.parse_args()


def main() -> None:
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    args = parse_args()
    sources_config = load_yaml(args.sources_config)
    variables_config = load_yaml(args.variables_config)
    selected_sources = args.source or sorted(sources_config["sources"])

    for source_id in selected_sources:
        if source_id not in sources_config["sources"]:
            raise KeyError(f"Unknown source_id={source_id!r}")
        source_config = sources_config["sources"][source_id]
        args._skip_units = set()
        args._skip_rows = 0
        if args.dry_run:
            row_count = 0
            variable_counts: dict[str, int] = {}
            for chunk in iter_source_chunks(source_config, variables_config, args):
                frame = chunk.frame
                row_count += int(len(frame))
                for variable, count in frame["variable_canonical"].value_counts(dropna=False).items():
                    variable_key = str(variable)
                    variable_counts[variable_key] = variable_counts.get(variable_key, 0) + int(count)
            print(f"{source_id}: {row_count:,} canonical observations")
            print(f"{source_id}: variable_counts={variable_counts}")
            continue
        write_source_dataset(source_id, source_config, variables_config, args)


if __name__ == "__main__":
    main()
