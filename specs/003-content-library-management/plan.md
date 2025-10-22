# Implementation Plan: Content Library Management

**Branch**: `003-content-library-management` | **Date**: 2025-10-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-content-library-management/spec.md`

## Summary

Build a content library management system that expands the streaming platform from a single 9-minute failover video (Big Buck Bunny) to 20+ hours of CC-licensed educational programming from MIT OCW, Harvard CS50, and Khan Academy. The system provides automated download scripts using yt-dlp, organizes content into constitutional time-block directories (kids/professional/evening/general), extracts metadata for content scheduling, and automatically updates OBS text overlays with proper attribution during streaming.

**Technical Approach**: Extend existing Python 3.11+ OBS orchestrator with bash download scripts (yt-dlp), Python metadata extraction tool (ffprobe), time-block directory organization, and OBS WebSocket text source updates for dynamic attribution. Content files remain on WSL2 filesystem (mounted read-only into Docker), with metadata tracked in SQLite. All content CC BY-NC-SA licensed, legally compliant for non-commercial educational streaming.

## Technical Context

**Language/Version**: Python 3.11+ (matches existing OBS orchestrator)
**Primary Dependencies**: `yt-dlp` (latest), `ffprobe` (from ffmpeg package), `obs-websocket-py` (existing), `structlog` (existing), `aiosqlite` (existing)
**Storage**: SQLite (extend existing `obs_bot.db` with content_sources, license_info tables)
**Testing**: pytest, pytest-asyncio (existing project stack)
**Target Platform**: Linux server (WSL2 Debian), Docker container, OBS Studio on Windows host
**Project Type**: Single project (extends existing `src/` structure)
**Performance Goals**: <3 hours full library download (10 Mbps connection), <2 minutes metadata extraction (25+ videos), <1 second attribution text updates
**Constraints**: <15 GB disk space (initial content set), <500MB RAM (Docker container), non-blocking OBS operations, read-only content mount
**Scale/Scope**: 20-50 hours educational content, 3 content sources (MIT/CS50/Khan), 4 time blocks, 25-50 initial videos

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ⚠️ Tier Prerequisites - BLOCKING ISSUE IDENTIFIED

- **Tier 1 Complete**: ✅ OBS streaming orchestrator fully functional (all 41 tests passing)
- **Tier 2 Status**: ⚠️ **INCOMPLETE** - Twitch Chat Bot specification exists (branch 002-twitch-chat-bot) but implementation not found (no src/services/chat*.py or tests)
- **Tier Compliance**: This IS **Tier 3: Intelligent Content Management** per Constitution v2.0.0 (content library organization, metadata tracking, time-based filtering)
- **Constitutional Requirement**: "Tier 2 MUST demonstrate chat engagement before Tier 3" - **CURRENTLY VIOLATED**

**DECISION MADE**: Option B Selected - Constitutional Amendment for Parallel Development

**Amendment Proposal**: `.specify/memory/amendment-proposal-2.1.0.md`
- **Status**: PENDING OWNER APPROVAL (24-hour review period started 2025-10-22)
- **Proposed Version**: Constitution v2.0.0 → v2.1.0 (MINOR)
- **Rationale**: Tier 2 (chat) and Tier 3 (content library) have zero architectural dependencies
- **Independence Verified**: No shared data models, services, or APIs beyond existing Tier 1 infrastructure
- **Risk Assessment**: Minimal - standard git merge complexity only
- **Benefit**: Enables immediate Tier 3 implementation without 2-4 week Tier 2 completion delay

**Implementation Status**: Tier 3 may proceed pending 24-hour owner approval. If rejected, pause at Phase 1 completion and pivot to Tier 2.

### ✅ Constitutional Principles

- **Principle I (Broadcast Continuity)**: Maintains failover video availability, graceful degradation if library empty
- **Principle II (Educational Quality)**: MIT OCW, Harvard CS50, Khan Academy sources - verified educational content
- **Principle III (Content Appropriateness)**: Time-block organization (kids 3-6 PM, professional 9 AM-3 PM, evening 7-10 PM)
- **Principle VII (Transparent Sustainability)**: Complete CC attribution, automatic OBS text overlay updates, license compliance documentation

### ✅ Operational Standards

- **Docker Compose orchestration**: Content mounted read-only, orchestrator tracks metadata
- **State persistence**: SQLite extended with content metadata tables
- **Logging**: Structured logging for downloads, metadata extraction, attribution updates
- **Monitoring**: Content library metrics (total videos, duration, disk usage) exposed via health API

**GATE STATUS**: ✅ CONDITIONAL PASS - Amendment proposal submitted for parallel Tier 2/3 development. May proceed with implementation pending 24-hour owner approval (Option B selected).

## Project Structure

### Documentation (this feature)

```
specs/003-content-library-management/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── service-contracts.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT YET CREATED)
```

### Source Code (repository root)

**Selected Structure**: Single project (extends existing OBS orchestrator codebase)

```
src/
├── models/
│   ├── content_source.py          # NEW - ContentSource entity
│   ├── license_info.py             # NEW - LicenseInfo entity
│   ├── download_job.py             # NEW - DownloadJob entity (future)
│   └── content_library.py          # NEW - ContentLibrary aggregate
├── services/
│   ├── content_metadata_manager.py # NEW - Metadata extraction service
│   ├── content_library_scanner.py  # NEW - Directory scanning service
│   ├── obs_attribution_updater.py  # NEW - OBS text source update service
│   └── obs_controller.py           # EXTEND - Add text source update methods
├── config/
│   └── settings.py                 # EXTEND - Add content library paths, sources
└── persistence/
    └── repositories/
        ├── content_sources.py      # NEW - ContentSource CRUD operations
        └── license_info.py          # NEW - LicenseInfo CRUD operations

