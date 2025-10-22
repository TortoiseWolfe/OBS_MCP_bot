"""Events repository for CRUD operations on DowntimeEvent entities.

Implements data persistence layer per data-model.md.
"""

import sqlite3
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.models.downtime_event import DowntimeEvent, FailureCause


class EventsRepository:
    """Repository for downtime event persistence."""

    def __init__(self, db_path: str):
        """Initialize events repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, event: DowntimeEvent) -> DowntimeEvent:
        """Create new downtime event record.

        Args:
            event: DowntimeEvent instance to persist

        Returns:
            Created DowntimeEvent instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO downtime_events (
                    event_id, stream_session_id, start_time, end_time, duration_sec,
                    failure_cause, recovery_action, automatic_recovery
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.event_id),
                    str(event.stream_session_id),
                    event.start_time.isoformat(),
                    event.end_time.isoformat() if event.end_time else None,
                    event.duration_sec,
                    event.failure_cause.value,
                    event.recovery_action,
                    1 if event.automatic_recovery else 0,
                ),
            )
            conn.commit()
            return event
        finally:
            conn.close()

    def get_by_id(self, event_id: UUID) -> Optional[DowntimeEvent]:
        """Retrieve downtime event by ID.

        Args:
            event_id: Event identifier

        Returns:
            DowntimeEvent instance if found, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM downtime_events WHERE event_id = ?",
                (str(event_id),)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_event(row)
            return None
        finally:
            conn.close()

    def get_by_session(self, stream_session_id: UUID) -> List[DowntimeEvent]:
        """Get all downtime events for a stream session.

        Args:
            stream_session_id: Stream session identifier

        Returns:
            List of DowntimeEvent instances ordered by start_time
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM downtime_events
                WHERE stream_session_id = ?
                ORDER BY start_time ASC
                """,
                (str(stream_session_id),)
            )
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
        finally:
            conn.close()

    def get_ongoing_events(self, stream_session_id: UUID) -> List[DowntimeEvent]:
        """Get ongoing downtime events (end_time is NULL).

        Args:
            stream_session_id: Stream session identifier

        Returns:
            List of ongoing DowntimeEvent instances
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM downtime_events
                WHERE stream_session_id = ? AND end_time IS NULL
                ORDER BY start_time DESC
                """,
                (str(stream_session_id),)
            )
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
        finally:
            conn.close()

    def update(self, event: DowntimeEvent) -> DowntimeEvent:
        """Update existing downtime event (typically to set end_time).

        Args:
            event: DowntimeEvent instance with updated data

        Returns:
            Updated DowntimeEvent instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE downtime_events
                SET end_time = ?, duration_sec = ?, recovery_action = ?
                WHERE event_id = ?
                """,
                (
                    event.end_time.isoformat() if event.end_time else None,
                    event.duration_sec,
                    event.recovery_action,
                    str(event.event_id),
                ),
            )
            conn.commit()
            return event
        finally:
            conn.close()

    def get_by_cause(
        self,
        stream_session_id: UUID,
        failure_cause: FailureCause
    ) -> List[DowntimeEvent]:
        """Get downtime events filtered by failure cause.

        Args:
            stream_session_id: Stream session identifier
            failure_cause: Type of failure to filter by

        Returns:
            List of DowntimeEvent instances matching the cause
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM downtime_events
                WHERE stream_session_id = ? AND failure_cause = ?
                ORDER BY start_time DESC
                """,
                (str(stream_session_id), failure_cause.value)
            )
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
        finally:
            conn.close()

    def _row_to_event(self, row: sqlite3.Row) -> DowntimeEvent:
        """Convert database row to DowntimeEvent instance.

        Args:
            row: SQLite row from downtime_events table

        Returns:
            DowntimeEvent instance
        """
        return DowntimeEvent(
            event_id=UUID(row["event_id"]),
            stream_session_id=UUID(row["stream_session_id"]),
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            duration_sec=row["duration_sec"],
            failure_cause=FailureCause(row["failure_cause"]),
            recovery_action=row["recovery_action"],
            automatic_recovery=bool(row["automatic_recovery"]),
        )
