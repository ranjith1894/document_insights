from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.database import db
from app.models.schemas import DocumentCreate, DocumentCreateResponse, DocumentResponse
from app.core.cache import get_cached_summary
from app.core.queue import (
    enqueue_document,
    get_active_job_count,
    increment_active_jobs,
)
from app.core.utils import make_content_hash, serialize_document, utc_now

router = APIRouter()


@router.post("/documents", response_model=DocumentCreateResponse, status_code=201)
async def create_document(payload: DocumentCreate):
    """
    Flow:
    1. hash content
    2. check cache
    3. check active jobs limit
    4. store in MongoDB
    5. enqueue for worker
    """
    content_hash = make_content_hash(payload.content)

    # content-based cache
    cached_summary = await get_cached_summary(payload.user_id, content_hash)
    if cached_summary is not None:
        # Find the EXISTING document with this content
        existing_doc = await db.documents.find_one({
            "user_id": payload.user_id,
            "content_hash": content_hash,
            "status": "completed"
        })
        
        if existing_doc:
            return {
                "document_id": str(existing_doc["_id"]),
                "status": "completed",
            }

    active_count = await get_active_job_count(payload.user_id)
    if active_count >= settings.ACTIVE_JOB_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="User already has too many active documents",
        )

    now = utc_now()
    doc = {
        "user_id": payload.user_id,
        "title": payload.title,
        "content": payload.content,
        "content_hash": content_hash,
        "status": "queued",
        "summary": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }

    result = await db.documents.insert_one(doc)
    document_id = str(result.inserted_id)

    await increment_active_jobs(payload.user_id)
    await enqueue_document(document_id)

    return {
        "document_id": document_id,
        "status": "queued",
    }


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    if not ObjectId.is_valid(document_id):
        raise HTTPException(status_code=404, detail="Document not found")

    doc = await db.documents.find_one({"_id": ObjectId(document_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return serialize_document(doc)


@router.get("/users/{user_id}/documents")
async def list_user_documents(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
):
    query = {"user_id": user_id}
    if status:
        query["status"] = status

    skip = (page - 1) * page_size
    total = await db.documents.count_documents(query)

    cursor = (
        db.documents.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = []
    async for doc in cursor:
        items.append(serialize_document(doc))

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "documents": items,
    }
