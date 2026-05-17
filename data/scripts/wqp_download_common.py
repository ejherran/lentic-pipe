#!/usr/bin/env python3
"""Shared resumable downloader for Water Quality Portal WQX3 CSV exports."""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data/raw/wqp"
CACHE_DIR = REPO_ROOT / "data/cache/downloads/wqp"

START_DATE = date(1970, 1, 1)
END_DATE = date(2026, 5, 11)
INITIAL_CHUNK_DAYS = 365
MIN_CHUNK_DAYS = 1
TIMEOUT_SECS = 1800
MAX_RETRIES = 10
RETRY_BACKOFF = 60
ERROR_MARKER = "INCOMPLETE DATA"


@dataclass(frozen=True)
class WqpDownloadConfig:
    label: str
    base_url: str
    base_params: tuple[tuple[str, str], ...]
    final_file: Path
    state_file: Path
    chunk_dir: Path
    user_agent: str
    dedupe_key_columns: tuple[str, ...] = ()


class DownloadFailed(Exception):
    """Raised when a date range exhausts all retry attempts."""


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def wqp_date(value: date) -> str:
    return value.strftime("%m-%d-%Y")


def build_url(config: WqpDownloadConfig, lo: date, hi: date) -> str:
    params = list(config.base_params) + [("startDateLo", wqp_date(lo)), ("startDateHi", wqp_date(hi))]
    return config.base_url + "?" + urlencode(params)


def chunk_path(config: WqpDownloadConfig, lo: date, hi: date) -> Path:
    return config.chunk_dir / f"chunk_{lo.isoformat()}_{hi.isoformat()}.csv"


def load_state(path: Path) -> dict:
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        state.setdefault("done", [])
        state.setdefault("accepted_partial", [])
        state.setdefault("bisecting", [])
        return state
    return {"done": [], "accepted_partial": [], "bisecting": []}


def save_state(state: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    tmp_path.replace(path)


def tail_has_error(path: Path, tail_bytes: int = 4096) -> bool:
    size = path.stat().st_size
    if size == 0:
        return True
    with path.open("rb") as handle:
        handle.seek(max(0, size - tail_bytes))
        tail = handle.read().decode("utf-8", errors="ignore")
    return ERROR_MARKER.upper() in tail.upper()


def strip_error_trailer(path: Path) -> None:
    if not path.exists():
        return
    if not tail_has_error(path):
        return
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    while lines and ERROR_MARKER.upper() in lines[-1].upper():
        lines.pop()
    while lines and lines[-1].strip() == "":
        lines.pop()
    path.write_bytes("".join(lines).encode("utf-8"))


def download_range(config: WqpDownloadConfig, lo: date, hi: date, path: Path) -> bool | None:
    url = build_url(config, lo, hi)
    headers = {"User-Agent": config.user_agent, "Accept": "text/csv,*/*"}
    path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, MAX_RETRIES + 1):
        started = time.time()
        try:
            with requests.get(url, headers=headers, stream=True, timeout=TIMEOUT_SECS) as response:
                response.raise_for_status()
                with path.open("wb") as handle:
                    n_bytes = 0
                    last_log = time.time()
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        n_bytes += len(chunk)
                        if time.time() - last_log > 10:
                            print(f"    ... {n_bytes / 1e6:8.1f} MB ({(time.time() - started):.0f}s)")
                            last_log = time.time()
            return not tail_has_error(path)
        except (requests.RequestException, OSError) as error:
            print(f"    attempt {attempt}/{MAX_RETRIES} failed: {error}")
            path.unlink(missing_ok=True)
            if attempt < MAX_RETRIES:
                print(f"    waiting {RETRY_BACKOFF}s before retry...")
                time.sleep(RETRY_BACKOFF)
            else:
                print(f"    exhausted retries for {lo} -> {hi}")
                return None
    return None


