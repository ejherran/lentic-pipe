"""Fail-closed E0-MV authority for ANFIS-ablation model manifests.

E0-MV is an additive governance overlay.  It preserves the one-shot A0/1729
bundle byte-for-byte under its historical P-E0-MU authority, fixes the
writer/consumer JSON-dialect mismatch, and authorizes only the next ordered
slot after a separately published P-E0-MV lock.

The module deliberately distinguishes two serializations:

* protocol locks and companions use compact, key-sorted canonical JSON;
* model manifests use the trainer/auditor dialect: two-space indentation,
  insertion order, one trailing newline, and the completion marker last.

No public writer accepts a caller-supplied payload, prelock snapshot, or
verification evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments import closure_contract
from src.experiments import closure_anfis_ablation_training_cohort_patch as mu
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = mu.PROJECT_ROOT
mt = mu.mt

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/anfis_ablation_model_manifest_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/anfis_ablation_model_manifest_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "anfis_ablation_model_manifest_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_anfis_ablation_model_manifest_patch/lock_bundle.guard"
)
LOCKER_PATH = Path(
    "src/experiments/lock_closure_anfis_ablation_model_manifest_patch.py"
)

BASE_COMMIT = "404983e3dfc511d982b2641aa4aea769dcbc6beb"
PATCH_GATE = "E0-MV"
EXPECTED_COMPANION_INPUT_COUNT = 72
EXPECTED_HISTORICAL_INPUT_COUNT = 4
MU_H_HEAD = "3fff3f272eb6f6ba8e644dd49436bc39ecbed1f8"
MU_H_PARENT = "1b68c24da4efe8fcf5eeb4b90ad0a99e95c96d93"
MU_P_HEAD = BASE_COMMIT

MU_LOCK_SHA256 = "8d574acf03abe92a5d759f9e0ff65c37e7455c3e24235dc8c1a60f3c6fe00a36"
MU_LOCK_BYTES = 31_693
MU_COMPANION_SHA256 = "e36ee7be07d659a93da0b5b13ef5ef9bd37ea1ee7df20928999fa7cba7e9f511"
MU_COMPANION_BYTES = 15_214

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): (
        "anfis_ablation_model_manifest_patch_lock_schema"
    ),
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_MANIFEST_PATCH_1.md": (
        "anfis_ablation_model_manifest_patch_protocol"
    ),
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": (
        "manifest_patch_anfis_ablation_model_bundle_auditor"
    ),
    "src/experiments/closure_anfis_ablation_model_manifest_patch.py": (
        "anfis_ablation_model_manifest_patch_validator"
    ),
    "src/data/prepare_commit_artifacts.py": (
        "manifest_patch_deferred_dvc_precommit_assistant"
    ),
    LOCKER_PATH.as_posix(): "anfis_ablation_model_manifest_patch_locker",
    "src/experiments/train_closure_anfis_ablation.py": (
        "manifest_patch_anfis_ablation_trainer"
    ),
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": (
        "manifest_patch_anfis_ablation_model_bundle_auditor_tests"
    ),
    "tests/test_closure_anfis_ablation_model_manifest_patch.py": (
        "anfis_ablation_model_manifest_patch_tests"
    ),
    "tests/test_train_closure_anfis_ablation.py": (
        "manifest_patch_anfis_ablation_trainer_tests"
    ),
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_COMPONENT_GIT_MODES = {
    path: (
        "100755"
        if path == "src/data/prepare_commit_artifacts.py"
        else "100644"
    )
    for path in PATCH_PATHS
}

SUPERSEDED_MU_PATHS = (
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py",
    "src/experiments/train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
    "tests/test_train_closure_anfis_ablation.py",
)
PRESERVED_MU_PATHS = tuple(
    path for path in mu.PATCH_PATHS if path not in SUPERSEDED_MU_PATHS
)
P_MU_COMPONENT_ROLES = {
    mu.DEFAULT_PATCH_LOCK_PATH.as_posix(): (
        "published_anfis_ablation_training_cohort_patch_lock"
    ),
    mu.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): (
        "published_anfis_ablation_training_cohort_patch_lock_manifest"
    ),
}
P_MU_PATHS = tuple(sorted(P_MU_COMPONENT_ROLES))

REGISTERED_SEEDS = mu.REGISTERED_SEEDS
ORDERED_SLOTS = mu.ORDERED_SLOTS
E0_M_PATHS = mu.E0_M_PATHS
OUTCOME_ACCESS_LOG = mu.OUTCOME_ACCESS_LOG
EMPTY_SHA256 = mu.EMPTY_SHA256
SHA1_RE = mu.SHA1_RE
SHA256_RE = mu.SHA256_RE

TYPE_CHECK_COMMAND = mu.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    ".venv/bin/python",
    "-m",
    "pytest",
    "-q",
    "tests/test_closure_anfis_ablation_model_manifest_patch.py",
    "tests/test_train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
)
FOCUSED_TEST_COUNT = 87
POETRY_CHECK_COMMAND = mu.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mu.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mu.DIFF_CHECK_COMMAND
FOCUSED_PYTEST_ENVIRONMENT = dict(mu.FOCUSED_PYTEST_ENVIRONMENT)
FOCUSED_SUMMARY_RE = re.compile(
    r"^(?P<count>[1-9][0-9]*) passed in (?P<seconds>[0-9]+\.[0-9]{2})s"
    r"(?: \((?P<clock>(?:[0-9]+ days?, )?[0-9]+:[0-9]{2}:[0-9]{2})\))?$"
)
FORBIDDEN_FOCUSED_SUMMARY_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed|errors?|failed)\b",
    flags=re.IGNORECASE,
)

LIGHT_SLOT_OUTPUT_NAMES = (
    "preprocessor",
    "training_curve",
    "selection_metrics",
    "report",
    "manifest",
)

UNPUBLISHED_AUTHORIZATIONS = {
    **mu.UNPUBLISHED_AUTHORIZATIONS,
    "model_bundle_audit_authorized": False,
}
LOCK_SEALS = {
    "historical_a0_bundle_preserved": True,
    "historical_a0_bundle_rewrite_forbidden": True,
    "historical_mu_authority_preserved": True,
    "model_manifest_dialect": "pretty_indent_2_insertion_order_newline",
    "completion_marker_written_last": True,
    "compact_sorted_manifest_dialect_rejected": True,
    "next_slot": {"model_id": "A1", "base_seed": 1729},
    "target_access_end": "2020-12",
    "calibration_2021_closed": True,
    "holdout_and_post_2021_closed": True,
    "ten_slots_individual_only": True,
    "dvc_absent": True,
    "outcomes_absent": True,
    "all_reconstructed_git_modes_100644": True,
}

HISTORICAL_A0_AUTHORITY = {
    "gate": "E0-MU",
    "status": "effective_preflight_passed",
    "h_patch_head": MU_H_HEAD,
    "p_patch_head": MU_P_HEAD,
    "h_components_sha256": (
        "6b4654ae79282bddd73e2e81f5f7d4686329130b4b2aeff27e128edc71bb0205"
    ),
    "physical_inputs_sha256": (
        "ebf054caacee9b73b61de4ad45f8bcf62e7800325bee8c40c88c3bed6010de60"
    ),
    "runtime_sha256": (
        "cf2cec52d9027db895e8859c7ffb321c831b66510132e137759e567b363f6a50"
    ),
    "lock_sha256": MU_LOCK_SHA256,
    "companion_sha256": MU_COMPANION_SHA256,
    "authorized_model_id": "A0",
    "authorized_base_seed": 1729,
    "completed_prefix_count": 0,
    "slot_creation_prefix_count": 0,
}

HISTORICAL_A0_FINAL_RECORDS = (
    {
        "role": "model",
        "path": "models/closure_v1/anfis_ablation/A0/seed_1729.pt",
        "bytes": 142_911,
        "sha256": "1e5c2c21b9cb69a4dfa9139fcd6058e57afd4922a19bd1b3cd071a6608897fef",
    },
    {
        "role": "checkpoint",
        "path": "models/closure_v1/anfis_ablation/A0/seed_1729.checkpoint.pt",
        "bytes": 142_911,
        "sha256": "0991ff130f694b69ae30bd37416d3ba2d63f67874b3d895976efb9e28c6ce277",
    },
    {
        "role": "preprocessor",
        "path": "reports/closure_v1/02_models/A0/seed_1729_preprocessor.json",
        "bytes": 2_472,
        "sha256": "ebffd11d392c62e68e2afbd3ee05febfd05a7411fc83ca18563c7773a51faa62",
    },
    {
        "role": "training_curve",
        "path": "reports/closure_v1/02_models/A0/seed_1729_training_curve.csv",
        "bytes": 2_588,
        "sha256": "edfb193302b0fe21708e1ff1556dcdcdf817948a8bd35cef2f90b16be9cc0ec0",
    },
    {
        "role": "selection_predictions",
        "path": (
            "data/closure_v1/development/anfis_ablation/A0/"
            "seed_1729_selection_predictions.parquet"
        ),
        "bytes": 64_842,
        "sha256": "6ca58207a32ba345fc4611c73a879e0546a608d7d076baf8f8da057373a3a4ae",
    },
    {
        "role": "selection_metrics",
        "path": "reports/closure_v1/02_models/A0/seed_1729_selection_metrics.csv",
        "bytes": 914,
        "sha256": "f6444a2047d2032334580f1322c4f61637a9028fd0aab27815a6c7386cf860eb",
    },
    {
        "role": "report",
        "path": "reports/closure_v1/02_models/A0/seed_1729_report.md",
        "bytes": 320,
        "sha256": "6e12b1d2fc0a1fce8baf7c1f81edbeb1bdd3d013d4365d606d21cc20399d123e",
    },
    {
        "role": "manifest",
        "path": "reports/closure_v1/02_models/A0/seed_1729_manifest.json",
        "bytes": 11_231,
        "sha256": "406bf44de3ecdc49ff3d5797cbca1ec0c11ebfbdc70ba262130b85a2e58e31e2",
    },
)
HISTORICAL_A0_LIGHT_PATHS = tuple(
    str(record["path"])
    for record in HISTORICAL_A0_FINAL_RECORDS
    if str(record["path"]).startswith("reports/")
)


class AnfisAblationModelManifestPatchError(RuntimeError):
    """Raised when E0-MV authority, history, or progression is not exact."""


def _translate(exc: BaseException) -> AnfisAblationModelManifestPatchError:
    return AnfisAblationModelManifestPatchError(
        str(exc).replace("E0-MT", "E0-MV").replace("E0-MU", "E0-MV")
    )


def _canonical_json(value: Any) -> bytes:
    """Canonical protocol JSON; model manifests intentionally use another dialect."""
    return mu._canonical_json(value)


def _model_manifest_json(value: Mapping[str, Any]) -> bytes:
    try:
        encoded = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV model manifest is not JSON-serializable"
        ) from exc
    return (encoded + "\n").encode("utf-8")


def _root(repo_root: Path | None = None) -> Path:
    return PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest_records(records: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_bytes(_canonical_json([dict(record) for record in records]))


def _exact_equal(actual: Any, expected: Any) -> bool:
    """Compare JSON-like values without Python's bool/int or int/float aliasing."""
    if isinstance(expected, Mapping):
        return (
            isinstance(actual, Mapping)
            and set(actual) == set(expected)
            and all(_exact_equal(actual[key], expected[key]) for key in expected)
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                _exact_equal(left, right)
                for left, right in zip(actual, expected, strict=True)
            )
        )
    if isinstance(expected, tuple):
        return (
            isinstance(actual, tuple)
            and len(actual) == len(expected)
            and all(
                _exact_equal(left, right)
                for left, right in zip(actual, expected, strict=True)
            )
        )
    return type(actual) is type(expected) and actual == expected


