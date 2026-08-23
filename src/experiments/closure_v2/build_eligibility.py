#!/usr/bin/env python
"""Audit Closure V1 development inputs and build the Closure V2 eligibility ledger."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.experiments.closure_contract import ClosureContractError, load_json_mapping
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT, audit_repository
from src.experiments.closure_v2.contracts import (
    ELIGIBILITY_POLICY,
    EXPECTED_SEEDS,
    PROTOCOL_LOCK,
    validate_eligibility_policy,
)
from src.experiments.closure_v2.hashing import md5_file, sha256_file


PROTOCOL_TAG = "closure-v2-protocol"
V1_TAG = "thesis-closure-v1"
LEDGER_OUTPUT = Path("data/closure_v2/development/fit_eligibility.parquet")
COUNTS_OUTPUT = Path("reports/closure_v2/01_surface/eligibility_counts.csv")
ROLE_OUTPUT = Path("reports/closure_v2/01_surface/eligibility_by_role.csv")
LOCATION_OUTPUT = Path("reports/closure_v2/01_surface/eligibility_by_location.csv")

IDENTITY_COLUMNS = ["source_id", "site_id", "origin_year_month", "target_year_month"]
INPUT_COLUMNS = [
    "x_yN",
    "x_yF",
    "x_yT",
    "x_sigma_N",
    "x_sigma_F",
    "x_sigma_T",
    "x_delta_yN",
    "x_delta_yF",
    "x_delta_yT",
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
]
STATE_INPUT_COLUMNS = INPUT_COLUMNS[:9]
TARGET_COLUMNS = [
    "target_yN",
    "target_yF",
    "target_yT",
    "target_sigma_N",
    "target_sigma_F",
    "target_sigma_T",
    "target_delta_yN",
    "target_delta_yF",
    "target_delta_yT",
]
FIT_ROLES = {"training", "model_selection"}
CALIBRATION_ROLE = "calibration_threshold"
EXPECTED_ROLES = FIT_ROLES | {CALIBRATION_ROLE}


@dataclass(frozen=True)
class ArtifactSpec:
    path: Path
    manifest: Path

    @property
    def pointer(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".dvc")


@dataclass(frozen=True)
class SequenceSpec(ArtifactSpec):
    model_id: str
    base_seed: int | None


def _sequence_specs() -> tuple[SequenceSpec, ...]:
    p0 = SequenceSpec(
        path=Path("data/closure_v1/development/sequences/P0/expert_no_current.parquet"),
        manifest=Path("reports/closure_v1/01_surface/sequences/P0/expert_no_current_manifest.json"),
        model_id="P0",
        base_seed=None,
    )
    p1 = tuple(
        SequenceSpec(
            path=Path(f"data/closure_v1/development/sequences/P1/seed_{seed}.parquet"),
            manifest=Path(f"reports/closure_v1/01_surface/sequences/P1/seed_{seed}_manifest.json"),
            model_id="P1",
            base_seed=seed,
        )
        for seed in EXPECTED_SEEDS
    )
    return (p0, *p1)


def _state_specs() -> tuple[ArtifactSpec, ...]:
    expert = ArtifactSpec(
        path=Path("data/closure_v1/development/expert/expert_no_current_state.parquet"),
        manifest=Path("reports/closure_v1/01_surface/expert/expert_no_current_state_manifest.json"),
    )
    adaptive = tuple(
        ArtifactSpec(
            path=Path(f"data/closure_v1/development/anfis/seed_{seed}/adaptive_no_current_state.parquet"),
            manifest=Path(f"reports/closure_v1/01_surface/anfis/seed_{seed}/manifest.json"),
        )
        for seed in EXPECTED_SEEDS
    )
    return (expert, *adaptive)


def _git(*args: str, root: Path = PROJECT_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _require_regular(root: Path, relative: Path) -> Path:
    candidate = root / relative
    if candidate.is_symlink() or not candidate.is_file():
        raise ClosureContractError(f"Required input is not a regular file: {relative}")
    return candidate


def _verify_tagged_bytes(relative: Path, *, tag: str, root: Path) -> None:
    physical = _require_regular(root, relative).read_bytes()
    tagged = subprocess.run(
        ["git", "show", f"{tag}:{relative.as_posix()}"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    if physical != tagged:
        raise ClosureContractError(f"Working-tree input differs from {tag}: {relative}")


def validate_protocol_publication(root: Path = PROJECT_ROOT) -> dict[str, str]:
    """Fail closed unless the immutable protocol tag is published in local history."""
    if _git("cat-file", "-t", f"refs/tags/{PROTOCOL_TAG}", root=root) != "tag":
        raise ClosureContractError(f"{PROTOCOL_TAG} must be an annotated tag")
    protocol_commit = _git("rev-parse", f"{PROTOCOL_TAG}^{{}}", root=root)
    head = _git("rev-parse", "HEAD", root=root)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", protocol_commit, head],
        cwd=root,
        check=True,
        capture_output=True,
    )
    _verify_tagged_bytes(PROTOCOL_LOCK, tag=PROTOCOL_TAG, root=root)
    return {"protocol_tag": PROTOCOL_TAG, "protocol_commit": protocol_commit, "head": head}


def _manifest_output(manifest: Mapping[str, Any], relative: Path) -> Mapping[str, Any]:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        raise ClosureContractError(f"Manifest has no outputs list for {relative}")
    matches = [item for item in outputs if isinstance(item, Mapping) and item.get("path") == relative.as_posix()]
    if len(matches) != 1:
        raise ClosureContractError(f"Manifest must bind exactly one output for {relative}")
    return matches[0]


def _audit_artifact(spec: ArtifactSpec, *, root: Path) -> dict[str, Any]:
    physical = _require_regular(root, spec.path)
    pointer = _require_regular(root, spec.pointer)
    manifest_path = _require_regular(root, spec.manifest)
    _verify_tagged_bytes(spec.pointer, tag=V1_TAG, root=root)
    _verify_tagged_bytes(spec.manifest, tag=V1_TAG, root=root)

    manifest = load_json_mapping(manifest_path)
    output = _manifest_output(manifest, spec.path)
    physical_sha = sha256_file(physical)
    if output.get("bytes") != physical.stat().st_size or output.get("sha256") != physical_sha:
        raise ClosureContractError(f"V1 manifest hash/size mismatch: {spec.path}")

    pointer_payload = yaml.safe_load(pointer.read_text(encoding="utf-8"))
    outs = pointer_payload.get("outs") if isinstance(pointer_payload, Mapping) else None
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise ClosureContractError(f"Expected one single-file DVC output: {spec.pointer}")
    dvc_output = outs[0]
    if dvc_output.get("path") != spec.path.name:
        raise ClosureContractError(f"DVC pointer path mismatch: {spec.pointer}")
    if dvc_output.get("size") != physical.stat().st_size or dvc_output.get("md5") != md5_file(physical):
        raise ClosureContractError(f"DVC pointer hash/size mismatch: {spec.pointer}")

    source_commit = _git("log", "-1", "--format=%H", "--", spec.pointer.as_posix(), root=root)
    if not source_commit:
        raise ClosureContractError(f"Cannot resolve source commit for {spec.pointer}")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, f"{V1_TAG}^{{}}"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return {
        "path": spec.path.as_posix(),
        "source_commit": source_commit,
        "bytes": physical.stat().st_size,
        "sha256": physical_sha,
        "dvc_pointer": spec.pointer.as_posix(),
        "dvc_md5": str(dvc_output["md5"]),
        "dvc_size": int(dvc_output["size"]),
        "manifest": spec.manifest.as_posix(),
        "manifest_sha256": sha256_file(manifest_path),
    }


def audit_development_inputs(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Verify all preferred V1 development artifacts without opening evaluation data."""
    protocol = validate_protocol_publication(root)
    v1 = audit_repository(root)
    if v1["protected_v1_changes"]:
        raise ClosureContractError(f"Closure V1 drift detected: {v1['protected_v1_changes']}")
    records = [_audit_artifact(spec, root=root) for spec in (*_sequence_specs(), *_state_specs())]
    return {
        "status": "passed",
        **protocol,
        "v1_inventory_digest_sha256": v1["inventory_digest_sha256"],
        "artifact_count": len(records),
        "artifacts": records,
        "evaluation_paths_opened": False,
        "post_2021_outcomes_opened": False,
    }


