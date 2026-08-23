from __future__ import annotations

import pandas as pd

from src.experiments.closure_v2.build_eligibility import EXPECTED_SEEDS
from src.experiments.closure_v2.build_shared_fit_keys import build_shared_keys


def _ledger() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    identities = [
        ("wqp", "wqp:a", "2018-01", "2018-02", "training"),
        ("wqp", "wqp:b", "2019-01", "2019-02", "model_selection"),
        ("wqp", "wqp:c", "2021-01", "2021-02", "calibration_threshold"),
        ("wqp", "wqp:d", "2018-03", "2018-04", "training"),
    ]
    for seed in EXPECTED_SEEDS:
        for model_id in ("P0", "P1"):
            for source_id, site_id, origin, target, role in identities:
                complete = site_id != "wqp:d" or model_id == "P0"
                fit = role != "calibration_threshold" and complete
                calibration = role == "calibration_threshold" and complete
                rows.append(
                    {
                        "source_id": source_id,
                        "site_id": site_id,
                        "origin_year_month": origin,
                        "target_year_month": target,
                        "horizon_months": 1,
                        "base_seed": seed,
                        "model_id": model_id,
                        "time_role": role,
                        "intent_to_fit": role != "calibration_threshold",
                        "fit_eligible": fit,
                        "calibration_eligible": calibration,
                        "shared_fit_eligible": fit and site_id != "wqp:d",
                        "shared_calibration_eligible": calibration,
                    }
                )
    return pd.DataFrame(rows)


def test_shared_keys_are_exact_intersections_and_retain_calibration() -> None:
    shared, summary = build_shared_keys(_ledger())
    assert summary["fit_rows_per_seed"] == 2
    assert summary["calibration_rows_per_seed"] == 1
    assert len(shared) == len(EXPECTED_SEEDS) * 3
    assert "wqp:d" not in set(shared["site_id"])


def test_shared_key_identities_are_identical_across_seeds() -> None:
    shared, _ = build_shared_keys(_ledger())
    identity_columns = [
        "source_id",
        "site_id",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
        "time_role",
        "usage_role",
    ]
    reference: set[tuple[object, ...]] | None = None
    for _, slot in shared.groupby("base_seed"):
        identities = set(slot[identity_columns].itertuples(index=False, name=None))
        reference = identities if reference is None else reference
        assert identities == reference


def test_manifest_digests_are_deterministic() -> None:
    _, first = build_shared_keys(_ledger())
    _, second = build_shared_keys(_ledger().sample(frac=1.0, random_state=7))
    assert first == second
