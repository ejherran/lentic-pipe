from __future__ import annotations

import csv
import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from src.reporting import validate_phase4_manuscript as validator


@dataclass
class ManuscriptFixture:
    root: Path
    tex: Path
    claim_matrix: Path


def _write_claim_matrix(root: Path) -> Path:
    artifact_root = root / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    matrix_path = root / "claims" / "THESIS_CLAIM_EVIDENCE_MATRIX.csv"
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    with matrix_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=validator.CLAIM_COLUMNS)
        writer.writeheader()
        for index, claim_id in enumerate(validator.EXPECTED_CLAIM_IDS, start=1):
            artifact_path = f"artifacts/{claim_id}.csv"
            (root / artifact_path).write_text("value\n1\n", encoding="utf-8")
            row = {
                "claim_id": claim_id,
                "chapter": validator.EXPECTED_CLAIM_DESTINATIONS[claim_id],
                "section": "Phase 4",
                "claim_text": f"Claim {index}",
                "claim_status": "descriptive_available",
                "artifact_path": artifact_path,
                "row_filter_or_record": "exact row",
                "metric": "state",
                "value_or_state": "available",
                "denominator": "1",
                "authority_commit": validator.CLOSURE_SOURCE_COMMIT,
                "limitation": "Bounded interpretation.",
                "allowed_wording": "bounded",
                "forbidden_wording": "universal",
            }
            if claim_id == "C03_primary_models_unavailable":
                row.update(
                    {
                        "claim_status": "model_unavailable",
                        "row_filter_or_record": "model_id in P0,P1,A2",
                        "value_or_state": "model_unavailable",
                        "denominator": "3 models",
                    }
                )
            elif claim_id == "C14_multiplicity":
                row.update(
                    {
                        "value_or_state": "A3;B78;C1;D9;E1",
                        "denominator": "92 cells",
                    }
                )
            writer.writerow(row)
    return matrix_path


def _claim_commands(start: int, stop: int) -> str:
    return "\n".join(
        rf"\claimid{{{claim_id}}}"
        for claim_id in validator.EXPECTED_CLAIM_IDS[start:stop]
    )


def _write_tex(root: Path) -> Path:
    tex_root = root / "manuscript"
    figure_root = tex_root / "closure_v1_figures"
    figure_root.mkdir(parents=True, exist_ok=True)
    for figure_name in validator.EXPECTED_FIGURE_PDFS:
        (figure_root / figure_name).write_bytes(b"phase-4-figure\n")

    artifact_commands = "\n".join(
        rf"\artifactpath{{artifacts/{claim_id}.csv}}"
        for claim_id in validator.EXPECTED_CLAIM_IDS
    )
    figure_commands = "\n".join(
        rf"\includegraphics{{closure_v1_figures/{figure_name}}}"
        for figure_name in validator.EXPECTED_FIGURE_PDFS
    )
    tex = rf"""\documentclass{{book}}
\newcommand{{\claimid}}[1]{{#1}}
\newcommand{{\artifactpath}}[1]{{#1}}
\begin{{document}}
\chapter*{{Resumen}}
\claimid{{C18_summary_boundary}}
\chapter*{{Abstract}}
\claimid{{C19_abstract_boundary}}
\chapter{{Chapter III: Methodology}}
\label{{sec:iii}}
\ref{{sec:iii}}
{_claim_commands(0, 2)}
\chapter{{Chapter IV: Results}}
{_claim_commands(2, 16)}
\begin{{itemize}}
\item P0, P1, and A2 remained \texttt{{model\_unavailable}}.
\end{{itemize}}
The Holm universes are A=3, B=78, C=1, D=9, and E=1.
The synthesis used 83 total inputs: 45 CSV, 33 JSON, one YAML, and four DVC pointers.
{artifact_commands}
{figure_commands}
\chapter{{Chapter V: Discussion}}
\claimid{{C17_global_verdict_discussion}}
\section{{General Conclusion}}
\claimid{{C20_conclusion_boundary}}
The source authority is {validator.CLOSURE_SOURCE_COMMIT}, and R-SYN was published at {validator.R_SYN_COMMIT}.
The literature reference is resolved \cite{{Reference2026}}.
\begin{{thebibliography}}{{1}}
\bibitem{{Reference2026}} Reference. (2026). Title.
\end{{thebibliography}}
\end{{document}}
"""
    tex_path = tex_root / "thesis.tex"
    tex_path.write_text(tex, encoding="utf-8")
    return tex_path


