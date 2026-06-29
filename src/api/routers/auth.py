import secrets
from datetime import datetime, timedelta, timezone
from typing import cast

import jwt
from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult

from src.api.config import settings
from src.api.core.audit import fire_audit
from src.api.core.blocklist import revoke_user_tokens
from src.api.core.dependencies import CurrentUser, DBDep
from src.api.core.email import send_email
from src.api.core.limiter import RateLimiter
from src.api.core.openapi import HTTP_401, HTTP_409, HTTP_422, HTTP_429
from src.api.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.api.models.audit_log import AuditAction
from src.api.models.email_code import EmailCode, EmailCodePurpose
from src.api.models.user import RefreshToken, SystemRole, User
from src.api.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    SessionResponse,
    TokenResponse,
)
from src.api.schemas.common import MessageResponse, Page
from src.api.schemas.user import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)

_RESET_CODE_TTL_MINUTES = 30

# Constant-time dummy used to prevent username enumeration via bcrypt timing.
# Always run verify_password even when the user doesn't exist.
_DUMMY_HASH: str = hash_password("__dummy_constant_lentic__")

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Create a new user account. All new accounts receive `system_role: researcher`.\n\n"
        "**Constraints:**\n"
        "- `username`: 3–50 alphanumeric characters, hyphens and underscores allowed, stored lowercase.\n"
        "- `password`: minimum 8 characters.\n"
        "- `email` and `username` must be unique across the system.\n\n"
        "Returns `403` if the administrator has disabled public registration "
        "(`REGISTRATION_ENABLED=false`).\n\n"
        "**Rate limit:** 10 registrations per hour per IP."
    ),
    dependencies=[RateLimiter(times=10, hours=1)],
    responses={
        403: {"description": "Public registration is disabled."},
        **HTTP_409,
        **HTTP_422,
        **HTTP_429,
    },
)
async def register(request: Request, body: RegisterRequest, db: DBDep):
    if not settings.REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )
    existing = await db.execute(
        select(User).where((User.email == body.email) | (User.username == body.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username already registered",
        )

    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        system_role=SystemRole.researcher,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    fire_audit(
        AuditAction.user_registered,
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and obtain a token pair",
    description=(
        "Authenticate with username and password. Returns an access token (valid 30 min) "
        "and a refresh token (valid 7 days).\n\n"
        "**Rate limit:** 20 per minute, 100 per hour per IP."
    ),
    dependencies=[
        RateLimiter(times=20, minutes=1),
        RateLimiter(times=100, hours=1),
    ],
    responses={
        401: {"description": "Invalid username or password."},
        403: {"description": "Account is disabled."},
        **HTTP_429,
    },
)
async def login(request: Request, body: LoginRequest, db: DBDep):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    stored_hash = user.hashed_password if user else _DUMMY_HASH
    if not verify_password(body.password, stored_hash) or not user:
        fire_audit(
            AuditAction.login_failure,
            ip_address=request.client.host if request.client else None,
            detail={"username": body.username},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    fire_audit(
        AuditAction.login_success,
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    access_token = create_access_token(user.id, user.system_role)
    refresh_token_str, jti = create_refresh_token(user.id)

    token_row = RefreshToken(
        user_id=user.id,
        jti=jti,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(token_row)
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token_str)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token",
    description=(
        "Exchange a valid refresh token for a new access + refresh token pair. "
        "The submitted token is **immediately revoked** (single-use rotation).\n\n"
        "If the same token is presented a second time it is rejected — this protects "
        "against replay attacks after a token has been stolen.\n\n"
        "**Rate limit:** 30 per minute per IP."
    ),
    dependencies=[RateLimiter(times=30, minutes=1)],
    responses={**HTTP_401, **HTTP_429},
)
async def refresh_token(body: RefreshRequest, db: DBDep):
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError:
        raise exc

    if payload.get("type") != "refresh":
        raise exc

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise exc

    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    token_row = result.scalar_one_or_none()
    if not token_row or token_row.is_revoked:
        raise exc
    expires_at = token_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = await db.get(User, token_row.user_id)
    if not user or not user.is_active:
        raise exc

    token_row.revoked_at = datetime.now(timezone.utc)

    new_refresh_str, new_jti = create_refresh_token(user.id)
    new_token_row = RefreshToken(
        user_id=user.id,
        jti=new_jti,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_token_row)
    await db.commit()

    access_token = create_access_token(user.id, user.system_role)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_str)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke a refresh token",
    description=(
        "Revoke a single refresh token. The associated access token remains valid until "
        "its natural 30-minute expiry. To invalidate all sessions use `POST /auth/me/logout-all`."
    ),
    responses={**HTTP_401},
)
async def logout(body: RefreshRequest, db: DBDep):
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError:
        raise exc

    if payload.get("type") != "refresh":
        raise exc

    jti = payload.get("jti")
    if not jti:
        raise exc

    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    token_row = result.scalar_one_or_none()
    if token_row and not token_row.is_revoked:
        token_row.revoked_at = datetime.now(timezone.utc)
        await db.commit()

    return MessageResponse(message="Logged out successfully")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get own profile",
    description="Return the authenticated user's full profile.",
    responses={**HTTP_401},
)
async def get_me(current_user: CurrentUser):
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update own profile",
    description=(
        "Update the authenticated user's `email` and/or `full_name`. "
        "All fields are optional — only provided fields are changed."
    ),
    responses={**HTTP_401, **HTTP_409, **HTTP_422},
)
async def update_me(body: UserUpdateRequest, current_user: CurrentUser, db: DBDep):
    if body.email and body.email != current_user.email:
        conflict = (
            await db.execute(select(User).where(User.email == body.email))
        ).scalar_one_or_none()
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        current_user.email = body.email
        current_user.email_verified = False
    if body.full_name is not None:
        current_user.full_name = body.full_name
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post(
    "/me/logout-all",
    response_model=MessageResponse,
    summary="Revoke all sessions",
    description=(
        "Revoke every active refresh token associated with the authenticated account. "
        "Use this to sign out from all devices simultaneously. "
        "The current access token remains valid until it expires naturally."
    ),
    responses={**HTTP_401},
)
async def logout_all(current_user: CurrentUser, db: DBDep):
    now = datetime.now(timezone.utc)
    cursor = cast(
        CursorResult,
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        ),
    )
    await db.commit()
    await revoke_user_tokens(str(current_user.id))
    return MessageResponse(message=f"Revoked {cursor.rowcount} active session(s)")


