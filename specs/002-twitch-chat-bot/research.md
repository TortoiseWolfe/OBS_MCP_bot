# Research Report: Tier 2 Twitch Chat Bot

**Date**: 2025-10-22
**Feature**: Twitch Chat Bot
**Phase**: Pre-implementation Research

## Overview

This document consolidates technical research for implementing a Twitch IRC chat bot with AI-powered responses, rate limiting, and moderation capabilities.

---

## Decision 1: Twitch IRC Library

**Decision**: Use **TwitchIO 2.10.0** (legacy IRC version)

### Rationale

- **Production-ready**: 857 GitHub stars, 65+ contributors, extensive documentation
- **Native asyncio**: Perfect fit for existing Python 3.11+ architecture
- **Built-in features**: Automatic reconnection, partial rate limiting, IRC parsing
- **Type safety**: Full type annotations align with FastAPI/Pydantic patterns
- **Low latency**: Direct IRC connection achieves <500ms requirement
- **Docker-friendly**: Pure Python, no GUI dependencies

### Alternatives Considered

1. **python-twitch-irc**: Abandoned (last commit Feb 2021), no rate limiting, minimal docs
2. **Custom Pydle implementation**: Higher development effort, no Twitch-specific features
3. **TwitchIO 3.x EventSub**: Future consideration, but adds complexity for MVP

### Important Caveats

- Using legacy IRC version (v3.x dropped IRC support)
- Must implement application-level rate limiting (20 msg/30s)
- Twitch recommends EventSub over IRC (migration path available)
- Pin to `twitchio==2.10.0` to maintain IRC support

### Implementation Notes

```python
# requirements.txt
twitchio==2.10.0

# Key features:
- Auto-reconnection on RECONNECT messages
- Commands extension for bot commands
- Rate limit handling for channel joins
- WebSocket support
```

---

## Decision 2: AI Integration (Claude API)

**Decision**: Use **Official Anthropic SDK** (`anthropic` package) with async client

### Rationale

- **Official support**: Maintained by Anthropic, native async/await
- **Built-in features**: Retry logic (2 retries default), timeout management, error handling
- **Performance**: Optional `aiohttp` backend for better concurrency
- **Type safety**: Full type annotations
- **Production patterns**: Well-documented async request patterns

### Architecture Pattern

**Producer-Consumer with Worker Pool**:
- `asyncio.Queue(maxsize=100)` for FIFO queue
- 10 concurrent workers with `asyncio.Semaphore` for concurrency control
- Separate response queue for decoupling API calls from IRC responses

### Rate Limiting Strategy (Three Layers)

1. **Per-User**: 1 question/60 seconds (application requirement) - timestamp tracking
2. **Concurrency**: `asyncio.Semaphore(10)` to limit simultaneous API calls
3. **API Limits**: Token bucket for Tier 1 (50 RPM, 30K ITPM, 8K OTPM)

### Performance Estimates

- **Throughput**: 10 workers × ~3s avg API latency = 2-3 requests/second
- **Queue drainage**: 100 queued requests = ~50s to drain when full
- **Response time**: <10s timeout enforced (90% target)
- **Token usage**: 450 chars ≈ 113 tokens → use `max_tokens=150`

### Cost Estimate

**Claude Sonnet (Tier 1)**:
- ~$2.40/day = $72/month for 1000 questions/day
- Prompt caching: Save ~$4/month on repeated system prompts

### Implementation Notes

```python
# requirements.txt
anthropic==0.40.0
anthropic[aiohttp]  # For better async performance

# Configuration:
- 10 concurrent workers
- 10 second timeout per request
- 100 max queued requests
- Automatic retry on 429/5xx errors
```

---

## Decision 3: Rate Limiting & Moderation

**Decision**: Use **in-memory data structures** (no external cache servers)

### Data Structures

