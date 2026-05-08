from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_context


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
logger = logging.getLogger("app.requests")


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, request_id_header: str) -> None:
        super().__init__(app)
        self.request_id_header = request_id_header

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = self._request_id(request)
        token = request_id_context.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[self.request_id_header] = request_id
            return response
        except Exception:
            logger.exception(
                "request.failed",
                extra=self._log_extra(request, status_code, started),
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "request.completed",
                extra=self._log_extra(request, status_code, started, duration_ms=duration_ms),
            )
            request_id_context.reset(token)

    def _request_id(self, request: Request) -> str:
        incoming = request.headers.get(self.request_id_header)
        if incoming and _REQUEST_ID_PATTERN.fullmatch(incoming):
            return incoming
        return uuid.uuid4().hex

    def _log_extra(
        self,
        request: Request,
        status_code: int,
        started: float,
        *,
        duration_ms: float | None = None,
    ) -> dict[str, object]:
        client_host = request.client.host if request.client else None
        return {
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": duration_ms if duration_ms is not None else round((time.perf_counter() - started) * 1000, 2),
            "client_host": client_host,
        }
