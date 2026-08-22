#!/usr/bin/env python
"""Strict public contract for the final Closure V1 Phase 4 certification.

This module is deliberately outcome-free.  It validates the static H/P/R-CERT
topology, the exact public evidence anchors, the eight identity-only DVC
pointers, the closed public-test inventory and the exact eight-file result
namespace.  It never resolves a DVC pointer and never opens a Parquet payload,
raw target, outcome namespace, private manuscript, or outcome-access log.

The public test suite is sealed to the exact selector count, collected-node
count and ordered-node digest reproduced by two independent outcome-free
collections.  The explicit ``pending_integration`` state remains available
only to integration fixtures; production authority and execution callers
reject it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = Path(
    "configs/closure_v1/phase4_final_certification.yaml"
)
DEFAULT_SCHEMA_PATH = Path(
    "configs/closure_v1/phase4_final_certification.schema.json"
)
H1_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority.json"
)
H1_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest.json"
)
H2_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v2.json"
)
H2_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v2.json"
)
H3_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v3.json"
)
H3_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v3.json"
)
H4_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v4.json"
)
H4_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v4.json"
)
H5_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v5.json"
)
H5_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v5.json"
)
H6_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v6.json"
)
H6_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v6.json"
)
H7_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v7.json"
)
H7_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v7.json"
)
H8_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v8.json"
)
H8_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v8.json"
)
H9_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v9.json"
)
H9_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v9.json"
)
H10_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v10.json"
)
H10_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v10.json"
)
H11_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v11.json"
)
H11_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v11.json"
)
H12_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v12.json"
)
H12_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v12.json"
)
H13_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v13.json"
)
H13_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v13.json"
)
H14_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v14.json"
)
H14_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v14.json"
)
H15_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v15.json"
)
H15_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v15.json"
)
H16_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v16.json"
)
H16_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v16.json"
)
H17_AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v17.json"
)
H17_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v17.json"
)
AUTHORITY_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_v18.json"
)
AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_final_certification_authority_manifest_v18.json"
)
CERTIFICATION_ROOT = Path("reports/closure_v1/12_certification")
GUARD_PATH = Path(
    "tmp/closure_v1_phase4_final_certification/certification.guard"
)
LOCAL_DVC_CONFIG_PATH = Path(".dvc/config.local")

CONTRACT_VERSION = "closure_v1_phase4_final_certification_v18"
CLOSURE_SOURCE_COMMIT = "ea8ddce7f8edb9a61db97e29178e52603fa371b1"
R_SYN_COMMIT = "528dcb74a7c08b65f262901e4562a67b784db8c9"
EDITORIAL_COMMIT = "d1daa3059462854d6ddf5199fbc05515cec76982"
H1_CERT_COMMIT = "003ca2282af5d7156b5814b59d8f1ddfb7fc681e"
P1_CERT_COMMIT = "67983d8ea823a59eb4af55b59da04fb4ae298dcb"
H2_CERT_COMMIT = "8e01709c54330502aee318500ab9248e90fe17c5"
P2_CERT_COMMIT = "72273b52d47df83acc7618fe98a887b74d690a13"
H3_CERT_COMMIT = "2372d0f9cc36aa916b79f34641b2b01134057890"
P3_CERT_COMMIT = "bcd306a9e8dd5162466124d8854b9d1d99a8517c"
H4_CERT_COMMIT = "44f96a7e2b204d80d8e336e90b4a0f4a3456c13f"
P4_CERT_COMMIT = "21551c7e53b776b693f4f76b88682180093a0f31"
H5_CERT_COMMIT = "d18201462be9f6cc057d0187dec2b8b731b62e48"
P5_CERT_COMMIT = "da7b673aa8a7cbdc428ca829e5b9f0a5ac79a3ef"
H6_CERT_COMMIT = "a67d58458c1eeb6b38e752dea4eb3bf91ec44ca9"
P6_CERT_COMMIT = "6aea7e7d7908ea0b23dcee41b316759f299114f5"
H7_CERT_COMMIT = "67b156d4f5d65ac471597349d20098346e17a736"
P7_CERT_COMMIT = "66505102124082e7926aac58215a0bd35a07ff4b"
H8_CERT_COMMIT = "6a339cb7fcec125e379d9829c76e90f5ded55d3a"
P8_CERT_COMMIT = "095b55b208f69936a562eaf09c76fab3389df199"
H9_CERT_COMMIT = "f296236fa7cdc89ad6b85ce1642b478276b92553"
P9_CERT_COMMIT = "73d12c7386b9e4a34d8f15b5330cecf357e05ac1"
H10_CERT_COMMIT = "825b3382f8d501cbc550bf7738a48d4d489dd5e8"
P10_CERT_COMMIT = "9ca3126667eaa8c4fd754a3499a7a9eacdd2d2b0"
H11_CERT_COMMIT = "b83bc2cbccdae5f81bb8ee4b6547054b543260fd"
P11_CERT_COMMIT = "af9e23ec1c21968b0d5bb52821619e21f8de5673"
H12_CERT_COMMIT = "bc5595bfca0e39cd3912f6b786442580d5c1a9fe"
P12_CERT_COMMIT = "f97e0a5cf21aa9b65623cee0a8a656ab0537e2ad"
H14_CERT_COMMIT = "b6c22c3bdc9e3209f621ee1c4d79ae0ca7770dec"
P14_CERT_COMMIT = "c0458d7294b0d088169b1f3471200ec1a7342f8b"
H15_CERT_COMMIT = "13640203e1c95d5ae9f8861fec3e6c842d90c545"
P15_CERT_COMMIT = "fa00bbd07d47ff504f2323e418934824efab386a"
H16_CERT_COMMIT = "4f78e7d1a8f93eedda169c5499c331b8da15de1e"
P16_CERT_COMMIT = "6c5fbaac2bf48393b3e7ef3e24d95006ecc016b9"
H17_CERT_COMMIT = "a7e4f10321c8ea8321d0c4917969ecc9ab39f59b"
P17_CERT_COMMIT = "1677778862786d28b9f60e80b7e718432e0b0947"
FINAL_TAG = "thesis-closure-v1"
AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v18"
AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v18"
)
H17_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v17"
H17_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v17"
)
H16_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v16"
H16_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v16"
)
H15_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v15"
H15_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v15"
)
H14_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v14"
H14_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v14"
)
H13_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v13"
H13_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v13"
)
H12_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v12"
H12_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v12"
)
H11_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v11"
H11_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v11"
)
H10_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v10"
H10_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v10"
)
H9_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v9"
H9_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v9"
)
H8_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v8"
H8_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v8"
)
H7_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v7"
H7_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v7"
)
H6_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v6"
H6_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v6"
)
H5_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v5"
H5_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v5"
)
H4_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v4"
H4_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v4"
)
H3_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v3"
H3_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v3"
)
H2_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v2"
H2_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v2"
)
H1_AUTHORITY_VERSION = "closure_v1_phase4_final_certification_authority_v1"
H1_AUTHORITY_MANIFEST_VERSION = (
    "closure_v1_phase4_final_certification_authority_manifest_v1"
)
H2_AUTHORITY_BYTES = 24631
H2_AUTHORITY_SHA256 = (
    "b1b382c8317a02daca0f842f901b06443c8125ee3bc6542c343c4b89187b147b"
)
H2_AUTHORITY_MANIFEST_BYTES = 1588
H2_AUTHORITY_MANIFEST_SHA256 = (
    "d41fd5900c1423f32d6929ce40214e54c943f72e603a83796189e3fc29ff2810"
)
H3_AUTHORITY_BYTES = 34128
H3_AUTHORITY_SHA256 = (
    "47bbb1839b5d28e91b1c535cbc093400d61a40354ec633d3ac8f2c43d42be2f8"
)
H3_AUTHORITY_MANIFEST_BYTES = 1832
H3_AUTHORITY_MANIFEST_SHA256 = (
    "1e9344535153e516562628881e041cc3ed1a28b5978ff6839f90b760db6e0d51"
)
H4_AUTHORITY_BYTES = 41119
H4_AUTHORITY_SHA256 = (
    "28bc6302e08b4e87f80737d7806cacd8d6856687ecee8ec5b2bc7e018d2e4c17"
)
H4_AUTHORITY_MANIFEST_BYTES = 1973
H4_AUTHORITY_MANIFEST_SHA256 = (
    "17bf44a59c7bc536fe981c1303e20e84accbc0d5c8f2a33cd0e12a8df12a80b8"
)
H5_AUTHORITY_BYTES = 47274
H5_AUTHORITY_SHA256 = (
    "f079c81d7c06440e0cda110d0434301ddc9aa0c3b22ef8d4ddf989cb76d9f849"
)
H5_AUTHORITY_MANIFEST_BYTES = 2114
H5_AUTHORITY_MANIFEST_SHA256 = (
    "f895eee5f6df76b4229f719fba2be398f11209b2ebf8893a886dea3d42947aba"
)
H6_AUTHORITY_BYTES = 55835
H6_AUTHORITY_SHA256 = (
    "aae4dba7483ac5cceb4076e4eaf74ebd75b6ffe8e766de5db77bf10f246c0720"
)
H6_AUTHORITY_MANIFEST_BYTES = 2255
H6_AUTHORITY_MANIFEST_SHA256 = (
    "609ba901e766bd62816a42da3761d078f226b4270e240e954669361afb637657"
)
H7_AUTHORITY_BYTES = 61984
H7_AUTHORITY_SHA256 = (
    "a82ebb157fea898ecf7606a3493577a2a508b6f936590410419f1bc8ea33d53d"
)
H7_AUTHORITY_MANIFEST_BYTES = 2396
H7_AUTHORITY_MANIFEST_SHA256 = (
    "b98a97ed7a021f5a26b2cb11ab7eb8a772526dfef54bb8876b3f849488332297"
)
H8_AUTHORITY_BYTES = 69024
H8_AUTHORITY_SHA256 = (
    "a8c5a8228134b5fdf5eadcb5943c9f72639913c565a2b572801ddfb0c6058c64"
)
H8_AUTHORITY_MANIFEST_BYTES = 2537
H8_AUTHORITY_MANIFEST_SHA256 = (
    "fae7ddfc08639110f606013b8ae05ded9a02fcdb47b118231b5b7db74054cbee"
)
H9_AUTHORITY_BYTES = 79355
H9_AUTHORITY_SHA256 = (
    "b9d6a453b6b989f6202a4c6dfabde31d01502faa887c83ac808a41876423859e"
)
H9_AUTHORITY_MANIFEST_BYTES = 2678
H9_AUTHORITY_MANIFEST_SHA256 = (
    "496f740f52ef03d46be615e482493dc58556dbbbeedfacbd1271418fbdf878d1"
)
H10_AUTHORITY_BYTES = 92421
H10_AUTHORITY_SHA256 = (
    "1e8822415f71d35d40db0f7b384184f1759ce1e899f068510605e3d25f9976d0"
)
H10_AUTHORITY_MANIFEST_BYTES = 2826
H10_AUTHORITY_MANIFEST_SHA256 = (
    "6a283c675bf5a61222df495f2374554d8d96caf1d2890305e2aea327a9e63932"
)
H11_AUTHORITY_BYTES = 101492
H11_AUTHORITY_SHA256 = (
    "10a390b8b23436a443c960b22b46d424dbfad3555f961641dd6e8779489b4b81"
)
H11_AUTHORITY_MANIFEST_BYTES = 2972
H11_AUTHORITY_MANIFEST_SHA256 = (
    "b9a0593cebaa5ff6ee919344e84cdeb6fead78c5e2b8af0f4a59a10590b6e716"
)
H12_AUTHORITY_BYTES = 111368
H12_AUTHORITY_SHA256 = (
    "62373f7c4d425d010925deb283750a1f3a65a0e62dcd98f817c9f9de6ffe792b"
)
H12_AUTHORITY_MANIFEST_BYTES = 3116
H12_AUTHORITY_MANIFEST_SHA256 = (
    "ee791c92b62d31c5366954656e40926f4afdc556ef4e6436019c12a2fa76868c"
)
H14_AUTHORITY_BYTES = 123750
H14_AUTHORITY_SHA256 = (
    "0244008e7d6f56a73bae119f8b4e4319606b04969776c6b18fa653bd3b5fbc0b"
)
H14_AUTHORITY_MANIFEST_BYTES = 3350
H14_AUTHORITY_MANIFEST_SHA256 = (
    "bfd990b8e916f4028f0768dc773b424d189f93b74c70cf4d356a2a0ee0e1c3a2"
)
H15_AUTHORITY_BYTES = 130583
H15_AUTHORITY_SHA256 = (
    "41f5099be018d89a7bfec099f8905fd1aacdbbc67f7d1d11cbecbe1c7640032b"
)
H15_AUTHORITY_MANIFEST_BYTES = 3494
H15_AUTHORITY_MANIFEST_SHA256 = (
    "82ccf6daa047950ff4c06de31defeecff574f678065d032e4a3530eca9e6ab40"
)
H16_AUTHORITY_BYTES = 142014
H16_AUTHORITY_SHA256 = (
    "aeff33d3ca0201fa86ded7759b6b3b7a12dad37b27c0a143f84a834fc9876797"
)
H16_AUTHORITY_MANIFEST_BYTES = 3638
H16_AUTHORITY_MANIFEST_SHA256 = (
    "e78e86590722c8eccd9f0936553750a8530e07232237cf57cf867f7b5e3f6fd3"
)
H17_AUTHORITY_BYTES = 154137
H17_AUTHORITY_SHA256 = (
    "d095c49c1038f4f4d11f1f5011b26152d666c67b8b7da4151a6fee70cbcaaacd"
)
H17_AUTHORITY_MANIFEST_BYTES = 3782
H17_AUTHORITY_MANIFEST_SHA256 = (
    "baa72773861fd9b24d55a106059690ead7089d7f3ccfeaf458f6b322b5481240"
)
HASH_CHUNK_SIZE = 1024 * 1024
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MD5_RE = re.compile(r"^[0-9a-f]{32}$")

OUTPUT_PATHS = (
    "reports/closure_v1/12_certification/public_tests.xml",
    "reports/closure_v1/12_certification/test_report.md",
    "reports/closure_v1/12_certification/openapi.json",
    "reports/closure_v1/12_certification/openapi_contract_report.md",
    "reports/closure_v1/12_certification/end_to_end_report.md",
    "reports/closure_v1/12_certification/environment.json",
    "reports/closure_v1/12_certification/FINAL_DOCTORAL_CERTIFICATION_REPORT.md",
    "reports/closure_v1/12_certification/final_certification_manifest.json",
)
EXPECTED_RUNTIME_VERSIONS: Mapping[str, str] = {
    "python": "Python 3.14.7",
    "dvc": "3.67.1",
    "ty": "ty 0.0.37",
    "git": "git version 2.55.0",
    "poetry": "Poetry (version 2.4.1)",
    "bubblewrap": "bubblewrap 0.11.2",
    "docker_client": "29.7.2",
    "docker_server": "29.7.2",
}
POSTGRES_PORTABLE_PATH_POLICY: Mapping[str, Any] = {
    "volume": "<OWNED_DB_SOCKET>:<CONTAINER_POSTGRES_SOCKET>",
    "data_tmpfs": "<CONTAINER_POSTGRES_DATA>:rw,size=512m",
    "runtime_tmpfs": "<CONTAINER_TMP>:rw,size=64m",
    "unix_socket_directories": (
        "unix_socket_directories=<CONTAINER_POSTGRES_SOCKET>"
    ),
    "absolute_paths_serialized": False,
}
POSTGRES_CONNECTION_POLICY: Mapping[str, Any] = {
    "test_database_url_scheme": "postgresql+asyncpg",
    "test_database_url_database": "closure_phase4_cert",
    "test_database_url_query_present": False,
    "test_database_url_hostname_present": False,
    "test_database_url_port_present": False,
    "test_database_url_password_present": False,
    "pg_host_source": "owned_unix_socket_environment",
    "pg_host_required": True,
    "helper_operation": "string_rsplit_last_slash",
    "helper_database_name": "closure_phase4_cert",
    "helper_admin_database_name": "postgres",
    "helper_admin_database_rewrite_preserves_socket_routing": True,
    "test_database_url_serialized": False,
    "pg_host_value_serialized": False,
    "credentials_serialized": False,
    "absolute_paths_serialized": False,
}
POSTGRES_STARTUP_STABILITY_POLICY: Mapping[str, Any] = {
    "pid1_expected_executable": "postgres",
    "pid1_checked_before_readiness": True,
    "pid1_revalidated_after_socket_claim": True,
    "readiness_uses_explicit_socket_directory": True,
    "exact_socket_claim_count": 2,
    "same_claims_revalidated_before_return": True,
    "max_stability_attempts": 120,
    "stability_interval_seconds": 0.25,
    "retryable_inventory_states": ["empty", "expected_subset"],
    "unexpected_names_fail_closed": True,
    "unexpected_inode_types_fail_closed": True,
    "unexpected_link_counts_fail_closed": True,
    "claim_replacement_fails_closed": True,
    "recapture_after_stop_authorized": False,
    "arbitrary_residual_adoption_authorized": False,
    "observed_inventory_serialized": False,
    "container_identity_serialized": False,
    "absolute_paths_serialized": False,
    "container_binding_checked_before_and_after_probes": True,
    "readiness_revalidated_after_socket_claim": True,
    "pid1_probe_requires_exact_stdout_and_empty_stderr": True,
    "handoff_updated_with_same_container_identity_and_claims": True,
}
POSTGRES_CLEANUP_POLICY: Mapping[str, Any] = {
    "graceful_stop_required": True,
    "graceful_stop_timeout_seconds": 30,
    "stop_targets_exact_owned_container_id": True,
    "residual_entries": [
        {"name": ".s.PGSQL.5432", "kind": "socket"},
        {"name": ".s.PGSQL.5432.lock", "kind": "regular_file"},
    ],
    "residual_cleanup_requires_container_absent": True,
    "residual_cleanup_requires_retained_directory_fd": True,
    "residual_claim_fields": ["name", "kind", "device", "inode", "link_count"],
    "arbitrary_residual_adoption_authorized": False,
    "socket_directory_empty_after_cleanup_required": True,
    "safe_internal_diagnostics_authorized": True,
    "raw_internal_diagnostics_serialized": False,
}
SANDBOX_MOUNTPOINT_POLICY: Mapping[str, Any] = {
    "ordered_clone_relative_paths": [".venv", "tmp"],
    "initial_state_required": "absent",
    "creation_stage": "after_clone_registration_before_private_dvc_configuration",
    "required_kind": "empty_directory",
    "required_mode": "0700",
    "exclusive_creation_required": True,
    "retained_clone_directory_fd_required": True,
    "identity_revalidation_required": True,
    "git_ignored_required": True,
    "rollback_by_owned_inode_required": True,
    "frozen_with_clone_inventory": True,
    "symlink_or_existing_inode_adoption_authorized": False,
    "retained_python_exact_alias": "/cert-python",
    "retained_poetry_exact_root_alias": "/cert-poetry",
    "retained_alias_public_suite_only": True,
    "retained_alias_workspace_root": "/workspace",
    "retained_python_host_target_environment": (
        "CLOSURE_PHASE4_CERTIFICATION_RETAINED_PYTHON"
    ),
    "retained_python_host_target_required_under_usr": True,
    "retained_python_alias_matches_proc_self_exe_full_identity": True,
    "retained_python_alias_matches_injected_host_target_full_identity": True,
    "retained_poetry_alias_requires_same_python_context": True,
    "arbitrary_retained_runtime_alias_authorized": False,
    "absolute_paths_serialized": False,
}
SANDBOX_SMOKE_POLICY: Mapping[str, Any] = {
    "required": True,
    "stage": "sandbox_smoke",
    "portable_command": ["<SANDBOX_SMOKE>"],
    "uses_exact_bwrap_prefix": True,
    "runs_after_dvc_restore_and_clone_inventory_freeze": True,
    "runs_before_postgresql_start": True,
    "actual_touch_required": True,
    "marker_location": "owned_sandbox_tmp",
    "marker_created_through_workspace_tmp_mount": True,
    "marker_verified_and_removed_by_owned_inode": True,
    "expected_returncode": 0,
    "stdout_required_empty": True,
    "stderr_required_empty": True,
    "python_started": False,
    "pytest_started": False,
    "network_authorized": False,
}
CLEANUP_DIAGNOSTIC_POLICY: Mapping[str, Any] = {
    "allowed_reason_codes": [
        "database_owner_retained",
        "frozen_inventory_drift",
        "socket_inventory_nonempty",
        "owned_site_cache_drift",
        "sandbox_inventory_drift",
        "work_tree_remove_failed",
        "unclassified_cleanup_failure",
    ],
    "serialized_record_keys": ["status", "namespace_preserved", "reason_codes"],
    "raw_exception_text_serialized": False,
    "raw_stdout_serialized": False,
    "raw_stderr_serialized": False,
    "absolute_paths_serialized": False,
    "container_ids_serialized": False,
    "namespace_path_or_run_id_serialized": False,
}
POSTGRES_DESTROY_POLL_POLICY: Mapping[str, Any] = {
    "max_attempts": 120,
    "interval_seconds": 0.1,
    "single_stop_command": True,
    "mixed_presence_same_owned_identity_allowed": True,
    "double_absence_required": True,
    "foreign_identity_fails_closed": True,
    "socket_cleanup_after_double_absence": True,
    "timeout_preserves_owner": True,
}
TEST_ACCESS_GUARD_POLICY: Mapping[str, Any] = {
    "public_tests_boundary": "bubblewrap_hard_boundary",
    "public_tests_python_audit_hook": False,
    "openapi_python_audit_hook": True,
    "e2e_python_audit_hook": True,
}
P0_RESTORED_ONLY_SKIP_REASON = (
    "The ignored P0 payload is restored only in an authorized data workspace"
)
PUBLIC_TESTS_RAW_SKIP_REASON_ALIASES: Mapping[str, str] = {
    "tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_physical_schema_matches_closed_fields": P0_RESTORED_ONLY_SKIP_REASON,
    "tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_failure_is_read_only[early]": P0_RESTORED_ONLY_SKIP_REASON,
    "tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_failure_is_read_only[late]": P0_RESTORED_ONLY_SKIP_REASON,
    "tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_pass_is_read_only": P0_RESTORED_ONLY_SKIP_REASON,
    "tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_cli_is_repeatable_and_read_only": P0_RESTORED_ONLY_SKIP_REASON,
}
PUBLIC_TESTS_JUNIT_DIAGNOSTIC_POLICY: Mapping[str, Any] = {
    "enabled_on_nonzero_exit": True,
    "require_success": False,
    "source_filename": "public-tests-raw.xml",
    "max_junit_bytes": 16777216,
    "retained_sandbox_directory_fd_required": True,
    "fd_relative_no_follow_open_required": True,
    "regular_single_link_required": True,
    "identity_revalidated_before_and_after_read": True,
    "xml_doctype_forbidden": True,
    "xml_entity_declaration_forbidden": True,
    "duplicate_testcase_nodeid_policy": (
        "single_record_or_exact_failure_error_pair"
    ),
    "duplicate_testcase_pair_max_records": 2,
    "duplicate_testcase_pair_exact_outcomes": ["failure", "error"],
    "outside_sealed_suite_nodeids_forbidden": True,
    "unknown_elements_or_attributes_forbidden": True,
    "exact_collection_count_required": True,
    "exact_collection_digest_required": True,
    "exact_skip_ledger_required": True,
    "exact_skip_override_marker": "skipif_true",
    "exact_skip_override_prepend": True,
    "preexisting_skipif_precedence_neutralized": True,
    "exact_skip_reason_emitted_required": True,
    "raw_skip_reason_aliases": PUBLIC_TESTS_RAW_SKIP_REASON_ALIASES,
    "raw_skip_reason_alias_count": 5,
    "raw_skip_reason_aliases_canonicalized_before_ledger_validation": True,
    "pytest_declared_tests_teardown_error_counter_accounting": True,
    "declared_tests_minimum": "logical_testcase_identity_count",
    "declared_tests_maximum": (
        "logical_testcase_identity_count_plus_error_identity_count"
    ),
    "declared_failures_errors_skipped_exact": True,
    "serialized_fields": [
        "status",
        "returncode",
        "totals",
        "failed_nodeids",
        "failed_nodeids_sha256",
        "error_nodeids",
        "error_nodeids_sha256",
        "collected_test_count",
        "collected_nodeids_sha256",
        "unavailable_reason",
        "messages_preserved",
        "tracebacks_preserved",
        "raw_junit_preserved",
        "raw_stdout_preserved",
        "raw_stderr_preserved",
        "credentials_preserved",
        "absolute_paths_preserved",
    ],
    "failure_or_error_nodeids_sorted": True,
    "nodeid_digest_algorithm": "sha256_canonical_json",
    "available_status": "failure_identity_available",
    "unavailable_status": "failure_identity_unavailable",
    "unavailable_reasons": [
        "junit_absent",
        "junit_unsafe_identity",
        "junit_oversized",
        "junit_malformed_or_hostile",
        "junit_sealed_suite_drift",
    ],
    "messages_serialized": False,
    "tracebacks_serialized": False,
    "raw_junit_serialized": False,
    "raw_stdout_serialized": False,
    "raw_stderr_serialized": False,
    "absolute_paths_serialized": False,
    "credentials_serialized": False,
    "unavailable_does_not_mask_active_error": True,
    "composite_error_propagates_public_tests_failure": True,
}
OWNED_SITE_CACHE_ROLES = ("runtime_version", "restore_status")
OWNED_SITE_CACHE_FILESYSTEM_MODE = "0700"
LOCKED_SUITE_STATUS = "locked"
LOCKED_SUITE_SELECTOR_COUNT = 39
LOCKED_SUITE_COLLECTED_TEST_COUNT = 944
LOCKED_SUITE_NODEIDS_SHA256 = (
    "8422082eca90068bf6d6fff4f1e4d9b9964535e12c8fd6b0844658bbdf683349"
)
LOCKED_SUITE_ALLOWED_SKIP_COUNT = 42
P17_FAILED_NODEIDS = (
    "tests/test_build_phase4_final_certification.py::test_bwrap_effect_sources_are_retained_fd_paths_not_mutable_names",
    "tests/test_build_phase4_final_certification.py::test_dvc_executable_swap_is_detected_after_fd_anchored_invocation",
    "tests/test_build_phase4_final_certification.py::test_dvc_launcher_swap_never_executes_foreign_launcher",
    "tests/test_build_phase4_final_certification.py::test_dvc_restore_never_opens_or_reads_parquet_or_cache_payloads_in_python",
    "tests/test_build_phase4_final_certification.py::test_dvc_restore_uses_eight_exact_unit_commands_and_empty_private_cache",
    "tests/test_build_phase4_final_certification.py::test_global_dvc_status_always_disables_analytics",
    "tests/test_build_phase4_final_certification.py::test_runtime_dvc_version_probe_disables_analytics",
)
P17_FAILED_NODEIDS_SHA256 = (
    "e328bbeea535afadf98704170520cc4c38d660b7b89dee32fdbf9ba5ab776eb6"
)


class FinalCertificationContractError(RuntimeError):
    """Raised when the final Phase 4 certification contract drifts."""


@dataclass(frozen=True)
class PublicationPathSpec:
    path: str
    status: str
    git_mode: str


@dataclass(frozen=True)
class AnchorInputSpec:
    path: str
    role: str


@dataclass(frozen=True)
class DvcPointerSpec:
    path: str
    role: str
    output_path: str
    md5: str
    size: int


@dataclass(frozen=True)
class TestSuiteSpec:
    suite_kind: str
    positive_test_paths: tuple[str, ...]
    exact_skipped_nodes: tuple[str, ...]
    exact_skip_reason: str
    e2e_nodes: tuple[str, ...]
    command_template: tuple[str, ...]
    static_commands: tuple[tuple[str, ...], ...]
    status: str
    selector_count: int | None
    collected_test_count: int | None
    nodeids_sha256: str | None
    allowed_skip_count: int

    @property
    def supplemental_skipped_nodes(self) -> tuple[str, ...]:
        """Skipped nodes whose files are not already positive selectors."""

        selected_files = set(self.positive_test_paths)
        return tuple(
            node
            for node in self.exact_skipped_nodes
            if node.split("::", 1)[0] not in selected_files
        )

    @property
    def selectors(self) -> tuple[str, ...]:
        """Exact non-duplicating pytest selectors in command order."""

        return (*self.positive_test_paths, *self.supplemental_skipped_nodes)


@dataclass(frozen=True)
class FinalCertificationContract:
    path: Path
    raw: Mapping[str, Any]
    closure_source_commit: str
    r_syn_commit: str
    editorial_commit: str
    h1_cert_commit: str
    p1_cert_commit: str
    h2_cert_commit: str
    p2_cert_commit: str
    h3_cert_commit: str
    p3_cert_commit: str
    h4_cert_commit: str
    p4_cert_commit: str
    h5_cert_commit: str
    p5_cert_commit: str
    h6_cert_commit: str
    p6_cert_commit: str
    h7_cert_commit: str
    p7_cert_commit: str
    h8_cert_commit: str
    p8_cert_commit: str
    h9_cert_commit: str
    p9_cert_commit: str
    h10_cert_commit: str
    p10_cert_commit: str
    h11_cert_commit: str
    p11_cert_commit: str
    h12_cert_commit: str
    p12_cert_commit: str
    h14_cert_commit: str
    p14_cert_commit: str
    h15_cert_commit: str
    p15_cert_commit: str
    h16_cert_commit: str
    p16_cert_commit: str
    h17_cert_commit: str
    p17_cert_commit: str
    final_tag: str
    h1_scope: tuple[PublicationPathSpec, ...]
    p1_scope: tuple[PublicationPathSpec, ...]
    h2_scope: tuple[PublicationPathSpec, ...]
    p2_scope: tuple[PublicationPathSpec, ...]
    h3_scope: tuple[PublicationPathSpec, ...]
    p3_scope: tuple[PublicationPathSpec, ...]
    h4_scope: tuple[PublicationPathSpec, ...]
    p4_scope: tuple[PublicationPathSpec, ...]
    h5_scope: tuple[PublicationPathSpec, ...]
    p5_scope: tuple[PublicationPathSpec, ...]
    h6_scope: tuple[PublicationPathSpec, ...]
    p6_scope: tuple[PublicationPathSpec, ...]
    h7_scope: tuple[PublicationPathSpec, ...]
    p7_scope: tuple[PublicationPathSpec, ...]
    h8_scope: tuple[PublicationPathSpec, ...]
    p8_scope: tuple[PublicationPathSpec, ...]
    h9_scope: tuple[PublicationPathSpec, ...]
    p9_scope: tuple[PublicationPathSpec, ...]
    h10_scope: tuple[PublicationPathSpec, ...]
    p10_scope: tuple[PublicationPathSpec, ...]
    h11_scope: tuple[PublicationPathSpec, ...]
    p11_scope: tuple[PublicationPathSpec, ...]
    h12_scope: tuple[PublicationPathSpec, ...]
    p12_scope: tuple[PublicationPathSpec, ...]
    h13_scope: tuple[PublicationPathSpec, ...]
    p13_scope: tuple[PublicationPathSpec, ...]
    h14_scope: tuple[PublicationPathSpec, ...]
    p14_scope: tuple[PublicationPathSpec, ...]
    h15_scope: tuple[PublicationPathSpec, ...]
    p15_scope: tuple[PublicationPathSpec, ...]
    h16_scope: tuple[PublicationPathSpec, ...]
    p16_scope: tuple[PublicationPathSpec, ...]
    h17_scope: tuple[PublicationPathSpec, ...]
    p17_scope: tuple[PublicationPathSpec, ...]
    h_scope: tuple[PublicationPathSpec, ...]
    p_scope: tuple[PublicationPathSpec, ...]
    r_scope: tuple[PublicationPathSpec, ...]
    anchor_inputs: tuple[AnchorInputSpec, ...]
    dvc_pointers: tuple[DvcPointerSpec, ...]
    dvc_pull_command_template: tuple[str, ...]
    post_restore_status_pointer_paths: tuple[str, ...]
    post_verification_status_pointer_paths: tuple[str, ...]
    partial_clone_global_status_authorized: bool
    postgres_portable_path_policy: Mapping[str, Any]
    postgres_connection_policy: Mapping[str, Any]
    postgres_startup_stability_policy: Mapping[str, Any]
    postgres_cleanup_policy: Mapping[str, Any]
    sandbox_mountpoint_policy: Mapping[str, Any]
    sandbox_smoke_policy: Mapping[str, Any]
    cleanup_diagnostic_policy: Mapping[str, Any]
    public_tests_junit_diagnostic_policy: Mapping[str, Any]
    postgres_destroy_poll_policy: Mapping[str, Any]
    test_access_guard_policy: Mapping[str, Any]
    test_suite: TestSuiteSpec
    expected_openapi_path_count: int
    expected_openapi_operation_count: int
    expected_documented_operation_count: int
    forbidden_read_prefixes: tuple[str, ...]
    forbidden_read_paths: tuple[str, ...]
    forbidden_read_prefix_dispositions: Mapping[str, str]
    forbidden_read_path_dispositions: Mapping[str, str]
    output_paths: tuple[str, ...]
    expected_runtime_versions: Mapping[str, str]
    concurrency_lock: str
    legacy_guard_path_must_be_absent: str
    external_namespace_mutation_is_stop_condition: bool
    noncooperating_same_uid_namespace_mutation: str
    identity_revalidated_before_and_after_name_cleanup: bool
    conditional_unlink_by_inode_claimed: bool
    no_clobber: bool
    cleanup_before_precommit: bool
    failure_diagnostics: Mapping[str, bool]
    stop_rules: tuple[str, ...]

    @property
    def guard_path(self) -> str:
        """Compatibility alias for the forbidden legacy guard path."""

        return self.legacy_guard_path_must_be_absent

    @property
    def anchor_input_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.anchor_inputs)

    @property
    def dvc_pointer_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.dvc_pointers)

    @property
    def dvc_output_paths(self) -> tuple[str, ...]:
        return tuple(item.output_path for item in self.dvc_pointers)

    @property
    def suite_selectors(self) -> tuple[str, ...]:
        return self.test_suite.selectors


H1_SCOPE = (
    PublicationPathSpec(
        "configs/closure_v1/phase4_final_certification.schema.json",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "configs/closure_v1/phase4_final_certification.yaml", "A", "100644"
    ),
    PublicationPathSpec(
        "docs/closure_v1/PHASE4_FINAL_CERTIFICATION.md", "A", "100644"
    ),
    PublicationPathSpec(
        "src/data/prepare_commit_artifacts.py", "M", "100755"
    ),
    PublicationPathSpec(
        "src/experiments/lock_phase4_final_certification.py", "A", "100644"
    ),
    PublicationPathSpec(
        "src/reporting/build_phase4_final_certification.py", "A", "100644"
    ),
    PublicationPathSpec(
        "src/reporting/phase4_final_certification_contract.py",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "tests/test_build_phase4_final_certification.py", "A", "100644"
    ),
    PublicationPathSpec(
        "tests/test_lock_phase4_final_certification.py", "A", "100644"
    ),
    PublicationPathSpec(
        "tests/test_phase4_final_certification_contract.py", "A", "100644"
    ),
    PublicationPathSpec(
        "tests/test_prepare_commit_artifacts.py", "M", "100644"
    ),
)
P1_SCOPE = (
    PublicationPathSpec(H1_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H1_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H2_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P2_SCOPE = (
    PublicationPathSpec(H2_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H2_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H3_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P3_SCOPE = (
    PublicationPathSpec(H3_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H3_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H4_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P4_SCOPE = (
    PublicationPathSpec(H4_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H4_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H5_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P5_SCOPE = (
    PublicationPathSpec(H5_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H5_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H6_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P6_SCOPE = (
    PublicationPathSpec(H6_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H6_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H7_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P7_SCOPE = (
    PublicationPathSpec(H7_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H7_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H8_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P8_SCOPE = (
    PublicationPathSpec(H8_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H8_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H9_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P9_SCOPE = (
    PublicationPathSpec(H9_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H9_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H10_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P10_SCOPE = (
    PublicationPathSpec(H10_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H10_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H11_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P11_SCOPE = (
    PublicationPathSpec(H11_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H11_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H12_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P12_SCOPE = (
    PublicationPathSpec(H12_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H12_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H13_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P13_SCOPE = (
    PublicationPathSpec(H13_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H13_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H14_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P14_SCOPE = (
    PublicationPathSpec(H14_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H14_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H15_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P15_SCOPE = (
    PublicationPathSpec(H15_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H15_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H16_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P16_SCOPE = (
    PublicationPathSpec(H16_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H16_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H17_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P17_SCOPE = (
    PublicationPathSpec(H17_AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(H17_AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
H_SCOPE = tuple(
    PublicationPathSpec(item.path, "M", item.git_mode) for item in H1_SCOPE
)
P_SCOPE = (
    PublicationPathSpec(AUTHORITY_PATH.as_posix(), "A", "100644"),
    PublicationPathSpec(AUTHORITY_MANIFEST_PATH.as_posix(), "A", "100644"),
)
R15_SCOPE = (
    PublicationPathSpec(
        "reports/closure_v1/12_certification/public_tests.xml",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "reports/closure_v1/12_certification/test_report.md",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "reports/closure_v1/12_certification/openapi.json",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "reports/closure_v1/12_certification/openapi_contract_report.md",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "reports/closure_v1/12_certification/end_to_end_report.md",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "reports/closure_v1/12_certification/environment.json",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "reports/closure_v1/12_certification/FINAL_DOCTORAL_CERTIFICATION_REPORT.md",
        "A",
        "100644",
    ),
    PublicationPathSpec(
        "reports/closure_v1/12_certification/final_certification_manifest.json",
        "A",
        "100644",
    ),
)
R16_SCOPE = tuple(
    PublicationPathSpec(path, "A", "100644") for path in OUTPUT_PATHS
)
R17_SCOPE = tuple(
    PublicationPathSpec(path, "A", "100644") for path in OUTPUT_PATHS
)
R_SCOPE = tuple(
    PublicationPathSpec(path, "A", "100644") for path in OUTPUT_PATHS
)

ANCHOR_INPUTS = (
    AnchorInputSpec(".dvc/config", "tracked_dvc_cache_configuration"),
    AnchorInputSpec("docs/API_DATASET_CONTRACT.md", "documented_api_contract"),
    AnchorInputSpec("docs/API_PROTOCOL.md", "documented_api_contract"),
    AnchorInputSpec("poetry.lock", "dependency_lock"),
    AnchorInputSpec("pyproject.toml", "project_and_tool_configuration"),
    AnchorInputSpec(
        "reports/closure_v1/11_synthesis/THESIS_CLAIM_EVIDENCE_MATRIX.csv",
        "approved_claim_boundary",
    ),
    AnchorInputSpec(
        "reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json",
        "published_r_syn_manifest",
    ),
    AnchorInputSpec(
        "reports/thesis/chapter_iv_evidence_matrix_manifest.json",
        "published_editorial_matrix_manifest",
    ),
    AnchorInputSpec(
        "reports/thesis/phase4_manuscript_build_receipt.json",
        "published_private_manuscript_attestation",
    ),
    AnchorInputSpec(
        "reports/thesis/phase4_manuscript_build_receipt_manifest.json",
        "published_private_manuscript_attestation_manifest",
    ),
)

DVC_POINTERS = (
    DvcPointerSpec(
        "data/closure_v1/locked_evaluation/input_history.parquet.dvc",
        "locked_evaluation_scientific_input",
        "data/closure_v1/locked_evaluation/input_history.parquet",
        "d02d1b0b94f740ce990d06a7a949b09c",
        480855,
    ),
    DvcPointerSpec(
        "data/closure_v1/locked_evaluation/intent_origins.parquet.dvc",
        "locked_evaluation_scientific_input",
        "data/closure_v1/locked_evaluation/intent_origins.parquet",
        "b9bad06b799f342f9bf54eb0a2cbec7a",
        171047,
    ),
    DvcPointerSpec(
        "data/closure_v1/locked_evaluation/origin_features.parquet.dvc",
        "locked_evaluation_scientific_input",
        "data/closure_v1/locked_evaluation/origin_features.parquet",
        "da118c0515bdbd9705539bce1305bf11",
        238955,
    ),
    DvcPointerSpec(
        "data/closure_v1/locked_evaluation/sequence_features.parquet.dvc",
        "locked_evaluation_scientific_input",
        "data/closure_v1/locked_evaluation/sequence_features.parquet",
        "f858efff8a4c2e25f4c5b287258f0176",
        436677,
    ),
    DvcPointerSpec(
        "data/closure_v1/degradation_masks.parquet.dvc",
        "final_scientific_output",
        "data/closure_v1/degradation_masks.parquet",
        "c483aab92229b79d5f77d4024c768be6",
        6037,
    ),
    DvcPointerSpec(
        "data/closure_v1/predictions_long.parquet.dvc",
        "final_scientific_output",
        "data/closure_v1/predictions_long.parquet",
        "8674d3247c5aa1a866199881c1389332",
        1794498,
    ),
    DvcPointerSpec(
        "reports/closure_v1/05_inference/bootstrap_distributions.parquet.dvc",
        "final_scientific_output",
        "reports/closure_v1/05_inference/bootstrap_distributions.parquet",
        "59ea9456ed60a49013fee3e0d0088711",
        2380,
    ),
    DvcPointerSpec(
        "reports/closure_v1/09_planning/planning_origin_deltas.parquet.dvc",
        "final_scientific_output",
        "reports/closure_v1/09_planning/planning_origin_deltas.parquet",
        "f67f23c22af0056b67852cc645703d19",
        7788,
    ),
)

DVC_PULL_COMMAND_TEMPLATE = (
    ".venv/bin/dvc",
    "pull",
    "--no-run-cache",
    "-j",
    "1",
    "{pointer_path}",
)

POSITIVE_TEST_PATHS = (
    "tests/test_api_counterfactual_simulation.py",
    "tests/test_api_dataset_validation.py",
    "tests/test_api_experiment_scientific_datasets.py",
    "tests/test_api_job_science_adapters.py",
    "tests/test_api_minimal_workflow.py",
    "tests/test_api_predictions_alerts.py",
    "tests/test_api_run_artifacts.py",
    "tests/test_api_run_executor.py",
    "tests/test_api_run_planner.py",
    "tests/test_api_run_scientific_outputs.py",
    "tests/test_api_scientific_workflow_adapters.py",
    "tests/test_api_system.py",
    "tests/test_api_workspace_catalog.py",
    "tests/test_audit_closure_p0_model_availability.py",
    "tests/test_audit_closure_p0_sequence_bundle.py",
    "tests/test_build_closure_e10_source_evidence.py",
    "tests/test_build_closure_synthesis.py",
    "tests/test_build_phase4_final_certification.py",
    "tests/test_build_thesis_evidence_matrix.py",
    "tests/test_closure_e0_u_activation_lock.py",
    "tests/test_closure_e0_u_authority.py",
    "tests/test_closure_e6_e9_unavailable.py",
    "tests/test_closure_phase3_context.py",
    "tests/test_closure_phase3_e1_e2_e3_e5_contracts.py",
    "tests/test_closure_phase3_e4_e7_contracts.py",
    "tests/test_closure_phase3_e8_locked_uncertainty.py",
    "tests/test_closure_phase3_input_overlay.py",
    "tests/test_closure_synthesis_contract.py",
    "tests/test_lock_closure_synthesis.py",
    "tests/test_lock_phase4_final_certification.py",
    "tests/test_phase4_final_certification_contract.py",
    "tests/test_prepare_commit_artifacts.py",
    "tests/test_validate_phase4_manuscript.py",
)

EXACT_SKIPPED_NODES = (
    "tests/test_build_closure_holdout.py::test_protocol_lock_requires_the_exact_selector_hash",
    "tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[assignment_created-holdout_assignment_created=false]",
    "tests/test_build_closure_holdout.py::test_protocol_lock_requires_pre_assignment_clean_state[dirty_locked_repository-worktree_status='clean']",
    "tests/test_build_closure_holdout.py::test_cli_dry_run_does_not_read_panel_or_write_outputs",
    "tests/test_build_closure_synthesis.py::test_check_only_before_p_syn_is_non_writing",
    "tests/test_closure_final_calibration.py::test_lock_validation_rejects_authorization_and_boundary_drifts",
    "tests/test_closure_final_calibration.py::test_output_contract_is_exact_manifest_last_and_zero_overlap",
    "tests/test_api_predictions_alerts.py::test_api_exposes_pipe_grud_reference_predictions_and_alerts",
    "tests/test_api_predictions_alerts.py::test_api_exposes_neural_ode_reference_predictions_and_alerts",
    "tests/test_api_predictions_alerts.py::test_api_exposes_mifal_predictions_and_alerts",
    "tests/test_api_scientific_workflow_adapters.py::test_neural_ode_reference_profile_inference_adapter_writes_calibrated_rollouts",
    "tests/test_api_scientific_workflow_adapters.py::test_pipe_grud_adaptive_surface_adapter_writes_reference_ready_sequences",
    "tests/test_api_scientific_workflow_adapters.py::test_pipe_grud_expert_surface_inference_adapter_writes_diagnostic_rollouts",
    "tests/test_api_scientific_workflow_adapters.py::test_pipe_grud_reference_profile_inference_adapter_writes_calibrated_rollouts",
    "tests/test_api_scientific_workflow_adapters.py::test_counterfactual_planning_adapter_runs_v1_scenarios_from_upstream_temporal_run",
    "tests/test_api_scientific_workflow_adapters.py::test_pipe_grud_reference_adapter_writes_manifest_and_report",
    "tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_physical_schema_matches_closed_fields",
    "tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_failure_is_read_only[early]",
    "tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_failure_is_read_only[late]",
    "tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_pass_is_read_only",
    "tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_cli_is_repeatable_and_read_only",
    "tests/test_audit_closure_p0_model_availability.py::test_public_policy_and_five_published_slots_pass_read_only_audit",
    "tests/test_audit_closure_p0_model_availability.py::test_p0_evidence_chain_and_git_blobs_are_exact",
    "tests/test_audit_closure_p0_model_availability.py::test_denominator_authority_reconstructs_role_and_fit_counts",
    "tests/test_audit_closure_p0_model_availability.py::test_p0_namespace_is_exact_and_records_all_absences",
    "tests/test_audit_closure_p0_model_availability.py::test_audit_rejects_any_preregistered_registry_entry",
    "tests/test_audit_closure_p0_model_availability.py::test_registry_payload_is_non_self_authorizing_and_has_no_placeholder_values",
    "tests/test_audit_closure_p0_model_availability.py::test_companion_uses_generic_completed_manifest_dialect",
    "tests/test_audit_closure_p0_model_availability.py::test_registry_bundle_validator_reconstructs_every_authoritative_section",
    "tests/test_audit_closure_p0_model_availability.py::test_registry_bundle_validator_accepts_exact_reconstruction",
    "tests/test_audit_closure_p0_model_availability.py::test_check_only_never_invokes_remote_or_dvc",
    "tests/test_audit_closure_p0_model_availability.py::test_published_loader_is_the_only_effective_authority",
    "tests/test_audit_closure_p0_model_availability.py::test_published_loader_rejects_live_remote_divergence",
    "tests/test_audit_closure_p0_model_availability.py::test_published_loader_rechecks_all_post_registry_absence_gates[P1 materialization predates the P0 registry]",
    "tests/test_audit_closure_p0_model_availability.py::test_published_loader_rechecks_all_post_registry_absence_gates[E0-M outputs already exist]",
    "tests/test_audit_closure_p0_model_availability.py::test_published_loader_rechecks_all_post_registry_absence_gates[Outcome access log must remain absent]",
    "tests/test_audit_closure_p0_model_availability.py::test_published_loader_rechecks_all_post_registry_absence_gates[Registry bundle namespace is not pristine]",
    "tests/test_closure_phase3_context.py::test_real_input_only_registries_are_exact",
    "tests/test_closure_phase3_context.py::test_real_b2_input_only_scoring_accepts_arrow_backed_origin_values",
    "tests/test_closure_phase3_context.py::test_real_r10_eligibility_token_reaches_temporal_slots",
    "tests/test_closure_e0_u_authority.py::test_runner_and_authority_share_exact_capability_and_commit_contracts",
    "tests/test_api_scientific_workflow_adapters.py::test_neural_ode_preflight_adapter_writes_dataset_diagnostic",
)
EXACT_SKIP_REASON = "final_certification_sandbox_or_state_incompatible"
HISTORICAL_EXACT_SKIPPED_NODES = EXACT_SKIPPED_NODES[:7]
HISTORICAL_EXACT_SKIP_REASON = (
    "final_certification_raw_or_historical_state_prohibited"
)
E2E_NODES = (
    "tests/test_api_predictions_alerts.py::test_api_exposes_current_state_predictions_and_alerts",
    "tests/test_api_counterfactual_simulation.py::test_api_runs_minimal_current_state_counterfactual",
    "tests/test_api_run_artifacts.py::test_api_lists_previews_and_summarizes_run_artifacts",
)
TEST_COMMAND_TEMPLATE = (
    ".venv/bin/python",
    "-m",
    "pytest",
    "{selectors}",
    "-ra",
    "-p",
    "src.reporting.build_phase4_final_certification",
    "-p",
    "no:cacheprovider",
    "--junitxml={junit_path}",
)
STATIC_COMMANDS = ((".venv/bin/ty", "check"), ("poetry", "check", "--lock"))

FORBIDDEN_READ_PREFIXES = (
    "private/",
    "data/targets/",
    "data/closure_v1/unblinded/",
    "data/closure_v1/evaluation_outcomes/",
)
FORBIDDEN_READ_PATHS = (
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl",
)
FORBIDDEN_READ_PREFIX_DISPOSITIONS: Mapping[str, str] = {
    path: "require_absent" for path in FORBIDDEN_READ_PREFIXES
}
FORBIDDEN_READ_PATH_DISPOSITIONS: Mapping[str, str] = {
    FORBIDDEN_READ_PATHS[0]: "require_regular_then_empty_file_mask",
}

STOP_RULES = (
    "refs_or_live_remote_drift",
    "topology_scope_mode_or_blob_drift",
    "pending_or_changed_test_suite_lock",
    "attempt_to_execute_from_superseded_p1",
    "attempt_to_execute_from_superseded_p2",
    "attempt_to_execute_from_superseded_p3",
    "attempt_to_execute_from_superseded_p4",
    "attempt_to_execute_from_superseded_p5",
    "attempt_to_execute_from_superseded_p6",
    "attempt_to_execute_from_superseded_p7",
    "attempt_to_execute_from_superseded_p8",
    "attempt_to_execute_from_superseded_p9",
    "attempt_to_execute_from_superseded_p10",
    "attempt_to_execute_from_superseded_p11",
    "attempt_to_execute_from_superseded_p12",
    "attempt_to_execute_from_superseded_p14",
    "attempt_to_execute_from_superseded_p15",
    "attempt_to_execute_from_superseded_p16",
    "attempt_to_execute_from_superseded_p17",
    "effective_authority_alias_projection_drift",
    "unexpected_clone_directory_nlink_delta",
    "primary_error_loss_after_safe_cleanup_or_unowned_cleanup",
    "unsanitized_active_error_or_cleanup_failure_masking",
    "non_pristine_clone_or_cache",
    "forbidden_path_or_parquet_open",
    "dvc_pull_scope_or_pointer_drift",
    "partial_clone_global_dvc_status_or_status_sweep_scope_drift",
    "test_failure_error_or_unregistered_skip",
    "openapi_or_e2e_contract_drift",
    "existing_partial_or_extra_output",
    "credential_remote_url_database_url_or_absolute_path_leak",
    "postgres_portable_path_projection_drift",
    "postgres_connection_policy_drift",
    "postgres_startup_stability_policy_drift",
    "forbidden_read_path_kind_disposition_drift",
    "postgres_cleanup_ownership_or_identity_drift",
    "unsafe_internal_cleanup_diagnostics",
    "sandbox_mountpoint_policy_drift",
    "retained_runtime_alias_identity_drift",
    "sandbox_smoke_or_marker_cleanup_drift",
    "cleanup_diagnostic_reason_code_drift",
    "public_tests_junit_failure_diagnostic_policy_drift",
    "credential_fd_bridge_or_owned_site_cache_drift",
    "private_dvc_operational_cache_equivalence_drift",
    "credential_fd_exposure_before_first_directed_pull",
    "attempt_to_execute_dvc_in_main_worktree",
    "source_git_or_dvc_mutation",
    "attempt_to_run_e0_u_e1_e10_fit_score_or_calibration",
    "attempt_to_begin_post_phase4_work",
)

FAILURE_DIAGNOSTICS_POLICY: Mapping[str, bool] = {
    "sanitized_command_preservation_authorized": True,
    "returncode_preservation_authorized": True,
    "safe_stderr_category_preservation_authorized": True,
    "raw_stdout_preservation_authorized": False,
    "raw_stderr_preservation_authorized": False,
    "credentials_preservation_authorized": False,
    "absolute_paths_preservation_authorized": False,
    "nonexact_cleanup_preserves_namespace": True,
    "composite_error_identifies_sanitized_active_error": True,
    "composite_error_identifies_cleanup_failure": True,
}


def expected_p2_failure_record() -> dict[str, Any]:
    """Return the factual, sanitized record of the superseded R-CERT2 run."""

    first_pointer = DVC_POINTERS[0].path
    return {
        "status": "superseded_failed",
        "active_error": {
            "stage": "first_directed_dvc_pull",
            "sanitized_command": [
                ".venv/bin/dvc",
                "pull",
                "--no-run-cache",
                "-j",
                "1",
                first_pointer,
            ],
            "returncode": None,
            "safe_stderr_category": "unavailable_not_persisted",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "cleanup": {
            "status": "failed_closed",
            "namespace_preserved": True,
            "active_error_was_masked": True,
        },
        "retry_authorized": False,
    }


def expected_p3_failure_record() -> dict[str, Any]:
    """Return the exact sanitized record of the superseded R-CERT3 run."""

    return {
        "status": "execution_and_cleanup_failed_closed",
        "active_error": {
            "stage": "first_directed_dvc_pull",
            "sanitized_command": [
                ".venv/bin/dvc",
                "pull",
                "--no-run-cache",
                "-j",
                "1",
                DVC_POINTERS[0].path,
            ],
            "returncode": 1,
            "safe_stderr_category": "nonzero_exit",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "cleanup": {
            "status": "failed_closed",
            "namespace_preserved": True,
            "active_error_was_masked": False,
        },
        "evidence_counts": {
            "successful_directed_dvc_pulls": 0,
            "dvc_cache_objects": 0,
            "restored_payloads": 0,
            "directed_dvc_status_checks": 0,
            "public_test_runs": 0,
            "postgresql_fixture_starts": 0,
            "docker_runs": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "r_cert_outputs": 0,
        },
        "archived_under_ignored_tmp": True,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p4_failure_record() -> dict[str, Any]:
    """Return the exact public record of the consumed R-CERT4 launch."""

    return {
        "status": "execution_failed_closed_cleanup_succeeded",
        "attempt": "R-CERT4",
        "active_error": {
            "stage": "private_dvc_configuration_after_owned_cache_settings",
            "safe_error": "private DVC configuration section set drifted",
            "failure_kind": "in_process_validation",
            "sanitized_command": [],
            "returncode": None,
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "private_configuration_values_preserved": False,
            "absolute_paths_preserved": False,
        },
        "cleanup": {
            "status": "succeeded_exact",
            "namespace_preserved": False,
            "active_error_was_masked": False,
        },
        "evidence_counts": {
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 2,
            "successful_directed_dvc_pulls": 0,
            "directed_dvc_status_checks": 0,
            "dvc_cache_objects": 0,
            "restored_payloads": 0,
            "parquet_payloads_opened_or_decoded": 0,
            "raw_target_or_outcome_reads": 0,
            "public_test_runs": 0,
            "postgresql_fixture_starts": 0,
            "docker_version_commands": 2,
            "docker_container_runs": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "r_cert_outputs": 0,
        },
        "credential_fd_read_or_egress_evidence_preserved": False,
        "verifiable_dvc_payload_egress_commands": 0,
        "absolute_network_egress_claimed": False,
        "archived_under_ignored_tmp": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p5_failure_record() -> dict[str, Any]:
    """Return the conservative factual record of the consumed R-CERT5 launch."""

    return {
        "status": "execution_and_cleanup_failed_closed",
        "attempt": "R-CERT5",
        "active_error": {
            "stage": "execution",
            "sanitized_command": [],
            "returncode": None,
            "safe_stderr_category": "unavailable_not_persisted",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "cleanup": {
            "status": "failed_closed",
            "namespace_preserved": True,
            "active_error_was_masked": False,
        },
        "evidence_counts": {
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_status_checks_confirmed_minimum": 7,
            "directed_dvc_status_checks_confirmed_maximum": 8,
            "exact_directed_dvc_status_count_claimed": False,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "public_test_runs": 0,
            "postgresql_fixture_starts": 0,
            "docker_version_commands": 2,
            "docker_container_runs": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "r_cert_outputs": 0,
        },
        "namespace_archived_under_ignored_tmp": True,
        "namespace_path_or_run_id_serialized": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p6_failure_record() -> dict[str, Any]:
    """Return the factual record of the consumed R-CERT6 launch."""

    return {
        "status": "execution_failed_closed_cleanup_succeeded",
        "attempt": "R-CERT6",
        "active_error": {
            "stage": "postgres_start_portable_command_serialization",
            "safe_error": "absolute command paths may not be serialized",
            "failure_kind": "in_process_portable_command_serialization",
            "sanitized_command": [],
            "returncode": None,
            "safe_stderr_category": "unavailable_not_persisted",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "cleanup": {
            "status": "succeeded_exact",
            "namespace_preserved": False,
            "active_error_was_masked": False,
        },
        "evidence_counts": {
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "postgresql_fixture_starts": 0,
            "docker_version_commands": 2,
            "docker_container_runs": 0,
            "public_test_runs": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
        },
        "archived_under_ignored_tmp": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p7_failure_record() -> dict[str, Any]:
    """Return the conservative factual record of the consumed R-CERT7 launch."""

    return {
        "status": "execution_and_cleanup_failed_closed",
        "attempt": "R-CERT7",
        "active_error": {
            "stage": "sandbox_projection",
            "safe_error": "forbidden_path_kind_mismatch",
            "failure_kind": "in_process_sandbox_projection",
            "sanitized_command": [],
            "returncode": None,
            "safe_stderr_category": "unavailable_not_persisted",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "cleanup": {
            "status": "failed_closed",
            "namespace_preserved": True,
            "active_error_was_masked": False,
            "exact_owned_container_absent": True,
            "residual_entry_count": 2,
            "residual_owner_uid": 65534,
        },
        "evidence_counts": {
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "postgresql_fixture_starts": 1,
            "docker_version_commands": 2,
            "docker_container_runs": 1,
            "verification_runtime_acquisitions": 1,
            "sandbox_projection_failures": 1,
            "public_test_runs": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
        },
        "namespace_archived_under_ignored_tmp": True,
        "namespace_path_or_run_id_serialized": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p8_failure_record() -> dict[str, Any]:
    """Return the factual, sanitized record of the consumed R-CERT8 launch."""

    selected_files = set(POSITIVE_TEST_PATHS)
    supplemental = tuple(
        node
        for node in HISTORICAL_EXACT_SKIPPED_NODES
        if node.split("::", 1)[0] not in selected_files
    )
    public_command = [
        ".venv/bin/python",
        "-m",
        "pytest",
        *POSITIVE_TEST_PATHS,
        *supplemental,
        "-ra",
        "-q",
        "-p",
        "src.reporting.build_phase4_final_certification",
        "-p",
        "no:cacheprovider",
        "--junitxml=tmp/public-tests-raw.xml",
    ]
    return {
        "status": "execution_and_cleanup_failed_closed",
        "attempt": "R-CERT8",
        "active_error": {
            "stage": "public_tests",
            "sanitized_command": public_command,
            "returncode": 1,
            "safe_stderr_category": "nonzero_exit",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "observed_cause": {
            "stage": "bubblewrap_mount_projection",
            "safe_error": "required_mountpoints_absent_under_read_only_clone",
            "missing_clone_relative_mountpoints": [".venv", "tmp"],
            "python_started": False,
            "pytest_started": False,
            "junit_written": False,
            "raw_diagnostic_preserved": False,
            "absolute_paths_preserved": False,
        },
        "cleanup": {
            "status": "failed_closed",
            "namespace_preserved": True,
            "active_error_was_masked": False,
            "reason_codes": ["unclassified_cleanup_failure"],
            "exact_owned_container_absent": True,
            "socket_directory_empty": True,
        },
        "evidence_counts": {
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "postgresql_fixture_starts": 1,
            "docker_version_commands": 2,
            "docker_container_runs": 1,
            "verification_runtime_acquisitions": 1,
            "bubblewrap_process_runs": 1,
            "sandbox_smoke_runs": 0,
            "python_process_starts": 0,
            "pytest_process_starts": 0,
            "public_test_runs": 0,
            "public_tests_collected": 0,
            "public_tests_executed": 0,
            "junit_artifacts": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
        },
        "namespace_archived_under_ignored_tmp": True,
        "namespace_path_or_run_id_serialized": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p9_failure_record() -> dict[str, Any]:
    """Return the factual, sanitized record of the consumed R-CERT9 launch."""

    selected_files = set(POSITIVE_TEST_PATHS)
    supplemental = tuple(
        node
        for node in HISTORICAL_EXACT_SKIPPED_NODES
        if node.split("::", 1)[0] not in selected_files
    )
    public_command = [
        ".venv/bin/python", "-m", "pytest", *POSITIVE_TEST_PATHS, *supplemental,
        "-ra", "-q", "-p", "src.reporting.build_phase4_final_certification",
        "-p", "no:cacheprovider", "--junitxml=tmp/public-tests-raw.xml",
    ]
    return {
        "status": "execution_and_cleanup_failed_closed",
        "attempt": "R-CERT9",
        "active_error": {
            "stage": "public_tests",
            "sanitized_command": public_command,
            "returncode": 1,
            "safe_stderr_category": "nonzero_exit",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "observed_cause": {
            "stage": "public_tests",
            "safe_error": "registered_suite_failures_errors_and_state_skips",
            "total": 944,
            "passed": 857,
            "failures": 65,
            "errors": 1,
            "skipped": 21,
            "junit_written": True,
            "raw_diagnostic_serialized": False,
            "absolute_paths_serialized": False,
        },
        "cleanup": {
            "status": "failed_closed",
            "namespace_preserved": True,
            "active_error_was_masked": False,
            "reason_codes": ["database_owner_retained"],
            "exact_owned_container_absent": False,
            "socket_directory_empty": False,
        },
        "evidence_counts": {
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "postgresql_fixture_starts": 1,
            "docker_version_commands": 2,
            "docker_container_runs": 1,
            "verification_runtime_acquisitions": 1,
            "bubblewrap_process_runs": 2,
            "sandbox_smoke_runs": 1,
            "python_process_starts": 1,
            "pytest_process_starts": 1,
            "public_test_runs": 1,
            "public_test_cases_reported": 944,
            "public_test_passes": 857,
            "public_test_failures": 65,
            "public_test_errors": 1,
            "public_test_skips": 21,
            "junit_artifacts": 1,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
        },
        "namespace_archived_under_ignored_tmp": True,
        "namespace_path_or_run_id_serialized": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p10_failure_record() -> dict[str, Any]:
    """Return the factual, sanitized record of the consumed R-CERT10 launch."""

    selected_files = set(POSITIVE_TEST_PATHS)
    supplemental = tuple(
        node
        for node in HISTORICAL_EXACT_SKIPPED_NODES
        if node.split("::", 1)[0] not in selected_files
    )
    public_command = [
        ".venv/bin/python", "-m", "pytest", *POSITIVE_TEST_PATHS, *supplemental,
        "-ra", "-q", "-p", "src.reporting.build_phase4_final_certification",
        "-p", "no:cacheprovider", "--junitxml=tmp/public-tests-raw.xml",
    ]
    unexpected_nodeids = [
        "tests/test_phase4_final_certification_contract.py::"
        "test_every_contract_boundary_fails_closed[<lambda>25]",
        "tests/test_phase4_final_certification_contract.py::"
        "test_every_contract_boundary_fails_closed[<lambda>26]",
    ]
    return {
        "status": "execution_failed_closed_cleanup_succeeded",
        "attempt": "R-CERT10",
        "active_error": {
            "stage": "public_tests",
            "sanitized_command": public_command,
            "returncode": 3,
            "safe_stderr_category": "nonzero_exit",
            "pytest_exit_category": "INTERNAL_ERROR",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "observed_cause": {
            "stage": "public_tests_collection",
            "safe_error": "sealed_suite_collection_count_and_digest_drift",
            "sealed_collected_test_count": 944,
            "sealed_nodeids_sha256": (
                "8422082eca90068bf6d6fff4f1e4d9b9964535e12c8fd6b0844658bbdf683349"
            ),
            "observed_collected_test_count": 946,
            "observed_nodeids_sha256": (
                "644bc8548b730c98a62773dcc01622a6d5322ffabbcc31aa0e63b12275df9295"
            ),
            "unexpected_nodeids": unexpected_nodeids,
            "deterministic_postmortem": True,
            "final_junit_preserved": False,
            "raw_diagnostic_serialized": False,
            "absolute_paths_serialized": False,
        },
        "cleanup": {
            "status": "succeeded_exact",
            "namespace_preserved": False,
            "active_error_was_masked": False,
            "reason_codes": [],
            "exact_owned_container_absent": True,
            "socket_directory_empty": True,
        },
        "evidence_counts": {
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "postgresql_fixture_starts": 1,
            "docker_version_commands": 2,
            "docker_container_runs": 1,
            "verification_runtime_acquisitions": 1,
            "bubblewrap_process_runs": 2,
            "sandbox_smoke_runs": 1,
            "python_process_starts": 1,
            "pytest_process_starts": 1,
            "public_test_runs": 1,
            "public_tests_collected": 946,
            "public_tests_executed": 0,
            "final_junit_artifacts": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
        },
        "namespace_archived_under_ignored_tmp": False,
        "namespace_path_or_run_id_serialized": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p11_failure_record() -> dict[str, Any]:
    """Return the factual, sanitized record of the consumed R-CERT11 launch."""

    selected_files = set(POSITIVE_TEST_PATHS)
    supplemental = tuple(
        node
        for node in HISTORICAL_EXACT_SKIPPED_NODES
        if node.split("::", 1)[0] not in selected_files
    )
    public_command = [
        ".venv/bin/python", "-m", "pytest", *POSITIVE_TEST_PATHS, *supplemental,
        "-ra", "-q", "-p", "src.reporting.build_phase4_final_certification",
        "-p", "no:cacheprovider", "--junitxml=tmp/public-tests-raw.xml",
    ]
    return {
        "status": "execution_failed_closed_cleanup_succeeded",
        "attempt": "R-CERT11",
        "active_error": {
            "stage": "public_tests",
            "sanitized_command": public_command,
            "returncode": 1,
            "safe_stderr_category": "nonzero_exit",
            "pytest_exit_category": "TESTS_FAILED",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "observed_cause": {
            "stage": "public_tests_fixture_setup",
            "safe_error": "naive_database_url_rsplit_misparsed_unix_socket_query",
            "affected_test_nodeid": (
                "tests/test_api_experiment_scientific_datasets.py::"
                "test_register_experiment_scientific_dataset_creates_sql_and_science_links"
            ),
            "helper_operation": "string_rsplit_last_slash",
            "configured_database_name": "closure_phase4_cert",
            "derived_database_name": "cert-db",
            "derived_admin_database_name": "closure_phase4_cert",
            "derived_admin_host_basename": "postgres",
            "derived_admin_host_was_root_absolute": True,
            "deterministic_source_postmortem": True,
            "final_junit_preserved": False,
            "raw_diagnostic_serialized": False,
            "database_url_serialized": False,
            "absolute_paths_serialized": False,
        },
        "cleanup": {
            "status": "succeeded_exact",
            "namespace_preserved": False,
            "active_error_was_masked": False,
            "reason_codes": [],
            "exact_owned_container_absent": True,
            "socket_directory_empty": True,
        },
        "evidence_counts": {
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "postgresql_fixture_starts": 1,
            "docker_version_commands": 2,
            "docker_container_runs": 1,
            "verification_runtime_acquisitions": 1,
            "bubblewrap_process_runs": 2,
            "sandbox_smoke_runs": 1,
            "python_process_starts": 1,
            "pytest_process_starts": 1,
            "public_test_runs": 1,
            "public_tests_collected": 944,
            "public_tests_executed_exact_count_known": False,
            "public_tests_executed_lower_bound": 1,
            "public_test_totals_preserved": False,
            "final_junit_artifacts": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
        },
        "namespace_archived_under_ignored_tmp": False,
        "namespace_path_or_run_id_serialized": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p12_failure_record() -> dict[str, Any]:
    """Return the factual, sanitized record of the consumed R-CERT12 launch."""

    return {
        "status": "execution_failed_closed_cleanup_succeeded",
        "attempt": "R-CERT12",
        "active_error": {
            "stage": "postgres_startup_socket_inventory",
            "safe_error": "socket_inventory_not_exact_two",
            "failure_kind": "in_process_post_readiness_socket_inventory_validation",
            "sanitized_launcher_command": [
                ".venv/bin/python",
                "src/reporting/build_phase4_final_certification.py",
                "--build",
            ],
            "launcher_returncode": 1,
            "sanitized_command": [],
            "returncode": None,
            "safe_stderr_category": "socket_inventory_not_exact_two",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "observed_cause": {
            "stage": "postgres_startup_socket_inventory",
            "safe_error": "socket_inventory_not_exact_two",
            "readiness_success_observed": True,
            "readiness_probe_total_exact_count_known": False,
            "readiness_probe_total_lower_bound": 1,
            "successful_readiness_probes": 1,
            "socket_inventory_capture_attempts": 1,
            "expected_socket_inventory_cardinality": 2,
            "observed_socket_inventory_cardinality_preserved": False,
            "observed_socket_inventory_entries_serialized": False,
            "socket_claims_captured": 0,
            "deterministic_control_flow_postmortem": True,
            "raw_diagnostic_serialized": False,
            "absolute_paths_serialized": False,
        },
        "cleanup": {
            "status": "succeeded_exact",
            "namespace_preserved": False,
            "active_error_was_masked": False,
            "reason_codes": [],
            "exact_owned_container_absent": True,
            "socket_directory_empty": True,
            "relevant_processes_absent": True,
            "postgres_listener_absent": True,
        },
        "evidence_counts": {
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "postgresql_fixture_starts": 1,
            "docker_version_commands": 2,
            "docker_container_runs": 1,
            "verification_runtime_acquisitions": 1,
            "bubblewrap_process_runs": 1,
            "sandbox_smoke_runs": 1,
            "successful_postgres_readiness_probes": 1,
            "postgres_readiness_probe_total_exact_count_known": False,
            "postgres_readiness_probe_total_lower_bound": 1,
            "postgres_socket_inventory_capture_attempts": 1,
            "postgres_socket_claims_captured": 0,
            "docker_container_stop_commands": 1,
            "python_process_starts": 0,
            "pytest_process_starts": 0,
            "public_test_runs": 0,
            "public_tests_collected": 0,
            "public_tests_executed": 0,
            "final_junit_artifacts": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
        },
        "namespace_archived_under_ignored_tmp": False,
        "namespace_path_or_run_id_serialized": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_h13_failure_record() -> dict[str, Any]:
    """Return the factual record of the unpublished H-CERT13 invalidation."""

    return {
        "status": "publication_candidate_invalidated_failed_closed",
        "attempt": "H-CERT13",
        "active_error": {
            "stage": "main_worktree_dvc_command_boundary",
            "safe_error": "manual_main_dvc_status_violated_absolute_boundary",
            "failure_kind": "prohibited_main_worktree_dvc_command",
            "sanitized_command": [".venv/bin/dvc", "status", "--json"],
            "returncode": 0,
            "safe_stdout_category": "empty_json_object",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "observed_cause": {
            "main_dvc_command_run": True,
            "main_dvc_status_command_run": True,
            "command_was_read_only": True,
            "stdout_semantic": {},
            "absolute_main_dvc_boundary_violated": True,
            "public_git_worktree_index_change_attributable": False,
            "ignored_dvc_metadata_mutation_assessed": False,
            "report_paths_serialized": False,
            "report_hashes_serialized": False,
            "temporary_reports_are_authority": False,
        },
        "evidence_counts": {
            "h13_check_only_runs": 3,
            "h13_check_only_passes": 3,
            "h13_precommit_invocations": 3,
            "h13_precommit_passes": 2,
            "h13_precommit_rejections": 1,
            "h13_precommit_rejection_returncode": 2,
            "ignored_tmp_precommit_reports": 2,
            "git_restore_staged_invocations": 2,
            "git_restore_staged_paths_per_invocation": 11,
            "manual_main_dvc_status_commands": 1,
            "dvc_add_commands": 0,
            "dvc_push_commands": 0,
            "h13_commits": 0,
            "h13_pushes": 0,
            "p13_files_generated": 0,
            "r13_execution_runs": 0,
            "r13_outputs_generated": 0,
            "certification_execution_runs": 0,
            "postgresql_fixture_starts": 0,
            "docker_commands": 0,
            "raw_target_or_outcome_reads": 0,
            "scientific_payload_reads": 0,
            "parquet_payloads_opened_or_decoded": 0,
        },
        "h13_commit_published": False,
        "p13_commit_published": False,
        "retry_authorized": False,
    }


def expected_p14_failure_record() -> dict[str, Any]:
    """Return the factual record of the R-CERT14 preflight rejection."""

    return {
        "status": "preflight_failed_closed_execution_not_started",
        "attempt": "R-CERT14",
        "active_error": {
            "stage": "effective_authority_alias_projection_preflight",
            "safe_error": "projected_effective_authority_omitted_h13_p13_aliases",
            "failure_kind": "non_idempotent_effective_authority_projection",
            "sanitized_command": [
                ".venv/bin/python",
                "src/reporting/build_phase4_final_certification.py",
                "--check-only",
            ],
            "returncode": 1,
            "safe_stderr_category": "missing_required_null_h13_p13_aliases",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "observed_cause": {
            "strict_loader_returned_h13_p13_aliases_as_null": True,
            "authority_projection_validated_raw_aliases_before_projection": True,
            "authority_projection_preserved_h13_p13_aliases": False,
            "second_validation_required_present_null_aliases": True,
            "published_p14_authority_corrupted": False,
            "deterministic_source_postmortem": True,
            "raw_diagnostic_serialized": False,
            "absolute_paths_serialized": False,
        },
        "operator_diagnostic": {
            "stage": "wrong_locker_check_only_invocation",
            "sanitized_command": [
                ".venv/bin/python",
                "src/experiments/lock_phase4_final_certification.py",
                "--check-only",
            ],
            "returncode": 2,
            "read_only": True,
            "used_as_authority": False,
        },
        "evidence_counts": {
            "wrong_locker_check_only_invocations": 1,
            "builder_check_only_invocations": 1,
            "builder_check_only_failures": 1,
            "r14_execution_runs": 0,
            "isolated_git_clones": 0,
            "dvc_commands": 0,
            "postgresql_fixture_starts": 0,
            "docker_commands": 0,
            "public_test_runs": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
            "runtime_guards_created": 0,
            "runtime_namespaces_created": 0,
            "raw_target_or_outcome_reads": 0,
            "scientific_payload_reads": 0,
            "parquet_payloads_opened_or_decoded": 0,
        },
        "p14_authority_remains_immutable": True,
        "retry_authorized": False,
    }


def expected_p15_failure_record() -> dict[str, Any]:
    """Return the factual, sanitized record of the consumed R-CERT15 launch."""

    selected_files = set(POSITIVE_TEST_PATHS)
    supplemental = tuple(
        node
        for node in HISTORICAL_EXACT_SKIPPED_NODES
        if node.split("::", 1)[0] not in selected_files
    )
    public_command = [
        ".venv/bin/python",
        "-m",
        "pytest",
        *POSITIVE_TEST_PATHS,
        *supplemental,
        "-ra",
        "-q",
        "-p",
        "src.reporting.build_phase4_final_certification",
        "-p",
        "no:cacheprovider",
        "--junitxml=tmp/public-tests-raw.xml",
    ]
    return {
        "status": "execution_failed_closed_cleanup_succeeded",
        "attempt": "R-CERT15",
        "active_error": {
            "stage": "public_tests",
            "sanitized_command": public_command,
            "returncode": 1,
            "safe_stderr_category": "nonzero_exit",
            "pytest_exit_category": "TESTS_FAILED",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "observed_cause": {
            "stage": "public_tests",
            "safe_error": "public_test_failure_identity_not_persisted",
            "failure_kind": "nonzero_public_test_process_without_safe_junit_postmortem",
            "underlying_cause_known": False,
            "failure_nodeids_known": False,
            "error_nodeids_known": False,
            "public_test_totals_known": False,
            "sealed_suite_collection_count": LOCKED_SUITE_COLLECTED_TEST_COUNT,
            "sealed_suite_nodeids_sha256": LOCKED_SUITE_NODEIDS_SHA256,
            "sealed_suite_identity_remains_defensible": True,
            "executed_case_identity_inferred_from_sealed_suite": False,
            "deterministic_runner_postmortem": True,
            "final_junit_preserved": False,
            "raw_junit_preserved": False,
            "raw_diagnostic_serialized": False,
            "absolute_paths_serialized": False,
        },
        "cleanup": {
            "status": "succeeded_exact",
            "namespace_preserved": False,
            "active_error_was_masked": False,
            "reason_codes": [],
            "exact_owned_container_absent": True,
            "socket_directory_empty": True,
        },
        "evidence_counts": {
            "r15_execution_runs": 1,
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "postgresql_fixture_starts": 1,
            "docker_version_commands": 2,
            "docker_container_runs": 1,
            "verification_runtime_acquisitions": 1,
            "bubblewrap_process_runs": 2,
            "sandbox_smoke_runs": 1,
            "python_process_starts": 1,
            "pytest_process_starts": 1,
            "public_test_runs": 1,
            "public_tests_collected": LOCKED_SUITE_COLLECTED_TEST_COUNT,
            "public_tests_executed_exact_count_known": False,
            "public_tests_executed_lower_bound": 1,
            "public_test_totals_preserved": False,
            "final_junit_artifacts": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
        },
        "namespace_archived_under_ignored_tmp": False,
        "namespace_path_or_run_id_serialized": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p16_failure_record() -> dict[str, Any]:
    """Return the factual, sanitized record of the consumed R-CERT16 launch."""

    selected_files = set(POSITIVE_TEST_PATHS)
    supplemental = tuple(
        node
        for node in HISTORICAL_EXACT_SKIPPED_NODES
        if node.split("::", 1)[0] not in selected_files
    )
    public_command = [
        ".venv/bin/python",
        "-m",
        "pytest",
        *POSITIVE_TEST_PATHS,
        *supplemental,
        "-ra",
        "-q",
        "-p",
        "src.reporting.build_phase4_final_certification",
        "-p",
        "no:cacheprovider",
        "--junitxml=tmp/public-tests-raw.xml",
    ]
    return {
        "status": "execution_failed_closed_cleanup_succeeded",
        "attempt": "R-CERT16",
        "active_error": {
            "stage": "public_tests",
            "sanitized_command": public_command,
            "returncode": 1,
            "safe_stderr_category": "nonzero_exit",
            "pytest_exit_category": "TESTS_FAILED",
            "public_tests_failure": {
                "status": "failure_identity_unavailable",
                "returncode": 1,
                "totals": {},
                "failed_nodeids": [],
                "failed_nodeids_sha256": digest_strings(()),
                "error_nodeids": [],
                "error_nodeids_sha256": digest_strings(()),
                "collected_test_count": None,
                "collected_nodeids_sha256": None,
                "unavailable_reason": "junit_malformed_or_hostile",
                "messages_preserved": False,
                "tracebacks_preserved": False,
                "raw_junit_preserved": False,
                "raw_stdout_preserved": False,
                "raw_stderr_preserved": False,
                "credentials_preserved": False,
                "absolute_paths_preserved": False,
            },
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "observed_cause": {
            "stage": "public_tests",
            "safe_error": "public_test_failure_identity_unavailable",
            "failure_kind": "strict_junit_diagnostic_rejected",
            "unavailable_reason": "junit_malformed_or_hostile",
            "underlying_test_cause_known": False,
            "failure_nodeids_known": False,
            "error_nodeids_known": False,
            "public_test_totals_known": False,
            "sealed_suite_collection_count": LOCKED_SUITE_COLLECTED_TEST_COUNT,
            "sealed_suite_nodeids_sha256": LOCKED_SUITE_NODEIDS_SHA256,
            "sealed_suite_identity_remains_defensible": True,
            "executed_case_identity_inferred_from_sealed_suite": False,
            "deterministic_runner_postmortem": True,
            "junit_diagnostic_attempted_before_cleanup": True,
            "final_junit_preserved": False,
            "raw_junit_preserved": False,
            "raw_diagnostic_serialized": False,
            "absolute_paths_serialized": False,
        },
        "cleanup": {
            "status": "succeeded_exact",
            "namespace_preserved": False,
            "active_error_was_masked": False,
            "reason_codes": [],
            "exact_owned_container_absent": True,
            "socket_directory_empty": True,
        },
        "evidence_counts": {
            "r16_execution_runs": 1,
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "postgresql_fixture_starts": 1,
            "docker_version_commands": 2,
            "docker_container_runs": 1,
            "verification_runtime_acquisitions": 1,
            "bubblewrap_process_runs": 2,
            "sandbox_smoke_runs": 1,
            "python_process_starts": 1,
            "pytest_process_starts": 1,
            "public_test_runs": 1,
            "public_tests_collected_expected": LOCKED_SUITE_COLLECTED_TEST_COUNT,
            "public_tests_collected_observed_known": False,
            "public_tests_executed_exact_count_known": False,
            "public_tests_executed_lower_bound": 1,
            "public_test_totals_preserved": False,
            "raw_junit_read_attempts": 1,
            "safe_junit_projections_available": 0,
            "safe_junit_projections_unavailable": 1,
            "final_junit_artifacts": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
        },
        "namespace_archived_under_ignored_tmp": False,
        "namespace_path_or_run_id_serialized": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_p17_failure_record() -> dict[str, Any]:
    """Return the factual, sanitized record of the consumed R-CERT17 launch."""

    selected_files = set(POSITIVE_TEST_PATHS)
    supplemental = tuple(
        node
        for node in HISTORICAL_EXACT_SKIPPED_NODES
        if node.split("::", 1)[0] not in selected_files
    )
    public_command = [
        ".venv/bin/python",
        "-m",
        "pytest",
        *POSITIVE_TEST_PATHS,
        *supplemental,
        "-ra",
        "-q",
        "-p",
        "src.reporting.build_phase4_final_certification",
        "-p",
        "no:cacheprovider",
        "--junitxml=tmp/public-tests-raw.xml",
    ]
    totals = {
        "tests": 944,
        "passed": 895,
        "failures": 7,
        "errors": 0,
        "skipped": 42,
    }
    return {
        "status": "execution_failed_closed_cleanup_succeeded",
        "attempt": "R-CERT17",
        "active_error": {
            "stage": "public_tests",
            "sanitized_command": public_command,
            "returncode": 1,
            "safe_stderr_category": "nonzero_exit",
            "pytest_exit_category": "TESTS_FAILED",
            "public_tests_failure": {
                "status": "failure_identity_available",
                "returncode": 1,
                "totals": totals,
                "failed_nodeids": list(P17_FAILED_NODEIDS),
                "failed_nodeids_sha256": P17_FAILED_NODEIDS_SHA256,
                "error_nodeids": [],
                "error_nodeids_sha256": digest_strings(()),
                "collected_test_count": LOCKED_SUITE_COLLECTED_TEST_COUNT,
                "collected_nodeids_sha256": LOCKED_SUITE_NODEIDS_SHA256,
                "unavailable_reason": None,
                "messages_preserved": False,
                "tracebacks_preserved": False,
                "raw_junit_preserved": False,
                "raw_stdout_preserved": False,
                "raw_stderr_preserved": False,
                "credentials_preserved": False,
                "absolute_paths_preserved": False,
            },
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        },
        "observed_cause": {
            "stage": "public_tests",
            "safe_error": "retained_sandbox_python_alias_rejected",
            "failure_kind": "lexical_system_python_guard_rejected_exact_retained_alias",
            "underlying_test_cause_known": True,
            "failure_nodeids_known": True,
            "error_nodeids_known": True,
            "public_test_totals_known": True,
            "common_pre_run_interpreter_guard_cause": True,
            "dvc_runtime_or_payload_failure_observed": False,
            "sealed_suite_collection_count": LOCKED_SUITE_COLLECTED_TEST_COUNT,
            "sealed_suite_nodeids_sha256": LOCKED_SUITE_NODEIDS_SHA256,
            "sealed_suite_identity_remains_defensible": True,
            "executed_case_identity_inferred_from_sealed_suite": False,
            "deterministic_runner_postmortem": True,
            "junit_diagnostic_available_before_cleanup": True,
            "final_junit_preserved": False,
            "raw_junit_preserved": False,
            "raw_diagnostic_serialized": False,
            "absolute_paths_serialized": False,
        },
        "cleanup": {
            "status": "succeeded_exact",
            "namespace_preserved": False,
            "active_error_was_masked": False,
            "reason_codes": [],
            "exact_owned_container_absent": True,
            "socket_directory_empty": True,
        },
        "evidence_counts": {
            "r17_execution_runs": 1,
            "live_remote_and_refs_validated": True,
            "isolated_git_clones": 1,
            "dvc_version_commands": 1,
            "dvc_local_config_commands": 2,
            "dvc_config_commands_receiving_credential_fd_set": 0,
            "successful_directed_dvc_pulls": 8,
            "dvc_cache_objects": 8,
            "restored_checkouts": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "parquet_payloads_opened_or_decoded_by_python": 0,
            "raw_target_or_outcome_reads": 0,
            "postgresql_fixture_starts": 1,
            "docker_version_commands": 2,
            "docker_container_runs": 1,
            "verification_runtime_acquisitions": 1,
            "bubblewrap_process_runs": 2,
            "sandbox_smoke_runs": 1,
            "python_process_starts": 1,
            "pytest_process_starts": 1,
            "public_test_runs": 1,
            "public_tests_collected_expected": LOCKED_SUITE_COLLECTED_TEST_COUNT,
            "public_tests_collected_observed": LOCKED_SUITE_COLLECTED_TEST_COUNT,
            "public_tests_executed_exact_count_known": True,
            "public_tests_executed": LOCKED_SUITE_COLLECTED_TEST_COUNT,
            "public_test_totals_preserved": True,
            "public_test_failures_preserved": 7,
            "public_test_errors_preserved": 0,
            "raw_junit_read_attempts": 1,
            "safe_junit_projections_available": 1,
            "safe_junit_projections_unavailable": 0,
            "final_junit_artifacts": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_payload_builds": 0,
            "r_cert_outputs": 0,
        },
        "namespace_archived_under_ignored_tmp": False,
        "namespace_path_or_run_id_serialized": False,
        "archive_is_authority": False,
        "retry_authorized": False,
    }


def expected_postgres_connection_policy() -> dict[str, Any]:
    """Return query-free DSN semantics without serializing URL or socket paths."""

    return dict(POSTGRES_CONNECTION_POLICY)


def expected_postgres_startup_stability_policy() -> dict[str, Any]:
    """Return the exact redacted PID1/readiness/socket stability policy."""

    return {
        **POSTGRES_STARTUP_STABILITY_POLICY,
        "retryable_inventory_states": list(
            cast(
                Sequence[str],
                POSTGRES_STARTUP_STABILITY_POLICY["retryable_inventory_states"],
            )
        ),
    }


def expected_postgres_portable_path_policy() -> dict[str, Any]:
    """Return the exact path-redaction projection for PostgreSQL evidence."""

    return dict(POSTGRES_PORTABLE_PATH_POLICY)


def expected_postgres_cleanup_policy() -> dict[str, Any]:
    """Return the exact fail-closed PostgreSQL ownership cleanup policy."""

    return {
        **POSTGRES_CLEANUP_POLICY,
        "residual_entries": [
            dict(record)
            for record in cast(
                Sequence[Mapping[str, Any]], POSTGRES_CLEANUP_POLICY["residual_entries"]
            )
        ],
        "residual_claim_fields": list(
            cast(Sequence[str], POSTGRES_CLEANUP_POLICY["residual_claim_fields"])
        ),
    }


def expected_sandbox_mountpoint_policy() -> dict[str, Any]:
    """Return the exact clone-local mountpoint preparation policy."""

    return {
        **SANDBOX_MOUNTPOINT_POLICY,
        "ordered_clone_relative_paths": list(
            cast(
                Sequence[str],
                SANDBOX_MOUNTPOINT_POLICY["ordered_clone_relative_paths"],
            )
        ),
    }


def expected_sandbox_smoke_policy() -> dict[str, Any]:
    """Return the exact pre-PostgreSQL bubblewrap smoke policy."""

    return {
        **SANDBOX_SMOKE_POLICY,
        "portable_command": list(
            cast(Sequence[str], SANDBOX_SMOKE_POLICY["portable_command"])
        ),
    }


def expected_cleanup_diagnostic_policy() -> dict[str, Any]:
    """Return the exact path-free cleanup diagnostic allowlist."""

    return {
        **CLEANUP_DIAGNOSTIC_POLICY,
        "allowed_reason_codes": list(
            cast(
                Sequence[str], CLEANUP_DIAGNOSTIC_POLICY["allowed_reason_codes"]
            )
        ),
        "serialized_record_keys": list(
            cast(
                Sequence[str], CLEANUP_DIAGNOSTIC_POLICY["serialized_record_keys"]
            )
        ),
    }


def expected_postgres_destroy_poll_policy() -> dict[str, Any]:
    """Return the exact bounded Docker destroy-poll policy."""

    return dict(POSTGRES_DESTROY_POLL_POLICY)


def expected_test_access_guard_policy() -> dict[str, Any]:
    """Return the split bubblewrap/audit-hook verification policy."""

    return dict(TEST_ACCESS_GUARD_POLICY)


def expected_public_tests_junit_diagnostic_policy() -> dict[str, Any]:
    """Return the exact bounded, path-free failed-public-test JUnit policy."""

    return {
        **PUBLIC_TESTS_JUNIT_DIAGNOSTIC_POLICY,
        "serialized_fields": list(
            cast(
                Sequence[str],
                PUBLIC_TESTS_JUNIT_DIAGNOSTIC_POLICY["serialized_fields"],
            )
        ),
        "unavailable_reasons": list(
            cast(
                Sequence[str],
                PUBLIC_TESTS_JUNIT_DIAGNOSTIC_POLICY["unavailable_reasons"],
            )
        ),
        "raw_skip_reason_aliases": dict(
            cast(
                Mapping[str, str],
                PUBLIC_TESTS_JUNIT_DIAGNOSTIC_POLICY["raw_skip_reason_aliases"],
            )
        ),
        "duplicate_testcase_pair_exact_outcomes": list(
            cast(
                Sequence[str],
                PUBLIC_TESTS_JUNIT_DIAGNOSTIC_POLICY[
                    "duplicate_testcase_pair_exact_outcomes"
                ],
            )
        ),
    }

AUTHORIZATION_POLICY: Mapping[str, bool] = {
    "certification_execution_authorized_after_publication": True,
    "isolated_clone_authorized": True,
    "directed_dvc_pull_authorized": True,
    "public_test_execution_authorized": True,
    "openapi_generation_authorized": True,
    "synthetic_e2e_authorized": True,
    "loopback_postgresql_fixture_authorized": True,
    "main_worktree_dvc_mutation_authorized": False,
    "dvc_add_authorized": False,
    "dvc_push_authorized": False,
    "git_commit_push_tag_authorized": False,
    "raw_outcome_access_authorized": False,
    "raw_target_access_authorized": False,
    "parquet_open_or_decode_authorized": False,
    "model_fit_or_reconstruction_authorized": False,
    "rescore_or_recalibrate_authorized": False,
    "rerun_e0_u_or_e1_e10_authorized": False,
    "post_phase4_work_authorized": False,
}
PROHIBITIONS: Mapping[str, bool] = {
    "main_worktree_mutation": True,
    "main_worktree_dvc_command_execution": True,
    "owned_site_cache_paths_serialization": True,
    "main_dvc_site_cache_payload_open_or_hash": True,
    "owned_site_cache_role_or_separation_drift": True,
    "private_dvc_configuration_or_pull_before_version_seal": True,
    "dvc_runtime_cross_call_identity_or_lifetime_drift": True,
    "private_dvc_operational_cache_equivalence_drift": True,
    "credential_fd_exposure_before_first_directed_pull": True,
    "partial_clone_global_dvc_status": True,
    "dvc_status_sweep_scope_or_order_drift": True,
    "postgres_portable_path_projection_drift": True,
    "postgres_connection_policy_drift": True,
    "postgres_startup_stability_policy_drift": True,
    "forbidden_read_path_kind_disposition_drift": True,
    "postgres_cleanup_ownership_or_identity_drift": True,
    "unsafe_internal_cleanup_diagnostics": True,
    "sandbox_mountpoint_policy_drift": True,
    "sandbox_smoke_or_marker_cleanup_drift": True,
    "cleanup_diagnostic_reason_code_drift": True,
    "public_tests_junit_failure_diagnostic_policy_drift": True,
    "raw_or_outcome_access": True,
    "parquet_open_or_decode": True,
    "dvc_add_or_push": True,
    "model_fit_reconstruction_rescore_or_recalibration": True,
    "rerun_e0_u_or_e1_e10": True,
    "git_commit_push_or_tag_by_orchestrator": True,
    "post_phase4_work": True,
}


def _error(message: str) -> FinalCertificationContractError:
    return FinalCertificationContractError(message)


def canonical_json_bytes(payload: Any) -> bytes:
    """Encode canonical JSON with one trailing LF and no NaN values."""

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


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def digest_strings(values: Sequence[str]) -> str:
    return sha256_bytes(canonical_json_bytes(list(values)))


def digest_records(records: Sequence[Mapping[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(list(records)))


def expected_h_scope() -> dict[str, str]:
    """Return the operational H-CERT18 scope (legacy adapter alias)."""

    return {item.path: item.status for item in H_SCOPE}


def expected_p_scope() -> dict[str, str]:
    """Return the operational P-CERT18 scope (legacy adapter alias)."""

    return {item.path: item.status for item in P_SCOPE}


def expected_r_scope() -> dict[str, str]:
    return {item.path: item.status for item in R_SCOPE}


def expected_h1_scope() -> dict[str, str]:
    return {item.path: item.status for item in H1_SCOPE}


def expected_p1_scope() -> dict[str, str]:
    return {item.path: item.status for item in P1_SCOPE}


def expected_h2_scope() -> dict[str, str]:
    return {item.path: item.status for item in H2_SCOPE}


def expected_p2_scope() -> dict[str, str]:
    return {item.path: item.status for item in P2_SCOPE}


def expected_h3_scope() -> dict[str, str]:
    return {item.path: item.status for item in H3_SCOPE}


def expected_p3_scope() -> dict[str, str]:
    return {item.path: item.status for item in P3_SCOPE}


def expected_h4_scope() -> dict[str, str]:
    return {item.path: item.status for item in H4_SCOPE}


def expected_p4_scope() -> dict[str, str]:
    return {item.path: item.status for item in P4_SCOPE}


def expected_h5_scope() -> dict[str, str]:
    return {item.path: item.status for item in H5_SCOPE}


def expected_p5_scope() -> dict[str, str]:
    return {item.path: item.status for item in P5_SCOPE}


def expected_h6_scope() -> dict[str, str]:
    return {item.path: item.status for item in H6_SCOPE}


def expected_p6_scope() -> dict[str, str]:
    return {item.path: item.status for item in P6_SCOPE}


def expected_h7_scope() -> dict[str, str]:
    return {item.path: item.status for item in H7_SCOPE}


def expected_p7_scope() -> dict[str, str]:
    return {item.path: item.status for item in P7_SCOPE}


def expected_h8_scope() -> dict[str, str]:
    return {item.path: item.status for item in H8_SCOPE}


def expected_p8_scope() -> dict[str, str]:
    return {item.path: item.status for item in P8_SCOPE}


def expected_h9_scope() -> dict[str, str]:
    return {item.path: item.status for item in H9_SCOPE}


def expected_p9_scope() -> dict[str, str]:
    return {item.path: item.status for item in P9_SCOPE}


def expected_h10_scope() -> dict[str, str]:
    return {item.path: item.status for item in H10_SCOPE}


def expected_p10_scope() -> dict[str, str]:
    return {item.path: item.status for item in P10_SCOPE}


def expected_h11_scope() -> dict[str, str]:
    return {item.path: item.status for item in H11_SCOPE}


def expected_p11_scope() -> dict[str, str]:
    return {item.path: item.status for item in P11_SCOPE}


def expected_h12_scope() -> dict[str, str]:
    return {item.path: item.status for item in H12_SCOPE}


def expected_p12_scope() -> dict[str, str]:
    return {item.path: item.status for item in P12_SCOPE}


def expected_h13_scope() -> dict[str, str]:
    return {item.path: item.status for item in H13_SCOPE}


def expected_p13_scope() -> dict[str, str]:
    return {item.path: item.status for item in P13_SCOPE}


def expected_h14_scope() -> dict[str, str]:
    return {item.path: item.status for item in H14_SCOPE}


def expected_p14_scope() -> dict[str, str]:
    return {item.path: item.status for item in P14_SCOPE}


def expected_h15_scope() -> dict[str, str]:
    return {item.path: item.status for item in H15_SCOPE}


def expected_p15_scope() -> dict[str, str]:
    return {item.path: item.status for item in P15_SCOPE}


def expected_r15_scope() -> dict[str, str]:
    return {item.path: item.status for item in R15_SCOPE}


def expected_h16_scope() -> dict[str, str]:
    return {item.path: item.status for item in H16_SCOPE}


def expected_p16_scope() -> dict[str, str]:
    return {item.path: item.status for item in P16_SCOPE}


def expected_r16_scope() -> dict[str, str]:
    return {item.path: item.status for item in R16_SCOPE}


def expected_h17_scope() -> dict[str, str]:
    return {item.path: item.status for item in H17_SCOPE}


def expected_p17_scope() -> dict[str, str]:
    return {item.path: item.status for item in P17_SCOPE}


def expected_r17_scope() -> dict[str, str]:
    return {item.path: item.status for item in R17_SCOPE}


def expected_h_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H_SCOPE}


def expected_p_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P_SCOPE}


def expected_h9_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H9_SCOPE}


def expected_p9_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P9_SCOPE}


def expected_h10_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H10_SCOPE}


def expected_p10_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P10_SCOPE}


def expected_h11_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H11_SCOPE}


def expected_p11_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P11_SCOPE}


def expected_h12_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H12_SCOPE}


def expected_p12_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P12_SCOPE}


def expected_h13_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H13_SCOPE}


def expected_p13_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P13_SCOPE}


def expected_h14_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H14_SCOPE}


def expected_p14_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P14_SCOPE}


def expected_h15_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H15_SCOPE}


def expected_p15_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P15_SCOPE}


def expected_r15_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in R15_SCOPE}


def expected_h16_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H16_SCOPE}


def expected_p16_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P16_SCOPE}


def expected_r16_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in R16_SCOPE}


def expected_h17_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H17_SCOPE}


def expected_p17_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P17_SCOPE}


def expected_r17_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in R17_SCOPE}


def expected_r_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in R_SCOPE}


def expected_h1_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H1_SCOPE}


def expected_p1_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P1_SCOPE}


def expected_h2_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H2_SCOPE}


def expected_p2_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P2_SCOPE}


def expected_h3_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H3_SCOPE}


def expected_p3_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P3_SCOPE}


def expected_h4_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H4_SCOPE}


def expected_p4_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P4_SCOPE}


def expected_h5_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H5_SCOPE}


def expected_p5_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P5_SCOPE}


def expected_h6_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H6_SCOPE}


def expected_p6_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P6_SCOPE}


def expected_h7_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H7_SCOPE}


def expected_p7_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P7_SCOPE}


def expected_h8_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in H8_SCOPE}


def expected_p8_modes() -> dict[str, str]:
    return {item.path: item.git_mode for item in P8_SCOPE}


def _require_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error(f"{context} must be a mapping")
    return cast(Mapping[str, Any], value)


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], *, context: str
) -> None:
    observed = set(value)
    if observed != expected:
        raise _error(
            f"{context} keys drifted: expected {sorted(expected)}, "
            f"observed {sorted(observed)}"
        )


def _require_list(value: Any, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise _error(f"{context} must be a list")
    return value


def _require_text(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise _error(f"{context} must be non-empty trimmed text")
    return value


def _require_int(value: Any, *, context: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise _error(f"{context} must be an integer >= {minimum}")
    return value


def _require_string_tuple(value: Any, *, context: str) -> tuple[str, ...]:
    result = _require_string_sequence(value, context=context)
    if len(result) != len(set(result)):
        raise _error(f"{context} contains duplicates")
    return result


def _require_string_sequence(value: Any, *, context: str) -> tuple[str, ...]:
    """Parse an ordered string sequence whose command flags may repeat."""

    return tuple(
        _require_text(item, context=f"{context}[{index}]")
        for index, item in enumerate(_require_list(value, context=context))
    )


def _safe_relative_path(value: str, *, context: str) -> PurePosixPath:
    if "\\" in value or "\x00" in value or any(
        marker in value for marker in ("*", "?", "[", "]", "{", "}")
    ):
        raise _error(f"{context} is not one literal POSIX path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise _error(f"{context} is not a normalized repository-relative path")
    return path


def _parse_scope(
    value: Any,
    *,
    stage: str,
    expected: tuple[PublicationPathSpec, ...],
) -> tuple[PublicationPathSpec, ...]:
    mapping = _require_mapping(value, context=f"publication_scopes.{stage}")
    _require_exact_keys(
        mapping,
        {"additions", "modifications", "ordered_paths"},
        context=f"publication_scopes.{stage}",
    )
    rows = _require_list(
        mapping["ordered_paths"],
        context=f"publication_scopes.{stage}.ordered_paths",
    )
    parsed: list[PublicationPathSpec] = []
    for index, raw in enumerate(rows):
        row = _require_mapping(raw, context=f"{stage} scope row {index}")
        _require_exact_keys(
            row, {"path", "status", "git_mode"}, context=f"{stage} scope row {index}"
        )
        path = _require_text(row["path"], context=f"{stage} scope path")
        _safe_relative_path(path, context=f"{stage} scope path")
        status = _require_text(row["status"], context=f"{stage} scope status")
        mode = _require_text(row["git_mode"], context=f"{stage} scope mode")
        if status not in {"A", "M"} or mode not in {"100644", "100755"}:
            raise _error(f"{stage} scope status or mode drifted")
        parsed.append(PublicationPathSpec(path, status, mode))
    result = tuple(parsed)
    additions = sum(item.status == "A" for item in result)
    modifications = sum(item.status == "M" for item in result)
    if (
        additions != _require_int(mapping["additions"], context=f"{stage} additions")
        or modifications
        != _require_int(mapping["modifications"], context=f"{stage} modifications")
        or result != expected
    ):
        raise _error(f"{stage} publication scope drifted")
    return result


def _parse_anchor_inputs(value: Any) -> tuple[AnchorInputSpec, ...]:
    records: list[AnchorInputSpec] = []
    for index, raw in enumerate(_require_list(value, context="anchor_inputs")):
        row = _require_mapping(raw, context=f"anchor_inputs[{index}]")
        _require_exact_keys(row, {"path", "role"}, context=f"anchor_inputs[{index}]")
        path = _require_text(row["path"], context=f"anchor_inputs[{index}].path")
        _safe_relative_path(path, context="anchor input path")
        records.append(
            AnchorInputSpec(
                path,
                _require_text(row["role"], context=f"anchor_inputs[{index}].role"),
            )
        )
    result = tuple(records)
    if result != ANCHOR_INPUTS:
        raise _error("Final-certification anchor input allowlist drifted")
    return result


def _parse_dvc_specs(value: Any) -> tuple[DvcPointerSpec, ...]:
    records: list[DvcPointerSpec] = []
    for index, raw in enumerate(_require_list(value, context="DVC pointers")):
        row = _require_mapping(raw, context=f"DVC pointer {index}")
        _require_exact_keys(
            row,
            {"path", "role", "output_path", "md5", "size"},
            context=f"DVC pointer {index}",
        )
        path = _require_text(row["path"], context=f"DVC pointer {index} path")
        output_path = _require_text(
            row["output_path"], context=f"DVC pointer {index} output"
        )
        _safe_relative_path(path, context="DVC pointer path")
        _safe_relative_path(output_path, context="DVC output path")
        md5 = _require_text(row["md5"], context=f"DVC pointer {index} md5")
        if not path.endswith(".parquet.dvc") or not output_path.endswith(".parquet"):
            raise _error("Final-certification DVC path dialect drifted")
        if MD5_RE.fullmatch(md5) is None:
            raise _error("Final-certification DVC md5 drifted")
        records.append(
            DvcPointerSpec(
                path,
                _require_text(row["role"], context=f"DVC pointer {index} role"),
                output_path,
                md5,
                _require_int(row["size"], context=f"DVC pointer {index} size", minimum=1),
            )
        )
    result = tuple(records)
    if result != DVC_POINTERS:
        raise _error("Final-certification exact-eight DVC inventory drifted")
    return result


def _parse_static_commands(value: Any) -> tuple[tuple[str, ...], ...]:
    commands = tuple(
        _require_string_tuple(raw, context=f"static_commands[{index}]")
        for index, raw in enumerate(
            _require_list(value, context="test_certification.static_commands")
        )
    )
    if commands != STATIC_COMMANDS:
        raise _error("Final-certification static command registry drifted")
    return commands


def _parse_test_suite(
    value: Any, *, allow_pending_suite: bool
) -> TestSuiteSpec:
    mapping = _require_mapping(value, context="test_certification")
    _require_exact_keys(
        mapping,
        {
            "suite_kind",
            "positive_test_paths",
            "exact_skipped_nodes",
            "exact_skip_reason",
            "e2e_nodes",
            "command_template",
            "static_commands",
            "loopback_postgresql_required",
            "unexpected_skips_authorized",
            "failures_or_errors_authorized",
            "suite_lock",
        },
        context="test_certification",
    )
    positive = _require_string_tuple(
        mapping["positive_test_paths"], context="positive_test_paths"
    )
    skipped = _require_string_tuple(
        mapping["exact_skipped_nodes"], context="exact_skipped_nodes"
    )
    e2e = _require_string_tuple(mapping["e2e_nodes"], context="e2e_nodes")
    command = _require_string_sequence(
        mapping["command_template"], context="test command template"
    )
    static_commands = _parse_static_commands(mapping["static_commands"])
    if (
        mapping["suite_kind"] != "closure_phase4_final_public"
        or positive != POSITIVE_TEST_PATHS
        or skipped != EXACT_SKIPPED_NODES
        or mapping["exact_skip_reason"] != EXACT_SKIP_REASON
        or e2e != E2E_NODES
        or command != TEST_COMMAND_TEMPLATE
        or static_commands != STATIC_COMMANDS
        or mapping["loopback_postgresql_required"] is not True
        or mapping["unexpected_skips_authorized"] is not False
        or mapping["failures_or_errors_authorized"] is not False
    ):
        raise _error("Final-certification public test contract drifted")
    lock = _require_mapping(mapping["suite_lock"], context="suite_lock")
    _require_exact_keys(
        lock,
        {
            "status",
            "selector_count",
            "collected_test_count",
            "nodeids_sha256",
            "allowed_skip_count",
        },
        context="suite_lock",
    )
    status = _require_text(lock["status"], context="suite_lock.status")
    allowed_skips = _require_int(
        lock["allowed_skip_count"], context="suite_lock.allowed_skip_count"
    )
    if (
        allowed_skips != LOCKED_SUITE_ALLOWED_SKIP_COUNT
        or allowed_skips != len(EXACT_SKIPPED_NODES)
    ):
        raise _error("Final-certification skip count drifted")

    selected_files = set(positive)
    supplemental = tuple(
        node for node in skipped if node.split("::", 1)[0] not in selected_files
    )
    exact_selector_count = len(positive) + len(supplemental)
    if status == "pending_integration":
        if any(
            lock[key] is not None
            for key in ("selector_count", "collected_test_count", "nodeids_sha256")
        ):
            raise _error("Pending suite lock must use null count and digest fields")
        if not allow_pending_suite:
            raise _error(
                "Final-certification suite lock is pending integration; "
                "seal count and node-id digest before H-CERT publication"
            )
        selector_count: int | None = None
        collected_test_count: int | None = None
        nodeids_sha256: str | None = None
    elif status == LOCKED_SUITE_STATUS:
        selector_count = _require_int(
            lock["selector_count"], context="suite_lock.selector_count", minimum=1
        )
        collected_test_count = _require_int(
            lock["collected_test_count"],
            context="suite_lock.collected_test_count",
            minimum=allowed_skips + 1,
        )
        nodeids_sha256 = _require_text(
            lock["nodeids_sha256"], context="suite_lock.nodeids_sha256"
        )
        if (
            selector_count != LOCKED_SUITE_SELECTOR_COUNT
            or exact_selector_count != LOCKED_SUITE_SELECTOR_COUNT
            or nodeids_sha256 != LOCKED_SUITE_NODEIDS_SHA256
            or SHA256_RE.fullmatch(nodeids_sha256) is None
        ):
            raise _error("Locked final-certification suite identity drifted")
        if collected_test_count != LOCKED_SUITE_COLLECTED_TEST_COUNT:
            raise _error("Locked final-certification collected count drifted")
    else:
        raise _error("Final-certification suite status is unsupported")

    return TestSuiteSpec(
        suite_kind="closure_phase4_final_public",
        positive_test_paths=positive,
        exact_skipped_nodes=skipped,
        exact_skip_reason=EXACT_SKIP_REASON,
        e2e_nodes=e2e,
        command_template=command,
        static_commands=static_commands,
        status=status,
        selector_count=selector_count,
        collected_test_count=collected_test_count,
        nodeids_sha256=nodeids_sha256,
        allowed_skip_count=allowed_skips,
    )


def expected_environment_dvc_record() -> dict[str, Any]:
    """Return the exact public ``environment.json.dvc`` projection."""

    return {
        "restored_pointer_count": len(DVC_POINTERS),
        "cache_initially_empty": True,
        "one_pointer_per_pull": True,
        "main_dvc_command_run": False,
        "main_dvc_status_command_run": False,
        "main_dvc_static_reconstruction_from_git_and_published_pointers": True,
        "owned_site_cache_count": 2,
        "owned_site_cache_roles": list(OWNED_SITE_CACHE_ROLES),
        "owned_site_cache_filesystem_mode": OWNED_SITE_CACHE_FILESYSTEM_MODE,
        "owned_site_caches_separated": True,
        "owned_site_cache_paths_serialized": False,
        "version_seal_before_private_config_or_pull": True,
        "single_dvc_runtime_retained_through_final_status_and_version_probe": True,
        "dvc_runtime_cross_call_identity_revalidated": True,
        "operational_cache_fields_normalized_before_section_set_equivalence": True,
        "only_owned_cache_dir_and_type_may_differ": True,
        "credential_fds_passed_to_dvc_config_commands": False,
        "first_credential_fd_subprocess_exposure": "first_directed_dvc_pull",
        "post_restore_status_pointer_paths": [
            item.path for item in DVC_POINTERS
        ],
        "post_verification_status_pointer_paths": [
            item.path for item in DVC_POINTERS
        ],
        "partial_clone_global_status_authorized": False,
        "main_dvc_site_cache_metadata_inode_inventory_unchanged": True,
        "payloads_opened_by_python": False,
        "payloads_decoded": False,
        "dvc_add_or_push": False,
        "main_worktree_written": False,
    }


def expected_manifest_clone_dvc_site_caches_record() -> dict[str, Any]:
    """Return the exact public ``manifest.clone.dvc_site_caches`` projection."""

    return {
        "owned_site_cache_count": 2,
        "owned_site_cache_roles": list(OWNED_SITE_CACHE_ROLES),
        "owned_site_cache_filesystem_mode": OWNED_SITE_CACHE_FILESYSTEM_MODE,
        "owned_site_caches_separated": True,
        "used_by_all_isolated_dvc_commands": True,
        "copied_core_site_cache_dir_used": False,
        "owned_site_cache_paths_serialized": False,
        "version_seal_before_private_config_or_pull": True,
        "single_dvc_runtime_retained_through_final_status_and_version_probe": True,
        "dvc_runtime_cross_call_identity_revalidated": True,
        "operational_cache_fields_normalized_before_section_set_equivalence": True,
        "only_owned_cache_dir_and_type_may_differ": True,
        "credential_fds_passed_to_dvc_config_commands": False,
        "first_credential_fd_subprocess_exposure": "first_directed_dvc_pull",
        "post_restore_status_pointer_paths": [
            item.path for item in DVC_POINTERS
        ],
        "post_verification_status_pointer_paths": [
            item.path for item in DVC_POINTERS
        ],
        "partial_clone_global_status_authorized": False,
    }


def expected_dvc_status_policy(
    contract: FinalCertificationContract,
) -> dict[str, Any]:
    """Return the exact status policy for the intentionally partial DVC clone."""

    ordered = list(contract.dvc_pointer_paths)
    return {
        "scope": "exact_eight_published_pointer_paths",
        "target_count": 8,
        "ordered_targets": ordered,
        "post_restore_status_pointer_paths": list(
            contract.post_restore_status_pointer_paths
        ),
        "post_verification_status_pointer_paths": list(
            contract.post_verification_status_pointer_paths
        ),
        "global_status_authorized": False,
        "final_status_empty_result_required": True,
    }


def _expected_topology() -> Mapping[str, Any]:
    return {
        "ordered_stages": [
            "H-CERT1",
            "P-CERT1",
            "H-CERT2",
            "P-CERT2",
            "H-CERT3",
            "P-CERT3",
            "H-CERT4",
            "P-CERT4",
            "H-CERT5",
            "P-CERT5",
            "H-CERT6",
            "P-CERT6",
            "H-CERT7",
            "P-CERT7",
            "R-CERT7",
            "H-CERT8",
            "P-CERT8",
            "R-CERT8",
            "H-CERT9",
            "P-CERT9",
            "R-CERT9",
            "H-CERT10",
            "P-CERT10",
            "R-CERT10",
            "H-CERT11",
            "P-CERT11",
            "R-CERT11",
            "H-CERT12",
            "P-CERT12",
            "R-CERT12",
            "H-CERT13",
            "P-CERT13",
            "R-CERT13",
            "H-CERT14",
            "P-CERT14",
            "R-CERT14",
            "H-CERT15",
            "P-CERT15",
            "R-CERT15",
            "H-CERT16",
            "P-CERT16",
            "R-CERT16",
            "H-CERT17",
            "P-CERT17",
            "R-CERT17",
            "H-CERT18",
            "P-CERT18",
            "R-CERT18",
        ],
        "H-CERT1": {
            "role": "historical_initial_implementation_schema_tests_and_freeze",
            "commit": "h1_cert_commit",
            "direct_parent": "editorial_commit",
            "certification_execution_authorized": False,
        },
        "P-CERT1": {
            "role": "superseded_failed_final_certification_authority",
            "commit": "p1_cert_commit",
            "requires_published_H_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "after_git_clone_namespace_validation",
            "dvc_pull_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "manifest_written_last": True,
        },
        "H-CERT2": {
            "role": "corrective_runtime_contract_tests_and_freeze",
            "commit": "h2_cert_commit",
            "direct_parent": "p1_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "post_clone_nlink_delta_exact_one",
                "clone_registered_for_early_cleanup",
                "primary_error_preserved_when_safe_cleanup_passes",
            ],
        },
        "P-CERT2": {
            "role": "data_only_final_certification_authority_v2",
            "commit": "p2_cert_commit",
            "requires_published_H_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "first_directed_dvc_pull",
            "dvc_pull_success_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "failed_closed_namespace_preserved",
            "manifest_written_last": True,
        },
        "H-CERT3": {
            "role": "corrective_failure_diagnostics_contract_tests_and_freeze",
            "commit": "h3_cert_commit",
            "direct_parent": "p2_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "do_not_adopt_failed_dvc_partial_tree_for_cleanup",
                "sanitize_active_verification_error",
                "preserve_namespace_and_emit_composite_on_nonexact_cleanup",
            ],
        },
        "P-CERT3": {
            "role": "data_only_final_certification_authority_v3",
            "commit": "p3_cert_commit",
            "requires_published_H_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "first_directed_dvc_pull",
            "dvc_pull_success_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "failed_closed_namespace_preserved",
            "manifest_written_last": True,
        },
        "H-CERT4": {
            "role": "corrective_credential_fd_and_dvc_site_cache_contract_tests_and_freeze",
            "commit": "h4_cert_commit",
            "direct_parent": "p3_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "credential_path_rebased_to_retained_fd",
                "two_separated_owned_dvc_site_caches_for_all_isolated_dvc_commands",
                "main_dvc_site_cache_metadata_inode_inventory_unchanged",
                "forbid_main_worktree_dvc_status_and_verify_static_git_pointer_boundary",
            ],
        },
        "P-CERT4": {
            "role": "data_only_final_certification_authority_v4",
            "commit": "p4_cert_commit",
            "requires_published_H_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "private_dvc_configuration_after_owned_cache_settings",
            "dvc_pull_success_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "succeeded_exact_namespace_removed",
            "manifest_written_last": True,
        },
        "H-CERT5": {
            "role": "corrective_private_dvc_cache_equivalence_and_capability_contract_tests_and_freeze",
            "commit": "h5_cert_commit",
            "direct_parent": "p4_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "normalize_owned_cache_dir_and_type_before_section_set_equivalence",
                "reject_every_non_operational_private_section_or_setting_drift",
                "withhold_credential_fds_until_first_directed_pull",
                "record_r_cert4_failure_and_forbid_p_cert4_retry",
            ],
        },
        "P-CERT5": {
            "role": "data_only_final_certification_authority_v5",
            "commit": "p5_cert_commit",
            "requires_published_H_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "post_exact_eight_restore_status_boundary",
            "successful_directed_dvc_pulls": 8,
            "restored_checkout_count": 8,
            "directed_dvc_status_checks_confirmed_minimum": 7,
            "directed_dvc_status_checks_confirmed_maximum": 8,
            "exact_directed_dvc_status_count_claimed": False,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "failed_closed_namespace_preserved",
            "manifest_written_last": True,
        },
        "H-CERT6": {
            "role": "corrective_partial_clone_dvc_status_scope_contract_tests_and_freeze",
            "commit": "h6_cert_commit",
            "direct_parent": "p5_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "scope_post_restore_status_to_exact_ordered_eight_pointer_paths",
                "scope_post_verification_status_to_exact_ordered_eight_pointer_paths",
                "forbid_global_dvc_status_in_partial_clone",
                "record_r_cert5_failure_and_forbid_p_cert5_retry",
            ],
        },
        "P-CERT6": {
            "role": "data_only_final_certification_authority_v6",
            "commit": "p6_cert_commit",
            "requires_published_H_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "postgres_start_portable_command_serialization",
            "successful_directed_dvc_pulls": 8,
            "restored_checkout_count": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "docker_container_runs": 0,
            "public_test_runs": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "succeeded_exact_namespace_removed",
            "manifest_written_last": True,
        },
        "H-CERT7": {
            "role": "corrective_postgres_portable_path_serialization_contract_tests_and_freeze",
            "commit": "h7_cert_commit",
            "direct_parent": "p6_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "redact_four_postgres_container_internal_paths_in_portable_command",
                "preserve_real_postgres_execution_command",
                "reject_every_absolute_path_in_serialized_command_evidence",
                "record_r_cert6_failure_and_forbid_p_cert6_retry",
            ],
        },
        "P-CERT7": {
            "role": "data_only_final_certification_authority_v7",
            "commit": "p7_cert_commit",
            "requires_published_H_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "sandbox_projection",
            "failure_kind": "forbidden_path_kind_mismatch",
            "successful_directed_dvc_pulls": 8,
            "restored_checkout_count": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "postgresql_fixture_starts": 1,
            "docker_container_runs": 1,
            "public_test_runs": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "failed_closed_namespace_preserved_then_archived",
            "manifest_written_last": True,
        },
        "R-CERT7": {
            "role": "superseded_failed_final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT7": True,
            "failure_stage": "sandbox_projection",
            "failure_kind": "forbidden_path_kind_mismatch",
            "output_count": 0,
            "manifest_written_last": False,
        },
        "H-CERT8": {
            "role": "corrective_sandbox_projection_and_postgres_cleanup_contract_tests_and_freeze",
            "commit": "h8_cert_commit",
            "direct_parent": "p7_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "require_four_forbidden_prefixes_absent_before_sandbox_projection",
                "require_outcome_log_regular_then_empty_file_mask",
                "graceful_postgres_stop_and_exact_residual_inode_cleanup",
                "forbid_arbitrary_residual_adoption_and_unsafe_internal_diagnostics",
                "record_r_cert7_failure_and_forbid_p_cert7_retry",
            ],
        },
        "P-CERT8": {
            "role": "data_only_final_certification_authority_v8",
            "commit": "p8_cert_commit",
            "requires_published_H_CERT8": True,
            "supersedes_P_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "public_tests",
            "failure_kind": "required_mountpoints_absent_under_read_only_clone",
            "successful_directed_dvc_pulls": 8,
            "restored_checkout_count": 8,
            "directed_dvc_unit_status_checks": 8,
            "post_restore_exact_eight_status_checks": 1,
            "post_verification_exact_eight_status_checks": 0,
            "global_dvc_status_commands": 0,
            "postgresql_fixture_starts": 1,
            "docker_container_runs": 1,
            "bubblewrap_process_runs": 1,
            "python_process_starts": 0,
            "pytest_process_starts": 0,
            "public_test_runs": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "failed_closed_namespace_preserved_then_archived",
            "manifest_written_last": True,
        },
        "R-CERT8": {
            "role": "superseded_failed_final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT8": True,
            "failure_stage": "public_tests",
            "failure_kind": "required_mountpoints_absent_under_read_only_clone",
            "output_count": 0,
            "manifest_written_last": False,
        },
        "H-CERT9": {
            "role": "corrective_sandbox_mountpoints_smoke_and_cleanup_diagnostics_contract_tests_and_freeze",
            "commit": "h9_cert_commit",
            "direct_parent": "p8_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "prepare_exact_empty_clone_mountpoints_before_private_dvc_configuration",
                "run_exact_bwrap_touch_smoke_after_restore_freeze_before_postgres",
                "allowlist_path_free_cleanup_reason_codes",
                "record_r_cert8_failure_and_forbid_p_cert8_retry",
            ],
        },
        "P-CERT9": {
            "role": "data_only_final_certification_authority_v9",
            "commit": "p9_cert_commit",
            "requires_published_H_CERT9": True,
            "supersedes_P_CERT8": True,
            "supersedes_P_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "public_tests",
            "failure_kind": "registered_suite_failures_errors_and_state_skips",
            "public_tests_total": 944,
            "public_tests_passed": 857,
            "public_tests_failed": 65,
            "public_tests_errors": 1,
            "public_tests_skipped": 21,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "failed_closed_namespace_preserved",
            "manifest_written_last": True,
        },
        "R-CERT9": {
            "role": "superseded_failed_final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT9": True,
            "failure_stage": "public_tests",
            "failure_kind": "registered_suite_failures_errors_and_state_skips",
            "output_count": 0,
            "manifest_written_last": False,
        },
        "H-CERT10": {
            "role": "corrective_public_suite_boundary_skip_ledger_and_postgres_destroy_poll_contract_tests_and_freeze",
            "commit": "h10_cert_commit",
            "direct_parent": "p9_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "replace_public_python_audit_hook_with_bubblewrap_hard_boundary",
                "preserve_openapi_and_e2e_python_audit_hooks",
                "seal_exact_42_honest_sandbox_or_state_skip_ledger",
                "bound_postgres_destroy_poll_and_require_double_absence",
                "record_r_cert9_failure_and_forbid_p_cert9_retry",
            ],
        },
        "P-CERT10": {
            "role": "data_only_final_certification_authority_v10",
            "commit": "p10_cert_commit",
            "requires_published_H_CERT10": True,
            "supersedes_P_CERT9": True,
            "supersedes_P_CERT8": True,
            "supersedes_P_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "public_tests",
            "failure_kind": "sealed_suite_collection_count_and_digest_drift",
            "sealed_collected_test_count": 944,
            "observed_collected_test_count": 946,
            "observed_nodeids_sha256": (
                "644bc8548b730c98a62773dcc01622a6d5322ffabbcc31aa0e63b12275df9295"
            ),
            "unexpected_node_count": 2,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "succeeded_exact_namespace_removed",
            "manifest_written_last": True,
        },
        "R-CERT10": {
            "role": "superseded_failed_final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT10": True,
            "failure_stage": "public_tests",
            "failure_kind": "sealed_suite_collection_count_and_digest_drift",
            "output_count": 0,
            "manifest_written_last": False,
        },
        "H-CERT11": {
            "role": "corrective_public_suite_lock_reconciliation_contract_tests_and_freeze",
            "commit": "h11_cert_commit",
            "direct_parent": "p10_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "restore_exact_944_node_suite_lock",
                "retain_h10_policy_checks_without_new_nodeids",
                "record_r_cert10_failure_and_forbid_p_cert10_retry",
            ],
        },
        "P-CERT11": {
            "role": "data_only_final_certification_authority_v11",
            "commit": "p11_cert_commit",
            "requires_published_H_CERT11": True,
            "supersedes_P_CERT10": True,
            "supersedes_P_CERT9": True,
            "supersedes_P_CERT8": True,
            "supersedes_P_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "public_tests",
            "failure_kind": "naive_database_url_rsplit_misparsed_unix_socket_query",
            "public_tests_collected": 944,
            "public_test_totals_preserved": False,
            "final_junit_preserved": False,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "succeeded_exact_namespace_removed",
            "manifest_written_last": True,
        },
        "R-CERT11": {
            "role": "superseded_failed_final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT11": True,
            "failure_stage": "public_tests",
            "failure_kind": "naive_database_url_rsplit_misparsed_unix_socket_query",
            "output_count": 0,
            "manifest_written_last": False,
        },
        "H-CERT12": {
            "role": "corrective_query_free_postgres_test_dsn_contract_tests_and_freeze",
            "commit": "h12_cert_commit",
            "direct_parent": "p11_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "replace_query_bearing_test_database_url_with_query_free_dsn",
                "route_unix_socket_exclusively_through_pg_host_environment",
                "seal_redacted_postgres_connection_semantics",
                "record_r_cert11_failure_and_forbid_p_cert11_retry",
            ],
        },
        "P-CERT12": {
            "role": "data_only_final_certification_authority_v12",
            "commit": "p12_cert_commit",
            "requires_published_H_CERT12": True,
            "supersedes_P_CERT11": True,
            "supersedes_P_CERT10": True,
            "supersedes_P_CERT9": True,
            "supersedes_P_CERT8": True,
            "supersedes_P_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "postgres_startup_socket_inventory",
            "failure_kind": "socket_inventory_not_exact_two",
            "readiness_success_observed": True,
            "observed_socket_inventory_serialized": False,
            "public_test_runs": 0,
            "openapi_generations": 0,
            "synthetic_e2e_runs": 0,
            "static_command_runs": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
            "cleanup_status": "succeeded_exact_namespace_removed",
            "manifest_written_last": True,
        },
        "R-CERT12": {
            "role": "superseded_failed_final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT12": True,
            "failure_stage": "postgres_startup_socket_inventory",
            "failure_kind": "socket_inventory_not_exact_two",
            "output_count": 0,
            "manifest_written_last": False,
        },
        "H-CERT13": {
            "role": "invalidated_unpublished_postgres_startup_stability_candidate",
            "direct_parent": "p12_cert_commit",
            "certification_execution_authorized": False,
            "commit_published": False,
            "failure_stage": "main_worktree_dvc_command_boundary",
            "failure_kind": "manual_main_dvc_status_violated_absolute_boundary",
            "retry_authorized": False,
            "corrections": [
                "require_postgres_pid1_before_and_after_readiness",
                "use_explicit_socket_readiness_and_revalidate_exact_same_claims",
                "retry_only_empty_or_expected_subset_inventories_within_bound",
                "fail_closed_on_unexpected_name_type_link_or_replacement",
                "forbid_post_stop_recapture_or_arbitrary_residual_adoption",
                "record_r_cert12_failure_and_forbid_p_cert12_retry",
            ],
        },
        "P-CERT13": {
            "role": "not_generated_due_to_invalidated_unpublished_h_cert13",
            "requires_published_H_CERT13": True,
            "authority_file_count": 0,
            "commit_published": False,
            "certification_execution_authorized": False,
            "manifest_written_last": False,
        },
        "R-CERT13": {
            "role": "not_executed_due_to_absent_p_cert13",
            "requires_published_P_CERT13": True,
            "execution_runs": 0,
            "output_count": 0,
            "manifest_written_last": False,
        },
        "H-CERT14": {
            "role": "corrective_absolute_main_dvc_boundary_postgres_stability_contract_tests_and_freeze",
            "commit": "h14_cert_commit",
            "direct_parent": "p12_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "preserve_postgres_pid1_readiness_and_socket_stability_hardening",
                "record_unpublished_h_cert13_candidate_invalidation",
                "restore_absolute_main_worktree_dvc_command_boundary",
                "reject_temporary_precommit_reports_as_authority",
                "forbid_h_cert13_retry_or_p_cert13_r_cert13_generation",
            ],
        },
        "P-CERT14": {
            "role": "superseded_preflight_blocked_final_certification_authority_v14",
            "commit": "p14_cert_commit",
            "requires_published_H_CERT14": True,
            "supersedes_unpublished_H_CERT13_candidate": True,
            "supersedes_P_CERT12": True,
            "supersedes_P_CERT11": True,
            "supersedes_P_CERT10": True,
            "supersedes_P_CERT9": True,
            "supersedes_P_CERT8": True,
            "supersedes_P_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "effective_authority_alias_projection_preflight",
            "failure_kind": "projected_effective_authority_omitted_h13_p13_aliases",
            "r_cert_execution_runs": 0,
            "retry_authorized": False,
            "manifest_written_last": True,
        },
        "R-CERT14": {
            "role": "superseded_preflight_failed_final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT14": True,
            "failure_stage": "effective_authority_alias_projection_preflight",
            "failure_kind": "projected_effective_authority_omitted_h13_p13_aliases",
            "execution_runs": 0,
            "output_count": 0,
            "retry_authorized": False,
            "manifest_written_last": False,
        },
        "H-CERT15": {
            "role": "corrective_effective_authority_projection_contract_tests_and_freeze",
            "commit": "h15_cert_commit",
            "direct_parent": "p14_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "preserve_present_null_h13_p13_aliases_in_builder_projection",
                "make_effective_authority_projection_revalidation_idempotent",
                "cover_strict_loader_to_check_only_composition",
                "record_r_cert14_preflight_failure_without_execution",
                "forbid_p_cert14_r_cert14_retry",
            ],
        },
        "P-CERT15": {
            "role": "superseded_failed_final_certification_authority_v15",
            "commit": "p15_cert_commit",
            "requires_published_H_CERT15": True,
            "supersedes_P_CERT14": True,
            "supersedes_unpublished_H_CERT13_candidate": True,
            "supersedes_P_CERT12": True,
            "supersedes_P_CERT11": True,
            "supersedes_P_CERT10": True,
            "supersedes_P_CERT9": True,
            "supersedes_P_CERT8": True,
            "supersedes_P_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "public_tests",
            "failure_kind": "public_test_failure_identity_not_persisted",
            "r_cert_execution_runs": 1,
            "retry_authorized": False,
            "manifest_written_last": True,
        },
        "R-CERT15": {
            "role": "superseded_failed_final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT15": True,
            "failure_stage": "public_tests",
            "failure_kind": "public_test_failure_identity_not_persisted",
            "execution_runs": 1,
            "output_count": 0,
            "retry_authorized": False,
            "manifest_written_last": False,
        },
        "H-CERT16": {
            "role": "corrective_safe_public_test_junit_failure_diagnostics_contract_tests_and_freeze",
            "commit": "h16_cert_commit",
            "direct_parent": "p15_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "record_consumed_r_cert15_failure_without_inventing_cause_nodeids_or_totals",
                "read_failed_public_test_junit_through_bounded_fd_safe_revalidated_path",
                "seal_only_totals_failure_error_nodeids_and_digests",
                "reject_hostile_oversized_duplicate_unknown_or_outside_suite_junit",
                "propagate_safe_junit_identity_through_composite_cleanup_errors",
                "forbid_p_cert15_r_cert15_retry",
            ],
        },
        "P-CERT16": {
            "role": "superseded_failed_final_certification_authority_v16",
            "commit": "p16_cert_commit",
            "requires_published_H_CERT16": True,
            "supersedes_P_CERT15": True,
            "supersedes_P_CERT14": True,
            "supersedes_unpublished_H_CERT13_candidate": True,
            "supersedes_P_CERT12": True,
            "supersedes_P_CERT11": True,
            "supersedes_P_CERT10": True,
            "supersedes_P_CERT9": True,
            "supersedes_P_CERT8": True,
            "supersedes_P_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "public_tests",
            "failure_kind": "strict_junit_diagnostic_rejected",
            "failure_identity_status": "failure_identity_unavailable",
            "failure_identity_unavailable_reason": "junit_malformed_or_hostile",
            "r_cert_execution_runs": 1,
            "retry_authorized": False,
            "manifest_written_last": True,
        },
        "R-CERT16": {
            "role": "superseded_failed_final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT16": True,
            "failure_stage": "public_tests",
            "failure_kind": "strict_junit_diagnostic_rejected",
            "failure_identity_status": "failure_identity_unavailable",
            "failure_identity_unavailable_reason": "junit_malformed_or_hostile",
            "execution_runs": 1,
            "output_count": 0,
            "retry_authorized": False,
            "manifest_written_last": False,
        },
        "H-CERT17": {
            "role": "corrective_pytest_skip_precedence_and_junit_teardown_accounting_contract_tests_and_freeze",
            "commit": "h17_cert_commit",
            "direct_parent": "p16_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "record_consumed_r_cert16_safe_unavailable_junit_diagnostic_without_inventing_cause_nodeids_or_totals",
                "prepend_exact_skipif_true_marker_with_sealed_reason",
                "neutralize_preexisting_skipif_precedence_for_exact_skip_ledger",
                "classify_structurally_valid_unsealed_skip_reason_as_junit_sealed_suite_drift",
                "admit_pytest_declared_tests_teardown_error_counter_only_within_logical_identity_count_plus_error_identity_count",
                "keep_failures_errors_and_skipped_counters_exact",
                "forbid_p_cert16_r_cert16_retry",
            ],
        },
        "P-CERT17": {
            "role": "superseded_failed_final_certification_authority_v17",
            "commit": "p17_cert_commit",
            "requires_published_H_CERT17": True,
            "supersedes_P_CERT16": True,
            "supersedes_P_CERT15": True,
            "supersedes_P_CERT14": True,
            "supersedes_unpublished_H_CERT13_candidate": True,
            "supersedes_P_CERT12": True,
            "supersedes_P_CERT11": True,
            "supersedes_P_CERT10": True,
            "supersedes_P_CERT9": True,
            "supersedes_P_CERT8": True,
            "supersedes_P_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized": False,
            "failure_stage": "public_tests",
            "failure_kind": "retained_sandbox_python_alias_rejected",
            "failure_identity_status": "failure_identity_available",
            "public_tests_total": 944,
            "public_tests_passed": 895,
            "public_tests_failed": 7,
            "public_tests_errors": 0,
            "public_tests_skipped": 42,
            "r_cert_execution_runs": 1,
            "retry_authorized": False,
            "manifest_written_last": True,
        },
        "R-CERT17": {
            "role": "superseded_failed_final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT17": True,
            "failure_stage": "public_tests",
            "failure_kind": "retained_sandbox_python_alias_rejected",
            "failure_identity_status": "failure_identity_available",
            "execution_runs": 1,
            "output_count": 0,
            "retry_authorized": False,
            "manifest_written_last": False,
        },
        "H-CERT18": {
            "role": "corrective_retained_python_and_poetry_sandbox_alias_identity_contract_tests_and_freeze",
            "direct_parent": "p17_cert_commit",
            "certification_execution_authorized": False,
            "corrections": [
                "record_consumed_r_cert17_safe_failure_identity_and_forbid_retry",
                "accept_only_exact_cert_python_alias_in_sealed_public_suite",
                "bind_cert_python_to_proc_self_exe_and_injected_usr_target_full_identity",
                "retain_normal_usr_python_origin_policy",
                "resolve_cert_poetry_only_under_same_proven_sandbox_python_context",
                "reject_arbitrary_similar_or_mutable_runtime_aliases",
            ],
        },
        "P-CERT18": {
            "role": "data_only_final_certification_authority_v18",
            "requires_published_H_CERT18": True,
            "supersedes_P_CERT17": True,
            "supersedes_P_CERT16": True,
            "supersedes_P_CERT15": True,
            "supersedes_P_CERT14": True,
            "supersedes_unpublished_H_CERT13_candidate": True,
            "supersedes_P_CERT12": True,
            "supersedes_P_CERT11": True,
            "supersedes_P_CERT10": True,
            "supersedes_P_CERT9": True,
            "supersedes_P_CERT8": True,
            "supersedes_P_CERT7": True,
            "supersedes_P_CERT6": True,
            "supersedes_P_CERT5": True,
            "supersedes_P_CERT4": True,
            "supersedes_P_CERT3": True,
            "supersedes_P_CERT2": True,
            "supersedes_P_CERT1": True,
            "certification_execution_authorized_while_unpublished": False,
            "manifest_written_last": True,
        },
        "R-CERT18": {
            "role": "final_doctoral_software_and_restorability_evidence",
            "requires_published_P_CERT18": True,
            "output_count": 8,
            "manifest_written_last": True,
        },
        "single_parent_commits_required": True,
        "closure_source_commit_must_remain_ancestor": True,
        "aligned_refs_and_live_remote_required": True,
        "clean_worktree_and_index_required_at_each_gate": True,
        "main_worktree_dvc_status_executed": False,
        "main_worktree_dvc_static_boundary_verified": True,
        "main_worktree_dvc_state_source": "git_and_versioned_dvc_pointers",
        "git_commit_push_and_tag_are_manual_user_actions": True,
    }


def _expected_dvc_controls() -> Mapping[str, Any]:
    return {
        "mode": "remote_pull_in_isolated_clone_with_initially_empty_cache",
        "pointer_count": 8,
        "pull_command_template": list(DVC_PULL_COMMAND_TEMPLATE),
        "one_pointer_per_command": True,
        "tracked_config_contains_remote": False,
        "ignored_local_remote_configuration_required": True,
        "ignored_local_remote_configuration_serialized": False,
        "credential_path_values_serialized": False,
        "owned_site_cache_count": 2,
        "owned_site_cache_roles": list(OWNED_SITE_CACHE_ROLES),
        "owned_site_cache_filesystem_mode": OWNED_SITE_CACHE_FILESYSTEM_MODE,
        "owned_site_caches_separated": True,
        "owned_site_cache_paths_serialized": False,
        "version_seal_before_private_config_or_pull": True,
        "single_dvc_runtime_retained_through_final_status_and_version_probe": True,
        "dvc_runtime_cross_call_identity_revalidated": True,
        "operational_cache_fields_normalized_before_section_set_equivalence": True,
        "only_owned_cache_dir_and_type_may_differ": True,
        "credential_fds_passed_to_dvc_config_commands": False,
        "first_credential_fd_subprocess_exposure": "first_directed_dvc_pull",
        "post_restore_status_pointer_paths": [
            item.path for item in DVC_POINTERS
        ],
        "post_verification_status_pointer_paths": [
            item.path for item in DVC_POINTERS
        ],
        "partial_clone_global_status_authorized": False,
        "used_by_all_isolated_dvc_commands": True,
        "copied_core_site_cache_dir_used": False,
        "main_dvc_site_cache_metadata_inode_inventory_unchanged": True,
        "main_dvc_command_run": False,
        "main_worktree_dvc_status_executed": False,
        "main_worktree_dvc_static_boundary_verified": True,
        "main_worktree_dvc_state_source": "git_and_versioned_dvc_pointers",
        "real_dvc_execution_scope": "isolated_r_cert_clone_only",
        "cache_initially_empty": True,
        "main_worktree_written": False,
        "dvc_add_authorized": False,
        "dvc_push_authorized": False,
        "parquet_open_or_decode_authorized": False,
    }


def _expected_isolation() -> Mapping[str, Any]:
    return {
        "clone_source": "live_origin_main",
        "clone_must_be_exact_p_cert": True,
        "clone_must_be_initially_clean": True,
        "clone_and_cache_under_owned_temporary_root": True,
        "source_worktree_read_only_during_verification": True,
        "host_virtualenv_read_only": True,
        "expected_runtime_versions": dict(EXPECTED_RUNTIME_VERSIONS),
        "network_policy": {
            "git_live_remote_ref_validation": "allowed",
            "git_clone_from_origin": "allowed",
            "eight_directed_dvc_pulls": "allowed",
            "loopback_postgresql": "allowed",
            "scientific_or_general_network": "forbidden",
        },
        "forbidden_read_prefixes": list(FORBIDDEN_READ_PREFIXES),
        "forbidden_read_paths": list(FORBIDDEN_READ_PATHS),
        "forbidden_read_prefix_dispositions": dict(
            FORBIDDEN_READ_PREFIX_DISPOSITIONS
        ),
        "forbidden_read_path_dispositions": dict(
            FORBIDDEN_READ_PATH_DISPOSITIONS
        ),
        "restored_parquet_payloads_are_transport_evidence_only": True,
        "absolute_paths_serialized": False,
        "remote_urls_serialized": False,
        "credentials_serialized": False,
        "database_urls_serialized": False,
        "orchestrator_git_commit_push_tag_authorized": False,
        "fixture_git_commits_only_in_owned_tmp_repositories": True,
        "rerun_e0_u_or_e1_e10_authorized": False,
        "refit_rescore_recalibrate_authorized": False,
        "concurrency_lock": "flock_retained_git_directory",
        "legacy_guard_path_must_be_absent": GUARD_PATH.as_posix(),
        "external_namespace_mutation_is_stop_condition": True,
        "noncooperating_same_uid_namespace_mutation": "out_of_scope",
        "identity_revalidated_before_and_after_name_cleanup": True,
        "conditional_unlink_by_inode_claimed": False,
        "no_clobber": True,
        "cleanup_before_precommit": True,
        "post_clone_directory_nlink_delta": 1,
        "post_clone_nlink_delta_stage": "after_git_clone",
        "clone_registered_after_exact_transition_check_before_subsequent_validation": True,
        "early_cleanup_inventory_claim_required": True,
        "primary_error_preserved_when_safe_cleanup_passes": True,
        "superseded_p1_retry_authorized": False,
        "failed_dvc_partial_tree_not_adopted_for_cleanup": True,
        "nonexact_cleanup_preserves_namespace": True,
        "composite_error_identifies_sanitized_active_error_and_cleanup_failure": True,
        "superseded_p2_retry_authorized": False,
        "credential_path_rebased_to_retained_fd": True,
        "credential_target_regular_single_link": True,
        "credential_target_group_or_other_writable": False,
        "private_dvc_effective_configuration_equivalent_except_owned_cache": True,
        "owned_site_cache_count": 2,
        "owned_site_cache_roles": list(OWNED_SITE_CACHE_ROLES),
        "owned_site_cache_filesystem_mode": OWNED_SITE_CACHE_FILESYSTEM_MODE,
        "owned_site_caches_separated": True,
        "owned_site_cache_paths_serialized": False,
        "version_seal_before_private_config_or_pull": True,
        "single_dvc_runtime_retained_through_final_status_and_version_probe": True,
        "dvc_runtime_cross_call_identity_revalidated": True,
        "operational_cache_fields_normalized_before_section_set_equivalence": True,
        "only_owned_cache_dir_and_type_may_differ": True,
        "credential_fds_passed_to_dvc_config_commands": False,
        "first_credential_fd_subprocess_exposure": "first_directed_dvc_pull",
        "used_by_all_isolated_dvc_commands": True,
        "copied_core_site_cache_dir_used": False,
        "main_dvc_site_cache_metadata_inode_inventory_unchanged": True,
        "main_dvc_command_run": False,
        "main_worktree_dvc_status_executed": False,
        "main_worktree_dvc_static_boundary_verified": True,
        "main_worktree_dvc_state_source": "git_and_versioned_dvc_pointers",
        "real_dvc_execution_scope": "isolated_r_cert_clone_only",
        "superseded_p3_retry_authorized": False,
        "superseded_p4_retry_authorized": False,
        "superseded_p5_retry_authorized": False,
        "superseded_p6_retry_authorized": False,
        "superseded_p7_retry_authorized": False,
        "superseded_p8_retry_authorized": False,
        "superseded_p9_retry_authorized": False,
        "superseded_p10_retry_authorized": False,
        "superseded_p11_retry_authorized": False,
        "superseded_p12_retry_authorized": False,
        "superseded_p14_retry_authorized": False,
        "superseded_p15_retry_authorized": False,
        "superseded_p16_retry_authorized": False,
        "superseded_p17_retry_authorized": False,
        "postgres_portable_path_policy": expected_postgres_portable_path_policy(),
        "postgres_connection_policy": expected_postgres_connection_policy(),
        "postgres_startup_stability_policy": (
            expected_postgres_startup_stability_policy()
        ),
        "postgres_cleanup_policy": expected_postgres_cleanup_policy(),
        "sandbox_mountpoint_policy": expected_sandbox_mountpoint_policy(),
        "sandbox_smoke_policy": expected_sandbox_smoke_policy(),
        "cleanup_diagnostic_policy": expected_cleanup_diagnostic_policy(),
        "public_tests_junit_diagnostic_policy": (
            expected_public_tests_junit_diagnostic_policy()
        ),
        "postgres_destroy_poll_policy": expected_postgres_destroy_poll_policy(),
        "test_access_guard_policy": expected_test_access_guard_policy(),
        "post_restore_status_pointer_paths": [
            item.path for item in DVC_POINTERS
        ],
        "post_verification_status_pointer_paths": [
            item.path for item in DVC_POINTERS
        ],
        "partial_clone_global_status_authorized": False,
    }


def _expected_outputs() -> Mapping[str, Any]:
    return {
        "root": CERTIFICATION_ROOT.as_posix(),
        "output_count": len(OUTPUT_PATHS),
        "manifest_written_last": True,
        "ordered_paths": list(OUTPUT_PATHS),
        "final_manifest_status": "completed",
        "final_report_claim_boundary": (
            "software_restorability_and_reproducibility_not_scientific_efficacy"
        ),
    }


def validate_contract_payload(
    payload: Any,
    *,
    path: Path = DEFAULT_CONTRACT_PATH,
    root: Path = PROJECT_ROOT,
    verify_inputs: bool = True,
    allow_pending_suite: bool = False,
) -> FinalCertificationContract:
    """Validate an already-decoded contract and return its typed projection."""

    mapping = _require_mapping(payload, context="final-certification contract")
    _require_exact_keys(
        mapping,
        {
            "contract_version",
            "authorities",
            "topology",
            "publication_scopes",
            "anchor_inputs",
            "dvc_restoration",
            "test_certification",
            "openapi_certification",
            "isolation",
            "failure_diagnostics",
            "outputs",
            "stop_rules",
        },
        context="final-certification contract",
    )
    if mapping["contract_version"] != CONTRACT_VERSION:
        raise _error("Final-certification contract version drifted")

    authorities = _require_mapping(mapping["authorities"], context="authorities")
    expected_authorities = {
        "closure_source_commit": CLOSURE_SOURCE_COMMIT,
        "r_syn_commit": R_SYN_COMMIT,
        "editorial_commit": EDITORIAL_COMMIT,
        "h1_cert_commit": H1_CERT_COMMIT,
        "p1_cert_commit": P1_CERT_COMMIT,
        "h2_cert_commit": H2_CERT_COMMIT,
        "p2_cert_commit": P2_CERT_COMMIT,
        "h3_cert_commit": H3_CERT_COMMIT,
        "p3_cert_commit": P3_CERT_COMMIT,
        "h4_cert_commit": H4_CERT_COMMIT,
        "p4_cert_commit": P4_CERT_COMMIT,
        "h5_cert_commit": H5_CERT_COMMIT,
        "p5_cert_commit": P5_CERT_COMMIT,
        "h6_cert_commit": H6_CERT_COMMIT,
        "p6_cert_commit": P6_CERT_COMMIT,
        "h7_cert_commit": H7_CERT_COMMIT,
        "p7_cert_commit": P7_CERT_COMMIT,
        "h8_cert_commit": H8_CERT_COMMIT,
        "p8_cert_commit": P8_CERT_COMMIT,
        "h9_cert_commit": H9_CERT_COMMIT,
        "p9_cert_commit": P9_CERT_COMMIT,
        "h10_cert_commit": H10_CERT_COMMIT,
        "p10_cert_commit": P10_CERT_COMMIT,
        "h11_cert_commit": H11_CERT_COMMIT,
        "p11_cert_commit": P11_CERT_COMMIT,
        "h12_cert_commit": H12_CERT_COMMIT,
        "p12_cert_commit": P12_CERT_COMMIT,
        "h14_cert_commit": H14_CERT_COMMIT,
        "p14_cert_commit": P14_CERT_COMMIT,
        "h15_cert_commit": H15_CERT_COMMIT,
        "p15_cert_commit": P15_CERT_COMMIT,
        "h16_cert_commit": H16_CERT_COMMIT,
        "p16_cert_commit": P16_CERT_COMMIT,
        "h17_cert_commit": H17_CERT_COMMIT,
        "p17_cert_commit": P17_CERT_COMMIT,
        "final_tag": FINAL_TAG,
        "certification_target": "published_P_CERT_v18_commit",
        "r_cert_executable_tree_must_equal_p_cert": True,
    }
    if dict(authorities) != expected_authorities:
        raise _error("Final-certification authority identities drifted")
    if not all(
        COMMIT_RE.fullmatch(str(authorities[key]))
        for key in (
            "closure_source_commit",
            "r_syn_commit",
            "editorial_commit",
            "h1_cert_commit",
            "p1_cert_commit",
            "h2_cert_commit",
            "p2_cert_commit",
            "h3_cert_commit",
            "p3_cert_commit",
            "h4_cert_commit",
            "p4_cert_commit",
            "h5_cert_commit",
            "p5_cert_commit",
            "h6_cert_commit",
            "p6_cert_commit",
            "h7_cert_commit",
            "p7_cert_commit",
            "h8_cert_commit",
            "p8_cert_commit",
            "h9_cert_commit",
            "p9_cert_commit",
            "h10_cert_commit",
            "p10_cert_commit",
            "h11_cert_commit",
            "p11_cert_commit",
            "h12_cert_commit",
            "p12_cert_commit",
            "h14_cert_commit",
            "p14_cert_commit",
            "h15_cert_commit",
            "p15_cert_commit",
            "h16_cert_commit",
            "p16_cert_commit",
            "h17_cert_commit",
            "p17_cert_commit",
        )
    ):
        raise _error("Final-certification commit syntax drifted")

    topology = _require_mapping(mapping["topology"], context="topology")
    if dict(topology) != _expected_topology():
        raise _error("Final-certification topology drifted")

    scopes = _require_mapping(
        mapping["publication_scopes"], context="publication_scopes"
    )
    _require_exact_keys(
        scopes,
        {
            "H-CERT1",
            "P-CERT1",
            "H-CERT2",
            "P-CERT2",
            "H-CERT3",
            "P-CERT3",
            "H-CERT4",
            "P-CERT4",
            "H-CERT5",
            "P-CERT5",
            "H-CERT6",
            "P-CERT6",
            "H-CERT7",
            "P-CERT7",
            "R-CERT7",
            "H-CERT8",
            "P-CERT8",
            "R-CERT8",
            "H-CERT9",
            "P-CERT9",
            "R-CERT9",
            "H-CERT10",
            "P-CERT10",
            "R-CERT10",
            "H-CERT11",
            "P-CERT11",
            "R-CERT11",
            "H-CERT12",
            "P-CERT12",
            "R-CERT12",
            "H-CERT13",
            "P-CERT13",
            "R-CERT13",
            "H-CERT14",
            "P-CERT14",
            "R-CERT14",
            "H-CERT15",
            "P-CERT15",
            "R-CERT15",
            "H-CERT16",
            "P-CERT16",
            "R-CERT16",
            "H-CERT17",
            "P-CERT17",
            "R-CERT17",
            "H-CERT18",
            "P-CERT18",
            "R-CERT18",
        },
        context="publication_scopes",
    )
    h1_scope = _parse_scope(
        scopes["H-CERT1"], stage="H-CERT1", expected=H1_SCOPE
    )
    p1_scope = _parse_scope(
        scopes["P-CERT1"], stage="P-CERT1", expected=P1_SCOPE
    )
    h2_scope = _parse_scope(
        scopes["H-CERT2"], stage="H-CERT2", expected=H2_SCOPE
    )
    p2_scope = _parse_scope(
        scopes["P-CERT2"], stage="P-CERT2", expected=P2_SCOPE
    )
    h3_scope = _parse_scope(
        scopes["H-CERT3"], stage="H-CERT3", expected=H3_SCOPE
    )
    p3_scope = _parse_scope(
        scopes["P-CERT3"], stage="P-CERT3", expected=P3_SCOPE
    )
    h4_scope = _parse_scope(
        scopes["H-CERT4"], stage="H-CERT4", expected=H4_SCOPE
    )
    p4_scope = _parse_scope(
        scopes["P-CERT4"], stage="P-CERT4", expected=P4_SCOPE
    )
    h5_scope = _parse_scope(
        scopes["H-CERT5"], stage="H-CERT5", expected=H5_SCOPE
    )
    p5_scope = _parse_scope(
        scopes["P-CERT5"], stage="P-CERT5", expected=P5_SCOPE
    )
    h6_scope = _parse_scope(
        scopes["H-CERT6"], stage="H-CERT6", expected=H6_SCOPE
    )
    p6_scope = _parse_scope(
        scopes["P-CERT6"], stage="P-CERT6", expected=P6_SCOPE
    )
    h7_scope = _parse_scope(
        scopes["H-CERT7"], stage="H-CERT7", expected=H7_SCOPE
    )
    p7_scope = _parse_scope(
        scopes["P-CERT7"], stage="P-CERT7", expected=P7_SCOPE
    )
    _parse_scope(scopes["R-CERT7"], stage="R-CERT7", expected=R_SCOPE)
    h8_scope = _parse_scope(scopes["H-CERT8"], stage="H-CERT8", expected=H8_SCOPE)
    p8_scope = _parse_scope(scopes["P-CERT8"], stage="P-CERT8", expected=P8_SCOPE)
    _parse_scope(scopes["R-CERT8"], stage="R-CERT8", expected=R_SCOPE)
    h9_scope = _parse_scope(scopes["H-CERT9"], stage="H-CERT9", expected=H9_SCOPE)
    p9_scope = _parse_scope(scopes["P-CERT9"], stage="P-CERT9", expected=P9_SCOPE)
    _parse_scope(scopes["R-CERT9"], stage="R-CERT9", expected=R_SCOPE)
    h10_scope = _parse_scope(
        scopes["H-CERT10"], stage="H-CERT10", expected=H10_SCOPE
    )
    p10_scope = _parse_scope(
        scopes["P-CERT10"], stage="P-CERT10", expected=P10_SCOPE
    )
    _parse_scope(scopes["R-CERT10"], stage="R-CERT10", expected=R_SCOPE)
    h11_scope = _parse_scope(
        scopes["H-CERT11"], stage="H-CERT11", expected=H11_SCOPE
    )
    p11_scope = _parse_scope(
        scopes["P-CERT11"], stage="P-CERT11", expected=P11_SCOPE
    )
    _parse_scope(scopes["R-CERT11"], stage="R-CERT11", expected=R_SCOPE)
    h12_scope = _parse_scope(
        scopes["H-CERT12"], stage="H-CERT12", expected=H12_SCOPE
    )
    p12_scope = _parse_scope(
        scopes["P-CERT12"], stage="P-CERT12", expected=P12_SCOPE
    )
    _parse_scope(scopes["R-CERT12"], stage="R-CERT12", expected=R_SCOPE)
    h13_scope = _parse_scope(
        scopes["H-CERT13"], stage="H-CERT13", expected=H13_SCOPE
    )
    p13_scope = _parse_scope(
        scopes["P-CERT13"], stage="P-CERT13", expected=P13_SCOPE
    )
    _parse_scope(scopes["R-CERT13"], stage="R-CERT13", expected=R_SCOPE)
    h14_scope = _parse_scope(
        scopes["H-CERT14"], stage="H-CERT14", expected=H14_SCOPE
    )
    p14_scope = _parse_scope(
        scopes["P-CERT14"], stage="P-CERT14", expected=P14_SCOPE
    )
    _parse_scope(scopes["R-CERT14"], stage="R-CERT14", expected=R_SCOPE)
    h15_scope = _parse_scope(
        scopes["H-CERT15"], stage="H-CERT15", expected=H15_SCOPE
    )
    p15_scope = _parse_scope(
        scopes["P-CERT15"], stage="P-CERT15", expected=P15_SCOPE
    )
    _parse_scope(scopes["R-CERT15"], stage="R-CERT15", expected=R15_SCOPE)
    h16_scope = _parse_scope(
        scopes["H-CERT16"], stage="H-CERT16", expected=H16_SCOPE
    )
    p16_scope = _parse_scope(
        scopes["P-CERT16"], stage="P-CERT16", expected=P16_SCOPE
    )
    _parse_scope(scopes["R-CERT16"], stage="R-CERT16", expected=R16_SCOPE)
    h17_scope = _parse_scope(
        scopes["H-CERT17"], stage="H-CERT17", expected=H17_SCOPE
    )
    p17_scope = _parse_scope(
        scopes["P-CERT17"], stage="P-CERT17", expected=P17_SCOPE
    )
    _parse_scope(scopes["R-CERT17"], stage="R-CERT17", expected=R17_SCOPE)
    h_scope = _parse_scope(scopes["H-CERT18"], stage="H-CERT18", expected=H_SCOPE)
    p_scope = _parse_scope(scopes["P-CERT18"], stage="P-CERT18", expected=P_SCOPE)
    r_scope = _parse_scope(scopes["R-CERT18"], stage="R-CERT18", expected=R_SCOPE)

    anchors = _parse_anchor_inputs(mapping["anchor_inputs"])

    dvc = _require_mapping(mapping["dvc_restoration"], context="dvc_restoration")
    _require_exact_keys(
        dvc,
        {*_expected_dvc_controls(), "pointers"},
        context="dvc_restoration",
    )
    controls = {key: dvc[key] for key in _expected_dvc_controls()}
    if controls != _expected_dvc_controls():
        raise _error("Final-certification DVC restoration controls drifted")
    dvc_pointers = _parse_dvc_specs(dvc["pointers"])
    ordered_pointer_paths = tuple(item.path for item in dvc_pointers)
    if (
        tuple(cast(Sequence[str], dvc["post_restore_status_pointer_paths"]))
        != ordered_pointer_paths
        or tuple(
            cast(Sequence[str], dvc["post_verification_status_pointer_paths"])
        )
        != ordered_pointer_paths
        or dvc["partial_clone_global_status_authorized"] is not False
    ):
        raise _error("Final-certification partial-clone DVC status policy drifted")

    test_suite = _parse_test_suite(
        mapping["test_certification"],
        allow_pending_suite=allow_pending_suite,
    )

    openapi = _require_mapping(
        mapping["openapi_certification"], context="openapi_certification"
    )
    expected_openapi = {
        "version_prefix": "3.",
        "expected_path_count": 69,
        "expected_operation_count": 83,
        "expected_documented_operation_count": 38,
        "operation_ids_unique": True,
        "path_parameters_exact": True,
        "missing_documented_operations": 0,
    }
    if dict(openapi) != expected_openapi:
        raise _error("Final-certification OpenAPI expectations drifted")

    isolation = _require_mapping(mapping["isolation"], context="isolation")
    if dict(isolation) != _expected_isolation():
        raise _error("Final-certification isolation boundary drifted")

    failure_diagnostics = _require_mapping(
        mapping["failure_diagnostics"], context="failure_diagnostics"
    )
    if dict(failure_diagnostics) != dict(FAILURE_DIAGNOSTICS_POLICY):
        raise _error("Final-certification failure diagnostics policy drifted")

    outputs = _require_mapping(mapping["outputs"], context="outputs")
    if dict(outputs) != _expected_outputs():
        raise _error("Final-certification output order or claim boundary drifted")

    stop_rules = _require_string_tuple(mapping["stop_rules"], context="stop_rules")
    if stop_rules != STOP_RULES:
        raise _error("Final-certification STOP rules drifted")

    contract = FinalCertificationContract(
        path=path,
        raw=mapping,
        closure_source_commit=CLOSURE_SOURCE_COMMIT,
        r_syn_commit=R_SYN_COMMIT,
        editorial_commit=EDITORIAL_COMMIT,
        h1_cert_commit=H1_CERT_COMMIT,
        p1_cert_commit=P1_CERT_COMMIT,
        h2_cert_commit=H2_CERT_COMMIT,
        p2_cert_commit=P2_CERT_COMMIT,
        h3_cert_commit=H3_CERT_COMMIT,
        p3_cert_commit=P3_CERT_COMMIT,
        h4_cert_commit=H4_CERT_COMMIT,
        p4_cert_commit=P4_CERT_COMMIT,
        h5_cert_commit=H5_CERT_COMMIT,
        p5_cert_commit=P5_CERT_COMMIT,
        h6_cert_commit=H6_CERT_COMMIT,
        p6_cert_commit=P6_CERT_COMMIT,
        h7_cert_commit=H7_CERT_COMMIT,
        p7_cert_commit=P7_CERT_COMMIT,
        h8_cert_commit=H8_CERT_COMMIT,
        p8_cert_commit=P8_CERT_COMMIT,
        h9_cert_commit=H9_CERT_COMMIT,
        p9_cert_commit=P9_CERT_COMMIT,
        h10_cert_commit=H10_CERT_COMMIT,
        p10_cert_commit=P10_CERT_COMMIT,
        h11_cert_commit=H11_CERT_COMMIT,
        p11_cert_commit=P11_CERT_COMMIT,
        h12_cert_commit=H12_CERT_COMMIT,
        p12_cert_commit=P12_CERT_COMMIT,
        h14_cert_commit=H14_CERT_COMMIT,
        p14_cert_commit=P14_CERT_COMMIT,
        h15_cert_commit=H15_CERT_COMMIT,
        p15_cert_commit=P15_CERT_COMMIT,
        h16_cert_commit=H16_CERT_COMMIT,
        p16_cert_commit=P16_CERT_COMMIT,
        h17_cert_commit=H17_CERT_COMMIT,
        p17_cert_commit=P17_CERT_COMMIT,
        final_tag=FINAL_TAG,
        h1_scope=h1_scope,
        p1_scope=p1_scope,
        h2_scope=h2_scope,
        p2_scope=p2_scope,
        h3_scope=h3_scope,
        p3_scope=p3_scope,
        h4_scope=h4_scope,
        p4_scope=p4_scope,
        h5_scope=h5_scope,
        p5_scope=p5_scope,
        h6_scope=h6_scope,
        p6_scope=p6_scope,
        h7_scope=h7_scope,
        p7_scope=p7_scope,
        h8_scope=h8_scope,
        p8_scope=p8_scope,
        h9_scope=h9_scope,
        p9_scope=p9_scope,
        h10_scope=h10_scope,
        p10_scope=p10_scope,
        h11_scope=h11_scope,
        p11_scope=p11_scope,
        h12_scope=h12_scope,
        p12_scope=p12_scope,
        h13_scope=h13_scope,
        p13_scope=p13_scope,
        h14_scope=h14_scope,
        p14_scope=p14_scope,
        h15_scope=h15_scope,
        p15_scope=p15_scope,
        h16_scope=h16_scope,
        p16_scope=p16_scope,
        h17_scope=h17_scope,
        p17_scope=p17_scope,
        h_scope=h_scope,
        p_scope=p_scope,
        r_scope=r_scope,
        anchor_inputs=anchors,
        dvc_pointers=dvc_pointers,
        dvc_pull_command_template=DVC_PULL_COMMAND_TEMPLATE,
        post_restore_status_pointer_paths=tuple(
            cast(Sequence[str], dvc["post_restore_status_pointer_paths"])
        ),
        post_verification_status_pointer_paths=tuple(
            cast(Sequence[str], dvc["post_verification_status_pointer_paths"])
        ),
        partial_clone_global_status_authorized=cast(
            bool, dvc["partial_clone_global_status_authorized"]
        ),
        postgres_portable_path_policy=dict(POSTGRES_PORTABLE_PATH_POLICY),
        postgres_connection_policy=expected_postgres_connection_policy(),
        postgres_startup_stability_policy=(
            expected_postgres_startup_stability_policy()
        ),
        postgres_cleanup_policy=expected_postgres_cleanup_policy(),
        sandbox_mountpoint_policy=expected_sandbox_mountpoint_policy(),
        sandbox_smoke_policy=expected_sandbox_smoke_policy(),
        cleanup_diagnostic_policy=expected_cleanup_diagnostic_policy(),
        public_tests_junit_diagnostic_policy=(
            expected_public_tests_junit_diagnostic_policy()
        ),
        postgres_destroy_poll_policy=expected_postgres_destroy_poll_policy(),
        test_access_guard_policy=expected_test_access_guard_policy(),
        test_suite=test_suite,
        expected_openapi_path_count=69,
        expected_openapi_operation_count=83,
        expected_documented_operation_count=38,
        forbidden_read_prefixes=FORBIDDEN_READ_PREFIXES,
        forbidden_read_paths=FORBIDDEN_READ_PATHS,
        forbidden_read_prefix_dispositions=dict(
            FORBIDDEN_READ_PREFIX_DISPOSITIONS
        ),
        forbidden_read_path_dispositions=dict(FORBIDDEN_READ_PATH_DISPOSITIONS),
        output_paths=OUTPUT_PATHS,
        expected_runtime_versions=EXPECTED_RUNTIME_VERSIONS,
        concurrency_lock="flock_retained_git_directory",
        legacy_guard_path_must_be_absent=GUARD_PATH.as_posix(),
        external_namespace_mutation_is_stop_condition=True,
        noncooperating_same_uid_namespace_mutation="out_of_scope",
        identity_revalidated_before_and_after_name_cleanup=True,
        conditional_unlink_by_inode_claimed=False,
        no_clobber=True,
        cleanup_before_precommit=True,
        failure_diagnostics=FAILURE_DIAGNOSTICS_POLICY,
        stop_rules=STOP_RULES,
    )
    if verify_inputs:
        collect_anchor_input_records(contract, root=root)
        collect_dvc_pointer_records(contract, root=root)
    return contract


@dataclass(frozen=True)
class _DirectoryBinding:
    parent_fd: int
    name: str
    fd: int
    device: int
    inode: int
    mode: int


@dataclass(frozen=True)
class _AnchoredRegularFile:
    path: Path
    root_parent_fd: int
    directories: tuple[_DirectoryBinding, ...]
    parent_fd: int
    name: str
    fd: int
    metadata: os.stat_result
    context: str


def _file_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_nlink,
        stat.S_IMODE(metadata.st_mode),
    )


def _open_directory_binding(
    parent_fd: int,
    name: str,
    *,
    context: str,
) -> _DirectoryBinding:
    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} directory name is unsafe")
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise _error(f"{context} directory is unavailable: {name}") from exc
    if stat.S_ISLNK(named.st_mode) or not stat.S_ISDIR(named.st_mode):
        raise _error(f"{context} directory is not no-follow: {name}")
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=parent_fd,
    )
    observed = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(observed.st_mode)
        or (observed.st_dev, observed.st_ino) != (named.st_dev, named.st_ino)
    ):
        os.close(descriptor)
        raise _error(f"{context} directory changed while opening: {name}")
    return _DirectoryBinding(
        parent_fd,
        name,
        descriptor,
        observed.st_dev,
        observed.st_ino,
        stat.S_IMODE(observed.st_mode),
    )


def _open_anchored_regular_file(
    root: Path,
    path_text: str,
    *,
    expected_modes: frozenset[int] | None,
    context: str,
) -> _AnchoredRegularFile:
    relative = _safe_relative_path(path_text, context=f"{context} path")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise _error(f"{context} repository root is unavailable") from exc
    if resolved_root == resolved_root.parent:
        raise _error(f"{context} repository root cannot be the filesystem root")
    root_parent_fd = os.open(
        resolved_root.parent,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    directories: list[_DirectoryBinding] = []
    file_fd: int | None = None
    try:
        root_binding = _open_directory_binding(
            root_parent_fd,
            resolved_root.name,
            context=context,
        )
        directories.append(root_binding)
        current_fd = root_binding.fd
        for part in relative.parts[:-1]:
            binding = _open_directory_binding(current_fd, part, context=context)
            directories.append(binding)
            current_fd = binding.fd
        name = relative.parts[-1]
        try:
            named = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
        except OSError as exc:
            raise _error(f"{context} is unavailable: {path_text}") from exc
        mode = stat.S_IMODE(named.st_mode)
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or named.st_nlink != 1
            or (expected_modes is not None and mode not in expected_modes)
        ):
            raise _error(
                f"{context} must be a permitted single-link regular file: "
                f"{path_text}"
            )
        file_fd = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=current_fd,
        )
        opened = os.fstat(file_fd)
        if not stat.S_ISREG(opened.st_mode) or _file_identity(opened) != _file_identity(
            named
        ):
            raise _error(f"{context} changed while opening: {path_text}")
        return _AnchoredRegularFile(
            resolved_root.joinpath(*relative.parts),
            root_parent_fd,
            tuple(directories),
            current_fd,
            name,
            file_fd,
            opened,
            context,
        )
    except BaseException:
        if file_fd is not None:
            os.close(file_fd)
        for binding in reversed(directories):
            os.close(binding.fd)
        os.close(root_parent_fd)
        raise


def _revalidate_anchored_file(anchored: _AnchoredRegularFile) -> os.stat_result:
    for binding in anchored.directories:
        try:
            named = os.stat(
                binding.name,
                dir_fd=binding.parent_fd,
                follow_symlinks=False,
            )
            opened = os.fstat(binding.fd)
        except OSError as exc:
            raise _error(
                f"{anchored.context} ancestor disappeared during validation"
            ) from exc
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISDIR(named.st_mode)
            or not stat.S_ISDIR(opened.st_mode)
            or (named.st_dev, named.st_ino, stat.S_IMODE(named.st_mode))
            != (binding.device, binding.inode, binding.mode)
            or (opened.st_dev, opened.st_ino, stat.S_IMODE(opened.st_mode))
            != (binding.device, binding.inode, binding.mode)
        ):
            raise _error(f"{anchored.context} ancestor binding drifted")
    try:
        named_file = os.stat(
            anchored.name,
            dir_fd=anchored.parent_fd,
            follow_symlinks=False,
        )
        opened_file = os.fstat(anchored.fd)
    except OSError as exc:
        raise _error(f"{anchored.context} name disappeared during validation") from exc
    if (
        stat.S_ISLNK(named_file.st_mode)
        or not stat.S_ISREG(named_file.st_mode)
        or _file_identity(named_file) != _file_identity(opened_file)
        or _file_identity(opened_file) != _file_identity(anchored.metadata)
    ):
        raise _error(f"{anchored.context} name or identity drifted")
    return opened_file


def _close_anchored_file(anchored: _AnchoredRegularFile) -> None:
    os.close(anchored.fd)
    for binding in reversed(anchored.directories):
        os.close(binding.fd)
    os.close(anchored.root_parent_fd)


def _read_stable_file(anchored: _AnchoredRegularFile) -> bytes:
    before = _revalidate_anchored_file(anchored)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(anchored.fd, HASH_CHUNK_SIZE)
        if not chunk:
            break
        chunks.append(chunk)
    after = os.fstat(anchored.fd)
    if _file_identity(after) != _file_identity(before):
        raise _error(f"{anchored.context} changed while reading")
    _revalidate_anchored_file(anchored)
    return b"".join(chunks)


def _read_contract_file(root: Path, path_text: str) -> bytes:
    anchored = _open_anchored_regular_file(
        root,
        path_text,
        expected_modes=frozenset({0o644}),
        context="Final-certification contract",
    )
    try:
        return _read_stable_file(anchored)
    finally:
        _close_anchored_file(anchored)


def load_contract(
    *,
    root: Path = PROJECT_ROOT,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    verify_inputs: bool = True,
    allow_pending_suite: bool = False,
) -> FinalCertificationContract:
    """Load and strictly validate the final Phase 4 certification contract."""

    if contract_path.is_absolute():
        try:
            relative_contract = contract_path.relative_to(root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise _error("Final-certification contract must remain below root") from exc
    else:
        relative_contract = contract_path
    payload = _read_contract_file(root, relative_contract.as_posix())
    try:
        decoded = yaml.safe_load(payload.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise _error("Final-certification contract is not valid UTF-8 YAML") from exc
    return validate_contract_payload(
        decoded,
        path=contract_path,
        root=root,
        verify_inputs=verify_inputs,
        allow_pending_suite=allow_pending_suite,
    )


def parse_dvc_pointer_bytes(
    payload: bytes, pointer_path: str | Path
) -> dict[str, Any]:
    """Parse one exact, single-file MD5 DVC pointer without resolving it."""

    raw_path = Path(pointer_path).as_posix()
    _safe_relative_path(raw_path, context="DVC pointer path")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _error(f"DVC pointer is not UTF-8: {raw_path}") from exc
    match = re.fullmatch(
        r"outs:\n"
        r"- md5: ([0-9a-f]{32})\n"
        r"  size: ([1-9][0-9]*)\n"
        r"  hash: md5\n"
        r"  path: ([A-Za-z0-9_.-]+)\n",
        text,
    )
    if match is None:
        raise _error(f"DVC pointer dialect drifted: {raw_path}")
    md5, size_text, output_name = match.groups()
    expected_name = Path(raw_path).with_suffix("").name
    if output_name != expected_name or not output_name.endswith(".parquet"):
        raise _error(f"DVC pointer output name drifted: {raw_path}")
    output_path = (Path(raw_path).parent / output_name).as_posix()
    return {
        "md5": md5,
        "size": int(size_text),
        "output_name": output_name,
        "output_path": output_path,
    }


def _run_git(root: Path, *args: str, text: bool) -> str | bytes:
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=text,
        env=environment,
    )
    if process.returncode != 0:
        stderr = (
            cast(str, process.stderr).strip()
            if text
            else cast(bytes, process.stderr).decode("utf-8", "replace").strip()
        )
        raise _error(f"git {' '.join(args)} failed: {stderr}")
    return process.stdout


def _git_blob_identity(root: Path, commit: str, path_text: str) -> tuple[str, str]:
    output = cast(
        str, _run_git(root, "ls-tree", commit, "--", path_text, text=True)
    ).strip()
    fields = output.split(None, 3)
    if (
        len(fields) != 4
        or fields[0] != "100644"
        or fields[1] != "blob"
        or not re.fullmatch(r"[0-9a-f]{40,64}", fields[2])
        or fields[3] != path_text
    ):
        raise _error(f"Public anchor is not one exact editorial Git blob: {path_text}")
    return fields[0], fields[2]


def _regular_repo_file(root: Path, path_text: str) -> _AnchoredRegularFile:
    return _open_anchored_regular_file(
        root,
        path_text,
        expected_modes=frozenset({0o644}),
        context="Public anchor",
    )


def _collect_git_bound_file(
    root: Path, *, path_text: str, role: str, commit: str
) -> tuple[dict[str, Any], bytes]:
    anchored = _regular_repo_file(root, path_text)
    try:
        payload = _read_stable_file(anchored)
        git_mode, git_blob_oid = _git_blob_identity(root, commit, path_text)
        git_payload = cast(
            bytes,
            _run_git(
                root,
                "cat-file",
                "blob",
                f"{commit}:{path_text}",
                text=False,
            ),
        )
        _revalidate_anchored_file(anchored)
        if payload != git_payload:
            raise _error(f"Public anchor differs from editorial Git: {path_text}")
        return (
            {
                "path": path_text,
                "role": role,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "git_mode": git_mode,
                "git_blob_oid": git_blob_oid,
                "repository_commit": commit,
            },
            payload,
        )
    finally:
        _close_anchored_file(anchored)


def collect_anchor_input_records(
    contract: FinalCertificationContract, *, root: Path = PROJECT_ROOT
) -> list[dict[str, Any]]:
    """Collect exact editorial-Git identities for the ten public anchors."""

    records = [
        _collect_git_bound_file(
            root,
            path_text=spec.path,
            role=spec.role,
            commit=contract.editorial_commit,
        )[0]
        for spec in contract.anchor_inputs
    ]
    if tuple(record["path"] for record in records) != contract.anchor_input_paths:
        raise _error("Public anchor record order drifted")
    return records


def collect_dvc_pointer_records(
    contract: FinalCertificationContract, *, root: Path = PROJECT_ROOT
) -> list[dict[str, Any]]:
    """Validate the eight Git-bound pointers without opening their payloads."""

    records: list[dict[str, Any]] = []
    for spec in contract.dvc_pointers:
        base, payload = _collect_git_bound_file(
            root,
            path_text=spec.path,
            role=spec.role,
            commit=contract.editorial_commit,
        )
        parsed = parse_dvc_pointer_bytes(payload, spec.path)
        if (
            parsed["md5"] != spec.md5
            or parsed["size"] != spec.size
            or parsed["output_path"] != spec.output_path
        ):
            raise _error(f"DVC pointer declaration drifted: {spec.path}")
        records.append(
            {
                **base,
                "output_path": spec.output_path,
                "payload_md5": spec.md5,
                "payload_bytes": spec.size,
                "parquet_payload_opened": False,
            }
        )
    if tuple(record["path"] for record in records) != contract.dvc_pointer_paths:
        raise _error("DVC pointer record order drifted")
    return records


def main_dvc_static_boundary_record(
    contract: FinalCertificationContract,
    *,
    anchor_records: Sequence[Mapping[str, Any]],
    pointer_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Seal main-worktree DVC state from Git-bound public bytes only."""

    if (
        len(anchor_records) != len(contract.anchor_inputs)
        or not anchor_records
        or anchor_records[0].get("path") != ".dvc/config"
        or anchor_records[0].get("repository_commit") != contract.editorial_commit
        or not isinstance(anchor_records[0].get("git_blob_oid"), str)
    ):
        raise _error("Main DVC static boundary lacks its Git-bound config")
    if (
        len(pointer_records) != len(contract.dvc_pointers)
        or len(pointer_records) != 8
        or tuple(record.get("path") for record in pointer_records)
        != contract.dvc_pointer_paths
        or any(
            record.get("repository_commit") != contract.editorial_commit
            or record.get("parquet_payload_opened") is not False
            for record in pointer_records
        )
    ):
        raise _error("Main DVC static boundary pointer reconstruction drifted")
    return {
        "status_executed": False,
        "state_source": "git_and_versioned_dvc_pointers",
        "static_boundary_verified": True,
        "tracked_config_path": ".dvc/config",
        "tracked_config_git_blob_oid": anchor_records[0]["git_blob_oid"],
        "versioned_pointer_count": 8,
        "versioned_pointer_records_digest": digest_records(pointer_records),
        "real_dvc_execution_scope": "isolated_r_cert_clone_only",
    }


