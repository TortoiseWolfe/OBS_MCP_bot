"""Content Library domain models (Tier 3).

Represents video content, licensing, and download tracking.
Implements schema from migration 003_content_library.sql.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class SourceAttribution(str, Enum):
    """Educational content source."""

    MIT_OCW = "MIT_OCW"
    CS50 = "CS50"
    KHAN_ACADEMY = "KHAN_ACADEMY"
    BLENDER = "BLENDER"


class AgeRating(str, Enum):
    """Content age appropriateness."""

    KIDS = "kids"
    ADULT = "adult"
    ALL = "all"


class DownloadStatus(str, Enum):
    """Download job status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class LicenseInfo(BaseModel):
    """Creative Commons license metadata.

    Tracks license details for educational content sources.
    All educational content must have verified CC licenses.
    """

    license_id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    license_type: str = Field(description="CC license type (e.g., 'CC BY-NC-SA 4.0')", min_length=1, max_length=50)
    source_name: str = Field(description="Content source name", min_length=1, max_length=100)
    attribution_text: str = Field(description="Attribution template with {source}, {course}, {title} placeholders", min_length=1)
    license_url: str = Field(description="Creative Commons license URL")
    permits_commercial_use: bool = Field(description="Whether commercial use is allowed")
    permits_modification: bool = Field(description="Whether modifications are allowed")
    requires_attribution: bool = Field(description="Whether attribution is required")
    requires_share_alike: bool = Field(description="Whether share-alike is required")
    verified_date: datetime = Field(description="When license was last verified (UTC)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")

    @field_validator("license_url")
    @classmethod
    def validate_license_url(cls, v: str) -> str:
        """Ensure license URL is a valid Creative Commons URL."""
        if not v.startswith("https://creativecommons.org/licenses/"):
            raise ValueError("license_url must be a valid Creative Commons license URL")
        return v

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "license_id": "550e8400-e29b-41d4-a716-446655440001",
                "license_type": "CC BY-NC-SA 4.0",
                "source_name": "MIT OpenCourseWare",
                "attribution_text": "{source} {course}: {title} - CC BY-NC-SA 4.0",
                "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                "permits_commercial_use": False,
                "permits_modification": True,
                "requires_attribution": True,
                "requires_share_alike": True,
                "verified_date": "2025-10-22T00:00:00Z"
            }
        }


