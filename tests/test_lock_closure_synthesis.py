from __future__ import annotations

import inspect
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.experiments import lock_closure_synthesis as locker
from src.reporting import closure_synthesis_contract as synthesis


def _run(root: Path, *args: str) -> str:
    result = subprocess.run(
        list(args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write(root: Path, relative: str, value: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _dummy_contract(source: str) -> SimpleNamespace:
    outputs = tuple(
        [f"reports/closure_v1/11_synthesis/output_{index:02d}.csv" for index in range(23)]
        + ["reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json"]
    )
    return SimpleNamespace(
        closure_source_commit=source,
        allowed_inputs=(SimpleNamespace(path="reports/source.csv"),),
        allowed_input_paths=("reports/source.csv",),
        output_paths=outputs,
        required_unavailable_models=("P0", "P1", "A2"),
        required_hypotheses=("H1", "H2", "H3", "H4", "H5a", "H5b"),
        holm_universes={"A": 3, "B": 78, "C": 1, "D": 9, "E": 1},
        final_closure_row_count=130,
        claim_evidence_row_count=20,
        table_row_counts={
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
    )


def _input_records() -> list[dict[str, Any]]:
    return [
        {
            "path": "reports/source.csv",
            "role": "test",
            "format": "csv",
            "bytes": 4,
            "sha256": "1" * 64,
            "git_mode": "100644",
            "git_blob_oid": "2" * 40,
            "filesystem_mode": 0o644,
        }
    ]


def _install_contract_stubs(
    monkeypatch: pytest.MonkeyPatch, source: str
) -> SimpleNamespace:
    contract = _dummy_contract(source)

    def load_contract(**_kwargs: Any) -> SimpleNamespace:
        return contract

    monkeypatch.setattr(synthesis, "load_contract", load_contract)
    monkeypatch.setattr(
        synthesis,
        "collect_input_records",
        lambda *_args, **_kwargs: _input_records(),
    )
    return contract


def _make_repository(tmp_path: Path) -> tuple[Path, Path, str, str]:
    root = tmp_path / "work"
    remote = tmp_path / "origin.git"
    root.mkdir()
    _run(root, "git", "init", "--initial-branch=main")
    _run(root, "git", "config", "user.name", "Closure Test")
    _run(root, "git", "config", "user.email", "closure@example.invalid")
    _write(root, ".gitignore", "tmp/\n")
    for path_text, kind in locker.H_SCOPE.items():
        if kind == "M":
            _write(root, path_text, f"source:{path_text}\n")
            (root / path_text).chmod(int(locker.H_GIT_MODES[path_text][-3:], 8))
    _write(root, "source_marker.txt", "base\n")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "base")
    base = _run(root, "git", "rev-parse", "HEAD")
    _write(root, "source_marker.txt", "closure source\n")
    _run(root, "git", "add", "source_marker.txt")
    _run(root, "git", "commit", "-m", "closure source")
    source = _run(root, "git", "rev-parse", "HEAD")

    _run(tmp_path, "git", "init", "--bare", "--initial-branch=main", str(remote))
    _run(root, "git", "remote", "add", "origin", str(remote))
    _run(root, "git", "push", "-u", "origin", "main")
    _run(root, "git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    (root / "tmp").mkdir()
    return root, remote, base, source


def _materialize_local_h(root: Path) -> None:
    for path_text, kind in locker.H_SCOPE.items():
        if kind == "A":
            _write(root, path_text, f"H-SYN:{path_text}\n")
        else:
            path = root / path_text
            path.write_text(path.read_text(encoding="utf-8") + "H-SYN\n", encoding="utf-8")


def _publish_h1(root: Path) -> str:
    _run(root, "git", "add", *locker.H_SCOPE)
    _run(root, "git", "commit", "-m", "H-SYN H1")
    head = _run(root, "git", "rev-parse", "HEAD")
    _run(root, "git", "push", "origin", "main")
    return head


def _materialize_local_h2(root: Path) -> None:
    for path_text in locker.H2_SCOPE:
        path = root / path_text
        path.write_text(
            path.read_text(encoding="utf-8") + "H-SYN H2\n",
            encoding="utf-8",
        )


def _publish_h2(root: Path) -> str:
    _run(root, "git", "add", *locker.H2_SCOPE)
    _run(root, "git", "commit", "-m", "H-SYN H2")
    head = _run(root, "git", "rev-parse", "HEAD")
    _run(root, "git", "push", "origin", "main")
    return head


def _patch_source(
    monkeypatch: pytest.MonkeyPatch, source: str
) -> SimpleNamespace:
    monkeypatch.setattr(locker, "SOURCE_COMMIT", source)
    return _install_contract_stubs(monkeypatch, source)


def _patch_h1(monkeypatch: pytest.MonkeyPatch, h1: str) -> None:
    monkeypatch.setattr(locker, "H1_COMMIT", h1)


def _fake_state() -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    for index, path_text in enumerate(sorted(locker.H_SCOPE)):
        git_mode = locker.H_GIT_MODES[path_text]
        components.append(
            {
                "path": path_text,
                "bytes": index + 1,
                "sha256": f"{index + 1:064x}",
                "git_mode": git_mode,
                "git_blob_oid": f"{index + 1:040x}",
                "filesystem_mode": int(git_mode[-3:], 8),
            }
        )
    contract = _dummy_contract(locker.SOURCE_COMMIT)
    return {
        "repository": {"head": "a" * 40},
        "closure_source_commit": locker.SOURCE_COMMIT,
        "synthesis_implementation_commit": "a" * 40,
        "h_scope": dict(locker.H_SCOPE),
        "h_components": components,
        "allowed_inputs": _input_records(),
        "allowed_input_paths": list(contract.allowed_input_paths),
        "output_paths": list(contract.output_paths),
        "required_unavailable_models": list(contract.required_unavailable_models),
        "required_hypotheses": list(contract.required_hypotheses),
        "holm_universes": dict(contract.holm_universes),
        "final_closure_row_count": contract.final_closure_row_count,
        "claim_evidence_row_count": contract.claim_evidence_row_count,
        "table_row_counts": dict(contract.table_row_counts),
    }


def _publication_root(tmp_path: Path) -> Path:
    root = tmp_path / "publication"
    (root / "configs/closure_v1").mkdir(parents=True)
    (root / "tmp").mkdir()
    return root


def test_cli_is_closed_and_main_translates_domain_errors(
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
        raise synthesis.SynthesisContractError("closed")

    monkeypatch.setattr(locker, "generate", fail)
    assert locker.main(["--generate"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "closed"


def test_h_syn_modes_preserve_the_executable_precommit_adapter() -> None:
    assert set(locker.H_GIT_MODES) == set(locker.H_SCOPE)
    assert locker.H2_SCOPE == {
        "docs/closure_v1/PHASE4_SYNTHESIS_FREEZE.md": "M",
        "src/data/prepare_commit_artifacts.py": "M",
        "src/experiments/lock_closure_synthesis.py": "M",
        "tests/test_lock_closure_synthesis.py": "M",
        "tests/test_prepare_commit_artifacts.py": "M",
    }
    assert locker.H2_GIT_MODES == {
        path: locker.H_GIT_MODES[path] for path in locker.H2_SCOPE
    }
    assert locker.H_GIT_MODES["src/data/prepare_commit_artifacts.py"] == "100755"
    assert {
        mode
        for path, mode in locker.H_GIT_MODES.items()
        if path != "src/data/prepare_commit_artifacts.py"
    } == {"100644"}


def test_check_only_accepts_exact_local_h_scope_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    before = _run(root, "git", "status", "--porcelain=v1", "--untracked-files=all")

    result = locker.check_only(root=root, verify_remote=True)

    after = _run(root, "git", "status", "--porcelain=v1", "--untracked-files=all")
    assert result["status"] == "ready_to_publish_h"
    assert result["synthesis_implementation_commit"] is None
    assert result["writes_performed"] is False
    assert before == after
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()
    assert not (root / locker.GUARD_PATH).exists()
    assert not (root / locker.GUARD_PATH.parent).exists()


@pytest.mark.parametrize("mutation", ["extra_path", "missing_path", "tracking_ref"])
def test_check_only_rejects_path_or_ref_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    root, _remote, base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    if mutation == "extra_path":
        _write(root, "unexpected.txt", "drift\n")
    elif mutation == "missing_path":
        (root / next(path for path, kind in locker.H_SCOPE.items() if kind == "A")).unlink()
    else:
        _run(root, "git", "update-ref", "refs/remotes/origin/main", base)
    with pytest.raises(synthesis.SynthesisContractError):
        locker.check_only(root=root, verify_remote=True)
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()


def test_check_only_accepts_exact_local_h2_scope_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    h1 = _publish_h1(root)
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    before = _run(root, "git", "status", "--porcelain=v1", "--untracked-files=all")

    result = locker.check_only(root=root, verify_remote=True)

    after = _run(root, "git", "status", "--porcelain=v1", "--untracked-files=all")
    assert result["status"] == "ready_to_publish_h2"
    assert result["synthesis_implementation_commit"] is None
    assert result["writes_performed"] is False
    assert before == after
    assert {
        line.lstrip().removeprefix("M ") for line in after.splitlines()
    } == set(locker.H2_SCOPE)
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()


def test_published_preflight_requires_exact_h1_h2_chain_and_clean_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    h1 = _publish_h1(root)
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    head = _publish_h2(root)

    result = locker.check_only(root=root, verify_remote=True)
    assert result["status"] == "ready_to_generate"
    assert result["synthesis_implementation_commit"] == head

    _write(root, "unexpected.txt", "dirty\n")
    with pytest.raises(synthesis.SynthesisContractError, match="clean"):
        locker.check_only(root=root, verify_remote=True)


def test_published_preflight_rejects_nonexact_h1_commit_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _write(root, "extra_in_h.txt", "not allowed\n")
    _patch_source(monkeypatch, source)
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "bad H-SYN H1")
    _run(root, "git", "push", "origin", "main")
    h1 = _run(root, "git", "rev-parse", "HEAD")
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    with pytest.raises(synthesis.SynthesisContractError, match="scope"):
        locker.check_only(root=root, verify_remote=True)


def test_published_preflight_rejects_nonexact_h2_commit_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    h1 = _publish_h1(root)
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    _write(root, "extra_in_h2.txt", "not allowed\n")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "bad H-SYN H2")
    _run(root, "git", "push", "origin", "main")
    with pytest.raises(synthesis.SynthesisContractError, match="scope"):
        locker.check_only(root=root, verify_remote=True)


def test_published_preflight_rejects_h2_wrong_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    h1 = _publish_h1(root)
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    _publish_h2(root)
    _run(root, "git", "commit", "--allow-empty", "-m", "foreign child")
    _run(root, "git", "push", "origin", "main")
    with pytest.raises(synthesis.SynthesisContractError, match="direct, single-parent"):
        locker.check_only(root=root, verify_remote=True)


def test_published_preflight_rejects_final_mode_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    h1 = _publish_h1(root)
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    path_text = "docs/closure_v1/PHASE4_SYNTHESIS_FREEZE.md"
    (root / path_text).chmod(0o755)
    _publish_h2(root)
    with pytest.raises(synthesis.SynthesisContractError, match="Git blob"):
        locker.check_only(root=root, verify_remote=True)


def test_published_preflight_rejects_aggregate_source_h2_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    h1 = _publish_h1(root)
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    reverted = "src/data/prepare_commit_artifacts.py"
    _write(root, reverted, f"source:{reverted}\n")
    (root / reverted).chmod(0o755)
    _publish_h2(root)
    with pytest.raises(synthesis.SynthesisContractError, match="aggregate scope"):
        locker.check_only(root=root, verify_remote=True)


def test_published_preflight_rejects_h1_wrong_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _patch_source(monkeypatch, source)
    _write(root, "detour.txt", "foreign parent\n")
    _run(root, "git", "add", "detour.txt")
    _run(root, "git", "commit", "-m", "detour")
    _run(root, "git", "push", "origin", "main")
    _materialize_local_h(root)
    h1 = _publish_h1(root)
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    with pytest.raises(synthesis.SynthesisContractError, match="H1 must be"):
        locker.check_only(root=root, verify_remote=True)


def test_published_preflight_rejects_tracking_ref_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    h1 = _publish_h1(root)
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    _publish_h2(root)
    _run(root, "git", "update-ref", "refs/remotes/origin/main", h1)
    with pytest.raises(synthesis.SynthesisContractError, match="refs"):
        locker.check_only(root=root, verify_remote=True)


@pytest.mark.parametrize(
    "occupied",
    ["authority", "manifest_symlink", "r_namespace", "temp", "coordination"],
)
def test_publication_rejects_no_clobber_symlink_and_partial_namespaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, occupied: str
) -> None:
    root = _publication_root(tmp_path)
    contract = _install_contract_stubs(monkeypatch, locker.SOURCE_COMMIT)
    authority = locker._build_authority(_fake_state())
    if occupied == "authority":
        _write(root, locker.AUTHORITY_PATH.as_posix(), "foreign\n")
    elif occupied == "manifest_symlink":
        target = root / "foreign"
        target.write_text("foreign\n", encoding="utf-8")
        (root / locker.MANIFEST_PATH).symlink_to(target)
    elif occupied == "r_namespace":
        (root / synthesis.SYNTHESIS_ROOT).mkdir(parents=True)
    elif occupied == "temp":
        _write(
            root,
            (locker.AUTHORITY_PATH.parent / f"{locker.TEMP_PREFIX}foreign.tmp").as_posix(),
            "foreign\n",
        )
    else:
        (root / locker.GUARD_PATH.parent).mkdir()
    with pytest.raises(synthesis.SynthesisContractError):
        locker.publish_authority_bundle(root, authority)
    assert not (root / locker.GUARD_PATH).exists()
    assert tuple(contract.output_paths)[-1].endswith("synthesis_bundle_manifest.json")


def test_publication_is_canonical_manifest_last_and_cleans_temporaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _publication_root(tmp_path)
    _install_contract_stubs(monkeypatch, locker.SOURCE_COMMIT)
    authority = locker._build_authority(_fake_state())
    order: list[str] = []
    original = locker._link_no_clobber

    def record_link(
        source: locker._OwnedFileAt,
        destination_parent_fd: int,
        destination_name: str,
    ) -> locker._OwnedFileAt:
        order.append(destination_name)
        return original(source, destination_parent_fd, destination_name)

    monkeypatch.setattr(locker, "_link_no_clobber", record_link)
    authority_record, manifest_record = locker.publish_authority_bundle(root, authority)

    assert order == [locker.AUTHORITY_PATH.name, locker.MANIFEST_PATH.name]
    authority_bytes = (root / locker.AUTHORITY_PATH).read_bytes()
    manifest_bytes = (root / locker.MANIFEST_PATH).read_bytes()
    assert authority_bytes == synthesis.canonical_json_bytes(json.loads(authority_bytes))
    assert manifest_bytes == synthesis.canonical_json_bytes(json.loads(manifest_bytes))
    manifest = json.loads(manifest_bytes)
    assert manifest["manifest_last"] is True
    assert manifest["outputs"] == [authority_record]
    assert manifest["authority"] == authority_record
    assert manifest_record["bytes"] == len(manifest_bytes)
    assert not (root / locker.GUARD_PATH).exists()
    assert not (root / locker.GUARD_PATH.parent).exists()
    assert not any(
        path.name.startswith(locker.TEMP_PREFIX)
        for path in (root / locker.AUTHORITY_PATH.parent).iterdir()
    )
    assert (root / locker.AUTHORITY_PATH).stat().st_nlink == 1
    assert (root / locker.MANIFEST_PATH).stat().st_nlink == 1


def test_publication_creates_and_removes_owned_tmp_root_in_fresh_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "fresh-publication"
    (root / "configs/closure_v1").mkdir(parents=True)
    _install_contract_stubs(monkeypatch, locker.SOURCE_COMMIT)

    locker.publish_authority_bundle(root, locker._build_authority(_fake_state()))

    assert (root / locker.AUTHORITY_PATH).is_file()
    assert (root / locker.MANIFEST_PATH).is_file()
    assert not (root / "tmp").exists()


def test_fresh_tmp_foreign_entry_is_preserved_and_publication_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "fresh-publication"
    (root / "configs/closure_v1").mkdir(parents=True)
    _install_contract_stubs(monkeypatch, locker.SOURCE_COMMIT)

    def inject_foreign_entry() -> None:
        (root / "tmp/foreign").write_bytes(b"foreign\n")
        raise synthesis.SynthesisContractError("post-link drift")

    with pytest.raises(synthesis.SynthesisContractError, match="cleanup could not"):
        locker.publish_authority_bundle(
            root,
            locker._build_authority(_fake_state()),
            postpublish_validator=inject_foreign_entry,
        )

    assert (root / "tmp/foreign").read_bytes() == b"foreign\n"
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()


def test_manifest_link_failure_rolls_back_only_published_owned_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _publication_root(tmp_path)
    _install_contract_stubs(monkeypatch, locker.SOURCE_COMMIT)
    authority = locker._build_authority(_fake_state())
    original = locker._link_no_clobber
    order: list[str] = []

    def fail_manifest(
        source: locker._OwnedFileAt,
        destination_parent_fd: int,
        destination_name: str,
    ) -> locker._OwnedFileAt:
        order.append(destination_name)
        if destination_name == locker.MANIFEST_PATH.name:
            raise OSError("injected manifest-last failure")
        return original(source, destination_parent_fd, destination_name)

    monkeypatch.setattr(locker, "_link_no_clobber", fail_manifest)
    with pytest.raises(OSError, match="injected"):
        locker.publish_authority_bundle(root, authority)
    assert order == [locker.AUTHORITY_PATH.name, locker.MANIFEST_PATH.name]
    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()
    assert not (root / locker.GUARD_PATH).exists()
    assert not (root / locker.GUARD_PATH.parent).exists()
    assert not any(
        path.name.startswith(locker.TEMP_PREFIX)
        for path in (root / locker.AUTHORITY_PATH.parent).iterdir()
    )


def test_rollback_preserves_foreign_inode(
    tmp_path: Path,
) -> None:
    path = tmp_path / "owned"
    parent_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        owner = locker._create_owned_file_at(
            parent_fd, "owned", b"owned\n", mode=0o644, context="test"
        )
        path.unlink()
        path.write_bytes(b"foreign\n")
        with pytest.raises(
            synthesis.SynthesisContractError, match="foreign replacement"
        ):
            locker._unlink_owned_file_at(owner, context="test")
        assert path.read_bytes() == b"foreign\n"
    finally:
        os.close(parent_fd)


def test_dirfd_publication_parent_swap_preserves_foreign_and_cleans_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _publication_root(tmp_path)
    _install_contract_stubs(monkeypatch, locker.SOURCE_COMMIT)
    authority = locker._build_authority(_fake_state())
    original_link = locker._link_no_clobber
    swapped = False
    original_parent = root / "configs/closure_v1"
    moved_parent = root / "configs/original-closure_v1"

    def swap_parent_before_first_link(
        source: locker._OwnedFileAt,
        destination_parent_fd: int,
        destination_name: str,
    ) -> locker._OwnedFileAt:
        nonlocal swapped
        if not swapped:
            swapped = True
            original_parent.rename(moved_parent)
            original_parent.mkdir()
            (original_parent / "foreign").write_bytes(b"foreign\n")
        return original_link(source, destination_parent_fd, destination_name)

    monkeypatch.setattr(locker, "_link_no_clobber", swap_parent_before_first_link)
    with pytest.raises(synthesis.SynthesisContractError, match="binding drifted"):
        locker.publish_authority_bundle(root, authority)

    assert (original_parent / "foreign").read_bytes() == b"foreign\n"
    assert sorted(path.name for path in moved_parent.iterdir()) == []
    assert not (root / locker.GUARD_PATH.parent).exists()


def test_generate_builds_twice_then_publishes_without_scientific_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _publication_root(tmp_path)
    _install_contract_stubs(monkeypatch, locker.SOURCE_COMMIT)
    state = _fake_state()
    calls: list[str] = []

    def collect(
        _root: Path,
        *,
        verify_remote: bool,
        publication_phase: str | None = None,
    ) -> dict[str, Any]:
        assert _root == root.resolve()
        assert verify_remote is True
        calls.append(f"collect:{publication_phase}")
        return state

    original_publish = locker.publish_authority_bundle

    def publish(
        _root: Path, authority: dict[str, Any], **kwargs: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        calls.append("publish")
        return original_publish(_root, authority, **kwargs)

    monkeypatch.setattr(locker, "_collect_published_state", collect)
    monkeypatch.setattr(locker, "publish_authority_bundle", publish)
    result = locker.generate(root=root, verify_remote=True)
    assert calls == [
        "collect:None",
        "collect:None",
        "publish",
        "collect:guarded_prelink",
        "collect:guarded_postlink",
    ]
    assert result["status"] == "authority_bundle_written_unpublished"
    assert result["dvc_commands_run"] is False
    assert result["raw_targets_accessed"] is False
    assert result["raw_outcomes_accessed"] is False
    assert result["scientific_network_commands_run"] is False


def test_generate_postlink_snapshot_drift_rolls_back_exact2a(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _publication_root(tmp_path)
    _install_contract_stubs(monkeypatch, locker.SOURCE_COMMIT)
    state = _fake_state()
    states = [state, state, state, {**state, "allowed_input_paths": ["drift"]}]

    def collect(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return states.pop(0)

    monkeypatch.setattr(locker, "_collect_published_state", collect)
    with pytest.raises(synthesis.SynthesisContractError, match="during P-SYN"):
        locker.generate(root=root, verify_remote=False)

    assert not (root / locker.AUTHORITY_PATH).exists()
    assert not (root / locker.MANIFEST_PATH).exists()
    assert not (root / locker.GUARD_PATH.parent).exists()


def test_generate_binds_new_authority_to_h2_and_final_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    h1 = _publish_h1(root)
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    h2 = _publish_h2(root)

    result = locker.generate(root=root, verify_remote=True)

    authority_bytes = (root / locker.AUTHORITY_PATH).read_bytes()
    authority = json.loads(authority_bytes)
    assert result["synthesis_implementation_commit"] == h2
    assert authority["synthesis_implementation_commit"] == h2
    assert [record["path"] for record in authority["h_component_records"]] == sorted(
        locker.H_SCOPE
    )
    for record in authority["h_component_records"]:
        tree = _run(root, "git", "ls-tree", h2, "--", record["path"])
        assert tree.split()[2] == record["git_blob_oid"]
    manifest = json.loads((root / locker.MANIFEST_PATH).read_bytes())
    assert manifest["synthesis_implementation_commit"] == h2
    assert manifest["authority"]["sha256"] == synthesis.sha256_bytes(authority_bytes)


def test_published_h_components_are_collected_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote, _base, source = _make_repository(tmp_path)
    _materialize_local_h(root)
    _patch_source(monkeypatch, source)
    h1 = _publish_h1(root)
    _patch_h1(monkeypatch, h1)
    _materialize_local_h2(root)
    h2 = _publish_h2(root)
    observed: list[str] = []
    original = locker._component_record

    def record_once(repo: Path, commit: str, path_text: str) -> dict[str, Any]:
        observed.append(path_text)
        return original(repo, commit, path_text)

    monkeypatch.setattr(locker, "_component_record", record_once)
    state = locker._collect_published_state(root, verify_remote=True)

    assert observed == sorted(locker.H_SCOPE)
    assert state["synthesis_implementation_commit"] == h2
    assert all(record["git_blob_oid"] for record in state["h_components"])


def test_authority_fixes_digests_invariants_and_all_mutating_flags_false() -> None:
    authority = locker._build_authority(_fake_state())
    locker.validate_authority(authority)
    assert authority["closure_source_commit"] == locker.SOURCE_COMMIT
    assert authority["synthesis_implementation_commit"] == "a" * 40
    assert authority["invariants"]["required_unavailable_models"] == ["P0", "P1", "A2"]
    assert authority["invariants"]["holm_universes"] == {
        "A": 3,
        "B": 78,
        "C": 1,
        "D": 9,
        "E": 1,
    }
    assert authority["authorizations"]
    assert set(authority["authorizations"].values()) == {False}
    for record in authority["allowed_input_records"]:
        assert {"path", "bytes", "sha256", "git_mode", "git_blob_oid"} <= set(record)


def test_authority_rejects_the_archived_h1_bound_p_syn() -> None:
    state = _fake_state()
    state["synthesis_implementation_commit"] = locker.H1_COMMIT
    with pytest.raises(synthesis.SynthesisContractError, match="predates"):
        locker._build_authority(state)


def test_locker_source_has_no_scientific_or_dvc_execution_entrypoint() -> None:
    source = inspect.getsource(locker)
    assert "read_parquet" not in source
    assert "dvc add" not in source
    assert "dvc push" not in source
    assert "requests." not in source
    assert "--check-only" in source
    assert "--generate" in source
