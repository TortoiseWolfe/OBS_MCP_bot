# Service Contracts: Content Library Management

**Feature**: 003-content-library-management
**Date**: 2025-10-22
**Phase**: 1 (Design & Contracts)

## Overview

This document defines service interfaces for the content library management feature. All services use async/await patterns consistent with existing Tier 1 infrastructure.

## Service Definitions

### 1. ContentMetadataManager

**Purpose**: Extract metadata from video files and generate ContentSource entities.

**Responsibilities**:
- Scan video files using ffprobe to extract duration and format
- Parse filenames to extract titles and sequence numbers
- Infer source attribution from directory structure
- Generate formatted attribution text for OBS display
- Export metadata to JSON for database import

**Interface**:

```python
class ContentMetadataManager:
    """Manages content metadata extraction from video files."""

    def __init__(self, content_root: Path, config: ContentConfig):
        """
        Initialize metadata manager.

        Args:
            content_root: Root path to content library (/app/content)
            config: Configuration with path mappings and attribution templates
        """

    async def scan_directory(self, directory_path: Path) -> List[ContentSource]:
        """
        Scan directory for video files and extract metadata.

        Args:
            directory_path: Directory to scan (e.g., /app/content/general)

        Returns:
            List of ContentSource entities with complete metadata

        Raises:
            DirectoryNotFoundError: If directory doesn't exist
            PermissionError: If directory not readable
        """

    async def extract_metadata(self, video_path: Path) -> Optional[ContentMetadata]:
        """
        Extract metadata from single video file.

        Args:
            video_path: Path to video file

        Returns:
            ContentMetadata object or None if extraction fails

        Raises:
            FileNotFoundError: If video file doesn't exist
            VideoFormatError: If file format not supported
        """

    def generate_attribution_text(self, source: ContentSource) -> str:
        """
        Generate formatted attribution text for OBS display.

        Args:
            source: ContentSource entity with license info

        Returns:
            Formatted string like "MIT OpenCourseWare 6.0001: Lecture 1 - CC BY-NC-SA 4.0"
        """

    async def export_to_json(self, sources: List[ContentSource], output_path: Path) -> None:
        """
        Export content sources to JSON file for database import.

        Args:
            sources: List of ContentSource entities
            output_path: Path to output JSON file

        Raises:
            IOError: If file cannot be written
        """

    def print_summary(self, sources: List[ContentSource]) -> None:
        """
        Print human-readable summary of scanned content.

        Args:
            sources: List of ContentSource entities

        Outputs to stdout: total videos, duration, size, breakdown by source/time-block
        """
```

**Dependencies**:
- `ffprobe` (subprocess call) for video metadata
- `ContentSource` model from data-model.md
- `settings.yaml` for path mappings and attribution templates

**Error Handling**:
- Missing ffprobe: Raise clear error with installation instructions
- Invalid video files: Log warning, continue with remaining files
- Permission errors: Raise with specific path for debugging

---

### 2. ContentLibraryScanner

**Purpose**: Scan content directories, validate files, and maintain ContentLibrary statistics.

**Responsibilities**:
- Discover video files in time-block directories
- Validate file existence and readability
- Update ContentLibrary aggregate statistics
- Detect changes (new files, removed files) since last scan

**Interface**:

```python
class ContentLibraryScanner:
    """Scans content library and maintains statistics."""

    def __init__(self, content_root: Path, db: Database):
        """
        Initialize library scanner.

        Args:
            content_root: Root path to content library (/app/content)
            db: Database connection for updating statistics
        """

    async def full_scan(self) -> ScanResult:
        """
        Perform full scan of content library.

        Scans all time-block directories, validates files, updates statistics.

        Returns:
            ScanResult with counts, new files, missing files, errors

        Raises:
            ContentRootNotFoundError: If content_root doesn't exist
        """

    async def scan_time_block(self, block_name: str) -> List[Path]:
        """
        Scan specific time-block directory for video files.

        Args:
            block_name: Time block identifier (kids_after_school, etc.)

        Returns:
            List of video file paths in this time block

        Raises:
            TimeBlockNotFoundError: If time block directory doesn't exist
        """

    async def validate_file(self, file_path: Path) -> ValidationResult:
        """
        Validate that video file exists and is playable.

        Args:
            file_path: Path to video file

        Returns:
            ValidationResult with exists, readable, playable, format info

        Checks:
            - File exists on filesystem
            - File is readable (permissions)
            - File is valid video format (via ffprobe)
        """

    async def update_library_statistics(self) -> None:
        """
        Update ContentLibrary aggregate statistics from ContentSource records.

        Computes:
            - total_videos: COUNT(*)
            - total_duration_sec: SUM(duration_sec)
            - total_size_mb: SUM(file_size_mb)
            - per-source counts

        Updates singleton ContentLibrary record in database.
        """

    async def detect_changes(self, previous_scan: ScanResult) -> ChangeSet:
        """
        Detect changes between current scan and previous scan.

        Args:
            previous_scan: Results from last scan operation

        Returns:
            ChangeSet with added files, removed files, modified files

        Used for incremental metadata updates instead of full re-scan.
        """
```

