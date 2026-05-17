from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, TARGET_COLUMNS


def _sequence_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    segments = [
        ("A", "s1", "train", "2018", 6, 0.10),
        ("A", "s1", "validation", "2019", 5, 0.30),
        ("B", "s1", "test", "2022", 5, 0.50),
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


def test_common_eval_cli_compares_completed_sweep_trial(tmp_path: Path) -> None:
    pytest.importorskip("torch")

    sequences_path = tmp_path / "sequences.parquet"
    sequence_manifest_path = tmp_path / "sequence_manifest.json"
    sweep_summary_path = tmp_path / "sweep_summary.csv"
    sweep_report_path = tmp_path / "sweep_report.md"
    sweep_manifest_path = tmp_path / "sweep_manifest.json"
    common_output_path = tmp_path / "common_eval.csv"
    common_report_path = tmp_path / "common_eval.md"
    common_manifest_path = tmp_path / "common_eval_manifest.json"
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
            str(sweep_summary_path),
            "--report",
            str(sweep_report_path),
            "--manifest",
            str(sweep_manifest_path),
            "--trial-report-root",
            str(trial_report_root),
            "--trial-model-root",
            str(trial_model_root),
            "--sweep-id",
            "common_eval_test_sweep",
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

    subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_pipe_grud_sweep_common.py",
            "--sequences",
            str(sequences_path),
            "--sweep-summary",
            str(sweep_summary_path),
            "--output",
            str(common_output_path),
            "--report",
            str(common_report_path),
            "--manifest",
            str(common_manifest_path),
            "--batch-size",
            "2",
        ],
        check=True,
    )

    common = pd.read_csv(common_output_path)
    manifest = json.loads(common_manifest_path.read_text(encoding="utf-8"))
    report = common_report_path.read_text(encoding="utf-8")

    assert len(common) == 1
    assert common.loc[0, "common_selection_rank"] == 1
    assert common.loc[0, "common_history_length"] == 2
    assert common.loc[0, "common_validation_rows"] > 0
    assert manifest["status"] == "completed"
    assert manifest["row_counts"]["evaluated_trials"] == 1
    assert manifest["outputs"][0]["sha256"]
    assert "same end-window population" in report