def _lexists(path: Path) -> bool:
    return mt._lexists(path)


def _is_regular_file_mode_0644(path: Path) -> bool:
    metadata = path.lstat()
    return (
        not path.is_symlink()
        and stat.S_ISREG(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) == 0o644
    )


def _read_regular_bytes(path: Path, *, repo_root: Path | None = None) -> bytes:
    try:
        return mt._read_regular_bytes(path, repo_root=_root(repo_root))
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _load_json(path: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    try:
        return mt._load_json(path, repo_root=_root(repo_root))
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _file_record(
    path: Path,
    *,
    role: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    try:
        return mt._file_record(path, role=role, repo_root=_root(repo_root))
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _git(repo_root: Path, *arguments: str) -> str:
    try:
        return mt._git(repo_root, *arguments)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _git_head(repo_root: Path, ref: str = "HEAD") -> str:
    try:
        return mt._git_head(repo_root, ref)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _single_parent(repo_root: Path, commit: str, *, context: str) -> str:
    fields = _git(repo_root, "rev-list", "--parents", "-n", "1", commit).split()
    if len(fields) != 2 or fields[0] != commit:
        raise AnfisAblationModelManifestPatchError(
            f"{context} must be a direct non-merge commit"
        )
    return fields[1]


def _git_scope(repo_root: Path, parent: str, head: str) -> dict[str, Any]:
    try:
        return mt._git_scope(repo_root, parent, head)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _git_mode(repo_root: Path, commit: str, path: str) -> str:
    try:
        return mt._git_mode(repo_root, commit, path)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _require_git_modes(
    repo_root: Path, commit: str, paths: Sequence[str], *, context: str
) -> None:
    drifted = [path for path in paths if _git_mode(repo_root, commit, path) != "100644"]
    if drifted:
        raise AnfisAblationModelManifestPatchError(
            f"{context} Git modes must all be 100644: {drifted}"
        )


def _require_exact_git_modes(
    repo_root: Path,
    commit: str,
    expected_modes: Mapping[str, str],
    *,
    context: str,
) -> None:
    actual = {
        path: _git_mode(repo_root, commit, path)
        for path in sorted(expected_modes)
    }
    expected = {
        path: expected_modes[path]
        for path in sorted(expected_modes)
    }
    if actual != expected:
        raise AnfisAblationModelManifestPatchError(
            f"{context} Git modes drifted: expected={expected}, actual={actual}"
        )


def _git_blob_record(
    repo_root: Path, commit: str, path: str, *, role: str
) -> dict[str, Any]:
    try:
        return mt._git_blob_record(repo_root, commit, path, role=role)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _plain_git_blob_record(
    repo_root: Path, commit: str, path: str, *, role: str
) -> dict[str, Any]:
    record = _git_blob_record(repo_root, commit, path, role=role)
    return {
        "role": role,
        "path": path,
        "bytes": record["bytes"],
        "sha256": record["sha256"],
    }


def _historical_git_blob_record(
    repo_root: Path, commit: str, path: str, *, role: str
) -> dict[str, Any]:
    record = _git_blob_record(repo_root, commit, path, role=role)
    record.update(
        {
            "commit": commit,
            "hash_source": "git_blob_at_commit",
            "current_bytes_required_to_match_historical": False,
        }
    )
    return record


def _live_remote_main_head(repo_root: Path) -> str:
    try:
        return mt._live_remote_main_head(repo_root)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV lock timestamp must be a string"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV lock timestamp is malformed"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV lock timestamp must include a timezone"
        )


def _strict_json(payload: bytes, *, label: str) -> dict[str, Any]:
    def reject_constant(value: str) -> Any:
        raise AnfisAblationModelManifestPatchError(
            f"{label} contains non-finite JSON: {value}"
        )

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AnfisAblationModelManifestPatchError(
                    f"{label} contains duplicate key: {key}"
                )
            result[key] = value
        return result

    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=unique_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnfisAblationModelManifestPatchError(
            f"{label} is not strict JSON"
        ) from exc
    if not isinstance(decoded, dict):
        raise AnfisAblationModelManifestPatchError(
            f"{label} must contain a JSON object"
        )
    return decoded


def _validate_role_record(value: Any) -> dict[str, Any]:
    try:
        return mt._validate_file_record(value)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _validate_mu_topology(repo_root: Path) -> None:
    expected_h_scope = {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "paths": list(mu.PATCH_PATHS),
    }
    expected_p_scope = {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "paths": list(P_MU_PATHS),
    }
    if (
        _single_parent(repo_root, MU_H_HEAD, context="H-E0-MU") != MU_H_PARENT
        or _git_scope(repo_root, MU_H_PARENT, MU_H_HEAD) != expected_h_scope
        or _single_parent(repo_root, MU_P_HEAD, context="P-E0-MU") != MU_H_HEAD
        or _git_scope(repo_root, MU_H_HEAD, MU_P_HEAD) != expected_p_scope
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV historical H/P-E0-MU topology drifted"
        )
    _require_git_modes(repo_root, MU_H_HEAD, mu.PATCH_PATHS, context="H-E0-MU")
    _require_git_modes(repo_root, MU_P_HEAD, P_MU_PATHS, context="P-E0-MU")


def _h_mv_components(head: str, repo_root: Path) -> list[dict[str, Any]]:
    records = [
        _file_record(Path(path), role=role, repo_root=repo_root)
        for path, role in sorted(PATCH_COMPONENT_ROLES.items())
    ]
    expected = [
        _plain_git_blob_record(repo_root, head, path, role=role)
        for path, role in sorted(PATCH_COMPONENT_ROLES.items())
    ]
    if records != expected:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV H components differ from their Git blobs"
        )
    return records