def _write_build_directory(
    root: Path,
    tex_path: Path,
    name: str,
    pdf_payload: bytes,
) -> Path:
    build_dir = root / name
    build_dir.mkdir(parents=True)
    stem = tex_path.stem
    for suffix in validator.BUILD_OUTPUT_SUFFIXES:
        (build_dir / f"{stem}{suffix}").write_bytes(b"placeholder\n")

    relative_inputs = (
        tex_path.name,
        *validator.EXPECTED_LISTING_INPUTS,
        *(
            f"closure_v1_figures/{figure_name}"
            for figure_name in validator.EXPECTED_FIGURE_PDFS
        ),
    )
    fls_lines = [
        f"PWD {validator.EXPECTED_FLS_WORKING_DIRECTORY}",
        "INPUT /usr/local/texlive/2026/texmf.cnf",
        *(f"INPUT {value}" for value in relative_inputs),
        *(f"INPUT /build/{stem}{suffix}" for suffix in validator.FLS_BUILD_INPUT_SUFFIXES),
        *(f"OUTPUT /build/{stem}{suffix}" for suffix in validator.FLS_OUTPUT_SUFFIXES),
    ]
    (build_dir / f"{stem}.fls").write_text(
        "\n".join(fls_lines) + "\n",
        encoding="utf-8",
    )
    (build_dir / f"{stem}.log").write_text(
        "This is a final deterministic build.\n"
        "Package rerunfilecheck Info: File has not changed.\n"
        "LaTeX Font Warning: A font shape was undefined and substituted.\n"
        f"Output written on /build/{stem}.pdf "
        f"({validator.EXPECTED_BUILD_PDF_PAGES} pages, {len(pdf_payload)} bytes).\n",
        encoding="utf-8",
    )
    (build_dir / f"{stem}.pdf").write_bytes(pdf_payload)
    return build_dir


def _write_build_pair(
    fixture: ManuscriptFixture,
    monkeypatch: pytest.MonkeyPatch,
    *,
    parent: Path | None = None,
) -> tuple[Path, Path, bytes]:
    pdf_payload = b"%PDF-1.7\ndeterministic-phase-4\n%%EOF\n"
    monkeypatch.setattr(validator, "EXPECTED_BUILD_PDF_BYTES", len(pdf_payload))
    monkeypatch.setattr(
        validator,
        "EXPECTED_BUILD_PDF_SHA256",
        hashlib.sha256(pdf_payload).hexdigest(),
    )
    build_root = parent if parent is not None else fixture.root
    return (
        _write_build_directory(build_root, fixture.tex, "build_a", pdf_payload),
        _write_build_directory(build_root, fixture.tex, "build_b", pdf_payload),
        pdf_payload,
    )


@pytest.fixture
def manuscript_fixture(tmp_path: Path) -> ManuscriptFixture:
    return ManuscriptFixture(
        root=tmp_path,
        tex=_write_tex(tmp_path),
        claim_matrix=_write_claim_matrix(tmp_path),
    )


