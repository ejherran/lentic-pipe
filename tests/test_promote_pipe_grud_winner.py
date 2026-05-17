from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


SOURCE_FILES = [
    "pipe_grud_metrics.csv",
    "pipe_grud_persistence_metrics.csv",
    "pipe_grud_persistence_comparison.csv",
    "pipe_grud_output_blend_weights.csv",
    "pipe_grud_output_blend_search.csv",
    "pipe_grud_training_curve.csv",
    "pipe_grud_prediction_examples.csv",
    "pipe_grud_report.md",
]


def test_promote_pipe_grud_winner_backs_up_and_writes_signed_manifests(tmp_path: Path) -> None:
    trial_model_dir = tmp_path / "trial_model"
    trial_report_dir = tmp_path / "trial_report"
    trial_model_dir.mkdir()
    trial_report_dir.mkdir()
    model_path = trial_model_dir / "pipe_grud_model.pt"
    model_path.write_text("new model\n", encoding="utf-8")
    (trial_model_dir / "pipe_grud_checkpoint.pt").write_text("new checkpoint\n", encoding="utf-8")
    for filename in SOURCE_FILES:
        (trial_report_dir / filename).write_text(f"{filename}\n", encoding="utf-8")
    trial_manifest_path = trial_report_dir / "pipe_grud_manifest.json"
    trial_manifest_path.write_text(
        json.dumps(
            {
                "model_version": "pipe_grud_v0",
                "status": "completed",
                "config": {"history_length": 12, "hidden_dim": 96, "mse_weight": 1.0},
                "row_counts": {"metric_rows": 30},
                "selection": {"best_epoch": 20, "best_validation_objective": 0.745},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    common_eval_path = tmp_path / "common_eval.csv"
    pd.DataFrame(
        [
            {
                "common_selection_rank": 1,
                "trial_id": "trial_a",
                "history_length": 12,
                "hidden_dim": 96,
                "mse_weight": 1.0,
                "common_validation_objective": 0.745,
                "common_validation_rmse": 0.112,
                "common_validation_mae": 0.060,
                "common_test_rmse": 0.109,
                "common_test_mae": 0.058,
                "model_path": model_path.as_posix(),
                "trial_report_path": (trial_report_dir / "pipe_grud_report.md").as_posix(),
                "manifest_path": trial_manifest_path.as_posix(),
            }
        ]
    ).to_csv(common_eval_path, index=False)
    common_eval_manifest_path = tmp_path / "common_eval_manifest.json"
    common_eval_manifest_path.write_text('{"status": "completed"}\n', encoding="utf-8")

    destination_model = tmp_path / "canonical" / "model.pt"
    destination_checkpoint = tmp_path / "canonical" / "checkpoint.pt"
    destination_metrics = tmp_path / "canonical" / "metrics.csv"
    destination_persistence_metrics = tmp_path / "canonical" / "persistence_metrics.csv"
    destination_comparison = tmp_path / "canonical" / "comparison.csv"
    destination_blend_weights = tmp_path / "canonical" / "blend_weights.csv"
    destination_blend_search = tmp_path / "canonical" / "blend_search.csv"
    destination_training_curve = tmp_path / "canonical" / "training_curve.csv"
    destination_examples = tmp_path / "canonical" / "examples.csv"
    destination_report = tmp_path / "canonical" / "report.md"
    destination_manifest = tmp_path / "canonical" / "manifest.json"
    promotion_report = tmp_path / "promotion_report.md"
    promotion_manifest = tmp_path / "promotion_manifest.json"
    destination_model.parent.mkdir()
    destination_model.write_text("old model\n", encoding="utf-8")
    destination_checkpoint.write_text("old checkpoint\n", encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "src/experiments/promote_pipe_grud_winner.py",
            "--common-eval",
            str(common_eval_path),
            "--common-eval-manifest",
            str(common_eval_manifest_path),
            "--destination-model",
            str(destination_model),
                "--destination-checkpoint",
                str(destination_checkpoint),
                "--destination-metrics",
                str(destination_metrics),
                "--destination-persistence-metrics",
                str(destination_persistence_metrics),
                "--destination-comparison",
                str(destination_comparison),
                "--destination-blend-weights",
                str(destination_blend_weights),
                "--destination-blend-search",
                str(destination_blend_search),
                "--destination-training-curve",
                str(destination_training_curve),
                "--destination-examples",
                str(destination_examples),
                "--destination-report",
                str(destination_report),
                "--destination-manifest",
                str(destination_manifest),
            "--promotion-report",
            str(promotion_report),
            "--promotion-manifest",
            str(promotion_manifest),
            "--model-backup-root",
            str(tmp_path / "model_backups"),
            "--report-backup-root",
            str(tmp_path / "report_backups"),
            "--promotion-id",
            "test_promotion",
        ],
        check=True,
    )

    promoted_manifest = json.loads(destination_manifest.read_text(encoding="utf-8"))
    promotion = json.loads(promotion_manifest.read_text(encoding="utf-8"))

    assert destination_model.read_text(encoding="utf-8") == "new model\n"
    assert destination_checkpoint.read_text(encoding="utf-8") == "new checkpoint\n"
    assert promoted_manifest["status"] == "completed"
    assert promoted_manifest["promotion"]["source_trial_id"] == "trial_a"
    assert promoted_manifest["outputs"][0]["sha256"]
    assert promotion["canonical_manifest"]["sha256"]
    assert len(promotion["backups"]) == 2
    assert "trial_a" in promotion_report.read_text(encoding="utf-8")
    assert destination_metrics.read_text(encoding="utf-8") == "pipe_grud_metrics.csv\n"
