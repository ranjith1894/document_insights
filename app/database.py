from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client = AsyncIOMotorClient(settings.MONGODB_URL)
db = client[settings.MONGODB_DB]


async def create_indexes() -> None:
    await db.documents.create_index([("user_id", 1), ("status", 1)])
    await db.documents.create_index([("user_id", 1), ("created_at", -1)])
    await db.documents.create_index([("user_id", 1), ("content_hash", 1)])