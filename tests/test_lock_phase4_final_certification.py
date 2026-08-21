from __future__ import annotations

import copy
import errno
import fcntl
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from src.experiments import lock_phase4_final_certification as locker
from src.reporting import phase4_final_certification_contract as certification


def _run(root: Path, *args: str) -> str:
    result = subprocess.run(
        list(args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write(root: Path, relative: str, payload: str, *, mode: int = 0o644) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    path.chmod(mode)


def _contract(
    *,
    closure_source: str,
    r_syn: str,
    editorial: str,
    h1_cert_commit: str | None = None,
    p1_cert_commit: str | None = None,
    h2_cert_commit: str | None = None,
    p2_cert_commit: str | None = None,
    h3_cert_commit: str | None = None,
    p3_cert_commit: str | None = None,
    h4_cert_commit: str | None = None,
    p4_cert_commit: str | None = None,
    h5_cert_commit: str | None = None,
    p5_cert_commit: str | None = None,
    h6_cert_commit: str | None = None,
    p6_cert_commit: str | None = None,
    suite_status: str = "locked",
) -> SimpleNamespace:
    positive = certification.POSITIVE_TEST_PATHS
    skipped = certification.EXACT_SKIPPED_NODES
    supplemental = tuple(
        node
        for node in skipped
        if node.split("::", 1)[0] not in set(positive)
    )
    selectors = positive + supplemental
    suite = SimpleNamespace(
        suite_kind="closure_phase4_final_public",
        positive_test_paths=positive,
        exact_skipped_nodes=skipped,
        exact_skip_reason=certification.EXACT_SKIP_REASON,
        e2e_nodes=certification.E2E_NODES,
        command_template=certification.TEST_COMMAND_TEMPLATE,
        static_commands=certification.STATIC_COMMANDS,
        status=suite_status,
        selector_count=(
            certification.LOCKED_SUITE_SELECTOR_COUNT
            if suite_status == certification.LOCKED_SUITE_STATUS
            else None
        ),
        collected_test_count=(
            certification.LOCKED_SUITE_COLLECTED_TEST_COUNT
            if suite_status == certification.LOCKED_SUITE_STATUS
            else None
        ),
        nodeids_sha256=(
            certification.LOCKED_SUITE_NODEIDS_SHA256
            if suite_status == certification.LOCKED_SUITE_STATUS
            else None
        ),
        allowed_skip_count=certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT,
        selectors=selectors,
    )
    return SimpleNamespace(
        closure_source_commit=closure_source,
        r_syn_commit=r_syn,
        editorial_commit=editorial,
        h1_cert_commit=h1_cert_commit or locker.H1_CERT_COMMIT,
        p1_cert_commit=p1_cert_commit or locker.P1_CERT_COMMIT,
        h2_cert_commit=h2_cert_commit or locker.H2_CERT_COMMIT,
        p2_cert_commit=p2_cert_commit or locker.P2_CERT_COMMIT,
        h3_cert_commit=h3_cert_commit or locker.H3_CERT_COMMIT,
        p3_cert_commit=p3_cert_commit or locker.P3_CERT_COMMIT,
        h4_cert_commit=h4_cert_commit or locker.H4_CERT_COMMIT,
        p4_cert_commit=p4_cert_commit or locker.P4_CERT_COMMIT,
        h5_cert_commit=h5_cert_commit or locker.H5_CERT_COMMIT,
        p5_cert_commit=p5_cert_commit or locker.P5_CERT_COMMIT,
        h6_cert_commit=h6_cert_commit or locker.H6_CERT_COMMIT,
        p6_cert_commit=p6_cert_commit or locker.P6_CERT_COMMIT,
        final_tag="thesis-closure-v1",
        h1_scope=tuple(),
        p1_scope=tuple(),
        h2_scope=tuple(),
        p2_scope=tuple(),
        h3_scope=tuple(),
        p3_scope=tuple(),
        h4_scope=tuple(),
        p4_scope=tuple(),
        h5_scope=tuple(),
        p5_scope=tuple(),
        h6_scope=tuple(),
        p6_scope=tuple(),
        h_scope=tuple(),
        p_scope=tuple(),
        r_scope=tuple(),
        anchor_inputs=certification.ANCHOR_INPUTS,
        anchor_input_paths=tuple(spec.path for spec in certification.ANCHOR_INPUTS),
        dvc_pointers=certification.DVC_POINTERS,
        dvc_pointer_paths=tuple(spec.path for spec in certification.DVC_POINTERS),
        post_restore_status_pointer_paths=tuple(
            spec.path for spec in certification.DVC_POINTERS
        ),
        post_verification_status_pointer_paths=tuple(
            spec.path for spec in certification.DVC_POINTERS
        ),
        partial_clone_global_status_authorized=False,
        test_suite=suite,
        output_paths=tuple(locker.R_SCOPE),
    )


def _anchor_records() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "role": certification.ANCHOR_INPUTS[index].role,
            "bytes": index + 10,
            "sha256": f"{index + 101:064x}",
            "git_mode": "100644",
            "git_blob_oid": f"{index + 201:040x}",
            "repository_commit": locker.EDITORIAL_COMMIT,
        }
        for index, path in enumerate(locker.ANCHOR_PATHS)
    ]


def _pointer_records() -> list[dict[str, Any]]:
    return [
        {
            "path": spec.path,
            "role": spec.role,
            "output_path": spec.output_path,
            "payload_md5": spec.md5,
            "payload_bytes": spec.size,
            "bytes": index + 20,
            "sha256": f"{index + 301:064x}",
            "git_mode": "100644",
            "git_blob_oid": f"{index + 401:040x}",
            "repository_commit": locker.EDITORIAL_COMMIT,
            "parquet_payload_opened": False,
        }
        for index, spec in enumerate(certification.DVC_POINTERS)
    ]


