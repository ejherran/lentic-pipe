#!/usr/bin/env python
"""Fit one locked Closure V1 adaptive ANFIS seed slot after E0-DL.

The command is deliberately unavailable before the external development lock
authorizes fitting.  Authorization is checked before any Parquet read or
output write.  Only ANFIS-N, ANFIS-F, and ANFIS-T-no-current are fitted; no
scientific outcome or observed-Chl-a lineage is read by this adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from src.experiments.build_closure_expert_state import (
    PROJECT_ROOT,
    _assert_unchanged,
    _dependency_snapshot,
    _file_record,
    _manifest_path,
    _runtime_section,
    _sha256_file,
    _write_json_atomic,
    _write_parquet_atomic,
)
from src.experiments.closure_contract import resolve_repo_path
from src.experiments.closure_development_guard import (
    DEVELOPMENT_ROLES,
    ROLE_TRAINING,
    DevelopmentGate,
    DevelopmentScanAudit,
    assert_development_frame,
    load_development_gate,
    scan_development_rows,
)
from src.experiments.closure_runtime_contract import (
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_RUNTIME_SCHEMA,
    EXPECTED_EXPERT_STATE_SHA256,
    EXPECTED_PANEL_SHA256,
    ClosureRuntimeContractError,
    anfis_hash_rank_sample,
    anfis_module_substreams,
    anfis_uncertainty_proxy,
    closure_anfis_features,
    closure_state_deltas,
    configure_torch_cpu_execution_policy,
    load_and_validate_development_runtime,
    validate_anfis_raw_projection_columns,
    validate_seed_slots,
)
from src.fuzzy.adaptive_anfis import (
    _require_torch,
    make_adaptive_anfis,
    max_parameter_delta,
    parameter_snapshot,
    set_reproducible_seed,
    train_supervised_anfis,
)


MANIFEST_VERSION = "closure_anfis_seed_manifest_v1"
LINEAGE_AUDIT_VERSION = "closure_anfis_seed_lineage_v1"
KEY_COLUMNS = ("source_id", "site_id", "year_month")
PRIMARY_MODULES = ("ANFIS-N", "ANFIS-F", "ANFIS-T-no-current")
MODULE_OUTPUTS: dict[str, tuple[str, str]] = {
    "ANFIS-N": ("yN_adaptive", "sigma_N_adaptive"),
    "ANFIS-F": ("yF_adaptive", "sigma_F_adaptive"),
    "ANFIS-T-no-current": ("yT_no_chla_adaptive", "sigma_T_no_chla_adaptive"),
}
INSUFFICIENT_SAMPLE_PATTERN = re.compile(
    r"^ANFIS candidate universe has (?P<eligible>[0-9]+) rows; "
    r"(?P<required>[0-9]+) are required$"
)


@dataclass(frozen=True)
class PanelAnchorJoinAudit:
    filtered_anchor_rows: int
    filtered_panel_rows: int
    matched_rows: int
    unmatched_anchor_rows: int
    unmatched_panel_rows: int
    anchor_keys_sha256: str
    panel_keys_sha256: str
    matched_keys_sha256: str
    unmatched_anchor_keys_sha256: str
    unmatched_panel_keys_sha256: str


@dataclass(frozen=True)
class AnfisSurfaceViews:
    """Separate full-development prediction and training-candidate joins."""

    full_development: pd.DataFrame
    training_candidates: pd.DataFrame
    full_development_join: PanelAnchorJoinAudit
    training_candidate_join: PanelAnchorJoinAudit
    source_scans: Mapping[str, DevelopmentScanAudit]


@dataclass
class ModuleFitResult:
    module: str
    module_seed: int
    model: Any
    sample_keys: pd.DataFrame
    sample_audit: dict[str, Any]
    predictions: np.ndarray
    uncertainty: np.ndarray
    metrics: dict[str, Any]
    curve: pd.DataFrame
    memberships_initial: pd.DataFrame
    memberships_final: pd.DataFrame


ModuleSample = tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]


@dataclass(frozen=True)
class ModuleSamplingUnavailable:
    """Machine-readable evidence for one module with too few eligible rows."""

    module: str
    module_seed: int
    base_seed: int
    required_rows: int
    eligible_rows: int
    audit: dict[str, Any]
    failure_reason: str = "insufficient_eligible_training_rows"
    replacement_used: bool = False


class AnfisModuleUnavailableError(ClosureRuntimeContractError):
    """Raised only for the locked no-replacement insufficient-row policy."""

    def __init__(self, evidence: ModuleSamplingUnavailable) -> None:
        self.evidence = evidence
        super().__init__(
            f"{evidence.module} is unavailable: {evidence.eligible_rows} eligible rows; "
            f"{evidence.required_rows} are required without replacement"
        )


def authorize_development_fit(
    *,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    runtime_schema: Path = DEFAULT_RUNTIME_SCHEMA,
) -> dict[str, Any]:
    """Import the external-lock validator lazily and fail closed."""
    from src.experiments.closure_development_runtime_lock import (  # noqa: PLC0415
        require_development_fit_authorized,
    )

    return require_development_fit_authorized(
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
    )


def _validate_authorization(
    authorization: Mapping[str, Any],
    *,
    runtime: Mapping[str, Any],
) -> None:
    """Bind a previously validated authorization summary to the physical E0-DL."""
    expected_fields = {
        "status": "locked",
        "device": "cpu",
        "fit_authorized": True,
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    for field, expected in expected_fields.items():
        if authorization.get(field) != expected or (
            expected is False and authorization.get(field) is not False
        ):
            raise ClosureRuntimeContractError(
                f"E0-DL authorization summary requires {field}={expected!r}"
            )

    implementation_lock = _runtime_section(runtime, "implementation_lock")
    lock_path = resolve_repo_path(str(implementation_lock["lock_manifest_path"]))
    if authorization.get("lock_path") != _manifest_path(lock_path):
        raise ClosureRuntimeContractError("E0-DL authorization path differs from the runtime contract")
    if authorization.get("lock_sha256") != _sha256_file(lock_path):
        raise ClosureRuntimeContractError("E0-DL authorization SHA-256 differs from the physical lock")


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        frame.to_csv(temporary, index=False)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _write_text_atomic(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _torch_save_atomic(payload: Mapping[str, Any], path: Path) -> None:
    torch = _require_torch()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        torch.save(dict(payload), temporary)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _compact_key_bytes(key: tuple[str, str, str]) -> bytes:
    return json.dumps(list(key), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _key_digest(keys: Sequence[tuple[str, str, str]]) -> str:
    digest = hashlib.sha256()
    for key in sorted(keys, key=_compact_key_bytes):
        digest.update(_compact_key_bytes(key))
        digest.update(b"\n")
    return digest.hexdigest()


def _frame_keys(frame: pd.DataFrame) -> list[tuple[str, str, str]]:
    return list(
        zip(
            frame["source_id"].astype(str),
            frame["site_id"].astype(str),
            frame["year_month"].astype(str),
            strict=True,
        )
    )


def _canonical_sort(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["_source_utf8"] = out["source_id"].map(lambda value: str(value).encode("utf-8"))
    out["_site_utf8"] = out["site_id"].map(lambda value: str(value).encode("utf-8"))
    out = out.sort_values(["_source_utf8", "_site_utf8", "year_month"], kind="mergesort")
    return out.drop(columns=["_source_utf8", "_site_utf8"]).reset_index(drop=True)


def _validate_scanned_source(
    frame: pd.DataFrame,
    *,
    projected_columns: Sequence[str],
    gate: DevelopmentGate,
    label: str,
) -> None:
    expected = {*projected_columns, "assignment_role", "time_role"}
    if set(frame.columns) != expected:
        raise ClosureRuntimeContractError(f"{label} scan returned columns outside its exact projection")
    if bool(frame.loc[:, list(KEY_COLUMNS)].isna().any().any()):
        raise ClosureRuntimeContractError(f"{label} contains null keys")
    if bool(frame.duplicated(list(KEY_COLUMNS), keep=False).any()):
        raise ClosureRuntimeContractError(f"{label} contains duplicate keys")
    assert_development_frame(
        frame,
        gate,
        role_column="time_role",
        allowed_roles=DEVELOPMENT_ROLES,
    )


def join_anfis_sources(
    panel: pd.DataFrame,
    anchor: pd.DataFrame,
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate,
) -> tuple[pd.DataFrame, PanelAnchorJoinAudit]:
    """Join independently guarded raw and anchor projections one-to-one."""
    anfis = _runtime_section(runtime, "anfis")
    projection = _runtime_section(anfis, "source_projection")
    panel_columns = tuple(str(value) for value in projection["panel_columns"])
    anchor_columns = tuple(str(value) for value in projection["expert_anchor_columns"])
    validate_anfis_raw_projection_columns(panel_columns, anchor_columns)
    _validate_scanned_source(
        panel,
        projected_columns=panel_columns,
        gate=gate,
        label="ANFIS panel",
    )
    _validate_scanned_source(
        anchor,
        projected_columns=anchor_columns,
        gate=gate,
        label="ANFIS expert anchor",
    )

    panel_keys = _frame_keys(panel)
    anchor_keys = _frame_keys(anchor)
    panel_set = set(panel_keys)
    anchor_set = set(anchor_keys)
    matched = panel_set.intersection(anchor_set)
    anchor_only = anchor_set.difference(panel_set)
    panel_only = panel_set.difference(anchor_set)
    audit = PanelAnchorJoinAudit(
        filtered_anchor_rows=len(anchor),
        filtered_panel_rows=len(panel),
        matched_rows=len(matched),
        unmatched_anchor_rows=len(anchor_only),
        unmatched_panel_rows=len(panel_only),
        anchor_keys_sha256=_key_digest(anchor_keys),
        panel_keys_sha256=_key_digest(panel_keys),
        matched_keys_sha256=_key_digest(list(matched)),
        unmatched_anchor_keys_sha256=_key_digest(list(anchor_only)),
        unmatched_panel_keys_sha256=_key_digest(list(panel_only)),
    )
    if audit.filtered_anchor_rows != audit.matched_rows + audit.unmatched_anchor_rows:
        raise ClosureRuntimeContractError("ANFIS anchor join conservation failed")
    if audit.filtered_panel_rows != audit.matched_rows + audit.unmatched_panel_rows:
        raise ClosureRuntimeContractError("ANFIS panel join conservation failed")

    panel_safe = panel.loc[:, [*panel_columns, "assignment_role", "time_role"]]
    anchor_safe = anchor.loc[:, [*anchor_columns, "assignment_role", "time_role"]]
    joined = anchor_safe.merge(
        panel_safe,
        on=list(KEY_COLUMNS),
        how="inner",
        validate="one_to_one",
        suffixes=("_anchor", "_panel"),
    )
    for field in ("assignment_role", "time_role"):
        if not bool(joined[f"{field}_anchor"].eq(joined[f"{field}_panel"]).all()):
            raise ClosureRuntimeContractError(f"ANFIS panel and anchor disagree on {field}")
        joined[field] = joined.pop(f"{field}_anchor")
        joined = joined.drop(columns=[f"{field}_panel"])
    if len(joined) != audit.matched_rows:
        raise ClosureRuntimeContractError("ANFIS joined row count differs from the key audit")

    feature_rows = [closure_anfis_features(row) for row in joined.to_dict(orient="records")]
    feature_frame = pd.DataFrame(feature_rows, index=joined.index)
    for column in feature_frame.columns:
        joined[column] = feature_frame[column]
    return _canonical_sort(joined), audit


def load_joined_anfis_surface(
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate,
) -> AnfisSurfaceViews:
    """Build separate full-development and training-only joins from one scan."""
    projection = _runtime_section(_runtime_section(runtime, "anfis"), "source_projection")
    panel_columns = tuple(str(value) for value in projection["panel_columns"])
    anchor_columns = tuple(str(value) for value in projection["expert_anchor_columns"])
    validate_anfis_raw_projection_columns(panel_columns, anchor_columns)
    panel, panel_audit = scan_development_rows(
        resolve_repo_path(str(projection["panel_path"])),
        gate,
        columns=panel_columns,
        point_month_column="year_month",
    )
    anchor, anchor_audit = scan_development_rows(
        resolve_repo_path(str(projection["expert_anchor_path"])),
        gate,
        columns=anchor_columns,
        point_month_column="year_month",
    )
    panel = panel.loc[:, [*panel_columns, "assignment_role", "time_role"]]
    anchor = anchor.loc[:, [*anchor_columns, "assignment_role", "time_role"]]
    full_development, full_join = join_anfis_sources(
        panel,
        anchor,
        runtime=runtime,
        gate=gate,
    )
    training_panel = panel.loc[panel["time_role"].eq(ROLE_TRAINING)].copy()
    training_anchor = anchor.loc[anchor["time_role"].eq(ROLE_TRAINING)].copy()
    training_candidates, training_join = join_anfis_sources(
        training_panel,
        training_anchor,
        runtime=runtime,
        gate=gate,
    )
    if not bool(training_candidates["time_role"].eq(ROLE_TRAINING).all()):
        raise ClosureRuntimeContractError(
            "ANFIS candidate join contains a non-training row"
        )
    return AnfisSurfaceViews(
        full_development=full_development,
        training_candidates=training_candidates,
        full_development_join=full_join,
        training_candidate_join=training_join,
        source_scans={"panel": panel_audit, "expert_anchor": anchor_audit},
    )


def _module_contract(
    runtime: Mapping[str, Any],
    module: str,
) -> tuple[list[str], str]:
    if module not in PRIMARY_MODULES:
        raise ClosureRuntimeContractError(f"Unregistered primary ANFIS module: {module!r}")
    anfis = _runtime_section(runtime, "anfis")
    features = _runtime_section(anfis, "primary_module_features")
    targets = _runtime_section(anfis, "primary_module_targets")
    return [str(value) for value in features[module]], str(targets[module])


def _module_arrays(
    frame: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
    target_column: str | None,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray]:
    features = frame.loc[:, list(feature_columns)].apply(pd.to_numeric, errors="coerce")
    features = features.replace([np.inf, -np.inf], np.nan)
    missing_fraction = features.isna().mean(axis=1).to_numpy(dtype="float64")
    x = features.fillna(0.5).clip(0.0, 1.0).to_numpy(dtype="float32", copy=True)
    target = None
    if target_column is not None:
        target_series = pd.to_numeric(frame[target_column], errors="coerce")
        if bool(target_series.isna().any()) or not bool(target_series.between(0.0, 1.0).all()):
            raise ClosureRuntimeContractError(
                f"ANFIS training anchor {target_column!r} must be finite in [0, 1]"
            )
        target = target_series.to_numpy(dtype="float32")
    return x, target, missing_fraction


def _optional_finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _unavailable_sampling_audit(
    rows: Sequence[Mapping[str, Any]],
    *,
    runtime: Mapping[str, Any],
    module: str,
    module_seed: int,
) -> dict[str, Any]:
    """Reconstruct evidence only after the production sampler proves insufficiency."""
    feature_columns, target_column = _module_contract(runtime, module)
    eligible_keys: list[tuple[str, str, str]] = []
    excluded_nonfinite_target_rows = 0
    excluded_missingness_rows = 0
    for row in rows:
        target = _optional_finite_float(row.get(target_column))
        if target is None:
            excluded_nonfinite_target_rows += 1
            continue
        missing_features = sum(
            _optional_finite_float(row.get(column)) is None for column in feature_columns
        )
        if missing_features / len(feature_columns) > 0.5:
            excluded_missingness_rows += 1
            continue
        eligible_keys.append(
            (
                str(row["source_id"]),
                str(row["site_id"]),
                str(row["year_month"]),
            )
        )

    anfis = _runtime_section(runtime, "anfis")
    configuration = _runtime_section(anfis, "fixed_configuration")
    offsets = _runtime_section(anfis, "module_seed_offsets")
    return {
        "input_rows": len(rows),
        "excluded_nonfinite_target_rows": excluded_nonfinite_target_rows,
        "excluded_missingness_rows": excluded_missingness_rows,
        "eligible_universe_rows": len(eligible_keys),
        "eligible_universe_sha256": _key_digest(eligible_keys),
        "selected_rows": 0,
        "selected_keys_sha256": hashlib.sha256(b"").hexdigest(),
        "module": module,
        "base_seed": int(module_seed - int(offsets[module])),
        "module_seed": module_seed,
        "required_rows": int(configuration["train_rows_per_module"]),
        "replacement_used": False,
        "failure_reason": "insufficient_eligible_training_rows",
    }


def select_module_training_rows(
    surface: pd.DataFrame,
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate,
    module: str,
    module_seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Apply the closed 4,096-key sampler and preserve rank order."""
    feature_columns, target_column = _module_contract(runtime, module)
    training = surface.loc[surface["time_role"].eq(ROLE_TRAINING)].copy()
    assert_development_frame(
        training,
        gate,
        role_column="time_role",
        allowed_roles={ROLE_TRAINING},
    )
    candidate_rows = training.loc[
        :,
        [*KEY_COLUMNS, "assignment_role", "time_role", target_column, *feature_columns],
    ].to_dict(orient="records")
    try:
        records, audit = anfis_hash_rank_sample(
            candidate_rows,
            module=module,
            module_seed=module_seed,
            development_keys=gate.development_keys,
        )
    except ClosureRuntimeContractError as exc:
        match = INSUFFICIENT_SAMPLE_PATTERN.fullmatch(str(exc))
        if match is None:
            raise
        unavailable_audit = _unavailable_sampling_audit(
            candidate_rows,
            runtime=runtime,
            module=module,
            module_seed=module_seed,
        )
        eligible_rows = int(match.group("eligible"))
        required_rows = int(match.group("required"))
        if (
            unavailable_audit["eligible_universe_rows"] != eligible_rows
            or unavailable_audit["required_rows"] != required_rows
        ):
            raise ClosureRuntimeContractError(
                "ANFIS insufficient-row evidence differs from the production sampler"
            ) from exc
        raise AnfisModuleUnavailableError(
            ModuleSamplingUnavailable(
                module=module,
                module_seed=module_seed,
                base_seed=int(unavailable_audit["base_seed"]),
                required_rows=required_rows,
                eligible_rows=eligible_rows,
                audit=unavailable_audit,
            )
        ) from exc

    persisted_columns = tuple(
        str(value)
        for value in _runtime_section(_runtime_section(runtime, "anfis"), "sampling")[
            "persisted_sample_columns"
        ]
    )
    sample_keys = pd.DataFrame(records, columns=persisted_columns)
    indexed = training.set_index(list(KEY_COLUMNS), drop=False)
    selected_rows = []
    for record in records:
        key = (record["source_id"], record["site_id"], record["year_month"])
        selected_rows.append(indexed.loc[key].to_dict())
    selected = pd.DataFrame(selected_rows).reset_index(drop=True)
    if len(selected) != int(audit["selected_rows"]):
        raise ClosureRuntimeContractError("ANFIS selected rows differ from the sample audit")
    return selected, sample_keys, audit