def _published_mu_bundle(
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Reconstruct P-E0-MU without invoking its now-superseded prefix loader."""
    _validate_mu_topology(repo_root)
    lock_bytes = _read_regular_bytes(mu.DEFAULT_PATCH_LOCK_PATH, repo_root=repo_root)
    companion_bytes = _read_regular_bytes(
        mu.DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=repo_root
    )
    lock = _strict_json(lock_bytes, label="P-E0-MU lock")
    companion = _strict_json(companion_bytes, label="P-E0-MU companion")
    if (
        len(lock_bytes) != MU_LOCK_BYTES
        or _sha256_bytes(lock_bytes) != MU_LOCK_SHA256
        or lock_bytes != _canonical_json(lock)
        or len(companion_bytes) != MU_COMPANION_BYTES
        or _sha256_bytes(companion_bytes) != MU_COMPANION_SHA256
        or companion_bytes != _canonical_json(companion)
    ):
        raise AnfisAblationModelManifestPatchError(
            "Published P-E0-MU lock/companion bytes drifted"
        )
    repository = lock.get("repository")
    h_patch = lock.get("h_patch")
    if (
        lock.get("gate") != "E0-MU"
        or lock.get("status") != "locked_unpublished"
        or not isinstance(repository, Mapping)
        or repository.get("head") != MU_H_HEAD
        or repository.get("parent") != MU_H_PARENT
        or not isinstance(h_patch, Mapping)
        or h_patch.get("head") != MU_H_HEAD
        or h_patch.get("component_count") != 9
    ):
        raise AnfisAblationModelManifestPatchError(
            "Published P-E0-MU lock identity drifted"
        )
    expected_h_components = [
        _plain_git_blob_record(repo_root, MU_H_HEAD, path, role=role)
        for path, role in sorted(mu.PATCH_COMPONENT_ROLES.items())
    ]
    if h_patch.get("components") != expected_h_components:
        raise AnfisAblationModelManifestPatchError(
            "Published P-E0-MU H component records drifted"
        )

    inputs = companion.get("inputs")
    historical_inputs = companion.get("historical_inputs")
    outputs = companion.get("outputs")
    if (
        companion.get("gate") != "E0-MU"
        or companion.get("status") != "completed"
        or companion.get("completion_marker_written_last") is not True
        or companion.get("manifest_written_last") is not True
        or companion.get("dvc_commands_run") is not False
        or not isinstance(inputs, list)
        or len(inputs) != 64
        or not isinstance(historical_inputs, list)
        or len(historical_inputs) != 4
        or not isinstance(outputs, list)
        or len(outputs) != 1
    ):
        raise AnfisAblationModelManifestPatchError(
            "Published P-E0-MU companion dialect drifted"
        )
    input_records = [_validate_role_record(record) for record in inputs]
    if (
        input_records != sorted(input_records, key=lambda record: str(record["path"]))
        or len({str(record["path"]) for record in input_records}) != 64
    ):
        raise AnfisAblationModelManifestPatchError(
            "Published P-E0-MU physical inputs are not exact and unique"
        )
    superseded = set(SUPERSEDED_MU_PATHS)
    for record in input_records:
        path = str(record["path"])
        if path in superseded:
            expected = _plain_git_blob_record(
                repo_root, MU_H_HEAD, path, role=str(record["role"])
            )
        else:
            expected = _file_record(
                Path(path), role=str(record["role"]), repo_root=repo_root
            )
        if record != expected:
            raise AnfisAblationModelManifestPatchError(
                f"Published P-E0-MU input drifted: {path}"
            )
    historical = [dict(record) for record in historical_inputs]
    if (
        len({str(record.get("path")) for record in historical}) != 4
        or any(record.get("hash_source") != "git_blob_at_commit" for record in historical)
        or any(
            record.get("current_bytes_required_to_match_historical") is not False
            for record in historical
        )
    ):
        raise AnfisAblationModelManifestPatchError(
            "Published P-E0-MU nested historical inputs drifted"
        )
    for record in historical:
        commit = record.get("commit")
        path = record.get("path")
        role = record.get("role")
        if not all(isinstance(value, str) for value in (commit, path, role)):
            raise AnfisAblationModelManifestPatchError(
                "Published P-E0-MU historical input identity is malformed"
            )
        expected_historical = _historical_git_blob_record(
            repo_root, str(commit), str(path), role=str(role)
        )
        if record != expected_historical:
            raise AnfisAblationModelManifestPatchError(
                f"Published P-E0-MU historical Git blob drifted: {path}"
            )
    lock_record = _file_record(
        mu.DEFAULT_PATCH_LOCK_PATH,
        role="anfis_ablation_training_cohort_patch_lock",
        repo_root=repo_root,
    )
    companion_record = _file_record(
        mu.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        role="anfis_ablation_training_cohort_patch_lock_manifest",
        repo_root=repo_root,
    )
    if outputs != [lock_record]:
        raise AnfisAblationModelManifestPatchError(
            "Published P-E0-MU companion output binding drifted"
        )
    companion_contract = lock.get("companion_contract")
    if (
        not isinstance(companion_contract, Mapping)
        or companion_contract.get("physical_input_count") != 64
        or companion_contract.get("historical_input_count") != 4
        or companion_contract.get("physical_inputs_sha256")
        != _digest_records(input_records)
        or companion_contract.get("historical_inputs_sha256")
        != _digest_records(historical)
        or companion.get("script")
        != next(
            (
                record
                for record in input_records
                if record["path"] == mu.LOCKER_PATH.as_posix()
            ),
            None,
        )
    ):
        raise AnfisAblationModelManifestPatchError(
            "Published P-E0-MU companion digest/script contract drifted"
        )
    return lock, companion, lock_record, companion_record


def _mu_authority(repo_root: Path) -> dict[str, Any]:
    lock, companion, lock_record, companion_record = _published_mu_bundle(repo_root)
    raw_inputs = cast(list[dict[str, Any]], companion["inputs"])
    preserved_inputs = [
        dict(record)
        for record in raw_inputs
        if str(record.get("path")) not in set(SUPERSEDED_MU_PATHS)
    ]
    historical = []
    by_path = {str(record.get("path")): record for record in raw_inputs}
    for path in SUPERSEDED_MU_PATHS:
        raw = by_path.get(path)
        if not isinstance(raw, Mapping):
            raise AnfisAblationModelManifestPatchError(
                f"P-E0-MU superseded input is absent: {path}"
            )
        record = _historical_git_blob_record(
            repo_root,
            MU_H_HEAD,
            path,
            role=f"superseded_mu_{raw['role']}",
        )
        if (
            record["bytes"] != raw.get("bytes")
            or record["sha256"] != raw.get("sha256")
        ):
            raise AnfisAblationModelManifestPatchError(
                f"P-E0-MU superseded Git blob drifted: {path}"
            )
        historical.append(record)
    historical.sort(key=lambda record: str(record["path"]))
    p_components = [
        _file_record(Path(path), role=role, repo_root=repo_root)
        for path, role in sorted(P_MU_COMPONENT_ROLES.items())
    ]
    return {
        "h_head": MU_H_HEAD,
        "h_parent": MU_H_PARENT,
        "h_scope": {"added": 5, "modified": 4, "deleted": 0},
        "p_head": MU_P_HEAD,
        "p_parent": MU_H_HEAD,
        "p_scope": {"added": 2, "modified": 0, "deleted": 0},
        "published_lock": lock_record,
        "published_companion": companion_record,
        "published_lock_payload_sha256": _sha256_bytes(_canonical_json(lock)),
        "published_companion_payload_sha256": _sha256_bytes(
            _canonical_json(companion)
        ),
        "preserved_physical_input_count": 60,
        "preserved_physical_inputs": preserved_inputs,
        "preserved_physical_inputs_sha256": _digest_records(preserved_inputs),
        "historical_component_count": 4,
        "historical_components": historical,
        "historical_components_sha256": _digest_records(historical),
        "p_component_count": 2,
        "p_components": p_components,
        "p_components_sha256": _digest_records(p_components),
        "h_components_git_mode": "100644",
        "p_components_git_mode": "100644",
    }


def _historical_a0_bundle(
    repo_root: Path, *, allow_registered_pointer: bool = False
) -> dict[str, Any]:
    if type(allow_registered_pointer) is not bool:
        raise AnfisAblationModelManifestPatchError(
            "Historical A0/1729 pointer policy must be an exact boolean"
        )
    expected = [dict(record) for record in HISTORICAL_A0_FINAL_RECORDS]
    actual = [
        _file_record(
            Path(str(record["path"])),
            role=str(record["role"]),
            repo_root=repo_root,
        )
        for record in expected
    ]
    if actual != expected:
        raise AnfisAblationModelManifestPatchError(
            "Historical A0/1729 final bytes drifted"
        )
    for record in expected:
        path = repo_root / str(record["path"])
        if not _is_regular_file_mode_0644(path):
            raise AnfisAblationModelManifestPatchError(
                f"Historical A0/1729 final is not regular mode 0644: {record['path']}"
            )
    manifest_path = Path(str(expected[-1]["path"]))
    manifest_bytes = _read_regular_bytes(manifest_path, repo_root=repo_root)
    manifest = _strict_json(manifest_bytes, label="historical A0/1729 manifest")
    if (
        not manifest
        or next(reversed(manifest)) != "completion_marker_written_last"
        or manifest_bytes != _model_manifest_json(manifest)
        or manifest.get("authority") != HISTORICAL_A0_AUTHORITY
        or manifest.get("model_id") != "A0"
        or manifest.get("base_seed") != 1729
        or manifest.get("status") != "completed"
        or manifest.get("slot_status") != "available"
        or manifest.get("fit_status") != "passed"
        or manifest.get("completion_marker_written_last") is not True
    ):
        raise AnfisAblationModelManifestPatchError(
            "Historical A0/1729 manifest dialect/authority drifted"
        )
    if not _exact_equal(manifest.get("outputs"), expected[:-1]):
        raise AnfisAblationModelManifestPatchError(
            "Historical A0/1729 manifest output records drifted"
        )
    historical_trainer = _plain_git_blob_record(
        repo_root,
        MU_H_HEAD,
        "src/experiments/train_closure_anfis_ablation.py",
        role="trainer",
    )
    if (
        not _exact_equal(manifest.get("script"), historical_trainer)
        or not _exact_equal(manifest.get("source_code"), [historical_trainer])
    ):
        raise AnfisAblationModelManifestPatchError(
            "Historical A0/1729 trainer source binding drifted"
        )
    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != 10:
        raise AnfisAblationModelManifestPatchError(
            "Historical A0/1729 input inventory drifted"
        )
    for raw in inputs:
        record = _validate_role_record(raw)
        if not _exact_equal(
            record,
            _file_record(
                Path(str(record["path"])),
                role=str(record["role"]),
                repo_root=repo_root,
            ),
        ):
            raise AnfisAblationModelManifestPatchError(
                f"Historical A0/1729 input drifted: {record['path']}"
            )
    authority_records = manifest.get("authority_records")
    expected_authority_records = [
        _file_record(
            Path("configs/closure_v1/anfis_ablation_training_development_runtime.yaml"),
            role="anfis_ablation_training_runtime_contract",
            repo_root=repo_root,
        ),
        _file_record(
            mu.DEFAULT_PATCH_LOCK_PATH,
            role="anfis_ablation_training_cohort_patch_lock",
            repo_root=repo_root,
        ),
        _file_record(
            mu.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="anfis_ablation_training_cohort_patch_lock_manifest",
            repo_root=repo_root,
        ),
    ]
    if not _exact_equal(authority_records, expected_authority_records):
        raise AnfisAblationModelManifestPatchError(
            "Historical A0/1729 authority records drifted"
        )
    mtimes = [
        (repo_root / str(record["path"])).lstat().st_mtime_ns for record in expected
    ]
    if mtimes[-1] <= max(mtimes[:-1]):
        raise AnfisAblationModelManifestPatchError(
            "Historical A0/1729 manifest is not physically last"
        )
    paths = mt.anfis_ablation_training_slot_paths("A0", 1729)
    prohibited = [
        *(mt._temporary_path(path) for path in paths.values()),
        mt._guard_path("A0", 1729),
        Path(f"{mt._pointer_path('A0', 1729).as_posix()}.tmp"),
    ]
    if not allow_registered_pointer:
        prohibited.append(mt._pointer_path("A0", 1729))
    occupied = [path.as_posix() for path in prohibited if _lexists(repo_root / path)]
    if occupied:
        raise AnfisAblationModelManifestPatchError(
            f"Historical A0/1729 prohibited namespace is occupied: {occupied}"
        )
    return {
        "model_id": "A0",
        "base_seed": 1729,
        "final_count": 8,
        "output_count": 8,
        "finals": expected,
        "finals_sha256": _digest_records(expected),
        "manifest": expected[-1],
        "manifest_dialect": "pretty_indent_2_insertion_order_newline",
        "manifest_completion_marker_last": True,
        "manifest_published_last": True,
        "historical_authority": dict(HISTORICAL_A0_AUTHORITY),
        "rewrite_forbidden": True,
        "dvc_pointer_present": False,
    }


def _training_namespace_state(repo_root: Path) -> dict[str, Any]:
    finals = mt._all_slot_paths()
    temporaries = tuple(mt._temporary_path(path) for path in finals)
    guards = tuple(mt._guard_path(model, seed) for model, seed in ORDERED_SLOTS)
    pointers = tuple(mt._pointer_path(model, seed) for model, seed in ORDERED_SLOTS)
    pointer_temporaries = tuple(Path(f"{path.as_posix()}.tmp") for path in pointers)
    final_present = [path.as_posix() for path in finals if _lexists(repo_root / path)]
    expected_present = [str(record["path"]) for record in HISTORICAL_A0_FINAL_RECORDS]
    state = {
        "completed_prefix_count": 1,
        "final_paths_present": final_present,
        "temporary_paths_present": [
            path.as_posix() for path in temporaries if _lexists(repo_root / path)
        ],
        "guard_paths_present": [
            path.as_posix() for path in guards if _lexists(repo_root / path)
        ],
        "prediction_pointers_present": [
            path.as_posix() for path in pointers if _lexists(repo_root / path)
        ],
        "prediction_pointer_temporaries_present": [
            path.as_posix()
            for path in pointer_temporaries
            if _lexists(repo_root / path)
        ],
        "output_namespace_sha256": _sha256_bytes(
            _canonical_json(
                [
                    *(path.as_posix() for path in finals),
                    *(path.as_posix() for path in temporaries),
                    *(path.as_posix() for path in guards),
                    *(path.as_posix() for path in pointers),
                    *(path.as_posix() for path in pointer_temporaries),
                ]
            )
        ),
    }
    occupied_prohibited = [
        path
        for key, values in state.items()
        if key.endswith("_present") and key != "final_paths_present"
        and isinstance(values, list)
        for path in values
    ]
    if final_present != expected_present or occupied_prohibited:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV training namespace is not the exact A0/1729 prefix"
        )
    return state


def _companion_physical_inputs(
    *, h_components: Sequence[Mapping[str, Any]], mu_authority: Mapping[str, Any]
) -> list[dict[str, Any]]:
    preserved = mu_authority.get("preserved_physical_inputs")
    p_components = mu_authority.get("p_components")
    if not isinstance(preserved, list) or not isinstance(p_components, list):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV companion source records are absent"
        )
    records = [
        *(dict(record) for record in preserved),
        *(dict(record) for record in p_components),
        *(dict(record) for record in h_components),
    ]
    records.sort(key=lambda record: str(record.get("path")))
    if (
        len(records) != 72
        or len({str(record.get("path")) for record in records}) != 72
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV companion must bind exactly 72 unique physical inputs"
        )
    return records


def preflight_anfis_ablation_model_manifest_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    encoded = _canonical_json(schema)
    forbidden = {"minimum", "maximum", "format", "minLength", "maxLength"}
    observed: set[str] = set()
    numeric_const_issues: list[str] = []

    def walk(value: Any, *, path: str = "$") -> None:
        if isinstance(value, Mapping):
            observed.update(str(key) for key in value)
            if "const" in value:
                constant = value["const"]
                if type(constant) in {int, float} and (
                    type(constant) is not int or value.get("type") != "integer"
                ):
                    numeric_const_issues.append(path)
            for key, child in value.items():
                walk(child, path=f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, path=f"{path}[{index}]")

    walk(schema)
    bad = sorted(forbidden.intersection(observed))
    subset_validator = getattr(closure_contract, "_assert_supported_json_schema", None)
    if not callable(subset_validator):
        raise AnfisAblationModelManifestPatchError(
            "Closure JSON-schema definition validator is unavailable"
        )
    try:
        subset_validator(schema)
    except ClosureContractError as exc:
        raise AnfisAblationModelManifestPatchError(str(exc)) from exc
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV schema properties are absent"
        )
    h_properties = cast(Mapping[str, Any], properties.get("h_patch", {})).get(
        "properties", {}
    )
    companion_properties = cast(
        Mapping[str, Any], properties.get("companion_contract", {})
    ).get("properties", {})
    definitions = cast(Mapping[str, Any], schema.get("$defs", {}))
    focused_definition = cast(
        Mapping[str, Any], definitions.get("focusedEvidence", {})
    )
    focused_properties = cast(
        Mapping[str, Any], focused_definition.get("properties", {})
    )
    mode_definition = cast(
        Mapping[str, Any], definitions.get("hComponentGitModes", {})
    )
    mode_properties = cast(
        Mapping[str, Any], mode_definition.get("properties", {})
    )
    schema_component_modes = {
        path: cast(Mapping[str, Any], mode_properties.get(path, {})).get("const")
        for path in PATCH_PATHS
    }
    if (
        bad
        or numeric_const_issues
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or cast(Mapping[str, Any], properties.get("gate", {})).get("const")
        != "E0-MV"
        or cast(Mapping[str, Any], h_properties).get("component_count", {}).get(
            "const"
        )
        != 10
        or cast(Mapping[str, Any], h_properties)
        .get("components_git_modes", {})
        .get("$ref")
        != "#/$defs/hComponentGitModes"
        or mode_definition.get("additionalProperties") is not False
        or mode_definition.get("required") != list(PATCH_PATHS)
        or schema_component_modes != PATCH_COMPONENT_GIT_MODES
        or cast(Mapping[str, Any], companion_properties)
        .get("physical_input_count", {})
        .get("const")
        != 72
        or cast(Mapping[str, Any], companion_properties)
        .get("historical_input_count", {})
        .get("const")
        != 4
        or cast(Mapping[str, Any], focused_properties.get("test_count", {})).get(
            "const"
        )
        != FOCUSED_TEST_COUNT
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV schema preflight drifted: "
            f"unsupported={bad}, numeric_consts={numeric_const_issues}"
        )
    return {
        "status": "schema_preflight_passed",
        "schema": _file_record(
            DEFAULT_PATCH_LOCK_SCHEMA,
            role="anfis_ablation_model_manifest_patch_lock_schema",
            repo_root=root,
        ),
        "canonical_schema_sha256": _sha256_bytes(encoded),
        "supported_subset_verified": True,
        "unsupported_semantic_keywords": [],
    }


def _control_namespace_state(repo_root: Path) -> dict[str, bool]:
    return {
        "mv_lock_absent": not _lexists(repo_root / DEFAULT_PATCH_LOCK_PATH),
        "mv_companion_absent": not _lexists(
            repo_root / DEFAULT_PATCH_LOCK_MANIFEST_PATH
        ),
        "mv_lock_temp_absent": not _lexists(
            repo_root / mt._temporary_path(DEFAULT_PATCH_LOCK_PATH)
        ),
        "mv_companion_temp_absent": not _lexists(
            repo_root / mt._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        ),
        "mv_locker_guard_absent": not _lexists(repo_root / LOCKER_GUARD_PATH),
        "p_mu_lock_present": _lexists(repo_root / mu.DEFAULT_PATCH_LOCK_PATH),
        "p_mu_companion_present": _lexists(
            repo_root / mu.DEFAULT_PATCH_LOCK_MANIFEST_PATH
        ),
        "p_mu_lock_temp_absent": not _lexists(
            repo_root / mt._temporary_path(mu.DEFAULT_PATCH_LOCK_PATH)
        ),
        "p_mu_companion_temp_absent": not _lexists(
            repo_root / mt._temporary_path(mu.DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        ),
        "p_mu_locker_guard_absent": not _lexists(repo_root / mu.LOCKER_GUARD_PATH),
    }


def _prohibited_namespace_state(repo_root: Path) -> dict[str, bool]:
    return {
        "e0_m_paths_absent": not any(
            _lexists(repo_root / path) for path in E0_M_PATHS
        ),
        "outcome_access_log_absent": not _lexists(repo_root / OUTCOME_ACCESS_LOG),
    }


def collect_anfis_ablation_model_manifest_patch_prelock_state(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    preflight_anfis_ablation_model_manifest_patch_schema(repo_root=root)
    head = _git_head(root)
    expected_scope = {
        "added": 5,
        "modified": 5,
        "deleted": 0,
        "paths": list(PATCH_PATHS),
    }
    if (
        _single_parent(root, head, context="H-E0-MV") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, head) != expected_scope
    ):
        raise AnfisAblationModelManifestPatchError(
            "H-E0-MV must be the exact 5M+5A child of P-E0-MU"
        )
    _require_exact_git_modes(
        root, head, PATCH_COMPONENT_GIT_MODES, context="H-E0-MV"
    )
    branch = _git(root, "branch", "--show-current").strip()
    tracking = _git_head(root, "origin/main")
    remote = _live_remote_main_head(root) if verify_remote else tracking
    if branch != "main" or tracking != head or remote != head:
        raise AnfisAblationModelManifestPatchError(
            "H-E0-MV refs are not aligned with main"
        )
    status_lines = [
        line
        for line in _git(
            root, "status", "--porcelain", "--untracked-files=all"
        ).splitlines()
        if line
    ]
    expected_status = [f"?? {path}" for path in sorted(HISTORICAL_A0_LIGHT_PATHS)]
    if status_lines != expected_status:
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV prelock worktree scope drifted: {status_lines}"
        )

    h_components = _h_mv_components(head, root)
    mu_authority = _mu_authority(root)
    historical_a0 = _historical_a0_bundle(root)
    namespace = _training_namespace_state(root)
    physical_inputs = _companion_physical_inputs(
        h_components=h_components, mu_authority=mu_authority
    )
    historical_inputs = cast(list[dict[str, Any]], mu_authority["historical_components"])
    control = _control_namespace_state(root)
    if not all(control.values()):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV/P-E0-MU control namespace drifted"
        )
    prohibited = _prohibited_namespace_state(root)
    if not all(prohibited.values()):
        raise AnfisAblationModelManifestPatchError(
            "E0-M or outcome namespace is present"
        )
    return {
        "repository": {
            "branch": branch,
            "head": head,
            "parent": BASE_COMMIT,
            "tracking_head": tracking,
            "remote_head": remote,
            "remote_verification_mode": (
                "live_remote_main_verified" if verify_remote else "tracking_ref_only"
            ),
            "worktree_scope": "exact_historical_a0_light_outputs_only",
        },
        "h_patch": {
            "base_commit": BASE_COMMIT,
            "head": head,
            "parent": BASE_COMMIT,
            "component_count": 10,
            "components": h_components,
            "components_sha256": _digest_records(h_components),
            "components_git_modes": dict(PATCH_COMPONENT_GIT_MODES),
            "scope": {"added": 5, "modified": 5, "deleted": 0},
        },
        "mu_authority": mu_authority,
        "adopted_a0_bundle": historical_a0,
        "manifest_dialect": {
            "encoding": "utf-8",
            "indent": 2,
            "ensure_ascii": False,
            "allow_nan": False,
            "sort_keys": False,
            "trailing_newline": True,
            "completion_marker_last": True,
            "historical_manifest_bytes": 11_231,
            "historical_manifest_sha256": str(
                HISTORICAL_A0_FINAL_RECORDS[-1]["sha256"]
            ),
            "legacy_compact_sorted_bytes": 9_019,
            "legacy_compact_sorted_sha256": (
                "25c70685524a8c7688e726466276c26a7823c53bd5aefa2087f20a7c8cfd35ce"
            ),
            "legacy_first_difference_offset": 1,
            "historical_rewrite_required": False,
        },
        "companion_contract": {
            "physical_input_count": 72,
            "historical_input_count": 4,
            "output_count": 1,
            "script_path": LOCKER_PATH.as_posix(),
            "physical_inputs_sha256": _digest_records(physical_inputs),
            "historical_inputs_sha256": _digest_records(historical_inputs),
            "historical_a0_outputs_in_inputs": False,
            "manifest_written_last": True,
        },
        "prelock": {
            **namespace,
            "historical_a0_finals_sha256": historical_a0["finals_sha256"],
            "control_paths": control,
            "prohibited_namespaces": prohibited,
        },
    }


def build_anfis_ablation_model_manifest_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    required = {
        "repository",
        "h_patch",
        "mu_authority",
        "adopted_a0_bundle",
        "manifest_dialect",
        "companion_contract",
        "prelock",
    }
    if set(prelock) != required:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV prelock bundle dialect drifted"
        )
    timestamp = created_at_utc or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "closure_anfis_ablation_model_manifest_patch_lock_v1",
        "status": "locked_unpublished",
        "gate": "E0-MV",
        "created_at_utc": timestamp,
        "repository": dict(prelock["repository"]),
        "h_patch": dict(prelock["h_patch"]),
        "mu_authority": dict(prelock["mu_authority"]),
        "adopted_a0_bundle": dict(prelock["adopted_a0_bundle"]),
        "manifest_dialect": dict(prelock["manifest_dialect"]),
        "companion_contract": dict(prelock["companion_contract"]),
        "prelock": dict(prelock["prelock"]),
        "verification": dict(verification),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
        "seals": dict(LOCK_SEALS),
    }


def _command_evidence(
    command: Sequence[str], stdout: str, stderr: str
) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": _sha256_bytes(stdout.encode("utf-8")),
        "stderr_sha256": _sha256_bytes(stderr.encode("utf-8")),
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": len(stderr.splitlines()),
    }


def _run_command(
    command: Sequence[str],
    *,
    repo_root: Path,
    sanitize_pytest_environment: bool = False,
) -> tuple[dict[str, Any], str, str]:
    environment = os.environ.copy()
    if sanitize_pytest_environment:
        environment.update(FOCUSED_PYTEST_ENVIRONMENT)
    result = subprocess.run(
        list(command),
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if result.returncode != 0:
        raise AnfisAblationModelManifestPatchError(
            f"Verification command failed ({result.returncode}): "
            f"{' '.join(command)}\n{result.stdout}\n{result.stderr}"
        )
    return _command_evidence(command, result.stdout, result.stderr), result.stdout, result.stderr


def _parse_focused_summary(stdout: str, stderr: str) -> dict[str, int]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    matches = [line for line in lines if FOCUSED_SUMMARY_RE.fullmatch(line)]
    match = FOCUSED_SUMMARY_RE.fullmatch(matches[0]) if len(matches) == 1 else None
    if (
        stderr.strip()
        or not lines
        or len(matches) != 1
        or matches[0] != lines[-1]
        or FORBIDDEN_FOCUSED_SUMMARY_RE.search(stdout + "\n" + stderr) is not None
        or match is None
        or int(match.group("count")) != FOCUSED_TEST_COUNT
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV focused pytest summary is not one clean result"
        )
    return {
        "test_count": FOCUSED_TEST_COUNT,
        "skipped_count": 0,
        "deselected_count": 0,
    }


def _audit_historical_a0_semantics(repo_root: Path) -> dict[str, Any]:
    """Run only the auditor's documented non-recursive, no-network core."""
    from src.experiments.audit_closure_anfis_ablation_model_bundle import (
        _load_runtime_contract,
        validate_anfis_ablation_model_bundle_semantics,
    )

    runtime, _ = _load_runtime_contract(repo_root)
    result = validate_anfis_ablation_model_bundle_semantics(
        model_id="A0",
        base_seed=1729,
        authority_binding=HISTORICAL_A0_AUTHORITY,
        runtime=runtime,
        repo_root=repo_root,
        allow_pointer=False,
        slot_source_record=_historical_trainer_record(repo_root),
    )
    required_false = (
        "calibration_targets_read",
        "test_or_holdout_targets_read",
        "future_outcomes_accessed",
        "dvc_command_executed",
        "scientific_network_egress",
        "writes_performed",
    )
    if (
        result.get("status") != "passed"
        or result.get("schema_exact") is not True
        or result.get("hash_bindings_verified") is not True
        or any(result.get(key) is not False for key in required_false)
    ):
        raise AnfisAblationModelManifestPatchError(
            "Historical A0/1729 semantic audit drifted"
        )
    return {
        "status": "passed",
        "model_id": "A0",
        "base_seed": 1729,
        "input_count": len(cast(Sequence[Any], result["inputs"])),
        "authority_record_count": len(
            cast(Sequence[Any], result["authority_records"])
        ),
        "source_code_count": len(cast(Sequence[Any], result["source_code"])),
        "output_count": len(cast(Sequence[Any], result["outputs"])),
        "schema_exact": True,
        "hash_bindings_verified": True,
        "calibration_targets_read": False,
        "test_or_holdout_targets_read": False,
        "future_outcomes_accessed": False,
        "dvc_command_executed": False,
        "scientific_network_egress": False,
        "writes_performed": False,
    }


def run_anfis_ablation_model_manifest_patch_verification(
    *,
    expected_schema_preflight: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    schema_preflight = preflight_anfis_ablation_model_manifest_patch_schema(
        repo_root=root
    )
    if (
        expected_schema_preflight is not None
        and dict(expected_schema_preflight) != schema_preflight
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV schema changed before verification"
        )
    full_type_check, stdout, stderr = _run_command(TYPE_CHECK_COMMAND, repo_root=root)
    if stdout != "All checks passed!\n" or stderr:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV full type-check output drifted"
        )
    focused_tests, stdout, stderr = _run_command(
        FOCUSED_TEST_COMMAND,
        repo_root=root,
        sanitize_pytest_environment=True,
    )
    focused_tests.update(_parse_focused_summary(stdout, stderr))
    focused_tests["stdout_text"] = stdout
    poetry_check, stdout, stderr = _run_command(POETRY_CHECK_COMMAND, repo_root=root)
    if stdout != "All set!\n" or stderr:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV poetry-check output drifted"
        )
    publication_guard, stdout, stderr = _run_command(
        PUBLICATION_GUARD_COMMAND, repo_root=root
    )
    if stdout != (
        "Checking tracked files before publication...\n"
        "OK: tracked files look publication-ready.\n"
    ) or stderr:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV publication-guard output drifted"
        )
    git_diff_check, stdout, stderr = _run_command(DIFF_CHECK_COMMAND, repo_root=root)
    if stdout or stderr:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV git diff-check output drifted"
        )
    historical_a0_semantic_audit = _audit_historical_a0_semantics(root)
    return {
        "schema_preflight": schema_preflight,
        "full_type_check": full_type_check,
        "focused_tests": focused_tests,
        "poetry_check": poetry_check,
        "publication_guard": publication_guard,
        "git_diff_check": git_diff_check,
        "historical_a0_semantic_audit": historical_a0_semantic_audit,
        "execution_boundaries": {
            "development_targets_through_2020_read_during_verification": True,
            "historical_a0_semantic_audit_run": True,
            "trainer_entrypoint_run": False,
            "model_fit_or_optimization_run": False,
            "auditor_entrypoint_run": False,
            "calibration_2021_targets_read_during_verification": False,
            "holdout_or_post_2021_targets_read_during_verification": False,
            "dvc_commands_run": False,
            "scientific_network_commands_run": False,
            "future_outcomes_accessed": False,
            "pytest_environment": dict(FOCUSED_PYTEST_ENVIRONMENT),
        },
    }


