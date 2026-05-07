from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        enabled: bool,
        requests_per_window: int,
        window_seconds: int,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)

        key = self._client_key(request)
        now = time.monotonic()
        window = self._requests[key]
        while window and now - window[0] >= self.window_seconds:
            window.popleft()

        if len(window) >= self.requests_per_window:
            retry_after = max(1, round(self.window_seconds - (now - window[0])))
            return JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)
        return await call_next(request)

    def _client_key(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",", maxsplit=1)[0].strip()
        return request.client.host if request.client else "unknown"
