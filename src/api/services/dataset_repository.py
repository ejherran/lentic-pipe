"""Local file-backed dataset registration for the API scaffold."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from src.api.config import api_workspace
from src.api.schemas.dataset import (
    DatasetArtifact,
    DatasetRegistrationResponse,
    DatasetValidationRequest,
)
from src.api.services.dataset_validation import validate_dataset_request

_DATASET_ID_PATTERN = re.compile(r"^ds_[a-f0-9]{16}$")


class DatasetNotFoundError(Exception):
    """Raised when a dataset registry entry does not exist."""


def register_dataset_request(
    request: DatasetValidationRequest,
    *,
    workspace: Path | None = None,
) -> DatasetRegistrationResponse:
    """Validate and persist an external dataset request in the local workspace."""

    root = workspace or api_workspace()
    canonical_payload = _canonical_json(request.model_dump(mode="json", exclude_none=True))
    content_sha256 = _sha256_text(canonical_payload)
    dataset_id = f"ds_{content_sha256[:16]}"
    dataset_dir = _dataset_dir(dataset_id, root)
    manifest_path = dataset_dir / "manifest.json"

    if manifest_path.exists():
        return _read_response(manifest_path)

    validation = validate_dataset_request(request)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    payload_path = dataset_dir / "payload.json"
    validation_path = dataset_dir / "validation.json"

    _write_json(payload_path, request.model_dump(mode="json", exclude_none=True))
    _write_json(validation_path, validation.model_dump(mode="json"))

    artifacts = [
        _artifact(root, payload_path, "payload", "application/json"),
        _artifact(root, validation_path, "validation", "application/json"),
    ]
    response = DatasetRegistrationResponse(
        dataset_id=dataset_id,
        dataset_name=request.dataset_name,
        status="registered",
        registered_at=_now_utc(),
        content_sha256=content_sha256,
        requested_workflow=request.requested_workflow,
        validation=validation,
        artifacts=artifacts,
    )
    _write_json(manifest_path, response.model_dump(mode="json"))

    response.artifacts.append(_artifact(root, manifest_path, "manifest", "application/json"))
    _write_json(manifest_path, response.model_dump(mode="json"))
    return response


def read_registered_dataset(
    dataset_id: str,
    *,
    workspace: Path | None = None,
) -> DatasetRegistrationResponse:
    """Read a previously registered dataset response."""

    if not _DATASET_ID_PATTERN.fullmatch(dataset_id):
        raise DatasetNotFoundError(dataset_id)
    root = workspace or api_workspace()
    manifest_path = _dataset_dir(dataset_id, root) / "manifest.json"
    if not manifest_path.exists():
        raise DatasetNotFoundError(dataset_id)
    return _read_response(manifest_path)


def read_dataset_request(
    dataset_id: str,
    *,
    workspace: Path | None = None,
) -> DatasetValidationRequest:
    """Read the original normalized request payload for a registered dataset."""

    if not _DATASET_ID_PATTERN.fullmatch(dataset_id):
        raise DatasetNotFoundError(dataset_id)
    root = workspace or api_workspace()
    payload_path = _dataset_dir(dataset_id, root) / "payload.json"
    if not payload_path.exists():
        raise DatasetNotFoundError(dataset_id)
    return DatasetValidationRequest.model_validate(json.loads(payload_path.read_text(encoding="utf-8")))


def _dataset_dir(dataset_id: str, workspace: Path) -> Path:
    return workspace / "datasets" / dataset_id


def _read_response(path: Path) -> DatasetRegistrationResponse:
    return DatasetRegistrationResponse.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _artifact(root: Path, path: Path, name: str, media_type: str) -> DatasetArtifact:
    content = path.read_bytes()
    return DatasetArtifact(
        name=name,
        uri=path.relative_to(root).as_posix(),
        media_type=media_type,
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