def _validate_command_evidence(
    value: Any,
    *,
    expected_command: Sequence[str],
    context: str,
    exact_stdout: str | None = None,
) -> None:
    keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV {context} evidence dialect drifted"
        )
    if (
        value.get("command") != list(expected_command)
        or type(value.get("returncode")) is not int
        or value.get("returncode") != 0
    ):
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV {context} command/result drifted"
        )
    if (
        any(
            not isinstance(value.get(key), str)
            or SHA256_RE.fullmatch(str(value[key])) is None
            for key in ("stdout_sha256", "stderr_sha256")
        )
        or any(
            type(value.get(key)) is not int or int(value[key]) < 0
            for key in ("stdout_line_count", "stderr_line_count")
        )
        or value.get("stderr_sha256") != EMPTY_SHA256
        or value.get("stderr_line_count") != 0
    ):
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV {context} digest/line evidence drifted"
        )
    if exact_stdout is not None and (
        value.get("stdout_sha256") != _sha256_bytes(exact_stdout.encode("utf-8"))
        or value.get("stdout_line_count") != len(exact_stdout.splitlines())
    ):
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV {context} stdout evidence drifted"
        )


def _validate_verification(value: Any, *, repo_root: Path) -> None:
    keys = {
        "schema_preflight",
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
        "historical_a0_semantic_audit",
        "execution_boundaries",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV verification dialect drifted"
        )
    if not _exact_equal(
        value.get("schema_preflight"),
        preflight_anfis_ablation_model_manifest_patch_schema(repo_root=repo_root),
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV schema-preflight evidence drifted"
        )
    _validate_command_evidence(
        value.get("full_type_check"),
        expected_command=TYPE_CHECK_COMMAND,
        context="full type check",
        exact_stdout="All checks passed!\n",
    )
    focused = value.get("focused_tests")
    focused_keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
        "stdout_text",
        "test_count",
        "skipped_count",
        "deselected_count",
    }
    if not isinstance(focused, Mapping) or set(focused) != focused_keys:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV focused-test evidence dialect drifted"
        )
    base_focused = {key: focused[key] for key in focused_keys if key not in {
        "stdout_text", "test_count", "skipped_count", "deselected_count"
    }}
    _validate_command_evidence(
        base_focused,
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused tests",
    )
    stdout_text = focused.get("stdout_text")
    if not isinstance(stdout_text, str):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV focused stdout is absent"
        )
    parsed = _parse_focused_summary(stdout_text, "")
    if (
        focused.get("stdout_sha256") != _sha256_bytes(stdout_text.encode("utf-8"))
        or focused.get("stdout_line_count") != len(stdout_text.splitlines())
        or any(
            type(focused.get(key)) is not int
            for key in ("test_count", "skipped_count", "deselected_count")
        )
        or {key: focused.get(key) for key in parsed} != parsed
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV focused-test stdout binding drifted"
        )
    _validate_command_evidence(
        value.get("poetry_check"),
        expected_command=POETRY_CHECK_COMMAND,
        context="poetry check",
        exact_stdout="All set!\n",
    )
    _validate_command_evidence(
        value.get("publication_guard"),
        expected_command=PUBLICATION_GUARD_COMMAND,
        context="publication guard",
        exact_stdout=(
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n"
        ),
    )
    _validate_command_evidence(
        value.get("git_diff_check"),
        expected_command=DIFF_CHECK_COMMAND,
        context="git diff check",
        exact_stdout="",
    )
    expected_audit = {
        "status": "passed",
        "model_id": "A0",
        "base_seed": 1729,
        "input_count": 10,
        "authority_record_count": 3,
        "source_code_count": 1,
        "output_count": 7,
        "schema_exact": True,
        "hash_bindings_verified": True,
        "calibration_targets_read": False,
        "test_or_holdout_targets_read": False,
        "future_outcomes_accessed": False,
        "dvc_command_executed": False,
        "scientific_network_egress": False,
        "writes_performed": False,
    }
    if not _exact_equal(value.get("historical_a0_semantic_audit"), expected_audit):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV historical A0 semantic-audit evidence drifted"
        )
    expected_boundaries = {
        "development_targets_through_2020_read_during_verification": True,
        "historical_a0_semantic_audit_run": True,
        "trainer_entrypoint_run": False,
        "model_fit_or_optimization_run": False,
        "auditor_entrypoint_run": False,
        "calibration_2021_targets_read_during_verification": False,
        "holdout_or_post_2021_targets_read_during_verification": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "future_outcomes_accessed": False,
        "pytest_environment": dict(FOCUSED_PYTEST_ENVIRONMENT),
    }
    if not _exact_equal(value.get("execution_boundaries"), expected_boundaries):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV verification execution boundaries drifted"
        )


