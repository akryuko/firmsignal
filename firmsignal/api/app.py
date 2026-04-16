from dotenv import load_dotenv
load_dotenv()

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from firmsignal.api.routes import router
from firmsignal.api.limiter import limiter, rate_limit_exceeded_handler

logger = logging.getLogger(__name__)

app = FastAPI(
    title="FirmSignal API",
    description="Multi-agent company intelligence system",
    version="0.1.0",
)

# ── Rate limiting ──────────────────────────────────────────────────────────────

app.state.limiter = limiter

if rate_limit_exceeded_handler is not None:
    try:
        from slowapi.errors import RateLimitExceeded
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    except Exception as e:
        logger.warning(f"Could not register rate limit handler: {e}")

# ── CORS ───────────────────────────────────────────────────────────────────────

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────────────────────

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "firmsignal"}
