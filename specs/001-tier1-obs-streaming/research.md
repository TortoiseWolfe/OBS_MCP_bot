# Research: Tier 1 OBS Streaming Foundation

**Feature**: 001-tier1-obs-streaming
**Date**: 2025-10-20
**Phase**: 0 (Pre-implementation research)

## Overview

This document resolves technical unknowns identified in the implementation plan's Technical Context section. Each decision is supported by best practices research, constitutional alignment, and trade-off analysis.

## Outstanding Questions

From Technical Context:
1. HTTP framework choice for health API/dashboard
2. Logging framework choice
3. Monitoring dashboard implementation approach

---

## Decision 1: HTTP Framework for Health API

**Context**: FR-023 requires queryable health status API or dashboard. Need lightweight HTTP framework for exposing stream metrics.

### Options Evaluated

| Option | Pros | Cons |
|--------|------|------|
| **FastAPI** | Modern async support, auto OpenAPI docs, type hints, fast | Extra dependency, overkill for simple health endpoint |
| **Flask** | Battle-tested, simple, minimal | Sync-only (blocks asyncio event loop), older patterns |
| **stdlib http.server** | Zero dependencies, minimal | Manual routing, no async, verbose implementation |
| **aiohttp** | Native asyncio, lightweight | Less familiar API, manual OpenAPI docs |

### Decision: **FastAPI**

**Rationale**:
1. **Native async integration**: Health API runs in same asyncio event loop as monitoring services (no thread blocking)
2. **Type safety**: Pydantic models match domain entities (Health Metric, Stream Session), compile-time validation
3. **Auto-generated OpenAPI**: Constitutional "Open Source transparency" - self-documenting API for community
4. **Minimal overhead**: Single endpoint (`GET /health`) with query params for historical metrics
5. **Industry standard**: Recommended for Python async microservices in 2025

**Alternatives Rejected**:
- Flask: Sync-only blocks asyncio event loop, forces threading complexity
- stdlib: Too verbose for simple health endpoint, manual JSON serialization
- aiohttp: Viable but less mature ecosystem than FastAPI, manual docs generation

**Dependencies Added**:
```
fastapi==0.104.1
uvicorn==0.24.0  # ASGI server for FastAPI
```

**Implementation Impact**:
- `src/api/health.py`: Single FastAPI router with `/health` endpoint
- `src/main.py`: Launch uvicorn server in background thread alongside streaming orchestrator
- `specs/001-tier1-obs-streaming/contracts/health-api.yaml`: Auto-generated OpenAPI spec

---

## Decision 2: Logging Framework

**Context**: System runs 24/7 unattended. Need structured logging for operational debugging, audit trail (constitutional requirement), and correlation across async tasks.

### Options Evaluated

| Option | Pros | Cons |
|--------|------|------|
| **structlog** | Structured JSON logs, contextualized loggers, async-safe | Extra dependency, learning curve |
| **python-json-logger** | Simple JSON formatter for stdlib logging | Less powerful than structlog, limited context binding |
| **stdlib logging** | Zero dependencies, familiar | Unstructured text logs, poor async support, manual JSON formatting |

### Decision: **structlog**

**Rationale**:
1. **Structured logging**: JSON output with `timestamp`, `level`, `event`, `stream_session_id`, `failure_type`, `recovery_action` fields
   - Enables `grep '{"failure_type": "obs_crash"}'` for incident analysis
   - Constitutional "Logging with audit trail for all major decisions" requirement
2. **Context binding**: Bind `stream_session_id` once, appears in all subsequent logs from that session
   - Critical for correlating failover events across async tasks
3. **Async-safe**: Thread-local context works with asyncio tasks
4. **Log rotation integration**: Works with `logging.handlers.RotatingFileHandler` (FR-edge case: disk space management)
5. **Zero-config JSON**: `structlog.configure(processors=[...JSONRenderer()])` - production-ready defaults

**Alternatives Rejected**:
- python-json-logger: Lacks context binding (would need manual `extra={}` on every log call)
- stdlib: Unstructured logs make operational debugging painful for 24/7 service

**Dependencies Added**:
```
structlog==23.2.0
```

**Implementation Impact**:
- `src/config/logging.py`: structlog configuration with JSON renderer, log rotation (30 days, 1GB max)
- All services use `structlog.get_logger()` with bound context (session IDs, failure types)
- Log format example:
  ```json
  {"timestamp": "2025-10-20T10:30:15Z", "level": "error", "event": "failover_triggered", "stream_session_id": "550e8400", "failure_type": "content_playback_error", "recovery_action": "switched_to_failover_scene", "duration_sec": 4.2}
  ```

