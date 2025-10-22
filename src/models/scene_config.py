"""SceneConfiguration domain model.

Represents required OBS scene metadata.
Implements entity specification from data-model.md.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ScenePurpose(str, Enum):
    """Scene purpose classification."""

    AUTOMATED = "automated"
    OWNER = "owner"
    FAILOVER = "failover"
    TECHNICAL_DIFFICULTIES = "technical_difficulties"


class SceneConfiguration(BaseModel):
    """Required OBS scene metadata.

    Required Scenes (FR-003):
    - "Automated Content" (purpose=automated)
    - "Owner Live" (purpose=owner)
    - "Failover" (purpose=failover)
    - "Technical Difficulties" (purpose=technical_difficulties)

    Validation Rules:
    - System creates missing scenes on init (FR-003, FR-012)
    - Never overwrites existing scenes (FR-004)
    - Re-verification every 60 seconds during operation
    """

    scene_id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    scene_name: str = Field(description="OBS scene name", min_length=1, max_length=100)
    purpose: ScenePurpose = Field(description="Scene purpose")
    exists_in_obs: bool = Field(description="Whether scene exists in OBS (updated during pre-flight validation)")
    last_verified_at: datetime = Field(description="Last verification timestamp")

    @property
    def needs_verification(self) -> bool:
        """Check if scene needs re-verification (>60 seconds old)."""
        from datetime import timezone
        age_seconds = (datetime.now(timezone.utc) - self.last_verified_at).total_seconds()
        return age_seconds > 60

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "scene_id": "cc0e8400-e29b-41d4-a716-446655440007",
                "scene_name": "Automated Content",
                "purpose": "automated",
                "exists_in_obs": True,
                "last_verified_at": "2025-10-21T12:00:00Z"
            }
        }
