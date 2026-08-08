"""Fail-closed E0-MT authority for A0/A1 development-only training."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

import yaml
from yaml.resolver import BaseResolver

from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_CONFIG = Path(
    "configs/closure_v1/anfis_ablation_training_development_runtime.yaml"
)
DEFAULT_RUNTIME_PATH = DEFAULT_RUNTIME_CONFIG
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/anfis_ablation_training_development_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/anfis_ablation_training_development_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "anfis_ablation_training_development_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_anfis_ablation_training_development_patch/lock_bundle.guard"
)

BASE_COMMIT = "e22fd44d8a1e13c5587237d9f7a38856ae262864"
SEQUENCE_PATCH_HEAD = "0847a948e47cb6b9bffa9d1551d1c28164dfe3f1"
SEQUENCE_LOCK_HEAD = "c50bb1bc3e69df817a87522c61daf13cfbda9d10"
REGISTERED_SEEDS = (1729, 20_260_612, 20_260_613, 20_260_614, 314_159)
ORDERED_SLOTS = tuple((model, seed) for seed in REGISTERED_SEEDS for model in ("A0", "A1"))

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): "anfis_ablation_training_patch_lock_schema",
    DEFAULT_RUNTIME_CONFIG.as_posix(): "anfis_ablation_training_runtime",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_TRAINING_DEVELOPMENT_PATCH_1.md": "anfis_ablation_training_protocol",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": "anfis_ablation_model_bundle_auditor",
    "src/experiments/closure_anfis_ablation_training_development_patch.py": "anfis_ablation_training_validator",
    "src/experiments/lock_closure_anfis_ablation_training_development_patch.py": "anfis_ablation_training_locker",
    "src/experiments/train_closure_anfis_ablation.py": "anfis_ablation_trainer",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": "anfis_ablation_model_bundle_auditor_tests",
    "tests/test_closure_anfis_ablation_training_development_patch.py": "anfis_ablation_training_validator_tests",
    "tests/test_train_closure_anfis_ablation.py": "anfis_ablation_trainer_tests",
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/python", "-m", "pytest", "-q",
    "tests/test_closure_anfis_ablation_training_development_patch.py",
    "tests/test_train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
)
FOCUSED_TEST_COUNT = 74
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")

UNPUBLISHED_AUTHORIZATIONS = {
    "a0_development_fit_authorized": False,
    "a1_development_fit_authorized": False,
    "target_access_through_2020_authorized": False,
    "selection_diagnostics_authorized": False,
    "calibration_authorized": False,
    "calibration_target_access_authorized": False,
    "final_e7_metrics_authorized": False,
    "rollout_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "dvc_commands_authorized": False,
    "scientific_network_authorized": False,
    "outcome_access_authorized": False,
    "future_outcomes_accessed": False,
    "batch_slot_execution_authorized": False,
    "effective_in_payload": False,
    "publication_required": True,
}
LOCK_SEALS = {
    "target_access_end": "2020-12",
    "calibration_2021_closed": True,
    "holdout_and_post_2021_closed": True,
    "add_last_forbidden": True,
    "ten_slots_individual_only": True,
    "dvc_absent": True,
    "outcomes_absent": True,
    "manifest_written_last": True,
}
LOCKER_PATH = Path(
    "src/experiments/lock_closure_anfis_ablation_training_development_patch.py"
)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
EXPECTED_RUNTIME_SECTION_SHA256 = {
    "authority": "59aa0e0c25858c36ec7095abcf6cf0d9bf60597f36bf881190e615550cd0ecd2",
    "patch_scope": "59e56adc0247b7aed943bdc8ec16ff2e03bbbd7f149867c5dfc2540351647e88",
    "roles": "46953d8d2a6aff8cd38bad7170d6c9e2c96f4cc8efe3f93ad710d34c4ec17b2c",
    "targets": "02703ac872c63c2180b2c8c9b2795d6bfb7d8caff0c2deba8de4fdee3121dddf",
    "inputs": "4f99b4e5cf6cc0b774d60460ca3ab98ad3bce8fbaaffc3e6bc7bce3284413844",
    "preprocessing": "09159927fbb59ebb342813498d5da9407c09383ed9f3cfb31bd6079724b36814",
    "model": "90e6eb28ae0b532f4a53663a1957f4d355f30d55f41fe5ed4dc0a2eb079b17c8",
    "slots": "880397dc7c1938e0e2fb0beb80e0448bc2a426e328e4733c62d8542b0d13822c",
    "outputs": "758eda635c8fb633072befbb31fd8c40bf49322d5230bebe1e2ed6667c880be8",
    "authorizations": "d123e51a4c4ea2c35b9496f863a6c196137a96ccc6356e5fe5797f9f9b5937bf",
    "seals": "9a219457bf190a5c666825d5d2bc4f45fa00cfd0fb5131174d51a11195091c3b",
    "verification": "befa0e4c93d49b07ea51b252304cd5ce8f6a640d07f1f38ee8ef587ae45d6e8f",
}
EXPECTED_PHYSICAL_INPUTS_SHA256 = (
    "ebf054caacee9b73b61de4ad45f8bcf62e7800325bee8c40c88c3bed6010de60"
)


class AnfisAblationTrainingDevelopmentPatchError(RuntimeError):
    """Raised when E0-MT authority or progression is not exact."""


@dataclass
class _OwnedGuard:
    path: Path
    lexical_parent: Path
    name: str
    file_descriptor: int
    parent_descriptor: int
    device: int
    inode: int
    parent_device: int
    parent_inode: int
    closed: bool = False


@dataclass
class _OwnedOutput:
    path: Path
    lexical_parent: Path
    name: str
    parent_descriptor: int
    device: int
    inode: int
    parent_device: int
    parent_inode: int
    closed: bool = False


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
E0_M_PATHS = (
    "reports/closure_v1/00_protocol/model_lock.yaml",
    "reports/closure_v1/00_protocol/calibration_lock.yaml",
    "reports/closure_v1/00_protocol/hypothesis_registry.csv",
    "reports/closure_v1/00_protocol/locked_batch_command.txt",
)
OUTCOME_ACCESS_LOG = "reports/closure_v1/00_protocol/outcome_access_log.jsonl"


def _root(repo_root: Path | None = None) -> Path:
    return PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()


def _relative_path(path: Path, repo_root: Path) -> Path:
    candidate = path if not path.is_absolute() else path.relative_to(repo_root)
    if candidate.is_absolute() or not candidate.parts or any(
        part in {"", ".", ".."} for part in candidate.parts
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"Non-canonical repository path: {path}"
        )
    return candidate


def _read_regular_bytes(path: Path, *, repo_root: Path | None = None) -> bytes:
    """Read a repository file through an anchored no-follow descriptor walk."""
    root = _root(repo_root)
    relative = _relative_path(path, root)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(root, directory_flags)
    file_descriptor: int | None = None
    try:
        for component in relative.parts[:-1]:
            child = os.open(component, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        file_flags |= getattr(os, "O_NOFOLLOW", 0)
        file_descriptor = os.open(relative.name, file_flags, dir_fd=descriptor)
        before = os.fstat(file_descriptor)
        named_before = os.stat(relative.name, dir_fd=descriptor, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(named_before.st_mode)
            or (before.st_dev, before.st_ino) != (named_before.st_dev, named_before.st_ino)
        ):
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"Input is not one stable regular file: {relative.as_posix()}"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(file_descriptor)
        named_after = os.stat(relative.name, dir_fd=descriptor, follow_symlinks=False)
        identity_before = (
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns
        )
        identity_after = (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns
        )
        named_identity = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if identity_before != identity_after or identity_after != named_identity:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"Input changed while it was read: {relative.as_posix()}"
            )
        return b"".join(chunks)
    except (FileNotFoundError, NotADirectoryError, OSError) as exc:
        if isinstance(exc, AnfisAblationTrainingDevelopmentPatchError):
            raise
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"Required regular input is unavailable: {relative.as_posix()}"
        ) from exc
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        os.close(descriptor)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"Duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _load_json(path: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    try:
        value = json.loads(
            _read_regular_bytes(path, repo_root=repo_root).decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"Invalid JSON document: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise AnfisAblationTrainingDevelopmentPatchError(f"JSON root is not an object: {path}")
    return value


class _UniqueSafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueSafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"Duplicate YAML key: {key!r}"
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueSafeLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _load_yaml(path: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    try:
        value = yaml.load(
            _read_regular_bytes(path, repo_root=repo_root).decode("utf-8"),
            Loader=_UniqueSafeLoader,
        )
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"Invalid YAML document: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise AnfisAblationTrainingDevelopmentPatchError(f"YAML root is not a mapping: {path}")
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_record(
    path: Path, *, role: str | None = None, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    relative = _relative_path(path, root)
    payload = _read_regular_bytes(relative, repo_root=root)
    record: dict[str, Any] = {
        "path": relative.as_posix(), "bytes": len(payload), "sha256": _sha256_bytes(payload)
    }
    if role is not None:
        record["role"] = role
    return record


def _digest_records(records: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_bytes(_canonical_json([dict(record) for record in records]))


def _git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=repo_root, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"Git command failed: git {' '.join(arguments)}: {result.stderr.strip()}"
        )
    return result.stdout


def _git_head(repo_root: Path, ref: str = "HEAD") -> str:
    value = _git(repo_root, "rev-parse", "--verify", ref).strip()
    if SHA1_RE.fullmatch(value) is None:
        raise AnfisAblationTrainingDevelopmentPatchError(f"Invalid Git ref: {ref}")
    return value


def _git_parent(repo_root: Path, head: str) -> str:
    return _git_head(repo_root, f"{head}^")


def _live_remote_main_head(repo_root: Path) -> str:
    output = _git(repo_root, "ls-remote", "origin", "refs/heads/main")
    rows = [line.split() for line in output.splitlines() if line.strip()]
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != "refs/heads/main":
        raise AnfisAblationTrainingDevelopmentPatchError(
            "Live origin main did not resolve to one exact ref"
        )
    head = rows[0][0]
    if SHA1_RE.fullmatch(head) is None:
        raise AnfisAblationTrainingDevelopmentPatchError("Live origin main hash is invalid")
    return head


def _git_scope(repo_root: Path, parent: str, head: str) -> dict[str, Any]:
    lines = [line for line in _git(repo_root, "diff", "--name-status", "--no-renames", parent, head).splitlines() if line]
    paths: list[str] = []
    counts = {"A": 0, "M": 0, "D": 0}
    for line in lines:
        status_value, path = line.split("\t", 1)
        if status_value not in counts:
            raise AnfisAblationTrainingDevelopmentPatchError("Git scope contains a non-additive status")
        counts[status_value] += 1
        paths.append(path)
    return {"added": counts["A"], "modified": counts["M"], "deleted": counts["D"], "paths": paths}


def _git_blob_record(
    repo_root: Path, head: str, path: str, *, role: str
) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{head}:{path}"], cwd=repo_root, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"Git blob is unavailable at {head}: {path}"
        )
    return {"path": path, "bytes": len(result.stdout), "sha256": _sha256_bytes(result.stdout), "role": role}


def _lexists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def validate_model_seed(model_id: str, base_seed: int) -> None:
    if model_id not in {"A0", "A1"}:
        raise AnfisAblationTrainingDevelopmentPatchError(f"Unknown ablation model: {model_id!r}")
    if type(base_seed) is not int or base_seed not in REGISTERED_SEEDS:
        raise AnfisAblationTrainingDevelopmentPatchError(f"Unregistered model seed: {base_seed!r}")


def anfis_ablation_training_slot_paths(model_id: str, base_seed: int) -> dict[str, Path]:
    validate_model_seed(model_id, base_seed)
    report_root = Path(f"reports/closure_v1/02_models/{model_id}")
    return {
        "model": Path(f"models/closure_v1/anfis_ablation/{model_id}/seed_{base_seed}.pt"),
        "checkpoint": Path(f"models/closure_v1/anfis_ablation/{model_id}/seed_{base_seed}.checkpoint.pt"),
        "preprocessor": report_root / f"seed_{base_seed}_preprocessor.json",
        "training_curve": report_root / f"seed_{base_seed}_training_curve.csv",
        "selection_predictions": Path(
            f"data/closure_v1/development/anfis_ablation/{model_id}/"
            f"seed_{base_seed}_selection_predictions.parquet"
        ),
        "selection_metrics": report_root / f"seed_{base_seed}_selection_metrics.csv",
        "report": report_root / f"seed_{base_seed}_report.md",
        "manifest": report_root / f"seed_{base_seed}_manifest.json",
    }


slot_paths = anfis_ablation_training_slot_paths


def _all_slot_paths() -> tuple[Path, ...]:
    return tuple(
        path
        for model_id, seed in ORDERED_SLOTS
        for path in anfis_ablation_training_slot_paths(model_id, seed).values()
    )


def _temporary_path(path: Path) -> Path:
    return Path(path.as_posix() + ".tmp")


def _pointer_path(model_id: str, base_seed: int) -> Path:
    return Path(
        anfis_ablation_training_slot_paths(model_id, base_seed)["selection_predictions"].as_posix()
        + ".dvc"
    )


def _guard_path(model_id: str, base_seed: int) -> Path:
    return Path(f"tmp/closure_v1_anfis_ablation_training/{model_id}_seed_{base_seed}.guard")


def load_anfis_ablation_training_runtime(
    path: Path = DEFAULT_RUNTIME_CONFIG,
    *,
    verify_physical_pins: bool = True,
    allow_models_dvc_drift: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    runtime = _load_yaml(path, repo_root=root)
    expected_runtime_keys = {
        "schema_version", "experiment_id", "surface_id", "status", "gate",
        "patch_id", "patch_base_commit", "authority", "patch_scope", "roles",
        "targets", "inputs", "preprocessing", "model", "slots", "outputs",
        "verification", "authorizations", "seals",
    }
    if set(runtime) != expected_runtime_keys:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "Runtime top-level dialect drifted"
        )
    expected_top = {
        "schema_version": "closure_anfis_ablation_training_development_runtime_v1",
        "experiment_id": "closure_v1",
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "status": "ready_to_lock",
        "gate": "E0-MT",
        "patch_id": "anfis_ablation_training_development_authority_patch_1",
        "patch_base_commit": BASE_COMMIT,
    }
    for key, expected in expected_top.items():
        if runtime.get(key) != expected:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"Runtime field {key!r} drifted"
            )
    for section, expected_digest in EXPECTED_RUNTIME_SECTION_SHA256.items():
        if _sha256_bytes(_canonical_json(runtime.get(section))) != expected_digest:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"Runtime section {section!r} drifted"
            )
    authority = runtime.get("authority")
    scope = runtime.get("patch_scope")
    targets = runtime.get("targets")
    slots = runtime.get("slots")
    outputs = runtime.get("outputs")
    model = runtime.get("model")
    preprocessing = runtime.get("preprocessing")
    authorizations = runtime.get("authorizations")
    if not all(
        isinstance(value, Mapping)
        for value in (authority, scope, targets, slots, outputs, model, preprocessing, authorizations)
    ):
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime required mappings are absent")
    authority = cast(Mapping[str, Any], authority)
    scope = cast(Mapping[str, Any], scope)
    targets = cast(Mapping[str, Any], targets)
    slots = cast(Mapping[str, Any], slots)
    outputs = cast(Mapping[str, Any], outputs)
    model = cast(Mapping[str, Any], model)
    preprocessing = cast(Mapping[str, Any], preprocessing)
    authorizations = cast(Mapping[str, Any], authorizations)
    if (
        scope.get("exact_added_count") != 10
        or scope.get("exact_modified_count") != 0
        or scope.get("exact_deleted_count") != 0
        or tuple(scope.get("paths", ())) != PATCH_PATHS
    ):
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime H-patch scope drifted")
    if authority.get("physical_input_count") != 47:
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime physical input count drifted")
    records = authority.get("physical_inputs")
    if not isinstance(records, list) or len(records) != 47:
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime physical inputs drifted")
    paths = [record.get("path") for record in records if isinstance(record, Mapping)]
    roles = [record.get("role") for record in records if isinstance(record, Mapping)]
    if len(paths) != 47 or len(set(paths)) != 47 or len(set(roles)) != 47:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "Runtime physical paths and roles must be unique"
        )
    if _digest_records(records) != EXPECTED_PHYSICAL_INPUTS_SHA256:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "Runtime physical-input allowlist drifted"
        )
    expected_projection = [
        "source_id", "site_id", "origin_year_month", "target_year_month",
        "horizon_months", "bloom_h", "target_risk_chla_h",
    ]
    if (
        targets.get("exact_projection") != expected_projection
        or targets.get("training") != {"origins": 5932, "rows": 17796}
        or targets.get("model_selection") != {"origins": 658, "rows": 1974}
        or targets.get("calibration_threshold_closed") != {"origins": 224, "rows": 672}
        or targets.get("post_2020_target_projection") != "forbidden"
        or targets.get("raw_chlorophyll_projection") != "forbidden"
    ):
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime target contract drifted")
    expected_slots = [
        {"model_id": model_id, "base_seed": seed} for model_id, seed in ORDERED_SLOTS
    ]
    if (
        slots.get("exact_slot_count") != 10
        or slots.get("ordered_slots") != expected_slots
        or slots.get("progression_policy")
        != "exact_completed_untracked_prefix_no_pointers_until_all_ten"
    ):
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime slot progression drifted")
    architecture = model.get("common_architecture")
    optimization = model.get("optimization")
    if not isinstance(architecture, Mapping) or not isinstance(optimization, Mapping):
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime model profile is absent")
    expected_architecture = {
        "hidden_dimension": 96,
        "recurrent_layers": 1,
        "dropout": 0.0,
        "add_last": False,
        "residual_mode": "training_only_horizon_priors",
    }
    if any(architecture.get(key) != value for key, value in expected_architecture.items()):
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime GRU architecture drifted")
    expected_optimization = {
        "optimizer": "AdamW", "learning_rate": 0.001, "weight_decay": 0.00001,
        "gradient_clip_norm": 1.0, "batch_size": 2048, "maximum_epochs": 20,
        "early_stopping_patience_epochs": 5, "early_stopping_minimum_delta": 0.0,
    }
    if any(optimization.get(key) != value for key, value in expected_optimization.items()):
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime optimization budget drifted")
    if (
        preprocessing.get("raw_values") != "mask_aware_training_standard_scaler_ddof0"
        or preprocessing.get("fit_role") != "training"
        or preprocessing.get("shared_raw_statistics_required_across_all_slots") is not True
    ):
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime preprocessing drifted")
    if (
        outputs.get("exact_final_path_count") != 80
        or outputs.get("exact_temporary_path_count") != 80
        or outputs.get("exact_guard_path_count") != 10
        or outputs.get("exact_prediction_pointer_count") != 10
    ):
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime output namespace drifted")
    if any(value is not False for key, value in authorizations.items() if key != "publication_required"):
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime contains an open authorization")
    if authorizations.get("publication_required") is not True:
        raise AnfisAblationTrainingDevelopmentPatchError("Runtime publication seal drifted")
    if verify_physical_pins:
        actual = [
            _file_record(root / str(record["path"]), role=str(record["role"]), repo_root=root)
            for record in records
            if not (
                allow_models_dvc_drift and str(record["path"]) == "models.dvc"
            )
        ]
        expected_actual = [
            dict(record)
            for record in records
            if not (
                allow_models_dvc_drift and str(record["path"]) == "models.dvc"
            )
        ]
        if actual != expected_actual:
            raise AnfisAblationTrainingDevelopmentPatchError(
                "Runtime physical input record differs from current bytes"
            )
    return runtime


def preflight_anfis_ablation_training_development_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    encoded = _canonical_json(schema)
    forbidden = {"minimum", "maximum", "format", "minLength", "maxLength"}
    observed: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            observed.update(str(key) for key in value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(schema)
    bad = sorted(forbidden.intersection(observed))
    if bad:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"Schema uses unsupported semantic keywords: {bad}"
        )
    if (
        schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or schema.get("properties", {}).get("gate", {}).get("const") != "E0-MT"
        or schema.get("properties", {}).get("runtime_contract", {}).get("properties", {})
        .get("physical_input_count", {}).get("const") != 47
    ):
        raise AnfisAblationTrainingDevelopmentPatchError("E0-MT schema preflight drifted")
    return {
        "status": "schema_preflight_passed",
        "schema": _file_record(DEFAULT_PATCH_LOCK_SCHEMA, role="patch_lock_schema", repo_root=root),
        "canonical_schema_sha256": _sha256_bytes(encoded),
        "unsupported_semantic_keywords": [],
    }


def collect_anfis_ablation_training_development_patch_prelock_state(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    preflight_anfis_ablation_training_development_patch_schema(repo_root=root)
    runtime = load_anfis_ablation_training_runtime(repo_root=root)
    head = _git_head(root)
    parent = _git_parent(root, head)
    if parent != BASE_COMMIT:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT H must be the direct child of the published sequence bundle"
        )
    scope = _git_scope(root, parent, head)
    if scope != {"added": 10, "modified": 0, "deleted": 0, "paths": list(PATCH_PATHS)}:
        raise AnfisAblationTrainingDevelopmentPatchError(f"E0-MT H scope drifted: {scope}")
    status_lines = [
        line for line in _git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
        if line
    ]
    if status_lines:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT prelock requires a clean worktree: {status_lines}"
        )
    branch = _git(root, "branch", "--show-current").strip()
    tracking = _git_head(root, "origin/main")
    remote = _live_remote_main_head(root) if verify_remote else tracking
    if branch != "main" or tracking != head or remote != head:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT H refs are not aligned with live remote main"
        )
    components = [
        _git_blob_record(root, head, path, role=PATCH_COMPONENT_ROLES[path])
        for path in PATCH_PATHS
    ]
    for record in components:
        current = _file_record(
            root / str(record["path"]), role=str(record["role"]), repo_root=root
        )
        if current != record:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"H component differs from Git blob: {record['path']}"
            )
    bundle_scope = _git_scope(root, SEQUENCE_LOCK_HEAD, BASE_COMMIT)
    if (
        bundle_scope["added"] != 18
        or bundle_scope["modified"] != 0
        or bundle_scope["deleted"] != 0
    ):
        raise AnfisAblationTrainingDevelopmentPatchError("Published sequence bundle scope drifted")
    physical_inputs = [dict(record) for record in runtime["authority"]["physical_inputs"]]
    bundle_records = [
        dict(record)
        for record in physical_inputs
        if str(record["role"]).startswith(("a0_sequence", "a1_sequence"))
    ]
    if len(bundle_records) != 24:
        raise AnfisAblationTrainingDevelopmentPatchError("Sequence bundle binding count drifted")
    finals = _all_slot_paths()
    temporaries = tuple(_temporary_path(path) for path in finals)
    guards = tuple(_guard_path(model_id, seed) for model_id, seed in ORDERED_SLOTS)
    pointers = tuple(_pointer_path(model_id, seed) for model_id, seed in ORDERED_SLOTS)
    present_finals = [path.as_posix() for path in finals if _lexists(root / path)]
    present_temporaries = [path.as_posix() for path in temporaries if _lexists(root / path)]
    present_guards = [path.as_posix() for path in guards if _lexists(root / path)]
    present_pointers = [path.as_posix() for path in pointers if _lexists(root / path)]
    if present_finals or present_temporaries or present_guards or present_pointers:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT prelock output namespace is not empty"
        )
    control = {
        "lock_absent": not _lexists(root / DEFAULT_PATCH_LOCK_PATH),
        "companion_absent": not _lexists(root / DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        "lock_temp_absent": not _lexists(root / _temporary_path(DEFAULT_PATCH_LOCK_PATH)),
        "companion_temp_absent": not _lexists(
            root / _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        ),
        "locker_guard_absent": not _lexists(root / LOCKER_GUARD_PATH),
    }
    if not all(control.values()):
        raise AnfisAblationTrainingDevelopmentPatchError("E0-MT lock namespace is occupied")
    prohibited = {
        "e0_m_paths_absent": not any(_lexists(root / path) for path in E0_M_PATHS),
        "outcome_access_log_absent": not _lexists(root / OUTCOME_ACCESS_LOG),
    }
    if not all(prohibited.values()):
        raise AnfisAblationTrainingDevelopmentPatchError("E0-M or outcome namespace is present")
    namespace = [
        *(path.as_posix() for path in finals),
        *(path.as_posix() for path in temporaries),
        *(path.as_posix() for path in guards),
        *(path.as_posix() for path in pointers),
    ]
    runtime_record = _file_record(
        DEFAULT_RUNTIME_CONFIG, role="anfis_ablation_training_runtime", repo_root=root
    )
    return {
        "repository": {
            "branch": branch,
            "head": head,
            "parent": parent,
            "tracking_head": tracking,
            "remote_head": remote,
            "remote_verification_mode": (
                "live_remote_main_verified" if verify_remote else "tracking_ref_only"
            ),
            "worktree_scope": "exact_h_patch_components_only",
        },
        "h_patch": {
            "base_commit": BASE_COMMIT,
            "head": head,
            "parent": parent,
            "component_count": 10,
            "components": components,
            "components_sha256": _digest_records(components),
            "scope": {"added": 10, "modified": 0, "deleted": 0},
        },
        "upstream_authority": {
            "sequence_patch_head": SEQUENCE_PATCH_HEAD,
            "sequence_lock_head": SEQUENCE_LOCK_HEAD,
            "sequence_bundle_head": BASE_COMMIT,
            "sequence_bundle_parent": SEQUENCE_LOCK_HEAD,
            "sequence_bundle_scope": {"added": 18, "modified": 0, "deleted": 0},
            "bundle_records": bundle_records,
            "bundle_records_sha256": _digest_records(bundle_records),
        },
        "runtime_contract": {
            "runtime": runtime_record,
            "runtime_sha256": str(runtime_record["sha256"]),
            "physical_input_count": 47,
            "physical_inputs": physical_inputs,
            "physical_inputs_sha256": _digest_records(physical_inputs),
            "target_contract": dict(runtime["targets"]),
            "preprocessing": dict(runtime["preprocessing"]),
            "model": dict(runtime["model"]),
            "slots": dict(runtime["slots"]),
            "outputs": dict(runtime["outputs"]),
        },
        "prelock": {
            "completed_prefix_count": 0,
            "final_paths_present": [],
            "temporary_paths_present": [],
            "guard_paths_present": [],
            "prediction_pointers_present": [],
            "output_namespace_sha256": _sha256_bytes(_canonical_json(namespace)),
            "control_paths": control,
            "prohibited_namespaces": prohibited,
        },
    }


def build_anfis_ablation_training_development_patch_lock_payload(
    *, prelock: Mapping[str, Any], verification: Mapping[str, Any]
) -> dict[str, Any]:
    """Construct the inert unpublished authority from an exact prelock snapshot."""
    required = {"repository", "h_patch", "upstream_authority", "runtime_contract", "prelock"}
    if set(prelock) != required:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT prelock bundle dialect drifted"
        )
    return {
        "schema_version": "closure_anfis_ablation_training_development_patch_lock_v1",
        "status": "locked_unpublished",
        "gate": "E0-MT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": dict(prelock["repository"]),
        "h_patch": dict(prelock["h_patch"]),
        "upstream_authority": dict(prelock["upstream_authority"]),
        "runtime_contract": dict(prelock["runtime_contract"]),
        "prelock": dict(prelock["prelock"]),
        "verification": dict(verification),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
        "seals": dict(LOCK_SEALS),
    }


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT lock timestamp must be a string"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT lock timestamp is malformed"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT lock timestamp must include a timezone"
        )


def _validate_file_record(value: Any, *, role_required: bool = True) -> dict[str, Any]:
    keys = {"path", "bytes", "sha256", "role"} if role_required else {
        "path", "bytes", "sha256"
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT file-record dialect drifted"
        )
    path = value.get("path")
    byte_count = value.get("bytes")
    digest = value.get("sha256")
    if (
        not isinstance(path, str)
        or not path
        or Path(path).is_absolute()
        or any(part in {"", ".", ".."} for part in Path(path).parts)
        or isinstance(byte_count, bool)
        or not isinstance(byte_count, int)
        or byte_count < 0
        or not isinstance(digest, str)
        or SHA256_RE.fullmatch(digest) is None
        or (role_required and (not isinstance(value.get("role"), str) or not value["role"]))
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT file-record semantics drifted"
        )
    return dict(value)


def _validate_command_evidence(
    value: Any,
    *,
    expected_command: Sequence[str],
    context: str,
    exact_stdout: str | None = None,
) -> None:
    keys = {
        "command", "returncode", "stdout_sha256", "stderr_sha256",
        "stdout_line_count", "stderr_line_count",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT {context} evidence dialect drifted"
        )
    if value.get("command") != list(expected_command) or value.get("returncode") != 0:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT {context} command/result drifted"
        )
    for key in ("stdout_sha256", "stderr_sha256"):
        if not isinstance(value.get(key), str) or SHA256_RE.fullmatch(str(value[key])) is None:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT {context} digest drifted"
            )
    for key in ("stdout_line_count", "stderr_line_count"):
        count = value.get(key)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT {context} line count drifted"
            )
    if value.get("stderr_sha256") != EMPTY_SHA256 or value.get("stderr_line_count") != 0:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT {context} stderr evidence drifted"
        )
    if exact_stdout is not None and (
        value.get("stdout_sha256") != _sha256_bytes(exact_stdout.encode("utf-8"))
        or value.get("stdout_line_count") != len(exact_stdout.splitlines())
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT {context} stdout evidence drifted"
        )


def _validate_verification(value: Any, *, repo_root: Path) -> None:
    keys = {
        "schema_preflight", "full_type_check", "focused_tests", "poetry_check",
        "publication_guard", "git_diff_check",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT verification bundle drifted"
        )
    if value.get("schema_preflight") != preflight_anfis_ablation_training_development_patch_schema(
        repo_root=repo_root
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT schema-preflight evidence drifted"
        )
    _validate_command_evidence(
        value.get("full_type_check"), expected_command=TYPE_CHECK_COMMAND,
        context="full type check", exact_stdout="All checks passed!\n",
    )
    _validate_command_evidence(
        value.get("poetry_check"), expected_command=POETRY_CHECK_COMMAND,
        context="poetry check", exact_stdout="All set!\n",
    )
    _validate_command_evidence(
        value.get("publication_guard"), expected_command=PUBLICATION_GUARD_COMMAND,
        context="publication guard",
        exact_stdout=(
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n"
        ),
    )
    _validate_command_evidence(
        value.get("git_diff_check"), expected_command=DIFF_CHECK_COMMAND,
        context="git diff check", exact_stdout="",
    )
    focused = value.get("focused_tests")
    if not isinstance(focused, Mapping):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT focused-test evidence is absent"
        )
    common = {
        key: focused.get(key)
        for key in (
            "command", "returncode", "stdout_sha256", "stderr_sha256",
            "stdout_line_count", "stderr_line_count",
        )
    }
    _validate_command_evidence(
        common, expected_command=FOCUSED_TEST_COMMAND, context="focused tests"
    )
    if set(focused) != {*common, "test_count", "skipped_count", "deselected_count"}:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT focused-test summary dialect drifted"
        )
    if FOCUSED_TEST_COUNT <= 0 or (
        focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT focused-test count drifted"
        )


def _reconstruct_h_components(
    payload: Mapping[str, Any], *, repo_root: Path
) -> list[dict[str, Any]]:
    h_patch = payload.get("h_patch")
    repository = payload.get("repository")
    if not isinstance(h_patch, Mapping) or not isinstance(repository, Mapping):
        raise AnfisAblationTrainingDevelopmentPatchError("E0-MT H binding is absent")
    head = repository.get("head")
    if not isinstance(head, str) or SHA1_RE.fullmatch(head) is None:
        raise AnfisAblationTrainingDevelopmentPatchError("E0-MT H head is invalid")
    records = [
        _git_blob_record(repo_root, head, path, role=PATCH_COMPONENT_ROLES[path])
        for path in PATCH_PATHS
    ]
    for record in records:
        if _file_record(
            Path(str(record["path"])), role=str(record["role"]), repo_root=repo_root
        ) != record:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT H component differs from published bytes: {record['path']}"
            )
    return records


def validate_anfis_ablation_training_development_patch_lock_payload(
    payload: Mapping[str, Any], *, repo_root: Path | None = None,
    allow_models_dvc_drift: bool = False,
) -> None:
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise AnfisAblationTrainingDevelopmentPatchError(str(exc)) from exc
    _validate_timestamp(payload.get("created_at_utc"))
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT unpublished authorizations drifted"
        )
    if payload.get("seals") != LOCK_SEALS:
        raise AnfisAblationTrainingDevelopmentPatchError("E0-MT seals drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or set(repository) != {
        "branch", "head", "parent", "tracking_head", "remote_head",
        "remote_verification_mode", "worktree_scope",
    }:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT repository dialect drifted"
        )
    h_head = repository.get("head")
    if (
        repository.get("branch") != "main"
        or not isinstance(h_head, str)
        or SHA1_RE.fullmatch(h_head) is None
        or repository.get("parent") != BASE_COMMIT
        or repository.get("tracking_head") != h_head
        or repository.get("remote_head") != h_head
        or repository.get("remote_verification_mode") != "live_remote_main_verified"
        or repository.get("worktree_scope") != "exact_h_patch_components_only"
        or _git_parent(root, h_head) != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, h_head)
        != {"added": 10, "modified": 0, "deleted": 0, "paths": list(PATCH_PATHS)}
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT repository/H topology drifted"
        )
    reconstructed = _reconstruct_h_components(payload, repo_root=root)
    h_patch = payload.get("h_patch")
    if not isinstance(h_patch, Mapping):
        raise AnfisAblationTrainingDevelopmentPatchError("E0-MT H payload is absent")
    if (
        set(h_patch) != {
            "base_commit", "head", "parent", "component_count", "components",
            "components_sha256", "scope",
        }
        or h_patch.get("base_commit") != BASE_COMMIT
        or h_patch.get("head") != h_head
        or h_patch.get("parent") != BASE_COMMIT
        or h_patch.get("component_count") != 10
        or h_patch.get("components") != reconstructed
        or h_patch.get("components_sha256") != _digest_records(reconstructed)
        or h_patch.get("scope") != {"added": 10, "modified": 0, "deleted": 0}
    ):
        raise AnfisAblationTrainingDevelopmentPatchError("E0-MT H binding drifted")
    runtime = load_anfis_ablation_training_runtime(
        repo_root=root,
        allow_models_dvc_drift=allow_models_dvc_drift,
    )
    physical = [dict(record) for record in runtime["authority"]["physical_inputs"]]
    runtime_record = _file_record(
        DEFAULT_RUNTIME_CONFIG, role="anfis_ablation_training_runtime", repo_root=root
    )
    expected_runtime = {
        "runtime": runtime_record,
        "runtime_sha256": runtime_record["sha256"],
        "physical_input_count": 47,
        "physical_inputs": physical,
        "physical_inputs_sha256": _digest_records(physical),
        "target_contract": dict(runtime["targets"]),
        "preprocessing": dict(runtime["preprocessing"]),
        "model": dict(runtime["model"]),
        "slots": dict(runtime["slots"]),
        "outputs": dict(runtime["outputs"]),
    }
    if payload.get("runtime_contract") != expected_runtime:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT complete runtime binding drifted"
        )
    upstream = payload.get("upstream_authority")
    bundle_records = [
        dict(record)
        for record in physical
        if str(record["role"]).startswith(("a0_sequence", "a1_sequence"))
    ]
    expected_upstream = {
        "sequence_patch_head": SEQUENCE_PATCH_HEAD,
        "sequence_lock_head": SEQUENCE_LOCK_HEAD,
        "sequence_bundle_head": BASE_COMMIT,
        "sequence_bundle_parent": SEQUENCE_LOCK_HEAD,
        "sequence_bundle_scope": {"added": 18, "modified": 0, "deleted": 0},
        "bundle_records": bundle_records,
        "bundle_records_sha256": _digest_records(bundle_records),
    }
    if upstream != expected_upstream:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT upstream authority binding drifted"
        )
    namespace = [
        *(path.as_posix() for path in _all_slot_paths()),
        *(_temporary_path(path).as_posix() for path in _all_slot_paths()),
        *(_guard_path(model, seed).as_posix() for model, seed in ORDERED_SLOTS),
        *(_pointer_path(model, seed).as_posix() for model, seed in ORDERED_SLOTS),
    ]
    expected_prelock = {
        "completed_prefix_count": 0,
        "final_paths_present": [],
        "temporary_paths_present": [],
        "guard_paths_present": [],
        "prediction_pointers_present": [],
        "output_namespace_sha256": _sha256_bytes(_canonical_json(namespace)),
        "control_paths": {
            "lock_absent": True, "companion_absent": True,
            "lock_temp_absent": True, "companion_temp_absent": True,
            "locker_guard_absent": True,
        },
        "prohibited_namespaces": {
            "e0_m_paths_absent": True, "outcome_access_log_absent": True,
        },
    }
    if payload.get("prelock") != expected_prelock:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT complete prelock binding drifted"
        )
    _validate_verification(payload.get("verification"), repo_root=root)


def _expected_companion(
    payload: Mapping[str, Any], lock_record: Mapping[str, Any], *, repo_root: Path | None = None
) -> dict[str, Any]:
    del repo_root
    h_patch = payload.get("h_patch")
    runtime_contract = payload.get("runtime_contract")
    if not isinstance(h_patch, Mapping) or not isinstance(runtime_contract, Mapping):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "Cannot construct E0-MT companion inputs"
        )
    components = h_patch.get("components")
    physical = runtime_contract.get("physical_inputs")
    if not isinstance(components, list) or not isinstance(physical, list):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "Cannot construct E0-MT companion records"
        )
    inputs = [dict(record) for record in (*components, *physical)]
    inputs.sort(key=lambda record: str(record.get("path")))
    input_paths = [str(record.get("path")) for record in inputs]
    if len(inputs) != 57 or len(set(input_paths)) != 57:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT companion must bind exactly 57 unique physical inputs"
        )
    script = next(
        dict(record) for record in components if record.get("path") == LOCKER_PATH.as_posix()
    )
    output = _validate_file_record(lock_record)
    if (
        output.get("path") != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or output.get("role") != "anfis_ablation_training_development_patch_lock"
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT companion lock output record drifted"
        )
    return {
        "manifest_version": "closure_anfis_ablation_training_development_patch_lock_manifest_v1",
        "gate": "E0-MT",
        "status": "completed",
        "script": script,
        "inputs": inputs,
        "historical_inputs": [],
        "historical_inputs_compared_to_current_paths": False,
        "outputs": [output],
        "physical_inputs_only": True,
        "manifest_written_last": True,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "data_execution_run": False,
        "future_outcomes_accessed": False,
        "completion_marker_written_last": True,
    }


def publish_anfis_ablation_training_lock_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Publish lock then companion through no-follow, no-clobber transactions."""
    root = _root(repo_root)
    validate_anfis_ablation_training_development_patch_lock_payload(
        payload, repo_root=root
    )
    controlled = (
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        _temporary_path(DEFAULT_PATCH_LOCK_PATH),
        _temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        LOCKER_GUARD_PATH,
    )
    occupied = [path.as_posix() for path in controlled if _lexists(root / path)]
    if occupied:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT lock namespace is occupied: {occupied}"
        )
    guard: _OwnedGuard | None = _acquire_publication_guard(
        LOCKER_GUARD_PATH, b"E0-MT lock bundle publication in progress\n", repo_root=root
    )
    published: list[_OwnedOutput] = []
    committed = False
    try:
        lock_output = _publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, _canonical_json(dict(payload)), repo_root=root
        )
        published.append(lock_output)
        lock_record = _file_record(
            DEFAULT_PATCH_LOCK_PATH,
            role="anfis_ablation_training_development_patch_lock",
            repo_root=root,
        )
        companion = _expected_companion(payload, lock_record, repo_root=root)
        companion_output = _publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            _canonical_json(companion),
            repo_root=root,
        )
        published.append(companion_output)
        if _load_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root) != dict(payload):
            raise AnfisAblationTrainingDevelopmentPatchError(
                "Published E0-MT lock differs from its payload"
            )
        if _load_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root) != companion:
            raise AnfisAblationTrainingDevelopmentPatchError(
                "Published E0-MT companion differs from its payload"
            )
        for output in published:
            _validate_owned_output(output)
        _release_publication_guard(guard)
        guard = None
        for output in published:
            _validate_owned_output(output)
        committed = True
        return dict(payload), companion
    except BaseException:
        for output in reversed(published):
            _rollback_owned_output(output)
        raise
    finally:
        if guard is not None:
            _release_publication_guard(guard, tolerate_foreign=True)
        if committed:
            for output in published:
                _close_owned_output(output)


