"""DowntimeEvent domain model.

Represents a period when the stream was offline or degraded.
Implements entity specification from data-model.md.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class FailureCause(str, Enum):
    """Type of failure that caused downtime."""

    CONNECTION_LOST = "connection_lost"  # RTMP connection to Twitch dropped
    OBS_CRASH = "obs_crash"  # OBS became unresponsive
    CONTENT_FAILURE = "content_failure"  # Content source failed to play
    NETWORK_DEGRADED = "network_degraded"  # Network bandwidth insufficient
    MANUAL_STOP = "manual_stop"  # Owner manually stopped streaming (edge case)


class DowntimeEvent(BaseModel):
    """Period when stream was offline or degraded.

    State Transitions:
    - Detected: start_time set, end_time null, failure logged
    - Recovering: Recovery action initiated (switch to failover, restart OBS, etc.)
    - Resolved: end_time set, duration computed
    """

    event_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this downtime event")
    stream_session_id: UUID = Field(description="Foreign key to StreamSession")
    start_time: datetime = Field(description="When downtime/degradation started (UTC)")
    end_time: Optional[datetime] = Field(None, description="When recovered (null if ongoing)")
    duration_sec: float = Field(0.0, ge=0.0, description="Duration of downtime (computed)")
    failure_cause: FailureCause = Field(description="Type of failure")
    recovery_action: str = Field(description="What action was taken to recover", min_length=1, max_length=500)
    automatic_recovery: bool = Field(description="True if auto-recovered, false if manual")

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Ensure end_time is after start_time if set."""
        if v is not None and "start_time" in info.data:
            if v <= info.data["start_time"]:
                raise ValueError("end_time must be after start_time")
        return v

    @property
    def is_ongoing(self) -> bool:
        """Check if downtime is currently ongoing."""
        return self.end_time is None

    def compute_duration(self) -> float:
        """Compute duration in seconds if end_time is set."""
        if self.end_time is not None:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "event_id": "660e8400-e29b-41d4-a716-446655440001",
                "stream_session_id": "550e8400-e29b-41d4-a716-446655440000",
                "start_time": "2025-10-21T14:30:00Z",
                "end_time": "2025-10-21T14:30:05Z",
                "duration_sec": 5.0,
                "failure_cause": "connection_lost",
                "recovery_action": "RTMP reconnection initiated automatically",
                "automatic_recovery": True
            }
        }
