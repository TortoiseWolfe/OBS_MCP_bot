"""SystemInitializationState domain model.

Represents the outcome of startup pre-flight validation.
Implements entity specification from data-model.md.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class OverallStatus(str, Enum):
    """Overall initialization status."""

    PASSED = "passed"
    FAILED = "failed"


class SystemInitializationState(BaseModel):
    """Outcome of startup pre-flight validation.

    State Transitions:
    - Validating: Pre-flight checks running
    - Passed: All checks true, streaming auto-started
    - Failed: One or more checks failed, retry after 60 sec
    """

    init_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this init attempt")
    timestamp: datetime = Field(description="When initialization was attempted")
    obs_connectivity: bool = Field(description="OBS websocket reachable")
    scenes_exist: bool = Field(description="All required scenes present")
    failover_content_available: bool = Field(description="Failover content verified playable")
    twitch_credentials_configured: bool = Field(description="Stream key configured")
    network_connectivity: bool = Field(description="Can reach Twitch RTMP endpoint")
    overall_status: OverallStatus = Field(description="Pass if all checks true")
    stream_started_at: Optional[datetime] = Field(None, description="When streaming auto-started (if passed)")
    failure_details: Optional[dict[str, Any]] = Field(None, description="Specific errors if failed")

    @field_validator("failure_details")
    @classmethod
    def validate_failure_details(cls, v: Optional[dict[str, Any]], info) -> Optional[dict[str, Any]]:
        """Ensure failure_details is provided if status is failed."""
        if "overall_status" in info.data:
            if info.data["overall_status"] == OverallStatus.FAILED and not v:
                raise ValueError("failure_details is required when overall_status is failed")
        return v

    @property
    def all_checks_passed(self) -> bool:
        """Check if all pre-flight validation checks passed."""
        return (
            self.obs_connectivity
            and self.scenes_exist
            and self.failover_content_available
            and self.twitch_credentials_configured
            and self.network_connectivity
        )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "init_id": "dd0e8400-e29b-41d4-a716-446655440008",
                "timestamp": "2025-10-21T12:00:00Z",
                "obs_connectivity": True,
                "scenes_exist": True,
                "failover_content_available": True,
                "twitch_credentials_configured": True,
                "network_connectivity": True,
                "overall_status": "passed",
                "stream_started_at": "2025-10-21T12:00:45Z",
                "failure_details": None
            }
        }
