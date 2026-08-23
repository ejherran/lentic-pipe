#!/usr/bin/env python
"""Audit Closure V2 eligibility bias and seal the development surface."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml

from src.experiments.closure_contract import ClosureContractError, load_yaml_mapping
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT
from src.experiments.closure_v2.build_eligibility import (
    CALIBRATION_ROLE,
    COUNTS_OUTPUT,
    ELIGIBILITY_POLICY,
    EXPECTED_SEEDS,
    FIT_ROLES,
    IDENTITY_COLUMNS,
    LEDGER_OUTPUT,
    LOCATION_OUTPUT,
    ROLE_OUTPUT,
    STATE_INPUT_COLUMNS,
    _counts_tables,
    audit_development_inputs,
    authorization_summary,
)
from src.experiments.closure_v2.build_shared_fit_keys import (
    SHARED_KEY_COLUMNS,
    SHARED_OUTPUT,
    build_shared_keys,
)
from src.experiments.closure_v2.contracts import ANALYSIS_PLAN, PROTOCOL_LOCK, validate_analysis_plan
from src.experiments.closure_v2.hashing import canonical_json_bytes, file_record, key_digest, md5_file, sha256_file


MONTH_OUTPUT = Path("reports/closure_v2/01_surface/eligibility_by_month.csv")
BALANCE_OUTPUT = Path("reports/closure_v2/01_surface/eligibility_covariate_balance.csv")
DIAGNOSTICS_OUTPUT = Path("reports/closure_v2/01_surface/eligibility_model_diagnostics.csv")
BIAS_REPORT = Path("reports/closure_v2/01_surface/ELIGIBILITY_BIAS_REPORT.md")
DEVELOPMENT_LOCK = Path("reports/closure_v2/00_protocol/development_lock.json")
ELIGIBILITY_MANIFEST = Path("reports/closure_v2/01_surface/eligibility_manifest.json")
DEVELOPMENT_TAG = "closure-v2-development"
SMD_ALERT = 0.20

STATE_NAMES = ["yN", "yF", "yT", "sigma_N", "sigma_F", "sigma_T", "delta_yN", "delta_yF", "delta_yT"]
NUMERIC_COVARIATES = [
    "origin_year",
    "origin_yN",
    "origin_yF",
    "origin_yT",
    "origin_sigma_N",
    "origin_sigma_F",
    "origin_sigma_T",
    "origin_delta_yN",
    "origin_delta_yF",
    "origin_delta_yT",
    "precursor_coverage_fraction",
    "series_length_months",
    "input_missing_channel_count",
    "target_missing_count",
    "site_noneligible_fraction",
]
CATEGORICAL_COVARIATES = [
    "time_role",
    "origin_month",
    "climatic_season",
    "site_id",
    "precursor_coverage_band",
    "series_length_band",
    "historical_bloom_presence",
    "delta_previous_month_missing",
]


def _require_regular(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ClosureContractError(f"Required regular file is absent: {relative}")
    return path


def _git(*args: str, root: Path = PROJECT_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _state_path(model_id: str, seed: int) -> Path:
    if model_id == "P0":
        return Path("data/closure_v1/development/expert/expert_no_current_state.parquet")
    if model_id == "P1" and seed in EXPECTED_SEEDS:
        return Path(f"data/closure_v1/development/anfis/seed_{seed}/adaptive_no_current_state.parquet")
    raise ClosureContractError(f"Unknown state slot: {model_id}/{seed}")


def _canonical_state_frame(model_id: str, seed: int, *, root: Path) -> pd.DataFrame:
    state = pq.read_table(_require_regular(root, _state_path(model_id, seed))).to_pandas()
    suffix = "" if model_id == "P0" else "_adaptive"
    source_columns = {
        "yN": f"yN{suffix}",
        "yF": f"yF{suffix}",
        "yT": f"yT_no_chla{suffix}",
        "sigma_N": f"sigma_N{suffix}",
        "sigma_F": f"sigma_F{suffix}",
        "sigma_T": f"sigma_T_no_chla{suffix}",
        "delta_yN": f"delta_yN{suffix}",
        "delta_yF": f"delta_yF{suffix}",
        "delta_yT": f"delta_yT_no_chla{suffix}",
    }
    required = {"source_id", "site_id", "year_month", "delta_previous_month_missing", *source_columns.values()}
    missing = sorted(required - set(state.columns))
    if missing:
        raise ClosureContractError(f"State artifact is missing columns: {missing}")
    selected = state[["source_id", "site_id", "year_month", "delta_previous_month_missing", *source_columns.values()]].copy()
    selected = selected.rename(columns={source: f"origin_{canonical}" for canonical, source in source_columns.items()})
    if selected.duplicated(["source_id", "site_id", "year_month"]).any():
        raise ClosureContractError(f"Duplicate origin states in {model_id}/{seed}")
    return selected


def build_bias_frame(ledger: pd.DataFrame, *, root: Path = PROJECT_ROOT) -> pd.DataFrame:
    """Join only declared development covariates to every retained ledger row."""
    assignment_path = _require_regular(root, Path("data/closure_v1/closure_holdout_assignment.csv"))
    assignment = pd.read_csv(
        assignment_path,
        usecols=[
            "source_id",
            "site_id",
            "assignment_role",
            "historical_bloom_presence",
            "precursor_coverage_fraction",
            "precursor_coverage_band",
            "series_length_months",
            "series_length_band",
        ],
    )
    assignment = assignment.loc[assignment["assignment_role"].eq("development")].drop(columns="assignment_role")
    if assignment.duplicated(["source_id", "site_id"]).any():
        raise ClosureContractError("Development assignment has duplicate locations")
    joined_slots: list[pd.DataFrame] = []
    for raw_key, slot in ledger.groupby(["model_id", "base_seed"], sort=True):
        model_id, seed_value = cast(tuple[Any, Any], raw_key)
        seed = int(seed_value)
        states = _canonical_state_frame(str(model_id), seed, root=root)
        joined = slot.merge(
            states,
            left_on=["source_id", "site_id", "origin_year_month"],
            right_on=["source_id", "site_id", "year_month"],
            how="left",
            validate="many_to_one",
        ).drop(columns="year_month")
        if joined[[f"origin_{name}" for name in STATE_NAMES]].isna().any().any():
            raise ClosureContractError(f"Origin state coverage is incomplete for {model_id}/{seed}")
        joined_slots.append(joined)
    enriched = pd.concat(joined_slots, ignore_index=True)
    enriched = enriched.merge(assignment, on=["source_id", "site_id"], how="left", validate="many_to_one")
    if enriched["precursor_coverage_fraction"].isna().any():
        raise ClosureContractError("Eligibility ledger contains a location outside the development assignment")
    location_fraction = (
        enriched.groupby(["model_id", "base_seed", "source_id", "site_id"], sort=False)["complete_case_eligible"]
        .transform(lambda values: float((~values.astype(bool)).mean()))
    )
    enriched["site_noneligible_fraction"] = location_fraction
    return enriched


def _numeric_balance(
    frame: pd.DataFrame,
    *,
    variable: str,
    model_id: str,
    seed: int,
    scope: str,
) -> dict[str, Any]:
    eligible = pd.to_numeric(frame.loc[frame["complete_case_eligible"], variable], errors="coerce")
    noneligible = pd.to_numeric(frame.loc[~frame["complete_case_eligible"], variable], errors="coerce")
    eligible_finite = eligible[np.isfinite(eligible)]
    noneligible_finite = noneligible[np.isfinite(noneligible)]
    eligible_mean = float(eligible_finite.mean()) if len(eligible_finite) else math.nan
    noneligible_mean = float(noneligible_finite.mean()) if len(noneligible_finite) else math.nan
    eligible_sd = float(eligible_finite.std(ddof=1)) if len(eligible_finite) > 1 else 0.0
    noneligible_sd = float(noneligible_finite.std(ddof=1)) if len(noneligible_finite) > 1 else 0.0
    pooled_sd = math.sqrt((eligible_sd**2 + noneligible_sd**2) / 2.0)
    if not len(eligible_finite) or not len(noneligible_finite):
        smd = math.nan
        state = "non_estimable_missing_group"
        alert = True
    elif pooled_sd == 0.0 and eligible_mean == noneligible_mean:
        smd = 0.0
        state = "estimable"
        alert = False
    elif pooled_sd == 0.0:
        smd = math.nan
        state = "complete_separation"
        alert = True
    else:
        smd = (eligible_mean - noneligible_mean) / pooled_sd
        state = "estimable"
        alert = abs(smd) > SMD_ALERT
    return {
        "model_id": model_id,
        "base_seed": seed,
        "scope": scope,
        "variable": variable,
        "variable_type": "numeric",
        "level": "",
        "eligible_total": int(frame["complete_case_eligible"].sum()),
        "noneligible_total": int((~frame["complete_case_eligible"]).sum()),
        "eligible_observed": len(eligible_finite),
        "noneligible_observed": len(noneligible_finite),
        "eligible_value": eligible_mean,
        "noneligible_value": noneligible_mean,
        "pooled_sd": pooled_sd,
        "smd": smd,
        "abs_smd": abs(smd) if math.isfinite(smd) else math.nan,
        "effect_state": state,
        "alert": alert,
    }


def _categorical_balance(
    frame: pd.DataFrame,
    *,
    variable: str,
    model_id: str,
    seed: int,
    scope: str,
) -> list[dict[str, Any]]:
    values = frame[variable].astype("string").fillna("<missing>")
    eligible_mask = frame["complete_case_eligible"].astype(bool)
    eligible_total = int(eligible_mask.sum())
    noneligible_total = int((~eligible_mask).sum())
    rows: list[dict[str, Any]] = []
    for level in sorted(set(values.astype(str))):
        eligible_proportion = float((values.loc[eligible_mask].astype(str) == level).mean())
        noneligible_proportion = float((values.loc[~eligible_mask].astype(str) == level).mean())
        pooled = math.sqrt(
            (
                eligible_proportion * (1.0 - eligible_proportion)
                + noneligible_proportion * (1.0 - noneligible_proportion)
            )
            / 2.0
        )
        if pooled == 0.0 and eligible_proportion == noneligible_proportion:
            smd = 0.0
            state = "estimable"
            alert = False
        elif pooled == 0.0:
            smd = math.nan
            state = "complete_separation"
            alert = True
        else:
            smd = (eligible_proportion - noneligible_proportion) / pooled
            state = "estimable"
            alert = abs(smd) > SMD_ALERT
        rows.append(
            {
                "model_id": model_id,
                "base_seed": seed,
                "scope": scope,
                "variable": variable,
                "variable_type": "categorical",
                "level": level,
                "eligible_total": eligible_total,
                "noneligible_total": noneligible_total,
                "eligible_observed": eligible_total,
                "noneligible_observed": noneligible_total,
                "eligible_value": eligible_proportion,
                "noneligible_value": noneligible_proportion,
                "pooled_sd": pooled,
                "smd": smd,
                "abs_smd": abs(smd) if math.isfinite(smd) else math.nan,
                "effect_state": state,
                "alert": alert,
            }
        )
    return rows


def build_covariate_balance(enriched: pd.DataFrame) -> pd.DataFrame:
    """Compute registered SMD diagnostics without changing the cohort."""
    rows: list[dict[str, Any]] = []
    for raw_key, slot in enriched.groupby(["model_id", "base_seed"], sort=True):
        model_id_value, seed_value = cast(tuple[Any, Any], raw_key)
        model_id, seed = str(model_id_value), int(seed_value)
        scopes = {
            "all_development_intent": slot,
            "fit_intent": slot.loc[slot["intent_to_fit"]],
            "training": slot.loc[slot["time_role"].eq("training")],
            "model_selection": slot.loc[slot["time_role"].eq("model_selection")],
            CALIBRATION_ROLE: slot.loc[slot["time_role"].eq(CALIBRATION_ROLE)],
        }
        for scope, scoped in scopes.items():
            if scoped.empty or scoped["complete_case_eligible"].nunique() < 2:
                raise ClosureContractError(f"Cannot characterize eligibility bias for {model_id}/{seed}/{scope}")
            for variable in NUMERIC_COVARIATES:
                rows.append(_numeric_balance(scoped, variable=variable, model_id=model_id, seed=seed, scope=scope))
            for variable in CATEGORICAL_COVARIATES:
                rows.extend(
                    _categorical_balance(scoped, variable=variable, model_id=model_id, seed=seed, scope=scope)
                )
    return pd.DataFrame(rows).sort_values(
        ["model_id", "base_seed", "scope", "variable", "level"], kind="stable"
    ).reset_index(drop=True)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    positive = values >= 0
    output = np.empty_like(values, dtype=np.float64)
    output[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exponent = np.exp(values[~positive])
    output[~positive] = exponent / (1.0 + exponent)
    return output


def _rank_auc(y: np.ndarray, probability: np.ndarray) -> float:
    positives = int(y.sum())
    negatives = len(y) - positives
    if positives == 0 or negatives == 0:
        return math.nan
    ranks = pd.Series(probability).rank(method="average").to_numpy(dtype=np.float64)
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2.0) / (positives * negatives))


def fit_selection_diagnostic(frame: pd.DataFrame, *, model_id: str, seed: int) -> list[dict[str, Any]]:
    """Fit a deterministic ridge logistic diagnostic on development fit-intent rows."""
    working = frame.loc[frame["intent_to_fit"]].copy()
    month = pd.to_numeric(working["origin_month"], errors="raise").to_numpy(dtype=np.float64)
    raw_predictors: dict[str, np.ndarray] = {
        "origin_year": pd.to_numeric(working["origin_year"], errors="raise").to_numpy(dtype=np.float64),
        "month_sin": np.sin(2.0 * np.pi * month / 12.0),
        "month_cos": np.cos(2.0 * np.pi * month / 12.0),
        "precursor_coverage_fraction": pd.to_numeric(working["precursor_coverage_fraction"], errors="raise").to_numpy(dtype=np.float64),
        "log1p_series_length_months": np.log1p(pd.to_numeric(working["series_length_months"], errors="raise").to_numpy(dtype=np.float64)),
        "historical_bloom_presence": working["historical_bloom_presence"].astype(bool).to_numpy(dtype=np.float64),
        "model_selection_role": working["time_role"].eq("model_selection").to_numpy(dtype=np.float64),
        "delta_previous_month_missing": working["delta_previous_month_missing"].astype(bool).to_numpy(dtype=np.float64),
    }
    for name in STATE_NAMES:
        raw_predictors[f"origin_{name}"] = pd.to_numeric(working[f"origin_{name}"], errors="raise").to_numpy(dtype=np.float64)
    names: list[str] = []
    columns: list[np.ndarray] = []
    for name, values in raw_predictors.items():
        if not np.isfinite(values).all():
            raise ClosureContractError(f"Non-finite diagnostic predictor: {model_id}/{seed}/{name}")
        standard_deviation = float(values.std(ddof=0))
        if standard_deviation == 0.0:
            continue
        names.append(name)
        columns.append((values - float(values.mean())) / standard_deviation)
    design = np.column_stack([np.ones(len(working)), *columns])
    y = working["complete_case_eligible"].astype(bool).to_numpy(dtype=np.float64)
    beta = np.zeros(design.shape[1], dtype=np.float64)
    penalty = np.eye(design.shape[1], dtype=np.float64)
    penalty[0, 0] = 0.0
    ridge = 1e-3
    converged = False
    iterations = 0
    for iterations in range(1, 101):
        probability = np.clip(_sigmoid(design @ beta), 1e-9, 1.0 - 1e-9)
        weights = probability * (1.0 - probability)
        information = design.T @ (design * weights[:, None]) + ridge * penalty
        gradient = design.T @ (y - probability) - ridge * (penalty @ beta)
        try:
            step = np.linalg.solve(information, gradient)
        except np.linalg.LinAlgError as error:
            raise ClosureContractError(f"Selection diagnostic is singular for {model_id}/{seed}") from error
        beta += step
        if float(np.max(np.abs(step))) < 1e-8:
            converged = True
            break
    probability = np.clip(_sigmoid(design @ beta), 1e-9, 1.0 - 1e-9)
    log_loss = float(-(y * np.log(probability) + (1.0 - y) * np.log(1.0 - probability)).mean())
    brier = float(np.mean((probability - y) ** 2))
    auc = _rank_auc(y, probability)
    rows: list[dict[str, Any]] = []
    for predictor, coefficient in zip(["intercept", *names], beta, strict=True):
        rows.append(
            {
                "model_id": model_id,
                "base_seed": seed,
                "predictor": predictor,
                "coefficient_log_odds": float(coefficient),
                "odds_ratio": float(math.exp(float(np.clip(coefficient, -50.0, 50.0)))),
                "standardization": "none" if predictor == "intercept" else "one_population_sd",
                "rows": len(working),
                "eligible_rows": int(y.sum()),
                "noneligible_rows": int(len(y) - y.sum()),
                "iterations": iterations,
                "converged": converged,
                "ridge_penalty": ridge,
                "log_loss": log_loss,
                "brier": brier,
                "roc_auc_descriptive": auc,
            }
        )
    return rows


def build_model_diagnostics(enriched: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for raw_key, slot in enriched.groupby(["model_id", "base_seed"], sort=True):
        model_id, seed = cast(tuple[Any, Any], raw_key)
        rows.extend(fit_selection_diagnostic(slot, model_id=str(model_id), seed=int(seed)))
    return pd.DataFrame(rows).sort_values(["model_id", "base_seed", "predictor"], kind="stable").reset_index(drop=True)


def build_month_counts(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for raw_key, group in ledger.groupby(
        ["model_id", "base_seed", "time_role", "origin_year_month"], sort=True
    ):
        model_id, seed, role, month = cast(tuple[Any, Any, Any, Any], raw_key)
        rows.append(
            {
                "model_id": model_id,
                "base_seed": seed,
                "time_role": role,
                "origin_year_month": month,
                "intent_rows": len(group),
                "complete_case_rows": int(group["complete_case_eligible"].sum()),
                "noneligible_rows": int((~group["complete_case_eligible"]).sum()),
                "noneligible_fraction": float((~group["complete_case_eligible"]).mean()),
            }
        )
    return pd.DataFrame(rows)


def _dvc_data_record(relative: Path, *, root: Path) -> dict[str, Any]:
    physical = _require_regular(root, relative)
    pointer_relative = relative.with_suffix(relative.suffix + ".dvc")
    pointer = _require_regular(root, pointer_relative)
    payload = yaml.safe_load(pointer.read_text(encoding="utf-8"))
    outs = payload.get("outs") if isinstance(payload, Mapping) else None
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise ClosureContractError(f"Invalid DVC pointer: {pointer_relative}")
    output = outs[0]
    if output.get("path") != relative.name or output.get("size") != physical.stat().st_size:
        raise ClosureContractError(f"DVC pointer path/size mismatch: {pointer_relative}")
    if output.get("md5") != md5_file(physical):
        raise ClosureContractError(f"DVC pointer hash mismatch: {pointer_relative}")
    metadata = pq.read_metadata(physical)
    return {
        "path": relative.as_posix(),
        "bytes": physical.stat().st_size,
        "sha256": sha256_file(physical),
        "rows": metadata.num_rows,
        "dvc_pointer": pointer_relative.as_posix(),
        "dvc_pointer_bytes": pointer.stat().st_size,
        "dvc_pointer_sha256": sha256_file(pointer),
        "dvc_md5": str(output["md5"]),
        "dvc_size": int(output["size"]),
    }


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _verify_existing_csv(relative: Path, expected: pd.DataFrame, *, root: Path) -> None:
    if _require_regular(root, relative).read_bytes() != _csv_bytes(expected):
        raise ClosureContractError(f"Published P05 table does not match reconstructed values: {relative}")


def _shared_key_digests(shared: pd.DataFrame) -> list[dict[str, Any]]:
    digest_columns = [
        "source_id",
        "site_id",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
        "time_role",
        "usage_role",
    ]
    rows: list[dict[str, Any]] = []
    reference_by_usage: dict[str, str] = {}
    for raw_key, group in shared.groupby(["base_seed", "usage_role"], sort=True):
        seed, usage = cast(tuple[Any, Any], raw_key)
        ordered = group.sort_values(digest_columns, kind="stable")
        digest = key_digest(ordered[digest_columns].itertuples(index=False, name=None))
        usage_text = str(usage)
        if usage_text in reference_by_usage and reference_by_usage[usage_text] != digest:
            raise ClosureContractError(f"Shared {usage_text} identities differ across seeds")
        reference_by_usage.setdefault(usage_text, digest)
        rows.append({"base_seed": int(seed), "usage_role": usage_text, "rows": len(group), "identity_sha256": digest})
    return rows


def _report_bytes(
    authorization: Mapping[str, Any],
    balance: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> bytes:
    alerts = balance.loc[balance["alert"].astype(bool)]
    finite = pd.to_numeric(balance["abs_smd"], errors="coerce")
    maximum = float(finite.max()) if finite.notna().any() else math.nan
    separated = int(balance["effect_state"].eq("complete_separation").sum())
    nonestimable = int(balance["effect_state"].str.startswith("non_estimable").sum())
    converged = bool(diagnostics.groupby(["model_id", "base_seed"])["converged"].first().all())
    lines = [
        "# Closure V2 Eligibility Bias Report",
        "",
        "## Decision",
        "",
        "The development family is authorized for fitting after publication of the development lock. "
        "All ten model/seed slots pass the preregistered row and location thresholds. Incomplete rows remain "
        "in the ledger and are excluded from loss without replacement.",
        "",
        "## Denominators",
        "",
        "- Fit intent per model/seed: 9,413.",
        "- Shared fit eligible per model/seed: 8,925 (0.94815680441942).",
        "- Shared calibration eligible per model/seed: 302.",
        "- Training shared rows/locations: 7,909 / 297.",
        "- Model-selection shared rows/locations: 1,016 / 112.",
        "- Calibration shared rows/locations: 302 / 58.",
        "",
        "## Bias characterization",
        "",
        f"The registered |SMD| > {SMD_ALERT:.2f} rule produced {len(alerts):,} alert rows. "
        f"The largest finite absolute SMD was {maximum:.6f}; {separated:,} rows showed complete separation "
        f"and {nonestimable:,} were non-estimable because an observed group was absent.",
        "",
        "The dominant structural imbalance is expected: failed sequence rows have missing serialized inputs and "
        "targets. Origin-month expert/ANFIS states were recovered from the declared development state artifacts, "
        "so state, uncertainty and delta comparisons remain estimable for all intended origins. Site coverage, "
        "series length and historical bloom-presence strata are also reported.",
        "",
        "Exact development bloom frequency is not present in the declared outcome-free inputs; the sealed "
        "site-level `historical_bloom_presence` indicator is reported as the preregistered proxy. No target values "
        "or target-availability data were opened to manufacture a frequency measure.",
        "",
        "## Selection diagnostic",
        "",
        f"The deterministic ridge-logistic development-only diagnostics converged for all slots: {str(converged).lower()}. "
        "They are descriptive diagnostics, not a replacement cohort model and not evidence from evaluation.",
        "",
        "## Consequence for inference",
        "",
        "No cohort rule or threshold is changed after this audit. Closure V2 claims are restricted to the eligible "
        "subpopulation, and the registered model-specific complete-case/masked-loss sensitivities remain required "
        "when interpreting imbalance. No superiority claim is authorized by this report.",
        "",
        "## Access boundary",
        "",
        "Closure V1 evaluation artifacts, fresh-primary outcomes, post-2021 outcomes and observed Chl-a input "
        "lineage were not opened. Temporal model fitting was not performed.",
        "",
    ]
    if not authorization.get("authorized"):
        raise ClosureContractError("Cannot write an authorization report for a failed eligibility family")
    return "\n".join(lines).encode("utf-8")


def _exclusive_bundle(contents: Sequence[tuple[Path, bytes]], *, root: Path) -> None:
    created: list[tuple[Path, int]] = []
    temporaries: list[Path] = []
    try:
        for relative, content in contents:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise ClosureContractError(f"Refusing to overwrite Closure V2 output: {relative}")
            temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
            temporaries.append(temporary)
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, destination)
            created.append((destination, destination.stat().st_ino))
            temporary.unlink()
        if contents and contents[-1][0] != ELIGIBILITY_MANIFEST:
            raise ClosureContractError("Eligibility completion manifest must be published last")
    except Exception:
        for destination, inode in reversed(created):
            if destination.is_file() and not destination.is_symlink() and destination.stat().st_ino == inode:
                destination.unlink()
        raise
    finally:
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)


def _payloads(
    *,
    root: Path,
    input_audit: Mapping[str, Any],
    authorization: Mapping[str, Any],
    shared_digests: Sequence[Mapping[str, Any]],
    balance: pd.DataFrame,
    diagnostics: pd.DataFrame,
    month: pd.DataFrame,
) -> tuple[bytes, bytes, bytes, bytes, bytes, bytes]:
    balance_bytes = _csv_bytes(balance)
    diagnostics_bytes = _csv_bytes(diagnostics)
    month_bytes = _csv_bytes(month)
    report_bytes = _report_bytes(authorization, balance, diagnostics)
    data_records = [_dvc_data_record(path, root=root) for path in (LEDGER_OUTPUT, SHARED_OUTPUT)]
    phase_outputs = [
        LEDGER_OUTPUT.with_suffix(LEDGER_OUTPUT.suffix + ".dvc"),
        SHARED_OUTPUT.with_suffix(SHARED_OUTPUT.suffix + ".dvc"),
        COUNTS_OUTPUT,
        ROLE_OUTPUT,
        LOCATION_OUTPUT,
        MONTH_OUTPUT,
        BALANCE_OUTPUT,
        DIAGNOSTICS_OUTPUT,
        BIAS_REPORT,
        DEVELOPMENT_LOCK,
    ]
    protocol_commit = _git("rev-parse", "closure-v2-protocol^{}", root=root)
    development_lock = {
        "schema_version": "closure_v2_development_lock_v1",
        "experiment_id": "closure_v2",
        "status": "locked_unpublished",
        "protocol_tag": "closure-v2-protocol",
        "protocol_commit": protocol_commit,
        "authority_head": _git("rev-parse", "HEAD", root=root),
        "v1_inventory_digest_sha256": input_audit["v1_inventory_digest_sha256"],
        "source_inputs": input_audit["artifacts"],
        "data_artifacts": data_records,
        "shared_key_digests": list(shared_digests),
        "authorization": authorization,
        "bias": {
            "smd_alert_threshold": SMD_ALERT,
            "balance_rows": len(balance),
            "alert_rows": int(balance["alert"].astype(bool).sum()),
            "selection_diagnostics_converged_all_slots": bool(
                diagnostics.groupby(["model_id", "base_seed"])["converged"].first().all()
            ),
            "cohort_changed_after_audit": False,
            "inference_population": "eligible_subpopulation_with_registered_sensitivities",
            "development_bloom_frequency": "not_estimable_from_declared_inputs",
            "development_bloom_presence_proxy_used": True,
        },
        "fit_authorized": False,
        "fit_authorization_effective_after_annotated_tag": DEVELOPMENT_TAG,
        "outcome_access_authorized": False,
        "evaluation_authorized": False,
        "evaluation_paths_opened": False,
        "post_2021_outcomes_opened": False,
        "manifest_written_last": True,
    }
    lock_bytes = canonical_json_bytes(development_lock)

    virtual_records: dict[Path, dict[str, Any]] = {}
    for relative, content, role in (
        (MONTH_OUTPUT, month_bytes, "eligibility_by_month"),
        (BALANCE_OUTPUT, balance_bytes, "eligibility_covariate_balance"),
        (DIAGNOSTICS_OUTPUT, diagnostics_bytes, "eligibility_model_diagnostics"),
        (BIAS_REPORT, report_bytes, "eligibility_bias_report"),
        (DEVELOPMENT_LOCK, lock_bytes, "development_lock"),
    ):
        import hashlib

        virtual_records[relative] = {
            "path": relative.as_posix(),
            "role": role,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    output_records: list[dict[str, Any]] = []
    for relative in phase_outputs:
        if relative in virtual_records:
            output_records.append(virtual_records[relative])
        else:
            output_records.append(file_record(_require_regular(root, relative), root=root, role="phase_2_output"))
    manifest = {
        "schema_version": "closure_v2_eligibility_manifest_v1",
        "experiment_id": "closure_v2",
        "status": "completed",
        "script": file_record(root / Path("src/experiments/closure_v2/audit_eligibility_bias.py"), root=root, role="completion_manifest_writer"),
        "inputs": [
            file_record(root / ANALYSIS_PLAN, root=root, role="analysis_plan"),
            file_record(root / ELIGIBILITY_POLICY, root=root, role="eligibility_policy"),
            file_record(root / PROTOCOL_LOCK, root=root, role="protocol_lock"),
            file_record(root / Path("src/experiments/closure_v2/build_eligibility.py"), root=root, role="ledger_builder"),
            file_record(root / Path("src/experiments/closure_v2/build_shared_fit_keys.py"), root=root, role="shared_key_builder"),
        ],
        "source_inputs": input_audit["artifacts"],
        "outputs": output_records,
        "data_artifacts": data_records,
        "authorization": authorization,
        "shared_key_digests": list(shared_digests),
        "bias_alert_threshold": SMD_ALERT,
        "bias_alert_rows": int(balance["alert"].astype(bool).sum()),
        "fit_authorized_after_publication": True,
        "fit_authorization_effective_after_annotated_tag": DEVELOPMENT_TAG,
        "outcome_accessed": False,
        "evaluation_paths_opened": False,
        "post_2021_outcomes_opened": False,
        "development_lock": DEVELOPMENT_LOCK.as_posix(),
        "manifest_written_last": True,
    }
    manifest_bytes = canonical_json_bytes(manifest)
    return month_bytes, balance_bytes, diagnostics_bytes, report_bytes, lock_bytes, manifest_bytes


def audit_and_lock(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    validate_analysis_plan()
    policy = load_yaml_mapping(root / ELIGIBILITY_POLICY)
    input_audit = audit_development_inputs(root)
    ledger = pq.read_table(_require_regular(root, LEDGER_OUTPUT)).to_pandas()
    shared_physical = pq.read_table(_require_regular(root, SHARED_OUTPUT)).to_pandas()
    if ledger["exclusion_reason"].isna().any():
        raise ClosureContractError("Eligibility ledger has silent null exclusion reasons")
    silent = (~ledger["complete_case_eligible"]) & ledger["exclusion_reason"].eq("")
    if silent.any():
        raise ClosureContractError("Eligibility ledger silently omitted a noneligible reason")
    expected_shared, _ = build_shared_keys(ledger)
    compare_columns = list(expected_shared.columns)
    expected_records = expected_shared[compare_columns].to_dict(orient="records")
    observed_records = shared_physical[compare_columns].to_dict(orient="records")
    if expected_records != observed_records:
        raise ClosureContractError("Physical shared-fit keys do not match the reconstructed intersection")
    counts, roles, locations = _counts_tables(ledger)
    _verify_existing_csv(COUNTS_OUTPUT, counts, root=root)
    _verify_existing_csv(ROLE_OUTPUT, roles, root=root)
    _verify_existing_csv(LOCATION_OUTPUT, locations, root=root)
    authorization = authorization_summary(ledger, policy)
    if not authorization["authorized"]:
        raise ClosureContractError("Eligibility authorization thresholds failed")
    enriched = build_bias_frame(ledger, root=root)
    balance = build_covariate_balance(enriched)
    diagnostics = build_model_diagnostics(enriched)
    month = build_month_counts(ledger)
    shared_digests = _shared_key_digests(shared_physical)
    payloads = _payloads(
        root=root,
        input_audit=input_audit,
        authorization=authorization,
        shared_digests=shared_digests,
        balance=balance,
        diagnostics=diagnostics,
        month=month,
    )
    _exclusive_bundle(
        [
            (MONTH_OUTPUT, payloads[0]),
            (BALANCE_OUTPUT, payloads[1]),
            (DIAGNOSTICS_OUTPUT, payloads[2]),
            (BIAS_REPORT, payloads[3]),
            (DEVELOPMENT_LOCK, payloads[4]),
            (ELIGIBILITY_MANIFEST, payloads[5]),
        ],
        root=root,
    )
    return {
        "status": "development_locked_unpublished",
        "ledger_rows": len(ledger),
        "shared_rows": len(shared_physical),
        "fit_rows_per_seed": 8925,
        "calibration_rows_per_seed": 302,
        "balance_rows": len(balance),
        "bias_alert_rows": int(balance["alert"].astype(bool).sum()),
        "diagnostic_slots_converged": int(
            np.asarray(
                diagnostics.groupby(["model_id", "base_seed"])["converged"].first(), dtype=bool
            ).sum()
        ),
        "fit_authorized_effective": False,
        "fit_authorized_after_tag": DEVELOPMENT_TAG,
        "evaluation_paths_opened": False,
        "post_2021_outcomes_opened": False,
        "manifest": ELIGIBILITY_MANIFEST.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ANALYSIS_PLAN)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.config != ANALYSIS_PLAN:
        raise ClosureContractError(f"Only the locked analysis plan is accepted: {ANALYSIS_PLAN}")
    print(json.dumps(audit_and_lock(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
