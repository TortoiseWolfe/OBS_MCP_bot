# Feature Specification: Content Library Management

**Feature Branch**: `003-content-library-management`
**Created**: 2025-10-22
**Status**: Draft
**Input**: User description: "Content Library Management - replace single Big Buck Bunny failover with organized library of 20+ hours of CC-licensed educational content from MIT OCW, Harvard CS50, and Khan Academy. Includes download automation, metadata tracking, time-block organization, and license compliance."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Educational Content Downloads (Priority: P1)

As a system operator, I need to download educational programming content from open-source repositories so that the stream has diverse, high-quality content instead of repeating a single fallback video.

**Why this priority**: This delivers the core value of the feature - expanding from 1 video (9 minutes) to 20+ hours of educational content. Without this, the feature provides no value. This is the foundation for all other user stories.

**Independent Test**: Can be fully tested by running download scripts, verifying videos are saved to the correct directories, and confirming file integrity and playback compatibility.

**Acceptance Scenarios**:

1. **Given** yt-dlp is installed and internet is available, **When** operator runs the MIT OCW download script, **Then** 12 Python lecture videos are downloaded to the general content directory with correct filenames and metadata
2. **Given** download scripts are executed, **When** network connection is lost mid-download, **Then** the script resumes from the last successful download without re-downloading completed files
3. **Given** the operator wants selective content, **When** they run individual download scripts (MIT, CS50, Khan Academy), **Then** only the specified source's content is downloaded to the appropriate time-block directory
4. **Given** insufficient disk space exists, **When** download is attempted, **Then** script checks available space before starting and provides clear error message if space is insufficient

---

### User Story 2 - Content Organization by Audience Time Blocks (Priority: P2)

As a system operator, I need downloaded content automatically organized into time-block directories (kids, professional, general) so that age-appropriate content can be selected during scheduled broadcast hours per Constitutional Principle III.

**Why this priority**: Enables constitutional compliance for content appropriateness. Required for Tier 3 intelligent content scheduling but can be tested independently with manual content selection.

**Independent Test**: Can be tested by verifying downloaded content is placed in correct directories based on its target audience, and that directory structure matches configuration in settings.yaml.

**Acceptance Scenarios**:

1. **Given** Khan Academy content is downloaded, **When** the download completes, **Then** files are saved to the kids-after-school directory because they target beginner/youth audiences
2. **Given** MIT OCW content is downloaded, **When** the download completes, **Then** files are saved to the general directory because they are appropriate for all audiences
3. **Given** content library structure is created, **When** operator lists directories, **Then** they see kids-after-school/, professional-hours/, evening-mixed/, general/, and failover/ directories
4. **Given** Big Buck Bunny failover video exists, **When** new content is downloaded, **Then** the failover video is preserved in the failover/ directory and not overwritten

---

### User Story 3 - Content Metadata Extraction and Tracking (Priority: P2)

As a system operator, I need video metadata automatically extracted (duration, title, source, license) so that the content scheduler knows what content is available and can make informed selection decisions.

**Why this priority**: Enables intelligent content scheduling and attribution. This bridges the gap between downloaded files and the orchestrator's content selection logic. Without metadata, the orchestrator cannot discover or utilize new content.

**Independent Test**: Can be tested by running the metadata extraction script after downloads complete, verifying JSON output contains all required fields, and confirming database can import the metadata.

**Acceptance Scenarios**:

1. **Given** videos are downloaded to content directories, **When** metadata extraction script runs, **Then** a JSON file is created containing title, duration, file path, source attribution, license type, and tags for each video
2. **Given** metadata extraction runs, **When** processing a video file, **Then** the script uses ffprobe to extract accurate duration in seconds
3. **Given** metadata is extracted, **When** operator reviews the summary, **Then** they see total video count, total duration in hours/minutes, breakdown by source, and breakdown by time block
4. **Given** video files lack readable metadata, **When** extraction runs, **Then** script generates metadata from filename and directory structure, logging warnings for files needing manual review

