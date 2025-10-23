"""VideoCaption repository for synchronized caption/transcript data access.

Provides CRUD operations and specialized queries for caption playback synchronization.
"""

import sqlite3
from typing import List, Optional
from uuid import uuid4

from src.config.logging import get_logger
from src.models.content_library import VideoCaption

logger = get_logger(__name__)


class VideoCaptionRepository:
    """Repository for video caption persistence and retrieval."""

    def __init__(self, db_path: str):
        """Initialize caption repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        logger.info("video_caption_repository_initialized", db_path=db_path)

    def create(self, caption: VideoCaption) -> VideoCaption:
        """Persist new caption entry.

        Args:
            caption: VideoCaption entity to create

        Returns:
            Created caption with generated ID if needed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Generate ID if not provided
            if not caption.caption_id or caption.caption_id == "":
                caption.caption_id = str(uuid4())

            cursor.execute(
                """
                INSERT INTO video_captions (
                    caption_id, content_source_id, language_code,
                    start_time_sec, end_time_sec, text, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    caption.caption_id,
                    caption.content_source_id,
                    caption.language_code,
                    caption.start_time_sec,
                    caption.end_time_sec,
                    caption.text,
                    caption.created_at.isoformat(),
                ),
            )
            conn.commit()

            logger.info(
                "caption_created",
                caption_id=caption.caption_id,
                content_source_id=caption.content_source_id,
                duration_sec=caption.end_time_sec - caption.start_time_sec,
            )
            return caption

        finally:
            conn.close()

    def create_batch(self, captions: List[VideoCaption]) -> int:
        """Persist multiple captions efficiently.

        Args:
            captions: List of VideoCaption entities

        Returns:
            Number of captions created
        """
        if not captions:
            return 0

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Generate IDs for any captions without them
            for caption in captions:
                if not caption.caption_id or caption.caption_id == "":
                    caption.caption_id = str(uuid4())

            caption_tuples = [
                (
                    c.caption_id,
                    c.content_source_id,
                    c.language_code,
                    c.start_time_sec,
                    c.end_time_sec,
                    c.text,
                    c.created_at.isoformat(),
                )
                for c in captions
            ]

            cursor.executemany(
                """
                INSERT INTO video_captions (
                    caption_id, content_source_id, language_code,
                    start_time_sec, end_time_sec, text, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                caption_tuples,
            )
            conn.commit()

            logger.info(
                "captions_batch_created",
                count=len(captions),
                content_source_id=captions[0].content_source_id if captions else None,
            )
            return len(captions)

        finally:
            conn.close()

    def get_by_content_source(
        self, content_source_id: str, language_code: str = "en"
    ) -> List[VideoCaption]:
        """Retrieve all captions for a content source.

        Args:
            content_source_id: Content source ID
            language_code: Language code (default: 'en')

        Returns:
            List of VideoCaption entities ordered by start time
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT caption_id, content_source_id, language_code,
                       start_time_sec, end_time_sec, text, created_at
                FROM video_captions
                WHERE content_source_id = ? AND language_code = ?
                ORDER BY start_time_sec ASC
                """,
                (content_source_id, language_code),
            )

            rows = cursor.fetchall()
            return [self._row_to_caption(row) for row in rows]

        finally:
            conn.close()

    def get_caption_at_time(
        self, content_source_id: str, time_sec: float, language_code: str = "en"
    ) -> Optional[VideoCaption]:
        """Get caption active at specific playback time.

        Args:
            content_source_id: Content source ID
            time_sec: Playback time in seconds
            language_code: Language code (default: 'en')

        Returns:
            VideoCaption if one exists at this time, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT caption_id, content_source_id, language_code,
                       start_time_sec, end_time_sec, text, created_at
                FROM video_captions
                WHERE content_source_id = ?
                  AND language_code = ?
                  AND start_time_sec <= ?
                  AND end_time_sec > ?
                ORDER BY start_time_sec DESC
                LIMIT 1
                """,
                (content_source_id, language_code, time_sec, time_sec),
            )

            row = cursor.fetchone()
            return self._row_to_caption(row) if row else None

        finally:
            conn.close()

    def delete_by_content_source(self, content_source_id: str) -> int:
        """Delete all captions for a content source.

        Args:
            content_source_id: Content source ID

        Returns:
            Number of captions deleted
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM video_captions WHERE content_source_id = ?",
                (content_source_id,),
            )
            deleted = cursor.rowcount
            conn.commit()

            logger.info(
                "captions_deleted",
                content_source_id=content_source_id,
                count=deleted,
            )
            return deleted

        finally:
            conn.close()

    def count_by_content_source(self, content_source_id: str) -> int:
        """Count captions for a content source.

        Args:
            content_source_id: Content source ID

        Returns:
            Number of captions
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM video_captions WHERE content_source_id = ?",
                (content_source_id,),
            )
            return cursor.fetchone()[0]

        finally:
            conn.close()

    def _row_to_caption(self, row: sqlite3.Row) -> VideoCaption:
        """Convert database row to VideoCaption entity.

        Args:
            row: SQLite row object

        Returns:
            VideoCaption entity
        """
        from datetime import datetime, timezone

        return VideoCaption(
            caption_id=row["caption_id"],
            content_source_id=row["content_source_id"],
            language_code=row["language_code"],
            start_time_sec=row["start_time_sec"],
            end_time_sec=row["end_time_sec"],
            text=row["text"],
            created_at=datetime.fromisoformat(row["created_at"]).replace(tzinfo=timezone.utc),
        )