def _open_parent_directory(
    path: Path, *, repo_root: Path, create: bool
) -> tuple[int, str]:
    relative = _relative_path(path, repo_root)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(repo_root, flags)
    try:
        for component in relative.parts[:-1]:
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(component, mode=0o755, dir_fd=descriptor)
                child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor, relative.name
    except BaseException:
        os.close(descriptor)
        raise


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise AnfisAblationTrainingDevelopmentPatchError(
                "E0-MT publication write made no progress"
            )
        offset += written


def _named_identity(parent_fd: int, name: str) -> tuple[int, int] | None:
    try:
        value = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(value.st_mode):
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT controlled path is not a regular file: {name}"
        )
    return value.st_dev, value.st_ino


def _acquire_publication_guard(
    path: Path, payload: bytes, *, repo_root: Path
) -> _OwnedGuard:
    relative = _relative_path(path, repo_root)
    lexical_parent = repo_root / relative.parent
    parent_fd, name = _open_parent_directory(path, repo_root=repo_root, create=True)
    descriptor: int | None = None
    identity: tuple[int, int] | None = None
    parent_identity: tuple[int, int] | None = None
    committed = False
    try:
        parent_stat = os.fstat(parent_fd)
        if not stat.S_ISDIR(parent_stat.st_mode):
            raise AnfisAblationTrainingDevelopmentPatchError(
                "E0-MT guard parent is not a directory"
            )
        parent_identity = (parent_stat.st_dev, parent_stat.st_ino)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(name, flags, 0o600, dir_fd=parent_fd)
        before = os.fstat(descriptor)
        identity = (before.st_dev, before.st_ino)
        if not stat.S_ISREG(before.st_mode):
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT owned path is not regular: {path.as_posix()}"
            )
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        after = os.fstat(descriptor)
        if (
            (after.st_dev, after.st_ino) != identity
            or after.st_size != len(payload)
            or _named_identity(parent_fd, name) != identity
        ):
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT owned path changed during write: {path.as_posix()}"
            )
        os.fsync(parent_fd)
        committed = True
        return _OwnedGuard(
            path=path,
            lexical_parent=lexical_parent,
            name=name,
            file_descriptor=descriptor,
            parent_descriptor=parent_fd,
            device=identity[0],
            inode=identity[1],
            parent_device=parent_identity[0],
            parent_inode=parent_identity[1],
        )
    except BaseException:
        if identity is not None and _named_identity(parent_fd, name) == identity:
            os.unlink(name, dir_fd=parent_fd)
            os.fsync(parent_fd)
        raise
    finally:
        if not committed and descriptor is not None:
            os.close(descriptor)
        if not committed:
            os.close(parent_fd)


