<!--
SYNC IMPACT REPORT
==================
Constitution Version: 1.0.0 → 2.0.0 (tier reprioritization)
Date: 2025-10-22
Change Type: MAJOR - Tier ordering changed (backward incompatible for planning)

Modified Principles: None (8 core principles unchanged)
Modified Sections:
  - Development Workflow → Priority Tiers section restructured
    * Tier 2: Twitch Chat Bot (NEW - moved from Tier 3, chat functionality extracted)
    * Tier 3: Intelligent Content Management (was Tier 2, shifted down)
    * Tier 4: Advanced AI Co-Host (was Tier 3, renamed, chat removed, vision/RAG/TTS remain)
    * Tier 5: Supporting Infrastructure (was Tier 4, shifted down)

Added Sections: None
Removed Sections: None

Rationale for MAJOR Bump:
  - Tier reordering is backward incompatible for development planning
  - Projects assuming "Tier 2 = Content Management" must adjust roadmaps
  - Constitutional discipline requires tier sequence to be stable contract
  - Chat bot moved to Tier 2 because it's standalone (no content library dependency)

Templates Requiring Updates:
  ✅ .specify/templates/plan-template.md (reviewed - no tier-specific references, no update needed)
  ✅ .specify/templates/spec-template.md (reviewed - no tier-specific references, no update needed)
  ✅ .specify/templates/tasks-template.md (reviewed - no tier-specific references, no update needed)
  ⚠️ PENDING - README.md (requires manual update to reflect new tier roadmap)
  ⚠️ PENDING - CLAUDE.md (auto-generated, will update when new features planned)

Follow-up TODOs:
  - [ ] Update README.md roadmap section with new Tier 2-5 structure
  - [ ] Create Tier 2 specification using /speckit.specify
  - [ ] Update any existing planning documents referencing old tier numbers
-->

# OBS_24_7 Constitution

## Core Principles

### I. Broadcast Continuity (NON-NEGOTIABLE)

**The stream must never go dark unintentionally. OBS is Job One.**

- Every feature, component, and decision serves the goal of continuous 24/7 streaming to Twitch
- Maximum acceptable downtime: 30 seconds per week (<0.1% uptime requirement)
- Failover content MUST always be available and tested
- Recovery procedures MUST execute automatically without manual intervention
- "Dead air" is unacceptable - viewers should always see educational content

**Rationale**: Unlike traditional streamers, this channel's value proposition is *always-on presence*. Going offline breaks the fundamental promise to global learners who depend on access across all timezones. OBS streaming to Twitch is the primary deliverable; everything else supports this.

### II. Educational Quality

**Technical accuracy and clear explanations are non-negotiable.**

- All teaching content MUST be technically accurate, verified against established sources
- Explanations MUST build from fundamentals, accessible to target audience
- Age-appropriate content MUST be enforced during scheduled time blocks
- Patient teaching that normalizes mistakes ("happy little bugs" philosophy)
- Factual material MUST be presented clearly without dumbing down
- Encourage learning through genuine support, not patronizing tone

**Rationale**: The channel exists to teach programming effectively. Entertaining but inaccurate content fails the mission. Quality education builds trust, drives retention, and creates real-world impact (children starting projects, adults adopting AI tools).

### III. Content Appropriateness

**Right content for right audience at right time.**

- Kids' content (creative, encouraging, simplified) during after-school hours (3-6 PM) and weekends
- Professional/adult content (AI tools, workflows, efficiency) during business hours (9 AM-3 PM)
- Mixed audience content (algorithms, problem-solving) during evenings (7-10 PM)
- Automatic filtering based on configured time blocks
- Manual overrides available but logged for audit
- DMCA compliance and Twitch TOS adherence mandatory

**Rationale**: Inappropriate content destroys parental trust and violates Twitch policies. Time-based audience segmentation ensures children get age-appropriate material while adults receive professional-grade instruction. Compliance protects channel sustainability.

### IV. Owner Responsiveness

**Owner can interrupt any programming instantly to go live.**

- Owner "I'm going live" signal triggers transition within 10 seconds
- AI seamlessly adapts to pair programming co-host mode or steps back entirely
- Manual overrides MUST always be available for content selection
- Current content state saved for potential resume after owner session
- Schedule conflicts resolved in favor of owner presence
- Owner's spontaneous teaching takes precedence over scheduled programming

