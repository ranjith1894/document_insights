from fastapi import HTTPException

from app.config import settings
from app.database import db
from app.redis_client import redis_client


def active_jobs_key(user_id: str) -> str:
    return f"active_jobs:{user_id}"


async def get_active_job_count(user_id: str) -> int:
    try:
        value = await redis_client.get(active_jobs_key(user_id))
        return int(value) if value else 0
    except Exception:
        # if Redis is down, fail safe by counting from MongoDB
        return await db.documents.count_documents(
            {"user_id": user_id, "status": {"$in": ["queued", "processing"]}}
        )


async def increment_active_jobs(user_id: str) -> None:
    try:
        await redis_client.incr(active_jobs_key(user_id))
    except Exception:
        pass


async def decrement_active_jobs(user_id: str) -> None:
    try:
        new_value = await redis_client.decr(active_jobs_key(user_id))
        if int(new_value) <= 0:
            await redis_client.delete(active_jobs_key(user_id))
    except Exception:
        pass


async def enqueue_document(document_id: str) -> None:
    try:
        await redis_client.rpush(settings.QUEUE_NAME, document_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Queue unavailable") from exc
