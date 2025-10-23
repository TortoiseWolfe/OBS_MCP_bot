# Feature Specification: Tier 2 Twitch Chat Bot

**Feature Branch**: `002-twitch-chat-bot`
**Created**: 2025-10-22
**Status**: Draft
**Input**: User description: "Tier 2 Twitch Chat Bot: IRC connection to Twitch chat for reading and writing messages. Basic bot commands (!help, !uptime, !commands, !ask) for viewer interaction. AI-powered responses using Claude API or equivalent for answering viewer questions about programming and educational content. Rate limiting and queue management to handle 50-100 concurrent viewer questions without overwhelming the system. Basic chat moderation including timeout handling, command cooldowns, and spam prevention. Integration with existing OBS orchestrator to query stream status and uptime metrics. Constitutional alignment: Principle VIII (Community Support) - Twitch chat for fast, ephemeral, high-energy quick questions. Does not require content library - works standalone with current streaming infrastructure."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Chat Interaction (Priority: P1)

As a Twitch viewer, I need to interact with the bot using simple commands so that I can quickly get information about the stream without interrupting the broadcast.

**Why this priority**: This is the foundational MVP. Without basic chat connectivity and commands, there is no bot. Delivers immediate viewer value by providing stream information on demand.

**Independent Test**: Can be fully tested by connecting to Twitch chat in a test stream, sending !help, !uptime, and !commands, and verifying the bot responds correctly within 2 seconds.

**Acceptance Scenarios**:

1. **Given** bot is connected to Twitch chat, **When** viewer types !help, **Then** bot responds with list of available commands and brief descriptions within 2 seconds
2. **Given** stream has been live for 45 minutes, **When** viewer types !uptime, **Then** bot responds with "Stream has been live for 45 minutes" within 2 seconds
3. **Given** bot is connected to chat, **When** viewer types !commands, **Then** bot responds with list of all bot commands (!help, !uptime, !ask) within 2 seconds
4. **Given** bot loses connection to Twitch IRC, **When** connection is restored, **Then** bot automatically reconnects and resumes responding to commands within 30 seconds
5. **Given** multiple viewers send commands simultaneously, **When** 5 viewers type !uptime at the same time, **Then** bot responds to all 5 viewers within 5 seconds

---

### User Story 2 - AI-Powered Question Answering (Priority: P2)

As a Twitch viewer learning programming, I need to ask the bot questions about coding concepts so that I can get quick educational answers without waiting for the streamer to respond.

**Why this priority**: This is the key differentiator - AI-powered educational support. Aligns with constitutional Principle II (Educational Quality) and Principle VIII (Community Support). Provides genuine learning value.

**Independent Test**: Can be fully tested by sending programming questions via !ask command and verifying bot provides relevant, technically accurate answers using AI within 10 seconds.

**Acceptance Scenarios**:

1. **Given** bot is connected and AI service is available, **When** viewer types "!ask what is recursion?", **Then** bot responds with clear educational explanation within 10 seconds
2. **Given** 50 viewers ask questions simultaneously, **When** all 50 send !ask commands within 1 minute, **Then** bot processes all questions without crashing and responds to each within 30 seconds
3. **Given** viewer asks inappropriate question (spam, offensive), **When** question is detected as inappropriate, **Then** bot does not respond or responds with "Question not suitable for educational stream"
4. **Given** AI service is temporarily unavailable, **When** viewer sends !ask command, **Then** bot responds with "AI service temporarily unavailable, please try again in a moment" within 2 seconds
5. **Given** viewer asks same question within 60 seconds, **When** viewer tries !ask command again, **Then** bot responds with "Please wait before asking another question (cooldown: X seconds remaining)"

---

### User Story 3 - Rate Limiting and Queue Management (Priority: P3)

As the stream owner, I need the bot to handle high viewer activity without overwhelming system resources so that the stream remains stable during peak viewership (50-100 concurrent viewers).

**Why this priority**: Supports constitutional Principle V (System Reliability). Prevents bot from becoming a performance bottleneck or crashing during high engagement periods.

**Independent Test**: Can be fully tested by simulating 100 concurrent viewers sending !ask commands and verifying bot handles all requests without crashing, maintains response times, and enforces rate limits.

**Acceptance Scenarios**:

1. **Given** 100 viewers are actively chatting, **When** all 100 viewers send !ask commands within 10 seconds, **Then** bot queues requests and processes them within 60 seconds without crashing
2. **Given** bot is processing queue of 50 questions, **When** new question arrives, **Then** bot adds to queue and responds when capacity available, maintaining queue order (FIFO)
3. **Given** single viewer sends 5 !ask commands in 30 seconds, **When** viewer exceeds rate limit, **Then** bot ignores excess requests and privately messages viewer about cooldown period
4. **Given** bot queue reaches 100 questions (maximum capacity), **When** new question arrives, **Then** bot responds with "Bot is currently busy, please try again in a moment"
5. **Given** bot is under heavy load (80+ questions in queue), **When** system resources reach 80% capacity, **Then** bot logs warning and temporarily increases cooldown periods to 120 seconds per user

---

### User Story 4 - Chat Moderation (Priority: P4)

As the stream owner, I need the bot to enforce chat moderation rules so that spam and abuse don't disrupt the educational environment.

**Why this priority**: Supports constitutional Principle II (Educational Quality) by maintaining appropriate learning environment. Less critical than core functionality but important for long-term community health.

**Independent Test**: Can be fully tested by sending spam messages, testing command cooldowns, and verifying bot enforces moderation rules without manual intervention.

**Acceptance Scenarios**:

1. **Given** viewer sends same command 5 times in 10 seconds, **When** spam is detected, **Then** bot ignores commands after 2nd use and issues warning about cooldown (minimum 30 seconds between identical commands)
2. **Given** viewer is on cooldown for !ask command, **When** viewer tries to ask another question, **Then** bot does not respond to AI service but privately messages viewer with remaining cooldown time
3. **Given** bot detects user spamming multiple commands, **When** user sends 10+ commands in 60 seconds, **Then** bot adds user to temporary ignore list (5 minute timeout) and logs incident
4. **Given** viewer sends message with banned keywords (configurable list), **When** message is detected, **Then** bot does not respond and optionally reports to Twitch moderation tools
5. **Given** bot has issued timeout to user, **When** timeout expires, **Then** bot automatically removes user from ignore list and allows commands again

---

### Edge Cases

- **What happens when Twitch IRC connection drops during active chat?** Bot must detect connection loss within 15 seconds, attempt automatic reconnection every 10 seconds (up to 5 attempts), maintain in-memory queue of pending responses, and log all connection events for debugging.

- **What happens when AI service returns error or inappropriate response?** Bot must catch AI service errors, log them for review, respond to user with generic "Unable to answer that question right now", and not expose raw error messages to chat.

- **What happens when bot receives message in unsupported language?** Bot assumes English by default. Non-English messages receive response "Bot currently supports English questions only" (future enhancement for multi-language).

- **What happens when viewer asks question longer than Twitch character limit (500 chars)?** Bot processes first 500 characters and truncates, responds with answer but notes "Question truncated due to length limit".

- **What happens when multiple bots are in chat (conflict with other bots)?** Bot monitors for command conflicts (another bot with same commands) and logs warnings. Owner must configure unique command prefix if needed (e.g., !edubot instead of !).

- **What happens when bot needs to restart during active stream?** Bot must gracefully disconnect (send "Bot restarting" message), save current queue state to disk, restart, reload queue, and resume processing within 30 seconds.

- **What happens when viewer tries to abuse bot (infinite loops, resource exhaustion)?** Bot enforces hard limits: max 10 questions per user per hour, max 500 character questions, automatic timeout for users exceeding limits, logged for owner review.

- **What happens during Twitch API rate limiting?** Bot must respect Twitch IRC rate limits (20 messages per 30 seconds per moderator), queue outgoing messages, and delay responses if rate limit approached. Log warnings when queue backs up.

## Requirements *(mandatory)*

### Functional Requirements

#### Chat Connection and Basic Interaction

