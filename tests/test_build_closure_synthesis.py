from __future__ import annotations

import csv
import io
import inspect
import os
import shutil
import stat
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from src.reporting import build_closure_synthesis as builder
from src.reporting import closure_synthesis_contract as contract_module


ROOT = Path(__file__).resolve().parents[1]


def _contract() -> contract_module.SynthesisContract:
    return contract_module.load_contract(root=ROOT)


def _family_cells(rows: list[dict[str, str]]) -> dict[str, int]:
    cells: dict[str, set[tuple[str, str, str, str]]] = {
        family: set() for family in ("A", "B", "C", "D", "E")
    }
    for row in rows:
        family = row["multiplicity_family"]
        if family:
            cells[family].add(
                (
                    row["model_or_pair"],
                    row["metric"],
                    row["population"],
                    row["estimand"],
                )
            )
    return {family: len(values) for family, values in cells.items()}


def test_final_matrix_preserves_models_hypotheses_and_holm_universes() -> None:
    contract = _contract()
    rows = builder.build_final_closure_rows(contract, root=ROOT)

    assert len(rows) == contract.final_closure_row_count == 130
    assert _family_cells(rows) == {"A": 3, "B": 78, "C": 1, "D": 9, "E": 1}
    assert {hypothesis for hypothesis in contract.required_hypotheses}.issubset(
        {row["hypothesis_id"].split(":", 1)[0] for row in rows}
    )
    for model_id in ("P0", "P1", "A2"):
        assert any(
            model_id in row["model_or_pair"]
            and row["availability_state"] == "model_unavailable"
            for row in rows
        )
    assert all(
        row["estimate"] == "" and row["uncertainty"] == ""
        for row in rows
        if row["availability_state"] in contract.non_estimable_states
    )
    assert rows == sorted(
        rows,
        key=lambda row: (
            row["hypothesis_id"],
            row["metric"],
            row["estimand"],
            row["model_or_pair"],
        ),
    )
    assert {
        "not_applicable",
        "model_unavailable",
        "insufficient_support",
        "descriptive_available",
    }.issubset({row["availability_state"] for row in rows})

    assert any(
        row["hypothesis_id"].startswith("H1:")
        and builder.TROPHIC_PROXY in row["evidence_paths"].split(";")
        for row in rows
    )
    assert any(
        row["hypothesis_id"].startswith("H2:")
        and builder.GENERALIZATION_GAP in row["evidence_paths"].split(";")
        for row in rows
    )
    assert any(
        row["hypothesis_id"].startswith("H3:")
        and builder.FAILURE_REGISTRY in row["evidence_paths"].split(";")
        for row in rows
    )
    assert all(
        row["metric"] == "delta_objective_vs_no_action"
        and row["availability_state"] == "not_applicable"
        and "NET_BENEFIT_ENDPOINT_NOT_REGISTERED" in row["limitation_code"]
        for row in rows
        if row["hypothesis_id"].startswith("H5b:")
    )
    assert not any(row["metric"] == "net_benefit" for row in rows)

    site_transfer = next(
        row for row in rows if row["hypothesis_id"] == "H2:E2:legacy_vs_locked_site_transfer"
    )
    assert site_transfer["availability_state"] == "insufficient_support"
    assert site_transfer["attempted_denominator"] == "1050"
    assert site_transfer["successful_denominator"] == "0"

    degradation = next(
        row for row in rows if row["hypothesis_id"] == "H3:E6:degradation_summary"
    )
    assert degradation["availability_state"] == "model_unavailable"
    assert degradation["attempted_denominator"] == "78"
    assert degradation["successful_denominator"] == "0"

    coverage = next(
        row
        for row in rows
        if row["hypothesis_id"] == "H3:locked_conformal_primary_groups"
    )
    assert coverage["attempted_denominator"] == "30"
    assert coverage["successful_denominator"] == "26"
    assert coverage["estimate"] == "0.8667"


def test_claim_matrix_has_evidence_and_wording_boundaries() -> None:
    contract = _contract()
    rows = builder.build_claim_evidence_rows(contract, root=ROOT)

    assert len(rows) == contract.claim_evidence_row_count == 20
    assert len({row["claim_id"] for row in rows}) == 20
    assert all(row["authority_commit"] == contract.closure_source_commit for row in rows)
    assert all(row["allowed_wording"] and row["forbidden_wording"] for row in rows)
    assert any(row["value_or_state"] == "A3;B78;C1;D9;E1" for row in rows)
    assert any(row["value_or_state"] == "model_unavailable" for row in rows)
    assert {"III", "IV", "V", "Summary", "Abstract", "Conclusion"}.issubset(
        {row["chapter"] for row in rows}
    )
    assert any(row["value_or_state"] == "positive in 15/15" for row in rows)
    assert any(row["value_or_state"] == "15/15" for row in rows)
    assert any(row["denominator"] == "1050" and row["value_or_state"] == "0" for row in rows)
    assert any(row["denominator"] == "78" and row["value_or_state"] == "0" for row in rows)
    assert not any(row["claim_status"] == "confirmatory_available" for row in rows)

    by_id = {row["claim_id"]: row for row in rows}
    assert by_id["C04_brier_observation_weighted"]["value_or_state"] == (
        "h1=B2:mean=0.1554:success_rate=0.184269:evaluable_rate=0.184269|"
        "h2=B2:mean=0.1597:success_rate=0.191176:evaluable_rate=0.191176|"
        "h3=B2:mean=0.1659:success_rate=0.182487:evaluable_rate=0.182487"
    )
    assert by_id["C04_brier_observation_weighted"]["denominator"] == (
        "h1:attempted=22440:successful=4135:evaluable=4135|"
        "h2:attempted=22440:successful=4290:evaluable=4290|"
        "h3:attempted=22440:successful=4095:evaluable=4095"
    )
    assert by_id["C05_pr_auc_observation_weighted"]["value_or_state"] == (
        "h1=A1:mean=0.6105:success_rate=0.141488:evaluable_rate=0.141488|"
        "h2=B2:mean=0.6287:success_rate=0.191176:evaluable_rate=0.191176|"
        "h3=B2:mean=0.6024:success_rate=0.182487:evaluable_rate=0.182487"
    )
    assert by_id["C05_pr_auc_observation_weighted"]["denominator"] == (
        "h1:attempted=22440:successful=3175:evaluable=3175|"
        "h2:attempted=22440:successful=4290:evaluable=4290|"
        "h3:attempted=22440:successful=4095:evaluable=4095"
    )
    assert by_id["C13_uncertainty"]["value_or_state"] == (
        "raw_within=30/30;locked_within=26/30;locked_closer=5/30;"
        "locked_wider=30/30;mean_abs_error_raw=0.015565;"
        "median_abs_error_raw=0.013386;mean_abs_error_locked=0.032271;"
        "median_abs_error_locked=0.030872"
    )
    assert by_id["C13_uncertainty"]["denominator"] == "30 paired primary groups"
    assert "conformal always improves" in by_id["C13_uncertainty"]["forbidden_wording"]
    assert by_id["C16_software"]["value_or_state"].endswith(
        "Python 3.14.7;FastAPI 0.138.1;DVC 3.67.1"
    )


