# OBS_24_7: AI-Hosted Educational Streaming

**24/7 educational Twitch broadcast via programmatic OBS control**

Inspired by Max Headroom (digital wit), Bob Ross (patient teaching), and PBS/NPR (public broadcasting model)

## Project Mission

Build a reliable 24/7 streaming infrastructure that controls OBS Studio programmatically to maintain continuous RTMP broadcasting to Twitch. The system handles automatic failover, owner interrupt transitions, stream health monitoring, and content playback - implementing the foundational Tier 1 requirements defined in the project constitution.

**Constitutional Framework**: [OBS_24_7 Constitution v1.0.0](.specify/memory/constitution.md)

## Development Status

✅ **Planning Complete** - Ready for Tier 1 Implementation

**Current Phase**: Implementation planning finished, 110 tasks defined across 4 user stories

**Quick Links**:
- 📜 [Constitution](.specify/memory/constitution.md) - 8 core principles and 4-tier priority structure
- 📋 [Tier 1 Specification](specs/001-tier1-obs-streaming/spec.md) - 39 functional requirements, 4 user stories
- 🚀 [Quickstart Guide](specs/001-tier1-obs-streaming/quickstart.md) - Complete setup instructions
- ✅ [Implementation Tasks](specs/001-tier1-obs-streaming/tasks.md) - 110 tasks organized by user story
- 🏗️ [Implementation Plan](specs/001-tier1-obs-streaming/plan.md) - Architecture and design decisions

## Technology Stack

**Core Platform**: Python 3.11+ (asyncio for concurrent monitoring)

**Dependencies**:
- `obs-websocket-py` - OBS control via WebSocket protocol
- `FastAPI` + `uvicorn` - Health API endpoints
- `structlog` - JSON structured logging
- `aiosqlite` - SQLite async state persistence
- `pydantic` - Configuration management and data validation

**Infrastructure**:
- Docker containerized deployment
- SQLite for metrics and state persistence
- OBS Studio 29+ with obs-websocket 5.x plugin

## Prerequisites

### Required Software

1. **OBS Studio 29.0+** with obs-websocket 5.x plugin
   - Download: https://obsproject.com/download
   - Enable WebSocket server in Tools → WebSocket Server Settings

2. **Docker & Docker Compose**
   ```bash
   docker --version
   docker-compose --version
   ```

3. **Python 3.11+** (for local development)
   ```bash
   python3 --version
   ```

4. **Twitch Account** with stream key
   - Get stream key: https://dashboard.twitch.tv/settings/stream

### System Resources
- CPU: 4+ cores recommended (OBS encoding + orchestration)
- RAM: 8GB minimum, 16GB recommended
- Network: 10 Mbps upload minimum for 1080p streaming
- Disk: 10GB for logs, state persistence, failover content

## Quick Start

### See It Run (5 minutes)

For complete setup instructions, see **[Quickstart Guide](specs/001-tier1-obs-streaming/quickstart.md)**.

Quick overview:

```bash
# 1. Clone and setup
git clone https://github.com/TortoiseWolfe/OBS_MCP_bot.git
cd OBS_MCP_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure (edit config/settings.yaml)
# - Set OBS WebSocket connection details
# - Configure owner sources for interrupt detection
# - Set failover content path

# 3. Start OBS Studio (don't click "Start Streaming" - system controls that)

# 4. Run the orchestrator
python -m src.main

# 5. Check health API
curl http://localhost:8000/health | jq
```

**Note**: Source code not yet implemented - follow [tasks.md](specs/001-tier1-obs-streaming/tasks.md) to build the system.

## User Stories

### Tier 1 Features (MVP Scope)

**US1 - Continuous Educational Broadcasting (P1)** - 17 tasks
- 24/7 streaming with auto-start after pre-flight validation
- Automatic content playback and transitions (<2 second gaps)
- 99.9% uptime target (max 30 seconds downtime per week)