def test_suite_record(contract: FinalCertificationContract) -> dict[str, Any]:
    """Return the exact canonical P-CERT projection of the locked suite."""

    suite = contract.test_suite
    if (
        suite.status != "locked"
        or suite.selector_count is None
        or suite.collected_test_count is None
        or suite.nodeids_sha256 is None
    ):
        raise _error("P-CERT requires a fully locked final-certification suite")
    return {
        "suite_kind": suite.suite_kind,
        "positive_test_paths": list(suite.positive_test_paths),
        "exact_skipped_nodes": list(suite.exact_skipped_nodes),
        "exact_skip_reason": suite.exact_skip_reason,
        "e2e_nodes": list(suite.e2e_nodes),
        "selectors": list(suite.selectors),
        "command_template": list(suite.command_template),
        "static_commands": [list(command) for command in suite.static_commands],
        "suite_lock": {
            "status": suite.status,
            "selector_count": suite.selector_count,
            "collected_test_count": suite.collected_test_count,
            "nodeids_sha256": suite.nodeids_sha256,
            "allowed_skip_count": suite.allowed_skip_count,
        },
    }


def _publication_file_record_and_payload(
    root: Path,
    *,
    commit: str,
    spec: PublicationPathSpec,
) -> tuple[dict[str, Any], bytes]:
    expected_mode = int(spec.git_mode[-3:], 8)
    anchored = _open_anchored_regular_file(
        root,
        spec.path,
        expected_modes=frozenset({expected_mode}),
        context="Published certification component",
    )
    try:
        payload = _read_stable_file(anchored)
        output = cast(
            str, _run_git(root, "ls-tree", commit, "--", spec.path, text=True)
        ).strip()
        fields = output.split(None, 3)
        if (
            len(fields) != 4
            or fields[0] != spec.git_mode
            or fields[1] != "blob"
            or not re.fullmatch(r"[0-9a-f]{40,64}", fields[2])
            or fields[3] != spec.path
        ):
            raise _error(f"H-CERT component Git identity drifted: {spec.path}")
        git_payload = cast(
            bytes, _run_git(root, "cat-file", "blob", fields[2], text=False)
        )
        _revalidate_anchored_file(anchored)
        if payload != git_payload:
            raise _error(
                f"H-CERT component differs from published Git: {spec.path}"
            )
        return (
            {
                "path": spec.path,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "git_mode": spec.git_mode,
                "git_blob_oid": fields[2],
                "filesystem_mode": stat.S_IMODE(anchored.metadata.st_mode),
            },
            payload,
        )
    finally:
        _close_anchored_file(anchored)


