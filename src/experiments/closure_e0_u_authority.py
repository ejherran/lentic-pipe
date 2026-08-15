"""One-shot, stdlib-only authority for the Closure V1 E0-U boundary.

This module is intentionally definition-only at import time.  The sealed batch
runner authenticates its source before execution and calls the public functions
below without giving the authority access to a scientific import loader.  A
runtime-owned context builder is injected only after E0-U has been authorized.
"""

from __future__ import annotations


GATE = "E0-U"
EXPERIMENT_ID = "closure_v1"
ACTIVATION_SCHEMA_VERSION = "closure_e0_u_activation_v1"
ACCESS_LOG_SCHEMA_VERSION = "closure_e0_u_access_log_v1"
BASE_R_COMMIT = "4c92ed7249a91b7dd541fd22dde68b61574556b2"
ACTIVATION_MANIFEST_PATH = "reports/closure_v1/00_protocol/closure_e0_u_activation.json"
OUTCOME_ACCESS_LOG_PATH = "reports/closure_v1/00_protocol/outcome_access_log.jsonl"
RUN_GUARD_PATH = "tmp/closure_v1_e0_u/sealed_batch.guard"
AUTHORITY_SOURCE_PATH = "src/experiments/closure_e0_u_authority.py"
RUNNER_SOURCE_PATH = "src/experiments/run_closure_benchmark.py"
CONTEXT_BUILDER_SOURCE_PATH = "src/experiments/closure_phase3_context.py"
SEALED_BATCH_COMMAND = "/usr/bin/env -i LANG=C LC_ALL=C .venv/bin/python -I -S -B src/experiments/run_closure_benchmark.py --execute-sealed-batch\n"
LIVE_REMOTE_URL = "https://github.com/ejherran/lentic-pipe.git"
CONFIGURED_ORIGIN_URL = "git@github.com:ejherran/lentic-pipe.git"
GIT_EXECUTABLE_PATH = "/usr/bin/git"
ENV_EXECUTABLE_PATH = "/usr/bin/env"
GIT_EXECUTABLE_SHA256 = "93473c28694fd72bd889364107cd2770514de59780885a6a4aafca4d602e30ad"
ENV_EXECUTABLE_SHA256 = "08392d72874da4f88c619ee717f2b4a5f28ba0534ff8cf1083fb2edc37d6475f"
GIT_CONFIG_PATH = ".git/config"
GIT_CONFIG_SHA256 = "326855ec20dd2ab7c5a7573748b5ed437bedd930f362438b46ff857319b8cd7d"
GIT_REMOTE_HTTPS_HELPER_PATH = "/usr/lib/git-core/git-remote-https"
GIT_REMOTE_HTTP_HELPER_PATH = "/usr/lib/git-core/git-remote-http"
GIT_REMOTE_HTTP_SHA256 = "23f747f69b5293b9f531cc17205eab792eb92075e92f99a8d6bc2b51cf007230"
EXECUTABLE_UID = 65534
EXECUTABLE_GID = 65534
REPOSITORY_OWNER_UID = 1000
REPOSITORY_OWNER_GID = 1000
EXPECTED_ARTIFACT_COUNT = 52
EXPECTED_STAGE_COUNT = 10
EXPECTED_HEAVY_ARTIFACT_COUNT = 4
EXPECTED_COMPONENT_BINDINGS = (
    (
        "E2_site_transfer",
        "src.experiments.evaluate_site_transfer",
        "src/experiments/evaluate_site_transfer.py",
    ),
    (
        "E3_threshold_sensitivity",
        "src.experiments.evaluate_threshold_sensitivity",
        "src/experiments/evaluate_threshold_sensitivity.py",
    ),
    (
        "E4_reference_targets",
        "src.experiments.build_trophic_reference_targets",
        "src/experiments/build_trophic_reference_targets.py",
    ),
    (
        "E4_trophic_evaluation",
        "src.experiments.evaluate_trophic_state",
        "src/experiments/evaluate_trophic_state.py",
    ),
    (
        "E5_clustered_inference",
        "src.experiments.compare_models_clustered",
        "src/experiments/compare_models_clustered.py",
    ),
    (
        "E6_matched_degradation",
        "src.experiments.evaluate_matched_degradation",
        "src/experiments/evaluate_matched_degradation.py",
    ),
    (
        "E7_anfis_ablation",
        "src.experiments.evaluate_anfis_ablation",
        "src/experiments/evaluate_anfis_ablation.py",
    ),
    (
        "E8_uncertainty",
        "src.experiments.calibrate_uncertainty_closure",
        "src/experiments/calibrate_uncertainty_closure.py",
    ),
    (
        "E9_planning_inference",
        "src.experiments.evaluate_planning_inference",
        "src/experiments/evaluate_planning_inference.py",
    ),
    (
        "E10_evidence_matrix",
        "src.reporting.build_closure_evidence_matrix",
        "src/reporting/build_closure_evidence_matrix.py",
    ),
)
EXPECTED_P_SCOPE_PATHS = (
    "data/closure_v1/locked_evaluation/adaptive_state_warmup.parquet.dvc",
    "data/closure_v1/locked_evaluation/phase3_runtime_weights.npz.dvc",
    "reports/closure_v1/00_protocol/software_evidence_source/end_to_end_report.md",
    "reports/closure_v1/00_protocol/software_evidence_source/environment.json",
    "reports/closure_v1/00_protocol/software_evidence_source/openapi.json",
    "reports/closure_v1/00_protocol/software_evidence_source/openapi_contract_report.md",
    "reports/closure_v1/00_protocol/software_evidence_source/public_tests.xml",
    "reports/closure_v1/00_protocol/software_evidence_source/software_evidence_source_manifest.json",
    "reports/closure_v1/00_protocol/software_evidence_source/test_report.md",
    "reports/closure_v1/01_surface/phase3_input_overlay_manifest.json",
)
PHASE3_OVERLAY_MANIFEST_PATH = (
    "reports/closure_v1/01_surface/phase3_input_overlay_manifest.json"
)
PHASE3_OVERLAY_BUILDER_PATH = (
    "src/experiments/build_closure_phase3_input_overlay.py"
)
PHASE3_OVERLAY_OUTPUTS = (
    (
        "data/closure_v1/locked_evaluation/phase3_runtime_weights.npz",
        "phase3_runtime_weights",
    ),
    (
        "data/closure_v1/locked_evaluation/adaptive_state_warmup.parquet",
        "adaptive_state_warmup",
    ),
)
PHASE3_OVERLAY_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
PHASE3_OVERLAY_HISTORY_PATH = (
    "data/closure_v1/locked_evaluation/input_history.parquet"
)
PHASE3_OVERLAY_PANEL_PATH = "data/panel/panel_monthly_v0.parquet"
PHASE3_OVERLAY_NPZ_INDEX_VERSION = "closure_phase3_numpy_state_dict_index_v1"
PHASE3_OVERLAY_PARITY_FIXTURE_VERSION = "deterministic_arithmetic_grid_v1"
PHASE3_OVERLAY_PARITY_ATOL = 0.000002
PHASE3_OVERLAY_PARITY_RTOL = 0.000002
PHASE3_OVERLAY_PHYSICAL_COLUMNS = (
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
PHASE3_OVERLAY_CALENDAR_COLUMNS = (
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
)
PHASE3_OVERLAY_PANEL_SEASON_COLUMNS = (
    "season_sin_1",
    "season_cos_1",
    "season_sin_2",
    "season_cos_2",
)
PHASE3_OVERLAY_HISTORY_PROJECTION = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "assignment_role",
    "history_year_month",
)
PHASE3_OVERLAY_PANEL_PROJECTION = (
    "source_id",
    "site_id",
    "year_month",
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
    "season_sin_1",
    "season_cos_1",
    "season_sin_2",
    "season_cos_2",
)
PHASE3_OVERLAY_DEEP_VALIDATION_KEYS = (
    "builder_source",
    "checkpoint_count",
    "checkpoint_identity_revalidated",
    "expected_h_commit",
    "experiment_id",
    "gate",
    "history_projection",
    "manifest",
    "manifest_regenerated_byte_equality",
    "npz_regenerated_byte_equality",
    "numpy_torch_parity_recomputed",
    "opened_outcome_path_count",
    "opened_target_path_count",
    "panel_projection",
    "physical_outputs",
    "projection_contains_chlorophyll",
    "projection_contains_target",
    "schema_version",
    "source_input_count",
    "source_inputs",
    "source_inputs_sha256",
    "state_dict_array_count",
    "status",
    "surface_id",
    "warmup_projection_recomputed",
    "warmup_regenerated_byte_equality",
    "warmup_row_count",
    "warmup_site_count",
    "writes_performed",
)
PHASE3_OVERLAY_WARMUP_COLUMNS = (
    "source_id",
    "site_id",
    "year_month",
    "row_present",
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
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
)
PHASE3_OVERLAY_MANIFEST_KEYS = (
    "experiment_id",
    "gate",
    "input_only",
    "inputs",
    "manifest_version",
    "numpy_export",
    "outcome_isolation",
    "outputs",
    "physical_outputs",
    "publication",
    "publication_status",
    "repository_head",
    "script",
    "source_inputs",
    "status",
    "surface_id",
    "warmup",
)
AUTHORITY_RESULT_KEYS = (
    "effective_authority",
    "e0_m_authorized",
    "e0_u_authorized",
    "evaluation_authorized",
    "gate",
    "historical_e0_m_commit",
    "outcome_access_authorized",
    "phase3_activation_commit",
    "phase3_code_commit",
    "phase3_evidence_commit",
    "sealed_authority_source_record",
    "sealed_batch_command",
    "sealed_batch_execution_authorized",
    "sealed_component_source_records",
    "sealed_context_builder_source_record",
    "sealed_env_executable_record",
    "sealed_git_executable_record",
    "sealed_runner_source_record",
    "sealed_runtime_environment_record",
    "sealed_support_source_records",
    "writes_performed",
)
ACTIVATION_MANIFEST_KEYS = (
    "base_r_commit",
    "dvc_policy",
    "execution_id",
    "experiment_id",
    "expected_artifact_paths_sha256",
    "expected_publication_order_sha256",
    "gate",
    "git_remote_url",
    "h_commit",
    "h_scope",
    "p_commit",
    "p_scope",
    "phase3_overlay_deep_validation",
    "schema_version",
    "sealed_batch_command",
    "sealed_batch_contract_sha256",
    "sealed_component_source_records",
    "sealed_context_builder_source_record",
    "sealed_runner_source_record",
    "sealed_runtime_environment_record",
    "sealed_support_source_records",
)
SCOPE_RECORD_KEYS = ("bytes", "mode", "path", "sha256", "status")
DVC_POLICY_KEYS = (
    "direct_git_artifact_paths",
    "dvc_add_after_success_only",
    "dvc_pointer_paths",
    "dvc_push_after_audit_only",
    "heavy_artifact_paths",
    "implicit_dvc_forbidden",
)
PUBLICATION_RECEIPT_KEYS = (
    "artifact_count",
    "batch_contract_sha256",
    "execution_id",
    "guard_released",
    "manifest_written_last",
    "one_shot_consumed",
    "published_artifact_paths_sha256",
    "rollback_performed",
    "stage_count",
    "status",
    "writes_performed",
)
PUBLICATION_AUDIT_KEYS = (
    "artifact_count",
    "artifact_payloads_sha256",
    "batch_contract_sha256",
    "execution_id",
    "guard_released",
    "manifest_written_last",
    "one_shot_consumed",
    "physical_records",
    "physical_records_sha256",
    "publication_guard_present",
    "publication_order",
    "publication_order_sha256",
    "published_artifact_paths_sha256",
    "rollback_performed",
    "stage_count",
    "status",
    "writes_performed",
)
PHYSICAL_RECORD_KEYS = (
    "bytes",
    "ctime_ns",
    "device",
    "inode",
    "mode",
    "mtime_ns",
    "nlink",
    "path",
    "sha256",
)
_STATE: dict[str, object] = {
    "required": False,
    "opened": False,
    "published": False,
    "failed": False,
    "repo_root": None,
    "repo_root_identity": None,
    "manifest": None,
    "public_authority": None,
    "contract_sha256": None,
    "execution_id": None,
    "expected_artifact_paths": None,
    "expected_publication_order": None,
    "manifest_last_paths": None,
    "stage_count": None,
    "guard_fd": None,
    "guard_record": None,
    "guard_parent_anchor": None,
    "guard_owned_directories": None,
    "published_records": None,
    "publication_receipt": None,
    "access_log_identity": None,
    "access_log_lease": None,
}


def _fail(message: str):
    raise RuntimeError("Closure E0-U authority rejected operation: " + message)


def _canonical_json_bytes(value):
    import json

    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Closure E0-U value is not canonical JSON") from exc


def _sha256_bytes(payload):
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_relative_parts(value):
    from pathlib import Path

    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        _fail("path is not a canonical repository-relative string")
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
        or path.as_posix() != value
    ):
        _fail("path escaped the canonical repository namespace: " + value)
    return tuple(path.parts)


def _resolved_repo_root(repo_root):
    import os
    import stat
    from pathlib import Path

    root = Path(repo_root).resolve(strict=True)
    before = os.lstat(root)
    descriptor = os.open(
        root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        not stat.S_ISDIR(before.st_mode)
        or (before.st_dev, before.st_ino, before.st_mode)
        != (opened.st_dev, opened.st_ino, opened.st_mode)
    ):
        _fail("repository root is not an anchored directory")
    return root


def _repository_root_identity(repo_root):
    import os
    import stat

    named = os.lstat(repo_root)
    descriptor = _open_root_directory(repo_root)
    try:
        opened = os.fstat(descriptor)
        identity = _directory_identity(opened)
    finally:
        os.close(descriptor)
    if (
        stat.S_ISLNK(named.st_mode)
        or not stat.S_ISDIR(named.st_mode)
        or not stat.S_ISDIR(opened.st_mode)
        or _directory_identity(named) != identity
    ):
        _fail("repository root identity is not anchored")
    return identity


def _open_root_directory(repo_root):
    import os

    return os.open(
        repo_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )


def _open_parent_directory(repo_root, relative_path, create, owned_directories):
    import os
    import stat

    parts = _canonical_relative_parts(relative_path)
    descriptor = _open_root_directory(repo_root)
    traversed = []
    try:
        for part in parts[:-1]:
            traversed.append(part)
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
            try:
                child = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, mode=0o755, dir_fd=descriptor)
                child = os.open(part, flags, dir_fd=descriptor)
                metadata = os.fstat(child)
                if not stat.S_ISDIR(metadata.st_mode):
                    os.close(child)
                    _fail("created publication parent is not a directory")
                owned_directories.append(
                    {
                        "path": "/".join(traversed),
                        "device": int(metadata.st_dev),
                        "inode": int(metadata.st_ino),
                    }
                )
                os.fsync(descriptor)
            parent_metadata = os.fstat(descriptor)
            child_metadata = os.fstat(child)
            if (
                not stat.S_ISDIR(parent_metadata.st_mode)
                or not stat.S_ISDIR(child_metadata.st_mode)
            ):
                os.close(child)
                _fail("publication parent walk encountered a non-directory")
            os.close(descriptor)
            descriptor = child
        return descriptor, parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def _directory_identity(metadata):
    import stat

    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        stat.S_IMODE(metadata.st_mode),
    )


