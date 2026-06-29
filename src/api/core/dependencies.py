import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.blocklist import is_token_revoked
from src.api.core.permissions import experiment_role_gte, is_admin
from src.api.core.security import decode_token
from src.api.database import AsyncSessionLocal, get_db
from src.api.models.api_key import ApiKey, ApiKeyScope
from src.api.models.experiment import CollaboratorRole, Experiment, ExperimentCollaborator
from src.api.models.user import SystemRole, User

bearer_scheme = HTTPBearer()

DBDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]


def _enforce_scope(scope: ApiKeyScope, method: str, path: str) -> None:
    if scope == ApiKeyScope.full:
        return
    if method in ("GET", "HEAD"):
        return
    if scope == ApiKeyScope.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key scope 'read_only' does not permit write operations",
        )
    if scope == ApiKeyScope.predictions and not path.startswith("/predictions"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key scope 'predictions' only permits /predictions endpoints",
        )
    if scope == ApiKeyScope.simulations and not path.startswith("/simulations"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key scope 'simulations' only permits /simulations endpoints",
        )


async def _touch_api_key(api_key_id: uuid.UUID) -> None:
    try:
        async with AsyncSessionLocal() as db:
            key = await db.get(ApiKey, api_key_id)
            if key:
                key.last_used_at = datetime.now(timezone.utc)
                await db.commit()
    except Exception:
        pass


async def _user_from_api_key(
    raw_key: str, db: AsyncSession
) -> tuple[User, ApiKeyScope] | None:
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    api_key = result.scalar_one_or_none()
    if not api_key or not api_key.is_active:
        return None
    if api_key.expires_at:
        expires_at = api_key.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return None
    user = await db.get(User, api_key.user_id)
    if not user or not user.is_active:
        return None
    task = asyncio.create_task(_touch_api_key(api_key.id))
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
    return user, api_key.scope


async def get_current_user(request: Request, credentials: TokenDep, db: DBDep) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    raw = credentials.credentials

    # API key path: keys start with "lk_"
    if raw.startswith("lk_"):
        result = await _user_from_api_key(raw, db)
        if result is None:
            raise exc
        user, scope = result
        _enforce_scope(scope, request.method, str(request.url.path))
        return user

    # JWT path
    try:
        payload = decode_token(raw)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise exc

    if payload.get("type") != "access":
        raise exc

    user_id = payload.get("sub")
    if not user_id:
        raise exc

    if await is_token_revoked(user_id, payload.get("iat")):
        raise exc

    user = await db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise exc

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_system_role(*roles: SystemRole):
    async def guard(current_user: CurrentUser) -> User:
        if current_user.system_role not in roles and not is_admin(current_user.system_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient system permissions",
            )
        return current_user

    return Depends(guard)

async def get_experiment_or_404(
    experiment_id: uuid.UUID,
    db: DBDep,
) -> Experiment:
    experiment = await db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return experiment


async def _get_collaboration(
    experiment_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> ExperimentCollaborator | None:
    result = await db.execute(
        select(ExperimentCollaborator).where(
            ExperimentCollaborator.experiment_id == experiment_id,
            ExperimentCollaborator.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


def require_experiment_role(min_role: CollaboratorRole):
    """
    Dependency factory that returns the collaboration row if the current user
    has at least `min_role` on the experiment (or is admin).
    """

    async def guard(
        experiment_id: uuid.UUID,
        current_user: CurrentUser,
        db: DBDep,
    ) -> ExperimentCollaborator:
        if is_admin(current_user.system_role):
            # Admins have implicit owner-level access; return a synthetic row
            return ExperimentCollaborator(
                experiment_id=experiment_id,
                user_id=current_user.id,
                role=CollaboratorRole.owner,
            )

        collab = await _get_collaboration(experiment_id, current_user.id, db)
        if not collab or not experiment_role_gte(collab.role, min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have the required role on this experiment",
            )
        return collab

    return Depends(guard)