def _historical_records() -> tuple[
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
    def records(
        paths: Mapping[str, str], offset: int, *, physical_mode: bool = False
    ) -> list[dict[str, Any]]:
        return [
            {
                "path": path,
                "bytes": index + offset,
                "sha256": f"{index + offset:064x}",
                "git_mode": locker.H_GIT_MODES.get(path, "100644"),
                "git_blob_oid": f"{index + offset:040x}",
                **(
                    {"filesystem_mode": int(locker.H_GIT_MODES[path][-3:], 8)}
                    if physical_mode
                    else {}
                ),
            }
            for index, path in enumerate(paths)
        ]

    p5_records = records(locker.P5_SCOPE, 1401)
    for record in p5_records:
        if record["path"] == locker.H5_AUTHORITY_PATH.as_posix():
            record["bytes"] = locker.H5_AUTHORITY_BYTES
            record["sha256"] = locker.H5_AUTHORITY_SHA256
        else:
            record["bytes"] = locker.H5_MANIFEST_BYTES
            record["sha256"] = locker.H5_MANIFEST_SHA256
    p6_records = records(locker.P6_SCOPE, 1601)
    for record in p6_records:
        if record["path"] == locker.H6_AUTHORITY_PATH.as_posix():
            record["bytes"] = locker.H6_AUTHORITY_BYTES
            record["sha256"] = locker.H6_AUTHORITY_SHA256
        else:
            record["bytes"] = locker.H6_MANIFEST_BYTES
            record["sha256"] = locker.H6_MANIFEST_SHA256
    return (
        records(locker.H1_SCOPE, 501),
        records(locker.P1_SCOPE, 601),
        records(locker.H2_SCOPE, 701, physical_mode=True),
        records(locker.P2_SCOPE, 801),
        records(locker.H3_SCOPE, 901, physical_mode=True),
        records(locker.P3_SCOPE, 1001),
        records(locker.H4_SCOPE, 1101, physical_mode=True),
        records(locker.P4_SCOPE, 1201),
        records(locker.H5_SCOPE, 1301, physical_mode=True),
        p5_records,
        records(locker.H6_SCOPE, 1501, physical_mode=True),
        p6_records,
    )


def _install_contract_stubs(
    monkeypatch: pytest.MonkeyPatch,
    contract: SimpleNamespace,
) -> None:
    def load_contract(**kwargs: Any) -> SimpleNamespace:
        if (
            kwargs.get("allow_pending_suite", False) is False
            and contract.test_suite.status != "locked"
        ):
            raise certification.FinalCertificationContractError(
                "Final certification suite lock remains pending"
            )
        return contract

    monkeypatch.setattr(certification, "load_contract", load_contract)
    monkeypatch.setattr(
        certification,
        "expected_h_scope",
        lambda: dict(locker.H_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_h1_scope",
        lambda: dict(locker.H1_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_p1_scope",
        lambda: dict(locker.P1_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_h2_scope",
        lambda: dict(locker.H2_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_p2_scope",
        lambda: dict(locker.P2_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_h3_scope",
        lambda: dict(locker.H3_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_p3_scope",
        lambda: dict(locker.P3_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_h4_scope",
        lambda: dict(locker.H4_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_p4_scope",
        lambda: dict(locker.P4_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_h5_scope",
        lambda: dict(locker.H5_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_p5_scope",
        lambda: dict(locker.P5_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_h6_scope",
        lambda: dict(locker.H6_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_p6_scope",
        lambda: dict(locker.P6_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_p_scope",
        lambda: dict(locker.P_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_r_scope",
        lambda: dict(locker.R_SCOPE),
    )
    monkeypatch.setattr(
        certification,
        "expected_h_modes",
        lambda: dict(locker.H_GIT_MODES),
    )
    monkeypatch.setattr(
        certification,
        "expected_p_modes",
        lambda: {path: "100644" for path in locker.P_SCOPE},
    )
    monkeypatch.setattr(
        certification,
        "expected_h2_modes",
        lambda: dict(locker.H_GIT_MODES),
    )
    monkeypatch.setattr(
        certification,
        "expected_p2_modes",
        lambda: {path: "100644" for path in locker.P2_SCOPE},
    )
    monkeypatch.setattr(
        certification,
        "expected_h4_modes",
        lambda: dict(locker.H_GIT_MODES),
    )
    monkeypatch.setattr(
        certification,
        "expected_p4_modes",
        lambda: {path: "100644" for path in locker.P4_SCOPE},
    )
    monkeypatch.setattr(
        certification,
        "expected_h5_modes",
        lambda: dict(locker.H_GIT_MODES),
        raising=False,
    )
    monkeypatch.setattr(
        certification,
        "expected_p5_modes",
        lambda: {path: "100644" for path in locker.P5_SCOPE},
        raising=False,
    )
    monkeypatch.setattr(
        certification,
        "expected_h6_modes",
        lambda: dict(locker.H_GIT_MODES),
        raising=False,
    )
    monkeypatch.setattr(
        certification,
        "expected_p6_modes",
        lambda: {path: "100644" for path in locker.P6_SCOPE},
        raising=False,
    )
    monkeypatch.setattr(
        certification,
        "expected_r_modes",
        lambda: {path: "100644" for path in locker.R_SCOPE},
    )
    monkeypatch.setattr(
        certification,
        "collect_anchor_input_records",
        lambda _contract, **_kwargs: _anchor_records(),
    )
    monkeypatch.setattr(
        certification,
        "collect_dvc_pointer_records",
        lambda _contract, **_kwargs: _pointer_records(),
    )
    monkeypatch.setattr(
        certification,
        "_historical_h1_p1_h2_p2_h3_p3_h4_p4_h5_p5_h6_p6_records",
        lambda _contract, **_kwargs: _historical_records(),
    )


def _make_repository(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
]:
    root = tmp_path / "work"
    remote = tmp_path / "origin.git"
    root.mkdir()
    _run(root, "git", "init", "--initial-branch=main")
    _run(root, "git", "config", "user.name", "Certification Test")
    _run(root, "git", "config", "user.email", "cert@example.invalid")
    _write(root, ".gitignore", "tmp/\n")
    for path_text, kind in locker.H1_SCOPE.items():
        if kind == "M":
            _write(
                root,
                path_text,
                f"base:{path_text}\n",
                mode=int(locker.H_GIT_MODES[path_text][-3:], 8),
            )
    _write(root, "closure_source.txt", "closure\n")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "closure source")
    closure_source = _run(root, "git", "rev-parse", "HEAD")

    _write(root, "r_syn.txt", "r-syn\n")
    _run(root, "git", "add", "r_syn.txt")
    _run(root, "git", "commit", "-m", "R-SYN")
    r_syn = _run(root, "git", "rev-parse", "HEAD")

    _write(root, "editorial.txt", "editorial\n")
    _run(root, "git", "add", "editorial.txt")
    _run(root, "git", "commit", "-m", "editorial")
    editorial = _run(root, "git", "rev-parse", "HEAD")

    for path_text, kind in locker.H1_SCOPE.items():
        mode = int(locker.H_GIT_MODES[path_text][-3:], 8)
        if kind == "A":
            _write(root, path_text, f"H-CERT1:{path_text}\n", mode=mode)
        else:
            path = root / path_text
            path.write_text(path.read_text(encoding="utf-8") + "H-CERT1\n", encoding="utf-8")
            path.chmod(mode)
    _run(root, "git", "add", *locker.H1_SCOPE)
    _run(root, "git", "commit", "-m", "H-CERT1")
    h1_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    _write(root, locker.H1_AUTHORITY_PATH.as_posix(), "{}\n")
    _write(root, locker.H1_MANIFEST_PATH.as_posix(), "{}\n")
    _run(root, "git", "add", *locker.P1_SCOPE)
    _run(root, "git", "commit", "-m", "P-CERT1")
    p1_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    for path_text in locker.H2_SCOPE:
        path = root / path_text
        path.write_text(
            path.read_text(encoding="utf-8") + "H-CERT2\n",
            encoding="utf-8",
        )
        path.chmod(int(locker.H_GIT_MODES[path_text][-3:], 8))
    _run(root, "git", "add", *locker.H2_SCOPE)
    _run(root, "git", "commit", "-m", "H-CERT2")
    h2_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    _write(root, locker.H2_AUTHORITY_PATH.as_posix(), "{}\n")
    _write(root, locker.H2_MANIFEST_PATH.as_posix(), "{}\n")
    _run(root, "git", "add", *locker.P2_SCOPE)
    _run(root, "git", "commit", "-m", "P-CERT2")
    p2_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    for path_text in locker.H3_SCOPE:
        path = root / path_text
        path.write_text(
            path.read_text(encoding="utf-8") + "H-CERT3\n",
            encoding="utf-8",
        )
        path.chmod(int(locker.H_GIT_MODES[path_text][-3:], 8))
    _run(root, "git", "add", *locker.H3_SCOPE)
    _run(root, "git", "commit", "-m", "H-CERT3")
    h3_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    _write(root, locker.H3_AUTHORITY_PATH.as_posix(), "{}\n")
    _write(root, locker.H3_MANIFEST_PATH.as_posix(), "{}\n")
    _run(root, "git", "add", *locker.P3_SCOPE)
    _run(root, "git", "commit", "-m", "P-CERT3")
    p3_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    for path_text in locker.H4_SCOPE:
        path = root / path_text
        path.write_text(
            path.read_text(encoding="utf-8") + "H-CERT4\n",
            encoding="utf-8",
        )
        path.chmod(int(locker.H_GIT_MODES[path_text][-3:], 8))
    _run(root, "git", "add", *locker.H4_SCOPE)
    _run(root, "git", "commit", "-m", "H-CERT4")
    h4_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    _write(root, locker.H4_AUTHORITY_PATH.as_posix(), "{}\n")
    _write(root, locker.H4_MANIFEST_PATH.as_posix(), "{}\n")
    _run(root, "git", "add", *locker.P4_SCOPE)
    _run(root, "git", "commit", "-m", "P-CERT4")
    p4_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    for path_text in locker.H5_SCOPE:
        path = root / path_text
        path.write_text(
            path.read_text(encoding="utf-8") + "H-CERT5\n",
            encoding="utf-8",
        )
        path.chmod(int(locker.H_GIT_MODES[path_text][-3:], 8))
    _run(root, "git", "add", *locker.H5_SCOPE)
    _run(root, "git", "commit", "-m", "H-CERT5")
    h5_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    for relative in (locker.H5_AUTHORITY_PATH, locker.H5_MANIFEST_PATH):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((locker.PROJECT_ROOT / relative).read_bytes())
        target.chmod(0o644)
    _run(root, "git", "add", *locker.P5_SCOPE)
    _run(root, "git", "commit", "-m", "P-CERT5")
    p5_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    for path_text in locker.H6_SCOPE:
        path = root / path_text
        path.write_text(
            path.read_text(encoding="utf-8") + "H-CERT6\n",
            encoding="utf-8",
        )
        path.chmod(int(locker.H_GIT_MODES[path_text][-3:], 8))
    _run(root, "git", "add", *locker.H6_SCOPE)
    _run(root, "git", "commit", "-m", "H-CERT6")
    h6_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    for relative in (locker.H6_AUTHORITY_PATH, locker.H6_MANIFEST_PATH):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((locker.PROJECT_ROOT / relative).read_bytes())
        target.chmod(0o644)
    _run(root, "git", "add", *locker.P6_SCOPE)
    _run(root, "git", "commit", "-m", "P-CERT6")
    p6_cert_commit = _run(root, "git", "rev-parse", "HEAD")

    _run(tmp_path, "git", "init", "--bare", "--initial-branch=main", str(remote))
    _run(root, "git", "remote", "add", "origin", str(remote))
    _run(root, "git", "push", "-u", "origin", "main")
    _run(root, "git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    return (
        root,
        remote,
        closure_source,
        r_syn,
        editorial,
        h1_cert_commit,
        p1_cert_commit,
        h2_cert_commit,
        p2_cert_commit,
        h3_cert_commit,
        p3_cert_commit,
        h4_cert_commit,
        p4_cert_commit,
        h5_cert_commit,
        p5_cert_commit,
        h6_cert_commit,
        p6_cert_commit,
    )


def _patch_topology(
    monkeypatch: pytest.MonkeyPatch,
    *,
    closure_source: str,
    r_syn: str,
    editorial: str,
    h1_cert_commit: str,
    p1_cert_commit: str,
    h2_cert_commit: str,
    p2_cert_commit: str,
    h3_cert_commit: str,
    p3_cert_commit: str,
    h4_cert_commit: str,
    p4_cert_commit: str,
    h5_cert_commit: str,
    p5_cert_commit: str,
    h6_cert_commit: str,
    p6_cert_commit: str,
) -> SimpleNamespace:
    monkeypatch.setattr(locker, "CLOSURE_SOURCE_COMMIT", closure_source)
    monkeypatch.setattr(locker, "R_SYN_COMMIT", r_syn)
    monkeypatch.setattr(locker, "EDITORIAL_COMMIT", editorial)
    monkeypatch.setattr(locker, "H1_CERT_COMMIT", h1_cert_commit)
    monkeypatch.setattr(locker, "P1_CERT_COMMIT", p1_cert_commit)
    monkeypatch.setattr(locker, "H2_CERT_COMMIT", h2_cert_commit)
    monkeypatch.setattr(locker, "P2_CERT_COMMIT", p2_cert_commit)
    monkeypatch.setattr(locker, "H3_CERT_COMMIT", h3_cert_commit)
    monkeypatch.setattr(locker, "P3_CERT_COMMIT", p3_cert_commit)
    monkeypatch.setattr(locker, "H4_CERT_COMMIT", h4_cert_commit)
    monkeypatch.setattr(locker, "P4_CERT_COMMIT", p4_cert_commit)
    monkeypatch.setattr(locker, "H5_CERT_COMMIT", h5_cert_commit)
    monkeypatch.setattr(locker, "P5_CERT_COMMIT", p5_cert_commit)
    monkeypatch.setattr(locker, "H6_CERT_COMMIT", h6_cert_commit)
    monkeypatch.setattr(locker, "P6_CERT_COMMIT", p6_cert_commit)
    contract = _contract(
        closure_source=closure_source,
        r_syn=r_syn,
        editorial=editorial,
        h1_cert_commit=h1_cert_commit,
        p1_cert_commit=p1_cert_commit,
        h2_cert_commit=h2_cert_commit,
        p2_cert_commit=p2_cert_commit,
        h3_cert_commit=h3_cert_commit,
        p3_cert_commit=p3_cert_commit,
        h4_cert_commit=h4_cert_commit,
        p4_cert_commit=p4_cert_commit,
        h5_cert_commit=h5_cert_commit,
        p5_cert_commit=p5_cert_commit,
        h6_cert_commit=h6_cert_commit,
        p6_cert_commit=p6_cert_commit,
    )
    _install_contract_stubs(monkeypatch, contract)
    return contract


def _materialize_h(root: Path) -> None:
    for path_text, kind in locker.H_SCOPE.items():
        mode = int(locker.H_GIT_MODES[path_text][-3:], 8)
        if kind == "A":
            _write(root, path_text, f"H-CERT:{path_text}\n", mode=mode)
        else:
            path = root / path_text
            path.write_text(
                path.read_text(encoding="utf-8") + "H-CERT\n",
                encoding="utf-8",
            )
            path.chmod(mode)


def _publish_h(root: Path) -> str:
    _run(root, "git", "add", *locker.H_SCOPE)
    _run(root, "git", "commit", "-m", "H-CERT")
    head = _run(root, "git", "rev-parse", "HEAD")
    _run(root, "git", "push", "origin", "main")
    return head


def _fake_state() -> dict[str, Any]:
    (
        h1_components,
        p1_components,
        h2_components,
        p2_components,
        h3_components,
        p3_components,
        h4_components,
        p4_components,
        h5_components,
        p5_components,
        h6_components,
        p6_components,
    ) = _historical_records()
    components = [
        {
            "path": path,
            "bytes": index + 1,
            "sha256": f"{index + 1:064x}",
            "git_mode": locker.H_GIT_MODES[path],
            "git_blob_oid": f"{index + 1:040x}",
            "filesystem_mode": int(locker.H_GIT_MODES[path][-3:], 8),
        }
        for index, path in enumerate(locker.H_SCOPE)
    ]
    contract = _contract(
        closure_source=locker.CLOSURE_SOURCE_COMMIT,
        r_syn=locker.R_SYN_COMMIT,
        editorial=locker.EDITORIAL_COMMIT,
    )
    suite = locker._suite_snapshot(  # noqa: SLF001 - direct authority unit test
        contract
    )
    anchors = _anchor_records()
    pointers = _pointer_records()
    static_contract = certification.load_contract(
        root=locker.PROJECT_ROOT,
        verify_inputs=False,
        allow_pending_suite=True,
    )
    return {
        "h_cert_commit": "a" * 40,
        "h1_component_records": h1_components,
        "p1_component_records": p1_components,
        "h2_component_records": h2_components,
        "p2_component_records": p2_components,
        "h3_component_records": h3_components,
        "p3_component_records": p3_components,
        "h4_component_records": h4_components,
        "p4_component_records": p4_components,
        "h5_component_records": h5_components,
        "p5_component_records": p5_components,
        "h6_component_records": h6_components,
        "p6_component_records": p6_components,
        "h_component_records": components,
        "anchor_input_records": anchors,
        "dvc_pointer_records": pointers,
        "dvc_status_policy": certification.expected_dvc_status_policy(
            static_contract
        ),
        "main_dvc_static_boundary": certification.main_dvc_static_boundary_record(
            static_contract,
            anchor_records=anchors,
            pointer_records=pointers,
        ),
        "suite": suite,
        "ordered_output_paths": list(locker.R_SCOPE),
    }


def _publication_root(tmp_path: Path) -> Path:
    root = tmp_path / "publication"
    (root / "configs/closure_v1").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "tmp").mkdir()
    return root


def test_scopes_modes_and_stop_boundary_are_exact() -> None:
    assert list(locker.H1_SCOPE.values()).count("A") == 9
    assert list(locker.H1_SCOPE.values()).count("M") == 2
    assert set(locker.H_SCOPE.values()) == {"M"}
    assert len(locker.H_SCOPE) == 11
    assert locker.H_GIT_MODES["src/data/prepare_commit_artifacts.py"] == "100755"
    assert {
        mode
        for path, mode in locker.H_GIT_MODES.items()
        if path != "src/data/prepare_commit_artifacts.py"
    } == {"100644"}
    assert locker.P_SCOPE == {
        "configs/closure_v1/phase4_final_certification_authority_v7.json": "A",
        "configs/closure_v1/phase4_final_certification_authority_manifest_v7.json": "A",
    }
    assert locker.P6_SCOPE == {
        "configs/closure_v1/phase4_final_certification_authority_v6.json": "A",
        "configs/closure_v1/phase4_final_certification_authority_manifest_v6.json": "A",
    }
    assert locker.P5_SCOPE == {
        "configs/closure_v1/phase4_final_certification_authority_v5.json": "A",
        "configs/closure_v1/phase4_final_certification_authority_manifest_v5.json": "A",
    }
    assert locker.P4_SCOPE == {
        "configs/closure_v1/phase4_final_certification_authority_v4.json": "A",
        "configs/closure_v1/phase4_final_certification_authority_manifest_v4.json": "A",
    }
    assert locker.P3_SCOPE == {
        "configs/closure_v1/phase4_final_certification_authority_v3.json": "A",
        "configs/closure_v1/phase4_final_certification_authority_manifest_v3.json": "A",
    }
    assert locker.P2_SCOPE == {
        "configs/closure_v1/phase4_final_certification_authority_v2.json": "A",
        "configs/closure_v1/phase4_final_certification_authority_manifest_v2.json": "A",
    }
    assert locker.P1_SCOPE == {
        "configs/closure_v1/phase4_final_certification_authority.json": "A",
        "configs/closure_v1/phase4_final_certification_authority_manifest.json": "A",
    }
    assert len(locker.R_SCOPE) == 8
    assert list(locker.R_SCOPE)[-1].endswith("final_certification_manifest.json")
    assert locker.ANCHOR_PATHS == (
        ".dvc/config",
        "docs/API_DATASET_CONTRACT.md",
        "docs/API_PROTOCOL.md",
        "poetry.lock",
        "pyproject.toml",
        "reports/closure_v1/11_synthesis/THESIS_CLAIM_EVIDENCE_MATRIX.csv",
        "reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json",
        "reports/thesis/chapter_iv_evidence_matrix_manifest.json",
        "reports/thesis/phase4_manuscript_build_receipt.json",
        "reports/thesis/phase4_manuscript_build_receipt_manifest.json",
    )


def test_cli_is_closed_and_domain_errors_are_translated(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    assert locker.parse_args(["--generate"]).generate is True
    for argv in ([], ["--check-only", "--generate"], ["--unknown"]):
        with pytest.raises(SystemExit):
            locker.parse_args(argv)

    monkeypatch.setattr(locker, "check_only", lambda: {"status": "ready"})
    assert locker.main(["--check-only"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "ready"}

    def fail() -> dict[str, Any]:
        raise certification.FinalCertificationContractError("closed")

    monkeypatch.setattr(locker, "generate", fail)
    assert locker.main(["--generate"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "closed"


def test_suite_snapshot_fails_closed_until_suite_is_locked() -> None:
    pending = _contract(
        closure_source=locker.CLOSURE_SOURCE_COMMIT,
        r_syn=locker.R_SYN_COMMIT,
        editorial=locker.EDITORIAL_COMMIT,
        suite_status="pending_integration",
    )
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="locked public-test suite",
    ):
        locker._suite_snapshot(pending)  # noqa: SLF001

    locked = _contract(
        closure_source=locker.CLOSURE_SOURCE_COMMIT,
        r_syn=locker.R_SYN_COMMIT,
        editorial=locker.EDITORIAL_COMMIT,
    )
    snapshot = locker._suite_snapshot(locked)  # noqa: SLF001
    assert snapshot["suite_lock"] == {
        "status": certification.LOCKED_SUITE_STATUS,
        "selector_count": certification.LOCKED_SUITE_SELECTOR_COUNT,
        "collected_test_count": certification.LOCKED_SUITE_COLLECTED_TEST_COUNT,
        "nodeids_sha256": certification.LOCKED_SUITE_NODEIDS_SHA256,
        "allowed_skip_count": certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT,
    }
    assert (
        snapshot["suite_lock"]["nodeids_sha256"]
        == "8422082eca90068bf6d6fff4f1e4d9b9964535e12c8fd6b0844658bbdf683349"
    )
    assert snapshot["selectors"] == list(locked.test_suite.selectors)

    for field, drift in (
        ("selector_count", certification.LOCKED_SUITE_SELECTOR_COUNT + 1),
        (
            "collected_test_count",
            certification.LOCKED_SUITE_COLLECTED_TEST_COUNT - 1,
        ),
        ("nodeids_sha256", "2" * 64),
        (
            "allowed_skip_count",
            certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT - 1,
        ),
    ):
        changed = _contract(
            closure_source=locker.CLOSURE_SOURCE_COMMIT,
            r_syn=locker.R_SYN_COMMIT,
            editorial=locker.EDITORIAL_COMMIT,
        )
        setattr(changed.test_suite, field, drift)
        with pytest.raises(
            certification.FinalCertificationContractError,
            match="exact locked public-test suite",
        ):
            locker._suite_snapshot(changed)  # noqa: SLF001


def test_authority_binds_every_frozen_surface_and_rejects_tampering() -> None:
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    locker.validate_authority(authority)
    assert authority["topology"] == {
        "closure_source_commit": locker.CLOSURE_SOURCE_COMMIT,
        "r_syn_commit": locker.R_SYN_COMMIT,
        "editorial_commit": locker.EDITORIAL_COMMIT,
        "h1_cert_commit": locker.H1_CERT_COMMIT,
        "p1_cert_commit": locker.P1_CERT_COMMIT,
        "h2_cert_commit": locker.H2_CERT_COMMIT,
        "p2_cert_commit": locker.P2_CERT_COMMIT,
        "h3_cert_commit": locker.H3_CERT_COMMIT,
        "p3_cert_commit": locker.P3_CERT_COMMIT,
        "h4_cert_commit": locker.H4_CERT_COMMIT,
        "p4_cert_commit": locker.P4_CERT_COMMIT,
        "h5_cert_commit": locker.H5_CERT_COMMIT,
        "p5_cert_commit": locker.P5_CERT_COMMIT,
        "h6_cert_commit": locker.H6_CERT_COMMIT,
        "p6_cert_commit": locker.P6_CERT_COMMIT,
        "h7_cert_commit": "a" * 40,
        "p7_cert_commit": None,
        "h_cert_commit": "a" * 40,
        "p_cert_commit": None,
        "r_cert_executable_tree_must_equal_p_cert": True,
    }
    assert [record["path"] for record in authority["anchor_input_records"]] == list(
        locker.ANCHOR_PATHS
    )
    assert len(authority["dvc_pointer_records"]) == 8
    assert authority["main_dvc_static_boundary"]["status_executed"] is False
    assert authority["main_dvc_static_boundary"][
        "static_boundary_verified"
    ] is True
    assert authority["main_dvc_static_boundary"]["real_dvc_execution_scope"] == (
        "isolated_r_cert_clone_only"
    )
    assert authority["ordered_r_cert_output_paths"] == list(locker.R_SCOPE)
    assert authority["p1_failure"]["retry_authorized"] is False
    assert authority["p2_failure"] == certification.expected_p2_failure_record()
    assert authority["p3_failure"] == certification.expected_p3_failure_record()
    assert authority["p4_failure"] == certification.expected_p4_failure_record()
    assert authority["p5_failure"] == certification.expected_p5_failure_record()
    assert authority["p6_failure"] == certification.expected_p6_failure_record()
    assert authority["p6_failure"]["status"] == (
        "execution_failed_closed_cleanup_succeeded"
    )
    assert authority["p6_failure"]["active_error"]["stage"] == (
        "postgres_start_portable_command_serialization"
    )
    assert authority["p6_failure"]["cleanup"] == {
        "status": "succeeded_exact",
        "namespace_preserved": False,
        "active_error_was_masked": False,
    }
    assert authority["p6_failure"]["retry_authorized"] is False
    assert [record["path"] for record in authority["h1_component_records"]] == list(
        locker.H1_SCOPE
    )
    assert [record["path"] for record in authority["p1_component_records"]] == list(
        locker.P1_SCOPE
    )
    assert [record["path"] for record in authority["h2_component_records"]] == list(
        locker.H2_SCOPE
    )
    assert [record["path"] for record in authority["p2_component_records"]] == list(
        locker.P2_SCOPE
    )
    assert [record["path"] for record in authority["h3_component_records"]] == list(
        locker.H3_SCOPE
    )
    assert [record["path"] for record in authority["p3_component_records"]] == list(
        locker.P3_SCOPE
    )
    assert [record["path"] for record in authority["h4_component_records"]] == list(
        locker.H4_SCOPE
    )
    assert [record["path"] for record in authority["p4_component_records"]] == list(
        locker.P4_SCOPE
    )
    assert [record["path"] for record in authority["h5_component_records"]] == list(
        locker.H5_SCOPE
    )
    assert [record["path"] for record in authority["p5_component_records"]] == list(
        locker.P5_SCOPE
    )
    assert [record["path"] for record in authority["h6_component_records"]] == list(
        locker.H6_SCOPE
    )
    assert [record["path"] for record in authority["p6_component_records"]] == list(
        locker.P6_SCOPE
    )
    assert authority["h7_component_records"] == authority["h_component_records"]
    assert authority["dvc_status_policy"] == certification.expected_dvc_status_policy(
        certification.load_contract(
            root=locker.PROJECT_ROOT,
            verify_inputs=False,
            allow_pending_suite=True,
        )
    )
    assert authority["dvc_status_policy"]["global_status_authorized"] is False
    assert authority["dvc_status_policy"]["target_count"] == 8
    assert authority["failure_diagnostics"] == dict(
        certification.FAILURE_DIAGNOSTICS_POLICY
    )
    assert authority["isolation"] == dict(certification._expected_isolation())
    assert authority["isolation"]["postgres_portable_path_policy"] == (
        certification.expected_postgres_portable_path_policy()
    )
    assert authority["isolation"]["expected_runtime_versions"] == dict(
        certification.EXPECTED_RUNTIME_VERSIONS
    )
    assert authority["isolation"][
        "failed_dvc_partial_tree_not_adopted_for_cleanup"
    ] is True
    assert authority["isolation"]["owned_site_cache_count"] == 2
    assert authority["isolation"]["owned_site_cache_roles"] == [
        "runtime_version",
        "restore_status",
    ]
    assert authority["isolation"]["owned_site_cache_filesystem_mode"] == "0700"
    assert authority["isolation"]["owned_site_caches_separated"] is True
    assert authority["isolation"]["owned_site_cache_paths_serialized"] is False
    assert authority["isolation"][
        "version_seal_before_private_config_or_pull"
    ] is True
    assert authority["isolation"][
        "single_dvc_runtime_retained_through_final_status_and_version_probe"
    ] is True
    assert authority["isolation"][
        "dvc_runtime_cross_call_identity_revalidated"
    ] is True
    assert authority["isolation"]["used_by_all_isolated_dvc_commands"] is True
    assert authority["isolation"]["copied_core_site_cache_dir_used"] is False
    assert authority["isolation"][
        "main_dvc_site_cache_metadata_inode_inventory_unchanged"
    ] is True
    assert authority["isolation"]["main_dvc_command_run"] is False
    assert "main_dvc_site_cache_must_remain_unchanged" not in authority["isolation"]
    assert "guard_path" not in authority["isolation"]
    assert "rollback_owned_inodes_only" not in authority["isolation"]
    assert authority["authorizations"] == dict(certification.AUTHORIZATION_POLICY)
    assert all(authority["prohibitions"].values())
    assert authority["prohibitions"]["owned_site_cache_paths_serialization"] is True
    assert authority["prohibitions"][
        "main_dvc_site_cache_payload_open_or_hash"
    ] is True
    assert authority["prohibitions"][
        "dvc_runtime_cross_call_identity_or_lifetime_drift"
    ] is True
    assert authority["prohibitions"]["partial_clone_global_dvc_status"] is True
    assert authority["prohibitions"][
        "postgres_portable_path_projection_drift"
    ] is True

    mutations: list[tuple[str, Any]] = [
        ("topology", {**authority["topology"], "p_cert_commit": "b" * 40}),
        ("p1_failure", {**authority["p1_failure"], "retry_authorized": True}),
        ("p2_failure", {**authority["p2_failure"], "retry_authorized": True}),
        ("p3_failure", {**authority["p3_failure"], "retry_authorized": True}),
        ("p4_failure", {**authority["p4_failure"], "retry_authorized": True}),
        ("p5_failure", {**authority["p5_failure"], "retry_authorized": True}),
        ("p6_failure", {**authority["p6_failure"], "retry_authorized": True}),
        ("h1_component_records_digest", "0" * 64),
        ("p1_component_records_digest", "0" * 64),
        ("h2_component_records_digest", "0" * 64),
        ("p2_component_records_digest", "0" * 64),
        ("h3_component_records_digest", "0" * 64),
        ("p3_component_records_digest", "0" * 64),
        ("h4_component_records_digest", "0" * 64),
        ("p4_component_records_digest", "0" * 64),
        ("h5_component_records_digest", "0" * 64),
        ("p5_component_records_digest", "0" * 64),
        ("h6_component_records_digest", "0" * 64),
        ("p6_component_records_digest", "0" * 64),
        ("h_scope", {}),
        ("h_component_records_digest", "0" * 64),
        ("h7_component_records_digest", "0" * 64),
        ("anchor_input_records_digest", "0" * 64),
        ("dvc_pointer_records", authority["dvc_pointer_records"][:-1]),
        (
            "dvc_status_policy",
            {**authority["dvc_status_policy"], "global_status_authorized": True},
        ),
        (
            "main_dvc_static_boundary",
            {**authority["main_dvc_static_boundary"], "status_executed": True},
        ),
        ("test_suite_digest", "0" * 64),
        ("ordered_r_cert_output_paths", list(reversed(list(locker.R_SCOPE)))),
        ("isolation", {}),
        ("failure_diagnostics", {}),
        ("authorizations", {}),
        ("prohibitions", {**authority["prohibitions"], "post_phase4_work": False}),
    ]
    for key, value in mutations:
        changed = copy.deepcopy(authority)
        changed[key] = value
        with pytest.raises(certification.FinalCertificationContractError):
            locker.validate_authority(changed)

    missing_isolation = copy.deepcopy(authority)
    del missing_isolation["isolation"]
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="authority keys drifted",
    ):
        locker.validate_authority(missing_isolation)

    for runtime_drift in (
        {**certification.EXPECTED_RUNTIME_VERSIONS, "python": "Python 3.14.8"},
        {**certification.EXPECTED_RUNTIME_VERSIONS, "foreign": "1.0"},
        {
            key: value
            for key, value in certification.EXPECTED_RUNTIME_VERSIONS.items()
            if key != "docker_server"
        },
    ):
        changed = copy.deepcopy(authority)
        changed["isolation"]["expected_runtime_versions"] = runtime_drift
        with pytest.raises(
            certification.FinalCertificationContractError,
            match="isolation boundary drifted",
        ):
            locker.validate_authority(changed)

    for lock_drift in (
        {
            "collected_test_count": (
                certification.LOCKED_SUITE_COLLECTED_TEST_COUNT - 1
            )
        },
        {"selector_count": certification.LOCKED_SUITE_SELECTOR_COUNT + 1},
        {"nodeids_sha256": "2" * 64},
        {
            "allowed_skip_count": (
                certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT - 1
            )
        },
    ):
        changed = copy.deepcopy(authority)
        changed["test_suite"]["suite_lock"].update(lock_drift)
        changed["test_suite_digest"] = certification.sha256_bytes(
            certification.canonical_json_bytes(changed["test_suite"])
        )
        with pytest.raises(
            certification.FinalCertificationContractError,
            match="test suite is not locked",
        ):
            locker.validate_authority(changed)


def test_manifest_is_canonical_and_binds_only_the_authority_output() -> None:
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    authority_bytes = certification.canonical_json_bytes(authority)
    manifest = locker._build_manifest(authority_bytes, "a" * 40)  # noqa: SLF001
    assert manifest["manifest_last"] is True
    assert manifest["h1_cert_commit"] == locker.H1_CERT_COMMIT
    assert manifest["p1_cert_commit"] == locker.P1_CERT_COMMIT
    assert manifest["h2_cert_commit"] == locker.H2_CERT_COMMIT
    assert manifest["p2_cert_commit"] == locker.P2_CERT_COMMIT
    assert manifest["h3_cert_commit"] == locker.H3_CERT_COMMIT
    assert manifest["p3_cert_commit"] == locker.P3_CERT_COMMIT
    assert manifest["h4_cert_commit"] == locker.H4_CERT_COMMIT
    assert manifest["p4_cert_commit"] == locker.P4_CERT_COMMIT
    assert manifest["h5_cert_commit"] == locker.H5_CERT_COMMIT
    assert manifest["p5_cert_commit"] == locker.P5_CERT_COMMIT
    assert manifest["h6_cert_commit"] == locker.H6_CERT_COMMIT
    assert manifest["p6_cert_commit"] == locker.P6_CERT_COMMIT
    assert manifest["h7_cert_commit"] == "a" * 40
    assert manifest["p7_cert_commit"] is None
    assert manifest["supersedes_p6"] is True
    assert manifest["supersedes_p5"] is True
    assert manifest["supersedes_p4"] is True
    assert manifest["supersedes_p3"] is True
    assert manifest["supersedes_p2"] is True
    assert manifest["supersedes_p1"] is True
    assert manifest["ordered_paths"] == list(locker.P_SCOPE)
    assert manifest["outputs"] == [manifest["authority"]]
    assert manifest["authority"] == {
        "path": locker.AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": certification.sha256_bytes(authority_bytes),
    }
    encoded = certification.canonical_json_bytes(manifest)
    assert encoded.endswith(b"\n")
    assert certification.canonical_json_bytes(json.loads(encoded)) == encoded


def test_check_only_accepts_exact_local_h_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        root, _remote, closure_source, r_syn, editorial,
        h1, p1, h2, p2, h3, p3, h4, p4, h5, p5, h6, p6,
    ) = _make_repository(tmp_path)
    _materialize_h(root)
    _patch_topology(
        monkeypatch,
        closure_source=closure_source,
        r_syn=r_syn,
        editorial=editorial,
        h1_cert_commit=h1,
        p1_cert_commit=p1,
        h2_cert_commit=h2,
        p2_cert_commit=p2,
        h3_cert_commit=h3,
        p3_cert_commit=p3,
        h4_cert_commit=h4,
        p4_cert_commit=p4,
        h5_cert_commit=h5,
        p5_cert_commit=p5,
        h6_cert_commit=h6,
        p6_cert_commit=p6,
    )
    before = _run(root, "git", "status", "--porcelain=v1", "--untracked-files=all")
    result = locker.check_only(root=root)
    after = _run(root, "git", "status", "--porcelain=v1", "--untracked-files=all")
    assert result["status"] == "ready_to_publish_h"
    assert result["writes_performed"] is False
    assert result["dvc_status_checked"] is False
    assert result["dvc_status_executed"] is False
    assert result["main_dvc_static_boundary_verified"] is True
    assert result["dvc_pull_commands_run"] is False
    assert result["test_commands_run"] is False
    assert result["parquet_payloads_opened"] is False
    assert before == after
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()


def test_check_only_accepts_pending_suite_only_for_local_h4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        root, _remote, closure_source, r_syn, editorial,
        h1, p1, h2, p2, h3, p3, h4, p4, h5, p5, h6, p6,
    ) = _make_repository(tmp_path)
    _materialize_h(root)
    contract = _patch_topology(
        monkeypatch,
        closure_source=closure_source,
        r_syn=r_syn,
        editorial=editorial,
        h1_cert_commit=h1,
        p1_cert_commit=p1,
        h2_cert_commit=h2,
        p2_cert_commit=p2,
        h3_cert_commit=h3,
        p3_cert_commit=p3,
        h4_cert_commit=h4,
        p4_cert_commit=p4,
        h5_cert_commit=h5,
        p5_cert_commit=p5,
        h6_cert_commit=h6,
        p6_cert_commit=p6,
    )
    contract.test_suite.status = "pending_integration"
    contract.test_suite.selector_count = None
    contract.test_suite.collected_test_count = None
    contract.test_suite.nodeids_sha256 = None
    result = locker.check_only(root=root)
    assert result["status"] == "ready_to_publish_h"
    assert result["h3_cert_commit"] == h3
    assert result["p3_cert_commit"] == p3
    assert result["h4_cert_commit"] == h4
    assert result["p4_cert_commit"] == p4
    assert result["h5_cert_commit"] == h5
    assert result["p5_cert_commit"] == p5
    assert result["h6_cert_commit"] == h6
    assert result["p6_cert_commit"] == p6
    assert result["h7_cert_commit"] is None
    assert result["h2_cert_commit"] == h2
    assert result["p2_cert_commit"] == p2


@pytest.mark.parametrize(
    "drift",
    ["extra", "unchanged", "mode", "symlink", "empty_addition"],
)
def test_local_h_rejects_scope_content_mode_and_symlink_drifts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    (
        root, _remote, closure_source, r_syn, editorial,
        h1, p1, h2, p2, h3, p3, h4, p4, h5, p5, h6, p6,
    ) = _make_repository(tmp_path)
    _materialize_h(root)
    _patch_topology(
        monkeypatch,
        closure_source=closure_source,
        r_syn=r_syn,
        editorial=editorial,
        h1_cert_commit=h1,
        p1_cert_commit=p1,
        h2_cert_commit=h2,
        p2_cert_commit=p2,
        h3_cert_commit=h3,
        p3_cert_commit=p3,
        h4_cert_commit=h4,
        p4_cert_commit=p4,
        h5_cert_commit=h5,
        p5_cert_commit=p5,
        h6_cert_commit=h6,
        p6_cert_commit=p6,
    )
    if drift == "extra":
        _write(root, "foreign.txt", "foreign\n")
    elif drift == "unchanged":
        target = root / "tests/test_prepare_commit_artifacts.py"
        target.write_text(
            _run(
                root,
                "git",
                "show",
                f"{p6}:tests/test_prepare_commit_artifacts.py",
            )
            + "\n",
            encoding="utf-8",
        )
    elif drift == "mode":
        (root / "tests/test_lock_phase4_final_certification.py").chmod(0o755)
    elif drift == "symlink":
        target = root / "tests/test_lock_phase4_final_certification.py"
        target.unlink()
        target.symlink_to(root / "editorial.txt")
    else:
        (root / "tests/test_lock_phase4_final_certification.py").write_bytes(b"")
    with pytest.raises(certification.FinalCertificationContractError):
        locker.check_only(root=root)


def test_check_only_accepts_only_clean_published_h_and_empty_dvc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        root, _remote, closure_source, r_syn, editorial,
        h1, p1, h2, p2, h3, p3, h4, p4, h5, p5, h6, p6,
    ) = _make_repository(tmp_path)
    _materialize_h(root)
    contract = _patch_topology(
        monkeypatch,
        closure_source=closure_source,
        r_syn=r_syn,
        editorial=editorial,
        h1_cert_commit=h1,
        p1_cert_commit=p1,
        h2_cert_commit=h2,
        p2_cert_commit=p2,
        h3_cert_commit=h3,
        p3_cert_commit=p3,
        h4_cert_commit=h4,
        p4_cert_commit=p4,
        h5_cert_commit=h5,
        p5_cert_commit=p5,
        h6_cert_commit=h6,
        p6_cert_commit=p6,
    )
    head = _publish_h(root)
    original_run = locker.subprocess.run

    def reject_dvc(command: list[str], *args: Any, **kwargs: Any) -> Any:
        executable = os.fspath(command[0])
        if executable.endswith("/dvc") or executable.startswith("/proc/self/fd/"):
            raise AssertionError("main-worktree DVC execution is forbidden")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(locker.subprocess, "run", reject_dvc)
    result = locker.check_only(root=root)
    assert result["status"] == "ready_to_generate"
    assert result["h_cert_commit"] == head
    assert result["dvc_status_checked"] is False
    assert result["dvc_status_executed"] is False
    assert result["main_dvc_static_boundary_verified"] is True
    assert result["main_dvc_static_boundary"]["state_source"] == (
        "git_and_versioned_dvc_pointers"
    )

    runtime_namespace = root / locker.RUNTIME_NAMESPACE_PATH
    runtime_namespace.mkdir(parents=True)
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="active runtime namespace",
    ):
        locker.check_only(root=root)
    runtime_namespace.rmdir()

    _write(root, "foreign.txt", "drift\n")
    with pytest.raises(
        certification.FinalCertificationContractError, match="clean worktree"
    ):
        locker.check_only(root=root)
    (root / "foreign.txt").unlink()
    contract.test_suite.status = "pending_integration"
    with pytest.raises(
        certification.FinalCertificationContractError, match="remains pending"
    ):
        locker.check_only(root=root)


def test_generation_revalidates_state_and_publishes_exact2_manifest_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        root, _remote, closure_source, r_syn, editorial,
        h1, p1, h2, p2, h3, p3, h4, p4, h5, p5, h6, p6,
    ) = _make_repository(tmp_path)
    _materialize_h(root)
    _patch_topology(
        monkeypatch,
        closure_source=closure_source,
        r_syn=r_syn,
        editorial=editorial,
        h1_cert_commit=h1,
        p1_cert_commit=p1,
        h2_cert_commit=h2,
        p2_cert_commit=p2,
        h3_cert_commit=h3,
        p3_cert_commit=p3,
        h4_cert_commit=h4,
        p4_cert_commit=p4,
        h5_cert_commit=h5,
        p5_cert_commit=p5,
        h6_cert_commit=h6,
        p6_cert_commit=p6,
    )
    head = _publish_h(root)
    original_run = locker.subprocess.run

    def reject_dvc(command: list[str], *args: Any, **kwargs: Any) -> Any:
        executable = os.fspath(command[0])
        if executable.endswith("/dvc") or executable.startswith("/proc/self/fd/"):
            raise AssertionError("main-worktree DVC execution is forbidden")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(locker.subprocess, "run", reject_dvc)
    link_order: list[str] = []
    original_link = locker._link_no_clobber  # noqa: SLF001

    def observed_link(
        source: locker._OwnedFileAt,  # noqa: SLF001
        parent_fd: int,
        name: str,
    ) -> locker._OwnedFileAt:  # noqa: SLF001
        link_order.append(name)
        return original_link(source, parent_fd, name)

    monkeypatch.setattr(locker, "_link_no_clobber", observed_link)
    result = locker.generate(root=root)
    assert result["status"] == "authority_bundle_written_unpublished"
    assert result["h_cert_commit"] == head
    assert result["dvc_status_checked"] is False
    assert result["dvc_status_executed"] is False
    assert result["main_dvc_static_boundary_verified"] is True
    assert result["dvc_pull_commands_run"] is False
    assert result["test_commands_run"] is False
    assert result["parquet_payloads_opened"] is False
    assert link_order == [locker.AUTHORITY_PATH.name, locker.MANIFEST_PATH.name]
    assert _run(
        root, "git", "status", "--porcelain=v1", "--untracked-files=all"
    ).splitlines() == sorted(
        [
            f"?? {locker.AUTHORITY_PATH.as_posix()}",
            f"?? {locker.MANIFEST_PATH.as_posix()}",
        ]
    )
    authority_path = root / locker.AUTHORITY_PATH
    manifest_path = root / locker.MANIFEST_PATH
    authority_bytes = authority_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    assert certification.canonical_json_bytes(json.loads(authority_bytes)) == authority_bytes
    assert certification.canonical_json_bytes(json.loads(manifest_bytes)) == manifest_bytes
    manifest = json.loads(manifest_bytes)
    assert manifest["authority"]["sha256"] == certification.sha256_bytes(
        authority_bytes
    )
    assert not (root / locker.GUARD_PATH).exists()
    assert not list((root / locker.AUTHORITY_PATH.parent).glob(f"{locker.TEMP_PREFIX}*"))
    assert not list(root.rglob(f"{locker.CLEANUP_TOMBSTONE_PREFIX}*"))


def test_publication_no_clobber_preserves_existing_authority(
    tmp_path: Path,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    existing = root / locker.AUTHORITY_PATH
    existing.write_bytes(b"foreign\n")
    before = existing.stat()
    with pytest.raises(
        certification.FinalCertificationContractError, match="must be absent"
    ):
        locker.publish_authority_bundle(root, authority)
    after = existing.stat()
    assert existing.read_bytes() == b"foreign\n"
    assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
    assert not (root / locker.MANIFEST_PATH).exists()


def test_publication_rolls_back_its_authority_if_manifest_link_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    original_link = locker._link_no_clobber  # noqa: SLF001
    calls = 0

    def fail_second_link(
        source: locker._OwnedFileAt,  # noqa: SLF001
        parent_fd: int,
        name: str,
    ) -> locker._OwnedFileAt:  # noqa: SLF001
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected manifest-last failure")
        return original_link(source, parent_fd, name)

    monkeypatch.setattr(locker, "_link_no_clobber", fail_second_link)
    with pytest.raises(OSError, match="manifest-last failure"):
        locker.publish_authority_bundle(root, authority)
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()
    assert not (root / locker.GUARD_PATH).exists()
    assert not list((root / locker.AUTHORITY_PATH.parent).glob(f"{locker.TEMP_PREFIX}*"))


def test_publication_rejects_symlink_legacy_guard_parent_without_following(
    tmp_path: Path,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (root / locker.GUARD_PATH.parent).symlink_to(foreign, target_is_directory=True)
    with pytest.raises(
        certification.FinalCertificationContractError, match="legacy guard ancestor"
    ):
        locker.publish_authority_bundle(root, authority)
    assert list(foreign.iterdir()) == []
    assert not (root / locker.AUTHORITY_PATH).exists()


@pytest.mark.parametrize("phase", ["prepublish", "postpublish"])
def test_publication_rejects_configs_ancestor_swap_and_rolls_back(
    tmp_path: Path,
    phase: str,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    moved_configs = root / "configs.moved"

    def swap_configs() -> None:
        os.rename(root / "configs", moved_configs)
        (root / "configs/closure_v1").mkdir(parents=True)

    validators = (
        {"prepublish_validator": swap_configs}
        if phase == "prepublish"
        else {"postpublish_validator": swap_configs}
    )
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="configs root ownership/path binding drifted",
    ):
        locker.publish_authority_bundle(root, authority, **validators)

    for base in (root / "configs", moved_configs):
        assert not (base / "closure_v1" / locker.AUTHORITY_PATH.name).exists()
        assert not (base / "closure_v1" / locker.MANIFEST_PATH.name).exists()
    assert not (root / locker.GUARD_PATH).exists()
    assert not list(
        (moved_configs / "closure_v1").glob(f"{locker.TEMP_PREFIX}*")
    )
    assert not list(root.rglob(f"{locker.CLEANUP_TOMBSTONE_PREFIX}*"))


def test_publication_detects_configs_swap_between_precheck_and_first_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    moved_configs = root / "configs.moved"
    original_link = locker._link_no_clobber  # noqa: SLF001
    swapped = False

    def swap_then_link(
        source: locker._OwnedFileAt,  # noqa: SLF001
        destination_parent_fd: int,
        destination_name: str,
    ) -> locker._OwnedFileAt:  # noqa: SLF001
        nonlocal swapped
        if not swapped:
            os.rename(root / "configs", moved_configs)
            (root / "configs/closure_v1").mkdir(parents=True)
            swapped = True
        return original_link(source, destination_parent_fd, destination_name)

    monkeypatch.setattr(locker, "_link_no_clobber", swap_then_link)
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="configs root ownership/path binding drifted",
    ):
        locker.publish_authority_bundle(root, authority)

    assert swapped is True
    for base in (root / "configs", moved_configs):
        assert not (base / "closure_v1" / locker.AUTHORITY_PATH.name).exists()
        assert not (base / "closure_v1" / locker.MANIFEST_PATH.name).exists()
    assert not (root / locker.GUARD_PATH).exists()
    assert not list(root.rglob(f"{locker.CLEANUP_TOMBSTONE_PREFIX}*"))


def test_publication_rejects_legacy_tmp_ancestor_swap_and_rolls_back(
    tmp_path: Path,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    retained_tmp = root / "tmp.retained"

    def swap_tmp_parent() -> None:
        os.rename(root / "tmp", retained_tmp)
        (root / "tmp").mkdir()
        (root / "tmp/foreign.marker").write_bytes(b"foreign\n")

    with pytest.raises(
        certification.FinalCertificationContractError,
        match="legacy guard tmp ancestor ownership/path binding drifted",
    ):
        locker.publish_authority_bundle(
            root,
            authority,
            postpublish_validator=swap_tmp_parent,
        )

    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()
    assert (root / "tmp/foreign.marker").read_bytes() == b"foreign\n"
    assert not (retained_tmp / locker.GUARD_PATH.parent.name).exists()
    assert not list(retained_tmp.rglob(f"{locker.CLEANUP_TOMBSTONE_PREFIX}*"))


@pytest.mark.parametrize(
    ("swap_kind", "error_pattern"),
    [
        ("root", "repository root ownership/path binding drifted"),
        ("parent", "repository parent ownership/path binding drifted"),
    ],
)
def test_publication_rejects_repository_root_or_parent_swap_and_rolls_back_by_fd(
    tmp_path: Path,
    swap_kind: str,
    error_pattern: str,
) -> None:
    canonical_parent = tmp_path / "canonical-parent"
    root = _publication_root(canonical_parent)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    if swap_kind == "root":
        retained_root = canonical_parent / "publication.retained"
    else:
        retained_parent = tmp_path / "canonical-parent.retained"
        retained_root = retained_parent / "publication"

    def swap_repository_binding() -> None:
        if swap_kind == "root":
            os.rename(root, retained_root)
        else:
            os.rename(canonical_parent, retained_parent)
        root.mkdir(parents=True)
        (root / "foreign.marker").write_bytes(b"foreign repository\n")

    with pytest.raises(
        certification.FinalCertificationContractError,
        match=error_pattern,
    ):
        locker.publish_authority_bundle(
            root,
            authority,
            postpublish_validator=swap_repository_binding,
        )

    assert (root / "foreign.marker").read_bytes() == b"foreign repository\n"
    assert not (retained_root / locker.AUTHORITY_PATH).exists()
    assert not (retained_root / locker.MANIFEST_PATH).exists()
    assert not (retained_root / locker.GUARD_PATH).exists()
    assert not list(retained_root.rglob(f"{locker.CLEANUP_TOMBSTONE_PREFIX}*"))


def test_publication_rechecks_r_cert_absence_after_postvalidator(
    tmp_path: Path,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    foreign_output = root / certification.CERTIFICATION_ROOT / "foreign.marker"

    def materialize_foreign_r_cert() -> None:
        foreign_output.parent.mkdir(parents=True)
        foreign_output.write_bytes(b"foreign R-CERT\n")

    with pytest.raises(
        certification.FinalCertificationContractError,
        match="R-CERT output namespace must be absent",
    ):
        locker.publish_authority_bundle(
            root,
            authority,
            postpublish_validator=materialize_foreign_r_cert,
        )

    assert foreign_output.read_bytes() == b"foreign R-CERT\n"
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()
    assert not (root / locker.GUARD_PATH).exists()
    assert not list(root.rglob(f"{locker.CLEANUP_TOMBSTONE_PREFIX}*"))


@pytest.mark.parametrize("entry_kind", ["file", "symlink"])
def test_publication_rejects_and_preserves_preexisting_legacy_guard(
    tmp_path: Path,
    entry_kind: str,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    guard = root / locker.GUARD_PATH
    guard.parent.mkdir()
    if entry_kind == "file":
        guard.write_bytes(b"legacy foreign guard\n")
    else:
        target = tmp_path / "foreign-target"
        target.write_bytes(b"foreign target\n")
        guard.symlink_to(target)
    before = guard.lstat()

    with pytest.raises(
        certification.FinalCertificationContractError,
        match="legacy guard must be absent",
    ):
        locker.publish_authority_bundle(root, authority)

    after = guard.lstat()
    assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()


def test_publication_preserves_legacy_namespace_and_never_touches_guard_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    legacy_namespace = root / locker.GUARD_PATH.parent
    legacy_namespace.mkdir()
    marker = legacy_namespace / "foreign.marker"
    marker.write_bytes(b"foreign namespace\n")
    created: list[str] = []
    removed: list[str] = []
    original_create = locker._create_owned_file_at  # noqa: SLF001
    original_unlink = locker._unlink_owned_file_at  # noqa: SLF001

    def observed_create(*args: Any, **kwargs: Any) -> locker._OwnedFileAt:  # noqa: SLF001
        created.append(args[1])
        return original_create(*args, **kwargs)

    def observed_unlink(
        owner: locker._OwnedFileAt,  # noqa: SLF001
        *,
        context: str,
        missing_is_error: bool = True,
    ) -> None:
        removed.append(owner.name)
        original_unlink(
            owner,
            context=context,
            missing_is_error=missing_is_error,
        )

    monkeypatch.setattr(locker, "_create_owned_file_at", observed_create)
    monkeypatch.setattr(locker, "_unlink_owned_file_at", observed_unlink)
    locker.publish_authority_bundle(root, authority)

    assert marker.read_bytes() == b"foreign namespace\n"
    assert not (legacy_namespace / locker.GUARD_PATH.name).exists()
    assert locker.GUARD_PATH.name not in created
    assert locker.GUARD_PATH.name not in removed


@pytest.mark.parametrize("phase", ["prepublish", "postpublish"])
def test_publication_stops_and_preserves_legacy_guard_that_appears(
    tmp_path: Path,
    phase: str,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    guard = root / locker.GUARD_PATH
    guard.parent.mkdir()

    def create_foreign_guard() -> None:
        guard.write_bytes(b"foreign guard during publication\n")

    validators = (
        {"prepublish_validator": create_foreign_guard}
        if phase == "prepublish"
        else {"postpublish_validator": create_foreign_guard}
    )
    with pytest.raises(
        certification.FinalCertificationContractError,
        match="legacy guard must be absent",
    ):
        locker.publish_authority_bundle(root, authority, **validators)

    assert guard.read_bytes() == b"foreign guard during publication\n"
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()


def test_publication_flock_rejects_concurrent_cooperator_and_releases(
    tmp_path: Path,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    competing_fd = os.open(root / ".git", os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(competing_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(
            certification.FinalCertificationContractError,
            match="holds the repository lock",
        ):
            locker.publish_authority_bundle(root, authority)
        assert not (root / locker.AUTHORITY_PATH).exists()
        assert not (root / locker.MANIFEST_PATH).exists()
    finally:
        fcntl.flock(competing_fd, fcntl.LOCK_UN)
        os.close(competing_fd)

    locker.publish_authority_bundle(root, authority)
    probe_fd = os.open(root / ".git", os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(probe_fd, fcntl.LOCK_UN)
    finally:
        os.close(probe_fd)


@pytest.mark.parametrize("phase", ["prepublish", "postpublish"])
def test_publication_retains_flock_through_every_validator(
    tmp_path: Path,
    phase: str,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    observed = False

    def require_lock_held() -> None:
        nonlocal observed
        probe_fd = os.open(root / ".git", os.O_RDONLY | os.O_DIRECTORY)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            observed = True
        finally:
            os.close(probe_fd)

    validators = (
        {"prepublish_validator": require_lock_held}
        if phase == "prepublish"
        else {"postpublish_validator": require_lock_held}
    )
    locker.publish_authority_bundle(root, authority, **validators)
    assert observed is True


def test_publication_releases_flock_after_failure(
    tmp_path: Path,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001

    def fail_under_lock() -> None:
        raise RuntimeError("injected publication failure")

    with pytest.raises(RuntimeError, match="injected publication failure"):
        locker.publish_authority_bundle(
            root,
            authority,
            prepublish_validator=fail_under_lock,
        )
    probe_fd = os.open(root / ".git", os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(probe_fd, fcntl.LOCK_UN)
    finally:
        os.close(probe_fd)
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()


def test_publication_detects_git_directory_swap_and_preserves_foreign(
    tmp_path: Path,
) -> None:
    root = _publication_root(tmp_path)
    authority = locker._build_authority(_fake_state())  # noqa: SLF001
    retained_git = root / ".git.retained"

    def swap_git_directory() -> None:
        os.rename(root / ".git", retained_git)
        (root / ".git").mkdir()
        (root / ".git/foreign.marker").write_bytes(b"foreign git directory\n")

    with pytest.raises(
        certification.FinalCertificationContractError,
        match="Git directory ownership/path binding drifted",
    ):
        locker.publish_authority_bundle(
            root,
            authority,
            prepublish_validator=swap_git_directory,
        )

    assert (root / ".git/foreign.marker").read_bytes() == b"foreign git directory\n"
    assert retained_git.is_dir()
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()


@pytest.mark.parametrize("entry_kind", ["file", "directory"])
def test_atomic_cleanup_capture_restores_boundary_foreign_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry_kind: str,
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    canonical = parent / "owned"
    saved_owned = parent / "owned.saved"
    if entry_kind == "file":
        canonical.write_bytes(b"owned\n")
    else:
        canonical.mkdir()
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    owned_fd: int | None = None
    metadata = canonical.lstat()
    if entry_kind == "directory":
        owned_fd = os.open(
            canonical.name,
            os.O_RDONLY | os.O_DIRECTORY,
            dir_fd=parent_fd,
        )
    original_rename = locker._rename_noreplace_at  # noqa: SLF001
    replaced = False

    def replace_at_capture_boundary(
        source_directory_fd: int,
        source_name: str,
        target_directory_fd: int,
        target_name: str,
    ) -> None:
        nonlocal replaced
        if source_name == canonical.name and not replaced:
            os.rename(
                canonical.name,
                saved_owned.name,
                src_dir_fd=source_directory_fd,
                dst_dir_fd=source_directory_fd,
            )
            if entry_kind == "file":
                canonical.write_bytes(b"foreign\n")
            else:
                canonical.mkdir()
                (canonical / "foreign.marker").write_bytes(b"foreign\n")
            replaced = True
        original_rename(
            source_directory_fd,
            source_name,
            target_directory_fd,
            target_name,
        )

    monkeypatch.setattr(
        locker,
        "_rename_noreplace_at",
        replace_at_capture_boundary,
    )
    try:
        with pytest.raises(
            certification.FinalCertificationContractError,
            match="foreign entry was restored",
        ):
            locker._remove_owned_name_atomic(  # noqa: SLF001
                parent_fd,
                canonical.name,
                (metadata.st_dev, metadata.st_ino),
                context="atomic boundary probe",
                missing_is_error=True,
                owned_fd=owned_fd,
                expected_directory=entry_kind == "directory",
            )
        assert replaced is True
        if entry_kind == "file":
            assert canonical.read_bytes() == b"foreign\n"
            assert saved_owned.read_bytes() == b"owned\n"
        else:
            assert (canonical / "foreign.marker").read_bytes() == b"foreign\n"
            assert saved_owned.is_dir()
        assert (saved_owned.stat().st_dev, saved_owned.stat().st_ino) == (
            metadata.st_dev,
            metadata.st_ino,
        )
        assert not list(parent.glob(f"{locker.CLEANUP_TOMBSTONE_PREFIX}*"))
    finally:
        if owned_fd is not None:
            os.close(owned_fd)
        os.close(parent_fd)


def test_atomic_cleanup_restores_owned_nonempty_directory(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    canonical = parent / "owned"
    canonical.mkdir(parents=True)
    (canonical / "retained.marker").write_bytes(b"retained\n")
    metadata = canonical.stat()
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    owned_fd = os.open(
        canonical.name,
        os.O_RDONLY | os.O_DIRECTORY,
        dir_fd=parent_fd,
    )
    try:
        with pytest.raises(
            certification.FinalCertificationContractError,
            match="owned cleanup directory is not empty",
        ):
            locker._remove_owned_name_atomic(  # noqa: SLF001
                parent_fd,
                canonical.name,
                (metadata.st_dev, metadata.st_ino),
                context="non-empty directory probe",
                missing_is_error=True,
                owned_fd=owned_fd,
                expected_directory=True,
            )
    finally:
        os.close(owned_fd)
        os.close(parent_fd)

    assert (canonical / "retained.marker").read_bytes() == b"retained\n"
    assert (canonical.stat().st_dev, canonical.stat().st_ino) == (
        metadata.st_dev,
        metadata.st_ino,
    )
    assert not list(parent.glob(f"{locker.CLEANUP_TOMBSTONE_PREFIX}*"))


def test_atomic_cleanup_restores_owned_file_after_unlink_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    canonical = parent / "owned"
    canonical.write_bytes(b"owned\n")
    metadata = canonical.stat()
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    original_unlink = locker.os.unlink

    def fail_tombstone_unlink(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if isinstance(path, str) and path.startswith(
            locker.CLEANUP_TOMBSTONE_PREFIX
        ):
            raise OSError(errno.EIO, "injected tombstone unlink failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(locker.os, "unlink", fail_tombstone_unlink)
    try:
        with pytest.raises(OSError, match="injected tombstone unlink failure"):
            locker._remove_owned_name_atomic(  # noqa: SLF001
                parent_fd,
                canonical.name,
                (metadata.st_dev, metadata.st_ino),
                context="unlink failure probe",
                missing_is_error=True,
            )
    finally:
        os.close(parent_fd)

    assert canonical.read_bytes() == b"owned\n"
    assert (canonical.stat().st_dev, canonical.stat().st_ino) == (
        metadata.st_dev,
        metadata.st_ino,
    )
    assert not list(parent.glob(f"{locker.CLEANUP_TOMBSTONE_PREFIX}*"))


def test_atomic_mkdir_never_adopts_foreign_final_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    original_rename = locker._rename_noreplace_at  # noqa: SLF001
    injected = False

    def create_foreign_before_final_rename(
        source_directory_fd: int,
        source_name: str,
        target_directory_fd: int,
        target_name: str,
    ) -> None:
        nonlocal injected
        if (
            not injected
            and source_name.startswith(locker.DIRECTORY_TEMP_PREFIX)
            and target_name == "owned"
        ):
            os.mkdir(target_name, mode=0o700, dir_fd=target_directory_fd)
            foreign_fd = os.open(
                target_name,
                os.O_RDONLY | os.O_DIRECTORY,
                dir_fd=target_directory_fd,
            )
            try:
                marker_fd = os.open(
                    "foreign.marker",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=foreign_fd,
                )
                try:
                    os.write(marker_fd, b"foreign directory\n")
                finally:
                    os.close(marker_fd)
            finally:
                os.close(foreign_fd)
            injected = True
        original_rename(
            source_directory_fd,
            source_name,
            target_directory_fd,
            target_name,
        )

    monkeypatch.setattr(
        locker,
        "_rename_noreplace_at",
        create_foreign_before_final_rename,
    )
    try:
        with pytest.raises(
            certification.FinalCertificationContractError,
            match="already exists",
        ):
            locker._mkdir_owned_at(  # noqa: SLF001
                parent_fd,
                "owned",
                mode=0o700,
                context="atomic mkdir probe",
            )
    finally:
        os.close(parent_fd)

    assert injected is True
    assert (parent / "owned/foreign.marker").read_bytes() == (
        b"foreign directory\n"
    )
    assert not list(parent.glob(f"{locker.DIRECTORY_TEMP_PREFIX}*"))
    assert not list(parent.glob(f"{locker.CLEANUP_TOMBSTONE_PREFIX}*"))


def test_regular_reader_restats_canonical_name_after_fd_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "component.py"
    target.write_bytes(b"owned bytes\n")
    saved = tmp_path / "component.saved"
    anchored = locker._regular_file(  # noqa: SLF001
        tmp_path,
        target.name,
        expected_mode=0o644,
        context="canonical relstat probe",
    )
    original_stat = locker.os.stat
    file_restats = 0
    swapped = False

    def swap_before_final_relstat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: Any,
        **kwargs: Any,
    ) -> os.stat_result:
        nonlocal file_restats, swapped
        if path == target.name and kwargs.get("dir_fd") == anchored.parent_fd:
            file_restats += 1
        if file_restats == 2 and not swapped:
            os.rename(
                target.name,
                saved.name,
                src_dir_fd=anchored.parent_fd,
                dst_dir_fd=anchored.parent_fd,
            )
            descriptor = os.open(
                target.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
                dir_fd=anchored.parent_fd,
            )
            os.write(descriptor, b"owned bytes\n")
            os.close(descriptor)
            swapped = True
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(locker.os, "stat", swap_before_final_relstat)
    try:
        with pytest.raises(
            certification.FinalCertificationContractError,
            match="name or identity drifted",
        ):
            locker._read_regular(  # noqa: SLF001
                anchored,
                context="canonical relstat probe",
            )
    finally:
        certification._close_anchored_file(anchored)  # noqa: SLF001
    assert target.read_bytes() == b"owned bytes\n"
    assert saved.read_bytes() == b"owned bytes\n"


def test_generation_does_not_contain_forbidden_execution_commands() -> None:
    source = Path(locker.__file__).read_text(encoding="utf-8")
    # The locker may inspect Git only. Real DVC belongs to the isolated R-CERT
    # clone and is never invoked by H-CERT4/P-CERT4.
    assert "def _dvc_status" not in source
    assert '"status", "--json"' not in source
    assert "DVC_NO_ANALYTICS" not in source
    assert '"pull"' not in source
    assert '"pytest"' not in source
    assert '"dvc", "add"' not in source
    assert '"dvc", "push"' not in source
    assert "read_parquet" not in source
    assert "data/targets" not in source
    assert "evaluation_outcomes" not in source
    assert "def _acquire_guard" not in source
    assert "rollback_owned_inodes_only" not in source


def test_contract_collection_rejects_wrong_anchor_pointer_and_output_cardinality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract(
        closure_source=locker.CLOSURE_SOURCE_COMMIT,
        r_syn=locker.R_SYN_COMMIT,
        editorial=locker.EDITORIAL_COMMIT,
    )
    _install_contract_stubs(monkeypatch, contract)
    state = locker._collect_contract_state(contract, Path("."))  # noqa: SLF001
    assert len(state["anchor_input_records"]) == 10
    assert len(state["dvc_pointer_records"]) == 8
    assert state["main_dvc_static_boundary"]["status_executed"] is False
    assert state["main_dvc_static_boundary"]["static_boundary_verified"] is True

    monkeypatch.setattr(
        certification,
        "collect_anchor_input_records",
        lambda *_args, **_kwargs: list(reversed(_anchor_records())),
    )
    with pytest.raises(
        certification.FinalCertificationContractError, match="anchor input path order"
    ):
        locker._collect_contract_state(contract, Path("."))  # noqa: SLF001

    monkeypatch.setattr(
        certification,
        "collect_anchor_input_records",
        lambda *_args, **_kwargs: _anchor_records(),
    )
    monkeypatch.setattr(
        certification,
        "collect_dvc_pointer_records",
        lambda *_args, **_kwargs: _pointer_records()[:-1],
    )
    with pytest.raises(
        certification.FinalCertificationContractError, match="exactly eight"
    ):
        locker._collect_contract_state(contract, Path("."))  # noqa: SLF001


def test_dvc_status_accepts_only_exact_empty_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Historical nodeid retained: H-CERT4 supersedes the old dynamic-status
    # assertion with an entirely static Git-and-pointer reconstruction.
    del tmp_path
    contract = _contract(
        closure_source=locker.CLOSURE_SOURCE_COMMIT,
        r_syn=locker.R_SYN_COMMIT,
        editorial=locker.EDITORIAL_COMMIT,
    )
    _install_contract_stubs(monkeypatch, contract)
    monkeypatch.setattr(
        locker.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("static boundary must not invoke subprocess")
        ),
    )
    state = locker._collect_contract_state(contract, Path("."))  # noqa: SLF001
    assert not hasattr(locker, "_dvc_status")
    assert state["main_dvc_static_boundary"]["status_executed"] is False
    assert state["main_dvc_static_boundary"]["static_boundary_verified"] is True
    assert state["main_dvc_static_boundary"]["versioned_pointer_count"] == 8


def test_dvc_status_executes_retained_fd_not_foreign_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Historical nodeid retained: no DVC descriptor is executed at all now.
    root, _remote, closure_source, r_syn, editorial, h1, p1, h2, p2, h3, p3, h4, p4, h5, p5, h6, p6 = (
        _make_repository(tmp_path)
    )
    _materialize_h(root)
    _patch_topology(
        monkeypatch,
        closure_source=closure_source,
        r_syn=r_syn,
        editorial=editorial,
        h1_cert_commit=h1,
        p1_cert_commit=p1,
        h2_cert_commit=h2,
        p2_cert_commit=p2,
        h3_cert_commit=h3,
        p3_cert_commit=p3,
        h4_cert_commit=h4,
        p4_cert_commit=p4,
        h5_cert_commit=h5,
        p5_cert_commit=p5,
        h6_cert_commit=h6,
        p6_cert_commit=p6,
    )
    original_run = locker.subprocess.run
    observed: list[list[str]] = []

    def reject_dvc(command: list[str], *args: Any, **kwargs: Any) -> Any:
        observed.append(command)
        executable = os.fspath(command[0])
        if executable.endswith("/dvc") or executable.startswith("/proc/self/fd/"):
            raise AssertionError("main-worktree DVC execution is forbidden")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(locker.subprocess, "run", reject_dvc)
    result = locker.check_only(root=root)
    assert result["dvc_status_executed"] is False
    assert observed
    assert {command[0] for command in observed} == {"git"}