def _release_publication_guard(
    guard: _OwnedGuard, *, tolerate_foreign: bool = False
) -> None:
    if guard.closed:
        return
    error: BaseException | None = None
    try:
        parent = os.fstat(guard.parent_descriptor)
        lexical_parent = guard.lexical_parent.lstat()
        opened = os.fstat(guard.file_descriptor)
        named = _named_identity(guard.parent_descriptor, guard.name)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or (parent.st_dev, parent.st_ino)
            != (guard.parent_device, guard.parent_inode)
            or not stat.S_ISDIR(lexical_parent.st_mode)
            or (lexical_parent.st_dev, lexical_parent.st_ino)
            != (guard.parent_device, guard.parent_inode)
            or not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (guard.device, guard.inode)
            or named != (guard.device, guard.inode)
        ):
            if not tolerate_foreign:
                error = AnfisAblationTrainingDevelopmentPatchError(
                    "E0-MT publication guard identity drifted"
                )
        else:
            os.unlink(guard.name, dir_fd=guard.parent_descriptor)
            os.fsync(guard.parent_descriptor)
    except BaseException as exc:
        error = exc
    finally:
        close_errors: list[OSError] = []
        for descriptor in (guard.file_descriptor, guard.parent_descriptor):
            try:
                os.close(descriptor)
            except OSError as exc:
                close_errors.append(exc)
        guard.closed = True
        if error is None and close_errors:
            error = close_errors[0]
    if error is not None and not tolerate_foreign:
        if isinstance(error, AnfisAblationTrainingDevelopmentPatchError):
            raise error
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT publication guard cleanup failed"
        ) from error


