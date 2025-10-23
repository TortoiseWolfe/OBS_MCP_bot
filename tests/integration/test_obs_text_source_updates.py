"""Integration test for OBS text source updates (T074).

Tests the live OBS text source attribution system.
Requires OBS to be running with obs-websocket enabled.
"""

import pytest
import asyncio
from src.services.obs_controller import OBSController
from src.services.obs_attribution_updater import OBSAttributionUpdater
from src.config.settings import Settings


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_obs_text_source_creation():
    """Test that text source can be created in OBS."""
    try:
        settings = Settings()
        updater = OBSAttributionUpdater(settings.obs)

        # Ensure text source exists
        await updater.ensure_text_source()

        # Verify source was created by trying to update it
        await updater.update_attribution(
            source_name="Test Source",
            title="Integration Test",
            license_type="CC BY 4.0",
        )

        # Cleanup
        await updater.clear_attribution()

    except ConnectionRefusedError:
        pytest.skip("OBS not running or WebSocket not enabled")
    except Exception as e:
        pytest.fail(f"OBS integration failed: {e}")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_obs_attribution_update_cycle():
    """Test full attribution update cycle with OBS."""
    try:
        settings = Settings()
        updater = OBSAttributionUpdater(settings.obs)

        # Ensure source exists
        await updater.ensure_text_source()

        # Update with test content
        await updater.update_attribution(
            source_name="MIT OpenCourseWare 6.0001",
            title="What is Computation?",
            license_type="CC BY-NC-SA 4.0",
        )

        # Wait briefly to ensure OBS processes the update
        await asyncio.sleep(0.1)

        # Update with different content
        await updater.update_attribution(
            source_name="Harvard CS50",
            title="Introduction to Computer Science",
            license_type="CC BY-NC-SA 4.0",
        )

        # Wait briefly
        await asyncio.sleep(0.1)

        # Clear attribution
        await updater.clear_attribution()

    except ConnectionRefusedError:
        pytest.skip("OBS not running or WebSocket not enabled")
    except Exception as e:
        pytest.fail(f"Attribution cycle failed: {e}")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_obs_text_source_visible_in_scene():
    """Test that text source is visible in the automated content scene."""
    try:
        settings = Settings()
        obs = OBSController(settings.obs)
        await obs.connect()

        # Get current scene items
        scene_items = await obs.get_scene_items(settings.obs.scenes["automated_content"])

        # Check if Content Attribution source exists
        source_names = [item.get("sourceName", "") for item in scene_items]
        assert "Content Attribution" in source_names, "Attribution source not found in scene"

        await obs.disconnect()

    except ConnectionRefusedError:
        pytest.skip("OBS not running or WebSocket not enabled")
    except Exception as e:
        pytest.fail(f"Scene inspection failed: {e}")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_obs_attribution_with_special_characters():
    """Test attribution with special characters and edge cases."""
    try:
        settings = Settings()
        updater = OBSAttributionUpdater(settings.obs)

        await updater.ensure_text_source()

        # Test with special characters
        await updater.update_attribution(
            source_name='Source & "Quoted" <Name>',
            title="Title with émojis 🎓 and spëcial çharacters",
            license_type="CC BY-NC-SA 4.0",
        )

        await asyncio.sleep(0.1)
        await updater.clear_attribution()

    except ConnectionRefusedError:
        pytest.skip("OBS not running or WebSocket not enabled")
    except Exception as e:
        pytest.fail(f"Special character handling failed: {e}")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_obs_multiple_rapid_updates():
    """Test that OBS handles multiple rapid attribution updates."""
    try:
        settings = Settings()
        updater = OBSAttributionUpdater(settings.obs)

        await updater.ensure_text_source()

        # Rapidly update attribution 10 times
        for i in range(10):
            await updater.update_attribution(
                source_name=f"Source {i}",
                title=f"Title {i}",
                license_type="CC BY 4.0",
            )

        # Should complete without errors
        await updater.clear_attribution()

    except ConnectionRefusedError:
        pytest.skip("OBS not running or WebSocket not enabled")
    except Exception as e:
        pytest.fail(f"Rapid updates failed: {e}")
