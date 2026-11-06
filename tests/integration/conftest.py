"""Fixtures for the integration tests.

Two kinds of integration test live in this folder:

* Tests marked ``requires_obs`` talk to a real OBS over its websocket. CI leaves them out
  (``-m "not requires_obs"``); run them on a machine with OBS up. They use ``live_obs``.
* Every other integration test runs everywhere. The ones about the content library use the
  ``library`` fixture: a small content folder and database built in a temporary directory
  (the real library is gigabytes of downloaded video and is not in the repository).
  Set ``OBS_BOT_REAL_LIBRARY=1`` to point those tests at the tower's real ``content/`` and
  ``data/obs_bot.db`` in the current directory instead.
"""

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio

from src.config.settings import Settings
from src.models.content_library import AgeRating, ContentSource, SourceAttribution
from src.persistence.db import SCHEMA_SQL
from src.persistence.repositories.content_library import ContentSourceRepository
from src.services.obs_attribution_updater import OBSAttributionUpdater
from src.services.obs_controller import OBSController

REPO_ROOT = Path(__file__).resolve().parents[2]

CONTENT_DIRS = [
    "general",
    "kids-after-school",
    "professional-hours",
    "evening-mixed",
    "failover",
]

# A just-big-enough MP4 start: 4-byte box size, then the "ftyp" marker, then a brand.
FAKE_MP4_HEADER = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"

# (title, folder, source, license in the seeded license_info table, age, time blocks, minutes)
SAMPLE_VIDEOS = [
    ("MIT 6.0001 Lecture 1", "general", SourceAttribution.MIT_OCW, "CC BY-NC-SA 4.0", AgeRating.ALL, ["general"], 50),
    ("CS50 Lecture 0", "general", SourceAttribution.CS50, "CC BY-NC-SA 4.0", AgeRating.ALL, ["general", "evening_mixed"], 110),
    ("Khan Academy Intro to JS", "kids-after-school", SourceAttribution.KHAN_ACADEMY, "CC BY-NC-SA", AgeRating.KIDS, ["kids_after_school"], 12),
    ("Advanced Algorithms", "professional-hours", SourceAttribution.MIT_OCW, "CC BY-NC-SA 4.0", AgeRating.ADULT, ["professional_hours"], 75),
    ("General Video 1", "general", SourceAttribution.CS50, "CC BY-NC-SA 4.0", AgeRating.ALL, ["general", "evening_mixed"], 30),
    ("Big Buck Bunny", "failover", SourceAttribution.BLENDER, "CC BY 3.0", AgeRating.ALL, ["failover"], 10),
]


@dataclass
class Library:
    """Where a content library lives and how to find a database path on disk."""

    root: Path
    db_path: Path
    synthetic: bool

    def resolve(self, file_path: str) -> Path:
        """Map a path stored in the database to the file on this machine."""
        if self.synthetic and file_path.startswith("/app/content/"):
            return self.root / "content" / file_path[len("/app/content/"):]
        return Path(file_path)


def _build_synthetic_library(root: Path) -> Library:
    for name in CONTENT_DIRS:
        (root / "content" / name).mkdir(parents=True)
    (root / "data").mkdir()
    db_path = root / "data" / "obs_bot.db"

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()

    repo = ContentSourceRepository(str(db_path))
    for index, (title, folder, source, license_type, age, blocks, minutes) in enumerate(SAMPLE_VIDEOS, 1):
        name = f"video_{index:02d}.mp4"
        video = root / "content" / folder / name
        video.write_bytes(FAKE_MP4_HEADER + b"\x00" * 1024)
        if index == 1:
            (root / "content" / folder / "video_01.info.json").write_text(
                f'{{"title": "{title}", "duration": {minutes * 60}}}'
            )
        repo.create(
            ContentSource(
                title=title,
                file_path=f"/app/content/{folder}/{name}",
                windows_obs_path=f"\\\\wsl.localhost\\Debian\\app\\content\\{folder}\\{name}",
                duration_sec=minutes * 60,
                file_size_mb=float(minutes * 8),
                width=1920,
                height=1080,
                source_attribution=source,
                license_type=license_type,
                course_name=f"Sample course {index}",
                source_url=f"https://example.org/sample/{index}",
                attribution_text=f"{source.value} sample {index}: {title} - {license_type}",
                age_rating=age,
                time_blocks=blocks,
                priority=5,
                tags=["sample"],
                last_verified=datetime.utcnow(),
            )
        )
    return Library(root=root, db_path=db_path, synthetic=True)


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A content library to test against, with the current directory set to its root."""
    if os.getenv("OBS_BOT_REAL_LIBRARY") == "1":
        root = Path.cwd()
        return Library(root=root, db_path=root / "data" / "obs_bot.db", synthetic=False)
    lib = _build_synthetic_library(tmp_path)
    monkeypatch.chdir(tmp_path)
    return lib


@pytest_asyncio.fixture
async def live_obs():
    """A connected OBSController for the tests marked requires_obs.

    With OBS down this errors at setup (an honest failure, not a skip).
    """
    controller = OBSController(Settings().obs)
    await controller.connect()
    yield controller
    await controller.disconnect()


@pytest.fixture
def make_content():
    """Factory for a ContentSource with the title and license a test wants shown."""

    def _make(
        title: str = "What is Computation?",
        license_type: str = "CC BY-NC-SA 4.0",
        source: SourceAttribution = SourceAttribution.MIT_OCW,
    ) -> ContentSource:
        return ContentSource(
            title=title,
            file_path="/app/content/general/attribution_test.mp4",
            windows_obs_path="\\\\wsl.localhost\\Debian\\app\\content\\general\\attribution_test.mp4",
            duration_sec=600,
            file_size_mb=100.0,
            width=1920,
            height=1080,
            source_attribution=source,
            license_type=license_type,
            course_name="Attribution test course",
            source_url="https://example.org/attribution-test",
            attribution_text=f"{source.value}: {title} - {license_type}",
            age_rating=AgeRating.ALL,
            time_blocks=["general"],
            priority=5,
            tags=["test"],
            last_verified=datetime.utcnow(),
        )

    return _make


@pytest_asyncio.fixture
async def attribution_updater(live_obs):
    """An OBSAttributionUpdater on a live OBS, with its text source made if missing."""
    updater = OBSAttributionUpdater(live_obs)
    if not await updater.verify_text_source_exists():
        await live_obs.create_text_source(
            scene_name=await live_obs.get_current_scene(),
            source_name=updater.text_source_name,
            text="",
        )
    yield updater
    await updater.clear_attribution()
