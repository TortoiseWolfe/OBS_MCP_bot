# OBS_bot Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-21

## Active Technologies
- Python 3.11+ (asyncio for concurrent monitoring, mature obs-websocket libraries) (001-tier1-obs-streaming)
- Python 3.11+ (matches existing OBS orchestrator) + `twitchio==2.10.0`, `anthropic==0.40.0`, `anthropic[aiohttp]` (002-twitch-chat-bot)
- SQLite (extend existing `obs_bot.db` with moderation_events table) (002-twitch-chat-bot)
- Python 3.11+ (matches existing OBS orchestrator) + `yt-dlp` (latest), `ffprobe` (from ffmpeg package), `obs-websocket-py` (existing), `structlog` (existing), `aiosqlite` (existing) (003-content-library-management)
- SQLite (extend existing `obs_bot.db` with content_sources, license_info tables) (003-content-library-management)

## Project Structure
```
src/
tests/
```

## Commands
cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style
Python 3.11+ (asyncio for concurrent monitoring, mature obs-websocket libraries): Follow standard conventions

## Recent Changes
- 003-content-library-management: Added Python 3.11+ (matches existing OBS orchestrator) + `yt-dlp` (latest), `ffprobe` (from ffmpeg package), `obs-websocket-py` (existing), `structlog` (existing), `aiosqlite` (existing)
- 002-twitch-chat-bot: Added Python 3.11+ (matches existing OBS orchestrator) + `twitchio==2.10.0`, `anthropic==0.40.0`, `anthropic[aiohttp]`
- 002-twitch-chat-bot: Added [if applicable, e.g., PostgreSQL, CoreData, files or N/A]

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
