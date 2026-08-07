from __future__ import annotations

import ast
import copy
import hashlib
import os
from pathlib import Path
import socket
import stat
import subprocess
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.experiments import (
    audit_closure_p1_seed_20260613_sequence_bundle as audit,
)
from src.experiments.build_closure_pipe_sequences import (
    INPUT_COLUMNS,
    SEQUENCE_COLUMNS,
    SEQUENCE_VERSION,
    SURFACE_ID,
    TARGET_COLUMNS,
    SequenceBuildAudit,
    sequence_arrow_table,
)


def _sample_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index, success in enumerate((True, False)):
        origin: Any = cast(Any, pd.Period("2018-01", freq="M")) + index
        row: dict[str, object] = {
            "sequence_version": SEQUENCE_VERSION,
            "surface_id": SURFACE_ID,
            "model_id": "P1",
            "base_seed": audit.BASE_SEED,
            "source_id": "wqp",
            "site_id": f"site-{index}",
            "common_origin_id": f"origin-{index}",
            "evaluation_unit_id": f"unit-{index}",
            "holdout_group_id": f"wqp::site-{index}",
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
                column: [float(np.float32(0.1 + index * 0.01))] * 12
                if success
                else None
                for column in INPUT_COLUMNS
            }
        )
        row.update(
            {
                column: float(np.float32(0.2 + index * 0.01))
                if success
                else None
                for column in TARGET_COLUMNS
            }
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=SEQUENCE_COLUMNS)


def _two_row_payload(monkeypatch: pytest.MonkeyPatch) -> pa.Table:
    monkeypatch.setattr(audit, "EXPECTED_INTENT_ORIGINS", 2)
    monkeypatch.setattr(
        audit,
        "EXPECTED_STATUS_COUNTS",
        {"success": 1, "autoregressive_target_unavailable": 1},
    )
    monkeypatch.setattr(
        audit,
        "EXPECTED_ROLE_COUNTS",
        {"training": 1, "model_selection": 1},
    )
    return sequence_arrow_table(_sample_frame())


def _replace_column(
    table: pa.Table,
    column: str,
    field: pa.Field,
    values: pa.Array,
) -> pa.Table:
    return table.set_column(table.schema.get_field_index(column), field, values)


def test_physical_payload_accepts_seed_20260613_and_closed_null_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = audit._validate_physical_payload(_two_row_payload(monkeypatch))

    assert evidence == {
        "rows": 2,
        "successful_rows": 1,
        "failed_rows": 1,
        "failed_input_tensors_all_null": len(INPUT_COLUMNS),
        "failed_targets_null": len(TARGET_COLUMNS),
    }