def _publication_file_record(
    root: Path,
    *,
    commit: str,
    spec: PublicationPathSpec,
) -> dict[str, Any]:
    return _publication_file_record_and_payload(
        root,
        commit=commit,
        spec=spec,
    )[0]


def _git_publication_file_record_and_payload(
    root: Path,
    *,
    commit: str,
    spec: PublicationPathSpec,
    context: str,
) -> tuple[dict[str, Any], bytes]:
    """Reconstruct a historical component from Git without using live bytes."""

    output = cast(
        str, _run_git(root, "ls-tree", commit, "--", spec.path, text=True)
    ).strip()
    fields = output.split(None, 3)
    if (
        len(fields) != 4
        or fields[0] != spec.git_mode
        or fields[1] != "blob"
        or not re.fullmatch(r"[0-9a-f]{40,64}", fields[2])
        or fields[3] != spec.path
    ):
        raise _error(f"{context} is not one exact Git blob: {spec.path}")
    payload = cast(
        bytes, _run_git(root, "cat-file", "blob", fields[2], text=False)
    )
    if not payload:
        raise _error(f"{context} is empty: {spec.path}")
    return (
        {
            "path": spec.path,
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
            "git_mode": spec.git_mode,
            "git_blob_oid": fields[2],
        },
        payload,
    )


