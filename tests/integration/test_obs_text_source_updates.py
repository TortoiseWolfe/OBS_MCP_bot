"""Integration test for OBS text source updates (T074).

Tests the live OBS text source attribution system.
Requires OBS to be running with obs-websocket enabled, so every test here is marked
requires_obs and is left out of CI. The ``live_obs`` and ``attribution_updater``
fixtures (conftest.py) connect to OBS and make the "Content Attribution" text source
if it is missing; with OBS down they error rather than skip.
"""

import asyncio

import pytest
from obswebsocket import requests as obs_requests

from src.config.settings import Settings
from src.models.content_library import SourceAttribution


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_obs_text_source_creation(live_obs, attribution_updater, make_content):
    """The attribution text source exists in OBS and accepts an update."""
    assert await attribution_updater.verify_text_source_exists()

    await attribution_updater.update_attribution(
        make_content(title="Integration Test", license_type="CC BY 4.0")
    )


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_obs_attribution_update_cycle(attribution_updater, make_content):
    """Test full attribution update cycle with OBS."""
    await attribution_updater.update_attribution(
        make_content(title="What is Computation?", source=SourceAttribution.MIT_OCW)
    )

    # Wait briefly to ensure OBS processes the update
    await asyncio.sleep(0.1)

    # Update with different content
    await attribution_updater.update_attribution(
        make_content(title="Introduction to Computer Science", source=SourceAttribution.CS50)
    )

    await asyncio.sleep(0.1)

    # Clear attribution
    await attribution_updater.clear_attribution()


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_obs_text_source_visible_in_scene(live_obs, attribution_updater):
    """Test that the text source is listed in the automated content scene."""
    scene_name = Settings().scenes.automated_content
    ws = live_obs._ensure_connected()

    scene_items = ws.call(obs_requests.GetSceneItemList(sceneName=scene_name)).getSceneItems()

    source_names = [item.get("sourceName", "") for item in scene_items]
    assert attribution_updater.text_source_name in source_names, (
        f"'{attribution_updater.text_source_name}' not found in scene '{scene_name}'"
    )


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_obs_attribution_with_special_characters(attribution_updater, make_content):
    """Test attribution with special characters and edge cases."""
    await attribution_updater.update_attribution(
        make_content(
            title='Title with "quotes" <tags> & émojis 🎓 and spëcial çharacters',
            license_type="CC BY-NC-SA 4.0",
        )
    )

    await asyncio.sleep(0.1)


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.asyncio
async def test_obs_multiple_rapid_updates(attribution_updater, make_content):
    """Test that OBS handles multiple rapid attribution updates."""
    # Rapidly update attribution 10 times; any failure raises
    for i in range(10):
        await attribution_updater.update_attribution(
            make_content(title=f"Title {i}", license_type="CC BY 4.0")
        )