def _expected_manifest_dialect() -> dict[str, Any]:
    return {
        "encoding": "utf-8",
        "indent": 2,
        "ensure_ascii": False,
        "allow_nan": False,
        "sort_keys": False,
        "trailing_newline": True,
        "completion_marker_last": True,
        "historical_manifest_bytes": 11_231,
        "historical_manifest_sha256": str(
            HISTORICAL_A0_FINAL_RECORDS[-1]["sha256"]
        ),
        "legacy_compact_sorted_bytes": 9_019,
        "legacy_compact_sorted_sha256": (
            "25c70685524a8c7688e726466276c26a7823c53bd5aefa2087f20a7c8cfd35ce"
        ),
        "legacy_first_difference_offset": 1,
        "historical_rewrite_required": False,
    }


def _expected_prelock() -> dict[str, Any]:
    finals = mt._all_slot_paths()
    temporaries = tuple(mt._temporary_path(path) for path in finals)
    guards = tuple(mt._guard_path(model, seed) for model, seed in ORDERED_SLOTS)
    pointers = tuple(mt._pointer_path(model, seed) for model, seed in ORDERED_SLOTS)
    pointer_temporaries = tuple(Path(f"{path.as_posix()}.tmp") for path in pointers)
    namespace = [
        *(path.as_posix() for path in finals),
        *(path.as_posix() for path in temporaries),
        *(path.as_posix() for path in guards),
        *(path.as_posix() for path in pointers),
        *(path.as_posix() for path in pointer_temporaries),
    ]
    return {
        "completed_prefix_count": 1,
        "final_paths_present": [
            str(record["path"]) for record in HISTORICAL_A0_FINAL_RECORDS
        ],
        "temporary_paths_present": [],
        "guard_paths_present": [],
        "prediction_pointers_present": [],
        "prediction_pointer_temporaries_present": [],
        "output_namespace_sha256": _sha256_bytes(_canonical_json(namespace)),
        "historical_a0_finals_sha256": _digest_records(
            [dict(record) for record in HISTORICAL_A0_FINAL_RECORDS]
        ),
        "control_paths": {
            "mv_lock_absent": True,
            "mv_companion_absent": True,
            "mv_lock_temp_absent": True,
            "mv_companion_temp_absent": True,
            "mv_locker_guard_absent": True,
            "p_mu_lock_present": True,
            "p_mu_companion_present": True,
            "p_mu_lock_temp_absent": True,
            "p_mu_companion_temp_absent": True,
            "p_mu_locker_guard_absent": True,
        },
        "prohibited_namespaces": {
            "e0_m_paths_absent": True,
            "outcome_access_log_absent": True,
        },
    }


