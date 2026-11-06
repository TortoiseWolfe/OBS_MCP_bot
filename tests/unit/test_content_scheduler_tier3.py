"""Unit tests for enhanced ContentScheduler with time-aware selection (Tier 3).

Tests smart scheduling, time-block detection, and database-driven content selection.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.models.content_library import AgeRating, ContentSource, SourceAttribution
from src.services.content_scheduler import ContentScheduler


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock()
    settings.obs = Mock()
    return settings


@pytest.fixture
def mock_obs_controller():
    """Create mock OBS controller."""
    obs = AsyncMock()
    obs.switch_scene = AsyncMock()
    obs.connect = AsyncMock()
    obs.disconnect = AsyncMock()
    return obs


@pytest.fixture
def mock_content_source_repo():
    """Create mock ContentSourceRepository."""
    return Mock()


@pytest.fixture
def scheduler(mock_settings, mock_obs_controller):
    """Create ContentScheduler without repository (filesystem mode)."""
    return ContentScheduler(
        settings=mock_settings,
        obs_controller=mock_obs_controller,
    )


@pytest.fixture
def scheduler_with_db(mock_settings, mock_obs_controller, mock_content_source_repo):
    """Create ContentScheduler with repository (database mode)."""
    return ContentScheduler(
        settings=mock_settings,
        obs_controller=mock_obs_controller,
        content_source_repo=mock_content_source_repo,
    )


@pytest.fixture
def sample_content_sources():
    """Create sample ContentSource entities for different time blocks."""
    return [
        ContentSource(
            title="Kids Video 1",
            file_path="/app/content/kids/video1.mp4",
            windows_obs_path="\\\\wsl.localhost\\content\\kids\\video1.mp4",
            duration_sec=600,
            file_size_mb=100.0,
            width=1920,
            height=1080,
            source_attribution=SourceAttribution.KHAN_ACADEMY,
            license_type="CC BY-NC-SA",
            course_name="Computer Programming",
            source_url="https://khanacademy.org",
            attribution_text="Khan Academy: Kids Video 1 - CC BY-NC-SA",
            age_rating=AgeRating.KIDS,
            time_blocks=["after_school_kids"],
            priority=5,
            tags=["beginner"],
            last_verified=datetime.now(timezone.utc),
        ),
        ContentSource(
            title="Professional Video 1",
            file_path="/app/content/professional/video1.mp4",
            windows_obs_path="\\\\wsl.localhost\\content\\professional\\video1.mp4",
            duration_sec=1200,
            file_size_mb=200.0,
            width=1920,
            height=1080,
            source_attribution=SourceAttribution.MIT_OCW,
            license_type="CC BY-NC-SA 4.0",
            course_name="6.0001",
            source_url="https://ocw.mit.edu",
            attribution_text="MIT OCW 6.0001: Professional Video 1 - CC BY-NC-SA 4.0",
            age_rating=AgeRating.ADULT,
            time_blocks=["professional_hours"],
            priority=3,
            tags=["advanced", "python"],
            last_verified=datetime.now(timezone.utc),
        ),
        ContentSource(
            title="Evening Video 1",
            file_path="/app/content/evening/video1.mp4",
            windows_obs_path="\\\\wsl.localhost\\content\\evening\\video1.mp4",
            duration_sec=3600,
            file_size_mb=500.0,
            width=1920,
            height=1080,
            source_attribution=SourceAttribution.CS50,
            license_type="CC BY-NC-SA 4.0",
            course_name="Introduction to Computer Science",
            source_url="https://cs50.harvard.edu",
            attribution_text="Harvard CS50: Evening Video 1 - CC BY-NC-SA 4.0",
            age_rating=AgeRating.ALL,
            time_blocks=["evening_mixed"],
            priority=7,
            tags=["algorithms"],
            last_verified=datetime.now(timezone.utc),
        ),
        ContentSource(
            title="General Video 1",
            file_path="/app/content/general/video1.mp4",
            windows_obs_path="\\\\wsl.localhost\\content\\general\\video1.mp4",
            duration_sec=900,
            file_size_mb=150.0,
            width=1920,
            height=1080,
            source_attribution=SourceAttribution.MIT_OCW,
            license_type="CC BY-NC-SA 4.0",
            course_name="General Course",
            source_url="https://ocw.mit.edu",
            attribution_text="MIT OCW: General Video 1 - CC BY-NC-SA 4.0",
            age_rating=AgeRating.ALL,
            time_blocks=["general", "evening_mixed"],
            priority=5,
            tags=["educational"],
            last_verified=datetime.now(timezone.utc),
        ),
    ]


class TestGetCurrentTimeBlock:
    """Test time block detection based on current time."""

    @patch("src.services.content_scheduler.datetime")
    def test_kids_after_school_time_block(self, mock_datetime, scheduler):
        """Test kids after school time block (3-6 PM weekdays)."""
        # Mock Wednesday 4 PM UTC
        mock_now = Mock()
        mock_now.hour = 16  # 4 PM
        mock_now.weekday.return_value = 2  # Wednesday
        mock_datetime.now.return_value = mock_now

        result = scheduler._get_current_time_block()

        assert result == "after_school_kids"

    @patch("src.services.content_scheduler.datetime")
    def test_professional_hours_time_block(self, mock_datetime, scheduler):
        """Test professional hours time block (9 AM-3 PM weekdays)."""
        # Mock Tuesday 11 AM UTC
        mock_now = Mock()
        mock_now.hour = 11
        mock_now.weekday.return_value = 1  # Tuesday
        mock_datetime.now.return_value = mock_now

        result = scheduler._get_current_time_block()

        assert result == "professional_hours"

    @patch("src.services.content_scheduler.datetime")
    def test_evening_mixed_time_block(self, mock_datetime, scheduler):
        """Test evening mixed time block (7-10 PM daily)."""
        # Mock Saturday 8 PM UTC
        mock_now = Mock()
        mock_now.hour = 20  # 8 PM
        mock_now.weekday.return_value = 5  # Saturday
        mock_datetime.now.return_value = mock_now

        result = scheduler._get_current_time_block()

        assert result == "evening_mixed"

    @patch("src.services.content_scheduler.datetime")
    def test_general_time_block_late_night(self, mock_datetime, scheduler):
        """Test general time block during off-hours (late night)."""
        # Mock Sunday 2 AM UTC
        mock_now = Mock()
        mock_now.hour = 2
        mock_now.weekday.return_value = 6  # Sunday
        mock_datetime.now.return_value = mock_now

        result = scheduler._get_current_time_block()

        assert result == "general"

    @patch("src.services.content_scheduler.datetime")
    def test_kids_time_not_on_weekend(self, mock_datetime, scheduler):
        """Test kids time block doesn't trigger on weekends."""
        # Mock Saturday 4 PM UTC (kids time but weekend)
        mock_now = Mock()
        mock_now.hour = 16
        mock_now.weekday.return_value = 5  # Saturday
        mock_datetime.now.return_value = mock_now

        result = scheduler._get_current_time_block()

        assert result != "after_school_kids"
        assert result == "general"


