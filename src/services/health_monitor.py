"""Health monitoring service for stream health metrics collection.

Implements FR-019-023: Collect and persist stream health metrics every 10 seconds,
detect degraded quality, and provide queryable health status.
"""

import asyncio
import psutil
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.config.logging import get_logger
from src.config.settings import Settings
from src.models.health_metric import (
    ConnectionStatus,
    HealthMetric,
    StreamingStatus,
)
from src.models.stream_session import StreamSession
from src.persistence.repositories.metrics import MetricsRepository
from src.services.obs_controller import OBSConnectionError, OBSController

logger = get_logger(__name__)


class HealthMonitor:
    """Monitors stream health and collects metrics periodically.

    Implements:
    - FR-019: Collect metrics every 10 seconds (bitrate, dropped frames, CPU, connection)
    - FR-020: Persist uptime metrics to database
    - FR-021: Detect degraded quality (>1% dropped frames)
    - FR-022: Detect complete stream failure within 30 seconds
    """

    def __init__(
        self,
        settings: Settings,
        obs_controller: OBSController,
        metrics_repo: MetricsRepository,
    ):
        """Initialize health monitor.

        Args:
            settings: Application settings
            obs_controller: OBS WebSocket controller
            metrics_repo: Metrics repository for persistence
        """
        self.settings = settings
        self.obs = obs_controller
        self.metrics_repo = metrics_repo
        self._monitoring_task: Optional[asyncio.Task] = None
        self._current_session: Optional[StreamSession] = None
        self._running = False
        self._collection_interval_sec = 10  # FR-019: every 10 seconds

    async def start_monitoring(self, stream_session: StreamSession) -> None:
        """Start health metrics collection for current stream session.

        Args:
            stream_session: Active stream session to monitor
        """
        if self._running:
            logger.warning("health_monitoring_already_running")
            return

        self._current_session = stream_session
        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(
            "health_monitoring_started",
            session_id=str(stream_session.session_id),
            collection_interval_sec=self._collection_interval_sec,
        )

    async def stop_monitoring(self) -> None:
        """Stop health metrics collection."""
        self._running = False

        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("health_monitoring_stopped")

    async def get_current_health(self) -> Optional[HealthMetric]:
        """Get most recent health metric for current session.

        Returns:
            Latest HealthMetric if exists, None otherwise
        """
        if not self._current_session:
            return None

        return self.metrics_repo.get_latest(self._current_session.session_id)

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that collects metrics every 10 seconds.

        Implements FR-019: Collect health metrics every 10 seconds.
        """
        logger.info("health_monitoring_loop_started")

        while self._running:
            try:
                # Collect metrics
                metric = await self._collect_metrics()

                if metric:
                    # Persist to database (FR-020)
                    self.metrics_repo.create(metric)

                    # Check for degraded quality (FR-021)
                    if metric.is_degraded:
                        logger.warning(
                            "stream_quality_degraded",
                            dropped_frames_pct=metric.dropped_frames_pct,
                            threshold_pct=1.0,
                            session_id=str(metric.stream_session_id),
                            active_scene=metric.active_scene,
                        )

                    # Check for complete failure (FR-022)
                    if (
                        metric.connection_status == ConnectionStatus.DISCONNECTED
                        or metric.streaming_status != StreamingStatus.STREAMING
                    ):
                        logger.error(
                            "stream_failure_detected",
                            connection_status=metric.connection_status.value,
                            streaming_status=metric.streaming_status.value,
                            session_id=str(metric.stream_session_id),
                        )

                # Wait before next collection
                await asyncio.sleep(self._collection_interval_sec)

            except asyncio.CancelledError:
                logger.info("health_monitoring_loop_cancelled")
                raise
            except Exception as e:
                logger.error("health_monitoring_error", error=str(e))
                # Continue monitoring even if one iteration fails
                await asyncio.sleep(self._collection_interval_sec)

    async def _collect_metrics(self) -> Optional[HealthMetric]:
        """Collect current health metrics from OBS and system.

        Returns:
            HealthMetric instance with current measurements, None if collection fails
        """
        if not self._current_session:
            logger.warning("no_active_session_for_metrics")
            return None

        try:
            # Get OBS streaming status
            streaming_status_data = await self.obs.get_streaming_status()

            # Get OBS performance stats
            obs_stats = await self.obs.get_stats()

            # Get current scene
            current_scene = await self.obs.get_current_scene()

            # Determine connection status
            connection_status = ConnectionStatus.CONNECTED
            if not streaming_status_data.get("active", False):
                connection_status = ConnectionStatus.DISCONNECTED
            elif streaming_status_data.get("reconnecting", False):
                connection_status = ConnectionStatus.DEGRADED

            # Determine streaming status
            if streaming_status_data.get("active", False):
                streaming_status = StreamingStatus.STREAMING
            else:
                streaming_status = StreamingStatus.STOPPED

            # Extract metrics from OBS stats
            # OBS WebSocket v5 stats structure varies, handle missing keys gracefully
            bitrate_kbps = float(obs_stats.get("outputBytes", 0)) * 8 / 1000 / streaming_status_data.get("duration_ms", 1) * 1000 if streaming_status_data.get("duration_ms", 0) > 0 else 0.0

            # Dropped frames calculation
            output_skipped_frames = float(obs_stats.get("outputSkippedFrames", 0))
            output_total_frames = float(obs_stats.get("outputTotalFrames", 1))
            dropped_frames_pct = (output_skipped_frames / output_total_frames * 100) if output_total_frames > 0 else 0.0

            # System CPU usage (not OBS CPU)
            cpu_usage_pct = psutil.cpu_percent(interval=0.1)

            # Create health metric
            metric = HealthMetric(
                metric_id=uuid4(),
                stream_session_id=self._current_session.session_id,
                timestamp=datetime.now(timezone.utc),
                bitrate_kbps=bitrate_kbps,
                dropped_frames_pct=dropped_frames_pct,
                cpu_usage_pct=cpu_usage_pct,
                active_scene=current_scene,
                active_source=None,  # TODO: Track active content source
                connection_status=connection_status,
                streaming_status=streaming_status,
            )

            logger.debug(
                "metrics_collected",
                bitrate_kbps=bitrate_kbps,
                dropped_frames_pct=dropped_frames_pct,
                cpu_usage_pct=cpu_usage_pct,
                scene=current_scene,
                connection=connection_status.value,
            )

            return metric

        except OBSConnectionError as e:
            logger.error("obs_connection_error_during_metrics_collection", error=str(e))
            # Return metric indicating failure
            return HealthMetric(
                metric_id=uuid4(),
                stream_session_id=self._current_session.session_id,
                timestamp=datetime.now(timezone.utc),
                bitrate_kbps=0.0,
                dropped_frames_pct=0.0,
                cpu_usage_pct=psutil.cpu_percent(interval=0.1),
                active_scene="Unknown",
                active_source=None,
                connection_status=ConnectionStatus.DISCONNECTED,
                streaming_status=StreamingStatus.STOPPED,
            )
        except Exception as e:
            logger.error("metrics_collection_failed", error=str(e))
            return None
