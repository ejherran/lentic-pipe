#!/usr/bin/env python
"""Fit the Closure V1 development-only B0/B1/B2 baseline bundle.

The production CLI is deliberately closed: it either performs a read-only
preflight or consumes the single baseline-development authorization.  It does
not calibrate, evaluate the holdout, create E0-M, run DVC, or open post-2021
outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import stat
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import joblib
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error, mean_squared_error
from threadpoolctl import threadpool_limits

from src.experiments.closure_development_guard import assert_development_frame, load_development_gate


RUNTIME_PATH = Path("configs/closure_v1/baseline_development_runtime.yaml")
PATCH_LOCK_PATH = Path("reports/closure_v1/00_protocol/baseline_development_patch_lock.json")
PATCH_COMPANION_PATH = Path(
    "reports/closure_v1/00_protocol/baseline_development_patch_lock_manifest.json"
)
COMMON_PATH = Path("data/closure_v1/common_origin_manifest.parquet")
PANEL_PATH = Path("data/panel/panel_monthly_v0.parquet")
TARGETS_PATH = Path("data/targets/monthly_targets_model_v0.parquet")
OUTCOME_ACCESS_LOG = Path("reports/closure_v1/00_protocol/outcome_access_log.jsonl")
RUNNER_SOURCE_PATH = Path("src/experiments/fit_closure_baselines.py")

MODEL_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
HORIZONS = (1, 2, 3)
TECHNICAL_SEED = 1729
CANDIDATES = ("logistic_sgd", "hist_gradient_boosting_classifier")

KEY_COLUMNS = [
    "source_id",
    "site_id",
    "common_origin_id",
    "evaluation_unit_id",
    "holdout_group_id",
    "assignment_role",
    "time_role",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
]
TARGET_JOIN_COLUMNS = [
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
]
TARGET_PROJECTION = tuple(TARGET_JOIN_COLUMNS + ["bloom_h", "target_risk_chla_h"])
STATE_COLUMNS = ["yN_adaptive", "yF_adaptive", "yT_no_chla_adaptive"]
DERIVED_SEASON_COLUMNS = [
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
]
EXPECTED_COMMON_ROWS = 29196
EXPECTED_INTENT_ORIGINS = 9732
EXPECTED_COMPLETE_ORIGINS = {"training": 5932, "model_selection": 658, "calibration_threshold": 224}
STRICT_MONTH = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")

RAW_PREDICTION_COLUMNS = (
    "surface_id",
    "model_id",
    "source_id",
    "site_id",
    "common_origin_id",
    "evaluation_unit_id",
    "holdout_group_id",
    "assignment_role",
    "time_role",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "technical_seed",
    "model_seed",
    "upstream_state_seed",
    "candidate",
    "selected_family",
    "availability_status",
    "failure_reason",
    "score_semantics",
    "raw_score",
    "predicted_bloom_probability",
)
RAW_STRING_COLUMNS = RAW_PREDICTION_COLUMNS[:11] + RAW_PREDICTION_COLUMNS[15:16] + RAW_PREDICTION_COLUMNS[17:20]
RAW_NON_NULL_STRING_COLUMNS = set(RAW_STRING_COLUMNS)
RAW_CANONICAL_KEY_COLUMNS = (
    "source_id",
    "site_id",
    "origin_year_month",
    "horizon_months",
    "target_year_month",
    "common_origin_id",
    "evaluation_unit_id",
)


class BaselineDevelopmentError(RuntimeError):
    """Raised when the closed baseline-development contract is violated."""


@dataclass(frozen=True)
class OwnedOutput:
    path: Path
    device: int
    inode: int
    bytes: int
    sha256: str
    directory_descriptor: int


@dataclass(frozen=True)
class OwnedGuard:
    path: Path
    device: int
    inode: int
    file_descriptor: int
    directory_descriptor: int


def raw_prediction_contract() -> dict[str, Any]:
    columns: list[dict[str, Any]] = []
    for name in RAW_PREDICTION_COLUMNS:
        if name in RAW_STRING_COLUMNS:
            dtype = "string"
            nullable = False
        elif name == "horizon_months":
            dtype = "int16"
            nullable = False
        elif name in {"technical_seed", "model_seed", "upstream_state_seed"}:
            dtype = "int64"
            nullable = name != "technical_seed"
        elif name == "selected_family":
            dtype = "bool"
            nullable = False
        else:
            dtype = "float64"
            nullable = True
        columns.append({"name": name, "dtype": dtype, "nullable": nullable})
    return {
        "columns": columns,
        "canonical_sort_keys": [
            "model_seed_rank",
            "upstream_state_seed_rank",
            "candidate_rank",
            *RAW_CANONICAL_KEY_COLUMNS,
        ],
        "model_seed_order": list(MODEL_SEEDS),
        "candidate_order": list(CANDIDATES),
        "availability_status_values": ["success", "model_unavailable"],
        "success_score_policy": "raw_score_and_probability_finite_in_closed_unit_interval",
        "unavailable_score_policy": "raw_score_and_probability_both_null",
        "B0_seed_policy": "technical_seed_only",
        "B1_seed_policy": "upstream_state_seed_only",
        "B2_seed_policy": "model_seed_only",
        "B1_probability_semantics": "uncalibrated_chla_free_irc_persistence_probability",
    }


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_record(path: Path, *, logical_path: Path | None = None) -> dict[str, Any]:
    """Hash one repository file through a no-follow, identity-pinned descriptor."""
    directory_descriptor, lexical_path = _open_real_repository_parent(path, create=False)
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            named_before = os.stat(
                lexical_path.name,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
            descriptor = os.open(lexical_path.name, flags, dir_fd=directory_descriptor)
        except OSError as exc:
            raise BaselineDevelopmentError(
                f"Input cannot be opened without following links: {path}"
            ) from exc
        opened_before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(named_before.st_mode)
            or not stat.S_ISREG(opened_before.st_mode)
            or (named_before.st_dev, named_before.st_ino)
            != (opened_before.st_dev, opened_before.st_ino)
        ):
            raise BaselineDevelopmentError(f"Input is not one stable regular file: {path}")
        before_state = (
            opened_before.st_dev,
            opened_before.st_ino,
            opened_before.st_size,
            opened_before.st_mtime_ns,
            opened_before.st_ctime_ns,
        )
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        opened_after = os.fstat(descriptor)
        named_after = os.stat(
            lexical_path.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        after_open_state = (
            opened_after.st_dev,
            opened_after.st_ino,
            opened_after.st_size,
            opened_after.st_mtime_ns,
            opened_after.st_ctime_ns,
        )
        after_name_state = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if before_state != after_open_state or before_state != after_name_state or size != opened_after.st_size:
            raise BaselineDevelopmentError(f"Input changed while it was hashed: {path}")
        record_path = logical_path or (
            lexical_path.relative_to(PROJECT_ROOT) if lexical_path.is_absolute() else lexical_path
        )
        return {
            "path": record_path.as_posix(),
            "bytes": int(size),
            "sha256": digest.hexdigest(),
        }
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_descriptor)


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        normalized: dict[str, Any] = {}
        for key, value in record.items():
            if value is None or value is pd.NA:
                normalized[str(key)] = None
                continue
            if isinstance(value, np.generic):
                value = value.item()
            if isinstance(value, float) and not math.isfinite(value):
                normalized[str(key)] = None
            else:
                normalized[str(key)] = value
        records.append(normalized)
    return records


def _manifest_json_bytes(payload: Mapping[str, Any]) -> bytes:
    keys = tuple(payload)
    if not keys or keys[-1] != "completion_marker_written_last":
        raise BaselineDevelopmentError("Manifest completion marker must be the last top-level key")
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def runtime_version_record() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "numpy": distribution_version("numpy"),
        "pandas": distribution_version("pandas"),
        "pyarrow": distribution_version("pyarrow"),
        "scikit_learn": distribution_version("scikit-learn"),
        "joblib": distribution_version("joblib"),
        "threadpoolctl": distribution_version("threadpoolctl"),
        "threadpool_limit": 1,
    }


def load_runtime_contract(path: Path = RUNTIME_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BaselineDevelopmentError("Baseline runtime must be a YAML mapping")
    if payload.get("schema_version") != "closure_baseline_development_runtime_v1":
        raise BaselineDevelopmentError("Unexpected baseline runtime schema_version")
    if payload.get("experiment_id") != "closure_v1" or payload.get("gate") != "E0-MP":
        raise BaselineDevelopmentError("Baseline runtime identity drifted")
    if payload.get("status") != "ready_to_lock":
        raise BaselineDevelopmentError("Baseline runtime is not ready_to_lock")
    b2 = payload.get("models", {}).get("B2", {})
    if (
        b2.get("candidate_slot_count") != 30
        or b2.get("maximum_pipeline_count") != 30
        or b2.get("exact_preprocessor_record_count") != 30
    ):
        raise BaselineDevelopmentError("Baseline B2 slot/output policy drifted")
    outputs = payload.get("outputs", {})
    if (
        outputs.get("exact_raw_prediction_rows") != 467136
        or outputs.get("minimum_final_path_count") != 39
        or outputs.get("maximum_final_path_count") != 69
        or outputs.get("raw_prediction_contract") != raw_prediction_contract()
    ):
        raise BaselineDevelopmentError("Baseline raw/output contract drifted")
    if payload.get("reproducibility") != {
        "execution_device": "cpu",
        "threadpool_limit": 1,
        "dependency_files": ["pyproject.toml", "poetry.lock"],
        "runtime_versions_recorded_in_manifest": True,
    }:
        raise BaselineDevelopmentError("Baseline reproducibility policy drifted")
    return payload


def physical_feature_columns(contract: Mapping[str, Any]) -> list[str]:
    columns = list(contract["models"]["B2"]["physical_feature_columns"])
    if len(columns) != 38 or len(set(columns)) != 38:
        raise BaselineDevelopmentError("B2 must declare exactly 38 unique physical features")
    lowered = "\n".join(columns).lower()
    if "chla" in lowered or "chlorophyll" in lowered or "risk_chla" in lowered:
        raise BaselineDevelopmentError("B2 physical features contain forbidden chlorophyll lineage")
    return columns


def exact_feature_columns(contract: Mapping[str, Any]) -> list[str]:
    physical = physical_feature_columns(contract)
    derived = list(contract["models"]["B2"]["derived_calendar_columns"])
    if derived != DERIVED_SEASON_COLUMNS:
        raise BaselineDevelopmentError("B2 derived seasonality columns drifted")
    result = physical + derived
    benchmark = yaml.safe_load(Path("configs/closure_v1/model_benchmark.yaml").read_text(encoding="utf-8"))
    expected = list(benchmark["models"]["B2"]["feature_allowlist"])
    if result != expected or len(result) != 42:
        raise BaselineDevelopmentError("B2 feature order differs from model_benchmark.yaml")
    return result


def derive_calendar_features(months: pd.Series) -> pd.DataFrame:
    values = months.astype(str)
    if not bool(values.map(lambda value: bool(STRICT_MONTH.fullmatch(value))).all()):
        raise BaselineDevelopmentError("Invalid YYYY-MM in B2 calendar derivation")
    month_number = values.str.slice(5, 7).astype("int16").to_numpy(dtype="float64")
    angle = 2.0 * math.pi * (month_number - 1.0) / 12.0
    return pd.DataFrame(
        {
            "season_sin_annual": np.sin(angle).astype("float32"),
            "season_cos_annual": np.cos(angle).astype("float32"),
            "season_sin_semiannual": np.sin(2.0 * angle).astype("float32"),
            "season_cos_semiannual": np.cos(2.0 * angle).astype("float32"),
        },
        index=months.index,
    )


def derive_b1_score(frame: pd.DataFrame) -> pd.Series:
    missing = sorted(set(STATE_COLUMNS).difference(frame.columns))
    if missing:
        raise BaselineDevelopmentError(f"B1 state is missing columns: {missing}")
    values = frame[STATE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    finite = np.isfinite(values.to_numpy(dtype="float64")).all(axis=1)
    result = pd.Series(np.nan, index=frame.index, dtype="float64")
    score = (values["yN_adaptive"] + (1.0 - values["yF_adaptive"]) + values["yT_no_chla_adaptive"]) / 3.0
    result.loc[finite] = score.loc[finite].clip(0.0, 1.0)
    return result


def _binary_bloom_labels(values: pd.Series, *, context: str) -> np.ndarray:
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.isna().any() or not numeric.isin([0, 1]).all():
        raise BaselineDevelopmentError(f"{context} bloom labels are not exact binary values")
    return numeric.to_numpy(dtype="int8")


def select_b2_families(metrics: pd.DataFrame, *, tolerance: float = 0.001) -> pd.DataFrame:
    required = {"candidate", "model_seed", "horizon_months", "brier", "pr_auc", "fit_status"}
    missing = sorted(required.difference(metrics.columns))
    if missing:
        raise BaselineDevelopmentError(f"B2 metrics are missing selection columns: {missing}")
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        candidates: list[dict[str, Any]] = []
        for candidate in CANDIDATES:
            subset = metrics.loc[
                (metrics["horizon_months"] == horizon) & (metrics["candidate"] == candidate)
            ].copy()
            seeds = set(pd.to_numeric(subset["model_seed"], errors="coerce").dropna().astype(int))
            finite = (
                len(subset) == len(MODEL_SEEDS)
                and seeds == set(MODEL_SEEDS)
                and subset["fit_status"].eq("success").all()
                and np.isfinite(pd.to_numeric(subset["brier"], errors="coerce")).all()
                and np.isfinite(pd.to_numeric(subset["pr_auc"], errors="coerce")).all()
            )
            if finite:
                candidates.append(
                    {
                        "candidate": candidate,
                        "mean_brier": float(subset["brier"].mean()),
                        "mean_pr_auc": float(subset["pr_auc"].mean()),
                    }
                )
        if not candidates:
            rows.append(
                {
                    "horizon_months": horizon,
                    "selected_candidate": pd.NA,
                    "selection_status": "model_unavailable",
                    "failure_reason": "no_candidate_with_five_finite_seed_metrics",
                    "mean_brier": np.nan,
                    "mean_pr_auc": np.nan,
                }
            )
            continue
        minimum = min(record["mean_brier"] for record in candidates)
        retained = [record for record in candidates if record["mean_brier"] <= minimum + tolerance]
        maximum_pr = max(record["mean_pr_auc"] for record in retained)
        retained = [record for record in retained if np.isclose(record["mean_pr_auc"], maximum_pr, rtol=0.0, atol=1e-15)]
        retained.sort(key=lambda record: (record["candidate"] != "logistic_sgd", record["candidate"]))
        chosen = retained[0]
        rows.append(
            {
                "horizon_months": horizon,
                "selected_candidate": chosen["candidate"],
                "selection_status": "selected",
                "failure_reason": "",
                "mean_brier": chosen["mean_brier"],
                "mean_pr_auc": chosen["mean_pr_auc"],
            }
        )
    return pd.DataFrame(rows).sort_values("horizon_months").reset_index(drop=True)


def _require_effective_authority() -> dict[str, Any]:
    from src.experiments.closure_baseline_development_patch import (
        require_baseline_development_authority,
    )

    return require_baseline_development_authority(verify_remote=True)


def _validated_authority_snapshot(authority: Mapping[str, Any]) -> dict[str, Any]:
    required_true = (
        "baseline_one_shot_authorized",
        "b0_fit_authorized",
        "b1_execution_authorized",
        "b2_fit_authorized",
    )
    required_false = (
        "calibration_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "dvc_commands_authorized",
        "network_authorized",
        "outcome_access_authorized",
        "future_outcomes_accessed",
    )
    if authority.get("gate") != "E0-MP" or authority.get("status") != "effective_preflight_passed":
        raise BaselineDevelopmentError("Published E0-MP authority identity/status drifted")
    if any(authority.get(name) is not True for name in required_true):
        raise BaselineDevelopmentError("Published E0-MP authority is incomplete")
    if any(authority.get(name) is not False for name in required_false):
        raise BaselineDevelopmentError("Published E0-MP authority broadened a forbidden operation")
    if authority.get("development_target_access_end") != "2020-12" or authority.get(
        "target_projection"
    ) != list(TARGET_PROJECTION):
        raise BaselineDevelopmentError("Published E0-MP target-access authority drifted")
    sha_fields = (
        "lock_sha256",
        "companion_sha256",
        "runtime_sha256",
        "h_components_sha256",
        "physical_inputs_sha256",
        "runner_sha256",
    )
    if any(
        not isinstance(authority.get(name), str)
        or re.fullmatch(r"[0-9a-f]{64}", str(authority.get(name))) is None
        for name in sha_fields
    ):
        raise BaselineDevelopmentError("Published E0-MP authority hash binding is incomplete")
    commit_fields = ("h_patch_head", "p_patch_head")
    if any(
        not isinstance(authority.get(name), str)
        or re.fullmatch(r"[0-9a-f]{40}", str(authority.get(name))) is None
        for name in commit_fields
    ):
        raise BaselineDevelopmentError("Published E0-MP authority commit binding is incomplete")
    keys = (
        "gate",
        "status",
        *required_true,
        *required_false,
        "development_target_access_end",
        "target_projection",
        *commit_fields,
        *sha_fields,
    )
    return {name: authority[name] for name in keys}


def _output_paths(contract: Mapping[str, Any]) -> tuple[list[Path], Path]:
    output = contract["outputs"]
    paths = [Path(value) for value in output["raw_score_parquets"].values()]
    for seed in MODEL_SEEDS:
        for candidate in CANDIDATES:
            for horizon in HORIZONS:
                paths.append(Path(output["b2_pipeline_template"].format(model_seed=seed, candidate=candidate, horizon=horizon)))
                paths.append(
                    Path(output["b2_preprocessor_template"].format(model_seed=seed, candidate=candidate, horizon=horizon))
                )
    light = {name: Path(value) for name, value in output["light_bundle"].items()}
    manifest = light.pop("manifest")
    paths.extend(light.values())
    return paths, manifest


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _assert_absent_namespace(contract: Mapping[str, Any], *, allow_guard: bool = False) -> None:
    paths, manifest = _output_paths(contract)
    extras = [manifest, Path(contract["outputs"]["publication"]["guard_path"])]
    extras.extend(Path(path.as_posix() + ".tmp") for path in paths + [manifest])
    guard = Path(contract["outputs"]["publication"]["guard_path"])
    present = [
        path.as_posix()
        for path in paths + extras
        if _lexists(path) and not (allow_guard and path == guard)
    ]
    if present:
        raise BaselineDevelopmentError(f"Baseline output namespace is not empty: {present}")
    _assert_future_dvc_namespace_absent(contract)
    if _lexists(OUTCOME_ACCESS_LOG):
        raise BaselineDevelopmentError("Outcome-access log must remain absent before E0-M")


def _assert_future_dvc_namespace_absent(contract: Mapping[str, Any]) -> None:
    pointers = [Path(path) for path in contract["dvc"]["future_pointer_paths"]]
    paths = pointers + [Path(path.as_posix() + ".tmp") for path in pointers]
    present = [path.as_posix() for path in paths if _lexists(path)]
    if present:
        raise BaselineDevelopmentError(
            f"Future baseline DVC pointer namespace is not empty: {present}"
        )


def _open_real_repository_parent(
    path: Path,
    *,
    create: bool,
    directory_mode: int = 0o755,
) -> tuple[int, Path]:
    """Anchor a repository parent without following or trusting path ancestors."""
    try:
        repository_root = PROJECT_ROOT.resolve(strict=True)
        lexical_path = Path(
            os.path.abspath(path if path.is_absolute() else PROJECT_ROOT / path)
        )
        relative_parent = lexical_path.parent.relative_to(repository_root)
    except (FileNotFoundError, ValueError) as exc:
        raise BaselineDevelopmentError(f"Path escapes the repository: {path}") from exc
    directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    directory_flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(repository_root, directory_flags)
    except OSError as exc:
        raise BaselineDevelopmentError("Repository root cannot be opened safely") from exc
    try:
        for part in relative_parent.parts:
            try:
                metadata = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                if not create:
                    raise BaselineDevelopmentError(
                        f"Required repository parent is absent: {lexical_path.parent}"
                    )
                try:
                    os.mkdir(part, mode=directory_mode, dir_fd=descriptor)
                except FileExistsError:
                    pass
                metadata = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(metadata.st_mode):
                raise BaselineDevelopmentError(
                    f"Repository ancestor is not a real directory: {lexical_path.parent}"
                )
            child = os.open(part, directory_flags, dir_fd=descriptor)
            opened = os.fstat(child)
            if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                os.close(child)
                raise BaselineDevelopmentError(
                    f"Repository ancestor identity drifted: {lexical_path.parent}"
                )
            previous = descriptor
            descriptor = child
            os.close(previous)
        opened_parent = os.fstat(descriptor)
        lexical_parent = lexical_path.parent.lstat()
        if (
            not stat.S_ISDIR(lexical_parent.st_mode)
            or (opened_parent.st_dev, opened_parent.st_ino)
            != (lexical_parent.st_dev, lexical_parent.st_ino)
        ):
            raise BaselineDevelopmentError(
                f"Repository parent identity drifted: {lexical_path.parent}"
            )
        return descriptor, lexical_path
    except BaseException:
        os.close(descriptor)
        raise


def _unlink_name_if_owned(
    directory_descriptor: int,
    name: str,
    *,
    device: int,
    inode: int,
) -> bool:
    try:
        metadata = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise BaselineDevelopmentError(f"Cannot inspect owned artifact: {name}") from exc
    if (
        stat.S_ISREG(metadata.st_mode)
        and (metadata.st_dev, metadata.st_ino) == (device, inode)
    ):
        os.unlink(name, dir_fd=directory_descriptor)
        return True
    return False


def _hash_owned_name(owned: OwnedOutput) -> tuple[int, str]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        named_before = os.stat(
            owned.path.name,
            dir_fd=owned.directory_descriptor,
            follow_symlinks=False,
        )
        descriptor = os.open(
            owned.path.name,
            flags,
            dir_fd=owned.directory_descriptor,
        )
        opened_before = os.fstat(descriptor)
        expected = (owned.device, owned.inode)
        if (
            not stat.S_ISREG(named_before.st_mode)
            or not stat.S_ISREG(opened_before.st_mode)
            or (named_before.st_dev, named_before.st_ino) != expected
            or (opened_before.st_dev, opened_before.st_ino) != expected
        ):
            raise BaselineDevelopmentError(
                f"Owned baseline artifact identity drifted: {owned.path}"
            )
        before_state = (
            opened_before.st_dev,
            opened_before.st_ino,
            opened_before.st_size,
            opened_before.st_mtime_ns,
            opened_before.st_ctime_ns,
        )
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        opened_after = os.fstat(descriptor)
        named_after = os.stat(
            owned.path.name,
            dir_fd=owned.directory_descriptor,
            follow_symlinks=False,
        )
        after_open = (
            opened_after.st_dev,
            opened_after.st_ino,
            opened_after.st_size,
            opened_after.st_mtime_ns,
            opened_after.st_ctime_ns,
        )
        after_name = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if before_state != after_open or before_state != after_name or size != opened_after.st_size:
            raise BaselineDevelopmentError(
                f"Owned baseline artifact changed while hashing: {owned.path}"
            )
        return size, digest.hexdigest()
    except OSError as exc:
        raise BaselineDevelopmentError(
            f"Owned baseline artifact cannot be opened safely: {owned.path}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _write_output_no_clobber_owned(
    path: Path,
    writer: Any,
    *,
    binary: bool,
) -> OwnedOutput:
    """Publish one inode with an anchored parent and retain rollback ownership."""
    directory_descriptor, lexical_path = _open_real_repository_parent(path, create=True)
    temporary_name = lexical_path.name + ".tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    device: int | None = None
    inode: int | None = None
    committed = False
    try:
        try:
            descriptor = os.open(
                temporary_name,
                flags,
                0o644,
                dir_fd=directory_descriptor,
            )
        except FileExistsError as exc:
            raise BaselineDevelopmentError(
                f"Refusing to overwrite temporary artifact: {path}.tmp"
            ) from exc
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise BaselineDevelopmentError(f"Temporary artifact is not regular: {path}.tmp")
        device, inode = metadata.st_dev, metadata.st_ino
        duplicate = os.dup(descriptor)
        try:
            if binary:
                handle = os.fdopen(duplicate, "wb")
            else:
                handle = os.fdopen(duplicate, "w", encoding="utf-8", newline="")
        except BaseException:
            os.close(duplicate)
            raise
        with handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        temporary = os.stat(
            temporary_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        parent_opened = os.fstat(directory_descriptor)
        parent_lexical = lexical_path.parent.lstat()
        if (
            not stat.S_ISREG(temporary.st_mode)
            or (temporary.st_dev, temporary.st_ino) != (device, inode)
            or not stat.S_ISDIR(parent_lexical.st_mode)
            or (parent_lexical.st_dev, parent_lexical.st_ino)
            != (parent_opened.st_dev, parent_opened.st_ino)
        ):
            raise BaselineDevelopmentError(f"Temporary artifact identity drifted: {path}.tmp")
        try:
            os.link(
                temporary_name,
                lexical_path.name,
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise BaselineDevelopmentError(f"Refusing to overwrite final artifact: {path}") from exc
        final = os.stat(
            lexical_path.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        parent_lexical = lexical_path.parent.lstat()
        if (
            not stat.S_ISREG(final.st_mode)
            or (final.st_dev, final.st_ino) != (device, inode)
            or (parent_lexical.st_dev, parent_lexical.st_ino)
            != (parent_opened.st_dev, parent_opened.st_ino)
        ):
            _unlink_name_if_owned(
                directory_descriptor,
                lexical_path.name,
                device=device,
                inode=inode,
            )
            raise BaselineDevelopmentError(f"Final artifact identity drifted: {path}")
        if not _unlink_name_if_owned(
            directory_descriptor,
            temporary_name,
            device=device,
            inode=inode,
        ):
            _unlink_name_if_owned(
                directory_descriptor,
                lexical_path.name,
                device=device,
                inode=inode,
            )
            raise BaselineDevelopmentError(f"Temporary artifact changed before cleanup: {path}.tmp")
        os.fsync(directory_descriptor)
        os.close(descriptor)
        descriptor = None
        provisional = OwnedOutput(
            path=lexical_path,
            device=device,
            inode=inode,
            bytes=0,
            sha256="",
            directory_descriptor=directory_descriptor,
        )
        size, sha256 = _hash_owned_name(provisional)
        committed = True
        return OwnedOutput(
            path=lexical_path,
            device=device,
            inode=inode,
            bytes=size,
            sha256=sha256,
            directory_descriptor=directory_descriptor,
        )
    finally:
        active_error = sys.exc_info()[1]
        cleanup_errors: list[Exception] = []
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as exc:
                cleanup_errors.append(exc)
        if not committed:
            if device is not None and inode is not None:
                for name in (lexical_path.name, temporary_name):
                    try:
                        _unlink_name_if_owned(
                            directory_descriptor,
                            name,
                            device=device,
                            inode=inode,
                        )
                    except (BaselineDevelopmentError, OSError) as exc:
                        cleanup_errors.append(exc)
                try:
                    os.fsync(directory_descriptor)
                except OSError as exc:
                    cleanup_errors.append(exc)
            try:
                os.close(directory_descriptor)
            except OSError as exc:
                cleanup_errors.append(exc)
        if cleanup_errors:
            cleanup_error = BaselineDevelopmentError(
                "Baseline artifact cleanup could not be completed safely"
            )
            cleanup_error.add_note(
                "Cleanup failures: "
                + "; ".join(f"{type(error).__name__}: {error}" for error in cleanup_errors)
            )
            if active_error is not None:
                raise cleanup_error from active_error
            raise cleanup_error from cleanup_errors[0]


def _owned_file_record(owned: OwnedOutput, *, logical_path: Path | None = None) -> dict[str, Any]:
    size, sha256 = _hash_owned_name(owned)
    if size != owned.bytes or sha256 != owned.sha256:
        raise BaselineDevelopmentError(f"Owned output bytes drifted: {owned.path}")
    record_path = logical_path or owned.path.relative_to(PROJECT_ROOT)
    return {"path": record_path.as_posix(), "bytes": size, "sha256": sha256}


class OutputTransaction:
    """Own all published baseline inodes until manifest-last commit succeeds."""

    def __init__(self) -> None:
        self._owned: list[OwnedOutput] = []

    def __enter__(self) -> OutputTransaction:
        return self

    def _publish(self, path: Path, writer: Any, *, binary: bool) -> OwnedOutput:
        owned = _write_output_no_clobber_owned(path, writer, binary=binary)
        self._owned.append(owned)
        return owned

    def publish_bytes(self, payload: bytes, path: Path) -> OwnedOutput:
        return self._publish(path, lambda handle: handle.write(payload), binary=True)

    def publish_arrow_table(self, table: pa.Table, path: Path) -> OwnedOutput:
        return self._publish(
            path,
            lambda handle: pq.write_table(
                table,
                handle,
                compression="zstd",
                use_dictionary=False,
            ),
            binary=True,
        )

    def publish_joblib(self, payload: Mapping[str, Any], path: Path) -> OwnedOutput:
        return self._publish(path, lambda handle: joblib.dump(dict(payload), handle), binary=True)

    def file_record(self, owned: OwnedOutput, *, logical_path: Path | None = None) -> dict[str, Any]:
        if owned not in self._owned:
            raise BaselineDevelopmentError("Output record is not owned by this transaction")
        return _owned_file_record(owned, logical_path=logical_path)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        commit_error: BaselineDevelopmentError | None = None
        rollback_errors: list[Exception] = []
        if exc_type is None:
            for owned in self._owned:
                try:
                    _owned_file_record(owned)
                    opened_parent = os.fstat(owned.directory_descriptor)
                    lexical_parent = owned.path.parent.lstat()
                except (BaselineDevelopmentError, FileNotFoundError, OSError) as error:
                    commit_error = BaselineDevelopmentError(
                        f"Baseline output disappeared or drifted before commit: {owned.path}"
                    )
                    commit_error.add_note(str(error))
                    break
                if (
                    not stat.S_ISDIR(lexical_parent.st_mode)
                    or (opened_parent.st_dev, opened_parent.st_ino)
                    != (lexical_parent.st_dev, lexical_parent.st_ino)
                ):
                    commit_error = BaselineDevelopmentError(
                        f"Baseline output parent drifted before commit: {owned.path.parent}"
                    )
                    break
        if exc_type is not None or commit_error is not None:
            for owned in reversed(self._owned):
                try:
                    if _unlink_name_if_owned(
                        owned.directory_descriptor,
                        owned.path.name,
                        device=owned.device,
                        inode=owned.inode,
                    ):
                        os.fsync(owned.directory_descriptor)
                except (BaselineDevelopmentError, OSError) as cleanup_error:
                    rollback_errors.append(cleanup_error)
        for owned in self._owned:
            try:
                os.close(owned.directory_descriptor)
            except OSError as cleanup_error:
                if exc_type is not None or commit_error is not None:
                    rollback_errors.append(cleanup_error)
        self._owned.clear()
        if rollback_errors:
            rollback_error = BaselineDevelopmentError(
                "Baseline output rollback could not be completed safely"
            )
            rollback_error.add_note(
                "Rollback failures: "
                + "; ".join(f"{type(error).__name__}: {error}" for error in rollback_errors)
            )
            if exc is not None:
                raise rollback_error from exc
            if commit_error is not None:
                raise rollback_error from commit_error
            raise rollback_error from rollback_errors[0]
        if commit_error is not None:
            raise commit_error
        return False


def _common_frame() -> pd.DataFrame:
    columns = KEY_COLUMNS + ["input_eligible", "target_evaluable", "complete_targets_evaluable"]
    frame = pq.read_table(COMMON_PATH, columns=columns).to_pandas()
    if len(frame) != EXPECTED_COMMON_ROWS or frame["common_origin_id"].nunique() != EXPECTED_INTENT_ORIGINS:
        raise BaselineDevelopmentError("Common-origin denominator drifted")
    if frame[KEY_COLUMNS].isna().any().any() or frame.duplicated(TARGET_JOIN_COLUMNS).any():
        raise BaselineDevelopmentError("Common-origin identity is null or duplicated")
    if set(frame["assignment_role"].astype(str)) != {"development"}:
        raise BaselineDevelopmentError("Common-origin contains non-development rows")
    observed = (
        frame.loc[frame["complete_targets_evaluable"]]
        .groupby("time_role", sort=False)["common_origin_id"]
        .nunique()
        .to_dict()
    )
    if observed != EXPECTED_COMPLETE_ORIGINS:
        raise BaselineDevelopmentError(f"Complete-target origin counts drifted: {observed}")
    return frame.sort_values(TARGET_JOIN_COLUMNS, kind="mergesort").reset_index(drop=True)


def _target_frame(development_site_ids: Sequence[str]) -> pd.DataFrame:
    dataset = ds.dataset(TARGETS_PATH, format="parquet")
    columns = TARGET_JOIN_COLUMNS + ["bloom_h", "target_risk_chla_h"]
    predicate = (
        (ds.field("source_id") == "wqp")
        & ds.field("site_id").isin(list(development_site_ids))
        & (ds.field("origin_year_month") <= "2020-12")
        & (ds.field("target_year_month") <= "2020-12")
    )
    table = dataset.scanner(columns=columns, filter=predicate).to_table()
    frame = table.to_pandas()
    if frame.empty:
        raise BaselineDevelopmentError("No training/model-selection target rows passed the physical predicate")
    if (frame["origin_year_month"].astype(str) > "2020-12").any() or (
        frame["target_year_month"].astype(str) > "2020-12"
    ).any():
        raise BaselineDevelopmentError("Target scanner materialized a label after 2020-12")
    if frame.duplicated(TARGET_JOIN_COLUMNS).any():
        raise BaselineDevelopmentError("Target source contains duplicate exact keys")
    return frame


def _panel_frame(contract: Mapping[str, Any], development_site_ids: Sequence[str]) -> pd.DataFrame:
    physical = physical_feature_columns(contract)
    columns = ["source_id", "site_id", "year_month"] + physical
    dataset = ds.dataset(PANEL_PATH, format="parquet")
    predicate = (
        (ds.field("source_id") == "wqp")
        & ds.field("site_id").isin(list(development_site_ids))
        & (ds.field("year_month") <= "2021-12")
    )
    frame = dataset.scanner(columns=columns, filter=predicate).to_table().to_pandas()
    if frame.duplicated(["source_id", "site_id", "year_month"]).any():
        raise BaselineDevelopmentError("Panel contains duplicate origin feature keys")
    numeric = frame[physical].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    frame.loc[:, physical] = numeric
    seasons = derive_calendar_features(frame["year_month"])
    for column in DERIVED_SEASON_COLUMNS:
        frame[column] = seasons[column]
    return frame


def _base_prediction_frame(common: pd.DataFrame, *, model_id: str) -> pd.DataFrame:
    frame = common[KEY_COLUMNS].copy()
    frame.insert(0, "surface_id", "closure_v1_wqp_adaptive_no_current_chla")
    frame.insert(1, "model_id", model_id)
    frame["technical_seed"] = TECHNICAL_SEED
    frame["model_seed"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    frame["upstream_state_seed"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    frame["candidate"] = ""
    frame["selected_family"] = False
    frame["availability_status"] = "success"
    frame["failure_reason"] = ""
    frame["score_semantics"] = ""
    frame["raw_score"] = np.nan
    frame["predicted_bloom_probability"] = np.nan
    return frame


def canonical_raw_prediction_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and deterministically order one closed B0/B1/B2 raw table."""
    if frame.columns.tolist() != list(RAW_PREDICTION_COLUMNS):
        raise BaselineDevelopmentError("Raw prediction columns or order drifted")
    if frame.empty:
        raise BaselineDevelopmentError("Raw prediction table cannot be empty")
    if frame[list(RAW_NON_NULL_STRING_COLUMNS)].isna().any().any():
        raise BaselineDevelopmentError("Raw prediction identity/status strings contain nulls")
    if frame[list(RAW_CANONICAL_KEY_COLUMNS)].isna().any().any():
        raise BaselineDevelopmentError("Raw prediction keys contain nulls")
    if not frame["surface_id"].eq("closure_v1_wqp_adaptive_no_current_chla").all():
        raise BaselineDevelopmentError("Raw prediction surface_id drifted")
    model_values = set(frame["model_id"].astype(str))
    if len(model_values) != 1 or not model_values.issubset({"B0", "B1", "B2"}):
        raise BaselineDevelopmentError("Raw prediction table must contain exactly one model")
    model_id = next(iter(model_values))
    if not frame["technical_seed"].eq(TECHNICAL_SEED).all():
        raise BaselineDevelopmentError("Raw prediction technical seed drifted")
    if not set(pd.to_numeric(frame["horizon_months"], errors="coerce").astype(int)).issubset(HORIZONS):
        raise BaselineDevelopmentError("Raw prediction horizon drifted")
    allowed_status = {"success", "model_unavailable"}
    if not set(frame["availability_status"].astype(str)).issubset(allowed_status):
        raise BaselineDevelopmentError("Raw prediction availability status drifted")
    success = frame["availability_status"].eq("success")
    unavailable = ~success
    if not frame.loc[success, "failure_reason"].eq("").all():
        raise BaselineDevelopmentError("Successful raw predictions must have empty failure_reason")
    if not frame.loc[unavailable, "failure_reason"].ne("").all():
        raise BaselineDevelopmentError("Unavailable raw predictions must have a failure_reason")
    raw = pd.to_numeric(frame["raw_score"], errors="coerce")
    probability = pd.to_numeric(frame["predicted_bloom_probability"], errors="coerce")
    for values, name in ((raw, "raw_score"), (probability, "predicted_bloom_probability")):
        observed = values.notna()
        if not np.isfinite(values.loc[observed].to_numpy(dtype="float64")).all():
            raise BaselineDevelopmentError(f"Raw prediction {name} contains nonfinite values")
        if bool(((values.loc[observed] < 0.0) | (values.loc[observed] > 1.0)).any()):
            raise BaselineDevelopmentError(f"Raw prediction {name} leaves [0, 1]")
    if raw.loc[success].isna().any() or probability.loc[success].isna().any():
        raise BaselineDevelopmentError("Successful raw predictions require both score columns")
    if raw.loc[unavailable].notna().any() or probability.loc[unavailable].notna().any():
        raise BaselineDevelopmentError("Unavailable raw predictions require null score columns")
    if model_id == "B0":
        if frame["model_seed"].notna().any() or frame["upstream_state_seed"].notna().any():
            raise BaselineDevelopmentError("B0 raw predictions cannot carry model/state seeds")
        if not frame["candidate"].eq("").all() or not frame["score_semantics"].eq(
            "bloom_probability"
        ).all():
            raise BaselineDevelopmentError("B0 raw semantics drifted")
    elif model_id == "B1":
        observed_seeds = set(
            pd.to_numeric(frame["upstream_state_seed"], errors="raise").astype(int)
        )
        if observed_seeds != set(MODEL_SEEDS) or frame["model_seed"].notna().any():
            raise BaselineDevelopmentError("B1 upstream seed mapping drifted")
        if not frame["candidate"].eq("").all() or not frame["score_semantics"].eq(
            "uncalibrated_chla_free_irc_persistence_probability"
        ).all():
            raise BaselineDevelopmentError("B1 raw semantics drifted")
    else:
        observed_seeds = set(pd.to_numeric(frame["model_seed"], errors="raise").astype(int))
        if observed_seeds != set(MODEL_SEEDS) or frame["upstream_state_seed"].notna().any():
            raise BaselineDevelopmentError("B2 model seed mapping drifted")
        if set(frame["candidate"].astype(str)) != set(CANDIDATES) or not frame[
            "score_semantics"
        ].eq("bloom_probability").all():
            raise BaselineDevelopmentError("B2 candidate/score semantics drifted")
    ordered = frame.copy()
    seed_rank = {seed: index for index, seed in enumerate(MODEL_SEEDS)}
    candidate_rank = {candidate: index for index, candidate in enumerate(CANDIDATES)}
    ordered["_model_seed_rank"] = ordered["model_seed"].map(seed_rank).fillna(-1).astype(int)
    ordered["_upstream_seed_rank"] = (
        ordered["upstream_state_seed"].map(seed_rank).fillna(-1).astype(int)
    )
    ordered["_candidate_rank"] = ordered["candidate"].map(candidate_rank).fillna(-1).astype(int)
    ordered = ordered.sort_values(
        ["_model_seed_rank", "_upstream_seed_rank", "_candidate_rank", *RAW_CANONICAL_KEY_COLUMNS],
        kind="mergesort",
        na_position="first",
    ).drop(columns=["_model_seed_rank", "_upstream_seed_rank", "_candidate_rank"])
    return ordered.reset_index(drop=True)


