# Implementation Tasks: Tier 1 OBS Streaming Foundation

**Feature**: 001-tier1-obs-streaming
**Branch**: `001-tier1-obs-streaming`
**Created**: 2025-10-20

## Overview

Implementation tasks organized by user story priority for independent, incremental delivery. Each user story phase can be implemented and tested independently, enabling parallel development and early MVP deployment.

**User Story Priorities** (from spec.md):
- **US1 (P1)**: Continuous Educational Broadcasting - 24/7 streaming with automated content
- **US2 (P2)**: Owner Live Broadcast Takeover - Owner interrupt handling via source detection
- **US3 (P3)**: Automatic Failover and Recovery - Resilience and automatic recovery
- **US4 (P4)**: Stream Health Monitoring - Health API and metrics collection

**Implementation Strategy**: MVP-first approach
- **MVP = US1 only**: Basic 24/7 streaming with pre-flight validation
- **US2**: Adds owner interrupt capability
- **US3**: Adds failover resilience
- **US4**: Adds operational visibility

---

## Phase 1: Project Setup

**Goal**: Initialize project structure, dependencies, and development environment per plan.md

**Tasks**:

- [ ] T001 Create project directory structure per plan.md (src/, tests/, config/, data/, logs/)
- [ ] T002 [P] Create requirements.txt with finalized dependencies from research.md
- [ ] T003 [P] Create Dockerfile for Python 3.11+ container
- [ ] T004 [P] Create docker-compose.yml for orchestrator service
- [ ] T005 [P] Create .gitignore excluding data/, logs/, .venv/, __pycache__
- [ ] T006 [P] Create config/settings.yaml with default configuration structure
- [ ] T007 [P] Create config/settings.py for configuration loading (Pydantic BaseSettings)
- [ ] T008 [P] Create config/defaults.py with default OBS scene definitions
- [ ] T009 [P] Setup structlog configuration in src/config/logging.py (JSON renderer, log rotation)
- [ ] T010 [P] Create src/__init__.py and package structure
- [ ] T011 [P] Create pytest.ini with async test configuration
- [ ] T012 Create README.md with quickstart instructions (link to quickstart.md)

**Completion Criteria**: Project builds, dependencies install, tests can run (empty test suite passes)

---

## Phase 2: Foundational Infrastructure

**Goal**: Implement shared infrastructure needed by all user stories (database, models, OBS connection)

**Tasks**:

- [ ] T013 [P] Create SQLite schema in src/persistence/db.py per data-model.md
- [ ] T014 [P] Implement StreamSession model in src/models/stream_session.py
- [ ] T015 [P] Implement DowntimeEvent model in src/models/downtime_event.py
- [ ] T016 [P] Implement HealthMetric model in src/models/health_metric.py
- [ ] T017 [P] Implement OwnerSession model in src/models/owner_session.py
- [ ] T018 [P] Implement ContentSource model in src/models/content_source.py
- [ ] T019 [P] Implement ScheduleBlock model in src/models/schedule_block.py
- [ ] T020 [P] Implement OwnerSourceConfiguration model in src/models/owner_source_config.py
- [ ] T021 [P] Implement SceneConfiguration model in src/models/scene_config.py
- [ ] T022 [P] Implement SystemInitializationState model in src/models/init_state.py
- [ ] T023 [P] Create metrics repository in src/persistence/repositories/metrics.py (CRUD for HealthMetric)
- [ ] T024 [P] Create sessions repository in src/persistence/repositories/sessions.py (CRUD for StreamSession, OwnerSession)
- [ ] T025 [P] Create events repository in src/persistence/repositories/events.py (CRUD for DowntimeEvent)
- [ ] T026 Implement OBSController service in src/services/obs_controller.py (WebSocket connection, scene switching per FR-001-008)
- [ ] T027 Test OBS connection and scene enumeration in tests/integration/test_obs_integration.py

