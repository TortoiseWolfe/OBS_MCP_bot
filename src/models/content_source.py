"""ContentSource domain model.

Represents any media that can be displayed on stream.
Implements entity specification from data-model.md.
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    """Type of content."""

    VIDEO_FILE = "video_file"
    SCENE_COMPOSITION = "scene_composition"
    LIVE_INPUT = "live_input"


class AgeAppropriateness(str, Enum):
    """Age rating for content."""

    KIDS = "kids"
    TEEN = "teen"
    ADULT = "adult"
    ALL_AGES = "all_ages"


class ContentSource(BaseModel):
    """Any media that can be displayed on stream.

    Validation Rules:
    - file_path must exist and be readable (verified during FR-037)
    - last_verified_at older than 24 hours triggers re-verification
    - priority_level 1-10 reserved for owner live/failover (enforced by config)
    """

    source_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this content source")
    source_type: SourceType = Field(description="Type of content")
    file_path: Optional[str] = Field(None, description="Absolute path to content file (required if source_type=video_file)")
    duration_sec: Optional[int] = Field(None, ge=0, description="Duration of content in seconds (required if source_type=video_file)")
    age_appropriateness: AgeAppropriateness = Field(description="Age rating for content")
    time_blocks_allowed: List[str] = Field(description="Time block IDs when this content can play", min_length=1)
    priority_level: int = Field(description="Priority (1=highest, owner live always wins)", ge=1, le=100)
    last_verified_at: datetime = Field(description="Last time content was verified playable")
    metadata: Optional[dict[str, Any]] = Field(None, description="Additional metadata (title, description, etc.)")

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: Optional[str], info) -> Optional[str]:
        """Ensure file_path is provided for video_file type."""
        if "source_type" in info.data:
            if info.data["source_type"] == SourceType.VIDEO_FILE and not v:
                raise ValueError("file_path is required for video_file source type")
        return v

    @field_validator("duration_sec")
    @classmethod
    def validate_duration(cls, v: Optional[int], info) -> Optional[int]:
        """Ensure duration is provided for video_file type."""
        if "source_type" in info.data:
            if info.data["source_type"] == SourceType.VIDEO_FILE and v is None:
                raise ValueError("duration_sec is required for video_file source type")
        return v

    @property
    def needs_verification(self) -> bool:
        """Check if content needs re-verification (>24 hours old)."""
        from datetime import timezone
        age_hours = (datetime.now(timezone.utc) - self.last_verified_at).total_seconds() / 3600
        return age_hours > 24

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "source_id": "990e8400-e29b-41d4-a716-446655440004",
                "source_type": "video_file",
                "file_path": "/app/content/educational/math_101.mp4",
                "duration_sec": 1800,
                "age_appropriateness": "all_ages",
                "time_blocks_allowed": ["morning", "afternoon"],
                "priority_level": 50,
                "last_verified_at": "2025-10-21T12:00:00Z",
                "metadata": {
                    "title": "Introduction to Algebra",
                    "description": "Basic algebra concepts for beginners",
                    "category": "mathematics"
                }
            }
        }
