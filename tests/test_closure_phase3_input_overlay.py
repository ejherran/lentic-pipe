from __future__ import annotations

import hashlib
import io
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import torch

from src.experiments import build_closure_phase3_input_overlay as overlay
from src.fuzzy.adaptive_anfis import make_adaptive_anfis


def _write_torch(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)


def _seeded_anfis_payload(
    *, seed: int, module: str, production: bool = False
) -> dict[str, Any]:
    dimensions = (
        overlay.ANFIS_EXPECTED_INPUT_DIMENSION
        if production
        else {"N": 2, "F": 2, "T": 1}
    )
    membership_count = 3 if production else 2
    module_names = {"N": "ANFIS-N", "F": "ANFIS-F", "T": "ANFIS-T-no-current"}
    torch.manual_seed(seed + ord(module))
    model = make_adaptive_anfis(
        input_dim=dimensions[module],
        membership_count=membership_count,
        min_width=0.03,
        min_gap=0.0001,
        output_activation="sigmoid",
        center_constraint="unit",
    )
    with torch.no_grad():
        for index, parameter in enumerate(model.parameters()):
            values = torch.linspace(
                -0.2 + index * 0.01,
                0.25 + index * 0.01,
                parameter.numel(),
                dtype=parameter.dtype,
            ).reshape(parameter.shape)
            parameter.copy_(values)
    return {
        "checkpoint_version": "closure_anfis_module_v1",
        "experiment_id": "closure_v1",
        "module": module_names[module],
        "base_seed": seed,
        "module_seed": seed + ord(module),
        "feature_columns": (
            list(overlay.ANFIS_EXPECTED_FEATURE_COLUMNS[module])
            if production
            else [f"feature_{index}" for index in range(dimensions[module])]
        ),
        "target_column": (
            overlay.ANFIS_EXPECTED_TARGET_COLUMN[module]
            if production
            else f"synthetic_{module}"
        ),
        "configuration": {
            "memberships_per_input": membership_count,
            "center_constraint": "unit",
            "min_width": 0.03,
            "min_gap": 0.0001,
            "output_activation": "sigmoid",
        },
        "model_state_dict": model.state_dict(),
    }


class _TinyDirectPriorResidualGRU(torch.nn.Module):
    def __init__(self, input_dimension: int = 3, hidden_dimension: int = 4) -> None:
        super().__init__()
        self.gru = torch.nn.GRU(
            input_dimension, hidden_dimension, num_layers=1, batch_first=True
        )
        self.bloom_delta = torch.nn.Linear(hidden_dimension, 3)
        self.risk_delta = torch.nn.Linear(hidden_dimension, 3)
        self.risk_logvar = torch.nn.Linear(hidden_dimension, 3)
        self.register_buffer(
            "bloom_prior_logits", torch.tensor([-0.7, -0.4, -0.1])
        )
        self.register_buffer("risk_prior_logits", torch.tensor([0.2, 0.4, 0.6]))


def _seeded_gru_payload(
    *, seed: int, model_id: str, production: bool = False
) -> dict[str, Any]:
    torch.manual_seed(seed + (0 if model_id == "A0" else 1))
    input_dimension = (
        overlay.GRU_EXPECTED_INPUT_DIMENSION[model_id] if production else 3
    )
    hidden_dimension = overlay.GRU_EXPECTED_HIDDEN_DIMENSION if production else 4
    model = _TinyDirectPriorResidualGRU(input_dimension, hidden_dimension)
    return {
        "model_version": "closure_anfis_ablation_direct_multitask_v1",
        "experiment_id": "closure_v1",
        "surface_id": (
            "closure_v1_wqp_adaptive_no_current_chla"
            if production
            else "closure_v1_anfis_ablation"
        ),
        "gate": "E0-MT",
        "artifact_role": "raw_best_checkpoint",
        "model_id": model_id,
        "base_seed": seed,
        "upstream_state_seed": seed if model_id == "A1" else None,
        "device": "cpu",
        "config": {
            "family": "direct_multitask_probabilistic_gru",
            "model_id": model_id,
            "input_dimension": input_dimension,
            "hidden_dimension": hidden_dimension,
            "recurrent_layers": 1,
            "history_length_months": 12,
            "risk_logvar_clamp": [-10.0, 2.0],
        },
        "bloom_training_priors": [0.2, 0.3, 0.4],
        "risk_training_priors": [0.5, 0.6, 0.7],
        "model_state_dict": model.state_dict(),
    }


