"""Metrics repository for CRUD operations on HealthMetric entities.

Implements data persistence layer per data-model.md.
"""

import sqlite3
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.models.health_metric import ConnectionStatus, HealthMetric, StreamingStatus


class MetricsRepository:
    """Repository for health metrics persistence."""

    def __init__(self, db_path: str):
        """Initialize metrics repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, metric: HealthMetric) -> HealthMetric:
        """Create new health metric record.

        Args:
            metric: HealthMetric instance to persist

        Returns:
            Created HealthMetric instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO health_metrics (
                    metric_id, stream_session_id, timestamp, bitrate_kbps,
                    dropped_frames_pct, cpu_usage_pct, active_scene, active_source,
                    connection_status, streaming_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(metric.metric_id),
                    str(metric.stream_session_id),
                    metric.timestamp.isoformat(),
                    metric.bitrate_kbps,
                    metric.dropped_frames_pct,
                    metric.cpu_usage_pct,
                    metric.active_scene,
                    metric.active_source,
                    metric.connection_status.value,
                    metric.streaming_status.value,
                ),
            )
            conn.commit()
            return metric
        finally:
            conn.close()

    def get_by_id(self, metric_id: UUID) -> Optional[HealthMetric]:
        """Retrieve health metric by ID.

        Args:
            metric_id: Unique metric identifier

        Returns:
            HealthMetric instance if found, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM health_metrics WHERE metric_id = ?",
                (str(metric_id),)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_metric(row)
            return None
        finally:
            conn.close()

    def get_by_session(
        self,
        stream_session_id: UUID,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[HealthMetric]:
        """Retrieve all metrics for a stream session.

        Args:
            stream_session_id: Stream session identifier
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of HealthMetric instances ordered by timestamp DESC
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = """
                SELECT * FROM health_metrics
                WHERE stream_session_id = ?
                ORDER BY timestamp DESC
            """
            params: list[str | int] = [str(stream_session_id)]

            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
            if offset is not None:
                query += " OFFSET ?"
                params.append(offset)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_metric(row) for row in rows]
        finally:
            conn.close()

    def get_latest(self, stream_session_id: UUID) -> Optional[HealthMetric]:
        """Get most recent metric for a session.

        Args:
            stream_session_id: Stream session identifier

        Returns:
            Latest HealthMetric instance if exists, None otherwise
        """
        metrics = self.get_by_session(stream_session_id, limit=1)
        return metrics[0] if metrics else None

    def delete_older_than(self, days: int) -> int:
        """Delete metrics older than specified days (storage optimization).

        Args:
            days: Delete metrics older than this many days

        Returns:
            Number of metrics deleted
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM health_metrics
                WHERE timestamp < datetime('now', ? || ' days')
                """,
                (f"-{days}",)
            )
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
        finally:
            conn.close()

    def _row_to_metric(self, row: sqlite3.Row) -> HealthMetric:
        """Convert database row to HealthMetric instance.

        Args:
            row: SQLite row from health_metrics table

        Returns:
            HealthMetric instance
        """
        return HealthMetric(
            metric_id=UUID(row["metric_id"]),
            stream_session_id=UUID(row["stream_session_id"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            bitrate_kbps=row["bitrate_kbps"],
            dropped_frames_pct=row["dropped_frames_pct"],
            cpu_usage_pct=row["cpu_usage_pct"],
            active_scene=row["active_scene"],
            active_source=row["active_source"],
            connection_status=ConnectionStatus(row["connection_status"]),
            streaming_status=StreamingStatus(row["streaming_status"]),
        )
