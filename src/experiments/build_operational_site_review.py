#!/usr/bin/env python
"""Build per-site operational review tables from frozen operational scores."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd

from src.pandas_utils import dataframe_rows
import pyarrow.parquet as pq


DEFAULT_SCORES = Path("data/fuzzy/operational_scores_v0.parquet")
DEFAULT_RECENT_LATEST_SITE_TOP_RISKS = Path("reports/anfis/operational_recent_latest_site_top_risks.csv")
DEFAULT_OPERATIONAL_MANIFEST = Path("reports/anfis/operational_scores_manifest.json")
DEFAULT_OUTPUT_DIR = Path("reports/anfis")
DEFAULT_SITE_SUMMARY = DEFAULT_OUTPUT_DIR / "operational_site_review_summary.csv"
DEFAULT_SITE_SUMMARY_PARQUET = DEFAULT_OUTPUT_DIR / "operational_site_review_summary.parquet"
DEFAULT_RECENT_SITE_RISK = DEFAULT_OUTPUT_DIR / "operational_site_review_recent_site_risk.csv"
DEFAULT_TRAJECTORIES = DEFAULT_OUTPUT_DIR / "operational_site_review_top_site_trajectories.csv"
DEFAULT_SUSTAINED_RISK = DEFAULT_OUTPUT_DIR / "operational_site_review_sustained_risk.csv"
DEFAULT_LOW_EVIDENCE_HIGH_RISK = DEFAULT_OUTPUT_DIR / "operational_site_review_low_evidence_high_risk.csv"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "operational_site_review_report.md"
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "operational_site_review_manifest.json"

REVIEW_VERSION = "operational_site_review_v0"
SCORE_COLUMNS = [
    "source_id",
    "site_id",
    "origin_year_month",
    "horizon_months",
    "probability_bloom_h",
    "threshold_bloom_h",
    "predicted_bloom_h",
    "risk_band",
    "current_model_score_name",
    "source_selector_score_name",
    "full_evidence",
    "exogenous_evidence",
    "evidence_N",
    "evidence_F",
    "evidence_T",
    "evidence_T_no_chla",
]
SITE_KEY_COLUMNS = ["source_id", "site_id", "horizon_months"]
TRAJECTORY_COLUMNS = [
    "review_rank_within_horizon",
    "source_id",
    "site_id",
    "origin_year_month",
    "horizon_months",
    "probability_bloom_h",
    "threshold_bloom_h",
    "threshold_margin",
    "predicted_bloom_h",
    "risk_band",
    "evidence_priority",
    "full_evidence",
    "exogenous_evidence",
    "current_model_score_name",
    "source_selector_score_name",
]


def _elapsed(started: float) -> str:
    return f"{time.monotonic() - started:,.1f}s"


def _format_int(value: int | float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{int(value):,}"


def _format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value):,.4f}"


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _json_sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_json_sanitize(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return _json_sanitize(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _path_record(path: Path) -> dict[str, Any]:
    if path.is_file():
        return _file_record(path)
    if not path.is_dir():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    files = []
    total_bytes = 0
    for file_path in sorted(item for item in path.rglob("*") if item.is_file() and not item.name.endswith(".tmp")):
        relative_path = file_path.relative_to(path).as_posix()
        file_hash = _sha256_file(file_path)
        file_bytes = file_path.stat().st_size
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
        total_bytes += file_bytes
        files.append(
            {
                "path": file_path.as_posix(),
                "relative_path": relative_path,
                "bytes": file_bytes,
                "sha256": file_hash,
            }
        )
    return {
        "path": path.as_posix(),
        "type": "directory",
        "bytes": total_bytes,
        "sha256": digest.hexdigest(),
        "files": files,
    }


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


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(_json_sanitize(payload), handle, indent=2, ensure_ascii=False, default=_json_default, allow_nan=False)
        handle.write("\n")
    tmp_path.replace(path)


def _write_text_atomic(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def score_part_paths(scores_path: Path) -> list[Path]:
    if scores_path.is_file():
        return [scores_path]
    if not scores_path.is_dir():
        raise FileNotFoundError(f"Scores path not found: {scores_path}")
    parts = sorted(path for path in scores_path.glob("*.parquet") if path.is_file())
    if not parts:
        raise FileNotFoundError(f"No parquet score parts found under {scores_path}")
    return parts


def read_score_part(path: Path) -> pd.DataFrame:
    available_columns = set(pq.ParquetFile(path).schema.names)
    missing = [column for column in SCORE_COLUMNS if column not in available_columns]
    if missing:
        raise ValueError(f"Score part {path} is missing columns: {missing}")
    return pd.read_parquet(path, columns=SCORE_COLUMNS)


def add_review_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["probability_bloom_h"] = pd.to_numeric(out["probability_bloom_h"], errors="coerce").clip(0.0, 1.0)
    out["threshold_bloom_h"] = pd.to_numeric(out["threshold_bloom_h"], errors="coerce").clip(0.0, 1.0)
    out["predicted_bloom_h"] = out["predicted_bloom_h"].astype(bool)
    out["threshold_margin"] = out["probability_bloom_h"] - out["threshold_bloom_h"]
    out["full_evidence"] = pd.to_numeric(out["full_evidence"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    out["exogenous_evidence"] = pd.to_numeric(out["exogenous_evidence"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    out["evidence_priority"] = out[["full_evidence", "exogenous_evidence"]].mean(axis=1)
    out["_origin_period"] = pd.PeriodIndex(out["origin_year_month"].astype(str), freq="M")
    return out


def _p90(values: pd.Series) -> float:
    return float(values.quantile(0.90))


def _p95(values: pd.Series) -> float:
    return float(values.quantile(0.95))


def build_site_summary(scores: pd.DataFrame, recent_months: int) -> pd.DataFrame:
    if recent_months <= 0:
        raise ValueError("recent_months must be positive")
    working_parts = []
    for horizon, group in add_review_features(scores).groupby("horizon_months", sort=True):
        group = group.copy()
        max_period = group["_origin_period"].max()
        cutoff = max_period - (recent_months - 1)
        group["recent_window_start"] = str(cutoff)
        group["recent_window_end"] = str(max_period)
        group["_in_recent_window"] = group["_origin_period"] >= cutoff
        working_parts.append(group)
    working = pd.concat(working_parts, ignore_index=True)

    grouped = (
        working.groupby(SITE_KEY_COLUMNS, dropna=False)
        .agg(
            rows=("probability_bloom_h", "size"),
            first_origin_year_month=("origin_year_month", "min"),
            last_origin_year_month=("origin_year_month", "max"),
            predicted_bloom_months=("predicted_bloom_h", "sum"),
            mean_probability=("probability_bloom_h", "mean"),
            p90_probability=("probability_bloom_h", _p90),
            p95_probability=("probability_bloom_h", _p95),
            max_probability=("probability_bloom_h", "max"),
            mean_threshold_margin=("threshold_margin", "mean"),
            max_threshold_margin=("threshold_margin", "max"),
            mean_full_evidence=("full_evidence", "mean"),
            mean_exogenous_evidence=("exogenous_evidence", "mean"),
            mean_evidence_priority=("evidence_priority", "mean"),
            current_model_score_name=("current_model_score_name", "last"),
            source_selector_score_name=("source_selector_score_name", "last"),
            recent_window_start=("recent_window_start", "first"),
            recent_window_end=("recent_window_end", "first"),
        )
        .reset_index()
    )
    grouped["predicted_bloom_rate"] = grouped["predicted_bloom_months"] / grouped["rows"]

    latest = (
        working.sort_values(SITE_KEY_COLUMNS + ["_origin_period", "origin_year_month"], ascending=[True, True, True, False, False])
        .drop_duplicates(SITE_KEY_COLUMNS, keep="first")
        [
            SITE_KEY_COLUMNS
            + [
                "origin_year_month",
                "probability_bloom_h",
                "threshold_bloom_h",
                "threshold_margin",
                "predicted_bloom_h",
                "risk_band",
                "full_evidence",
                "exogenous_evidence",
                "evidence_priority",
                "_in_recent_window",
            ]
        ]
        .rename(
            columns={
                "origin_year_month": "latest_origin_year_month",
                "probability_bloom_h": "latest_probability",
                "threshold_bloom_h": "latest_threshold",
                "threshold_margin": "latest_threshold_margin",
                "predicted_bloom_h": "latest_predicted_bloom",
                "risk_band": "latest_risk_band",
                "full_evidence": "latest_full_evidence",
                "exogenous_evidence": "latest_exogenous_evidence",
                "evidence_priority": "latest_evidence_priority",
                "_in_recent_window": "active_in_recent_window",
            }
        )
    )

    recent = working[working["_in_recent_window"]].copy()
    recent_grouped = (
        recent.groupby(SITE_KEY_COLUMNS, dropna=False)
        .agg(
            recent_rows=("probability_bloom_h", "size"),
            recent_predicted_bloom_months=("predicted_bloom_h", "sum"),
            recent_mean_probability=("probability_bloom_h", "mean"),
            recent_max_probability=("probability_bloom_h", "max"),
            recent_mean_threshold_margin=("threshold_margin", "mean"),
            recent_max_threshold_margin=("threshold_margin", "max"),
            recent_mean_evidence_priority=("evidence_priority", "mean"),
        )
        .reset_index()
    )
    recent_grouped["recent_predicted_bloom_rate"] = (
        recent_grouped["recent_predicted_bloom_months"] / recent_grouped["recent_rows"]
    )

    recent_latest = (
        recent.sort_values(SITE_KEY_COLUMNS + ["_origin_period", "origin_year_month"], ascending=[True, True, True, False, False])
        .drop_duplicates(SITE_KEY_COLUMNS, keep="first")
        [
            SITE_KEY_COLUMNS
            + [
                "origin_year_month",
                "probability_bloom_h",
                "threshold_margin",
                "predicted_bloom_h",
                "risk_band",
                "evidence_priority",
            ]
        ]
        .rename(
            columns={
                "origin_year_month": "recent_latest_origin_year_month",
                "probability_bloom_h": "recent_latest_probability",
                "threshold_margin": "recent_latest_threshold_margin",
                "predicted_bloom_h": "recent_latest_predicted_bloom",
                "risk_band": "recent_latest_risk_band",
                "evidence_priority": "recent_latest_evidence_priority",
            }
        )
    )

    out = grouped.merge(latest, on=SITE_KEY_COLUMNS, how="left")
    out = out.merge(recent_grouped, on=SITE_KEY_COLUMNS, how="left")
    out = out.merge(recent_latest, on=SITE_KEY_COLUMNS, how="left")
    for column in [
        "recent_rows",
        "recent_predicted_bloom_months",
        "recent_mean_probability",
        "recent_max_probability",
        "recent_mean_threshold_margin",
        "recent_max_threshold_margin",
        "recent_mean_evidence_priority",
        "recent_predicted_bloom_rate",
    ]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
    out["active_in_recent_window"] = out["active_in_recent_window"].fillna(False).astype(bool)
    return out.sort_values(["horizon_months", "source_id", "site_id"]).reset_index(drop=True)


def build_sustained_risk(
    site_summary: pd.DataFrame,
    *,
    min_recent_rows: int,
    min_sustained_months: int,
    top_n_per_horizon: int,
) -> pd.DataFrame:
    flagged = site_summary[
        (site_summary["active_in_recent_window"])
        & (site_summary["recent_rows"] >= int(min_recent_rows))
        & (site_summary["recent_predicted_bloom_months"] >= int(min_sustained_months))
    ].copy()
    if flagged.empty:
        return flagged
    flagged = flagged.sort_values(
        [
            "horizon_months",
            "recent_predicted_bloom_months",
            "recent_predicted_bloom_rate",
            "recent_max_probability",
            "recent_latest_probability",
            "recent_mean_evidence_priority",
            "source_id",
            "site_id",
        ],
        ascending=[True, False, False, False, False, False, True, True],
        kind="mergesort",
    )
    flagged["rank_within_horizon"] = flagged.groupby("horizon_months").cumcount() + 1
    if top_n_per_horizon > 0:
        flagged = flagged[flagged["rank_within_horizon"] <= int(top_n_per_horizon)].copy()
    return flagged.reset_index(drop=True)


def build_low_evidence_high_risk(
    site_summary: pd.DataFrame,
    *,
    evidence_threshold: float,
    top_n_per_horizon: int,
) -> pd.DataFrame:
    flagged = site_summary[
        (site_summary["active_in_recent_window"])
        & (site_summary["recent_latest_predicted_bloom"].fillna(False).astype(bool))
        & (site_summary["recent_latest_evidence_priority"] <= float(evidence_threshold))
    ].copy()
    if flagged.empty:
        return flagged
    flagged = flagged.sort_values(
        [
            "horizon_months",
            "recent_latest_probability",
            "recent_latest_threshold_margin",
            "recent_latest_evidence_priority",
            "source_id",
            "site_id",
        ],
        ascending=[True, False, False, True, True, True],
        kind="mergesort",
    )
    flagged["rank_within_horizon"] = flagged.groupby("horizon_months").cumcount() + 1
    if top_n_per_horizon > 0:
        flagged = flagged[flagged["rank_within_horizon"] <= int(top_n_per_horizon)].copy()
    return flagged.reset_index(drop=True)


def select_trajectory_sites(recent_site_risk: pd.DataFrame, top_sites_per_horizon: int) -> pd.DataFrame:
    required = {"source_id", "site_id", "horizon_months", "rank_within_horizon"}
    missing = required.difference(recent_site_risk.columns)
    if missing:
        raise ValueError(f"Recent site risk input is missing columns: {sorted(missing)}")
    selected = recent_site_risk.copy()
    selected["rank_within_horizon"] = pd.to_numeric(selected["rank_within_horizon"], errors="coerce")
    selected = selected[selected["rank_within_horizon"] <= int(top_sites_per_horizon)].copy()
    return selected[SITE_KEY_COLUMNS + ["rank_within_horizon"]].rename(
        columns={"rank_within_horizon": "review_rank_within_horizon"}
    )


def build_top_site_trajectories(scores: pd.DataFrame, selected_sites: pd.DataFrame) -> pd.DataFrame:
    if selected_sites.empty:
        return pd.DataFrame()
    enriched = add_review_features(scores)
    out = enriched.merge(selected_sites, on=SITE_KEY_COLUMNS, how="inner")
    if out.empty:
        return pd.DataFrame(columns=TRAJECTORY_COLUMNS)
    return out[TRAJECTORY_COLUMNS].sort_values(
        ["horizon_months", "review_rank_within_horizon", "source_id", "site_id", "origin_year_month"]
    )


def prepare_recent_site_risk(path: Path) -> pd.DataFrame:
    recent = pd.read_csv(path)
    if recent.empty:
        return recent
    recent["risk_review_view"] = "recent_latest_site_top_risks"
    return recent


def write_report(
    *,
    args: argparse.Namespace,
    site_summary: pd.DataFrame,
    recent_site_risk: pd.DataFrame,
    trajectories: pd.DataFrame,
    sustained_risk: pd.DataFrame,
    low_evidence_high_risk: pd.DataFrame,
    started_at_utc: str,
) -> None:
    overall = (
        site_summary.groupby("horizon_months", sort=True)
        .agg(
            sites=("site_id", "size"),
            active_recent_sites=("active_in_recent_window", "sum"),
            recent_predicted_sites=("recent_latest_predicted_bloom", "sum"),
            mean_recent_latest_probability=("recent_latest_probability", "mean"),
            sustained_risk_sites=("recent_predicted_bloom_months", lambda values: int((values >= args.min_sustained_months).sum())),
        )
        .reset_index()
    )
    source_counts = (
        recent_site_risk.groupby(["horizon_months", "source_id"], dropna=False)
        .size()
        .reset_index()
    )
    source_counts.columns = ["horizon_months", "source_id", "recent_top_sites"]
    source_counts = source_counts.sort_values(["horizon_months", "recent_top_sites", "source_id"], ascending=[True, False, True])
    lines = [
        "# Operational Site Review v0",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Started at UTC: `{started_at_utc}`",
        "",
        "## Scope",
        "",
        "This review aggregates frozen operational scores by source-scoped site. It does not refit or change the model.",
        f"Recent window: last `{int(args.recent_months)}` months.",
        "",
        "## Horizon Summary",
        "",
        "| horizon | sites | active recent sites | recent predicted sites | mean recent latest probability | sustained risk sites |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in dataframe_rows(overall):
        lines.append(
            f"| {int(row.horizon_months)} | {_format_int(row.sites)} | {_format_int(row.active_recent_sites)} | "
            f"{_format_int(row.recent_predicted_sites)} | {_format_float(row.mean_recent_latest_probability)} | "
            f"{_format_int(row.sustained_risk_sites)} |"
        )

    lines.extend(["", "## Recent Top Source Counts", "", "| horizon | source | top sites |", "|---:|---|---:|"])
    for row in dataframe_rows(source_counts.groupby("horizon_months", sort=True).head(5)):
        lines.append(f"| {int(row.horizon_months)} | `{row.source_id}` | {_format_int(row.recent_top_sites)} |")

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Site summary: `{args.site_summary}`",
            f"- Site summary parquet: `{args.site_summary_parquet}`",
            f"- Recent site risk: `{args.recent_site_risk}`",
            f"- Top-site trajectories: `{args.trajectories}`",
            f"- Sustained risk: `{args.sustained_risk}`",
            f"- Low-evidence high-risk: `{args.low_evidence_high_risk}`",
            f"- Manifest: `{args.manifest}`",
            "",
            f"Site summary rows: `{_format_int(len(site_summary))}`",
            f"Recent site-risk rows: `{_format_int(len(recent_site_risk))}`",
            f"Trajectory rows: `{_format_int(len(trajectories))}`",
            f"Sustained risk rows: `{_format_int(len(sustained_risk))}`",
            f"Low-evidence high-risk rows: `{_format_int(len(low_evidence_high_risk))}`",
        ]
    )
    _write_text_atomic("\n".join(lines) + "\n", args.report)


def build_manifest(
    *,
    args: argparse.Namespace,
    score_parts: list[Path],
    site_summary: pd.DataFrame,
    recent_site_risk: pd.DataFrame,
    trajectories: pd.DataFrame,
    sustained_risk: pd.DataFrame,
    low_evidence_high_risk: pd.DataFrame,
    started_at_utc: str,
) -> dict[str, Any]:
    inputs = [args.scores, args.recent_latest_site_top_risks, args.operational_manifest]
    outputs = [
        args.site_summary,
        args.site_summary_parquet,
        args.recent_site_risk,
        args.trajectories,
        args.sustained_risk,
        args.low_evidence_high_risk,
        args.report,
    ]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at_utc,
        "review_version": REVIEW_VERSION,
        "config": {
            "recent_months": int(args.recent_months),
            "top_sites_per_horizon": int(args.top_sites_per_horizon),
            "top_n_per_horizon": int(args.top_n_per_horizon),
            "min_recent_rows": int(args.min_recent_rows),
            "min_sustained_months": int(args.min_sustained_months),
            "low_evidence_threshold": float(args.low_evidence_threshold),
        },
        "row_counts": {
            "score_parts": len(score_parts),
            "site_summary_rows": int(len(site_summary)),
            "recent_site_risk_rows": int(len(recent_site_risk)),
            "trajectory_rows": int(len(trajectories)),
            "sustained_risk_rows": int(len(sustained_risk)),
            "low_evidence_high_risk_rows": int(len(low_evidence_high_risk)),
        },
        "inputs": [_path_record(path) for path in inputs if path.exists()],
        "score_parts": [_file_record(path) for path in score_parts],
        "outputs": [_file_record(path) for path in outputs if path.exists()],
        "script": _file_record(Path(__file__)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, default=DEFAULT_SCORES)
    parser.add_argument("--recent-latest-site-top-risks", type=Path, default=DEFAULT_RECENT_LATEST_SITE_TOP_RISKS)
    parser.add_argument("--operational-manifest", type=Path, default=DEFAULT_OPERATIONAL_MANIFEST)
    parser.add_argument("--site-summary", type=Path, default=DEFAULT_SITE_SUMMARY)
    parser.add_argument("--site-summary-parquet", type=Path, default=DEFAULT_SITE_SUMMARY_PARQUET)
    parser.add_argument("--recent-site-risk", type=Path, default=DEFAULT_RECENT_SITE_RISK)
    parser.add_argument("--trajectories", type=Path, default=DEFAULT_TRAJECTORIES)
    parser.add_argument("--sustained-risk", type=Path, default=DEFAULT_SUSTAINED_RISK)
    parser.add_argument("--low-evidence-high-risk", type=Path, default=DEFAULT_LOW_EVIDENCE_HIGH_RISK)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--recent-months", type=int, default=24)
    parser.add_argument("--top-sites-per-horizon", type=int, default=100)
    parser.add_argument("--top-n-per-horizon", type=int, default=1000)
    parser.add_argument("--min-recent-rows", type=int, default=3)
    parser.add_argument("--min-sustained-months", type=int, default=3)
    parser.add_argument("--low-evidence-threshold", type=float, default=0.33)
    return parser.parse_args()


def main() -> None:
    started = time.monotonic()
    started_at_utc = datetime.now(timezone.utc).isoformat()
    args = parse_args()

    print(f"loading recent site risk {args.recent_latest_site_top_risks}", flush=True)
    recent_site_risk = prepare_recent_site_risk(args.recent_latest_site_top_risks)
    selected_sites = select_trajectory_sites(recent_site_risk, args.top_sites_per_horizon)

    score_parts = score_part_paths(args.scores)
    summary_parts: list[pd.DataFrame] = []
    trajectory_parts: list[pd.DataFrame] = []
    for index, part_path in enumerate(score_parts, start=1):
        print(f"processing score part {index}/{len(score_parts)}: {part_path}", flush=True)
        scores = read_score_part(part_path)
        summary_parts.append(build_site_summary(scores, args.recent_months))
        trajectory_parts.append(build_top_site_trajectories(scores, selected_sites))
        print(f"processed {len(scores):,} score rows; elapsed={_elapsed(started)}", flush=True)

    site_summary = pd.concat(summary_parts, ignore_index=True).sort_values(["horizon_months", "source_id", "site_id"])
    non_empty_trajectories = [part for part in trajectory_parts if not part.empty]
    trajectories = (
        pd.concat(non_empty_trajectories, ignore_index=True).sort_values(
            ["horizon_months", "review_rank_within_horizon", "source_id", "site_id", "origin_year_month"]
        )
        if non_empty_trajectories
        else pd.DataFrame(columns=TRAJECTORY_COLUMNS)
    )
    sustained_risk = build_sustained_risk(
        site_summary,
        min_recent_rows=args.min_recent_rows,
        min_sustained_months=args.min_sustained_months,
        top_n_per_horizon=args.top_n_per_horizon,
    )
    low_evidence_high_risk = build_low_evidence_high_risk(
        site_summary,
        evidence_threshold=args.low_evidence_threshold,
        top_n_per_horizon=args.top_n_per_horizon,
    )

    _write_csv_atomic(site_summary, args.site_summary)
    _write_parquet_atomic(site_summary, args.site_summary_parquet)
    _write_csv_atomic(recent_site_risk, args.recent_site_risk)
    _write_csv_atomic(trajectories, args.trajectories)
    _write_csv_atomic(sustained_risk, args.sustained_risk)
    _write_csv_atomic(low_evidence_high_risk, args.low_evidence_high_risk)
    write_report(
        args=args,
        site_summary=site_summary,
        recent_site_risk=recent_site_risk,
        trajectories=trajectories,
        sustained_risk=sustained_risk,
        low_evidence_high_risk=low_evidence_high_risk,
        started_at_utc=started_at_utc,
    )
    manifest = build_manifest(
        args=args,
        score_parts=score_parts,
        site_summary=site_summary,
        recent_site_risk=recent_site_risk,
        trajectories=trajectories,
        sustained_risk=sustained_risk,
        low_evidence_high_risk=low_evidence_high_risk,
        started_at_utc=started_at_utc,
    )
    _write_json_atomic(manifest, args.manifest)

    print(f"wrote {args.site_summary}", flush=True)
    print(f"wrote {args.site_summary_parquet}", flush=True)
    print(f"wrote {args.recent_site_risk}", flush=True)
    print(f"wrote {args.trajectories}", flush=True)
    print(f"wrote {args.sustained_risk}", flush=True)
    print(f"wrote {args.low_evidence_high_risk}", flush=True)
    print(f"wrote {args.report}", flush=True)
    print(f"wrote {args.manifest}", flush=True)
    print(f"done; elapsed={_elapsed(started)}", flush=True)


if __name__ == "__main__":
    main()