class TestGetAgeRatingForTimeBlock:
    """Test age rating mapping for time blocks."""

    def test_kids_time_block_gets_kids_rating(self, scheduler):
        """Test kids time block requires KIDS rating."""
        result = scheduler._get_age_rating_for_time_block("after_school_kids")
        assert result == AgeRating.KIDS

    def test_professional_time_block_gets_adult_rating(self, scheduler):
        """Test professional time block requires ADULT rating."""
        result = scheduler._get_age_rating_for_time_block("professional_hours")
        assert result == AgeRating.ADULT

    def test_evening_time_block_gets_all_rating(self, scheduler):
        """Test evening time block allows ALL ratings."""
        result = scheduler._get_age_rating_for_time_block("evening_mixed")
        assert result == AgeRating.ALL

    def test_general_time_block_gets_all_rating(self, scheduler):
        """Test general time block allows ALL ratings."""
        result = scheduler._get_age_rating_for_time_block("general")
        assert result == AgeRating.ALL


class TestIsAgeAppropriate:
    """Test age appropriateness checking."""

    def test_all_content_always_appropriate(self, scheduler):
        """Test ALL-rated content is appropriate for any time block."""
        assert scheduler._is_age_appropriate(AgeRating.ALL, AgeRating.KIDS) is True
        assert scheduler._is_age_appropriate(AgeRating.ALL, AgeRating.ADULT) is True
        assert scheduler._is_age_appropriate(AgeRating.ALL, AgeRating.ALL) is True

    def test_kids_content_only_for_kids_blocks(self, scheduler):
        """Test KIDS-rated content only appropriate for KIDS time blocks."""
        assert scheduler._is_age_appropriate(AgeRating.KIDS, AgeRating.KIDS) is True
        assert scheduler._is_age_appropriate(AgeRating.KIDS, AgeRating.ADULT) is False
        assert scheduler._is_age_appropriate(AgeRating.KIDS, AgeRating.ALL) is False

    def test_adult_content_for_adult_and_all_blocks(self, scheduler):
        """Test ADULT-rated content appropriate for ADULT and ALL blocks."""
        assert scheduler._is_age_appropriate(AgeRating.ADULT, AgeRating.KIDS) is False
        assert scheduler._is_age_appropriate(AgeRating.ADULT, AgeRating.ADULT) is True
        assert scheduler._is_age_appropriate(AgeRating.ADULT, AgeRating.ALL) is True


