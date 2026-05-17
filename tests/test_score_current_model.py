from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from src.experiments.refine_expert_fuzzy import STATE_FEATURE_COLUMNS
from src.experiments.score_current_model import (
    _add_source_selector,
    build_latest_site_top_risks,
    build_recent_latest_site_top_risks,
    build_recent_top_risks,
    build_summary,
    build_top_risks,
)


def _identity_calibrator() -> IsotonicRegression:
    return IsotonicRegression(out_of_bounds="clip").fit([0.0, 1.0], [0.0, 1.0])


def _write_calibrator(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"calibrator": _identity_calibrator(), "threshold": 0.5}, path)


def _panel() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_id": ["A", "A", "B", "C"],
            "site_id": ["s1", "s2", "s3", "s4"],
            "year_month": ["2020-01", "2020-02", "2020-01", "2020-01"],
            "month": [1, 2, 1, 1],
            "risk_chla": [0.20, 0.80, 0.40, 0.60],
        }
    )


def _splits() -> pd.DataFrame:
    rows = []
    for horizon in [1, 2]:
        rows.extend(
            [
                {
                    "source_id": "A",
                    "site_id": "s1",
                    "origin_year_month": "2020-01",
                    "horizon_months": horizon,
                    "split": "train",
                    "bloom_h": 0,
                    "target_risk_chla_h": 0.0,
                },
                {
                    "source_id": "A",
                    "site_id": "s2",
                    "origin_year_month": "2020-02",
                    "horizon_months": horizon,
                    "split": "train",
                    "bloom_h": 1,
                    "target_risk_chla_h": 1.0,
                },
            ]
        )
    return pd.DataFrame(rows)


def _state() -> pd.DataFrame:
    frame = _panel()[["source_id", "site_id", "year_month"]].copy()
    for column in STATE_FEATURE_COLUMNS:
        frame[column] = 0.0
    frame["irc1"] = [0.80, 0.30, 0.70, 0.90]
    frame["irc1_no_chla"] = [0.70, 0.20, 0.60, 0.80]
    frame["evidence_N"] = [1.0, 0.5, 0.8, 0.4]
    frame["evidence_F"] = [1.0, 0.5, 0.8, 0.4]
    frame["evidence_T"] = [1.0, 0.5, 0.8, 0.4]
    frame["evidence_T_no_chla"] = [1.0, 0.5, 0.8, 0.4]
    return frame


def test_source_selector_uses_known_sources_and_fallback() -> None:
    frame = pd.DataFrame(
        {
            "source_id": ["A", "B", "C"],
            "baseline_calibrated": [0.1, 0.2, 0.3],
            "blend_irc1_w0p25": [0.4, 0.5, 0.6],
            "gate_full_irc1_w0p25": [0.7, 0.8, 0.9],
        }
    )
    selection_row = pd.Series({"score_name": "source_selector"})
    source_selection = pd.DataFrame(
        {
            "source_id": ["A", "B"],
            "selected_score": ["gate_full_irc1_w0p25", "blend_irc1_w0p25"],
            "selection_reason": ["validation", "fallback_low_rows_or_single_class"],
        }
    )

    selected, fallback = _add_source_selector(frame, selection_row=selection_row, source_selection=source_selection)

    assert fallback == "blend_irc1_w0p25"
    assert selected["source_selector_score_name"].tolist() == [
        "gate_full_irc1_w0p25",
        "blend_irc1_w0p25",
        "blend_irc1_w0p25",
    ]
    assert selected["source_selector_known_source"].tolist() == [True, True, False]
    assert selected["source_selector"].tolist() == [0.7, 0.5, 0.6]


def test_build_summary_reports_overall_and_source_rows() -> None:
    predictions = pd.DataFrame(
        {
            "source_id": ["A", "A", "B"],
            "site_id": ["s1", "s2", "s3"],
            "origin_year_month": ["2020-01", "2020-02", "2020-01"],
            "horizon_months": [1, 1, 1],
            "probability_bloom_h": [0.1, 0.7, 0.9],
            "predicted_bloom_h": [False, True, True],
            "full_evidence": [0.5, 0.7, 0.9],
            "exogenous_evidence": [0.4, 0.6, 0.8],
        }
    )

    summary = build_summary(predictions)
    overall = summary[(summary["source_id"] == "all") & (summary["horizon_months"] == 1)].iloc[0]

    assert len(summary) == 3
    assert overall["rows"] == 3
    assert overall["predicted_blooms"] == 2
    assert overall["predicted_bloom_rate"] == 2 / 3


