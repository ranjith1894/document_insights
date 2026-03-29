import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.cache import (
    cache_key,
    get_cached_summary,
    set_cached_summary,
)
from app.core.queue import (
    active_jobs_key,
    decrement_active_jobs,
    enqueue_document,
    get_active_job_count,
    increment_active_jobs,
)
from app.core.utils import (
    make_content_hash,
    serialize_document,
    utc_now,
)


class TestMakeContentHash:
    def test_same_content_same_hash(self):
        content = "Hello World"
        hash1 = make_content_hash(content)
        hash2 = make_content_hash(content)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        hash1 = make_content_hash("Content 1")
        hash2 = make_content_hash("Content 2")
        assert hash1 != hash2

    def test_hash_is_sha256(self):
        content = "Test"
        result = make_content_hash(content)
        assert len(result) == 64  # SHA256 hex is 64 chars


class TestCacheKey:
    def test_cache_key_format(self):
        key = cache_key("user123", "hash456")
        assert key == "summary_cache:user123:hash456"

    def test_different_params_different_keys(self):
        key1 = cache_key("user1", "hash1")
        key2 = cache_key("user2", "hash1")
        assert key1 != key2


class TestActiveJobsKey:
    def test_active_jobs_key_format(self):
        key = active_jobs_key("user123")
        assert key == "active_jobs:user123"


class TestUtcNow:
    def test_returns_datetime(self):
        result = utc_now()
        assert isinstance(result, datetime)

    def test_returns_utc_timezone(self):
        result = utc_now()
        assert result.tzinfo == timezone.utc


class TestGetCachedSummary:
    @pytest.mark.asyncio
    async def test_get_cached_summary_found(self):
        summary_data = {"short_summary": "Test", "word_count": 2}
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(summary_data)

        with patch("app.core.cache.redis_client", mock_redis):
            result = await get_cached_summary("user1", "hash1")

        assert result == summary_data
        mock_redis.get.assert_called_once_with("summary_cache:user1:hash1")

    @pytest.mark.asyncio
    async def test_get_cached_summary_not_found(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch("app.core.cache.redis_client", mock_redis):
            result = await get_cached_summary("user1", "hash1")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_summary_redis_error(self):
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")

        with patch("app.core.cache.redis_client", mock_redis):
            result = await get_cached_summary("user1", "hash1")

        assert result is None


class TestSetCachedSummary:
    @pytest.mark.asyncio
    async def test_set_cached_summary_success(self):
        summary_data = {"short_summary": "Test", "word_count": 2}
        mock_redis = AsyncMock()

        with patch("app.core.cache.redis_client", mock_redis):
            await set_cached_summary("user1", "hash1", summary_data)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "summary_cache:user1:hash1"
        assert json.loads(call_args[0][2]) == summary_data

    @pytest.mark.asyncio
    async def test_set_cached_summary_redis_error(self):
        summary_data = {"short_summary": "Test"}
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis error")

        with patch("app.core.cache.redis_client", mock_redis):
            # Should not raise, graceful degradation
            await set_cached_summary("user1", "hash1", summary_data)


class TestGetActiveJobCount:
    @pytest.mark.asyncio
    async def test_get_active_job_count_from_redis(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "2"

        with patch("app.core.queue.redis_client", mock_redis):
            result = await get_active_job_count("user1")

        assert result == 2
        mock_redis.get.assert_called_once_with("active_jobs:user1")

    @pytest.mark.asyncio
    async def test_get_active_job_count_no_value(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch("app.core.queue.redis_client", mock_redis):
            result = await get_active_job_count("user1")

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_active_job_count_redis_error_falls_back_to_mongo(self):
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")
        mock_db = AsyncMock()
        mock_db.documents.count_documents.return_value = 1

        with patch("app.core.queue.redis_client", mock_redis):
            with patch("app.core.queue.db", mock_db):
                result = await get_active_job_count("user1")

        assert result == 1
        mock_db.documents.count_documents.assert_called_once()


class TestIncrementActiveJobs:
    @pytest.mark.asyncio
    async def test_increment_active_jobs(self):
        mock_redis = AsyncMock()

        with patch("app.core.queue.redis_client", mock_redis):
            await increment_active_jobs("user1")

        mock_redis.incr.assert_called_once_with("active_jobs:user1")

    @pytest.mark.asyncio
    async def test_increment_active_jobs_redis_error(self):
        mock_redis = AsyncMock()
        mock_redis.incr.side_effect = Exception("Redis error")

        with patch("app.core.queue.redis_client", mock_redis):
            # Should not raise
            await increment_active_jobs("user1")


class TestDecrementActiveJobs:
    @pytest.mark.asyncio
    async def test_decrement_active_jobs(self):
        mock_redis = AsyncMock()
        mock_redis.decr.return_value = "1"

        with patch("app.core.queue.redis_client", mock_redis):
            await decrement_active_jobs("user1")

        mock_redis.decr.assert_called_once_with("active_jobs:user1")

    @pytest.mark.asyncio
    async def test_decrement_active_jobs_and_delete_on_zero(self):
        mock_redis = AsyncMock()
        mock_redis.decr.return_value = "0"

        with patch("app.core.queue.redis_client", mock_redis):
            await decrement_active_jobs("user1")

        mock_redis.delete.assert_called_once_with("active_jobs:user1")

    @pytest.mark.asyncio
    async def test_decrement_active_jobs_redis_error(self):
        mock_redis = AsyncMock()
        mock_redis.decr.side_effect = Exception("Redis error")

        with patch("app.core.queue.redis_client", mock_redis):
            # Should not raise
            await decrement_active_jobs("user1")


class TestEnqueueDocument:
    @pytest.mark.asyncio
    async def test_enqueue_document_success(self):
        mock_redis = AsyncMock()

        with patch("app.core.queue.redis_client", mock_redis):
            await enqueue_document("doc123")

        mock_redis.rpush.assert_called_once_with("document_queue", "doc123")

    @pytest.mark.asyncio
    async def test_enqueue_document_redis_error(self):
        from fastapi import HTTPException

        mock_redis = AsyncMock()
        mock_redis.rpush.side_effect = Exception("Redis error")

        with patch("app.core.queue.redis_client", mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await enqueue_document("doc123")

        assert exc_info.value.status_code == 503


class TestSerializeDocument:
    def test_serialize_document_complete(self):
        doc = {
            "_id": "507f1f77bcf86cd799439011",
            "user_id": "user1",
            "title": "Test Doc",
            "status": "completed",
            "content_hash": "hash123",
            "summary": {"key": "value"},
            "error_message": None,
        }

        result = serialize_document(doc)

        assert result["document_id"] == "507f1f77bcf86cd799439011"
        assert result["user_id"] == "user1"
        assert result["title"] == "Test Doc"
        assert result["status"] == "completed"
        assert result["summary"] == {"key": "value"}
        assert result["error_message"] is None

    def test_serialize_document_without_summary(self):
        doc = {
            "_id": "507f1f77bcf86cd799439011",
            "user_id": "user1",
            "title": "Test Doc",
            "status": "queued",
            "content_hash": "hash123",
        }

        result = serialize_document(doc)

        assert result["summary"] is None
        assert result["error_message"] is None