**Completion Criteria**: Database schema created, all models implemented, OBS connection works, repositories tested

**Dependencies**: All user stories depend on Phase 2 completion

---

## Phase 3: User Story 1 - Continuous Educational Broadcasting (P1)

**Story Goal**: System auto-starts streaming on init and maintains 24/7 broadcast with content playback

**Independent Test**: Monitor stream uptime for 7 days, verify <30 seconds downtime (SC-001)

**Story Dependencies**: None (MVP story)

**Tasks**:

### Initialization & Pre-flight Validation

- [ ] T028 [US1] Implement pre-flight validation in src/services/startup_validator.py (FR-009-013: OBS connectivity, scenes exist, failover content, Twitch credentials, network)
- [ ] T029 [US1] Implement scene creation logic in src/services/obs_controller.py (FR-003-004: create missing scenes if not exist, never overwrite)
- [ ] T030 [US1] Implement initialization state persistence in startup_validator.py (save validation results to SystemInitializationState)

### Streaming Orchestration

- [ ] T031 [US1] Implement StreamManager service in src/services/stream_manager.py (FR-009-018: start/stop streaming, maintain RTMP connection, monitor connection status)
- [ ] T032 [US1] Implement automatic streaming start after pre-flight pass in stream_manager.py (FR-010: auto-start within 60 seconds)
- [ ] T033 [US1] Implement retry logic for failed pre-flight validation in startup_validator.py (retry every 60 seconds per edge case)
- [ ] T034 [US1] Implement stream session tracking in stream_manager.py (create StreamSession on start, update on events)

### Content Scheduling

- [ ] T035 [US1] Implement ContentScheduler service in src/services/content_scheduler.py (FR-035-039: play scheduled content per time blocks, transition between content <2 seconds)
- [ ] T036 [US1] Implement content file verification in content_scheduler.py (FR-037: verify files exist and playable before scheduling)
- [ ] T037 [US1] Implement content metadata handling in content_scheduler.py (FR-039: respect duration, age-appropriateness, time blocks)
- [ ] T038 [US1] Implement automatic content transitions in content_scheduler.py (FR-036: no dead air, <2 second gaps)

### Main Orchestrator

- [ ] T039 [US1] Implement main.py entry point (coordinate startup_validator, stream_manager, content_scheduler)
- [ ] T040 [US1] Implement graceful shutdown handling in main.py (persist state, stop streaming cleanly)
- [ ] T041 [US1] Implement Docker container restart handling in main.py (state persistence across restarts per FR-020)

### Integration Testing

- [ ] T042 [US1] Create integration test for pre-flight validation in tests/integration/test_obs_integration.py
- [ ] T043 [US1] Create integration test for auto-start streaming in tests/integration/test_obs_integration.py
- [ ] T044 [US1] Create integration test for content playback and transitions in tests/integration/test_obs_integration.py

**US1 Acceptance Criteria**:
- ✅ System auto-starts streaming after pre-flight validation passes
- ✅ Stream remains live for 7+ days with <30 seconds downtime
- ✅ Content transitions occur smoothly with <2 second gaps
- ✅ State persists across Docker container restarts

**Parallel Execution Notes**: T028-T030 can run parallel with T031-T034. T035-T038 depends on T031 (StreamManager). T039-T041 must be sequential after all services complete.

---

## Phase 4: User Story 2 - Owner Live Broadcast Takeover (P2)

**Story Goal**: Owner can interrupt automated content by activating sources in OBS, system detects and transitions within 10 seconds

**Independent Test**: Activate owner screen capture source during automated content, verify transition <10 seconds, verify resume after deactivation

**Story Dependencies**: Requires US1 (streaming orchestration must be working)

**Tasks**:

### Owner Source Detection