def test_build_top_risks_uses_deterministic_tie_breakers() -> None:
    predictions = pd.DataFrame(
        {
            "source_id": ["B", "A", "A"],
            "site_id": ["low-evidence", "older", "recent"],
            "origin_year_month": ["2025-01", "2020-01", "2024-01"],
            "horizon_months": [1, 1, 1],
            "probability_bloom_h": [0.9, 0.9, 0.9],
            "threshold_bloom_h": [0.5, 0.5, 0.5],
            "predicted_bloom_h": [True, True, True],
            "risk_band": ["very_high", "very_high", "very_high"],
            "current_model_score_name": ["score", "score", "score"],
            "source_selector_score_name": ["score", "score", "score"],
            "full_evidence": [0.1, 0.8, 0.8],
            "exogenous_evidence": [0.1, 0.8, 0.8],
        }
    )

    top = build_top_risks(predictions, top_n=3)

    assert top["site_id"].tolist() == ["recent", "older", "low-evidence"]
    assert top["rank_within_horizon"].tolist() == [1, 2, 3]
    assert top["threshold_margin"].tolist() == [0.4, 0.4, 0.4]
    assert top["evidence_priority"].tolist() == [0.8, 0.8, 0.1]


def test_recent_and_latest_site_top_risks_limit_operational_scope() -> None:
    predictions = pd.DataFrame(
        {
            "source_id": ["A", "A", "A", "B"],
            "site_id": ["s1", "s1", "s2", "s3"],
            "origin_year_month": ["2023-01", "2024-01", "2024-02", "2024-02"],
            "horizon_months": [1, 1, 1, 1],
            "probability_bloom_h": [0.99, 0.70, 0.80, 0.60],
            "threshold_bloom_h": [0.5, 0.5, 0.5, 0.5],
            "predicted_bloom_h": [True, True, True, True],
            "risk_band": ["very_high", "high", "very_high", "high"],
            "current_model_score_name": ["score"] * 4,
            "source_selector_score_name": ["score"] * 4,
            "full_evidence": [0.9, 0.8, 0.7, 0.6],
            "exogenous_evidence": [0.9, 0.8, 0.7, 0.6],
        }
    )

    recent = build_recent_top_risks(predictions, top_n=10, recent_months=2)
    latest = build_latest_site_top_risks(predictions, top_n=10)
    recent_latest = build_recent_latest_site_top_risks(predictions, top_n=10, recent_months=2)

    assert recent["origin_year_month"].tolist() == ["2024-02", "2024-01", "2024-02"]
    assert recent["recent_window_start"].eq("2024-01").all()
    assert recent["recent_window_end"].eq("2024-02").all()
    assert latest["site_id"].tolist() == ["s2", "s1", "s3"]
    assert "2023-01" not in latest["origin_year_month"].tolist()
    assert recent_latest["site_id"].tolist() == ["s2", "s1", "s3"]
    assert recent_latest["recent_window_start"].eq("2024-01").all()
    assert "2023-01" not in recent_latest["origin_year_month"].tolist()


