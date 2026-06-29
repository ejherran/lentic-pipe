import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from src.api.config import settings


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _make_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: uuid.UUID, system_role: str) -> str:
    return _make_token(
        {"sub": str(user_id), "role": system_role, "type": "access", "iat": _now_ts()},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
    """Returns (token_string, jti). Store jti in DB for revocation."""
    jti = str(uuid.uuid4())
    token = _make_token(
        {"sub": str(user_id), "jti": jti, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return token, jti


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
