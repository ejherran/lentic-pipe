from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.experiments.audit_no_chla_operational_surface import (
    add_evidence_flags,
    attach_origin_predictors,
    build_feature_coverage,
    build_sequence_coverage,
    summarize_operational_coverage,
)


def _panel() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_id": ["A", "A", "B", "B", "C"],
            "site_id": ["s1", "s2", "s1", "s2", "s1"],
            "site_id_source": ["s1", "s2", "s1", "s2", "s1"],
            "site_name": ["one", "two", "three", "four", "five"],
            "year_month": ["2020-01", "2020-01", "2020-01", "2020-01", "2021-01"],
            "mean_TP_ugL": [20.0, 15.0, None, None, None],
            "mean_TN_ugL": [800.0, None, None, None, 900.0],
            "TN_TP_ratio": [40.0, None, None, None, None],
            "log_TP": [3.0, 2.7, None, None, None],
            "log_TN": [6.7, None, None, None, 6.8],
            "mean_temperature_C": [24.0, None, 23.0, None, 24.0],
            "mean_secchi_depth_m": [1.5, None, None, None, None],
            "mean_turbidity_NTU": [None, None, None, None, None],
            "mean_DO_mgL": [None, None, 8.0, None, None],
            "mean_pH": [None, None, None, None, 7.8],
            "mean_chlorophyll_a_ugL": [35.0, None, None, None, None],
            "risk_chla": [1.0, None, None, None, None],
        }
    )


def _splits() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_id": ["A", "A", "B", "B", "C"],
            "site_id": ["s1", "s2", "s1", "s2", "s1"],
            "site_id_source": ["s1", "s2", "s1", "s2", "s1"],
            "site_name": ["one", "two", "three", "four", "five"],
            "origin_year_month": ["2020-01", "2020-01", "2020-01", "2020-01", "2021-01"],
            "horizon_months": [1, 1, 1, 1, 2],
            "target_year_month": ["2020-02", "2020-02", "2020-02", "2020-02", "2021-03"],
            "bloom_h": [True, False, False, True, True],
            "target_risk_chla_h": [1.0, 0.2, 0.1, 0.9, 0.8],
            "split": ["test", "test", "test", "test", "validation"],
        }
    )


def _sequences() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_id": ["A", "A", "B"],
            "site_id": ["s1", "s2", "s1"],
            "origin_year_month": ["2020-01", "2020-01", "2020-01"],
            "target_year_month": ["2020-02", "2020-02", "2020-02"],
            "split": ["test", "test", "test"],
            "x_yN": [0.8, 0.5, 0.5],
            "x_yF": [0.4, 0.4, 0.6],
            "x_yT": [0.7, 0.5, 0.7],
            "x_irc1": [0.9, 0.6, 0.4],
            "x_irc1_no_chla": [0.7, 0.6, 0.4],
            "x_evidence_N": [1.0, 0.2, 0.0],
            "x_evidence_F": [0.5, 0.5, 1.0],
            "x_evidence_T_no_chla": [1.0, 0.0, 0.8],
            "x_missing_N": [0.0, 0.8, 1.0],
            "x_missing_F": [0.5, 0.5, 0.0],
            "x_missing_T_no_chla": [0.0, 1.0, 0.2],
        }
    )


def test_no_chla_audit_evidence_bands_are_explicit() -> None:
    frame = add_evidence_flags(attach_origin_predictors(_splits(), _panel()))

    bands = dict(zip(frame["site_id"], frame["operational_evidence_band"], strict=False))

    assert bands["s1"] == "high"
    assert bands["s2"] == "season_only"
    assert frame["has_current_chla_forbidden"].sum() == 1
    assert frame["precursor_ready"].sum() == 2

    summary = summarize_operational_coverage(frame, ["split", "horizon_months"])
    test_h1 = summary[(summary["split"] == "test") & (summary["horizon_months"] == 1)].iloc[0]

    assert test_h1["rows"] == 4
    assert test_h1["any_nutrient_rows"] == 2
    assert test_h1["high"] == 1
    assert test_h1["season_only"] == 1


def test_no_chla_audit_feature_and_sequence_coverage() -> None:
    frame = add_evidence_flags(attach_origin_predictors(_splits(), _panel()))
    feature_coverage = build_feature_coverage(frame)
    sequence_coverage = build_sequence_coverage(_sequences())

    tp_test = feature_coverage[
        (feature_coverage["source_id"] == "A")
        & (feature_coverage["split"] == "test")
        & (feature_coverage["feature_name"] == "TP_ugL")
    ].iloc[0]

    assert tp_test["present_rows"] == 2
    assert tp_test["coverage_rate"] == 1.0
    assert sequence_coverage["changed_irc_chla_delta_rate"].iloc[0] == 0.5
    assert "low_nutrient_evidence_rate" in sequence_coverage.columns


def test_no_chla_audit_cli_writes_outputs(tmp_path: Path) -> None:
    panel_path = tmp_path / "panel.parquet"
    splits_path = tmp_path / "splits.parquet"
    sequences_path = tmp_path / "sequences.parquet"
    summary_path = tmp_path / "summary.csv"
    by_source_path = tmp_path / "by_source.csv"
    feature_coverage_path = tmp_path / "feature_coverage.csv"
    sequence_coverage_path = tmp_path / "sequence_coverage.csv"
    low_evidence_examples_path = tmp_path / "examples.csv"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"

    _panel().to_parquet(panel_path, index=False)
    _splits().to_parquet(splits_path, index=False)
    _sequences().to_parquet(sequences_path, index=False)

    result = subprocess.run(
        [
            sys.executable,
            "src/experiments/audit_no_chla_operational_surface.py",
            "--panel",
            str(panel_path),
            "--splits",
            str(splits_path),
            "--sequences",
            str(sequences_path),
            "--summary",
            str(summary_path),
            "--by-source",
            str(by_source_path),
            "--feature-coverage",
            str(feature_coverage_path),
            "--sequence-coverage",
            str(sequence_coverage_path),
            "--low-evidence-examples",
            str(low_evidence_examples_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--examples-per-group",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "built audit frame" in result.stdout
    for path in [
        summary_path,
        by_source_path,
        feature_coverage_path,
        sequence_coverage_path,
        low_evidence_examples_path,
        report_path,
        manifest_path,
    ]:
        assert path.exists()
        assert path.stat().st_size > 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["audit_version"] == "no_chla_operational_surface_audit_v0"
    assert manifest["row_counts"]["audited_rows"] == 5
    assert all(len(record["sha256"]) == 64 for record in manifest["outputs"])