def test_score_current_model_cli_writes_signed_operational_outputs(tmp_path: Path) -> None:
    panel_path = tmp_path / "panel.parquet"
    splits_path = tmp_path / "splits.parquet"
    state_path = tmp_path / "state.parquet"
    baseline_selection_path = tmp_path / "baseline_selection.csv"
    baseline_calibrators_dir = tmp_path / "baseline_calibrators"
    fuzzy_calibrators_dir = tmp_path / "fuzzy_calibrators"
    selection_path = tmp_path / "selection.csv"
    source_selection_path = tmp_path / "source_selection.csv"
    registry_path = tmp_path / "registry.json"
    current_manifest_path = tmp_path / "current_manifest.json"
    scores_path = tmp_path / "scores.parquet"
    summary_path = tmp_path / "summary.csv"
    top_risks_path = tmp_path / "top_risks.csv"
    recent_top_risks_path = tmp_path / "recent_top_risks.csv"
    latest_site_top_risks_path = tmp_path / "latest_site_top_risks.csv"
    recent_latest_site_top_risks_path = tmp_path / "recent_latest_site_top_risks.csv"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"

    _panel().to_parquet(panel_path, index=False)
    _splits().to_parquet(splits_path, index=False)
    _state().to_parquet(state_path, index=False)
    pd.DataFrame(
        {
            "selection_task": ["bloom", "bloom"],
            "horizon_months": [1, 2],
            "model": ["persistence", "persistence"],
        }
    ).to_csv(baseline_selection_path, index=False)
    pd.DataFrame(
        {
            "horizon_months": [1, 2],
            "score_name": ["blend_irc1_w0p25", "source_selector"],
            "selected_threshold": [0.5, 0.5],
            "selection_policy": ["validation", "validation"],
        }
    ).to_csv(selection_path, index=False)
    pd.DataFrame(
        {
            "source_id": ["A", "B"],
            "selected_score": ["gate_full_irc1_w0p25", "blend_irc1_w0p25"],
            "validation_rows": [10, 1],
            "selection_reason": ["validation", "fallback_low_rows_or_single_class"],
            "validation_pr_auc": [1.0, None],
            "validation_brier": [0.1, None],
            "horizon_months": [2, 2],
        }
    ).to_csv(source_selection_path, index=False)
    registry_path.write_text('{"model_version": "current_refined_fuzzy_v0"}\n', encoding="utf-8")
    current_manifest_path.write_text('{"model_version": "current_refined_fuzzy_v0"}\n', encoding="utf-8")

    for horizon in [1, 2]:
        _write_calibrator(baseline_calibrators_dir / f"persistence_h{horizon}_isotonic.joblib")
        _write_calibrator(fuzzy_calibrators_dir / f"irc1_h{horizon}_isotonic.joblib")
        _write_calibrator(fuzzy_calibrators_dir / f"irc1_no_chla_h{horizon}_isotonic.joblib")

    result = subprocess.run(
        [
            sys.executable,
            "src/experiments/score_current_model.py",
            "--panel",
            str(panel_path),
            "--splits",
            str(splits_path),
            "--state",
            str(state_path),
            "--baseline-selection",
            str(baseline_selection_path),
            "--baseline-calibrators-dir",
            str(baseline_calibrators_dir),
            "--fuzzy-calibrators-dir",
            str(fuzzy_calibrators_dir),
            "--selection",
            str(selection_path),
            "--source-selection",
            str(source_selection_path),
            "--current-registry",
            str(registry_path),
            "--current-manifest",
            str(current_manifest_path),
            "--scores",
            str(scores_path),
            "--summary",
            str(summary_path),
            "--top-risks",
            str(top_risks_path),
            "--recent-top-risks",
            str(recent_top_risks_path),
            "--latest-site-top-risks",
            str(latest_site_top_risks_path),
            "--recent-latest-site-top-risks",
            str(recent_latest_site_top_risks_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--horizons",
            "1",
            "2",
            "--top-n",
            "2",
            "--recent-months",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "wrote" in result.stdout
    for path in [
        scores_path,
        summary_path,
        top_risks_path,
        recent_top_risks_path,
        latest_site_top_risks_path,
        recent_latest_site_top_risks_path,
        report_path,
        manifest_path,
    ]:
        assert path.exists()
        assert path.stat().st_size > 0
    scores = pd.read_parquet(scores_path)
    assert len(scores) == 8
    assert scores["model_version"].eq("current_refined_fuzzy_v0").all()
    h2_unknown = scores[
        (scores["horizon_months"] == 2)
        & (scores["source_id"] == "C")
        & (scores["current_model_score_name"] == "source_selector")
    ].iloc[0]
    assert not bool(h2_unknown["source_selector_known_source"])
    assert h2_unknown["source_selector_score_name"] == "blend_irc1_w0p25"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["row_counts"]["score_rows"] == 8
    assert manifest["row_counts"]["recent_top_risk_rows"] == 4
    assert manifest["row_counts"]["latest_site_top_risk_rows"] == 4
    assert manifest["row_counts"]["recent_latest_site_top_risk_rows"] == 4
    assert all(len(record["sha256"]) == 64 for record in manifest["outputs"])
    recent_top = pd.read_csv(recent_top_risks_path)
    latest_site_top = pd.read_csv(latest_site_top_risks_path)
    recent_latest_site_top = pd.read_csv(recent_latest_site_top_risks_path)
    assert {"recent_window_start", "recent_window_end"}.issubset(recent_top.columns)
    assert "threshold_margin" in latest_site_top.columns
    assert {"recent_window_start", "recent_window_end", "threshold_margin"}.issubset(recent_latest_site_top.columns)

    resumed = subprocess.run(
        [
            sys.executable,
            "src/experiments/score_current_model.py",
            "--panel",
            str(panel_path),
            "--splits",
            str(splits_path),
            "--state",
            str(state_path),
            "--baseline-selection",
            str(baseline_selection_path),
            "--baseline-calibrators-dir",
            str(baseline_calibrators_dir),
            "--fuzzy-calibrators-dir",
            str(fuzzy_calibrators_dir),
            "--selection",
            str(selection_path),
            "--source-selection",
            str(source_selection_path),
            "--current-registry",
            str(registry_path),
            "--current-manifest",
            str(current_manifest_path),
            "--scores",
            str(scores_path),
            "--summary",
            str(summary_path),
            "--top-risks",
            str(top_risks_path),
            "--recent-top-risks",
            str(recent_top_risks_path),
            "--latest-site-top-risks",
            str(latest_site_top_risks_path),
            "--recent-latest-site-top-risks",
            str(recent_latest_site_top_risks_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--horizons",
            "1",
            "2",
            "--top-n",
            "2",
            "--recent-months",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "rebuilding reports only" in resumed.stdout
