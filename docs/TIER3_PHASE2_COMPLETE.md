# Tier 3 Phase 2: Foundational - COMPLETE

**Date**: 2025-10-22
**Commit**: 5cebbfd
**Status**: 51/51 tests passing (100%)

## What Was Built

### 1. Database Schema
**File**: `src/persistence/db.py`

Added 4 new tables (total: 11 tables):
- `license_info` - CC license metadata (MIT OCW, CS50, Khan Academy, Blender)
- `content_sources` - Video files with full metadata, attribution, paths
- `content_library` - Aggregate statistics (singleton)
- `download_jobs` - Download tracking (future feature)

**Key Decision**: Removed unused Tier 1 `content_sources` table - it was planned but never implemented, conflicted with Tier 3 design.

### 2. Domain Models
**File**: `src/models/content_library.py`

- `LicenseInfo` - CC license with URL validation
- `ContentSource` - Videos with WSL2/Windows path mapping, priority 1-10, age ratings, tags
- `ContentLibrary` - Singleton stats (fixed UUID)
- `DownloadJob` - Status tracking with timestamps
- Enums: `SourceAttribution`, `AgeRating`, `DownloadStatus`

**Coverage**: 97% (3 lines uncovered)

### 3. Repository Layer
**File**: `src/persistence/repositories/content_library.py`

- `LicenseInfoRepository` - CRUD + get_by_type
- `ContentSourceRepository` - CRUD + filtering (attribution, age, priority)
- `ContentLibraryRepository` - Singleton pattern
- `DownloadJobRepository` - Status updates with automatic timestamps

**Coverage**: 95% (11 lines uncovered)

### 4. OBS Controller Extensions
**File**: `src/services/obs_controller.py`

Added 3 methods for attribution text overlays:
- `set_source_visibility()` - Show/hide text sources
- `update_text_content()` - Update text dynamically
- `set_source_transform()` - Position text (x, y, scale)

**Coverage**: 33% for new methods (14 tests, mocked obswebsocket)

### 5. Configuration
**File**: `src/config/settings.py`

Extended `ContentSettings` with Tier 3 fields:
- `scan_interval_hours`, `verify_files_on_scan`, `extract_metadata_on_scan`
- `enable_downloads`, `download_max_file_size_mb`, `download_max_concurrent`
- Source paths: `mit_ocw_path`, `cs50_path`, `khan_academy_path`, `blender_path`

### 6. Dependencies
- **requirements.txt**: Added `yt-dlp>=2024.0.0`
- **Dockerfile**: Added `ffmpeg` (includes ffprobe)

### 7. Testing
**51 tests, 100% passing**

- `tests/unit/test_content_library_models.py` - 19 tests
  - Pydantic validation, enums, singleton pattern
- `tests/unit/test_content_library_repositories.py` - 18 tests
  - CRUD, filtering, foreign keys, singleton
- `tests/unit/test_obs_controller_tier3.py` - 14 tests
  - Mocked obswebsocket, request type verification

### 8. Documentation
- `README.md` - Updated with Phase 2 status
- `CLAUDE.md` - Already had Tier 3 dependencies
- Deprecated `src/models/content_source.py` (enums still used by ScheduleBlock)

## Architecture Decisions

### 1. No Migration System
**Decision**: Put Tier 3 tables directly in `SCHEMA_SQL` instead of separate migration files
**Reason**: Simpler, no migration runner needed, Tier 1 never implemented migrations
**Trade-off**: Future schema changes require careful SCHEMA_SQL edits

### 2. Docker-First Architecture
**Decision**: All code runs in Docker, only videos on WSL2 host filesystem
**Reason**: User's explicit requirement ("all my projects are docker first")
**Implementation**: Content mount `./content:/app/content:ro` (read-only)

### 3. Replaced Tier 1 ContentSource
**Decision**: Removed unused Tier 1 generic ContentSource table, replaced with Tier 3 video-specific version
**Reason**: Tier 1 ContentSource was never implemented (task T018 incomplete), conflicted with Tier 3 needs
**Preserved**: Enums (`AgeAppropriateness`, `SourceType`) still used by `ScheduleBlock`

### 4. OBS Test Mocking Strategy
**Decision**: Verify `obswebsocket` request types (isinstance checks) instead of parameter inspection
**Reason**: Request objects don't expose parameters as attributes, internal data structure unclear
**Trade-off**: Tests verify correct request types but not all parameters

## Known Issues / Limitations

1. **OBS Controller Tests**: Don't validate all request parameters (only types)
2. **Coverage Warning**: pytest-cov warns about 21% total coverage (Tier 3 only tests Tier 3 code)
3. **Deprecated Model**: `src/models/content_source.py` ContentSource class unused but can't delete (enums needed)

## What's Next: Phase 3

### User Story 1: Download Scripts (T017-T025)
1. Create download scripts:
   - `scripts/download_mit_ocw.sh` - MIT OpenCourseWare 6.0001
   - `scripts/download_cs50.sh` - Harvard CS50 lectures
   - `scripts/download_khan_academy.sh` - Khan Academy content
   - `scripts/download_all_content.sh` - Master script
2. Create `scripts/add_content_metadata.py`:
   - Scan content directory
   - Extract metadata with ffprobe
   - Map WSL2 → Windows UNC paths
   - Insert into database via repositories
3. Test full workflow inside Docker container

### Files to Create
- `scripts/download_mit_ocw.sh`
- `scripts/download_cs50.sh`
- `scripts/download_khan_academy.sh`
- `scripts/download_all_content.sh`
- `scripts/add_content_metadata.py`

### Commands to Run
```bash
# Run download script in Docker
docker run --rm -v ./content:/app/content obs-bot:latest python scripts/download_all_content.sh

# Add metadata to database
docker run --rm -v ./content:/app/content obs-bot:latest python scripts/add_content_metadata.py
```

## Quick Reference

### Test Commands
```bash
# Run all Tier 3 tests
docker run --rm obs-bot-test:latest pytest tests/unit/test_content_library_*.py tests/unit/test_obs_controller_tier3.py -v

# Run with coverage
docker run --rm obs-bot-test:latest pytest tests/unit/ --cov=src.models.content_library --cov=src.persistence.repositories.content_library --cov-report=term-missing
```

### Database Schema Check
```bash
# Connect to database and inspect tables
docker run --rm -v ./data:/app/data obs-bot:latest python3 -c "import sqlite3; conn = sqlite3.connect('/app/data/obs_bot.db'); print(conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall())"
```

### Key File Locations
- Models: `src/models/content_library.py`
- Repositories: `src/persistence/repositories/content_library.py`
- Tests: `tests/unit/test_content_library_*.py`, `tests/unit/test_obs_controller_tier3.py`
- Schema: `src/persistence/db.py` (SCHEMA_SQL)
- Config: `src/config/settings.py` (ContentSettings)

## Context for Next Session

**Branch**: `003-content-library-management`
**Last Commit**: 5cebbfd - "feat(tier3): complete Phase 2 foundational content library"
**Working Directory**: Clean (all changes committed)

**What works**: Database schema, models, repositories, OBS text overlays, 51 tests passing
**What's next**: Download scripts (Phase 3, tasks T017-T025)

**Critical Understanding**:
- Everything runs in Docker except videos (stored on WSL2 host at `./content`)
- OBS on Windows accesses videos via `\\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content\`
- No migration system - schema in SCHEMA_SQL
- Tier 1 ContentSource replaced, only enums preserved

**User Preferences**:
- Docker-first (user quote: "all my projects are docker first, the only thing local is all the videos we are downloading")
- Test everything before proceeding
- Don't mock away real validation

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
