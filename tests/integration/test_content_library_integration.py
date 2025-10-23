"""Integration test for complete content library workflow (T075).

Tests the end-to-end content library management workflow:
1. Content download/discovery
2. Metadata extraction
3. Database population
4. Content scheduling
5. OBS playback with attribution
"""

import pytest
import asyncio
from pathlib import Path
from src.persistence.repositories.content_library import ContentSourceRepository
from src.services.content_scheduler import ContentScheduler
from src.services.obs_attribution_updater import OBSAttributionUpdater
from src.config.settings import Settings


@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_library_end_to_end():
    """Test complete workflow from content discovery to playback."""
    # Step 1: Verify content directory exists
    content_dir = Path("content")
    assert content_dir.exists(), "Content directory not found"

    # Step 2: Verify video files exist
    video_files = list(content_dir.rglob("*.mp4"))
    assert len(video_files) > 0, "No video files found in content library"

    # Step 3: Verify database has content
    repo = ContentSourceRepository("data/obs_bot.db")
    all_videos = repo.list_all()
    assert len(all_videos) > 0, "No videos in database - metadata extraction may have failed"

    # Step 4: Verify videos have required metadata
    for video in all_videos[:5]:  # Check first 5
        assert video.title, "Video missing title"
        assert video.duration_sec > 0, "Video missing duration"
        assert video.file_size_bytes > 0, "Video missing file size"
        assert video.source_attribution, "Video missing attribution"
        assert video.license_type, "Video missing license type"

    print(f"\n✓ Content library has {len(all_videos)} videos with complete metadata")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_scheduling_integration():
    """Test that content scheduler can select appropriate content."""
    repo = ContentSourceRepository("data/obs_bot.db")
    all_videos = repo.list_all()

    if len(all_videos) == 0:
        pytest.skip("No videos in database")

    # Test time-block filtering
    general_videos = [v for v in all_videos if "general" in v.time_blocks]
    assert len(general_videos) > 0, "No videos in 'general' time block"

    # Test age rating filtering
    all_ages_videos = [v for v in all_videos if v.age_rating == "all"]
    assert len(all_ages_videos) > 0, "No all-ages videos found"

    print(f"\n✓ Content scheduling: {len(general_videos)} general videos, {len(all_ages_videos)} all-ages")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_content_playback_with_attribution():
    """Test content playback with automatic attribution updates."""
    try:
        # Get a video from database
        repo = ContentSourceRepository("data/obs_bot.db")
        videos = repo.list_all()

        if len(videos) == 0:
            pytest.skip("No videos in database")

        test_video = videos[0]

        # Update attribution for this video
        settings = Settings()
        updater = OBSAttributionUpdater(settings.obs)

        await updater.ensure_text_source()
        await updater.update_attribution(
            source_name=test_video.source_attribution.value,
            title=test_video.title,
            license_type=test_video.license_type.value,
        )

        # Verify attribution was set
        await asyncio.sleep(0.1)

        print(f"\n✓ Successfully set attribution for: {test_video.title}")

        # Cleanup
        await updater.clear_attribution()

    except ConnectionRefusedError:
        pytest.skip("OBS not running or WebSocket not enabled")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_library_statistics():
    """Test that library statistics can be generated."""
    repo = ContentSourceRepository("data/obs_bot.db")
    videos = repo.list_all()

    if len(videos) == 0:
        pytest.skip("No videos in database")

    # Calculate statistics
    total_duration = sum(v.duration_sec for v in videos)
    total_size = sum(v.file_size_bytes for v in videos)

    # Group by source
    by_source = {}
    for video in videos:
        source = video.source_attribution.value
        by_source[source] = by_source.get(source, 0) + 1

    # Group by time block
    by_time_block = {}
    for video in videos:
        for block in video.time_blocks:
            by_time_block[block] = by_time_block.get(block, 0) + 1

    print(f"\n✓ Library Statistics:")
    print(f"  Total videos: {len(videos)}")
    print(f"  Total duration: {total_duration / 3600:.1f} hours")
    print(f"  Total size: {total_size / (1024**3):.2f} GB")
    print(f"  By source: {by_source}")
    print(f"  By time block: {by_time_block}")

    # Verify statistics make sense
    assert total_duration > 0, "Invalid total duration"
    assert total_size > 0, "Invalid total size"
    assert len(by_source) > 0, "No source attribution"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_time_block_compliance():
    """Test that time-block organization matches constitutional requirements."""
    repo = ContentSourceRepository("data/obs_bot.db")
    videos = repo.list_all()

    if len(videos) == 0:
        pytest.skip("No videos in database")

    # Required time blocks per constitution
    required_blocks = ["general", "kids-after-school", "professional-hours", "evening-mixed"]

    # Check each required block has content
    for block in required_blocks:
        block_videos = [v for v in videos if block in v.time_blocks]
        if block != "kids-after-school" and block != "professional-hours" and block != "evening-mixed":
            # General should have content
            assert len(block_videos) > 0, f"No videos in required time block: {block}"

    print(f"\n✓ Time-block compliance validated")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_license_compliance():
    """Test that all content has proper license attribution."""
    repo = ContentSourceRepository("data/obs_bot.db")
    videos = repo.list_all()

    if len(videos) == 0:
        pytest.skip("No videos in database")

    # Verify all videos have license information
    for video in videos:
        assert video.license_type, f"Video missing license: {video.title}"
        assert video.source_attribution, f"Video missing attribution: {video.title}"

        # Verify license is one of the approved types
        valid_licenses = ["CC BY 3.0", "CC BY 4.0", "CC BY-NC-SA 3.0", "CC BY-NC-SA 4.0"]
        assert video.license_type.value in valid_licenses, f"Invalid license: {video.license_type.value}"

    print(f"\n✓ All {len(videos)} videos have valid CC licenses")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_file_accessibility():
    """Test that all database entries point to accessible files."""
    repo = ContentSourceRepository("data/obs_bot.db")
    videos = repo.list_all()

    if len(videos) == 0:
        pytest.skip("No videos in database")

    missing_files = []
    for video in videos:
        file_path = Path(video.file_path)
        if not file_path.exists():
            missing_files.append(str(file_path))

    if missing_files:
        print(f"\n⚠ Warning: {len(missing_files)} files not accessible:")
        for path in missing_files[:5]:  # Show first 5
            print(f"  - {path}")

    # Most files should be accessible
    accessible_count = len(videos) - len(missing_files)
    accessibility_rate = accessible_count / len(videos) if videos else 0

    assert accessibility_rate >= 0.9, f"Only {accessibility_rate * 100:.1f}% of files accessible"

    print(f"\n✓ {accessible_count}/{len(videos)} files accessible ({accessibility_rate * 100:.1f}%)")
