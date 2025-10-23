# Data Model: Twitch Chat Bot

**Feature**: Tier 2 Twitch Chat Bot
**Date**: 2025-10-22

## Entity Relationship Overview

```
┌─────────────────┐
│   ChatMessage   │
└────────┬────────┘
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌────────────────┐   ┌──────────────┐
│  BotCommand    │   │ UserRateLimit │
└────────┬───────┘   └───────┬──────┘
         │                   │
         │                   │
         ▼                   │
┌────────────────────┐       │
│ AIQuestionRequest  │       │
└──────────┬─────────┘       │
           │                 │
           └────────┬────────┘
                    │
                    ▼
           ┌────────────────┐
           │ModerationEvent │
           └────────────────┘

┌─────────────┐
│StreamStatus │  (from OBS orchestrator)
└─────────────┘
```

---

## Core Entities

### 1. ChatMessage

**Description**: Represents incoming message from Twitch chat

**Source**: TwitchIO `Message` event

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `sender_username` | `str` | Yes | Twitch username | 4-25 chars, alphanumeric + underscore |
| `content` | `str` | Yes | Message text | Max 500 chars (Twitch limit) |
| `timestamp` | `datetime` | Yes | When received (UTC) | ISO 8601 format |
| `channel_name` | `str` | Yes | Channel where sent | Must match configured channel |
| `is_command` | `bool` | Yes | Starts with `!` prefix | Computed from content |

**Example**:
```python
{
    "sender_username": "viewer123",
    "content": "!ask what is recursion?",
    "timestamp": "2025-10-22T15:30:45Z",
    "channel_name": "your_channel",
    "is_command": True
}
```

---

### 2. BotCommand

**Description**: Parsed command from chat message

**Derived From**: ChatMessage (when `is_command=True`)

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `command_name` | `str` | Yes | Command without prefix | One of: help, uptime, commands, ask |
| `arguments` | `List[str]` | No | Space-separated args | Max 450 chars total |
| `sender_username` | `str` | Yes | Who sent command | From ChatMessage |
| `timestamp` | `datetime` | Yes | When received | From ChatMessage |

**Commands**:
- `!help` - Show available commands
- `!uptime` - Show stream uptime
- `!commands` - List all commands
- `!ask [question]` - Ask AI a question

**Example**:
```python
{
    "command_name": "ask",
    "arguments": ["what", "is", "recursion?"],
    "sender_username": "viewer123",
    "timestamp": "2025-10-22T15:30:45Z"
}
```

---

### 3. AIQuestionRequest

**Description**: Queued request for AI-powered answer

**Persistence**: In-memory queue (`asyncio.Queue`)

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `request_id` | `UUID` | Yes | Unique identifier | Generated on creation |
| `question_text` | `str` | Yes | User's question | Max 500 chars |
| `sender_username` | `str` | Yes | Who asked | From BotCommand |
| `timestamp_submitted` | `datetime` | Yes | When submitted | UTC timestamp |
| `queue_position` | `int` | Yes | Position in queue | 1-based indexing |
| `processing_status` | `Enum` | Yes | Current state | pending/processing/completed/failed |
| `response_text` | `str` | No | AI answer | Max 450 chars, set when completed |
| `error_message` | `str` | No | Error if failed | Set on API errors |
| `timestamp_completed` | `datetime` | No | When completed | Set on completion |
| `processing_time_ms` | `float` | No | Time to process | Calculated metric |

**Status Enum**:
```python
class RequestStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
```

**State Transitions**:
```
pending → processing → completed
                    → failed
```

**Example**:
```python
{
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "question_text": "what is recursion?",
    "sender_username": "viewer123",
    "timestamp_submitted": "2025-10-22T15:30:45Z",
    "queue_position": 5,
    "processing_status": "processing",
    "response_text": None,
    "error_message": None,
    "timestamp_completed": None,
    "processing_time_ms": None
}
```

---

### 4. RateLimitEntry

**Description**: Rate limiting state per user

**Persistence**: In-memory dictionary

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `username` | `str` | Yes | Twitch username | Primary key |
| `last_command_timestamp` | `float` | Yes | Unix time (monotonic) | time.monotonic() |
| `remaining_cooldown_seconds` | `float` | Yes | Time until next allowed | Calculated |
| `commands_sent_hour` | `int` | Yes | Count in last hour | Max 10 |
| `hourly_window_timestamps` | `deque[float]` | Yes | Last 10 command times | collections.deque(maxlen=10) |
| `per_minute_window` | `deque[float]` | Yes | Last command time | collections.deque(maxlen=1) |

**Validation Rules**:
- `commands_sent_hour <= 10` (FR-023)
- `remaining_cooldown_seconds >= 0`
- Window timestamps auto-expire after 1 hour

**Memory Optimization**:
```python
@dataclass
class RateLimitEntry:
    __slots__ = ['username', 'last_command_timestamp', 'commands_sent_hour',
                 'hourly_window_timestamps', 'per_minute_window']
```

**Example**:
```python
{
    "username": "viewer123",
    "last_command_timestamp": 1234567890.123,
    "remaining_cooldown_seconds": 45.2,
    "commands_sent_hour": 3,
    "hourly_window_timestamps": deque([1234567850.0, 1234567870.0, 1234567890.0]),
    "per_minute_window": deque([1234567890.0])
}
```

---

### 5. ModerationEvent

**Description**: Moderation action taken by bot

