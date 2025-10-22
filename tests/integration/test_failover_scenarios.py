"""Integration tests for US3 - Automatic Failover and Recovery.

Tests:
- T073: Content failure failover
- T074: OBS crash recovery
- T075: RTMP reconnection
- T076: Downtime event logging

Requirements tested:
- FR-024: Maintain pre-configured failover content
- FR-025: Auto-switch to failover within 5 seconds
- FR-026: Detect content failures
- FR-027: Auto-restart OBS if unresponsive
- FR-028: Log all failover events with diagnostics
- SC-005: Automatic failover recovers within 5 seconds (100% success rate)
"""

import asyncio
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.config.settings import get_settings
from src.models.downtime_event import DowntimeEvent, FailureCause
from src.models.stream_session import StreamSession
from src.persistence.db import Database
from src.persistence.repositories.events import EventsRepository
from src.services.failover_manager import FailoverManager
from src.services.obs_controller import OBSConnectionError, OBSController


@pytest.fixture
async def test_db():
    """Create test database with schema."""
    test_db_path = Path("data/test_failover.db")
    test_db_path.parent.mkdir(exist_ok=True)

    # Remove existing test DB
    if test_db_path.exists():
        test_db_path.unlink()

    db = Database(db_path=test_db_path)
    await db.connect()

    yield db

    # Cleanup
    await db.disconnect()
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
async def events_repo(test_db):
    """Create events repository with test database."""
    return EventsRepository(str(test_db.db_path))


@pytest.fixture
async def mock_obs_controller():
    """Create mock OBS controller."""
    mock_obs = MagicMock(spec=OBSController)
    mock_obs.is_connected = MagicMock(return_value=True)
    mock_obs.switch_scene = AsyncMock()
    mock_obs.connect = AsyncMock()
    mock_obs.start_streaming = AsyncMock()
    mock_obs.get_streaming_status = AsyncMock(return_value={"active": True, "reconnecting": False})
    return mock_obs


@pytest.fixture
async def failover_manager(mock_obs_controller, events_repo):
    """Create failover manager with mocked dependencies."""
    settings = get_settings()
    manager = FailoverManager(settings, mock_obs_controller, events_repo)
    yield manager
    # Cleanup - stop monitoring if running
    if manager._running:
        await manager.stop_monitoring()


@pytest.fixture
def stream_session():
    """Create test stream session."""
    return StreamSession(
        session_id=uuid4(),
        start_time=datetime.now(timezone.utc),
        end_time=None,
        total_duration_sec=0,
        downtime_duration_sec=0,
        avg_bitrate_kbps=0.0,
        avg_dropped_frames_pct=0.0,
        peak_cpu_usage_pct=0.0,
    )


# ===== T073: Content Failure Failover =====


@pytest.mark.asyncio
async def test_content_failure_triggers_failover(
    failover_manager: FailoverManager,
    mock_obs_controller: MagicMock,
    events_repo: EventsRepository,
    stream_session: StreamSession,
):
    """Test that content failure triggers failover scene within 5 seconds.

    Tests FR-025, FR-026, SC-005.
    """
    # Start monitoring
    await failover_manager.start_monitoring(stream_session)

    # Record start time
    start_time = datetime.now(timezone.utc)

    # Simulate content failure
    await failover_manager.handle_content_failure("Test content file not found")

    # Calculate transition time
    transition_time = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Verify failover scene was activated
    mock_obs_controller.switch_scene.assert_called_once_with("Failover")

    # Verify transition was within 5 seconds (SC-005)
    assert transition_time < 5.0, f"Failover took {transition_time}s, expected <5s"

    # Verify downtime event was recorded
    events = events_repo.get_by_session(stream_session.session_id)
    assert len(events) == 1
    assert events[0].failure_cause == FailureCause.CONTENT_FAILURE
    # Recovery action gets updated during failover activation
    assert "Switched to failover scene" in events[0].recovery_action or "Test content file not found" in events[0].recovery_action
    assert events[0].automatic_recovery is True

    await failover_manager.stop_monitoring()