def test_matrix_validators_reject_row_loss_reordering_and_destination_loss() -> None:
    contract = _contract()
    matrix = builder.build_final_closure_rows(contract, root=ROOT)
    claims = builder.build_claim_evidence_rows(contract, root=ROOT)

    with pytest.raises(contract_module.SynthesisContractError, match="exact130"):
        contract_module.validate_final_closure_rows(matrix[:-1], contract)
    reordered = [*matrix]
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(contract_module.SynthesisContractError, match="order"):
        contract_module.validate_final_closure_rows(reordered, contract)
    reordered_claims = [*claims]
    reordered_claims[0], reordered_claims[1] = (
        reordered_claims[1],
        reordered_claims[0],
    )
    with pytest.raises(contract_module.SynthesisContractError, match="order"):
        contract_module.validate_claim_evidence_rows(reordered_claims, contract)
    invented_history = [dict(row) for row in claims]
    invented_history[0]["claim_status"] = "historical_unregistered"
    invented_history[0]["authority_commit"] = "0" * 40
    with pytest.raises(contract_module.SynthesisContractError, match="claim_status"):
        contract_module.validate_claim_evidence_rows(invented_history, contract)
    without_conclusion = [
        {**row, "chapter": "IV"} if row["chapter"] == "Conclusion" else row
        for row in claims
    ]
    with pytest.raises(contract_module.SynthesisContractError, match="destinations"):
        contract_module.validate_claim_evidence_rows(without_conclusion, contract)


def test_final_report_is_substantive_and_maps_every_claim() -> None:
    contract = _contract()
    matrix = builder.build_final_closure_rows(contract, root=ROOT)
    claims = builder.build_claim_evidence_rows(contract, root=ROOT)

    report = builder._report(contract, matrix, claims).decode("utf-8")

    for section in range(1, 11):
        assert f"## {section}." in report
    for experiment in range(1, 11):
        assert f"### E{experiment}" in report
    assert "0/1050" in report
    assert "0/78" in report
    assert "26/30" in report
    assert "raw_within=30/30" in report
    assert "locked_closer=5/30" in report
    assert "locked_wider=30/30" in report
    assert "0.015565/0.013386 for raw" in report
    assert "0.032271/0.030872" in report
    assert "`conformal always improves` is prohibited" in report
    assert "Python 3.14.7, FastAPI 0.138.1, and DVC 3.67.1" in report
    assert "0/9" in report
    assert "A=3, B=78, C=1, D=9, and E=1" in report
    assert "private/mifal_ed_t2/mifal_ed_modelo_tesis_v5.tex" in report
    assert "not_estimable` as a zero effect" in report
    assert "net benefit" in report
    for claim in claims:
        assert claim["claim_id"] in report
    for artifact_id, caption in contract.artifact_captions.items():
        assert f"**{artifact_id}**" in report
        assert caption in report


def test_e8_pairwise_diagnostics_are_exact_and_fail_closed_on_raw_drift() -> None:
    contract = _contract()
    rows = builder._read_allowed_csv(
        contract, ROOT, builder.UNCERTAINTY_LEDGER
    )

    diagnostics = builder._e8_primary_diagnostics(rows)

    assert diagnostics.group_count == 30
    assert (
        diagnostics.raw_within_margin,
        diagnostics.locked_within_margin,
        diagnostics.locked_closer,
        diagnostics.locked_wider,
    ) == (30, 26, 5, 30)
    assert builder._decimal(format(diagnostics.raw_mean_absolute_error, "f"), 6) == "0.015565"
    assert builder._decimal(format(diagnostics.raw_median_absolute_error, "f"), 6) == "0.013386"
    assert builder._decimal(format(diagnostics.locked_mean_absolute_error, "f"), 6) == "0.032271"
    assert builder._decimal(format(diagnostics.locked_median_absolute_error, "f"), 6) == "0.030872"

    drifted = [dict(row) for row in rows]
    raw_primary = next(
        row
        for row in drifted
        if row["model_id"] in {"A0", "A1"}
        and row["interval_version"] == "raw_gaussian"
        and abs(float(row["nominal_coverage"]) - 0.9) <= 1e-12
    )
    raw_primary["absolute_coverage_error"] = "0.060000"
    with pytest.raises(builder.SynthesisBuildError, match="paired diagnostics drifted"):
        builder._e8_primary_diagnostics(drifted)


def test_runtime_versions_are_exact_and_fail_closed_on_dependency_drift() -> None:
    contract = _contract()
    environment = builder._read_allowed_json(contract, ROOT, builder.API_ENVIRONMENT)

    assert builder._validated_runtime_versions(environment) == {
        "python": "3.14.7",
        "fastapi": "0.138.1",
        "dvc": "3.67.1",
    }

    drifted = dict(environment)
    runtime = dict(cast(dict[str, Any], drifted["runtime"]))
    runtime["fastapi"] = "0.0.0"
    drifted["runtime"] = runtime
    with pytest.raises(builder.SynthesisBuildError, match="runtime versions drifted"):
        builder._validated_runtime_versions(drifted)


def _copy_allowed_inputs(tmp_path: Path, contract: contract_module.SynthesisContract) -> None:
    for path_text in contract.allowed_input_paths:
        source = ROOT / path_text
        destination = tmp_path / path_text
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def test_build_payloads_is_exact24_deterministic_and_manifest_last(
    tmp_path: Path,
) -> None:
    contract = _contract()
    _copy_allowed_inputs(tmp_path, contract)
    input_records = []
    for path_text in contract.allowed_input_paths:
        payload = (tmp_path / path_text).read_bytes()
        input_records.append(
            {
                "path": path_text,
                "bytes": len(payload),
                "sha256": contract_module.sha256_bytes(payload),
                "filesystem_mode": 0o644,
            }
        )
    authority = {
        "synthesis_implementation_commit": "1" * 40,
        "allowed_input_records_digest": "2" * 64,
        "allowed_input_records": input_records,
        "h_component_records": [
            {
                "path": builder.authority_locker.BUILDER_PATH,
                "bytes": 123,
                "sha256": "6" * 64,
            }
        ],
    }
    authority_path = tmp_path / contract_module.AUTHORITY_PATH
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    authority_path.write_bytes(contract_module.canonical_json_bytes(authority))

    first = builder.build_payloads(
        contract,
        authority,
        p_syn_commit="3" * 40,
        authority_manifest_sha256="4" * 64,
        root=tmp_path,
    )
    second = builder.build_payloads(
        contract,
        authority,
        p_syn_commit="3" * 40,
        authority_manifest_sha256="4" * 64,
        root=tmp_path,
    )

    relative_order = [
        str(Path(path).relative_to(contract_module.SYNTHESIS_ROOT))
        for path in contract.output_paths
    ]
    assert list(first) == relative_order
    assert first == second
    assert len(first) == 24
    assert list(first)[-1] == "synthesis_bundle_manifest.json"
    manifest = first["synthesis_bundle_manifest.json"]
    assert b"generated_at" not in manifest
    assert b'"manifest_last":true' in manifest
    assert b'"dvc_required":false' in manifest
    decoded_manifest = builder._decode_json(manifest, context="test")
    assert decoded_manifest["p_syn_commit"] == "3" * 40
    assert decoded_manifest["authority_manifest"] == {
        "path": contract_module.AUTHORITY_MANIFEST_PATH.as_posix(),
        "sha256": "4" * 64,
    }
    assert decoded_manifest["captions"] == dict(contract.artifact_captions)
    assert decoded_manifest["script"] == {
        "path": builder.authority_locker.BUILDER_PATH,
        "bytes": 123,
        "sha256": "6" * 64,
    }
    assert decoded_manifest["inputs"] == authority["allowed_input_records"]


def _minimal_payloads(contract: contract_module.SynthesisContract) -> dict[str, bytes]:
    return {
        str(Path(path).relative_to(contract_module.SYNTHESIS_ROOT)): (
            b'{"manifest_last":true}\n'
            if path.endswith("synthesis_bundle_manifest.json")
            else f"payload:{path}\n".encode("utf-8")
        )
        for path in contract.output_paths
    }


