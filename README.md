# DocumentInsights API

A FastAPI-based document processing system with Redis caching, MongoDB persistence, and background workers.

## Features

- **Document Processing**: Upload documents for AI-powered summarization
- **Smart Caching**: Deduplicates content (same user + same content = instant result)
- **Job Queue Management**: Limits concurrent processing per user
- **Background Workers**: Asynchronous document processing
- **Health Monitoring**: Real-time MongoDB and Redis status checks
- **RESTful API**: Fully documented with OpenAPI/Swagger

## Architecture

```
API (FastAPI)
    ↓
MongoDB ← Documents (persistent storage, indexed)
Redis ← Cache, Queue, Job counters (fast operations)
    ↓
Background Worker (async processing)
```

## Project Structure

```
app/
├── config.py           # Configuration settings
├── database.py         # MongoDB setup
├── main.py            # FastAPI app, lifespan events
├── redis_client.py    # Redis connection
│
├── core/              # Business logic
│   ├── cache.py       # Summary caching
│   ├── queue.py       # Document queue & job counting
│   └── utils.py       # Utilities (hash, time, serialization)
│
├── models/            # Data schemas
│   └── schemas.py     # Pydantic models
│
├── routers/           # API endpoints
│   ├── documents.py   # Document CRUD
│   └── health.py      # Health check
│
└── workers/           # Background processing
    └── document_worker.py  # Document processing job
```

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and navigate to project
cd DocumentInsights

# Start all services (MongoDB, Redis, API, Worker)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Visit: **http://localhost:8000/docs**

For detailed Docker instructions, see [DOCKER.md](DOCKER.md).

### Option 2: Local Setup

Prerequisites:
- Python 3.8+
- MongoDB
- Redis

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Terminal 1: MongoDB
docker run -p 27017:27017 mongo

# Terminal 2: Redis
docker run -p 6379:6379 redis

# Terminal 3: API Server
uvicorn app.main:app --reload
# Visit: http://localhost:8000/docs

# Terminal 4: Background Worker
python -m app.workers.document_worker
```

## API Endpoints

### POST /documents
Create a new document for processing.

```bash
curl -X POST "http://localhost:8000/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "title": "AI in Healthcare",
    "content": "Artificial intelligence is revolutionizing..."
  }'

# Response:
{
  "document_id": "507f1f77bcf86cd799439011",
  "status": "queued"
}
```

### GET /documents/{document_id}
Retrieve a document's details and processing result.

```bash
curl "http://localhost:8000/documents/507f1f77bcf86cd799439011"

# Response (when completed):
{
  "document_id": "507f1f77bcf86cd799439011",
  "user_id": "user123",
  "title": "AI in Healthcare",
  "status": "completed",
  "content_hash": "a1b2c3d4e5f6...",
  "summary": {
    "short_summary": "AI is transforming healthcare...",
    "word_count": 450,
    "character_count": 2847,
    "top_insights": [
      "Improves diagnosis accuracy",
      "Reduces treatment time",
      "Lowers healthcare costs"
    ]
  },
  "error_message": null
}
```

### GET /users/{user_id}/documents
List all documents for a user with pagination and filtering.

```bash
curl "http://localhost:8000/users/user123/documents?page=1&page_size=10&status=completed"

# Response:
{
  "page": 1,
  "page_size": 10,
  "total": 25,
  "documents": [
    { ... },
    { ... }
  ]
}
```

### GET /health
Check API health and service dependencies.

```bash
curl "http://localhost:8000/health"