def _publish_bytes_no_clobber(
    final_path: Path, payload: bytes, *, repo_root: Path
) -> _OwnedOutput:
    temporary = _temporary_path(final_path)
    relative = _relative_path(final_path, repo_root)
    lexical_parent = repo_root / relative.parent
    parent_fd, final_name = _open_parent_directory(
        final_path, repo_root=repo_root, create=True
    )
    temporary_name = _relative_path(temporary, repo_root).name
    descriptor: int | None = None
    temp_identity: tuple[int, int] | None = None
    final_identity: tuple[int, int] | None = None
    parent_identity: tuple[int, int] | None = None
    retained = False
    try:
        parent = os.fstat(parent_fd)
        if not stat.S_ISDIR(parent.st_mode):
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT output parent is not a directory: {final_path.as_posix()}"
            )
        parent_identity = (parent.st_dev, parent.st_ino)
        if _named_identity(parent_fd, final_name) is not None:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT refuses to overwrite final: {final_path.as_posix()}"
            )
        if _named_identity(parent_fd, temporary_name) is not None:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT refuses occupied temporary: {temporary.as_posix()}"
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary_name, flags, 0o644, dir_fd=parent_fd)
        before = os.fstat(descriptor)
        temp_identity = (before.st_dev, before.st_ino)
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        after = os.fstat(descriptor)
        if (
            not stat.S_ISREG(after.st_mode)
            or (after.st_dev, after.st_ino) != temp_identity
            or after.st_size != len(payload)
            or _named_identity(parent_fd, temporary_name) != temp_identity
        ):
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT temporary changed during write: {temporary.as_posix()}"
            )
        os.link(
            temporary_name,
            final_name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
            follow_symlinks=False,
        )
        final_identity = _named_identity(parent_fd, final_name)
        if final_identity != temp_identity:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT final identity drifted: {final_path.as_posix()}"
            )
        os.fsync(parent_fd)
        if _named_identity(parent_fd, temporary_name) != temp_identity:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT temporary was replaced: {temporary.as_posix()}"
            )
        os.unlink(temporary_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
        if final_identity is None:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT final identity is absent: {final_path.as_posix()}"
            )
        retained = True
        return _OwnedOutput(
            path=final_path,
            lexical_parent=lexical_parent,
            name=final_name,
            parent_descriptor=parent_fd,
            device=final_identity[0],
            inode=final_identity[1],
            parent_device=parent_identity[0],
            parent_inode=parent_identity[1],
        )
    except BaseException:
        if temp_identity is not None and _named_identity(parent_fd, temporary_name) == temp_identity:
            os.unlink(temporary_name, dir_fd=parent_fd)
        if final_identity is not None and _named_identity(parent_fd, final_name) == final_identity:
            os.unlink(final_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if not retained:
            os.close(parent_fd)


def _validate_owned_output(output: _OwnedOutput) -> None:
    if output.closed:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT owned output descriptor is closed: {output.path.as_posix()}"
        )
    parent = os.fstat(output.parent_descriptor)
    lexical_parent = output.lexical_parent.lstat()
    named = _named_identity(output.parent_descriptor, output.name)
    if (
        not stat.S_ISDIR(parent.st_mode)
        or (parent.st_dev, parent.st_ino)
        != (output.parent_device, output.parent_inode)
        or not stat.S_ISDIR(lexical_parent.st_mode)
        or (lexical_parent.st_dev, lexical_parent.st_ino)
        != (output.parent_device, output.parent_inode)
        or named != (output.device, output.inode)
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT owned output identity drifted: {output.path.as_posix()}"
        )


