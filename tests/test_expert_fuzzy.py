from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.fuzzy.expert import EVIDENCE_COLUMNS, STATE_COLUMNS, build_expert_state


def _synthetic_panel() -> pd.DataFrame:
    rows = [
        {
            "source_id": "unit",
            "site_id": "A",
            "site_id_source": "A",
            "site_name": "Lake A",
            "year_month": "2020-01",
            "mean_TP_ugL": 8.0,
            "mean_TN_ugL": 250.0,
            "TN_TP_ratio": 31.25,
            "mean_DO_mgL": 9.0,
            "mean_pH": 7.6,
            "mean_turbidity_NTU": 2.0,
            "mean_secchi_depth_m": 4.0,
            "mean_temperature_C": 10.0,
            "mean_chlorophyll_a_ugL": 1.0,
            "risk_chla": 0.0,
        },
        {
            "source_id": "unit",
            "site_id": "A",
            "site_id_source": "A",
            "site_name": "Lake A",
            "year_month": "2020-02",
            "mean_TP_ugL": 150.0,
            "mean_TN_ugL": 2500.0,
            "TN_TP_ratio": 16.67,
            "mean_DO_mgL": 2.0,
            "mean_pH": 10.0,
            "mean_turbidity_NTU": 90.0,
            "mean_secchi_depth_m": 0.2,
            "mean_temperature_C": 26.0,
            "mean_chlorophyll_a_ugL": 45.0,
            "risk_chla": 1.0,
        },
        {
            "source_id": "unit",
            "site_id": "B",
            "site_id_source": "B",
            "site_name": "Lake B",
            "year_month": "2020-01",
            "mean_TP_ugL": None,
            "mean_TN_ugL": None,
            "TN_TP_ratio": None,
            "mean_DO_mgL": None,
            "mean_pH": None,
            "mean_turbidity_NTU": None,
            "mean_secchi_depth_m": None,
            "mean_temperature_C": None,
            "mean_chlorophyll_a_ugL": None,
            "risk_chla": None,
        },
    ]
    frame = pd.DataFrame(rows)
    for variable in [
        "TP_ugL",
        "TN_ugL",
        "DO_mgL",
        "pH",
        "turbidity_NTU",
        "secchi_depth_m",
        "temperature_C",
        "chlorophyll_a_ugL",
    ]:
        frame[f"qc_ok_rate_{variable}"] = 1.0
    return frame


def _synthetic_splits() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_id": "unit",
                "site_id": "A",
                "origin_year_month": "2020-01",
                "horizon_months": 1,
                "split": "train",
                "bloom_h": True,
                "target_risk_chla_h": 1.0,
            },
            {
                "source_id": "unit",
                "site_id": "A",
                "origin_year_month": "2020-02",
                "horizon_months": 1,
                "split": "validation",
                "bloom_h": True,
                "target_risk_chla_h": 1.0,
            },
            {
                "source_id": "unit",
                "site_id": "B",
                "origin_year_month": "2020-01",
                "horizon_months": 1,
                "split": "test",
                "bloom_h": False,
                "target_risk_chla_h": 0.0,
            },
        ]
    )


def test_expert_state_ranges_and_direction() -> None:
    state, trace = build_expert_state(_synthetic_panel(), irc_weights={"alpha": 1.0, "beta": 1.0, "gamma": 1.0})

    assert len(state) == 3
    assert set(STATE_COLUMNS).issubset(state.columns)
    for column in STATE_COLUMNS + EVIDENCE_COLUMNS + ["irc1", "irc1_no_chla", "yT_no_chla", "sigma_T_no_chla"]:
        assert state[column].between(-1.0, 1.0).all()
    low = state[(state["site_id"] == "A") & (state["year_month"] == "2020-01")].iloc[0]
    high = state[(state["site_id"] == "A") & (state["year_month"] == "2020-02")].iloc[0]
    assert high["yN"] > low["yN"]
    assert high["yF"] < low["yF"]
    assert high["yT"] > low["yT"]
    assert high["irc1"] > low["irc1"]
    assert "irc1_no_chla" in state.columns
    assert "evidence_N" in state.columns
    assert "evidence_T_no_chla" in state.columns
    assert low["delta_yN"] == 0
    assert high["delta_yN"] > 0
    assert "tp_pressure" in trace.columns


