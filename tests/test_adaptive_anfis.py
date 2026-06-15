from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.fuzzy.adaptive_anfis import (
    make_adaptive_anfis,
    max_parameter_delta,
    parameter_snapshot,
    train_supervised_anfis,
)


def test_adaptive_anfis_output_range_and_ordered_centers() -> None:
    torch = pytest.importorskip("torch")
    model = make_adaptive_anfis(input_dim=2, membership_count=3)
    x = torch.tensor([[0.0, 0.2], [0.5, 0.5], [1.0, 0.8]], dtype=torch.float32)

    details = model(x, return_details=True)

    assert details["prediction"].shape == (3,)
    assert details["prediction"].min().item() >= 0.0
    assert details["prediction"].max().item() <= 1.0
    assert details["normalized_firing_strengths"].shape == (3, 9)
    assert torch.allclose(details["normalized_firing_strengths"].sum(dim=1), torch.ones(3), atol=1e-6)
    assert model.centers_are_ordered()
    assert bool((model.positive_widths() > 0).all().item())


def test_adaptive_anfis_unit_center_constraint_keeps_centers_bounded() -> None:
    torch = pytest.importorskip("torch")
    rng = np.random.default_rng(123)
    x = rng.uniform(0.0, 1.0, size=(64, 2)).astype("float32")
    y = np.clip(0.25 + 0.35 * x[:, 0] + 0.25 * x[:, 1], 0.0, 1.0).astype("float32")
    model = make_adaptive_anfis(input_dim=2, membership_count=3, center_constraint="unit")

    train_supervised_anfis(model, x, y, epochs=30, learning_rate=0.04, random_seed=123)

    centers = model.ordered_centers().detach()
    assert model.centers_are_ordered()
    assert model.centers_in_unit_interval()
    assert bool((centers >= 0.0).all().item())
    assert bool((centers <= 1.0).all().item())
    prediction = model(torch.as_tensor(x, dtype=torch.float32))
    assert prediction.min().item() >= 0.0
    assert prediction.max().item() <= 1.0


def test_adaptive_anfis_synthetic_training_updates_parameters() -> None:
    torch = pytest.importorskip("torch")
    rng = np.random.default_rng(1729)
    x = rng.uniform(0.0, 1.0, size=(96, 1)).astype("float32")
    y = np.clip(0.15 + 0.75 * x[:, 0], 0.0, 1.0).astype("float32")
    model = make_adaptive_anfis(input_dim=1, membership_count=3)
    before = parameter_snapshot(model)

    curve = train_supervised_anfis(model, x, y, epochs=80, learning_rate=0.05, random_seed=1729)

    assert curve[0]["loss"] > curve[-1]["loss"]
    assert curve[-1]["loss"] < 0.02
    assert max_parameter_delta(model, before) > 0
    assert model.centers_are_ordered()
    grid = torch.linspace(0.0, 1.0, 25, dtype=torch.float32)[:, None]
    prediction = model(grid).detach().cpu().numpy()
    assert prediction[-1] > prediction[0]
    assert float(np.corrcoef(grid[:, 0].numpy(), prediction)[0, 1]) > 0.95


def test_adaptive_anfis_training_is_deterministic_with_fixed_seed() -> None:
    torch = pytest.importorskip("torch")
    rng = np.random.default_rng(20260615)
    x = rng.uniform(0.0, 1.0, size=(72, 2)).astype("float32")
    y = np.clip(0.4 * x[:, 0] + 0.6 * x[:, 1], 0.0, 1.0).astype("float32")
    left = make_adaptive_anfis(input_dim=2, membership_count=3)
    right = make_adaptive_anfis(input_dim=2, membership_count=3)

    left_curve = train_supervised_anfis(left, x, y, epochs=50, learning_rate=0.04, random_seed=99)
    right_curve = train_supervised_anfis(right, x, y, epochs=50, learning_rate=0.04, random_seed=99)

    x_tensor = torch.as_tensor(x, dtype=torch.float32)
    assert left_curve == right_curve
    assert torch.allclose(left(x_tensor), right(x_tensor), atol=1e-7)


def test_adaptive_anfis_synthetic_smoke_cli_writes_report_and_manifest(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    report_path = tmp_path / "adaptive_anfis_synthetic_smoke_report.md"
    manifest_path = tmp_path / "adaptive_anfis_synthetic_smoke_manifest.json"
    metrics_path = tmp_path / "adaptive_anfis_synthetic_smoke_metrics.csv"

    subprocess.run(
        [
            sys.executable,
            "src/experiments/run_adaptive_anfis_synthetic_smoke.py",
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--metrics",
            str(metrics_path),
            "--rows",
            "64",
            "--epochs",
            "40",
            "--random-seed",
            "1729",
        ],
        check=True,
    )

    metrics = pd.read_csv(metrics_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")

    assert set(metrics["module"]) == {"ANFIS-N", "ANFIS-F", "ANFIS-T"}
    assert set(metrics["status"]) == {"passed"}
    assert metrics["finite_loss"].all()
    assert metrics["output_in_range"].all()
    assert metrics["centers_ordered"].all()
    assert (metrics["max_parameter_delta"] > 0).all()
    assert manifest["status"] == "completed"
    assert manifest["config"]["rows"] == 64
    assert manifest["script"]["sha256"]
    assert "Status: `completed`" in report