def _physical_values(index: int) -> dict[str, float | None]:
    return {
        column: (None if index % 7 == 0 and position == 0 else index + position / 100.0)
        for position, column in enumerate(overlay.PHYSICAL_FEATURE_COLUMNS)
    }


def _write_input_parquets(root: Path, *, site_count: int = 88) -> None:
    history_rows: list[dict[str, Any]] = []
    panel_rows: list[dict[str, Any]] = []
    panel_annual = 2.0 * math.pi * 336.0 / 365.25
    for index in range(site_count):
        site_id = f"site-{index:03d}"
        common = {
            "source_id": "wqp",
            "site_id": site_id,
            "holdout_group_id": f"group-{index:03d}",
            "assignment_role": "internal_holdout",
        }
        history_rows.extend(
            [
                {**common, "history_year_month": "2021-02"},
                {**common, "history_year_month": "2021-01"},
            ]
        )
        if index % 2 == 0:
            panel_rows.append(
                {
                    "source_id": "wqp",
                    "site_id": site_id,
                    "year_month": "2020-12",
                    **_physical_values(index),
                    "season_sin_1": math.sin(panel_annual),
                    "season_cos_1": math.cos(panel_annual),
                    "season_sin_2": math.sin(2.0 * panel_annual),
                    "season_cos_2": math.cos(2.0 * panel_annual),
                }
            )
    history_path = root / overlay.R10_INPUT_HISTORY_PATH
    panel_path = root / overlay.PANEL_PATH
    history_path.parent.mkdir(parents=True, exist_ok=True)
    panel_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(history_rows), history_path)
    pq.write_table(pa.Table.from_pylist(panel_rows), panel_path)


def _write_checkpoint_surface(root: Path, *, production: bool = False) -> None:
    for spec in overlay.CHECKPOINT_SPECS:
        payload = (
            _seeded_anfis_payload(
                seed=spec.seed, module=str(spec.module), production=production
            )
            if spec.family == "anfis"
            else _seeded_gru_payload(
                seed=spec.seed,
                model_id=str(spec.model_id),
                production=production,
            )
        )
        _write_torch(root / spec.path, payload)


def _synthetic_repository(root: Path, *, production: bool = False) -> None:
    (root / overlay.NPZ_OUTPUT_PATH.parent).mkdir(parents=True, exist_ok=True)
    (root / overlay.MANIFEST_OUTPUT_PATH.parent).mkdir(parents=True, exist_ok=True)
    (root / overlay.GUARD_PATH.parent).mkdir(parents=True, exist_ok=True)
    _write_input_parquets(root)
    _write_checkpoint_surface(root, production=production)


def _tree_digest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.mark.parametrize(
    ("center_constraint", "output_activation"),
    (("unit", "sigmoid"), ("ordered", "clip")),
)
def test_local_torch_anfis_forward_matches_reference_bytes(
    center_constraint: str,
    output_activation: str,
) -> None:
    torch.manual_seed(8675309)
    model = make_adaptive_anfis(
        input_dim=3,
        membership_count=3,
        min_width=0.03,
        min_gap=0.0001,
        output_activation=output_activation,
        center_constraint=center_constraint,
    )
    with torch.no_grad():
        for index, parameter in enumerate(model.parameters()):
            parameter.copy_(
                torch.linspace(
                    -0.31 + index * 0.02,
                    0.37 + index * 0.02,
                    parameter.numel(),
                    dtype=parameter.dtype,
                ).reshape(parameter.shape)
            )
    features = np.linspace(-0.2, 1.2, 33, dtype=np.float32).reshape(11, 3)
    configuration = {
        "min_width": 0.03,
        "min_gap": 0.0001,
        "output_activation": output_activation,
        "center_constraint": center_constraint,
    }
    with torch.no_grad():
        expected = (
            model(torch.as_tensor(features, dtype=torch.float32))
            .detach()
            .cpu()
            .numpy()
        )

    observed = overlay._anfis_torch_forward(
        model.state_dict(),
        features,
        configuration=configuration,
    )

    assert np.array_equal(observed, expected)
    assert observed.tobytes() == expected.tobytes()