def validate_anfis_ablation_model_manifest_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    allow_registered_pointers: bool = False,
    repo_root: Path | None = None,
) -> None:
    if type(allow_registered_pointers) is not bool:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV registered-pointer policy must be an exact boolean"
        )
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise AnfisAblationModelManifestPatchError(str(exc)) from exc
    _validate_timestamp(payload.get("created_at_utc"))
    if not _exact_equal(payload.get("authorizations"), UNPUBLISHED_AUTHORIZATIONS):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV unpublished authorizations drifted"
        )
    if not _exact_equal(payload.get("seals"), LOCK_SEALS):
        raise AnfisAblationModelManifestPatchError("E0-MV seals drifted")
    repository = payload.get("repository")
    h_patch = payload.get("h_patch")
    if not isinstance(repository, Mapping) or not isinstance(h_patch, Mapping):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV repository/H binding is absent"
        )
    h_head = repository.get("head")
    expected_scope = {
        "added": 5,
        "modified": 5,
        "deleted": 0,
        "paths": list(PATCH_PATHS),
    }
    if (
        repository.get("branch") != "main"
        or not isinstance(h_head, str)
        or SHA1_RE.fullmatch(h_head) is None
        or repository.get("parent") != BASE_COMMIT
        or repository.get("tracking_head") != h_head
        or repository.get("remote_head") != h_head
        or repository.get("remote_verification_mode") != "live_remote_main_verified"
        or repository.get("worktree_scope")
        != "exact_historical_a0_light_outputs_only"
        or _single_parent(root, h_head, context="H-E0-MV") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, h_head) != expected_scope
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV repository/H topology drifted"
        )
    _require_exact_git_modes(
        root, h_head, PATCH_COMPONENT_GIT_MODES, context="H-E0-MV"
    )
    h_components = _h_mv_components(h_head, root)
    expected_h = {
        "base_commit": BASE_COMMIT,
        "head": h_head,
        "parent": BASE_COMMIT,
        "component_count": 10,
        "components": h_components,
        "components_sha256": _digest_records(h_components),
        "components_git_modes": dict(PATCH_COMPONENT_GIT_MODES),
        "scope": {"added": 5, "modified": 5, "deleted": 0},
    }
    if not _exact_equal(h_patch, expected_h):
        raise AnfisAblationModelManifestPatchError("E0-MV H binding drifted")
    mu_authority = _mu_authority(root)
    if not _exact_equal(payload.get("mu_authority"), mu_authority):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV H/P-E0-MU reconstruction drifted"
        )
    adopted = _historical_a0_bundle(
        root, allow_registered_pointer=allow_registered_pointers
    )
    if not _exact_equal(payload.get("adopted_a0_bundle"), adopted):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV adopted A0/1729 binding drifted"
        )
    if not _exact_equal(payload.get("manifest_dialect"), _expected_manifest_dialect()):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV model-manifest dialect drifted"
        )
    physical_inputs = _companion_physical_inputs(
        h_components=h_components, mu_authority=mu_authority
    )
    historical = cast(list[dict[str, Any]], mu_authority["historical_components"])
    expected_companion_contract = {
        "physical_input_count": 72,
        "historical_input_count": 4,
        "output_count": 1,
        "script_path": LOCKER_PATH.as_posix(),
        "physical_inputs_sha256": _digest_records(physical_inputs),
        "historical_inputs_sha256": _digest_records(historical),
        "historical_a0_outputs_in_inputs": False,
        "manifest_written_last": True,
    }
    if not _exact_equal(payload.get("companion_contract"), expected_companion_contract):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV companion contract drifted"
        )
    if not _exact_equal(payload.get("prelock"), _expected_prelock()):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV complete prelock binding drifted"
        )
    _validate_verification(payload.get("verification"), repo_root=root)


def _expected_companion(
    payload: Mapping[str, Any],
    lock_record: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    h_patch = payload.get("h_patch")
    mu_authority = payload.get("mu_authority")
    if not isinstance(h_patch, Mapping) or not isinstance(mu_authority, Mapping):
        raise AnfisAblationModelManifestPatchError(
            "Cannot construct E0-MV companion sections"
        )
    h_components = h_patch.get("components")
    historical = mu_authority.get("historical_components")
    if not isinstance(h_components, list) or not isinstance(historical, list):
        raise AnfisAblationModelManifestPatchError(
            "Cannot construct E0-MV companion records"
        )
    inputs = _companion_physical_inputs(
        h_components=cast(list[dict[str, Any]], h_components),
        mu_authority=mu_authority,
    )
    historical_inputs = [dict(record) for record in historical]
    historical_inputs.sort(key=lambda record: str(record.get("path")))
    if (
        len(historical_inputs) != 4
        or len({str(record.get("path")) for record in historical_inputs}) != 4
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV companion must bind exactly four historical inputs"
        )
    script = next(
        (
            dict(record)
            for record in h_components
            if record.get("path") == LOCKER_PATH.as_posix()
        ),
        None,
    )
    if script is None:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV companion generating script is absent"
        )
    output = _validate_role_record(lock_record)
    if (
        output.get("path") != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or output.get("role") != "anfis_ablation_model_manifest_patch_lock"
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV companion lock output record drifted"
        )
    return {
        "manifest_version": (
            "closure_anfis_ablation_model_manifest_patch_lock_manifest_v1"
        ),
        "gate": "E0-MV",
        "status": "completed",
        "script": script,
        "inputs": inputs,
        "historical_inputs": historical_inputs,
        "historical_inputs_compared_to_current_paths": False,
        "outputs": [output],
        "physical_inputs_only": True,
        "historical_a0_outputs_in_inputs": False,
        "adopted_a0_bundle_rewritten": False,
        "manifest_written_last": True,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "scientific_network_commands_run": False,
        "historical_a0_semantic_audit_run": True,
        "trainer_entrypoint_run": False,
        "auditor_entrypoint_run": False,
        "model_fit_or_optimization_run": False,
        "calibration_2021_targets_read_during_verification": False,
        "holdout_or_post_2021_targets_read_during_verification": False,
        "future_outcomes_accessed": False,
        "completion_marker_written_last": True,
    }


def _revalidate_publication_state_under_guard(
    payload: Mapping[str, Any],
    *,
    repo_root: Path,
    expected_published_outputs: Sequence[Path],
) -> None:
    """Rehash every trusted input while the exclusive publisher guard is held."""
    repository = payload.get("repository")
    h_patch = payload.get("h_patch")
    mu_authority = payload.get("mu_authority")
    if not all(
        isinstance(section, Mapping)
        for section in (repository, h_patch, mu_authority)
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded publication sections are absent"
        )
    repository = cast(Mapping[str, Any], repository)
    h_patch = cast(Mapping[str, Any], h_patch)
    mu_authority = cast(Mapping[str, Any], mu_authority)
    h_head = repository.get("head")
    if (
        not isinstance(h_head, str)
        or _git_head(repo_root) != h_head
        or _git_head(repo_root, "origin/main") != h_head
        or _live_remote_main_head(repo_root) != h_head
        or _git(repo_root, "branch", "--show-current").strip() != "main"
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded Git refs drifted"
        )
    h_components = _h_mv_components(h_head, repo_root)
    if not _exact_equal(h_patch.get("components"), h_components):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded H components drifted"
        )
    live_mu = _mu_authority(repo_root)
    if not _exact_equal(dict(mu_authority), live_mu):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded P-E0-MU reconstruction drifted"
        )
    if not _exact_equal(
        payload.get("adopted_a0_bundle"), _historical_a0_bundle(repo_root)
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded adopted A0/1729 bundle drifted"
        )
    physical_inputs = _companion_physical_inputs(
        h_components=h_components, mu_authority=live_mu
    )
    contract = payload.get("companion_contract")
    if (
        not isinstance(contract, Mapping)
        or contract.get("physical_input_count") != 72
        or contract.get("physical_inputs_sha256") != _digest_records(physical_inputs)
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded 72-input digest drifted"
        )
    expected_prelock = payload.get("prelock")
    if not isinstance(expected_prelock, Mapping):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded prelock binding is absent"
        )
    live_namespace = _training_namespace_state(repo_root)
    if any(
        not _exact_equal(expected_prelock.get(key), value)
        for key, value in live_namespace.items()
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded training namespace drifted"
        )
    expected_controls = expected_prelock.get("control_paths")
    live_controls = _control_namespace_state(repo_root)
    p_mu_control_keys = {
        key for key in live_controls if key.startswith("p_mu_")
    }
    if (
        not isinstance(expected_controls, Mapping)
        or any(
            not _exact_equal(expected_controls.get(key), live_controls[key])
            for key in p_mu_control_keys
        )
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded P-E0-MU control namespace drifted"
        )
    live_prohibited = _prohibited_namespace_state(repo_root)
    if not _exact_equal(
        expected_prelock.get("prohibited_namespaces"), live_prohibited
    ) or not all(live_prohibited.values()):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded E0-M/outcome boundary drifted"
        )
    expected_paths = {
        *HISTORICAL_A0_LIGHT_PATHS,
        *(path.as_posix() for path in expected_published_outputs),
    }
    status_lines = [
        line
        for line in _git(
            repo_root, "status", "--porcelain", "--untracked-files=all"
        ).splitlines()
        if line
    ]
    if (
        any(len(line) < 4 or line[:2] != "??" for line in status_lines)
        or {line[3:] for line in status_lines} != expected_paths
    ):
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV guarded worktree scope drifted: {status_lines}"
        )
    controlled_temporaries = (
        mt._temporary_path(DEFAULT_PATCH_LOCK_PATH),
        mt._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
    )
    if any(_lexists(repo_root / path) for path in controlled_temporaries):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV guarded publication temporary appeared"
        )