def test_build_expert_fuzzy_cli_writes_reviewable_outputs(tmp_path: Path) -> None:
    panel_path = tmp_path / "panel.parquet"
    splits_path = tmp_path / "splits.parquet"
    state_path = tmp_path / "state.parquet"
    metrics_path = tmp_path / "irc1_metrics.csv"
    calibrated_metrics_path = tmp_path / "irc1_calibrated_metrics.csv"
    report_path = tmp_path / "anfis_report.md"
    manifest_path = tmp_path / "fuzzy_manifest.json"
    calibrators_dir = tmp_path / "calibrators"
    rules_path = tmp_path / "rules.csv"
    memberships_path = tmp_path / "memberships.csv"
    trace_path = tmp_path / "trace_examples.csv"
    _synthetic_panel().to_parquet(panel_path, index=False)
    _synthetic_splits().to_parquet(splits_path, index=False)

    result = subprocess.run(
        [
            sys.executable,
            "src/experiments/build_expert_fuzzy.py",
            "--panel",
            str(panel_path),
            "--splits",
            str(splits_path),
            "--state",
            str(state_path),
            "--metrics",
            str(metrics_path),
            "--calibrated-metrics",
            str(calibrated_metrics_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--calibrators-dir",
            str(calibrators_dir),
            "--rules",
            str(rules_path),
            "--memberships",
            str(memberships_path),
            "--trace",
            str(trace_path),
            "--weights-mode",
            "expert",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "wrote" in result.stdout
    for path in [
        state_path,
        metrics_path,
        calibrated_metrics_path,
        report_path,
        manifest_path,
        rules_path,
        memberships_path,
        trace_path,
    ]:
        assert path.exists()
        assert path.stat().st_size > 0
    state = pd.read_parquet(state_path)
    metrics = pd.read_csv(metrics_path)
    calibrated_metrics = pd.read_csv(calibrated_metrics_path)
    assert {"yN", "yF", "yT", "irc1", "irc1_no_chla", "evidence_N"}.issubset(state.columns)
    assert {"metric_scope", "score_name", "rows"}.issubset(metrics.columns)
    assert {"metric_scope", "score_name", "threshold", "brier"}.issubset(calibrated_metrics.columns)
    assert any(calibrators_dir.glob("*.joblib"))


def test_review_expert_fuzzy_cli_writes_signed_outputs(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline_calibrated_metrics.csv"
    raw_metrics_path = tmp_path / "irc1_metrics.csv"
    calibrated_metrics_path = tmp_path / "irc1_calibrated_metrics.csv"
    report_path = tmp_path / "expert_fuzzy_review.md"
    comparison_path = tmp_path / "expert_fuzzy_test_comparison.csv"
    source_summary_path = tmp_path / "expert_fuzzy_source_summary.csv"
    manifest_path = tmp_path / "expert_fuzzy_review_manifest.json"

    pd.DataFrame(
        [
            {
                "selection_task": "bloom",
                "phase": "isotonic_calibrated",
                "model": "logistic_sgd",
                "horizon_months": 1,
                "split": "test",
                "rows": 10,
                "threshold": 0.35,
                "pr_auc": 0.8,
                "roc_auc": 0.9,
                "brier": 0.06,
                "recall": 0.7,
                "macro_f1": 0.75,
            }
        ]
    ).to_csv(baseline_path, index=False)
    pd.DataFrame(
        [
            {
                "metric_scope": "target",
                "score_name": "irc1",
                "source_id": "wqp",
                "horizon_months": 1,
                "split": "test",
                "rows": 10,
                "pr_auc": 0.7,
                "roc_auc": 0.85,
                "brier": 0.12,
                "recall": 0.8,
                "macro_f1": 0.65,
                "mae_score_risk_chla": 0.2,
            }
        ]
    ).to_csv(raw_metrics_path, index=False)
    pd.DataFrame(
        [
            {
                "metric_scope": "target_calibrated",
                "score_name": "irc1",
                "source_id": "all",
                "horizon_months": 1,
                "split": "test",
                "rows": 10,
                "threshold": 0.3,
                "pr_auc": 0.72,
                "roc_auc": 0.86,
                "brier": 0.08,
                "recall": 0.68,
                "macro_f1": 0.7,
            },
            {
                "metric_scope": "target_calibrated",
                "score_name": "irc1",
                "source_id": "wqp",
                "horizon_months": 1,
                "split": "test",
                "rows": 10,
                "threshold": 0.3,
                "pr_auc": 0.72,
                "roc_auc": 0.86,
                "brier": 0.08,
                "recall": 0.68,
                "macro_f1": 0.7,
            },
        ]
    ).to_csv(calibrated_metrics_path, index=False)

    result = subprocess.run(
        [
            sys.executable,
            "src/experiments/review_expert_fuzzy.py",
            "--baseline-metrics",
            str(baseline_path),
            "--irc-metrics",
            str(raw_metrics_path),
            "--calibrated-metrics",
            str(calibrated_metrics_path),
            "--report",
            str(report_path),
            "--comparison",
            str(comparison_path),
            "--source-summary",
            str(source_summary_path),
            "--manifest",
            str(manifest_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "wrote" in result.stdout
    for path in [report_path, comparison_path, source_summary_path, manifest_path]:
        assert path.exists()
        assert path.stat().st_size > 0
    comparison = pd.read_csv(comparison_path)
    assert round(float(comparison.loc[0, "delta_pr_auc_vs_baseline"]), 2) == -0.08
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["row_counts"] == {"comparison_rows": 1, "source_summary_rows": 1}
    assert all(len(record["sha256"]) == 64 for record in manifest["inputs"])
    assert all(len(record["sha256"]) == 64 for record in manifest["outputs"])