class TestSelectContentForCurrentTime:
    """Test time-aware content selection from database."""

    @patch("src.services.content_scheduler.ContentScheduler._get_current_time_block")
    def test_select_content_for_kids_time(
        self, mock_get_time_block, scheduler_with_db, sample_content_sources
    ):
        """Test selecting content during kids after school time."""
        mock_get_time_block.return_value = "after_school_kids"
        scheduler_with_db.content_source_repo.list_all.return_value = sample_content_sources

        result = scheduler_with_db._select_content_for_current_time()

        # Should only include kids content (KIDS rating + after_school_kids time block)
        assert len(result) == 1
        assert result[0].title == "Kids Video 1"
        assert result[0].age_rating == AgeRating.KIDS

    @patch("src.services.content_scheduler.ContentScheduler._get_current_time_block")
    def test_select_content_for_professional_time(
        self, mock_get_time_block, scheduler_with_db, sample_content_sources
    ):
        """Test selecting content during professional hours."""
        mock_get_time_block.return_value = "professional_hours"
        scheduler_with_db.content_source_repo.list_all.return_value = sample_content_sources

        result = scheduler_with_db._select_content_for_current_time()

        # Should only include professional content (ADULT rating + professional_hours block)
        assert len(result) == 1
        assert result[0].title == "Professional Video 1"
        assert result[0].age_rating == AgeRating.ADULT

    @patch("src.services.content_scheduler.ContentScheduler._get_current_time_block")
    def test_select_content_for_evening_time(
        self, mock_get_time_block, scheduler_with_db, sample_content_sources
    ):
        """Test selecting content during evening mixed time."""
        mock_get_time_block.return_value = "evening_mixed"
        scheduler_with_db.content_source_repo.list_all.return_value = sample_content_sources

        result = scheduler_with_db._select_content_for_current_time()

        # Should include evening and general content (ALL rating + evening_mixed block)
        assert len(result) == 2
        titles = [cs.title for cs in result]
        assert "Evening Video 1" in titles
        assert "General Video 1" in titles

    @patch("src.services.content_scheduler.ContentScheduler._get_current_time_block")
    def test_select_content_priority_ordering(
        self, mock_get_time_block, scheduler_with_db, sample_content_sources
    ):
        """Test content is ordered by priority (1=highest)."""
        mock_get_time_block.return_value = "evening_mixed"
        scheduler_with_db.content_source_repo.list_all.return_value = sample_content_sources

        result = scheduler_with_db._select_content_for_current_time()

        # Should be sorted by priority (lower number = higher priority)
        # General Video (priority=5) should come before Evening Video (priority=7)
        assert result[0].priority <= result[-1].priority

    @patch("src.services.content_scheduler.ContentScheduler._get_current_time_block")
    def test_select_content_fallback_to_general(
        self, mock_get_time_block, scheduler_with_db, sample_content_sources
    ):
        """Test fallback to general content when no time-specific matches."""
        mock_get_time_block.return_value = "after_school_kids"

        # Remove kids content from sample data
        content_without_kids = [cs for cs in sample_content_sources if cs.age_rating != AgeRating.KIDS]
        scheduler_with_db.content_source_repo.list_all.return_value = content_without_kids

        result = scheduler_with_db._select_content_for_current_time()

        # No kids content is left, so the scheduler falls back to content tagged
        # "general". Only "General Video 1" has that tag and an age rating (ALL)
        # that is allowed in a kids block.
        assert [cs.title for cs in result] == ["General Video 1"]

    @patch("src.services.content_scheduler.ContentScheduler._get_current_time_block")
    def test_select_content_empty_database(
        self, mock_get_time_block, scheduler_with_db
    ):
        """Test handling of empty database."""
        mock_get_time_block.return_value = "general"
        scheduler_with_db.content_source_repo.list_all.return_value = []

        result = scheduler_with_db._select_content_for_current_time()

        assert result == []

    def test_select_content_without_repository(self, scheduler):
        """Test selection fails gracefully without repository."""
        result = scheduler._select_content_for_current_time()

        assert result == []


