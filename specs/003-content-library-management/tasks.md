# Tasks: Content Library Management

**Input**: Design documents from `/specs/003-content-library-management/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/service-contracts.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Tests**: Unit and integration tests included per feature specification requirements.

**Total Tasks**: 82 tasks (updated from 80 after /speckit.analyze remediation added T030a and T074a)

**⚠️ CONSTITUTIONAL AMENDMENT PENDING**: This is Tier 3 (Intelligent Content Management). Constitutional amendment proposal submitted for parallel Tier 2/3 development (`.specify/memory/amendment-proposal-2.1.0.md`). Implementation may proceed pending 24-hour owner approval. See plan.md for full amendment details.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory structure creation

- [X] T001 Create content directory structure: content/kids-after-school/, content/professional-hours/, content/evening-mixed/, content/general/ (preserving existing content/failover/)
- [X] T002 [P] Create scripts/ directory for download automation
- [X] T003 [P] Create docs/ directory for architecture documentation
- [X] T004 [P] Install yt-dlp dependency via pip install yt-dlp (added to requirements.txt + Dockerfile will install on rebuild)
- [X] T005 [P] Verify ffprobe is available (from ffmpeg package) with installation instructions if missing (added ffmpeg to Dockerfile)
- [X] T006 Update docker-compose.prod.yml to mount content/ directory as read-only volume at /app/content (already configured)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 Create database migration script for content library schema in src/persistence/migrations/003_content_library.sql
- [ ] T008 [P] Create LicenseInfo model in src/models/license_info.py with CC license attributes and validation
- [ ] T009 [P] Create ContentSource model in src/models/content_source.py with metadata fields and time-block arrays
- [ ] T010 [P] Create ContentLibrary model in src/models/content_library.py with aggregate statistics
- [ ] T011 [P] Create DownloadJob model in src/models/download_job.py with status tracking
- [ ] T012 Create LicenseInfo repository in src/persistence/repositories/license_info.py with CRUD operations
- [ ] T013 [P] Create ContentSource repository in src/persistence/repositories/content_sources.py with CRUD and query methods
- [ ] T014 Seed LicenseInfo table with CC licenses (MIT OCW, CS50, Khan Academy, Blender) in migration script
- [ ] T015 Extend src/config/settings.py with content library configuration section (time_block_paths, sources, attribution)
- [ ] T016 Extend src/services/obs_controller.py with set_text_source_text(), get_text_source_text(), and text_source_exists() methods for WebSocket text source control

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Automated Educational Content Downloads (Priority: P1) 🎯 MVP

**Goal**: Enable operators to download 20+ hours of CC-licensed educational content from MIT OCW, Harvard CS50, and Khan Academy

**Independent Test**: Run download scripts, verify videos are saved to correct directories with proper filenames, confirm file integrity and playback compatibility

### Implementation for User Story 1

- [ ] T017 [P] [US1] Create MIT OCW download script in scripts/download_mit_ocw.sh using yt-dlp for 6.0001 Python course (12 lectures, 720p, descriptive filenames)
- [ ] T018 [P] [US1] Create Harvard CS50 download script in scripts/download_cs50.sh using yt-dlp for CS50 sample lectures (5+ videos, 720p)
- [ ] T019 [P] [US1] Create Khan Academy download script in scripts/download_khan_academy.sh using yt-dlp for beginner programming content (10+ videos, 720p)
- [ ] T020 [US1] Create master download orchestrator script in scripts/download_all_content.sh that executes all source downloads sequentially with progress reporting
- [ ] T021 [US1] Add disk space validation (10 GB minimum) to all download scripts before starting downloads
- [ ] T022 [US1] Add resume capability (--no-overwrites) to all download scripts to skip already-downloaded files
- [ ] T023 [US1] Add rate limiting (--throttled-rate 100K) to all download scripts to avoid overwhelming source servers
- [ ] T024 [US1] Add yt-dlp installation check to all download scripts with clear error message and installation instructions if missing
- [ ] T025 [US1] Create download script setup guide in scripts/SETUP.md documenting usage, requirements, and troubleshooting

**Checkpoint**: At this point, operators can download full content library (20+ hours) in under 3 hours

---

## Phase 4: User Story 5 - OBS Integration and Playback Verification (Priority: P1)

**Goal**: Verify OBS can access and play downloaded content from WSL2 filesystem, and enable automatic attribution text updates

**Independent Test**: Manually add downloaded videos as OBS media sources using WSL2 UNC path format, confirm smooth playback, verify text source updates work

### Implementation for User Story 5

- [ ] T026 [P] [US5] Create OBSAttributionUpdater service in src/services/obs_attribution_updater.py with update_attribution(), verify_text_source_exists(), and format_attribution_text() methods
- [ ] T027 [US5] Implement attribution text formatting logic in OBSAttributionUpdater to generate "{source} {course}: {title} - {license}" format
- [ ] T028 [US5] Implement OBS text source verification in OBSAttributionUpdater.verify_text_source_exists() checking for "Content Attribution" source in current scene
- [ ] T029 [US5] Implement attribution update logic in OBSAttributionUpdater.update_attribution() using obs_controller.set_text_source_text() with 1-second timeout
- [ ] T030 [US5] Add pre-flight validation to orchestrator startup checking OBS text source exists via OBSAttributionUpdater.verify_text_source_exists()
- [ ] T030a [US5] Integrate OBSAttributionUpdater.verify_text_source_exists() into orchestrator startup pre-flight checks in src/orchestrator.py (abort startup if text source missing with clear error message)
- [ ] T031 [US5] Create OBS setup guide in docs/OBS_ATTRIBUTION_SETUP.md documenting "Content Attribution" text source creation (font, size, position, formatting)
- [ ] T032 [US5] Create WSL2 path verification procedure in docs/CONTENT_ARCHITECTURE.md documenting \\wsl.localhost\Debian\... path format for OBS access
- [ ] T033 [US5] Document Docker container path (/app/content) and Windows OBS path (//wsl.localhost/...) mappings in config/settings.yaml with comments
- [ ] T034 [US5] Add file permission documentation (755 directories, 644 files) to docs/CONTENT_ARCHITECTURE.md for cross-platform access

**Checkpoint**: At this point, OBS can access content via WSL2 paths and attribution updates automatically during playback

---

## Phase 5: User Story 2 - Content Organization by Audience Time Blocks (Priority: P2)

**Goal**: Organize downloaded content into constitutional time-block directories (kids, professional, evening, general) for age-appropriate scheduling

**Independent Test**: Verify downloaded content is placed in correct directories based on target audience, confirm directory structure matches settings.yaml configuration

### Implementation for User Story 2

- [ ] T035 [US2] Update download_khan_academy.sh to save files to content/kids-after-school/ directory automatically
- [ ] T036 [P] [US2] Update download_mit_ocw.sh to save files to content/general/ directory automatically
- [ ] T037 [P] [US2] Update download_cs50.sh to save files to content/general/ directory automatically
- [ ] T038 [US2] Document time-block directory mappings in config/settings.yaml under content.time_block_paths
- [ ] T039 [US2] Add time-block validation to download scripts checking target directory exists before starting
- [ ] T040 [US2] Document time-block schedule (kids 3-6 PM, professional 9 AM-3 PM, evening 7-10 PM) in docs/CONTENT_ARCHITECTURE.md
- [ ] T041 [US2] Add symlink support documentation to scripts/SETUP.md for content appearing in multiple time blocks

**Checkpoint**: At this point, all content is organized by constitutional time blocks for appropriate scheduling

---

## Phase 6: User Story 3 - Content Metadata Extraction and Tracking (Priority: P2)

**Goal**: Extract video metadata (duration, title, source, license) and populate database for content scheduler

**Independent Test**: Run metadata extraction script after downloads, verify JSON output contains all required fields, confirm database import succeeds

### Implementation for User Story 3

- [ ] T042 [P] [US3] Create ContentMetadataManager service in src/services/content_metadata_manager.py with scan_directory(), extract_metadata(), generate_attribution_text(), and export_to_json() methods
- [ ] T043 [P] [US3] Create ContentLibraryScanner service in src/services/content_library_scanner.py with full_scan(), scan_time_block(), validate_file(), and update_library_statistics() methods
- [ ] T044 [US3] Implement ffprobe integration in ContentMetadataManager.extract_metadata() to extract video duration and format
- [ ] T045 [US3] Implement filename parsing in ContentMetadataManager.extract_metadata() to extract titles and sequence numbers
- [ ] T046 [US3] Implement source attribution inference in ContentMetadataManager based on directory structure (mit-ocw, harvard-cs50, khan-academy)
- [ ] T047 [US3] Implement time-block inference in ContentMetadataManager based on directory location
- [ ] T048 [US3] Implement topic tag generation in ContentMetadataManager based on filename and path analysis
- [ ] T049 [US3] Implement JSON export in ContentMetadataManager.export_to_json() generating content_metadata.json with all ContentSource entities
- [ ] T050 [US3] Implement summary statistics in ContentMetadataManager.print_summary() showing total videos, duration, breakdown by source/time-block
- [ ] T051 [US3] Create metadata extraction CLI tool in scripts/add_content_metadata.py that invokes ContentMetadataManager and ContentLibraryScanner
- [ ] T052 [US3] Implement directory scanning in ContentLibraryScanner.full_scan() to discover all video files in time-block directories
- [ ] T053 [US3] Implement file validation in ContentLibraryScanner.validate_file() checking existence, readability, and video format via ffprobe
- [ ] T054 [US3] Implement library statistics update in ContentLibraryScanner.update_library_statistics() computing total videos, duration, size from ContentSource records
- [ ] T055 [US3] Add database import logic to scripts/add_content_metadata.py reading JSON and inserting ContentSource records via repository
- [ ] T056 [US3] Add error handling in metadata extraction for missing ffprobe with clear installation instructions
- [ ] T057 [US3] Add warning logs for videos with extraction failures without aborting entire process

**Checkpoint**: At this point, content library metadata is fully tracked in database for scheduling decisions

---

## Phase 7: User Story 4 - License Compliance and Attribution Management (Priority: P3)

**Goal**: Document all content sources with proper CC attribution for legal compliance and Twitch TOS adherence

**Independent Test**: Review content/README.md, verify all sources have complete attribution (author, license, URL), confirm license terms permit educational streaming

### Implementation for User Story 4

- [ ] T058 [P] [US4] Create content attribution documentation in content/README.md with complete CC license information for all sources
- [ ] T059 [P] [US4] Document MIT OCW CC BY-NC-SA 4.0 license with attribution requirements, source URL, and verification date in content/README.md
- [ ] T060 [P] [US4] Document Harvard CS50 CC BY-NC-SA 4.0 license with attribution requirements, source URL, and verification date in content/README.md
- [ ] T061 [P] [US4] Document Khan Academy CC BY-NC-SA license with attribution requirements, source URL, and verification date in content/README.md
- [ ] T062 [P] [US4] Document Big Buck Bunny CC BY 3.0 license (Blender Foundation) with attribution in content/README.md
- [ ] T063 [US4] Add license verification checklist to content/README.md recommending annual review process
- [ ] T064 [US4] Add Twitch TOS compliance statement to content/README.md confirming non-commercial educational use is permitted
- [ ] T065 [US4] Add commercial use prohibition documentation (no ads, no monetization, no sponsored streams) to content/README.md
- [ ] T066 [US4] Create license compliance verification section in docs/CONTENT_ARCHITECTURE.md with DMCA risk analysis

**Checkpoint**: At this point, all content is fully documented for legal compliance

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, testing, validation, and deployment readiness

- [ ] T067 [P] Create comprehensive architecture documentation in docs/CONTENT_ARCHITECTURE.md showing WSL2/Docker/OBS data flow diagram
- [ ] T068 [P] Create quickstart validation script verifying CONTENT_QUICKSTART.md steps work end-to-end
- [ ] T069 [P] Create troubleshooting guide in docs/CONTENT_TROUBLESHOOTING.md covering: yt-dlp installation, OBS path access, Docker volume mounts, disk space, format compatibility
- [ ] T070 [P] Write unit tests for ContentMetadataManager in tests/unit/test_content_metadata_manager.py
- [ ] T071 [P] Write unit tests for ContentLibraryScanner in tests/unit/test_content_library_scanner.py
- [ ] T072 [P] Write unit tests for OBSAttributionUpdater in tests/unit/test_obs_attribution_updater.py
- [ ] T073 [P] Write integration test for download flow in tests/integration/test_content_download_flow.py
- [ ] T074 [P] Write integration test for OBS text source updates in tests/integration/test_obs_text_source_updates.py
- [ ] T074a [P] Write performance test for attribution update timing (<1 second requirement from SC-013) in tests/integration/test_obs_attribution_timing.py
- [ ] T075 [P] Write integration test for content library workflow in tests/integration/test_content_library_integration.py
- [ ] T076 Update main README.md with content library management section and quickstart link
- [ ] T077 Add content library metrics to health API endpoint (total videos, duration, disk usage)
- [ ] T078 Add structured logging for download operations, metadata extraction, and attribution updates
- [ ] T079 Verify all 135 release-gate checklist items pass from checklists/release-gate.md
- [ ] T080 Run end-to-end validation following specs/003-content-library-management/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 Downloads (Phase 3, P1): Can start after Foundational - No dependencies on other stories
  - US5 OBS Integration (Phase 4, P1): Can start after Foundational - Depends on US1 having content to test
  - US2 Organization (Phase 5, P2): Can start after Foundational - Integrates with US1 download scripts
  - US3 Metadata (Phase 6, P2): Can start after Foundational - Requires US1 downloads and US2 organization complete
  - US4 License (Phase 7, P3): Can start after Foundational - Independent documentation tasks
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 Downloads (P1)**: No dependencies - can start after Foundational
- **US5 OBS Integration (P1)**: Depends on US1 for content to test with
- **US2 Organization (P2)**: Integrates with US1 download scripts (must modify them)
- **US3 Metadata (P2)**: Requires US1 downloads and US2 organization complete to have content to scan
- **US4 License (P3)**: Independent - can run in parallel with other stories

### Within Each User Story

- Models before services
- Services before CLI tools
- Core implementation before integration
- Error handling after core functionality
- Documentation after implementation

### Parallel Opportunities

- Phase 1: All tasks except T001 can run in parallel after directory structure exists
- Phase 2: T008-T011 (models) can run in parallel, T012-T013 (repositories) can run in parallel after models
- Phase 3: T017-T019 (individual download scripts) can run in parallel
- Phase 4: T026-T029 (attribution service) can run in parallel, documentation tasks T031-T034 can run in parallel
- Phase 5: T036-T037 (MIT/CS50 script updates) can run in parallel
- Phase 6: T042-T043 (service creation) can run in parallel
- Phase 7: All documentation tasks T058-T062 can run in parallel
- Phase 8: All unit tests T070-T072 can run in parallel, all integration tests T073-T075 (including T074a) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all individual download scripts together:
# Task T017: Create MIT OCW download script
# Task T018: Create Harvard CS50 download script
# Task T019: Create Khan Academy download script

# These are independent files and can be written in parallel
```

