from __future__ import annotations

from itertools import product
from random import random, seed
from typing import cast

import pytest

from src.mifal.ed_t2 import (
    Interval,
    MIFALEDT2,
    MIFALConfig,
    MembershipFunction,
    Observation,
    clip01,
    conservative_risk,
    eco_and,
    interval_coverage,
    interval_sugeno_zero_order,
    winkler_interval_score,
)


def assert_interval(value: object) -> None:
    assert isinstance(value, tuple) and len(value) == 2
    interval = cast(Interval, value)
    assert 0.0 <= interval[0] <= interval[1] <= 1.0


def test_smoke_and_bounds() -> None:
    model = MIFALEDT2()
    data = {
        "Tw": Observation(28.0, source_quality=0.90, sigma=0.6, age_days=1.0),
        "TP": Observation(85.0, source_quality=0.80, cv=0.20, age_days=12.0),
        "TN": Observation(1.2, source_quality=0.70, cv=0.25, age_days=12.0),
        "Secchi": Observation(0.75, source_quality=0.80, sigma=0.15, age_days=5.0),
        "Wind": Observation(1.4, source_quality=0.95, sigma=0.3, age_days=0.2),
        "Residence": Observation(35.0, source_quality=0.60, cv=0.30, age_days=10.0),
        "Chl_prev": Observation(24.0, source_quality=0.80, cv=0.15, age_days=4.0),
        "Visual": Observation(0.7, source_quality=0.50, sigma=0.2, age_days=1.0),
    }

    result = model.step(data, dt_days=7.0)

    assert_interval(result["risk_interval"])
    assert 0.0 <= cast(float, result["risk_conservative"]) <= 1.0
    assert 0.0 <= cast(float, result["confidence"]) <= 1.0
    assert result["alert_class"] in {"low", "watch", "high", "critical"}
    for interval in cast(dict[str, Interval], result["indices"]).values():
        assert_interval(interval)


def test_single_precise_observation_can_have_high_reliability() -> None:
    fv = MIFALEDT2().fuse_variable(
        "Tw",
        Observation(28.0, sigma=0.01, source_quality=1.0, source_fit=1.0, age_days=0.0),
    )

    assert fv.available
    assert fv.reliability > 0.99
    assert fv.sigma < 0.02


def test_tp_monotonicity_under_high_quality_context() -> None:
    base = {
        "Tw": Observation(28.0, sigma=0.2, source_quality=1.0),
        "TN": Observation(1.0, sigma=0.05, source_quality=1.0),
        "Secchi": Observation(1.0, sigma=0.05, source_quality=1.0),
        "Wind": Observation(1.0, sigma=0.1, source_quality=1.0),
        "Residence": Observation(30.0, sigma=2.0, source_quality=1.0),
        "Chl_prev": Observation(10.0, sigma=1.0, source_quality=1.0),
    }
    risks = []
    for tp in [5, 20, 40, 60, 80, 100, 150]:
        data = dict(base)
        data["TP"] = Observation(float(tp), sigma=2.0, source_quality=1.0)
        risks.append(cast(float, MIFALEDT2().step(data, update_state=False, assimilate=False)["risk_conservative"]))

    assert all(after + 1e-9 >= before for before, after in zip(risks, risks[1:]))


def test_sugeno_zero_order_matches_bruteforce_vertices() -> None:
    seed(7)
    for n in range(2, 6):
        for _ in range(100):
            weights = []
            for _ in range(n):
                a, b = random(), random()
                weights.append((min(a, b), max(a, b)))
            consequents = [random() for _ in range(n)]
            km = interval_sugeno_zero_order(weights, consequents)
            brute_min, brute_max = 10.0, -10.0
            for bits in product([0, 1], repeat=n):
                ws = [weights[index][bits[index]] for index in range(n)]
                denominator = sum(ws)
                value = 0.0 if denominator <= 1e-12 else sum(weight * consequent for weight, consequent in zip(ws, consequents, strict=True)) / denominator
                brute_min = min(brute_min, value)
                brute_max = max(brute_max, value)
            assert abs(km[0] - brute_min) < 1e-8
            assert abs(km[1] - brute_max) < 1e-8


def test_assimilation_before_forecast_at_zero_horizon() -> None:
    model = MIFALEDT2()
    before = model.current_state()

    result = model.step({"Chl": Observation(80.0, sigma=2.0, source_quality=1.0)}, dt_days=0.0, update_state=False)

    after_analysis = cast(Interval, result["state_after_observation_assimilation"])
    assert after_analysis[0] >= before[0]
    assert cast(float, result["risk_conservative"]) > conservative_risk(before)


def test_step_does_not_mutate_state_by_default_and_can_update_explicitly() -> None:
    model = MIFALEDT2()
    initial = model.current_state()
    data = {
        "Tw": Observation(28.0, sigma=0.2, source_quality=1.0),
        "TP": Observation(90.0, sigma=2.0, source_quality=1.0),
        "Secchi": Observation(1.0, sigma=0.05, source_quality=1.0),
        "Wind": Observation(1.0, sigma=0.1, source_quality=1.0),
    }

    model.step(data, dt_days=7.0)
    assert model.current_state() == initial

    model.step(data, dt_days=7.0, update_state=True, state_update_target="forecast")
    assert model.current_state() != initial

    model.reset()
    expected_analysis = cast(
        Interval,
        model.step({"Chl": Observation(60.0, sigma=2.0, source_quality=1.0)}, dt_days=7.0)["state_after_observation_assimilation"],
    )
    assert model.current_state() == initial

    model.step({"Chl": Observation(60.0, sigma=2.0, source_quality=1.0)}, dt_days=7.0, update_state=True, state_update_target="analysis")
    assert model.current_state() == expected_analysis


def test_defensive_configuration_and_inputs() -> None:
    cfg = MIFALConfig()
    cfg.membership["TP"]["high"] = MembershipFunction("ramp_up", (80.0, 55.0))
    with pytest.raises(ValueError, match="Invalid membership"):
        MIFALEDT2(cfg)

    model = MIFALEDT2()
    with pytest.raises(KeyError):
        model.fuse_all({"UnknownX": 1.0})
    with pytest.raises(ValueError):
        model.fuse_variable("TP", Observation(-1.0))

    relaxed = MIFALEDT2(config=MIFALConfig(strict_physical_bounds=False))
    assert relaxed.fuse_variable("TP", Observation(-1.0)).value == 0.0

    with pytest.raises(ValueError):
        eco_and([(0.1, 0.2), (0.3, 0.4)], reliabilities=[1.0])


def test_interval_metrics_and_alert_helpers() -> None:
    assert interval_coverage([0.2, 0.8], [(0.0, 0.3), (0.7, 0.9)]) == 1.0
    assert winkler_interval_score(0.5, (0.4, 0.6), alpha=0.1) == pytest.approx(0.2)
    assert winkler_interval_score(0.8, (0.4, 0.6), alpha=0.1) > 0.2
    assert MIFALEDT2.alert_class(0.0) == "low"
    assert MIFALEDT2.alert_class(0.3) == "watch"
    assert MIFALEDT2.alert_class(0.6) == "high"
    assert MIFALEDT2.alert_class(0.9) == "critical"
    assert clip01(-1) == 0.0 and clip01(2) == 1.0
