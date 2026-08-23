#!/usr/bin/env python
"""Materialize exact shared P0/P1 complete-case keys for Closure V2."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pyarrow.parquet as pq

from src.experiments.closure_contract import ClosureContractError
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT
from src.experiments.closure_v2.build_eligibility import (
    CALIBRATION_ROLE,
    ELIGIBILITY_POLICY,
    EXPECTED_SEEDS,
    IDENTITY_COLUMNS,
    LEDGER_OUTPUT,
    _write_parquet_exclusive,
)
from src.experiments.closure_v2.contracts import validate_eligibility_policy
from src.experiments.closure_v2.hashing import key_digest


SHARED_OUTPUT = Path("data/closure_v2/development/shared_fit_keys.parquet")
SHARED_KEY_COLUMNS = [*IDENTITY_COLUMNS, "horizon_months", "base_seed"]


def build_shared_keys(ledger: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate and collapse a two-model ledger to model-independent shared keys."""
    required = {
        *SHARED_KEY_COLUMNS,
        "model_id",
        "time_role",
        "intent_to_fit",
        "fit_eligible",
        "calibration_eligible",
        "shared_fit_eligible",
        "shared_calibration_eligible",
    }
    missing = sorted(required - set(ledger.columns))
    if missing:
        raise ClosureContractError(f"Eligibility ledger is missing columns: {missing}")
    if set(ledger["model_id"].astype(str)) != {"P0", "P1"}:
        raise ClosureContractError("Eligibility ledger must contain exactly P0 and P1")
    if {int(value) for value in ledger["base_seed"].unique()} != set(EXPECTED_SEEDS):
        raise ClosureContractError("Eligibility ledger seed set drifted")
    if ledger.duplicated([*SHARED_KEY_COLUMNS, "model_id"]).any():
        raise ClosureContractError("Eligibility ledger has duplicate model/seed keys")
    role_counts = ledger.groupby(SHARED_KEY_COLUMNS, sort=False)["time_role"].nunique()
    if not role_counts.eq(1).all():
        raise ClosureContractError("A shared identity maps to more than one temporal role")
    role_records = ledger[[*SHARED_KEY_COLUMNS, "time_role"]].drop_duplicates(SHARED_KEY_COLUMNS)
    role_by_key = {
        tuple(row[column] for column in SHARED_KEY_COLUMNS): str(row["time_role"])
        for row in role_records.to_dict(orient="records")
    }

    fit_sets: dict[tuple[str, int], set[tuple[Any, ...]]] = {}
    calibration_sets: dict[tuple[str, int], set[tuple[Any, ...]]] = {}
    for raw_key, slot in ledger.groupby(["model_id", "base_seed"], sort=True):
        model_id, seed = cast(tuple[Any, Any], raw_key)
        fit_sets[(str(model_id), int(seed))] = set(
            slot.loc[slot["fit_eligible"], SHARED_KEY_COLUMNS].itertuples(index=False, name=None)
        )
        calibration_sets[(str(model_id), int(seed))] = set(
            slot.loc[slot["calibration_eligible"], SHARED_KEY_COLUMNS].itertuples(index=False, name=None)
        )

    rows: list[dict[str, Any]] = []
    digests: list[dict[str, Any]] = []
    for seed in EXPECTED_SEEDS:
        p0_fit = fit_sets[("P0", seed)]
        p1_fit = fit_sets[("P1", seed)]
        p0_calibration = calibration_sets[("P0", seed)]
        p1_calibration = calibration_sets[("P1", seed)]
        shared_fit = sorted(p0_fit & p1_fit)
        shared_calibration = sorted(p0_calibration & p1_calibration)
        expected_fit_flags = set(
            ledger.loc[
                ledger["base_seed"].eq(seed) & ledger["shared_fit_eligible"], SHARED_KEY_COLUMNS
            ].itertuples(index=False, name=None)
        )
        expected_calibration_flags = set(
            ledger.loc[
                ledger["base_seed"].eq(seed) & ledger["shared_calibration_eligible"], SHARED_KEY_COLUMNS
            ].itertuples(index=False, name=None)
        )
        if set(shared_fit) != expected_fit_flags or set(shared_calibration) != expected_calibration_flags:
            raise ClosureContractError(f"Ledger shared eligibility flags drifted for seed {seed}")
        for usage_role, keys in (("fit", shared_fit), ("calibration", shared_calibration)):
            digests.append(
                {
                    "base_seed": seed,
                    "usage_role": usage_role,
                    "rows": len(keys),
                    "sha256": key_digest(keys),
                }
            )
            for key in keys:
                row = dict(zip(SHARED_KEY_COLUMNS, key, strict=True))
                time_role = role_by_key[key]
                if (usage_role == "calibration") != (time_role == CALIBRATION_ROLE):
                    raise ClosureContractError(f"Shared key has invalid temporal role: {key}")
                row["time_role"] = time_role
                row["usage_role"] = usage_role
                rows.append(row)
    shared = pd.DataFrame(rows)
    shared = shared.sort_values(
        ["base_seed", "usage_role", "source_id", "site_id", "origin_year_month", "target_year_month"],
        kind="stable",
    ).reset_index(drop=True)
    fit_by_seed = shared.loc[shared["usage_role"].eq("fit")].groupby("base_seed", sort=True).size()
    calibration_by_seed = (
        shared.loc[shared["usage_role"].eq("calibration")].groupby("base_seed", sort=True).size()
    )
    if fit_by_seed.nunique() != 1 or calibration_by_seed.nunique() != 1:
        raise ClosureContractError("Shared key counts differ across registered seeds")
    return shared, {"digests": digests, "fit_rows_per_seed": int(fit_by_seed.iloc[0]), "calibration_rows_per_seed": int(calibration_by_seed.iloc[0])}
def write_shared_keys(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    validate_eligibility_policy()
    ledger_path = root / LEDGER_OUTPUT
    if ledger_path.is_symlink() or not ledger_path.is_file():
        raise ClosureContractError(f"Eligibility ledger is absent: {LEDGER_OUTPUT}")
    ledger = pq.read_table(ledger_path).to_pandas()
    shared, summary = build_shared_keys(ledger)
    _write_parquet_exclusive(shared, SHARED_OUTPUT, root=root)
    return {
        "status": "shared_fit_keys_written_unpublished",
        "rows": len(shared),
        "fit_rows_per_seed": summary["fit_rows_per_seed"],
        "calibration_rows_per_seed": summary["calibration_rows_per_seed"],
        "digests": summary["digests"],
        "output": SHARED_OUTPUT.as_posix(),
        "evaluation_paths_opened": False,
        "post_2021_outcomes_opened": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ELIGIBILITY_POLICY)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.config != ELIGIBILITY_POLICY:
        raise ClosureContractError(f"Only the locked eligibility policy is accepted: {ELIGIBILITY_POLICY}")
    print(json.dumps(write_shared_keys(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
