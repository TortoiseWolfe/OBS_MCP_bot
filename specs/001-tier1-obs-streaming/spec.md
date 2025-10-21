# Feature Specification: Tier 1 OBS Streaming Foundation

**Feature Branch**: `001-tier1-obs-streaming`
**Created**: 2025-10-20
**Status**: Draft
**Input**: User description: "Tier 1 OBS Streaming Foundation: programmatic OBS control for scene switching and source management, 24/7 RTMP stream output to Twitch, stream health monitoring and failover system to prevent dead air, content playback and transitions, owner interrupt handling with 10-second transitions"

## Clarifications

### Session 2025-10-20

- Q: How should OBS streaming be controlled to enable both 24/7 automated content and owner live sessions? → A: System controls OBS streaming (24/7 on) - owner signals scene switch to their camera/sources
- Q: How should the owner signal "I want to go live" (scene switch to owner content)? → A: Source detection - system detects when owner's camera/mic/screen sources become active
- Q: Who is responsible for creating and configuring the OBS scenes? → A: Hybrid - system creates basic scenes, owner customizes them
- Q: What should the system do when it first starts up? → A: Auto-start streaming immediately - system starts broadcasting as soon as initialization completes

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Continuous Educational Broadcasting (Priority: P1)

As a global learner, I need the educational stream to be available 24/7 across all timezones so that I can learn programming whenever I have time available, regardless of my location or schedule.

**Why this priority**: This is the core constitutional principle ("Broadcast Continuity - NON-NEGOTIABLE"). The entire channel's value proposition is always-on educational presence. Without this, there is no product.

**Independent Test**: Can be fully tested by monitoring stream uptime over a 7-day period and verifying that educational content is continuously visible on Twitch with zero unintentional interruptions.

**Acceptance Scenarios**:

1. **Given** the system is running, **When** no manual intervention occurs, **Then** the stream remains live on Twitch continuously for 7+ days
2. **Given** educational content is playing, **When** content finishes naturally, **Then** the next content begins automatically within 2 seconds with no dead air
3. **Given** the stream is live, **When** viewers tune in at any hour, **Then** they see educational programming appropriate for the current time block
4. **Given** the system has been running for 168 hours, **When** checking stream health metrics, **Then** total downtime is less than 30 seconds (<0.1% requirement)

---

### User Story 2 - Owner Live Broadcast Takeover (Priority: P2)

As the channel owner, I need to interrupt any automated programming and go live instantly so that I can provide spontaneous teaching sessions, respond to current events, or interact with the community without technical delays.

**Why this priority**: Owner authenticity is constitutionally protected. The bot amplifies the owner's teaching, not replaces it. If the owner can't go live easily, the system becomes a barrier instead of an enabler.

**Independent Test**: Can be fully tested by activating owner sources (screen share, camera) in OBS during automated content and measuring time to transition plus verifying stream continues seamlessly afterward.

**Acceptance Scenarios**:

1. **Given** automated content is playing, **When** owner activates their screen share or camera sources in OBS, **Then** the stream transitions to owner's live content within 10 seconds
2. **Given** owner has finished their live session, **When** owner deactivates their sources (stops screen share, turns off camera), **Then** the stream resumes automated programming within 10 seconds
3. **Given** owner goes live during a scheduled content block, **When** owner session ends (sources deactivated), **Then** the system resumes the appropriate content for the current time block
4. **Given** owner transitions are configured, **When** owner activates their sources, **Then** transition is smooth (audio fade, scene switch) without jarring cuts or dead air

---

### User Story 3 - Automatic Failover and Recovery (Priority: P3)

As a system operator, I need the streaming system to automatically detect and recover from content failures so that the stream never goes dark without requiring manual intervention at 3 AM.

**Why this priority**: Supports the broadcast continuity principle by ensuring resilience. Manual recovery would require 24/7 human monitoring, which violates the "automatic recovery without manual intervention" constitutional requirement.

**Independent Test**: Can be fully tested by simulating content source failures (file not found, playback error, source timeout) and verifying the system switches to failover content and logs the incident.

**Acceptance Scenarios**:

1. **Given** primary content source fails, **When** the failure is detected, **Then** the stream switches to failover content within 5 seconds
2. **Given** failover content is active, **When** the issue is resolved, **Then** the system returns to scheduled programming at the next natural transition point
3. **Given** both primary and failover content fail, **When** no content is available, **Then** a static "technical difficulties" scene displays with educational messaging and logs a critical alert
4. **Given** a content failure occurs, **When** the incident is logged, **Then** the log includes timestamp, failure type, recovery action taken, and total duration of degraded service

---

### User Story 4 - Stream Health Monitoring (Priority: P4)

As a system operator, I need real-time visibility into stream health metrics so that I can identify problems before they cause downtime and verify the system is meeting uptime commitments.

**Why this priority**: Provides operational visibility supporting the reliability principle. Less critical than the automated recovery itself, but necessary for long-term system optimization.

**Independent Test**: Can be fully tested by accessing the monitoring dashboard and verifying it displays accurate real-time metrics that update as stream conditions change.

**Acceptance Scenarios**:

1. **Given** the stream is active, **When** checking the monitoring dashboard, **Then** I see current bitrate, dropped frames percentage, stream uptime, and current content source
2. **Given** stream quality degrades (frames dropping above 1%), **When** the threshold is exceeded, **Then** the system logs a warning with diagnostic information
3. **Given** 7 days have elapsed, **When** requesting uptime report, **Then** the system provides total uptime percentage, downtime events, and total seconds offline
4. **Given** the RTMP connection to Twitch fails, **When** the connection drops, **Then** the system logs the failure and attempts automatic reconnection every 10 seconds

---

### Edge Cases

- **What happens when OBS crashes or becomes unresponsive?** System must detect unresponsive state within 30 seconds and attempt automatic restart via Docker container orchestration. If restart fails after 3 attempts, log critical alert.

- **What happens when network connection to Twitch is lost?** System must detect connection loss within 15 seconds, maintain OBS running locally, and attempt reconnection every 10 seconds. When reconnected, verify stream key is still valid and resume broadcasting.

- **What happens when owner sources become active but aren't ready/configured properly?** System detects source activation but if source is showing blank/black screen (video luminance <10%) or has no audio (level <-40dB) for more than 30 seconds, system displays a "going live soon" transition scene. If sources don't become properly active within 30 seconds, resume automated content and log the issue.

- **What happens when multiple content sources are configured for the same time block?** System follows priority order: Owner live > Scheduled premium content > Scheduled standard content > Failover content. Priority is determined by content metadata.

- **What happens when the system clock is incorrect or timezone is misconfigured?** Time-based content selection should use UTC internally and convert to configured timezone for scheduling. Log warnings if system time differs from NTP time by more than 60 seconds. System continues startup (does not block streaming), but schedule accuracy may be affected until clock synchronization resolves.

- **What happens during daylight saving time transitions?** Schedule definitions use fixed UTC offsets or timezone-aware scheduling. Content blocks automatically adjust to maintain intended real-world time (e.g., "after school hours" remain 3-6 PM local time).

- **What happens when disk space for logging or state persistence fills up?** System implements log rotation (retain 30 days, max 1GB), automatic cleanup of oldest logs, and alerts when disk usage exceeds 80% of allocated space.

- **What happens if owner manually starts/stops streaming in OBS?** System detects unexpected streaming state changes via obs-websocket. If owner manually stops streaming, system logs warning and automatically restarts streaming within 10 seconds to maintain 24/7 continuity. If owner manually starts streaming while system believes it's already streaming, system logs the anomaly but continues normal operation.

- **What happens if pre-flight validation fails during startup?** System logs specific critical error (e.g., "OBS not reachable", "Failover content missing", "No network connectivity") and does NOT start streaming. System retries pre-flight validation every 60 seconds until all checks pass, then auto-starts streaming. Owner must resolve the blocking issue (start OBS, fix network, add failover content) for system to proceed.

## Requirements *(mandatory)*

### Functional Requirements

#### OBS Programmatic Control

