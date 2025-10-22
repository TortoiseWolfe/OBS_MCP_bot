"""Default OBS scene definitions and configurations.

This module defines the structure for required OBS scenes that are automatically
created if they don't exist (FR-003-004). Never overwrites existing scenes.
"""

from typing import Any, TypedDict


class OBSSource(TypedDict):
    """OBS source definition."""

    name: str
    type: str  # e.g., "ffmpeg_source", "text_gdiplus_v2", "color_source_v3"
    settings: dict[str, Any]
    visible: bool


class OBSSceneDefinition(TypedDict):
    """Complete OBS scene definition with sources."""

    name: str
    sources: list[OBSSource]


# Default OBS scene definitions
# These are created automatically during pre-flight validation if missing
DEFAULT_SCENES: dict[str, OBSSceneDefinition] = {
    "automated_content": {
        "name": "Automated Content",
        "sources": [
            {
                "name": "Content Video Player",
                "type": "ffmpeg_source",
                "settings": {
                    "local_file": "",  # Set dynamically by ContentScheduler
                    "looping": False,
                    "restart_on_activate": False,
                    "clear_on_media_end": False,
                },
                "visible": True,
            },
            {
                "name": "Stream Title Overlay",
                "type": "text_gdiplus_v2",
                "settings": {
                    "text": "24/7 Educational Programming",
                    "font": {"face": "Arial", "size": 48, "flags": 0},
                    "color": 0xFFFFFFFF,  # White
                    "outline": True,
                    "outline_size": 2,
                    "outline_color": 0xFF000000,  # Black
                },
                "visible": True,
            },
        ],
    },
    "owner_live": {
        "name": "Owner Live",
        "sources": [
            # Owner configures their own sources (camera, screen capture, etc.)
            # System creates empty scene with placeholder
            {
                "name": "Owner Setup Instructions",
                "type": "text_gdiplus_v2",
                "settings": {
                    "text": "Configure your camera and screen capture sources in this scene.\n\n"
                    "Press F8 or manually switch to this scene to go live.",
                    "font": {"face": "Arial", "size": 36, "flags": 0},
                    "color": 0xFFFFFFFF,
                    "align": "center",
                    "valign": "center",
                },
                "visible": True,
            },
        ],
    },
    "failover": {
        "name": "Failover",
        "sources": [
            {
                "name": "Failover Video",
                "type": "ffmpeg_source",
                "settings": {
                    "local_file": "",  # Set from config/settings.yaml failover_video
                    "looping": True,  # Loop failover content continuously
                    "restart_on_activate": True,
                },
                "visible": True,
            },
            {
                "name": "Failover Message",
                "type": "text_gdiplus_v2",
                "settings": {
                    "text": "Experiencing technical difficulties\nBe right back!",
                    "font": {"face": "Arial", "size": 48, "flags": 1},  # Bold
                    "color": 0xFFFFFF00,  # Yellow
                    "outline": True,
                    "outline_size": 3,
                    "outline_color": 0xFF000000,
                },
                "visible": True,
            },
        ],
    },
    "technical_difficulties": {
        "name": "Technical Difficulties",
        "sources": [
            {
                "name": "Technical Difficulties Background",
                "type": "color_source_v3",
                "settings": {
                    "color": 0xFF1E1E1E,  # Dark gray
                    "width": 1920,
                    "height": 1080,
                },
                "visible": True,
            },
            {
                "name": "Technical Difficulties Text",
                "type": "text_gdiplus_v2",
                "settings": {
                    "text": "TECHNICAL DIFFICULTIES\n\n"
                    "We're experiencing issues with our streaming system.\n"
                    "Please check back shortly.\n\n"
                    "This channel provides 24/7 educational programming.",
                    "font": {"face": "Arial", "size": 56, "flags": 1},
                    "color": 0xFFFF0000,  # Red
                    "align": "center",
                    "valign": "center",
                    "outline": True,
                    "outline_size": 3,
                },
                "visible": True,
            },
        ],
    },
    "going_live_soon": {
        "name": "Going Live Soon",
        "sources": [
            {
                "name": "Going Live Background",
                "type": "color_source_v3",
                "settings": {
                    "color": 0xFF2C3E50,  # Midnight blue
                    "width": 1920,
                    "height": 1080,
                },
                "visible": True,
            },
            {
                "name": "Going Live Text",
                "type": "text_gdiplus_v2",
                "settings": {
                    "text": "OWNER GOING LIVE SOON\n\n"
                    "Setting up camera and sources...\n"
                    "Please stand by!",
                    "font": {"face": "Arial", "size": 52, "flags": 1},
                    "color": 0xFF00FF00,  # Green
                    "align": "center",
                    "valign": "center",
                    "outline": True,
                    "outline_size": 2,
                },
                "visible": True,
            },
        ],
    },
}


def get_scene_definition(scene_key: str) -> OBSSceneDefinition | None:
    """Get default scene definition by key.

    Args:
        scene_key: Scene identifier (e.g., "automated_content", "failover")

    Returns:
        Scene definition dict or None if not found
    """
    return DEFAULT_SCENES.get(scene_key)


def get_all_required_scenes() -> list[str]:
    """Get list of all required scene names.

    Returns:
        List of scene names that must exist in OBS
    """
    return [scene["name"] for scene in DEFAULT_SCENES.values()]
