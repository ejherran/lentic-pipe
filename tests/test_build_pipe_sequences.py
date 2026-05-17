from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd

from src.experiments.build_pipe_sequences import (
    INPUT_COLUMNS,
    PIPE_STATE_COLUMNS,
    TARGET_COLUMNS,
    build_sequence_candidates,
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
    frame["irc1"] = frame["base"]
    frame["irc1_no_chla"] = frame["base"] - 0.01
    frame["evidence_N"] = 1.0
    frame["evidence_F"] = 0.8
    frame["evidence_T"] = 0.6
    frame["missing_N"] = 0.0
    frame["missing_F"] = 0.2
    frame["missing_T"] = 0.4
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
        ],
        check=True,
    )

    sequences = pd.read_parquet(sequences_path)
    summary = pd.read_csv(summary_path)
    discarded = pd.read_csv(discarded_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert len(sequences) == 2
    assert len(summary) == 2
    assert not discarded.empty
    assert manifest["row_counts"]["kept_sequence_rows"] == 2
    assert manifest["row_counts"]["discarded_candidate_rows"] == 5
    assert manifest["outputs"][0]["sha256"]
    assert "Input dimensionality" in report_path.read_text(encoding="utf-8")