- **FR-001**: Bot MUST connect to Twitch IRC servers using valid channel credentials and maintain persistent connection for duration of stream
- **FR-002**: Bot MUST automatically reconnect to Twitch IRC if connection is lost, with exponential backoff (10s, 20s, 40s, 80s, 160s max) up to 5 attempts before alerting owner
- **FR-003**: Bot MUST read all incoming chat messages from channel in real-time (latency less than 500ms from message sent to message received)
- **FR-004**: Bot MUST respond to !help command with list of available commands and brief descriptions
- **FR-005**: Bot MUST respond to !uptime command with current stream duration in human-readable format (e.g., "2 hours 34 minutes")
- **FR-006**: Bot MUST respond to !commands command with complete list of bot commands
- **FR-007**: Bot MUST send responses to Twitch chat visible to all viewers (public messages, not whispers) within 2 seconds for simple commands (!help, !uptime, !commands)
- **FR-008**: Bot MUST respect Twitch IRC rate limits (20 messages per 30 seconds) to avoid being throttled or banned

#### AI-Powered Question Answering

- **FR-009**: Bot MUST respond to !ask [question] command by sending question to AI service and returning answer to chat
- **FR-010**: Bot MUST limit AI responses to 450 characters to fit within Twitch chat message limit (500 chars) with buffer for bot name/prefix. Implementation: (1) Use system prompt to instruct Claude to provide concise chat-appropriate responses (context engineering), (2) Send full user question context to Claude (no truncation of input), (3) Set max_tokens=150 as safety guardrail on output generation, (4) If response exceeds 450 chars, intelligently truncate at last complete sentence boundary and append "..."
- **FR-011**: Bot MUST handle AI service errors gracefully (timeouts, service unavailable, rate limits) and respond with user-friendly message "AI temporarily unavailable"
- **FR-012**: Bot MUST log all !ask questions and AI responses to persistent storage for later review and quality control
- **FR-013**: Bot MUST detect and reject inappropriate questions (profanity, spam patterns, off-topic requests) without sending to AI service. Implementation: **Phase 1 (MVP)** - Pattern-based spam detection: reject questions with >80% uppercase chars, >5 consecutive repeated chars, <20% alphabetic chars, or duplicate of question sent by same user within 60 seconds. Respond with "Question does not meet bot guidelines". **Phase 2 (Future)** - Add Claude-based content filtering using built-in safety features for sophisticated moderation. MVP relies on community moderation and rate limits for non-spam inappropriate content.
- **FR-014**: Bot MUST provide educational, technically accurate responses focused on programming and computer science topics per constitutional Principle II (Educational Quality)

#### Rate Limiting and Queue Management

- **FR-015**: Bot MUST enforce per-user rate limit of 1 !ask command per 60 seconds to prevent spam
- **FR-016**: Bot MUST enforce global rate limit of 100 concurrent !ask requests in queue at any time. Queue overflow handling: Per-user rate limits (FR-023: max 10/hour/user) make overflow unlikely with 100 concurrent viewers. If queue reaches capacity (100 requests), reject new !ask commands with message "Bot is currently busy, please try again in a moment (queue full)". Log all queue overflow events for capacity monitoring and alerting.
- **FR-017**: Bot MUST process !ask requests in FIFO (first-in-first-out) order when queue is active
- **FR-018**: Bot MUST respond with cooldown message when user attempts !ask command before cooldown expires (e.g., "Please wait 30 seconds before asking another question")
- **FR-019**: Bot MUST handle 50-100 concurrent viewers without service degradation (response times remain under 10 seconds for !ask, under 2 seconds for simple commands)
- **FR-020**: Bot MUST log queue metrics (current queue depth, average wait time, peak queue depth) every 60 seconds for performance monitoring. Implementation: (1) Structured logging to files (matches existing OBS orchestrator pattern) for historical analysis, (2) Expose metrics via `/health` endpoint for real-time monitoring and integration with existing health monitoring infrastructure. Health endpoint format: `{"status": "healthy", "queue_depth": 12, "avg_wait_time_sec": 3.2, "peak_queue_depth_1h": 45, "connected_to_twitch": true}`. Aligns with OBS orchestrator health API pattern (FR-026).

#### Chat Moderation

- **FR-021**: Bot MUST enforce command cooldown of 30 seconds between identical commands from same user
- **FR-022**: Bot MUST detect spam patterns (same message repeated 3+ times in 60 seconds) and temporarily ignore user for 5 minutes
- **FR-023**: Bot MUST enforce hard limit of 10 !ask commands per user per hour to prevent abuse
- **FR-024**: Bot MUST maintain temporary ignore list in memory with automatic removal after timeout expires
- **FR-025**: Bot MUST log all moderation actions (timeouts, ignored messages, rate limit violations) with timestamps and user information

