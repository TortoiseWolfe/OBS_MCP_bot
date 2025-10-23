"""Unit tests for ContentMetadataManager service.

Tests metadata extraction, inference, and ContentSource generation.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.models.content_library import AgeRating, ContentSource, SourceAttribution
from src.services.content_metadata_manager import (
    ContentMetadataManager,
    MetadataExtractionError,
)


@pytest.fixture
def metadata_manager(tmp_path):
    """Create ContentMetadataManager with temp directory."""
    return ContentMetadataManager(content_root=tmp_path)


@pytest.fixture
def sample_video_path(tmp_path):
    """Create a sample video file path."""
    video_dir = tmp_path / "general" / "mit-ocw-6.0001"
    video_dir.mkdir(parents=True)
    video_file = video_dir / "01-Introduction.mp4"
    video_file.write_text("fake video content")
    return video_file


class TestScanDirectory:
    """Test directory scanning functionality."""

    def test_scan_empty_directory(self, metadata_manager, tmp_path):
        """Test scanning an empty directory returns empty list."""
        result = metadata_manager.scan_directory(tmp_path)
        assert result == []

    def test_scan_nonexistent_directory(self, metadata_manager, tmp_path):
        """Test scanning nonexistent directory returns empty list."""
        nonexistent = tmp_path / "does_not_exist"
        result = metadata_manager.scan_directory(nonexistent)
        assert result == []

    def test_scan_directory_with_videos(self, metadata_manager, tmp_path):
        """Test scanning directory with video files."""
        # Create test video files
        (tmp_path / "video1.mp4").write_text("fake")
        (tmp_path / "video2.mkv").write_text("fake")
        (tmp_path / "not_video.txt").write_text("fake")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "video3.mp4").write_text("fake")

        result = metadata_manager.scan_directory(tmp_path)

        # Should find 3 videos (recursive)
        assert len(result) == 3
        assert all(p.suffix.lower() in ContentMetadataManager.VIDEO_EXTENSIONS for p in result)

    def test_scan_filters_by_extension(self, metadata_manager, tmp_path):
        """Test only video extensions are returned."""
        (tmp_path / "video.mp4").write_text("fake")
        (tmp_path / "image.jpg").write_text("fake")
        (tmp_path / "document.pdf").write_text("fake")

        result = metadata_manager.scan_directory(tmp_path)

        assert len(result) == 1
        assert result[0].name == "video.mp4"


class TestExtractMetadata:
    """Test metadata extraction with ffprobe."""

    @patch("subprocess.run")
    def test_extract_metadata_success(self, mock_run, metadata_manager, sample_video_path):
        """Test successful metadata extraction."""
        # Mock ffprobe output
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({
                "format": {
                    "duration": "1234.56",
                    "size": "524288000",  # 500 MB in bytes
                    "format_name": "mp4"
                }
            })
        )

        result = metadata_manager.extract_metadata(sample_video_path)

        assert result["duration_sec"] == 1234
        assert result["file_size_mb"] == 500.0
        assert result["format"] == "mp4"

    @patch("subprocess.run")
    def test_extract_metadata_ffprobe_failure(self, mock_run, metadata_manager, sample_video_path):
        """Test handling of ffprobe failure."""
        mock_run.return_value = Mock(
            returncode=1,
            stderr="ffprobe error"
        )

        with pytest.raises(MetadataExtractionError, match="ffprobe failed"):
            metadata_manager.extract_metadata(sample_video_path)

    def test_extract_metadata_file_not_found(self, metadata_manager, tmp_path):
        """Test error when video file doesn't exist."""
        nonexistent = tmp_path / "missing.mp4"

        with pytest.raises(MetadataExtractionError, match="not found"):
            metadata_manager.extract_metadata(nonexistent)

    @patch("subprocess.run")
    def test_extract_metadata_timeout(self, mock_run, metadata_manager, sample_video_path):
        """Test handling of ffprobe timeout."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("ffprobe", 30)

        with pytest.raises(MetadataExtractionError, match="timed out"):
            metadata_manager.extract_metadata(sample_video_path)


class TestParseFilename:
    """Test filename parsing for titles and sequence numbers."""

    def test_parse_filename_with_sequence(self, metadata_manager, tmp_path):
        """Test parsing filename with sequence number prefix."""
        video = tmp_path / "01-Introduction_to_Python.mp4"

        result = metadata_manager.parse_filename(video)

        assert result["title"] == "Introduction To Python"
        assert result["sequence_number"] == "01"

    def test_parse_filename_without_sequence(self, metadata_manager, tmp_path):
        """Test parsing filename without sequence number."""
        video = tmp_path / "Introduction_to_Python.mp4"

        result = metadata_manager.parse_filename(video)

        assert result["title"] == "Introduction To Python"
        assert result["sequence_number"] is None

    def test_parse_filename_with_underscores(self, metadata_manager, tmp_path):
        """Test filename with underscores is converted to title case."""
        video = tmp_path / "what_is_computation.mp4"

        result = metadata_manager.parse_filename(video)

        assert result["title"] == "What Is Computation"

    def test_parse_filename_with_hyphens(self, metadata_manager, tmp_path):
        """Test filename with hyphens is converted properly."""
        video = tmp_path / "data-structures-and-algorithms.mp4"

        result = metadata_manager.parse_filename(video)

        assert result["title"] == "Data Structures And Algorithms"


class TestInferSourceAttribution:
    """Test source attribution inference from path."""

    def test_infer_mit_ocw(self, metadata_manager, tmp_path):
        """Test inferring MIT OCW source."""
        video = tmp_path / "general" / "mit-ocw-6.0001" / "lecture.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_source_attribution(video)

        assert result == SourceAttribution.MIT_OCW

    def test_infer_cs50(self, metadata_manager, tmp_path):
        """Test inferring CS50 source."""
        video = tmp_path / "evening-mixed" / "harvard-cs50" / "lecture.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_source_attribution(video)

        assert result == SourceAttribution.CS50

    def test_infer_khan_academy(self, metadata_manager, tmp_path):
        """Test inferring Khan Academy source."""
        video = tmp_path / "kids-after-school" / "khan-academy" / "intro.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_source_attribution(video)

        assert result == SourceAttribution.KHAN_ACADEMY

    def test_infer_blender_failover(self, metadata_manager, tmp_path):
        """Test inferring Blender (failover) source."""
        video = tmp_path / "failover" / "big_buck_bunny.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_source_attribution(video)

        assert result == SourceAttribution.BLENDER

    def test_infer_unknown_defaults_to_blender(self, metadata_manager, tmp_path):
        """Test unknown source defaults to Blender."""
        video = tmp_path / "unknown" / "video.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_source_attribution(video)

        assert result == SourceAttribution.BLENDER


class TestInferTimeBlocks:
    """Test time block inference from directory structure."""

    def test_infer_kids_after_school(self, metadata_manager, tmp_path):
        """Test inferring kids-after-school time block."""
        video = tmp_path / "kids-after-school" / "video.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_time_blocks(video)

        assert result == ["after_school_kids"]

    def test_infer_professional_hours(self, metadata_manager, tmp_path):
        """Test inferring professional-hours time block."""
        video = tmp_path / "professional-hours" / "video.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_time_blocks(video)

        assert result == ["professional_hours"]

    def test_infer_evening_mixed(self, metadata_manager, tmp_path):
        """Test inferring evening-mixed time block."""
        video = tmp_path / "evening-mixed" / "video.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_time_blocks(video)

        assert result == ["evening_mixed"]

    def test_infer_general_multiple_blocks(self, metadata_manager, tmp_path):
        """Test general content maps to multiple time blocks."""
        video = tmp_path / "general" / "video.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_time_blocks(video)

        assert "general" in result
        assert "evening_mixed" in result

    def test_infer_time_blocks_outside_content_root(self, metadata_manager, tmp_path):
        """Test video outside content root defaults to general."""
        external_dir = tmp_path.parent / "external"
        external_dir.mkdir(exist_ok=True)
        video = external_dir / "video.mp4"

        result = metadata_manager.infer_time_blocks(video)

        assert result == ["general"]


class TestInferAgeRating:
    """Test age rating inference."""

    def test_kids_after_school_gets_kids_rating(self, metadata_manager, tmp_path):
        """Test kids directory gets KIDS rating."""
        video = tmp_path / "kids-after-school" / "video.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_age_rating(video)

        assert result == AgeRating.KIDS

    def test_professional_hours_gets_adult_rating(self, metadata_manager, tmp_path):
        """Test professional directory gets ADULT rating."""
        video = tmp_path / "professional-hours" / "video.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_age_rating(video)

        assert result == AgeRating.ADULT

    def test_general_gets_all_rating(self, metadata_manager, tmp_path):
        """Test general directory gets ALL rating."""
        video = tmp_path / "general" / "video.mp4"
        video.parent.mkdir(parents=True)

        result = metadata_manager.infer_age_rating(video)

        assert result == AgeRating.ALL


class TestGenerateTags:
    """Test tag generation from filename and path."""

    def test_generate_python_tag(self, metadata_manager, tmp_path):
        """Test Python tag generation."""
        video = tmp_path / "mit-ocw" / "python_intro.mp4"
        video.parent.mkdir(parents=True)

        tags = metadata_manager.generate_tags(video, "Introduction to Python")

        assert "python" in tags

    def test_generate_beginner_tag(self, metadata_manager, tmp_path):
        """Test beginner tag generation."""
        video = tmp_path / "intro.mp4"

        tags = metadata_manager.generate_tags(video, "Introduction to Programming")

        assert "beginner" in tags

    def test_generate_algorithms_tag(self, metadata_manager, tmp_path):
        """Test algorithms tag generation."""
        video = tmp_path / "algo.mp4"

        tags = metadata_manager.generate_tags(video, "Sorting Algorithms")

        assert "algorithms" in tags

    def test_generate_university_tag_for_mit(self, metadata_manager, tmp_path):
        """Test MIT OCW gets university tag."""
        video = tmp_path / "mit-ocw" / "lecture.mp4"
        video.parent.mkdir(parents=True)

        tags = metadata_manager.generate_tags(video, "Computer Science Lecture")

        assert "university" in tags

    def test_default_educational_tag(self, metadata_manager, tmp_path):
        """Test default educational tag when no specific tags match."""
        video = tmp_path / "generic_video.mp4"

        tags = metadata_manager.generate_tags(video, "Random Educational Content")

        assert "educational" in tags


class TestConvertToWindowsPath:
    """Test Linux to Windows UNC path conversion."""

    def test_convert_linux_to_windows_path(self, metadata_manager):
        """Test conversion from Linux path to Windows UNC path."""
        linux_path = Path("/home/turtle_wolfe/repos/OBS_bot/content/general/video.mp4")

        windows_path = metadata_manager.convert_to_windows_path(linux_path)

        assert windows_path.startswith("\\\\wsl.localhost\\Debian")
        assert "home\\turtle_wolfe\\repos\\OBS_bot\\content\\general\\video.mp4" in windows_path

    def test_convert_preserves_full_path(self, metadata_manager):
        """Test all path components are preserved."""
        linux_path = Path("/home/user/test/path/to/file.mp4")

        windows_path = metadata_manager.convert_to_windows_path(linux_path)

        assert "\\home\\user\\test\\path\\to\\file.mp4" in windows_path


class TestGenerateAttributionText:
    """Test attribution text generation."""

    def test_generate_mit_ocw_attribution(self, metadata_manager):
        """Test MIT OCW attribution format."""
        text = metadata_manager.generate_attribution_text(
            SourceAttribution.MIT_OCW,
            "6.0001",
            "Introduction to Python",
            "CC BY-NC-SA 4.0"
        )

        assert text == "MIT OCW 6.0001: Introduction to Python - CC BY-NC-SA 4.0"

    def test_generate_cs50_attribution(self, metadata_manager):
        """Test CS50 attribution format."""
        text = metadata_manager.generate_attribution_text(
            SourceAttribution.CS50,
            "Introduction to Computer Science",
            "Lecture 0",
            "CC BY-NC-SA 4.0"
        )

        assert text == "Harvard CS50 Introduction to Computer Science: Lecture 0 - CC BY-NC-SA 4.0"

    def test_generate_khan_academy_attribution(self, metadata_manager):
        """Test Khan Academy attribution format."""
        text = metadata_manager.generate_attribution_text(
            SourceAttribution.KHAN_ACADEMY,
            "Computer Programming",
            "Intro to Drawing",
            "CC BY-NC-SA"
        )

        assert text == "Khan Academy Computer Programming: Intro to Drawing - CC BY-NC-SA"


class TestGetLicenseType:
    """Test license type retrieval."""

    def test_mit_ocw_license(self, metadata_manager):
        """Test MIT OCW license type."""
        license_type = metadata_manager.get_license_type(SourceAttribution.MIT_OCW)
        assert license_type == "CC BY-NC-SA 4.0"

    def test_cs50_license(self, metadata_manager):
        """Test CS50 license type."""
        license_type = metadata_manager.get_license_type(SourceAttribution.CS50)
        assert license_type == "CC BY-NC-SA 4.0"

    def test_khan_academy_license(self, metadata_manager):
        """Test Khan Academy license type."""
        license_type = metadata_manager.get_license_type(SourceAttribution.KHAN_ACADEMY)
        assert license_type == "CC BY-NC-SA"

    def test_blender_license(self, metadata_manager):
        """Test Blender license type."""
        license_type = metadata_manager.get_license_type(SourceAttribution.BLENDER)
        assert license_type == "CC BY 3.0"


class TestExportToJson:
    """Test JSON export functionality."""

    def test_export_to_json_creates_file(self, metadata_manager, tmp_path):
        """Test JSON export creates file."""
        content_sources = [
            ContentSource(
                title="Test Video",
                file_path=str(tmp_path / "test.mp4"),
                windows_obs_path="\\\\wsl.localhost\\Debian\\test.mp4",
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
                last_verified="2025-10-22T10:00:00Z"
            )
        ]

        output_file = tmp_path / "output.json"
        metadata_manager.export_to_json(content_sources, output_file)

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert len(data) == 1
        assert data[0]["title"] == "Test Video"

    def test_export_to_json_empty_list(self, metadata_manager, tmp_path):
        """Test exporting empty list creates valid JSON."""
        output_file = tmp_path / "empty.json"
        metadata_manager.export_to_json([], output_file)

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data == []


class TestPrintSummary:
    """Test summary statistics printing."""

    def test_print_summary_with_content(self, metadata_manager, capsys):
        """Test summary prints statistics correctly."""
        content_sources = [
            ContentSource(
                title="Video 1",
                file_path="/test1.mp4",
                windows_obs_path="\\\\test1.mp4",
                duration_sec=600,
                file_size_mb=100.0,
                source_attribution=SourceAttribution.MIT_OCW,
                license_type="CC BY-NC-SA 4.0",
                course_name="Course 1",
                source_url="https://example.com",
                attribution_text="Attribution 1",
                age_rating=AgeRating.ALL,
                time_blocks=["general"],
                priority=5,
                tags=["test"],
                last_verified="2025-10-22T10:00:00Z"
            ),
            ContentSource(
                title="Video 2",
                file_path="/test2.mp4",
                windows_obs_path="\\\\test2.mp4",
                duration_sec=1200,
                file_size_mb=200.0,
                source_attribution=SourceAttribution.CS50,
                license_type="CC BY-NC-SA 4.0",
                course_name="Course 2",
                source_url="https://example.com",
                attribution_text="Attribution 2",
                age_rating=AgeRating.ALL,
                time_blocks=["evening_mixed"],
                priority=5,
                tags=["test"],
                last_verified="2025-10-22T10:00:00Z"
            )
        ]

        metadata_manager.print_summary(content_sources)

        captured = capsys.readouterr()
        assert "Total Videos: 2" in captured.out
        assert "MIT_OCW: 1" in captured.out
        assert "CS50: 1" in captured.out

    def test_print_summary_empty_list(self, metadata_manager, capsys):
        """Test summary with no content."""
        metadata_manager.print_summary([])

        captured = capsys.readouterr()
        assert "No content sources found" in captured.out