**Dependencies**:
- `ContentLibrary` model from data-model.md
- `Database` from persistence layer
- Filesystem access for directory scanning

**Error Handling**:
- Missing directories: Log warning, continue with other time blocks
- Unreadable files: Log error with path and permissions info
- Database errors: Propagate with context about which operation failed

---

### 3. OBSAttributionUpdater

**Purpose**: Update OBS text sources with content attribution during playback.

**Responsibilities**:
- Connect to OBS via WebSocket (reuse existing connection)
- Update "Content Attribution" text source when content changes
- Verify text source exists during pre-flight checks
- Handle connection failures gracefully

**Interface**:

```python
class OBSAttributionUpdater:
    """Updates OBS text sources for content attribution."""

    def __init__(self, obs_client: OBSWebSocketClient, logger: StructuredLogger):
        """
        Initialize attribution updater.

        Args:
            obs_client: Existing OBS WebSocket client (from Tier 1)
            logger: Structured logger for audit trail
        """

    async def update_attribution(self, source: ContentSource) -> None:
        """
        Update OBS text source with content attribution.

        Args:
            source: ContentSource with attribution_text to display

        Updates text source named "Content Attribution" with formatted text.

        Raises:
            TextSourceNotFoundError: If "Content Attribution" source doesn't exist
            OBSConnectionError: If WebSocket connection failed
            UpdateTimeoutError: If update takes longer than 1 second
        """

    async def verify_text_source_exists(self) -> bool:
        """
        Verify "Content Attribution" text source exists in current OBS scene.

        Returns:
            True if text source exists, False otherwise

        Called during pre-flight validation to ensure setup is correct.
        """

    async def get_text_source_properties(self) -> TextSourceProperties:
        """
        Get current properties of "Content Attribution" text source.

        Returns:
            TextSourceProperties with font, size, color, position

        Used for debugging and validation.
        """

    def format_attribution_text(self, source: ContentSource) -> str:
        """
        Format attribution text according to license requirements.

        Args:
            source: ContentSource with license info

        Returns:
            Formatted string ready for OBS display

        Format: "{source_attribution} {course_name}: {title} - {license_type}"
        Example: "MIT OpenCourseWare 6.0001: What is Computation? - CC BY-NC-SA 4.0"
        """

    async def clear_attribution(self) -> None:
        """
        Clear attribution text (set to empty string).

        Used when switching to failover content or going offline.
        """
```

**Dependencies**:
- `OBSWebSocketClient` from existing Tier 1 infrastructure
- `ContentSource` model from data-model.md
- `structlog` for audit logging

