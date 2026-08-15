#!/usr/bin/env python
"""Build the outcome-free runtime overlay consumed immediately before E0-U.

The overlay has three and only three outputs.  It exports the locked Torch
``state_dict`` tensors to a deterministic NumPy archive, materializes one
physical-input warm-up month per locked holdout site, and writes a canonical
manifest last.  Neither target tables nor scientific outcome paths are part
of this adapter's input namespace.

``--check-only`` validates the namespace, file identities and Parquet schemas
without loading checkpoint payloads, reading scientific rows, or writing any
file.  ``--generate`` is deliberately exclusive and no-clobber.  A failed
generation removes only files whose device/inode pairs were created by the
current process.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import json
import math
import os
import secrets
import stat
import subprocess
import sys
import zipfile
from contextlib import contextmanager
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Iterator, cast

np: Any = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_VERSION = "closure_phase3_input_overlay_manifest_v1"
NPZ_INDEX_VERSION = "closure_phase3_numpy_state_dict_index_v1"
SURFACE_ID = "closure_v1_phase3_input_overlay"
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
EXPECTED_HOLDOUT_SITES = 88
PARITY_FIXTURE_VERSION = "deterministic_arithmetic_grid_v1"
PARITY_ATOL = 2.0e-6
PARITY_RTOL = 2.0e-6
DEEP_VALIDATION_VERSION = "closure_phase3_input_overlay_deep_validation_v1"

R10_INPUT_HISTORY_PATH = Path(
    "data/closure_v1/locked_evaluation/input_history.parquet"
)
PANEL_PATH = Path("data/panel/panel_monthly_v0.parquet")
NPZ_OUTPUT_PATH = Path(
    "data/closure_v1/locked_evaluation/phase3_runtime_weights.npz"
)
WARMUP_OUTPUT_PATH = Path(
    "data/closure_v1/locked_evaluation/adaptive_state_warmup.parquet"
)
MANIFEST_OUTPUT_PATH = Path(
    "reports/closure_v1/01_surface/phase3_input_overlay_manifest.json"
)
GUARD_PATH = Path("tmp/closure_phase3_input_overlay.guard")

HISTORY_PROJECTION = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "assignment_role",
    "history_year_month",
)
PHYSICAL_FEATURE_COLUMNS = (
    "mean_TP_ugL",
    "std_TP_ugL",
    "n_obs_TP_ugL",
    "n_bad_TP_ugL",
    "qc_ok_rate_TP_ugL",
    "mean_TN_ugL",
    "std_TN_ugL",
    "n_obs_TN_ugL",
    "n_bad_TN_ugL",
    "qc_ok_rate_TN_ugL",
    "mean_temperature_C",
    "std_temperature_C",
    "n_obs_temperature_C",
    "n_bad_temperature_C",
    "qc_ok_rate_temperature_C",
    "mean_secchi_depth_m",
    "std_secchi_depth_m",
    "n_obs_secchi_depth_m",
    "n_bad_secchi_depth_m",
    "qc_ok_rate_secchi_depth_m",
    "mean_turbidity_NTU",
    "std_turbidity_NTU",
    "n_obs_turbidity_NTU",
    "n_bad_turbidity_NTU",
    "qc_ok_rate_turbidity_NTU",
    "mean_DO_mgL",
    "std_DO_mgL",
    "n_obs_DO_mgL",
    "n_bad_DO_mgL",
    "qc_ok_rate_DO_mgL",
    "mean_pH",
    "std_pH",
    "n_obs_pH",
    "n_bad_pH",
    "qc_ok_rate_pH",
    "log_TP",
    "log_TN",
    "TN_TP_ratio",
)
PANEL_SEASON_COLUMNS = (
    "season_sin_1",
    "season_cos_1",
    "season_sin_2",
    "season_cos_2",
)
DERIVED_CALENDAR_COLUMNS = (
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
)
PANEL_SEASON_TO_OUTPUT = dict(zip(PANEL_SEASON_COLUMNS, DERIVED_CALENDAR_COLUMNS))
PANEL_PROJECTION = (
    "source_id",
    "site_id",
    "year_month",
    *PHYSICAL_FEATURE_COLUMNS,
    *PANEL_SEASON_COLUMNS,
)
WARMUP_COLUMNS = (
    "source_id",
    "site_id",
    "year_month",
    "row_present",
    *PHYSICAL_FEATURE_COLUMNS,
    *DERIVED_CALENDAR_COLUMNS,
)

ANFIS_MODULE_TOKEN = {
    "ANFIS-N": "N",
    "ANFIS-F": "F",
    "ANFIS-T-no-current": "T",
}
ANFIS_EXPECTED_INPUT_DIMENSION = {"N": 3, "F": 4, "T": 1}
ANFIS_EXPECTED_FEATURE_COLUMNS = {
    "N": ("tp_pressure", "tn_pressure", "ratio_imbalance_pressure"),
    "F": ("do_good", "ph_good", "turbidity_good", "secchi_good"),
    "T": ("temp_favorable",),
}
ANFIS_EXPECTED_TARGET_COLUMN = {
    "N": "yN",
    "F": "yF",
    "T": "yT_no_chla",
}
ANFIS_EXPECTED_STATE_KEYS = {
    "raw_center_gaps",
    "raw_widths",
    "consequent_weights",
    "consequent_bias",
    "rule_indices",
}
GRU_EXPECTED_STATE_KEYS = {
    "bloom_prior_logits",
    "risk_prior_logits",
    "gru.weight_ih_l0",
    "gru.weight_hh_l0",
    "gru.bias_ih_l0",
    "gru.bias_hh_l0",
    "bloom_delta.weight",
    "bloom_delta.bias",
    "risk_delta.weight",
    "risk_delta.bias",
    "risk_logvar.weight",
    "risk_logvar.bias",
}
GRU_EXPECTED_INPUT_DIMENSION = {"A0": 18, "A1": 27}
GRU_EXPECTED_HIDDEN_DIMENSION = 96
GRU_HISTORY_LENGTH = 12
GRU_LOGVAR_MIN = -10.0
GRU_LOGVAR_MAX = 2.0


class Phase3InputOverlayError(RuntimeError):
    """Raised when the pre-E0-U overlay contract cannot be proven."""


@dataclass(frozen=True)
class CheckpointSpec:
    family: str
    seed: int
    path: Path
    module: str | None = None
    model_id: str | None = None

    @property
    def identity(self) -> str:
        if self.family == "anfis":
            return f"anfis/{self.seed}/{self.module}"
        return f"gru/{self.model_id}/{self.seed}"


@dataclass(frozen=True)
class OverlayPaths:
    history: Path = R10_INPUT_HISTORY_PATH
    panel: Path = PANEL_PATH
    npz_output: Path = NPZ_OUTPUT_PATH
    warmup_output: Path = WARMUP_OUTPUT_PATH
    manifest_output: Path = MANIFEST_OUTPUT_PATH
    guard: Path = GUARD_PATH


@dataclass
class DirectoryAnchor:
    """Open descriptor chain that keeps one repository parent namespace fixed."""

    repo_root: Path
    descriptors: list[int]
    bindings: list[tuple[int, str, int, tuple[int, ...]]]
    root_identity: tuple[int, ...]
    closed: bool = False

    @property
    def parent_fd(self) -> int:
        if self.closed or not self.descriptors:
            raise _error("owned parent anchor is closed")
        return self.descriptors[-1]


@dataclass(frozen=True)
class OwnedPath:
    path: Path
    device: int
    inode: int
    anchor: DirectoryAnchor


def _default_checkpoint_specs() -> tuple[CheckpointSpec, ...]:
    specs: list[CheckpointSpec] = []
    for seed in REGISTERED_SEEDS:
        names = (
            {
                "N": "ANFIS-N.pt",
                "F": "ANFIS-F.pt",
                "T": "ANFIS-T-no-current.pt",
            }
            if seed == 1729
            else {
                "N": "anfis_n.pt",
                "F": "anfis_f.pt",
                "T": "anfis_t_no_current.pt",
            }
        )
        for module in ("N", "F", "T"):
            specs.append(
                CheckpointSpec(
                    family="anfis",
                    seed=seed,
                    module=module,
                    path=Path(f"models/closure_v1/anfis/seed_{seed}")
                    / names[module],
                )
            )
    for model_id in ("A0", "A1"):
        for seed in REGISTERED_SEEDS:
            specs.append(
                CheckpointSpec(
                    family="gru",
                    seed=seed,
                    model_id=model_id,
                    path=Path(
                        f"models/closure_v1/anfis_ablation/{model_id}/"
                        f"seed_{seed}.checkpoint.pt"
                    ),
                )
            )
    return tuple(specs)


CHECKPOINT_SPECS = _default_checkpoint_specs()


def _error(message: str) -> Phase3InputOverlayError:
    return Phase3InputOverlayError(f"Closure Phase 3 input overlay: {message}")


def _activate_scientific_runtime(repo_root: Path) -> None:
    """Make the repository's exact venv importable for the pre-U deep audit."""

    global np
    if np is not None:
        return
    imported_numpy = sys.modules.get("numpy")
    if imported_numpy is not None:
        np = imported_numpy
        return
    purelib = Path(repo_root) / ".venv" / "lib" / (
        f"python{sys.version_info.major}.{sys.version_info.minor}"
    ) / "site-packages"
    try:
        metadata = purelib.lstat()
    except FileNotFoundError as exc:
        raise _error("local scientific purelib is absent") from exc
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise _error("local scientific purelib is not one real directory")
    purelib_text = purelib.as_posix()
    if purelib_text not in sys.path:
        sys.path.insert(0, purelib_text)
    try:
        import numpy as numpy_module
    except ImportError as exc:
        raise _error("NumPy is unavailable in the local scientific runtime") from exc
    np = numpy_module