- [ ] T045 [US2] Implement OwnerDetector service in src/services/owner_detector.py (FR-029-034: monitor designated sources, detect activation/deactivation)
- [ ] T046 [US2] Implement source activation detection in owner_detector.py (FR-029: poll source status every 1 second, check enabled state)
- [ ] T047 [US2] Implement debounce logic in owner_detector.py (FR-034: configurable debounce time to prevent false triggers, default 5 seconds)
- [ ] T048 [US2] Implement source deactivation detection in owner_detector.py (FR-032: detect when sources become inactive)

### Owner Transition Logic

- [ ] T049 [US2] Implement owner live transition in stream_manager.py (FR-030: switch to "Owner Live" scene within 10 seconds)
- [ ] T050 [US2] Implement content state saving in content_scheduler.py (FR-031: save current content state for resume)
- [ ] T051 [US2] Implement owner session tracking in owner_detector.py (create OwnerSession record with transition time)
- [ ] T052 [US2] Implement automated content resume in content_scheduler.py (FR-032: resume after owner sources deactivate)
- [ ] T053 [US2] Implement smooth transition effects in stream_manager.py (FR-033: audio fade, visual transition)

### Edge Case Handling

- [ ] T054 [US2] Implement owner source readiness check in owner_detector.py (edge case: wait 30 seconds for source to become properly active)
- [ ] T055 [US2] Implement "going live soon" scene in stream_manager.py (edge case: display if source not ready after 30 seconds)

### Integration Testing

- [ ] T056 [US2] Create integration test for owner interrupt in tests/integration/test_owner_interrupt.py
- [ ] T057 [US2] Create integration test for owner transition timing in tests/integration/test_owner_interrupt.py (verify <10 seconds per SC-003)
- [ ] T058 [US2] Create integration test for content resume in tests/integration/test_owner_interrupt.py

**US2 Acceptance Criteria**:
- ✅ Owner source activation triggers transition within 10 seconds (95% of transitions)
- ✅ Automated content resumes after owner sources deactivate
- ✅ Transition is smooth with audio fade and visual effects
- ✅ OwnerSession records include transition time for analysis

**Parallel Execution Notes**: T045-T048 (detection logic) can run parallel with T049-T053 (transition logic) until integration in main.py.

---

## Phase 5: User Story 3 - Automatic Failover and Recovery (P3)

**Story Goal**: System automatically detects content failures and switches to failover content within 5 seconds, recovers from OBS crashes

**Independent Test**: Simulate content source failure (file not found, playback error), verify failover <5 seconds and incident logging

**Story Dependencies**: Requires US1 (streaming and content scheduling must be working)

**Tasks**:

### Failover Detection

- [ ] T059 [US3] Implement FailoverManager service in src/services/failover_manager.py (FR-024-028: detect failures, coordinate recovery)
- [ ] T060 [US3] Implement content failure detection in failover_manager.py (FR-026: detect file not found, playback errors, source timeouts)
- [ ] T061 [US3] Implement OBS crash detection in failover_manager.py (FR-027: detect unresponsive OBS via websocket connection loss, <30 seconds)
- [ ] T062 [US3] Implement RTMP disconnect detection in failover_manager.py (FR-022: detect connection lost, <30 seconds)

### Failover Recovery

- [ ] T063 [US3] Implement failover content management in failover_manager.py (FR-024: maintain pre-configured failover content, test on startup)
- [ ] T064 [US3] Implement automatic failover scene switch in failover_manager.py (FR-025: switch to "Failover" scene within 5 seconds)
- [ ] T065 [US3] Implement OBS restart logic in failover_manager.py (FR-027: restart OBS via Docker if unresponsive, max 3 attempts)
- [ ] T066 [US3] Implement RTMP reconnection logic in stream_manager.py (FR-015: auto-reconnect every 10 seconds)

### Downtime Event Logging

- [ ] T067 [US3] Implement downtime event recording in failover_manager.py (FR-028: log timestamp, failure type, recovery action, duration)
- [ ] T068 [US3] Implement failover event categorization in failover_manager.py (FailureCause enum: connection_lost, obs_crash, content_failure, etc.)
- [ ] T069 [US3] Implement automatic vs manual recovery tracking in downtime events

