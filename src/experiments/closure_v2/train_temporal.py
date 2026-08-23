#!/usr/bin/env python
"""Train Closure V2 P0/P1 residual probabilistic GRUs on exact shared-fit keys."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import platform
import random
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.experiments.closure_contract import (
    ClosureContractError,
    load_json_mapping,
    load_yaml_mapping,
    validate_json_schema,
)
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT, audit_repository
from src.experiments.closure_v2.build_eligibility import (
    EXPECTED_SEEDS,
    IDENTITY_COLUMNS,
    INPUT_COLUMNS,
    LEDGER_OUTPUT,
    TARGET_COLUMNS,
)
from src.experiments.closure_v2.build_shared_fit_keys import SHARED_OUTPUT
from src.experiments.closure_v2.hashing import canonical_json_bytes, file_record, md5_file, sha256_file
from src.experiments.train_pipe_grud import (
    STATE_TARGET_NAMES,
    TARGET_WEIGHTS,
    _blend_weight_tensor,
    _require_torch,
    evaluate_model,
    make_model,
    select_output_blend_weights,
    training_loss,
)


RUNTIME_CONFIG = Path("configs/closure_v2/development_runtime.yaml")
RUNTIME_SCHEMA = Path("configs/closure_v2/development_runtime.schema.json")
DEVELOPMENT_LOCK = Path("reports/closure_v2/00_protocol/development_lock.json")
ELIGIBILITY_MANIFEST = Path("reports/closure_v2/01_surface/eligibility_manifest.json")
PROTOCOL_LOCK = Path("reports/closure_v2/00_protocol/protocol_lock.json")
PROTOCOL_TAG = "closure-v2-protocol"
DEVELOPMENT_TAG = "closure-v2-development"
MODEL_IDS = ("P0", "P1")
BLEND_GRID = (0.0, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 1.0)
FAMILY_ROOT = Path("reports/closure_v2/02_models")
FAMILY_SUMMARY = FAMILY_ROOT / "family_summary.csv"
FAMILY_REPORT = FAMILY_ROOT / "FAMILY_REPORT.md"
FAMILY_MANIFEST = FAMILY_ROOT / "family_manifest.json"


class TemporalTrainingError(ClosureContractError):
    """Raised when a V2 temporal fit violates a sealed development decision."""


@dataclass(frozen=True)
class TrainingProfile:
    name: str
    batch_size: int
    maximum_epochs: int
    patience: int
    minimum_delta: float


@dataclass(frozen=True)
class WindowBundle:
    metadata: pd.DataFrame
    x: np.ndarray
    y: np.ndarray

    def subset(self, role: str) -> WindowBundle:
        mask = self.metadata["time_role"].eq(role).to_numpy(dtype=bool)
        return WindowBundle(
            metadata=self.metadata.loc[mask].reset_index(drop=True),
            x=self.x[mask],
            y=self.y[mask],
        )


@dataclass(frozen=True)
class ProfileFit:
    profile: TrainingProfile
    best_epoch: int
    best_objective: float
    epochs_ran: int
    history: pd.DataFrame
    best_state_dict: dict[str, Any]


@dataclass(frozen=True)
class SlotFit:
    model_id: str
    base_seed: int
    selected_profile: str
    profile_fits: tuple[ProfileFit, ...]
    model: Any
    blend_weights: pd.DataFrame
    blend_search: pd.DataFrame
    metrics: pd.DataFrame


class TensorWindowDataset:
    def __init__(self, x: np.ndarray, y: np.ndarray) -> None:
        self.x = np.asarray(x, dtype=np.float32)
        self.y = np.asarray(y, dtype=np.float32)

    def __len__(self) -> int:
        return len(self.x)

    def __getitem__(self, index: int) -> tuple[Any, Any]:
        torch = _require_torch()
        return torch.from_numpy(self.x[index]), torch.from_numpy(self.y[index])


def _git(*args: str, root: Path = PROJECT_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _require_regular(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise TemporalTrainingError(f"Required regular file is absent: {relative}")
    return path


def _verify_tagged_file(relative: Path, *, tag: str, root: Path) -> None:
    live = _require_regular(root, relative).read_bytes()
    tagged = subprocess.run(
        ["git", "show", f"{tag}:{relative.as_posix()}"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    if live != tagged:
        raise TemporalTrainingError(f"Live authority differs from {tag}: {relative}")


def validate_runtime(path: Path = RUNTIME_CONFIG) -> dict[str, Any]:
    runtime = dict(load_yaml_mapping(path))
    validate_json_schema(
        runtime,
        load_json_mapping(RUNTIME_SCHEMA),
        instance_path="$.development_runtime",
    )
    expected = {
        "models": ["P0", "P1"],
        "seeds": EXPECTED_SEEDS,
    }
    for key, value in expected.items():
        if runtime.get(key) != value:
            raise TemporalTrainingError(f"Runtime {key} drifted")
    architecture = cast(Mapping[str, Any], runtime["architecture"])
    if dict(architecture) != {
        "history_length_months": 12,
        "input_dimension": 13,
        "target_dimension": 9,
        "hidden_dimension": 96,
        "recurrent_layers": 1,
        "dropout": 0.0,
        "residual_mode": "add_last",
    }:
        raise TemporalTrainingError("Runtime architecture drifted")
    optimization = cast(Mapping[str, Any], runtime["optimization"])
    if dict(optimization) != {
        "optimizer": "AdamW",
        "learning_rate": 0.001,
        "weight_decay": 0.00001,
        "gradient_clip_norm": 1.0,
        "mse_weight": 1.0,
        "device": "cpu",
        "torch_num_threads": 1,
        "torch_num_interop_threads": 1,
    }:
        raise TemporalTrainingError("Runtime optimization drifted")
    profiles = cast(Mapping[str, Any], runtime["profiles"])
    expected_profiles = {
        "v2_primary": {
            "batch_size": 512,
            "maximum_epochs": 60,
            "early_stopping_patience": 10,
            "early_stopping_minimum_delta": 0.0,
        },
        "legacy_diagnostic": {
            "batch_size": 2048,
            "maximum_epochs": 20,
            "early_stopping_patience": 5,
            "early_stopping_minimum_delta": 0.0,
        },
    }
    if dict(profiles) != expected_profiles:
        raise TemporalTrainingError("Runtime training profiles drifted")
    selection = cast(Mapping[str, Any], runtime["profile_selection"])
    if dict(selection) != {
        "data_role": "model_selection",
        "metric": "probabilistic_validation_loss",
        "direction": "lower_is_better",
        "exact_tie_break": "v2_primary",
    }:
        raise TemporalTrainingError("Runtime profile-selection rule drifted")
    blend = cast(Mapping[str, Any], runtime["output_blend"])
    if tuple(blend.get("grid", ())) != BLEND_GRID or blend.get("stage") != "once_after_selected_raw_best_restore":
        raise TemporalTrainingError("Runtime output-blend rule drifted")
    return runtime


def _verify_record(record: Mapping[str, Any], *, root: Path) -> None:
    relative = Path(str(record["path"]))
    path = _require_regular(root, relative)
    if path.stat().st_size != record.get("bytes") or sha256_file(path) != record.get("sha256"):
        raise TemporalTrainingError(f"Authority record hash/size mismatch: {relative}")


def validate_development_authority(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Make development fit authorization effective only after its annotated tag."""
    validate_runtime(root / RUNTIME_CONFIG)
    if _git("cat-file", "-t", f"refs/tags/{DEVELOPMENT_TAG}", root=root) != "tag":
        raise TemporalTrainingError(f"{DEVELOPMENT_TAG} must be an annotated tag")
    development_commit = _git("rev-parse", f"{DEVELOPMENT_TAG}^{{}}", root=root)
    protocol_commit = _git("rev-parse", f"{PROTOCOL_TAG}^{{}}", root=root)
    head = _git("rev-parse", "HEAD", root=root)
    subprocess.run(["git", "merge-base", "--is-ancestor", development_commit, head], cwd=root, check=True)
    if _git("rev-parse", f"{development_commit}^", root=root) != protocol_commit:
        raise TemporalTrainingError("Development commit must be the direct child of the protocol commit")
    remote = _git("rev-parse", "refs/remotes/origin/closure-v2", root=root)
    if remote != head:
        raise TemporalTrainingError("origin/closure-v2 must equal HEAD before fitting")
    for relative in (DEVELOPMENT_LOCK, ELIGIBILITY_MANIFEST):
        _verify_tagged_file(relative, tag=DEVELOPMENT_TAG, root=root)
    lock = load_json_mapping(root / DEVELOPMENT_LOCK)
    manifest = load_json_mapping(root / ELIGIBILITY_MANIFEST)
    if lock.get("status") != "locked_unpublished" or lock.get("fit_authorized") is not False:
        raise TemporalTrainingError("Development lock pre-publication state drifted")
    if lock.get("fit_authorization_effective_after_annotated_tag") != DEVELOPMENT_TAG:
        raise TemporalTrainingError("Development lock tag gate drifted")
    if lock.get("protocol_commit") != protocol_commit or lock.get("authority_head") != protocol_commit:
        raise TemporalTrainingError("Development lock ancestry drifted")
    if not cast(Mapping[str, Any], lock.get("authorization", {})).get("authorized"):
        raise TemporalTrainingError("Development eligibility thresholds did not authorize fit")
    for record in cast(Sequence[Mapping[str, Any]], manifest["inputs"]):
        _verify_record(record, root=root)
    for record in cast(Sequence[Mapping[str, Any]], manifest["outputs"]):
        _verify_record(record, root=root)
    for record in cast(Sequence[Mapping[str, Any]], manifest["source_inputs"]):
        _verify_record(record, root=root)
    for record in cast(Sequence[Mapping[str, Any]], manifest["data_artifacts"]):
        _verify_record(record, root=root)
        pointer = _require_regular(root, Path(str(record["dvc_pointer"])))
        if pointer.stat().st_size != record.get("dvc_pointer_bytes") or sha256_file(pointer) != record.get("dvc_pointer_sha256"):
            raise TemporalTrainingError(f"Development DVC pointer drifted: {pointer}")
        if md5_file(root / str(record["path"])) != record.get("dvc_md5"):
            raise TemporalTrainingError(f"Development DVC object drifted: {record['path']}")
    v1 = audit_repository(root)
    if v1["protected_v1_changes"]:
        raise TemporalTrainingError(f"Closure V1 drift detected: {v1['protected_v1_changes']}")
    return {
        "status": "fit_authorized",
        "protocol_commit": protocol_commit,
        "development_commit": development_commit,
        "head": head,
        "fit_authorized": True,
        "evaluation_authorized": False,
        "post_2021_outcomes_authorized": False,
    }