def _open_parent_directory_anchor(
    repo_root,
    relative_path,
    create,
    owned_directories,
    expected_root_identity=None,
):
    import os
    import stat

    parts = _canonical_relative_parts(relative_path)
    directory_flags = (
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    )
    descriptors = []
    bindings = []
    created_records = []
    try:
        named_root = os.lstat(repo_root)
        root_fd = os.open(repo_root, directory_flags)
        descriptors.append(root_fd)
        opened_root = os.fstat(root_fd)
        root_identity = _directory_identity(opened_root)
        if (
            stat.S_ISLNK(named_root.st_mode)
            or not stat.S_ISDIR(named_root.st_mode)
            or not stat.S_ISDIR(opened_root.st_mode)
            or _directory_identity(named_root) != root_identity
        ):
            _fail("publication repository root is not an anchored directory")
        if (
            expected_root_identity is not None
            and root_identity != expected_root_identity
        ):
            _fail("repository root changed after authority require")
        current = root_fd
        traversed = []
        for component in parts[:-1]:
            traversed.append(component)
            created = False
            try:
                named = os.stat(
                    component,
                    dir_fd=current,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(component, mode=0o755, dir_fd=current)
                os.fsync(current)
                named = os.stat(
                    component,
                    dir_fd=current,
                    follow_symlinks=False,
                )
                created = True
            if stat.S_ISLNK(named.st_mode) or not stat.S_ISDIR(named.st_mode):
                _fail("publication parent walk encountered a non-directory")
            if created:
                record = {
                    "path": "/".join(traversed),
                    "device": int(named.st_dev),
                    "inode": int(named.st_ino),
                    "_parent_fd": current,
                    "_leaf": component,
                }
                owned_directories.append(record)
                created_records.append(record)
            child = os.open(component, directory_flags, dir_fd=current)
            opened = os.fstat(child)
            identity = _directory_identity(opened)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or _directory_identity(named) != identity
            ):
                os.close(child)
                _fail("publication parent directory identity drifted")
            descriptors.append(child)
            bindings.append((current, component, child, identity))
            current = child
        anchor = {
            "repo_root": repo_root,
            "descriptors": descriptors,
            "bindings": bindings,
            "root_identity": root_identity,
            "leaf": parts[-1],
            "closed": False,
        }
        _recapture_parent_directory_anchor(
            anchor,
            "publication parent " + relative_path,
        )
        return anchor
    except BaseException as exc:
        rollback_error = None
        try:
            _rollback_owned_directories(repo_root, created_records)
        except BaseException as cleanup_exc:
            rollback_error = cleanup_exc
        finally:
            for record in created_records:
                if record in owned_directories:
                    owned_directories.remove(record)
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        if rollback_error is not None:
            raise RuntimeError(
                "Closure E0-U publication parent cleanup was incomplete"
            ) from rollback_error
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(
            "Closure E0-U publication parent cannot be opened without "
            "following names: " + relative_path
        ) from exc


def _recapture_parent_directory_anchor(anchor, label):
    import os
    import stat

    if not isinstance(anchor, dict) or anchor.get("closed"):
        _fail(label + " anchor is closed")
    try:
        descriptors = anchor["descriptors"]
        named_root = os.lstat(anchor["repo_root"])
        if (
            stat.S_ISLNK(named_root.st_mode)
            or _directory_identity(named_root) != anchor["root_identity"]
            or _directory_identity(os.fstat(descriptors[0]))
            != anchor["root_identity"]
        ):
            _fail(label + " repository root was replaced")
        for parent, component, child, identity in anchor["bindings"]:
            named = os.stat(
                component,
                dir_fd=parent,
                follow_symlinks=False,
            )
            if (
                stat.S_ISLNK(named.st_mode)
                or _directory_identity(named) != identity
                or _directory_identity(os.fstat(child)) != identity
            ):
                _fail(label + " ancestor was replaced")
    except RuntimeError:
        raise
    except OSError as exc:
        raise RuntimeError(
            "Closure E0-U authority rejected operation: "
            + label
            + " ancestor recapture failed"
        ) from exc


def _close_parent_directory_anchor(anchor):
    import os

    if not isinstance(anchor, dict) or anchor.get("closed"):
        return
    for descriptor in reversed(anchor["descriptors"]):
        try:
            os.close(descriptor)
        except OSError:
            pass
    anchor["descriptors"].clear()
    anchor["closed"] = True


def _anchor_parent_fd(anchor):
    if not isinstance(anchor, dict) or anchor.get("closed"):
        _fail("publication parent anchor is closed")
    descriptors = anchor.get("descriptors")
    if not isinstance(descriptors, list) or not descriptors:
        _fail("publication parent anchor is malformed")
    return descriptors[-1]