def prepare_slot_module_samples(
    surface: pd.DataFrame,
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate,
    substreams: Mapping[str, int],
) -> tuple[dict[str, ModuleSample], dict[str, ModuleSamplingUnavailable]]:
    """Preflight every module before constructing or fitting any model."""
    if tuple(substreams) != PRIMARY_MODULES:
        raise ClosureRuntimeContractError("ANFIS module substreams are not in locked order")
    prepared: dict[str, ModuleSample] = {}
    unavailable: dict[str, ModuleSamplingUnavailable] = {}
    for module in PRIMARY_MODULES:
        try:
            prepared[module] = select_module_training_rows(
                surface,
                runtime=runtime,
                gate=gate,
                module=module,
                module_seed=int(substreams[module]),
            )
        except AnfisModuleUnavailableError as exc:
            unavailable[module] = exc.evidence
    return prepared, unavailable


def set_closure_anfis_seed(module_seed: int) -> None:
    """Set all fixed deterministic controls before model construction."""
    set_reproducible_seed(module_seed)
    torch = _require_torch()
    torch.use_deterministic_algorithms(True)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True


def _membership_table(model: Any, *, module: str, features: Sequence[str], phase: str) -> pd.DataFrame:
    centers = model.ordered_centers().detach().cpu().numpy()
    widths = model.positive_widths().detach().cpu().numpy()
    rows: list[dict[str, Any]] = []
    for feature_index, feature in enumerate(features):
        for membership_index in range(centers.shape[1]):
            rows.append(
                {
                    "phase": phase,
                    "module": module,
                    "feature": feature,
                    "membership_index": membership_index,
                    "center": float(centers[feature_index, membership_index]),
                    "width": float(widths[feature_index, membership_index]),
                }
            )
    return pd.DataFrame(rows)