### Edge Case Handling

- [ ] T070 [US3] Implement "technical difficulties" fallback in failover_manager.py (edge case: when both primary and failover content fail)
- [ ] T071 [US3] Implement manual stream stop detection in stream_manager.py (edge case: owner manually stops OBS streaming, auto-restart within 10 seconds)
- [ ] T072 [US3] Implement stream key validation in stream_manager.py (edge case: verify stream key still valid after reconnection)

### Integration Testing

- [ ] T073 [US3] Create integration test for content failure failover in tests/integration/test_failover_scenarios.py
- [ ] T074 [US3] Create integration test for OBS crash recovery in tests/integration/test_failover_scenarios.py
- [ ] T075 [US3] Create integration test for RTMP reconnection in tests/integration/test_failover_scenarios.py
- [ ] T076 [US3] Create integration test for downtime event logging in tests/integration/test_failover_scenarios.py

**US3 Acceptance Criteria**:
- ✅ Content failures trigger failover within 5 seconds (100% success rate per SC-005)
- ✅ OBS crashes are detected within 30 seconds and automatic restart attempted
- ✅ RTMP disconnects trigger reconnection every 10 seconds
- ✅ All failover events are logged with complete diagnostic information

**Parallel Execution Notes**: T059-T062 (detection logic) can run parallel with T063-T066 (recovery logic). T067-T069 (logging) can run parallel with recovery logic.

---

## Phase 6: User Story 4 - Stream Health Monitoring (P4)

**Story Goal**: Health API provides real-time stream metrics and uptime reports for operational visibility

**Independent Test**: Query `/health` endpoint during streaming, verify accurate real-time metrics and uptime calculation

**Story Dependencies**: Requires US1 (streaming must be working for metrics collection)

**Tasks**:

### Health Metrics Collection

- [ ] T077 [US4] Implement HealthMonitor service in src/services/health_monitor.py (FR-019-023: collect metrics every 10 seconds)
- [ ] T078 [US4] Implement bitrate collection in health_monitor.py (FR-019: query OBS for current bitrate)
- [ ] T079 [US4] Implement dropped frames collection in health_monitor.py (FR-019: query OBS for dropped frames percentage)
- [ ] T080 [US4] Implement CPU usage collection in health_monitor.py (FR-019: system CPU usage)
- [ ] T081 [US4] Implement connection status polling in health_monitor.py (FR-019: RTMP connection state)
- [ ] T082 [US4] Implement health metric persistence in health_monitor.py (FR-020: save metrics to database every 10 seconds)

### Quality Detection

- [ ] T083 [US4] Implement degraded quality detection in health_monitor.py (FR-021: log warning when dropped frames >1%)
- [ ] T084 [US4] Implement failure detection in health_monitor.py (FR-022: detect complete failure within 30 seconds)

### Health API

- [ ] T085 [US4] Implement FastAPI app in src/api/health.py per contracts/health-api.yaml
- [ ] T086 [US4] Implement GET /health endpoint in health.py (return current health snapshot)
- [ ] T087 [US4] Implement GET /health/metrics endpoint in health.py (query historical metrics with filters)
- [ ] T088 [US4] Implement GET /health/uptime endpoint in health.py (generate uptime report for SC-001 validation)
- [ ] T089 [US4] Implement uptime calculation logic in health.py (calculate uptime percentage per data-model.md)
- [ ] T090 [US4] Implement transition time analysis in health.py (analyze owner transitions per data-model.md)
- [ ] T091 [US4] Implement failover performance analysis in health.py (analyze failover recovery times)

### API Integration

- [ ] T092 [US4] Integrate FastAPI server into main.py (launch uvicorn in background thread)
- [ ] T093 [US4] Implement CORS configuration for health API (allow localhost access during development)