def _read_regular_relative(repo_root, relative_path, expected_mode, expected_nlink):
    import os
    import stat

    parts = _canonical_relative_parts(relative_path)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    directories = []
    directory_bindings = []
    descriptor = None
    try:
        named_root = os.lstat(repo_root)
        current = _open_root_directory(repo_root)
        opened_root = os.fstat(current)
        root_identity = (
            opened_root.st_dev,
            opened_root.st_ino,
            opened_root.st_mode,
            opened_root.st_nlink,
            opened_root.st_size,
            opened_root.st_mtime_ns,
            opened_root.st_ctime_ns,
        )
        if (
            not stat.S_ISDIR(named_root.st_mode)
            or not stat.S_ISDIR(opened_root.st_mode)
            or root_identity
            != (
                named_root.st_dev,
                named_root.st_ino,
                named_root.st_mode,
                named_root.st_nlink,
                named_root.st_size,
                named_root.st_mtime_ns,
                named_root.st_ctime_ns,
            )
        ):
            os.close(current)
            _fail("repository root is not one anchored directory")
        directories.append(current)
        for component in parts[:-1]:
            parent = current
            named_directory = os.stat(
                component,
                dir_fd=parent,
                follow_symlinks=False,
            )
            current = os.open(component, directory_flags, dir_fd=parent)
            opened_directory = os.fstat(current)
            directory_identity = (
                opened_directory.st_dev,
                opened_directory.st_ino,
                opened_directory.st_mode,
                opened_directory.st_nlink,
                opened_directory.st_size,
                opened_directory.st_mtime_ns,
                opened_directory.st_ctime_ns,
            )
            if (
                not stat.S_ISDIR(named_directory.st_mode)
                or not stat.S_ISDIR(opened_directory.st_mode)
                or directory_identity
                != (
                    named_directory.st_dev,
                    named_directory.st_ino,
                    named_directory.st_mode,
                    named_directory.st_nlink,
                    named_directory.st_size,
                    named_directory.st_mtime_ns,
                    named_directory.st_ctime_ns,
                )
            ):
                _fail("regular file ancestor is not one anchored directory")
            directories.append(current)
            directory_bindings.append(
                (parent, component, current, directory_identity)
            )
        leaf = parts[-1]
        before = os.stat(leaf, dir_fd=current, follow_symlinks=False)
        descriptor = os.open(leaf, file_flags, dir_fd=current)
        opened = os.fstat(descriptor)
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        named_after = os.stat(leaf, dir_fd=current, follow_symlinks=False)
        for parent, component, opened_directory, identity_before in directory_bindings:
            named_directory_after = os.stat(
                component,
                dir_fd=parent,
                follow_symlinks=False,
            )
            opened_directory_after = os.fstat(opened_directory)
            if identity_before != (
                opened_directory_after.st_dev,
                opened_directory_after.st_ino,
                opened_directory_after.st_mode,
                opened_directory_after.st_nlink,
                opened_directory_after.st_size,
                opened_directory_after.st_mtime_ns,
                opened_directory_after.st_ctime_ns,
            ) or identity_before != (
                named_directory_after.st_dev,
                named_directory_after.st_ino,
                named_directory_after.st_mode,
                named_directory_after.st_nlink,
                named_directory_after.st_size,
                named_directory_after.st_mtime_ns,
                named_directory_after.st_ctime_ns,
            ):
                _fail("regular file ancestor changed during anchored read")
        named_root_after = os.lstat(repo_root)
        opened_root_after = os.fstat(directories[0])
        if root_identity != (
            named_root_after.st_dev,
            named_root_after.st_ino,
            named_root_after.st_mode,
            named_root_after.st_nlink,
            named_root_after.st_size,
            named_root_after.st_mtime_ns,
            named_root_after.st_ctime_ns,
        ) or root_identity != (
            opened_root_after.st_dev,
            opened_root_after.st_ino,
            opened_root_after.st_mode,
            opened_root_after.st_nlink,
            opened_root_after.st_size,
            opened_root_after.st_mtime_ns,
            opened_root_after.st_ctime_ns,
        ):
            _fail("repository root changed during anchored read")
    except OSError as exc:
        raise RuntimeError(
            "Closure E0-U regular file cannot be read: " + relative_path
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for opened_directory in reversed(directories):
            os.close(opened_directory)
    identity = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    if (
        not stat.S_ISREG(before.st_mode)
        or (
            expected_mode is not None
            and stat.S_IMODE(before.st_mode) != expected_mode
        )
        or (
            expected_mode is None
            and stat.S_IMODE(before.st_mode) not in (0o444, 0o644)
        )
        or (expected_nlink is not None and before.st_nlink != expected_nlink)
        or (expected_nlink is None and before.st_nlink < 1)
        or identity
        != (
            opened.st_dev,
            opened.st_ino,
            opened.st_mode,
            opened.st_nlink,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        or identity
        != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        or identity
        != (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_mode,
            named_after.st_nlink,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        or sum(len(chunk) for chunk in chunks) != before.st_size
    ):
        _fail("regular file identity drifted: " + relative_path)
    return b"".join(chunks), before


def _relative_leaf_state(repo_root, relative_path):
    import os

    try:
        parent_fd, leaf = _open_parent_directory(repo_root, relative_path, False, [])
    except FileNotFoundError:
        return None
    try:
        try:
            return os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
    finally:
        os.close(parent_fd)


def _basic_regular_record(repo_root, relative_path):
    import stat

    payload, metadata = _read_regular_relative(repo_root, relative_path, 0o644, 1)
    return {
        "path": relative_path,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
    }


def _absolute_executable_record(path_text, expected_sha256):
    import os
    import stat
    from pathlib import Path

    path = Path(path_text)
    try:
        if path.resolve(strict=True) != path:
            _fail("sealed executable path is not canonical: " + path_text)
        before = os.lstat(path)
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        chunks = []
        try:
            opened = os.fstat(descriptor)
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after_opened = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after = os.lstat(path)
    except OSError as exc:
        raise RuntimeError(
            "Closure E0-U sealed executable cannot be authenticated: " + path_text
        ) from exc
    identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mode,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    payload = b"".join(chunks)
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_IMODE(before.st_mode) != 0o755
        or before.st_nlink != 1
        or before.st_uid != EXECUTABLE_UID
        or before.st_gid != EXECUTABLE_GID
        or identity
        != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mode,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        or identity
        != (
            after_opened.st_dev,
            after_opened.st_ino,
            after_opened.st_size,
            after_opened.st_mode,
            after_opened.st_mtime_ns,
            after_opened.st_ctime_ns,
        )
        or identity
        != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mode,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        or _sha256_bytes(payload) != expected_sha256
    ):
        _fail("sealed executable identity drifted: " + path_text)
    return {
        "path": path_text,
        "bytes": len(payload),
        "sha256": expected_sha256,
        "device": int(before.st_dev),
        "inode": int(before.st_ino),
        "mode": stat.S_IMODE(before.st_mode),
        "nlink": int(before.st_nlink),
        "uid": int(before.st_uid),
        "gid": int(before.st_gid),
        "mtime_ns": int(before.st_mtime_ns),
        "ctime_ns": int(before.st_ctime_ns),
    }


def _git_config_record(repo_root):
    import stat

    payload, metadata = _read_regular_relative(
        repo_root,
        GIT_CONFIG_PATH,
        0o644,
        1,
    )
    digest = _sha256_bytes(payload)
    if (
        digest != GIT_CONFIG_SHA256
        or metadata.st_uid != REPOSITORY_OWNER_UID
        or metadata.st_gid != REPOSITORY_OWNER_GID
    ):
        _fail("local Git configuration binding drifted")
    return {
        "path": GIT_CONFIG_PATH,
        "bytes": len(payload),
        "sha256": digest,
        "device": int(metadata.st_dev),
        "inode": int(metadata.st_ino),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
        "uid": int(metadata.st_uid),
        "gid": int(metadata.st_gid),
        "mtime_ns": int(metadata.st_mtime_ns),
        "ctime_ns": int(metadata.st_ctime_ns),
    }


def _https_helper_record():
    import os
    import stat
    from pathlib import Path

    link_path = Path(GIT_REMOTE_HTTPS_HELPER_PATH)
    target_path = Path(GIT_REMOTE_HTTP_HELPER_PATH)
    try:
        link = os.lstat(link_path)
        target = os.readlink(link_path)
    except OSError as exc:
        raise RuntimeError("Closure E0-U HTTPS helper is absent") from exc
    target_record = _absolute_executable_record(
        GIT_REMOTE_HTTP_HELPER_PATH,
        GIT_REMOTE_HTTP_SHA256,
    )
    if (
        not stat.S_ISLNK(link.st_mode)
        or target != "git-remote-http"
        or link.st_nlink != 1
        or link.st_uid != EXECUTABLE_UID
        or link.st_gid != EXECUTABLE_GID
        or link_path.resolve(strict=True) != target_path
    ):
        _fail("HTTPS Git helper identity drifted")
    return {
        "link_path": GIT_REMOTE_HTTPS_HELPER_PATH,
        "link_target": target,
        "link_mode": stat.S_IMODE(link.st_mode),
        "link_nlink": int(link.st_nlink),
        "link_uid": int(link.st_uid),
        "link_gid": int(link.st_gid),
        "target": target_record,
    }


def _git(repo_root, arguments, accepted_codes=(0,)):
    import os
    import subprocess

    git_before = _absolute_executable_record(
        GIT_EXECUTABLE_PATH,
        GIT_EXECUTABLE_SHA256,
    )
    config_before = _git_config_record(repo_root)
    command = [
        GIT_EXECUTABLE_PATH,
        "--no-pager",
        "--literal-pathspecs",
        "--git-dir=" + (repo_root / ".git").as_posix(),
        "--work-tree=" + repo_root.as_posix(),
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "core.excludesFile=/dev/null",
        "-c",
        "credential.helper=",
        "-c",
        "http.proxy=",
    ]
    command.extend(arguments)
    environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_ASKPASS": "/bin/false",
        "GIT_SSH_COMMAND": "/bin/false",
        "GIT_EXEC_PATH": "/usr/lib/git-core",
    }
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if (
        completed.returncode not in accepted_codes
        or _absolute_executable_record(
            GIT_EXECUTABLE_PATH,
            GIT_EXECUTABLE_SHA256,
        )
        != git_before
        or _git_config_record(repo_root) != config_before
    ):
        _fail("sealed Git command failed")
    return completed.stdout


def _git_text(repo_root, arguments):
    try:
        return _git(repo_root, arguments).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("Closure E0-U Git output is not UTF-8") from exc


def _git_oid(repo_root, expression):
    value = _git_text(
        repo_root,
        ["rev-parse", "--verify", expression],
    ).strip()
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        _fail("Git object id is malformed: " + expression)
    return value


def _git_blob_record(repo_root, commit, relative_path):
    import stat

    _canonical_relative_parts(relative_path)
    raw = _git(repo_root, ["ls-tree", "-z", commit, "--", relative_path])
    if raw.count(b"\x00") != 1 or not raw.endswith(b"\x00"):
        _fail("Git tree binding is not unique: " + relative_path)
    try:
        header, observed_path = raw[:-1].split(b"\t", 1)
        mode, object_type, oid = header.decode("ascii").split(" ")
        path_text = observed_path.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("Closure E0-U Git tree binding is malformed") from exc
    if path_text != relative_path or object_type != "blob" or mode not in ("100644", "100755"):
        _fail("Git tree binding drifted: " + relative_path)
    blob = _git(repo_root, ["cat-file", "blob", oid])
    return {
        "path": relative_path,
        "bytes": len(blob),
        "sha256": _sha256_bytes(blob),
        "mode": stat.S_IMODE(int(mode, 8)),
        "git_mode": mode,
        "git_oid": oid,
        "payload": blob,
    }


def _git_diff_scope(repo_root, parent, child):
    raw = _git(
        repo_root,
        ["diff", "--name-status", "-z", "--no-renames", parent, child, "--"],
    )
    fields = raw.split(b"\x00")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) % 2:
        _fail("Git commit scope is malformed")
    records = []
    for index in range(0, len(fields), 2):
        try:
            status = fields[index].decode("ascii")
            path = fields[index + 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError("Closure E0-U Git scope is not UTF-8") from exc
        if status not in ("A", "M"):
            _fail("Git commit scope contains a forbidden status: " + status)
        blob = _git_blob_record(repo_root, child, path)
        records.append(
            {
                "path": path,
                "status": status,
                "mode": blob["git_mode"],
                "bytes": blob["bytes"],
                "sha256": blob["sha256"],
            }
        )
    return sorted(records, key=lambda record: record["path"])


def _validate_scope_records(value, label):
    from collections.abc import Mapping, Sequence

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        _fail(label + " scope is not a sequence")
    records = []
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != set(SCOPE_RECORD_KEYS):
            _fail(label + " scope record keys drifted")
        record = dict(raw)
        path = record["path"]
        _canonical_relative_parts(path)
        if record["status"] not in ("A", "M"):
            _fail(label + " scope status drifted")
        if record["mode"] not in ("100644", "100755"):
            _fail(label + " scope mode drifted")
        if type(record["bytes"]) is not int or record["bytes"] < 0:
            _fail(label + " scope byte count drifted")
        digest = record["sha256"]
        if type(digest) is not str or len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            _fail(label + " scope digest drifted")
        records.append(record)
    if records != sorted(records, key=lambda record: record["path"]) or len(
        {record["path"] for record in records}
    ) != len(records):
        _fail(label + " scope ordering or uniqueness drifted")
    return records


def _git_bound_regular_payload(repo_root, commit, relative_path):
    payload, metadata = _read_regular_relative(repo_root, relative_path, 0o644, 1)
    blob = _git_blob_record(repo_root, commit, relative_path)
    if (
        blob["git_mode"] != "100644"
        or blob["payload"] != payload
        or blob["bytes"] != metadata.st_size
    ):
        _fail("published Git payload drifted: " + relative_path)
    return payload


def _validate_dvc_pointer_payload(pointer_payload, pointer_path, output_path, output_payload):
    import hashlib

    try:
        lines = pointer_payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise RuntimeError("Closure E0-U DVC pointer is not UTF-8") from exc
    expected_name = output_path.rsplit("/", 1)[-1]
    if (
        len(lines) != 5
        or lines[0] != "outs:"
        or not lines[1].startswith("- md5: ")
        or not lines[2].startswith("  size: ")
        or lines[3] != "  hash: md5"
        or lines[4] != "  path: " + expected_name
    ):
        _fail("DVC pointer dialect drifted: " + pointer_path)
    digest = lines[1][7:]
    size_text = lines[2][8:]
    if (
        len(digest) != 32
        or any(character not in "0123456789abcdef" for character in digest)
        or not size_text.isdigit()
        or int(size_text) != len(output_payload)
        or hashlib.md5(output_payload, usedforsecurity=False).hexdigest() != digest
    ):
        _fail("DVC pointer does not bind physical overlay bytes: " + pointer_path)


def _phase3_overlay_checkpoint_specs():
    specs = []
    for module in ("F", "N", "T"):
        for seed in sorted(PHASE3_OVERLAY_SEEDS):
            filename = (
                {"N": "ANFIS-N.pt", "F": "ANFIS-F.pt", "T": "ANFIS-T-no-current.pt"}[
                    module
                ]
                if seed == 1729
                else {
                    "N": "anfis_n.pt",
                    "F": "anfis_f.pt",
                    "T": "anfis_t_no_current.pt",
                }[module]
            )
            specs.append(
                {
                    "family": "anfis",
                    "surface_model_id": "F1",
                    "seed": seed,
                    "module": module,
                    "model_id": None,
                    "identity_prefix": "anfis/" + str(seed) + "/" + module,
                    "source_path": (
                        "models/closure_v1/anfis/seed_"
                        + str(seed)
                        + "/"
                        + filename
                    ),
                }
            )
    for model_id in ("A0", "A1"):
        for seed in sorted(PHASE3_OVERLAY_SEEDS):
            specs.append(
                {
                    "family": "gru",
                    "surface_model_id": model_id,
                    "seed": seed,
                    "module": None,
                    "model_id": model_id,
                    "identity_prefix": "gru/" + model_id + "/" + str(seed),
                    "source_path": (
                        "models/closure_v1/anfis_ablation/"
                        + model_id
                        + "/seed_"
                        + str(seed)
                        + ".checkpoint.pt"
                    ),
                }
            )
    return specs


def _phase3_overlay_source_specs():
    records = [
        {
            "role": "r10_input_history",
            "path": PHASE3_OVERLAY_HISTORY_PATH,
        },
        {
            "role": "panel_physical_seasonal",
            "path": PHASE3_OVERLAY_PANEL_PATH,
        },
    ]
    for spec in _phase3_overlay_checkpoint_specs():
        records.append(
            {
                "role": spec["identity_prefix"] + "_checkpoint",
                "path": spec["source_path"],
            }
        )
    return sorted(records, key=lambda record: (record["role"], record["path"]))


def _validate_phase3_overlay_deep_validation(
    value,
    expected_h_commit,
    expected_overlay_record=None,
    repo_root=None,
):
    """Validate U's transitive receipt for the outcome-free P overlay."""

    from collections.abc import Mapping
    from typing import Any, cast

    if (
        type(value) is not dict
        or set(value) != set(PHASE3_OVERLAY_DEEP_VALIDATION_KEYS)
        or type(expected_h_commit) is not str
        or len(expected_h_commit) != 40
        or any(
            character not in "0123456789abcdef"
            for character in expected_h_commit
        )
    ):
        _fail("Phase 3 overlay deep-validation receipt shape drifted")
    receipt = dict(value)
    expected_scalars = {
        "schema_version": "closure_phase3_input_overlay_deep_validation_v1",
        "status": "passed",
        "experiment_id": EXPERIMENT_ID,
        "surface_id": "closure_v1_phase3_input_overlay",
        "gate": "pre_E0-U",
        "expected_h_commit": expected_h_commit,
        "source_input_count": 27,
        "checkpoint_count": 25,
        "state_dict_array_count": 195,
        "warmup_row_count": 88,
        "warmup_site_count": 88,
        "npz_regenerated_byte_equality": True,
        "warmup_regenerated_byte_equality": True,
        "manifest_regenerated_byte_equality": True,
        "checkpoint_identity_revalidated": True,
        "numpy_torch_parity_recomputed": True,
        "warmup_projection_recomputed": True,
        "projection_contains_chlorophyll": False,
        "projection_contains_target": False,
        "opened_outcome_path_count": 0,
        "opened_target_path_count": 0,
        "writes_performed": False,
    }
    if any(
        type(receipt.get(key)) is not type(expected)
        or receipt.get(key) != expected
        for key, expected in expected_scalars.items()
    ):
        _fail("Phase 3 overlay deep-validation scalar drifted")

    builder = receipt.get("builder_source")
    if (
        not isinstance(builder, Mapping)
        or set(builder) != {"role", "path", "bytes", "sha256"}
        or builder.get("role") != "phase3_input_overlay_builder"
        or builder.get("path") != PHASE3_OVERLAY_BUILDER_PATH
        or type(builder.get("bytes")) is not int
        or builder["bytes"] <= 0
        or not _is_sha256(builder.get("sha256"))
    ):
        _fail("Phase 3 overlay deep-validation builder binding drifted")
    builder_record = cast(Mapping[str, Any], builder)
    if repo_root is not None:
        builder_blob = _git_blob_record(
            repo_root,
            expected_h_commit,
            PHASE3_OVERLAY_BUILDER_PATH,
        )
        if dict(builder_record) != {
            "role": "phase3_input_overlay_builder",
            "path": PHASE3_OVERLAY_BUILDER_PATH,
            "bytes": builder_blob["bytes"],
            "sha256": builder_blob["sha256"],
        } or builder_blob.get("git_mode") != "100644":
            _fail("Phase 3 overlay deep-validation builder differs from H")

    sources = receipt.get("source_inputs")
    specs = _phase3_overlay_source_specs()
    if not isinstance(sources, list) or len(sources) != len(specs):
        _fail("Phase 3 overlay deep-validation source registry drifted")
    source_records = cast(list[Any], sources)
    normalized_sources = []
    for raw_record, spec in zip(source_records, specs, strict=True):
        if (
            not isinstance(raw_record, Mapping)
            or set(raw_record) != {"role", "path", "bytes", "sha256"}
            or raw_record.get("role") != spec["role"]
            or raw_record.get("path") != spec["path"]
            or type(raw_record.get("bytes")) is not int
            or raw_record["bytes"] <= 0
            or not _is_sha256(raw_record.get("sha256"))
        ):
            _fail("Phase 3 overlay deep-validation source identity drifted")
        record = dict(raw_record)
        if repo_root is not None:
            payload, metadata = _read_regular_relative(
                repo_root,
                spec["path"],
                None,
                None,
            )
            if record != {
                "role": spec["role"],
                "path": spec["path"],
                "bytes": metadata.st_size,
                "sha256": _sha256_bytes(payload),
            }:
                _fail(
                    "Phase 3 overlay deep-validation source bytes drifted: "
                    + spec["path"]
                )
        normalized_sources.append(record)
    if (
        not _is_sha256(receipt.get("source_inputs_sha256"))
        or receipt["source_inputs_sha256"]
        != _sha256_bytes(_canonical_json_bytes(normalized_sources))
    ):
        _fail("Phase 3 overlay deep-validation source digest drifted")

    manifest_record = receipt.get("manifest")
    output_records = receipt.get("physical_outputs")
    if (
        not isinstance(manifest_record, Mapping)
        or set(manifest_record) != {"path", "bytes", "sha256"}
        or manifest_record.get("path") != PHASE3_OVERLAY_MANIFEST_PATH
        or type(manifest_record.get("bytes")) is not int
        or manifest_record["bytes"] <= 0
        or not _is_sha256(manifest_record.get("sha256"))
        or not isinstance(output_records, list)
        or len(output_records) != len(PHASE3_OVERLAY_OUTPUTS)
    ):
        _fail("Phase 3 overlay deep-validation physical binding drifted")
    typed_manifest_record = cast(Mapping[str, Any], manifest_record)
    typed_output_records = cast(list[Any], output_records)
    normalized_outputs = []
    for raw_record, (expected_path, _role) in zip(
        typed_output_records,
        PHASE3_OVERLAY_OUTPUTS,
        strict=True,
    ):
        if (
            not isinstance(raw_record, Mapping)
            or set(raw_record) != {"path", "bytes", "sha256"}
            or raw_record.get("path") != expected_path
            or type(raw_record.get("bytes")) is not int
            or raw_record["bytes"] <= 0
            or not _is_sha256(raw_record.get("sha256"))
        ):
            _fail("Phase 3 overlay deep-validation physical binding drifted")
        normalized_outputs.append(dict(raw_record))
    if expected_overlay_record is not None:
        if (
            not isinstance(expected_overlay_record, Mapping)
            or set(expected_overlay_record) != {"manifest", "physical_outputs"}
            or dict(typed_manifest_record)
            != expected_overlay_record.get("manifest")
            or normalized_outputs != expected_overlay_record.get("physical_outputs")
        ):
            _fail("Phase 3 overlay deep-validation P binding drifted")
    if (
        type(receipt.get("history_projection")) is not list
        or receipt["history_projection"]
        != list(PHASE3_OVERLAY_HISTORY_PROJECTION)
        or type(receipt.get("panel_projection")) is not list
        or receipt["panel_projection"] != list(PHASE3_OVERLAY_PANEL_PROJECTION)
    ):
        _fail("Phase 3 overlay deep-validation projection drifted")
    return receipt


def _phase3_overlay_state_shapes(spec):
    if spec["family"] == "anfis":
        dimension = {"N": 3, "F": 4, "T": 1}[spec["module"]]
        rules = 3**dimension
        return {
            "raw_center_gaps": [dimension, 4],
            "raw_widths": [dimension, 3],
            "consequent_weights": [rules, dimension],
            "consequent_bias": [rules],
            "rule_indices": [rules, dimension],
        }
    input_dimension = {"A0": 18, "A1": 27}[spec["model_id"]]
    return {
        "bloom_prior_logits": [3],
        "risk_prior_logits": [3],
        "gru.weight_ih_l0": [288, input_dimension],
        "gru.weight_hh_l0": [288, 96],
        "gru.bias_ih_l0": [288],
        "gru.bias_hh_l0": [288],
        "bloom_delta.weight": [3, 96],
        "bloom_delta.bias": [3],
        "risk_delta.weight": [3, 96],
        "risk_delta.bias": [3],
        "risk_logvar.weight": [3, 96],
        "risk_logvar.bias": [3],
    }


def _require_phase3_hex_digest(value, label):
    if type(value) is not str or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        _fail("Phase 3 overlay digest drifted: " + label)
    return value


def _validate_phase3_checkpoint_identity(identity, spec):
    from collections.abc import Mapping

    if not isinstance(identity, Mapping):
        _fail("Phase 3 overlay checkpoint identity is malformed")
    if spec["family"] == "anfis":
        expected_keys = {
            "checkpoint_version",
            "experiment_id",
            "module",
            "base_seed",
            "module_seed",
            "feature_columns",
            "target_column",
            "configuration",
        }
        expected_module = {
            "N": "ANFIS-N",
            "F": "ANFIS-F",
            "T": "ANFIS-T-no-current",
        }[spec["module"]]
        expected_features = {
            "N": ["tp_pressure", "tn_pressure", "ratio_imbalance_pressure"],
            "F": ["do_good", "ph_good", "turbidity_good", "secchi_good"],
            "T": ["temp_favorable"],
        }[spec["module"]]
        expected_target = {"N": "yN", "F": "yF", "T": "yT_no_chla"}[
            spec["module"]
        ]
        configuration = identity.get("configuration")
        if (
            set(identity) != expected_keys
            or identity.get("checkpoint_version") != "closure_anfis_module_v1"
            or identity.get("experiment_id") != EXPERIMENT_ID
            or identity.get("module") != expected_module
            or identity.get("base_seed") != spec["seed"]
            or type(identity.get("module_seed")) is not int
            or identity.get("feature_columns") != expected_features
            or identity.get("target_column") != expected_target
            or not isinstance(configuration, Mapping)
            or configuration.get("memberships_per_input") != 3
            or configuration.get("center_constraint") != "unit"
            or configuration.get("min_width") != 0.03
            or configuration.get("min_gap") != 0.0001
            or configuration.get("output_activation") != "sigmoid"
        ):
            _fail("Phase 3 overlay ANFIS identity drifted")
        return
    expected_keys = {
        "model_version",
        "experiment_id",
        "surface_id",
        "gate",
        "artifact_role",
        "model_id",
        "base_seed",
        "upstream_state_seed",
        "device",
        "config",
        "bloom_training_priors",
        "risk_training_priors",
    }
    configuration = identity.get("config")
    model_id = spec["model_id"]
    if (
        set(identity) != expected_keys
        or identity.get("model_version")
        != "closure_anfis_ablation_direct_multitask_v1"
        or identity.get("experiment_id") != EXPERIMENT_ID
        or identity.get("surface_id")
        != "closure_v1_wqp_adaptive_no_current_chla"
        or identity.get("gate") != "E0-MT"
        or identity.get("artifact_role") != "raw_best_checkpoint"
        or identity.get("model_id") != model_id
        or identity.get("base_seed") != spec["seed"]
        or identity.get("upstream_state_seed")
        != (spec["seed"] if model_id == "A1" else None)
        or identity.get("device") != "cpu"
        or not isinstance(configuration, Mapping)
        or configuration.get("family") != "direct_multitask_probabilistic_gru"
        or configuration.get("model_id") != model_id
        or configuration.get("input_dimension") != {"A0": 18, "A1": 27}[model_id]
        or configuration.get("hidden_dimension") != 96
        or configuration.get("recurrent_layers") != 1
        or configuration.get("history_length_months") != 12
        or configuration.get("risk_logvar_clamp") != [-10.0, 2.0]
        or not isinstance(identity.get("bloom_training_priors"), list)
        or len(identity["bloom_training_priors"]) != 3
        or not isinstance(identity.get("risk_training_priors"), list)
        or len(identity["risk_training_priors"]) != 3
    ):
        _fail("Phase 3 overlay GRU identity drifted")


def _validate_phase3_parity_record(value, spec):
    import math
    from collections.abc import Mapping
    from typing import cast

    expected_keys = {
        "fixture_version",
        "fixture_shape",
        "fixture_dtype",
        "output_names",
        "output_shape",
        "atol",
        "rtol",
        "maximum_absolute_error",
        "passed",
    }
    maximum_error = value.get("maximum_absolute_error") if isinstance(value, Mapping) else None
    if not isinstance(maximum_error, (int, float)) or isinstance(maximum_error, bool):
        _fail("Phase 3 overlay NumPy/Torch parity evidence drifted")
    normalized_error = float(cast(float, maximum_error))
    if spec["family"] == "anfis":
        dimension = {"N": 3, "F": 4, "T": 1}[spec["module"]]
        fixture_shape = [7, dimension]
        output_names = ["prediction"]
        output_shape = [7]
    else:
        fixture_shape = [4, 12, {"A0": 18, "A1": 27}[spec["model_id"]]]
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
        output_shape = [4, 9]
    if (
        not isinstance(value, Mapping)
        or set(value) != expected_keys
        or value.get("fixture_version")
        != PHASE3_OVERLAY_PARITY_FIXTURE_VERSION
        or value.get("fixture_shape") != fixture_shape
        or value.get("fixture_dtype") != "<f4"
        or value.get("output_names") != output_names
        or value.get("output_shape") != output_shape
        or value.get("atol") != PHASE3_OVERLAY_PARITY_ATOL
        or value.get("rtol") != PHASE3_OVERLAY_PARITY_RTOL
        or not math.isfinite(normalized_error)
        or normalized_error < 0.0
        or normalized_error > 0.0001
        or value.get("passed") is not True
    ):
        _fail("Phase 3 overlay NumPy/Torch parity evidence drifted")
    return normalized_error


def _validate_phase3_numpy_export(value, source_by_path):
    import math
    from collections.abc import Mapping, Sequence

    keys = {
        "format_version",
        "internal_manifest_key",
        "internal_manifest_encoding",
        "internal_manifest_bytes",
        "internal_manifest_sha256",
        "key_dialect",
        "checkpoint_count",
        "anfis_checkpoint_count",
        "anfis_f1_checkpoint_count",
        "gru_checkpoint_count",
        "state_dict_array_count",
        "archive_array_count",
        "archive_keys",
        "arrays",
        "checkpoints",
        "parity",
    }
    key_dialect = {
        "anfis": "anfis/{seed}/{module}/{state_key}",
        "anfis_modules": ["N", "F", "T"],
        "gru": "gru/{model_id}/{seed}/{state_key}",
        "gru_model_ids": ["A0", "A1"],
        "state_key_encoding": "literal_utf8_no_slash",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != keys
        or value.get("format_version") != PHASE3_OVERLAY_NPZ_INDEX_VERSION
        or value.get("internal_manifest_key") != "__manifest_json__"
        or value.get("internal_manifest_encoding")
        != "uint8_utf8_canonical_json"
        or type(value.get("internal_manifest_bytes")) is not int
        or value.get("internal_manifest_bytes") <= 0
        or _require_phase3_hex_digest(
            value.get("internal_manifest_sha256"), "NPZ internal manifest"
        )
        != value.get("internal_manifest_sha256")
        or value.get("key_dialect") != key_dialect
        or value.get("checkpoint_count") != 25
        or value.get("anfis_checkpoint_count") != 15
        or value.get("anfis_f1_checkpoint_count") != 15
        or value.get("gru_checkpoint_count") != 10
    ):
        _fail("Phase 3 overlay NumPy export header drifted")
    checkpoints = value.get("checkpoints")
    arrays = value.get("arrays")
    if (
        not isinstance(checkpoints, Sequence)
        or isinstance(checkpoints, (str, bytes))
        or len(checkpoints) != 25
        or not isinstance(arrays, Sequence)
        or isinstance(arrays, (str, bytes))
    ):
        _fail("Phase 3 overlay NumPy registries drifted")
    expected_checkpoint_keys = {
        "family",
        "surface_model_id",
        "seed",
        "module",
        "model_id",
        "source_path",
        "source_sha256",
        "identity",
        "state_dict_key_count",
        "state_dict_arrays",
        "parity",
    }
    expected_array_keys = {
        "npz_key",
        "state_key",
        "dtype",
        "shape",
        "element_count",
        "data_sha256",
        "npy_sha256",
        "origin_path",
        "origin_sha256",
        "checkpoint_family",
        "surface_model_id",
        "seed",
        "module",
        "model_id",
    }
    collected = []
    maximum_errors = []
    anfis_errors = []
    gru_errors = []
    for raw_checkpoint, spec in zip(
        checkpoints, _phase3_overlay_checkpoint_specs(), strict=True
    ):
        if not isinstance(raw_checkpoint, Mapping) or set(raw_checkpoint) != expected_checkpoint_keys:
            _fail("Phase 3 overlay checkpoint record keys drifted")
        source = source_by_path.get(spec["source_path"])
        expected_shapes = _phase3_overlay_state_shapes(spec)
        state_arrays = raw_checkpoint.get("state_dict_arrays")
        if (
            source is None
            or raw_checkpoint.get("family") != spec["family"]
            or raw_checkpoint.get("surface_model_id") != spec["surface_model_id"]
            or raw_checkpoint.get("seed") != spec["seed"]
            or raw_checkpoint.get("module") != spec["module"]
            or raw_checkpoint.get("model_id") != spec["model_id"]
            or raw_checkpoint.get("source_path") != spec["source_path"]
            or raw_checkpoint.get("source_sha256") != source["sha256"]
            or raw_checkpoint.get("state_dict_key_count") != len(expected_shapes)
            or not isinstance(state_arrays, Sequence)
            or isinstance(state_arrays, (str, bytes))
            or len(state_arrays) != len(expected_shapes)
        ):
            _fail("Phase 3 overlay checkpoint/source binding drifted")
        _validate_phase3_checkpoint_identity(raw_checkpoint.get("identity"), spec)
        observed_state_keys = []
        for raw_array in state_arrays:
            if not isinstance(raw_array, Mapping) or set(raw_array) != expected_array_keys:
                _fail("Phase 3 overlay array record keys drifted")
            state_key = raw_array.get("state_key")
            shape = raw_array.get("shape")
            expected_npz_key = spec["identity_prefix"] + "/" + str(state_key)
            element_count = 1
            if isinstance(shape, list):
                for dimension in shape:
                    if type(dimension) is not int or dimension <= 0:
                        _fail("Phase 3 overlay array shape drifted")
                    element_count *= dimension
            if (
                type(state_key) is not str
                or state_key not in expected_shapes
                or "/" in state_key
                or raw_array.get("npz_key") != expected_npz_key
                or shape != expected_shapes[state_key]
                or raw_array.get("element_count") != element_count
                or raw_array.get("dtype")
                != ("<i8" if state_key == "rule_indices" else "<f4")
                or raw_array.get("origin_path") != spec["source_path"]
                or raw_array.get("origin_sha256") != source["sha256"]
                or raw_array.get("checkpoint_family") != spec["family"]
                or raw_array.get("surface_model_id") != spec["surface_model_id"]
                or raw_array.get("seed") != spec["seed"]
                or raw_array.get("module") != spec["module"]
                or raw_array.get("model_id") != spec["model_id"]
            ):
                _fail("Phase 3 overlay state-array binding drifted")
            _require_phase3_hex_digest(raw_array.get("data_sha256"), "array data")
            _require_phase3_hex_digest(raw_array.get("npy_sha256"), "NPY payload")
            observed_state_keys.append(state_key)
            collected.append(dict(raw_array))
        if observed_state_keys != sorted(expected_shapes):
            _fail("Phase 3 overlay state-array order drifted")
        error = _validate_phase3_parity_record(raw_checkpoint.get("parity"), spec)
        maximum_errors.append(error)
        (anfis_errors if spec["family"] == "anfis" else gru_errors).append(error)
    collected.sort(key=lambda record: record["npz_key"])
    archive_keys = sorted(["__manifest_json__", *[record["npz_key"] for record in collected]])
    if (
        list(arrays) != collected
        or len(collected) != 195
        or value.get("state_dict_array_count") != len(collected)
        or value.get("archive_array_count") != len(archive_keys)
        or value.get("archive_keys") != archive_keys
    ):
        _fail("Phase 3 overlay flattened array registry drifted")
    parity = value.get("parity")
    parity_keys = {
        "fixture_version",
        "atol",
        "rtol",
        "checkpoint_count",
        "passed_checkpoint_count",
        "maximum_absolute_error",
        "anfis_maximum_absolute_error",
        "gru_maximum_absolute_error",
        "passed",
    }
    if (
        not isinstance(parity, Mapping)
        or set(parity) != parity_keys
        or parity.get("fixture_version") != PHASE3_OVERLAY_PARITY_FIXTURE_VERSION
        or parity.get("atol") != PHASE3_OVERLAY_PARITY_ATOL
        or parity.get("rtol") != PHASE3_OVERLAY_PARITY_RTOL
        or parity.get("checkpoint_count") != 25
        or parity.get("passed_checkpoint_count") != 25
        or parity.get("maximum_absolute_error") != max(maximum_errors)
        or parity.get("anfis_maximum_absolute_error") != max(anfis_errors)
        or parity.get("gru_maximum_absolute_error") != max(gru_errors)
        or parity.get("passed") is not True
        or not math.isfinite(float(parity.get("maximum_absolute_error", -1.0)))
    ):
        _fail("Phase 3 overlay aggregate parity evidence drifted")
    return {
        "format_version": PHASE3_OVERLAY_NPZ_INDEX_VERSION,
        "key_dialect": key_dialect,
        "checkpoint_count": 25,
        "state_dict_array_count": len(collected),
        "array_keys": [record["npz_key"] for record in collected],
        "arrays": collected,
        "checkpoints": [dict(record) for record in checkpoints],
    }


def _validate_phase3_warmup(value):
    import math
    from collections.abc import Mapping
    from typing import cast

    keys = {
        "algorithm",
        "site_count",
        "row_count",
        "row_present_count",
        "row_missing_count",
        "source_ids",
        "assignment_roles",
        "holdout_group_count",
        "first_history_months_sha256",
        "panel_projection",
        "panel_projection_count",
        "panel_projection_contains_chlorophyll",
        "panel_projection_contains_target",
        "panel_seasonal_projection",
        "panel_seasonal_values_used_for_runtime",
        "runtime_seasonal_algorithm",
        "panel_to_runtime_season_comparison",
        "panel_to_runtime_season_maximum_absolute_difference",
        "physical_missing_counts",
        "calendar_missing_counts",
    }
    panel_projection = [
        "source_id",
        "site_id",
        "year_month",
        *PHASE3_OVERLAY_PHYSICAL_COLUMNS,
        *PHASE3_OVERLAY_PANEL_SEASON_COLUMNS,
    ]
    missing_physical = value.get("physical_missing_counts") if isinstance(value, Mapping) else None
    missing_calendar = value.get("calendar_missing_counts") if isinstance(value, Mapping) else None
    seasonal_difference = (
        value.get("panel_to_runtime_season_maximum_absolute_difference")
        if isinstance(value, Mapping)
        else None
    )
    if not isinstance(seasonal_difference, (int, float)) or isinstance(
        seasonal_difference, bool
    ):
        _fail("Phase 3 overlay warm-up contract drifted")
    normalized_seasonal_difference = float(cast(float, seasonal_difference))
    if (
        not isinstance(value, Mapping)
        or set(value) != keys
        or value.get("algorithm")
        != "calendar_month_preceding_site_first_r10_history_month_v1"
        or value.get("site_count") != 88
        or value.get("row_count") != 88
        or type(value.get("row_present_count")) is not int
        or type(value.get("row_missing_count")) is not int
        or value.get("row_present_count") + value.get("row_missing_count") != 88
        or value.get("source_ids") != ["wqp"]
        or value.get("assignment_roles") != ["internal_holdout"]
        or value.get("holdout_group_count") != 88
        or _require_phase3_hex_digest(
            value.get("first_history_months_sha256"), "warm-up identities"
        )
        != value.get("first_history_months_sha256")
        or value.get("panel_projection") != panel_projection
        or value.get("panel_projection_count") != len(panel_projection)
        or value.get("panel_projection_contains_chlorophyll") is not False
        or value.get("panel_projection_contains_target") is not False
        or value.get("panel_seasonal_projection")
        != list(PHASE3_OVERLAY_PANEL_SEASON_COLUMNS)
        or value.get("panel_seasonal_values_used_for_runtime") is not False
        or value.get("runtime_seasonal_algorithm")
        != "calendar_month_zero_based_fourier_annual_semiannual_v1"
        or value.get("panel_to_runtime_season_comparison")
        != {
            "season_sin_1": "season_sin_annual",
            "season_cos_1": "season_cos_annual",
            "season_sin_2": "season_sin_semiannual",
            "season_cos_2": "season_cos_semiannual",
        }
        or not math.isfinite(normalized_seasonal_difference)
        or normalized_seasonal_difference < 0.0
        or not isinstance(missing_physical, Mapping)
        or set(missing_physical) != set(PHASE3_OVERLAY_PHYSICAL_COLUMNS)
        or any(type(count) is not int or count < 0 or count > 88 for count in missing_physical.values())
        or not isinstance(missing_calendar, Mapping)
        or set(missing_calendar) != set(PHASE3_OVERLAY_CALENDAR_COLUMNS)
        or any(count != 0 for count in missing_calendar.values())
    ):
        _fail("Phase 3 overlay warm-up contract drifted")


def _validate_phase3_overlay_bundle(repo_root, h_commit, p_commit):
    import json
    from collections.abc import Mapping, Sequence

    manifest_payload = _git_bound_regular_payload(
        repo_root,
        p_commit,
        PHASE3_OVERLAY_MANIFEST_PATH,
    )
    try:
        manifest = json.loads(manifest_payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("Closure E0-U overlay manifest cannot be decoded") from exc
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != set(PHASE3_OVERLAY_MANIFEST_KEYS)
        or _canonical_json_bytes(dict(manifest)) != manifest_payload
        or manifest.get("manifest_version")
        != "closure_phase3_input_overlay_manifest_v1"
        or manifest.get("experiment_id") != EXPERIMENT_ID
        or manifest.get("surface_id") != "closure_v1_phase3_input_overlay"
        or manifest.get("gate") != "pre_E0-U"
        or manifest.get("status") != "completed"
        or manifest.get("publication_status") != "materialized_unpublished"
        or manifest.get("repository_head") != h_commit
        or manifest.get("input_only") is not True
    ):
        _fail("Phase 3 input overlay manifest binding drifted")
    script = manifest.get("script")
    if (
        not isinstance(script, Mapping)
        or set(script) != {"role", "path", "bytes", "sha256"}
        or script.get("path") != PHASE3_OVERLAY_BUILDER_PATH
    ):
        _fail("Phase 3 input overlay builder binding is absent")
    builder_blob = _git_blob_record(repo_root, h_commit, PHASE3_OVERLAY_BUILDER_PATH)
    if (
        script.get("role") != "phase3_input_overlay_builder"
        or script.get("bytes") != builder_blob["bytes"]
        or script.get("sha256") != builder_blob["sha256"]
        or builder_blob["git_mode"] != "100644"
    ):
        _fail("Phase 3 input overlay builder differs from H")
    inputs = manifest.get("inputs")
    source_inputs = manifest.get("source_inputs")
    if (
        not isinstance(inputs, Sequence)
        or isinstance(inputs, (str, bytes))
        or not isinstance(source_inputs, Sequence)
        or isinstance(source_inputs, (str, bytes))
        or len(inputs) != 27
        or len(source_inputs) != 28
        or source_inputs[0] != script
        or list(source_inputs[1:]) != list(inputs)
    ):
        _fail("Phase 3 input overlay source registry drifted")
    expected_sources = []
    source_by_path = {}
    for raw_record, spec in zip(
        inputs, _phase3_overlay_source_specs(), strict=True
    ):
        if (
            not isinstance(raw_record, Mapping)
            or set(raw_record) != {"role", "path", "bytes", "sha256"}
            or raw_record.get("role") != spec["role"]
            or raw_record.get("path") != spec["path"]
        ):
            _fail("Phase 3 input overlay source identity drifted")
        payload, metadata = _read_regular_relative(
            repo_root, spec["path"], None, None
        )
        expected = {
            "role": spec["role"],
            "path": spec["path"],
            "bytes": metadata.st_size,
            "sha256": _sha256_bytes(payload),
        }
        if dict(raw_record) != expected:
            _fail("Phase 3 input overlay source bytes drifted: " + spec["path"])
        expected_sources.append(expected)
        source_by_path[spec["path"]] = expected
    if list(inputs) != expected_sources:
        _fail("Phase 3 input overlay source ordering drifted")
    _validate_phase3_numpy_export(manifest.get("numpy_export"), source_by_path)
    _validate_phase3_warmup(manifest.get("warmup"))
    outputs = manifest.get("physical_outputs")
    if (
        not isinstance(outputs, Sequence)
        or isinstance(outputs, (str, bytes))
        or manifest.get("outputs") != outputs
        or len(outputs) != len(PHASE3_OVERLAY_OUTPUTS)
    ):
        _fail("Phase 3 input overlay physical output registry drifted")
    physical_output_records = []
    for raw_record, (output_path, role) in zip(
        outputs, PHASE3_OVERLAY_OUTPUTS, strict=True
    ):
        if not isinstance(raw_record, Mapping):
            _fail("Phase 3 input overlay output record is malformed")
        output_payload, output_metadata = _read_regular_relative(
            repo_root, output_path, None, None
        )
        expected_record_keys = (
            {
                "role",
                "path",
                "bytes",
                "sha256",
                "checkpoint_count",
                "state_dict_array_count",
                "archive_array_count",
                "archive_keys",
            }
            if role == "phase3_runtime_weights"
            else {
                "role",
                "path",
                "bytes",
                "sha256",
                "row_count",
                "site_count",
                "columns",
                "arrow_schema",
            }
        )
        if (
            set(raw_record) != expected_record_keys
            or raw_record.get("path") != output_path
            or raw_record.get("role") != role
            or raw_record.get("bytes") != output_metadata.st_size
            or raw_record.get("bytes") != len(output_payload)
            or raw_record.get("sha256") != _sha256_bytes(output_payload)
        ):
            _fail("Phase 3 input overlay physical bytes drifted: " + output_path)
        if role == "phase3_runtime_weights":
            numpy_export = manifest["numpy_export"]
            if (
                raw_record.get("checkpoint_count") != 25
                or raw_record.get("state_dict_array_count") != 195
                or raw_record.get("archive_array_count") != 196
                or raw_record.get("archive_keys") != numpy_export["archive_keys"]
            ):
                _fail("Phase 3 runtime-weight output record drifted")
        else:
            expected_arrow = [
                {
                    "name": column,
                    "type": (
                        "string"
                        if column in ("source_id", "site_id", "year_month")
                        else "bool"
                        if column == "row_present"
                        else "double"
                    ),
                    "nullable": True,
                }
                for column in PHASE3_OVERLAY_WARMUP_COLUMNS
            ]
            if (
                raw_record.get("row_count") != 88
                or raw_record.get("site_count") != 88
                or raw_record.get("columns")
                != list(PHASE3_OVERLAY_WARMUP_COLUMNS)
                or raw_record.get("arrow_schema") != expected_arrow
            ):
                _fail("Phase 3 warm-up output record drifted")
        pointer_path = output_path + ".dvc"
        pointer_payload = _git_bound_regular_payload(
            repo_root, p_commit, pointer_path
        )
        _validate_dvc_pointer_payload(
            pointer_payload,
            pointer_path,
            output_path,
            output_payload,
        )
        physical_output_records.append(
            {
                "path": output_path,
                "bytes": len(output_payload),
                "sha256": _sha256_bytes(output_payload),
            }
        )
    isolation = manifest.get("outcome_isolation")
    if (
        not isinstance(isolation, Mapping)
        or set(isolation)
        != {
            "opened_outcome_path_count",
            "opened_target_path_count",
            "outcome_paths",
            "target_paths",
            "panel_projection_contains_chlorophyll",
            "panel_projection_contains_target",
            "scientific_outcomes_accessed",
            "e0_u_authorized",
            "evaluation_authorized",
        }
        or isolation.get("opened_outcome_path_count") != 0
        or isolation.get("opened_target_path_count") != 0
        or isolation.get("outcome_paths") != []
        or isolation.get("target_paths") != []
        or isolation.get("scientific_outcomes_accessed") is not False
        or isolation.get("e0_u_authorized") is not False
        or isolation.get("evaluation_authorized") is not False
        or isolation.get("panel_projection_contains_chlorophyll") is not False
        or isolation.get("panel_projection_contains_target") is not False
    ):
        _fail("Phase 3 input overlay outcome-isolation claim drifted")
    publication = manifest.get("publication")
    if (
        not isinstance(publication, Mapping)
        or set(publication)
        != {
            "exclusive_guard",
            "no_clobber",
            "temporary_files_exclusive",
            "publication_primitive",
            "rollback_policy",
            "manifest_written_last",
            "publication_order",
        }
        or publication.get("exclusive_guard")
        != "tmp/closure_phase3_input_overlay.guard"
        or publication.get("no_clobber") is not True
        or publication.get("temporary_files_exclusive") is not True
        or publication.get("publication_primitive")
        != "temporary_regular_file_then_hardlink"
        or publication.get("manifest_written_last") is not True
        or publication.get("rollback_policy")
        != "current_process_device_inode_only"
        or publication.get("publication_order")
        != [
            PHASE3_OVERLAY_OUTPUTS[0][0],
            PHASE3_OVERLAY_OUTPUTS[1][0],
            PHASE3_OVERLAY_MANIFEST_PATH,
        ]
    ):
        _fail("Phase 3 input overlay publication contract drifted")
    return {
        "manifest": {
            "path": PHASE3_OVERLAY_MANIFEST_PATH,
            "bytes": len(manifest_payload),
            "sha256": _sha256_bytes(manifest_payload),
        },
        "physical_outputs": physical_output_records,
    }


def _validate_source_record(repo_root, head, value, expected_path):
    from collections.abc import Mapping

    if not isinstance(value, Mapping):
        _fail("sealed source record is not a mapping")
    record = dict(value)
    path = record.get("path", record.get("source_path"))
    if type(path) is not str or (expected_path is not None and path != expected_path):
        _fail("sealed source path drifted")
    physical = _basic_regular_record(repo_root, path)
    blob = _git_blob_record(repo_root, head, path)
    if (
        blob["payload"]
        != _read_regular_relative(repo_root, path, physical["mode"], 1)[0]
        or blob["mode"] != physical["mode"]
    ):
        _fail("sealed source differs from the HEAD Git blob: " + path)
    for key in ("bytes", "sha256", "mode", "nlink"):
        if type(record.get(key)) is not type(physical[key]) or record.get(key) != physical[key]:
            _fail("sealed source record drifted: " + path + ":" + key)
    return record


def _contract_layout(sealed_batch_contract):
    from collections.abc import Mapping
    from typing import cast

    if not isinstance(sealed_batch_contract, Mapping):
        _fail("sealed batch contract is not a mapping")
    contract = dict(sealed_batch_contract)
    stages = contract.get("stages")
    artifact_contracts = contract.get("component_artifact_contracts")
    if (
        type(stages) is not list
        or type(artifact_contracts) is not list
    ):
        _fail("sealed batch artifact topology is absent")
    stages = cast(list, stages)
    artifact_contracts = cast(list, artifact_contracts)
    manifest_by_stage = {}
    formats_by_path = {}
    for item in artifact_contracts:
        if not isinstance(item, Mapping):
            _fail("artifact ownership contract is malformed")
        stage_id = item.get("stage_id")
        paths = item.get("artifact_paths")
        formats = item.get("artifact_formats")
        terminal = item.get("manifest_last_path")
        if (
            type(stage_id) is not str
            or type(paths) is not list
            or type(formats) is not list
            or len(paths) != len(formats)
        ):
            _fail("artifact ownership contract drifted")
        if not paths:
            if terminal is not None:
                _fail("empty artifact owner has a manifest-last path")
            continue
        if (
            type(terminal) is not str
            or terminal not in paths
            or stage_id in manifest_by_stage
        ):
            _fail("artifact ownership contract drifted")
        manifest_by_stage[stage_id] = terminal
        for path, format_name in zip(paths, formats, strict=True):
            _canonical_relative_parts(path)
            if (
                type(format_name) is not str
                or path in formats_by_path
                or format_name
                not in ("csv", "json", "markdown", "parquet", "xml")
                or not (
                    path.startswith("reports/closure_v1/")
                    or path.startswith("data/closure_v1/")
                )
                or path in (ACTIVATION_MANIFEST_PATH, OUTCOME_ACCESS_LOG_PATH)
            ):
                _fail("artifact path ownership is not exact")
            formats_by_path[path] = format_name
    publication_order = []
    stage_ids = []
    for stage in stages:
        if not isinstance(stage, Mapping):
            _fail("batch stage record is malformed")
        stage_id = stage.get("stage_id")
        paths = stage.get("output_paths")
        if type(stage_id) is not str or type(paths) is not list:
            _fail("batch stage output scope is malformed")
        if stage_id == "E0-U":
            if paths not in ([], [OUTCOME_ACCESS_LOG_PATH]):
                _fail("E0-U access-log ownership drifted")
            continue
        if not paths:
            continue
        if stage_id in stage_ids or stage_id not in manifest_by_stage:
            _fail("batch stage manifest ownership drifted")
        terminal = manifest_by_stage[stage_id]
        if terminal not in paths or len(set(paths)) != len(paths):
            _fail("batch stage output paths drifted")
        for path in paths:
            if path != terminal:
                publication_order.append(path)
        publication_order.append(terminal)
        stage_ids.append(stage_id)
    expected_paths = tuple(sorted(formats_by_path))
    if (
        len(expected_paths) != EXPECTED_ARTIFACT_COUNT
        or len(publication_order) != EXPECTED_ARTIFACT_COUNT
        or set(publication_order) != set(expected_paths)
        or len(stage_ids) != EXPECTED_STAGE_COUNT
    ):
        _fail("sealed batch does not own exact52 artifacts across E1-E10")
    return {
        "contract": contract,
        "contract_sha256": _sha256_bytes(_canonical_json_bytes(contract)),
        "expected_paths": expected_paths,
        "formats_by_path": formats_by_path,
        "manifest_by_stage": manifest_by_stage,
        "publication_order": tuple(publication_order),
        "stage_ids": tuple(stage_ids),
    }


def _validate_dvc_policy(value, expected_paths, formats_by_path=None):
    from collections.abc import Mapping, Sequence

    if not isinstance(value, Mapping) or set(value) != set(DVC_POLICY_KEYS):
        _fail("DVC publication policy keys drifted")
    policy = dict(value)
    for key in (
        "dvc_add_after_success_only",
        "dvc_push_after_audit_only",
        "implicit_dvc_forbidden",
    ):
        if type(policy[key]) is not bool or policy[key] is not True:
            _fail("DVC publication policy is not fail-closed: " + key)
    for key in (
        "direct_git_artifact_paths",
        "dvc_pointer_paths",
        "heavy_artifact_paths",
    ):
        if not isinstance(policy[key], Sequence) or isinstance(policy[key], (str, bytes)):
            _fail("DVC publication path policy is malformed: " + key)
        if any(type(path) is not str for path in policy[key]):
            _fail("DVC publication path policy contains a non-string")
        if list(policy[key]) != sorted(policy[key]) or len(set(policy[key])) != len(policy[key]):
            _fail("DVC publication path policy is not sorted and unique")
    heavy = set(policy["heavy_artifact_paths"])
    direct = set(policy["direct_git_artifact_paths"])
    pointers = set(policy["dvc_pointer_paths"])
    if (
        len(heavy) != EXPECTED_HEAVY_ARTIFACT_COUNT
        or heavy | direct != set(expected_paths)
        or heavy & direct
        or pointers != {path + ".dvc" for path in heavy}
    ):
        _fail("DVC/Git ownership does not partition exact52")
    if formats_by_path is not None and heavy != {
        path for path, format_name in formats_by_path.items() if format_name == "parquet"
    }:
        _fail("DVC-heavy outputs are not exactly the four Parquets")
    return policy


def _load_activation_manifest(repo_root, sealed_batch_contract):
    import json
    from collections.abc import Mapping

    payload, metadata = _read_regular_relative(
        repo_root,
        ACTIVATION_MANIFEST_PATH,
        0o644,
        1,
    )
    try:
        manifest = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("Closure E0-U activation manifest is not canonical JSON") from exc
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != set(ACTIVATION_MANIFEST_KEYS)
        or _canonical_json_bytes(dict(manifest)) != payload
        or metadata.st_size != len(payload)
    ):
        _fail("activation manifest shape or canonical encoding drifted")
    result = dict(manifest)
    expected_scalars = {
        "schema_version": ACTIVATION_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "gate": GATE,
        "base_r_commit": BASE_R_COMMIT,
        "git_remote_url": LIVE_REMOTE_URL,
        "sealed_batch_command": SEALED_BATCH_COMMAND,
    }
    for key, expected in expected_scalars.items():
        if type(result.get(key)) is not type(expected) or result.get(key) != expected:
            _fail("activation manifest scalar drifted: " + key)
    for key in ("h_commit", "p_commit"):
        value = result.get(key)
        if type(value) is not str or len(value) != 40 or any(
            character not in "0123456789abcdef" for character in value
        ):
            _fail("activation manifest commit is malformed: " + key)
    execution_id = result.get("execution_id")
    if type(execution_id) is not str or len(execution_id) < 16 or len(execution_id) > 128:
        _fail("activation execution id is malformed")
    layout = _contract_layout(sealed_batch_contract)
    if result.get("sealed_batch_contract_sha256") != layout["contract_sha256"]:
        _fail("activation sealed batch contract digest drifted")
    if result.get("expected_artifact_paths_sha256") != _sha256_bytes(
        _canonical_json_bytes(list(layout["expected_paths"]))
    ):
        _fail("activation exact52 path digest drifted")
    if result.get("expected_publication_order_sha256") != _sha256_bytes(
        _canonical_json_bytes(list(layout["publication_order"]))
    ):
        _fail("activation publication order digest drifted")
    result["h_scope"] = _validate_scope_records(result["h_scope"], "H")
    result["p_scope"] = _validate_scope_records(result["p_scope"], "P")
    result["dvc_policy"] = _validate_dvc_policy(
        result["dvc_policy"],
        layout["expected_paths"],
        layout["formats_by_path"],
    )
    result["phase3_overlay_deep_validation"] = (
        _validate_phase3_overlay_deep_validation(
            result["phase3_overlay_deep_validation"],
            result["h_commit"],
        )
    )
    return result, layout


