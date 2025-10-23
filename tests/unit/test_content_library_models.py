"""Unit tests for Tier 3 content library Pydantic models.

Tests field validation, constraints, and business logic for:
- LicenseInfo
- ContentSource
- ContentLibrary
- DownloadJob
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.models.content_library import (
    AgeRating,
    ContentLibrary,
    ContentSource,
    DownloadJob,
    DownloadStatus,
    LicenseInfo,
    SourceAttribution,
)


class TestLicenseInfo:
    """Tests for LicenseInfo model."""

    def test_valid_license_info(self):
        """Test creating valid license info."""
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

        assert license_info.license_type == "CC BY-NC-SA 4.0"
        assert license_info.source_name == "MIT OpenCourseWare"
        assert license_info.permits_commercial_use is False
        assert license_info.requires_attribution is True
        assert isinstance(license_info.license_id, UUID)

    def test_invalid_license_url(self):
        """Test that non-CC license URLs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LicenseInfo(
                license_type="CC BY 4.0",
                source_name="Test",
                attribution_text="Test",
                license_url="https://example.com/license",  # Invalid - not CC
                permits_commercial_use=True,
                permits_modification=True,
                requires_attribution=True,
                requires_share_alike=False,
                verified_date=datetime.utcnow(),
            )

        assert "license_url must be a valid Creative Commons license URL" in str(exc_info.value)

    def test_empty_license_type(self):
        """Test that empty license type is rejected."""
        with pytest.raises(ValidationError):
            LicenseInfo(
                license_type="",  # Invalid - empty
                source_name="Test",
                attribution_text="Test",
                license_url="https://creativecommons.org/licenses/by/4.0/",
                permits_commercial_use=True,
                permits_modification=True,
                requires_attribution=True,
                requires_share_alike=False,
                verified_date=datetime.utcnow(),
            )


