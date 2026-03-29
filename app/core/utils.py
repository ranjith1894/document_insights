import hashlib
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc)


def make_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def serialize_document(doc: dict) -> dict:
    return {
        "document_id": str(doc["_id"]),
        "user_id": doc["user_id"],
        "title": doc["title"],
        "status": doc["status"],
        "content_hash": doc["content_hash"],
        "summary": doc.get("summary"),
        "error_message": doc.get("error_message"),
    }
