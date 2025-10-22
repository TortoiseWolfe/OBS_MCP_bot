#!/bin/bash
# MIT OpenCourseWare 6.0001 Python Course Downloader
# Downloads 12 lectures from MIT OCW Introduction to Computer Science and Programming in Python
# License: CC BY-NC-SA 4.0
# Source: https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/
#
# Implements:
# - T017: MIT OCW download script with yt-dlp
# - T021: Disk space validation (10 GB minimum)
# - T022: Resume capability (--no-overwrites)
# - T023: Rate limiting (--throttled-rate 100K)
# - T024: yt-dlp installation check

set -e  # Exit on error

# Configuration
COURSE_NAME="mit-ocw-6.0001"
TARGET_DIR="content/general/${COURSE_NAME}"
PLAYLIST_URL="https://www.youtube.com/playlist?list=PLUl4u3cNGP63WbdFxL8giv4yhgdMGaZNA"
MIN_DISK_SPACE_GB=10
RATE_LIMIT="100K"  # Throttle to 100 KB/s to avoid overwhelming source
LECTURE_COUNT=12   # Download first 12 lectures only

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== MIT OCW 6.0001 Python Course Downloader ===${NC}"
echo -e "${BLUE}Course: Introduction to Computer Science and Programming in Python${NC}"
echo -e "${BLUE}License: CC BY-NC-SA 4.0${NC}"
echo ""

# T024: Check if yt-dlp is installed
if ! command -v yt-dlp &> /dev/null; then
    echo -e "${RED}ERROR: yt-dlp is not installed${NC}"
    echo ""
    echo "Installation instructions:"
    echo "  Ubuntu/Debian: sudo apt install yt-dlp"
    echo "  macOS (Homebrew): brew install yt-dlp"
    echo "  Python (pip): pip install yt-dlp"
    echo ""
    echo "Or download from: https://github.com/yt-dlp/yt-dlp"
    exit 1
fi

echo -e "${GREEN}✓ yt-dlp found: $(yt-dlp --version)${NC}"

# T021: Check available disk space (10 GB minimum)
echo ""
echo "Checking disk space..."
AVAILABLE_SPACE_KB=$(df -k "$(dirname "$TARGET_DIR")" 2>/dev/null | tail -1 | awk '{print $4}' || echo "0")
AVAILABLE_SPACE_GB=$((AVAILABLE_SPACE_KB / 1024 / 1024))

if [ "$AVAILABLE_SPACE_GB" -lt "$MIN_DISK_SPACE_GB" ]; then
    echo -e "${RED}ERROR: Insufficient disk space${NC}"
    echo "  Required: ${MIN_DISK_SPACE_GB} GB"
    echo "  Available: ${AVAILABLE_SPACE_GB} GB"
    echo ""
    echo "Please free up disk space and try again."
    exit 1
fi

echo -e "${GREEN}✓ Sufficient disk space: ${AVAILABLE_SPACE_GB} GB available${NC}"

# T039: Validate time-block directory structure
echo ""
echo "Validating directory structure..."
CONTENT_DIR="content"
TIME_BLOCK_DIR="content/general"

if [ ! -d "$CONTENT_DIR" ]; then
    echo -e "${RED}ERROR: Content directory not found: $CONTENT_DIR${NC}"
    echo ""
    echo "Please create the content directory structure first:"
    echo "  mkdir -p content/general content/kids-after-school content/evening-mixed content/failover"
    echo ""
    exit 1
fi

if [ ! -w "$CONTENT_DIR" ]; then
    echo -e "${RED}ERROR: Content directory is not writable: $CONTENT_DIR${NC}"
    echo ""
    echo "Fix permissions with:"
    echo "  chmod 755 content/"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Content directory structure valid${NC}"

# Create target directory
echo ""
echo "Creating target directory: ${TARGET_DIR}"
mkdir -p "$TARGET_DIR"

# Download configuration
echo ""
echo -e "${YELLOW}Starting download...${NC}"
echo "  Course: MIT OCW 6.0001"
echo "  Lectures: 1-${LECTURE_COUNT}"
echo "  Target: ${TARGET_DIR}"
echo "  Format: 720p MP4 (best quality up to 720p)"
echo "  Rate limit: ${RATE_LIMIT}"
echo ""

# T017: Download videos using yt-dlp
# T022: --no-overwrites for resume capability
# T023: --throttled-rate for rate limiting
yt-dlp \
    --format "bestvideo[height<=720]+bestaudio/best[height<=720]" \
    --merge-output-format mp4 \
    --output "${TARGET_DIR}/%(playlist_index)02d-%(title)s.%(ext)s" \
    --no-overwrites \
    --throttled-rate "$RATE_LIMIT" \
    --restrict-filenames \
    --no-playlist-reverse \
    --playlist-items 1-${LECTURE_COUNT} \
    --write-info-json \
    --write-description \
    "$PLAYLIST_URL"

DOWNLOAD_STATUS=$?

echo ""
if [ $DOWNLOAD_STATUS -eq 0 ]; then
    echo -e "${GREEN}=== Download Complete ===${NC}"
    echo ""
    echo "Downloaded ${LECTURE_COUNT} lectures to: ${TARGET_DIR}"
    echo ""
    echo "Next steps:"
    echo "  1. Run metadata extraction: python scripts/add_content_metadata.py"
    echo "  2. Verify videos are playable in OBS"
    echo "  3. Update content library database"
    echo ""

    # Show downloaded files
    echo "Downloaded files:"
    ls -lh "$TARGET_DIR"/*.mp4 2>/dev/null | awk '{print "  " $9 " (" $5 ")")' || echo "  No MP4 files found"
    echo ""

    echo -e "${BLUE}License Information:${NC}"
    echo "  These videos are licensed under CC BY-NC-SA 4.0"
    echo "  Attribution: MIT OpenCourseWare"
    echo "  Source: https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/"
    echo ""
else
    echo -e "${RED}=== Download Failed ===${NC}"
    echo ""
    echo "Common issues:"
    echo "  - HTTP 403/429 errors: YouTube blocking automated downloads"
    echo "  - PO token errors: YouTube requiring browser authentication"
    echo "  - Network connectivity issues"
    echo ""
    echo "Alternative: Try CDN download from archive.org"
    echo "  URL: https://archive.org/download/MIT6.0001F16/"
    echo "  Download manually and place in: ${TARGET_DIR}"
    echo ""
    exit 1
fi