# Response:
{
  "status": "ok",
  "mongodb": true,
  "redis": true
}
```

## Data Storage

For detailed information on how data is stored in **Redis** and **MongoDB**, see [DATA_STORAGE.md](DATA_STORAGE.md).

### Quick Summary:

**Redis:**
- `summary_cache:{user_id}:{content_hash}` → Cached summaries (1 hour TTL)
- `active_jobs:{user_id}` → Active job counter
- `document_queue` → FIFO processing queue

**MongoDB:**
- `documents` collection with fields:
  - `user_id`, `title`, `content`, `content_hash`
  - `status` (queued/processing/completed/failed)
  - `summary`, `error_message`
  - `created_at`, `updated_at`

## Configuration

Edit [app/config.py](app/config.py) or set environment variables:

```python
APP_NAME = "Document Insights API"
MONGODB_URL = "mongodb://localhost:27017"
MONGODB_DB = "document_insights"
REDIS_URL = "redis://localhost:6379/0"
QUEUE_NAME = "document_queue"
CACHE_TTL_SECONDS = 3600        # 1 hour
ACTIVE_JOB_LIMIT = 3            # Max 3 concurrent jobs
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_service.py -v

# Run with coverage
pytest tests/ --cov=app
```

## Key Features Explained

### 1. Content-Based Deduplication
same user uploads the same content twice:
- First request: Processed, result cached in Redis
- Second request: Result retrieved from cache instantly

### 2. Job Limit Management
- User can have max 3 documents processing concurrently
- Attempts to exceed limit receive HTTP 429 error
- Counter decremented when job completes

### 3. Graceful Degradation
- If Redis is down, system falls back to MongoDB for job counting
- Cache operations fail silently (no exceptions bubbled to client)
- MongoDB is required; Redis failures are non-fatal

### 4. Status Lifecycle
- `queued` → Waiting in queue
- `processing` → Being processed by worker
- `completed` → Done, summary available
- `failed` → Error occurred, error_message populated

## Environment Variables

Create `.env` file:

```bash
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=document_insights
REDIS_URL=redis://localhost:6379/0
QUEUE_NAME=document_queue
CACHE_TTL_SECONDS=3600
ACTIVE_JOB_LIMIT=3
```

## Troubleshooting

### Using Docker

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Restart a service
docker-compose restart api

# Rebuild images
docker-compose up -d --build

# Clean everything
docker-compose down -v
```

See [DOCKER.md](DOCKER.md) for detailed Docker troubleshooting.

### Documents stuck in "queued" status
- Check if worker is running: `docker-compose logs worker` (Docker) or `python -m app.workers.document_worker` (Local)
- Verify Redis connection: `docker exec document_insights_redis redis-cli ping` (Docker)
- Check MongoDB connection: `docker exec document_insights_mongo mongosh` (Docker)

### High latency on document creation
- Check Redis performance: `docker exec document_insights_redis redis-cli --latency` (Docker)
- Check MongoDB indexes: `db.documents.getIndexes()` (in MongoDB shell)
- Monitor active jobs per user

### Memory issues
- Check Redis memory: `docker exec document_insights_redis redis-cli INFO memory` (Docker)
- Check container resource usage: `docker stats`
- Clear old cache entries: `FLUSHDB` (warning: destructive)

## Development

### Docker Development

For development with Docker, see [DOCKER.md - Development Workflow](DOCKER.md#development-workflow):

```bash
# Start services
docker-compose up -d

# Run tests in container
docker exec -it document_insights_api pytest tests/ -v

# View logs
docker-compose logs -f api

# Rebuild after dependency changes
docker-compose up -d --build
```

### Project Structure Benefits

```
- core/     → Business logic (testable, reusable)
- routers/  → API endpoints (FastAPI decorators)
- workers/  → Background jobs (independent processes)
- models/   → Shared data schemas (Pydantic)
```

### Adding a New Router

1. Create file in `app/routers/`
```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/endpoint")
async def my_endpoint():
    return {"status": "ok"}
```

2. Include in [app/main.py](app/main.py):
```python
from app.routers.my_router import router as my_router

app.include_router(my_router)
```

## License

MIT

## Support

For issues or questions, please check the [DATA_STORAGE.md](DATA_STORAGE.md) guide for data structure details.