@router.post(
    "/me/change-password",
    response_model=MessageResponse,
    summary="Change password",
    description=(
        "Change the authenticated user's password. On success, **all active refresh tokens "
        "for the account are revoked** — the user must log in again on all devices.\n\n"
        "**Rules:**\n"
        "- `current_password` must match the stored password.\n"
        "- `new_password` must differ from the current password.\n"
        "- `new_password` must be at least 8 characters."
    ),
    responses={
        400: {"description": "Wrong current password, or new password identical to current."},
        **HTTP_401,
        **HTTP_422,
    },
)
async def change_password(body: ChangePasswordRequest, current_user: CurrentUser, db: DBDep):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from current password",
        )
    current_user.hashed_password = hash_password(body.new_password)
    now = datetime.now(timezone.utc)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.commit()
    await revoke_user_tokens(str(current_user.id))
    fire_audit(AuditAction.password_changed, user_id=current_user.id)
    return MessageResponse(message="Password updated successfully")


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    summary="Request a password-reset code",
    description=(
        "Send a 6-digit password-reset code to the given email address. "
        "The code is valid for 30 minutes.\n\n"
        "Always returns `200` regardless of whether the email exists, to avoid user enumeration. "
        "If SMTP is not configured the code is logged to stdout and retrievable by an admin "
        "via `GET /auth/email/pending-code`.\n\n"
        "**Rate limit:** 5 per hour per IP."
    ),
    dependencies=[RateLimiter(times=5, hours=1)],
    responses={**HTTP_429},
)
async def request_password_reset(body: PasswordResetRequest, db: DBDep):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user:
        code = str(secrets.randbelow(10**6)).zfill(6)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=_RESET_CODE_TTL_MINUTES)
        db.add(EmailCode(
            user_id=user.id,
            code=code,
            purpose=EmailCodePurpose.password_reset,
            expires_at=expires_at,
        ))
        await db.commit()

        await send_email(
            to=user.email,
            subject="Lentic API — password reset code",
            body_text=(
                f"Your password reset code is: {code}\n\n"
                f"It expires in {_RESET_CODE_TTL_MINUTES} minutes.\n\n"
                "If you did not request a password reset, ignore this email."
            ),
            body_html=(
                f"<p>Your password reset code is: <strong>{code}</strong></p>"
                f"<p>It expires in {_RESET_CODE_TTL_MINUTES} minutes.</p>"
                "<p>If you did not request a password reset, ignore this email.</p>"
            ),
        )

    return MessageResponse(message="If that email is registered, a reset code has been sent")


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    summary="Confirm password reset with code",
    description=(
        "Submit the 6-digit code and a new password. On success all active refresh tokens "
        "for the account are revoked — the user must log in again on all devices.\n\n"
        "The code is single-use and expires after 30 minutes."
    ),
    responses={
        400: {"description": "Code invalid, already used, or expired."},
        **HTTP_422,
    },
)
async def confirm_password_reset(body: PasswordResetConfirmRequest, db: DBDep):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    code_result = await db.execute(
        select(EmailCode).where(
            EmailCode.user_id == user.id,
            EmailCode.code == body.code,
            EmailCode.purpose == EmailCodePurpose.password_reset,
            EmailCode.used_at.is_(None),
            EmailCode.expires_at > datetime.now(timezone.utc),
        )
    )
    email_code = code_result.scalar_one_or_none()
    if not email_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    now = datetime.now(timezone.utc)
    email_code.used_at = now
    user.hashed_password = hash_password(body.new_password)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.commit()
    await revoke_user_tokens(str(user.id))
    fire_audit(AuditAction.password_reset, user_id=user.id)
    return MessageResponse(message="Password reset successfully")