def raw_prediction_arrow_table(frame: pd.DataFrame) -> pa.Table:
    """Build the exact 22-column Closure baseline raw Arrow schema."""
    ordered = canonical_raw_prediction_frame(frame)
    arrays: list[pa.Array] = []
    fields: list[pa.Field] = []
    for column in RAW_PREDICTION_COLUMNS:
        if column in RAW_STRING_COLUMNS:
            arrays.append(pa.array(ordered[column].astype(str).tolist(), type=pa.string()))
            fields.append(pa.field(column, pa.string(), nullable=False))
        elif column == "horizon_months":
            arrays.append(pa.array(ordered[column].astype(int).tolist(), type=pa.int16()))
            fields.append(pa.field(column, pa.int16(), nullable=False))
        elif column == "technical_seed":
            arrays.append(pa.array(ordered[column].astype(int).tolist(), type=pa.int64()))
            fields.append(pa.field(column, pa.int64(), nullable=False))
        elif column in {"model_seed", "upstream_state_seed"}:
            values = [None if pd.isna(value) else int(value) for value in ordered[column]]
            arrays.append(pa.array(values, type=pa.int64()))
            fields.append(pa.field(column, pa.int64(), nullable=True))
        elif column == "selected_family":
            arrays.append(pa.array(ordered[column].astype(bool).tolist(), type=pa.bool_()))
            fields.append(pa.field(column, pa.bool_(), nullable=False))
        else:
            numeric = pd.to_numeric(ordered[column], errors="coerce")
            values = [None if pd.isna(value) else float(value) for value in numeric]
            arrays.append(pa.array(values, type=pa.float64()))
            fields.append(pa.field(column, pa.float64(), nullable=True))
    return pa.Table.from_arrays(arrays, schema=pa.schema(fields))


