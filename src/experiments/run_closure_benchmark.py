#!/usr/bin/env python
"""Run the single sealed Closure V1 evaluation batch.

The executable is published before formal E0-M.  Import and ``--check-only``
are outcome-free and write-free.  ``--execute-sealed-batch`` delegates its
first operation to the future effective E0-U authority; while that authority
does not exist, execution fails before resolving or opening any outcome path.
"""

from __future__ import annotations

import argparse
import ast
import base64
import builtins
import copy
import csv
import hashlib
import io
import json
import math
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any, Mapping, Sequence, cast


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path("src/experiments/run_closure_benchmark.py")
FORMAL_MODEL_LOCK_GATE = "E0-M"
UNBLINDING_GATE = "E0-U"
GATE = FORMAL_MODEL_LOCK_GATE
PATCH_GATE = FORMAL_MODEL_LOCK_GATE
SEALED_BATCH_MODE = "--execute-sealed-batch"
CHECK_ONLY_MODE = "--check-only"
SEALED_BATCH_PYTHON_ARGV = (
    ".venv/bin/python",
    "-I",
    "-S",
    "-B",
    SCRIPT_PATH.as_posix(),
    SEALED_BATCH_MODE,
)
SEALED_BATCH_ARGV = SEALED_BATCH_PYTHON_ARGV
SEALED_BATCH_PYTHON_COMMAND = " ".join(SEALED_BATCH_PYTHON_ARGV) + "\n"
SEALED_BATCH_LAUNCH_ARGV = (
    "/usr/bin/env",
    "-i",
    "LANG=C",
    "LC_ALL=C",
    *SEALED_BATCH_PYTHON_ARGV,
)
SEALED_BATCH_LAUNCH_COMMAND = " ".join(SEALED_BATCH_LAUNCH_ARGV) + "\n"
SEALED_BATCH_COMMAND_ARGV = SEALED_BATCH_LAUNCH_ARGV
SEALED_BATCH_COMMAND = SEALED_BATCH_LAUNCH_COMMAND
E0_U_AUTHORITY_MODULE = "src.experiments.closure_e0_u_authority"
E0_U_AUTHORITY_API = "require_closure_e0_u_authority"
E0_U_AUTHORITY_PATH = Path("src/experiments/closure_e0_u_authority.py")
E0_U_CONTEXT_FACTORY_API = "open_sealed_batch_context"
E0_U_TRANSACTION_PUBLISHER_API = "publish_sealed_batch_artifacts"
E0_U_PUBLICATION_AUDITOR_API = "validate_published_sealed_batch_artifacts"
E0_U_CONTEXT_BUILDER_MODULE = "src.experiments.closure_phase3_context"
E0_U_CONTEXT_BUILDER_PATH = Path("src/experiments/closure_phase3_context.py")
E0_U_CONTEXT_BUILDER_API = "materialize_sealed_batch_context"
E0_U_CONTEXT_PREFLIGHT_API = "preflight_sealed_phase3_context_inputs"
E0_U_PHASE3_OVERLAY_RECORD_KEY = "_observed_phase3_overlay_record"
E0_U_AUTHORITY_SOURCE_RECORD_KEY = "sealed_authority_source_record"
E0_U_RUNNER_SOURCE_RECORD_KEY = "sealed_runner_source_record"
E0_U_COMPONENT_SOURCE_RECORDS_KEY = "sealed_component_source_records"
E0_U_CONTEXT_BUILDER_SOURCE_RECORD_KEY = "sealed_context_builder_source_record"
E0_U_SUPPORT_SOURCE_RECORDS_KEY = "sealed_support_source_records"
E0_U_RUNTIME_ENVIRONMENT_RECORD_KEY = "sealed_runtime_environment_record"
E0_U_GIT_EXECUTABLE_RECORD_KEY = "sealed_git_executable_record"
E0_U_ENV_EXECUTABLE_RECORD_KEY = "sealed_env_executable_record"
HISTORICAL_E0_M_COMMIT = "4c92ed7249a91b7dd541fd22dde68b61574556b2"
E0_U_COMMIT_BINDING_KEYS = (
    "historical_e0_m_commit",
    "phase3_code_commit",
    "phase3_evidence_commit",
    "phase3_activation_commit",
)
E0_U_AUTHORITY_RESULT_KEYS = frozenset(
    {
        "gate",
        "effective_authority",
        "sealed_batch_execution_authorized",
        "e0_m_authorized",
        "e0_u_authorized",
        "evaluation_authorized",
        "outcome_access_authorized",
        "writes_performed",
        "sealed_batch_command",
        *E0_U_COMMIT_BINDING_KEYS,
        E0_U_AUTHORITY_SOURCE_RECORD_KEY,
        E0_U_RUNNER_SOURCE_RECORD_KEY,
        E0_U_COMPONENT_SOURCE_RECORDS_KEY,
        E0_U_CONTEXT_BUILDER_SOURCE_RECORD_KEY,
        E0_U_SUPPORT_SOURCE_RECORDS_KEY,
        E0_U_RUNTIME_ENVIRONMENT_RECORD_KEY,
        E0_U_GIT_EXECUTABLE_RECORD_KEY,
        E0_U_ENV_EXECUTABLE_RECORD_KEY,
    }
)
E0_U_AUTHORITY_INTERNAL_KEYS = frozenset(
    {
        E0_U_CONTEXT_FACTORY_API,
        E0_U_TRANSACTION_PUBLISHER_API,
        E0_U_PUBLICATION_AUDITOR_API,
        "_observed_authority_source_record",
        "_observed_git_executable_record",
        "_observed_env_executable_record",
        "_observed_context_builder_source_record",
        "_observed_support_source_records",
        E0_U_PHASE3_OVERLAY_RECORD_KEY,
    }
)
GIT_EXECUTABLE = Path("/usr/bin/git")
GIT_EXECUTABLE_SHA256 = "93473c28694fd72bd889364107cd2770514de59780885a6a4aafca4d602e30ad"
GIT_EXECUTABLE_UID = 65534
GIT_EXECUTABLE_GID = 65534
ENV_EXECUTABLE = Path("/usr/bin/env")
ENV_EXECUTABLE_SHA256 = "08392d72874da4f88c619ee717f2b4a5f28ba0534ff8cf1083fb2edc37d6475f"
PYTHON_EXECUTABLE_TARGET = Path("/usr/bin/python3.14")
PYTHON_EXECUTABLE_SHA256 = "d78f9cf7178ecff09963551399855543c297f37ac207e626228bfe43cb26a70c"
GIT_REMOTE_HTTPS_HELPER = Path("/usr/lib/git-core/git-remote-https")
GIT_REMOTE_HTTP_HELPER = Path("/usr/lib/git-core/git-remote-http")
GIT_REMOTE_HTTP_SHA256 = "23f747f69b5293b9f531cc17205eab792eb92075e92f99a8d6bc2b51cf007230"
LIVE_REMOTE_URL = "https://github.com/ejherran/lentic-pipe.git"
GIT_CONFIG_PATH = Path(".git/config")
GIT_CONFIG_SHA256 = "326855ec20dd2ab7c5a7573748b5ed437bedd930f362438b46ff857319b8cd7d"
STARTUP_ENVIRONMENT_DENY_NAMES = frozenset({"LD_PRELOAD", "LD_AUDIT"})
STARTUP_ENVIRONMENT_DENY_PREFIXES = ("PYTHON",)
SEALED_SUPPORT_SOURCES = (
    MappingProxyType(
        {
            "support_id": "mifal_ed_t2",
            "module_name": "src.mifal.ed_t2",
            "source_path": "src/mifal/ed_t2.py",
            "required_symbols": ("MIFALEDT2",),
        }
    ),
    MappingProxyType(
        {
            "support_id": "mifal_closure_panel_adapter",
            "module_name": "src.mifal.closure_panel_adapter",
            "source_path": "src/mifal/closure_panel_adapter.py",
            "required_symbols": (
                "panel_row_to_closure_mifal_payload",
                "payload_is_eligible",
            ),
        }
    ),
    MappingProxyType(
        {
            "support_id": "closure_e10_source_evidence",
            "module_name": "src.experiments.build_closure_e10_source_evidence",
            "source_path": "src/experiments/build_closure_e10_source_evidence.py",
            "required_symbols": (
                "load_closure_e10_software_evidence",
                "validate_closure_e10_environment_payload",
            ),
        }
    ),
)
RUNTIME_DISTRIBUTIONS = (
    "joblib",
    "numpy",
    "pandas",
    "pyarrow",
    "python-dateutil",
    "scikit-learn",
    "scipy",
    "six",
    "threadpoolctl",
    "tzdata",
)
RUNTIME_DISTRIBUTION_ROOTS = MappingProxyType(
    {
        "joblib": ("joblib", "joblib-1.5.3.dist-info"),
        "numpy": ("numpy", "numpy.libs", "numpy-2.4.5.dist-info"),
        "pandas": ("pandas", "pandas-3.0.3.dist-info"),
        "pyarrow": ("pyarrow", "pyarrow-24.0.0.dist-info"),
        "python-dateutil": ("dateutil", "python_dateutil-2.9.0.post0.dist-info"),
        "scikit-learn": ("sklearn", "scikit_learn.libs", "scikit_learn-1.8.0.dist-info"),
        "scipy": ("scipy", "scipy.libs", "scipy-1.17.1.dist-info"),
        "six": ("six.py", "six-1.17.0.dist-info"),
        "threadpoolctl": ("threadpoolctl.py", "threadpoolctl-3.6.0.dist-info"),
        "tzdata": ("tzdata", "tzdata-2026.2.dist-info"),
    }
)
RUNTIME_IMPORT_ROOTS = frozenset(
    {"joblib", "numpy", "pandas", "pyarrow", "dateutil", "sklearn", "scipy", "six", "threadpoolctl", "tzdata"}
)
STDLIB_DYNAMIC_IMPORT_ROOTS = frozenset(
    {"_sysconfigdata__linux_x86_64-linux-gnu"}
)
RUNTIME_STDLIB_IMPORT_ROOTS = frozenset(
    {
        "_compat_pickle",
        "_compression",
        "_csv",
        "_asyncio",
        "_bisect",
        "_bz2",
        "_codecs_cn",
        "_codecs_hk",
        "_codecs_iso2022",
        "_codecs_jp",
        "_codecs_kr",
        "_codecs_tw",
        "_colorize",
        "_ctypes",
        "_datetime",
        "_decimal",
        "_elementtree",
        "_hashlib",
        "_heapq",
        "_hmac",
        "_interpreters",
        "_json",
        "_locale",
        "_lzma",
        "_multibytecodec",
        "_multiprocessing",
        "_opcode",
        "_operator",
        "_pickle",
        "_posixshmem",
        "_pyrepl",
        "_queue",
        "_random",
        "_sha1",
        "_sha2",
        "_socket",
        "_sqlite3",
        "_ssl",
        "_statistics",
        "_string",
        "_strptime",
        "_struct",
        "_typing",
        "_uuid",
        "_weakref",
        "_zoneinfo",
        "_zstd",
        "abc",
        "array",
        "asyncio",
        "atexit",
        "ast",
        "base64",
        "bisect",
        "bz2",
        "calendar",
        "cmath",
        "codeop",
        "codecs",
        "collections",
        "concurrent",
        "compression",
        "contextlib",
        "contextvars",
        "copy",
        "copyreg",
        "csv",
        "ctypes",
        "dataclasses",
        "datetime",
        "decimal",
        "difflib",
        "dis",
        "email",
        "encodings",
        "enum",
        "errno",
        "fnmatch",
        "faulthandler",
        "fileinput",
        "fractions",
        "functools",
        "gc",
        "genericpath",
        "getpass",
        "gettext",
        "glob",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "importlib",
        "inspect",
        "io",
        "ipaddress",
        "itertools",
        "json",
        "keyword",
        "linecache",
        "locale",
        "logging",
        "lzma",
        "marshal",
        "math",
        "mmap",
        "multiprocessing",
        "numbers",
        "opcode",
        "operator",
        "os",
        "pathlib",
        "pickle",
        "pickletools",
        "pkgutil",
        "platform",
        "posix",
        "posixpath",
        "pprint",
        "pydoc",
        "pyexpat",
        "queue",
        "random",
        "re",
        "resource",
        "runpy",
        "secrets",
        "selectors",
        "shlex",
        "shutil",
        "signal",
        "socket",
        "sqlite3",
        "ssl",
        "stat",
        "statistics",
        "string",
        "struct",
        "subprocess",
        "sys",
        "sysconfig",
        "tarfile",
        "tempfile",
        "textwrap",
        "threading",
        "time",
        "timeit",
        "token",
        "tokenize",
        "traceback",
        "types",
        "typing",
        "unicodedata",
        "urllib",
        "uuid",
        "warnings",
        "weakref",
        "xml",
        "unittest",
        "zipfile",
        "zipimport",
        "zlib",
        "zoneinfo",
    }
)
AUTHORITY_STDLIB_IMPORT_ROOTS = frozenset(
    {
        "base64",
        "collections",
        "ctypes",
        "csv",
        "hashlib",
        "io",
        "json",
        "math",
        "os",
        "pathlib",
        "stat",
        "subprocess",
        "sys",
        "typing",
    }
)
SEALED_PYCACHE_PREFIX = Path("/dev/null/closure_e0_u_pycache")
BOOTSTRAP_SYS_PATH = (
    "/usr/lib/python314.zip",
    "/usr/lib/python3.14",
    "/usr/lib/python3.14/lib-dynload",
)
BOOTSTRAP_META_PATH = (
    {"module": "_frozen_importlib", "qualname": "BuiltinImporter"},
    {"module": "_frozen_importlib", "qualname": "FrozenImporter"},
    {"module": "_frozen_importlib_external", "qualname": "PathFinder"},
)
BOOTSTRAP_PATH_HOOKS = (
    {"module": "zipimport", "qualname": "zipimporter"},
    {
        "module": "_frozen_importlib_external",
        "qualname": "FileFinder.path_hook.<locals>.path_hook_for_FileFinder",
    },
)
BOOTSTRAP_MODULE_ROOTS = frozenset(
    {
        "__future__",
        "__main__",
        "_abc",
        "_ast",
        "_blake2",
        "_codecs",
        "_collections",
        "_collections_abc",
        "_contextvars",
        "_csv",
        "_frozen_importlib",
        "_frozen_importlib_external",
        "_functools",
        "_hashlib",
        "_imp",
        "_io",
        "_json",
        "_locale",
        "_opcode",
        "_opcode_metadata",
        "_operator",
        "_posixsubprocess",
        "_py_warnings",
        "_signal",
        "_sre",
        "_stat",
        "_struct",
        "_thread",
        "_tokenize",
        "_types",
        "_typing",
        "_warnings",
        "_weakref",
        "_weakrefset",
        "abc",
        "annotationlib",
        "argparse",
        "ast",
        "base64",
        "binascii",
        "builtins",
        "codecs",
        "collections",
        "contextlib",
        "copy",
        "copyreg",
        "csv",
        "dataclasses",
        "dis",
        "encodings",
        "enum",
        "errno",
        "fcntl",
        "fnmatch",
        "functools",
        "genericpath",
        "gettext",
        "glob",
        "grp",
        "hashlib",
        "importlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "keyword",
        "linecache",
        "locale",
        "marshal",
        "math",
        "ntpath",
        "opcode",
        "operator",
        "os",
        "pathlib",
        "posix",
        "posixpath",
        "pwd",
        "re",
        "reprlib",
        "select",
        "selectors",
        "signal",
        "src",
        "stat",
        "struct",
        "subprocess",
        "sys",
        "threading",
        "time",
        "token",
        "tokenize",
        "types",
        "typing",
        "warnings",
        "weakref",
        "zipimport",
    }
)
RUNTIME_INJECTED_MODULE_NAMES = frozenset(
    {
        "__mp_main__",
        "_csparsetools",
        "_cython_3_2_2",
        "_cython_3_2_4",
        "_cyutility",
        "_loss",
        "_moduleTNC",
        "_ni_label",
        "cython_runtime",
    }
)
INTERNAL_E1_EXECUTOR_API = "_execute_e1_locked_benchmark_stage"
RNG_SEED = 1729
BATCH_CONTEXT_KEYS = frozenset(
    {
        "execution_id",
        "rng_seed",
        "tables",
        "stage_results",
        "model_availability",
        "software_evidence",
    }
)
SOFTWARE_EVIDENCE_KEYS = frozenset(
    {
        "public_tests_xml",
        "test_report",
        "openapi",
        "openapi_contract_report",
        "end_to_end_report",
        "environment",
    }
)
ARTIFACT_FORMATS = frozenset({"csv", "json", "markdown", "parquet", "xml"})

OUTCOME_ACCESS_LOG_PATH = Path(
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl"
)
LOCKED_INPUT_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/locked_evaluation_input_manifest.json"
)
FINAL_CALIBRATION_MANIFEST_PATH = Path(
    "reports/closure_v1/03_calibration/final_calibration_manifest.json"
)
MODEL_LOCK_PATH = Path("reports/closure_v1/00_protocol/model_lock.yaml")
CALIBRATION_LOCK_PATH = Path("reports/closure_v1/00_protocol/calibration_lock.yaml")
HYPOTHESIS_REGISTRY_PATH = Path(
    "reports/closure_v1/00_protocol/hypothesis_registry.csv"
)
LOCKED_BATCH_COMMAND_PATH = Path(
    "reports/closure_v1/00_protocol/locked_batch_command.txt"
)
PHASE3_OVERLAY_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/phase3_input_overlay_manifest.json"
)
PHASE3_OVERLAY_OUTPUT_PATHS = (
    Path("data/closure_v1/locked_evaluation/phase3_runtime_weights.npz"),
    Path("data/closure_v1/locked_evaluation/adaptive_state_warmup.parquet"),
)

MODEL_IDS = ("B0", "B1", "B2", "F0", "F1", "P0", "P1", "M0", "A0", "A1", "A2")
HORIZONS_MONTHS = (1, 2, 3)
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
EVALUATION_SOURCE_ID = "wqp"
EVALUATION_COHORT = "location_holdout"
EVALUATION_ROLE = "test"
EVALUATION_TIME_ROLE = "post_2021_evaluation"
LOCKED_HOLDOUT_SITE_COUNT = 88
LOCKED_BASE_ORIGIN_COUNT = 4488
LOCKED_INTENT_COUNT = LOCKED_BASE_ORIGIN_COUNT * len(HORIZONS_MONTHS)
TERMINAL_STATUSES = (
    "success",
    "input_ineligible",
    "target_unavailable",
    "model_unavailable",
    "numerical_failure",
    "infrastructure_failure",
)
ENDPOINTS = ("bloom", "continuous", "uncertainty", "ordinal")
ENDPOINT_STATUSES = (*TERMINAL_STATUSES, "not_applicable")
ENDPOINT_STATUS_COLUMNS = tuple(f"{endpoint}_status" for endpoint in ENDPOINTS)
UNAVAILABLE_MODEL_IDS = ("P0", "P1", "A2")
MODEL_ENDPOINT_AVAILABILITY = MappingProxyType(
    {
        "B0": {"bloom": "available", "continuous": "not_applicable", "uncertainty": "not_applicable", "ordinal": "not_applicable"},
        "B1": {"bloom": "available", "continuous": "available", "uncertainty": "not_applicable", "ordinal": "available"},
        "B2": {"bloom": "available", "continuous": "not_applicable", "uncertainty": "not_applicable", "ordinal": "available"},
        "F0": {"bloom": "not_applicable", "continuous": "available", "uncertainty": "not_applicable", "ordinal": "not_applicable"},
        "F1": {"bloom": "not_applicable", "continuous": "available", "uncertainty": "not_applicable", "ordinal": "not_applicable"},
        "P0": {endpoint: "model_unavailable" for endpoint in ENDPOINTS},
        "P1": {endpoint: "model_unavailable" for endpoint in ENDPOINTS},
        "M0": {"bloom": "available", "continuous": "available", "uncertainty": "not_applicable", "ordinal": "not_applicable"},
        "A0": {"bloom": "available", "continuous": "available", "uncertainty": "available", "ordinal": "not_applicable"},
        "A1": {"bloom": "available", "continuous": "available", "uncertainty": "available", "ordinal": "not_applicable"},
        "A2": {endpoint: "model_unavailable" for endpoint in ENDPOINTS},
    }
)
DETERMINISTIC_MODEL_IDS = ("B0", "F0", "M0")
ZERO_SLOT_MODEL_IDS = ("A2",)
E1_MODEL_SLOT_COUNT = (len(MODEL_IDS) - len(ZERO_SLOT_MODEL_IDS)) * len(
    REGISTERED_SEEDS
)
LOCKED_PREDICTION_ROW_COUNT = LOCKED_INTENT_COUNT * E1_MODEL_SLOT_COUNT
E1_MODEL_PAIRS = (
    ("P1", "B1", "pipeline_vs_persistence"),
    ("P1", "B2", "pipeline_vs_strong_raw_baseline"),
    ("P1", "P0", "adaptive_vs_expert_pipe"),
    ("P1", "M0", "pipe_vs_mifal"),
    ("F1", "F0", "adaptive_vs_expert_static"),
    ("A2", "P1", "current_chla_information_advantage"),
)
E1_INPUT_TABLES = ("predictions_long", "intent_origins", "target_outcomes")
E1_OUTPUT_TABLES = (
    "predictions_long",
    "paired_metric_rows",
    "trophic_predictions",
    "e1_model_metrics",
    "e1_model_comparisons",
)
E1_REQUIRED_NONEMPTY_TABLES = E1_OUTPUT_TABLES
PUBLICATION_RECEIPT_KEYS = frozenset(
    {
        "status",
        "execution_id",
        "batch_contract_sha256",
        "artifact_count",
        "published_artifact_paths_sha256",
        "stage_count",
        "one_shot_consumed",
        "guard_released",
        "rollback_performed",
        "manifest_written_last",
        "writes_performed",
    }
)
PUBLICATION_AUDIT_RECORD_KEYS = frozenset(
    {
        "path",
        "bytes",
        "sha256",
        "device",
        "inode",
        "mode",
        "nlink",
        "mtime_ns",
        "ctime_ns",
    }
)
PUBLICATION_AUDIT_KEYS = frozenset(
    {
        "status",
        "execution_id",
        "batch_contract_sha256",
        "artifact_count",
        "published_artifact_paths_sha256",
        "artifact_payloads_sha256",
        "physical_records",
        "physical_records_sha256",
        "publication_order",
        "publication_order_sha256",
        "stage_count",
        "one_shot_consumed",
        "guard_released",
        "publication_guard_present",
        "rollback_performed",
        "manifest_written_last",
        "writes_performed",
    }
)
E1_PREDICTION_COLUMNS = (
    "source_id",
    "site_id",
    "common_origin_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "model_id",
    "model_seed",
    "seed_slot",
    "terminal_status",
    *ENDPOINT_STATUS_COLUMNS,
    "bloom_probability",
    "alert_threshold",
    "predicted_value",
    "predicted_sigma",
    "predicted_lower",
    "predicted_upper",
    "continuous_score",
    "ordinal_score",
    "cutpoint_1",
    "cutpoint_2",
    "cutpoint_3",
)
E1_INTENT_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "common_origin_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "evaluation_cohort",
    "evaluation_role",
    "time_role",
)
E1_TARGET_COLUMNS = (
    "source_id",
    "site_id",
    "common_origin_id",
    "target_year_month",
    "horizon_months",
    "actual_bloom",
    "actual_value",
    "actual_chla_ug_l",
    "actual_trophic_state",
    "target_status",
)
PAIRED_METRIC_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "common_origin_id",
    "horizon_months",
    "model_id",
    "model_seed",
    "seed_slot",
    "evaluation_cohort",
    "metric",
    "loss",
    "terminal_status",
)


class ClosureBenchmarkError(RuntimeError):
    """Fail-closed error for the sealed Closure V1 batch."""


@dataclass(frozen=True)
class BatchStage:
    stage_id: str
    role: str
    requires_outcomes: bool
    output_root: str
    output_paths: tuple[str, ...]


@dataclass(frozen=True)
class BatchComponent:
    component_id: str
    stage_id: str
    module_name: str
    source_path: str
    preflight_api: str
    execute_api: str
    output_tables: tuple[str, ...]
    required_nonempty_tables: tuple[str, ...]
    completed_nonempty_tables: tuple[str, ...] = ()
    unavailable_nonempty_tables: tuple[str, ...] = ()
    unavailable_empty_tables: tuple[str, ...] = ()
    artifact_paths: tuple[str, ...] = ()
    artifact_formats: tuple[str, ...] = ()
    manifest_last_path: str | None = None


BATCH_STAGES = (
    BatchStage(
        "E0-U",
        "authorize_and_log_single_opening",
        False,
        "reports/closure_v1/00_protocol",
        (OUTCOME_ACCESS_LOG_PATH.as_posix(),),
    ),
    BatchStage(
        "E1",
        "paired_final_benchmark",
        True,
        "reports/closure_v1/01_benchmark",
        (
            "reports/closure_v1/01_benchmark/model_metrics_long.csv",
            "reports/closure_v1/01_benchmark/model_comparison_paired.csv",
            "reports/closure_v1/01_benchmark/benchmark_report.md",
            "reports/closure_v1/01_benchmark/benchmark_manifest.json",
            "data/closure_v1/predictions_long.parquet",
        ),
    ),
    BatchStage(
        "E2",
        "locked_internal_location_holdout",
        True,
        "reports/closure_v1/02_site_transfer",
        (
            "reports/closure_v1/02_site_transfer/location_holdout_metrics.csv",
            "reports/closure_v1/02_site_transfer/site_level_metrics.csv",
            "reports/closure_v1/02_site_transfer/fold_assignments.csv",
            "reports/closure_v1/02_site_transfer/generalization_gap.csv",
            "reports/closure_v1/02_site_transfer/site_transfer_report.md",
        ),
    ),
    BatchStage(
        "E3",
        "bloom_threshold_sensitivity",
        True,
        "reports/closure_v1/03_thresholds",
        (
            "reports/closure_v1/03_thresholds/threshold_prevalence.csv",
            "reports/closure_v1/03_thresholds/threshold_metrics.csv",
            "reports/closure_v1/03_thresholds/threshold_pairwise_differences.csv",
            "reports/closure_v1/03_thresholds/rank_stability.csv",
            "reports/closure_v1/03_thresholds/threshold_sensitivity_report.md",
        ),
    ),
    BatchStage(
        "E4",
        "direct_trophic_state_validation",
        True,
        "reports/closure_v1/04_trophic",
        (
            "reports/closure_v1/04_trophic/trophic_proxy_metrics.csv",
            "reports/closure_v1/04_trophic/carlson_reference_metrics.csv",
            "reports/closure_v1/04_trophic/trophic_confusion_matrices.csv",
            "reports/closure_v1/04_trophic/nla_semantic_metrics.csv",
            "reports/closure_v1/04_trophic/trophic_validation_report.md",
        ),
    ),
    BatchStage(
        "E5",
        "paired_hierarchical_inference",
        True,
        "reports/closure_v1/05_inference",
        (
            "reports/closure_v1/05_inference/pairwise_effects.csv",
            "reports/closure_v1/05_inference/site_level_losses.csv",
            "reports/closure_v1/05_inference/bootstrap_distributions.parquet",
            "reports/closure_v1/05_inference/multiplicity_report.csv",
            "reports/closure_v1/05_inference/statistical_inference_report.md",
        ),
    ),
    BatchStage(
        "E6",
        "matched_pipe_mifal_degradation",
        True,
        "reports/closure_v1/06_degradation",
        (
            "data/closure_v1/degradation_masks.parquet",
            "reports/closure_v1/06_degradation/matched_degradation_metrics.csv",
            "reports/closure_v1/06_degradation/matched_degradation_pairwise.csv",
            "reports/closure_v1/06_degradation/failure_registry.csv",
            "reports/closure_v1/06_degradation/robustness_auc.csv",
            "reports/closure_v1/06_degradation/matched_degradation_report.md",
        ),
    ),
    BatchStage(
        "E7",
        "locked_anfis_ablation_evaluation",
        True,
        "reports/closure_v1/07_anfis_ablation_evaluation",
        (
            "reports/closure_v1/07_anfis_ablation_evaluation/ablation_metrics.csv",
            "reports/closure_v1/07_anfis_ablation_evaluation/ablation_pairwise.csv",
            "reports/closure_v1/07_anfis_ablation_evaluation/membership_stability.csv",
            "reports/closure_v1/07_anfis_ablation_evaluation/anfis_learning_curve.csv",
            "reports/closure_v1/07_anfis_ablation_evaluation/anfis_ablation_report.md",
        ),
    ),
    BatchStage(
        "E8",
        "uncertainty_recalibration_ledger",
        True,
        "reports/closure_v1/08_uncertainty",
        (
            "reports/closure_v1/08_uncertainty/uncertainty_ledger.csv",
            "reports/closure_v1/08_uncertainty/conditional_coverage.csv",
            "reports/closure_v1/08_uncertainty/recalibration_comparison.csv",
            "reports/closure_v1/08_uncertainty/reliability_bins.csv",
            "reports/closure_v1/08_uncertainty/uncertainty_report.md",
        ),
    ),
    BatchStage(
        "E9",
        "counterfactual_planning_robustness",
        True,
        "reports/closure_v1/09_planning",
        (
            "reports/closure_v1/09_planning/planning_origin_deltas.parquet",
            "reports/closure_v1/09_planning/planning_bootstrap.csv",
            "reports/closure_v1/09_planning/planning_sensitivity.csv",
            "reports/closure_v1/09_planning/ecological_coherence.csv",
            "reports/closure_v1/09_planning/planning_inference_report.md",
        ),
    ),
    BatchStage(
        "E10",
        "reproducible_api_and_evidence_freeze",
        True,
        "reports/closure_v1/10_api",
        (
            "reports/closure_v1/10_api/public_tests.xml",
            "reports/closure_v1/10_api/test_report.md",
            "reports/closure_v1/10_api/openapi.json",
            "reports/closure_v1/10_api/openapi_contract_report.md",
            "reports/closure_v1/10_api/end_to_end_report.md",
            "reports/closure_v1/10_api/environment.json",
        ),
    ),
)

