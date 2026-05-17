from __future__ import annotations

import numpy as np
import pandas as pd

from src.experiments.refine_expert_fuzzy import (
    build_deterministic_candidates,
    build_selection,
    evaluate_candidate_columns,
    source_specific_selector,
)


def test_deterministic_candidates_blend_and_gate() -> None:
    frame = pd.DataFrame(
        {
            "baseline_calibrated": [0.2, 0.8],
            "irc1_calibrated": [0.8, 0.2],
            "irc1_no_chla_calibrated": [0.6, 0.4],
            "full_evidence": [0.5, 1.0],
            "evidence_T": [0.25, 0.75],
            "exogenous_evidence": [0.75, 0.25],
        }
    )

    candidates = build_deterministic_candidates(frame, [0.5])

    assert set(candidates) == {
        "baseline_calibrated",
        "irc1_calibrated",
        "irc1_no_chla_calibrated",
        "blend_irc1_w0p5",
        "gate_full_irc1_w0p5",
        "gate_trophic_irc1_w0p5",
        "gate_exogenous_no_chla_w0p5",
    }
    assert np.allclose(candidates["blend_irc1_w0p5"], [0.5, 0.5])
    assert np.allclose(candidates["gate_full_irc1_w0p5"], [0.35, 0.5])
    assert np.all((candidates["gate_exogenous_no_chla_w0p5"] >= 0.0) & (candidates["gate_exogenous_no_chla_w0p5"] <= 1.0))


def test_source_selector_uses_validation_only_and_fallback() -> None:
    validation = pd.DataFrame(
        {
            "source_id": ["A", "A", "A", "A", "B"],
            "bloom_h": [0, 0, 1, 1, 1],
            "candidate_a": [0.1, 0.2, 0.8, 0.9, 0.1],
            "candidate_b": [0.9, 0.8, 0.2, 0.1, 0.9],
        }
    )
    eval_frame = pd.DataFrame(
        {
            "source_id": ["A", "B"],
            "candidate_a": [0.8, 0.2],
            "candidate_b": [0.2, 0.9],
        }
    )

    score, source_selection = source_specific_selector(
        validation,
        eval_frame,
        ["candidate_a", "candidate_b"],
        min_rows=2,
        fallback_candidate="candidate_b",
        brier_tolerance=0.002,
    )

    assert np.allclose(score, [0.8, 0.9])
    selected = dict(zip(source_selection["source_id"], source_selection["selected_score"], strict=False))
    assert selected["A"] == "candidate_a"
    assert selected["B"] == "candidate_b"


def test_build_selection_reports_test_delta_vs_baseline() -> None:
    frame = pd.DataFrame(
        {
            "source_id": ["A"] * 8,
            "site_id": ["s1"] * 8,
            "origin_year_month": ["2020-01", "2020-02", "2020-03", "2020-04"] * 2,
            "horizon_months": [1] * 8,
            "split": ["validation"] * 4 + ["test"] * 4,
            "bloom_h": [0, 0, 1, 1, 0, 0, 1, 1],
            "target_risk_chla_h": [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0],
            "baseline_calibrated": [0.2, 0.3, 0.7, 0.8, 0.3, 0.4, 0.6, 0.7],
            "candidate_refined": [0.1, 0.2, 0.8, 0.9, 0.2, 0.3, 0.7, 0.8],
        }
    )

    metrics = evaluate_candidate_columns(frame, ["baseline_calibrated", "candidate_refined"])
    selection = build_selection(metrics)

    assert selection.loc[0, "score_name"] == "candidate_refined"
    assert round(float(selection.loc[0, "delta_test_brier_vs_baseline"]), 4) < 0
    assert round(float(selection.loc[0, "test_pr_auc"]), 4) == 1.0