def _close_owned_output(output: _OwnedOutput) -> None:
    if output.closed:
        return
    try:
        os.close(output.parent_descriptor)
    finally:
        output.closed = True


def _rollback_owned_output(output: _OwnedOutput) -> None:
    """Remove only our inode through its retained parent descriptor."""

    if output.closed:
        return
    error: BaseException | None = None
    try:
        parent = os.fstat(output.parent_descriptor)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or (parent.st_dev, parent.st_ino)
            != (output.parent_device, output.parent_inode)
        ):
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT owned output parent identity drifted: {output.path.as_posix()}"
            )
        if _named_identity(output.parent_descriptor, output.name) == (
            output.device,
            output.inode,
        ):
            os.unlink(output.name, dir_fd=output.parent_descriptor)
            os.fsync(output.parent_descriptor)
    except BaseException as exc:
        error = exc
    finally:
        try:
            os.close(output.parent_descriptor)
        except OSError as exc:
            if error is None:
                error = exc
        output.closed = True
    if error is not None:
        if isinstance(error, AnfisAblationTrainingDevelopmentPatchError):
            raise error
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT owned output rollback failed: {output.path.as_posix()}"
        ) from error


def load_effective_anfis_ablation_training_authority(
    *,
    verify_remote: bool = True,
    mode: str = "audit",
    model_id: str | None = None,
    base_seed: int | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if mode not in {"build", "audit"}:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT mode must be build or audit"
        )
    if verify_remote is not True:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT effective authority requires live remote verification"
        )
    root = _root(repo_root)
    payload = _load_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    if _read_regular_bytes(DEFAULT_PATCH_LOCK_PATH, repo_root=root) != _canonical_json(payload):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT lock is not canonical JSON"
        )
    # DVC may change only models.dvc after all ten bundles have been audited.
    all_pointer_presence = [
        _lexists(root / _pointer_path(slot_model, slot_seed))
        for slot_model, slot_seed in ORDERED_SLOTS
    ]
    allow_models_dvc_drift = all(all_pointer_presence)
    validate_anfis_ablation_training_development_patch_lock_payload(
        payload, repo_root=root, allow_models_dvc_drift=allow_models_dvc_drift
    )
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="anfis_ablation_training_development_patch_lock",
        repo_root=root,
    )
    companion = _load_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root)
    if (
        _read_regular_bytes(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root)
        != _canonical_json(companion)
        or companion != _expected_companion(payload, lock_record, repo_root=root)
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT lock companion drifted"
        )
    companion_record = _file_record(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        role="anfis_ablation_training_development_patch_lock_manifest",
        repo_root=root,
    )
    publication = _validate_p_publication(payload, repo_root=root)
    static = _static_effective_authority(
        payload, publication=publication, lock=lock_record, companion=companion_record
    )
    prefix_count = _validate_exact_training_prefix(
        static,
        audit_mode=mode == "audit",
        repo_root=root,
    )
    if model_id is None:
        if base_seed is not None:
            raise AnfisAblationTrainingDevelopmentPatchError(
                "E0-MT implicit target cannot carry a seed"
            )
        if mode == "build":
            if prefix_count >= len(ORDERED_SLOTS):
                raise AnfisAblationTrainingDevelopmentPatchError(
                    "All E0-MT one-shot authorities have been consumed"
                )
            model_id, base_seed = ORDERED_SLOTS[prefix_count]
        else:
            return {
                **static,
                **_effective_authorizations(model_id="A0", mode="summary"),
                "authorized_model_id": None,
                "authorized_base_seed": None,
                "completed_prefix_count": prefix_count,
                "slot_creation_prefix_count": None,
                "audit_current_unpublished": False,
                "ordered_slots": [
                    {"model_id": item_model, "base_seed": item_seed}
                    for item_model, item_seed in ORDERED_SLOTS
                ],
                "progression_policy": (
                    "exact_completed_untracked_prefix_no_pointers_until_all_ten"
                ),
            }
    if model_id is None or base_seed is None:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT target model/seed is incomplete"
        )
    validate_model_seed(model_id, base_seed)
    target_index = ORDERED_SLOTS.index((model_id, base_seed))
    target_valid = (
        target_index == prefix_count
        if mode == "build"
        else target_index < prefix_count
    )
    if not target_valid:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT target is not in the exact {mode} position"
        )
    authorizations = _effective_authorizations(model_id=model_id, mode=mode)
    return {
        **static,
        **authorizations,
        "authorized_model_id": model_id,
        "authorized_base_seed": base_seed,
        "completed_prefix_count": prefix_count if mode == "audit" else target_index,
        "slot_creation_prefix_count": target_index,
        "audit_current_unpublished": mode == "audit",
        "ordered_slots": [
            {"model_id": item_model, "base_seed": item_seed}
            for item_model, item_seed in ORDERED_SLOTS
        ],
        "progression_policy": "exact_completed_untracked_prefix_no_pointers_until_all_ten",
    }


