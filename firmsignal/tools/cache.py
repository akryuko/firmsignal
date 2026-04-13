import hashlib
import json
import os

CACHE_TTL = 86_400  # 24 hours


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