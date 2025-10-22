"""Sessions repository for CRUD operations on StreamSession and OwnerSession entities.

Implements data persistence layer per data-model.md.
"""

import sqlite3
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.models.owner_session import OwnerSession, TriggerMethod
from src.models.stream_session import StreamSession


class SessionsRepository:
    """Repository for stream session and owner session persistence."""

    def __init__(self, db_path: str):
        """Initialize sessions repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # StreamSession methods

    def create_stream_session(self, session: StreamSession) -> StreamSession:
        """Create new stream session record.

        Args:
            session: StreamSession instance to persist

        Returns:
            Created StreamSession instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO stream_sessions (
                    session_id, start_time, end_time, total_duration_sec,
                    downtime_duration_sec, avg_bitrate_kbps, avg_dropped_frames_pct,
                    peak_cpu_usage_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(session.session_id),
                    session.start_time.isoformat(),
                    session.end_time.isoformat() if session.end_time else None,
                    session.total_duration_sec,
                    session.downtime_duration_sec,
                    session.avg_bitrate_kbps,
                    session.avg_dropped_frames_pct,
                    session.peak_cpu_usage_pct,
                ),
            )
            conn.commit()
            return session
        finally:
            conn.close()

    def get_stream_session(self, session_id: UUID) -> Optional[StreamSession]:
        """Retrieve stream session by ID.

        Args:
            session_id: Stream session identifier

        Returns:
            StreamSession instance if found, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM stream_sessions WHERE session_id = ?",
                (str(session_id),)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_stream_session(row)
            return None
        finally:
            conn.close()

    def get_current_stream_session(self) -> Optional[StreamSession]:
        """Get the current ongoing stream session (end_time is NULL).

        Returns:
            Current StreamSession instance if exists, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM stream_sessions
                WHERE end_time IS NULL
                ORDER BY start_time DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_stream_session(row)
            return None
        finally:
            conn.close()

    def update_stream_session(self, session: StreamSession) -> StreamSession:
        """Update existing stream session.

        Args:
            session: StreamSession instance with updated data

        Returns:
            Updated StreamSession instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE stream_sessions
                SET end_time = ?, total_duration_sec = ?, downtime_duration_sec = ?,
                    avg_bitrate_kbps = ?, avg_dropped_frames_pct = ?, peak_cpu_usage_pct = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (
                    session.end_time.isoformat() if session.end_time else None,
                    session.total_duration_sec,
                    session.downtime_duration_sec,
                    session.avg_bitrate_kbps,
                    session.avg_dropped_frames_pct,
                    session.peak_cpu_usage_pct,
                    str(session.session_id),
                ),
            )
            conn.commit()
            return session
        finally:
            conn.close()

    # OwnerSession methods

    def create_owner_session(self, session: OwnerSession) -> OwnerSession:
        """Create new owner session record.

        Args:
            session: OwnerSession instance to persist

        Returns:
            Created OwnerSession instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO owner_sessions (
                    session_id, stream_session_id, start_time, end_time, duration_sec,
                    content_interrupted, resume_content, transition_time_sec, trigger_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(session.session_id),
                    str(session.stream_session_id),
                    session.start_time.isoformat(),
                    session.end_time.isoformat() if session.end_time else None,
                    session.duration_sec,
                    session.content_interrupted,
                    session.resume_content,
                    session.transition_time_sec,
                    session.trigger_method.value,
                ),
            )
            conn.commit()
            return session
        finally:
            conn.close()

    def get_owner_session(self, session_id: UUID) -> Optional[OwnerSession]:
        """Retrieve owner session by ID.

        Args:
            session_id: Owner session identifier

        Returns:
            OwnerSession instance if found, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM owner_sessions WHERE session_id = ?",
                (str(session_id),)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_owner_session(row)
            return None
        finally:
            conn.close()

    def get_owner_sessions_by_stream(self, stream_session_id: UUID) -> List[OwnerSession]:
        """Get all owner sessions for a stream session.

        Args:
            stream_session_id: Stream session identifier

        Returns:
            List of OwnerSession instances ordered by start_time
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM owner_sessions
                WHERE stream_session_id = ?
                ORDER BY start_time ASC
                """,
                (str(stream_session_id),)
            )
            rows = cursor.fetchall()
            return [self._row_to_owner_session(row) for row in rows]
        finally:
            conn.close()

    def update_owner_session(self, session: OwnerSession) -> OwnerSession:
        """Update existing owner session.

        Args:
            session: OwnerSession instance with updated data

        Returns:
            Updated OwnerSession instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE owner_sessions
                SET end_time = ?, duration_sec = ?, resume_content = ?
                WHERE session_id = ?
                """,
                (
                    session.end_time.isoformat() if session.end_time else None,
                    session.duration_sec,
                    session.resume_content,
                    str(session.session_id),
                ),
            )
            conn.commit()
            return session
        finally:
            conn.close()

    # Helper methods

    def _row_to_stream_session(self, row: sqlite3.Row) -> StreamSession:
        """Convert database row to StreamSession instance.

        Args:
            row: SQLite row from stream_sessions table

        Returns:
            StreamSession instance
        """
        return StreamSession(
            session_id=UUID(row["session_id"]),
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            total_duration_sec=row["total_duration_sec"],
            downtime_duration_sec=row["downtime_duration_sec"],
            avg_bitrate_kbps=row["avg_bitrate_kbps"],
            avg_dropped_frames_pct=row["avg_dropped_frames_pct"],
            peak_cpu_usage_pct=row["peak_cpu_usage_pct"],
        )

    def _row_to_owner_session(self, row: sqlite3.Row) -> OwnerSession:
        """Convert database row to OwnerSession instance.

        Args:
            row: SQLite row from owner_sessions table

        Returns:
            OwnerSession instance
        """
        return OwnerSession(
            session_id=UUID(row["session_id"]),
            stream_session_id=UUID(row["stream_session_id"]),
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            duration_sec=row["duration_sec"],
            content_interrupted=row["content_interrupted"],
            resume_content=row["resume_content"],
            transition_time_sec=row["transition_time_sec"],
            trigger_method=TriggerMethod(row["trigger_method"]),
        )
