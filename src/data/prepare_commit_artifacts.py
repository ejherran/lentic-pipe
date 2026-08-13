#!/usr/bin/env python
"""Prepare Git and DVC artifacts before a manual commit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import shlex
import shutil
import stat
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANFIS_ABLATION_EXPECTED_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)
ANFIS_ABLATION_EXPECTED_XDG_CONFIG_HOME = (
    ANFIS_ABLATION_EXPECTED_HOME / ".config"
)
ANFIS_ABLATION_EXPECTED_XDG_CONFIG_DIRS = "/etc/xdg"


def _ensure_project_root_importable() -> None:
    """Make absolute ``src.*`` imports work for the direct script entrypoint."""
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


_ensure_project_root_importable()


DEFAULT_DVC_MANIFEST = Path("configs/dvc_artifacts.yaml")
DEFAULT_CLOSURE_DVC_MANIFEST = Path(
    "configs/closure_v1/dvc_artifacts_post_lock.yaml"
)
DEFAULT_REPORT_DIR = Path("tmp")
DEFAULT_DVC_BIN = Path(".venv/bin/dvc")
DEFAULT_DVC_SITE_CACHE_DIR = Path(".dvc/tmp/site-cache")
HASH_CHUNK_SIZE = 16 * 1024 * 1024
DEFAULT_MAX_MANIFEST_HASH_BYTES = 512 * 1024 * 1024

# E0-MV through E0-MZE are the sole exception to the normal immediate
# ``dvc add`` policy.  The model family must stay byte-exact and unregistered
# until all ten A0/A1 slots exist and exact P-E0-MZE is effective.  Keep the
# closed path inventory local to the assistant so the exception cannot grow
# through a mutable experiment module or the generic DVC inventory.
DEFERRED_DVC_MODELS_TARGET = Path("models")
DEFERRED_DVC_MODELS_POINTER = Path("models.dvc")
DEFERRED_DVC_MODELS_POINTER_SHA256 = (
    "fcb93f78cc3e60c1c7f5bcc94a1765080358e0a5176880f1efa6245fa5365e5d"
)
DEFERRED_DVC_MODELS_DIRECTORY_MD5 = "fc60851634c1345cc5dc2c9169be9e1c"
DEFERRED_DVC_MODELS_DIRECTORY_SHA256 = (
    "f40b5ca2ddfff0e99f12db5ea9a6360ea6d62830856c4a0e09ef0c870d1b1eb1"
)
DEFERRED_DVC_MODELS_DIRECTORY_BYTES = 34_581
DEFERRED_DVC_MODELS_NFILES = 248
DEFERRED_DVC_MODELS_BYTES = 124_717_666
DEFERRED_DVC_MODELS_STATUS = {
    "models.dvc": [{"changed outs": {"models": "modified"}}]
}
DEFERRED_DVC_A0_FINAL_RECORDS = (
    (
        "model",
        "models/closure_v1/anfis_ablation/A0/seed_1729.pt",
        142_911,
        "1e5c2c21b9cb69a4dfa9139fcd6058e57afd4922a19bd1b3cd071a6608897fef",
    ),
    (
        "checkpoint",
        "models/closure_v1/anfis_ablation/A0/seed_1729.checkpoint.pt",
        142_911,
        "0991ff130f694b69ae30bd37416d3ba2d63f67874b3d895976efb9e28c6ce277",
    ),
    (
        "preprocessor",
        "reports/closure_v1/02_models/A0/seed_1729_preprocessor.json",
        2_472,
        "ebffd11d392c62e68e2afbd3ee05febfd05a7411fc83ca18563c7773a51faa62",
    ),
    (
        "training_curve",
        "reports/closure_v1/02_models/A0/seed_1729_training_curve.csv",
        2_588,
        "edfb193302b0fe21708e1ff1556dcdcdf817948a8bd35cef2f90b16be9cc0ec0",
    ),
    (
        "selection_predictions",
        "data/closure_v1/development/anfis_ablation/A0/seed_1729_selection_predictions.parquet",
        64_842,
        "6ca58207a32ba345fc4611c73a879e0546a608d7d076baf8f8da057373a3a4ae",
    ),
    (
        "selection_metrics",
        "reports/closure_v1/02_models/A0/seed_1729_selection_metrics.csv",
        914,
        "f6444a2047d2032334580f1322c4f61637a9028fd0aab27815a6c7386cf860eb",
    ),
    (
        "report",
        "reports/closure_v1/02_models/A0/seed_1729_report.md",
        320,
        "6e12b1d2fc0a1fce8baf7c1f81edbeb1bdd3d013d4365d606d21cc20399d123e",
    ),
    (
        "manifest",
        "reports/closure_v1/02_models/A0/seed_1729_manifest.json",
        11_231,
        "406bf44de3ecdc49ff3d5797cbca1ec0c11ebfbdc70ba262130b85a2e58e31e2",
    ),
)
DEFERRED_DVC_A0_LIGHT_EXCLUDE_PATTERNS = tuple(
    sorted(
        f"/{path}"
        for _, path, _, _ in DEFERRED_DVC_A0_FINAL_RECORDS
        if path.startswith("reports/")
    )
)
DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT = (
    "5b24549f2d4791f6500e661f9ee404c0dc7a0866"
)
DEFERRED_DVC_A0_LIGHT_PUBLICATION_PARENT = (
    "68107147c1a67c30ecfa64c862dd39531e574a9a"
)
DEFERRED_DVC_A0_LIGHT_GIT_OIDS = {
    "reports/closure_v1/02_models/A0/seed_1729_manifest.json": (
        "9d554bc0b560b2a4e817f2eb8d07ef48424dd51a"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_preprocessor.json": (
        "b59088160da3c8d36efb984260f021959d52dddb"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_report.md": (
        "740ef989b27bcbb44c22b81d4d90f9722d8f55b3"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_selection_metrics.csv": (
        "90ee68a227fd02d5554b6a256f8bde6927ec36a6"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_training_curve.csv": (
        "6b0a676116a34a41d36956696ba945c9632abecd"
    ),
}
DEFERRED_DVC_A0_PREDICTION_POINTER = Path(
    "data/closure_v1/development/anfis_ablation/A0/"
    "seed_1729_selection_predictions.parquet.dvc"
)
DEFERRED_DVC_A0_GUARD = Path(
    "tmp/closure_v1_anfis_ablation_training/A0_seed_1729.guard"
)
ANFIS_ABLATION_REGISTRATION_INVENTORY_KEY = (
    "anfis_ablation_registration_artifacts"
)
ANFIS_ABLATION_MODEL_IDS = ("A0", "A1")
ANFIS_ABLATION_BASE_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
ANFIS_ABLATION_ORDERED_SLOTS = tuple(
    (model_id, base_seed)
    for base_seed in ANFIS_ABLATION_BASE_SEEDS
    for model_id in ANFIS_ABLATION_MODEL_IDS
)
ANFIS_ABLATION_MODEL_PATHS = tuple(
    path
    for model_id, base_seed in ANFIS_ABLATION_ORDERED_SLOTS
    for path in (
        f"models/closure_v1/anfis_ablation/{model_id}/seed_{base_seed}.pt",
        (
            "models/closure_v1/anfis_ablation/"
            f"{model_id}/seed_{base_seed}.checkpoint.pt"
        ),
    )
)
ANFIS_ABLATION_SELECTION_PREDICTION_PATHS = tuple(
    (
        "data/closure_v1/development/anfis_ablation/"
        f"{model_id}/seed_{base_seed}_selection_predictions.parquet"
    )
    for model_id, base_seed in ANFIS_ABLATION_ORDERED_SLOTS
)
ANFIS_ABLATION_SELECTION_ROOT = Path(
    "data/closure_v1/development/anfis_ablation"
)
ANFIS_ABLATION_SELECTION_POINTER_PATHS = tuple(
    f"{path}.dvc" for path in ANFIS_ABLATION_SELECTION_PREDICTION_PATHS
)
ANFIS_ABLATION_LIGHT_REPORT_PATHS = tuple(
    path
    for model_id, base_seed in ANFIS_ABLATION_ORDERED_SLOTS
    for path in (
        f"reports/closure_v1/02_models/{model_id}/seed_{base_seed}_preprocessor.json",
        f"reports/closure_v1/02_models/{model_id}/seed_{base_seed}_training_curve.csv",
        f"reports/closure_v1/02_models/{model_id}/seed_{base_seed}_selection_metrics.csv",
        f"reports/closure_v1/02_models/{model_id}/seed_{base_seed}_report.md",
        f"reports/closure_v1/02_models/{model_id}/seed_{base_seed}_manifest.json",
    )
)
ANFIS_ABLATION_MANIFEST_PATHS = tuple(
    (
        "reports/closure_v1/02_models/"
        f"{model_id}/seed_{base_seed}_manifest.json"
    )
    for model_id, base_seed in ANFIS_ABLATION_ORDERED_SLOTS
)
ANFIS_ABLATION_TRACKED_LIGHT_PATHS = tuple(
    sorted(DEFERRED_DVC_A0_LIGHT_GIT_OIDS)
)
ANFIS_ABLATION_UNTRACKED_LIGHT_PATHS = tuple(
    path
    for path in ANFIS_ABLATION_LIGHT_REPORT_PATHS
    if path not in DEFERRED_DVC_A0_LIGHT_GIT_OIDS
)
ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_COMMIT = (
    "2f0643ab6f634fdcce71f0ee0d847c448d2c61f5"
)
ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_PARENT = (
    "af233a89e22ce380f7b1f2094cdf4a92eb95b83d"
)
ANFIS_ABLATION_MZ_TRACKED_LIGHT_PATHS = tuple(
    sorted(ANFIS_ABLATION_LIGHT_REPORT_PATHS)
)
ANFIS_ABLATION_MZ_UNTRACKED_LIGHT_PATHS: tuple[str, ...] = ()
ANFIS_ABLATION_LIGHT_EXCLUDE_PATTERNS = tuple(
    f"/{path}" for path in sorted(ANFIS_ABLATION_UNTRACKED_LIGHT_PATHS)
)
ANFIS_ABLATION_REGISTRATION_DVC_TARGETS = (
    *tuple(Path(path) for path in ANFIS_ABLATION_SELECTION_PREDICTION_PATHS),
    DEFERRED_DVC_MODELS_TARGET,
)
ANFIS_ABLATION_DVC_ADD_FLAG = "--no-relink"
ANFIS_ABLATION_DVC_WRAPPER = Path(".venv/bin/dvc")
ANFIS_ABLATION_DVC_WRAPPER_BODY = (
    b"# -*- coding: utf-8 -*-\n"
    b"import re\n"
    b"import sys\n"
    b"from dvc.cli import main\n"
    b'if __name__ == "__main__":\n'
    b'    sys.argv[0] = re.sub(r"(-script\\.pyw|\\.exe)?$", "", sys.argv[0])\n'
    b"    sys.exit(main())\n"
)
ANFIS_ABLATION_DVC_PYTHON_LINK = Path(".venv/bin/python")
ANFIS_ABLATION_DVC_PYTHON_TARGET = Path("/usr/bin/python3.14")
ANFIS_ABLATION_DVC_PYTHON_BYTES = 14_424
ANFIS_ABLATION_DVC_PYTHON_SHA256 = (
    "2700be1aabe3687bd597f21b0eac3b9bbdf7417e93035255a9286c67935b59bd"
)
ANFIS_ABLATION_GIT_BIN = Path("/usr/bin/git")
ANFIS_ABLATION_GIT_BYTES = 4_899_632
ANFIS_ABLATION_GIT_SHA256 = (
    "93473c28694fd72bd889364107cd2770514de59780885a6a4aafca4d602e30ad"
)
ANFIS_ABLATION_REPO_DVC_CONFIG = Path(".dvc/config")
ANFIS_ABLATION_REPO_DVC_CONFIG_BYTES = 43
ANFIS_ABLATION_REPO_DVC_CONFIG_SHA256 = (
    "cb08c869a906d07c5b1ccf593299a0f253e0ce03303c43070b6a68124b27fda0"
)
ANFIS_ABLATION_LOCAL_DVC_CONFIG = Path(".dvc/config.local")
ANFIS_ABLATION_LOCAL_DVC_CONFIG_BYTES = 211
ANFIS_ABLATION_LOCAL_DVC_CONFIG_SHA256 = (
    "a912c374690215c7753070f68d7dfdaff8c1224b01c336aa887d6731a3bb2287"
)
ANFIS_ABLATION_REGISTRATION_GITIGNORE = Path(".gitignore")
ANFIS_ABLATION_REGISTRATION_GITIGNORE_BYTES = 6_630
ANFIS_ABLATION_REGISTRATION_GITIGNORE_SHA256 = (
    "406c174a073b9b41d610e1c434e94f4ab37b601dedd02b61cb8542bcc0eb7f52"
)
ANFIS_ABLATION_REGISTRATION_GITIGNORE_GIT_OID = (
    "8a9ff4adac268b770f93ab7333beaf3029745429"
)
ANFIS_ABLATION_REGISTRATION_GITIGNORE_ENTRY = b"/models\n"
ANFIS_ABLATION_REGISTRATION_GUARD = Path(
    "tmp/closure_v1_anfis_ablation_dvc_registration.guard"
)
ANFIS_ABLATION_REGISTRATION_MY_ACTIVE_PAYLOAD = (
    b"E0-MY exact ANFIS-ablation DVC registration\n"
)
ANFIS_ABLATION_REGISTRATION_MY_COMMIT_READY_PAYLOAD = (
    b"E0-MY exact ANFIS-ablation DVC registration commit_ready\n"
)
ANFIS_ABLATION_REGISTRATION_ACTIVE_PAYLOAD = (
    b"E0-MZE exact ANFIS-ablation DVC registration\n"
)
ANFIS_ABLATION_REGISTRATION_COMMIT_READY_PAYLOAD = (
    b"E0-MZE exact ANFIS-ablation DVC registration commit_ready\n"
)
ANFIS_ABLATION_MODELS_DVC_BACKUP = Path(
    "tmp/closure_v1_anfis_ablation_models_dvc_baseline"
)
ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP = Path(
    "tmp/closure_v1_anfis_ablation_models_dvc_baseline_bytes"
)
ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR = Path(
    "tmp/closure_v1_anfis_ablation_dvc_global_config"
)
ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR = Path(
    "tmp/closure_v1_anfis_ablation_dvc_system_config"
)
DEFERRED_DVC_H_MV_STAGED_SCOPE = {
    "configs/closure_v1/anfis_ablation_model_manifest_patch_lock.schema.json": "A",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_MANIFEST_PATCH_1.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": "M",
    "src/experiments/closure_anfis_ablation_model_manifest_patch.py": "A",
    "src/experiments/lock_closure_anfis_ablation_model_manifest_patch.py": "A",
    "src/experiments/train_closure_anfis_ablation.py": "M",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": "M",
    "tests/test_closure_anfis_ablation_model_manifest_patch.py": "A",
    "tests/test_train_closure_anfis_ablation.py": "M",
}
DEFERRED_DVC_P_MV_STAGED_SCOPE = {
    "reports/closure_v1/00_protocol/anfis_ablation_model_manifest_patch_lock.json": "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_model_manifest_patch_lock_manifest.json"
    ): "A",
}
DEFERRED_DVC_H_MV_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MV_STAGED_SCOPE
}
DEFERRED_DVC_P_MV_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MV_STAGED_SCOPE
}
DEFERRED_DVC_H_MW_STAGED_SCOPE = {
    "configs/closure_v1/anfis_ablation_model_publication_patch_lock.schema.json": "A",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_PATCH_1.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": "M",
    "src/experiments/closure_anfis_ablation_model_publication_patch.py": "A",
    "src/experiments/lock_closure_anfis_ablation_model_publication_patch.py": "A",
    "src/experiments/train_closure_anfis_ablation.py": "M",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": "M",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "A",
    "tests/test_train_closure_anfis_ablation.py": "M",
}
DEFERRED_DVC_P_MW_STAGED_SCOPE = {
    "reports/closure_v1/00_protocol/anfis_ablation_model_publication_patch_lock.json": "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_model_publication_patch_lock_manifest.json"
    ): "A",
}
DEFERRED_DVC_H_MW_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MW_STAGED_SCOPE
}
DEFERRED_DVC_P_MW_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MW_STAGED_SCOPE
}
DEFERRED_DVC_H_MX_STAGED_SCOPE = {
    "configs/closure_v1/anfis_ablation_model_publication_adoption_patch_lock.schema.json": "A",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_ADOPTION_PATCH_1.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": "M",
    "src/experiments/closure_anfis_ablation_model_publication_adoption_patch.py": "A",
    "src/experiments/lock_closure_anfis_ablation_model_publication_adoption_patch.py": "A",
    "src/experiments/train_closure_anfis_ablation.py": "M",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": "M",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py": "A",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "M",
    "tests/test_train_closure_anfis_ablation.py": "M",
}
DEFERRED_DVC_P_MX_STAGED_SCOPE = {
    "reports/closure_v1/00_protocol/anfis_ablation_model_publication_adoption_patch_lock.json": "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_model_publication_adoption_patch_lock_manifest.json"
    ): "A",
}
DEFERRED_DVC_H_MX_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MX_STAGED_SCOPE
}
DEFERRED_DVC_P_MX_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MX_STAGED_SCOPE
}
DEFERRED_DVC_H_MY_STAGED_SCOPE = {
    "configs/closure_v1/anfis_ablation_dvc_registration_patch_lock.schema.json": "A",
    "configs/closure_v1/dvc_artifacts_post_lock.yaml": "M",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_PATCH_1.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/closure_anfis_ablation_dvc_registration_patch.py": "A",
    "src/experiments/lock_closure_anfis_ablation_dvc_registration_patch.py": "A",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "M",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py": "A",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py": "M",
}
DEFERRED_DVC_P_MY_STAGED_SCOPE = {
    "reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_patch_lock.json": "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_patch_lock_manifest.json"
    ): "A",
}
ANFIS_ABLATION_R_MY_STAGED_SCOPE = {
    **{path: "A" for path in ANFIS_ABLATION_UNTRACKED_LIGHT_PATHS},
    **{path: "A" for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS},
    DEFERRED_DVC_MODELS_POINTER.as_posix(): "M",
}
DEFERRED_DVC_H_MY_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MY_STAGED_SCOPE
}
DEFERRED_DVC_P_MY_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MY_STAGED_SCOPE
}
ANFIS_ABLATION_R_MY_GIT_MODES = {
    path: "100644" for path in ANFIS_ABLATION_R_MY_STAGED_SCOPE
}
DEFERRED_DVC_H_MZ_STAGED_SCOPE = {
    (
        "configs/closure_v1/"
        "anfis_ablation_dvc_registration_adoption_patch_lock.schema.json"
    ): "A",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_ADOPTION_PATCH_1.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    (
        "src/experiments/"
        "closure_anfis_ablation_dvc_registration_adoption_patch.py"
    ): "A",
    (
        "src/experiments/"
        "lock_closure_anfis_ablation_dvc_registration_adoption_patch.py"
    ): "A",
    "tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py": "A",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py": "M",
    (
        "tests/"
        "test_closure_anfis_ablation_model_publication_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "M",
}
DEFERRED_DVC_P_MZ_STAGED_SCOPE = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_adoption_patch_lock.json"
    ): "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_adoption_patch_lock_manifest.json"
    ): "A",
}
ANFIS_ABLATION_R_MZ_STAGED_SCOPE = {
    **{path: "A" for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS},
    DEFERRED_DVC_MODELS_POINTER.as_posix(): "M",
}
DEFERRED_DVC_H_MZ_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MZ_STAGED_SCOPE
}
DEFERRED_DVC_P_MZ_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MZ_STAGED_SCOPE
}
ANFIS_ABLATION_R_MZ_GIT_MODES = {
    path: "100644" for path in ANFIS_ABLATION_R_MZ_STAGED_SCOPE
}
DEFERRED_DVC_H_MZA_STAGED_SCOPE = {
    (
        "configs/closure_v1/"
        "anfis_ablation_dvc_registration_order_patch_lock.schema.json"
    ): "A",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_ORDER_PATCH_1.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    (
        "src/experiments/"
        "closure_anfis_ablation_dvc_registration_order_patch.py"
    ): "A",
    (
        "src/experiments/"
        "lock_closure_anfis_ablation_dvc_registration_order_patch.py"
    ): "A",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py": "A",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py": "M",
    (
        "tests/"
        "test_closure_anfis_ablation_model_publication_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "M",
}
DEFERRED_DVC_P_MZA_STAGED_SCOPE = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_order_patch_lock.json"
    ): "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_order_patch_lock_manifest.json"
    ): "A",
}
ANFIS_ABLATION_R_MZA_STAGED_SCOPE = {
    **{path: "A" for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS},
    DEFERRED_DVC_MODELS_POINTER.as_posix(): "M",
}
DEFERRED_DVC_H_MZA_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MZA_STAGED_SCOPE
}
DEFERRED_DVC_P_MZA_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MZA_STAGED_SCOPE
}
ANFIS_ABLATION_R_MZA_GIT_MODES = {
    path: "100644" for path in ANFIS_ABLATION_R_MZA_STAGED_SCOPE
}
DEFERRED_DVC_H_MZB_STAGED_SCOPE = {
    (
        "configs/closure_v1/"
        "anfis_ablation_dvc_registration_namespace_patch_lock.schema.json"
    ): "A",
    (
        "docs/closure_v1/"
        "E0_M_ANFIS_ABLATION_DVC_REGISTRATION_NAMESPACE_PATCH_1.md"
    ): "A",
    "src/data/prepare_commit_artifacts.py": "M",
    (
        "src/experiments/"
        "closure_anfis_ablation_dvc_registration_namespace_patch.py"
    ): "A",
    (
        "src/experiments/"
        "lock_closure_anfis_ablation_dvc_registration_namespace_patch.py"
    ): "A",
    "tests/test_closure_anfis_ablation_dvc_registration_namespace_patch.py": "A",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py": "M",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py": "M",
    (
        "tests/"
        "test_closure_anfis_ablation_model_publication_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "M",
}
DEFERRED_DVC_P_MZB_STAGED_SCOPE = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_namespace_patch_lock.json"
    ): "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_namespace_patch_lock_manifest.json"
    ): "A",
}
ANFIS_ABLATION_R_MZB_STAGED_SCOPE = {
    **{path: "A" for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS},
    DEFERRED_DVC_MODELS_POINTER.as_posix(): "M",
}
DEFERRED_DVC_H_MZB_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MZB_STAGED_SCOPE
}
DEFERRED_DVC_P_MZB_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MZB_STAGED_SCOPE
}
ANFIS_ABLATION_R_MZB_GIT_MODES = {
    path: "100644" for path in ANFIS_ABLATION_R_MZB_STAGED_SCOPE
}
DEFERRED_DVC_H_MZC_STAGED_SCOPE = {
    ".gitignore": "M",
    (
        "configs/closure_v1/"
        "anfis_ablation_dvc_registration_gitignore_patch.schema.json"
    ): "A",
    (
        "docs/closure_v1/ANFIS_ABLATION_DVC_REGISTRATION_GITIGNORE_PATCH.md"
    ): "A",
    "src/data/prepare_commit_artifacts.py": "M",
    (
        "src/experiments/"
        "closure_anfis_ablation_dvc_registration_gitignore_patch.py"
    ): "A",
    (
        "src/experiments/"
        "lock_closure_anfis_ablation_dvc_registration_gitignore_patch.py"
    ): "A",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_gitignore_patch.py"
    ): "A",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_namespace_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py": "M",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py": "M",
    (
        "tests/"
        "test_closure_anfis_ablation_model_publication_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "M",
}
DEFERRED_DVC_P_MZC_STAGED_SCOPE = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_gitignore_patch_lock.json"
    ): "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_gitignore_patch_lock_manifest.json"
    ): "A",
}
ANFIS_ABLATION_R_MZC_STAGED_SCOPE = {
    **{path: "A" for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS},
    DEFERRED_DVC_MODELS_POINTER.as_posix(): "M",
}
DEFERRED_DVC_H_MZC_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MZC_STAGED_SCOPE
}
DEFERRED_DVC_P_MZC_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MZC_STAGED_SCOPE
}
ANFIS_ABLATION_R_MZC_GIT_MODES = {
    path: "100644" for path in ANFIS_ABLATION_R_MZC_STAGED_SCOPE
}
DEFERRED_DVC_H_MZD_STAGED_SCOPE = {
    (
        "configs/closure_v1/"
        "anfis_ablation_dvc_registration_status_patch.schema.json"
    ): "A",
    "docs/closure_v1/ANFIS_ABLATION_DVC_REGISTRATION_STATUS_PATCH.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    (
        "src/experiments/closure_anfis_ablation_dvc_registration_status_patch.py"
    ): "A",
    (
        "src/experiments/"
        "lock_closure_anfis_ablation_dvc_registration_status_patch.py"
    ): "A",
    (
        "tests/test_closure_anfis_ablation_dvc_registration_status_patch.py"
    ): "A",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_gitignore_patch.py"
    ): "M",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_namespace_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py": "M",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py": "M",
    (
        "tests/"
        "test_closure_anfis_ablation_model_publication_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "M",
}
DEFERRED_DVC_P_MZD_STAGED_SCOPE = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_status_patch_lock.json"
    ): "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_status_patch_lock_manifest.json"
    ): "A",
}
ANFIS_ABLATION_R_MZD_STAGED_SCOPE = {
    **{path: "A" for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS},
    DEFERRED_DVC_MODELS_POINTER.as_posix(): "M",
}
DEFERRED_DVC_H_MZD_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MZD_STAGED_SCOPE
}
DEFERRED_DVC_P_MZD_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MZD_STAGED_SCOPE
}
ANFIS_ABLATION_R_MZD_GIT_MODES = {
    path: "100644" for path in ANFIS_ABLATION_R_MZD_STAGED_SCOPE
}
DEFERRED_DVC_H_MZE_STAGED_SCOPE = {
    (
        "configs/closure_v1/"
        "anfis_ablation_dvc_registration_reproducibility_patch.schema.json"
    ): "A",
    (
        "docs/closure_v1/"
        "ANFIS_ABLATION_DVC_REGISTRATION_REPRODUCIBILITY_PATCH.md"
    ): "A",
    "src/data/prepare_commit_artifacts.py": "M",
    (
        "src/experiments/"
        "closure_anfis_ablation_dvc_registration_reproducibility_patch.py"
    ): "A",
    (
        "src/experiments/"
        "lock_closure_anfis_ablation_dvc_registration_reproducibility_patch.py"
    ): "A",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_reproducibility_patch.py"
    ): "A",
    (
        "tests/test_closure_anfis_ablation_dvc_registration_status_patch.py"
    ): "M",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_gitignore_patch.py"
    ): "M",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_namespace_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_dvc_registration_order_patch.py": "M",
    (
        "tests/"
        "test_closure_anfis_ablation_dvc_registration_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_dvc_registration_patch.py": "M",
    (
        "tests/"
        "test_closure_anfis_ablation_model_publication_adoption_patch.py"
    ): "M",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "M",
}
DEFERRED_DVC_P_MZE_STAGED_SCOPE = {
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_reproducibility_patch_lock.json"
    ): "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_dvc_registration_reproducibility_patch_lock_manifest.json"
    ): "A",
}
ANFIS_ABLATION_R_MZE_STAGED_SCOPE = {
    **{path: "A" for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS},
    DEFERRED_DVC_MODELS_POINTER.as_posix(): "M",
}
DEFERRED_DVC_H_MZE_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MZE_STAGED_SCOPE
}
DEFERRED_DVC_P_MZE_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MZE_STAGED_SCOPE
}
ANFIS_ABLATION_R_MZE_GIT_MODES = {
    path: "100644" for path in ANFIS_ABLATION_R_MZE_STAGED_SCOPE
}
DEFERRED_DVC_ACTIVE_STAGING_GATES = frozenset({"H-E0-MZE", "P-E0-MZE"})


def _deferred_dvc_staged_scopes() -> dict[str, Mapping[str, str]]:
    """Resolve current scope maps so tests and callers cannot observe stale aliases."""
    return {
        "H-E0-MV": DEFERRED_DVC_H_MV_STAGED_SCOPE,
        "P-E0-MV": DEFERRED_DVC_P_MV_STAGED_SCOPE,
        "H-E0-MW": DEFERRED_DVC_H_MW_STAGED_SCOPE,
        "P-E0-MW": DEFERRED_DVC_P_MW_STAGED_SCOPE,
        "H-E0-MX": DEFERRED_DVC_H_MX_STAGED_SCOPE,
        "P-E0-MX": DEFERRED_DVC_P_MX_STAGED_SCOPE,
        "H-E0-MY": DEFERRED_DVC_H_MY_STAGED_SCOPE,
        "P-E0-MY": DEFERRED_DVC_P_MY_STAGED_SCOPE,
        "H-E0-MZ": DEFERRED_DVC_H_MZ_STAGED_SCOPE,
        "P-E0-MZ": DEFERRED_DVC_P_MZ_STAGED_SCOPE,
        "H-E0-MZA": DEFERRED_DVC_H_MZA_STAGED_SCOPE,
        "P-E0-MZA": DEFERRED_DVC_P_MZA_STAGED_SCOPE,
        "H-E0-MZB": DEFERRED_DVC_H_MZB_STAGED_SCOPE,
        "P-E0-MZB": DEFERRED_DVC_P_MZB_STAGED_SCOPE,
        "H-E0-MZC": DEFERRED_DVC_H_MZC_STAGED_SCOPE,
        "P-E0-MZC": DEFERRED_DVC_P_MZC_STAGED_SCOPE,
        "H-E0-MZD": DEFERRED_DVC_H_MZD_STAGED_SCOPE,
        "P-E0-MZD": DEFERRED_DVC_P_MZD_STAGED_SCOPE,
        "H-E0-MZE": DEFERRED_DVC_H_MZE_STAGED_SCOPE,
        "P-E0-MZE": DEFERRED_DVC_P_MZE_STAGED_SCOPE,
    }


def _deferred_dvc_git_modes() -> dict[str, Mapping[str, str]]:
    return {
        "H-E0-MV": DEFERRED_DVC_H_MV_GIT_MODES,
        "P-E0-MV": DEFERRED_DVC_P_MV_GIT_MODES,
        "H-E0-MW": DEFERRED_DVC_H_MW_GIT_MODES,
        "P-E0-MW": DEFERRED_DVC_P_MW_GIT_MODES,
        "H-E0-MX": DEFERRED_DVC_H_MX_GIT_MODES,
        "P-E0-MX": DEFERRED_DVC_P_MX_GIT_MODES,
        "H-E0-MY": DEFERRED_DVC_H_MY_GIT_MODES,
        "P-E0-MY": DEFERRED_DVC_P_MY_GIT_MODES,
        "H-E0-MZ": DEFERRED_DVC_H_MZ_GIT_MODES,
        "P-E0-MZ": DEFERRED_DVC_P_MZ_GIT_MODES,
        "H-E0-MZA": DEFERRED_DVC_H_MZA_GIT_MODES,
        "P-E0-MZA": DEFERRED_DVC_P_MZA_GIT_MODES,
        "H-E0-MZB": DEFERRED_DVC_H_MZB_GIT_MODES,
        "P-E0-MZB": DEFERRED_DVC_P_MZB_GIT_MODES,
        "H-E0-MZC": DEFERRED_DVC_H_MZC_GIT_MODES,
        "P-E0-MZC": DEFERRED_DVC_P_MZC_GIT_MODES,
        "H-E0-MZD": DEFERRED_DVC_H_MZD_GIT_MODES,
        "P-E0-MZD": DEFERRED_DVC_P_MZD_GIT_MODES,
        "H-E0-MZE": DEFERRED_DVC_H_MZE_GIT_MODES,
        "P-E0-MZE": DEFERRED_DVC_P_MZE_GIT_MODES,
    }


def require_active_deferred_dvc_staging_gate(gate: str) -> str:
    """Reject historical deferred-DVC scopes at the only mutating boundary."""
    if type(gate) is str and gate in DEFERRED_DVC_ACTIVE_STAGING_GATES:
        return gate
    # Published MV/MW/MX regression harnesses exercise the transaction with every
    # Git/DVC operation replaced inside a directory that is not a repository.
    # Preserve that read-only reconstruction without admitting historical gates
    # at a real repository mutation boundary.
    if (
        type(gate) is str
        and gate
        in {
            "H-E0-MV",
            "P-E0-MV",
            "H-E0-MW",
            "P-E0-MW",
            "H-E0-MX",
            "P-E0-MX",
            "H-E0-MY",
            "P-E0-MY",
            "H-E0-MZ",
            "P-E0-MZ",
            "H-E0-MZA",
            "P-E0-MZA",
            "H-E0-MZB",
            "P-E0-MZB",
            "H-E0-MZC",
            "P-E0-MZC",
        }
        and not Path(".git").exists()
    ):
        return gate
    raise DeferredDvcTargetError(
        "Deferred models execution is closed to exact H-E0-MZE/P-E0-MZE scopes"
    )


HEAVY_PREFIXES = (
    "data/raw/",
    "data/interim/",
    "data/cache/",
    "data/panel/",
    "data/targets/",
    "data/splits/",
    "data/diagnostics/",
    "data/fuzzy/",
    "data/pipe_grud/",
    "data/closure_v1/",
    "models/",
    "checkpoints/",
    "outputs/",
    "artifacts/",
    "runs/",
    "mlruns/",
    "wandb/",
)
IGNORED_PREFIXES_TO_SKIP = (
    ".dvc/cache/",
    ".dvc/tmp/",
    ".pytest_cache/",
    ".venv/",
    "private/",
)
IGNORED_PATH_PARTS_TO_SKIP = {
    "__pycache__",
    ".ipynb_checkpoints",
}
REPORT_SMOKE_PARQUET_SUFFIXES = ("_smoke.parquet", "_stochastic_smoke.parquet")
REGENERABLE_IGNORED_PATHS = {
    "data/interim/observations/observations_summary.csv",
}
REPORT_ARTIFACT_SUFFIXES = {".csv", ".json", ".md", ".parquet", ".txt"}
CLOSURE_PROTOCOL_LOCK_PATH = Path("reports/closure_v1/00_protocol/protocol_lock.json")
CLOSURE_PROTOCOL_LOCK_VERSION = "closure_protocol_lock_v1"
CLOSURE_PROTOCOL_LOCK_SCRIPT = Path("src/experiments/lock_closure_protocol.py")
CLOSURE_DEVELOPMENT_RUNTIME_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_lock.json"
)
CLOSURE_DEVELOPMENT_RUNTIME_LOCK_SCHEMA = Path(
    "configs/closure_v1/development_runtime_lock.schema.json"
)
CLOSURE_DEVELOPMENT_RUNTIME_LOCK_VERSION = "closure_development_runtime_lock_v1"
CLOSURE_COMMON_ORIGIN_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/common_origin_manifest.json"
)
CLOSURE_COMMON_ORIGIN_MANIFEST_VERSION = "closure_common_origin_manifest_v1"
CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT = Path(
    "src/experiments/build_common_origin_manifest.py"
)
CLOSURE_COMMON_ORIGIN_OUTPUT_PATH = Path(
    "data/closure_v1/common_origin_manifest.parquet"
)
CLOSURE_EXPERT_STATE_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/expert/expert_no_current_state_manifest.json"
)
CLOSURE_EXPERT_STATE_OUTPUT_PATH = Path(
    "data/closure_v1/development/expert/expert_no_current_state.parquet"
)
CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_PATH = Path(
    "reports/closure_v1/02_models/M0/manifest.json"
)
CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_SCHEMA_VERSION = (
    "closure_mifal_development_manifest_v1"
)
CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_STATUS = (
    "mifal_development_bundle_written_unpublished"
)
CLOSURE_MIFAL_DEVELOPMENT_SCRIPT = Path(
    "src/experiments/run_closure_mifal.py"
)
CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS = (
    Path("data/closure_v1/development/mifal/M0/raw_scores.parquet"),
    Path("reports/closure_v1/02_models/M0/model_spec.json"),
    Path("reports/closure_v1/02_models/M0/lineage_audit.json"),
    Path("reports/closure_v1/02_models/M0/availability.csv"),
    Path("reports/closure_v1/02_models/M0/report.md"),
)
CLOSURE_MIFAL_DEVELOPMENT_SOURCE_PATHS = (
    Path("src/mifal/ed_t2.py"),
    CLOSURE_MIFAL_DEVELOPMENT_SCRIPT,
    Path("src/mifal/closure_panel_adapter.py"),
)
CLOSURE_MIFAL_DEVELOPMENT_INPUT_PATHS_AND_ROLES = (
    (Path("reports/closure_v1/00_protocol/protocol_lock.json"), "protocol_lock"),
    (
        Path("reports/closure_v1/00_protocol/development_runtime_lock.json"),
        "development_runtime_lock",
    ),
    (
        Path(
            "reports/closure_v1/00_protocol/"
            "development_runtime_temporal_validation_dialect_patch_lock.json"
        ),
        "effective_development_runtime_lock",
    ),
    (
        Path(
            "reports/closure_v1/00_protocol/"
            "development_runtime_temporal_validation_dialect_patch_lock_manifest.json"
        ),
        "effective_development_runtime_lock_manifest",
    ),
    (Path("src/experiments/closure_development_guard.py"), "development_guard"),
    (
        Path("data/closure_v1/closure_holdout_assignment.csv"),
        "holdout_assignment",
    ),
    (
        Path("reports/closure_v1/00_protocol/holdout_manifest.json"),
        "holdout_manifest",
    ),
    (
        Path("data/closure_v1/common_origin_manifest.parquet"),
        "common_origin",
    ),
    (
        Path("data/closure_v1/common_origin_manifest.parquet.dvc"),
        "common_origin_pointer",
    ),
    (
        Path("reports/closure_v1/01_surface/common_origin_manifest.json"),
        "common_origin_manifest",
    ),
    (Path("data/panel/panel_monthly_v0.parquet"), "panel"),
    (Path("data/panel/panel_monthly_v0.parquet.dvc"), "panel_pointer"),
    (Path("configs/closure_v1/model_benchmark.yaml"), "model_benchmark"),
    (Path("configs/closure_v1/surface_primary.yaml"), "primary_surface"),
    (Path("configs/closure_v1/analysis_plan.yaml"), "analysis_plan"),
    (
        Path("configs/closure_v1/experimental_matrix.yaml"),
        "experimental_matrix",
    ),
    (Path("src/mifal/ed_t2.py"), "mifal_core"),
    (Path("pyproject.toml"), "pyproject"),
    (Path("poetry.lock"), "poetry_lock"),
    (
        Path("reports/closure_v1/02_models/baselines/manifest.json"),
        "upstream_baseline_manifest",
    ),
    (
        Path(
            "reports/closure_v1/00_protocol/"
            "baseline_development_publication_guard_patch_lock.json"
        ),
        "upstream_baseline_patch_lock",
    ),
    (
        Path(
            "reports/closure_v1/00_protocol/"
            "baseline_development_publication_guard_patch_lock_manifest.json"
        ),
        "upstream_baseline_patch_lock_manifest",
    ),
    (Path("models.dvc"), "models_dvc_observer"),
    (
        Path("configs/closure_v1/mifal_development_runtime.yaml"),
        "mifal_runtime",
    ),
    (
        Path("reports/closure_v1/00_protocol/mifal_development_patch_lock.json"),
        "effective_patch_lock",
    ),
    (
        Path(
            "reports/closure_v1/00_protocol/"
            "mifal_development_patch_lock_manifest.json"
        ),
        "effective_patch_lock_manifest",
    ),
    (CLOSURE_MIFAL_DEVELOPMENT_SCRIPT, "mifal_development_runner"),
    (Path("src/mifal/closure_panel_adapter.py"), "strict_panel_adapter"),
)
CLOSURE_MIFAL_RAW_PREDICTION_CONTRACT_SHA256 = (
    "e6e50951d083e0109f9a7395ab711edc318d8c80b0c11b7e5d7de8f086eaf2e1"
)
CLOSURE_MIFAL_EXPECTED_AUTHORITY = {
    "gate": "E0-MR",
    "status": "effective_preflight_passed",
    "strict_adapter_authorized": True,
    "mifal_one_shot_authorized": True,
    "m0_execution_authorized": True,
    "tuning_authorized": False,
    "target_access_authorized": False,
    "calibration_authorized": False,
    "metrics_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "dvc_commands_authorized": False,
    "scientific_network_authorized": False,
    "outcome_access_authorized": False,
    "future_outcomes_accessed": False,
    "h_patch_head": "4dab0a286f4df31c95251fde7f9e36ee7d09e968",
    "p_patch_head": "9106ff042ecea135d3652e8dedac4d78a2360b3e",
    "lock_sha256": "59eb0674ae4502bcbae16b9ad0f4c653429771e3c9ec89b1ef1f31e3dbb08125",
    "companion_sha256": "3628973b4eda30b14787f57554bef8b13d8c9580d1b3c3f2c4134acb7c3130f9",
    "runtime_sha256": "26a1e2fa6f7d630cbe770dd282f8d86b21a152f4733874ecc6b19de53b5e7d84",
    "h_components_sha256": "8bfad66fb5e2c2072e815966b85bff207f501ddf7cdc680fbadcefe8f44b8955",
    "physical_inputs_sha256": "49ffcc28dec8ea2306d46b2f5b274a318ec7d8d2c94a36ea5fa970fa059b16d3",
    "runner_sha256": "a4afeeeb475d0cc4d9532ed92e5a05d1b37ca73e2b9bf8755d224f7b1fc3d6f4",
    "adapter_sha256": "d9438eacd4dfdd1127a2cf22398de420802c8044948b548dccd23d28fbde4773",
    "mifal_core_sha256": "46490b08e6efd2725c14ba4cd07eede2b06b191179d25d1ffecf189efec1ca53",
    "exact_raw_prediction_rows": 29196,
    "minimum_observed_evidence_groups": 2,
}
CLOSURE_MIFAL_EXPECTED_COUNTS = {
    "raw_rows": 29196,
    "intent_origins": 9732,
    "eligible_origins": 9732,
    "input_ineligible_origins": 0,
    "development_locations": 353,
    "final_paths": 6,
}
CLOSURE_MIFAL_MANIFEST_FALSE_FLAGS = (
    "tuning_performed",
    "targets_opened",
    "calibration_performed",
    "metrics_computed",
    "e0_m_authorized",
    "evaluation_authorized",
    "e0_u_authorized",
    "dvc_commands_run",
    "network_calls_made",
    "future_outcomes_accessed",
)
CLOSURE_COMMON_ORIGIN_CODE_PATHS = (
    CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT,
    Path("src/experiments/build_closure_holdout.py"),
    Path("src/experiments/closure_contract.py"),
    Path("src/experiments/closure_development_guard.py"),
    Path("src/pandas_utils.py"),
)
CLOSURE_COMMON_ORIGIN_CONFIG_PATHS = (
    Path("configs/closure_v1/analysis_plan.yaml"),
    Path("configs/closure_v1/analysis_plan.schema.json"),
    Path("configs/closure_v1/surface_primary.yaml"),
    Path("configs/closure_v1/surface_secondary.yaml"),
    Path("configs/closure_v1/location_holdout.yaml"),
    Path("configs/closure_v1/model_benchmark.yaml"),
    Path("configs/closure_v1/experimental_matrix.yaml"),
    Path("configs/counterfactual_planning_v1.yaml"),
)
CLOSURE_COMMON_ORIGIN_SOURCE_PATHS = (
    Path("data/panel/panel_monthly_v0.parquet"),
    Path("data/splits/monthly_model_splits_v0.parquet"),
    Path("data/targets/monthly_targets_model_v0.parquet"),
    Path("data/targets/target_manifest_v0.json"),
    Path("data/splits/split_manifest.json"),
)
CLOSURE_COMMON_ORIGIN_SOURCE_ROLES = (
    "cutoff_safe_input_history_source",
    "canonical_leakage_safe_temporal_rows",
    "historical_stratification_and_later_evaluation_targets",
    "canonical_target_provenance_and_threshold_manifest",
    "temporal_split_provenance",
)
CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES = (
    (Path("reports/closure_v1/00_protocol/protocol_lock.json"), "protocol_lock"),
    (Path("reports/closure_v1/00_protocol/holdout_manifest.json"), "holdout_manifest"),
    (Path("data/closure_v1/closure_holdout_assignment.csv"), "holdout_assignment"),
)
CLOSURE_COMMON_ORIGIN_REPRODUCTION_COMMAND = [
    "poetry",
    "run",
    "python",
    CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT.as_posix(),
    "--panel",
    CLOSURE_COMMON_ORIGIN_SOURCE_PATHS[0].as_posix(),
    "--splits",
    CLOSURE_COMMON_ORIGIN_SOURCE_PATHS[1].as_posix(),
    "--output",
    CLOSURE_COMMON_ORIGIN_OUTPUT_PATH.as_posix(),
    "--manifest",
    CLOSURE_COMMON_ORIGIN_MANIFEST_PATH.as_posix(),
]
FREEZE_ARTIFACT_PATHS = {
    Path("data/freeze/derived_file_manifest_v0.csv"),
    Path("data/freeze/data_freeze_manifest_v0.json"),
    Path("data/freeze/DATA_FREEZE.md"),
}
FREEZE_REQUIRED_OUTPUTS = {
    Path("data/freeze/derived_file_manifest_v0.csv"),
    Path("data/freeze/data_freeze_manifest_v0.json"),
    Path("data/freeze/DATA_FREEZE.md"),
}
FREEZE_DOCUMENTATION_OUTPUTS = {
    Path("data/freeze/data_freeze_manifest_v0.json"),
    Path("data/freeze/DATA_FREEZE.md"),
}
FREEZE_SENSITIVE_EXACT_PATHS = {
    "configs/sources.yaml",
    "configs/site_resolution.yaml",
    "src/data/build_observations.py",
    "src/data/build_waterbody_crosswalk.py",
    "src/data/build_panel.py",
    "src/data/build_targets.py",
    "src/data/diagnose_panel_targets.py",
    "src/data/freeze.py",
    "src/data/raw_manifest.py",
    "src/data/report_observations.py",
    "src/data/site_registry.py",
    "src/data/validate_sources.py",
}
FREEZE_SENSITIVE_PREFIXES = (
    "data/catalog/",
    "data/interim/",
    "data/panel/",
    "data/targets/",
    "data/diagnostics/",
    "data/scripts/",
)
DEFAULT_DVC_ARTIFACT_INVENTORY = Path("configs/dvc_artifacts.yaml")


@dataclass(frozen=True)
class DvcArtifact:
    artifact_id: str
    path: Path
    artifact_type: str
    source_id: str
    dvc: bool


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ReproducibilityFinding:
    level: str
    check: str
    path: str
    message: str


@dataclass(frozen=True)
class FinalCalibrationR8PhysicalIdentity:
    path: str
    device: int
    inode: int
    mode: int
    nlink: int
    bytes: int
    sha256: str
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class AnfisAblationManifestScriptProvenance:
    manifest_path: str
    script_path: str
    commit: str
    blob_oid: str
    git_mode: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class DeferredDvcFinalSnapshot:
    path: str
    device: int
    inode: int
    mtime_ns: int
    size: int
    sha256: str
    mode: int
    nlink: int = 1
    ctime_ns: int = 0


@dataclass(frozen=True)
class RegistrationFileIdentity:
    path: str
    device: int
    inode: int
    mode: int
    nlink: int
    size: int
    sha256: str
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class RegistrationDirectoryIdentity:
    path: str
    device: int
    inode: int
    mode: int
    nlink: int
    entry_count: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class RegistrationOwnedNode:
    """Stable ownership captured immediately after one exclusive creation."""

    path: str
    device: int
    inode: int
    mode: int
    nlink: int


@dataclass(frozen=True)
class RegistrationSymlinkIdentity:
    path: str
    target: str
    device: int
    inode: int
    mode: int
    nlink: int
    size: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class AnfisAblationDvcRuntimeIdentity:
    wrapper: RegistrationFileIdentity
    python_link: RegistrationSymlinkIdentity
    python_target: RegistrationFileIdentity
    git: RegistrationFileIdentity


ANFIS_ABLATION_REGISTRATION_TRAINER_PATH = (
    "src/experiments/train_closure_anfis_ablation.py"
)
ANFIS_ABLATION_REGISTRATION_P_MZD_COMMIT = (
    "33b84bc8aa7a9968947f4b670dbd0aae10fbfa74"
)
ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_COMMIT = (
    "3fff3f272eb6f6ba8e644dd49436bc39ecbed1f8"
)
ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_BLOB_OID = (
    "f80a80fe89538da3c87707496dfa828053f77d77"
)
ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_BYTES = 107_577
ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_SHA256 = (
    "608786d9da2c263cbae5010dd19d6a6acc61df25d4c370c1e1312526693eca7e"
)
ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_COMMIT = (
    "8b4452bdca930a7b1ac1a7094f0c2b36e7d5d559"
)
ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_BLOB_OID = (
    "f76ad4990c2838632b5806a3dcf193c5d1177da5"
)
ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_BYTES = 112_554
ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_SHA256 = (
    "738bf8a5dd4fba09e4238d2b9a2f436081410e4ab998fc4b8b822ff9c402e0a9"
)
_ANFIS_ABLATION_REGISTRATION_MANIFEST_SCRIPT_PROVENANCE_RECORDS = tuple(
    AnfisAblationManifestScriptProvenance(
        manifest_path=manifest_path,
        script_path=ANFIS_ABLATION_REGISTRATION_TRAINER_PATH,
        commit=(
            ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_COMMIT
            if manifest_path
            == "reports/closure_v1/02_models/A0/seed_1729_manifest.json"
            else ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_COMMIT
        ),
        blob_oid=(
            ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_BLOB_OID
            if manifest_path
            == "reports/closure_v1/02_models/A0/seed_1729_manifest.json"
            else ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_BLOB_OID
        ),
        git_mode="100644",
        bytes=(
            ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_BYTES
            if manifest_path
            == "reports/closure_v1/02_models/A0/seed_1729_manifest.json"
            else ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_BYTES
        ),
        sha256=(
            ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_SHA256
            if manifest_path
            == "reports/closure_v1/02_models/A0/seed_1729_manifest.json"
            else ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_SHA256
        ),
    )
    for manifest_path in ANFIS_ABLATION_MANIFEST_PATHS
)
ANFIS_ABLATION_REGISTRATION_MANIFEST_SCRIPT_PROVENANCE: Mapping[
    str, AnfisAblationManifestScriptProvenance
] = MappingProxyType(
    {
        record.manifest_path: record
        for record in _ANFIS_ABLATION_REGISTRATION_MANIFEST_SCRIPT_PROVENANCE_RECORDS
    }
)


class DeferredDvcTargetError(RuntimeError):
    """Raised when the closed model-bundle DVC-deferral exception drifts."""


class FinalCalibrationR8ManifestReproducibilityAdapterError(RuntimeError):
    """Raised when the exact E0-MCALK precommit exception drifts."""


class FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(RuntimeError):
    """Raised when the exact E0-MCALL precommit exception drifts."""


class FinalCalibrationR8PostPublicationAuthorityAdapterError(RuntimeError):
    """Raised when the exact E0-MCALM precommit exception drifts."""


class ClosureLockedEvaluationInputBundleAdapterError(RuntimeError):
    """Raised when the exact E0-MIB precommit exception drifts."""


_LOCKED_EVALUATION_INPUT_H_STAGED_SCOPE = {
    "configs/closure_v1/locked_evaluation_input_bundle_lock.schema.json": "A",
    "docs/closure_v1/E0_M_LOCKED_EVALUATION_INPUT_BUNDLE.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/closure_locked_evaluation_input_bundle.py": "A",
    "src/experiments/lock_closure_locked_evaluation_input_bundle.py": "A",
    "tests/test_closure_locked_evaluation_input_bundle.py": "A",
}
_LOCKED_EVALUATION_INPUT_P_STAGED_SCOPE = {
    "configs/closure_v1/locked_evaluation_input_bundle_lock.json": "A",
    "configs/closure_v1/locked_evaluation_input_bundle_lock_manifest.json": "A",
}
_LOCKED_EVALUATION_INPUT_R_STAGED_SCOPE = {
    "data/closure_v1/locked_evaluation/input_history.parquet.dvc": "A",
    "data/closure_v1/locked_evaluation/intent_origins.parquet.dvc": "A",
    "data/closure_v1/locked_evaluation/origin_features.parquet.dvc": "A",
    "data/closure_v1/locked_evaluation/sequence_features.parquet.dvc": "A",
    "reports/closure_v1/01_surface/locked_evaluation_input_manifest.json": "A",
    "reports/closure_v1/01_surface/locked_evaluation_input_summary.json": "A",
}
_LOCKED_EVALUATION_INPUT_H_GIT_MODES = {
    path: (
        "100755"
        if path == "src/data/prepare_commit_artifacts.py"
        else "100644"
    )
    for path in _LOCKED_EVALUATION_INPUT_H_STAGED_SCOPE
}


def _final_calibration_stage_adapter_error(
    gate: str, message: str
) -> RuntimeError:
    """Preserve the owning adapter error boundary for each calibration gate."""
    if gate.endswith("MIB") or gate == "R-E0-MI":
        return ClosureLockedEvaluationInputBundleAdapterError(message)
    if gate.endswith("MCALM"):
        return FinalCalibrationR8PostPublicationAuthorityAdapterError(message)
    if gate.endswith("MCALL"):
        return FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            message
        )
    return FinalCalibrationR8ManifestReproducibilityAdapterError(message)


def anfis_ablation_registration_dvc_add_command(
    dvc_bin: str, target: Path
) -> list[str]:
    """Build one exact no-relink command from the closed ordered target set."""
    if (
        dvc_bin != DEFAULT_DVC_BIN.as_posix()
        or target not in ANFIS_ABLATION_REGISTRATION_DVC_TARGETS
    ):
        raise DeferredDvcTargetError(
            "E0-MY DVC add command received a non-closed binary or target"
        )
    return [dvc_bin, "add", ANFIS_ABLATION_DVC_ADD_FLAG, target.as_posix()]


def command_text(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def sha256_file(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5_file(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_regular_file(path: Path, *, mode: int | None = None) -> os.stat_result:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise DeferredDvcTargetError(f"Required deferred-DVC file is absent: {path}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise DeferredDvcTargetError(f"Deferred-DVC path is not a regular file: {path}")
    if mode is not None and stat.S_IMODE(metadata.st_mode) != mode:
        raise DeferredDvcTargetError(
            f"Deferred-DVC file mode drifted: {path} "
            f"({stat.S_IMODE(metadata.st_mode):04o} != {mode:04o})"
        )
    return metadata


def _require_no_symlink_ancestors(path: Path, *, anchor: Path) -> None:
    try:
        relative = path.relative_to(anchor)
    except ValueError as exc:
        raise DeferredDvcTargetError(
            f"Deferred-DVC path escapes its lexical anchor: {path}"
        ) from exc
    current = anchor
    if not stat.S_ISDIR(current.lstat().st_mode):
        raise DeferredDvcTargetError(
            f"Deferred-DVC lexical anchor is not a directory: {anchor}"
        )
    for part in relative.parts[:-1]:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError as exc:
            raise DeferredDvcTargetError(
                f"Deferred-DVC lexical ancestor is absent: {current}"
            ) from exc
        if not stat.S_ISDIR(metadata.st_mode):
            raise DeferredDvcTargetError(
                f"Deferred-DVC lexical ancestor is not a directory: {current}"
            )


def _validate_closed_git_exclude_environment(
    *,
    expected_patterns: tuple[str, ...],
    expected_description: str,
    env: Mapping[str, str] | None = None,
) -> tuple[int, int, int, str]:
    """Validate one exact command-scoped Git exclusion file."""
    source = os.environ if env is None else env
    expected_names = {"GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"}
    observed_names = {
        name
        for name in source
        if name.startswith("GIT_CONFIG")
    }
    if observed_names != expected_names:
        raise DeferredDvcTargetError(
            "Deferred models DVC target requires exactly one command-scoped Git config entry"
        )
    if source.get("GIT_CONFIG_COUNT") != "1" or source.get("GIT_CONFIG_KEY_0") != "core.excludesFile":
        raise DeferredDvcTargetError(
            "Deferred models DVC target requires GIT_CONFIG_COUNT=1 and core.excludesFile"
        )
    raw_path = source.get("GIT_CONFIG_VALUE_0")
    if not isinstance(raw_path, str) or not raw_path:
        raise DeferredDvcTargetError("Deferred models DVC exclude-file path is absent")
    exclude_path = Path(raw_path)
    if not exclude_path.is_absolute():
        raise DeferredDvcTargetError("Deferred models DVC exclude-file path must be absolute")
    redirected_git_environment = {
        "GIT_INDEX_FILE",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE",
    }
    present_redirects = sorted(redirected_git_environment.intersection(source))
    if present_redirects:
        raise DeferredDvcTargetError(
            "Deferred models DVC mode forbids redirected Git state: "
            + ", ".join(present_redirects)
        )
    metadata = _require_regular_file(exclude_path, mode=0o600)
    _require_no_symlink_ancestors(exclude_path, anchor=Path(exclude_path.anchor))
    if metadata.st_nlink != 1:
        raise DeferredDvcTargetError(
            "Deferred models DVC exclude file must have exactly one hard link"
        )
    expected = "".join(f"{pattern}\n" for pattern in expected_patterns)
    try:
        payload = exclude_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DeferredDvcTargetError("Deferred models DVC exclude file is not UTF-8") from exc
    if payload != expected:
        raise DeferredDvcTargetError(
            "Deferred models DVC exclude file must contain "
            f"{expected_description}"
        )
    return (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns, sha256_file(exclude_path))


def validate_deferred_dvc_git_exclude_environment(
    *, env: Mapping[str, str] | None = None
) -> tuple[int, int, int, str]:
    """Validate the historical exact five-path exclusion through E0-MX."""
    return _validate_closed_git_exclude_environment(
        expected_patterns=DEFERRED_DVC_A0_LIGHT_EXCLUDE_PATTERNS,
        expected_description="the exact five rooted A0 paths",
        env=env,
    )


def validate_anfis_ablation_family_git_exclude_environment(
    *, env: Mapping[str, str] | None = None
) -> tuple[int, int, int, str]:
    """Validate the E0-MY exclusion for exactly 45 untracked light reports."""
    return _validate_closed_git_exclude_environment(
        expected_patterns=ANFIS_ABLATION_LIGHT_EXCLUDE_PATTERNS,
        expected_description=(
            "the exact 45 rooted untracked A0/A1 lightweight-report paths"
        ),
        env=env,
    )


def validate_anfis_ablation_adoption_git_environment(
    *, env: Mapping[str, str] | None = None
) -> tuple[int, int, int, str]:
    """Require default Git visibility after all fifty light finals are tracked."""
    source = os.environ if env is None else env
    config_names = sorted(name for name in source if name.startswith("GIT_CONFIG"))
    redirected_names = sorted(
        {
            "GIT_INDEX_FILE",
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_NAMESPACE",
        }.intersection(source)
    )
    if config_names or redirected_names:
        raise DeferredDvcTargetError(
            "E0-MZE deferred models mode requires default Git visibility"
        )
    return (0, 0, 0, hashlib.sha256(b"").hexdigest())


def normalize_deferred_dvc_targets(
    raw_targets: list[str], *, no_push: bool
) -> list[Path]:
    if not raw_targets:
        return []
    if raw_targets != [DEFERRED_DVC_MODELS_TARGET.as_posix()]:
        raise DeferredDvcTargetError(
            "The only supported deferred DVC target is the single exact path: models"
        )
    if not no_push:
        raise DeferredDvcTargetError("Deferred DVC targets require --no-push")
    return [DEFERRED_DVC_MODELS_TARGET]


def validate_deferred_dvc_invocation(
    args: Any,
    deferred_paths: list[Path],
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    if not deferred_paths:
        return
    source = os.environ if env is None else env
    dvc_site_cache = source.get("DVC_SITE_CACHE_DIR")
    if (
        args.yes
        or args.dry_run
        or args.skip_publication_check
        or args.jobs is not None
        or not args.allow_unmanaged
        or args.dvc_bin is not None
        or args.manifest != DEFAULT_DVC_MANIFEST
        or args.report is not None
        or "DVC_BIN" in source
        or source.get("DVC_NO_ANALYTICS") != "1"
        or (
            dvc_site_cache is not None
            and dvc_site_cache != DEFAULT_DVC_SITE_CACHE_DIR.as_posix()
        )
    ):
        raise DeferredDvcTargetError(
            "Deferred models mode requires --allow-unmanaged --no-push and forbids "
            "--yes, --dry-run, --jobs, --skip-publication-check, custom DVC binaries, "
            "custom DVC manifests, custom report paths, analytics-enabled DVC, and "
            "custom DVC site-cache paths"
        )


def validate_deferred_dvc_target_selection(
    deferred_paths: list[Path],
    *,
    artifacts: list[DvcArtifact],
    changed_artifacts: list[DvcArtifact],
    missing_pointer_artifacts: list[DvcArtifact],
    manual_targets: list[Path],
) -> None:
    if not deferred_paths:
        return
    configured = [
        artifact
        for artifact in artifacts
        if artifact.dvc and artifact.path == DEFERRED_DVC_MODELS_TARGET
    ]
    if len(configured) != 1 or not DEFERRED_DVC_MODELS_TARGET.exists():
        raise DeferredDvcTargetError(
            "Deferred models target must be one present configured DVC artifact"
        )
    if [artifact.path for artifact in changed_artifacts] != [DEFERRED_DVC_MODELS_TARGET]:
        raise DeferredDvcTargetError(
            "Deferred mode requires models to be the only changed DVC artifact"
        )
    if missing_pointer_artifacts:
        raise DeferredDvcTargetError("Deferred mode forbids missing DVC pointers")
    if manual_targets:
        raise DeferredDvcTargetError("Deferred mode forbids additional manual DVC targets")


def _git_output(repo_root: Path, *args: str) -> str:
    return run_command(["git", "-C", repo_root.as_posix(), *args]).stdout


def _validate_deferred_a0_git_tracking(repo_root: Path) -> None:
    """Bind the adopted lightweight A0 files to their exact publication commit."""
    light_paths = set(DEFERRED_DVC_A0_LIGHT_GIT_OIDS)
    expected_light_paths = {
        path
        for _, path, _, _ in DEFERRED_DVC_A0_FINAL_RECORDS
        if path.startswith("reports/")
    }
    if light_paths != expected_light_paths or len(light_paths) != 5:
        raise DeferredDvcTargetError(
            "Deferred A0 tracked-light inventory drifted from the exact five reports"
        )

    ancestry = _git_output(
        repo_root,
        "rev-list",
        "--parents",
        "-n",
        "1",
        DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT,
    ).strip()
    if ancestry != (
        f"{DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT} "
        f"{DEFERRED_DVC_A0_LIGHT_PUBLICATION_PARENT}"
    ):
        raise DeferredDvcTargetError(
            "Deferred A0 lightweight publication commit topology drifted"
        )
    merge_base = _git_output(
        repo_root,
        "merge-base",
        "HEAD",
        DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT,
    ).strip()
    if merge_base != DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT:
        raise DeferredDvcTargetError(
            "Deferred A0 lightweight publication commit is not a HEAD ancestor"
        )

    publication_scope: dict[str, str] = {}
    for line in _git_output(
        repo_root,
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "-r",
        DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT,
    ).splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[1] in publication_scope:
            raise DeferredDvcTargetError(
                "Deferred A0 lightweight publication commit scope is malformed"
            )
        publication_scope[fields[1]] = fields[0]
    if publication_scope != {path: "A" for path in light_paths}:
        raise DeferredDvcTargetError(
            "Deferred A0 lightweight publication commit is not the exact five additions"
        )

    for raw_path, expected_oid in sorted(DEFERRED_DVC_A0_LIGHT_GIT_OIDS.items()):
        publication_line = _git_output(
            repo_root,
            "ls-tree",
            DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT,
            "--",
            raw_path,
        ).strip()
        expected_line = f"100644 blob {expected_oid}\t{raw_path}"
        head_oid = _git_output(repo_root, "rev-parse", f"HEAD:{raw_path}").strip()
        index_line = _git_output(
            repo_root, "ls-files", "-s", "--", raw_path
        ).strip()
        worktree_oid = _git_output(
            repo_root, "hash-object", "--no-filters", "--", raw_path
        ).strip()
        if (
            publication_line != expected_line
            or head_oid != expected_oid
            or index_line != f"100644 {expected_oid} 0\t{raw_path}"
            or worktree_oid != expected_oid
        ):
            raise DeferredDvcTargetError(
                f"Deferred A0 lightweight Git binding drifted: {raw_path}"
            )

    ordered_light_paths = sorted(light_paths)
    if _git_output(
        repo_root, "diff", "--name-only", "--", *ordered_light_paths
    ).strip() or _git_output(
        repo_root, "diff", "--cached", "--name-only", "--", *ordered_light_paths
    ).strip():
        raise DeferredDvcTargetError(
            "Deferred A0 lightweight reports must be clean in index and worktree"
        )

    heavy_paths = sorted(
        path
        for _, path, _, _ in DEFERRED_DVC_A0_FINAL_RECORDS
        if path not in light_paths
    )
    if _git_output(
        repo_root, "ls-files", "--stage", "--", *heavy_paths
    ).strip():
        raise DeferredDvcTargetError(
            "Deferred A0 heavyweight finals must remain outside Git"
        )


def _validate_anfis_ablation_mz_git_tracking(repo_root: Path) -> None:
    """Bind all fifty light finals to the exact 2f0643a publication."""
    light_paths = set(ANFIS_ABLATION_MZ_TRACKED_LIGHT_PATHS)
    if light_paths != set(ANFIS_ABLATION_LIGHT_REPORT_PATHS) or len(light_paths) != 50:
        raise DeferredDvcTargetError(
            "E0-MZE tracked-light inventory is not the exact fifty reports"
        )
    ancestry = _git_output(
        repo_root,
        "rev-list",
        "--parents",
        "-n",
        "1",
        ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_COMMIT,
    ).strip()
    if ancestry != (
        f"{ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_COMMIT} "
        f"{ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_PARENT}"
    ):
        raise DeferredDvcTargetError("E0-MZE light publication topology drifted")
    if _git_output(
        repo_root,
        "merge-base",
        "HEAD",
        ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_COMMIT,
    ).strip() != ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_COMMIT:
        raise DeferredDvcTargetError(
            "E0-MZE light publication is not an ancestor of HEAD"
        )

    publication_scope: dict[str, str] = {}
    for line in _git_output(
        repo_root,
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "-r",
        ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_COMMIT,
    ).splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[1] in publication_scope:
            raise DeferredDvcTargetError("E0-MZE light publication scope is malformed")
        publication_scope[fields[1]] = fields[0]
    if publication_scope != {
        path: "A" for path in ANFIS_ABLATION_UNTRACKED_LIGHT_PATHS
    }:
        raise DeferredDvcTargetError(
            "E0-MZE light publication must be the exact forty-five additions"
        )

    publication_records: dict[str, str] = {}
    for line in _git_output(
        repo_root,
        "ls-tree",
        "-r",
        "--full-tree",
        ANFIS_ABLATION_MZ_LIGHT_PUBLICATION_COMMIT,
        "--",
        *sorted(light_paths),
    ).splitlines():
        metadata, separator, raw_path = line.partition("\t")
        fields = metadata.split()
        if (
            not separator
            or len(fields) != 3
            or fields[0] != "100644"
            or fields[1] != "blob"
            or raw_path in publication_records
        ):
            raise DeferredDvcTargetError(
                "E0-MZE tracked-light Git tree record is malformed"
            )
        publication_records[raw_path] = fields[2]
    if set(publication_records) != light_paths:
        raise DeferredDvcTargetError(
            "E0-MZE tracked-light Git tree is not the exact fifty reports"
        )

    for raw_path, expected_oid in sorted(publication_records.items()):
        physical = repo_root / raw_path
        _require_no_symlink_ancestors(physical, anchor=repo_root)
        metadata = _require_regular_file(physical, mode=0o644)
        head_oid = _git_output(repo_root, "rev-parse", f"HEAD:{raw_path}").strip()
        index_line = _git_output(
            repo_root, "ls-files", "-s", "--", raw_path
        ).strip()
        worktree_oid = _git_output(
            repo_root, "hash-object", "--no-filters", "--", raw_path
        ).strip()
        if (
            metadata.st_nlink != 1
            or head_oid != expected_oid
            or index_line != f"100644 {expected_oid} 0\t{raw_path}"
            or worktree_oid != expected_oid
        ):
            raise DeferredDvcTargetError(
                f"E0-MZE tracked-light Git binding drifted: {raw_path}"
            )

    ordered_light_paths = sorted(light_paths)
    if _git_output(
        repo_root, "diff", "--name-only", "--", *ordered_light_paths
    ).strip() or _git_output(
        repo_root, "diff", "--cached", "--name-only", "--", *ordered_light_paths
    ).strip():
        raise DeferredDvcTargetError(
            "E0-MZE tracked-light reports must be clean in index and worktree"
        )

    heavy_paths = sorted(
        set(ANFIS_ABLATION_MODEL_PATHS)
        | set(ANFIS_ABLATION_SELECTION_PREDICTION_PATHS)
    )
    if len(heavy_paths) != 30 or _git_output(
        repo_root, "ls-files", "--stage", "--", *heavy_paths
    ).strip():
        raise DeferredDvcTargetError(
            "E0-MZE exact thirty heavyweight finals must remain outside Git"
        )


def _validate_deferred_models_pointer(repo_root: Path) -> None:
    pointer = repo_root / DEFERRED_DVC_MODELS_POINTER
    _require_no_symlink_ancestors(pointer, anchor=repo_root)
    metadata = _require_regular_file(pointer, mode=0o644)
    if metadata.st_size != 109 or sha256_file(pointer) != DEFERRED_DVC_MODELS_POINTER_SHA256:
        raise DeferredDvcTargetError("models.dvc bytes drifted from the deferred-DVC baseline")
    try:
        payload = yaml.safe_load(pointer.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise DeferredDvcTargetError("models.dvc is not strict readable YAML") from exc
    expected = {
        "outs": [
            {
                "md5": f"{DEFERRED_DVC_MODELS_DIRECTORY_MD5}.dir",
                "size": DEFERRED_DVC_MODELS_BYTES,
                "nfiles": DEFERRED_DVC_MODELS_NFILES,
                "hash": "md5",
                "path": "models",
            }
        ]
    }
    if payload != expected:
        raise DeferredDvcTargetError("models.dvc descriptor dialect drifted")

    head_oid = _git_output(repo_root, "rev-parse", "HEAD:models.dvc").strip()
    worktree_oid = _git_output(repo_root, "hash-object", "models.dvc").strip()
    index_line = _git_output(repo_root, "ls-files", "-s", "--", "models.dvc").strip()
    if index_line != f"100644 {head_oid} 0\tmodels.dvc" or worktree_oid != head_oid:
        raise DeferredDvcTargetError("models.dvc HEAD/index/worktree binding drifted")
    if _git_output(repo_root, "diff", "--name-only", "--", "models.dvc").strip():
        raise DeferredDvcTargetError("models.dvc has an unstaged change")
    if _git_output(repo_root, "diff", "--cached", "--name-only", "--", "models.dvc").strip():
        raise DeferredDvcTargetError("models.dvc must not be staged by deferred mode")


def _walk_regular_tree(root: Path) -> dict[str, Path]:
    try:
        root_metadata = root.lstat()
    except FileNotFoundError as exc:
        raise DeferredDvcTargetError(f"Deferred-DVC tree is absent: {root}") from exc
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise DeferredDvcTargetError(f"Deferred-DVC tree root is not a directory: {root}")
    result: dict[str, Path] = {}
    for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in directory_names:
            candidate = current_path / name
            if not stat.S_ISDIR(candidate.lstat().st_mode):
                raise DeferredDvcTargetError(
                    f"Deferred-DVC tree contains a non-directory ancestor: {candidate}"
                )
        for name in file_names:
            candidate = current_path / name
            if not stat.S_ISREG(candidate.lstat().st_mode):
                raise DeferredDvcTargetError(
                    f"Deferred-DVC tree contains a non-regular file: {candidate}"
                )
            relative = candidate.relative_to(root).as_posix()
            if relative in result:
                raise DeferredDvcTargetError(f"Deferred-DVC tree path is duplicated: {relative}")
            result[relative] = candidate
    return result


def _validate_deferred_models_tree(
    repo_root: Path,
    *,
    exact_extra_model_paths: tuple[str, ...] | None = None,
) -> None:
    descriptor_path = (
        repo_root
        / ".dvc/cache/files/md5"
        / DEFERRED_DVC_MODELS_DIRECTORY_MD5[:2]
        / f"{DEFERRED_DVC_MODELS_DIRECTORY_MD5[2:]}.dir"
    )
    _require_no_symlink_ancestors(descriptor_path, anchor=repo_root)
    descriptor_metadata = _require_regular_file(descriptor_path, mode=0o444)
    if (
        descriptor_metadata.st_size != DEFERRED_DVC_MODELS_DIRECTORY_BYTES
        or sha256_file(descriptor_path) != DEFERRED_DVC_MODELS_DIRECTORY_SHA256
        or _md5_file(descriptor_path) != DEFERRED_DVC_MODELS_DIRECTORY_MD5
    ):
        raise DeferredDvcTargetError("Deferred models DVC .dir descriptor drifted")
    try:
        records = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeferredDvcTargetError("Deferred models DVC .dir descriptor is invalid JSON") from exc
    if not isinstance(records, list) or len(records) != DEFERRED_DVC_MODELS_NFILES:
        raise DeferredDvcTargetError("Deferred models DVC .dir record count drifted")

    baseline: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {"md5", "relpath"}:
            raise DeferredDvcTargetError("Deferred models DVC .dir record dialect drifted")
        digest = record.get("md5")
        relative = record.get("relpath")
        if (
            not isinstance(digest, str)
            or len(digest) != 32
            or any(character not in "0123456789abcdef" for character in digest)
            or not isinstance(relative, str)
            or not relative
        ):
            raise DeferredDvcTargetError("Deferred models DVC .dir record is malformed")
        relative_path = Path(relative)
        if relative_path.is_absolute() or "." in relative_path.parts or ".." in relative_path.parts:
            raise DeferredDvcTargetError("Deferred models DVC .dir relpath is unsafe")
        if relative in baseline:
            raise DeferredDvcTargetError("Deferred models DVC .dir relpath is duplicated")
        baseline[relative] = digest
    if list(baseline) != sorted(baseline):
        raise DeferredDvcTargetError("Deferred models DVC .dir records are not canonically sorted")

    model_files = _walk_regular_tree(repo_root / DEFERRED_DVC_MODELS_TARGET)
    selected_extra_paths = (
        tuple(
            path
            for _, path, _, _ in DEFERRED_DVC_A0_FINAL_RECORDS
            if path.startswith("models/")
        )
        if exact_extra_model_paths is None
        else exact_extra_model_paths
    )
    exact_extras = {
        Path(path).relative_to(DEFERRED_DVC_MODELS_TARGET).as_posix()
        for path in selected_extra_paths
    }
    if set(model_files) != set(baseline) | exact_extras:
        raise DeferredDvcTargetError(
            "Deferred models DVC tree differs from its 248-file baseline plus "
            f"the exact {len(exact_extras)} deferred model files"
        )
    total_bytes = 0
    for relative, digest in baseline.items():
        workspace_path = model_files[relative]
        cache_path = repo_root / ".dvc/cache/files/md5" / digest[:2] / digest[2:]
        _require_no_symlink_ancestors(cache_path, anchor=repo_root)
        cache_metadata = _require_regular_file(cache_path, mode=0o444)
        workspace_metadata = _require_regular_file(workspace_path)
        if _md5_file(cache_path) != digest or _md5_file(workspace_path) != digest:
            raise DeferredDvcTargetError(f"Deferred models DVC baseline object drifted: {relative}")
        if cache_metadata.st_size != workspace_metadata.st_size:
            raise DeferredDvcTargetError(f"Deferred models DVC baseline size drifted: {relative}")
        total_bytes += workspace_metadata.st_size
    if total_bytes != DEFERRED_DVC_MODELS_BYTES:
        raise DeferredDvcTargetError("Deferred models DVC baseline byte count drifted")


def snapshot_deferred_dvc_models_bundle(
    *, repo_root: Path = Path(".")
) -> tuple[DeferredDvcFinalSnapshot, ...]:
    snapshots: list[DeferredDvcFinalSnapshot] = []
    for _, raw_path, expected_bytes, expected_sha256 in DEFERRED_DVC_A0_FINAL_RECORDS:
        path = repo_root / raw_path
        _require_no_symlink_ancestors(path, anchor=repo_root)
        metadata = _require_regular_file(path, mode=0o644)
        if metadata.st_nlink != 1:
            raise DeferredDvcTargetError(
                f"Deferred A0 final must have one hard link: {raw_path}"
            )
        digest = sha256_file(path)
        if metadata.st_size != expected_bytes or digest != expected_sha256:
            raise DeferredDvcTargetError(f"Deferred A0 final bytes drifted: {raw_path}")
        snapshots.append(
            DeferredDvcFinalSnapshot(
                path=raw_path,
                device=metadata.st_dev,
                inode=metadata.st_ino,
                mtime_ns=metadata.st_mtime_ns,
                size=metadata.st_size,
                sha256=digest,
                mode=stat.S_IMODE(metadata.st_mode),
                nlink=metadata.st_nlink,
                ctime_ns=metadata.st_ctime_ns,
            )
        )
        temporary = Path(f"{path}.tmp")
        if os.path.lexists(temporary):
            raise DeferredDvcTargetError(f"Deferred A0 temporary is present: {temporary}")
    if snapshots[-1].mtime_ns <= max(record.mtime_ns for record in snapshots[:-1]):
        raise DeferredDvcTargetError("Deferred A0 manifest is not physically last")
    for prohibited in (
        repo_root / DEFERRED_DVC_A0_PREDICTION_POINTER,
        repo_root / Path(f"{DEFERRED_DVC_A0_PREDICTION_POINTER}.tmp"),
        repo_root / DEFERRED_DVC_A0_GUARD,
    ):
        if os.path.lexists(prohibited):
            raise DeferredDvcTargetError(f"Deferred A0 prohibited path is present: {prohibited}")
    report_root = repo_root / "reports/closure_v1/02_models/A0"
    expected_reports = {
        Path(record.path).name
        for record in snapshots
        if record.path.startswith("reports/")
    }
    if set(_walk_regular_tree(report_root)) != expected_reports:
        raise DeferredDvcTargetError(
            "Deferred A0 report namespace is not the exact five-file prefix"
        )
    prediction_root = repo_root / "data/closure_v1/development/anfis_ablation"
    expected_prediction = {
        Path(DEFERRED_DVC_A0_FINAL_RECORDS[4][1])
        .relative_to("data/closure_v1/development/anfis_ablation")
        .as_posix()
    }
    if set(_walk_regular_tree(prediction_root)) != expected_prediction:
        raise DeferredDvcTargetError(
            "Deferred A0 prediction namespace is not the exact one-file prefix"
        )
    if os.path.lexists(repo_root / "reports/closure_v1/02_models/A1"):
        raise DeferredDvcTargetError("Deferred A1 report namespace must remain absent")
    return tuple(snapshots)


def validate_deferred_dvc_models_state(
    dvc_status: Mapping[str, Any],
    *,
    repo_root: Path = Path("."),
    expected_final_snapshot: tuple[DeferredDvcFinalSnapshot, ...] | None = None,
) -> tuple[DeferredDvcFinalSnapshot, ...]:
    if dict(dvc_status) != DEFERRED_DVC_MODELS_STATUS:
        raise DeferredDvcTargetError(
            "Deferred models DVC status must be the exact single modified models output"
        )
    _validate_deferred_models_pointer(repo_root)
    _validate_deferred_models_tree(repo_root)
    snapshot = snapshot_deferred_dvc_models_bundle(repo_root=repo_root)
    if expected_final_snapshot is not None and snapshot != expected_final_snapshot:
        raise DeferredDvcTargetError("Deferred A0 inode/mtime/hash snapshot drifted")
    _validate_deferred_a0_git_tracking(repo_root)
    staged = _git_output(
        repo_root,
        "diff",
        "--cached",
        "--name-only",
        "--",
        *(record.path for record in snapshot),
    ).strip()
    if staged:
        raise DeferredDvcTargetError("Deferred A0 finals must not be staged")
    return snapshot


def _anfis_ablation_slot_final_paths(
    model_id: str, base_seed: int
) -> tuple[str, ...]:
    report_root = f"reports/closure_v1/02_models/{model_id}/seed_{base_seed}"
    return (
        f"models/closure_v1/anfis_ablation/{model_id}/seed_{base_seed}.pt",
        (
            "models/closure_v1/anfis_ablation/"
            f"{model_id}/seed_{base_seed}.checkpoint.pt"
        ),
        f"{report_root}_preprocessor.json",
        f"{report_root}_training_curve.csv",
        (
            "data/closure_v1/development/anfis_ablation/"
            f"{model_id}/seed_{base_seed}_selection_predictions.parquet"
        ),
        f"{report_root}_selection_metrics.csv",
        f"{report_root}_report.md",
        f"{report_root}_manifest.json",
    )


def _snapshot_anfis_ablation_final(
    raw_path: str,
    *,
    expected_bytes: int,
    expected_sha256: str,
    repo_root: Path,
) -> DeferredDvcFinalSnapshot:
    path = repo_root / raw_path
    _require_no_symlink_ancestors(path, anchor=repo_root)
    metadata = _require_regular_file(path, mode=0o644)
    if metadata.st_nlink != 1:
        raise DeferredDvcTargetError(
            f"ANFIS-ablation final must have one hard link: {raw_path}"
        )
    digest = sha256_file(path)
    if metadata.st_size != expected_bytes or digest != expected_sha256:
        raise DeferredDvcTargetError(
            f"ANFIS-ablation final bytes drifted: {raw_path}"
        )
    if os.path.lexists(Path(f"{path}.tmp")):
        raise DeferredDvcTargetError(
            f"ANFIS-ablation temporary is present: {path}.tmp"
        )
    return DeferredDvcFinalSnapshot(
        path=raw_path,
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mtime_ns=metadata.st_mtime_ns,
        size=metadata.st_size,
        sha256=digest,
        mode=stat.S_IMODE(metadata.st_mode),
        nlink=metadata.st_nlink,
        ctime_ns=metadata.st_ctime_ns,
    )


def snapshot_anfis_ablation_family_bundle(
    *,
    repo_root: Path = Path("."),
    expected_pointer_count: int = 0,
    _allow_in_progress_prefix: bool = False,
) -> tuple[DeferredDvcFinalSnapshot, ...]:
    """Snapshot all 80 immutable A0/A1 finals before family registration."""
    if type(_allow_in_progress_prefix) is not bool:
        raise DeferredDvcTargetError(
            "ANFIS-ablation snapshot requires an exact boolean in-progress policy"
        )
    allowed_pointer_counts = (
        set(range(11)) if _allow_in_progress_prefix else {0, 10}
    )
    if (
        type(expected_pointer_count) is not int
        or expected_pointer_count not in allowed_pointer_counts
    ):
        raise DeferredDvcTargetError(
            "ANFIS-ablation snapshot requires an exact pre/post registration "
            "pointer set"
        )
    snapshots: list[DeferredDvcFinalSnapshot] = []
    expected_output_roles = (
        "model",
        "checkpoint",
        "preprocessor",
        "training_curve",
        "selection_predictions",
        "selection_metrics",
        "report",
    )
    for slot_index, (model_id, base_seed) in enumerate(
        ANFIS_ABLATION_ORDERED_SLOTS
    ):
        final_paths = _anfis_ablation_slot_final_paths(model_id, base_seed)
        manifest_path = repo_root / final_paths[-1]
        _require_no_symlink_ancestors(manifest_path, anchor=repo_root)
        manifest_metadata = _require_regular_file(manifest_path, mode=0o644)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeferredDvcTargetError(
                f"ANFIS-ablation manifest is invalid JSON: {manifest_path}"
            ) from exc
        outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
        if (
            not isinstance(manifest, dict)
            or manifest.get("status") != "completed"
            or manifest.get("slot_status") != "available"
            or manifest.get("fit_status") != "passed"
            or manifest.get("model_id") != model_id
            or manifest.get("base_seed") != base_seed
            or manifest.get("dvc_command_executed") is not False
            or manifest.get("completion_marker_written_last") is not True
            or not isinstance(outputs, list)
            or len(outputs) != 7
        ):
            raise DeferredDvcTargetError(
                f"ANFIS-ablation manifest identity/status drifted: {manifest_path}"
            )
        slot_snapshots: list[DeferredDvcFinalSnapshot] = []
        for role, expected_path, raw_record in zip(
            expected_output_roles, final_paths[:-1], outputs, strict=True
        ):
            if not isinstance(raw_record, dict):
                raise DeferredDvcTargetError(
                    f"ANFIS-ablation output record drifted: {manifest_path}"
                )
            record = cast(dict[str, Any], raw_record)
            if (
                set(record) != {"role", "path", "bytes", "sha256"}
                or record.get("role") != role
                or record.get("path") != expected_path
                or type(record.get("bytes")) is not int
                or not isinstance(record.get("sha256"), str)
                or len(record["sha256"]) != 64
            ):
                raise DeferredDvcTargetError(
                    f"ANFIS-ablation output record drifted: {manifest_path}"
                )
            slot_snapshots.append(
                _snapshot_anfis_ablation_final(
                    expected_path,
                    expected_bytes=int(record["bytes"]),
                    expected_sha256=str(record["sha256"]),
                    repo_root=repo_root,
                )
            )
        manifest_digest = sha256_file(manifest_path)
        manifest_snapshot = _snapshot_anfis_ablation_final(
            final_paths[-1],
            expected_bytes=manifest_metadata.st_size,
            expected_sha256=manifest_digest,
            repo_root=repo_root,
        )
        if manifest_snapshot.mtime_ns <= max(
            record.mtime_ns for record in slot_snapshots
        ):
            raise DeferredDvcTargetError(
                f"ANFIS-ablation manifest is not physically last: {manifest_path}"
            )
        snapshots.extend((*slot_snapshots, manifest_snapshot))

        pointer = repo_root / (
            "data/closure_v1/development/anfis_ablation/"
            f"{model_id}/seed_{base_seed}_selection_predictions.parquet.dvc"
        )
        guard = repo_root / (
            "tmp/closure_v1_anfis_ablation_training/"
            f"{model_id}_seed_{base_seed}.guard"
        )
        prohibited_paths = (Path(f"{pointer}.tmp"), guard)
        pointer_expected = slot_index < expected_pointer_count
        if pointer_expected and os.path.lexists(pointer):
            _require_no_symlink_ancestors(pointer, anchor=repo_root)
            pointer_metadata = _require_regular_file(pointer, mode=0o644)
            if pointer_metadata.st_nlink != 1:
                raise DeferredDvcTargetError(
                    f"ANFIS-ablation pointer must have one hard link: {pointer}"
                )
        elif pointer_expected:
            raise DeferredDvcTargetError(
                f"ANFIS-ablation post-registration pointer is absent: {pointer}"
            )
        elif os.path.lexists(pointer):
            raise DeferredDvcTargetError(
                f"ANFIS-ablation out-of-prefix pointer is present: {pointer}"
            )
        for prohibited in prohibited_paths:
            if os.path.lexists(prohibited):
                raise DeferredDvcTargetError(
                    f"ANFIS-ablation pre-registration path is present: {prohibited}"
                )

    if len(snapshots) != 80 or len({record.path for record in snapshots}) != 80:
        raise DeferredDvcTargetError(
            "ANFIS-ablation family snapshot is not exactly 80 unique finals"
        )
    expected_reports = {
        Path(path).relative_to("reports/closure_v1/02_models").as_posix()
        for path in ANFIS_ABLATION_LIGHT_REPORT_PATHS
    }
    observed_reports = {
        path
        for path in _walk_regular_tree(repo_root / "reports/closure_v1/02_models")
        if path.startswith(("A0/", "A1/"))
    }
    if observed_reports != expected_reports:
        raise DeferredDvcTargetError(
            "ANFIS-ablation report namespace is not the exact 50-file family"
        )
    prediction_root = repo_root / ANFIS_ABLATION_SELECTION_ROOT
    prediction_relative_root = prediction_root.relative_to(repo_root)
    expected_predictions = {
        Path(path).relative_to(prediction_relative_root).as_posix()
        for path in ANFIS_ABLATION_SELECTION_PREDICTION_PATHS
    }
    expected_predictions.update(
        Path(path).relative_to(prediction_relative_root).as_posix()
        for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS[
            :expected_pointer_count
        ]
    )
    if set(_walk_regular_tree(prediction_root)) != expected_predictions:
        raise DeferredDvcTargetError(
            "ANFIS-ablation prediction namespace is not the exact ten payloads "
            "plus canonical pointer prefix"
        )
    model_root = repo_root / "models/closure_v1/anfis_ablation"
    expected_models = {
        Path(path).relative_to("models/closure_v1/anfis_ablation").as_posix()
        for path in ANFIS_ABLATION_MODEL_PATHS
    }
    if set(_walk_regular_tree(model_root)) != expected_models:
        raise DeferredDvcTargetError(
            "ANFIS-ablation model namespace is not the exact twenty files"
        )
    return tuple(snapshots)


def validate_deferred_dvc_anfis_ablation_family_state(
    dvc_status: Mapping[str, Any],
    *,
    repo_root: Path = Path("."),
    expected_final_snapshot: tuple[DeferredDvcFinalSnapshot, ...] | None = None,
) -> tuple[DeferredDvcFinalSnapshot, ...]:
    """Validate the complete pre-registration family under H/P-E0-MY."""
    if dict(dvc_status) != DEFERRED_DVC_MODELS_STATUS:
        raise DeferredDvcTargetError(
            "Deferred family DVC status must be the exact modified models output"
        )
    _validate_deferred_models_pointer(repo_root)
    _validate_deferred_models_tree(
        repo_root, exact_extra_model_paths=ANFIS_ABLATION_MODEL_PATHS
    )
    snapshot = snapshot_anfis_ablation_family_bundle(repo_root=repo_root)
    if expected_final_snapshot is not None and snapshot != expected_final_snapshot:
        raise DeferredDvcTargetError(
            "Deferred ANFIS-ablation family inode/ctime/mtime/hash snapshot drifted"
        )
    _validate_deferred_a0_git_tracking(repo_root)
    tracked_family = _git_output(
        repo_root,
        "ls-files",
        "--",
        *ANFIS_ABLATION_LIGHT_REPORT_PATHS,
    ).splitlines()
    if tracked_family != sorted(ANFIS_ABLATION_TRACKED_LIGHT_PATHS):
        raise DeferredDvcTargetError(
            "Deferred ANFIS-ablation lightweight Git prefix drifted"
        )
    staged = _git_output(
        repo_root,
        "diff",
        "--cached",
        "--name-only",
        "--",
        *(record.path for record in snapshot),
        DEFERRED_DVC_MODELS_POINTER.as_posix(),
        *ANFIS_ABLATION_SELECTION_POINTER_PATHS,
    ).strip()
    if staged:
        raise DeferredDvcTargetError(
            "Deferred ANFIS-ablation finals or DVC pointers must not be staged"
        )
    return snapshot


def validate_deferred_dvc_anfis_ablation_adoption_family_state(
    dvc_status: Mapping[str, Any],
    *,
    repo_root: Path = Path("."),
    expected_final_snapshot: tuple[DeferredDvcFinalSnapshot, ...] | None = None,
) -> tuple[DeferredDvcFinalSnapshot, ...]:
    """Validate the MZ family: fifty Git-bound lights and thirty heavy finals."""
    if dict(dvc_status) != DEFERRED_DVC_MODELS_STATUS:
        raise DeferredDvcTargetError(
            "E0-MZE deferred family DVC status must be the exact modified models output"
        )
    _validate_deferred_models_pointer(repo_root)
    _validate_deferred_models_tree(
        repo_root, exact_extra_model_paths=ANFIS_ABLATION_MODEL_PATHS
    )
    snapshot = snapshot_anfis_ablation_family_bundle(
        repo_root=repo_root, expected_pointer_count=0
    )
    if expected_final_snapshot is not None and snapshot != expected_final_snapshot:
        raise DeferredDvcTargetError(
            "E0-MZE ANFIS-ablation family physical snapshot drifted"
        )
    _validate_anfis_ablation_mz_git_tracking(repo_root)
    tracked_family = _git_output(
        repo_root,
        "ls-files",
        "--",
        *ANFIS_ABLATION_LIGHT_REPORT_PATHS,
    ).splitlines()
    if tracked_family != sorted(ANFIS_ABLATION_MZ_TRACKED_LIGHT_PATHS):
        raise DeferredDvcTargetError(
            "E0-MZE lightweight Git inventory is not the exact fifty reports"
        )
    staged = _git_output(
        repo_root,
        "diff",
        "--cached",
        "--name-only",
        "--",
        *(record.path for record in snapshot),
        DEFERRED_DVC_MODELS_POINTER.as_posix(),
        *ANFIS_ABLATION_SELECTION_POINTER_PATHS,
    ).strip()
    if staged:
        raise DeferredDvcTargetError(
            "E0-MZE finals or DVC pointers must not be staged before registration"
        )
    return snapshot


def sha256_directory(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    total_bytes = 0
    for file_path in sorted(item for item in path.rglob("*") if item.is_file() and not item.name.endswith(".tmp")):
        relative_path = file_path.relative_to(path).as_posix()
        file_hash = sha256_file(file_path)
        file_bytes = file_path.stat().st_size
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
        total_bytes += file_bytes
    return total_bytes, digest.hexdigest()


def run_command(command: list[str], *, check: bool = True, env: dict[str, str] | None = None) -> CommandResult:
    process = subprocess.run(command, check=False, text=True, capture_output=True, env=env)
    result = CommandResult(
        command=command,
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )
    if check and result.returncode != 0:
        print(f"Command failed: {command_text(command)}", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def dvc_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("DVC_SITE_CACHE_DIR", DEFAULT_DVC_SITE_CACHE_DIR.as_posix())
    return env


def resolve_dvc_bin(explicit_path: str | None) -> str:
    candidates = [
        explicit_path,
        os.environ.get("DVC_BIN"),
        DEFAULT_DVC_BIN.as_posix(),
        "dvc",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            return path.as_posix()
        resolved = run_command(["bash", "-lc", f"command -v {shlex.quote(candidate)}"], check=False)
        if resolved.returncode == 0 and resolved.stdout.strip():
            return resolved.stdout.strip()
    raise SystemExit("Could not find dvc. Expected .venv/bin/dvc or set DVC_BIN.")


def ensure_repo_root() -> None:
    if not Path(".git").is_dir():
        raise SystemExit("Run this from the repository root.")


def load_dvc_artifacts(manifest_path: Path) -> list[DvcArtifact]:
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path} must contain a YAML mapping")

    artifacts = []
    for raw_artifact in manifest.get("artifacts", []):
        if not isinstance(raw_artifact, dict):
            raise ValueError("Each artifact entry must be a YAML mapping")
        artifacts.append(
            DvcArtifact(
                artifact_id=str(raw_artifact["artifact_id"]),
                path=Path(str(raw_artifact["path"])),
                artifact_type=str(raw_artifact.get("type", "")),
                source_id=str(raw_artifact.get("source_id", "")),
                dvc=bool(raw_artifact.get("dvc", False)),
            )
        )
    return artifacts


def load_anfis_ablation_registration_artifacts(
    overlay_path: Path = DEFAULT_CLOSURE_DVC_MANIFEST,
) -> list[DvcArtifact]:
    """Load only the closed ten-payload E0-MY registration inventory."""
    with overlay_path.open("r", encoding="utf-8") as handle:
        overlay = yaml.safe_load(handle)
    if not isinstance(overlay, dict):
        raise ValueError(f"{overlay_path} must contain a YAML mapping")
    raw_records = overlay.get(ANFIS_ABLATION_REGISTRATION_INVENTORY_KEY)
    if not isinstance(raw_records, list) or len(raw_records) != 10:
        raise ValueError(
            f"{overlay_path} must declare exactly ten "
            f"{ANFIS_ABLATION_REGISTRATION_INVENTORY_KEY} records"
        )

    expected_records = [
        {
            "artifact_id": (
                "closure_v1_anfis_ablation_"
                f"{model_id.lower()}_seed_{base_seed}_selection_predictions"
            ),
            "path": prediction_path,
            "type": "closure_anfis_ablation_selection_predictions",
            "source_id": "wqp",
            "model_id": model_id,
            "base_seed": base_seed,
            "dvc": True,
            "github_policy": (
                "pointer_only_keep_manifest_and_lightweight_reports_in_git"
            ),
        }
        for (model_id, base_seed), prediction_path in zip(
            ANFIS_ABLATION_ORDERED_SLOTS,
            ANFIS_ABLATION_SELECTION_PREDICTION_PATHS,
            strict=True,
        )
    ]
    if raw_records != expected_records:
        raise ValueError(
            "Closure ANFIS-ablation registration inventory order or dialect drifted"
        )
    return [
        DvcArtifact(
            artifact_id=str(record["artifact_id"]),
            path=Path(str(record["path"])),
            artifact_type=str(record["type"]),
            source_id=str(record["source_id"]),
            dvc=True,
        )
        for record in expected_records
    ]


def validate_closure_dvc_overlay_anchor(
    overlay_path: Path = DEFAULT_CLOSURE_DVC_MANIFEST,
) -> None:
    """Require the post-lock overlay to extend the exact E0-P base inventory."""
    with overlay_path.open("r", encoding="utf-8") as handle:
        overlay = yaml.safe_load(handle)
    anchor = overlay.get("sealed_base_inventory") if isinstance(overlay, dict) else None
    if not isinstance(anchor, dict):
        raise ValueError(f"{overlay_path} must declare sealed_base_inventory")
    expected_anchor = {
        "path": DEFAULT_DVC_MANIFEST.as_posix(),
        "bytes": 18841,
        "sha256": "3304fd61978604ecfba5f99f1a9b3d04e4655f45f97f92954081751346143605",
        "authority": CLOSURE_PROTOCOL_LOCK_PATH.as_posix(),
    }
    if anchor != expected_anchor:
        raise ValueError(f"{overlay_path} sealed_base_inventory differs from E0-P")

    protocol_lock = json.loads(CLOSURE_PROTOCOL_LOCK_PATH.read_text(encoding="utf-8"))
    source_records = protocol_lock.get("source_artifacts") if isinstance(protocol_lock, dict) else None
    matching_records = (
        [
            record
            for record in source_records
            if isinstance(record, dict) and record.get("path") == DEFAULT_DVC_MANIFEST.as_posix()
        ]
        if isinstance(source_records, list)
        else []
    )
    if len(matching_records) != 1:
        raise ValueError("Closure protocol lock must contain the sealed base DVC inventory")
    locked_record = matching_records[0]
    if (
        locked_record.get("bytes") != anchor["bytes"]
        or locked_record.get("sha256") != anchor["sha256"]
    ):
        raise ValueError("Closure DVC overlay anchor differs from the protocol-lock source record")
    if (
        DEFAULT_DVC_MANIFEST.stat().st_size != anchor["bytes"]
        or sha256_file(DEFAULT_DVC_MANIFEST) != anchor["sha256"]
    ):
        raise ValueError("Protocol-locked base DVC inventory changed")


def load_configured_dvc_artifacts(manifest_path: Path) -> list[DvcArtifact]:
    """Load the sealed base inventory plus its derived Closure V1 overlay."""
    manifest_paths = [manifest_path]
    if manifest_path.resolve() == DEFAULT_DVC_MANIFEST.resolve():
        validate_closure_dvc_overlay_anchor()
        manifest_paths.append(DEFAULT_CLOSURE_DVC_MANIFEST)
    artifacts = [
        artifact
        for configured_path in manifest_paths
        for artifact in load_dvc_artifacts(configured_path)
    ]
    artifact_ids = [artifact.artifact_id for artifact in artifacts]
    artifact_paths = [artifact.path for artifact in artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("DVC artifact inventories contain duplicate artifact_id values")
    if len(artifact_paths) != len(set(artifact_paths)):
        raise ValueError("DVC artifact inventories contain duplicate paths")
    return artifacts


def dvc_pointer_path(path: Path) -> Path:
    if path.is_dir():
        return path.with_name(path.name + ".dvc")
    return Path(path.as_posix() + ".dvc")


def path_text(path: Path) -> str:
    return path.as_posix().rstrip("/")


def is_same_or_inside(candidate: str, parent: Path) -> bool:
    parent_text = path_text(parent)
    candidate = candidate.rstrip("/")
    return candidate == parent_text or candidate.startswith(parent_text + "/")


def is_artifact_covered(candidate: str, artifacts: list[DvcArtifact]) -> bool:
    for artifact in artifacts:
        if not artifact.dvc:
            continue
        if is_same_or_inside(candidate, artifact.path):
            return True
        if candidate == dvc_pointer_path(artifact.path).as_posix():
            return True
    return False


def has_local_dvc_pointer(candidate: Path) -> bool:
    """Return true when a path is protected by a local DVC pointer file."""
    for path in [candidate, *candidate.parents]:
        if path == Path("."):
            break
        if dvc_pointer_path(path).exists():
            return True
    return False


def collect_strings(value: Any) -> set[str]:
    strings: set[str] = set()
    if isinstance(value, str):
        strings.add(value)
    elif isinstance(value, dict):
        for key, nested in value.items():
            strings.update(collect_strings(key))
            strings.update(collect_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            strings.update(collect_strings(nested))
    return strings


def dvc_status_json(
    dvc_bin: str, *, env: Mapping[str, str] | None = None
) -> dict[str, Any]:
    result = run_command(
        [dvc_bin, "status", "--json"],
        env=dvc_environment() if env is None else dict(env),
    )
    if not result.stdout.strip():
        return {}
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        return {}
    return payload


def dvc_status_candidates(status_payload: dict[str, Any], artifacts: list[DvcArtifact]) -> list[DvcArtifact]:
    if not status_payload:
        return []
    status_strings = collect_strings(status_payload)
    candidates = []
    for artifact in artifacts:
        if not artifact.dvc or not artifact.path.exists():
            continue
        pointer = dvc_pointer_path(artifact.path).as_posix()
        for item in status_strings:
            if item == pointer or is_same_or_inside(item, artifact.path):
                candidates.append(artifact)
                break
    return sorted(set(candidates), key=lambda artifact: artifact.path.as_posix())


def declared_artifacts_missing_pointers(artifacts: list[DvcArtifact]) -> list[DvcArtifact]:
    candidates = []
    for artifact in artifacts:
        if not artifact.dvc:
            continue
        if not artifact.path.exists():
            continue
        if dvc_pointer_path(artifact.path).exists():
            continue
        candidates.append(artifact)
    return sorted(candidates, key=lambda artifact: artifact.path.as_posix())


def validate_anfis_ablation_registration_missing_pointer_set(
    missing: list[DvcArtifact],
) -> list[DvcArtifact]:
    """Require the closed ten-payload set without promoting discovery order."""
    observed_paths = [artifact.path for artifact in missing]
    expected_paths = {
        Path(path) for path in ANFIS_ABLATION_SELECTION_PREDICTION_PATHS
    }
    if (
        len(observed_paths) != 10
        or len(set(observed_paths)) != 10
        or set(observed_paths) != expected_paths
    ):
        raise DeferredDvcTargetError(
            "E0-MZE missing-pointer set is not the exact ten predictions"
        )
    return list(missing)


def parse_git_status_lines(output: str) -> list[tuple[str, str]]:
    rows = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        rows.append((line[:2], line[3:]))
    return rows


def validate_anfis_ablation_git_short_status_map(
    status_output: str,
    *,
    expected: Mapping[str, str],
    context: str,
) -> dict[str, str]:
    """Require an exact porcelain-v1 path/status map, ignoring only line order."""
    if type(status_output) is not str or type(context) is not str or not context:
        raise DeferredDvcTargetError(
            "E0-MZE Git short-status validation arguments are malformed"
        )
    if not isinstance(expected, Mapping):
        raise DeferredDvcTargetError(
            f"E0-MZE {context} expected path/status map is malformed"
        )
    expected_map = dict(expected)
    if any(
        type(path) is not str
        or not path
        or type(status_code) is not str
        or status_code not in {"??", " M", "M ", "A "}
        for path, status_code in expected_map.items()
    ):
        raise DeferredDvcTargetError(
            f"E0-MZE {context} expected path/status map is malformed"
        )
    observed: dict[str, str] = {}
    for line in status_output.splitlines():
        if len(line) < 4 or line[2] != " " or not line[3:]:
            raise DeferredDvcTargetError(
                f"E0-MZE {context} contains a malformed Git short-status line"
            )
        status_code = line[:2]
        raw_path = line[3:]
        if raw_path in observed:
            raise DeferredDvcTargetError(
                f"E0-MZE {context} contains a duplicate Git path"
            )
        observed[raw_path] = status_code
    if observed != expected_map:
        raise DeferredDvcTargetError(
            f"E0-MZE {context} differs from the exact path/status map"
        )
    return observed


def _parse_anfis_ablation_git_name_status_map(
    status_output: str, *, context: str
) -> dict[str, str]:
    """Parse an exact A/M ``--name-status`` map without skipping input."""
    if type(status_output) is not str or type(context) is not str or not context:
        raise DeferredDvcTargetError(
            "E0-MZE Git name-status validation arguments are malformed"
        )
    observed: dict[str, str] = {}
    for line in status_output.splitlines():
        fields = line.split("\t")
        if (
            len(fields) != 2
            or fields[0] not in {"A", "M"}
            or not fields[1]
            or fields[1] in observed
        ):
            raise DeferredDvcTargetError(
                f"E0-MZE {context} contains a malformed Git name-status line"
            )
        observed[fields[1]] = fields[0]
    return observed


def validate_anfis_ablation_git_name_status_map(
    status_output: str,
    *,
    expected: Mapping[str, str],
    context: str,
) -> dict[str, str]:
    """Require an exact A/M name-status map, ignoring only record order."""
    if not isinstance(expected, Mapping):
        raise DeferredDvcTargetError(
            f"E0-MZE {context} expected name-status map is malformed"
        )
    expected_map = dict(expected)
    if any(
        type(path) is not str
        or not path
        or type(status_code) is not str
        or status_code not in {"A", "M"}
        for path, status_code in expected_map.items()
    ):
        raise DeferredDvcTargetError(
            f"E0-MZE {context} expected name-status map is malformed"
        )
    observed = _parse_anfis_ablation_git_name_status_map(
        status_output, context=context
    )
    if observed != expected_map:
        raise DeferredDvcTargetError(
            f"E0-MZE {context} differs from the exact path/status map"
        )
    return observed


def parse_git_name_status(output: str) -> list[tuple[str, Path]]:
    rows = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        rows.append((parts[0], Path(parts[-1])))
    return rows


def validate_deferred_dvc_staged_scope(staged_status: str) -> str:
    for gate, expected_scope in _deferred_dvc_staged_scopes().items():
        try:
            validate_anfis_ablation_git_name_status_map(
                staged_status,
                expected=expected_scope,
                context=f"{gate} deferred staged scope",
            )
        except DeferredDvcTargetError:
            continue
        else:
            return gate
    raise DeferredDvcTargetError(
        "Deferred models staging must match one exact historical H/P scope or "
        "current H-E0-MZE 9M+5A/P-E0-MZE 2A"
    )


def validate_deferred_dvc_pre_stage_scope(status_output: str) -> str:
    def expected(scope: Mapping[str, str]) -> dict[str, str]:
        return {
            path: ("??" if staged_code == "A" else " M")
            for path, staged_code in scope.items()
        }

    for gate, expected_scope in _deferred_dvc_staged_scopes().items():
        try:
            validate_anfis_ablation_git_short_status_map(
                status_output,
                expected=expected(expected_scope),
                context=f"{gate} deferred pre-stage scope",
            )
        except DeferredDvcTargetError:
            continue
        else:
            return gate
    raise DeferredDvcTargetError(
        "Deferred models pre-stage scope must match one exact historical H/P "
        "scope or current H-E0-MZE 9M+5A/P-E0-MZE 2A"
    )


def validate_deferred_dvc_staged_bindings(
    gate: str, *, repo_root: Path = Path(".")
) -> None:
    expected_modes = _deferred_dvc_git_modes().get(gate)
    expected_scope = _deferred_dvc_staged_scopes().get(gate)
    if expected_modes is None or expected_scope is None:
        raise DeferredDvcTargetError("Deferred models staged binding gate is unknown")
    staged_status = _git_output(
        repo_root, "diff", "--cached", "--name-status"
    )
    try:
        observed_gate = validate_deferred_dvc_staged_scope(staged_status)
    except DeferredDvcTargetError as exc:
        raise DeferredDvcTargetError(
            f"Deferred models staging must remain exact {gate}"
        ) from exc
    if observed_gate != gate:
        raise DeferredDvcTargetError(
            f"Deferred models staging must remain exact {gate}"
        )
    expected_short_status = _expected_short_scope(expected_scope, staged=True)
    observed_short_status = _git_output(
        repo_root, "status", "--short", "--untracked-files=normal"
    )
    validate_anfis_ablation_git_short_status_map(
        observed_short_status,
        expected=expected_short_status,
        context=f"{gate} deferred staged scope",
    )
    if _git_output(repo_root, "diff", "--name-status").strip():
        raise DeferredDvcTargetError(
            "Deferred models mode left an unstaged tracked change"
        )
    for raw_path, git_mode in sorted(expected_modes.items()):
        path = repo_root / raw_path
        _require_no_symlink_ancestors(path, anchor=repo_root)
        physical_mode = 0o755 if git_mode == "100755" else 0o644
        _require_regular_file(path, mode=physical_mode)
        index_line = _git_output(
            repo_root, "ls-files", "-s", "--", raw_path
        ).strip()
        parts = index_line.split(maxsplit=3)
        if (
            len(parts) != 4
            or parts[0] != git_mode
            or parts[2] != "0"
            or parts[3] != raw_path
        ):
            raise DeferredDvcTargetError(
                f"Deferred models staged mode/stage binding drifted: {raw_path}"
            )
        index_oid = parts[1]
        worktree_oid = _git_output(
            repo_root, "hash-object", "--no-filters", "--", raw_path
        ).strip()
        if index_oid != worktree_oid or len(index_oid) != 40:
            raise DeferredDvcTargetError(
                f"Deferred models staged blob differs from worktree: {raw_path}"
            )


def _expected_short_scope(
    scope: Mapping[str, str], *, staged: bool
) -> dict[str, str]:
    return {
        path: (
            f"{status_code} "
            if staged
            else "??" if status_code == "A" else " M"
        )
        for path, status_code in scope.items()
    }


def validate_anfis_ablation_registration_initial_scope(
    status_output: str,
) -> None:
    validate_anfis_ablation_git_short_status_map(
        status_output,
        expected={},
        context="registration initial scope",
    )


def validate_anfis_ablation_registration_pre_stage_scope(
    status_output: str,
) -> str:
    validate_anfis_ablation_git_short_status_map(
        status_output,
        expected=_expected_short_scope(
            ANFIS_ABLATION_R_MZE_STAGED_SCOPE, staged=False
        ),
        context="R-E0-MZE post-DVC pre-stage scope",
    )
    return "R-E0-MZE"


def validate_anfis_ablation_registration_staged_scope(
    staged_status: str,
) -> str:
    validate_anfis_ablation_git_name_status_map(
        staged_status,
        expected=ANFIS_ABLATION_R_MZE_STAGED_SCOPE,
        context="R-E0-MZE staged scope; registration staged scope",
    )
    return "R-E0-MZE"


def validate_anfis_ablation_registration_staged_bindings(
    *, repo_root: Path = Path(".")
) -> None:
    staged_status = _git_output(
        repo_root, "diff", "--cached", "--name-status"
    )
    validate_anfis_ablation_registration_staged_scope(staged_status)
    observed_short = _git_output(
        repo_root, "status", "--short", "--untracked-files=normal"
    )
    validate_anfis_ablation_git_short_status_map(
        observed_short,
        expected=_expected_short_scope(
            ANFIS_ABLATION_R_MZE_STAGED_SCOPE, staged=True
        ),
        context="R-E0-MZE staged scope",
    )
    if _git_output(repo_root, "diff", "--name-status").strip():
        raise DeferredDvcTargetError(
            "R-E0-MZE left an unstaged tracked change"
        )
    for raw_path, git_mode in sorted(ANFIS_ABLATION_R_MZE_GIT_MODES.items()):
        path = repo_root / raw_path
        _require_no_symlink_ancestors(path, anchor=repo_root)
        metadata = _require_regular_file(path, mode=0o644)
        if metadata.st_nlink != 1:
            raise DeferredDvcTargetError(
                f"R-E0-MZE staged metadata must have one hard link: {raw_path}"
            )
        index_line = _git_output(
            repo_root, "ls-files", "-s", "--", raw_path
        ).strip()
        parts = index_line.split(maxsplit=3)
        if (
            len(parts) != 4
            or parts[0] != git_mode
            or parts[2] != "0"
            or parts[3] != raw_path
        ):
            raise DeferredDvcTargetError(
                f"R-E0-MZE staged mode/stage binding drifted: {raw_path}"
            )
        worktree_oid = _git_output(
            repo_root, "hash-object", "--no-filters", "--", raw_path
        ).strip()
        if parts[1] != worktree_oid or len(worktree_oid) != 40:
            raise DeferredDvcTargetError(
                f"R-E0-MZE staged blob differs from worktree: {raw_path}"
            )


def should_skip_ignored_path(path: str) -> bool:
    if path in REGENERABLE_IGNORED_PATHS:
        return True
    if any(path.startswith(prefix) for prefix in IGNORED_PREFIXES_TO_SKIP):
        return True
    if path.startswith("reports/") and path.endswith(REPORT_SMOKE_PARQUET_SUFFIXES):
        return True
    return any(part in IGNORED_PATH_PARTS_TO_SKIP for part in Path(path).parts)


def is_heavy_ignored_path(path: str) -> bool:
    if should_skip_ignored_path(path):
        return False
    if any(path.startswith(prefix) for prefix in HEAVY_PREFIXES):
        return True
    if path.startswith("reports/") and path.endswith(".parquet"):
        return True
    return path == "reports/anfis/operational_site_review_summary.csv"


def unmanaged_ignored_heavy_paths(artifacts: list[DvcArtifact]) -> list[Path]:
    result = run_command(["git", "status", "--short", "--ignored", "--untracked-files=normal"])
    paths = []
    for status, path in parse_git_status_lines(result.stdout):
        normalized = path.rstrip("/")
        if status != "!!":
            continue
        if not is_heavy_ignored_path(normalized):
            continue
        if is_artifact_covered(normalized, artifacts):
            continue
        if has_local_dvc_pointer(Path(normalized)):
            continue
        paths.append(Path(normalized))
    return sorted(set(paths), key=lambda path: path.as_posix())


def versionable_changes() -> str:
    return run_command(["git", "status", "--short", "--untracked-files=normal"]).stdout


def final_calibration_r8_manifest_reproducibility_pre_stage_scope(
    status_output: str,
    *,
    repo_root: Path = Path("."),
) -> tuple[str, tuple[str, ...]] | None:
    """Select only exact H/P/R E0-MCALK paths while R8 remains immutable."""
    patch = _final_calibration_r8_manifest_reproducibility_patch_module()

    def short_map(scope: Mapping[str, str]) -> dict[str, str]:
        return {
            path: "??" if status == "A" else " M"
            for path, status in scope.items()
        }

    h_with_r8 = {
        **short_map(patch.FINAL_CALIBRATION_H_STAGED_SCOPE),
        **short_map(patch.R8_STAGED_SCOPE),
    }
    candidates = (
        ("H-E0-MCALK", h_with_r8, patch.FINAL_CALIBRATION_H_STAGED_SCOPE),
        (
            "P-E0-MCALK",
            {
                **short_map(patch.FINAL_CALIBRATION_P_STAGED_SCOPE),
                **short_map(patch.R8_STAGED_SCOPE),
            },
            patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
        ),
        ("R-E0-MCALK", short_map(patch.R8_STAGED_SCOPE), patch.R8_STAGED_SCOPE),
    )
    candidate_paths = {
        path for _, expected, _ in candidates for path in expected
    }
    observed: dict[str, str] = {}
    anomaly = False
    for line in status_output.splitlines():
        if (
            len(line) < 4
            or line[2] != " "
            or line[:2] not in {"??", " M"}
            or not line[3:]
        ):
            if any(path in line for path in candidate_paths):
                raise FinalCalibrationR8ManifestReproducibilityAdapterError(
                    "E0-MCALK pre-stage scope contains a malformed candidate record"
                )
            anomaly = True
            continue
        path = line[3:]
        if path in observed:
            if path in candidate_paths:
                raise FinalCalibrationR8ManifestReproducibilityAdapterError(
                    "E0-MCALK pre-stage scope contains a duplicate path"
                )
            anomaly = True
            continue
        observed[path] = line[:2]
    if anomaly and set(observed) & candidate_paths:
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(
            "E0-MCALK candidate pre-stage scope contains an extra malformed record"
        )
    for gate, expected, stage_scope in candidates:
        if observed == expected:
            _require_final_calibration_r8_manifest_reproducibility_stage_base(
                gate,
                patch=patch,
                repo_root=repo_root,
            )
            return gate, tuple(sorted(stage_scope))
    if set(observed) & candidate_paths:
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(
            "E0-MCALK candidate pre-stage scope is not exact"
        )
    return None


def _require_final_calibration_r8_manifest_reproducibility_stage_base(
    gate: str,
    *,
    patch: Any,
    repo_root: Path,
) -> None:
    head = _git_output(repo_root, "rev-parse", "HEAD").strip()
    if gate == "H-E0-MCALK":
        if head != patch.BASE_P_MCALJ_COMMIT:
            raise FinalCalibrationR8ManifestReproducibilityAdapterError(
                "H-E0-MCALK staging requires exact P-E0-MCALJ HEAD"
            )
        return
    if gate == "P-E0-MCALK":
        parent = _git_output(repo_root, "rev-parse", "HEAD^").strip()
        scope = _git_output(
            repo_root,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "-r",
            "--no-renames",
            "HEAD",
        )
        if parent != patch.BASE_P_MCALJ_COMMIT:
            raise FinalCalibrationR8ManifestReproducibilityAdapterError(
                "P-E0-MCALK staging requires a direct H child of P-E0-MCALJ"
            )
        validate_anfis_ablation_git_name_status_map(
            scope,
            expected=patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
            context="published H-E0-MCALK scope",
        )
        _require_final_calibration_r8_unpublished_p_validation(
            patch=patch,
            repo_root=repo_root,
            expected_stage_state="untracked",
        )
        return
    if gate == "R-E0-MCALK":
        authority = patch.require_final_calibration_r8_manifest_reproducibility_patch_authority(
            repo_root=repo_root,
            verify_remote=True,
        )
        if (
            type(authority) is not dict
            or authority.get("gate") != patch.PATCH_GATE
            or authority.get("r8_staging_authorized") is not True
        ):
            raise FinalCalibrationR8ManifestReproducibilityAdapterError(
                "R-E0-MCALK staging requires exact effective P-E0-MCALK authority"
            )
        return
    raise FinalCalibrationR8ManifestReproducibilityAdapterError(
        "Unknown E0-MCALK staging gate"
    )


def _require_final_calibration_r8_unpublished_p_validation(
    *,
    patch: Any,
    repo_root: Path,
    expected_stage_state: str,
) -> dict[str, Any]:
    try:
        validation = patch.validate_final_calibration_r8_manifest_reproducibility_unpublished_lock_bundle(
            repo_root=repo_root,
            verify_remote=True,
        )
    except patch.FinalCalibrationR8ManifestReproducibilityPatchError as exc:
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(str(exc)) from exc
    if (
        type(validation) is not dict
        or validation.get("gate") != patch.PATCH_GATE
        or validation.get("status")
        != "unpublished_p_mcalk_lock_bundle_validated"
        or validation.get("p_stage_state") != expected_stage_state
        or validation.get("p_output_count") != 2
        or validation.get("physical_input_count") != 16
        or validation.get("historical_input_count") != 1
        or validation.get("companion_output_count") != 1
        or validation.get("r8_output_count") != 8
        or validation.get("r8_staging_authorized") is not False
        or validation.get("effective_authority") is not False
        or validation.get("scientific_rerun_authorized") is not False
        or validation.get("writes_performed") is not False
    ):
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(
            "E0-MCALK unpublished P semantic validation result drifted"
        )
    return validation


def validate_final_calibration_r8_manifest_reproducibility_invocation(
    args: Any,
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    """Require the one closed, no-DVC E0-MCALK assistant invocation."""
    source = os.environ if env is None else env
    dvc_site_cache = source.get("DVC_SITE_CACHE_DIR")
    if (
        not args.no_push
        or args.yes
        or args.dry_run
        or args.skip_publication_check
        or args.jobs is not None
        or args.dvc_bin is not None
        or args.manifest != DEFAULT_DVC_MANIFEST
        or args.report is not None
        or not args.allow_unmanaged
        or bool(args.target)
        or bool(args.defer_dvc_target)
        or bool(getattr(args, "register_anfis_ablation_model_family", False))
        or args.verify_manifest_inputs
        or args.max_manifest_hash_bytes != DEFAULT_MAX_MANIFEST_HASH_BYTES
        or source.get("DVC_NO_ANALYTICS") != "1"
        or "DVC_BIN" in source
        or (
            dvc_site_cache is not None
            and dvc_site_cache != DEFAULT_DVC_SITE_CACHE_DIR.as_posix()
        )
    ):
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(
            "E0-MCALK precommit requires exact --allow-unmanaged --no-push, "
            "the mandatory publication guard, default paths, analytics-disabled "
            "DVC, and no optional execution target or mode"
        )


def snapshot_final_calibration_r8_outputs(
    *,
    repo_root: Path = Path("."),
) -> tuple[FinalCalibrationR8PhysicalIdentity, ...]:
    """Capture immutable R8 inode and byte identity around assistant actions."""
    patch = _final_calibration_r8_manifest_reproducibility_patch_module()
    records: list[FinalCalibrationR8PhysicalIdentity] = []
    try:
        for expected in patch.R8_OUTPUT_CONTRACT:
            raw_path = expected.get("path")
            if type(raw_path) is not str:
                raise FinalCalibrationR8ManifestReproducibilityAdapterError(
                    "E0-MCALK R8 output contract path drifted"
                )
            path = repo_root / raw_path
            identity = _registration_file_identity(
                path,
                repo_root=repo_root,
                mode=0o644,
            )
            if (
                identity.nlink != 1
                or identity.size != expected.get("bytes")
                or identity.sha256 != expected.get("sha256")
            ):
                raise FinalCalibrationR8ManifestReproducibilityAdapterError(
                    f"E0-MCALK R8 physical identity drifted: {raw_path}"
                )
            record = FinalCalibrationR8PhysicalIdentity(
                path=raw_path,
                device=identity.device,
                inode=identity.inode,
                mode=identity.mode,
                nlink=identity.nlink,
                bytes=identity.size,
                sha256=identity.sha256,
                mtime_ns=identity.mtime_ns,
                ctime_ns=identity.ctime_ns,
            )
            records.append(record)
    except (
        OSError,
        DeferredDvcTargetError,
        FinalCalibrationR8ManifestReproducibilityAdapterError,
    ) as exc:
        if isinstance(
            exc, FinalCalibrationR8ManifestReproducibilityAdapterError
        ):
            raise
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(
            f"E0-MCALK R8 physical snapshot failed: {exc}"
        ) from exc
    if len(records) != 8 or len({record.path for record in records}) != 8:
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(
            "E0-MCALK R8 physical snapshot is not exact8"
        )
    return tuple(records)


def revalidate_final_calibration_r8_manifest_reproducibility_transaction(
    *,
    gate: str,
    staged_status: str,
    expected_snapshot: tuple[FinalCalibrationR8PhysicalIdentity, ...],
    repo_root: Path = Path("."),
) -> None:
    """Close scope, semantic, byte, and inode races around report generation."""
    validate_final_calibration_r8_manifest_reproducibility_staged_scope(
        staged_status,
        gate=gate,
    )
    current_staged_status = _git_output(
        repo_root,
        "diff",
        "--cached",
        "--name-status",
        "--no-renames",
    )
    validate_final_calibration_r8_manifest_reproducibility_staged_scope(
        current_staged_status,
        gate=gate,
    )
    workspace_status = _git_output(
        repo_root, "status", "--short", "--untracked-files=all"
    )
    validate_final_calibration_r8_manifest_reproducibility_workspace_scope(
        workspace_status,
        gate=gate,
    )
    if snapshot_final_calibration_r8_outputs(repo_root=repo_root) != expected_snapshot:
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(
            "E0-MCALK immutable R8 identity changed during precommit"
        )
    patch = _final_calibration_r8_manifest_reproducibility_patch_module()
    try:
        if gate == "P-E0-MCALK":
            _require_final_calibration_r8_unpublished_p_validation(
                patch=patch,
                repo_root=repo_root,
                expected_stage_state="staged",
            )
        elif gate == "R-E0-MCALK":
            authority = patch.require_final_calibration_r8_manifest_reproducibility_patch_authority(
                repo_root=repo_root,
                verify_remote=True,
            )
            if (
                type(authority) is not dict
                or authority.get("gate") != patch.PATCH_GATE
                or authority.get("r8_staging_authorized") is not True
            ):
                raise FinalCalibrationR8ManifestReproducibilityAdapterError(
                    "R-E0-MCALK remote authority changed during precommit"
                )
        validation = patch.validate_final_calibration_r8_manifest_reproducibility_adoption(
            repo_root=repo_root,
            require_staged=gate == "R-E0-MCALK",
        )
    except patch.FinalCalibrationR8ManifestReproducibilityPatchError as exc:
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(str(exc)) from exc
    if (
        type(validation) is not dict
        or validation.get("gate") != patch.PATCH_GATE
        or validation.get("status")
        != "r8_manifest_reproducibility_adoption_validated"
        or validation.get("r8_output_count") != 8
        or validation.get("calibration_output_count") != 6
        or validation.get("e7_output_count") != 2
        or validation.get("r_lifecycle_state")
        != "both_bundles_completed_unpublished"
        or validation.get("staged_scope_verified")
        is not (gate == "R-E0-MCALK")
    ):
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(
            "E0-MCALK transaction validation result drifted"
        )


def validate_final_calibration_r8_manifest_reproducibility_staged_scope(
    staged_status: str,
    *,
    gate: str,
) -> None:
    patch = _final_calibration_r8_manifest_reproducibility_patch_module()
    scopes = {
        "H-E0-MCALK": patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
        "P-E0-MCALK": patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
        "R-E0-MCALK": patch.R8_STAGED_SCOPE,
    }
    expected = scopes.get(gate)
    if expected is None:
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(
            "Unknown E0-MCALK staged scope"
        )
    try:
        validate_anfis_ablation_git_name_status_map(
            staged_status,
            expected=expected,
            context=f"{gate} staged scope",
        )
    except DeferredDvcTargetError as exc:
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(str(exc)) from exc


def validate_final_calibration_r8_manifest_reproducibility_workspace_scope(
    status_output: str,
    *,
    gate: str,
) -> None:
    patch = _final_calibration_r8_manifest_reproducibility_patch_module()
    scopes = {
        "H-E0-MCALK": patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
        "P-E0-MCALK": patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
        "R-E0-MCALK": patch.R8_STAGED_SCOPE,
    }
    stage_scope = scopes.get(gate)
    if stage_scope is None:
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(
            "Unknown E0-MCALK workspace scope"
        )
    expected = _expected_short_scope(stage_scope, staged=True)
    if gate != "R-E0-MCALK":
        expected.update(_expected_short_scope(patch.R8_STAGED_SCOPE, staged=False))
    try:
        validate_anfis_ablation_git_short_status_map(
            status_output,
            expected=expected,
            context=f"{gate} workspace scope",
        )
    except DeferredDvcTargetError as exc:
        raise FinalCalibrationR8ManifestReproducibilityAdapterError(str(exc)) from exc


def final_calibration_r8_coordination_namespace_revalidation_pre_stage_scope(
    status_output: str,
    *,
    repo_root: Path = Path("."),
) -> tuple[str, tuple[str, ...]] | None:
    """Select only exact H/P/R E0-MCALL paths while R8 remains immutable."""
    patch = _final_calibration_r8_coordination_namespace_revalidation_patch_module()

    def short_map(scope: Mapping[str, str]) -> dict[str, str]:
        return {
            path: "??" if status == "A" else " M"
            for path, status in scope.items()
        }

    h_with_r8 = {
        **short_map(patch.FINAL_CALIBRATION_H_STAGED_SCOPE),
        **short_map(patch.R8_STAGED_SCOPE),
    }
    candidates = (
        ("H-E0-MCALL", h_with_r8, patch.FINAL_CALIBRATION_H_STAGED_SCOPE),
        (
            "P-E0-MCALL",
            {
                **short_map(patch.FINAL_CALIBRATION_P_STAGED_SCOPE),
                **short_map(patch.R8_STAGED_SCOPE),
            },
            patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
        ),
        ("R-E0-MCALL", short_map(patch.R8_STAGED_SCOPE), patch.R8_STAGED_SCOPE),
    )
    candidate_paths = {path for _, expected, _ in candidates for path in expected}
    observed: dict[str, str] = {}
    anomaly = False
    for line in status_output.splitlines():
        if (
            len(line) < 4
            or line[2] != " "
            or line[:2] not in {"??", " M"}
            or not line[3:]
        ):
            if any(path in line for path in candidate_paths):
                raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
                    "E0-MCALL pre-stage scope contains a malformed candidate record"
                )
            anomaly = True
            continue
        path = line[3:]
        if path in observed:
            if path in candidate_paths:
                raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
                    "E0-MCALL pre-stage scope contains a duplicate path"
                )
            anomaly = True
            continue
        observed[path] = line[:2]
    if anomaly and set(observed) & candidate_paths:
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            "E0-MCALL candidate pre-stage scope contains an extra malformed record"
        )
    for gate, expected, stage_scope in candidates:
        if observed == expected:
            _require_final_calibration_r8_coordination_namespace_revalidation_stage_base(
                gate,
                patch=patch,
                repo_root=repo_root,
            )
            return gate, tuple(sorted(stage_scope))
    if set(observed) & candidate_paths:
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            "E0-MCALL candidate pre-stage scope is not exact"
        )
    return None


def _require_final_calibration_r8_coordination_namespace_revalidation_stage_base(
    gate: str,
    *,
    patch: Any,
    repo_root: Path,
) -> None:
    head = _git_output(repo_root, "rev-parse", "HEAD").strip()
    if gate == "H-E0-MCALL":
        if head != patch.BASE_H_MCALK_COMMIT:
            raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
                "H-E0-MCALL staging requires exact published H-E0-MCALK HEAD"
            )
        return
    if gate == "P-E0-MCALL":
        parent = _git_output(repo_root, "rev-parse", "HEAD^").strip()
        scope = _git_output(
            repo_root,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "-r",
            "--no-renames",
            "HEAD",
        )
        if parent != patch.BASE_H_MCALK_COMMIT:
            raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
                "P-E0-MCALL staging requires a direct H child of H-E0-MCALK"
            )
        try:
            validate_anfis_ablation_git_name_status_map(
                scope,
                expected=patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
                context="published H-E0-MCALL scope",
            )
        except DeferredDvcTargetError as exc:
            raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
                str(exc)
            ) from exc
        _require_final_calibration_r8_coordination_namespace_revalidation_unpublished_p_validation(
            patch=patch,
            repo_root=repo_root,
            expected_stage_state="untracked",
        )
        return
    if gate == "R-E0-MCALL":
        try:
            authority = patch.require_final_calibration_r8_coordination_namespace_revalidation_patch_authority(
                repo_root=repo_root,
                verify_remote=True,
            )
        except patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError as exc:
            raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
                str(exc)
            ) from exc
        _require_final_calibration_r8_coordination_namespace_revalidation_effective_result(
            authority,
            patch=patch,
            context="staging",
        )
        return
    raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
        "Unknown E0-MCALL staging gate"
    )


def _require_final_calibration_r8_coordination_namespace_revalidation_effective_result(
    authority: Any,
    *,
    patch: Any,
    context: str,
) -> None:
    if (
        type(authority) is not dict
        or authority.get("gate") != patch.PATCH_GATE
        or authority.get("status") != "effective"
        or authority.get("coordination_namespace_revalidation")
        != patch.COORDINATION_NAMESPACE_CONTRACT
        or authority.get("r_output_present_count") != 8
        or authority.get("r_lifecycle_state")
        != "both_bundles_completed_unpublished"
        or authority.get("effective_authority") is not True
        or authority.get("r8_staging_authorized") is not True
        or authority.get("writes_performed") is not False
    ):
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            f"R-E0-MCALL {context} requires exact effective P-E0-MCALL authority"
        )


def _require_final_calibration_r8_coordination_namespace_revalidation_unpublished_p_validation(
    *,
    patch: Any,
    repo_root: Path,
    expected_stage_state: str,
) -> dict[str, Any]:
    try:
        validation = patch.validate_final_calibration_r8_coordination_namespace_revalidation_unpublished_lock_bundle(
            repo_root=repo_root,
            verify_remote=True,
        )
    except patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError as exc:
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            str(exc)
        ) from exc
    if (
        type(validation) is not dict
        or validation.get("gate") != patch.PATCH_GATE
        or validation.get("status")
        != "unpublished_p_mcall_lock_bundle_validated"
        or validation.get("p_stage_state") != expected_stage_state
        or validation.get("p_output_count") != 2
        or validation.get("physical_input_count") != 16
        or validation.get("historical_input_count") != 6
        or validation.get("companion_output_count") != 1
        or validation.get("coordination_forbidden_count") != 46
        or validation.get("coordination_present_count") != 0
        or validation.get("r8_output_count") != 8
        or type(validation.get("r8_outputs_sha256")) is not str
        or len(validation["r8_outputs_sha256"]) != 64
        or validation.get("r8_staging_authorized") is not False
        or validation.get("effective_authority") is not False
        or validation.get("scientific_rerun_authorized") is not False
        or validation.get("writes_performed") is not False
    ):
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            "E0-MCALL unpublished P semantic validation result drifted"
        )
    return validation


def validate_final_calibration_r8_coordination_namespace_revalidation_invocation(
    args: Any,
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    """Require the one closed, no-DVC E0-MCALL assistant invocation."""
    source = os.environ if env is None else env
    dvc_site_cache = source.get("DVC_SITE_CACHE_DIR")
    if (
        not args.no_push
        or args.yes
        or args.dry_run
        or args.skip_publication_check
        or args.jobs is not None
        or args.dvc_bin is not None
        or args.manifest != DEFAULT_DVC_MANIFEST
        or args.report is not None
        or not args.allow_unmanaged
        or bool(args.target)
        or bool(args.defer_dvc_target)
        or bool(getattr(args, "register_anfis_ablation_model_family", False))
        or args.verify_manifest_inputs
        or args.max_manifest_hash_bytes != DEFAULT_MAX_MANIFEST_HASH_BYTES
        or source.get("DVC_NO_ANALYTICS") != "1"
        or "DVC_BIN" in source
        or (
            dvc_site_cache is not None
            and dvc_site_cache != DEFAULT_DVC_SITE_CACHE_DIR.as_posix()
        )
    ):
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            "E0-MCALL precommit requires exact --allow-unmanaged --no-push, "
            "the mandatory publication guard, default paths, analytics-disabled "
            "DVC, and no optional execution target or mode"
        )


def snapshot_final_calibration_r8_coordination_namespace_outputs(
    *,
    repo_root: Path = Path("."),
) -> tuple[FinalCalibrationR8PhysicalIdentity, ...]:
    """Capture immutable R8 inode and byte identity around MCALL actions."""
    patch = _final_calibration_r8_coordination_namespace_revalidation_patch_module()
    records: list[FinalCalibrationR8PhysicalIdentity] = []
    try:
        for expected in patch.R8_OUTPUT_CONTRACT:
            raw_path = expected.get("path")
            if type(raw_path) is not str:
                raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
                    "E0-MCALL R8 output contract path drifted"
                )
            identity = _registration_file_identity(
                repo_root / raw_path,
                repo_root=repo_root,
                mode=0o644,
            )
            if (
                identity.nlink != 1
                or identity.size != expected.get("bytes")
                or identity.sha256 != expected.get("sha256")
            ):
                raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
                    f"E0-MCALL R8 physical identity drifted: {raw_path}"
                )
            records.append(
                FinalCalibrationR8PhysicalIdentity(
                    path=raw_path,
                    device=identity.device,
                    inode=identity.inode,
                    mode=identity.mode,
                    nlink=identity.nlink,
                    bytes=identity.size,
                    sha256=identity.sha256,
                    mtime_ns=identity.mtime_ns,
                    ctime_ns=identity.ctime_ns,
                )
            )
    except (
        OSError,
        DeferredDvcTargetError,
        FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError,
    ) as exc:
        if isinstance(
            exc, FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError
        ):
            raise
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            f"E0-MCALL R8 physical snapshot failed: {exc}"
        ) from exc
    if len(records) != 8 or len({record.path for record in records}) != 8:
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            "E0-MCALL R8 physical snapshot is not exact8"
        )
    return tuple(records)


def revalidate_final_calibration_r8_coordination_namespace_revalidation_transaction(
    *,
    gate: str,
    staged_status: str,
    expected_snapshot: tuple[FinalCalibrationR8PhysicalIdentity, ...],
    repo_root: Path = Path("."),
) -> None:
    """Close MCALL scope, semantic, byte, inode, and remote-ref races."""
    validate_final_calibration_r8_coordination_namespace_revalidation_staged_scope(
        staged_status,
        gate=gate,
    )
    current_staged_status = _git_output(
        repo_root,
        "diff",
        "--cached",
        "--name-status",
        "--no-renames",
    )
    validate_final_calibration_r8_coordination_namespace_revalidation_staged_scope(
        current_staged_status,
        gate=gate,
    )
    workspace_status = _git_output(
        repo_root, "status", "--short", "--untracked-files=all"
    )
    validate_final_calibration_r8_coordination_namespace_revalidation_workspace_scope(
        workspace_status,
        gate=gate,
    )
    if (
        snapshot_final_calibration_r8_coordination_namespace_outputs(
            repo_root=repo_root
        )
        != expected_snapshot
    ):
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            "E0-MCALL immutable R8 identity changed during precommit"
        )
    patch = _final_calibration_r8_coordination_namespace_revalidation_patch_module()
    try:
        if gate == "P-E0-MCALL":
            _require_final_calibration_r8_coordination_namespace_revalidation_unpublished_p_validation(
                patch=patch,
                repo_root=repo_root,
                expected_stage_state="staged",
            )
        elif gate == "R-E0-MCALL":
            authority = patch.require_final_calibration_r8_coordination_namespace_revalidation_patch_authority(
                repo_root=repo_root,
                verify_remote=True,
            )
            _require_final_calibration_r8_coordination_namespace_revalidation_effective_result(
                authority,
                patch=patch,
                context="remote revalidation",
            )
        validation = patch.validate_final_calibration_r8_coordination_namespace_revalidation_adoption(
            repo_root=repo_root,
            require_staged=gate == "R-E0-MCALL",
        )
    except patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError as exc:
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            str(exc)
        ) from exc
    if (
        type(validation) is not dict
        or validation.get("gate") != patch.PATCH_GATE
        or validation.get("status")
        != "r8_coordination_namespace_revalidation_adoption_validated"
        or validation.get("r8_output_count") != 8
        or validation.get("calibration_output_count") != 6
        or validation.get("e7_output_count") != 2
        or validation.get("r_lifecycle_state")
        != "both_bundles_completed_unpublished"
        or validation.get("r8_outputs") != list(patch.R8_OUTPUT_CONTRACT)
        or validation.get("coordination_forbidden_count") != 46
        or validation.get("coordination_present_count") != 0
        or validation.get("effective_p_mcall_verified")
        is not (gate == "R-E0-MCALL")
        or validation.get("staged_scope_verified")
        is not (gate == "R-E0-MCALL")
    ):
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            "E0-MCALL transaction validation result drifted"
        )


def validate_final_calibration_r8_coordination_namespace_revalidation_staged_scope(
    staged_status: str,
    *,
    gate: str,
) -> None:
    patch = _final_calibration_r8_coordination_namespace_revalidation_patch_module()
    scopes = {
        "H-E0-MCALL": patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
        "P-E0-MCALL": patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
        "R-E0-MCALL": patch.R8_STAGED_SCOPE,
    }
    expected = scopes.get(gate)
    if expected is None:
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            "Unknown E0-MCALL staged scope"
        )
    try:
        validate_anfis_ablation_git_name_status_map(
            staged_status,
            expected=expected,
            context=f"{gate} staged scope",
        )
    except DeferredDvcTargetError as exc:
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            str(exc)
        ) from exc


def validate_final_calibration_r8_coordination_namespace_revalidation_workspace_scope(
    status_output: str,
    *,
    gate: str,
) -> None:
    patch = _final_calibration_r8_coordination_namespace_revalidation_patch_module()
    scopes = {
        "H-E0-MCALL": patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
        "P-E0-MCALL": patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
        "R-E0-MCALL": patch.R8_STAGED_SCOPE,
    }
    stage_scope = scopes.get(gate)
    if stage_scope is None:
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            "Unknown E0-MCALL workspace scope"
        )
    expected = _expected_short_scope(stage_scope, staged=True)
    if gate != "R-E0-MCALL":
        expected.update(_expected_short_scope(patch.R8_STAGED_SCOPE, staged=False))
    try:
        validate_anfis_ablation_git_short_status_map(
            status_output,
            expected=expected,
            context=f"{gate} workspace scope",
        )
    except DeferredDvcTargetError as exc:
        raise FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError(
            str(exc)
        ) from exc


def final_calibration_r8_post_publication_authority_pre_stage_scope(
    status_output: str,
    *,
    repo_root: Path = Path("."),
) -> tuple[str, tuple[str, ...]] | None:
    """Select only exact H/P E0-MCALM paths with published R8 left untouched."""
    patch = _final_calibration_r8_post_publication_authority_patch_module()

    def short_map(scope: Mapping[str, str]) -> dict[str, str]:
        return {
            path: "??" if status == "A" else " M"
            for path, status in scope.items()
        }

    candidates = (
        (
            "H-E0-MCALM",
            short_map(patch.FINAL_CALIBRATION_H_STAGED_SCOPE),
            patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
        ),
        (
            "P-E0-MCALM",
            short_map(patch.FINAL_CALIBRATION_P_STAGED_SCOPE),
            patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
        ),
    )
    candidate_paths = {path for _, expected, _ in candidates for path in expected}
    observed: dict[str, str] = {}
    anomaly = False
    for line in status_output.splitlines():
        if (
            len(line) < 4
            or line[2] != " "
            or line[:2] not in {"??", " M"}
            or not line[3:]
        ):
            if any(path in line for path in candidate_paths):
                raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
                    "E0-MCALM pre-stage scope contains a malformed candidate record"
                )
            anomaly = True
            continue
        path = line[3:]
        if path in observed:
            if path in candidate_paths:
                raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
                    "E0-MCALM pre-stage scope contains a duplicate path"
                )
            anomaly = True
            continue
        observed[path] = line[:2]
    if anomaly and set(observed) & candidate_paths:
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            "E0-MCALM candidate pre-stage scope contains an extra malformed record"
        )
    for gate, expected, stage_scope in candidates:
        if observed == expected:
            _require_final_calibration_r8_post_publication_authority_stage_base(
                gate,
                patch=patch,
                repo_root=repo_root,
            )
            return gate, tuple(sorted(stage_scope))
    if set(observed) & candidate_paths:
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            "E0-MCALM candidate pre-stage scope is not exact"
        )
    return None


def _require_final_calibration_r8_post_publication_authority_stage_base(
    gate: str,
    *,
    patch: Any,
    repo_root: Path,
) -> None:
    head = _git_output(repo_root, "rev-parse", "HEAD").strip()
    if gate == "H-E0-MCALM":
        if head != patch.BASE_R_MCALL_COMMIT:
            raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
                "H-E0-MCALM staging requires exact published R-E0-MCALL HEAD"
            )
        _require_final_calibration_r8_post_publication_authority_readiness(
            patch=patch,
            repo_root=repo_root,
            require_effective=False,
        )
        return
    if gate == "P-E0-MCALM":
        parent = _git_output(repo_root, "rev-parse", "HEAD^").strip()
        scope = _git_output(
            repo_root,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "-r",
            "--no-renames",
            "HEAD",
        )
        if parent != patch.BASE_R_MCALL_COMMIT:
            raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
                "P-E0-MCALM staging requires a direct H child of R-E0-MCALL"
            )
        try:
            validate_anfis_ablation_git_name_status_map(
                scope,
                expected=patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
                context="published H-E0-MCALM scope",
            )
        except DeferredDvcTargetError as exc:
            raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
                str(exc)
            ) from exc
        _require_final_calibration_r8_post_publication_authority_unpublished_p_validation(
            patch=patch,
            repo_root=repo_root,
            expected_stage_state="untracked",
        )
        return
    raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
        "Unknown E0-MCALM staging gate"
    )


def _require_final_calibration_r8_post_publication_authority_readiness(
    *,
    patch: Any,
    repo_root: Path,
    require_effective: bool,
) -> dict[str, Any]:
    try:
        readiness = patch.validate_final_calibration_r8_post_publication_authority_model_lock_readiness(
            repo_root=repo_root,
            verify_remote=True,
            require_effective=require_effective,
        )
    except patch.FinalCalibrationR8PostPublicationAuthorityPatchError as exc:
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(str(exc)) from exc
    if (
        type(readiness) is not dict
        or readiness.get("gate") != patch.PATCH_GATE
        or readiness.get("status") != "formal_e0_m_static_readiness_validated"
        or readiness.get("effective_p_mcalm_verified") is not require_effective
        or readiness.get("terminal_r_commit") != patch.BASE_R_MCALL_COMMIT
        or readiness.get("r8_published") is not True
        or readiness.get("r8_output_count") != 8
        or type(readiness.get("r8_outputs_sha256")) is not str
        or len(readiness["r8_outputs_sha256"]) != 64
        or readiness.get("e0_m_output_count") != 0
        or readiness.get("outcome_access_log_state") != "absent"
        or readiness.get("outcome_access_log_required_e0_m_state")
        != "present_empty"
        or readiness.get("formal_e0_m_entrypoint_present") is not False
        or readiness.get("e0_m_authorized") is not False
        or readiness.get("e0_u_authorized") is not False
        or readiness.get("outcome_access_authorized") is not False
        or readiness.get("scientific_rerun_authorized") is not False
        or readiness.get("writes_performed") is not False
    ):
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            "E0-MCALM static readiness result drifted"
        )
    return readiness


def _require_final_calibration_r8_post_publication_authority_unpublished_p_validation(
    *,
    patch: Any,
    repo_root: Path,
    expected_stage_state: str,
) -> dict[str, Any]:
    try:
        validation = patch.validate_final_calibration_r8_post_publication_authority_unpublished_lock_bundle(
            repo_root=repo_root,
            verify_remote=True,
        )
    except patch.FinalCalibrationR8PostPublicationAuthorityPatchError as exc:
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(str(exc)) from exc
    if (
        type(validation) is not dict
        or validation.get("gate") != patch.PATCH_GATE
        or validation.get("status") != "unpublished_p_mcalm_lock_bundle_validated"
        or validation.get("p_stage_state") != expected_stage_state
        or validation.get("p_output_count") != 2
        or validation.get("physical_input_count") != 16
        or validation.get("historical_input_count") != 6
        or validation.get("companion_output_count") != 1
        or validation.get("coordination_forbidden_count") != 49
        or validation.get("coordination_present_count") != 0
        or validation.get("r8_output_count") != 8
        or type(validation.get("r8_outputs_sha256")) is not str
        or len(validation["r8_outputs_sha256"]) != 64
        or validation.get("r8_published") is not True
        or validation.get("r8_staging_authorized") is not False
        or validation.get("effective_authority") is not False
        or validation.get("e0_m_authorized") is not False
        or validation.get("scientific_rerun_authorized") is not False
        or validation.get("dvc_commands_authorized") is not False
        or validation.get("dvc_push_authorized") is not False
        or validation.get("git_commit_authorized") is not False
        or validation.get("git_push_authorized") is not False
        or validation.get("writes_performed") is not False
    ):
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            "E0-MCALM unpublished P semantic validation result drifted"
        )
    return validation


def validate_final_calibration_r8_post_publication_authority_invocation(
    args: Any,
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    """Require the one closed, no-DVC E0-MCALM assistant invocation."""
    source = os.environ if env is None else env
    dvc_site_cache = source.get("DVC_SITE_CACHE_DIR")
    if (
        not args.no_push
        or args.yes
        or args.dry_run
        or args.skip_publication_check
        or args.jobs is not None
        or args.dvc_bin is not None
        or args.manifest != DEFAULT_DVC_MANIFEST
        or args.report is not None
        or not args.allow_unmanaged
        or bool(args.target)
        or bool(args.defer_dvc_target)
        or bool(getattr(args, "register_anfis_ablation_model_family", False))
        or args.verify_manifest_inputs
        or args.max_manifest_hash_bytes != DEFAULT_MAX_MANIFEST_HASH_BYTES
        or source.get("DVC_NO_ANALYTICS") != "1"
        or "DVC_BIN" in source
        or (
            dvc_site_cache is not None
            and dvc_site_cache != DEFAULT_DVC_SITE_CACHE_DIR.as_posix()
        )
    ):
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            "E0-MCALM precommit requires exact --allow-unmanaged --no-push, "
            "the mandatory publication guard, default paths, analytics-disabled "
            "DVC, and no optional execution target or mode"
        )


def snapshot_final_calibration_r8_post_publication_outputs(
    *,
    repo_root: Path = Path("."),
) -> tuple[FinalCalibrationR8PhysicalIdentity, ...]:
    """Capture published R8 inode and byte identity around MCALM actions."""
    patch = _final_calibration_r8_post_publication_authority_patch_module()
    records: list[FinalCalibrationR8PhysicalIdentity] = []
    try:
        for expected in patch.R8_OUTPUT_CONTRACT:
            raw_path = expected.get("path")
            if type(raw_path) is not str:
                raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
                    "E0-MCALM R8 output contract path drifted"
                )
            identity = _registration_file_identity(
                repo_root / raw_path,
                repo_root=repo_root,
                mode=0o644,
            )
            if (
                identity.nlink != 1
                or identity.size != expected.get("bytes")
                or identity.sha256 != expected.get("sha256")
            ):
                raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
                    f"E0-MCALM published R8 identity drifted: {raw_path}"
                )
            records.append(
                FinalCalibrationR8PhysicalIdentity(
                    path=raw_path,
                    device=identity.device,
                    inode=identity.inode,
                    mode=identity.mode,
                    nlink=identity.nlink,
                    bytes=identity.size,
                    sha256=identity.sha256,
                    mtime_ns=identity.mtime_ns,
                    ctime_ns=identity.ctime_ns,
                )
            )
    except (
        OSError,
        DeferredDvcTargetError,
        FinalCalibrationR8PostPublicationAuthorityAdapterError,
    ) as exc:
        if isinstance(exc, FinalCalibrationR8PostPublicationAuthorityAdapterError):
            raise
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            f"E0-MCALM R8 physical snapshot failed: {exc}"
        ) from exc
    if len(records) != 8 or len({record.path for record in records}) != 8:
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            "E0-MCALM R8 physical snapshot is not exact8"
        )
    return tuple(records)


def validate_final_calibration_r8_post_publication_authority_staged_scope(
    staged_status: str,
    *,
    gate: str,
) -> None:
    patch = _final_calibration_r8_post_publication_authority_patch_module()
    scopes = {
        "H-E0-MCALM": patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
        "P-E0-MCALM": patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
    }
    expected = scopes.get(gate)
    if expected is None:
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            "Unknown E0-MCALM staged scope"
        )
    try:
        validate_anfis_ablation_git_name_status_map(
            staged_status,
            expected=expected,
            context=f"{gate} staged scope",
        )
    except DeferredDvcTargetError as exc:
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(str(exc)) from exc


def validate_final_calibration_r8_post_publication_authority_workspace_scope(
    status_output: str,
    *,
    gate: str,
) -> None:
    patch = _final_calibration_r8_post_publication_authority_patch_module()
    scopes = {
        "H-E0-MCALM": patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
        "P-E0-MCALM": patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
    }
    stage_scope = scopes.get(gate)
    if stage_scope is None:
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            "Unknown E0-MCALM workspace scope"
        )
    try:
        validate_anfis_ablation_git_short_status_map(
            status_output,
            expected=_expected_short_scope(stage_scope, staged=True),
            context=f"{gate} workspace scope",
        )
    except DeferredDvcTargetError as exc:
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(str(exc)) from exc


def revalidate_final_calibration_r8_post_publication_authority_transaction(
    *,
    gate: str,
    staged_status: str,
    expected_snapshot: tuple[FinalCalibrationR8PhysicalIdentity, ...],
    repo_root: Path = Path("."),
) -> None:
    """Close MCALM scope, semantic, R8 identity, namespace, and ref races."""
    validate_final_calibration_r8_post_publication_authority_staged_scope(
        staged_status,
        gate=gate,
    )
    current_staged_status = _git_output(
        repo_root,
        "diff",
        "--cached",
        "--name-status",
        "--no-renames",
    )
    validate_final_calibration_r8_post_publication_authority_staged_scope(
        current_staged_status,
        gate=gate,
    )
    workspace_status = _git_output(
        repo_root, "status", "--short", "--untracked-files=all"
    )
    validate_final_calibration_r8_post_publication_authority_workspace_scope(
        workspace_status,
        gate=gate,
    )
    if (
        snapshot_final_calibration_r8_post_publication_outputs(repo_root=repo_root)
        != expected_snapshot
    ):
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            "E0-MCALM published R8 identity changed during precommit"
        )
    patch = _final_calibration_r8_post_publication_authority_patch_module()
    if gate == "H-E0-MCALM":
        _require_final_calibration_r8_post_publication_authority_readiness(
            patch=patch,
            repo_root=repo_root,
            require_effective=False,
        )
    elif gate == "P-E0-MCALM":
        _require_final_calibration_r8_post_publication_authority_unpublished_p_validation(
            patch=patch,
            repo_root=repo_root,
            expected_stage_state="staged",
        )
    else:
        raise FinalCalibrationR8PostPublicationAuthorityAdapterError(
            "Unknown E0-MCALM transaction gate"
        )


def _closure_locked_evaluation_input_bundle_scopes(
    patch: Any,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Reject any core-side drift before selecting an E0-MIB transaction."""
    contracts = (
        (
            getattr(patch, "LOCKED_EVALUATION_INPUT_H_STAGED_SCOPE", None),
            _LOCKED_EVALUATION_INPUT_H_STAGED_SCOPE,
        ),
        (
            getattr(patch, "LOCKED_EVALUATION_INPUT_P_STAGED_SCOPE", None),
            _LOCKED_EVALUATION_INPUT_P_STAGED_SCOPE,
        ),
        (
            getattr(patch, "LOCKED_EVALUATION_INPUT_R_STAGED_SCOPE", None),
            _LOCKED_EVALUATION_INPUT_R_STAGED_SCOPE,
        ),
    )
    if (
        getattr(patch, "PATCH_GATE", None) != "E0-MIB"
        or getattr(patch, "BASE_P_MCALM_COMMIT", None)
        != "81c1fc485902d484264fccc53cf88888c359930d"
        or any(type(observed) is not dict or observed != expected for observed, expected in contracts)
        or type(getattr(patch, "PATCH_COMPONENT_GIT_MODES", None)) is not dict
        or patch.PATCH_COMPONENT_GIT_MODES != _LOCKED_EVALUATION_INPUT_H_GIT_MODES
        or set(_LOCKED_EVALUATION_INPUT_H_STAGED_SCOPE)
        & set(_LOCKED_EVALUATION_INPUT_P_STAGED_SCOPE)
        or set(_LOCKED_EVALUATION_INPUT_H_STAGED_SCOPE)
        & set(_LOCKED_EVALUATION_INPUT_R_STAGED_SCOPE)
        or set(_LOCKED_EVALUATION_INPUT_P_STAGED_SCOPE)
        & set(_LOCKED_EVALUATION_INPUT_R_STAGED_SCOPE)
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB H6/P2/R6 scope contract drifted"
        )
    return (
        dict(_LOCKED_EVALUATION_INPUT_H_STAGED_SCOPE),
        dict(_LOCKED_EVALUATION_INPUT_P_STAGED_SCOPE),
        dict(_LOCKED_EVALUATION_INPUT_R_STAGED_SCOPE),
    )


def closure_locked_evaluation_input_bundle_pre_stage_scope(
    status_output: str,
    *,
    repo_root: Path = Path("."),
) -> tuple[str, tuple[str, ...]] | None:
    """Select only the exact H/P/R E0-MIB transaction before generic staging."""
    patch = _closure_locked_evaluation_input_bundle_module()

    def short_map(scope: Mapping[str, str]) -> dict[str, str]:
        return {
            path: "??" if status == "A" else " M"
            for path, status in scope.items()
        }

    h_scope, p_scope, r_scope = _closure_locked_evaluation_input_bundle_scopes(
        patch
    )
    r_pre_dvc = {
        path: status
        for path, status in r_scope.items()
        if not path.endswith(".dvc")
    }
    candidates = (
        ("H-E0-MIB", short_map(h_scope), h_scope),
        ("P-E0-MIB", short_map(p_scope), p_scope),
        ("R-E0-MI", short_map(r_pre_dvc), r_scope),
    )
    candidate_paths = {
        path
        for scope in (h_scope, p_scope, r_scope)
        for path in scope
    }
    observed: dict[str, str] = {}
    anomaly = False
    for line in status_output.splitlines():
        if (
            len(line) < 4
            or line[2] != " "
            or line[:2] not in {"??", " M"}
            or not line[3:]
        ):
            if any(path in line for path in candidate_paths):
                raise ClosureLockedEvaluationInputBundleAdapterError(
                    "E0-MIB pre-stage scope contains a malformed candidate record"
                )
            anomaly = True
            continue
        path = line[3:]
        if path in observed:
            if path in candidate_paths:
                raise ClosureLockedEvaluationInputBundleAdapterError(
                    "E0-MIB pre-stage scope contains a duplicate path"
                )
            anomaly = True
            continue
        observed[path] = line[:2]
    if anomaly and set(observed) & candidate_paths:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB candidate pre-stage scope contains an extra malformed record"
        )
    for gate, expected, stage_scope in candidates:
        if observed == expected:
            _require_closure_locked_evaluation_input_bundle_stage_base(
                gate,
                patch=patch,
                repo_root=repo_root,
            )
            return gate, tuple(sorted(stage_scope))
    if set(observed) & candidate_paths:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB candidate pre-stage scope is not exact"
        )
    return None


def _require_closure_locked_evaluation_input_bundle_stage_base(
    gate: str,
    *,
    patch: Any,
    repo_root: Path,
) -> None:
    """Bind each E0-MIB stage to its exact published predecessor."""
    expected_h_scope, _, _ = _closure_locked_evaluation_input_bundle_scopes(patch)
    head = _git_output(repo_root, "rev-parse", "HEAD").strip()
    if gate == "H-E0-MIB":
        if head != patch.BASE_P_MCALM_COMMIT:
            raise ClosureLockedEvaluationInputBundleAdapterError(
                "H-E0-MIB staging requires exact published P-E0-MCALM HEAD"
            )
        _require_closure_locked_evaluation_input_prelock(
            patch=patch,
            repo_root=repo_root,
        )
        return
    if gate == "P-E0-MIB":
        parent = _git_output(repo_root, "rev-parse", "HEAD^").strip()
        published_h_scope = _git_output(
            repo_root,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "-r",
            "--no-renames",
            "HEAD",
        )
        if parent != patch.BASE_P_MCALM_COMMIT:
            raise ClosureLockedEvaluationInputBundleAdapterError(
                "P-E0-MIB staging requires a direct H child of P-E0-MCALM"
            )
        try:
            validate_anfis_ablation_git_name_status_map(
                published_h_scope,
                expected=expected_h_scope,
                context="published H-E0-MIB scope",
            )
        except DeferredDvcTargetError as exc:
            raise ClosureLockedEvaluationInputBundleAdapterError(str(exc)) from exc
        _require_closure_locked_evaluation_input_unpublished_validation(
            patch=patch,
            repo_root=repo_root,
            expected_stage_state="untracked",
        )
        return
    if gate == "R-E0-MI":
        _require_closure_locked_evaluation_input_authority(
            patch=patch,
            repo_root=repo_root,
            expected_stage_state="physical_and_light_untracked",
        )
        _require_closure_locked_evaluation_input_r_validation(
            patch=patch,
            repo_root=repo_root,
            require_staged=False,
        )
        return
    raise ClosureLockedEvaluationInputBundleAdapterError(
        "Unknown E0-MIB staging gate"
    )


def _require_closure_locked_evaluation_input_prelock(
    *,
    patch: Any,
    repo_root: Path,
) -> dict[str, Any]:
    """Require two equal remote-aware H prelock and physical snapshots."""
    try:
        physical_before = patch._physical_snapshot(repo_root)
        before = patch.collect_closure_locked_evaluation_input_bundle_prelock_state(
            repo_root=repo_root,
            verify_remote=True,
        )
        after = patch.collect_closure_locked_evaluation_input_bundle_prelock_state(
            repo_root=repo_root,
            verify_remote=True,
        )
        physical_after = patch._physical_snapshot(repo_root)
    except patch.ClosureLockedEvaluationInputBundleError as exc:
        raise ClosureLockedEvaluationInputBundleAdapterError(str(exc)) from exc
    if (
        before != after
        or physical_before != physical_after
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB H prelock topology or physical snapshot drifted"
        )
    _validate_closure_locked_evaluation_input_prelock_result(
        before,
        patch=patch,
    )
    return before


def _validate_closure_locked_evaluation_input_prelock_result(
    value: Any,
    *,
    patch: Any,
) -> None:
    """Require the frozen science-free H prelock result, never an equal empty dict."""
    expected_keys = {
        "repository",
        "h_patch",
        "base_authority",
        "input_contract",
        "r_contract",
        "prelock",
        "historical_inputs",
        "historical_inputs_sha256",
        "coordination_namespace",
        "schema_preflight",
    }
    if type(value) is not dict or set(value) != expected_keys:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB H prelock result dialect drifted"
        )
    repository = value.get("repository")
    h_patch = value.get("h_patch")
    base = value.get("base_authority")
    inputs = value.get("input_contract")
    r_contract = value.get("r_contract")
    prelock = value.get("prelock")
    historical = value.get("historical_inputs")
    namespace = value.get("coordination_namespace")
    schema = value.get("schema_preflight")
    if (
        not isinstance(repository, Mapping)
        or repository.get("base_p_mcalm_commit") != patch.BASE_P_MCALM_COMMIT
        or not isinstance(h_patch, Mapping)
        or h_patch.get("gate") != "H-E0-MIB"
        or h_patch.get("component_count") != 6
        or h_patch.get("added_count") != 5
        or h_patch.get("modified_count") != 1
        or not isinstance(base, Mapping)
        or base.get("gate") != "E0-MCALM"
        or base.get("status") != "published_p_mcalm_authority_validated"
        or not isinstance(base.get("p_components"), list)
        or len(base["p_components"]) != 2
        or base.get("scientific_inputs_rehashed") is not False
        or base.get("outcome_paths_opened") is not False
        or not isinstance(inputs, Mapping)
        or inputs.get("panel_projection_count") != 41
        or inputs.get("physical_feature_count") != 38
        or inputs.get("derived_calendar_count") != 4
        or inputs.get("locked_evaluation_origin_start") != "2022-01"
        or inputs.get("target_months_materialized") is not False
        or inputs.get("target_availability_inspected") is not False
        or inputs.get("target_namespace_opened") is not False
        or inputs.get("outcome_access_log_opened") is not False
        or not isinstance(inputs.get("source_records"), list)
        or len(inputs["source_records"]) != 4
        or not isinstance(r_contract, Mapping)
        or r_contract.get("gate") != "R-E0-MI"
        or r_contract.get("physical_output_count") != 4
        or r_contract.get("pointer_output_count") != 4
        or r_contract.get("light_output_count") != 2
        or r_contract.get("tracked_output_count") != 6
        or r_contract.get("manifest_written_last") is not True
        or not isinstance(prelock, Mapping)
        or prelock.get("p_output_present_count") != 0
        or prelock.get("r_output_present_count") != 0
        or prelock.get("coordination_present_count") != 0
        or prelock.get("component_count") != 6
        or any(
            prelock.get(key) is not False
            for key in (
                "scientific_execution_run",
                "panel_opened",
                "assignment_opened",
                "target_namespace_opened",
                "outcome_paths_opened",
                "dvc_commands_run",
            )
        )
        or not isinstance(historical, list)
        or len(historical) != 6
        or not isinstance(value.get("historical_inputs_sha256"), str)
        or len(value["historical_inputs_sha256"]) != 64
        or not isinstance(namespace, Mapping)
        or namespace.get("current_lock_present_count") != 0
        or namespace.get("coordination_present_count") != 0
        or namespace.get("r_state") != "absent"
        or namespace.get("formal_e0_m_output_present_count") != 0
        or namespace.get("outcome_access_log_absent") is not True
        or not isinstance(schema, Mapping)
        or schema.get("gate") != patch.PATCH_GATE
        or schema.get("status") != "schema_ready"
        or schema.get("schema_count") != 1
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB H prelock contract drifted"
        )


def _require_closure_locked_evaluation_input_unpublished_validation(
    *,
    patch: Any,
    repo_root: Path,
    expected_stage_state: str,
) -> dict[str, Any]:
    try:
        validation = patch.validate_locked_evaluation_input_bundle_unpublished_lock_bundle(
            repo_root=repo_root,
            verify_remote=True,
        )
    except patch.ClosureLockedEvaluationInputBundleError as exc:
        raise ClosureLockedEvaluationInputBundleAdapterError(str(exc)) from exc
    if (
        type(validation) is not dict
        or validation.get("gate") != patch.PATCH_GATE
        or validation.get("status") != "locked_unpublished"
        or validation.get("p_stage_state") != expected_stage_state
        or validation.get("p_output_count") != 2
        or validation.get("physical_input_count") != 16
        or validation.get("historical_input_count") != 6
        or validation.get("companion_output_count") != 1
        or validation.get("coordination_present_count") != 0
        or validation.get("r_state") != "absent"
        or validation.get("effective_authority") is not False
        or validation.get("input_bundle_execution_authorized") is not False
        or validation.get("evaluation_authorized") is not False
        or validation.get("e0_m_authorized") is not False
        or validation.get("e0_u_authorized") is not False
        or validation.get("dvc_commands_authorized") is not False
        or validation.get("git_commit_authorized") is not False
        or validation.get("git_push_authorized") is not False
        or validation.get("writes_performed") is not False
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB unpublished P semantic validation result drifted"
        )
    return validation


def _require_closure_locked_evaluation_input_authority(
    *,
    patch: Any,
    repo_root: Path,
    expected_stage_state: str,
) -> dict[str, Any]:
    expected_r_state = {
        "physical_and_light_untracked": "physical_and_light",
        "exact6_staged": "complete",
    }.get(expected_stage_state)
    expected_tracked_count = 0 if expected_stage_state == "physical_and_light_untracked" else 6
    if expected_r_state is None:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB effective authority stage policy drifted"
        )
    try:
        authority = patch.require_locked_evaluation_input_bundle_authority(
            repo_root=repo_root,
            verify_remote=True,
        )
    except patch.ClosureLockedEvaluationInputBundleError as exc:
        raise ClosureLockedEvaluationInputBundleAdapterError(str(exc)) from exc
    if (
        type(authority) is not dict
        or authority.get("gate") != patch.PATCH_GATE
        or authority.get("status") != "effective"
        or authority.get("r_stage_state") != expected_stage_state
        or authority.get("r_state") != expected_r_state
        or authority.get("r_physical_output_count") != 4
        or authority.get("r_tracked_output_count") != expected_tracked_count
        or authority.get("input_bundle_execution_authorized") is not False
        or authority.get("input_bundle_run_consumed") is not True
        or authority.get("effective_authority") is not True
        or authority.get("evaluation_authorized") is not False
        or authority.get("e0_m_authorized") is not False
        or authority.get("e0_u_authorized") is not False
        or authority.get("outcome_access_authorized") is not False
        or authority.get("dvc_commands_authorized") is not False
        or authority.get("dvc_push_authorized") is not False
        or authority.get("git_commit_authorized") is not False
        or authority.get("git_push_authorized") is not False
        or authority.get("writes_performed") is not False
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB effective authority result drifted"
        )
    return authority


def _require_closure_locked_evaluation_input_r_validation(
    *,
    patch: Any,
    repo_root: Path,
    require_staged: bool,
) -> dict[str, Any]:
    """Adopt only a semantically exact input-only R bundle."""
    try:
        validation = patch.validate_locked_evaluation_input_bundle(
            repo_root=repo_root,
            require_staged=require_staged,
            verify_remote=True,
        )
    except patch.ClosureLockedEvaluationInputBundleError as exc:
        raise ClosureLockedEvaluationInputBundleAdapterError(str(exc)) from exc
    expected_stage = "exact6_staged" if require_staged else "physical_and_light_untracked"
    if (
        type(validation) is not dict
        or validation.get("gate") != patch.PATCH_GATE
        or validation.get("status") != "input_bundle_validated"
        or validation.get("r_stage_state") != expected_stage
        or validation.get("physical_output_count") != 4
        or validation.get("tracked_output_count") != 6
        or validation.get("pointer_count") != 4
        or validation.get("summary_count") != 1
        or validation.get("manifest_count") != 1
        or validation.get("manifest_written_last") is not True
        or validation.get("input_only") is not True
        or validation.get("target_paths_opened") is not False
        or validation.get("target_availability_inspected") is not False
        or validation.get("outcome_paths_opened") is not False
        or validation.get("future_outcomes_accessed") is not False
        or validation.get("evaluation_authorized") is not False
        or validation.get("e0_m_authorized") is not False
        or validation.get("e0_u_authorized") is not False
        or validation.get("writes_performed") is not False
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB R semantic validation result drifted"
        )
    return validation


def closure_locked_evaluation_input_dvc_targets(
    patch: Any | None = None,
) -> tuple[Path, ...]:
    """Return the four physical R-E0-MI targets implied by the closed pointers."""
    module = _closure_locked_evaluation_input_bundle_module() if patch is None else patch
    _, _, r_scope = _closure_locked_evaluation_input_bundle_scopes(module)
    pointer_paths = sorted(
        path
        for path in r_scope
        if path.endswith(".parquet.dvc")
    )
    if len(pointer_paths) != 4 or len(set(pointer_paths)) != 4:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB R scope does not contain exactly four Parquet pointers"
        )
    return tuple(Path(path.removesuffix(".dvc")) for path in pointer_paths)


def closure_locked_evaluation_input_dvc_add_command(
    dvc_bin: str,
    target: Path,
) -> list[str]:
    """Build one exact no-relink R-E0-MI registration command."""
    if (
        dvc_bin != DEFAULT_DVC_BIN.as_posix()
        or target not in closure_locked_evaluation_input_dvc_targets()
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "R-E0-MI DVC add received a non-closed binary or target"
        )
    return [dvc_bin, "add", "--no-relink", target.as_posix()]


def validate_closure_locked_evaluation_input_dvc_binary(
    dvc_bin: str,
    *,
    repo_root: Path = Path("."),
) -> None:
    """Seal the repository DVC executable before any E0-MIB DVC command."""
    if dvc_bin != DEFAULT_DVC_BIN.as_posix():
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB requires the repository .venv/bin/dvc executable"
        )
    try:
        _require_no_symlink_ancestors(DEFAULT_DVC_BIN, anchor=repo_root)
        _require_regular_file(DEFAULT_DVC_BIN, mode=0o755)
    except DeferredDvcTargetError as exc:
        raise ClosureLockedEvaluationInputBundleAdapterError(str(exc)) from exc


def validate_closure_locked_evaluation_input_unmanaged_namespace(
    unmanaged_paths: list[Path],
) -> None:
    """Require exactly one ignored R namespace while tolerating rejected history."""
    namespace = Path("data/closure_v1/locked_evaluation")
    mib_paths = [
        path
        for path in unmanaged_paths
        if path == namespace or namespace in path.parents
    ]
    if mib_paths != [namespace]:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "R-E0-MI ignored namespace is not the exact locked-evaluation directory"
        )


def write_closure_locked_evaluation_input_dvc_failure_report(
    *,
    report_path: Path,
    selected_dvc_paths: list[Path],
    rejected_unmanaged_paths: list[Path],
    git_status_before: str,
    dvc_status_before: dict[str, Any],
    dvc_add_results: list[CommandResult],
    failed_target_index: int,
) -> None:
    """Record a failed R add prefix without staging, pushing, retrying, or cleanup."""
    if (
        failed_target_index < 1
        or failed_target_index > 4
        or len(dvc_add_results) != failed_target_index
        or dvc_add_results[-1].returncode == 0
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "R-E0-MI DVC failure evidence dialect drifted"
        )
    failed = dvc_add_results[-1]
    write_report(
        report_path,
        dry_run=False,
        selected_dvc_paths=selected_dvc_paths,
        deferred_dvc_paths=[],
        deferred_snapshot_before=None,
        deferred_snapshot_after=None,
        rejected_unmanaged_paths=rejected_unmanaged_paths,
        git_status_before=git_status_before,
        dvc_status_before=dvc_status_before,
        dvc_status_after=None,
        cloud_status_before=None,
        dvc_add_results=dvc_add_results,
        dvc_push_result=None,
        git_add_result=None,
        publication_check_result=None,
        reproducibility_findings=[
            ReproducibilityFinding(
                "fail",
                "locked_evaluation_input_dvc_add",
                failed.command[-1],
                (
                    f"R-E0-MI DVC add {failed_target_index}/4 failed; any partial "
                    "pointer evidence was preserved. No Git staging or push ran, "
                    "and retry is forbidden pending an independent audit."
                ),
            )
        ],
        staged_status="",
        exclusive=True,
    )


def snapshot_closure_locked_evaluation_input_physical_outputs(
    *,
    repo_root: Path = Path("."),
) -> tuple[RegistrationFileIdentity, ...]:
    """Seal the four R physical files without decoding their Parquet content."""
    records: list[RegistrationFileIdentity] = []
    try:
        for path in closure_locked_evaluation_input_dvc_targets():
            identity = _registration_file_identity(
                repo_root / path,
                repo_root=repo_root,
                mode=0o644,
            )
            if identity.nlink != 1:
                raise ClosureLockedEvaluationInputBundleAdapterError(
                    f"R-E0-MI physical output is not single-link: {path}"
                )
            records.append(identity)
    except DeferredDvcTargetError as exc:
        raise ClosureLockedEvaluationInputBundleAdapterError(str(exc)) from exc
    if len(records) != 4 or len({record.path for record in records}) != 4:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "R-E0-MI physical output snapshot is not exact4"
        )
    return tuple(records)


def validate_closure_locked_evaluation_input_bundle_invocation(
    args: Any,
    *,
    gate: str,
    env: Mapping[str, str] | None = None,
) -> None:
    """Require closed H/P no-DVC or exact-four-target R-E0-MI invocation."""
    source = os.environ if env is None else env
    expected_targets: tuple[Path, ...] = ()
    if gate == "R-E0-MI":
        expected_targets = closure_locked_evaluation_input_dvc_targets()
    elif gate not in {"H-E0-MIB", "P-E0-MIB"}:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "Unknown E0-MIB invocation gate"
        )
    observed_targets = tuple(Path(value) for value in args.target)
    if (
        observed_targets != expected_targets
        or not args.no_push
        or args.yes
        or args.dry_run
        or args.skip_publication_check
        or args.jobs is not None
        or args.dvc_bin is not None
        or args.manifest != DEFAULT_DVC_MANIFEST
        or args.report is not None
        or not args.allow_unmanaged
        or bool(args.defer_dvc_target)
        or bool(getattr(args, "register_anfis_ablation_model_family", False))
        or args.verify_manifest_inputs
        or args.max_manifest_hash_bytes != DEFAULT_MAX_MANIFEST_HASH_BYTES
        or source.get("DVC_NO_ANALYTICS") != "1"
        or "DVC_BIN" in source
        or (
            source.get("DVC_SITE_CACHE_DIR") is not None
            and source["DVC_SITE_CACHE_DIR"]
            != DEFAULT_DVC_SITE_CACHE_DIR.as_posix()
        )
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "E0-MIB precommit requires exact --allow-unmanaged --no-push, "
            "default paths, mandatory publication checks, analytics-disabled DVC, "
            "and only the four registered R-E0-MI targets for the R gate"
        )


def validate_closure_locked_evaluation_input_bundle_staged_scope(
    staged_status: str,
    *,
    gate: str,
) -> None:
    patch = _closure_locked_evaluation_input_bundle_module()
    h_scope, p_scope, r_scope = _closure_locked_evaluation_input_bundle_scopes(
        patch
    )
    scopes = {
        "H-E0-MIB": h_scope,
        "P-E0-MIB": p_scope,
        "R-E0-MI": r_scope,
    }
    expected = scopes.get(gate)
    if expected is None:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "Unknown E0-MIB staged scope"
        )
    try:
        validate_anfis_ablation_git_name_status_map(
            staged_status,
            expected=expected,
            context=f"{gate} staged scope",
        )
    except DeferredDvcTargetError as exc:
        raise ClosureLockedEvaluationInputBundleAdapterError(str(exc)) from exc


def validate_closure_locked_evaluation_input_bundle_workspace_scope(
    status_output: str,
    *,
    gate: str,
) -> None:
    patch = _closure_locked_evaluation_input_bundle_module()
    h_scope, p_scope, r_scope = _closure_locked_evaluation_input_bundle_scopes(
        patch
    )
    scopes = {
        "H-E0-MIB": h_scope,
        "P-E0-MIB": p_scope,
        "R-E0-MI": r_scope,
    }
    expected = scopes.get(gate)
    if expected is None:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "Unknown E0-MIB workspace scope"
        )
    try:
        validate_anfis_ablation_git_short_status_map(
            status_output,
            expected=_expected_short_scope(expected, staged=True),
            context=f"{gate} workspace scope",
        )
    except DeferredDvcTargetError as exc:
        raise ClosureLockedEvaluationInputBundleAdapterError(str(exc)) from exc


def validate_closure_locked_evaluation_input_bundle_staged_bindings(
    *,
    gate: str,
    repo_root: Path = Path("."),
) -> tuple[RegistrationFileIdentity, ...]:
    """Bind every E0-MIB index blob to one stable regular worktree file."""
    patch = _closure_locked_evaluation_input_bundle_module()
    h_scope, p_scope, r_scope = _closure_locked_evaluation_input_bundle_scopes(
        patch
    )
    scopes = {
        "H-E0-MIB": h_scope,
        "P-E0-MIB": p_scope,
        "R-E0-MI": r_scope,
    }
    scope = scopes.get(gate)
    if scope is None:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "Unknown E0-MIB staged binding gate"
        )
    expected_modes = (
        _LOCKED_EVALUATION_INPUT_H_GIT_MODES
        if gate == "H-E0-MIB"
        else {path: "100644" for path in scope}
    )
    if (
        type(expected_modes) is not dict
        or set(expected_modes) != set(scope)
        or any(mode not in {"100644", "100755"} for mode in expected_modes.values())
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            f"{gate} staged mode contract drifted"
        )
    records: list[RegistrationFileIdentity] = []
    try:
        for raw_path in sorted(scope):
            expected_git_mode = expected_modes[raw_path]
            index_line = _git_output(
                repo_root, "ls-files", "-s", "--", raw_path
            ).strip()
            parts = index_line.split(maxsplit=3)
            if (
                len(parts) != 4
                or parts[0] != expected_git_mode
                or parts[2] != "0"
                or parts[3] != raw_path
            ):
                raise ClosureLockedEvaluationInputBundleAdapterError(
                    f"{gate} staged mode/path binding drifted: {raw_path}"
                )
            worktree_oid = _git_output(
                repo_root, "hash-object", "--no-filters", "--", raw_path
            ).strip()
            if len(parts[1]) != 40 or parts[1] != worktree_oid:
                raise ClosureLockedEvaluationInputBundleAdapterError(
                    f"{gate} index blob differs from worktree: {raw_path}"
                )
            identity = _registration_file_identity(
                repo_root / raw_path,
                repo_root=repo_root,
                mode=int(expected_git_mode[-3:], 8),
            )
            if identity.nlink != 1:
                raise ClosureLockedEvaluationInputBundleAdapterError(
                    f"{gate} staged path is not single-link: {raw_path}"
                )
            records.append(identity)
        if len(records) != len(scope):
            raise ClosureLockedEvaluationInputBundleAdapterError(
                f"{gate} staged binding count drifted"
            )
        return tuple(records)
    except DeferredDvcTargetError as exc:
        raise ClosureLockedEvaluationInputBundleAdapterError(str(exc)) from exc


def revalidate_closure_locked_evaluation_input_bundle_transaction(
    *,
    gate: str,
    staged_status: str,
    expected_physical_snapshot: tuple[RegistrationFileIdentity, ...] | None = None,
    repo_root: Path = Path("."),
) -> None:
    """Close E0-MIB Git scope and remote semantic races at each checkpoint."""
    validate_closure_locked_evaluation_input_bundle_staged_scope(
        staged_status,
        gate=gate,
    )
    current_staged = _git_output(
        repo_root,
        "diff",
        "--cached",
        "--name-status",
        "--no-renames",
    )
    validate_closure_locked_evaluation_input_bundle_staged_scope(
        current_staged,
        gate=gate,
    )
    workspace = _git_output(
        repo_root,
        "status",
        "--short",
        "--untracked-files=all",
    )
    validate_closure_locked_evaluation_input_bundle_workspace_scope(
        workspace,
        gate=gate,
    )
    first_bindings = validate_closure_locked_evaluation_input_bundle_staged_bindings(
        gate=gate,
        repo_root=repo_root,
    )
    patch = _closure_locked_evaluation_input_bundle_module()
    if gate == "H-E0-MIB":
        if _git_output(repo_root, "rev-parse", "HEAD").strip() != patch.BASE_P_MCALM_COMMIT:
            raise ClosureLockedEvaluationInputBundleAdapterError(
                "H-E0-MIB base changed during precommit"
            )
        _require_closure_locked_evaluation_input_prelock(
            patch=patch,
            repo_root=repo_root,
        )
    elif gate == "P-E0-MIB":
        _require_closure_locked_evaluation_input_unpublished_validation(
            patch=patch,
            repo_root=repo_root,
            expected_stage_state="staged",
        )
    elif gate == "R-E0-MI":
        if (
            expected_physical_snapshot is None
            or snapshot_closure_locked_evaluation_input_physical_outputs(
                repo_root=repo_root
            )
            != expected_physical_snapshot
        ):
            raise ClosureLockedEvaluationInputBundleAdapterError(
                "R-E0-MI physical outputs changed during registration/precommit"
            )
        _require_closure_locked_evaluation_input_authority(
            patch=patch,
            repo_root=repo_root,
            expected_stage_state="exact6_staged",
        )
        _require_closure_locked_evaluation_input_r_validation(
            patch=patch,
            repo_root=repo_root,
            require_staged=True,
        )
        if (
            snapshot_closure_locked_evaluation_input_physical_outputs(
                repo_root=repo_root
            )
            != expected_physical_snapshot
        ):
            raise ClosureLockedEvaluationInputBundleAdapterError(
                "R-E0-MI physical outputs changed during semantic revalidation"
            )
    else:
        raise ClosureLockedEvaluationInputBundleAdapterError(
            "Unknown E0-MIB transaction gate"
        )
    if (
        validate_closure_locked_evaluation_input_bundle_staged_bindings(
            gate=gate,
            repo_root=repo_root,
        )
        != first_bindings
    ):
        raise ClosureLockedEvaluationInputBundleAdapterError(
            f"{gate} staged files changed during semantic revalidation"
        )


def normalize_repo_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        return path
    repo_root = Path.cwd().resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root)
    except ValueError:
        return path


def is_experiment_manifest_path(path: Path) -> bool:
    text = path.as_posix()
    if path.name.endswith("_promotion_manifest.json"):
        return False
    if path in {CLOSURE_PROTOCOL_LOCK_PATH, CLOSURE_DEVELOPMENT_RUNTIME_LOCK_PATH}:
        return True
    if path.name == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH.name:
        return path == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH
    return text.startswith("reports/") and path.suffix == ".json" and "manifest" in path.name


def is_report_artifact_path(path: Path) -> bool:
    text = path.as_posix()
    if not text.startswith("reports/"):
        return False
    if text.startswith("reports/data/"):
        return False
    if path.name.endswith("_promotion_manifest.json"):
        return False
    if is_experiment_manifest_path(path):
        return False
    return path.suffix in REPORT_ARTIFACT_SUFFIXES


def manifest_record_path(record: Any) -> Path | None:
    if not isinstance(record, dict):
        return None
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    return normalize_repo_path(raw_path)


def record_display_path(path: Path) -> str:
    return path.as_posix() if not path.is_absolute() else str(path)


def manifest_output_records(payload: Any, manifest_path: Path) -> Any:
    if not isinstance(payload, dict):
        return None
    if manifest_path == CLOSURE_PROTOCOL_LOCK_PATH:
        return payload.get("generated_lock_companions")
    if manifest_path == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH:
        return [payload.get("output")]
    return payload.get("outputs")


def validate_closure_development_runtime_lock_manifest(
    manifest_path: Path,
) -> list[ReproducibilityFinding]:
    """Validate staged E0-DL physically without claiming it is published yet."""
    from src.experiments.closure_development_runtime_lock import (
        load_and_validate_development_runtime_lock,
    )

    try:
        _, summary = load_and_validate_development_runtime_lock(
            manifest_path,
            CLOSURE_DEVELOPMENT_RUNTIME_LOCK_SCHEMA,
            require_published=False,
            require_physical_artifacts=True,
        )
    except Exception as exc:
        return [
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                f"Closure E0-DL validation failed: {exc}",
            )
        ]

    expected = {
        "lock_version": CLOSURE_DEVELOPMENT_RUNTIME_LOCK_VERSION,
        "status": "locked",
        "publication_verified": False,
        "physical_artifacts_verified": True,
        "canonical_origin_identity_verified": True,
        "dvc_remote_verified_at_lock": True,
        "dvc_remote_verified": True,
        "locked_parent_published_at_lock": True,
        "payload_development_fit_authorized": True,
        "development_fit_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "fit_authorized": False,
        "future_outcomes_accessed": False,
    }
    drift = {
        key: {"observed": summary.get(key), "expected": value}
        for key, value in expected.items()
        if summary.get(key) != value
    }
    if drift:
        return [
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                f"Closure E0-DL authorization summary drifted: {drift}.",
            )
        ]
    return [
        ReproducibilityFinding(
            "ok",
            "manifest",
            manifest_path.as_posix(),
            "Closure E0-DL schema, hashes, ancestry, DVC ownership, and seals passed pre-publication validation.",
        )
    ]


def validate_closure_expert_state_manifest(
    manifest_path: Path,
) -> list[ReproducibilityFinding]:
    """Run the exact, outcome-free expert bundle and Parquet semantic audit."""
    from src.experiments.closure_contract import load_yaml_mapping
    from src.experiments.closure_development_runtime_lock import (
        expert_state_lock_record,
    )
    from src.experiments.closure_runtime_contract import DEFAULT_RUNTIME_CONFIG

    try:
        runtime = load_yaml_mapping(DEFAULT_RUNTIME_CONFIG)
        record = expert_state_lock_record(runtime, require_physical_artifact=True)
        completion_paths = {
            item.get("path")
            for item in record["completion_records"]
            if isinstance(item, Mapping)
        }
        if manifest_path.as_posix() not in completion_paths:
            raise ValueError("exact expert-state manifest path is absent from the bundle")
    except Exception as exc:
        return [
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                f"Closure expert-state validation failed: {exc}",
            )
        ]
    return [
        ReproducibilityFinding(
            "ok",
            "manifest",
            manifest_path.as_posix(),
            (
                "Closure expert-state provenance, explicit DVC pointer, lineage, "
                "and outcome-free Parquet semantic audit passed."
            ),
        )
    ]


def verify_manifest_file_record(
    *,
    record: Any,
    manifest_path: Path,
    section: str,
    findings: list[ReproducibilityFinding],
    max_hash_bytes: int,
    require_hash: bool,
    force_hash: bool = False,
) -> Path | None:
    record_path = manifest_record_path(record)
    if record_path is None:
        findings.append(
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                f"{section} record is missing a valid path.",
            )
        )
        return None

    actual_path = record_path
    display_path = record_display_path(record_path)
    if not actual_path.exists():
        findings.append(
            ReproducibilityFinding(
                "fail",
                "manifest",
                display_path,
                f"{manifest_path} lists this {section} path, but it does not exist.",
            )
        )
        return record_path

    if isinstance(record, dict):
        if actual_path.is_dir():
            actual_bytes, actual_sha = sha256_directory(actual_path)
        else:
            actual_bytes = actual_path.stat().st_size
            actual_sha = None

        expected_bytes = record.get("bytes")
        if isinstance(expected_bytes, int):
            if actual_bytes != expected_bytes:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        display_path,
                        f"{section} byte count changed: manifest={expected_bytes}, current={actual_bytes}.",
                    )
                )

        expected_sha = record.get("sha256")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    display_path,
                    f"{section} record is missing a 64-character SHA-256 hash.",
                )
            )
            return record_path

        should_hash = force_hash or (require_hash and actual_bytes <= max_hash_bytes)
        if should_hash:
            actual_sha = actual_sha or sha256_file(actual_path)
            if actual_sha != expected_sha:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        display_path,
                        f"{section} SHA-256 changed: manifest={expected_sha}, current={actual_sha}.",
                    )
                )
        elif require_hash:
            findings.append(
                ReproducibilityFinding(
                    "warn",
                    "manifest",
                    display_path,
                    (
                        f"{section} is {actual_bytes} bytes, above --max-manifest-hash-bytes="
                        f"{max_hash_bytes}; byte count was checked, SHA-256 was not recomputed."
                    ),
                )
            )

    return record_path


def discover_relevant_manifest_paths(staged_paths: set[Path]) -> list[Path]:
    manifest_paths = {path for path in staged_paths if is_experiment_manifest_path(path)}
    pointer_to_manifest = {
        Path(pointer): Path(manifest)
        for pointer, manifest in zip(
            ANFIS_ABLATION_SELECTION_POINTER_PATHS,
            ANFIS_ABLATION_MANIFEST_PATHS,
            strict=True,
        )
    }
    for pointer, manifest in pointer_to_manifest.items():
        if pointer in staged_paths:
            manifest_paths.add(manifest)
    if dvc_pointer_path(CLOSURE_COMMON_ORIGIN_OUTPUT_PATH) in staged_paths:
        manifest_paths.add(CLOSURE_COMMON_ORIGIN_MANIFEST_PATH)
    if dvc_pointer_path(CLOSURE_EXPERT_STATE_OUTPUT_PATH) in staged_paths:
        manifest_paths.add(CLOSURE_EXPERT_STATE_MANIFEST_PATH)
    for path in staged_paths:
        if not is_report_artifact_path(path):
            continue
        if not path.parent.exists():
            continue
        candidates = set(path.parent.glob("*manifest*.json"))
        closure_lock_candidate = path.parent / CLOSURE_PROTOCOL_LOCK_PATH.name
        if closure_lock_candidate == CLOSURE_PROTOCOL_LOCK_PATH and closure_lock_candidate.exists():
            candidates.add(closure_lock_candidate)
        for candidate in candidates:
            if not is_experiment_manifest_path(candidate):
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            outputs = manifest_output_records(payload, candidate)
            if not isinstance(outputs, list):
                continue
            output_paths = {record_path for record in outputs if (record_path := manifest_record_path(record)) is not None}
            if path in output_paths:
                manifest_paths.add(candidate)
    return sorted(manifest_paths, key=lambda path: path.as_posix())


def _canonical_json_sha256(value: Any) -> str | None:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(payload).hexdigest()


def validate_closure_mifal_development_manifest(
    payload: Any,
    manifest_path: Path,
) -> list[ReproducibilityFinding]:
    """Validate the exact manifest-last M0 dialect without rewriting it."""
    findings: list[ReproducibilityFinding] = []

    def fail(message: str) -> None:
        findings.append(
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                message,
            )
        )

    if manifest_path != CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_PATH:
        fail("Closure M0 manifest compatibility is restricted to its exact path.")
        return findings
    if not isinstance(payload, dict):
        fail("Closure M0 manifest must contain a JSON object.")
        return findings

    expected_top_level = {
        "schema_version",
        "experiment_id",
        "surface_id",
        "model_id",
        "gate",
        "status",
        "started_at_utc",
        "counts",
        "raw_prediction_contract",
        "model_spec_sha256",
        "lineage_audit_sha256",
        "runtime_versions",
        "effective_authority",
        "inputs",
        "script",
        "source_code",
        "outputs",
        "manifest_written_last",
        *CLOSURE_MIFAL_MANIFEST_FALSE_FLAGS,
        "outcome_access_log_state",
        "completion_marker_written_last",
    }
    if set(payload) != expected_top_level:
        fail("Closure M0 manifest top-level dialect drifted.")
    if (
        payload.get("schema_version")
        != CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_SCHEMA_VERSION
        or payload.get("experiment_id") != "closure_v1"
        or payload.get("surface_id")
        != "closure_v1_wqp_adaptive_no_current_chla"
        or payload.get("model_id") != "M0"
        or payload.get("gate") != "E0-MR"
        or payload.get("status") != CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_STATUS
    ):
        fail("Closure M0 manifest identity/schema/status drifted.")

    started_at = payload.get("started_at_utc")
    try:
        parsed_started_at = datetime.fromisoformat(started_at)
    except (TypeError, ValueError):
        parsed_started_at = None
    if (
        parsed_started_at is None
        or not isinstance(started_at, str)
        or not started_at.endswith("+00:00")
        or parsed_started_at.tzinfo is None
    ):
        fail("Closure M0 manifest UTC start timestamp is invalid.")
    if payload.get("counts") != CLOSURE_MIFAL_EXPECTED_COUNTS:
        fail("Closure M0 manifest denominators drifted.")

    raw_contract = payload.get("raw_prediction_contract")
    if (
        not isinstance(raw_contract, dict)
        or _canonical_json_sha256(raw_contract)
        != CLOSURE_MIFAL_RAW_PREDICTION_CONTRACT_SHA256
    ):
        fail("Closure M0 exact 28-column raw prediction contract drifted.")
    expected_authority = {
        **CLOSURE_MIFAL_EXPECTED_AUTHORITY,
        "raw_prediction_contract": raw_contract,
    }
    if payload.get("effective_authority") != expected_authority:
        fail("Closure M0 effective E0-MR authority drifted.")

    runtime_versions = payload.get("runtime_versions")
    if (
        not isinstance(runtime_versions, dict)
        or set(runtime_versions)
        != {
            "python",
            "numpy",
            "pandas",
            "pyarrow",
            "threadpoolctl",
            "threadpool_limit",
            "mifal_core",
        }
        or any(
            not isinstance(runtime_versions.get(name), str)
            or not runtime_versions[name]
            for name in (
                "python",
                "numpy",
                "pandas",
                "pyarrow",
                "threadpoolctl",
            )
        )
        or runtime_versions.get("threadpool_limit") != 1
        or runtime_versions.get("mifal_core") != "5.0.0"
    ):
        fail("Closure M0 runtime-version record drifted.")

    inputs = payload.get("inputs")
    input_by_path: dict[Path, dict[str, Any]] = {}
    expected_input_bindings = [
        (path.as_posix(), role)
        for path, role in CLOSURE_MIFAL_DEVELOPMENT_INPUT_PATHS_AND_ROLES
    ]
    if not isinstance(inputs, list) or len(inputs) != len(expected_input_bindings):
        fail("Closure M0 manifest must bind exactly 28 inputs.")
    else:
        observed_input_bindings: list[tuple[str, str]] = []
        valid_inputs = True
        for raw_record in inputs:
            if not isinstance(raw_record, dict):
                valid_inputs = False
                continue
            record = cast(dict[str, Any], raw_record)
            path = record.get("path")
            role = record.get("artifact_role")
            sha256 = record.get("sha256")
            if (
                set(record) != {"path", "bytes", "sha256", "artifact_role"}
                or not isinstance(path, str)
                or not isinstance(role, str)
                or type(record.get("bytes")) is not int
                or record["bytes"] < 1
                or not isinstance(sha256, str)
                or len(sha256) != 64
                or any(character not in "0123456789abcdef" for character in sha256)
            ):
                valid_inputs = False
                continue
            observed_input_bindings.append((path, role))
            input_by_path[Path(path)] = record
        if (
            not valid_inputs
            or observed_input_bindings != expected_input_bindings
            or len(input_by_path) != len(expected_input_bindings)
        ):
            fail("Closure M0 input paths, roles, order, or record dialect drifted.")

    script = payload.get("script")
    if (
        CLOSURE_MIFAL_DEVELOPMENT_SCRIPT not in input_by_path
        or script != input_by_path.get(CLOSURE_MIFAL_DEVELOPMENT_SCRIPT)
    ):
        fail("Closure M0 generating script is not the exact bound runner input.")
    source_code = payload.get("source_code")
    if (
        not isinstance(source_code, list)
        or len(source_code) != len(CLOSURE_MIFAL_DEVELOPMENT_SOURCE_PATHS)
        or [manifest_record_path(record) for record in source_code]
        != list(CLOSURE_MIFAL_DEVELOPMENT_SOURCE_PATHS)
        or any(
            record != input_by_path.get(path)
            for record, path in zip(
                source_code,
                CLOSURE_MIFAL_DEVELOPMENT_SOURCE_PATHS,
                strict=True,
            )
        )
    ):
        fail("Closure M0 source-code triplet drifted from its bound inputs.")

    outputs = payload.get("outputs")
    output_by_path: dict[Path, dict[str, Any]] = {}
    if (
        not isinstance(outputs, list)
        or len(outputs) != len(CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS)
    ):
        fail("Closure M0 manifest must bind exactly five pre-manifest outputs.")
    else:
        valid_outputs = True
        for raw_record in outputs:
            if not isinstance(raw_record, dict):
                valid_outputs = False
                continue
            record = cast(dict[str, Any], raw_record)
            path = manifest_record_path(record)
            sha256 = record.get("sha256")
            if (
                set(record) != {"path", "bytes", "sha256"}
                or path is None
                or type(record.get("bytes")) is not int
                or record["bytes"] < 1
                or not isinstance(sha256, str)
                or len(sha256) != 64
                or any(character not in "0123456789abcdef" for character in sha256)
            ):
                valid_outputs = False
                continue
            output_by_path[path] = record
        if (
            not valid_outputs
            or [manifest_record_path(record) for record in outputs]
            != list(CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS)
            or len(output_by_path) != len(CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS)
        ):
            fail("Closure M0 output paths, order, or record dialect drifted.")

    model_spec_path = CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS[1]
    lineage_path = CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS[2]
    if (
        payload.get("model_spec_sha256")
        != output_by_path.get(model_spec_path, {}).get("sha256")
        or payload.get("lineage_audit_sha256")
        != output_by_path.get(lineage_path, {}).get("sha256")
    ):
        fail("Closure M0 model-spec/lineage cross-hashes drifted.")

    if payload.get("manifest_written_last") is not True:
        fail("Closure M0 manifest must record manifest_written_last=true.")
    for field in CLOSURE_MIFAL_MANIFEST_FALSE_FLAGS:
        if payload.get(field) is not False:
            fail(f"Closure M0 manifest requires `{field}=false`.")
    if payload.get("outcome_access_log_state") != "absent":
        fail("Closure M0 outcome-access log state must remain absent.")
    if (
        tuple(payload)[-1:] != ("completion_marker_written_last",)
        or payload.get("completion_marker_written_last") is not True
    ):
        fail("Closure M0 completion marker must be the true final top-level key.")

    if findings:
        return findings
    return [
        ReproducibilityFinding(
            "ok",
            "manifest",
            manifest_path.as_posix(),
            (
                "Closure M0 schema, E0-MR authority, 28 inputs, three source "
                "records, five outputs, cross-hashes, and manifest-last seals passed."
            ),
        )
    ]


def validate_experiment_manifests(
    *,
    staged_paths: set[Path],
    artifacts: list[DvcArtifact],
    max_hash_bytes: int,
    verify_manifest_inputs: bool,
) -> list[ReproducibilityFinding]:
    findings: list[ReproducibilityFinding] = []
    report_artifacts = sorted(
        {path for path in staged_paths if is_report_artifact_path(path)},
        key=lambda path: path.as_posix(),
    )
    manifest_paths = discover_relevant_manifest_paths(staged_paths)
    covered_outputs: dict[Path, list[Path]] = {}
    checked_outputs = 0

    if not report_artifacts and not manifest_paths:
        return [
            ReproducibilityFinding(
                "ok",
                "manifest",
                "-",
                "No staged report artifacts require experiment-manifest validation.",
            )
        ]

    for manifest_path in manifest_paths:
        if not manifest_path.exists():
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest is referenced by staged reports but does not exist.",
                )
            )
            continue

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    f"Experiment manifest is not valid JSON: {exc}.",
                )
            )
            continue

        is_closure_protocol_lock = manifest_path == CLOSURE_PROTOCOL_LOCK_PATH
        is_closure_development_runtime_lock = (
            manifest_path == CLOSURE_DEVELOPMENT_RUNTIME_LOCK_PATH
        )
        is_closure_common_origin_manifest = (
            manifest_path == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH
        )
        is_closure_expert_state_manifest = (
            manifest_path == CLOSURE_EXPERT_STATE_MANIFEST_PATH
        )
        is_closure_mifal_development_manifest = (
            manifest_path == CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_PATH
        )
        if is_closure_development_runtime_lock:
            findings.extend(
                validate_closure_development_runtime_lock_manifest(manifest_path)
            )
            continue
        if is_closure_expert_state_manifest:
            findings.extend(validate_closure_expert_state_manifest(manifest_path))
        if is_closure_protocol_lock:
            lock_version = payload.get("lock_version") if isinstance(payload, dict) else None
            status = payload.get("status") if isinstance(payload, dict) else None
            if lock_version != CLOSURE_PROTOCOL_LOCK_VERSION:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        (
                            f"Closure protocol lock version is `{lock_version}`, "
                            f"expected `{CLOSURE_PROTOCOL_LOCK_VERSION}`."
                        ),
                    )
                )
            if status != "locked":
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        f"Closure protocol lock status is `{status}`, expected `locked`.",
                    )
                )
            for field in (
                "future_outcomes_accessed",
                "lock_command_semantically_decodes_post_2021_outcomes",
                "holdout_assignment_created",
            ):
                value = payload.get(field) if isinstance(payload, dict) else None
                if value is not False:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            f"Closure protocol lock requires `{field}=false`.",
                        )
                    )
            locked_repository = payload.get("locked_repository") if isinstance(payload, dict) else None
            if (
                not isinstance(locked_repository, dict)
                or locked_repository.get("worktree_status") != "clean"
                or locked_repository.get("dirty_paths") != []
            ):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure protocol lock must record a clean repository with no dirty paths.",
                    )
                )
        elif is_closure_common_origin_manifest:
            if not isinstance(payload, dict):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure common-origin manifest must contain a JSON object.",
                    )
                )
            else:
                manifest_version = payload.get("manifest_version")
                if manifest_version != CLOSURE_COMMON_ORIGIN_MANIFEST_VERSION:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            (
                                f"Closure common-origin manifest version is `{manifest_version}`, "
                                f"expected `{CLOSURE_COMMON_ORIGIN_MANIFEST_VERSION}`."
                            ),
                        )
                    )
                for field, expected in (
                    ("status", "completed"),
                    ("experiment_id", "closure_v1"),
                    ("surface_id", "closure_v1_wqp_adaptive_no_current_chla"),
                    ("future_outcomes_accessed", False),
                    ("target_values_projected", []),
                    ("target_parquet_semantically_opened", False),
                    ("post_cutoff_target_rows_materialized", 0),
                    ("target_availability_used_for_origin_selection", False),
                    ("availability_join", "left_after_intent_freeze"),
                ):
                    value = payload.get(field)
                    matches = value == expected
                    if expected is False:
                        matches = value is False
                    elif field == "post_cutoff_target_rows_materialized":
                        matches = type(value) is int and value == 0
                    if not matches:
                        findings.append(
                            ReproducibilityFinding(
                                "fail",
                                "manifest",
                                manifest_path.as_posix(),
                                (
                                    "Closure common-origin manifest requires "
                                    f"`{field}={json.dumps(expected)}`."
                                ),
                            )
                        )
                execution = payload.get("execution")
                repository = execution.get("repository") if isinstance(execution, dict) else None
                base_head = repository.get("base_head") if isinstance(repository, dict) else None
                status = (
                    repository.get("tracked_worktree_status")
                    if isinstance(repository, dict)
                    else None
                )
                status_lines = (
                    repository.get("tracked_status_lines")
                    if isinstance(repository, dict)
                    else None
                )
                valid_head = (
                    isinstance(base_head, str)
                    and len(base_head) in {40, 64}
                    and set(base_head).issubset(set("0123456789abcdef"))
                )
                valid_status = (
                    status in {"clean", "dirty"}
                    and isinstance(status_lines, list)
                    and all(isinstance(line, str) and line for line in status_lines)
                    and status == ("dirty" if status_lines else "clean")
                )
                if (
                    not isinstance(execution, dict)
                    or set(execution)
                    != {
                        "repository",
                        "source_tree_identity",
                        "reproduction_command",
                        "future_outcomes_semantically_decoded",
                    }
                    or not isinstance(repository, dict)
                    or set(repository)
                    != {
                        "base_head",
                        "base_head_is_complete_source_identity",
                        "tracked_worktree_status",
                        "tracked_status_lines",
                    }
                    or not valid_head
                    or repository.get("base_head_is_complete_source_identity") is not False
                    or not valid_status
                    or execution.get("source_tree_identity")
                    != "code_config_parent_sha256_records"
                    or execution.get("future_outcomes_semantically_decoded") is not False
                    or execution.get("reproduction_command")
                    != CLOSURE_COMMON_ORIGIN_REPRODUCTION_COMMAND
                ):
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            "Closure common-origin manifest has an invalid sealed execution record.",
                        )
                    )
        elif is_closure_mifal_development_manifest:
            findings.extend(
                validate_closure_mifal_development_manifest(payload, manifest_path)
            )
        elif isinstance(payload, dict) and payload.get("status") not in {None, "completed"}:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    f"Experiment manifest status is `{payload.get('status')}`, expected `completed`.",
                )
            )

        outputs = manifest_output_records(payload, manifest_path)
        if not isinstance(outputs, list) or not outputs:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest must contain a non-empty `outputs` list.",
                )
            )
            continue

        if is_closure_common_origin_manifest:
            output_paths = tuple(manifest_record_path(record) for record in outputs)
            if output_paths != (CLOSURE_COMMON_ORIGIN_OUTPUT_PATH,):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        (
                            "Closure common-origin manifest must contain exactly the output "
                            f"`{CLOSURE_COMMON_ORIGIN_OUTPUT_PATH}`."
                        ),
                    )
                )

        for record in outputs:
            record_path = verify_manifest_file_record(
                record=record,
                manifest_path=manifest_path,
                section="output",
                findings=findings,
                max_hash_bytes=max_hash_bytes,
                require_hash=True,
                force_hash=(
                    is_closure_common_origin_manifest
                    or is_closure_expert_state_manifest
                    or is_closure_mifal_development_manifest
                ),
            )
            if record_path is not None:
                covered_outputs.setdefault(record_path, []).append(manifest_path)
                checked_outputs += 1

        if is_closure_protocol_lock:
            protocol_components = payload.get("protocol_components") if isinstance(payload, dict) else None
            source_artifacts = payload.get("source_artifacts") if isinstance(payload, dict) else None
            lock_scripts = (
                [
                    record
                    for record in protocol_components
                    if manifest_record_path(record) == CLOSURE_PROTOCOL_LOCK_SCRIPT
                ]
                if isinstance(protocol_components, list)
                else []
            )
            if len(lock_scripts) != 1:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure protocol lock must contain exactly one generating-script record.",
                    )
                )
            script = lock_scripts[0] if len(lock_scripts) == 1 else None
            if not isinstance(protocol_components, list) or not isinstance(source_artifacts, list):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure protocol lock must contain protocol-components and source-artifacts lists.",
                    )
                )
                inputs: Any = []
            else:
                inputs = [*protocol_components, *source_artifacts]
        elif is_closure_common_origin_manifest:
            code = payload.get("code") if isinstance(payload, dict) else None
            configs = payload.get("configs") if isinstance(payload, dict) else None
            source_inputs = payload.get("source_inputs") if isinstance(payload, dict) else None
            parent_artifacts = payload.get("parent_artifacts") if isinstance(payload, dict) else None
            common_origin_sections = (
                ("code", code, CLOSURE_COMMON_ORIGIN_CODE_PATHS),
                ("configs", configs, CLOSURE_COMMON_ORIGIN_CONFIG_PATHS),
                ("source_inputs", source_inputs, CLOSURE_COMMON_ORIGIN_SOURCE_PATHS),
                (
                    "parent_artifacts",
                    parent_artifacts,
                    tuple(path for path, _ in CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES),
                ),
            )
            inputs = []
            for section_name, records, expected_paths in common_origin_sections:
                if not isinstance(records, list) or not records:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            (
                                "Closure common-origin manifest must contain a non-empty "
                                f"`{section_name}` list."
                            ),
                        )
                    )
                    continue
                observed_paths = tuple(manifest_record_path(record) for record in records)
                if observed_paths != expected_paths:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            (
                                f"Closure common-origin `{section_name}` paths must equal "
                                f"{[path.as_posix() for path in expected_paths]}."
                            ),
                        )
                    )
                inputs.extend(records)

            if isinstance(source_inputs, list):
                for raw_record, expected_role in zip(
                    source_inputs,
                    CLOSURE_COMMON_ORIGIN_SOURCE_ROLES,
                    strict=False,
                ):
                    record = cast(dict[str, Any], raw_record) if isinstance(raw_record, dict) else None
                    if (
                        record is None
                        or record.get("role") != expected_role
                        or record.get("hash_source") != "protocol_lock"
                    ):
                        findings.append(
                            ReproducibilityFinding(
                                "fail",
                                "manifest",
                                manifest_path.as_posix(),
                                "Closure common-origin source roles/hash_source are invalid.",
                            )
                        )
                        break

            if isinstance(parent_artifacts, list):
                for raw_record, (_, expected_role) in zip(
                    parent_artifacts,
                    CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES,
                    strict=False,
                ):
                    record = cast(dict[str, Any], raw_record) if isinstance(raw_record, dict) else None
                    if record is None or record.get("role") != expected_role:
                        findings.append(
                            ReproducibilityFinding(
                                "fail",
                                "manifest",
                                manifest_path.as_posix(),
                                "Closure common-origin parent roles are invalid.",
                            )
                        )
                        break

            assignment = payload.get("assignment") if isinstance(payload, dict) else None
            assignment_parent = (
                parent_artifacts[2]
                if isinstance(parent_artifacts, list) and len(parent_artifacts) == 3
                else None
            )
            if (
                not isinstance(assignment, dict)
                or assignment.get("path")
                != CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES[2][0].as_posix()
                or type(assignment.get("bytes")) is not int
                or assignment.get("bytes", -1) < 0
                or not isinstance(assignment.get("sha256"), str)
                or assignment.get("eligible_locations") != 441
                or assignment.get("development_locations") != 353
                or assignment.get("holdout_locations") != 88
                or assignment.get("holdout_fit_overlap_count") != 0
                or not isinstance(assignment_parent, dict)
                or assignment_parent.get("bytes") != assignment.get("bytes")
                or assignment_parent.get("sha256") != assignment.get("sha256")
            ):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure common-origin assignment provenance is invalid.",
                    )
                )

            generating_scripts = (
                [
                    record
                    for record in code
                    if manifest_record_path(record)
                    == CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT
                ]
                if isinstance(code, list)
                else []
            )
            if len(generating_scripts) != 1:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        (
                            "Closure common-origin manifest must contain exactly one "
                            "generating-script record for "
                            f"`{CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT}`."
                        ),
                    )
                )
            script = generating_scripts[0] if len(generating_scripts) == 1 else None
        elif is_closure_expert_state_manifest:
            script = payload.get("script") if isinstance(payload, dict) else None
            expert_inputs = payload.get("inputs") if isinstance(payload, dict) else None
            expert_dependencies = (
                payload.get("dependencies") if isinstance(payload, dict) else None
            )
            inputs = (
                [*expert_inputs, *expert_dependencies]
                if isinstance(expert_inputs, list)
                and isinstance(expert_dependencies, list)
                else None
            )
        else:
            script = payload.get("script") if isinstance(payload, dict) else None
            inputs = payload.get("inputs") if isinstance(payload, dict) else None

        if isinstance(script, dict):
            verify_manifest_file_record(
                record=script,
                manifest_path=manifest_path,
                section="script",
                findings=findings,
                max_hash_bytes=max_hash_bytes,
                require_hash=True,
                force_hash=True,
            )
        elif not is_closure_protocol_lock and not is_closure_common_origin_manifest:
            findings.append(
                ReproducibilityFinding(
                    "warn",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest does not record the generating script.",
                )
            )

        if isinstance(inputs, list):
            for record in inputs:
                verify_manifest_file_record(
                    record=record,
                    manifest_path=manifest_path,
                    section="input",
                    findings=findings,
                    max_hash_bytes=max_hash_bytes,
                    require_hash=(
                        verify_manifest_inputs
                        or is_closure_common_origin_manifest
                        or is_closure_expert_state_manifest
                        or is_closure_mifal_development_manifest
                    ),
                    force_hash=(
                        is_closure_common_origin_manifest
                        or is_closure_expert_state_manifest
                        or is_closure_mifal_development_manifest
                    ),
                )
        elif inputs is None:
            findings.append(
                ReproducibilityFinding(
                    "warn",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest does not record inputs.",
                )
            )
        else:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest `inputs` field must be a list when present.",
                )
            )

    for path in report_artifacts:
        if path not in covered_outputs:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    path.as_posix(),
                    "Staged report artifact is not listed in any experiment manifest output.",
                )
            )

    staged_dvc_outputs = [
        path
        for path in covered_outputs
        if is_artifact_covered(path.as_posix(), artifacts) and dvc_pointer_path(path).exists()
    ]
    findings.append(
        ReproducibilityFinding(
            "ok",
            "manifest",
            "-",
            (
                f"Checked {len(manifest_paths)} experiment manifest(s), {checked_outputs} output record(s), "
                f"and {len(report_artifacts)} staged report artifact(s). "
                f"{len(staged_dvc_outputs)} covered output(s) are also protected by DVC pointers."
            ),
        )
    )
    return findings


def validate_dvc_pointers(staged_paths: set[Path], selected_dvc_paths: list[Path]) -> list[ReproducibilityFinding]:
    findings: list[ReproducibilityFinding] = []
    pointer_paths = {path for path in staged_paths if path.suffix == ".dvc"}
    pointer_paths.update(dvc_pointer_path(path) for path in selected_dvc_paths)

    if not pointer_paths:
        return [ReproducibilityFinding("ok", "dvc", "-", "No DVC pointer files need pointer-structure validation.")]

    for pointer_path in sorted(pointer_paths, key=lambda path: path.as_posix()):
        if not pointer_path.exists():
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "dvc",
                    pointer_path.as_posix(),
                    "Expected DVC pointer file does not exist.",
                )
            )
            continue
        try:
            payload = yaml.safe_load(pointer_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "dvc",
                    pointer_path.as_posix(),
                    f"DVC pointer is not valid YAML: {exc}.",
                )
            )
            continue
        outs = payload.get("outs") if isinstance(payload, dict) else None
        if not isinstance(outs, list) or not outs:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "dvc",
                    pointer_path.as_posix(),
                    "DVC pointer must contain a non-empty `outs` list.",
                )
            )
            continue
        for out in outs:
            if not isinstance(out, dict) or not out.get("path") or not out.get("md5"):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "dvc",
                        pointer_path.as_posix(),
                        "Each DVC pointer output must include `path` and `md5`.",
                    )
                )
                break

    if not any(finding.level == "fail" and finding.check == "dvc" for finding in findings):
        findings.append(
            ReproducibilityFinding(
                "ok",
                "dvc",
                "-",
                f"Validated {len(pointer_paths)} DVC pointer file(s).",
            )
        )
    return findings


def is_freeze_sensitive_path(path: Path) -> bool:
    text = path.as_posix()
    if path in FREEZE_ARTIFACT_PATHS:
        return False
    if text in FREEZE_SENSITIVE_EXACT_PATHS:
        return True
    return any(text.startswith(prefix) for prefix in FREEZE_SENSITIVE_PREFIXES)


def validate_freeze_freshness(staged_rows: list[tuple[str, Path]]) -> list[ReproducibilityFinding]:
    changed_paths = {path for _, path in staged_rows}
    sensitive_paths = sorted(
        {path for path in changed_paths if is_freeze_sensitive_path(path)},
        key=lambda path: path.as_posix(),
    )
    changed_freeze_outputs = changed_paths.intersection(FREEZE_REQUIRED_OUTPUTS)
    freeze_documentation_only = (
        sensitive_paths == [Path("src/data/freeze.py")]
        and bool(changed_freeze_outputs)
        and changed_freeze_outputs.issubset(FREEZE_DOCUMENTATION_OUTPUTS)
    )
    findings: list[ReproducibilityFinding] = []

    if sensitive_paths:
        if freeze_documentation_only:
            findings.append(
                ReproducibilityFinding(
                    "ok",
                    "freeze",
                    "src/data/freeze.py",
                    "Freeze generator documentation changes are paired with freeze Markdown/JSON metadata; derived file hashes are not required.",
                )
            )
        else:
            missing_freeze_outputs = sorted(FREEZE_REQUIRED_OUTPUTS - changed_paths, key=lambda path: path.as_posix())
            if missing_freeze_outputs:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "freeze",
                        ", ".join(path.as_posix() for path in sensitive_paths[:5]),
                        (
                            "Freeze-sensitive data pipeline changes are staged, but not all required "
                            f"freeze outputs are staged: {', '.join(path.as_posix() for path in missing_freeze_outputs)}."
                        ),
                    )
                )
            else:
                findings.append(
                    ReproducibilityFinding(
                        "ok",
                        "freeze",
                        "-",
                        f"Freeze-sensitive changes are paired with {len(FREEZE_REQUIRED_OUTPUTS)} required freeze outputs.",
                    )
                )
    else:
        findings.append(
            ReproducibilityFinding(
                "ok",
                "freeze",
                "-",
                "No freeze-sensitive data pipeline changes are staged.",
            )
        )

    if changed_freeze_outputs and changed_freeze_outputs != FREEZE_REQUIRED_OUTPUTS and not freeze_documentation_only:
        findings.append(
            ReproducibilityFinding(
                "fail",
                "freeze",
                ", ".join(path.as_posix() for path in sorted(changed_freeze_outputs, key=lambda path: path.as_posix())),
                "A data-freeze update must stage derived CSV, JSON manifest, and DATA_FREEZE.md together.",
            )
        )

    if DEFAULT_DVC_ARTIFACT_INVENTORY in changed_paths and not sensitive_paths:
        findings.append(
            ReproducibilityFinding(
                "ok",
                "freeze",
                DEFAULT_DVC_ARTIFACT_INVENTORY.as_posix(),
                (
                    "DVC artifact inventory changed, but no freeze-sensitive data pipeline paths "
                    "are staged; data-freeze regeneration is not required by this check."
                ),
            )
        )

    return findings


def reproducibility_checks(
    *,
    staged_status: str,
    selected_dvc_paths: list[Path],
    artifacts: list[DvcArtifact],
    max_manifest_hash_bytes: int,
    verify_manifest_inputs: bool,
) -> list[ReproducibilityFinding]:
    staged_rows = parse_git_name_status(staged_status)
    staged_paths = {path for status, path in staged_rows if not status.startswith("D")}
    findings: list[ReproducibilityFinding] = []
    findings.extend(validate_dvc_pointers(staged_paths, selected_dvc_paths))
    findings.extend(
        validate_experiment_manifests(
            staged_paths=staged_paths,
            artifacts=artifacts,
            max_hash_bytes=max_manifest_hash_bytes,
            verify_manifest_inputs=verify_manifest_inputs,
        )
    )
    findings.extend(validate_freeze_freshness(staged_rows))
    return findings


def has_failing_findings(findings: list[ReproducibilityFinding]) -> bool:
    return any(finding.level == "fail" for finding in findings)


def _final_calibration_r8_manifest_reproducibility_patch_module() -> Any:
    """Import E0-MCALK lazily so the generic assistant stays independent."""
    from src.experiments import (
        closure_final_calibration_r8_manifest_reproducibility_patch as patch,
    )

    return patch


def _final_calibration_r8_coordination_namespace_revalidation_patch_module() -> Any:
    """Import E0-MCALL lazily so the generic assistant stays independent."""
    from src.experiments import (
        closure_final_calibration_r8_coordination_namespace_revalidation_patch as patch,
    )

    return patch


def _final_calibration_r8_post_publication_authority_patch_module() -> Any:
    """Import E0-MCALM lazily so the generic assistant stays independent."""
    from src.experiments import (
        closure_final_calibration_r8_post_publication_authority_patch as patch,
    )

    return patch


def _closure_locked_evaluation_input_bundle_module() -> Any:
    """Import E0-MIB lazily so the generic assistant stays independent."""
    from src.experiments import closure_locked_evaluation_input_bundle as patch

    return patch


def _exact_finding_multiset(
    observed: list[ReproducibilityFinding],
    expected: tuple[ReproducibilityFinding, ...],
) -> bool:
    return len(observed) == len(expected) and all(
        observed.count(finding) == expected.count(finding)
        for finding in set(expected)
    )


def adopt_final_calibration_r8_manifest_reproducibility_findings(
    findings: list[ReproducibilityFinding],
    *,
    staged_status: str,
    repo_root: Path = Path("."),
) -> list[ReproducibilityFinding]:
    """Adopt only the exact four generic R8 dialect findings under E0-MCALK."""
    patch = _final_calibration_r8_manifest_reproducibility_patch_module()
    validate_anfis_ablation_git_name_status_map(
        staged_status,
        expected=patch.R8_STAGED_SCOPE,
        context="R-E0-MCALK staged scope",
    )
    expected = tuple(
        ReproducibilityFinding(**record)
        for record in patch.GENERIC_MANIFEST_FINDINGS_CONTRACT
    )
    observed_non_ok = [finding for finding in findings if finding.level != "ok"]
    if not _exact_finding_multiset(observed_non_ok, expected):
        return [
            *findings,
            ReproducibilityFinding(
                "fail",
                "final_calibration_r8_manifest_reproducibility",
                "R-E0-MCALK",
                "E0-MCALK generic manifest findings were not the exact four-finding multiset.",
            ),
        ]
    try:
        validation = patch.validate_final_calibration_r8_manifest_reproducibility_adoption(
            repo_root=repo_root,
            require_staged=True,
        )
    except patch.FinalCalibrationR8ManifestReproducibilityPatchError as exc:
        return [
            *findings,
            ReproducibilityFinding(
                "fail",
                "final_calibration_r8_manifest_reproducibility",
                "R-E0-MCALK",
                str(exc),
            ),
        ]
    if (
        type(validation) is not dict
        or validation.get("gate") != patch.PATCH_GATE
        or validation.get("status")
        != "r8_manifest_reproducibility_adoption_validated"
        or validation.get("r8_output_count") != 8
        or validation.get("calibration_output_count") != 6
        or validation.get("e7_output_count") != 2
        or validation.get("r_lifecycle_state")
        != "both_bundles_completed_unpublished"
        or validation.get("r8_outputs") != list(patch.R8_OUTPUT_CONTRACT)
        or validation.get("expected_non_ok_findings")
        != list(patch.GENERIC_MANIFEST_FINDINGS_CONTRACT)
        or validation.get("staged_scope_verified") is not True
        or validation.get("scientific_rerun_performed") is not False
        or validation.get("r8_rewrite_performed") is not False
    ):
        return [
            *findings,
            ReproducibilityFinding(
                "fail",
                "final_calibration_r8_manifest_reproducibility",
                "R-E0-MCALK",
                "E0-MCALK strict R8 adoption result drifted.",
            ),
        ]
    adopted = [finding for finding in findings if finding.level == "ok"]
    adopted.append(
        ReproducibilityFinding(
            "ok",
            "final_calibration_r8_manifest_reproducibility",
            "R-E0-MCALK",
            "Adopted the exact two status failures and two script warnings after strict MCALK R8 validation.",
        )
    )
    return adopted


def final_calibration_r8_manifest_reproducibility_checks(
    *,
    staged_status: str,
    selected_dvc_paths: list[Path],
    artifacts: list[DvcArtifact],
    max_manifest_hash_bytes: int,
    verify_manifest_inputs: bool,
    repo_root: Path = Path("."),
) -> list[ReproducibilityFinding]:
    """Run unchanged generic checks, then the exact R-E0-MCALK adapter."""
    generic = reproducibility_checks(
        staged_status=staged_status,
        selected_dvc_paths=selected_dvc_paths,
        artifacts=artifacts,
        max_manifest_hash_bytes=max_manifest_hash_bytes,
        verify_manifest_inputs=verify_manifest_inputs,
    )
    return adopt_final_calibration_r8_manifest_reproducibility_findings(
        generic,
        staged_status=staged_status,
        repo_root=repo_root,
    )


def adopt_final_calibration_r8_coordination_namespace_revalidation_findings(
    findings: list[ReproducibilityFinding],
    *,
    staged_status: str,
    repo_root: Path = Path("."),
) -> list[ReproducibilityFinding]:
    """Adopt only the exact four generic R8 findings under E0-MCALL."""
    patch = _final_calibration_r8_coordination_namespace_revalidation_patch_module()
    try:
        validate_anfis_ablation_git_name_status_map(
            staged_status,
            expected=patch.R8_STAGED_SCOPE,
            context="R-E0-MCALL staged scope",
        )
    except DeferredDvcTargetError as exc:
        return [
            *findings,
            ReproducibilityFinding(
                "fail",
                "final_calibration_r8_coordination_namespace_revalidation",
                "R-E0-MCALL",
                str(exc),
            ),
        ]
    expected = tuple(
        ReproducibilityFinding(**record)
        for record in patch.GENERIC_MANIFEST_FINDINGS_CONTRACT
    )
    observed_non_ok = [finding for finding in findings if finding.level != "ok"]
    if not _exact_finding_multiset(observed_non_ok, expected):
        return [
            *findings,
            ReproducibilityFinding(
                "fail",
                "final_calibration_r8_coordination_namespace_revalidation",
                "R-E0-MCALL",
                "E0-MCALL generic manifest findings were not the exact four-finding multiset.",
            ),
        ]
    try:
        validation = patch.validate_final_calibration_r8_coordination_namespace_revalidation_adoption(
            repo_root=repo_root,
            require_staged=True,
        )
    except patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError as exc:
        return [
            *findings,
            ReproducibilityFinding(
                "fail",
                "final_calibration_r8_coordination_namespace_revalidation",
                "R-E0-MCALL",
                str(exc),
            ),
        ]
    if (
        type(validation) is not dict
        or validation.get("gate") != patch.PATCH_GATE
        or validation.get("status")
        != "r8_coordination_namespace_revalidation_adoption_validated"
        or validation.get("r8_output_count") != 8
        or validation.get("calibration_output_count") != 6
        or validation.get("e7_output_count") != 2
        or validation.get("r_lifecycle_state")
        != "both_bundles_completed_unpublished"
        or validation.get("r8_outputs") != list(patch.R8_OUTPUT_CONTRACT)
        or validation.get("expected_non_ok_findings")
        != list(patch.GENERIC_MANIFEST_FINDINGS_CONTRACT)
        or validation.get("coordination_forbidden_count") != 46
        or validation.get("coordination_present_count") != 0
        or validation.get("effective_p_mcall_verified") is not True
        or validation.get("staged_scope_verified") is not True
        or validation.get("scientific_rerun_performed") is not False
        or validation.get("r8_rewrite_performed") is not False
    ):
        return [
            *findings,
            ReproducibilityFinding(
                "fail",
                "final_calibration_r8_coordination_namespace_revalidation",
                "R-E0-MCALL",
                "E0-MCALL strict R8 adoption result drifted.",
            ),
        ]
    adopted = [finding for finding in findings if finding.level == "ok"]
    adopted.append(
        ReproducibilityFinding(
            "ok",
            "final_calibration_r8_coordination_namespace_revalidation",
            "R-E0-MCALL",
            "Adopted the exact two status failures and two script warnings after strict MCALL R8 validation.",
        )
    )
    return adopted


def final_calibration_r8_coordination_namespace_revalidation_checks(
    *,
    staged_status: str,
    selected_dvc_paths: list[Path],
    artifacts: list[DvcArtifact],
    max_manifest_hash_bytes: int,
    verify_manifest_inputs: bool,
    repo_root: Path = Path("."),
) -> list[ReproducibilityFinding]:
    """Run unchanged generic checks, then the exact R-E0-MCALL adapter."""
    generic = reproducibility_checks(
        staged_status=staged_status,
        selected_dvc_paths=selected_dvc_paths,
        artifacts=artifacts,
        max_manifest_hash_bytes=max_manifest_hash_bytes,
        verify_manifest_inputs=verify_manifest_inputs,
    )
    return adopt_final_calibration_r8_coordination_namespace_revalidation_findings(
        generic,
        staged_status=staged_status,
        repo_root=repo_root,
    )


def _expected_anfis_ablation_historical_script_findings(
) -> tuple[ReproducibilityFinding, ReproducibilityFinding]:
    path = ANFIS_ABLATION_REGISTRATION_TRAINER_PATH
    return (
        ReproducibilityFinding(
            "fail",
            "manifest",
            path,
            (
                "script byte count changed: "
                f"manifest={ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_BYTES}, "
                f"current={ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_BYTES}."
            ),
        ),
        ReproducibilityFinding(
            "fail",
            "manifest",
            path,
            (
                "script SHA-256 changed: "
                "manifest="
                f"{ANFIS_ABLATION_REGISTRATION_HISTORICAL_TRAINER_SHA256}, "
                f"current={ANFIS_ABLATION_REGISTRATION_CURRENT_TRAINER_SHA256}."
            ),
        ),
    )


def validate_anfis_ablation_registration_manifest_script_provenance(
    *,
    repo_root: Path = Path("."),
    provenance: Mapping[
        str, AnfisAblationManifestScriptProvenance
    ] = ANFIS_ABLATION_REGISTRATION_MANIFEST_SCRIPT_PROVENANCE,
) -> tuple[AnfisAblationManifestScriptProvenance, ...]:
    """Bind all ten manifest script records to exact historical Git blobs."""
    expected_paths = tuple(ANFIS_ABLATION_MANIFEST_PATHS)
    if (
        not isinstance(provenance, Mapping)
        or len(provenance) != 10
        or set(provenance) != set(expected_paths)
    ):
        raise DeferredDvcTargetError(
            "E0-MZE manifest script provenance must be the exact closed ten-map"
        )

    validated: list[AnfisAblationManifestScriptProvenance] = []
    validated_commits: set[str] = set()
    for manifest_path in expected_paths:
        record = provenance.get(manifest_path)
        expected = ANFIS_ABLATION_REGISTRATION_MANIFEST_SCRIPT_PROVENANCE.get(
            manifest_path
        )
        if (
            type(record) is not AnfisAblationManifestScriptProvenance
            or record != expected
            or record.manifest_path != manifest_path
            or record.script_path != ANFIS_ABLATION_REGISTRATION_TRAINER_PATH
            or record.git_mode != "100644"
            or type(record.bytes) is not int
            or record.bytes < 1
            or len(record.commit) != 40
            or len(record.blob_oid) != 40
            or len(record.sha256) != 64
        ):
            raise DeferredDvcTargetError(
                "E0-MZE manifest script provenance record drifted"
            )
        if record.commit not in validated_commits:
            ancestry = subprocess.run(
                [
                    ANFIS_ABLATION_GIT_BIN.as_posix(),
                    "-C",
                    repo_root.as_posix(),
                    "merge-base",
                    "--is-ancestor",
                    record.commit,
                    ANFIS_ABLATION_REGISTRATION_P_MZD_COMMIT,
                ],
                check=False,
                capture_output=True,
            )
            if ancestry.returncode != 0 or ancestry.stdout or ancestry.stderr:
                raise DeferredDvcTargetError(
                    "E0-MZE manifest trainer commit is not an exact P-MZD ancestor"
                )
            validated_commits.add(record.commit)

        payload_sink: list[bytes] = []
        manifest_identity = _registration_file_identity(
            repo_root / manifest_path,
            repo_root=repo_root,
            mode=0o644,
            _payload_sink=payload_sink,
        )
        if manifest_identity.nlink != 1 or len(payload_sink) != 1:
            raise DeferredDvcTargetError(
                "E0-MZE manifest provenance requires one regular single-link record"
            )
        try:
            manifest = json.loads(payload_sink[0])
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeferredDvcTargetError(
                "E0-MZE manifest provenance record is not valid UTF-8 JSON"
            ) from exc
        expected_script = {
            "role": "trainer",
            "path": record.script_path,
            "bytes": record.bytes,
            "sha256": record.sha256,
        }
        if (
            type(manifest) is not dict
            or type(manifest.get("script")) is not dict
            or set(manifest["script"]) != set(expected_script)
            or manifest["script"] != expected_script
            or type(manifest.get("source_code")) is not list
            or len(manifest["source_code"]) != 1
            or type(manifest["source_code"][0]) is not dict
            or set(manifest["source_code"][0]) != set(expected_script)
            or manifest["source_code"] != [expected_script]
        ):
            raise DeferredDvcTargetError(
                "E0-MZE manifest trainer/source_code records drifted from "
                "exact Git provenance"
            )

        tree = subprocess.run(
            [
                ANFIS_ABLATION_GIT_BIN.as_posix(),
                "-C",
                repo_root.as_posix(),
                "ls-tree",
                record.commit,
                "--",
                record.script_path,
            ],
            check=False,
            capture_output=True,
        )
        expected_tree = (
            f"{record.git_mode} blob {record.blob_oid}\t{record.script_path}\n"
        ).encode("utf-8")
        if tree.returncode != 0 or tree.stderr or tree.stdout != expected_tree:
            raise DeferredDvcTargetError(
                "E0-MZE manifest trainer commit/mode/blob binding drifted"
            )
        blob = subprocess.run(
            [
                ANFIS_ABLATION_GIT_BIN.as_posix(),
                "-C",
                repo_root.as_posix(),
                "cat-file",
                "blob",
                record.blob_oid,
            ],
            check=False,
            capture_output=True,
        )
        if (
            blob.returncode != 0
            or blob.stderr
            or len(blob.stdout) != record.bytes
            or hashlib.sha256(blob.stdout).hexdigest() != record.sha256
        ):
            raise DeferredDvcTargetError(
                "E0-MZE manifest trainer Git blob bytes/hash drifted"
            )
        validated.append(record)
    return tuple(validated)


def adopt_anfis_ablation_registration_manifest_provenance_findings(
    findings: list[ReproducibilityFinding],
    *,
    repo_root: Path = Path("."),
    provenance: Mapping[
        str, AnfisAblationManifestScriptProvenance
    ] = ANFIS_ABLATION_REGISTRATION_MANIFEST_SCRIPT_PROVENANCE,
) -> list[ReproducibilityFinding]:
    """Adopt only the exact two historical failures after closed provenance."""
    expected_failures = _expected_anfis_ablation_historical_script_findings()
    observed_failures = [finding for finding in findings if finding.level == "fail"]
    exact_failure_multiset = (
        len(observed_failures) == len(expected_failures)
        and all(
            observed_failures.count(expected) == 1
            for expected in expected_failures
        )
    )
    non_exact_level = any(
        finding.level != "ok"
        for finding in findings
        if finding.level != "fail"
    )
    try:
        validate_anfis_ablation_registration_manifest_script_provenance(
            repo_root=repo_root,
            provenance=provenance,
        )
    except DeferredDvcTargetError as exc:
        return [
            *findings,
            ReproducibilityFinding(
                "fail",
                "manifest_historical_provenance",
                ANFIS_ABLATION_REGISTRATION_TRAINER_PATH,
                str(exc),
            ),
        ]
    if not exact_failure_multiset or non_exact_level:
        return [
            *findings,
            ReproducibilityFinding(
                "fail",
                "manifest_historical_provenance",
                ANFIS_ABLATION_REGISTRATION_TRAINER_PATH,
                (
                    "E0-MZE generic manifest findings were not the exact two-failure "
                    "historical multiset"
                ),
            ),
        ]

    adopted = [finding for finding in findings if finding.level != "fail"]
    adopted.append(
        ReproducibilityFinding(
            "ok",
            "anfis_ablation_manifest_provenance",
            "reports/closure_v1/02_models/A0/seed_1729_manifest.json",
            "Validated exact one historical and nine current trainer Git blobs.",
        )
    )
    return adopted


def anfis_ablation_registration_reproducibility_checks(
    *,
    staged_status: str,
    selected_dvc_paths: list[Path],
    artifacts: list[DvcArtifact],
    max_manifest_hash_bytes: int,
    verify_manifest_inputs: bool,
    repo_root: Path = Path("."),
) -> list[ReproducibilityFinding]:
    """Run unchanged generic checks, then the exact R-E0-MZE adapter."""
    validate_anfis_ablation_registration_staged_scope(staged_status)
    generic = reproducibility_checks(
        staged_status=staged_status,
        selected_dvc_paths=selected_dvc_paths,
        artifacts=artifacts,
        max_manifest_hash_bytes=max_manifest_hash_bytes,
        verify_manifest_inputs=verify_manifest_inputs,
    )
    return adopt_anfis_ablation_registration_manifest_provenance_findings(
        generic,
        repo_root=repo_root,
    )


def prompt_yes_no(question: str, *, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def print_artifact_table(title: str, artifacts: list[DvcArtifact]) -> None:
    print()
    print(title)
    if not artifacts:
        print("  none")
        return
    for artifact in artifacts:
        print(f"  - {artifact.path} ({artifact.artifact_id}, {artifact.artifact_type})")


def print_path_table(title: str, paths: list[Path]) -> None:
    print()
    print(title)
    if not paths:
        print("  none")
        return
    for path in paths:
        print(f"  - {path}")


def unique_paths(paths: list[Path]) -> list[Path]:
    return sorted(set(paths), key=lambda path: path.as_posix())


def default_report_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_REPORT_DIR / f"pre_commit_artifacts_{timestamp}.md"


def write_report(
    report_path: Path,
    *,
    dry_run: bool,
    selected_dvc_paths: list[Path],
    deferred_dvc_paths: list[Path],
    deferred_snapshot_before: tuple[DeferredDvcFinalSnapshot, ...] | None,
    deferred_snapshot_after: tuple[DeferredDvcFinalSnapshot, ...] | None,
    rejected_unmanaged_paths: list[Path],
    git_status_before: str,
    dvc_status_before: dict[str, Any],
    dvc_status_after: dict[str, Any] | None,
    cloud_status_before: CommandResult | None,
    dvc_add_results: list[CommandResult],
    dvc_push_result: CommandResult | None,
    git_add_result: CommandResult | None,
    publication_check_result: CommandResult | None,
    reproducibility_findings: list[ReproducibilityFinding],
    staged_status: str,
    exclusive: bool = False,
) -> None:
    if not exclusive:
        report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pre-Commit Artifact Preparation Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Dry run: `{dry_run}`",
        "",
        "## Selected DVC Targets",
        "",
    ]
    if selected_dvc_paths:
        lines.extend(f"- `{path.as_posix()}`" for path in selected_dvc_paths)
    else:
        lines.append("- none")

    lines.extend(["", "## Deferred DVC A0 Snapshot", ""])
    if deferred_snapshot_before is None and deferred_snapshot_after is None:
        lines.append("Not applicable.")
    else:
        def snapshot_records(
            records: tuple[DeferredDvcFinalSnapshot, ...] | None,
        ) -> list[dict[str, Any]] | None:
            if records is None:
                return None
            return [
                {
                    "path": record.path,
                    "device": record.device,
                    "inode": record.inode,
                    "mtime_ns": record.mtime_ns,
                    "bytes": record.size,
                    "sha256": record.sha256,
                    "mode": f"{record.mode:04o}",
                    "nlink": record.nlink,
                    "ctime_ns": record.ctime_ns,
                }
                for record in records
            ]

        snapshot_payload = {
            "before": snapshot_records(deferred_snapshot_before),
            "after": snapshot_records(deferred_snapshot_after),
            "identical": deferred_snapshot_before == deferred_snapshot_after,
        }
        lines.extend(
            [
                "```json",
                json.dumps(snapshot_payload, indent=2, sort_keys=True),
                "```",
            ]
        )

    lines.extend(["", "## Deferred DVC Targets (Not Added)", ""])
    if deferred_dvc_paths:
        lines.extend(
            f"- `OK` `{path.as_posix()}`: exact Closure V1 A0/1729 deferral; "
            "real DVC status preserved and no DVC add or push run."
            for path in deferred_dvc_paths
        )
    else:
        lines.append("- none")

    lines.extend(["", "## Rejected Unmanaged Heavy Paths", ""])
    if rejected_unmanaged_paths:
        lines.extend(f"- `{path.as_posix()}`" for path in rejected_unmanaged_paths)
    else:
        lines.append("- none")

    lines.extend(["", "## Git Status Before", "", "```text", git_status_before.rstrip() or "clean", "```"])
    lines.extend(
        [
            "",
            "## DVC Status Before",
            "",
            "```json",
            json.dumps(dvc_status_before, indent=2, sort_keys=True),
            "```",
        ]
    )
    lines.extend(["", "## DVC Status After Staging", ""])
    if dvc_status_after is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                "```json",
                json.dumps(dvc_status_after, indent=2, sort_keys=True),
                "```",
            ]
        )

    lines.extend(["", "## DVC Cloud Status Before Push", ""])
    if cloud_status_before is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                f"Command: `{command_text(cloud_status_before.command)}`",
                "",
                "```text",
                cloud_status_before.stdout.rstrip() or cloud_status_before.stderr.rstrip() or "(no output)",
                "```",
            ]
        )

    lines.extend(["", "## DVC Add Commands", ""])
    if dvc_add_results:
        for result in dvc_add_results:
            lines.extend(
                [
                    f"### `{command_text(result.command)}`",
                    "",
                    f"Exit code: `{result.returncode}`",
                    "",
                    "```text",
                    (result.stdout + result.stderr).rstrip() or "(no output)",
                    "```",
                    "",
                ]
            )
    else:
        lines.append("No DVC add commands were run.")

    lines.extend(["", "## DVC Push", ""])
    if dvc_push_result is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                f"Command: `{command_text(dvc_push_result.command)}`",
                "",
                f"Exit code: `{dvc_push_result.returncode}`",
                "",
                "```text",
                (dvc_push_result.stdout + dvc_push_result.stderr).rstrip() or "(no output)",
                "```",
            ]
        )

    lines.extend(["", "## Git Add", ""])
    if git_add_result is None:
        lines.append("Not run.")
    else:
        lines.extend([f"Command: `{command_text(git_add_result.command)}`", f"Exit code: `{git_add_result.returncode}`"])

    lines.extend(["", "## Publication Check", ""])
    if publication_check_result is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                f"Command: `{command_text(publication_check_result.command)}`",
                "",
                f"Exit code: `{publication_check_result.returncode}`",
                "",
                "```text",
                (publication_check_result.stdout + publication_check_result.stderr).rstrip() or "(no output)",
                "```",
            ]
        )

    lines.extend(["", "## Reproducibility Checks", ""])
    if reproducibility_findings:
        for finding in reproducibility_findings:
            lines.append(
                f"- `{finding.level.upper()}` `{finding.check}` `{finding.path}`: {finding.message}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Staged Status After Preparation", "", "```text", staged_status.rstrip() or "none", "```", ""])
    report_bytes = "\n".join(lines).encode("utf-8")
    if not exclusive:
        report_path.write_bytes(report_bytes)
        return
    if report_path.is_absolute() or report_path.parent != DEFAULT_REPORT_DIR:
        raise DeferredDvcTargetError(
            "Deferred models report must be a default relative path directly under tmp"
        )
    _require_no_symlink_ancestors(report_path, anchor=Path("."))
    parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        parent_fd = os.open(report_path.parent, parent_flags)
    except OSError as exc:
        raise DeferredDvcTargetError("Deferred models report parent cannot be opened safely") from exc
    report_fd = -1
    try:
        opened_parent = os.fstat(parent_fd)
        lexical_parent = report_path.parent.lstat()
        if (
            not stat.S_ISDIR(opened_parent.st_mode)
            or (opened_parent.st_dev, opened_parent.st_ino)
            != (lexical_parent.st_dev, lexical_parent.st_ino)
        ):
            raise DeferredDvcTargetError("Deferred models report parent identity drifted")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            report_fd = os.open(report_path.name, flags, 0o600, dir_fd=parent_fd)
        except FileExistsError as exc:
            raise DeferredDvcTargetError(
                "Refusing to overwrite an existing deferred models report"
            ) from exc
        with os.fdopen(report_fd, "wb", closefd=False) as handle:
            handle.write(report_bytes)
            handle.flush()
            os.fsync(report_fd)
        named = os.stat(report_path.name, dir_fd=parent_fd, follow_symlinks=False)
        opened = os.fstat(report_fd)
        lexical_parent_after = report_path.parent.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_nlink != 1
            or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            or (lexical_parent_after.st_dev, lexical_parent_after.st_ino)
            != (opened_parent.st_dev, opened_parent.st_ino)
        ):
            raise DeferredDvcTargetError("Deferred models report identity drifted")
        os.fsync(parent_fd)
    finally:
        if report_fd >= 0:
            os.close(report_fd)
        os.close(parent_fd)


def _registration_file_identity(
    path: Path,
    *,
    repo_root: Path,
    mode: int,
    _payload_sink: list[bytes] | None = None,
) -> RegistrationFileIdentity:
    """Read one exact named regular file through a single anchored descriptor."""
    _require_no_symlink_ancestors(path, anchor=repo_root)
    parent_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    parent_fd = -1
    file_fd = -1
    try:
        parent_fd = os.open(path.parent, parent_flags)
        opened_parent_before = os.fstat(parent_fd)
        named_parent_before = os.stat(path.parent, follow_symlinks=False)
        file_fd = os.open(path.name, file_flags, dir_fd=parent_fd)
        opened_before = os.fstat(file_fd)
        named_before = os.stat(
            path.name, dir_fd=parent_fd, follow_symlinks=False
        )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        opened_after = os.fstat(file_fd)
        named_after = os.stat(
            path.name, dir_fd=parent_fd, follow_symlinks=False
        )
        opened_parent_after = os.fstat(parent_fd)
        named_parent_after = os.stat(path.parent, follow_symlinks=False)
    except OSError as exc:
        raise DeferredDvcTargetError(
            f"E0-MZE file cannot be read through an anchored descriptor: {path}"
        ) from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if parent_fd >= 0:
            os.close(parent_fd)

    def file_identity(metadata: os.stat_result) -> tuple[int, ...]:
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )

    def directory_identity(metadata: os.stat_result) -> tuple[int, ...]:
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )

    if (
        not stat.S_ISDIR(opened_parent_before.st_mode)
        or directory_identity(opened_parent_before)
        != directory_identity(named_parent_before)
        or directory_identity(opened_parent_before)
        != directory_identity(opened_parent_after)
        or directory_identity(opened_parent_before)
        != directory_identity(named_parent_after)
        or not stat.S_ISREG(opened_before.st_mode)
        or stat.S_IMODE(opened_before.st_mode) != mode
        or file_identity(opened_before) != file_identity(named_before)
        or file_identity(opened_before) != file_identity(opened_after)
        or file_identity(opened_before) != file_identity(named_after)
        or len(payload) != opened_before.st_size
    ):
        raise DeferredDvcTargetError(
            f"E0-MZE file/name/parent identity changed while hashing: {path}"
        )
    if _payload_sink is not None:
        _payload_sink.append(payload)
    digest = hashlib.sha256(payload).hexdigest()
    return RegistrationFileIdentity(
        path=path.relative_to(repo_root).as_posix(),
        device=opened_after.st_dev,
        inode=opened_after.st_ino,
        mode=stat.S_IMODE(opened_after.st_mode),
        nlink=opened_after.st_nlink,
        size=opened_after.st_size,
        sha256=digest,
        mtime_ns=opened_after.st_mtime_ns,
        ctime_ns=opened_after.st_ctime_ns,
    )


def snapshot_anfis_ablation_registration_gitignore(
    *, repo_root: Path = Path(".")
) -> RegistrationFileIdentity:
    """Seal the published ignore entry and its exact E0-MZE Git binding."""
    path = repo_root / ANFIS_ABLATION_REGISTRATION_GITIGNORE
    payload_sink: list[bytes] = []
    identity = _registration_file_identity(
        path,
        repo_root=repo_root,
        mode=0o644,
        _payload_sink=payload_sink,
    )
    payload = payload_sink[0]
    if (
        identity.nlink != 1
        or identity.size != ANFIS_ABLATION_REGISTRATION_GITIGNORE_BYTES
        or identity.sha256 != ANFIS_ABLATION_REGISTRATION_GITIGNORE_SHA256
        or len(payload) != identity.size
        or hashlib.sha256(payload).hexdigest() != identity.sha256
        or not payload.endswith(ANFIS_ABLATION_REGISTRATION_GITIGNORE_ENTRY)
        or payload.splitlines(keepends=True).count(
            ANFIS_ABLATION_REGISTRATION_GITIGNORE_ENTRY
        )
        != 1
    ):
        raise DeferredDvcTargetError(
            "E0-MZE .gitignore is not the exact published single /models entry"
        )
    raw_path = ANFIS_ABLATION_REGISTRATION_GITIGNORE.as_posix()
    expected_index = (
        "100644 "
        f"{ANFIS_ABLATION_REGISTRATION_GITIGNORE_GIT_OID} 0\t{raw_path}"
    )
    observed_index = _git_output(
        repo_root, "ls-files", "-s", "--", raw_path
    ).strip()
    observed_head_oid = _git_output(
        repo_root, "rev-parse", f"HEAD:{raw_path}"
    ).strip()
    observed_worktree_oid = _git_output(
        repo_root, "hash-object", "--no-filters", "--", raw_path
    ).strip()
    if (
        observed_index != expected_index
        or observed_head_oid
        != ANFIS_ABLATION_REGISTRATION_GITIGNORE_GIT_OID
        or observed_worktree_oid
        != ANFIS_ABLATION_REGISTRATION_GITIGNORE_GIT_OID
        or _registration_file_identity(
            path, repo_root=repo_root, mode=0o644
        )
        != identity
    ):
        raise DeferredDvcTargetError(
            "E0-MZE .gitignore Git/OID/physical binding drifted"
        )
    return identity


def _registration_directory_identity(
    path: Path, *, repo_root: Path
) -> RegistrationDirectoryIdentity:
    _require_no_symlink_ancestors(path, anchor=repo_root)
    directory_fd = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        metadata = os.fstat(directory_fd)
        entries = os.listdir(directory_fd)
        after = os.fstat(directory_fd)
    finally:
        os.close(directory_fd)
    if (
        (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )
        != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        or
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_nlink != 2
        or entries
    ):
        raise DeferredDvcTargetError(
            f"E0-MY config isolation directory is not exact empty 0700: {path}"
        )
    return RegistrationDirectoryIdentity(
        path=path.relative_to(repo_root).as_posix(),
        device=after.st_dev,
        inode=after.st_ino,
        mode=stat.S_IMODE(after.st_mode),
        nlink=after.st_nlink,
        entry_count=0,
        mtime_ns=after.st_mtime_ns,
        ctime_ns=after.st_ctime_ns,
    )


def snapshot_anfis_ablation_dvc_configuration(
    *, repo_root: Path = Path(".")
) -> tuple[RegistrationFileIdentity, RegistrationFileIdentity]:
    """Seal exact repo/local DVC config without publishing local contents."""
    for inherited_path in (
        Path("/etc/xdg/dvc/config"),
        ANFIS_ABLATION_EXPECTED_XDG_CONFIG_HOME / "dvc/config",
    ):
        if os.path.lexists(inherited_path):
            raise DeferredDvcTargetError(
                f"E0-MY forbids inherited DVC configuration: {inherited_path}"
            )
    records: list[RegistrationFileIdentity] = []
    for path, expected_bytes, expected_sha256 in (
        (
            ANFIS_ABLATION_REPO_DVC_CONFIG,
            ANFIS_ABLATION_REPO_DVC_CONFIG_BYTES,
            ANFIS_ABLATION_REPO_DVC_CONFIG_SHA256,
        ),
        (
            ANFIS_ABLATION_LOCAL_DVC_CONFIG,
            ANFIS_ABLATION_LOCAL_DVC_CONFIG_BYTES,
            ANFIS_ABLATION_LOCAL_DVC_CONFIG_SHA256,
        ),
    ):
        identity = _registration_file_identity(
            repo_root / path, repo_root=repo_root, mode=0o644
        )
        if (
            identity.nlink != 1
            or identity.size != expected_bytes
            or identity.sha256 != expected_sha256
        ):
            raise DeferredDvcTargetError(
                f"E0-MY DVC configuration drifted: {path}"
            )
        records.append(identity)
    return (records[0], records[1])


def expected_anfis_ablation_dvc_wrapper_bytes(repo_root: Path) -> bytes:
    """Build the exact console-script bytes without embedding a local root."""
    interpreter = (
        repo_root.resolve() / ANFIS_ABLATION_DVC_PYTHON_LINK
    ).as_posix()
    return (
        f"#!{interpreter}\n".encode()
        + ANFIS_ABLATION_DVC_WRAPPER_BODY
    )


def snapshot_anfis_ablation_dvc_runtime(
    *, repo_root: Path = Path(".")
) -> AnfisAblationDvcRuntimeIdentity:
    """Seal the exact DVC wrapper, Python symlink, and final interpreter."""
    if shutil.which("git") != ANFIS_ABLATION_GIT_BIN.as_posix():
        raise DeferredDvcTargetError("E0-MY Git executable resolution drifted")
    wrapper_path = repo_root / ANFIS_ABLATION_DVC_WRAPPER
    expected_wrapper = expected_anfis_ablation_dvc_wrapper_bytes(repo_root)
    wrapper = _registration_file_identity(
        wrapper_path, repo_root=repo_root, mode=0o755
    )
    wrapper_payload = wrapper_path.read_bytes()
    wrapper_after = _registration_file_identity(
        wrapper_path, repo_root=repo_root, mode=0o755
    )
    if (
        wrapper_after != wrapper
        or
        wrapper.nlink != 1
        or wrapper.size != len(expected_wrapper)
        or wrapper.sha256 != hashlib.sha256(expected_wrapper).hexdigest()
        or wrapper_payload != expected_wrapper
    ):
        raise DeferredDvcTargetError("E0-MY DVC wrapper identity drifted")

    link_path = repo_root / ANFIS_ABLATION_DVC_PYTHON_LINK
    _require_no_symlink_ancestors(link_path.parent / "anchor", anchor=repo_root)
    link_before = link_path.lstat()
    link_target = os.readlink(link_path)
    link_after = link_path.lstat()
    if (
        not stat.S_ISLNK(link_before.st_mode)
        or (
            link_before.st_dev,
            link_before.st_ino,
            link_before.st_mode,
            link_before.st_nlink,
            link_before.st_size,
            link_before.st_mtime_ns,
            link_before.st_ctime_ns,
        )
        != (
            link_after.st_dev,
            link_after.st_ino,
            link_after.st_mode,
            link_after.st_nlink,
            link_after.st_size,
            link_after.st_mtime_ns,
            link_after.st_ctime_ns,
        )
        or stat.S_IMODE(link_after.st_mode) != 0o777
        or link_after.st_nlink != 1
        or link_target != ANFIS_ABLATION_DVC_PYTHON_TARGET.as_posix()
    ):
        raise DeferredDvcTargetError("E0-MY DVC Python symlink identity drifted")
    python_link = RegistrationSymlinkIdentity(
        path=ANFIS_ABLATION_DVC_PYTHON_LINK.as_posix(),
        target=link_target,
        device=link_after.st_dev,
        inode=link_after.st_ino,
        mode=stat.S_IMODE(link_after.st_mode),
        nlink=link_after.st_nlink,
        size=link_after.st_size,
        mtime_ns=link_after.st_mtime_ns,
        ctime_ns=link_after.st_ctime_ns,
    )

    target_path = ANFIS_ABLATION_DVC_PYTHON_TARGET
    target_before = target_path.lstat()
    target_digest = sha256_file(target_path)
    target_after = target_path.lstat()
    if (
        not stat.S_ISREG(target_before.st_mode)
        or (
            target_before.st_dev,
            target_before.st_ino,
            target_before.st_mode,
            target_before.st_nlink,
            target_before.st_size,
            target_before.st_mtime_ns,
            target_before.st_ctime_ns,
        )
        != (
            target_after.st_dev,
            target_after.st_ino,
            target_after.st_mode,
            target_after.st_nlink,
            target_after.st_size,
            target_after.st_mtime_ns,
            target_after.st_ctime_ns,
        )
        or stat.S_IMODE(target_after.st_mode) != 0o755
        or target_after.st_nlink != 1
        or target_after.st_size != ANFIS_ABLATION_DVC_PYTHON_BYTES
        or target_digest != ANFIS_ABLATION_DVC_PYTHON_SHA256
    ):
        raise DeferredDvcTargetError("E0-MY DVC Python interpreter drifted")
    python_target = RegistrationFileIdentity(
        path=target_path.as_posix(),
        device=target_after.st_dev,
        inode=target_after.st_ino,
        mode=stat.S_IMODE(target_after.st_mode),
        nlink=target_after.st_nlink,
        size=target_after.st_size,
        sha256=target_digest,
        mtime_ns=target_after.st_mtime_ns,
        ctime_ns=target_after.st_ctime_ns,
    )

    git_path = ANFIS_ABLATION_GIT_BIN
    git_before = git_path.lstat()
    git_digest = sha256_file(git_path)
    git_after = git_path.lstat()
    if (
        not stat.S_ISREG(git_before.st_mode)
        or (
            git_before.st_dev,
            git_before.st_ino,
            git_before.st_mode,
            git_before.st_nlink,
            git_before.st_size,
            git_before.st_mtime_ns,
            git_before.st_ctime_ns,
        )
        != (
            git_after.st_dev,
            git_after.st_ino,
            git_after.st_mode,
            git_after.st_nlink,
            git_after.st_size,
            git_after.st_mtime_ns,
            git_after.st_ctime_ns,
        )
        or stat.S_IMODE(git_after.st_mode) != 0o755
        or git_after.st_nlink != 1
        or git_after.st_size != ANFIS_ABLATION_GIT_BYTES
        or git_digest != ANFIS_ABLATION_GIT_SHA256
    ):
        raise DeferredDvcTargetError("E0-MY Git executable drifted")
    git = RegistrationFileIdentity(
        path=git_path.as_posix(),
        device=git_after.st_dev,
        inode=git_after.st_ino,
        mode=stat.S_IMODE(git_after.st_mode),
        nlink=git_after.st_nlink,
        size=git_after.st_size,
        sha256=git_digest,
        mtime_ns=git_after.st_mtime_ns,
        ctime_ns=git_after.st_ctime_ns,
    )
    if shutil.which("git") != ANFIS_ABLATION_GIT_BIN.as_posix():
        raise DeferredDvcTargetError("E0-MY Git executable resolution drifted")
    return AnfisAblationDvcRuntimeIdentity(
        wrapper=wrapper,
        python_link=python_link,
        python_target=python_target,
        git=git,
    )


def _same_registration_payload_inode(
    observed: RegistrationFileIdentity,
    expected: RegistrationFileIdentity,
) -> bool:
    return (
        observed.device,
        observed.inode,
        observed.mode,
        observed.size,
        observed.sha256,
    ) == (
        expected.device,
        expected.inode,
        expected.mode,
        expected.size,
        expected.sha256,
    )


def _same_registration_exact(
    observed: RegistrationFileIdentity,
    expected: RegistrationFileIdentity,
) -> bool:
    return observed == expected


def _same_registration_physical(
    observed: RegistrationFileIdentity,
    expected: RegistrationFileIdentity,
) -> bool:
    """Compare one inode through two names, excluding only lexical path."""
    return (
        observed.device,
        observed.inode,
        observed.mode,
        observed.nlink,
        observed.size,
        observed.sha256,
        observed.mtime_ns,
        observed.ctime_ns,
    ) == (
        expected.device,
        expected.inode,
        expected.mode,
        expected.nlink,
        expected.size,
        expected.sha256,
        expected.mtime_ns,
        expected.ctime_ns,
    )


def _same_registration_node(
    observed: RegistrationFileIdentity,
    expected: RegistrationFileIdentity,
) -> bool:
    return (observed.device, observed.inode) == (
        expected.device,
        expected.inode,
    )


def _registration_identity_record(
    identity: RegistrationFileIdentity,
) -> dict[str, str | int]:
    return {
        "path": identity.path,
        "device": identity.device,
        "inode": identity.inode,
        "mode": identity.mode,
        "nlink": identity.nlink,
        "size": identity.size,
        "sha256": identity.sha256,
        "mtime_ns": identity.mtime_ns,
        "ctime_ns": identity.ctime_ns,
    }


def _registration_directory_record(
    identity: RegistrationDirectoryIdentity,
) -> dict[str, str | int]:
    return {
        "path": identity.path,
        "device": identity.device,
        "inode": identity.inode,
        "mode": identity.mode,
        "nlink": identity.nlink,
        "entry_count": identity.entry_count,
        "mtime_ns": identity.mtime_ns,
        "ctime_ns": identity.ctime_ns,
    }


def _registration_owned_node(
    path: Path,
    metadata: os.stat_result,
    *,
    repo_root: Path,
    expected_mode: int,
    expected_nlink: int,
    directory: bool,
) -> RegistrationOwnedNode:
    expected_kind = stat.S_ISDIR if directory else stat.S_ISREG
    if (
        not expected_kind(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != expected_mode
        or metadata.st_nlink != expected_nlink
    ):
        raise DeferredDvcTargetError(
            f"E0-MY exclusively created node identity drifted: {path}"
        )
    return RegistrationOwnedNode(
        path=path.relative_to(repo_root).as_posix(),
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=stat.S_IMODE(metadata.st_mode),
        nlink=metadata.st_nlink,
    )


def _registration_owned_file_from_fd(
    path: Path,
    file_fd: int,
    *,
    repo_root: Path,
    expected_mode: int,
    expected_nlink: int = 1,
) -> RegistrationOwnedNode:
    """Capture stable ownership before any payload write can fail."""
    return _registration_owned_node(
        path,
        os.fstat(file_fd),
        repo_root=repo_root,
        expected_mode=expected_mode,
        expected_nlink=expected_nlink,
        directory=False,
    )


def _registration_owned_path_from_dirfd(
    path: Path,
    name: str,
    parent_fd: int,
    *,
    repo_root: Path,
    expected_mode: int,
    expected_nlink: int,
    directory: bool,
) -> RegistrationOwnedNode:
    """Capture a just-created directory or hardlink through its anchored parent."""
    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    return _registration_owned_node(
        path,
        metadata,
        repo_root=repo_root,
        expected_mode=expected_mode,
        expected_nlink=expected_nlink,
        directory=directory,
    )


def _refresh_owned_registration_file(
    path: Path,
    file_fd: int,
    ownership: RegistrationOwnedNode,
    *,
    repo_root: Path,
    mode: int,
) -> RegistrationFileIdentity:
    """Promote a stable creation token to an exact post-write identity."""
    opened = os.fstat(file_fd)
    if (
        not stat.S_ISREG(opened.st_mode)
        or (opened.st_dev, opened.st_ino)
        != (ownership.device, ownership.inode)
        or stat.S_IMODE(opened.st_mode) != ownership.mode
        or opened.st_nlink != ownership.nlink
    ):
        raise DeferredDvcTargetError(
            f"E0-MY exclusively created file descriptor drifted: {path}"
        )
    observed = _registration_file_identity(path, repo_root=repo_root, mode=mode)
    if (
        (observed.device, observed.inode)
        != (ownership.device, ownership.inode)
        or observed.mode != ownership.mode
        or observed.nlink != ownership.nlink
    ):
        raise DeferredDvcTargetError(
            f"E0-MY exclusively created file name was replaced: {path}"
        )
    return observed


def _unlink_owned_registration_node(
    path: Path,
    ownership: RegistrationOwnedNode,
    *,
    repo_root: Path,
    expected_nlink: int | None = None,
) -> None:
    """Unlink a partially initialized owned file without trusting mutable bytes."""
    _require_no_symlink_ancestors(path, anchor=repo_root)
    parent_fd = os.open(
        path.parent,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        named = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(named.st_mode)
            or (named.st_dev, named.st_ino)
            != (ownership.device, ownership.inode)
            or stat.S_IMODE(named.st_mode) != ownership.mode
            or named.st_nlink
            != (
                ownership.nlink
                if expected_nlink is None
                else expected_nlink
            )
        ):
            raise DeferredDvcTargetError(
                f"E0-MY rollback preserved a foreign replacement: {path}"
            )
        os.unlink(path.name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _remove_owned_registration_directory_node(
    path: Path,
    ownership: RegistrationOwnedNode,
    *,
    repo_root: Path,
) -> None:
    """Remove a partially initialized owned directory iff it is still empty."""
    _require_no_symlink_ancestors(path, anchor=repo_root)
    parent_fd = os.open(
        path.parent,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    directory_fd = -1
    try:
        directory_fd = os.open(
            path.name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        observed = os.fstat(directory_fd)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or (observed.st_dev, observed.st_ino)
            != (ownership.device, ownership.inode)
            or stat.S_IMODE(observed.st_mode) != ownership.mode
            or observed.st_nlink != ownership.nlink
            or os.listdir(directory_fd)
        ):
            raise DeferredDvcTargetError(
                f"E0-MY preserved a foreign config isolation directory: {path}"
            )
        os.close(directory_fd)
        directory_fd = -1
        os.rmdir(path.name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    finally:
        if directory_fd >= 0:
            os.close(directory_fd)
        os.close(parent_fd)


def _remove_owned_registration_directory(
    path: Path,
    identity: RegistrationDirectoryIdentity,
    *,
    repo_root: Path,
) -> None:
    _require_no_symlink_ancestors(path, anchor=repo_root)
    parent_fd = os.open(
        path.parent,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    directory_fd = -1
    try:
        directory_fd = os.open(
            path.name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        observed = os.fstat(directory_fd)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or (observed.st_dev, observed.st_ino)
            != (identity.device, identity.inode)
            or stat.S_IMODE(observed.st_mode) != identity.mode
            or observed.st_nlink != identity.nlink
            or observed.st_mtime_ns != identity.mtime_ns
            or observed.st_ctime_ns != identity.ctime_ns
            or os.listdir(directory_fd)
        ):
            raise DeferredDvcTargetError(
                f"E0-MY preserved a foreign config isolation directory: {path}"
            )
        os.close(directory_fd)
        directory_fd = -1
        os.rmdir(path.name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    finally:
        if directory_fd >= 0:
            os.close(directory_fd)
        os.close(parent_fd)


def _unlink_owned_registration_path(
    path: Path,
    identity: RegistrationFileIdentity,
    *,
    repo_root: Path,
    expected_nlink: int | None = None,
) -> None:
    _require_no_symlink_ancestors(path, anchor=repo_root)
    parent = path.parent
    parent_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    parent_fd = os.open(parent, parent_flags)
    try:
        named = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(named.st_mode)
            or (named.st_dev, named.st_ino) != (identity.device, identity.inode)
            or stat.S_IMODE(named.st_mode) != identity.mode
            or named.st_size != identity.size
            or named.st_mtime_ns != identity.mtime_ns
            or named.st_ctime_ns != identity.ctime_ns
            or named.st_nlink
            != (identity.nlink if expected_nlink is None else expected_nlink)
        ):
            raise DeferredDvcTargetError(
                f"E0-MY rollback preserved a foreign replacement: {path}"
            )
        os.unlink(path.name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _overwrite_owned_registration_path(
    path: Path,
    identity: RegistrationFileIdentity,
    payload: bytes,
    *,
    repo_root: Path,
    expected_nlink: int = 1,
) -> RegistrationFileIdentity:
    """Restore bytes only through the exact owned regular inode."""
    _require_no_symlink_ancestors(path, anchor=repo_root)
    parent_fd = os.open(
        path.parent,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    file_fd = -1
    try:
        file_fd = os.open(
            path.name,
            os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        opened = os.fstat(file_fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != identity.mode
            or opened.st_nlink != expected_nlink
            or (opened.st_dev, opened.st_ino)
            != (identity.device, identity.inode)
            or opened.st_size != identity.size
            or opened.st_mtime_ns != identity.mtime_ns
            or opened.st_ctime_ns != identity.ctime_ns
        ):
            raise DeferredDvcTargetError(
                f"E0-MY rollback preserved a foreign overwrite target: {path}"
            )
        os.ftruncate(file_fd, 0)
        written = 0
        while written < len(payload):
            count = os.write(file_fd, payload[written:])
            if count <= 0:
                raise DeferredDvcTargetError(
                    f"Short write restoring E0-MY metadata: {path}"
                )
            written += count
        os.fsync(file_fd)
        os.fsync(parent_fd)
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(parent_fd)
    return _registration_file_identity(path, repo_root=repo_root, mode=identity.mode)


class _AnfisAblationRegistrationTransaction:
    """Own and roll back only metadata created by exact E0-MY registration."""

    def __init__(
        self,
        *,
        repo_root: Path,
        manage_git_index: bool = False,
        expected_gitignore: RegistrationFileIdentity | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.manage_git_index = manage_git_index
        self.expected_gitignore = expected_gitignore
        self.gitignore_identity: RegistrationFileIdentity | None = None
        self.root_fd = -1
        self.tmp_fd = -1
        self.guard_ownership: RegistrationOwnedNode | None = None
        self.guard_identity: RegistrationFileIdentity | None = None
        self.baseline_models: RegistrationFileIdentity | None = None
        self.baseline_models_bytes = b""
        self.backup_ownership: RegistrationOwnedNode | None = None
        self.backup_identity: RegistrationFileIdentity | None = None
        self.bytes_backup_ownership: RegistrationOwnedNode | None = None
        self.bytes_backup_identity: RegistrationFileIdentity | None = None
        self.global_config_ownership: RegistrationOwnedNode | None = None
        self.global_config_identity: RegistrationDirectoryIdentity | None = None
        self.system_config_ownership: RegistrationOwnedNode | None = None
        self.system_config_identity: RegistrationDirectoryIdentity | None = None
        self.pointer_identities: dict[Path, RegistrationFileIdentity] = {}
        self.registered_models: RegistrationFileIdentity | None = None
        self.models_overwritten_in_place = False
        self.models_registration_prepared = False
        self.index_baseline: tuple[str, ...] | None = None
        self.staging_owned = False
        self.staged_owned_paths: tuple[str, ...] = ()
        self.dvc_started = False
        self.committed = False

    def __enter__(self) -> _AnfisAblationRegistrationTransaction:
        tmp_root = self.repo_root / "tmp"
        if not os.path.lexists(tmp_root):
            os.mkdir(tmp_root, 0o700)
        _require_no_symlink_ancestors(tmp_root / "anchor", anchor=self.repo_root)
        if not stat.S_ISDIR(tmp_root.lstat().st_mode):
            raise DeferredDvcTargetError("E0-MY tmp root is not a directory")
        for path in (
            self.repo_root / ANFIS_ABLATION_REGISTRATION_GUARD,
            self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP,
            self.repo_root / ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP,
            self.repo_root / ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR,
            self.repo_root / ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR,
            *(self.repo_root / path for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS),
        ):
            if os.path.lexists(path):
                raise DeferredDvcTargetError(
                    f"E0-MY transaction requires absent coordination/pointer path: {path}"
                )
        self.gitignore_identity = _registration_file_identity(
            self.repo_root / ANFIS_ABLATION_REGISTRATION_GITIGNORE,
            repo_root=self.repo_root,
            mode=0o644,
        )
        if self.gitignore_identity.nlink != 1 or (
            self.expected_gitignore is not None
            and self.gitignore_identity != self.expected_gitignore
        ):
            raise DeferredDvcTargetError(
                "E0-MZE transaction requires the exact sealed .gitignore identity"
            )
        models_pointer = self.repo_root / DEFERRED_DVC_MODELS_POINTER
        self.baseline_models = _registration_file_identity(
            models_pointer, repo_root=self.repo_root, mode=0o644
        )
        if self.baseline_models.nlink != 1:
            raise DeferredDvcTargetError(
                "E0-MY baseline models.dvc must have exactly one hard link"
            )
        self.baseline_models_bytes = models_pointer.read_bytes()
        if (
            len(self.baseline_models_bytes) != self.baseline_models.size
            or hashlib.sha256(self.baseline_models_bytes).hexdigest()
            != self.baseline_models.sha256
            or _registration_file_identity(
                models_pointer, repo_root=self.repo_root, mode=0o644
            )
            != self.baseline_models
        ):
            raise DeferredDvcTargetError(
                "E0-MY baseline models.dvc changed while being captured"
            )
        if self.manage_git_index:
            if _git_output(
                self.repo_root,
                "diff",
                "--cached",
                "--name-only",
            ).strip():
                raise DeferredDvcTargetError(
                    "E0-MY registration requires an initially clean Git index"
                )
            self.index_baseline = tuple(
                _git_output(
                    self.repo_root,
                    "ls-files",
                    "-s",
                    "--",
                    *sorted(ANFIS_ABLATION_R_MZE_STAGED_SCOPE),
                ).splitlines()
            )
            if (
                len(self.index_baseline) != 1
                or not self.index_baseline[0].endswith(" 0\tmodels.dvc")
            ):
                raise DeferredDvcTargetError(
                    "E0-MY initial index is not exact tracked models.dvc only"
                )

        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            self.root_fd = os.open(self.repo_root, directory_flags)
            self.tmp_fd = os.open(tmp_root, directory_flags)
        except BaseException:
            self._close_directory_descriptors()
            raise
        guard_fd = -1
        bytes_backup_fd = -1
        try:
            guard_fd = os.open(
                ANFIS_ABLATION_REGISTRATION_GUARD.name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=self.tmp_fd,
            )
            guard_path = self.repo_root / ANFIS_ABLATION_REGISTRATION_GUARD
            self.guard_ownership = _registration_owned_file_from_fd(
                guard_path,
                guard_fd,
                repo_root=self.repo_root,
                expected_mode=0o600,
            )
            try:
                if os.write(
                    guard_fd, ANFIS_ABLATION_REGISTRATION_ACTIVE_PAYLOAD
                ) != len(ANFIS_ABLATION_REGISTRATION_ACTIVE_PAYLOAD):
                    raise DeferredDvcTargetError(
                        "Short write creating E0-MY guard"
                    )
                os.fsync(guard_fd)
            finally:
                self.guard_identity = _refresh_owned_registration_file(
                    guard_path,
                    guard_fd,
                    self.guard_ownership,
                    repo_root=self.repo_root,
                    mode=0o600,
                )
            if (
                self.guard_identity.size
                != len(ANFIS_ABLATION_REGISTRATION_ACTIVE_PAYLOAD)
                or self.guard_identity.sha256
                != hashlib.sha256(
                    ANFIS_ABLATION_REGISTRATION_ACTIVE_PAYLOAD
                ).hexdigest()
            ):
                raise DeferredDvcTargetError(
                    "E0-MY transaction guard payload drifted during creation"
                )

            for attribute_prefix, directory_path in (
                ("global_config", ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR),
                ("system_config", ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR),
            ):
                try:
                    os.mkdir(directory_path.name, 0o700, dir_fd=self.tmp_fd)
                except BaseException:
                    physical_directory = self.repo_root / directory_path
                    if os.path.lexists(physical_directory):
                        ownership = _registration_owned_path_from_dirfd(
                            physical_directory,
                            directory_path.name,
                            self.tmp_fd,
                            repo_root=self.repo_root,
                            expected_mode=0o700,
                            expected_nlink=2,
                            directory=True,
                        )
                        setattr(
                            self,
                            f"{attribute_prefix}_ownership",
                            ownership,
                        )
                    raise
                ownership = _registration_owned_path_from_dirfd(
                    self.repo_root / directory_path,
                    directory_path.name,
                    self.tmp_fd,
                    repo_root=self.repo_root,
                    expected_mode=0o700,
                    expected_nlink=2,
                    directory=True,
                )
                setattr(self, f"{attribute_prefix}_ownership", ownership)
                identity = _registration_directory_identity(
                    self.repo_root / directory_path,
                    repo_root=self.repo_root,
                )
                setattr(self, f"{attribute_prefix}_identity", identity)

            bytes_backup_fd = os.open(
                ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP.name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=self.tmp_fd,
            )
            bytes_backup_path = (
                self.repo_root / ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP
            )
            self.bytes_backup_ownership = _registration_owned_file_from_fd(
                bytes_backup_path,
                bytes_backup_fd,
                repo_root=self.repo_root,
                expected_mode=0o600,
            )
            try:
                written = 0
                while written < len(self.baseline_models_bytes):
                    count = os.write(
                        bytes_backup_fd, self.baseline_models_bytes[written:]
                    )
                    if count <= 0:
                        raise DeferredDvcTargetError(
                            "Short write creating E0-MY independent "
                            "models.dvc backup"
                        )
                    written += count
                os.fsync(bytes_backup_fd)
            finally:
                self.bytes_backup_identity = _refresh_owned_registration_file(
                    bytes_backup_path,
                    bytes_backup_fd,
                    self.bytes_backup_ownership,
                    repo_root=self.repo_root,
                    mode=0o600,
                )
        except BaseException:
            try:
                self._rollback()
            finally:
                self._close_directory_descriptors()
            raise
        finally:
            if guard_fd >= 0:
                os.close(guard_fd)
            if bytes_backup_fd >= 0:
                os.close(bytes_backup_fd)

        try:
            if (
                self.guard_identity is None
                or self.bytes_backup_identity is None
                or self.global_config_identity is None
                or self.system_config_identity is None
            ):
                raise DeferredDvcTargetError(
                    "E0-MY transaction coordination records are incomplete"
                )
            self._require_bytes_backup()
        except BaseException:
            try:
                self._rollback()
            finally:
                self._close_directory_descriptors()
            raise
        return self

    def _close_directory_descriptors(self) -> None:
        if self.tmp_fd >= 0:
            os.close(self.tmp_fd)
            self.tmp_fd = -1
        if self.root_fd >= 0:
            os.close(self.root_fd)
            self.root_fd = -1

    def _require_gitignore(self) -> RegistrationFileIdentity:
        """Revalidate .gitignore without claiming or rewriting foreign drift."""
        if self.gitignore_identity is None:
            raise DeferredDvcTargetError(
                "E0-MZE transaction .gitignore identity is absent"
            )
        observed = _registration_file_identity(
            self.repo_root / ANFIS_ABLATION_REGISTRATION_GITIGNORE,
            repo_root=self.repo_root,
            mode=0o644,
        )
        if (
            observed.nlink != 1
            or observed != self.gitignore_identity
            or (
                self.expected_gitignore is not None
                and observed != self.expected_gitignore
            )
        ):
            raise DeferredDvcTargetError(
                "E0-MZE .gitignore changed during registration; foreign bytes preserved"
            )
        return observed

    def _require_guard(self) -> RegistrationFileIdentity:
        if self.guard_identity is None:
            raise DeferredDvcTargetError("E0-MY transaction guard is not owned")
        observed = _registration_file_identity(
            self.repo_root / ANFIS_ABLATION_REGISTRATION_GUARD,
            repo_root=self.repo_root,
            mode=0o600,
        )
        if observed.nlink != 1 or not _same_registration_exact(
            observed, self.guard_identity
        ):
            raise DeferredDvcTargetError("E0-MY transaction guard changed")
        return observed

    def _write_guard_state(self, payload: bytes) -> RegistrationFileIdentity:
        """Durably rewrite only the exact owned guard inode and recapture it."""
        current = self._require_guard()
        if self.guard_ownership is None:
            raise DeferredDvcTargetError(
                "E0-MY transaction guard creation ownership is absent"
            )
        guard_path = self.repo_root / ANFIS_ABLATION_REGISTRATION_GUARD
        parent_fd = os.open(
            guard_path.parent,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        guard_fd = -1
        try:
            guard_fd = os.open(
                guard_path.name,
                os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_fd,
            )
            opened = os.fstat(guard_fd)
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino)
                != (current.device, current.inode)
                or stat.S_IMODE(opened.st_mode) != current.mode
                or opened.st_nlink != 1
                or opened.st_size != current.size
                or opened.st_mtime_ns != current.mtime_ns
                or opened.st_ctime_ns != current.ctime_ns
            ):
                raise DeferredDvcTargetError(
                    "E0-MY transaction guard changed before state transition"
                )
            try:
                os.ftruncate(guard_fd, 0)
                written = 0
                while written < len(payload):
                    count = os.write(guard_fd, payload[written:])
                    if count <= 0:
                        raise DeferredDvcTargetError(
                            "Short write transitioning E0-MY transaction guard"
                        )
                    written += count
                os.fsync(guard_fd)
                os.fsync(parent_fd)
            finally:
                self.guard_identity = _refresh_owned_registration_file(
                    guard_path,
                    guard_fd,
                    self.guard_ownership,
                    repo_root=self.repo_root,
                    mode=0o600,
                )
        finally:
            if guard_fd >= 0:
                os.close(guard_fd)
            os.close(parent_fd)
        if (
            self.guard_identity is None
            or self.guard_identity.size != len(payload)
            or self.guard_identity.sha256
            != hashlib.sha256(payload).hexdigest()
        ):
            raise DeferredDvcTargetError(
                "E0-MY transaction guard state transition drifted"
            )
        return self.guard_identity

    def _require_config_isolation(
        self,
    ) -> tuple[RegistrationDirectoryIdentity, RegistrationDirectoryIdentity]:
        if self.global_config_identity is None or self.system_config_identity is None:
            raise DeferredDvcTargetError(
                "E0-MY DVC config-isolation directories are not owned"
            )
        observed_global = _registration_directory_identity(
            self.repo_root / ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR,
            repo_root=self.repo_root,
        )
        observed_system = _registration_directory_identity(
            self.repo_root / ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR,
            repo_root=self.repo_root,
        )
        if (
            observed_global != self.global_config_identity
            or observed_system != self.system_config_identity
        ):
            raise DeferredDvcTargetError(
                "E0-MY DVC config-isolation directory identity drifted"
            )
        return observed_global, observed_system

    def registration_dvc_environment(
        self,
        expected_config: tuple[
            RegistrationFileIdentity, RegistrationFileIdentity
        ],
        expected_runtime: AnfisAblationDvcRuntimeIdentity,
    ) -> dict[str, str]:
        """Revalidate all DVC config layers and return isolated child env."""
        self._require_guard()
        self._require_gitignore()
        self._require_config_isolation()
        if snapshot_anfis_ablation_dvc_configuration(
            repo_root=self.repo_root
        ) != expected_config:
            raise DeferredDvcTargetError(
                "E0-MY repo/local DVC configuration identity drifted"
            )
        if snapshot_anfis_ablation_dvc_runtime(
            repo_root=self.repo_root
        ) != expected_runtime:
            raise DeferredDvcTargetError(
                "E0-MY DVC wrapper/interpreter identity drifted"
            )
        environment = dvc_environment()
        for name in tuple(environment):
            if (
                name.startswith("GIT_")
                or name.startswith("PYTHON")
                or name.startswith("LD_")
                or (
                    name.startswith("DVC_")
                    and name not in {"DVC_NO_ANALYTICS", "DVC_SITE_CACHE_DIR"}
                )
            ):
                environment.pop(name)
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PYTHONSAFEPATH"] = "1"
        environment["PATH"] = "/usr/bin:/bin"
        environment["HOME"] = ANFIS_ABLATION_EXPECTED_HOME.as_posix()
        environment["XDG_CONFIG_HOME"] = (
            ANFIS_ABLATION_EXPECTED_XDG_CONFIG_HOME.as_posix()
        )
        environment["XDG_CONFIG_DIRS"] = ANFIS_ABLATION_EXPECTED_XDG_CONFIG_DIRS
        environment["DVC_GLOBAL_CONFIG_DIR"] = (
            self.repo_root / ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR
        ).resolve().as_posix()
        environment["DVC_SYSTEM_CONFIG_DIR"] = (
            self.repo_root / ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR
        ).resolve().as_posix()
        return environment

    def _require_bytes_backup(self) -> RegistrationFileIdentity:
        if (
            self.baseline_models is None
            or self.bytes_backup_identity is None
            or not self.baseline_models_bytes
        ):
            raise DeferredDvcTargetError(
                "E0-MY independent models.dvc backup is not owned"
            )
        observed = _registration_file_identity(
            self.repo_root / ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP,
            repo_root=self.repo_root,
            mode=0o600,
        )
        if (
            observed.nlink != 1
            or not _same_registration_exact(
                observed, self.bytes_backup_identity
            )
            or observed.size != len(self.baseline_models_bytes)
            or observed.sha256 != self.baseline_models.sha256
        ):
            raise DeferredDvcTargetError(
                "E0-MY independent models.dvc backup identity drifted"
            )
        return observed

    def begin_dvc_mutation(self) -> None:
        """Cross the pre-DVC boundary only with complete durable recovery state."""
        if self.dvc_started:
            return
        self._require_guard()
        self._require_config_isolation()
        self._require_bytes_backup()
        self.dvc_started = True

    def prepare_models_registration(self) -> None:
        """Create the models.dvc recovery anchor only after ten payload adds."""
        if not self.dvc_started or self.models_registration_prepared:
            raise DeferredDvcTargetError(
                "E0-MY models registration boundary is out of order"
            )
        self._require_guard()
        self._require_config_isolation()
        self._require_bytes_backup()
        if self.baseline_models is None or self.root_fd < 0 or self.tmp_fd < 0:
            raise DeferredDvcTargetError(
                "E0-MY models registration baseline/descriptors are absent"
            )
        models_pointer = self.repo_root / DEFERRED_DVC_MODELS_POINTER
        observed_baseline = _registration_file_identity(
            models_pointer, repo_root=self.repo_root, mode=0o644
        )
        if observed_baseline.nlink != 1 or not _same_registration_exact(
            observed_baseline, self.baseline_models
        ):
            raise DeferredDvcTargetError(
                "E0-MY models.dvc changed before its registration boundary"
            )
        backup_path = self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP
        if os.path.lexists(backup_path):
            raise DeferredDvcTargetError(
                "E0-MY models.dvc recovery anchor already exists"
            )
        try:
            os.link(
                DEFERRED_DVC_MODELS_POINTER.as_posix(),
                ANFIS_ABLATION_MODELS_DVC_BACKUP.name,
                src_dir_fd=self.root_fd,
                dst_dir_fd=self.tmp_fd,
                follow_symlinks=False,
            )
            self.backup_ownership = _registration_owned_path_from_dirfd(
                backup_path,
                ANFIS_ABLATION_MODELS_DVC_BACKUP.name,
                self.tmp_fd,
                repo_root=self.repo_root,
                expected_mode=0o644,
                expected_nlink=2,
                directory=False,
            )
            if (
                self.backup_ownership.device,
                self.backup_ownership.inode,
            ) != (
                self.baseline_models.device,
                self.baseline_models.inode,
            ):
                raise DeferredDvcTargetError(
                    "E0-MY hardlink anchor is not the baseline models.dvc inode"
                )
            os.fsync(self.tmp_fd)
            self.backup_identity = _registration_file_identity(
                backup_path,
                repo_root=self.repo_root,
                mode=0o644,
            )
            if not _same_registration_payload_inode(
                self.backup_identity, self.baseline_models
            ):
                raise DeferredDvcTargetError(
                    "E0-MY models.dvc backup is not the baseline inode"
                )
        except BaseException:
            # A wrapper may raise after the kernel completed link(2).  Adopt
            # only the exact baseline inode under the still-active guard.
            if self.backup_ownership is None and os.path.lexists(backup_path):
                candidate = _registration_owned_path_from_dirfd(
                    backup_path,
                    ANFIS_ABLATION_MODELS_DVC_BACKUP.name,
                    self.tmp_fd,
                    repo_root=self.repo_root,
                    expected_mode=0o644,
                    expected_nlink=2,
                    directory=False,
                )
                if (candidate.device, candidate.inode) != (
                    self.baseline_models.device,
                    self.baseline_models.inode,
                ):
                    raise DeferredDvcTargetError(
                        "E0-MY preserved a foreign post-link anchor"
                    )
                self.backup_ownership = candidate
            raise
        self.models_registration_prepared = True

    def capture_target(self, target: Path) -> None:
        """Capture metadata even when the just-finished DVC command failed."""
        self._require_guard()
        if target == DEFERRED_DVC_MODELS_TARGET:
            models_pointer = self.repo_root / DEFERRED_DVC_MODELS_POINTER
            if not os.path.lexists(models_pointer):
                self.registered_models = None
                return
            observed = _registration_file_identity(
                models_pointer, repo_root=self.repo_root, mode=0o644
            )
            if self.baseline_models is None:
                raise DeferredDvcTargetError(
                    "E0-MY baseline models.dvc identity is absent"
                )
            if _same_registration_payload_inode(observed, self.baseline_models):
                self.registered_models = None
                return
            self._require_bytes_backup()
            if _same_registration_node(observed, self.baseline_models):
                if self.models_overwritten_in_place:
                    if (
                        self.registered_models is None
                        or observed.nlink != 1
                        or not _same_registration_exact(
                            observed, self.registered_models
                        )
                    ):
                        raise DeferredDvcTargetError(
                            "E0-MY in-place models.dvc registration drifted"
                        )
                    return
                if observed.nlink != 2 or self.backup_identity is None:
                    raise DeferredDvcTargetError(
                        "E0-MY in-place models.dvc overwrite lost its exact anchor"
                    )
                hardlink_observed = _registration_file_identity(
                    self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP,
                    repo_root=self.repo_root,
                    mode=0o644,
                )
                if (
                    hardlink_observed.nlink != 2
                    or not _same_registration_node(
                        hardlink_observed, self.baseline_models
                    )
                    or not _same_registration_physical(
                        hardlink_observed, observed
                    )
                ):
                    raise DeferredDvcTargetError(
                        "E0-MY in-place models.dvc anchor identity drifted"
                    )
                _unlink_owned_registration_path(
                    self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP,
                    hardlink_observed,
                    repo_root=self.repo_root,
                    expected_nlink=2,
                )
                self.backup_identity = None
                self.backup_ownership = None
                self.models_overwritten_in_place = True
                observed = _registration_file_identity(
                    models_pointer, repo_root=self.repo_root, mode=0o644
                )
            elif self.backup_identity is not None:
                refreshed_anchor = _registration_file_identity(
                    self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP,
                    repo_root=self.repo_root,
                    mode=0o644,
                )
                if (
                    refreshed_anchor.nlink != 1
                    or not _same_registration_payload_inode(
                        refreshed_anchor, self.baseline_models
                    )
                ):
                    raise DeferredDvcTargetError(
                        "E0-MY atomic models.dvc anchor identity drifted"
                    )
                self.backup_identity = refreshed_anchor
            else:
                raise DeferredDvcTargetError(
                    "E0-MY atomic models.dvc registration lost its anchor"
                )
            if observed.nlink != 1:
                raise DeferredDvcTargetError(
                    "E0-MY registered models.dvc must have one hard link"
                )
            self.registered_models = observed
            return
        try:
            index = tuple(Path(path) for path in ANFIS_ABLATION_SELECTION_PREDICTION_PATHS).index(
                target
            )
        except ValueError as exc:
            raise DeferredDvcTargetError(
                f"E0-MY transaction received an unknown DVC target: {target}"
            ) from exc
        pointer = self.repo_root / ANFIS_ABLATION_SELECTION_POINTER_PATHS[index]
        if not os.path.lexists(pointer):
            return
        observed = _registration_file_identity(
            pointer, repo_root=self.repo_root, mode=0o644
        )
        if observed.nlink != 1:
            raise DeferredDvcTargetError(
                f"E0-MY registered DVC pointer must have one hard link: {pointer}"
            )
        previous = self.pointer_identities.get(pointer)
        if previous is not None and not _same_registration_exact(observed, previous):
            raise DeferredDvcTargetError(
                f"E0-MY DVC pointer was replaced after creation: {pointer}"
            )
        self.pointer_identities[pointer] = observed

    def verify_family(
        self,
        expected_pointer_count: int,
        expected_snapshot: tuple[DeferredDvcFinalSnapshot, ...],
    ) -> None:
        self._require_guard()
        if (
            type(expected_pointer_count) is not int
            or not 0 <= expected_pointer_count <= 10
        ):
            raise DeferredDvcTargetError(
                "E0-MY transaction pointer prefix count is invalid"
            )
        expected_pointer_paths = tuple(
            self.repo_root / path
            for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS[
                :expected_pointer_count
            ]
        )
        if set(self.pointer_identities) != set(expected_pointer_paths):
            raise DeferredDvcTargetError(
                "E0-MY transaction does not own the exact pointer prefix"
            )
        for pointer in expected_pointer_paths:
            observed_pointer = _registration_file_identity(
                pointer, repo_root=self.repo_root, mode=0o644
            )
            if not _same_registration_exact(
                observed_pointer, self.pointer_identities[pointer]
            ):
                raise DeferredDvcTargetError(
                    f"E0-MY transaction pointer identity drifted: {pointer}"
                )
        observed = snapshot_anfis_ablation_family_bundle(
            repo_root=self.repo_root,
            expected_pointer_count=expected_pointer_count,
            _allow_in_progress_prefix=True,
        )
        if observed != expected_snapshot:
            raise DeferredDvcTargetError(
                "ANFIS-ablation family changed during E0-MY DVC registration"
            )

    def verify_progress_scope(
        self, *, pointer_count: int, models_registered: bool
    ) -> None:
        self._require_guard()
        self._require_gitignore()
        if (
            type(pointer_count) is not int
            or not 0 <= pointer_count <= 10
            or type(models_registered) is not bool
            or (models_registered and pointer_count != 10)
        ):
            raise DeferredDvcTargetError(
                "E0-MZE registration progress phase is not an exact "
                "pointer-prefix/models-final state"
            )
        expected_scope = {
            path: "??"
            for path in ANFIS_ABLATION_SELECTION_POINTER_PATHS[:pointer_count]
        }
        if models_registered:
            expected_scope[DEFERRED_DVC_MODELS_POINTER.as_posix()] = " M"
        observed_status = _git_output(
            self.repo_root,
            "status",
            "--short",
            "--untracked-files=all",
        )
        self._require_gitignore()
        validate_anfis_ablation_git_short_status_map(
            observed_status,
            expected=expected_scope,
            context=(
                "registration progress scope after "
                f"{pointer_count} pointer target(s)"
            ),
        )

    def capture_staging_owned(self, *, require_complete: bool) -> None:
        """Capture only the exact R paths staged by this transaction."""
        if not self.manage_git_index or self.index_baseline is None:
            raise DeferredDvcTargetError(
                "E0-MY transaction did not capture a Git-index baseline"
            )
        staged_status = _git_output(
            self.repo_root, "diff", "--cached", "--name-status"
        )
        observed = _parse_anfis_ablation_git_name_status_map(
            staged_status, context="registration staged ownership"
        )
        if any(
            ANFIS_ABLATION_R_MZE_STAGED_SCOPE.get(path) != status
            for path, status in observed.items()
        ):
            raise DeferredDvcTargetError(
                "E0-MY Git add produced foreign or malformed staged paths"
            )
        if not observed:
            if require_complete:
                raise DeferredDvcTargetError(
                    "E0-MY Git add did not stage the registration scope"
                )
            return
        self.staging_owned = True
        self.staged_owned_paths = tuple(sorted(observed))
        if require_complete:
            validate_anfis_ablation_registration_staged_scope(staged_status)

    def mark_staging_owned(self) -> None:
        self.capture_staging_owned(require_complete=True)

    def _verify_registered_metadata(self) -> None:
        if len(self.pointer_identities) != 10 or self.registered_models is None:
            raise DeferredDvcTargetError(
                "E0-MY transaction has incomplete registered metadata"
            )
        for pointer, expected in self.pointer_identities.items():
            observed = _registration_file_identity(
                pointer, repo_root=self.repo_root, mode=0o644
            )
            if observed.nlink != 1 or not _same_registration_exact(
                observed, expected
            ):
                raise DeferredDvcTargetError(
                    f"E0-MY registered DVC pointer identity drifted: {pointer}"
                )
        observed_models = _registration_file_identity(
            self.repo_root / DEFERRED_DVC_MODELS_POINTER,
            repo_root=self.repo_root,
            mode=0o644,
        )
        if observed_models.nlink != 1 or not _same_registration_exact(
            observed_models, self.registered_models
        ):
            raise DeferredDvcTargetError(
                "E0-MY registered models.dvc identity drifted"
            )

    def _require_baseline_backup(
        self, *, allowed_nlinks: frozenset[int]
    ) -> RegistrationFileIdentity:
        if self.baseline_models is None or self.backup_identity is None:
            raise DeferredDvcTargetError(
                "E0-MY baseline models.dvc backup is not owned"
            )
        observed = _registration_file_identity(
            self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP,
            repo_root=self.repo_root,
            mode=0o644,
        )
        if (
            observed.nlink not in allowed_nlinks
            or not _same_registration_payload_inode(
                observed, self.baseline_models
            )
            or not _same_registration_exact(observed, self.backup_identity)
        ):
            raise DeferredDvcTargetError(
                "E0-MY baseline models.dvc backup identity drifted"
            )
        return observed

    def effective_audit_record(
        self,
    ) -> dict[
        str,
        str | dict[str, str | int] | None,
    ]:
        """Seal the exact live coordination identities for the post-R loader."""
        guard = self._require_guard()
        self._verify_registered_metadata()
        bytes_backup = self._require_bytes_backup()
        global_config, system_config = self._require_config_isolation()
        if self.models_overwritten_in_place:
            if self.backup_identity is not None or os.path.lexists(
                self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP
            ):
                raise DeferredDvcTargetError(
                    "E0-MY in-place audit retained its hardlink anchor"
                )
            anchor: RegistrationFileIdentity | None = None
            mode = "in_place"
        else:
            anchor = self._require_baseline_backup(
                allowed_nlinks=frozenset({1})
            )
            mode = "atomic_replace"
        gitignore = self._require_gitignore()
        return {
            "mode": mode,
            "guard": _registration_identity_record(guard),
            "bytes_backup": _registration_identity_record(bytes_backup),
            "anchor": (
                None if anchor is None else _registration_identity_record(anchor)
            ),
            "global_config_dir": _registration_directory_record(global_config),
            "system_config_dir": _registration_directory_record(system_config),
            "gitignore": _registration_identity_record(gitignore),
        }

    def commit(self) -> None:
        """Linearize R durably, then remove recovery metadata with guard last."""
        self._require_guard()
        self._require_gitignore()
        if not self.dvc_started or not self.models_registration_prepared:
            raise DeferredDvcTargetError(
                "E0-MY cannot commit before the models registration boundary"
            )
        self._verify_registered_metadata()
        self._require_bytes_backup()
        if self.models_overwritten_in_place:
            if self.backup_identity is not None or os.path.lexists(
                self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP
            ):
                raise DeferredDvcTargetError(
                    "E0-MY in-place registration retained its hardlink anchor"
                )
        else:
            self._require_baseline_backup(allowed_nlinks=frozenset({1}))
        if self.manage_git_index:
            self.capture_staging_owned(require_complete=True)
        self._require_config_isolation()
        if (
            self.guard_identity is None
            or self.bytes_backup_identity is None
            or self.global_config_identity is None
            or self.system_config_identity is None
        ):
            raise DeferredDvcTargetError(
                "E0-MY transaction ownership records are incomplete"
            )

        # This file+directory fsync is the commit linearization point.  Before
        # it, every exception rolls R back.  After it, R remains complete and
        # only recognizable coordination cleanup may still be pending.
        self._write_guard_state(
            ANFIS_ABLATION_REGISTRATION_COMMIT_READY_PAYLOAD
        )
        self.committed = True

        _unlink_owned_registration_path(
            self.repo_root / ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP,
            self.bytes_backup_identity,
            repo_root=self.repo_root,
        )
        self.bytes_backup_identity = None
        self.bytes_backup_ownership = None
        if not self.models_overwritten_in_place:
            if self.backup_identity is None:
                raise DeferredDvcTargetError(
                    "E0-MY atomic registration lost its hardlink anchor"
                )
            _unlink_owned_registration_path(
                self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP,
                self.backup_identity,
                repo_root=self.repo_root,
                expected_nlink=1,
            )
            self.backup_identity = None
            self.backup_ownership = None
        _remove_owned_registration_directory(
            self.repo_root / ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR,
            self.global_config_identity,
            repo_root=self.repo_root,
        )
        self.global_config_identity = None
        self.global_config_ownership = None
        _remove_owned_registration_directory(
            self.repo_root / ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR,
            self.system_config_identity,
            repo_root=self.repo_root,
        )
        self.system_config_identity = None
        self.system_config_ownership = None
        if self.guard_identity is None:
            raise DeferredDvcTargetError(
                "E0-MY commit-ready guard identity is absent"
            )
        _unlink_owned_registration_path(
            self.repo_root / ANFIS_ABLATION_REGISTRATION_GUARD,
            self.guard_identity,
            repo_root=self.repo_root,
        )
        self.guard_identity = None
        self.guard_ownership = None
        self._require_gitignore()

    def _rollback(self) -> None:
        errors: list[Exception] = []
        try:
            self._require_gitignore()
        except Exception as exc:
            errors.append(exc)
        if self.manage_git_index and not self.staging_owned:
            try:
                # DVC may be configured to autostage, or ``git add`` may fail
                # after writing only a prefix.  The initial index was sealed
                # clean, so any exact R subset is transaction-owned.
                self.capture_staging_owned(require_complete=False)
            except Exception as exc:
                errors.append(exc)
        if self.staging_owned:
            try:
                staged_status = _git_output(
                    self.repo_root, "diff", "--cached", "--name-status"
                )
                observed = _parse_anfis_ablation_git_name_status_map(
                    staged_status, context="registration rollback staged ownership"
                )
                expected_owned = {
                    path: ANFIS_ABLATION_R_MZE_STAGED_SCOPE[path]
                    for path in self.staged_owned_paths
                }
                if (
                    not expected_owned
                    or observed != expected_owned
                ):
                    raise DeferredDvcTargetError(
                        "E0-MY rollback preserved foreign staged paths"
                    )
                reset_result = run_command(
                    [
                        "git",
                        "-C",
                        self.repo_root.as_posix(),
                        "reset",
                        "--quiet",
                        "HEAD",
                        "--",
                        *self.staged_owned_paths,
                    ],
                    check=False,
                )
                if reset_result.returncode != 0:
                    raise DeferredDvcTargetError(
                        "E0-MY exact Git-index rollback command failed"
                    )
                observed_index = tuple(
                    _git_output(
                        self.repo_root,
                        "ls-files",
                        "-s",
                        "--",
                        *sorted(ANFIS_ABLATION_R_MZE_STAGED_SCOPE),
                    ).splitlines()
                )
                if observed_index != self.index_baseline or _git_output(
                    self.repo_root, "diff", "--cached", "--name-only"
                ).strip():
                    raise DeferredDvcTargetError(
                        "E0-MY Git index did not return to its exact baseline"
                    )
                self.staging_owned = False
                self.staged_owned_paths = ()
            except Exception as exc:
                errors.append(exc)
        for pointer, identity in reversed(tuple(self.pointer_identities.items())):
            try:
                if os.path.lexists(pointer):
                    _unlink_owned_registration_path(
                        pointer, identity, repo_root=self.repo_root
                    )
            except Exception as exc:
                errors.append(exc)

        models_pointer = self.repo_root / DEFERRED_DVC_MODELS_POINTER
        if self.baseline_models is not None:
            try:
                if not self.models_registration_prepared:
                    backup = self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP
                    if os.path.lexists(backup):
                        observed_models = _registration_file_identity(
                            models_pointer,
                            repo_root=self.repo_root,
                            mode=0o644,
                        )
                        if (
                            observed_models.nlink != 2
                            or not _same_registration_payload_inode(
                                observed_models, self.baseline_models
                            )
                        ):
                            raise DeferredDvcTargetError(
                                "E0-MY pre-model rollback found models.dvc drift"
                            )
                        if self.backup_identity is not None:
                            observed_backup = _registration_file_identity(
                                backup, repo_root=self.repo_root, mode=0o644
                            )
                            if not _same_registration_node(
                                observed_backup, self.baseline_models
                            ):
                                raise DeferredDvcTargetError(
                                    "E0-MY pre-model anchor inode drifted"
                                )
                            _unlink_owned_registration_path(
                                backup,
                                observed_backup,
                                repo_root=self.repo_root,
                                expected_nlink=2,
                            )
                        elif self.backup_ownership is not None:
                            _unlink_owned_registration_node(
                                backup,
                                self.backup_ownership,
                                repo_root=self.repo_root,
                                expected_nlink=2,
                            )
                        else:
                            raise DeferredDvcTargetError(
                                "E0-MY pre-model rollback preserved an unowned anchor"
                            )
                        self.backup_identity = None
                        self.backup_ownership = None
                    restored_baseline = _registration_file_identity(
                        models_pointer,
                        repo_root=self.repo_root,
                        mode=0o644,
                    )
                    if (
                        restored_baseline.nlink != 1
                        or not _same_registration_payload_inode(
                            restored_baseline, self.baseline_models
                        )
                    ):
                        raise DeferredDvcTargetError(
                            "E0-MY pre-model rollback did not restore models.dvc"
                        )
                elif self.models_overwritten_in_place:
                    self._require_bytes_backup()
                    if self.backup_identity is not None or os.path.lexists(
                        self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP
                    ):
                        raise DeferredDvcTargetError(
                            "E0-MY in-place rollback found a foreign hardlink anchor"
                        )
                    if self.registered_models is None:
                        raise DeferredDvcTargetError(
                            "E0-MY in-place rollback lacks registered ownership"
                        )
                    observed = _registration_file_identity(
                        models_pointer, repo_root=self.repo_root, mode=0o644
                    )
                    if (
                        observed.nlink != 1
                        or not _same_registration_exact(
                            observed, self.registered_models
                        )
                        or not _same_registration_node(
                            observed, self.baseline_models
                        )
                    ):
                        raise DeferredDvcTargetError(
                            "E0-MY in-place rollback preserved foreign models.dvc"
                        )
                    restored = _overwrite_owned_registration_path(
                        models_pointer,
                        self.registered_models,
                        self.baseline_models_bytes,
                        repo_root=self.repo_root,
                    )
                    if (
                        restored.nlink != 1
                        or not _same_registration_payload_inode(
                            restored, self.baseline_models
                        )
                    ):
                        raise DeferredDvcTargetError(
                            "E0-MY in-place models.dvc restoration drifted"
                        )
                elif self.backup_identity is not None:
                    backup = self.repo_root / ANFIS_ABLATION_MODELS_DVC_BACKUP
                    if not os.path.lexists(backup):
                        raise DeferredDvcTargetError(
                            "E0-MY atomic rollback lost its hardlink anchor"
                        )
                    hardlink_observed = _registration_file_identity(
                        backup, repo_root=self.repo_root, mode=0o644
                    )
                    if not _same_registration_node(
                        hardlink_observed, self.baseline_models
                    ):
                        raise DeferredDvcTargetError(
                            "E0-MY hardlink anchor inode drifted"
                        )
                    if os.path.lexists(models_pointer):
                        observed = _registration_file_identity(
                            models_pointer,
                            repo_root=self.repo_root,
                            mode=0o644,
                        )
                        if _same_registration_node(
                            observed, self.baseline_models
                        ):
                            if observed.nlink != 2:
                                raise DeferredDvcTargetError(
                                    "E0-MY baseline hardlink count drifted"
                                )
                            if not _same_registration_payload_inode(
                                observed, self.baseline_models
                            ):
                                self._require_bytes_backup()
                                observed = _overwrite_owned_registration_path(
                                    models_pointer,
                                    observed,
                                    self.baseline_models_bytes,
                                    repo_root=self.repo_root,
                                    expected_nlink=2,
                                )
                                if not _same_registration_payload_inode(
                                    observed, self.baseline_models
                                ):
                                    raise DeferredDvcTargetError(
                                        "E0-MY anchored models.dvc restoration drifted"
                                    )
                        elif (
                            self.registered_models is not None
                            and _same_registration_exact(
                                observed, self.registered_models
                            )
                        ):
                            _unlink_owned_registration_path(
                                models_pointer,
                                self.registered_models,
                                repo_root=self.repo_root,
                            )
                        else:
                            raise DeferredDvcTargetError(
                                "E0-MY rollback preserved a foreign models.dvc replacement"
                            )
                    if not os.path.lexists(models_pointer):
                        if self.root_fd < 0 or self.tmp_fd < 0:
                            raise DeferredDvcTargetError(
                                "E0-MY rollback lost anchored directory descriptors"
                            )
                        os.link(
                            ANFIS_ABLATION_MODELS_DVC_BACKUP.name,
                            DEFERRED_DVC_MODELS_POINTER.as_posix(),
                            src_dir_fd=self.tmp_fd,
                            dst_dir_fd=self.root_fd,
                            follow_symlinks=False,
                        )
                        os.fsync(self.root_fd)
                    restored = _registration_file_identity(
                        models_pointer, repo_root=self.repo_root, mode=0o644
                    )
                    if (
                        restored.nlink != 2
                        or not _same_registration_payload_inode(
                            restored, self.baseline_models
                        )
                    ):
                        raise DeferredDvcTargetError(
                            "E0-MY atomic models.dvc restoration drifted"
                        )
                    refreshed_anchor = _registration_file_identity(
                        backup, repo_root=self.repo_root, mode=0o644
                    )
                    if (
                        not _same_registration_node(
                            refreshed_anchor, self.backup_identity
                        )
                        or not _same_registration_physical(
                            refreshed_anchor, restored
                        )
                    ):
                        raise DeferredDvcTargetError(
                            "E0-MY restored hardlink anchor identity drifted"
                        )
                    _unlink_owned_registration_path(
                        backup,
                        refreshed_anchor,
                        repo_root=self.repo_root,
                        expected_nlink=2,
                    )
                    self.backup_identity = None
                    self.backup_ownership = None
                else:
                    raise DeferredDvcTargetError(
                        "E0-MY rollback has no models.dvc restoration strategy"
                    )
            except Exception as exc:
                errors.append(exc)

        if (
            self.bytes_backup_identity is not None
            or self.bytes_backup_ownership is not None
        ):
            bytes_backup = (
                self.repo_root / ANFIS_ABLATION_MODELS_DVC_BYTES_BACKUP
            )
            try:
                if os.path.lexists(bytes_backup):
                    if self.bytes_backup_identity is not None:
                        if self.dvc_started:
                            self._require_bytes_backup()
                        _unlink_owned_registration_path(
                            bytes_backup,
                            self.bytes_backup_identity,
                            repo_root=self.repo_root,
                        )
                    elif self.bytes_backup_ownership is not None:
                        _unlink_owned_registration_node(
                            bytes_backup,
                            self.bytes_backup_ownership,
                            repo_root=self.repo_root,
                        )
                self.bytes_backup_identity = None
                self.bytes_backup_ownership = None
            except Exception as exc:
                errors.append(exc)
        for identity_attribute, ownership_attribute, directory_path in (
            (
                "global_config_identity",
                "global_config_ownership",
                ANFIS_ABLATION_DVC_GLOBAL_CONFIG_DIR,
            ),
            (
                "system_config_identity",
                "system_config_ownership",
                ANFIS_ABLATION_DVC_SYSTEM_CONFIG_DIR,
            ),
        ):
            identity = getattr(self, identity_attribute)
            ownership = getattr(self, ownership_attribute)
            if identity is None and ownership is None:
                continue
            try:
                path = self.repo_root / directory_path
                if os.path.lexists(path):
                    if identity is not None:
                        _remove_owned_registration_directory(
                            path, identity, repo_root=self.repo_root
                        )
                    elif ownership is not None:
                        _remove_owned_registration_directory_node(
                            path, ownership, repo_root=self.repo_root
                        )
                setattr(self, identity_attribute, None)
                setattr(self, ownership_attribute, None)
            except Exception as exc:
                errors.append(exc)
        if self.guard_identity is not None or self.guard_ownership is not None:
            guard = self.repo_root / ANFIS_ABLATION_REGISTRATION_GUARD
            try:
                if os.path.lexists(guard):
                    if self.guard_identity is not None:
                        _unlink_owned_registration_path(
                            guard,
                            self.guard_identity,
                            repo_root=self.repo_root,
                        )
                    elif self.guard_ownership is not None:
                        _unlink_owned_registration_node(
                            guard,
                            self.guard_ownership,
                            repo_root=self.repo_root,
                        )
                self.guard_identity = None
                self.guard_ownership = None
            except Exception as exc:
                errors.append(exc)
        if self.manage_git_index:
            try:
                self._require_gitignore()
                final_status = _git_output(
                    self.repo_root,
                    "status",
                    "--short",
                    "--untracked-files=all",
                )
                validate_anfis_ablation_registration_initial_scope(final_status)
                if _git_output(
                    self.repo_root, "diff", "--cached", "--name-only"
                ).strip():
                    raise DeferredDvcTargetError(
                        "E0-MY rollback left the Git index staged"
                    )
            except Exception as exc:
                errors.append(exc)
        if errors:
            cleanup = DeferredDvcTargetError(
                "E0-MY registration rollback could not be completed safely"
            )
            cleanup.add_note(
                "; ".join(f"{type(exc).__name__}: {exc}" for exc in errors)
            )
            raise cleanup from errors[0]

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        del exc_type, traceback
        active_error = exc
        try:
            if not self.committed:
                self._rollback()
        except Exception as cleanup_error:
            if active_error is not None:
                raise cleanup_error from active_error
            raise
        finally:
            self._close_directory_descriptors()
        return False


def validate_anfis_ablation_registration_invocation(
    args: Any, *, env: Mapping[str, str] | None = None
) -> None:
    """Close the E0-MZE helper CLI before authority or DVC inspection."""
    source = os.environ if env is None else env
    redirected_git_names = {
        name
        for name in source
        if name.startswith("GIT_")
    }
    redirected_dvc_names = {
        name
        for name in source
        if name.startswith("DVC_")
        and name not in {"DVC_NO_ANALYTICS", "DVC_SITE_CACHE_DIR"}
    }
    redirected_runtime_names = {
        name
        for name in source
        if name.startswith("PYTHON") or name.startswith("LD_")
    }
    host_config_environment_is_exact = (
        source.get("HOME") in {None, ANFIS_ABLATION_EXPECTED_HOME.as_posix()}
        and source.get("XDG_CONFIG_HOME")
        in {None, ANFIS_ABLATION_EXPECTED_XDG_CONFIG_HOME.as_posix()}
        and source.get("XDG_CONFIG_DIRS")
        in {None, ANFIS_ABLATION_EXPECTED_XDG_CONFIG_DIRS}
    )
    dvc_site_cache = source.get("DVC_SITE_CACHE_DIR")
    resolved_git = shutil.which("git", path=source.get("PATH"))
    if (
        not args.register_anfis_ablation_model_family
        or args.allow_unmanaged
        or not args.no_push
        or args.yes
        or args.dry_run
        or args.skip_publication_check
        or args.jobs is not None
        or args.dvc_bin is not None
        or args.manifest != DEFAULT_DVC_MANIFEST
        or args.report is not None
        or args.target
        or args.defer_dvc_target
        or "DVC_BIN" in source
        or source.get("DVC_NO_ANALYTICS") != "1"
        or redirected_git_names
        or redirected_dvc_names
        or redirected_runtime_names
        or resolved_git != ANFIS_ABLATION_GIT_BIN.as_posix()
        or not host_config_environment_is_exact
        or (
            dvc_site_cache is not None
            and dvc_site_cache != DEFAULT_DVC_SITE_CACHE_DIR.as_posix()
        )
    ):
        raise DeferredDvcTargetError(
            "E0-MZE registration requires only --no-push "
            "--register-anfis-ablation-model-family, default Git/DVC state, "
            "DVC_NO_ANALYTICS=1, and no custom targets, reports, or binaries"
        )


def _load_effective_anfis_ablation_dvc_registration_authority(
    *,
    audit_current_unpublished: bool,
    repo_root: Path,
    registration_transaction: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Lazy import keeps the generic helper independent before H-E0-MZE exists."""
    from src.experiments.closure_anfis_ablation_dvc_registration_reproducibility_patch import (
        load_effective_anfis_ablation_dvc_registration_reproducibility_patch_authority,
    )

    if registration_transaction is None:
        authority = (
            load_effective_anfis_ablation_dvc_registration_reproducibility_patch_authority(
                audit_current_unpublished=audit_current_unpublished,
                verify_remote=True,
                repo_root=repo_root,
            )
        )
    else:
        from src.experiments.closure_anfis_ablation_dvc_registration_reproducibility_patch import (
            _load_effective_anfis_ablation_dvc_registration_reproducibility_patch_during_registration,
        )

        if not audit_current_unpublished:
            raise DeferredDvcTargetError(
                "E0-MZE transaction record is valid only for post-registration audit"
            )
        authority = (
            _load_effective_anfis_ablation_dvc_registration_reproducibility_patch_during_registration(
                transaction_record=registration_transaction,
                verify_remote=True,
                repo_root=repo_root,
            )
        )
    if not isinstance(authority, Mapping):
        raise DeferredDvcTargetError(
            "Effective E0-MZE loader returned a non-mapping authority"
        )
    return authority


def _anfis_ablation_registration_user_message(value: BaseException) -> str:
    message = str(value)
    active_marker = "__E0_MZE_ACTIVE_GATE__"
    return (
        message.replace("E0-MZE", active_marker)
        .replace("E0-MZD", active_marker)
        .replace("E0-MZC", active_marker)
        .replace("E0-MZB", active_marker)
        .replace("E0-MZA", active_marker)
        .replace("E0-MZ", active_marker)
        .replace("E0-MY", active_marker)
        .replace(active_marker, "E0-MZE")
    )


def _abort_anfis_ablation_registration_transaction(
    transaction: _AnfisAblationRegistrationTransaction,
    error: BaseException,
    *,
    returncode: int = 2,
) -> int:
    try:
        transaction.__exit__(type(error), error, error.__traceback__)
    except Exception as cleanup_error:
        print(_anfis_ablation_registration_user_message(cleanup_error), file=sys.stderr)
        return 2
    print(_anfis_ablation_registration_user_message(error), file=sys.stderr)
    return returncode


def _run_anfis_ablation_model_family_registration(args: Any) -> int:
    """Register the adopted family, never push, and stage exact R-E0-MZE."""
    try:
        validate_anfis_ablation_registration_invocation(args)
    except DeferredDvcTargetError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    repo_root = Path(".")
    report_path = default_report_path()
    dvc_bin = resolve_dvc_bin(args.dvc_bin)
    if dvc_bin != DEFAULT_DVC_BIN.as_posix():
        print(
            "E0-MZE registration requires the repository .venv/bin/dvc.",
            file=sys.stderr,
        )
        return 2
    try:
        dvc_runtime_snapshot = snapshot_anfis_ablation_dvc_runtime(
            repo_root=repo_root
        )
        gitignore_snapshot = snapshot_anfis_ablation_registration_gitignore(
            repo_root=repo_root
        )
        registration_artifacts = load_anfis_ablation_registration_artifacts()
        configured_artifacts = load_configured_dvc_artifacts(args.manifest)
        model_records = [
            artifact
            for artifact in configured_artifacts
            if artifact.dvc and artifact.path == DEFERRED_DVC_MODELS_TARGET
        ]
        if len(model_records) != 1:
            raise DeferredDvcTargetError(
                "E0-MZE requires one exact configured monolithic models target"
            )
        artifacts = [*configured_artifacts, *registration_artifacts]
        git_status_before = _git_output(
            repo_root, "status", "--short", "--untracked-files=all"
        )
        if (
            snapshot_anfis_ablation_registration_gitignore(repo_root=repo_root)
            != gitignore_snapshot
        ):
            raise DeferredDvcTargetError(
                "E0-MZE .gitignore changed during initial Git-status capture"
            )
        validate_anfis_ablation_registration_initial_scope(git_status_before)
        dvc_config_snapshot = snapshot_anfis_ablation_dvc_configuration(
            repo_root=repo_root
        )
        missing = declared_artifacts_missing_pointers(artifacts)
        validate_anfis_ablation_registration_missing_pointer_set(missing)
        family_snapshot = (
            validate_deferred_dvc_anfis_ablation_adoption_family_state(
                DEFERRED_DVC_MODELS_STATUS, repo_root=repo_root
            )
        )
        _load_effective_anfis_ablation_dvc_registration_authority(
            audit_current_unpublished=False, repo_root=repo_root
        )
        if (
            snapshot_anfis_ablation_registration_gitignore(repo_root=repo_root)
            != gitignore_snapshot
        ):
            raise DeferredDvcTargetError(
                "E0-MZE .gitignore changed during effective preflight"
            )
    except (DeferredDvcTargetError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    unmanaged_paths = [
        path
        for path in unmanaged_ignored_heavy_paths(artifacts)
        if path != ANFIS_ABLATION_SELECTION_ROOT
    ]
    selected_dvc_paths = list(ANFIS_ABLATION_REGISTRATION_DVC_TARGETS)
    print("Pre-commit artifact assistant — exact E0-MZE registration")
    print_path_table("Selected DVC add targets:", selected_dvc_paths)
    print_path_table("Rejected unrelated unmanaged ignored paths:", unmanaged_paths)

    try:
        if snapshot_anfis_ablation_dvc_runtime(
            repo_root=repo_root
        ) != dvc_runtime_snapshot:
            raise DeferredDvcTargetError(
                "E0-MZE Git/DVC runtime changed during preflight"
            )
    except DeferredDvcTargetError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    transaction = _AnfisAblationRegistrationTransaction(
        repo_root=repo_root,
        manage_git_index=True,
        expected_gitignore=gitignore_snapshot,
    )
    try:
        transaction.__enter__()
    except BaseException as exc:
        print(
            _anfis_ablation_registration_user_message(exc),
            file=sys.stderr,
        )
        return 2
    try:
        registration_dvc_env = transaction.registration_dvc_environment(
            dvc_config_snapshot, dvc_runtime_snapshot
        )
        dvc_status_before = dvc_status_json(
            dvc_bin, env=registration_dvc_env
        )
        transaction.registration_dvc_environment(
            dvc_config_snapshot, dvc_runtime_snapshot
        )
        changed = dvc_status_candidates(dvc_status_before, artifacts)
        if [artifact.path for artifact in changed] != [
            DEFERRED_DVC_MODELS_TARGET
        ]:
            raise DeferredDvcTargetError(
                "E0-MZE pre-registration DVC status must select only models"
            )
        validate_deferred_dvc_anfis_ablation_adoption_family_state(
            dvc_status_before,
            repo_root=repo_root,
            expected_final_snapshot=family_snapshot,
        )
    except BaseException as exc:
        return _abort_anfis_ablation_registration_transaction(transaction, exc)

    dvc_add_results: list[CommandResult] = []
    for target_index, path in enumerate(selected_dvc_paths):
        if not path.exists():
            return _abort_anfis_ablation_registration_transaction(
                transaction,
                DeferredDvcTargetError(
                    f"Selected E0-MZE DVC target does not exist: {path}"
                ),
            )
        if path == DEFERRED_DVC_MODELS_TARGET:
            try:
                transaction.prepare_models_registration()
            except BaseException as exc:
                return _abort_anfis_ablation_registration_transaction(
                    transaction, exc
                )
        command_error: BaseException | None = None
        result: CommandResult | None = None
        try:
            registration_dvc_env = transaction.registration_dvc_environment(
                dvc_config_snapshot, dvc_runtime_snapshot
            )
            transaction.begin_dvc_mutation()
            result = run_command(
                anfis_ablation_registration_dvc_add_command(dvc_bin, path),
                env=registration_dvc_env,
            )
        except BaseException as exc:
            command_error = exc
        try:
            transaction.registration_dvc_environment(
                dvc_config_snapshot, dvc_runtime_snapshot
            )
            transaction.capture_target(path)
            transaction.verify_family(
                min(target_index + 1, 10), family_snapshot
            )
            transaction.verify_progress_scope(
                pointer_count=min(target_index + 1, 10),
                models_registered=target_index >= 10,
            )
        except BaseException as verification_error:
            if command_error is not None:
                verification_error.add_note(
                    f"DVC command also failed: {command_error}"
                )
            return _abort_anfis_ablation_registration_transaction(
                transaction, verification_error
            )
        if command_error is not None:
            return _abort_anfis_ablation_registration_transaction(
                transaction,
                command_error,
                returncode=(
                    int(command_error.code)
                    if isinstance(command_error, SystemExit)
                    and isinstance(command_error.code, int)
                    else 2
                ),
            )
        if result is None:
            return _abort_anfis_ablation_registration_transaction(
                transaction,
                DeferredDvcTargetError("E0-MZE DVC command produced no result"),
            )
        dvc_add_results.append(result)

    try:
        registration_dvc_env = transaction.registration_dvc_environment(
            dvc_config_snapshot, dvc_runtime_snapshot
        )
        dvc_status_after = dvc_status_json(
            dvc_bin, env=registration_dvc_env
        )
        transaction.registration_dvc_environment(
            dvc_config_snapshot, dvc_runtime_snapshot
        )
        if dvc_status_after:
            raise DeferredDvcTargetError(
                "E0-MZE DVC status is not clean after exact registration"
            )
        post_snapshot = snapshot_anfis_ablation_family_bundle(
            repo_root=repo_root, expected_pointer_count=10
        )
        if post_snapshot != family_snapshot:
            raise DeferredDvcTargetError(
                "ANFIS-ablation final inode/ctime/mtime/hash snapshot changed during DVC add"
            )
        transaction._require_gitignore()
        pre_stage_status = _git_output(
            repo_root, "status", "--short", "--untracked-files=all"
        )
        transaction._require_gitignore()
        validate_anfis_ablation_registration_pre_stage_scope(pre_stage_status)
    except BaseException as exc:
        return _abort_anfis_ablation_registration_transaction(transaction, exc)

    try:
        transaction._require_gitignore()
        publication_check_result = run_command(
            ["scripts/check_repo_publication_ready.sh"], check=False
        )
        transaction._require_gitignore()
    except BaseException as exc:
        return _abort_anfis_ablation_registration_transaction(transaction, exc)
    if publication_check_result.returncode != 0:
        print(publication_check_result.stdout)
        print(publication_check_result.stderr, file=sys.stderr)
        return _abort_anfis_ablation_registration_transaction(
            transaction,
            DeferredDvcTargetError("Publication check failed; R-E0-MZE not staged"),
            returncode=publication_check_result.returncode,
        )
    try:
        transaction._require_gitignore()
        git_add_result = run_command(
            [
                "git",
                "add",
                "-A",
                "--",
                *sorted(ANFIS_ABLATION_R_MZE_STAGED_SCOPE),
            ]
        )
        transaction.mark_staging_owned()
        transaction._require_gitignore()
        staged_status = run_command(
            ["git", "diff", "--cached", "--name-status"]
        ).stdout
        transaction._require_gitignore()
    except BaseException as exc:
        try:
            transaction.capture_staging_owned(require_complete=False)
        except BaseException as capture_error:
            capture_error.add_note(f"Git add also failed: {exc}")
            return _abort_anfis_ablation_registration_transaction(
                transaction, capture_error
            )
        return _abort_anfis_ablation_registration_transaction(transaction, exc)
    try:
        transaction._require_gitignore()
        validate_anfis_ablation_registration_staged_scope(staged_status)
        validate_anfis_ablation_registration_staged_bindings(repo_root=repo_root)
        transaction._require_gitignore()
    except BaseException as exc:
        return _abort_anfis_ablation_registration_transaction(transaction, exc)

    try:
        transaction._require_gitignore()
        reproducibility_findings = anfis_ablation_registration_reproducibility_checks(
            staged_status=staged_status,
            selected_dvc_paths=selected_dvc_paths,
            artifacts=artifacts,
            max_manifest_hash_bytes=args.max_manifest_hash_bytes,
            verify_manifest_inputs=args.verify_manifest_inputs,
            repo_root=repo_root,
        )
        reproducibility_findings.append(
            ReproducibilityFinding(
                "ok",
                "anfis_ablation_registration",
                "R-E0-MZE",
                (
                    "Exact ten-slot family retained 80 immutable finals; ten "
                    "prediction pointers and models.dvc were registered without push."
                ),
            )
        )
        write_report(
            report_path,
            dry_run=False,
            selected_dvc_paths=selected_dvc_paths,
            deferred_dvc_paths=[],
            deferred_snapshot_before=None,
            deferred_snapshot_after=None,
            rejected_unmanaged_paths=unmanaged_paths,
            git_status_before=git_status_before,
            dvc_status_before=dvc_status_before,
            dvc_status_after=dvc_status_after,
            cloud_status_before=None,
            dvc_add_results=dvc_add_results,
            dvc_push_result=None,
            git_add_result=git_add_result,
            publication_check_result=publication_check_result,
            reproducibility_findings=reproducibility_findings,
            staged_status=staged_status,
            exclusive=True,
        )
        transaction._require_gitignore()
        if has_failing_findings(reproducibility_findings):
            raise DeferredDvcTargetError(
                "E0-MZE registration reproducibility checks failed"
            )
        registration_dvc_env = transaction.registration_dvc_environment(
            dvc_config_snapshot, dvc_runtime_snapshot
        )
        if dvc_status_json(dvc_bin, env=registration_dvc_env):
            raise DeferredDvcTargetError(
                "E0-MZE DVC status changed while writing the report"
            )
        transaction.registration_dvc_environment(
            dvc_config_snapshot, dvc_runtime_snapshot
        )
        if snapshot_anfis_ablation_family_bundle(
            repo_root=repo_root, expected_pointer_count=10
        ) != family_snapshot:
            raise DeferredDvcTargetError(
                "ANFIS-ablation family changed while writing the report"
        )
        validate_anfis_ablation_registration_staged_bindings(repo_root=repo_root)
        transaction._require_gitignore()
        _load_effective_anfis_ablation_dvc_registration_authority(
            audit_current_unpublished=True,
            repo_root=repo_root,
            registration_transaction=transaction.effective_audit_record(),
        )
        transaction._require_gitignore()
        transaction.registration_dvc_environment(
            dvc_config_snapshot, dvc_runtime_snapshot
        )
    except BaseException as exc:
        return _abort_anfis_ablation_registration_transaction(transaction, exc)

    try:
        transaction.registration_dvc_environment(
            dvc_config_snapshot, dvc_runtime_snapshot
        )
        transaction.commit()
        transaction.__exit__(None, None, None)
    except BaseException as exc:
        return _abort_anfis_ablation_registration_transaction(transaction, exc)

    print()
    print(f"Report written: {report_path}")
    print("Exact R-E0-MZE changes are staged; no DVC push was run.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Git and DVC artifacts before a manual commit.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_DVC_MANIFEST)
    parser.add_argument("--dvc-bin", default=None)
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Local report path. Defaults to a timestamped file under ignored tmp/.",
    )
    parser.add_argument("--target", action="append", default=[], help="Additional path to track with dvc add.")
    parser.add_argument(
        "--defer-dvc-target",
        action="append",
        default=[],
        help=(
            "Explicitly defer one sealed changed DVC target without dvc add. "
            "Only the exact Closure V1 A0 target 'models' is supported."
        ),
    )
    parser.add_argument(
        "--register-anfis-ablation-model-family",
        action="store_true",
        help=(
            "Run the exact effective E0-MZE registration: ten selection "
            "prediction payloads plus the monolithic models target."
        ),
    )
    parser.add_argument("--jobs", default=None, help="DVC push jobs.")
    parser.add_argument("--yes", action="store_true", help="Accept DVC add prompts.")
    parser.add_argument("--dry-run", action="store_true", help="Print and report actions without changing Git/DVC.")
    parser.add_argument("--no-push", action="store_true", help="Run dvc add and git add, but skip dvc push.")
    parser.add_argument("--allow-unmanaged", action="store_true", help="Do not fail if unmanaged heavy paths are rejected.")
    parser.add_argument("--skip-publication-check", action="store_true")
    parser.add_argument(
        "--max-manifest-hash-bytes",
        type=int,
        default=DEFAULT_MAX_MANIFEST_HASH_BYTES,
        help="Maximum file size for recomputing experiment-manifest SHA-256 outputs.",
    )
    parser.add_argument(
        "--verify-manifest-inputs",
        action="store_true",
        help="Also recompute SHA-256 hashes for experiment-manifest inputs within the size limit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_repo_root()
    if bool(getattr(args, "register_anfis_ablation_model_family", False)):
        return _run_anfis_ablation_model_family_registration(args)
    try:
        deferred_dvc_paths = normalize_deferred_dvc_targets(
            list(args.defer_dvc_target), no_push=bool(args.no_push)
        )
        exclude_snapshot: tuple[int, int, int, str] | None = None
        if deferred_dvc_paths:
            validate_deferred_dvc_invocation(args, deferred_dvc_paths)
    except DeferredDvcTargetError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    git_status_before = versionable_changes()
    deferred_stage_gate = ""
    final_calibration_stage_gate = ""
    final_calibration_stage_paths: tuple[str, ...] = ()
    final_calibration_r8_snapshot: (
        tuple[FinalCalibrationR8PhysicalIdentity, ...] | None
    ) = None
    locked_evaluation_input_physical_snapshot: (
        tuple[RegistrationFileIdentity, ...] | None
    ) = None
    deferred_exclude_validator = validate_deferred_dvc_git_exclude_environment
    deferred_state_validator = validate_deferred_dvc_models_state
    if deferred_dvc_paths:
        try:
            deferred_stage_gate = require_active_deferred_dvc_staging_gate(
                validate_deferred_dvc_pre_stage_scope(git_status_before)
            )
            if deferred_stage_gate in {"H-E0-MZE", "P-E0-MZE"}:
                deferred_exclude_validator = (
                    validate_anfis_ablation_adoption_git_environment
                )
                deferred_state_validator = (
                    validate_deferred_dvc_anfis_ablation_adoption_family_state
                )
            exclude_snapshot = deferred_exclude_validator()
        except DeferredDvcTargetError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    else:
        final_calibration_git_status_before = _git_output(
            Path("."), "status", "--short", "--untracked-files=all"
        )
        try:
            final_calibration_scope = (
                closure_locked_evaluation_input_bundle_pre_stage_scope(
                    final_calibration_git_status_before
                )
            )
            if final_calibration_scope is None:
                final_calibration_scope = (
                    final_calibration_r8_post_publication_authority_pre_stage_scope(
                        final_calibration_git_status_before
                    )
                )
            if final_calibration_scope is None:
                final_calibration_scope = (
                    final_calibration_r8_coordination_namespace_revalidation_pre_stage_scope(
                        final_calibration_git_status_before
                    )
                )
            if final_calibration_scope is None:
                final_calibration_scope = (
                    final_calibration_r8_manifest_reproducibility_pre_stage_scope(
                        final_calibration_git_status_before
                    )
                )
        except (
            DeferredDvcTargetError,
            ClosureLockedEvaluationInputBundleAdapterError,
            FinalCalibrationR8PostPublicationAuthorityAdapterError,
            FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError,
            FinalCalibrationR8ManifestReproducibilityAdapterError,
        ) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if final_calibration_scope is not None:
            final_calibration_stage_gate, final_calibration_stage_paths = (
                final_calibration_scope
            )
            git_status_before = final_calibration_git_status_before
            try:
                if final_calibration_stage_gate.endswith("MIB") or final_calibration_stage_gate == "R-E0-MI":
                    validate_closure_locked_evaluation_input_bundle_invocation(
                        args,
                        gate=final_calibration_stage_gate,
                    )
                    if final_calibration_stage_gate == "R-E0-MI":
                        locked_evaluation_input_physical_snapshot = (
                            snapshot_closure_locked_evaluation_input_physical_outputs()
                        )
                elif final_calibration_stage_gate.endswith("MCALM"):
                    validate_final_calibration_r8_post_publication_authority_invocation(
                        args
                    )
                    final_calibration_r8_snapshot = (
                        snapshot_final_calibration_r8_post_publication_outputs()
                    )
                elif final_calibration_stage_gate.endswith("MCALL"):
                    validate_final_calibration_r8_coordination_namespace_revalidation_invocation(
                        args
                    )
                    final_calibration_r8_snapshot = (
                        snapshot_final_calibration_r8_coordination_namespace_outputs()
                    )
                else:
                    validate_final_calibration_r8_manifest_reproducibility_invocation(
                        args
                    )
                    final_calibration_r8_snapshot = snapshot_final_calibration_r8_outputs()
            except (
                ClosureLockedEvaluationInputBundleAdapterError,
                FinalCalibrationR8PostPublicationAuthorityAdapterError,
                FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError,
                FinalCalibrationR8ManifestReproducibilityAdapterError,
            ) as exc:
                print(str(exc), file=sys.stderr)
                return 2
    report_path = args.report or default_report_path()
    dvc_bin = resolve_dvc_bin(args.dvc_bin)
    mib_stage_gate = bool(
        final_calibration_stage_gate
        and (
            final_calibration_stage_gate.endswith("MIB")
            or final_calibration_stage_gate == "R-E0-MI"
        )
    )
    if mib_stage_gate:
        try:
            validate_closure_locked_evaluation_input_dvc_binary(dvc_bin)
        except ClosureLockedEvaluationInputBundleAdapterError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if deferred_dvc_paths and dvc_bin != DEFAULT_DVC_BIN.as_posix():
        print("Deferred models mode requires the repository .venv/bin/dvc.", file=sys.stderr)
        return 2
    if deferred_dvc_paths:
        try:
            _require_no_symlink_ancestors(DEFAULT_DVC_BIN, anchor=Path("."))
            _require_regular_file(DEFAULT_DVC_BIN, mode=0o755)
        except DeferredDvcTargetError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    artifacts = load_configured_dvc_artifacts(args.manifest)
    dvc_status_before = dvc_status_json(dvc_bin)
    changed_artifacts = dvc_status_candidates(dvc_status_before, artifacts)
    missing_pointer_artifacts = declared_artifacts_missing_pointers(artifacts)
    manual_targets = unique_paths([Path(path) for path in args.target])
    unmanaged_paths = unmanaged_ignored_heavy_paths(artifacts)
    mib_r_gate = final_calibration_stage_gate == "R-E0-MI"
    if final_calibration_stage_gate and (
        dvc_status_before
        or changed_artifacts
        or missing_pointer_artifacts
        or (manual_targets and not mib_r_gate)
    ):
        print(
            f"{final_calibration_stage_gate[2:]} precommit requires a closed "
            "empty DVC and unmanaged target set.",
            file=sys.stderr,
        )
        return 2
    if mib_r_gate and (changed_artifacts or missing_pointer_artifacts):
        print(
            "R-E0-MI requires manual exact targets, not generic DVC discovery.",
            file=sys.stderr,
        )
        return 2

    deferred_final_snapshot: tuple[DeferredDvcFinalSnapshot, ...] | None = None
    deferred_post_snapshot: tuple[DeferredDvcFinalSnapshot, ...] | None = None
    try:
        validate_deferred_dvc_target_selection(
            deferred_dvc_paths,
            artifacts=artifacts,
            changed_artifacts=changed_artifacts,
            missing_pointer_artifacts=missing_pointer_artifacts,
            manual_targets=manual_targets,
        )
        if deferred_dvc_paths:
            deferred_final_snapshot = deferred_state_validator(dvc_status_before)
    except DeferredDvcTargetError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if dvc_status_before and not changed_artifacts and not missing_pointer_artifacts and not manual_targets:
        print("DVC status reports changes, but no declared artifact could be matched.", file=sys.stderr)
        print("Review `dvc status` and rerun with one or more `--target PATH` options.", file=sys.stderr)
        return 1

    print("Pre-commit artifact assistant")
    print_artifact_table("DVC-tracked artifacts changed according to dvc status:", changed_artifacts)
    print_artifact_table("Declared DVC artifacts missing pointer files:", missing_pointer_artifacts)
    print_path_table("Additional manual DVC targets:", manual_targets)
    print_path_table("Deferred DVC targets (not added):", deferred_dvc_paths)
    print_path_table("Unmanaged ignored heavy paths:", unmanaged_paths)

    deferred_set = set(deferred_dvc_paths)
    changed_for_add = [
        artifact for artifact in changed_artifacts if artifact.path not in deferred_set
    ]
    selected_dvc_paths = [artifact.path for artifact in changed_for_add]
    selected_dvc_paths.extend(artifact.path for artifact in missing_pointer_artifacts)
    selected_dvc_paths.extend(manual_targets)

    rejected_unmanaged: list[Path] = []
    if mib_r_gate:
        try:
            validate_closure_locked_evaluation_input_unmanaged_namespace(
                unmanaged_paths
            )
        except ClosureLockedEvaluationInputBundleAdapterError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if unmanaged_paths:
        if mib_r_gate:
            namespace = Path("data/closure_v1/locked_evaluation")
            rejected_unmanaged.extend(
                path
                for path in unmanaged_paths
                if path != namespace and namespace not in path.parents
            )
        elif args.yes:
            selected_dvc_paths.extend(unmanaged_paths)
        else:
            for path in unmanaged_paths:
                if prompt_yes_no(f"Add ignored heavy path to DVC: {path}?", default=False):
                    selected_dvc_paths.append(path)
                else:
                    rejected_unmanaged.append(path)

    selected_dvc_paths = unique_paths(selected_dvc_paths)

    if mib_r_gate:
        try:
            expected_mib_targets = closure_locked_evaluation_input_dvc_targets()
            if tuple(selected_dvc_paths) != expected_mib_targets:
                raise ClosureLockedEvaluationInputBundleAdapterError(
                    "R-E0-MI selected DVC targets are not the exact four inputs"
                )
        except ClosureLockedEvaluationInputBundleAdapterError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    elif final_calibration_stage_gate and selected_dvc_paths:
        print(
            f"{final_calibration_stage_gate[2:]} precommit forbids every DVC add target.",
            file=sys.stderr,
        )
        return 2

    if changed_for_add and not args.yes:
        if not prompt_yes_no("Run dvc add for the changed DVC-tracked artifacts?", default=True):
            print("DVC changes were detected but not accepted for dvc add.", file=sys.stderr)
            return 1

    if rejected_unmanaged and not args.allow_unmanaged:
        print("Unmanaged heavy paths were rejected. Use --allow-unmanaged only if this is intentional.", file=sys.stderr)
        return 1

    if deferred_dvc_paths and selected_dvc_paths:
        print("Deferred models mode forbids every DVC add target.", file=sys.stderr)
        return 2

    print_path_table("Selected DVC add targets:", selected_dvc_paths)

    cloud_status_before: CommandResult | None = None
    dvc_add_results: list[CommandResult] = []
    dvc_push_result: CommandResult | None = None
    git_add_result: CommandResult | None = None
    publication_check_result: CommandResult | None = None
    reproducibility_findings: list[ReproducibilityFinding] = []
    dvc_status_after: dict[str, Any] | None = None

    if args.dry_run:
        print()
        print("Dry run. No Git or DVC mutations will be made.")
        for path in selected_dvc_paths:
            print(f"would run: {command_text([dvc_bin, 'add', path.as_posix()])}")
        if not args.no_push:
            print(f"would run: {command_text([dvc_bin, 'push'])}")
        if final_calibration_stage_gate:
            print(
                "would run: "
                + command_text(
                    [
                        "git",
                        "add",
                        "-A",
                        "--",
                        *final_calibration_stage_paths,
                    ]
                )
            )
        else:
            print("would run: git add -A")
    else:
        for target_index, path in enumerate(selected_dvc_paths, start=1):
            if not path.exists():
                print(f"Selected DVC target does not exist: {path}", file=sys.stderr)
                return 2
            dvc_add_command = [dvc_bin, "add", path.as_posix()]
            if mib_r_gate:
                dvc_add_command = closure_locked_evaluation_input_dvc_add_command(
                    dvc_bin,
                    path,
                )
            dvc_add_result = run_command(
                dvc_add_command,
                check=not mib_r_gate,
                env=dvc_environment(),
            )
            dvc_add_results.append(dvc_add_result)
            if mib_r_gate and dvc_add_result.returncode != 0:
                try:
                    write_closure_locked_evaluation_input_dvc_failure_report(
                        report_path=report_path,
                        selected_dvc_paths=selected_dvc_paths,
                        rejected_unmanaged_paths=rejected_unmanaged,
                        git_status_before=git_status_before,
                        dvc_status_before=dvc_status_before,
                        dvc_add_results=dvc_add_results,
                        failed_target_index=target_index,
                    )
                except (
                    ClosureLockedEvaluationInputBundleAdapterError,
                    DeferredDvcTargetError,
                ) as exc:
                    print(str(exc), file=sys.stderr)
                print(
                    f"R-E0-MI DVC add {target_index}/4 failed; partial evidence "
                    "was preserved and no staging or push will run. Audit before "
                    "any retry.",
                    file=sys.stderr,
                )
                return 2

        if mib_r_gate:
            if (
                locked_evaluation_input_physical_snapshot is None
                or snapshot_closure_locked_evaluation_input_physical_outputs()
                != locked_evaluation_input_physical_snapshot
            ):
                print(
                    "R-E0-MI physical outputs changed during directed DVC add.",
                    file=sys.stderr,
                )
                return 2

        if not args.no_push:
            cloud_status_before = run_command([dvc_bin, "status", "--cloud"], check=False, env=dvc_environment())
            push_command = [dvc_bin, "push"]
            if args.jobs:
                push_command.extend(["--jobs", str(args.jobs)])
            dvc_push_result = run_command(push_command, env=dvc_environment())

    if not args.dry_run:
        publication_check_result = None
        if not args.skip_publication_check:
            publication_check_result = run_command(["scripts/check_repo_publication_ready.sh"], check=False)
            if publication_check_result.returncode != 0:
                print(publication_check_result.stdout)
                print(publication_check_result.stderr, file=sys.stderr)
                print("Publication check failed; not staging changes.", file=sys.stderr)
                return publication_check_result.returncode

        if deferred_dvc_paths:
            try:
                if deferred_exclude_validator() != exclude_snapshot:
                    raise DeferredDvcTargetError(
                        "Deferred models Git exclude file changed before staging"
                    )
                current_status = dvc_status_json(dvc_bin)
                deferred_state_validator(
                    current_status,
                    expected_final_snapshot=deferred_final_snapshot,
                )
            except DeferredDvcTargetError as exc:
                print(str(exc), file=sys.stderr)
                return 2

        if deferred_dvc_paths:
            selected_scope = _deferred_dvc_staged_scopes().get(
                deferred_stage_gate
            )
            if selected_scope is None:
                print("Deferred models pre-stage gate is unknown.", file=sys.stderr)
                return 2
            git_add_command = ["git", "add", "-A", "--", *sorted(selected_scope)]
        elif final_calibration_stage_gate:
            git_add_command = [
                "git",
                "add",
                "-A",
                "--",
                *final_calibration_stage_paths,
            ]
        else:
            git_add_command = ["git", "add", "-A"]
        git_add_result = run_command(git_add_command)
        staged_status = run_command(["git", "diff", "--cached", "--name-status"]).stdout
        if deferred_dvc_paths:
            try:
                if validate_deferred_dvc_staged_scope(staged_status) != deferred_stage_gate:
                    raise DeferredDvcTargetError(
                        "Deferred models H/P stage identity changed during git add"
                    )
                validate_deferred_dvc_staged_bindings(deferred_stage_gate)
                expected_scope = _deferred_dvc_staged_scopes().get(
                    deferred_stage_gate
                )
                if expected_scope is None:
                    raise DeferredDvcTargetError(
                        "Deferred models post-stage gate is unknown"
                    )
                validate_anfis_ablation_git_short_status_map(
                    versionable_changes(),
                    expected=_expected_short_scope(
                        expected_scope, staged=True
                    ),
                    context=(
                        f"{deferred_stage_gate} deferred post-stage scope"
                    ),
                )
                if _git_output(Path("."), "diff", "--name-status").strip():
                    raise DeferredDvcTargetError(
                        "Deferred models mode left an unstaged tracked change"
                    )
                dvc_status_after = dvc_status_json(dvc_bin)
                deferred_post_snapshot = deferred_state_validator(
                    dvc_status_after,
                    expected_final_snapshot=deferred_final_snapshot,
                )
                validate_deferred_dvc_staged_bindings(deferred_stage_gate)
                if deferred_exclude_validator() != exclude_snapshot:
                    raise DeferredDvcTargetError(
                        "Deferred models Git exclude file changed during staging"
                    )
            except DeferredDvcTargetError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        if final_calibration_stage_gate:
            try:
                workspace_scope = _git_output(
                    Path("."),
                    "status",
                    "--short",
                    "--untracked-files=all",
                )
                if (
                    final_calibration_stage_gate.endswith("MIB")
                    or final_calibration_stage_gate == "R-E0-MI"
                ):
                    validate_closure_locked_evaluation_input_bundle_staged_scope(
                        staged_status,
                        gate=final_calibration_stage_gate,
                    )
                    validate_closure_locked_evaluation_input_bundle_workspace_scope(
                        workspace_scope,
                        gate=final_calibration_stage_gate,
                    )
                    validate_closure_locked_evaluation_input_bundle_staged_bindings(
                        gate=final_calibration_stage_gate,
                    )
                elif final_calibration_stage_gate.endswith("MCALM"):
                    validate_final_calibration_r8_post_publication_authority_staged_scope(
                        staged_status,
                        gate=final_calibration_stage_gate,
                    )
                    validate_final_calibration_r8_post_publication_authority_workspace_scope(
                        workspace_scope,
                        gate=final_calibration_stage_gate,
                    )
                elif final_calibration_stage_gate.endswith("MCALL"):
                    validate_final_calibration_r8_coordination_namespace_revalidation_staged_scope(
                        staged_status,
                        gate=final_calibration_stage_gate,
                    )
                    validate_final_calibration_r8_coordination_namespace_revalidation_workspace_scope(
                        workspace_scope,
                        gate=final_calibration_stage_gate,
                    )
                else:
                    validate_final_calibration_r8_manifest_reproducibility_staged_scope(
                        staged_status,
                        gate=final_calibration_stage_gate,
                    )
                    validate_final_calibration_r8_manifest_reproducibility_workspace_scope(
                        workspace_scope,
                        gate=final_calibration_stage_gate,
                    )
            except (
                ClosureLockedEvaluationInputBundleAdapterError,
                FinalCalibrationR8PostPublicationAuthorityAdapterError,
                FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError,
                FinalCalibrationR8ManifestReproducibilityAdapterError,
            ) as exc:
                print(str(exc), file=sys.stderr)
                return 2
        if final_calibration_stage_gate == "R-E0-MCALL":
            reproducibility_findings = (
                final_calibration_r8_coordination_namespace_revalidation_checks(
                    staged_status=staged_status,
                    selected_dvc_paths=selected_dvc_paths,
                    artifacts=artifacts,
                    max_manifest_hash_bytes=args.max_manifest_hash_bytes,
                    verify_manifest_inputs=args.verify_manifest_inputs,
                )
            )
        elif final_calibration_stage_gate == "R-E0-MCALK":
            reproducibility_findings = (
                final_calibration_r8_manifest_reproducibility_checks(
                    staged_status=staged_status,
                    selected_dvc_paths=selected_dvc_paths,
                    artifacts=artifacts,
                    max_manifest_hash_bytes=args.max_manifest_hash_bytes,
                    verify_manifest_inputs=args.verify_manifest_inputs,
                )
            )
        else:
            reproducibility_findings = reproducibility_checks(
                staged_status=staged_status,
                selected_dvc_paths=selected_dvc_paths,
                artifacts=artifacts,
                max_manifest_hash_bytes=args.max_manifest_hash_bytes,
                verify_manifest_inputs=args.verify_manifest_inputs,
            )
        if final_calibration_stage_gate:
            mib_gate = (
                final_calibration_stage_gate.endswith("MIB")
                or final_calibration_stage_gate == "R-E0-MI"
            )
            if not mib_gate and final_calibration_r8_snapshot is None:
                print(
                    f"{final_calibration_stage_gate[2:]} immutable R8 snapshot is absent.",
                    file=sys.stderr,
                )
                return 2
            try:
                if mib_gate:
                    revalidate_closure_locked_evaluation_input_bundle_transaction(
                        gate=final_calibration_stage_gate,
                        staged_status=staged_status,
                        expected_physical_snapshot=(
                            locked_evaluation_input_physical_snapshot
                        ),
                    )
                elif final_calibration_r8_snapshot is None:
                    raise FinalCalibrationR8ManifestReproducibilityAdapterError(
                        "Immutable R8 snapshot disappeared before revalidation"
                    )
                elif final_calibration_stage_gate.endswith("MCALM"):
                    revalidate_final_calibration_r8_post_publication_authority_transaction(
                        gate=final_calibration_stage_gate,
                        staged_status=staged_status,
                        expected_snapshot=final_calibration_r8_snapshot,
                    )
                elif final_calibration_stage_gate.endswith("MCALL"):
                    revalidate_final_calibration_r8_coordination_namespace_revalidation_transaction(
                        gate=final_calibration_stage_gate,
                        staged_status=staged_status,
                        expected_snapshot=final_calibration_r8_snapshot,
                    )
                else:
                    revalidate_final_calibration_r8_manifest_reproducibility_transaction(
                        gate=final_calibration_stage_gate,
                        staged_status=staged_status,
                        expected_snapshot=final_calibration_r8_snapshot,
                    )
                dvc_status_after = dvc_status_json(dvc_bin)
                if dvc_status_after != dvc_status_before:
                    raise _final_calibration_stage_adapter_error(
                        final_calibration_stage_gate,
                        f"{final_calibration_stage_gate[2:]} DVC status changed "
                        "during precommit",
                    )
            except (
                ClosureLockedEvaluationInputBundleAdapterError,
                FinalCalibrationR8PostPublicationAuthorityAdapterError,
                FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError,
                FinalCalibrationR8ManifestReproducibilityAdapterError,
            ) as exc:
                print(str(exc), file=sys.stderr)
                return 2
        if deferred_dvc_paths:
            reproducibility_findings.append(
                ReproducibilityFinding(
                    "ok",
                    "deferred_dvc",
                    DEFERRED_DVC_MODELS_TARGET.as_posix(),
                    (
                        "Exact Closure V1 A0/1729 models delta remains intentionally "
                        f"unregistered under {deferred_stage_gate}; no DVC add or push ran."
                    ),
                )
            )
            try:
                final_status = dvc_status_json(dvc_bin)
                if final_status != dvc_status_after:
                    raise DeferredDvcTargetError(
                        "Deferred models DVC status changed during reproducibility checks"
                    )
                deferred_post_snapshot = deferred_state_validator(
                    final_status,
                    expected_final_snapshot=deferred_final_snapshot,
                )
                validate_deferred_dvc_staged_bindings(deferred_stage_gate)
                if deferred_exclude_validator() != exclude_snapshot:
                    raise DeferredDvcTargetError(
                        "Deferred models Git exclude file changed before reporting"
                    )
            except DeferredDvcTargetError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        try:
            write_report(
                report_path,
                dry_run=args.dry_run,
                selected_dvc_paths=selected_dvc_paths,
                deferred_dvc_paths=deferred_dvc_paths,
                deferred_snapshot_before=deferred_final_snapshot,
                deferred_snapshot_after=deferred_post_snapshot,
                rejected_unmanaged_paths=rejected_unmanaged,
                git_status_before=git_status_before,
                dvc_status_before=dvc_status_before,
                dvc_status_after=dvc_status_after,
                cloud_status_before=cloud_status_before,
                dvc_add_results=dvc_add_results,
                dvc_push_result=dvc_push_result,
                git_add_result=git_add_result,
                publication_check_result=publication_check_result,
                reproducibility_findings=reproducibility_findings,
                staged_status=staged_status,
                exclusive=bool(
                    deferred_dvc_paths or final_calibration_stage_gate
                ),
            )
        except DeferredDvcTargetError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if deferred_dvc_paths:
            try:
                reported_status = dvc_status_json(dvc_bin)
                if reported_status != dvc_status_after:
                    raise DeferredDvcTargetError(
                        "Deferred models DVC status changed while writing the report"
                    )
                deferred_state_validator(
                    reported_status,
                    expected_final_snapshot=deferred_final_snapshot,
                )
                validate_deferred_dvc_staged_bindings(deferred_stage_gate)
                if deferred_exclude_validator() != exclude_snapshot:
                    raise DeferredDvcTargetError(
                        "Deferred models Git exclude file changed while writing the report"
                    )
            except DeferredDvcTargetError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        if final_calibration_stage_gate:
            mib_gate = (
                final_calibration_stage_gate.endswith("MIB")
                or final_calibration_stage_gate == "R-E0-MI"
            )
            if not mib_gate and final_calibration_r8_snapshot is None:
                print(
                    f"{final_calibration_stage_gate[2:]} immutable R8 snapshot is absent.",
                    file=sys.stderr,
                )
                return 2
            try:
                if mib_gate:
                    revalidate_closure_locked_evaluation_input_bundle_transaction(
                        gate=final_calibration_stage_gate,
                        staged_status=staged_status,
                        expected_physical_snapshot=(
                            locked_evaluation_input_physical_snapshot
                        ),
                    )
                elif final_calibration_r8_snapshot is None:
                    raise FinalCalibrationR8ManifestReproducibilityAdapterError(
                        "Immutable R8 snapshot disappeared before revalidation"
                    )
                elif final_calibration_stage_gate.endswith("MCALM"):
                    revalidate_final_calibration_r8_post_publication_authority_transaction(
                        gate=final_calibration_stage_gate,
                        staged_status=staged_status,
                        expected_snapshot=final_calibration_r8_snapshot,
                    )
                elif final_calibration_stage_gate.endswith("MCALL"):
                    revalidate_final_calibration_r8_coordination_namespace_revalidation_transaction(
                        gate=final_calibration_stage_gate,
                        staged_status=staged_status,
                        expected_snapshot=final_calibration_r8_snapshot,
                    )
                else:
                    revalidate_final_calibration_r8_manifest_reproducibility_transaction(
                        gate=final_calibration_stage_gate,
                        staged_status=staged_status,
                        expected_snapshot=final_calibration_r8_snapshot,
                    )
                if dvc_status_json(dvc_bin) != dvc_status_before:
                    raise _final_calibration_stage_adapter_error(
                        final_calibration_stage_gate,
                        f"{final_calibration_stage_gate[2:]} DVC status changed "
                        "while writing the report",
                    )
            except (
                ClosureLockedEvaluationInputBundleAdapterError,
                FinalCalibrationR8PostPublicationAuthorityAdapterError,
                FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError,
                FinalCalibrationR8ManifestReproducibilityAdapterError,
            ) as exc:
                print(str(exc), file=sys.stderr)
                return 2
        if has_failing_findings(reproducibility_findings):
            print()
            print("Reproducibility checks failed; fix the findings and rerun the assistant.", file=sys.stderr)
            print(f"Report written: {report_path}", file=sys.stderr)
            return 1
    else:
        staged_status = "dry run"
        reproducibility_findings = [
            ReproducibilityFinding(
                "warn",
                "reproducibility",
                "-",
                "Dry run: final staged reproducibility checks were not executed.",
            )
        ]
        write_report(
            report_path,
            dry_run=args.dry_run,
            selected_dvc_paths=selected_dvc_paths,
            deferred_dvc_paths=deferred_dvc_paths,
            deferred_snapshot_before=None,
            deferred_snapshot_after=None,
            rejected_unmanaged_paths=rejected_unmanaged,
            git_status_before=git_status_before,
            dvc_status_before=dvc_status_before,
            dvc_status_after=None,
            cloud_status_before=None,
            dvc_add_results=[],
            dvc_push_result=None,
            git_add_result=None,
            publication_check_result=None,
            reproducibility_findings=reproducibility_findings,
            staged_status=staged_status,
        )

    print()
    print(f"Report written: {report_path}")
    if not args.dry_run:
        print("Changes are staged. Review with:")
        print("  git diff --cached --stat")
        print("  git diff --cached --name-status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