class TestDatabaseVsFilesystemMode:
    """Test scheduler behavior in database vs filesystem modes."""

    def test_scheduler_detects_database_mode(self, scheduler_with_db):
        """Test scheduler detects database mode when repository provided."""
        assert scheduler_with_db._use_database is True

    def test_scheduler_detects_filesystem_mode(self, scheduler):
        """Test scheduler detects filesystem mode when no repository."""
        assert scheduler._use_database is False


class TestContentPlaybackIntegration:
    """Test content playback with time-aware selection."""

    @pytest.mark.asyncio
    @patch("src.services.content_scheduler.ContentScheduler._select_content_for_current_time")
    async def test_database_mode_uses_actual_duration(
        self, mock_select, scheduler_with_db, mock_obs_controller, sample_content_sources
    ):
        """Test database mode waits the video's real duration, not the 300 s default."""
        content = sample_content_sources[0]  # duration_sec=600
        mock_select.return_value = [content]

        mock_obs_controller._ensure_connected = Mock()
        mock_obs_controller.get_canvas_resolution = AsyncMock(return_value=(1920, 1080))
        mock_obs_controller.calculate_video_transform = Mock(return_value=(0, 0, 1.0, 1.0))
        mock_obs_controller.set_source_transform = AsyncMock()

        waits = []

        async def fake_sleep(seconds):
            # Record every wait and stop the loop once the video "finished playing".
            waits.append(seconds)
            if seconds == content.duration_sec:
                scheduler_with_db._running = False

        scheduler_with_db._running = True
        with patch("src.services.content_scheduler.asyncio.sleep", fake_sleep):
            await scheduler_with_db._content_playback_loop()

        mock_obs_controller.switch_scene.assert_awaited_with("Automated Content")
        # The video's real length, then the short 0.5 s transition pause. A 5 s wait
        # here would mean the loop hit an error and went into its retry wait.
        assert waits == [600, 0.5]


class TestContentSchedulerBackwardCompatibility:
    """Test backward compatibility with Tier 1 filesystem mode."""

    def test_filesystem_mode_still_works(self, scheduler, tmp_path):
        """Test filesystem discovery still finds the video files in the content folder."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "video1.mp4").write_text("fake")
        (content_dir / "video2.mp4").write_text("fake")
        (content_dir / "notes.txt").write_text("not a video")

        # _discover_content looks in /app/content; point it at the temporary folder.
        with patch("src.services.content_scheduler.Path", return_value=content_dir):
            files = scheduler._discover_content()

        assert [f.name for f in files] == ["video1.mp4", "video2.mp4"]
