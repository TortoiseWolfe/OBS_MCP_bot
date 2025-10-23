"""Content Metadata Manager Service.

Extracts video metadata from downloaded content files and generates
ContentSource entities for database import.

Implements User Story 3: Content Metadata Extraction and Tracking (US3).
"""

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import structlog

from ..models.content_library import (
    AgeRating,
    ContentSource,
    SourceAttribution,
)

logger = structlog.get_logger()


class MetadataExtractionError(Exception):
    """Raised when metadata extraction fails."""

    pass


class ContentMetadataManager:
    """Manages content metadata extraction and ContentSource generation.

    Implements T042-T049: Metadata extraction pipeline.
    """

    # Video file extensions to scan
    VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}

    # Content root directory (WSL2 path)
    CONTENT_ROOT = Path("/home/turtle_wolfe/repos/OBS_bot/content")

    # Windows UNC path prefix
    WINDOWS_PREFIX = "\\\\wsl.localhost\\Debian"

    # Source attribution mappings
    SOURCE_MAPPING = {
        "mit-ocw": SourceAttribution.MIT_OCW,
        "harvard-cs50": SourceAttribution.CS50,
        "khan-academy": SourceAttribution.KHAN_ACADEMY,
        "failover": SourceAttribution.BLENDER,
    }

    # Time block directory mappings
    TIME_BLOCK_MAPPING = {
        "kids-after-school": ["after_school_kids"],
        "professional-hours": ["professional_hours"],
        "evening-mixed": ["evening_mixed"],
        "general": ["general", "evening_mixed"],  # General content works in multiple blocks
        "failover": ["failover"],
    }

    # Age rating by time block
    AGE_RATING_MAPPING = {
        "kids-after-school": AgeRating.KIDS,
        "professional-hours": AgeRating.ADULT,
        "evening-mixed": AgeRating.ALL,
        "general": AgeRating.ALL,
        "failover": AgeRating.ALL,
    }

    def __init__(self, content_root: Optional[Path] = None):
        """Initialize metadata manager.

        Args:
            content_root: Root content directory (defaults to WSL2 standard path)
        """
        self.content_root = content_root or self.CONTENT_ROOT
        logger.info("content_metadata_manager_initialized", content_root=str(self.content_root))

    def scan_directory(self, directory: Path) -> List[Path]:
        """Recursively scan directory for video files.

        Implements T052: Directory scanning.

        Args:
            directory: Directory to scan

        Returns:
            List of video file paths
        """
        video_files = []

        if not directory.exists():
            logger.warning("directory_not_found", path=str(directory))
            return video_files

        if not directory.is_dir():
            logger.warning("path_not_directory", path=str(directory))
            return video_files

        # Recursively find video files
        for ext in self.VIDEO_EXTENSIONS:
            video_files.extend(directory.rglob(f"*{ext}"))

        logger.info(
            "directory_scanned",
            directory=str(directory),
            files_found=len(video_files),
            extensions=list(self.VIDEO_EXTENSIONS),
        )

        return sorted(video_files)

    def extract_metadata(self, video_path: Path) -> Dict[str, any]:
        """Extract video metadata using ffprobe.

        Implements T044: ffprobe integration for duration/format extraction.

        Args:
            video_path: Path to video file

        Returns:
            Dict with metadata: duration_sec, file_size_mb, format

        Raises:
            MetadataExtractionError: If ffprobe fails or file inaccessible
        """
        if not video_path.exists():
            raise MetadataExtractionError(f"Video file not found: {video_path}")

        if not video_path.is_file():
            raise MetadataExtractionError(f"Path is not a file: {video_path}")

        try:
            # Run ffprobe to extract duration, format, and video resolution
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration,size,format_name:stream=width,height",
                    "-of",
                    "json",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                raise MetadataExtractionError(
                    f"ffprobe failed: {result.stderr}"
                )

            # Parse JSON output
            data = json.loads(result.stdout)

            if "format" not in data:
                raise MetadataExtractionError("ffprobe output missing 'format' key")

            format_info = data["format"]

            # Extract duration
            duration_sec = float(format_info.get("duration", 0))
            if duration_sec == 0:
                logger.warning(
                    "zero_duration_detected",
                    file=str(video_path),
                    warning="Duration may be incorrect or file corrupt",
                )

            # Extract file size
            file_size_bytes = int(format_info.get("size", 0))
            file_size_mb = file_size_bytes / (1024 * 1024)

            # Extract format
            video_format = format_info.get("format_name", "unknown")

            # Extract video resolution from streams
            width = 0
            height = 0
            if "streams" in data:
                for stream in data["streams"]:
                    # Find first video stream with resolution
                    if "width" in stream and "height" in stream:
                        width = int(stream["width"])
                        height = int(stream["height"])
                        break

            if width == 0 or height == 0:
                logger.warning(
                    "no_video_resolution_detected",
                    file=str(video_path),
                    warning="Could not extract video resolution",
                )

            logger.debug(
                "metadata_extracted",
                file=video_path.name,
                duration_sec=int(duration_sec),
                size_mb=round(file_size_mb, 2),
                format=video_format,
                resolution=f"{width}x{height}",
            )

            return {
                "duration_sec": int(duration_sec),
                "file_size_mb": round(file_size_mb, 2),
                "format": video_format,
                "width": width,
                "height": height,
            }

        except subprocess.TimeoutExpired:
            raise MetadataExtractionError(f"ffprobe timed out: {video_path}")
        except json.JSONDecodeError as e:
            raise MetadataExtractionError(f"ffprobe output not valid JSON: {e}")
        except Exception as e:
            raise MetadataExtractionError(f"Metadata extraction failed: {e}")

    def parse_filename(self, video_path: Path) -> Dict[str, str]:
        """Parse video filename to extract title and sequence number.

        Implements T045: Filename parsing for titles.

        Expected formats:
        - "01-Lecture_Title.mp4"
        - "Lecture_01_Title.mp4"
        - "Title.mp4"

        Args:
            video_path: Path to video file

        Returns:
            Dict with title, sequence_number
        """
        filename = video_path.stem  # Remove extension

        # Try to extract sequence number (e.g., "01-Title" or "Title_01")
        sequence_match = re.match(r"^(\d+)[-_\s](.+)$", filename)
        if sequence_match:
            sequence_num = sequence_match.group(1)
            title = sequence_match.group(2)
        else:
            sequence_num = None
            title = filename

        # Clean up title: replace underscores/hyphens with spaces, title case
        title = title.replace("_", " ").replace("-", " ")
        title = " ".join(word.capitalize() for word in title.split())

        return {
            "title": title,
            "sequence_number": sequence_num,
        }

    def infer_source_attribution(self, video_path: Path) -> SourceAttribution:
        """Infer source attribution from directory structure.

        Implements T046: Source attribution inference.

        Args:
            video_path: Path to video file

        Returns:
            SourceAttribution enum

        Raises:
            MetadataExtractionError: If source cannot be determined
        """
        path_str = str(video_path).lower()

        for key, source in self.SOURCE_MAPPING.items():
            if key in path_str:
                logger.debug("source_inferred", file=video_path.name, source=source.value)
                return source

        # Default to Blender for failover
        logger.warning(
            "source_attribution_unknown",
            file=str(video_path),
            default="BLENDER",
        )
        return SourceAttribution.BLENDER

    def infer_time_blocks(self, video_path: Path) -> List[str]:
        """Infer time block assignment from directory location.

        Implements T047: Time-block inference from directory.

        Args:
            video_path: Path to video file

        Returns:
            List of time block names
        """
        # Get relative path from content root
        try:
            rel_path = video_path.relative_to(self.content_root)
        except ValueError:
            logger.warning(
                "file_outside_content_root",
                file=str(video_path),
                content_root=str(self.content_root),
            )
            return ["general"]  # Default

        # Extract first directory component (time block directory)
        parts = rel_path.parts
        if len(parts) == 0:
            return ["general"]

        time_block_dir = parts[0]

        # Map directory name to time blocks
        time_blocks = self.TIME_BLOCK_MAPPING.get(time_block_dir, ["general"])

        logger.debug(
            "time_blocks_inferred",
            file=video_path.name,
            directory=time_block_dir,
            time_blocks=time_blocks,
        )

        return time_blocks

    def infer_age_rating(self, video_path: Path) -> AgeRating:
        """Infer age rating from directory location.

        Args:
            video_path: Path to video file

        Returns:
            AgeRating enum
        """
        try:
            rel_path = video_path.relative_to(self.content_root)
            time_block_dir = rel_path.parts[0] if len(rel_path.parts) > 0 else "general"
            return self.AGE_RATING_MAPPING.get(time_block_dir, AgeRating.ALL)
        except ValueError:
            return AgeRating.ALL

    def generate_tags(self, video_path: Path, title: str) -> List[str]:
        """Generate content tags from filename and path.

        Implements T048: Topic tag generation from analysis.

        Args:
            video_path: Path to video file
            title: Parsed title

        Returns:
            List of tag strings
        """
        tags = []

        path_str = str(video_path).lower()
        title_lower = title.lower()

        # Programming language tags
        if any(lang in path_str or lang in title_lower for lang in ["python", "py"]):
            tags.append("python")
        if any(lang in path_str or lang in title_lower for lang in ["javascript", "js"]):
            tags.append("javascript")
        if "java" in path_str or "java" in title_lower:
            tags.append("java")
        if any(lang in path_str or lang in title_lower for lang in ["c++", "cpp"]):
            tags.append("cpp")

        # Difficulty tags
        if any(word in title_lower for word in ["intro", "introduction", "beginner", "basics", "fundamentals"]):
            tags.append("beginner")
        if any(word in title_lower for word in ["advanced", "expert", "deep dive"]):
            tags.append("advanced")

        # Topic tags
        if any(word in title_lower for word in ["algorithm", "algorithms"]):
            tags.append("algorithms")
        if any(word in title_lower for word in ["data structure", "datastructure"]):
            tags.append("data-structures")
        if any(word in title_lower for word in ["web", "html", "css"]):
            tags.append("web-development")
        if "math" in title_lower or "mathematics" in title_lower:
            tags.append("mathematics")

        # Source-specific tags
        source = self.infer_source_attribution(video_path)
        if source == SourceAttribution.MIT_OCW:
            tags.append("university")
        if source == SourceAttribution.KHAN_ACADEMY:
            tags.append("interactive")

        # Remove duplicates
        tags = list(set(tags))

        logger.debug("tags_generated", file=video_path.name, tags=tags)

        return tags if tags else ["educational"]  # Default tag

    def convert_to_windows_path(self, linux_path: Path) -> str:
        """Convert Linux path to Windows UNC path for OBS.

        Args:
            linux_path: Linux filesystem path

        Returns:
            Windows UNC path string
        """
        # Convert /home/turtle_wolfe/... to \\wsl.localhost\Debian\home\turtle_wolfe\...
        linux_str = str(linux_path)
        windows_str = self.WINDOWS_PREFIX + linux_str.replace("/", "\\")

        return windows_str

    def generate_attribution_text(
        self,
        source: SourceAttribution,
        course_name: str,
        title: str,
        license_type: str,
    ) -> str:
        """Generate formatted attribution text for OBS display.

        Args:
            source: Content source
            course_name: Course name
            title: Video title
            license_type: License type

        Returns:
            Formatted attribution string
        """
        source_name_map = {
            SourceAttribution.MIT_OCW: "MIT OCW",
            SourceAttribution.CS50: "Harvard CS50",
            SourceAttribution.KHAN_ACADEMY: "Khan Academy",
            SourceAttribution.BLENDER: "Big Buck Bunny",
        }

        source_name = source_name_map.get(source, str(source))

        return f"{source_name} {course_name}: {title} - {license_type}"

    def get_course_name(self, video_path: Path, source: SourceAttribution) -> str:
        """Extract course name from directory structure.

        Args:
            video_path: Path to video file
            source: Content source

        Returns:
            Course name string
        """
        # Try to extract from parent directory name
        try:
            rel_path = video_path.relative_to(self.content_root)
            parts = rel_path.parts

            if len(parts) >= 2:
                # e.g., general/mit-ocw-6.0001/video.mp4 -> "6.0001"
                course_dir = parts[1]

                # Clean up course name
                if source == SourceAttribution.MIT_OCW:
                    # Extract course number (e.g., "mit-ocw-6.0001" -> "6.0001")
                    match = re.search(r"(\d+[\.\-]\d+)", course_dir)
                    return match.group(1) if match else course_dir

                if source == SourceAttribution.CS50:
                    return "Introduction to Computer Science"

                if source == SourceAttribution.KHAN_ACADEMY:
                    return "Computer Programming"

            return "Course"  # Default

        except ValueError:
            return "Course"

    def get_license_type(self, source: SourceAttribution) -> str:
        """Get license type for source.

        Args:
            source: Content source

        Returns:
            License type string
        """
        license_map = {
            SourceAttribution.MIT_OCW: "CC BY-NC-SA 4.0",
            SourceAttribution.CS50: "CC BY-NC-SA 4.0",
            SourceAttribution.KHAN_ACADEMY: "CC BY-NC-SA",
            SourceAttribution.BLENDER: "CC BY 3.0",
        }
        return license_map.get(source, "Unknown License")

    def get_source_url(self, source: SourceAttribution, course_name: str) -> str:
        """Get source URL for content.

        Args:
            source: Content source
            course_name: Course name

        Returns:
            Source URL string
        """
        url_map = {
            SourceAttribution.MIT_OCW: f"https://ocw.mit.edu/courses/{course_name.lower().replace('.', '-')}/",
            SourceAttribution.CS50: "https://cs50.harvard.edu/",
            SourceAttribution.KHAN_ACADEMY: "https://www.khanacademy.org/computing/computer-programming",
            SourceAttribution.BLENDER: "https://peach.blender.org/",
        }
        return url_map.get(source, "")

    def create_content_source(self, video_path: Path) -> Optional[ContentSource]:
        """Create ContentSource entity from video file.

        Implements T042-T049: Full metadata extraction pipeline.

        Args:
            video_path: Path to video file

        Returns:
            ContentSource entity or None if extraction failed
        """
        try:
            # Extract metadata with ffprobe
            metadata = self.extract_metadata(video_path)

            # Parse filename
            filename_data = self.parse_filename(video_path)

            # Infer attributes from path
            source = self.infer_source_attribution(video_path)
            time_blocks = self.infer_time_blocks(video_path)
            age_rating = self.infer_age_rating(video_path)
            tags = self.generate_tags(video_path, filename_data["title"])

            # Get course and license info
            course_name = self.get_course_name(video_path, source)
            license_type = self.get_license_type(source)
            source_url = self.get_source_url(source, course_name)

            # Generate attribution text
            attribution_text = self.generate_attribution_text(
                source, course_name, filename_data["title"], license_type
            )

            # Convert paths
            windows_path = self.convert_to_windows_path(video_path)

            # Create ContentSource
            content_source = ContentSource(
                source_id=uuid4(),
                title=filename_data["title"],
                file_path=str(video_path),
                windows_obs_path=windows_path,
                duration_sec=metadata["duration_sec"],
                file_size_mb=metadata["file_size_mb"],
                width=metadata["width"],
                height=metadata["height"],
                source_attribution=source,
                license_type=license_type,
                course_name=course_name,
                source_url=source_url,
                attribution_text=attribution_text,
                age_rating=age_rating,
                time_blocks=time_blocks,
                priority=5,  # Default priority (middle of 1-10 scale)
                tags=tags,
                last_verified=datetime.now(timezone.utc),
            )

            logger.info(
                "content_source_created",
                title=content_source.title,
                source=content_source.source_attribution.value,
                duration_sec=content_source.duration_sec,
                time_blocks=content_source.time_blocks,
            )

            return content_source

        except MetadataExtractionError as e:
            logger.error(
                "content_source_creation_failed",
                file=str(video_path),
                error=str(e),
            )
            return None
        except Exception as e:
            logger.error(
                "content_source_creation_unexpected_error",
                file=str(video_path),
                error=str(e),
                exc_info=True,
            )
            return None

    def export_to_json(self, content_sources: List[ContentSource], output_path: Path) -> None:
        """Export content sources to JSON file.

        Implements T049: JSON export for database import.

        Args:
            content_sources: List of ContentSource entities
            output_path: Path to output JSON file
        """
        # Convert to dict list
        data = [source.model_dump(mode="json") for source in content_sources]

        # Write JSON file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(
            "content_sources_exported",
            output=str(output_path),
            count=len(content_sources),
        )

    def print_summary(self, content_sources: List[ContentSource]) -> None:
        """Print summary statistics of content library.

        Implements T050: Summary statistics output.

        Args:
            content_sources: List of ContentSource entities
        """
        if not content_sources:
            logger.warning("no_content_sources_found")
            print("\n❌ No content sources found\n")
            return

        # Calculate statistics
        total_videos = len(content_sources)
        total_duration_sec = sum(s.duration_sec for s in content_sources)
        total_duration_hrs = total_duration_sec / 3600
        total_size_gb = sum(s.file_size_mb for s in content_sources) / 1024

        # Count by source
        source_counts = {}
        for source in content_sources:
            key = source.source_attribution.value
            source_counts[key] = source_counts.get(key, 0) + 1

        # Count by time block
        time_block_counts = {}
        for source in content_sources:
            for block in source.time_blocks:
                time_block_counts[block] = time_block_counts.get(block, 0) + 1

        # Print summary
        print("\n" + "=" * 60)
        print("Content Library Summary")
        print("=" * 60)
        print(f"\nTotal Videos: {total_videos}")
        print(f"Total Duration: {total_duration_hrs:.2f} hours ({total_duration_sec:,} seconds)")
        print(f"Total Size: {total_size_gb:.2f} GB ({sum(s.file_size_mb for s in content_sources):.2f} MB)")

        print("\nBy Source:")
        for source, count in sorted(source_counts.items()):
            print(f"  {source}: {count} videos")

        print("\nBy Time Block:")
        for block, count in sorted(time_block_counts.items()):
            print(f"  {block}: {count} videos")

        print("\n" + "=" * 60 + "\n")

        logger.info(
            "content_summary",
            total_videos=total_videos,
            total_duration_hrs=round(total_duration_hrs, 2),
            total_size_gb=round(total_size_gb, 2),
            sources=source_counts,
            time_blocks=time_block_counts,
        )
