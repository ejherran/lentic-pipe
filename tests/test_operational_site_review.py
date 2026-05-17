from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.experiments.build_operational_site_review import (
    build_low_evidence_high_risk,
    build_site_summary,
    build_sustained_risk,
    build_top_site_trajectories,
    select_trajectory_sites,
)


def _score_rows() -> pd.DataFrame:
    base = {
        "threshold_bloom_h": 0.5,
        "current_model_score_name": "score",
        "source_selector_score_name": "score",
        "evidence_N": 0.5,
        "evidence_F": 0.5,
        "evidence_T": 0.5,
        "evidence_T_no_chla": 0.5,
    }
    rows = [
        {
            **base,
            "source_id": "A",
            "site_id": "s1",
            "origin_year_month": "2024-01",
            "horizon_months": 1,
            "probability_bloom_h": 0.2,
            "predicted_bloom_h": False,
            "risk_band": "low",
            "full_evidence": 0.8,
            "exogenous_evidence": 0.8,
        },
        {
            **base,
            "source_id": "A",
            "site_id": "s1",
            "origin_year_month": "2024-02",
            "horizon_months": 1,
            "probability_bloom_h": 0.7,
            "predicted_bloom_h": True,
            "risk_band": "high",
            "full_evidence": 0.7,
            "exogenous_evidence": 0.7,
        },
        {
            **base,
            "source_id": "A",
            "site_id": "s2",
            "origin_year_month": "2024-02",
            "horizon_months": 1,
            "probability_bloom_h": 0.8,
            "predicted_bloom_h": True,
            "risk_band": "very_high",
            "full_evidence": 0.2,
            "exogenous_evidence": 0.2,
        },
        {
            **base,
            "source_id": "B",
            "site_id": "s3",
            "origin_year_month": "2023-01",
            "horizon_months": 1,
            "probability_bloom_h": 0.9,
            "predicted_bloom_h": True,
            "risk_band": "very_high",
            "full_evidence": 0.9,
            "exogenous_evidence": 0.9,
        },
        {
            **base,
            "source_id": "A",
            "site_id": "s1",
            "origin_year_month": "2024-02",
            "horizon_months": 2,
            "probability_bloom_h": 0.65,
            "predicted_bloom_h": True,
            "risk_band": "high",
            "full_evidence": 0.6,
            "exogenous_evidence": 0.6,
        },
    ]
    return pd.DataFrame(rows)


def _recent_top_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rank_within_horizon": [1, 2, 1],
            "recent_window_start": ["2024-01", "2024-01", "2024-01"],
            "recent_window_end": ["2024-02", "2024-02", "2024-02"],
            "source_id": ["A", "A", "A"],
            "site_id": ["s2", "s1", "s1"],
            "origin_year_month": ["2024-02", "2024-02", "2024-02"],
            "horizon_months": [1, 1, 2],
            "probability_bloom_h": [0.8, 0.7, 0.65],
            "threshold_bloom_h": [0.5, 0.5, 0.5],
            "threshold_margin": [0.3, 0.2, 0.15],
            "predicted_bloom_h": [True, True, True],
            "risk_band": ["very_high", "high", "high"],
            "evidence_priority": [0.2, 0.7, 0.6],
            "current_model_score_name": ["score", "score", "score"],
            "source_selector_score_name": ["score", "score", "score"],
            "full_evidence": [0.2, 0.7, 0.6],
            "exogenous_evidence": [0.2, 0.7, 0.6],
        }
    )


def test_site_summary_tracks_recent_latest_and_inactive_sites() -> None:
    summary = build_site_summary(_score_rows(), recent_months=2)
    s1 = summary[(summary["source_id"] == "A") & (summary["site_id"] == "s1") & (summary["horizon_months"] == 1)].iloc[0]
    s3 = summary[(summary["source_id"] == "B") & (summary["site_id"] == "s3") & (summary["horizon_months"] == 1)].iloc[0]

    assert s1["rows"] == 2
    assert s1["latest_origin_year_month"] == "2024-02"
    assert s1["recent_rows"] == 2
    assert s1["recent_predicted_bloom_months"] == 1
    assert bool(s1["active_in_recent_window"])
    assert not bool(s3["active_in_recent_window"])
    assert s3["recent_rows"] == 0


