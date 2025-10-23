# Data Model: Content Library Management

**Feature**: 003-content-library-management
**Date**: 2025-10-22
**Phase**: 1 (Design & Contracts)

## Overview

This document defines the domain entities, their relationships, validation rules, and persistence schema for the content library management feature. All entities extend the existing Tier 1 streaming system database (`obs_bot.db`).

## Entity Relationship Diagram

```
┌─────────────────────┐
│ ContentLibrary      │
│                     │
│ - total_videos      │       1:N        ┌──────────────────────┐
│ - total_duration    │◄─────────────────┤  ContentSource       │
│ - total_size_mb     │                  │                      │
│ - last_scanned      │                  │ - source_id (PK)     │
└─────────────────────┘                  │ - title              │
                                         │ - file_path          │
                                         │ - duration_sec       │
                                         │ - source_attribution │
                                         │ - license_type       │
                                         │ - attribution_text   │
                                         │ - time_blocks[]      │
                                         │ - tags[]             │
                                         └──────────────────────┘
                                                  │
                                                  │ N:1
                                                  ▼
                                         ┌──────────────────────┐
                                         │ LicenseInfo          │
                                         │                      │
                                         │ - license_id (PK)    │
                                         │ - license_type       │
                                         │ - source_name        │
                                         │ - attribution_text   │
                                         │ - permits_commercial │
                                         │ - requires_attribute │
                                         │ - verified_date      │
                                         └──────────────────────┘

┌─────────────────────┐
│ DownloadJob         │
│                     │
│ - job_id (PK)       │       1:N        ┌──────────────────────┐
│ - source_name       │◄─────────creates─┤  ContentSource       │
│ - status            │                  │  (upon completion)   │
│ - started_at        │                  └──────────────────────┘
│ - completed_at      │
│ - videos_downloaded │
│ - error_message     │
└─────────────────────┘

┌─────────────────────┐
│ TimeBlock           │
│ (Configuration)     │
│ - block_name        │       1:N        ┌──────────────────────┐
│ - time_range        │◄─────────────────┤  ContentSource       │
│ - age_requirement   │  (via time_blocks│  (many-to-many)      │
│ - directory_path    │       array)     └──────────────────────┘
└─────────────────────┘
```

## Entities

### 1. ContentSource

**Purpose**: Represents a single video file in the content library with all metadata needed for selection, playback, and attribution.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `source_id` | UUID | Yes | Unique identifier for this content source | UUID v4 format |
| `title` | String | Yes | Human-readable title extracted from filename or metadata | Max 500 chars, non-empty |
| `file_path` | String | Yes | Absolute path to video file (Docker container path) | Must start with /app/content/, file must exist |
| `windows_obs_path` | String | Yes | Windows UNC path for OBS access | Must start with \\\\wsl.localhost\\ |
| `duration_sec` | Integer | Yes | Video duration in seconds (from ffprobe) | >= 0, typical range 600-3600 (10-60 min) |
| `file_size_mb` | Float | Yes | File size in megabytes | > 0, typical range 50-500 MB |
| `source_attribution` | String | Yes | Source name (MIT OCW, Harvard CS50, Khan Academy, Blender Foundation) | Enum: MIT_OCW, CS50, KHAN_ACADEMY, BLENDER |
| `license_type` | String | Yes | Creative Commons license identifier | Must match LicenseInfo.license_type |
| `course_name` | String | Yes | Course or series name | Max 200 chars |
| `source_url` | String | Yes | Original source URL for verification | Valid URL format |
| `attribution_text` | String | Yes | Formatted text for OBS display | Format: "{source} {course}: {title} - {license}" |
| `age_rating` | String | Yes | Target audience age appropriateness | Enum: kids, adult, all |
| `time_blocks` | Array[String] | Yes | Time blocks this content belongs to | Array of: kids_after_school, professional_hours, evening_mixed, general, failover |
| `priority` | Integer | Yes | Selection priority within time block | 1-10, higher = more priority |
| `tags` | Array[String] | Yes | Topic tags for filtering | e.g., ["python", "beginner", "algorithms"] |
| `last_verified` | DateTime (UTC) | Yes | When content was last validated (file exists, playable) | ISO 8601 format |
| `created_at` | DateTime (UTC) | Yes | When record was created | ISO 8601 format, auto-set |
| `updated_at` | DateTime (UTC) | Yes | When record was last modified | ISO 8601 format, auto-update |

