from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, TARGET_COLUMNS
from src.experiments.sweep_pipe_grud import build_trial_configs


def _sequence_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    segments = [
        ("A", "s1", "train", "2018", 5, 0.10),
        ("A", "s1", "validation", "2019", 4, 0.30),
        ("B", "s1", "test", "2022", 4, 0.50),
    ]
    for source_id, site_id, split, year, count, base in segments:
        for step in range(count):
            row: dict[str, object] = {
                "source_id": source_id,
                "site_id": site_id,
                "sequence_step": step,
                "origin_year_month": f"{year}-{step + 1:02d}",
                "target_year_month": f"{year}-{step + 2:02d}",
                "split": split,
            }
            for column_index, column in enumerate(INPUT_COLUMNS):
                row[column] = base + step / 100.0 + column_index / 1000.0
            for column_index, column in enumerate(TARGET_COLUMNS):
                row[column] = base + (step + 1) / 100.0 + column_index / 1000.0
            rows.append(row)
    return pd.DataFrame(rows)


def _args() -> Namespace:
    return Namespace(
        history_lengths="3,6",
        hidden_dims="64",
        mse_weights="0.5",
        learning_rates="0.001",
        random_seed=1729,
        vary_seed=False,
        limit_trials=None,
    )


def test_build_trial_configs_preserves_grid_order_and_seed() -> None:
    configs = build_trial_configs(_args())

    assert [config.history_length for config in configs] == [3, 6]
    assert {config.random_seed for config in configs} == {1729}
    assert configs[0].trial_id == "h03_hd064_mse0p5_lr0p001_seed1729"


def test_sweep_pipe_grud_cli_writes_signed_summary(tmp_path: Path) -> None:
    pytest.importorskip("torch")

    sequences_path = tmp_path / "sequences.parquet"
    sequence_manifest_path = tmp_path / "sequence_manifest.json"
    summary_path = tmp_path / "sweep_summary.csv"
    report_path = tmp_path / "sweep_report.md"
    manifest_path = tmp_path / "sweep_manifest.json"
    trial_report_root = tmp_path / "trial_reports"
    trial_model_root = tmp_path / "trial_models"

    _sequence_rows().to_parquet(sequences_path, index=False)
    sequence_manifest_path.write_text('{"status": "test"}\n', encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "src/experiments/sweep_pipe_grud.py",
            "--sequences",
            str(sequences_path),
            "--sequence-manifest",
            str(sequence_manifest_path),
            "--summary",
            str(summary_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--trial-report-root",
            str(trial_report_root),
            "--trial-model-root",
            str(trial_model_root),
            "--sweep-id",
            "test_sweep",
            "--history-lengths",
            "2",
            "--hidden-dims",
            "8",
            "--mse-weights",
            "0.5",
            "--epochs",
            "1",
            "--batch-size",
            "2",
            "--max-train-windows",
            "10",
            "--max-eval-windows",
            "10",
            "--max-examples",
            "2",
            "--progress-every-batches",
            "0",
        ],
        check=True,
    )

    summary = pd.read_csv(summary_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")

    assert len(summary) == 1
    assert summary.loc[0, "status"] == "completed"
    assert summary.loc[0, "selection_rank"] == 1
    assert summary.loc[0, "history_length"] == 2
    assert summary.loc[0, "hidden_dim"] == 8
    assert Path(summary.loc[0, "manifest_path"]).exists()
    assert manifest["status"] == "completed"
    assert manifest["row_counts"]["planned_trials"] == 1
    assert manifest["row_counts"]["completed_trials"] == 1
    assert manifest["outputs"][0]["sha256"]
    assert manifest["trial_manifests"][0]["sha256"]
    assert "Ranking is selected on validation only" in report
