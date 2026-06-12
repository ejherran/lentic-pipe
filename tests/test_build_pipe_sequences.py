from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest

from src.experiments.build_pipe_sequences import (
    INPUT_COLUMNS,
    PIPE_STATE_COLUMNS,
    TARGET_COLUMNS,
    build_sequence_candidates,
    filter_state_sources,
    filter_leakage_safe_sequences,
    summarize_discarded,
    summarize_sequences,
)


def _state_frame() -> pd.DataFrame:
    rows = [
        ("A", "s1", "2018-11", 0.10),
        ("A", "s1", "2018-12", 0.20),
        ("A", "s1", "2019-01", 0.30),
        ("A", "s2", "2020-01", 0.40),
        ("A", "s2", "2020-03", 0.50),
        ("B", "s1", "2022-01", 0.60),
        ("B", "s1", "2022-02", 0.70),
    ]
    frame = pd.DataFrame(rows, columns=["source_id", "site_id", "year_month", "base"])
    for offset, column in enumerate(PIPE_STATE_COLUMNS):
        frame[column] = frame["base"] + offset / 100.0
    frame["yT_no_chla"] = frame["yT"] - 0.25
    frame["sigma_T_no_chla"] = frame["sigma_T"] + 0.25
    frame["delta_yT_no_chla"] = frame["delta_yT"] - 0.25
    frame["irc1"] = frame["base"]
    frame["irc1_no_chla"] = frame["base"] - 0.01
    frame["evidence_N"] = 1.0
    frame["evidence_F"] = 0.8
    frame["evidence_T"] = 0.6
    frame["evidence_T_no_chla"] = 0.4
    frame["missing_N"] = 0.0
    frame["missing_F"] = 0.2
    frame["missing_T"] = 0.4
    frame["missing_T_no_chla"] = 0.6
    return frame.drop(columns=["base"])


def _args() -> Namespace:
    return Namespace(
        max_gap_months=1,
        train_end="2018-12",
        validation_start="2019-01",
        validation_end="2021-12",
        test_start="2022-01",
        test_end=None,
    )


def test_build_sequences_keeps_source_scoped_consecutive_transitions() -> None:
    candidates = build_sequence_candidates(_state_frame())
    sequences, discarded = filter_leakage_safe_sequences(candidates, _args())

    kept_keys = sequences[["source_id", "site_id", "origin_year_month", "target_year_month", "split"]].to_dict(
        orient="records"
    )

    assert kept_keys == [
        {
            "source_id": "A",
            "site_id": "s1",
            "origin_year_month": "2018-11",
            "target_year_month": "2018-12",
            "split": "train",
        },
        {
            "source_id": "B",
            "site_id": "s1",
            "origin_year_month": "2022-01",
            "target_year_month": "2022-02",
            "split": "test",
        }
    ]
    assert sequences["target_gap_months"].tolist() == [1, 1]
    assert sequences[INPUT_COLUMNS + TARGET_COLUMNS].notna().all().all()
    assert {"crosses_split_boundary", "gap_too_large", "no_next_state"}.issubset(set(discarded["split_reason"]))


def test_sequence_summary_and_discarded_summary_are_source_scoped() -> None:
    candidates = build_sequence_candidates(_state_frame())
    sequences, discarded = filter_leakage_safe_sequences(candidates, _args())

    summary = summarize_sequences(sequences)
    discarded_summary = summarize_discarded(discarded)

    assert summary[["source_id", "split", "rows", "sites"]].to_dict(orient="records") == [
        {"source_id": "A", "split": "train", "rows": 1, "sites": 1},
        {"source_id": "B", "split": "test", "rows": 1, "sites": 1}
    ]
    assert discarded_summary.groupby("source_id")["rows"].sum().to_dict() == {"A": 4, "B": 1}


def test_no_current_chla_surface_replaces_current_inputs_only() -> None:
    candidates = build_sequence_candidates(_state_frame(), input_surface="no_current_chla")
    sequences, _ = filter_leakage_safe_sequences(candidates, _args())

    first = sequences.iloc[0]

    assert first["x_yT"] == pytest.approx(first["target_yT"] - 0.35)
    assert first["x_sigma_T"] == pytest.approx(first["target_sigma_T"] + 0.15)
    assert first["x_delta_yT"] == pytest.approx(first["target_delta_yT"] - 0.35)
    assert first["target_yT"] != first["x_yT"]
    assert first["target_sigma_T"] != first["x_sigma_T"]
    assert first["target_delta_yT"] != first["x_delta_yT"]


def test_source_filter_keeps_requested_sources_only() -> None:
    state = filter_state_sources(_state_frame(), ["B"])
    candidates = build_sequence_candidates(state, input_surface="no_current_chla")
    sequences, discarded = filter_leakage_safe_sequences(candidates, _args())

    assert set(state["source_id"]) == {"B"}
    assert sequences["source_id"].tolist() == ["B"]
    assert discarded["source_id"].tolist() == ["B"]


def test_build_pipe_sequences_cli_writes_signed_outputs(tmp_path: Path) -> None:
    state_path = tmp_path / "state.parquet"
    sequences_path = tmp_path / "sequences.parquet"
    summary_path = tmp_path / "summary.csv"
    discarded_path = tmp_path / "discarded.csv"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"
    _state_frame().to_parquet(state_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/build_pipe_sequences.py",
            "--state",
            str(state_path),
            "--sequences",
            str(sequences_path),
            "--summary",
            str(summary_path),
            "--discarded",
            str(discarded_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--input-surface",
            "no_current_chla",
            "--source-ids",
            "B",
        ],
        check=True,
    )

    sequences = pd.read_parquet(sequences_path)
    summary = pd.read_csv(summary_path)
    discarded = pd.read_csv(discarded_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert len(sequences) == 1
    assert len(summary) == 1
    assert not discarded.empty
    assert manifest["row_counts"]["kept_sequence_rows"] == 1
    assert manifest["row_counts"]["discarded_candidate_rows"] == 1
    assert manifest["config"]["input_surface"] == "no_current_chla"
    assert manifest["config"]["source_ids"] == ["B"]
    assert manifest["config"]["input_state_mapping"]["yT"] == "yT_no_chla"
    assert manifest["outputs"][0]["sha256"]
    assert manifest["script"]["path"] == "src/experiments/build_pipe_sequences.py"
    assert "No-current-Chl-a mode" in report_path.read_text(encoding="utf-8")
    assert "Input dimensionality" in report_path.read_text(encoding="utf-8")
