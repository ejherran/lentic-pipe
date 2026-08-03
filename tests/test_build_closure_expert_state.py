from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.experiments import build_closure_expert_state as expert_adapter
from src.experiments.closure_contract import load_yaml_mapping
from src.experiments.closure_development_guard import (
    DevelopmentGate,
    TimeRoleBounds,
)
from src.experiments.closure_runtime_contract import (
    DEFAULT_RUNTIME_CONFIG,
    ClosureRuntimeContractError,
)


def _runtime() -> dict[str, Any]:
    return load_yaml_mapping(DEFAULT_RUNTIME_CONFIG)


def _gate(*, development_sites: tuple[str, ...] = ("A",), holdout_sites: tuple[str, ...] = ("H",)) -> DevelopmentGate:
    rows = [
        {
            "source_id": "wqp",
            "site_id": site_id,
            "holdout_group_id": f"wqp::{site_id}",
            "assignment_role": "development",
        }
        for site_id in development_sites
    ]
    rows.extend(
        {
            "source_id": "wqp",
            "site_id": site_id,
            "holdout_group_id": f"wqp::{site_id}",
            "assignment_role": "internal_holdout",
        }
        for site_id in holdout_sites
    )
    return DevelopmentGate(
        assignment_path=Path("assignment.csv"),
        assignment_sha256="a" * 64,
        holdout_manifest_path=Path("holdout.json"),
        holdout_manifest_sha256="b" * 64,
        protocol_lock_path=Path("protocol.json"),
        protocol_lock_sha256="c" * 64,
        locked_repository_head="d" * 40,
        repository_validated=False,
        bounds=TimeRoleBounds(
            training_end="2018-12",
            model_selection_start="2019-01",
            model_selection_end="2020-12",
            calibration_threshold_start="2021-01",
            calibration_threshold_end="2021-12",
            locked_evaluation_start="2022-01",
        ),
        _assignment=pd.DataFrame(rows),
    )


def _projected_rows() -> pd.DataFrame:
    rows = [
        ("2019-12", 0.8, 0.6, 0.7),
        ("2020-01", 0.3, 0.9, 0.2),
        ("2020-03", 0.4, 0.8, 0.6),
    ]
    return pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "A",
                "year_month": month,
                "yN": y_n,
                "yF": y_f,
                "yT_no_chla": y_t,
                "sigma_N": 0.2,
                "sigma_F": 0.3,
                "sigma_T_no_chla": 0.4,
                "assignment_role": "development",
                "time_role": "model_selection",
                # Poisoned siblings are deliberately outside the physical
                # projection and must never survive the output allowlist.
                "mean_chlorophyll_a_ugL": 9999.0,
                "yT": 0.99,
                "delta_yT": 999.0,
            }
            for month, y_n, y_f, y_t in rows
        ]
    )


def test_expert_adapter_uses_exact_month_deltas_and_closed_allowlist() -> None:
    observed = expert_adapter.build_expert_no_current_state(
        _projected_rows(),
        runtime=_runtime(),
        gate=_gate(),
    )

    expected_columns = _runtime()["primary_autoregressive_state"]["state_export"][
        "p0_output_columns"
    ]
    assert list(observed.columns) == expected_columns
    by_month = observed.set_index("year_month")
    assert by_month.loc["2020-01", "delta_yN"] == pytest.approx(-0.5)
    assert by_month.loc["2020-01", "delta_yF"] == pytest.approx(0.3)
    assert by_month.loc["2020-01", "delta_yT_no_chla"] == pytest.approx(-0.5)
    assert bool(by_month.loc["2020-01", "delta_previous_month_missing"]) is False
    assert by_month.loc["2020-03", "delta_yN"] == 0.0
    assert by_month.loc["2020-03", "delta_yF"] == 0.0
    assert by_month.loc["2020-03", "delta_yT_no_chla"] == 0.0
    assert bool(by_month.loc["2020-03", "delta_previous_month_missing"]) is True
    assert "mean_chlorophyll_a_ugL" not in observed
    assert "yT" not in observed


def test_expert_adapter_rejects_holdout_and_post_2021_rows() -> None:
    holdout = _projected_rows().assign(site_id="H", assignment_role="holdout")
    with pytest.raises(Exception, match="holdout"):
        expert_adapter.build_expert_no_current_state(
            holdout,
            runtime=_runtime(),
            gate=_gate(),
        )

    future = _projected_rows().iloc[[0]].assign(year_month="2022-01")
    with pytest.raises(ClosureRuntimeContractError, match="after 2021-12"):
        expert_adapter.build_expert_no_current_state(
            future,
            runtime=_runtime(),
            gate=_gate(),
        )


