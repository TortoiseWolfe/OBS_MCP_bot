"""Unit tests for Tier 3 content library repositories.

Tests CRUD operations for:
- LicenseInfoRepository
- ContentSourceRepository
- ContentLibraryRepository
- DownloadJobRepository
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from src.models.content_library import (
    AgeRating,
    ContentLibrary,
    ContentSource,
    DownloadJob,
    DownloadStatus,
    LicenseInfo,
    SourceAttribution,
)
from src.persistence.repositories.content_library import (
    ContentLibraryRepository,
    ContentSourceRepository,
    DownloadJobRepository,
    LicenseInfoRepository,
)


@pytest.fixture
def test_db(tmp_path: Path):
    """Create temporary test database with Tier 3 schema."""
    db_path = tmp_path / "test_content.db"
    conn = sqlite3.connect(db_path)

    # Execute Tier 3 schema (from db.py SCHEMA_SQL)
    conn.executescript("""
        PRAGMA foreign_keys = ON;

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
            time_blocks TEXT NOT NULL,
            priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 10),
            tags TEXT NOT NULL,
            last_verified TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (license_type) REFERENCES license_info(license_type)
        );

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
    """)
    conn.commit()
    conn.close()

    return str(db_path)


class TestLicenseInfoRepository:
    """Tests for LicenseInfoRepository."""

    def test_create_and_get_by_id(self, test_db):
        """Test creating and retrieving license by ID."""
        repo = LicenseInfoRepository(test_db)

        license_info = LicenseInfo(
            license_type="CC BY-NC-SA 4.0",
            source_name="MIT OpenCourseWare",
            attribution_text="{source} {course}: {title} - CC BY-NC-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-nc-sa/4.0/",
            permits_commercial_use=False,
            permits_modification=True,
            requires_attribution=True,
            requires_share_alike=True,
            verified_date=datetime(2025, 10, 22),
        )

        created = repo.create(license_info)
        retrieved = repo.get_by_id(created.license_id)

        assert retrieved is not None
        assert retrieved.license_type == "CC BY-NC-SA 4.0"
        assert retrieved.source_name == "MIT OpenCourseWare"
        assert retrieved.permits_commercial_use is False

    def test_get_by_type(self, test_db):
        """Test retrieving license by type."""
        repo = LicenseInfoRepository(test_db)

        license_info = LicenseInfo(
            license_type="CC BY 3.0",
            source_name="Blender Foundation",
            attribution_text="Test",
            license_url="https://creativecommons.org/licenses/by/3.0/",
            permits_commercial_use=True,
            permits_modification=True,
            requires_attribution=True,
            requires_share_alike=False,
            verified_date=datetime.utcnow(),
        )

        repo.create(license_info)
        retrieved = repo.get_by_type("CC BY 3.0")

        assert retrieved is not None
        assert retrieved.source_name == "Blender Foundation"
        assert retrieved.permits_commercial_use is True

    def test_list_all(self, test_db):
        """Test listing all licenses."""
        repo = LicenseInfoRepository(test_db)

        # Create multiple licenses
        for i, source in enumerate(["MIT", "Harvard", "Khan"]):
            license_info = LicenseInfo(
                license_type=f"CC BY-NC-SA {i}",
                source_name=source,
                attribution_text="Test",
                license_url="https://creativecommons.org/licenses/by-nc-sa/4.0/",
                permits_commercial_use=False,
                permits_modification=True,
                requires_attribution=True,
                requires_share_alike=True,
                verified_date=datetime.utcnow(),
            )
            repo.create(license_info)

        all_licenses = repo.list_all()
        assert len(all_licenses) == 3
        assert all([lic.source_name in ["MIT", "Harvard", "Khan"] for lic in all_licenses])


class TestContentSourceRepository:
    """Tests for ContentSourceRepository."""

    @pytest.fixture(autouse=True)
    def seed_license(self, test_db):
        """Seed a license for FK constraint."""
        repo = LicenseInfoRepository(test_db)
        license_info = LicenseInfo(
            license_type="CC BY-NC-SA 4.0",
            source_name="MIT OpenCourseWare",
            attribution_text="Test",
            license_url="https://creativecommons.org/licenses/by-nc-sa/4.0/",
            permits_commercial_use=False,
            permits_modification=True,
            requires_attribution=True,
            requires_share_alike=True,
            verified_date=datetime.utcnow(),
        )
        repo.create(license_info)

    def test_create_and_get_by_id(self, test_db):
        """Test creating and retrieving content source."""
        repo = ContentSourceRepository(test_db)

        content = ContentSource(
            title="Lecture 1",
            file_path="/home/turtle_wolfe/repos/OBS_bot/content/mit_ocw/lec01.mp4",
            windows_obs_path="\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\mit_ocw\\lec01.mp4",
            duration_sec=3000,
            file_size_mb=400.0,
            source_attribution=SourceAttribution.MIT_OCW,
            license_type="CC BY-NC-SA 4.0",
            course_name="6.0001",
            source_url="https://ocw.mit.edu",
            attribution_text="MIT OCW 6.0001",
            age_rating=AgeRating.ALL,
            time_blocks=["all"],
            priority=5,
            tags=["python"],
            last_verified=datetime.utcnow(),
        )

        created = repo.create(content)
        retrieved = repo.get_by_id(created.source_id)

        assert retrieved is not None
        assert retrieved.title == "Lecture 1"
        assert retrieved.duration_sec == 3000
        assert retrieved.source_attribution == SourceAttribution.MIT_OCW

    def test_get_by_file_path(self, test_db):
        """Test retrieving content by file path."""
        repo = ContentSourceRepository(test_db)

        file_path = "/home/turtle_wolfe/repos/OBS_bot/content/test/video.mp4"
        content = ContentSource(
            title="Test Video",
            file_path=file_path,
            windows_obs_path="\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\test\\video.mp4",
            duration_sec=100,
            file_size_mb=50.0,
            source_attribution=SourceAttribution.MIT_OCW,
            license_type="CC BY-NC-SA 4.0",
            course_name="Test",
            source_url="https://example.com",
            attribution_text="Test",
            age_rating=AgeRating.ALL,
            time_blocks=["all"],
            priority=5,
            tags=["test"],
            last_verified=datetime.utcnow(),
        )

        repo.create(content)
        retrieved = repo.get_by_file_path(file_path)

        assert retrieved is not None
        assert retrieved.title == "Test Video"

    def test_list_by_attribution(self, test_db):
        """Test filtering content by source attribution."""
        repo = ContentSourceRepository(test_db)

        # Create MIT OCW content
        for i in range(3):
            content = ContentSource(
                title=f"MIT Lecture {i}",
                file_path=f"/home/turtle_wolfe/repos/OBS_bot/content/mit_{i}.mp4",
                windows_obs_path=f"\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\mit_{i}.mp4",
                duration_sec=1000,
                file_size_mb=100.0,
                source_attribution=SourceAttribution.MIT_OCW,
                license_type="CC BY-NC-SA 4.0",
                course_name="Test",
                source_url="https://example.com",
                attribution_text="Test",
                age_rating=AgeRating.ALL,
                time_blocks=["all"],
                priority=5,
                tags=["test"],
                last_verified=datetime.utcnow(),
            )
            repo.create(content)

        mit_content = repo.list_by_attribution(SourceAttribution.MIT_OCW)
        assert len(mit_content) == 3
        assert all([c.source_attribution == SourceAttribution.MIT_OCW for c in mit_content])

    def test_list_by_age_rating(self, test_db):
        """Test filtering content by age rating."""
        repo = ContentSourceRepository(test_db)

        # Create kids content
        content = ContentSource(
            title="Kids Video",
            file_path="/home/turtle_wolfe/repos/OBS_bot/content/kids.mp4",
            windows_obs_path="\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\kids.mp4",
            duration_sec=1000,
            file_size_mb=100.0,
            source_attribution=SourceAttribution.MIT_OCW,
            license_type="CC BY-NC-SA 4.0",
            course_name="Test",
            source_url="https://example.com",
            attribution_text="Test",
            age_rating=AgeRating.KIDS,
            time_blocks=["all"],
            priority=5,
            tags=["test"],
            last_verified=datetime.utcnow(),
        )
        repo.create(content)

        kids_content = repo.list_by_age_rating(AgeRating.KIDS)
        assert len(kids_content) == 1
        assert kids_content[0].age_rating == AgeRating.KIDS

    def test_list_by_priority(self, test_db):
        """Test filtering content by priority range."""
        repo = ContentSourceRepository(test_db)

        # Create content with different priorities
        for priority in [1, 5, 10]:
            content = ContentSource(
                title=f"Priority {priority}",
                file_path=f"/home/turtle_wolfe/repos/OBS_bot/content/p{priority}.mp4",
                windows_obs_path=f"\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\p{priority}.mp4",
                duration_sec=1000,
                file_size_mb=100.0,
                source_attribution=SourceAttribution.MIT_OCW,
                license_type="CC BY-NC-SA 4.0",
                course_name="Test",
                source_url="https://example.com",
                attribution_text="Test",
                age_rating=AgeRating.ALL,
                time_blocks=["all"],
                priority=priority,
                tags=["test"],
                last_verified=datetime.utcnow(),
            )
            repo.create(content)

        high_priority = repo.list_by_priority(min_priority=1, max_priority=5)
        assert len(high_priority) == 2
        assert all([c.priority <= 5 for c in high_priority])

    def test_update_last_verified(self, test_db):
        """Test updating last verified timestamp."""
        repo = ContentSourceRepository(test_db)

        content = ContentSource(
            title="Test",
            file_path="/home/turtle_wolfe/repos/OBS_bot/content/test.mp4",
            windows_obs_path="\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\test.mp4",
            duration_sec=1000,
            file_size_mb=100.0,
            source_attribution=SourceAttribution.MIT_OCW,
            license_type="CC BY-NC-SA 4.0",
            course_name="Test",
            source_url="https://example.com",
            attribution_text="Test",
            age_rating=AgeRating.ALL,
            time_blocks=["all"],
            priority=5,
            tags=["test"],
            last_verified=datetime(2025, 1, 1),
        )
        created = repo.create(content)

        new_time = datetime(2025, 10, 22)
        success = repo.update_last_verified(created.source_id, new_time)
        assert success is True

        updated = repo.get_by_id(created.source_id)
        assert updated.last_verified == new_time

    def test_delete(self, test_db):
        """Test deleting content source."""
        repo = ContentSourceRepository(test_db)

        content = ContentSource(
            title="To Delete",
            file_path="/home/turtle_wolfe/repos/OBS_bot/content/delete.mp4",
            windows_obs_path="\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\delete.mp4",
            duration_sec=1000,
            file_size_mb=100.0,
            source_attribution=SourceAttribution.MIT_OCW,
            license_type="CC BY-NC-SA 4.0",
            course_name="Test",
            source_url="https://example.com",
            attribution_text="Test",
            age_rating=AgeRating.ALL,
            time_blocks=["all"],
            priority=5,
            tags=["test"],
            last_verified=datetime.utcnow(),
        )
        created = repo.create(content)

        success = repo.delete(created.source_id)
        assert success is True

        retrieved = repo.get_by_id(created.source_id)
        assert retrieved is None


class TestContentLibraryRepository:
    """Tests for ContentLibraryRepository."""

    def test_get_or_create_creates_singleton(self, test_db):
        """Test that get_or_create creates singleton on first call."""
        repo = ContentLibraryRepository(test_db)

        library = repo.get_or_create()

        assert library is not None
        assert library.library_id == UUID("550e8400-e29b-41d4-a716-446655440000")
        assert library.total_videos == 0

    def test_get_or_create_returns_existing(self, test_db):
        """Test that get_or_create returns existing singleton."""
        repo = ContentLibraryRepository(test_db)

        library1 = repo.get_or_create()
        library2 = repo.get_or_create()

        assert library1.library_id == library2.library_id

    def test_update_library_stats(self, test_db):
        """Test updating library statistics."""
        repo = ContentLibraryRepository(test_db)

        library = repo.get_or_create()
        library.total_videos = 50
        library.mit_ocw_count = 30
        library.cs50_count = 20
        library.last_scanned = datetime(2025, 10, 22)

        updated = repo.update(library)

        assert updated.total_videos == 50
        assert updated.mit_ocw_count == 30
        assert updated.cs50_count == 20

        # Verify persistence
        retrieved = repo.get()
        assert retrieved.total_videos == 50


class TestDownloadJobRepository:
    """Tests for DownloadJobRepository."""

    def test_create_and_get_by_id(self, test_db):
        """Test creating and retrieving download job."""
        repo = DownloadJobRepository(test_db)

        job = DownloadJob(
            source_name=SourceAttribution.MIT_OCW,
            status=DownloadStatus.PENDING,
        )

        created = repo.create(job)
        retrieved = repo.get_by_id(created.job_id)

        assert retrieved is not None
        assert retrieved.source_name == SourceAttribution.MIT_OCW
        assert retrieved.status == DownloadStatus.PENDING

    def test_list_by_status(self, test_db):
        """Test filtering jobs by status."""
        repo = DownloadJobRepository(test_db)

        # Create jobs with different statuses
        for status in [DownloadStatus.PENDING, DownloadStatus.IN_PROGRESS, DownloadStatus.COMPLETED]:
            job = DownloadJob(
                source_name=SourceAttribution.MIT_OCW,
                status=status,
            )
            repo.create(job)

        pending_jobs = repo.list_by_status(DownloadStatus.PENDING)
        assert len(pending_jobs) == 1
        assert pending_jobs[0].status == DownloadStatus.PENDING

    def test_update_status_to_in_progress(self, test_db):
        """Test updating job status to in_progress sets started_at."""
        repo = DownloadJobRepository(test_db)

        job = DownloadJob(
            source_name=SourceAttribution.CS50,
            status=DownloadStatus.PENDING,
        )
        created = repo.create(job)

        success = repo.update_status(
            created.job_id,
            DownloadStatus.IN_PROGRESS,
            videos_downloaded=5,
            total_size_mb=500.0
        )
        assert success is True

        updated = repo.get_by_id(created.job_id)
        assert updated.status == DownloadStatus.IN_PROGRESS
        assert updated.started_at is not None
        assert updated.videos_downloaded == 5
        assert updated.total_size_mb == 500.0

    def test_update_status_to_completed(self, test_db):
        """Test updating job status to completed sets completed_at."""
        repo = DownloadJobRepository(test_db)

        job = DownloadJob(
            source_name=SourceAttribution.KHAN_ACADEMY,
            status=DownloadStatus.IN_PROGRESS,
        )
        created = repo.create(job)

        success = repo.update_status(
            created.job_id,
            DownloadStatus.COMPLETED,
            videos_downloaded=10,
            total_size_mb=1200.0
        )
        assert success is True

        updated = repo.get_by_id(created.job_id)
        assert updated.status == DownloadStatus.COMPLETED
        assert updated.completed_at is not None

    def test_update_status_to_failed_with_error(self, test_db):
        """Test updating job status to failed with error message."""
        repo = DownloadJobRepository(test_db)

        job = DownloadJob(
            source_name=SourceAttribution.MIT_OCW,
            status=DownloadStatus.IN_PROGRESS,
        )
        created = repo.create(job)

        success = repo.update_status(
            created.job_id,
            DownloadStatus.FAILED,
            error_message="Network timeout"
        )
        assert success is True

        updated = repo.get_by_id(created.job_id)
        assert updated.status == DownloadStatus.FAILED
        assert updated.error_message == "Network timeout"
        assert updated.completed_at is not None
