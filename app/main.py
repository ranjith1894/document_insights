from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import create_indexes, db
from app.routers.documents import router as document_router
from app.routers.health import router as health_router
from app.redis_client import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_indexes()
    yield
    # Shutdown (if needed, add cleanup here)


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.include_router(document_router)
app.include_router(health_router)