COMPONENT_PREFLIGHT_API = "preflight_closure_sealed_batch_component"
COMPONENT_EXECUTE_API = "execute_closure_sealed_batch_component"
BATCH_COMPONENTS = (
    BatchComponent(
        "E2_site_transfer",
        "E2",
        "src.experiments.evaluate_site_transfer",
        "src/experiments/evaluate_site_transfer.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
        (
            "e2_location_metrics",
            "e2_site_metrics",
            "e2_fold_assignments",
            "e2_generalization_gaps",
        ),
        ("e2_location_metrics", "e2_site_metrics", "e2_fold_assignments"),
        artifact_paths=BATCH_STAGES[2].output_paths,
        artifact_formats=("csv", "csv", "csv", "csv", "markdown"),
        manifest_last_path=BATCH_STAGES[2].output_paths[-1],
    ),
    BatchComponent(
        "E3_threshold_sensitivity",
        "E3",
        "src.experiments.evaluate_threshold_sensitivity",
        "src/experiments/evaluate_threshold_sensitivity.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
        (
            "e3_threshold_prevalence",
            "e3_threshold_metrics",
            "e3_threshold_pairwise",
            "e3_rank_stability",
        ),
        ("e3_threshold_prevalence", "e3_threshold_metrics", "e3_threshold_pairwise"),
        artifact_paths=BATCH_STAGES[3].output_paths,
        artifact_formats=("csv", "csv", "csv", "csv", "markdown"),
        manifest_last_path=BATCH_STAGES[3].output_paths[-1],
    ),
    BatchComponent(
        "E4_reference_targets",
        "E4",
        "src.experiments.build_trophic_reference_targets",
        "src/experiments/build_trophic_reference_targets.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
        ("trophic_reference_targets",),
        ("trophic_reference_targets",),
        artifact_paths=(),
        artifact_formats=(),
        manifest_last_path=None,
    ),
    BatchComponent(
        "E4_trophic_evaluation",
        "E4",
        "src.experiments.evaluate_trophic_state",
        "src/experiments/evaluate_trophic_state.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
        (
            "trophic_proxy_metrics",
            "carlson_reference_metrics",
            "trophic_confusion_matrices",
            "nla_semantic_metrics",
        ),
        (
            "trophic_proxy_metrics",
            "carlson_reference_metrics",
            "trophic_confusion_matrices",
        ),
        artifact_paths=BATCH_STAGES[4].output_paths,
        artifact_formats=("csv", "csv", "csv", "csv", "markdown"),
        manifest_last_path=BATCH_STAGES[4].output_paths[-1],
    ),
    BatchComponent(
        "E5_clustered_inference",
        "E5",
        "src.experiments.compare_models_clustered",
        "src/experiments/compare_models_clustered.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
        (
            "pairwise_effects",
            "site_level_losses",
            "bootstrap_distributions",
            "multiplicity_report",
        ),
        ("pairwise_effects", "multiplicity_report"),
        ("site_level_losses", "bootstrap_distributions"),
        (),
        ("site_level_losses", "bootstrap_distributions"),
        artifact_paths=BATCH_STAGES[5].output_paths,
        artifact_formats=("csv", "csv", "parquet", "csv", "markdown"),
        manifest_last_path=BATCH_STAGES[5].output_paths[-1],
    ),
    BatchComponent(
        "E6_matched_degradation",
        "E6",
        "src.experiments.evaluate_matched_degradation",
        "src/experiments/evaluate_matched_degradation.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
        (
            "degradation_masks",
            "matched_degradation_metrics",
            "matched_degradation_pairwise",
            "failure_registry",
            "robustness_auc",
        ),
        (),
        (
            "degradation_masks",
            "matched_degradation_metrics",
            "matched_degradation_pairwise",
            "robustness_auc",
        ),
        ("failure_registry",),
        (
            "degradation_masks",
            "matched_degradation_metrics",
            "matched_degradation_pairwise",
            "robustness_auc",
        ),
        artifact_paths=BATCH_STAGES[6].output_paths,
        artifact_formats=("parquet", "csv", "csv", "csv", "csv", "markdown"),
        manifest_last_path=BATCH_STAGES[6].output_paths[-1],
    ),
    BatchComponent(
        "E7_anfis_ablation",
        "E7",
        "src.experiments.evaluate_anfis_ablation",
        "src/experiments/evaluate_anfis_ablation.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
        (
            "e7_ablation_metrics",
            "e7_ablation_pairwise",
            "e7_membership_stability",
            "e7_learning_curve_summary",
        ),
        ("e7_ablation_metrics", "e7_ablation_pairwise"),
        artifact_paths=BATCH_STAGES[7].output_paths,
        artifact_formats=("csv", "csv", "csv", "csv", "markdown"),
        manifest_last_path=BATCH_STAGES[7].output_paths[-1],
    ),
    BatchComponent(
        "E8_uncertainty",
        "E8",
        "src.experiments.calibrate_uncertainty_closure",
        "src/experiments/calibrate_uncertainty_closure.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
        (
            "e8_conformal_factors",
            "e8_uncertainty_ledger",
            "e8_conditional_coverage",
            "e8_recalibration_comparison",
            "e8_reliability_bins",
        ),
        (),
        ("e8_conformal_factors", "e8_uncertainty_ledger"),
        unavailable_nonempty_tables=(
            "e8_conformal_factors",
            "e8_uncertainty_ledger",
            "e8_recalibration_comparison",
        ),
        artifact_paths=BATCH_STAGES[8].output_paths,
        artifact_formats=("csv", "csv", "csv", "csv", "markdown"),
        manifest_last_path=BATCH_STAGES[8].output_paths[-1],
    ),
    BatchComponent(
        "E9_planning_inference",
        "E9",
        "src.experiments.evaluate_planning_inference",
        "src/experiments/evaluate_planning_inference.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
        (
            "e9_planning_origin_deltas",
            "e9_planning_bootstrap_replicates",
            "e9_planning_inference",
            "e9_planning_failures",
            "e9_planning_sensitivity",
            "e9_ecological_coherence",
        ),
        ("e9_planning_inference", "e9_planning_sensitivity", "e9_ecological_coherence"),
        ("e9_planning_origin_deltas", "e9_planning_bootstrap_replicates"),
        ("e9_planning_failures",),
        (
            "e9_planning_origin_deltas",
            "e9_planning_bootstrap_replicates",
        ),
        artifact_paths=BATCH_STAGES[9].output_paths,
        artifact_formats=("parquet", "csv", "csv", "csv", "markdown"),
        manifest_last_path=BATCH_STAGES[9].output_paths[-1],
    ),
    BatchComponent(
        "E10_evidence_matrix",
        "E10",
        "src.reporting.build_closure_evidence_matrix",
        "src/reporting/build_closure_evidence_matrix.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
        ("e10_stage_evidence",),
        ("e10_stage_evidence",),
        artifact_paths=BATCH_STAGES[10].output_paths,
        artifact_formats=("xml", "markdown", "json", "markdown", "markdown", "json"),
        manifest_last_path=BATCH_STAGES[10].output_paths[-1],
    ),
)

CURRENT_MODEL_AVAILABILITY = MappingProxyType(
    {
        "B0": "available",
        "B1": "available",
        "B2": "available",
        "F0": "available",
        "F1": "available",
        "P0": "unavailable",
        "P1": "unavailable",
        "M0": "available",
        "A0": "available",
        "A1": "available",
        "A2": "unavailable",
    }
)

COMPONENT_TABLE_VIEWS = MappingProxyType(
    {
        "E1_benchmark_scientific_executor": E1_INPUT_TABLES,
        "E2_site_transfer": ("predictions_long", "e2_site_strata"),
        "E3_threshold_sensitivity": ("predictions_long",),
        "E4_reference_targets": ("future_trophic_indicators",),
        "E4_trophic_evaluation": (
            "trophic_predictions",
            "trophic_reference_targets",
            "nla_trophic_semantic",
        ),
        "E5_clustered_inference": ("paired_metric_rows", "hypothesis_registry"),
        "E6_matched_degradation": ("intent_origins",),
        "E7_anfis_ablation": (
            "e7_predictions",
            "e7_memberships",
            "e7_learning_curve",
        ),
        "E8_uncertainty": (
            "locked_conformal_factors",
            "uncertainty_evaluation",
        ),
        "E9_planning_inference": ("intent_origins",),
        "E10_evidence_matrix": (),
        "E0-U_publication": (),
    }
)
OPENED_CONTEXT_TABLES = frozenset(
    {
        "predictions_long",
        "intent_origins",
        "target_outcomes",
        "e2_site_strata",
        "future_trophic_indicators",
        "hypothesis_registry",
        "e7_predictions",
        "locked_conformal_factors",
        "uncertainty_evaluation",
    }
)


def _canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, MappingProxyType):
        value = dict(value)
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


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


EXPECTED_ARTIFACT_PATHS = tuple(
    sorted(
        path
        for stage in BATCH_STAGES
        if stage.stage_id != "E0-U"
        for path in stage.output_paths
    )
)
if len(EXPECTED_ARTIFACT_PATHS) != 52 or len(set(EXPECTED_ARTIFACT_PATHS)) != 52:
    raise RuntimeError("E0-M expected artifact path contract is not exact52")
EXPECTED_ARTIFACT_PATHS_SHA256 = _sha256_bytes(
    _canonical_json_bytes(list(EXPECTED_ARTIFACT_PATHS))
)
E1_ARTIFACT_PATHS = BATCH_STAGES[1].output_paths
E1_ARTIFACT_FORMATS = ("csv", "csv", "markdown", "json", "parquet")
E1_MANIFEST_LAST_PATH = E1_ARTIFACT_PATHS[3]
COMPONENT_ARTIFACT_CONTRACTS = MappingProxyType(
    {
        "E1_benchmark_scientific_executor": {
            "component_id": "E1_benchmark_scientific_executor",
            "stage_id": "E1",
            "artifact_paths": E1_ARTIFACT_PATHS,
            "artifact_formats": E1_ARTIFACT_FORMATS,
            "manifest_last_path": E1_MANIFEST_LAST_PATH,
        },
        **{
            component.component_id: {
                "component_id": component.component_id,
                "stage_id": component.stage_id,
                "artifact_paths": component.artifact_paths,
                "artifact_formats": component.artifact_formats,
                "manifest_last_path": component.manifest_last_path,
            }
            for component in BATCH_COMPONENTS
        },
    }
)
_artifact_formats_by_path: dict[str, str] = {}
_manifest_last_by_stage: dict[str, str] = {}
for _artifact_contract in COMPONENT_ARTIFACT_CONTRACTS.values():
    _paths = cast(tuple[str, ...], _artifact_contract["artifact_paths"])
    _formats = cast(tuple[str, ...], _artifact_contract["artifact_formats"])
    _terminal = cast(str | None, _artifact_contract["manifest_last_path"])
    if len(_paths) != len(_formats) or len(_paths) != len(set(_paths)):
        raise RuntimeError("E0-M component artifact path/format contract drifted")
    if (_terminal is None) != (not _paths) or (
        _terminal is not None and _terminal not in _paths
    ):
        raise RuntimeError("E0-M component artifact sentinel contract drifted")
    for _path, _format in zip(_paths, _formats, strict=True):
        if _format not in ARTIFACT_FORMATS or _path in _artifact_formats_by_path:
            raise RuntimeError("E0-M component artifact ownership is not exact")
        _artifact_formats_by_path[_path] = _format
    if _terminal is not None:
        _stage_id = cast(str, _artifact_contract["stage_id"])
        if _stage_id in _manifest_last_by_stage:
            raise RuntimeError("E0-M stage has multiple manifest-last owners")
        _manifest_last_by_stage[_stage_id] = _terminal
if (
    tuple(sorted(_artifact_formats_by_path)) != EXPECTED_ARTIFACT_PATHS
    or set(_manifest_last_by_stage) != {f"E{index}" for index in range(1, 11)}
):
    raise RuntimeError("E0-M component artifact ownership does not cover exact52")
EXPECTED_ARTIFACT_FORMATS = MappingProxyType(dict(_artifact_formats_by_path))
EXPECTED_MANIFEST_LAST_PATHS = MappingProxyType(dict(_manifest_last_by_stage))
EXPECTED_PUBLICATION_ORDER = tuple(
    path
    for stage in BATCH_STAGES
    if stage.stage_id != "E0-U"
    for path in (
        *(
            candidate
            for candidate in stage.output_paths
            if candidate != EXPECTED_MANIFEST_LAST_PATHS[stage.stage_id]
        ),
        EXPECTED_MANIFEST_LAST_PATHS[stage.stage_id],
    )
)
if len(EXPECTED_PUBLICATION_ORDER) != 52 or set(EXPECTED_PUBLICATION_ORDER) != set(
    EXPECTED_ARTIFACT_PATHS
):
    raise RuntimeError("E0-M publication order is not exact52")
EXPECTED_PUBLICATION_ORDER_SHA256 = _sha256_bytes(
    _canonical_json_bytes(list(EXPECTED_PUBLICATION_ORDER))
)
STAGE_OUTPUT_TABLES = MappingProxyType(
    {
        "E1": E1_OUTPUT_TABLES,
        **{
            stage_id: tuple(
                table_name
                for component in BATCH_COMPONENTS
                if component.stage_id == stage_id
                for table_name in component.output_tables
            )
            for stage_id in (f"E{index}" for index in range(2, 11))
        },
    }
)
if set(STAGE_OUTPUT_TABLES) != {f"E{index}" for index in range(1, 11)} or any(
    not names or len(names) != len(set(names)) for names in STAGE_OUTPUT_TABLES.values()
):
    raise RuntimeError("E0-M stage output table contract is not exact E1-E10")


COMPONENT_CONTRACT_SHA256 = MappingProxyType(
    {
        "E4_reference_targets": "79d5890c8c541e55e32d750998a11d126e19b80ff85663369649de2dde20c2ce",
        "E4_trophic_evaluation": "fef2c9ab0154f62617945997edf1e685325ebcfddb9df754302ee700e041b83e",
        "E5_clustered_inference": "6540042e3f1d1bf7e27a1818c7b950e8316dce3770d46ef4fb2e554a9c8ae1c1",
        "E6_matched_degradation": "c00bbfc96d9b8865f9daa9a856e422216e4aa076a552b1f3d1b1adc7d1861403",
        "E7_anfis_ablation": "a94e84b3308aaf92b5b771aa0d646179419310ffc469187ea958ccd3cea5927a",
        "E8_uncertainty": "2ec8c92af8baac9be85184fbe80c1cc15ce98bb64d8c71c97a5db247a19680c9",
        "E9_planning_inference": "51f7730fe87ee168e5687ebc1da10ebc141db6f32544fac48f781407f3b7592b",
        "E10_evidence_matrix": "a5ca6af7e949d42d97c9afadff00e5dc9ce991e3b951410288df4d3f01f0c4b4",
    }
)
COMPONENT_DIAGNOSTICS_CONTRACTS = MappingProxyType(
    {
        "E1_benchmark_scientific_executor": {
            "statuses": ["completed_unavailable"],
            "schemas": {
                "completed_unavailable": {
                    "execution_id": "nonempty_string",
                    "model_count": "exact_int_11",
                    "seed_slot_count": "exact_int_5",
                    "unavailable_model_ids": "exact_list_P0_P1_A2",
                    "evaluation_refit_performed": "false",
                    "outcome_paths_opened": "true",
                    "writes_performed": "false",
                }
            },
        },
        "E2_site_transfer": {
            "statuses": ["completed", "completed_unavailable"],
            "schemas": {
                "completed": "exact_e2_keys_and_e2b_predictions_available_true",
                "completed_unavailable": "exact_e2_keys_and_e2b_predictions_available_false",
            },
        },
        "E3_threshold_sensitivity": {
            "statuses": ["completed", "completed_unavailable"],
            "schemas": {
                "completed": "exact_e3_threshold_diagnostics",
                "completed_unavailable": "exact_e3_threshold_diagnostics",
            },
        },
        "E4_reference_targets": {
            "statuses": ["completed"],
            "schemas": {"completed": "exact_nonnegative_reference_counts"},
        },
        "E4_trophic_evaluation": {
            "statuses": ["completed"],
            "schemas": {"completed": "exact_bound_unavailable_model_ids"},
        },
        "E5_clustered_inference": {
            "statuses": ["completed", "completed_unavailable"],
            "schemas": {
                "completed": "exact_cluster_bootstrap_diagnostics",
                "completed_unavailable": "exact_cluster_bootstrap_diagnostics",
            },
        },
        "E6_matched_degradation": {
            "statuses": ["completed", "completed_unavailable"],
            "schemas": {
                "completed": "exact_thirteen_scenario_diagnostics",
                "completed_unavailable": "exact_unavailable_reason_diagnostics",
            },
        },
        "E7_anfis_ablation": {
            "statuses": ["completed", "completed_unavailable"],
            "schemas": {
                "completed": "exact_e7_contract_counts_and_availability",
                "completed_unavailable": "exact_e7_contract_counts_and_availability",
            },
        },
        "E8_uncertainty": {
            "statuses": ["completed", "completed_unavailable"],
            "schemas": {
                "completed": "exact_e8_contract_counts_and_no_q_refit",
                "completed_unavailable": "exact_e8_contract_counts_and_no_q_refit",
            },
        },
        "E9_planning_inference": {
            "statuses": ["completed", "completed_unavailable"],
            "schemas": {
                "completed": "exact_e9_available_branch",
                "completed_unavailable": [
                    "exact_e9_available_zero_shared_branch",
                    "exact_e9_p1_unavailable_branch",
                ],
            },
        },
        "E10_evidence_matrix": {
            "statuses": ["completed"],
            "schemas": {"completed": "exact_e10_evidence_counts_no_operations"},
        },
    }
)
STARTUP_CONTRACT = MappingProxyType(
    {
        "schema_version": "closure_sealed_batch_startup_v1",
        "external_launch_argv": list(SEALED_BATCH_LAUNCH_ARGV),
        "external_launch_command": SEALED_BATCH_LAUNCH_COMMAND,
        "python_argv": list(SEALED_BATCH_PYTHON_ARGV),
        "python_command": SEALED_BATCH_PYTHON_COMMAND,
        "startup_environment": {"LANG": "C", "LC_ALL": "C"},
        "startup_flags": {
            "isolated": True,
            "no_site": True,
            "dont_write_bytecode": True,
        },
        "bootstrap_sys_path": list(BOOTSTRAP_SYS_PATH),
        "authenticated_bootstrap": {
            "outcome_free": True,
            "authority_source_binding": "physical_equals_index_equals_content_addressed_head_blob",
            "live_remote_url": LIVE_REMOTE_URL,
            "live_remote_main_equals_head": True,
            "git_and_https_helper_physically_sealed": True,
            "live_remote_transport_tcb": [
                "git_remote_http",
                "system_libcurl_tls_dns_and_ca_stack",
            ],
            "authority_source_top_level": "future_annotations_literals_functions_no_classes",
            "authority_stdlib_import_roots": sorted(AUTHORITY_STDLIB_IMPORT_ROOTS),
        },
        "authority_require": {
            "first_capability_operation": True,
            "source_record_key": E0_U_AUTHORITY_SOURCE_RECORD_KEY,
            "runtime_environment_record_key": E0_U_RUNTIME_ENVIRONMENT_RECORD_KEY,
            "result_exact_keys": True,
            "public_result_keys": sorted(E0_U_AUTHORITY_RESULT_KEYS),
            "commit_binding_keys": list(E0_U_COMMIT_BINDING_KEYS),
            "commit_parent_chain": "R_HEAD~3__H_HEAD~2__P_HEAD~1__U_HEAD",
            "private_apis_removed_from_component_payload": True,
        },
        "runtime_activation": {
            "manual_purelib_after_authority": True,
            "site_and_pth_forbidden": True,
            "pycache_prefix": SEALED_PYCACHE_PREFIX.as_posix(),
            "runtime_distributions": list(RUNTIME_DISTRIBUTIONS),
            "runtime_import_roots": sorted(RUNTIME_IMPORT_ROOTS),
            "stdlib_import_roots_closed": True,
            "import_origins_physically_sealed": True,
            "preactivated_runtime_modules_forbidden": True,
            "process_environment_recaptured": True,
            "importer_cache_object_identity_sealed": True,
            "runtime_recaptured_after_callbacks_before_publication_and_at_terminal": True,
        },
        "component_diagnostics": {
            "component_count": 11,
            "exact_keysets": True,
            "branch_aware": True,
            "canonical_json_scalars_lists_maps_only": True,
        },
        "publication": {
            "artifact_count": 52,
            "stage_count": 10,
            "transactional_publisher_required": True,
            "physical_post_publication_auditor_required": True,
        },
        "external_pre_python_tcb": [
            "/usr/bin/env",
            "kernel_and_elf_loader",
            "/usr/bin/python3.14_and_linked_system_libraries",
            "python_frozen_and_stdlib_bootstrap",
        ],
    }
)


BATCH_CONTRACT = MappingProxyType(
    {
        "schema_version": "closure_sealed_evaluation_batch_v1",
        "experiment_id": "closure_v1",
        "formal_model_lock_gate": FORMAL_MODEL_LOCK_GATE,
        "execution_gate": UNBLINDING_GATE,
        "sealed_argv": list(SEALED_BATCH_ARGV),
        "sealed_command": SEALED_BATCH_COMMAND,
        "startup_contract": dict(STARTUP_CONTRACT),
        "authenticated_bootstrap_precedes_authority": True,
        "authority_is_first_execute_operation": True,
        "authority_first_execute_operation_semantics": (
            "first_capability_or_outcome_operation_after_authenticated_outcome_free_bootstrap"
        ),
        "authority_is_first_capability_operation": True,
        "evaluation_refit": "forbidden",
        "failed_model_replacement": "forbidden",
        "silent_row_deletion": "forbidden",
        "manifest_last": True,
        "one_batch_only": True,
        "registered_seeds": list(REGISTERED_SEEDS),
        "horizons_months": list(HORIZONS_MONTHS),
        "model_ids": list(MODEL_IDS),
        "model_availability": dict(CURRENT_MODEL_AVAILABILITY),
        "terminal_statuses": list(TERMINAL_STATUSES),
        "stages": [
            {
                "stage_id": stage.stage_id,
                "role": stage.role,
                "requires_outcomes": stage.requires_outcomes,
                "output_root": stage.output_root,
                "output_paths": list(stage.output_paths),
            }
            for stage in BATCH_STAGES
        ],
        "components": [
            {
                "component_id": component.component_id,
                "stage_id": component.stage_id,
                "module_name": component.module_name,
                "source_path": component.source_path,
                "preflight_api": component.preflight_api,
                "execute_api": component.execute_api,
            }
            for component in BATCH_COMPONENTS
        ],
        "component_output_contracts": [
            {
                "component_id": component.component_id,
                "stage_id": component.stage_id,
                "output_tables": list(component.output_tables),
                "required_nonempty_tables": list(
                    component.required_nonempty_tables
                ),
                "completed_nonempty_tables": list(
                    component.completed_nonempty_tables
                ),
                "unavailable_nonempty_tables": list(
                    component.unavailable_nonempty_tables
                ),
                "unavailable_empty_tables": list(
                    component.unavailable_empty_tables
                ),
            }
            for component in BATCH_COMPONENTS
        ],
        "component_diagnostics_contracts": dict(COMPONENT_DIAGNOSTICS_CONTRACTS),
        "component_contract_sha256": dict(COMPONENT_CONTRACT_SHA256),
        "component_artifact_contracts": [
            {
                "component_id": cast(str, contract["component_id"]),
                "stage_id": cast(str, contract["stage_id"]),
                "artifact_paths": list(
                    cast(tuple[str, ...], contract["artifact_paths"])
                ),
                "artifact_formats": list(
                    cast(tuple[str, ...], contract["artifact_formats"])
                ),
                "manifest_last_path": cast(
                    str | None, contract["manifest_last_path"]
                ),
            }
            for contract in COMPONENT_ARTIFACT_CONTRACTS.values()
        ],
        "source_execution": {
            "authority_source_record_key": E0_U_AUTHORITY_SOURCE_RECORD_KEY,
            "runner_source_record_key": E0_U_RUNNER_SOURCE_RECORD_KEY,
            "component_source_records_key": E0_U_COMPONENT_SOURCE_RECORDS_KEY,
            "context_builder_source_record_key": E0_U_CONTEXT_BUILDER_SOURCE_RECORD_KEY,
            "support_source_records_key": E0_U_SUPPORT_SOURCE_RECORDS_KEY,
            "support_sources": [
                {
                    "support_id": spec["support_id"],
                    "module_name": spec["module_name"],
                    "source_path": spec["source_path"],
                    "required_symbols": list(
                        cast(Sequence[str], spec["required_symbols"])
                    ),
                }
                for spec in SEALED_SUPPORT_SOURCES
            ],
            "context_builder_module": E0_U_CONTEXT_BUILDER_MODULE,
            "context_builder_path": E0_U_CONTEXT_BUILDER_PATH.as_posix(),
            "context_builder_api": E0_U_CONTEXT_BUILDER_API,
            "context_builder_preflight_api": E0_U_CONTEXT_PREFLIGHT_API,
            "context_builder_and_preflight_same_sealed_module": True,
            "context_input_preflight": {
                "timing": "before_first_durable_outcome_access_log_append",
                "outcome_access_performed": False,
                "writes_performed": False,
                "complete_pretarget_scoring_performed": True,
                "phase3_overlay_authority_record_compared": True,
                "anchored_source_evidence_file_count": 7,
                "cross_append_policy": (
                    "reopen_rehash_redecode_rescore_and_compare_exact_path_bytes_sha256"
                ),
                "snapshot_reuse_authorized": False,
            },
            "component_loader": "compile_exec_exact_anchored_source_bytes",
            "importlib_component_loading": "forbidden",
            "pyc_component_loading": "forbidden",
            "source_revalidated_after_execution": True,
            "e0_u_authority_must_bind_exact_sources": True,
            "e0_u_authority_preexec_binding": "physical_equals_index_equals_head_git_blob",
            "e0_u_authority_git_blob_oid_recomputed": True,
            "e0_u_authority_top_level": "stdlib_only_definition_only",
            "authority_commit_binding_keys": list(E0_U_COMMIT_BINDING_KEYS),
            "authority_commit_topology": "historical_e0_m_R__phase3_code_H__phase3_evidence_P__phase3_activation_U",
            "historical_e0_m_commit": HISTORICAL_E0_M_COMMIT,
            "authority_commit_parent_chain": {
                "phase3_activation_commit": "HEAD",
                "phase3_evidence_commit": "HEAD~1",
                "phase3_code_commit": "HEAD~2",
                "historical_e0_m_commit": "HEAD~3",
            },
            "git_executable_record_key": E0_U_GIT_EXECUTABLE_RECORD_KEY,
            "runtime_environment_record_key": E0_U_RUNTIME_ENVIRONMENT_RECORD_KEY,
            "startup_flags": ["isolated", "no_site", "dont_write_bytecode"],
            "external_launch_argv": list(SEALED_BATCH_LAUNCH_ARGV),
            "external_launch_command": SEALED_BATCH_LAUNCH_COMMAND,
            "startup_environment": {"LANG": "C", "LC_ALL": "C"},
            "purelib_activation": "manual_after_e0_u_require_without_site_or_pth",
            "runtime_distributions": list(RUNTIME_DISTRIBUTIONS),
            "runtime_import_roots": sorted(RUNTIME_IMPORT_ROOTS),
            "runtime_recaptured_after_callbacks_before_publication_and_at_terminal": True,
            "authority_result_exact_keys": True,
            "component_authority_payload_excludes_private_apis": True,
        },
        "batch_context": {
            "exact_keys": sorted(BATCH_CONTEXT_KEYS),
            "execution_id_type": "nonempty_string",
            "rng_seed": RNG_SEED,
            "tables_type": "mapping_string_to_dataframe",
            "initial_table_names": sorted(OPENED_CONTEXT_TABLES),
            "stage_results_type": "mapping_string_to_mapping",
            "model_availability": dict(CURRENT_MODEL_AVAILABILITY),
            "software_evidence_type": "mapping_with_exact_logical_keys",
            "software_evidence_keys": sorted(SOFTWARE_EVIDENCE_KEYS),
            "component_context_is_copied": True,
            "component_context_table_views": {
                key: list(value)
                for key, value in COMPONENT_TABLE_VIEWS.items()
                if key != "E0-U_publication"
            },
            "component_context_stage_results": "E10_only",
            "component_context_software_evidence": "E10_only",
            "component_filesystem_writes": "forbidden",
        },
        "artifact_envelope": {
            "exact_keys": ["format", "payload", "manifest_last"],
            "formats": sorted(ARTIFACT_FORMATS),
            "publication": "runner_owned_single_transaction_after_all_stages",
        },
        "artifact_serialization": {
            "csv": "pandas_to_csv_index_false_lineterminator_lf_na_empty_float_17g_utf8",
            "parquet": "pandas_to_parquet_pyarrow_zstd_index_false",
            "json": "canonical_utf8_sort_keys_compact_lf_no_nan",
            "markdown": "exact_utf8_text",
            "xml": "exact_bytes_or_utf8_text",
            "physical_mode": "100644",
            "physical_nlink": 1,
        },
        "authority_context_factory_api": E0_U_CONTEXT_FACTORY_API,
        "authority_context_factory_arguments": [
            "authority",
            "sealed_batch_contract",
            "repo_root",
            "context_builder",
        ],
        "authority_transaction_publisher_api": E0_U_TRANSACTION_PUBLISHER_API,
        "authority_post_publication_auditor_api": E0_U_PUBLICATION_AUDITOR_API,
        "authority_transaction_publisher_arguments": [
            "authority",
            "sealed_batch_contract",
            "batch_context",
            "stage_results",
            "artifacts",
            "serialized_artifacts",
            "repo_root",
        ],
        "authority_transaction_publisher_receipt": {
            "exact_keys": sorted(PUBLICATION_RECEIPT_KEYS),
            "status": "sealed_batch_artifacts_published",
            "artifact_count": 52,
            "published_artifact_paths_sha256": EXPECTED_ARTIFACT_PATHS_SHA256,
            "artifact_path_digest": "sha256_canonical_json_sorted_exact_paths",
            "stage_count": 10,
            "one_shot_consumed": True,
            "guard_released": True,
            "rollback_performed": False,
            "manifest_written_last": True,
            "writes_performed": True,
        },
        "authority_post_publication_auditor_arguments": [
            "authority",
            "sealed_batch_contract",
            "batch_context",
            "stage_results",
            "artifacts",
            "serialized_artifacts",
            "publication_receipt",
            "repo_root",
        ],
        "authority_post_publication_audit": {
            "exact_keys": sorted(PUBLICATION_AUDIT_KEYS),
            "status": "sealed_batch_artifacts_physically_validated",
            "artifact_count": 52,
            "physical_record_exact_keys": sorted(PUBLICATION_AUDIT_RECORD_KEYS),
            "physical_record_order": "sorted_exact_paths",
            "publication_order": list(EXPECTED_PUBLICATION_ORDER),
            "publication_order_sha256": EXPECTED_PUBLICATION_ORDER_SHA256,
            "stage_count": 10,
            "one_shot_consumed": True,
            "guard_released": True,
            "publication_guard_present": False,
            "rollback_performed": False,
            "manifest_written_last": True,
            "writes_performed": True,
            "runner_physical_recapture_before_and_after_audit": True,
        },
        "stage_output_tables": {
            stage_id: list(table_names)
            for stage_id, table_names in STAGE_OUTPUT_TABLES.items()
        },
        "composite_stage_results": {
            "E4": {
                "component_id": "E4_composite",
                "ordered_component_ids": [
                    "E4_reference_targets",
                    "E4_trophic_evaluation",
                ],
                "output_tables": [
                    "trophic_reference_targets",
                    "trophic_proxy_metrics",
                    "carlson_reference_metrics",
                    "trophic_confusion_matrices",
                    "nla_semantic_metrics",
                ],
                "diagnostics_component_summary_exact_keys": [
                    "component_id",
                    "status",
                    "artifact_paths",
                    "table_names",
                ],
            }
        },
        "e1_scientific_executor_status": "implemented",
        "e1_input_tables": list(E1_INPUT_TABLES),
        "e1_output_tables": list(E1_OUTPUT_TABLES),
        "e1_required_nonempty_tables": list(E1_REQUIRED_NONEMPTY_TABLES),
        "e1_input_table_columns": {
            "predictions_long": list(E1_PREDICTION_COLUMNS),
            "intent_origins": list(E1_INTENT_COLUMNS),
            "target_outcomes": list(E1_TARGET_COLUMNS),
        },
        "e1_model_pairs": [list(value) for value in E1_MODEL_PAIRS],
        "e1_unavailable_models": list(UNAVAILABLE_MODEL_IDS),
        "e1_target_statuses": ["available", "target_unavailable"],
        "e1_location_holdout_role": "test_only",
        "e1_estimands": ["observation_weighted", "site_weighted"],
        "e1_noninferiority_margins": {
            "pr_auc_absolute": 0.02,
            "brier_absolute": 0.01,
            "status": "project_convention_locked_before_e0_u",
        },
        "e1_paired_metric_columns": list(PAIRED_METRIC_COLUMNS),
    }
)


