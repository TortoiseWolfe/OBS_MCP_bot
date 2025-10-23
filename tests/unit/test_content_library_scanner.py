"""Unit tests for ContentLibraryScanner service.

Tests file validation, library scanning, and statistics updates.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.models.content_library import AgeRating, ContentLibrary, ContentSource, SourceAttribution
from src.services.content_library_scanner import ContentLibraryScanner
from src.services.content_metadata_manager import ContentMetadataManager


@pytest.fixture
def mock_repos():
    """Create mock repositories."""
    content_source_repo = Mock()
    content_library_repo = Mock()
    return content_source_repo, content_library_repo


@pytest.fixture
def metadata_manager(tmp_path):
    """Create real ContentMetadataManager."""
    return ContentMetadataManager(content_root=tmp_path)


@pytest.fixture
def scanner(mock_repos, metadata_manager):
    """Create ContentLibraryScanner with mocked dependencies."""
    content_source_repo, content_library_repo = mock_repos
    return ContentLibraryScanner(
        content_source_repo=content_source_repo,
        content_library_repo=content_library_repo,
        metadata_manager=metadata_manager,
    )


@pytest.fixture
def sample_content_source():
    """Create a sample ContentSource for testing."""
    return ContentSource(
        title="Test Video",
        file_path="/home/test/content/general/test.mp4",
        windows_obs_path="\\\\wsl.localhost\\Debian\\home\\test\\content\\general\\test.mp4",
        duration_sec=300,
        file_size_mb=100.0,
        source_attribution=SourceAttribution.MIT_OCW,
        license_type="CC BY-NC-SA 4.0",
        course_name="Test Course",
        source_url="https://example.com",
        attribution_text="MIT OCW Test: Test Video - CC BY-NC-SA 4.0",
        age_rating=AgeRating.ALL,
        time_blocks=["general"],
        priority=5,
        tags=["test"],
        last_verified=datetime.now(timezone.utc),
    )


class TestValidateFile:
    """Test file validation functionality."""

    def test_validate_existing_video_file(self, scanner, tmp_path):
        """Test validation of existing video file."""
        video = tmp_path / "test.mp4"
        video.write_text("fake video content")

        # Mock ffprobe extraction to succeed
        with patch.object(scanner.metadata_manager, "extract_metadata", return_value={"duration_sec": 300}):
            is_valid, error = scanner.validate_file(video)

        assert is_valid is True
        assert error == ""

    def test_validate_nonexistent_file(self, scanner, tmp_path):
        """Test validation fails for nonexistent file."""
        video = tmp_path / "missing.mp4"

        is_valid, error = scanner.validate_file(video)

        assert is_valid is False
        assert "does not exist" in error

    def test_validate_directory_not_file(self, scanner, tmp_path):
        """Test validation fails for directory."""
        directory = tmp_path / "not_a_file"
        directory.mkdir()

        is_valid, error = scanner.validate_file(directory)

        assert is_valid is False
        assert "not a file" in error

    def test_validate_empty_file(self, scanner, tmp_path):
        """Test validation fails for empty file."""
        video = tmp_path / "empty.mp4"
        video.touch()  # Create empty file

        is_valid, error = scanner.validate_file(video)

        assert is_valid is False
        assert "empty" in error

    def test_validate_unsupported_extension(self, scanner, tmp_path):
        """Test validation fails for unsupported file type."""
        file = tmp_path / "document.pdf"
        file.write_text("not a video")

        is_valid, error = scanner.validate_file(file)

        assert is_valid is False
        assert "Unsupported file extension" in error

    def test_validate_invalid_video_format(self, scanner, tmp_path):
        """Test validation fails for corrupt video."""
        video = tmp_path / "corrupt.mp4"
        video.write_text("not really a video")

        # Mock ffprobe extraction to fail
        from src.services.content_metadata_manager import MetadataExtractionError
        with patch.object(scanner.metadata_manager, "extract_metadata", side_effect=MetadataExtractionError("Invalid")):
            is_valid, error = scanner.validate_file(video)

        assert is_valid is False
        assert "Invalid video file" in error


class TestScanTimeBlock:
    """Test time-block directory scanning."""

    def test_scan_empty_time_block(self, scanner, tmp_path):
        """Test scanning empty time block directory."""
        time_block_dir = tmp_path / "general"
        time_block_dir.mkdir()

        result = scanner.scan_time_block(time_block_dir)

        assert result == []

    def test_scan_nonexistent_time_block(self, scanner, tmp_path):
        """Test scanning nonexistent directory."""
        nonexistent = tmp_path / "missing"

        result = scanner.scan_time_block(nonexistent)

        assert result == []

    @patch("src.services.content_library_scanner.ContentLibraryScanner.validate_file")
    @patch("src.services.content_metadata_manager.ContentMetadataManager.create_content_source")
    def test_scan_time_block_with_valid_videos(
        self, mock_create, mock_validate, scanner, tmp_path, sample_content_source
    ):
        """Test scanning time block with valid videos."""
        time_block_dir = tmp_path / "general"
        time_block_dir.mkdir()
        (time_block_dir / "video1.mp4").write_text("fake")
        (time_block_dir / "video2.mp4").write_text("fake")

        # Mock validation to succeed
        mock_validate.return_value = (True, "")
        # Mock content source creation
        mock_create.return_value = sample_content_source

        result = scanner.scan_time_block(time_block_dir)

        assert len(result) == 2
        assert all(isinstance(cs, ContentSource) for cs in result)

    @patch("src.services.content_library_scanner.ContentLibraryScanner.validate_file")
    def test_scan_time_block_with_invalid_videos(
        self, mock_validate, scanner, tmp_path
    ):
        """Test scanning time block with invalid videos."""
        time_block_dir = tmp_path / "general"
        time_block_dir.mkdir()
        (time_block_dir / "corrupt.mp4").write_text("fake")

        # Mock validation to fail
        mock_validate.return_value = (False, "Invalid video")

        result = scanner.scan_time_block(time_block_dir)

        assert result == []

    @patch("src.services.content_library_scanner.ContentLibraryScanner.validate_file")
    @patch("src.services.content_metadata_manager.ContentMetadataManager.create_content_source")
    def test_scan_time_block_handles_metadata_failure(
        self, mock_create, mock_validate, scanner, tmp_path
    ):
        """Test handling of metadata extraction failure."""
        time_block_dir = tmp_path / "general"
        time_block_dir.mkdir()
        (time_block_dir / "video.mp4").write_text("fake")

        mock_validate.return_value = (True, "")
        mock_create.return_value = None  # Metadata extraction failed

        result = scanner.scan_time_block(time_block_dir)

        assert result == []


class TestFullScan:
    """Test full library scan functionality."""

    @patch("src.services.content_library_scanner.ContentLibraryScanner.scan_time_block")
    @patch("src.services.content_library_scanner.ContentLibraryScanner._persist_content_sources")
    @patch("src.services.content_library_scanner.ContentLibraryScanner.update_library_statistics")
    def test_full_scan_all_time_blocks(
        self, mock_update_stats, mock_persist, mock_scan_block, scanner, sample_content_source
    ):
        """Test full scan processes all time block directories."""
        # Mock scan_time_block to return content
        mock_scan_block.return_value = [sample_content_source]

        result = scanner.full_scan(persist=True)

        # Should call scan_time_block for each directory (5 total)
        assert mock_scan_block.call_count == 5
        assert len(result) == 5  # 1 content source per time block
        mock_persist.assert_called_once()
        mock_update_stats.assert_called_once()

    @patch("src.services.content_library_scanner.ContentLibraryScanner.scan_time_block")
    def test_full_scan_without_persist(
        self, mock_scan_block, scanner, sample_content_source
    ):
        """Test full scan without database persistence."""
        mock_scan_block.return_value = [sample_content_source]

        result = scanner.full_scan(persist=False)

        assert len(result) == 5
        # Verify _persist_content_sources was NOT called
        scanner.content_source_repo.create.assert_not_called()

    @patch("src.services.content_library_scanner.ContentLibraryScanner.scan_time_block")
    def test_full_scan_empty_library(self, mock_scan_block, scanner):
        """Test full scan with no content."""
        mock_scan_block.return_value = []

        result = scanner.full_scan(persist=False)

        assert result == []


class TestPersistContentSources:
    """Test database persistence of content sources."""

    def test_persist_new_content_sources(self, scanner, sample_content_source):
        """Test persisting new content sources."""
        scanner.content_source_repo.get_by_file_path.return_value = None  # Not exists

        scanner._persist_content_sources([sample_content_source])

        scanner.content_source_repo.create.assert_called_once_with(sample_content_source)

    def test_persist_existing_content_sources(self, scanner, sample_content_source):
        """Test updating existing content sources."""
        existing = Mock(source_id="existing-id")
        scanner.content_source_repo.get_by_file_path.return_value = existing

        scanner._persist_content_sources([sample_content_source])

        # Should update last_verified instead of creating
        scanner.content_source_repo.update_last_verified.assert_called_once()
        scanner.content_source_repo.create.assert_not_called()

    def test_persist_handles_errors(self, scanner, sample_content_source):
        """Test error handling during persistence."""
        scanner.content_source_repo.get_by_file_path.side_effect = Exception("DB error")

        # Should not raise exception, just log error
        scanner._persist_content_sources([sample_content_source])

    def test_persist_multiple_content_sources(self, scanner, sample_content_source):
        """Test persisting multiple content sources."""
        scanner.content_source_repo.get_by_file_path.return_value = None

        content_sources = [sample_content_source, sample_content_source]
        scanner._persist_content_sources(content_sources)

        assert scanner.content_source_repo.create.call_count == 2


class TestUpdateLibraryStatistics:
    """Test library statistics calculation and update."""

    def test_update_library_statistics(self, scanner, mock_repos):
        """Test calculating and updating library statistics."""
        content_source_repo, content_library_repo = mock_repos

        # Create test content sources
        content_sources = [
            ContentSource(
                title="MIT Video",
                file_path="/test1.mp4",
                windows_obs_path="\\\\test1.mp4",
                duration_sec=600,
                file_size_mb=100.0,
                source_attribution=SourceAttribution.MIT_OCW,
                license_type="CC BY-NC-SA 4.0",
                course_name="Course",
                source_url="https://example.com",
                attribution_text="Attribution",
                age_rating=AgeRating.ALL,
                time_blocks=["general"],
                priority=5,
                tags=["test"],
                last_verified=datetime.now(timezone.utc),
            ),
            ContentSource(
                title="CS50 Video",
                file_path="/test2.mp4",
                windows_obs_path="\\\\test2.mp4",
                duration_sec=1200,
                file_size_mb=200.0,
                source_attribution=SourceAttribution.CS50,
                license_type="CC BY-NC-SA 4.0",
                course_name="Course",
                source_url="https://example.com",
                attribution_text="Attribution",
                age_rating=AgeRating.ALL,
                time_blocks=["general"],
                priority=5,
                tags=["test"],
                last_verified=datetime.now(timezone.utc),
            ),
        ]

        # Mock get_or_create to return a library
        mock_library = ContentLibrary(
            total_videos=0,
            total_duration_sec=0,
            total_size_mb=0.0,
            last_scanned=datetime.now(timezone.utc),
        )
        content_library_repo.get_or_create.return_value = mock_library
        content_library_repo.update.return_value = mock_library

        result = scanner.update_library_statistics(content_sources)

        # Verify statistics calculated correctly
        assert result.total_videos == 2
        assert result.total_duration_sec == 1800  # 600 + 1200
        assert result.total_size_mb == 300.0  # 100 + 200
        assert result.mit_ocw_count == 1
        assert result.cs50_count == 1

        # Verify database update called
        content_library_repo.update.assert_called_once()

    def test_update_library_statistics_empty_library(self, scanner, mock_repos):
        """Test updating statistics with no content."""
        content_library_repo = mock_repos[1]

        mock_library = ContentLibrary(
            total_videos=0,
            total_duration_sec=0,
            total_size_mb=0.0,
            last_scanned=datetime.now(timezone.utc),
        )
        content_library_repo.get_or_create.return_value = mock_library
        content_library_repo.update.return_value = mock_library

        result = scanner.update_library_statistics([])

        assert result.total_videos == 0
        assert result.total_duration_sec == 0
        assert result.total_size_mb == 0.0

    def test_update_library_statistics_counts_by_source(self, scanner, mock_repos):
        """Test source-specific counts are calculated correctly."""
        content_library_repo = mock_repos[1]

        content_sources = [
            ContentSource(
                title=f"Video {i}",
                file_path=f"/test{i}.mp4",
                windows_obs_path=f"\\\\test{i}.mp4",
                duration_sec=300,
                file_size_mb=100.0,
                source_attribution=SourceAttribution.KHAN_ACADEMY,
                license_type="CC BY-NC-SA",
                course_name="Course",
                source_url="https://example.com",
                attribution_text="Attribution",
                age_rating=AgeRating.KIDS,
                time_blocks=["after_school_kids"],
                priority=5,
                tags=["test"],
                last_verified=datetime.now(timezone.utc),
            )
            for i in range(3)
        ]

        mock_library = ContentLibrary(
            total_videos=0,
            total_duration_sec=0,
            total_size_mb=0.0,
            last_scanned=datetime.now(timezone.utc),
        )
        content_library_repo.get_or_create.return_value = mock_library
        content_library_repo.update.return_value = mock_library

        result = scanner.update_library_statistics(content_sources)

        assert result.khan_academy_count == 3
        assert result.mit_ocw_count == 0
        assert result.cs50_count == 0
        assert result.blender_count == 0


class TestRescanAndUpdate:
    """Test combined rescan and update operation."""

    @patch("src.services.content_library_scanner.ContentLibraryScanner.full_scan")
    def test_rescan_and_update(self, mock_full_scan, scanner, sample_content_source, mock_repos):
        """Test rescan performs full scan with persistence."""
        content_library_repo = mock_repos[1]

        mock_full_scan.return_value = [sample_content_source]

        mock_library = ContentLibrary(
            total_videos=1,
            total_duration_sec=300,
            total_size_mb=100.0,
            last_scanned=datetime.now(timezone.utc),
        )
        content_library_repo.get.return_value = mock_library

        content_sources, library = scanner.rescan_and_update()

        assert len(content_sources) == 1
        assert library.total_videos == 1
        mock_full_scan.assert_called_once_with(persist=True)

    @patch("src.services.content_library_scanner.ContentLibraryScanner.full_scan")
    def test_rescan_handles_missing_library(self, mock_full_scan, scanner, mock_repos):
        """Test rescan handles case where library stats don't exist."""
        content_library_repo = mock_repos[1]

        mock_full_scan.return_value = []
        content_library_repo.get.return_value = None  # Library doesn't exist

        content_sources, library = scanner.rescan_and_update()

        # Should return default library with 0 stats
        assert content_sources == []
        assert library.total_videos == 0
