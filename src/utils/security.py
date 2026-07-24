import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from helpers.config import Settings


PUBLIC_PATH_PREFIXES = (
    "/api/v1/health",
    "/metrics",
    "/metrics24",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/admin",
)


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._requires_api_key(request) and request.headers.get("X-API-Key") != self.settings.API_KEY:
            return Response(
                content='{"detail":"Invalid or missing API key"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
            )

        if self.settings.RATE_LIMIT_ENABLED and self._is_rate_limited(request):
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={"Retry-After": str(self.settings.RATE_LIMIT_WINDOW_SECONDS)},
            )

        response = await call_next(request)
        self._add_security_headers(response)
        return response

    def _requires_api_key(self, request: Request) -> bool:
        return self.settings.REQUIRE_API_KEY and not request.url.path.startswith(PUBLIC_PATH_PREFIXES)

    def _is_rate_limited(self, request: Request) -> bool:
        if request.url.path.startswith(PUBLIC_PATH_PREFIXES):
            return False
        client_host = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - self.settings.RATE_LIMIT_WINDOW_SECONDS
        request_times = self._requests[client_host]
        while request_times and request_times[0] < window_start:
            request_times.popleft()
        if len(request_times) >= self.settings.RATE_LIMIT_REQUESTS:
            return True
        request_times.append(now)
        return False

    @staticmethod
    def _add_security_headers(response: Response) -> None:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")


def setup_security(app: FastAPI, settings: Settings) -> None:
    if settings.TRUSTED_HOSTS and "*" not in settings.TRUSTED_HOSTS:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials="*" not in settings.CORS_ALLOWED_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )
    app.add_middleware(SecurityMiddleware, settings=settings)
