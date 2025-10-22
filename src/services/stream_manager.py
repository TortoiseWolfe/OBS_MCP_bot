"""Stream manager service for streaming orchestration.

Implements FR-009-018: Start/stop streaming, maintain RTMP connection, monitor status.
Coordinates OBS streaming operations and session tracking.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.config.logging import get_logger
from src.config.settings import Settings
from src.models.init_state import SystemInitializationState
from src.models.owner_session import OwnerSession, TriggerMethod
from src.models.stream_session import StreamSession
from src.persistence.repositories.sessions import SessionsRepository
from src.services.obs_controller import OBSConnectionError, OBSController

# Optional US2 imports
try:
    from src.persistence.repositories.owner_sessions import OwnerSessionsRepository
    from src.services.content_scheduler import ContentScheduler
except ImportError:
    OwnerSessionsRepository = None  # type: ignore
    ContentScheduler = None  # type: ignore

logger = get_logger(__name__)


class StreamManager:
    """Manages streaming lifecycle and session tracking.

    Implements:
    - FR-010: Auto-start streaming after pre-flight validation passes
    - FR-014: Streaming state monitoring
    - FR-015: Start streaming operations
    - FR-017: Stream session tracking
    """

    def __init__(
        self,
        settings: Settings,
        obs_controller: OBSController,
        sessions_repo: SessionsRepository,
        owner_sessions_repo: Optional["OwnerSessionsRepository"] = None,
        content_scheduler: Optional["ContentScheduler"] = None,
    ):
        """Initialize stream manager.

        Args:
            settings: Application settings
            obs_controller: OBS WebSocket controller
            sessions_repo: Sessions repository for persistence
            owner_sessions_repo: Optional owner sessions repository (US2 feature)
            content_scheduler: Optional content scheduler for pause/resume on owner interrupt
        """
        self.settings = settings
        self.obs = obs_controller
        self.sessions_repo = sessions_repo
        self.owner_sessions_repo = owner_sessions_repo
        self.content_scheduler = content_scheduler
        self._current_session: Optional[StreamSession] = None
        self._current_owner_session: Optional[OwnerSession] = None
        self._monitoring_task: Optional[asyncio.Task] = None

    async def auto_start_streaming(
        self,
        init_state: SystemInitializationState
    ) -> StreamSession:
        """Auto-start streaming after successful pre-flight validation.

        Implements FR-010: Auto-start within 60 seconds of startup.
        Implements FR-032: Automatic streaming start after pre-flight pass.

        Args:
            init_state: Pre-flight validation results

        Returns:
            Created StreamSession

        Raises:
            OBSConnectionError: If streaming fails to start
        """
        logger.info("auto_start_streaming_initiated", init_id=str(init_state.init_id))

        try:
            # Start streaming via OBS
            await self.obs.start_streaming()

            # Create stream session
            session = StreamSession(
                session_id=uuid4(),
                start_time=datetime.now(timezone.utc),
                end_time=None,
                total_duration_sec=0,
                downtime_duration_sec=0,
                avg_bitrate_kbps=0.0,
                avg_dropped_frames_pct=0.0,
                peak_cpu_usage_pct=0.0,
            )

            # Persist session
            self.sessions_repo.create_stream_session(session)
            self._current_session = session

            # Update init state with stream start timestamp
            init_state.stream_started_at = session.start_time

            logger.info(
                "streaming_auto_started",
                session_id=str(session.session_id),
                start_time=session.start_time.isoformat(),
            )

            # Start background monitoring
            await self._start_monitoring()

            return session

        except OBSConnectionError as e:
            logger.error("auto_start_streaming_failed", error=str(e))
            raise

    async def start_streaming(self) -> StreamSession:
        """Manually start streaming (for non-auto-start scenarios).

        Returns:
            Created StreamSession

        Raises:
            OBSConnectionError: If streaming fails to start
            ValueError: If stream key is not configured
        """
        logger.info("manual_start_streaming_initiated")

        # T072: Validate stream key is configured
        if not self.settings.twitch.stream_key or len(self.settings.twitch.stream_key.strip()) == 0:
            raise ValueError("TWITCH_STREAM_KEY is not configured - cannot start streaming")

        try:
            await self.obs.start_streaming()

            session = StreamSession(
                session_id=uuid4(),
                start_time=datetime.now(timezone.utc),
                end_time=None,
                total_duration_sec=0,
                downtime_duration_sec=0,
                avg_bitrate_kbps=0.0,
                avg_dropped_frames_pct=0.0,
                peak_cpu_usage_pct=0.0,
            )

            self.sessions_repo.create_stream_session(session)
            self._current_session = session

            logger.info(
                "streaming_started",
                session_id=str(session.session_id),
                start_time=session.start_time.isoformat(),
            )

            await self._start_monitoring()

            return session

        except OBSConnectionError as e:
            logger.error("start_streaming_failed", error=str(e))
            raise

    async def stop_streaming(self) -> None:
        """Stop streaming and finalize current session.

        Implements FR-046: Graceful streaming stop.
        """
        logger.info("stop_streaming_initiated")

        try:
            # Stop background monitoring
            await self._stop_monitoring()

            # Stop OBS streaming
            await self.obs.stop_streaming()

            # Finalize current session
            if self._current_session:
                await self._finalize_session()

            logger.info("streaming_stopped")

        except OBSConnectionError as e:
            logger.error("stop_streaming_failed", error=str(e))
            raise

    async def get_current_session(self) -> Optional[StreamSession]:
        """Get the current active stream session.

        Returns:
            Current StreamSession if streaming, None otherwise
        """
        return self._current_session

    async def _start_monitoring(self) -> None:
        """Start background task to monitor stream health.

        Implements FR-014: Streaming state monitoring.
        """
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitor_stream_health())
            logger.info("stream_monitoring_started")

    async def _stop_monitoring(self) -> None:
        """Stop background monitoring task."""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("stream_monitoring_stopped")

    async def _monitor_stream_health(self) -> None:
        """Background task to monitor stream health and update session.

        Monitors streaming status every 10 seconds and updates session metrics.
        Implements FR-014, FR-017.
        """
        logger.info("stream_health_monitoring_loop_started")

        while True:
            try:
                await asyncio.sleep(10)  # Monitor every 10 seconds per FR-019

                if not self._current_session:
                    continue

                # Get streaming status
                status = await self.obs.get_streaming_status()
                streaming_active = status.get("active", False)

                # T071: Detect manual stream stop and auto-restart
                if not streaming_active:
                    logger.warning(
                        "stream_stopped_detected",
                        session_id=str(self._current_session.session_id),
                        message="Streaming stopped manually, auto-restarting in 10 seconds"
                    )
                    await asyncio.sleep(10)
                    try:
                        await self.obs.start_streaming()
                        logger.info("stream_auto_restarted_after_manual_stop")
                        continue  # Skip this iteration, will verify on next check
                    except OBSConnectionError as e:
                        logger.error("stream_auto_restart_failed", error=str(e))
                        # Continue monitoring even if restart fails

                # Get OBS stats
                stats = await self.obs.get_stats()

                # Update session duration
                elapsed = (datetime.now(timezone.utc) - self._current_session.start_time).total_seconds()
                self._current_session.total_duration_sec = int(elapsed)

                # Update session metrics (simple averaging for now)
                # TODO: Implement proper metric aggregation from health_metrics table

                # Persist updated session
                self.sessions_repo.update_stream_session(self._current_session)

                logger.debug(
                    "stream_health_updated",
                    session_id=str(self._current_session.session_id),
                    duration_sec=self._current_session.total_duration_sec,
                    streaming_active=streaming_active,
                )

            except asyncio.CancelledError:
                logger.info("stream_health_monitoring_cancelled")
                raise
            except Exception as e:
                logger.error("stream_health_monitoring_error", error=str(e))
                # Continue monitoring even if one iteration fails
                await asyncio.sleep(10)

    async def _finalize_session(self) -> None:
        """Finalize current stream session with end time and final metrics.

        Implements FR-017: Stream session tracking.
        """
        if not self._current_session:
            return

        try:
            # Set end time
            self._current_session.end_time = datetime.now(timezone.utc)

            # Calculate final duration
            elapsed = (self._current_session.end_time - self._current_session.start_time).total_seconds()
            self._current_session.total_duration_sec = int(elapsed)

            # Persist final session state
            self.sessions_repo.update_stream_session(self._current_session)

            logger.info(
                "stream_session_finalized",
                session_id=str(self._current_session.session_id),
                duration_sec=self._current_session.total_duration_sec,
                uptime_percentage=self._current_session.uptime_percentage,
            )

            self._current_session = None

        except Exception as e:
            logger.error("session_finalization_error", error=str(e))

    async def handle_owner_goes_live(
        self,
        interrupted_scene: str,
        transition_time_sec: float,
        trigger_method: TriggerMethod,
    ) -> None:
        """Handle owner interrupt - owner wants to take over the stream.

        Implements FR-031: Transition to owner live within 10 seconds.
        Called by OwnerDetector when owner switches to "Owner Live" scene.

        Args:
            interrupted_scene: Scene that was active before owner took over
            transition_time_sec: Time taken to detect and transition
            trigger_method: How owner triggered the interrupt (HOTKEY or SCENE_CHANGE)
        """
        if not self.owner_sessions_repo:
            logger.warning("owner_interrupt_ignored_no_repository")
            return

        if not self._current_session:
            logger.warning("owner_interrupt_ignored_no_active_stream")
            return

        try:
            # Create owner session
            owner_session = OwnerSession(
                session_id=uuid4(),
                stream_session_id=self._current_session.session_id,
                start_time=datetime.now(timezone.utc),
                end_time=None,
                duration_sec=0,
                content_interrupted=interrupted_scene,
                resume_content=None,  # Will be set when owner returns
                transition_time_sec=transition_time_sec,
                trigger_method=trigger_method,
            )

            # Persist owner session
            await self.owner_sessions_repo.create_owner_session(owner_session)
            self._current_owner_session = owner_session

            # Pause content scheduler if available
            if self.content_scheduler:
                await self.content_scheduler.pause()

            logger.info(
                "owner_interrupt_started",
                owner_session_id=str(owner_session.session_id),
                stream_session_id=str(self._current_session.session_id),
                interrupted_scene=interrupted_scene,
                transition_time_sec=transition_time_sec,
                trigger_method=trigger_method.value,
            )

        except Exception as e:
            logger.error("owner_interrupt_handling_error", error=str(e))
            raise

    async def handle_owner_returns(self, owner_scene: str) -> None:
        """Handle owner return - owner returning to automated mode.

        Implements FR-034: Resume automated programming within 10 seconds.
        Called by OwnerDetector when owner switches away from "Owner Live".

        Args:
            owner_scene: Scene owner was using (typically "Owner Live")
        """
        if not self.owner_sessions_repo:
            logger.warning("owner_return_ignored_no_repository")
            return

        if not self._current_owner_session:
            logger.warning("owner_return_ignored_no_active_owner_session")
            return

        try:
            # Finalize owner session
            self._current_owner_session.end_time = datetime.now(timezone.utc)
            elapsed = (
                self._current_owner_session.end_time
                - self._current_owner_session.start_time
            ).total_seconds()
            self._current_owner_session.duration_sec = int(elapsed)

            # Update in database
            await self.owner_sessions_repo.update_owner_session(self._current_owner_session)

            # Resume content scheduler if available
            if self.content_scheduler:
                await self.content_scheduler.resume()

            logger.info(
                "owner_interrupt_ended",
                owner_session_id=str(self._current_owner_session.session_id),
                duration_sec=self._current_owner_session.duration_sec,
            )

            self._current_owner_session = None

        except Exception as e:
            logger.error("owner_return_handling_error", error=str(e))
            raise