def _require_direct_parent(repo_root, child, expected_parent, label):
    parent_fields = _git_text(
        repo_root,
        ["rev-list", "--parents", "-n", "1", child],
    ).strip().split()
    if parent_fields != [child, expected_parent]:
        _fail(label + " is not an exact direct non-merge descendant")


def _validate_git_topology(repo_root, manifest, verify_remote):
    head = _git_oid(repo_root, "HEAD^{commit}")
    main = _git_oid(repo_root, "refs/heads/main^{commit}")
    tracking = _git_oid(repo_root, "refs/remotes/origin/main^{commit}")
    origin_head = _git_oid(repo_root, "refs/remotes/origin/HEAD^{commit}")
    p_commit = _git_oid(repo_root, "HEAD~1^{commit}")
    h_commit = _git_oid(repo_root, "HEAD~2^{commit}")
    r_commit = _git_oid(repo_root, "HEAD~3^{commit}")
    if (
        head != main
        or head != tracking
        or head != origin_head
        or p_commit != manifest["p_commit"]
        or h_commit != manifest["h_commit"]
        or r_commit != BASE_R_COMMIT
        or _git_text(repo_root, ["symbolic-ref", "--quiet", "HEAD"]).strip()
        != "refs/heads/main"
        or _git_text(
            repo_root,
            ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
        ).strip()
        != "refs/remotes/origin/main"
        or _git_text(repo_root, ["remote", "get-url", "origin"]).strip()
        != CONFIGURED_ORIGIN_URL
    ):
        _fail("R-H-P-U repository topology or refs drifted")
    for child, expected_parent, label in (
        (h_commit, r_commit, "H"),
        (p_commit, h_commit, "P"),
        (head, p_commit, "U"),
    ):
        _require_direct_parent(repo_root, child, expected_parent, label)
    if _git(repo_root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]):
        _fail("repository worktree or index is not clean")
    if _git_diff_scope(repo_root, BASE_R_COMMIT, h_commit) != manifest["h_scope"]:
        _fail("H commit scope differs from the activation binding")
    if _git_diff_scope(repo_root, h_commit, p_commit) != manifest["p_scope"]:
        _fail("P commit scope differs from the activation binding")
    u_scope = _git_diff_scope(repo_root, p_commit, head)
    if u_scope != [
        {
            "path": ACTIVATION_MANIFEST_PATH,
            "status": "A",
            "mode": "100644",
            "bytes": _git_blob_record(
                repo_root,
                head,
                ACTIVATION_MANIFEST_PATH,
            )["bytes"],
            "sha256": _git_blob_record(
                repo_root,
                head,
                ACTIVATION_MANIFEST_PATH,
            )["sha256"],
        }
    ]:
        _fail("U commit is not the exact data-only activation")
    if verify_remote:
        helper_before = _https_helper_record()
        remote = _git(
            repo_root,
            ["ls-remote", "--heads", LIVE_REMOTE_URL, "refs/heads/main"],
        )
        try:
            fields = remote.decode("ascii").strip().split()
        except UnicodeDecodeError as exc:
            raise RuntimeError("Closure E0-U live remote response is malformed") from exc
        if fields != [head, "refs/heads/main"]:
            _fail("live remote main is not aligned to U")
        if _https_helper_record() != helper_before:
            _fail("HTTPS Git helper changed during live-remote authentication")
    return head