@pytest.mark.asyncio
async def test_content_failure_logging(
    failover_manager: FailoverManager,
    events_repo: EventsRepository,
    stream_session: StreamSession,
):
    """Test that content failures are logged with diagnostic info.

    Tests FR-028.
    """
    await failover_manager.start_monitoring(stream_session)

    # Simulate content failure
    error_msg = "Media playback error: codec not supported"
    await failover_manager.handle_content_failure(error_msg)

    # Verify downtime event includes diagnostic info
    events = events_repo.get_by_session(stream_session.session_id)
    assert len(events) == 1
    event = events[0]

    # Check all required diagnostic fields
    assert event.event_id is not None
    assert event.stream_session_id == stream_session.session_id
    assert event.start_time is not None
    assert event.failure_cause == FailureCause.CONTENT_FAILURE
    # Recovery action gets updated during failover, so check it contains relevant info
    assert "failover" in event.recovery_action.lower() or "content" in event.recovery_action.lower()
    assert event.automatic_recovery is True

    await failover_manager.stop_monitoring()


# ===== T074: OBS Crash Recovery =====


@pytest.mark.asyncio
async def test_obs_crash_detection_and_reconnect(
    failover_manager: FailoverManager,
    mock_obs_controller: MagicMock,
    events_repo: EventsRepository,
    stream_session: StreamSession,
):
    """Test that OBS crash is detected and reconnection is attempted.

    Tests FR-027.
    """
    # Setup: OBS connection lost
    mock_obs_controller.is_connected.return_value = False
    mock_obs_controller.connect.return_value = AsyncMock()

    await failover_manager.start_monitoring(stream_session)

    # Wait for one monitoring cycle (15 seconds)
    await asyncio.sleep(16)

    # Verify reconnection was attempted
    mock_obs_controller.connect.assert_called()

    # Verify downtime event was recorded
    events = events_repo.get_by_session(stream_session.session_id)
    assert len(events) >= 1
    assert events[0].failure_cause == FailureCause.OBS_CRASH

    await failover_manager.stop_monitoring()


@pytest.mark.asyncio
async def test_obs_restart_max_attempts(
    failover_manager: FailoverManager,
    mock_obs_controller: MagicMock,
    stream_session: StreamSession,
):
    """Test that OBS restart attempts are limited to 3.

    Tests FR-027.
    """
    # Setup: OBS connection always fails
    mock_obs_controller.is_connected.return_value = False
    mock_obs_controller.connect.side_effect = OBSConnectionError("Connection refused")

    await failover_manager.start_monitoring(stream_session)

    # Trigger OBS crash detection multiple times
    for _ in range(4):
        await failover_manager._handle_obs_crash()

    # Verify connect was called max 3 times
    assert mock_obs_controller.connect.call_count == 3

    # Verify technical difficulties scene was activated after max attempts
    assert mock_obs_controller.switch_scene.call_count > 0
    # Last call should be to Technical Difficulties
    last_call = mock_obs_controller.switch_scene.call_args_list[-1]
    assert last_call[0][0] == "Technical Difficulties"

    await failover_manager.stop_monitoring()


# ===== T075: RTMP Reconnection =====


@pytest.mark.asyncio
async def test_rtmp_disconnect_detection(
    failover_manager: FailoverManager,
    mock_obs_controller: MagicMock,
    events_repo: EventsRepository,
    stream_session: StreamSession,
):
    """Test that RTMP disconnect is detected and logged.

    Tests FR-022.
    """
    # Setup: RTMP stream is inactive
    mock_obs_controller.get_streaming_status.return_value = {
        "active": False,
        "reconnecting": False
    }

    await failover_manager.start_monitoring(stream_session)

    # Wait for one monitoring cycle
    await asyncio.sleep(16)

    # Verify streaming restart was attempted
    mock_obs_controller.start_streaming.assert_called()

    # Verify downtime event was recorded
    events = events_repo.get_by_session(stream_session.session_id)
    assert len(events) >= 1
    assert events[0].failure_cause == FailureCause.CONNECTION_LOST

    await failover_manager.stop_monitoring()


@pytest.mark.asyncio
async def test_rtmp_auto_reconnecting(
    failover_manager: FailoverManager,
    mock_obs_controller: MagicMock,
    events_repo: EventsRepository,
    stream_session: StreamSession,
):
    """Test that OBS auto-reconnection is detected and logged.

    Tests FR-015.
    """
    # Setup: OBS is handling reconnection automatically
    mock_obs_controller.get_streaming_status.return_value = {
        "active": False,
        "reconnecting": True
    }

    await failover_manager.start_monitoring(stream_session)

    # Wait for one monitoring cycle
    await asyncio.sleep(16)

    # Verify manual restart was NOT attempted (OBS is handling it)
    mock_obs_controller.start_streaming.assert_not_called()

    # Verify downtime event was still recorded
    events = events_repo.get_by_session(stream_session.session_id)
    assert len(events) >= 1
    assert events[0].failure_cause == FailureCause.CONNECTION_LOST

    await failover_manager.stop_monitoring()


