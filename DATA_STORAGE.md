# DocumentInsights - Data Storage Guide

## Overview
This document explains how data is stored in **Redis** and **MongoDB** with practical examples.

---

## Redis Data Storage

Redis is used for:
1. **Summary Cache** - Stores processed document summaries
2. **Active Jobs Counter** - Tracks concurrent processing jobs per user
3. **Document Queue** - FIFO queue for background processing

### 1. Summary Cache

**Key Format:** `summary_cache:{user_id}:{content_hash}`

**Value:** JSON-serialized summary object (TTL: 1 hour / 3600 seconds)

#### Example:

```
Key: summary_cache:user123:a1b2c3d4e5f6g7h8...
Value: {
  "short_summary": "Artificial intelligence is transforming industries...",
  "word_count": 450,
  "character_count": 2847,
  "top_insights": [
    "AI improves efficiency",
    "Cost reduction achieved",
    "Enhanced decision making"
  ]
}

TTL: 3600 seconds (auto-expires)
```

**When it's used:**
- When creating a new document, system checks if same `user_id + content_hash` exists in cache
- If cached summary found → document marked as `completed` immediately
- Prevents reprocessing identical content from same user

**Use case example:**
If user123 uploads the same document twice:
- First request: Processes & caches result
- Second request: Retrieves from cache instantly (< 1ms)

---

### 2. Active Jobs Counter

**Key Format:** `active_jobs:{user_id}`

**Value:** Integer (current count)

#### Example:

```
Key: active_jobs:user123
Value: 2

(User currently has 2 documents being processed)
```

**Operations:**
- `INCR` → Increment when document queued
- `DECR` → Decrement when document finishes (completed/failed)
- `DELETE` → Remove key when count reaches 0

**Configuration:**
- `ACTIVE_JOB_LIMIT: 3` → Maximum 3 concurrent jobs per user
- Returns HTTP 429 if limit exceeded

**Example workflow:**
```
User123 uploads 3 documents:
1st upload:  active_jobs:user123 = 0 → 1 ✓
2nd upload:  active_jobs:user123 = 1 → 2 ✓
3rd upload:  active_jobs:user123 = 2 → 3 ✓
4th upload:  active_jobs:user123 = 3 ✗ Error 429 "Too many active documents"

Document completes processing:
Finish 1st:  active_jobs:user123 = 3 → 2 (now user can upload again)
```

---

### 3. Document Queue

**Key:** `document_queue`

**Type:** Redis List (FIFO)

**Value:** Document IDs (ObjectId as string)

#### Example:

```
Queue: document_queue
Contents (left to right, FIFO):
[
  "507f1f77bcf86cd799439011",
  "507f1f77bcf86cd799439012",
  "507f1f77bcf86cd799439013"
]

Operations:
- RPUSH → Add to right (enqueue new document)
- BLPOP → Remove from left (worker picks up)
```

**Workflow:**
```
1. POST /documents → Document created
2. RPUSH document_queue → Document ID added
3. Worker running: BLPOP document_queue
4. Worker processes the document
5. Updates MongoDB result
6. Worker caches summary in Redis
7. DECR active_jobs for user
```

---

## MongoDB Data Storage

Database: `document_insights`
Collection: `documents`

### Document Schema

```javascript
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "user_id": "user123",
  "title": "AI in Healthcare",
  "content": "Artificial intelligence is revolutionizing...",
  "content_hash": "a1b2c3d4e5f6g7h8...",
  "status": "completed",
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
  "error_message": null,
  "created_at": ISODate("2024-03-29T10:30:00Z"),
  "updated_at": ISODate("2024-03-29T10:35:45Z")
}
```

### Document Fields

| Field | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Auto-generated unique ID |
| `user_id` | String | Document owner (1-100 chars) |
| `title` | String | Document title (1-255 chars) |
| `content` | String | Full document content |
| `content_hash` | String | SHA256 hash of content (for deduplication) |
| `status` | String | `queued` \| `processing` \| `completed` \| `failed` |
| `summary` | Object | Processing result (null if not completed) |
| `error_message` | String | Error details if status is `failed` (null otherwise) |
| `created_at` | DateTime | Document creation timestamp |
| `updated_at` | DateTime | Last status update timestamp |

---

### Document Status Lifecycle

```
Created → queued → processing → completed
                              ↓
                            failed
```

#### Status Details:

**1. `queued`** (Waiting for processing)
```javascript
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "user_id": "user123",
  "title": "AI in Healthcare",
  "content": "...",
  "content_hash": "a1b2c3d4e5f6...",
  "status": "queued",      // ← Waiting in queue
  "summary": null,         // ← Not processed yet
  "error_message": null,
  "created_at": ISODate("2024-03-29T10:30:00Z"),
  "updated_at": ISODate("2024-03-29T10:30:00Z")
}
```

**2. `processing`** (Being processed by worker)
```javascript
{
  // ... same fields ...
  "status": "processing",    // ← Currently being processed
  "summary": null,           // ← Still null
  "updated_at": ISODate("2024-03-29T10:31:30Z")
}
```

