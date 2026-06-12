from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, TARGET_COLUMNS
from src.experiments.train_pipe_grud import eligible_window_indices, make_model, prepare_window_frame


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


def test_window_indices_stay_inside_source_site_split_runs() -> None:
    frame = prepare_window_frame(_sequence_rows())
    train_indices = eligible_window_indices(frame, "train", history_length=3)

    assert len(train_indices) == 3
    for index in train_indices:
        window = frame.loc[index - 2 : index]
        assert window["source_id"].nunique() == 1
        assert window["site_id"].nunique() == 1
        assert window["split"].nunique() == 1


def test_residual_model_starts_from_last_state() -> None:
    torch = pytest.importorskip("torch")
    model = make_model(
        input_dim=len(INPUT_COLUMNS),
        target_dim=len(TARGET_COLUMNS),
        hidden_dim=4,
        num_layers=1,
        dropout=0.0,
        residual_mode="add_last",
    )
    for parameter in model.parameters():
        torch.nn.init.zeros_(parameter)
    x = torch.zeros((2, 3, len(INPUT_COLUMNS)), dtype=torch.float32)
    x[:, -1, : len(TARGET_COLUMNS)] = torch.arange(len(TARGET_COLUMNS), dtype=torch.float32)

    mu, _ = model(x)

    assert torch.equal(mu[0], x[0, -1, : len(TARGET_COLUMNS)])


def test_train_pipe_grud_cli_writes_signed_outputs(tmp_path: Path) -> None:
    pytest.importorskip("torch")

    sequences_path = tmp_path / "sequences.parquet"
    sequence_manifest_path = tmp_path / "sequence_manifest.json"
    model_path = tmp_path / "model.pt"
    checkpoint_path = tmp_path / "checkpoint.pt"
    metrics_path = tmp_path / "metrics.csv"
    persistence_metrics_path = tmp_path / "persistence_metrics.csv"
    comparison_path = tmp_path / "comparison.csv"
    blend_weights_path = tmp_path / "blend_weights.csv"
    blend_search_path = tmp_path / "blend_search.csv"
    training_curve_path = tmp_path / "training_curve.csv"
    examples_path = tmp_path / "examples.csv"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"

    _sequence_rows().to_parquet(sequences_path, index=False)
    sequence_manifest_path.write_text('{"status": "test"}\n', encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "src/experiments/train_pipe_grud.py",
            "--sequences",
            str(sequences_path),
            "--sequence-manifest",
            str(sequence_manifest_path),
            "--model",
            str(model_path),
            "--checkpoint",
            str(checkpoint_path),
            "--metrics",
            str(metrics_path),
            "--persistence-metrics",
            str(persistence_metrics_path),
            "--comparison",
            str(comparison_path),
            "--blend-weights",
            str(blend_weights_path),
            "--blend-search",
            str(blend_search_path),
            "--training-curve",
            str(training_curve_path),
            "--examples",
            str(examples_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--epochs",
            "2",
            "--history-length",
            "2",
            "--hidden-dim",
            "8",
            "--batch-size",
            "2",
            "--max-train-windows",
            "10",
            "--max-eval-windows",
            "10",
            "--progress-every-batches",
            "0",
        ],
        check=True,
    )

    metrics = pd.read_csv(metrics_path)
    persistence_metrics = pd.read_csv(persistence_metrics_path)
    comparison = pd.read_csv(comparison_path)
    blend_weights = pd.read_csv(blend_weights_path)
    blend_search = pd.read_csv(blend_search_path)
    training_curve = pd.read_csv(training_curve_path)
    examples = pd.read_csv(examples_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert model_path.exists()
    assert checkpoint_path.exists()
    assert len(metrics) == 30
    assert set(metrics["split"]) == {"train", "validation", "test"}
    assert len(persistence_metrics) == 30
    assert len(comparison) == 30
    assert len(blend_weights) == len(TARGET_COLUMNS)
    assert len(blend_search) == len(TARGET_COLUMNS) * 9
    assert blend_weights["blend_weight"].between(0, 1).all()
    assert set(blend_weights["selection_metric"]) == {"balanced"}
    assert "rmse_relative_improvement" in comparison.columns
    assert len(training_curve) == 2
    assert not examples.empty
    assert manifest["status"] == "completed"
    assert manifest["config"]["residual_mode"] == "add_last"
    assert manifest["config"]["mse_weight"] == 0.5
    assert manifest["config"]["checkpoint_selection_metric"] == "balanced"
    assert manifest["config"]["checkpoint_selection_uses_output_blend"] is True
    assert manifest["row_counts"]["metric_rows"] == 30
    assert manifest["row_counts"]["blend_weight_rows"] == len(TARGET_COLUMNS)
    assert manifest["row_counts"]["blend_search_rows"] == len(TARGET_COLUMNS) * 9
    assert manifest["config"]["blend_selection_metric"] == "balanced"
    assert manifest["selection"]["best_epoch"] in [1, 2]
    assert manifest["selection"]["best_validation_objective"] is not None
    assert manifest["row_counts"]["persistence_metric_rows"] == 30
    assert manifest["row_counts"]["comparison_rows"] == 30
    assert manifest["outputs"][0]["sha256"]
    assert manifest["script"]["path"] == "src/experiments/train_pipe_grud.py"
    assert "Status: `completed`" in report_path.read_text(encoding="utf-8")
    assert "Output Blend Weights" in report_path.read_text(encoding="utf-8")
    assert "Persistence Comparison" in report_path.read_text(encoding="utf-8")