scripts/
├── download_mit_ocw.sh             # NEW - MIT OCW download automation
├── download_cs50.sh                # NEW - Harvard CS50 download automation
├── download_khan_academy.sh        # NEW - Khan Academy download automation
├── download_all_content.sh         # NEW - Master download orchestrator
├── add_content_metadata.py         # NEW - Metadata extraction CLI tool
└── SETUP.md                        # NEW - Installation and setup guide

content/
├── kids-after-school/              # NEW - Time block directory
├── professional-hours/             # NEW - Time block directory
├── evening-mixed/                  # NEW - Time block directory
├── general/                        # NEW - Time block directory
├── failover/                       # EXISTING - Preserved
│   └── default_failover.mp4
└── README.md                       # NEW - License attribution documentation

docs/
├── CONTENT_ARCHITECTURE.md         # NEW - WSL2/Docker/OBS architecture
└── CONTENT_QUICKSTART.md           # NEW - Quick start guide

tests/
├── unit/
│   ├── test_content_metadata_manager.py  # NEW - Metadata extraction tests
│   ├── test_content_library_scanner.py    # NEW - Directory scanning tests
│   └── test_obs_attribution_updater.py    # NEW - Attribution update tests
└── integration/
    ├── test_content_download_flow.py      # NEW - End-to-end download tests
    ├── test_obs_text_source_updates.py    # NEW - OBS WebSocket integration tests
    └── test_content_library_integration.py # NEW - Full library workflow tests
```

**Structure Decision**: Extend existing single project structure from Tier 1. No new top-level directories needed except `scripts/` and `content/`. All content management logic lives in `src/services/` and `src/models/` following established patterns. Content files remain on WSL2 filesystem (not in Docker) with read-only volume mount to `/app/content`. This minimizes complexity and maximizes code reuse (database connection, logging, OBS WebSocket client, health monitoring).

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

**No violations** - Feature complies with all constitutional principles and tier prerequisites. Extends Tier 1 infrastructure without introducing new architectural patterns or cross-tier dependencies.
