#!/usr/bin/env python
"""Strict, outcome-free contract helpers for Closure V1 Phase 4 synthesis.

The module accepts only the explicit structured-input allowlist declared in
``configs/closure_v1/phase4_synthesis.yaml``.  It never discovers inputs,
follows paths embedded in manifests, or opens raw targets/outcomes.  The
helpers are shared by the P-SYN authority locker and the R-SYN builder.
"""

from __future__ import annotations

import csv
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
DEFAULT_CONTRACT_PATH = Path("configs/closure_v1/phase4_synthesis.yaml")
DEFAULT_SCHEMA_PATH = Path("configs/closure_v1/phase4_synthesis.schema.json")
AUTHORITY_PATH = Path("configs/closure_v1/phase4_synthesis_authority.json")
AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/phase4_synthesis_authority_manifest.json"
)
SYNTHESIS_ROOT = Path("reports/closure_v1/11_synthesis")
HASH_CHUNK_SIZE = 1024 * 1024
GIT_OID_RE = re.compile(r"^[0-9a-f]{40,64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
NULL_TOKENS = frozenset({"na", "n/a", "nan", "none", "null"})
FINAL_CLOSURE_COLUMNS = (
    "hypothesis_id",
    "hypothesis_text",
    "decisive_experiments",
    "estimand",
    "population",
    "model_or_pair",
    "availability_state",
    "attempted_denominator",
    "successful_denominator",
    "metric",
    "estimate",
    "uncertainty",
    "multiplicity_family",
    "verdict",
    "limitation_code",
    "evidence_paths",
    "authority_commit",
)
CLAIM_EVIDENCE_COLUMNS = (
    "claim_id",
    "chapter",
    "section",
    "claim_text",
    "claim_status",
    "artifact_path",
    "row_filter_or_record",
    "metric",
    "value_or_state",
    "denominator",
    "authority_commit",
    "limitation",
    "allowed_wording",
    "forbidden_wording",
)
OUTPUT_PATHS = (
    "reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv",
    "reports/closure_v1/11_synthesis/THESIS_CLAIM_EVIDENCE_MATRIX.csv",
    "reports/closure_v1/11_synthesis/FINAL_CLOSURE_REPORT.md",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T01_model_experiment_availability.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T02_intent_to_predict_funnel.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T03_dual_benchmark.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T04_descriptive_deltas.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T05_site_transfer.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T06_threshold_sensitivity.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T07_trophic_performance.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T08_multiplicity_ledger.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T09_anfis_ablation.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T10_uncertainty.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T11_e6_e9_unavailability.csv",
    "reports/closure_v1/11_synthesis/THESIS_TABLES/T12_software_evidence.csv",
    "reports/closure_v1/11_synthesis/THESIS_FIGURES/F01_intent_to_predict_funnel.svg",
    "reports/closure_v1/11_synthesis/THESIS_FIGURES/F02_benchmark_metrics.svg",
    "reports/closure_v1/11_synthesis/THESIS_FIGURES/F03_descriptive_deltas.svg",
    "reports/closure_v1/11_synthesis/THESIS_FIGURES/F04_threshold_sensitivity.svg",
    "reports/closure_v1/11_synthesis/THESIS_FIGURES/F05_trophic_heatmap.svg",
    "reports/closure_v1/11_synthesis/THESIS_FIGURES/F06_uncertainty_coverage.svg",
    "reports/closure_v1/11_synthesis/THESIS_FIGURES/F07_hypothesis_verdicts.svg",
    "reports/closure_v1/11_synthesis/THESIS_FIGURES/F08_provenance.svg",
    "reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json",
)


class SynthesisContractError(RuntimeError):
    """Raised when the H-SYN/P-SYN/R-SYN contract cannot be proven."""


@dataclass(frozen=True)
class InputSpec:
    path: str
    role: str
    format: str
    allow_empty: bool = False


@dataclass(frozen=True)
class SynthesisContract:
    path: Path
    raw: Mapping[str, Any]
    closure_source_commit: str
    allowed_inputs: tuple[InputSpec, ...]
    output_paths: tuple[str, ...]
    final_closure_columns: tuple[str, ...]
    claim_evidence_columns: tuple[str, ...]
    availability_states: tuple[str, ...]
    non_estimable_states: tuple[str, ...]
    required_unavailable_models: tuple[str, ...]
    required_hypotheses: tuple[str, ...]
    holm_universes: Mapping[str, int]
    final_closure_row_count: int
    claim_evidence_row_count: int
    table_row_counts: Mapping[str, int]
    artifact_captions: Mapping[str, str]

    @property
    def allowed_input_paths(self) -> tuple[str, ...]:
        return tuple(spec.path for spec in self.allowed_inputs)


def _error(message: str) -> SynthesisContractError:
    return SynthesisContractError(message)


def canonical_json_bytes(payload: Any) -> bytes:
    """Return canonical UTF-8 JSON with exactly one trailing LF."""

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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_strings(values: Sequence[str]) -> str:
    return sha256_bytes(canonical_json_bytes(list(values)))


def digest_records(records: Sequence[Mapping[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(list(records)))


def _require_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error(f"{context} must be a mapping")
    return cast(Mapping[str, Any], value)


def _require_list(value: Any, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise _error(f"{context} must be a list")
    return value


def _require_text(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise _error(f"{context} must be non-empty trimmed text")
    return value


def _require_string_list(value: Any, *, context: str) -> tuple[str, ...]:
    items = tuple(
        _require_text(item, context=f"{context}[{index}]")
        for index, item in enumerate(_require_list(value, context=context))
    )
    if len(set(items)) != len(items):
        raise _error(f"{context} contains duplicates")
    return items


def _safe_relative_path(path_text: str, *, context: str) -> PurePosixPath:
    if "\\" in path_text or "\x00" in path_text:
        raise _error(f"{context} is not a canonical POSIX path: {path_text!r}")
    path = PurePosixPath(path_text)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise _error(f"{context} must be a normalized repository-relative path")
    if any(token in path_text for token in ("*", "?", "[", "]", "{" , "}")):
        raise _error(f"{context} must not contain glob syntax: {path_text}")
    return path


def _run_git(root: Path, *args: str, text: bool = True) -> str | bytes:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=text,
    )
    if process.returncode != 0:
        stderr = process.stderr.strip() if text else process.stderr.decode("utf-8", "replace").strip()
        raise _error(f"git {' '.join(args)} failed: {stderr}")
    return process.stdout


def _git_blob_identity(root: Path, commit: str, path_text: str) -> tuple[str, str]:
    output = cast(str, _run_git(root, "ls-tree", commit, "--", path_text)).strip()
    fields = output.split(None, 3)
    if len(fields) != 4 or fields[1] != "blob" or fields[3] != path_text:
        raise _error(f"Input is not one exact Git blob at {commit}: {path_text}")
    mode, _kind, oid, _path = fields
    if mode != "100644" or GIT_OID_RE.fullmatch(oid) is None:
        raise _error(f"Input Git identity drifted at {commit}: {path_text}")
    return mode, oid


def _regular_repo_file(root: Path, path_text: str) -> tuple[Path, os.stat_result]:
    relative = _safe_relative_path(path_text, context="input path")
    cursor = root
    for part in relative.parts[:-1]:
        cursor = cursor / part
        try:
            parent_metadata = cursor.lstat()
        except OSError as exc:
            raise _error(f"Input parent is absent: {cursor}") from exc
        if cursor.is_symlink() or not stat.S_ISDIR(parent_metadata.st_mode):
            raise _error(f"Input parent must be a non-symlink directory: {cursor}")
    path = cursor / relative.parts[-1]
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise _error(f"Input must be a regular non-symlink file: {path_text}")
    if metadata.st_nlink != 1:
        raise _error(f"Input must be single-link: {path_text}")
    return path, metadata


def _read_regular_bytes(path: Path, expected: os.stat_result) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or (before.st_dev, before.st_ino) != (expected.st_dev, expected.st_ino)
        ):
            raise _error(f"Input identity changed before read: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, HASH_CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        ):
            raise _error(f"Input identity changed during read: {path}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _validate_structured_file(payload: bytes, spec: InputSpec) -> None:
    if not payload or not payload.strip():
        if spec.allow_empty:
            return
        raise _error(f"Structured input is unexpectedly empty: {spec.path}")
    if b"\r" in payload:
        raise _error(f"Structured input must use LF line endings: {spec.path}")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _error(f"Structured input is not UTF-8: {spec.path}") from exc
    if spec.format == "csv":
        header = next(csv.reader([text.splitlines()[0]]), [])
        if not header or any(not column for column in header) or len(set(header)) != len(header):
            raise _error(f"CSV header is missing or invalid: {spec.path}")
    elif spec.format == "json":
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise _error(f"Invalid JSON input: {spec.path}") from exc
        if not isinstance(decoded, Mapping):
            raise _error(f"JSON input must contain an object: {spec.path}")
    elif spec.format in {"yaml", "dvc"}:
        try:
            decoded = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise _error(f"Invalid YAML input: {spec.path}") from exc
        if not isinstance(decoded, Mapping):
            raise _error(f"YAML input must contain a mapping: {spec.path}")
        if spec.format == "dvc" and not isinstance(decoded.get("outs"), list):
            raise _error(f"DVC pointer lacks outs[]: {spec.path}")
    else:
        raise _error(f"Unsupported structured format {spec.format!r}: {spec.path}")


def input_record(
    root: Path,
    source_commit: str,
    spec: InputSpec,
    *,
    validate_payload: bool = True,
) -> dict[str, Any]:
    path, metadata = _regular_repo_file(root, spec.path)
    git_mode, git_oid = _git_blob_identity(root, source_commit, spec.path)
    live_bytes = _read_regular_bytes(path, metadata)
    source_bytes = cast(
        bytes,
        _run_git(root, "cat-file", "blob", git_oid, text=False),
    )
    if live_bytes != source_bytes:
        raise _error(f"Input differs from its closure-source blob: {spec.path}")
    if validate_payload:
        _validate_structured_file(live_bytes, spec)
    return {
        "path": spec.path,
        "role": spec.role,
        "format": spec.format,
        "bytes": len(live_bytes),
        "sha256": sha256_bytes(live_bytes),
        "git_mode": git_mode,
        "git_blob_oid": git_oid,
        "filesystem_mode": stat.S_IMODE(metadata.st_mode),
    }


def collect_input_records(
    contract: SynthesisContract,
    *,
    root: Path = PROJECT_ROOT,
    validate_payloads: bool = True,
) -> list[dict[str, Any]]:
    return [
        input_record(
            root,
            contract.closure_source_commit,
            spec,
            validate_payload=validate_payloads,
        )
        for spec in contract.allowed_inputs
    ]


def _parse_input_specs(value: Any) -> tuple[InputSpec, ...]:
    records = _require_list(value, context="allowed_inputs")
    specs: list[InputSpec] = []
    for index, record_value in enumerate(records):
        record = _require_mapping(record_value, context=f"allowed_inputs[{index}]")
        allowed_keys = {"path", "role", "format", "allow_empty"}
        if set(record) - allowed_keys:
            raise _error(f"allowed_inputs[{index}] has unknown keys")
        path = _require_text(record.get("path"), context=f"allowed_inputs[{index}].path")
        _safe_relative_path(path, context=f"allowed_inputs[{index}].path")
        role = _require_text(record.get("role"), context=f"allowed_inputs[{index}].role")
        format_name = _require_text(record.get("format"), context=f"allowed_inputs[{index}].format")
        allow_empty = record.get("allow_empty", False)
        if type(allow_empty) is not bool:
            raise _error(f"allowed_inputs[{index}].allow_empty must be boolean")
        specs.append(InputSpec(path, role, format_name, allow_empty))
    paths = tuple(spec.path for spec in specs)
    if len(set(paths)) != len(paths):
        raise _error("allowed_inputs contains duplicate paths")
    if paths != tuple(sorted(paths)):
        raise _error("allowed_inputs must be lexicographically ordered")
    return tuple(specs)


def _validate_path_policy(raw: Mapping[str, Any], specs: Sequence[InputSpec]) -> None:
    policy = _require_mapping(raw.get("input_policy"), context="input_policy")
    expected_policy = {
        "closed_allowlist": True,
        "discovery_forbidden": True,
        "follow_manifest_paths": False,
        "follow_symlinks": False,
        "recursive_walk_forbidden": True,
        "resolve_dvc_pointers": False,
        "read_dvc_payloads": False,
        "inputs_are_read_only": True,
        "forbidden_prefixes": ["private/", "data/targets/"],
        "forbidden_suffixes": [".parquet", ".jsonl", ".md", ".xml"],
        "markdown_and_xml_as_numerical_sources": "forbidden",
        "dvc_pointers_are_identity_evidence_only": True,
        "embedded_path_strings_are_not_inputs": True,
    }
    if policy != expected_policy:
        raise _error("input_policy drifted from the closed outcome-free boundary")
    forbidden_prefixes = _require_string_list(
        policy.get("forbidden_prefixes"), context="input_policy.forbidden_prefixes"
    )
    forbidden_suffixes = _require_string_list(
        policy.get("forbidden_suffixes"), context="input_policy.forbidden_suffixes"
    )
    required_prefixes = {"private/", "data/targets/"}
    if not required_prefixes.issubset(forbidden_prefixes):
        raise _error("input_policy does not block private/ and data/targets/")
    required_suffixes = {".parquet", ".jsonl", ".md", ".xml"}
    if not required_suffixes.issubset(forbidden_suffixes):
        raise _error("input_policy does not block all forbidden source formats")
    format_by_suffix = {".csv": "csv", ".json": "json", ".yaml": "yaml", ".dvc": "dvc"}
    for spec in specs:
        if any(spec.path.startswith(prefix) for prefix in forbidden_prefixes):
            raise _error(f"Allowlisted input enters a forbidden prefix: {spec.path}")
        if any(spec.path.endswith(suffix) for suffix in forbidden_suffixes):
            raise _error(f"Allowlisted input has a forbidden suffix: {spec.path}")
        expected_format = next(
            (format_name for suffix, format_name in format_by_suffix.items() if spec.path.endswith(suffix)),
            None,
        )
        if expected_format != spec.format:
            raise _error(f"Input format/path mismatch: {spec.path}")
    if len(specs) != 83:
        raise _error("The synthesis input allowlist must contain exact83 paths")
    empty_allowed = {spec.path for spec in specs if spec.allow_empty}
    if empty_allowed != {"reports/closure_v1/04_trophic/nla_semantic_metrics.csv"}:
        raise _error("The intentional empty-sentinel allowlist drifted")


def load_contract(
    *,
    root: Path = PROJECT_ROOT,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    verify_inputs: bool = False,
) -> SynthesisContract:
    path = contract_path if contract_path.is_absolute() else root / contract_path
    try:
        decoded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise _error(f"Cannot load Phase 4 synthesis contract: {path}") from exc
    raw = _require_mapping(decoded, context="phase4 synthesis contract")
    required_top_level = {
        "contract_version",
        "closure_source_commit",
        "topology",
        "input_policy",
        "allowed_inputs",
        "matrices",
        "outputs",
        "invariants",
        "rounding",
        "captions",
        "adjudication",
    }
    if set(raw) != required_top_level:
        raise _error("Phase 4 synthesis contract top-level keys drifted")
    if raw.get("contract_version") != "closure_v1_phase4_synthesis_v1":
        raise _error("Phase 4 synthesis contract version drifted")
    source_commit = _require_text(raw.get("closure_source_commit"), context="closure_source_commit")
    if source_commit != "ea8ddce7f8edb9a61db97e29178e52603fa371b1":
        raise _error("Closure source commit drifted")
    topology = _require_mapping(raw.get("topology"), context="topology")
    expected_topology = {
        "ordered_stages": ["H-SYN", "P-SYN", "R-SYN"],
        "H-SYN": {
            "role": "implementation_schema_tests_and_freeze",
            "synthesis_outputs_authorized": False,
            "outcome_access_authorized": False,
        },
        "P-SYN": {
            "role": "data_only_synthesis_authority",
            "requires_published_H_SYN": True,
            "outcome_access_authorized": False,
            "ordered_outputs": [
                AUTHORITY_PATH.as_posix(),
                AUTHORITY_MANIFEST_PATH.as_posix(),
            ],
            "manifest_written_last": True,
        },
        "R-SYN": {
            "role": "deterministic_synthesis_render",
            "requires_published_P_SYN": True,
            "outcome_access_authorized": False,
            "output_count": 24,
            "manifest_written_last": True,
        },
        "closure_source_commit_must_remain_ancestor": True,
        "direct_parent_publication_required": True,
        "clean_worktree_and_index_required_at_each_gate": True,
        "aligned_refs_and_live_remote_required": True,
    }
    if topology != expected_topology:
        raise _error("H-SYN/P-SYN/R-SYN topology drifted")
    specs = _parse_input_specs(raw.get("allowed_inputs"))
    _validate_path_policy(raw, specs)

    matrices = _require_mapping(raw.get("matrices"), context="matrices")
    if set(matrices) != {"final_closure_matrix", "thesis_claim_evidence_matrix"}:
        raise _error("Matrix declarations drifted")
    final_spec = _require_mapping(matrices["final_closure_matrix"], context="final_closure_matrix")
    claim_spec = _require_mapping(
        matrices["thesis_claim_evidence_matrix"], context="thesis_claim_evidence_matrix"
    )
    final_columns = _require_string_list(final_spec.get("columns"), context="final_closure_matrix.columns")
    claim_columns = _require_string_list(claim_spec.get("columns"), context="thesis_claim_evidence_matrix.columns")
    if final_columns != FINAL_CLOSURE_COLUMNS:
        raise _error("FINAL_CLOSURE_MATRIX columns/order drifted")
    if claim_columns != CLAIM_EVIDENCE_COLUMNS:
        raise _error("THESIS_CLAIM_EVIDENCE_MATRIX columns/order drifted")
    if set(final_spec) != {"path", "columns", "sort_key"} or (
        final_spec.get("path") != OUTPUT_PATHS[0]
        or final_spec.get("sort_key")
        != ["hypothesis_id", "metric", "estimand", "model_or_pair"]
    ):
        raise _error("FINAL_CLOSURE_MATRIX path/sort contract drifted")
    if set(claim_spec) != {"path", "columns", "sort_key"} or (
        claim_spec.get("path") != OUTPUT_PATHS[1]
        or claim_spec.get("sort_key")
        != [
            "claim_id",
            "chapter",
            "section",
            "artifact_path",
            "row_filter_or_record",
        ]
    ):
        raise _error("THESIS_CLAIM_EVIDENCE_MATRIX path/sort contract drifted")

    outputs = _require_mapping(raw.get("outputs"), context="outputs")
    if set(outputs) != {
        "root",
        "atomic_bundle",
        "no_clobber",
        "manifest_written_last",
        "ordered_paths",
    } or any(
        outputs.get(key) is not True
        for key in ("atomic_bundle", "no_clobber", "manifest_written_last")
    ) or outputs.get("root") != SYNTHESIS_ROOT.as_posix():
        raise _error("R-SYN publication controls drifted")
    output_paths = _require_string_list(outputs.get("ordered_paths"), context="outputs.ordered_paths")
    for output in output_paths:
        relative = _safe_relative_path(output, context="output path")
        if tuple(relative.parts[:3]) != ("reports", "closure_v1", "11_synthesis"):
            raise _error(f"Output escapes synthesis namespace: {output}")
    if output_paths != OUTPUT_PATHS:
        raise _error("R-SYN output order must be exact24 with manifest last")

    captions = _require_mapping(raw.get("captions"), context="captions")
    if (
        captions.get("required_elements")
        != [
            "population",
            "weighting",
            "horizon",
            "denominator",
            "authority",
            "limitation",
        ]
        or captions.get("svg_title_equals_caption") is not True
        or captions.get("svg_desc_records_sources_and_filters") is not True
    ):
        raise _error("Caption controls drifted")
    literal_captions_raw = _require_mapping(
        captions.get("literal_by_artifact"), context="captions.literal_by_artifact"
    )
    expected_caption_keys = {
        *(f"T{index:02d}" for index in range(1, 13)),
        *(f"F{index:02d}" for index in range(1, 9)),
    }
    if set(literal_captions_raw) != expected_caption_keys:
        raise _error("Literal caption set must be exact T01--T12/F01--F08")
    literal_captions = {
        str(key): _require_text(value, context=f"caption {key}")
        for key, value in literal_captions_raw.items()
    }
    if any(source_commit not in caption for caption in literal_captions.values()):
        raise _error("Every literal caption must bind the closure source commit")

    invariants = _require_mapping(raw.get("invariants"), context="invariants")
    availability = _require_string_list(invariants.get("availability_states"), context="availability_states")
    non_estimable = _require_string_list(invariants.get("non_estimable_states"), context="non_estimable_states")
    unavailable_models = _require_string_list(
        invariants.get("required_unavailable_models"), context="required_unavailable_models"
    )
    hypotheses = _require_string_list(invariants.get("required_hypotheses"), context="required_hypotheses")
    if availability != (
        "not_applicable",
        "model_unavailable",
        "insufficient_support",
        "descriptive_available",
        "confirmatory_available",
    ):
        raise _error("Availability-state vocabulary drifted")
    if non_estimable != (
        "not_applicable",
        "model_unavailable",
        "insufficient_support",
    ):
        raise _error("Non-estimable state vocabulary drifted")
    if unavailable_models != ("P0", "P1", "A2"):
        raise _error("Unavailable model invariant drifted")
    if hypotheses != ("H1", "H2", "H3", "H4", "H5a", "H5b"):
        raise _error("Hypothesis adjudication invariant drifted")
    holm_raw = _require_mapping(invariants.get("holm_universes"), context="holm_universes")
    holm = {str(key): int(value) for key, value in holm_raw.items()}
    if holm != {"A": 3, "B": 78, "C": 1, "D": 9, "E": 1}:
        raise _error("Holm universes drifted")
    expected_invariant_keys = {
        "availability_states",
        "non_estimable_states",
        "required_unavailable_models",
        "required_hypotheses",
        "holm_universes",
        "final_closure_row_count",
        "holm_cell_count",
        "claim_evidence_row_count",
        "table_row_counts",
        "unavailable_hypotheses_remain_in_holm_universe",
        "not_estimable_is_not_zero_effect",
        "unavailable_is_not_negative_result",
        "no_model_substitution",
        "no_denominator_substitution",
        "preserve_estimand_labels",
        "no_cross_estimand_or_cross_freeze_pooling",
        "confidence_intervals_precede_p_values",
        "descriptive_results_are_not_confirmatory",
    }
    if set(invariants) != expected_invariant_keys or any(
        invariants.get(key) is not True
        for key in expected_invariant_keys
        - {
            "availability_states",
            "non_estimable_states",
            "required_unavailable_models",
            "required_hypotheses",
            "holm_universes",
            "final_closure_row_count",
            "holm_cell_count",
            "claim_evidence_row_count",
            "table_row_counts",
        }
    ):
        raise _error("Scientific synthesis invariants drifted")
    table_row_counts_raw = _require_mapping(
        invariants.get("table_row_counts"), context="invariants.table_row_counts"
    )
    table_row_counts = {
        str(key): int(value) for key, value in table_row_counts_raw.items()
    }
    if (
        invariants.get("final_closure_row_count") != 130
        or invariants.get("holm_cell_count") != 92
        or invariants.get("claim_evidence_row_count") != 20
        or table_row_counts
        != {
            "T01": 99,
            "T02": 33,
            "T03": 198,
            "T04": 24,
            "T05": 11,
            "T06": 48,
            "T07": 31,
            "T08": 92,
            "T09": 7,
            "T10": 36,
            "T11": 87,
            "T12": 5,
        }
    ):
        raise _error("Synthesis matrix/table row-count contract drifted")

    rounding = _require_mapping(raw.get("rounding"), context="rounding")
    expected_rounding = {
        "decision_values_use_unrounded_source": True,
        "round_only_at_render_boundary": True,
        "decimal_mode": "half_even",
        "metric_decimal_places": 4,
        "interval_decimal_places": 4,
        "p_value_decimal_places": 6,
        "counts_are_integers": True,
        "negative_zero": "0",
        "nonfinite_values": "forbidden",
        "csv_missing_numeric": "",
        "csv_missing_text": "N/A",
        "markdown_and_svg_missing": "N/A",
        "json_missing": None,
        "zero_for_missing": "forbidden",
    }
    if rounding != expected_rounding:
        raise _error("Rounding and missing-value policy drifted")

    adjudication = _require_mapping(raw.get("adjudication"), context="adjudication")
    expected_adjudication_keys = {
        "hypothesis_order",
        "decisive_experiments",
        "registered_hypotheses",
        "verdict_vocabulary",
        "global_thesis_verdict",
        "causal_field_claims",
        "official_management_recommendations",
        "rerun_E0_U_or_E1_E10",
        "refit_or_reconstruct_P0_P1_A2",
        "recalibrate_or_change_thresholds",
        "edit_manuscript_before_matrix_and_report_approval",
    }
    if set(adjudication) != expected_adjudication_keys:
        raise _error("Adjudication contract keys drifted")
    if adjudication.get("hypothesis_order") != ["H1", "H2", "H3", "H4", "H5a", "H5b"]:
        raise _error("Adjudication hypothesis order drifted")
    if adjudication.get("decisive_experiments") != {
        "H1": ["E7", "E4"],
        "H2": ["E1", "E2"],
        "H3": ["E8", "E6"],
        "H4": ["E6"],
        "H5a": ["E9"],
        "H5b": ["E9"],
    }:
        raise _error("Decisive-experiment mapping drifted")
    registered = _require_mapping(
        adjudication.get("registered_hypotheses"),
        context="adjudication.registered_hypotheses",
    )
    if set(registered) != {"H1", "H2", "H3", "H4", "H5a", "H5b"}:
        raise _error("Registered-hypothesis adjudication groups drifted")
    registered_lists = {
        key: _require_string_list(value, context=f"registered_hypotheses.{key}")
        for key, value in registered.items()
    }
    expected_registered = {
        "H1": ("H1_P1_vs_P0", "H_surface_A2_vs_P1"),
        "H2": ("H2_P1_vs_B1", "H2_P1_vs_B2"),
        "H3": ("H_E_uncertainty_before_vs_after_recalibration",),
        "H4": (
            "H4_M0_vs_P1_control",
            "H4_M0_vs_P1_mcar_10",
            "H4_M0_vs_P1_mcar_25",
            "H4_M0_vs_P1_mcar_50",
            "H4_M0_vs_P1_block_1m_10",
            "H4_M0_vs_P1_block_3m_10",
            "H4_M0_vs_P1_block_6m_25",
            "H4_M0_vs_P1_ablate_nutrients",
            "H4_M0_vs_P1_ablate_physchem",
            "H4_M0_vs_P1_ablate_light",
            "H4_M0_vs_P1_ablate_temperature",
            "H4_M0_vs_P1_combined_moderate",
            "H4_M0_vs_P1_combined_severe",
        ),
        "H5a": (
            "H_D_tp_reduction_10_vs_no_action",
            "H_D_tp_reduction_25_vs_no_action",
            "H_D_tn_reduction_10_vs_no_action",
            "H_D_tp_tn_reduction_10_vs_no_action",
            "H_D_clarity_mild_vs_no_action",
            "H_D_clarity_strong_vs_no_action",
            "H_D_oxygen_support_05_vs_no_action",
            "H_D_nutrient_clarity_mild_vs_no_action",
            "H_D_nutrient_clarity_strong_vs_no_action",
        ),
        "H5b": (
            "H_D_tp_reduction_10_vs_no_action",
            "H_D_tp_reduction_25_vs_no_action",
            "H_D_tn_reduction_10_vs_no_action",
            "H_D_tp_tn_reduction_10_vs_no_action",
            "H_D_clarity_mild_vs_no_action",
            "H_D_clarity_strong_vs_no_action",
            "H_D_oxygen_support_05_vs_no_action",
            "H_D_nutrient_clarity_mild_vs_no_action",
            "H_D_nutrient_clarity_strong_vs_no_action",
        ),
    }
    if registered_lists != expected_registered:
        raise _error("Registered-hypothesis adjudication membership drifted")
    if adjudication.get("verdict_vocabulary") != [
        "limited_descriptive_support",
        "not_estimable_primary_architecture",
        "partial_descriptive_only",
        "not_estimable",
        "not_confirmed_scientifically",
    ]:
        raise _error("Verdict vocabulary drifted")
    if (
        adjudication.get("global_thesis_verdict")
        != "no_conclusive_predictive_corroboration_with_reproducible_engineering_and_methodological_contribution"
        or any(
            adjudication.get(key) != "forbidden"
            for key in (
                "causal_field_claims",
                "official_management_recommendations",
                "rerun_E0_U_or_E1_E10",
                "refit_or_reconstruct_P0_P1_A2",
                "recalibrate_or_change_thresholds",
                "edit_manuscript_before_matrix_and_report_approval",
            )
        )
    ):
        raise _error("Adjudication prohibitions drifted")

    contract = SynthesisContract(
        path=path,
        raw=raw,
        closure_source_commit=source_commit,
        allowed_inputs=specs,
        output_paths=output_paths,
        final_closure_columns=final_columns,
        claim_evidence_columns=claim_columns,
        availability_states=availability,
        non_estimable_states=non_estimable,
        required_unavailable_models=unavailable_models,
        required_hypotheses=hypotheses,
        holm_universes=holm,
        final_closure_row_count=130,
        claim_evidence_row_count=20,
        table_row_counts=table_row_counts,
        artifact_captions=literal_captions,
    )
    if verify_inputs:
        collect_input_records(contract, root=root)
    return contract


def _validate_exact_columns(
    row: Mapping[str, str], columns: Sequence[str], *, context: str
) -> None:
    if tuple(row) != tuple(columns):
        raise _error(f"{context} columns/order drifted")
    for key, value in row.items():
        if not isinstance(value, str):
            raise _error(f"{context}.{key} must be text")
        if "\r" in value or "\x00" in value:
            raise _error(f"{context}.{key} contains forbidden control bytes")


def _validate_denominators(row: Mapping[str, str], *, context: str) -> None:
    values: list[int] = []
    for column in ("attempted_denominator", "successful_denominator"):
        raw = row[column]
        if not raw.isascii() or not raw.isdigit():
            raise _error(f"{context}.{column} must be a non-negative integer")
        values.append(int(raw))
    if values[1] > values[0]:
        raise _error(f"{context} successful denominator exceeds attempted")


def _evidence_paths(value: str, *, context: str) -> tuple[str, ...]:
    paths = tuple(item for item in value.split(";") if item)
    if not paths or ";".join(paths) != value or len(set(paths)) != len(paths):
        raise _error(f"{context} evidence_paths must be a unique semicolon list")
    for path in paths:
        _safe_relative_path(path, context=context)
    return paths


def validate_final_closure_rows(
    rows: Sequence[Mapping[str, str]], contract: SynthesisContract
) -> None:
    if len(rows) != contract.final_closure_row_count:
        raise _error(
            "FINAL_CLOSURE_MATRIX must contain exact"
            f"{contract.final_closure_row_count} rows"
        )
    expected_order = sorted(
        rows,
        key=lambda row: (
            row.get("hypothesis_id", ""),
            row.get("metric", ""),
            row.get("estimand", ""),
            row.get("model_or_pair", ""),
        ),
    )
    if list(rows) != expected_order:
        raise _error("FINAL_CLOSURE_MATRIX row order drifted")
    allowed_inputs = set(contract.allowed_input_paths)
    observed_hypotheses: set[str] = set()
    unavailable_models: set[str] = set()
    family_cells: dict[str, set[tuple[str, str, str, str]]] = {
        family: set() for family in contract.holm_universes
    }
    for index, row in enumerate(rows):
        context = f"FINAL_CLOSURE_MATRIX row {index + 1}"
        _validate_exact_columns(row, contract.final_closure_columns, context=context)
        _validate_denominators(row, context=context)
        state = row["availability_state"]
        if state not in contract.availability_states:
            raise _error(f"{context} has unknown availability_state")
        if state in contract.non_estimable_states and (row["estimate"] or row["uncertainty"]):
            raise _error(f"{context} encodes a non-estimable value")
        if row["estimate"].strip().lower() in NULL_TOKENS or row["uncertainty"].strip().lower() in NULL_TOKENS:
            raise _error(f"{context} uses a textual null token")
        if row["authority_commit"] != contract.closure_source_commit:
            raise _error(f"{context} mixes authority commits")
        hypothesis_id = row["hypothesis_id"]
        for required in contract.required_hypotheses:
            if hypothesis_id == required or hypothesis_id.startswith(required + ":"):
                observed_hypotheses.add(required)
        for model_id in contract.required_unavailable_models:
            if model_id in row["model_or_pair"] and state == "model_unavailable":
                unavailable_models.add(model_id)
        for path in _evidence_paths(row["evidence_paths"], context=context):
            if path not in allowed_inputs:
                raise _error(f"{context} cites a non-allowlisted input: {path}")
        family = row["multiplicity_family"]
        if family:
            if family not in family_cells:
                raise _error(f"{context} has unknown Holm family")
            family_cells[family].add(
                (row["model_or_pair"], row["metric"], row["population"], row["estimand"])
            )
    if observed_hypotheses != set(contract.required_hypotheses):
        raise _error("FINAL_CLOSURE_MATRIX does not adjudicate H1--H5b")
    if unavailable_models != set(contract.required_unavailable_models):
        raise _error("FINAL_CLOSURE_MATRIX hides P0, P1 or A2")
    if not {
        "not_applicable",
        "model_unavailable",
        "insufficient_support",
        "descriptive_available",
    }.issubset({row["availability_state"] for row in rows}):
        raise _error("FINAL_CLOSURE_MATRIX collapsed required availability states")
    observed_universes = {family: len(cells) for family, cells in family_cells.items()}
    if observed_universes != dict(contract.holm_universes):
        raise _error(f"Holm universe cells drifted: {observed_universes}")


def validate_claim_evidence_rows(
    rows: Sequence[Mapping[str, str]], contract: SynthesisContract
) -> None:
    if len(rows) != contract.claim_evidence_row_count:
        raise _error(
            "THESIS_CLAIM_EVIDENCE_MATRIX must contain exact"
            f"{contract.claim_evidence_row_count} rows"
        )
    expected_order = sorted(
        rows,
        key=lambda row: (
            row.get("claim_id", ""),
            row.get("chapter", ""),
            row.get("section", ""),
            row.get("artifact_path", ""),
            row.get("row_filter_or_record", ""),
        ),
    )
    if list(rows) != expected_order:
        raise _error("THESIS_CLAIM_EVIDENCE_MATRIX row order drifted")
    allowed_artifacts = set(contract.allowed_input_paths) | set(contract.output_paths)
    claim_ids: set[str] = set()
    for index, row in enumerate(rows):
        context = f"THESIS_CLAIM_EVIDENCE_MATRIX row {index + 1}"
        _validate_exact_columns(row, contract.claim_evidence_columns, context=context)
        claim_id = row["claim_id"]
        if not claim_id or claim_id in claim_ids:
            raise _error(f"{context} claim_id is missing or duplicated")
        claim_ids.add(claim_id)
        claim_status = row["claim_status"]
        if claim_status not in contract.availability_states:
            raise _error(f"{context} has unknown claim_status")
        artifact = row["artifact_path"]
        if artifact not in allowed_artifacts:
            raise _error(f"{context} cites a non-authorized artifact")
        if row["authority_commit"] != contract.closure_source_commit:
            raise _error(f"{context} mixes authority commits")
        if not row["allowed_wording"] or not row["forbidden_wording"]:
            raise _error(f"{context} lacks wording boundaries")
        value = row["value_or_state"].strip().lower()
        if value in NULL_TOKENS:
            raise _error(f"{context} uses a textual null token")
    required_destinations = {"III", "IV", "V", "Summary", "Abstract", "Conclusion"}
    if not required_destinations.issubset({row["chapter"] for row in rows}):
        raise _error("THESIS_CLAIM_EVIDENCE_MATRIX lacks manuscript destinations")


def csv_bytes(rows: Sequence[Mapping[str, str]], columns: Sequence[str]) -> bytes:
    """Serialize exact-column rows deterministically as UTF-8/LF CSV."""

    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(columns),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")