**US2 - Owner Live Broadcast Takeover (P2)** - 14 tasks
- Source detection triggers owner live scene within 10 seconds
- Automatic resume to automated content when owner deactivates sources
- Smooth transitions with audio fade and visual effects

**US3 - Automatic Failover and Recovery (P3)** - 18 tasks
- Content failure detection and automatic failover within 5 seconds
- OBS crash detection and automatic restart attempts
- RTMP reconnection logic with 10-second retry intervals

**US4 - Stream Health Monitoring (P4)** - 20 tasks
- Health metrics collection every 10 seconds (bitrate, dropped frames, CPU)
- REST API for real-time health snapshots and uptime reports
- Degraded quality detection and alerting (>1% dropped frames)

## Implementation Workflow

This project uses [SpecKit](https://github.com/github/spec-kit) for spec-driven development with AI assistance.

### Completed Phases

1. ✅ `/speckit.constitution` - Established 8 core principles and Tier 1-4 priority structure
2. ✅ `/speckit.specify` - Created Tier 1 specification with 39 functional requirements
3. ✅ `/speckit.clarify` - Resolved 4 critical architectural questions
4. ✅ `/speckit.plan` - Generated architecture, data model, and API contracts
5. ✅ `/speckit.tasks` - Created 110 implementation tasks organized by user story
6. ✅ `/speckit.analyze` - Validated cross-artifact consistency (zero critical issues)

### Current Phase: Implementation

**MVP Scope**: 44 tasks (Phase 1 Setup + Phase 2 Foundational + Phase 3 US1)

**Recommended Approach**:
1. **Sprint 1**: Complete MVP (US1) - Working 24/7 streaming
2. **Sprint 2**: Add US2 (Owner Interrupt)
3. **Sprint 3**: Add US3 (Failover & Recovery)
4. **Sprint 4**: Add US4 (Health Monitoring) + Polish

See [tasks.md](specs/001-tier1-obs-streaming/tasks.md) for complete task breakdown and dependency graph.

## Project Structure

### Planning Artifacts (specs/)

```
specs/001-tier1-obs-streaming/
├── spec.md              # Feature specification with 39 functional requirements
├── plan.md              # Implementation plan with architecture decisions
├── tasks.md             # 110 implementation tasks organized by user story
├── research.md          # Technology stack research and decisions
├── data-model.md        # 9 domain entities with SQLite schema
├── quickstart.md        # Complete development setup guide
├── contracts/
│   └── health-api.yaml  # OpenAPI 3.0 specification for health API
└── checklists/
    ├── requirements.md  # Spec quality validation (PASSED)
    └── tasks.md         # Task completeness validation (PASSED)
```

### Source Code Structure (Planned)

```
src/
├── models/              # 9 domain entities (StreamSession, HealthMetric, etc.)
├── services/            # Business logic services
│   ├── obs_controller.py
│   ├── stream_manager.py
│   ├── health_monitor.py
│   ├── failover_manager.py
│   ├── owner_detector.py
│   ├── content_scheduler.py
│   └── startup_validator.py
├── api/
│   └── health.py        # FastAPI health endpoints
├── persistence/
│   ├── db.py            # SQLite schema and connection
│   └── repositories/    # CRUD operations
├── config/
│   ├── settings.py      # Pydantic configuration management
│   └── defaults.py      # Default OBS scene definitions
└── main.py              # Entry point and orchestration

tests/
├── unit/                # Service unit tests
├── integration/         # OBS integration tests
└── contract/            # API contract tests
```

**Status**: Source code not yet implemented - structure defined in plan.md

## Development Commands

### SpecKit Slash Commands (Claude Code)

- `/speckit.implement` - Execute implementation tasks from tasks.md
- `/speckit.analyze` - Re-run cross-artifact consistency analysis
- `/speckit.checklist` - Generate quality checklists

### Direct CLI Usage

```bash
./specify --help           # Show SpecKit help
./specify check            # Check required tools
./specify update           # Update SpecKit to latest version
```

## Constitutional Principles

**Tier 1 Scope**: OBS + Twitch Streaming Foundation (BLOCKING for all other tiers)

This implementation satisfies:
- **Principle I (Broadcast Continuity)**: 24/7 streaming, failover, automatic recovery
- **Principle IV (Owner Responsiveness)**: 10-second owner interrupt transitions
- **Principle V (System Reliability)**: Docker deployment, graceful degradation, monitoring

**NOT in Tier 1 scope**:
- ❌ Content decision engine (Tier 2: Intelligent Content Management)
- ❌ AI teaching personality (Tier 3: AI Teaching Personality)
- ❌ Discord integration (Tier 4: Supporting Infrastructure)

See [Constitution](.specify/memory/constitution.md) for complete principle definitions and tier discipline.

## Success Criteria

The system meets Tier 1 requirements when:

- **SC-001**: 99.9% uptime over any 7-day period (max 30 seconds downtime)
- **SC-002**: Auto-start streaming within 60 seconds of startup
- **SC-003**: Owner transitions complete in ≤10 seconds (95% of transitions)
- **SC-004**: Zero dead air >5 seconds during any 7-day period
- **SC-005**: Failover recovers within 5 seconds (100% success rate)
- **SC-006**: Dropped frames <1% during normal operation
- **SC-007**: Content transitions <2 seconds
- **SC-008**: Uptime metrics accurate to within 1 second
- **SC-009**: Owner can interrupt 5+ times per day without degradation

See [spec.md](specs/001-tier1-obs-streaming/spec.md) for complete success criteria definitions.

## Git Workflow

### What to Commit

**Commit these**:
- All files in `specs/` (specifications, plans, tasks)
- `.specify/memory/constitution.md` (project constitution)
- `docker-compose.yml`, `Dockerfile`, `requirements.txt`
- `src/` and `tests/` (when implemented)
- `config/` examples and documentation
- This `README.md`

**Don't commit** (already in .gitignore):
- `.speckit/` - SpecKit installation files (auto-regenerated)
- `.venv/` - Python virtual environment
- `data/` - SQLite database and state files
- `logs/` - Structured log output
- `__pycache__/` - Python bytecode

### Branch Strategy

- `main` - Planning artifacts and documentation
- `001-tier1-obs-streaming` - Tier 1 implementation (110 tasks)
- Future feature branches follow `NNN-feature-name` pattern

## Troubleshooting

### Pre-flight Validation Fails

**Error**: `obs_connectivity: fail`
- ✅ OBS Studio is running
- ✅ WebSocket server enabled (Tools → WebSocket Server Settings)
- ✅ Port 4455 accessible: `nc -zv localhost 4455`

**Error**: `failover_content: fail`
- ✅ Failover file exists and is playable
- ✅ Path in `config/settings.yaml` is correct

See [Quickstart Guide](specs/001-tier1-obs-streaming/quickstart.md) for complete troubleshooting section.

### Docker Issues

**"Cannot connect to Docker daemon"**
- Make sure Docker Desktop is running

**Permission errors on files**
- Run `./specify update` to clean and reinstall SpecKit

## Learn More

- [OBS Studio Documentation](https://obsproject.com/wiki/)
- [obs-websocket Protocol](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md)
- [Twitch Streaming Guidelines](https://help.twitch.tv/s/article/broadcasting-guidelines)
- [SpecKit Documentation](https://github.com/github/spec-kit)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## License

[Specify license - e.g., MIT, Apache 2.0, or link to LICENSE file]

---

**Version**: 1.0.0 (Tier 1 Planning Complete)
**Last Updated**: 2025-10-21
**Maintainer**: [Channel Owner]
**Framework**: SpecKit by GitHub + PRP (Product Requirements Prompt) by Rasmus Widing
