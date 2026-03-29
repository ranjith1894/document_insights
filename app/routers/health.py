from fastapi import APIRouter

from app.database import db
from app.redis_client import redis_client

router = APIRouter()


@router.get("/health")
async def health():
    mongo_ok = True
    redis_ok = True

    try:
        await db.command("ping")
    except Exception:
        mongo_ok = False

    try:
        await redis_client.ping()
    except Exception:
        redis_ok = False

    return {
        "status": "ok" if mongo_ok and redis_ok else "degraded",
        "mongodb": mongo_ok,
        "redis": redis_ok,
    }
