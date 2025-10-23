"""Content scheduler service for automated content playback.

Implements FR-035-039: Schedule content playback, manage transitions, respect time blocks.
Coordinates OBS Media Source playback and scene transitions.

Enhanced for Tier 3: Database-driven, time-aware content selection.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from obswebsocket import requests as obs_requests

from src.config.logging import get_logger
from src.config.settings import Settings
from src.models.content_library import AgeRating, ContentSource
from src.persistence.repositories.content_library import ContentSourceRepository
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
        content_source_repo: Optional[ContentSourceRepository] = None,
    ):
        """Initialize content scheduler.

        Args:
            settings: Application settings
            obs_controller: OBS WebSocket controller
            failover_manager: Optional failover manager for failure handling (US3 feature)
            content_source_repo: Optional content source repository for database-driven selection (Tier 3)
        """
        self.settings = settings
        self.obs = obs_controller
        self.failover_manager = failover_manager
        self.content_source_repo = content_source_repo
        self._content_loop_task: Optional[asyncio.Task] = None
        self._running = False
        self._paused = False  # For owner interrupt handling
        self._current_content_index = 0
        self._use_database = content_source_repo is not None  # Enable smart scheduling if repo available

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

        # Get available content (database-driven or filesystem fallback)
        if self._use_database:
            content_sources = self._select_content_for_current_time()
            if not content_sources:
                logger.warning("no_content_available_for_current_time_using_failover")
                if self.failover_manager:
                    await self.failover_manager.handle_content_failure(
                        "No content available for current time block"
                    )
                else:
                    await self.obs.switch_scene("Failover")
                return
            logger.info("content_selected_from_database", count=len(content_sources))
        else:
            # Fallback to filesystem discovery (MVP mode)
            content_files = self._discover_content()
            if not content_files:
                logger.warning("no_content_available_using_failover")
                if self.failover_manager:
                    await self.failover_manager.handle_content_failure(
                        "No content files found in content directory"
                    )
                else:
                    await self.obs.switch_scene("Failover")
                return
            logger.info("content_discovered_from_filesystem", count=len(content_files))

        while self._running:
            try:
                # Check if paused (owner interrupt)
                if self._paused:
                    logger.debug("content_scheduler_paused_waiting")
                    await asyncio.sleep(1)  # Wait while paused
                    continue

                # Get next content (database or filesystem)
                if self._use_database:
                    # Database-driven selection with actual metadata
                    content_source = content_sources[self._current_content_index % len(content_sources)]
                    self._current_content_index += 1

                    logger.info(
                        "content_playback_starting_db",
                        title=content_source.title,
                        source=content_source.source_attribution.value,
                        duration_sec=content_source.duration_sec,
                        time_blocks=content_source.time_blocks,
                    )

                    duration_sec = content_source.duration_sec
                    content_file_name = content_source.title

                    # Update the Content Player media source with the new video file
                    # Use SetInputSettings directly since the source already exists
                    ws = self.obs._ensure_connected()
                    ws.call(obs_requests.SetInputSettings(
                        inputName="Content Player",
                        inputSettings={
                            "local_file": content_source.windows_obs_path,
                            "looping": False,
                            "restart_on_activate": True,
                            "close_when_inactive": False,
                        },
                        overlay=False
                    ))

                    logger.info(
                        "content_player_updated",
                        file=content_source.windows_obs_path,
                        title=content_source.title
                    )

                    # Get canvas resolution and calculate optimal transform
                    canvas_width, canvas_height = await self.obs.get_canvas_resolution()
                    x_pos, y_pos, x_scale, y_scale = self.obs.calculate_video_transform(
                        video_width=content_source.width,
                        video_height=content_source.height,
                        canvas_width=canvas_width,
                        canvas_height=canvas_height
                    )

                    # Apply transform to scale and center video
                    await self.obs.set_source_transform(
                        scene_name="Automated Content",
                        source_name="Content Player",
                        x=x_pos,
                        y=y_pos,
                        scale_x=x_scale,
                        scale_y=y_scale
                    )

                    logger.info(
                        "content_player_scaled",
                        title=content_source.title,
                        resolution=f"{content_source.width}x{content_source.height}",
                        canvas=f"{canvas_width}x{canvas_height}",
                        scale=round(x_scale, 3)
                    )

                    # Update Content Credits text overlay
                    attribution_text = f"{content_source.title}\nSource: {content_source.source_attribution.value}"
                    ws.call(obs_requests.SetInputSettings(
                        inputName="Content Credits",
                        inputSettings={
                            "text": attribution_text,
                        },
                        overlay=True
                    ))

                    logger.info(
                        "attribution_updated",
                        title=content_source.title,
                        source=content_source.source_attribution.value
                    )

                else:
                    # Filesystem-based selection (MVP mode)
                    content_file = content_files[self._current_content_index % len(content_files)]
                    self._current_content_index += 1

                    logger.info(
                        "content_playback_starting_filesystem",
                        file=content_file.name,
                        index=self._current_content_index - 1,
                    )

                    duration_sec = self._estimate_duration(content_file)
                    content_file_name = content_file.name

                # Switch to Automated Content scene
                await self.obs.switch_scene("Automated Content")

                logger.info(
                    "content_playing",
                    file=content_file_name,
                    duration_sec=duration_sec,
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

    def _get_current_time_block(self) -> Optional[str]:
        """Determine current time block based on current time.

        Maps current hour and day to time block names.

        Returns:
            Time block name or None if no specific block matches
        """
        now = datetime.now(timezone.utc)
        hour = now.hour
        weekday = now.weekday()  # 0 = Monday, 6 = Sunday

        # Kids After School: 15:00-18:00 (3 PM - 6 PM), Monday-Friday
        if weekday < 5 and 15 <= hour < 18:
            return "after_school_kids"

        # Professional Hours: 09:00-15:00 (9 AM - 3 PM), Monday-Friday
        if weekday < 5 and 9 <= hour < 15:
            return "professional_hours"

        # Evening Mixed: 19:00-22:00 (7 PM - 10 PM), Every day
        if 19 <= hour < 22:
            return "evening_mixed"

        # Default to general content outside specific time blocks
        return "general"

    def _get_age_rating_for_time_block(self, time_block: str) -> AgeRating:
        """Map time block to appropriate age rating.

        Args:
            time_block: Time block name

        Returns:
            AgeRating enum
        """
        age_mapping = {
            "after_school_kids": AgeRating.KIDS,
            "professional_hours": AgeRating.ADULT,
            "evening_mixed": AgeRating.ALL,
            "general": AgeRating.ALL,
            "failover": AgeRating.ALL,
        }
        return age_mapping.get(time_block, AgeRating.ALL)

    def _select_content_for_current_time(self) -> List[ContentSource]:
        """Select appropriate content for current time block (Tier 3 enhancement).

        Implements time-aware, priority-ordered content selection using database.

        Returns:
            List of ContentSource entities appropriate for current time
        """
        if not self.content_source_repo:
            logger.error("content_source_repo_not_initialized")
            return []

        # Get current time block
        current_time_block = self._get_current_time_block()
        required_age_rating = self._get_age_rating_for_time_block(current_time_block)

        logger.info(
            "selecting_content_for_time_block",
            time_block=current_time_block,
            age_rating=required_age_rating.value,
        )

        # Query all content from database
        all_content = self.content_source_repo.list_all()

        if not all_content:
            logger.warning("no_content_in_database")
            return []

        # Filter by time block and age rating
        matching_content = []

        for content in all_content:
            # Check if content is allowed in current time block
            if current_time_block in content.time_blocks:
                # Check age appropriateness
                if self._is_age_appropriate(content.age_rating, required_age_rating):
                    matching_content.append(content)

        # If no content matches current time block, fall back to general content
        if not matching_content:
            logger.info(
                "no_content_for_time_block_using_general",
                time_block=current_time_block,
            )

            for content in all_content:
                if "general" in content.time_blocks:
                    if self._is_age_appropriate(content.age_rating, required_age_rating):
                        matching_content.append(content)

        # Sort by priority (1 = highest priority)
        matching_content.sort(key=lambda c: c.priority)

        logger.info(
            "content_selection_complete",
            matched=len(matching_content),
            time_block=current_time_block,
        )

        return matching_content

    def _is_age_appropriate(self, content_age: AgeRating, required_age: AgeRating) -> bool:
        """Check if content age rating matches required age rating for time block.

        Args:
            content_age: Content's age rating
            required_age: Required age rating for current time block

        Returns:
            True if content is appropriate for time block
        """
        # ALL content is always appropriate
        if content_age == AgeRating.ALL:
            return True

        # KIDS content is appropriate for KIDS time blocks only
        if content_age == AgeRating.KIDS and required_age == AgeRating.KIDS:
            return True

        # ADULT content is appropriate for ADULT and ALL time blocks
        if content_age == AgeRating.ADULT and required_age in (AgeRating.ADULT, AgeRating.ALL):
            return True

        return False

    def _discover_content(self) -> List[Path]:
        """Discover available content files (filesystem fallback for MVP mode).

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