# ===== T076: Downtime Event Logging =====


@pytest.mark.asyncio
async def test_downtime_event_finalization(
    failover_manager: FailoverManager,
    mock_obs_controller: MagicMock,
    events_repo: EventsRepository,
    stream_session: StreamSession,
):
    """Test that downtime events are finalized with end time and duration.

    Tests FR-028.
    """
    await failover_manager.start_monitoring(stream_session)

    # Simulate content failure
    await failover_manager.handle_content_failure("Test failure")

    # Verify event was created
    events = events_repo.get_ongoing_events(stream_session.session_id)
    assert len(events) == 1
    assert events[0].is_ongoing

    # Simulate recovery by finalizing the event
    await failover_manager._finalize_downtime_event("Test recovery successful")

    # Verify event was finalized
    all_events = events_repo.get_by_session(stream_session.session_id)
    assert len(all_events) == 1
    event = all_events[0]

    assert event.end_time is not None
    assert not event.is_ongoing
    assert event.duration_sec > 0
    assert "Test recovery successful" in event.recovery_action

    await failover_manager.stop_monitoring()


@pytest.mark.asyncio
async def test_multiple_failure_types_logged(
    failover_manager: FailoverManager,
    mock_obs_controller: MagicMock,
    events_repo: EventsRepository,
    stream_session: StreamSession,
):
    """Test that different failure types are logged distinctly.

    Tests FR-028.
    """
    await failover_manager.start_monitoring(stream_session)

    # Simulate content failure
    await failover_manager.handle_content_failure("Content failure")
    await failover_manager._finalize_downtime_event("Content recovered")

    # Simulate OBS crash
    mock_obs_controller.is_connected.return_value = False
    await failover_manager._handle_obs_crash()
    await failover_manager._finalize_downtime_event("OBS recovered")

    # Verify both events were logged
    events = events_repo.get_by_session(stream_session.session_id)
    assert len(events) == 2

    # Verify different failure causes
    failure_causes = {event.failure_cause for event in events}
    assert FailureCause.CONTENT_FAILURE in failure_causes
    assert FailureCause.OBS_CRASH in failure_causes

    await failover_manager.stop_monitoring()


# ===== Edge Cases =====


@pytest.mark.asyncio
async def test_technical_difficulties_fallback(
    failover_manager: FailoverManager,
    mock_obs_controller: MagicMock,
    stream_session: StreamSession,
):
    """Test that technical difficulties scene is used when failover fails.

    Tests edge case: both primary and failover content fail.
    """
    # Setup: Failover scene switch fails
    mock_obs_controller.switch_scene.side_effect = [
        OBSConnectionError("Failover scene failed"),
        None  # Technical Difficulties succeeds
    ]

    await failover_manager.start_monitoring(stream_session)

    # Trigger failover
    await failover_manager._activate_failover("test", "Test recovery")

    # Verify technical difficulties was activated
    assert mock_obs_controller.switch_scene.call_count == 2
    last_call = mock_obs_controller.switch_scene.call_args_list[-1]
    assert last_call[0][0] == "Technical Difficulties"

    await failover_manager.stop_monitoring()


@pytest.mark.asyncio
async def test_stream_recovery_from_failover(
    failover_manager: FailoverManager,
    mock_obs_controller: MagicMock,
    stream_session: StreamSession,
):
    """Test that failover mode is cleared when stream recovers."""
    # Start with stream inactive and restart streaming fails
    mock_obs_controller.get_streaming_status.return_value = {
        "active": False,
        "reconnecting": False
    }
    # Make streaming restart fail to trigger failover activation
    mock_obs_controller.start_streaming.side_effect = OBSConnectionError("RTMP restart failed")

    await failover_manager.start_monitoring(stream_session)

    # Wait for failover to activate
    await asyncio.sleep(16)

    # Verify failover mode was activated due to restart failure
    assert failover_manager._in_failover_mode

    # Simulate stream recovery - streaming becomes active again
    mock_obs_controller.get_streaming_status.return_value = {
        "active": True,
        "reconnecting": False
    }
    # Reset the side effect so restart can succeed
    mock_obs_controller.start_streaming.side_effect = None

    # Wait for recovery detection
    await asyncio.sleep(16)

    # Verify failover mode was cleared
    assert not failover_manager._in_failover_mode

    await failover_manager.stop_monitoring()
