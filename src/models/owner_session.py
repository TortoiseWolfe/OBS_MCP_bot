"""OwnerSession domain model.

Represents a period when the owner was broadcasting live.
Implements entity specification from data-model.md.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class TriggerMethod(str, Enum):
    """How owner triggered 'Go Live'."""

    HOTKEY = "hotkey"  # Owner pressed hotkey (e.g., F8)
    SCENE_CHANGE = "scene_change"  # Owner manually switched to owner live scene


class OwnerSession(BaseModel):
    """Period when owner was broadcasting live.

    Validation Rules:
    - transition_time_sec should be ≤10 seconds 95% of the time (SC-003)
    - Owner sessions cannot overlap (enforced via application logic)
    """

    session_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this owner session")
    stream_session_id: UUID = Field(description="Foreign key to parent StreamSession")
    start_time: datetime = Field(description="When owner went live (sources activated)")
    end_time: Optional[datetime] = Field(None, description="When owner session ended (sources deactivated)")
    duration_sec: int = Field(0, ge=0, description="Duration of owner session (computed)")
    content_interrupted: Optional[str] = Field(None, description="What content was playing before owner took over", max_length=255)
    resume_content: Optional[str] = Field(None, description="What content resumed after owner finished", max_length=255)
    transition_time_sec: float = Field(description="How long the transition took (for SC-003 measurement)", ge=0.0, le=60.0)
    trigger_method: TriggerMethod = Field(description="How owner triggered 'Go Live'")

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
        """Check if owner session is currently active."""
        return self.end_time is None

    @property
    def meets_transition_target(self) -> bool:
        """Check if transition met ≤10 second target (SC-003)."""
        return self.transition_time_sec <= 10.0

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "session_id": "880e8400-e29b-41d4-a716-446655440003",
                "stream_session_id": "550e8400-e29b-41d4-a716-446655440000",
                "start_time": "2025-10-21T15:00:00Z",
                "end_time": "2025-10-21T15:45:00Z",
                "duration_sec": 2700,
                "content_interrupted": "educational_video_042.mp4",
                "resume_content": "educational_video_043.mp4",
                "transition_time_sec": 8.5,
                "trigger_method": "hotkey"
            }
        }
