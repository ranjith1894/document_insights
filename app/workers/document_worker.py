import asyncio
import random

from bson import ObjectId
from pymongo import ReturnDocument

from app.config import settings
from app.database import db
from app.redis_client import redis_client
from app.core.cache import set_cached_summary
from app.core.queue import decrement_active_jobs
from app.core.utils import utc_now


def build_mock_summary(content: str) -> dict:
    words = content.split()

    short_summary = " ".join(words[:30])
    if len(words) > 30:
        short_summary += "..."

    return {
        "short_summary": short_summary,
        "word_count": len(words),
        "character_count": len(content),
        "top_insights": [
            "Mock insight 1",
            "Mock insight 2",
            "Mock insight 3",
        ],
    }


async def process_document(doc_id: str) -> None:
    object_id = ObjectId(doc_id)

    # Atomically move queued -> processing
    doc = await db.documents.find_one_and_update(
        {"_id": object_id, "status": "queued"},
        {"$set": {"status": "processing", "updated_at": utc_now()}},
        return_document=ReturnDocument.AFTER,
    )

    if not doc:
        return

    try:
        # Simulate long-running processing
        await asyncio.sleep(random.randint(10, 30))

        # Simulate ~10% random failure
        if random.random() < 0.1:
            raise RuntimeError("Simulated processing failure")

        summary = build_mock_summary(doc["content"])

        await db.documents.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": "completed",
                    "summary": summary,
                    "error_message": None,
                    "updated_at": utc_now(),
                }
            },
        )

        # Store cache for same user + same content
        await set_cached_summary(doc["user_id"], doc["content_hash"], summary)

        print(f"Document processed successfully: {doc_id}")

    except Exception as exc:
        await db.documents.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(exc),
                    "updated_at": utc_now(),
                }
            },
        )
        print(f"Document processing failed: {doc_id} | Error: {exc}")

    finally:
        await decrement_active_jobs(doc["user_id"])


async def worker_loop() -> None:
    print("Worker started and waiting for jobs...")

    while True:
        try:
            job = await redis_client.blpop(settings.QUEUE_NAME, timeout=5)

            if not job:
                await asyncio.sleep(1)
                continue

            _, doc_id = job
            print(f"Picked document from queue: {doc_id}")

            await process_document(doc_id)

        except Exception as exc:
            print(f"Worker loop error: {exc}")
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(worker_loop())
