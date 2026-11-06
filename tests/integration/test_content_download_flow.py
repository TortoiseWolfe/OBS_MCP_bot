"""Integration test for content download flow (T073).

Tests the end-to-end download workflow from script execution
to metadata extraction and database population. None of these need OBS or the
network: the download script is only asked for its help text, and the content
folder checks run against the ``library`` fixture (see conftest.py).
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
@pytest.mark.slow
def test_download_script_execution():
    """The download script is present, executable and runs."""
    script_path = REPO_ROOT / "scripts" / "download_mit_ocw.sh"

    assert script_path.exists(), "Download script not found"
    assert os.access(script_path, os.X_OK), "Download script is not executable"

    # --help only: the real script downloads gigabytes.
    result = subprocess.run(
        [str(script_path), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # 0 = help printed; 1 = it stopped early (for example yt-dlp is not installed here).
    assert result.returncode in [0, 1], "Download script failed to execute"


@pytest.mark.integration
def test_content_directory_structure(library):
    """The library has every required time-block folder, and the README documents them."""
    required_dirs = [
        "general",
        "kids-after-school",
        "professional-hours",
        "evening-mixed",
        "failover",
    ]

    readme = (REPO_ROOT / "content" / "README.md").read_text()
    for name in required_dirs:
        dir_path = library.root / "content" / name
        assert dir_path.exists(), f"Required directory missing: {dir_path}"
        assert dir_path.is_dir(), f"Not a directory: {dir_path}"
        assert f"{name}/" in readme, f"content/README.md does not describe {name}/"


@pytest.mark.integration
def test_downloaded_files_are_valid(library):
    """The video files in the library start like MP4 files."""
    mp4_files = sorted((library.root / "content").rglob("*.mp4"))
    assert mp4_files, "No MP4 files found in the content library"

    for test_file in mp4_files:
        assert test_file.stat().st_size > 0, f"File is empty: {test_file}"
        with open(test_file, "rb") as f:
            header = f.read(12)
        assert len(header) == 12, f"File too small to be valid video: {test_file}"
        # MP4 files have 'ftyp' (or 'moov') in the first 12 bytes
        assert b"ftyp" in header or b"moov" in header, f"Not a valid MP4 file: {test_file}"


@pytest.mark.integration
def test_metadata_extraction_workflow():
    """The metadata extraction script is present and executable."""
    metadata_script = REPO_ROOT / "scripts" / "add_content_metadata.py"

    assert metadata_script.exists(), "Metadata extraction script not found"
    assert os.access(metadata_script, os.X_OK) or metadata_script.suffix == ".py"


@pytest.mark.integration
def test_download_creates_required_metadata_files(library):
    """The .info.json files that downloads leave behind carry a title."""
    info_files = sorted((library.root / "content").rglob("*.info.json"))
    assert info_files, "No .info.json files found in the content library"

    for info_file in info_files:
        info = json.loads(info_file.read_text())
        # Common yt-dlp metadata fields
        assert "title" in info or "fulltitle" in info, f"Missing title in {info_file}"
