#!/usr/bin/env python3
"""Content Metadata Extraction and Database Import Script.

Scans content directories, extracts video metadata using ffprobe,
and populates the content_sources table in SQLite database.

Implements User Story 3: Content Metadata Extraction and Tracking (US3).
Implements T051: Metadata extraction CLI tool.
Implements T055: Database import logic.

Usage:
    python3 scripts/add_content_metadata.py                    # Scan and import to database
    python3 scripts/add_content_metadata.py --dry-run          # Scan only, don't import
    python3 scripts/add_content_metadata.py --json-only        # Export to JSON only
    python3 scripts/add_content_metadata.py --help             # Show help
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for src imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.content_metadata_manager import ContentMetadataManager
from src.services.content_library_scanner import ContentLibraryScanner
from src.persistence.repositories.content_library import (
    ContentSourceRepository,
    ContentLibraryRepository,
)


def main():
    """Main entry point for metadata extraction script."""
    parser = argparse.ArgumentParser(
        description="Extract content metadata and import to database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full scan and database import:
  python3 scripts/add_content_metadata.py

  # Dry run (scan only, don't import):
  python3 scripts/add_content_metadata.py --dry-run

  # Export to JSON only:
  python3 scripts/add_content_metadata.py --json-only

  # Specify custom content root:
  python3 scripts/add_content_metadata.py --content-root /custom/path

Database Location:
  data/obs_bot.db (created automatically if missing)

Content Root:
  Default: /home/turtle_wolfe/repos/OBS_bot/content
  Override with --content-root flag
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and display summary without importing to database",
    )

    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Export to JSON only (scripts/content_metadata.json)",
    )

    parser.add_argument(
        "--content-root",
        type=Path,
        default=Path("/home/turtle_wolfe/repos/OBS_bot/content"),
        help="Content root directory to scan (default: /home/turtle_wolfe/repos/OBS_bot/content)",
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/obs_bot.db"),
        help="Database path (default: data/obs_bot.db)",
    )

    args = parser.parse_args()

    # Validate content root exists
    if not args.content_root.exists():
        print(f"❌ Error: Content root directory not found: {args.content_root}")
        print("\nPlease ensure the content directory exists and contains video files.")
        print("Expected structure:")
        print("  content/")
        print("  ├── kids-after-school/")
        print("  ├── professional-hours/")
        print("  ├── evening-mixed/")
        print("  ├── general/")
        print("  └── failover/")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("Content Metadata Extraction and Database Import")
    print("=" * 70)
    print(f"\nContent Root: {args.content_root}")
    print(f"Database Path: {args.db_path}")

    if args.dry_run:
        print("Mode: DRY RUN (scan only, no database changes)")
    elif args.json_only:
        print("Mode: JSON EXPORT ONLY")
    else:
        print("Mode: FULL SCAN + DATABASE IMPORT")

    print("\n" + "-" * 70)

    # Initialize metadata manager
    metadata_manager = ContentMetadataManager(content_root=args.content_root)

    # Scan content library
    print("\n📁 Scanning content directories...")
    print("-" * 70)

    video_files = []
    time_block_dirs = [
        args.content_root / "kids-after-school",
        args.content_root / "professional-hours",
        args.content_root / "evening-mixed",
        args.content_root / "general",
        args.content_root / "failover",
    ]

    for time_block_dir in time_block_dirs:
        if time_block_dir.exists():
            files = metadata_manager.scan_directory(time_block_dir)
            print(f"  {time_block_dir.name}: {len(files)} videos")
            video_files.extend(files)
        else:
            print(f"  {time_block_dir.name}: (directory missing)")

    if not video_files:
        print("\n❌ No video files found.")
        print("\nTo download content, run:")
        print("  cd scripts/")
        print("  ./download_all_content.sh")
        sys.exit(0)

    print(f"\n✅ Found {len(video_files)} total video files")

    # Extract metadata from all videos
    print("\n🔍 Extracting metadata (this may take a few minutes)...")
    print("-" * 70)

    content_sources = []
    failed_count = 0

    for i, video_path in enumerate(video_files, 1):
        # Show progress
        if i % 5 == 0 or i == len(video_files):
            print(f"  Progress: {i}/{len(video_files)} ({int(i/len(video_files)*100)}%)")

        # Create ContentSource entity
        content_source = metadata_manager.create_content_source(video_path)

        if content_source:
            content_sources.append(content_source)
        else:
            failed_count += 1

    print(f"\n✅ Successfully extracted metadata from {len(content_sources)} videos")
    if failed_count > 0:
        print(f"⚠️  Failed to extract metadata from {failed_count} videos")

    # Print summary
    metadata_manager.print_summary(content_sources)

    # Export to JSON if requested
    if args.json_only or args.dry_run:
        output_json = Path("scripts/content_metadata.json")
        metadata_manager.export_to_json(content_sources, output_json)
        print(f"\n💾 Metadata exported to: {output_json}")

    # Import to database if not dry-run
    if not args.dry_run and not args.json_only:
        print("\n💾 Importing to database...")
        print("-" * 70)

        # Ensure database directory exists
        args.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize repositories
        content_source_repo = ContentSourceRepository(str(args.db_path))
        content_library_repo = ContentLibraryRepository(str(args.db_path))

        # Initialize scanner
        scanner = ContentLibraryScanner(
            content_source_repo=content_source_repo,
            content_library_repo=content_library_repo,
            metadata_manager=metadata_manager,
        )

        # Persist content sources
        scanner._persist_content_sources(content_sources)

        # Update library statistics
        library = scanner.update_library_statistics(content_sources)

        print(f"\n✅ Database import complete!")
        print(f"\nLibrary Statistics:")
        print(f"  Total Videos: {library.total_videos}")
        print(f"  Total Duration: {library.total_duration_sec / 3600:.2f} hours")
        print(f"  Total Size: {library.total_size_mb / 1024:.2f} GB")
        print(f"  Last Scanned: {library.last_scanned}")
        print(f"\nBy Source:")
        print(f"  MIT OCW: {library.mit_ocw_count}")
        print(f"  Harvard CS50: {library.cs50_count}")
        print(f"  Khan Academy: {library.khan_academy_count}")
        print(f"  Blender: {library.blender_count}")

    # Next steps
    print("\n" + "=" * 70)
    print("Next Steps")
    print("=" * 70)

    if args.dry_run:
        print("\n1. Review the summary above")
        print("2. If everything looks good, run without --dry-run to import:")
        print("   python3 scripts/add_content_metadata.py")
    elif args.json_only:
        print("\n1. Review scripts/content_metadata.json")
        print("2. Import to database:")
        print("   python3 scripts/add_content_metadata.py")
    else:
        print("\n1. ✅ Content metadata is now in database")
        print("2. Test content scheduling:")
        print("   python3 -m src.main  # Start orchestrator")
        print("3. Verify OBS can access content via WSL2 paths")
        print("4. Check attribution text updates in OBS")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
