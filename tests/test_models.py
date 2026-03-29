import pytest
from pydantic import ValidationError

from app.models.schemas import DocumentCreate, DocumentCreateResponse, DocumentResponse


class TestDocumentCreate:
    def test_document_create_valid(self):
        payload = {
            "user_id": "user123",
            "title": "My Document",
            "content": "This is the content",
        }
        doc = DocumentCreate(**payload)

        assert doc.user_id == "user123"
        assert doc.title == "My Document"
        assert doc.content == "This is the content"

    def test_document_create_missing_user_id(self):
        payload = {"title": "My Document", "content": "This is the content"}

        with pytest.raises(ValidationError) as exc_info:
            DocumentCreate(**payload)

        assert "user_id" in str(exc_info.value)

    def test_document_create_missing_title(self):
        payload = {"user_id": "user123", "content": "This is the content"}

        with pytest.raises(ValidationError) as exc_info:
            DocumentCreate(**payload)

        assert "title" in str(exc_info.value)

    def test_document_create_missing_content(self):
        payload = {"user_id": "user123", "title": "My Document"}

        with pytest.raises(ValidationError) as exc_info:
            DocumentCreate(**payload)

        assert "content" in str(exc_info.value)

    def test_document_create_empty_user_id(self):
        payload = {
            "user_id": "",
            "title": "My Document",
            "content": "This is the content",
        }

        with pytest.raises(ValidationError) as exc_info:
            DocumentCreate(**payload)

        assert "user_id" in str(exc_info.value)

    def test_document_create_empty_title(self):
        payload = {
            "user_id": "user123",
            "title": "",
            "content": "This is the content",
        }

        with pytest.raises(ValidationError) as exc_info:
            DocumentCreate(**payload)

        assert "title" in str(exc_info.value)

    def test_document_create_empty_content(self):
        payload = {"user_id": "user123", "title": "My Document", "content": ""}

        with pytest.raises(ValidationError) as exc_info:
            DocumentCreate(**payload)

        assert "content" in str(exc_info.value)

    def test_document_create_user_id_too_long(self):
        payload = {
            "user_id": "x" * 101,
            "title": "My Document",
            "content": "This is the content",
        }

        with pytest.raises(ValidationError) as exc_info:
            DocumentCreate(**payload)

        assert "user_id" in str(exc_info.value)

    def test_document_create_title_too_long(self):
        payload = {
            "user_id": "user123",
            "title": "x" * 256,
            "content": "This is the content",
        }

        with pytest.raises(ValidationError) as exc_info:
            DocumentCreate(**payload)

        assert "title" in str(exc_info.value)

    def test_document_create_boundary_values(self):
        payload = {
            "user_id": "u",
            "title": "t",
            "content": "c",
        }
        doc = DocumentCreate(**payload)

        assert doc.user_id == "u"
        assert doc.title == "t"
        assert doc.content == "c"


class TestDocumentCreateResponse:
    def test_document_create_response_valid(self):
        payload = {"document_id": "507f1f77bcf86cd799439011", "status": "queued"}
        response = DocumentCreateResponse(**payload)

        assert response.document_id == "507f1f77bcf86cd799439011"
        assert response.status == "queued"

    def test_document_create_response_missing_document_id(self):
        payload = {"status": "queued"}

        with pytest.raises(ValidationError) as exc_info:
            DocumentCreateResponse(**payload)

        assert "document_id" in str(exc_info.value)

    def test_document_create_response_missing_status(self):
        payload = {"document_id": "507f1f77bcf86cd799439011"}

        with pytest.raises(ValidationError) as exc_info:
            DocumentCreateResponse(**payload)

        assert "status" in str(exc_info.value)

    def test_document_create_response_completed_status(self):
        payload = {"document_id": "507f1f77bcf86cd799439011", "status": "completed"}
        response = DocumentCreateResponse(**payload)

        assert response.status == "completed"


class TestDocumentResponse:
    def test_document_response_complete(self):
        payload = {
            "document_id": "507f1f77bcf86cd799439011",
            "user_id": "user1",
            "title": "Test Document",
            "status": "completed",
            "content_hash": "hash123",
            "summary": {"short_summary": "Test", "word_count": 1},
            "error_message": None,
        }
        response = DocumentResponse(**payload)

        assert response.document_id == "507f1f77bcf86cd799439011"
        assert response.user_id == "user1"
        assert response.title == "Test Document"
        assert response.status == "completed"
        assert response.content_hash == "hash123"
        assert response.summary == {"short_summary": "Test", "word_count": 1}
        assert response.error_message is None

    def test_document_response_without_summary(self):
        payload = {
            "document_id": "507f1f77bcf86cd799439011",
            "user_id": "user1",
            "title": "Test Document",
            "status": "queued",
            "content_hash": "hash123",
        }
        response = DocumentResponse(**payload)

        assert response.summary is None
        assert response.error_message is None

    def test_document_response_with_error(self):
        payload = {
            "document_id": "507f1f77bcf86cd799439011",
            "user_id": "user1",
            "title": "Test Document",
            "status": "failed",
            "content_hash": "hash123",
            "error_message": "Processing failed",
        }
        response = DocumentResponse(**payload)

        assert response.status == "failed"
        assert response.error_message == "Processing failed"
        assert response.summary is None

    def test_document_response_missing_required_field(self):
        payload = {
            "document_id": "507f1f77bcf86cd799439011",
            "user_id": "user1",
            "title": "Test Document",
            "content_hash": "hash123",
        }

        with pytest.raises(ValidationError) as exc_info:
            DocumentResponse(**payload)

        assert "status" in str(exc_info.value)

    def test_document_response_all_statuses(self):
        for status in ["queued", "processing", "completed", "failed"]:
            payload = {
                "document_id": "507f1f77bcf86cd799439011",
                "user_id": "user1",
                "title": "Test Document",
                "status": status,
                "content_hash": "hash123",
            }
            response = DocumentResponse(**payload)

            assert response.status == status