def _validate(
    fixture: ManuscriptFixture,
    *,
    pdf: Path | None = None,
    build_dir_a: Path | None = None,
    build_dir_b: Path | None = None,
) -> dict[str, object]:
    return validator.validate_phase4_manuscript(
        tex=fixture.tex,
        claim_matrix=fixture.claim_matrix,
        repo_root=fixture.root,
        pdf=pdf,
        build_dir_a=build_dir_a,
        build_dir_b=build_dir_b,
    )


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _tree_payloads(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def test_valid_temp_manuscript_is_deterministic_and_read_only(
    manuscript_fixture: ManuscriptFixture,
) -> None:
    before = _tree_payloads(manuscript_fixture.root)

    first = _validate(manuscript_fixture)
    second = _validate(manuscript_fixture)

    assert first == second
    assert first["status"] == "validated"
    assert first["writes_performed"] is False
    assert first["claim_ids"] == list(validator.EXPECTED_CLAIM_IDS)
    assert first["figures"] == list(validator.EXPECTED_FIGURE_PDFS)
    assert first["input_breakdown"] == dict(validator.EXPECTED_INPUT_BREAKDOWN)
    assert first["holm_universes"] == dict(validator.EXPECTED_HOLM_UNIVERSES)
    assert first["pdf"] is None
    assert "build_evidence" not in first
    assert _tree_payloads(manuscript_fixture.root) == before


def test_cli_prints_only_deterministic_json_to_stdout(
    manuscript_fixture: ManuscriptFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = [
        "--tex",
        manuscript_fixture.tex.relative_to(manuscript_fixture.root).as_posix(),
        "--claim-matrix",
        manuscript_fixture.claim_matrix.relative_to(manuscript_fixture.root).as_posix(),
        "--repo-root",
        str(manuscript_fixture.root),
    ]
    assert validator.main(arguments) == 0
    first = capsys.readouterr()
    assert first.err == ""
    decoded = json.loads(first.out)
    assert decoded["status"] == "validated"
    assert "timestamp" not in first.out.lower()

    assert validator.main(arguments) == 0
    second = capsys.readouterr()
    assert second.err == ""
    assert second.out == first.out


@pytest.mark.parametrize(
    ("old", "new", "match"),
    [
        (
            r"\claimid{C20_conclusion_boundary}",
            r"\claimid{C20_conclusion_drift}",
            "exact C01-C20",
        ),
        (
            r"\claimid{C20_conclusion_boundary}",
            "\\claimid{C20_conclusion_boundary}\n\\claimid{C20_conclusion_boundary}",
            "exactly once",
        ),
        ("Chapter IV: Results", "Findings", "Required manuscript divisions"),
        ("45 CSV", "44 CSV", "83-input"),
        ("B=78", "B=77", "Holm universes"),
        (
            r"P0, P1, and A2 remained \texttt{model\_unavailable}",
            "P0, P1, and A2 were available",
            "explicitly unavailable",
        ),
        (
            validator.CLOSURE_SOURCE_COMMIT,
            validator.CLOSURE_SOURCE_COMMIT[:-1] + "0",
            "Closure source commit",
        ),
        (validator.R_SYN_COMMIT, "0000000", "R-SYN publication commit"),
        (r"\end{itemize}", r"\end{enumerate}", "Unbalanced LaTeX environment"),
        (
            "F08_provenance.pdf",
            "F08_provenance_drift.pdf",
            "F01-F08 PDF include names",
        ),
    ],
)
def test_adversarial_manuscript_literal_and_structure_drift_fails_closed(
    manuscript_fixture: ManuscriptFixture,
    old: str,
    new: str,
    match: str,
) -> None:
    _replace(manuscript_fixture.tex, old, new)
    with pytest.raises(validator.ManuscriptValidationError, match=match):
        _validate(manuscript_fixture)


def test_today_duplicate_label_unresolved_ref_and_cite_fail_closed(
    manuscript_fixture: ManuscriptFixture,
) -> None:
    _replace(manuscript_fixture.tex, r"\begin{document}", "\\begin{document}\n\\today")
    with pytest.raises(validator.ManuscriptValidationError, match="today"):
        _validate(manuscript_fixture)

    manuscript_fixture.tex = _write_tex(manuscript_fixture.root)
    _replace(manuscript_fixture.tex, r"\ref{sec:iii}", r"\label{sec:iii}")
    with pytest.raises(validator.ManuscriptValidationError, match="Duplicate LaTeX labels"):
        _validate(manuscript_fixture)

    manuscript_fixture.tex = _write_tex(manuscript_fixture.root)
    _replace(manuscript_fixture.tex, r"\ref{sec:iii}", r"\ref{sec:absent}")
    with pytest.raises(validator.ManuscriptValidationError, match="Unresolved LaTeX references"):
        _validate(manuscript_fixture)

    manuscript_fixture.tex = _write_tex(manuscript_fixture.root)
    _replace(manuscript_fixture.tex, r"\cite{Reference2026}", r"\cite{Missing2026}")
    with pytest.raises(validator.ManuscriptValidationError, match="Unresolved LaTeX citations"):
        _validate(manuscript_fixture)


def test_claim_matrix_drift_and_missing_artifact_fail_closed(
    manuscript_fixture: ManuscriptFixture,
) -> None:
    _replace(
        manuscript_fixture.claim_matrix,
        "C14_multiplicity,IV,",
        "C14_multiplicity,V,",
    )
    with pytest.raises(validator.ManuscriptValidationError, match="destination drifted"):
        _validate(manuscript_fixture)

    manuscript_fixture.claim_matrix = _write_claim_matrix(manuscript_fixture.root)
    missing = manuscript_fixture.root / "artifacts" / "C01_holdout_population.csv"
    missing.unlink()
    with pytest.raises(validator.ManuscriptValidationError, match="does not exist"):
        _validate(manuscript_fixture)


def test_pdf_returns_only_bytes_and_sha_and_rejects_links(
    manuscript_fixture: ManuscriptFixture,
) -> None:
    pdf = manuscript_fixture.root / "manuscript" / "compiled.pdf"
    payload = b"%PDF-1.7\nphase-4\n%%EOF\n"
    pdf.write_bytes(payload)

    result = _validate(manuscript_fixture, pdf=pdf)

    assert result["pdf"] == {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    encoded = json.dumps(result, sort_keys=True)
    assert str(pdf) not in encoded
    pdf_record = result["pdf"]
    assert isinstance(pdf_record, dict)
    assert "content" not in pdf_record
    assert "path" not in pdf_record

    hardlink = pdf.with_name("compiled-hardlink.pdf")
    os.link(pdf, hardlink)
    with pytest.raises(validator.ManuscriptValidationError, match="single-link"):
        _validate(manuscript_fixture, pdf=pdf)

    hardlink.unlink()
    symlink = pdf.with_name("compiled-symlink.pdf")
    symlink.symlink_to(pdf.name)
    with pytest.raises(validator.ManuscriptValidationError, match="symlink"):
        _validate(manuscript_fixture, pdf=symlink)


@pytest.mark.parametrize(
    "forbidden_relative",
    [
        "private/FULL.md",
        "data/targets/monthly.csv",
        "reports/closure_v1/outcomes.csv",
        "data/closure_v1/raw_payload.parquet",
    ],
)
def test_forbidden_explicit_tex_inputs_are_rejected_before_leaf_access(
    manuscript_fixture: ManuscriptFixture,
    forbidden_relative: str,
) -> None:
    forbidden = manuscript_fixture.root / forbidden_relative
    forbidden.parent.mkdir(parents=True, exist_ok=True)
    forbidden.write_text("must not be opened", encoding="utf-8")

    with pytest.raises(validator.ManuscriptValidationError, match="read boundary"):
        validator.validate_phase4_manuscript(
            tex=Path(forbidden_relative),
            claim_matrix=manuscript_fixture.claim_matrix,
            repo_root=manuscript_fixture.root,
        )


def test_cli_invalid_result_is_json_and_contains_no_input_path(
    manuscript_fixture: ManuscriptFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _replace(manuscript_fixture.tex, "45 CSV", "44 CSV")
    exit_code = validator.main(
        [
            "--tex",
            str(manuscript_fixture.tex),
            "--claim-matrix",
            str(manuscript_fixture.claim_matrix),
            "--repo-root",
            str(manuscript_fixture.root),
        ]
    )
    output = capsys.readouterr()

    assert exit_code == 1
    assert output.err == ""
    assert json.loads(output.out)["status"] == "invalid"
    assert str(manuscript_fixture.root) not in output.out


def test_build_pair_evidence_is_deterministic_bounded_and_path_free(
    manuscript_fixture: ManuscriptFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_a, build_b, pdf_payload = _write_build_pair(
        manuscript_fixture,
        monkeypatch,
    )
    before = _tree_payloads(manuscript_fixture.root)

    first = _validate(
        manuscript_fixture,
        build_dir_a=build_a.relative_to(manuscript_fixture.root),
        build_dir_b=build_b.relative_to(manuscript_fixture.root),
    )
    second = _validate(
        manuscript_fixture,
        build_dir_a=build_a,
        build_dir_b=build_b,
    )

    assert first == second
    evidence = cast(Mapping[str, object], first["build_evidence"])
    assert evidence["pdf_byte_identical"] is True
    assert evidence["expected_output_file_count"] == 6
    for build_key in ("build_a", "build_b"):
        build = cast(Mapping[str, object], evidence[build_key])
        assert build["output_file_count"] == 6
        assert build["pdf"] == {
            "bytes": len(pdf_payload),
            "sha256": hashlib.sha256(pdf_payload).hexdigest(),
        }
        fls = cast(Mapping[str, object], build["fls"])
        assert fls["input_record_count"] == 16
        assert fls["relative_input_unique_count"] == 12
        assert fls["output_record_count"] == 5
        log = cast(Mapping[str, object], build["log"])
        assert log["page_count"] == validator.EXPECTED_BUILD_PDF_PAGES
        assert log["latex_error_count"] == 0
        assert log["undefined_reference_or_citation_count"] == 0
        assert log["duplicate_destination_count"] == 0
        assert log["rerun_request_count"] == 0
        assert log["overfull_count"] == 0
    encoded = json.dumps(first, sort_keys=True)
    assert str(build_a) not in encoded
    assert str(build_b) not in encoded
    assert "content" not in encoded
    assert _tree_payloads(manuscript_fixture.root) == before


def test_build_pair_cli_accepts_explicit_relative_directories(
    manuscript_fixture: ManuscriptFixture,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_a, build_b, _payload = _write_build_pair(
        manuscript_fixture,
        monkeypatch,
    )
    exit_code = validator.main(
        [
            "--tex",
            manuscript_fixture.tex.relative_to(manuscript_fixture.root).as_posix(),
            "--claim-matrix",
            manuscript_fixture.claim_matrix.relative_to(
                manuscript_fixture.root
            ).as_posix(),
            "--repo-root",
            str(manuscript_fixture.root),
            "--build-dir-a",
            build_a.relative_to(manuscript_fixture.root).as_posix(),
            "--build-dir-b",
            build_b.relative_to(manuscript_fixture.root).as_posix(),
        ]
    )
    output = capsys.readouterr()

    assert exit_code == 0
    assert output.err == ""
    decoded = json.loads(output.out)
    assert decoded["build_evidence"]["pdf_byte_identical"] is True
    assert str(manuscript_fixture.root) not in output.out


def test_absolute_build_directories_may_be_outside_repo_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    fixture = ManuscriptFixture(
        root=repo_root,
        tex=_write_tex(repo_root),
        claim_matrix=_write_claim_matrix(repo_root),
    )
    build_a, build_b, _payload = _write_build_pair(
        fixture,
        monkeypatch,
        parent=tmp_path,
    )

    result = _validate(
        fixture,
        build_dir_a=build_a,
        build_dir_b=build_b,
    )

    assert result["status"] == "validated"
    assert "build_evidence" in result


def test_build_directories_are_pair_required_and_distinct(
    manuscript_fixture: ManuscriptFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_a, build_b, _payload = _write_build_pair(
        manuscript_fixture,
        monkeypatch,
    )
    with pytest.raises(validator.ManuscriptValidationError, match="supplied together"):
        _validate(manuscript_fixture, build_dir_a=build_a)
    with pytest.raises(validator.ManuscriptValidationError, match="distinct directories"):
        _validate(
            manuscript_fixture,
            build_dir_a=build_b,
            build_dir_b=build_b,
        )


def test_build_directory_rejects_leaf_and_ancestor_symlinks(
    manuscript_fixture: ManuscriptFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_a, build_b, _payload = _write_build_pair(
        manuscript_fixture,
        monkeypatch,
    )
    leaf_link = manuscript_fixture.root / "build_leaf_link"
    leaf_link.symlink_to(build_a.name, target_is_directory=True)
    with pytest.raises(validator.ManuscriptValidationError, match="symlinks"):
        _validate(
            manuscript_fixture,
            build_dir_a=leaf_link.relative_to(manuscript_fixture.root),
            build_dir_b=build_b,
        )

    real_parent = manuscript_fixture.root / "real_parent"
    real_parent.mkdir()
    nested_build = _write_build_directory(
        real_parent,
        manuscript_fixture.tex,
        "nested_build",
        _payload,
    )
    ancestor_link = manuscript_fixture.root / "ancestor_link"
    ancestor_link.symlink_to(real_parent.name, target_is_directory=True)
    relative_nested = ancestor_link.relative_to(manuscript_fixture.root) / nested_build.name
    with pytest.raises(validator.ManuscriptValidationError, match="symlinks"):
        _validate(
            manuscript_fixture,
            build_dir_a=relative_nested,
            build_dir_b=build_b,
        )
    with pytest.raises(validator.ManuscriptValidationError, match="symlinks"):
        _validate(
            manuscript_fixture,
            build_dir_a=manuscript_fixture.root / relative_nested,
            build_dir_b=build_b,
        )


def test_build_directory_rejects_extra_missing_and_hardlinked_outputs(
    manuscript_fixture: ManuscriptFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_a, build_b, _payload = _write_build_pair(
        manuscript_fixture,
        monkeypatch,
    )
    extra = build_a / "unexpected.tmp"
    extra.write_text("unexpected\n", encoding="utf-8")
    with pytest.raises(validator.ManuscriptValidationError, match="exact six"):
        _validate(manuscript_fixture, build_dir_a=build_a, build_dir_b=build_b)
    extra.unlink()

    aux = build_a / f"{manuscript_fixture.tex.stem}.aux"
    aux.unlink()
    with pytest.raises(validator.ManuscriptValidationError, match="exact six"):
        _validate(manuscript_fixture, build_dir_a=build_a, build_dir_b=build_b)
    aux.write_bytes(b"placeholder\n")

    outside_link = manuscript_fixture.root / "aux-hardlink"
    os.link(aux, outside_link)
    with pytest.raises(validator.ManuscriptValidationError, match="single-link"):
        _validate(manuscript_fixture, build_dir_a=build_a, build_dir_b=build_b)


@pytest.mark.parametrize(
    "diagnostic",
    [
        "! Undefined control sequence.",
        "Emergency stop.",
        "Fatal error occurred, no output PDF file produced.",
        "LaTeX Warning: Reference `missing' on page 1 undefined on input line 1.",
        "LaTeX Warning: There were undefined citations.",
        "pdfTeX warning: destination with the same identifier duplicate ignored.",
        "LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right.",
        r"Overfull \hbox (1.0pt too wide) in paragraph at lines 1--2",
    ],
)
def test_final_log_forbidden_diagnostics_fail_closed(
    manuscript_fixture: ManuscriptFixture,
    monkeypatch: pytest.MonkeyPatch,
    diagnostic: str,
) -> None:
    build_a, build_b, _payload = _write_build_pair(
        manuscript_fixture,
        monkeypatch,
    )
    log = build_a / f"{manuscript_fixture.tex.stem}.log"
    log.write_text(diagnostic + "\n" + log.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(validator.ManuscriptValidationError, match="forbidden diagnostic"):
        _validate(manuscript_fixture, build_dir_a=build_a, build_dir_b=build_b)


def test_final_log_exact_page_and_byte_record_is_required(
    manuscript_fixture: ManuscriptFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_a, build_b, _payload = _write_build_pair(
        manuscript_fixture,
        monkeypatch,
    )
    log = build_a / f"{manuscript_fixture.tex.stem}.log"
    _replace(log, "80 pages", "79 pages")

    with pytest.raises(validator.ManuscriptValidationError, match="page or byte count"):
        _validate(manuscript_fixture, build_dir_a=build_a, build_dir_b=build_b)


@pytest.mark.parametrize(
    ("old", "new", "match"),
    [
        (
            f"PWD {validator.EXPECTED_FLS_WORKING_DIRECTORY}",
            "PWD /workspace/other",
            "exact sealed value",
        ),
        (
            "INPUT /usr/local/texlive/2026/texmf.cnf",
            "INPUT /usr/local/texlive/2026/texmf.cnf\nINPUT /etc/passwd",
            "escaped the allowed absolute input roots",
        ),
        (
            "INPUT /usr/local/texlive/2026/texmf.cnf",
            "INPUT /usr/local/texlive/2026/texmf.cnf\nINPUT raw_payload.parquet",
            "read boundary",
        ),
        (
            "INPUT demo_mifal_ed_v5.py\n",
            "",
            "relative inputs differ",
        ),
        (
            "OUTPUT /build/thesis.pdf",
            "OUTPUT /build/thesis.pdf\nOUTPUT /build/unexpected.pdf",
            "outputs differ",
        ),
    ],
)
def test_fls_allowlist_and_working_directory_drift_fail_closed(
    manuscript_fixture: ManuscriptFixture,
    monkeypatch: pytest.MonkeyPatch,
    old: str,
    new: str,
    match: str,
) -> None:
    build_a, build_b, _payload = _write_build_pair(
        manuscript_fixture,
        monkeypatch,
    )
    fls = build_a / f"{manuscript_fixture.tex.stem}.fls"
    _replace(fls, old, new)

    with pytest.raises(validator.ManuscriptValidationError, match=match):
        _validate(manuscript_fixture, build_dir_a=build_a, build_dir_b=build_b)


def test_build_pdf_must_match_sealed_identity_and_other_build(
    manuscript_fixture: ManuscriptFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_a, build_b, _payload = _write_build_pair(
        manuscript_fixture,
        monkeypatch,
    )
    (build_b / f"{manuscript_fixture.tex.stem}.pdf").write_bytes(b"drifted")

    with pytest.raises(validator.ManuscriptValidationError, match="PDF identity drifted"):
        _validate(manuscript_fixture, build_dir_a=build_a, build_dir_b=build_b)