def _git_bound_authority_source_record(repo_root, head, verify_remote):
    import stat

    physical = _basic_regular_record(repo_root, AUTHORITY_SOURCE_PATH)
    blob = _git_blob_record(repo_root, head, AUTHORITY_SOURCE_PATH)
    if (
        blob["payload"]
        != _read_regular_relative(repo_root, AUTHORITY_SOURCE_PATH, 0o644, 1)[0]
        or blob["mode"] != stat.S_IMODE(0o100644)
    ):
        _fail("authority source is not identical across worktree and HEAD")
    index = _git(repo_root, ["ls-files", "--stage", "-z", "--", AUTHORITY_SOURCE_PATH])
    expected_index = (
        "100644 " + blob["git_oid"] + " 0\t" + AUTHORITY_SOURCE_PATH + "\x00"
    ).encode("utf-8")
    if index != expected_index:
        _fail("authority source index binding drifted")
    if verify_remote:
        live_remote_main = head
    else:
        live_remote_main = head
    return {
        **physical,
        "git_head": head,
        "git_oid": blob["git_oid"],
        "git_mode": "100644",
        "index_oid": blob["git_oid"],
        "index_mode": "100644",
        "head_ref": "refs/heads/main",
        "origin_head_ref": "refs/remotes/origin/main",
        "refs_aligned": True,
        "live_remote_url": LIVE_REMOTE_URL,
        "live_remote_main": live_remote_main,
        "content_addressed_commit_tree_blob": True,
        "staged_changes_present": False,
        "untracked": False,
    }


