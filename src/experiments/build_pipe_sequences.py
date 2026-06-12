#!/usr/bin/env python
"""Build the sequential S(t) -> S(t+1) dataset for PIPE/GRU-D."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows, year_month_month

from src.experiments.refine_expert_fuzzy import STATE_FEATURE_COLUMNS


DEFAULT_STATE = Path("data/fuzzy/state_vector_v0.parquet")
DEFAULT_OUTPUT_DIR = Path("data/pipe_grud")
DEFAULT_REPORT_DIR = Path("reports/pipe_grud")
DEFAULT_SEQUENCES = DEFAULT_OUTPUT_DIR / "pipe_sequence_dataset_v0.parquet"
DEFAULT_SUMMARY = DEFAULT_REPORT_DIR / "pipe_sequence_summary.csv"
DEFAULT_DISCARDED = DEFAULT_REPORT_DIR / "pipe_sequence_discarded_summary.csv"
DEFAULT_REPORT = DEFAULT_REPORT_DIR / "pipe_sequence_report.md"
DEFAULT_MANIFEST = DEFAULT_REPORT_DIR / "pipe_sequence_manifest.json"

KEY_COLUMNS = ["source_id", "site_id", "year_month"]
PIPE_STATE_COLUMNS = [
    "yN",
    "yF",
    "yT",
    "sigma_N",
    "sigma_F",
    "sigma_T",
    "delta_yN",
    "delta_yF",
    "delta_yT",
]
SEASON_COLUMNS = [
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
]
INPUT_COLUMNS = [f"x_{column}" for column in PIPE_STATE_COLUMNS] + SEASON_COLUMNS
TARGET_COLUMNS = [f"target_{column}" for column in PIPE_STATE_COLUMNS]
OPTIONAL_CONTEXT_COLUMNS = [
    "irc1",
    "irc1_no_chla",
    "evidence_N",
    "evidence_F",
    "evidence_T",
    "evidence_T_no_chla",
    "missing_N",
    "missing_F",
    "missing_T",
    "missing_T_no_chla",
]
INPUT_SURFACE_FULL = "full"
INPUT_SURFACE_NO_CURRENT_CHLA = "no_current_chla"
INPUT_SURFACES = [INPUT_SURFACE_FULL, INPUT_SURFACE_NO_CURRENT_CHLA]
NO_CURRENT_CHLA_INPUT_MAPPING = {
    "yT": "yT_no_chla",
    "sigma_T": "sigma_T_no_chla",
    "delta_yT": "delta_yT_no_chla",
}


def _format_int(value: int) -> str:
    return f"{value:,}"


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:,.4f}"


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": _manifest_path(path), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=_json_default)
        handle.write("\n")
    tmp_path.replace(path)


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp_path, index=False)
    tmp_path.replace(path)


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.unlink(missing_ok=True)
    try:
        frame.to_parquet(tmp_path, index=False)
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def _write_text_atomic(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _period_index(months: pd.Series) -> pd.PeriodIndex:
    return pd.PeriodIndex(months.astype(str), freq="M")


def _assign_split(
    months: pd.Series,
    *,
    train_end: str,
    validation_start: str,
    validation_end: str,
    test_start: str,
    test_end: str | None,
) -> pd.Series:
    values = _period_index(months)
    out = pd.Series(pd.NA, index=months.index, dtype="string")
    out.loc[values <= pd.Period(train_end, freq="M")] = "train"
    out.loc[(values >= pd.Period(validation_start, freq="M")) & (values <= pd.Period(validation_end, freq="M"))] = (
        "validation"
    )
    test_mask = values >= pd.Period(test_start, freq="M")
    if test_end is not None:
        test_mask = test_mask & (values <= pd.Period(test_end, freq="M"))
    out.loc[test_mask] = "test"
    return out


def _add_season_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    month = year_month_month(out["origin_year_month"]).astype("float64")
    radians = 2.0 * np.pi * (month - 1.0) / 12.0
    out["origin_month"] = month.astype("int16")
    out["season_sin_annual"] = np.sin(radians)
    out["season_cos_annual"] = np.cos(radians)
    out["season_sin_semiannual"] = np.sin(2.0 * radians)
    out["season_cos_semiannual"] = np.cos(2.0 * radians)
    return out


def _coerce_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        out[column] = pd.to_numeric(out[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return out


def _parse_source_ids(values: list[str] | None) -> list[str]:
    if not values:
        return []
    source_ids = []
    for value in values:
        source_ids.extend(part.strip() for part in value.split(",") if part.strip())
    return sorted(set(source_ids))


def _source_filter_label(args: argparse.Namespace) -> str:
    source_ids = getattr(args, "source_ids_normalized", [])
    if not source_ids:
        return "all"
    return ", ".join(source_ids)


def _input_mapping(input_surface: str) -> dict[str, str]:
    if input_surface == INPUT_SURFACE_FULL:
        return {}
    if input_surface == INPUT_SURFACE_NO_CURRENT_CHLA:
        return NO_CURRENT_CHLA_INPUT_MAPPING
    raise ValueError(f"Unsupported input surface: {input_surface!r}")


def _source_column_for_input(column: str, input_surface: str) -> str:
    return _input_mapping(input_surface).get(column, column)


def _required_state_columns(input_surface: str) -> list[str]:
    required = set(PIPE_STATE_COLUMNS)
    required.update(_input_mapping(input_surface).values())
    return [column for column in STATE_FEATURE_COLUMNS if column in required]


def load_state(path: Path, *, input_surface: str = INPUT_SURFACE_FULL) -> pd.DataFrame:
    required = _required_state_columns(input_surface)
    optional = [column for column in STATE_FEATURE_COLUMNS if column in OPTIONAL_CONTEXT_COLUMNS]
    columns = KEY_COLUMNS + required + optional
    state = pd.read_parquet(path, columns=columns)
    missing = [column for column in KEY_COLUMNS + required if column not in state.columns]
    if missing:
        raise ValueError(f"State vector is missing required columns: {missing}")
    state = _coerce_numeric(state, [column for column in state.columns if column not in KEY_COLUMNS])
    state["source_id"] = state["source_id"].astype(str)
    state["site_id"] = state["site_id"].astype(str)
    state["year_month"] = state["year_month"].astype(str)
    return state


def filter_state_sources(state: pd.DataFrame, source_ids: list[str]) -> pd.DataFrame:
    if not source_ids:
        return state
    available = set(state["source_id"].unique())
    missing = sorted(set(source_ids).difference(available))
    if missing:
        raise ValueError(f"Requested source_id values are not present in the state vector: {missing}")
    out = state[state["source_id"].isin(source_ids)].copy()
    if out.empty:
        raise ValueError(f"Source filter removed all state rows: {source_ids}")
    return out.reset_index(drop=True)


def build_sequence_candidates(state: pd.DataFrame, *, input_surface: str = INPUT_SURFACE_FULL) -> pd.DataFrame:
    frame = state.copy()
    mapping = _input_mapping(input_surface)
    missing = [source for source in mapping.values() if source not in frame.columns]
    if missing:
        raise ValueError(f"State vector is missing columns required by {input_surface}: {missing}")
    periods = _period_index(frame["year_month"])
    frame["period_ord"] = periods.asi8.astype("int64")
    frame["sequence_step"] = (
        frame.sort_values(["source_id", "site_id", "period_ord"])
        .groupby(["source_id", "site_id"], sort=False)
        .cumcount()
        .astype("int32")
    )
    frame = frame.sort_values(["source_id", "site_id", "period_ord"]).reset_index(drop=True)

    group = frame.groupby(["source_id", "site_id"], sort=False)
    candidates = frame[["source_id", "site_id", "year_month", "period_ord", "sequence_step"]].rename(
        columns={"year_month": "origin_year_month", "period_ord": "origin_period_ord"}
    )
    candidates["target_year_month"] = group["year_month"].shift(-1)
    candidates["target_period_ord"] = group["period_ord"].shift(-1)
    candidates["target_gap_months"] = candidates["target_period_ord"] - candidates["origin_period_ord"]

    for column in PIPE_STATE_COLUMNS:
        source_column = _source_column_for_input(column, input_surface)
        candidates[f"x_{column}"] = frame[source_column].to_numpy()
        candidates[f"target_{column}"] = group[column].shift(-1).to_numpy()
    for column in OPTIONAL_CONTEXT_COLUMNS:
        if column in frame.columns:
            candidates[f"x_{column}"] = frame[column].to_numpy()

    return candidates


def filter_leakage_safe_sequences(candidates: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = candidates.copy()
    frame["origin_split"] = _assign_split(
        frame["origin_year_month"],
        train_end=args.train_end,
        validation_start=args.validation_start,
        validation_end=args.validation_end,
        test_start=args.test_start,
        test_end=args.test_end,
    )

    has_target = frame["target_year_month"].notna()
    frame["target_split"] = pd.Series(pd.NA, index=frame.index, dtype="string")
    frame.loc[has_target, "target_split"] = _assign_split(
        frame.loc[has_target, "target_year_month"],
        train_end=args.train_end,
        validation_start=args.validation_start,
        validation_end=args.validation_end,
        test_start=args.test_start,
        test_end=args.test_end,
    )

    frame["split_reason"] = "kept"
    frame.loc[~has_target, "split_reason"] = "no_next_state"
    frame.loc[has_target & (frame["target_gap_months"] > args.max_gap_months), "split_reason"] = "gap_too_large"
    outside = has_target & (frame["origin_split"].isna() | frame["target_split"].isna())
    frame.loc[outside, "split_reason"] = "outside_split_bounds"
    crossing = has_target & frame["origin_split"].notna() & frame["target_split"].notna() & (
        frame["origin_split"] != frame["target_split"]
    )
    frame.loc[crossing, "split_reason"] = "crosses_split_boundary"

    kept = frame[frame["split_reason"] == "kept"].copy()
    kept["split"] = kept["origin_split"].astype("string")
    kept["target_gap_months"] = kept["target_gap_months"].astype("int16")
    kept = _add_season_features(kept)

    ordered_columns = (
        [
            "source_id",
            "site_id",
            "sequence_step",
            "origin_year_month",
            "target_year_month",
            "target_gap_months",
            "split",
            "origin_month",
        ]
        + INPUT_COLUMNS
        + TARGET_COLUMNS
        + [f"x_{column}" for column in OPTIONAL_CONTEXT_COLUMNS if f"x_{column}" in kept.columns]
    )
    kept = kept[ordered_columns].sort_values(["source_id", "site_id", "origin_year_month"]).reset_index(drop=True)

    discarded = frame[frame["split_reason"] != "kept"].copy()
    return kept, discarded.reset_index(drop=True)


def summarize_sequences(sequences: pd.DataFrame) -> pd.DataFrame:
    if sequences.empty:
        return pd.DataFrame(
            columns=[
                "source_id",
                "split",
                "rows",
                "sites",
                "origin_min",
                "origin_max",
                "target_min",
                "target_max",
                "mean_gap_months",
                "max_gap_months",
            ]
        )
    grouped = sequences.groupby(["source_id", "split"], dropna=False)
    summary = grouped.agg(
        rows=("site_id", "size"),
        sites=("site_id", "nunique"),
        origin_min=("origin_year_month", "min"),
        origin_max=("origin_year_month", "max"),
        target_min=("target_year_month", "min"),
        target_max=("target_year_month", "max"),
        mean_gap_months=("target_gap_months", "mean"),
        max_gap_months=("target_gap_months", "max"),
    ).reset_index()
    summary["rows"] = summary["rows"].astype("int64")
    summary["sites"] = summary["sites"].astype("int64")
    summary["max_gap_months"] = summary["max_gap_months"].astype("int64")
    return summary.sort_values(["source_id", "split"]).reset_index(drop=True)


def summarize_discarded(discarded: pd.DataFrame) -> pd.DataFrame:
    if discarded.empty:
        return pd.DataFrame(columns=["source_id", "split_reason", "rows", "sites"])
    grouped = discarded.groupby(["source_id", "split_reason"], dropna=False)
    summary = grouped.agg(rows=("site_id", "size"), sites=("site_id", "nunique")).reset_index()
    summary["rows"] = summary["rows"].astype("int64")
    summary["sites"] = summary["sites"].astype("int64")
    return summary.sort_values(["source_id", "split_reason"]).reset_index(drop=True)


def _split_summary(sequences: pd.DataFrame) -> pd.DataFrame:
    if sequences.empty:
        return pd.DataFrame(columns=["split", "rows", "sites", "origin_min", "origin_max", "target_min", "target_max"])
    summary = (
        sequences.groupby("split", dropna=False)
        .agg(
            rows=("site_id", "size"),
            sites=("site_id", "nunique"),
            origin_min=("origin_year_month", "min"),
            origin_max=("origin_year_month", "max"),
            target_min=("target_year_month", "min"),
            target_max=("target_year_month", "max"),
        )
        .reset_index()
        .sort_values("split")
    )
    summary["rows"] = summary["rows"].astype("int64")
    summary["sites"] = summary["sites"].astype("int64")
    return summary.reset_index(drop=True)


def write_report(
    *,
    args: argparse.Namespace,
    sequences: pd.DataFrame,
    discarded: pd.DataFrame,
    summary: pd.DataFrame,
    discarded_summary: pd.DataFrame,
    started_at: datetime,
) -> None:
    split_summary = _split_summary(sequences)
    lines = [
        "# PIPE Sequence Dataset v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at.isoformat()}`",
        "",
        "## Scope",
        "",
        "This step builds a leakage-safe adjacent-month `S(t) -> S(t+1)` dataset for PIPE/GRU-D.",
        "It does not train or tune a temporal model.",
        f"Input surface: `{args.input_surface}`.",
        f"Source filter: `{_source_filter_label(args)}`.",
        f"Maximum allowed target gap: `{args.max_gap_months}` month(s).",
        f"Input dimensionality for the minimal PIPE model: `{len(INPUT_COLUMNS)}` = 9 state values + 4 seasonal values.",
    ]
    if args.input_surface == INPUT_SURFACE_NO_CURRENT_CHLA:
        lines.extend(
            [
                "",
                "No-current-Chl-a mode replaces current thermal/biological input channels with no-Chl-a fuzzy variants:",
                "",
                "| input channel | state source |",
                "|---|---|",
            ]
        )
        for input_column, source_column in NO_CURRENT_CHLA_INPUT_MAPPING.items():
            lines.append(f"| `x_{input_column}` | `{source_column}` |")
        lines.extend(
            [
                "",
                "Targets remain the full next-month fuzzy state, so observed future Chl-a-derived state can still be evaluated.",
            ]
        )
    lines.extend(
        [
            "",
            "## Row Counts",
            "",
            f"- Candidate state rows: `{_format_int(len(sequences) + len(discarded))}`",
            f"- Kept sequence rows: `{_format_int(len(sequences))}`",
            f"- Discarded candidate rows: `{_format_int(len(discarded))}`",
            f"- Source-scoped sites kept: `{_format_int(int(sequences.groupby(['source_id', 'site_id']).ngroups if len(sequences) else 0))}`",
            "",
            "## By Split",
            "",
            "| split | rows | sites | origin range | target range |",
            "|---|---:|---:|---|---|",
        ]
    )
    if split_summary.empty:
        lines.append("| `NA` | 0 | 0 | `NA` | `NA` |")
    else:
        for row in dataframe_rows(split_summary):
            lines.append(
                f"| `{row.split}` | {_format_int(int(row.rows))} | {_format_int(int(row.sites))} | "
                f"`{row.origin_min}..{row.origin_max}` | `{row.target_min}..{row.target_max}` |"
            )

    lines.extend(["", "## By Source And Split", "", "| source | split | rows | sites | origin range | target range | mean gap | max gap |", "|---|---|---:|---:|---|---|---:|---:|"])
    if summary.empty:
        lines.append("| `NA` | `NA` | 0 | 0 | `NA` | `NA` | NA | NA |")
    else:
        for row in dataframe_rows(summary):
            lines.append(
                f"| `{row.source_id}` | `{row.split}` | {_format_int(int(row.rows))} | "
                f"{_format_int(int(row.sites))} | `{row.origin_min}..{row.origin_max}` | "
                f"`{row.target_min}..{row.target_max}` | {_format_float(float(row.mean_gap_months))} | "
                f"{int(row.max_gap_months)} |"
            )

    lines.extend(["", "## Discarded", "", "| source | reason | rows | sites |", "|---|---|---:|---:|"])
    if discarded_summary.empty:
        lines.append("| `NA` | `none` | 0 | 0 |")
    else:
        for row in dataframe_rows(discarded_summary):
            lines.append(
                f"| `{row.source_id}` | `{row.split_reason}` | {_format_int(int(row.rows))} | "
                f"{_format_int(int(row.sites))} |"
            )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Sequence dataset: `{args.sequences}`",
            f"- Summary: `{args.summary}`",
            f"- Discarded summary: `{args.discarded}`",
            f"- Manifest: `{args.manifest}`",
            "",
        ]
    )
    _write_text_atomic("\n".join(lines), args.report)


def manifest_payload(
    *,
    args: argparse.Namespace,
    sequences: pd.DataFrame,
    discarded: pd.DataFrame,
    summary: pd.DataFrame,
    discarded_summary: pd.DataFrame,
    started_at: datetime,
) -> dict[str, Any]:
    outputs = [args.sequences, args.summary, args.discarded, args.report]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "dataset_version": "pipe_sequence_dataset_v0",
        "config": {
            "max_gap_months": int(args.max_gap_months),
            "input_surface": args.input_surface,
            "source_ids": getattr(args, "source_ids_normalized", []),
            "input_state_mapping": {
                column: _source_column_for_input(column, args.input_surface) for column in PIPE_STATE_COLUMNS
            },
            "train_end": args.train_end,
            "validation_start": args.validation_start,
            "validation_end": args.validation_end,
            "test_start": args.test_start,
            "test_end": args.test_end,
            "pipe_state_columns": PIPE_STATE_COLUMNS,
            "season_columns": SEASON_COLUMNS,
            "input_columns": INPUT_COLUMNS,
            "target_columns": TARGET_COLUMNS,
        },
        "row_counts": {
            "candidate_rows": int(len(sequences) + len(discarded)),
            "kept_sequence_rows": int(len(sequences)),
            "discarded_candidate_rows": int(len(discarded)),
            "source_scoped_sites": int(sequences.groupby(["source_id", "site_id"]).ngroups if len(sequences) else 0),
            "summary_rows": int(len(summary)),
            "discarded_summary_rows": int(len(discarded_summary)),
        },
        "inputs": [_file_record(args.state)],
        "outputs": [_file_record(path) for path in outputs],
        "script": _file_record(Path(__file__)),
        "by_source_split": summary.to_dict(orient="records"),
        "discarded_summary": discarded_summary.to_dict(orient="records"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build leakage-safe PIPE/GRU-D sequence transitions.")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--sequences", type=Path, default=DEFAULT_SEQUENCES)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--discarded", type=Path, default=DEFAULT_DISCARDED)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--input-surface", choices=INPUT_SURFACES, default=INPUT_SURFACE_FULL)
    parser.add_argument(
        "--source-ids",
        nargs="+",
        default=None,
        help="Optional source_id filter. Accepts one or more values, or comma-separated values.",
    )
    parser.add_argument("--max-gap-months", type=int, default=1)
    parser.add_argument("--train-end", default="2018-12")
    parser.add_argument("--validation-start", default="2019-01")
    parser.add_argument("--validation-end", default="2021-12")
    parser.add_argument("--test-start", default="2022-01")
    parser.add_argument("--test-end", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.source_ids_normalized = _parse_source_ids(args.source_ids)
    if args.max_gap_months < 1:
        raise ValueError("--max-gap-months must be >= 1")

    started_at = datetime.now(timezone.utc)
    print(f"loading state {args.state}", flush=True)
    state = load_state(args.state, input_surface=args.input_surface)
    print(f"state rows={len(state):,}", flush=True)
    if args.source_ids_normalized:
        print(f"filtering source_id to {args.source_ids_normalized}", flush=True)
        state = filter_state_sources(state, args.source_ids_normalized)
        print(f"filtered state rows={len(state):,}", flush=True)

    print("building adjacent state transitions", flush=True)
    candidates = build_sequence_candidates(state, input_surface=args.input_surface)
    sequences, discarded = filter_leakage_safe_sequences(candidates, args)
    summary = summarize_sequences(sequences)
    discarded_summary = summarize_discarded(discarded)

    _write_parquet_atomic(sequences, args.sequences)
    print(f"wrote {args.sequences} ({len(sequences):,} rows)", flush=True)
    _write_csv_atomic(summary, args.summary)
    print(f"wrote {args.summary}", flush=True)
    _write_csv_atomic(discarded_summary, args.discarded)
    print(f"wrote {args.discarded}", flush=True)
    write_report(args=args, sequences=sequences, discarded=discarded, summary=summary, discarded_summary=discarded_summary, started_at=started_at)
    print(f"wrote {args.report}", flush=True)
    manifest = manifest_payload(
        args=args,
        sequences=sequences,
        discarded=discarded,
        summary=summary,
        discarded_summary=discarded_summary,
        started_at=started_at,
    )
    _write_json_atomic(manifest, args.manifest)
    print(f"wrote {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
