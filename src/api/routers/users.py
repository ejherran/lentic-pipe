import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from src.api.core.audit import fire_audit
from src.api.core.blocklist import revoke_user_tokens
from src.api.core.dependencies import CurrentUser, DBDep, require_system_role
from src.api.core.openapi import HTTP_401, HTTP_403, HTTP_404, HTTP_422
from src.api.models.audit_log import AuditAction
from src.api.models.user import SystemRole, User
from src.api.schemas.common import Page
from src.api.schemas.user import AdminUserUpdateRequest, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])

AdminDep = require_system_role(SystemRole.admin)

_ADMIN_ONLY = "Requires `system_role: admin`."


@router.get(
    "",
    response_model=Page[UserResponse],
    dependencies=[AdminDep],
    summary="List all users",
    description=f"Paginated list of every registered user account. {_ADMIN_ONLY}",
    responses={**HTTP_401, **HTTP_403},
)
async def list_users(
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page (1–200)"),
    offset: int = Query(0, ge=0, description="Zero-based page offset"),
):
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return Page(items=list(result.scalars().all()), total=total, limit=limit, offset=offset)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[AdminDep],
    summary="Get user by ID",
    description=f"Retrieve a single user account by UUID. {_ADMIN_ONLY}",
    responses={**HTTP_401, **HTTP_403, **HTTP_404},
)
async def get_user(user_id: uuid.UUID, db: DBDep):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[AdminDep],
    summary="Update user",
    description=(
        f"Update a user's `email`, `full_name`, `system_role`, or `is_active` flag. "
        f"All fields are optional. {_ADMIN_ONLY}\n\n"
        "Setting `is_active: false` immediately prevents the user from obtaining new tokens."
    ),
    responses={**HTTP_401, **HTTP_403, **HTTP_404, **HTTP_422},
)
async def update_user(user_id: uuid.UUID, body: AdminUserUpdateRequest, current_user: CurrentUser, db: DBDep):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.email is not None and body.email != user.email:
        user.email = body.email
        user.email_verified = False
    if body.full_name is not None:
        user.full_name = body.full_name
    old_role = user.system_role
    if body.system_role is not None:
        user.system_role = body.system_role
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.commit()
    await db.refresh(user)

    if body.system_role is not None and body.system_role != old_role:
        fire_audit(
            AuditAction.role_changed,
            user_id=current_user.id,
            resource_type="user",
            resource_id=str(user_id),
            detail={"from": old_role, "to": body.system_role},
        )
        await revoke_user_tokens(str(user_id))
    if body.is_active is False:
        await revoke_user_tokens(str(user_id))
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminDep],
    summary="Delete user",
    description=(
        f"Permanently delete a user account. {_ADMIN_ONLY}\n\n"
        "Admins cannot delete their own account."
    ),
    responses={
        400: {"description": "Cannot delete your own account."},
        **HTTP_401,
        **HTTP_403,
        **HTTP_404,
    },
)
async def delete_user(user_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    fire_audit(
        AuditAction.user_deleted,
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(user_id),
        detail={"username": user.username},
    )
    await db.delete(user)
    await db.commit()