def build_b0_predictions(common: pd.DataFrame, targets: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    joined = common.merge(targets, on=TARGET_JOIN_COLUMNS, how="left", validate="one_to_one")
    fit = joined.loc[
        joined["time_role"].eq("training") & joined["complete_targets_evaluable"].astype(bool)
    ].copy()
    prevalence = {
        str(int(horizon)): float(
            _binary_bloom_labels(
                group["bloom_h"],
                context=f"B0 training h{int(horizon)}",
            ).mean()
        )
        for horizon, group in fit.groupby("horizon_months")
    }
    if set(prevalence) != {"1", "2", "3"}:
        raise BaselineDevelopmentError("B0 did not fit all horizons")
    out = _base_prediction_frame(common, model_id="B0")
    out["score_semantics"] = "bloom_probability"
    out["raw_score"] = out["horizon_months"].map(lambda value: prevalence[str(int(value))]).astype("float64")
    out["predicted_bloom_probability"] = out["raw_score"]
    return out, prevalence


def build_b1_predictions(common: pd.DataFrame, state_by_seed: Mapping[int, pd.DataFrame]) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    for seed in MODEL_SEEDS:
        state = state_by_seed[seed].copy()
        required = ["source_id", "site_id", "year_month"] + STATE_COLUMNS
        if sorted(set(required).difference(state.columns)):
            raise BaselineDevelopmentError(f"B1 state seed {seed} lacks required columns")
        if state.duplicated(["source_id", "site_id", "year_month"]).any():
            raise BaselineDevelopmentError(f"B1 state seed {seed} contains duplicate keys")
        subset = state[required].rename(columns={"year_month": "origin_year_month"})
        joined = common.merge(subset, on=["source_id", "site_id", "origin_year_month"], how="left", validate="many_to_one")
        out = _base_prediction_frame(joined, model_id="B1")
        out["upstream_state_seed"] = seed
        out["score_semantics"] = "uncalibrated_chla_free_irc_persistence_probability"
        score = derive_b1_score(joined)
        available = score.notna()
        out.loc[available, "raw_score"] = score.loc[available]
        out.loc[available, "predicted_bloom_probability"] = score.loc[available]
        out.loc[~available, "availability_status"] = "model_unavailable"
        out.loc[~available, "failure_reason"] = "chla_free_origin_state_unavailable"
        outputs.append(out)
    result = pd.concat(outputs, ignore_index=True)
    if len(result) != len(common) * len(MODEL_SEEDS):
        raise BaselineDevelopmentError("B1 row denominator drifted")
    return result


def _fit_preprocessor(train: pd.DataFrame, features: Sequence[str], *, scale: bool) -> tuple[np.ndarray, dict[str, Any]]:
    raw = train[list(features)].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    finite_counts = np.isfinite(raw.to_numpy(dtype="float64")).sum(axis=0)
    if bool((finite_counts == 0).any()):
        missing = [feature for feature, count in zip(features, finite_counts, strict=True) if int(count) == 0]
        raise BaselineDevelopmentError(f"Training feature has no finite values: {missing}")
    medians = raw.median(axis=0, skipna=True).to_numpy(dtype="float64")
    matrix = raw.to_numpy(dtype="float64", copy=True)
    missing_mask = ~np.isfinite(matrix)
    matrix[missing_mask] = np.take(medians, np.nonzero(missing_mask)[1])
    means = np.zeros(len(features), dtype="float64")
    scales = np.ones(len(features), dtype="float64")
    if scale:
        means = matrix.mean(axis=0, dtype="float64")
        scales = matrix.std(axis=0, dtype="float64")
        scales[~np.isfinite(scales) | (scales == 0.0)] = 1.0
        matrix = (matrix - means) / scales
    payload = {
        "feature_order": list(features),
        "finite_training_counts": [int(value) for value in finite_counts],
        "medians_float64": [float(value) for value in medians],
        "scaling": "standard" if scale else "none",
        "means_float64": [float(value) for value in means],
        "scales_float64": [float(value) for value in scales],
        "missing_indicator": False,
        "matrix_dtype": "float64",
    }
    return matrix, payload


def _transform_with_preprocessor(frame: pd.DataFrame, payload: Mapping[str, Any]) -> np.ndarray:
    features = list(payload["feature_order"])
    matrix = (
        frame[features]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .to_numpy(dtype="float64", copy=True)
    )
    medians = np.asarray(payload["medians_float64"], dtype="float64")
    mask = ~np.isfinite(matrix)
    matrix[mask] = np.take(medians, np.nonzero(mask)[1])
    if payload["scaling"] == "standard":
        matrix = (matrix - np.asarray(payload["means_float64"], dtype="float64")) / np.asarray(
            payload["scales_float64"], dtype="float64"
        )
    return matrix


def _positive_probability(model: Any, matrix: np.ndarray) -> np.ndarray:
    probabilities = np.asarray(model.predict_proba(matrix), dtype="float64")
    classes = list(model.classes_)
    if 1 not in classes:
        raise BaselineDevelopmentError("B2 classifier lacks positive class 1")
    return np.clip(probabilities[:, classes.index(1)], 0.0, 1.0)


def fit_b2(
    common: pd.DataFrame,
    targets: pd.DataFrame,
    panel: pd.DataFrame,
    contract: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[int, str, int], Any], dict[tuple[int, str, int], dict[str, Any]]]:
    features = exact_feature_columns(contract)
    panel_join = panel.rename(columns={"year_month": "origin_year_month"})
    joined = common.merge(panel_join, on=["source_id", "site_id", "origin_year_month"], how="left", validate="many_to_one", indicator="_panel_join")
    joined = joined.merge(targets, on=TARGET_JOIN_COLUMNS, how="left", validate="one_to_one")
    outputs: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    models: dict[tuple[int, str, int], Any] = {}
    preprocessors: dict[tuple[int, str, int], dict[str, Any]] = {}
    for seed in MODEL_SEEDS:
        for candidate in CANDIDATES:
            for horizon in HORIZONS:
                key = (seed, candidate, horizon)
                horizon_rows = joined.loc[joined["horizon_months"].eq(horizon)].copy()
                train = horizon_rows.loc[
                    horizon_rows["time_role"].eq("training")
                    & horizon_rows["complete_targets_evaluable"].astype(bool)
                    & horizon_rows["bloom_h"].notna()
                    & horizon_rows["_panel_join"].eq("both")
                ].copy()
                selection = horizon_rows.loc[
                    horizon_rows["time_role"].eq("model_selection")
                    & horizon_rows["complete_targets_evaluable"].astype(bool)
                    & horizon_rows["bloom_h"].notna()
                    & horizon_rows["_panel_join"].eq("both")
                ].copy()
                status = "success"
                failure = ""
                brier = np.nan
                pr_auc = np.nan
                model: Any | None = None
                preprocessor: dict[str, Any]
                try:
                    if train["common_origin_id"].nunique() != EXPECTED_COMPLETE_ORIGINS["training"]:
                        raise BaselineDevelopmentError("B2 training complete-origin denominator drifted")
                    if selection["common_origin_id"].nunique() != EXPECTED_COMPLETE_ORIGINS["model_selection"]:
                        raise BaselineDevelopmentError("B2 selection complete-origin denominator drifted")
                    y_train = _binary_bloom_labels(
                        train["bloom_h"],
                        context=f"B2 training {candidate} seed {seed} h{horizon}",
                    )
                    y_selection = _binary_bloom_labels(
                        selection["bloom_h"],
                        context=f"B2 selection {candidate} seed {seed} h{horizon}",
                    )
                    if len(np.unique(y_train)) != 2 or len(np.unique(y_selection)) != 2:
                        raise BaselineDevelopmentError("B2 training/selection requires both bloom classes")
                    x_train, preprocessor = _fit_preprocessor(
                        train, features, scale=candidate == "logistic_sgd"
                    )
                    if candidate == "logistic_sgd":
                        model = SGDClassifier(
                            loss="log_loss",
                            penalty="l2",
                            alpha=0.0001,
                            max_iter=100,
                            tol=0.001,
                            class_weight="balanced",
                            n_jobs=1,
                            early_stopping=False,
                            random_state=seed,
                        )
                    else:
                        model = HistGradientBoostingClassifier(
                            loss="log_loss",
                            max_iter=150,
                            learning_rate=0.05,
                            max_leaf_nodes=31,
                            early_stopping=False,
                            random_state=seed,
                        )
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", ConvergenceWarning)
                        model.fit(x_train, y_train)
                    selection_probability = _positive_probability(
                        model, _transform_with_preprocessor(selection, preprocessor)
                    )
                    brier = float(brier_score_loss(y_selection, selection_probability))
                    pr_auc = float(average_precision_score(y_selection, selection_probability))
                    if not np.isfinite([brier, pr_auc]).all():
                        raise BaselineDevelopmentError("B2 selection metric is nonfinite")
                    models[key] = model
                    preprocessors[key] = preprocessor
                except (BaselineDevelopmentError, ConvergenceWarning, ValueError, FloatingPointError) as exc:
                    status = "model_unavailable"
                    failure = f"{type(exc).__name__}:{exc}"
                    model = None
                    preprocessor = {
                        "feature_order": list(features),
                        "status": status,
                        "failure_reason": failure,
                        "missing_indicator": False,
                    }
                    preprocessors[key] = preprocessor
                metric_rows.append(
                    {
                        "model_id": "B2",
                        "candidate": candidate,
                        "technical_seed": TECHNICAL_SEED,
                        "model_seed": seed,
                        "upstream_state_seed": pd.NA,
                        "horizon_months": horizon,
                        "role": "model_selection",
                        "fit_status": status,
                        "failure_reason": failure,
                        "rows": int(len(selection)),
                        "brier": brier,
                        "pr_auc": pr_auc,
                        "rmse": np.nan,
                        "mae": np.nan,
                    }
                )
                raw = _base_prediction_frame(horizon_rows, model_id="B2")
                raw["model_seed"] = seed
                raw["candidate"] = candidate
                raw["score_semantics"] = "bloom_probability"
                available = horizon_rows["_panel_join"].eq("both") & (model is not None)
                if model is not None and bool(available.any()):
                    probability = _positive_probability(
                        model, _transform_with_preprocessor(horizon_rows.loc[available], preprocessors[key])
                    )
                    raw.loc[available.to_numpy(), "raw_score"] = probability
                    raw.loc[available.to_numpy(), "predicted_bloom_probability"] = probability
                raw.loc[~available.to_numpy(), "availability_status"] = "model_unavailable"
                raw.loc[~available.to_numpy(), "failure_reason"] = np.where(
                    ~horizon_rows["_panel_join"].eq("both").to_numpy(),
                    "raw_feature_row_unavailable",
                    failure or "candidate_fit_unavailable",
                )
                outputs.append(raw)
    metrics = pd.DataFrame(metric_rows)
    selection = select_b2_families(metrics)
    result = pd.concat(outputs, ignore_index=True)
    chosen = selection.set_index("horizon_months")["selected_candidate"].to_dict()
    result["selected_family"] = result.apply(
        lambda row: bool(pd.notna(chosen.get(int(row["horizon_months"]))))
        and row["candidate"] == chosen[int(row["horizon_months"])],
        axis=1,
    )
    if len(result) != len(common) * len(MODEL_SEEDS) * len(CANDIDATES):
        raise BaselineDevelopmentError("B2 candidate prediction denominator drifted")
    return result, metrics, models, preprocessors