**State Transitions**: None (entity is data-only, no workflow states)

**Validation Rules**:
- `file_path` must exist on filesystem at time of insertion
- `attribution_text` must be formatted as: `"{source_attribution} {course_name}: {title} - {license_type}"`
- `time_blocks` must contain at least one valid time block name
- `license_type` must reference existing LicenseInfo record

**Persistence (SQLite)**:

```sql
CREATE TABLE content_sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    windows_obs_path TEXT NOT NULL,
    duration_sec INTEGER NOT NULL CHECK(duration_sec >= 0),
    file_size_mb REAL NOT NULL CHECK(file_size_mb > 0),
    source_attribution TEXT NOT NULL CHECK(source_attribution IN ('MIT_OCW', 'CS50', 'KHAN_ACADEMY', 'BLENDER')),
    license_type TEXT NOT NULL,
    course_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    attribution_text TEXT NOT NULL,
    age_rating TEXT NOT NULL CHECK(age_rating IN ('kids', 'adult', 'all')),
    time_blocks TEXT NOT NULL,  -- JSON array
    priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 10),
    tags TEXT NOT NULL,  -- JSON array
    last_verified TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (license_type) REFERENCES license_info(license_type)
);

CREATE INDEX idx_content_sources_time_blocks ON content_sources(time_blocks);
CREATE INDEX idx_content_sources_attribution ON content_sources(source_attribution);
CREATE INDEX idx_content_sources_age_rating ON content_sources(age_rating);
CREATE INDEX idx_content_sources_priority ON content_sources(priority DESC);
```

---

### 2. LicenseInfo

**Purpose**: Represents Creative Commons license metadata for content attribution and compliance verification.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `license_id` | UUID | Yes | Unique identifier for this license record | UUID v4 format |
| `license_type` | String | Yes | CC license identifier (e.g., "CC BY-NC-SA 4.0") | Must match CC license format |
| `source_name` | String | Yes | Content provider name (MIT, Harvard, Khan Academy, Blender) | Max 200 chars |
| `attribution_text` | String | Yes | Template for attribution display | Contains placeholders for title, course |
| `license_url` | String | Yes | Full license text URL (creativecommons.org) | Valid URL |
| `permits_commercial_use` | Boolean | Yes | Whether commercial use is permitted | False for BY-NC-SA |
| `permits_modification` | Boolean | Yes | Whether derivatives are permitted | True for all target licenses |
| `requires_attribution` | Boolean | Yes | Whether attribution is required | True for all CC licenses |
| `requires_share_alike` | Boolean | Yes | Whether derivatives must use same license | True for SA licenses |
| `verified_date` | DateTime (UTC) | Yes | When license terms were last verified | ISO 8601 format |

**Persistence (SQLite)**:

```sql
CREATE TABLE license_info (
    license_id TEXT PRIMARY KEY,
    license_type TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    attribution_text TEXT NOT NULL,
    license_url TEXT NOT NULL,
    permits_commercial_use INTEGER NOT NULL CHECK(permits_commercial_use IN (0, 1)),
    permits_modification INTEGER NOT NULL CHECK(permits_modification IN (0, 1)),
    requires_attribution INTEGER NOT NULL CHECK(requires_attribution IN (0, 1)),
    requires_share_alike INTEGER NOT NULL CHECK(requires_share_alike IN (0, 1)),
    verified_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_license_info_type ON license_info(license_type);
```

**Initial Data** (seeded at deployment):