**3. `completed`** (Successfully processed)
```javascript
{
  // ... same fields ...
  "status": "completed",     // ← Done
  "summary": {               // ← Contains result
    "short_summary": "AI is transforming healthcare...",
    "word_count": 450,
    "character_count": 2847,
    "top_insights": [
      "Improves diagnosis accuracy",
      "Reduces treatment time",
      "Lowers healthcare costs"
    ]
  },
  "error_message": null,
  "updated_at": ISODate("2024-03-29T10:35:45Z")
}
```

**4. `failed`** (Processing error)
```javascript
{
  // ... same fields ...
  "status": "failed",                           // ← Error occurred
  "summary": null,                              // ← No summary generated
  "error_message": "Simulated processing failure",  // ← Error details
  "updated_at": ISODate("2024-03-29T10:36:00Z")
}
```

---

### MongoDB Indexes

Indexes created for performance:

```javascript
// Index 1: User + Status queries (common filtering)
db.documents.createIndex([("user_id", 1), ("status", 1)])

// Index 2: User + Created date (sorting for list endpoint)
db.documents.createIndex([("user_id", 1), ("created_at", -1)])

// Index 3: User + Content hash (cache deduplication lookup)
db.documents.createIndex([("user_id", 1), ("content_hash", 1)])
```

**Why these indexes?**
- Fast user-specific queries
- Efficient sorting by creation date
- Quick cache hit detection

---

## Data Flow Example

### Scenario: User uploads document, waits for processing

```
Timeline:
─────────────────────────────────────────────────────────→

1. POST /documents
   Client: Sends document
   ↓
   
2. System hashes content
   content_hash = SHA256(content)
   ↓
   
3. Check Redis cache
   GET summary_cache:user123:{hash}
   → Cache miss (not cached before)
   ↓
   
4. Check active jobs limit
   GET active_jobs:user123 → 1 (has 1 active)
   → 1 < 3, so allowed
   ↓
   
5. Create MongoDB document
   INSERT documents {
     user_id: "user123",
     title: "AI in Healthcare",
     content: "...",
     content_hash: "{hash}",
     status: "queued",
     summary: null,
     created_at: now(),
     updated_at: now()
   }
   → Returns: _id = "507f1f77bcf86cd799439011"
   ↓
   
6. Increment active jobs
   INCR active_jobs:user123 → 2
   ↓
   
7. Enqueue for processing
   RPUSH document_queue → "507f1f77bcf86cd799439011"
   
   Response to client:
   {
     "document_id": "507f1f77bcf86cd799439011",
     "status": "queued"
   }

───────────────────────────── (Background Work) ─────────────────────────────

8. Worker picks up from queue
   BLPOP document_queue
   → Gets: "507f1f77bcf86cd799439011"
   ↓
   
9. Find document in MongoDB
   FIND documents {_id: "507f1f77bcf86cd799439011"}
   ↓
   
10. Update status to processing
    UPDATE documents SET status = "processing"
    ↓
    
11. Process document (10-30 seconds)
    Simulate: Generate summary
    ↓
    
12. Update MongoDB with results
    UPDATE documents SET {
      status: "completed",
      summary: {
        short_summary: "...",
        word_count: 450,
        ...
      },
      error_message: null,
      updated_at: now()
    }
    ↓
    
13. Cache result for same content
    SET summary_cache:user123:{hash}
    VALUE: {summary object}
    EX: 3600 (1 hour TTL)
    ↓
    
14. Decrement active jobs
    DECR active_jobs:user123 → 1

───────────────────────────────────────────────────────────

15. GET /documents/{document_id}
    Client: Polls for result
    ↓
    FIND documents {_id: "507f1f77bcf86cd799439011"}
    ↓
    Response:
    {
      "document_id": "507f1f77bcf86cd799439011",
      "user_id": "user123",
      "title": "AI in Healthcare",
      "status": "completed",
      "content_hash": "{hash}",
      "summary": {
        "short_summary": "...",
        "word_count": 450,
        ...
      },
      "error_message": null
    }
```

---

## Redis vs MongoDB Usage

| Operation | Storage | Reason |
|-----------|---------|--------|
| Cache summary | Redis | Fast lookups, auto-expire, deduplication |
| Track active jobs | Redis | Real-time counters, no persistence needed |
| Queue documents | Redis | FIFO ordering, atomic operations |
| Store documents | MongoDB | Persistent, queryable, indexed, audit trail |

---

## Configuration

From [app/config.py](app/config.py):

```python
MONGODB_URL: str = "mongodb://mongodb:27017"
MONGODB_DB: str = "document_insights"
REDIS_URL: str = "redis://redis:6379/0"
QUEUE_NAME: str = "document_queue"
CACHE_TTL_SECONDS: int = 3600      # 1 hour
ACTIVE_JOB_LIMIT: int = 3         # Max 3 concurrent
```

---

## Debugging

### View Redis data (CLI):

```bash
# Check cache
redis-cli GET "summary_cache:user123:a1b2c3d4..."

# Check active jobs
redis-cli GET "active_jobs:user123"

# View queue
redis-cli LRANGE document_queue 0 -1

# Count all keys
redis-cli DBSIZE
```

### View MongoDB data (CLI):

```bash
# Connect
mongosh "mongodb://mongodb:27017/document_insights"

# View all documents
db.documents.find().pretty()

# Find user's documents
db.documents.find({ user_id: "user123" }).pretty()

# Find by status
db.documents.find({ status: "completed" }).pretty()

# Count pending
db.documents.countDocuments({ status: "queued" })
```