def collect_git_component_records(
    scope: Sequence[PublicationPathSpec],
    *,
    commit: str,
    root: Path = PROJECT_ROOT,
    context: str = "Historical certification component",
) -> list[dict[str, Any]]:
    if COMMIT_RE.fullmatch(commit) is None:
        raise _error(f"{context} commit syntax drifted")
    return [
        _git_publication_file_record_and_payload(
            root, commit=commit, spec=spec, context=context
        )[0]
        for spec in scope
    ]


def collect_h_component_records(
    contract: FinalCertificationContract,
    *,
    h_cert_commit: str,
    root: Path = PROJECT_ROOT,
) -> list[dict[str, Any]]:
    """Reconstruct every H-CERT component from physical and Git identities."""

    if COMMIT_RE.fullmatch(h_cert_commit) is None:
        raise _error("H-CERT commit syntax drifted")
    return [
        _publication_file_record(root, commit=h_cert_commit, spec=spec)
        for spec in contract.h_scope
    ]


def _decode_canonical_public_json(
    root: Path, relative: Path, *, commit: str
) -> tuple[Mapping[str, Any], bytes]:
    spec = PublicationPathSpec(relative.as_posix(), "A", "100644")
    _record, payload = _publication_file_record_and_payload(
        root,
        commit=commit,
        spec=spec,
    )
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _error(f"P-CERT JSON cannot be decoded: {relative}") from exc
    mapping = _require_mapping(decoded, context=relative.as_posix())
    if canonical_json_bytes(mapping) != payload:
        raise _error(f"P-CERT JSON is not canonical: {relative}")
    return mapping, payload