def _profiles(runtime: Mapping[str, Any]) -> tuple[TrainingProfile, ...]:
    profiles = cast(Mapping[str, Mapping[str, Any]], runtime["profiles"])
    return tuple(
        TrainingProfile(
            name=name,
            batch_size=int(profiles[name]["batch_size"]),
            maximum_epochs=int(profiles[name]["maximum_epochs"]),
            patience=int(profiles[name]["early_stopping_patience"]),
            minimum_delta=float(profiles[name]["early_stopping_minimum_delta"]),
        )
        for name in ("v2_primary", "legacy_diagnostic")
    )


def _sequence_path(model_id: str, base_seed: int) -> Path:
    if model_id == "P0":
        return Path("data/closure_v1/development/sequences/P0/expert_no_current.parquet")
    if model_id == "P1" and base_seed in EXPECTED_SEEDS:
        return Path(f"data/closure_v1/development/sequences/P1/seed_{base_seed}.parquet")
    raise TemporalTrainingError(f"Unknown temporal slot: {model_id}/{base_seed}")


def _key_tuples(frame: pd.DataFrame) -> set[tuple[Any, ...]]:
    return set(frame[IDENTITY_COLUMNS].itertuples(index=False, name=None))


def load_slot_bundle(model_id: str, base_seed: int, *, root: Path = PROJECT_ROOT) -> WindowBundle:
    if model_id not in MODEL_IDS or base_seed not in EXPECTED_SEEDS:
        raise TemporalTrainingError(f"Unregistered temporal slot: {model_id}/{base_seed}")
    ledger = pq.read_table(_require_regular(root, LEDGER_OUTPUT)).to_pandas()
    shared = pq.read_table(_require_regular(root, SHARED_OUTPUT)).to_pandas()
    slot_ledger = ledger.loc[ledger["model_id"].eq(model_id) & ledger["base_seed"].eq(base_seed)]
    shared_fit_ledger = slot_ledger.loc[slot_ledger["shared_fit_eligible"]]
    shared_slot = shared.loc[shared["base_seed"].eq(base_seed) & shared["usage_role"].eq("fit")]
    if len(slot_ledger) != 9732 or len(shared_fit_ledger) != 8925 or len(shared_slot) != 8925:
        raise TemporalTrainingError(f"Locked slot denominators drifted: {model_id}/{base_seed}")
    if _key_tuples(shared_fit_ledger) != _key_tuples(shared_slot):
        raise TemporalTrainingError(f"Ledger/shared-fit identities drifted: {model_id}/{base_seed}")
    source = pq.read_table(_require_regular(root, _sequence_path(model_id, base_seed))).to_pandas()
    if len(source) != 9732 or source.duplicated(IDENTITY_COLUMNS).any():
        raise TemporalTrainingError(f"Source sequence denominator/identity drifted: {model_id}/{base_seed}")
    if set(source["model_id"].astype(str)) != {model_id}:
        raise TemporalTrainingError(f"Source model identity drifted: {model_id}/{base_seed}")
    if model_id == "P0" and not source["base_seed"].isna().all():
        raise TemporalTrainingError("P0 source sequences must remain seed-independent")
    if model_id == "P1" and set(pd.to_numeric(source["base_seed"]).astype(int)) != {base_seed}:
        raise TemporalTrainingError("P1 source sequence seed drifted")
    shared_keys = _key_tuples(shared_slot)
    selected = source.loc[
        source[IDENTITY_COLUMNS].apply(tuple, axis=1).isin(shared_keys)
    ].copy()
    if len(selected) != 8925 or set(selected["sequence_status"].astype(str)) != {"success"}:
        raise TemporalTrainingError(f"Shared source filtering did not produce 8,925 successful rows: {model_id}/{base_seed}")
    if set(selected["time_role"].astype(str)) != {"training", "model_selection"}:
        raise TemporalTrainingError("Shared fit contains a forbidden temporal role")
    if selected["target_year_month"].astype(str).max() > "2020-12":
        raise TemporalTrainingError("Fit bundle contains calibration/evaluation time")
    selected = selected.sort_values(IDENTITY_COLUMNS, kind="stable").reset_index(drop=True)
    matrices: list[np.ndarray] = []
    for row in selected.to_dict(orient="records"):
        columns: list[np.ndarray] = []
        for column in INPUT_COLUMNS:
            value = np.asarray(row[column], dtype=np.float32)
            if value.shape != (12,) or not np.isfinite(value).all():
                raise TemporalTrainingError(f"Nonfinite shared input: {model_id}/{base_seed}/{column}")
            columns.append(value)
        matrices.append(np.column_stack(columns))
    x = np.stack(matrices).astype(np.float32, copy=False)
    y = selected[TARGET_COLUMNS].to_numpy(dtype=np.float32)
    if not np.isfinite(y).all():
        raise TemporalTrainingError(f"Nonfinite shared target: {model_id}/{base_seed}")
    role_counts = selected["time_role"].value_counts().to_dict()
    if role_counts != {"training": 7909, "model_selection": 1016}:
        raise TemporalTrainingError(f"Shared role denominators drifted: {role_counts}")
    return WindowBundle(metadata=selected, x=x, y=y)