def _validate_manifest_bindings(repo_root, head, manifest):
    from collections.abc import Mapping

    runner = _validate_source_record(
        repo_root,
        head,
        manifest["sealed_runner_source_record"],
        RUNNER_SOURCE_PATH,
    )
    context_builder = _validate_source_record(
        repo_root,
        head,
        manifest["sealed_context_builder_source_record"],
        CONTEXT_BUILDER_SOURCE_PATH,
    )
    components_raw = manifest["sealed_component_source_records"]
    if type(components_raw) is not list or len(components_raw) != 10:
        _fail("sealed component source records are absent")
    components = []
    seen_paths = set()
    for raw_record, expected_binding in zip(
        components_raw, EXPECTED_COMPONENT_BINDINGS, strict=True
    ):
        if not isinstance(raw_record, Mapping):
            _fail("sealed component source record is malformed")
        module_name = raw_record.get("module_name")
        component_id = raw_record.get("component_id")
        if (
            (component_id, module_name, raw_record.get("source_path"))
            != expected_binding
            or raw_record.get("status") != "ready"
        ):
            _fail("sealed component module name drifted")
        record = _validate_source_record(
            repo_root,
            head,
            raw_record,
            None,
        )
        path = record.get("path", record.get("source_path"))
        if path in seen_paths:
            _fail("sealed component source path is duplicated")
        seen_paths.add(path)
        components.append(record)
    support_raw = manifest["sealed_support_source_records"]
    if type(support_raw) is not list or len(support_raw) != 3:
        _fail("sealed support source record scope drifted")
    expected_support = (
        ("mifal_ed_t2", "src.mifal.ed_t2"),
        ("mifal_closure_panel_adapter", "src.mifal.closure_panel_adapter"),
        (
            "closure_e10_source_evidence",
            "src.experiments.build_closure_e10_source_evidence",
        ),
    )
    support = []
    for raw_record, expected in zip(support_raw, expected_support, strict=True):
        if (
            not isinstance(raw_record, Mapping)
            or raw_record.get("support_id") != expected[0]
            or raw_record.get("module_name") != expected[1]
            or raw_record.get("status") != "ready"
        ):
            _fail("sealed support source record order or status drifted")
        record = _validate_source_record(
            repo_root,
            head,
            raw_record,
            None,
        )
        path = record.get("path", record.get("source_path"))
        if path in seen_paths:
            _fail("sealed support source path is duplicated")
        seen_paths.add(path)
        support.append(record)
    runtime = manifest["sealed_runtime_environment_record"]
    if not isinstance(runtime, Mapping) or not runtime:
        _fail("sealed runtime environment record is absent")
    return runner, context_builder, components, support, dict(runtime)


def _validate_activation_without_contract(manifest):
    from collections.abc import Mapping

    if not isinstance(manifest, Mapping) or set(manifest) != set(
        ACTIVATION_MANIFEST_KEYS
    ):
        _fail("activation manifest keys drifted")
    expected = {
        "schema_version": ACTIVATION_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "gate": GATE,
        "base_r_commit": BASE_R_COMMIT,
        "git_remote_url": LIVE_REMOTE_URL,
        "sealed_batch_command": SEALED_BATCH_COMMAND,
    }
    for key, value in expected.items():
        if type(manifest.get(key)) is not type(value) or manifest.get(key) != value:
            _fail("activation manifest scalar drifted: " + key)
    for key in (
        "h_commit",
        "p_commit",
        "sealed_batch_contract_sha256",
        "expected_artifact_paths_sha256",
        "expected_publication_order_sha256",
    ):
        value = manifest.get(key)
        expected_length = 64 if key.endswith("sha256") else 40
        if type(value) is not str or len(value) != expected_length:
            _fail("activation digest or commit is malformed: " + key)
        if any(character not in "0123456789abcdef" for character in value):
            _fail("activation digest or commit is malformed: " + key)
    execution_id = manifest.get("execution_id")
    if (
        type(execution_id) is not str
        or not (16 <= len(execution_id) <= 128)
        or any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for character in execution_id
        )
    ):
        _fail("activation execution id is malformed")
    h_scope = _validate_scope_records(manifest["h_scope"], "H")
    p_scope = _validate_scope_records(manifest["p_scope"], "P")
    h_by_path = {record["path"]: record for record in h_scope}
    if {
        path: h_by_path.get(path, {}).get("status")
        for path in (
            AUTHORITY_SOURCE_PATH,
            CONTEXT_BUILDER_SOURCE_PATH,
            RUNNER_SOURCE_PATH,
        )
    } != {
        AUTHORITY_SOURCE_PATH: "A",
        CONTEXT_BUILDER_SOURCE_PATH: "A",
        RUNNER_SOURCE_PATH: "M",
    }:
        _fail("H scope does not contain the exact authority/context/runner overlay")
    h_paths = set(h_by_path)
    p_paths = {record["path"] for record in p_scope}
    forbidden = {ACTIVATION_MANIFEST_PATH, OUTCOME_ACCESS_LOG_PATH}
    if (
        tuple(record["path"] for record in p_scope) != EXPECTED_P_SCOPE_PATHS
        or any(record["status"] != "A" or record["mode"] != "100644" for record in p_scope)
        or any(
            not (
                record["path"].startswith("reports/closure_v1/")
                or record["path"].startswith("data/closure_v1/")
                or record["path"].startswith("models/closure_v1/")
                or record["path"] == "models.dvc"
            )
            or record["path"].endswith((".py", ".pyi"))
            for record in p_scope
        )
        or h_paths & p_paths
        or forbidden & (h_paths | p_paths)
    ):
        _fail("H/P scopes are not disjoint code-then-data-only boundaries")
    if len({BASE_R_COMMIT, manifest["h_commit"], manifest["p_commit"]}) != 3:
        _fail("R/H/P commit identities are not distinct")
    if not isinstance(manifest.get("dvc_policy"), Mapping):
        _fail("activation DVC policy is absent")
    _validate_phase3_overlay_deep_validation(
        manifest["phase3_overlay_deep_validation"],
        manifest["h_commit"],
    )
    return dict(manifest)


def _require_empty_access_log(repo_root):
    payload, metadata = _read_regular_relative(
        repo_root,
        OUTCOME_ACCESS_LOG_PATH,
        0o644,
        1,
    )
    if payload != b"" or metadata.st_size != 0:
        _fail("outcome access log is already non-empty; retry is forbidden")


def _require_outputs_absent(repo_root, expected_paths):
    for path in expected_paths:
        if _relative_leaf_state(repo_root, path) is not None:
            _fail("sealed output already exists: " + path)


def _public_authority_matches(value):
    from collections.abc import Mapping

    expected = _STATE["public_authority"]
    if not isinstance(value, Mapping) or dict(value) != expected:
        _fail("public authority payload drifted")
    return dict(value)


def _contract_matches(value):
    layout = _contract_layout(value)
    if layout["contract_sha256"] != _STATE["contract_sha256"]:
        _fail("sealed batch contract changed after authority activation")
    if _STATE["expected_artifact_paths"] is not None and (
        layout["expected_paths"] != _STATE["expected_artifact_paths"]
        or layout["publication_order"] != _STATE["expected_publication_order"]
        or layout["manifest_by_stage"] != _STATE["manifest_last_paths"]
        or len(layout["stage_ids"]) != _STATE["stage_count"]
    ):
        _fail("sealed batch artifact layout changed after outcome opening")
    return layout