### Contract Testing

- [ ] T094 [US4] Create contract test for GET /health in tests/contract/test_health_api.py
- [ ] T095 [US4] Create contract test for GET /health/metrics in tests/contract/test_health_api.py
- [ ] T096 [US4] Create contract test for GET /health/uptime in tests/contract/test_health_api.py

**US4 Acceptance Criteria**:
- ✅ Health metrics collected every 10 seconds and persisted
- ✅ `/health` endpoint returns accurate real-time stream status
- ✅ `/health/uptime` report validates SC-001 (99.9% uptime requirement)
- ✅ Degraded quality (>1% dropped frames) triggers warnings

**Parallel Execution Notes**: T077-T082 (metrics collection) can run parallel with T085-T091 (API endpoints). T094-T096 (contract tests) can run parallel after API is implemented.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Goal**: Final integration, documentation, and production readiness

**Tasks**:

- [ ] T097 [P] Add comprehensive logging to all services (structured JSON logs with context binding)
- [ ] T098 [P] Implement log rotation in src/config/logging.py (30 days retention, 1GB max per edge case)
- [ ] T099 [P] Create Docker healthcheck in docker-compose.yml (check `/health` endpoint)
- [ ] T100 [P] Create .dockerignore excluding unnecessary files from container
- [ ] T101 Update README.md with production deployment instructions
- [ ] T102 Create example config/settings.yaml with all required fields documented
- [ ] T103 [P] Add error handling and edge case coverage across all services
- [ ] T104 Implement comprehensive error messages for pre-flight validation failures
- [ ] T105 [P] Add type hints throughout codebase (enable mypy validation)
- [ ] T106 Run full integration test suite across all user stories
- [ ] T107 Verify SC-001 through SC-009 success criteria in integration tests
- [ ] T108 Create sample failover content for quickstart testing
- [ ] T109 Document owner source configuration examples in quickstart.md
- [ ] T110 Create systemd service file for production deployment (optional)

**Completion Criteria**: All user stories pass independent tests, SC-001 through SC-009 validated, production-ready Docker deployment

---

## Dependency Graph

### User Story Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational)
    ↓
    ├──→ US1 (P1) - Continuous Broadcasting [MVP]
    │         ↓
    │         ├──→ US2 (P2) - Owner Interrupt (depends on US1 streaming)
    │         │
    │         ├──→ US3 (P3) - Failover (depends on US1 content scheduling)
    │         │
    │         └──→ US4 (P4) - Health Monitoring (depends on US1 streaming)
    │
    └──→ Phase 7 (Polish) - Can start after US1, runs parallel with US2/3/4