def _score_b0_b1_metrics(
    b0: pd.DataFrame,
    b1: pd.DataFrame,
    common: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    labels = common.merge(targets, on=TARGET_JOIN_COLUMNS, how="left", validate="one_to_one")
    labels = labels.loc[
        labels["time_role"].eq("model_selection")
        & labels["complete_targets_evaluable"].astype(bool)
    ][TARGET_JOIN_COLUMNS + ["bloom_h", "target_risk_chla_h"]]
    for horizon in HORIZONS:
        horizon_labels = labels.loc[labels["horizon_months"].eq(horizon)]
        if (
            len(horizon_labels) != EXPECTED_COMPLETE_ORIGINS["model_selection"]
            or horizon_labels["bloom_h"].isna().any()
        ):
            raise BaselineDevelopmentError(
                "B0/B1 selection label denominator or bloom availability drifted"
            )
    rows: list[dict[str, Any]] = []
    b0_joined = b0.merge(labels, on=TARGET_JOIN_COLUMNS, how="inner", validate="one_to_one")
    for horizon in HORIZONS:
        group = b0_joined.loc[b0_joined["horizon_months"].eq(horizon)]
        y = _binary_bloom_labels(group["bloom_h"], context=f"B0 selection h{horizon}")
        probability = group["predicted_bloom_probability"].to_numpy(dtype="float64")
        rows.append(
            {
                "model_id": "B0",
                "candidate": "horizon_prevalence",
                "technical_seed": TECHNICAL_SEED,
                "model_seed": pd.NA,
                "upstream_state_seed": pd.NA,
                "horizon_months": horizon,
                "role": "model_selection",
                "fit_status": "success",
                "failure_reason": "",
                "rows": int(len(group)),
                "brier": float(brier_score_loss(y, probability)),
                "pr_auc": float(average_precision_score(y, probability)),
                "rmse": np.nan,
                "mae": np.nan,
            }
        )
    b1_joined = b1.merge(labels, on=TARGET_JOIN_COLUMNS, how="inner", validate="many_to_one")
    for seed in MODEL_SEEDS:
        for horizon in HORIZONS:
            group = b1_joined.loc[
                b1_joined["upstream_state_seed"].eq(seed)
                & b1_joined["horizon_months"].eq(horizon)
            ]
            bloom_valid = group["raw_score"].notna() & group["bloom_h"].notna()
            continuous_target = pd.to_numeric(
                group["target_risk_chla_h"], errors="coerce"
            )
            continuous_valid = group["raw_score"].notna() & np.isfinite(
                continuous_target
            )
            bloom_score = group.loc[bloom_valid, "raw_score"].to_numpy(dtype="float64")
            bloom = _binary_bloom_labels(
                group.loc[bloom_valid, "bloom_h"],
                context=f"B1 selection seed {seed} h{horizon}",
            )
            continuous_score = group.loc[continuous_valid, "raw_score"].to_numpy(
                dtype="float64"
            )
            target = continuous_target.loc[continuous_valid].to_numpy(dtype="float64")
            rows.append(
                {
                    "model_id": "B1",
                    "candidate": "chla_free_state_persistence",
                    "technical_seed": TECHNICAL_SEED,
                    "model_seed": pd.NA,
                    "upstream_state_seed": seed,
                    "horizon_months": horizon,
                    "role": "model_selection",
                    "fit_status": "success" if len(bloom_score) else "model_unavailable",
                    "failure_reason": "" if len(bloom_score) else "no_finite_paired_scores",
                    "rows": int(len(bloom_score)),
                    "continuous_rows": int(len(continuous_score)),
                    "brier": (
                        float(brier_score_loss(bloom, bloom_score))
                        if len(bloom_score)
                        else np.nan
                    ),
                    "pr_auc": (
                        float(average_precision_score(bloom, bloom_score))
                        if len(bloom_score)
                        else np.nan
                    ),
                    "rmse": (
                        float(math.sqrt(mean_squared_error(target, continuous_score)))
                        if len(continuous_score)
                        else np.nan
                    ),
                    "mae": (
                        float(mean_absolute_error(target, continuous_score))
                        if len(continuous_score)
                        else np.nan
                    ),
                }
            )
    return pd.DataFrame(rows)


def _load_state_frames(contract: Mapping[str, Any]) -> dict[int, pd.DataFrame]:
    result: dict[int, pd.DataFrame] = {}
    for record in contract["upstream_anfis_bundles"]:
        seed = int(record["base_seed"])
        path = Path(record["state"]["path"])
        frame = pq.read_table(path, columns=["source_id", "site_id", "year_month"] + STATE_COLUMNS).to_pandas()
        result[seed] = frame
    if set(result) != set(MODEL_SEEDS):
        raise BaselineDevelopmentError("ANFIS state seed set drifted")
    return result


def _verify_authority_records(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for role, value in contract["authority"].items():
        if not isinstance(value, dict) or "path" not in value or "sha256" not in value:
            continue
        path = Path(value["path"])
        if not path.is_file() or path.is_symlink():
            raise BaselineDevelopmentError(f"Authority input is missing/non-regular: {path}")
        actual = _file_record(path)
        if actual["sha256"] != value["sha256"] or (
            "bytes" in value and actual["bytes"] != int(value["bytes"])
        ):
            raise BaselineDevelopmentError(f"Authority input drifted: {path}")
        actual["artifact_role"] = str(role)
        records.append(actual)
    for bundle in contract["upstream_anfis_bundles"]:
        for role in ("state", "pointer", "manifest"):
            expected = bundle[role]
            path = Path(expected["path"])
            actual = _file_record(path)
            if actual["bytes"] != int(expected["bytes"]) or actual["sha256"] != expected["sha256"]:
                raise BaselineDevelopmentError(f"ANFIS authority input drifted: {path}")
            actual["artifact_role"] = f"anfis_{int(bundle['base_seed'])}_{role}"
            records.append(actual)
    paths = [str(record["path"]) for record in records]
    if len(paths) != len(set(paths)):
        raise BaselineDevelopmentError("Baseline authority input paths are not unique")
    return records


def _compare_supplied_authority(
    supplied: Mapping[str, Any] | None,
    effective: Mapping[str, Any],
) -> None:
    if supplied is not None and dict(supplied) != dict(effective):
        raise BaselineDevelopmentError(
            "Supplied E0-MP authority differs from the effective published authority"
        )


def preflight(authority: Mapping[str, Any] | None = None) -> dict[str, Any]:
    effective = _require_effective_authority()
    _compare_supplied_authority(authority, effective)
    return _preflight_with_verified_authority(effective)


def _preflight_with_verified_authority(authority: Mapping[str, Any]) -> dict[str, Any]:
    contract = load_runtime_contract()
    authority_snapshot = _validated_authority_snapshot(authority)
    _assert_absent_namespace(contract)
    records = _verify_authority_records(contract)
    runtime_record = {**_file_record(RUNTIME_PATH), "artifact_role": "baseline_runtime"}
    lock_record = {**_file_record(PATCH_LOCK_PATH), "artifact_role": "effective_patch_lock"}
    companion_record = {
        **_file_record(PATCH_COMPANION_PATH),
        "artifact_role": "effective_patch_lock_manifest",
    }
    runner_record = {
        **_file_record(RUNNER_SOURCE_PATH),
        "artifact_role": "baseline_development_runner",
    }
    if runtime_record["sha256"] != authority_snapshot["runtime_sha256"]:
        raise BaselineDevelopmentError("Effective E0-MP runtime binding drifted")
    if lock_record["sha256"] != authority_snapshot["lock_sha256"]:
        raise BaselineDevelopmentError("Effective E0-MP lock binding drifted")
    if companion_record["sha256"] != authority_snapshot["companion_sha256"]:
        raise BaselineDevelopmentError("Effective E0-MP companion binding drifted")
    if runner_record["sha256"] != authority_snapshot["runner_sha256"]:
        raise BaselineDevelopmentError("Effective E0-MP runner binding drifted")
    exact_feature_columns(contract)
    return {
        "status": "ready_to_execute_one_shot",
        "gate": "E0-MP",
        "baseline_one_shot_authorized": True,
        "authority_input_count": len(records) + 4,
        "authority_binding": authority_snapshot,
        "common_origin_rows": EXPECTED_COMMON_ROWS,
        "intent_origins": EXPECTED_INTENT_ORIGINS,
        "writes_performed": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


def _acquire_guard(contract: Mapping[str, Any]) -> OwnedGuard:
    guard = Path(contract["outputs"]["publication"]["guard_path"])
    directory_descriptor, lexical_guard = _open_real_repository_parent(
        guard,
        create=True,
        directory_mode=0o700,
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    device: int | None = None
    inode: int | None = None
    try:
        try:
            descriptor = os.open(
                lexical_guard.name,
                flags,
                0o600,
                dir_fd=directory_descriptor,
            )
        except FileExistsError as exc:
            raise BaselineDevelopmentError(
                f"Baseline development slot is already reserved: {guard}"
            ) from exc
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise BaselineDevelopmentError("Baseline development guard is not regular")
        device, inode = int(metadata.st_dev), int(metadata.st_ino)
        opened_parent = os.fstat(directory_descriptor)
        lexical_parent = lexical_guard.parent.lstat()
        if (
            not stat.S_ISDIR(lexical_parent.st_mode)
            or (opened_parent.st_dev, opened_parent.st_ino)
            != (lexical_parent.st_dev, lexical_parent.st_ino)
        ):
            raise BaselineDevelopmentError("Baseline guard parent identity drifted")
        os.fsync(descriptor)
        os.fsync(directory_descriptor)
        return OwnedGuard(
            path=lexical_guard,
            device=device,
            inode=inode,
            file_descriptor=descriptor,
            directory_descriptor=directory_descriptor,
        )
    except BaseException as exc:
        cleanup_errors: list[Exception] = []
        if device is not None and inode is not None:
            try:
                _unlink_name_if_owned(
                    directory_descriptor,
                    lexical_guard.name,
                    device=device,
                    inode=inode,
                )
                os.fsync(directory_descriptor)
            except (BaselineDevelopmentError, OSError) as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as cleanup_error:
                cleanup_errors.append(cleanup_error)
        try:
            os.close(directory_descriptor)
        except OSError as cleanup_error:
            cleanup_errors.append(cleanup_error)
        if cleanup_errors:
            cleanup_failure = BaselineDevelopmentError(
                "Baseline guard acquisition rollback could not be completed safely"
            )
            cleanup_failure.add_note(
                "Cleanup failures: "
                + "; ".join(
                    f"{type(error).__name__}: {error}" for error in cleanup_errors
                )
            )
            raise cleanup_failure from exc
        raise


def _release_guard(guard: OwnedGuard) -> None:
    errors: list[Exception] = []
    try:
        opened_parent = os.fstat(guard.directory_descriptor)
        lexical_parent = guard.path.parent.lstat()
        current = os.stat(
            guard.path.name,
            dir_fd=guard.directory_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(current.st_mode)
            or (current.st_dev, current.st_ino) != (guard.device, guard.inode)
            or not stat.S_ISDIR(lexical_parent.st_mode)
            or (opened_parent.st_dev, opened_parent.st_ino)
            != (lexical_parent.st_dev, lexical_parent.st_ino)
        ):
            raise BaselineDevelopmentError("Baseline guard changed during execution")
        if not _unlink_name_if_owned(
            guard.directory_descriptor,
            guard.path.name,
            device=guard.device,
            inode=guard.inode,
        ):
            raise BaselineDevelopmentError("Owned baseline guard disappeared before cleanup")
        os.fsync(guard.directory_descriptor)
    except Exception as exc:
        errors.append(exc)
    for descriptor in (guard.file_descriptor, guard.directory_descriptor):
        try:
            os.close(descriptor)
        except OSError as exc:
            errors.append(exc)
    if errors:
        error = BaselineDevelopmentError("Baseline guard cleanup could not be completed safely")
        error.add_note(
            "Cleanup failures: "
            + "; ".join(f"{type(item).__name__}: {item}" for item in errors)
        )
        raise error from errors[0]


def _serialize_dataframe_csv(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _report_text(*, b0_rows: int, b1_rows: int, b2_rows: int, selected: pd.DataFrame) -> str:
    lines = [
        "# Closure V1 development baselines",
        "",
        "- Surface: `closure_v1_wqp_adaptive_no_current_chla`",
        f"- B0 raw rows: {b0_rows:,}",
        f"- B1 raw rows: {b1_rows:,}",
        f"- B2 candidate raw rows: {b2_rows:,}",
        "- Calibration, E0-M, E0-U, evaluation, DVC, and post-2021 outcome access: not performed",
        "",
        "## Selected B2 family by horizon",
        "",
    ]
    for row in selected.to_dict(orient="records"):
        lines.append(
            f"- h{int(row['horizon_months'])}: {row['selected_candidate']} ({row['selection_status']})"
        )
    return "\n".join(lines) + "\n"


def execute_one_shot(authority: Mapping[str, Any] | None = None) -> dict[str, Any]:
    effective = _require_effective_authority()
    _compare_supplied_authority(authority, effective)
    return _execute_one_shot_with_verified_authority(effective)


def _execute_one_shot_with_verified_authority(
    effective_authority: Mapping[str, Any],
) -> dict[str, Any]:
    contract = load_runtime_contract()
    preflight_result = _preflight_with_verified_authority(effective_authority)
    authority_snapshot = _validated_authority_snapshot(effective_authority)
    guard = _acquire_guard(contract)
    guard_active = True
    try:
        _assert_absent_namespace(contract, allow_guard=True)
        input_records_before = _verify_authority_records(contract)
        input_records_before.extend(
            (
                {**_file_record(RUNTIME_PATH), "artifact_role": "baseline_runtime"},
                {**_file_record(PATCH_LOCK_PATH), "artifact_role": "effective_patch_lock"},
                {
                    **_file_record(PATCH_COMPANION_PATH),
                    "artifact_role": "effective_patch_lock_manifest",
                },
                {
                    **_file_record(RUNNER_SOURCE_PATH),
                    "artifact_role": "baseline_development_runner",
                },
            )
        )
        if input_records_before[-1]["sha256"] != authority_snapshot["runner_sha256"]:
            raise BaselineDevelopmentError("Effective E0-MP runner binding drifted")
        if len({record["path"] for record in input_records_before}) != len(
            input_records_before
        ):
            raise BaselineDevelopmentError("Execution input records are not path-unique")
        gate = load_development_gate()
        common = _common_frame()
        assert_development_frame(common, gate, role_column="time_role")
        development_site_ids = sorted(site for source, site in gate.development_keys if source == "wqp")
        targets = _target_frame(development_site_ids)
        panel = _panel_frame(contract, development_site_ids)
        states = _load_state_frames(contract)

        b0, prevalence = build_b0_predictions(common, targets)
        b1 = build_b1_predictions(common, states)
        with threadpool_limits(limits=1):
            b2, b2_metrics, models, preprocessors = fit_b2(
                common,
                targets,
                panel,
                contract,
            )
            selection = select_b2_families(b2_metrics)
            metrics = pd.concat(
                [_score_b0_b1_metrics(b0, b1, common, targets), b2_metrics],
                ignore_index=True,
            )

        output = contract["outputs"]
        manifest_record: dict[str, Any]
        with OutputTransaction() as transaction:
            output_records_by_path: dict[str, dict[str, Any]] = {}
            for model_id, frame in (("B0", b0), ("B1", b1), ("B2", b2)):
                final = Path(output["raw_score_parquets"][model_id])
                owned = transaction.publish_arrow_table(
                    raw_prediction_arrow_table(frame),
                    final,
                )
                output_records_by_path[final.as_posix()] = transaction.file_record(
                    owned,
                    logical_path=final,
                )

            model_records: list[dict[str, Any]] = []
            preprocessor_records: list[dict[str, Any]] = []
            for seed in MODEL_SEEDS:
                for candidate in CANDIDATES:
                    for horizon in HORIZONS:
                        key = (seed, candidate, horizon)
                        pre_final = Path(
                            output["b2_preprocessor_template"].format(
                                model_seed=seed,
                                candidate=candidate,
                                horizon=horizon,
                            )
                        )
                        pre_payload = dict(preprocessors[key])
                        pre_payload.update(
                            {
                                "model_seed": seed,
                                "candidate": candidate,
                                "horizon_months": horizon,
                                "status": "success" if key in models else "model_unavailable",
                            }
                        )
                        pre_owned = transaction.publish_bytes(
                            _canonical_json_bytes(pre_payload),
                            pre_final,
                        )
                        pre_record = transaction.file_record(pre_owned, logical_path=pre_final)
                        preprocessor_records.append(pre_record)
                        output_records_by_path[pre_final.as_posix()] = pre_record
                        if key not in models:
                            continue
                        pipeline_final = Path(
                            output["b2_pipeline_template"].format(
                                model_seed=seed,
                                candidate=candidate,
                                horizon=horizon,
                            )
                        )
                        pipeline_owned = transaction.publish_joblib(
                            {
                                "model": models[key],
                                "preprocessor": preprocessors[key],
                                "model_seed": seed,
                                "candidate": candidate,
                                "horizon_months": horizon,
                            },
                            pipeline_final,
                        )
                        pipeline_record = transaction.file_record(
                            pipeline_owned,
                            logical_path=pipeline_final,
                        )
                        model_records.append(pipeline_record)
                        output_records_by_path[pipeline_final.as_posix()] = pipeline_record

            light = {name: Path(path) for name, path in output["light_bundle"].items()}
            model_specs = {
                "schema_version": "closure_baseline_model_specs_v1",
                "B0": {"technical_seed": TECHNICAL_SEED, "prevalence_by_horizon": prevalence},
                "B1": {
                    "technical_seed": TECHNICAL_SEED,
                    "upstream_state_seeds": list(MODEL_SEEDS),
                    "formula": "clip_0_1_of_yN_plus_1_minus_yF_plus_yT_no_chla_divided_by_3",
                },
                "B2": {
                    "model_seeds": list(MODEL_SEEDS),
                    "feature_order": exact_feature_columns(contract),
                    "pipeline_records": model_records,
                    "preprocessor_records": preprocessor_records,
                },
            }
            lineage = {
                "schema_version": "closure_baseline_feature_lineage_audit_v1",
                "status": "passed",
                "physical_features": physical_feature_columns(contract),
                "derived_features": DERIVED_SEASON_COLUMNS,
                "observed_chlorophyll_lineage_count": 0,
                "legacy_alias_count": 0,
                "holdout_overlap_count": 0,
                "post_2020_target_rows_materialized": 0,
                "post_2021_feature_rows_materialized": 0,
            }
            light_payloads = {
                light["model_specs"]: _canonical_json_bytes(model_specs),
                light["metrics"]: _serialize_dataframe_csv(metrics),
                light["selection"]: _serialize_dataframe_csv(selection),
                light["lineage_audit"]: _canonical_json_bytes(lineage),
                light["report"]: _report_text(
                    b0_rows=len(b0),
                    b1_rows=len(b1),
                    b2_rows=len(b2),
                    selected=selection,
                ).encode("utf-8"),
            }
            for final, payload in light_payloads.items():
                owned = transaction.publish_bytes(payload, final)
                output_records_by_path[final.as_posix()] = transaction.file_record(
                    owned,
                    logical_path=final,
                )

            input_records_after = _verify_authority_records(contract)
            input_records_after.extend(
                (
                    {**_file_record(RUNTIME_PATH), "artifact_role": "baseline_runtime"},
                    {**_file_record(PATCH_LOCK_PATH), "artifact_role": "effective_patch_lock"},
                    {
                        **_file_record(PATCH_COMPANION_PATH),
                        "artifact_role": "effective_patch_lock_manifest",
                    },
                    {
                        **_file_record(RUNNER_SOURCE_PATH),
                        "artifact_role": "baseline_development_runner",
                    },
                )
            )
            if len({record["path"] for record in input_records_after}) != len(
                input_records_after
            ):
                raise BaselineDevelopmentError("Execution input records are not path-unique")
            if input_records_before != input_records_after:
                raise BaselineDevelopmentError("Authority inputs changed during baseline execution")
            _assert_future_dvc_namespace_absent(contract)
            if _lexists(OUTCOME_ACCESS_LOG):
                raise BaselineDevelopmentError("Outcome-access log changed during baseline execution")

            manifest_final = light["manifest"]
            output_records = [
                output_records_by_path[path]
                for path in sorted(output_records_by_path)
            ]
            manifest_payload = {
                "schema_version": "closure_baseline_development_bundle_v1",
                "status": "completed",
                "experiment_id": "closure_v1",
                "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "gate": "E0-MP",
                "models": ["B0", "B1", "B2"],
                "seeds": list(MODEL_SEEDS),
                "counts": {
                    "common_origin_rows": len(common),
                    "intent_origins": int(common["common_origin_id"].nunique()),
                    "B0_raw_rows": len(b0),
                    "B1_raw_rows": len(b1),
                    "B2_candidate_raw_rows": len(b2),
                    "pipeline_records": len(model_records),
                    "preprocessor_records": len(preprocessor_records),
                },
                "raw_prediction_contract": raw_prediction_contract(),
                "runtime_versions": runtime_version_record(),
                "selection": _json_records(selection),
                "effective_authority": authority_snapshot,
                "inputs": input_records_after,
                "script": dict(input_records_after[-1]),
                "source_code": [dict(input_records_after[-1])],
                "outputs": output_records,
                "calibration_authorized": False,
                "e0_m_authorized": False,
                "evaluation_authorized": False,
                "e0_u_authorized": False,
                "dvc_commands_run": False,
                "future_outcomes_accessed": False,
                "outcome_access_log_state": "absent",
                "completion_marker_written_last": True,
            }
            manifest_owned = transaction.publish_bytes(
                _manifest_json_bytes(manifest_payload),
                manifest_final,
            )
            manifest_record = transaction.file_record(
                manifest_owned,
                logical_path=manifest_final,
            )
        guard_active = False
        _release_guard(guard)
        return {
            **preflight_result,
            "status": "baseline_bundle_written_unpublished",
            "writes_performed": True,
            "B0_raw_rows": len(b0),
            "B1_raw_rows": len(b1),
            "B2_candidate_raw_rows": len(b2),
            "pipeline_count": len(model_records),
            "manifest": manifest_record,
            "dvc_commands_run": False,
            "outcome_paths_opened": False,
        }
    except BaseException as exc:
        if guard_active:
            guard_active = False
            try:
                _release_guard(guard)
            except BaselineDevelopmentError as cleanup_error:
                raise cleanup_error from exc
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-only", action="store_true")
    modes.add_argument("--execute-one-shot", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    # Authority is intentionally the first operation after argument parsing.
    authority = _require_effective_authority()
    if args.check_only:
        result = _preflight_with_verified_authority(authority)
    else:
        result = _execute_one_shot_with_verified_authority(authority)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