def _commit_parents(root: Path, commit: str) -> tuple[str, ...]:
    fields = cast(
        str, _run_git(root, "rev-list", "--parents", "-n", "1", commit, text=True)
    ).strip().split()
    if not fields or fields[0] != commit:
        raise _error(f"Cannot resolve commit parents: {commit}")
    return tuple(fields[1:])


def _commit_scope(root: Path, commit: str) -> dict[str, str]:
    output = cast(
        str,
        _run_git(
            root,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "--no-renames",
            "-r",
            f"{commit}^",
            commit,
            text=True,
        ),
    )
    result: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"A", "M"} or fields[1] in result:
            raise _error(f"Unsupported publication diff at {commit}")
        result[fields[1]] = fields[0]
    return result


def _one_commit(root: Path, ref: str) -> str:
    value = cast(
        str, _run_git(root, "rev-parse", "--verify", f"{ref}^{{commit}}", text=True)
    ).strip()
    if COMMIT_RE.fullmatch(value) is None:
        raise _error(f"Git ref is not one commit: {ref}")
    return value


def _require_effective_refs(
    root: Path, expected: str, *, verify_remote: bool
) -> dict[str, str]:
    refs = {
        "head": _one_commit(root, "HEAD"),
        "main": _one_commit(root, "main"),
        "origin_main": _one_commit(root, "origin/main"),
        "origin_head": _one_commit(root, "origin/HEAD"),
    }
    if set(refs.values()) != {expected}:
        raise _error("P-CERT local/tracking refs are not aligned")
    if verify_remote:
        output = cast(
            str,
            _run_git(
                root,
                "ls-remote",
                "--exit-code",
                "origin",
                "HEAD",
                "refs/heads/main",
                text=True,
            ),
        )
        remote: dict[str, str] = {}
        for line in output.splitlines():
            fields = line.split("\t")
            if (
                len(fields) != 2
                or COMMIT_RE.fullmatch(fields[0]) is None
                or fields[1] in remote
            ):
                raise _error("P-CERT live remote refs are malformed")
            remote[fields[1]] = fields[0]
        if (
            set(remote) != {"HEAD", "refs/heads/main"}
            or set(remote.values()) != {expected}
        ):
            raise _error("P-CERT live remote HEAD/main are not aligned")
        refs["remote_main"] = expected
    return refs


