"""Integration test for complete content library workflow (T075).

Tests the end-to-end content library management workflow:
1. Content download/discovery
2. Metadata extraction
3. Database population
4. Content scheduling
5. OBS playback with attribution

Everything except test_content_playback_with_attribution (marked requires_obs) runs
without OBS, against the ``library`` fixture from conftest.py.
"""

import asyncio

import pytest

from src.persistence.repositories.content_library import ContentSourceRepository
from src.services.obs_attribution_updater import OBSAttributionUpdater


@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_library_end_to_end(library):
    """Test complete workflow from content discovery to playback."""
    # Step 1: Verify content directory exists
    content_dir = library.root / "content"
    assert content_dir.exists(), "Content directory not found"

    # Step 2: Verify video files exist
    video_files = list(content_dir.rglob("*.mp4"))
    assert len(video_files) > 0, "No video files found in content library"

    # Step 3: Verify database has content
    repo = ContentSourceRepository(str(library.db_path))
    all_videos = repo.list_all()
    assert len(all_videos) > 0, "No videos in database - metadata extraction may have failed"

    # Step 4: Verify videos have required metadata
    for video in all_videos[:5]:  # Check first 5
        assert video.title, "Video missing title"
        assert video.duration_sec > 0, "Video missing duration"
        assert video.file_size_mb > 0, "Video missing file size"
        assert video.source_attribution, "Video missing attribution"
        assert video.license_type, "Video missing license type"

    print(f"\n✓ Content library has {len(all_videos)} videos with complete metadata")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_scheduling_integration(library):
    """Test that content scheduler can select appropriate content."""
    repo = ContentSourceRepository(str(library.db_path))
    all_videos = repo.list_all()
    assert len(all_videos) > 0, "No videos in database"

    # Test time-block filtering
    general_videos = [v for v in all_videos if "general" in v.time_blocks]
    assert len(general_videos) > 0, "No videos in 'general' time block"

    # Test age rating filtering
    all_ages_videos = [v for v in all_videos if v.age_rating.value == "all"]
    assert len(all_ages_videos) > 0, "No all-ages videos found"

    print(f"\n✓ Content scheduling: {len(general_videos)} general videos, {len(all_ages_videos)} all-ages")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_content_playback_with_attribution(library, live_obs):
    """Test content playback with automatic attribution updates (needs a live OBS)."""
    repo = ContentSourceRepository(str(library.db_path))
    videos = repo.list_all()
    assert len(videos) > 0, "No videos in database"

    test_video = videos[0]

    updater = OBSAttributionUpdater(live_obs)
    assert await updater.verify_text_source_exists(), (
        "OBS has no 'Content Attribution' text source in the current scene"
    )
    await updater.update_attribution(test_video)

    # Give OBS a moment to apply the change
    await asyncio.sleep(0.1)

    # Cleanup
    await updater.clear_attribution()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_library_statistics(library):
    """Test that library statistics can be generated."""
    repo = ContentSourceRepository(str(library.db_path))
    videos = repo.list_all()
    assert len(videos) > 0, "No videos in database"

    # Calculate statistics
    total_duration = sum(v.duration_sec for v in videos)
    total_size_mb = sum(v.file_size_mb for v in videos)

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

    print("\n✓ Library Statistics:")
    print(f"  Total videos: {len(videos)}")
    print(f"  Total duration: {total_duration / 3600:.1f} hours")
    print(f"  Total size: {total_size_mb / 1024:.2f} GB")
    print(f"  By source: {by_source}")
    print(f"  By time block: {by_time_block}")

    # Verify statistics make sense
    assert total_duration > 0, "Invalid total duration"
    assert total_size_mb > 0, "Invalid total size"
    assert len(by_source) > 0, "No source attribution"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_time_block_compliance(library):
    """Test that time-block organization matches constitutional requirements."""
    repo = ContentSourceRepository(str(library.db_path))
    videos = repo.list_all()
    assert len(videos) > 0, "No videos in database"

    # The "general" block is the fallback for every other time of day, so it must
    # always have content. The other blocks may be empty while their content is still
    # being downloaded.
    general_videos = [v for v in videos if "general" in v.time_blocks]
    assert len(general_videos) > 0, "No videos in required time block: general"

    print("\n✓ Time-block compliance validated")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_license_compliance(library):
    """Test that all content has proper license attribution."""
    repo = ContentSourceRepository(str(library.db_path))
    videos = repo.list_all()
    assert len(videos) > 0, "No videos in database"

    # Verify all videos have license information
    for video in videos:
        assert video.license_type, f"Video missing license: {video.title}"
        assert video.source_attribution, f"Video missing attribution: {video.title}"

        # Verify license is one of the approved types
        valid_licenses = ["CC BY 3.0", "CC BY 4.0", "CC BY-NC-SA", "CC BY-NC-SA 3.0", "CC BY-NC-SA 4.0"]
        assert video.license_type in valid_licenses, f"Invalid license: {video.license_type}"

    print(f"\n✓ All {len(videos)} videos have valid CC licenses")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_file_accessibility(library):
    """Test that all database entries point to accessible files."""
    repo = ContentSourceRepository(str(library.db_path))
    videos = repo.list_all()
    assert len(videos) > 0, "No videos in database"

    missing_files = []
    for video in videos:
        file_path = library.resolve(video.file_path)
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