def process_range(config: WqpDownloadConfig, lo: date, hi: date, state: dict) -> None:
    key = f"{lo.isoformat()}|{hi.isoformat()}"
    path = chunk_path(config, lo, hi)
    if key in state["done"] or key in state["accepted_partial"]:
        if path.exists():
            print(f"[skip] {lo} -> {hi} already processed")
            return
        print(f"[redo] {lo} -> {hi} was in state but chunk is missing")
        for bucket in ("done", "accepted_partial"):
            if key in state[bucket]:
                state[bucket].remove(key)
        save_state(state, config.state_file)

    if key in state["bisecting"]:
        print(f"[bsec] {lo} -> {hi} already marked for bisection")
        days_total = (hi - lo).days
        mid = lo + timedelta(days=days_total // 2)
        process_range(config, lo, mid, state)
        process_range(config, mid + timedelta(days=1), hi, state)
        return

    if path.exists():
        if not tail_has_error(path):
            print(f"[fix ] {lo} -> {hi} existing chunk OK")
            state["done"].append(key)
            save_state(state, config.state_file)
            return
        path.unlink()

    days = (hi - lo).days + 1
    print(f"[try ] {config.label} {lo} -> {hi} ({days} days)")
    complete = download_range(config, lo, hi, path)
    if complete is True:
        print(f"[ok  ] {lo} -> {hi} {path.stat().st_size / 1e6:.1f} MB")
        state["done"].append(key)
        save_state(state, config.state_file)
        return
    if complete is None:
        raise DownloadFailed(f"Could not download {lo} -> {hi} after {MAX_RETRIES} attempts")

    print(f"[part] {lo} -> {hi} {ERROR_MARKER} -> bisect")
    path.unlink(missing_ok=True)
    if (hi - lo).days < MIN_CHUNK_DAYS * 2:
        result = download_range(config, lo, hi, path)
        if result is None:
            raise DownloadFailed(f"Could not download minimum range {lo} -> {hi}")
        strip_error_trailer(path)
        state["accepted_partial"].append(key)
        save_state(state, config.state_file)
        return

    state["bisecting"].append(key)
    save_state(state, config.state_file)
    days_total = (hi - lo).days
    mid = lo + timedelta(days=days_total // 2)
    process_range(config, lo, mid, state)
    process_range(config, mid + timedelta(days=1), hi, state)


def initial_ranges(start: date, end: date, step_days: int):
    current = start
    while current <= end:
        next_end = min(current + timedelta(days=step_days - 1), end)
        yield current, next_end
        current = next_end + timedelta(days=1)


def iter_chunk_files(config: WqpDownloadConfig) -> list[Path]:
    if not config.chunk_dir.exists():
        return []
    return sorted(path for path in config.chunk_dir.glob("chunk_*.csv") if path.is_file())


def merge_chunks(config: WqpDownloadConfig, output_path: Path) -> int:
    files = iter_chunk_files(config)
    if not files:
        print(f"No chunks found in {config.chunk_dir}")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output_path.with_name(output_path.name + ".tmp")
    n_rows = 0
    header_written = False
    with tmp_output.open("w", encoding="utf-8", newline="") as out_handle:
        writer = csv.writer(out_handle)
        for path in files:
            strip_error_trailer(path)
            with path.open("r", encoding="utf-8", newline="") as in_handle:
                reader = csv.reader(in_handle)
                try:
                    header = next(reader)
                except StopIteration:
                    continue
                if not header_written:
                    writer.writerow(header)
                    header_written = True
                for row in reader:
                    if not row:
                        continue
                    if ERROR_MARKER.upper() in ",".join(row).upper():
                        continue
                    writer.writerow(row)
                    n_rows += 1
    tmp_output.replace(output_path)
    print(f"merged {len(files)} chunks -> {output_path} ({n_rows:,} rows)")
    return n_rows


def deduplicate_csv(input_path: Path, output_path: Path, key_columns: tuple[str, ...]) -> int:
    tmp_output = output_path.with_name(output_path.name + ".tmp")
    seen: set[tuple[str, ...]] = set()
    written = 0
    with input_path.open("r", encoding="utf-8", newline="") as in_handle, tmp_output.open(
        "w", encoding="utf-8", newline=""
    ) as out_handle:
        reader = csv.reader(in_handle)
        writer = csv.writer(out_handle)
        header = next(reader)
        writer.writerow(header)
        indexes = [header.index(column) for column in key_columns]
        for row in reader:
            if not row:
                continue
            key = tuple(row[index] if index < len(row) else "" for index in indexes)
            if key in seen:
                continue
            seen.add(key)
            writer.writerow(row)
            written += 1
    tmp_output.replace(output_path)
    print(f"deduplicated {input_path} -> {output_path} ({written:,} rows)")
    return written


def finalize_download(config: WqpDownloadConfig) -> None:
    if config.dedupe_key_columns:
        merged_path = config.chunk_dir.parent / f"{config.label}_merged.csv"
        merge_chunks(config, merged_path)
        if not merged_path.exists():
            return
        deduplicate_csv(merged_path, config.final_file, config.dedupe_key_columns)
        merged_path.unlink(missing_ok=True)
    else:
        merge_chunks(config, config.final_file)


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--start-date", type=parse_date, default=START_DATE, help="Inclusive YYYY-MM-DD start date.")
    parser.add_argument("--end-date", type=parse_date, default=END_DATE, help="Inclusive YYYY-MM-DD end date.")
    parser.add_argument("--chunk-days", type=int, default=INITIAL_CHUNK_DAYS)
    parser.add_argument("--force", action="store_true", help="Run even when the final output file already exists.")
    parser.add_argument("--merge-only", action="store_true", help="Only merge existing chunks into the final CSV.")
    return parser.parse_args()


def run(config: WqpDownloadConfig, args: argparse.Namespace) -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    config.chunk_dir.mkdir(parents=True, exist_ok=True)
    if config.final_file.exists() and not args.force and not args.merge_only:
        print(f"{config.final_file} already exists; use --force to download again or --merge-only to rebuild it.")
        return 0

    state = load_state(config.state_file)
    print(f"output: {config.final_file}")
    print(f"state: {config.state_file}")
    print(f"chunks: {config.chunk_dir}")
    print(
        f"state has {len(state['done'])} done, {len(state['accepted_partial'])} partial, "
        f"{len(state['bisecting'])} bisecting ranges"
    )

    if args.merge_only:
        finalize_download(config)
        return 0

    try:
        for lo, hi in initial_ranges(args.start_date, args.end_date, args.chunk_days):
            process_range(config, lo, hi, state)
    except DownloadFailed as error:
        print(f"\n[STOP] {error}")
        print(f"State was saved in {config.state_file}")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. Run the same script again to resume.")
        return 130

    finalize_download(config)
    if state["accepted_partial"]:
        print("\nWarning: these minimum ranges were accepted after stripping INCOMPLETE DATA trailers:")
        for key in state["accepted_partial"]:
            print(f"  - {key}")
    return 0


def results_config() -> WqpDownloadConfig:
    return WqpDownloadConfig(
        label="wqp_results",
        base_url="https://www.waterqualitydata.us/wqx3/Result/search",
        base_params=(
            ("countrycode", "US"),
            ("siteType", "Lake, Reservoir, Impoundment"),
            ("sampleMedia", "Water"),
            ("mimeType", "csv"),
            ("dataProfile", "fullPhysChem"),
            ("providers", "NWIS"),
            ("providers", "STORET"),
        ),
        final_file=RAW_DIR / "wqp_results.csv",
        state_file=RAW_DIR / "wqp_results_state.json",
        chunk_dir=CACHE_DIR / "results",
        user_agent="lentic-pipe-wqp-results-downloader/1.0",
    )


def activity_config() -> WqpDownloadConfig:
    return WqpDownloadConfig(
        label="wqp_activity",
        base_url="https://www.waterqualitydata.us/wqx3/Activity/search",
        base_params=(
            ("countrycode", "US"),
            ("siteType", "Lake, Reservoir, Impoundment"),
            ("sampleMedia", "Water"),
            ("mimeType", "csv"),
            ("providers", "NWIS"),
            ("providers", "STORET"),
        ),
        final_file=RAW_DIR / "wqp_activity.csv",
        state_file=RAW_DIR / "wqp_activity_state.json",
        chunk_dir=CACHE_DIR / "activity",
        user_agent="lentic-pipe-wqp-activity-downloader/1.0",
    )


def stations_config() -> WqpDownloadConfig:
    return WqpDownloadConfig(
        label="wqp_stations",
        base_url="https://www.waterqualitydata.us/wqx3/Station/search",
        base_params=(
            ("countrycode", "US"),
            ("siteType", "Lake, Reservoir, Impoundment"),
            ("sampleMedia", "Water"),
            ("mimeType", "csv"),
            ("providers", "NWIS"),
            ("providers", "STORET"),
        ),
        final_file=RAW_DIR / "wqp_stations.csv",
        state_file=RAW_DIR / "wqp_stations_state.json",
        chunk_dir=CACHE_DIR / "stations",
        user_agent="lentic-pipe-wqp-stations-downloader/1.0",
        dedupe_key_columns=("Org_Identifier", "Location_Identifier"),
    )
