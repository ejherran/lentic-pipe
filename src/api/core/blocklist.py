"""Redis-backed access token revocation by user + issue-time.

When a user logs out all sessions, changes their password, or resets their
password, all access tokens issued before that moment are immediately invalid
even though they have not expired yet.

The Redis key ``auth:revoke:<user_id>`` stores the UNIX timestamp T; any
access token with ``iat < T`` is treated as revoked.  The key TTL is set to
``ACCESS_TOKEN_EXPIRE_MINUTES`` so it auto-cleans once no unexpired access
token can reference the user.

A module-level ConnectionPool is used so all calls share connections instead
of opening a new socket per request.
"""
import logging
from datetime import datetime, timezone

from redis.asyncio import ConnectionPool, Redis

from src.api.config import settings

_logger = logging.getLogger(__name__)
_PREFIX = "auth:revoke:"

_pool: ConnectionPool | None = None


def get_redis_client() -> Redis:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            max_connections=10,
        )
    return Redis(connection_pool=_pool)


async def revoke_user_tokens(user_id: str) -> None:
    try:
        r = get_redis_client()
        ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        now_ts = str(int(datetime.now(timezone.utc).timestamp()))
        await r.setex(f"{_PREFIX}{user_id}", ttl, now_ts)
    except Exception:
        _logger.warning("blocklist_write_failed", extra={"user_id": user_id})


async def is_token_revoked(user_id: str, issued_at: int | None) -> bool:
    if issued_at is None:
        return False
    try:
        r = get_redis_client()
        raw = await r.get(f"{_PREFIX}{user_id}")
        if raw is None:
            return False
        return issued_at < int(raw)
    except Exception:
        _logger.warning("blocklist_read_failed", extra={"user_id": user_id})
        return False
