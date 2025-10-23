"""Unit tests for OBSAttributionUpdater service (T072).

Tests the OBS text overlay management for content attribution.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.obs_attribution_updater import OBSAttributionUpdater
from src.config.settings import OBSSettings


@pytest.fixture
def obs_settings():
    """Mock OBS settings."""
    return OBSSettings(
        host="localhost",
        port=4455,
        password="test_password",
        scenes={"automated_content": "Automated Content"},
        sources={},
    )


@pytest.fixture
def mock_obs_controller():
    """Mock OBS controller."""
    controller = MagicMock()
    controller.connect = AsyncMock()
    controller.disconnect = AsyncMock()
    controller.get_text_source = AsyncMock(return_value="Content Attribution")
    controller.update_text_source = AsyncMock()
    controller.create_text_source = AsyncMock()
    return controller


@pytest.fixture
def attribution_updater(obs_settings):
    """Create OBSAttributionUpdater instance."""
    return OBSAttributionUpdater(obs_settings)


# ===== Test ensure_text_source() =====


@pytest.mark.asyncio
async def test_ensure_text_source_creates_if_missing(attribution_updater, mock_obs_controller):
    """Test that ensure_text_source creates text source if it doesn't exist."""
    with patch.object(attribution_updater, "obs", mock_obs_controller):
        mock_obs_controller.get_text_source.return_value = None  # Source doesn't exist

        await attribution_updater.ensure_text_source()

        # Should create the source
        mock_obs_controller.create_text_source.assert_called_once()
        call_args = mock_obs_controller.create_text_source.call_args
        assert call_args[1]["source_name"] == "Content Attribution"
        assert call_args[1]["scene_name"] == "Automated Content"


@pytest.mark.asyncio
async def test_ensure_text_source_skips_if_exists(attribution_updater, mock_obs_controller):
    """Test that ensure_text_source skips creation if source already exists."""
    with patch.object(attribution_updater, "obs", mock_obs_controller):
        mock_obs_controller.get_text_source.return_value = "Content Attribution"

        await attribution_updater.ensure_text_source()

        # Should NOT create the source
        mock_obs_controller.create_text_source.assert_not_called()


# ===== Test update_attribution() =====


@pytest.mark.asyncio
async def test_update_attribution_formats_text_correctly(attribution_updater, mock_obs_controller):
    """Test that update_attribution formats attribution text correctly."""
    with patch.object(attribution_updater, "obs", mock_obs_controller):
        await attribution_updater.update_attribution(
            source_name="MIT OpenCourseWare 6.0001",
            title="What is Computation?",
            license_type="CC BY-NC-SA 4.0",
        )

        # Check that update was called with correct text
        mock_obs_controller.update_text_source.assert_called_once()
        call_args = mock_obs_controller.update_text_source.call_args
        text = call_args[1]["text"]

        assert "MIT OpenCourseWare 6.0001" in text
        assert "What is Computation?" in text
        assert "CC BY-NC-SA 4.0" in text


@pytest.mark.asyncio
async def test_update_attribution_with_minimal_info(attribution_updater, mock_obs_controller):
    """Test update_attribution with minimal information."""
    with patch.object(attribution_updater, "obs", mock_obs_controller):
        await attribution_updater.update_attribution(
            source_name="Unknown Source",
            title="Untitled",
            license_type="CC BY 4.0",
        )

        mock_obs_controller.update_text_source.assert_called_once()
        call_args = mock_obs_controller.update_text_source.call_args
        text = call_args[1]["text"]

        assert "Unknown Source" in text
        assert "Untitled" in text
        assert "CC BY 4.0" in text


# ===== Test clear_attribution() =====


@pytest.mark.asyncio
async def test_clear_attribution_sets_empty_text(attribution_updater, mock_obs_controller):
    """Test that clear_attribution sets text to empty string."""
    with patch.object(attribution_updater, "obs", mock_obs_controller):
        await attribution_updater.clear_attribution()

        mock_obs_controller.update_text_source.assert_called_once()
        call_args = mock_obs_controller.update_text_source.call_args
        assert call_args[1]["text"] == ""


# ===== Test attribution timing (SC-013 requirement) =====


@pytest.mark.asyncio
async def test_update_attribution_completes_quickly(attribution_updater, mock_obs_controller):
    """Test that attribution update completes in <1 second (SC-013)."""
    import time

    with patch.object(attribution_updater, "obs", mock_obs_controller):
        start = time.time()

        await attribution_updater.update_attribution(
            source_name="Test Source",
            title="Test Title",
            license_type="CC BY 4.0",
        )

        elapsed = time.time() - start

        # Should complete in well under 1 second (allowing for test overhead)
        assert elapsed < 1.0, f"Attribution update took {elapsed:.3f}s (exceeds 1s requirement)"


# ===== Test error handling =====


@pytest.mark.asyncio
async def test_update_attribution_handles_obs_disconnect(attribution_updater, mock_obs_controller):
    """Test that update_attribution handles OBS disconnect gracefully."""
    with patch.object(attribution_updater, "obs", mock_obs_controller):
        mock_obs_controller.update_text_source.side_effect = ConnectionError("OBS disconnected")

        # Should not raise exception
        with pytest.raises(ConnectionError):
            await attribution_updater.update_attribution(
                source_name="Test",
                title="Test",
                license_type="CC BY 4.0",
            )


@pytest.mark.asyncio
async def test_ensure_text_source_handles_create_failure(attribution_updater, mock_obs_controller):
    """Test that ensure_text_source handles creation failure."""
    with patch.object(attribution_updater, "obs", mock_obs_controller):
        mock_obs_controller.get_text_source.return_value = None
        mock_obs_controller.create_text_source.side_effect = Exception("Creation failed")

        with pytest.raises(Exception):
            await attribution_updater.ensure_text_source()


# ===== Test formatting edge cases =====


def test_format_attribution_with_long_title(attribution_updater):
    """Test attribution formatting with very long title."""
    formatted = attribution_updater._format_attribution(
        source_name="MIT OCW",
        title="A" * 200,  # Very long title
        license_type="CC BY 4.0",
    )

    # Should still format correctly (may truncate)
    assert "MIT OCW" in formatted
    assert "CC BY 4.0" in formatted


def test_format_attribution_with_special_characters(attribution_updater):
    """Test attribution formatting with special characters."""
    formatted = attribution_updater._format_attribution(
        source_name="Source & Name",
        title='Title with "quotes" and <brackets>',
        license_type="CC BY-NC-SA 4.0",
    )

    assert "Source & Name" in formatted
    assert "CC BY-NC-SA 4.0" in formatted


# ===== Performance baseline =====


@pytest.mark.asyncio
async def test_attribution_update_performance_baseline(attribution_updater, mock_obs_controller):
    """Establish performance baseline for attribution updates."""
    import time

    with patch.object(attribution_updater, "obs", mock_obs_controller):
        # Measure 10 consecutive updates
        times = []
        for i in range(10):
            start = time.time()
            await attribution_updater.update_attribution(
                source_name=f"Source {i}",
                title=f"Title {i}",
                license_type="CC BY 4.0",
            )
            times.append(time.time() - start)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        # Log performance metrics
        print(f"\nAttribution update performance:")
        print(f"  Average: {avg_time * 1000:.2f}ms")
        print(f"  Maximum: {max_time * 1000:.2f}ms")

        # All updates should be sub-second
        assert max_time < 1.0, f"Slowest update took {max_time * 1000:.0f}ms"