@pytest.mark.parametrize(
    "seeds",
    (
        [None, None],
        [audit.BASE_SEED, None],
        [audit.BASE_SEED, 1729],
    ),
    ids=("all-null", "partially-null", "cross-seed"),
)
def test_physical_payload_rejects_nonexact_seed(
    seeds: list[int | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = _two_row_payload(monkeypatch)
    table = _replace_column(
        table,
        "base_seed",
        pa.field("base_seed", pa.int64(), nullable=True),
        pa.array(seeds, type=pa.int64()),
    )

    with pytest.raises(
        audit.ClosureP1Seed20260613SequenceAuditError, match="base_seed"
    ):
        audit._validate_physical_payload(table)


@pytest.mark.parametrize("mutation", ("extra-column", "failed-input", "nan-target"))
def test_physical_payload_rejects_schema_null_or_finitude_drift(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = _two_row_payload(monkeypatch)
    if mutation == "extra-column":
        table = table.append_column("forbidden", pa.array([1, 2], type=pa.int64()))
    elif mutation == "failed-input":
        column = INPUT_COLUMNS[0]
        values = table.column(column).combine_chunks().to_pylist()
        values[1][0] = 0.0
        table = _replace_column(
            table,
            column,
            pa.field(column, pa.list_(pa.float32(), 12), nullable=True),
            pa.array(values, type=pa.list_(pa.float32(), 12)),
        )
    else:
        column = TARGET_COLUMNS[0]
        table = _replace_column(
            table,
            column,
            pa.field(column, pa.float32(), nullable=True),
            pa.array([float("nan"), None], type=pa.float32()),
        )

    with pytest.raises(audit.ClosureP1Seed20260613SequenceAuditError):
        audit._validate_physical_payload(table)


def _valid_namespace(*, pointer: bool = False) -> dict[str, Any]:
    data = [
        "seed_1729.parquet",
        "seed_1729.parquet.dvc",
        "seed_20260612.parquet",
        "seed_20260612.parquet.dvc",
        "seed_20260613.parquet",
    ]
    if pointer:
        data.append("seed_20260613.parquet.dvc")
    return {
        "data": sorted(data),
        "reports": sorted(
            (
                "seed_1729_manifest.json",
                "seed_1729_summary.csv",
                "seed_20260612_manifest.json",
                "seed_20260612_summary.csv",
                "seed_20260613_manifest.json",
                "seed_20260613_summary.csv",
            )
        ),
        "sequence_guards": None,
        "model_files": None,
        "model_reports": sorted(
            (
                "seed_1729_manifest.json",
                "seed_1729_report.md",
                "seed_20260612_manifest.json",
                "seed_20260612_report.md",
            )
        ),
        "consumer_guards": None,
        "protocol": [],
    }


@pytest.mark.parametrize("pointer", (False, True), ids=("pre-dvc", "post-dvc"))
def test_namespace_accepts_exact_ordered_progression(pointer: bool) -> None:
    evidence = audit._validate_closed_namespace(_valid_namespace(pointer=pointer))

    assert evidence["pointer_present"] is pointer
    assert evidence["slot_integrity"]["registered_slot_present_count"] == (
        4 if pointer else 3
    )
    assert evidence["slot_integrity"]["registered_slot_absent_count"] == (
        24 if pointer else 25
    )
    assert evidence["progression_observation"]["prior_seed_present_count"] == 12
    assert evidence["progression_observation"]["prior_seeds"] == [1729, 20260612]
    assert evidence["registered_namespace"]["registered_present_count"] == (
        16 if pointer else 15
    )
    assert evidence["registered_namespace"]["registered_absent_count"] == (
        124 if pointer else 125
    )
    assert (
        evidence["progression_observation"][
            "pre_consumer_and_pre_e0_m_clear_now"
        ]
        is True
    )


@pytest.mark.parametrize(
    ("key", "entry", "raises_immediately"),
    (
        ("data", "seed_20260613.parquet.tmp", True),
        ("data", "seed_1729.parquet.dvc.tmp", True),
        ("reports", "unregistered.json", True),
        ("model_reports", "seed_20260613_report.md", False),
        ("data", "seed_20260614.parquet", False),
        ("protocol", "model_lock.yaml", False),
        ("protocol", "outcome_access_log.jsonl", False),
    ),
)
def test_namespace_rejects_or_closes_forbidden_progression(
    key: str,
    entry: str,
    raises_immediately: bool,
) -> None:
    snapshot = _valid_namespace()
    values = snapshot[key]
    if values is None:
        values = []
        snapshot[key] = values
    cast(list[str], values).append(entry)
    cast(list[str], values).sort()

    if raises_immediately:
        with pytest.raises(audit.ClosureP1Seed20260613SequenceAuditError):
            audit._validate_closed_namespace(snapshot)
        return
    evidence = audit._validate_closed_namespace(snapshot)
    with pytest.raises(
        audit.ClosureP1Seed20260613SequenceAuditError, match="pre-consumer"
    ):
        audit._require_pre_consumer_progression_clear(evidence)


@pytest.mark.parametrize(
    "missing",
    ("seed_1729_report.md", "seed_20260612_report.md"),
)
def test_namespace_requires_both_six_record_predecessors(missing: str) -> None:
    snapshot = _valid_namespace()
    cast(list[str], snapshot["model_reports"]).remove(missing)

    with pytest.raises(
        audit.ClosureP1Seed20260613SequenceAuditError, match="predecessor"
    ):
        audit._validate_closed_namespace(snapshot)


def _pinned(path: Path, payload: bytes) -> SimpleNamespace:
    return SimpleNamespace(
        payload=payload,
        relative_path=path,
        record={
            "path": path.as_posix(),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
    )


def test_optional_dvc_pointer_binds_seed_20260613_payload() -> None:
    payload = b"closed-p1-seed-20260613-payload"
    digest = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    pointer = (
        "outs:\n"
        f"- md5: {digest}\n"
        f"  size: {len(payload)}\n"
        "  hash: md5\n"
        "  path: seed_20260613.parquet\n"
    ).encode("utf-8")

    pre = audit._validate_dvc_pointer(_pinned(audit.P1_SEQUENCE_PATH, payload), None)
    post = audit._validate_dvc_pointer(
        _pinned(audit.P1_SEQUENCE_PATH, payload),
        _pinned(audit.P1_POINTER_PATH, pointer),
    )

    assert pre["state"] == "pre_dvc"
    assert post["state"] == "post_dvc"
    assert post["pointer_payload_binding_verified"] is True
    assert post["cache_verified"] is False
    assert post["remote_verified"] is False
    assert post["dvc_command_executed_by_auditor"] is False


@pytest.mark.parametrize("mutation", ("digest", "size", "path"))
def test_optional_dvc_pointer_rejects_drift(mutation: str) -> None:
    payload = b"closed-p1-seed-20260613-payload"
    digest = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    size = len(payload)
    name = "seed_20260613.parquet"
    if mutation == "digest":
        digest = "0" * 32
    elif mutation == "size":
        size += 1
    else:
        name = "seed_1729.parquet"
    pointer = (
        "outs:\n"
        f"- md5: {digest}\n"
        f"  size: {size}\n"
        "  hash: md5\n"
        f"  path: {name}\n"
    ).encode("utf-8")

    with pytest.raises(
        audit.ClosureP1Seed20260613SequenceAuditError, match="pointer"
    ):
        audit._validate_dvc_pointer(
            _pinned(audit.P1_SEQUENCE_PATH, payload),
            _pinned(audit.P1_POINTER_PATH, pointer),
        )


def _strict_physical_json(path: Path) -> dict[str, Any]:
    payload = (audit.PROJECT_ROOT / path).read_bytes()
    return audit._decode_strict_json(payload, path=path.as_posix())


def test_state_manifest_accepts_seed_20260613_and_exact_state_binding() -> None:
    payload = _strict_physical_json(audit.P1_STATE_MANIFEST_PATH)
    record = audit._physical_record(audit.EXPECTED_INPUT_RECORDS[-1])

    audit._validate_state_manifest(payload, state_record=record)


@pytest.mark.parametrize("mutation", ("seed", "outcome", "state-binding"))
def test_state_manifest_rejects_identity_or_binding_drift(mutation: str) -> None:
    payload = _strict_physical_json(audit.P1_STATE_MANIFEST_PATH)
    record = audit._physical_record(audit.EXPECTED_INPUT_RECORDS[-1])
    if mutation == "seed":
        payload["base_seed"] = 1729
    elif mutation == "outcome":
        payload["future_outcomes_accessed"] = True
    else:
        outputs = cast(list[dict[str, Any]], payload["outputs"])
        for output in outputs:
            if output.get("path") == audit.P1_STATE_PATH.as_posix():
                output["sha256"] = "0" * 64

    with pytest.raises(audit.ClosureP1Seed20260613SequenceAuditError):
        audit._validate_state_manifest(payload, state_record=record)


def _mj_physical_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for expected in (
        *audit.EXPECTED_E0_MJ_INPUT_RECORDS,
        *audit.EXPECTED_E0_MJ_PATCH_RECORDS,
    ):
        records[str(expected["path"])] = audit._physical_record(expected)
    return records


def _validate_physical_mj(
    lock: dict[str, Any],
    companion: dict[str, Any],
) -> dict[str, Any]:
    return audit._validate_e0_mj_reference(
        lock,
        companion,
        lock_record=audit._physical_record(audit.EXPECTED_INPUT_RECORDS[10]),
        physical_records=_mj_physical_records(),
    )


def test_e0_mj_reference_accepts_exact_post_consumption_authority() -> None:
    evidence = _validate_physical_mj(
        _strict_physical_json(audit.E0_MJ_LOCK_PATH),
        _strict_physical_json(audit.E0_MJ_COMPANION_PATH),
    )

    assert evidence["physical_input_count"] == 22
    assert evidence["physical_patch_component_count"] == 7
    assert evidence["state_bundle_physically_reconciled"] is True
    assert evidence["prior_p1_1729_physically_reconciled"] is True
    assert evidence["prior_p1_20260612_physically_reconciled"] is True
    assert evidence["effective_loader_called_by_auditor"] is False
    assert evidence["one_shot_reconsumed_by_auditor"] is False


@pytest.mark.parametrize(
    "mutation",
    (
        "authorization",
        "anfis",
        "predecessor",
        "current-predecessor",
        "input",
        "historical",
        "script",
    ),
)
def test_e0_mj_reference_rejects_semantic_or_binding_drift(mutation: str) -> None:
    lock = copy.deepcopy(_strict_physical_json(audit.E0_MJ_LOCK_PATH))
    companion = copy.deepcopy(_strict_physical_json(audit.E0_MJ_COMPANION_PATH))
    if mutation == "authorization":
        cast(dict[str, Any], lock["authorizations"])["p1_consumer_authorized"] = True
    elif mutation == "anfis":
        cast(dict[str, Any], lock["anfis_20260613_state_bundle"])[
            "future_outcomes_accessed"
        ] = True
    elif mutation == "predecessor":
        cast(list[dict[str, Any]], cast(dict[str, Any], lock["p1_1729_publication"])["records"])[0][
            "sha256"
        ] = "0" * 64
    elif mutation == "current-predecessor":
        cast(
            list[dict[str, Any]],
            cast(dict[str, Any], lock["p1_20260612_publication"])["records"],
        )[0]["sha256"] = "0" * 64
    elif mutation == "input":
        cast(list[dict[str, Any]], companion["inputs"])[0]["sha256"] = "0" * 64
    elif mutation == "historical":
        cast(list[dict[str, Any]], companion["historical_inputs"])[0][
            "hash_source"
        ] = "physical_file"
    else:
        cast(dict[str, Any], companion["script"])["sha256"] = "0" * 64

    with pytest.raises(audit.ClosureP1Seed20260613SequenceAuditError):
        _validate_physical_mj(lock, companion)


def _closed_build_audit() -> SequenceBuildAudit:
    return SequenceBuildAudit(
        intent_origins=9_732,
        successful_origins=9_227,
        failed_origins=505,
        role_counts=dict(audit.EXPECTED_ROLE_COUNTS),
        status_counts=dict(audit.EXPECTED_STATUS_COUNTS),
        failure_reason_counts=dict(audit.EXPECTED_FAILURE_REASON_COUNTS),
        delta_previous_month_missing_history_values=496,
        delta_previous_month_missing_target_values=0,
    )


def _validate_physical_sequence_manifest(payload: dict[str, Any]) -> None:
    audit._validate_manifest(
        payload,
        builder_record=audit._physical_record(audit.EXPECTED_INPUT_RECORDS[8]),
        input_records=[dict(record) for record in audit.EXPECTED_INPUT_RECORDS],
        output_records=[
            dict(audit.EXPECTED_BUNDLE_RECORDS[path.as_posix()])
            for path in (audit.P1_SEQUENCE_PATH, audit.P1_SUMMARY_PATH)
        ],
        audit=_closed_build_audit(),
        boundary={"holdout_overlap": 0, "post_2021_rows": 0},
    )


def test_sequence_manifest_and_summary_match_closed_bundle() -> None:
    payload_bytes = (audit.PROJECT_ROOT / audit.P1_MANIFEST_PATH).read_bytes()
    payload = audit._decode_strict_json(
        payload_bytes, path=audit.P1_MANIFEST_PATH.as_posix()
    )
    _validate_physical_sequence_manifest(payload)
    audit._assert_canonical_json(
        payload_bytes, payload, path=audit.P1_MANIFEST_PATH.as_posix()
    )
    expected_summary = (
        "time_role,sequence_status,failure_reason,rows\n"
        "calibration_threshold,autoregressive_target_unavailable,missing_target_state,17\n"
        "calibration_threshold,success,,302\n"
        "model_selection,autoregressive_target_unavailable,missing_target_state,45\n"
        "model_selection,success,,1016\n"
        "training,autoregressive_target_unavailable,missing_target_state,443\n"
        "training,success,,7909\n"
    ).encode("utf-8")
    assert (audit.PROJECT_ROOT / audit.P1_SUMMARY_PATH).read_bytes() == expected_summary


@pytest.mark.parametrize("mutation", ("seed", "mapping", "input", "count", "dialect"))
def test_sequence_manifest_rejects_closed_contract_drift(mutation: str) -> None:
    payload = copy.deepcopy(_strict_physical_json(audit.P1_MANIFEST_PATH))
    if mutation == "seed":
        payload["base_seed"] = 1729
    elif mutation == "mapping":
        cast(dict[str, Any], payload["input_state_mapping"])["yN"] = "yN"
    elif mutation == "input":
        cast(list[dict[str, Any]], payload["inputs"])[0]["sha256"] = "0" * 64
    elif mutation == "count":
        cast(dict[str, Any], payload["counts"])["intent_origins"] = 9_733
    else:
        payload["unexpected"] = True

    with pytest.raises(
        audit.ClosureP1Seed20260613SequenceAuditError, match="manifest"
    ):
        _validate_physical_sequence_manifest(payload)


def test_strict_json_rejects_duplicate_keys_and_noncanonical_bytes() -> None:
    with pytest.raises(
        audit.ClosureP1Seed20260613SequenceAuditError, match="duplicate key"
    ):
        audit._decode_strict_json(
            b'{"status":"completed","status":"drifted"}\n', path="duplicate.json"
        )
    payload = {"status": "completed"}
    with pytest.raises(
        audit.ClosureP1Seed20260613SequenceAuditError, match="canonical"
    ):
        audit._assert_canonical_json(
            b'{"status": "completed"}', payload, path="noncanonical.json"
        )


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


def test_fit_evidence_keeps_model_unavailable_denominators() -> None:
    evidence = audit._fit_evidence(_fit_evidence_frame())

    assert evidence["observed_fit_status_counts"] == {
        "success": 8_925,
        "autoregressive_target_unavailable": 488,
    }
    assert evidence["observed_calibration_failure_count"] == 17
    assert evidence["available"] is False
    assert evidence["expected_fit_status"] == "not_attempted"
    assert evidence["expected_failure_reason"] == "sequence_fit_rows_unavailable"


def test_pinned_reader_rejects_symlink_ancestor_and_fifo(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "payload.bin").write_bytes(b"payload")
    (tmp_path / "linked").symlink_to(real, target_is_directory=True)
    fifo = tmp_path / "payload.fifo"
    os.mkfifo(fifo)

    with audit.historical.secure_reads._RepoReadSession(tmp_path) as session:
        with pytest.raises(
            audit.historical.secure_reads.ClosureP0SequenceAuditError,
            match="ancestor",
        ):
            session.pin(tmp_path / "linked" / "payload.bin")
        with pytest.raises(
            audit.historical.secure_reads.ClosureP0SequenceAuditError,
            match="regular file",
        ):
            session.pin(fifo)


def test_pinned_reader_detects_mutate_then_restore(tmp_path: Path) -> None:
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"original")
    original_mtime = payload.stat().st_mtime_ns

    with pytest.raises(
        audit.historical.secure_reads.ClosureP0SequenceAuditError,
        match="Pinned audit file changed",
    ):
        with audit.historical.secure_reads._RepoReadSession(tmp_path) as session:
            session.pin(payload)
            payload.write_bytes(b"modified")
            payload.write_bytes(b"original")
            os.utime(payload, ns=(payload.stat().st_atime_ns, original_mtime))


def test_auditor_source_has_no_mutator_process_network_or_effective_gate() -> None:
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
        "requests.",
        "urllib.",
        "pq.write_table",
        "train_closure_pipe",
        "load_and_validate_p1_sequence_seed_20260613_patch_lock(",
        "require_p1_sequence_seed_20260613_authorized(",
    }

    assert isinstance(tree, ast.Module)
    assert not {call for call in forbidden_calls if call in source}


def test_cli_is_closed_and_requires_check_only() -> None:
    assert audit.parse_args(["--check-only"]).check_only is True
    with pytest.raises(SystemExit):
        audit.parse_args([])
    with pytest.raises(SystemExit):
        audit.parse_args(["--check-only", "--output", "unexpected.json"])


def _lexical_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _fingerprint(path: Path) -> tuple[int, int, int, int, int, int, int]:
    metadata = path.lstat()
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _real_audit_snapshot() -> dict[str, Any]:
    paths = [
        audit.PROJECT_ROOT / audit.P1_SEQUENCE_PATH,
        audit.PROJECT_ROOT / audit.P1_SUMMARY_PATH,
        audit.PROJECT_ROOT / audit.P1_MANIFEST_PATH,
        audit.PROJECT_ROOT / audit.P1_POINTER_PATH,
    ]
    files: dict[str, Any] = {}
    for path in paths:
        if not _lexical_exists(path):
            continue
        files[path.relative_to(audit.PROJECT_ROOT).as_posix()] = {
            "fingerprint": _fingerprint(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    directories: dict[str, Any] = {}
    for relative in audit.NAMESPACE_DIRECTORIES.values():
        path = audit.PROJECT_ROOT / relative
        key = path.relative_to(audit.PROJECT_ROOT).as_posix()
        if not _lexical_exists(path):
            directories[key] = None
            continue
        directories[key] = {
            "fingerprint": _fingerprint(path),
            "entries": sorted(entry.name for entry in path.iterdir()),
        }
    git_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=audit.PROJECT_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return {"files": files, "directories": directories, "git_status": git_status}


@pytest.mark.skipif(
    not (audit.PROJECT_ROOT / audit.P1_SEQUENCE_PATH).is_file(),
    reason="The ignored P1/20260613 payload exists only in the authorized workspace",
)
def test_real_p1_seed_20260613_audit_pass_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _real_audit_snapshot()
    descriptors_before = len(os.listdir("/proc/self/fd"))

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("The P1/20260613 auditor attempted a mutation or external call")

    with monkeypatch.context() as guarded:
        for name in (
            "mkdir",
            "unlink",
            "rename",
            "replace",
            "touch",
            "write_bytes",
            "write_text",
        ):
            guarded.setattr(Path, name, forbidden)
        for name in ("link", "mkdir", "remove", "rename", "replace", "rmdir", "unlink"):
            guarded.setattr(os, name, forbidden)
        guarded.setattr(subprocess, "run", forbidden)
        guarded.setattr(socket, "socket", forbidden)
        guarded.setattr(socket, "create_connection", forbidden)
        guarded.setattr(pq, "write_table", forbidden)
        result = audit.audit_p1_seed_20260613_sequence_bundle()

    assert len(os.listdir("/proc/self/fd")) == descriptors_before
    assert _real_audit_snapshot() == before
    assert result["status"] == "validated"
    assert result["base_seed"] == audit.BASE_SEED
    assert result["counts"]["intent_origins"] == 9_732
    assert result["counts"]["successful_origins"] == 9_227
    assert result["counts"]["failed_origins"] == 505
    assert result["development_boundary"]["holdout_overlap"] == 0
    assert result["development_boundary"]["post_2021_rows"] == 0
    assert result["physical_evidence"]["rows"] == 9_732
    assert result["pinned_read_session_verified"] is True
    assert result["builder_reconstruction_executed"] is True
    assert result["builder_cli_executed"] is False
    assert result["one_shot_reconsumed_by_auditor"] is False
    assert result["fit_or_model_construction_executed_by_auditor"] is False
    assert result["dvc_operation_executed_by_auditor"] is False
    assert result["future_outcomes_accessed_by_auditor"] is False


@pytest.mark.skipif(
    not (audit.PROJECT_ROOT / audit.P1_SEQUENCE_PATH).is_file(),
    reason="The ignored P1/20260613 payload exists only in the authorized workspace",
)
def test_real_p1_seed_20260613_late_failure_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _real_audit_snapshot()
    descriptors_before = len(os.listdir("/proc/self/fd"))
    original = audit._validate_physical_payload

    def injected_failure(table: pa.Table) -> dict[str, int]:
        original(table)
        raise audit.ClosureP1Seed20260613SequenceAuditError(
            "injected late audit failure"
        )

    monkeypatch.setattr(audit, "_validate_physical_payload", injected_failure)
    with pytest.raises(
        audit.ClosureP1Seed20260613SequenceAuditError,
        match="injected late audit failure",
    ):
        audit.audit_p1_seed_20260613_sequence_bundle()

    assert len(os.listdir("/proc/self/fd")) == descriptors_before
    assert _real_audit_snapshot() == before
