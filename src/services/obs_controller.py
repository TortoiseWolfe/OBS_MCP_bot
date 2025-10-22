"""OBS Studio WebSocket controller for programmatic control.

Implements FR-001 through FR-008: OBS scene management, streaming control,
and connection monitoring using obs-websocket protocol v5.x.
"""

import asyncio
from typing import Any

from obswebsocket import obsws, requests as obs_requests
from obswebsocket.exceptions import ConnectionFailure, MessageTimeout

from src.config.logging import get_logger
from src.config.settings import OBSSettings

logger = get_logger(__name__)


class OBSConnectionError(Exception):
    """Raised when OBS connection fails or is lost."""

    pass


class OBSController:
    """Controls OBS Studio via WebSocket protocol.

    Provides programmatic control over scenes, sources, and streaming state.
    Implements automatic reconnection and error recovery per FR-027.
    """

    def __init__(self, settings: OBSSettings):
        """Initialize OBS controller.

        Args:
            settings: OBS connection configuration
        """
        self.settings = settings
        self._ws: obsws | None = None
        self._connected: bool = False
        self._reconnect_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Establish WebSocket connection to OBS.

        Implements FR-001: Initial OBS connection with retry logic.

        Raises:
            OBSConnectionError: If connection fails after retries
        """
        # Parse websocket URL
        host, port = self._parse_websocket_url(self.settings.websocket_url)

        attempts = 0
        max_attempts = self.settings.max_reconnect_attempts

        while attempts < max_attempts or max_attempts == 0:
            try:
                self._ws = obsws(
                    host=host,
                    port=port,
                    password=self.settings.password,
                    timeout=self.settings.connection_timeout_sec,
                )
                self._ws.connect()
                self._connected = True

                # Get OBS version info for logging (handle version API differences)
                try:
                    version_info = self._ws.call(obs_requests.GetVersion())
                    obs_version = version_info.getObsVersion() if hasattr(version_info, 'getObsVersion') else "unknown"
                    logger.info(
                        "obs_connected",
                        host=host,
                        port=port,
                        obs_version=obs_version,
                    )
                except Exception as e:
                    logger.info(
                        "obs_connected",
                        host=host,
                        port=port,
                        version_info_error=str(e),
                    )
                return

            except (ConnectionFailure, ConnectionRefusedError) as e:
                attempts += 1
                logger.warning(
                    "obs_connection_failed",
                    attempt=attempts,
                    max_attempts=max_attempts if max_attempts > 0 else "infinite",
                    error=str(e),
                )

                if max_attempts > 0 and attempts >= max_attempts:
                    raise OBSConnectionError(
                        f"Failed to connect to OBS after {attempts} attempts"
                    ) from e

                # Wait before retry
                await asyncio.sleep(self.settings.reconnect_interval_sec)

    async def disconnect(self) -> None:
        """Gracefully close OBS WebSocket connection.

        Implements clean shutdown per FR-046.
        """
        if self._ws:
            try:
                self._ws.disconnect()
                self._connected = False
                logger.info("obs_disconnected")
            except Exception as e:
                logger.warning("obs_disconnect_error", error=str(e))

    def is_connected(self) -> bool:
        """Check if currently connected to OBS.

        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._ws is not None

    async def list_scenes(self) -> list[str]:
        """Get list of all scene names in OBS.

        Implements FR-003: Scene enumeration.

        Returns:
            List of scene names

        Raises:
            OBSConnectionError: If not connected to OBS
        """
        ws = self._ensure_connected()

        try:
            response = ws.call(obs_requests.GetSceneList())
            scenes = [scene["sceneName"] for scene in response.getScenes()]
            logger.debug("scenes_listed", count=len(scenes), scenes=scenes)
            return scenes

        except (MessageTimeout, Exception) as e:
            logger.error("list_scenes_failed", error=str(e))
            raise OBSConnectionError(f"Failed to list scenes: {e}") from e

    async def get_current_scene(self) -> str:
        """Get name of currently active scene.

        Implements FR-005: Current scene detection.

        Returns:
            Current scene name

        Raises:
            OBSConnectionError: If not connected or request fails
        """
        ws = self._ensure_connected()

        try:
            response = ws.call(obs_requests.GetCurrentProgramScene())
            scene_name = response.getCurrentProgramSceneName()
            logger.debug("current_scene_retrieved", scene=scene_name)
            return scene_name

        except (MessageTimeout, Exception) as e:
            logger.error("get_current_scene_failed", error=str(e))
            raise OBSConnectionError(f"Failed to get current scene: {e}") from e

    async def switch_scene(self, scene_name: str, transition_duration_ms: int = 300) -> None:
        """Switch to specified scene with smooth transition.

        Implements FR-002: Programmatic scene switching.
        Implements FR-035: Smooth transition effects.

        Args:
            scene_name: Name of scene to activate
            transition_duration_ms: Transition duration in milliseconds (default: 300ms)

        Raises:
            OBSConnectionError: If scene doesn't exist or switch fails
        """
        ws = self._ensure_connected()

        try:
            # Set transition duration for smooth scene change
            if transition_duration_ms > 0:
                ws.call(obs_requests.SetCurrentSceneTransitionDuration(transitionDuration=transition_duration_ms))

            # Switch to the scene
            ws.call(obs_requests.SetCurrentProgramScene(sceneName=scene_name))
            logger.info("scene_switched", scene=scene_name, transition_ms=transition_duration_ms)

        except (MessageTimeout, Exception) as e:
            logger.error("scene_switch_failed", scene=scene_name, error=str(e))
            raise OBSConnectionError(f"Failed to switch to scene '{scene_name}': {e}") from e

    async def scene_exists(self, scene_name: str) -> bool:
        """Check if scene exists in OBS.

        Implements FR-012: Scene existence verification.

        Args:
            scene_name: Scene name to check

        Returns:
            True if scene exists, False otherwise
        """
        scenes = await self.list_scenes()
        return scene_name in scenes

    async def create_scene(self, scene_name: str) -> None:
        """Create new scene in OBS.

        Implements FR-003: Scene creation (never overwrites existing).

        Args:
            scene_name: Name for new scene

        Raises:
            OBSConnectionError: If scene already exists or creation fails
        """
        ws = self._ensure_connected()

        # Check if scene already exists (FR-004: never overwrite)
        if await self.scene_exists(scene_name):
            logger.info("scene_already_exists", scene=scene_name)
            return

        try:
            ws.call(obs_requests.CreateScene(sceneName=scene_name))
            logger.info("scene_created", scene=scene_name)

        except (MessageTimeout, Exception) as e:
            logger.error("scene_creation_failed", scene=scene_name, error=str(e))
            raise OBSConnectionError(f"Failed to create scene '{scene_name}': {e}") from e

    async def create_media_source(
        self,
        scene_name: str,
        source_name: str,
        file_path: str,
        loop: bool = True
    ) -> None:
        """Create or update a media source in a scene for video playback.

        Args:
            scene_name: Scene to add the source to
            source_name: Name for the media source
            file_path: WSL path to media file (e.g., //wsl.localhost/Debian/path/to/file.mp4)
            loop: Whether to loop the media

        Raises:
            OBSConnectionError: If source creation/update fails
        """
        ws = self._ensure_connected()

        try:
            # Input settings for media source
            input_settings = {
                "local_file": file_path,
                "looping": loop,
                "restart_on_activate": True,
                "close_when_inactive": False,
            }

            # Try to create the source - if it exists, OBS will error
            try:
                ws.call(obs_requests.CreateInput(
                    sceneName=scene_name,
                    inputName=source_name,
                    inputKind="ffmpeg_source",  # Media Source
                    inputSettings=input_settings,
                    sceneItemEnabled=True
                ))
                logger.info(
                    "media_source_created",
                    scene=scene_name,
                    source=source_name,
                    file=file_path,
                    loop=loop
                )
            except Exception as create_error:
                # Source might already exist, try updating it instead
                logger.debug("media_source_exists_updating", source=source_name, error=str(create_error))
                ws.call(obs_requests.SetInputSettings(
                    inputName=source_name,
                    inputSettings=input_settings,
                    overlay=False  # Replace all settings
                ))
                logger.info(
                    "media_source_updated",
                    scene=scene_name,
                    source=source_name,
                    file=file_path,
                    loop=loop
                )

        except (MessageTimeout, Exception) as e:
            logger.error(
                "media_source_operation_failed",
                scene=scene_name,
                source=source_name,
                error=str(e)
            )
            raise OBSConnectionError(f"Failed to create/update media source '{source_name}': {e}") from e

    async def create_text_source(
        self,
        scene_name: str,
        source_name: str,
        text: str,
        font_size: int = 48,
        color: int = 0xFFFFFFFF,  # White
        outline: bool = True,
        outline_size: int = 2,
        outline_color: int = 0xFF000000,  # Black
    ) -> None:
        """Create or update a text source in a scene.

        Args:
            scene_name: Scene to add the text to
            source_name: Name for the text source
            text: Text content to display
            font_size: Font size in points
            color: Text color in ARGB format (0xAARRGGBB)
            outline: Whether to add outline
            outline_size: Outline thickness in pixels
            outline_color: Outline color in ARGB format

        Raises:
            OBSConnectionError: If source creation/update fails
        """
        ws = self._ensure_connected()

        try:
            # Input settings for text source (FreeType 2 - cross-platform)
            input_settings = {
                "text": text,
                "font": {
                    "face": "Arial",
                    "size": font_size,
                    "flags": 0,  # 0=normal, 1=bold, 2=italic, 3=bold+italic
                },
                "color": color,
                "outline": outline,
                "outline_size": outline_size,
                "outline_color": outline_color,
            }

            # Try to create the source
            try:
                ws.call(obs_requests.CreateInput(
                    sceneName=scene_name,
                    inputName=source_name,
                    inputKind="text_ft2_source_v2",  # FreeType 2 text source
                    inputSettings=input_settings,
                    sceneItemEnabled=True
                ))
                logger.info(
                    "text_source_created",
                    scene=scene_name,
                    source=source_name,
                    text_length=len(text)
                )
            except Exception as create_error:
                # Source might already exist, try updating it instead
                logger.debug("text_source_exists_updating", source=source_name, error=str(create_error))
                ws.call(obs_requests.SetInputSettings(
                    inputName=source_name,
                    inputSettings=input_settings,
                    overlay=False
                ))
                logger.info(
                    "text_source_updated",
                    scene=scene_name,
                    source=source_name,
                    text_length=len(text)
                )

        except (MessageTimeout, Exception) as e:
            logger.error(
                "text_source_operation_failed",
                scene=scene_name,
                source=source_name,
                error=str(e)
            )
            raise OBSConnectionError(f"Failed to create/update text source '{source_name}': {e}") from e

    async def get_streaming_status(self) -> dict[str, Any]:
        """Get current streaming status from OBS.

        Implements FR-014: Streaming state monitoring.

        Returns:
            Dict with streaming status:
            - active (bool): True if streaming
            - reconnecting (bool): True if reconnecting to RTMP
            - timecode (str): Stream duration if active

        Raises:
            OBSConnectionError: If status check fails
        """
        ws = self._ensure_connected()

        try:
            response = ws.call(obs_requests.GetStreamStatus())
            status = {
                "active": response.getOutputActive(),
                "reconnecting": response.getOutputReconnecting(),
                "timecode": response.getOutputTimecode(),
                "bytes": response.getOutputBytes(),
                "duration_ms": response.getOutputDuration(),
            }
            logger.debug("streaming_status_retrieved", **status)
            return status

        except (MessageTimeout, Exception) as e:
            logger.error("get_streaming_status_failed", error=str(e))
            raise OBSConnectionError(f"Failed to get streaming status: {e}") from e

    async def start_streaming(self) -> None:
        """Start RTMP streaming to Twitch.

        Implements FR-010: Auto-start streaming.

        Raises:
            OBSConnectionError: If streaming start fails
        """
        ws = self._ensure_connected()

        try:
            # Check if already streaming
            status = await self.get_streaming_status()
            if status["active"]:
                logger.info("streaming_already_active")
                return

            ws.call(obs_requests.StartStream())
            logger.info("streaming_started")

        except (MessageTimeout, Exception) as e:
            logger.error("start_streaming_failed", error=str(e))
            raise OBSConnectionError(f"Failed to start streaming: {e}") from e

    async def stop_streaming(self) -> None:
        """Stop RTMP streaming.

        Implements FR-046: Graceful streaming stop.

        Raises:
            OBSConnectionError: If streaming stop fails
        """
        ws = self._ensure_connected()

        try:
            # Check if currently streaming
            status = await self.get_streaming_status()
            if not status["active"]:
                logger.info("streaming_already_stopped")
                return

            ws.call(obs_requests.StopStream())
            logger.info("streaming_stopped")

        except (MessageTimeout, Exception) as e:
            logger.error("stop_streaming_failed", error=str(e))
            raise OBSConnectionError(f"Failed to stop streaming: {e}") from e

    async def get_stats(self) -> dict[str, Any]:
        """Get OBS performance statistics.

        Implements FR-019: Health metrics collection.

        Returns:
            Dict with stats:
            - cpu_usage: CPU usage percentage
            - memory_usage: Memory usage in MB
            - fps: Current framerate
            - render_missed_frames: Dropped render frames
            - output_skipped_frames: Dropped output frames

        Raises:
            OBSConnectionError: If stats retrieval fails
        """
        ws = self._ensure_connected()

        try:
            response = ws.call(obs_requests.GetStats())
            # OBS WebSocket v5.x returns stats directly in datain
            stats = response.datain if hasattr(response, 'datain') else {}
            logger.debug("obs_stats_retrieved", **stats)
            return stats

        except (MessageTimeout, Exception) as e:
            logger.error("get_stats_failed", error=str(e))
            raise OBSConnectionError(f"Failed to get OBS stats: {e}") from e

    def _ensure_connected(self) -> obsws:
        """Verify connection to OBS is active.

        Returns:
            Active WebSocket connection

        Raises:
            OBSConnectionError: If not connected
        """
        if not self.is_connected():
            raise OBSConnectionError("Not connected to OBS. Call connect() first.")
        assert self._ws is not None, "WebSocket should be initialized after is_connected() check"
        return self._ws

    def _parse_websocket_url(self, url: str) -> tuple[str, int]:
        """Parse WebSocket URL into host and port.

        Args:
            url: WebSocket URL (e.g., "ws://localhost:4455")

        Returns:
            Tuple of (host, port)

        Raises:
            ValueError: If URL format is invalid
        """
        # Remove ws:// or wss:// prefix
        url = url.replace("ws://", "").replace("wss://", "")

        # Split host:port
        if ":" in url:
            host, port_str = url.rsplit(":", 1)
            try:
                port = int(port_str)
                return host, port
            except ValueError:
                raise ValueError(f"Invalid port in WebSocket URL: {url}")
        else:
            # Default OBS websocket port
            return url, 4455
