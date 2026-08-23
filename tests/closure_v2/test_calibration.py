from __future__ import annotations

import numpy as np
import pytest

from src.experiments.closure_v2 import calibrate_temporal


def test_runtime_rejects_raw_score_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = calibrate_temporal.load_yaml_mapping(calibrate_temporal.CALIBRATION_CONFIG)
    runtime["raw_bloom_score"]["gamma_yT"] = 1.9
    monkeypatch.setattr(calibrate_temporal, "load_yaml_mapping", lambda _: runtime)
    with pytest.raises(calibrate_temporal.CalibrationError, match="Raw bloom-score"):
        calibrate_temporal.validate_runtime()


def test_irc_probability_is_bounded_and_uses_locked_weights() -> None:
    state = np.asarray([[1.0, 0.0, 1.0], [0.0, 1.0, 0.0], [2.0, -1.0, 2.0]])
    probability = calibrate_temporal._irc_probability(state)
    assert np.array_equal(probability, np.asarray([1.0, 0.0, 1.0]))


def test_higher_conformal_quantile() -> None:
    values = np.asarray([1.0, 2.0, 3.0, 4.0])
    assert calibrate_temporal._higher_quantile(values, 0.8) == 4.0


def test_recursive_prediction_shapes_are_h1_h3() -> None:
    torch = calibrate_temporal.torch

    class Persistence(torch.nn.Module):
        def forward(self, x):
            return x[:, -1, :9], torch.zeros_like(x[:, -1, :9])

    selected = __import__("pandas").DataFrame(
        {"origin_year_month": ["2021-01", "2021-02"]}
    )
    for column in calibrate_temporal.INPUT_COLUMNS:
        selected[column] = [np.zeros(12, dtype=np.float32), np.ones(12, dtype=np.float32)]
    outputs = calibrate_temporal.recursive_predictions(
        selected, Persistence(), torch.ones(9, dtype=torch.float32)
    )
    assert set(outputs) == {1, 2, 3}
    assert all(mu.shape == (2, 9) and sigma.shape == (2, 9) for mu, sigma in outputs.values())


def test_post_2021_target_boundary_is_rejected() -> None:
    assert calibrate_temporal._month_add("2021-09", 3) == "2021-12"
    assert calibrate_temporal._month_add("2021-10", 3) == "2022-01"
