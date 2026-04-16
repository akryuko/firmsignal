import logging

logger = logging.getLogger(__name__)

try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    limiter = Limiter(key_func=get_remote_address)

    async def rate_limit_exceeded_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "detail": "Too many requests. Please wait before trying again.",
            },
        )

except ImportError:
    logger.warning("slowapi not installed — rate limiting disabled")

    class _NoopLimiter:  # type: ignore[no-redef]
        def limit(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator

    limiter = _NoopLimiter()  # type: ignore[assignment]
    rate_limit_exceeded_handler = None  # type: ignore[assignment]
