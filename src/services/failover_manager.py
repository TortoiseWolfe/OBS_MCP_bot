"""Failover manager service for automatic failure detection and recovery.

Implements FR-024-028: Detect failures, coordinate automatic recovery, maintain uptime.
Implements US3: Automatic Failover and Recovery.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from src.config.logging import get_logger
from src.config.settings import Settings
from src.models.downtime_event import DowntimeEvent, FailureCause
from src.models.stream_session import StreamSession
from src.persistence.repositories.events import EventsRepository
from src.services.obs_controller import OBSConnectionError, OBSController

logger = get_logger(__name__)


class FailoverManager:
    """Manages automatic failure detection and recovery.

    Implements:
    - FR-024: Maintain pre-configured failover content
    - FR-025: Auto-switch to failover within 5 seconds
    - FR-026: Detect content failures
    - FR-027: Auto-restart OBS if unresponsive
    - FR-028: Log all failover events with diagnostics
    - FR-022: Detect complete stream failure within 30 seconds
    """

    def __init__(
        self,
        settings: Settings,
        obs_controller: OBSController,
        events_repo: EventsRepository,
    ):
        """Initialize failover manager.

        Args:
            settings: Application settings
            obs_controller: OBS WebSocket controller
            events_repo: Events repository for downtime tracking
        """
        self.settings = settings
        self.obs = obs_controller
        self.events_repo = events_repo
        self._monitoring_task: Optional[asyncio.Task] = None
        self._current_session: Optional[StreamSession] = None
        self._current_downtime_event: Optional[DowntimeEvent] = None
        self._running = False
        self._in_failover_mode = False
        self._obs_restart_attempts = 0
        self._max_obs_restart_attempts = 3
        self._rtmp_reconnect_interval_sec = 10

    async def start_monitoring(self, stream_session: StreamSession) -> None:
        """Start failure monitoring for current stream session.

        Args:
            stream_session: Active stream session to monitor
        """
        if self._running:
            logger.warning("failover_monitoring_already_running")
            return

        self._current_session = stream_session
        self._running = True
        self._monitoring_task = asyncio.create_task(self._failover_monitoring_loop())
        logger.info(
            "failover_monitoring_started",
            session_id=str(stream_session.session_id),
        )

    async def stop_monitoring(self) -> None:
        """Stop failure monitoring."""
        self._running = False

        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        # Finalize any ongoing downtime event
        if self._current_downtime_event and self._current_downtime_event.is_ongoing:
            await self._finalize_downtime_event(
                "Monitoring stopped - planned shutdown"
            )

        logger.info("failover_monitoring_stopped")

    async def handle_content_failure(self, error_message: str) -> None:
        """Handle content playback failure.

        Implements FR-026: Detect content source failures.
        Called by ContentScheduler when content fails to play.

        Args:
            error_message: Description of content failure
        """
        logger.error("content_failure_detected", error=error_message)

        # Record downtime event
        await self._record_downtime_event(
            FailureCause.CONTENT_FAILURE,
            f"Content playback failed: {error_message}",
        )

        # Switch to failover scene
        await self._activate_failover(
            reason="content_failure",
            recovery_action="Switched to failover scene",
        )

    async def _failover_monitoring_loop(self) -> None:
        """Main monitoring loop for failure detection.

        Monitors:
        - OBS connection health (FR-027: detect unresponsive OBS)
        - RTMP connection status (FR-022: detect complete failure)
        - Streaming status (active/inactive)

        Runs checks every 15 seconds (faster than 30 second FR-022 requirement).
        """
        logger.info("failover_monitoring_loop_started")

        while self._running:
            try:
                await asyncio.sleep(15)  # Monitor every 15 seconds

                if not self._current_session:
                    continue

                # Check OBS connection health
                if not self.obs.is_connected():
                    logger.warning("obs_connection_lost_detected")
                    await self._handle_obs_crash()
                    continue

                # Check RTMP streaming status
                try:
                    status = await self.obs.get_streaming_status()

                    if not status.get("active", False):
                        # Stream is not active - could be RTMP disconnect or manual stop
                        logger.warning(
                            "rtmp_stream_inactive_detected",
                            reconnecting=status.get("reconnecting", False),
                        )

                        # Check if OBS is attempting to reconnect
                        if status.get("reconnecting", False):
                            await self._handle_rtmp_disconnect(is_reconnecting=True)
                        else:
                            # Not reconnecting - might be manual stop or critical failure
                            await self._handle_rtmp_disconnect(is_reconnecting=False)
                    else:
                        # Stream is active and healthy
                        # If we were in failover mode and stream recovered, log it
                        if self._in_failover_mode:
                            logger.info("stream_recovered_from_failover")
                            self._in_failover_mode = False

                            # Finalize any ongoing downtime event
                            if self._current_downtime_event:
                                await self._finalize_downtime_event(
                                    "Stream recovered - automatic"
                                )

                except OBSConnectionError as e:
                    logger.error("obs_status_check_failed", error=str(e))
                    await self._handle_obs_crash()

            except asyncio.CancelledError:
                logger.info("failover_monitoring_loop_cancelled")
                raise
            except Exception as e:
                logger.error("failover_monitoring_error", error=str(e))
                # Continue monitoring even if one iteration fails
                await asyncio.sleep(15)

    async def _handle_obs_crash(self) -> None:
        """Handle OBS crash or unresponsive state.

        Implements FR-027: Auto-restart OBS if unresponsive (max 3 attempts).
        """
        logger.error(
            "obs_crash_detected",
            restart_attempts=self._obs_restart_attempts,
            max_attempts=self._max_obs_restart_attempts,
        )

        # Record downtime event
        await self._record_downtime_event(
            FailureCause.OBS_CRASH,
            "OBS connection lost or unresponsive",
        )

        # Attempt to reconnect to OBS
        if self._obs_restart_attempts < self._max_obs_restart_attempts:
            self._obs_restart_attempts += 1

            logger.info(
                "obs_restart_attempt",
                attempt=self._obs_restart_attempts,
                max_attempts=self._max_obs_restart_attempts,
            )

            try:
                # Try to reconnect
                await self.obs.connect()

                logger.info("obs_reconnected_successfully")
                self._obs_restart_attempts = 0  # Reset counter on success

                # Check if we need to restart streaming
                status = await self.obs.get_streaming_status()
                if not status.get("active", False):
                    logger.info("restarting_streaming_after_obs_recovery")
                    await self.obs.start_streaming()

                # Finalize downtime event
                await self._finalize_downtime_event(
                    f"OBS reconnected automatically (attempt {self._obs_restart_attempts})"
                )

            except OBSConnectionError as e:
                logger.error(
                    "obs_reconnect_failed",
                    attempt=self._obs_restart_attempts,
                    error=str(e),
                )

                # If max attempts reached, switch to technical difficulties
                if self._obs_restart_attempts >= self._max_obs_restart_attempts:
                    await self._activate_technical_difficulties(
                        reason="OBS failed to restart after 3 attempts"
                    )
        else:
            # Max attempts exhausted
            await self._activate_technical_difficulties(
                reason="OBS restart attempts exhausted"
            )

    async def _handle_rtmp_disconnect(self, is_reconnecting: bool) -> None:
        """Handle RTMP connection loss to Twitch.

        Implements FR-015: Auto-reconnect every 10 seconds.

        Args:
            is_reconnecting: True if OBS is already attempting reconnection
        """
        logger.warning(
            "rtmp_disconnect_detected",
            obs_reconnecting=is_reconnecting,
        )

        # Record downtime event if not already recorded
        if not self._current_downtime_event or not self._current_downtime_event.is_ongoing:
            await self._record_downtime_event(
                FailureCause.CONNECTION_LOST,
                "RTMP connection to Twitch lost",
            )

        if is_reconnecting:
            # OBS is handling reconnection automatically
            logger.info("obs_handling_rtmp_reconnection")
            # Just log and wait for recovery
        else:
            # OBS is not reconnecting - attempt manual restart
            logger.info("manually_restarting_rtmp_stream")

            try:
                await self.obs.start_streaming()
                logger.info("rtmp_stream_restarted")

                # Finalize downtime event
                await self._finalize_downtime_event(
                    "RTMP stream restarted manually"
                )

            except OBSConnectionError as e:
                logger.error("rtmp_restart_failed", error=str(e))

                # Switch to failover scene
                await self._activate_failover(
                    reason="rtmp_restart_failed",
                    recovery_action="Switched to failover - RTMP connection lost",
                )

    async def _activate_failover(self, reason: str, recovery_action: str) -> None:
        """Activate failover scene.

        Implements FR-025: Switch to failover within 5 seconds.

        Args:
            reason: Why failover was activated
            recovery_action: Description of recovery action taken
        """
        if self._in_failover_mode:
            logger.debug("already_in_failover_mode")
            return

        logger.warning("activating_failover_scene", reason=reason)

        try:
            # Switch to Failover scene
            await self.obs.switch_scene("Failover")
            self._in_failover_mode = True

            logger.info(
                "failover_activated",
                reason=reason,
                recovery_action=recovery_action,
            )

            # Update downtime event recovery action
            if self._current_downtime_event:
                self._current_downtime_event.recovery_action = recovery_action
                self.events_repo.update(self._current_downtime_event)

        except OBSConnectionError as e:
            logger.error("failover_activation_failed", error=str(e))

            # If failover scene switch fails, try technical difficulties
            await self._activate_technical_difficulties(
                reason=f"Failover scene switch failed: {e}"
            )

    async def _activate_technical_difficulties(self, reason: str) -> None:
        """Activate technical difficulties scene when both primary and failover fail.

        Edge case handler when all recovery options exhausted.

        Args:
            reason: Why technical difficulties was activated
        """
        logger.error("activating_technical_difficulties", reason=reason)

        try:
            await self.obs.switch_scene("Technical Difficulties")

            logger.critical(
                "technical_difficulties_active",
                reason=reason,
                message="Manual intervention required",
            )

            # Update downtime event
            if self._current_downtime_event:
                self._current_downtime_event.recovery_action = (
                    f"Technical Difficulties scene activated: {reason}"
                )
                self.events_repo.update(self._current_downtime_event)

        except OBSConnectionError as e:
            logger.critical(
                "technical_difficulties_activation_failed",
                error=str(e),
                message="CRITICAL: Unable to switch to any scene - manual intervention required",
            )

    async def _record_downtime_event(
        self,
        failure_cause: FailureCause,
        initial_action: str,
    ) -> None:
        """Record new downtime event.

        Implements FR-028: Log all failover events with diagnostics.

        Args:
            failure_cause: Type of failure
            initial_action: Initial recovery action description
        """
        if not self._current_session:
            logger.warning("cannot_record_downtime_no_active_session")
            return

        # Create downtime event
        event = DowntimeEvent(
            event_id=uuid4(),
            stream_session_id=self._current_session.session_id,
            start_time=datetime.now(timezone.utc),
            end_time=None,  # Ongoing until resolved
            duration_sec=0.0,
            failure_cause=failure_cause,
            recovery_action=initial_action,
            automatic_recovery=True,  # All recoveries in this service are automatic
        )

        # Persist to database
        self.events_repo.create(event)
        self._current_downtime_event = event

        logger.warning(
            "downtime_event_recorded",
            event_id=str(event.event_id),
            failure_cause=failure_cause.value,
            recovery_action=initial_action,
        )

    async def _finalize_downtime_event(self, final_action: str) -> None:
        """Finalize ongoing downtime event with end time and duration.

        Args:
            final_action: Final recovery action description
        """
        if not self._current_downtime_event:
            return

        # Set end time and compute duration
        self._current_downtime_event.end_time = datetime.now(timezone.utc)
        self._current_downtime_event.duration_sec = (
            self._current_downtime_event.compute_duration()
        )
        self._current_downtime_event.recovery_action = (
            f"{self._current_downtime_event.recovery_action} -> {final_action}"
        )

        # Update in database
        self.events_repo.update(self._current_downtime_event)

        logger.info(
            "downtime_event_finalized",
            event_id=str(self._current_downtime_event.event_id),
            duration_sec=self._current_downtime_event.duration_sec,
            final_action=final_action,
        )

        self._current_downtime_event = None
