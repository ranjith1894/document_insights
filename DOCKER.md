# Docker Setup Guide

This project is fully containerized using Docker and Docker Compose.

## Prerequisites

- Docker (version 20.10+)
- Docker Compose (version 1.29+)

## Quick Start

### 1. Start All Services

```bash
docker-compose up -d
```

This will start:
- **MongoDB** (port 27017)
- **Redis** (port 6379)
- **FastAPI** (port 8000)
- **Background Worker**

### 2. Check Service Status

```bash
docker-compose ps
```

### 3. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f mongodb
docker-compose logs -f redis
```

### 4. Access API

Visit: **http://localhost:8000**

- API Documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 5. Stop Services

```bash
docker-compose down
```

### 6. Clean Everything (Including Volumes)

```bash
docker-compose down -v
```

---

## Service Details

### MongoDB Container
- **Name:** document_insights_mongo
- **Image:** mongo:7.0
- **Port:** 27017
- **Volume:** `mongodb_data` (persistent storage)
- **Health Check:** Every 10s

```bash
# Connect to MongoDB
docker exec -it document_insights_mongo mongosh
```

### Redis Container
- **Name:** document_insights_redis
- **Image:** redis:7.0-alpine
- **Port:** 6379
- **Volume:** `redis_data` (persistent storage)
- **Health Check:** Every 10s

```bash
# Connect to Redis CLI
docker exec -it document_insights_redis redis-cli
```

### API Container
- **Name:** document_insights_api
- **Port:** 8000
- **Auto-reload:** Enabled (for development)
- **Volume:** Current directory mapped to `/app` (live code updates)

```bash
# View logs
docker-compose logs -f api

# Run command in container
docker exec -it document_insights_api pytest tests/
```

### Worker Container
- **Name:** document_insights_worker
- **Background Processing:** Async document processing
- **Volume:** Current directory mapped to `/app`

```bash
# View worker logs
docker-compose logs -f worker
```

---

## Environment Variables

Configure in `docker-compose.yml` under each service's `environment` section:

```yaml
environment:
  MONGODB_URL: mongodb://mongodb:27017
  MONGODB_DB: document_insights
  REDIS_URL: redis://redis:6379/0
  QUEUE_NAME: document_queue
  CACHE_TTL_SECONDS: 3600
  ACTIVE_JOB_LIMIT: 3
```

Or create `.env` file:

```bash
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DB=document_insights
REDIS_URL=redis://redis:6379/0
QUEUE_NAME=document_queue
CACHE_TTL_SECONDS=3600
ACTIVE_JOB_LIMIT=3
```

---

## Development Workflow

### 1. Start Services

```bash
docker-compose up -d
```

### 2. Test Changes

```bash
# Run tests inside container
docker exec -it document_insights_api pytest tests/ -v

# Or run specific test
docker exec -it document_insights_api pytest tests/test_models.py -v
```

### 3. Check Logs

```bash
docker-compose logs -f api
```

### 4. Rebuild After Dependency Changes

```bash
# If you add dependencies to requirements.txt
docker-compose up -d --build
```

---

## Production Deployment

### 1. Build Image

```bash
docker build -t document_insights:latest .
```

### 2. Run Single Instance

```bash
docker run -d \
  --name document_insights_api \
  -p 8000:8000 \
  -e MONGODB_URL=mongodb://mongo:27017 \
  -e REDIS_URL=redis://redis:6379/0 \
  document_insights:latest
```

### 3. Use Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  api:
    image: document_insights:latest
    container_name: document_insights_api
    restart: always
    ports:
      - "8000:8000"
    environment:
      MONGODB_URL: mongodb://mongodb:27017
      REDIS_URL: redis://redis:6379/0
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    networks:
      - document_network

  worker:
    image: document_insights:latest
    restart: always
    environment:
      MONGODB_URL: mongodb://mongodb:27017
      REDIS_URL: redis://redis:6379/0
    command: python -m app.workers.document_worker
    networks:
      - document_network

  mongodb:
    image: mongo:7.0
    restart: always
    ports:
      - "27017:27017"
    volumes:
      - mongodb_prod:/data/db
    networks:
      - document_network

  redis:
    image: redis:7.0-alpine
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis_prod:/data
    networks:
      - document_network

volumes:
  mongodb_prod:
  redis_prod:

networks:
  document_network:
    driver: bridge
```

Run with:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs

# Restart services
docker-compose restart

# Rebuild from scratch
docker-compose down -v && docker-compose up -d --build
```

### MongoDB Connection Error

```bash
# Check if MongoDB is running
docker-compose ps mongodb

# View MongoDB logs
docker-compose logs mongodb

# Restart MongoDB
docker-compose restart mongodb
```

### Redis Connection Error

```bash
# Check if Redis is running
docker-compose ps redis

# Test Redis connection
docker exec document_insights_redis redis-cli ping

# Restart Redis
docker-compose restart redis
```

### Port Already in Use

Change ports in `docker-compose.yml`:

```yaml
services:
  api:
    ports:
      - "8001:8000"  # Changed from 8000:8000

  mongodb:
    ports:
      - "27018:27017"  # Changed from 27017:27017

  redis:
    ports:
      - "6380:6379"  # Changed from 6379:6379
```

### API Shows Old Code Changes

Ensure volume is mounted correctly:

```bash
# Verify volume mount
docker-compose exec api pwd

# Should show: /app

# Check if files are synced
docker-compose exec api ls -la
```

---

## Container Networking

All containers are connected via `document_network`:

```
API (api:8000)
    ↓
MongoDB (mongodb:27017)
    ↓
Redis (redis:6379)
    ↓
Worker (background process)
```

Services communicate using container names:
- `mongodb://mongodb:27017` (API to DB)
- `redis://redis:6379/0` (API to Cache)

---

## Monitoring

### Resource Usage

```bash
docker stats
```

### Container Details

```bash
# Inspect container
docker inspect document_insights_api

# View networks
docker network ls
docker network inspect document_network
```

### Database Management

```bash
# MongoDB Shell
docker exec -it document_insights_mongo mongosh

# Redis CLI
docker exec -it document_insights_redis redis-cli

# View logs
docker logs document_insights_api
```

---

## File Structure

```
.
├── Dockerfile           # API application container
├── docker-compose.yml   # Development setup
├── .dockerignore        # Files to exclude from build
│
├── app/
│   ├── *.py
│   └── ...
│
├── tests/
│   ├── *.py
│   └── ...
│
├── requirements.txt
└── README.md
```

---

## Tips

1. **Live Code Reload:** Changes to Python files automatically reload in container (development mode)
2. **Persistent Data:** MongoDB and Redis data persists across restarts (volumes)
3. **Health Checks:** Services wait for dependencies to be healthy before starting
4. **Isolation:** Each service runs in its own container with isolated environment

---

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [MongoDB Docker Image](https://hub.docker.com/_/mongo)
- [Redis Docker Image](https://hub.docker.com/_/redis)
- [Python Docker Image](https://hub.docker.com/_/python)