---

### User Story 4 - License Compliance and Attribution Management (Priority: P3)

As a system operator, I need all content sources documented with proper Creative Commons attribution so that streaming complies with license terms and avoids DMCA takedowns on Twitch.

**Why this priority**: Legal requirement for using CC-licensed content. While critical for production use, it can be tested independently of the actual streaming integration. Lower priority than downloading and organizing content because it's primarily documentation.

**Independent Test**: Can be tested by reviewing content/README.md, verifying all sources have complete attribution (author, license, URL), and confirming license terms permit educational streaming use.

**Acceptance Scenarios**:

1. **Given** educational content is downloaded, **When** operator reviews content/README.md, **Then** each source (MIT OCW, CS50, Khan Academy, Big Buck Bunny) has documented license type, attribution requirements, source URL, and permitted use cases
2. **Given** content is being streamed, **When** operator checks OBS configuration guidance, **Then** documentation includes instructions for displaying required attribution text overlays per each license's requirements
3. **Given** new content source is added, **When** operator updates the library, **Then** documentation template requires license verification before download scripts are created
4. **Given** license compliance is reviewed, **When** checking Twitch TOS compatibility, **Then** all content licenses explicitly permit non-commercial educational use without monetization

---

### User Story 5 - OBS Integration and Playback Verification (Priority: P1)

As a system operator, I need to verify OBS can access and play downloaded content from the WSL2 filesystem so that the orchestrator can successfully control content playback during streaming.

**Why this priority**: Critical validation step - if OBS cannot access the files, the entire content library is unusable. This must work before any automated content scheduling can be implemented.

**Independent Test**: Can be tested by manually adding downloaded videos as OBS media sources using the WSL2 UNC path format and confirming smooth playback without errors.

**Acceptance Scenarios**:

1. **Given** content is downloaded to WSL2 filesystem, **When** operator adds a media source in OBS using the path `\\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content\general\...`, **Then** OBS successfully loads and plays the video
2. **Given** Docker orchestrator is running, **When** it mounts the content directory at /app/content, **Then** orchestrator can read file listings and metadata without permission errors
3. **Given** multiple videos exist in time-block directories, **When** operator tests playback of videos from each directory, **Then** all videos play successfully in OBS with correct audio and video
4. **Given** content library paths are configured, **When** settings.yaml is loaded, **Then** both Docker paths (/app/content) and Windows OBS paths (//wsl.localhost/...) are correctly mapped for each time block
5. **Given** content is playing and switches to a new video, **When** orchestrator initiates content transition, **Then** OBS "Content Attribution" text source updates to display new content's source, title, and license within 1 second

---

### Edge Cases

- **What happens when download source URLs change or videos are removed?** Download scripts fail with clear error messages. Documentation includes alternative sources (Internet Archive mirrors, direct OCW downloads). Failed downloads don't prevent system startup - existing content remains usable.

- **What happens when downloaded video format is incompatible with OBS?** Metadata extraction script detects format via ffprobe. Documentation includes ffmpeg re-encoding commands for converting incompatible formats. Incompatible videos are flagged in metadata JSON for manual review.

- **What happens when disk space fills up during downloads?** Download scripts check available space before starting and during execution. If space becomes critically low (<5 GB remaining), script pauses and prompts operator to free space or cancel. Partial downloads are preserved for resumption.

- **What happens when content library is empty (no downloads completed)?** System falls back to Big Buck Bunny failover video as it does currently. Health monitoring logs warning "content library empty - only failover available." Stream continues uninterrupted.

- **What happens when metadata extraction fails for some videos?** Failed videos are logged separately. System continues processing remaining videos. JSON output includes "extraction_errors" section with failed files and error messages. Operator can manually review and fix issues.

- **What happens when license terms change for a content source?** Documentation includes license verification date. Operators should review license terms annually. If terms change to prohibit use, documentation provides removal procedure and alternative source recommendations.

- **What happens during Docker container restart?** Content files remain on WSL2 filesystem (not in container). Metadata persists in SQLite database. Container remounts content directory on startup. No re-download or re-extraction needed.

- **What happens when the same content exists in multiple time blocks?** Content scheduler uses priority rules (defined in settings.yaml) to select appropriate version based on current time block. Duplicate files are allowed but logged as warnings during metadata extraction.

## Requirements *(mandatory)*

### Functional Requirements

#### Content Download (FR-001 through FR-010)

- **FR-001**: System MUST provide automated download scripts for MIT OpenCourseWare 6.0001 Python course (12 lectures)
- **FR-002**: System MUST provide automated download scripts for Harvard CS50 Introduction to Computer Science (at least 5 sample lectures)
- **FR-003**: System MUST provide automated download scripts for Khan Academy computer programming content (beginner-level JavaScript/creative coding)
- **FR-004**: System MUST verify yt-dlp is installed before executing downloads and provide clear installation instructions if missing
- **FR-005**: Download scripts MUST check available disk space before starting and abort if less than 10 GB is available
- **FR-006**: Download scripts MUST support resumable downloads (skip already-downloaded files based on filename matching)
- **FR-007**: Download scripts MUST limit video quality to 720p maximum to manage bandwidth and storage requirements
- **FR-008**: Download scripts MUST include throttling (rate limiting) to avoid overwhelming source servers
- **FR-009**: System MUST provide a master download script that executes all individual source downloads sequentially with progress reporting
- **FR-010**: Download scripts MUST save video files with descriptive filenames including sequence numbers (e.g., "01-What_is_Computation.mp4")

#### Content Organization (FR-011 through FR-020)

- **FR-011**: System MUST create directory structure: kids-after-school/, professional-hours/, evening-mixed/, general/, failover/
- **FR-012**: System MUST place Khan Academy content in kids-after-school/ directory automatically
- **FR-013**: System MUST place MIT OCW and Harvard CS50 content in general/ directory automatically
- **FR-014**: System MUST preserve existing Big Buck Bunny failover video in failover/ directory
- **FR-015**: System MUST support content existing in multiple time-block directories simultaneously (symlinks or duplicates permitted)
- **FR-016**: Directory structure MUST match time blocks defined in Constitutional Principle III (Kids After School 3-6 PM, Professional Hours 9 AM-3 PM, Evening Mixed 7-10 PM)
- **FR-017**: System MUST maintain consistent path mapping between Docker container paths (/app/content) and WSL2 filesystem paths
- **FR-018**: System MUST maintain consistent path mapping between Docker container paths and Windows OBS paths (//wsl.localhost/Debian/...)
- **FR-019**: Configuration file (settings.yaml) MUST document all path mappings for each time block
- **FR-020**: System MUST allow operators to manually add content to any time-block directory without running automated downloads

#### Metadata Extraction (FR-021 through FR-030)

- **FR-021**: System MUST provide Python script to scan content directories and extract metadata from all video files
- **FR-022**: Metadata extraction MUST use ffprobe to determine video duration in seconds
- **FR-023**: Metadata extraction MUST determine file size in megabytes for storage tracking
- **FR-024**: Metadata extraction MUST infer source attribution from directory structure (mit-ocw, harvard-cs50, khan-academy)
- **FR-025**: Metadata extraction MUST infer time-block assignments from directory location
- **FR-026**: Metadata extraction MUST extract or generate video titles from filenames (removing sequence numbers and formatting)
- **FR-027**: Metadata extraction MUST generate topic tags based on filename and path analysis (python, algorithms, web-dev, beginner, etc.)
- **FR-028**: Metadata extraction MUST export all metadata to JSON file (content_metadata.json) with structured format
- **FR-029**: Metadata extraction MUST provide summary statistics: total videos, total duration, breakdown by source, breakdown by time block
- **FR-030**: Metadata extraction MUST log warnings for videos with extraction failures without aborting the entire process

#### License Compliance (FR-031 through FR-040)

- **FR-031**: System MUST maintain content/README.md documenting all content sources with complete attribution
- **FR-032**: Documentation MUST include for each source: license type, attribution requirements, source URL, permitted uses, restrictions
- **FR-033**: Documentation MUST confirm all licenses permit non-commercial educational streaming use
- **FR-034**: System MUST automatically update OBS text source with current content attribution when content changes, and documentation MUST provide OBS scene setup guidance for "Content Attribution" text source
- **FR-035**: System MUST verify all downloaded content is Creative Commons licensed (CC BY-NC-SA or CC BY) before inclusion
- **FR-036**: Documentation MUST include license verification dates and recommend annual review process
- **FR-037**: System MUST document that Big Buck Bunny is licensed CC BY 3.0 from Blender Foundation
- **FR-038**: System MUST document that MIT OCW content is licensed CC BY-NC-SA 4.0
- **FR-039**: System MUST document that Harvard CS50 content is licensed CC BY-NC-SA 4.0
- **FR-040**: Documentation MUST explicitly state commercial use is prohibited (no ads, no monetization, no sponsored streams with this content)

#### OBS Integration (FR-041 through FR-050)

- **FR-041**: System MUST document Windows OBS path format for accessing WSL2 files: `\\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content\`
- **FR-042**: System MUST provide verification procedure for testing OBS can access and play downloaded content
- **FR-043**: Docker compose configuration MUST mount content directory as read-only volume at /app/content
- **FR-044**: Settings.yaml MUST include windows_content_path configuration for OBS path translation
- **FR-045**: System MUST support both Docker orchestrator metadata access (/app/content) and OBS direct file access (WSL2 UNC path) simultaneously
- **FR-046**: System MUST verify video files are in OBS-compatible formats (MP4 with H.264 video and AAC audio preferred)
- **FR-047**: Documentation MUST include ffmpeg re-encoding commands for converting incompatible video formats
- **FR-048**: System MUST maintain Docker network mode as "host" to allow orchestrator connection to OBS WebSocket on localhost
- **FR-049**: System MUST ensure content files remain on WSL2 filesystem (not copied into Docker images) for persistence across container restarts
- **FR-050**: System MUST document file permission requirements (755 for directories, 644 for files) for cross-platform access

#### System Integration (FR-051 through FR-055)

- **FR-051**: System MUST extend existing Docker Compose configuration with production orchestrator service including content volume mount
- **FR-052**: System MUST provide installation verification script checking: yt-dlp installed, ffprobe available, disk space sufficient, directory structure created
- **FR-053**: Documentation MUST provide complete architecture diagram showing: WSL2 filesystem, Docker container, OBS Studio, and data flow between components
- **FR-054**: System MUST create separate documentation for architecture (CONTENT_ARCHITECTURE.md) and quickstart guide (CONTENT_QUICKSTART.md)
- **FR-055**: System MUST provide troubleshooting guide covering: yt-dlp installation, OBS path access, Docker volume mounts, disk space management, video format compatibility

#### Content Attribution (FR-056 through FR-060)

- **FR-056**: System MUST update OBS text source named "Content Attribution" via WebSocket when content switches to display current video's attribution
- **FR-057**: Attribution text MUST include source name, course/video title, and license type (format: "MIT OpenCourseWare 6.0001: What is Computation? - CC BY-NC-SA 4.0")
- **FR-058**: Pre-flight validation MUST verify all OBS scenes contain a text source named "Content Attribution" before allowing stream start
- **FR-059**: System MUST provide text source creation template and configuration guide for operators setting up OBS scenes with attribution overlay
- **FR-060**: Attribution text updates MUST complete within 1 second of content transition to maintain synchronization with video playback

### Key Entities

- **ContentSource**: Represents a single video file in the content library
  - Attributes: source_id (UUID), title, file_path (Docker and OBS paths), duration_sec, file_size_mb, source_attribution (MIT/CS50/Khan), license_type, course_name, source_url, attribution_text (formatted string for OBS display), age_rating (kids/adult/all), time_blocks (array), priority, tags (array), last_verified
  - Relationships: Belongs to one or more time blocks, belongs to one content provider

- **ContentLibrary**: Represents the complete collection of available educational content
  - Attributes: total_videos, total_duration_sec, total_size_mb, last_scanned, sources_count (MIT/CS50/Khan counts)
  - Relationships: Contains many ContentSource entities

- **LicenseInfo**: Represents licensing metadata for content sources
  - Attributes: license_id, license_type (CC BY-NC-SA 4.0, etc.), source_name, attribution_text, license_url, permits_commercial_use (false), permits_modification (true), requires_attribution (true), verified_date
  - Relationships: Associated with one or more ContentSource entities from same provider

- **DownloadJob**: Represents a content download operation (for future automation)
  - Attributes: job_id, source_name (MIT/CS50/Khan), status (pending/in_progress/completed/failed), started_at, completed_at, videos_downloaded, total_size_mb, error_message
  - Relationships: Creates multiple ContentSource entities upon completion

- **TimeBlock**: Represents scheduled time periods for audience-appropriate content
  - Attributes: block_name (kids-after-school, professional-hours, evening-mixed, general), time_range, days_of_week, age_requirement, allowed_content_types, directory_path
  - Relationships: Contains many ContentSource entities

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Content library expands from 1 video (9 minutes) to minimum 20 hours of educational programming across multiple sources
- **SC-002**: Operator can download full content library (MIT OCW + CS50 + Khan Academy samples) in under 3 hours on standard broadband connection (10 Mbps)
- **SC-003**: Metadata extraction completes processing 25+ videos and generates valid JSON output in under 2 minutes
- **SC-004**: 100% of downloaded videos are playable in OBS Studio via WSL2 UNC paths without format conversion
- **SC-005**: Content library consumes less than 15 GB of disk space for initial content set (extensible to 50 GB for full courses)
- **SC-006**: All content sources (MIT, Harvard, Khan Academy) are documented with complete CC license attribution meeting legal requirements
- **SC-007**: Docker orchestrator can mount and read content directory metadata with zero permission errors on container startup
- **SC-008**: Operator can verify OBS content access in under 5 minutes using provided test procedure
- **SC-009**: Content organization matches constitutional time-block structure (kids/professional/evening/general) for 100% of downloaded content
- **SC-010**: System maintains failover video (Big Buck Bunny) availability at all times, even during content library updates
- **SC-011**: Download scripts successfully resume interrupted downloads without re-downloading completed files (tested via network interruption simulation)
- **SC-012**: Documentation enables new operator to complete full setup (install yt-dlp, download content, verify OBS access) in under 1 hour
- **SC-013**: OBS text attribution updates automatically within 1 second when content changes, displaying correct source/title/license for 100% of content transitions

## Assumptions

**Attribution Method**: Dynamic automatic updates chosen because:
- **Legal Compliance**: CC BY-NC-SA licenses require specific attribution per source - generic attribution violates license terms
- **Technical Feasibility**: Orchestrator already controls OBS via WebSocket for media playback - text source updates are incremental capability requiring same protocol
- **Constitutional Alignment**: Principle VII (Transparent Sustainability) requires attribution that provides educational value - viewers benefit from knowing exactly what content they're watching
- **Operational Efficiency**: Dynamic updates eliminate manual per-scene setup burden and reduce configuration errors
- **Alternative Analysis**:
  - Option A (Static generic overlay): Violates CC license requirements, provides no educational context
  - Option C (Pre-configured per-source scenes): Creates 20+ scene variants requiring manual maintenance
  - Option B (Dynamic automatic updates): Satisfies legal requirements, enhances educational value, minimal operational burden
