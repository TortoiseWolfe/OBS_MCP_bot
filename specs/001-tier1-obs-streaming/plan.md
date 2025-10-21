# Implementation Plan: Tier 1 OBS Streaming Foundation

**Branch**: `001-tier1-obs-streaming` | **Date**: 2025-10-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-tier1-obs-streaming/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build the foundational Tier 1 streaming infrastructure for 24/7 educational broadcasting on Twitch. System controls OBS programmatically to maintain continuous RTMP streaming with automatic failover, owner interrupt handling via source detection, stream health monitoring, and pre-flight validated auto-start. Implements constitutional Principle I (Broadcast Continuity), Principle IV (Owner Responsiveness), and Principle V (System Reliability).

## Technical Context

**Language/Version**: Python 3.11+ (asyncio for concurrent monitoring, mature obs-websocket libraries)
**Primary Dependencies**:
- obs-websocket-py (OBS control via WebSocket protocol)
- asyncio (concurrent health monitoring, source detection, failover logic)
- NEEDS CLARIFICATION: HTTP framework for health API/dashboard (FastAPI, Flask, or built-in http.server)
- NEEDS CLARIFICATION: Logging framework (structlog, python-json-logger, or stdlib logging)

**Storage**:
- SQLite for state persistence (uptime metrics, downtime events, owner sessions, stream health history)
- Filesystem for failover content verification and configuration

**Testing**: pytest with async support (pytest-asyncio), contract tests for OBS websocket interactions

**Target Platform**: Linux server (Docker containerized, host runs OBS Studio with obs-websocket plugin)

**Project Type**: Single service (streaming orchestration daemon)

**Performance Goals**:
- <10 second owner interrupt transitions (95th percentile)
- <5 second failover recovery (100% of failures)
- <30 second failure detection (OBS unresponsive, RTMP disconnect)
- <2 second content transition gaps
- Health metrics collection every 10 seconds

**Constraints**:
- 99.9% uptime requirement (max 30 seconds downtime per week)
- <1% dropped frames during normal operation
- Must run continuously 24/7 without manual intervention
- Auto-recovery from all transient failures (network, OBS crash, content failure)
- Pre-flight validation before streaming (no blind auto-start)

**Scale/Scope**:
- Single Twitch stream (one RTMP connection)
- 4 required OBS scenes minimum (Automated Content, Owner Live, Failover, Technical Difficulties)
- Configurable owner source monitoring (screen capture, camera, microphone sources)
- 7+ day continuous operation between planned maintenance

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Tier 1 Priority Compliance

✅ **PASS** - This feature IS Tier 1 ("OBS + Twitch Streaming - Job One")
- Implements all Tier 1 requirements: OBS programmatic control, 24/7 RTMP streaming, health monitoring, failover, content playback
- Constitutional mandate: "Tier 1 MUST be fully functional before Tier 2 development begins"

### Principle I: Broadcast Continuity (NON-NEGOTIABLE)

✅ **PASS** - Direct implementation of "stream must never go dark"
- FR-010: Auto-start streaming after pre-flight validation
- FR-025: Automatic failover within 5 seconds
- FR-015: 24/7 RTMP connection with auto-reconnection
- SC-001: 99.9% uptime target (30 seconds max downtime per week)
- SC-004: Zero dead air >5 seconds

### Principle IV: Owner Responsiveness

✅ **PASS** - "Owner can interrupt any programming instantly"
- FR-029-034: Source detection for owner "going live" (screen share, camera activation)
- FR-030: 10-second transitions to owner live scene
- SC-003: 95% of transitions ≤10 seconds
- Owner controls scene content via natural workflow (activate sources in OBS)

### Principle V: System Reliability

✅ **PASS** - "Stable operation within local hardware constraints"
- Docker containerized deployment (per spec assumptions)
- FR-024-028: Failover and automatic recovery
- FR-022: Detects complete stream failure within 30 seconds
- FR-009-013: Pre-flight validation with retry on failure
- FR-020: Persists uptime metrics across restarts

### Operational Standards - Broadcast Quality

✅ **PASS**
- FR-017: Configurable stream quality (resolution, bitrate, framerate) per Twitch guidelines
- FR-018: <1% dropped frames requirement
- FR-021: Degraded quality detection and logging

### Operational Standards - Technical Operations

✅ **PASS**
- Docker Compose orchestration (per assumptions)
- obs-websocket for programmatic OBS control (FR-002)
- State persistence via SQLite (Technical Context)
- FR-019-023: Health metrics collection and logging
- NEEDS CLARIFICATION: Monitoring dashboard implementation approach

### Development Workflow - Implementation Discipline

✅ **PASS** - No cross-tier dependencies
- This IS Tier 1, contains no Tier 2/3/4 features
- No content decision engine (Tier 2)
- No AI teaching personality (Tier 3)
- No Discord integration (Tier 4)

### Gate Evaluation

**Status**: ✅ **CLEARED FOR PHASE 0 RESEARCH**

**Outstanding Clarifications**: NONE - All resolved in Phase 0 research.md

**Final Technology Decisions** (from research.md):
1. HTTP framework: FastAPI (async-native, auto OpenAPI docs, type-safe)
2. Logging framework: structlog (JSON structured logs, context binding, async-safe)
3. Monitoring: Health API only (web dashboard deferred to Tier 4 per constitutional tier discipline)

**No violations to justify** - All constitutional requirements satisfied.

---

## Post-Design Re-Evaluation (Phase 1 Complete)