def _git_mode(repo_root: Path, commit: str, path: str) -> str:
    rows = _git(repo_root, "ls-tree", commit, "--", path).splitlines()
    if len(rows) != 1:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT Git path is not unique: {path}"
        )
    return rows[0].split()[0]


def _validate_p_publication(
    payload: Mapping[str, Any], *, repo_root: Path
) -> dict[str, str]:
    h_head = payload["repository"]["head"]
    head = _git_head(repo_root)
    tracking = _git_head(repo_root, "origin/main")
    remote = _live_remote_main_head(repo_root)
    if (
        _git(repo_root, "branch", "--show-current").strip() != "main"
        or _git_parent(repo_root, head) != h_head
        or tracking != head
        or remote != head
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "Published P-E0-MT topology/refs drifted"
        )
    expected_paths = sorted(
        (DEFAULT_PATCH_LOCK_PATH.as_posix(), DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix())
    )
    scope = _git_scope(repo_root, h_head, head)
    if scope != {"added": 2, "modified": 0, "deleted": 0, "paths": expected_paths}:
        raise AnfisAblationTrainingDevelopmentPatchError(
            "P-E0-MT must add exactly lock plus companion"
        )
    for path in expected_paths:
        if _git_mode(repo_root, head, path) != "100644":
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"P-E0-MT Git mode drifted: {path}"
            )
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


