from typing import Optional
from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class DocumentCreateResponse(BaseModel):
    document_id: str
    status: str


class DocumentResponse(BaseModel):
    document_id: str
    user_id: str
    title: str
    status: str
    content_hash: str
    summary: Optional[dict] = None
    error_message: Optional[str] = None