class TestContentSource:
    """Tests for ContentSource model."""

    def test_valid_content_source(self):
        """Test creating valid content source."""
        content = ContentSource(
            title="Lecture 1: Introduction to Python",
            file_path="/home/turtle_wolfe/repos/OBS_bot/content/mit_ocw/lecture_01.mp4",
            windows_obs_path="\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\mit_ocw\\lecture_01.mp4",
            duration_sec=3125,
            file_size_mb=450.5,
            source_attribution=SourceAttribution.MIT_OCW,
            license_type="CC BY-NC-SA 4.0",
            course_name="6.0001 Introduction to Computer Science",
            source_url="https://ocw.mit.edu/courses/6-0001/",
            attribution_text="MIT OCW 6.0001: Lecture 1 - CC BY-NC-SA 4.0",
            age_rating=AgeRating.ALL,
            time_blocks=["after_school_kids", "evening_general"],
            priority=5,
            tags=["python", "beginner"],
            last_verified=datetime.utcnow(),
        )

        assert content.title == "Lecture 1: Introduction to Python"
        assert content.source_attribution == SourceAttribution.MIT_OCW
        assert content.age_rating == AgeRating.ALL
        assert content.priority == 5
        assert "python" in content.tags

    def test_invalid_file_path(self):
        """Test that file path outside content directory is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ContentSource(
                title="Test",
                file_path="/tmp/video.mp4",  # Invalid - not in content dir
                windows_obs_path="\\\\wsl.localhost\\Debian\\tmp\\video.mp4",
                duration_sec=100,
                file_size_mb=10.0,
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

        assert "file_path must be within /home/turtle_wolfe/repos/OBS_bot/content/" in str(exc_info.value)

    def test_invalid_windows_path(self):
        """Test that Windows path without UNC prefix is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ContentSource(
                title="Test",
                file_path="/home/turtle_wolfe/repos/OBS_bot/content/test.mp4",
                windows_obs_path="C:\\content\\test.mp4",  # Invalid - not UNC path
                duration_sec=100,
                file_size_mb=10.0,
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

        assert "windows_obs_path must start with \\\\wsl.localhost\\" in str(exc_info.value)

    def test_negative_duration(self):
        """Test that negative duration is rejected."""
        with pytest.raises(ValidationError):
            ContentSource(
                title="Test",
                file_path="/home/turtle_wolfe/repos/OBS_bot/content/test.mp4",
                windows_obs_path="\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\test.mp4",
                duration_sec=-100,  # Invalid - negative
                file_size_mb=10.0,
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

    def test_invalid_priority(self):
        """Test that priority outside 1-10 range is rejected."""
        with pytest.raises(ValidationError):
            ContentSource(
                title="Test",
                file_path="/home/turtle_wolfe/repos/OBS_bot/content/test.mp4",
                windows_obs_path="\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\test.mp4",
                duration_sec=100,
                file_size_mb=10.0,
                source_attribution=SourceAttribution.MIT_OCW,
                license_type="CC BY-NC-SA 4.0",
                course_name="Test",
                source_url="https://example.com",
                attribution_text="Test",
                age_rating=AgeRating.ALL,
                time_blocks=["all"],
                priority=11,  # Invalid - outside 1-10 range
                tags=["test"],
                last_verified=datetime.utcnow(),
            )

    def test_empty_time_blocks(self):
        """Test that empty time_blocks list is rejected."""
        with pytest.raises(ValidationError):
            ContentSource(
                title="Test",
                file_path="/home/turtle_wolfe/repos/OBS_bot/content/test.mp4",
                windows_obs_path="\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\test.mp4",
                duration_sec=100,
                file_size_mb=10.0,
                source_attribution=SourceAttribution.MIT_OCW,
                license_type="CC BY-NC-SA 4.0",
                course_name="Test",
                source_url="https://example.com",
                attribution_text="Test",
                age_rating=AgeRating.ALL,
                time_blocks=[],  # Invalid - empty
                priority=5,
                tags=["test"],
                last_verified=datetime.utcnow(),
            )


class TestContentLibrary:
    """Tests for ContentLibrary model."""

    def test_valid_content_library(self):
        """Test creating valid content library."""
        library = ContentLibrary(
            total_videos=42,
            total_duration_sec=151200,
            total_size_mb=18432.5,
            last_scanned=datetime.utcnow(),
            mit_ocw_count=20,
            cs50_count=15,
            khan_academy_count=5,
            blender_count=2,
        )

        assert library.total_videos == 42
        assert library.mit_ocw_count == 20
        assert library.cs50_count == 15
        assert library.library_id == UUID("550e8400-e29b-41d4-a716-446655440000")

    def test_singleton_id_is_fixed(self):
        """Test that library_id is always the singleton UUID."""
        library1 = ContentLibrary(
            total_videos=10,
            total_duration_sec=1000,
            total_size_mb=100.0,
            last_scanned=datetime.utcnow(),
        )

        library2 = ContentLibrary(
            total_videos=20,
            total_duration_sec=2000,
            total_size_mb=200.0,
            last_scanned=datetime.utcnow(),
        )

        # Both should have the same singleton ID
        assert library1.library_id == library2.library_id
        assert library1.library_id == UUID("550e8400-e29b-41d4-a716-446655440000")

    def test_negative_counts_rejected(self):
        """Test that negative counts are rejected."""
        with pytest.raises(ValidationError):
            ContentLibrary(
                total_videos=-1,  # Invalid - negative
                total_duration_sec=1000,
                total_size_mb=100.0,
                last_scanned=datetime.utcnow(),
            )


class TestDownloadJob:
    """Tests for DownloadJob model."""

    def test_valid_download_job(self):
        """Test creating valid download job."""
        job = DownloadJob(
            source_name=SourceAttribution.MIT_OCW,
            status=DownloadStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
            videos_downloaded=5,
            total_size_mb=1200.5,
        )

        assert job.source_name == SourceAttribution.MIT_OCW
        assert job.status == DownloadStatus.IN_PROGRESS
        assert job.videos_downloaded == 5
        assert isinstance(job.job_id, UUID)

    def test_pending_job_no_timestamps(self):
        """Test that pending job can be created without timestamps."""
        job = DownloadJob(
            source_name=SourceAttribution.CS50,
            status=DownloadStatus.PENDING,
        )

        assert job.status == DownloadStatus.PENDING
        assert job.started_at is None
        assert job.completed_at is None
        assert job.videos_downloaded == 0
        assert job.total_size_mb == 0.0

    def test_failed_job_with_error(self):
        """Test failed job with error message."""
        job = DownloadJob(
            source_name=SourceAttribution.KHAN_ACADEMY,
            status=DownloadStatus.FAILED,
            started_at=datetime(2025, 10, 22, 10, 0),
            completed_at=datetime(2025, 10, 22, 10, 30),
            error_message="Network timeout after 30 seconds",
        )

        assert job.status == DownloadStatus.FAILED
        assert job.error_message == "Network timeout after 30 seconds"
        assert job.completed_at is not None

    def test_negative_videos_downloaded(self):
        """Test that negative videos_downloaded is rejected."""
        with pytest.raises(ValidationError):
            DownloadJob(
                source_name=SourceAttribution.MIT_OCW,
                status=DownloadStatus.COMPLETED,
                videos_downloaded=-1,  # Invalid - negative
                total_size_mb=100.0,
            )


class TestEnums:
    """Tests for content library enums."""

    def test_source_attribution_values(self):
        """Test SourceAttribution enum values."""
        assert SourceAttribution.MIT_OCW.value == "MIT_OCW"
        assert SourceAttribution.CS50.value == "CS50"
        assert SourceAttribution.KHAN_ACADEMY.value == "KHAN_ACADEMY"
        assert SourceAttribution.BLENDER.value == "BLENDER"

    def test_age_rating_values(self):
        """Test AgeRating enum values."""
        assert AgeRating.KIDS.value == "kids"
        assert AgeRating.ADULT.value == "adult"
        assert AgeRating.ALL.value == "all"

    def test_download_status_values(self):
        """Test DownloadStatus enum values."""
        assert DownloadStatus.PENDING.value == "pending"
        assert DownloadStatus.IN_PROGRESS.value == "in_progress"
        assert DownloadStatus.COMPLETED.value == "completed"
        assert DownloadStatus.FAILED.value == "failed"
