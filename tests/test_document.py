from unittest.mock import AsyncMock, patch
from bson import ObjectId

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import DocumentCreate


@pytest.fixture
def client():
    return TestClient(app)


class TestCreateDocument:
    def test_create_document_cache_hit(self, client):
        payload = {"user_id": "user1", "title": "Test", "content": "Test content"}
        mock_summary = {"short_summary": "Test", "word_count": 2}
        existing_doc_id = ObjectId()

        with patch(
            "app.routers.documents.get_cached_summary", new_callable=AsyncMock
        ) as mock_cache:
            with patch("app.routers.documents.make_content_hash") as mock_hash:
                with patch("app.routers.documents.db") as mock_db:
                    mock_hash.return_value = "hash123"
                    mock_cache.return_value = mock_summary
                    # Mock find_one to return existing document
                    mock_db.documents.find_one = AsyncMock(
                        return_value={
                            "_id": existing_doc_id,
                            "user_id": "user1",
                            "title": "Test",
                            "status": "completed",
                            "summary": mock_summary
                        }
                    )

                    response = client.post("/documents", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "completed"
        assert data["document_id"] == str(existing_doc_id)

    def test_create_document_job_limit_exceeded(self, client):
        payload = {"user_id": "user1", "title": "Test", "content": "Test content"}

        with patch(
            "app.routers.documents.get_cached_summary", new_callable=AsyncMock
        ) as mock_cache:
            with patch("app.routers.documents.make_content_hash") as mock_hash:
                with patch(
                    "app.routers.documents.get_active_job_count", new_callable=AsyncMock
                ) as mock_count:
                    mock_hash.return_value = "hash123"
                    mock_cache.return_value = None
                    mock_count.return_value = 3  # ACTIVE_JOB_LIMIT is 3

                    response = client.post("/documents", json=payload)

        assert response.status_code == 429
        assert "too many active" in response.json()["detail"]

    def test_create_document_queued(self, client):
        payload = {"user_id": "user1", "title": "Test", "content": "Test content"}
        new_doc_id = ObjectId()

        with patch(
            "app.routers.documents.get_cached_summary", new_callable=AsyncMock
        ) as mock_cache:
            with patch("app.routers.documents.make_content_hash") as mock_hash:
                with patch(
                    "app.routers.documents.get_active_job_count", new_callable=AsyncMock
                ) as mock_count:
                    with patch(
                        "app.routers.documents.increment_active_jobs", new_callable=AsyncMock
                    ) as mock_incr:
                        with patch(
                            "app.routers.documents.enqueue_document", new_callable=AsyncMock
                        ) as mock_enqueue:
                            with patch("app.routers.documents.db") as mock_db:
                                mock_hash.return_value = "hash123"
                                mock_cache.return_value = None
                                mock_count.return_value = 0
                                mock_db.documents.insert_one = AsyncMock()
                                mock_db.documents.insert_one.return_value.inserted_id = new_doc_id

                                response = client.post("/documents", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert "document_id" in data

    def test_create_document_missing_field(self, client):
        payload = {"user_id": "user1"}  # Missing title and content

        response = client.post("/documents", json=payload)

        assert response.status_code == 422

    def test_create_document_empty_content(self, client):
        payload = {"user_id": "user1", "title": "Test", "content": ""}

        response = client.post("/documents", json=payload)

        assert response.status_code == 422


class TestGetDocument:
    def test_get_document_found(self, client):
        doc_id = str(ObjectId())
        doc_data = {
            "_id": ObjectId(doc_id),
            "user_id": "user1",
            "title": "Test",
            "status": "completed",
            "content_hash": "hash123",
            "summary": {"short_summary": "Test"},
            "error_message": None,
        }

        with patch("app.routers.documents.db") as mock_db:
            with patch("app.routers.documents.serialize_document") as mock_serialize:
                mock_db.documents.find_one = AsyncMock(return_value=doc_data)
                mock_serialize.return_value = {
                    "document_id": doc_id,
                    "user_id": "user1",
                    "title": "Test",
                    "status": "completed",
                    "content_hash": "hash123",
                    "summary": {"short_summary": "Test"},
                    "error_message": None,
                }

                response = client.get(f"/documents/{doc_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == doc_id

    def test_get_document_not_found(self, client):
        doc_id = str(ObjectId())

        with patch("app.routers.documents.db") as mock_db:
            mock_db.documents.find_one = AsyncMock(return_value=None)

            response = client.get(f"/documents/{doc_id}")

        assert response.status_code == 404

    def test_get_document_invalid_id(self, client):
        response = client.get("/documents/invalid_id")

        assert response.status_code == 404


class TestListUserDocuments:
    def test_list_user_documents_default_pagination(self, client):
        doc_id = str(ObjectId())
        doc_data = {
            "_id": ObjectId(doc_id),
            "user_id": "user1",
            "title": "Test",
            "status": "completed",
            "content_hash": "hash123",
            "summary": None,
            "error_message": None,
            "created_at": "2024-01-01T00:00:00Z",
        }

        with patch("app.routers.documents.db") as mock_db:
            with patch("app.routers.documents.serialize_document") as mock_serialize:
                mock_db.documents.count_documents = AsyncMock(return_value=1)
                mock_cursor = AsyncMock()
                mock_cursor.__aiter__.return_value = [doc_data]
                mock_db.documents.find.return_value.sort.return_value.skip.return_value.limit.return_value = (
                    mock_cursor
                )
                mock_serialize.return_value = {
                    "document_id": doc_id,
                    "user_id": "user1",
                    "title": "Test",
                    "status": "completed",
                    "content_hash": "hash123",
                    "summary": None,
                    "error_message": None,
                }

                response = client.get("/users/user1/documents")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total"] == 1
        assert len(data["documents"]) == 1

    def test_list_user_documents_with_status_filter(self, client):
        doc_id = str(ObjectId())
        doc_data = {
            "_id": ObjectId(doc_id),
            "user_id": "user1",
            "title": "Test",
            "status": "completed",
            "content_hash": "hash123",
            "summary": None,
            "error_message": None,
            "created_at": "2024-01-01T00:00:00Z",
        }

        with patch("app.routers.documents.db") as mock_db:
            with patch("app.routers.documents.serialize_document") as mock_serialize:
                mock_db.documents.count_documents = AsyncMock(return_value=1)
                mock_cursor = AsyncMock()
                mock_cursor.__aiter__.return_value = [doc_data]
                mock_db.documents.find.return_value.sort.return_value.skip.return_value.limit.return_value = (
                    mock_cursor
                )
                mock_serialize.return_value = {
                    "document_id": doc_id,
                    "user_id": "user1",
                    "title": "Test",
                    "status": "completed",
                    "content_hash": "hash123",
                    "summary": None,
                    "error_message": None,
                }

                response = client.get("/users/user1/documents?status=completed")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_list_user_documents_pagination_second_page(self, client):
        with patch("app.routers.documents.db") as mock_db:
            mock_db.documents.count_documents = AsyncMock(return_value=25)
            mock_cursor = AsyncMock()
            mock_cursor.__aiter__.return_value = []
            mock_db.documents.find.return_value.sort.return_value.skip.return_value.limit.return_value = (
                mock_cursor
            )

            response = client.get("/users/user1/documents?page=2&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["total"] == 25

    def test_list_user_documents_invalid_page_size(self, client):
        response = client.get("/users/user1/documents?page_size=101")

        assert response.status_code == 422

    def test_list_user_documents_invalid_page(self, client):
        response = client.get("/users/user1/documents?page=0")

        assert response.status_code == 422
