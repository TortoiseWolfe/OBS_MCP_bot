# Implementation Plan: Tier 2 Twitch Chat Bot

**Branch**: `002-twitch-chat-bot` | **Date**: 2025-10-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-twitch-chat-bot/spec.md`

## Summary

Build a Twitch IRC chat bot with AI-powered question answering using Claude API. The bot connects to Twitch IRC, responds to basic commands (!help, !uptime, !commands), processes AI questions via !ask command with queue management, and enforces rate limiting and moderation rules. Designed to handle 50-100 concurrent viewers without external cache servers (in-memory state).

**Technical Approach**: Use TwitchIO 2.10.0 for IRC connectivity, Anthropic SDK for AI responses with async worker pool pattern, and collections.deque for in-memory rate limiting. Extends existing OBS orchestrator architecture.

**Clarifications Applied**: During `/speckit.clarify`, resolved 5 key ambiguities:
1. AI response truncation strategy (context engineering + intelligent sentence-boundary truncation)
2. Queue overflow handling (reject with clear message, log for monitoring)
3. Inappropriate content detection (pattern-based spam detection for MVP, Claude filtering future)
4. Stream offline status messaging (transparent: "Stream is not currently live" vs "Stream status unavailable")
5. Queue metrics exposure (structured logging + /health endpoint)

## Technical Context

**Language/Version**: Python 3.11+ (matches existing OBS orchestrator)
**Primary Dependencies**: `twitchio==2.10.0`, `anthropic==0.40.0`, `anthropic[aiohttp]`
**Storage**: SQLite (extend existing `obs_bot.db` with moderation_events table)
**Testing**: pytest, pytest-asyncio (existing project stack)
**Target Platform**: Linux server (Docker container)
**Project Type**: Single project (extends existing `src/` structure)
**Performance Goals**: <2s response (simple commands 95%), <10s response (AI questions 90%), handle 100 concurrent viewers
**Constraints**: <500MB RAM, <10% CPU peak load, in-memory rate limiting (no Redis), non-blocking OBS operations
**Scale/Scope**: 50-100 concurrent viewers, max 100 queued AI requests, 4 commands (!help, !uptime, !commands, !ask)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ Tier 2 Prerequisites Met

- **Tier 1 Complete**: OBS streaming orchestrator fully functional and deployed
- **Tier Compliance**: This IS Tier 2 (Twitch Chat Bot) per Constitution v2.0.0
- **No Cross-Tier Dependencies**: Only dependency is Tier 1 Health API for !uptime (approved integration)

### ✅ Constitutional Principles

- **Principle I (Broadcast Continuity)**: Bot runs independently, won't disrupt streaming
- **Principle II (Educational Quality)**: AI responses provide technically accurate programming education
- **Principle V (System Reliability)**: In-memory design, graceful degradation, resource limits enforced
- **Principle VIII (Community Support)**: Primary goal - Twitch chat engagement for fast, ephemeral Q&A

### ✅ Operational Standards

- **Docker Compose orchestration**: Bot runs as separate container alongside OBS orchestrator
- **State persistence**: SQLite for moderation audit trail (ephemeral queue acceptable)
- **Logging**: Structured logging with audit trail for moderation actions
- **Monitoring**: Queue metrics exposed via health endpoint integration

**GATE STATUS**: ✅ PASS - No violations, proceed with implementation

## Project Structure

### Documentation (this feature)

```
specs/002-twitch-chat-bot/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command) ✅
├── data-model.md        # Phase 1 output (/speckit.plan command) ✅
├── quickstart.md        # Phase 1 output (/speckit.plan command) ✅
├── contracts/           # Phase 1 output (/speckit.plan command) ✅
│   └── service-contracts.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT YET CREATED)
```

### Source Code (repository root)

**Selected Structure**: Single project (extends existing OBS orchestrator codebase)

```
src/
├── models/
│   ├── chat_message.py           # NEW - ChatMessage entity
│   ├── bot_command.py             # NEW - BotCommand entity
│   ├── ai_question_request.py    # NEW - AIQuestionRequest entity
│   └── moderation_event.py       # NEW - ModerationEvent entity
├── services/
│   ├── twitch_chat_bot.py        # NEW - Main bot service (TwitchIO integration)
│   ├── claude_queue.py            # NEW - AI question queue and workers
│   ├── moderation.py              # NEW - Rate limiting and spam detection
│   └── stream_status_cache.py    # NEW - Cache for OBS Health API calls
├── config/
│   └── settings.py                # EXTEND - Add TwitchSettings and ClaudeSettings
└── persistence/
    └── repositories/
        └── moderation_events.py   # NEW - Moderation event repository