**Rationale**: The channel amplifies the owner's teaching, not replaces them. Owner authenticity and spontaneity are irreplaceable assets. Rigid automation that blocks owner participation defeats the purpose.

### V. System Reliability

**Stable operation within local hardware constraints.**

- Docker containerized deployment for isolation and recovery
- Graceful degradation when optimal content unavailable (switch to backup)
- State persistence across container restarts (no amnesia)
- Resource usage MUST stay within host machine limits (CPU, memory, bandwidth)
- Monitoring with automated recovery procedures
- UPS recommended for power continuity

**Rationale**: Local infrastructure avoids cloud costs but introduces hardware dependency. Reliability engineering ensures 24/7 operation doesn't require 24/7 human monitoring. Graceful degradation maintains educational value even when ideal content fails.

### VI. Personality Authenticity

**Competence-based teaching, not entertainment gimmicks.**

- AI personality emerges from **expertise demonstrated through clear explanations**
- Bob Ross influence: Patient, encouraging, normalizes mistakes, calm debugging
- Max Headroom influence: Comfortable being AI, occasional wit about running in Docker, self-aware charm
- Open Source transparency: Explains own technology, discusses sustainability, builds in public
- NEVER cheesy game show host or forced entertainment personality
- Self-awareness enhances trust when appropriate, never distracts from education
- Genuine encouragement that respects learner intelligence

**Rationale**: Viewers seek quality education, not Twitch entertainment. Competence builds credibility. Bob Ross proved patience and encouragement create safe learning environments. Max Headroom showed digital hosts can be charming through self-awareness. Open source ethos builds community trust through transparency.

### VII. Transparent Sustainability

**Open source business model with ethical sponsorship.**

