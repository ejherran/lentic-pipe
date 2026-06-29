"""
Per-IP rate limiting using Redis INCR + EXPIRE (fixed window).

If Redis is unavailable the check is skipped and the request is allowed —
same fail-open policy used by the auth blocklist. This means rate limiting
is automatically disabled in test environments where Redis is not running.

X-Forwarded-For is only trusted when the direct connecting IP belongs to
a proxy listed in TRUSTED_PROXIES (config). Without that setting, the
connecting IP is always used directly, preventing header-spoofing attacks.
"""
import ipaddress
import logging

from fastapi import Depends, HTTPException, Request, status

from src.api.core.blocklist import get_redis_client
from src.api.config import settings

_logger = logging.getLogger(__name__)


def _parse_trusted_proxies(raw: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    if not raw.strip():
        return []
    result = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            result.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            _logger.warning("invalid_trusted_proxy_entry", extra={"entry": entry})
    return result


_TRUSTED_PROXY_NETS = _parse_trusted_proxies(settings.TRUSTED_PROXIES)


def _client_ip(request: Request) -> str:
    connecting = request.client.host if request.client else "127.0.0.1"
    forwarded = request.headers.get("X-Forwarded-For")
    if not forwarded or not _TRUSTED_PROXY_NETS:
        return connecting
    try:
        addr = ipaddress.ip_address(connecting)
        if any(addr in net for net in _TRUSTED_PROXY_NETS):
            return forwarded.split(",")[0].strip()
    except ValueError:
        pass
    return connecting


def RateLimiter(times: int, *, hours: int = 0, minutes: int = 0, seconds: int = 0):
    """
    FastAPI dependency factory for per-IP rate limiting.

    Usage:
        dependencies=[RateLimiter(times=10, hours=1)]
    """
    window = hours * 3600 + minutes * 60 + seconds
    if window <= 0:
        raise ValueError("At least one of hours, minutes, or seconds must be positive")

    async def _check(request: Request) -> None:
        ip = _client_ip(request)
        key = f"rl:{request.url.path}:{ip}:{window}:{times}"

        try:
            r = get_redis_client()
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            count, _ = await pipe.execute()
            if count > times:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Try again later.",
                )
        except HTTPException:
            raise
        except Exception:
            _logger.warning("rate_limit_check_failed", extra={"key": key})

    return Depends(_check)