def _require_clean_git_state(root: Path) -> None:
    output = cast(
        str,
        _run_git(
            root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            text=True,
        ),
    )
    if output:
        raise _error("Effective P-CERT loader requires a clean worktree and index")


def _historical_h1_p1_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct the superseded H1/P1 chain without treating it as effective."""

    if (
        _commit_parents(root, contract.h1_cert_commit)
        != (contract.editorial_commit,)
        or _commit_scope(root, contract.h1_cert_commit) != expected_h1_scope()
        or _commit_parents(root, contract.p1_cert_commit)
        != (contract.h1_cert_commit,)
        or _commit_scope(root, contract.p1_cert_commit) != expected_p1_scope()
        or _commit_parents(root, contract.editorial_commit)
        != (contract.r_syn_commit,)
    ):
        raise _error("Historical H1/P1/editorial topology or scope drifted")
    h1_records = collect_git_component_records(
        contract.h1_scope,
        commit=contract.h1_cert_commit,
        root=root,
        context="Historical H-CERT1 component",
    )
    physical_p1_payloads = [
        _publication_file_record_and_payload(
            root,
            commit=contract.p1_cert_commit,
            spec=spec,
        )[1]
        for spec in contract.p1_scope
    ]
    authority, authority_bytes = _decode_canonical_public_json(
        root, H1_AUTHORITY_PATH, commit=contract.p1_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H1_AUTHORITY_MANIFEST_PATH, commit=contract.p1_cert_commit
    )
    if physical_p1_payloads != [authority_bytes, manifest_bytes]:
        raise _error("Historical P-CERT1 physical/Git bytes drifted")
    topology = authority.get("topology")
    if (
        authority.get("authority_version") != H1_AUTHORITY_VERSION
        or authority.get("gate") != "P-CERT"
        or authority.get("status") != "locked_unpublished"
        or not isinstance(topology, Mapping)
        or topology.get("h_cert_commit") != contract.h1_cert_commit
        or topology.get("p_cert_commit") is not None
        or authority.get("h_scope") != expected_h1_scope()
    ):
        raise _error("Historical P-CERT1 authority identity drifted")
    authority_record = {
        "path": H1_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    if manifest != {
        "manifest_version": H1_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h_cert_commit": contract.h1_cert_commit,
        "manifest_last": True,
        "ordered_paths": [
            H1_AUTHORITY_PATH.as_posix(),
            H1_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }:
        raise _error("Historical P-CERT1 companion identity drifted")
    p1_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p1_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p1_cert_commit,
            spec=spec,
            context="Historical P-CERT1 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT1 physical/Git bytes drifted")
        p1_records.append(record)
    return h1_records, p1_records


def _historical_h2_isolation() -> Mapping[str, Any]:
    """Return the exact isolation projection sealed by superseded P-CERT2."""

    current = dict(_historical_h3_isolation())
    for key in (
        "failed_dvc_partial_tree_not_adopted_for_cleanup",
        "nonexact_cleanup_preserves_namespace",
        "composite_error_identifies_sanitized_active_error_and_cleanup_failure",
        "superseded_p2_retry_authorized",
    ):
        current.pop(key)
    return current


def _historical_h3_isolation() -> Mapping[str, Any]:
    """Return the exact isolation projection sealed in immutable P-CERT3."""

    current = dict(_historical_h4_isolation())
    for key in (
        "credential_path_rebased_to_retained_fd",
        "credential_target_regular_single_link",
        "credential_target_group_or_other_writable",
        "private_dvc_effective_configuration_equivalent_except_owned_cache",
        "owned_site_cache_count",
        "owned_site_cache_roles",
        "owned_site_cache_filesystem_mode",
        "owned_site_caches_separated",
        "owned_site_cache_paths_serialized",
        "version_seal_before_private_config_or_pull",
        "single_dvc_runtime_retained_through_final_status_and_version_probe",
        "dvc_runtime_cross_call_identity_revalidated",
        "used_by_all_isolated_dvc_commands",
        "copied_core_site_cache_dir_used",
        "main_dvc_site_cache_metadata_inode_inventory_unchanged",
        "main_dvc_command_run",
        "main_worktree_dvc_status_executed",
        "main_worktree_dvc_static_boundary_verified",
        "main_worktree_dvc_state_source",
        "real_dvc_execution_scope",
        "superseded_p3_retry_authorized",
    ):
        current.pop(key)
    return current


def _historical_h4_isolation() -> Mapping[str, Any]:
    """Return the exact isolation projection sealed in immutable P-CERT4."""

    current = dict(_historical_h5_isolation())
    current["network_policy"] = {
        "git_clone_from_origin": "allowed",
        "eight_directed_dvc_pulls": "allowed",
        "loopback_postgresql": "allowed",
        "scientific_or_general_network": "forbidden",
    }
    for key in (
        "operational_cache_fields_normalized_before_section_set_equivalence",
        "only_owned_cache_dir_and_type_may_differ",
        "credential_fds_passed_to_dvc_config_commands",
        "first_credential_fd_subprocess_exposure",
        "superseded_p4_retry_authorized",
    ):
        current.pop(key)
    return current


def _historical_h7_isolation() -> Mapping[str, Any]:
    """Return the exact isolation projection sealed in immutable P-CERT7."""

    current = dict(_historical_h8_isolation())
    for key in (
        "forbidden_read_prefix_dispositions",
        "forbidden_read_path_dispositions",
        "superseded_p7_retry_authorized",
        "postgres_cleanup_policy",
    ):
        current.pop(key)
    return current


def _historical_h8_isolation() -> Mapping[str, Any]:
    """Return the exact isolation projection sealed in immutable P-CERT8."""

    current = dict(_expected_isolation())
    for key in (
        "superseded_p17_retry_authorized",
        "superseded_p16_retry_authorized",
        "superseded_p15_retry_authorized",
        "superseded_p14_retry_authorized",
        "superseded_p12_retry_authorized",
        "superseded_p11_retry_authorized",
        "superseded_p10_retry_authorized",
        "superseded_p9_retry_authorized",
        "postgres_connection_policy",
        "postgres_startup_stability_policy",
        "postgres_destroy_poll_policy",
        "test_access_guard_policy",
        "superseded_p8_retry_authorized",
        "sandbox_mountpoint_policy",
        "sandbox_smoke_policy",
        "cleanup_diagnostic_policy",
        "public_tests_junit_diagnostic_policy",
    ):
        current.pop(key)
    return current


def _historical_h6_isolation() -> Mapping[str, Any]:
    """Return the exact isolation projection sealed in immutable P-CERT6."""

    current = dict(_historical_h7_isolation())
    current.pop("superseded_p6_retry_authorized")
    current.pop("postgres_portable_path_policy")
    return current


def _historical_h5_isolation() -> Mapping[str, Any]:
    """Return the exact isolation projection sealed in immutable P-CERT5."""

    current = dict(_historical_h6_isolation())
    for key in (
        "superseded_p5_retry_authorized",
        "post_restore_status_pointer_paths",
        "post_verification_status_pointer_paths",
        "partial_clone_global_status_authorized",
    ):
        current.pop(key)
    return current


def _historical_h7_prohibitions() -> Mapping[str, bool]:
    """Return the exact prohibition projection sealed in immutable P-CERT7."""

    historical = dict(_historical_h8_prohibitions())
    for key in (
        "forbidden_read_path_kind_disposition_drift",
        "postgres_cleanup_ownership_or_identity_drift",
        "unsafe_internal_cleanup_diagnostics",
    ):
        historical.pop(key)
    return historical


def _historical_h8_prohibitions() -> Mapping[str, bool]:
    """Return the exact prohibition projection sealed in immutable P-CERT8."""

    historical = dict(PROHIBITIONS)
    for key in (
        "postgres_connection_policy_drift",
        "postgres_startup_stability_policy_drift",
        "sandbox_mountpoint_policy_drift",
        "sandbox_smoke_or_marker_cleanup_drift",
        "cleanup_diagnostic_reason_code_drift",
        "public_tests_junit_failure_diagnostic_policy_drift",
    ):
        historical.pop(key)
    return historical


def _historical_h6_prohibitions() -> Mapping[str, bool]:
    """Return the exact prohibition projection sealed in immutable P-CERT6."""

    historical = dict(_historical_h7_prohibitions())
    historical.pop("postgres_portable_path_projection_drift")
    return historical


def _historical_h5_prohibitions() -> Mapping[str, bool]:
    """Return the exact prohibition projection sealed in immutable P-CERT5."""

    historical = dict(_historical_h6_prohibitions())
    historical.pop("partial_clone_global_dvc_status")
    historical.pop("dvc_status_sweep_scope_or_order_drift")
    return historical


def _historical_h4_prohibitions() -> Mapping[str, bool]:
    """Return the exact prohibition projection sealed in immutable P-CERT4."""

    historical = dict(_historical_h5_prohibitions())
    historical.pop("private_dvc_operational_cache_equivalence_drift")
    historical.pop("credential_fd_exposure_before_first_directed_pull")
    return historical


def _historical_prohibitions() -> Mapping[str, bool]:
    """Return the prohibition projection sealed before H-CERT4."""

    historical = dict(_historical_h4_prohibitions())
    for key in (
        "main_worktree_dvc_command_execution",
        "owned_site_cache_paths_serialization",
        "main_dvc_site_cache_payload_open_or_hash",
        "owned_site_cache_role_or_separation_drift",
        "private_dvc_configuration_or_pull_before_version_seal",
        "dvc_runtime_cross_call_identity_or_lifetime_drift",
    ):
        historical.pop(key)
    return historical


def _historical_h2_suite_record(
    contract: FinalCertificationContract,
) -> dict[str, Any]:
    """Reconstruct the public-suite projection sealed in immutable P-CERT2."""

    suite = contract.test_suite
    return {
        "suite_kind": suite.suite_kind,
        "positive_test_paths": list(suite.positive_test_paths),
        "exact_skipped_nodes": list(HISTORICAL_EXACT_SKIPPED_NODES),
        "exact_skip_reason": HISTORICAL_EXACT_SKIP_REASON,
        "e2e_nodes": list(suite.e2e_nodes),
        "selectors": list(suite.selectors),
        "command_template": list(suite.command_template),
        "static_commands": [list(command) for command in suite.static_commands],
        "suite_lock": {
            "status": "locked",
            "selector_count": 39,
            "collected_test_count": 905,
            "nodeids_sha256": (
                "679cfd4e62e6eb9f7eb14e9ba1739f7b427fe56a65dab92ac3b39c0ddff42c03"
            ),
            "allowed_skip_count": 7,
        },
    }


def _historical_h3_suite_record(
    contract: FinalCertificationContract,
) -> dict[str, Any]:
    """Reconstruct the public-suite projection sealed in immutable P-CERT3."""

    suite = _historical_locked_suite_record(contract)
    suite["suite_lock"] = {
        "status": "locked",
        "selector_count": 39,
        "collected_test_count": 920,
        "nodeids_sha256": (
            "b6ebc960455574fb8b07c76467e1111c2b34f401ab6c83fcddc03f5857242367"
        ),
        "allowed_skip_count": 7,
    }
    return suite


def _historical_locked_suite_record(
    contract: FinalCertificationContract,
) -> dict[str, Any]:
    """Return the exact seven-skip suite sealed from P-CERT4 through P-CERT9."""

    suite = test_suite_record(contract)
    suite["exact_skipped_nodes"] = list(HISTORICAL_EXACT_SKIPPED_NODES)
    suite["exact_skip_reason"] = HISTORICAL_EXACT_SKIP_REASON
    suite["suite_lock"]["allowed_skip_count"] = len(
        HISTORICAL_EXACT_SKIPPED_NODES
    )
    return suite


def _historical_h2_p2_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
    h1_records: Sequence[Mapping[str, Any]] | None = None,
    p1_records: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H2/P2 before accepting H3."""

    if (
        _commit_parents(root, contract.h2_cert_commit)
        != (contract.p1_cert_commit,)
        or _commit_scope(root, contract.h2_cert_commit) != expected_h2_scope()
        or _commit_parents(root, contract.p2_cert_commit)
        != (contract.h2_cert_commit,)
        or _commit_scope(root, contract.p2_cert_commit) != expected_p2_scope()
    ):
        raise _error("Historical H2/P2 topology or scope drifted")
    if h1_records is None or p1_records is None:
        observed_h1, observed_p1 = _historical_h1_p1_records(contract, root=root)
        h1_records = observed_h1
        p1_records = observed_p1
    h2_records = []
    for spec in contract.h2_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h2_cert_commit,
            spec=spec,
            context="Historical H-CERT2 component",
        )
        h2_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    physical_p2_payloads = [
        _publication_file_record_and_payload(
            root,
            commit=contract.p2_cert_commit,
            spec=spec,
        )[1]
        for spec in contract.p2_scope
    ]
    authority, authority_bytes = _decode_canonical_public_json(
        root, H2_AUTHORITY_PATH, commit=contract.p2_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H2_AUTHORITY_MANIFEST_PATH, commit=contract.p2_cert_commit
    )
    if physical_p2_payloads != [authority_bytes, manifest_bytes]:
        raise _error("Historical P-CERT2 physical/Git bytes drifted")
    if (
        len(authority_bytes) != H2_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H2_AUTHORITY_SHA256
        or len(manifest_bytes) != H2_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H2_AUTHORITY_MANIFEST_SHA256
    ):
        raise _error("Historical P-CERT2 canonical byte identity drifted")

    anchors = collect_anchor_input_records(contract, root=root)
    pointers = collect_dvc_pointer_records(contract, root=root)
    suite = _historical_h2_suite_record(contract)
    expected_authority = {
        "authority_version": H2_AUTHORITY_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "topology": {
            "closure_source_commit": contract.closure_source_commit,
            "r_syn_commit": contract.r_syn_commit,
            "editorial_commit": contract.editorial_commit,
            "h1_cert_commit": contract.h1_cert_commit,
            "p1_cert_commit": contract.p1_cert_commit,
            "h_cert_commit": contract.h2_cert_commit,
            "p_cert_commit": None,
            "r_cert_executable_tree_must_equal_p_cert": True,
        },
        "p1_failure": {
            "status": "superseded_failed",
            "failure_stage": "after_git_clone_namespace_validation",
            "dvc_pull_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
        },
        "h1_scope": expected_h1_scope(),
        "h1_component_records": list(h1_records),
        "h1_component_records_digest": digest_records(h1_records),
        "p1_scope": expected_p1_scope(),
        "p1_component_records": list(p1_records),
        "p1_component_records_digest": digest_records(p1_records),
        "h_scope": expected_h2_scope(),
        "h_component_records": h2_records,
        "h_component_records_digest": digest_records(h2_records),
        "anchor_input_records": anchors,
        "anchor_input_records_digest": digest_records(anchors),
        "dvc_pointer_records": pointers,
        "dvc_pointer_records_digest": digest_records(pointers),
        "test_suite": suite,
        "test_suite_digest": sha256_bytes(canonical_json_bytes(suite)),
        "ordered_r_cert_output_paths": list(contract.output_paths),
        "r_cert_output_paths_digest": digest_strings(contract.output_paths),
        "isolation": dict(_historical_h2_isolation()),
        "authorizations": dict(AUTHORIZATION_POLICY),
        "prohibitions": dict(_historical_prohibitions()),
    }
    if authority != expected_authority or authority_bytes != canonical_json_bytes(
        expected_authority
    ):
        raise _error("Historical P-CERT2 authority identity drifted")
    authority_record = {
        "path": H2_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H2_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h_cert_commit": contract.h2_cert_commit,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H2_AUTHORITY_PATH.as_posix(),
            H2_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT2 companion identity drifted")
    p2_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p2_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p2_cert_commit,
            spec=spec,
            context="Historical P-CERT2 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT2 physical/Git bytes drifted")
        p2_records.append(record)
    return h2_records, p2_records


