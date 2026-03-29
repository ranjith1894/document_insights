import json
from typing import Optional

from app.config import settings
from app.redis_client import redis_client


def cache_key(user_id: str, content_hash: str) -> str:
    return f"summary_cache:{user_id}:{content_hash}"


async def get_cached_summary(user_id: str, content_hash: str) -> Optional[dict]:
    try:
        value = await redis_client.get(cache_key(user_id, content_hash))
        return json.loads(value) if value else None
    except Exception:
        # graceful degradation if Redis is unavailable
        return None


async def set_cached_summary(user_id: str, content_hash: str, summary: dict) -> None:
    try:
        await redis_client.setex(
            cache_key(user_id, content_hash),
            settings.CACHE_TTL_SECONDS,
            json.dumps(summary),
        )
    except Exception:
        # graceful degradation if Redis is unavailable
        pass
