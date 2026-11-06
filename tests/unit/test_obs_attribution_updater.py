"""Unit tests for OBSAttributionUpdater service (T072).

Tests the OBS text overlay management for content attribution against the
service's real API: OBSAttributionUpdater(obs_controller), format_attribution_text(),
verify_text_source_exists(), update_attribution(content_source) and clear_attribution().
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.content_library import AgeRating, ContentSource, SourceAttribution
from src.services.obs_attribution_updater import (
    AttributionUpdateError,
    OBSAttributionUpdater,
)
from src.services.obs_controller import OBSConnectionError


@pytest.fixture
def mock_obs_controller():
    """Mock OBS controller with the methods the updater calls."""
    controller = MagicMock()
    controller.get_current_scene = AsyncMock(return_value="Automated Content")
    controller.update_text_content = AsyncMock()
    controller._ensure_connected = MagicMock(return_value=MagicMock())
    return controller


@pytest.fixture
def attribution_updater(mock_obs_controller):
    """Create OBSAttributionUpdater instance around the mock controller."""
    return OBSAttributionUpdater(mock_obs_controller)


def make_content(title="What is Computation?", license_type="CC BY-NC-SA 4.0") -> ContentSource:
    """A real Tier 3 ContentSource to hand to update_attribution."""
    return ContentSource(
        title=title,
        file_path="/app/content/mit_ocw/lecture_01.mp4",
        windows_obs_path="\\\\wsl.localhost\\Debian\\app\\content\\mit_ocw\\lecture_01.mp4",
        duration_sec=600,
        file_size_mb=100.0,
        width=1920,
        height=1080,
        source_attribution=SourceAttribution.MIT_OCW,
        license_type=license_type,
        course_name="6.0001 Introduction to Computer Science",
        source_url="https://ocw.mit.edu/courses/6-0001/",
        attribution_text=f"MIT OCW 6.0001: {title} - {license_type}",
        age_rating=AgeRating.ALL,
        time_blocks=["evening_general"],
        priority=5,
        tags=["python"],
        last_verified=datetime.utcnow(),
    )


def sent_text(mock_obs_controller) -> str:
    """The text of the one update_text_content call."""
    mock_obs_controller.update_text_content.assert_awaited_once()
    return mock_obs_controller.update_text_content.await_args.kwargs["text"]


# ===== Test verify_text_source_exists() =====


@pytest.mark.asyncio
async def test_verify_text_source_exists_true_when_obs_has_it(attribution_updater, mock_obs_controller):
    """The source is reported present when OBS answers the settings request."""
    ws = mock_obs_controller._ensure_connected.return_value
    ws.call.return_value = MagicMock()

    assert await attribution_updater.verify_text_source_exists() is True
    ws.call.assert_called_once()
    assert ws.call.call_args.args[0].__class__.__name__ == "GetInputSettings"


@pytest.mark.asyncio
async def test_verify_text_source_exists_false_when_obs_lacks_it(attribution_updater, mock_obs_controller):
    """The source is reported missing when OBS raises for the settings request."""
    ws = mock_obs_controller._ensure_connected.return_value
    ws.call.side_effect = Exception("No input was found")

    assert await attribution_updater.verify_text_source_exists() is False


@pytest.mark.asyncio
async def test_verify_text_source_exists_reraises_connection_error(attribution_updater, mock_obs_controller):
    """A lost OBS connection is an error, not a 'missing source' answer."""
    mock_obs_controller._ensure_connected.side_effect = OBSConnectionError("not connected")

    with pytest.raises(OBSConnectionError):
        await attribution_updater.verify_text_source_exists()


# ===== Test update_attribution() =====


@pytest.mark.asyncio
async def test_update_attribution_formats_text_correctly(attribution_updater, mock_obs_controller):
    """update_attribution sends the title and license to the configured text source."""
    await attribution_updater.update_attribution(make_content())

    assert mock_obs_controller.update_text_content.await_args.kwargs["source_name"] == "Content Attribution"
    text = sent_text(mock_obs_controller)
    assert "What is Computation?" in text
    assert "CC BY-NC-SA 4.0" in text


@pytest.mark.asyncio
async def test_update_attribution_with_minimal_info(attribution_updater, mock_obs_controller):
    """A short title and a plain CC BY license still produce a complete line."""
    await attribution_updater.update_attribution(make_content(title="Untitled", license_type="CC BY 4.0"))

    text = sent_text(mock_obs_controller)
    assert "Untitled" in text
    assert "CC BY 4.0" in text


# ===== Test clear_attribution() =====


@pytest.mark.asyncio
async def test_clear_attribution_sets_empty_text(attribution_updater, mock_obs_controller):
    """clear_attribution sets the text to an empty string."""
    await attribution_updater.clear_attribution()

    assert sent_text(mock_obs_controller) == ""


@pytest.mark.asyncio
async def test_clear_attribution_wraps_obs_errors(attribution_updater, mock_obs_controller):
    """A failed clear is reported as an AttributionUpdateError."""
    mock_obs_controller.update_text_content.side_effect = OBSConnectionError("gone")

    with pytest.raises(AttributionUpdateError):
        await attribution_updater.clear_attribution()


# ===== Test attribution timing (SC-013 requirement) =====


@pytest.mark.asyncio
async def test_update_attribution_completes_quickly(attribution_updater):
    """Attribution update completes in <1 second (SC-013)."""
    start = time.monotonic()
    await attribution_updater.update_attribution(make_content(title="Test Title", license_type="CC BY 4.0"))
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"Attribution update took {elapsed:.3f}s (exceeds 1s requirement)"


@pytest.mark.asyncio
async def test_update_attribution_times_out_when_obs_is_slow(mock_obs_controller):
    """An OBS call slower than the timeout becomes an AttributionUpdateError."""
    async def slow(**_kwargs):
        await asyncio.sleep(1.0)

    mock_obs_controller.update_text_content = AsyncMock(side_effect=slow)
    updater = OBSAttributionUpdater(mock_obs_controller, update_timeout=0.05)

    with pytest.raises(AttributionUpdateError, match="timed out"):
        await updater.update_attribution(make_content())


# ===== Test error handling =====


@pytest.mark.asyncio
async def test_update_attribution_handles_obs_disconnect(attribution_updater, mock_obs_controller):
    """An OBS disconnect surfaces as AttributionUpdateError, not a raw OBS error."""
    mock_obs_controller.update_text_content.side_effect = OBSConnectionError("OBS disconnected")

    with pytest.raises(AttributionUpdateError, match="OBS connection error"):
        await attribution_updater.update_attribution(make_content())


@pytest.mark.asyncio
async def test_update_attribution_wraps_unexpected_errors(attribution_updater, mock_obs_controller):
    """Any other failure is wrapped with the original error kept as the cause."""
    mock_obs_controller.update_text_content.side_effect = ConnectionError("socket reset")

    with pytest.raises(AttributionUpdateError, match="Failed to update attribution") as exc_info:
        await attribution_updater.update_attribution(make_content())

    assert isinstance(exc_info.value.__cause__, ConnectionError)


# ===== Test formatting edge cases =====


def test_format_attribution_with_all_parts(attribution_updater):
    """Source, course, title and license come out as '<source> <course>: <title> - <license>'."""
    text = attribution_updater.format_attribution_text(
        source_name="MIT OCW", course_name="6.0001", title="What is Computation?", license_type="CC BY-NC-SA 4.0",
    )

    assert text == "MIT OCW 6.0001: What is Computation? - CC BY-NC-SA 4.0"


def test_format_attribution_with_nothing_uses_the_default_line(attribution_updater):
    """With no information at all, the generic CC line is used."""
    assert attribution_updater.format_attribution_text() == "Educational Content - CC Licensed"


def test_format_attribution_with_long_title(attribution_updater):
    """A very long title is kept whole and the source and license are still present."""
    formatted = attribution_updater.format_attribution_text(
        source_name="MIT OCW", title="A" * 200, license_type="CC BY 4.0",
    )

    assert "MIT OCW" in formatted
    assert "A" * 200 in formatted
    assert formatted.endswith("CC BY 4.0")


def test_format_attribution_with_special_characters(attribution_updater):
    """Ampersands, quotes and angle brackets pass through unchanged."""
    formatted = attribution_updater.format_attribution_text(
        source_name="Source & Name",
        title='Title with "quotes" and <brackets>',
        license_type="CC BY-NC-SA 4.0",
    )

    assert "Source & Name" in formatted
    assert 'Title with "quotes" and <brackets>' in formatted
    assert "CC BY-NC-SA 4.0" in formatted


def test_format_attribution_prefers_the_stored_text(attribution_updater):
    """A content record's own attribution_text is shown as written."""
    from types import SimpleNamespace

    content = SimpleNamespace(
        source_attribution="MIT_OCW",
        course_name="6.0001",
        title="Lecture 1",
        license_type="CC BY-NC-SA 4.0",
        attribution_text="MIT OpenCourseWare 6.0001: Lecture 1 - CC BY-NC-SA 4.0",
    )

    assert attribution_updater.format_attribution_text(content) == content.attribution_text


def test_format_attribution_turns_the_source_code_into_a_readable_name(attribution_updater):
    """Without stored text, MIT_OCW shows as 'MIT OpenCourseWare' plus the course name."""
    from src.models.content_library import SourceAttribution
    from types import SimpleNamespace

    content = SimpleNamespace(
        source_attribution=SourceAttribution.MIT_OCW,
        course_name="6.0001",
        title="Lecture 1",
        license_type="CC BY-NC-SA 4.0",
        attribution_text="",
    )

    text = attribution_updater.format_attribution_text(content)

    assert text == "MIT OpenCourseWare 6.0001: Lecture 1 - CC BY-NC-SA 4.0"
    assert "MIT_OCW" not in text


# ===== Performance baseline =====


@pytest.mark.asyncio
async def test_attribution_update_performance_baseline(attribution_updater):
    """Ten consecutive updates each finish well inside the 1 s limit."""
    times = []
    for i in range(10):
        start = time.monotonic()
        await attribution_updater.update_attribution(make_content(title=f"Title {i}", license_type="CC BY 4.0"))
        times.append(time.monotonic() - start)

    max_time = max(times)
    assert max_time < 1.0, f"Slowest update took {max_time * 1000:.0f}ms"