1. **`collections.deque`**: Sliding window rate limiting
   - O(1) append/pop operations
   - Automatic FIFO with `maxlen`
   - Thread-safe for basic operations

2. **`dict` + lazy cleanup**: User state management
   - Per-user tracking with `__slots__` for memory efficiency
   - Lazy cleanup on access (no background tasks initially)

3. **`asyncio.Semaphore`**: Global concurrency control
   - Limit 100 concurrent request processing

4. **`hash()` + deque**: Fast spam detection
   - No ML required for duplicate detection
   - <1ms per check

### Performance Characteristics

- **Memory**: ~300KB for 100 active users
- **Latency**: <1ms per check (rate limiting + spam detection)
- **Scalability**: Handles 100 concurrent viewers easily

### Rate Limiting Implementation

**Per-User Limits**:
- 1 command per 60 seconds (command rate limit)
- 10 commands per hour (hard limit)
- 30 seconds between identical commands (command cooldown)

**Global Limits**:
- 100 concurrent requests max (semaphore)
- 20 outgoing messages per 30 seconds (Twitch IRC rate limit)

**Spam Detection**:
- 3+ identical messages in 60 seconds = timeout (5 minutes)
- Pattern-based detection (character repetition, excessive caps)

### Implementation Notes

```python
# Key patterns:
- Use time.monotonic() for all timing
- Implement lazy cleanup (no background tasks)
- Use __slots__ for memory efficiency (~40% savings)
- Periodic cleanup every 5 minutes for inactive users
```

---

## Decision 4: Integration with OBS Orchestrator

**Decision**: Query existing **Health API** for stream status

### Integration Points

1. **Stream Uptime**: Query `/health` endpoint for current session
2. **Stream Status**: Check if streaming is active
3. **Health Metrics**: Access stream health for debugging

### Implementation

```python
# Use existing httpx client from OBS orchestrator
import httpx

async def get_stream_uptime() -> str:
    """Query OBS orchestrator for stream uptime"""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/health")
        data = response.json()
        # Parse uptime from response
        return format_uptime(data['streaming_session']['uptime_seconds'])
```

### Cache Strategy

- Cache stream status for 10 seconds to reduce API calls
- Invalidate cache on explicit stream state changes

---

## Technical Context Summary

### Technology Stack

**Language**: Python 3.11+
**Primary Dependencies**:
- `twitchio==2.10.0` - Twitch IRC connectivity
- `anthropic==0.40.0` - Claude API integration
- `anthropic[aiohttp]` - Async HTTP performance
- `httpx` - HTTP client (already in project)
- `aiosqlite` - Persistence (already in project)

**Storage**: SQLite (extend existing `obs_bot.db`)
**Testing**: pytest, pytest-asyncio (already in project)
**Target Platform**: Linux server (Docker container)
**Project Type**: Single project (extends existing `src/` structure)

### Performance Goals

- **Response time**: <2s for simple commands (!help, !uptime), <10s for AI questions (90%)
- **Throughput**: Handle 100 concurrent viewers
- **Latency**: IRC message latency <500ms
- **Resource usage**: <500MB RAM, <10% CPU during peak load

### Constraints

- **Memory**: In-memory rate limiting (no Redis/Memcached)
- **Docker deployment**: Containerized alongside OBS orchestrator
- **No blocking**: Must not block OBS/Twitch IRC message handling
- **Twitch limits**: 20 messages/30s, 100 concurrent channels

### Scale/Scope

- **Concurrent users**: 50-100 viewers
- **Question queue**: Max 100 queued requests
- **Commands**: 4 basic commands (!help, !uptime, !commands, !ask)
- **Moderation**: Per-user + global rate limiting, spam detection

---

## Phase 0 Research Complete

All technical unknowns resolved. Ready to proceed with Phase 1 (Design & Contracts).

### Next Steps

1. Generate data model from spec entities
2. Create API contracts (internal service APIs)
3. Generate quickstart documentation
4. Update agent context with technology choices
