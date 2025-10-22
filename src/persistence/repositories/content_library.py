"""Content library repositories for CRUD operations (Tier 3).

Implements data persistence layer for content_sources, license_info,
content_library, and download_jobs tables.
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.models.content_library import (
    AgeRating,
    ContentLibrary,
    ContentSource,
    DownloadJob,
    DownloadStatus,
    LicenseInfo,
    SourceAttribution,
)


class LicenseInfoRepository:
    """Repository for license information persistence."""

    def __init__(self, db_path: str):
        """Initialize license info repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, license_info: LicenseInfo) -> LicenseInfo:
        """Create new license info record.

        Args:
            license_info: LicenseInfo instance to persist

        Returns:
            Created LicenseInfo instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO license_info (
                    license_id, license_type, source_name, attribution_text,
                    license_url, permits_commercial_use, permits_modification,
                    requires_attribution, requires_share_alike, verified_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(license_info.license_id),
                    license_info.license_type,
                    license_info.source_name,
                    license_info.attribution_text,
                    license_info.license_url,
                    1 if license_info.permits_commercial_use else 0,
                    1 if license_info.permits_modification else 0,
                    1 if license_info.requires_attribution else 0,
                    1 if license_info.requires_share_alike else 0,
                    license_info.verified_date.isoformat(),
                ),
            )
            conn.commit()
            return license_info
        finally:
            conn.close()

    def get_by_id(self, license_id: UUID) -> Optional[LicenseInfo]:
        """Retrieve license info by ID.

        Args:
            license_id: Unique license identifier

        Returns:
            LicenseInfo instance if found, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM license_info WHERE license_id = ?",
                (str(license_id),)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_license_info(row)
            return None
        finally:
            conn.close()

    def get_by_type(self, license_type: str) -> Optional[LicenseInfo]:
        """Retrieve license info by license type.

        Args:
            license_type: License type (e.g., 'CC BY-NC-SA 4.0')

        Returns:
            LicenseInfo instance if found, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM license_info WHERE license_type = ?",
                (license_type,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_license_info(row)
            return None
        finally:
            conn.close()

    def list_all(self) -> List[LicenseInfo]:
        """Retrieve all license info records.

        Returns:
            List of LicenseInfo instances
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM license_info ORDER BY source_name")
            rows = cursor.fetchall()
            return [self._row_to_license_info(row) for row in rows]
        finally:
            conn.close()

    def _row_to_license_info(self, row: sqlite3.Row) -> LicenseInfo:
        """Convert database row to LicenseInfo instance.

        Args:
            row: SQLite row from license_info table

        Returns:
            LicenseInfo instance
        """
        return LicenseInfo(
            license_id=UUID(row["license_id"]),
            license_type=row["license_type"],
            source_name=row["source_name"],
            attribution_text=row["attribution_text"],
            license_url=row["license_url"],
            permits_commercial_use=bool(row["permits_commercial_use"]),
            permits_modification=bool(row["permits_modification"]),
            requires_attribution=bool(row["requires_attribution"]),
            requires_share_alike=bool(row["requires_share_alike"]),
            verified_date=datetime.fromisoformat(row["verified_date"]),
        )


