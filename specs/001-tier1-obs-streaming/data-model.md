# Data Model: Tier 1 OBS Streaming Foundation

**Feature**: 001-tier1-obs-streaming
**Date**: 2025-10-20
**Phase**: 1 (Design & Contracts)

## Overview

This document defines the domain entities, their relationships, validation rules, and persistence schema for the Tier 1 streaming system. All entities are derived from the Key Entities section in [spec.md](./spec.md).

## Entity Relationship Diagram

```
┌─────────────────┐       1:N        ┌──────────────────┐
│ StreamSession   │◄────────────────┤  DowntimeEvent   │
│                 │                  └──────────────────┘
│ - session_id    │
│ - start_time    │       1:N        ┌──────────────────┐
│ - end_time      │◄────────────────┤  HealthMetric    │
│ - uptime_sec    │                  └──────────────────┘
│ - downtime_sec  │
└─────────────────┘       1:N        ┌──────────────────┐
        │                            │  OwnerSession    │
        └────────────────────────────►                  │
                                     │ - session_id     │
                                     │ - stream_id (FK) │
                                     │ - start_time     │
                                     │ - end_time       │
                                     └──────────────────┘

┌─────────────────────┐
│ ContentSource       │
│                     │
│ - source_id         │
│ - source_type       │
│ - file_path         │
│ - duration_sec      │
│ - age_rating        │
│ - time_blocks[]     │
│ - priority          │
│ - last_verified     │
└─────────────────────┘

┌─────────────────────┐
│ ScheduleBlock       │
│                     │
│ - block_id          │
│ - time_range        │
│ - day_restrictions  │
│ - allowed_types[]   │
│ - age_requirement   │
│ - priority_order[]  │
└─────────────────────┘

┌──────────────────────┐
│ OwnerSourceConfig    │
│                      │
│ - config_id          │
│ - source_names[]     │
│ - detection_method   │
│ - debounce_sec       │
└──────────────────────┘

┌──────────────────────┐
│ SceneConfiguration   │
│                      │
│ - scene_id           │
│ - scene_name         │
│ - purpose            │
│ - exists_in_obs      │
│ - last_verified      │
└──────────────────────┘

┌───────────────────────┐
│ InitializationState   │
│                       │
│ - init_id             │
│ - timestamp           │
│ - validation_results  │
│ - overall_status      │
│ - stream_started_at   │
└───────────────────────┘
```

## Entities

### 1. StreamSession

**Purpose**: Represents a continuous broadcast period from stream start to stream end.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `session_id` | UUID | Yes | Unique identifier for this stream session | UUID v4 format |
| `start_time` | DateTime (UTC) | Yes | When streaming started | ISO 8601, not future |
| `end_time` | DateTime (UTC) | No | When streaming ended (null if ongoing) | Must be > start_time |
| `total_duration_sec` | Integer | Yes | Total seconds streamed (computed) | >= 0 |
| `downtime_duration_sec` | Integer | Yes | Total seconds offline during session | >= 0, <= total_duration |
| `downtime_events` | List[UUID] | Yes | Foreign keys to DowntimeEvent | Empty list allowed |
| `failover_events` | List[UUID] | Yes | Foreign keys to DowntimeEvent (type=failover) | Empty list allowed |
| `owner_interrupts` | List[UUID] | Yes | Foreign keys to OwnerSession | Empty list allowed |
| `avg_bitrate_kbps` | Float | Yes | Average bitrate across all health metrics | > 0 |
| `avg_dropped_frames_pct` | Float | Yes | Average dropped frames percentage | 0.0 - 100.0 |
| `peak_cpu_usage_pct` | Float | Yes | Peak CPU usage during session | 0.0 - 100.0 |

**State Transitions**:
- **Created**: `start_time` set, `end_time` null, streaming initiated
- **Ongoing**: Health metrics accumulated, downtime/owner events appended
- **Ended**: `end_time` set, final statistics computed

**Persistence**:
```sql
CREATE TABLE stream_sessions (
    session_id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,  -- ISO 8601 UTC
    end_time TEXT,              -- ISO 8601 UTC, NULL if ongoing
    total_duration_sec INTEGER NOT NULL DEFAULT 0,
    downtime_duration_sec INTEGER NOT NULL DEFAULT 0,
    avg_bitrate_kbps REAL NOT NULL DEFAULT 0.0,
    avg_dropped_frames_pct REAL NOT NULL DEFAULT 0.0,
    peak_cpu_usage_pct REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stream_sessions_start ON stream_sessions(start_time DESC);
```

---

### 2. DowntimeEvent

**Purpose**: Represents a period when the stream was offline or degraded.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `event_id` | UUID | Yes | Unique identifier for this downtime event | UUID v4 format |
| `stream_session_id` | UUID | Yes | Foreign key to StreamSession | Must exist |
| `start_time` | DateTime (UTC) | Yes | When downtime/degradation started | ISO 8601 |
| `end_time` | DateTime (UTC) | No | When recovered (null if ongoing) | Must be > start_time |
| `duration_sec` | Float | Yes | Duration of downtime (computed) | >= 0 |
| `failure_cause` | Enum | Yes | Type of failure | See FailureCause enum |
| `recovery_action` | String | Yes | What action was taken to recover | Non-empty, max 500 chars |
| `automatic_recovery` | Boolean | Yes | True if auto-recovered, false if manual | - |

**FailureCause Enum**:
- `connection_lost`: RTMP connection to Twitch dropped
- `obs_crash`: OBS became unresponsive
- `content_failure`: Content source failed to play
- `network_degraded`: Network bandwidth insufficient
- `manual_stop`: Owner manually stopped streaming (edge case)

**State Transitions**:
- **Detected**: `start_time` set, `end_time` null, failure logged
- **Recovering**: Recovery action initiated (switch to failover, restart OBS, etc.)
- **Resolved**: `end_time` set, duration computed

**Persistence**:
```sql
CREATE TABLE downtime_events (
    event_id TEXT PRIMARY KEY,
    stream_session_id TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_sec REAL NOT NULL DEFAULT 0.0,
    failure_cause TEXT NOT NULL CHECK (failure_cause IN (
        'connection_lost', 'obs_crash', 'content_failure',
        'network_degraded', 'manual_stop'
    )),
    recovery_action TEXT NOT NULL,
    automatic_recovery INTEGER NOT NULL,  -- SQLite boolean (0/1)
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stream_session_id) REFERENCES stream_sessions(session_id)
);

CREATE INDEX idx_downtime_stream ON downtime_events(stream_session_id);
CREATE INDEX idx_downtime_cause ON downtime_events(failure_cause);
```

---

### 3. HealthMetric

**Purpose**: Represents point-in-time stream health measurement (collected every 10 seconds per FR-019).

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `metric_id` | UUID | Yes | Unique identifier for this metric snapshot | UUID v4 format |
| `stream_session_id` | UUID | Yes | Foreign key to StreamSession | Must exist |
| `timestamp` | DateTime (UTC) | Yes | When metric was collected | ISO 8601 |
| `bitrate_kbps` | Float | Yes | Current bitrate in kilobits/sec | >= 0 |
| `dropped_frames_pct` | Float | Yes | Percentage of dropped frames | 0.0 - 100.0 |
| `cpu_usage_pct` | Float | Yes | CPU usage percentage | 0.0 - 100.0 |
| `active_scene` | String | Yes | Current OBS scene name | Non-empty, max 100 chars |
| `active_source` | String | No | Current content source (if applicable) | Max 255 chars |
| `connection_status` | Enum | Yes | RTMP connection state | `connected`, `disconnected`, `degraded` |
| `streaming_status` | Enum | Yes | OBS streaming state | `streaming`, `stopped`, `starting`, `stopping` |

**Validation Rules**:
- `dropped_frames_pct` > 1.0 triggers warning (FR-021)
- `connection_status` = `disconnected` for >30 sec triggers recovery (FR-022)
- Metrics older than 7 days are archived (storage optimization)

**Persistence**:
```sql
CREATE TABLE health_metrics (
    metric_id TEXT PRIMARY KEY,
    stream_session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    bitrate_kbps REAL NOT NULL,
    dropped_frames_pct REAL NOT NULL CHECK (dropped_frames_pct BETWEEN 0 AND 100),
    cpu_usage_pct REAL NOT NULL CHECK (cpu_usage_pct BETWEEN 0 AND 100),
    active_scene TEXT NOT NULL,
    active_source TEXT,
    connection_status TEXT NOT NULL CHECK (connection_status IN ('connected', 'disconnected', 'degraded')),
    streaming_status TEXT NOT NULL CHECK (streaming_status IN ('streaming', 'stopped', 'starting', 'stopping')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stream_session_id) REFERENCES stream_sessions(session_id)
);

CREATE INDEX idx_health_session_time ON health_metrics(stream_session_id, timestamp DESC);
CREATE INDEX idx_health_timestamp ON health_metrics(timestamp DESC);
```

---

### 4. OwnerSession

**Purpose**: Represents a period when the owner was broadcasting live.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `session_id` | UUID | Yes | Unique identifier for this owner session | UUID v4 format |
| `stream_session_id` | UUID | Yes | Foreign key to parent StreamSession | Must exist |
| `start_time` | DateTime (UTC) | Yes | When owner went live (sources activated) | ISO 8601 |
| `end_time` | DateTime (UTC) | No | When owner session ended (sources deactivated) | Must be > start_time |
| `duration_sec` | Integer | Yes | Duration of owner session (computed) | >= 0 |
| `content_interrupted` | String | No | What content was playing before owner took over | Max 255 chars |
| `resume_content` | String | No | What content resumed after owner finished | Max 255 chars |
| `transition_time_sec` | Float | Yes | How long the transition took (for SC-003 measurement) | 0.0 - 60.0 |

**Validation Rules**:
- `transition_time_sec` should be ≤10 seconds 95% of the time (SC-003)
- Owner sessions cannot overlap (enforce via application logic)

**Persistence**:
```sql
CREATE TABLE owner_sessions (
    session_id TEXT PRIMARY KEY,
    stream_session_id TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_sec INTEGER NOT NULL DEFAULT 0,
    content_interrupted TEXT,
    resume_content TEXT,
    transition_time_sec REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stream_session_id) REFERENCES stream_sessions(session_id)
);

CREATE INDEX idx_owner_stream ON owner_sessions(stream_session_id);
```

---

### 5. ContentSource

**Purpose**: Represents any media that can be displayed on stream.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `source_id` | UUID | Yes | Unique identifier for this content source | UUID v4 format |
| `source_type` | Enum | Yes | Type of content | `video_file`, `scene_composition`, `live_input` |
| `file_path` | String | Conditional | Absolute path to content file | Required if source_type=video_file |
| `duration_sec` | Integer | Conditional | Duration of content in seconds | Required if source_type=video_file, > 0 |
| `age_appropriateness` | Enum | Yes | Age rating for content | `kids`, `teen`, `adult`, `all_ages` |
| `time_blocks_allowed` | List[String] | Yes | Time block IDs when this content can play | Non-empty |
| `priority_level` | Integer | Yes | Priority (1=highest, owner live always wins) | 1-100 |
| `last_verified_at` | DateTime (UTC) | Yes | Last time content was verified playable | ISO 8601 |
| `metadata` | JSON | No | Additional metadata (title, description, etc.) | Valid JSON |

**Validation Rules**:
- `file_path` must exist and be readable (verified during FR-037)
- `last_verified_at` older than 24 hours triggers re-verification
- `priority_level` 1-10 reserved for owner live/failover (enforced by config)

**Persistence**:
```sql
CREATE TABLE content_sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL CHECK (source_type IN ('video_file', 'scene_composition', 'live_input')),
    file_path TEXT,
    duration_sec INTEGER,
    age_appropriateness TEXT NOT NULL CHECK (age_appropriateness IN ('kids', 'teen', 'adult', 'all_ages')),
    time_blocks_allowed TEXT NOT NULL,  -- JSON array of block IDs
    priority_level INTEGER NOT NULL CHECK (priority_level BETWEEN 1 AND 100),
    last_verified_at TEXT NOT NULL,
    metadata TEXT,  -- JSON
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_content_priority ON content_sources(priority_level);
```

---

### 6. ScheduleBlock

**Purpose**: Represents time-based programming configuration.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `block_id` | UUID | Yes | Unique identifier for this schedule block | UUID v4 format |
| `name` | String | Yes | Human-readable name (e.g., "After School Kids") | Non-empty, max 100 chars |
| `time_range_start` | Time (HH:MM) | Yes | Start time in local timezone | 00:00 - 23:59 |
| `time_range_end` | Time (HH:MM) | Yes | End time in local timezone | Must be != start_time |
| `day_restrictions` | List[String] | Yes | Days of week (Monday-Sunday, or "all") | Valid day names |
| `allowed_content_types` | List[Enum] | Yes | Allowed source types | Subset of ContentSource.source_type |
| `age_requirement` | Enum | Yes | Age appropriateness filter | Same as ContentSource enum |
| `priority_order` | List[String] | Yes | Content priority rules for this block | Non-empty |

**Validation Rules**:
- Time ranges can wrap midnight (e.g., 22:00-02:00)
- No overlapping time ranges for same day (enforced at creation)
- `priority_order` format: `["owner_live", "failover", "scheduled"]`

**Persistence**:
```sql
CREATE TABLE schedule_blocks (
    block_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    time_range_start TEXT NOT NULL,  -- HH:MM format
    time_range_end TEXT NOT NULL,
    day_restrictions TEXT NOT NULL,  -- JSON array
    allowed_content_types TEXT NOT NULL,  -- JSON array
    age_requirement TEXT NOT NULL,
    priority_order TEXT NOT NULL,  -- JSON array
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

### 7. OwnerSourceConfiguration

**Purpose**: Represents configuration for detecting owner's live presence.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `config_id` | UUID | Yes | Unique identifier | UUID v4 format |
| `designated_source_names` | List[String] | Yes | OBS source names to monitor | Non-empty, max 10 sources |
| `detection_method` | Enum | Yes | How to detect activation | `source_enabled`, `audio_threshold`, `video_active` |
| `debounce_time_sec` | Float | Yes | Prevent false triggers from brief activations | 1.0 - 30.0 |
| `audio_threshold_db` | Float | Conditional | dB threshold if detection_method=audio | -60.0 to 0.0 |

**Validation Rules**:
- `designated_source_names` must match actual OBS source names (validated at startup)
- `debounce_time_sec` default: 5.0 seconds (balance between responsiveness and false triggers)

**Persistence**:
```sql
CREATE TABLE owner_source_configs (
    config_id TEXT PRIMARY KEY,
    designated_source_names TEXT NOT NULL,  -- JSON array
    detection_method TEXT NOT NULL CHECK (detection_method IN ('source_enabled', 'audio_threshold', 'video_active')),
    debounce_time_sec REAL NOT NULL CHECK (debounce_time_sec BETWEEN 1.0 AND 30.0),
    audio_threshold_db REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

### 8. SceneConfiguration

**Purpose**: Represents required OBS scene metadata.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `scene_id` | UUID | Yes | Unique identifier | UUID v4 format |
| `scene_name` | String | Yes | OBS scene name | Non-empty, max 100 chars |
| `purpose` | Enum | Yes | Scene purpose | `automated`, `owner`, `failover`, `technical_difficulties` |
| `exists_in_obs` | Boolean | Yes | Whether scene exists in OBS | Updated during pre-flight validation |
| `last_verified_at` | DateTime (UTC) | Yes | Last verification timestamp | ISO 8601 |

**Required Scenes** (FR-003):
- "Automated Content" (purpose=automated)
- "Owner Live" (purpose=owner)
- "Failover" (purpose=failover)
- "Technical Difficulties" (purpose=technical_difficulties)

**Validation Rules**:
- System creates missing scenes on init (FR-003, FR-012)
- Never overwrites existing scenes (FR-004)
- Re-verification every 60 seconds during operation

**Persistence**:
```sql
CREATE TABLE scene_configurations (
    scene_id TEXT PRIMARY KEY,
    scene_name TEXT NOT NULL UNIQUE,
    purpose TEXT NOT NULL CHECK (purpose IN ('automated', 'owner', 'failover', 'technical_difficulties')),
    exists_in_obs INTEGER NOT NULL,  -- SQLite boolean
    last_verified_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

### 9. SystemInitializationState

**Purpose**: Represents the outcome of startup pre-flight validation.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `init_id` | UUID | Yes | Unique identifier for this init attempt | UUID v4 format |
| `timestamp` | DateTime (UTC) | Yes | When initialization was attempted | ISO 8601 |
| `obs_connectivity` | Boolean | Yes | OBS websocket reachable | - |
| `scenes_exist` | Boolean | Yes | All required scenes present | - |
| `failover_content_available` | Boolean | Yes | Failover content verified playable | - |
| `twitch_credentials_configured` | Boolean | Yes | Stream key configured | - |
| `network_connectivity` | Boolean | Yes | Can reach Twitch RTMP endpoint | - |
| `overall_status` | Enum | Yes | Pass if all checks true | `passed`, `failed` |
| `stream_started_at` | DateTime (UTC) | No | When streaming auto-started (if passed) | ISO 8601 |
| `failure_details` | JSON | Conditional | Specific errors if failed | Required if status=failed |

**State Transitions**:
- **Validating**: Pre-flight checks running
- **Passed**: All checks true, streaming auto-started
- **Failed**: One or more checks failed, retry after 60 sec

**Persistence**:
```sql
CREATE TABLE initialization_states (
    init_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    obs_connectivity INTEGER NOT NULL,
    scenes_exist INTEGER NOT NULL,
    failover_content_available INTEGER NOT NULL,
    twitch_credentials_configured INTEGER NOT NULL,
    network_connectivity INTEGER NOT NULL,
    overall_status TEXT NOT NULL CHECK (overall_status IN ('passed', 'failed')),
    stream_started_at TEXT,
    failure_details TEXT,  -- JSON
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_init_timestamp ON initialization_states(timestamp DESC);
```

---

## Aggregations & Queries

### Uptime Calculation (SC-001, SC-008)

```python
def calculate_uptime_percentage(session: StreamSession) -> float:
    """Calculate uptime % for SC-001 validation (99.9% target)"""
    if session.total_duration_sec == 0:
        return 0.0
    uptime_sec = session.total_duration_sec - session.downtime_duration_sec
    return (uptime_sec / session.total_duration_sec) * 100.0
```

### Transition Time Analysis (SC-003)

```python
def analyze_owner_transitions(session: StreamSession) -> dict:
    """Calculate owner transition performance (95% under 10sec)"""
    owner_sessions = OwnerSession.query.filter_by(stream_session_id=session.session_id).all()
    transition_times = [s.transition_time_sec for s in owner_sessions]

    if not transition_times:
        return {"avg": 0, "p95": 0, "success_rate": 100}

    transition_times.sort()
    p95_index = int(len(transition_times) * 0.95)
    p95_time = transition_times[p95_index]

    success_count = sum(1 for t in transition_times if t <= 10.0)
    success_rate = (success_count / len(transition_times)) * 100.0

    return {
        "avg": sum(transition_times) / len(transition_times),
        "p95": p95_time,
        "success_rate": success_rate  # Should be >= 95% per SC-003
    }
```

### Failover Performance (SC-005)

```python
def analyze_failover_performance(session: StreamSession) -> dict:
    """Verify failover meets 5-second requirement (SC-005)"""
    failover_events = DowntimeEvent.query.filter_by(
        stream_session_id=session.session_id,
        failure_cause='content_failure',
        automatic_recovery=True
    ).all()

    recovery_times = [e.duration_sec for e in failover_events]

    if not recovery_times:
        return {"avg": 0, "max": 0, "success_rate": 100}

    success_count = sum(1 for t in recovery_times if t <= 5.0)
    success_rate = (success_count / len(recovery_times)) * 100.0

    return {
        "avg": sum(recovery_times) / len(recovery_times),
        "max": max(recovery_times),
        "success_rate": success_rate  # Should be 100% per SC-005
    }
```

---

## Migrations & Schema Evolution

**Version**: 1.0.0 (initial schema)

**Migration Strategy**:
- SQLite schema created via `persistence/db.py` on first run
- Future schema changes use Alembic migrations (deferred to Tier 2)
- State persistence survives container restarts (SQLite file mounted as Docker volume)

**Backup Strategy**:
- SQLite file backed up daily via cron (outside Tier 1 scope)
- Downtime events critical for constitutional audit trail (never deleted)
- Health metrics archived after 30 days to separate table (future optimization)

---

## Next Steps

**Phase 1 Continues**:
1. Generate `contracts/health-api.yaml` OpenAPI spec
2. Generate `quickstart.md` for development setup
3. Update agent context with finalized data model