#### Integration with OBS Orchestrator

- **FR-026**: Bot MUST query OBS orchestrator health API to retrieve current stream uptime for !uptime command
- **FR-027**: Bot MUST query OBS orchestrator for stream status (online/offline) to determine if uptime is available. Response scenarios: (1) Stream is LIVE - respond with uptime in human-readable format (e.g., "Stream has been live for 2 hours 34 minutes"), (2) Stream is OFFLINE - respond with "Stream is not currently live" (chat remains active pre-stream, post-stream, and between streams), (3) Health API is DOWN - respond with "Stream status unavailable" (per FR-028)
- **FR-028**: Bot MUST handle OBS orchestrator service unavailable gracefully (respond with "Stream status unavailable" if health API is down)
- **FR-029**: Bot MUST cache stream status data for 10 seconds to reduce API calls during high traffic

### Key Entities

- **Chat Message**: Represents incoming message from Twitch chat. Attributes include sender username, message content, timestamp, channel name, and whether it's a command (!prefix).

- **Bot Command**: Represents parsed command from chat message. Attributes include command name (!help, !uptime, !ask), command arguments (e.g., question text for !ask), sender username, and timestamp.

- **AI Question Request**: Represents queued request for AI-powered answer. Attributes include question text, sender username, timestamp submitted, queue position, processing status (pending/processing/completed/failed), and response text when available.

- **Rate Limit Entry**: Represents rate limiting state per user. Attributes include username, last command timestamp, remaining cooldown seconds, and total commands sent in current hour.

- **Moderation Event**: Represents moderation action taken by bot. Attributes include event type (timeout/spam detection/rate limit violation), username, timestamp, duration (for timeouts), and reason.

- **Stream Status**: Represents current stream state retrieved from OBS orchestrator. Attributes include streaming (boolean), uptime duration (seconds), timestamp last updated, and health API availability.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Bot responds to simple commands (!help, !uptime, !commands) within 2 seconds in 95% of requests during normal operation (under 50 concurrent viewers)
- **SC-002**: Bot handles 100 concurrent viewers sending !ask commands within 60 seconds without crashing or dropping requests (100% success rate processing all queued questions)
- **SC-003**: Bot provides AI-powered answers to !ask questions within 10 seconds in 90% of requests during normal operation
- **SC-004**: Bot maintains uptime of 99.5% or higher during stream sessions (max 30 seconds downtime per hour of streaming)
- **SC-005**: Bot enforces rate limits successfully with zero users able to exceed 10 questions per hour limit (100% enforcement rate)
- **SC-006**: Bot spam detection identifies and timeouts spam users within 60 seconds of spam pattern starting (90% accuracy, minimal false positives)
- **SC-007**: Bot integration with OBS orchestrator provides accurate stream uptime (within 5 seconds of actual uptime) in 99% of !uptime command responses
- **SC-008**: Bot question answering maintains educational quality with 90% of AI responses rated as "helpful" or "very helpful" by viewer feedback surveys (post-stream sampling)
- **SC-009**: Bot resource usage remains under 500MB RAM and 10% CPU during peak load (100 concurrent viewers) to avoid impacting stream quality

### Constitutional Alignment

This feature directly implements:
- **Principle VIII (Community Support)**: Twitch chat as primary platform for fast, ephemeral, high-energy quick questions
- **Principle II (Educational Quality)**: AI-powered responses provide technically accurate programming education accessible to all viewers
- **Principle V (System Reliability)**: Rate limiting and graceful error handling ensure bot doesn't compromise stream stability
- **Tier 2 Priority**: Chat bot operates standalone without content library, provides immediate viewer engagement

### Assumptions

- Bot will run as separate containerized service alongside OBS orchestrator (Docker Compose)
- Twitch channel credentials (OAuth token, channel name) are available and configured before bot starts
- AI service (Claude API or equivalent) credentials are configured and service is accessible
- Bot has read/write permissions in Twitch channel (moderator or broadcaster role)
- Stream owner will review and configure moderation settings (spam thresholds, banned keywords list) during initial setup
- Bot will use English language for all interactions (multi-language support deferred to future enhancement)
- Twitch IRC protocol remains stable (no breaking API changes from Twitch during development)
- OBS orchestrator health API (from Tier 1) is available and accessible at http://localhost:8000/health
