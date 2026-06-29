import asyncio
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.api.config import settings

_logger = logging.getLogger(__name__)


class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            _logger.warning(
                "request_timeout",
                extra={"path": request.url.path, "timeout": settings.REQUEST_TIMEOUT_SECONDS},
            )
            return JSONResponse(
                {"error": "Request timed out. Please try again later."},
                status_code=504,
            )
