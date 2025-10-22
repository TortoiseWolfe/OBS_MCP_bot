"""OwnerInterruptConfiguration domain model.

Represents configuration for owner 'Go Live' signaling and transitions.
Implements entity specification from data-model.md.
"""

from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DetectionMethod(str, Enum):
    """How owner signals intent to go live."""

    HOTKEY = "hotkey"
    SCENE_CHANGE = "scene_change"
    BOTH = "both"


class OwnerInterruptConfiguration(BaseModel):
    """Configuration for owner 'Go Live' signaling and transitions.

    Validation Rules:
    - owner_scene_name must match actual OBS scene name (validated at startup)
    - cooldown_period_sec default: 2.0 seconds (balance between responsiveness and accidental triggers)
    - detection_method = both enables either hotkey OR scene change
    """

    config_id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    hotkey_binding: str = Field(description="Hotkey for 'Go Live' toggle (e.g., 'F8')")
    owner_scene_name: str = Field("Owner Live", description="Scene name for manual switching detection")
    transition_duration_ms: int = Field(description="Scene transition duration in milliseconds", ge=0, le=5000)
    audio_fade_duration_ms: int = Field(description="Audio crossfade duration", ge=0, le=2000)
    cooldown_period_sec: float = Field(description="Prevent accidental double-triggers", ge=1.0, le=10.0)
    detection_method: DetectionMethod = Field(description="How owner signals intent")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "config_id": "bb0e8400-e29b-41d4-a716-446655440006",
                "hotkey_binding": "F8",
                "owner_scene_name": "Owner Live",
                "transition_duration_ms": 300,
                "audio_fade_duration_ms": 150,
                "cooldown_period_sec": 2.0,
                "detection_method": "both"
            }
        }