def sealed_batch_contract() -> dict[str, Any]:
    """Return the public, mutation-free batch contract used by E0-M."""

    return cast(dict[str, Any], json.loads(_canonical_json_bytes(BATCH_CONTRACT)))


def sealed_batch_contract_sha256() -> str:
    return _sha256_bytes(_canonical_json_bytes(BATCH_CONTRACT))


def validate_sealed_batch_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = sealed_batch_contract()
    if dict(value) != expected:
        raise ClosureBenchmarkError("E0-M sealed batch contract drifted")
    return expected


def validate_sealed_batch_command(value: str | bytes) -> str:
    """Accept only the exact newline-terminated, non-shell batch command."""

    try:
        text = value.decode("utf-8") if isinstance(value, bytes) else value
    except UnicodeDecodeError as exc:
        raise ClosureBenchmarkError("E0-M sealed batch command is not UTF-8") from exc
    if type(text) is not str or text != SEALED_BATCH_COMMAND:
        raise ClosureBenchmarkError("E0-M sealed batch command drifted")
    return text


def _read_anchored_regular_bytes(
    relative_path: Path,
    *,
    repo_root: Path,
    expected_mode: int,
    expected_nlink: int,
) -> tuple[bytes, os.stat_result]:
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
        or relative_path.as_posix() != str(relative_path)
    ):
        raise ClosureBenchmarkError(
            f"E0-M path is not canonical: {relative_path.as_posix()}"
        )
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = (
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptors: list[int] = []
    descriptor = -1
    try:
        current = os.open(repo_root, directory_flags)
        descriptors.append(current)
        for part in relative_path.parts[:-1]:
            current = os.open(part, directory_flags, dir_fd=current)
            descriptors.append(current)
        descriptor = os.open(relative_path.name, file_flags, dir_fd=current)
        metadata = os.fstat(descriptor)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        named = os.stat(
            relative_path.name,
            dir_fd=current,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise ClosureBenchmarkError(
            f"E0-M anchored file cannot be read: {relative_path.as_posix()}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        for opened in reversed(descriptors):
            os.close(opened)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != expected_nlink
        or stat.S_IMODE(metadata.st_mode) != expected_mode
        or (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )
        != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        or (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_nlink)
        != (named.st_dev, named.st_ino, named.st_mode, named.st_nlink)
        or len(payload) != metadata.st_size
    ):
        raise ClosureBenchmarkError(
            f"E0-M anchored file identity drifted: {relative_path.as_posix()}"
        )
    return payload, metadata


def _read_regular_source(
    relative_path: Path, *, repo_root: Path
) -> tuple[bytes, os.stat_result]:
    return _read_anchored_regular_bytes(
        relative_path,
        repo_root=repo_root,
        expected_mode=0o644,
        expected_nlink=1,
    )


def _source_identity_record(
    relative_path: Path, payload: bytes, metadata: os.stat_result
) -> dict[str, Any]:
    return {
        "path": relative_path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
    }


def _require_source_identity(
    expected: Any,
    observed: Mapping[str, Any],
    *,
    context: str,
) -> None:
    if not isinstance(expected, Mapping):
        raise ClosureBenchmarkError(f"E0-U sealed source binding drifted: {context}")
    expected_path = expected.get("path", expected.get("source_path"))
    if expected_path != observed.get("path") or any(
        type(expected.get(key)) is not type(value) or expected.get(key) != value
        for key, value in observed.items()
        if key != "path"
    ):
        raise ClosureBenchmarkError(f"E0-U sealed source binding drifted: {context}")


def _git_executable_record() -> dict[str, Any]:
    """Authenticate the only Git binary admitted before E0-U source execution."""

    try:
        if GIT_EXECUTABLE.resolve(strict=True) != GIT_EXECUTABLE:
            raise ClosureBenchmarkError("E0-U Git executable is not canonical")
        before = os.lstat(GIT_EXECUTABLE)
        descriptor = os.open(
            GIT_EXECUTABLE,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            opened = os.fstat(descriptor)
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(descriptor)
        after = os.lstat(GIT_EXECUTABLE)
    except (OSError, RuntimeError) as exc:
        if isinstance(exc, ClosureBenchmarkError):
            raise
        raise ClosureBenchmarkError("E0-U Git executable cannot be authenticated") from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_IMODE(before.st_mode) != 0o755
        or before.st_nlink != 1
        or before.st_uid != GIT_EXECUTABLE_UID
        or before.st_gid != GIT_EXECUTABLE_GID
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    ):
        raise ClosureBenchmarkError("E0-U Git executable identity drifted")
    payload = b"".join(chunks)
    digest = _sha256_bytes(payload)
    if digest != GIT_EXECUTABLE_SHA256:
        raise ClosureBenchmarkError("E0-U Git executable bytes drifted")
    return {
        "path": GIT_EXECUTABLE.as_posix(),
        "bytes": len(payload),
        "sha256": digest,
        "device": int(before.st_dev),
        "inode": int(before.st_ino),
        "mode": stat.S_IMODE(before.st_mode),
        "nlink": int(before.st_nlink),
        "uid": int(before.st_uid),
        "gid": int(before.st_gid),
        "mtime_ns": int(before.st_mtime_ns),
        "ctime_ns": int(before.st_ctime_ns),
    }


def _git_config_record() -> dict[str, Any]:
    payload, metadata = _read_anchored_regular_bytes(
        GIT_CONFIG_PATH,
        repo_root=PROJECT_ROOT,
        expected_mode=0o644,
        expected_nlink=1,
    )
    digest = _sha256_bytes(payload)
    if (
        digest != GIT_CONFIG_SHA256
        or metadata.st_uid != 1000
        or metadata.st_gid != 1000
    ):
        raise ClosureBenchmarkError("E0-U local Git config binding drifted")
    return {
        "path": GIT_CONFIG_PATH.as_posix(),
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


def _sealed_git(*arguments: str, accepted_codes: tuple[int, ...] = (0,)) -> bytes:
    git_record_before = _git_executable_record()
    config_before = _git_config_record()
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
    command = (
        GIT_EXECUTABLE.as_posix(),
        "--no-pager",
        "--literal-pathspecs",
        f"--git-dir={(PROJECT_ROOT / '.git').as_posix()}",
        f"--work-tree={PROJECT_ROOT.as_posix()}",
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
        "-c",
        "http.sslVerify=true",
        "-c",
        "http.followRedirects=false",
        "-c",
        "protocol.version=2",
        "-c",
        "protocol.file.allow=never",
        "-c",
        "protocol.ext.allow=never",
        *arguments,
    )
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ClosureBenchmarkError("E0-U sealed Git query failed") from exc
    if (
        completed.returncode not in accepted_codes
        or _git_executable_record() != git_record_before
        or _git_config_record() != config_before
    ):
        raise ClosureBenchmarkError("E0-U sealed Git query failed closed")
    return bytes(completed.stdout)


def _https_helper_record() -> dict[str, Any]:
    try:
        link = os.lstat(GIT_REMOTE_HTTPS_HELPER)
        target = os.readlink(GIT_REMOTE_HTTPS_HELPER)
    except OSError as exc:
        raise ClosureBenchmarkError("E0-U HTTPS Git helper is absent") from exc
    if (
        not stat.S_ISLNK(link.st_mode)
        or target != "git-remote-http"
        or link.st_nlink != 1
        or link.st_uid != GIT_EXECUTABLE_UID
        or link.st_gid != GIT_EXECUTABLE_GID
        or GIT_REMOTE_HTTPS_HELPER.resolve(strict=True) != GIT_REMOTE_HTTP_HELPER
    ):
        raise ClosureBenchmarkError("E0-U HTTPS Git helper link drifted")
    target_record = _absolute_regular_record(
        GIT_REMOTE_HTTP_HELPER, expected_mode=0o755
    )
    if (
        target_record["sha256"] != GIT_REMOTE_HTTP_SHA256
        or target_record["uid"] != GIT_EXECUTABLE_UID
        or target_record["gid"] != GIT_EXECUTABLE_GID
    ):
        raise ClosureBenchmarkError("E0-U HTTPS Git helper bytes drifted")
    return {
        "link_path": GIT_REMOTE_HTTPS_HELPER.as_posix(),
        "link_target": target,
        "link_mode": stat.S_IMODE(link.st_mode),
        "link_nlink": int(link.st_nlink),
        "link_uid": int(link.st_uid),
        "link_gid": int(link.st_gid),
        "target": target_record,
    }


def _live_remote_main_head() -> str:
    helper_before = _https_helper_record()
    raw = _sealed_git(
        "ls-remote",
        "--refs",
        LIVE_REMOTE_URL,
        "refs/heads/main",
    )
    if _https_helper_record() != helper_before:
        raise ClosureBenchmarkError("E0-U HTTPS Git helper changed during remote query")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ClosureBenchmarkError("E0-U live remote response is not ASCII") from exc
    fields = text.rstrip("\n").split("\t")
    if (
        raw.count(b"\n") != 1
        or not raw.endswith(b"\n")
        or len(fields) != 2
        or fields[1] != "refs/heads/main"
        or len(fields[0]) != 40
        or any(character not in "0123456789abcdef" for character in fields[0])
    ):
        raise ClosureBenchmarkError("E0-U live remote main response drifted")
    return fields[0]


def _git_oid_output(raw: bytes, *, context: str) -> str:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ClosureBenchmarkError(f"E0-U Git {context} is not ASCII") from exc
    if (
        len(text) != 41
        or not text.endswith("\n")
        or any(character not in "0123456789abcdef" for character in text[:-1])
    ):
        raise ClosureBenchmarkError(f"E0-U Git {context} is not one exact object id")
    return text[:-1]


def _content_addressed_git_object(object_type: str, oid: str) -> bytes:
    if object_type not in {"commit", "tree", "blob"}:
        raise ClosureBenchmarkError("E0-U Git object type is not sealed")
    payload = _sealed_git("cat-file", object_type, oid)
    calculated = hashlib.sha1(
        f"{object_type} {len(payload)}\0".encode("ascii") + payload,
        usedforsecurity=False,
    ).hexdigest()
    if calculated != oid:
        raise ClosureBenchmarkError(f"E0-U Git {object_type} content address drifted")
    return payload


def _tree_entry(tree_payload: bytes, name: str) -> tuple[str, str]:
    position = 0
    matches: list[tuple[str, str]] = []
    encoded_name = name.encode("utf-8")
    while position < len(tree_payload):
        try:
            space = tree_payload.index(b" ", position)
            nul = tree_payload.index(b"\0", space + 1)
        except ValueError as exc:
            raise ClosureBenchmarkError("E0-U Git tree object is malformed") from exc
        oid_start = nul + 1
        oid_end = oid_start + 20
        if oid_end > len(tree_payload):
            raise ClosureBenchmarkError("E0-U Git tree object is truncated")
        try:
            mode = tree_payload[position:space].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ClosureBenchmarkError("E0-U Git tree mode is not ASCII") from exc
        entry_name = tree_payload[space + 1 : nul]
        entry_oid = tree_payload[oid_start:oid_end].hex()
        if entry_name == encoded_name:
            matches.append((mode, entry_oid))
        position = oid_end
    if position != len(tree_payload) or len(matches) != 1:
        raise ClosureBenchmarkError("E0-U Git tree path is not unique")
    return matches[0]


def _content_addressed_head_blob(head: str, relative_path: Path) -> tuple[str, bytes]:
    commit = _content_addressed_git_object("commit", head)
    first_line = commit.split(b"\n", 1)[0]
    if not first_line.startswith(b"tree ") or len(first_line) != 45:
        raise ClosureBenchmarkError("E0-U HEAD commit tree binding is malformed")
    try:
        tree_oid = first_line[5:].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ClosureBenchmarkError("E0-U HEAD tree object id is not ASCII") from exc
    if any(character not in "0123456789abcdef" for character in tree_oid):
        raise ClosureBenchmarkError("E0-U HEAD tree object id is malformed")
    parts = relative_path.parts
    for index, part in enumerate(parts):
        tree_payload = _content_addressed_git_object("tree", tree_oid)
        mode, entry_oid = _tree_entry(tree_payload, part)
        if index < len(parts) - 1:
            if mode != "40000":
                raise ClosureBenchmarkError("E0-U authority ancestor is not a Git tree")
            tree_oid = entry_oid
            continue
        if mode != "100644":
            raise ClosureBenchmarkError("E0-U authority Git mode is not 100644")
        return entry_oid, _content_addressed_git_object("blob", entry_oid)
    raise ClosureBenchmarkError("E0-U authority Git path is empty")


def _git_bound_e0_u_authority_source_record() -> dict[str, Any]:
    """Bind the future E0-U source to aligned refs, HEAD, index, and worktree."""

    path = E0_U_AUTHORITY_PATH.as_posix()
    # Missing E0-U is the normal pre-unblinding state and must stop locally,
    # before even attempting the live-remote trust check.
    payload, metadata = _read_regular_source(E0_U_AUTHORITY_PATH, repo_root=PROJECT_ROOT)
    try:
        head = _git_oid_output(
            _sealed_git("rev-parse", "--verify", "HEAD^{commit}"),
            context="HEAD",
        )
        refs = {
            name: _git_oid_output(
                _sealed_git("rev-parse", "--verify", f"{name}^{{commit}}"),
                context=name,
            )
            for name in ("refs/heads/main", "refs/remotes/origin/main", "refs/remotes/origin/HEAD")
        }
        head_symbolic = _sealed_git("symbolic-ref", "--quiet", "HEAD").decode().strip()
        origin_symbolic = _sealed_git(
            "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"
        ).decode().strip()
        tree_raw = _sealed_git("ls-tree", "-z", "HEAD", "--", path)
        index_raw = _sealed_git("ls-files", "--stage", "-z", "--", path)
    except (ClosureBenchmarkError, UnicodeDecodeError) as exc:
        raise ClosureBenchmarkError("E0-U repository topology cannot authenticate authority") from exc
    if (
        len(head) != 40
        or any(character not in "0123456789abcdef" for character in head)
        or set(refs.values()) != {head}
        or head_symbolic != "refs/heads/main"
        or origin_symbolic != "refs/remotes/origin/main"
        or _live_remote_main_head() != head
    ):
        raise ClosureBenchmarkError("E0-U repository refs are not exactly aligned")
    tree_oid, blob = _content_addressed_head_blob(head, E0_U_AUTHORITY_PATH)
    expected_tree_record = (
        f"100644 blob {tree_oid}\t{path}\0".encode("utf-8")
    )
    if tree_raw != expected_tree_record:
        raise ClosureBenchmarkError("E0-U authority ls-tree binding drifted")
    expected_index_record = f"100644 {tree_oid} 0\t{path}\0".encode("utf-8")
    if index_raw != expected_index_record:
        raise ClosureBenchmarkError("E0-U authority is staged or index-bound to another blob")
    if payload != blob:
        raise ClosureBenchmarkError("E0-U authority worktree bytes differ from HEAD")
    if (
        _git_oid_output(
            _sealed_git("rev-parse", "--verify", "HEAD^{commit}"),
            context="HEAD recapture",
        )
        != head
        or _git_oid_output(
            _sealed_git("rev-parse", "--verify", "refs/heads/main^{commit}"),
            context="main recapture",
        )
        != head
        or _git_oid_output(
            _sealed_git("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
            context="origin/main recapture",
        )
        != head
        or _git_oid_output(
            _sealed_git("rev-parse", "--verify", "refs/remotes/origin/HEAD^{commit}"),
            context="origin/HEAD recapture",
        )
        != head
        or _live_remote_main_head() != head
    ):
        raise ClosureBenchmarkError("E0-U repository changed during source authentication")
    return {
        **_source_identity_record(E0_U_AUTHORITY_PATH, payload, metadata),
        "git_head": head,
        "git_oid": tree_oid,
        "git_mode": "100644",
        "index_oid": tree_oid,
        "index_mode": "100644",
        "head_ref": head_symbolic,
        "origin_head_ref": origin_symbolic,
        "refs_aligned": True,
        "live_remote_url": LIVE_REMOTE_URL,
        "live_remote_main": head,
        "content_addressed_commit_tree_blob": True,
        "staged_changes_present": False,
        "untracked": False,
    }


def _require_sealed_startup_environment() -> None:
    if (
        sys.flags.isolated != 1
        or sys.flags.no_site != 1
        or not sys.dont_write_bytecode
        or tuple(getattr(sys, "orig_argv", ())) != SEALED_BATCH_ARGV
        or tuple(sys.argv) != (SCRIPT_PATH.as_posix(), SEALED_BATCH_MODE)
        or Path.cwd().resolve() != PROJECT_ROOT
        or Path(sys.executable) != PROJECT_ROOT / SEALED_BATCH_ARGV[0]
        or tuple(sys.path) != BOOTSTRAP_SYS_PATH
        or tuple(_import_hook_identity(value) for value in sys.meta_path)
        != BOOTSTRAP_META_PATH
        or tuple(_import_hook_identity(value) for value in sys.path_hooks)
        != BOOTSTRAP_PATH_HOOKS
        or sys.gettrace() is not None
        or sys.getprofile() is not None
        or sys.pycache_prefix is not None
    ):
        raise ClosureBenchmarkError("E0-U sealed execution startup flags or argv drifted")
    _exact_process_environment()
    _env_executable_record()
    _python_executable_record()


def _exact_process_environment() -> dict[str, str]:
    observed = dict(os.environ)
    expected = {"LANG": "C", "LC_ALL": "C"}
    if observed != expected:
        raise ClosureBenchmarkError("E0-U sealed execution environment is not sanitized")
    return expected


def _normalize_sealed_dependency_import_environment() -> None:
    expected = {"LANG": "C", "LC_ALL": "C"}
    observed = dict(os.environ)
    known_import_defaults = {
        "KMP_DUPLICATE_LIB_OK": "True",
        "KMP_INIT_AT_FORK": "FALSE",
    }
    if observed == expected:
        return
    if observed != {**expected, **known_import_defaults}:
        raise ClosureBenchmarkError(
            "E0-U scientific dependency changed the sealed process environment"
        )
    for name in known_import_defaults:
        os.environ.pop(name, None)
    _exact_process_environment()


def _require_no_preactivated_runtime() -> None:
    purelib = PROJECT_ROOT / ".venv" / "lib" / (
        f"python{sys.version_info.major}.{sys.version_info.minor}"
    ) / "site-packages"
    for name, module in tuple(sys.modules.items()):
        root = name.partition(".")[0]
        if root not in BOOTSTRAP_MODULE_ROOTS | RUNTIME_STDLIB_IMPORT_ROOTS:
            raise ClosureBenchmarkError(
                f"E0-U module existed outside the bootstrap allowlist: {name}"
            )
        if root == "site" or root in RUNTIME_IMPORT_ROOTS:
            raise ClosureBenchmarkError(
                f"E0-U scientific runtime was imported before activation: {name}"
            )
        origin = getattr(module, "__file__", None)
        if type(origin) is str and _path_is_within(Path(origin), (purelib,)):
            raise ClosureBenchmarkError(
                f"E0-U purelib module was imported before activation: {name}"
            )


def _require_stdlib_only_authority_source(payload: bytes) -> None:
    try:
        tree = ast.parse(payload.decode("utf-8"), filename=E0_U_AUTHORITY_PATH.as_posix())
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ClosureBenchmarkError("E0-U authority source is not valid UTF-8 Python") from exc
    body = list(tree.body)
    offset = 0
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and type(body[0].value.value) is str
    ):
        offset = 1
    if offset >= len(body):
        raise ClosureBenchmarkError("E0-U authority future-annotations seal is absent")
    future = body[offset]
    if not (
        isinstance(future, ast.ImportFrom)
        and future.level == 0
        and future.module == "__future__"
        and len(future.names) == 1
        and future.names[0].name == "annotations"
        and future.names[0].asname is None
    ):
        raise ClosureBenchmarkError(
            "E0-U authority must begin with future annotations"
        )

    def require_literal(value: ast.expr | None) -> None:
        if value is None:
            return
        try:
            ast.literal_eval(value)
        except (ValueError, TypeError) as exc:
            raise ClosureBenchmarkError(
                "E0-U authority startup value is not a literal"
            ) from exc

    def require_safe_function_definition(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        if node.decorator_list or getattr(node, "type_params", ()):
            raise ClosureBenchmarkError(
                "E0-U authority definition has startup side effects"
            )
        for default in (*node.args.defaults, *node.args.kw_defaults):
            require_literal(default)
        annotations: list[ast.expr] = []
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ):
            if argument.annotation is not None:
                annotations.append(argument.annotation)
        for argument in (node.args.vararg, node.args.kwarg):
            if argument is not None and argument.annotation is not None:
                annotations.append(argument.annotation)
        if node.returns is not None:
            annotations.append(node.returns)
        if any(
            isinstance(
                descendant,
                (
                    ast.Call,
                    ast.Lambda,
                    ast.Await,
                    ast.Yield,
                    ast.YieldFrom,
                    ast.NamedExpr,
                    ast.ListComp,
                    ast.SetComp,
                    ast.DictComp,
                    ast.GeneratorExp,
                ),
            )
            for annotation in annotations
            for descendant in ast.walk(annotation)
        ):
            raise ClosureBenchmarkError(
                "E0-U authority annotation is not a static deferred expression"
            )

    for node in body[offset + 1 :]:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            require_safe_function_definition(node)
            continue
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise ClosureBenchmarkError(
                    "E0-U authority assignment target is not a sealed name"
                )
            require_literal(node.value)
            continue
        if isinstance(node, ast.AnnAssign):
            if not isinstance(node.target, ast.Name):
                raise ClosureBenchmarkError(
                    "E0-U authority assignment target is not a sealed name"
                )
            require_literal(node.value)
            if any(
                isinstance(descendant, (ast.Call, ast.Lambda, ast.NamedExpr))
                for descendant in ast.walk(node.annotation)
            ):
                raise ClosureBenchmarkError(
                    "E0-U authority annotation is not a static deferred expression"
                )
            continue
        raise ClosureBenchmarkError("E0-U authority top level is not definition-only")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            raise ClosureBenchmarkError("E0-U authority classes are forbidden")
        modules: tuple[str, ...] = ()
        if isinstance(node, ast.Import):
            modules = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node is future:
                continue
            if node.level or node.module is None:
                raise ClosureBenchmarkError("E0-U authority contains a relative import")
            modules = (node.module,)
        for module in modules:
            if module.split(".", 1)[0] not in AUTHORITY_STDLIB_IMPORT_ROOTS:
                raise ClosureBenchmarkError(
                    "E0-U authority import escaped the closed stdlib allowlist"
                )
        if (
            isinstance(node, ast.Name)
            and node.id
            in {
                "__builtins__",
                "__import__",
                "builtins",
                "compile",
                "delattr",
                "eval",
                "exec",
                "getattr",
                "globals",
                "locals",
                "setattr",
                "vars",
            }
        ) or (
            isinstance(node, ast.Attribute)
            and (
                (node.attr.startswith("__") and node.attr.endswith("__"))
                or node.attr
                in {
                    "__builtins__",
                    "__dict__",
                    "__globals__",
                    "__import__",
                    "modules",
                    "meta_path",
                    "path_hooks",
                    "path_importer_cache",
                }
                or (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "sys"
                    and node.attr
                    in {"meta_path", "modules", "path", "path_hooks", "path_importer_cache"}
                )
            )
        ) or (
            isinstance(node, ast.Constant)
            and node.value in {"__import__", "compile", "eval", "exec"}
        ):
            raise ClosureBenchmarkError("E0-U authority contains a dynamic loader")


def _sealed_authority_builtins() -> dict[str, Any]:
    allowed = dict(vars(builtins))
    real_import = builtins.__import__

    def sealed_import(
        name: str,
        globals_value: Mapping[str, Any] | None = None,
        locals_value: Mapping[str, Any] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> Any:
        if type(name) is str and name.partition(".")[0] == "__future__":
            if (
                name == "__future__"
                and type(level) is int
                and level == 0
                and type(fromlist) is tuple
                and fromlist == ("annotations",)
            ):
                return real_import(
                    name, globals_value, locals_value, fromlist, level
                )
            raise ImportError(
                "E0-U authority future import is not exactly annotations"
            )
        if (
            type(name) is not str
            or not name
            or type(level) is not int
            or level != 0
            or name.partition(".")[0] not in AUTHORITY_STDLIB_IMPORT_ROOTS
        ):
            raise ImportError("E0-U authority dynamic import escaped the stdlib allowlist")
        return real_import(name, globals_value, locals_value, fromlist, level)

    allowed["__import__"] = sealed_import
    for name in ("breakpoint", "compile", "eval", "exec", "help", "input"):
        allowed.pop(name, None)
    return allowed


def _absolute_regular_record(path: Path, *, expected_mode: int) -> dict[str, Any]:
    try:
        before = os.lstat(path)
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            opened = os.fstat(descriptor)
            digest = hashlib.sha256()
            size = 0
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
            after_opened = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after = os.lstat(path)
    except OSError as exc:
        raise ClosureBenchmarkError(f"E0-U runtime file is unreadable: {path}") from exc
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
        or stat.S_IMODE(before.st_mode) != expected_mode
        or before.st_nlink != 1
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
            after_opened.st_dev,
            after_opened.st_ino,
            after_opened.st_mode,
            after_opened.st_nlink,
            after_opened.st_size,
            after_opened.st_mtime_ns,
            after_opened.st_ctime_ns,
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
        or size != before.st_size
    ):
        raise ClosureBenchmarkError(f"E0-U runtime file identity drifted: {path}")
    return {
        "path": path.as_posix(),
        "bytes": size,
        "sha256": digest.hexdigest(),
        "device": int(before.st_dev),
        "inode": int(before.st_ino),
        "mode": stat.S_IMODE(before.st_mode),
        "nlink": int(before.st_nlink),
        "uid": int(before.st_uid),
        "gid": int(before.st_gid),
        "mtime_ns": int(before.st_mtime_ns),
        "ctime_ns": int(before.st_ctime_ns),
    }


def _env_executable_record() -> dict[str, Any]:
    record = _absolute_regular_record(ENV_EXECUTABLE, expected_mode=0o755)
    if (
        record["sha256"] != ENV_EXECUTABLE_SHA256
        or record["uid"] != GIT_EXECUTABLE_UID
        or record["gid"] != GIT_EXECUTABLE_GID
    ):
        raise ClosureBenchmarkError("E0-U env executable binding drifted")
    return record


def _python_executable_record() -> dict[str, Any]:
    link_path = PROJECT_ROOT / SEALED_BATCH_PYTHON_ARGV[0]
    try:
        link = os.lstat(link_path)
        raw_target = os.readlink(link_path)
        resolved = link_path.resolve(strict=True)
    except OSError as exc:
        raise ClosureBenchmarkError("E0-U Python executable cannot be resolved") from exc
    if (
        not stat.S_ISLNK(link.st_mode)
        or stat.S_IMODE(link.st_mode) != 0o777
        or link.st_nlink != 1
        or link.st_uid != 1000
        or link.st_gid != 1000
        or raw_target != PYTHON_EXECUTABLE_TARGET.as_posix()
        or resolved != PYTHON_EXECUTABLE_TARGET
        or Path(sys.executable) != link_path
    ):
        raise ClosureBenchmarkError("E0-U Python executable link drifted")
    target = _absolute_regular_record(PYTHON_EXECUTABLE_TARGET, expected_mode=0o755)
    if (
        target["sha256"] != PYTHON_EXECUTABLE_SHA256
        or target["uid"] != GIT_EXECUTABLE_UID
        or target["gid"] != GIT_EXECUTABLE_GID
    ):
        raise ClosureBenchmarkError("E0-U Python executable bytes drifted")
    return {
        "link_path": link_path.as_posix(),
        "link_target": raw_target,
        "link_device": int(link.st_dev),
        "link_inode": int(link.st_ino),
        "link_mode": stat.S_IMODE(link.st_mode),
        "link_nlink": int(link.st_nlink),
        "link_uid": int(link.st_uid),
        "link_gid": int(link.st_gid),
        "link_mtime_ns": int(link.st_mtime_ns),
        "link_ctime_ns": int(link.st_ctime_ns),
        "target": target,
    }


def _runtime_tree_records(
    directory_fd: int,
    *,
    relative_prefix: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        names = sorted(os.listdir(directory_fd))
    except OSError as exc:
        raise ClosureBenchmarkError("E0-U runtime directory cannot be enumerated") from exc
    for name in names:
        if not name or name in {".", ".."} or "/" in name or "\0" in name:
            raise ClosureBenchmarkError("E0-U runtime tree has a noncanonical name")
        relative = f"{relative_prefix}/{name}" if relative_prefix else name
        try:
            named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError as exc:
            raise ClosureBenchmarkError("E0-U runtime tree entry cannot be stated") from exc
        if stat.S_ISDIR(named.st_mode):
            flags = (
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            try:
                child_fd = os.open(name, flags, dir_fd=directory_fd)
            except OSError as exc:
                raise ClosureBenchmarkError("E0-U runtime directory cannot be anchored") from exc
            try:
                opened = os.fstat(child_fd)
                if (
                    not stat.S_ISDIR(opened.st_mode)
                    or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
                ):
                    raise ClosureBenchmarkError("E0-U runtime directory identity drifted")
                records.append(
                    {
                        "path": relative,
                        "type": "directory",
                        "device": int(opened.st_dev),
                        "inode": int(opened.st_ino),
                        "mode": stat.S_IMODE(opened.st_mode),
                        "nlink": int(opened.st_nlink),
                        "mtime_ns": int(opened.st_mtime_ns),
                        "ctime_ns": int(opened.st_ctime_ns),
                    }
                )
                records.extend(
                    _runtime_tree_records(child_fd, relative_prefix=relative)
                )
                after_opened = os.fstat(child_fd)
                after_named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if (opened.st_dev, opened.st_ino, opened.st_mtime_ns, opened.st_ctime_ns) != (
                    after_opened.st_dev,
                    after_opened.st_ino,
                    after_opened.st_mtime_ns,
                    after_opened.st_ctime_ns,
                ) or (opened.st_dev, opened.st_ino, opened.st_mtime_ns, opened.st_ctime_ns) != (
                    after_named.st_dev,
                    after_named.st_ino,
                    after_named.st_mtime_ns,
                    after_named.st_ctime_ns,
                ):
                    raise ClosureBenchmarkError("E0-U runtime directory changed during capture")
            finally:
                os.close(child_fd)
            continue
        if not stat.S_ISREG(named.st_mode) or named.st_nlink != 1:
            raise ClosureBenchmarkError("E0-U runtime tree contains a non-regular entry")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            file_fd = os.open(name, flags, dir_fd=directory_fd)
        except OSError as exc:
            raise ClosureBenchmarkError("E0-U runtime file cannot be anchored") from exc
        try:
            opened = os.fstat(file_fd)
            digest = hashlib.sha256()
            size = 0
            while True:
                chunk = os.read(file_fd, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
            after_opened = os.fstat(file_fd)
        finally:
            os.close(file_fd)
        after_named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        file_identity = (
            opened.st_dev,
            opened.st_ino,
            opened.st_mode,
            opened.st_nlink,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        if (
            file_identity
            != (
                named.st_dev,
                named.st_ino,
                named.st_mode,
                named.st_nlink,
                named.st_size,
                named.st_mtime_ns,
                named.st_ctime_ns,
            )
            or file_identity
            != (
                after_opened.st_dev,
                after_opened.st_ino,
                after_opened.st_mode,
                after_opened.st_nlink,
                after_opened.st_size,
                after_opened.st_mtime_ns,
                after_opened.st_ctime_ns,
            )
            or file_identity
            != (
                after_named.st_dev,
                after_named.st_ino,
                after_named.st_mode,
                after_named.st_nlink,
                after_named.st_size,
                after_named.st_mtime_ns,
                after_named.st_ctime_ns,
            )
            or size != opened.st_size
        ):
            raise ClosureBenchmarkError("E0-U runtime file changed during capture")
        records.append(
            {
                "path": relative,
                "type": "file",
                "bytes": size,
                "sha256": digest.hexdigest(),
                "device": int(opened.st_dev),
                "inode": int(opened.st_ino),
                "mode": stat.S_IMODE(opened.st_mode),
                "nlink": int(opened.st_nlink),
                "mtime_ns": int(opened.st_mtime_ns),
                "ctime_ns": int(opened.st_ctime_ns),
            }
        )
    return records


def _validate_runtime_distribution_record(
    distribution: str,
    roots: tuple[str, ...],
    records: Sequence[Mapping[str, Any]],
    *,
    purelib: Path,
) -> dict[str, Any]:
    dist_info = next((root for root in roots if root.endswith(".dist-info")), None)
    if dist_info is None:
        raise ClosureBenchmarkError("E0-U runtime distribution lacks dist-info")
    record_path = f"{dist_info}/RECORD"
    by_path = {
        cast(str, record["path"]): record
        for record in records
        if record.get("type") == "file"
    }
    if record_path not in by_path:
        raise ClosureBenchmarkError("E0-U runtime distribution RECORD is absent")
    payload, _metadata = _read_anchored_regular_bytes(
        Path(record_path),
        repo_root=purelib,
        expected_mode=0o644,
        expected_nlink=1,
    )
    try:
        rows = list(csv.reader(io.StringIO(payload.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ClosureBenchmarkError("E0-U runtime distribution RECORD is malformed") from exc
    seen: set[str] = set()
    covered: set[str] = set()
    outside: list[str] = []
    for row in rows:
        if len(row) != 3 or not row[0] or row[0] in seen:
            raise ClosureBenchmarkError("E0-U runtime distribution RECORD rows drifted")
        path, digest_field, size_field = row
        seen.add(path)
        if not any(path == root or path.startswith(f"{root}/") for root in roots):
            outside.append(path)
            continue
        observed = by_path.get(path)
        if observed is None:
            raise ClosureBenchmarkError("E0-U runtime RECORD payload is absent")
        covered.add(path)
        if path == record_path and not digest_field and not size_field:
            continue
        if not digest_field.startswith("sha256=") or not size_field.isdecimal():
            raise ClosureBenchmarkError("E0-U runtime RECORD digest dialect drifted")
        encoded = digest_field.partition("=")[2]
        try:
            decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).hex()
        except (ValueError, TypeError) as exc:
            raise ClosureBenchmarkError("E0-U runtime RECORD digest is malformed") from exc
        if decoded != observed.get("sha256") or int(size_field) != observed.get("bytes"):
            raise ClosureBenchmarkError("E0-U runtime RECORD payload digest drifted")
    allowed_outside = (
        {"../../../bin/f2py", "../../../bin/numpy-config"}
        if distribution == "numpy"
        else set()
    )
    if set(outside) != allowed_outside:
        raise ClosureBenchmarkError("E0-U runtime RECORD escaped sealed roots")
    unrecorded = set(by_path).difference(covered)
    if any(
        "/__pycache__/" not in path or not path.endswith(".pyc")
        for path in unrecorded
    ):
        raise ClosureBenchmarkError("E0-U runtime root contains an unrecorded payload")
    return {
        "path": record_path,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "row_count": len(rows),
        "unrecorded_pyc_count": len(unrecorded),
        "outside_runtime_paths": sorted(outside),
    }


def _runtime_environment_record() -> dict[str, Any]:
    purelib = PROJECT_ROOT / ".venv" / "lib" / (
        f"python{sys.version_info.major}.{sys.version_info.minor}"
    ) / "site-packages"
    python_record = _python_executable_record()
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        purelib_fd = os.open(purelib, directory_flags)
    except OSError as exc:
        raise ClosureBenchmarkError("E0-U purelib cannot be anchored") from exc
    distribution_records: list[dict[str, Any]] = []
    try:
        purelib_metadata = os.fstat(purelib_fd)
        top_level_records: list[dict[str, Any]] = []
        for name in sorted(os.listdir(purelib_fd)):
            metadata = os.stat(name, dir_fd=purelib_fd, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                entry_type = "directory"
            elif stat.S_ISREG(metadata.st_mode):
                entry_type = "file"
            else:
                raise ClosureBenchmarkError("E0-U purelib top level is not regular")
            top_level_records.append(
                {
                    "path": name,
                    "type": entry_type,
                    "bytes": int(metadata.st_size),
                    "device": int(metadata.st_dev),
                    "inode": int(metadata.st_ino),
                    "mode": stat.S_IMODE(metadata.st_mode),
                    "nlink": int(metadata.st_nlink),
                    "mtime_ns": int(metadata.st_mtime_ns),
                    "ctime_ns": int(metadata.st_ctime_ns),
                }
            )
        for distribution in RUNTIME_DISTRIBUTIONS:
            roots = RUNTIME_DISTRIBUTION_ROOTS[distribution]
            records: list[dict[str, Any]] = []
            for root in roots:
                try:
                    named = os.stat(root, dir_fd=purelib_fd, follow_symlinks=False)
                except OSError as exc:
                    raise ClosureBenchmarkError(
                        f"E0-U runtime distribution root is absent: {distribution}:{root}"
                    ) from exc
                if stat.S_ISDIR(named.st_mode):
                    root_fd = os.open(root, directory_flags, dir_fd=purelib_fd)
                    try:
                        opened = os.fstat(root_fd)
                        if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
                            raise ClosureBenchmarkError("E0-U runtime root identity drifted")
                        records.append(
                            {
                                "path": root,
                                "type": "directory",
                                "device": int(opened.st_dev),
                                "inode": int(opened.st_ino),
                                "mode": stat.S_IMODE(opened.st_mode),
                                "nlink": int(opened.st_nlink),
                                "mtime_ns": int(opened.st_mtime_ns),
                                "ctime_ns": int(opened.st_ctime_ns),
                            }
                        )
                        records.extend(
                            _runtime_tree_records(root_fd, relative_prefix=root)
                        )
                    finally:
                        os.close(root_fd)
                elif stat.S_ISREG(named.st_mode):
                    file_fd = os.open(
                        root,
                        os.O_RDONLY
                        | getattr(os, "O_CLOEXEC", 0)
                        | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=purelib_fd,
                    )
                    try:
                        digest = hashlib.sha256()
                        size = 0
                        while True:
                            chunk = os.read(file_fd, 1024 * 1024)
                            if not chunk:
                                break
                            digest.update(chunk)
                            size += len(chunk)
                        opened = os.fstat(file_fd)
                    finally:
                        os.close(file_fd)
                    if opened.st_nlink != 1 or size != opened.st_size:
                        raise ClosureBenchmarkError("E0-U runtime root file drifted")
                    records.append(
                        {
                            "path": root,
                            "type": "file",
                            "bytes": size,
                            "sha256": digest.hexdigest(),
                            "device": int(opened.st_dev),
                            "inode": int(opened.st_ino),
                            "mode": stat.S_IMODE(opened.st_mode),
                            "nlink": int(opened.st_nlink),
                            "mtime_ns": int(opened.st_mtime_ns),
                            "ctime_ns": int(opened.st_ctime_ns),
                        }
                    )
                else:
                    raise ClosureBenchmarkError("E0-U runtime root is not regular")
            records.sort(key=lambda item: cast(str, item["path"]))
            distribution_records.append(
                {
                    "name": distribution,
                    "roots": list(roots),
                    "record_count": len(records),
                    "records_sha256": _sha256_bytes(_canonical_json_bytes(records)),
                    "wheel_record": _validate_runtime_distribution_record(
                        distribution,
                        roots,
                        records,
                        purelib=purelib,
                    ),
                }
            )
    finally:
        os.close(purelib_fd)
    return {
        "schema_version": "closure_sealed_runtime_environment_v1",
        "sealed_launch_command": SEALED_BATCH_LAUNCH_COMMAND,
        "sealed_python_argv": list(SEALED_BATCH_PYTHON_ARGV),
        "process_environment": _exact_process_environment(),
        "env_executable": _env_executable_record(),
        "git_executable": _git_executable_record(),
        "git_https_helper": _https_helper_record(),
        "git_config": _git_config_record(),
        "python_implementation": sys.implementation.name,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_executable": python_record,
        "purelib_path": purelib.as_posix(),
        "purelib_identity": {
            "device": int(purelib_metadata.st_dev),
            "inode": int(purelib_metadata.st_ino),
            "mode": stat.S_IMODE(purelib_metadata.st_mode),
            "nlink": int(purelib_metadata.st_nlink),
            "mtime_ns": int(purelib_metadata.st_mtime_ns),
            "ctime_ns": int(purelib_metadata.st_ctime_ns),
        },
        "purelib_top_level_count": len(top_level_records),
        "purelib_top_level_sha256": _sha256_bytes(
            _canonical_json_bytes(top_level_records)
        ),
        "distribution_count": len(distribution_records),
        "distributions": distribution_records,
        "distributions_sha256": _sha256_bytes(
            _canonical_json_bytes(distribution_records)
        ),
        "import_roots": sorted(RUNTIME_IMPORT_ROOTS),
        "site_imported": "site" in sys.modules,
        "pth_processing_performed": False,
    }


def _import_hook_identity(value: Any) -> dict[str, str]:
    return {
        "module": str(getattr(value, "__module__", type(value).__module__)),
        "qualname": str(getattr(value, "__qualname__", type(value).__qualname__)),
    }


def _bootstrap_import_state_record() -> dict[str, Any]:
    return {
        "meta_path": [_import_hook_identity(value) for value in sys.meta_path],
        "path_hooks": [_import_hook_identity(value) for value in sys.path_hooks],
        "importer_cache": [
            {
                "path": str(path),
                "finder": (
                    None if finder is None else _import_hook_identity(finder)
                ),
            }
            for path, finder in sorted(
                sys.path_importer_cache.items(), key=lambda item: str(item[0])
            )
        ],
        "pycache_prefix": sys.pycache_prefix,
    }


def _path_is_within(path: Path, roots: Sequence[Path]) -> bool:
    absolute = path if path.is_absolute() else Path("/") / path
    resolved = absolute.resolve(strict=False)
    for root in roots:
        resolved_root = root.resolve(strict=False)
        lexical_inside = absolute == root or root in absolute.parents
        resolved_inside = resolved == resolved_root or resolved_root in resolved.parents
        if lexical_inside and resolved_inside:
            return True
    return False


class _SealedRuntimeImportGuard:
    def __init__(
        self,
        *,
        builtin_importer: Any,
        frozen_importer: Any,
        path_finder: Any,
        source_file_loader: type[Any],
        extension_file_loader: type[Any],
        namespace_loader: type[Any],
        zip_importer: type[Any],
        purelib: Path,
    ) -> None:
        self._builtin_importer = builtin_importer
        self._frozen_importer = frozen_importer
        self._path_finder = path_finder
        self._loader_types = (
            source_file_loader,
            extension_file_loader,
            namespace_loader,
            zip_importer,
        )
        self._purelib = purelib
        self._stdlib_roots = tuple(Path(value) for value in BOOTSTRAP_SYS_PATH)
        runtime_locations: dict[str, tuple[Path, ...]] = {}
        for root in RUNTIME_IMPORT_ROOTS:
            candidates = tuple(
                purelib / relative
                for roots in RUNTIME_DISTRIBUTION_ROOTS.values()
                for relative in roots
                if relative == root or relative == f"{root}.py"
            )
            if not candidates:
                raise ClosureBenchmarkError(
                    f"E0-U runtime import root has no sealed location: {root}"
                )
            runtime_locations[root] = candidates
        self._runtime_locations = MappingProxyType(runtime_locations)

    @staticmethod
    def _spec_locations(spec: Any) -> tuple[str, ...]:
        locations: list[str] = []
        origin = getattr(spec, "origin", None)
        if isinstance(origin, str) and origin not in {"built-in", "frozen"}:
            locations.append(origin)
        search = getattr(spec, "submodule_search_locations", None)
        if search is not None:
            for raw in search:
                if type(raw) is not str:
                    raise ModuleNotFoundError("E0-U runtime import location is malformed")
                locations.append(raw)
        return tuple(locations)

    def find_spec(
        self,
        fullname: str,
        path: Any = None,
        target: Any = None,
    ) -> Any:
        root = fullname.partition(".")[0]
        runtime_root = root in RUNTIME_IMPORT_ROOTS
        stdlib_root = (
            root in RUNTIME_STDLIB_IMPORT_ROOTS
            or root in STDLIB_DYNAMIC_IMPORT_ROOTS
        )
        if not runtime_root and not stdlib_root:
            raise ModuleNotFoundError(
                f"E0-U runtime import escaped sealed closure: {fullname}",
                name=fullname,
            )
        spec = self._builtin_importer.find_spec(fullname, path, target)
        if spec is None:
            spec = self._frozen_importer.find_spec(fullname, path, target)
        if spec is not None:
            if runtime_root or _import_hook_identity(spec.loader) not in BOOTSTRAP_META_PATH[:2]:
                raise ModuleNotFoundError(
                    f"E0-U built-in/frozen import escaped sealed stdlib: {fullname}",
                    name=fullname,
                )
            return spec
        spec = self._path_finder.find_spec(fullname, path, target)
        if spec is None:
            if root == "six" and (
                fullname == "six.moves" or fullname.startswith("six.moves.")
            ) and (
                len(sys.meta_path) == 5
                and sys.meta_path[0] is self
                and tuple(_import_hook_identity(value) for value in sys.meta_path[1:4])
                == BOOTSTRAP_META_PATH
                and _import_hook_identity(sys.meta_path[4])
                == {"module": "six", "qualname": "_SixMetaPathImporter"}
                and isinstance(sys.modules.get("six"), ModuleType)
                and getattr(sys.modules["six"], "_importer", None) is sys.meta_path[4]
                and type(sys.meta_path[4])
                is getattr(sys.modules["six"], "_SixMetaPathImporter", None)
            ):
                # The sealed six.py bytes install the only permitted synthetic
                # meta-path importer, whose exact identity is recaptured below.
                return None
            raise ModuleNotFoundError(
                f"E0-U sealed runtime import is unavailable: {fullname}",
                name=fullname,
            )
        locations = self._spec_locations(spec)
        if not locations and getattr(spec, "origin", None) not in {"built-in", "frozen"}:
            raise ModuleNotFoundError(
                f"E0-U sealed runtime import has no physical origin: {fullname}",
                name=fullname,
            )
        roots = (
            self._runtime_locations[root]
            if runtime_root
            else self._stdlib_roots
        )
        loader = getattr(spec, "loader", None)
        loader_path = getattr(loader, "path", None)
        namespace_spec = (
            loader is None
            and getattr(spec, "origin", None) is None
            and bool(getattr(spec, "submodule_search_locations", None))
        )
        if any(
            location.endswith((".pyc", ".pyo"))
            or not _path_is_within(Path(location), roots)
            or (stdlib_root and _path_is_within(Path(location), (self._purelib,)))
            for location in locations
        ) or (not namespace_spec and type(loader) not in self._loader_types) or (
            loader_path is not None
            and (
                type(loader_path) is not str
                or not locations
                or Path(loader_path) != Path(locations[0])
            )
        ):
            raise ModuleNotFoundError(
                f"E0-U runtime import origin escaped sealed roots: {fullname}",
                name=fullname,
            )
        return spec


def _install_sealed_source_namespaces() -> None:
    created: dict[str, ModuleType] = {}
    for name in ("src", "src.experiments", "src.reporting", "src.mifal"):
        if name in sys.modules:
            raise ClosureBenchmarkError("E0-U source namespace existed before activation")
        module = ModuleType(name)
        module.__package__ = name
        module.__loader__ = None
        module.__dict__["__path__"] = ()
        created[name] = module
        sys.modules[name] = module
    created["src"].__dict__["experiments"] = created["src.experiments"]
    created["src"].__dict__["reporting"] = created["src.reporting"]
    created["src"].__dict__["mifal"] = created["src.mifal"]
    authority = sys.modules.get(E0_U_AUTHORITY_MODULE)
    if not isinstance(authority, ModuleType):
        raise ClosureBenchmarkError("E0-U authority module disappeared before activation")
    created["src.experiments"].__dict__["closure_e0_u_authority"] = authority


def _pycache_blocker_record() -> dict[str, int]:
    try:
        null_device = os.lstat(SEALED_PYCACHE_PREFIX.parent)
        os.lstat(SEALED_PYCACHE_PREFIX)
    except OSError as exc:
        if exc.filename == SEALED_PYCACHE_PREFIX.as_posix() and exc.errno in {2, 20}:
            pass
        else:
            raise ClosureBenchmarkError("E0-U sealed pycache blocker is unreadable") from exc
    else:
        raise ClosureBenchmarkError("E0-U sealed pycache path unexpectedly exists")
    if (
        not stat.S_ISCHR(null_device.st_mode)
        or stat.S_IMODE(null_device.st_mode) != 0o666
        or null_device.st_nlink != 1
        or null_device.st_uid != GIT_EXECUTABLE_UID
        or null_device.st_gid != GIT_EXECUTABLE_GID
        or null_device.st_rdev != os.makedev(1, 3)
    ):
        raise ClosureBenchmarkError("E0-U sealed pycache blocker device drifted")
    return {
        "device": int(null_device.st_dev),
        "inode": int(null_device.st_ino),
        "mode": stat.S_IMODE(null_device.st_mode),
        "nlink": int(null_device.st_nlink),
        "uid": int(null_device.st_uid),
        "gid": int(null_device.st_gid),
        "rdev": int(null_device.st_rdev),
        "mtime_ns": int(null_device.st_mtime_ns),
        "ctime_ns": int(null_device.st_ctime_ns),
    }


def _activate_sealed_runtime_environment(authority: Mapping[str, Any]) -> dict[str, Any]:
    if "site" in sys.modules:
        raise ClosureBenchmarkError("E0-U site was imported before runtime activation")
    baseline = _runtime_environment_record()
    if authority.get(E0_U_RUNTIME_ENVIRONMENT_RECORD_KEY) != baseline:
        raise ClosureBenchmarkError("E0-U runtime environment authority binding drifted")
    baseline["bootstrap_import_state"] = _bootstrap_import_state_record()
    purelib = cast(str, baseline["purelib_path"])
    if purelib in sys.path or any(
        "site-packages" in Path(value).parts for value in sys.path if isinstance(value, str)
    ):
        raise ClosureBenchmarkError("E0-U purelib was active before authority")
    if any(
        type(path) is not str
        or _path_is_within(Path(path), (Path(purelib),))
        for path in sys.path_importer_cache
    ):
        raise ClosureBenchmarkError("E0-U purelib importer cache existed before activation")
    if tuple(_import_hook_identity(value) for value in sys.meta_path) != BOOTSTRAP_META_PATH:
        raise ClosureBenchmarkError("E0-U bootstrap meta_path drifted")
    pycache_blocker = _pycache_blocker_record()
    sys.pycache_prefix = SEALED_PYCACHE_PREFIX.as_posix()
    from importlib.machinery import (
        BuiltinImporter,
        ExtensionFileLoader,
        FileFinder,
        FrozenImporter,
        NamespaceLoader,
        PathFinder,
        SourceFileLoader,
    )
    from zipimport import zipimporter

    guard = _SealedRuntimeImportGuard(
        builtin_importer=BuiltinImporter,
        frozen_importer=FrozenImporter,
        path_finder=PathFinder,
        source_file_loader=SourceFileLoader,
        extension_file_loader=ExtensionFileLoader,
        namespace_loader=NamespaceLoader,
        zip_importer=zipimporter,
        purelib=Path(purelib),
    )
    sys.meta_path.insert(0, guard)
    hooks = tuple(sys.path_hooks)
    importer_cache = dict(sys.path_importer_cache)
    original_path = tuple(sys.path)
    sys.path.append(purelib)
    _install_sealed_source_namespaces()
    module_objects = dict(sys.modules)
    if "site" in sys.modules:
        raise ClosureBenchmarkError("E0-U site or .pth processing occurred")
    return {
        "record": baseline,
        "guard": guard,
        "meta_path": tuple(sys.meta_path),
        "path_hooks": hooks,
        "importer_cache": importer_cache,
        "file_finder_class": FileFinder,
        "module_objects": module_objects,
        "bootstrap_paths": original_path,
        "sys_path": (*original_path, purelib),
        "pycache_prefix": SEALED_PYCACHE_PREFIX.as_posix(),
        "pycache_blocker": pycache_blocker,
    }


def _sealed_six_importer() -> Any | None:
    module = sys.modules.get("six")
    if not isinstance(module, ModuleType):
        return None
    importer_class = getattr(module, "_SixMetaPathImporter", None)
    importer = getattr(module, "_importer", None)
    if not isinstance(importer_class, type) or type(importer) is not importer_class:
        raise ClosureBenchmarkError("E0-U sealed six importer identity drifted")
    return importer


def _recapture_runtime_environment(state: Mapping[str, Any]) -> None:
    baseline = state.get("record")
    guard = state.get("guard")
    if not isinstance(baseline, Mapping) or not isinstance(
        guard, _SealedRuntimeImportGuard
    ):
        raise ClosureBenchmarkError("E0-U runtime recapture state is malformed")
    observed = _runtime_environment_record()
    observed["bootstrap_import_state"] = baseline.get("bootstrap_import_state")
    current_meta = tuple(sys.meta_path)
    sealed_meta = cast(tuple[Any, ...], state.get("meta_path"))
    extra_meta = current_meta[len(sealed_meta) :]
    six_importer = _sealed_six_importer()
    if (
        observed != dict(baseline)
        or "site" in sys.modules
        or tuple(sys.path) != tuple(state.get("sys_path", ()))
        or tuple(sys.path_hooks) != tuple(state.get("path_hooks", ()))
        or sys.pycache_prefix != state.get("pycache_prefix")
        or _pycache_blocker_record() != state.get("pycache_blocker")
        or current_meta[: len(sealed_meta)] != sealed_meta
        or len(extra_meta) > 1
        or (bool(extra_meta) != (six_importer is not None))
        or (extra_meta and extra_meta[0] is not six_importer)
    ):
        raise ClosureBenchmarkError("E0-U sealed runtime environment changed")
    module_objects = state.get("module_objects")
    if type(module_objects) is not dict or any(
        name not in sys.modules or sys.modules[name] is not module
        for name, module in module_objects.items()
    ):
        raise ClosureBenchmarkError("E0-U preexisting module identity drifted")
    component_modules = {component.module_name for component in BATCH_COMPONENTS}
    sealed_source_modules = {
        "src",
        "src.experiments",
        "src.reporting",
        "src.mifal",
        E0_U_AUTHORITY_MODULE,
        E0_U_CONTEXT_BUILDER_MODULE,
        *(cast(str, spec["module_name"]) for spec in SEALED_SUPPORT_SOURCES),
        *component_modules,
    }
    allowed_new_roots = (
        RUNTIME_IMPORT_ROOTS
        | RUNTIME_STDLIB_IMPORT_ROOTS
        | STDLIB_DYNAMIC_IMPORT_ROOTS
    )
    purelib = Path(cast(str, baseline["purelib_path"]))
    for name, module in tuple(sys.modules.items()):
        if name in module_objects:
            continue
        root = name.partition(".")[0]
        origin = getattr(module, "__file__", None)
        injected_runtime_module = name in RUNTIME_INJECTED_MODULE_NAMES and (
            (name == "__mp_main__" and module is sys.modules.get("__main__"))
            or (
                name in {"cython_runtime", "_cython_3_2_2", "_cython_3_2_4"}
                and origin is None
            )
            or (
                type(origin) is str
                and origin.endswith(".so")
                and _path_is_within(Path(origin), (purelib,))
            )
        )
        if (
            not isinstance(module, ModuleType)
            or (
                name not in sealed_source_modules
                and root not in allowed_new_roots
                and not injected_runtime_module
            )
        ):
            raise ClosureBenchmarkError(
                f"E0-U runtime module escaped the sealed closure: {name}"
            )
        module_objects[name] = module
    original_cache = cast(Mapping[Any, Any], state.get("importer_cache"))
    if type(original_cache) is not dict:
        raise ClosureBenchmarkError("E0-U importer cache seal is malformed")
    if any(
        path not in sys.path_importer_cache
        or sys.path_importer_cache[path] is not finder
        for path, finder in original_cache.items()
    ):
        raise ClosureBenchmarkError("E0-U existing importer cache entry drifted")
    bootstrap_paths = tuple(
        Path(value) for value in cast(tuple[str, ...], state.get("bootstrap_paths"))
    )
    allowed_roots = {
        root
        for roots in RUNTIME_DISTRIBUTION_ROOTS.values()
        for root in roots
    }
    for raw_path, finder in sys.path_importer_cache.items():
        path = str(raw_path)
        if raw_path in original_cache:
            continue
        candidate = Path(path)
        try:
            relative = candidate.relative_to(purelib)
        except ValueError:
            if not _path_is_within(candidate, bootstrap_paths):
                raise ClosureBenchmarkError(
                    "E0-U importer cache escaped sealed runtime roots"
                )
        else:
            if relative.parts and relative.parts[0] not in allowed_roots:
                raise ClosureBenchmarkError(
                    "E0-U importer cache entered an unsealed root"
                )
        file_finder_class = state.get("file_finder_class")
        if finder is not None and type(finder) is not file_finder_class:
            raise ClosureBenchmarkError("E0-U importer cache finder drifted")
        cast(dict[Any, Any], original_cache)[raw_path] = finder


def runner_source_record(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Return the source record that the formal E0-M lock must seal."""

    root = PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()
    payload, metadata = _read_regular_source(SCRIPT_PATH, repo_root=root)
    return {
        **_source_identity_record(SCRIPT_PATH, payload, metadata),
        "contract_sha256": sealed_batch_contract_sha256(),
        "sealed_command": SEALED_BATCH_COMMAND,
    }


def validate_runner_source_record(
    record: Mapping[str, Any], *, repo_root: Path | None = None
) -> dict[str, Any]:
    observed = runner_source_record(repo_root=repo_root)
    if dict(record) != observed:
        raise ClosureBenchmarkError("E0-M batch runner source record drifted")
    return observed


def _component_source_record(
    component: BatchComponent, *, repo_root: Path
) -> dict[str, Any]:
    relative_path = Path(component.source_path)
    try:
        payload, metadata = _read_regular_source(relative_path, repo_root=repo_root)
        decoded = payload.decode("utf-8")
        tree = ast.parse(decoded, filename=component.source_path)
    except (ClosureBenchmarkError, UnicodeDecodeError, SyntaxError) as exc:
        return {
            "component_id": component.component_id,
            "stage_id": component.stage_id,
            "source_path": component.source_path,
            "status": "missing_or_invalid",
            "reason": type(exc).__name__,
        }
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing_apis = sorted(
        {component.preflight_api, component.execute_api}.difference(functions)
    )
    identity = _source_identity_record(relative_path, payload, metadata)
    return {
        "component_id": component.component_id,
        "stage_id": component.stage_id,
        "module_name": component.module_name,
        "source_path": component.source_path,
        "bytes": identity["bytes"],
        "sha256": identity["sha256"],
        "mode": identity["mode"],
        "nlink": identity["nlink"],
        "required_apis": [component.preflight_api, component.execute_api],
        "missing_apis": missing_apis,
        "status": "ready" if not missing_apis else "missing_required_api",
    }


def _context_builder_source_record(*, repo_root: Path) -> dict[str, Any]:
    try:
        payload, metadata = _read_regular_source(
            E0_U_CONTEXT_BUILDER_PATH, repo_root=repo_root
        )
        tree = ast.parse(
            payload.decode("utf-8"),
            filename=E0_U_CONTEXT_BUILDER_PATH.as_posix(),
        )
    except (ClosureBenchmarkError, UnicodeDecodeError, SyntaxError) as exc:
        return {
            "support_id": "phase3_context_builder",
            "module_name": E0_U_CONTEXT_BUILDER_MODULE,
            "source_path": E0_U_CONTEXT_BUILDER_PATH.as_posix(),
            "required_api": E0_U_CONTEXT_BUILDER_API,
            "status": "missing_or_invalid",
            "reason": type(exc).__name__,
        }
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    identity = _source_identity_record(
        E0_U_CONTEXT_BUILDER_PATH, payload, metadata
    )
    present = {
        E0_U_CONTEXT_BUILDER_API,
        E0_U_CONTEXT_PREFLIGHT_API,
    }.issubset(functions)
    return {
        "support_id": "phase3_context_builder",
        "module_name": E0_U_CONTEXT_BUILDER_MODULE,
        "source_path": E0_U_CONTEXT_BUILDER_PATH.as_posix(),
        "bytes": identity["bytes"],
        "sha256": identity["sha256"],
        "mode": identity["mode"],
        "nlink": identity["nlink"],
        "required_api": E0_U_CONTEXT_BUILDER_API,
        "status": "ready" if present else "missing_required_api",
    }


def _support_source_record(
    spec: Mapping[str, Any], *, repo_root: Path
) -> dict[str, Any]:
    relative_path = Path(cast(str, spec["source_path"]))
    required_symbols = tuple(cast(Sequence[str], spec["required_symbols"]))
    try:
        payload, metadata = _read_regular_source(relative_path, repo_root=repo_root)
        tree = ast.parse(payload.decode("utf-8"), filename=relative_path.as_posix())
    except (ClosureBenchmarkError, UnicodeDecodeError, SyntaxError) as exc:
        return {
            "support_id": spec["support_id"],
            "module_name": spec["module_name"],
            "source_path": relative_path.as_posix(),
            "required_symbols": list(required_symbols),
            "status": "missing_or_invalid",
            "reason": type(exc).__name__,
        }
    symbols = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    missing = sorted(set(required_symbols).difference(symbols))
    identity = _source_identity_record(relative_path, payload, metadata)
    return {
        "support_id": spec["support_id"],
        "module_name": spec["module_name"],
        "source_path": relative_path.as_posix(),
        "bytes": identity["bytes"],
        "sha256": identity["sha256"],
        "mode": identity["mode"],
        "nlink": identity["nlink"],
        "required_symbols": list(required_symbols),
        "missing_symbols": missing,
        "status": "ready" if not missing else "missing_required_symbol",
    }


def _execute_sealed_source_module(
    *,
    module_name: str,
    source_path: Path,
    repo_root: Path,
    expected_source_record: Mapping[str, Any],
) -> tuple[ModuleType, dict[str, Any]]:
    """Execute one exact source file directly, never consulting import caches."""

    payload, metadata = _read_regular_source(source_path, repo_root=repo_root)
    observed = _source_identity_record(source_path, payload, metadata)
    _require_source_identity(
        expected_source_record,
        observed,
        context=module_name,
    )
    if module_name == E0_U_AUTHORITY_MODULE:
        _require_stdlib_only_authority_source(payload)
    try:
        code = compile(payload, source_path.as_posix(), "exec", dont_inherit=True)
    except (SyntaxError, ValueError) as exc:
        raise ClosureBenchmarkError(
            f"E0-U sealed source cannot be compiled: {module_name}"
        ) from exc
    module = ModuleType(module_name)
    module.__file__ = (repo_root / source_path).as_posix()
    module.__package__ = module_name.rpartition(".")[0]
    module.__loader__ = None
    module.__dict__["__cached__"] = None
    if module_name == E0_U_AUTHORITY_MODULE:
        module.__dict__["__builtins__"] = _sealed_authority_builtins()
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except BaseException as exc:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise ClosureBenchmarkError(
            f"E0-U sealed source execution failed: {module_name}"
        ) from exc
    recaptured_payload, recaptured_metadata = _read_regular_source(
        source_path, repo_root=repo_root
    )
    recaptured = _source_identity_record(
        source_path, recaptured_payload, recaptured_metadata
    )
    if recaptured != observed or recaptured_payload != payload:
        raise ClosureBenchmarkError(
            f"E0-U sealed source changed during execution: {module_name}"
        )
    parent_name, _, child_name = module_name.rpartition(".")
    parent = sys.modules.get(parent_name)
    if (
        isinstance(parent, ModuleType)
        and parent.__dict__.get("__path__") == ()
    ):
        parent.__dict__[child_name] = module
    return module, observed


def collect_sealed_batch_component_readiness(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    """Inspect source contracts only; never import a scientific component."""

    root = PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()
    records = [
        _component_source_record(component, repo_root=root)
        for component in BATCH_COMPONENTS
    ]
    context_builder_record = _context_builder_source_record(repo_root=root)
    support_records = [
        _support_source_record(spec, repo_root=root)
        for spec in SEALED_SUPPORT_SOURCES
    ]
    missing: list[dict[str, Any]] = []
    if not callable(globals().get(INTERNAL_E1_EXECUTOR_API)):
        missing.append(
            {
                "component_id": "E1_benchmark_scientific_executor",
                "stage_id": "E1",
                "reason": f"missing internal API {INTERNAL_E1_EXECUTOR_API}",
            }
        )
    missing.extend(
        {
            "component_id": record["component_id"],
            "stage_id": record["stage_id"],
            "reason": record["status"],
        }
        for record in records
        if record["status"] != "ready"
    )
    if context_builder_record["status"] != "ready":
        missing.append(
            {
                "component_id": "phase3_context_builder",
                "stage_id": "E0-U",
                "reason": context_builder_record["status"],
            }
        )
    missing.extend(
        {
            "component_id": record["support_id"],
            "stage_id": "E0-U",
            "reason": record["status"],
        }
        for record in support_records
        if record["status"] != "ready"
    )
    return {
        "status": (
            "sealed_batch_components_ready"
            if not missing
            else "sealed_batch_components_incomplete"
        ),
        "component_count": 1 + len(BATCH_COMPONENTS),
        "external_component_count": len(BATCH_COMPONENTS),
        "ready_external_component_count": sum(
            record["status"] == "ready" for record in records
        ),
        "missing_component_count": len(missing),
        "missing_components": missing,
        "component_source_records": records,
        "context_builder_source_record": context_builder_record,
        "support_source_records": support_records,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


def collect_e0_u_activation_material(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    """Capture the outcome-free material sealed by the future E0-U activation.

    This API is intended for the data-only activation writer.  It must be
    called from the same isolated, ``-S`` and sanitized Python runtime used by
    the sealed batch so that the runtime record is byte-for-byte comparable at
    execution time.  It never resolves an outcome path and performs no writes.
    """

    root = PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()
    if root != PROJECT_ROOT:
        raise ClosureBenchmarkError("E0-U activation material repository drifted")
    source_before = runner_source_record(repo_root=root)
    readiness_before = collect_sealed_batch_component_readiness(repo_root=root)
    if readiness_before["missing_component_count"] != 0:
        raise ClosureBenchmarkError(
            "E0-U activation material cannot seal incomplete components"
        )
    runtime_environment = _runtime_environment_record()
    source_after = runner_source_record(repo_root=root)
    readiness_after = collect_sealed_batch_component_readiness(repo_root=root)
    if source_after != source_before or readiness_after != readiness_before:
        raise ClosureBenchmarkError(
            "E0-U activation sources changed during material capture"
        )
    heavy = sorted(
        path
        for path, format_name in EXPECTED_ARTIFACT_FORMATS.items()
        if format_name == "parquet"
    )
    direct = sorted(set(EXPECTED_ARTIFACT_PATHS).difference(heavy))
    if len(heavy) != 4 or len(direct) != 48:
        raise ClosureBenchmarkError("E0-U activation DVC partition drifted")
    return {
        "status": "e0_u_activation_material_ready",
        "runner_source_record": source_before,
        "component_source_records": readiness_before["component_source_records"],
        "context_builder_source_record": readiness_before[
            "context_builder_source_record"
        ],
        "support_source_records": readiness_before["support_source_records"],
        "runtime_environment_record": runtime_environment,
        "sealed_batch_contract_sha256": sealed_batch_contract_sha256(),
        "expected_artifact_paths_sha256": EXPECTED_ARTIFACT_PATHS_SHA256,
        "expected_publication_order_sha256": EXPECTED_PUBLICATION_ORDER_SHA256,
        "dvc_policy": {
            "direct_git_artifact_paths": direct,
            "dvc_pointer_paths": sorted(path + ".dvc" for path in heavy),
            "heavy_artifact_paths": heavy,
            "dvc_add_after_success_only": True,
            "dvc_push_after_audit_only": True,
            "implicit_dvc_forbidden": True,
        },
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


def _load_e0_u_authority_module(
    expected_source_record: Mapping[str, Any],
) -> tuple[ModuleType, dict[str, Any]]:
    """Load E0-U itself from exact source bytes without importlib or pyc."""

    try:
        return _execute_sealed_source_module(
            module_name=E0_U_AUTHORITY_MODULE,
            source_path=E0_U_AUTHORITY_PATH,
            repo_root=PROJECT_ROOT,
            expected_source_record=expected_source_record,
        )
    except ClosureBenchmarkError as exc:
        raise ClosureBenchmarkError(
            "E0-U authority is not published or its exact source cannot be loaded; "
            "sealed batch execution is forbidden"
        ) from exc


def _validate_authority_commit_bindings(
    authority: Mapping[str, Any],
    authority_source_record: Mapping[str, Any],
) -> dict[str, str]:
    """Reconstruct and validate the exact historical R -> H -> P -> U chain."""

    observed_head = authority_source_record.get("git_head")
    if type(observed_head) is not str:
        raise ClosureBenchmarkError("E0-U authority activation commit is absent")
    expected = {
        "historical_e0_m_commit": _git_oid_output(
            _sealed_git("rev-parse", "--verify", "HEAD~3^{commit}"),
            context="historical E0-M commit",
        ),
        "phase3_code_commit": _git_oid_output(
            _sealed_git("rev-parse", "--verify", "HEAD~2^{commit}"),
            context="Phase 3 code commit",
        ),
        "phase3_evidence_commit": _git_oid_output(
            _sealed_git("rev-parse", "--verify", "HEAD~1^{commit}"),
            context="Phase 3 evidence commit",
        ),
        "phase3_activation_commit": _git_oid_output(
            _sealed_git("rev-parse", "--verify", "HEAD^{commit}"),
            context="Phase 3 activation commit",
        ),
    }
    if (
        expected["historical_e0_m_commit"] != HISTORICAL_E0_M_COMMIT
        or expected["phase3_activation_commit"] != observed_head
        or len(set(expected.values())) != 4
    ):
        raise ClosureBenchmarkError("E0-U authority R-H-P-U topology drifted")
    for key in E0_U_COMMIT_BINDING_KEYS:
        value = authority.get(key)
        if (
            type(value) is not str
            or len(value) != 40
            or any(character not in "0123456789abcdef" for character in value)
            or value != expected[key]
        ):
            raise ClosureBenchmarkError(
                f"E0-U authority commit binding drifted: {key}"
            )
    return expected


def _require_clean_repository_snapshot_before_outcome_log(
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    """Recapture the published U topology and a clean tree immediately pre-open."""

    activation_commit = authority.get("phase3_activation_commit")
    if (
        type(activation_commit) is not str
        or len(activation_commit) != 40
        or any(character not in "0123456789abcdef" for character in activation_commit)
    ):
        raise ClosureBenchmarkError(
            "E0-U activation commit is malformed before outcome logging"
        )

    def capture() -> dict[str, Any]:
        refs = {
            name: _git_oid_output(
                _sealed_git("rev-parse", "--verify", f"{name}^{{commit}}"),
                context=f"{name} pre-outcome-log recapture",
            )
            for name in (
                "HEAD",
                "refs/heads/main",
                "refs/remotes/origin/main",
                "refs/remotes/origin/HEAD",
            )
        }
        try:
            head_ref = _sealed_git(
                "symbolic-ref", "--quiet", "HEAD"
            ).decode("ascii")
            origin_head_ref = _sealed_git(
                "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"
            ).decode("ascii")
        except UnicodeDecodeError as exc:
            raise ClosureBenchmarkError(
                "E0-U symbolic refs are not ASCII before outcome logging"
            ) from exc
        status = _sealed_git(
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        )
        return {
            "refs": refs,
            "head_ref": head_ref,
            "origin_head_ref": origin_head_ref,
            "status": status,
        }

    first = capture()
    second = capture()
    if first != second:
        raise ClosureBenchmarkError(
            "E0-U repository changed during the final pre-outcome-log snapshot"
        )
    refs = cast(dict[str, str], second["refs"])
    if (
        set(refs.values()) != {activation_commit}
        or second["head_ref"] != "refs/heads/main\n"
        or second["origin_head_ref"] != "refs/remotes/origin/main\n"
        or second["status"] != b""
    ):
        raise ClosureBenchmarkError(
            "E0-U repository is not published and clean immediately before outcome logging"
        )
    return {
        "phase3_activation_commit": activation_commit,
        "refs_aligned": True,
        "head_ref": "refs/heads/main",
        "origin_head_ref": "refs/remotes/origin/main",
        "worktree_clean": True,
        "index_clean": True,
        "untracked_paths_absent": True,
        "double_recapture_equal": True,
    }


def _require_e0_u_authority_first(
    expected_source_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Perform the mandatory first sealed-execution operation."""

    _require_sealed_startup_environment()
    _require_no_preactivated_runtime()
    module, observed_physical_source = _load_e0_u_authority_module(
        expected_source_record
    )
    _require_sealed_startup_environment()
    _require_no_preactivated_runtime()
    _require_source_identity(
        expected_source_record,
        observed_physical_source,
        context=E0_U_AUTHORITY_MODULE,
    )
    require = getattr(module, E0_U_AUTHORITY_API, None)
    if not callable(require):
        raise ClosureBenchmarkError("E0-U authority API is absent")
    try:
        raw = require(verify_remote=True, repo_root=PROJECT_ROOT)
    except BaseException as exc:
        raise ClosureBenchmarkError("E0-U authority rejected sealed execution") from exc
    _require_sealed_startup_environment()
    _require_no_preactivated_runtime()
    if not isinstance(raw, Mapping):
        raise ClosureBenchmarkError("E0-U authority result is not a mapping")
    authority = dict(raw)
    if set(authority) != E0_U_AUTHORITY_RESULT_KEYS:
        raise ClosureBenchmarkError("E0-U authority result keys drifted")
    expected = {
        "gate": UNBLINDING_GATE,
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
    }
    for key, value in expected.items():
        if type(authority.get(key)) is not type(value) or authority.get(key) != value:
            raise ClosureBenchmarkError(f"E0-U authority field drifted: {key}")
    _validate_authority_commit_bindings(authority, expected_source_record)
    if authority.get("sealed_batch_command") != SEALED_BATCH_COMMAND:
        raise ClosureBenchmarkError("E0-U authority sealed command drifted")
    if authority.get(E0_U_AUTHORITY_SOURCE_RECORD_KEY) != dict(expected_source_record):
        raise ClosureBenchmarkError("E0-U authority Git source binding drifted")
    git_record = _git_executable_record()
    if authority.get(E0_U_GIT_EXECUTABLE_RECORD_KEY) != git_record:
        raise ClosureBenchmarkError("E0-U authority Git executable binding drifted")
    env_record = _env_executable_record()
    if authority.get(E0_U_ENV_EXECUTABLE_RECORD_KEY) != env_record:
        raise ClosureBenchmarkError("E0-U authority env executable binding drifted")
    if _git_bound_e0_u_authority_source_record() != dict(expected_source_record):
        raise ClosureBenchmarkError("E0-U authority repository binding changed during require")
    context_builder_record = _context_builder_source_record(repo_root=PROJECT_ROOT)
    if (
        context_builder_record.get("status") != "ready"
        or authority.get(E0_U_CONTEXT_BUILDER_SOURCE_RECORD_KEY)
        != context_builder_record
    ):
        raise ClosureBenchmarkError(
            "E0-U authority context-builder binding drifted"
        )
    support_source_records = [
        _support_source_record(spec, repo_root=PROJECT_ROOT)
        for spec in SEALED_SUPPORT_SOURCES
    ]
    if (
        any(record.get("status") != "ready" for record in support_source_records)
        or authority.get(E0_U_SUPPORT_SOURCE_RECORDS_KEY)
        != support_source_records
    ):
        raise ClosureBenchmarkError("E0-U authority support-source binding drifted")
    overlay_validator = getattr(module, "_validate_phase3_overlay_bundle", None)
    if not callable(overlay_validator):
        raise ClosureBenchmarkError("E0-U authority overlay validator is absent")
    try:
        overlay_record = _validate_phase3_overlay_record(
            overlay_validator(
                PROJECT_ROOT,
                authority["phase3_code_commit"],
                authority["phase3_evidence_commit"],
            )
        )
    except BaseException as exc:
        raise ClosureBenchmarkError(
            "E0-U authority Phase 3 overlay recapture failed"
        ) from exc
    for api_name in (
        E0_U_CONTEXT_FACTORY_API,
        E0_U_TRANSACTION_PUBLISHER_API,
        E0_U_PUBLICATION_AUDITOR_API,
    ):
        api = getattr(module, api_name, None)
        if not callable(api):
            raise ClosureBenchmarkError(f"E0-U authority API is absent: {api_name}")
        authority[api_name] = api
    authority["_observed_authority_source_record"] = dict(expected_source_record)
    authority["_observed_git_executable_record"] = git_record
    authority["_observed_env_executable_record"] = env_record
    authority["_observed_context_builder_source_record"] = context_builder_record
    authority["_observed_support_source_records"] = support_source_records
    authority[E0_U_PHASE3_OVERLAY_RECORD_KEY] = overlay_record
    return authority


def _public_authority_payload(authority: Mapping[str, Any]) -> dict[str, Any]:
    if set(authority) != E0_U_AUTHORITY_RESULT_KEYS | E0_U_AUTHORITY_INTERNAL_KEYS:
        raise ClosureBenchmarkError("E0-U internal authority keys drifted")
    return copy.deepcopy(
        {key: authority[key] for key in sorted(E0_U_AUTHORITY_RESULT_KEYS)}
    )


def check_only(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Validate the runner itself without opening outcomes or writing files."""

    root = PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()
    source_before = runner_source_record(repo_root=root)
    validate_sealed_batch_command(SEALED_BATCH_COMMAND)
    readiness = collect_sealed_batch_component_readiness(repo_root=root)
    source_after = runner_source_record(repo_root=root)
    if source_after != source_before:
        raise ClosureBenchmarkError("E0-M batch runner changed during check-only")
    execution_ready = readiness["missing_component_count"] == 0
    return {
        "gate": FORMAL_MODEL_LOCK_GATE,
        "status": (
            "sealed_batch_runner_ready_for_formal_lock"
            if execution_ready
            else "sealed_batch_runner_incomplete"
        ),
        "runner": source_before,
        "batch_contract_sha256": sealed_batch_contract_sha256(),
        "sealed_batch_command": SEALED_BATCH_COMMAND,
        "startup_contract": cast(
            dict[str, Any], json.loads(_canonical_json_bytes(STARTUP_CONTRACT))
        ),
        "component_readiness": readiness,
        "formal_model_lock_ready": execution_ready,
        "evaluator_available": execution_ready,
        "missing_component_count": readiness["missing_component_count"],
        "sealed_batch_execution_ready": execution_ready,
        "e0_u_authority_path": E0_U_AUTHORITY_PATH.as_posix(),
        "e0_u_authority_inspected": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "evaluation_authorized": False,
        "outcome_access_authorized": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


def _copy_dataframe_tables(value: Mapping[str, Any]) -> dict[str, Any]:
    # pandas is deliberately imported only after effective E0-U authority.
    import pandas as pd

    tables: dict[str, Any] = {}
    for key, frame in value.items():
        if type(key) is not str or not key or type(frame) is not pd.DataFrame:
            raise ClosureBenchmarkError("E0-U logical table binding drifted")
        tables[key] = frame.copy(deep=True)
    return tables


def _validate_opened_batch_context(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != BATCH_CONTEXT_KEYS:
        raise ClosureBenchmarkError("E0-U opened batch_context keys drifted")
    execution_id = raw.get("execution_id")
    if type(execution_id) is not str or not execution_id:
        raise ClosureBenchmarkError("E0-U execution_id is malformed")
    if type(raw.get("rng_seed")) is not int or raw.get("rng_seed") != RNG_SEED:
        raise ClosureBenchmarkError("E0-U batch RNG seed drifted")
    tables = raw.get("tables")
    stage_results = raw.get("stage_results")
    availability = raw.get("model_availability")
    software_evidence = raw.get("software_evidence")
    if not isinstance(tables, Mapping) or not isinstance(stage_results, Mapping):
        raise ClosureBenchmarkError("E0-U batch context mappings are malformed")
    if set(tables) != OPENED_CONTEXT_TABLES:
        raise ClosureBenchmarkError("E0-U opened logical table scope drifted")
    if stage_results:
        raise ClosureBenchmarkError("E0-U opened context contains precomputed stages")
    if not isinstance(availability, Mapping) or dict(availability) != dict(
        CURRENT_MODEL_AVAILABILITY
    ):
        raise ClosureBenchmarkError("E0-U model availability drifted")
    if not isinstance(software_evidence, Mapping) or set(software_evidence) != SOFTWARE_EVIDENCE_KEYS:
        raise ClosureBenchmarkError("E0-U software evidence keys drifted")
    software_evidence_copy: dict[str, Any] = {}
    for key, value in software_evidence.items():
        if type(key) is not str or not isinstance(value, (str, bytes, Mapping)):
            raise ClosureBenchmarkError("E0-U software evidence payload drifted")
        software_evidence_copy[key] = copy.deepcopy(value)
    return {
        "execution_id": execution_id,
        "rng_seed": RNG_SEED,
        "tables": _copy_dataframe_tables(tables),
        "stage_results": {},
        "model_availability": dict(CURRENT_MODEL_AVAILABILITY),
        "software_evidence": software_evidence_copy,
    }


def _exact_int_series(series: Any, *, label: str) -> Any:
    import numpy as np
    import pandas as pd

    numeric = pd.to_numeric(series, errors="raise")
    values = numeric.to_numpy(dtype="float64")
    if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise ClosureBenchmarkError(f"E1 {label} is not exact integer")
    return numeric.astype("int64")


def _require_exact_columns(frame: Any, columns: tuple[str, ...], *, label: str) -> None:
    if tuple(frame.columns) != columns:
        raise ClosureBenchmarkError(f"E1 {label} columns drifted")


def _require_text_columns(frame: Any, columns: Sequence[str], *, label: str) -> None:
    for column in columns:
        if frame[column].isna().any() or (frame[column].astype(str).str.len() == 0).any():
            raise ClosureBenchmarkError(f"E1 {label} text field drifted: {column}")
        frame[column] = frame[column].astype(str)


def _validate_origin_horizon_arithmetic(intent: Any) -> None:
    import pandas as pd

    try:
        origins = pd.PeriodIndex(intent["origin_year_month"].astype(str), freq="M")
        targets = pd.PeriodIndex(intent["target_year_month"].astype(str), freq="M")
    except BaseException as exc:
        raise ClosureBenchmarkError("E1 origin/target month dialect drifted") from exc
    horizons = intent["horizon_months"].to_numpy(dtype="int64")
    expected = pd.PeriodIndex(
        [origin + int(horizon) for origin, horizon in zip(origins, horizons, strict=True)],
        freq="M",
    )
    if not expected.equals(targets):
        raise ClosureBenchmarkError("E1 target month is not origin plus horizon")


def _normalize_e1_prediction_surface(tables: Mapping[str, Any]) -> Any:
    import numpy as np
    import pandas as pd

    for table_name in E1_INPUT_TABLES:
        if table_name not in tables or type(tables[table_name]) is not pd.DataFrame:
            raise ClosureBenchmarkError(f"E1 locked table is absent: {table_name}")
    predictions = tables["predictions_long"].copy(deep=True)
    intents = tables["intent_origins"].copy(deep=True)
    targets = tables["target_outcomes"].copy(deep=True)
    _require_exact_columns(predictions, E1_PREDICTION_COLUMNS, label="predictions")
    _require_exact_columns(intents, E1_INTENT_COLUMNS, label="intent origins")
    _require_exact_columns(targets, E1_TARGET_COLUMNS, label="target outcomes")
    if predictions.empty or intents.empty or targets.empty:
        raise ClosureBenchmarkError("E1 locked surface is empty")

    identity = [
        "source_id",
        "site_id",
        "common_origin_id",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
    ]
    target_identity = [
        "source_id",
        "site_id",
        "common_origin_id",
        "target_year_month",
        "horizon_months",
    ]
    _require_text_columns(
        predictions,
        [
            "source_id",
            "site_id",
            "common_origin_id",
            "origin_year_month",
            "target_year_month",
            "model_id",
            "terminal_status",
            *ENDPOINT_STATUS_COLUMNS,
        ],
        label="prediction",
    )
    _require_text_columns(
        intents,
        [
            "source_id",
            "site_id",
            "holdout_group_id",
            "common_origin_id",
            "origin_year_month",
            "target_year_month",
            "evaluation_cohort",
            "evaluation_role",
            "time_role",
        ],
        label="intent",
    )
    _require_text_columns(
        targets,
        ["source_id", "site_id", "common_origin_id", "target_year_month"],
        label="target",
    )
    for frame in (predictions, intents, targets):
        frame["horizon_months"] = _exact_int_series(
            frame["horizon_months"], label="horizon"
        )
        if not frame["horizon_months"].isin(HORIZONS_MONTHS).all():
            raise ClosureBenchmarkError("E1 horizon set drifted")
    predictions["model_seed"] = _exact_int_series(
        predictions["model_seed"], label="model seed"
    )
    predictions["seed_slot"] = _exact_int_series(
        predictions["seed_slot"], label="seed slot"
    )
    if not predictions["model_seed"].isin(REGISTERED_SEEDS).all() or not predictions[
        "seed_slot"
    ].isin(REGISTERED_SEEDS).all():
        raise ClosureBenchmarkError("E1 registered seed contract drifted")
    if not predictions["model_id"].isin(MODEL_IDS).all():
        raise ClosureBenchmarkError("E1 model registry drifted")
    if not predictions["terminal_status"].isin(TERMINAL_STATUSES).all():
        raise ClosureBenchmarkError("E1 terminal status drifted")
    if any(
        not predictions[column].isin(ENDPOINT_STATUSES).all()
        for column in ENDPOINT_STATUS_COLUMNS
    ):
        raise ClosureBenchmarkError("E1 endpoint terminal status drifted")
    if (
        not intents["source_id"].eq(EVALUATION_SOURCE_ID).all()
        or not intents["evaluation_cohort"].eq(EVALUATION_COHORT).all()
        or not intents["evaluation_role"].eq(EVALUATION_ROLE).all()
        or not intents["time_role"].eq(EVALUATION_TIME_ROLE).all()
    ):
        raise ClosureBenchmarkError("E1 locked holdout cohort/role/time binding drifted")
    if not intents["holdout_group_id"].eq(
        intents["source_id"].astype(str) + "::" + intents["site_id"].astype(str)
    ).all():
        raise ClosureBenchmarkError("E1 holdout-group derivation drifted")
    _validate_origin_horizon_arithmetic(intents)
    if intents.duplicated(identity).any() or targets.duplicated(target_identity).any():
        raise ClosureBenchmarkError("E1 locked intent/target keys are duplicated")
    origin_identity = [
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "origin_year_month",
    ]
    horizon_sets = intents.groupby(origin_identity, sort=True)["horizon_months"].apply(
        lambda values: set(values.astype("int64"))
    )
    if (
        len(intents) != LOCKED_INTENT_COUNT
        or len(horizon_sets) != LOCKED_BASE_ORIGIN_COUNT
        or any(value != set(HORIZONS_MONTHS) for value in horizon_sets)
        or intents[["source_id", "site_id"]].drop_duplicates().shape[0]
        != LOCKED_HOLDOUT_SITE_COUNT
    ):
        raise ClosureBenchmarkError("E1 locked holdout denominator drifted")
    try:
        origin_periods = pd.PeriodIndex(intents["origin_year_month"], freq="M")
        target_periods = pd.PeriodIndex(intents["target_year_month"], freq="M")
    except BaseException as exc:
        raise ClosureBenchmarkError("E1 evaluation month dialect drifted") from exc
    if (origin_periods < pd.Period("2022-01", freq="M")).any() or (
        target_periods < pd.Period("2022-02", freq="M")
    ).any():
        raise ClosureBenchmarkError("E1 pre-2022 rows entered the locked evaluation")
    intent_target_keys = set(
        map(tuple, intents[target_identity].itertuples(index=False, name=None))
    )
    observed_target_keys = set(
        map(tuple, targets[target_identity].itertuples(index=False, name=None))
    )
    if observed_target_keys != intent_target_keys:
        raise ClosureBenchmarkError("E1 target key universe is not exact")

    prediction_key = [*identity, "model_id", "seed_slot"]
    if predictions.duplicated(prediction_key).any():
        raise ClosureBenchmarkError("E1 prediction keys are duplicated")
    expected_pairs = {
        (model, seed)
        for model in MODEL_IDS
        if model not in ZERO_SLOT_MODEL_IDS
        for seed in REGISTERED_SEEDS
    }
    pair_sets = predictions.groupby(identity, sort=True).apply(
        lambda group: set(zip(group["model_id"], group["seed_slot"], strict=True)),
        include_groups=False,
    )
    if (
        len(predictions) != LOCKED_PREDICTION_ROW_COUNT
        or len(pair_sets) != len(intents)
        or any(pairs != expected_pairs for pairs in pair_sets)
    ):
        raise ClosureBenchmarkError("E1 model-by-seed paired surface is incomplete")
    deterministic = predictions["model_id"].isin(DETERMINISTIC_MODEL_IDS)
    if (
        not predictions.loc[deterministic, "model_seed"].eq(RNG_SEED).all()
        or not predictions.loc[~deterministic, "model_seed"].eq(
            predictions.loc[~deterministic, "seed_slot"]
        ).all()
    ):
        raise ClosureBenchmarkError("E1 model-seed versus inferential-slot policy drifted")

    numeric_prediction_columns = [
        "bloom_probability",
        "alert_threshold",
        "predicted_value",
        "predicted_sigma",
        "predicted_lower",
        "predicted_upper",
        "continuous_score",
        "ordinal_score",
        "cutpoint_1",
        "cutpoint_2",
        "cutpoint_3",
    ]
    for column in numeric_prediction_columns:
        predictions[column] = pd.to_numeric(predictions[column], errors="coerce")
    targets["actual_bloom"] = pd.to_numeric(targets["actual_bloom"], errors="coerce")
    targets["actual_value"] = pd.to_numeric(targets["actual_value"], errors="coerce")
    targets["actual_chla_ug_l"] = pd.to_numeric(
        targets["actual_chla_ug_l"], errors="coerce"
    )
    _require_text_columns(targets, ["target_status"], label="target")
    if not targets["target_status"].isin(["available", "target_unavailable"]).all():
        raise ClosureBenchmarkError("E1 locked target status drifted")
    target_available = targets["target_status"].eq("available")
    target_numeric = targets.loc[
        target_available, ["actual_bloom", "actual_value", "actual_chla_ug_l"]
    ].to_numpy(dtype="float64")
    if (
        target_numeric.size
        and not np.isfinite(target_numeric).all()
        or not targets.loc[target_available, "actual_bloom"].isin([0.0, 1.0]).all()
        or not targets.loc[target_available, "actual_value"].between(0.0, 1.0).all()
        or (targets.loc[target_available, "actual_chla_ug_l"] < 0.0).any()
        or not targets.loc[target_available, "actual_bloom"].eq(
            targets.loc[target_available, "actual_chla_ug_l"].gt(30.0).astype(float)
        ).all()
        or targets.loc[
            ~target_available, ["actual_bloom", "actual_value", "actual_chla_ug_l"]
        ]
        .notna()
        .any()
        .any()
    ):
        raise ClosureBenchmarkError("E1 locked target values drifted")
    trophic_labels = {"oligotrophic", "mesotrophic", "eutrophic", "hypereutrophic"}
    if (
        targets.loc[target_available, "actual_trophic_state"].isna().any()
        or not targets.loc[target_available, "actual_trophic_state"]
        .astype(str)
        .isin(trophic_labels)
        .all()
        or targets.loc[~target_available, "actual_trophic_state"].notna().any()
    ):
        raise ClosureBenchmarkError("E1 locked trophic target dialect drifted")

    endpoint_fields = {
        "bloom": ("bloom_probability", "alert_threshold"),
        "continuous": ("predicted_value", "continuous_score"),
        "uncertainty": (
            "predicted_sigma",
            "predicted_lower",
            "predicted_upper",
        ),
        "ordinal": ("ordinal_score", "cutpoint_1", "cutpoint_2", "cutpoint_3"),
    }
    for endpoint, fields in endpoint_fields.items():
        endpoint_success = predictions[f"{endpoint}_status"].eq("success")
        if predictions.loc[endpoint_success, list(fields)].isna().any().any():
            raise ClosureBenchmarkError(
                f"E1 successful {endpoint} endpoint is incomplete"
            )
        values = predictions.loc[endpoint_success, list(fields)].to_numpy(
            dtype="float64"
        )
        if values.size and not np.isfinite(values).all():
            raise ClosureBenchmarkError(
                f"E1 successful {endpoint} endpoint is nonfinite"
            )
        if predictions.loc[~endpoint_success, list(fields)].notna().any().any():
            raise ClosureBenchmarkError(
                f"E1 unavailable {endpoint} endpoint contains invented values"
            )
    bloom_success = predictions["bloom_status"].eq("success")
    continuous_success = predictions["continuous_status"].eq("success")
    uncertainty_success = predictions["uncertainty_status"].eq("success")
    ordinal_success = predictions["ordinal_status"].eq("success")
    if (
        not predictions.loc[bloom_success, "bloom_probability"].between(0.0, 1.0).all()
        or not predictions.loc[bloom_success, "alert_threshold"].between(0.0, 1.0).all()
        or not predictions.loc[continuous_success, "predicted_value"].between(0.0, 1.0).all()
        or not predictions.loc[continuous_success, "continuous_score"].between(0.0, 1.0).all()
        or not (predictions.loc[uncertainty_success, "predicted_sigma"] > 0.0).all()
        or not (
            predictions.loc[uncertainty_success, "predicted_lower"]
            <= predictions.loc[uncertainty_success, "predicted_upper"]
        ).all()
        or not predictions.loc[uncertainty_success, "continuous_status"].eq("success").all()
        or not (
            predictions.loc[ordinal_success, "cutpoint_1"]
            < predictions.loc[ordinal_success, "cutpoint_2"]
        ).all()
        or not (
            predictions.loc[ordinal_success, "cutpoint_2"]
            < predictions.loc[ordinal_success, "cutpoint_3"]
        ).all()
        or not predictions.loc[ordinal_success, "ordinal_score"].between(0.0, 1.0).all()
        or not predictions.loc[ordinal_success, "cutpoint_1"].between(0.0, 1.0).all()
        or not predictions.loc[ordinal_success, "cutpoint_2"].between(0.0, 1.0).all()
        or not predictions.loc[ordinal_success, "cutpoint_3"].between(0.0, 1.0).all()
    ):
        raise ClosureBenchmarkError("E1 successful endpoint range drifted")
    global_success = predictions["terminal_status"].eq("success")
    any_endpoint_success = predictions[list(ENDPOINT_STATUS_COLUMNS)].eq("success").any(axis=1)
    if not global_success.eq(any_endpoint_success).all():
        raise ClosureBenchmarkError("E1 row and endpoint terminal statuses disagree")
    for model_id, availability in CURRENT_MODEL_AVAILABILITY.items():
        rows = predictions["model_id"].eq(model_id)
        if availability == "unavailable":
            if rows.any() and (
                not predictions.loc[rows, "terminal_status"].eq("model_unavailable").all()
                or not predictions.loc[rows, list(ENDPOINT_STATUS_COLUMNS)]
                .eq("model_unavailable")
                .all()
                .all()
            ):
                raise ClosureBenchmarkError(
                    f"E1 unavailable model terminal drifted: {model_id}"
                )
        elif predictions.loc[rows, "terminal_status"].eq("model_unavailable").any():
            raise ClosureBenchmarkError(
                f"E1 available model was silently marked unavailable: {model_id}"
            )
        if rows.any() and availability == "available":
            for endpoint, endpoint_availability in MODEL_ENDPOINT_AVAILABILITY[
                model_id
            ].items():
                statuses = predictions.loc[rows, f"{endpoint}_status"]
                if endpoint_availability == "not_applicable" and not statuses.eq(
                    "not_applicable"
                ).all():
                    raise ClosureBenchmarkError(
                        f"E1 not-applicable endpoint drifted: {model_id}:{endpoint}"
                    )
                if endpoint_availability == "available" and statuses.isin(
                    ["not_applicable", "model_unavailable"]
                ).any():
                    raise ClosureBenchmarkError(
                        f"E1 applicable endpoint was silently removed: {model_id}:{endpoint}"
                    )

    merged = predictions.merge(
        intents,
        on=identity,
        how="left",
        validate="many_to_one",
        indicator="_intent_merge",
    )
    if not merged["_intent_merge"].eq("both").all():
        raise ClosureBenchmarkError("E1 prediction is outside locked intents")
    merged = merged.drop(columns="_intent_merge").merge(
        targets,
        on=target_identity,
        how="left",
        validate="many_to_one",
        indicator="_target_merge",
    )
    if not merged["_target_merge"].eq("both").all():
        raise ClosureBenchmarkError("E1 prediction target is absent")
    merged = merged.drop(columns="_target_merge")
    target_missing = merged["target_status"].eq("target_unavailable")
    models_available = merged["model_id"].map(CURRENT_MODEL_AVAILABILITY).eq("available")
    if not merged.loc[
        target_missing & models_available, "terminal_status"
    ].eq("target_unavailable").all():
        raise ClosureBenchmarkError("E1 missing target terminal precedence drifted")
    if merged.loc[
        ~target_missing, "terminal_status"
    ].eq("target_unavailable").any():
        raise ClosureBenchmarkError("E1 available target was marked unavailable")
    for endpoint in ENDPOINTS:
        status_column = f"{endpoint}_status"
        applicable = merged["model_id"].map(
            lambda model_id: MODEL_ENDPOINT_AVAILABILITY[str(model_id)][endpoint]
            == "available"
        )
        if not merged.loc[target_missing & models_available & applicable, status_column].eq(
            "target_unavailable"
        ).all():
            raise ClosureBenchmarkError(
                f"E1 missing-target endpoint precedence drifted: {endpoint}"
            )
        if merged.loc[
            ~target_missing & models_available & applicable, status_column
        ].eq("target_unavailable").any():
            raise ClosureBenchmarkError(
                f"E1 available-target endpoint was marked unavailable: {endpoint}"
            )
    return merged.sort_values(prediction_key, kind="mergesort").reset_index(drop=True)


def _e1_metric_values(group: Any) -> dict[str, float | None]:
    import numpy as np
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        f1_score,
        fbeta_score,
        mean_absolute_error,
        mean_squared_error,
        precision_score,
        recall_score,
    )

    empty = {
        "rmse": None,
        "mae": None,
        "nll": None,
        "coverage": None,
        "pr_auc": None,
        "brier": None,
        "recall": None,
        "precision": None,
        "f2": None,
        "macro_f1": None,
        "alert_rate": None,
    }
    result = dict(empty)
    continuous = group.loc[group["continuous_status"].eq("success")]
    if not continuous.empty:
        actual = continuous["actual_value"].to_numpy(dtype="float64")
        predicted = continuous["predicted_value"].to_numpy(dtype="float64")
        result["rmse"] = float(math.sqrt(mean_squared_error(actual, predicted)))
        result["mae"] = float(mean_absolute_error(actual, predicted))
    uncertain = group.loc[group["uncertainty_status"].eq("success")]
    if not uncertain.empty:
        actual = uncertain["actual_value"].to_numpy(dtype="float64")
        predicted = uncertain["predicted_value"].to_numpy(dtype="float64")
        sigma = uncertain["predicted_sigma"].to_numpy(dtype="float64")
        lower = uncertain["predicted_lower"].to_numpy(dtype="float64")
        upper = uncertain["predicted_upper"].to_numpy(dtype="float64")
        result["nll"] = float(
            np.mean(
                0.5
                * (
                    np.log(2.0 * np.pi * sigma**2)
                    + ((actual - predicted) / sigma) ** 2
                )
            )
        )
        result["coverage"] = float(np.mean((actual >= lower) & (actual <= upper)))
    bloom = group.loc[group["bloom_status"].eq("success")]
    if not bloom.empty:
        labels = bloom["actual_bloom"].to_numpy(dtype="int64")
        probability = bloom["bloom_probability"].to_numpy(dtype="float64")
        alerts = probability >= bloom["alert_threshold"].to_numpy(dtype="float64")
        result.update(
            {
                "pr_auc": (
                    float(average_precision_score(labels, probability))
                    if np.unique(labels).size == 2
                    else None
                ),
                "brier": float(brier_score_loss(labels, probability)),
                "recall": float(recall_score(labels, alerts, zero_division=0)),
                "precision": float(
                    precision_score(labels, alerts, zero_division=0)
                ),
                "f2": float(fbeta_score(labels, alerts, beta=2.0, zero_division=0)),
                "macro_f1": float(
                    f1_score(labels, alerts, average="macro", zero_division=0)
                ),
                "alert_rate": float(np.mean(alerts)),
            }
        )
    return result


def _e1_metrics_long(surface: Any) -> Any:
    import numpy as np
    import pandas as pd

    test = surface.loc[surface["evaluation_role"].eq("test")]
    group_columns = [
        "model_id",
        "model_seed",
        "seed_slot",
        "horizon_months",
        "evaluation_cohort",
    ]
    rows: list[dict[str, Any]] = []
    for raw_key, group in test.groupby(group_columns, sort=True):
        key = cast(tuple[Any, ...], raw_key)
        observation = _e1_metric_values(group)
        site_values: dict[str, list[float]] = {name: [] for name in observation}
        for _, site_group in group.groupby(["source_id", "site_id"], sort=True):
            for metric, value in _e1_metric_values(site_group).items():
                if value is not None and np.isfinite(value):
                    site_values[metric].append(value)
        for metric, value in observation.items():
            terminal = "estimated" if value is not None else "not_estimable"
            endpoint_status = (
                "continuous_status"
                if metric in {"rmse", "mae"}
                else "uncertainty_status"
                if metric in {"nll", "coverage"}
                else "bloom_status"
            )
            base = {
                **dict(zip(group_columns, key, strict=True)),
                "metric": metric,
                "origin_count": int(len(group)),
                "model_applicable_origin_count": int(
                    group[endpoint_status].ne("not_applicable").sum()
                ),
                "input_eligible_origin_count": int(
                    (~group[endpoint_status].isin(
                        ["not_applicable", "model_unavailable", "input_ineligible"]
                    )).sum()
                ),
                "successful_origin_count": int(
                    group[endpoint_status].eq("success").sum()
                ),
                "metric_evaluable_origin_count": int(
                    group[endpoint_status].eq("success").sum()
                ),
                "site_count": int(group[["source_id", "site_id"]].drop_duplicates().shape[0]),
                "successful_site_count": int(
                    group.loc[
                        group[endpoint_status].eq("success"), ["source_id", "site_id"]
                    ].drop_duplicates().shape[0]
                ),
                **{
                    f"{status}_origin_count": int(group[endpoint_status].eq(status).sum())
                    for status in ENDPOINT_STATUSES
                    if status != "success"
                },
                "terminal_status": terminal,
            }
            rows.append({**base, "estimand": "observation_weighted", "value": value})
            values = site_values[metric]
            rows.append(
                {
                    **base,
                    "estimand": "site_weighted",
                    "value": float(np.mean(values)) if values else None,
                    "terminal_status": "estimated" if values else "not_estimable",
                }
            )
    return pd.DataFrame(rows).sort_values(
        [*group_columns, "metric", "estimand"], kind="mergesort"
    ).reset_index(drop=True)


def _e1_paired_metric_rows(surface: Any) -> Any:
    import numpy as np
    import pandas as pd

    test = surface.loc[surface["evaluation_role"].eq("test")]
    identity = list(PAIRED_METRIC_COLUMNS[:9])
    rows: list[Any] = []
    for metric in ("brier_loss", "absolute_error"):
        part = test.loc[:, identity].copy()
        status_column = (
            "bloom_status" if metric == "brier_loss" else "continuous_status"
        )
        success = test[status_column].eq("success")
        if metric == "brier_loss":
            loss = (
                test["bloom_probability"].to_numpy(dtype="float64")
                - test["actual_bloom"].to_numpy(dtype="float64")
            ) ** 2
        else:
            loss = np.abs(
                test["predicted_value"].to_numpy(dtype="float64")
                - test["actual_value"].to_numpy(dtype="float64")
            )
        part["metric"] = metric
        part["loss"] = np.where(success.to_numpy(dtype="bool"), loss, np.nan)
        part["terminal_status"] = test[status_column].to_numpy()
        rows.append(part.loc[:, PAIRED_METRIC_COLUMNS])
    result = pd.concat(rows, ignore_index=True)
    return result.sort_values(
        [
            "metric",
            "seed_slot",
            "horizon_months",
            "evaluation_cohort",
            "source_id",
            "site_id",
            "common_origin_id",
            "model_id",
        ],
        kind="mergesort",
    ).reset_index(drop=True)


def _e1_comparisons(paired: Any) -> Any:
    import numpy as np
    import pandas as pd

    join_columns = [
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "horizon_months",
        "seed_slot",
        "evaluation_cohort",
        "metric",
    ]
    rows: list[dict[str, Any]] = []
    for model_a, model_b, family in E1_MODEL_PAIRS:
        left = paired.loc[
            paired["model_id"].eq(model_a), [*join_columns, "loss", "terminal_status"]
        ].rename(columns={"loss": "loss_a", "terminal_status": "status_a"})
        right = paired.loc[
            paired["model_id"].eq(model_b), [*join_columns, "loss", "terminal_status"]
        ].rename(columns={"loss": "loss_b", "terminal_status": "status_b"})
        joined = left.merge(right, on=join_columns, how="outer", validate="one_to_one")
        for raw_key, group in joined.groupby(
            ["horizon_months", "seed_slot", "evaluation_cohort", "metric"],
            sort=True,
        ):
            key = cast(tuple[Any, ...], raw_key)
            eligible = group["loss_a"].notna() & group["loss_b"].notna()
            delta = (
                group.loc[eligible, "loss_a"].to_numpy(dtype="float64")
                - group.loc[eligible, "loss_b"].to_numpy(dtype="float64")
            )
            rows.append(
                {
                    "comparison_id": f"{model_a}_vs_{model_b}",
                    "family": family,
                    "model_a": model_a,
                    "model_b": model_b,
                    "horizon_months": int(key[0]),
                    "seed_slot": int(key[1]),
                    "evaluation_cohort": str(key[2]),
                    "metric": str(key[3]),
                    "paired_origin_count": int(eligible.sum()),
                    "mean_loss_model_a": (
                        float(group.loc[eligible, "loss_a"].mean()) if eligible.any() else None
                    ),
                    "mean_loss_model_b": (
                        float(group.loc[eligible, "loss_b"].mean()) if eligible.any() else None
                    ),
                    "mean_loss_difference_a_minus_b": (
                        float(np.mean(delta)) if delta.size else None
                    ),
                    "terminal_status": "estimated" if delta.size else "not_estimable",
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["comparison_id", "seed_slot", "horizon_months", "evaluation_cohort", "metric"],
        kind="mergesort",
    ).reset_index(drop=True)


def _e1_trophic_predictions(surface: Any) -> Any:
    columns = [
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
        "model_id",
        "model_seed",
        "seed_slot",
        "evaluation_cohort",
        "evaluation_role",
        "terminal_status",
        "ordinal_status",
        "ordinal_score",
        "cutpoint_1",
        "cutpoint_2",
        "cutpoint_3",
    ]
    evaluation = surface.loc[
        surface["evaluation_role"].eq("test")
        & surface["evaluation_cohort"].eq("location_holdout"),
        columns,
    ].copy(deep=True)
    return evaluation.sort_values(
        [
            "source_id",
            "site_id",
            "common_origin_id",
            "horizon_months",
            "model_id",
            "seed_slot",
        ],
        kind="mergesort",
    ).reset_index(drop=True)


def _dataframe_digest(frame: Any) -> str:
    import pandas as pd

    if not isinstance(frame, pd.DataFrame):
        raise ClosureBenchmarkError("E1 digest input is not a DataFrame")
    records = json.loads(
        frame.to_json(orient="records", date_format="iso", double_precision=15)
    )
    return _sha256_bytes(_canonical_json_bytes(records))


def _execute_e1_locked_benchmark_stage(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    batch_context: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """Build the common paired E1 surface and metrics entirely in memory."""

    del repo_root
    expected_authority = {
        "gate": UNBLINDING_GATE,
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
    }
    for key, expected in expected_authority.items():
        if type(authority.get(key)) is not type(expected) or authority.get(key) != expected:
            raise ClosureBenchmarkError(f"E1 authority field drifted: {key}")
    validate_sealed_batch_contract(sealed_batch_contract)
    context = _validate_opened_batch_context(batch_context)
    tables = cast(dict[str, Any], context["tables"])
    surface = _normalize_e1_prediction_surface(tables)
    metrics = _e1_metrics_long(surface)
    paired = _e1_paired_metric_rows(surface)
    comparisons = _e1_comparisons(paired)
    trophic = _e1_trophic_predictions(surface)
    report = (
        "# Closure V1 E1 unified benchmark\n\n"
        "All model slots were evaluated on the same locked intent/outcome keys. "
        "No model was fitted, recalibrated, replaced, or silently removed in E1.\n\n"
        f"- paired prediction rows: {len(surface)}\n"
        f"- paired intent keys: {surface[list(E1_INTENT_COLUMNS[:7])].drop_duplicates().shape[0]}\n"
        f"- metric rows: {len(metrics)}\n"
        f"- comparison rows: {len(comparisons)}\n"
        f"- unavailable model ids retained: {', '.join(UNAVAILABLE_MODEL_IDS)}\n"
        "- observation-weighted and site-weighted estimands are reported separately.\n"
        "- noninferiority margins (PR-AUC 0.02; Brier 0.01) are project conventions, not ecological standards.\n"
    )
    output_paths = next(stage.output_paths for stage in BATCH_STAGES if stage.stage_id == "E1")
    manifest = {
        "schema_version": "closure_e1_benchmark_manifest_v1",
        "execution_id": context["execution_id"],
        "rng_seed": RNG_SEED,
        "model_ids": list(MODEL_IDS),
        "registered_seed_slots": list(REGISTERED_SEEDS),
        "model_availability": dict(CURRENT_MODEL_AVAILABILITY),
        "prediction_row_count": len(surface),
        "metric_row_count": len(metrics),
        "comparison_row_count": len(comparisons),
        "prediction_sha256": _dataframe_digest(surface),
        "metrics_sha256": _dataframe_digest(metrics),
        "comparisons_sha256": _dataframe_digest(comparisons),
        "output_paths": list(output_paths),
        "evaluation_refit_performed": False,
        "failed_model_replacement_performed": False,
        "silent_row_deletion_performed": False,
        "manifest_last": True,
    }
    artifacts = {
        output_paths[4]: {
            "format": "parquet",
            "payload": surface.copy(deep=True),
            "manifest_last": False,
        },
        output_paths[0]: {
            "format": "csv",
            "payload": metrics.copy(deep=True),
            "manifest_last": False,
        },
        output_paths[1]: {
            "format": "csv",
            "payload": comparisons.copy(deep=True),
            "manifest_last": False,
        },
        output_paths[2]: {
            "format": "markdown",
            "payload": report,
            "manifest_last": False,
        },
        output_paths[3]: {
            "format": "json",
            "payload": manifest,
            "manifest_last": True,
        },
    }
    return {
        "component_id": "E1_benchmark_scientific_executor",
        "stage_id": "E1",
        "status": "completed_unavailable",
        "artifacts": artifacts,
        "tables": {
            "predictions_long": surface.copy(deep=True),
            "paired_metric_rows": paired.copy(deep=True),
            "trophic_predictions": trophic.copy(deep=True),
            "e1_model_metrics": metrics.copy(deep=True),
            "e1_model_comparisons": comparisons.copy(deep=True),
        },
        "diagnostics": {
            "execution_id": context["execution_id"],
            "model_count": len(MODEL_IDS),
            "seed_slot_count": len(REGISTERED_SEEDS),
            "unavailable_model_ids": list(UNAVAILABLE_MODEL_IDS),
            "evaluation_refit_performed": False,
            "outcome_paths_opened": True,
            "writes_performed": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }


def _load_ready_components(
    readiness: Mapping[str, Any],
) -> tuple[tuple[BatchComponent, ModuleType], ...]:
    if readiness.get("status") != "sealed_batch_components_ready":
        raise ClosureBenchmarkError("E0-U component readiness drifted")
    records_raw = readiness.get("component_source_records")
    if not isinstance(records_raw, Sequence) or isinstance(records_raw, (str, bytes)):
        raise ClosureBenchmarkError("E0-U component source records are malformed")
    records = {
        cast(str, record.get("component_id")): record
        for record in records_raw
        if isinstance(record, Mapping) and isinstance(record.get("component_id"), str)
    }
    if set(records) != {component.component_id for component in BATCH_COMPONENTS}:
        raise ClosureBenchmarkError("E0-U component source record set drifted")
    loaded: list[tuple[BatchComponent, ModuleType]] = []
    for component in BATCH_COMPONENTS:
        try:
            module, observed = _execute_sealed_source_module(
                module_name=component.module_name,
                source_path=Path(component.source_path),
                repo_root=PROJECT_ROOT,
                expected_source_record=records[component.component_id],
            )
        except BaseException as exc:
            raise ClosureBenchmarkError(
                f"E0-U component source execution failed closed: {component.component_id}"
            ) from exc
        _normalize_sealed_dependency_import_environment()
        _require_source_identity(
            records[component.component_id],
            observed,
            context=component.component_id,
        )
        if not callable(getattr(module, component.preflight_api, None)) or not callable(
            getattr(module, component.execute_api, None)
        ):
            raise ClosureBenchmarkError(
                f"E0-U component API drifted: {component.component_id}"
            )
        loaded.append((component, module))
    return tuple(loaded)


def _load_ready_context_builder(
    readiness: Mapping[str, Any], authority: Mapping[str, Any]
) -> tuple[Any, Any, dict[str, Any]]:
    readiness_record = readiness.get("context_builder_source_record")
    authority_record = authority.get(E0_U_CONTEXT_BUILDER_SOURCE_RECORD_KEY)
    if (
        not isinstance(readiness_record, Mapping)
        or readiness_record.get("status") != "ready"
        or not isinstance(authority_record, Mapping)
        or dict(authority_record) != dict(readiness_record)
    ):
        raise ClosureBenchmarkError(
            "E0-U context-builder source binding drifted"
        )
    try:
        module, observed = _execute_sealed_source_module(
            module_name=E0_U_CONTEXT_BUILDER_MODULE,
            source_path=E0_U_CONTEXT_BUILDER_PATH,
            repo_root=PROJECT_ROOT,
            expected_source_record=authority_record,
        )
    except BaseException as exc:
        raise ClosureBenchmarkError(
            "E0-U context-builder source execution failed closed"
        ) from exc
    _normalize_sealed_dependency_import_environment()
    _require_source_identity(
        authority_record, observed, context="phase3_context_builder"
    )
    builder = getattr(module, E0_U_CONTEXT_BUILDER_API, None)
    preflight = getattr(module, E0_U_CONTEXT_PREFLIGHT_API, None)
    if not callable(builder) or not callable(preflight):
        raise ClosureBenchmarkError("E0-U context-builder/preflight API drifted")
    return builder, preflight, dict(readiness_record)


def _validate_phase3_overlay_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "manifest",
        "physical_outputs",
    }:
        raise ClosureBenchmarkError("E0-U Phase 3 overlay binding is malformed")
    manifest = value.get("manifest")
    outputs = value.get("physical_outputs")
    expected_paths = [path.as_posix() for path in PHASE3_OVERLAY_OUTPUT_PATHS]
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != {"path", "bytes", "sha256"}
        or manifest.get("path") != PHASE3_OVERLAY_MANIFEST_PATH.as_posix()
        or type(manifest.get("bytes")) is not int
        or cast(int, manifest["bytes"]) <= 0
        or not _is_sha256(manifest.get("sha256"))
        or not isinstance(outputs, list)
        or len(outputs) != len(expected_paths)
    ):
        raise ClosureBenchmarkError("E0-U Phase 3 overlay binding is malformed")
    normalized_outputs: list[dict[str, Any]] = []
    for raw, expected_path in zip(outputs, expected_paths, strict=True):
        if not isinstance(raw, Mapping):
            raise ClosureBenchmarkError("E0-U Phase 3 overlay binding is malformed")
        record = cast(Mapping[str, Any], raw)
        if (
            set(record) != {"path", "bytes", "sha256"}
            or record.get("path") != expected_path
            or type(record.get("bytes")) is not int
            or cast(int, record["bytes"]) <= 0
            or not _is_sha256(record.get("sha256"))
        ):
            raise ClosureBenchmarkError("E0-U Phase 3 overlay binding is malformed")
        normalized_outputs.append(dict(record))
    return {
        "manifest": dict(manifest),
        "physical_outputs": normalized_outputs,
    }


def _validate_phase3_context_input_preflight(
    value: Any,
    *,
    expected_overlay_record: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ClosureBenchmarkError("E0-U Phase 3 input preflight is not a mapping")
    observed = dict(value)
    sealed_overlay_record = _validate_phase3_overlay_record(expected_overlay_record)
    exact = {
        "status": "sealed_phase3_context_inputs_ready",
        "gate": UNBLINDING_GATE,
        "input_only": True,
        "outcome_access_performed": False,
        "writes_performed": False,
        "refit_performed": False,
        "snapshot_reuse_authorized": False,
        "post_append_revalidation_required": True,
        "holdout_site_count": LOCKED_HOLDOUT_SITE_COUNT,
        "origin_count": LOCKED_BASE_ORIGIN_COUNT,
        "history_row_count": 53856,
        "origin_feature_row_count": LOCKED_BASE_ORIGIN_COUNT,
        "eligible_origin_count": 804,
        "ineligible_origin_count": 3684,
        "expanded_intent_count": LOCKED_INTENT_COUNT,
        "pretarget_prediction_count": LOCKED_PREDICTION_ROW_COUNT,
        "warmup_site_count": LOCKED_HOLDOUT_SITE_COUNT,
        "calibrator_count": 66,
        "threshold_count": 66,
        "cutpoint_count": 30,
        "conformal_factor_count": 90,
        "site_strata_count": LOCKED_HOLDOUT_SITE_COUNT,
        "hypothesis_count": 27,
        "software_evidence_artifact_count": len(SOFTWARE_EVIDENCE_KEYS),
        "registered_seed_count": len(REGISTERED_SEEDS),
        "outcome_bearing_paths_opened": [],
        "phase3_overlay_record": sealed_overlay_record,
    }
    positive_count_keys = {
        "overlay_array_count",
        "scored_model_slot_count",
        "anchored_input_read_count",
    }
    digest_key = "input_snapshot_sha256"
    if (
        set(observed) != set(exact) | positive_count_keys | {digest_key}
        or any(
            type(observed.get(key)) is not type(expected)
            or observed.get(key) != expected
            for key, expected in exact.items()
        )
        or any(
            type(observed.get(key)) is not int
            or cast(int, observed[key]) <= 0
            for key in positive_count_keys
        )
        or not _is_sha256(observed.get(digest_key))
    ):
        raise ClosureBenchmarkError(
            "E0-U Phase 3 input preflight diagnostics drifted"
        )
    return observed


def _load_ready_support_sources(
    readiness: Mapping[str, Any], authority: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    readiness_records = readiness.get("support_source_records")
    authority_records = authority.get(E0_U_SUPPORT_SOURCE_RECORDS_KEY)
    if (
        not isinstance(readiness_records, list)
        or not isinstance(authority_records, list)
        or authority_records != readiness_records
        or len(readiness_records) != len(SEALED_SUPPORT_SOURCES)
    ):
        raise ClosureBenchmarkError("E0-U support-source bindings drifted")
    observed_records: list[dict[str, Any]] = []
    for spec, record in zip(
        SEALED_SUPPORT_SOURCES, readiness_records, strict=True
    ):
        record_mapping = cast(Mapping[str, Any], record)
        if (
            not isinstance(record, Mapping)
            or record_mapping.get("status") != "ready"
            or record_mapping.get("support_id") != spec["support_id"]
        ):
            raise ClosureBenchmarkError("E0-U support-source readiness drifted")
        module, observed = _execute_sealed_source_module(
            module_name=cast(str, spec["module_name"]),
            source_path=Path(cast(str, spec["source_path"])),
            repo_root=PROJECT_ROOT,
            expected_source_record=record_mapping,
        )
        _normalize_sealed_dependency_import_environment()
        _require_source_identity(
            record_mapping, observed, context=cast(str, spec["support_id"])
        )
        for symbol in cast(Sequence[str], spec["required_symbols"]):
            if not callable(getattr(module, symbol, None)):
                raise ClosureBenchmarkError(
                    f"E0-U support-source symbol drifted: {spec['support_id']}:{symbol}"
                )
        if spec["support_id"] == "closure_e10_source_evidence":
            loader = getattr(module, "load_closure_e10_software_evidence")
            try:
                evidence = loader(
                    repo_root=PROJECT_ROOT,
                    expected_h_commit=authority["phase3_code_commit"],
                    require_git_publication=True,
                )
            except BaseException as exc:
                raise ClosureBenchmarkError(
                    "E0-U E10 source evidence failed before outcome logging"
                ) from exc
            if not isinstance(evidence, Mapping) or set(evidence) != SOFTWARE_EVIDENCE_KEYS:
                raise ClosureBenchmarkError(
                    "E0-U E10 source evidence keys drifted before outcome logging"
                )
        observed_records.append(dict(record_mapping))
    return tuple(observed_records)


def _validate_authority_source_bindings(
    authority: Mapping[str, Any], readiness: Mapping[str, Any]
) -> None:
    observed_runner = runner_source_record(repo_root=PROJECT_ROOT)
    if authority.get(E0_U_RUNNER_SOURCE_RECORD_KEY) != observed_runner:
        raise ClosureBenchmarkError("E0-U authority runner source binding drifted")
    records = readiness.get("component_source_records")
    if not isinstance(records, list) or authority.get(
        E0_U_COMPONENT_SOURCE_RECORDS_KEY
    ) != records:
        raise ClosureBenchmarkError("E0-U authority component source binding drifted")
    context_builder_record = readiness.get("context_builder_source_record")
    if not isinstance(context_builder_record, Mapping) or authority.get(
        E0_U_CONTEXT_BUILDER_SOURCE_RECORD_KEY
    ) != dict(context_builder_record):
        raise ClosureBenchmarkError(
            "E0-U authority context-builder source binding drifted"
        )
    support_records = readiness.get("support_source_records")
    if not isinstance(support_records, list) or authority.get(
        E0_U_SUPPORT_SOURCE_RECORDS_KEY
    ) != support_records:
        raise ClosureBenchmarkError("E0-U authority support-source binding drifted")
    observed_authority = authority.get("_observed_authority_source_record")
    if not isinstance(observed_authority, Mapping):
        raise ClosureBenchmarkError("E0-U observed authority source is absent")
    _validate_authority_commit_bindings(authority, observed_authority)
    if authority.get(E0_U_AUTHORITY_SOURCE_RECORD_KEY) != dict(observed_authority):
        raise ClosureBenchmarkError("E0-U authority Git source binding drifted")


def _recapture_authority_source(authority: Mapping[str, Any]) -> None:
    observed = _git_bound_e0_u_authority_source_record()
    _validate_authority_commit_bindings(authority, observed)
    if (
        authority.get(E0_U_AUTHORITY_SOURCE_RECORD_KEY) != observed
        or observed != authority.get("_observed_authority_source_record")
        or authority.get(E0_U_GIT_EXECUTABLE_RECORD_KEY)
        != _git_executable_record()
        or authority.get(E0_U_ENV_EXECUTABLE_RECORD_KEY)
        != _env_executable_record()
        or authority.get(E0_U_CONTEXT_BUILDER_SOURCE_RECORD_KEY)
        != _context_builder_source_record(repo_root=PROJECT_ROOT)
        or authority.get("_observed_context_builder_source_record")
        != _context_builder_source_record(repo_root=PROJECT_ROOT)
        or authority.get(E0_U_SUPPORT_SOURCE_RECORDS_KEY)
        != [
            _support_source_record(spec, repo_root=PROJECT_ROOT)
            for spec in SEALED_SUPPORT_SOURCES
        ]
        or authority.get("_observed_support_source_records")
        != [
            _support_source_record(spec, repo_root=PROJECT_ROOT)
            for spec in SEALED_SUPPORT_SOURCES
        ]
    ):
        raise ClosureBenchmarkError("E0-U authority source changed during execution")


def _component_context(
    context: Mapping[str, Any], *, component_id: str
) -> dict[str, Any]:
    allowed = COMPONENT_TABLE_VIEWS.get(component_id)
    if allowed is None:
        raise ClosureBenchmarkError(
            f"E0-U component has no least-privilege table view: {component_id}"
        )
    source_tables = cast(Mapping[str, Any], context["tables"])
    selected_tables = {
        table_name: source_tables[table_name]
        for table_name in allowed
        if table_name in source_tables
    }
    stage_results = (
        copy.deepcopy(dict(cast(Mapping[str, Any], context["stage_results"])))
        if component_id == "E10_evidence_matrix"
        else {}
    )
    software_evidence = (
        copy.deepcopy(dict(cast(Mapping[str, Any], context["software_evidence"])))
        if component_id == "E10_evidence_matrix"
        else {}
    )
    return {
        "execution_id": context["execution_id"],
        "rng_seed": RNG_SEED,
        "tables": _copy_dataframe_tables(selected_tables),
        "stage_results": stage_results,
        "model_availability": dict(CURRENT_MODEL_AVAILABILITY),
        "software_evidence": software_evidence,
    }


def _is_sha256(value: Any, *, expected: str | None = None) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
        and (expected is None or value == expected)
    )


def _is_nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _require_closed_json_diagnostics(value: Any, *, context: str) -> None:
    def closed(item: Any) -> bool:
        if item is None or type(item) in {bool, int, str}:
            return True
        if type(item) is float:
            return math.isfinite(item)
        if type(item) is list:
            return all(closed(element) for element in item)
        if type(item) is dict:
            return all(
                type(key) is str and bool(key) and closed(element)
                for key, element in item.items()
            )
        return False

    if type(value) is not dict or not closed(value):
        raise ClosureBenchmarkError(
            f"E0-U diagnostics contain a non-canonical payload: {context}"
        )


def _validate_component_diagnostics(
    value: Any,
    *,
    component_id: str,
    status: str,
) -> dict[str, Any]:
    _require_closed_json_diagnostics(value, context=component_id)
    diagnostics = cast(dict[str, Any], value)
    contract = COMPONENT_DIAGNOSTICS_CONTRACTS.get(component_id)
    if not isinstance(contract, Mapping) or status not in cast(
        Sequence[str], contract.get("statuses", ())
    ):
        raise ClosureBenchmarkError(
            f"E0-U diagnostics status is not component-bound: {component_id}:{status}"
        )

    def exact_keys(*names: str) -> bool:
        return set(diagnostics) == set(names)

    if component_id == "E1_benchmark_scientific_executor":
        valid = (
            exact_keys(
                "execution_id",
                "model_count",
                "seed_slot_count",
                "unavailable_model_ids",
                "evaluation_refit_performed",
                "outcome_paths_opened",
                "writes_performed",
            )
            and type(diagnostics["execution_id"]) is str
            and bool(diagnostics["execution_id"])
            and type(diagnostics["model_count"]) is int
            and diagnostics["model_count"] == 11
            and type(diagnostics["seed_slot_count"]) is int
            and diagnostics["seed_slot_count"] == 5
            and diagnostics["unavailable_model_ids"] == ["P0", "P1", "A2"]
            and diagnostics["evaluation_refit_performed"] is False
            and diagnostics["outcome_paths_opened"] is True
            and diagnostics["writes_performed"] is False
        )
    elif component_id == "E2_site_transfer":
        valid = (
            exact_keys(
                "execution_id",
                "e2a_complete",
                "e2a_estimand",
                "legacy_surface_available",
                "legacy_gap_not_estimable_reason",
                "e2b_predeclared",
                "e2b_predictions_available",
                "fold_count",
                "unavailable_models_retained",
                "writes_performed",
            )
            and type(diagnostics["execution_id"]) is str
            and bool(diagnostics["execution_id"])
            and diagnostics["e2a_complete"] is True
            and diagnostics["e2a_estimand"] == "locked_location_holdout_only"
            and diagnostics["legacy_surface_available"] is False
            and diagnostics["legacy_gap_not_estimable_reason"]
            == "legacy_evaluation_surface_not_frozen_before_e0_u"
            and diagnostics["e2b_predeclared"] is True
            and diagnostics["e2b_predictions_available"] is False
            and status == "completed_unavailable"
            and type(diagnostics["fold_count"]) is int
            and diagnostics["fold_count"] == 5
            and diagnostics["unavailable_models_retained"] == ["P0", "P1"]
            and diagnostics["writes_performed"] is False
        )
    elif component_id == "E3_threshold_sensitivity":
        thresholds = diagnostics.get("thresholds_ug_l")
        valid = (
            exact_keys(
                "execution_id",
                "thresholds_ug_l",
                "primary_threshold_ug_l",
                "model_scores_refit",
                "calibrator_fit_performed",
                "decision_threshold_selection_performed",
                "fixed_probability_sensitivity_only",
                "evaluation_cohort",
                "b2_secondary_retraining_performed",
                "writes_performed",
            )
            and type(diagnostics["execution_id"]) is str
            and bool(diagnostics["execution_id"])
            and type(thresholds) is list
            and all(type(item) is float for item in thresholds)
            and thresholds == [25.0, 30.0, 33.0, 50.0]
            and type(diagnostics["primary_threshold_ug_l"]) is float
            and diagnostics["primary_threshold_ug_l"] == 30.0
            and diagnostics["model_scores_refit"] is False
            and diagnostics["calibrator_fit_performed"] is False
            and diagnostics["decision_threshold_selection_performed"] is False
            and diagnostics["fixed_probability_sensitivity_only"] is True
            and diagnostics["evaluation_cohort"] == EVALUATION_COHORT
            and diagnostics["b2_secondary_retraining_performed"] is False
            and diagnostics["writes_performed"] is False
        )
    elif component_id == "E4_reference_targets":
        valid = (
            exact_keys(
                "row_count",
                "site_count",
                "non_chla_reference_row_count",
                "future_indicator_imputation_performed",
            )
            and _is_nonnegative_int(diagnostics["row_count"])
            and _is_nonnegative_int(diagnostics["site_count"])
            and diagnostics["site_count"] <= diagnostics["row_count"]
            and _is_nonnegative_int(diagnostics["non_chla_reference_row_count"])
            and diagnostics["non_chla_reference_row_count"] <= diagnostics["row_count"]
            and diagnostics["future_indicator_imputation_performed"] is False
        )
    elif component_id == "E4_trophic_evaluation":
        valid = (
            exact_keys(
                "unavailable_model_ids",
                "nla_temporal_validation_claimed",
                "future_indicator_imputation_performed",
            )
            and diagnostics["unavailable_model_ids"] == ["A2", "P0", "P1"]
            and diagnostics["nla_temporal_validation_claimed"] is False
            and diagnostics["future_indicator_imputation_performed"] is False
        )
    elif component_id == "E5_clustered_inference":
        valid = (
            exact_keys(
                "bootstrap_replicates",
                "cluster_unit",
                "hypothesis_count",
                "family_universe_sizes",
                "unavailable_model_ids",
                "holm_universe_reduced",
                "row_level_independence_assumed",
            )
            and type(diagnostics["bootstrap_replicates"]) is int
            and diagnostics["bootstrap_replicates"] == 5000
            and diagnostics["cluster_unit"] == "holdout_group_id"
            and diagnostics["hypothesis_count"] == 27
            and diagnostics["family_universe_sizes"]
            == {"A": 3, "B": 78, "C": 1, "D": 9, "E": 1}
            and diagnostics["unavailable_model_ids"] == ["P0", "P1", "A2"]
            and diagnostics["holm_universe_reduced"] is False
            and diagnostics["row_level_independence_assumed"] is False
        )
    elif component_id == "E6_matched_degradation":
        if status == "completed":
            valid = (
                exact_keys(
                    "scenario_count",
                    "ordered_seed_slot_count",
                    "common_mask_required",
                    "refit_performed",
                )
                and type(diagnostics["scenario_count"]) is int
                and diagnostics["scenario_count"] == 13
                and type(diagnostics["ordered_seed_slot_count"]) is int
                and diagnostics["ordered_seed_slot_count"] == 5
                and diagnostics["common_mask_required"] is True
                and diagnostics["refit_performed"] is False
            )
        else:
            valid = (
                exact_keys(
                    "component_contract_sha256",
                    "reason",
                    "intent_row_count",
                    "common_origin_count",
                    "site_count",
                    "family_b_cell_count",
                    "ordered_seed_slot_count",
                    "refit_performed",
                )
                and _is_sha256(
                    diagnostics["component_contract_sha256"],
                    expected=COMPONENT_CONTRACT_SHA256[component_id],
                )
                and diagnostics["reason"]
                == "M0_or_P1_model_unavailable_under_formal_lock"
                and _is_nonnegative_int(diagnostics["intent_row_count"])
                and _is_nonnegative_int(diagnostics["common_origin_count"])
                and _is_nonnegative_int(diagnostics["site_count"])
                and diagnostics["family_b_cell_count"] == 78
                and diagnostics["ordered_seed_slot_count"] == 5
                and diagnostics["refit_performed"] is False
            )
    elif component_id == "E7_anfis_ablation":
        valid = (
            exact_keys(
                "component_contract_sha256",
                "input_row_count",
                "available_metric_group_count",
                "unavailable_models",
                "refit_performed",
                "silent_row_deletion",
            )
            and _is_sha256(
                diagnostics["component_contract_sha256"],
                expected=COMPONENT_CONTRACT_SHA256[component_id],
            )
            and _is_nonnegative_int(diagnostics["input_row_count"])
            and _is_nonnegative_int(diagnostics["available_metric_group_count"])
            and diagnostics["unavailable_models"] == ["P0", "P1"]
            and diagnostics["refit_performed"] is False
            and diagnostics["silent_row_deletion"] is False
        )
    elif component_id == "E8_uncertainty":
        valid = (
            exact_keys(
                "component_contract_sha256",
                "locked_factor_count",
                "evaluation_attempt_row_count",
                "uncertainty_applicable_model_ids",
                "a2_slot_count",
                "calibration_table_received",
                "q_fit_or_recompute_performed",
                "q_refit_in_evaluation",
                "confirmatory_family_E_status",
                "holm_family_E_universe_size",
                "p1_substitution_performed",
            )
            and _is_sha256(
                diagnostics["component_contract_sha256"],
                expected=COMPONENT_CONTRACT_SHA256[component_id],
            )
            and diagnostics["locked_factor_count"] == 90
            and _is_nonnegative_int(diagnostics["evaluation_attempt_row_count"])
            and diagnostics["uncertainty_applicable_model_ids"] == ["A0", "A1"]
            and diagnostics["a2_slot_count"] == 0
            and diagnostics["calibration_table_received"] is False
            and diagnostics["q_fit_or_recompute_performed"] is False
            and diagnostics["q_refit_in_evaluation"] is False
            and diagnostics["confirmatory_family_E_status"]
            == "not_estimable_model_unavailable"
            and diagnostics["holm_family_E_universe_size"] == 1
            and diagnostics["p1_substitution_performed"] is False
            and status == "completed_unavailable"
        )
    elif component_id == "E9_planning_inference":
        unavailable_keys = {
            "component_contract_sha256",
            "unavailable_reason",
            "model_id",
            "intent_row_count",
            "common_origin_count",
            "site_count",
            "holdout_group_count",
            "failure_ledger_row_count",
            "intended_action_seed_row_count",
            "holm_universe_size",
            "refit_performed",
        }
        available_keys = {
            "component_contract_sha256",
            "input_row_count",
            "shared_success_row_count",
            "failure_row_count",
            "bootstrap_replicates",
            "holm_universe_size",
            "refit_performed",
        }
        digest_valid = _is_sha256(
            diagnostics.get("component_contract_sha256"),
            expected=COMPONENT_CONTRACT_SHA256[component_id],
        )
        if set(diagnostics) == unavailable_keys:
            valid = (
                status == "completed_unavailable"
                and digest_valid
                and diagnostics["unavailable_reason"] == "P1_model_unavailable"
                and diagnostics["model_id"] == "P1"
                and _is_nonnegative_int(diagnostics["intent_row_count"])
                and _is_nonnegative_int(diagnostics["common_origin_count"])
                and _is_nonnegative_int(diagnostics["site_count"])
                and _is_nonnegative_int(diagnostics["holdout_group_count"])
                and diagnostics["failure_ledger_row_count"] == 27
                and diagnostics["intended_action_seed_row_count"]
                == diagnostics["intent_row_count"] * 9 * 5
                and diagnostics["holm_universe_size"] == 9
                and diagnostics["refit_performed"] is False
            )
        else:
            valid = (
                set(diagnostics) == available_keys
                and digest_valid
                and _is_nonnegative_int(diagnostics["input_row_count"])
                and _is_nonnegative_int(diagnostics["shared_success_row_count"])
                and _is_nonnegative_int(diagnostics["failure_row_count"])
                and diagnostics["shared_success_row_count"]
                <= diagnostics["input_row_count"]
                and diagnostics["failure_row_count"]
                <= diagnostics["input_row_count"]
                and (
                    (
                        status == "completed"
                        and diagnostics["shared_success_row_count"] > 0
                    )
                    or (
                        status == "completed_unavailable"
                        and diagnostics["shared_success_row_count"] == 0
                    )
                )
                and type(diagnostics["bootstrap_replicates"]) is int
                and diagnostics["bootstrap_replicates"] == 2000
                and type(diagnostics["holm_universe_size"]) is int
                and diagnostics["holm_universe_size"] == 9
                and diagnostics["refit_performed"] is False
            )
    elif component_id == "E10_evidence_matrix":
        valid = (
            exact_keys(
                "component_contract_sha256",
                "evidence_sha256",
                "prior_stage_count",
                "prior_component_count",
                "stage_evidence_row_count",
                "public_test_count",
                "public_skip_count",
                "openapi_path_count",
                "operational_commands_run",
                "git_operations_run",
                "dvc_operations_run",
            )
            and _is_sha256(
                diagnostics["component_contract_sha256"],
                expected=COMPONENT_CONTRACT_SHA256[component_id],
            )
            and _is_sha256(diagnostics["evidence_sha256"])
            and type(diagnostics["prior_stage_count"]) is int
            and diagnostics["prior_stage_count"] == 9
            and type(diagnostics["prior_component_count"]) is int
            and diagnostics["prior_component_count"] == 10
            and type(diagnostics["stage_evidence_row_count"]) is int
            and diagnostics["stage_evidence_row_count"] == 11
            and _is_nonnegative_int(diagnostics["public_test_count"])
            and _is_nonnegative_int(diagnostics["public_skip_count"])
            and diagnostics["public_skip_count"] <= diagnostics["public_test_count"]
            and _is_nonnegative_int(diagnostics["openapi_path_count"])
            and type(diagnostics["operational_commands_run"]) is int
            and diagnostics["operational_commands_run"] == 0
            and type(diagnostics["git_operations_run"]) is int
            and diagnostics["git_operations_run"] == 0
            and type(diagnostics["dvc_operations_run"]) is int
            and diagnostics["dvc_operations_run"] == 0
        )
    else:
        valid = False
    if not valid:
        raise ClosureBenchmarkError(
            f"E0-U component diagnostics contract drifted: {component_id}:{status}"
        )
    return copy.deepcopy(diagnostics)


def _validate_component_result(
    raw: Any,
    *,
    component_id: str,
    stage_id: str,
    output_tables: Sequence[str],
    required_nonempty_tables: Sequence[str] = (),
    completed_nonempty_tables: Sequence[str] = (),
    unavailable_nonempty_tables: Sequence[str] = (),
    unavailable_empty_tables: Sequence[str] = (),
) -> dict[str, Any]:
    import pandas as pd

    exact_keys = {
        "component_id",
        "stage_id",
        "status",
        "artifacts",
        "tables",
        "diagnostics",
        "outcome_paths_opened",
        "writes_performed",
    }
    if not isinstance(raw, Mapping) or set(raw) != exact_keys:
        raise ClosureBenchmarkError(f"E0-U component result keys drifted: {component_id}")
    result = dict(raw)
    expected = {
        "component_id": component_id,
        "stage_id": stage_id,
        "outcome_paths_opened": True,
        "writes_performed": False,
    }
    for key, value in expected.items():
        if type(result.get(key)) is not type(value) or result.get(key) != value:
            raise ClosureBenchmarkError(
                f"E0-U component result field drifted: {component_id}:{key}"
            )
    if result.get("status") not in {"completed", "completed_unavailable"}:
        raise ClosureBenchmarkError(f"E0-U component is not terminal: {component_id}")
    diagnostics = _validate_component_diagnostics(
        result.get("diagnostics"),
        component_id=component_id,
        status=cast(str, result["status"]),
    )
    artifacts_raw = result.get("artifacts")
    tables_raw = result.get("tables")
    if not isinstance(artifacts_raw, Mapping) or not isinstance(tables_raw, Mapping):
        raise ClosureBenchmarkError(f"E0-U component payload mappings drifted: {component_id}")
    expected_table_names = tuple(output_tables)
    if (
        not expected_table_names
        or len(set(expected_table_names)) != len(expected_table_names)
        or any(type(name) is not str or not name for name in expected_table_names)
        or set(tables_raw) != set(expected_table_names)
    ):
        raise ClosureBenchmarkError(
            f"E0-U component output table scope drifted: {component_id}"
        )
    policy_names = {
        *required_nonempty_tables,
        *completed_nonempty_tables,
        *unavailable_nonempty_tables,
        *unavailable_empty_tables,
    }
    if not policy_names.issubset(set(expected_table_names)):
        raise ClosureBenchmarkError(
            f"E0-U component output table policy drifted: {component_id}"
        )
    artifacts: dict[str, dict[str, Any]] = {}
    artifact_contract = COMPONENT_ARTIFACT_CONTRACTS.get(component_id)
    if artifact_contract is None or artifact_contract.get("stage_id") != stage_id:
        raise ClosureBenchmarkError(
            f"E0-U component artifact contract is absent: {component_id}"
        )
    expected_artifact_paths = cast(
        tuple[str, ...], artifact_contract["artifact_paths"]
    )
    expected_artifact_formats = dict(
        zip(
            expected_artifact_paths,
            cast(tuple[str, ...], artifact_contract["artifact_formats"]),
            strict=True,
        )
    )
    manifest_last_path = cast(
        str | None, artifact_contract["manifest_last_path"]
    )
    if set(artifacts_raw) != set(expected_artifact_paths):
        raise ClosureBenchmarkError(
            f"E0-U component artifact ownership drifted: {component_id}"
        )
    stage_output_paths = set(
        next(stage.output_paths for stage in BATCH_STAGES if stage.stage_id == stage_id)
    )
    for path, envelope_raw in artifacts_raw.items():
        if type(path) is not str or not path or not isinstance(envelope_raw, Mapping):
            raise ClosureBenchmarkError(f"E0-U artifact binding drifted: {component_id}")
        if path not in stage_output_paths:
            raise ClosureBenchmarkError(
                f"E0-U artifact escaped stage scope: {component_id}:{path}"
            )
        envelope = dict(envelope_raw)
        if set(envelope) != {"format", "payload", "manifest_last"}:
            raise ClosureBenchmarkError(f"E0-U artifact envelope drifted: {path}")
        if envelope.get("format") != expected_artifact_formats[path]:
            raise ClosureBenchmarkError(f"E0-U artifact format drifted: {path}")
        if (
            type(envelope.get("manifest_last")) is not bool
            or envelope.get("manifest_last") != (path == manifest_last_path)
        ):
            raise ClosureBenchmarkError(f"E0-U artifact manifest flag drifted: {path}")
        payload = envelope.get("payload")
        if not isinstance(payload, (pd.DataFrame, Mapping, str, bytes)):
            raise ClosureBenchmarkError(f"E0-U artifact payload drifted: {path}")
        artifacts[path] = {
            "format": envelope["format"],
            "payload": payload.copy(deep=True)
            if isinstance(payload, pd.DataFrame)
            else copy.deepcopy(payload),
            "manifest_last": envelope["manifest_last"],
        }
    tables: dict[str, Any] = {}
    for name, frame in tables_raw.items():
        if type(name) is not str or not name or type(frame) is not pd.DataFrame:
            raise ClosureBenchmarkError(f"E0-U component table drifted: {component_id}")
        tables[name] = frame.copy(deep=True)
    nonempty = set(required_nonempty_tables)
    empty: set[str] = set()
    if result["status"] == "completed":
        nonempty.update(completed_nonempty_tables)
    else:
        nonempty.update(unavailable_nonempty_tables)
        empty.update(unavailable_empty_tables)
    if nonempty.intersection(empty):
        raise ClosureBenchmarkError(
            f"E0-U component output table policy overlaps: {component_id}"
        )
    for name in nonempty:
        if tables[name].empty:
            raise ClosureBenchmarkError(
                f"E0-U required output table is empty: {component_id}:{name}"
            )
    for name in empty:
        if not tables[name].empty:
            raise ClosureBenchmarkError(
                f"E0-U unavailable output table invented rows: {component_id}:{name}"
            )
    return {
        "component_id": component_id,
        "stage_id": stage_id,
        "status": result["status"],
        "artifacts": artifacts,
        "tables": tables,
        "diagnostics": diagnostics,
        "outcome_paths_opened": True,
        "writes_performed": False,
    }


def _merge_component_result(
    context: dict[str, Any],
    result: Mapping[str, Any],
    artifacts: dict[str, dict[str, Any]],
    *,
    allow_prediction_replacement: bool = False,
) -> None:
    tables = cast(dict[str, Any], context["tables"])
    result_tables = cast(Mapping[str, Any], result["tables"])
    for name, frame in result_tables.items():
        if name in tables and not (allow_prediction_replacement and name == "predictions_long"):
            raise ClosureBenchmarkError(f"E0-U logical table clobber rejected: {name}")
        tables[name] = frame.copy(deep=True)
    result_artifacts = cast(Mapping[str, dict[str, Any]], result["artifacts"])
    for path, envelope in result_artifacts.items():
        if path in artifacts:
            raise ClosureBenchmarkError(f"E0-U artifact clobber rejected: {path}")
        artifacts[path] = copy.deepcopy(envelope)


def _aggregate_stage_results(
    stage_id: str, parts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    if not parts:
        raise ClosureBenchmarkError(f"E0-U stage has no component result: {stage_id}")
    if len(parts) == 1:
        return copy.deepcopy(dict(parts[0]))
    if stage_id != "E4" or tuple(part.get("component_id") for part in parts) != (
        "E4_reference_targets",
        "E4_trophic_evaluation",
    ):
        raise ClosureBenchmarkError(
            f"E0-U composite component order drifted: {stage_id}"
        )
    artifacts: dict[str, Any] = {}
    tables: dict[str, Any] = {}
    component_summaries: list[dict[str, Any]] = []
    for part in parts:
        if part.get("stage_id") != stage_id:
            raise ClosureBenchmarkError(f"E0-U composite stage identity drifted: {stage_id}")
        for path, envelope in cast(Mapping[str, Any], part["artifacts"]).items():
            if path in artifacts:
                raise ClosureBenchmarkError(f"E0-U composite artifact collision: {path}")
            artifacts[path] = copy.deepcopy(envelope)
        for name, frame in cast(Mapping[str, Any], part["tables"]).items():
            if name in tables:
                raise ClosureBenchmarkError(f"E0-U composite table collision: {name}")
            tables[name] = frame.copy(deep=True)
        component_summaries.append(
            {
                "component_id": part["component_id"],
                "status": part["status"],
                "artifact_paths": sorted(cast(Mapping[str, Any], part["artifacts"])),
                "table_names": sorted(cast(Mapping[str, Any], part["tables"])),
            }
        )
    expected_e4_tables = {
        "trophic_reference_targets",
        "trophic_proxy_metrics",
        "carlson_reference_metrics",
        "trophic_confusion_matrices",
        "nla_semantic_metrics",
    }
    if set(tables) != expected_e4_tables:
        raise ClosureBenchmarkError("E0-U E4 composite output table scope drifted")
    return {
        "component_id": f"{stage_id}_composite",
        "stage_id": stage_id,
        "status": (
            "completed_unavailable"
            if any(part["status"] == "completed_unavailable" for part in parts)
            else "completed"
        ),
        "artifacts": artifacts,
        "tables": tables,
        "diagnostics": {"component_results": component_summaries},
        "outcome_paths_opened": True,
        "writes_performed": False,
    }


def _validate_complete_artifact_set(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> None:
    stage_paths = {
        stage.stage_id: set(stage.output_paths)
        for stage in BATCH_STAGES
        if stage.stage_id != "E0-U"
    }
    expected = set().union(*stage_paths.values())
    if tuple(sorted(expected)) != EXPECTED_ARTIFACT_PATHS:
        raise ClosureBenchmarkError("E0-U sealed artifact path contract drifted")
    if set(artifacts) != expected:
        missing = sorted(expected.difference(artifacts))
        extra = sorted(set(artifacts).difference(expected))
        raise ClosureBenchmarkError(
            f"E0-U final artifact scope drifted; missing={missing}, extra={extra}"
        )
    for stage_id, paths in stage_paths.items():
        terminal = sum(bool(artifacts[path]["manifest_last"]) for path in paths)
        if terminal != 1:
            raise ClosureBenchmarkError(
                f"E0-U stage manifest-last count drifted: {stage_id}:{terminal}"
            )


def _artifact_payload_bytes(path: str, envelope: Mapping[str, Any]) -> bytes:
    """Serialize one envelope using the exact E0-U publication dialect."""

    import pandas as pd

    expected_format = EXPECTED_ARTIFACT_FORMATS.get(path)
    format_name = envelope.get("format")
    payload = envelope.get("payload")
    if format_name != expected_format:
        raise ClosureBenchmarkError(f"E0-U publication format drifted: {path}")
    if format_name == "csv":
        if type(payload) is not pd.DataFrame:
            raise ClosureBenchmarkError(f"E0-U CSV payload is not a DataFrame: {path}")
        return cast(Any, payload).to_csv(
            index=False,
            lineterminator="\n",
            na_rep="",
            float_format="%.17g",
        ).encode("utf-8")
    if format_name == "parquet":
        if type(payload) is not pd.DataFrame:
            raise ClosureBenchmarkError(
                f"E0-U Parquet payload is not a DataFrame: {path}"
            )
        stream = io.BytesIO()
        cast(Any, payload).to_parquet(
            stream,
            engine="pyarrow",
            compression="zstd",
            index=False,
        )
        return stream.getvalue()
    if format_name == "json":
        if not isinstance(payload, Mapping):
            raise ClosureBenchmarkError(f"E0-U JSON payload is not a mapping: {path}")
        return _canonical_json_bytes(dict(payload))
    if format_name == "markdown":
        if type(payload) is not str:
            raise ClosureBenchmarkError(f"E0-U Markdown payload is not text: {path}")
        return payload.encode("utf-8")
    if format_name == "xml":
        if type(payload) is bytes:
            return payload
        if type(payload) is str:
            return payload.encode("utf-8")
        raise ClosureBenchmarkError(f"E0-U XML payload is not bytes/text: {path}")
    raise ClosureBenchmarkError(f"E0-U publication format is unsupported: {path}")


def _expected_artifact_bytes(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, bytes]:
    _validate_complete_artifact_set(artifacts)
    return {
        path: _artifact_payload_bytes(path, artifacts[path])
        for path in EXPECTED_ARTIFACT_PATHS
    }


def _artifact_content_records(
    expected_bytes: Mapping[str, bytes],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "path": path,
            "bytes": len(expected_bytes[path]),
            "sha256": _sha256_bytes(expected_bytes[path]),
        }
        for path in EXPECTED_ARTIFACT_PATHS
    )


def _published_artifact_snapshot(
    expected_bytes: Mapping[str, bytes], *, repo_root: Path
) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for path_text in EXPECTED_ARTIFACT_PATHS:
        path = Path(path_text)
        payload, metadata = _read_anchored_regular_bytes(
            path,
            repo_root=repo_root,
            expected_mode=0o644,
            expected_nlink=1,
        )
        if payload != expected_bytes[path_text]:
            raise ClosureBenchmarkError(
                f"E0-U published artifact bytes drifted: {path_text}"
            )
        records.append(
            {
                "path": path_text,
                "bytes": len(payload),
                "sha256": _sha256_bytes(payload),
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": stat.S_IMODE(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
            }
        )
    return tuple(records)


def _require_terminal_published_artifact_snapshot(
    expected_bytes: Mapping[str, bytes],
    baseline: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
) -> tuple[dict[str, Any], ...]:
    observed = _published_artifact_snapshot(
        expected_bytes,
        repo_root=repo_root,
    )
    expected = tuple(dict(record) for record in baseline)
    if observed != expected:
        raise ClosureBenchmarkError(
            "E0-U published artifacts changed before the terminal success boundary"
        )
    return observed


def published_artifact_paths_sha256(paths: Sequence[str]) -> str:
    """Return the receipt digest only for the exact sealed set of 52 paths."""

    if len(paths) != 52 or any(type(path) is not str or not path for path in paths):
        raise ClosureBenchmarkError("E0-U published artifact paths drifted")
    observed = tuple(sorted(paths))
    if (
        len(set(paths)) != 52
        or observed != EXPECTED_ARTIFACT_PATHS
    ):
        raise ClosureBenchmarkError("E0-U published artifact paths drifted")
    return _sha256_bytes(_canonical_json_bytes(list(observed)))


def _validate_publication_receipt(
    raw: Any,
    *,
    execution_id: str,
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != PUBLICATION_RECEIPT_KEYS:
        raise ClosureBenchmarkError("E0-U publication receipt keys drifted")
    published = dict(raw)
    expected = {
        "status": "sealed_batch_artifacts_published",
        "execution_id": execution_id,
        "batch_contract_sha256": sealed_batch_contract_sha256(),
        "artifact_count": 52,
        "published_artifact_paths_sha256": published_artifact_paths_sha256(
            tuple(artifacts)
        ),
        "stage_count": 10,
        "one_shot_consumed": True,
        "guard_released": True,
        "rollback_performed": False,
        "manifest_written_last": True,
        "writes_performed": True,
    }
    for key, value in expected.items():
        if type(published.get(key)) is not type(value) or published.get(key) != value:
            raise ClosureBenchmarkError(f"E0-U publication receipt drifted: {key}")
    return published


def _validate_post_publication_audit(
    raw: Any,
    *,
    execution_id: str,
    expected_bytes: Mapping[str, bytes],
    observed_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != PUBLICATION_AUDIT_KEYS:
        raise ClosureBenchmarkError("E0-U post-publication audit keys drifted")
    audit = dict(raw)
    content_records = _artifact_content_records(expected_bytes)
    physical_records = tuple(dict(record) for record in observed_records)
    if any(set(record) != PUBLICATION_AUDIT_RECORD_KEYS for record in physical_records):
        raise ClosureBenchmarkError("E0-U physical publication record keys drifted")
    expected = {
        "status": "sealed_batch_artifacts_physically_validated",
        "execution_id": execution_id,
        "batch_contract_sha256": sealed_batch_contract_sha256(),
        "artifact_count": 52,
        "published_artifact_paths_sha256": EXPECTED_ARTIFACT_PATHS_SHA256,
        "artifact_payloads_sha256": _sha256_bytes(
            _canonical_json_bytes(list(content_records))
        ),
        "physical_records": list(physical_records),
        "physical_records_sha256": _sha256_bytes(
            _canonical_json_bytes(list(physical_records))
        ),
        "publication_order": list(EXPECTED_PUBLICATION_ORDER),
        "publication_order_sha256": EXPECTED_PUBLICATION_ORDER_SHA256,
        "stage_count": 10,
        "one_shot_consumed": True,
        "guard_released": True,
        "publication_guard_present": False,
        "rollback_performed": False,
        "manifest_written_last": True,
        "writes_performed": True,
    }
    if audit != expected:
        raise ClosureBenchmarkError("E0-U post-publication physical audit drifted")
    return audit


def _execute_with_verified_e0_u_authority(
    authority: Mapping[str, Any],
    readiness: Mapping[str, Any],
    runtime_state: Mapping[str, Any],
) -> dict[str, Any]:
    # No component or outcome may be opened until the authority returned.
    if not sys.dont_write_bytecode:
        raise ClosureBenchmarkError("E0-U sealed execution requires -B")
    _validate_authority_source_bindings(authority, readiness)
    public_authority = _public_authority_payload(authority)
    components = _load_ready_components(readiness)
    support_source_records = _load_ready_support_sources(readiness, authority)
    context_builder, context_input_preflight, context_builder_source = _load_ready_context_builder(
        readiness, authority
    )
    _recapture_runtime_environment(runtime_state)
    input_contract = sealed_batch_contract()
    try:
        raw_context_preflight = context_input_preflight(
            authority=copy.deepcopy(public_authority),
            sealed_batch_contract=input_contract,
            repo_root=PROJECT_ROOT,
        )
    except BaseException as exc:
        raise ClosureBenchmarkError(
            "E0-U Phase 3 input preflight failed before outcome logging"
        ) from exc
    _recapture_runtime_environment(runtime_state)
    context_preflight = _validate_phase3_context_input_preflight(
        raw_context_preflight,
        expected_overlay_record=cast(
            Mapping[str, Any], authority[E0_U_PHASE3_OVERLAY_RECORD_KEY]
        ),
    )
    preflights: list[dict[str, Any]] = []
    for component, module in components:
        preflight = getattr(module, component.preflight_api)
        try:
            raw = preflight(
                authority=copy.deepcopy(public_authority),
                sealed_batch_contract=sealed_batch_contract(),
                repo_root=PROJECT_ROOT,
            )
        except BaseException as exc:
            raise ClosureBenchmarkError(
                f"E0-U component preflight failed: {component.component_id}"
            ) from exc
        _recapture_runtime_environment(runtime_state)
        if not isinstance(raw, Mapping):
            raise ClosureBenchmarkError(
                f"E0-U component preflight is not a mapping: {component.component_id}"
            )
        result = dict(raw)
        expected = {
            "component_id": component.component_id,
            "stage_id": component.stage_id,
            "status": "ready",
            "outcome_paths_opened": False,
            "writes_performed": False,
        }
        for key, value in expected.items():
            if type(result.get(key)) is not type(value) or result.get(key) != value:
                raise ClosureBenchmarkError(
                    f"E0-U component preflight field drifted: {component.component_id}:{key}"
                )
        digest = result.get("contract_sha256")
        if type(digest) is not str or digest != sealed_batch_contract_sha256():
            raise ClosureBenchmarkError(
                f"E0-U component preflight digest drifted: {component.component_id}"
            )
        preflights.append(result)
    source_baseline = runner_source_record(repo_root=PROJECT_ROOT)
    recaptured_readiness = collect_sealed_batch_component_readiness(
        repo_root=PROJECT_ROOT
    )
    if recaptured_readiness != dict(readiness):
        raise ClosureBenchmarkError("E0-U component source changed before outcome opening")
    _recapture_authority_source(authority)
    factory = authority.get(E0_U_CONTEXT_FACTORY_API)
    publisher = authority.get(E0_U_TRANSACTION_PUBLISHER_API)
    auditor = authority.get(E0_U_PUBLICATION_AUDITOR_API)
    if not callable(factory) or not callable(publisher) or not callable(auditor):
        raise ClosureBenchmarkError(
            "E0-U context factory, publisher, or physical auditor is absent"
        )
    contract = sealed_batch_contract()
    _recapture_runtime_environment(runtime_state)
    _require_clean_repository_snapshot_before_outcome_log(public_authority)
    _recapture_runtime_environment(runtime_state)
    try:
        opened = factory(
            authority=copy.deepcopy(public_authority),
            sealed_batch_contract=contract,
            repo_root=PROJECT_ROOT,
            context_builder=context_builder,
        )
    except BaseException as exc:
        raise ClosureBenchmarkError("E0-U sealed batch context opening failed") from exc
    _recapture_runtime_environment(runtime_state)
    context = _validate_opened_batch_context(opened)
    artifacts: dict[str, dict[str, Any]] = {}
    _recapture_runtime_environment(runtime_state)
    e1_raw = _execute_e1_locked_benchmark_stage(
        public_authority,
        contract,
        _component_context(
            context, component_id="E1_benchmark_scientific_executor"
        ),
        PROJECT_ROOT,
    )
    _recapture_runtime_environment(runtime_state)
    e1 = _validate_component_result(
        e1_raw,
        component_id="E1_benchmark_scientific_executor",
        stage_id="E1",
        output_tables=E1_OUTPUT_TABLES,
        required_nonempty_tables=E1_REQUIRED_NONEMPTY_TABLES,
    )
    _merge_component_result(
        context, e1, artifacts, allow_prediction_replacement=True
    )
    cast(dict[str, Any], context["stage_results"])["E1"] = copy.deepcopy(e1)

    stage_parts: list[dict[str, Any]] = []
    active_stage: str | None = None
    for index, (component, module) in enumerate(components):
        if active_stage is None:
            active_stage = component.stage_id
        elif active_stage != component.stage_id:
            raise ClosureBenchmarkError("E0-U component stage order is not contiguous")
        execute = getattr(module, component.execute_api)
        try:
            raw = execute(
                authority=copy.deepcopy(public_authority),
                sealed_batch_contract=contract,
                batch_context=_component_context(
                    context, component_id=component.component_id
                ),
                repo_root=PROJECT_ROOT,
            )
        except BaseException as exc:
            raise ClosureBenchmarkError(
                f"E0-U component execution failed: {component.component_id}"
            ) from exc
        _recapture_runtime_environment(runtime_state)
        result = _validate_component_result(
            raw,
            component_id=component.component_id,
            stage_id=component.stage_id,
            output_tables=component.output_tables,
            required_nonempty_tables=component.required_nonempty_tables,
            completed_nonempty_tables=component.completed_nonempty_tables,
            unavailable_nonempty_tables=component.unavailable_nonempty_tables,
            unavailable_empty_tables=component.unavailable_empty_tables,
        )
        _merge_component_result(context, result, artifacts)
        stage_parts.append(result)
        next_stage = (
            components[index + 1][0].stage_id if index + 1 < len(components) else None
        )
        if next_stage != component.stage_id:
            cast(dict[str, Any], context["stage_results"])[component.stage_id] = (
                _aggregate_stage_results(component.stage_id, stage_parts)
            )
            stage_parts = []
            active_stage = next_stage

    _validate_complete_artifact_set(artifacts)
    stage_results = cast(dict[str, Any], context["stage_results"])
    if set(stage_results) != {f"E{index}" for index in range(1, 11)}:
        raise ClosureBenchmarkError("E0-U terminal stage-result set drifted")
    for stage_id, expected_tables in STAGE_OUTPUT_TABLES.items():
        result_tables = stage_results[stage_id].get("tables")
        if not isinstance(result_tables, Mapping) or set(result_tables) != set(
            expected_tables
        ):
            raise ClosureBenchmarkError(
                f"E0-U terminal stage output table scope drifted: {stage_id}"
            )
    if runner_source_record(repo_root=PROJECT_ROOT) != source_baseline:
        raise ClosureBenchmarkError("E0-U runner source changed during the sealed batch")
    final_readiness = collect_sealed_batch_component_readiness(repo_root=PROJECT_ROOT)
    if final_readiness != dict(readiness):
        raise ClosureBenchmarkError("E0-U component source changed during the sealed batch")
    _recapture_authority_source(authority)
    expected_artifact_bytes = _expected_artifact_bytes(artifacts)
    if _context_builder_source_record(
        repo_root=PROJECT_ROOT
    ) != dict(context_builder_source):
        raise ClosureBenchmarkError(
            "E0-U context-builder source changed during the sealed batch"
        )
    if [
        _support_source_record(spec, repo_root=PROJECT_ROOT)
        for spec in SEALED_SUPPORT_SOURCES
    ] != list(support_source_records):
        raise ClosureBenchmarkError(
            "E0-U support sources changed during the sealed batch"
        )
    _recapture_runtime_environment(runtime_state)
    try:
        published_raw = publisher(
            authority=copy.deepcopy(public_authority),
            sealed_batch_contract=contract,
            batch_context=_component_context(
                context, component_id="E0-U_publication"
            ),
            stage_results=copy.deepcopy(stage_results),
            artifacts=copy.deepcopy(artifacts),
            serialized_artifacts=copy.deepcopy(expected_artifact_bytes),
            repo_root=PROJECT_ROOT,
        )
    except BaseException as exc:
        raise ClosureBenchmarkError("E0-U batch publication transaction failed") from exc
    _recapture_runtime_environment(runtime_state)
    published = _validate_publication_receipt(
        published_raw,
        execution_id=cast(str, context["execution_id"]),
        artifacts=artifacts,
    )
    physical_before = _published_artifact_snapshot(
        expected_artifact_bytes,
        repo_root=PROJECT_ROOT,
    )
    _recapture_runtime_environment(runtime_state)
    try:
        audit_raw = auditor(
            authority=copy.deepcopy(public_authority),
            sealed_batch_contract=contract,
            batch_context=_component_context(
                context, component_id="E0-U_publication"
            ),
            stage_results=copy.deepcopy(stage_results),
            artifacts=copy.deepcopy(artifacts),
            serialized_artifacts=copy.deepcopy(expected_artifact_bytes),
            publication_receipt=copy.deepcopy(published),
            repo_root=PROJECT_ROOT,
        )
    except BaseException as exc:
        raise ClosureBenchmarkError(
            "E0-U post-publication physical audit failed"
        ) from exc
    _recapture_runtime_environment(runtime_state)
    publication_audit = _validate_post_publication_audit(
        audit_raw,
        execution_id=cast(str, context["execution_id"]),
        expected_bytes=expected_artifact_bytes,
        observed_records=physical_before,
    )
    physical_after = _published_artifact_snapshot(
        expected_artifact_bytes,
        repo_root=PROJECT_ROOT,
    )
    if physical_after != physical_before:
        raise ClosureBenchmarkError(
            "E0-U published artifacts changed during the physical audit"
        )
    if runner_source_record(repo_root=PROJECT_ROOT) != source_baseline:
        raise ClosureBenchmarkError("E0-U runner source changed during publication")
    if collect_sealed_batch_component_readiness(
        repo_root=PROJECT_ROOT
    ) != dict(readiness):
        raise ClosureBenchmarkError("E0-U component source changed during publication")
    _recapture_authority_source(authority)
    _recapture_runtime_environment(runtime_state)
    result = {
        "gate": UNBLINDING_GATE,
        "status": "sealed_batch_completed",
        "execution_id": context["execution_id"],
        "batch_contract_sha256": sealed_batch_contract_sha256(),
        "preflight_count": len(preflights),
        "stage_count": 10,
        "artifact_count": len(artifacts),
        "completed_unavailable_stages": sorted(
            stage_id
            for stage_id, result in stage_results.items()
            if result["status"] == "completed_unavailable"
        ),
        "outcome_paths_opened": True,
        "writes_performed": True,
        "publication": published,
        "publication_audit": publication_audit,
    }
    _require_terminal_published_artifact_snapshot(
        expected_artifact_bytes,
        physical_before,
        repo_root=PROJECT_ROOT,
    )
    return result


def execute_sealed_batch() -> dict[str, Any]:
    # The authenticated, outcome-free bootstrap establishes the exact process,
    # repository, remote and future-authority source. E0-U require is then the
    # first capability-bearing operation; no scientific dependency is importable
    # before it returns.
    _require_sealed_startup_environment()
    authority_source = _git_bound_e0_u_authority_source_record()
    authority = _require_e0_u_authority_first(authority_source)
    runtime_state = _activate_sealed_runtime_environment(authority)
    readiness = collect_sealed_batch_component_readiness(repo_root=PROJECT_ROOT)
    if readiness["missing_component_count"] != 0:
        raise ClosureBenchmarkError(
            "E0-U sealed batch components are incomplete; no outcome I/O occurred: "
            + json.dumps(
                readiness["missing_components"],
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    return _execute_with_verified_e0_u_authority(
        authority, readiness, runtime_state
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(CHECK_ONLY_MODE, action="store_true")
    modes.add_argument(SEALED_BATCH_MODE, action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = check_only() if args.check_only else execute_sealed_batch()
    except ClosureBenchmarkError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