class ContentSourceRepository:
    """Repository for content source persistence."""

    def __init__(self, db_path: str):
        """Initialize content source repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, content_source: ContentSource) -> ContentSource:
        """Create new content source record.

        Args:
            content_source: ContentSource instance to persist

        Returns:
            Created ContentSource instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO content_sources (
                    source_id, title, file_path, windows_obs_path, duration_sec,
                    file_size_mb, width, height, source_attribution, license_type, course_name,
                    source_url, attribution_text, age_rating, time_blocks,
                    priority, tags, last_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(content_source.source_id),
                    content_source.title,
                    content_source.file_path,
                    content_source.windows_obs_path,
                    content_source.duration_sec,
                    content_source.file_size_mb,
                    content_source.width,
                    content_source.height,
                    content_source.source_attribution.value,
                    content_source.license_type,
                    content_source.course_name,
                    content_source.source_url,
                    content_source.attribution_text,
                    content_source.age_rating.value,
                    json.dumps(content_source.time_blocks),
                    content_source.priority,
                    json.dumps(content_source.tags),
                    content_source.last_verified.isoformat(),
                ),
            )
            conn.commit()
            return content_source
        finally:
            conn.close()

    def get_by_id(self, source_id: UUID) -> Optional[ContentSource]:
        """Retrieve content source by ID.

        Args:
            source_id: Unique source identifier

        Returns:
            ContentSource instance if found, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM content_sources WHERE source_id = ?",
                (str(source_id),)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_content_source(row)
            return None
        finally:
            conn.close()

    def get_by_file_path(self, file_path: str) -> Optional[ContentSource]:
        """Retrieve content source by file path.

        Args:
            file_path: File path to search for

        Returns:
            ContentSource instance if found, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM content_sources WHERE file_path = ?",
                (file_path,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_content_source(row)
            return None
        finally:
            conn.close()

    def list_by_attribution(self, source_attribution: SourceAttribution) -> List[ContentSource]:
        """Retrieve all content from a specific source.

        Args:
            source_attribution: Source to filter by

        Returns:
            List of ContentSource instances
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM content_sources
                WHERE source_attribution = ?
                ORDER BY priority ASC, title ASC
                """,
                (source_attribution.value,)
            )
            rows = cursor.fetchall()
            return [self._row_to_content_source(row) for row in rows]
        finally:
            conn.close()

    def list_by_age_rating(self, age_rating: AgeRating) -> List[ContentSource]:
        """Retrieve all content for a specific age rating.

        Args:
            age_rating: Age rating to filter by

        Returns:
            List of ContentSource instances
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM content_sources
                WHERE age_rating = ?
                ORDER BY priority ASC, title ASC
                """,
                (age_rating.value,)
            )
            rows = cursor.fetchall()
            return [self._row_to_content_source(row) for row in rows]
        finally:
            conn.close()

    def list_by_priority(self, min_priority: int = 1, max_priority: int = 10) -> List[ContentSource]:
        """Retrieve content within priority range.

        Args:
            min_priority: Minimum priority (inclusive)
            max_priority: Maximum priority (inclusive)

        Returns:
            List of ContentSource instances ordered by priority
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM content_sources
                WHERE priority BETWEEN ? AND ?
                ORDER BY priority ASC, title ASC
                """,
                (min_priority, max_priority)
            )
            rows = cursor.fetchall()
            return [self._row_to_content_source(row) for row in rows]
        finally:
            conn.close()

    def list_all(self) -> List[ContentSource]:
        """Retrieve all content sources.

        Returns:
            List of ContentSource instances ordered by priority
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM content_sources ORDER BY priority ASC, title ASC"
            )
            rows = cursor.fetchall()
            return [self._row_to_content_source(row) for row in rows]
        finally:
            conn.close()

    def update_last_verified(self, source_id: UUID, verified_at: datetime) -> bool:
        """Update last verified timestamp for a content source.

        Args:
            source_id: Source identifier
            verified_at: New verification timestamp

        Returns:
            True if updated, False if source not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE content_sources
                SET last_verified = ?, updated_at = CURRENT_TIMESTAMP
                WHERE source_id = ?
                """,
                (verified_at.isoformat(), str(source_id))
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete(self, source_id: UUID) -> bool:
        """Delete a content source.

        Args:
            source_id: Source identifier

        Returns:
            True if deleted, False if source not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM content_sources WHERE source_id = ?",
                (str(source_id),)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_content_source(self, row: sqlite3.Row) -> ContentSource:
        """Convert database row to ContentSource instance.

        Args:
            row: SQLite row from content_sources table

        Returns:
            ContentSource instance
        """
        return ContentSource(
            source_id=UUID(row["source_id"]),
            title=row["title"],
            file_path=row["file_path"],
            windows_obs_path=row["windows_obs_path"],
            duration_sec=row["duration_sec"],
            file_size_mb=row["file_size_mb"],
            width=row["width"],
            height=row["height"],
            source_attribution=SourceAttribution(row["source_attribution"]),
            license_type=row["license_type"],
            course_name=row["course_name"],
            source_url=row["source_url"],
            attribution_text=row["attribution_text"],
            age_rating=AgeRating(row["age_rating"]),
            time_blocks=json.loads(row["time_blocks"]),
            priority=row["priority"],
            tags=json.loads(row["tags"]),
            last_verified=datetime.fromisoformat(row["last_verified"]),
        )