def _configure_seed(base_seed: int) -> Any:
    random.seed(base_seed)
    np.random.seed(base_seed)
    torch = _require_torch()
    torch.manual_seed(base_seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(base_seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        if torch.get_num_interop_threads() != 1:
            raise
    return torch.device("cpu")


def _loss_weights(device: Any) -> Any:
    torch = _require_torch()
    values = np.asarray([TARGET_WEIGHTS[name] for name in STATE_TARGET_NAMES], dtype=np.float32)
    return torch.from_numpy(values).to(device=device, dtype=torch.float32)


def canonical_epoch_batches(
    keys: Sequence[Sequence[str]], *, base_seed: int, epoch: int, batch_size: int
) -> tuple[list[np.ndarray], str]:
    if epoch < 1 or batch_size < 1:
        raise TemporalTrainingError("Epoch and batch size must be positive")
    torch = _require_torch()
    generator = torch.Generator(device="cpu")
    generator.manual_seed(base_seed + epoch)
    permutation = torch.randperm(len(keys), generator=generator).numpy().astype(np.int64)
    batches = [permutation[start : start + batch_size] for start in range(0, len(permutation), batch_size)]
    digest = hashlib.sha256()
    for number, indices in enumerate(batches, start=1):
        payload = [epoch, number, [list(keys[int(index)]) for index in indices]]
        digest.update(json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n")
    return batches, digest.hexdigest()


def _train_epoch(
    model: Any,
    bundle: WindowBundle,
    batches: Sequence[np.ndarray],
    *,
    optimizer: Any,
    weights: Any,
    device: Any,
) -> float:
    torch = _require_torch()
    model.train()
    total = 0.0
    rows = 0
    for indices in batches:
        x = torch.from_numpy(bundle.x[indices]).to(device=device, dtype=torch.float32)
        y = torch.from_numpy(bundle.y[indices]).to(device=device, dtype=torch.float32)
        optimizer.zero_grad(set_to_none=True)
        mu, logvar = model(x)
        loss = training_loss(mu, logvar, y, weights, 1.0)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        total += float(loss.item()) * len(indices)
        rows += len(indices)
    return total / rows


def _probabilistic_loss(
    model: Any, bundle: WindowBundle, *, batch_size: int, weights: Any, device: Any
) -> float:
    torch = _require_torch()
    model.eval()
    total = 0.0
    rows = 0
    with torch.no_grad():
        for start in range(0, len(bundle.x), batch_size):
            stop = min(start + batch_size, len(bundle.x))
            x = torch.from_numpy(bundle.x[start:stop]).to(device=device, dtype=torch.float32)
            y = torch.from_numpy(bundle.y[start:stop]).to(device=device, dtype=torch.float32)
            mu, logvar = model(x)
            loss = training_loss(mu, logvar, y, weights, 1.0)
            total += float(loss.item()) * (stop - start)
            rows += stop - start
    return total / rows


def fit_profile(
    bundle: WindowBundle,
    *,
    base_seed: int,
    profile: TrainingProfile,
) -> tuple[ProfileFit, Any]:
    device = _configure_seed(base_seed)
    training = bundle.subset("training")
    selection = bundle.subset("model_selection")
    if not len(training.x) or not len(selection.x):
        raise TemporalTrainingError("Training and model-selection rows are required")
    torch = _require_torch()
    model = make_model(
        input_dim=13,
        target_dim=9,
        hidden_dim=96,
        num_layers=1,
        dropout=0.0,
        residual_mode="add_last",
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.00001)
    weights = _loss_weights(device)
    keys = [
        [str(row[column]) for column in IDENTITY_COLUMNS]
        for row in training.metadata.to_dict(orient="records")
    ]
    best_objective = math.inf
    best_epoch = 0
    without_improvement = 0
    best_state: dict[str, Any] | None = None
    history: list[dict[str, Any]] = []
    for epoch in range(1, profile.maximum_epochs + 1):
        batches, digest = canonical_epoch_batches(
            keys, base_seed=base_seed, epoch=epoch, batch_size=profile.batch_size
        )
        train_loss = _train_epoch(
            model, training, batches, optimizer=optimizer, weights=weights, device=device
        )
        selection_loss = _probabilistic_loss(
            model, selection, batch_size=profile.batch_size, weights=weights, device=device
        )
        improved = selection_loss < best_objective - profile.minimum_delta
        if improved:
            best_objective = selection_loss
            best_epoch = epoch
            without_improvement = 0
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        else:
            without_improvement += 1
        history.append(
            {
                "profile": profile.name,
                "epoch": epoch,
                "training_loss": train_loss,
                "probabilistic_validation_loss": selection_loss,
                "best_probabilistic_validation_loss": best_objective,
                "best_epoch": best_epoch,
                "epochs_without_improvement": without_improvement,
                "batch_order_sha256": digest,
            }
        )
        if without_improvement >= profile.patience:
            break
    if best_state is None or best_epoch < 1 or not math.isfinite(best_objective):
        raise TemporalTrainingError(f"No finite best checkpoint for profile {profile.name}")
    model.load_state_dict(best_state)
    return (
        ProfileFit(
            profile=profile,
            best_epoch=best_epoch,
            best_objective=best_objective,
            epochs_ran=len(history),
            history=pd.DataFrame(history),
            best_state_dict=best_state,
        ),
        model,
    )


def fit_slot(
    bundle: WindowBundle,
    *,
    model_id: str,
    base_seed: int,
    profiles: Sequence[TrainingProfile],
) -> SlotFit:
    fitted: list[tuple[ProfileFit, Any]] = []
    for profile in profiles:
        fitted.append(fit_profile(bundle, base_seed=base_seed, profile=profile))
    ordered = sorted(
        fitted,
        key=lambda item: (
            item[0].best_objective,
            0 if item[0].profile.name == "v2_primary" else 1,
        ),
    )
    selected_fit, selected_model = ordered[0]
    selected_model.load_state_dict(selected_fit.best_state_dict)
    device = _configure_seed(base_seed)
    selected_model = selected_model.to(device)
    selection = bundle.subset("model_selection")
    weights = _loss_weights(device)
    blend_weights, blend_search = select_output_blend_weights(
        selected_model,
        cast(Any, TensorWindowDataset(selection.x, selection.y)),
        batch_size=selected_fit.profile.batch_size,
        grid=list(BLEND_GRID),
        selection_metric="balanced",
        device=device,
    )
    blend_tensor = _blend_weight_tensor(blend_weights, device)
    metrics_parts: list[pd.DataFrame] = []
    for role in ("training", "model_selection"):
        subset = bundle.subset(role)
        metrics, _ = evaluate_model(
            selected_model,
            cast(Any, TensorWindowDataset(subset.x, subset.y)),
            batch_size=selected_fit.profile.batch_size,
            weights=weights,
            device=device,
            blend_weights=blend_tensor,
        )
        metrics.insert(0, "time_role", role)
        metrics_parts.append(metrics)
    return SlotFit(
        model_id=model_id,
        base_seed=base_seed,
        selected_profile=selected_fit.profile.name,
        profile_fits=tuple(item[0] for item in fitted),
        model=selected_model,
        blend_weights=blend_weights,
        blend_search=blend_search,
        metrics=pd.concat(metrics_parts, ignore_index=True),
    )


def _slot_paths(model_id: str, base_seed: int) -> dict[str, Path]:
    model_root = Path(f"models/closure_v2/{model_id}/seed_{base_seed}")
    report_root = Path(f"reports/closure_v2/02_models/{model_id}/seed_{base_seed}")
    return {
        "model": model_root / "model.pt",
        "checkpoint": model_root / "checkpoint.pt",
        "curve": report_root / "training_curve.csv",
        "metrics": report_root / "selection_metrics.csv",
        "blend": report_root / "blend_weights.csv",
        "report": report_root / "report.md",
        "manifest": report_root / "manifest.json",
    }


def ensure_slot_absent(model_id: str, base_seed: int, *, root: Path = PROJECT_ROOT) -> None:
    paths = _slot_paths(model_id, base_seed)
    existing = [relative.as_posix() for relative in paths.values() if (root / relative).exists()]
    pointer_existing = [
        relative.with_suffix(relative.suffix + ".dvc").as_posix()
        for relative in (paths["model"], paths["checkpoint"])
        if (root / relative.with_suffix(relative.suffix + ".dvc")).exists()
    ]
    if existing or pointer_existing:
        raise TemporalTrainingError(
            f"Resume/replacement is forbidden for {model_id}/{base_seed}: {existing + pointer_existing}"
        )


def _torch_bytes(payload: Mapping[str, Any]) -> bytes:
    buffer = io.BytesIO()
    _require_torch().save(dict(payload), buffer)
    return buffer.getvalue()


def _virtual_record(relative: Path, content: bytes, role: str) -> dict[str, Any]:
    return {
        "path": relative.as_posix(),
        "role": role,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _exclusive_bundle(contents: Sequence[tuple[Path, bytes]], *, root: Path) -> None:
    created: list[tuple[Path, int]] = []
    temporaries: list[Path] = []
    try:
        for relative, content in contents:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise TemporalTrainingError(f"Refusing to overwrite slot output: {relative}")
            temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
            temporaries.append(temporary)
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, destination)
            created.append((destination, destination.stat().st_ino))
            temporary.unlink()
        if not contents or not contents[-1][0].name.endswith("manifest.json"):
            raise TemporalTrainingError("Slot completion manifest must be written last")
    except Exception:
        for destination, inode in reversed(created):
            if destination.is_file() and not destination.is_symlink() and destination.stat().st_ino == inode:
                destination.unlink()
        raise
    finally:
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)


def _environment() -> dict[str, Any]:
    torch = _require_torch()
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pa.__version__,
        "torch": torch.__version__,
        "device": "cpu",
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads(),
    }


def write_completed_slot(
    fit: SlotFit,
    bundle: WindowBundle,
    *,
    runtime_seconds: float,
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    paths = _slot_paths(fit.model_id, fit.base_seed)
    selected = next(item for item in fit.profile_fits if item.profile.name == fit.selected_profile)
    state_dict = {key: value.detach().cpu() for key, value in selected.best_state_dict.items()}
    checkpoint_payload = {
        "schema_version": "closure_v2_temporal_checkpoint_v1",
        "model_id": fit.model_id,
        "base_seed": fit.base_seed,
        "profile": fit.selected_profile,
        "best_epoch": selected.best_epoch,
        "best_probabilistic_validation_loss": selected.best_objective,
        "state_dict": state_dict,
    }
    blend_mapping = dict(
        zip(fit.blend_weights["target"].astype(str), fit.blend_weights["blend_weight"].astype(float), strict=True)
    )
    model_payload = {
        **checkpoint_payload,
        "schema_version": "closure_v2_temporal_model_v1",
        "architecture": {
            "input_dimension": 13,
            "target_dimension": 9,
            "hidden_dimension": 96,
            "recurrent_layers": 1,
            "dropout": 0.0,
            "residual_mode": "add_last",
        },
        "output_blend_weights": blend_mapping,
    }
    model_bytes = _torch_bytes(model_payload)
    checkpoint_bytes = _torch_bytes(checkpoint_payload)
    curve = pd.concat([item.history for item in fit.profile_fits], ignore_index=True)
    profile_rows = pd.DataFrame(
        [
            {
                "record_type": "profile_selection",
                "profile": item.profile.name,
                "selected": item.profile.name == fit.selected_profile,
                "best_epoch": item.best_epoch,
                "probabilistic_validation_loss": item.best_objective,
                "epochs_ran": item.epochs_ran,
                "time_role": "model_selection",
                "target": "all",
                "rows": 1016,
                "rmse": np.nan,
                "mae": np.nan,
                "nll": np.nan,
                "interval_90_coverage": np.nan,
                "interval_90_mean_width": np.nan,
            }
            for item in fit.profile_fits
        ]
    )
    metric_rows = fit.metrics.copy()
    metric_rows.insert(0, "record_type", "selected_profile_metric")
    metric_rows.insert(1, "profile", fit.selected_profile)
    metric_rows.insert(2, "selected", True)
    metric_rows.insert(3, "best_epoch", selected.best_epoch)
    metric_rows.insert(4, "probabilistic_validation_loss", selected.best_objective)
    metric_rows.insert(5, "epochs_ran", selected.epochs_ran)
    metrics = pd.concat([profile_rows, metric_rows], ignore_index=True)
    curve_bytes = _csv_bytes(curve)
    metric_bytes = _csv_bytes(metrics)
    blend_bytes = _csv_bytes(fit.blend_weights)
    report_lines = [
        f"# Closure V2 {fit.model_id} seed {fit.base_seed}",
        "",
        "- Status: completed.",
        f"- Selected profile: `{fit.selected_profile}` (model-selection only).",
        f"- Best epoch: {selected.best_epoch}.",
        f"- Best probabilistic validation loss: {selected.best_objective:.12f}.",
        "- Shared fit rows: 8,925 (training 7,909; model selection 1,016).",
        "- Retained ledger rows outside loss: 807 (including calibration and incomplete intent rows per slot).",
        "- Output blend: calculated once after restoring the selected raw best checkpoint.",
        f"- Runtime seconds: {runtime_seconds:.6f}.",
        "- Evaluation/outcomes accessed: no.",
        "- Replacement/resume: not used.",
        "",
    ]
    report_bytes = "\n".join(report_lines).encode("utf-8")
    output_records = [
        _virtual_record(paths["model"], model_bytes, "final_temporal_model"),
        _virtual_record(paths["checkpoint"], checkpoint_bytes, "raw_best_checkpoint"),
        _virtual_record(paths["curve"], curve_bytes, "training_curve"),
        _virtual_record(paths["metrics"], metric_bytes, "selection_metrics"),
        _virtual_record(paths["blend"], blend_bytes, "final_output_blend"),
        _virtual_record(paths["report"], report_bytes, "slot_report"),
    ]
    sequence_path = _sequence_path(fit.model_id, fit.base_seed)
    manifest = {
        "schema_version": "closure_v2_temporal_slot_manifest_v1",
        "experiment_id": "closure_v2",
        "status": "completed",
        "model_id": fit.model_id,
        "base_seed": fit.base_seed,
        "selected_profile": fit.selected_profile,
        "best_epoch": selected.best_epoch,
        "best_probabilistic_validation_loss": selected.best_objective,
        "profile_results": [
            {
                "profile": item.profile.name,
                "best_epoch": item.best_epoch,
                "best_probabilistic_validation_loss": item.best_objective,
                "epochs_ran": item.epochs_ran,
            }
            for item in fit.profile_fits
        ],
        "denominators": {
            "ledger_intent_rows": 9732,
            "fit_intent_rows": 9413,
            "shared_fit_rows": 8925,
            "training_rows": 7909,
            "model_selection_rows": 1016,
            "calibration_rows_excluded_from_fit": 319,
            "retained_fit_failures_outside_loss": 488,
        },
        "runtime_seconds": runtime_seconds,
        "environment": _environment(),
        "script": file_record(root / Path("src/experiments/closure_v2/train_temporal.py"), root=root, role="slot_trainer"),
        "inputs": [
            file_record(root / RUNTIME_CONFIG, root=root, role="development_runtime"),
            file_record(root / DEVELOPMENT_LOCK, root=root, role="development_lock"),
            file_record(root / ELIGIBILITY_MANIFEST, root=root, role="eligibility_manifest"),
            file_record(root / LEDGER_OUTPUT, root=root, role="eligibility_ledger"),
            file_record(root / SHARED_OUTPUT, root=root, role="shared_fit_keys"),
            file_record(root / sequence_path, root=root, role="source_sequences"),
        ],
        "outputs": output_records,
        "profile_selection_data_role": "model_selection",
        "output_blend_recalculations_after_selected_best_restore": 1,
        "evaluation_paths_opened": False,
        "post_2021_outcomes_opened": False,
        "current_chla_input_lineage": False,
        "replacement_used": False,
        "resume_used": False,
        "manifest_written_last": True,
    }
    manifest_bytes = canonical_json_bytes(manifest)
    _exclusive_bundle(
        [
            (paths["checkpoint"], checkpoint_bytes),
            (paths["model"], model_bytes),
            (paths["curve"], curve_bytes),
            (paths["metrics"], metric_bytes),
            (paths["blend"], blend_bytes),
            (paths["report"], report_bytes),
            (paths["manifest"], manifest_bytes),
        ],
        root=root,
    )
    return manifest


def write_failed_slot(
    model_id: str,
    base_seed: int,
    *,
    error: Exception,
    root: Path = PROJECT_ROOT,
) -> None:
    paths = _slot_paths(model_id, base_seed)
    if any((root / relative).exists() for relative in paths.values()):
        return
    message = f"{type(error).__name__}: {error}"
    report_bytes = (
        f"# Closure V2 {model_id} seed {base_seed}\n\n"
        f"- Status: failed.\n- Failure: `{message}`.\n"
        "- Replacement, resume and hyperparameter changes: forbidden.\n"
        "- Evaluation/outcomes accessed: no.\n"
    ).encode("utf-8")
    manifest = {
        "schema_version": "closure_v2_temporal_slot_manifest_v1",
        "experiment_id": "closure_v2",
        "status": "failed",
        "model_id": model_id,
        "base_seed": base_seed,
        "failure": message,
        "outputs": [_virtual_record(paths["report"], report_bytes, "failure_report")],
        "replacement_used": False,
        "resume_used": False,
        "evaluation_paths_opened": False,
        "post_2021_outcomes_opened": False,
        "manifest_written_last": True,
    }
    _exclusive_bundle(
        [(paths["report"], report_bytes), (paths["manifest"], canonical_json_bytes(manifest))],
        root=root,
    )


def smoke_fit() -> dict[str, Any]:
    rng = np.random.default_rng(20260823)
    x = rng.normal(0.0, 0.2, size=(32, 12, 13)).astype(np.float32)
    y = (x[:, -1, :9] + rng.normal(0.0, 0.01, size=(32, 9))).astype(np.float32)
    metadata = pd.DataFrame(
        {
            "source_id": ["synthetic"] * 32,
            "site_id": [f"synthetic:{index:03d}" for index in range(32)],
            "origin_year_month": ["2018-01"] * 24 + ["2019-01"] * 8,
            "target_year_month": ["2018-02"] * 24 + ["2019-02"] * 8,
            "time_role": ["training"] * 24 + ["model_selection"] * 8,
        }
    )
    bundle = WindowBundle(metadata=metadata, x=x, y=y)
    profiles = (
        TrainingProfile("v2_primary", 8, 3, 2, 0.0),
        TrainingProfile("legacy_diagnostic", 16, 2, 1, 0.0),
    )
    first = fit_slot(bundle, model_id="P0", base_seed=1729, profiles=profiles)
    second = fit_slot(bundle, model_id="P0", base_seed=1729, profiles=profiles)
    first_selected = next(item for item in first.profile_fits if item.profile.name == first.selected_profile)
    second_selected = next(item for item in second.profile_fits if item.profile.name == second.selected_profile)
    deterministic = (
        first.selected_profile == second.selected_profile
        and first_selected.best_epoch == second_selected.best_epoch
        and first_selected.best_objective == second_selected.best_objective
        and all(
            bool(_require_torch().equal(first_selected.best_state_dict[key], second_selected.best_state_dict[key]))
            for key in first_selected.best_state_dict
        )
    )
    if not deterministic:
        raise TemporalTrainingError("Synthetic smoke fit is not deterministic")
    return {
        "status": "passed",
        "rows": 32,
        "training_rows": 24,
        "model_selection_rows": 8,
        "selected_profile": first.selected_profile,
        "best_epoch": first_selected.best_epoch,
        "deterministic": True,
        "outputs_written": False,
    }


def _validate_dvc_pointer(artifact: Path, *, root: Path) -> dict[str, Any]:
    physical = _require_regular(root, artifact)
    pointer_relative = artifact.with_suffix(artifact.suffix + ".dvc")
    pointer = _require_regular(root, pointer_relative)
    loaded = yaml.safe_load(pointer.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise TemporalTrainingError(f"Invalid DVC pointer mapping: {pointer_relative}")
    payload = cast(Mapping[str, Any], loaded)
    outs = payload.get("outs")
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise TemporalTrainingError(f"Invalid single-file DVC pointer: {pointer_relative}")
    record = cast(Mapping[str, Any], outs[0])
    expected = {
        "md5": md5_file(physical),
        "size": physical.stat().st_size,
        "hash": "md5",
        "path": artifact.name,
    }
    if dict(record) != expected:
        raise TemporalTrainingError(f"DVC pointer does not match artifact: {pointer_relative}")
    return {
        "artifact": file_record(physical, root=root, role="temporal_model_artifact"),
        "pointer": file_record(pointer, root=root, role="dvc_pointer"),
        "dvc_md5": expected["md5"],
    }


def _validate_slot_for_summary(
    model_id: str, base_seed: int, *, root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    paths = _slot_paths(model_id, base_seed)
    manifest_path = _require_regular(root, paths["manifest"])
    manifest = dict(load_json_mapping(manifest_path))
    expected_identity = {
        "schema_version": "closure_v2_temporal_slot_manifest_v1",
        "status": "completed",
        "model_id": model_id,
        "base_seed": base_seed,
    }
    for key, expected in expected_identity.items():
        if manifest.get(key) != expected:
            raise TemporalTrainingError(
                f"Slot manifest identity/status mismatch for {model_id}/{base_seed}: {key}"
            )
    expected_denominators = {
        "ledger_intent_rows": 9732,
        "fit_intent_rows": 9413,
        "shared_fit_rows": 8925,
        "training_rows": 7909,
        "model_selection_rows": 1016,
        "calibration_rows_excluded_from_fit": 319,
        "retained_fit_failures_outside_loss": 488,
    }
    if manifest.get("denominators") != expected_denominators:
        raise TemporalTrainingError(f"Slot denominators drifted for {model_id}/{base_seed}")
    for predicate in (
        "evaluation_paths_opened",
        "post_2021_outcomes_opened",
        "current_chla_input_lineage",
        "replacement_used",
        "resume_used",
    ):
        if manifest.get(predicate) is not False:
            raise TemporalTrainingError(
                f"Forbidden slot predicate for {model_id}/{base_seed}: {predicate}"
            )
    if manifest.get("output_blend_recalculations_after_selected_best_restore") != 1:
        raise TemporalTrainingError(f"Output-blend count drifted for {model_id}/{base_seed}")

    outputs = cast(Sequence[Mapping[str, Any]], manifest.get("outputs", ()))
    output_by_path = {str(item.get("path")): item for item in outputs}
    for name in ("model", "checkpoint", "curve", "metrics", "blend", "report"):
        relative = paths[name]
        if relative.as_posix() not in output_by_path:
            raise TemporalTrainingError(f"Unregistered slot output: {relative}")
        _verify_record(output_by_path[relative.as_posix()], root=root)

    pointer_records = [
        _validate_dvc_pointer(paths["model"], root=root),
        _validate_dvc_pointer(paths["checkpoint"], root=root),
    ]
    metrics = pd.read_csv(root / paths["metrics"])
    selection = metrics.loc[
        metrics["record_type"].eq("selected_profile_metric")
        & metrics["time_role"].eq("model_selection")
    ].copy()
    if len(selection) != len(TARGET_COLUMNS) or set(selection["target"].astype(str)) != set(TARGET_COLUMNS):
        raise TemporalTrainingError(f"Incomplete selection metrics for {model_id}/{base_seed}")
    rows = []
    for metric in selection.sort_values("target", kind="stable").to_dict(orient="records"):
        rows.append(
            {
                "model_id": model_id,
                "base_seed": base_seed,
                "status": "completed",
                "selected_profile": manifest["selected_profile"],
                "best_epoch": manifest["best_epoch"],
                "best_probabilistic_validation_loss": manifest[
                    "best_probabilistic_validation_loss"
                ],
                "ledger_intent_rows": 9732,
                "fit_intent_rows": 9413,
                "shared_fit_rows": 8925,
                "target": metric["target"],
                "selection_rows": int(metric["rows"]),
                "selection_rmse": float(metric["rmse"]),
                "selection_mae": float(metric["mae"]),
                "selection_nll": float(metric["nll"]),
                "selection_interval_90_coverage": float(metric["interval_90_coverage"]),
                "selection_interval_90_mean_width": float(metric["interval_90_mean_width"]),
                "model_sha256": pointer_records[0]["artifact"]["sha256"],
                "model_dvc_md5": pointer_records[0]["dvc_md5"],
                "checkpoint_sha256": pointer_records[1]["artifact"]["sha256"],
                "checkpoint_dvc_md5": pointer_records[1]["dvc_md5"],
                "runtime_seconds": manifest["runtime_seconds"],
                "environment": json.dumps(
                    manifest["environment"], sort_keys=True, separators=(",", ":")
                ),
            }
        )
    input_records = [
        file_record(manifest_path, root=root, role="completed_slot_manifest"),
        *[record["artifact"] for record in pointer_records],
        *[record["pointer"] for record in pointer_records],
    ]
    return manifest, rows, input_records


def summarize_families(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    validate_development_authority(root)
    for relative in (FAMILY_SUMMARY, FAMILY_REPORT, FAMILY_MANIFEST):
        if (root / relative).exists() or (root / relative).is_symlink():
            raise TemporalTrainingError(f"Refusing to overwrite family summary: {relative}")
    slot_manifests: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    for model_id in MODEL_IDS:
        for base_seed in EXPECTED_SEEDS:
            manifest, slot_rows, slot_inputs = _validate_slot_for_summary(
                model_id, base_seed, root=root
            )
            slot_manifests.append(manifest)
            rows.extend(slot_rows)
            inputs.extend(slot_inputs)
    summary = pd.DataFrame(rows).sort_values(
        ["model_id", "base_seed", "target"], kind="stable"
    )
    summary_bytes = _csv_bytes(summary)
    report_lines = [
        "# Closure V2 temporal family summary",
        "",
        "- P0 availability: 5/5 completed slots.",
        "- P1 availability: 5/5 completed slots.",
        "- Per slot: 9,732 intent rows, 9,413 fit-intent rows, 8,925 shared eligible rows.",
        "- Profile and blend selection used model-selection data only.",
        "- Seeds are retained as an ensemble family; no seed was selected or replaced.",
        "- Evaluation, post-2021 outcomes and current-Chl-a lineage accessed: no.",
        "- Model/checkpoint SHA-256 and DVC MD5 hashes are recorded in family_summary.csv.",
        "",
    ]
    report_bytes = "\n".join(report_lines).encode("utf-8")
    output_records = [
        _virtual_record(FAMILY_SUMMARY, summary_bytes, "family_summary"),
        _virtual_record(FAMILY_REPORT, report_bytes, "family_report"),
    ]
    family_manifest = {
        "schema_version": "closure_v2_temporal_family_manifest_v1",
        "experiment_id": "closure_v2",
        "status": "completed_unpublished",
        "models": {"P0": {"completed_slots": 5}, "P1": {"completed_slots": 5}},
        "seeds": EXPECTED_SEEDS,
        "slot_count": len(slot_manifests),
        "selection_metric_rows": len(summary),
        "denominators_per_slot": {
            "ledger_intent_rows": 9732,
            "fit_intent_rows": 9413,
            "shared_fit_rows": 8925,
        },
        "script": file_record(
            root / Path("src/experiments/closure_v2/train_temporal.py"),
            root=root,
            role="family_summary_writer",
        ),
        "inputs": inputs,
        "outputs": output_records,
        "seed_selection_used": False,
        "replacement_used": False,
        "evaluation_paths_opened": False,
        "post_2021_outcomes_opened": False,
        "current_chla_input_lineage": False,
        "manifest_written_last": True,
    }
    manifest_bytes = canonical_json_bytes(family_manifest)
    _exclusive_bundle(
        [
            (FAMILY_SUMMARY, summary_bytes),
            (FAMILY_REPORT, report_bytes),
            (FAMILY_MANIFEST, manifest_bytes),
        ],
        root=root,
    )
    return family_manifest


def execute_slot(model_id: str, base_seed: int, *, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    validate_development_authority(root)
    runtime = validate_runtime(root / RUNTIME_CONFIG)
    ensure_slot_absent(model_id, base_seed, root=root)
    guard = root / f"tmp/closure_v2_train_{model_id}_{base_seed}.guard"
    guard.parent.mkdir(parents=True, exist_ok=True)
    try:
        guard.mkdir()
    except FileExistsError as error:
        raise TemporalTrainingError(f"Active/existing slot guard: {guard.relative_to(root)}") from error
    started = time.monotonic()
    try:
        bundle = load_slot_bundle(model_id, base_seed, root=root)
        fit = fit_slot(
            bundle,
            model_id=model_id,
            base_seed=base_seed,
            profiles=_profiles(runtime),
        )
        manifest = write_completed_slot(
            fit, bundle, runtime_seconds=time.monotonic() - started, root=root
        )
        return {
            "status": "completed_unpublished",
            "model_id": model_id,
            "base_seed": base_seed,
            "selected_profile": manifest["selected_profile"],
            "best_epoch": manifest["best_epoch"],
            "best_probabilistic_validation_loss": manifest["best_probabilistic_validation_loss"],
            "runtime_seconds": manifest["runtime_seconds"],
            "manifest": _slot_paths(model_id, base_seed)["manifest"].as_posix(),
        }
    except Exception as error:
        write_failed_slot(model_id, base_seed, error=error, root=root)
        raise
    finally:
        guard.rmdir()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=RUNTIME_CONFIG)
    parser.add_argument("--model-id", choices=MODEL_IDS)
    parser.add_argument("--base-seed", type=int)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.config != RUNTIME_CONFIG:
        raise TemporalTrainingError(f"Only the locked runtime is accepted: {RUNTIME_CONFIG}")
    authority = validate_development_authority()
    if args.smoke:
        result = {"authority": authority, "smoke": smoke_fit()}
    elif args.summarize:
        if args.model_id is not None or args.base_seed is not None:
            raise TemporalTrainingError("--summarize does not accept slot selectors")
        result = summarize_families()
    elif args.execute:
        if args.model_id is None or args.base_seed is None:
            raise TemporalTrainingError("--execute requires --model-id and --base-seed")
        result = execute_slot(args.model_id, args.base_seed)
    else:
        result = {
            "status": "ready_to_fit",
            "authority": authority,
            "registered_slots": [f"{model}/{seed}" for model in MODEL_IDS for seed in EXPECTED_SEEDS],
            "outputs_written": False,
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