def _static_effective_authority(
    payload: Mapping[str, Any],
    *,
    publication: Mapping[str, str],
    lock: Mapping[str, Any],
    companion: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_contract = payload["runtime_contract"]
    h_patch = payload["h_patch"]
    return {
        "gate": "E0-MT",
        "status": "effective_preflight_passed",
        "h_patch_head": publication["h_patch_head"],
        "p_patch_head": publication["p_patch_head"],
        "runtime": dict(runtime_contract["runtime"]),
        "lock": dict(lock),
        "companion": dict(companion),
        "h_components_sha256": h_patch["components_sha256"],
        "physical_inputs_sha256": runtime_contract["physical_inputs_sha256"],
        "runtime_sha256": runtime_contract["runtime_sha256"],
        "lock_sha256": lock["sha256"],
        "companion_sha256": companion["sha256"],
    }


def _effective_authorizations(*, model_id: str, mode: str) -> dict[str, bool]:
    build = mode == "build"
    development_read = mode in {"build", "audit"}
    return {
        "a0_development_fit_authorized": build and model_id == "A0",
        "a1_development_fit_authorized": build and model_id == "A1",
        "target_access_through_2020_authorized": development_read,
        "selection_diagnostics_authorized": development_read,
        "model_bundle_audit_authorized": mode == "audit",
        "calibration_authorized": False,
        "calibration_target_access_authorized": False,
        "final_e7_metrics_authorized": False,
        "rollout_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "scientific_network_authorized": False,
        "outcome_access_authorized": False,
        "future_outcomes_accessed": False,
        "batch_slot_execution_authorized": False,
    }


def _plain_record(path: Path, *, role: str, repo_root: Path) -> dict[str, Any]:
    return _file_record(path, role=role, repo_root=repo_root)


def _manifest_input_spec(model_id: str, base_seed: int) -> list[tuple[str, Path]]:
    if model_id == "A0":
        sequence = Path("data/closure_v1/development/sequences/A0/raw_no_current.parquet")
        stem = Path("reports/closure_v1/01_surface/sequences/A0/raw_no_current")
    else:
        sequence = Path(
            f"data/closure_v1/development/sequences/A1/seed_{base_seed}.parquet"
        )
        stem = Path(
            f"reports/closure_v1/01_surface/sequences/A1/seed_{base_seed}"
        )
    prefix = model_id.lower()
    return [
        (f"{prefix}_sequence", sequence),
        (f"{prefix}_sequence_pointer", Path(sequence.as_posix() + ".dvc")),
        (f"{prefix}_sequence_summary", Path(stem.as_posix() + "_summary.csv")),
        (f"{prefix}_sequence_manifest", Path(stem.as_posix() + "_manifest.json")),
        ("common_origin", Path("data/closure_v1/common_origin_manifest.parquet")),
        ("common_origin_pointer", Path("data/closure_v1/common_origin_manifest.parquet.dvc")),
        ("common_origin_manifest", Path("reports/closure_v1/01_surface/common_origin_manifest.json")),
        ("development_targets", Path("data/targets/monthly_targets_model_v0.parquet")),
        ("targets_pointer", Path("data/targets.dvc")),
        ("target_manifest", Path("data/targets/target_manifest_v0.json")),
    ]


def _validate_completed_slot(
    static: Mapping[str, Any],
    *,
    model_id: str,
    base_seed: int,
    target_index: int,
    target_reference: Any,
    repo_root: Path,
) -> None:
    paths = anfis_ablation_training_slot_paths(model_id, base_seed)
    manifest_bytes = _read_regular_bytes(paths["manifest"], repo_root=repo_root)
    manifest = _load_json(paths["manifest"], repo_root=repo_root)
    if manifest_bytes != _canonical_json(manifest):
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT manifest is not canonical: {model_id}/{base_seed}"
        )
    expected_keys = {
        "manifest_version", "status", "slot_status", "fit_status",
        "generated_at_utc", "experiment_id", "surface_id", "model_id",
        "base_seed", "device", "future_outcomes_accessed",
        "calibration_authorized", "calibration_target_accessed",
        "evaluation_authorized", "e0_m_authorized", "e0_u_authorized",
        "dvc_command_executed", "target_contract", "role_counts",
        "architecture", "preprocessing", "pairing", "authority", "authority_records", "script",
        "inputs", "source_code", "outputs", "completion_marker_written_last",
    }
    required_scalars = {
        "manifest_version": "closure_anfis_ablation_model_manifest_v1",
        "status": "completed", "slot_status": "available", "fit_status": "passed",
        "experiment_id": "closure_v1",
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "model_id": model_id, "base_seed": base_seed, "device": "cpu",
        "future_outcomes_accessed": False, "calibration_authorized": False,
        "calibration_target_accessed": False, "evaluation_authorized": False,
        "e0_m_authorized": False, "e0_u_authorized": False,
        "dvc_command_executed": False, "completion_marker_written_last": True,
    }
    if (
        set(manifest) != expected_keys
        or
        any(manifest.get(key) != expected for key, expected in required_scalars.items())
        or next(reversed(manifest), None) != "completion_marker_written_last"
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT manifest identity drifted: {model_id}/{base_seed}"
        )
    _validate_timestamp(manifest.get("generated_at_utc"))
    runtime_record = load_anfis_ablation_training_runtime(
        verify_physical_pins=False, repo_root=repo_root
    )
    targets = runtime_record["targets"]
    preprocessing = runtime_record["preprocessing"]
    model = runtime_record["model"]
    inputs_section = runtime_record["inputs"]
    roles_section = runtime_record["roles"]
    expected_sections = {
        "target_contract": {
            "join_columns": list(targets["join_columns"]),
            "exact_projection": list(targets["exact_projection"]),
            "horizons_months": list(targets["horizons_months"]),
            "development_target_access_end": str(roles_section["model_selection_end"]),
            "calibration_target_values_opened": False,
            "raw_chlorophyll_projection": "forbidden",
        },
        "role_counts": {
            "training": dict(targets["training"]),
            "model_selection": dict(targets["model_selection"]),
            "calibration_threshold_metadata_only": dict(
                targets["calibration_threshold_closed"]
            ),
            "calibration_target_rows_read": 0,
            "test_target_rows_read": 0,
            "holdout_target_rows_read": 0,
            "post_2020_target_rows_read": 0,
        },
        "architecture": {
            "history_length_months": int(inputs_section["history_length_months"]),
            "input_dimension": int(inputs_section[model_id]["input_dimension"]),
            "family": model["family"],
            "common_architecture": dict(model["common_architecture"]),
            "loss": dict(model["loss"]),
            "selection": dict(model["selection"]),
            "optimization": dict(model["optimization"]),
            "execution": dict(model["execution"]),
        },
        "preprocessing": dict(preprocessing),
    }
    if any(manifest.get(key) != expected for key, expected in expected_sections.items()):
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT manifest scientific contract drifted: {model_id}/{base_seed}"
        )
    pairing = manifest.get("pairing")
    if (
        not isinstance(pairing, Mapping)
        or set(pairing) != {
            "policy", "paired_model_ids", "base_seed", "training_identity_sha256",
            "selection_identity_sha256", "selection_target_sha256",
        }
        or pairing.get("policy") != "same_model_seed_pair_A0_then_A1"
        or pairing.get("paired_model_ids") != ["A0", "A1"]
        or pairing.get("base_seed") != base_seed
        or any(
            not isinstance(pairing.get(key), str)
            or SHA256_RE.fullmatch(str(pairing[key])) is None
            for key in (
                "training_identity_sha256", "selection_identity_sha256",
                "selection_target_sha256",
            )
        )
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT manifest pairing contract drifted: {model_id}/{base_seed}"
        )
    expected_authority = {
        key: static[key]
        for key in (
            "gate", "status", "h_patch_head", "p_patch_head",
            "h_components_sha256", "physical_inputs_sha256", "runtime_sha256",
            "lock_sha256", "companion_sha256",
        )
    }
    expected_authority.update(
        {
            "authorized_model_id": model_id,
            "authorized_base_seed": base_seed,
            "completed_prefix_count": target_index,
            "slot_creation_prefix_count": target_index,
        }
    )
    if manifest.get("authority") != expected_authority:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT manifest authority drifted: {model_id}/{base_seed}"
        )
    expected_inputs = [
        _plain_record(path, role=role, repo_root=repo_root)
        for role, path in _manifest_input_spec(model_id, base_seed)
    ]
    if manifest.get("inputs") != expected_inputs:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT manifest inputs drifted: {model_id}/{base_seed}"
        )
    trainer_record = _plain_record(
        Path("src/experiments/train_closure_anfis_ablation.py"),
        role="trainer",
        repo_root=repo_root,
    )
    if manifest.get("script") != trainer_record or manifest.get("source_code") != [trainer_record]:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT trainer binding drifted: {model_id}/{base_seed}"
        )
    expected_outputs = [
        _plain_record(paths[name], role=name, repo_root=repo_root)
        for name in (
            "model", "checkpoint", "preprocessor", "training_curve",
            "selection_predictions", "selection_metrics", "report",
        )
    ]
    if manifest.get("outputs") != expected_outputs:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT manifest outputs drifted: {model_id}/{base_seed}"
        )
    from src.experiments.audit_closure_anfis_ablation_model_bundle import (
        AnfisAblationModelAuditError,
        validate_anfis_ablation_model_bundle_semantics,
    )

    try:
        validate_anfis_ablation_model_bundle_semantics(
            model_id=model_id,
            base_seed=base_seed,
            authority_binding=expected_authority,
            runtime=runtime_record,
            repo_root=repo_root,
            allow_pointer=_lexists(repo_root / _pointer_path(model_id, base_seed)),
            target_reference=target_reference,
        )
    except AnfisAblationModelAuditError as exc:
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT completed slot failed semantic audit: {model_id}/{base_seed}"
        ) from exc


