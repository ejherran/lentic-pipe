#!/usr/bin/env python
"""Materialize the development-only E0-MCAL final-calibration bundle.

Every public mode first calls ``require_final_calibration_authority``; only
after that gate may a scientific reader or ``publish_ordered_bundle`` run.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import io
import json
import math
import os
import re
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import yaml
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import closure_final_calibration as calibration  # noqa: E402
from src.experiments import train_closure_anfis_ablation as anfis_training  # noqa: E402
from src.experiments.closure_runtime_contract import (  # noqa: E402
    configure_torch_cpu_execution_policy,
    validate_development_runtime,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = PROJECT_ROOT / "reports/closure_v1/03_calibration"
CALIBRATOR_SPECS_PATH = OUTPUT_ROOT / "calibrator_specs.json"
CALIBRATION_METRICS_PATH = OUTPUT_ROOT / "calibration_metrics.csv"
ALERT_THRESHOLDS_PATH = OUTPUT_ROOT / "alert_thresholds.csv"
ORDINAL_CUTPOINTS_PATH = OUTPUT_ROOT / "ordinal_cutpoints.csv"
MODEL_AVAILABILITY_PATH = OUTPUT_ROOT / "model_availability.csv"
MANIFEST_PATH = OUTPUT_ROOT / "final_calibration_manifest.json"
OUTPUT_PATHS = (
    CALIBRATOR_SPECS_PATH,
    CALIBRATION_METRICS_PATH,
    ALERT_THRESHOLDS_PATH,
    ORDINAL_CUTPOINTS_PATH,
    MODEL_AVAILABILITY_PATH,
    MANIFEST_PATH,
)
GUARD_PATH = PROJECT_ROOT / "tmp/closure_v1_e0_mcal/final_calibration.guard"
GUARD_PAYLOAD = b"E0-MCAL active light-output transaction\n"
TARGET_PATH = PROJECT_ROOT / "data/targets/monthly_targets_model_v0.parquet"
COMMON_ORIGIN_PATH = PROJECT_ROOT / "data/closure_v1/common_origin_manifest.parquet"
HORIZONS = (1, 2, 3)
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
METHODS = ("identity", "platt_logistic", "isotonic_regression")
TROPHIC_LABELS = ("oligotrophic", "mesotrophic", "eutrophic", "hypereutrophic")
CALIBRATABLE_MODELS = ("B0", "B1", "B2", "M0", "A0", "A1")
ORDINAL_MODELS = ("B0", "B1", "B2")
UNCERTAINTY_MODELS = ("A0", "A1")
MODEL_SEEDS: dict[str, tuple[int, ...]] = {
    "B0": (1729,),
    "B1": REGISTERED_SEEDS,
    "B2": REGISTERED_SEEDS,
    "F0": (1729,),
    "F1": REGISTERED_SEEDS,
    "P0": REGISTERED_SEEDS,
    "P1": REGISTERED_SEEDS,
    "M0": (1729,),
    "A0": REGISTERED_SEEDS,
    "A1": REGISTERED_SEEDS,
    "A2": (),
}
PREDICTION_COLUMNS = (
    "model_id",
    "model_seed",
    "horizon_months",
    "source_id",
    "site_id",
    "common_origin_id",
    "origin_year_month",
    "assignment_role",
    "time_role",
    "target_year_month",
    "bloom_probability",
    "bloom_label",
    "ordinal_score",
    "ordinal_label",
    "observed_risk",
    "predicted_risk",
    "predicted_risk_sigma",
)
TARGET_JOIN_COLUMNS = (
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
)


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    nlink: int
    size: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class OwnedOutput:
    path: Path
    identity: FileIdentity
    sha256: str
    created_directories: tuple["OwnedDirectory", ...] = ()


@dataclass(frozen=True)
class OwnedDirectory:
    path: Path
    device: int
    inode: int


def _error(message: str) -> calibration.FinalCalibrationError:
    return calibration.FinalCalibrationError(message)


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _load_unique_json_mapping(payload: bytes, *, path: Path) -> Mapping[str, Any]:
    """Decode historical JSON without accepting last-key-wins ambiguity."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, nested in pairs:
            if key in value:
                raise _error(
                    f"E0-MCAL JSON input contains a duplicate key: {path}:{key}"
                )
            value[key] = nested
        return value

    try:
        value = json.loads(payload, object_pairs_hook=reject_duplicates)
    except calibration.FinalCalibrationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _error(f"E0-MCAL JSON input is malformed: {path}") from exc
    if not isinstance(value, Mapping):
        raise _error(f"E0-MCAL JSON input is not one mapping: {path}")
    return value


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode(
        "utf-8"
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _identity(value: os.stat_result) -> FileIdentity:
    return FileIdentity(
        device=int(value.st_dev),
        inode=int(value.st_ino),
        mode=stat.S_IMODE(value.st_mode),
        nlink=int(value.st_nlink),
        size=int(value.st_size),
        mtime_ns=int(value.st_mtime_ns),
        ctime_ns=int(value.st_ctime_ns),
    )


def _write_all(descriptor: int, payload: bytes, *, context: str) -> None:
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        written = os.write(descriptor, view[offset:])
        if written <= 0:
            raise _error(f"{context} produced a short write")
        offset += written


def _relative_parts(path: Path, *, repo_root: Path) -> tuple[str, ...]:
    try:
        root = Path(os.path.abspath(repo_root))
        candidate = Path(os.path.abspath(path if path.is_absolute() else root / path))
        relative = candidate.relative_to(root)
    except (OSError, ValueError) as exc:
        raise _error(f"Output path escapes the repository: {path}") from exc
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise _error(f"Output path is not canonical: {path}")
    return relative.parts


def _open_parent(
    path: Path, *, repo_root: Path, create: bool
) -> tuple[int, str, list[OwnedDirectory]]:
    parts = _relative_parts(path, repo_root=repo_root)
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    descriptor = os.open(repo_root, flags)
    created: list[OwnedDirectory] = []
    current = Path(os.path.abspath(repo_root))
    try:
        for component in parts[:-1]:
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(component, mode=0o755, dir_fd=descriptor)
                child = os.open(component, flags, dir_fd=descriptor)
                observed = os.fstat(child)
                created.append(
                    OwnedDirectory(
                        path=current / component,
                        device=int(observed.st_dev),
                        inode=int(observed.st_ino),
                    )
                )
                os.fsync(descriptor)
            observed = os.fstat(child)
            if not stat.S_ISDIR(observed.st_mode) or observed.st_nlink < 2:
                os.close(child)
                raise _error(f"Repository parent is not a real directory: {component}")
            os.close(descriptor)
            descriptor = child
            current = current / component
        return descriptor, parts[-1], created
    except BaseException as exc:
        os.close(descriptor)
        # ``_open_parent`` may have created several ancestors before a later
        # component proved missing, non-directory, or symlinked.  Ownership is
        # already bound to the just-opened inode, so unwind that partial
        # namespace here rather than losing the records before the caller can
        # start its transaction.
        try:
            _remove_owned_empty_directories(created, repo_root=repo_root)
        except BaseException as cleanup_exc:
            exc.add_note(
                "E0-MCAL partial parent cleanup failed: "
                f"{type(cleanup_exc).__name__}: {cleanup_exc}"
            )
        raise


def _read_named_bytes(path: Path, *, repo_root: Path) -> tuple[bytes, FileIdentity]:
    parent, name, _ = _open_parent(path, repo_root=repo_root, create=False)
    descriptor: int | None = None
    try:
        named_before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(name, flags, dir_fd=parent)
        opened_before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(named_before.st_mode)
            or not stat.S_ISREG(opened_before.st_mode)
            or (named_before.st_dev, named_before.st_ino)
            != (opened_before.st_dev, opened_before.st_ino)
            or opened_before.st_nlink != 1
        ):
            raise _error(f"Input is not one regular, singly linked file: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        opened_after = os.fstat(descriptor)
        named_after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        before_identity = _identity(opened_before)
        if (
            _identity(opened_after) != before_identity
            or _identity(named_after) != before_identity
            or len(payload) != before_identity.size
        ):
            raise _error(f"Input changed during anchored read: {path}")
        return payload, before_identity
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def _read_scientific_named_bytes(
    path: Path,
    *,
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> tuple[bytes, FileIdentity]:
    """Read exactly one P-authorized portable or DVC-cache payload.

    The core authority owns the physical-materialization policy.  Delegating
    here keeps every scientific reader on the same two closed classes:
    ``0644/nlink=1`` or an authorized ``0444/nlink=2`` DVC-cache hardlink
    whose second name, bytes and inode are revalidated.
    """

    try:
        relative = path.relative_to(repo_root)
    except ValueError as exc:
        raise _error(f"Scientific input is outside the repository: {path}") from exc
    try:
        payload, metadata = calibration._read_scientific_payload_bytes_and_metadata(
            relative,
            authorized_dvc_pointers=authorized_dvc_pointers,
            repo_root=repo_root,
        )
    except calibration.FinalCalibrationError as exc:
        raise _error(f"Scientific input physical authority failed: {path}: {exc}") from exc
    return payload, _identity(metadata)


def _authorized_scientific_dvc_pointers(
    authority: Mapping[str, Any],
) -> tuple[Path, ...]:
    """Derive the one closed DVC-pointer set from the effective P inventory."""

    inventory = authority.get("scientific_input_inventory")
    if not isinstance(inventory, Mapping):
        raise _error("E0-MCAL scientific input inventory is absent")
    authority_records = inventory.get("authority_records")
    payload_bindings = inventory.get("payload_bindings")
    if (
        not isinstance(authority_records, list)
        or not all(isinstance(record, Mapping) for record in authority_records)
        or not isinstance(payload_bindings, list)
        or not all(isinstance(record, Mapping) for record in payload_bindings)
    ):
        raise _error("E0-MCAL scientific input inventory records are malformed")
    try:
        return calibration._scientific_dvc_pointer_paths(
            cast(Sequence[Mapping[str, Any]], authority_records),
            cast(Sequence[Mapping[str, Any]], payload_bindings),
        )
    except calibration.FinalCalibrationError as exc:
        raise _error(f"E0-MCAL scientific DVC pointer authority failed: {exc}") from exc


def stable_file_record(path: Path, *, repo_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    payload, identity = _read_named_bytes(path, repo_root=repo_root)
    return {
        "path": path.relative_to(repo_root).as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "mode": format(identity.mode, "04o"),
        "nlink": identity.nlink,
        "device": identity.device,
        "inode": identity.inode,
        "mtime_ns": identity.mtime_ns,
        "ctime_ns": identity.ctime_ns,
    }


def _unlink_owned(path: Path, owned: OwnedOutput, *, repo_root: Path) -> None:
    parent, name, _ = _open_parent(path, repo_root=repo_root, create=False)
    try:
        try:
            observed = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        if (
            not stat.S_ISREG(observed.st_mode)
            or (observed.st_dev, observed.st_ino)
            != (owned.identity.device, owned.identity.inode)
            or observed.st_nlink != 1
        ):
            raise _error(f"Refusing to remove a foreign output during rollback: {path}")
        os.unlink(name, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(parent)


def _validate_owned(owned: OwnedOutput, *, repo_root: Path) -> None:
    """Bind the live name, bytes, and metadata to the inode we published."""
    payload, identity = _read_named_bytes(owned.path, repo_root=repo_root)
    if identity != owned.identity or _sha256_bytes(payload) != owned.sha256:
        raise _error(f"E0-MCAL owned output drifted before commit: {owned.path}")


def _remove_owned_empty_directories(
    directories: Sequence[OwnedDirectory], *, repo_root: Path
) -> None:
    unique = {
        directory.path: directory
        for directory in directories
    }
    errors: list[BaseException] = []
    for directory in sorted(
        unique.values(), key=lambda value: len(value.path.parts), reverse=True
    ):
        try:
            parent, name, _ = _open_parent(
                directory.path, repo_root=repo_root, create=False
            )
        except FileNotFoundError:
            continue
        except BaseException as exc:
            errors.append(exc)
            continue
        try:
            try:
                observed = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if (
                not stat.S_ISDIR(observed.st_mode)
                or (observed.st_dev, observed.st_ino)
                != (directory.device, directory.inode)
            ):
                raise _error(
                    f"Refusing to remove a foreign publication directory: {directory.path}"
                )
            try:
                os.rmdir(name, dir_fd=parent)
            except OSError as exc:
                if exc.errno == errno.ENOTEMPTY:
                    continue
                raise
            os.fsync(parent)
        except BaseException as exc:
            errors.append(exc)
        finally:
            try:
                os.close(parent)
            except BaseException as exc:
                errors.append(exc)
    if errors:
        detail = "E0-MCAL owned-directory cleanup was incomplete: " + "; ".join(
            f"{type(exc).__name__}: {exc}" for exc in errors
        )
        fatal = next((exc for exc in errors if not isinstance(exc, Exception)), None)
        if fatal is not None:
            fatal.add_note(detail)
            raise fatal
        raise _error(detail)


def _publish_one(
    path: Path,
    payload: bytes,
    *,
    repo_root: Path,
    final_mode: int | None = None,
) -> OwnedOutput:
    if final_mode is None:
        final_mode = 0o600 if payload == GUARD_PAYLOAD else 0o644
    if type(final_mode) is not int or final_mode not in {0o600, 0o644}:
        raise _error("E0-MCAL publication mode is not registered")
    parent, name, created_directories = _open_parent(
        path, repo_root=repo_root, create=True
    )
    token = hashlib.sha256(
        f"{os.getpid()}:{path.as_posix()}:{len(payload)}".encode("utf-8")
    ).hexdigest()[:20]
    temporary = f".{name}.e0_mcal_{token}.tmp"
    descriptor: int | None = None
    linked = False
    succeeded = False
    temp_created = False
    temp_identity: FileIdentity | None = None
    result: OwnedOutput | None = None
    try:
        if os.path.lexists(path):
            raise _error(f"E0-MCAL output already exists: {path}")
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(temporary, flags, 0o600, dir_fd=parent)
        temp_created = True
        temp_identity = _identity(os.fstat(descriptor))
        _write_all(descriptor, payload, context=f"temporary output {path}")
        os.fchmod(descriptor, final_mode)
        os.fsync(descriptor)
        completed = os.fstat(descriptor)
        if not stat.S_ISREG(completed.st_mode) or completed.st_nlink != 1:
            raise _error(f"Temporary output identity drifted: {path}")
        temp_identity = _identity(completed)
        os.link(
            temporary,
            name,
            src_dir_fd=parent,
            dst_dir_fd=parent,
            follow_symlinks=False,
        )
        linked = True
        os.fsync(parent)
        final_linked = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (
            (final_linked.st_dev, final_linked.st_ino)
            != (completed.st_dev, completed.st_ino)
            or final_linked.st_nlink != 2
        ):
            raise _error(f"Hardlink publication identity drifted: {path}")
        os.unlink(temporary, dir_fd=parent)
        temp_created = False
        os.fsync(parent)
        final = os.stat(name, dir_fd=parent, follow_symlinks=False)
        final_identity = _identity(final)
        if (
            not stat.S_ISREG(final.st_mode)
            or final_identity.mode != final_mode
            or final_identity.nlink != 1
            or final_identity.size != len(payload)
        ):
            raise _error(f"Published output metadata drifted: {path}")
        result = OwnedOutput(
            path=path,
            identity=final_identity,
            sha256=_sha256_bytes(payload),
            created_directories=tuple(created_directories),
        )
        succeeded = True
        return result
    except BaseException as exc:
        cleanup_errors: list[BaseException | str] = []
        if linked:
            try:
                observed = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if temp_identity is not None and (
                    observed.st_dev,
                    observed.st_ino,
                ) == (temp_identity.device, temp_identity.inode):
                    os.unlink(name, dir_fd=parent)
                else:
                    cleanup_errors.append(f"foreign final {path}")
            except FileNotFoundError:
                pass
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if temp_created:
            try:
                observed = os.stat(temporary, dir_fd=parent, follow_symlinks=False)
                if temp_identity is not None and (
                    observed.st_dev,
                    observed.st_ino,
                ) == (temp_identity.device, temp_identity.inode):
                    os.unlink(temporary, dir_fd=parent)
                else:
                    cleanup_errors.append(f"foreign temporary {path}")
            except FileNotFoundError:
                pass
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        try:
            os.fsync(parent)
        except BaseException as cleanup_exc:
            cleanup_errors.append(cleanup_exc)
        if cleanup_errors:
            exc.add_note(
                "E0-MCAL local publication cleanup was incomplete: "
                + "; ".join(str(value) for value in cleanup_errors)
            )
        raise
    finally:
        close_errors: list[BaseException] = []
        if descriptor is not None:
            try:
                os.close(descriptor)
            except BaseException as exc:
                close_errors.append(exc)
        try:
            os.close(parent)
        except BaseException as exc:
            close_errors.append(exc)
        if not succeeded:
            try:
                _remove_owned_empty_directories(
                    created_directories, repo_root=repo_root
                )
            except BaseException as exc:
                close_errors.append(exc)
        if close_errors:
            active = sys.exception()
            if active is None and succeeded and result is not None:
                # A close failure occurs after the caller-visible name exists
                # but before ownership can be returned to the transaction.
                # Reclaim it here, then unwind its created parents.
                try:
                    _unlink_owned(result.path, result, repo_root=repo_root)
                except BaseException as exc:
                    close_errors.append(exc)
                try:
                    _remove_owned_empty_directories(
                        created_directories, repo_root=repo_root
                    )
                except BaseException as exc:
                    close_errors.append(exc)
            detail = "E0-MCAL descriptor/directory cleanup failed: " + "; ".join(
                f"{type(exc).__name__}: {exc}" for exc in close_errors
            )
            if active is not None:
                active.add_note(detail)
            else:
                fatal = next(
                    (exc for exc in close_errors if not isinstance(exc, Exception)),
                    None,
                )
                if fatal is not None:
                    fatal.add_note(detail)
                    raise fatal
                raise _error(detail)


class OrderedBundleTransaction:
    """Publish one light bundle without clobber and roll back only owned inodes."""

    def __init__(self, *, guard_path: Path, repo_root: Path = PROJECT_ROOT) -> None:
        self.guard_path = guard_path
        self.repo_root = repo_root
        self.guard: OwnedOutput | None = None
        self.outputs: list[OwnedOutput] = []
        self.created_directories: list[OwnedDirectory] = []
        self.committed = False

    def __enter__(self) -> "OrderedBundleTransaction":
        self.guard = _publish_one(
            self.guard_path,
            GUARD_PAYLOAD,
            repo_root=self.repo_root,
        )
        self.created_directories.extend(self.guard.created_directories)
        return self

    def publish(self, path: Path, payload: bytes) -> dict[str, Any]:
        if self.committed:
            raise _error("Cannot publish after E0-MCAL transaction commit")
        owned = _publish_one(path, payload, repo_root=self.repo_root)
        self.outputs.append(owned)
        self.created_directories.extend(owned.created_directories)
        return {
            "path": path.relative_to(self.repo_root).as_posix(),
            "bytes": owned.identity.size,
            "sha256": owned.sha256,
        }

    def commit(
        self, *, post_release_validators: Sequence[Callable[[], None]] = ()
    ) -> None:
        if self.guard is None or self.committed:
            raise _error("E0-MCAL transaction is not active")
        _validate_owned(self.guard, repo_root=self.repo_root)
        for owned in self.outputs:
            _validate_owned(owned, repo_root=self.repo_root)
        _unlink_owned(self.guard_path, self.guard, repo_root=self.repo_root)
        self.guard = None
        # The guard release is the last point at which another actor can race
        # the owned bundle while publication is still provisional.  Reopen
        # every name after that release so a same-inode write or name swap in
        # the validation/unlink window cannot be reported as committed.
        for owned in self.outputs:
            _validate_owned(owned, repo_root=self.repo_root)
        for validator in post_release_validators:
            validator()
        # A validator can be arbitrarily expensive.  Close the reciprocal
        # window by checking the owned payloads once more after all external
        # scientific/authority snapshots have been revalidated.
        for owned in self.outputs:
            _validate_owned(owned, repo_root=self.repo_root)
        _remove_owned_empty_directories(
            self.created_directories, repo_root=self.repo_root
        )
        self.committed = True

    def _rollback(self) -> None:
        errors: list[BaseException] = []
        for owned in reversed(self.outputs):
            try:
                _unlink_owned(owned.path, owned, repo_root=self.repo_root)
            except BaseException as exc:
                errors.append(exc)
        if self.guard is not None:
            try:
                _unlink_owned(self.guard_path, self.guard, repo_root=self.repo_root)
                self.guard = None
            except BaseException as exc:
                errors.append(exc)
        try:
            _remove_owned_empty_directories(
                self.created_directories, repo_root=self.repo_root
            )
        except BaseException as exc:
            errors.append(exc)
        if errors:
            detail = "E0-MCAL rollback could not be completed safely: " + "; ".join(
                f"{type(exc).__name__}: {exc}" for exc in errors
            )
            fatal = next((exc for exc in errors if not isinstance(exc, Exception)), None)
            if fatal is not None:
                fatal.add_note(detail)
                raise fatal
            raise _error(detail)

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        if not self.committed:
            self._rollback()
        return False


def publish_ordered_bundle(
    payloads: Sequence[tuple[Path, bytes]],
    *,
    manifest_path: Path,
    guard_path: Path,
    repo_root: Path = PROJECT_ROOT,
) -> list[dict[str, Any]]:
    paths = [path for path, _ in payloads]
    if len(paths) != len(set(paths)) or not paths or paths[-1] != manifest_path:
        raise _error("E0-MCAL bundle must be unique, nonempty, and manifest-last")
    records: list[dict[str, Any]] = []
    with OrderedBundleTransaction(guard_path=guard_path, repo_root=repo_root) as transaction:
        for path, payload in payloads:
            records.append(transaction.publish(path, payload))
        transaction.commit()
    return records


def _finite_vector(values: Sequence[float] | np.ndarray, *, context: str) -> np.ndarray:
    raw = np.asarray(values)
    if raw.dtype.kind == "b" or raw.dtype.kind not in {"i", "u", "f"}:
        raise _error(f"{context} must contain only real non-boolean numbers")
    array = raw.astype(np.float64)
    if array.ndim != 1 or array.size == 0 or not np.isfinite(array).all():
        raise _error(f"{context} must be one nonempty finite vector")
    return array


def _probability_vector(
    values: Sequence[float] | np.ndarray, *, context: str
) -> np.ndarray:
    array = _finite_vector(values, context=context)
    if np.any((array < 0.0) | (array > 1.0)):
        raise _error(f"{context} must remain in [0, 1]")
    return array


def _binary_vector(values: Sequence[int] | np.ndarray, *, context: str) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim != 1 or array.size == 0 or array.dtype.kind == "b":
        raise _error(f"{context} must be one nonempty vector")
    if array.dtype.kind not in {"i", "u"} or not np.isin(array, (0, 1)).all():
        raise _error(f"{context} must contain exact binary labels")
    return array.astype(np.int8)


def fit_calibrator_spec(
    method: str,
    scores: Sequence[float] | np.ndarray,
    labels: Sequence[int] | np.ndarray,
) -> dict[str, Any]:
    score = _probability_vector(scores, context="calibrator scores")
    target = _binary_vector(labels, context="calibrator labels")
    if len(score) != len(target):
        raise _error("Calibrator scores/labels differ")
    if method not in METHODS:
        raise _error(f"Unregistered calibration method: {method!r}")
    if method == "identity":
        return {"method": method, "parameters": {}, "fit_rows": len(score)}
    if len(np.unique(target)) != 2:
        raise _error(f"{method} requires both binary classes")
    if method == "platt_logistic":
        estimator = LogisticRegression(
            C=1_000_000.0,
            solver="lbfgs",
            fit_intercept=True,
            max_iter=2000,
            tol=1e-12,
            random_state=1729,
        )
        estimator.fit(score.reshape(-1, 1), target)
        return {
            "method": method,
            "parameters": {
                "coefficient": float(estimator.coef_[0, 0]),
                "intercept": float(estimator.intercept_[0]),
                "input": "raw_probability",
            },
            "fit_rows": len(score),
        }
    estimator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    estimator.fit(score, target)
    return {
        "method": method,
        "parameters": {
            "x_thresholds": [float(value) for value in estimator.X_thresholds_],
            "y_thresholds": [float(value) for value in estimator.y_thresholds_],
            "out_of_bounds": "clip",
        },
        "fit_rows": len(score),
    }


def apply_calibrator_spec(
    spec: Mapping[str, Any], scores: Sequence[float] | np.ndarray
) -> np.ndarray:
    score = _probability_vector(scores, context="calibrator application scores")
    method = spec.get("method")
    parameters = spec.get("parameters")
    if not isinstance(parameters, Mapping):
        raise _error("Calibrator parameters must be one mapping")
    if method == "identity":
        calibrated = score.copy()
    elif method == "platt_logistic":
        coefficient = float(parameters.get("coefficient"))
        intercept = float(parameters.get("intercept"))
        logits = np.clip(coefficient * score + intercept, -700.0, 700.0)
        calibrated = 1.0 / (1.0 + np.exp(-logits))
    elif method == "isotonic_regression":
        x = _finite_vector(
            cast(Sequence[float], parameters.get("x_thresholds")),
            context="isotonic x thresholds",
        )
        y = _finite_vector(
            cast(Sequence[float], parameters.get("y_thresholds")),
            context="isotonic y thresholds",
        )
        if len(x) != len(y) or len(x) < 2 or np.any(np.diff(x) <= 0.0) or np.any(
            np.diff(y) < 0.0
        ):
            raise _error("Isotonic threshold specification drifted")
        calibrated = np.interp(score, x, y, left=y[0], right=y[-1])
    else:
        raise _error("Calibrator specification carries an unknown method")
    if not np.isfinite(calibrated).all() or np.any((calibrated < 0.0) | (calibrated > 1.0)):
        raise _error("Calibrated probabilities leave [0, 1]")
    return calibrated.astype(np.float64)


def brier_score(labels: Sequence[int] | np.ndarray, probabilities: Sequence[float] | np.ndarray) -> float:
    target = _binary_vector(labels, context="Brier labels")
    probability = _probability_vector(probabilities, context="Brier probabilities")
    if len(target) != len(probability):
        raise _error("Brier vectors differ in length")
    return float(np.mean((probability - target) ** 2))


def expected_calibration_error(
    labels: Sequence[int] | np.ndarray,
    probabilities: Sequence[float] | np.ndarray,
    *,
    bins: int = 10,
) -> float:
    target = _binary_vector(labels, context="ECE labels")
    probability = _probability_vector(probabilities, context="ECE probabilities")
    if len(target) != len(probability) or type(bins) is not int or bins != 10:
        raise _error("ECE requires equal vectors and the locked ten bins")
    total = len(target)
    value = 0.0
    indexes = np.minimum((probability * bins).astype(int), bins - 1)
    for index in range(bins):
        mask = indexes == index
        if mask.any():
            value += float(mask.sum()) / total * abs(
                float(probability[mask].mean()) - float(target[mask].mean())
            )
    return value


def select_calibration_method(
    fit_scores: Sequence[float] | np.ndarray,
    fit_labels: Sequence[int] | np.ndarray,
    assessment_scores: Sequence[float] | np.ndarray,
    assessment_labels: Sequence[int] | np.ndarray,
    *,
    tolerance: float = 0.001,
) -> tuple[str, list[dict[str, Any]]]:
    if type(tolerance) is not float or tolerance != 0.001:
        raise _error("Calibration method selection requires tolerance=0.001")
    assessment_target = _binary_vector(assessment_labels, context="assessment labels")
    rows: list[dict[str, Any]] = []
    for rank, method in enumerate(METHODS):
        spec = fit_calibrator_spec(method, fit_scores, fit_labels)
        probability = apply_calibrator_spec(spec, assessment_scores)
        rows.append(
            {
                "method": method,
                "brier": brier_score(assessment_target, probability),
                "ece10": expected_calibration_error(assessment_target, probability),
                "simplicity_rank": rank,
            }
        )
    minimum = min(float(row["brier"]) for row in rows)
    eligible = [row for row in rows if float(row["brier"]) <= minimum + tolerance]
    selected = min(
        eligible,
        key=lambda row: (float(row["ece10"]), int(row["simplicity_rank"])),
    )
    return str(selected["method"]), rows


def select_alert_threshold(
    probabilities: Sequence[float] | np.ndarray,
    labels: Sequence[int] | np.ndarray,
    *,
    beta: float = 2.0,
) -> dict[str, Any]:
    probability = _probability_vector(probabilities, context="threshold probabilities")
    target = _binary_vector(labels, context="threshold labels")
    if len(probability) != len(target) or type(beta) is not float or beta != 2.0:
        raise _error("Threshold selection requires equal vectors and beta=2")
    candidates = np.unique(np.concatenate((probability, np.asarray([0.0, 0.5, 1.0]))))
    rows: list[dict[str, float]] = []
    beta_squared = beta * beta
    for threshold in candidates:
        predicted = probability >= threshold
        positives = target == 1
        tp = int(np.logical_and(predicted, positives).sum())
        fp = int(np.logical_and(predicted, ~positives).sum())
        fn = int(np.logical_and(~predicted, positives).sum())
        recall = tp / (tp + fn) if tp + fn else 0.0
        precision = tp / (tp + fp) if tp + fp else 0.0
        denominator = beta_squared * precision + recall
        fbeta = (
            (1.0 + beta_squared) * precision * recall / denominator
            if denominator
            else 0.0
        )
        rows.append(
            {
                "threshold": float(threshold),
                "f2": float(fbeta),
                "recall": float(recall),
                "precision": float(precision),
            }
        )
    return max(
        rows,
        key=lambda row: (
            row["f2"],
            row["recall"],
            row["precision"],
            -row["threshold"],
        ),
    )


def _ordinal_metrics(target: np.ndarray, predicted: np.ndarray) -> tuple[float, float]:
    f1_values: list[float] = []
    for value in range(4):
        true = target == value
        selected = predicted == value
        tp = int(np.logical_and(true, selected).sum())
        denominator = int(true.sum()) + int(selected.sum())
        f1_values.append(2.0 * tp / denominator if denominator else 0.0)
    return float(np.mean(f1_values)), float(np.mean(np.abs(target - predicted)))


def select_ordinal_cutpoints(
    scores: Sequence[float] | np.ndarray,
    labels: Sequence[int] | np.ndarray,
) -> dict[str, Any]:
    score = _finite_vector(scores, context="ordinal scores")
    raw_target = np.asarray(labels)
    if (
        raw_target.ndim != 1
        or len(raw_target) != len(score)
        or raw_target.dtype.kind == "b"
        or raw_target.dtype.kind not in {"i", "u"}
        or not np.isin(raw_target, (0, 1, 2, 3)).all()
    ):
        raise _error("Ordinal targets must be exact classes 0..3")
    target = raw_target.astype(np.int8)
    order = np.argsort(score, kind="mergesort")
    sorted_score = score[order]
    sorted_target = target[order]
    unique, group_counts = np.unique(sorted_score, return_counts=True)
    if len(unique) < 4:
        raise _error("Ordinal cutpoint selection needs four distinct predictions")
    candidates = (unique[:-1] + unique[1:]) / 2.0
    group_ends = np.concatenate(
        (np.asarray([0], dtype=np.int64), np.cumsum(group_counts, dtype=np.int64))
    )
    label_prefix = np.zeros((len(score) + 1, 4), dtype=np.int64)
    label_prefix[1:, :] = np.cumsum(
        np.eye(4, dtype=np.int64)[sorted_target.astype(np.int64)], axis=0
    )
    absolute_prefix = np.zeros((len(score) + 1, 4), dtype=np.int64)
    absolute_prefix[1:, :] = np.cumsum(
        np.abs(sorted_target[:, None].astype(np.int64) - np.arange(4)[None, :]),
        axis=0,
    )
    true_counts = np.bincount(target.astype(np.int64), minlength=4).astype(np.int64)
    unique_count = len(unique)

    # Four predicted classes induce four contiguous score segments.  The
    # objective is additive by segment: F1_c depends only on TP_c and the
    # predicted size of segment c, while ordinal absolute error is a prefix
    # sum.  Dynamic programming therefore evaluates every exact boundary pair
    # in O(4 U^2), instead of enumerating O(U^3) cutpoint triples.
    previous_f1 = np.full(unique_count + 1, -np.inf, dtype=np.float64)
    previous_error = np.full(unique_count + 1, np.iinfo(np.int64).max, dtype=np.int64)
    previous_bounds: list[tuple[int, ...] | None] = [None] * (unique_count + 1)

    def segment_values(
        predicted_class: int, starts: np.ndarray, end: int
    ) -> tuple[np.ndarray, np.ndarray]:
        start_rows = group_ends[starts]
        end_row = int(group_ends[end])
        predicted_count = end_row - start_rows
        true_positive = (
            label_prefix[end_row, predicted_class]
            - label_prefix[start_rows, predicted_class]
        )
        denominator = true_counts[predicted_class] + predicted_count
        f1 = np.divide(
            2.0 * true_positive,
            denominator,
            out=np.zeros_like(true_positive, dtype=np.float64),
            where=denominator != 0,
        )
        error = (
            absolute_prefix[end_row, predicted_class]
            - absolute_prefix[start_rows, predicted_class]
        )
        return f1, error.astype(np.int64, copy=False)

    for end in range(1, unique_count - 2):
        f1, error = segment_values(0, np.asarray([0], dtype=np.int64), end)
        previous_f1[end] = float(f1[0])
        previous_error[end] = int(error[0])
        previous_bounds[end] = (end,)

    for predicted_class, maximum_end in ((1, unique_count - 1), (2, unique_count)):
        current_f1 = np.full(unique_count + 1, -np.inf, dtype=np.float64)
        current_error = np.full(
            unique_count + 1, np.iinfo(np.int64).max, dtype=np.int64
        )
        current_bounds: list[tuple[int, ...] | None] = [None] * (unique_count + 1)
        minimum_end = predicted_class + 1
        for end in range(minimum_end, maximum_end):
            starts = np.arange(predicted_class, end, dtype=np.int64)
            valid = np.isfinite(previous_f1[starts])
            starts = starts[valid]
            if starts.size == 0:
                continue
            segment_f1, segment_error = segment_values(predicted_class, starts, end)
            candidate_f1 = previous_f1[starts] + segment_f1
            best_f1 = float(np.max(candidate_f1))
            tied_mask = np.isclose(candidate_f1, best_f1, rtol=0.0, atol=1e-15)
            tied = starts[tied_mask]
            tied_error = previous_error[tied] + segment_error[tied_mask]
            best_error = int(np.min(tied_error))
            tied = tied[tied_error == best_error]
            best_start = min(
                (int(start) for start in tied),
                key=lambda start: cast(tuple[int, ...], previous_bounds[start]),
            )
            current_f1[end] = best_f1
            current_error[end] = best_error
            current_bounds[end] = (
                *cast(tuple[int, ...], previous_bounds[best_start]),
                end,
            )
        previous_f1, previous_error, previous_bounds = (
            current_f1,
            current_error,
            current_bounds,
        )

    starts = np.arange(3, unique_count, dtype=np.int64)
    valid = np.isfinite(previous_f1[starts])
    starts = starts[valid]
    final_f1, final_error = segment_values(3, starts, unique_count)
    candidate_f1 = previous_f1[starts] + final_f1
    best_f1_sum = float(np.max(candidate_f1))
    tied_mask = np.isclose(candidate_f1, best_f1_sum, rtol=0.0, atol=1e-15)
    tied = starts[tied_mask]
    tied_error = previous_error[tied] + final_error[tied_mask]
    best_error_sum = int(np.min(tied_error))
    tied = tied[tied_error == best_error_sum]
    boundaries = min(
        (cast(tuple[int, ...], previous_bounds[int(start)]) for start in tied)
    )
    cutpoints = tuple(float(candidates[index - 1]) for index in boundaries)
    return {
        "cutpoints": list(cutpoints),
        "macro_f1": best_f1_sum / 4.0,
        "ordinal_mae": best_error_sum / len(target),
    }


def split_conformal_q_c(
    observed: Sequence[float] | np.ndarray,
    predicted: Sequence[float] | np.ndarray,
    sigma: Sequence[float] | np.ndarray,
    *,
    levels: Sequence[float] = (0.80, 0.90, 0.95),
    scale_floor: float = 0.000001,
    minimum_rows: int = 30,
) -> list[dict[str, Any]]:
    if (
        tuple(levels) != (0.80, 0.90, 0.95)
        or any(type(level) is not float for level in levels)
        or type(scale_floor) is not float
        or scale_floor != 0.000001
        or type(minimum_rows) is not int
        or minimum_rows != 30
    ):
        raise _error("Conformal controls differ from the exact E0-MCAL contract")
    target = _finite_vector(observed, context="conformal observations")
    estimate = _finite_vector(predicted, context="conformal predictions")
    scale = _finite_vector(sigma, context="conformal scales")
    if len(target) != len(estimate) or len(target) != len(scale):
        raise _error("Conformal vectors differ in length")
    if np.any(scale <= 0.0):
        raise _error("Conformal scales must be strictly positive")
    residual = np.abs(target - estimate) / np.maximum(scale, scale_floor)
    ordered = np.sort(residual, kind="mergesort")
    rows: list[dict[str, Any]] = []
    for level in levels:
        if len(ordered) < minimum_rows:
            rows.append(
                {
                    "coverage_level": level,
                    "status": "not_available_insufficient_finite_rows",
                    "finite_rows": len(ordered),
                    "q_c": None,
                }
            )
            continue
        rank = min(len(ordered), math.ceil((len(ordered) + 1) * level))
        rows.append(
            {
                "coverage_level": level,
                "status": "completed",
                "finite_rows": len(ordered),
                "order_statistic_rank": rank,
                "q_c": float(ordered[rank - 1]),
            }
        )
    return rows


def _exact_integer_column(frame: pd.DataFrame, column: str) -> pd.Series:
    values = frame[column]
    if not pd.api.types.is_integer_dtype(values.dtype) or pd.api.types.is_bool_dtype(
        values.dtype
    ):
        raise _error(f"E0-MCAL {column} must contain exact non-boolean integers")
    return values.astype("int64")


def _canonical_months(values: pd.Series, *, context: str) -> pd.PeriodIndex:
    strings = values.astype(str)
    if not strings.str.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])").all():
        raise _error(f"E0-MCAL {context} contains a noncanonical month")
    try:
        periods = pd.PeriodIndex(strings, freq="M")
    except (TypeError, ValueError) as exc:
        raise _error(f"E0-MCAL {context} contains an invalid month") from exc
    if periods.astype(str).tolist() != strings.tolist():
        raise _error(f"E0-MCAL {context} month roundtrip drifted")
    return periods


def _target_key_set(frame: pd.DataFrame) -> set[tuple[Any, ...]]:
    return set(
        frame.loc[:, list(TARGET_JOIN_COLUMNS)].itertuples(index=False, name=None)
    )


def _validate_calibration_frame(
    frame: pd.DataFrame, *, target_universe: pd.DataFrame | None = None
) -> pd.DataFrame:
    if not set(PREDICTION_COLUMNS).issubset(frame.columns):
        missing = sorted(set(PREDICTION_COLUMNS) - set(frame.columns))
        raise _error(f"E0-MCAL normalized prediction columns are absent: {missing}")
    value = frame.loc[:, list(PREDICTION_COLUMNS)].copy()
    if value.empty or value.isna().loc[:, [
        "model_id",
        "model_seed",
        "horizon_months",
        "source_id",
        "site_id",
        "common_origin_id",
        "origin_year_month",
        "assignment_role",
        "time_role",
        "target_year_month",
        "bloom_probability",
        "bloom_label",
    ]].any().any():
        raise _error("E0-MCAL normalized predictions are empty or incomplete")
    _require_exact_text_columns(
        value,
        (
            "model_id",
            "source_id",
            "site_id",
            "common_origin_id",
            "origin_year_month",
            "assignment_role",
            "time_role",
            "target_year_month",
        ),
        context="normalized predictions",
    )
    if (
        set(value["source_id"].astype(str)) != {"wqp"}
        or set(value["assignment_role"].astype(str)) != {"development"}
        or not value["time_role"].isin(
            {"model_selection", "calibration_threshold"}
        ).all()
    ):
        raise _error("E0-MCAL normalized predictions cross the development boundary")
    origin_periods = _canonical_months(
        value["origin_year_month"], context="origin_year_month"
    )
    target_periods = _canonical_months(
        value["target_year_month"], context="target_year_month"
    )
    value["model_seed"] = _exact_integer_column(value, "model_seed")
    value["horizon_months"] = _exact_integer_column(value, "horizon_months")
    if not value["horizon_months"].isin(HORIZONS).all() or any(
        origin + int(horizon) != target
        for origin, target, horizon in zip(
            origin_periods,
            target_periods,
            value["horizon_months"],
            strict=True,
        )
    ):
        raise _error("E0-MCAL exact origin/target/horizon identity drifted")
    if not target_periods.astype(str).to_series(index=value.index).between(
        "2019-01", "2021-12"
    ).all():
        raise _error("E0-MCAL normalized predictions cross the development boundary")
    years = pd.Series(
        [cast(pd.Period, period).year for period in target_periods],
        index=value.index,
    ).astype(str)
    expected_roles = years.map(
        {"2019": "model_selection", "2020": "model_selection", "2021": "calibration_threshold"}
    )
    if expected_roles.isna().any() or not value["time_role"].astype(str).eq(
        expected_roles
    ).all():
        raise _error("E0-MCAL temporal role/year binding drifted")
    value["calibration_year"] = years.astype(int)
    _probability_vector(
        value["bloom_probability"].to_numpy(), context="normalized bloom probability"
    )
    _binary_vector(value["bloom_label"].to_numpy(), context="normalized bloom labels")
    ordinal_mask = value["model_id"].isin(ORDINAL_MODELS)
    if (
        value.loc[ordinal_mask, ["ordinal_score", "ordinal_label"]].isna().any().any()
        or value.loc[~ordinal_mask, ["ordinal_score", "ordinal_label"]]
        .notna()
        .any()
        .any()
    ):
        raise _error("E0-MCAL ordinal applicability columns drifted")
    if ordinal_mask.any():
        _probability_vector(
            value.loc[ordinal_mask, "ordinal_score"].to_numpy(),
            context="normalized ordinal score",
        )
        ordinal_label = value.loc[ordinal_mask, "ordinal_label"]
        if ordinal_label.dtype.kind == "b" or ordinal_label.dtype.kind not in {"i", "u"}:
            raise _error("E0-MCAL ordinal labels must be exact integer classes")
        if not ordinal_label.isin((0, 1, 2, 3)).all():
            raise _error("E0-MCAL ordinal labels leave exact classes 0..3")
    uncertainty_mask = value["model_id"].isin(UNCERTAINTY_MODELS)
    uncertainty_columns = [
        "observed_risk",
        "predicted_risk",
        "predicted_risk_sigma",
    ]
    if (
        value.loc[uncertainty_mask, uncertainty_columns].isna().any().any()
        or value.loc[~uncertainty_mask, uncertainty_columns].notna().any().any()
    ):
        raise _error("E0-MCAL uncertainty applicability columns drifted")
    if uncertainty_mask.any():
        _probability_vector(
            value.loc[uncertainty_mask, "observed_risk"].to_numpy(),
            context="normalized observed risk",
        )
        _probability_vector(
            value.loc[uncertainty_mask, "predicted_risk"].to_numpy(),
            context="normalized predicted risk",
        )
        sigma = _finite_vector(
            value.loc[uncertainty_mask, "predicted_risk_sigma"].to_numpy(),
            context="normalized predicted risk sigma",
        )
        if np.any(sigma <= 0.0):
            raise _error("E0-MCAL predicted risk sigma must be strictly positive")
    expected_groups = {
        (model, seed, horizon)
        for model in CALIBRATABLE_MODELS
        for seed in MODEL_SEEDS[model]
        for horizon in HORIZONS
    }
    observed_groups = set(
        value.loc[:, ["model_id", "model_seed", "horizon_months"]].itertuples(
            index=False, name=None
        )
    )
    if observed_groups != expected_groups or len(expected_groups) != 66:
        raise _error("E0-MCAL bloom group universe differs from exact 66")
    common_bindings = value.groupby(
        ["source_id", "site_id", "origin_year_month"], sort=False
    )["common_origin_id"].nunique()
    if not common_bindings.eq(1).all():
        raise _error("E0-MCAL common-origin identity is not functional")

    target_columns = [
        *TARGET_JOIN_COLUMNS,
        "bloom_h",
        "target_risk_chla_h",
        "ordinal_label",
    ]
    if target_universe is None or not set(target_columns).issubset(
        target_universe.columns
    ):
        raise _error("E0-MCAL exact labeled target universe is absent")
    reference = target_universe.loc[:, target_columns].copy()
    reference["horizon_months"] = _exact_integer_column(
        reference, "horizon_months"
    )
    _canonical_months(reference["origin_year_month"], context="target origin")
    _canonical_months(reference["target_year_month"], context="target month")
    if (
        reference.duplicated(list(TARGET_JOIN_COLUMNS)).any()
        or not pd.api.types.is_bool_dtype(reference["bloom_h"].dtype)
        or reference["bloom_h"].isna().any()
    ):
        raise _error("E0-MCAL exact target universe is duplicated or malformed")
    reference["bloom_h"] = reference["bloom_h"].astype("int8")
    _probability_vector(
        reference["target_risk_chla_h"].to_numpy(),
        context="exact target risk",
    )
    target_ordinal = reference["ordinal_label"]
    if (
        target_ordinal.dtype.kind == "b"
        or target_ordinal.dtype.kind not in {"i", "u"}
        or not target_ordinal.isin((0, 1, 2, 3)).all()
    ):
        raise _error("E0-MCAL exact target ordinal labels drifted")
    expected_by_horizon = {
        horizon: _target_key_set(reference.loc[reference["horizon_months"].eq(horizon)])
        for horizon in HORIZONS
    }
    if any(not keys for keys in expected_by_horizon.values()):
        raise _error("E0-MCAL exact target universe is incomplete")

    for key, group in value.groupby(
        ["model_id", "model_seed", "horizon_months"], sort=False
    ):
        if set(group["calibration_year"].astype(int)) != {2019, 2020, 2021}:
            raise _error(f"E0-MCAL group lacks 2019/2020/2021 rows: {key}")
        if group.duplicated(list(TARGET_JOIN_COLUMNS)).any():
            raise _error(f"E0-MCAL group contains duplicate identities: {key}")
        horizon = int(cast(tuple[Any, Any, Any], key)[2])
        if _target_key_set(group) != expected_by_horizon[horizon]:
            raise _error(f"E0-MCAL group target universe drifted: {key}")
        labeled = group.merge(
            reference.loc[
                reference["horizon_months"].eq(horizon), target_columns
            ],
            on=list(TARGET_JOIN_COLUMNS),
            how="inner",
            validate="one_to_one",
        )
        if not np.array_equal(
            labeled["bloom_label"].to_numpy(dtype=np.int8),
            labeled["bloom_h"].to_numpy(dtype=np.int8),
        ):
            raise _error(f"E0-MCAL group bloom labels differ from targets: {key}")
        model_id = str(cast(tuple[Any, Any, Any], key)[0])
        if model_id in ORDINAL_MODELS and not np.array_equal(
            labeled["ordinal_label_x"].to_numpy(dtype=np.int8),
            labeled["ordinal_label_y"].to_numpy(dtype=np.int8),
        ):
            raise _error(f"E0-MCAL group ordinal labels differ from targets: {key}")
        if model_id in UNCERTAINTY_MODELS and not np.array_equal(
            labeled["observed_risk"].to_numpy(dtype=np.float64),
            labeled["target_risk_chla_h"].to_numpy(dtype=np.float64),
        ):
            raise _error(f"E0-MCAL group risks differ from targets: {key}")
    return value.sort_values(
        [
            "model_id",
            "model_seed",
            "horizon_months",
            "target_year_month",
            "origin_year_month",
            "source_id",
            "site_id",
            "common_origin_id",
        ],
        kind="mergesort",
    ).reset_index(drop=True)


def _availability_frame(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    observed = [dict(record) for record in records]
    expected = [dict(record) for record in calibration._expected_model_records()]
    if _canonical_json_bytes({"records": observed}) != _canonical_json_bytes(
        {"records": expected}
    ):
        raise _error("E0-MCAL model availability matrix differs from its authority")
    frame = pd.DataFrame(observed, columns=list(expected[0]))
    if "availability" not in frame or frame["availability"].value_counts().to_dict() != {
        "available": 8,
        "unavailable": 3,
    }:
        raise _error("E0-MCAL availability partition differs from 8/3")
    return frame


def _validate_input_filter_evidence(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Close the scientific row-filter audit before serializing any output."""

    observed = [dict(record) for record in records]
    if len(observed) != 5:
        raise _error("E0-MCAL calibration filter evidence cardinality drifted")
    target = observed[0]
    target_keys = {
        "role",
        "scanner",
        "predicate",
        "materialized_row_count",
        "minimum_origin_year_month",
        "maximum_origin_year_month",
        "minimum_target_year_month",
        "maximum_target_year_month",
        "boundary_crossing_rows",
        "holdout_rows_materialized",
        "development_site_count",
        "development_site_ids_sha256",
    }
    if (
        set(target) != target_keys
        or target.get("role") != "target_predicate_scan"
        or target.get("scanner")
        != "pyarrow_dataset_anchored_fd_predicate_pushdown"
        or target.get("predicate")
        != (
            "source_id=wqp AND site_id IN development AND "
            "origin<=2021-12 AND 2019-01<=target<=2021-12"
        )
        or target.get("materialized_row_count") != 2646
        or target.get("minimum_origin_year_month") != "2018-10"
        or target.get("maximum_origin_year_month") != "2021-11"
        or target.get("minimum_target_year_month") != "2019-01"
        or target.get("maximum_target_year_month") != "2021-12"
        or target.get("boundary_crossing_rows") != 0
        or target.get("holdout_rows_materialized") != 0
        or type(target.get("development_site_count")) is not int
        or cast(int, target["development_site_count"]) <= 0
        or re.fullmatch(
            r"[0-9a-f]{64}", str(target.get("development_site_ids_sha256"))
        )
        is None
    ):
        raise _error("E0-MCAL target filter evidence drifted")

    expected = (
        (
            "B0",
            "data/closure_v1/development/baselines/B0/raw_scores.parquet",
            2931,
            2646,
            285,
        ),
        (
            "B1",
            "data/closure_v1/development/baselines/B1/raw_scores.parquet",
            14655,
            13230,
            1425,
        ),
        (
            "B2",
            "data/closure_v1/development/baselines/B2/raw_scores.parquet",
            14655,
            13230,
            1425,
        ),
        (
            "M0",
            "data/closure_v1/development/mifal/M0/raw_scores.parquet",
            2931,
            2646,
            285,
        ),
    )
    raw_keys = {
        "model_id",
        "source_path",
        "candidate_row_count",
        "matched_target_row_count",
        "excluded_incomplete_target_row_count",
        "excluded_target_keys_sha256",
    }
    for record, (model_id, path, candidate, matched, excluded) in zip(
        observed[1:], expected, strict=True
    ):
        if (
            set(record) != raw_keys
            or record.get("model_id") != model_id
            or record.get("source_path") != path
            or record.get("candidate_row_count") != candidate
            or record.get("matched_target_row_count") != matched
            or record.get("excluded_incomplete_target_row_count") != excluded
            or candidate != matched + excluded
            or re.fullmatch(
                r"[0-9a-f]{64}", str(record.get("excluded_target_keys_sha256"))
            )
            is None
        ):
            raise _error(f"E0-MCAL raw exclusion evidence drifted: {model_id}")
    return observed


def build_final_calibration_bundle(
    *,
    authority: Mapping[str, Any],
    predictions: pd.DataFrame,
    model_availability: Sequence[Mapping[str, Any]],
    target_universe: pd.DataFrame | None = None,
    input_records: Sequence[Mapping[str, Any]] = (),
    input_filter_evidence: Sequence[Mapping[str, Any]] = (),
    execution_policy: Mapping[str, Any] | None = None,
    repo_root: Path = PROJECT_ROOT,
) -> tuple[list[tuple[Path, bytes]], dict[str, Any]]:
    """Build the exact six-file calibration bundle without touching the FS."""
    if authority.get("gate") != calibration.PATCH_GATE or authority.get("status") != "effective":
        raise _error("E0-MCAL calibration builder lacks effective authority")
    filter_evidence = _validate_input_filter_evidence(input_filter_evidence)
    frame = _validate_calibration_frame(
        predictions, target_universe=target_universe
    )
    availability = _availability_frame(model_availability)
    calibrators: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    ordinal_rows: list[dict[str, Any]] = []
    q_c_rows: list[dict[str, Any]] = []
    grouped = frame.groupby(
        ["model_id", "model_seed", "horizon_months"], sort=True
    )
    for raw_key, group in grouped:
        model_id, model_seed, horizon = cast(tuple[str, int, int], raw_key)
        by_year = {
            year: group.loc[group["calibration_year"].eq(year)].reset_index(drop=True)
            for year in (2019, 2020, 2021)
        }
        fit = by_year[2019]
        assessment = by_year[2020]
        calibration_rows = by_year[2021]
        if model_id == "B0":
            selected_method = "identity"
            selection_rows = [
                {
                    "method": "identity",
                    "brier": brier_score(
                        assessment["bloom_label"].to_numpy(),
                        assessment["bloom_probability"].to_numpy(),
                    ),
                    "ece10": expected_calibration_error(
                        assessment["bloom_label"].to_numpy(),
                        assessment["bloom_probability"].to_numpy(),
                    ),
                    "simplicity_rank": 0,
                }
            ]
        else:
            selected_method, selection_rows = select_calibration_method(
                fit["bloom_probability"].to_numpy(),
                fit["bloom_label"].to_numpy(),
                assessment["bloom_probability"].to_numpy(),
                assessment["bloom_label"].to_numpy(),
            )
        if model_id == "B0":
            final_spec = {"method": "identity", "parameters": {}, "fit_rows": 0}
            refit_year: int | None = None
            refit_status = "not_applicable_fixed_identity"
        else:
            final_spec = fit_calibrator_spec(
                selected_method,
                calibration_rows["bloom_probability"].to_numpy(),
                calibration_rows["bloom_label"].to_numpy(),
            )
            refit_year = 2021
            refit_status = "completed"
        calibrated = apply_calibrator_spec(
            final_spec, calibration_rows["bloom_probability"].to_numpy()
        )
        selected_evidence = next(
            row for row in selection_rows if row["method"] == selected_method
        )
        identity = {
            "model_id": str(model_id),
            "model_seed": int(model_seed),
            "horizon_months": int(horizon),
        }
        calibrators.append(
            {
                **identity,
                "selection_fit_year": 2019,
                "selection_assessment_year": 2020,
                "refit_year": refit_year,
                "refit_status": refit_status,
                "selected_method": selected_method,
                "selection_candidates": selection_rows,
                "refit_spec": final_spec,
            }
        )
        metric_rows.append(
            {
                **identity,
                "selected_method": selected_method,
                "selection_brier": selected_evidence["brier"],
                "selection_ece10": selected_evidence["ece10"],
                "calibration_brier": brier_score(
                    calibration_rows["bloom_label"].to_numpy(), calibrated
                ),
                "calibration_ece10": expected_calibration_error(
                    calibration_rows["bloom_label"].to_numpy(), calibrated
                ),
                "calibration_rows": len(calibration_rows),
            }
        )
        threshold_rows.append(
            {
                **identity,
                **select_alert_threshold(
                    calibrated, calibration_rows["bloom_label"].to_numpy()
                ),
                "selection_year": 2021,
            }
        )
        if model_id in ORDINAL_MODELS:
            if calibration_rows[["ordinal_score", "ordinal_label"]].isna().any().any():
                raise _error(f"E0-MCAL ordinal group is incomplete: {identity}")
            if model_id == "B0":
                if calibration_rows["ordinal_score"].nunique(dropna=False) != 1:
                    raise _error("E0-MCAL B0 fixed ordinal score is not constant")
                ordinal_rows.append(
                    {
                        **identity,
                        "status": "not_available_degenerate_constant_score",
                        "cutpoints": None,
                        "macro_f1": None,
                        "ordinal_mae": None,
                        "selection_year": 2021,
                    }
                )
            else:
                ordinal_rows.append(
                    {
                        **identity,
                        "status": "completed",
                        **select_ordinal_cutpoints(
                            calibration_rows["ordinal_score"].to_numpy(),
                            calibration_rows["ordinal_label"].to_numpy(),
                        ),
                        "selection_year": 2021,
                    }
                )
        if model_id in UNCERTAINTY_MODELS:
            if calibration_rows[
                ["observed_risk", "predicted_risk", "predicted_risk_sigma"]
            ].isna().any().any():
                raise _error(f"E0-MCAL uncertainty group is incomplete: {identity}")
            for record in split_conformal_q_c(
                calibration_rows["observed_risk"].to_numpy(),
                calibration_rows["predicted_risk"].to_numpy(),
                calibration_rows["predicted_risk_sigma"].to_numpy(),
            ):
                q_c_rows.append({**identity, **record, "calibration_year": 2021})
    if not (
        len(calibrators) == 66
        and len(metric_rows) == 66
        and len(threshold_rows) == 66
        and len(ordinal_rows) == 33
        and len(q_c_rows) == 90
    ):
        raise _error("E0-MCAL output group counts differ from 66/33/90")

    specs_payload = _canonical_json_bytes(
        {
            "schema_version": "closure_final_calibrator_specs_v1",
            "gate": calibration.PATCH_GATE,
            "bloom_calibrators": calibrators,
            "split_conformal_q_c": q_c_rows,
        }
    )
    members: list[tuple[Path, bytes]] = [
        (repo_root / CALIBRATOR_SPECS_PATH.relative_to(PROJECT_ROOT), specs_payload),
        (
            repo_root / CALIBRATION_METRICS_PATH.relative_to(PROJECT_ROOT),
            _csv_bytes(pd.DataFrame(metric_rows)),
        ),
        (
            repo_root / ALERT_THRESHOLDS_PATH.relative_to(PROJECT_ROOT),
            _csv_bytes(pd.DataFrame(threshold_rows)),
        ),
        (
            repo_root / ORDINAL_CUTPOINTS_PATH.relative_to(PROJECT_ROOT),
            _csv_bytes(pd.DataFrame(ordinal_rows)),
        ),
        (
            repo_root / MODEL_AVAILABILITY_PATH.relative_to(PROJECT_ROOT),
            _csv_bytes(availability),
        ),
    ]
    output_records = [
        {
            "path": path.relative_to(repo_root).as_posix(),
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        for path, payload in members
    ]
    authority_sha256 = authority.get("authority_binding_sha256")
    if (
        not isinstance(authority_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", authority_sha256) is None
    ):
        raise _error("E0-MCAL effective authority binding digest is absent")
    manifest = {
        "schema_version": "closure_final_calibration_manifest_v1",
        "experiment_id": "closure_v1",
        "gate": calibration.PATCH_GATE,
        "status": "completed_unpublished",
        "authority_sha256": authority_sha256,
        "group_counts": {
            "bloom": 66,
            "ordinal": 33,
            "uncertainty": 30,
            "q_c": 90,
        },
        "temporal_protocol": {
            "fit": "2019",
            "assessment": "2020",
            "refit_threshold_cutpoint_q_c": "2021",
            "time_column": "target_year_month",
        },
        "inputs": [dict(record) for record in input_records],
        "input_filter_evidence": filter_evidence,
        "execution_policy": dict(execution_policy or {}),
        "outputs": output_records,
        "scientific_boundary": {
            "development_only": True,
            "holdout_accessed": False,
            "post_2021_rows_accessed": False,
            "final_evaluation_run": False,
            "future_outcomes_accessed": False,
        },
    }
    members.append(
        (
            repo_root / MANIFEST_PATH.relative_to(PROJECT_ROOT),
            _canonical_json_bytes(manifest),
        )
    )
    return members, manifest


def _read_parquet_frame(
    path: Path,
    *,
    columns: Sequence[str],
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    payload, identity = _read_scientific_named_bytes(
        path,
        authorized_dvc_pointers=authorized_dvc_pointers,
        repo_root=repo_root,
    )
    try:
        table = pq.read_table(io.BytesIO(payload), columns=list(columns))
    except (OSError, ValueError) as exc:
        raise _error(f"E0-MCAL cannot decode exact Parquet input: {path}") from exc
    for column in (
        "model_seed",
        "technical_seed",
        "upstream_state_seed",
        "base_seed",
        "horizon_months",
    ):
        if column in table.column_names and not pa.types.is_integer(
            table.schema.field(column).type
        ):
            raise _error(f"E0-MCAL Parquet identity column is not integer: {column}")
    for column in (
        "source_id",
        "site_id",
        "common_origin_id",
        "assignment_role",
        "time_role",
        "origin_year_month",
        "target_year_month",
    ):
        if column in table.column_names and not (
            pa.types.is_string(table.schema.field(column).type)
            or pa.types.is_large_string(table.schema.field(column).type)
        ):
            raise _error(f"E0-MCAL Parquet identity column is not text: {column}")
    relative = path.relative_to(repo_root).as_posix()

    def exact_field(
        name: str, expected_type: pa.DataType, *, nullable: bool
    ) -> None:
        if name not in table.column_names:
            return
        field = table.schema.field(name)
        if field.type != expected_type or field.nullable is not nullable:
            raise _error(
                "E0-MCAL Parquet physical schema drifted: "
                f"{relative}:{name}"
            )

    if relative.endswith("/raw_scores.parquet"):
        for name in (
            "model_id",
            "source_id",
            "site_id",
            "common_origin_id",
            "assignment_role",
            "time_role",
            "origin_year_month",
            "target_year_month",
            "candidate",
            "availability_status",
            "failure_reason",
        ):
            exact_field(name, pa.string(), nullable=False)
        exact_field("horizon_months", pa.int16(), nullable=False)
        exact_field("technical_seed", pa.int64(), nullable=False)
        exact_field("model_seed", pa.int64(), nullable=True)
        exact_field("upstream_state_seed", pa.int64(), nullable=True)
        exact_field("selected_family", pa.bool_(), nullable=False)
        exact_field("raw_score", pa.float64(), nullable=True)
        exact_field("predicted_bloom_probability", pa.float64(), nullable=True)
    elif relative.endswith("_selection_predictions.parquet"):
        for name in (
            "model_id",
            "source_id",
            "site_id",
            "common_origin_id",
            "time_role",
            "origin_year_month",
            "target_year_month",
            "availability_status",
            "failure_reason",
        ):
            exact_field(name, pa.string(), nullable=False)
        exact_field("base_seed", pa.int64(), nullable=False)
        exact_field("horizon_months", pa.int16(), nullable=False)
        exact_field("observed_bloom", pa.int8(), nullable=False)
        for name in (
            "observed_risk",
            "predicted_bloom_probability",
            "predicted_risk",
            "predicted_risk_sigma",
        ):
            exact_field(name, pa.float64(), nullable=False)
    elif relative == "data/closure_v1/common_origin_manifest.parquet":
        exact_field("input_eligible", pa.bool_(), nullable=True)
        exact_field("complete_targets_evaluable", pa.bool_(), nullable=True)
        exact_field("horizon_months", pa.int64(), nullable=True)
    record = {
        "path": path.relative_to(repo_root).as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "mode": format(identity.mode, "04o"),
        "nlink": identity.nlink,
        "device": identity.device,
        "inode": identity.inode,
        "mtime_ns": identity.mtime_ns,
        "ctime_ns": identity.ctime_ns,
    }
    return table.to_pandas(), record


def _read_filtered_target_frame(
    path: Path,
    *,
    columns: Sequence[str],
    development_site_ids: Sequence[str],
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    if not development_site_ids:
        raise _error("E0-MCAL target scanner lacks development sites")
    authorized_payload, authorized_metadata = (
        calibration._read_scientific_payload_bytes_and_metadata(
            path.relative_to(repo_root),
            authorized_dvc_pointers=authorized_dvc_pointers,
            repo_root=repo_root,
        )
    )
    authorized_identity = _identity(authorized_metadata)
    parent, name, _ = _open_parent(path, repo_root=repo_root, create=False)
    descriptor: int | None = None
    try:
        named_before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent,
        )
        opened_before = os.fstat(descriptor)
        identity = _identity(opened_before)
        if (
            not stat.S_ISREG(opened_before.st_mode)
            or (opened_before.st_dev, opened_before.st_ino)
            != (named_before.st_dev, named_before.st_ino)
            or identity != authorized_identity
        ):
            raise _error("E0-MCAL target input differs from its P-bound identity")
        descriptor_path = Path(f"/proc/self/fd/{descriptor}")
        if not descriptor_path.exists():
            raise _error("E0-MCAL pinned target descriptor is unavailable")
        dataset = ds.dataset(descriptor_path.as_posix(), format="parquet")
        for column in (
            "source_id",
            "site_id",
            "origin_year_month",
            "target_year_month",
            "target_trophic_state_h",
        ):
            field_type = dataset.schema.field(column).type
            if not (pa.types.is_string(field_type) or pa.types.is_large_string(field_type)):
                raise _error(
                    f"E0-MCAL target Arrow text schema drifted: {column}"
                )
        if not pa.types.is_boolean(dataset.schema.field("bloom_h").type):
            raise _error("E0-MCAL target bloom_h Arrow schema is not exact boolean")
        if dataset.schema.field("horizon_months").type != pa.int64():
            raise _error("E0-MCAL target horizon Arrow schema is not exact integer")
        if dataset.schema.field("target_risk_chla_h").type != pa.float64():
            raise _error("E0-MCAL target risk Arrow schema is not exact floating point")
        predicate = (
            (ds.field("source_id") == "wqp")
            & ds.field("site_id").isin(list(development_site_ids))
            & (ds.field("origin_year_month") <= "2021-12")
            & (ds.field("target_year_month") >= "2019-01")
            & (ds.field("target_year_month") <= "2021-12")
        )
        frame = dataset.scanner(columns=list(columns), filter=predicate).to_table().to_pandas()
        opened_after_scan = os.fstat(descriptor)
        named_after_scan = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if _identity(opened_after_scan) != identity or _identity(named_after_scan) != identity:
            raise _error("E0-MCAL target input changed during predicate scan")
        digest = hashlib.sha256()
        size = 0
        os.lseek(descriptor, 0, os.SEEK_SET)
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        if (
            _identity(os.fstat(descriptor)) != identity
            or size != identity.size
            or size != len(authorized_payload)
            or digest.hexdigest() != _sha256_bytes(authorized_payload)
        ):
            raise _error("E0-MCAL target input changed during anchored hashing")
        if frame.empty:
            raise _error("E0-MCAL target predicate produced no development rows")
        origin = frame["origin_year_month"].astype(str)
        target = frame["target_year_month"].astype(str)
        boundary_crossing = int(
            ((origin > "2021-12") | (target > "2021-12") | (target < "2019-01")).sum()
        )
        sites = sorted(set(frame["site_id"].astype(str)))
        if boundary_crossing or not set(sites).issubset(set(development_site_ids)):
            raise _error("E0-MCAL target predicate crossed its scientific boundary")
        record = {
            "path": path.relative_to(repo_root).as_posix(),
            "bytes": identity.size,
            "sha256": digest.hexdigest(),
            "mode": format(identity.mode, "04o"),
            "nlink": identity.nlink,
            "device": identity.device,
            "inode": identity.inode,
            "mtime_ns": identity.mtime_ns,
            "ctime_ns": identity.ctime_ns,
        }
        audit = {
            "scanner": "pyarrow_dataset_anchored_fd_predicate_pushdown",
            "predicate": "source_id=wqp AND site_id IN development AND origin<=2021-12 AND 2019-01<=target<=2021-12",
            "materialized_row_count": len(frame),
            "minimum_origin_year_month": str(origin.min()),
            "maximum_origin_year_month": str(origin.max()),
            "minimum_target_year_month": str(target.min()),
            "maximum_target_year_month": str(target.max()),
            "boundary_crossing_rows": 0,
            "holdout_rows_materialized": 0,
            "development_site_count": len(sites),
            "development_site_ids_sha256": _sha256_bytes(
                _canonical_json_bytes({"site_ids": sites})
            ),
        }
        return frame, record, audit
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def _portable_record(record: Mapping[str, Any], *, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": str(record["path"]),
        "bytes": int(record["bytes"]),
        "sha256": str(record["sha256"]),
    }


def _require_exact_text_columns(
    frame: pd.DataFrame,
    columns: Sequence[str],
    *,
    context: str,
    allow_empty: Sequence[str] = (),
) -> None:
    for column in columns:
        if column not in frame or any(
            type(value) is not str or (not value and column not in allow_empty)
            for value in frame[column].tolist()
        ):
            raise _error(f"E0-MCAL {context} text identity drifted: {column}")


def _authority_path_records(
    paths: Sequence[tuple[str, Path]], *, repo_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    portable: list[dict[str, Any]] = []
    snapshot: list[dict[str, Any]] = []
    for role, path in paths:
        observed = stable_file_record(path, repo_root=repo_root)
        portable.append(_portable_record(observed, role=role))
        snapshot.append({"role": role, **observed})
    return portable, snapshot


def _validate_anfis_slot_manifest(
    manifest: Mapping[str, Any],
    *,
    model_id: str,
    base_seed: int,
    observed_outputs: Mapping[str, Mapping[str, Any]],
) -> None:
    """Bind a published A0/A1 slot manifest to every input opened by MCAL."""

    expected_scalars: Mapping[str, Any] = {
        "manifest_version": "closure_anfis_ablation_model_manifest_v1",
        "status": "completed",
        "slot_status": "available",
        "fit_status": "passed",
        "experiment_id": "closure_v1",
        "surface_id": anfis_training.SURFACE_ID,
        "model_id": model_id,
        "base_seed": base_seed,
        "device": anfis_training.LOCKED_DEVICE,
        "future_outcomes_accessed": False,
        "calibration_authorized": False,
        "calibration_target_accessed": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "dvc_command_executed": False,
        "completion_marker_written_last": True,
    }
    if any(manifest.get(key) != value for key, value in expected_scalars.items()):
        raise _error("E0-MCAL ANFIS model manifest identity drifted")
    authority = manifest.get("authority")
    expected_gate = "E0-MU" if model_id == "A0" and base_seed == 1729 else "E0-MX"
    if (
        not isinstance(authority, Mapping)
        or authority.get("gate") != expected_gate
        or authority.get("status") != "effective_preflight_passed"
        or authority.get("authorized_model_id") != model_id
        or authority.get("authorized_base_seed") != base_seed
    ):
        raise _error("E0-MCAL ANFIS model manifest authority drifted")
    script = manifest.get("script")
    source_code = manifest.get("source_code")
    if (
        not isinstance(script, Mapping)
        or set(script) != {"role", "path", "bytes", "sha256"}
        or script.get("role") != "trainer"
        or script.get("path") != "src/experiments/train_closure_anfis_ablation.py"
        or type(script.get("bytes")) is not int
        or cast(int, script["bytes"]) <= 0
        or not isinstance(script.get("sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", cast(str, script["sha256"])) is None
        or source_code != [dict(script)]
    ):
        raise _error("E0-MCAL ANFIS model manifest source provenance drifted")
    raw_outputs = manifest.get("outputs")
    expected_roles = {
        "model",
        "checkpoint",
        "preprocessor",
        "training_curve",
        "selection_predictions",
        "selection_metrics",
        "report",
    }
    if not isinstance(raw_outputs, list) or len(raw_outputs) != len(expected_roles):
        raise _error("E0-MCAL ANFIS model manifest output set drifted")
    by_role: dict[str, Mapping[str, Any]] = {}
    for raw in raw_outputs:
        if (
            not isinstance(raw, Mapping)
            or set(raw) != {"role", "path", "bytes", "sha256"}
            or not isinstance(raw.get("role"), str)
            or cast(str, raw["role"]) in by_role
            or not isinstance(raw.get("path"), str)
            or type(raw.get("bytes")) is not int
            or cast(int, raw["bytes"]) <= 0
            or not isinstance(raw.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", cast(str, raw["sha256"])) is None
        ):
            raise _error("E0-MCAL ANFIS model manifest output record drifted")
        by_role[cast(str, raw["role"])] = raw
    if set(by_role) != expected_roles:
        raise _error("E0-MCAL ANFIS model manifest output roles drifted")
    for role, observed in observed_outputs.items():
        expected = by_role.get(role)
        if expected is None or {
            key: expected.get(key) for key in ("path", "bytes", "sha256")
        } != {key: observed.get(key) for key in ("path", "bytes", "sha256")}:
            raise _error(
                f"E0-MCAL ANFIS manifest/input binding drifted: {model_id}:{base_seed}:{role}"
            )


def _target_projection(
    *, authorized_dvc_pointers: Sequence[Path], repo_root: Path
) -> tuple[
    pd.DataFrame,
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    columns = [
        *TARGET_JOIN_COLUMNS,
        "bloom_h",
        "target_risk_chla_h",
        "target_trophic_state_h",
    ]
    common_columns = [
        "source_id",
        "site_id",
        "common_origin_id",
        "assignment_role",
        "time_role",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
        "input_eligible",
        "complete_targets_evaluable",
    ]
    common_path = repo_root / "data/closure_v1/common_origin_manifest.parquet"
    common, common_record = _read_parquet_frame(
        common_path,
        columns=common_columns,
        authorized_dvc_pointers=authorized_dvc_pointers,
        repo_root=repo_root,
    )
    if any(
        not pd.api.types.is_bool_dtype(common[column].dtype)
        or common[column].isna().any()
        for column in ("input_eligible", "complete_targets_evaluable")
    ):
        raise _error("E0-MCAL common-origin eligibility types drifted")
    _require_exact_text_columns(
        common,
        (
            "source_id",
            "site_id",
            "common_origin_id",
            "assignment_role",
            "time_role",
            "origin_year_month",
            "target_year_month",
        ),
        context="common-origin",
    )
    common = common.loc[
        common["source_id"].astype(str).eq("wqp")
        & common["assignment_role"].astype(str).eq("development")
        & common["time_role"].isin({"model_selection", "calibration_threshold"})
        & common["input_eligible"].eq(True)
        & common["complete_targets_evaluable"].eq(True)
        & common["target_year_month"].astype(str).between("2019-01", "2021-12")
    ].copy()
    if common.empty or common.duplicated(list(TARGET_JOIN_COLUMNS)).any():
        raise _error("E0-MCAL development common-origin target universe drifted")
    development_site_ids = sorted(set(common["site_id"].astype(str)))
    targets, target_record, scanner_audit = _read_filtered_target_frame(
        repo_root / "data/targets/monthly_targets_model_v0.parquet",
        columns=columns,
        development_site_ids=development_site_ids,
        authorized_dvc_pointers=authorized_dvc_pointers,
        repo_root=repo_root,
    )
    _require_exact_text_columns(
        targets,
        (
            "source_id",
            "site_id",
            "origin_year_month",
            "target_year_month",
            "target_trophic_state_h",
        ),
        context="target",
    )
    frame = common.merge(
        targets,
        on=list(TARGET_JOIN_COLUMNS),
        how="left",
        validate="one_to_one",
    )
    if frame.empty or frame.duplicated(list(TARGET_JOIN_COLUMNS)).any():
        raise _error("E0-MCAL target projection is empty or duplicated")
    if (
        not pd.api.types.is_integer_dtype(frame["horizon_months"].dtype)
        or pd.api.types.is_bool_dtype(frame["horizon_months"].dtype)
        or not frame["horizon_months"].isin(HORIZONS).all()
        or not pd.api.types.is_bool_dtype(frame["bloom_h"].dtype)
        or frame["bloom_h"].isna().any()
    ):
        raise _error("E0-MCAL target horizon/bloom source types drifted")
    _canonical_months(frame["origin_year_month"], context="target origin")
    _canonical_months(frame["target_year_month"], context="target month")
    _probability_vector(
        frame["target_risk_chla_h"].to_numpy(), context="target risk"
    )
    if set(frame["target_trophic_state_h"].astype(str)) - set(TROPHIC_LABELS):
        raise _error("E0-MCAL target trophic labels drifted")
    trophic = {label: index for index, label in enumerate(TROPHIC_LABELS)}
    frame["ordinal_label"] = frame["target_trophic_state_h"].map(trophic)
    if frame[["bloom_h", "target_risk_chla_h", "ordinal_label"]].isna().any().any():
        raise _error("E0-MCAL 2019-2021 development target labels are incomplete")
    authority_paths = (
        (
            "common_origin_pointer",
            repo_root / "data/closure_v1/common_origin_manifest.parquet.dvc",
        ),
        (
            "common_origin_manifest",
            repo_root / "reports/closure_v1/01_surface/common_origin_manifest.json",
        ),
        ("targets_pointer", repo_root / "data/targets.dvc"),
        ("target_manifest", repo_root / "data/targets/target_manifest_v0.json"),
    )
    extra_portable, extra_snapshot = _authority_path_records(
        authority_paths, repo_root=repo_root
    )
    portable = [
        _portable_record(common_record, role="common_origin"),
        _portable_record(target_record, role="development_targets"),
        *extra_portable,
    ]
    snapshot = [
        {"role": "common_origin", **common_record},
        {"role": "development_targets", **target_record},
        *extra_snapshot,
    ]
    return frame, portable, snapshot, scanner_audit


def _baseline_predictions(
    targets: pd.DataFrame,
    *,
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> tuple[
    pd.DataFrame,
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    rows: list[pd.DataFrame] = []
    portable: list[dict[str, Any]] = []
    snapshot: list[dict[str, Any]] = []
    filter_evidence: list[dict[str, Any]] = []
    raw_columns = [
        "model_id",
        "source_id",
        "site_id",
        "common_origin_id",
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
        "raw_score",
        "predicted_bloom_probability",
    ]
    for model_id, relative in (
        ("B0", "data/closure_v1/development/baselines/B0/raw_scores.parquet"),
        ("B1", "data/closure_v1/development/baselines/B1/raw_scores.parquet"),
        ("B2", "data/closure_v1/development/baselines/B2/raw_scores.parquet"),
        ("M0", "data/closure_v1/development/mifal/M0/raw_scores.parquet"),
    ):
        path = repo_root / relative
        frame, record = _read_parquet_frame(
            path,
            columns=raw_columns,
            authorized_dvc_pointers=authorized_dvc_pointers,
            repo_root=repo_root,
        )
        _require_exact_text_columns(
            frame,
            (
                "model_id",
                "source_id",
                "site_id",
                "common_origin_id",
                "assignment_role",
                "time_role",
                "origin_year_month",
                "target_year_month",
                "candidate",
                "availability_status",
                "failure_reason",
            ),
            context=f"{model_id} raw scores",
            allow_empty=("failure_reason",),
        )
        snapshot.append({"role": f"{model_id.lower()}_raw_scores", **record})
        portable.append(_portable_record(record, role=f"{model_id.lower()}_raw_scores"))
        pointer_portable, pointer_snapshot = _authority_path_records(
            ((f"{model_id.lower()}_raw_scores_pointer", Path(f"{path}.dvc")),),
            repo_root=repo_root,
        )
        portable.extend(pointer_portable)
        snapshot.extend(pointer_snapshot)
        if set(frame["model_id"].tolist()) != {model_id}:
            raise _error(f"E0-MCAL {model_id} raw-score model identity drifted")
        frame["horizon_months"] = _exact_integer_column(
            frame, "horizon_months"
        )
        _exact_integer_column(frame, "technical_seed")
        if (
            not pd.api.types.is_bool_dtype(frame["selected_family"].dtype)
            or frame["selected_family"].isna().any()
        ):
            raise _error(f"E0-MCAL {model_id} selected_family type drifted")
        if (
            set(frame["availability_status"].tolist()) != {"success"}
            or not frame["failure_reason"].eq("").all()
        ):
            raise _error(f"E0-MCAL {model_id} raw-score availability drifted")
        if model_id == "M0":
            _probability_vector(
                frame["raw_score"].to_numpy(), context="M0 raw bloom score"
            )
            if frame["predicted_bloom_probability"].notna().any():
                raise _error("E0-MCAL M0 predicted probability must remain absent")
        else:
            _probability_vector(
                frame["predicted_bloom_probability"].to_numpy(),
                context=f"{model_id} predicted bloom probability",
            )
            _probability_vector(
                frame["raw_score"].to_numpy(),
                context=f"{model_id} raw ordinal score",
            )
        frame = frame.loc[
            frame["source_id"].astype(str).eq("wqp")
            & frame["assignment_role"].astype(str).eq("development")
            & frame["time_role"].isin({"model_selection", "calibration_threshold"})
            & frame["target_year_month"].astype(str).between("2019-01", "2021-12")
            & frame["availability_status"].astype(str).eq("success")
            & frame["failure_reason"].astype(str).eq("")
        ].copy()
        if model_id == "B2":
            frame = frame.loc[
                frame["selected_family"].eq(True)
                & frame["candidate"].astype(str).eq(
                    "hist_gradient_boosting_classifier"
                )
            ].copy()
            frame["normalized_seed"] = _exact_integer_column(frame, "model_seed")
        elif model_id == "B1":
            frame["normalized_seed"] = _exact_integer_column(
                frame, "upstream_state_seed"
            )
        else:
            frame["normalized_seed"] = _exact_integer_column(
                frame, "technical_seed"
            )
        if set(int(value) for value in frame["normalized_seed"]) != set(
            MODEL_SEEDS[model_id]
        ):
            raise _error(f"E0-MCAL {model_id} registered seed set drifted")
        if frame["normalized_seed"].isna().any() or frame["horizon_months"].isna().any():
            raise _error(f"E0-MCAL {model_id} seed/horizon identity is incomplete")
        candidate_keys = frame.loc[:, list(TARGET_JOIN_COLUMNS)].copy()
        target_keys = targets.loc[:, list(TARGET_JOIN_COLUMNS)].drop_duplicates()
        membership = candidate_keys.merge(
            target_keys.assign(_mcal_target=True),
            on=list(TARGET_JOIN_COLUMNS),
            how="left",
            validate="many_to_one",
        )["_mcal_target"].fillna(False).to_numpy(dtype=bool)
        excluded = frame.loc[~membership, list(TARGET_JOIN_COLUMNS)].drop_duplicates()
        excluded_rows = sorted(
            "|".join(str(value) for value in row)
            for row in excluded.itertuples(index=False, name=None)
        )
        filter_evidence.append(
            {
                "model_id": model_id,
                "source_path": relative,
                "candidate_row_count": len(frame),
                "matched_target_row_count": int(membership.sum()),
                "excluded_incomplete_target_row_count": int((~membership).sum()),
                "excluded_target_keys_sha256": _sha256_bytes(
                    _canonical_json_bytes({"keys": excluded_rows})
                ),
            }
        )
        frame = frame.loc[membership].copy()
        joined = frame.merge(
            targets.loc[
                :,
                [
                    *TARGET_JOIN_COLUMNS,
                    "bloom_h",
                    "target_risk_chla_h",
                    "ordinal_label",
                ],
            ],
            on=list(TARGET_JOIN_COLUMNS),
            how="inner",
            validate="many_to_one",
        )
        if joined[["bloom_h", "target_risk_chla_h", "ordinal_label"]].isna().any().any():
            raise _error(f"E0-MCAL {model_id} labels are incomplete")
        normalized = pd.DataFrame(
            {
                "model_id": model_id,
                "model_seed": joined["normalized_seed"].astype("int64"),
                "horizon_months": joined["horizon_months"].astype("int64"),
                "source_id": joined["source_id"].astype(str),
                "site_id": joined["site_id"].astype(str),
                "common_origin_id": joined["common_origin_id"].astype(str),
                "origin_year_month": joined["origin_year_month"].astype(str),
                "assignment_role": joined["assignment_role"].astype(str),
                "time_role": joined["time_role"].astype(str),
                "target_year_month": joined["target_year_month"].astype(str),
                "bloom_probability": pd.to_numeric(
                    (
                        joined["raw_score"]
                        if model_id == "M0"
                        else joined["predicted_bloom_probability"]
                    ),
                    errors="raise",
                ),
                "bloom_label": joined["bloom_h"].astype("int8"),
                "ordinal_score": (
                    pd.to_numeric(joined["raw_score"], errors="raise")
                    if model_id in ORDINAL_MODELS
                    else np.nan
                ),
                "ordinal_label": (
                    joined["ordinal_label"].astype("int8")
                    if model_id in ORDINAL_MODELS
                    else np.nan
                ),
                "observed_risk": np.nan,
                "predicted_risk": np.nan,
                "predicted_risk_sigma": np.nan,
            }
        )
        rows.append(normalized)
    authority_paths = (
        ("baseline_manifest", repo_root / "reports/closure_v1/02_models/baselines/manifest.json"),
        ("baseline_lineage", repo_root / "reports/closure_v1/02_models/baselines/lineage_audit.json"),
        ("m0_manifest", repo_root / "reports/closure_v1/02_models/M0/manifest.json"),
        ("m0_lineage", repo_root / "reports/closure_v1/02_models/M0/lineage_audit.json"),
    )
    extra_portable, extra_snapshot = _authority_path_records(
        authority_paths, repo_root=repo_root
    )
    return (
        pd.concat(rows, ignore_index=True),
        [*portable, *extra_portable],
        [*snapshot, *extra_snapshot],
        filter_evidence,
    )


def _anfis_selection_predictions(
    targets: pd.DataFrame,
    *,
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[pd.DataFrame] = []
    portable: list[dict[str, Any]] = []
    snapshot: list[dict[str, Any]] = []
    target_reference = targets.loc[
        targets["target_year_month"].astype(str).between("2019-01", "2020-12"),
        [
            *TARGET_JOIN_COLUMNS,
            "assignment_role",
            "time_role",
            "bloom_h",
            "target_risk_chla_h",
        ],
    ].copy()
    if len(target_reference) != 1_974 or target_reference.duplicated(
        list(TARGET_JOIN_COLUMNS)
    ).any():
        raise _error("E0-MCAL ANFIS selection target universe drifted")
    for model_id in UNCERTAINTY_MODELS:
        for base_seed in REGISTERED_SEEDS:
            path = (
                repo_root
                / f"data/closure_v1/development/anfis_ablation/{model_id}/seed_{base_seed}_selection_predictions.parquet"
            )
            frame, record = _read_parquet_frame(
                path,
                columns=[
                    "model_id",
                    "base_seed",
                    "source_id",
                    "site_id",
                    "common_origin_id",
                    "time_role",
                    "origin_year_month",
                    "target_year_month",
                    "horizon_months",
                    "observed_bloom",
                    "observed_risk",
                    "predicted_bloom_probability",
                    "predicted_risk",
                    "predicted_risk_sigma",
                    "availability_status",
                    "failure_reason",
                ],
                authorized_dvc_pointers=authorized_dvc_pointers,
                repo_root=repo_root,
            )
            _require_exact_text_columns(
                frame,
                (
                    "model_id",
                    "source_id",
                    "site_id",
                    "common_origin_id",
                    "time_role",
                    "origin_year_month",
                    "target_year_month",
                    "availability_status",
                    "failure_reason",
                ),
                context=f"{model_id} selection predictions",
                allow_empty=("failure_reason",),
            )
            frame["base_seed"] = _exact_integer_column(frame, "base_seed")
            frame["horizon_months"] = _exact_integer_column(
                frame, "horizon_months"
            )
            _canonical_months(
                frame["origin_year_month"], context="ANFIS selection origin"
            )
            _canonical_months(
                frame["target_year_month"], context="ANFIS selection target"
            )
            _binary_vector(
                frame["observed_bloom"].to_numpy(),
                context="ANFIS selection observed bloom",
            )
            _probability_vector(
                frame["observed_risk"].to_numpy(),
                context="ANFIS selection observed risk",
            )
            _probability_vector(
                frame["predicted_bloom_probability"].to_numpy(),
                context="ANFIS selection predicted bloom",
            )
            _probability_vector(
                frame["predicted_risk"].to_numpy(),
                context="ANFIS selection predicted risk",
            )
            sigma = _finite_vector(
                frame["predicted_risk_sigma"].to_numpy(),
                context="ANFIS selection predicted sigma",
            )
            if np.any(sigma <= 0.0):
                raise _error("E0-MCAL ANFIS selection sigma is not positive")
            if (
                set(frame["model_id"].tolist()) != {model_id}
                or set(frame["availability_status"].tolist()) != {"success"}
                or not frame["failure_reason"].eq("").all()
            ):
                raise _error(f"E0-MCAL {model_id} selection identity drifted")
            frame = frame.loc[
                frame["target_year_month"].astype(str).between("2019-01", "2020-12")
            ].copy()
            if (
                not frame["base_seed"].eq(base_seed).all()
                or not frame["horizon_months"].isin(HORIZONS).all()
                or len(frame) != len(target_reference)
                or _target_key_set(frame) != _target_key_set(target_reference)
            ):
                raise _error(f"E0-MCAL {model_id} selection seed/horizon drifted")
            joined = frame.merge(
                target_reference,
                on=list(TARGET_JOIN_COLUMNS),
                how="inner",
                validate="one_to_one",
                suffixes=("_selection", "_target"),
            )
            observed_bloom = joined["observed_bloom"].to_numpy(dtype=np.int8)
            target_bloom = joined["bloom_h"].to_numpy(dtype=np.int8)
            observed_risk = joined["observed_risk"].to_numpy(dtype=np.float64)
            target_risk = joined["target_risk_chla_h"].to_numpy(dtype=np.float64)
            if (
                not joined["time_role_selection"].eq(
                    joined["time_role_target"]
                ).all()
                or not np.array_equal(observed_bloom, target_bloom)
                or not np.array_equal(observed_risk, target_risk)
            ):
                raise _error(
                    f"E0-MCAL {model_id} selection labels differ from target authority"
                )
            manifest_path = anfis_training.slot_paths(
                model_id, base_seed, repo_root=repo_root
            ).manifest
            manifest, manifest_record, manifest_snapshot = _json_input(
                manifest_path,
                role=f"{model_id.lower()}_manifest_seed_{base_seed}",
                repo_root=repo_root,
            )
            _validate_anfis_slot_manifest(
                manifest,
                model_id=model_id,
                base_seed=base_seed,
                observed_outputs={"selection_predictions": record},
            )
            rows.append(
                pd.DataFrame(
                    {
                        "model_id": joined["model_id"].astype(str),
                        "model_seed": joined["base_seed"].astype("int64"),
                        "horizon_months": joined["horizon_months"].astype("int64"),
                        "source_id": joined["source_id"].astype(str),
                        "site_id": joined["site_id"].astype(str),
                        "common_origin_id": joined["common_origin_id"].astype(str),
                        "origin_year_month": joined["origin_year_month"].astype(str),
                        "assignment_role": joined["assignment_role"].astype(str),
                        "time_role": joined["time_role_target"].astype(str),
                        "target_year_month": joined["target_year_month"].astype(str),
                        "bloom_probability": joined["predicted_bloom_probability"],
                        "bloom_label": target_bloom,
                        "ordinal_score": np.nan,
                        "ordinal_label": np.nan,
                        "observed_risk": target_risk,
                        "predicted_risk": joined["predicted_risk"],
                        "predicted_risk_sigma": joined["predicted_risk_sigma"],
                    }
                )
            )
            portable.append(_portable_record(record, role=f"{model_id.lower()}_selection_predictions"))
            snapshot.append({"role": f"{model_id.lower()}_selection_predictions", **record})
            portable.append(manifest_record)
            snapshot.append(manifest_snapshot)
            pointer_portable, pointer_snapshot = _authority_path_records(
                (
                    (
                        f"{model_id.lower()}_selection_predictions_pointer_seed_{base_seed}",
                        Path(f"{path}.dvc"),
                    ),
                ),
                repo_root=repo_root,
            )
            portable.extend(pointer_portable)
            snapshot.extend(pointer_snapshot)
    return pd.concat(rows, ignore_index=True), portable, snapshot


def _json_input(
    path: Path, *, role: str, repo_root: Path
) -> tuple[Mapping[str, Any], dict[str, Any], dict[str, Any]]:
    payload, identity = _read_named_bytes(path, repo_root=repo_root)
    value = _load_unique_json_mapping(payload, path=path)
    snapshot = {
        "role": role,
        "path": path.relative_to(repo_root).as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "mode": format(identity.mode, "04o"),
        "nlink": identity.nlink,
        "device": identity.device,
        "inode": identity.inode,
        "mtime_ns": identity.mtime_ns,
        "ctime_ns": identity.ctime_ns,
    }
    return value, _portable_record(snapshot, role=role), snapshot


def _torch_input(
    path: Path,
    *,
    role: str,
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> tuple[Mapping[str, Any], dict[str, Any], dict[str, Any]]:
    payload, identity = _read_scientific_named_bytes(
        path,
        authorized_dvc_pointers=authorized_dvc_pointers,
        repo_root=repo_root,
    )
    torch = anfis_training._require_torch()
    try:
        value = torch.load(io.BytesIO(payload), map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _error(f"E0-MCAL ANFIS artifact cannot be decoded: {path}") from exc
    if not isinstance(value, Mapping):
        raise _error(f"E0-MCAL ANFIS artifact is not one mapping: {path}")
    snapshot = {
        "role": role,
        "path": path.relative_to(repo_root).as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "mode": format(identity.mode, "04o"),
        "nlink": identity.nlink,
        "device": identity.device,
        "inode": identity.inode,
        "mtime_ns": identity.mtime_ns,
        "ctime_ns": identity.ctime_ns,
    }
    return value, _portable_record(snapshot, role=role), snapshot


def _equal_state_dicts(left: Any, right: Any) -> bool:
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return False
    if list(left) != list(right):
        return False
    torch = anfis_training._require_torch()
    return all(
        torch.is_tensor(left[key])
        and torch.is_tensor(right[key])
        and torch.equal(left[key], right[key])
        for key in left
    )


def _standardizer_from_payload(
    payload: Mapping[str, Any], *, model_id: str, base_seed: int
) -> anfis_training.RawStandardizer:
    columns = payload.get("columns")
    if (
        payload.get("version") != "closure_mask_aware_training_standardization_v1"
        or payload.get("fit_role") != "training"
        or payload.get("model_id") != model_id
        or payload.get("base_seed") != base_seed
        or payload.get("input_columns") != list(anfis_training.input_columns(model_id))
        or not isinstance(columns, list)
        or len(columns) != len(anfis_training.RAW_STANDARDIZATION_COLUMNS)
    ):
        raise _error("E0-MCAL ANFIS preprocessor identity drifted")
    expected_columns = list(anfis_training.RAW_STANDARDIZATION_COLUMNS)
    if [record.get("column") for record in columns if isinstance(record, Mapping)] != expected_columns:
        raise _error("E0-MCAL ANFIS preprocessor columns drifted")
    try:
        counts = np.asarray([record["observed_count"] for record in columns], dtype=np.int64)
        means = np.asarray([record["mean"] for record in columns], dtype=np.float64)
        deviations = np.asarray(
            [record["standard_deviation"] for record in columns], dtype=np.float64
        )
        epsilon = float(payload["epsilon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _error("E0-MCAL ANFIS preprocessor numeric payload drifted") from exc
    if (
        any(type(record.get("observed_count")) is not int for record in columns)
        or not np.isfinite(means).all()
        or not np.isfinite(deviations).all()
        or np.any(deviations <= 0.0)
        or epsilon != anfis_training.PREPROCESSOR_EPSILON
    ):
        raise _error("E0-MCAL ANFIS preprocessor numeric contract drifted")
    standardizer = anfis_training.RawStandardizer(
        columns=tuple(expected_columns),
        counts=counts,
        means=means,
        standard_deviations=deviations,
        epsilon=epsilon,
    )
    anfis_training.validate_physical_standardizer(standardizer)
    return standardizer


def _calibration_bundle_from_sequence(
    targets: pd.DataFrame,
    sequence: pd.DataFrame,
    *,
    model_id: str,
    standardizer: anfis_training.RawStandardizer,
) -> anfis_training.TrainingBundle:
    selected_targets = targets.loc[
        targets["time_role"].astype(str).eq("calibration_threshold")
        & targets["target_year_month"].astype(str).between("2021-01", "2021-12")
    ].copy()
    if (
        len(selected_targets) != 672
        or selected_targets["common_origin_id"].nunique() != 224
        or not selected_targets.groupby("common_origin_id")["horizon_months"]
        .agg(lambda values: set(int(value) for value in values))
        .eq(set(HORIZONS))
        .all()
    ):
        raise _error("E0-MCAL 2021 exact ANFIS target universe drifted")
    origins = (
        selected_targets.loc[
            :,
            [
                "source_id",
                "site_id",
                "common_origin_id",
                "assignment_role",
                "time_role",
                "origin_year_month",
            ],
        ]
        .drop_duplicates()
        .sort_values(
            ["source_id", "site_id", "origin_year_month", "common_origin_id"],
            kind="mergesort",
        )
        .reset_index(drop=True)
    )
    if len(origins) != 224:
        raise _error("E0-MCAL 2021 ANFIS origin denominator drifted")
    sequence_index = sequence.set_index("common_origin_id", verify_integrity=True)
    if not set(origins["common_origin_id"]).issubset(sequence_index.index):
        raise _error("E0-MCAL 2021 ANFIS sequences omit complete target origins")
    selected_sequence = sequence_index.loc[origins["common_origin_id"]].reset_index()
    for column in ("source_id", "site_id", "time_role", "origin_year_month"):
        if selected_sequence[column].astype(str).tolist() != origins[column].astype(str).tolist():
            raise _error("E0-MCAL 2021 ANFIS sequence/target identity drifted")
    ordered_targets = selected_targets.set_index(
        ["common_origin_id", "horizon_months"], verify_integrity=True
    )
    bloom = np.empty((len(origins), len(HORIZONS)), dtype=np.float32)
    risk = np.empty_like(bloom)
    for row_index, common_origin_id in enumerate(origins["common_origin_id"]):
        for horizon_index, horizon in enumerate(HORIZONS):
            record = ordered_targets.loc[(common_origin_id, horizon)]
            bloom[row_index, horizon_index] = float(record["bloom_h"])
            risk[row_index, horizon_index] = float(record["target_risk_chla_h"])
    if not np.isin(bloom, (0.0, 1.0)).all() or not np.isfinite(risk).all() or np.any(
        (risk < 0.0) | (risk > 1.0)
    ):
        raise _error("E0-MCAL 2021 ANFIS targets drifted")
    raw_tensor = anfis_training._tensor_from_sequence(selected_sequence, model_id=model_id)
    tensor = anfis_training.apply_mask_aware_standardizer(raw_tensor, standardizer)
    return anfis_training.TrainingBundle(origins, tensor, bloom, risk)


def _mcal_sequence_frame(
    *,
    model_id: str,
    base_seed: int,
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    sequence_path, pointer_path, _, manifest_path = anfis_training.sequence_paths(
        model_id, base_seed, repo_root=repo_root
    )
    columns = [
        *anfis_training.SEQUENCE_IDENTITY_COLUMNS,
        *anfis_training.input_columns(model_id),
    ]
    frame, sequence_record = _read_parquet_frame(
        sequence_path,
        columns=columns,
        authorized_dvc_pointers=authorized_dvc_pointers,
        repo_root=repo_root,
    )
    _require_exact_text_columns(
        frame,
        (
            "model_id",
            "source_id",
            "site_id",
            "common_origin_id",
            "assignment_role",
            "time_role",
            "origin_year_month",
            "sequence_status",
            "failure_reason",
            "sequence_version",
        ),
        context=f"{model_id} sequence",
        allow_empty=("failure_reason",),
    )
    if (
        len(frame) != 9_732
        or frame["common_origin_id"].nunique() != 9_732
        or set(frame["sequence_status"].astype(str)) != {"success"}
        or not frame["failure_reason"].eq("").all()
        or set(frame["model_id"].astype(str)) != {model_id}
        or set(frame["sequence_version"].astype(str))
        != {anfis_training.SEQUENCE_VERSION}
        or set(frame["assignment_role"].astype(str)) != {"development"}
        or set(frame["source_id"].astype(str)) != {"wqp"}
        or frame.duplicated(["source_id", "site_id", "origin_year_month"]).any()
    ):
        raise _error("E0-MCAL ANFIS sequence scientific identity drifted")
    if frame["time_role"].value_counts().to_dict() != {
        "training": anfis_training.EXPECTED_SEQUENCE_TRAINING_ORIGINS,
        "model_selection": anfis_training.EXPECTED_SEQUENCE_SELECTION_ORIGINS,
        "calibration_threshold": anfis_training.EXPECTED_SEQUENCE_CALIBRATION_ORIGINS,
    }:
        raise _error("E0-MCAL ANFIS sequence role counts drifted")
    if model_id == "A0":
        if frame["base_seed"].notna().any() or frame["upstream_state_seed"].notna().any():
            raise _error("E0-MCAL A0 sequence unexpectedly carries a seed")
    elif not frame["base_seed"].eq(base_seed).all() or not frame[
        "upstream_state_seed"
    ].eq(base_seed).all():
        raise _error("E0-MCAL A1 sequence seed binding drifted")
    ordered = frame.sort_values(
        ["source_id", "site_id", "origin_year_month", "common_origin_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    if not frame.reset_index(drop=True).equals(ordered):
        raise _error("E0-MCAL ANFIS sequence canonical order drifted")
    extra_portable, extra_snapshot = _authority_path_records(
        (
            (f"{model_id.lower()}_sequence_pointer", pointer_path),
            (f"{model_id.lower()}_sequence_manifest", manifest_path),
        ),
        repo_root=repo_root,
    )
    role = f"{model_id.lower()}_sequence"
    return (
        frame,
        [_portable_record(sequence_record, role=role), *extra_portable],
        [{"role": role, **sequence_record}, *extra_snapshot],
    )


def _anfis_calibration_predictions(
    targets: pd.DataFrame,
    *,
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    """Infer exact 2021 A0/A1 rows from published models; never refit or use state."""
    rows: list[pd.DataFrame] = []
    portable: list[dict[str, Any]] = []
    snapshot: list[dict[str, Any]] = []
    sequence_cache: dict[tuple[str, int], tuple[pd.DataFrame, list[dict[str, Any]]]] = {}
    try:
        for model_id in UNCERTAINTY_MODELS:
            for base_seed in REGISTERED_SEEDS:
                sequence_key = (model_id, 0 if model_id == "A0" else base_seed)
                if sequence_key not in sequence_cache:
                    sequence, sequence_portable, sequence_snapshot = _mcal_sequence_frame(
                        model_id=model_id,
                        base_seed=base_seed,
                        authorized_dvc_pointers=authorized_dvc_pointers,
                        repo_root=repo_root,
                    )
                    sequence_cache[sequence_key] = (sequence, sequence_snapshot)
                    portable.extend(sequence_portable)
                    snapshot.extend(sequence_snapshot)
                sequence, _ = sequence_cache[sequence_key]
                paths = anfis_training.slot_paths(
                    model_id, base_seed, repo_root=repo_root
                )
                model_payload, model_record, model_snapshot = _torch_input(
                    paths.model,
                    role=f"{model_id.lower()}_model_seed_{base_seed}",
                    authorized_dvc_pointers=authorized_dvc_pointers,
                    repo_root=repo_root,
                )
                checkpoint_payload, checkpoint_record, checkpoint_snapshot = _torch_input(
                    paths.checkpoint,
                    role=f"{model_id.lower()}_checkpoint_seed_{base_seed}",
                    authorized_dvc_pointers=authorized_dvc_pointers,
                    repo_root=repo_root,
                )
                preprocessor_payload, preprocessor_record, preprocessor_snapshot = _json_input(
                    paths.preprocessor,
                    role=f"{model_id.lower()}_preprocessor_seed_{base_seed}",
                    repo_root=repo_root,
                )
                manifest_payload, manifest_record, manifest_snapshot = _json_input(
                    paths.manifest,
                    role=f"{model_id.lower()}_manifest_seed_{base_seed}",
                    repo_root=repo_root,
                )
                portable.extend(
                    [model_record, checkpoint_record, preprocessor_record, manifest_record]
                )
                snapshot.extend(
                    [
                        model_snapshot,
                        checkpoint_snapshot,
                        preprocessor_snapshot,
                        manifest_snapshot,
                    ]
                )
                _validate_anfis_slot_manifest(
                    manifest_payload,
                    model_id=model_id,
                    base_seed=base_seed,
                    observed_outputs={
                        "model": model_record,
                        "checkpoint": checkpoint_record,
                        "preprocessor": preprocessor_record,
                    },
                )
                required_identity = {
                    "model_version": anfis_training.MODEL_VERSION,
                    "experiment_id": "closure_v1",
                    "surface_id": anfis_training.SURFACE_ID,
                    "gate": "E0-MT",
                    "model_id": model_id,
                    "base_seed": base_seed,
                    "device": anfis_training.LOCKED_DEVICE,
                    "config": anfis_training._model_config(model_id),
                }
                for payload, role in (
                    (model_payload, "final_restored_model"),
                    (checkpoint_payload, "raw_best_checkpoint"),
                ):
                    if any(payload.get(key) != value for key, value in required_identity.items()) or payload.get(
                        "artifact_role"
                    ) != role:
                        raise _error("E0-MCAL ANFIS model/checkpoint identity drifted")
                if not _equal_state_dicts(
                    model_payload.get("model_state_dict"),
                    checkpoint_payload.get("model_state_dict"),
                ):
                    raise _error("E0-MCAL ANFIS model/checkpoint states differ")
                bloom_priors = _probability_vector(
                    cast(Sequence[float], model_payload.get("bloom_training_priors")),
                    context="ANFIS bloom priors",
                )
                risk_priors = _probability_vector(
                    cast(Sequence[float], model_payload.get("risk_training_priors")),
                    context="ANFIS risk priors",
                )
                if bloom_priors.shape != (3,) or risk_priors.shape != (3,):
                    raise _error("E0-MCAL ANFIS training priors drifted")
                standardizer = _standardizer_from_payload(
                    preprocessor_payload, model_id=model_id, base_seed=base_seed
                )
                bundle = _calibration_bundle_from_sequence(
                    targets, sequence, model_id=model_id, standardizer=standardizer
                )
                torch = anfis_training._require_torch()
                device = torch.device("cpu")
                model = anfis_training.make_anfis_ablation_model(
                    input_dimension=bundle.x.shape[2],
                    bloom_priors=bloom_priors,
                    risk_priors=risk_priors,
                ).to(device)
                model.load_state_dict(model_payload["model_state_dict"], strict=True)
                bloom_probability, risk_mu, risk_logvar = anfis_training._predict_arrays(
                    model, bundle, device=device
                )
                predicted = anfis_training._selection_prediction_frame(
                    bundle,
                    model_id=model_id,
                    base_seed=base_seed,
                    bloom_probability=bloom_probability,
                    risk_mu=risk_mu,
                    risk_logvar=risk_logvar,
                )
                if len(predicted) != 672 or set(predicted["time_role"].astype(str)) != {
                    "calibration_threshold"
                }:
                    raise _error("E0-MCAL ANFIS 2021 inference denominator drifted")
                rows.append(
                    pd.DataFrame(
                        {
                            "model_id": predicted["model_id"].astype(str),
                            "model_seed": predicted["base_seed"].astype("int64"),
                            "horizon_months": predicted["horizon_months"].astype("int64"),
                            "source_id": predicted["source_id"].astype(str),
                            "site_id": predicted["site_id"].astype(str),
                            "common_origin_id": predicted["common_origin_id"].astype(str),
                            "origin_year_month": predicted["origin_year_month"].astype(str),
                            "assignment_role": "development",
                            "time_role": predicted["time_role"].astype(str),
                            "target_year_month": predicted["target_year_month"].astype(str),
                            "bloom_probability": predicted[
                                "predicted_bloom_probability"
                            ],
                            "bloom_label": predicted["observed_bloom"].astype("int8"),
                            "ordinal_score": np.nan,
                            "ordinal_label": np.nan,
                            "observed_risk": predicted["observed_risk"],
                            "predicted_risk": predicted["predicted_risk"],
                            "predicted_risk_sigma": predicted["predicted_risk_sigma"],
                        }
                    )
                )
    except anfis_training.AnfisAblationTrainingError as exc:
        raise _error(f"E0-MCAL ANFIS 2021 inference failed: {exc}") from exc
    return pd.concat(rows, ignore_index=True), portable, snapshot


def _deduplicate_records(
    records: Sequence[Mapping[str, Any]], *, portable: bool
) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    for raw in records:
        record = dict(raw)
        path = record.get("path")
        if not isinstance(path, str) or not path or path in by_path and {
            key: value for key, value in record.items() if key != "role"
        } != {
            key: value for key, value in by_path[path].items() if key != "role"
        }:
            raise _error("E0-MCAL scientific input records are duplicated or inconsistent")
        by_path.setdefault(path, record)
    ordered = [by_path[path] for path in sorted(by_path)]
    if portable:
        return [
            {
                "role": str(record["role"]),
                "path": str(record["path"]),
                "bytes": int(record["bytes"]),
                "sha256": str(record["sha256"]),
            }
            for record in ordered
        ]
    return ordered


def _validate_authority_input_inventory(
    authority: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> None:
    inventory = authority.get("scientific_input_inventory")
    if inventory is None:
        return
    if not isinstance(inventory, Mapping):
        raise _error("E0-MCAL scientific input inventory is malformed")
    raw_required = inventory.get("calibration_required_inputs")
    required_count = inventory.get("calibration_required_input_count")
    required_digest = inventory.get("calibration_required_inputs_sha256")
    if (
        not isinstance(raw_required, list)
        or type(required_count) is not int
        or required_count != 97
        or not isinstance(required_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", required_digest) is None
    ):
        raise _error("E0-MCAL calibration input partition is absent or malformed")

    def canonical(records_value: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in records_value:
            if (
                not isinstance(raw, Mapping)
                or set(raw) != {"role", "path", "bytes", "sha256"}
                or not isinstance(raw.get("role"), str)
                or not cast(str, raw["role"])
                or not isinstance(raw.get("path"), str)
                or not cast(str, raw["path"])
                or cast(str, raw["path"]) in seen
                or type(raw.get("bytes")) is not int
                or cast(int, raw["bytes"]) <= 0
                or not isinstance(raw.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", cast(str, raw["sha256"])) is None
            ):
                raise _error("E0-MCAL calibration input partition record drifted")
            seen.add(cast(str, raw["path"]))
            result.append(
                {
                    "role": cast(str, raw["role"]),
                    "path": cast(str, raw["path"]),
                    "bytes": cast(int, raw["bytes"]),
                    "sha256": cast(str, raw["sha256"]),
                }
            )
        if [record["path"] for record in result] != sorted(seen):
            raise _error("E0-MCAL calibration input partition order drifted")
        return result

    expected = canonical(cast(Sequence[Mapping[str, Any]], raw_required))
    observed = canonical(records)
    digest = hashlib.sha256(
        json.dumps(
            expected,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if (
        len(expected) != 97
        or len(observed) != 97
        or digest != required_digest
        or observed != expected
    ):
        raise _error("E0-MCAL calibration input partition differs from P authority")


def _load_final_calibration_inputs(
    *, authorized_dvc_pointers: Sequence[Path], repo_root: Path
) -> dict[str, Any]:
    """Load the closed development input surface after the effective P gate."""
    runtime = calibration.load_and_validate_final_calibration_runtime(repo_root=repo_root)
    targets, target_records, target_snapshot, target_scan_audit = _target_projection(
        authorized_dvc_pointers=authorized_dvc_pointers,
        repo_root=repo_root,
    )
    baseline, baseline_records, baseline_snapshot, filter_evidence = _baseline_predictions(
        targets,
        authorized_dvc_pointers=authorized_dvc_pointers,
        repo_root=repo_root,
    )
    selection, selection_records, selection_snapshot = _anfis_selection_predictions(
        targets,
        authorized_dvc_pointers=authorized_dvc_pointers,
        repo_root=repo_root,
    )
    inferred, inference_records, inference_snapshot = _anfis_calibration_predictions(
        targets,
        authorized_dvc_pointers=authorized_dvc_pointers,
        repo_root=repo_root,
    )
    authority_records, authority_snapshot = _authority_path_records(
        (
            ("models_dvc", repo_root / "models.dvc"),
        ),
        repo_root=repo_root,
    )
    predictions = pd.concat([baseline, selection, inferred], ignore_index=True)
    records = _deduplicate_records(
        [
            *target_records,
            *baseline_records,
            *selection_records,
            *inference_records,
            *authority_records,
        ],
        portable=True,
    )
    snapshot = _deduplicate_records(
        [
            *target_snapshot,
            *baseline_snapshot,
            *selection_snapshot,
            *inference_snapshot,
            *authority_snapshot,
        ],
        portable=False,
    )
    matrix = runtime.get("model_matrix")
    if not isinstance(matrix, Mapping) or not isinstance(matrix.get("records"), list):
        raise _error("E0-MCAL effective model matrix is absent")
    return {
        "predictions": predictions,
        "target_universe": targets.copy(),
        "model_availability": [dict(record) for record in matrix["records"]],
        "input_records": records,
        "input_snapshot": snapshot,
        "input_filter_evidence": [
            {"role": "target_predicate_scan", **target_scan_audit},
            *filter_evidence,
        ],
    }


def _revalidate_final_calibration_input_snapshot(
    snapshot: Sequence[Mapping[str, Any]],
    *,
    authorized_dvc_pointers: Sequence[Path],
    repo_root: Path,
) -> None:
    if not snapshot:
        raise _error("E0-MCAL scientific input snapshot is empty")
    seen: set[str] = set()
    for raw in snapshot:
        record = dict(raw)
        path = record.get("path")
        if not isinstance(path, str) or path in seen:
            raise _error("E0-MCAL scientific input snapshot path drifted")
        seen.add(path)
        payload, identity = _read_scientific_named_bytes(
            repo_root / path,
            authorized_dvc_pointers=authorized_dvc_pointers,
            repo_root=repo_root,
        )
        observed = {
            "path": path,
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
            "mode": format(identity.mode, "04o"),
            "nlink": identity.nlink,
            "device": identity.device,
            "inode": identity.inode,
            "mtime_ns": identity.mtime_ns,
            "ctime_ns": identity.ctime_ns,
        }
        expected = {key: record.get(key) for key in observed}
        if observed != expected:
            raise _error(f"E0-MCAL scientific input changed during execution: {path}")


def _require_calibration_namespace_absent(*, repo_root: Path) -> None:
    paths = [
        *(repo_root / path.relative_to(PROJECT_ROOT) for path in OUTPUT_PATHS),
        repo_root / GUARD_PATH.relative_to(PROJECT_ROOT),
    ]
    occupied = [path.relative_to(repo_root).as_posix() for path in paths if os.path.lexists(path)]
    if occupied:
        raise _error(
            "E0-MCAL calibration one-shot namespace is already occupied: "
            + ", ".join(occupied)
        )


def _load_mcal_development_runtime(
    *, repo_root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the P-bound historical runtime without its obsolete Git gate."""

    config_path = repo_root / "configs/closure_v1/development_runtime.yaml"
    schema_path = repo_root / "configs/closure_v1/development_runtime.schema.json"
    config_payload, _ = _read_named_bytes(config_path, repo_root=repo_root)
    schema_payload, _ = _read_named_bytes(schema_path, repo_root=repo_root)
    try:
        raw_runtime = yaml.safe_load(config_payload)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise _error("E0-MCAL historical development runtime is malformed") from exc
    if not isinstance(raw_runtime, Mapping):
        raise _error("E0-MCAL historical development runtime is not one mapping")
    runtime = dict(raw_runtime)
    schema = dict(_load_unique_json_mapping(schema_payload, path=schema_path))
    audit = validate_development_runtime(
        runtime,
        schema,
        cross_validate_locked=False,
        validate_repository=False,
    )
    audit.update(
        {
            "config_path": config_path.relative_to(repo_root).as_posix(),
            "config_sha256": _sha256_bytes(config_payload),
            "schema_path": schema_path.relative_to(repo_root).as_posix(),
            "schema_sha256": _sha256_bytes(schema_payload),
            "status": runtime.get("status"),
            "validation_scope": (
                "exact_schema_contract_under_effective_e0_mcal_authority"
            ),
        }
    )
    return runtime, audit


def _configure_calibration_cpu_policy(*, repo_root: Path) -> dict[str, Any]:
    runtime, audit = _load_mcal_development_runtime(repo_root=repo_root)
    try:
        observed = configure_torch_cpu_execution_policy(runtime)
    except Exception as exc:
        raise _error(f"E0-MCAL CPU execution policy failed: {exc}") from exc
    return {
        "torch_cpu_execution_policy": observed,
        "development_runtime_schema_version": runtime.get("schema_version"),
        "development_runtime_audit_sha256": _sha256_bytes(
            _canonical_json_bytes(audit)
        ),
        "threadpool_limit": 1,
    }


def check_only(*, repo_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = calibration.require_final_calibration_authority(
        verify_remote=True, repo_root=repo_root
    )
    namespace = calibration.require_final_calibration_run_namespace(
        runner="calibration", repo_root=repo_root
    )
    return {
        "status": "ready_to_calibrate",
        "gate": calibration.PATCH_GATE,
        "authority": authority,
        "namespace": namespace,
        "output_count": len(OUTPUT_PATHS),
        "writes_performed": False,
        "calibration_run": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "holdout_accessed": False,
        "post_2021_rows_accessed": False,
        "future_outcomes_accessed": False,
    }


def execute_one_shot(*, repo_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Execute the closed calibration transaction after P-E0-MCAL is effective."""
    authority = calibration.require_final_calibration_authority(
        verify_remote=True, repo_root=repo_root
    )
    namespace = calibration.require_final_calibration_run_namespace(
        runner="calibration", repo_root=repo_root
    )
    authorized_dvc_pointers = _authorized_scientific_dvc_pointers(authority)
    execution_policy = _configure_calibration_cpu_policy(repo_root=repo_root)
    with threadpool_limits(limits=1):
        loaded = _load_final_calibration_inputs(
            authorized_dvc_pointers=authorized_dvc_pointers,
            repo_root=repo_root,
        )
        input_records = cast(Sequence[Mapping[str, Any]], loaded["input_records"])
        input_snapshot = cast(Sequence[Mapping[str, Any]], loaded["input_snapshot"])
        _validate_authority_input_inventory(authority, input_records)
        payloads, manifest = build_final_calibration_bundle(
            authority=authority,
            predictions=cast(pd.DataFrame, loaded["predictions"]),
            target_universe=cast(pd.DataFrame, loaded["target_universe"]),
            model_availability=cast(
                Sequence[Mapping[str, Any]], loaded["model_availability"]
            ),
            input_records=input_records,
            input_filter_evidence=cast(
                Sequence[Mapping[str, Any]], loaded["input_filter_evidence"]
            ),
            execution_policy=execution_policy,
            repo_root=repo_root,
        )
    _revalidate_final_calibration_input_snapshot(
        input_snapshot,
        authorized_dvc_pointers=authorized_dvc_pointers,
        repo_root=repo_root,
    )
    if calibration.require_final_calibration_authority(
        verify_remote=True, repo_root=repo_root
    ) != authority:
        raise _error("E0-MCAL authority changed before calibration publication")
    records: list[dict[str, Any]] = []
    guard = repo_root / GUARD_PATH.relative_to(PROJECT_ROOT)

    def revalidate_post_release() -> None:
        _revalidate_final_calibration_input_snapshot(
            input_snapshot,
            authorized_dvc_pointers=authorized_dvc_pointers,
            repo_root=repo_root,
        )
        if calibration.require_final_calibration_authority(
            verify_remote=True, repo_root=repo_root
        ) != authority:
            raise _error(
                "E0-MCAL authority changed after calibration guard release"
            )

    with OrderedBundleTransaction(guard_path=guard, repo_root=repo_root) as transaction:
        for path, payload in payloads:
            records.append(transaction.publish(path, payload))
        _revalidate_final_calibration_input_snapshot(
            input_snapshot,
            authorized_dvc_pointers=authorized_dvc_pointers,
            repo_root=repo_root,
        )
        if calibration.require_final_calibration_authority(
            verify_remote=True, repo_root=repo_root
        ) != authority:
            raise _error("E0-MCAL authority changed during calibration publication")
        transaction.commit(post_release_validators=(revalidate_post_release,))
    return {
        "status": "completed_unpublished",
        "gate": calibration.PATCH_GATE,
        "output_count": 6,
        "records": records,
        "manifest": manifest,
        "namespace": namespace,
        "calibration_run": True,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "holdout_accessed": False,
        "post_2021_rows_accessed": False,
        "future_outcomes_accessed": False,
    }


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