def test_sustained_and_low_evidence_flags_are_site_scoped() -> None:
    summary = build_site_summary(_score_rows(), recent_months=2)
    sustained = build_sustained_risk(summary, min_recent_rows=1, min_sustained_months=1, top_n_per_horizon=10)
    low_evidence = build_low_evidence_high_risk(summary, evidence_threshold=0.33, top_n_per_horizon=10)

    assert {"A:s1", "A:s2"}.issubset(set(sustained["source_id"] + ":" + sustained["site_id"]))
    assert low_evidence["site_id"].tolist() == ["s2"]
    assert low_evidence["recent_latest_evidence_priority"].iloc[0] == 0.2


def test_top_site_trajectories_use_recent_review_keys() -> None:
    selected = select_trajectory_sites(_recent_top_rows(), top_sites_per_horizon=1)
    trajectories = build_top_site_trajectories(_score_rows(), selected)

    assert set(trajectories["site_id"]) == {"s2", "s1"}
    assert trajectories["review_rank_within_horizon"].max() == 1
    assert set(trajectories["horizon_months"]) == {1, 2}


def test_operational_site_review_cli_writes_signed_outputs(tmp_path: Path) -> None:
    scores_dir = tmp_path / "scores.parquet"
    scores_dir.mkdir()
    _score_rows()[_score_rows()["horizon_months"] == 1].to_parquet(scores_dir / "part-h01.parquet", index=False)
    _score_rows()[_score_rows()["horizon_months"] == 2].to_parquet(scores_dir / "part-h02.parquet", index=False)
    recent_top_path = tmp_path / "recent_top.csv"
    manifest_input = tmp_path / "operational_manifest.json"
    site_summary_path = tmp_path / "site_summary.csv"
    site_summary_parquet_path = tmp_path / "site_summary.parquet"
    recent_site_risk_path = tmp_path / "recent_site_risk.csv"
    trajectories_path = tmp_path / "trajectories.csv"
    sustained_path = tmp_path / "sustained.csv"
    low_evidence_path = tmp_path / "low_evidence.csv"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"

    _recent_top_rows().to_csv(recent_top_path, index=False)
    manifest_input.write_text('{"operational_score_version": "operational_scores_v0"}\n', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "src/experiments/build_operational_site_review.py",
            "--scores",
            str(scores_dir),
            "--recent-latest-site-top-risks",
            str(recent_top_path),
            "--operational-manifest",
            str(manifest_input),
            "--site-summary",
            str(site_summary_path),
            "--site-summary-parquet",
            str(site_summary_parquet_path),
            "--recent-site-risk",
            str(recent_site_risk_path),
            "--trajectories",
            str(trajectories_path),
            "--sustained-risk",
            str(sustained_path),
            "--low-evidence-high-risk",
            str(low_evidence_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--recent-months",
            "2",
            "--top-sites-per-horizon",
            "1",
            "--min-recent-rows",
            "1",
            "--min-sustained-months",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "wrote" in result.stdout
    for path in [
        site_summary_path,
        site_summary_parquet_path,
        recent_site_risk_path,
        trajectories_path,
        sustained_path,
        low_evidence_path,
        report_path,
        manifest_path,
    ]:
        assert path.exists()
        assert path.stat().st_size > 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    site_summary_csv = pd.read_csv(site_summary_path)
    site_summary_parquet = pd.read_parquet(site_summary_parquet_path)
    assert manifest["row_counts"]["site_summary_rows"] == 4
    assert manifest["row_counts"]["recent_site_risk_rows"] == 3
    assert manifest["row_counts"]["score_parts"] == 2
    assert len(site_summary_csv) == len(site_summary_parquet) == 4
    assert site_summary_parquet["horizon_months"].tolist() == site_summary_csv["horizon_months"].tolist()
    assert all(len(record["sha256"]) == 64 for record in manifest["outputs"])
