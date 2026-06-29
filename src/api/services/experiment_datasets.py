"""Experiment-scoped scientific dataset helpers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.models.experiment import Dataset
from src.api.schemas.dataset import DatasetRegistrationResponse, DatasetValidationRequest

SCIENTIFIC_DATASET_META_KIND = "lentic_scientific_dataset"
_EXPERIMENT_DATASET_CONFIG_KEYS = ("experiment_dataset_id", "dataset_record_id")


def scientific_dataset_manifest_uri(registration: DatasetRegistrationResponse) -> str | None:
    """Return the manifest artifact URI for a registered scientific dataset."""

    for artifact in registration.artifacts:
        if artifact.name == "manifest":
            return artifact.uri
    return None


def derive_dataset_source_id(
    request: DatasetValidationRequest,
    *,
    explicit_source_id: str | None = None,
) -> str | None:
    """Derive a compact source id when the payload has a single source."""

    if explicit_source_id:
        return explicit_source_id
    source_ids = sorted({observation.source_id for observation in request.observations})
    if len(source_ids) == 1:
        return source_ids[0]
    return None


def build_scientific_dataset_meta(
    registration: DatasetRegistrationResponse,
    *,
    user_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the SQL metadata that links an experiment dataset to science artifacts."""

    artifact_uris = {artifact.name: artifact.uri for artifact in registration.artifacts}
    meta: dict[str, Any] = {
        "kind": SCIENTIFIC_DATASET_META_KIND,
        "scientific_dataset_id": registration.dataset_id,
        "content_sha256": registration.content_sha256,
        "requested_workflow": registration.requested_workflow,
        "validation_outcome": registration.validation.outcome,
        "validation_summary": registration.validation.summary.model_dump(mode="json"),
        "artifact_uris": artifact_uris,
        "registry": "local_workspace",
        "registry_version": "dataset_registry_v0",
    }
    if user_meta:
        meta["user_meta"] = user_meta
    return meta


def config_requests_scientific_workflow(config: dict[str, Any] | None) -> bool:
    """Return true when a run config requests a wired scientific workflow."""

    if not config or not (config.get("workflow") or config.get("science_workflow")):
        return False
    return bool(
        config.get("dataset_id")
        or any(config.get(key) for key in _EXPERIMENT_DATASET_CONFIG_KEYS)
    )


async def resolve_scientific_dataset_config(
    config: dict[str, Any],
    *,
    experiment_id: uuid.UUID | None,
    db: AsyncSession | None,
) -> dict[str, Any]:
    """Resolve an experiment dataset row to the file-backed scientific dataset id."""

    dataset_record_ref = _experiment_dataset_ref(config)
    if dataset_record_ref is None:
        if config.get("dataset_id"):
            return dict(config)
        raise ValueError("Scientific workflow config requires dataset_id or experiment_dataset_id.")

    if experiment_id is None or db is None:
        raise ValueError("experiment_dataset_id can only be resolved inside an experiment run.")

    try:
        dataset_record_id = uuid.UUID(dataset_record_ref)
    except ValueError as exc:
        raise ValueError("experiment_dataset_id must be a valid UUID.") from exc

    dataset = await db.get(Dataset, dataset_record_id)
    if not dataset or dataset.experiment_id != experiment_id:
        raise ValueError("Experiment dataset record does not exist for this run's experiment.")

    scientific_dataset_id = _scientific_dataset_id(dataset.meta)
    if scientific_dataset_id is None:
        raise ValueError(
            "Experiment dataset is metadata-only and is not linked to a registered "
            "scientific dataset."
        )

    resolved = dict(config)
    resolved["dataset_id"] = scientific_dataset_id
    resolved["experiment_dataset_id"] = str(dataset.id)
    resolved["dataset_record_id"] = str(dataset.id)
    resolved.setdefault("dataset_name", dataset.name)
    return resolved


def _experiment_dataset_ref(config: dict[str, Any]) -> str | None:
    for key in _EXPERIMENT_DATASET_CONFIG_KEYS:
        value = config.get(key)
        if value:
            return str(value)
    return None


def _scientific_dataset_id(meta: dict[str, Any] | None) -> str | None:
    if not meta:
        return None
    dataset_id = meta.get("scientific_dataset_id")
    if isinstance(dataset_id, str) and dataset_id:
        return dataset_id
    return None
