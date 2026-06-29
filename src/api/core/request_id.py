import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

_logger = logging.getLogger("lentic.access")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Reads X-Request-ID from the incoming request (useful when Nginx or a client sets it)
    or generates a new UUID4. Stores it in a ContextVar and echoes it back in the response.
    Emits a structured access log entry for every request.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers[REQUEST_ID_HEADER] = request_id
        _logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client": request.client.host if request.client else None,
            },
        )
        return response


def get_request_id() -> str:
    return request_id_var.get()
