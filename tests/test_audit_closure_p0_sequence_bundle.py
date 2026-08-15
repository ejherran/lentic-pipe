from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.experiments import audit_closure_p0_sequence_bundle as audit
from src.experiments.build_closure_pipe_sequences import (
    INPUT_COLUMNS,
    SEQUENCE_COLUMNS,
    SEQUENCE_VERSION,
    SURFACE_ID,
    TARGET_COLUMNS,
    SequenceBuildAudit,
    sequence_arrow_table,
)


REPOSITORY_ROOT = audit.PROJECT_ROOT
P0_BUNDLE_COMMIT = "b075d4f1606aa35c1b86493604c18845f2d28a2f"
P0_PHYSICAL_DVC_PATHS = {
    audit.DEFAULT_COMMON_ORIGINS,
    audit.P0_STATE_PATH,
    audit.P0_SEQUENCE_PATH,
}


@pytest.fixture(scope="module")
def historical_p0_repository(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Materialize the exact tracked P0 authority plus its immutable DVC data."""

    snapshot = tmp_path_factory.mktemp("closure_p0_historical_repository")
    for source in audit._closed_paths(pointer_present=True):
        relative = source.relative_to(REPOSITORY_ROOT)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if relative in P0_PHYSICAL_DVC_PATHS:
            payload = source.read_bytes()
        else:
            payload = subprocess.run(
                [
                    "git",
                    "show",
                    f"{P0_BUNDLE_COMMIT}:{relative.as_posix()}",
                ],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
            ).stdout
        destination.write_bytes(payload)
    (snapshot / "tmp").mkdir()

    historical_builder = (
        snapshot / "src/experiments/build_closure_pipe_sequences.py"
    ).read_bytes()
    assert len(historical_builder) == 110_034
    assert hashlib.sha256(historical_builder).hexdigest() == (
        "dc500d94c8ca4b3705d2cb849a037524e33915624cd86f9d355e5c4eebb347f6"
    )
    return snapshot


def _sample_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index, success in enumerate((True, False)):
        origin: Any = cast(Any, pd.Period("2018-01", freq="M")) + index
        row: dict[str, object] = {
            "sequence_version": SEQUENCE_VERSION,
            "surface_id": SURFACE_ID,
            "model_id": "P0",
            "base_seed": None,
            "source_id": "wqp",
            "site_id": f"site-{index}",
            "common_origin_id": f"origin-{index}",
            "evaluation_unit_id": f"unit-{index}",
            "holdout_group_id": f"group-{index}",
            "assignment_role": "development",
            "time_role": "training" if success else "model_selection",
            "origin_year_month": str(origin),
            "target_year_month": str(origin + 1),
            "history_start_year_month": str(origin - 11),
            "history_end_year_month": str(origin),
            "history_length_months": 12,
            "sequence_status": (
                "success" if success else "autoregressive_target_unavailable"
            ),
            "failure_reason": "" if success else "missing_target_state",
        }
        row.update(
            {
                column: [float(np.float32(0.1 + index * 0.01))] * 12 if success else None
                for column in INPUT_COLUMNS
            }
        )
        row.update(
            {
                column: float(np.float32(0.2 + index * 0.01)) if success else None
                for column in TARGET_COLUMNS
            }
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=SEQUENCE_COLUMNS)


def _replace_input(table: pa.Table, values: pa.Array) -> pa.Table:
    column = INPUT_COLUMNS[0]
    index = table.schema.get_field_index(column)
    field = pa.field(column, pa.list_(pa.float32(), 12), nullable=True)
    return table.set_column(index, field, values)


def test_physical_audit_accepts_outer_valid_all_null_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "EXPECTED_INTENT_ORIGINS", 2)
    evidence = audit._validate_physical_payload(sequence_arrow_table(_sample_frame()))

    assert evidence == {
        "rows": 2,
        "successful_rows": 1,
        "failed_rows": 1,
        "failed_input_tensors_all_null": len(INPUT_COLUMNS),
        "failed_targets_null": len(TARGET_COLUMNS),
    }


def test_physical_audit_rejects_parent_null_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "EXPECTED_INTENT_ORIGINS", 2)
    table = sequence_arrow_table(_sample_frame())
    values = pa.array(
        [[float(np.float32(0.1))] * 12, None],
        type=pa.list_(pa.float32(), 12),
    )

    with pytest.raises(audit.ClosureP0SequenceAuditError, match="physically valid"):
        audit._validate_physical_payload(_replace_input(table, values))


def test_physical_audit_rejects_partial_null_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "EXPECTED_INTENT_ORIGINS", 2)
    table = sequence_arrow_table(_sample_frame())
    values = pa.array(
        [
            [float(np.float32(0.1))] * 12,
            [None] * 11 + [float(np.float32(0.0))],
        ],
        type=pa.list_(pa.float32(), 12),
    )

    with pytest.raises(audit.ClosureP0SequenceAuditError, match="all-null tensor"):
        audit._validate_physical_payload(_replace_input(table, values))


def test_physical_audit_rejects_nonfinite_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "EXPECTED_INTENT_ORIGINS", 2)
    table = sequence_arrow_table(_sample_frame())
    values = pa.array(
        [
            [float(np.float32(0.1))] * 11 + [float("inf")],
            [None] * 12,
        ],
        type=pa.list_(pa.float32(), 12),
    )

    with pytest.raises(audit.ClosureP0SequenceAuditError, match="non-finite"):
        audit._validate_physical_payload(_replace_input(table, values))


def test_physical_audit_rejects_extra_physical_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "EXPECTED_INTENT_ORIGINS", 2)
    table = sequence_arrow_table(_sample_frame()).append_column(
        "forbidden_extra",
        pa.array([1, 2], type=pa.int64()),
    )

    with pytest.raises(audit.ClosureP0SequenceAuditError, match="columns/order"):
        audit._validate_physical_payload(table)


def test_physical_audit_rejects_metadata_field_type_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "EXPECTED_INTENT_ORIGINS", 2)
    table = sequence_arrow_table(_sample_frame())
    index = table.schema.get_field_index("history_length_months")
    table = table.set_column(
        index,
        pa.field("history_length_months", pa.int64(), nullable=False),
        pa.array([12, 12], type=pa.int64()),
    )

    with pytest.raises(audit.ClosureP0SequenceAuditError, match="physical schema"):
        audit._validate_physical_payload(table)


@pytest.mark.skipif(
    not (audit.PROJECT_ROOT / audit.P0_SEQUENCE_PATH).is_file(),
    reason="The ignored P0 payload is restored only in an authorized data workspace",
)
def test_real_p0_physical_schema_matches_closed_fields() -> None:
    with audit._RepoReadSession(audit.PROJECT_ROOT) as session:
        _, actual = audit._parquet_table(
            session.pin(audit.PROJECT_ROOT / audit.P0_SEQUENCE_PATH)
        )
    assert actual.schema.names == list(SEQUENCE_COLUMNS)
    for column in INPUT_COLUMNS:
        field = actual.schema.field(column)
        assert pa.types.is_fixed_size_list(field.type)
        assert field.type.list_size == 12
        assert field.type.value_type == pa.float32()


def test_summary_is_reconstructed_in_closed_order() -> None:
    assert audit._summary_bytes(_sample_frame()).decode("utf-8") == (
        "time_role,sequence_status,failure_reason,rows\n"
        "model_selection,autoregressive_target_unavailable,missing_target_state,1\n"
        "training,success,,1\n"
    )


def test_manifest_counts_preserve_failed_rows_and_delta_accounting() -> None:
    build_audit = SequenceBuildAudit(
        intent_origins=2,
        successful_origins=1,
        failed_origins=1,
        role_counts={"training": 1, "model_selection": 1},
        status_counts={"success": 1, "autoregressive_target_unavailable": 1},
        failure_reason_counts={"missing_target_state": 1},
        delta_previous_month_missing_history_values=3,
        delta_previous_month_missing_target_values=0,
    )

    counts = audit._manifest_counts(
        build_audit,
        {"holdout_overlap": 0, "post_2021_rows": 0},
    )

    assert counts["delta_previous_month_missing_count"] == 3
    assert counts["delta_previous_month_missing_history_values"] == 3
    assert counts["delta_previous_month_missing_target_values"] == 0
    assert counts["holdout_overlap"] == 0
    assert counts["post_2021_rows"] == 0


def test_strict_json_rejects_duplicate_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "PROJECT_ROOT", tmp_path)
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"status": "completed", "status": "drifted"}\n')

    with pytest.raises(audit.ClosureP0SequenceAuditError, match="duplicate key"):
        audit._strict_json_object(duplicate)


def test_cli_is_closed_and_requires_check_only() -> None:
    assert audit.parse_args(["--check-only"]).check_only is True
    with pytest.raises(SystemExit):
        audit.parse_args([])
    with pytest.raises(SystemExit):
        audit.parse_args(["--check-only", "--output", "unexpected.json"])


def test_cli_failure_is_canonical_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail() -> dict[str, Any]:
        raise audit.ClosureP0SequenceAuditError("closed failure")

    monkeypatch.setattr(audit, "audit_p0_sequence_bundle", fail)
    with pytest.raises(SystemExit) as caught:
        audit.main(["--check-only"])

    assert caught.value.code == 1
    assert capsys.readouterr().err == (
        '{"audit_version": "closure_p0_sequence_bundle_audit_v1", '
        '"error": "closed failure", '
        '"error_type": "ClosureP0SequenceAuditError", "status": "failed"}\n'
    )


def test_namespace_accepts_only_closed_pre_or_post_dvc_states() -> None:
    reports = sorted((audit.P0_MANIFEST_PATH.name, audit.P0_SUMMARY_PATH.name))
    assert audit._validate_closed_namespace(
        {"data": [audit.P0_SEQUENCE_PATH.name], "reports": reports, "guards": None}
    ) is False
    assert audit._validate_closed_namespace(
        {
            "data": sorted((audit.P0_SEQUENCE_PATH.name, audit.P0_POINTER_PATH.name)),
            "reports": reports,
            "guards": [],
        }
    ) is True
    with pytest.raises(audit.ClosureP0SequenceAuditError, match="optional exact DVC"):
        audit._validate_closed_namespace(
            {
                "data": [audit.P0_SEQUENCE_PATH.name, f"{audit.P0_POINTER_PATH.name}.tmp"],
                "reports": reports,
                "guards": None,
            }
        )


def test_p_dls_rejects_dirty_reconstruction_source() -> None:
    lock = audit._strict_json_object(audit.PROJECT_ROOT / audit.P_DLS_LOCK_PATH)
    companion = audit._strict_json_object(
        audit.PROJECT_ROOT / audit.P_DLS_COMPANION_PATH
    )
    with audit._RepoReadSession(audit.PROJECT_ROOT) as session:
        records = [
            session.pin(audit.PROJECT_ROOT / path).record
            for path in audit.RECONSTRUCTION_SOURCE_PATHS
        ]
    records[0] = {**records[0], "sha256": "0" * 64}

    with pytest.raises(audit.ClosureP0SequenceAuditError, match="differs from P-DLS"):
        audit._validate_p_dls_reference(
            lock,
            companion,
            lock_record=audit.EXPECTED_P_DLS_RECORDS[
                audit.P_DLS_LOCK_PATH.as_posix()
            ],
            reconstruction_records=records,
        )


def test_explicit_dvc_pointer_binds_exact_payload(
    tmp_path: Path,
) -> None:
    sequence = tmp_path / audit.P0_SEQUENCE_PATH
    pointer = tmp_path / audit.P0_POINTER_PATH
    sequence.parent.mkdir(parents=True)
    sequence.write_bytes(b"closed-p0-payload")
    digest = hashlib.md5(sequence.read_bytes(), usedforsecurity=False).hexdigest()
    pointer.write_text(
        "outs:\n"
        f"- md5: {digest}\n"
        f"  size: {sequence.stat().st_size}\n"
        "  hash: md5\n"
        "  path: expert_no_current.parquet\n",
        encoding="utf-8",
    )

    with audit._RepoReadSession(tmp_path) as session:
        evidence = audit._validate_dvc_pointer(
            session.pin(sequence),
            session.pin(pointer),
        )

    assert evidence["state"] == "post_dvc"
    assert evidence["pointer_payload_binding_verified"] is True
    assert evidence["cache_verified"] is False
    assert evidence["remote_verified"] is False


def test_explicit_dvc_pointer_rejects_size_drift(tmp_path: Path) -> None:
    sequence = tmp_path / audit.P0_SEQUENCE_PATH
    pointer = tmp_path / audit.P0_POINTER_PATH
    sequence.parent.mkdir(parents=True)
    sequence.write_bytes(b"closed-p0-payload")
    digest = hashlib.md5(sequence.read_bytes(), usedforsecurity=False).hexdigest()
    pointer.write_text(
        "outs:\n"
        f"- md5: {digest}\n"
        "  size: 1\n"
        "  hash: md5\n"
        "  path: expert_no_current.parquet\n",
        encoding="utf-8",
    )

    with audit._RepoReadSession(tmp_path) as session:
        with pytest.raises(audit.ClosureP0SequenceAuditError, match="does not bind"):
            audit._validate_dvc_pointer(session.pin(sequence), session.pin(pointer))


def test_pinned_reader_rejects_symlink_ancestor_and_fifo(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "payload.bin").write_bytes(b"payload")
    (tmp_path / "linked").symlink_to(real, target_is_directory=True)
    fifo = tmp_path / "payload.fifo"
    os.mkfifo(fifo)

    with audit._RepoReadSession(tmp_path) as session:
        with pytest.raises(audit.ClosureP0SequenceAuditError, match="ancestor"):
            session.pin(tmp_path / "linked" / "payload.bin")
        with pytest.raises(audit.ClosureP0SequenceAuditError, match="regular file"):
            session.pin(fifo)


def test_pinned_reader_detects_content_restore(tmp_path: Path) -> None:
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"original")
    original_mtime = payload.stat().st_mtime_ns

    with pytest.raises(audit.ClosureP0SequenceAuditError, match="Pinned audit file changed"):
        with audit._RepoReadSession(tmp_path) as session:
            session.pin(payload)
            payload.write_bytes(b"modified")
            payload.write_bytes(b"original")
            os.utime(payload, ns=(payload.stat().st_atime_ns, original_mtime))


def test_pinned_reader_closes_every_descriptor_after_read_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = tmp_path / "nested" / "payload.bin"
    payload.parent.mkdir()
    payload.write_bytes(b"payload")
    real_open = os.open
    real_close = os.close
    opened: list[int] = []
    closed: list[int] = []

    def tracked_open(*args: Any, **kwargs: Any) -> int:
        descriptor = real_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def tracked_close(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    def fail_pread(*_args: Any, **_kwargs: Any) -> bytes:
        raise OSError("injected read error")

    monkeypatch.setattr(os, "open", tracked_open)
    monkeypatch.setattr(os, "close", tracked_close)
    with audit._RepoReadSession(tmp_path) as session:
        monkeypatch.setattr(os, "pread", fail_pread)
        with pytest.raises(audit.ClosureP0SequenceAuditError, match="inspected safely"):
            session.pin(payload)

    assert opened
    assert sorted(opened) == sorted(closed)


def test_physical_drift_overrides_semantic_failure(tmp_path: Path) -> None:
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"original")

    with pytest.raises(audit.ClosureP0SequenceAuditError, match="Pinned audit file changed") as caught:
        with audit._RepoReadSession(tmp_path) as session:
            session.pin(payload)
            payload.write_bytes(b"modified")
            raise RuntimeError("injected semantic failure")

    assert isinstance(caught.value.__cause__, RuntimeError)


def _fit_evidence_frame() -> pd.DataFrame:
    roles = ["training"] * 8_352 + ["model_selection"] * 1_061 + [
        "calibration_threshold"
    ] * 319
    statuses = ["success"] * len(roles)
    reasons = [""] * len(roles)
    for start, failures in ((0, 443), (8_352, 45), (9_413, 17)):
        for index in range(start, start + failures):
            statuses[index] = "autoregressive_target_unavailable"
            reasons[index] = "missing_target_state"
    return pd.DataFrame(
        {"time_role": roles, "sequence_status": statuses, "failure_reason": reasons}
    )


def test_fit_evidence_preserves_exact_total_fit_and_calibration_failures(
) -> None:
    frame = _fit_evidence_frame()

    evidence = audit._fit_evidence(frame)

    assert evidence["observed_total_status_counts"] == audit.EXPECTED_STATUS_COUNTS
    assert evidence["observed_fit_status_counts"] == audit.EXPECTED_FIT_STATUS_COUNTS
    assert evidence["observed_calibration_failure_count"] == 17
    assert evidence["expected_temporal_slot_status"] == "model_unavailable"
    assert evidence["expected_model_or_checkpoint_emitted"] is False
    assert evidence["availability_inferred_from_closed_counts"] is True
    assert evidence["consumer_executed"] is False


def test_fit_evidence_rejects_one_missing_retained_failure(
) -> None:
    frame = _fit_evidence_frame()
    failed = frame.index[frame["sequence_status"].eq("autoregressive_target_unavailable")][0]
    frame.loc[failed, ["sequence_status", "failure_reason"]] = ["success", ""]
    with pytest.raises(audit.ClosureP0SequenceAuditError, match="total availability"):
        audit._fit_evidence(frame)


def test_boundary_evidence_derives_holdout_and_post_cutoff_rows() -> None:
    assignment = pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "development",
                "assignment_role": "development",
                "holdout_group_id": "wqp::development",
            },
            {
                "source_id": "wqp",
                "site_id": "holdout",
                "assignment_role": "internal_holdout",
                "holdout_group_id": "wqp::holdout",
            },
        ]
    )
    sequence = pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "holdout",
                "assignment_role": "development",
                "holdout_group_id": "wqp::holdout",
                "target_year_month": "2022-01",
            },
            {
                "source_id": "wqp",
                "site_id": "holdout",
                "assignment_role": "development",
                "holdout_group_id": "wqp::holdout",
                "target_year_month": "2021-12",
            },
        ]
    )

    evidence = audit._derive_boundary_evidence(
        sequence,
        assignment,
        enforce_closed=False,
    )

    assert evidence["holdout_overlap"] == 1
    assert evidence["holdout_overlap_rows"] == 2
    assert evidence["assignment_role_mismatch_rows"] == 2
    assert evidence["post_2021_rows"] == 1


def test_auditor_source_has_no_filesystem_or_process_mutator() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {
        ".mkdir(",
        ".rmdir(",
        ".touch(",
        ".unlink(",
        ".write_bytes(",
        ".write_text(",
        "os.link(",
        "os.mkdir(",
        "os.remove(",
        "os.rename(",
        "os.replace(",
        "os.unlink(",
        "subprocess.",
        "socket.",
    }

    assert isinstance(tree, ast.Module)
    assert not {call for call in forbidden_calls if call in source}
    assert "subprocess" not in source
    assert "train_closure_pipe" not in source
    assert "pq.write_table" not in source


def _external_audit_snapshot() -> dict[str, Any]:
    pointer_present = (audit.PROJECT_ROOT / audit.P0_POINTER_PATH).exists()
    paths = audit._closed_paths(pointer_present=pointer_present)
    files: dict[str, Any] = {}
    for path in paths:
        metadata = path.lstat()
        files[path.relative_to(audit.PROJECT_ROOT).as_posix()] = {
            "fingerprint": audit._fingerprint(metadata),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    directories: dict[str, Any] = {}
    for path in (
        (audit.PROJECT_ROOT / audit.P0_SEQUENCE_PATH).parent,
        (audit.PROJECT_ROOT / audit.P0_SUMMARY_PATH).parent,
        audit.PROJECT_ROOT / "tmp",
    ):
        metadata = path.lstat()
        directories[path.relative_to(audit.PROJECT_ROOT).as_posix()] = {
            "fingerprint": audit._fingerprint(metadata),
            "entries": sorted(entry.name for entry in path.iterdir()),
        }
    git_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return {"files": files, "directories": directories, "git_status": git_status}


@pytest.mark.skipif(
    not (audit.PROJECT_ROOT / audit.P0_SEQUENCE_PATH).is_file(),
    reason="The ignored P0 payload is restored only in an authorized data workspace",
)
@pytest.mark.parametrize("failure_stage", ["early", "late"])
def test_real_p0_audit_failure_is_read_only(
    failure_stage: str,
    monkeypatch: pytest.MonkeyPatch,
    historical_p0_repository: Path,
) -> None:
    monkeypatch.setattr(audit, "PROJECT_ROOT", historical_p0_repository)
    before = _external_audit_snapshot()
    descriptors_before = len(os.listdir("/proc/self/fd"))

    def injected_failure(*_args: Any, **_kwargs: Any) -> Any:
        raise audit.ClosureP0SequenceAuditError(f"injected {failure_stage} failure")

    target = "_validate_p_dls_reference" if failure_stage == "early" else "_validate_manifest"
    monkeypatch.setattr(audit, target, injected_failure)
    with pytest.raises(
        audit.ClosureP0SequenceAuditError,
        match=f"injected {failure_stage} failure",
    ):
        audit.audit_p0_sequence_bundle()

    assert len(os.listdir("/proc/self/fd")) == descriptors_before
    assert _external_audit_snapshot() == before


@pytest.mark.skipif(
    not (audit.PROJECT_ROOT / audit.P0_SEQUENCE_PATH).is_file(),
    reason="The ignored P0 payload is restored only in an authorized data workspace",
)
def test_real_p0_audit_pass_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
    historical_p0_repository: Path,
) -> None:
    monkeypatch.setattr(audit, "PROJECT_ROOT", historical_p0_repository)
    before = _external_audit_snapshot()

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("The read-only P0 auditor attempted a mutation or external call")

    with monkeypatch.context() as guarded:
        for name in ("mkdir", "unlink", "rename", "replace", "touch", "write_bytes", "write_text"):
            guarded.setattr(Path, name, forbidden)
        for name in ("link", "mkdir", "remove", "rename", "replace", "rmdir", "unlink"):
            guarded.setattr(os, name, forbidden)
        guarded.setattr(subprocess, "run", forbidden)
        guarded.setattr(socket, "socket", forbidden)
        guarded.setattr(socket, "create_connection", forbidden)
        guarded.setattr(pq, "write_table", forbidden)
        result = audit.audit_p0_sequence_bundle()

    after = _external_audit_snapshot()
    assert before == after
    assert result["status"] == "validated"
    assert result["pinned_read_session_verified"] is True
    assert result["builder_reconstruction_executed"] is True
    assert result["builder_cli_executed"] is False
    assert result["fit_or_model_construction_executed"] is False
    assert result["fit_availability"]["consumer_executed"] is False


@pytest.mark.skipif(
    not (audit.PROJECT_ROOT / audit.P0_SEQUENCE_PATH).is_file(),
    reason="The ignored P0 payload is restored only in an authorized data workspace",
)
def test_real_p0_cli_is_repeatable_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
    historical_p0_repository: Path,
) -> None:
    monkeypatch.setattr(audit, "PROJECT_ROOT", historical_p0_repository)
    before = _external_audit_snapshot()
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(REPOSITORY_ROOT), environment.get("PYTHONPATH", "")),
        )
    )
    command = [sys.executable, "-B", audit.AUDITOR_PATH.as_posix(), "--check-only"]
    completed = [
        subprocess.run(
            command,
            cwd=audit.PROJECT_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        for _ in range(2)
    ]
    after = _external_audit_snapshot()

    assert before == after
    assert [item.returncode for item in completed] == [0, 0]
    assert [item.stderr for item in completed] == ["", ""]
    assert completed[0].stdout == completed[1].stdout
    assert json.loads(completed[0].stdout)["status"] == "validated"