def _historical_h1_p1_h2_p2_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Return every immutable H/P predecessor record in topology order."""

    h1_records, p1_records = _historical_h1_p1_records(contract, root=root)
    h2_records, p2_records = _historical_h2_p2_records(
        contract,
        root=root,
        h1_records=h1_records,
        p1_records=p1_records,
    )
    return h1_records, p1_records, h2_records, p2_records


def _historical_h3_p3_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
    predecessor_records: tuple[
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
    ] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT3/P-CERT3."""

    if (
        _commit_parents(root, contract.h3_cert_commit)
        != (contract.p2_cert_commit,)
        or _commit_scope(root, contract.h3_cert_commit) != expected_h3_scope()
        or _commit_parents(root, contract.p3_cert_commit)
        != (contract.h3_cert_commit,)
        or _commit_scope(root, contract.p3_cert_commit) != expected_p3_scope()
    ):
        raise _error("Historical H3/P3 topology or scope drifted")
    if predecessor_records is None:
        predecessor_records = _historical_h1_p1_h2_p2_records(
            contract, root=root
        )
    h1_records, p1_records, h2_records, p2_records = predecessor_records
    h3_records: list[dict[str, Any]] = []
    for spec in contract.h3_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h3_cert_commit,
            spec=spec,
            context="Historical H-CERT3 component",
        )
        h3_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H3_AUTHORITY_PATH, commit=contract.p3_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H3_AUTHORITY_MANIFEST_PATH, commit=contract.p3_cert_commit
    )
    if (
        len(authority_bytes) != H3_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H3_AUTHORITY_SHA256
        or len(manifest_bytes) != H3_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H3_AUTHORITY_MANIFEST_SHA256
    ):
        raise _error("Historical P-CERT3 canonical byte identity drifted")
    anchors = collect_anchor_input_records(contract, root=root)
    pointers = collect_dvc_pointer_records(contract, root=root)
    suite = _historical_h3_suite_record(contract)
    outputs = list(contract.output_paths)
    expected_authority = {
        "authority_version": H3_AUTHORITY_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "topology": {
            "closure_source_commit": contract.closure_source_commit,
            "r_syn_commit": contract.r_syn_commit,
            "editorial_commit": contract.editorial_commit,
            "h1_cert_commit": contract.h1_cert_commit,
            "p1_cert_commit": contract.p1_cert_commit,
            "h2_cert_commit": contract.h2_cert_commit,
            "p2_cert_commit": contract.p2_cert_commit,
            "h3_cert_commit": contract.h3_cert_commit,
            "p3_cert_commit": None,
            "h_cert_commit": contract.h3_cert_commit,
            "p_cert_commit": None,
            "r_cert_executable_tree_must_equal_p_cert": True,
        },
        "p1_failure": {
            "status": "superseded_failed",
            "failure_stage": "after_git_clone_namespace_validation",
            "dvc_pull_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
        },
        "p2_failure": expected_p2_failure_record(),
        "h1_scope": expected_h1_scope(),
        "h1_component_records": list(h1_records),
        "h1_component_records_digest": digest_records(h1_records),
        "p1_scope": expected_p1_scope(),
        "p1_component_records": list(p1_records),
        "p1_component_records_digest": digest_records(p1_records),
        "h2_scope": expected_h2_scope(),
        "h2_component_records": list(h2_records),
        "h2_component_records_digest": digest_records(h2_records),
        "p2_scope": expected_p2_scope(),
        "p2_component_records": list(p2_records),
        "p2_component_records_digest": digest_records(p2_records),
        "h_scope": expected_h3_scope(),
        "h_component_records": h3_records,
        "h_component_records_digest": digest_records(h3_records),
        "h3_scope": expected_h3_scope(),
        "h3_component_records": h3_records,
        "h3_component_records_digest": digest_records(h3_records),
        "p_scope": expected_p3_scope(),
        "p3_scope": expected_p3_scope(),
        "anchor_input_records": anchors,
        "anchor_input_records_digest": digest_records(anchors),
        "dvc_pointer_records": pointers,
        "dvc_pointer_records_digest": digest_records(pointers),
        "test_suite": suite,
        "test_suite_digest": sha256_bytes(canonical_json_bytes(suite)),
        "ordered_r_cert_output_paths": outputs,
        "r_cert_output_paths_digest": digest_strings(outputs),
        "isolation": dict(_historical_h3_isolation()),
        "failure_diagnostics": dict(FAILURE_DIAGNOSTICS_POLICY),
        "authorizations": dict(AUTHORIZATION_POLICY),
        "prohibitions": dict(_historical_prohibitions()),
    }
    if authority != expected_authority or authority_bytes != canonical_json_bytes(
        expected_authority
    ):
        raise _error("Historical P-CERT3 authority identity drifted")
    authority_record = {
        "path": H3_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H3_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": None,
        "h_cert_commit": contract.h3_cert_commit,
        "p_cert_commit": None,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H3_AUTHORITY_PATH.as_posix(),
            H3_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT3 companion identity drifted")
    p3_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p3_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p3_cert_commit,
            spec=spec,
            context="Historical P-CERT3 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT3 physical/Git bytes drifted")
        p3_records.append(record)
    return h3_records, p3_records


def _historical_h1_p1_h2_p2_h3_p3_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    predecessor = _historical_h1_p1_h2_p2_records(contract, root=root)
    h3_records, p3_records = _historical_h3_p3_records(
        contract, root=root, predecessor_records=predecessor
    )
    return (*predecessor, h3_records, p3_records)


def _historical_h4_p4_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
    predecessor_records: tuple[
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
    ] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT4/P-CERT4."""

    if (
        _commit_parents(root, contract.h4_cert_commit)
        != (contract.p3_cert_commit,)
        or _commit_scope(root, contract.h4_cert_commit) != expected_h4_scope()
        or _commit_parents(root, contract.p4_cert_commit)
        != (contract.h4_cert_commit,)
        or _commit_scope(root, contract.p4_cert_commit) != expected_p4_scope()
    ):
        raise _error("Historical H4/P4 topology or scope drifted")
    if predecessor_records is None:
        predecessor_records = _historical_h1_p1_h2_p2_h3_p3_records(
            contract, root=root
        )
    (
        h1_records,
        p1_records,
        h2_records,
        p2_records,
        h3_records,
        p3_records,
    ) = predecessor_records
    h4_records: list[dict[str, Any]] = []
    for spec in contract.h4_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h4_cert_commit,
            spec=spec,
            context="Historical H-CERT4 component",
        )
        h4_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H4_AUTHORITY_PATH, commit=contract.p4_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H4_AUTHORITY_MANIFEST_PATH, commit=contract.p4_cert_commit
    )
    if (
        len(authority_bytes) != H4_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H4_AUTHORITY_SHA256
        or len(manifest_bytes) != H4_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H4_AUTHORITY_MANIFEST_SHA256
    ):
        raise _error("Historical P-CERT4 canonical byte identity drifted")
    anchors = collect_anchor_input_records(contract, root=root)
    pointers = collect_dvc_pointer_records(contract, root=root)
    suite = _historical_locked_suite_record(contract)
    outputs = list(contract.output_paths)
    expected_authority = {
        "authority_version": H4_AUTHORITY_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "topology": {
            "closure_source_commit": contract.closure_source_commit,
            "r_syn_commit": contract.r_syn_commit,
            "editorial_commit": contract.editorial_commit,
            "h1_cert_commit": contract.h1_cert_commit,
            "p1_cert_commit": contract.p1_cert_commit,
            "h2_cert_commit": contract.h2_cert_commit,
            "p2_cert_commit": contract.p2_cert_commit,
            "h3_cert_commit": contract.h3_cert_commit,
            "p3_cert_commit": contract.p3_cert_commit,
            "h4_cert_commit": contract.h4_cert_commit,
            "p4_cert_commit": None,
            "h_cert_commit": contract.h4_cert_commit,
            "p_cert_commit": None,
            "r_cert_executable_tree_must_equal_p_cert": True,
        },
        "p1_failure": {
            "status": "superseded_failed",
            "failure_stage": "after_git_clone_namespace_validation",
            "dvc_pull_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
        },
        "p2_failure": expected_p2_failure_record(),
        "p3_failure": expected_p3_failure_record(),
        "h1_scope": expected_h1_scope(),
        "h1_component_records": list(h1_records),
        "h1_component_records_digest": digest_records(h1_records),
        "p1_scope": expected_p1_scope(),
        "p1_component_records": list(p1_records),
        "p1_component_records_digest": digest_records(p1_records),
        "h2_scope": expected_h2_scope(),
        "h2_component_records": list(h2_records),
        "h2_component_records_digest": digest_records(h2_records),
        "p2_scope": expected_p2_scope(),
        "p2_component_records": list(p2_records),
        "p2_component_records_digest": digest_records(p2_records),
        "h3_scope": expected_h3_scope(),
        "h3_component_records": list(h3_records),
        "h3_component_records_digest": digest_records(h3_records),
        "p3_scope": expected_p3_scope(),
        "p3_component_records": list(p3_records),
        "p3_component_records_digest": digest_records(p3_records),
        "h_scope": expected_h4_scope(),
        "h_component_records": h4_records,
        "h_component_records_digest": digest_records(h4_records),
        "h4_scope": expected_h4_scope(),
        "h4_component_records": h4_records,
        "h4_component_records_digest": digest_records(h4_records),
        "p_scope": expected_p4_scope(),
        "p4_scope": expected_p4_scope(),
        "anchor_input_records": anchors,
        "anchor_input_records_digest": digest_records(anchors),
        "dvc_pointer_records": pointers,
        "dvc_pointer_records_digest": digest_records(pointers),
        "main_dvc_static_boundary": main_dvc_static_boundary_record(
            contract,
            anchor_records=anchors,
            pointer_records=pointers,
        ),
        "test_suite": suite,
        "test_suite_digest": sha256_bytes(canonical_json_bytes(suite)),
        "ordered_r_cert_output_paths": outputs,
        "r_cert_output_paths_digest": digest_strings(outputs),
        "isolation": dict(_historical_h4_isolation()),
        "failure_diagnostics": dict(FAILURE_DIAGNOSTICS_POLICY),
        "authorizations": dict(AUTHORIZATION_POLICY),
        "prohibitions": dict(_historical_h4_prohibitions()),
    }
    if authority != expected_authority or authority_bytes != canonical_json_bytes(
        expected_authority
    ):
        raise _error("Historical P-CERT4 authority identity drifted")
    authority_record = {
        "path": H4_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H4_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": contract.p3_cert_commit,
        "h4_cert_commit": contract.h4_cert_commit,
        "p4_cert_commit": None,
        "h_cert_commit": contract.h4_cert_commit,
        "p_cert_commit": None,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H4_AUTHORITY_PATH.as_posix(),
            H4_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT4 companion identity drifted")
    p4_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p4_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p4_cert_commit,
            spec=spec,
            context="Historical P-CERT4 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT4 physical/Git bytes drifted")
        p4_records.append(record)
    return h4_records, p4_records


def _historical_h1_p1_h2_p2_h3_p3_h4_p4_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    predecessor = _historical_h1_p1_h2_p2_h3_p3_records(contract, root=root)
    h4_records, p4_records = _historical_h4_p4_records(
        contract, root=root, predecessor_records=predecessor
    )
    return (*predecessor, h4_records, p4_records)


def _historical_h5_p5_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
    predecessor_records: tuple[
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
    ] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT5/P-CERT5."""

    if (
        _commit_parents(root, contract.h5_cert_commit)
        != (contract.p4_cert_commit,)
        or _commit_scope(root, contract.h5_cert_commit) != expected_h5_scope()
        or _commit_parents(root, contract.p5_cert_commit)
        != (contract.h5_cert_commit,)
        or _commit_scope(root, contract.p5_cert_commit) != expected_p5_scope()
    ):
        raise _error("Historical H5/P5 topology or scope drifted")
    if predecessor_records is None:
        predecessor_records = _historical_h1_p1_h2_p2_h3_p3_h4_p4_records(
            contract, root=root
        )
    (
        h1_records,
        p1_records,
        h2_records,
        p2_records,
        h3_records,
        p3_records,
        h4_records,
        p4_records,
    ) = predecessor_records
    h5_records: list[dict[str, Any]] = []
    for spec in contract.h5_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h5_cert_commit,
            spec=spec,
            context="Historical H-CERT5 component",
        )
        h5_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H5_AUTHORITY_PATH, commit=contract.p5_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H5_AUTHORITY_MANIFEST_PATH, commit=contract.p5_cert_commit
    )
    if (
        len(authority_bytes) != H5_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H5_AUTHORITY_SHA256
        or len(manifest_bytes) != H5_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H5_AUTHORITY_MANIFEST_SHA256
    ):
        raise _error("Historical P-CERT5 canonical byte identity drifted")
    anchors = collect_anchor_input_records(contract, root=root)
    pointers = collect_dvc_pointer_records(contract, root=root)
    suite = _historical_locked_suite_record(contract)
    outputs = list(contract.output_paths)
    expected_authority = {
        "authority_version": H5_AUTHORITY_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "topology": {
            "closure_source_commit": contract.closure_source_commit,
            "r_syn_commit": contract.r_syn_commit,
            "editorial_commit": contract.editorial_commit,
            "h1_cert_commit": contract.h1_cert_commit,
            "p1_cert_commit": contract.p1_cert_commit,
            "h2_cert_commit": contract.h2_cert_commit,
            "p2_cert_commit": contract.p2_cert_commit,
            "h3_cert_commit": contract.h3_cert_commit,
            "p3_cert_commit": contract.p3_cert_commit,
            "h4_cert_commit": contract.h4_cert_commit,
            "p4_cert_commit": contract.p4_cert_commit,
            "h5_cert_commit": contract.h5_cert_commit,
            "p5_cert_commit": None,
            "h_cert_commit": contract.h5_cert_commit,
            "p_cert_commit": None,
            "r_cert_executable_tree_must_equal_p_cert": True,
        },
        "p1_failure": {
            "status": "superseded_failed",
            "failure_stage": "after_git_clone_namespace_validation",
            "dvc_pull_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
        },
        "p2_failure": expected_p2_failure_record(),
        "p3_failure": expected_p3_failure_record(),
        "p4_failure": expected_p4_failure_record(),
        "h1_scope": expected_h1_scope(),
        "h1_component_records": list(h1_records),
        "h1_component_records_digest": digest_records(h1_records),
        "p1_scope": expected_p1_scope(),
        "p1_component_records": list(p1_records),
        "p1_component_records_digest": digest_records(p1_records),
        "h2_scope": expected_h2_scope(),
        "h2_component_records": list(h2_records),
        "h2_component_records_digest": digest_records(h2_records),
        "p2_scope": expected_p2_scope(),
        "p2_component_records": list(p2_records),
        "p2_component_records_digest": digest_records(p2_records),
        "h3_scope": expected_h3_scope(),
        "h3_component_records": list(h3_records),
        "h3_component_records_digest": digest_records(h3_records),
        "p3_scope": expected_p3_scope(),
        "p3_component_records": list(p3_records),
        "p3_component_records_digest": digest_records(p3_records),
        "h4_scope": expected_h4_scope(),
        "h4_component_records": list(h4_records),
        "h4_component_records_digest": digest_records(h4_records),
        "p4_scope": expected_p4_scope(),
        "p4_component_records": list(p4_records),
        "p4_component_records_digest": digest_records(p4_records),
        "h_scope": expected_h5_scope(),
        "h_component_records": h5_records,
        "h_component_records_digest": digest_records(h5_records),
        "h5_scope": expected_h5_scope(),
        "h5_component_records": h5_records,
        "h5_component_records_digest": digest_records(h5_records),
        "p_scope": expected_p5_scope(),
        "p5_scope": expected_p5_scope(),
        "anchor_input_records": anchors,
        "anchor_input_records_digest": digest_records(anchors),
        "dvc_pointer_records": pointers,
        "dvc_pointer_records_digest": digest_records(pointers),
        "main_dvc_static_boundary": main_dvc_static_boundary_record(
            contract,
            anchor_records=anchors,
            pointer_records=pointers,
        ),
        "test_suite": suite,
        "test_suite_digest": sha256_bytes(canonical_json_bytes(suite)),
        "ordered_r_cert_output_paths": outputs,
        "r_cert_output_paths_digest": digest_strings(outputs),
        "isolation": dict(_historical_h5_isolation()),
        "failure_diagnostics": dict(FAILURE_DIAGNOSTICS_POLICY),
        "authorizations": dict(AUTHORIZATION_POLICY),
        "prohibitions": dict(_historical_h5_prohibitions()),
    }
    if authority != expected_authority or authority_bytes != canonical_json_bytes(
        expected_authority
    ):
        raise _error("Historical P-CERT5 authority identity drifted")
    authority_record = {
        "path": H5_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H5_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": contract.p3_cert_commit,
        "h4_cert_commit": contract.h4_cert_commit,
        "p4_cert_commit": contract.p4_cert_commit,
        "h5_cert_commit": contract.h5_cert_commit,
        "p5_cert_commit": None,
        "h_cert_commit": contract.h5_cert_commit,
        "p_cert_commit": None,
        "supersedes_p4": True,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H5_AUTHORITY_PATH.as_posix(),
            H5_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT5 companion identity drifted")
    p5_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p5_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p5_cert_commit,
            spec=spec,
            context="Historical P-CERT5 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT5 physical/Git bytes drifted")
        p5_records.append(record)
    return h5_records, p5_records


def _historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    predecessor = _historical_h1_p1_h2_p2_h3_p3_h4_p4_records(
        contract, root=root
    )
    h5_records, p5_records = _historical_h5_p5_records(
        contract, root=root, predecessor_records=predecessor
    )
    return (*predecessor, h5_records, p5_records)


def _historical_h6_p6_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT6/P-CERT6."""

    if (
        _commit_parents(root, contract.h6_cert_commit)
        != (contract.p5_cert_commit,)
        or _commit_scope(root, contract.h6_cert_commit) != expected_h6_scope()
        or _commit_parents(root, contract.p6_cert_commit)
        != (contract.h6_cert_commit,)
        or _commit_scope(root, contract.p6_cert_commit) != expected_p6_scope()
    ):
        raise _error("Historical H6/P6 topology or scope drifted")
    h6_records: list[dict[str, Any]] = []
    for spec in contract.h6_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h6_cert_commit,
            spec=spec,
            context="Historical H-CERT6 component",
        )
        h6_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H6_AUTHORITY_PATH, commit=contract.p6_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H6_AUTHORITY_MANIFEST_PATH, commit=contract.p6_cert_commit
    )
    if (
        len(authority_bytes) != H6_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H6_AUTHORITY_SHA256
        or len(manifest_bytes) != H6_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H6_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H6_AUTHORITY_VERSION
        or authority.get("isolation") != _historical_h6_isolation()
        or authority.get("prohibitions") != _historical_h6_prohibitions()
        or authority.get("p5_failure") != expected_p5_failure_record()
    ):
        raise _error("Historical P-CERT6 canonical byte identity drifted")
    authority_record = {
        "path": H6_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H6_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": contract.p3_cert_commit,
        "h4_cert_commit": contract.h4_cert_commit,
        "p4_cert_commit": contract.p4_cert_commit,
        "h5_cert_commit": contract.h5_cert_commit,
        "p5_cert_commit": contract.p5_cert_commit,
        "h6_cert_commit": contract.h6_cert_commit,
        "p6_cert_commit": None,
        "h_cert_commit": contract.h6_cert_commit,
        "p_cert_commit": None,
        "supersedes_p5": True,
        "supersedes_p4": True,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H6_AUTHORITY_PATH.as_posix(),
            H6_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT6 companion identity drifted")
    p6_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p6_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p6_cert_commit,
            spec=spec,
            context="Historical P-CERT6 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT6 physical/Git bytes drifted")
        p6_records.append(record)
    return h6_records, p6_records


def _historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_h6_p6_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    predecessor = _historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_records(
        contract, root=root
    )
    h6_records, p6_records = _historical_h6_p6_records(contract, root=root)
    return (*predecessor, h6_records, p6_records)


def _historical_h7_p7_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT7/P-CERT7."""

    if (
        _commit_parents(root, contract.h7_cert_commit)
        != (contract.p6_cert_commit,)
        or _commit_scope(root, contract.h7_cert_commit) != expected_h7_scope()
        or _commit_parents(root, contract.p7_cert_commit)
        != (contract.h7_cert_commit,)
        or _commit_scope(root, contract.p7_cert_commit) != expected_p7_scope()
    ):
        raise _error("Historical H7/P7 topology or scope drifted")
    h7_records: list[dict[str, Any]] = []
    for spec in contract.h7_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h7_cert_commit,
            spec=spec,
            context="Historical H-CERT7 component",
        )
        h7_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H7_AUTHORITY_PATH, commit=contract.p7_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H7_AUTHORITY_MANIFEST_PATH, commit=contract.p7_cert_commit
    )
    if (
        len(authority_bytes) != H7_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H7_AUTHORITY_SHA256
        or len(manifest_bytes) != H7_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H7_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H7_AUTHORITY_VERSION
        or authority.get("isolation") != _historical_h7_isolation()
        or authority.get("prohibitions") != _historical_h7_prohibitions()
        or authority.get("p6_failure") != expected_p6_failure_record()
    ):
        raise _error("Historical P-CERT7 canonical byte identity drifted")
    authority_record = {
        "path": H7_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H7_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": contract.p3_cert_commit,
        "h4_cert_commit": contract.h4_cert_commit,
        "p4_cert_commit": contract.p4_cert_commit,
        "h5_cert_commit": contract.h5_cert_commit,
        "p5_cert_commit": contract.p5_cert_commit,
        "h6_cert_commit": contract.h6_cert_commit,
        "p6_cert_commit": contract.p6_cert_commit,
        "h7_cert_commit": contract.h7_cert_commit,
        "p7_cert_commit": None,
        "h_cert_commit": contract.h7_cert_commit,
        "p_cert_commit": None,
        "supersedes_p6": True,
        "supersedes_p5": True,
        "supersedes_p4": True,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H7_AUTHORITY_PATH.as_posix(),
            H7_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT7 companion identity drifted")
    p7_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p7_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p7_cert_commit,
            spec=spec,
            context="Historical P-CERT7 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT7 physical/Git bytes drifted")
        p7_records.append(record)
    return h7_records, p7_records


def _historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_h6_p6_h7_p7_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    predecessor = _historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_h6_p6_records(
        contract, root=root
    )
    h7_records, p7_records = _historical_h7_p7_records(contract, root=root)
    return (*predecessor, h7_records, p7_records)


def _historical_h8_p8_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT8/P-CERT8."""

    if (
        _commit_parents(root, contract.h8_cert_commit)
        != (contract.p7_cert_commit,)
        or _commit_scope(root, contract.h8_cert_commit) != expected_h8_scope()
        or _commit_parents(root, contract.p8_cert_commit)
        != (contract.h8_cert_commit,)
        or _commit_scope(root, contract.p8_cert_commit) != expected_p8_scope()
    ):
        raise _error("Historical H8/P8 topology or scope drifted")
    h8_records: list[dict[str, Any]] = []
    for spec in contract.h8_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h8_cert_commit,
            spec=spec,
            context="Historical H-CERT8 component",
        )
        h8_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H8_AUTHORITY_PATH, commit=contract.p8_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H8_AUTHORITY_MANIFEST_PATH, commit=contract.p8_cert_commit
    )
    if (
        len(authority_bytes) != H8_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H8_AUTHORITY_SHA256
        or len(manifest_bytes) != H8_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H8_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H8_AUTHORITY_VERSION
        or authority.get("isolation") != _historical_h8_isolation()
        or authority.get("prohibitions") != _historical_h8_prohibitions()
        or authority.get("p7_failure") != expected_p7_failure_record()
    ):
        raise _error("Historical P-CERT8 canonical byte identity drifted")
    authority_record = {
        "path": H8_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H8_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": contract.p3_cert_commit,
        "h4_cert_commit": contract.h4_cert_commit,
        "p4_cert_commit": contract.p4_cert_commit,
        "h5_cert_commit": contract.h5_cert_commit,
        "p5_cert_commit": contract.p5_cert_commit,
        "h6_cert_commit": contract.h6_cert_commit,
        "p6_cert_commit": contract.p6_cert_commit,
        "h7_cert_commit": contract.h7_cert_commit,
        "p7_cert_commit": contract.p7_cert_commit,
        "h8_cert_commit": contract.h8_cert_commit,
        "p8_cert_commit": None,
        "h_cert_commit": contract.h8_cert_commit,
        "p_cert_commit": None,
        "supersedes_p7": True,
        "supersedes_p6": True,
        "supersedes_p5": True,
        "supersedes_p4": True,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H8_AUTHORITY_PATH.as_posix(),
            H8_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT8 companion identity drifted")
    p8_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p8_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p8_cert_commit,
            spec=spec,
            context="Historical P-CERT8 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT8 physical/Git bytes drifted")
        p8_records.append(record)
    return h8_records, p8_records


def _historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_h6_p6_h7_p7_h8_p8_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    predecessor = (
        _historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_h6_p6_h7_p7_records(
            contract, root=root
        )
    )
    h8_records, p8_records = _historical_h8_p8_records(contract, root=root)
    return (*predecessor, h8_records, p8_records)


def _historical_h9_p9_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT9/P-CERT9."""

    if (
        _commit_parents(root, contract.h9_cert_commit)
        != (contract.p8_cert_commit,)
        or _commit_scope(root, contract.h9_cert_commit) != expected_h9_scope()
        or _commit_parents(root, contract.p9_cert_commit)
        != (contract.h9_cert_commit,)
        or _commit_scope(root, contract.p9_cert_commit) != expected_p9_scope()
    ):
        raise _error("Historical H9/P9 topology or scope drifted")
    h9_records: list[dict[str, Any]] = []
    for spec in contract.h9_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h9_cert_commit,
            spec=spec,
            context="Historical H-CERT9 component",
        )
        h9_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H9_AUTHORITY_PATH, commit=contract.p9_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H9_AUTHORITY_MANIFEST_PATH, commit=contract.p9_cert_commit
    )
    if (
        len(authority_bytes) != H9_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H9_AUTHORITY_SHA256
        or len(manifest_bytes) != H9_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H9_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H9_AUTHORITY_VERSION
        or authority.get("p8_failure") != expected_p8_failure_record()
    ):
        raise _error("Historical P-CERT9 canonical byte identity drifted")
    authority_record = {
        "path": H9_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H9_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": contract.p3_cert_commit,
        "h4_cert_commit": contract.h4_cert_commit,
        "p4_cert_commit": contract.p4_cert_commit,
        "h5_cert_commit": contract.h5_cert_commit,
        "p5_cert_commit": contract.p5_cert_commit,
        "h6_cert_commit": contract.h6_cert_commit,
        "p6_cert_commit": contract.p6_cert_commit,
        "h7_cert_commit": contract.h7_cert_commit,
        "p7_cert_commit": contract.p7_cert_commit,
        "h8_cert_commit": contract.h8_cert_commit,
        "p8_cert_commit": contract.p8_cert_commit,
        "h9_cert_commit": contract.h9_cert_commit,
        "p9_cert_commit": None,
        "h_cert_commit": contract.h9_cert_commit,
        "p_cert_commit": None,
        "supersedes_p8": True,
        "supersedes_p7": True,
        "supersedes_p6": True,
        "supersedes_p5": True,
        "supersedes_p4": True,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H9_AUTHORITY_PATH.as_posix(),
            H9_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT9 companion identity drifted")
    p9_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p9_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p9_cert_commit,
            spec=spec,
            context="Historical P-CERT9 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT9 physical/Git bytes drifted")
        p9_records.append(record)
    return h9_records, p9_records


def _historical_through_p9_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], ...]:
    predecessor = (
        _historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_h6_p6_h7_p7_h8_p8_records(
            contract, root=root
        )
    )
    h9_records, p9_records = _historical_h9_p9_records(contract, root=root)
    return (*predecessor, h9_records, p9_records)


def _historical_h10_p10_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT10/P-CERT10."""

    if (
        _commit_parents(root, contract.h10_cert_commit)
        != (contract.p9_cert_commit,)
        or _commit_scope(root, contract.h10_cert_commit) != expected_h10_scope()
        or _commit_parents(root, contract.p10_cert_commit)
        != (contract.h10_cert_commit,)
        or _commit_scope(root, contract.p10_cert_commit) != expected_p10_scope()
    ):
        raise _error("Historical H10/P10 topology or scope drifted")
    h10_records: list[dict[str, Any]] = []
    for spec in contract.h10_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h10_cert_commit,
            spec=spec,
            context="Historical H-CERT10 component",
        )
        h10_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H10_AUTHORITY_PATH, commit=contract.p10_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H10_AUTHORITY_MANIFEST_PATH, commit=contract.p10_cert_commit
    )
    if (
        len(authority_bytes) != H10_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H10_AUTHORITY_SHA256
        or len(manifest_bytes) != H10_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H10_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H10_AUTHORITY_VERSION
        or authority.get("p9_failure") != expected_p9_failure_record()
    ):
        raise _error("Historical P-CERT10 canonical byte identity drifted")
    authority_record = {
        "path": H10_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H10_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": contract.p3_cert_commit,
        "h4_cert_commit": contract.h4_cert_commit,
        "p4_cert_commit": contract.p4_cert_commit,
        "h5_cert_commit": contract.h5_cert_commit,
        "p5_cert_commit": contract.p5_cert_commit,
        "h6_cert_commit": contract.h6_cert_commit,
        "p6_cert_commit": contract.p6_cert_commit,
        "h7_cert_commit": contract.h7_cert_commit,
        "p7_cert_commit": contract.p7_cert_commit,
        "h8_cert_commit": contract.h8_cert_commit,
        "p8_cert_commit": contract.p8_cert_commit,
        "h9_cert_commit": contract.h9_cert_commit,
        "p9_cert_commit": contract.p9_cert_commit,
        "h10_cert_commit": contract.h10_cert_commit,
        "p10_cert_commit": None,
        "h_cert_commit": contract.h10_cert_commit,
        "p_cert_commit": None,
        "supersedes_p9": True,
        "supersedes_p8": True,
        "supersedes_p7": True,
        "supersedes_p6": True,
        "supersedes_p5": True,
        "supersedes_p4": True,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H10_AUTHORITY_PATH.as_posix(),
            H10_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT10 companion identity drifted")
    p10_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p10_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p10_cert_commit,
            spec=spec,
            context="Historical P-CERT10 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT10 physical/Git bytes drifted")
        p10_records.append(record)
    return h10_records, p10_records


def _historical_through_p10_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], ...]:
    predecessor = _historical_through_p9_records(contract, root=root)
    h10_records, p10_records = _historical_h10_p10_records(contract, root=root)
    return (*predecessor, h10_records, p10_records)


def _historical_h11_p11_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT11/P-CERT11."""

    if (
        _commit_parents(root, contract.h11_cert_commit)
        != (contract.p10_cert_commit,)
        or _commit_scope(root, contract.h11_cert_commit) != expected_h11_scope()
        or _commit_parents(root, contract.p11_cert_commit)
        != (contract.h11_cert_commit,)
        or _commit_scope(root, contract.p11_cert_commit) != expected_p11_scope()
    ):
        raise _error("Historical H11/P11 topology or scope drifted")
    h11_records: list[dict[str, Any]] = []
    for spec in contract.h11_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h11_cert_commit,
            spec=spec,
            context="Historical H-CERT11 component",
        )
        h11_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H11_AUTHORITY_PATH, commit=contract.p11_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H11_AUTHORITY_MANIFEST_PATH, commit=contract.p11_cert_commit
    )
    if (
        len(authority_bytes) != H11_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H11_AUTHORITY_SHA256
        or len(manifest_bytes) != H11_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H11_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H11_AUTHORITY_VERSION
        or authority.get("p10_failure") != expected_p10_failure_record()
    ):
        raise _error("Historical P-CERT11 canonical byte identity drifted")
    authority_record = {
        "path": H11_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H11_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": contract.p3_cert_commit,
        "h4_cert_commit": contract.h4_cert_commit,
        "p4_cert_commit": contract.p4_cert_commit,
        "h5_cert_commit": contract.h5_cert_commit,
        "p5_cert_commit": contract.p5_cert_commit,
        "h6_cert_commit": contract.h6_cert_commit,
        "p6_cert_commit": contract.p6_cert_commit,
        "h7_cert_commit": contract.h7_cert_commit,
        "p7_cert_commit": contract.p7_cert_commit,
        "h8_cert_commit": contract.h8_cert_commit,
        "p8_cert_commit": contract.p8_cert_commit,
        "h9_cert_commit": contract.h9_cert_commit,
        "p9_cert_commit": contract.p9_cert_commit,
        "h10_cert_commit": contract.h10_cert_commit,
        "p10_cert_commit": contract.p10_cert_commit,
        "h11_cert_commit": contract.h11_cert_commit,
        "p11_cert_commit": None,
        "h_cert_commit": contract.h11_cert_commit,
        "p_cert_commit": None,
        "supersedes_p10": True,
        "supersedes_p9": True,
        "supersedes_p8": True,
        "supersedes_p7": True,
        "supersedes_p6": True,
        "supersedes_p5": True,
        "supersedes_p4": True,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H11_AUTHORITY_PATH.as_posix(),
            H11_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT11 companion identity drifted")
    p11_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p11_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p11_cert_commit,
            spec=spec,
            context="Historical P-CERT11 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT11 physical/Git bytes drifted")
        p11_records.append(record)
    return h11_records, p11_records


def _historical_through_p11_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], ...]:
    predecessor = _historical_through_p10_records(contract, root=root)
    h11_records, p11_records = _historical_h11_p11_records(contract, root=root)
    return (*predecessor, h11_records, p11_records)