**Persistence**: SQLite (logged for audit trail)

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `event_id` | `UUID` | Yes | Unique identifier | Auto-generated |
| `event_type` | `Enum` | Yes | Type of action | timeout/spam_detected/rate_limit_violation/command_cooldown |
| `username` | `str` | Yes | User affected | Twitch username |
| `timestamp` | `datetime` | Yes | When occurred (UTC) | ISO 8601 |
| `duration_seconds` | `int` | No | For timeouts | 300 (5 min) for spam |
| `reason` | `str` | Yes | Why action taken | Max 200 chars |
| `metadata` | `JSON` | No | Additional context | Command attempted, message hash, etc. |

**Event Types**:
```python
class ModerationEventType(str, Enum):
    TIMEOUT = "timeout"
    SPAM_DETECTED = "spam_detected"
    RATE_LIMIT_VIOLATION = "rate_limit_violation"
    COMMAND_COOLDOWN = "command_cooldown"
```

**Example**:
```python
{
    "event_id": "660e8400-e29b-41d4-a716-446655440001",
    "event_type": "spam_detected",
    "username": "spammer456",
    "timestamp": "2025-10-22T15:35:20Z",
    "duration_seconds": 300,
    "reason": "Sent identical message 3 times in 60 seconds",
    "metadata": {
        "message_hash": "abc123def456",
        "identical_count": 3,
        "window_seconds": 60
    }
}
```

---

### 6. StreamStatus

**Description**: Current stream state from OBS orchestrator

**Source**: OBS orchestrator Health API (`GET /health`)

**Caching**: 10 seconds (FR-029)

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `streaming` | `bool` | Yes | Is stream active | True/False |
| `uptime_duration_seconds` | `int` | No | Stream duration | Only when streaming=True |
| `timestamp_last_updated` | `datetime` | Yes | Cache timestamp | UTC |
| `health_api_available` | `bool` | Yes | API reachable | Connectivity check |

**Example**:
```python
{
    "streaming": True,
    "uptime_duration_seconds": 9234,
    "timestamp_last_updated": "2025-10-22T15:30:40Z",
    "health_api_available": True
}
```

---

## Database Schema

### SQLite Tables

#### `moderation_events`

```sql
CREATE TABLE moderation_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    username TEXT NOT NULL,
    timestamp TEXT NOT NULL,  -- ISO 8601 UTC
    duration_seconds INTEGER,
    reason TEXT NOT NULL,
    metadata TEXT,  -- JSON
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_moderation_username ON moderation_events(username);
CREATE INDEX idx_moderation_timestamp ON moderation_events(timestamp);
CREATE INDEX idx_moderation_type ON moderation_events(event_type);
```

#### `chat_questions_log` (Optional - for analytics)

```sql
CREATE TABLE chat_questions_log (
    request_id TEXT PRIMARY KEY,
    question_text TEXT NOT NULL,
    sender_username TEXT NOT NULL,
    timestamp_submitted TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    response_text TEXT,
    error_message TEXT,
    processing_time_ms REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_questions_username ON chat_questions_log(sender_username);
CREATE INDEX idx_questions_timestamp ON chat_questions_log(timestamp_submitted);
CREATE INDEX idx_questions_status ON chat_questions_log(processing_status);
```

---

## Validation Rules

### Message Validation (FR-008, FR-010)

1. **Twitch chat message limit**: 500 characters
2. **Bot response limit**: 450 characters (50 char buffer for bot name/prefix)
3. **Question text**: Max 500 chars (FR-008 compliance)

### Rate Limiting (FR-015, FR-016, FR-023)

1. **Per-user command rate**: 1 command per 60 seconds
2. **Per-user hourly limit**: 10 commands per hour (hard limit)
3. **Global queue**: Max 100 concurrent AIQuestionRequest (FR-016)
4. **Command cooldown**: 30 seconds between identical commands (FR-021)

### Spam Detection (FR-022)

1. **Duplicate detection**: 3+ identical messages in 60 seconds = timeout
2. **Timeout duration**: 5 minutes (300 seconds)
3. **Automatic removal**: Timeout expires automatically

---

## Data Flow

### Command Processing Flow

```
1. ChatMessage received from Twitch IRC
   ↓
2. Parse into BotCommand
   ↓
3. Check RateLimitEntry (per-user + global)
   ↓
4a. Rate limit violated → Log ModerationEvent → Respond with cooldown message
   ↓
4b. Rate limit OK → Process command
   ↓
5a. Simple command (!help, !uptime) → Immediate response
   ↓
5b. AI command (!ask) → Create AIQuestionRequest → Add to queue
   ↓
6. Worker picks AIQuestionRequest from queue
   ↓
7. Call Claude API → Update request status
   ↓
8. Send response to Twitch chat
   ↓
9. Log to chat_questions_log (optional analytics)
```

### Spam Detection Flow

```
1. ChatMessage received
   ↓
2. Calculate message hash
   ↓
3. Check recent message hashes (last 3 in 60s window)
   ↓
4a. <3 identical → Allow processing
   ↓
4b. ≥3 identical → Spam detected
   ↓
5. Create ModerationEvent (type=spam_detected)
   ↓
6. Add user to ignore list (5 min timeout)
   ↓
7. Ignore subsequent messages from user until timeout expires
```

---

## Memory Footprint Estimates

**Per-user state** (RateLimitEntry with `__slots__`):
- ~80 bytes per user

**Global state** (100 active users):
- Rate limiting: ~8KB
- Ignore list (100 timeouts): ~10KB
- Message spam detection: ~20KB
- **Total**: ~38KB (negligible)

**In-memory queue** (100 AIQuestionRequests):
- ~500 bytes per request
- **Total**: ~50KB

**Overall memory**: <100KB for core bot state
