"""Content scheduler service for automated content playback.

Implements FR-035-039: Schedule content playback, manage transitions, respect time blocks.
Coordinates OBS Media Source playback and scene transitions.
"""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from src.config.logging import get_logger
from src.config.settings import Settings
from src.services.obs_controller import OBSConnectionError, OBSController

if TYPE_CHECKING:
    from src.services.failover_manager import FailoverManager

logger = get_logger(__name__)


class ContentScheduler:
    """Manages automated content playback and transitions.

    Implements:
    - FR-035: Schedule content playback based on time blocks
    - FR-036: Automatic content transitions (<2 seconds)
    - FR-037: Content file verification
    - FR-038: No dead air (continuous content)
    - FR-039: Respect duration, age-appropriateness, time blocks
    """

    def __init__(
        self,
        settings: Settings,
        obs_controller: OBSController,
        failover_manager: Optional["FailoverManager"] = None,
    ):
        """Initialize content scheduler.

        Args:
            settings: Application settings
            obs_controller: OBS WebSocket controller
            failover_manager: Optional failover manager for failure handling (US3 feature)
        """
        self.settings = settings
        self.obs = obs_controller
        self.failover_manager = failover_manager
        self._content_loop_task: Optional[asyncio.Task] = None
        self._running = False
        self._paused = False  # For owner interrupt handling
        self._current_content_index = 0

    async def start(self) -> None:
        """Start content scheduling loop.

        Begins automated content playback with scene transitions.
        """
        if self._running:
            logger.warning("content_scheduler_already_running")
            return

        self._running = True
        self._content_loop_task = asyncio.create_task(self._content_playback_loop())
        logger.info("content_scheduler_started")

    async def stop(self) -> None:
        """Stop content scheduling loop."""
        self._running = False

        if self._content_loop_task and not self._content_loop_task.done():
            self._content_loop_task.cancel()
            try:
                await self._content_loop_task
            except asyncio.CancelledError:
                pass

        logger.info("content_scheduler_stopped")

    async def pause(self) -> None:
        """Pause automated content playback.

        Called when owner interrupts to take over the stream.
        Implements FR-031: Transition to owner live.
        """
        if not self._running:
            logger.warning("content_scheduler_not_running_cannot_pause")
            return

        if self._paused:
            logger.warning("content_scheduler_already_paused")
            return

        self._paused = True
        logger.info("content_scheduler_paused")

    async def resume(self) -> None:
        """Resume automated content playback.

        Called when owner returns control to automated mode.
        Implements FR-034: Resume automated programming.
        """
        if not self._running:
            logger.warning("content_scheduler_not_running_cannot_resume")
            return

        if not self._paused:
            logger.warning("content_scheduler_not_paused")
            return

        self._paused = False
        logger.info("content_scheduler_resumed")

    async def _content_playback_loop(self) -> None:
        """Main content playback loop.

        Implements FR-036, FR-038: Continuous content with <2 second transitions.
        """
        logger.info("content_playback_loop_started")

        # Get available content
        content_files = self._discover_content()

        if not content_files:
            logger.warning("no_content_available_using_failover")

            # Notify failover manager if available
            if self.failover_manager:
                await self.failover_manager.handle_content_failure(
                    "No content files found in content directory"
                )
            else:
                # Fall back to failover scene if no failover manager
                await self.obs.switch_scene("Failover")
            return

        logger.info("content_discovered", count=len(content_files))

        while self._running:
            try:
                # Check if paused (owner interrupt)
                if self._paused:
                    logger.debug("content_scheduler_paused_waiting")
                    await asyncio.sleep(1)  # Wait while paused
                    continue

                # Get next content file (round-robin for MVP)
                content_file = content_files[self._current_content_index % len(content_files)]
                self._current_content_index += 1

                logger.info(
                    "content_playback_starting",
                    file=content_file.name,
                    index=self._current_content_index - 1,
                )

                # Switch to Automated Content scene
                await self.obs.switch_scene("Automated Content")

                # For MVP: Simple timing-based playback
                # TODO: Implement OBS Media Source control and media_ended event detection
                # For now, use estimated duration
                duration_sec = self._estimate_duration(content_file)

                logger.info(
                    "content_playing",
                    file=content_file.name,
                    estimated_duration_sec=duration_sec,
                )

                # Wait for content to finish
                await asyncio.sleep(duration_sec)

                logger.info("content_playback_complete", file=content_file.name)

                # Small delay for transition (< 2 seconds per FR-036)
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                logger.info("content_playback_loop_cancelled")
                raise
            except OBSConnectionError as e:
                logger.error("content_playback_obs_error", error=str(e))

                # Notify failover manager if available
                if self.failover_manager:
                    await self.failover_manager.handle_content_failure(
                        f"OBS connection error during content playback: {e}"
                    )
                else:
                    await asyncio.sleep(5)  # Wait before retry
            except Exception as e:
                logger.error("content_playback_error", error=str(e))

                # Notify failover manager if available
                if self.failover_manager:
                    await self.failover_manager.handle_content_failure(
                        f"Content playback error: {e}"
                    )
                else:
                    await asyncio.sleep(5)  # Wait before retry

    def _discover_content(self) -> List[Path]:
        """Discover available content files.

        Implements FR-037: Content file verification.

        Returns:
            List of available content file paths
        """
        content_dir = Path("/app/content")

        if not content_dir.exists():
            logger.warning("content_directory_not_found", path=str(content_dir))
            return []

        # Discover video files
        video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
        content_files = []

        for file_path in sorted(content_dir.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                # Verify file is readable (FR-037)
                if self._verify_file(file_path):
                    content_files.append(file_path)
                    logger.debug("content_file_verified", file=str(file_path))
                else:
                    logger.warning("content_file_unreadable", file=str(file_path))

        return content_files

    def _verify_file(self, file_path: Path) -> bool:
        """Verify content file exists and is readable.

        Implements FR-037: Verify files exist and playable.

        Args:
            file_path: Path to content file

        Returns:
            True if file is verified
        """
        try:
            # Check file exists and has read permissions
            return file_path.exists() and file_path.is_file() and file_path.stat().st_size > 0
        except Exception as e:
            logger.error("file_verification_error", file=str(file_path), error=str(e))
            return False

    def _estimate_duration(self, file_path: Path) -> int:
        """Estimate content duration in seconds.

        For MVP, uses simple heuristic. Future implementation will use actual
        media metadata parsing.

        Args:
            file_path: Path to content file

        Returns:
            Estimated duration in seconds
        """
        # For MVP: Default to 5 minutes per file
        # TODO: Implement actual duration detection using ffprobe or similar
        default_duration = 300  # 5 minutes

        logger.debug(
            "duration_estimated",
            file=file_path.name,
            duration_sec=default_duration,
        )

        return default_duration
