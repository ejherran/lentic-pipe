#!/usr/bin/env python
"""Run the closed, development-only E0-MCAL ANFIS learning curve.

The effective E0-MCALJ authority is always evaluated before scientific input
loading, fitting, directory creation, or publication.  The E0-MCAL learning-
curve algorithm and output dialect remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import AbstractSet, Any, Callable, Mapping, Sequence, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import yaml
from threadpoolctl import threadpool_limits

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import (  # noqa: E402
    closure_final_calibration_platt_parameter_dialect_patch as calibration,
)
from src.experiments.calibrate_closure_final_models import (  # noqa: E402
    _canonical_json_bytes,
    _csv_bytes,
    _read_named_bytes,
    stable_file_record,
)
from src.experiments import calibrate_closure_final_models as calibration_runner  # noqa: E402
from src.experiments.closure_development_guard import (  # noqa: E402
    DevelopmentGate,
    DevelopmentScanAudit,
    TimeRoleBounds,
    assert_development_frame,
    assign_point_roles,
    validate_assignment_frame,
)
from src.experiments.closure_runtime_contract import (  # noqa: E402
    anfis_module_substreams,
    configure_torch_cpu_execution_policy,
    validate_anfis_raw_projection_columns,
)
from src.experiments import (  # noqa: E402
    closure_anfis_ablation_dvc_registration_reproducibility_patch as family_registration,
)
from src.experiments.fit_closure_anfis_state import (  # noqa: E402
    PRIMARY_MODULES,
    fit_primary_module,
    join_anfis_sources,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = PROJECT_ROOT / "reports/closure_v1/07_anfis_ablation"
LEARNING_CURVE_PATH = OUTPUT_ROOT / "anfis_learning_curve.csv"
MANIFEST_PATH = OUTPUT_ROOT / "anfis_learning_curve_manifest.json"
OUTPUT_PATHS = (LEARNING_CURVE_PATH, MANIFEST_PATH)
TRAINING_SIZES = (4096, 16384, 65536)
BASE_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
MODULES = PRIMARY_MODULES
SLOT_ORDER = tuple(
    (training_size, base_seed)
    for training_size in TRAINING_SIZES
    for base_seed in BASE_SEEDS
)
STRATUM_COLUMNS = ("holdout_group_id", "temporal_period", "expert_anchor_band")
KEY_COLUMNS = ("source_id", "site_id", "year_month")
GUARD_PATH = PROJECT_ROOT / "tmp/closure_v1_e0_mcal/anfis_learning_curve.guard"
FitSlot = Callable[..., Mapping[str, Any]]
HISTORICAL_E7_BLOCKERS = (
    (
        "configs/closure_v1/development_runtime.yaml",
        46105,
        "0b2588248ee006f7d8e8843291b6a5847201a36fed35422473c9c0aa9492b10d",
        "5970ab73eedb20f464f804a185a3057daba93ab3",
    ),
    (
        "configs/closure_v1/anfis_ablation_training_development_runtime.yaml",
        22694,
        "cf2cec52d9027db895e8859c7ffb321c831b66510132e137759e567b363f6a50",
        "94f84be4346fd4e01fd52d207b932e21022fc436",
    ),
    (
        "configs/closure_v1/anfis_ablation_sequence_development_runtime.yaml",
        21827,
        "49d1a3f562f2cd68ff65f29c92ac4e028b3ad407f30a9960ea0d29260df7d56b",
        "f9956fb51a8b0a742831c3400cc9624f4369fe90",
    ),
)


class LearningCurveResourceError(calibration.FinalCalibrationError):
    """A measured per-slot resource/eligibility limit, never a code error."""

    def __init__(self, message: str, *, eligible_rows: int = 0) -> None:
        super().__init__(message)
        self.eligible_rows = eligible_rows


def _error(message: str) -> calibration.FinalCalibrationError:
    return calibration.FinalCalibrationError(message)


def _slot_rank(
    key: tuple[str, str, str], *, module: str, base_seed: int, training_size: int
) -> str:
    payload = json.dumps(
        ["E0-MCAL", "E7", module, base_seed, training_size, *key],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _exact_text(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns or frame[column].isna().any():
        raise _error(f"E7 sampling column is absent or null: {column}")
    values = frame[column]
    if not all(type(value) is str and value != "" for value in values.tolist()):
        raise _error(f"E7 sampling column must contain exact nonempty strings: {column}")
    return values.astype(str)


def _stratified_quotas(counts: pd.Series, training_size: int) -> dict[tuple[str, str, str], int]:
    total = int(counts.sum())
    if total < training_size:
        raise LearningCurveResourceError(
            f"E7 candidate universe has {total} rows; {training_size} are required",
            eligible_rows=total,
        )
    exact = counts.astype(float) * float(training_size) / float(total)
    quotas = exact.astype(int)
    remaining = training_size - int(quotas.sum())
    priority = sorted(
        counts.index.tolist(),
        key=lambda key: (-(float(exact.loc[key]) - int(quotas.loc[key])), key),
    )
    for key in priority:
        if remaining == 0:
            break
        if int(quotas.loc[key]) < int(counts.loc[key]):
            quotas.loc[key] += 1
            remaining -= 1
    if remaining != 0:
        raise _error("E7 stratified allocation could not satisfy the exact size")
    return {tuple(key): int(quotas.loc[key]) for key in counts.index}


def select_learning_curve_sample(
    rows: pd.DataFrame,
    *,
    module: str,
    base_seed: int,
    training_size: int,
    development_keys: AbstractSet[tuple[str, str]] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Select one deterministic, order-invariant, exact stratified E7 sample."""
    if module not in PRIMARY_MODULES:
        raise _error(f"E7 module is not registered: {module!r}")
    if type(base_seed) is not int or base_seed not in BASE_SEEDS:
        raise _error(f"E7 base seed is not registered: {base_seed!r}")
    if type(training_size) is not int or training_size not in TRAINING_SIZES:
        raise _error(f"E7 training size is not registered: {training_size!r}")
    frame = rows.copy()
    production = set((*KEY_COLUMNS, "assignment_role", "time_role")).issubset(
        frame.columns
    )
    if production:
        for column in (*KEY_COLUMNS, "assignment_role", "time_role"):
            frame[column] = _exact_text(frame, column)
        if (
            not frame["source_id"].eq("wqp").all()
            or not frame["assignment_role"].eq("development").all()
            or not frame["time_role"].eq("training").all()
            or not frame["year_month"].le("2018-12").all()
        ):
            raise _error("E7 sampling frame crosses its WQP development/training boundary")
        identity_columns = list(KEY_COLUMNS)
        # The published production surface exposes the exact module features
        # and target names used by the original sampler.  Synthetic unit
        # fixtures deliberately omit them and use the already-derived strata.
        from src.experiments.closure_runtime_contract import (
            EXPECTED_ANFIS_MODULE_FEATURES,
            EXPECTED_ANFIS_MODULE_TARGETS,
        )

        feature_columns = tuple(EXPECTED_ANFIS_MODULE_FEATURES[module])
        target_column = EXPECTED_ANFIS_MODULE_TARGETS[module]
        if not set((*feature_columns, target_column)).issubset(frame.columns):
            raise _error("E7 production surface lacks module eligibility columns")
        target = pd.to_numeric(frame[target_column], errors="coerce")
        features = frame.loc[:, list(feature_columns)].apply(pd.to_numeric, errors="coerce")
        invalid_target = target.notna() & ~target.between(0.0, 1.0)
        invalid_features = (features.notna() & ~features.apply(lambda column: column.between(0.0, 1.0))).any(axis=1)
        if bool(invalid_target.any()) or bool(invalid_features.any()):
            raise _error("E7 module target/features leave [0, 1]")
        eligible = target.notna() & features.isna().mean(axis=1).le(0.5)
        frame = frame.loc[eligible].copy()
        frame["holdout_group_id"] = frame["source_id"] + "::" + frame["site_id"]
        months = sorted(frame["year_month"].unique().tolist())
        if not months:
            raise LearningCurveResourceError("E7 eligible module universe is empty")
        labels = ("early", "middle", "late")
        month_period_map = {
            month: labels[min(2, (3 * index) // len(months))]
            for index, month in enumerate(months)
        }
        frame["temporal_period"] = frame["year_month"].map(month_period_map)
        values = pd.to_numeric(frame[target_column], errors="raise")
        frame["expert_anchor_band"] = np.select(
            [values < (1.0 / 3.0), values < (2.0 / 3.0)],
            ["low", "middle"],
            default="high",
        )
    else:
        raise _error(
            "E7 caller-supplied strata are forbidden; production eligibility columns are required"
        )
    if frame.duplicated(identity_columns).any():
        raise _error("E7 sampling keys must be unique")
    if development_keys is not None and any(
        (source, site) not in development_keys
        for source, site in frame.loc[:, ["source_id", "site_id"]].itertuples(
            index=False, name=None
        )
    ):
        raise _error("E7 sampling frame contains a non-development location")

    counts = frame.groupby(list(STRATUM_COLUMNS), sort=True).size()
    quotas = _stratified_quotas(counts, training_size)
    selected_parts: list[pd.DataFrame] = []
    stratum_records: list[dict[str, Any]] = []
    for stratum in sorted(quotas):
        mask = np.logical_and.reduce(
            [frame[column].eq(value).to_numpy() for column, value in zip(STRATUM_COLUMNS, stratum, strict=True)]
        )
        subset = frame.loc[mask].copy()
        rank_keys = [
            (
                str(row["source_id"]),
                str(row["site_id"]),
                str(row["year_month"] if production else row["row_id"]),
            )
            for row in subset.to_dict(orient="records")
        ]
        subset["rank_sha256"] = [
            _slot_rank(
                key,
                module=module,
                base_seed=base_seed,
                training_size=training_size,
            )
            for key in rank_keys
        ]
        subset = subset.sort_values(
            ["rank_sha256", *identity_columns], kind="mergesort"
        ).head(quotas[stratum])
        selected_parts.append(subset)
        stratum_records.append(
            {
                **dict(zip(STRATUM_COLUMNS, stratum, strict=True)),
                "eligible_rows": int(mask.sum()),
                "selected_rows": len(subset),
            }
        )
    selected = pd.concat(selected_parts, ignore_index=True).sort_values(
        ["rank_sha256", *identity_columns], kind="mergesort"
    ).reset_index(drop=True)
    if len(selected) != training_size:
        raise _error("E7 stratified sample cardinality drifted")
    digest = hashlib.sha256()
    for key in selected.loc[:, identity_columns].itertuples(index=False, name=None):
        digest.update(json.dumps(list(key), separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    eligible_digest = hashlib.sha256()
    for key in frame.sort_values(identity_columns, kind="mergesort").loc[
        :, identity_columns
    ].itertuples(index=False, name=None):
        eligible_digest.update(json.dumps(list(key), separators=(",", ":")).encode("utf-8"))
        eligible_digest.update(b"\n")
    strata_payload = _canonical_json_bytes({"records": stratum_records})
    month_payload = _canonical_json_bytes(
        {"month_period_map": dict(sorted(month_period_map.items()))}
    )
    return selected, {
        "module": module,
        "base_seed": base_seed,
        "training_size": training_size,
        "input_rows": len(frame),
        "eligible_rows": len(frame),
        "eligible_universe_rows": len(frame),
        "eligible_universe_sha256": eligible_digest.hexdigest(),
        "selected_rows": len(selected),
        "selected_row_count": len(selected),
        "selected_keys_sha256": digest.hexdigest(),
        "sampling_strata": list(STRATUM_COLUMNS),
        "stratum_count": len(stratum_records),
        "strata": stratum_records,
        "strata_sha256": hashlib.sha256(strata_payload).hexdigest(),
        "strata_derivation": {
            "holdout_group_rule": "source_id::site_id",
            "month_period_map": dict(sorted(month_period_map.items())),
            "month_period_map_sha256": hashlib.sha256(month_payload).hexdigest(),
            "expert_anchor_band_cuts": [0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0],
            "expert_anchor_band_labels": ["low", "middle", "high"],
        },
        "month_period_map": dict(sorted(month_period_map.items())),
        "month_period_map_sha256": hashlib.sha256(month_payload).hexdigest(),
        "replacement": False,
        "replacement_used": False,
    }


def _default_fit_slot(
    surface: pd.DataFrame,
    *,
    runtime: Mapping[str, Any],
    gate: Any,
    module: str,
    base_seed: int,
    prepared_sample: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]],
) -> Mapping[str, Any]:
    module_seed = int(anfis_module_substreams(base_seed)[module])
    result = fit_primary_module(
        surface,
        runtime=runtime,
        gate=gate,
        module=module,
        module_seed=module_seed,
        prepared_sample=prepared_sample,
    )
    return result.metrics


def run_learning_curve(
    surface: pd.DataFrame,
    *,
    runtime: Mapping[str, Any],
    gate: Any,
    fit_slot: FitSlot | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Terminalize exactly 15 slots; completed slots contain all three modules."""
    fitter = fit_slot or _default_fit_slot
    rows: list[dict[str, Any]] = []
    sample_evidence: list[dict[str, Any]] = []
    development_keys = getattr(gate, "development_keys", None)
    if development_keys is None:
        development_keys = {
            (str(source), str(site))
            for source, site in surface.loc[:, ["source_id", "site_id"]].itertuples(
                index=False, name=None
            )
        }
    for training_size, base_seed in SLOT_ORDER:
        prepared: dict[str, tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]] = {}
        failures: list[str] = []
        substreams = anfis_module_substreams(base_seed)
        for module in PRIMARY_MODULES:
            try:
                selected, audit = select_learning_curve_sample(
                    surface,
                    module=module,
                    base_seed=base_seed,
                    training_size=training_size,
                    development_keys=development_keys,
                )
            except LearningCurveResourceError as exc:
                failures.append(f"{module}: {exc}")
                match = re.search(r"universe has ([0-9]+) rows", str(exc))
                eligible_rows = (
                    exc.eligible_rows
                    if exc.eligible_rows > 0
                    else int(match.group(1)) if match is not None else 0
                )
                sample_evidence.append(
                    {
                        "module": module,
                        "base_seed": base_seed,
                        "training_size": training_size,
                        "status": "resource_failure_recorded",
                        "reason": str(exc),
                        "eligible_rows": eligible_rows,
                    }
                )
                continue
            key_columns = [
                column
                for column in (*KEY_COLUMNS, "row_id", "rank_sha256")
                if column in selected.columns
            ]
            sample_keys = selected.loc[:, key_columns].copy()
            sample_keys["module"] = module
            sample_keys["module_seed"] = int(substreams[module])
            fit_audit = {
                **audit,
                "module_seed": int(substreams[module]),
                "selected_keys_sha256": audit["selected_keys_sha256"],
            }
            prepared[module] = (selected, sample_keys, fit_audit)
            sample_evidence.append(fit_audit)
        if failures:
            rows.append(
                {
                    "training_rows_per_module": training_size,
                    "base_seed": base_seed,
                    "status": "resource_failure_recorded",
                    "completed_module_fit_count": 0,
                    "resource_limitation": " | ".join(failures),
                    "resource_failure_timing": "pre_fit_exact_eligibility_check",
                    "downstream_metrics_status": "not_estimable_without_separate_temporal_consumers",
                    "saturation_claim_authorized": False,
                }
            )
            continue
        module_metrics: dict[str, Mapping[str, Any]] = {}
        for module in PRIMARY_MODULES:
            module_metrics[module] = fitter(
                surface,
                runtime=runtime,
                gate=gate,
                module=module,
                base_seed=base_seed,
                prepared_sample=prepared[module],
            )
        failed = [
            module
            for module, metrics in module_metrics.items()
            if metrics.get("status") not in {"passed", "completed"}
        ]
        if failed:
            raise _error(
                "E7 module scientific quality gate failed: " + ", ".join(failed)
            )
        row: dict[str, Any] = {
            "training_rows_per_module": training_size,
            "base_seed": base_seed,
            "status": "completed",
            "completed_module_fit_count": 3,
            "resource_limitation": "",
            "resource_failure_timing": "",
            "downstream_metrics_status": "not_estimable_without_separate_temporal_consumers",
            "saturation_claim_authorized": False,
        }
        for module in PRIMARY_MODULES:
            token = module.lower().replace("-", "_")
            metrics = module_metrics[module]
            audit = prepared[module][2]
            for field in (
                "final_checkpoint_loss",
                "rule_count",
                "epochs",
                "quality_gate_output_standard_deviation",
                "maximum_parameter_delta",
                "centers_ordered",
                "centers_in_unit_interval",
            ):
                row[f"{token}_{field}"] = metrics.get(field)
            row[f"{token}_selected_keys_sha256"] = audit.get(
                "selected_keys_sha256"
            )
            rule_count = metrics.get("rule_count")
            epochs = metrics.get("epochs")
            row[f"{token}_computational_cost_proxy"] = (
                training_size * int(rule_count) * int(epochs)
                if type(rule_count) is int and type(epochs) is int
                else None
            )
            row[f"{token}_quality_gate_output_scope"] = (
                f"e7_stratified_training_sample_{training_size}"
            )
        rows.append(row)
    curve = pd.DataFrame(rows)
    observed = list(
        curve.loc[:, ["training_rows_per_module", "base_seed"]].itertuples(
            index=False, name=None
        )
    )
    if observed != list(SLOT_ORDER) or len(curve) != 15:
        raise _error("E7 terminal slot order/cardinality drifted")
    completed_slots = int(curve["status"].eq("completed").sum())
    resource_slots = int(curve["status"].eq("resource_failure_recorded").sum())
    result = {
        "experiment_id": "E7",
        "terminal_row_count": 15,
        "completed_slot_count": completed_slots,
        "resource_failure_count": resource_slots,
        "completed_module_fit_count": completed_slots * 3,
        "new_e7_fit_count": completed_slots * 3,
        "primary_fit_reuse_count": 0,
        "sample_evidence": sample_evidence,
        "silent_omission": False,
        "post_hoc_substitution_performed": False,
        "saturation_claim_authorized": False,
    }
    contract = runtime.get("e0_mcal_e7_terminal_record", runtime.get("e7_terminal_record"))
    if isinstance(contract, Mapping) and "eligible_rows_by_module" in contract:
        expected_eligible = {
            "ANFIS-N": 4757,
            "ANFIS-F": 35273,
            "ANFIS-T-no-current": 35419,
        }
        if len(sample_evidence) != 45:
            raise _error("E7 did not retain all 45 module preflight records")
        for record in sample_evidence:
            if record.get("eligible_rows") != expected_eligible.get(str(record.get("module"))):
                raise _error("E7 measured module eligibility differs from authority")
        if (completed_slots, resource_slots) != (5, 10):
            raise _error("E7 terminal completion/resource counts differ from authority")
        result["saturation_claim_authorized"] = False
    return curve, result


def _validate_sample_evidence(value: Any) -> list[dict[str, Any]]:
    """Validate all 45 measured module preflights in their canonical order."""

    if not isinstance(value, list) or len(value) != 45:
        raise _error("E7 terminal evidence lacks exact 45 module preflights")
    eligible = {
        "ANFIS-N": 4757,
        "ANFIS-F": 35273,
        "ANFIS-T-no-current": 35419,
    }
    expected_order = [
        (size, seed, module)
        for size, seed in SLOT_ORDER
        for module in PRIMARY_MODULES
    ]
    success_keys = {
        "module",
        "base_seed",
        "training_size",
        "input_rows",
        "eligible_rows",
        "eligible_universe_rows",
        "eligible_universe_sha256",
        "selected_rows",
        "selected_row_count",
        "selected_keys_sha256",
        "sampling_strata",
        "stratum_count",
        "strata",
        "strata_sha256",
        "strata_derivation",
        "month_period_map",
        "month_period_map_sha256",
        "replacement",
        "replacement_used",
        "module_seed",
    }
    resource_keys = {
        "module",
        "base_seed",
        "training_size",
        "status",
        "reason",
        "eligible_rows",
    }
    observed_order: list[tuple[int, int, str]] = []
    validated: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise _error("E7 sample evidence is malformed")
        record = dict(raw)
        size = record.get("training_size")
        seed = record.get("base_seed")
        module = record.get("module")
        if (
            type(size) is not int
            or type(seed) is not int
            or seed not in BASE_SEEDS
            or not isinstance(module, str)
            or module not in PRIMARY_MODULES
            or record.get("eligible_rows") != eligible[module]
        ):
            raise _error("E7 sample evidence identity drifted")
        observed_order.append((size, seed, module))
        expected_eligible = eligible[module]
        if size <= expected_eligible:
            if (
                set(record) != success_keys
                or record.get("input_rows") != expected_eligible
                or record.get("eligible_universe_rows") != expected_eligible
                or re.fullmatch(
                    r"[0-9a-f]{64}", str(record.get("eligible_universe_sha256"))
                )
                is None
                or record.get("selected_rows") != size
                or record.get("selected_row_count") != size
                or re.fullmatch(
                    r"[0-9a-f]{64}", str(record.get("selected_keys_sha256"))
                )
                is None
                or record.get("replacement") is not False
                or record.get("replacement_used") is not False
                or record.get("sampling_strata") != list(STRATUM_COLUMNS)
                or record.get("module_seed")
                != int(anfis_module_substreams(seed)[module])
            ):
                raise _error("E7 selected sample evidence drifted")
            strata = record.get("strata")
            stratum_count = record.get("stratum_count")
            if (
                not isinstance(strata, list)
                or type(stratum_count) is not int
                or stratum_count <= 0
                or len(strata) != stratum_count
            ):
                raise _error("E7 stratum record cardinality drifted")
            previous: tuple[str, str, str] | None = None
            eligible_sum = 0
            selected_sum = 0
            for raw_stratum in strata:
                if not isinstance(raw_stratum, Mapping) or set(raw_stratum) != {
                    *STRATUM_COLUMNS,
                    "eligible_rows",
                    "selected_rows",
                }:
                    raise _error("E7 stratum evidence dialect drifted")
                group = raw_stratum.get("holdout_group_id")
                period = raw_stratum.get("temporal_period")
                band = raw_stratum.get("expert_anchor_band")
                eligible_rows = raw_stratum.get("eligible_rows")
                selected_rows = raw_stratum.get("selected_rows")
                if (
                    not isinstance(group, str)
                    or not group.startswith("wqp::")
                    or group == "wqp::"
                    or period not in {"early", "middle", "late"}
                    or band not in {"low", "middle", "high"}
                    or type(eligible_rows) is not int
                    or type(selected_rows) is not int
                    or eligible_rows <= 0
                    or selected_rows < 0
                    or selected_rows > eligible_rows
                ):
                    raise _error("E7 stratum evidence semantics drifted")
                key = (group, cast(str, period), cast(str, band))
                if previous is not None and key <= previous:
                    raise _error("E7 stratum evidence order drifted")
                previous = key
                eligible_sum += eligible_rows
                selected_sum += selected_rows
            expected_strata_sha256 = hashlib.sha256(
                _canonical_json_bytes({"records": strata})
            ).hexdigest()
            if (
                eligible_sum != expected_eligible
                or selected_sum != size
                or record.get("strata_sha256") != expected_strata_sha256
            ):
                raise _error("E7 stratum evidence digest drifted")

            month_map = record.get("month_period_map")
            derivation = record.get("strata_derivation")
            if (
                not isinstance(month_map, Mapping)
                or not month_map
                or list(month_map) != sorted(month_map)
                or not isinstance(derivation, Mapping)
                or set(derivation)
                != {
                    "holdout_group_rule",
                    "month_period_map",
                    "month_period_map_sha256",
                    "expert_anchor_band_cuts",
                    "expert_anchor_band_labels",
                }
                or derivation.get("holdout_group_rule") != "source_id::site_id"
                or derivation.get("month_period_map") != month_map
                or derivation.get("expert_anchor_band_cuts")
                != [0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0]
                or derivation.get("expert_anchor_band_labels")
                != ["low", "middle", "high"]
            ):
                raise _error("E7 strata derivation evidence drifted")
            months = list(month_map)
            if any(
                not isinstance(month, str)
                or re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month) is None
                for month in months
            ):
                raise _error("E7 month-period evidence key drifted")
            month_names = cast(list[str], months)
            expected_periods = {
                month: ("early", "middle", "late")[
                    min(2, (3 * index) // len(month_names))
                ]
                for index, month in enumerate(month_names)
            }
            month_sha256 = hashlib.sha256(
                _canonical_json_bytes({"month_period_map": expected_periods})
            ).hexdigest()
            if (
                dict(month_map) != expected_periods
                or record.get("month_period_map_sha256") != month_sha256
                or derivation.get("month_period_map_sha256") != month_sha256
            ):
                raise _error("E7 month-period evidence digest drifted")
        elif (
            set(record) != resource_keys
            or record.get("status") != "resource_failure_recorded"
            or record.get("reason")
            != (
                f"E7 candidate universe has {expected_eligible} rows; "
                f"{size} are required"
            )
        ):
            raise _error("E7 pre-fit resource evidence drifted")
        validated.append(record)
    if observed_order != expected_order:
        raise _error("E7 module preflight evidence order drifted")
    return validated


def _validate_e7_execution_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "torch_cpu_execution_policy",
        "threadpool_limit",
    }:
        raise _error("E7 execution policy dialect drifted")
    expected_torch = {
        "device": "cpu",
        "torch_num_threads": 1,
        "torch_num_interop_threads": 1,
        "blas_thread_environment_control": "not_locked_by_e0_dl_v1",
        "bitwise_reproducibility_claim": (
            "forbidden_across_processes_or_blas_backends"
        ),
        "torch_num_threads_observed": 1,
        "torch_num_interop_threads_observed": 1,
    }
    if value.get("threadpool_limit") != 1 or value.get(
        "torch_cpu_execution_policy"
    ) != expected_torch:
        raise _error("E7 execution policy drifted")
    return dict(value)


def build_anfis_learning_curve_bundle(
    *,
    authority: Mapping[str, Any],
    curve: pd.DataFrame,
    evidence: Mapping[str, Any],
    input_records: Sequence[Mapping[str, Any]] = (),
    repo_root: Path = PROJECT_ROOT,
) -> tuple[list[tuple[Path, bytes]], dict[str, Any]]:
    expected_inputs = _e7_required_input_partition(authority)
    if [dict(record) for record in input_records] != expected_inputs:
        raise _error("E7 bundle inputs differ from the exact P authority partition")
    module_fields = (
        "final_checkpoint_loss",
        "rule_count",
        "epochs",
        "quality_gate_output_standard_deviation",
        "maximum_parameter_delta",
        "centers_ordered",
        "centers_in_unit_interval",
        "selected_keys_sha256",
        "computational_cost_proxy",
        "quality_gate_output_scope",
    )
    module_columns = tuple(
        f"{module.lower().replace('-', '_')}_{field}"
        for module in PRIMARY_MODULES
        for field in module_fields
    )
    expected_columns = [
        "training_rows_per_module",
        "base_seed",
        "status",
        "completed_module_fit_count",
        "resource_limitation",
        "resource_failure_timing",
        "downstream_metrics_status",
        "saturation_claim_authorized",
        *module_columns,
    ]
    if list(curve.columns) != expected_columns:
        raise _error("E7 learning-curve column dialect drifted")
    expected = list(SLOT_ORDER)
    observed = list(
        curve.loc[:, ["training_rows_per_module", "base_seed"]].itertuples(
            index=False, name=None
        )
    )
    statuses = set(curve["status"].astype(str)) if "status" in curve else set()
    expected_statuses = ["completed"] * 5 + ["resource_failure_recorded"] * 10
    if (
        observed != expected
        or statuses != {"completed", "resource_failure_recorded"}
        or curve["status"].astype(str).tolist() != expected_statuses
    ):
        raise _error("E7 bundle lacks the exact canonical terminal slots")
    for row, (size, seed) in zip(
        curve.to_dict(orient="records"), SLOT_ORDER, strict=True
    ):
        completed = size == 4096
        if (
            type(row.get("training_rows_per_module")) is not int
            or row.get("training_rows_per_module") != size
            or type(row.get("base_seed")) is not int
            or row.get("base_seed") != seed
            or row.get("status")
            != ("completed" if completed else "resource_failure_recorded")
            or type(row.get("completed_module_fit_count")) is not int
            or row.get("completed_module_fit_count") != (3 if completed else 0)
            or row.get("downstream_metrics_status")
            != "not_estimable_without_separate_temporal_consumers"
            or row.get("saturation_claim_authorized") is not False
        ):
            raise _error("E7 terminal row identity/status drifted")
        if completed:
            if row.get("resource_limitation") != "" or row.get(
                "resource_failure_timing"
            ) != "":
                raise _error("E7 completed row carries a resource limitation")
            for module in PRIMARY_MODULES:
                token = module.lower().replace("-", "_")
                loss = row.get(f"{token}_final_checkpoint_loss")
                rules = row.get(f"{token}_rule_count")
                epochs = row.get(f"{token}_epochs")
                deviation = row.get(
                    f"{token}_quality_gate_output_standard_deviation"
                )
                delta = row.get(f"{token}_maximum_parameter_delta")
                cost = row.get(f"{token}_computational_cost_proxy")
                rules_is_integer = (
                    not isinstance(rules, (bool, np.bool_))
                    and isinstance(rules, (int, float, np.integer, np.floating))
                    and np.isfinite(rules)
                    and float(rules).is_integer()
                    and int(rules) > 0
                )
                epochs_is_integer = (
                    not isinstance(epochs, (bool, np.bool_))
                    and isinstance(epochs, (int, float, np.integer, np.floating))
                    and np.isfinite(epochs)
                    and float(epochs).is_integer()
                    and int(epochs) > 0
                )
                cost_is_integer = (
                    not isinstance(cost, (bool, np.bool_))
                    and isinstance(cost, (int, float, np.integer, np.floating))
                    and np.isfinite(cost)
                    and float(cost).is_integer()
                    and int(cost) > 0
                )
                if (
                    isinstance(loss, (bool, np.bool_))
                    or not isinstance(loss, (int, float, np.integer, np.floating))
                    or not np.isfinite(loss)
                    or float(loss) < 0.0
                    or not rules_is_integer
                    or not epochs_is_integer
                    or isinstance(deviation, (bool, np.bool_))
                    or not isinstance(
                        deviation, (int, float, np.integer, np.floating)
                    )
                    or not np.isfinite(deviation)
                    or float(deviation) < 0.0
                    or isinstance(delta, (bool, np.bool_))
                    or not isinstance(delta, (int, float, np.integer, np.floating))
                    or not np.isfinite(delta)
                    or float(delta) < 0.0
                    or row.get(f"{token}_centers_ordered") is not True
                    or row.get(f"{token}_centers_in_unit_interval") is not True
                    or not isinstance(
                        row.get(f"{token}_selected_keys_sha256"), str
                    )
                    or re.fullmatch(
                        r"[0-9a-f]{64}",
                        cast(str, row[f"{token}_selected_keys_sha256"]),
                    )
                    is None
                    or not cost_is_integer
                    or int(cast(float | int, cost))
                    != size
                    * int(cast(float | int, rules))
                    * int(cast(float | int, epochs))
                    or row.get(f"{token}_quality_gate_output_scope")
                    != f"e7_stratified_training_sample_{size}"
                ):
                    raise _error(f"E7 completed module evidence drifted: {module}")
        elif (
            not isinstance(row.get("resource_limitation"), str)
            or not cast(str, row["resource_limitation"])
            or row.get("resource_failure_timing")
            != "pre_fit_exact_eligibility_check"
            or any(not pd.isna(row.get(column)) for column in module_columns)
        ):
            raise _error("E7 resource-limited row evidence drifted")
    completed_slots = int(curve["status"].eq("completed").sum())
    resource_slots = int(curve["status"].eq("resource_failure_recorded").sum())
    expected_evidence = {
        "terminal_row_count": 15,
        "completed_slot_count": completed_slots,
        "resource_failure_count": resource_slots,
        "completed_module_fit_count": completed_slots * 3,
        "new_e7_fit_count": 15,
        "primary_fit_reuse_count": 0,
        "primary_slots_untouched": True,
        "saturation_claim_authorized": False,
        "post_hoc_substitution_performed": False,
        "silent_omission": False,
    }
    for key, value in expected_evidence.items():
        if evidence.get(key) != value:
            raise _error(f"E7 terminal evidence drifted: {key}")
    for forbidden_alias in (
        "terminal_record_count",
        "completed_record_count",
        "resource_failure_record_count",
        "post_hoc_substitution",
    ):
        if forbidden_alias in evidence:
            raise _error(f"E7 legacy evidence alias is forbidden: {forbidden_alias}")
    expected_evidence_keys = {
        "experiment_id",
        *expected_evidence,
        "sample_evidence",
        "execution_policy",
    }
    if set(evidence) != expected_evidence_keys or evidence.get("experiment_id") != "E7":
        raise _error("E7 terminal evidence dialect drifted")
    sample_evidence = _validate_sample_evidence(evidence.get("sample_evidence"))
    execution_policy = _validate_e7_execution_policy(evidence.get("execution_policy"))
    csv_payload = _csv_bytes(curve)
    curve_record = {
        "path": LEARNING_CURVE_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "bytes": len(csv_payload),
        "sha256": hashlib.sha256(csv_payload).hexdigest(),
    }
    authority_sha256 = authority.get("authority_binding_sha256")
    if (
        not isinstance(authority_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", authority_sha256) is None
    ):
        raise _error("E7 effective authority binding digest is absent")
    manifest = {
        "schema_version": "closure_anfis_learning_curve_manifest_v1",
        "experiment_id": "E7",
        "gate": calibration.PATCH_GATE,
        "status": "terminal",
        "authority_sha256": authority_sha256,
        **expected_evidence,
        "slot_order": [
            {"training_rows_per_module": size, "base_seed": seed}
            for size, seed in SLOT_ORDER
        ],
        "terminal_evidence": {
            **dict(evidence),
            "sample_evidence": sample_evidence,
            "execution_policy": execution_policy,
        },
        "inputs": [dict(record) for record in input_records],
        "outputs": [curve_record],
        "scientific_boundary": {
            "development_only": True,
            "holdout_accessed": False,
            "post_2021_rows_accessed": False,
            "final_evaluation_run": False,
            "future_outcomes_accessed": False,
        },
    }
    manifest_payload = _canonical_json_bytes(manifest)
    return [
        (repo_root / curve_record["path"], csv_payload),
        (
            repo_root / MANIFEST_PATH.relative_to(PROJECT_ROOT),
            manifest_payload,
        ),
    ], manifest


def _git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()  # noqa: S324 - Git object identity


def validate_historical_e7_blockers(
    *, repo_root: Path = PROJECT_ROOT
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    payloads: list[Mapping[str, Any]] = []
    for relative, expected_bytes, expected_sha256, expected_oid in HISTORICAL_E7_BLOCKERS:
        path = repo_root / relative
        payload, identity = _read_named_bytes(path, repo_root=repo_root)
        if (
            len(payload) != expected_bytes
            or hashlib.sha256(payload).hexdigest() != expected_sha256
            or _git_blob_oid(payload) != expected_oid
            or identity.mode != 0o644
            or identity.nlink != 1
        ):
            raise _error(f"E7 historical blocker binding drifted: {relative}")
        parsed = yaml.safe_load(payload)
        if not isinstance(parsed, Mapping):
            raise _error(f"E7 historical blocker is not one mapping: {relative}")
        payloads.append(parsed)
        records.append(
            {
                "role": "historical_e7_blocker",
                "path": relative,
                "bytes": expected_bytes,
                "sha256": expected_sha256,
                "git_oid": expected_oid,
                "git_mode": "100644",
            }
        )
    development, training, sequence = payloads
    if (
        development.get("anfis", {})
        .get("e7_training_size_sensitivity", {})
        .get("status")
        != "blocked_pending_sampling_strata_contract"
        or training.get("seals", {}).get("e7_learning_curve_status")
        != "blocked_for_separate_gate"
        or sequence.get("seals", {}).get("e7_learning_curve_status")
        != "blocked_for_separate_gate"
        or sequence.get("seals", {}).get("e7_learning_curve_sizes_authorized")
        is not False
    ):
        raise _error("E7 historical blocker semantics drifted")
    return records


def _pinned_json(
    pinned: "_PinnedE7Inputs", path: str
) -> Mapping[str, Any]:
    return calibration_runner._load_unique_json_mapping(
        pinned.payload(path), path=Path(path)
    )


def _pinned_development_gate(pinned: "_PinnedE7Inputs") -> DevelopmentGate:
    assignment_path = "data/closure_v1/closure_holdout_assignment.csv"
    manifest_path = "reports/closure_v1/00_protocol/holdout_manifest.json"
    protocol_path = "reports/closure_v1/00_protocol/protocol_lock.json"
    plan_path = "configs/closure_v1/analysis_plan.yaml"
    assignment_payload = pinned.payload(assignment_path)
    manifest_payload = pinned.payload(manifest_path)
    protocol_payload = pinned.payload(protocol_path)
    plan_payload = pinned.payload(plan_path)
    manifest = _pinned_json(pinned, manifest_path)
    protocol = _pinned_json(pinned, protocol_path)
    if (
        manifest.get("status") != "completed"
        or manifest.get("experiment_id") != "closure_v1"
        or manifest.get("future_outcomes_accessed") is not False
        or protocol.get("status") != "locked"
        or protocol.get("experiment_id") != "closure_v1"
        or protocol.get("future_outcomes_accessed") is not False
        or protocol.get("holdout_assignment_created") is not False
    ):
        raise _error("E7 pinned development-gate semantics drifted")
    counts = manifest.get("counts")
    outputs = manifest.get("outputs")
    protocol_record = manifest.get("protocol_lock")
    locked_repository = protocol.get("locked_repository")
    if (
        not isinstance(counts, Mapping)
        or not isinstance(outputs, list)
        or not isinstance(protocol_record, Mapping)
        or not isinstance(locked_repository, Mapping)
    ):
        raise _error("E7 pinned development-gate records are malformed")
    assignment_records = [
        record
        for record in outputs
        if isinstance(record, Mapping) and record.get("path") == assignment_path
    ]
    locked_head = locked_repository.get("head")
    if (
        len(assignment_records) != 1
        or assignment_records[0].get("bytes") != len(assignment_payload)
        or assignment_records[0].get("sha256")
        != hashlib.sha256(assignment_payload).hexdigest()
        or protocol_record.get("path") != protocol_path
        or protocol_record.get("sha256")
        != hashlib.sha256(protocol_payload).hexdigest()
        or protocol_record.get("locked_repository_head") != locked_head
        or not isinstance(locked_head, str)
        or re.fullmatch(r"[0-9a-f]{40,64}", locked_head) is None
    ):
        raise _error("E7 pinned development-gate bindings drifted")
    try:
        assignment = validate_assignment_frame(
            pd.read_csv(io.BytesIO(assignment_payload)), expected_counts=counts
        )
        plan = yaml.safe_load(plan_payload)
    except Exception as exc:
        raise _error(f"E7 pinned development-gate payload cannot be decoded: {exc}") from exc
    if not isinstance(plan, Mapping) or not isinstance(plan.get("time_roles"), Mapping):
        raise _error("E7 pinned analysis-plan time roles are absent")
    roles = cast(Mapping[str, Any], plan["time_roles"])

    def role_month(role: str, field: str) -> str:
        value = roles.get(role)
        if not isinstance(value, Mapping) or not isinstance(value.get(field), str):
            raise _error(f"E7 pinned analysis-plan month is absent: {role}.{field}")
        month = cast(str, value[field])
        if re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])", month) is None:
            raise _error(f"E7 pinned analysis-plan month drifted: {role}.{field}")
        try:
            if str(pd.Period(month, freq="M")) != month:
                raise ValueError(month)
        except ValueError as exc:
            raise _error(
                f"E7 pinned analysis-plan month is not canonical: {role}.{field}"
            ) from exc
        return month

    bounds = TimeRoleBounds(
        training_end=role_month("training", "target_end"),
        model_selection_start=role_month("model_selection", "origin_start"),
        model_selection_end=role_month("model_selection", "target_end"),
        calibration_threshold_start=role_month(
            "calibration_threshold", "origin_start"
        ),
        calibration_threshold_end=role_month(
            "calibration_threshold", "target_end"
        ),
        locked_evaluation_start=role_month("locked_evaluation", "target_start"),
    )
    return DevelopmentGate(
        assignment_path=pinned.repo_root / assignment_path,
        assignment_sha256=hashlib.sha256(assignment_payload).hexdigest(),
        holdout_manifest_path=pinned.repo_root / manifest_path,
        holdout_manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        protocol_lock_path=pinned.repo_root / protocol_path,
        protocol_lock_sha256=hashlib.sha256(protocol_payload).hexdigest(),
        locked_repository_head=locked_head,
        repository_validated=False,
        bounds=bounds,
        _assignment=assignment,
    )


def _scan_pinned_development_rows(
    pinned: "_PinnedE7Inputs",
    path: str,
    gate: DevelopmentGate,
    *,
    columns: Sequence[str],
) -> tuple[pd.DataFrame, DevelopmentScanAudit]:
    requested = list(columns)
    if not requested or len(requested) != len(set(requested)):
        raise _error("E7 pinned Parquet projection is empty or duplicated")
    payload = pinned.payload(path)
    fragment = ds.ParquetFileFormat().make_fragment(pa.BufferReader(payload))
    missing = sorted(set(requested).difference(fragment.physical_schema.names))
    if missing:
        raise _error(f"E7 pinned Parquet projection is incomplete: {missing}")
    development_sites = sorted(
        site_id
        for source_id, site_id in gate.development_keys
        if source_id == "wqp"
    )
    predicate = (
        (ds.field("source_id") == "wqp")
        & ds.field("site_id").isin(development_sites)
        & (ds.field("year_month") <= gate.bounds.calibration_threshold_end)
    )
    table = fragment.scanner(columns=requested, filter=predicate).to_table()
    frame = table.to_pandas()
    if frame.empty:
        raise _error("E7 pinned development scan produced no rows")
    materialized_rows = len(frame)
    frame["source_id"] = frame["source_id"].astype(str)
    frame["site_id"] = frame["site_id"].astype(str)
    assignment = gate.assignment.loc[
        gate.assignment["assignment_role"].eq("development"),
        ["source_id", "site_id", "holdout_group_id", "assignment_role"],
    ]
    frame = frame.merge(
        assignment,
        on=["source_id", "site_id"],
        how="left",
        validate="many_to_one",
    )
    if frame["assignment_role"].isna().any():
        raise _error("E7 pinned development scan failed its assignment join")
    frame["time_role"] = assign_point_roles(
        frame, month_column="year_month", gate=gate
    )
    assert_development_frame(frame, gate, role_column="time_role")
    frame = frame.reset_index(drop=True)
    counts = frame["time_role"].value_counts()
    role_counts = tuple(
        (role, int(counts[role]))
        for role in ("training", "model_selection", "calibration_threshold")
        if role in counts.index
    )
    pinned.revalidate()
    return frame, DevelopmentScanAudit(
        materialized_rows=materialized_rows,
        returned_rows=len(frame),
        boundary_crossing_rows=0,
        _role_counts=role_counts,
    )


def _load_mcal_development_runtime_from_pinned_inputs(
    pinned: "_PinnedE7Inputs",
) -> tuple[dict[str, Any], dict[str, Any]]:
    config_path = "configs/closure_v1/development_runtime.yaml"
    schema_path = "configs/closure_v1/development_runtime.schema.json"
    config_payload = pinned.payload(config_path)
    schema_payload = pinned.payload(schema_path)
    try:
        raw_runtime = yaml.safe_load(config_payload)
        schema = calibration_runner._load_unique_json_mapping(
            schema_payload, path=Path(schema_path)
        )
    except Exception as exc:
        raise _error(f"E7 pinned development runtime cannot be decoded: {exc}") from exc
    if not isinstance(raw_runtime, Mapping):
        raise _error("E7 pinned development runtime is not one mapping")
    runtime = dict(raw_runtime)
    try:
        audit = calibration_runner.validate_development_runtime(
            runtime,
            dict(schema),
            cross_validate_locked=False,
            validate_repository=False,
        )
    except Exception as exc:
        raise _error(f"E7 pinned development runtime failed validation: {exc}") from exc
    audit.update(
        {
            "config_path": config_path,
            "config_sha256": hashlib.sha256(config_payload).hexdigest(),
            "schema_path": schema_path,
            "schema_sha256": hashlib.sha256(schema_payload).hexdigest(),
            "status": runtime.get("status"),
            "validation_scope": (
                "exact_schema_contract_under_effective_e0_mcal_authority"
            ),
        }
    )
    return runtime, audit


def _validate_pinned_historical_e7_blockers(
    pinned: "_PinnedE7Inputs",
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    payloads: list[Mapping[str, Any]] = []
    for relative, expected_bytes, expected_sha256, expected_oid in HISTORICAL_E7_BLOCKERS:
        payload = pinned.payload(relative)
        if (
            len(payload) != expected_bytes
            or hashlib.sha256(payload).hexdigest() != expected_sha256
            or _git_blob_oid(payload) != expected_oid
        ):
            raise _error(f"E7 pinned historical blocker binding drifted: {relative}")
        parsed = yaml.safe_load(payload)
        if not isinstance(parsed, Mapping):
            raise _error(f"E7 pinned historical blocker is not one mapping: {relative}")
        payloads.append(parsed)
        records.append(
            {
                "role": "historical_e7_blocker",
                "path": relative,
                "bytes": expected_bytes,
                "sha256": expected_sha256,
                "git_oid": expected_oid,
                "git_mode": "100644",
            }
        )
    development, training, sequence = payloads
    if (
        development.get("anfis", {})
        .get("e7_training_size_sensitivity", {})
        .get("status")
        != "blocked_pending_sampling_strata_contract"
        or training.get("seals", {}).get("e7_learning_curve_status")
        != "blocked_for_separate_gate"
        or sequence.get("seals", {}).get("e7_learning_curve_status")
        != "blocked_for_separate_gate"
        or sequence.get("seals", {}).get("e7_learning_curve_sizes_authorized")
        is not False
    ):
        raise _error("E7 pinned historical blocker semantics drifted")
    return records


def _pinned_learning_curve_surface(
    pinned: "_PinnedE7Inputs",
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate,
) -> pd.DataFrame:
    anfis = runtime.get("anfis")
    projection = anfis.get("source_projection") if isinstance(anfis, Mapping) else None
    if not isinstance(projection, Mapping):
        raise _error("E7 pinned ANFIS source projection is absent")
    panel_columns = tuple(str(value) for value in cast(Sequence[Any], projection.get("panel_columns")))
    anchor_columns = tuple(
        str(value) for value in cast(Sequence[Any], projection.get("expert_anchor_columns"))
    )
    validate_anfis_raw_projection_columns(panel_columns, anchor_columns)
    panel_path = "data/panel/panel_monthly_v0.parquet"
    anchor_path = "data/fuzzy/state_vector_v0.parquet"
    if (
        projection.get("panel_path") != panel_path
        or projection.get("expert_anchor_path") != anchor_path
    ):
        raise _error("E7 pinned ANFIS source paths drifted")
    panel, _ = _scan_pinned_development_rows(
        pinned, panel_path, gate, columns=panel_columns
    )
    anchor, _ = _scan_pinned_development_rows(
        pinned, anchor_path, gate, columns=anchor_columns
    )
    panel = panel.loc[:, [*panel_columns, "assignment_role", "time_role"]]
    anchor = anchor.loc[:, [*anchor_columns, "assignment_role", "time_role"]]
    training_panel = panel.loc[panel["time_role"].eq("training")].copy()
    training_anchor = anchor.loc[anchor["time_role"].eq("training")].copy()
    training, _ = join_anfis_sources(
        training_panel, training_anchor, runtime=runtime, gate=gate
    )
    if not training["time_role"].eq("training").all():
        raise _error("E7 pinned ANFIS surface contains non-training rows")
    pinned.revalidate()
    return training


def _load_learning_curve_surface(
    *, pinned_inputs: "_PinnedE7Inputs", repo_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Load the E7 surface only from descriptors retained by the P snapshot."""
    blocker_records = _validate_pinned_historical_e7_blockers(pinned_inputs)
    correction = pinned_inputs.authority.get("e7_authority_correction")
    terminal_contract = {
        "historical_e7_blocker_adopted": pinned_inputs.authority.get(
            "historical_e7_blocker_adopted"
        ),
        "supersession_scope": (
            correction.get("supersession_scope")
            if isinstance(correction, Mapping)
            else None
        ),
        "eligible_rows_by_module": {
            "ANFIS-N": 4757,
            "ANFIS-F": 35273,
            "ANFIS-T-no-current": 35419,
        },
        "expected_completed_slot_count": pinned_inputs.authority.get(
            "e7_expected_completed_slot_count"
        ),
        "expected_completed_module_fit_count": pinned_inputs.authority.get(
            "e7_expected_completed_module_fit_count"
        ),
        "expected_resource_failure_record_count": pinned_inputs.authority.get(
            "e7_expected_resource_failure_record_count"
        ),
    }
    if (
        terminal_contract["historical_e7_blocker_adopted"] is not True
        or terminal_contract["supersession_scope"]
        != "e7_only_additive_authority"
        or terminal_contract["expected_completed_slot_count"] != 5
        or terminal_contract["expected_completed_module_fit_count"] != 15
        or terminal_contract["expected_resource_failure_record_count"] != 10
    ):
        raise _error("E7 additive superseding contract is absent")
    development_runtime, runtime_audit = (
        _load_mcal_development_runtime_from_pinned_inputs(pinned_inputs)
    )
    gate = _pinned_development_gate(pinned_inputs)
    training_candidates = _pinned_learning_curve_surface(
        pinned_inputs, runtime=development_runtime, gate=gate
    )
    runtime = dict(development_runtime)
    runtime["e0_mcal_e7_terminal_record"] = dict(terminal_contract)
    return {
        "surface": training_candidates,
        "runtime": runtime,
        "gate": gate,
        "input_records": blocker_records,
        "runtime_audit": runtime_audit,
    }


def _e7_required_input_partition(
    authority: Mapping[str, Any],
) -> list[dict[str, Any]]:
    inventory = authority.get("scientific_input_inventory")
    if not isinstance(inventory, Mapping):
        raise _error("E7 scientific input inventory is absent")
    raw = inventory.get("e7_required_inputs")
    count = inventory.get("e7_required_input_count")
    expected_digest = inventory.get("e7_required_inputs_sha256")
    if (
        not isinstance(raw, list)
        or type(count) is not int
        or count != 15
        or not isinstance(expected_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_digest) is None
    ):
        raise _error("E7 scientific input partition is malformed")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in raw:
        if (
            not isinstance(value, Mapping)
            or set(value) != {"role", "path", "bytes", "sha256"}
            or not isinstance(value.get("role"), str)
            or not cast(str, value["role"])
            or not isinstance(value.get("path"), str)
            or not cast(str, value["path"])
            or cast(str, value["path"]) in seen
            or Path(cast(str, value["path"])).is_absolute()
            or ".." in Path(cast(str, value["path"])).parts
            or type(value.get("bytes")) is not int
            or cast(int, value["bytes"]) <= 0
            or not isinstance(value.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", cast(str, value["sha256"])) is None
        ):
            raise _error("E7 scientific input partition record drifted")
        record = {
            "role": cast(str, value["role"]),
            "path": cast(str, value["path"]),
            "bytes": cast(int, value["bytes"]),
            "sha256": cast(str, value["sha256"]),
        }
        seen.add(record["path"])
        records.append(record)
    if len(records) != 15 or [record["path"] for record in records] != sorted(seen):
        raise _error("E7 scientific input partition order/cardinality drifted")
    digest = hashlib.sha256(
        json.dumps(
            records,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if digest != expected_digest:
        raise _error("E7 scientific input partition digest drifted")
    return records


@dataclass(frozen=True)
class _PinnedE7Handle:
    path: str
    descriptor: int
    identity: tuple[int, int, int, int, int, int, int]
    parent_identity: tuple[int, int, int, int, int, int]


class _PinnedE7Inputs:
    """Hold all 15 P-authorized inputs open across loading, fitting and commit.

    The core reader first proves the exact portable/DVC-cache topology.  The
    retained descriptor is then required to have the same inode and bytes.
    Every parser and Parquet fragment consumes the exact byte strings returned
    by that core read; retained descriptors exist only to keep validating the
    live names and parents through the post-release boundary.
    """

    def __init__(self, authority: Mapping[str, Any], *, repo_root: Path) -> None:
        self.authority = authority
        self.repo_root = repo_root
        self.records = _e7_required_input_partition(authority)
        self.authorized_dvc_pointers = (
            calibration_runner._authorized_scientific_dvc_pointers(authority)
        )
        self._handles: dict[str, _PinnedE7Handle] = {}
        self._payloads: dict[str, bytes] = {}
        self.snapshot: list[dict[str, Any]] = []

    @staticmethod
    def _file_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
        return (
            int(metadata.st_dev),
            int(metadata.st_ino),
            stat.S_IMODE(metadata.st_mode),
            int(metadata.st_nlink),
            int(metadata.st_size),
            int(metadata.st_mtime_ns),
            int(metadata.st_ctime_ns),
        )

    @staticmethod
    def _parent_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
        return (
            int(metadata.st_dev),
            int(metadata.st_ino),
            stat.S_IMODE(metadata.st_mode),
            int(metadata.st_nlink),
            int(metadata.st_mtime_ns),
            int(metadata.st_ctime_ns),
        )

    @staticmethod
    def _descriptor_digest(descriptor: int) -> tuple[int, str]:
        digest = hashlib.sha256()
        offset = 0
        while True:
            chunk = os.pread(descriptor, 1024 * 1024, offset)
            if not chunk:
                break
            digest.update(chunk)
            offset += len(chunk)
        return offset, digest.hexdigest()

    def __enter__(self) -> "_PinnedE7Inputs":
        try:
            for expected in self.records:
                relative = Path(expected["path"])
                authorized_payload, authorized_metadata = (
                    calibration._read_scientific_payload_bytes_and_metadata(
                        relative,
                        authorized_dvc_pointers=self.authorized_dvc_pointers,
                        repo_root=self.repo_root,
                    )
                )
                expected_identity = self._file_identity(authorized_metadata)
                absolute = self.repo_root / relative
                parent, name, _ = calibration_runner._open_parent(
                    absolute, repo_root=self.repo_root, create=False
                )
                descriptor: int | None = None
                try:
                    parent_before = os.fstat(parent)
                    descriptor = os.open(
                        name,
                        os.O_RDONLY
                        | getattr(os, "O_CLOEXEC", 0)
                        | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=parent,
                    )
                    opened = os.fstat(descriptor)
                    named = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    parent_after = os.fstat(parent)
                    identity = self._file_identity(opened)
                    parent_identity = self._parent_identity(parent_before)
                    byte_count, sha256 = self._descriptor_digest(descriptor)
                    if (
                        identity != expected_identity
                        or self._file_identity(named) != identity
                        or self._parent_identity(parent_after) != parent_identity
                        or byte_count != expected["bytes"]
                        or sha256 != expected["sha256"]
                        or byte_count != len(authorized_payload)
                        or sha256 != hashlib.sha256(authorized_payload).hexdigest()
                    ):
                        raise _error(
                            "E7 pinned scientific input differs from P authority: "
                            f"{relative.as_posix()}"
                        )
                    handle = _PinnedE7Handle(
                        path=relative.as_posix(),
                        descriptor=descriptor,
                        identity=identity,
                        parent_identity=parent_identity,
                    )
                    self._handles[handle.path] = handle
                    self._payloads[handle.path] = authorized_payload
                    descriptor = None
                    self.snapshot.append(
                        {
                            **expected,
                            "device": identity[0],
                            "inode": identity[1],
                            "mode": format(identity[2], "04o"),
                            "nlink": identity[3],
                            "mtime_ns": identity[5],
                            "ctime_ns": identity[6],
                            "parent_device": parent_identity[0],
                            "parent_inode": parent_identity[1],
                            "parent_mode": format(parent_identity[2], "04o"),
                            "parent_nlink": parent_identity[3],
                            "parent_mtime_ns": parent_identity[4],
                            "parent_ctime_ns": parent_identity[5],
                        }
                    )
                finally:
                    if descriptor is not None:
                        os.close(descriptor)
                    os.close(parent)
            if (
                len(self._handles) != 15
                or len(self._payloads) != 15
                or len(self.snapshot) != 15
            ):
                raise _error("E7 pinned scientific input cardinality drifted")
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        for handle in reversed(tuple(self._handles.values())):
            try:
                os.close(handle.descriptor)
            except OSError:
                pass
        self._handles.clear()
        self._payloads.clear()

    def payload(self, path: str) -> bytes:
        payload = self._payloads.get(path)
        if payload is None or path not in self._handles:
            raise _error(f"E7 pinned scientific input is absent: {path}")
        # These are the exact chunks returned by the core strict reader in
        # __enter__, not a second pass over a potentially mutated inode.
        return payload

    def revalidate(self) -> None:
        for handle in self._handles.values():
            if self._file_identity(os.fstat(handle.descriptor)) != handle.identity:
                raise _error(f"E7 pinned descriptor identity changed: {handle.path}")
            byte_count, sha256 = self._descriptor_digest(handle.descriptor)
            expected = next(
                record for record in self.records if record["path"] == handle.path
            )
            if (
                byte_count != expected["bytes"]
                or sha256 != expected["sha256"]
                or self._file_identity(os.fstat(handle.descriptor)) != handle.identity
            ):
                raise _error(f"E7 pinned descriptor bytes changed: {handle.path}")
            absolute = self.repo_root / handle.path
            parent, name, _ = calibration_runner._open_parent(
                absolute, repo_root=self.repo_root, create=False
            )
            try:
                if (
                    self._parent_identity(os.fstat(parent)) != handle.parent_identity
                    or self._file_identity(
                        os.stat(name, dir_fd=parent, follow_symlinks=False)
                    )
                    != handle.identity
                ):
                    raise _error(f"E7 named scientific input changed: {handle.path}")
            finally:
                os.close(parent)


def _snapshot_e7_required_inputs(
    authority: Mapping[str, Any], *, repo_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compatibility snapshot built through the strict pinned transaction."""

    with _PinnedE7Inputs(authority, repo_root=repo_root) as pinned:
        pinned.revalidate()
        return [dict(record) for record in pinned.records], [
            dict(record) for record in pinned.snapshot
        ]


def _revalidate_e7_required_input_snapshot(
    authority: Mapping[str, Any],
    snapshot: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
) -> None:
    _, observed = _snapshot_e7_required_inputs(authority, repo_root=repo_root)
    if observed != [dict(record) for record in snapshot]:
        raise _error("E7 scientific input snapshot changed during execution")


def _snapshot_primary_anfis_family(*, repo_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in family_registration._family_final_paths():
        absolute = repo_root / path
        parent, _, _ = calibration_runner._open_parent(
            absolute, repo_root=repo_root, create=False
        )
        try:
            before = os.fstat(parent)
            file_record = stable_file_record(absolute, repo_root=repo_root)
            after = os.fstat(parent)
            parent_identity = (
                before.st_dev,
                before.st_ino,
                stat.S_IMODE(before.st_mode),
                before.st_nlink,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            if parent_identity != (
                after.st_dev,
                after.st_ino,
                stat.S_IMODE(after.st_mode),
                after.st_nlink,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise _error("E7 primary ANFIS parent changed during snapshot")
            records.append(
                {
                    "role": "primary_anfis_family_final",
                    **file_record,
                    "parent_device": int(before.st_dev),
                    "parent_inode": int(before.st_ino),
                    "parent_mode": format(stat.S_IMODE(before.st_mode), "04o"),
                    "parent_nlink": int(before.st_nlink),
                    "parent_mtime_ns": int(before.st_mtime_ns),
                    "parent_ctime_ns": int(before.st_ctime_ns),
                }
            )
        finally:
            os.close(parent)
    if len(records) != 80 or len({record["path"] for record in records}) != 80:
        raise _error("E7 primary ANFIS family snapshot differs from exact 80")
    return records


def _revalidate_primary_anfis_family_snapshot(
    snapshot: Sequence[Mapping[str, Any]], *, repo_root: Path
) -> None:
    if len(snapshot) != 80:
        raise _error("E7 primary ANFIS family snapshot cardinality drifted")
    observed = _snapshot_primary_anfis_family(repo_root=repo_root)
    if observed != [dict(record) for record in snapshot]:
        raise _error("E7 primary ANFIS family changed during execution")


def _configure_e7_cpu_policy(runtime: Mapping[str, Any]) -> dict[str, Any]:
    try:
        observed = configure_torch_cpu_execution_policy(runtime)
    except Exception as exc:
        raise _error(f"E7 CPU execution policy failed: {exc}") from exc
    return {"torch_cpu_execution_policy": observed, "threadpool_limit": 1}


def _require_e7_run_namespace(*, repo_root: Path) -> Mapping[str, Any]:
    require = getattr(
        calibration, "require_final_calibration_run_namespace", None
    )
    if not callable(require):
        raise _error("E0-MCAL run-namespace authority is unavailable")
    value = require(runner="e7", repo_root=repo_root)
    if not isinstance(value, Mapping):
        raise _error("E7 run-namespace authority is malformed")
    return value


def check_only(*, repo_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = calibration.require_final_calibration_authority(
        verify_remote=True, repo_root=repo_root
    )
    namespace = _require_e7_run_namespace(repo_root=repo_root)
    return {
        "status": "ready_to_run_learning_curve",
        "gate": calibration.PATCH_GATE,
        "authority": authority,
        "namespace": dict(namespace),
        "training_sizes": list(TRAINING_SIZES),
        "base_seeds": list(BASE_SEEDS),
        "slot_count": len(TRAINING_SIZES) * len(BASE_SEEDS),
        "output_count": len(OUTPUT_PATHS),
        "writes_performed": False,
        "fit_run": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "holdout_accessed": False,
        "post_2021_rows_accessed": False,
        "future_outcomes_accessed": False,
    }


def _execute_one_shot_with_pinned_inputs(
    *,
    authority: Mapping[str, Any],
    namespace: Mapping[str, Any],
    pinned_inputs: _PinnedE7Inputs,
    repo_root: Path,
) -> dict[str, Any]:
    input_records = [dict(record) for record in pinned_inputs.records]
    primary_snapshot = _snapshot_primary_anfis_family(repo_root=repo_root)
    loaded = _load_learning_curve_surface(
        pinned_inputs=pinned_inputs, repo_root=repo_root
    )
    surface = loaded["surface"]
    runtime = loaded["runtime"]
    gate = loaded["gate"]
    execution_policy = _configure_e7_cpu_policy(runtime)
    with threadpool_limits(limits=1):
        curve, evidence = run_learning_curve(surface, runtime=runtime, gate=gate)
    _revalidate_primary_anfis_family_snapshot(
        primary_snapshot, repo_root=repo_root
    )
    pinned_inputs.revalidate()
    evidence = {
        **evidence,
        "primary_slots_untouched": True,
        "execution_policy": execution_policy,
    }
    contract = runtime.get("e0_mcal_e7_terminal_record")
    if isinstance(contract, Mapping) and (
        evidence.get("completed_slot_count") != 5
        or evidence.get("resource_failure_count") != 10
        or evidence.get("completed_module_fit_count") != 15
    ):
        raise _error("E7 measured terminal result differs from its effective authority")
    payloads, manifest = build_anfis_learning_curve_bundle(
        authority=authority,
        curve=curve,
        evidence=evidence,
        input_records=input_records,
        repo_root=repo_root,
    )
    if calibration.require_final_calibration_authority(
        verify_remote=True, repo_root=repo_root
    ) != authority:
        raise _error("E0-MCAL authority changed during E7 terminalization")
    _revalidate_primary_anfis_family_snapshot(
        primary_snapshot, repo_root=repo_root
    )
    records: list[dict[str, Any]] = []
    guard = repo_root / GUARD_PATH.relative_to(PROJECT_ROOT)

    with calibration_runner.OrderedBundleTransaction(
        guard_path=guard, repo_root=repo_root
    ) as transaction:
        for path, payload in payloads:
            records.append(transaction.publish(path, payload))
        _revalidate_primary_anfis_family_snapshot(
            primary_snapshot, repo_root=repo_root
        )
        pinned_inputs.revalidate()
        calibration.revalidate_final_calibration_owned_run_publication(
            authority,
            runner="e7",
            phase="active_guard",
            owned_guard=transaction.owned_guard_capability(),
            owned_outputs=transaction.owned_output_capabilities(),
            verify_remote=True,
            repo_root=repo_root,
        )

        def revalidate_post_release() -> None:
            _revalidate_primary_anfis_family_snapshot(
                primary_snapshot, repo_root=repo_root
            )
            pinned_inputs.revalidate()
            calibration.revalidate_final_calibration_owned_run_publication(
                authority,
                runner="e7",
                phase="post_release",
                owned_guard=transaction.owned_guard_capability(),
                owned_outputs=transaction.owned_output_capabilities(),
                verify_remote=True,
                repo_root=repo_root,
            )

        transaction.commit(post_release_validators=(revalidate_post_release,))
    completed_module_fit_count = evidence.get("completed_module_fit_count")
    if type(completed_module_fit_count) is not int:
        raise _error("E7 completed module fit count drifted after publication")
    return {
        "status": "completed_unpublished",
        "gate": calibration.PATCH_GATE,
        "terminal_row_count": 15,
        "output_count": 2,
        "records": records,
        "manifest": manifest,
        "namespace": dict(namespace),
        "fit_run": True,
        "new_e7_fit_count": completed_module_fit_count,
        "primary_fit_reuse_count": 0,
        "primary_slots_untouched": evidence["primary_slots_untouched"],
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "holdout_accessed": False,
        "post_2021_rows_accessed": False,
        "future_outcomes_accessed": False,
    }


def execute_one_shot(*, repo_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Execute all 15 terminal slots from one retained P-authorized FD set."""

    authority = calibration.require_final_calibration_authority(
        verify_remote=True, repo_root=repo_root
    )
    namespace = _require_e7_run_namespace(repo_root=repo_root)
    with _PinnedE7Inputs(authority, repo_root=repo_root) as pinned_inputs:
        return _execute_one_shot_with_pinned_inputs(
            authority=authority,
            namespace=namespace,
            pinned_inputs=pinned_inputs,
            repo_root=repo_root,
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute-one-shot", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = check_only() if args.check_only else execute_one_shot()
    except calibration.FinalCalibrationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(calibration._canonical_json_bytes(payload).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