def _historical_h12_p12_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT12/P-CERT12."""

    if (
        _commit_parents(root, contract.h12_cert_commit)
        != (contract.p11_cert_commit,)
        or _commit_scope(root, contract.h12_cert_commit) != expected_h12_scope()
        or _commit_parents(root, contract.p12_cert_commit)
        != (contract.h12_cert_commit,)
        or _commit_scope(root, contract.p12_cert_commit) != expected_p12_scope()
    ):
        raise _error("Historical H12/P12 topology or scope drifted")
    h12_records: list[dict[str, Any]] = []
    for spec in contract.h12_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h12_cert_commit,
            spec=spec,
            context="Historical H-CERT12 component",
        )
        h12_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H12_AUTHORITY_PATH, commit=contract.p12_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H12_AUTHORITY_MANIFEST_PATH, commit=contract.p12_cert_commit
    )
    if (
        len(authority_bytes) != H12_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H12_AUTHORITY_SHA256
        or len(manifest_bytes) != H12_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H12_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H12_AUTHORITY_VERSION
        or authority.get("p11_failure") != expected_p11_failure_record()
    ):
        raise _error("Historical P-CERT12 canonical byte identity drifted")
    authority_record = {
        "path": H12_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": H12_AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": contract.h1_cert_commit,
        "p1_cert_commit": contract.p1_cert_commit,
        "h2_cert_commit": contract.h2_cert_commit,
        "p2_cert_commit": contract.p2_cert_commit,
        "h3_cert_commit": contract.h3_cert_commit,
        "p3_cert_commit": contract.p3_cert_commit,
        "h4_cert_commit": contract.h4_cert_commit,
        "p4_cert_commit": contract.p4_cert_commit,
        "h5_cert_commit": contract.h5_cert_commit,
        "p5_cert_commit": contract.p5_cert_commit,
        "h6_cert_commit": contract.h6_cert_commit,
        "p6_cert_commit": contract.p6_cert_commit,
        "h7_cert_commit": contract.h7_cert_commit,
        "p7_cert_commit": contract.p7_cert_commit,
        "h8_cert_commit": contract.h8_cert_commit,
        "p8_cert_commit": contract.p8_cert_commit,
        "h9_cert_commit": contract.h9_cert_commit,
        "p9_cert_commit": contract.p9_cert_commit,
        "h10_cert_commit": contract.h10_cert_commit,
        "p10_cert_commit": contract.p10_cert_commit,
        "h11_cert_commit": contract.h11_cert_commit,
        "p11_cert_commit": contract.p11_cert_commit,
        "h12_cert_commit": contract.h12_cert_commit,
        "p12_cert_commit": None,
        "h_cert_commit": contract.h12_cert_commit,
        "p_cert_commit": None,
        "supersedes_p11": True,
        "supersedes_p10": True,
        "supersedes_p9": True,
        "supersedes_p8": True,
        "supersedes_p7": True,
        "supersedes_p6": True,
        "supersedes_p5": True,
        "supersedes_p4": True,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [
            H12_AUTHORITY_PATH.as_posix(),
            H12_AUTHORITY_MANIFEST_PATH.as_posix(),
        ],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Historical P-CERT12 companion identity drifted")
    p12_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p12_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p12_cert_commit,
            spec=spec,
            context="Historical P-CERT12 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT12 physical/Git bytes drifted")
        p12_records.append(record)
    return h12_records, p12_records


def _historical_through_p12_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], ...]:
    predecessor = _historical_through_p11_records(contract, root=root)
    h12_records, p12_records = _historical_h12_p12_records(contract, root=root)
    return (*predecessor, h12_records, p12_records)


def _historical_h14_p14_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT14/P-CERT14."""

    if (
        _commit_parents(root, contract.h14_cert_commit)
        != (contract.p12_cert_commit,)
        or _commit_scope(root, contract.h14_cert_commit) != expected_h14_scope()
        or _commit_parents(root, contract.p14_cert_commit)
        != (contract.h14_cert_commit,)
        or _commit_scope(root, contract.p14_cert_commit) != expected_p14_scope()
    ):
        raise _error("Historical H14/P14 topology or scope drifted")
    h14_records: list[dict[str, Any]] = []
    for spec in contract.h14_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h14_cert_commit,
            spec=spec,
            context="Historical H-CERT14 component",
        )
        h14_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H14_AUTHORITY_PATH, commit=contract.p14_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H14_AUTHORITY_MANIFEST_PATH, commit=contract.p14_cert_commit
    )
    topology = authority.get("topology")
    if (
        len(authority_bytes) != H14_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H14_AUTHORITY_SHA256
        or len(manifest_bytes) != H14_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H14_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H14_AUTHORITY_VERSION
        or authority.get("gate") != "P-CERT"
        or authority.get("status") != "locked_unpublished"
        or authority.get("h13_failure") != expected_h13_failure_record()
        or not isinstance(topology, Mapping)
        or topology.get("h13_cert_commit") is not None
        or topology.get("p13_cert_commit") is not None
        or topology.get("h14_cert_commit") != contract.h14_cert_commit
        or topology.get("p14_cert_commit") is not None
        or manifest.get("manifest_version") != H14_AUTHORITY_MANIFEST_VERSION
        or manifest.get("h13_cert_commit") is not None
        or manifest.get("p13_cert_commit") is not None
        or manifest.get("h14_cert_commit") != contract.h14_cert_commit
        or manifest.get("p14_cert_commit") is not None
    ):
        raise _error("Historical P-CERT14 canonical byte identity drifted")
    p14_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p14_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p14_cert_commit,
            spec=spec,
            context="Historical P-CERT14 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT14 physical/Git bytes drifted")
        p14_records.append(record)
    return h14_records, p14_records


def _historical_through_p14_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], ...]:
    predecessor = _historical_through_p12_records(contract, root=root)
    h14_records, p14_records = _historical_h14_p14_records(contract, root=root)
    return (*predecessor, h14_records, p14_records)


def _historical_h15_p15_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT15/P-CERT15."""

    if (
        _commit_parents(root, contract.h15_cert_commit)
        != (contract.p14_cert_commit,)
        or _commit_scope(root, contract.h15_cert_commit) != expected_h15_scope()
        or _commit_parents(root, contract.p15_cert_commit)
        != (contract.h15_cert_commit,)
        or _commit_scope(root, contract.p15_cert_commit) != expected_p15_scope()
    ):
        raise _error("Historical H15/P15 topology or scope drifted")
    h15_records: list[dict[str, Any]] = []
    for spec in contract.h15_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h15_cert_commit,
            spec=spec,
            context="Historical H-CERT15 component",
        )
        h15_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H15_AUTHORITY_PATH, commit=contract.p15_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H15_AUTHORITY_MANIFEST_PATH, commit=contract.p15_cert_commit
    )
    topology = authority.get("topology")
    if (
        len(authority_bytes) != H15_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H15_AUTHORITY_SHA256
        or len(manifest_bytes) != H15_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H15_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H15_AUTHORITY_VERSION
        or authority.get("gate") != "P-CERT"
        or authority.get("status") != "locked_unpublished"
        or authority.get("p14_failure") != expected_p14_failure_record()
        or not isinstance(topology, Mapping)
        or topology.get("h13_cert_commit") is not None
        or topology.get("p13_cert_commit") is not None
        or topology.get("h14_cert_commit") != contract.h14_cert_commit
        or topology.get("p14_cert_commit") != contract.p14_cert_commit
        or topology.get("h15_cert_commit") != contract.h15_cert_commit
        or topology.get("p15_cert_commit") is not None
        or manifest.get("manifest_version") != H15_AUTHORITY_MANIFEST_VERSION
        or manifest.get("h13_cert_commit") is not None
        or manifest.get("p13_cert_commit") is not None
        or manifest.get("h14_cert_commit") != contract.h14_cert_commit
        or manifest.get("p14_cert_commit") != contract.p14_cert_commit
        or manifest.get("h15_cert_commit") != contract.h15_cert_commit
        or manifest.get("p15_cert_commit") is not None
    ):
        raise _error("Historical P-CERT15 canonical byte identity drifted")
    p15_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p15_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p15_cert_commit,
            spec=spec,
            context="Historical P-CERT15 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT15 physical/Git bytes drifted")
        p15_records.append(record)
    return h15_records, p15_records


def _historical_through_p15_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], ...]:
    predecessor = _historical_through_p14_records(contract, root=root)
    h15_records, p15_records = _historical_h15_p15_records(contract, root=root)
    return (*predecessor, h15_records, p15_records)


def _historical_h16_p16_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT16/P-CERT16."""

    if (
        _commit_parents(root, contract.h16_cert_commit)
        != (contract.p15_cert_commit,)
        or _commit_scope(root, contract.h16_cert_commit) != expected_h16_scope()
        or _commit_parents(root, contract.p16_cert_commit)
        != (contract.h16_cert_commit,)
        or _commit_scope(root, contract.p16_cert_commit) != expected_p16_scope()
    ):
        raise _error("Historical H16/P16 topology or scope drifted")
    h16_records: list[dict[str, Any]] = []
    for spec in contract.h16_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h16_cert_commit,
            spec=spec,
            context="Historical H-CERT16 component",
        )
        h16_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H16_AUTHORITY_PATH, commit=contract.p16_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H16_AUTHORITY_MANIFEST_PATH, commit=contract.p16_cert_commit
    )
    topology = authority.get("topology")
    if (
        len(authority_bytes) != H16_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H16_AUTHORITY_SHA256
        or len(manifest_bytes) != H16_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H16_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H16_AUTHORITY_VERSION
        or authority.get("gate") != "P-CERT"
        or authority.get("status") != "locked_unpublished"
        or authority.get("p15_failure") != expected_p15_failure_record()
        or not isinstance(topology, Mapping)
        or topology.get("h13_cert_commit") is not None
        or topology.get("p13_cert_commit") is not None
        or topology.get("h15_cert_commit") != contract.h15_cert_commit
        or topology.get("p15_cert_commit") != contract.p15_cert_commit
        or topology.get("h16_cert_commit") != contract.h16_cert_commit
        or topology.get("p16_cert_commit") is not None
        or manifest.get("manifest_version") != H16_AUTHORITY_MANIFEST_VERSION
        or manifest.get("h13_cert_commit") is not None
        or manifest.get("p13_cert_commit") is not None
        or manifest.get("h15_cert_commit") != contract.h15_cert_commit
        or manifest.get("p15_cert_commit") != contract.p15_cert_commit
        or manifest.get("h16_cert_commit") != contract.h16_cert_commit
        or manifest.get("p16_cert_commit") is not None
    ):
        raise _error("Historical P-CERT16 canonical byte identity drifted")
    p16_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p16_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p16_cert_commit,
            spec=spec,
            context="Historical P-CERT16 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT16 physical/Git bytes drifted")
        p16_records.append(record)
    return h16_records, p16_records


def _historical_through_p16_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], ...]:
    predecessor = _historical_through_p15_records(contract, root=root)
    h16_records, p16_records = _historical_h16_p16_records(contract, root=root)
    return (*predecessor, h16_records, p16_records)


def _historical_h17_p17_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconstruct and byte-bind immutable H-CERT17/P-CERT17."""

    if (
        _commit_parents(root, contract.h17_cert_commit)
        != (contract.p16_cert_commit,)
        or _commit_scope(root, contract.h17_cert_commit) != expected_h17_scope()
        or _commit_parents(root, contract.p17_cert_commit)
        != (contract.h17_cert_commit,)
        or _commit_scope(root, contract.p17_cert_commit) != expected_p17_scope()
    ):
        raise _error("Historical H17/P17 topology or scope drifted")
    h17_records: list[dict[str, Any]] = []
    for spec in contract.h17_scope:
        record, _payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.h17_cert_commit,
            spec=spec,
            context="Historical H-CERT17 component",
        )
        h17_records.append(
            {**record, "filesystem_mode": int(spec.git_mode[-3:], 8)}
        )

    authority, authority_bytes = _decode_canonical_public_json(
        root, H17_AUTHORITY_PATH, commit=contract.p17_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, H17_AUTHORITY_MANIFEST_PATH, commit=contract.p17_cert_commit
    )
    topology = authority.get("topology")
    if (
        len(authority_bytes) != H17_AUTHORITY_BYTES
        or sha256_bytes(authority_bytes) != H17_AUTHORITY_SHA256
        or len(manifest_bytes) != H17_AUTHORITY_MANIFEST_BYTES
        or sha256_bytes(manifest_bytes) != H17_AUTHORITY_MANIFEST_SHA256
        or authority.get("authority_version") != H17_AUTHORITY_VERSION
        or authority.get("gate") != "P-CERT"
        or authority.get("status") != "locked_unpublished"
        or authority.get("p16_failure") != expected_p16_failure_record()
        or not isinstance(topology, Mapping)
        or topology.get("h13_cert_commit") is not None
        or topology.get("p13_cert_commit") is not None
        or topology.get("h16_cert_commit") != contract.h16_cert_commit
        or topology.get("p16_cert_commit") != contract.p16_cert_commit
        or topology.get("h17_cert_commit") != contract.h17_cert_commit
        or topology.get("p17_cert_commit") is not None
        or manifest.get("manifest_version") != H17_AUTHORITY_MANIFEST_VERSION
        or manifest.get("h13_cert_commit") is not None
        or manifest.get("p13_cert_commit") is not None
        or manifest.get("h16_cert_commit") != contract.h16_cert_commit
        or manifest.get("p16_cert_commit") != contract.p16_cert_commit
        or manifest.get("h17_cert_commit") != contract.h17_cert_commit
        or manifest.get("p17_cert_commit") is not None
    ):
        raise _error("Historical P-CERT17 canonical byte identity drifted")
    p17_records: list[dict[str, Any]] = []
    for spec, payload in zip(
        contract.p17_scope, (authority_bytes, manifest_bytes), strict=True
    ):
        record, git_payload = _git_publication_file_record_and_payload(
            root,
            commit=contract.p17_cert_commit,
            spec=spec,
            context="Historical P-CERT17 component",
        )
        if git_payload != payload:
            raise _error("Historical P-CERT17 physical/Git bytes drifted")
        p17_records.append(record)
    return h17_records, p17_records


def _historical_through_p17_records(
    contract: FinalCertificationContract,
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], ...]:
    predecessor = _historical_through_p16_records(contract, root=root)
    h17_records, p17_records = _historical_h17_p17_records(contract, root=root)
    return (*predecessor, h17_records, p17_records)


def _expected_effective_authority(
    contract: FinalCertificationContract,
    *,
    root: Path,
    h_cert_commit: str,
) -> dict[str, Any]:
    components = collect_h_component_records(
        contract, h_cert_commit=h_cert_commit, root=root
    )
    (
        h1_records,
        p1_records,
        h2_records,
        p2_records,
        h3_records,
        p3_records,
        h4_records,
        p4_records,
        h5_records,
        p5_records,
        h6_records,
        p6_records,
        h7_records,
        p7_records,
        h8_records,
        p8_records,
        h9_records,
        p9_records,
        h10_records,
        p10_records,
        h11_records,
        p11_records,
        h12_records,
        p12_records,
        h14_records,
        p14_records,
        h15_records,
        p15_records,
        h16_records,
        p16_records,
        h17_records,
        p17_records,
    ) = _historical_through_p17_records(contract, root=root)
    anchors = collect_anchor_input_records(contract, root=root)
    pointers = collect_dvc_pointer_records(contract, root=root)
    suite = test_suite_record(contract)
    outputs = list(contract.output_paths)
    return {
        "authority_version": AUTHORITY_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "topology": {
            "closure_source_commit": contract.closure_source_commit,
            "r_syn_commit": contract.r_syn_commit,
            "editorial_commit": contract.editorial_commit,
            "h1_cert_commit": contract.h1_cert_commit,
            "p1_cert_commit": contract.p1_cert_commit,
            "h2_cert_commit": contract.h2_cert_commit,
            "p2_cert_commit": contract.p2_cert_commit,
            "h3_cert_commit": contract.h3_cert_commit,
            "p3_cert_commit": contract.p3_cert_commit,
            "h4_cert_commit": contract.h4_cert_commit,
            "p4_cert_commit": contract.p4_cert_commit,
            "h5_cert_commit": contract.h5_cert_commit,
            "p5_cert_commit": contract.p5_cert_commit,
            "h6_cert_commit": contract.h6_cert_commit,
            "p6_cert_commit": contract.p6_cert_commit,
            "h7_cert_commit": contract.h7_cert_commit,
            "p7_cert_commit": contract.p7_cert_commit,
            "h8_cert_commit": contract.h8_cert_commit,
            "p8_cert_commit": contract.p8_cert_commit,
            "h9_cert_commit": contract.h9_cert_commit,
            "p9_cert_commit": contract.p9_cert_commit,
            "h10_cert_commit": contract.h10_cert_commit,
            "p10_cert_commit": contract.p10_cert_commit,
            "h11_cert_commit": contract.h11_cert_commit,
            "p11_cert_commit": contract.p11_cert_commit,
            "h12_cert_commit": contract.h12_cert_commit,
            "p12_cert_commit": contract.p12_cert_commit,
            "h13_cert_commit": None,
            "p13_cert_commit": None,
            "h14_cert_commit": contract.h14_cert_commit,
            "p14_cert_commit": contract.p14_cert_commit,
            "h15_cert_commit": contract.h15_cert_commit,
            "p15_cert_commit": contract.p15_cert_commit,
            "h16_cert_commit": contract.h16_cert_commit,
            "p16_cert_commit": contract.p16_cert_commit,
            "h17_cert_commit": contract.h17_cert_commit,
            "p17_cert_commit": contract.p17_cert_commit,
            "h18_cert_commit": h_cert_commit,
            "p18_cert_commit": None,
            "h_cert_commit": h_cert_commit,
            "p_cert_commit": None,
            "supersedes_unpublished_H_CERT13_candidate": True,
            "supersedes_P_CERT14": True,
            "supersedes_P_CERT15": True,
            "supersedes_P_CERT16": True,
            "supersedes_P_CERT17": True,
            "r_cert_executable_tree_must_equal_p_cert": True,
        },
        "p1_failure": {
            "status": "superseded_failed",
            "failure_stage": "after_git_clone_namespace_validation",
            "dvc_pull_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
        },
        "p2_failure": expected_p2_failure_record(),
        "p3_failure": expected_p3_failure_record(),
        "p4_failure": expected_p4_failure_record(),
        "p5_failure": expected_p5_failure_record(),
        "p6_failure": expected_p6_failure_record(),
        "p7_failure": expected_p7_failure_record(),
        "p8_failure": expected_p8_failure_record(),
        "p9_failure": expected_p9_failure_record(),
        "p10_failure": expected_p10_failure_record(),
        "p11_failure": expected_p11_failure_record(),
        "p12_failure": expected_p12_failure_record(),
        "h13_failure": expected_h13_failure_record(),
        "p14_failure": expected_p14_failure_record(),
        "p15_failure": expected_p15_failure_record(),
        "p16_failure": expected_p16_failure_record(),
        "p17_failure": expected_p17_failure_record(),
        "h1_scope": expected_h1_scope(),
        "h1_component_records": h1_records,
        "h1_component_records_digest": digest_records(h1_records),
        "p1_scope": expected_p1_scope(),
        "p1_component_records": p1_records,
        "p1_component_records_digest": digest_records(p1_records),
        "h2_scope": expected_h2_scope(),
        "h2_component_records": h2_records,
        "h2_component_records_digest": digest_records(h2_records),
        "p2_scope": expected_p2_scope(),
        "p2_component_records": p2_records,
        "p2_component_records_digest": digest_records(p2_records),
        "h3_scope": expected_h3_scope(),
        "h3_component_records": h3_records,
        "h3_component_records_digest": digest_records(h3_records),
        "p3_scope": expected_p3_scope(),
        "p3_component_records": p3_records,
        "p3_component_records_digest": digest_records(p3_records),
        "h4_scope": expected_h4_scope(),
        "h4_component_records": h4_records,
        "h4_component_records_digest": digest_records(h4_records),
        "p4_scope": expected_p4_scope(),
        "p4_component_records": p4_records,
        "p4_component_records_digest": digest_records(p4_records),
        "h5_scope": expected_h5_scope(),
        "h5_component_records": h5_records,
        "h5_component_records_digest": digest_records(h5_records),
        "p5_scope": expected_p5_scope(),
        "p5_component_records": p5_records,
        "p5_component_records_digest": digest_records(p5_records),
        "h6_scope": expected_h6_scope(),
        "h6_component_records": h6_records,
        "h6_component_records_digest": digest_records(h6_records),
        "p6_scope": expected_p6_scope(),
        "p6_component_records": p6_records,
        "p6_component_records_digest": digest_records(p6_records),
        "h7_scope": expected_h7_scope(),
        "h7_component_records": h7_records,
        "h7_component_records_digest": digest_records(h7_records),
        "p7_scope": expected_p7_scope(),
        "p7_component_records": p7_records,
        "p7_component_records_digest": digest_records(p7_records),
        "h8_scope": expected_h8_scope(),
        "h8_component_records": h8_records,
        "h8_component_records_digest": digest_records(h8_records),
        "p8_scope": expected_p8_scope(),
        "p8_component_records": p8_records,
        "p8_component_records_digest": digest_records(p8_records),
        "h9_scope": expected_h9_scope(),
        "h9_component_records": h9_records,
        "h9_component_records_digest": digest_records(h9_records),
        "p9_scope": expected_p9_scope(),
        "p9_component_records": p9_records,
        "p9_component_records_digest": digest_records(p9_records),
        "h10_scope": expected_h10_scope(),
        "h10_component_records": h10_records,
        "h10_component_records_digest": digest_records(h10_records),
        "p10_scope": expected_p10_scope(),
        "p10_component_records": p10_records,
        "p10_component_records_digest": digest_records(p10_records),
        "h11_scope": expected_h11_scope(),
        "h11_component_records": h11_records,
        "h11_component_records_digest": digest_records(h11_records),
        "p11_scope": expected_p11_scope(),
        "p11_component_records": p11_records,
        "p11_component_records_digest": digest_records(p11_records),
        "h12_scope": expected_h12_scope(),
        "h12_component_records": h12_records,
        "h12_component_records_digest": digest_records(h12_records),
        "p12_scope": expected_p12_scope(),
        "p12_component_records": p12_records,
        "p12_component_records_digest": digest_records(p12_records),
        "h13_scope": expected_h13_scope(),
        "p13_scope": expected_p13_scope(),
        "r13_scope": expected_r_scope(),
        "h14_scope": expected_h14_scope(),
        "h14_component_records": h14_records,
        "h14_component_records_digest": digest_records(h14_records),
        "p14_scope": expected_p14_scope(),
        "p14_component_records": p14_records,
        "p14_component_records_digest": digest_records(p14_records),
        "r14_scope": expected_r_scope(),
        "h15_scope": expected_h15_scope(),
        "h15_component_records": h15_records,
        "h15_component_records_digest": digest_records(h15_records),
        "p15_scope": expected_p15_scope(),
        "p15_component_records": p15_records,
        "p15_component_records_digest": digest_records(p15_records),
        "r15_scope": expected_r15_scope(),
        "h16_scope": expected_h16_scope(),
        "h16_component_records": h16_records,
        "h16_component_records_digest": digest_records(h16_records),
        "p16_scope": expected_p16_scope(),
        "p16_component_records": p16_records,
        "p16_component_records_digest": digest_records(p16_records),
        "r16_scope": expected_r16_scope(),
        "h17_scope": expected_h17_scope(),
        "h17_component_records": h17_records,
        "h17_component_records_digest": digest_records(h17_records),
        "p17_scope": expected_p17_scope(),
        "p17_component_records": p17_records,
        "p17_component_records_digest": digest_records(p17_records),
        "r17_scope": expected_r17_scope(),
        "h_scope": expected_h_scope(),
        "h_component_records": components,
        "h_component_records_digest": digest_records(components),
        "h18_scope": expected_h_scope(),
        "h18_component_records": components,
        "h18_component_records_digest": digest_records(components),
        "p_scope": expected_p_scope(),
        "p18_scope": expected_p_scope(),
        "r_scope": expected_r_scope(),
        "r18_scope": expected_r_scope(),
        "anchor_input_records": anchors,
        "anchor_input_records_digest": digest_records(anchors),
        "dvc_pointer_records": pointers,
        "dvc_pointer_records_digest": digest_records(pointers),
        "dvc_status_policy": expected_dvc_status_policy(contract),
        "main_dvc_static_boundary": main_dvc_static_boundary_record(
            contract,
            anchor_records=anchors,
            pointer_records=pointers,
        ),
        "test_suite": suite,
        "test_suite_digest": sha256_bytes(canonical_json_bytes(suite)),
        "ordered_r_cert_output_paths": outputs,
        "r_cert_output_paths_digest": digest_strings(outputs),
        "isolation": dict(_expected_isolation()),
        "failure_diagnostics": dict(FAILURE_DIAGNOSTICS_POLICY),
        "authorizations": dict(AUTHORIZATION_POLICY),
        "prohibitions": dict(PROHIBITIONS),
    }


def load_effective_authority(
    contract: FinalCertificationContract | None = None,
    *,
    root: Path = PROJECT_ROOT,
    verify_remote: bool = True,
    require_clean: bool = True,
) -> dict[str, Any]:
    """Load and independently reconstruct one published effective P-CERT18.

    The stored authority deliberately has ``p_cert_commit=null`` because it is
    generated before its publication commit exists.  Effectiveness is derived
    here from the observed exact P commit, direct H parent, exact scopes,
    canonical bytes, aligned refs and (by default) live remote.
    """

    active_contract = contract or load_contract(root=root)
    if active_contract.test_suite.status != "locked":
        raise _error("Effective P-CERT requires a locked public-test suite")
    if require_clean:
        _require_clean_git_state(root)
    p_cert_commit = _one_commit(root, "HEAD")
    parents = _commit_parents(root, p_cert_commit)
    if len(parents) != 1:
        raise _error("P-CERT18 must have exactly one H-CERT18 parent")
    h_cert_commit = parents[0]
    if (
        _commit_parents(root, h_cert_commit) != (active_contract.p17_cert_commit,)
        or _commit_scope(root, h_cert_commit) != expected_h_scope()
        or _commit_scope(root, p_cert_commit) != expected_p_scope()
    ):
        raise _error("Effective P-CERT18 H18/P18 topology or scope drifted")
    _historical_through_p17_records(active_contract, root=root)
    ancestor = subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            active_contract.closure_source_commit,
            p_cert_commit,
        ],
        cwd=root,
        check=False,
        capture_output=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if ancestor.returncode != 0 or ancestor.stdout or ancestor.stderr:
        raise _error("Closure source is not a clean ancestor of effective P-CERT")
    refs = _require_effective_refs(root, p_cert_commit, verify_remote=verify_remote)
    authority, authority_bytes = _decode_canonical_public_json(
        root, AUTHORITY_PATH, commit=p_cert_commit
    )
    manifest, manifest_bytes = _decode_canonical_public_json(
        root, AUTHORITY_MANIFEST_PATH, commit=p_cert_commit
    )
    expected_authority = _expected_effective_authority(
        active_contract, root=root, h_cert_commit=h_cert_commit
    )
    if authority != expected_authority or authority_bytes != canonical_json_bytes(
        expected_authority
    ):
        raise _error("Published P-CERT authority is not independently reproducible")
    authority_record = {
        "path": AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": sha256_bytes(authority_bytes),
    }
    expected_manifest = {
        "manifest_version": AUTHORITY_MANIFEST_VERSION,
        "gate": "P-CERT",
        "status": "locked_unpublished",
        "h1_cert_commit": active_contract.h1_cert_commit,
        "p1_cert_commit": active_contract.p1_cert_commit,
        "h2_cert_commit": active_contract.h2_cert_commit,
        "p2_cert_commit": active_contract.p2_cert_commit,
        "h3_cert_commit": active_contract.h3_cert_commit,
        "p3_cert_commit": active_contract.p3_cert_commit,
        "h4_cert_commit": active_contract.h4_cert_commit,
        "p4_cert_commit": active_contract.p4_cert_commit,
        "h5_cert_commit": active_contract.h5_cert_commit,
        "p5_cert_commit": active_contract.p5_cert_commit,
        "h6_cert_commit": active_contract.h6_cert_commit,
        "p6_cert_commit": active_contract.p6_cert_commit,
        "h7_cert_commit": active_contract.h7_cert_commit,
        "p7_cert_commit": active_contract.p7_cert_commit,
        "h8_cert_commit": active_contract.h8_cert_commit,
        "p8_cert_commit": active_contract.p8_cert_commit,
        "h9_cert_commit": active_contract.h9_cert_commit,
        "p9_cert_commit": active_contract.p9_cert_commit,
        "h10_cert_commit": active_contract.h10_cert_commit,
        "p10_cert_commit": active_contract.p10_cert_commit,
        "h11_cert_commit": active_contract.h11_cert_commit,
        "p11_cert_commit": active_contract.p11_cert_commit,
        "h12_cert_commit": active_contract.h12_cert_commit,
        "p12_cert_commit": active_contract.p12_cert_commit,
        "h13_cert_commit": None,
        "p13_cert_commit": None,
        "h14_cert_commit": active_contract.h14_cert_commit,
        "p14_cert_commit": active_contract.p14_cert_commit,
        "h15_cert_commit": active_contract.h15_cert_commit,
        "p15_cert_commit": active_contract.p15_cert_commit,
        "h16_cert_commit": active_contract.h16_cert_commit,
        "p16_cert_commit": active_contract.p16_cert_commit,
        "h17_cert_commit": active_contract.h17_cert_commit,
        "p17_cert_commit": active_contract.p17_cert_commit,
        "h18_cert_commit": h_cert_commit,
        "p18_cert_commit": None,
        "h_cert_commit": h_cert_commit,
        "p_cert_commit": None,
        "supersedes_unpublished_h13_candidate": True,
        "supersedes_p14": True,
        "supersedes_p15": True,
        "supersedes_p16": True,
        "supersedes_p17": True,
        "supersedes_p12": True,
        "supersedes_p11": True,
        "supersedes_p10": True,
        "supersedes_p9": True,
        "supersedes_p8": True,
        "supersedes_p7": True,
        "supersedes_p6": True,
        "supersedes_p5": True,
        "supersedes_p4": True,
        "supersedes_p3": True,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [AUTHORITY_PATH.as_posix(), AUTHORITY_MANIFEST_PATH.as_posix()],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(AUTHORIZATION_POLICY),
    }
    if manifest != expected_manifest or manifest_bytes != canonical_json_bytes(
        expected_manifest
    ):
        raise _error("Published P-CERT companion is not independently reproducible")
    return {
        "status": "effective",
        "gate": "P-CERT",
        "p_cert_commit": p_cert_commit,
        "h_cert_commit": h_cert_commit,
        "p18_cert_commit": p_cert_commit,
        "h18_cert_commit": h_cert_commit,
        "p17_cert_commit": active_contract.p17_cert_commit,
        "h17_cert_commit": active_contract.h17_cert_commit,
        "p16_cert_commit": active_contract.p16_cert_commit,
        "h16_cert_commit": active_contract.h16_cert_commit,
        "p15_cert_commit": active_contract.p15_cert_commit,
        "h15_cert_commit": active_contract.h15_cert_commit,
        "p14_cert_commit": active_contract.p14_cert_commit,
        "h14_cert_commit": active_contract.h14_cert_commit,
        "p13_cert_commit": None,
        "h13_cert_commit": None,
        "p12_cert_commit": active_contract.p12_cert_commit,
        "h12_cert_commit": active_contract.h12_cert_commit,
        "p11_cert_commit": active_contract.p11_cert_commit,
        "h11_cert_commit": active_contract.h11_cert_commit,
        "p10_cert_commit": active_contract.p10_cert_commit,
        "h10_cert_commit": active_contract.h10_cert_commit,
        "p9_cert_commit": active_contract.p9_cert_commit,
        "h9_cert_commit": active_contract.h9_cert_commit,
        "p8_cert_commit": active_contract.p8_cert_commit,
        "h8_cert_commit": active_contract.h8_cert_commit,
        "p7_cert_commit": active_contract.p7_cert_commit,
        "h7_cert_commit": active_contract.h7_cert_commit,
        "p6_cert_commit": active_contract.p6_cert_commit,
        "h6_cert_commit": active_contract.h6_cert_commit,
        "p5_cert_commit": active_contract.p5_cert_commit,
        "h5_cert_commit": active_contract.h5_cert_commit,
        "p4_cert_commit": active_contract.p4_cert_commit,
        "h4_cert_commit": active_contract.h4_cert_commit,
        "p3_cert_commit": active_contract.p3_cert_commit,
        "h3_cert_commit": active_contract.h3_cert_commit,
        "p2_cert_commit": active_contract.p2_cert_commit,
        "h2_cert_commit": active_contract.h2_cert_commit,
        "p1_cert_commit": active_contract.p1_cert_commit,
        "h1_cert_commit": active_contract.h1_cert_commit,
        "repository": refs,
        "authority": authority,
        "authority_bytes": authority_bytes,
        "authority_sha256": sha256_bytes(authority_bytes),
        "manifest": manifest,
        "manifest_bytes": manifest_bytes,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "dvc_status_policy": expected_dvc_status_policy(active_contract),
    }


def validate_local_dvc_remote_configuration(
    *, root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Validate local DVC remote metadata without reading or hashing its contents.

    The returned projection intentionally omits the path, bytes, remote name,
    URL and credentials.  It is operational preflight state, never an
    authority input or public manifest record.
    """

    anchored = _open_anchored_regular_file(
        root,
        LOCAL_DVC_CONFIG_PATH.as_posix(),
        expected_modes=frozenset({0o600, 0o644}),
        context="Ignored local DVC remote configuration",
    )
    try:
        _revalidate_anchored_file(anchored)
        ignored = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                "--",
                LOCAL_DVC_CONFIG_PATH.as_posix(),
            ],
            cwd=root,
            check=False,
            capture_output=True,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        _revalidate_anchored_file(anchored)
        if ignored.returncode != 0 or ignored.stdout or ignored.stderr:
            raise _error("Local DVC remote configuration is not cleanly Git-ignored")
        return {
            "present": True,
            "regular_file": True,
            "single_link": True,
            "filesystem_mode": format(
                stat.S_IMODE(anchored.metadata.st_mode),
                "04o",
            ),
            "git_ignored": True,
            "content_opened": False,
            "content_or_path_serialized": False,
        }
    finally:
        _close_anchored_file(anchored)