def execute_and_publish_anfis_ablation_model_manifest_patch_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconstruct, verify once, and atomically publish P-E0-MV."""
    root = _root(repo_root)
    schema_preflight = preflight_anfis_ablation_model_manifest_patch_schema(
        repo_root=root
    )
    before = collect_anfis_ablation_model_manifest_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    verification = run_anfis_ablation_model_manifest_patch_verification(
        expected_schema_preflight=schema_preflight, repo_root=root
    )
    after = collect_anfis_ablation_model_manifest_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    if not _exact_equal(before, after):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV prelock state changed during verification"
        )
    payload = build_anfis_ablation_model_manifest_patch_lock_payload(
        before,
        verification,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    validate_anfis_ablation_model_manifest_patch_lock_payload(
        payload, repo_root=root
    )
    live_prelock = collect_anfis_ablation_model_manifest_patch_prelock_state(
        verify_remote=True, repo_root=root
    )
    for section in (
        "repository",
        "h_patch",
        "mu_authority",
        "adopted_a0_bundle",
        "manifest_dialect",
        "companion_contract",
        "prelock",
    ):
        if not _exact_equal(payload.get(section), live_prelock.get(section)):
            raise AnfisAblationModelManifestPatchError(
                f"E0-MV live prelock state drifted: {section}"
            )
    controlled = (
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mt._temporary_path(DEFAULT_PATCH_LOCK_PATH),
        mt._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        LOCKER_GUARD_PATH,
    )
    occupied = [path.as_posix() for path in controlled if _lexists(root / path)]
    if occupied:
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV lock namespace is occupied: {occupied}"
        )
    guard: mt._OwnedGuard | None = None
    published: list[mt._OwnedOutput] = []
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MV lock bundle publication in progress\n",
            repo_root=root,
        )
        _revalidate_publication_state_under_guard(
            payload, repo_root=root, expected_published_outputs=()
        )
        lock_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH,
            _canonical_json(dict(payload)),
            repo_root=root,
        )
        published.append(lock_output)
        lock_record = _file_record(
            DEFAULT_PATCH_LOCK_PATH,
            role="anfis_ablation_model_manifest_patch_lock",
            repo_root=root,
        )
        companion = _expected_companion(payload, lock_record, repo_root=root)
        companion_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            _canonical_json(companion),
            repo_root=root,
        )
        published.append(companion_output)
        if not _exact_equal(
            _load_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root), dict(payload)
        ):
            raise AnfisAblationModelManifestPatchError(
                "Published E0-MV lock differs from its payload"
            )
        if not _exact_equal(
            _load_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root), companion
        ):
            raise AnfisAblationModelManifestPatchError(
                "Published E0-MV companion differs from its payload"
            )
        for output in published:
            mt._validate_owned_output(output)
        _revalidate_publication_state_under_guard(
            payload,
            repo_root=root,
            expected_published_outputs=(
                DEFAULT_PATCH_LOCK_PATH,
                DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            ),
        )
        for output in published:
            mt._validate_owned_output(output)
        mt._release_publication_guard(guard)
        guard = None
        for output in published:
            mt._validate_owned_output(output)
        committed = True
        return dict(payload), companion
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        for output in reversed(published):
            mt._rollback_owned_output(output)
        raise _translate(exc) from exc
    except BaseException:
        for output in reversed(published):
            mt._rollback_owned_output(output)
        raise
    finally:
        if guard is not None:
            mt._release_publication_guard(guard, tolerate_foreign=True)
        if committed:
            for output in published:
                mt._close_owned_output(output)


def publish_anfis_ablation_model_manifest_patch_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Safe publisher; caller-supplied payload/evidence is never accepted."""
    return execute_and_publish_anfis_ablation_model_manifest_patch_lock_bundle(
        repo_root=repo_root
    )


def _validate_p_publication(
    payload: Mapping[str, Any], *, repo_root: Path
) -> dict[str, str]:
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("head"), str
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV H repository binding is absent"
        )
    h_head = str(repository["head"])
    head = _git_head(repo_root)
    tracking = _git_head(repo_root, "origin/main")
    remote = _live_remote_main_head(repo_root)
    expected_paths = sorted(
        (
            DEFAULT_PATCH_LOCK_PATH.as_posix(),
            DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
        )
    )
    if (
        _git(repo_root, "branch", "--show-current").strip() != "main"
        or _single_parent(repo_root, head, context="P-E0-MV") != h_head
        or tracking != head
        or remote != head
        or _git_scope(repo_root, h_head, head)
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "paths": expected_paths,
        }
    ):
        raise AnfisAblationModelManifestPatchError(
            "Published P-E0-MV topology/refs drifted"
        )
    _require_git_modes(repo_root, head, expected_paths, context="P-E0-MV")
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


def _static_effective_authority(
    payload: Mapping[str, Any],
    *,
    publication: Mapping[str, str],
    lock: Mapping[str, Any],
    companion: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    h_patch = cast(Mapping[str, Any], payload["h_patch"])
    companion_contract = cast(Mapping[str, Any], payload["companion_contract"])
    runtime = _file_record(
        Path("configs/closure_v1/anfis_ablation_training_development_runtime.yaml"),
        role="anfis_ablation_training_runtime_contract",
        repo_root=repo_root,
    )
    return {
        "gate": "E0-MV",
        "status": "effective_preflight_passed",
        "h_patch_head": publication["h_patch_head"],
        "p_patch_head": publication["p_patch_head"],
        "runtime": runtime,
        "lock": dict(lock),
        "companion": dict(companion),
        "h_components_sha256": h_patch["components_sha256"],
        "physical_inputs_sha256": companion_contract["physical_inputs_sha256"],
        "runtime_sha256": runtime["sha256"],
        "lock_sha256": lock["sha256"],
        "companion_sha256": companion["sha256"],
    }


def _slot_manifest_binding(
    static: Mapping[str, Any], *, model_id: str, base_seed: int, index: int
) -> dict[str, Any]:
    binding = {
        key: static[key]
        for key in (
            "gate",
            "status",
            "h_patch_head",
            "p_patch_head",
            "h_components_sha256",
            "physical_inputs_sha256",
            "runtime_sha256",
            "lock_sha256",
            "companion_sha256",
        )
    }
    binding.update(
        {
            "authorized_model_id": model_id,
            "authorized_base_seed": base_seed,
            "completed_prefix_count": index,
            "slot_creation_prefix_count": index,
        }
    )
    return binding


def _current_trainer_record(repo_root: Path) -> dict[str, Any]:
    return _file_record(
        Path("src/experiments/train_closure_anfis_ablation.py"),
        role="trainer",
        repo_root=repo_root,
    )


def _historical_trainer_record(repo_root: Path) -> dict[str, Any]:
    return _plain_git_blob_record(
        repo_root,
        MU_H_HEAD,
        "src/experiments/train_closure_anfis_ablation.py",
        role="trainer",
    )


def _validate_completed_mv_slot(
    static: Mapping[str, Any],
    *,
    model_id: str,
    base_seed: int,
    target_index: int,
    repo_root: Path,
    target_reference: Any,
    allow_pointer: bool = False,
) -> None:
    if type(allow_pointer) is not bool:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV completed-slot pointer policy must be an exact boolean"
        )
    paths = mt.anfis_ablation_training_slot_paths(model_id, base_seed)
    manifest_bytes = _read_regular_bytes(paths["manifest"], repo_root=repo_root)
    manifest = _strict_json(
        manifest_bytes, label=f"E0-MV model manifest {model_id}/{base_seed}"
    )
    expected_binding = _slot_manifest_binding(
        static, model_id=model_id, base_seed=base_seed, index=target_index
    )
    if (
        not manifest
        or next(reversed(manifest)) != "completion_marker_written_last"
        or manifest_bytes != _model_manifest_json(manifest)
        or not _exact_equal(manifest.get("authority"), expected_binding)
        or manifest.get("model_id") != model_id
        or manifest.get("base_seed") != base_seed
        or manifest.get("status") != "completed"
        or manifest.get("slot_status") != "available"
        or manifest.get("fit_status") != "passed"
        or manifest.get("completion_marker_written_last") is not True
    ):
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV completed slot manifest drifted: {model_id}/{base_seed}"
        )
    expected_outputs = [
        _file_record(path, role=name, repo_root=repo_root)
        for name, path in paths.items()
        if name != "manifest"
    ]
    if not _exact_equal(manifest.get("outputs"), expected_outputs):
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV completed slot outputs drifted: {model_id}/{base_seed}"
        )
    trainer = _current_trainer_record(repo_root)
    if not _exact_equal(manifest.get("script"), trainer) or not _exact_equal(
        manifest.get("source_code"), [trainer]
    ):
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV completed slot source drifted: {model_id}/{base_seed}"
        )
    expected_authority_records = [
        dict(static["runtime"]),
        dict(static["lock"]),
        dict(static["companion"]),
    ]
    if not _exact_equal(manifest.get("authority_records"), expected_authority_records):
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV completed slot authority records drifted: {model_id}/{base_seed}"
        )
    from src.experiments.audit_closure_anfis_ablation_model_bundle import (
        AnfisAblationModelAuditError,
        _load_runtime_contract,
        validate_anfis_ablation_model_bundle_semantics,
    )

    runtime, _ = _load_runtime_contract(repo_root)
    try:
        result = validate_anfis_ablation_model_bundle_semantics(
            model_id=model_id,
            base_seed=base_seed,
            authority_binding=expected_binding,
            runtime=runtime,
            repo_root=repo_root,
            allow_pointer=allow_pointer,
            target_reference=target_reference,
            slot_source_record=trainer,
        )
    except AnfisAblationModelAuditError as exc:
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV completed slot failed semantic audit: {model_id}/{base_seed}"
        ) from exc
    if (
        result.get("status") != "passed"
        or result.get("schema_exact") is not True
        or result.get("hash_bindings_verified") is not True
        or any(
            result.get(key) is not False
            for key in (
                "calibration_targets_read",
                "test_or_holdout_targets_read",
                "future_outcomes_accessed",
                "dvc_command_executed",
                "scientific_network_egress",
                "writes_performed",
            )
        )
    ):
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV completed slot semantic evidence drifted: {model_id}/{base_seed}"
        )


