"""SQLite database schema and connection management.

Implements Tier 1 streaming entities (1-4, 9-11) and Tier 3 content library entities (5-8)
with proper constraints, indexes, and foreign keys. Uses aiosqlite for async database operations.
"""

import aiosqlite
import sqlite3
from pathlib import Path
from typing import AsyncContextManager

from src.config.logging import get_logger

logger = get_logger(__name__)


# Database schema SQL - Tier 1 + Tier 3 tables (11 total)
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


-- 5. LicenseInfo: Creative Commons license metadata (Tier 3)
CREATE TABLE IF NOT EXISTS license_info (
    license_id TEXT PRIMARY KEY,
    license_type TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    attribution_text TEXT NOT NULL,
    license_url TEXT NOT NULL,
    permits_commercial_use INTEGER NOT NULL CHECK(permits_commercial_use IN (0, 1)),
    permits_modification INTEGER NOT NULL CHECK(permits_modification IN (0, 1)),
    requires_attribution INTEGER NOT NULL CHECK(requires_attribution IN (0, 1)),
    requires_share_alike INTEGER NOT NULL CHECK(requires_share_alike IN (0, 1)),
    verified_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_license_info_type ON license_info(license_type);


-- 6. ContentSource: Individual video files in content library (Tier 3)
CREATE TABLE IF NOT EXISTS content_sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    windows_obs_path TEXT NOT NULL,
    duration_sec INTEGER NOT NULL CHECK(duration_sec >= 0),
    file_size_mb REAL NOT NULL CHECK(file_size_mb > 0),
    source_attribution TEXT NOT NULL CHECK(source_attribution IN ('MIT_OCW', 'CS50', 'KHAN_ACADEMY', 'BLENDER')),
    license_type TEXT NOT NULL,
    course_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    attribution_text TEXT NOT NULL,
    age_rating TEXT NOT NULL CHECK(age_rating IN ('kids', 'adult', 'all')),
    time_blocks TEXT NOT NULL,  -- JSON array
    priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 10),
    tags TEXT NOT NULL,  -- JSON array
    last_verified TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (license_type) REFERENCES license_info(license_type)
);

CREATE INDEX IF NOT EXISTS idx_content_sources_time_blocks ON content_sources(time_blocks);
CREATE INDEX IF NOT EXISTS idx_content_sources_attribution ON content_sources(source_attribution);
CREATE INDEX IF NOT EXISTS idx_content_sources_age_rating ON content_sources(age_rating);
CREATE INDEX IF NOT EXISTS idx_content_sources_priority ON content_sources(priority DESC);


-- 7. ContentLibrary: Aggregate statistics (singleton) (Tier 3)
CREATE TABLE IF NOT EXISTS content_library (
    library_id TEXT PRIMARY KEY,
    total_videos INTEGER NOT NULL DEFAULT 0,
    total_duration_sec INTEGER NOT NULL DEFAULT 0,
    total_size_mb REAL NOT NULL DEFAULT 0.0,
    last_scanned TEXT NOT NULL,
    mit_ocw_count INTEGER NOT NULL DEFAULT 0,
    cs50_count INTEGER NOT NULL DEFAULT 0,
    khan_academy_count INTEGER NOT NULL DEFAULT 0,
    blender_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_content_library_singleton ON content_library(library_id);


-- 8. DownloadJob: Content download operation tracking (Tier 3, future feature)
CREATE TABLE IF NOT EXISTS download_jobs (
    job_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL CHECK(source_name IN ('MIT_OCW', 'CS50', 'KHAN_ACADEMY')),
    status TEXT NOT NULL CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
    started_at TEXT,
    completed_at TEXT,
    videos_downloaded INTEGER NOT NULL DEFAULT 0,
    total_size_mb REAL NOT NULL DEFAULT 0.0,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_download_jobs_status ON download_jobs(status);
CREATE INDEX IF NOT EXISTS idx_download_jobs_source ON download_jobs(source_name);


-- Seed Data: License information for CC-licensed content sources (Tier 3)
INSERT OR IGNORE INTO license_info (
    license_id,
    license_type,
    source_name,
    attribution_text,
    license_url,
    permits_commercial_use,
    permits_modification,
    requires_attribution,
    requires_share_alike,
    verified_date
) VALUES
    ('550e8400-e29b-41d4-a716-446655440001', 'CC BY-NC-SA 4.0', 'MIT OpenCourseWare', '{source} {course}: {title} - CC BY-NC-SA 4.0', 'https://creativecommons.org/licenses/by-nc-sa/4.0/', 0, 1, 1, 1, '2025-10-22T00:00:00Z'),
    ('550e8400-e29b-41d4-a716-446655440002', 'CC BY-NC-SA 4.0', 'Harvard CS50', '{source} CS50: {title} - CC BY-NC-SA 4.0', 'https://creativecommons.org/licenses/by-nc-sa/4.0/', 0, 1, 1, 1, '2025-10-22T00:00:00Z'),
    ('550e8400-e29b-41d4-a716-446655440003', 'CC BY-NC-SA', 'Khan Academy', 'Khan Academy: {title} - CC BY-NC-SA', 'https://creativecommons.org/licenses/by-nc-sa/3.0/', 0, 1, 1, 1, '2025-10-22T00:00:00Z'),
    ('550e8400-e29b-41d4-a716-446655440004', 'CC BY 3.0', 'Blender Foundation', 'Big Buck Bunny © 2008 Blender Foundation - CC BY 3.0', 'https://creativecommons.org/licenses/by/3.0/', 1, 1, 1, 0, '2025-10-22T00:00:00Z');


-- 9. ScheduleBlock: Time-based programming configuration
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


-- 10. OwnerInterruptConfiguration: Owner "Go Live" configuration
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


-- 11. SceneConfiguration: Required OBS scene metadata (FR-003-004)
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
