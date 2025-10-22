"""Repository for owner session persistence.

Handles CRUD operations for OwnerSession entities.
Implements data access layer for US2 - Owner Live Broadcast Takeover.
"""

import sqlite3
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import structlog

from src.models.owner_session import OwnerSession
from src.persistence.db import Database

logger = structlog.get_logger(__name__)


class OwnerSessionsRepository:
    """Repository for managing owner session persistence.

    Provides CRUD operations for owner sessions, including:
    - Creating new owner sessions
    - Updating session end times and metrics
    - Querying sessions by stream or time range
    - Calculating owner interrupt statistics
    """

    def __init__(self, db: Database):
        """Initialize repository.

        Args:
            db: Database instance for connections
        """
        self.db = db

    async def create_owner_session(self, session: OwnerSession) -> None:
        """Create a new owner session record.

        Args:
            session: OwnerSession to persist
        """
        query = """
            INSERT INTO owner_sessions (
                session_id,
                stream_session_id,
                start_time,
                end_time,
                duration_sec,
                content_interrupted,
                resume_content,
                transition_time_sec,
                trigger_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            str(session.session_id),
            str(session.stream_session_id),
            session.start_time.isoformat(),
            session.end_time.isoformat() if session.end_time else None,
            session.duration_sec,
            session.content_interrupted,
            session.resume_content,
            session.transition_time_sec,
            session.trigger_method.value,
        )

        await self.db.execute(query, params)
        logger.info(
            "owner_session_created",
            session_id=str(session.session_id),
            stream_session_id=str(session.stream_session_id),
        )

    async def update_owner_session(self, session: OwnerSession) -> None:
        """Update an existing owner session.

        Args:
            session: OwnerSession with updated fields
        """
        query = """
            UPDATE owner_sessions SET
                end_time = ?,
                duration_sec = ?,
                resume_content = ?
            WHERE session_id = ?
        """

        params = (
            session.end_time.isoformat() if session.end_time else None,
            session.duration_sec,
            session.resume_content,
            str(session.session_id),
        )

        await self.db.execute(query, params)
        logger.debug(
            "owner_session_updated",
            session_id=str(session.session_id),
        )

    def get_owner_session(self, session_id: UUID) -> Optional[OwnerSession]:
        """Retrieve an owner session by ID.

        Args:
            session_id: Session UUID to retrieve

        Returns:
            OwnerSession if found, None otherwise
        """
        query = """
            SELECT
                session_id,
                stream_session_id,
                start_time,
                end_time,
                duration_sec,
                content_interrupted,
                resume_content,
                transition_time_sec,
                trigger_method
            FROM owner_sessions
            WHERE session_id = ?
        """

        row = self.db.fetchone(query, (str(session_id),))
        if not row:
            return None

        return self._row_to_owner_session(row)

    def get_sessions_for_stream(self, stream_session_id: UUID) -> List[OwnerSession]:
        """Get all owner sessions for a specific stream session.

        Args:
            stream_session_id: Stream session UUID

        Returns:
            List of OwnerSessions for this stream
        """
        query = """
            SELECT
                session_id,
                stream_session_id,
                start_time,
                end_time,
                duration_sec,
                content_interrupted,
                resume_content,
                transition_time_sec,
                trigger_method
            FROM owner_sessions
            WHERE stream_session_id = ?
            ORDER BY start_time DESC
        """

        rows = self.db.fetchall(query, (str(stream_session_id),))
        return [self._row_to_owner_session(row) for row in rows]

    def get_ongoing_session(self) -> Optional[OwnerSession]:
        """Get the currently ongoing owner session (if any).

        Returns:
            OwnerSession if owner is currently live, None otherwise
        """
        query = """
            SELECT
                session_id,
                stream_session_id,
                start_time,
                end_time,
                duration_sec,
                content_interrupted,
                resume_content,
                transition_time_sec,
                trigger_method
            FROM owner_sessions
            WHERE end_time IS NULL
            ORDER BY start_time DESC
            LIMIT 1
        """

        row = self.db.fetchone(query)
        if not row:
            return None

        return self._row_to_owner_session(row)

    def get_transition_stats(self, days: int = 7) -> dict:
        """Get statistics about owner transition times.

        Calculates percentage meeting SC-003 (≤10 second transitions).

        Args:
            days: Number of days to analyze (default: 7)

        Returns:
            Dict with transition statistics:
            - total_transitions: Total owner sessions
            - avg_transition_sec: Average transition time
            - pct_under_10_sec: Percentage meeting ≤10 sec target
        """
        query = """
            SELECT
                COUNT(*) as total,
                AVG(transition_time_sec) as avg_transition,
                SUM(CASE WHEN transition_time_sec <= 10 THEN 1 ELSE 0 END) as under_10
            FROM owner_sessions
            WHERE start_time >= datetime('now', '-' || ? || ' days')
        """

        row = self.db.fetchone(query, (days,))
        if not row or row[0] == 0:
            return {
                "total_transitions": 0,
                "avg_transition_sec": 0.0,
                "pct_under_10_sec": 100.0,  # No transitions = 100% compliant
            }

        total = row[0]
        avg_transition = row[1] or 0.0
        under_10 = row[2] or 0
        pct_under_10 = (under_10 / total * 100) if total > 0 else 100.0

        return {
            "total_transitions": total,
            "avg_transition_sec": round(avg_transition, 2),
            "pct_under_10_sec": round(pct_under_10, 2),
        }

    def _row_to_owner_session(self, row: sqlite3.Row) -> OwnerSession:
        """Convert database row to OwnerSession model.

        Args:
            row: Database row (sqlite3.Row)

        Returns:
            OwnerSession instance
        """
        from src.models.owner_session import TriggerMethod

        return OwnerSession(
            session_id=UUID(row[0]),
            stream_session_id=UUID(row[1]),
            start_time=datetime.fromisoformat(row[2]),
            end_time=datetime.fromisoformat(row[3]) if row[3] else None,
            duration_sec=row[4],
            content_interrupted=row[5],
            resume_content=row[6],
            transition_time_sec=row[7],
            trigger_method=TriggerMethod(row[8]),
        )
