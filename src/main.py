"""Main entry point for OBS_bot streaming orchestrator.

Implements User Story 1: Continuous Educational Broadcasting
- Pre-flight validation
- Auto-start streaming
- Automated content playback
- 24/7 operation

Implements User Story 2: Owner Live Broadcast Takeover (US2)
- Owner interrupt detection via scene monitoring
- Automated pause/resume of content scheduler
- Owner session tracking and metrics

Implements User Story 3: Automatic Failover and Recovery (US3)
- Failure detection (OBS crash, RTMP disconnect, content failure)
- Automatic recovery with failover scenes
- Downtime event tracking and logging

Implements User Story 4: Stream Health Monitoring (US4)
- Health metrics collection every 10 seconds
- FastAPI health endpoints for operational visibility
- Uptime reporting and SC-001 validation

Coordinates startup_validator, stream_manager, content_scheduler, owner_detector, failover_manager, and health_monitor services.
"""

import asyncio
import signal
import sys
from pathlib import Path

import uvicorn

from src.config.logging import configure_logging, get_logger
from src.config.settings import get_settings
from src.models.init_state import OverallStatus
from src.persistence.db import Database
from src.persistence.repositories.content_library import ContentSourceRepository
from src.persistence.repositories.events import EventsRepository
from src.persistence.repositories.metrics import MetricsRepository
from src.persistence.repositories.sessions import SessionsRepository
from src.services.content_scheduler import ContentScheduler
from src.services.failover_manager import FailoverManager
from src.services.health_monitor import HealthMonitor
from src.services.obs_controller import OBSController, OBSConnectionError
from src.services.startup_validator import StartupValidator
from src.services.stream_manager import StreamManager

# Optional US2 imports
try:
    from src.persistence.repositories.owner_sessions import OwnerSessionsRepository
    from src.services.owner_detector import OwnerDetector
except ImportError:
    OwnerSessionsRepository = None  # type: ignore
    OwnerDetector = None  # type: ignore

logger = get_logger(__name__)