def test_expert_adapter_rejects_duplicate_and_out_of_range_state() -> None:
    duplicated = pd.concat([_projected_rows(), _projected_rows().iloc[[0]]], ignore_index=True)
    with pytest.raises(ClosureRuntimeContractError, match="duplicate"):
        expert_adapter.build_expert_no_current_state(
            duplicated,
            runtime=_runtime(),
            gate=_gate(),
        )

    invalid = _projected_rows()
    invalid.loc[0, "sigma_N"] = 1.1
    with pytest.raises(ClosureRuntimeContractError, match=r"finite in \[0, 1\]"):
        expert_adapter.build_expert_no_current_state(
            invalid,
            runtime=_runtime(),
            gate=_gate(),
        )


def test_physical_expert_scan_projects_only_safe_columns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = copy.deepcopy(_runtime())
    source = tmp_path / "state.parquet"
    pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": site_id,
                "year_month": "2020-01",
                "yN": 0.2,
                "yF": 0.3,
                "yT_no_chla": 0.4,
                "sigma_N": 0.2,
                "sigma_F": 0.3,
                "sigma_T_no_chla": 0.4,
                "mean_chlorophyll_a_ugL": 9999.0,
                "yT": 0.99,
            }
            for site_id in ("A", "H")
        ]
    ).to_parquet(source, index=False)
    runtime["primary_autoregressive_state"]["state_export"]["p0_source_path"] = str(source)
    monkeypatch.setattr(expert_adapter, "resolve_repo_path", lambda value: Path(value))

    observed, audit = expert_adapter.load_projected_p0_anchor(
        source,
        runtime=runtime,
        gate=_gate(),
    )

    assert observed["site_id"].tolist() == ["A"]
    assert "mean_chlorophyll_a_ugL" not in observed
    assert "yT" not in observed
    assert audit.returned_rows == 1
    assert audit.role_counts == {"model_selection": 1}


def test_expert_bundle_writes_manifest_last(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, Path]] = []
    output = tmp_path / "state.parquet"
    lineage = tmp_path / "lineage.json"
    manifest = tmp_path / "manifest.json"

    monkeypatch.setattr(
        expert_adapter,
        "_write_parquet_atomic",
        lambda frame, path: calls.append(("parquet", path)),
    )
    monkeypatch.setattr(
        expert_adapter,
        "_write_json_atomic",
        lambda payload, path: calls.append(("json", path)),
    )
    monkeypatch.setattr(
        expert_adapter,
        "_file_record",
        lambda path: {"path": path.as_posix(), "bytes": 1, "sha256": "a" * 64},
    )

    expert_adapter.write_expert_bundle(
        pd.DataFrame({"x": [1]}),
        output_path=output,
        lineage_path=lineage,
        manifest_path=manifest,
        lineage={"status": "passed"},
        manifest_base={"status": "completed"},
    )

    assert calls == [("parquet", output), ("json", lineage), ("json", manifest)]


def test_expert_builder_fails_before_gate_or_row_io_after_e0_dl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        expert_adapter,
        "load_and_validate_development_runtime",
        lambda *args, **kwargs: (
            _runtime(),
            {"implementation_lock_present": True, "fit_authorized": True},
        ),
    )
    monkeypatch.setattr(
        expert_adapter,
        "load_development_gate",
        lambda: (_ for _ in ()).throw(AssertionError("development gate loaded")),
    )

    with pytest.raises(ClosureRuntimeContractError, match="pre-E0-DL"):
        expert_adapter.materialize_expert_state()