def _canonical_json_text(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise _error("manifest payload is not canonical-JSON safe") from exc


def _canonical_json_bytes(value: Any) -> bytes:
    return (_canonical_json_text(value) + "\n").encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _relative_path(path: Path, *, repo_root: Path) -> Path:
    root = Path(os.path.abspath(repo_root))
    candidate = path if path.is_absolute() else root / path
    candidate = Path(os.path.abspath(candidate))
    try:
        return candidate.relative_to(root)
    except ValueError as exc:
        raise _error(f"path escapes repository root: {path}") from exc


def _physical_path(path: Path, *, repo_root: Path) -> Path:
    return Path(os.path.abspath(repo_root)) / _relative_path(path, repo_root=repo_root)


def _assert_real_parent(path: Path, *, repo_root: Path) -> None:
    root = Path(os.path.abspath(repo_root))
    relative = _relative_path(path, repo_root=root)
    current = root
    try:
        root_meta = current.lstat()
    except FileNotFoundError as exc:
        raise _error(f"repository root is absent: {root}") from exc
    if not stat.S_ISDIR(root_meta.st_mode) or stat.S_ISLNK(root_meta.st_mode):
        raise _error("repository root must be a real directory")
    for part in relative.parts[:-1]:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError as exc:
            raise _error(f"required parent directory is absent: {current}") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise _error(f"parent component is not a real directory: {current}")


def _metadata_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


@contextmanager
def _anchored_regular(
    path: Path, *, repo_root: Path
) -> Iterator[tuple[int, os.stat_result]]:
    """Open one regular input without following or losing any pathname binding."""

    root = Path(os.path.abspath(repo_root))
    relative = _relative_path(path, repo_root=root)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directories: list[int] = []
    bindings: list[tuple[int, str, int, tuple[int, ...]]] = []
    descriptor: int | None = None
    try:
        named_root = os.lstat(root)
        current = os.open(root, directory_flags)
        opened_root = os.fstat(current)
        root_identity = _metadata_identity(opened_root)
        if (
            not stat.S_ISDIR(named_root.st_mode)
            or not stat.S_ISDIR(opened_root.st_mode)
            or _metadata_identity(named_root) != root_identity
        ):
            os.close(current)
            raise _error("repository root is not one anchored directory")
        directories.append(current)
        for component in relative.parts[:-1]:
            parent = current
            named_directory = os.stat(
                component, dir_fd=parent, follow_symlinks=False
            )
            current = os.open(component, directory_flags, dir_fd=parent)
            opened_directory = os.fstat(current)
            identity = _metadata_identity(opened_directory)
            if (
                not stat.S_ISDIR(named_directory.st_mode)
                or not stat.S_ISDIR(opened_directory.st_mode)
                or _metadata_identity(named_directory) != identity
            ):
                os.close(current)
                raise _error("input ancestor is not one anchored directory")
            directories.append(current)
            bindings.append((parent, component, current, identity))
        leaf = relative.name
        named_before = os.stat(leaf, dir_fd=current, follow_symlinks=False)
        descriptor = os.open(leaf, file_flags, dir_fd=current)
        opened_before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(named_before.st_mode)
            or not stat.S_ISREG(opened_before.st_mode)
            or stat.S_IMODE(opened_before.st_mode) not in {0o444, 0o644}
            or opened_before.st_nlink < 1
            or _metadata_identity(named_before) != _metadata_identity(opened_before)
        ):
            raise _error(f"required input is not one anchored regular file: {path}")
        yield descriptor, opened_before
        opened_after = os.fstat(descriptor)
        named_after = os.stat(leaf, dir_fd=current, follow_symlinks=False)
        if (
            _metadata_identity(opened_after) != _metadata_identity(opened_before)
            or _metadata_identity(named_after) != _metadata_identity(opened_before)
        ):
            raise _error(f"input changed during anchored read: {path}")
        for parent, component, opened_directory, identity in bindings:
            named_directory = os.stat(
                component, dir_fd=parent, follow_symlinks=False
            )
            if (
                _metadata_identity(os.fstat(opened_directory)) != identity
                or _metadata_identity(named_directory) != identity
            ):
                raise _error(f"input ancestor changed during read: {path}")
        named_root_after = os.lstat(root)
        if (
            _metadata_identity(os.fstat(directories[0])) != root_identity
            or _metadata_identity(named_root_after) != root_identity
        ):
            raise _error(f"repository root changed during input read: {path}")
    except Phase3InputOverlayError:
        raise
    except OSError as exc:
        raise _error(f"cannot open required regular input: {path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for directory in reversed(directories):
            os.close(directory)


def _hash_descriptor(descriptor: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return size, digest.hexdigest()


def _source_record(path: Path, *, role: str, repo_root: Path) -> dict[str, Any]:
    with _anchored_regular(path, repo_root=repo_root) as (descriptor, before):
        size, sha256 = _hash_descriptor(descriptor)
        after = os.fstat(descriptor)
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or size != after.st_size
    ):
        raise _error(f"input changed while hashing: {path}")
    return {
        "role": role,
        "path": _relative_path(path, repo_root=repo_root).as_posix(),
        "bytes": size,
        "sha256": sha256,
    }


def _validate_checkpoint_specs(specs: Sequence[CheckpointSpec]) -> None:
    identities = [spec.identity for spec in specs]
    if len(specs) != 25 or len(set(identities)) != 25:
        raise _error("checkpoint surface must contain 25 unique slots")
    observed_anfis = {
        (spec.seed, spec.module)
        for spec in specs
        if spec.family == "anfis"
    }
    expected_anfis = {
        (seed, module)
        for seed in REGISTERED_SEEDS
        for module in ("N", "F", "T")
    }
    observed_gru = {
        (spec.model_id, spec.seed)
        for spec in specs
        if spec.family == "gru"
    }
    expected_gru = {
        (model_id, seed)
        for model_id in ("A0", "A1")
        for seed in REGISTERED_SEEDS
    }
    if observed_anfis != expected_anfis or observed_gru != expected_gru:
        raise _error("checkpoint surface is not exact 15 ANFIS plus exact 10 A0/A1")
    for spec in specs:
        if spec.seed not in REGISTERED_SEEDS:
            raise _error("checkpoint seed is not registered")
        if spec.family == "anfis":
            if spec.module not in {"N", "F", "T"} or spec.model_id is not None:
                raise _error("ANFIS checkpoint identity is malformed")
        elif spec.family == "gru":
            if spec.model_id not in {"A0", "A1"} or spec.module is not None:
                raise _error("GRU checkpoint identity is malformed")
        else:
            raise _error(f"unsupported checkpoint family: {spec.family}")


def _validate_projection_contract() -> None:
    if len(PANEL_PROJECTION) != len(set(PANEL_PROJECTION)):
        raise _error("panel projection contains duplicate columns")
    forbidden_tokens = ("chl", "chlorophyll", "target", "outcome", "risk_chla")
    forbidden = [
        column
        for column in (*PANEL_PROJECTION, *WARMUP_COLUMNS)
        if any(token in column.casefold() for token in forbidden_tokens)
    ]
    if forbidden:
        raise _error(f"physical projection contains forbidden columns: {forbidden}")
    if set(PANEL_SEASON_TO_OUTPUT.values()) != set(DERIVED_CALENDAR_COLUMNS):
        raise _error("panel-to-runtime season mapping drifted")


def _parquet_schema(path: Path, *, repo_root: Path) -> tuple[list[str], int]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise _error("PyArrow is required for the overlay") from exc
    try:
        with _anchored_regular(path, repo_root=repo_root) as (descriptor, _metadata):
            with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
                parquet = pq.ParquetFile(stream)
                return list(parquet.schema_arrow.names), int(parquet.metadata.num_rows)
    except Exception as exc:
        raise _error(f"cannot inspect Parquet schema: {path}") from exc


def _output_namespace_absent(paths: OverlayPaths, *, repo_root: Path) -> None:
    outputs = (paths.npz_output, paths.warmup_output, paths.manifest_output)
    pointer_paths = (
        paths.npz_output.with_suffix(paths.npz_output.suffix + ".dvc"),
        paths.warmup_output.with_suffix(paths.warmup_output.suffix + ".dvc"),
    )
    for path in (*outputs, *pointer_paths, paths.guard):
        physical = _physical_path(path, repo_root=repo_root)
        if physical.exists() or physical.is_symlink():
            raise _error(f"exclusive output namespace is not empty: {path}")
    for path in outputs:
        parent = _physical_path(path, repo_root=repo_root).parent
        _assert_real_parent(path, repo_root=repo_root)
        prefix = f".{path.name}."
        stale = [
            candidate.name
            for candidate in parent.iterdir()
            if candidate.name.startswith(prefix) and candidate.name.endswith(".tmp")
        ]
        if stale:
            raise _error(f"temporary output namespace is not empty: {stale}")


def check_only(
    *,
    repo_root: Path = PROJECT_ROOT,
    paths: OverlayPaths = OverlayPaths(),
    checkpoint_specs: Sequence[CheckpointSpec] = CHECKPOINT_SPECS,
) -> dict[str, Any]:
    """Validate the outcome-free namespace without writing or decoding rows."""

    root = Path(os.path.abspath(repo_root))
    _validate_checkpoint_specs(checkpoint_specs)
    _validate_projection_contract()
    _output_namespace_absent(paths, repo_root=root)

    history_columns, history_rows = _parquet_schema(paths.history, repo_root=root)
    panel_columns, panel_rows = _parquet_schema(paths.panel, repo_root=root)
    missing_history = sorted(set(HISTORY_PROJECTION) - set(history_columns))
    missing_panel = sorted(set(PANEL_PROJECTION) - set(panel_columns))
    if missing_history or missing_panel:
        raise _error(
            "input Parquet schema is missing required projected columns: "
            f"history={missing_history}, panel={missing_panel}"
        )

    source_records = [
        _source_record(paths.history, role="r10_input_history", repo_root=root),
        _source_record(paths.panel, role="panel_physical_seasonal", repo_root=root),
    ]
    for spec in checkpoint_specs:
        source_records.append(
            _source_record(
                spec.path,
                role=f"{spec.identity}_checkpoint",
                repo_root=root,
            )
        )
    return {
        "manifest_version": MANIFEST_VERSION,
        "surface_id": SURFACE_ID,
        "status": "ready_to_generate",
        "checkpoint_count": len(checkpoint_specs),
        "anfis_checkpoint_count": sum(
            spec.family == "anfis" for spec in checkpoint_specs
        ),
        "anfis_f1_checkpoint_count": sum(
            spec.family == "anfis" for spec in checkpoint_specs
        ),
        "gru_checkpoint_count": sum(
            spec.family == "gru" for spec in checkpoint_specs
        ),
        "history_metadata_rows": history_rows,
        "panel_metadata_rows": panel_rows,
        "source_digest_sha256": _sha256_bytes(
            _canonical_json_text(source_records).encode("utf-8")
        ),
        "panel_projection": list(PANEL_PROJECTION),
        "panel_projection_contains_forbidden_columns": False,
        "opened_outcome_path_count": 0,
        "opened_target_path_count": 0,
        "checkpoint_payloads_decoded": False,
        "scientific_rows_read": False,
        "writes_performed": False,
    }


def _torch_load_checkpoint(
    spec: CheckpointSpec, *, repo_root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise _error("Torch is required to export checkpoint state") from exc
    with _anchored_regular(spec.path, repo_root=repo_root) as (descriptor, before):
        size, sha256 = _hash_descriptor(descriptor)
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
            try:
                payload = torch.load(stream, map_location="cpu", weights_only=True)
            except TypeError as exc:  # pragma: no cover - fail closed on old Torch
                raise _error("Torch runtime lacks weights_only checkpoint loading") from exc
        after = os.fstat(descriptor)
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or size != after.st_size
    ):
        raise _error(f"checkpoint changed while loading: {spec.path}")
    if not isinstance(payload, Mapping):
        raise _error(f"checkpoint payload is not a mapping: {spec.path}")
    source = {
        "role": f"{spec.identity}_checkpoint",
        "path": _relative_path(spec.path, repo_root=repo_root).as_posix(),
        "bytes": size,
        "sha256": sha256,
    }
    return dict(payload), source


def _state_dict(payload: Mapping[str, Any], *, spec: CheckpointSpec) -> dict[str, Any]:
    raw = payload.get("model_state_dict")
    if not isinstance(raw, Mapping) or not raw:
        raise _error(f"checkpoint lacks a non-empty model_state_dict: {spec.identity}")
    state = {str(key): value for key, value in raw.items()}
    if len(state) != len(raw) or any("/" in key or not key for key in state):
        raise _error(f"checkpoint state keys are not reversible: {spec.identity}")
    return state


def _tensor_shape(value: Any, *, context: str) -> tuple[int, ...]:
    shape = getattr(value, "shape", None)
    if shape is None:
        raise _error(f"state tensor shape is unavailable: {context}")
    try:
        return tuple(int(dimension) for dimension in shape)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _error(f"state tensor shape is malformed: {context}") from exc


def _validate_production_anfis_shapes(
    state: Mapping[str, Any], *, module: str, identity: str
) -> None:
    dimension = ANFIS_EXPECTED_INPUT_DIMENSION[module]
    memberships = 3
    rules = memberships**dimension
    expected = {
        "raw_center_gaps": (dimension, memberships + 1),
        "raw_widths": (dimension, memberships),
        "consequent_weights": (rules, dimension),
        "consequent_bias": (rules,),
        "rule_indices": (rules, dimension),
    }
    observed = {
        key: _tensor_shape(state[key], context=f"{identity}/{key}")
        for key in expected
    }
    if observed != expected:
        raise _error(f"ANFIS production tensor shapes drifted: {identity}")


def _validate_production_gru_shapes(
    state: Mapping[str, Any], *, model_id: str, identity: str
) -> None:
    input_dimension = GRU_EXPECTED_INPUT_DIMENSION[model_id]
    hidden = GRU_EXPECTED_HIDDEN_DIMENSION
    expected = {
        "bloom_prior_logits": (3,),
        "risk_prior_logits": (3,),
        "gru.weight_ih_l0": (3 * hidden, input_dimension),
        "gru.weight_hh_l0": (3 * hidden, hidden),
        "gru.bias_ih_l0": (3 * hidden,),
        "gru.bias_hh_l0": (3 * hidden,),
        "bloom_delta.weight": (3, hidden),
        "bloom_delta.bias": (3,),
        "risk_delta.weight": (3, hidden),
        "risk_delta.bias": (3,),
        "risk_logvar.weight": (3, hidden),
        "risk_logvar.bias": (3,),
    }
    observed = {
        key: _tensor_shape(state[key], context=f"{identity}/{key}")
        for key in expected
    }
    if observed != expected:
        raise _error(f"GRU production tensor shapes drifted: {identity}")


def _validate_checkpoint_identity(
    payload: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    spec: CheckpointSpec,
    enforce_production_contract: bool,
) -> dict[str, Any]:
    if spec.family == "anfis":
        payload_module = str(payload.get("module"))
        expected_module = {
            "N": "ANFIS-N",
            "F": "ANFIS-F",
            "T": "ANFIS-T-no-current",
        }[cast(str, spec.module)]
        if (
            payload.get("checkpoint_version") != "closure_anfis_module_v1"
            or payload.get("experiment_id") != "closure_v1"
            or payload_module != expected_module
            or payload.get("base_seed") != spec.seed
        ):
            raise _error(f"ANFIS checkpoint identity drifted: {spec.identity}")
        configuration = payload.get("configuration")
        feature_columns = payload.get("feature_columns")
        if not isinstance(configuration, Mapping) or not isinstance(
            feature_columns, Sequence
        ) or isinstance(feature_columns, (str, bytes)):
            raise _error(f"ANFIS checkpoint configuration is malformed: {spec.identity}")
        normalized = {
            "checkpoint_version": payload["checkpoint_version"],
            "experiment_id": payload["experiment_id"],
            "module": payload_module,
            "base_seed": spec.seed,
            "module_seed": payload.get("module_seed"),
            "feature_columns": [str(value) for value in feature_columns],
            "target_column": payload.get("target_column"),
            "configuration": dict(configuration),
        }
        if enforce_production_contract:
            module = cast(str, spec.module)
            expected_dimension = ANFIS_EXPECTED_INPUT_DIMENSION[module]
            required_config = {
                "memberships_per_input": 3,
                "center_constraint": "unit",
                "min_width": 0.03,
                "min_gap": 0.0001,
                "output_activation": "sigmoid",
            }
            if (
                len(normalized["feature_columns"]) != expected_dimension
                or tuple(normalized["feature_columns"])
                != ANFIS_EXPECTED_FEATURE_COLUMNS[module]
                or normalized["target_column"]
                != ANFIS_EXPECTED_TARGET_COLUMN[module]
                or any(
                    configuration.get(key) != value
                    for key, value in required_config.items()
                )
            ):
                raise _error(f"ANFIS production architecture drifted: {spec.identity}")
            if set(state) != ANFIS_EXPECTED_STATE_KEYS:
                raise _error(f"ANFIS state-key contract drifted: {spec.identity}")
            _validate_production_anfis_shapes(
                state, module=module, identity=spec.identity
            )
        return normalized

    if (
        payload.get("model_version")
        != "closure_anfis_ablation_direct_multitask_v1"
        or payload.get("experiment_id") != "closure_v1"
        or payload.get("model_id") != spec.model_id
        or payload.get("base_seed") != spec.seed
        or payload.get("artifact_role") != "raw_best_checkpoint"
    ):
        raise _error(f"GRU checkpoint identity drifted: {spec.identity}")
    configuration = payload.get("config")
    if not isinstance(configuration, Mapping):
        raise _error(f"GRU checkpoint configuration is malformed: {spec.identity}")
    normalized = {
        "model_version": payload["model_version"],
        "experiment_id": payload["experiment_id"],
        "surface_id": payload.get("surface_id"),
        "gate": payload.get("gate"),
        "artifact_role": payload["artifact_role"],
        "model_id": payload["model_id"],
        "base_seed": spec.seed,
        "upstream_state_seed": payload.get("upstream_state_seed"),
        "device": payload.get("device"),
        "config": dict(configuration),
        "bloom_training_priors": payload.get("bloom_training_priors"),
        "risk_training_priors": payload.get("risk_training_priors"),
    }
    if enforce_production_contract:
        model_id = cast(str, spec.model_id)
        if (
            payload.get("surface_id") != "closure_v1_wqp_adaptive_no_current_chla"
            or payload.get("gate") != "E0-MT"
            or payload.get("device") != "cpu"
            or payload.get("upstream_state_seed")
            != (spec.seed if model_id == "A1" else None)
            or configuration.get("family")
            != "direct_multitask_probabilistic_gru"
            or configuration.get("model_id") != model_id
            or configuration.get("input_dimension")
            != GRU_EXPECTED_INPUT_DIMENSION[model_id]
            or configuration.get("hidden_dimension")
            != GRU_EXPECTED_HIDDEN_DIMENSION
            or configuration.get("recurrent_layers") != 1
            or configuration.get("history_length_months") != GRU_HISTORY_LENGTH
            or configuration.get("risk_logvar_clamp")
            != [GRU_LOGVAR_MIN, GRU_LOGVAR_MAX]
            or set(state) != GRU_EXPECTED_STATE_KEYS
        ):
            raise _error(f"GRU production architecture drifted: {spec.identity}")
        _validate_production_gru_shapes(
            state, model_id=model_id, identity=spec.identity
        )
    return normalized


def _canonical_array(value: Any, *, context: str) -> np.ndarray:
    try:
        array = value.detach().cpu().contiguous().numpy()
    except (AttributeError, TypeError, RuntimeError) as exc:
        raise _error(f"state value is not a dense CPU-convertible tensor: {context}") from exc
    if array.dtype.hasobject or array.dtype.fields is not None:
        raise _error(f"state tensor has a non-portable dtype: {context}")
    dtype = array.dtype
    if dtype.byteorder == ">" or (dtype.byteorder == "=" and not np.little_endian):
        array = array.astype(dtype.newbyteorder("<"), copy=False)
    return np.ascontiguousarray(array)


def _npy_bytes(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.lib.format.write_array(buffer, array, allow_pickle=False)
    return buffer.getvalue()


def _array_record(
    *, npz_key: str, state_key: str, array: np.ndarray
) -> dict[str, Any]:
    return {
        "npz_key": npz_key,
        "state_key": state_key,
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "element_count": int(array.size),
        "data_sha256": _sha256_bytes(array.tobytes(order="C")),
        "npy_sha256": _sha256_bytes(_npy_bytes(array)),
    }


def _softplus_numpy(values: np.ndarray) -> np.ndarray:
    return np.log1p(np.exp(-np.abs(values))) + np.maximum(values, 0.0)


def _sigmoid_numpy(values: np.ndarray) -> np.ndarray:
    positive = values >= 0.0
    output = np.empty_like(values)
    output[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exponential = np.exp(values[~positive])
    output[~positive] = exponential / (1.0 + exponential)
    return output


def _anfis_numpy_forward(
    state: Mapping[str, np.ndarray],
    features: np.ndarray,
    *,
    configuration: Mapping[str, Any],
) -> np.ndarray:
    x = np.asarray(features, dtype=np.float32)
    raw_widths = np.asarray(state["raw_widths"], dtype=np.float32)
    min_width = float(configuration.get("min_width", 0.03))
    min_gap = float(configuration.get("min_gap", 0.0001))
    center_constraint = str(configuration.get("center_constraint", "unit"))
    if center_constraint == "unit":
        raw_gaps = np.asarray(state["raw_center_gaps"], dtype=np.float32)
        shifted = raw_gaps - raw_gaps.max(axis=1, keepdims=True)
        proportions = np.exp(shifted)
        proportions /= proportions.sum(axis=1, keepdims=True)
        residual = 1.0 - min_gap * raw_gaps.shape[1]
        gaps = min_gap + residual * proportions
        centers = np.cumsum(gaps[:, :-1], axis=1)
    elif center_constraint == "ordered":
        first = np.asarray(state["first_center"], dtype=np.float32)[:, None]
        deltas = _softplus_numpy(
            np.asarray(state["raw_deltas"], dtype=np.float32)
        ) + min_gap
        centers = np.concatenate(
            [first, first + np.cumsum(deltas, axis=1)], axis=1
        )
    else:
        raise _error(f"unsupported ANFIS center constraint: {center_constraint}")
    widths = _softplus_numpy(raw_widths) + min_width
    scaled = (x[:, :, None] - centers[None, :, :]) / widths[None, :, :]
    memberships = np.exp(np.float32(-0.5) * scaled**2)
    rule_indices = np.asarray(state["rule_indices"], dtype=np.int64)
    firing = np.ones((len(x), len(rule_indices)), dtype=np.float32)
    for feature_index in range(x.shape[1]):
        firing *= memberships[:, feature_index, rule_indices[:, feature_index]]
    normalized = firing / np.maximum(
        firing.sum(axis=1, keepdims=True), np.float32(1.0e-12)
    )
    weights = np.asarray(state["consequent_weights"], dtype=np.float32)
    bias = np.asarray(state["consequent_bias"], dtype=np.float32)
    raw = (normalized * (x @ weights.T + bias)).sum(axis=1)
    activation = str(configuration.get("output_activation", "sigmoid"))
    if activation == "sigmoid":
        return _sigmoid_numpy(raw)
    if activation == "clip":
        return np.clip(raw, 0.0, 1.0)
    raise _error(f"unsupported ANFIS output activation: {activation}")


def _anfis_torch_forward(
    original_state: Mapping[str, Any],
    features: np.ndarray,
    *,
    configuration: Mapping[str, Any],
) -> np.ndarray:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise _error("Torch ANFIS runtime is unavailable") from exc
    raw_widths = original_state.get("raw_widths")
    if raw_widths is None or getattr(raw_widths, "ndim", None) != 2:
        raise _error("ANFIS raw_widths shape is unavailable")
    min_width = float(configuration.get("min_width", 0.03))
    min_gap = float(configuration.get("min_gap", 0.0001))
    center_constraint = str(configuration.get("center_constraint", "unit"))
    with torch.no_grad():
        x = torch.as_tensor(features, dtype=torch.float32)
        if center_constraint == "unit":
            raw_gaps = original_state.get("raw_center_gaps")
            if raw_gaps is None or getattr(raw_gaps, "ndim", None) != 2:
                raise _error("ANFIS raw_center_gaps shape is unavailable")
            residual = 1.0 - min_gap * int(raw_gaps.shape[1])
            gaps = min_gap + residual * torch.nn.functional.softmax(
                raw_gaps, dim=1
            )
            centers = torch.cumsum(gaps[:, :-1], dim=1)
        elif center_constraint == "ordered":
            first_center = original_state.get("first_center")
            raw_deltas = original_state.get("raw_deltas")
            if first_center is None or raw_deltas is None:
                raise _error("ANFIS ordered-center state is unavailable")
            deltas = torch.nn.functional.softplus(raw_deltas) + min_gap
            centers = torch.cat(
                [
                    first_center[:, None],
                    first_center[:, None] + torch.cumsum(deltas, dim=1),
                ],
                dim=1,
            )
        else:
            raise _error(
                f"unsupported ANFIS center constraint: {center_constraint}"
            )
        widths = torch.nn.functional.softplus(raw_widths) + min_width
        centers = centers.to(device=x.device, dtype=x.dtype)
        widths = widths.to(device=x.device, dtype=x.dtype)
        scaled = (x[:, :, None] - centers[None, :, :]) / widths[None, :, :]
        memberships = torch.exp(-0.5 * scaled**2)
        rule_indices = original_state.get("rule_indices")
        if rule_indices is None or getattr(rule_indices, "ndim", None) != 2:
            raise _error("ANFIS rule_indices shape is unavailable")
        rule_indices = rule_indices.to(device=x.device)
        per_feature = [
            memberships[:, feature_index, rule_indices[:, feature_index]]
            for feature_index in range(int(x.shape[1]))
        ]
        firing = torch.stack(per_feature, dim=0).prod(dim=0)
        normalized = firing / torch.clamp(
            firing.sum(dim=1, keepdim=True), min=1.0e-12
        )
        consequent_weights = original_state.get("consequent_weights")
        consequent_bias = original_state.get("consequent_bias")
        if consequent_weights is None or consequent_bias is None:
            raise _error("ANFIS consequent state is unavailable")
        rule_outputs = (
            x @ consequent_weights.to(device=x.device, dtype=x.dtype).T
            + consequent_bias.to(device=x.device, dtype=x.dtype)
        )
        raw_output = (normalized * rule_outputs).sum(dim=1)
        output_activation = str(
            configuration.get("output_activation", "sigmoid")
        )
        if output_activation == "sigmoid":
            result = torch.sigmoid(raw_output)
        elif output_activation == "clip":
            result = torch.clamp(raw_output, 0.0, 1.0)
        else:
            raise _error(
                f"unsupported ANFIS output activation: {output_activation}"
            )
        return result.detach().cpu().numpy()


def _gru_numpy_forward(
    state: Mapping[str, np.ndarray], features: np.ndarray
) -> np.ndarray:
    x = np.asarray(features, dtype=np.float32)
    weight_ih = np.asarray(state["gru.weight_ih_l0"], dtype=np.float32)
    weight_hh = np.asarray(state["gru.weight_hh_l0"], dtype=np.float32)
    bias_ih = np.asarray(state["gru.bias_ih_l0"], dtype=np.float32)
    bias_hh = np.asarray(state["gru.bias_hh_l0"], dtype=np.float32)
    hidden_size = weight_hh.shape[1]
    hidden = np.zeros((x.shape[0], hidden_size), dtype=np.float32)
    w_ir, w_iz, w_in = np.split(weight_ih, 3, axis=0)
    w_hr, w_hz, w_hn = np.split(weight_hh, 3, axis=0)
    b_ir, b_iz, b_in = np.split(bias_ih, 3)
    b_hr, b_hz, b_hn = np.split(bias_hh, 3)
    for step in range(x.shape[1]):
        current = x[:, step, :]
        reset = _sigmoid_numpy(current @ w_ir.T + b_ir + hidden @ w_hr.T + b_hr)
        update = _sigmoid_numpy(current @ w_iz.T + b_iz + hidden @ w_hz.T + b_hz)
        candidate = np.tanh(
            current @ w_in.T + b_in + reset * (hidden @ w_hn.T + b_hn)
        )
        hidden = (np.float32(1.0) - update) * candidate + update * hidden

    def linear(prefix: str) -> np.ndarray:
        weight = np.asarray(state[f"{prefix}.weight"], dtype=np.float32)
        bias = np.asarray(state[f"{prefix}.bias"], dtype=np.float32)
        return hidden @ weight.T + bias

    bloom = np.asarray(state["bloom_prior_logits"], dtype=np.float32) + linear(
        "bloom_delta"
    )
    risk_mu = _sigmoid_numpy(
        np.asarray(state["risk_prior_logits"], dtype=np.float32)
        + linear("risk_delta")
    )
    logvar = np.clip(linear("risk_logvar"), GRU_LOGVAR_MIN, GRU_LOGVAR_MAX)
    return np.concatenate([bloom, risk_mu, logvar], axis=1)


def _gru_torch_forward(
    original_state: Mapping[str, Any], features: np.ndarray
) -> np.ndarray:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise _error("Torch GRU runtime is unavailable") from exc
    weight_ih = original_state.get("gru.weight_ih_l0")
    weight_hh = original_state.get("gru.weight_hh_l0")
    if weight_ih is None or weight_hh is None:
        raise _error("GRU recurrent weights are unavailable")
    input_size = int(weight_ih.shape[1])
    hidden_size = int(weight_hh.shape[1])
    gru = torch.nn.GRU(input_size, hidden_size, num_layers=1, batch_first=True)
    gru.load_state_dict(
        {
            key.removeprefix("gru."): value
            for key, value in original_state.items()
            if key.startswith("gru.")
        },
        strict=True,
    )
    gru.eval()
    tensor = torch.as_tensor(features, dtype=torch.float32)
    with torch.no_grad():
        _, recurrent = gru(tensor)
        hidden = recurrent[-1]

        def linear(prefix: str) -> Any:
            return torch.nn.functional.linear(
                hidden,
                original_state[f"{prefix}.weight"],
                original_state[f"{prefix}.bias"],
            )

        bloom = original_state["bloom_prior_logits"] + linear("bloom_delta")
        risk_mu = torch.sigmoid(
            original_state["risk_prior_logits"] + linear("risk_delta")
        )
        logvar = torch.clamp(
            linear("risk_logvar"), min=GRU_LOGVAR_MIN, max=GRU_LOGVAR_MAX
        )
        result = torch.cat([bloom, risk_mu, logvar], dim=1)
    return result.detach().cpu().numpy()


def _fixture(shape: tuple[int, ...]) -> np.ndarray:
    count = int(np.prod(shape))
    values = ((np.arange(count, dtype=np.int64) * 37 + 11) % 101) / 100.0
    return values.astype(np.float32).reshape(shape)


def _parity_record(
    *,
    spec: CheckpointSpec,
    original_state: Mapping[str, Any],
    exported_state: Mapping[str, np.ndarray],
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    if spec.family == "anfis":
        raw_widths = exported_state.get("raw_widths")
        if raw_widths is None or raw_widths.ndim != 2:
            raise _error(f"ANFIS width tensor is malformed: {spec.identity}")
        fixture = _fixture((7, int(raw_widths.shape[0])))
        configuration = identity.get("configuration")
        if not isinstance(configuration, Mapping):
            raise _error(f"ANFIS configuration is unavailable: {spec.identity}")
        numpy_output = _anfis_numpy_forward(
            exported_state, fixture, configuration=configuration
        )
        torch_output = _anfis_torch_forward(
            original_state, fixture, configuration=configuration
        )
        output_names = ["prediction"]
    else:
        weight_ih = exported_state.get("gru.weight_ih_l0")
        if weight_ih is None or weight_ih.ndim != 2:
            raise _error(f"GRU input tensor is malformed: {spec.identity}")
        fixture = _fixture((4, GRU_HISTORY_LENGTH, int(weight_ih.shape[1])))
        numpy_output = _gru_numpy_forward(exported_state, fixture)
        torch_output = _gru_torch_forward(original_state, fixture)
        output_names = [
            "bloom_logit_h1",
            "bloom_logit_h2",
            "bloom_logit_h3",
            "risk_mean_h1",
            "risk_mean_h2",
            "risk_mean_h3",
            "risk_logvar_h1",
            "risk_logvar_h2",
            "risk_logvar_h3",
        ]
    if numpy_output.shape != torch_output.shape:
        raise _error(f"NumPy/Torch parity shape differs: {spec.identity}")
    delta = np.abs(
        numpy_output.astype(np.float64) - torch_output.astype(np.float64)
    )
    max_error = float(delta.max(initial=0.0))
    passed = bool(
        np.allclose(
            numpy_output,
            torch_output,
            rtol=PARITY_RTOL,
            atol=PARITY_ATOL,
            equal_nan=False,
        )
    )
    if not passed:
        raise _error(
            f"NumPy/Torch parity failed for {spec.identity}: {max_error:.12g}"
        )
    return {
        "fixture_version": PARITY_FIXTURE_VERSION,
        "fixture_shape": list(fixture.shape),
        "fixture_dtype": fixture.dtype.str,
        "output_names": output_names,
        "output_shape": list(numpy_output.shape),
        "atol": PARITY_ATOL,
        "rtol": PARITY_RTOL,
        "maximum_absolute_error": max_error,
        "passed": True,
    }


def _checkpoint_export(
    spec: CheckpointSpec,
    *,
    repo_root: Path,
    enforce_production_contract: bool,
) -> tuple[dict[str, np.ndarray], dict[str, Any], dict[str, Any]]:
    payload, source = _torch_load_checkpoint(spec, repo_root=repo_root)
    state = _state_dict(payload, spec=spec)
    identity = _validate_checkpoint_identity(
        payload,
        state,
        spec=spec,
        enforce_production_contract=enforce_production_contract,
    )
    arrays: dict[str, np.ndarray] = {}
    array_records: list[dict[str, Any]] = []
    exported_state: dict[str, np.ndarray] = {}
    for state_key in sorted(state):
        array = _canonical_array(
            state[state_key], context=f"{spec.identity}/{state_key}"
        )
        npz_key = f"{spec.identity}/{state_key}"
        arrays[npz_key] = array
        exported_state[state_key] = array
        record = _array_record(
            npz_key=npz_key, state_key=state_key, array=array
        )
        record.update(
            {
                "origin_path": source["path"],
                "origin_sha256": source["sha256"],
                "checkpoint_family": spec.family,
                "surface_model_id": "F1" if spec.family == "anfis" else spec.model_id,
                "seed": spec.seed,
                "module": spec.module,
                "model_id": spec.model_id,
            }
        )
        array_records.append(record)
    parity = _parity_record(
        spec=spec,
        original_state=state,
        exported_state=exported_state,
        identity=identity,
    )
    checkpoint_record = {
        "family": spec.family,
        "surface_model_id": "F1" if spec.family == "anfis" else spec.model_id,
        "seed": spec.seed,
        "module": spec.module,
        "model_id": spec.model_id,
        "source_path": source["path"],
        "source_sha256": source["sha256"],
        "identity": identity,
        "state_dict_key_count": len(array_records),
        "state_dict_arrays": array_records,
        "parity": parity,
    }
    return arrays, checkpoint_record, source


def _deterministic_npz_bytes(arrays: Mapping[str, np.ndarray]) -> bytes:
    if not arrays or any(not key or key.endswith(".npy") for key in arrays):
        raise _error("NPZ array namespace is malformed")
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for key in sorted(arrays):
            info = zipfile.ZipInfo(f"{key}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            info.create_system = 3
            archive.writestr(info, _npy_bytes(np.asarray(arrays[key])))
    payload = buffer.getvalue()
    try:
        with np.load(io.BytesIO(payload), allow_pickle=False) as loaded:
            if loaded.files != sorted(arrays):
                raise _error("NPZ archive key ordering/content drifted")
            for key in loaded.files:
                if not np.array_equal(loaded[key], arrays[key], equal_nan=True):
                    raise _error(f"NPZ archive array round-trip failed: {key}")
    except Phase3InputOverlayError:
        raise
    except Exception as exc:
        raise _error("constructed NPZ archive is unreadable") from exc
    return payload


def _build_npz(
    specs: Sequence[CheckpointSpec],
    *,
    repo_root: Path,
    enforce_production_contract: bool,
) -> tuple[bytes, dict[str, Any], list[dict[str, Any]]]:
    _activate_scientific_runtime(repo_root)
    arrays: dict[str, np.ndarray] = {}
    checkpoints: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for spec in specs:
        exported, record, source = _checkpoint_export(
            spec,
            repo_root=repo_root,
            enforce_production_contract=enforce_production_contract,
        )
        collision = set(arrays) & set(exported)
        if collision:
            raise _error(f"NPZ key collision: {sorted(collision)}")
        arrays.update(exported)
        checkpoints.append(record)
        sources.append(source)
    checkpoints.sort(
        key=lambda record: (
            str(record["family"]),
            str(record["model_id"] or record["module"]),
            int(record["seed"]),
        )
    )
    array_records = sorted(
        (
            dict(record)
            for checkpoint in checkpoints
            for record in cast(list[dict[str, Any]], checkpoint["state_dict_arrays"])
        ),
        key=lambda record: str(record["npz_key"]),
    )
    internal_index = {
        "format_version": NPZ_INDEX_VERSION,
        "key_dialect": {
            "anfis": "anfis/{seed}/{module}/{state_key}",
            "anfis_modules": ["N", "F", "T"],
            "gru": "gru/{model_id}/{seed}/{state_key}",
            "gru_model_ids": ["A0", "A1"],
            "state_key_encoding": "literal_utf8_no_slash",
        },
        "checkpoint_count": len(checkpoints),
        "state_dict_array_count": len(array_records),
        "array_keys": [record["npz_key"] for record in array_records],
        "arrays": array_records,
        "checkpoints": checkpoints,
    }
    internal_payload = _canonical_json_text(internal_index).encode("utf-8")
    arrays["__manifest_json__"] = np.frombuffer(internal_payload, dtype=np.uint8).copy()
    npz_payload = _deterministic_npz_bytes(arrays)
    maximum_errors = [
        float(cast(Mapping[str, Any], record["parity"])["maximum_absolute_error"])
        for record in checkpoints
    ]
    export_summary = {
        "format_version": NPZ_INDEX_VERSION,
        "internal_manifest_key": "__manifest_json__",
        "internal_manifest_encoding": "uint8_utf8_canonical_json",
        "internal_manifest_bytes": len(internal_payload),
        "internal_manifest_sha256": _sha256_bytes(internal_payload),
        "key_dialect": internal_index["key_dialect"],
        "checkpoint_count": len(checkpoints),
        "anfis_checkpoint_count": sum(
            record["family"] == "anfis" for record in checkpoints
        ),
        "anfis_f1_checkpoint_count": sum(
            record["surface_model_id"] == "F1" for record in checkpoints
        ),
        "gru_checkpoint_count": sum(
            record["family"] == "gru" for record in checkpoints
        ),
        "state_dict_array_count": len(array_records),
        "archive_array_count": len(arrays),
        "archive_keys": sorted(arrays),
        "arrays": array_records,
        "checkpoints": checkpoints,
        "parity": {
            "fixture_version": PARITY_FIXTURE_VERSION,
            "atol": PARITY_ATOL,
            "rtol": PARITY_RTOL,
            "checkpoint_count": len(checkpoints),
            "passed_checkpoint_count": len(checkpoints),
            "maximum_absolute_error": max(maximum_errors, default=0.0),
            "anfis_maximum_absolute_error": max(
                (
                    float(
                        cast(Mapping[str, Any], record["parity"])[
                            "maximum_absolute_error"
                        ]
                    )
                    for record in checkpoints
                    if record["family"] == "anfis"
                ),
                default=0.0,
            ),
            "gru_maximum_absolute_error": max(
                (
                    float(
                        cast(Mapping[str, Any], record["parity"])[
                            "maximum_absolute_error"
                        ]
                    )
                    for record in checkpoints
                    if record["family"] == "gru"
                ),
                default=0.0,
            ),
            "passed": True,
        },
    }
    return npz_payload, export_summary, sources


def _month_index(value: Any) -> int:
    text = str(value)
    if len(text) != 7 or text[4] != "-" or not (
        text[:4].isdigit() and text[5:].isdigit()
    ):
        raise _error(f"calendar month is malformed: {text!r}")
    year = int(text[:4])
    month = int(text[5:])
    if year < 1900 or month < 1 or month > 12:
        raise _error(f"calendar month is out of range: {text!r}")
    return year * 12 + month - 1


def _month_text(index: int) -> str:
    year, zero_based_month = divmod(index, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"


def _calendar_features(month_index: int) -> dict[str, float]:
    month = month_index % 12
    annual = 2.0 * math.pi * month / 12.0
    return {
        "season_sin_annual": math.sin(annual),
        "season_cos_annual": math.cos(annual),
        "season_sin_semiannual": math.sin(2.0 * annual),
        "season_cos_semiannual": math.cos(2.0 * annual),
    }


def _numeric_or_none(value: Any, *, column: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise _error(f"physical input is boolean: {column}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _error(f"physical input is not numeric: {column}") from exc
    return number if math.isfinite(number) else None


def _read_parquet_projection(
    path: Path,
    *,
    columns: Sequence[str],
    filters: list[tuple[str, str, Any]],
    repo_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise _error("PyArrow is required for projected Parquet reads") from exc
    with _anchored_regular(path, repo_root=repo_root) as (descriptor, before):
        size, sha256 = _hash_descriptor(descriptor)
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
            table = pq.read_table(stream, columns=list(columns), filters=filters)
        after = os.fstat(descriptor)
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or size != after.st_size
    ):
        raise _error(f"Parquet input changed while reading: {path}")
    if list(table.column_names) != list(columns):
        raise _error(f"Parquet projection drifted: {path}")
    source = {
        "path": _relative_path(path, repo_root=repo_root).as_posix(),
        "bytes": size,
        "sha256": sha256,
    }
    return [cast(dict[str, Any], row) for row in table.to_pylist()], source


def _first_history_months(
    *, repo_root: Path, path: Path, expected_site_count: int
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    rows, source = _read_parquet_projection(
        path,
        columns=HISTORY_PROJECTION,
        filters=[
            ("source_id", "=", "wqp"),
            ("assignment_role", "=", "internal_holdout"),
        ],
        repo_root=repo_root,
    )
    by_site: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if set(row) != set(HISTORY_PROJECTION):
            raise _error("R10 history projection dialect drifted")
        if row["source_id"] != "wqp" or row["assignment_role"] != "internal_holdout":
            raise _error("R10 history projection escaped location_holdout")
        site_id = str(row["site_id"])
        group_id = str(row["holdout_group_id"])
        if not site_id or not group_id:
            raise _error("R10 history contains an empty holdout identity")
        month_index = _month_index(row["history_year_month"])
        key = ("wqp", site_id)
        current = by_site.get(key)
        if current is None:
            by_site[key] = {
                "holdout_group_id": group_id,
                "first_month_index": month_index,
            }
        else:
            if current["holdout_group_id"] != group_id:
                raise _error("R10 holdout group changes within a site")
            current["first_month_index"] = min(
                int(current["first_month_index"]), month_index
            )
    if len(by_site) != expected_site_count:
        raise _error(
            f"R10 history must retain exactly {expected_site_count} holdout sites; "
            f"observed {len(by_site)}"
        )
    result = [
        {
            "source_id": source_id,
            "site_id": site_id,
            "holdout_group_id": str(values["holdout_group_id"]),
            "first_history_year_month": _month_text(
                int(values["first_month_index"])
            ),
            "warmup_year_month": _month_text(
                int(values["first_month_index"]) - 1
            ),
        }
        for (source_id, site_id), values in sorted(by_site.items())
    ]
    source["role"] = "r10_input_history"
    return result, source


def _build_warmup_records(
    *,
    repo_root: Path,
    paths: OverlayPaths,
    expected_site_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    first_months, history_source = _first_history_months(
        repo_root=repo_root,
        path=paths.history,
        expected_site_count=expected_site_count,
    )
    site_ids = [row["site_id"] for row in first_months]
    warmup_months = sorted({row["warmup_year_month"] for row in first_months})
    panel_rows, panel_source = _read_parquet_projection(
        paths.panel,
        columns=PANEL_PROJECTION,
        filters=[
            ("source_id", "=", "wqp"),
            ("site_id", "in", site_ids),
            ("year_month", "in", warmup_months),
        ],
        repo_root=repo_root,
    )
    panel_source["role"] = "panel_physical_seasonal"
    panel_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    expected_keys = {
        (row["source_id"], row["site_id"], row["warmup_year_month"])
        for row in first_months
    }
    seasonal_max_error = 0.0
    for raw in panel_rows:
        if set(raw) != set(PANEL_PROJECTION):
            raise _error("panel projection dialect drifted")
        key = (str(raw["source_id"]), str(raw["site_id"]), str(raw["year_month"]))
        if key not in expected_keys:
            continue
        if key in panel_by_key:
            raise _error("panel warm-up projection has a duplicate site/month")
        calendar = _calendar_features(_month_index(key[2]))
        for panel_column, output_column in PANEL_SEASON_TO_OUTPUT.items():
            observed = _numeric_or_none(raw[panel_column], column=panel_column)
            if observed is None:
                raise _error("present panel row has a missing seasonal coordinate")
            error = abs(observed - calendar[output_column])
            seasonal_max_error = max(seasonal_max_error, error)
        panel_by_key[key] = {
            column: _numeric_or_none(raw[column], column=column)
            for column in PHYSICAL_FEATURE_COLUMNS
        }

    records: list[dict[str, Any]] = []
    for identity in first_months:
        key = (
            identity["source_id"],
            identity["site_id"],
            identity["warmup_year_month"],
        )
        physical = panel_by_key.get(key)
        calendar = _calendar_features(_month_index(identity["warmup_year_month"]))
        record: dict[str, Any] = {
            "source_id": identity["source_id"],
            "site_id": identity["site_id"],
            "year_month": identity["warmup_year_month"],
            "row_present": physical is not None,
        }
        record.update(
            {
                column: None if physical is None else physical[column]
                for column in PHYSICAL_FEATURE_COLUMNS
            }
        )
        record.update(calendar)
        if tuple(record) != WARMUP_COLUMNS:
            raise _error("warm-up record column order drifted")
        records.append(record)
    if len(records) != expected_site_count or len(
        {(record["source_id"], record["site_id"]) for record in records}
    ) != expected_site_count:
        raise _error("warm-up surface is not one row per locked holdout site")
    summary = {
        "algorithm": "calendar_month_preceding_site_first_r10_history_month_v1",
        "site_count": len(records),
        "row_count": len(records),
        "row_present_count": sum(bool(record["row_present"]) for record in records),
        "row_missing_count": sum(not bool(record["row_present"]) for record in records),
        "source_ids": sorted({str(record["source_id"]) for record in records}),
        "assignment_roles": ["internal_holdout"],
        "holdout_group_count": len(
            {identity["holdout_group_id"] for identity in first_months}
        ),
        "first_history_months_sha256": _sha256_bytes(
            _canonical_json_text(first_months).encode("utf-8")
        ),
        "panel_projection": list(PANEL_PROJECTION),
        "panel_projection_count": len(PANEL_PROJECTION),
        "panel_projection_contains_chlorophyll": False,
        "panel_projection_contains_target": False,
        "panel_seasonal_projection": list(PANEL_SEASON_COLUMNS),
        "panel_seasonal_values_used_for_runtime": False,
        "runtime_seasonal_algorithm": (
            "calendar_month_zero_based_fourier_annual_semiannual_v1"
        ),
        "panel_to_runtime_season_comparison": PANEL_SEASON_TO_OUTPUT,
        "panel_to_runtime_season_maximum_absolute_difference": seasonal_max_error,
        "physical_missing_counts": {
            column: sum(record[column] is None for record in records)
            for column in PHYSICAL_FEATURE_COLUMNS
        },
        "calendar_missing_counts": {
            column: sum(record[column] is None for record in records)
            for column in DERIVED_CALENDAR_COLUMNS
        },
    }
    return records, summary, [history_source, panel_source]


def _warmup_parquet_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise _error("PyArrow is required to serialize warm-up inputs") from exc
    fields = []
    string_columns = {
        "source_id",
        "site_id",
        "year_month",
    }
    for column in WARMUP_COLUMNS:
        if column in string_columns:
            data_type = pa.string()
        elif column == "row_present":
            data_type = pa.bool_()
        else:
            data_type = pa.float64()
        fields.append(pa.field(column, data_type, nullable=True))
    schema = pa.schema(fields)
    table = pa.Table.from_pylist([dict(record) for record in records], schema=schema)
    if list(table.column_names) != list(WARMUP_COLUMNS):
        raise _error("constructed warm-up table schema drifted")
    buffer = io.BytesIO()
    pq.write_table(
        table,
        buffer,
        compression="zstd",
        use_dictionary=False,
        write_statistics=True,
        data_page_version="1.0",
    )
    payload = buffer.getvalue()
    parquet = pq.ParquetFile(io.BytesIO(payload))
    if parquet.metadata.num_rows != len(records):
        raise _error("constructed warm-up Parquet row count drifted")
    return payload


def _parquet_output_record(
    path: Path, payload: bytes, records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise _error("PyArrow is required to describe warm-up output") from exc
    parquet = pq.ParquetFile(io.BytesIO(payload))
    return {
        "role": "adaptive_state_warmup",
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "row_count": int(parquet.metadata.num_rows),
        "site_count": len({str(record["site_id"]) for record in records}),
        "columns": list(parquet.schema_arrow.names),
        "arrow_schema": [
            {
                "name": field.name,
                "type": str(field.type),
                "nullable": bool(field.nullable),
            }
            for field in parquet.schema_arrow
        ],
    }


def _npz_output_record(path: Path, payload: bytes, summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "role": "phase3_runtime_weights",
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "checkpoint_count": summary["checkpoint_count"],
        "state_dict_array_count": summary["state_dict_array_count"],
        "archive_array_count": summary["archive_array_count"],
        "archive_keys": summary["archive_keys"],
    }


def _git_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value if len(value) == 40 else None


def _directory_identity(metadata: os.stat_result) -> tuple[int, ...]:
    """Stable directory identity fields unaffected by owned entry creation."""

    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        stat.S_IMODE(metadata.st_mode),
    )


def _open_directory_anchor(
    relative_directory: Path,
    *,
    repo_root: Path,
    label: str,
) -> DirectoryAnchor:
    root = Path(os.path.abspath(repo_root))
    relative = _relative_path(relative_directory, repo_root=root)
    parts = () if relative == Path(".") else relative.parts
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptors: list[int] = []
    bindings: list[tuple[int, str, int, tuple[int, ...]]] = []
    try:
        named_root = os.lstat(root)
        root_fd = os.open(root, flags)
        descriptors.append(root_fd)
        opened_root = os.fstat(root_fd)
        root_identity = _directory_identity(opened_root)
        if (
            stat.S_ISLNK(named_root.st_mode)
            or not stat.S_ISDIR(named_root.st_mode)
            or not stat.S_ISDIR(opened_root.st_mode)
            or _directory_identity(named_root) != root_identity
        ):
            raise _error(f"{label} repository root is unsafe")
        current = root_fd
        for component in parts:
            named = os.stat(component, dir_fd=current, follow_symlinks=False)
            child = os.open(component, flags, dir_fd=current)
            opened = os.fstat(child)
            identity = _directory_identity(opened)
            if (
                stat.S_ISLNK(named.st_mode)
                or not stat.S_ISDIR(named.st_mode)
                or not stat.S_ISDIR(opened.st_mode)
                or _directory_identity(named) != identity
            ):
                os.close(child)
                raise _error(f"{label} ancestor is unsafe")
            descriptors.append(child)
            bindings.append((current, component, child, identity))
            current = child
        return DirectoryAnchor(
            repo_root=root,
            descriptors=descriptors,
            bindings=bindings,
            root_identity=root_identity,
        )
    except Phase3InputOverlayError:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise
    except OSError as exc:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise _error(f"{label} parent cannot be opened without following names") from exc


def _recapture_directory_anchor(anchor: DirectoryAnchor, *, label: str) -> None:
    if anchor.closed:
        raise _error(f"{label} parent anchor is closed")
    try:
        named_root = os.lstat(anchor.repo_root)
        if (
            stat.S_ISLNK(named_root.st_mode)
            or _directory_identity(named_root) != anchor.root_identity
            or _directory_identity(os.fstat(anchor.descriptors[0]))
            != anchor.root_identity
        ):
            raise _error(f"{label} repository root was replaced")
        for parent, component, child, identity in anchor.bindings:
            named = os.stat(component, dir_fd=parent, follow_symlinks=False)
            if (
                stat.S_ISLNK(named.st_mode)
                or _directory_identity(named) != identity
                or _directory_identity(os.fstat(child)) != identity
            ):
                raise _error(f"{label} ancestor was replaced")
    except Phase3InputOverlayError:
        raise
    except OSError as exc:
        raise _error(f"{label} ancestor recapture failed") from exc


def _close_directory_anchor(
    anchor: DirectoryAnchor,
    *,
    suppress_errors: bool = False,
) -> None:
    if anchor.closed:
        return
    errors: list[OSError] = []
    for descriptor in reversed(anchor.descriptors):
        try:
            os.close(descriptor)
        except OSError as exc:
            errors.append(exc)
    anchor.descriptors.clear()
    anchor.closed = True
    if errors and not suppress_errors:
        raise errors[0]


def _owned_path(path: Path, *, repo_root: Path | None = None) -> OwnedPath:
    root = Path(os.path.abspath(repo_root if repo_root is not None else path.parent))
    relative = _relative_path(path, repo_root=root)
    anchor = _open_directory_anchor(
        relative.parent,
        repo_root=root,
        label=f"owned path {relative.as_posix()}",
    )
    try:
        metadata = os.stat(
            relative.name,
            dir_fd=anchor.parent_fd,
            follow_symlinks=False,
        )
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise _error(f"published output is not a regular file: {relative}")
        return OwnedPath(
            path=relative,
            device=metadata.st_dev,
            inode=metadata.st_ino,
            anchor=anchor,
        )
    except BaseException:
        _close_directory_anchor(anchor)
        raise


def _unlink_owned_at(
    parent_fd: int,
    leaf: str,
    identity: tuple[int, int] | None,
    *,
    label: str,
) -> bool:
    """Atomically capture a canonical name before removing the owned inode.

    A fresh mode-0700 random directory gives ``rename`` an atomically
    exclusive destination namespace.  A replacement captured at the rename
    boundary is restored with a no-clobber hardlink and never passed to
    ``unlink``.  Linux has no compare-and-unlink primitive; deliberate
    same-UID interference inside the unpredictable private namespace after
    capture is outside the sealed single-writer publication contract.
    """

    if identity is None:
        return False
    try:
        before = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if (before.st_dev, before.st_ino) != identity:
        raise _error(f"refusing to remove a replaced path: {label}")

    tombstone_leaf: str | None = None
    tombstone_fd: int | None = None
    tombstone_identity: tuple[int, ...] | None = None
    for _attempt in range(16):
        candidate = f".closure-owned-capture-{secrets.token_hex(16)}"
        try:
            os.mkdir(candidate, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        tombstone_leaf = candidate
        try:
            tombstone_fd = os.open(
                candidate,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_fd,
            )
            opened_directory = os.fstat(tombstone_fd)
            named_directory = os.stat(
                candidate,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
            tombstone_identity = _directory_identity(opened_directory)
            if (
                not stat.S_ISDIR(opened_directory.st_mode)
                or stat.S_IMODE(opened_directory.st_mode) != 0o700
                or _directory_identity(named_directory) != tombstone_identity
            ):
                raise _error(f"cleanup namespace was replaced: {label}")
        except BaseException:
            if tombstone_fd is not None:
                os.close(tombstone_fd)
                tombstone_fd = None
            try:
                current_directory = os.stat(
                    candidate,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if (
                    tombstone_identity is not None
                    and _directory_identity(current_directory)
                    == tombstone_identity
                ):
                    os.rmdir(candidate, dir_fd=parent_fd)
            except OSError:
                pass
            raise
        break
    if tombstone_leaf is None or tombstone_fd is None:
        raise _error(f"cleanup namespace is unavailable: {label}")

    captured_leaf = "captured"
    captured_present = False
    try:
        try:
            os.rename(
                leaf,
                captured_leaf,
                src_dir_fd=parent_fd,
                dst_dir_fd=tombstone_fd,
            )
        except FileNotFoundError as exc:
            raise _error(f"owned path disappeared at cleanup boundary: {label}") from exc
        captured_present = True
        os.fsync(parent_fd)
        os.fsync(tombstone_fd)
        captured = os.stat(
            captured_leaf,
            dir_fd=tombstone_fd,
            follow_symlinks=False,
        )
        captured_identity = (captured.st_dev, captured.st_ino)
        if captured_identity != identity:
            try:
                _rename_noreplace_at(
                    tombstone_fd,
                    captured_leaf,
                    parent_fd,
                    leaf,
                )
            except OSError as exc:
                raise _error(
                    f"foreign replacement could not be restored: {label}"
                ) from exc
            restored = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
            if (restored.st_dev, restored.st_ino) != captured_identity:
                raise _error(f"foreign replacement restoration drifted: {label}")
            os.fsync(parent_fd)
            captured_present = False
            os.fsync(tombstone_fd)
            raise _error(f"refusing to remove a replaced path: {label}")
        os.unlink(captured_leaf, dir_fd=tombstone_fd)
        captured_present = False
        os.fsync(tombstone_fd)
    finally:
        os.close(tombstone_fd)
        if not captured_present:
            try:
                named_directory = os.stat(
                    tombstone_leaf,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if (
                    tombstone_identity is not None
                    and _directory_identity(named_directory)
                    == tombstone_identity
                ):
                    os.rmdir(tombstone_leaf, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
    os.fsync(parent_fd)
    return True


def _rename_noreplace_at(
    source_directory_fd: int,
    source_name: str,
    target_directory_fd: int,
    target_name: str,
) -> None:
    """Use Linux renameat2 to restore any entry type without clobbering."""

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = libc.renameat2
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        source_directory_fd,
        os.fsencode(source_name),
        target_directory_fd,
        os.fsencode(target_name),
        1,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _unlink_if_owned(
    owned: OwnedPath,
    *,
    require_present: bool = False,
) -> None:
    try:
        removed = _unlink_owned_at(
            owned.anchor.parent_fd,
            owned.path.name,
            (owned.device, owned.inode),
            label=owned.path.as_posix(),
        )
        if require_present and not removed:
            raise _error(f"owned path disappeared before cleanup: {owned.path}")
        _recapture_directory_anchor(
            owned.anchor,
            label=f"owned cleanup {owned.path.as_posix()}",
        )
    finally:
        _close_directory_anchor(owned.anchor)


def _hash_owned(owned: OwnedPath) -> tuple[int, str]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor: int | None = None
    try:
        named_before = os.stat(
            owned.path.name,
            dir_fd=owned.anchor.parent_fd,
            follow_symlinks=False,
        )
        descriptor = os.open(
            owned.path.name,
            flags,
            dir_fd=owned.anchor.parent_fd,
        )
        before = os.fstat(descriptor)
        expected = (owned.device, owned.inode)
        if (
            not stat.S_ISREG(named_before.st_mode)
            or not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o644
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino) != expected
            or (named_before.st_dev, named_before.st_ino) != expected
            or _metadata_identity(named_before) != _metadata_identity(before)
        ):
            raise _error(f"owned output identity drifted: {owned.path}")
        size, sha256 = _hash_descriptor(descriptor)
        after = os.fstat(descriptor)
        named_after = os.stat(
            owned.path.name,
            dir_fd=owned.anchor.parent_fd,
            follow_symlinks=False,
        )
        if (
            _metadata_identity(before) != _metadata_identity(after)
            or _metadata_identity(before) != _metadata_identity(named_after)
            or size != after.st_size
        ):
            raise _error(f"owned output changed while hashing: {owned.path}")
        _recapture_directory_anchor(
            owned.anchor,
            label=f"owned hash {owned.path.as_posix()}",
        )
        return size, sha256
    except OSError as exc:
        raise _error(f"owned output cannot be hashed: {owned.path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


class OutputTransaction:
    """Publish byte payloads by exclusive hardlink and rollback owned inodes."""

    def __init__(
        self,
        *,
        repo_root: Path,
        namespace_guard: OwnedPath | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.namespace_guard = namespace_guard
        self.owned: list[OwnedPath] = []
        self.expected: list[tuple[OwnedPath, int, str]] = []
        self.temporary: list[OwnedPath] = []
        self.committed = False
        self.guard_finalized = False

    def __enter__(self) -> OutputTransaction:
        return self

    def _require_guard_leaf(self, *, recapture_namespace: bool = True) -> None:
        if self.namespace_guard is None:
            return
        guard = self.namespace_guard
        try:
            metadata = os.stat(
                guard.path.name,
                dir_fd=guard.anchor.parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError as exc:
            raise _error("exclusive generation guard disappeared") from exc
        expected = (guard.device, guard.inode)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
            or (metadata.st_dev, metadata.st_ino) != expected
        ):
            raise _error("exclusive generation guard was replaced")
        if recapture_namespace:
            _recapture_directory_anchor(
                guard.anchor,
                label="exclusive generation guard",
            )

    def _require_same_repository_root(
        self,
        anchor: DirectoryAnchor,
        *,
        label: str,
    ) -> None:
        if self.namespace_guard is None:
            return
        self._require_guard_leaf()
        if anchor.root_identity != self.namespace_guard.anchor.root_identity:
            raise _error(f"{label} does not share the guarded repository root")

    def _release_guard(self) -> None:
        if self.namespace_guard is None:
            self.guard_finalized = True
            return
        guard = self.namespace_guard
        self._require_guard_leaf(recapture_namespace=False)
        removed = _unlink_owned_at(
            guard.anchor.parent_fd,
            guard.path.name,
            (guard.device, guard.inode),
            label=guard.path.as_posix(),
        )
        if not removed:
            raise _error("exclusive generation guard disappeared before release")
        self.guard_finalized = True
        try:
            os.stat(
                guard.path.name,
                dir_fd=guard.anchor.parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise _error("exclusive generation guard was replaced during release")
        _recapture_directory_anchor(
            guard.anchor,
            label="exclusive generation guard release",
        )

    def publish(self, relative: Path, payload: bytes) -> OwnedPath:
        canonical = _relative_path(relative, repo_root=self.repo_root)
        anchor = _open_directory_anchor(
            canonical.parent,
            repo_root=self.repo_root,
            label=f"output publication {canonical.as_posix()}",
        )
        try:
            self._require_same_repository_root(
                anchor,
                label=f"output publication {canonical.as_posix()}",
            )
        except BaseException:
            _close_directory_anchor(anchor)
            raise
        token = secrets.token_hex(12)
        temporary_leaf = f".{canonical.name}.{token}.tmp"
        descriptor: int | None = None
        temp_identity: tuple[int, int] | None = None
        final_identity: tuple[int, int] | None = None
        final_owned: OwnedPath | None = None
        try:
            try:
                os.stat(
                    canonical.name,
                    dir_fd=anchor.parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise _error(f"no-clobber output already exists: {relative}")
            descriptor = os.open(
                temporary_leaf,
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=anchor.parent_fd,
            )
            opened = os.fstat(descriptor)
            temp_identity = (opened.st_dev, opened.st_ino)
            if (
                not stat.S_ISREG(opened.st_mode)
                or stat.S_IMODE(opened.st_mode) != 0o600
                or opened.st_nlink != 1
                or opened.st_size != 0
            ):
                raise _error(f"temporary output identity drifted: {relative}")
            view = memoryview(payload)
            offset = 0
            while offset < len(view):
                written = os.write(descriptor, view[offset:])
                if written <= 0:
                    raise _error(f"short write for temporary output: {relative}")
                offset += written
            os.fchmod(descriptor, 0o644)
            os.fsync(descriptor)
            written_metadata = os.fstat(descriptor)
            temp_named = os.stat(
                temporary_leaf,
                dir_fd=anchor.parent_fd,
                follow_symlinks=False,
            )
            if (
                _metadata_identity(written_metadata)
                != _metadata_identity(temp_named)
                or (written_metadata.st_dev, written_metadata.st_ino)
                != temp_identity
                or stat.S_IMODE(written_metadata.st_mode) != 0o644
                or written_metadata.st_nlink != 1
                or written_metadata.st_size != len(payload)
            ):
                raise _error(f"temporary output identity drifted: {relative}")
            _recapture_directory_anchor(
                anchor,
                label=f"output publication {canonical.as_posix()}",
            )
            self._require_same_repository_root(
                anchor,
                label=f"output publication {canonical.as_posix()}",
            )
            try:
                os.link(
                    temporary_leaf,
                    canonical.name,
                    src_dir_fd=anchor.parent_fd,
                    dst_dir_fd=anchor.parent_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                raise _error(
                    f"no-clobber output appeared concurrently: {relative}"
                ) from exc
            final_identity = temp_identity
            linked = os.stat(
                canonical.name,
                dir_fd=anchor.parent_fd,
                follow_symlinks=False,
            )
            linked_opened = os.fstat(descriptor)
            if (
                _metadata_identity(linked) != _metadata_identity(linked_opened)
                or (linked.st_dev, linked.st_ino) != final_identity
                or linked.st_nlink != 2
            ):
                raise _error(f"published hardlink identity drifted: {relative}")
            _unlink_owned_at(
                anchor.parent_fd,
                temporary_leaf,
                temp_identity,
                label=f"temporary {canonical.as_posix()}",
            )
            temp_identity = None
            os.fsync(anchor.parent_fd)
            final_named = os.stat(
                canonical.name,
                dir_fd=anchor.parent_fd,
                follow_symlinks=False,
            )
            final_opened = os.fstat(descriptor)
            if (
                _metadata_identity(final_named) != _metadata_identity(final_opened)
                or (final_opened.st_dev, final_opened.st_ino) != final_identity
                or final_opened.st_nlink != 1
                or final_opened.st_size != len(payload)
            ):
                raise _error(f"published output identity drifted: {relative}")
            observed_size, observed_sha256 = _hash_descriptor(descriptor)
            expected_sha256 = _sha256_bytes(payload)
            if (
                observed_size != len(payload)
                or observed_sha256 != expected_sha256
                or _metadata_identity(os.fstat(descriptor))
                != _metadata_identity(final_opened)
            ):
                raise _error(f"published output content drifted: {relative}")
            _recapture_directory_anchor(
                anchor,
                label=f"output publication {canonical.as_posix()}",
            )
            self._require_same_repository_root(
                anchor,
                label=f"output publication {canonical.as_posix()}",
            )
            final_owned = OwnedPath(
                path=canonical,
                device=final_identity[0],
                inode=final_identity[1],
                anchor=anchor,
            )
            self.owned.append(final_owned)
            self.expected.append((final_owned, len(payload), expected_sha256))
            os.close(descriptor)
            descriptor = None
            return final_owned
        except BaseException:
            if descriptor is not None:
                os.close(descriptor)
                descriptor = None
            cleanup_error: BaseException | None = None
            try:
                _unlink_owned_at(
                    anchor.parent_fd,
                    temporary_leaf,
                    temp_identity,
                    label=f"temporary {canonical.as_posix()}",
                )
                _unlink_owned_at(
                    anchor.parent_fd,
                    canonical.name,
                    final_identity,
                    label=canonical.as_posix(),
                )
                _recapture_directory_anchor(
                    anchor,
                    label=f"failed output publication {canonical.as_posix()}",
                )
            except BaseException as exc:
                cleanup_error = exc
            if final_owned is not None and final_owned in self.owned:
                self.owned.remove(final_owned)
                self.expected = [
                    record for record in self.expected if record[0] is not final_owned
                ]
            _close_directory_anchor(anchor)
            if cleanup_error is not None:
                raise _error(
                    f"failed output cleanup was incomplete: {canonical.as_posix()}"
                ) from cleanup_error
            raise
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def commit(self) -> None:
        for owned, expected_size, expected_sha256 in self.expected:
            self._require_same_repository_root(
                owned.anchor,
                label=f"bundle output {owned.path.as_posix()}",
            )
            observed_size, observed_sha256 = _hash_owned(owned)
            if (
                observed_size != expected_size
                or observed_sha256 != expected_sha256
            ):
                raise _error(f"bundle output changed before commit: {owned.path}")
        self.committed = True

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        recapture_error: BaseException | None = None
        if exc_type is None and self.committed:
            try:
                for owned in self.owned:
                    self._require_same_repository_root(
                        owned.anchor,
                        label=f"committed output {owned.path.as_posix()}",
                    )
                    _recapture_directory_anchor(
                        owned.anchor,
                        label=f"committed output {owned.path.as_posix()}",
                    )
                self._require_guard_leaf()
            except BaseException as anchor_exc:
                recapture_error = anchor_exc
        transaction_error = exc_type is not None or not self.committed
        if not transaction_error and recapture_error is None:
            try:
                self._release_guard()
                for owned in self.owned:
                    _recapture_directory_anchor(
                        owned.anchor,
                        label=f"released bundle output {owned.path.as_posix()}",
                    )
                    if (
                        self.namespace_guard is not None
                        and owned.anchor.root_identity
                        != self.namespace_guard.anchor.root_identity
                    ):
                        raise _error(
                            "released bundle output does not share the guarded "
                            "repository root"
                        )
            except BaseException as release_exc:
                recapture_error = release_exc

        rollback_errors: list[Exception] = []
        guard_error: BaseException | None = None
        try:
            if transaction_error or recapture_error is not None:
                for owned in reversed(self.owned):
                    try:
                        _unlink_if_owned(owned)
                    except Exception as rollback_exc:  # pragma: no cover - hostile race
                        rollback_errors.append(rollback_exc)
                for owned in reversed(self.temporary):
                    try:
                        _unlink_if_owned(owned)
                    except Exception as rollback_exc:  # pragma: no cover - hostile race
                        rollback_errors.append(rollback_exc)
                if not self.guard_finalized:
                    try:
                        self._release_guard()
                    except BaseException as release_exc:
                        guard_error = release_exc
            else:
                for owned in reversed(self.owned):
                    _close_directory_anchor(
                        owned.anchor,
                        suppress_errors=True,
                    )
        finally:
            if self.namespace_guard is not None:
                _close_directory_anchor(
                    self.namespace_guard.anchor,
                    suppress_errors=(
                        not transaction_error
                        and recapture_error is None
                        and not rollback_errors
                        and guard_error is None
                    ),
                )

        if rollback_errors and exc_type is None and recapture_error is None:
            raise _error("output rollback was incomplete") from rollback_errors[0]
        if recapture_error is not None:
            raise _error("output namespace changed before transaction close") from (
                rollback_errors[0]
                if rollback_errors
                else guard_error or recapture_error
            )
        if guard_error is not None and exc_type is None:
            raise _error("exclusive generation guard cleanup was incomplete") from (
                rollback_errors[0] if rollback_errors else guard_error
            )
        return False


def _acquire_guard(path: Path, *, repo_root: Path) -> OwnedPath:
    canonical = _relative_path(path, repo_root=repo_root)
    anchor = _open_directory_anchor(
        canonical.parent,
        repo_root=repo_root,
        label="exclusive generation guard",
    )
    descriptor: int | None = None
    identity: tuple[int, int] | None = None
    try:
        descriptor = os.open(
            canonical.name,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=anchor.parent_fd,
        )
        metadata = os.fstat(descriptor)
        identity = (metadata.st_dev, metadata.st_ino)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
            or metadata.st_size != 0
        ):
            raise _error("exclusive generation guard identity drifted")
        payload = _canonical_json_bytes(
            {"surface_id": SURFACE_ID, "pid": os.getpid(), "exclusive": True}
        )
        view = memoryview(payload)
        offset = 0
        while offset < len(view):
            written = os.write(descriptor, view[offset:])
            if written <= 0:
                raise _error("short write for exclusive generation guard")
            offset += written
        os.fsync(descriptor)
        written = os.fstat(descriptor)
        named = os.stat(
            canonical.name,
            dir_fd=anchor.parent_fd,
            follow_symlinks=False,
        )
        if (
            _metadata_identity(written) != _metadata_identity(named)
            or (written.st_dev, written.st_ino) != identity
            or written.st_size != len(payload)
        ):
            raise _error("exclusive generation guard identity drifted")
        _recapture_directory_anchor(anchor, label="exclusive generation guard")
        owned = OwnedPath(
            path=canonical,
            device=identity[0],
            inode=identity[1],
            anchor=anchor,
        )
        os.close(descriptor)
        descriptor = None
        return owned
    except FileExistsError as exc:
        _close_directory_anchor(anchor)
        raise _error("exclusive generation guard already exists") from exc
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        cleanup_error: BaseException | None = None
        try:
            _unlink_owned_at(
                anchor.parent_fd,
                canonical.name,
                identity,
                label=canonical.as_posix(),
            )
            _recapture_directory_anchor(anchor, label="exclusive generation guard")
        except BaseException as exc:
            cleanup_error = exc
        _close_directory_anchor(anchor)
        if cleanup_error is not None:
            raise _error("exclusive generation guard cleanup was incomplete") from cleanup_error
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _assert_source_records_unchanged(
    records: Sequence[Mapping[str, Any]], *, repo_root: Path
) -> None:
    for record in records:
        refreshed = _source_record(
            Path(str(record["path"])),
            role=str(record["role"]),
            repo_root=repo_root,
        )
        if refreshed != dict(record):
            raise _error(f"source input changed during generation: {record['path']}")


def _builder_source_record() -> dict[str, Any]:
    payload = Path(__file__).read_bytes()
    return {
        "role": "phase3_input_overlay_builder",
        "path": "src/experiments/build_closure_phase3_input_overlay.py",
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _read_anchored_bytes(path: Path, *, repo_root: Path) -> bytes:
    with _anchored_regular(path, repo_root=repo_root) as (descriptor, metadata):
        size, _sha256 = _hash_descriptor(descriptor)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        if size != metadata.st_size or len(payload) != metadata.st_size:
            raise _error(f"anchored payload size drifted: {path}")
        return payload


def _git_blob_bytes(repo_root: Path, commit: str, path: Path) -> bytes:
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise _error("expected H commit is not a lowercase SHA-1")
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{path.as_posix()}"],
            cwd=repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise _error(f"cannot reconstruct H blob: {path}") from exc
    return bytes(result.stdout)


def validate_materialized_phase3_input_overlay(
    *,
    repo_root: Path = PROJECT_ROOT,
    expected_h_commit: str,
) -> dict[str, Any]:
    """Regenerate P in memory and prove byte equality without outcomes or writes."""

    root = Path(os.path.abspath(repo_root))
    _validate_checkpoint_specs(CHECKPOINT_SPECS)
    _validate_projection_contract()
    builder_path = Path("src/experiments/build_closure_phase3_input_overlay.py")
    builder_payload = _read_anchored_bytes(builder_path, repo_root=root)
    builder_blob = _git_blob_bytes(root, expected_h_commit, builder_path)
    if builder_payload != builder_blob:
        raise _error("physical overlay builder differs from exact H")
    builder_source = {
        "role": "phase3_input_overlay_builder",
        "path": builder_path.as_posix(),
        "bytes": len(builder_payload),
        "sha256": _sha256_bytes(builder_payload),
    }

    npz_payload, numpy_export, checkpoint_sources = _build_npz(
        CHECKPOINT_SPECS,
        repo_root=root,
        enforce_production_contract=True,
    )
    warmup_records, warmup_summary, parquet_sources = _build_warmup_records(
        repo_root=root,
        paths=OverlayPaths(),
        expected_site_count=EXPECTED_HOLDOUT_SITES,
    )
    warmup_payload = _warmup_parquet_bytes(warmup_records)
    sources = [*parquet_sources, *checkpoint_sources]
    sources.sort(key=lambda record: (str(record["role"]), str(record["path"])))
    _assert_source_records_unchanged(sources, repo_root=root)
    if _read_anchored_bytes(builder_path, repo_root=root) != builder_payload:
        raise _error("overlay builder changed during deep validation")

    physical_outputs = [
        _npz_output_record(NPZ_OUTPUT_PATH, npz_payload, numpy_export),
        _parquet_output_record(WARMUP_OUTPUT_PATH, warmup_payload, warmup_records),
    ]
    expected_manifest = {
        "manifest_version": MANIFEST_VERSION,
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "gate": "pre_E0-U",
        "status": "completed",
        "publication_status": "materialized_unpublished",
        "repository_head": expected_h_commit,
        "input_only": True,
        "script": builder_source,
        "inputs": sources,
        "outputs": physical_outputs,
        "source_inputs": [builder_source, *sources],
        "physical_outputs": physical_outputs,
        "numpy_export": numpy_export,
        "warmup": warmup_summary,
        "outcome_isolation": {
            "opened_outcome_path_count": 0,
            "opened_target_path_count": 0,
            "outcome_paths": [],
            "target_paths": [],
            "panel_projection_contains_chlorophyll": False,
            "panel_projection_contains_target": False,
            "scientific_outcomes_accessed": False,
            "e0_u_authorized": False,
            "evaluation_authorized": False,
        },
        "publication": {
            "exclusive_guard": GUARD_PATH.as_posix(),
            "no_clobber": True,
            "temporary_files_exclusive": True,
            "publication_primitive": "temporary_regular_file_then_hardlink",
            "rollback_policy": "current_process_device_inode_only",
            "manifest_written_last": True,
            "publication_order": [
                NPZ_OUTPUT_PATH.as_posix(),
                WARMUP_OUTPUT_PATH.as_posix(),
                MANIFEST_OUTPUT_PATH.as_posix(),
            ],
        },
    }
    expected_manifest_payload = _canonical_json_bytes(expected_manifest)
    actual_npz = _read_anchored_bytes(NPZ_OUTPUT_PATH, repo_root=root)
    actual_warmup = _read_anchored_bytes(WARMUP_OUTPUT_PATH, repo_root=root)
    actual_manifest = _read_anchored_bytes(MANIFEST_OUTPUT_PATH, repo_root=root)
    if actual_npz != npz_payload:
        raise _error("materialized NPZ differs from regenerated checkpoint state")
    if actual_warmup != warmup_payload:
        raise _error("materialized warm-up differs from regenerated projection")
    if actual_manifest != expected_manifest_payload:
        raise _error("materialized overlay manifest differs from regeneration")

    source_digest = _sha256_bytes(_canonical_json_bytes(sources))
    return {
        "schema_version": DEEP_VALIDATION_VERSION,
        "status": "passed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "gate": "pre_E0-U",
        "expected_h_commit": expected_h_commit,
        "builder_source": builder_source,
        "source_inputs": sources,
        "source_input_count": len(sources),
        "source_inputs_sha256": source_digest,
        "manifest": {
            "path": MANIFEST_OUTPUT_PATH.as_posix(),
            "bytes": len(actual_manifest),
            "sha256": _sha256_bytes(actual_manifest),
        },
        "physical_outputs": [
            {
                "path": NPZ_OUTPUT_PATH.as_posix(),
                "bytes": len(actual_npz),
                "sha256": _sha256_bytes(actual_npz),
            },
            {
                "path": WARMUP_OUTPUT_PATH.as_posix(),
                "bytes": len(actual_warmup),
                "sha256": _sha256_bytes(actual_warmup),
            },
        ],
        "checkpoint_count": int(numpy_export["checkpoint_count"]),
        "state_dict_array_count": int(numpy_export["state_dict_array_count"]),
        "warmup_row_count": len(warmup_records),
        "warmup_site_count": len(
            {(record["source_id"], record["site_id"]) for record in warmup_records}
        ),
        "npz_regenerated_byte_equality": True,
        "warmup_regenerated_byte_equality": True,
        "manifest_regenerated_byte_equality": True,
        "checkpoint_identity_revalidated": True,
        "numpy_torch_parity_recomputed": True,
        "warmup_projection_recomputed": True,
        "history_projection": list(HISTORY_PROJECTION),
        "panel_projection": list(PANEL_PROJECTION),
        "projection_contains_chlorophyll": False,
        "projection_contains_target": False,
        "opened_outcome_path_count": 0,
        "opened_target_path_count": 0,
        "writes_performed": False,
    }


def generate_phase3_input_overlay(
    *,
    repo_root: Path = PROJECT_ROOT,
    paths: OverlayPaths = OverlayPaths(),
    checkpoint_specs: Sequence[CheckpointSpec] = CHECKPOINT_SPECS,
    expected_site_count: int = EXPECTED_HOLDOUT_SITES,
    enforce_production_contract: bool = True,
) -> dict[str, Any]:
    """Generate the three-file input-only overlay with manifest-last publication."""

    root = Path(os.path.abspath(repo_root))
    if type(expected_site_count) is not int or expected_site_count <= 0:
        raise _error("expected_site_count must be a positive exact integer")
    _validate_checkpoint_specs(checkpoint_specs)
    _validate_projection_contract()
    _output_namespace_absent(paths, repo_root=root)
    history_columns, _history_rows = _parquet_schema(paths.history, repo_root=root)
    panel_columns, _panel_rows = _parquet_schema(paths.panel, repo_root=root)
    if not set(HISTORY_PROJECTION).issubset(history_columns) or not set(
        PANEL_PROJECTION
    ).issubset(panel_columns):
        raise _error("projected input columns are absent")

    builder_source = _builder_source_record()
    guard = _acquire_guard(paths.guard, repo_root=root)
    guard_transferred = False
    try:
        npz_payload, numpy_export, checkpoint_sources = _build_npz(
            checkpoint_specs,
            repo_root=root,
            enforce_production_contract=enforce_production_contract,
        )
        warmup_records, warmup_summary, parquet_sources = _build_warmup_records(
            repo_root=root,
            paths=paths,
            expected_site_count=expected_site_count,
        )
        warmup_payload = _warmup_parquet_bytes(warmup_records)
        sources = [*parquet_sources, *checkpoint_sources]
        sources.sort(key=lambda record: (str(record["role"]), str(record["path"])))
        _assert_source_records_unchanged(sources, repo_root=root)
        if _builder_source_record() != builder_source:
            raise _error("builder source changed during generation")
        source_inputs = [builder_source, *sources]

        physical_outputs = [
            _npz_output_record(paths.npz_output, npz_payload, numpy_export),
            _parquet_output_record(
                paths.warmup_output, warmup_payload, warmup_records
            ),
        ]
        manifest: dict[str, Any] = {
            "manifest_version": MANIFEST_VERSION,
            "experiment_id": "closure_v1",
            "surface_id": SURFACE_ID,
            "gate": "pre_E0-U",
            "status": "completed",
            "publication_status": "materialized_unpublished",
            "repository_head": _git_head(root),
            "input_only": True,
            "script": builder_source,
            "inputs": sources,
            "outputs": physical_outputs,
            "source_inputs": source_inputs,
            "physical_outputs": physical_outputs,
            "numpy_export": numpy_export,
            "warmup": warmup_summary,
            "outcome_isolation": {
                "opened_outcome_path_count": 0,
                "opened_target_path_count": 0,
                "outcome_paths": [],
                "target_paths": [],
                "panel_projection_contains_chlorophyll": False,
                "panel_projection_contains_target": False,
                "scientific_outcomes_accessed": False,
                "e0_u_authorized": False,
                "evaluation_authorized": False,
            },
            "publication": {
                "exclusive_guard": paths.guard.as_posix(),
                "no_clobber": True,
                "temporary_files_exclusive": True,
                "publication_primitive": "temporary_regular_file_then_hardlink",
                "rollback_policy": "current_process_device_inode_only",
                "manifest_written_last": True,
                "publication_order": [
                    paths.npz_output.as_posix(),
                    paths.warmup_output.as_posix(),
                    paths.manifest_output.as_posix(),
                ],
            },
        }
        manifest_payload = _canonical_json_bytes(manifest)
        with OutputTransaction(
            repo_root=root,
            namespace_guard=guard,
        ) as transaction:
            guard_transferred = True
            transaction.publish(paths.npz_output, npz_payload)
            transaction.publish(paths.warmup_output, warmup_payload)
            # Manifest-last is a contract, not merely descriptive metadata.
            transaction.publish(paths.manifest_output, manifest_payload)
            transaction.commit()
        return {
            "status": "materialized_unpublished",
            "manifest_path": paths.manifest_output.as_posix(),
            "manifest_bytes": len(manifest_payload),
            "manifest_sha256": _sha256_bytes(manifest_payload),
            "physical_output_count": len(physical_outputs),
            "checkpoint_count": numpy_export["checkpoint_count"],
            "site_count": warmup_summary["site_count"],
            "manifest_written_last": True,
            "opened_outcome_path_count": 0,
            "opened_target_path_count": 0,
            "writes_performed": True,
        }
    finally:
        if not guard_transferred:
            _unlink_if_owned(guard, require_present=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check-only",
        action="store_true",
        help="validate sources and namespace without writes or payload decoding",
    )
    mode.add_argument(
        "--generate",
        action="store_true",
        help="exclusively publish the pre-E0-U overlay bundle",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    result = (
        check_only()
        if arguments.check_only
        else generate_phase3_input_overlay()
    )
    print(_canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
