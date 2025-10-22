"""ScheduleBlock domain model.

Represents time-based programming configuration.
Implements entity specification from data-model.md.
"""

from typing import List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from src.models.content_source import AgeAppropriateness, SourceType


class ScheduleBlock(BaseModel):
    """Time-based programming configuration.

    Validation Rules:
    - Time ranges can wrap midnight (e.g., 22:00-02:00)
    - No overlapping time ranges for same day (enforced at creation)
    - priority_order format: ["owner_live", "failover", "scheduled"]
    """

    block_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this schedule block")
    name: str = Field(description="Human-readable name (e.g., 'After School Kids')", min_length=1, max_length=100)
    time_range_start: str = Field(description="Start time in local timezone (HH:MM format)")
    time_range_end: str = Field(description="End time in local timezone (HH:MM format)")
    day_restrictions: List[str] = Field(description="Days of week (Monday-Sunday, or 'all')", min_length=1)
    allowed_content_types: List[SourceType] = Field(description="Allowed source types", min_length=1)
    age_requirement: AgeAppropriateness = Field(description="Age appropriateness filter")
    priority_order: List[str] = Field(description="Content priority rules for this block", min_length=1)

    @field_validator("time_range_start", "time_range_end")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate HH:MM format."""
        import re
        if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", v):
            raise ValueError("Time must be in HH:MM format (00:00-23:59)")
        return v

    @field_validator("day_restrictions")
    @classmethod
    def validate_days(cls, v: List[str]) -> List[str]:
        """Validate day names."""
        valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "all"}
        for day in v:
            if day not in valid_days:
                raise ValueError(f"Invalid day: {day}. Must be one of {valid_days}")
        return v

    @field_validator("time_range_end")
    @classmethod
    def validate_time_range(cls, v: str, info) -> str:
        """Ensure start and end times are different."""
        if "time_range_start" in info.data:
            if v == info.data["time_range_start"]:
                raise ValueError("time_range_end must be different from time_range_start")
        return v

    @property
    def crosses_midnight(self) -> bool:
        """Check if time range crosses midnight (e.g., 22:00-02:00)."""
        start_hour = int(self.time_range_start.split(":")[0])
        end_hour = int(self.time_range_end.split(":")[0])
        return end_hour < start_hour

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "block_id": "aa0e8400-e29b-41d4-a716-446655440005",
                "name": "After School Kids",
                "time_range_start": "15:00",
                "time_range_end": "18:00",
                "day_restrictions": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "allowed_content_types": ["video_file"],
                "age_requirement": "kids",
                "priority_order": ["owner_live", "failover", "scheduled"]
            }
        }
