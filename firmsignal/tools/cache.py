import concurrent.futures
import hashlib
import json
import logging
import os

import requests

from firmsignal.tools.retry import tavily_retry

CACHE_TTL = 86_400  # 24 hours
_TAVILY_SEARCH_TIMEOUT = 10  # seconds per attempt

logger = logging.getLogger(__name__)


def _get_client():
    url = os.getenv("UPSTASH_REDIS_URL")
    token = os.getenv("UPSTASH_REDIS_TOKEN")
    if not url or not token:
        print("[cache] Upstash credentials not set — caching disabled")
        return None
    try:
        from upstash_redis import Redis
        return Redis(url=url, token=token)
    except Exception as e:
        print(f"[cache] Init failed: {e}")
        return None


def _cache_key(query: str) -> str:
    digest = hashlib.md5(query.lower().strip().encode()).hexdigest()
    return f"firmsignal:tavily:{digest}"


def get_cached(query: str) -> list[dict] | None:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(_cache_key(query))
        return json.loads(raw) if raw else None
    except Exception as e:
        print(f"[cache] Read failed: {e}")
        return None


def set_cached(query: str, results: list[dict]) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(_cache_key(query), CACHE_TTL, json.dumps(results))
    except Exception as e:
        print(f"[cache] Write failed: {e}")


@tavily_retry
def run_tavily_search(client, kwargs: dict) -> list[dict]:
    """
    Execute a single Tavily search attempt with a 10s per-attempt timeout.
    Wrapped with tavily_retry for automatic retries on timeout/connection/rate errors.
    Returns empty list on final failure — never raises.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(client.search, **kwargs)
    executor.shutdown(wait=False)
    try:
        response = future.result(timeout=_TAVILY_SEARCH_TIMEOUT)
        return response.get("results", [])
    except concurrent.futures.TimeoutError:
        logger.warning("[cache] Tavily search timed out after %ds", _TAVILY_SEARCH_TIMEOUT)
        raise requests.exceptions.Timeout(f"Tavily search exceeded {_TAVILY_SEARCH_TIMEOUT}s")