**Status**: ✅ **PASSED** - All constitutional gates satisfied post-design

### Technology Stack Validation

**Dependency Count**: 7 non-stdlib packages (constitutional simplicity maintained)
- obs-websocket-py (required for FR-001)
- FastAPI + uvicorn + pydantic (health API per FR-023)
- structlog (operational debugging per Principle V)
- aiosqlite (state persistence per FR-020)

**Complexity Justification**: All dependencies directly map to functional requirements or constitutional principles. No speculative or "nice-to-have" dependencies added.

### Tier Discipline Verification

✅ **PASS** - No Tier 2/3/4 features in design:
- research.md: Explicitly deferred web dashboard to Tier 4
- data-model.md: No content decision engine entities (Tier 2)
- contracts/: No AI personality API (Tier 3), no Discord webhooks (Tier 4)

### Data Model Validation

✅ **PASS** - All entities derived from spec Key Entities section:
- 9 entities mapped 1:1 to spec definitions
- SQLite schema enforces validation rules from functional requirements
- State persistence enables constitutional "no amnesia" requirement (Principle V)

### API Contract Validation

✅ **PASS** - Health API aligns with constitutional requirements:
- `/health` endpoint provides SC-001 uptime validation (99.9% target)
- `/health/metrics` enables SC-008 accuracy verification (within 1 second)
- `/health/uptime` generates constitutional compliance reports
- OpenAPI spec provides "Open Source transparency" (Principle VI)

### Quickstart Validation

✅ **PASS** - Development setup maintains simplicity:
- Zero-config SQLite (no PostgreSQL/Redis complexity)
- Local OBS + Docker deployment (Principle V: "local infrastructure")
- Pre-flight validation tested in quickstart (FR-009-013)
- Failover content setup required (constitutional "always available")

**Final Gate Status**: ✅ **CLEARED FOR PHASE 2 TASKS**

No design changes required. Proceed to `/speckit.tasks` to generate implementation task list.

## Project Structure

### Documentation (this feature)

```
specs/001-tier1-obs-streaming/
├── spec.md              # Feature specification with clarifications
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command) - PENDING
├── data-model.md        # Phase 1 output (/speckit.plan command) - PENDING
├── quickstart.md        # Phase 1 output (/speckit.plan command) - PENDING
├── contracts/           # Phase 1 output (/speckit.plan command) - PENDING
│   └── health-api.yaml  # OpenAPI spec for health monitoring API
├── checklists/          # Quality validation checklists
│   └── requirements.md  # Spec quality checklist (already completed)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT YET CREATED)
```

### Source Code (repository root)

```
src/
├── models/
│   ├── stream_session.py      # Stream Session entity
│   ├── content_source.py      # Content Source entity
│   ├── downtime_event.py      # Downtime Event entity
│   ├── health_metric.py       # Health Metric entity
│   ├── owner_session.py       # Owner Session entity
│   ├── schedule_block.py      # Schedule Block entity
│   ├── owner_source_config.py # Owner Source Configuration entity
│   ├── scene_config.py        # Scene Configuration entity
│   └── init_state.py          # System Initialization State entity
│
├── services/
│   ├── obs_controller.py      # OBS WebSocket connection and control (FR-001-008)
│   ├── stream_manager.py      # Streaming state management (FR-009-018)
│   ├── health_monitor.py      # Health metrics collection (FR-019-023)
│   ├── failover_manager.py    # Failover and recovery logic (FR-024-028)
│   ├── owner_detector.py      # Owner source detection (FR-029-034)
│   ├── content_scheduler.py   # Content playback scheduling (FR-035-039)
│   └── startup_validator.py   # Pre-flight validation (FR-009-013)
│
├── api/
│   └── health.py              # Health status API/dashboard (FR-023)
│
├── persistence/
│   ├── db.py                  # SQLite connection and schema
│   └── repositories/
│       ├── metrics.py         # Health metrics persistence
│       ├── sessions.py        # Stream/owner session persistence
│       └── events.py          # Downtime event persistence
│
├── config/
│   ├── settings.py            # Configuration management
│   └── defaults.py            # Default OBS scene definitions
│
└── main.py                    # Entry point with initialization orchestration

tests/
├── unit/
│   ├── test_obs_controller.py
│   ├── test_stream_manager.py
│   ├── test_health_monitor.py
│   ├── test_failover_manager.py
│   ├── test_owner_detector.py
│   ├── test_content_scheduler.py
│   └── test_startup_validator.py
│
├── integration/
│   ├── test_obs_integration.py      # Real OBS websocket interactions
│   ├── test_failover_scenarios.py   # End-to-end failover flows
│   └── test_owner_interrupt.py      # Owner source detection flows
│
└── contract/
    ├── test_health_api.py           # Health API contract tests
    └── test_obs_websocket.py        # OBS websocket protocol contracts
```

**Structure Decision**: Single project (Option 1) selected. This is a streaming orchestration daemon with no frontend/backend separation or mobile components. All logic runs in one Python service that controls OBS and maintains streaming state. Clean separation of concerns via services layer, with models for domain entities and persistence layer for SQLite state management.

## Complexity Tracking

*No constitutional violations - this section intentionally left empty.*

All complexity is justified by constitutional requirements:
- 99.9% uptime requires automatic failover, health monitoring, pre-flight validation
- Owner responsiveness requires source detection and scene switching
- System reliability requires state persistence and graceful degradation

No simpler alternatives exist that satisfy constitutional mandates.