def _month_role(value: str) -> str | None:
    if value <= "2018-12":
        return "training"
    if "2019-01" <= value <= "2020-12":
        return "model_selection"
    if "2021-01" <= value <= "2021-12":
        return CALIBRATION_ROLE
    return None


def _finite_list(value: Any, *, expected_length: int = 12) -> bool:
    if value is None:
        return False
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError):
        return False
    return array.shape == (expected_length,) and bool(np.isfinite(array).all())


def _finite_scalar(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _climatic_season(month: int) -> str:
    if month in {12, 1, 2}:
        return "DJF"
    if month in {3, 4, 5}:
        return "MAM"
    if month in {6, 7, 8}:
        return "JJA"
    return "SON"


def classify_sequence_frame(
    frame: pd.DataFrame,
    *,
    model_id: str,
    base_seed: int,
    holdout_keys: set[tuple[str, str]],
) -> pd.DataFrame:
    """Classify every intended sequence row; never silently discard failures."""
    required = {
        *IDENTITY_COLUMNS,
        "model_id",
        "base_seed",
        "assignment_role",
        "time_role",
        "sequence_status",
        "failure_reason",
        *INPUT_COLUMNS,
        *TARGET_COLUMNS,
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ClosureContractError(f"Sequence input is missing columns: {missing}")
    if frame.duplicated(IDENTITY_COLUMNS).any():
        raise ClosureContractError(f"Duplicate sequence identities in {model_id}/{base_seed}")
    if set(frame["model_id"].astype(str)) != {model_id}:
        raise ClosureContractError(f"Unexpected model_id values in {model_id}/{base_seed}")
    if set(frame["assignment_role"].astype(str)) != {"development"}:
        raise ClosureContractError(f"Holdout or unknown assignment detected in {model_id}/{base_seed}")
    if not set(frame["time_role"].astype(str)).issubset(EXPECTED_ROLES):
        raise ClosureContractError(f"Unknown time role detected in {model_id}/{base_seed}")
    if any("chla" in column.lower() for column in INPUT_COLUMNS):
        raise ClosureContractError("Observed Chl-a lineage detected in input channels")

    output_rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        source_id = str(row["source_id"])
        site_id = str(row["site_id"])
        origin = str(row["origin_year_month"])
        target = str(row["target_year_month"])
        time_role = str(row["time_role"])
        if (source_id, site_id) in holdout_keys:
            raise ClosureContractError(f"Holdout overlap detected: {source_id}/{site_id}")
        if origin > "2021-12" or target > "2021-12":
            raise ClosureContractError(f"Post-2021 development row detected: {source_id}/{site_id}/{origin}")
        role_geometry_valid = _month_role(origin) == time_role and _month_role(target) == time_role
        input_flags = [_finite_list(row[column]) for column in INPUT_COLUMNS]
        target_flags = [_finite_scalar(row[column]) for column in TARGET_COLUMNS]
        input_complete = all(input_flags)
        target_complete = all(target_flags)
        sequence_status = str(row["sequence_status"])
        failure_reason = str(row["failure_reason"])
        complete_case = (
            sequence_status == "success"
            and input_complete
            and target_complete
            and role_geometry_valid
        )
        intent_to_fit = time_role in FIT_ROLES
        intent_to_calibrate = time_role == CALIBRATION_ROLE
        reasons: list[str] = []
        if sequence_status != "success":
            reasons.append(f"sequence_{sequence_status}")
        if failure_reason:
            reasons.append(f"failure_{failure_reason}")
        if not input_complete:
            reasons.append("input_incomplete")
        if not target_complete:
            reasons.append("target_incomplete")
        if not role_geometry_valid:
            reasons.append("origin_target_role_mismatch")
        if complete_case and intent_to_calibrate:
            reasons.append("reserved_for_calibration")
        if not reasons and not intent_to_fit:
            reasons.append("role_not_authorized")
        exclusion_reason = "|".join(reasons)

        origin_month = int(origin[5:7])
        result: dict[str, Any] = {
            "source_id": source_id,
            "site_id": site_id,
            "origin_year_month": origin,
            "target_year_month": target,
            "horizon_months": 1,
            "time_role": time_role,
            "model_id": model_id,
            "base_seed": base_seed,
            "intent_to_fit": intent_to_fit,
            "intent_to_calibrate": intent_to_calibrate,
            "sequence_status": sequence_status,
            "failure_reason": failure_reason,
            "input_complete": input_complete,
            "target_complete": target_complete,
            "role_geometry_valid": role_geometry_valid,
            "complete_case_eligible": complete_case,
            "fit_eligible": complete_case and intent_to_fit,
            "calibration_eligible": complete_case and intent_to_calibrate,
            "shared_fit_eligible": False,
            "shared_calibration_eligible": False,
            "exclusion_reason": exclusion_reason,
            "origin_year": int(origin[:4]),
            "origin_month": origin_month,
            "climatic_season": _climatic_season(origin_month),
            "input_missing_channel_count": len(INPUT_COLUMNS) - sum(input_flags),
            "target_missing_count": len(TARGET_COLUMNS) - sum(target_flags),
        }
        for column in STATE_INPUT_COLUMNS:
            value = row[column]
            result[f"last_{column.removeprefix('x_')}"] = (
                float(np.asarray(value, dtype=np.float64)[-1]) if _finite_list(value) else np.nan
            )
        output_rows.append(result)
    return pd.DataFrame(output_rows)


def _holdout_keys(root: Path) -> set[tuple[str, str]]:
    assignment = pd.read_csv(
        _require_regular(root, Path("data/closure_v1/closure_holdout_assignment.csv")),
        usecols=["source_id", "site_id", "assignment_role"],
    )
    unknown = set(assignment["assignment_role"].astype(str)) - {"development", "internal_holdout"}
    if unknown:
        raise ClosureContractError(f"Unknown V1 assignment roles: {sorted(unknown)}")
    held = assignment.loc[
        assignment["assignment_role"].eq("internal_holdout"), ["source_id", "site_id"]
    ]
    return set(held.itertuples(index=False, name=None))


def _load_sequence(spec: SequenceSpec, *, root: Path) -> pd.DataFrame:
    manifest = load_json_mapping(_require_regular(root, spec.manifest))
    if manifest.get("status") != "completed" or manifest.get("experiment_id") != "closure_v1":
        raise ClosureContractError(f"Sequence manifest is not completed Closure V1: {spec.manifest}")
    if manifest.get("model_id") != spec.model_id or manifest.get("base_seed") != spec.base_seed:
        raise ClosureContractError(f"Sequence manifest slot mismatch: {spec.manifest}")
    if manifest.get("future_outcomes_accessed") is not False or manifest.get("evaluation_authorized") is not False:
        raise ClosureContractError(f"Sequence manifest is not development-only: {spec.manifest}")
    if manifest.get("input_columns") != INPUT_COLUMNS or manifest.get("target_columns") != TARGET_COLUMNS:
        raise ClosureContractError(f"Sequence channel contract mismatch: {spec.manifest}")
    table = pq.read_table(_require_regular(root, spec.path))
    return table.to_pandas()


def build_eligibility_ledger(root: Path = PROJECT_ROOT) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build the complete 2-model × 5-seed intent ledger in memory."""
    input_audit = audit_development_inputs(root)
    holdout = _holdout_keys(root)
    classified: list[pd.DataFrame] = []
    specs = _sequence_specs()
    p0_frame = _load_sequence(specs[0], root=root)
    for seed in EXPECTED_SEEDS:
        classified.append(classify_sequence_frame(p0_frame, model_id="P0", base_seed=seed, holdout_keys=holdout))
    for spec in specs[1:]:
        if spec.base_seed is None:
            raise ClosureContractError("P1 sequence seed must not be null")
        classified.append(
            classify_sequence_frame(
                _load_sequence(spec, root=root),
                model_id="P1",
                base_seed=spec.base_seed,
                holdout_keys=holdout,
            )
        )
    ledger = pd.concat(classified, ignore_index=True)
    intersection_columns = [*IDENTITY_COLUMNS, "horizon_months", "base_seed"]
    for eligibility, shared_column in (
        ("fit_eligible", "shared_fit_eligible"),
        ("calibration_eligible", "shared_calibration_eligible"),
    ):
        eligible = ledger.loc[ledger[eligibility], [*intersection_columns, "model_id"]]
        counts = eligible.groupby(intersection_columns, sort=False)["model_id"].nunique()
        shared_index = counts[counts.eq(2)].index
        keyed = pd.MultiIndex.from_frame(ledger[intersection_columns])
        ledger[shared_column] = keyed.isin(shared_index)
    ledger = ledger.sort_values(
        ["model_id", "base_seed", "source_id", "site_id", "origin_year_month", "target_year_month"],
        kind="stable",
    ).reset_index(drop=True)
    return ledger, input_audit


def authorization_summary(ledger: pd.DataFrame, policy: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate every preregistered row and location threshold per model/seed."""
    thresholds = policy["authorization_thresholds"]
    slots: list[dict[str, Any]] = []
    for raw_key, slot in ledger.groupby(["model_id", "base_seed"], sort=True):
        model_id, base_seed = cast(tuple[Any, Any], raw_key)
        fit = slot.loc[slot["intent_to_fit"]]
        fit_eligible = slot.loc[slot["shared_fit_eligible"]]
        calibration = slot.loc[slot["shared_calibration_eligible"]]
        role_rows = {
            role: int(fit_eligible["time_role"].eq(role).sum())
            for role in sorted(FIT_ROLES)
        }
        role_rows[CALIBRATION_ROLE] = len(calibration)
        role_locations = {
            role: int(
                pd.concat(
                    [fit_eligible, calibration], ignore_index=True
                ).loc[lambda frame: frame["time_role"].eq(role), ["source_id", "site_id"]].drop_duplicates().shape[0]
            )
            for role in sorted(EXPECTED_ROLES)
        }
        fraction = float(len(fit_eligible) / len(fit)) if len(fit) else 0.0
        passed = (
            fraction >= float(thresholds["minimum_overall_fit_eligibility_fraction"])
            and role_rows["training"] >= int(thresholds["minimum_training_rows"])
            and role_rows["model_selection"] >= int(thresholds["minimum_model_selection_rows"])
            and role_rows[CALIBRATION_ROLE] >= int(thresholds["minimum_calibration_rows"])
            and role_locations["training"] >= int(thresholds["minimum_training_locations"])
            and role_locations["model_selection"] >= int(thresholds["minimum_model_selection_locations"])
            and role_locations[CALIBRATION_ROLE] >= int(thresholds["minimum_calibration_locations"])
        )
        slots.append(
            {
                "model_id": str(model_id),
                "base_seed": int(base_seed),
                "fit_intent_rows": len(fit),
                "shared_fit_eligible_rows": len(fit_eligible),
                "fit_eligibility_fraction": fraction,
                "role_rows": role_rows,
                "role_locations": role_locations,
                "authorized": passed,
            }
        )
    return {"authorized": bool(slots) and all(slot["authorized"] for slot in slots), "slots": slots}


def _counts_tables(ledger: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    count_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    location_rows: list[dict[str, Any]] = []
    slot_columns = ["model_id", "base_seed"]
    for raw_key, slot in ledger.groupby(slot_columns, sort=True):
        model_id, seed = cast(tuple[Any, Any], raw_key)
        fit = slot["intent_to_fit"]
        count_rows.append(
            {
                "model_id": model_id,
                "base_seed": seed,
                "intent_rows": len(slot),
                "complete_case_rows": int(slot["complete_case_eligible"].sum()),
                "fit_intent_rows": int(fit.sum()),
                "fit_eligible_rows": int(slot["fit_eligible"].sum()),
                "shared_fit_eligible_rows": int(slot["shared_fit_eligible"].sum()),
                "fit_eligibility_fraction": float(slot.loc[fit, "fit_eligible"].mean()),
                "calibration_intent_rows": int(slot["intent_to_calibrate"].sum()),
                "calibration_eligible_rows": int(slot["calibration_eligible"].sum()),
                "shared_calibration_eligible_rows": int(slot["shared_calibration_eligible"].sum()),
                "noneligible_rows": int((~slot["complete_case_eligible"]).sum()),
            }
        )
    for raw_key, group in ledger.groupby([*slot_columns, "time_role"], sort=True):
        model_id, seed, role = cast(tuple[Any, Any, Any], raw_key)
        role_rows.append(
            {
                "model_id": model_id,
                "base_seed": seed,
                "time_role": role,
                "intent_rows": len(group),
                "complete_case_rows": int(group["complete_case_eligible"].sum()),
                "fit_eligible_rows": int(group["fit_eligible"].sum()),
                "shared_fit_eligible_rows": int(group["shared_fit_eligible"].sum()),
                "calibration_eligible_rows": int(group["calibration_eligible"].sum()),
                "shared_calibration_eligible_rows": int(group["shared_calibration_eligible"].sum()),
                "noneligible_rows": int((~group["complete_case_eligible"]).sum()),
                "locations": int(group[["source_id", "site_id"]].drop_duplicates().shape[0]),
                "eligible_locations": int(
                    group.loc[group["complete_case_eligible"], ["source_id", "site_id"]].drop_duplicates().shape[0]
                ),
            }
        )
    for raw_key, group in ledger.groupby([*slot_columns, "time_role", "source_id", "site_id"], sort=True):
        model_id, seed, role, source_id, site_id = cast(tuple[Any, Any, Any, Any, Any], raw_key)
        location_rows.append(
            {
                "model_id": model_id,
                "base_seed": seed,
                "time_role": role,
                "source_id": source_id,
                "site_id": site_id,
                "intent_rows": len(group),
                "complete_case_rows": int(group["complete_case_eligible"].sum()),
                "noneligible_rows": int((~group["complete_case_eligible"]).sum()),
                "noneligible_fraction": float((~group["complete_case_eligible"]).mean()),
            }
        )
    return pd.DataFrame(count_rows), pd.DataFrame(role_rows), pd.DataFrame(location_rows)


def _write_parquet_exclusive(frame: pd.DataFrame, relative: Path, *, root: Path) -> None:
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise ClosureContractError(f"Refusing to overwrite Closure V2 output: {relative}")
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        table = pa.Table.from_pandas(frame, preserve_index=False)
        pq.write_table(table, temporary, compression="zstd", version="2.6", write_statistics=True)
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _write_csv_exclusive(frame: pd.DataFrame, relative: Path, *, root: Path) -> None:
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise ClosureContractError(f"Refusing to overwrite Closure V2 output: {relative}")
    content = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def write_eligibility_outputs(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    policy = validate_eligibility_policy()
    ledger, input_audit = build_eligibility_ledger(root)
    authorization = authorization_summary(ledger, policy)
    if not authorization["authorized"]:
        raise ClosureContractError("Closure V2 aggregate eligibility thresholds did not pass")
    counts, roles, locations = _counts_tables(ledger)
    _write_parquet_exclusive(ledger, LEDGER_OUTPUT, root=root)
    _write_csv_exclusive(counts, COUNTS_OUTPUT, root=root)
    _write_csv_exclusive(roles, ROLE_OUTPUT, root=root)
    _write_csv_exclusive(locations, LOCATION_OUTPUT, root=root)
    return {
        "status": "eligibility_ledger_written_unpublished",
        "ledger_rows": len(ledger),
        "input_artifacts": input_audit["artifact_count"],
        "authorization": authorization,
        "outputs": [
            LEDGER_OUTPUT.as_posix(),
            COUNTS_OUTPUT.as_posix(),
            ROLE_OUTPUT.as_posix(),
            LOCATION_OUTPUT.as_posix(),
        ],
        "evaluation_paths_opened": False,
        "post_2021_outcomes_opened": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ELIGIBILITY_POLICY)
    parser.add_argument("--audit-inputs", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.config != ELIGIBILITY_POLICY:
        raise ClosureContractError(f"Only the locked eligibility policy is accepted: {ELIGIBILITY_POLICY}")
    validate_eligibility_policy(args.config)
    result = audit_development_inputs() if args.audit_inputs else write_eligibility_outputs()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