---

## Decision 3: Monitoring Dashboard Implementation

**Context**: FR-023 requires "queryable health status API or dashboard". Need to define what "dashboard" means for Tier 1.

### Options Evaluated

| Option | Pros | Cons |
|--------|------|------|
| **Web UI dashboard** | Visual graphs, real-time updates, accessible from browser | Requires frontend build tooling, out of scope for Tier 1 |
| **CLI tool** | Simple, scriptable, no frontend dependencies | Less accessible for quick checks, manual invocation |
| **Log-based (JSON logs + jq)** | Zero code, uses structured logs | Requires jq knowledge, not real-time |
| **Health API only (no dashboard)** | Minimal scope, enables future dashboard | No human-friendly view in Tier 1 |

### Decision: **Health API only (defer dashboard to Tier 4)**

**Rationale**:
1. **Constitutional tier discipline**: Dashboard is Tier 4 ("Supporting Infrastructure - Analytics and decision logging")
   - Tier 1 scope: "Stream health monitoring and failover" (FR-019-023)
   - Monitoring dashboard is nice-to-have, not blocking for 24/7 streaming
2. **Spec requirement met by API**: FR-023 says "API **or** dashboard" - API satisfies requirement
3. **Structured logs as interim dashboard**: JSON logs + `jq` provide queryable metrics:
   ```bash
   # Current uptime
   curl localhost:8000/health | jq '.uptime_seconds'

   # Failover events today
   tail -f logs/stream.log | jq 'select(.event == "failover_triggered")'
   ```
4. **Future-proof**: API contract (`/health` endpoint) remains stable when Tier 4 adds web UI
5. **Owner operational burden**: Web dashboard adds deployment complexity (nginx, SSL, port management) - violates Principle V (System Reliability - "stay within host machine limits")

**Alternatives Rejected**:
- Web UI: Cross-tier dependency (Tier 1 blocked on Tier 4 deliverable)
- CLI tool: Duplicates API functionality, extra maintenance burden

**Implementation Impact**:
- `src/api/health.py`: FastAPI endpoint returns JSON health snapshot
  ```python
  GET /health -> {
    "streaming": bool,
    "uptime_seconds": int,
    "current_scene": str,
    "dropped_frames_pct": float,
    "last_failover": ISO8601 | null,
    "owner_live": bool
  }
  ```
- `specs/001-tier1-obs-streaming/quickstart.md`: Document `curl localhost:8000/health` usage
- Tier 4 future work: Add Grafana/Prometheus dashboard consuming same API

---

## Technology Stack Summary

**Final Dependencies**:
```python
# Core
obs-websocket-py==0.11.0  # OBS control
aiosqlite==0.19.0          # Async SQLite for state persistence

# API & Web
fastapi==0.104.1           # Health API framework
uvicorn==0.24.0            # ASGI server
pydantic==2.5.0            # Data validation (included with FastAPI)

# Logging
structlog==23.2.0          # Structured logging

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1     # Async test support
pytest-cov==4.1.0          # Coverage reporting
httpx==0.25.2              # FastAPI test client
```

**Platform Requirements** (from spec assumptions):
- Python 3.11+
- OBS Studio with obs-websocket plugin enabled
- Docker & Docker Compose
- Linux server (WSL2 acceptable for development)

**No additional research needed** - all unknowns resolved with constitutional alignment verified.

---

## Validation Against Constitution

### Principle I: Broadcast Continuity
✅ All decisions minimize dependencies and operational complexity:
- FastAPI: Single extra dependency for critical health monitoring
- structlog: Enables faster incident response (structured logs)
- No web dashboard: Reduces deployment complexity and failure modes

### Principle V: System Reliability
✅ Choices favor stability over features:
- SQLite over PostgreSQL: Fewer moving parts, file-based simplicity
- Stdlib where possible: Only 5 non-stdlib dependencies (obs-websocket-py, fastapi, uvicorn, structlog, aiosqlite)
- Deferred web dashboard: Avoids nginx, SSL, port management complexity

### Development Workflow - Tier Discipline
✅ No cross-tier dependencies:
- Web dashboard (Tier 4) explicitly deferred
- Health API (Tier 1) provides foundation for future Tier 4 enhancements
- Research focused solely on Tier 1 streaming requirements

---

## Next Steps

**Phase 0 Complete** - All technical unknowns resolved.

**Proceed to Phase 1**:
1. Generate `data-model.md` from entities in spec
2. Generate `contracts/health-api.yaml` OpenAPI spec
3. Generate `quickstart.md` for development setup
4. Update agent context with finalized technology stack