class Application:
    """24/7 streaming orchestrator application.

    Implements US1: Continuous Educational Broadcasting.
    """

    def __init__(self):
        """Initialize application components."""
        self.running = False
        self.settings = None
        self.db: Database | None = None
        self.obs_controller: OBSController | None = None
        self.startup_validator: StartupValidator | None = None
        self.stream_manager: StreamManager | None = None
        self.content_scheduler: ContentScheduler | None = None
        self.sessions_repo: SessionsRepository | None = None
        self.events_repo: EventsRepository | None = None
        self.metrics_repo: MetricsRepository | None = None
        self.content_source_repo: ContentSourceRepository | None = None
        # US2 - Owner Live Broadcast Takeover
        self.owner_sessions_repo: "OwnerSessionsRepository | None" = None
        self.owner_detector: "OwnerDetector | None" = None
        # US3 - Automatic Failover and Recovery
        self.failover_manager: FailoverManager | None = None
        # US4 - Stream Health Monitoring
        self.health_monitor: HealthMonitor | None = None
        self.api_server_task: asyncio.Task | None = None

    async def startup(self) -> None:
        """Initialize application and perform pre-flight validation.

        Implements FR-009: Pre-flight validation on startup.
        Implements FR-010: Auto-start streaming after validation passes.
        """
        try:
            logger.info("application_starting")

            # Load configuration
            self.settings = get_settings()

            # Configure logging
            configure_logging(
                level=self.settings.logging.level,
                log_format=self.settings.logging.format,
                log_dir=Path("logs"),
            )

            # Initialize database
            self.db = Database(db_path=Path("data") / "obs_bot.db")
            await self.db.connect()
            logger.info("database_initialized")

            # Initialize repositories
            self.sessions_repo = SessionsRepository(str(Path("data") / "obs_bot.db"))
            self.events_repo = EventsRepository(str(Path("data") / "obs_bot.db"))
            self.metrics_repo = MetricsRepository(str(Path("data") / "obs_bot.db"))
            self.content_source_repo = ContentSourceRepository(str(Path("data") / "obs_bot.db"))
            logger.info("repositories_initialized")

            # Initialize US2 repositories if available
            if OwnerSessionsRepository is not None:
                self.owner_sessions_repo = OwnerSessionsRepository(self.db)
                logger.info("owner_sessions_repository_initialized")

            # Initialize OBS controller
            self.obs_controller = OBSController(self.settings.obs)

            # Initialize US3 FailoverManager
            self.failover_manager = FailoverManager(
                self.settings,
                self.obs_controller,
                self.events_repo,
            )
            logger.info("failover_manager_initialized")

            # Initialize US4 HealthMonitor
            self.health_monitor = HealthMonitor(
                self.settings,
                self.obs_controller,
                self.metrics_repo,
            )
            logger.info("health_monitor_initialized")

            # Initialize services
            self.startup_validator = StartupValidator(self.settings, self.obs_controller)
            self.content_scheduler = ContentScheduler(
                self.settings,
                self.obs_controller,
                failover_manager=self.failover_manager,
                content_source_repo=self.content_source_repo,  # Tier 3: Enable smart scheduling
            )

            # Initialize StreamManager with US2 support
            self.stream_manager = StreamManager(
                self.settings,
                self.obs_controller,
                self.sessions_repo,
                owner_sessions_repo=self.owner_sessions_repo,
                content_scheduler=self.content_scheduler,
            )

            # Initialize OwnerDetector if available (US2)
            if OwnerDetector is not None:
                self.owner_detector = OwnerDetector(
                    self.settings,
                    self.obs_controller,
                )
                # Register callbacks for owner interrupts
                self.owner_detector.on_owner_live(self.stream_manager.handle_owner_goes_live)
                self.owner_detector.on_owner_return(self.stream_manager.handle_owner_returns)
                logger.info("owner_detector_initialized")

            # Run pre-flight validation with retry
            logger.info("preflight_validation_starting")
            init_state = await self.startup_validator.validate_with_retry(
                max_retries=None,  # Retry forever until validation passes
                create_missing_scenes=True,
            )

            if init_state.overall_status == OverallStatus.PASSED:
                logger.info("preflight_validation_passed")

                # Auto-start streaming (FR-010)
                session = await self.stream_manager.auto_start_streaming(init_state)
                logger.info("streaming_auto_started", session_id=str(session.session_id))

                # Start failover monitoring (US3)
                if self.failover_manager:
                    await self.failover_manager.start_monitoring(session)
                    logger.info("failover_monitoring_started")

                # Start health monitoring (US4)
                if self.health_monitor:
                    await self.health_monitor.start_monitoring(session)
                    logger.info("health_monitoring_started")

                # Initialize and start FastAPI health API (US4)
                await self._start_health_api()

                # Start content scheduler
                await self.content_scheduler.start()
                logger.info("content_scheduler_started")

                # Start owner detector if available (US2)
                if self.owner_detector:
                    await self.owner_detector.start()
                    logger.info("owner_detector_started")

                self.running = True
                logger.info("application_ready")
            else:
                logger.error("preflight_validation_failed_after_retries")
                raise RuntimeError("Pre-flight validation failed")

        except Exception as e:
            logger.error("startup_failed", error=str(e), exc_info=True)
            raise

    async def shutdown(self) -> None:
        """Gracefully shutdown application.

        Implements FR-046: Graceful shutdown with planned maintenance mode.
        """
        logger.info("application_shutting_down")
        self.running = False

        try:
            # Switch to Technical Difficulties scene
            if self.obs_controller and self.obs_controller.is_connected():
                await self.obs_controller.switch_scene("Technical Difficulties")
                logger.info("switched_to_technical_difficulties_scene")

                # Wait 30 seconds for viewers to see the message
                await asyncio.sleep(30)

            # Stop owner detector if running (US2)
            if self.owner_detector:
                await self.owner_detector.stop()
                logger.info("owner_detector_stopped")

            # Stop health monitoring if running (US4)
            if self.health_monitor:
                await self.health_monitor.stop_monitoring()
                logger.info("health_monitoring_stopped")

            # Stop health API server if running (US4)
            if self.api_server_task and not self.api_server_task.done():
                self.api_server_task.cancel()
                try:
                    await self.api_server_task
                except asyncio.CancelledError:
                    pass
                logger.info("health_api_stopped")

            # Stop failover monitoring if running (US3)
            if self.failover_manager:
                await self.failover_manager.stop_monitoring()
                logger.info("failover_monitoring_stopped")

            # Stop content scheduler
            if self.content_scheduler:
                await self.content_scheduler.stop()
                logger.info("content_scheduler_stopped")

            # Stop streaming
            if self.stream_manager:
                await self.stream_manager.stop_streaming()
                logger.info("streaming_stopped")

            # Disconnect from OBS
            if self.obs_controller:
                await self.obs_controller.disconnect()
                logger.info("obs_disconnected")

        except Exception as e:
            logger.error("shutdown_error", error=str(e), exc_info=True)

        logger.info("application_stopped")

    async def _start_health_api(self) -> None:
        """Start FastAPI health monitoring server in background.

        Implements FR-023: Queryable health status API (localhost-only).
        Implements T092: Integrate FastAPI server into main.py.
        """
        # Initialize API repositories
        from src.api.health import app as health_app
        from src.api.health import init_repositories

        # Ensure repositories are initialized
        assert self.sessions_repo is not None, "Sessions repository not initialized"
        assert self.metrics_repo is not None, "Metrics repository not initialized"
        assert self.events_repo is not None, "Events repository not initialized"

        init_repositories(
            sessions_repo=self.sessions_repo,
            metrics_repo=self.metrics_repo,
            events_repo=self.events_repo,
            content_repo=self.content_source_repo,  # T077: Pass content repo for health metrics
        )

        # Configure uvicorn
        config = uvicorn.Config(
            app=health_app,
            host="127.0.0.1",  # localhost-only for security (FR-023)
            port=8000,
            log_level="info",
            access_log=False,  # Reduce log noise
        )

        server = uvicorn.Server(config)

        # Run server in background task
        self.api_server_task = asyncio.create_task(server.serve())
        logger.info("health_api_server_started", host="127.0.0.1", port=8000)

    async def run(self) -> None:
        """Main application loop.

        Keeps application running and monitors stream health.
        Implements FR-020: State persistence across restarts.
        """
        logger.info("application_running")

        try:
            # Keep application alive while services run in background
            while self.running:
                await asyncio.sleep(10)

                # Log health status periodically
                if self.stream_manager:
                    session = await self.stream_manager.get_current_session()
                    if session:
                        logger.debug(
                            "stream_health_check",
                            session_id=str(session.session_id),
                            duration_sec=session.total_duration_sec,
                            uptime_pct=session.uptime_percentage,
                        )

        except asyncio.CancelledError:
            logger.info("application_cancelled")


async def main() -> None:
    """Main entry point with signal handling."""
    app = Application()

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("shutdown_signal_received", signal=sig)
        asyncio.create_task(app.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await app.startup()
        await app.run()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
    except Exception as e:
        logger.error("application_error", error=str(e), exc_info=True)
        sys.exit(1)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    """Run application.

    Usage:
        python -m src.main
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