def require_closure_e0_u_authority(verify_remote=True, repo_root=None):
    """Validate the clean R-H-P-U chain without opening or writing outcomes."""

    if type(verify_remote) is not bool or repo_root is None:
        _fail("authority arguments are malformed")
    if _STATE["required"] or _STATE["opened"] or _STATE["published"]:
        _fail("authority require may run only once per process")
    root = _resolved_repo_root(repo_root)
    root_identity = _repository_root_identity(root)
    git_record = _absolute_executable_record(
        GIT_EXECUTABLE_PATH,
        GIT_EXECUTABLE_SHA256,
    )
    env_record = _absolute_executable_record(
        ENV_EXECUTABLE_PATH,
        ENV_EXECUTABLE_SHA256,
    )
    manifest_payload, _ = _read_regular_relative(
        root,
        ACTIVATION_MANIFEST_PATH,
        0o644,
        1,
    )
    import json

    try:
        manifest_preview = json.loads(manifest_payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("Closure E0-U activation manifest cannot be decoded") from exc
    if not isinstance(manifest_preview, dict):
        _fail("activation manifest is not a JSON object")
    if _canonical_json_bytes(manifest_preview) != manifest_payload:
        _fail("activation manifest encoding is not canonical")
    # The caller supplies the actual contract only to later APIs.  The activation
    # manifest nevertheless binds its digest; topology/source validation happens
    # now, while the exact layout is recovered from a compact manifest projection.
    synthetic_contract = manifest_preview.get("sealed_batch_contract")
    if synthetic_contract is not None:
        _fail("activation manifest must not embed a mutable batch contract")
    contract_projection = manifest_preview.get("contract_projection")
    if contract_projection is not None:
        _fail("activation manifest contains a forbidden contract projection")
    # Validate manifest structure before Git.  Layout fields are checked against
    # the runner-provided contract in ``open_sealed_batch_context``; require binds
    # the published digests without importing the runner.
    manifest_preview = _validate_activation_without_contract(manifest_preview)
    head = _validate_git_topology(root, manifest_preview, verify_remote)
    h_scope = _validate_scope_records(manifest_preview["h_scope"], "H")
    p_scope = _validate_scope_records(manifest_preview["p_scope"], "P")
    if _git_diff_scope(root, BASE_R_COMMIT, manifest_preview["h_commit"]) != h_scope:
        _fail("H scope binding drifted")
    if _git_diff_scope(root, manifest_preview["h_commit"], manifest_preview["p_commit"]) != p_scope:
        _fail("P scope binding drifted")
    bindings = _validate_manifest_bindings(root, head, manifest_preview)
    overlay_record = _validate_phase3_overlay_bundle(
        root,
        manifest_preview["h_commit"],
        manifest_preview["p_commit"],
    )
    _validate_phase3_overlay_deep_validation(
        manifest_preview["phase3_overlay_deep_validation"],
        manifest_preview["h_commit"],
        overlay_record,
        root,
    )
    _require_empty_access_log(root)
    authority_source = _git_bound_authority_source_record(root, head, verify_remote)
    if _absolute_executable_record(
        GIT_EXECUTABLE_PATH,
        GIT_EXECUTABLE_SHA256,
    ) != git_record or _absolute_executable_record(
        ENV_EXECUTABLE_PATH,
        ENV_EXECUTABLE_SHA256,
    ) != env_record:
        _fail("sealed executable changed during authority validation")
    result = {
        "gate": GATE,
        "historical_e0_m_commit": BASE_R_COMMIT,
        "phase3_code_commit": manifest_preview["h_commit"],
        "phase3_evidence_commit": manifest_preview["p_commit"],
        "phase3_activation_commit": head,
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
        "sealed_batch_command": SEALED_BATCH_COMMAND,
        "sealed_authority_source_record": authority_source,
        "sealed_runner_source_record": bindings[0],
        "sealed_context_builder_source_record": bindings[1],
        "sealed_component_source_records": bindings[2],
        "sealed_support_source_records": bindings[3],
        "sealed_runtime_environment_record": bindings[4],
        "sealed_git_executable_record": git_record,
        "sealed_env_executable_record": env_record,
    }
    if set(result) != set(AUTHORITY_RESULT_KEYS):
        _fail("authority result keys drifted")
    if _repository_root_identity(root) != root_identity:
        _fail("repository root changed during authority require")
    _STATE["required"] = True
    _STATE["repo_root"] = root
    _STATE["repo_root_identity"] = root_identity
    _STATE["manifest"] = dict(manifest_preview)
    _STATE["public_authority"] = dict(result)
    _STATE["contract_sha256"] = manifest_preview["sealed_batch_contract_sha256"]
    _STATE["execution_id"] = manifest_preview["execution_id"]
    return result


def _create_guard(repo_root, expected_root_identity):
    import os
    import stat

    owned_directories = []
    parent_anchor = _open_parent_directory_anchor(
        repo_root,
        RUN_GUARD_PATH,
        True,
        owned_directories,
        expected_root_identity,
    )
    parent_fd = _anchor_parent_fd(parent_anchor)
    leaf = parent_anchor["leaf"]
    descriptor = None
    owned_record = None
    try:
        descriptor = os.open(
            leaf,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        metadata = os.fstat(descriptor)
        owned_record = {
            "path": RUN_GUARD_PATH,
            "device": int(metadata.st_dev),
            "inode": int(metadata.st_ino),
        }
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
            or metadata.st_size != 0
        ):
            _fail("exclusive run guard identity drifted")
        os.fsync(descriptor)
        os.fsync(parent_fd)
        _recapture_parent_directory_anchor(parent_anchor, "exclusive run guard")
        return descriptor, owned_record, owned_directories, parent_anchor
    except BaseException as guard_error:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        cleanup_errors = []
        try:
            _unlink_anchored_identity(
                parent_fd,
                leaf,
                owned_record,
                "exclusive run guard",
            )
        except BaseException as exc:
            cleanup_errors.append(exc)
        try:
            _rollback_owned_directories(repo_root, owned_directories)
        except BaseException as exc:
            cleanup_errors.append(exc)
        finally:
            _close_parent_directory_anchor(parent_anchor)
        if cleanup_errors:
            raise RuntimeError(
                "Closure E0-U authority rejected operation: exclusive run guard "
                "cleanup was incomplete"
            ) from cleanup_errors[0]
        raise guard_error


def _append_first_access_record(repo_root, execution_id):
    import os
    import stat
    from typing import cast

    record = {
        "event": "sealed_outcome_context_opened",
        "execution_id": execution_id,
        "experiment_id": EXPERIMENT_ID,
        "gate": GATE,
        "one_shot_consumed": True,
        "outcome_access_authorized": True,
        "schema_version": ACCESS_LOG_SCHEMA_VERSION,
    }
    payload = _canonical_json_bytes(record)
    guard_anchor = cast(dict, _STATE["guard_parent_anchor"])
    if not isinstance(guard_anchor, dict) or guard_anchor.get("closed"):
        _fail("guarded repository root is absent before outcome logging")
    parent_anchor = _open_parent_directory_anchor(
        repo_root,
        OUTCOME_ACCESS_LOG_PATH,
        False,
        [],
        _STATE["repo_root_identity"],
    )
    parent_fd = _anchor_parent_fd(parent_anchor)
    leaf = parent_anchor["leaf"]
    descriptor = None
    try:
        if parent_anchor["root_identity"] != guard_anchor["root_identity"]:
            _fail("access log repository root is not the guarded root")
        _recapture_parent_directory_anchor(
            guard_anchor,
            "exclusive run guard before outcome logging",
        )
        _recapture_parent_directory_anchor(
            parent_anchor,
            "outcome access log before append",
        )
        before = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        descriptor = os.open(
            leaf,
            os.O_RDWR | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o644
            or before.st_nlink != 1
            or opened.st_nlink != 1
            or before.st_size != 0
            or (before.st_dev, before.st_ino, before.st_size, before.st_mode)
            != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mode)
        ):
            _fail("outcome access log is not the exact empty sealed file")
        position = 0
        while position < len(payload):
            written = os.write(descriptor, payload[position:])
            if written <= 0:
                _fail("durable access log write made no progress")
            position += written
        os.fsync(descriptor)
        after = os.fstat(descriptor)
        if (
            after.st_dev != opened.st_dev
            or after.st_ino != opened.st_ino
            or after.st_mode != opened.st_mode
            or after.st_size != len(payload)
            or after.st_nlink != 1
        ):
            _fail("durable access log identity drifted after fsync")
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks = []
        while True:
            chunk = os.read(descriptor, 4096)
            if not chunk:
                break
            chunks.append(chunk)
        after_read = os.fstat(descriptor)
        named_after = os.stat(
            leaf,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if (
            b"".join(chunks) != payload
            or after_identity
            != (
                after_read.st_dev,
                after_read.st_ino,
                after_read.st_mode,
                after_read.st_nlink,
                after_read.st_size,
                after_read.st_mtime_ns,
                after_read.st_ctime_ns,
            )
            or after_identity
            != (
                named_after.st_dev,
                named_after.st_ino,
                named_after.st_mode,
                named_after.st_nlink,
                named_after.st_size,
                named_after.st_mtime_ns,
                named_after.st_ctime_ns,
            )
        ):
            _fail("durable access log bytes or inode drifted after append")
        os.fsync(parent_fd)
        _recapture_parent_directory_anchor(
            parent_anchor,
            "outcome access log after append",
        )
        _recapture_parent_directory_anchor(
            guard_anchor,
            "exclusive run guard after outcome logging",
        )
        lease = {
            "descriptor": descriptor,
            "parent_anchor": parent_anchor,
            "leaf": leaf,
            "file_identity": after_identity,
            "payload": payload,
            "closed": False,
        }
        identity = {
            "device": int(after.st_dev),
            "inode": int(after.st_ino),
        }
        descriptor = None
        parent_anchor = None
        return record, identity, lease
    finally:
        if descriptor is not None:
            os.close(descriptor)
        _close_parent_directory_anchor(parent_anchor)


def _recapture_access_log_lease(lease, label):
    import os

    if not isinstance(lease, dict) or lease.get("closed"):
        _fail(label + " access log lease is absent")
    descriptor = lease.get("descriptor")
    anchor = lease.get("parent_anchor")
    leaf = lease.get("leaf")
    expected_identity = lease.get("file_identity")
    expected_payload = lease.get("payload")
    if (
        type(descriptor) is not int
        or not isinstance(anchor, dict)
        or type(leaf) is not str
        or not isinstance(expected_identity, tuple)
        or type(expected_payload) is not bytes
    ):
        _fail(label + " access log lease is malformed")
    try:
        before = os.fstat(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks = []
        while True:
            chunk = os.read(descriptor, 4096)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        named = os.stat(
            leaf,
            dir_fd=_anchor_parent_fd(anchor),
            follow_symlinks=False,
        )
    except OSError as exc:
        raise RuntimeError(
            "Closure E0-U authority rejected operation: "
            + label
            + " access log leaf disappeared"
        ) from exc
    observed_identities = (
        (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ),
        (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ),
        (
            named.st_dev,
            named.st_ino,
            named.st_mode,
            named.st_nlink,
            named.st_size,
            named.st_mtime_ns,
            named.st_ctime_ns,
        ),
    )
    if (
        any(identity != expected_identity for identity in observed_identities)
        or b"".join(chunks) != expected_payload
    ):
        _fail(label + " access log leaf or bytes drifted")
    _recapture_parent_directory_anchor(anchor, label + " access log")


def _close_access_log_lease(lease):
    import os

    if not isinstance(lease, dict) or lease.get("closed"):
        return
    descriptor = lease.get("descriptor")
    if type(descriptor) is int:
        try:
            os.close(descriptor)
        except OSError:
            pass
    _close_parent_directory_anchor(lease.get("parent_anchor"))
    lease["descriptor"] = None
    lease["parent_anchor"] = None
    lease["closed"] = True


def _require_exact_access_record(repo_root):
    from typing import cast

    expected = {
        "event": "sealed_outcome_context_opened",
        "execution_id": _STATE["execution_id"],
        "experiment_id": EXPERIMENT_ID,
        "gate": GATE,
        "one_shot_consumed": True,
        "outcome_access_authorized": True,
        "schema_version": ACCESS_LOG_SCHEMA_VERSION,
    }
    payload, metadata = _read_regular_relative(
        repo_root,
        OUTCOME_ACCESS_LOG_PATH,
        0o644,
        1,
    )
    identity = cast(dict, _STATE["access_log_identity"])
    if (
        payload != _canonical_json_bytes(expected)
        or not isinstance(identity, dict)
        or (metadata.st_dev, metadata.st_ino)
        != (identity.get("device"), identity.get("inode"))
    ):
        _fail("one-shot access log bytes or inode drifted")
    return payload


def _release_owned_guard(remove_owned_directories):
    import os
    from typing import cast

    descriptor = cast(int, _STATE["guard_fd"])
    record = cast(dict, _STATE["guard_record"])
    anchor = cast(dict, _STATE["guard_parent_anchor"])
    if (
        descriptor is None
        or not isinstance(record, dict)
        or not isinstance(anchor, dict)
    ):
        _fail("run guard state is absent")
    parent_fd = _anchor_parent_fd(anchor)
    leaf = anchor["leaf"]
    cleanup_error = None
    directory_error = None
    try:
        metadata = os.fstat(descriptor)
        if (
            (metadata.st_dev, metadata.st_ino)
            != (record["device"], record["inode"])
        ):
            _fail("run guard descriptor is no longer the authority-owned inode")
        if not _unlink_anchored_identity(
            parent_fd,
            leaf,
            record,
            "exclusive run guard",
        ):
            _fail("run guard disappeared before cleanup")
        _recapture_parent_directory_anchor(anchor, "exclusive run guard cleanup")
    except BaseException as exc:
        cleanup_error = exc
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        _STATE["guard_fd"] = None
        if remove_owned_directories:
            try:
                _rollback_owned_directories(
                    _STATE["repo_root"],
                    _STATE["guard_owned_directories"] or [],
                )
            except BaseException as exc:
                directory_error = exc
        try:
            _close_parent_directory_anchor(anchor)
        finally:
            _STATE["guard_parent_anchor"] = None
            _STATE["guard_owned_directories"] = None
    if cleanup_error is None and directory_error is not None:
        cleanup_error = directory_error
    if cleanup_error is not None:
        raise cleanup_error


def open_sealed_batch_context(
    authority,
    sealed_batch_contract,
    repo_root,
    context_builder,
):
    """Consume the one-shot boundary, then invoke the injected DataFrame builder."""

    from collections.abc import Mapping
    from typing import cast

    if (
        not _STATE["required"]
        or _STATE["opened"]
        or _STATE["published"]
        or _STATE["failed"]
        or not callable(context_builder)
    ):
        _fail("sealed context may be opened exactly once after require")
    _public_authority_matches(authority)
    root = _resolved_repo_root(repo_root)
    if (
        root != _STATE["repo_root"]
        or _repository_root_identity(root) != _STATE["repo_root_identity"]
    ):
        _fail("repository root changed after authority require")
    layout = _contract_matches(sealed_batch_contract)
    manifest = cast(dict, _STATE["manifest"])
    if manifest["expected_artifact_paths_sha256"] != _sha256_bytes(
        _canonical_json_bytes(list(layout["expected_paths"]))
    ) or manifest["expected_publication_order_sha256"] != _sha256_bytes(
        _canonical_json_bytes(list(layout["publication_order"]))
    ):
        _fail("activation manifest does not bind the live exact52 layout")
    _validate_dvc_policy(
        manifest["dvc_policy"],
        layout["expected_paths"],
        layout["formats_by_path"],
    )
    _require_empty_access_log(root)
    _require_outputs_absent(root, layout["expected_paths"])
    if _relative_leaf_state(root, RUN_GUARD_PATH) is not None:
        _fail("E0-U run guard already exists")
    try:
        descriptor, guard_record, owned_directories, guard_anchor = _create_guard(
            root,
            _STATE["repo_root_identity"],
        )
    except BaseException:
        _STATE["failed"] = True
        raise
    _STATE["guard_fd"] = descriptor
    _STATE["guard_record"] = guard_record
    _STATE["guard_parent_anchor"] = guard_anchor
    _STATE["guard_owned_directories"] = owned_directories
    _STATE["opened"] = True
    _STATE["expected_artifact_paths"] = layout["expected_paths"]
    _STATE["expected_publication_order"] = layout["publication_order"]
    _STATE["manifest_last_paths"] = layout["manifest_by_stage"]
    _STATE["stage_count"] = len(layout["stage_ids"])
    execution_id = _STATE["execution_id"]
    try:
        _, log_identity, log_lease = _append_first_access_record(
            root,
            execution_id,
        )
    except BaseException as log_error:
        _STATE["failed"] = True
        try:
            _release_owned_guard(True)
        except BaseException as cleanup_error:
            raise log_error from cleanup_error
        raise
    _STATE["access_log_identity"] = log_identity
    _STATE["access_log_lease"] = log_lease
    try:
        _recapture_access_log_lease(
            log_lease,
            "before context materialization",
        )
        _recapture_parent_directory_anchor(
            _STATE["guard_parent_anchor"],
            "exclusive run guard before context materialization",
        )
        raw = context_builder(
            authority=dict(authority),
            sealed_batch_contract=dict(sealed_batch_contract),
            repo_root=root,
            execution_id=execution_id,
        )
        _recapture_access_log_lease(
            log_lease,
            "after context materialization",
        )
        _recapture_parent_directory_anchor(
            _STATE["guard_parent_anchor"],
            "exclusive run guard after context materialization",
        )
    except BaseException:
        _STATE["failed"] = True
        _close_access_log_lease(log_lease)
        _STATE["access_log_lease"] = None
        raise
    _close_access_log_lease(log_lease)
    _STATE["access_log_lease"] = None
    if not isinstance(raw, Mapping) or raw.get("execution_id") != execution_id:
        _STATE["failed"] = True
        _fail("injected context builder returned a malformed context")
    return dict(raw)


def _validate_artifact_inputs(
    artifacts,
    serialized_artifacts,
    batch_context,
    stage_results,
    layout,
):
    from collections.abc import Mapping

    if (
        not isinstance(artifacts, Mapping)
        or not isinstance(serialized_artifacts, Mapping)
        or set(artifacts) != set(layout["expected_paths"])
        or set(serialized_artifacts) != set(layout["expected_paths"])
    ):
        _fail("publication artifact scope is not exact52")
    if not isinstance(batch_context, Mapping) or batch_context.get("execution_id") != _STATE["execution_id"]:
        _fail("publication batch context identity drifted")
    if not isinstance(stage_results, Mapping) or set(stage_results) != set(layout["stage_ids"]):
        _fail("publication stage result scope drifted")
    terminal_paths = set(layout["manifest_by_stage"].values())
    for path in layout["expected_paths"]:
        envelope = artifacts[path]
        if not isinstance(envelope, Mapping) or set(envelope) != {"format", "payload", "manifest_last"}:
            _fail("artifact envelope keys drifted: " + path)
        if envelope["format"] != layout["formats_by_path"][path]:
            _fail("artifact format drifted: " + path)
        if type(envelope["manifest_last"]) is not bool or envelope["manifest_last"] != (path in terminal_paths):
            _fail("artifact manifest-last marker drifted: " + path)
        if type(serialized_artifacts[path]) is not bytes:
            _fail("runner-side serialized artifact is not bytes: " + path)


def _write_all(descriptor, payload):
    import os

    position = 0
    while position < len(payload):
        written = os.write(descriptor, payload[position:])
        if written <= 0:
            _fail("publication write made no progress")
        position += written


def _rename_noreplace_at(
    source_directory_fd,
    source_name,
    target_directory_fd,
    target_name,
):
    import ctypes
    import os

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


def _unlink_anchored_identity(parent_fd, leaf, record, label):
    import os
    import stat

    if not isinstance(record, dict):
        return False
    try:
        before = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    expected_identity = (
        record.get("device"),
        record.get("inode"),
    )
    if (before.st_dev, before.st_ino) != expected_identity:
        _fail("refusing to unlink a replaced " + label)

    # An atomically-created, mode-0700 random directory gives rename an
    # exclusive destination namespace.  If the source name changes at the
    # rename boundary, renameat2 restores every entry type without clobber.
    # Same-UID interference with this unpredictable private tombstone after it
    # has captured the name is outside the threat model: Linux offers no
    # conditional unlink; ctypes/libc are already part of the sealed runtime.
    tombstone_leaf = None
    tombstone_fd = None
    tombstone_identity = None
    for _attempt in range(16):
        candidate = ".closure-owned-capture-" + os.urandom(16).hex()
        try:
            os.mkdir(candidate, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        tombstone_leaf = candidate
        try:
            tombstone_fd = os.open(
                candidate,
                os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
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
                _fail(label + " tombstone namespace was replaced")
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
        _fail(label + " tombstone namespace is unavailable")
    assert type(tombstone_leaf) is str
    assert type(tombstone_fd) is int
    capture_directory_leaf = tombstone_leaf
    capture_directory_fd = tombstone_fd

    captured_leaf = "captured"
    captured_present = False
    try:
        try:
            os.rename(
                leaf,
                captured_leaf,
                src_dir_fd=parent_fd,
                dst_dir_fd=capture_directory_fd,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Closure E0-U authority rejected operation: "
                + label
                + " disappeared at cleanup boundary"
            ) from exc
        captured_present = True
        os.fsync(parent_fd)
        os.fsync(capture_directory_fd)
        captured = os.stat(
            captured_leaf,
            dir_fd=capture_directory_fd,
            follow_symlinks=False,
        )
        captured_identity = (captured.st_dev, captured.st_ino)
        if captured_identity != expected_identity:
            try:
                _rename_noreplace_at(
                    capture_directory_fd,
                    captured_leaf,
                    parent_fd,
                    leaf,
                )
            except OSError as exc:
                raise RuntimeError(
                    "Closure E0-U authority rejected operation: "
                    + label
                    + " foreign inode could not be restored without clobber"
                ) from exc
            restored = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
            if (restored.st_dev, restored.st_ino) != captured_identity:
                _fail(label + " foreign inode restoration drifted")
            os.fsync(parent_fd)
            captured_present = False
            os.fsync(capture_directory_fd)
            _fail(label + " was replaced at cleanup boundary")
        os.unlink(captured_leaf, dir_fd=capture_directory_fd)
        captured_present = False
        os.fsync(capture_directory_fd)
    finally:
        os.close(capture_directory_fd)
        if not captured_present:
            try:
                named_directory = os.stat(
                    capture_directory_leaf,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if (
                    tombstone_identity is not None
                    and _directory_identity(named_directory)
                    == tombstone_identity
                ):
                    os.rmdir(capture_directory_leaf, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
    os.fsync(parent_fd)
    return True


def _publish_one(repo_root, relative_path, payload, execution_id, owned_directories):
    import os
    import stat

    owned_directory_start = len(owned_directories)
    parent_anchor = _open_parent_directory_anchor(
        repo_root,
        relative_path,
        True,
        owned_directories,
        _STATE["repo_root_identity"],
    )
    parent_fd = _anchor_parent_fd(parent_anchor)
    leaf = parent_anchor["leaf"]
    temporary_leaf = "." + leaf + ".closure-e0-u-" + execution_id + ".tmp"
    descriptor = None
    temporary_record = None
    final_record = None
    try:
        try:
            os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            _fail("publication would clobber an existing artifact: " + relative_path)
        descriptor = os.open(
            temporary_leaf,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        opened = os.fstat(descriptor)
        temporary_record = {
            "parent_path": "/".join(
                _canonical_relative_parts(relative_path)[:-1]
            ),
            "leaf": temporary_leaf,
            "device": int(opened.st_dev),
            "inode": int(opened.st_ino),
        }
        if (
            not stat.S_ISREG(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_nlink != 1
            or opened.st_size != 0
        ):
            _fail("publication temporary creation identity drifted: " + relative_path)
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o644)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o644
            or metadata.st_nlink != 1
            or metadata.st_size != len(payload)
        ):
            _fail("publication temporary identity drifted: " + relative_path)
        if (metadata.st_dev, metadata.st_ino) != (opened.st_dev, opened.st_ino):
            _fail("publication temporary inode drifted: " + relative_path)
        _recapture_parent_directory_anchor(
            parent_anchor,
            "publication temporary " + relative_path,
        )
        os.link(
            temporary_leaf,
            leaf,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
            follow_symlinks=False,
        )
        final_record = {
            "path": relative_path,
            "device": int(metadata.st_dev),
            "inode": int(metadata.st_ino),
        }
        linked = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        if (linked.st_dev, linked.st_ino) != (metadata.st_dev, metadata.st_ino) or linked.st_nlink != 2:
            _fail("publication hardlink identity drifted: " + relative_path)
        if not _unlink_anchored_identity(
            parent_fd,
            temporary_leaf,
            temporary_record,
            "publication temporary",
        ):
            _fail("publication temporary disappeared: " + relative_path)
        temporary_record = None
        final = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        if (
            (final.st_dev, final.st_ino) != (metadata.st_dev, metadata.st_ino)
            or final.st_nlink != 1
            or stat.S_IMODE(final.st_mode) != 0o644
            or final.st_size != len(payload)
        ):
            _fail("published artifact identity drifted: " + relative_path)
        _recapture_parent_directory_anchor(
            parent_anchor,
            "published artifact " + relative_path,
        )
        final_record["_leaf"] = leaf
        final_record["_anchor"] = parent_anchor
        return final_record
    except BaseException as publication_error:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        cleanup_errors = []
        for cleanup_leaf, cleanup_record, cleanup_label in (
            (leaf, final_record, "publication artifact"),
            (temporary_leaf, temporary_record, "publication temporary"),
        ):
            try:
                _unlink_anchored_identity(
                    parent_fd,
                    cleanup_leaf,
                    cleanup_record,
                    cleanup_label,
                )
            except BaseException as exc:
                cleanup_errors.append(exc)
        try:
            _recapture_parent_directory_anchor(
                parent_anchor,
                "failed publication " + relative_path,
            )
        except BaseException as exc:
            cleanup_errors.append(exc)
        created_records = owned_directories[owned_directory_start:]
        try:
            _rollback_owned_directories(repo_root, created_records)
        except BaseException as exc:
            cleanup_errors.append(exc)
        finally:
            del owned_directories[owned_directory_start:]
            _close_parent_directory_anchor(parent_anchor)
        if cleanup_errors:
            raise RuntimeError(
                "Closure E0-U authority rejected operation: failed publication "
                "cleanup was incomplete: " + relative_path
            ) from cleanup_errors[0]
        raise publication_error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _unlink_owned_leaf(repo_root, record):
    import os

    if not isinstance(record, dict):
        return False
    anchor = record.get("_anchor")
    anchored_leaf = record.get("_leaf")
    if isinstance(anchor, dict) and type(anchored_leaf) is str:
        parent_fd = _anchor_parent_fd(anchor)
        removed = _unlink_anchored_identity(
            parent_fd,
            anchored_leaf,
            record,
            "publication artifact",
        )
        if not removed:
            return False
        _recapture_parent_directory_anchor(
            anchor,
            "publication rollback " + str(record.get("path")),
        )
        return True
    path = record.get("path")
    if type(path) is not str:
        parent_path = record.get("parent_path")
        leaf = record.get("leaf")
        if type(parent_path) is not str or type(leaf) is not str:
            return False
        path = parent_path + "/" + leaf if parent_path else leaf
    try:
        parent_fd, leaf = _open_parent_directory(repo_root, path, False, [])
    except FileNotFoundError:
        return False
    try:
        return _unlink_anchored_identity(
            parent_fd,
            leaf,
            record,
            "publication artifact",
        )
    finally:
        os.close(parent_fd)


def _remove_anchored_directory_identity(parent_fd, leaf, record, label):
    import os
    import stat
    from typing import cast

    if not isinstance(record, dict):
        return False
    expected_identity = (record.get("device"), record.get("inode"))
    try:
        before = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISDIR(before.st_mode)
        or (before.st_dev, before.st_ino) != expected_identity
    ):
        _fail(label + " was replaced before cleanup")

    capture_leaf = None
    capture_fd = None
    capture_identity = None
    for _attempt in range(16):
        candidate = ".closure-owned-directory-capture-" + os.urandom(16).hex()
        try:
            os.mkdir(candidate, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        capture_leaf = candidate
        capture_fd = os.open(
            candidate,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        opened = os.fstat(capture_fd)
        named = os.stat(candidate, dir_fd=parent_fd, follow_symlinks=False)
        capture_identity = _directory_identity(opened)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o700
            or _directory_identity(named) != capture_identity
        ):
            os.close(capture_fd)
            _fail(label + " capture namespace drifted")
        break
    if type(capture_leaf) is not str or type(capture_fd) is not int:
        _fail(label + " capture namespace is unavailable")

    private_leaf = cast(str, capture_leaf)
    private_fd = cast(int, capture_fd)
    captured_leaf = "captured"
    captured_present = False
    try:
        os.rename(
            leaf,
            captured_leaf,
            src_dir_fd=parent_fd,
            dst_dir_fd=private_fd,
        )
        captured_present = True
        captured = os.stat(
            captured_leaf,
            dir_fd=private_fd,
            follow_symlinks=False,
        )
        captured_identity = (captured.st_dev, captured.st_ino)
        if captured_identity != expected_identity:
            _rename_noreplace_at(private_fd, captured_leaf, parent_fd, leaf)
            captured_present = False
            os.fsync(parent_fd)
            _fail(label + " was replaced at cleanup boundary")
        try:
            os.rmdir(captured_leaf, dir_fd=private_fd)
        except OSError as exc:
            try:
                _rename_noreplace_at(private_fd, captured_leaf, parent_fd, leaf)
                captured_present = False
                os.fsync(parent_fd)
            except OSError:
                pass
            raise RuntimeError(
                "Closure E0-U authority rejected operation: "
                + label
                + " is not empty during cleanup"
            ) from exc
        captured_present = False
        os.fsync(private_fd)
    finally:
        try:
            os.close(private_fd)
        except OSError:
            pass
        if not captured_present:
            try:
                named_capture = os.stat(
                    private_leaf,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if (
                    capture_identity is not None
                    and _directory_identity(named_capture) == capture_identity
                ):
                    os.rmdir(private_leaf, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
    os.fsync(parent_fd)
    return True


def _rollback_owned_directories(repo_root, owned_directories):
    import os

    cleanup_errors = []
    for record in reversed(list(owned_directories)):
        anchored_parent = record.get("_parent_fd")
        anchored_leaf = record.get("_leaf")
        if type(anchored_parent) is int and type(anchored_leaf) is str:
            try:
                _remove_anchored_directory_identity(
                    anchored_parent,
                    anchored_leaf,
                    record,
                    "owned directory " + str(record.get("path")),
                )
            except BaseException as exc:
                cleanup_errors.append(exc)
            continue
        path = record.get("path")
        if type(path) is not str:
            cleanup_errors.append(
                RuntimeError(
                    "Closure E0-U authority rejected operation: owned "
                    "directory record is malformed"
                )
            )
            continue
        parts = _canonical_relative_parts(path)
        if len(parts) == 1:
            parent_fd = _open_root_directory(repo_root)
            leaf = parts[0]
        else:
            try:
                parent_fd, leaf = _open_parent_directory(repo_root, path, False, [])
            except FileNotFoundError:
                continue
            except OSError as exc:
                cleanup_errors.append(exc)
                continue
        try:
            try:
                _remove_anchored_directory_identity(
                    parent_fd,
                    leaf,
                    record,
                    "owned directory " + path,
                )
            except BaseException as exc:
                cleanup_errors.append(exc)
        finally:
            try:
                os.close(parent_fd)
            except OSError:
                pass
    if cleanup_errors:
        raise RuntimeError(
            "Closure E0-U authority rejected operation: owned directory "
            "cleanup was incomplete"
        ) from cleanup_errors[0]


def _close_publication_anchors(records):
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        anchor = record.get("_anchor")
        if not isinstance(anchor, dict) or id(anchor) in seen:
            continue
        seen.add(id(anchor))
        _close_parent_directory_anchor(anchor)


def _recapture_published_record(record, expected_size):
    import os
    import stat

    if not isinstance(record, dict):
        _fail("published artifact record is malformed")
    anchor = record.get("_anchor")
    leaf = record.get("_leaf")
    if not isinstance(anchor, dict) or type(leaf) is not str:
        _fail("published artifact anchor is absent")
    metadata = os.stat(
        leaf,
        dir_fd=_anchor_parent_fd(anchor),
        follow_symlinks=False,
    )
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o644
        or metadata.st_nlink != 1
        or metadata.st_size != expected_size
        or (metadata.st_dev, metadata.st_ino)
        != (record.get("device"), record.get("inode"))
    ):
        _fail("published artifact identity drifted before transaction close")
    _recapture_parent_directory_anchor(
        anchor,
        "published artifact transaction close " + str(record.get("path")),
    )


def _plain_published_record(record):
    return {
        "path": record["path"],
        "device": record["device"],
        "inode": record["inode"],
    }


def _rollback_publication(repo_root, final_records, temporary_records, owned_directories):
    rollback_errors = []
    for record in reversed(list(final_records)):
        try:
            _unlink_owned_leaf(repo_root, record)
        except BaseException as exc:
            rollback_errors.append(exc)
    for record in reversed(list(temporary_records)):
        try:
            _unlink_owned_leaf(repo_root, record)
        except BaseException as exc:
            rollback_errors.append(exc)
    try:
        _rollback_owned_directories(repo_root, owned_directories)
    except BaseException as exc:
        rollback_errors.append(exc)
    finally:
        _close_publication_anchors([*final_records, *temporary_records])
    if rollback_errors:
        raise RuntimeError(
            "Closure E0-U authority rejected operation: publication rollback "
            "was incomplete"
        ) from rollback_errors[0]


def publish_sealed_batch_artifacts(
    authority,
    sealed_batch_contract,
    batch_context,
    stage_results,
    artifacts,
    serialized_artifacts,
    repo_root,
):
    """Publish runner-serialized bytes in one guarded, no-clobber transaction."""

    import os

    if (
        not _STATE["required"]
        or not _STATE["opened"]
        or _STATE["published"]
        or _STATE["failed"]
    ):
        _fail("publication is not authorized in the current one-shot state")
    _public_authority_matches(authority)
    root = _resolved_repo_root(repo_root)
    if (
        root != _STATE["repo_root"]
        or _repository_root_identity(root) != _STATE["repo_root_identity"]
    ):
        _fail("publication repository root drifted")
    layout = _contract_matches(sealed_batch_contract)
    _validate_artifact_inputs(
        artifacts,
        serialized_artifacts,
        batch_context,
        stage_results,
        layout,
    )
    _require_exact_access_record(root)
    _release_guard_state = _STATE["guard_fd"]
    if _release_guard_state is None:
        _fail("exclusive run guard is absent before publication")
    _require_outputs_absent(root, layout["expected_paths"])
    # The guard is expected to exist here; output absence is checked separately.
    if _relative_leaf_state(root, RUN_GUARD_PATH) is None:
        _fail("exclusive run guard disappeared before publication")
    final_records = []
    temporary_records = []
    owned_directories = []
    try:
        for path in layout["publication_order"]:
            final = _publish_one(
                root,
                path,
                serialized_artifacts[path],
                _STATE["execution_id"],
                owned_directories,
            )
            final_records.append(final)
        for record in final_records:
            _recapture_published_record(
                record,
                len(serialized_artifacts[record["path"]]),
            )
        _release_owned_guard(True)
        for record in final_records:
            _recapture_published_record(
                record,
                len(serialized_artifacts[record["path"]]),
            )
    except BaseException as publication_error:
        rollback_error = None
        guard_error = None
        try:
            _rollback_publication(
                root,
                final_records,
                temporary_records,
                owned_directories,
            )
        except BaseException as exc:
            rollback_error = exc
        _STATE["failed"] = True
        descriptor = _STATE["guard_fd"]
        if type(descriptor) is int:
            try:
                _release_owned_guard(True)
            except BaseException as exc:
                guard_error = exc
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                _STATE["guard_fd"] = None
        if rollback_error is not None:
            raise rollback_error from publication_error
        if guard_error is not None:
            raise RuntimeError(
                "Closure E0-U authority rejected operation: publication guard "
                "cleanup was incomplete"
            ) from guard_error
        raise publication_error
    plain_final_records = [_plain_published_record(record) for record in final_records]
    _close_publication_anchors(final_records)
    _STATE["published"] = True
    _STATE["published_records"] = plain_final_records
    receipt = {
        "status": "sealed_batch_artifacts_published",
        "execution_id": _STATE["execution_id"],
        "batch_contract_sha256": layout["contract_sha256"],
        "artifact_count": len(layout["expected_paths"]),
        "published_artifact_paths_sha256": _sha256_bytes(
            _canonical_json_bytes(list(layout["expected_paths"]))
        ),
        "stage_count": len(layout["stage_ids"]),
        "one_shot_consumed": True,
        "guard_released": True,
        "rollback_performed": False,
        "manifest_written_last": True,
        "writes_performed": True,
    }
    if set(receipt) != set(PUBLICATION_RECEIPT_KEYS):
        _fail("publication receipt keys drifted")
    _STATE["publication_receipt"] = dict(receipt)
    return receipt


def _physical_artifact_record(repo_root, path, expected_payload, owned_record):
    import stat

    payload, metadata = _read_regular_relative(repo_root, path, 0o644, 1)
    if payload != expected_payload:
        _fail("published artifact bytes drifted: " + path)
    if not isinstance(owned_record, dict) or (
        metadata.st_dev,
        metadata.st_ino,
    ) != (owned_record.get("device"), owned_record.get("inode")):
        _fail("published artifact is no longer the authority-owned inode: " + path)
    return {
        "path": path,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "device": int(metadata.st_dev),
        "inode": int(metadata.st_ino),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
        "mtime_ns": int(metadata.st_mtime_ns),
        "ctime_ns": int(metadata.st_ctime_ns),
    }


def validate_published_sealed_batch_artifacts(
    authority,
    sealed_batch_contract,
    batch_context,
    stage_results,
    artifacts,
    serialized_artifacts,
    publication_receipt,
    repo_root,
):
    """Physically re-read every published byte and its inode after publication."""

    from collections.abc import Mapping
    from typing import cast

    if not _STATE["published"] or _STATE["failed"]:
        _fail("physical audit requires a successful publication")
    _public_authority_matches(authority)
    root = _resolved_repo_root(repo_root)
    if (
        root != _STATE["repo_root"]
        or _repository_root_identity(root) != _STATE["repo_root_identity"]
    ):
        _fail("physical audit repository root drifted")
    layout = _contract_matches(sealed_batch_contract)
    _validate_artifact_inputs(
        artifacts,
        serialized_artifacts,
        batch_context,
        stage_results,
        layout,
    )
    if (
        not isinstance(publication_receipt, Mapping)
        or set(publication_receipt) != set(PUBLICATION_RECEIPT_KEYS)
        or dict(publication_receipt) != _STATE["publication_receipt"]
    ):
        _fail("publication receipt drifted before physical audit")
    if _relative_leaf_state(root, RUN_GUARD_PATH) is not None:
        _fail("publication guard remains after successful publication")
    _require_exact_access_record(root)
    published_records = cast(list[dict], _STATE["published_records"])
    owned_by_path = {record["path"]: record for record in published_records}
    physical_records = []
    content_records = []
    for path in layout["expected_paths"]:
        payload = serialized_artifacts[path]
        physical = _physical_artifact_record(
            root,
            path,
            payload,
            owned_by_path.get(path),
        )
        if set(physical) != set(PHYSICAL_RECORD_KEYS):
            _fail("physical artifact record keys drifted")
        physical_records.append(physical)
        content_records.append(
            {
                "path": path,
                "bytes": len(payload),
                "sha256": _sha256_bytes(payload),
            }
        )
    result = {
        "status": "sealed_batch_artifacts_physically_validated",
        "execution_id": _STATE["execution_id"],
        "batch_contract_sha256": layout["contract_sha256"],
        "artifact_count": len(layout["expected_paths"]),
        "published_artifact_paths_sha256": _sha256_bytes(
            _canonical_json_bytes(list(layout["expected_paths"]))
        ),
        "artifact_payloads_sha256": _sha256_bytes(
            _canonical_json_bytes(content_records)
        ),
        "physical_records": physical_records,
        "physical_records_sha256": _sha256_bytes(
            _canonical_json_bytes(physical_records)
        ),
        "publication_order": list(layout["publication_order"]),
        "publication_order_sha256": _sha256_bytes(
            _canonical_json_bytes(list(layout["publication_order"]))
        ),
        "stage_count": len(layout["stage_ids"]),
        "one_shot_consumed": True,
        "guard_released": True,
        "publication_guard_present": False,
        "rollback_performed": False,
        "manifest_written_last": True,
        "writes_performed": True,
    }
    if set(result) != set(PUBLICATION_AUDIT_KEYS):
        _fail("physical publication audit keys drifted")
    return result
