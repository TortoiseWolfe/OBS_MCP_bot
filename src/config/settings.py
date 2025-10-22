"""Configuration management using Pydantic for type safety and validation.

Loads configuration from:
1. config/settings.yaml (default values)
2. Environment variables (override YAML, prefixed with OBS_BOT_)
3. Direct env vars for secrets (OBS_WEBSOCKET_PASSWORD, TWITCH_STREAM_KEY, DISCORD_WEBHOOK_URL)
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OBSSettings(BaseModel):
    """OBS WebSocket connection settings."""

    websocket_url: str = "ws://localhost:4455"
    password: str = Field(default="", exclude=True)  # Load from env only
    connection_timeout_sec: int = 10
    reconnect_interval_sec: int = 5
    max_reconnect_attempts: int = 10


class TwitchSettings(BaseModel):
    """Twitch streaming settings."""

    stream_key: str = Field(default="", exclude=True)  # Load from env only
    rtmp_url: str = "rtmp://live.twitch.tv/app"
    reconnect_interval_sec: int = 10
    max_reconnect_attempts: int = 0  # 0 = infinite

    @field_validator("stream_key")
    @classmethod
    def validate_stream_key(cls, v: str) -> str:
        """Log warning if stream key not provided (will be loaded from env after init)."""
        # Note: Stream key is loaded from env after Settings object creation
        # Validation happens in startup_validator service
        return v


class StreamQualitySettings(BaseModel):
    """Stream quality configuration."""

    resolution: str = "1920x1080"
    framerate: int = 60
    bitrate_kbps: int = 6000
    encoder: Literal["x264", "nvenc"] = "x264"


class OwnerInterruptSettings(BaseModel):
    """Owner interrupt detection configuration (FR-029-035)."""

    detection_method: Literal["hotkey", "scene", "hotkey_and_scene"] = "hotkey_and_scene"
    hotkey_binding: str = "F8"
    owner_scene_name: str = "Owner Live"
    transition_duration_ms: int = 1000
    debounce_sec: int = 5


class SceneSettings(BaseModel):
    """Required OBS scene names."""

    automated_content: str = "Automated Content"
    owner_live: str = "Owner Live"
    failover: str = "Failover"
    technical_difficulties: str = "Technical Difficulties"
    going_live_soon: str = "Going Live Soon"


class ContentSettings(BaseModel):
    """Content scheduling settings."""

    library_path: Path = Path("/app/content")
    windows_content_path: str = "//wsl.localhost/Debian/home/turtle_wolfe/repos/OBS_bot/content"
    failover_video: Path = Path("/app/content/failover/default_failover.mp4")
    transition_duration_sec: int = 2

    @field_validator("failover_video")
    @classmethod
    def validate_failover_exists(cls, v: Path) -> Path:
        """Ensure failover video is configured (validation happens at startup)."""
        if not v:
            raise ValueError("Failover video path is required")
        return v


class ScheduleBlock(BaseModel):
    """Time-based content filtering block."""

    name: str
    time_range: str  # Format: "HH:MM-HH:MM"
    days: list[str]
    age_requirement: Literal["kids", "adult", "all"]
    allowed_types: list[str]


class HealthSettings(BaseModel):
    """Health monitoring configuration (FR-019-023)."""

    metrics_collection_interval_sec: int = 10
    degraded_quality_threshold_pct: float = 1.0
    failure_detection_timeout_sec: int = 30


class APISettings(BaseModel):
    """Health API configuration."""

    host: str = "127.0.0.1"  # localhost-only per FR-023
    port: int = 8000
    enable_cors: bool = False


class DiscordSettings(BaseModel):
    """Discord alerting configuration (FR-043-045)."""

    webhook_url: str = Field(default="", exclude=True)  # Load from env only
    alert_on_stream_offline: bool = True
    alert_on_validation_failed: bool = True
    alert_on_failover_triggered: bool = True
    offline_threshold_sec: int = 120

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook(cls, v: str) -> str:
        """Log warning if Discord webhook URL not provided (optional for MVP)."""
        if not v:
            import logging
            logging.warning("DISCORD_WEBHOOK_URL not configured - alerts disabled")
        return v


class PreflightSettings(BaseModel):
    """Pre-flight validation configuration (FR-009-013)."""

    retry_interval_sec: int = 60
    required_checks: list[str] = [
        "obs_connectivity",
        "obs_scenes_exist",
        "failover_content_exists",
        "twitch_credentials_valid",
        "network_connectivity",
    ]


class LoggingSettings(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["json", "text"] = "json"
    rotation_days: int = 30
    max_size_mb: int = 1000


class DatabaseSettings(BaseModel):
    """Database configuration."""

    path: Path = Path("/app/data/obs_bot.db")
    backup_interval_hours: int = 24


class SystemSettings(BaseModel):
    """System-level settings."""

    timezone: str = "UTC"
    graceful_shutdown_timeout_sec: int = 30


class Settings(BaseSettings):
    """Main application settings loaded from YAML and environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="OBS_BOT_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    obs: OBSSettings = Field(default_factory=OBSSettings)
    twitch: TwitchSettings = Field(default_factory=TwitchSettings)
    stream: StreamQualitySettings = Field(default_factory=StreamQualitySettings)
    owner_interrupt: OwnerInterruptSettings = Field(default_factory=OwnerInterruptSettings)
    scenes: SceneSettings = Field(default_factory=SceneSettings)
    content: ContentSettings = Field(default_factory=ContentSettings)
    schedule_blocks: list[ScheduleBlock] = Field(default_factory=list)
    health: HealthSettings = Field(default_factory=HealthSettings)
    api: APISettings = Field(default_factory=APISettings)
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    preflight: PreflightSettings = Field(default_factory=PreflightSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    system: SystemSettings = Field(default_factory=SystemSettings)

    @classmethod
    def load_from_yaml(cls, config_path: Path = Path("config/settings.yaml")) -> "Settings":
        """Load settings from YAML file, then override with environment variables.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Loaded and validated Settings instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValidationError: If configuration is invalid
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            yaml_config = yaml.safe_load(f)

        # Override secrets from environment variables
        yaml_config.setdefault("obs", {})["password"] = ""  # Placeholder
        yaml_config.setdefault("twitch", {})["stream_key"] = ""  # Placeholder
        yaml_config.setdefault("discord", {})["webhook_url"] = ""  # Placeholder

        # Create settings instance (will load env vars automatically)
        settings = cls(**yaml_config)

        # Load secrets from dedicated env vars (not prefixed)
        import os

        settings.obs.password = os.getenv("OBS_WEBSOCKET_PASSWORD", "")
        settings.twitch.stream_key = os.getenv("TWITCH_STREAM_KEY", "")
        settings.discord.webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")

        return settings


# Global settings instance (lazy-loaded)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create global settings instance.

    Returns:
        Global Settings instance loaded from config/settings.yaml + env vars
    """
    global _settings
    if _settings is None:
        _settings = Settings.load_from_yaml()
    return _settings