@router.get(
    "/me/sessions",
    response_model=Page[SessionResponse],
    summary="List active sessions",
    description=(
        "Return all active (non-revoked) refresh token sessions for the authenticated account. "
        "Useful for auditing which devices are logged in."
    ),
    responses={**HTTP_401},
)
async def list_sessions(
    current_user: CurrentUser,
    db: DBDep,
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Zero-based page offset"),
):
    base_where = (
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked_at.is_(None),
    )
    total = (
        await db.execute(select(func.count()).select_from(RefreshToken).where(*base_where))
    ).scalar_one()
    items = list(
        (
            await db.execute(
                select(RefreshToken)
                .where(*base_where)
                .order_by(RefreshToken.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/me/notifications",
    response_model=NotificationPreferencesResponse,
    summary="Get notification preferences",
    description="Return the authenticated user's email notification preferences.",
    responses={**HTTP_401},
)
async def get_notifications(current_user: CurrentUser):
    return current_user


@router.patch(
    "/me/notifications",
    response_model=NotificationPreferencesResponse,
    summary="Update notification preferences",
    description=(
        "Update which job-completion events trigger an email notification. "
        "All fields are optional — only provided fields are changed.\n\n"
        "Notifications are only sent when the account has a verified email address. "
        "Configure SMTP settings to enable actual delivery."
    ),
    responses={**HTTP_401},
)
async def update_notifications(
    body: NotificationPreferencesUpdateRequest, current_user: CurrentUser, db: DBDep
):
    if body.notify_on_run_completed is not None:
        current_user.notify_on_run_completed = body.notify_on_run_completed
    if body.notify_on_run_failed is not None:
        current_user.notify_on_run_failed = body.notify_on_run_failed
    if body.notify_on_simulation_completed is not None:
        current_user.notify_on_simulation_completed = body.notify_on_simulation_completed
    if body.notify_on_simulation_failed is not None:
        current_user.notify_on_simulation_failed = body.notify_on_simulation_failed
    await db.commit()
    await db.refresh(current_user)
    return current_user