## Parallel Example: User Story 3

```bash
# Launch both service implementations together:
# Task T042: Create ContentMetadataManager service
# Task T043: Create ContentLibraryScanner service

# These are different files with no cross-dependencies
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 5)

1. Complete Phase 1: Setup (directory structure, dependencies)
2. Complete Phase 2: Foundational (database schema, models, base services)
3. Complete Phase 3: US1 - Downloads (download scripts, automation)
4. Complete Phase 4: US5 - OBS Integration (attribution updates, playback verification)
5. **STOP and VALIDATE**: Test that operators can download content and OBS can play it with attribution
6. Deploy/demo MVP

**MVP Delivers**: Operators can expand from 1 video (9 minutes) to 20+ hours of educational content that OBS can play with automatic attribution

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 Downloads → Test downloading content → **Deliverable: Content library expansion**
3. Add US5 OBS Integration → Test OBS playback and attribution → **Deliverable: MVP complete**
4. Add US2 Organization → Test time-block placement → **Deliverable: Constitutional compliance ready**
5. Add US3 Metadata → Test metadata extraction → **Deliverable: Content scheduling ready**
6. Add US4 License → Test documentation → **Deliverable: Legal compliance complete**
7. Add Polish → Run all tests → **Deliverable: Production ready**

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (critical path)
2. Once Foundational is done:
   - Developer A: US1 Downloads (Phase 3)
   - Developer B: US4 License Documentation (Phase 7) - independent
   - Developer C: Start planning US2/US3/US5 integration
3. After US1 completes:
   - Developer A: US2 Organization (extends US1 scripts)
   - Developer B: US5 OBS Integration (needs US1 content)
   - Developer C: Begin US3 Metadata preparation
4. After US2 completes:
   - Developer A/B/C: US3 Metadata (needs organized content)
5. All developers: Polish phase testing and validation

---

## Notes

- [P] tasks = different files, no dependencies - can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable except where integration is required (US5 needs US1 content, US3 needs US1+US2 complete)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- MVP = US1 + US5 delivers core value (content expansion + OBS playback)
- Full feature = All user stories deliver complete content library management

---

## Success Metrics

After completing all tasks:

- ✅ **SC-001**: Content library expands from 1 video (9 min) to 20+ hours
- ✅ **SC-002**: Downloads complete in <3 hours on 10 Mbps connection
- ✅ **SC-003**: Metadata extraction processes 25+ videos in <2 minutes
- ✅ **SC-004**: 100% of videos playable in OBS via WSL2 UNC paths
- ✅ **SC-005**: Content library uses <15 GB disk space
- ✅ **SC-006**: All sources documented with complete CC attribution
- ✅ **SC-007**: Docker orchestrator mounts content with zero permission errors
- ✅ **SC-008**: OBS content access verified in <5 minutes
- ✅ **SC-009**: 100% of content organized by constitutional time blocks
- ✅ **SC-010**: Big Buck Bunny failover preserved
- ✅ **SC-011**: Download resume capability tested via network interruption
- ✅ **SC-012**: New operator completes setup in <1 hour
- ✅ **SC-013**: Attribution updates complete in <1 second
