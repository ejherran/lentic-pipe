"""
Email verification flow.

POST /auth/email/send-verification  — generate a 6-digit code and email it.
POST /auth/email/verify             — submit the code to mark email as verified.

If SMTP is not configured the code is logged to stdout. Admins can also retrieve
the pending code via GET /auth/email/pending-code (development helper).

> Emails sent from servers without SPF/DKIM/DMARC will likely land in spam.
> Inform users to check their spam folder and whitelist the sender address.
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update

from src.api.config import settings
from src.api.core.dependencies import CurrentUser, DBDep, require_system_role
from src.api.core.email import send_email
from src.api.core.limiter import RateLimiter
from src.api.core.openapi import HTTP_401, HTTP_429
from src.api.models.email_code import EmailCode, EmailCodePurpose
from src.api.models.user import SystemRole
from src.api.schemas.common import MessageResponse

router = APIRouter(prefix="/auth/email", tags=["Auth"])

_CODE_TTL_MINUTES = 30
_ADMIN_DEP = require_system_role(SystemRole.admin)


def _new_code() -> str:
    return str(secrets.randbelow(10**6)).zfill(6)


class VerifyRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"code": "482910"}}}
    code: str


@router.post(
    "/send-verification",
    response_model=MessageResponse,
    summary="Send email verification code",
    description=(
        "Generate a 6-digit verification code valid for 30 minutes and send it to the "
        "authenticated user's email address.\n\n"
        "If no SMTP server is configured, the code is printed to the server log "
        "and can be retrieved by an admin via `GET /auth/email/pending-code`.\n\n"
        "> ⚠ Emails from servers without SPF/DKIM/DMARC will likely land in **spam**. "
        "Ask users to check their spam folder and whitelist the sender."
    ),
    dependencies=[RateLimiter(times=5, hours=1)],
    responses={
        200: {"description": "Code sent (or logged if no SMTP configured)."},
        **HTTP_401,
        **HTTP_429,
    },
)
async def send_verification(current_user: CurrentUser, db: DBDep):
    if current_user.email_verified:
        return MessageResponse(message="Email is already verified")

    now = datetime.now(timezone.utc)
    await db.execute(
        update(EmailCode)
        .where(
            EmailCode.user_id == current_user.id,
            EmailCode.purpose == EmailCodePurpose.verification,
            EmailCode.used_at.is_(None),
        )
        .values(used_at=now)
    )

    code = _new_code()
    expires_at = now + timedelta(minutes=_CODE_TTL_MINUTES)
    db.add(
        EmailCode(
            user_id=current_user.id,
            code=code,
            purpose=EmailCodePurpose.verification,
            expires_at=expires_at,
        )
    )
    await db.commit()

    await send_email(
        to=current_user.email,
        subject="Verify your Lentic API email address",
        body_text=(
            f"Your verification code is: {code}\n\n"
            f"It expires in {_CODE_TTL_MINUTES} minutes.\n\n"
            "If you did not request this, you can ignore this email."
        ),
        body_html=(
            f"<p>Your verification code is: <strong>{code}</strong></p>"
            f"<p>It expires in {_CODE_TTL_MINUTES} minutes.</p>"
            "<p>If you did not request this, you can ignore this email.</p>"
        ),
    )
    return MessageResponse(message="Verification code sent")


@router.post(
    "/verify",
    response_model=MessageResponse,
    summary="Verify email with code",
    description=(
        "Submit the 6-digit code received by email to mark the account as verified. "
        "The code is single-use and expires after 30 minutes."
    ),
    responses={
        400: {"description": "Code is invalid, already used, or expired."},
        **HTTP_401,
    },
)
async def verify_email(body: VerifyRequest, current_user: CurrentUser, db: DBDep):
    if current_user.email_verified:
        return MessageResponse(message="Email is already verified")

    result = await db.execute(
        select(EmailCode).where(
            EmailCode.user_id == current_user.id,
            EmailCode.code == body.code,
            EmailCode.purpose == EmailCodePurpose.verification,
            EmailCode.used_at.is_(None),
            EmailCode.expires_at > datetime.now(timezone.utc),
        )
    )
    email_code = result.scalar_one_or_none()

    if not email_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already used code")

    email_code.used_at = datetime.now(timezone.utc)
    current_user.email_verified = True
    await db.commit()

    return MessageResponse(message="Email verified successfully")


@router.get(
    "/pending-code",
    response_model=MessageResponse,
    dependencies=[_ADMIN_DEP],
    include_in_schema=settings.APP_ENV != "production",
    summary="Retrieve pending verification code (admin / dev helper)",
    description=(
        "Returns the most recent unused verification code for the current user. "
        "**Only available to admins.** Intended for development environments where "
        "no SMTP server is configured and codes are only logged to stdout."
    ),
    responses={
        404: {"description": "No pending verification code found."},
        **HTTP_401,
    },
)
async def get_pending_code(current_user: CurrentUser, db: DBDep):
    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is not available in production",
        )
    result = await db.execute(
        select(EmailCode)
        .where(
            EmailCode.user_id == current_user.id,
            EmailCode.purpose == EmailCodePurpose.verification,
            EmailCode.used_at.is_(None),
        )
        .order_by(EmailCode.created_at.desc())
        .limit(1)
    )
    email_code = result.scalar_one_or_none()
    if not email_code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending verification code")
    return MessageResponse(message=f"Pending code: {email_code.code}")
