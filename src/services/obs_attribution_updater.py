"""OBS Attribution Updater Service.

Handles automatic attribution text updates in OBS for content library management.
Ensures proper Creative Commons license compliance during streaming.
"""

import asyncio
import structlog
from typing import Optional
from ..models.content_source import ContentSource
from .obs_controller import OBSController, OBSConnectionError

logger = structlog.get_logger()


class AttributionUpdateError(Exception):
    """Raised when attribution text update fails."""
    pass


class OBSAttributionUpdater:
    """Service for managing OBS attribution text overlays.

    Implements User Story 5: OBS Integration and Attribution Updates.
    Automatically updates text source overlays with proper CC license attribution
    during content playback.

    Attributes:
        obs_controller: OBS WebSocket controller instance
        text_source_name: Name of the OBS text source for attribution
        update_timeout: Maximum time allowed for text updates (seconds)
    """

    DEFAULT_TEXT_SOURCE_NAME = "Content Attribution"
    DEFAULT_UPDATE_TIMEOUT = 1.0  # seconds (SC-013: <1 second requirement)

    def __init__(
        self,
        obs_controller: OBSController,
        text_source_name: str = DEFAULT_TEXT_SOURCE_NAME,
        update_timeout: float = DEFAULT_UPDATE_TIMEOUT
    ):
        """Initialize OBS attribution updater.

        Args:
            obs_controller: Connected OBS controller instance
            text_source_name: Name of text source in OBS for attribution
            update_timeout: Maximum seconds to wait for text update
        """
        self.obs_controller = obs_controller
        self.text_source_name = text_source_name
        self.update_timeout = update_timeout

        logger.info(
            "obs_attribution_updater_initialized",
            text_source=text_source_name,
            timeout_sec=update_timeout
        )

    def format_attribution_text(
        self,
        content_source: Optional[ContentSource] = None,
        source_name: Optional[str] = None,
        course_name: Optional[str] = None,
        title: Optional[str] = None,
        license_type: Optional[str] = None
    ) -> str:
        """Format attribution text for OBS display.

        Generates standardized attribution text in the format:
        "{source} {course}: {title} - {license}"

        Examples:
            "MIT OCW 6.0001: What is Computation? - CC BY-NC-SA 4.0"
            "Harvard CS50: Introduction - CC BY-NC-SA 4.0"
            "Khan Academy: Intro to JavaScript - CC BY-NC-SA"

        Args:
            content_source: ContentSource entity (if provided, overrides other params)
            source_name: Content source name (e.g., "MIT OCW")
            course_name: Course identifier (e.g., "6.0001")
            title: Video title (e.g., "What is Computation?")
            license_type: License string (e.g., "CC BY-NC-SA 4.0")

        Returns:
            Formatted attribution text string
        """
        # Extract from ContentSource if provided
        if content_source:
            source_attribution = content_source.source_attribution or "Unknown Source"
            title = content_source.title or "Untitled"
            license_type = content_source.license_type or "Unknown License"

            # Parse source attribution (e.g., "MIT OpenCourseWare 6.0001")
            parts = source_attribution.split()
            if len(parts) >= 2:
                source_name = " ".join(parts[:-1])  # "MIT OpenCourseWare"
                course_name = parts[-1]  # "6.0001"
            else:
                source_name = source_attribution
                course_name = ""

        # Build attribution text
        components = []

        if source_name:
            if course_name:
                components.append(f"{source_name} {course_name}")
            else:
                components.append(source_name)

        if title:
            components.append(title)

        # Join with colon separator
        text = ": ".join(components) if len(components) > 1 else components[0] if components else ""

        # Add license suffix
        if license_type:
            text = f"{text} - {license_type}" if text else license_type

        logger.debug(
            "attribution_text_formatted",
            text_length=len(text),
            source=source_name,
            title=title
        )

        return text or "Educational Content - CC Licensed"

    async def verify_text_source_exists(
        self,
        current_scene: Optional[str] = None
    ) -> bool:
        """Verify that the attribution text source exists in OBS.

        Checks if the configured text source is present in the current scene.
        Used for pre-flight validation during orchestrator startup.

        Args:
            current_scene: Scene to check (defaults to current active scene)

        Returns:
            True if text source exists and is accessible, False otherwise

        Raises:
            OBSConnectionError: If OBS connection fails during check
        """
        try:
            # Get current scene if not specified
            if not current_scene:
                current_scene = await self.obs_controller.get_current_scene()

            # Try to get source settings to verify existence
            # This will raise an exception if source doesn't exist
            ws = self.obs_controller._ensure_connected()

            try:
                # Attempt to get input settings for the text source
                # If it exists, this will succeed; if not, it will raise
                from obswebsocket import requests as obs_requests
                ws.call(obs_requests.GetInputSettings(inputName=self.text_source_name))

                logger.info(
                    "text_source_verified",
                    source=self.text_source_name,
                    scene=current_scene
                )
                return True

            except Exception as e:
                logger.warning(
                    "text_source_not_found",
                    source=self.text_source_name,
                    scene=current_scene,
                    error=str(e)
                )
                return False

        except OBSConnectionError as e:
            logger.error(
                "text_source_verification_failed",
                source=self.text_source_name,
                error=str(e)
            )
            raise

    async def update_attribution(
        self,
        content_source: ContentSource,
        timeout: Optional[float] = None
    ) -> None:
        """Update OBS attribution text overlay for current content.

        Updates the text source with formatted attribution information.
        Respects SC-013 requirement: <1 second update time.

        Args:
            content_source: ContentSource entity with attribution metadata
            timeout: Custom timeout in seconds (defaults to instance timeout)

        Raises:
            AttributionUpdateError: If text update fails or times out
            OBSConnectionError: If OBS connection is unavailable
        """
        timeout = timeout or self.update_timeout

        try:
            # Format attribution text
            attribution_text = self.format_attribution_text(content_source)

            logger.info(
                "updating_attribution",
                source=self.text_source_name,
                content_title=content_source.title,
                timeout_sec=timeout
            )

            # Update text with timeout
            try:
                await asyncio.wait_for(
                    self.obs_controller.update_text_content(
                        source_name=self.text_source_name,
                        text=attribution_text
                    ),
                    timeout=timeout
                )

                logger.info(
                    "attribution_updated",
                    source=self.text_source_name,
                    content_source=content_source.source_attribution,
                    text_length=len(attribution_text)
                )

            except asyncio.TimeoutError:
                logger.error(
                    "attribution_update_timeout",
                    source=self.text_source_name,
                    timeout_sec=timeout
                )
                raise AttributionUpdateError(
                    f"Attribution update timed out after {timeout}s"
                )

        except OBSConnectionError as e:
            logger.error(
                "attribution_update_obs_error",
                source=self.text_source_name,
                error=str(e)
            )
            raise AttributionUpdateError(f"OBS connection error: {e}") from e

        except Exception as e:
            logger.error(
                "attribution_update_failed",
                source=self.text_source_name,
                error=str(e)
            )
            raise AttributionUpdateError(f"Failed to update attribution: {e}") from e

    async def clear_attribution(self) -> None:
        """Clear attribution text overlay (e.g., during failover).

        Sets text to empty or default message.

        Raises:
            AttributionUpdateError: If text clear fails
        """
        try:
            await self.obs_controller.update_text_content(
                source_name=self.text_source_name,
                text=""  # Clear text
            )

            logger.info("attribution_cleared", source=self.text_source_name)

        except OBSConnectionError as e:
            raise AttributionUpdateError(f"Failed to clear attribution: {e}") from e