```

**Critical Path**: Phase 1 → Phase 2 → US1 (MVP)
**Parallel Opportunities**: US2, US3, US4 can be developed in parallel after US1 is complete

### Task Dependencies Within Phases

**US1 Internal Dependencies**:
- T028-T030 (pre-flight) → T031 (stream manager) → T039 (main orchestrator)
- T035-T038 (content scheduler) → T031 (stream manager)
- T042-T044 (tests) depend on all services

**US2 Internal Dependencies**:
- T045-T048 (detection) + T049-T053 (transition) → T056-T058 (tests)

**US3 Internal Dependencies**:
- T059-T062 (detection) + T063-T066 (recovery) → T073-T076 (tests)

**US4 Internal Dependencies**:
- T077-T082 (collection) → T085-T091 (API) → T094-T096 (tests)

---

## Parallel Execution Examples

### After Phase 2 Completion

**Parallel Track A** (US1 team):
- T028-T030, T031-T034, T035-T038 (streaming core)

**Parallel Track B** (US2 team):
- Design owner detection logic (can start planning while US1 completes)

**Parallel Track C** (US4 team):
- T077-T082 (health metrics collection - only needs streaming to exist)

### After US1 Completion (MVP Ready)

**Parallel Track A** (US2 team):
- T045-T055 (owner interrupt implementation)

**Parallel Track B** (US3 team):
- T059-T072 (failover implementation)

**Parallel Track C** (US4 team):
- T085-T091 (health API implementation)

**Parallel Track D** (Polish team):
- T097-T105 (logging, error handling, type hints)

---

## Implementation Strategy

### Recommended Approach: MVP-First

1. **Sprint 1** (MVP): Complete Phase 1 → Phase 2 → US1
   - **Deliverable**: System that auto-starts streaming and maintains 24/7 broadcast
   - **Value**: Constitutional Principle I (Broadcast Continuity) satisfied
   - **Testing**: Can run for 7 days and validate SC-001 (99.9% uptime)

2. **Sprint 2** (Owner Control): Complete US2
   - **Deliverable**: Owner can interrupt automated programming
   - **Value**: Constitutional Principle IV (Owner Responsiveness) satisfied
   - **Testing**: Activate sources in OBS, verify <10 second transitions

3. **Sprint 3** (Resilience): Complete US3
   - **Deliverable**: Automatic failover and recovery from failures
   - **Value**: Constitutional Principle V (System Reliability) enhanced
   - **Testing**: Simulate failures, verify <5 second recovery

4. **Sprint 4** (Visibility): Complete US4 + Phase 7
   - **Deliverable**: Health API and operational monitoring
   - **Value**: Operational visibility for SC-001 validation
   - **Testing**: Query health endpoints, validate uptime calculations

### Alternative: Feature Team Parallel Development

After US1 MVP is complete, assign teams to US2/3/4 concurrently:
- **Team A**: US2 (owner interrupt)
- **Team B**: US3 (failover)
- **Team C**: US4 (health monitoring)
- **Team D**: Polish & integration

**Risk**: Requires more coordination, but delivers all features faster.

---

## Task Summary

**Total Tasks**: 110
- **Phase 1 (Setup)**: 12 tasks
- **Phase 2 (Foundational)**: 15 tasks
- **Phase 3 (US1)**: 17 tasks
- **Phase 4 (US2)**: 14 tasks
- **Phase 5 (US3)**: 18 tasks
- **Phase 6 (US4)**: 20 tasks
- **Phase 7 (Polish)**: 14 tasks

**Parallelizable Tasks**: 67/110 (61% marked with [P])

**User Story Task Distribution**:
- US1 (P1): 17 tasks (MVP scope)
- US2 (P2): 14 tasks
- US3 (P3): 18 tasks
- US4 (P4): 20 tasks
- Infrastructure: 41 tasks (Setup + Foundational + Polish)

**Independent Test Criteria Met**: All 4 user stories have independent acceptance criteria and integration tests

**MVP Scope**: Phase 1 + Phase 2 + Phase 3 (US1) = 44 tasks → working 24/7 streaming system

---

## Success Criteria Validation

**Success Criteria Coverage** (from spec.md SC-001 through SC-009):

- **SC-001** (99.9% uptime): Validated via US1 7-day test + US4 `/health/uptime` endpoint
- **SC-002** (auto-start <60 sec): Validated via US1 T032-T033 (pre-flight validation)
- **SC-003** (owner transitions <10 sec): Validated via US2 T051 + T057 (transition time tracking)
- **SC-004** (zero dead air >5 sec): Validated via US1 T038 (content transitions) + US3 T064 (failover)
- **SC-005** (failover <5 sec): Validated via US3 T064 + T073 (failover timing test)
- **SC-006** (stream quality <1% dropped): Validated via US4 T079 + T083 (quality detection)
- **SC-007** (content transition <2 sec): Validated via US1 T038 (transition logic)
- **SC-008** (uptime metrics accuracy): Validated via US4 T089 (uptime calculation)
- **SC-009** (owner interrupt 5x/day): Validated via US2 T056-T058 (owner interrupt tests)

All success criteria have corresponding implementation tasks and validation tests.