tests/
├── integration/
│   ├── test_twitch_chat_bot.py   # NEW - End-to-end bot tests
│   ├── test_claude_queue.py       # NEW - Queue and worker tests
│   └── test_moderation.py         # NEW - Rate limiting tests
└── unit/
    ├── test_bot_command_parsing.py  # NEW - Command parsing logic
    ├── test_spam_detection.py       # NEW - Spam detection algorithm
    └── test_rate_limiter.py          # NEW - Rate limiter unit tests
```

**Structure Decision**: Extend existing single project structure from Tier 1. No new top-level directories needed. All chat bot functionality lives in `src/services/` and `src/models/` following established patterns. This minimizes complexity and allows code reuse (database connection, logging, health monitoring).

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

**No violations** - Feature complies with all constitutional principles and tier prerequisites.

## Implementation Details (from /speckit.clarify)

### AI Response Handling (FR-010)

**Context Engineering Approach**:
1. System prompt instructs Claude for concise, chat-appropriate responses
2. Full user question context sent (no input truncation)
3. `max_tokens=150` as safety guardrail on output generation
4. If response >450 chars, intelligently truncate at last sentence boundary + append "..."

**Rationale**: max_tokens should not restrict conversation context, only output. Context engineering guides Claude to be concise naturally.

### Queue Overflow Strategy (FR-016)

**Defensive Handling**:
- Per-user rate limits (10/hour) make overflow unlikely with 100 concurrent viewers
- If queue reaches 100: reject new !ask with "Bot is currently busy, please try again in a moment (queue full)"
- Log all overflow events for capacity monitoring and alerting

**Rationale**: Clear failure signal prevents indefinite waiting, logs enable proactive scaling.

### Spam Detection Strategy (FR-013)

**Phase 1 (MVP)** - Pattern-based detection:
- Reject if >80% uppercase chars
- Reject if >5 consecutive repeated chars
- Reject if <20% alphabetic chars
- Reject if duplicate of same user's question within 60s
- Response: "Question does not meet bot guidelines"

**Phase 2 (Future)** - Claude-based content filtering using built-in safety features

**Rationale**: Simple patterns catch obvious spam, community moderation + rate limits handle edge cases.

### Stream Status Messaging (FR-027)

**Three Distinct Scenarios**:
1. Stream LIVE → "Stream has been live for X hours Y minutes"
2. Stream OFFLINE → "Stream is not currently live" (chat active pre/post-stream)
3. Health API DOWN → "Stream status unavailable"

**Rationale**: Twitch chat remains active when stream offline (pre-stream gathering, post-stream discussion). Transparent messaging follows best practices.

### Queue Metrics Monitoring (FR-020)

**Dual Approach**:
1. Structured logging to files (matches OBS orchestrator pattern) for historical analysis
2. `/health` endpoint for real-time monitoring:
```json
{
  "status": "healthy",
  "queue_depth": 12,
  "avg_wait_time_sec": 3.2,
  "peak_queue_depth_1h": 45,
  "connected_to_twitch": true
}
```

**Rationale**: Aligns with existing OBS health API (FR-026), enables operational visibility without external monitoring infrastructure.

## Phase 0: Research ✅

**Status**: Complete - All technology decisions documented in [research.md](./research.md)

**Key Decisions**:
- TwitchIO 2.10.0 for IRC connectivity (production-ready, native asyncio)
- Anthropic SDK with async client for Claude API integration
- collections.deque for in-memory rate limiting (sliding window)
- 10 concurrent workers with asyncio.Semaphore for queue processing

## Phase 1: Design & Contracts ✅

**Status**: Complete - All artifacts generated

**Artifacts**:
- [data-model.md](./data-model.md) - 6 entities with validation rules
- [contracts/service-contracts.md](./contracts/service-contracts.md) - Internal service APIs
- [quickstart.md](./quickstart.md) - Development setup guide
- CLAUDE.md updated via `.specify/scripts/bash/update-agent-context.sh claude`

## Phase 2: Task Breakdown

**Status**: PENDING - Run `/speckit.tasks` to generate tasks.md

**Next Command**: `/speckit.tasks` to create dependency-ordered implementation tasks