- **FR-001**: System MUST have exclusive control of OBS streaming state (Start Streaming / Stop Streaming) - owner does not manually control streaming, only scene content
- **FR-002**: System MUST connect to OBS via obs-websocket protocol and maintain persistent connection with automatic reconnection on connection loss
- **FR-003**: System MUST create basic functional OBS scenes on first initialization if they do not already exist (minimum required: "Automated Content", "Owner Live", "Failover", "Technical Difficulties")
- **FR-004**: System MUST NOT overwrite or modify existing scenes - scene creation is idempotent (checks existence before creating)
- **FR-005**: System MUST switch between OBS scenes programmatically using scene names only, without dependency on specific scene content or layout
- **FR-006**: System MUST control OBS media sources including play, pause, stop, and source switching operations
- **FR-007**: System MUST verify OBS scene transitions complete successfully by confirming active scene matches target scene within transition duration (max 2 seconds) and no OBS error events logged, logging any transition failures
- **FR-008**: System MUST query current OBS state including active scene, source status, and streaming status

#### System Startup and Initialization

- **FR-009**: System MUST perform pre-flight validation on startup before beginning streaming, including: OBS connectivity, required scenes exist, failover content available, Twitch credentials configured, network connectivity
- **FR-010**: System MUST automatically start streaming immediately after successful pre-flight validation without manual intervention
- **FR-011**: System MUST log critical error and NOT start streaming if any pre-flight validation fails, with specific error details for troubleshooting
- **FR-012**: System MUST create missing required scenes during initialization if they don't exist (idempotent scene creation per FR-004)
- **FR-013**: System MUST load and verify failover content playability during initialization before starting stream

#### Twitch Streaming

- **FR-014**: System MUST configure OBS to output RTMP stream to Twitch with configured stream key
- **FR-015**: System MUST maintain 24/7 RTMP connection to Twitch with automatic reconnection on connection loss
- **FR-016**: System MUST verify stream is live on Twitch by monitoring connection status every 30 seconds
- **FR-017**: System MUST use configured stream quality settings (resolution, bitrate, framerate) appropriate for Twitch guidelines and local bandwidth constraints
- **FR-018**: System MUST maintain stable bitrate and keep dropped frames below 1% during normal operation

#### Stream Health Monitoring

- **FR-019**: System MUST collect stream health metrics every 10 seconds including bitrate, dropped frames, CPU usage, and connection status
- **FR-020**: System MUST persist uptime metrics including total seconds online, total seconds offline, and downtime events with timestamps
- **FR-021**: System MUST detect degraded stream quality (dropped frames above 1%) and log warnings with diagnostic context
- **FR-022**: System MUST detect complete stream failure (RTMP connection lost, OBS unresponsive) within 30 seconds
- **FR-023**: System MUST provide queryable health status API or dashboard showing current stream state and historical uptime

#### Failover and Recovery

- **FR-024**: System MUST maintain pre-configured failover content that is always available and tested during system startup
- **FR-025**: System MUST automatically switch to failover content within 5 seconds when primary content source fails
- **FR-026**: System MUST detect content source failures including file not found, media playback errors, and source timeouts
- **FR-027**: System MUST attempt automatic recovery by restarting OBS if it becomes unresponsive (detected via websocket connection loss)
- **FR-028**: System MUST log all failover events with timestamp, failure type, recovery action, and duration of degraded service

#### Owner Interrupt Handling

- **FR-029**: System MUST monitor designated owner sources (screen capture, camera, microphone) and detect when they become active in OBS
- **FR-030**: System MUST transition to owner live scene within 10 seconds of detecting owner sources becoming active
- **FR-031**: System MUST save current automated content state to enable resume after owner session ends
- **FR-032**: System MUST detect when owner sources become inactive and resume automated programming within 10 seconds
- **FR-033**: System MUST handle owner transitions smoothly with configured audio fade and visual transition effects
- **FR-034**: System MUST allow configuration of which sources are considered "owner sources" for triggering live transitions

#### Content Playback and Transitions

- **FR-035**: System MUST play scheduled content according to time-based programming blocks defined in configuration
- **FR-036**: System MUST transition between content pieces automatically with no dead air (gap less than 2 seconds)
- **FR-037**: System MUST verify content files exist and are playable before scheduling them for broadcast
- **FR-038**: System MUST support multiple content types including video files, scene compositions, and live sources
- **FR-039**: System MUST respect content metadata including duration, age-appropriateness, and time block restrictions

### Key Entities