- Owner's professional visibility is explicit "sponsorship" funding free education
- Every owner mention MUST provide educational value (teaching examples from owner's projects)
- Frequency limits strictly enforced: maximum 2 mentions per 30-minute content block
- Contextual relevance required - no forced promotion
- Transparent framing: "This channel is sponsored by [Owner]'s expertise in..."
- Public broadcasting model (PBS/NPR) - free education, clear funding source
- NEVER sacrifice teaching quality for promotion

**Rationale**: Free quality education requires sustainable funding. Hidden promotion erodes trust. Transparent sponsorship where owner's projects become teaching examples provides genuine educational value while building owner's professional brand. Frequency limits prevent oversaturation.

### VIII. Community Support

**Twitch is primary platform; Discord supports but doesn't drive.**

- Twitch live stream is core product - 24/7 broadcast is Job One
- Discord provides persistent community, code sharing, deep discussions (supplementary)
- NEVER sacrifice broadcast quality or reliability for Discord features
- Twitch chat: Fast, ephemeral, high-energy - good for quick questions
- Discord: Persistent, formatted code, threaded discussions - good for complex help
- Global accessibility: Continuous streaming serves all timezones equally
- Go-live notifications in Discord when special content starts

**Rationale**: The vision is 24/7 broadcast television, not a Discord community with occasional streams. Twitch streaming is the primary value delivery. Discord enhances but doesn't replace. Prioritization prevents feature creep that undermines core mission.

## Operational Standards

### Broadcast Quality
- Stream quality maintained per Twitch guidelines (1080p60 recommended, configurable)
- Audio levels consistent across content types and transitions
- OBS scenes optimized for readability: appropriate fonts, colors, contrast
- Bitrate stable, dropped frames minimized (<1% acceptable)
- Stream health monitoring with automated alerts

### Content Safety
- Twitch Terms of Service compliance mandatory
- DMCA-safe content only (original, licensed, or public domain)
- Chat moderation maintains educational environment
- No inappropriate content during kids' programming hours
- Automated content filtering with manual review option

### Technical Operations
- Docker Compose orchestration for multi-container architecture
- obs-websocket or equivalent for programmatic OBS control
- State persistence via PostgreSQL or SQLite
- Logging with audit trail for all major decisions
- Monitoring dashboard for owner visibility into system state

## Development Workflow

### Priority Tiers (Strict Enforcement)

**Tier 1: OBS + Twitch Streaming (Job One)**
- OBS programmatic control (scene switching, source management)
- 24/7 RTMP stream output to Twitch
- Stream health monitoring and failover
- Content playback and transitions
- Owner interrupt handling (10-second transitions)
- BLOCKING: Nothing else matters if stream is offline

**Tier 2: Twitch Chat Bot**
- IRC connection to Twitch chat (read/write messages)
- Basic bot commands (!help, !uptime, !commands, !ask)
- AI-powered responses using Claude API or equivalent
- Rate limiting and queue management (50-100 concurrent viewers)
- Basic chat moderation (timeout handling, command cooldowns)
- Viewer engagement without requiring content library

**Tier 3: Intelligent Content Management**
- Decision engine: what to stream when and why
- Content library organization and indexing
- Schedule coordination and time-based filtering
- Content metadata (age-appropriateness, duration, topics)
- Priority-based content selection algorithm
- Foundation for advanced AI features requiring content knowledge

**Tier 4: Advanced AI Co-Host**
- Computer vision to see current stream content (screenshot OBS output)
- RAG system with educational content index (built in Tier 3)
- Context-aware chat responses referencing live content
- TTS voice synthesis for AI narration and teaching
- Solo teaching capability (autonomous 30+ minute sessions)
- Pair programming assistance when owner live
- Bob Ross + Max Headroom + Open Source personality blend

**Tier 5: Supporting Infrastructure**
- Web dashboard for stream analytics (Grafana/Prometheus)
- Discord community notifications (go-live alerts)
- Advanced logging and decision tracking
- Guest host coordination features
- Sponsorship mention integration
- VOD/clip generation and archival

### Implementation Discipline

- Tier 1 MUST be fully functional before Tier 2 development begins
- Tier 2 MUST demonstrate chat engagement before Tier 3
- Tier 3 MUST prove content organization before Tier 4
- Tier 4 MUST demonstrate advanced AI features before Tier 5
- Cross-tier dependencies require explicit justification and approval
- Features that don't fit tiers require constitutional amendment

**Rationale**: This prevents common failure mode of building supporting infrastructure while neglecting core features. OBS broadcasting is the product; chat provides engagement; content organization enables intelligence; advanced AI enhances teaching; supporting tools optimize operations. Each tier builds on previous foundation.

## Governance

### Amendment Procedure

**Constitutional changes require:**
1. Written proposal documenting rationale and impact
2. Review period (minimum 24 hours for owner consideration)
3. Explicit approval from owner/maintainer
4. Migration plan if existing implementations affected
5. Version bump per semantic versioning rules

**Version Bump Rules:**
- **MAJOR**: Backward incompatible changes to core principles or tier priorities
- **MINOR**: New principle added, existing principle materially expanded
- **PATCH**: Clarifications, wording improvements, non-semantic refinements

### Compliance Review

**All implementations MUST:**
- Declare which Constitution version they target
- Pass all Level 1-3 validation criteria before deployment
- Document any principle trade-offs or exceptions taken
- Provide audit trail demonstrating adherence to priority hierarchy
- Submit to quarterly review against Level 4 validation criteria

**All feature additions MUST answer:**
1. Does this improve broadcast reliability or educational quality?
2. Does this reduce owner operational burden?
3. Which tier does this belong to, and are prerequisites met?
4. Does this maintain local infrastructure viability?
5. Does this align with transparent sustainability model?

### Complexity Justification

**Any feature that violates simplicity MUST document:**
- Why simpler alternative insufficient for requirements
- Operational burden introduced (setup, maintenance, debugging)
- Long-term sustainability implications
- Owner approval before implementation

### Runtime Development Guidance

For agent-specific implementation guidance (prompts, workflows, command templates), refer to:
- `.specify/templates/commands/*.md` for agent workflows
- `README.md` for deployment and setup procedures
- Plan template for constitution check integration

**IMPORTANT**: Constitution applies to all implementations regardless of agent or technology stack. Agents receive specific prompts; constitution defines universal principles.

---

**Version**: 2.0.0
**Ratified**: 2025-10-20
**Last Amended**: 2025-10-22
**Maintainer**: [Channel Owner]
**Framework**: PRP (Product Requirements Prompt) by Rasmus Widing
**Core Mission**: 24/7 AI-hosted educational Twitch broadcast via local OBS
**Inspired by**: Max Headroom (digital wit), Bob Ross (patient teaching), PBS/NPR (public broadcasting)
