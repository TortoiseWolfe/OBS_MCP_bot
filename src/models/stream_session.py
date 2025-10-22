"""StreamSession domain model.

Represents a continuous broadcast period from stream start to stream end.
Implements entity specification from data-model.md.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class StreamSession(BaseModel):
    """Continuous broadcast period tracking.

    State Transitions:
    - Created: start_time set, end_time null, streaming initiated
    - Ongoing: Health metrics accumulated, downtime/owner events appended
    - Ended: end_time set, final statistics computed
    """

    session_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this stream session")
    start_time: datetime = Field(description="When streaming started (UTC)")
    end_time: Optional[datetime] = Field(None, description="When streaming ended (null if ongoing)")
    total_duration_sec: int = Field(0, ge=0, description="Total seconds streamed (computed)")
    downtime_duration_sec: int = Field(0, ge=0, description="Total seconds offline during session")
    avg_bitrate_kbps: float = Field(0.0, ge=0, description="Average bitrate across all health metrics")
    avg_dropped_frames_pct: float = Field(0.0, ge=0.0, le=100.0, description="Average dropped frames percentage")
    peak_cpu_usage_pct: float = Field(0.0, ge=0.0, le=100.0, description="Peak CPU usage during session")

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Ensure end_time is after start_time if set."""
        if v is not None and "start_time" in info.data:
            if v <= info.data["start_time"]:
                raise ValueError("end_time must be after start_time")
        return v

    @field_validator("downtime_duration_sec")
    @classmethod
    def validate_downtime(cls, v: int, info) -> int:
        """Ensure downtime doesn't exceed total duration."""
        if "total_duration_sec" in info.data:
            if v > info.data["total_duration_sec"]:
                raise ValueError("downtime_duration_sec cannot exceed total_duration_sec")
        return v

    @property
    def is_ongoing(self) -> bool:
        """Check if stream session is currently active."""
        return self.end_time is None

    @property
    def uptime_duration_sec(self) -> int:
        """Calculate actual streaming time (total - downtime)."""
        return self.total_duration_sec - self.downtime_duration_sec

    @property
    def uptime_percentage(self) -> float:
        """Calculate uptime percentage (99.9% target per FR-001)."""
        if self.total_duration_sec == 0:
            return 100.0
        return (self.uptime_duration_sec / self.total_duration_sec) * 100.0

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "start_time": "2025-10-21T12:00:00Z",
                "end_time": None,
                "total_duration_sec": 3600,
                "downtime_duration_sec": 15,
                "avg_bitrate_kbps": 6000.0,
                "avg_dropped_frames_pct": 0.5,
                "peak_cpu_usage_pct": 45.2
            }
        }
