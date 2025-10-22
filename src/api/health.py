"""Health API endpoints for stream monitoring and uptime reporting.

Implements FR-023: Queryable health status API (localhost-only).
Follows contract specification from contracts/health-api.yaml.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config.logging import get_logger
from src.models.downtime_event import DowntimeEvent
from src.models.health_metric import HealthMetric
from src.models.stream_session import StreamSession
from src.persistence.repositories.events import EventsRepository
from src.persistence.repositories.metrics import MetricsRepository
from src.persistence.repositories.sessions import SessionsRepository

logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="OBS Streaming Health API",
    description="Health monitoring API for Tier 1 OBS Streaming Foundation",
    version="1.0.0",
)

# T093: Configure CORS for localhost development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ===== Response Models (matching contract spec) =====


class StreamQuality(BaseModel):
    """Stream quality metrics."""

    bitrate_kbps: float = Field(ge=0, description="Current bitrate in kilobits per second")
    dropped_frames_pct: float = Field(ge=0, le=100, description="Percentage of dropped frames")
    cpu_usage_pct: float = Field(ge=0, le=100, description="CPU usage percentage")
    connection_status: str = Field(description="RTMP connection state")


class FailoverEvent(BaseModel):
    """Last failover event information."""

    timestamp: datetime = Field(description="When failover occurred (ISO 8601 UTC)")
    failure_cause: str = Field(description="Type of failure that triggered failover")
    recovery_time_sec: float = Field(ge=0, description="How long recovery took")


class SessionInfo(BaseModel):
    """Current session information."""

    session_id: str = Field(description="Unique identifier for current stream session")
    start_time: datetime = Field(description="When current session started (ISO 8601 UTC)")
    total_downtime_sec: int = Field(ge=0, description="Total downtime seconds in current session")


class HealthSnapshot(BaseModel):
    """Complete health snapshot response."""

    streaming: bool = Field(description="Whether stream is currently live on Twitch")
    uptime_seconds: int = Field(ge=0, description="Seconds since current session started")
    uptime_percentage: float = Field(ge=0, le=100, description="Uptime percentage for current session")
    current_scene: str = Field(description="Active OBS scene name")
    current_content: Optional[str] = Field(None, description="Currently playing content source")
    stream_quality: StreamQuality
    owner_live: bool = Field(description="Whether owner is currently broadcasting")
    last_failover: Optional[FailoverEvent] = None
    session_info: SessionInfo
    history: Optional[List[dict]] = Field(default=None, description="Recent health metrics if requested")


class HealthMetricResponse(BaseModel):
    """Health metric data point."""

    metric_id: str
    timestamp: datetime
    bitrate_kbps: float
    dropped_frames_pct: float
    cpu_usage_pct: float
    active_scene: str
    active_source: Optional[str]
    connection_status: str
    streaming_status: str


class MetricsQueryResponse(BaseModel):
    """Response for metrics query."""

    metrics: List[HealthMetricResponse]
    total_count: int
    query: dict


class DowntimeEventSummary(BaseModel):
    """Downtime event summary for uptime report."""

    timestamp: datetime
    duration_sec: float
    failure_cause: str
    recovery_action: str


class UptimeReport(BaseModel):
    """Uptime report response."""

    period_days: int
    total_uptime_seconds: int
    total_downtime_seconds: int
    uptime_percentage: float = Field(ge=0, le=100)
    meets_sc001: bool = Field(description="Whether uptime meets 99.9% requirement")
    downtime_events: List[DowntimeEventSummary]


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    details: Optional[str] = None
    timestamp: datetime


# ===== Dependencies =====

# These will be injected from main.py
_sessions_repo: Optional[SessionsRepository] = None
_metrics_repo: Optional[MetricsRepository] = None
_events_repo: Optional[EventsRepository] = None


def init_repositories(
    sessions_repo: SessionsRepository,
    metrics_repo: MetricsRepository,
    events_repo: EventsRepository,
) -> None:
    """Initialize repository dependencies.

    Called from main.py during startup.

    Args:
        sessions_repo: Sessions repository
        metrics_repo: Metrics repository
        events_repo: Events repository
    """
    global _sessions_repo, _metrics_repo, _events_repo
    _sessions_repo = sessions_repo
    _metrics_repo = metrics_repo
    _events_repo = events_repo
    logger.info("health_api_repositories_initialized")


# ===== Endpoints =====


@app.get(
    "/health",
    response_model=HealthSnapshot,
    responses={
        503: {"model": ErrorResponse, "description": "Stream offline or system not initialized"}
    },
    summary="Get current stream health snapshot",
    tags=["Health"],
)
async def get_health(
    include_history: bool = Query(
        False,
        description="Include recent health metrics history (last 100 data points)",
    )
) -> HealthSnapshot:
    """Get current stream health snapshot.

    Returns real-time stream health status including:
    - Streaming state (on/off)
    - Current uptime
    - Active scene and content
    - Stream quality metrics
    - Last failover event
    - Owner live status

    Implements FR-023: Queryable health status API.
    """
    if not _sessions_repo or not _metrics_repo or not _events_repo:
        raise HTTPException(
            status_code=503,
            detail="Health API not initialized - repositories not available",
        )

    # Get current active session
    active_session = _sessions_repo.get_current_stream_session()
    if not active_session:
        # No active session - stream is offline
        return _build_offline_response()

    # Get latest health metric
    latest_metric = _metrics_repo.get_latest(active_session.session_id)
    if not latest_metric:
        # No metrics yet - stream just started
        return _build_starting_response(active_session)

    # Check if owner is currently live
    owner_live = latest_metric.active_scene == "Owner Live"

    # Calculate uptime
    uptime_seconds = int(
        (datetime.now(timezone.utc) - active_session.start_time).total_seconds()
    )

    # Calculate uptime percentage
    total_session_duration = uptime_seconds
    downtime_duration = active_session.downtime_duration_sec
    uptime_percentage = (
        ((total_session_duration - downtime_duration) / total_session_duration * 100)
        if total_session_duration > 0
        else 100.0
    )

    # Get last failover event
    last_failover = None
    downtime_events = _events_repo.get_by_session(active_session.session_id)
    if downtime_events:
        event = downtime_events[-1]  # Get most recent event (list is ordered ASC)
        last_failover = FailoverEvent(
            timestamp=event.start_time,
            failure_cause=event.failure_cause.value,
            recovery_time_sec=event.duration_sec if event.duration_sec else 0.0,
        )

    # Build stream quality
    stream_quality = StreamQuality(
        bitrate_kbps=latest_metric.bitrate_kbps,
        dropped_frames_pct=latest_metric.dropped_frames_pct,
        cpu_usage_pct=latest_metric.cpu_usage_pct,
        connection_status=latest_metric.connection_status.value,
    )

    # Build session info
    session_info = SessionInfo(
        session_id=str(active_session.session_id),
        start_time=active_session.start_time,
        total_downtime_sec=int(active_session.downtime_duration_sec),
    )

    # Optionally include history
    history = None
    if include_history:
        metrics = _metrics_repo.get_by_session(active_session.session_id, limit=100)
        history = [
            {
                "metric_id": str(m.metric_id),
                "timestamp": m.timestamp.isoformat(),
                "bitrate_kbps": m.bitrate_kbps,
                "dropped_frames_pct": m.dropped_frames_pct,
                "cpu_usage_pct": m.cpu_usage_pct,
                "active_scene": m.active_scene,
                "connection_status": m.connection_status.value,
            }
            for m in metrics
        ]

    # Build complete snapshot
    snapshot = HealthSnapshot(
        streaming=latest_metric.streaming_status.value == "streaming",
        uptime_seconds=uptime_seconds,
        uptime_percentage=uptime_percentage,
        current_scene=latest_metric.active_scene,
        current_content=latest_metric.active_source,
        stream_quality=stream_quality,
        owner_live=owner_live,
        last_failover=last_failover,
        session_info=session_info,
        history=history,
    )

    logger.debug(
        "health_snapshot_generated",
        streaming=snapshot.streaming,
        uptime_pct=uptime_percentage,
        owner_live=owner_live,
    )

    return snapshot


@app.get(
    "/health/metrics",
    response_model=MetricsQueryResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query parameters"}
    },
    summary="Get historical health metrics",
    tags=["Health"],
)
async def get_health_metrics(
    start_time: Optional[str] = Query(None, description="Start of time range (ISO 8601 UTC)"),
    end_time: Optional[str] = Query(None, description="End of time range (ISO 8601 UTC)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of metrics to return"),
) -> MetricsQueryResponse:
    """Query historical health metrics for trend analysis.

    Use Cases:
    - Validate SC-006: Content transition gap analysis (<2 seconds)
    - Validate SC-008: Uptime accuracy verification (within 1 second)
    - Debug performance degradation over time

    Implements FR-023: Queryable health status API.
    """
    if not _sessions_repo or not _metrics_repo:
        raise HTTPException(
            status_code=503,
            detail="Health API not initialized",
        )

    # Get current active session
    active_session = _sessions_repo.get_current_stream_session()
    if not active_session:
        # No active session - return empty metrics
        return MetricsQueryResponse(
            metrics=[],
            total_count=0,
            query={
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            },
        )

    # Get metrics for session
    # TODO: Add time range filtering in repository when needed
    all_metrics = _metrics_repo.get_by_session(active_session.session_id, limit=limit)

    # Convert to response model
    metrics_response = [
        HealthMetricResponse(
            metric_id=str(m.metric_id),
            timestamp=m.timestamp,
            bitrate_kbps=m.bitrate_kbps,
            dropped_frames_pct=m.dropped_frames_pct,
            cpu_usage_pct=m.cpu_usage_pct,
            active_scene=m.active_scene,
            active_source=m.active_source,
            connection_status=m.connection_status.value,
            streaming_status=m.streaming_status.value,
        )
        for m in all_metrics
    ]

    return MetricsQueryResponse(
        metrics=metrics_response,
        total_count=len(metrics_response),
        query={
            "start_time": start_time,
            "end_time": end_time,
            "limit": limit,
        },
    )


@app.get(
    "/health/uptime",
    response_model=UptimeReport,
    summary="Get uptime report for validation",
    tags=["Health"],
)
async def get_uptime_report(
    period_days: int = Query(
        7,
        ge=1,
        le=30,
        description="Number of days to analyze (default 7 for weekly SC-001 check)",
    )
) -> UptimeReport:
    """Generate uptime report for constitutional compliance verification (SC-001).

    Returns:
    - Total uptime percentage over period
    - Downtime events with causes
    - Success criteria validation (99.9% target)

    Implements FR-023: Queryable health status API.
    Validates SC-001: 99.9% uptime requirement.
    """
    if not _sessions_repo or not _events_repo:
        raise HTTPException(
            status_code=503,
            detail="Health API not initialized",
        )

    # Get current active session
    active_session = _sessions_repo.get_current_stream_session()
    if not active_session:
        # No active session - return empty report
        return UptimeReport(
            period_days=period_days,
            total_uptime_seconds=0,
            total_downtime_seconds=0,
            uptime_percentage=0.0,
            meets_sc001=False,
            downtime_events=[],
        )

    # Calculate total session duration
    total_duration_sec = int(
        (datetime.now(timezone.utc) - active_session.start_time).total_seconds()
    )

    # Get all downtime events for session
    downtime_events = _events_repo.get_by_session(active_session.session_id)

    # Calculate total downtime
    total_downtime_sec = sum(
        event.duration_sec if event.duration_sec else 0.0 for event in downtime_events
    )

    # Calculate uptime
    total_uptime_sec = max(0, total_duration_sec - int(total_downtime_sec))

    # Calculate uptime percentage
    uptime_percentage = (
        (total_uptime_sec / total_duration_sec * 100) if total_duration_sec > 0 else 100.0
    )

    # Check if meets SC-001 (99.9% uptime)
    meets_sc001 = uptime_percentage >= 99.9

    # Build downtime event summaries
    event_summaries = [
        DowntimeEventSummary(
            timestamp=event.start_time,
            duration_sec=event.duration_sec if event.duration_sec else 0.0,
            failure_cause=event.failure_cause.value,
            recovery_action=event.recovery_action or "Unknown",
        )
        for event in downtime_events
    ]

    report = UptimeReport(
        period_days=period_days,
        total_uptime_seconds=total_uptime_sec,
        total_downtime_seconds=int(total_downtime_sec),
        uptime_percentage=uptime_percentage,
        meets_sc001=meets_sc001,
        downtime_events=event_summaries,
    )

    logger.info(
        "uptime_report_generated",
        uptime_pct=uptime_percentage,
        meets_sc001=meets_sc001,
        downtime_events_count=len(downtime_events),
    )

    return report


# ===== Analytics Endpoints (T090, T091) =====


@app.get("/health/analytics/transitions")
async def get_transition_analytics():
    """T090: Get owner transition time analysis.

    Returns statistics on owner interrupt transitions:
    - Average transition time
    - Total transitions
    - Fastest/slowest transitions
    """
    if _owner_sessions_repo is None:
        raise HTTPException(
            status_code=503,
            detail="Owner sessions repository not available"
        )

    if not _sessions_repo:
        raise HTTPException(
            status_code=503,
            detail="Health API not initialized"
        )

    active_session = _sessions_repo.get_current_stream_session()
    if not active_session:
        return {
            "total_transitions": 0,
            "avg_transition_time_sec": 0.0,
            "fastest_transition_sec": 0.0,
            "slowest_transition_sec": 0.0
        }

    # Get all owner sessions for current stream session
    owner_sessions = _owner_sessions_repo.get_owner_sessions_by_stream(active_session.session_id)

    if not owner_sessions:
        return {
            "total_transitions": 0,
            "avg_transition_time_sec": 0.0,
            "fastest_transition_sec": 0.0,
            "slowest_transition_sec": 0.0
        }

    # Calculate transition statistics
    transition_times = [
        (session.end_time - session.start_time).total_seconds()
        for session in owner_sessions
        if session.end_time is not None
    ]

    if not transition_times:
        return {
            "total_transitions": len(owner_sessions),
            "avg_transition_time_sec": 0.0,
            "fastest_transition_sec": 0.0,
            "slowest_transition_sec": 0.0
        }

    return {
        "total_transitions": len(owner_sessions),
        "avg_transition_time_sec": sum(transition_times) / len(transition_times),
        "fastest_transition_sec": min(transition_times),
        "slowest_transition_sec": max(transition_times)
    }


@app.get("/health/analytics/failover")
async def get_failover_analytics():
    """T091: Get failover performance analysis.

    Returns statistics on failover recovery:
    - Total failover events
    - Average recovery time
    - Fastest/slowest recovery
    - Failover causes breakdown
    """
    if not _events_repo or not _sessions_repo:
        raise HTTPException(
            status_code=503,
            detail="Health API not initialized"
        )

    active_session = _sessions_repo.get_current_stream_session()
    if not active_session:
        return {
            "total_failovers": 0,
            "avg_recovery_time_sec": 0.0,
            "fastest_recovery_sec": 0.0,
            "slowest_recovery_sec": 0.0,
            "causes_breakdown": {}
        }

    # Get all downtime events for current session
    downtime_events = _events_repo.get_by_session(active_session.session_id)

    if not downtime_events:
        return {
            "total_failovers": 0,
            "avg_recovery_time_sec": 0.0,
            "fastest_recovery_sec": 0.0,
            "slowest_recovery_sec": 0.0,
            "causes_breakdown": {}
        }

    # Calculate recovery times
    recovery_times = [event.duration_sec for event in downtime_events if event.duration_sec > 0]

    # Count failure causes
    causes_breakdown = {}
    for event in downtime_events:
        cause = event.failure_cause.value
        causes_breakdown[cause] = causes_breakdown.get(cause, 0) + 1

    if not recovery_times:
        return {
            "total_failovers": len(downtime_events),
            "avg_recovery_time_sec": 0.0,
            "fastest_recovery_sec": 0.0,
            "slowest_recovery_sec": 0.0,
            "causes_breakdown": causes_breakdown
        }

    return {
        "total_failovers": len(downtime_events),
        "avg_recovery_time_sec": sum(recovery_times) / len(recovery_times),
        "fastest_recovery_sec": min(recovery_times),
        "slowest_recovery_sec": max(recovery_times),
        "causes_breakdown": causes_breakdown
    }


# ===== Helper Functions =====


def _build_offline_response() -> HealthSnapshot:
    """Build health snapshot for offline stream."""
    return HealthSnapshot(
        streaming=False,
        uptime_seconds=0,
        uptime_percentage=0.0,
        current_scene="Offline",
        current_content=None,
        stream_quality=StreamQuality(
            bitrate_kbps=0.0,
            dropped_frames_pct=0.0,
            cpu_usage_pct=0.0,
            connection_status="disconnected",
        ),
        owner_live=False,
        last_failover=None,
        session_info=SessionInfo(
            session_id="00000000-0000-0000-0000-000000000000",
            start_time=datetime.now(timezone.utc),
            total_downtime_sec=0,
        ),
        history=None,
    )


def _build_starting_response(session: StreamSession) -> HealthSnapshot:
    """Build health snapshot for stream that just started."""
    uptime_seconds = int(
        (datetime.now(timezone.utc) - session.start_time).total_seconds()
    )

    return HealthSnapshot(
        streaming=True,
        uptime_seconds=uptime_seconds,
        uptime_percentage=100.0,
        current_scene="Starting",
        current_content=None,
        stream_quality=StreamQuality(
            bitrate_kbps=0.0,
            dropped_frames_pct=0.0,
            cpu_usage_pct=0.0,
            connection_status="connected",
        ),
        owner_live=False,
        last_failover=None,
        session_info=SessionInfo(
            session_id=str(session.session_id),
            start_time=session.start_time,
            total_downtime_sec=0,
        ),
        history=None,
    )