class ContentSource(BaseModel):
    """Individual video file in content library.

    Represents a single educational video with full metadata,
    licensing information, and OBS path mapping.
    """

    source_id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    title: str = Field(description="Video title", min_length=1, max_length=255)
    file_path: str = Field(description="WSL2 filesystem path (/home/turtle_wolfe/repos/OBS_bot/content/...)")
    windows_obs_path: str = Field(description="Windows UNC path for OBS (\\\\wsl.localhost\\Debian\\...)")
    duration_sec: int = Field(ge=0, description="Video duration in seconds")
    file_size_mb: float = Field(gt=0, description="File size in megabytes")
    width: int = Field(gt=0, description="Video width in pixels")
    height: int = Field(gt=0, description="Video height in pixels")
    source_attribution: SourceAttribution = Field(description="Content source")
    license_type: str = Field(description="CC license type (FK to license_info.license_type)", max_length=50)
    course_name: str = Field(description="Course name (e.g., '6.0001 Intro to CS')", min_length=1, max_length=255)
    source_url: str = Field(description="Original video URL")
    attribution_text: str = Field(description="Formatted attribution text for display")
    age_rating: AgeRating = Field(description="Age appropriateness")
    time_blocks: List[str] = Field(description="Allowed time block names (e.g., ['after_school_kids', 'late_night_adult'])", min_length=1)
    priority: int = Field(ge=1, le=10, description="Playback priority (1=highest)")
    tags: List[str] = Field(description="Content tags for filtering (e.g., ['python', 'beginner'])")
    last_verified: datetime = Field(description="When file was last verified to exist and be playable")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")

    @field_validator("windows_obs_path")
    @classmethod
    def validate_windows_path(cls, v: str) -> str:
        """Ensure Windows path starts with correct UNC prefix."""
        if not v.startswith("\\\\wsl.localhost\\"):
            raise ValueError("windows_obs_path must start with \\\\wsl.localhost\\")
        return v

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Ensure file path is absolute and within a content directory."""
        # Accept both host path (/home/.../content/) and container path (/app/content/)
        valid_prefixes = [
            "/home/turtle_wolfe/repos/OBS_bot/content/",
            "/app/content/",
        ]
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(f"file_path must start with one of: {valid_prefixes}")
        return v

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "source_id": "660e8400-e29b-41d4-a716-446655440010",
                "title": "Lecture 1: Introduction to Python",
                "file_path": "/home/turtle_wolfe/repos/OBS_bot/content/mit_ocw/6.0001/lecture_01.mp4",
                "windows_obs_path": "\\\\wsl.localhost\\Debian\\home\\turtle_wolfe\\repos\\OBS_bot\\content\\mit_ocw\\6.0001\\lecture_01.mp4",
                "duration_sec": 3125,
                "file_size_mb": 450.5,
                "source_attribution": "MIT_OCW",
                "license_type": "CC BY-NC-SA 4.0",
                "course_name": "6.0001 Introduction to Computer Science and Programming in Python",
                "source_url": "https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/",
                "attribution_text": "MIT OpenCourseWare 6.0001: Lecture 1 - CC BY-NC-SA 4.0",
                "age_rating": "all",
                "time_blocks": ["after_school_kids", "evening_general"],
                "priority": 5,
                "tags": ["python", "beginner", "programming"],
                "last_verified": "2025-10-22T10:30:00Z"
            }
        }


class ContentLibrary(BaseModel):
    """Aggregate statistics for content library (singleton).

    Only one record should exist - represents the entire library state.
    """

    library_id: UUID = Field(default_factory=lambda: UUID("550e8400-e29b-41d4-a716-446655440000"), description="Fixed UUID for singleton")
    total_videos: int = Field(ge=0, default=0, description="Total number of videos")
    total_duration_sec: int = Field(ge=0, default=0, description="Total duration of all videos")
    total_size_mb: float = Field(ge=0.0, default=0.0, description="Total size of all videos")
    last_scanned: datetime = Field(description="When library was last scanned")
    mit_ocw_count: int = Field(ge=0, default=0, description="Number of MIT OCW videos")
    cs50_count: int = Field(ge=0, default=0, description="Number of CS50 videos")
    khan_academy_count: int = Field(ge=0, default=0, description="Number of Khan Academy videos")
    blender_count: int = Field(ge=0, default=0, description="Number of Blender videos")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "library_id": "550e8400-e29b-41d4-a716-446655440000",
                "total_videos": 42,
                "total_duration_sec": 151200,
                "total_size_mb": 18432.5,
                "last_scanned": "2025-10-22T10:00:00Z",
                "mit_ocw_count": 20,
                "cs50_count": 15,
                "khan_academy_count": 5,
                "blender_count": 2
            }
        }


class DownloadJob(BaseModel):
    """Content download operation tracking (future feature).

    Tracks bulk downloads from educational content sources.
    """

    job_id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    source_name: SourceAttribution = Field(description="Content source being downloaded")
    status: DownloadStatus = Field(description="Current job status")
    started_at: Optional[datetime] = Field(None, description="When download started")
    completed_at: Optional[datetime] = Field(None, description="When download completed")
    videos_downloaded: int = Field(ge=0, default=0, description="Number of videos downloaded")
    total_size_mb: float = Field(ge=0.0, default=0.0, description="Total size downloaded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "job_id": "770e8400-e29b-41d4-a716-446655440020",
                "source_name": "MIT_OCW",
                "status": "completed",
                "started_at": "2025-10-22T08:00:00Z",
                "completed_at": "2025-10-22T09:30:00Z",
                "videos_downloaded": 12,
                "total_size_mb": 5400.0
            }
        }


class VideoCaption(BaseModel):
    """Video caption/transcript entry with timing information.

    Entity 9: Synchronized captions for live playback overlay (Tier 3+).
    Supports multiple languages and sub-second timing accuracy.
    """

    caption_id: str = Field(description="Unique caption entry ID (UUID)")
    content_source_id: str = Field(description="Foreign key to ContentSource")
    language_code: str = Field(default="en", description="ISO 639-1 language code")
    start_time_sec: float = Field(ge=0.0, description="Caption start time in seconds")
    end_time_sec: float = Field(gt=0.0, description="Caption end time in seconds")
    text: str = Field(min_length=1, description="Caption text content")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Caption creation time")

    @field_validator("end_time_sec")
    @classmethod
    def validate_end_after_start(cls, v: float, info) -> float:
        """Ensure end time is after start time."""
        if "start_time_sec" in info.data and v <= info.data["start_time_sec"]:
            raise ValueError("end_time_sec must be greater than start_time_sec")
        return v

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "caption_id": "990e8400-e29b-41d4-a716-446655440030",
                "content_source_id": "770e8400-e29b-41d4-a716-446655440010",
                "language_code": "en",
                "start_time_sec": 12.5,
                "end_time_sec": 15.8,
                "text": "In computer science, we use algorithms to solve problems.",
                "created_at": "2025-10-22T10:00:00Z"
            }
        }