```sql
INSERT INTO license_info VALUES
('uuid1', 'CC BY-NC-SA 4.0', 'MIT OpenCourseWare', '{source} {course}: {title} - CC BY-NC-SA 4.0', 'https://creativecommons.org/licenses/by-nc-sa/4.0/', 0, 1, 1, 1, '2025-10-22T00:00:00Z', CURRENT_TIMESTAMP),
('uuid2', 'CC BY-NC-SA 4.0', 'Harvard CS50', '{source} CS50: {title} - CC BY-NC-SA 4.0', 'https://creativecommons.org/licenses/by-nc-sa/4.0/', 0, 1, 1, 1, '2025-10-22T00:00:00Z', CURRENT_TIMESTAMP),
('uuid3', 'CC BY-NC-SA', 'Khan Academy', 'Khan Academy: {title} - CC BY-NC-SA', 'https://creativecommons.org/licenses/by-nc-sa/3.0/', 0, 1, 1, 1, '2025-10-22T00:00:00Z', CURRENT_TIMESTAMP),
('uuid4', 'CC BY 3.0', 'Blender Foundation', 'Big Buck Bunny © 2008 Blender Foundation - CC BY 3.0', 'https://creativecommons.org/licenses/by/3.0/', 1, 1, 1, 0, '2025-10-22T00:00:00Z', CURRENT_TIMESTAMP);
```

---

### 3. ContentLibrary

**Purpose**: Aggregate entity representing the complete content collection with summary statistics.

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `library_id` | UUID | Yes | Unique identifier (singleton, only one record) | UUID v4 format |
| `total_videos` | Integer | Yes | Count of ContentSource records | >= 0 |
| `total_duration_sec` | Integer | Yes | Sum of all video durations | >= 0 |
| `total_size_mb` | Float | Yes | Sum of all file sizes | >= 0 |
| `last_scanned` | DateTime (UTC) | Yes | When library was last scanned for changes | ISO 8601 format |
| `mit_ocw_count` | Integer | Yes | Count of MIT OCW videos | >= 0 |
| `cs50_count` | Integer | Yes | Count of Harvard CS50 videos | >= 0 |
| `khan_academy_count` | Integer | Yes | Count of Khan Academy videos | >= 0 |
| `blender_count` | Integer | Yes | Count of Blender Foundation videos | >= 0 |

**Persistence (SQLite)**:

```sql
CREATE TABLE content_library (
    library_id TEXT PRIMARY KEY,
    total_videos INTEGER NOT NULL DEFAULT 0,
    total_duration_sec INTEGER NOT NULL DEFAULT 0,
    total_size_mb REAL NOT NULL DEFAULT 0.0,
    last_scanned TEXT NOT NULL,
    mit_ocw_count INTEGER NOT NULL DEFAULT 0,
    cs50_count INTEGER NOT NULL DEFAULT 0,
    khan_academy_count INTEGER NOT NULL DEFAULT 0,
    blender_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Singleton constraint (only one library record)
CREATE UNIQUE INDEX idx_content_library_singleton ON content_library(library_id);
```

**Update Trigger**: Statistics automatically recalculated on ContentSource insert/update/delete.

---

### 4. DownloadJob

**Purpose**: Tracks content download operations for monitoring and error handling (future feature, minimal implementation for Phase 1).

**Attributes**:

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `job_id` | UUID | Yes | Unique identifier for this download job | UUID v4 format |
| `source_name` | String | Yes | Content source being downloaded (MIT_OCW, CS50, KHAN_ACADEMY) | Enum value |
| `status` | String | Yes | Job status | Enum: pending, in_progress, completed, failed |
| `started_at` | DateTime (UTC) | No | When download started (null if pending) | ISO 8601 format |
| `completed_at` | DateTime (UTC) | No | When download finished (null if in progress) | ISO 8601 format |
| `videos_downloaded` | Integer | Yes | Count of successfully downloaded videos | >= 0 |
| `total_size_mb` | Float | Yes | Total size of downloaded files | >= 0 |
| `error_message` | String | No | Error details if failed | Max 1000 chars |

**Persistence (SQLite)**:

```sql
CREATE TABLE download_jobs (
    job_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL CHECK(source_name IN ('MIT_OCW', 'CS50', 'KHAN_ACADEMY')),
    status TEXT NOT NULL CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
    started_at TEXT,
    completed_at TEXT,
    videos_downloaded INTEGER NOT NULL DEFAULT 0,
    total_size_mb REAL NOT NULL DEFAULT 0.0,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_download_jobs_status ON download_jobs(status);
CREATE INDEX idx_download_jobs_source ON download_jobs(source_name);
```

---

### 5. TimeBlock

**Purpose**: Configuration entity defining scheduled time periods for audience-appropriate content selection. **Note**: Not persisted in database - defined in `settings.yaml` configuration.

**Attributes**:

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `block_name` | String | Yes | Identifier for this time block | "kids_after_school" |
| `display_name` | String | Yes | Human-readable name | "Kids After School" |
| `time_range` | String | Yes | Time range in HH:MM-HH:MM format | "15:00-18:00" |
| `days_of_week` | Array[String] | Yes | Days this block applies | ["monday", "tuesday", "wednesday", "thursday", "friday"] |
| `age_requirement` | String | Yes | Target age group | Enum: kids, adult, all |
| `allowed_content_types` | Array[String] | Yes | Content categories allowed | ["creative", "simplified"] |
| `directory_path` | String | Yes | Filesystem path for this block | "/app/content/kids-after-school" |

**Configuration (settings.yaml)**:

```yaml
schedule_blocks:
  - name: "kids_after_school"
    display_name: "Kids After School"
    time_range: "15:00-18:00"
    days: ["monday", "tuesday", "wednesday", "thursday", "friday"]
    age_requirement: "kids"
    allowed_types: ["creative", "simplified"]
    directory_path: "/app/content/kids-after-school"

  - name: "professional_hours"
    display_name: "Professional Hours"
    time_range: "09:00-15:00"
    days: ["monday", "tuesday", "wednesday", "thursday", "friday"]
    age_requirement: "adult"
    allowed_types: ["ai_tools", "workflows", "professional"]
    directory_path: "/app/content/professional-hours"

  - name: "evening_mixed"
    display_name: "Evening Mixed"
    time_range: "19:00-22:00"
    days: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    age_requirement: "all"
    allowed_types: ["algorithms", "problem_solving"]
    directory_path: "/app/content/evening-mixed"

  - name: "general"
    display_name: "General Audience"
    time_range: "00:00-23:59"
    days: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    age_requirement: "all"
    allowed_types: ["all"]
    directory_path: "/app/content/general"
```

---

## Relationships

### ContentSource → LicenseInfo (N:1)
- Many content sources share one license
- Foreign key: `ContentSource.license_type` → `LicenseInfo.license_type`
- Cascade: ON DELETE RESTRICT (cannot delete license if content exists)

### ContentLibrary → ContentSource (1:N)
- Library aggregate contains many sources
- Relationship: Virtual (no foreign key, statistics computed via aggregation queries)
- Update: ContentLibrary statistics updated via triggers on ContentSource table

### ContentSource → TimeBlock (N:M)
- Content can belong to multiple time blocks (via JSON array `time_blocks`)
- TimeBlock defined in configuration, not database
- Mapping: ContentSource.time_blocks array contains TimeBlock.block_name values

### DownloadJob → ContentSource (1:N)
- Download job creates multiple content sources
- Relationship: Logical (no foreign key, linked via `source_attribution` matching)

---

## Migration Path

### Phase 1: Initial Schema
1. Create `license_info` table with seed data
2. Create `content_sources` table with indexes
3. Create `content_library` table (singleton)
4. Create `download_jobs` table (optional, future use)

### Phase 2: Data Population
1. Run metadata extraction script on existing content
2. Insert ContentSource records for Big Buck Bunny (existing failover)
3. Initialize ContentLibrary singleton with current statistics

### Phase 3: Ongoing Maintenance
1. ContentLibrary statistics updated on content changes (triggers)
2. Metadata refresh runs weekly (cron job) to verify files still exist
3. License verification date checked annually (manual review)

---

**Phase 1 Complete**: Data model defined with validation rules, SQLite schema, and relationships. Ready for service contract definition.