def predict_primary_module(
    model: Any,
    frame: pd.DataFrame,
    *,
    runtime: Mapping[str, Any],
    module: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Predict with raw model firing strengths and the exact uncertainty API."""
    feature_columns, _ = _module_contract(runtime, module)
    configuration = _runtime_section(_runtime_section(runtime, "anfis"), "fixed_configuration")
    batch_rows = int(configuration["predict_batch_rows"])
    torch = _require_torch()
    predictions: list[np.ndarray] = []
    uncertainties: list[np.ndarray] = []
    model.eval()
    for start in range(0, len(frame), batch_rows):
        chunk = frame.iloc[start : start + batch_rows]
        x, _, missing = _module_arrays(
            chunk,
            feature_columns=feature_columns,
            target_column=None,
        )
        with torch.no_grad():
            details = model(torch.as_tensor(x, dtype=torch.float32), return_details=True)
        prediction = details["prediction"].detach().cpu().numpy().astype("float64")
        raw_firing = details["firing_strengths"].detach().cpu().numpy()
        sigma = np.asarray(
            [
                anfis_uncertainty_proxy(
                    raw_firing[row_index].tolist(),
                    module=module,
                    missing_fraction=float(missing[row_index]),
                )
                for row_index in range(len(chunk))
            ],
            dtype="float64",
        )
        predictions.append(prediction)
        uncertainties.append(sigma)
    return (
        np.concatenate(predictions) if predictions else np.empty(0, dtype="float64"),
        np.concatenate(uncertainties) if uncertainties else np.empty(0, dtype="float64"),
    )


def fit_primary_module(
    surface: pd.DataFrame,
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate,
    module: str,
    module_seed: int,
    prepared_sample: ModuleSample | None = None,
) -> ModuleFitResult:
    if prepared_sample is None:
        selected, sample_keys, sample_audit = select_module_training_rows(
            surface,
            runtime=runtime,
            gate=gate,
            module=module,
            module_seed=module_seed,
        )
    else:
        selected, sample_keys, sample_audit = prepared_sample
        if (
            sample_audit.get("module") != module
            or sample_audit.get("module_seed") != module_seed
        ):
            raise ClosureRuntimeContractError(
                "Prepared ANFIS sample differs from its module substream"
            )
    feature_columns, target_column = _module_contract(runtime, module)
    train_x, train_y, _ = _module_arrays(
        selected,
        feature_columns=feature_columns,
        target_column=target_column,
    )
    assert train_y is not None
    configuration = _runtime_section(_runtime_section(runtime, "anfis"), "fixed_configuration")

    set_closure_anfis_seed(module_seed)
    model = make_adaptive_anfis(
        input_dim=len(feature_columns),
        membership_count=int(configuration["memberships_per_input"]),
        min_width=float(configuration["min_width"]),
        min_gap=float(configuration["min_gap"]),
        output_activation=str(configuration["output_activation"]),
        center_constraint=str(configuration["center_constraint"]),
    )
    parameter_devices = {parameter.device.type for parameter in model.parameters()}
    if parameter_devices and parameter_devices != {"cpu"}:
        raise ClosureRuntimeContractError("Closure ANFIS must remain on the locked CPU device")
    memberships_initial = _membership_table(
        model,
        module=module,
        features=feature_columns,
        phase="initial",
    )
    before = parameter_snapshot(model)
    curve_records = train_supervised_anfis(
        model,
        train_x,
        train_y,
        epochs=int(configuration["epochs"]),
        learning_rate=float(configuration["learning_rate"]),
        random_seed=module_seed,
        grad_clip=float(configuration["grad_clip"]),
    )
    memberships_final = _membership_table(
        model,
        module=module,
        features=feature_columns,
        phase="final",
    )
    final_checkpoint_loss, quality_gate_output_std = _post_update_anchor_metrics(
        model,
        train_x,
        train_y,
    )
    predictions, uncertainty = predict_primary_module(
        model,
        surface,
        runtime=runtime,
        module=module,
    )
    materialized_surface_output_std = float(np.std(predictions, dtype="float64"))
    curve_last_pre_update_loss = float(curve_records[-1]["loss"])
    status = (
        "passed"
        if math.isfinite(final_checkpoint_loss)
        and quality_gate_output_std
        >= float(configuration["min_output_standard_deviation"])
        and max_parameter_delta(model, before) > 0.0
        and model.centers_are_ordered()
        and model.centers_in_unit_interval()
        else "failed"
    )
    metrics = {
        "module": module,
        "status": status,
        "base_seed": int(sample_audit["base_seed"]),
        "module_seed": module_seed,
        "train_rows": len(selected),
        "prediction_rows": len(surface),
        "input_dimension": len(feature_columns),
        "rule_count": int(model.rule_count),
        "epochs": len(curve_records),
        "curve_initial_pre_update_loss": float(curve_records[0]["loss"]),
        "curve_last_pre_update_loss": curve_last_pre_update_loss,
        "minimum_curve_pre_update_loss": float(
            min(row["loss"] for row in curve_records)
        ),
        "final_checkpoint_loss": final_checkpoint_loss,
        "quality_gate_output_standard_deviation": quality_gate_output_std,
        "quality_gate_output_scope": "locked_hash_ranked_training_sample_4096",
        "materialized_surface_output_standard_deviation": (
            materialized_surface_output_std
        ),
        "maximum_parameter_delta": max_parameter_delta(model, before),
        "centers_ordered": bool(model.centers_are_ordered()),
        "centers_in_unit_interval": bool(model.centers_in_unit_interval()),
    }
    curve = pd.DataFrame(curve_records)
    curve.insert(0, "module", module)
    curve.insert(1, "module_seed", module_seed)
    return ModuleFitResult(
        module=module,
        module_seed=module_seed,
        model=model,
        sample_keys=sample_keys,
        sample_audit=sample_audit,
        predictions=predictions,
        uncertainty=uncertainty,
        metrics=metrics,
        curve=curve,
        memberships_initial=memberships_initial,
        memberships_final=memberships_final,
    )


def _post_update_anchor_metrics(
    model: Any,
    features: np.ndarray,
    target: np.ndarray,
) -> tuple[float, float]:
    """Evaluate loss and spread on the locked sample after the final update."""
    torch = _require_torch()
    model.eval()
    with torch.no_grad():
        prediction = model(torch.as_tensor(features, dtype=torch.float32))
        observed = torch.as_tensor(target, dtype=torch.float32).reshape(-1)
        loss = torch.nn.functional.mse_loss(prediction.reshape(-1), observed)
    values = prediction.detach().cpu().numpy().astype("float64", copy=False)
    return float(loss.detach().item()), float(np.std(values, dtype="float64"))


def build_adaptive_state(
    surface: pd.DataFrame,
    module_results: Mapping[str, ModuleFitResult],
    *,
    runtime: Mapping[str, Any],
    gate: DevelopmentGate,
) -> pd.DataFrame:
    if tuple(module_results) != PRIMARY_MODULES:
        raise ClosureRuntimeContractError("Adaptive state requires the three ordered primary modules")
    base = surface.loc[:, [*KEY_COLUMNS, "time_role"]].copy()
    for module in PRIMARY_MODULES:
        result = module_results[module]
        output_column, sigma_column = MODULE_OUTPUTS[module]
        if len(result.predictions) != len(base) or len(result.uncertainty) != len(base):
            raise ClosureRuntimeContractError(f"{module} prediction count differs from the state surface")
        base[output_column] = result.predictions
        base[sigma_column] = result.uncertainty
    level_columns = [MODULE_OUTPUTS[module][0] for module in PRIMARY_MODULES]
    sigma_columns = [MODULE_OUTPUTS[module][1] for module in PRIMARY_MODULES]
    for column in [*level_columns, *sigma_columns]:
        numeric = pd.to_numeric(base[column], errors="coerce")
        if bool(numeric.isna().any()) or not bool(numeric.between(0.0, 1.0).all()):
            raise ClosureRuntimeContractError(
                f"Adaptive Closure state {column!r} must be finite in [0, 1]"
            )
    delta_records = closure_state_deltas(
        "P1",
        base.loc[:, [*KEY_COLUMNS, *level_columns]].to_dict(orient="records"),
        development_keys=gate.development_keys,
    )
    state = base.merge(
        pd.DataFrame(delta_records),
        on=list(KEY_COLUMNS),
        how="left",
        validate="one_to_one",
    )
    export = _runtime_section(
        _runtime_section(runtime, "primary_autoregressive_state"),
        "state_export",
    )
    output_columns = tuple(str(value) for value in export["p1_output_columns"])
    if set(state.columns) != set(output_columns):
        raise ClosureRuntimeContractError("P1 state does not match the exact output allowlist")
    state = _canonical_sort(state.loc[:, output_columns])
    assert_development_frame(
        state,
        gate,
        role_column="time_role",
        allowed_roles=DEVELOPMENT_ROLES,
    )
    if str(state["year_month"].max()) > str(export["latest_state_month"]):
        raise ClosureRuntimeContractError("Adaptive state materialized a row after 2021-12")
    return state


def _slot_paths(runtime: Mapping[str, Any], base_seed: int) -> dict[str, Any]:
    artifacts = _runtime_section(runtime, "artifacts")
    paths: dict[str, Any] = {}
    for field in (
        "anfis_state_template",
        "anfis_metrics_template",
        "anfis_training_curve_template",
        "anfis_memberships_initial_template",
        "anfis_memberships_final_template",
        "anfis_report_template",
        "anfis_manifest_template",
        "anfis_lineage_audit_template",
    ):
        paths[field] = resolve_repo_path(str(artifacts[field]).format(base_seed=base_seed))
    paths["models"] = {
        module: resolve_repo_path(
            str(artifacts["anfis_model_template"]).format(
                base_seed=base_seed,
                module=module,
            )
        )
        for module in PRIMARY_MODULES
    }
    paths["samples"] = {
        module: resolve_repo_path(
            str(artifacts["anfis_sample_keys_template"]).format(
                base_seed=base_seed,
                module=module,
            )
        )
        for module in PRIMARY_MODULES
    }
    return paths


def _planned_slot_artifact_paths(
    runtime: Mapping[str, Any],
    base_seed: int,
) -> tuple[Path, ...]:
    paths = _slot_paths(runtime, base_seed)
    ordered = [
        paths[field]
        for field in (
            "anfis_state_template",
            "anfis_metrics_template",
            "anfis_training_curve_template",
            "anfis_memberships_initial_template",
            "anfis_memberships_final_template",
            "anfis_report_template",
            "anfis_manifest_template",
            "anfis_lineage_audit_template",
        )
    ]
    ordered.extend(paths["models"][module] for module in PRIMARY_MODULES)
    ordered.extend(paths["samples"][module] for module in PRIMARY_MODULES)
    state_path = paths["anfis_state_template"]
    ordered.append(state_path.with_suffix(state_path.suffix + ".dvc"))
    return tuple(ordered)


def require_pristine_anfis_seed_slot(
    runtime: Mapping[str, Any],
    base_seed: int,
) -> None:
    """Fail before row I/O when any final or temporary slot artifact exists."""
    planned = _planned_slot_artifact_paths(runtime, base_seed)
    candidates = [
        candidate
        for path in planned
        for candidate in (path, path.with_suffix(path.suffix + ".tmp"))
    ]
    existing = [_manifest_path(path) for path in candidates if path.exists()]
    if existing:
        raise ClosureRuntimeContractError(
            "Closure ANFIS seed slots are one-shot; existing artifacts require "
            f"review and authorized removal: {existing}"
        )


def _checkpoint_payload(
    result: ModuleFitResult,
    *,
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    features, target = _module_contract(runtime, result.module)
    configuration = _runtime_section(_runtime_section(runtime, "anfis"), "fixed_configuration")
    return {
        "checkpoint_version": "closure_anfis_module_v1",
        "experiment_id": "closure_v1",
        "module": result.module,
        "base_seed": int(result.sample_audit["base_seed"]),
        "module_seed": result.module_seed,
        "feature_columns": features,
        "target_column": target,
        "configuration": dict(configuration),
        "sample_audit": result.sample_audit,
        "model_state_dict": result.model.state_dict(),
    }


def _join_audit_payload(
    audits: Mapping[str, PanelAnchorJoinAudit],
) -> dict[str, dict[str, Any]]:
    expected = ("training_candidates", "full_development")
    if tuple(audits) != expected:
        raise ClosureRuntimeContractError(
            "ANFIS join audits must contain ordered training and full-development scopes"
        )
    return {scope: asdict(audits[scope]) for scope in expected}


def write_anfis_slot_bundle(
    state: pd.DataFrame,
    results: Mapping[str, ModuleFitResult],
    *,
    runtime: Mapping[str, Any],
    base_seed: int,
    join_audits: Mapping[str, PanelAnchorJoinAudit],
    scan_audits: Mapping[str, DevelopmentScanAudit],
    manifest_base: Mapping[str, Any],
) -> dict[str, Any]:
    """Write all slot outputs and write its completion manifest last."""
    paths = _slot_paths(runtime, base_seed)
    _write_parquet_atomic(state, paths["anfis_state_template"])
    output_records: list[dict[str, Any]] = [
        {**_file_record(paths["anfis_state_template"]), "role": "adaptive_no_current_state"}
    ]
    for module in PRIMARY_MODULES:
        result = results[module]
        _torch_save_atomic(
            _checkpoint_payload(result, runtime=runtime),
            paths["models"][module],
        )
        _write_csv_atomic(result.sample_keys, paths["samples"][module])
        output_records.extend(
            [
                {**_file_record(paths["models"][module]), "role": "anfis_checkpoint", "module": module},
                {**_file_record(paths["samples"][module]), "role": "sample_keys", "module": module},
            ]
        )

    metrics = pd.DataFrame([results[module].metrics for module in PRIMARY_MODULES])
    curves = pd.concat([results[module].curve for module in PRIMARY_MODULES], ignore_index=True)
    memberships_initial = pd.concat(
        [results[module].memberships_initial for module in PRIMARY_MODULES],
        ignore_index=True,
    )
    memberships_final = pd.concat(
        [results[module].memberships_final for module in PRIMARY_MODULES],
        ignore_index=True,
    )
    for frame, field, role in (
        (metrics, "anfis_metrics_template", "module_metrics"),
        (curves, "anfis_training_curve_template", "training_curve"),
        (memberships_initial, "anfis_memberships_initial_template", "memberships_initial"),
        (memberships_final, "anfis_memberships_final_template", "memberships_final"),
    ):
        _write_csv_atomic(frame, paths[field])
        output_records.append({**_file_record(paths[field]), "role": role})

    report_lines = [
        "# Closure V1 adaptive ANFIS development fit",
        "",
        f"- Base seed: `{base_seed}`",
        f"- State rows: `{len(state)}`",
        "- Evaluation authorized: `False`",
        "- E0-U authorized: `False`",
        "",
        "| module | status | train rows | final checkpoint loss | training-sample output std |",
        "|---|---|---:|---:|---:|",
    ]
    for module in PRIMARY_MODULES:
        row = results[module].metrics
        report_lines.append(
            f"| `{module}` | `{row['status']}` | {row['train_rows']} | "
            f"{row['final_checkpoint_loss']:.8f} | "
            f"{row['quality_gate_output_standard_deviation']:.8f} |"
        )
    _write_text_atomic("\n".join(report_lines) + "\n", paths["anfis_report_template"])
    output_records.append({**_file_record(paths["anfis_report_template"]), "role": "report"})

    lineage = {
        "audit_version": LINEAGE_AUDIT_VERSION,
        "status": "passed" if bool(metrics["status"].eq("passed").all()) else "failed",
        "experiment_id": "closure_v1",
        "base_seed": base_seed,
        "modules": list(PRIMARY_MODULES),
        "forbidden_primary_module_materialized": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "state_artifact_emitted": True,
        "failed_slot_replaced": False,
        "panel_anchor_joins": _join_audit_payload(join_audits),
        "source_scans": {
            name: {
                "materialized_rows": audit.materialized_rows,
                "returned_rows": audit.returned_rows,
                "boundary_crossing_rows": audit.boundary_crossing_rows,
                "role_counts": audit.role_counts,
            }
            for name, audit in scan_audits.items()
        },
        "state_output_columns": list(state.columns),
        "delta_previous_month_missing_count": int(state["delta_previous_month_missing"].sum()),
        "zero_holdout_overlap": True,
        "maximum_year_month": str(state["year_month"].max()),
    }
    _write_json_atomic(lineage, paths["anfis_lineage_audit_template"])
    output_records.append(
        {**_file_record(paths["anfis_lineage_audit_template"]), "role": "lineage_audit"}
    )
    slot_available = lineage["status"] == "passed"
    payload = dict(manifest_base)
    payload["status"] = "completed"
    payload["slot_status"] = "available" if slot_available else "model_unavailable"
    payload["fit_status"] = "passed" if slot_available else "failed"
    payload["failure_reason"] = "" if slot_available else "module_fit_quality_gate_failed"
    payload["failed_modules"] = [
        str(module)
        for module in PRIMARY_MODULES
        if results[module].metrics.get("status") != "passed"
    ]
    payload["retain_failed_seed_slot"] = not slot_available
    payload["replacement_used"] = False
    payload["failed_slot_replaced"] = False
    payload["model_construction_attempted"] = True
    payload["fit_attempted"] = True
    payload["state_output_materialized"] = True
    payload["state_artifact_emitted"] = True
    payload["checkpoint_outputs_materialized"] = True
    payload["module_metrics"] = metrics.to_dict(orient="records")
    payload["sampling"] = {
        module: results[module].sample_audit for module in PRIMARY_MODULES
    }
    payload["planned_unmaterialized_heavy_outputs"] = []
    payload["outputs"] = output_records
    _write_json_atomic(payload, paths["anfis_manifest_template"])
    return payload


def _sampling_metrics_rows(
    prepared: Mapping[str, ModuleSample],
    unavailable: Mapping[str, ModuleSamplingUnavailable],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for module in PRIMARY_MODULES:
        if module in unavailable:
            evidence = unavailable[module]
            audit = evidence.audit
            status = "model_unavailable"
            reason = evidence.failure_reason
        else:
            _, _, audit = prepared[module]
            status = "not_fitted_due_to_slot_unavailable"
            reason = "paired_slot_unavailable"
        rows.append(
            {
                "module": module,
                "status": status,
                "failure_reason": reason,
                "base_seed": int(audit["base_seed"]),
                "module_seed": int(audit["module_seed"]),
                "input_rows": int(audit["input_rows"]),
                "excluded_nonfinite_target_rows": int(audit["excluded_nonfinite_target_rows"]),
                "excluded_missingness_rows": int(audit["excluded_missingness_rows"]),
                "eligible_universe_rows": int(audit["eligible_universe_rows"]),
                "selected_rows": int(audit["selected_rows"]),
                "required_rows": int(audit.get("required_rows", 4096)),
                "replacement_used": False,
                "fit_attempted": False,
            }
        )
    return rows


def write_anfis_unavailable_slot_bundle(
    prepared: Mapping[str, ModuleSample],
    unavailable: Mapping[str, ModuleSamplingUnavailable],
    *,
    runtime: Mapping[str, Any],
    base_seed: int,
    join_audits: Mapping[str, PanelAnchorJoinAudit],
    scan_audits: Mapping[str, DevelopmentScanAudit],
    manifest_base: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist a retained unavailable slot without state, checkpoints, or fit."""
    if not unavailable:
        raise ClosureRuntimeContractError("Unavailable ANFIS bundle requires a failed module")
    if set(prepared).intersection(unavailable) or set(prepared).union(unavailable) != set(
        PRIMARY_MODULES
    ):
        raise ClosureRuntimeContractError("ANFIS availability evidence does not cover three modules")

    paths = _slot_paths(runtime, base_seed)
    forbidden_heavy = [paths["anfis_state_template"], *paths["models"].values()]
    forbidden_fit_only = [
        paths["anfis_training_curve_template"],
        paths["anfis_memberships_initial_template"],
        paths["anfis_memberships_final_template"],
    ]
    existing_forbidden = [
        _manifest_path(path)
        for path in (*forbidden_heavy, *forbidden_fit_only)
        if path.exists()
    ]
    if existing_forbidden:
        raise ClosureRuntimeContractError(
            "Unavailable ANFIS slot has pre-existing state/checkpoint/fit-only outputs: "
            f"{existing_forbidden}"
        )

    persisted_columns = tuple(
        str(value)
        for value in _runtime_section(_runtime_section(runtime, "anfis"), "sampling")[
            "persisted_sample_columns"
        ]
    )
    output_records: list[dict[str, Any]] = []
    sampling: dict[str, dict[str, Any]] = {}
    for module in PRIMARY_MODULES:
        if module in prepared:
            _, sample_keys, audit = prepared[module]
            sample_frame = sample_keys.loc[:, list(persisted_columns)].copy()
        else:
            audit = unavailable[module].audit
            sample_frame = pd.DataFrame(columns=persisted_columns)
        _write_csv_atomic(sample_frame, paths["samples"][module])
        output_records.append(
            {**_file_record(paths["samples"][module]), "role": "sample_keys", "module": module}
        )
        sampling[module] = dict(audit)

    metrics = pd.DataFrame(_sampling_metrics_rows(prepared, unavailable))
    _write_csv_atomic(metrics, paths["anfis_metrics_template"])
    output_records.append(
        {**_file_record(paths["anfis_metrics_template"]), "role": "module_metrics"}
    )

    failed_modules = [module for module in PRIMARY_MODULES if module in unavailable]
    report_lines = [
        "# Closure V1 adaptive ANFIS unavailable seed slot",
        "",
        f"- Base seed: `{base_seed}`",
        "- Slot status: `model_unavailable`",
        "- Failure reason: `insufficient_eligible_training_rows`",
        "- Replacement used: `False`",
        "- Model construction attempted: `False`",
        "- Fit attempted: `False`",
        "- Evaluation authorized: `False`",
        "- E0-U authorized: `False`",
        "",
        "| module | status | eligible rows | required rows | selected rows |",
        "|---|---|---:|---:|---:|",
    ]
    for row in metrics.to_dict(orient="records"):
        report_lines.append(
            f"| `{row['module']}` | `{row['status']}` | {row['eligible_universe_rows']} | "
            f"{row['required_rows']} | {row['selected_rows']} |"
        )
    _write_text_atomic("\n".join(report_lines) + "\n", paths["anfis_report_template"])
    output_records.append({**_file_record(paths["anfis_report_template"]), "role": "report"})

    lineage = {
        "audit_version": LINEAGE_AUDIT_VERSION,
        "status": "model_unavailable",
        "slot_status": "model_unavailable",
        "failure_reason": "insufficient_eligible_training_rows",
        "experiment_id": "closure_v1",
        "base_seed": base_seed,
        "modules": list(PRIMARY_MODULES),
        "failed_modules": failed_modules,
        "retain_failed_seed_slot": True,
        "replacement_used": False,
        "model_construction_attempted": False,
        "fit_attempted": False,
        "state_output_materialized": False,
        "state_artifact_emitted": False,
        "checkpoint_outputs_materialized": False,
        "failed_slot_replaced": False,
        "forbidden_primary_module_materialized": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "panel_anchor_joins": _join_audit_payload(join_audits),
        "source_scans": {
            name: {
                "materialized_rows": audit.materialized_rows,
                "returned_rows": audit.returned_rows,
                "boundary_crossing_rows": audit.boundary_crossing_rows,
                "role_counts": audit.role_counts,
            }
            for name, audit in scan_audits.items()
        },
        "zero_holdout_overlap": True,
    }
    _write_json_atomic(lineage, paths["anfis_lineage_audit_template"])
    output_records.append(
        {**_file_record(paths["anfis_lineage_audit_template"]), "role": "lineage_audit"}
    )

    payload = dict(manifest_base)
    payload.update(
        {
            "status": "completed",
            "slot_status": "model_unavailable",
            "fit_status": "not_attempted",
            "failure_reason": "insufficient_eligible_training_rows",
            "failed_modules": failed_modules,
            "retain_failed_seed_slot": True,
            "replacement_used": False,
            "failed_slot_replaced": False,
            "model_construction_attempted": False,
            "fit_attempted": False,
            "state_output_materialized": False,
            "state_artifact_emitted": False,
            "checkpoint_outputs_materialized": False,
            "module_metrics": metrics.to_dict(orient="records"),
            "sampling": sampling,
            "planned_unmaterialized_heavy_outputs": [
                _manifest_path(path) for path in forbidden_heavy
            ],
            "outputs": output_records,
        }
    )
    _write_json_atomic(payload, paths["anfis_manifest_template"])
    return payload


def anfis_dependency_paths_and_roles(
    *,
    runtime: Mapping[str, Any],
    runtime_config: Path,
    runtime_schema: Path,
    gate: DevelopmentGate,
) -> list[tuple[Path, str]]:
    projection = _runtime_section(_runtime_section(runtime, "anfis"), "source_projection")
    implementation_lock = _runtime_section(runtime, "implementation_lock")
    authority = _runtime_section(runtime, "authority")
    return [
        (runtime_config, "development_runtime_config"),
        (runtime_schema, "development_runtime_schema"),
        (
            resolve_repo_path(str(implementation_lock["lock_manifest_path"])),
            "development_runtime_lock",
        ),
        (
            resolve_repo_path(str(implementation_lock["lock_schema_path"])),
            "development_runtime_lock_schema",
        ),
        (
            resolve_repo_path(str(authority["common_origin_manifest_path"])),
            "common_origin",
        ),
        (
            resolve_repo_path(str(authority["common_origin_completion_manifest_path"])),
            "common_origin_completion_manifest",
        ),
        (resolve_repo_path(str(projection["panel_path"])), "restored_panel"),
        (
            resolve_repo_path(str(projection["expert_anchor_path"])),
            "restored_expert_anchor",
        ),
        (gate.assignment_path, "holdout_assignment"),
        (gate.holdout_manifest_path, "holdout_manifest"),
        (gate.protocol_lock_path, "protocol_lock"),
        (Path(__file__), "strict_anfis_state_adapter"),
        (
            PROJECT_ROOT / "src/experiments/build_closure_expert_state.py",
            "strict_expert_state_adapter",
        ),
        (
            PROJECT_ROOT / "src/experiments/closure_development_runtime_lock.py",
            "runtime_lock_validator",
        ),
        (
            PROJECT_ROOT / "src/experiments/closure_runtime_contract.py",
            "runtime_contract_validator",
        ),
        (
            PROJECT_ROOT / "src/experiments/closure_development_guard.py",
            "closure_development_guard",
        ),
        (PROJECT_ROOT / "src/experiments/closure_contract.py", "closure_contract"),
        (
            PROJECT_ROOT / "src/fuzzy/adaptive_anfis.py",
            "adaptive_anfis_implementation",
        ),
    ]


def _validate_restored_dependency_snapshot(
    before: Mapping[str, Mapping[str, Any]],
    runtime: Mapping[str, Any],
) -> None:
    projection = _runtime_section(_runtime_section(runtime, "anfis"), "source_projection")
    panel_path = _manifest_path(resolve_repo_path(str(projection["panel_path"])))
    anchor_path = _manifest_path(resolve_repo_path(str(projection["expert_anchor_path"])))
    if before.get(panel_path, {}).get("sha256") != EXPECTED_PANEL_SHA256:
        raise ClosureRuntimeContractError("Restored ANFIS panel changed after E0-DL authorization")
    if before.get(anchor_path, {}).get("sha256") != EXPECTED_EXPERT_STATE_SHA256:
        raise ClosureRuntimeContractError(
            "Restored ANFIS expert anchor changed after E0-DL authorization"
        )


def materialize_anfis_seed_slot(
    *,
    base_seed: int,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    runtime_schema: Path = DEFAULT_RUNTIME_SCHEMA,
) -> dict[str, Any]:
    # The published E0-DL validator is intentionally invoked inside the
    # programmatic materializer.  Callers cannot inject an authorization
    # summary as ordinary data and bypass its publication/physical checks.
    authorization = authorize_development_fit(
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
    )
    runtime, runtime_summary = load_and_validate_development_runtime(
        runtime_config,
        runtime_schema,
        require_restored_development_sources=True,
    )
    cpu_execution_policy = configure_torch_cpu_execution_policy(runtime)
    _validate_authorization(authorization, runtime=runtime)
    slots = validate_seed_slots(_runtime_section(runtime, "seeds")["ordered_slots"])
    if base_seed not in {slot["base_seed"] for slot in slots}:
        raise ClosureRuntimeContractError(f"Unregistered Closure V1 seed: {base_seed}")
    gate = load_development_gate()
    dependencies = anfis_dependency_paths_and_roles(
        runtime=runtime,
        runtime_config=resolve_repo_path(runtime_config),
        runtime_schema=resolve_repo_path(runtime_schema),
        gate=gate,
    )
    before = _dependency_snapshot(dependencies)
    _validate_restored_dependency_snapshot(before, runtime)
    require_pristine_anfis_seed_slot(runtime, base_seed)
    views = load_joined_anfis_surface(runtime=runtime, gate=gate)
    surface = views.full_development
    join_audits = {
        "training_candidates": views.training_candidate_join,
        "full_development": views.full_development_join,
    }
    scan_audits = views.source_scans
    substreams = anfis_module_substreams(base_seed)
    prepared_samples, unavailable_modules = prepare_slot_module_samples(
        views.training_candidates,
        runtime=runtime,
        gate=gate,
        substreams=substreams,
    )
    state_contract = _runtime_section(runtime, "primary_autoregressive_state")
    script_record = {**_file_record(Path(__file__)), "role": "generating_script"}
    input_records = [
        dict(record)
        for record in before.values()
        if record.get("role") != "strict_anfis_state_adapter"
    ]
    common_manifest_base = {
        "manifest_version": MANIFEST_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "closure_v1",
        "surface_id": str(state_contract["surface_id"]),
        "model_id": "F1",
        "consumer_model_id": "P1",
        "base_seed": base_seed,
        "module_substreams": substreams,
        "future_outcomes_accessed": False,
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "authorization": dict(authorization),
        "runtime": {
            "config_path": runtime_summary["config_path"],
            "config_sha256": runtime_summary["config_sha256"],
            "schema_path": runtime_summary["schema_path"],
            "schema_sha256": runtime_summary["schema_sha256"],
        },
        "cpu_execution_policy": cpu_execution_policy,
        "script": script_record,
        "inputs": input_records,
        "panel_anchor_joins": _join_audit_payload(join_audits),
        "dependencies": list(before.values()),
        "completion_marker_written_last": True,
    }
    if unavailable_modules:
        _assert_unchanged(before, dependencies)
        unavailable_base = {
            **common_manifest_base,
            "counts": {
                "state_rows": 0,
                "joined_development_rows": len(surface),
                "joined_training_candidate_rows": len(views.training_candidates),
                "development_locations": int(
                    surface.loc[:, ["source_id", "site_id"]].drop_duplicates().shape[0]
                ),
                "unavailable_modules": len(unavailable_modules),
            },
        }
        payload = write_anfis_unavailable_slot_bundle(
            prepared_samples,
            unavailable_modules,
            runtime=runtime,
            base_seed=base_seed,
            join_audits=join_audits,
            scan_audits=scan_audits,
            manifest_base=unavailable_base,
        )
        manifest_path = _slot_paths(runtime, base_seed)["anfis_manifest_template"]
        print(f"wrote retained unavailable slot {manifest_path}")
        return payload

    result_rows: dict[str, ModuleFitResult] = {}
    for module in PRIMARY_MODULES:
        result_rows[module] = fit_primary_module(
            surface,
            runtime=runtime,
            gate=gate,
            module=module,
            module_seed=substreams[module],
            prepared_sample=prepared_samples[module],
        )
    state = build_adaptive_state(surface, result_rows, runtime=runtime, gate=gate)
    _assert_unchanged(before, dependencies)

    manifest_base = {
        **common_manifest_base,
        "counts": {
            "state_rows": len(state),
            "joined_development_rows": len(surface),
            "joined_training_candidate_rows": len(views.training_candidates),
            "development_locations": int(
                state.loc[:, ["source_id", "site_id"]].drop_duplicates().shape[0]
            ),
            "delta_previous_month_missing": int(state["delta_previous_month_missing"].sum()),
        },
    }
    payload = write_anfis_slot_bundle(
        state,
        result_rows,
        runtime=runtime,
        base_seed=base_seed,
        join_audits=join_audits,
        scan_audits=scan_audits,
        manifest_base=manifest_base,
    )
    manifest_path = _slot_paths(runtime, base_seed)["anfis_manifest_template"]
    print(f"wrote {manifest_path}")
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-seed", type=int, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_RUNTIME_SCHEMA)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, Any]:
    return materialize_anfis_seed_slot(
        base_seed=args.base_seed,
        runtime_config=args.config,
        runtime_schema=args.schema,
    )


def main(argv: Sequence[str] | None = None) -> None:
    run(parse_args(argv))


if __name__ == "__main__":
    main()