def _validate_prediction_pointer(
    *, model_id: str, base_seed: int, repo_root: Path
) -> None:
    pointer_path = _pointer_path(model_id, base_seed)
    output_path = anfis_ablation_training_slot_paths(model_id, base_seed)[
        "selection_predictions"
    ]
    pointer = _load_yaml(pointer_path, repo_root=repo_root)
    outs = pointer.get("outs")
    payload = _read_regular_bytes(output_path, repo_root=repo_root)
    if (
        set(pointer) != {"outs"}
        or not isinstance(outs, list)
        or len(outs) != 1
        or not isinstance(outs[0], Mapping)
        or set(outs[0]) != {"md5", "size", "hash", "path"}
        or outs[0].get("md5")
        != hashlib.md5(payload, usedforsecurity=False).hexdigest()
        or outs[0].get("size") != len(payload)
        or outs[0].get("hash") != "md5"
        or outs[0].get("path") != output_path.name
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            f"E0-MT DVC pointer drifted: {pointer_path.as_posix()}"
        )


def _validate_exact_training_prefix(
    static: Mapping[str, Any], *, audit_mode: bool, repo_root: Path
) -> int:
    complete: list[bool] = []
    allowed_status_paths: set[str] = set()
    pointer_presence: list[bool] = []
    target_reference: Any | None = None
    for index, (model_id, base_seed) in enumerate(ORDERED_SLOTS):
        paths = anfis_ablation_training_slot_paths(model_id, base_seed)
        observed = [_lexists(repo_root / path) for path in paths.values()]
        if any(observed) and not all(observed):
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT partial slot exists: {model_id}/{base_seed}"
            )
        slot_complete = all(observed)
        complete.append(slot_complete)
        if slot_complete:
            if target_reference is None:
                from src.experiments.audit_closure_anfis_ablation_model_bundle import (
                    load_cutoff_target_reference,
                )

                target_reference = load_cutoff_target_reference(repo_root=repo_root)
            _validate_completed_slot(
                static,
                model_id=model_id,
                base_seed=base_seed,
                target_index=index,
                target_reference=target_reference,
                repo_root=repo_root,
            )
            allowed_status_paths.update(path.as_posix() for path in paths.values())
        pointer = _pointer_path(model_id, base_seed)
        pointer_present = _lexists(repo_root / pointer)
        pointer_presence.append(pointer_present)
        if pointer_present:
            allowed_status_paths.add(pointer.as_posix())
        prohibited = [
            *(_temporary_path(path) for path in paths.values()),
            Path(pointer.as_posix() + ".tmp"),
            _guard_path(model_id, base_seed),
        ]
        if any(_lexists(repo_root / path) for path in prohibited):
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT prohibited temporary/guard exists: {model_id}/{base_seed}"
            )
    prefix = 0
    while prefix < len(complete) and complete[prefix]:
        prefix += 1
    if any(complete[prefix:]):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT completed slots do not form the exact ordered prefix"
        )
    common_pairing_reference: tuple[str, str, str] | None = None
    for index, (model_id, base_seed) in enumerate(ORDERED_SLOTS):
        if not complete[index]:
            continue
        manifest = _load_json(
            anfis_ablation_training_slot_paths(model_id, base_seed)["manifest"],
            repo_root=repo_root,
        )
        pairing = manifest.get("pairing")
        if not isinstance(pairing, Mapping):
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT pairing evidence is absent: {model_id}/{base_seed}"
            )
        pairing_reference = (
            str(pairing.get("training_identity_sha256")),
            str(pairing.get("selection_identity_sha256")),
            str(pairing.get("selection_target_sha256")),
        )
        if common_pairing_reference is None:
            common_pairing_reference = pairing_reference
        elif pairing_reference != common_pairing_reference:
            raise AnfisAblationTrainingDevelopmentPatchError(
                "E0-MT common training/selection/target identity drifted across slots"
            )
    for seed_index, seed in enumerate(REGISTERED_SEEDS):
        a0_index = seed_index * 2
        a1_index = a0_index + 1
        if complete[a1_index]:
            a0_manifest = _load_json(
                anfis_ablation_training_slot_paths("A0", seed)["manifest"],
                repo_root=repo_root,
            )
            a1_manifest = _load_json(
                anfis_ablation_training_slot_paths("A1", seed)["manifest"],
                repo_root=repo_root,
            )
            a0_pairing = a0_manifest.get("pairing")
            a1_pairing = a1_manifest.get("pairing")
            pair_keys = (
                "training_identity_sha256", "selection_identity_sha256",
                "selection_target_sha256",
            )
            if (
                not isinstance(a0_pairing, Mapping)
                or not isinstance(a1_pairing, Mapping)
                or any(a0_pairing.get(key) != a1_pairing.get(key) for key in pair_keys)
            ):
                raise AnfisAblationTrainingDevelopmentPatchError(
                    f"E0-MT A0/A1 pairing drifted for seed {seed}"
                )
    if any(pointer_presence):
        if not audit_mode or prefix != 10 or not all(pointer_presence):
            raise AnfisAblationTrainingDevelopmentPatchError(
                "E0-MT DVC pointers must be absent or the complete post-audit set"
            )
        for model_id, base_seed in ORDERED_SLOTS:
            _validate_prediction_pointer(
                model_id=model_id, base_seed=base_seed, repo_root=repo_root
            )
        allowed_status_paths.add("models.dvc")
    if any(_lexists(repo_root / path) for path in E0_M_PATHS) or _lexists(
        repo_root / OUTCOME_ACCESS_LOG
    ):
        raise AnfisAblationTrainingDevelopmentPatchError(
            "E0-MT progression crossed E0-M/outcome boundary"
        )
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=all")
    for line in status.splitlines():
        if len(line) < 4 or line[:2] not in {"??", "A ", " M", "M "}:
            raise AnfisAblationTrainingDevelopmentPatchError(
                "E0-MT worktree contains an unsupported progression status"
            )
        if line[3:] not in allowed_status_paths:
            raise AnfisAblationTrainingDevelopmentPatchError(
                f"E0-MT worktree contains an unrelated path: {line[3:]}"
            )
    return prefix


def require_anfis_ablation_training_authority(
    model_id: str,
    base_seed: int,
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    return load_effective_anfis_ablation_training_authority(
        verify_remote=verify_remote,
        mode="audit" if audit_current_unpublished else "build",
        model_id=model_id,
        base_seed=base_seed,
        repo_root=repo_root,
    )