**Error Handling**:
- Missing text source: Raise clear error with setup instructions
- Connection failure: Log error, retry once, then raise
- Update timeout: Cancel operation, log warning, continue (don't block stream)

**Performance Requirements**:
- Update latency < 1 second (per SC-013)
- WebSocket connection reuse (no reconnect per update)
- Non-blocking operation (don't block content transitions)

---

### 4. OBSController Extensions

**Purpose**: Extend existing OBS controller with text source update capability.

**Added Methods**:

```python
class OBSController:
    """Extended with text source update methods."""

    # ... existing methods from Tier 1 ...

    async def set_text_source_text(self, source_name: str, text: str) -> None:
        """
        Update text of a text source in OBS.

        Args:
            source_name: Name of text source in OBS scene
            text: New text content to display

        Raises:
            SourceNotFoundError: If source doesn't exist
            SourceTypeError: If source is not a text source
            OBSConnectionError: If WebSocket connection failed

        Uses obs-websocket SetInputSettings command:
            - inputName: source_name
            - inputSettings: {"text": text}
        """

    async def get_text_source_text(self, source_name: str) -> str:
        """
        Get current text of a text source in OBS.

        Args:
            source_name: Name of text source in OBS scene

        Returns:
            Current text content

        Raises:
            SourceNotFoundError: If source doesn't exist
            SourceTypeError: If source is not a text source

        Uses obs-websocket GetInputSettings command.
        """

    async def text_source_exists(self, source_name: str) -> bool:
        """
        Check if a text source exists in current OBS scene.

        Args:
            source_name: Name of text source to check

        Returns:
            True if source exists and is a text source, False otherwise

        Used for pre-flight validation.
        """
```

---

## Service Interactions

### Content Discovery Flow

```
┌──────────────────────────┐
│ Metadata Extraction      │
│ (CLI: add_content_       │
│  metadata.py)            │
└──────────┬───────────────┘
           │
           │ 1. Scan directories
           ▼
┌──────────────────────────┐
│ ContentLibraryScanner    │
│  - scan_time_block()     │
│  - validate_file()       │
└──────────┬───────────────┘
           │
           │ 2. Extract metadata per file
           ▼
┌──────────────────────────┐
│ ContentMetadataManager   │
│  - extract_metadata()    │
│  - generate_attribution()│
└──────────┬───────────────┘
           │
           │ 3. Export to JSON
           ▼
┌──────────────────────────┐
│ content_metadata.json    │
└──────────────────────────┘
           │
           │ 4. Import to database (separate step)
           ▼
┌──────────────────────────┐
│ Database (content_       │
│  sources table)          │
└──────────────────────────┘
```

### Content Playback Flow

```
┌──────────────────────────┐
│ Stream Manager           │
│ (Tier 1)                 │
└──────────┬───────────────┘
           │
           │ 1. Select content from library
           ▼
┌──────────────────────────┐
│ Database Query           │
│ (filter by time_blocks,  │
│  age_rating, priority)   │
└──────────┬───────────────┘
           │
           │ 2. Get ContentSource
           ▼
┌──────────────────────────┐
│ ContentSource entity     │
└──────────┬───────────────┘
           │
           ├─────────────────────┬──────────────────────┐
           │ 3a. Play video      │ 3b. Update attribution│
           ▼                     ▼                       │
┌──────────────────────────┐ ┌──────────────────────────┐
│ OBS Controller           │ │ OBS Attribution Updater  │
│  - set_media_source()    │ │  - update_attribution()  │
└──────────────────────────┘ └──────────────────────────┘
           │                     │
           │ 4a. OBS WebSocket   │ 4b. OBS WebSocket
           ▼                     ▼
┌──────────────────────────────────────────────┐
│ OBS Studio                                    │
│  - Media Source: plays video                 │
│  - Text Source: displays attribution         │
└──────────────────────────────────────────────┘
```

---

## Configuration Schema

**settings.yaml Extensions**:

```yaml
content:
  library_path: "/app/content"
  windows_content_path: "//wsl.localhost/Debian/home/turtle_wolfe/repos/OBS_bot/content"
  failover_video: "/app/content/failover/default_failover.mp4"

  # Time block paths
  time_block_paths:
    kids_after_school: "/app/content/kids-after-school"
    professional_hours: "/app/content/professional-hours"
    evening_mixed: "/app/content/evening-mixed"
    general: "/app/content/general"
    failover: "/app/content/failover"

  # Content sources (CC-licensed)
  sources:
    - name: "MIT OpenCourseWare 6.0001"
      path: "/app/content/general/mit-ocw-6.0001"
      license: "CC BY-NC-SA 4.0"
      attribution: "MIT OpenCourseWare"
    - name: "Harvard CS50"
      path: "/app/content/general/harvard-cs50"
      license: "CC BY-NC-SA 4.0"
      attribution: "Harvard University CS50"
    - name: "Khan Academy Programming"
      path: "/app/content/kids-after-school/khan-academy"
      license: "CC BY-NC-SA"
      attribution: "Khan Academy"

  # Attribution settings
  attribution:
    text_source_name: "Content Attribution"
    update_timeout_sec: 1
    verify_on_startup: true
```

---

## Testing Contracts

### Unit Test Coverage

**ContentMetadataManager**:
- `test_extract_metadata_valid_video()`: Verify ffprobe integration
- `test_generate_attribution_text()`: Verify formatting
- `test_scan_directory_multiple_files()`: Verify batch processing
- `test_handle_missing_ffprobe()`: Verify error handling

**ContentLibraryScanner**:
- `test_scan_time_block()`: Verify file discovery
- `test_validate_file_exists()`: Verify file validation
- `test_update_library_statistics()`: Verify aggregation
- `test_detect_changes()`: Verify incremental scanning

**OBSAttributionUpdater**:
- `test_update_attribution()`: Verify WebSocket call
- `test_verify_text_source_exists()`: Verify pre-flight check
- `test_format_attribution_text()`: Verify formatting
- `test_handle_connection_failure()`: Verify retry logic

### Integration Test Coverage

**End-to-End Flows**:
- `test_full_metadata_extraction_flow()`: Download → scan → extract → export
- `test_obs_text_source_updates()`: Content change → attribution update → verify display
- `test_content_library_integration()`: Scan → database → query → playback

---

**Phase 1 Complete**: Service contracts defined with interfaces, interactions, and testing requirements. Ready for quickstart guide.