def _slot_light_paths(paths: Mapping[str, Path]) -> set[str]:
    if set(LIGHT_SLOT_OUTPUT_NAMES) - set(paths):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV slot path dialect is missing light outputs"
        )
    return {paths[name].as_posix() for name in LIGHT_SLOT_OUTPUT_NAMES}


def _validate_registered_prediction_pointer(
    *, model_id: str, base_seed: int, repo_root: Path
) -> None:
    try:
        mt._validate_prediction_pointer(
            model_id=model_id, base_seed=base_seed, repo_root=repo_root
        )
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _validate_exact_training_prefix(
    static: Mapping[str, Any], *, audit_mode: bool, repo_root: Path
) -> int:
    if type(audit_mode) is not bool:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV prefix audit mode must be an exact boolean"
        )
    complete: list[bool] = []
    pointer_presence: list[bool] = []
    slot_paths: list[dict[str, Path]] = []
    for index, (model_id, base_seed) in enumerate(ORDERED_SLOTS):
        paths = mt.anfis_ablation_training_slot_paths(model_id, base_seed)
        slot_paths.append(paths)
        observed = [_lexists(repo_root / path) for path in paths.values()]
        if any(observed) and not all(observed):
            raise AnfisAblationModelManifestPatchError(
                f"E0-MV partial slot exists: {model_id}/{base_seed}"
            )
        slot_complete = all(observed)
        complete.append(slot_complete)
        pointer = mt._pointer_path(model_id, base_seed)
        pointer_presence.append(_lexists(repo_root / pointer))
        prohibited = [
            *(mt._temporary_path(path) for path in paths.values()),
            mt._guard_path(model_id, base_seed),
            Path(f"{pointer.as_posix()}.tmp"),
        ]
        if any(_lexists(repo_root / path) for path in prohibited):
            raise AnfisAblationModelManifestPatchError(
                f"E0-MV prohibited temporary/guard exists: {model_id}/{base_seed}"
            )
    prefix = 0
    while prefix < len(complete) and complete[prefix]:
        prefix += 1
    if prefix < 1 or any(complete[prefix:]):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV completed slots do not form the exact adopted prefix"
        )
    registered = any(pointer_presence)
    if registered and (
        not audit_mode
        or prefix != len(ORDERED_SLOTS)
        or not all(pointer_presence)
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV pointers require the complete explicit post-registration audit"
        )
    target_reference: Any | None = None
    expected_light_paths: set[str] = set()
    for index, (model_id, base_seed) in enumerate(ORDERED_SLOTS[:prefix]):
        paths = slot_paths[index]
        expected_light_paths.update(_slot_light_paths(paths))
        if index == 0:
            _historical_a0_bundle(
                repo_root, allow_registered_pointer=registered
            )
        else:
            if target_reference is None:
                from src.experiments.audit_closure_anfis_ablation_model_bundle import (
                    load_cutoff_target_reference,
                )

                target_reference = load_cutoff_target_reference(
                    repo_root=repo_root
                )
            _validate_completed_mv_slot(
                static,
                model_id=model_id,
                base_seed=base_seed,
                target_index=index,
                repo_root=repo_root,
                target_reference=target_reference,
                allow_pointer=registered,
            )
        if registered:
            _validate_registered_prediction_pointer(
                model_id=model_id, base_seed=base_seed, repo_root=repo_root
            )
    if any(_lexists(repo_root / path) for path in E0_M_PATHS) or _lexists(
        repo_root / OUTCOME_ACCESS_LOG
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV progression crossed E0-M/outcome boundary"
        )
    status_lines = [
        line
        for line in _git(
            repo_root, "status", "--porcelain", "--untracked-files=all"
        ).splitlines()
        if line
    ]
    if not registered:
        expected_status = [f"?? {path}" for path in sorted(expected_light_paths)]
        if status_lines != expected_status:
            raise AnfisAblationModelManifestPatchError(
                f"E0-MV unregistered slot status drifted: {status_lines}"
            )
        return prefix
    allowed_registered_paths = {
        *expected_light_paths,
        *(mt._pointer_path(model, seed).as_posix() for model, seed in ORDERED_SLOTS),
        "models.dvc",
    }
    for line in status_lines:
        if (
            len(line) < 4
            or line[:2] not in {"??", "A ", " M", "M "}
            or line[3:] not in allowed_registered_paths
        ):
            raise AnfisAblationModelManifestPatchError(
                f"E0-MV post-registration worktree drifted: {line}"
            )
    return prefix


def _effective_authorizations(*, model_id: str, audit: bool) -> dict[str, bool]:
    return {
        "a0_development_fit_authorized": not audit and model_id == "A0",
        "a1_development_fit_authorized": not audit and model_id == "A1",
        "target_access_through_2020_authorized": True,
        "selection_diagnostics_authorized": True,
        "model_bundle_audit_authorized": audit,
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


def _summary_authorizations() -> dict[str, bool]:
    return {key: False for key in _effective_authorizations(model_id="A0", audit=False)}


def load_effective_anfis_ablation_model_manifest_authority(
    *,
    model_id: str | None = None,
    base_seed: int | None = None,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if type(audit_current_unpublished) is not bool:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV audit mode must be an exact boolean"
        )
    target_supplied = model_id is not None or base_seed is not None
    if target_supplied and (model_id is None or base_seed is None):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV target model/seed is incomplete"
        )
    if audit_current_unpublished and not target_supplied:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV audit mode requires one explicit target"
        )
    if target_supplied:
        if type(model_id) is not str or type(base_seed) is not int:
            raise AnfisAblationModelManifestPatchError(
                "E0-MV target model/seed types drifted"
            )
        try:
            mt.validate_model_seed(model_id, base_seed)
        except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
            raise _translate(exc) from exc
    if verify_remote is not True:
        raise AnfisAblationModelManifestPatchError(
            "E0-MV effective authority requires live remote verification"
        )
    root = _root(repo_root)
    payload_bytes = _read_regular_bytes(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    payload = _strict_json(payload_bytes, label="P-E0-MV lock")
    if payload_bytes != _canonical_json(payload):
        raise AnfisAblationModelManifestPatchError("E0-MV lock is not canonical JSON")
    pointer_presence = [
        _lexists(root / mt._pointer_path(slot_model, slot_seed))
        for slot_model, slot_seed in ORDERED_SLOTS
    ]
    allow_registered_pointers = (
        audit_current_unpublished and all(pointer_presence)
    )
    validate_anfis_ablation_model_manifest_patch_lock_payload(
        payload,
        allow_registered_pointers=allow_registered_pointers,
        repo_root=root,
    )
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="anfis_ablation_model_manifest_patch_lock",
        repo_root=root,
    )
    companion_bytes = _read_regular_bytes(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    companion_payload = _strict_json(companion_bytes, label="P-E0-MV companion")
    if (
        companion_bytes != _canonical_json(companion_payload)
        or not _exact_equal(
            companion_payload,
            _expected_companion(payload, lock_record, repo_root=root),
        )
    ):
        raise AnfisAblationModelManifestPatchError(
            "E0-MV lock companion drifted"
        )
    companion_record = _file_record(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        role="anfis_ablation_model_manifest_patch_lock_manifest",
        repo_root=root,
    )
    publication = _validate_p_publication(payload, repo_root=root)
    static = _static_effective_authority(
        payload,
        publication=publication,
        lock=lock_record,
        companion=companion_record,
        repo_root=root,
    )
    prefix = _validate_exact_training_prefix(
        static, audit_mode=audit_current_unpublished, repo_root=root
    )
    if model_id is None or base_seed is None:
        return {
            **static,
            **_summary_authorizations(),
            "authorized_model_id": None,
            "authorized_base_seed": None,
            "completed_prefix_count": prefix,
            "slot_creation_prefix_count": None,
            "audit_current_unpublished": False,
            "slot_manifest_authority": None,
            "slot_source_record": None,
            "ordered_slots": [
                {"model_id": slot_model, "base_seed": slot_seed}
                for slot_model, slot_seed in ORDERED_SLOTS
            ],
            "progression_policy": "exact_pretty_manifest_prefix_no_pointers_until_all_ten",
        }
    target_index = ORDERED_SLOTS.index((model_id, base_seed))
    valid_target = target_index < prefix if audit_current_unpublished else target_index == prefix
    if not valid_target:
        mode = "audit" if audit_current_unpublished else "build"
        raise AnfisAblationModelManifestPatchError(
            f"E0-MV target is not in the exact {mode} position"
        )
    if audit_current_unpublished and target_index == 0:
        slot_manifest_authority = dict(HISTORICAL_A0_AUTHORITY)
        slot_source_record = _historical_trainer_record(root)
    else:
        slot_manifest_authority = _slot_manifest_binding(
            static,
            model_id=model_id,
            base_seed=base_seed,
            index=target_index,
        )
        slot_source_record = _current_trainer_record(root)
    return {
        **static,
        **_effective_authorizations(model_id=model_id, audit=audit_current_unpublished),
        "authorized_model_id": model_id,
        "authorized_base_seed": base_seed,
        "completed_prefix_count": prefix,
        "slot_creation_prefix_count": target_index,
        "audit_current_unpublished": audit_current_unpublished,
        "slot_manifest_authority": slot_manifest_authority,
        "slot_source_record": slot_source_record,
        "ordered_slots": [
            {"model_id": slot_model, "base_seed": slot_seed}
            for slot_model, slot_seed in ORDERED_SLOTS
        ],
        "progression_policy": "exact_pretty_manifest_prefix_no_pointers_until_all_ten",
    }


def require_anfis_ablation_model_manifest_authority(
    model_id: str,
    base_seed: int,
    *,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    return load_effective_anfis_ablation_model_manifest_authority(
        model_id=model_id,
        base_seed=base_seed,
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )
