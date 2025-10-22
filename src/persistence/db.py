"""SQLite database schema and connection management.

Implements all 9 entities from data-model.md with proper constraints, indexes,
and foreign keys. Uses aiosqlite for async database operations.
"""

import aiosqlite
import sqlite3
from pathlib import Path
from typing import AsyncContextManager

from src.config.logging import get_logger

logger = get_logger(__name__)


# Database schema SQL - all 9 tables from data-model.md
SCHEMA_SQL = """
-- 1. StreamSession: Continuous broadcast period tracking
CREATE TABLE IF NOT EXISTS stream_sessions (
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

CREATE INDEX IF NOT EXISTS idx_stream_sessions_start ON stream_sessions(start_time DESC);


-- 2. DowntimeEvent: Stream offline or degraded periods
CREATE TABLE IF NOT EXISTS downtime_events (
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

CREATE INDEX IF NOT EXISTS idx_downtime_stream ON downtime_events(stream_session_id);
CREATE INDEX IF NOT EXISTS idx_downtime_cause ON downtime_events(failure_cause);


-- 3. HealthMetric: Point-in-time stream health (FR-019, every 10 seconds)
CREATE TABLE IF NOT EXISTS health_metrics (
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

CREATE INDEX IF NOT EXISTS idx_health_session_time ON health_metrics(stream_session_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_health_timestamp ON health_metrics(timestamp DESC);


-- 4. OwnerSession: Owner live broadcast periods (FR-029-035)
CREATE TABLE IF NOT EXISTS owner_sessions (
    session_id TEXT PRIMARY KEY,
    stream_session_id TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_sec INTEGER NOT NULL DEFAULT 0,
    content_interrupted TEXT,
    resume_content TEXT,
    transition_time_sec REAL NOT NULL,  -- SC-003: Should be <= 10 seconds
    trigger_method TEXT NOT NULL CHECK (trigger_method IN ('hotkey', 'scene_change')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stream_session_id) REFERENCES stream_sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_owner_stream ON owner_sessions(stream_session_id);


-- 5. ContentSource: Media that can be displayed on stream (FR-035-042)
CREATE TABLE IF NOT EXISTS content_sources (
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

CREATE INDEX IF NOT EXISTS idx_content_priority ON content_sources(priority_level);


-- 6. ScheduleBlock: Time-based programming configuration
CREATE TABLE IF NOT EXISTS schedule_blocks (
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


-- 7. OwnerInterruptConfiguration: Owner "Go Live" configuration
CREATE TABLE IF NOT EXISTS owner_interrupt_configs (
    config_id TEXT PRIMARY KEY,
    hotkey_binding TEXT NOT NULL,
    owner_scene_name TEXT NOT NULL DEFAULT 'Owner Live',
    transition_duration_ms INTEGER NOT NULL CHECK (transition_duration_ms BETWEEN 0 AND 5000),
    audio_fade_duration_ms INTEGER NOT NULL CHECK (audio_fade_duration_ms BETWEEN 0 AND 2000),
    cooldown_period_sec REAL NOT NULL CHECK (cooldown_period_sec BETWEEN 1.0 AND 10.0),
    detection_method TEXT NOT NULL CHECK (detection_method IN ('hotkey', 'scene_change', 'both')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- 8. SceneConfiguration: Required OBS scene metadata (FR-003-004)
CREATE TABLE IF NOT EXISTS scene_configurations (
    scene_id TEXT PRIMARY KEY,
    scene_name TEXT NOT NULL UNIQUE,
    purpose TEXT NOT NULL CHECK (purpose IN ('automated', 'owner', 'failover', 'technical_difficulties', 'going_live_soon')),
    exists_in_obs INTEGER NOT NULL,  -- SQLite boolean
    last_verified_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- 9. SystemInitializationState: Pre-flight validation results (FR-009-013)
CREATE TABLE IF NOT EXISTS initialization_states (
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

CREATE INDEX IF NOT EXISTS idx_init_timestamp ON initialization_states(timestamp DESC);
"""


class Database:
    """SQLite database connection manager with schema initialization."""

    def __init__(self, db_path: Path):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Establish database connection and initialize schema.

        Creates database file and all tables if they don't exist.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )

        # Enable foreign key constraints
        await self._connection.execute("PRAGMA foreign_keys = ON")

        # Initialize schema
        await self._connection.executescript(SCHEMA_SQL)
        await self._connection.commit()

        logger.info("database_connected", path=str(self.db_path))

    async def disconnect(self) -> None:
        """Close database connection gracefully."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("database_disconnected")

    def get_connection(self) -> aiosqlite.Connection:
        """Get active database connection.

        Returns:
            Active aiosqlite connection

        Raises:
            RuntimeError: If database not connected
        """
        if not self._connection:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    async def execute(self, query: str, params: tuple | dict | None = None) -> aiosqlite.Cursor:
        """Execute a single SQL query.

        Args:
            query: SQL query string
            params: Query parameters (tuple or dict)

        Returns:
            Cursor with query results
        """
        conn = self.get_connection()
        if params:
            return await conn.execute(query, params)
        return await conn.execute(query)

    async def executemany(self, query: str, params_list: list[tuple]) -> aiosqlite.Cursor:
        """Execute query with multiple parameter sets.

        Args:
            query: SQL query string
            params_list: List of parameter tuples

        Returns:
            Cursor with query results
        """
        conn = self.get_connection()
        return await conn.executemany(query, params_list)

    async def commit(self) -> None:
        """Commit pending transactions."""
        conn = self.get_connection()
        await conn.commit()

    def fetchone(self, query: str, params: tuple | None = None) -> sqlite3.Row | None:
        """Execute query and fetch one row (synchronous).

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Single row or None if no results

        Note: Uses synchronous sqlite3 connection. Prefer async methods when possible.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchone()
        finally:
            conn.close()

    def fetchall(self, query: str, params: tuple | None = None) -> list[sqlite3.Row]:
        """Execute query and fetch all rows (synchronous).

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of rows

        Note: Uses synchronous sqlite3 connection. Prefer async methods when possible.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return list(cursor.fetchall())
        finally:
            conn.close()

    async def vacuum(self) -> None:
        """Optimize database by reclaiming space and defragmenting.

        Run periodically (e.g., weekly) to maintain performance.
        """
        conn = self.get_connection()
        await conn.execute("VACUUM")
        logger.info("database_vacuumed")


# Global database instance
_db: Database | None = None


def get_database(db_path: Path | None = None) -> Database:
    """Get or create global database instance.

    Args:
        db_path: Path to database file (required on first call)

    Returns:
        Global Database instance

    Raises:
        RuntimeError: If db_path not provided on first call
    """
    global _db
    if _db is None:
        if db_path is None:
            raise RuntimeError("db_path required for first database initialization")
        _db = Database(db_path)
    return _db


async def init_database(db_path: Path) -> Database:
    """Initialize global database and create schema.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Connected database instance
    """
    db = get_database(db_path)
    await db.connect()
    return db