def test_publication_is_no_clobber_and_cleans_guard(tmp_path: Path) -> None:
    contract = _contract()
    (tmp_path / "reports/closure_v1").mkdir(parents=True)
    (tmp_path / "tmp").mkdir()
    payloads = _minimal_payloads(contract)

    builder._publish_payloads(payloads, contract, root=tmp_path)

    final_root = tmp_path / contract_module.SYNTHESIS_ROOT
    assert final_root.is_dir()
    assert [
        (final_root / Path(path).relative_to(contract_module.SYNTHESIS_ROOT)).read_bytes()
        for path in contract.output_paths
    ] == list(payloads.values())
    assert not (tmp_path / builder.GUARD_PATH).exists()
    with pytest.raises(builder.SynthesisBuildError, match="clobber"):
        builder._publish_payloads(payloads, contract, root=tmp_path)


def test_publication_rolls_back_owned_namespace_on_mid_bundle_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _contract()
    (tmp_path / "reports/closure_v1").mkdir(parents=True)
    (tmp_path / "tmp").mkdir()
    payloads = _minimal_payloads(contract)
    real_link = os.link
    calls = 0

    def failing_link(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic link failure")
        real_link(*args, **kwargs)

    monkeypatch.setattr(os, "link", failing_link)
    with pytest.raises(OSError, match="synthetic"):
        builder._publish_payloads(payloads, contract, root=tmp_path)

    assert not (tmp_path / contract_module.SYNTHESIS_ROOT).exists()
    assert not (tmp_path / builder.GUARD_PATH).exists()


def _publication_root(tmp_path: Path) -> Path:
    root = tmp_path / "publication"
    (root / "reports/closure_v1").mkdir(parents=True)
    (root / "tmp").mkdir()
    return root


def _fake_authority_bundle(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[
    contract_module.SynthesisContract,
    dict[str, Any],
    dict[str, dict[str, Any]],
]:
    h_records: list[dict[str, Any]] = []
    h_payloads: dict[str, bytes] = {}
    for index, path_text in enumerate(sorted(builder.authority_locker.H_SCOPE)):
        payload = f"H-SYN:{path_text}\n".encode()
        h_payloads[path_text] = payload
        path = root / path_text
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        git_mode = builder.authority_locker.H_GIT_MODES[path_text]
        path.chmod(int(git_mode[-3:], 8))
        h_records.append(
            {
                "path": path_text,
                "bytes": len(payload),
                "sha256": contract_module.sha256_bytes(payload),
                "git_mode": git_mode,
                "git_blob_oid": f"{index + 1:040x}",
                "filesystem_mode": int(git_mode[-3:], 8),
            }
        )
    input_records = [
        {
            "path": "reports/source.csv",
            "role": "source",
            "format": "csv",
            "bytes": 4,
            "sha256": "1" * 64,
            "git_mode": "100644",
            "git_blob_oid": "2" * 40,
            "filesystem_mode": 0o644,
        }
    ]
    outputs = [
        f"reports/closure_v1/11_synthesis/output_{index:02d}.csv"
        for index in range(23)
    ] + ["reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json"]
    fake_contract = cast(
        contract_module.SynthesisContract,
        SimpleNamespace(
            closure_source_commit=builder.authority_locker.SOURCE_COMMIT,
            allowed_input_paths=("reports/source.csv",),
            output_paths=tuple(outputs),
        ),
    )
    state = {
        "synthesis_implementation_commit": "a" * 40,
        "h_components": h_records,
        "allowed_inputs": input_records,
        "allowed_input_paths": list(fake_contract.allowed_input_paths),
        "output_paths": outputs,
        "required_unavailable_models": ["P0", "P1", "A2"],
        "required_hypotheses": ["H1", "H2", "H3", "H4", "H5a", "H5b"],
        "holm_universes": {"A": 3, "B": 78, "C": 1, "D": 9, "E": 1},
        "final_closure_row_count": 130,
        "claim_evidence_row_count": 20,
        "table_row_counts": {
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
        },
    }
    authority = builder.authority_locker._build_authority(state)
    authority_bytes = contract_module.canonical_json_bytes(authority)
    manifest = builder.authority_locker._build_manifest(
        authority_bytes, "a" * 40
    )
    authority_path = root / contract_module.AUTHORITY_PATH
    manifest_path = root / contract_module.AUTHORITY_MANIFEST_PATH
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    authority_path.write_bytes(authority_bytes)
    manifest_path.write_bytes(contract_module.canonical_json_bytes(manifest))
    by_path = {record["path"]: record for record in h_records}
    monkeypatch.setattr(
        builder.authority_locker,
        "_validate_published_h",
        lambda _root, commit: h_records
        if commit == "a" * 40
        else (_ for _ in ()).throw(AssertionError(commit)),
    )
    monkeypatch.setattr(
        builder.authority_locker,
        "_component_record",
        lambda _root, commit, path: by_path[path]
        if commit == "a" * 40
        else (_ for _ in ()).throw(AssertionError(commit)),
    )
    monkeypatch.setattr(
        builder,
        "_git_blob_bytes",
        lambda _root, commit, path, *, expected_mode="100644": h_payloads[path]
        if commit == "a" * 40
        and expected_mode == builder.authority_locker.H_GIT_MODES[path]
        else (_ for _ in ()).throw(AssertionError(commit)),
    )
    monkeypatch.setattr(
        builder,
        "collect_input_records",
        lambda _contract, **_kwargs: input_records,
    )
    return fake_contract, authority, by_path


def test_authority_loader_uses_exact_locker_manifest_and_reconstructs_h(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract, authority, _records = _fake_authority_bundle(tmp_path, monkeypatch)
    observed = builder.validate_authority(
        contract,
        root=tmp_path,
        verify_publication=False,
        verify_remote=False,
    )
    assert observed == authority

    manifest_path = tmp_path / contract_module.AUTHORITY_MANIFEST_PATH
    manifest = dict(builder._decode_json(manifest_path.read_bytes(), context="test"))
    manifest["foreign"] = True
    manifest_path.write_bytes(contract_module.canonical_json_bytes(manifest))
    with pytest.raises(builder.SynthesisBuildError, match="exact locker manifest"):
        builder.validate_authority(
            contract,
            root=tmp_path,
            verify_publication=False,
            verify_remote=False,
        )


def test_authority_loader_rejects_h_drift_hardlinks_and_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract, _authority, records = _fake_authority_bundle(tmp_path, monkeypatch)
    drift_path = tmp_path / next(
        path for path in records if path == "docs/closure_v1/PHASE4_SYNTHESIS_FREEZE.md"
    )
    drift_path.write_bytes(b"foreign H bytes\n")
    with pytest.raises(builder.SynthesisBuildError, match="component binding drifted"):
        builder.validate_authority(
            contract,
            root=tmp_path,
            verify_publication=False,
            verify_remote=False,
        )

    # Restore H, then make the authority itself multi-link.
    drift_path.write_bytes(b"H-SYN:docs/closure_v1/PHASE4_SYNTHESIS_FREEZE.md\n")
    authority_path = tmp_path / contract_module.AUTHORITY_PATH
    os.link(authority_path, tmp_path / "foreign-authority-link")
    with pytest.raises(builder.SynthesisBuildError, match="single-link"):
        builder.validate_authority(
            contract,
            root=tmp_path,
            verify_publication=False,
            verify_remote=False,
        )

    (tmp_path / "foreign-authority-link").unlink()
    manifest_path = tmp_path / contract_module.AUTHORITY_MANIFEST_PATH
    manifest_bytes = manifest_path.read_bytes()
    manifest_path.unlink()
    target = tmp_path / "foreign-manifest"
    target.write_bytes(manifest_bytes)
    manifest_path.symlink_to(target)
    with pytest.raises(builder.SynthesisBuildError, match="not regular"):
        builder.validate_authority(
            contract,
            root=tmp_path,
            verify_publication=False,
            verify_remote=False,
        )


def test_publication_links_manifest_last_and_final_files_are_single_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _contract()
    root = _publication_root(tmp_path)
    payloads = _minimal_payloads(contract)
    observed: list[str] = []
    real_link = os.link

    def record_link(source: str, destination: str, **kwargs: Any) -> None:
        observed.append(destination)
        real_link(source, destination, **kwargs)

    monkeypatch.setattr(os, "link", record_link)
    builder._publish_payloads(payloads, contract, root=root)
    assert len(observed) == 24
    assert observed[-1] == "synthesis_bundle_manifest.json"
    final_root = root / contract_module.SYNTHESIS_ROOT
    for relative in payloads:
        metadata = (final_root / relative).stat()
        assert metadata.st_nlink == 1
        assert stat.S_IMODE(metadata.st_mode) == 0o644
    assert stat.S_IMODE(final_root.stat().st_mode) == 0o755
    assert stat.S_IMODE((final_root / "THESIS_TABLES").stat().st_mode) == 0o755
    assert stat.S_IMODE((final_root / "THESIS_FIGURES").stat().st_mode) == 0o755
    assert not (root / builder.GUARD_PATH.parent).exists()


def test_publication_creates_and_removes_owned_tmp_root_in_fresh_clone(
    tmp_path: Path,
) -> None:
    contract = _contract()
    root = tmp_path / "fresh-publication"
    (root / "reports/closure_v1").mkdir(parents=True)
    assert not (root / "tmp").exists()

    builder._publish_payloads(_minimal_payloads(contract), contract, root=root)

    assert (root / contract_module.SYNTHESIS_ROOT).is_dir()
    assert not (root / "tmp").exists()


def test_fresh_tmp_foreign_entry_is_preserved_and_fails_closed(
    tmp_path: Path,
) -> None:
    contract = _contract()
    root = tmp_path / "fresh-publication"
    (root / "reports/closure_v1").mkdir(parents=True)

    def inject_foreign_entry() -> None:
        (root / "tmp/foreign").write_bytes(b"foreign\n")
        raise builder.SynthesisBuildError("post-link drift")

    with pytest.raises(builder.SynthesisBuildError, match="cleanup failed closed"):
        builder._publish_payloads(
            _minimal_payloads(contract),
            contract,
            root=root,
            postpublish_validator=inject_foreign_entry,
        )

    assert (root / "tmp/foreign").read_bytes() == b"foreign\n"
    assert not (root / contract_module.SYNTHESIS_ROOT).exists()


def test_prepublish_revalidation_failure_leaves_no_r_namespace(
    tmp_path: Path,
) -> None:
    contract = _contract()
    root = _publication_root(tmp_path)
    payloads = _minimal_payloads(contract)

    def reject() -> None:
        assert not (root / contract_module.SYNTHESIS_ROOT).exists()
        raise builder.SynthesisBuildError("snapshot drift")

    with pytest.raises(builder.SynthesisBuildError, match="snapshot drift"):
        builder._publish_payloads(
            payloads, contract, root=root, prepublish_validator=reject
        )
    assert not (root / contract_module.SYNTHESIS_ROOT).exists()
    assert not (root / builder.GUARD_PATH.parent).exists()


def test_postpublish_revalidation_failure_rolls_back_exact24(
    tmp_path: Path,
) -> None:
    contract = _contract()
    root = _publication_root(tmp_path)
    payloads = _minimal_payloads(contract)

    def reject_after_manifest() -> None:
        assert all(
            (root / path_text).is_file() for path_text in contract.output_paths
        )
        raise builder.SynthesisBuildError("post-link snapshot drift")

    with pytest.raises(builder.SynthesisBuildError, match="post-link snapshot drift"):
        builder._publish_payloads(
            payloads,
            contract,
            root=root,
            postpublish_validator=reject_after_manifest,
        )
    assert not (root / contract_module.SYNTHESIS_ROOT).exists()
    assert not (root / builder.GUARD_PATH.parent).exists()


def test_publication_preserves_foreign_replacement_and_never_uses_rmtree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _contract()
    root = _publication_root(tmp_path)
    payloads = _minimal_payloads(contract)
    first_relative = next(iter(payloads))
    real_link = os.link
    replaced = False

    def replace_after_link(source: str, destination: str, **kwargs: Any) -> None:
        nonlocal replaced
        real_link(source, destination, **kwargs)
        if not replaced:
            replaced = True
            destination_fd = kwargs["dst_dir_fd"]
            os.unlink(destination, dir_fd=destination_fd)
            descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
                dir_fd=destination_fd,
            )
            os.write(descriptor, b"foreign\n")
            os.close(descriptor)
            raise OSError("foreign replacement injected")

    monkeypatch.setattr(os, "link", replace_after_link)
    with pytest.raises(builder.SynthesisBuildError, match="cleanup failed closed"):
        builder._publish_payloads(payloads, contract, root=root)
    foreign = root / contract_module.SYNTHESIS_ROOT / first_relative
    assert foreign.read_bytes() == b"foreign\n"
    assert "shutil.rmtree" not in inspect.getsource(builder._publish_payloads)


def test_publication_rejects_symlink_namespace_without_touching_target(
    tmp_path: Path,
) -> None:
    contract = _contract()
    root = _publication_root(tmp_path)
    foreign = tmp_path / "foreign-directory"
    foreign.mkdir()
    final_root = root / contract_module.SYNTHESIS_ROOT
    final_root.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(builder.SynthesisBuildError, match="clobber"):
        builder._publish_payloads(_minimal_payloads(contract), contract, root=root)
    assert final_root.is_symlink()
    assert list(foreign.iterdir()) == []


def test_build_rejects_snapshot_drift_before_calling_publisher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _contract()
    states = [
        {
            "snapshot": "before",
            "head": "3" * 40,
            "manifest_bytes_sha256": "4" * 64,
            "authority": {"synthesis_implementation_commit": "a" * 40},
        },
        {
            "snapshot": "drift",
            "head": "3" * 40,
            "manifest_bytes_sha256": "4" * 64,
            "authority": {"synthesis_implementation_commit": "a" * 40},
        },
    ]
    monkeypatch.setattr(builder, "load_contract", lambda **_kwargs: contract)
    monkeypatch.setattr(
        builder,
        "_capture_prepublication_snapshot",
        lambda *_args, **_kwargs: states.pop(0),
    )
    monkeypatch.setattr(
        builder,
        "build_payloads",
        lambda *_args, **_kwargs: _minimal_payloads(contract),
    )
    monkeypatch.setattr(
        builder,
        "_publish_payloads",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("publisher reached")
        ),
    )
    with pytest.raises(builder.SynthesisBuildError, match="changed while building"):
        builder.build_and_publish(root=tmp_path, verify_remote=False)


def test_build_revalidates_snapshot_after_exact24_links_and_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = _contract()
    root = _publication_root(tmp_path)
    stable = {
        "snapshot": "stable",
        "head": "3" * 40,
        "manifest_bytes_sha256": "4" * 64,
        "authority": {"synthesis_implementation_commit": "a" * 40},
    }
    states = [stable, stable, stable, {**stable, "snapshot": "drift"}]
    allowed_statuses: list[tuple[str, ...]] = []

    def capture(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        allowed_statuses.append(tuple(kwargs.get("allowed_untracked_paths", ())))
        return states.pop(0)

    monkeypatch.setattr(builder, "load_contract", lambda **_kwargs: contract)
    monkeypatch.setattr(builder, "_capture_prepublication_snapshot", capture)
    monkeypatch.setattr(
        builder,
        "build_payloads",
        lambda *_args, **_kwargs: _minimal_payloads(contract),
    )

    with pytest.raises(builder.SynthesisBuildError, match="during R-SYN publication"):
        builder.build_and_publish(root=root, verify_remote=False)

    assert allowed_statuses == [(), (), (), tuple(contract.output_paths)]
    assert not (root / contract_module.SYNTHESIS_ROOT).exists()
    assert not (root / builder.GUARD_PATH.parent).exists()


def test_mode_aware_h_readers_accept_executable_adapter_without_monkeypatch() -> None:
    path_text = "src/data/prepare_commit_artifacts.py"
    physical, record = builder._read_repository_file(
        ROOT, path_text, expected_mode=0o755
    )
    committed = builder._git_blob_bytes(
        ROOT,
        builder.authority_locker.SOURCE_COMMIT,
        path_text,
        expected_mode="100755",
    )

    assert physical
    assert committed
    assert record["filesystem_mode"] == 0o755


def test_allowed_read_rejects_mutate_read_restore_against_p_syn_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path_text = "reports/source.csv"
    path = tmp_path / path_text
    path.parent.mkdir(parents=True)
    original = b"a,b\n1,2\n"
    tampered = b"x,y\n9,8\n"
    assert len(original) == len(tampered)
    path.write_bytes(original)
    path.chmod(0o644)
    original_metadata = path.stat()
    contract = cast(
        contract_module.SynthesisContract,
        SimpleNamespace(allowed_input_paths=(path_text,)),
    )
    token = builder._EXPECTED_INPUT_BINDINGS.set(
        {
            path_text: (
                len(original),
                contract_module.sha256_bytes(original),
                0o644,
            )
        }
    )
    real_read = os.read
    injected = False

    def mutate_read_restore(descriptor: int, byte_count: int) -> bytes:
        nonlocal injected
        if injected:
            return real_read(descriptor, byte_count)
        injected = True
        path.write_bytes(tampered)
        observed = real_read(descriptor, byte_count)
        path.write_bytes(original)
        os.utime(
            path,
            ns=(original_metadata.st_atime_ns, original_metadata.st_mtime_ns),
        )
        return observed

    monkeypatch.setattr(os, "read", mutate_read_restore)
    try:
        with pytest.raises(
            builder.SynthesisBuildError,
            match="changed during read|differ from P-SYN",
        ):
            builder._read_allowed_bytes(contract, tmp_path, path_text)
    finally:
        builder._EXPECTED_INPUT_BINDINGS.reset(token)

    assert path.read_bytes() == original


def test_check_only_before_p_syn_is_non_writing() -> None:
    before = {
        "authority": (ROOT / contract_module.AUTHORITY_PATH).exists(),
        "manifest": (ROOT / contract_module.AUTHORITY_MANIFEST_PATH).exists(),
        "synthesis": (ROOT / contract_module.SYNTHESIS_ROOT).exists(),
    }
    result = builder.check_only(root=ROOT)
    after = {
        "authority": (ROOT / contract_module.AUTHORITY_PATH).exists(),
        "manifest": (ROOT / contract_module.AUTHORITY_MANIFEST_PATH).exists(),
        "synthesis": (ROOT / contract_module.SYNTHESIS_ROOT).exists(),
    }

    assert result["status"] == "ready_for_p_syn"
    assert result["writes_performed"] is False
    assert before == after


SVG_NAMESPACE = {"svg": "http://www.w3.org/2000/svg"}


def _svg_root(payload: bytes) -> ET.Element:
    root = ET.fromstring(payload)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    return root


def _elements_with_class(root: ET.Element, class_name: str) -> list[ET.Element]:
    return [
        element
        for element in root.iter()
        if class_name in element.attrib.get("class", "").split()
    ]


def test_f01_f08_are_deterministic_literal_captioned_data_driven_svgs() -> None:
    contract = _contract()
    matrix_rows = builder.build_final_closure_rows(contract, root=ROOT)
    first = builder._figure_payloads(contract, matrix_rows, root=ROOT)
    second = builder._figure_payloads(contract, matrix_rows, root=ROOT)

    assert first == second
    assert list(first) == [
        "F01_intent_to_predict_funnel.svg",
        "F02_benchmark_metrics.svg",
        "F03_descriptive_deltas.svg",
        "F04_threshold_sensitivity.svg",
        "F05_trophic_heatmap.svg",
        "F06_uncertainty_coverage.svg",
        "F07_hypothesis_verdicts.svg",
        "F08_provenance.svg",
    ]
    for index, payload in enumerate(first.values(), start=1):
        artifact_id = f"F{index:02d}"
        root = _svg_root(payload)
        assert root.attrib["data-artifact-id"] == artifact_id
        title = root.find("svg:title", SVG_NAMESPACE)
        description = root.find("svg:desc", SVG_NAMESPACE)
        assert title is not None
        assert title.text == contract.artifact_captions[artifact_id]
        assert description is not None
        assert description.text is not None
        assert description.text.startswith("Sources: ")
        assert ". Filters: " in description.text

        if index <= 6:
            assert _elements_with_class(root, "axis")
            assert any("data-series" in element.attrib for element in root.iter())
            assert any("data-value" in element.attrib for element in root.iter())


def test_f01_f06_encode_expected_axes_series_values_and_na_states() -> None:
    contract = _contract()
    matrix_rows = builder.build_final_closure_rows(contract, root=ROOT)
    figures = builder._figure_payloads(contract, matrix_rows, root=ROOT)

    f01 = _svg_root(figures["F01_intent_to_predict_funnel.svg"])
    assert "13,464" in " ".join(f01.itertext())
    funnel = _elements_with_class(f01, "funnel-series")
    assert {row.attrib["data-horizon"] for row in funnel} == {"1", "2", "3"}
    assert {row.attrib["data-target-available"] for row in funnel} == {
        "819",
        "827",
        "858",
    }
    unavailable = [
        row
        for row in funnel
        if row.attrib["data-series"] in {"P0", "P1", "A2"}
    ]
    assert len(unavailable) == 9
    assert all(row.attrib["data-value"] == "N/A" for row in unavailable)
    assert all(row.attrib["data-attempted"] == "4488" for row in funnel)

    f02 = _svg_root(figures["F02_benchmark_metrics.svg"])
    metric_values = _elements_with_class(f02, "metric-value")
    assert {row.attrib["data-metric"] for row in metric_values} == {
        "pr_auc",
        "brier",
        "f2",
    }
    assert {row.attrib["data-estimand"] for row in metric_values} == {
        "observation_weighted",
        "site_weighted",
    }
    availability_bars = _elements_with_class(f02, "availability-bar")
    assert len(availability_bars) == 11 * 3 * 2 * 3
    assert len(
        {
            (
                row.attrib["data-model"],
                row.attrib["data-horizon"],
                row.attrib["data-estimand"],
                row.attrib["data-metric"],
            )
            for row in availability_bars
        }
    ) == 198
    assert {
        row.attrib["data-model"]
        for row in availability_bars
        if row.attrib["data-state"] == "unavailable"
    } == {"P0", "P1", "A2"}
    assert all(
        {
            "data-attempted",
            "data-successful",
            "data-evaluable",
            "data-success-rate",
            "data-evaluable-rate",
            "data-terminal-status",
            "data-value",
        }.issubset(row.attrib)
        for row in availability_bars
    )
    quantitative_rates = {
        row.attrib["data-evaluable-rate"] for row in availability_bars
    }
    assert "0.000000" in quantitative_rates
    assert any(0 < float(rate) < 1 for rate in quantitative_rates)
    assert len({row.attrib["height"] for row in availability_bars}) > 2
    b2_brier_h1 = next(
        row
        for row in availability_bars
        if row.attrib["data-model"] == "B2"
        and row.attrib["data-horizon"] == "1"
        and row.attrib["data-estimand"] == "observation_weighted"
        and row.attrib["data-metric"] == "brier"
    )
    assert (
        b2_brier_h1.attrib["data-attempted"],
        b2_brier_h1.attrib["data-successful"],
        b2_brier_h1.attrib["data-evaluable"],
        b2_brier_h1.attrib["data-success-rate"],
        b2_brier_h1.attrib["data-evaluable-rate"],
    ) == ("22440", "4135", "4135", "0.184269", "0.184269")
    assert all(
        row.attrib["data-attempted"] == "0"
        and row.attrib["data-successful"] == "0"
        and row.attrib["data-evaluable"] == "0"
        and row.attrib["data-terminal-status"] == "not_attempted_no_slots"
        for row in availability_bars
        if row.attrib["data-model"] == "A2"
    )

    f03 = _svg_root(figures["F03_descriptive_deltas.svg"])
    deltas = _elements_with_class(f03, "delta-value")
    assert {row.attrib["data-series"] for row in deltas} == {
        "F1-F0",
        "A1-A0",
    }
    assert not _elements_with_class(f03, "errorbar")

    f04 = _svg_root(figures["F04_threshold_sensitivity.svg"])
    threshold_values = _elements_with_class(f04, "threshold-value")
    rank_values = _elements_with_class(f04, "rank-value")
    assert {row.attrib["data-cutoff"] for row in threshold_values} == {
        "25",
        "30",
        "33",
        "50",
    }
    assert len(threshold_values) == 12
    assert len(rank_values) == 36

    f05 = _svg_root(figures["F05_trophic_heatmap.svg"])
    heatmap = _elements_with_class(f05, "heatmap-value")
    assert len(heatmap) == 120
    assert {row.attrib["data-series"] for row in heatmap} == {"B1", "B2"}
    assert {row.attrib["data-reference"] for row in heatmap} == {
        "future_chla_operational_proxy",
        "tsi_tp_h",
        "tsi_sd_h",
        "tsi_non_chla_h",
        "tsi_all_h",
    }

    f06 = _svg_root(figures["F06_uncertainty_coverage.svg"])
    uncertainty = _elements_with_class(f06, "uncertainty-value")
    assert len(uncertainty) == 36
    assert {row.attrib["data-series"] for row in uncertainty} == {
        "raw_gaussian",
        "locked_conformal",
    }
    assert len(_elements_with_class(f06, "h3-marker")) == 12
    assert {
        row.attrib["data-value"]
        for row in _elements_with_class(f06, "nominal-line")
    } == {"0.9000"}


def test_f07_uses_non_binary_states_and_f08_binds_json_provenance() -> None:
    contract = _contract()
    matrix_rows = builder.build_final_closure_rows(contract, root=ROOT)
    figures = builder._figure_payloads(contract, matrix_rows, root=ROOT)

    f07 = _svg_root(figures["F07_hypothesis_verdicts.svg"])
    states = _elements_with_class(f07, "hypothesis-state")
    assert len(states) == 6
    assert {row.attrib["data-state"] for row in states} == {
        "limited_descriptive_support",
        "partial_descriptive_only",
        "not_estimable",
        "not_scientifically_confirmed",
    }
    f07_text = " ".join(f07.itertext()).lower()
    assert "positive" not in f07_text
    assert "negative" not in f07_text
    h1_state = next(
        row for row in states if row.attrib["data-hypothesis"] == "H1"
    )
    assert h1_state.attrib["data-direct-anfis-row-count"] == "15"
    assert h1_state.attrib["data-direct-anfis-available-count"] == "9"
    assert h1_state.attrib["data-direct-anfis-unavailable-count"] == "6"
    assert h1_state.attrib["data-auxiliary-b1-b2-row-count"] == "13"
    assert h1_state.attrib["data-estimable-row-count"] == "9"
    assert h1_state.attrib["data-total-descriptive-row-count"] == "22"
    assert "Direct ANFIS: 9/15" in " ".join(f07.itertext())
    assert "auxiliary B1/B2 context: 13; does not validate ANFIS" in " ".join(
        f07.itertext()
    )

    primary_h1 = next(
        row
        for row in matrix_rows
        if row["hypothesis_id"] == "H1:H1_P1_vs_P0"
    )
    assert primary_h1["limitation_code"] == (
        "P0_AND_P1_MODEL_UNAVAILABLE_NO_PRIMARY_ARCHITECTURE_COMPARISON"
    )
    auxiliary_h1 = [
        row
        for row in matrix_rows
        if row["hypothesis_id"].startswith("H1:B2_vs_B1:")
    ]
    assert len(auxiliary_h1) == 13
    assert all(
        "DOES_NOT_VALIDATE_THE_PRIMARY_ANFIS_BRANCH" in row["limitation_code"]
        for row in auxiliary_h1
    )

    f08 = _svg_root(figures["F08_provenance.svg"])
    nodes = _elements_with_class(f08, "provenance-node")
    assert [row.attrib["data-stage"] for row in nodes] == [
        "R",
        "H1",
        "P1",
        "U1",
        "H2",
        "P2",
        "U2",
        "H3",
        "P3",
        "U3",
        "H4",
        "F",
    ]
    by_stage = {row.attrib["data-stage"]: row for row in nodes}
    assert by_stage["U1"].attrib["data-state"] == "recorded failure"
    assert by_stage["U2"].attrib["data-state"] == "recorded failure"
    assert by_stage["U3"].attrib["data-state"] == "only successful attempt"
    assert by_stage["U3"].attrib["data-identity"] == builder.PHASE3_U3_COMMIT
    assert by_stage["H4"].attrib["data-identity"] == builder.PHASE3_H4_COMMIT
    assert "structured final hardening" not in figures[
        "F08_provenance.svg"
    ].decode("utf-8")
    assert by_stage["F"].attrib["data-identity"] == contract.closure_source_commit
    assert builder.authority_locker._git(
        ROOT,
        "rev-list",
        "--parents",
        "-n",
        "1",
        builder.PHASE3_U3_COMMIT,
    ).split() == [
        builder.PHASE3_U3_COMMIT,
        by_stage["P3"].attrib["data-identity"],
    ]
    assert builder.authority_locker._git(
        ROOT,
        "rev-list",
        "--parents",
        "-n",
        "1",
        builder.PHASE3_H4_COMMIT,
    ).split() == [builder.PHASE3_H4_COMMIT, builder.PHASE3_U3_COMMIT]
    assert builder.authority_locker._git(
        ROOT,
        "rev-list",
        "--parents",
        "-n",
        "1",
        contract.closure_source_commit,
    ).split() == [contract.closure_source_commit, builder.PHASE3_H4_COMMIT]


def test_f07_f08_fail_closed_on_auxiliary_or_provenance_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    matrix_rows = builder.build_final_closure_rows(contract, root=ROOT)
    altered_rows = [dict(row) for row in matrix_rows]
    auxiliary = next(
        row
        for row in altered_rows
        if row["hypothesis_id"].startswith("H1:B2_vs_B1:")
    )
    auxiliary["limitation_code"] = ""
    with pytest.raises(builder.SynthesisBuildError, match="partition drifted"):
        builder._figure_f07_hypothesis_verdicts(contract, altered_rows)

    with monkeypatch.context() as scoped:
        scoped.setattr(builder, "PHASE3_U3_COMMIT", "0" * 40)
        with pytest.raises(builder.SynthesisBuildError, match="identity drifted"):
            builder._figure_f08_provenance(contract, root=ROOT)
    with monkeypatch.context() as scoped:
        scoped.setattr(builder, "PHASE3_H4_COMMIT", "1" * 40)
        with pytest.raises(builder.SynthesisBuildError, match="identity drifted"):
            builder._figure_f08_provenance(contract, root=ROOT)


def test_figure_readers_are_closed_to_allowlisted_csv_and_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    matrix_rows = builder.build_final_closure_rows(contract, root=ROOT)
    observed: list[str] = []
    real_csv = builder._read_allowed_csv
    real_json = builder._read_allowed_json

    def read_csv(*args: Any, **kwargs: Any) -> Any:
        path_text = args[2]
        observed.append(path_text)
        return real_csv(*args, **kwargs)

    def read_json(*args: Any, **kwargs: Any) -> Any:
        path_text = args[2]
        observed.append(path_text)
        return real_json(*args, **kwargs)

    monkeypatch.setattr(builder, "_read_allowed_csv", read_csv)
    monkeypatch.setattr(builder, "_read_allowed_json", read_json)
    builder._figure_payloads(contract, matrix_rows, root=ROOT)

    assert observed
    assert set(observed).issubset(set(contract.allowed_input_paths))
    assert all(Path(path).suffix in {".csv", ".json"} for path in observed)
    assert all(not path.startswith(("private/", "data/targets/")) for path in observed)
    assert all(not path.endswith(".parquet") for path in observed)


def test_f04_svg_changes_when_allowlisted_prevalence_value_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    original = builder._figure_f04_threshold_sensitivity(contract, root=ROOT)
    real_csv = builder._read_allowed_csv

    def changed_csv(*args: Any, **kwargs: Any) -> Any:
        rows = real_csv(*args, **kwargs)
        if args[2] == builder.THRESHOLD_PREVALENCE:
            rows = [dict(row) for row in rows]
            rows[0]["positive_rate"] = "0.1234"
        return rows

    monkeypatch.setattr(builder, "_read_allowed_csv", changed_csv)
    changed = builder._figure_f04_threshold_sensitivity(contract, root=ROOT)

    assert changed != original
    root = _svg_root(changed)
    assert any(
        row.attrib.get("data-value") == "0.1234"
        for row in _elements_with_class(root, "threshold-value")
    )


def _decode_typed_table(payload: bytes) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8"), newline=""))
    assert reader.fieldnames is not None
    rows = [cast(dict[str, str], dict(row)) for row in reader]
    return list(reader.fieldnames), rows


@pytest.fixture(scope="module")
def typed_tables() -> dict[str, tuple[list[str], list[dict[str, str]]]]:
    contract = _contract()
    payloads = builder._table_payloads(contract, ROOT, ())
    return {name: _decode_typed_table(payload) for name, payload in payloads.items()}


def test_t01_t12_are_typed_and_match_frozen_row_counts(
    typed_tables: dict[str, tuple[list[str], list[dict[str, str]]]],
) -> None:
    contract = _contract()
    expected_names = [
        "T01_model_experiment_availability.csv",
        "T02_intent_to_predict_funnel.csv",
        "T03_dual_benchmark.csv",
        "T04_descriptive_deltas.csv",
        "T05_site_transfer.csv",
        "T06_threshold_sensitivity.csv",
        "T07_trophic_performance.csv",
        "T08_multiplicity_ledger.csv",
        "T09_anfis_ablation.csv",
        "T10_uncertainty.csv",
        "T11_e6_e9_unavailability.csv",
        "T12_software_evidence.csv",
    ]
    assert list(typed_tables) == expected_names
    for index, name in enumerate(expected_names, start=1):
        columns, rows = typed_tables[name]
        table_id = f"T{index:02d}"
        assert len(rows) == contract.table_row_counts[table_id]
        assert columns
        assert len(columns) == len(set(columns))
        assert "record_json" not in columns
        assert all(set(row) == set(columns) for row in rows)
        assert all(None not in row and None not in row.values() for row in rows)


def test_t01_t03_preserve_exact_model_horizon_and_estimand_grids(
    typed_tables: dict[str, tuple[list[str], list[dict[str, str]]]],
) -> None:
    models = {"B0", "B1", "B2", "F0", "F1", "P0", "P1", "M0", "A0", "A1", "A2"}
    unavailable = {"P0", "P1", "A2"}

    t01 = typed_tables["T01_model_experiment_availability.csv"][1]
    assert {(row["model_id"], row["experiment_id"]) for row in t01} == {
        (model_id, f"E{experiment}")
        for model_id in models
        for experiment in range(1, 10)
    }
    t01_by_cell = {
        (row["model_id"], row["experiment_id"]): row for row in t01
    }
    assert all(
        any(
            t01_by_cell[(model_id, f"E{experiment}")]["availability_state"]
            == "model_unavailable"
            for experiment in range(1, 10)
        )
        for model_id in unavailable
    )
    assert t01_by_cell[("A2", "E2")]["availability_state"] == "not_applicable"
    assert t01_by_cell[("P0", "E6")]["availability_state"] == "not_applicable"
    assert t01_by_cell[("P1", "E6")]["availability_state"] == "model_unavailable"
    assert t01_by_cell[("P1", "E9")]["availability_state"] == "model_unavailable"
    assert t01_by_cell[("A2", "E9")]["availability_state"] == "not_applicable"
    assert {
        row["availability_reason"]
        for row in t01
        if row["experiment_id"] == "E2"
        and row["availability_state"] == "descriptive_available"
    } == {
        "internal_holdout_descriptive_available_but_legacy_gap_"
        "insufficient_support_0_of_1050"
    }
    assert {
        row["availability_reason"]
        for row in t01
        if row["experiment_id"] == "E7"
        and row["availability_state"] == "descriptive_available"
    } == {
        "pairwise_ablation_descriptive_available_but_learning_curve_and_"
        "membership_diagnostics_insufficient_0_of_4"
    }
    assert {
        row["model_id"]
        for row in t01
        if row["experiment_id"] == "E4"
        and row["availability_state"] == "descriptive_available"
    } == {"B1", "B2"}

    t02 = typed_tables["T02_intent_to_predict_funnel.csv"][1]
    assert {(row["model_id"], row["horizon_months"]) for row in t02} == {
        (model_id, str(horizon))
        for model_id in models
        for horizon in (1, 2, 3)
    }
    assert {row["attempted_origin_count"] for row in t02} == {"4488"}
    assert {row["target_available_origin_count"] for row in t02} == {
        "819",
        "827",
        "858",
    }
    assert all(
        row["availability_state"] == "model_unavailable"
        and row["input_target_intersection_min"] == ""
        and row["successful_origin_count_min"] == ""
        and row["failed_origin_count_min"] == "4488"
        for row in t02
        if row["model_id"] in unavailable
    )
    assert all(
        row["availability_state"] == "descriptive_available"
        and row["successful_origin_count_min"] != ""
        for row in t02
        if row["model_id"] not in unavailable
    )

    t03 = typed_tables["T03_dual_benchmark.csv"][1]
    assert {
        (
            row["model_id"],
            row["horizon_months"],
            row["estimand"],
            row["metric"],
        )
        for row in t03
    } == {
        (model_id, str(horizon), estimand, metric)
        for model_id in models
        for horizon in (1, 2, 3)
        for estimand in ("observation_weighted", "site_weighted")
        for metric in ("pr_auc", "brier", "f2")
    }
    assert {
        (row["estimand"], row["source_estimand"]) for row in t03
    } == {
        ("observation_weighted", "observation_weighted"),
        ("site_weighted", "site_weighted"),
    }
    assert all(
        row["availability_state"] == "model_unavailable"
        and row["value_mean"] == ""
        and row["attempted_origin_count"] == ""
        for row in t03
        if row["model_id"] in unavailable
    )


def test_t04_t07_preserve_descriptive_cells_and_nla_boundary(
    typed_tables: dict[str, tuple[list[str], list[dict[str, str]]]],
) -> None:
    t04 = typed_tables["T04_descriptive_deltas.csv"][1]
    assert Counter(row["comparison_id"] for row in t04) == {
        "F1_vs_F0": 15,
        "A1_vs_A0": 9,
    }
    assert all(row["uncertainty"] == "" for row in t04)
    assert all(
        row["metric"] == "absolute_error"
        for row in t04
        if row["comparison_id"] == "F1_vs_F0"
    )
    assert Counter(
        row["metric"] for row in t04 if row["comparison_id"] == "A1_vs_A0"
    ) == {"delta_pr_auc": 3, "delta_brier": 3, "delta_mae": 3}

    t05 = typed_tables["T05_site_transfer.csv"][1]
    assert {row["model_id"] for row in t05} == {
        "B0",
        "B1",
        "B2",
        "F0",
        "F1",
        "P0",
        "P1",
        "M0",
        "A0",
        "A1",
        "A2",
    }
    a2 = next(row for row in t05 if row["model_id"] == "A2")
    assert a2["availability_state"] == "model_unavailable"
    assert a2["internal_metric_row_count"] == "0"
    assert a2["generalization_gap_estimable_count"] == "0"
    assert all(row["generalization_gap_estimable_count"] == "0" for row in t05)

    t06 = typed_tables["T06_threshold_sensitivity.csv"][1]
    assert Counter(row["record_type"] for row in t06) == {
        "threshold_prevalence": 12,
        "rank_stability": 36,
    }
    assert {
        row["threshold_ug_l"]
        for row in t06
        if row["record_type"] == "threshold_prevalence"
    } == {"25", "30", "33", "50"}

    t07 = typed_tables["T07_trophic_performance.csv"][1]
    assert Counter(row["record_type"] for row in t07) == {
        "ordinal_performance": 30,
        "nla_semantic_sentinel": 1,
    }
    ordinal = [row for row in t07 if row["record_type"] == "ordinal_performance"]
    assert {
        (row["reference"], row["model_id"], row["horizon_months"])
        for row in ordinal
    } == {
        (reference, model_id, str(horizon))
        for reference in (
            "future_chla_operational_proxy",
            "tsi_tp_h",
            "tsi_sd_h",
            "tsi_non_chla_h",
            "tsi_all_h",
        )
        for model_id in ("B1", "B2")
        for horizon in (1, 2, 3)
    }
    sentinel = next(
        row for row in t07 if row["record_type"] == "nla_semantic_sentinel"
    )
    assert sentinel["availability_state"] == "not_applicable"
    assert sentinel["macro_f1_mean"] == ""
    assert "does_not_validate_monthly_WQP_targets" in sentinel["limitation"]


def test_t08_t11_preserve_holm_and_non_estimability_without_fake_zero_effects(
    typed_tables: dict[str, tuple[list[str], list[dict[str, str]]]],
) -> None:
    contract = _contract()
    t08 = typed_tables["T08_multiplicity_ledger.csv"][1]
    assert Counter(row["multiplicity_family"] for row in t08) == dict(
        contract.holm_universes
    )
    assert len({row["cell_id"] for row in t08}) == 92
    assert all(row["holm_universe_retained"] == "true" for row in t08)
    assert all(row["availability_reason"] for row in t08)
    assert all(row["raw_p_value"] == row["holm_p_value"] == "" for row in t08)
    family_b = [row for row in t08 if row["multiplicity_family"] == "B"]
    assert {row["horizon_months"] for row in family_b} == {"1", "2", "3"}
    assert {row["endpoint"] for row in family_b} == {"bloom_h", "irc_alert_h"}

    t09 = typed_tables["T09_anfis_ablation.csv"][1]
    assert Counter(row["record_type"] for row in t09) == {
        "A1_vs_A0": 3,
        "learning_curve_sentinel": 3,
        "membership_stability_sentinel": 1,
    }
    assert all(
        row["saturation_claim_authorized"] == "false"
        for row in t09
        if row["record_type"] == "learning_curve_sentinel"
    )
    assert all(
        row["availability_state"] == "insufficient_support"
        for row in t09
        if row["record_type"] != "A1_vs_A0"
    )
    assert next(
        row
        for row in t09
        if row["record_type"] == "membership_stability_sentinel"
    )["membership_stability_claim_authorized"] == "false"

    t10 = typed_tables["T10_uncertainty.csv"][1]
    assert {
        (
            row["model_id"],
            row["interval_version"],
            row["horizon_months"],
            row["nominal_coverage"],
        )
        for row in t10
    } == {
        (model_id, version, str(horizon), nominal)
        for model_id in ("A0", "A1")
        for version in ("raw_gaussian", "locked_conformal")
        for horizon in (1, 2, 3)
        for nominal in ("0.8000", "0.9000", "0.9500")
    }
    assert all(row["seed_row_count"] == "5" for row in t10)

    t11 = typed_tables["T11_e6_e9_unavailability.csv"][1]
    assert Counter(row["experiment_id"] for row in t11) == {"E6": 78, "E9": 9}
    assert all(row["availability_state"] == "model_unavailable" for row in t11)
    assert all(
        row[field] == ""
        for row in t11
        for field in ("estimate", "ci95_lower", "ci95_upper", "p_value")
    )


def test_t12_is_five_typed_software_records_with_restricted_paths_closed(
    typed_tables: dict[str, tuple[list[str], list[dict[str, str]]]],
) -> None:
    t12 = typed_tables["T12_software_evidence.csv"][1]
    assert {row["evidence_id"] for row in t12} == {
        "runtime_environment",
        "openapi_contract",
        "public_tests",
        "synthetic_e2e",
        "restricted_path_safety",
    }
    public = next(row for row in t12 if row["evidence_id"] == "public_tests")
    assert (public["test_count"], public["pass_count"], public["skip_count"]) == (
        "347",
        "338",
        "9",
    )
    openapi = next(row for row in t12 if row["evidence_id"] == "openapi_contract")
    assert (
        openapi["path_count"],
        openapi["operation_count"],
        openapi["documented_operation_count"],
    ) == ("69", "83", "38")
    runtime = next(row for row in t12 if row["evidence_id"] == "runtime_environment")
    assert "python=3.14.7" in runtime["detail"]
    assert "fastapi=0.138.1" in runtime["detail"]
    assert "dvc=3.67.1" in runtime["detail"]
    restricted = next(
        row for row in t12 if row["evidence_id"] == "restricted_path_safety"
    )
    assert restricted["status"] == "passed"
    assert restricted["source_artifact_count"] == "6"
    assert {
        restricted["outcome_paths_opened"],
        restricted["target_paths_opened"],
        restricted["private_full_opened"],
    } == {"false"}


def test_table_readers_are_closed_to_allowlisted_csv_and_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    observed: list[str] = []
    real_csv = builder._read_allowed_csv
    real_json = builder._read_allowed_json

    def read_csv(*args: Any, **kwargs: Any) -> Any:
        observed.append(args[2])
        return real_csv(*args, **kwargs)

    def read_json(*args: Any, **kwargs: Any) -> Any:
        observed.append(args[2])
        return real_json(*args, **kwargs)

    monkeypatch.setattr(builder, "_read_allowed_csv", read_csv)
    monkeypatch.setattr(builder, "_read_allowed_json", read_json)
    builder._table_payloads(contract, ROOT, ())

    assert observed
    assert set(observed).issubset(set(contract.allowed_input_paths))
    assert all(Path(path).suffix in {".csv", ".json"} for path in observed)
    assert all(not path.startswith(("private/", "data/targets/")) for path in observed)
    assert all(not path.endswith(".parquet") for path in observed)