def test_scientific_runtime_executes_local_anfis_under_isolated_python() -> None:
    probe = """
import runpy
import sys
from pathlib import Path

root = Path.cwd()
namespace = runpy.run_path(
    str(root / "src/experiments/build_closure_phase3_input_overlay.py"),
    run_name="isolated_closure_phase3_input_overlay",
)
activate = namespace["_activate_scientific_runtime"]
activate(root)
activate(root)
purelib = root / ".venv" / "lib" / (
    f"python{sys.version_info.major}.{sys.version_info.minor}"
) / "site-packages"
assert root.as_posix() not in sys.path
assert sys.path.count(purelib.as_posix()) == 1
assert "src" not in sys.modules
torch = __import__("torch")
numpy = __import__("numpy")
state = {
    "raw_center_gaps": torch.tensor(
        [[-0.4, -0.1, 0.2], [-0.3, 0.0, 0.3]], dtype=torch.float32
    ),
    "raw_widths": torch.tensor(
        [[-0.6, -0.2], [-0.5, -0.1]], dtype=torch.float32
    ),
    "consequent_weights": torch.linspace(-0.2, 0.3, 8).reshape(4, 2),
    "consequent_bias": torch.linspace(-0.1, 0.2, 4),
    "rule_indices": torch.tensor(
        [[0, 0], [0, 1], [1, 0], [1, 1]], dtype=torch.long
    ),
}
features = numpy.asarray([[0.2, 0.4], [0.7, 0.9]], dtype=numpy.float32)
result = namespace["_anfis_torch_forward"](
    state,
    features,
    configuration={
        "min_width": 0.03,
        "min_gap": 0.0001,
        "output_activation": "sigmoid",
        "center_constraint": "unit",
    },
)
assert result.shape == (2,)
assert numpy.isfinite(result).all()
assert "src" not in sys.modules
print("isolated-forward-ok")
"""
    result = subprocess.run(
        [
            "/usr/bin/env",
            "-i",
            "LANG=C",
            "LC_ALL=C",
            ".venv/bin/python",
            "-I",
            "-S",
            "-B",
            "-c",
            probe,
        ],
        cwd=overlay.PROJECT_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "isolated-forward-ok"


def test_check_only_is_zero_write_and_projection_is_outcome_free(tmp_path: Path) -> None:
    _synthetic_repository(tmp_path)
    before = _tree_digest(tmp_path)

    result = overlay.check_only(repo_root=tmp_path)

    assert result["status"] == "ready_to_generate"
    assert result["checkpoint_count"] == 25
    assert result["checkpoint_payloads_decoded"] is False
    assert result["scientific_rows_read"] is False
    assert result["writes_performed"] is False
    assert result["opened_outcome_path_count"] == 0
    assert result["opened_target_path_count"] == 0
    assert before == _tree_digest(tmp_path)
    assert not any(
        token in column.casefold()
        for column in overlay.PANEL_PROJECTION
        for token in ("chl", "chlorophyll", "target", "outcome")
    )


def test_synthetic_generate_exports_exact_dialect_warmup_and_parity(
    tmp_path: Path,
) -> None:
    _synthetic_repository(tmp_path)

    result = overlay.generate_phase3_input_overlay(
        repo_root=tmp_path,
        enforce_production_contract=False,
    )

    assert result["status"] == "materialized_unpublished"
    assert result["checkpoint_count"] == 25
    assert result["site_count"] == 88
    assert result["manifest_written_last"] is True
    assert not (tmp_path / overlay.GUARD_PATH).exists()

    manifest_path = tmp_path / overlay.MANIFEST_OUTPUT_PATH
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest_bytes == overlay._canonical_json_bytes(manifest)
    assert manifest["status"] == "completed"
    assert manifest["publication_status"] == "materialized_unpublished"
    assert manifest["script"] == manifest["source_inputs"][0]
    assert manifest["inputs"] == manifest["source_inputs"][1:]
    assert manifest["outputs"] == manifest["physical_outputs"]
    assert len(manifest["source_inputs"]) == 28
    assert [record["path"] for record in manifest["physical_outputs"]] == [
        overlay.NPZ_OUTPUT_PATH.as_posix(),
        overlay.WARMUP_OUTPUT_PATH.as_posix(),
    ]
    assert manifest["warmup"]["site_count"] == 88
    assert manifest["warmup"]["row_present_count"] == 44
    assert manifest["warmup"]["row_missing_count"] == 44
    assert manifest["warmup"]["panel_seasonal_values_used_for_runtime"] is False
    assert (
        manifest["warmup"][
            "panel_to_runtime_season_maximum_absolute_difference"
        ]
        > 0.0
    )
    assert manifest["numpy_export"]["anfis_checkpoint_count"] == 15
    assert manifest["numpy_export"]["anfis_f1_checkpoint_count"] == 15
    assert manifest["numpy_export"]["gru_checkpoint_count"] == 10
    assert manifest["numpy_export"]["parity"]["passed"] is True
    assert (
        manifest["numpy_export"]["parity"]["maximum_absolute_error"]
        <= overlay.PARITY_ATOL
        + overlay.PARITY_RTOL
        * manifest["numpy_export"]["parity"]["maximum_absolute_error"]
    )
    assert manifest["outcome_isolation"]["outcome_paths"] == []
    assert manifest["outcome_isolation"]["target_paths"] == []

    with np.load(tmp_path / overlay.NPZ_OUTPUT_PATH, allow_pickle=False) as archive:
        assert "__manifest_json__" in archive.files
        internal = json.loads(archive["__manifest_json__"].tobytes().decode("utf-8"))
        assert internal["checkpoint_count"] == 25
        assert internal["key_dialect"]["state_key_encoding"] == "literal_utf8_no_slash"
        state_keys = [key for key in archive.files if key != "__manifest_json__"]
        assert all(
            key.startswith("anfis/") or key.startswith("gru/") for key in state_keys
        )
        assert any(key.startswith("anfis/1729/N/") for key in state_keys)
        assert any(key.startswith("gru/A1/314159/") for key in state_keys)
        assert internal["array_keys"] == sorted(state_keys)

    warmup = pq.read_table(tmp_path / overlay.WARMUP_OUTPUT_PATH).to_pandas()
    assert list(warmup.columns) == list(overlay.WARMUP_COLUMNS)
    assert len(warmup) == 88
    assert warmup["row_present"].sum() == 44
    absent = warmup.loc[~warmup["row_present"]]
    assert absent[list(overlay.PHYSICAL_FEATURE_COLUMNS)].isna().all().all()
    assert absent[list(overlay.DERIVED_CALENDAR_COLUMNS)].notna().all().all()
    assert set(warmup["year_month"]) == {"2020-12"}
    expected_calendar = overlay._calendar_features(overlay._month_index("2020-12"))
    for column, value in expected_calendar.items():
        assert np.allclose(warmup[column], value, rtol=0.0, atol=1.0e-15)

    before_second_attempt = _tree_digest(tmp_path)
    with pytest.raises(overlay.Phase3InputOverlayError, match="not empty"):
        overlay.generate_phase3_input_overlay(
            repo_root=tmp_path,
            enforce_production_contract=False,
        )
    assert before_second_attempt == _tree_digest(tmp_path)


def test_deep_validator_regenerates_production_npz_warmup_and_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h_commit = "1" * 40
    _synthetic_repository(tmp_path, production=True)
    builder_path = tmp_path / "src/experiments/build_closure_phase3_input_overlay.py"
    builder_path.parent.mkdir(parents=True)
    builder_payload = Path(overlay.__file__).read_bytes()
    builder_path.write_bytes(builder_payload)
    monkeypatch.setattr(overlay, "_git_head", lambda _root: h_commit)

    overlay.generate_phase3_input_overlay(
        repo_root=tmp_path,
        enforce_production_contract=True,
    )
    monkeypatch.setattr(
        overlay,
        "_git_blob_bytes",
        lambda _root, commit, path: (
            builder_payload
            if commit == h_commit
            and path.as_posix()
            == "src/experiments/build_closure_phase3_input_overlay.py"
            else b""
        ),
    )
    before = _tree_digest(tmp_path)

    receipt = overlay.validate_materialized_phase3_input_overlay(
        repo_root=tmp_path,
        expected_h_commit=h_commit,
    )

    assert receipt["schema_version"] == overlay.DEEP_VALIDATION_VERSION
    assert receipt["status"] == "passed"
    assert receipt["source_input_count"] == 27
    assert receipt["checkpoint_count"] == 25
    assert receipt["state_dict_array_count"] == 195
    assert receipt["warmup_row_count"] == 88
    assert receipt["warmup_site_count"] == 88
    assert receipt["npz_regenerated_byte_equality"] is True
    assert receipt["warmup_regenerated_byte_equality"] is True
    assert receipt["manifest_regenerated_byte_equality"] is True
    assert receipt["opened_outcome_path_count"] == 0
    assert receipt["opened_target_path_count"] == 0
    assert receipt["writes_performed"] is False
    assert before == _tree_digest(tmp_path)

    npz_path = tmp_path / overlay.NPZ_OUTPUT_PATH
    original_npz = npz_path.read_bytes()
    npz_path.write_bytes(original_npz[:-1] + bytes([original_npz[-1] ^ 1]))
    with pytest.raises(
        overlay.Phase3InputOverlayError,
        match="differs from regenerated checkpoint state",
    ):
        overlay.validate_materialized_phase3_input_overlay(
            repo_root=tmp_path,
            expected_h_commit=h_commit,
        )


def test_manifest_failure_rolls_back_only_owned_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _synthetic_repository(tmp_path)
    original_publish = overlay.OutputTransaction.publish

    def fail_before_manifest(
        self: overlay.OutputTransaction, relative: Path, payload: bytes
    ) -> overlay.OwnedPath:
        if relative == overlay.MANIFEST_OUTPUT_PATH:
            raise RuntimeError("synthetic manifest publication failure")
        return original_publish(self, relative, payload)

    monkeypatch.setattr(overlay.OutputTransaction, "publish", fail_before_manifest)

    with pytest.raises(RuntimeError, match="synthetic manifest"):
        overlay.generate_phase3_input_overlay(
            repo_root=tmp_path,
            enforce_production_contract=False,
        )

    assert not (tmp_path / overlay.NPZ_OUTPUT_PATH).exists()
    assert not (tmp_path / overlay.WARMUP_OUTPUT_PATH).exists()
    assert not (tmp_path / overlay.MANIFEST_OUTPUT_PATH).exists()
    assert not (tmp_path / overlay.GUARD_PATH).exists()
    assert not list(tmp_path.rglob("*.tmp"))


def test_npz_bytes_are_deterministic_and_state_key_mapping_is_literal(
    tmp_path: Path,
) -> None:
    _synthetic_repository(tmp_path)

    first, first_index, _ = overlay._build_npz(
        overlay.CHECKPOINT_SPECS,
        repo_root=tmp_path,
        enforce_production_contract=False,
    )
    second, second_index, _ = overlay._build_npz(
        overlay.CHECKPOINT_SPECS,
        repo_root=tmp_path,
        enforce_production_contract=False,
    )

    assert first == second
    assert first_index == second_index
    recurrent = next(
        record
        for record in first_index["arrays"]
        if record["npz_key"] == "gru/A0/1729/gru.weight_ih_l0"
    )
    assert recurrent["state_key"] == "gru.weight_ih_l0"
    assert recurrent["dtype"] == "<f4"
    assert recurrent["shape"] == [12, 3]
    assert math.isfinite(first_index["parity"]["maximum_absolute_error"])


def test_rollback_refuses_to_remove_a_replaced_inode(tmp_path: Path) -> None:
    path = tmp_path / "owned.bin"
    path.write_bytes(b"owned")
    owned = overlay._owned_path(path)
    path.unlink()
    path.write_bytes(b"replacement")

    with pytest.raises(overlay.Phase3InputOverlayError, match="replaced path"):
        overlay._unlink_if_owned(owned)

    assert path.read_bytes() == b"replacement"


def test_owned_cleanup_restores_replacement_captured_at_rename_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "owned.bin"
    path.write_bytes(b"owned")
    owned = overlay._owned_path(path)
    real_rename = os.rename
    raced = False

    def replace_then_rename(
        source: str,
        target: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal raced
        if not raced and source == path.name:
            raced = True
            os.unlink(source, dir_fd=src_dir_fd)
            descriptor = os.open(
                source,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
                dir_fd=src_dir_fd,
            )
            try:
                os.write(descriptor, b"foreign")
            finally:
                os.close(descriptor)
        real_rename(
            source,
            target,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(os, "rename", replace_then_rename)
    with pytest.raises(overlay.Phase3InputOverlayError, match="replaced path"):
        overlay._unlink_if_owned(owned)

    assert raced is True
    assert path.read_bytes() == b"foreign"
    assert not list(tmp_path.glob(".closure-owned-capture-*"))


def test_owned_cleanup_restores_directory_captured_at_rename_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "owned.bin"
    path.write_bytes(b"owned")
    owned = overlay._owned_path(path)
    real_rename = os.rename
    raced = False

    def replace_then_rename(
        source: str,
        target: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal raced
        if not raced and source == path.name:
            raced = True
            os.unlink(source, dir_fd=src_dir_fd)
            os.mkdir(source, 0o700, dir_fd=src_dir_fd)
        real_rename(
            source,
            target,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(os, "rename", replace_then_rename)
    with pytest.raises(overlay.Phase3InputOverlayError, match="replaced path"):
        overlay._unlink_if_owned(owned)

    assert raced is True
    assert path.is_dir()
    assert not list(tmp_path.glob(".closure-owned-capture-*"))


def test_transaction_rollback_uses_original_parent_after_ancestor_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    sealed = repo / "sealed"
    sealed.mkdir(parents=True)
    real_write = os.write
    write_calls = 0

    def replacing_write(descriptor: int, payload: bytes | memoryview) -> int:
        nonlocal write_calls
        write_calls += 1
        if write_calls == 2:
            sealed.rename(repo / "sealed-old")
            sealed.mkdir()
        return real_write(descriptor, payload)

    monkeypatch.setattr(os, "write", replacing_write)
    with pytest.raises(
        overlay.Phase3InputOverlayError,
        match="cleanup was incomplete",
    ):
        with overlay.OutputTransaction(repo_root=repo) as transaction:
            transaction.publish(Path("sealed/first.bin"), b"first")
            transaction.publish(Path("sealed/second.bin"), b"second")
            transaction.commit()

    assert not (repo / "sealed-old" / "first.bin").exists()
    assert not (repo / "sealed-old" / "second.bin").exists()
    assert not (repo / "sealed" / "first.bin").exists()
    assert not (repo / "sealed" / "second.bin").exists()
    assert not list(repo.rglob("*.tmp"))


def test_guard_cleanup_uses_original_parent_after_repository_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    (repo / "tmp").mkdir(parents=True)
    real_write = os.write
    replaced = False

    def replacing_write(descriptor: int, payload: bytes | memoryview) -> int:
        nonlocal replaced
        if not replaced:
            replaced = True
            repo.rename(tmp_path / "repo-old")
            (repo / "tmp").mkdir(parents=True)
        return real_write(descriptor, payload)

    monkeypatch.setattr(os, "write", replacing_write)
    with pytest.raises(
        overlay.Phase3InputOverlayError,
        match="guard cleanup was incomplete",
    ):
        overlay._acquire_guard(overlay.GUARD_PATH, repo_root=repo)

    assert not (tmp_path / "repo-old" / overlay.GUARD_PATH).exists()
    assert not (repo / overlay.GUARD_PATH).exists()


def test_guard_and_transaction_reject_distinct_repository_roots(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "tmp").mkdir(parents=True)
    (repo / "sealed").mkdir()
    guard = overlay._acquire_guard(overlay.GUARD_PATH, repo_root=repo)
    repo.rename(tmp_path / "repo-before-publication")
    (repo / "tmp").mkdir(parents=True)
    (repo / "sealed").mkdir()

    with pytest.raises(
        overlay.Phase3InputOverlayError,
        match="generation guard repository root was replaced",
    ):
        with overlay.OutputTransaction(
            repo_root=repo,
            namespace_guard=guard,
        ) as transaction:
            transaction.publish(Path("sealed/output.bin"), b"payload")
            transaction.commit()

    assert not (
        tmp_path / "repo-before-publication" / overlay.GUARD_PATH
    ).exists()
    assert not (tmp_path / "repo-before-publication" / "sealed/output.bin").exists()
    assert not (repo / overlay.GUARD_PATH).exists()
    assert not (repo / "sealed/output.bin").exists()
    assert not list(tmp_path.rglob("*.tmp"))


def test_transaction_rejects_disappeared_guard_and_rolls_back_outputs(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "tmp").mkdir(parents=True)
    (repo / "sealed").mkdir()
    guard = overlay._acquire_guard(overlay.GUARD_PATH, repo_root=repo)

    with pytest.raises(
        overlay.Phase3InputOverlayError,
        match="output namespace changed before transaction close",
    ):
        with overlay.OutputTransaction(
            repo_root=repo,
            namespace_guard=guard,
        ) as transaction:
            transaction.publish(Path("sealed/output.bin"), b"payload")
            transaction.commit()
            os.unlink(
                guard.path.name,
                dir_fd=guard.anchor.parent_fd,
            )

    assert not (repo / "sealed/output.bin").exists()
    assert not (repo / overlay.GUARD_PATH).exists()
    assert not list(repo.rglob("*.tmp"))


def test_transaction_rejects_replaced_guard_and_preserves_foreign_leaf(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "tmp").mkdir(parents=True)
    (repo / "sealed").mkdir()
    guard = overlay._acquire_guard(overlay.GUARD_PATH, repo_root=repo)

    with pytest.raises(
        overlay.Phase3InputOverlayError,
        match="output namespace changed before transaction close",
    ):
        with overlay.OutputTransaction(
            repo_root=repo,
            namespace_guard=guard,
        ) as transaction:
            transaction.publish(Path("sealed/output.bin"), b"payload")
            transaction.commit()
            os.unlink(
                guard.path.name,
                dir_fd=guard.anchor.parent_fd,
            )
            (repo / overlay.GUARD_PATH).write_bytes(b"foreign")

    assert not (repo / "sealed/output.bin").exists()
    assert (repo / overlay.GUARD_PATH).read_bytes() == b"foreign"
    assert not list(repo.rglob("*.tmp"))


def test_post_commit_descriptor_close_error_does_not_report_false_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    (repo / "tmp").mkdir(parents=True)
    (repo / "sealed").mkdir()
    guard = overlay._acquire_guard(overlay.GUARD_PATH, repo_root=repo)
    real_close = os.close
    injected = False

    with overlay.OutputTransaction(
        repo_root=repo,
        namespace_guard=guard,
    ) as transaction:
        owned = transaction.publish(Path("sealed/output.bin"), b"payload")
        target_descriptor = owned.anchor.parent_fd
        transaction.commit()

        def close_then_report(descriptor: int) -> None:
            nonlocal injected
            real_close(descriptor)
            if descriptor == target_descriptor and not injected:
                injected = True
                raise OSError("synthetic post-commit close report")

        monkeypatch.setattr(os, "close", close_then_report)

    assert injected is True
    assert (repo / "sealed/output.bin").read_bytes() == b"payload"
    assert not (repo / overlay.GUARD_PATH).exists()


def test_output_publication_rejects_symlinked_ancestor(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    (repo / "sealed").symlink_to(outside, target_is_directory=True)

    with pytest.raises(overlay.Phase3InputOverlayError, match="without following"):
        with overlay.OutputTransaction(repo_root=repo) as transaction:
            transaction.publish(Path("sealed/output.bin"), b"payload")
            transaction.commit()

    assert not (outside / "output.bin").exists()


def test_anchored_overlay_reader_rejects_replaced_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "sealed"
    parent.mkdir()
    (parent / "payload.bin").write_bytes(b"sealed")
    real_read = os.read
    replaced = False

    def replacing_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        if not replaced:
            replaced = True
            parent.rename(tmp_path / "sealed-old")
            parent.mkdir()
            (parent / "payload.bin").write_bytes(b"replacement")
        return real_read(descriptor, size)

    monkeypatch.setattr(os, "read", replacing_read)
    with pytest.raises(
        overlay.Phase3InputOverlayError,
        match="ancestor changed during read",
    ):
        overlay._read_anchored_bytes(Path("sealed/payload.bin"), repo_root=tmp_path)


def test_anchored_overlay_reader_rejects_replaced_repository_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    payload = repo / "sealed" / "payload.bin"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"sealed")
    real_read = os.read
    replaced = False

    def replacing_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        if not replaced:
            replaced = True
            repo.rename(tmp_path / "repo-old")
            replacement = repo / "sealed"
            replacement.mkdir(parents=True)
            (replacement / "payload.bin").write_bytes(b"replacement")
        return real_read(descriptor, size)

    monkeypatch.setattr(os, "read", replacing_read)
    with pytest.raises(
        overlay.Phase3InputOverlayError,
        match="repository root changed during input read",
    ):
        overlay._read_anchored_bytes(Path("sealed/payload.bin"), repo_root=repo)


def test_anchored_overlay_reader_accepts_hash_bound_dvc_hardlink(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "payload.parquet"
    cache = tmp_path / "cache-object"
    payload.write_bytes(b"dvc-payload")
    os.link(payload, cache)
    payload.chmod(0o444)

    assert payload.stat().st_nlink == 2
    assert overlay._read_anchored_bytes(
        Path("payload.parquet"), repo_root=tmp_path
    ) == b"dvc-payload"
    payload.chmod(0o600)
    with pytest.raises(
        overlay.Phase3InputOverlayError,
        match="anchored regular file",
    ):
        overlay._read_anchored_bytes(
            Path("payload.parquet"), repo_root=tmp_path
        )


def test_production_checkpoint_shape_contracts_are_enforced() -> None:
    anfis = make_adaptive_anfis(
        input_dim=3,
        membership_count=3,
        min_width=0.03,
        min_gap=0.0001,
        output_activation="sigmoid",
        center_constraint="unit",
    )
    anfis_payload = {
        "checkpoint_version": "closure_anfis_module_v1",
        "experiment_id": "closure_v1",
        "module": "ANFIS-N",
        "base_seed": 1729,
        "module_seed": 1830,
        "feature_columns": list(overlay.ANFIS_EXPECTED_FEATURE_COLUMNS["N"]),
        "target_column": "yN",
        "configuration": {
            "memberships_per_input": 3,
            "center_constraint": "unit",
            "min_width": 0.03,
            "min_gap": 0.0001,
            "output_activation": "sigmoid",
        },
        "model_state_dict": anfis.state_dict(),
    }
    anfis_spec = next(
        spec
        for spec in overlay.CHECKPOINT_SPECS
        if spec.family == "anfis" and spec.seed == 1729 and spec.module == "N"
    )
    overlay._validate_checkpoint_identity(
        anfis_payload,
        anfis_payload["model_state_dict"],
        spec=anfis_spec,
        enforce_production_contract=True,
    )

    gru = _TinyDirectPriorResidualGRU(input_dimension=18, hidden_dimension=96)
    gru_payload = {
        "model_version": "closure_anfis_ablation_direct_multitask_v1",
        "experiment_id": "closure_v1",
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "gate": "E0-MT",
        "artifact_role": "raw_best_checkpoint",
        "model_id": "A0",
        "base_seed": 1729,
        "upstream_state_seed": None,
        "device": "cpu",
        "config": {
            "family": "direct_multitask_probabilistic_gru",
            "model_id": "A0",
            "input_dimension": 18,
            "hidden_dimension": 96,
            "recurrent_layers": 1,
            "history_length_months": 12,
            "risk_logvar_clamp": [-10.0, 2.0],
        },
        "model_state_dict": gru.state_dict(),
    }
    gru_spec = next(
        spec
        for spec in overlay.CHECKPOINT_SPECS
        if spec.family == "gru" and spec.seed == 1729 and spec.model_id == "A0"
    )
    overlay._validate_checkpoint_identity(
        gru_payload,
        gru_payload["model_state_dict"],
        spec=gru_spec,
        enforce_production_contract=True,
    )
    gru_payload["config"]["hidden_dimension"] = 95
    with pytest.raises(overlay.Phase3InputOverlayError, match="architecture drifted"):
        overlay._validate_checkpoint_identity(
            gru_payload,
            gru_payload["model_state_dict"],
            spec=gru_spec,
            enforce_production_contract=True,
        )
