"""HealthMetric domain model.

Represents point-in-time stream health measurement (collected every 10 seconds per FR-019).
Implements entity specification from data-model.md.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ConnectionStatus(str, Enum):
    """RTMP connection state."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DEGRADED = "degraded"


class StreamingStatus(str, Enum):
    """OBS streaming state."""

    STREAMING = "streaming"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"


class HealthMetric(BaseModel):
    """Point-in-time stream health measurement.

    Validation Rules:
    - dropped_frames_pct > 1.0 triggers warning (FR-021)
    - connection_status = disconnected for >30 sec triggers recovery (FR-022)
    - Metrics older than 7 days are archived (storage optimization)
    """

    metric_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this metric snapshot")
    stream_session_id: UUID = Field(description="Foreign key to StreamSession")
    timestamp: datetime = Field(description="When metric was collected (UTC)")
    bitrate_kbps: float = Field(ge=0.0, description="Current bitrate in kilobits/sec")
    dropped_frames_pct: float = Field(ge=0.0, le=100.0, description="Percentage of dropped frames")
    cpu_usage_pct: float = Field(ge=0.0, le=100.0, description="CPU usage percentage")
    active_scene: str = Field(description="Current OBS scene name", min_length=1, max_length=100)
    active_source: Optional[str] = Field(None, description="Current content source (if applicable)", max_length=255)
    connection_status: ConnectionStatus = Field(description="RTMP connection state")
    streaming_status: StreamingStatus = Field(description="OBS streaming state")

    @property
    def is_degraded(self) -> bool:
        """Check if stream quality is degraded (>1% dropped frames per FR-021)."""
        return self.dropped_frames_pct > 1.0

    @property
    def is_healthy(self) -> bool:
        """Check if stream is healthy (connected and streaming with good quality)."""
        return (
            self.connection_status == ConnectionStatus.CONNECTED
            and self.streaming_status == StreamingStatus.STREAMING
            and not self.is_degraded
        )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "metric_id": "770e8400-e29b-41d4-a716-446655440002",
                "stream_session_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-10-21T12:05:00Z",
                "bitrate_kbps": 6000.0,
                "dropped_frames_pct": 0.3,
                "cpu_usage_pct": 42.5,
                "active_scene": "Educational Content",
                "active_source": "video_001.mp4",
                "connection_status": "connected",
                "streaming_status": "streaming"
            }
        }
