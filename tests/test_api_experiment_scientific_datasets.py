import asyncio
import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.core.dependencies import get_current_user
from src.api.database import Base, get_db
from src.api.models.experiment import CollaboratorRole, Experiment, ExperimentCollaborator
from src.api.models.run import ModelType
from src.api.models.user import SystemRole, User
from src.api.schemas.dataset import DatasetObservation, DatasetValidationRequest
from src.api.schemas.run import RunCreateRequest
from src.api.services.dataset_repository import register_dataset_request
from src.api.services.experiment_datasets import (
    build_scientific_dataset_meta,
    resolve_scientific_dataset_config,
    scientific_dataset_manifest_uri,
)


def _dataset_request() -> DatasetValidationRequest:
    return DatasetValidationRequest(
        dataset_name="Experiment Lake",
        requested_workflow="canonical_observations",
        observations=[
            DatasetObservation(
                source_id="experiment-upload",
                site_id="lake-a",
                observed_at="2024-01-15",
                variable="TP_ugL",
                value=35.0,
                unit="ug/L",
            )
        ],
    )


def test_scientific_dataset_meta_links_file_backed_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    registration = register_dataset_request(_dataset_request())

    meta = build_scientific_dataset_meta(registration, user_meta={"owner_note": "source export"})

    assert meta["kind"] == "lentic_scientific_dataset"
    assert meta["scientific_dataset_id"] == registration.dataset_id
    assert meta["content_sha256"] == registration.content_sha256
    assert meta["validation_outcome"] == registration.validation.outcome
    assert meta["artifact_uris"]["manifest"] == scientific_dataset_manifest_uri(registration)
    assert meta["user_meta"] == {"owner_note": "source export"}


def test_run_create_request_accepts_experiment_dataset_reference() -> None:
    request = RunCreateRequest(
        model_type=ModelType.pipe_grud,
        config={
            "experiment_dataset_id": str(uuid.uuid4()),
            "workflow": "canonical_observations",
        },
    )

    assert request.config is not None
    assert request.config["experiment_dataset_id"]


def test_resolve_scientific_dataset_config_requires_experiment_context() -> None:
    with pytest.raises(ValueError, match="inside an experiment run"):
        asyncio.run(
            resolve_scientific_dataset_config(
                {
                    "experiment_dataset_id": str(uuid.uuid4()),
                    "workflow": "canonical_observations",
                },
                experiment_id=None,
                db=None,
            )
        )


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


async def _ensure_postgres_database(url: str) -> None:
    if not url.startswith("postgresql"):
        return
    import asyncpg

    pg_url = url.replace("postgresql+asyncpg://", "postgresql://")
    db_name = pg_url.rsplit("/", 1)[-1]
    admin_url = pg_url.rsplit("/", 1)[0] + "/postgres"
    conn = await asyncpg.connect(admin_url)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def pg_session_factory():
    if TEST_DATABASE_URL is None:
        pytest.skip("Set TEST_DATABASE_URL to run experiment-scoped dataset HTTP tests.")
    await _ensure_postgres_database(TEST_DATABASE_URL)
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_register_experiment_scientific_dataset_creates_sql_and_science_links(
    pg_session_factory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.main import app

    monkeypatch.setenv("LENTIC_API_WORKSPACE", str(tmp_path))
    async with pg_session_factory() as session:
        user = User(
            email="scientist@example.test",
            username="scientist",
            hashed_password="not-used",
            system_role=SystemRole.researcher,
            is_active=True,
        )
        experiment = Experiment(title="External Lake API")
        session.add_all([user, experiment])
        await session.flush()
        session.add(
            ExperimentCollaborator(
                experiment_id=experiment.id,
                user_id=user.id,
                role=CollaboratorRole.owner,
            )
        )
        await session.commit()
        await session.refresh(user)
        await session.refresh(experiment)

    async def override_get_db():
        async with pg_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def override_current_user() -> User:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        with (
            patch("src.api.core.limiter.get_redis_client", side_effect=ConnectionError),
            patch("src.api.core.blocklist.get_redis_client", side_effect=ConnectionError),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/experiments/{experiment.id}/datasets/register",
                    json=_dataset_request().model_dump(mode="json", exclude_none=True),
                )
    finally:
        app.dependency_overrides.clear()
    body = response.json()

    assert response.status_code == 201, body
    dataset = body["dataset"]
    scientific_dataset = body["scientific_dataset"]
    assert dataset["experiment_id"] == str(experiment.id)
    assert dataset["name"] == "Experiment Lake"
    assert dataset["source_id"] == "experiment-upload"
    assert dataset["meta"]["scientific_dataset_id"] == scientific_dataset["dataset_id"]
    assert dataset["file_path"] == f"datasets/{scientific_dataset['dataset_id']}/manifest.json"

    async with pg_session_factory() as session:
        resolved = await resolve_scientific_dataset_config(
            {
                "experiment_dataset_id": dataset["id"],
                "workflow": "canonical_observations",
            },
            experiment_id=experiment.id,
            db=session,
        )

    assert resolved["dataset_id"] == scientific_dataset["dataset_id"]
    assert resolved["dataset_name"] == "Experiment Lake"
