import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from src.api.core.audit import fire_audit
from src.api.core.dependencies import CurrentUser, DBDep
from src.api.core.openapi import HTTP_401, HTTP_404
from src.api.models.api_key import ApiKey
from src.api.models.audit_log import AuditAction
from src.api.schemas.api_key import ApiKeyCreateRequest, ApiKeyCreatedResponse, ApiKeyResponse
from src.api.schemas.common import Page

router = APIRouter(prefix="/auth/api-keys", tags=["Auth"])

_PREFIX_LEN = 8
_KEY_BYTES = 32


def _generate_key() -> tuple[str, str, str]:
    """Return (raw_key, prefix, sha256_hex)."""
    raw = f"lk_{secrets.token_urlsafe(_KEY_BYTES)}"
    prefix = raw[:_PREFIX_LEN]
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, prefix, key_hash


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description=(
        "Generate a new API key for programmatic access. "
        "The raw key is returned **once** at creation and never stored — "
        "save it immediately.\n\n"
        "Use the key as a Bearer token: `Authorization: Bearer lk_<key>`.\n\n"
        "Set `expires_days` to limit the key's validity (omit for no expiry)."
    ),
    responses={**HTTP_401},
)
async def create_api_key(body: ApiKeyCreateRequest, current_user: CurrentUser, db: DBDep):
    raw_key, prefix, key_hash = _generate_key()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=body.expires_days)
        if body.expires_days
        else None
    )
    api_key = ApiKey(
        user_id=current_user.id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scope=body.scope,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    fire_audit(
        AuditAction.api_key_created,
        user_id=current_user.id,
        resource_type="api_key",
        resource_id=str(api_key.id),
        detail={"name": body.name, "scope": body.scope},
    )

    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,
        key_prefix=prefix,
        scope=api_key.scope,
        expires_at=expires_at,
        created_at=api_key.created_at,
    )


@router.get(
    "",
    response_model=Page[ApiKeyResponse],
    summary="List API keys",
    description="List all API keys for the authenticated user. The raw key is never returned.",
    responses={**HTTP_401},
)
async def list_api_keys(
    current_user: CurrentUser,
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Zero-based page offset"),
):
    base_where = ApiKey.user_id == current_user.id
    total = (
        await db.execute(select(func.count()).select_from(ApiKey).where(base_where))
    ).scalar_one()
    items = list(
        (
            await db.execute(
                select(ApiKey)
                .where(base_where)
                .order_by(ApiKey.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API key",
    description="Permanently revoke (delete) an API key. The key is immediately unusable.",
    responses={**HTTP_401, **HTTP_404},
)
async def revoke_api_key(key_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    fire_audit(
        AuditAction.api_key_deleted,
        user_id=current_user.id,
        resource_type="api_key",
        resource_id=str(key_id),
        detail={"name": api_key.name},
    )
    await db.delete(api_key)
    await db.commit()
