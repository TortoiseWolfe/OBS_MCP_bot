"""Content Library Scanner Service.

Scans content directories, validates files, and updates library statistics.

Implements User Story 3: Content Metadata Extraction and Tracking (US3).
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

import structlog

from ..models.content_library import ContentLibrary, ContentSource, SourceAttribution
from ..persistence.repositories.content_library import (
    ContentLibraryRepository,
    ContentSourceRepository,
)
from .content_metadata_manager import ContentMetadataManager, MetadataExtractionError

logger = structlog.get_logger()


class ContentLibraryScanner:
    """Manages content library scanning and statistics updates.

    Implements T052-T054: Directory scanning, file validation, statistics updates.
    """

    def __init__(
        self,
        content_source_repo: ContentSourceRepository,
        content_library_repo: ContentLibraryRepository,
        metadata_manager: ContentMetadataManager,
    ):
        """Initialize content library scanner.

        Args:
            content_source_repo: Repository for content sources
            content_library_repo: Repository for library statistics
            metadata_manager: Metadata extraction service
        """
        self.content_source_repo = content_source_repo
        self.content_library_repo = content_library_repo
        self.metadata_manager = metadata_manager

        logger.info("content_library_scanner_initialized")

    def validate_file(self, video_path: Path) -> Tuple[bool, str]:
        """Validate video file is accessible and has required attributes.

        Implements T053: File validation.

        Args:
            video_path: Path to video file

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file exists
        if not video_path.exists():
            return False, f"File does not exist: {video_path}"

        # Check is a file (not directory)
        if not video_path.is_file():
            return False, f"Path is not a file: {video_path}"

        # Check is readable
        if not video_path.stat().st_mode & 0o400:  # Check read permission
            return False, f"File is not readable: {video_path}"

        # Check file is not empty
        if video_path.stat().st_size == 0:
            return False, f"File is empty: {video_path}"

        # Check file extension
        if video_path.suffix.lower() not in ContentMetadataManager.VIDEO_EXTENSIONS:
            return False, f"Unsupported file extension: {video_path.suffix}"

        # Try to extract metadata with ffprobe (validates it's a valid video)
        try:
            self.metadata_manager.extract_metadata(video_path)
            return True, ""
        except MetadataExtractionError as e:
            return False, f"Invalid video file: {e}"

    def scan_time_block(self, time_block_dir: Path) -> List[ContentSource]:
        """Scan a single time-block directory and create ContentSource entities.

        Args:
            time_block_dir: Directory to scan (e.g., content/general/)

        Returns:
            List of created ContentSource instances
        """
        if not time_block_dir.exists():
            logger.warning(
                "time_block_directory_missing",
                directory=str(time_block_dir),
            )
            return []

        logger.info(
            "scanning_time_block",
            directory=str(time_block_dir),
        )

        # Scan directory for video files
        video_files = self.metadata_manager.scan_directory(time_block_dir)

        content_sources = []
        failed_files = []

        for video_path in video_files:
            # Validate file
            is_valid, error_msg = self.validate_file(video_path)

            if not is_valid:
                logger.warning(
                    "file_validation_failed",
                    file=str(video_path),
                    error=error_msg,
                )
                failed_files.append((str(video_path), error_msg))
                continue

            # Create ContentSource
            content_source = self.metadata_manager.create_content_source(video_path)

            if content_source:
                content_sources.append(content_source)
            else:
                failed_files.append((str(video_path), "Metadata extraction failed"))

        logger.info(
            "time_block_scan_complete",
            directory=str(time_block_dir),
            successful=len(content_sources),
            failed=len(failed_files),
        )

        if failed_files:
            logger.warning(
                "file_validation_summary",
                failed_count=len(failed_files),
                failures=failed_files[:5],  # Log first 5 failures
            )

        return content_sources

    def full_scan(self, persist: bool = True) -> List[ContentSource]:
        """Scan all time-block directories and discover all content.

        Implements T052: Full library scan.

        Args:
            persist: If True, save ContentSource entities to database

        Returns:
            List of all discovered ContentSource instances
        """
        logger.info("full_library_scan_starting")

        content_root = self.metadata_manager.content_root

        # Scan each time-block directory
        time_block_dirs = [
            content_root / "kids-after-school",
            content_root / "professional-hours",
            content_root / "evening-mixed",
            content_root / "general",
            content_root / "failover",
        ]

        all_content_sources = []

        for time_block_dir in time_block_dirs:
            content_sources = self.scan_time_block(time_block_dir)
            all_content_sources.extend(content_sources)

        logger.info(
            "full_library_scan_complete",
            total_videos=len(all_content_sources),
        )

        # Persist to database if requested
        if persist:
            self._persist_content_sources(all_content_sources)

            # Update library statistics
            self.update_library_statistics(all_content_sources)

        return all_content_sources

    def _persist_content_sources(self, content_sources: List[ContentSource]) -> None:
        """Persist ContentSource entities to database.

        Args:
            content_sources: List of ContentSource instances
        """
        logger.info(
            "persisting_content_sources",
            count=len(content_sources),
        )

        success_count = 0
        error_count = 0

        for content_source in content_sources:
            try:
                # Check if content already exists (by file_path)
                existing = self.content_source_repo.get_by_file_path(
                    content_source.file_path
                )

                if existing:
                    # Update last_verified timestamp instead of creating duplicate
                    self.content_source_repo.update_last_verified(
                        existing.source_id,
                        content_source.last_verified,
                    )
                    logger.debug(
                        "content_source_updated",
                        file=content_source.file_path,
                    )
                else:
                    # Create new record
                    self.content_source_repo.create(content_source)
                    logger.debug(
                        "content_source_created",
                        file=content_source.file_path,
                    )

                success_count += 1

            except Exception as e:
                logger.error(
                    "content_source_persist_failed",
                    file=content_source.file_path,
                    error=str(e),
                )
                error_count += 1

        logger.info(
            "content_sources_persisted",
            successful=success_count,
            failed=error_count,
        )

    def update_library_statistics(self, content_sources: List[ContentSource]) -> ContentLibrary:
        """Update library aggregate statistics.

        Implements T054: Library statistics update.

        Args:
            content_sources: All ContentSource instances in library

        Returns:
            Updated ContentLibrary instance
        """
        logger.info("updating_library_statistics")

        # Calculate aggregate stats
        total_videos = len(content_sources)
        total_duration_sec = sum(source.duration_sec for source in content_sources)
        total_size_mb = sum(source.file_size_mb for source in content_sources)

        # Count by source attribution
        mit_ocw_count = sum(
            1 for s in content_sources if s.source_attribution == SourceAttribution.MIT_OCW
        )
        cs50_count = sum(
            1 for s in content_sources if s.source_attribution == SourceAttribution.CS50
        )
        khan_academy_count = sum(
            1 for s in content_sources if s.source_attribution == SourceAttribution.KHAN_ACADEMY
        )
        blender_count = sum(
            1 for s in content_sources if s.source_attribution == SourceAttribution.BLENDER
        )

        # Get or create library record
        library = self.content_library_repo.get_or_create()

        # Update statistics
        library.total_videos = total_videos
        library.total_duration_sec = total_duration_sec
        library.total_size_mb = total_size_mb
        library.last_scanned = datetime.now(timezone.utc)
        library.mit_ocw_count = mit_ocw_count
        library.cs50_count = cs50_count
        library.khan_academy_count = khan_academy_count
        library.blender_count = blender_count

        # Persist to database
        library = self.content_library_repo.update(library)

        logger.info(
            "library_statistics_updated",
            total_videos=total_videos,
            total_duration_hrs=round(total_duration_sec / 3600, 2),
            total_size_gb=round(total_size_mb / 1024, 2),
        )

        return library

    def rescan_and_update(self) -> Tuple[List[ContentSource], ContentLibrary]:
        """Full rescan of content library with database update.

        Convenience method for complete refresh operation.

        Returns:
            Tuple of (all_content_sources, updated_library_stats)
        """
        logger.info("initiating_full_rescan")

        # Scan all content
        content_sources = self.full_scan(persist=True)

        # Get updated library stats
        library = self.content_library_repo.get()

        if not library:
            logger.error("library_stats_missing_after_update")
            library = ContentLibrary(
                total_videos=0,
                total_duration_sec=0,
                total_size_mb=0.0,
                last_scanned=datetime.now(timezone.utc),
            )

        logger.info(
            "full_rescan_complete",
            total_videos=library.total_videos,
            total_duration_hrs=round(library.total_duration_sec / 3600, 2),
        )

        return content_sources, library