class ContentLibraryRepository:
    """Repository for content library aggregate statistics (singleton)."""

    SINGLETON_ID = "550e8400-e29b-41d4-a716-446655440000"

    def __init__(self, db_path: str):
        """Initialize content library repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_or_create(self) -> ContentLibrary:
        """Get singleton library stats or create if doesn't exist.

        Returns:
            ContentLibrary instance
        """
        library = self.get()
        if library:
            return library

        # Create initial library record
        library = ContentLibrary(
            library_id=UUID(self.SINGLETON_ID),
            total_videos=0,
            total_duration_sec=0,
            total_size_mb=0.0,
            last_scanned=datetime.utcnow(),
            mit_ocw_count=0,
            cs50_count=0,
            khan_academy_count=0,
            blender_count=0,
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO content_library (
                    library_id, total_videos, total_duration_sec, total_size_mb,
                    last_scanned, mit_ocw_count, cs50_count, khan_academy_count,
                    blender_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(library.library_id),
                    library.total_videos,
                    library.total_duration_sec,
                    library.total_size_mb,
                    library.last_scanned.isoformat(),
                    library.mit_ocw_count,
                    library.cs50_count,
                    library.khan_academy_count,
                    library.blender_count,
                ),
            )
            conn.commit()
            return library
        finally:
            conn.close()

    def get(self) -> Optional[ContentLibrary]:
        """Get singleton library stats.

        Returns:
            ContentLibrary instance if exists, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM content_library WHERE library_id = ?",
                (self.SINGLETON_ID,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_content_library(row)
            return None
        finally:
            conn.close()

    def update(self, library: ContentLibrary) -> ContentLibrary:
        """Update library statistics.

        Args:
            library: ContentLibrary instance with updated stats

        Returns:
            Updated ContentLibrary instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE content_library SET
                    total_videos = ?,
                    total_duration_sec = ?,
                    total_size_mb = ?,
                    last_scanned = ?,
                    mit_ocw_count = ?,
                    cs50_count = ?,
                    khan_academy_count = ?,
                    blender_count = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE library_id = ?
                """,
                (
                    library.total_videos,
                    library.total_duration_sec,
                    library.total_size_mb,
                    library.last_scanned.isoformat(),
                    library.mit_ocw_count,
                    library.cs50_count,
                    library.khan_academy_count,
                    library.blender_count,
                    str(library.library_id),
                ),
            )
            conn.commit()
            return library
        finally:
            conn.close()

    def _row_to_content_library(self, row: sqlite3.Row) -> ContentLibrary:
        """Convert database row to ContentLibrary instance.

        Args:
            row: SQLite row from content_library table

        Returns:
            ContentLibrary instance
        """
        return ContentLibrary(
            library_id=UUID(row["library_id"]),
            total_videos=row["total_videos"],
            total_duration_sec=row["total_duration_sec"],
            total_size_mb=row["total_size_mb"],
            last_scanned=datetime.fromisoformat(row["last_scanned"]),
            mit_ocw_count=row["mit_ocw_count"],
            cs50_count=row["cs50_count"],
            khan_academy_count=row["khan_academy_count"],
            blender_count=row["blender_count"],
        )


class DownloadJobRepository:
    """Repository for download job tracking."""

    def __init__(self, db_path: str):
        """Initialize download job repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, job: DownloadJob) -> DownloadJob:
        """Create new download job record.

        Args:
            job: DownloadJob instance to persist

        Returns:
            Created DownloadJob instance
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO download_jobs (
                    job_id, source_name, status, started_at, completed_at,
                    videos_downloaded, total_size_mb, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(job.job_id),
                    job.source_name.value,
                    job.status.value,
                    job.started_at.isoformat() if job.started_at else None,
                    job.completed_at.isoformat() if job.completed_at else None,
                    job.videos_downloaded,
                    job.total_size_mb,
                    job.error_message,
                ),
            )
            conn.commit()
            return job
        finally:
            conn.close()

    def get_by_id(self, job_id: UUID) -> Optional[DownloadJob]:
        """Retrieve download job by ID.

        Args:
            job_id: Unique job identifier

        Returns:
            DownloadJob instance if found, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM download_jobs WHERE job_id = ?",
                (str(job_id),)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_download_job(row)
            return None
        finally:
            conn.close()

    def list_by_status(self, status: DownloadStatus) -> List[DownloadJob]:
        """Retrieve all jobs with specific status.

        Args:
            status: Status to filter by

        Returns:
            List of DownloadJob instances
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM download_jobs
                WHERE status = ?
                ORDER BY created_at DESC
                """,
                (status.value,)
            )
            rows = cursor.fetchall()
            return [self._row_to_download_job(row) for row in rows]
        finally:
            conn.close()

    def update_status(
        self,
        job_id: UUID,
        status: DownloadStatus,
        videos_downloaded: Optional[int] = None,
        total_size_mb: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update job status and optional progress fields.

        Args:
            job_id: Job identifier
            status: New status
            videos_downloaded: Updated video count (optional)
            total_size_mb: Updated total size (optional)
            error_message: Error message if failed (optional)

        Returns:
            True if updated, False if job not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Build dynamic query based on provided fields
            updates = ["status = ?"]
            params: list = [status.value]

            if videos_downloaded is not None:
                updates.append("videos_downloaded = ?")
                params.append(videos_downloaded)

            if total_size_mb is not None:
                updates.append("total_size_mb = ?")
                params.append(total_size_mb)

            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            # Set timestamps based on status
            if status == DownloadStatus.IN_PROGRESS:
                updates.append("started_at = ?")
                params.append(datetime.utcnow().isoformat())
            elif status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED):
                updates.append("completed_at = ?")
                params.append(datetime.utcnow().isoformat())

            params.append(str(job_id))

            query = f"UPDATE download_jobs SET {', '.join(updates)} WHERE job_id = ?"
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_download_job(self, row: sqlite3.Row) -> DownloadJob:
        """Convert database row to DownloadJob instance.

        Args:
            row: SQLite row from download_jobs table

        Returns:
            DownloadJob instance
        """
        return DownloadJob(
            job_id=UUID(row["job_id"]),
            source_name=SourceAttribution(row["source_name"]),
            status=DownloadStatus(row["status"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            videos_downloaded=row["videos_downloaded"],
            total_size_mb=row["total_size_mb"],
            error_message=row["error_message"],
        )
