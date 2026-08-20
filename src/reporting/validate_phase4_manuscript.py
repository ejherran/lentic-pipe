#!/usr/bin/env python
"""Validate a Phase 4 thesis manuscript without writing or opening outcomes.

The validator has no repository-private defaults.  Every readable input is
explicitly supplied by the caller, while artifact references are checked only
for safe filesystem existence.  Raw targets, outcome paths, Parquet payloads,
and ``private/FULL.md`` are rejected before filesystem access.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import stat
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


CLOSURE_SOURCE_COMMIT = "ea8ddce7f8edb9a61db97e29178e52603fa371b1"
R_SYN_COMMIT = "528dcb7"
EXPECTED_BUILD_PDF_BYTES = 863_932
EXPECTED_BUILD_PDF_PAGES = 80
EXPECTED_BUILD_PDF_SHA256 = (
    "b20908f37c93b8039431132ffb3def28fa08154b75cb5283011cf1f3bbb05044"
)
BUILD_OUTPUT_SUFFIXES = (".aux", ".fls", ".log", ".out", ".pdf", ".toc")
FLS_BUILD_INPUT_SUFFIXES = (".aux", ".out", ".toc")
FLS_OUTPUT_SUFFIXES = (".aux", ".log", ".out", ".pdf", ".toc")
EXPECTED_LISTING_INPUTS = (
    "demo_mifal_ed_v5.py",
    "mifal_ed_v5.py",
    "test_mifal_ed_v5.py",
)
EXPECTED_FLS_WORKING_DIRECTORY = "/workspace/private/mifal_ed_t2"

CLAIM_COLUMNS = (
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

EXPECTED_CLAIM_IDS = (
    "C01_holdout_population",
    "C02_intent_to_predict",
    "C03_primary_models_unavailable",
    "C04_brier_observation_weighted",
    "C05_pr_auc_observation_weighted",
    "C06_f1_vs_f0_absolute_error",
    "C07_anfis_ablation",
    "C08_anfis_missing_diagnostics",
    "C09_site_transfer",
    "C10_thresholds",
    "C11_trophic_b2_vs_b1",
    "C12_degradation",
    "C13_uncertainty",
    "C14_multiplicity",
    "C15_planning",
    "C16_software",
    "C17_global_verdict_discussion",
    "C18_summary_boundary",
    "C19_abstract_boundary",
    "C20_conclusion_boundary",
)

EXPECTED_CLAIM_DESTINATIONS: Mapping[str, str] = {
    **{claim_id: "III" for claim_id in EXPECTED_CLAIM_IDS[0:2]},
    **{claim_id: "IV" for claim_id in EXPECTED_CLAIM_IDS[2:16]},
    EXPECTED_CLAIM_IDS[16]: "V",
    EXPECTED_CLAIM_IDS[17]: "Summary",
    EXPECTED_CLAIM_IDS[18]: "Abstract",
    EXPECTED_CLAIM_IDS[19]: "Conclusion",
}

EXPECTED_FIGURE_PDFS = (
    "F01_intent_to_predict_funnel.pdf",
    "F02_benchmark_metrics.pdf",
    "F03_descriptive_deltas.pdf",
    "F04_threshold_sensitivity.pdf",
    "F05_trophic_heatmap.pdf",
    "F06_uncertainty_coverage.pdf",
    "F07_hypothesis_verdicts.pdf",
    "F08_provenance.pdf",
)

EXPECTED_INPUT_BREAKDOWN: Mapping[str, int] = {
    "csv": 45,
    "dvc": 4,
    "json": 33,
    "total": 83,
    "yaml": 1,
}
EXPECTED_HOLM_UNIVERSES: Mapping[str, int] = {
    "A": 3,
    "B": 78,
    "C": 1,
    "D": 9,
    "E": 1,
}

_CLAIM_RE = re.compile(r"\\claimid\s*\{([^{}]+)\}")
_ARTIFACT_RE = re.compile(r"\\artifactpath\s*\{([^{}]+)\}")
_INCLUDEGRAPHICS_RE = re.compile(
    r"\\includegraphics\s*(?:\[[^\]]*\]\s*)?\{([^{}]+)\}"
)
_HEADING_OR_CLAIM_RE = re.compile(
    r"\\(?P<heading>chapter\*?|section\*?)\s*\{(?P<title>[^{}]*)\}"
    r"|\\claimid\s*\{(?P<claim>[^{}]+)\}"
)
_ENVIRONMENT_RE = re.compile(r"(?<!\\)\\(?P<kind>begin|end)\s*\{(?P<name>[^{}]+)\}")
_LABEL_RE = re.compile(r"\\label\s*\{([^{}]+)\}")
_REFERENCE_RE = re.compile(
    r"\\(?:ref|pageref|eqref|autoref|cref|Cref|vref|Vref|nameref)"
    r"\*?(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}"
)
_CITATION_RE = re.compile(
    r"\\(?:cite[a-zA-Z]*|parencite|textcite|autocite)\*?"
    r"(?:\s*\[[^\]]*\]){0,2}\s*\{([^{}]+)\}"
)
_BIBITEM_RE = re.compile(r"\\bibitem(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}")


def _ascii_token(values: Sequence[int]) -> str:
    return "".join(chr(value) for value in values)


_LOCALIZED_SUMMARY = _ascii_token((114, 101, 115, 117, 109, 101, 110))
_LOCALIZED_CHAPTER = _ascii_token((99, 97, 112, 105, 116, 117, 108, 111))
_LOCALIZED_METHODOLOGY_STEM = _ascii_token((109, 101, 116, 111, 100, 111, 108, 111, 103))
_LOCALIZED_RESULTS_STEM = _ascii_token((114, 101, 115, 117, 108, 116, 97, 100))
_LOCALIZED_DISCUSSION_STEM = _ascii_token((100, 105, 115, 99, 117, 115, 105))
_LOCALIZED_ONE_ARTICLE = _ascii_token((117, 110))
_LOCALIZED_ONE_WORD = _ascii_token((117, 110, 111))
_LOCALIZED_FOUR_WORD = _ascii_token((99, 117, 97, 116, 114, 111))


class ManuscriptValidationError(RuntimeError):
    """Raised when a Phase 4 manuscript invariant cannot be established."""


def _error(message: str) -> ManuscriptValidationError:
    return ManuscriptValidationError(message)


@dataclass(frozen=True)
class _ValidatedBuild:
    evidence: Mapping[str, Any]
    pdf_payload: bytes
    directory_identity: tuple[int, int]


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _validate_repo_root(repo_root: Path) -> Path:
    root = _lexical_absolute(repo_root)
    try:
        metadata = root.lstat()
    except OSError as exc:
        raise _error("Repository root does not exist") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise _error("Repository root must be a non-symlink directory")
    return root


def _forbidden_relative_path(relative: PurePosixPath) -> bool:
    lowered = relative.as_posix().lower()
    parts = tuple(part.lower() for part in relative.parts)
    if lowered == "private/full.md":
        return True
    if lowered.endswith(".parquet"):
        return True
    if len(parts) >= 2 and parts[0:2] == ("data", "targets"):
        return True
    return any("outcome" in part for part in parts)


def _safe_relative_text(path_text: str, *, context: str) -> PurePosixPath:
    if not path_text or path_text != path_text.strip():
        raise _error(f"{context} must be non-empty trimmed text")
    if "\\" in path_text or "\x00" in path_text:
        raise _error(f"{context} must be a canonical POSIX path")
    relative = PurePosixPath(path_text)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise _error(f"{context} must be repository-relative and normalized")
    if any(character in path_text for character in ("*", "?", "[", "]", "{", "}")):
        raise _error(f"{context} must not contain discovery syntax")
    if _forbidden_relative_path(relative):
        raise _error(f"{context} is forbidden by the read boundary")
    return relative


def _resolve_explicit_input(
    root: Path,
    supplied: Path,
    *,
    context: str,
) -> tuple[Path, PurePosixPath]:
    candidate = supplied if supplied.is_absolute() else root / supplied
    candidate = _lexical_absolute(candidate)
    try:
        relative_path = candidate.relative_to(root)
    except ValueError as exc:
        raise _error(f"{context} must remain inside the repository root") from exc
    relative = _safe_relative_text(relative_path.as_posix(), context=context)
    return candidate, relative


def _leaf_metadata(
    root: Path,
    relative: PurePosixPath,
    *,
    context: str,
    allow_directory: bool = False,
) -> tuple[Path, os.stat_result]:
    cursor = root
    for part in relative.parts[:-1]:
        cursor /= part
        try:
            metadata = cursor.lstat()
        except OSError as exc:
            raise _error(f"{context} parent does not exist") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise _error(f"{context} parent must be a non-symlink directory")

    path = cursor / relative.parts[-1]
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _error(f"{context} does not exist") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise _error(f"{context} must not be a symlink")
    if allow_directory and stat.S_ISDIR(metadata.st_mode):
        return path, metadata
    if not stat.S_ISREG(metadata.st_mode):
        raise _error(f"{context} must be a regular file")
    if metadata.st_nlink != 1:
        raise _error(f"{context} must be single-link")
    return path, metadata


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


def _read_bound_bytes(
    path: Path,
    expected: os.stat_result,
    *,
    context: str,
) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino) != (expected.st_dev, expected.st_ino)
        ):
            raise _error(f"{context} identity changed before read")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if _metadata_identity(before) != _metadata_identity(after):
            raise _error(f"{context} identity changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_explicit_utf8(
    root: Path,
    supplied: Path,
    *,
    context: str,
) -> tuple[str, Path]:
    path, relative = _resolve_explicit_input(root, supplied, context=context)
    checked_path, metadata = _leaf_metadata(root, relative, context=context)
    if checked_path != path:
        raise _error(f"{context} path normalization drifted")
    payload = _read_bound_bytes(path, metadata, context=context)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _error(f"{context} must be UTF-8") from exc
    if "\x00" in text:
        raise _error(f"{context} contains a NUL byte")
    return text, path


def _hash_explicit_file(root: Path, supplied: Path, *, context: str) -> dict[str, Any]:
    path, relative = _resolve_explicit_input(root, supplied, context=context)
    checked_path, metadata = _leaf_metadata(root, relative, context=context)
    if checked_path != path:
        raise _error(f"{context} path normalization drifted")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino) != (metadata.st_dev, metadata.st_ino)
        ):
            raise _error(f"{context} identity changed before read")
        digest = hashlib.sha256()
        byte_count = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            byte_count += len(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
        if _metadata_identity(before) != _metadata_identity(after):
            raise _error(f"{context} identity changed during read")
    finally:
        os.close(descriptor)
    return {"bytes": byte_count, "sha256": digest.hexdigest()}


def _build_directory_path(root: Path, supplied: Path, *, context: str) -> Path:
    if "\x00" in os.fspath(supplied) or any(part == ".." for part in supplied.parts):
        raise _error(f"{context} must be a normalized explicit path")
    if supplied.is_absolute():
        candidate = _lexical_absolute(supplied)
        cursor = Path(candidate.anchor)
        parts_to_walk = candidate.parts[1:]
    else:
        relative = _safe_relative_text(
            supplied.as_posix(),
            context=context,
        )
        candidate = _lexical_absolute(root / Path(*relative.parts))
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise _error(f"{context} must remain below the repository root") from exc
        cursor = root
        parts_to_walk = relative.parts
    lowered_parts = tuple(part.lower() for part in candidate.parts)
    if (
        any("outcome" in part for part in lowered_parts)
        or "targets" in lowered_parts
        or any(part.endswith(".parquet") for part in lowered_parts)
        or lowered_parts[-2:] == ("private", "full.md")
    ):
        raise _error(f"{context} is forbidden by the read boundary")
    for part in parts_to_walk:
        cursor /= part
        try:
            metadata = cursor.lstat()
        except OSError as exc:
            raise _error(f"{context} or one of its ancestors does not exist") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise _error(f"{context} ancestors and leaf must not be symlinks")
        if not stat.S_ISDIR(metadata.st_mode):
            raise _error(f"{context} ancestors and leaf must be directories")
    return candidate


def _read_build_leaf(
    directory_descriptor: int,
    name: str,
    expected: os.stat_result,
    *,
    context: str,
) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_descriptor,
    )
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino) != (expected.st_dev, expected.st_ino)
        ):
            raise _error(f"{context} identity changed before read")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if _metadata_identity(before) != _metadata_identity(after):
            raise _error(f"{context} identity changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _payload_record(payload: bytes) -> dict[str, Any]:
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def _decode_build_text(
    payload: bytes,
    *,
    context: str,
    allow_latin1: bool = False,
) -> str:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        if not allow_latin1:
            raise _error(f"{context} must be UTF-8") from exc
        text = payload.decode("latin-1")
    if "\x00" in text:
        raise _error(f"{context} contains a NUL byte")
    return text


def _count_patterns(text: str, patterns: Sequence[re.Pattern[str]]) -> int:
    return sum(len(pattern.findall(text)) for pattern in patterns)


def _validate_final_log(log_payload: bytes, *, stem: str) -> dict[str, Any]:
    text = _decode_build_text(
        log_payload,
        context="final build log",
        allow_latin1=True,
    )
    latex_error_count = _count_patterns(
        text,
        (
            re.compile(r"(?m)^!\s"),
            re.compile(r"(?i)\b(?:LaTeX|Package [^:\n]+) Error:"),
            re.compile(r"(?mi)Emergency stop"),
            re.compile(r"(?mi)Fatal error occurred"),
        ),
    )
    undefined_reference_or_citation_count = _count_patterns(
        text,
        (
            re.compile(
                r"(?mi)^(?:LaTeX|Package [^\n]+) Warning: "
                r"(?:Reference|Citation) .+ undefined"
            ),
            re.compile(r"(?mi)There were undefined (?:references|citations)"),
        ),
    )
    duplicate_destination_count = _count_patterns(
        text,
        (
            re.compile(r"(?i)destination with the same identifier"),
            re.compile(r"(?i)duplicate destination"),
        ),
    )
    rerun_request_count = _count_patterns(
        text,
        (
            re.compile(r"(?i)\bRerun (?:to|get|LaTeX)"),
            re.compile(r"(?i)\bPlease (?:(?:\(re\)|re)?run)\b"),
            re.compile(r"(?i)\brun LaTeX again\b"),
            re.compile(r"(?i)Label\(s\) may have changed"),
            re.compile(r"(?i)rerunfilecheck Warning"),
        ),
    )
    overfull_count = len(re.findall(r"(?mi)^\s*Overfull \\[hv]box", text))
    issue_counts = {
        "duplicate_destination_count": duplicate_destination_count,
        "latex_error_count": latex_error_count,
        "overfull_count": overfull_count,
        "rerun_request_count": rerun_request_count,
        "undefined_reference_or_citation_count": (
            undefined_reference_or_citation_count
        ),
    }
    if any(issue_counts.values()):
        raise _error("Final LaTeX log contains a forbidden diagnostic")

    output_pattern = re.compile(
        rf"(?m)^Output written on /build/{re.escape(stem)}\.pdf "
        r"\((\d+) pages?, (\d+) bytes\)\.$"
    )
    output_records = output_pattern.findall(text)
    if len(output_records) != 1:
        raise _error("Final LaTeX log must contain one exact output record")
    pages, byte_count = (int(value) for value in output_records[0])
    if pages != EXPECTED_BUILD_PDF_PAGES or byte_count != EXPECTED_BUILD_PDF_BYTES:
        raise _error("Final LaTeX page or byte count drifted")
    return {
        **_payload_record(log_payload),
        **issue_counts,
        "output_record_count": 1,
        "page_count": pages,
    }


def _canonical_absolute_fls_path(path_text: str, *, context: str) -> PurePosixPath:
    if "\\" in path_text or "\x00" in path_text:
        raise _error(f"{context} is not a canonical POSIX path")
    path = PurePosixPath(path_text)
    if (
        not path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != path_text
    ):
        raise _error(f"{context} is not a normalized absolute path")
    return path


def _canonical_relative_fls_path(path_text: str, *, context: str) -> str:
    if "\\" in path_text or "\x00" in path_text:
        raise _error(f"{context} is not a canonical relative path")
    path = PurePosixPath(path_text)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise _error(f"{context} is not a normalized relative path")
    normalized = path.as_posix()
    if _forbidden_relative_path(PurePosixPath(normalized)):
        raise _error(f"{context} is forbidden by the read boundary")
    if path_text not in {normalized, f"./{normalized}"}:
        raise _error(f"{context} contains a non-canonical relative spelling")
    return normalized


def _validate_fls(fls_payload: bytes, *, tex_name: str, stem: str) -> dict[str, Any]:
    text = _decode_build_text(fls_payload, context="FLS recorder output")
    if not text.endswith("\n"):
        raise _error("FLS recorder output must end with LF")
    records: list[tuple[str, str]] = []
    for line in text.splitlines():
        kind, separator, path_text = line.partition(" ")
        if separator != " " or not path_text or path_text != path_text.strip():
            raise _error("FLS recorder line is malformed")
        if kind not in {"PWD", "INPUT", "OUTPUT"}:
            raise _error("FLS recorder contains an unsupported record kind")
        records.append((kind, path_text))

    working_directories = [value for kind, value in records if kind == "PWD"]
    if len(working_directories) != 1:
        raise _error("FLS recorder must contain exactly one working directory")
    if working_directories[0] != EXPECTED_FLS_WORKING_DIRECTORY:
        raise _error("FLS working directory differs from the exact sealed value")
    _canonical_absolute_fls_path(
        working_directories[0],
        context="FLS working directory",
    )

    expected_relative_inputs = {
        tex_name,
        *EXPECTED_LISTING_INPUTS,
        *(f"closure_v1_figures/{name}" for name in EXPECTED_FIGURE_PDFS),
    }
    expected_build_inputs = {
        f"/build/{stem}{suffix}" for suffix in FLS_BUILD_INPUT_SUFFIXES
    }
    expected_outputs = {f"/build/{stem}{suffix}" for suffix in FLS_OUTPUT_SUFFIXES}
    relative_inputs: list[str] = []
    build_inputs: list[str] = []
    toolchain_inputs: list[str] = []
    for kind, path_text in records:
        if kind != "INPUT":
            continue
        if path_text.startswith("/usr/local/texlive/"):
            _canonical_absolute_fls_path(path_text, context="FLS toolchain input")
            toolchain_inputs.append(path_text)
        elif path_text.startswith("/build/"):
            _canonical_absolute_fls_path(path_text, context="FLS build input")
            if path_text not in expected_build_inputs:
                raise _error("FLS recorder contains an unexpected /build input")
            build_inputs.append(path_text)
        elif path_text.startswith("/"):
            raise _error("FLS recorder escaped the allowed absolute input roots")
        else:
            relative_inputs.append(
                _canonical_relative_fls_path(
                    path_text,
                    context="FLS relative input",
                )
            )
    if not toolchain_inputs:
        raise _error("FLS recorder contains no TeX Live toolchain inputs")
    if set(build_inputs) != expected_build_inputs:
        raise _error("FLS recorder is missing an exact /build aux/out/toc input")
    if set(relative_inputs) != expected_relative_inputs:
        raise _error("FLS recorder relative inputs differ from the exact manuscript set")

    outputs = [value for kind, value in records if kind == "OUTPUT"]
    for output in outputs:
        _canonical_absolute_fls_path(output, context="FLS output")
    if set(outputs) != expected_outputs:
        raise _error("FLS recorder outputs differ from the exact build set")
    return {
        **_payload_record(fls_payload),
        "build_input_record_count": len(build_inputs),
        "input_record_count": len(relative_inputs) + len(build_inputs) + len(toolchain_inputs),
        "output_record_count": len(outputs),
        "relative_input_record_count": len(relative_inputs),
        "relative_input_unique_count": len(set(relative_inputs)),
        "toolchain_input_record_count": len(toolchain_inputs),
        "toolchain_input_unique_count": len(set(toolchain_inputs)),
        "working_directory_record_count": 1,
    }


def _validate_build_directory(
    root: Path,
    supplied: Path,
    *,
    context: str,
    tex_name: str,
    stem: str,
) -> _ValidatedBuild:
    directory = _build_directory_path(root, supplied, context=context)
    expected_names = {f"{stem}{suffix}" for suffix in BUILD_OUTPUT_SUFFIXES}
    expected_directory_metadata = directory.lstat()
    descriptor = os.open(
        directory,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before_directory = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(before_directory.st_mode)
            or (before_directory.st_dev, before_directory.st_ino)
            != (expected_directory_metadata.st_dev, expected_directory_metadata.st_ino)
        ):
            raise _error(f"{context} identity changed before validation")
        observed_names = set(os.listdir(descriptor))
        if observed_names != expected_names:
            raise _error(f"{context} must contain the exact six build outputs")

        metadata_by_name: dict[str, os.stat_result] = {}
        for name in sorted(expected_names):
            metadata = os.stat(
                name,
                dir_fd=descriptor,
                follow_symlinks=False,
            )
            if not stat.S_ISREG(metadata.st_mode):
                raise _error(f"{context} outputs must be regular files")
            if metadata.st_nlink != 1:
                raise _error(f"{context} outputs must be single-link")
            metadata_by_name[name] = metadata

        fls_name = f"{stem}.fls"
        log_name = f"{stem}.log"
        pdf_name = f"{stem}.pdf"
        fls_payload = _read_build_leaf(
            descriptor,
            fls_name,
            metadata_by_name[fls_name],
            context=f"{context} FLS output",
        )
        log_payload = _read_build_leaf(
            descriptor,
            log_name,
            metadata_by_name[log_name],
            context=f"{context} log output",
        )
        pdf_payload = _read_build_leaf(
            descriptor,
            pdf_name,
            metadata_by_name[pdf_name],
            context=f"{context} PDF output",
        )
        fls_evidence = _validate_fls(fls_payload, tex_name=tex_name, stem=stem)
        log_evidence = _validate_final_log(log_payload, stem=stem)
        pdf_evidence = _payload_record(pdf_payload)
        if (
            pdf_evidence["bytes"] != EXPECTED_BUILD_PDF_BYTES
            or pdf_evidence["sha256"] != EXPECTED_BUILD_PDF_SHA256
        ):
            raise _error(f"{context} PDF identity drifted")

        for name, before in metadata_by_name.items():
            after = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if _metadata_identity(before) != _metadata_identity(after):
                raise _error(f"{context} output identity changed during validation")
        if set(os.listdir(descriptor)) != expected_names:
            raise _error(f"{context} contents changed during validation")
        after_directory = os.fstat(descriptor)
        if _metadata_identity(before_directory) != _metadata_identity(after_directory):
            raise _error(f"{context} identity changed during validation")
    finally:
        os.close(descriptor)
    return _ValidatedBuild(
        evidence={
            "fls": fls_evidence,
            "log": log_evidence,
            "output_file_count": len(expected_names),
            "pdf": pdf_evidence,
        },
        pdf_payload=pdf_payload,
        directory_identity=(
            expected_directory_metadata.st_dev,
            expected_directory_metadata.st_ino,
        ),
    )


def _validate_build_pair(
    root: Path,
    build_dir_a: Path,
    build_dir_b: Path,
    *,
    tex_name: str,
    stem: str,
) -> dict[str, Any]:
    build_a = _validate_build_directory(
        root,
        build_dir_a,
        context="build A directory",
        tex_name=tex_name,
        stem=stem,
    )
    build_b = _validate_build_directory(
        root,
        build_dir_b,
        context="build B directory",
        tex_name=tex_name,
        stem=stem,
    )
    if build_a.directory_identity == build_b.directory_identity:
        raise _error("Build A and build B must be distinct directories")
    pdf_byte_identical = build_a.pdf_payload == build_b.pdf_payload
    if not pdf_byte_identical:
        raise _error("Build A and build B PDFs differ byte-for-byte")
    return {
        "build_a": dict(build_a.evidence),
        "build_b": dict(build_b.evidence),
        "expected_output_file_count": len(BUILD_OUTPUT_SUFFIXES),
        "pdf_byte_identical": True,
    }


def _strip_tex_comments(text: str) -> str:
    stripped_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        cut = len(line)
        for index, character in enumerate(line):
            if character != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cut = index
                break
        suffix = "\n" if line.endswith("\n") else ""
        stripped_lines.append(line[:cut].rstrip("\r\n") + suffix)
    return "".join(stripped_lines)


def _normalize_prose(text: str) -> str:
    normalized = text.replace("\\_", "_")
    normalized = re.sub(r"\\[a-zA-Z@]+\*?", " ", normalized)
    normalized = normalized.replace("{", " ").replace("}", " ")
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", normalized).strip().lower()


def _decode_tex_path(path_text: str, *, context: str) -> str:
    decoded = path_text.strip()
    for escaped, literal in (("\\_", "_"), ("\\%", "%"), ("\\#", "#"), ("\\&", "&")):
        decoded = decoded.replace(escaped, literal)
    if "\\" in decoded:
        raise _error(f"{context} contains an unsupported TeX path expression")
    return decoded


def _load_claim_rows(csv_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text, newline=""))
    if tuple(reader.fieldnames or ()) != CLAIM_COLUMNS:
        raise _error("Claim matrix columns do not match the exact Phase 4 contract")
    rows: list[dict[str, str]] = []
    for index, raw_row in enumerate(reader, start=1):
        if None in raw_row or any(value is None for value in raw_row.values()):
            raise _error(f"Claim matrix row {index} is malformed")
        row = {key: value for key, value in raw_row.items() if key is not None and value is not None}
        if any(value != value.strip() or not value for value in row.values()):
            raise _error(f"Claim matrix row {index} contains empty or untrimmed fields")
        rows.append(row)

    observed_ids = tuple(row["claim_id"] for row in rows)
    if observed_ids != EXPECTED_CLAIM_IDS:
        raise _error("Claim matrix must contain the exact ordered C01-C20 identifiers")
    for row in rows:
        claim_id = row["claim_id"]
        expected_destination = EXPECTED_CLAIM_DESTINATIONS[claim_id]
        if row["chapter"] != expected_destination:
            raise _error(f"Claim destination drifted for {claim_id}")
        if row["authority_commit"] != CLOSURE_SOURCE_COMMIT:
            raise _error(f"Closure source authority drifted for {claim_id}")

    by_id = {row["claim_id"]: row for row in rows}
    availability = by_id["C03_primary_models_unavailable"]
    if (
        availability["claim_status"] != "model_unavailable"
        or availability["value_or_state"] != "model_unavailable"
        or not all(model in availability["row_filter_or_record"] for model in ("P0", "P1", "A2"))
    ):
        raise _error("P0/P1/A2 must remain explicitly model_unavailable")
    multiplicity = by_id["C14_multiplicity"]
    if multiplicity["value_or_state"] != "A3;B78;C1;D9;E1":
        raise _error("Holm universes drifted in the claim matrix")
    return rows


def _validate_artifact_reference(root: Path, path_text: str, *, context: str) -> str:
    relative = _safe_relative_text(path_text, context=context)
    _leaf_metadata(
        root,
        relative,
        context=context,
        allow_directory=path_text.endswith("/"),
    )
    return relative.as_posix()


def _validate_environment_balance(text: str) -> int:
    stack: list[str] = []
    begin_count = 0
    document_begins = 0
    document_ends = 0
    for match in _ENVIRONMENT_RE.finditer(text):
        kind = match.group("kind")
        name = match.group("name").strip()
        if not name:
            raise _error("LaTeX environment name must not be empty")
        if kind == "begin":
            stack.append(name)
            begin_count += 1
            if name == "document":
                document_begins += 1
            continue
        if name == "document":
            document_ends += 1
        if not stack or stack[-1] != name:
            expected = stack[-1] if stack else "none"
            raise _error(f"Unbalanced LaTeX environment: expected {expected}, got {name}")
        stack.pop()
    if stack:
        raise _error(f"Unclosed LaTeX environment: {stack[-1]}")
    if document_begins != 1 or document_ends != 1:
        raise _error("LaTeX document environment must occur exactly once")
    return begin_count


def _heading_category(title: str) -> str | None:
    plain = _normalize_prose(title)
    if re.search(rf"\b{_LOCALIZED_SUMMARY}\b", plain):
        return "Summary"
    if re.search(r"\babstract\b", plain):
        return "Abstract"
    if (
        re.search(rf"\b{_LOCALIZED_CHAPTER}\s+iii\b", plain)
        or _LOCALIZED_METHODOLOGY_STEM in plain
        or "methodolog" in plain
    ):
        return "III"
    if (
        re.search(rf"\b{_LOCALIZED_CHAPTER}\s+iv\b", plain)
        or _LOCALIZED_RESULTS_STEM in plain
        or "result" in plain
    ):
        return "IV"
    if (
        re.search(rf"\b{_LOCALIZED_CHAPTER}\s+v\b", plain)
        or _LOCALIZED_DISCUSSION_STEM in plain
        or "discussion" in plain
    ):
        return "V"
    return None


def _validate_claim_placement(
    text: str,
    expected_ids: Sequence[str],
) -> tuple[dict[str, int], tuple[str, ...]]:
    occurrences: Counter[str] = Counter(_CLAIM_RE.findall(text))
    observed_set = set(occurrences)
    expected_set = set(expected_ids)
    if observed_set != expected_set:
        missing = sorted(expected_set - observed_set)
        unexpected = sorted(observed_set - expected_set)
        raise _error(
            "Manuscript claim identifiers differ from exact C01-C20: "
            f"missing={missing}, unexpected={unexpected}"
        )
    repeated = sorted(claim_id for claim_id, count in occurrences.items() if count != 1)
    if repeated:
        raise _error(f"Each exact C01-C20 claim identifier must occur exactly once: {repeated}")

    current_chapter: str | None = None
    current_section: str | None = None
    headings_seen: set[str] = set()
    placements: dict[str, set[str]] = {claim_id: set() for claim_id in expected_ids}
    for match in _HEADING_OR_CLAIM_RE.finditer(text):
        heading = match.group("heading")
        if heading is not None:
            title = match.group("title") or ""
            if heading.startswith("chapter"):
                current_chapter = _heading_category(title)
                current_section = None
                if current_chapter is not None:
                    headings_seen.add(current_chapter)
            else:
                plain = _normalize_prose(title)
                current_section = "Conclusion" if "conclusion" in plain else None
                if current_section is not None:
                    headings_seen.add(current_section)
            continue
        claim_id = (match.group("claim") or "").strip()
        if claim_id in placements:
            destination = current_section or current_chapter
            if destination is not None:
                placements[claim_id].add(destination)

    required_headings = {"III", "IV", "V", "Summary", "Abstract", "Conclusion"}
    if headings_seen != required_headings:
        raise _error(
            "Required manuscript divisions drifted: "
            f"missing={sorted(required_headings - headings_seen)}, "
            f"unexpected={sorted(headings_seen - required_headings)}"
        )
    for claim_id, expected_destination in EXPECTED_CLAIM_DESTINATIONS.items():
        if expected_destination not in placements[claim_id]:
            raise _error(f"{claim_id} is not present in {expected_destination}")
    ordered_counts = {claim_id: occurrences[claim_id] for claim_id in expected_ids}
    return ordered_counts, tuple(sorted(headings_seen))


def _validate_labels_references_and_citations(text: str) -> dict[str, int]:
    labels = [value.strip() for value in _LABEL_RE.findall(text)]
    if any(not label for label in labels):
        raise _error("LaTeX labels must not be empty")
    duplicate_labels = sorted(label for label, count in Counter(labels).items() if count > 1)
    if duplicate_labels:
        raise _error(f"Duplicate LaTeX labels: {duplicate_labels}")
    label_set = set(labels)

    references = [
        key.strip()
        for group in _REFERENCE_RE.findall(text)
        for key in group.split(",")
        if key.strip()
    ]
    unresolved_references = sorted(set(references) - label_set)
    if unresolved_references:
        raise _error(f"Unresolved LaTeX references: {unresolved_references}")

    bibliography_keys = [value.strip() for value in _BIBITEM_RE.findall(text)]
    duplicate_bibliography = sorted(
        key for key, count in Counter(bibliography_keys).items() if count > 1
    )
    if duplicate_bibliography:
        raise _error(f"Duplicate bibliography keys: {duplicate_bibliography}")
    citation_keys = [
        key.strip()
        for group in _CITATION_RE.findall(text)
        for key in group.split(",")
        if key.strip() and key.strip() != "*"
    ]
    unresolved_citations = sorted(set(citation_keys) - set(bibliography_keys))
    if unresolved_citations:
        raise _error(f"Unresolved LaTeX citations: {unresolved_citations}")
    return {
        "bibliography_entries": len(bibliography_keys),
        "citations": len(citation_keys),
        "labels": len(labels),
        "references": len(references),
    }


def _window_with_all_patterns(
    text: str,
    *,
    anchor: re.Pattern[str],
    patterns: Sequence[re.Pattern[str]],
    radius_before: int,
    radius_after: int,
) -> bool:
    for match in anchor.finditer(text):
        window = text[
            max(0, match.start() - radius_before) : min(len(text), match.end() + radius_after)
        ]
        if all(pattern.search(window) is not None for pattern in patterns):
            return True
    return False


def _validate_scientific_literals(text: str) -> None:
    plain = _normalize_prose(text)
    input_patterns = (
        re.compile(r"\b45\b.{0,50}\bcsv\b"),
        re.compile(r"\b33\b.{0,50}\bjson\b"),
        re.compile(
            rf"\b(?:1|one|{_LOCALIZED_ONE_ARTICLE}|{_LOCALIZED_ONE_WORD})\b"
            r".{0,50}\byaml\b"
        ),
        re.compile(rf"\b(?:4|four|{_LOCALIZED_FOUR_WORD})\b.{{0,70}}\bdvc\b"),
        re.compile(r"\binputs?\b"),
    )
    if not _window_with_all_patterns(
        plain,
        anchor=re.compile(r"\b83\b"),
        patterns=input_patterns,
        radius_before=80,
        radius_after=420,
    ):
        raise _error("The 83-input CSV/JSON/YAML/DVC breakdown is absent or drifted")

    holm_patterns = tuple(
        re.compile(rf"\b{family.lower()}\s*(?:=|:)?\s*{count}\b")
        for family, count in EXPECTED_HOLM_UNIVERSES.items()
    )
    if not _window_with_all_patterns(
        plain,
        anchor=re.compile(r"\bholm\b"),
        patterns=holm_patterns,
        radius_before=80,
        radius_after=280,
    ):
        raise _error("Holm universes A3/B78/C1/D9/E1 are absent or drifted")

    availability_patterns = (
        re.compile(r"\bp0\b"),
        re.compile(r"\bp1\b"),
        re.compile(r"\ba2\b"),
        re.compile(r"model_unavailable|model unavailable|unavailable|not available"),
    )
    if not _window_with_all_patterns(
        plain,
        anchor=re.compile(r"\bp0\b"),
        patterns=availability_patterns,
        radius_before=40,
        radius_after=260,
    ):
        raise _error("P0/P1/A2 are not jointly and explicitly unavailable")


def _validate_figures(root: Path, tex_path: Path, text: str) -> tuple[str, ...]:
    include_values = [
        _decode_tex_path(value, context="includegraphics path")
        for value in _INCLUDEGRAPHICS_RE.findall(text)
    ]
    basenames = [PurePosixPath(value).name for value in include_values]
    expected_counts = Counter(EXPECTED_FIGURE_PDFS)
    observed_expected_counts = Counter(
        basename for basename in basenames if basename in expected_counts
    )
    if observed_expected_counts != expected_counts:
        raise _error("F01-F08 PDF include names must each occur exactly once")

    for value in include_values:
        include_path = Path(value)
        candidate = include_path if include_path.is_absolute() else tex_path.parent / include_path
        _candidate, relative = _resolve_explicit_input(
            root,
            candidate,
            context="included figure",
        )
        _leaf_metadata(root, relative, context="included figure")
    return EXPECTED_FIGURE_PDFS


def validate_phase4_manuscript(
    *,
    tex: Path,
    claim_matrix: Path,
    repo_root: Path,
    pdf: Path | None = None,
    build_dir_a: Path | None = None,
    build_dir_b: Path | None = None,
) -> dict[str, Any]:
    """Return a deterministic validation record and perform no writes."""

    if (build_dir_a is None) != (build_dir_b is None):
        raise _error("Build A and build B directories must be supplied together")
    root = _validate_repo_root(repo_root)
    tex_text, tex_path = _read_explicit_utf8(root, tex, context="TeX input")
    matrix_text, _matrix_path = _read_explicit_utf8(
        root,
        claim_matrix,
        context="claim matrix input",
    )
    if re.search(r"\\today\b", tex_text):
        raise _error("Dynamic \\today is forbidden")
    active_text = _strip_tex_comments(tex_text)

    rows = _load_claim_rows(matrix_text)
    matrix_artifacts: list[str] = []
    for row in rows:
        matrix_artifacts.append(
            _validate_artifact_reference(
                root,
                row["artifact_path"],
                context=f"claim artifact for {row['claim_id']}",
            )
        )

    tex_artifacts = [
        _decode_tex_path(value, context="artifactpath reference")
        for value in _ARTIFACT_RE.findall(active_text)
    ]
    tex_artifact_set = set(tex_artifacts)
    missing_matrix_references = sorted(set(matrix_artifacts) - tex_artifact_set)
    if missing_matrix_references:
        raise _error("Manuscript does not reference every claim-matrix artifact")
    for path_text in sorted(tex_artifact_set):
        _validate_artifact_reference(root, path_text, context="manuscript artifact")

    claim_occurrences, divisions = _validate_claim_placement(
        active_text,
        EXPECTED_CLAIM_IDS,
    )
    environment_count = _validate_environment_balance(active_text)
    reference_counts = _validate_labels_references_and_citations(active_text)
    _validate_scientific_literals(active_text)

    if CLOSURE_SOURCE_COMMIT not in active_text:
        raise _error("Exact Closure source commit is absent")
    if re.search(rf"(?<![0-9a-f]){R_SYN_COMMIT}(?![0-9a-f])", active_text) is None:
        raise _error("Exact R-SYN publication commit is absent")
    figures = _validate_figures(root, tex_path, active_text)

    pdf_record = (
        _hash_explicit_file(root, pdf, context="compiled PDF")
        if pdf is not None
        else None
    )
    build_evidence = (
        _validate_build_pair(
            root,
            build_dir_a,
            build_dir_b,
            tex_name=tex_path.name,
            stem=tex_path.stem,
        )
        if build_dir_a is not None and build_dir_b is not None
        else None
    )
    result: dict[str, Any] = {
        "artifact_references": {
            "claim_matrix_unique": len(set(matrix_artifacts)),
            "manuscript_unique": len(tex_artifact_set),
        },
        "claim_ids": list(EXPECTED_CLAIM_IDS),
        "claim_occurrences": claim_occurrences,
        "closure_source_commit": CLOSURE_SOURCE_COMMIT,
        "divisions": list(divisions),
        "environment_count": environment_count,
        "figures": list(figures),
        "holm_universes": dict(EXPECTED_HOLM_UNIVERSES),
        "input_breakdown": dict(EXPECTED_INPUT_BREAKDOWN),
        "pdf": pdf_record,
        "r_syn_commit": R_SYN_COMMIT,
        "references": reference_counts,
        "status": "validated",
        "writes_performed": False,
    }
    if build_evidence is not None:
        result["build_evidence"] = build_evidence
    return result


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tex", type=Path, required=True)
    parser.add_argument("--claim-matrix", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--build-dir-a", type=Path)
    parser.add_argument("--build-dir-b", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = validate_phase4_manuscript(
            tex=args.tex,
            claim_matrix=args.claim_matrix,
            repo_root=args.repo_root,
            pdf=args.pdf,
            build_dir_a=args.build_dir_a,
            build_dir_b=args.build_dir_b,
        )
    except ManuscriptValidationError as exc:
        print(
            json.dumps(
                {"error": str(exc), "status": "invalid"},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
