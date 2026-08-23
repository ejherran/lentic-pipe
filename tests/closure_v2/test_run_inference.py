from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.experiments.closure_v2 import run_inference as inference


def _surface() -> pd.DataFrame:
    rows = []
    for site, labels in (("a", [0, 1, 0, 1]), ("b", [0, 0, 1, 1]), ("c", [0, 1, 1, 0])):
        for index, label in enumerate(labels):
            rows.append({
                "evaluation_cohort": "fresh_primary", "comparison_id": "P1_vs_P0",
                "challenger": "P1", "reference": "P0", "horizon_months": 1,
                "origin_id": f"{site}-{index}", "origin_year_month": f"2022-{index + 1:02d}",
                "source_id": "wqp", "site_id": site, "cluster_id": f"wqp::{site}",
                "y_true": label, "bloom_probability_challenger": 0.8 if label else 0.2,
                "bloom_probability_reference": 0.6 if label else 0.4,
            })
    return pd.DataFrame(rows)


def test_parser_separates_materialization_and_finalize() -> None:
    parser = inference.build_parser()
    assert parser.parse_args([]).execute is False
    assert parser.parse_args(["--execute"]).execute is True
    assert parser.parse_args(["--finalize"]).finalize is True
    assert parser.parse_args(["--complete-manifest"]).complete_manifest is True
    with pytest.raises(SystemExit):
        parser.parse_args(["--execute", "--finalize"])


def test_registered_holm_universes_are_exact_and_complete() -> None:
    assert {key: len(value) for key, value in inference.FAMILIES.items()} == {"A": 3, "B": 3, "C": 6}
    assert len({item for family in inference.FAMILIES.values() for item in family}) == 12


def test_cluster_bootstrap_is_deterministic() -> None:
    first, first_rows = inference._bootstrap_effect(_surface(), metric="brier", estimand="site_weighted")
    second, second_rows = inference._bootstrap_effect(_surface(), metric="brier", estimand="site_weighted")
    assert first == second
    pd.testing.assert_frame_equal(first_rows, second_rows)
    assert first["valid_replicates"] == 2000
    assert first["estimate"] < 0.0


def test_pr_auc_single_class_replicate_is_not_zero() -> None:
    surface = _surface().copy()
    surface["y_true"] = 0
    summary, rows = inference._bootstrap_effect(surface, metric="pr_auc", estimand="observation_weighted")
    assert summary["valid_replicates"] == 0
    assert np.isnan(summary["ci95_lower"])
    assert rows["delta_challenger_minus_reference"].isna().all()
    assert set(rows["replicate_status"]) == {"replicate_not_estimable_single_class"}


def test_adjudication_respects_metric_direction() -> None:
    assert inference._adjudication("brier", -0.1, -0.2, -0.01) == "superior"
    assert inference._adjudication("brier", 0.1, 0.01, 0.2) == "inferior"
    assert inference._adjudication("pr_auc", 0.1, 0.01, 0.2) == "superior"
    assert inference._adjudication("pr_auc", -0.1, -0.2, -0.01) == "inferior"


def test_site_pr_auc_marks_single_class_as_not_estimable() -> None:
    surface = _surface()
    surface.loc[surface["site_id"].eq("a"), "y_true"] = 0
    site = inference._site_rows(surface, "pr_auc")
    row = site.loc[site["site_id"].eq("a")].iloc[0]
    assert row["status"] == "not_estimable_single_class"
    assert np.isnan(row["delta_challenger_minus_reference"])