@pytest.mark.parametrize("reason", ["dirty worktree", "stale remote main"])
def test_expert_builder_requires_clean_published_h0_before_gate_or_rows(
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    monkeypatch.setattr(
        expert_adapter,
        "load_and_validate_development_runtime",
        lambda *args, **kwargs: (
            _runtime(),
            {"implementation_lock_present": False, "fit_authorized": False},
        ),
    )
    monkeypatch.setattr(
        expert_adapter,
        "require_published_h0",
        lambda runtime: (_ for _ in ()).throw(ClosureRuntimeContractError(reason)),
    )
    monkeypatch.setattr(
        expert_adapter,
        "load_development_gate",
        lambda: (_ for _ in ()).throw(AssertionError("development gate loaded")),
    )

    with pytest.raises(ClosureRuntimeContractError, match=reason):
        expert_adapter.materialize_expert_state()


def test_expert_builder_uses_schema_only_validation_before_h0_publication_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[bool, bool]] = []

    def load(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        del args
        calls.append(
            (
                bool(kwargs["cross_validate_locked"]),
                bool(kwargs["validate_repository"]),
            )
        )
        return _runtime(), {
            "implementation_lock_present": False,
            "fit_authorized": False,
        }

    monkeypatch.setattr(expert_adapter, "load_and_validate_development_runtime", load)
    monkeypatch.setattr(
        expert_adapter,
        "require_published_h0",
        lambda runtime: (_ for _ in ()).throw(ClosureRuntimeContractError("not published")),
    )
    monkeypatch.setattr(
        expert_adapter,
        "load_development_gate",
        lambda: (_ for _ in ()).throw(AssertionError("development gate loaded")),
    )

    with pytest.raises(ClosureRuntimeContractError, match="not published"):
        expert_adapter.materialize_expert_state()
    assert calls == [(False, False)]


def test_expert_bundle_is_one_shot_including_dvc_pointer_and_temporaries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = copy.deepcopy(_runtime())
    output = tmp_path / "expert.parquet"
    lineage = tmp_path / "lineage.json"
    manifest = tmp_path / "manifest.json"
    runtime["artifacts"]["expert_state_path"] = str(output)
    runtime["artifacts"]["expert_state_lineage_audit_path"] = str(lineage)
    runtime["artifacts"]["expert_state_manifest_path"] = str(manifest)
    monkeypatch.setattr(expert_adapter, "resolve_repo_path", lambda value: Path(value))

    for stale in (
        output,
        lineage,
        manifest,
        output.with_suffix(".parquet.dvc"),
        manifest.with_suffix(".json.tmp"),
    ):
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_bytes(b"stale")
        with pytest.raises(ClosureRuntimeContractError, match="one-shot"):
            expert_adapter.require_pristine_expert_bundle(runtime)
        stale.unlink()


def test_expert_semantic_audit_recomputes_roles_and_exact_month_deltas(
    tmp_path: Path,
) -> None:
    runtime = _runtime()
    gate = _gate()
    frame = expert_adapter.build_expert_no_current_state(
        _projected_rows(),
        runtime=runtime,
        gate=gate,
    )
    path = tmp_path / "expert.parquet"
    frame.to_parquet(path, index=False)

    audit = expert_adapter.audit_materialized_expert_state(
        path,
        runtime=runtime,
        gate=gate,
    )

    assert audit["schema_allowlist_verified"] is True
    assert audit["locations"] == 1
    assert audit["rows"] == 3
    assert audit["locked_time_roles_verified"] is True
    assert audit["exact_month_delta_recomputation_verified"] is True
    assert audit["future_outcomes_accessed"] is False


def test_expert_builder_dict_literals_have_no_duplicate_string_keys() -> None:
    source_path = Path(expert_adapter.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        seen: set[str] = set()
        for key_node in node.keys:
            if not (
                isinstance(key_node, ast.Constant)
                and isinstance(key_node.value, str)
            ):
                continue
            assert key_node.value not in seen, (
                f"duplicate dict literal key {key_node.value!r} at "
                f"{source_path}:{key_node.lineno}"
            )
            seen.add(key_node.value)


@pytest.mark.parametrize("mutation", ["extra_column", "holdout", "delta"])
def test_expert_semantic_audit_rejects_schema_assignment_or_delta_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    runtime = _runtime()
    gate = _gate()
    frame = expert_adapter.build_expert_no_current_state(
        _projected_rows(),
        runtime=runtime,
        gate=gate,
    )
    if mutation == "extra_column":
        frame["outcome"] = 1.0
    elif mutation == "holdout":
        frame["site_id"] = "H"
    else:
        frame.loc[1, "delta_yN"] = 0.123
    path = tmp_path / f"{mutation}.parquet"
    frame.to_parquet(path, index=False)

    with pytest.raises(Exception):
        expert_adapter.audit_materialized_expert_state(
            path,
            runtime=runtime,
            gate=gate,
        )


def test_expert_lineage_and_manifest_match_e0_dl_completion_dialect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frame = expert_adapter.build_expert_no_current_state(
        _projected_rows(),
        runtime=_runtime(),
        gate=_gate(),
    )
    scan = expert_adapter.DevelopmentScanAudit(
        materialized_rows=len(frame),
        returned_rows=len(frame),
        boundary_crossing_rows=0,
        _role_counts=(("model_selection", len(frame)),),
    )
    lineage = expert_adapter.expert_lineage_audit(
        frame,
        runtime=_runtime(),
        scan_audit=scan,
    )

    assert lineage["status"] == "passed"
    assert lineage["future_outcomes_accessed"] is False
    assert lineage["post_2021_outcomes_materialized"] is False
    assert lineage["checks"]
    assert all(value is True for value in lineage["checks"].values())

    monkeypatch.setattr(
        expert_adapter,
        "_write_parquet_atomic",
        lambda frame, path: path.write_bytes(b"parquet"),
    )
    output = tmp_path / "state.parquet"
    audit_path = tmp_path / "lineage.json"
    manifest_path = tmp_path / "manifest.json"
    manifest = expert_adapter.write_expert_bundle(
        frame,
        output_path=output,
        lineage_path=audit_path,
        manifest_path=manifest_path,
        lineage=lineage,
        manifest_base={
            "status": "completed",
            "future_outcomes_accessed": False,
            "post_2021_outcomes_materialized": False,
            "zero_holdout_overlap": True,
        },
    )
    state_records = [record for record in manifest["outputs"] if record["path"] == output.as_posix()]
    assert len(state_records) == 1
    assert manifest["post_2021_outcomes_materialized"] is False
    assert manifest["zero_holdout_overlap"] is True