- **Stream Session**: Represents a continuous broadcast period from stream start to stream end. Attributes include start time, end time, total duration, downtime duration, downtime events, failover events, owner interrupts, and stream quality metrics.

- **Content Source**: Represents any media that can be displayed on stream. Attributes include source type (video file, scene, live input), file path or source identifier, duration, age-appropriateness rating, time blocks allowed, priority level, and last verification timestamp.

- **Downtime Event**: Represents a period when the stream was offline or degraded. Attributes include start time, end time, duration, failure cause (connection lost, OBS crash, content failure, etc.), recovery action taken, and automatic vs manual recovery.

- **Health Metric**: Represents point-in-time stream health measurement. Attributes include timestamp, bitrate, dropped frames percentage, CPU usage, active scene, active source, connection status, and streaming status.

- **Owner Session**: Represents a period when the owner was broadcasting live. Attributes include start time, end time, duration, content interrupted (what was playing before owner took over), and resume content (what resumed after owner finished).

- **Schedule Block**: Represents time-based programming configuration. Attributes include time range (start/end hours in local timezone), day of week restrictions, allowed content types, age-appropriateness requirements, and priority order for content selection.

- **Owner Source Configuration**: Represents configuration for detecting owner's live presence. Attributes include list of designated owner source names (e.g., "Screen Capture", "Webcam", "Microphone"), activation detection method (source enabled, audio above threshold, video feed active), and debounce timing to prevent false triggers from brief activations.

- **Scene Configuration**: Represents required OBS scene metadata. Attributes include scene name, purpose (automated/owner/failover/technical-difficulties), whether scene exists in OBS, and last verification timestamp. System creates missing scenes on initialization but never modifies existing ones.

- **System Initialization State**: Represents the outcome of startup pre-flight validation. Attributes include startup timestamp, validation results per check (OBS connectivity: pass/fail, scenes exist: pass/fail, failover content available: pass/fail, Twitch credentials: pass/fail, network connectivity: pass/fail), overall validation status (passed/failed), and streaming auto-started timestamp if successful.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Stream achieves 99.9% uptime over any 7-day measurement period (maximum 30 seconds downtime per week)
- **SC-002**: System automatically starts streaming within 60 seconds of startup when all pre-flight validations pass (no manual intervention required)
- **SC-003**: Owner "going live" transitions complete in 10 seconds or less from source activation to live on stream, measured 95% of the time
- **SC-004**: Zero instances of "dead air" (blank stream or silent stream) lasting longer than 5 seconds during any 7-day period
- **SC-005**: Automatic failover recovers from content failures within 5 seconds without manual intervention, measured 100% of the time
- **SC-006**: Stream quality maintains below 1% dropped frames during normal operation (non-degraded network conditions)
- **SC-007**: Content transitions between scheduled programming occur smoothly with gaps under 2 seconds
- **SC-008**: System uptime metrics are queryable and accurate to within 1 second of actual measured uptime
- **SC-009**: Owner can successfully interrupt and resume automated programming at least 5 times per day without causing stream quality degradation

### Constitutional Alignment

This feature directly implements:
- **Principle I (Broadcast Continuity)**: 24/7 streaming, failover, automatic recovery
- **Principle IV (Owner Responsiveness)**: 10-second owner interrupt transitions
- **Principle V (System Reliability)**: Docker deployment, graceful degradation, monitoring
- **Tier 1 Priority**: OBS + Twitch streaming foundation that must be complete before Tier 2 development

### Assumptions

- OBS Studio is installed and configured on the host system with obs-websocket plugin enabled
- Docker and Docker Compose are available for containerized deployment
- Owner delegates OBS streaming control to the system (system starts/stops streaming, owner controls only scene content via signals)
- System creates basic functional scenes on first initialization, owner may customize them freely afterward (system never overwrites customizations)
- Network bandwidth is sufficient for stable Twitch RTMP streaming at configured quality (minimum 5 Mbps upload recommended for 1080p)
- Initial content library exists or will be provided during implementation (at minimum, one failover video for testing)
- Twitch stream key and channel credentials are available for configuration
- System clock is synchronized via NTP or equivalent for accurate time-based scheduling
- Host system has sufficient resources (CPU, RAM) to run OBS encoding and orchestration services simultaneously
