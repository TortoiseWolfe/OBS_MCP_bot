#!/bin/bash
###############################################################################
# Phased Content Download Script
#
# Downloads minimal content strategically for MVP testing and validation.
# Total size: ~1-2 GB (vs. 10 GB full library)
#
# Strategy:
# - Phase 1: Failover content (already exists - Big Buck Bunny)
# - Phase 2: General content (2-3 MIT OCW videos for testing)
# - Phase 3: Kids content (2 Khan Academy videos)
# - Phase 4: Evening content (2 CS50 videos)
#
# Usage:
#   ./download_phased.sh                 # Download all phases
#   ./download_phased.sh --phase 2       # Download specific phase only
#   ./download_phased.sh --full          # Download full library (all content)
###############################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Base directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTENT_ROOT="$SCRIPT_DIR/../content"

# Parse arguments
PHASE="all"
FULL_DOWNLOAD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --phase)
            PHASE="$2"
            shift 2
            ;;
        --full)
            FULL_DOWNLOAD=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --phase N      Download specific phase only (1-4)"
            echo "  --full         Download full library (10+ GB)"
            echo "  --help         Show this help message"
            echo ""
            echo "Phases:"
            echo "  1. Failover content (Big Buck Bunny - already exists)"
            echo "  2. General content (2-3 MIT OCW videos, ~500 MB)"
            echo "  3. Kids content (2 Khan Academy videos, ~200 MB)"
            echo "  4. Evening content (2 CS50 videos, ~400 MB)"
            echo ""
            echo "Examples:"
            echo "  $0                    # Download all phases (MVP testing)"
            echo "  $0 --phase 2          # Download only Phase 2"
            echo "  $0 --full             # Download full library"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}Phased Content Download Script${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

if [ "$FULL_DOWNLOAD" = true ]; then
    echo -e "${YELLOW}Mode: FULL LIBRARY DOWNLOAD (10+ GB)${NC}"
    echo ""
    read -p "Are you sure you want to download the full library? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
else
    echo -e "${GREEN}Mode: PHASED MVP DOWNLOAD (~1-2 GB)${NC}"
fi

echo ""

# Check for yt-dlp
if ! command -v yt-dlp &> /dev/null; then
    echo -e "${RED}Error: yt-dlp is not installed${NC}"
    echo "Install with: pip install yt-dlp"
    exit 1
fi

# Check disk space (require 5 GB minimum for phased, 15 GB for full)
if [ "$FULL_DOWNLOAD" = true ]; then
    REQUIRED_SPACE_KB=$((15 * 1024 * 1024))
    REQUIRED_GB=15
else
    REQUIRED_SPACE_KB=$((5 * 1024 * 1024))
    REQUIRED_GB=5
fi

AVAILABLE_SPACE_KB=$(df --output=avail "$SCRIPT_DIR" | tail -n 1)

if [ "$AVAILABLE_SPACE_KB" -lt "$REQUIRED_SPACE_KB" ]; then
    AVAILABLE_GB=$((AVAILABLE_SPACE_KB / 1024 / 1024))
    echo -e "${RED}Error: Insufficient disk space${NC}"
    echo -e "${RED}Required: ${REQUIRED_GB} GB, Available: ${AVAILABLE_GB} GB${NC}"
    exit 1
fi

echo -e "${GREEN}✓ yt-dlp installed${NC}"
echo -e "${GREEN}✓ Disk space sufficient (${REQUIRED_GB} GB required)${NC}"
echo ""

###############################################################################
# Phase 1: Failover Content (Big Buck Bunny)
###############################################################################
download_phase_1() {
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}Phase 1: Failover Content (Big Buck Bunny)${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo ""

    FAILOVER_DIR="$CONTENT_ROOT/failover"
    mkdir -p "$FAILOVER_DIR"

    if [ -f "$FAILOVER_DIR/big_buck_bunny.mp4" ]; then
        echo -e "${GREEN}✓ Failover content already exists${NC}"
    else
        echo "Downloading Big Buck Bunny (151 MB)..."
        cd "$FAILOVER_DIR"

        wget -O big_buck_bunny.mp4 \
            "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4" \
            2>&1 | grep --line-buffered "%" | sed 's/^/  /'

        echo -e "${GREEN}✓ Phase 1 complete${NC}"
    fi
    echo ""
}

###############################################################################
# Phase 2: General Content (MIT OCW - 2-3 videos)
###############################################################################
download_phase_2() {
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}Phase 2: General Content (MIT OpenCourseWare)${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo ""

    GENERAL_DIR="$CONTENT_ROOT/general/mit-ocw-6.0001"
    mkdir -p "$GENERAL_DIR"

    if [ "$FULL_DOWNLOAD" = true ]; then
        echo "Downloading full MIT OCW 6.0001 course (12 lectures, ~3-5 GB)..."
        PLAYLIST_ITEMS="1-12"
    else
        echo "Downloading first 3 MIT OCW 6.0001 lectures (~500 MB)..."
        PLAYLIST_ITEMS="1-3"
    fi

    cd "$GENERAL_DIR"

    yt-dlp \
        --playlist-items "$PLAYLIST_ITEMS" \
        --format 'bestvideo[height<=720]+bestaudio/best[height<=720]' \
        --output '%(playlist_index)02d-%(title)s.%(ext)s' \
        --no-overwrites \
        --throttled-rate 100K \
        --progress \
        "https://www.youtube.com/playlist?list=PLUl4u3cNGP63WbdFxL8giv4yhgdMGaZNA" \
        2>&1 | grep --line-buffered -E "(Downloading|has already been downloaded|ETA)" | sed 's/^/  /'

    echo -e "${GREEN}✓ Phase 2 complete${NC}"
    echo ""
}

###############################################################################
# Phase 3: Kids Content (Khan Academy - 2 videos)
###############################################################################
download_phase_3() {
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}Phase 3: Kids Content (Khan Academy)${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo ""

    KIDS_DIR="$CONTENT_ROOT/kids-after-school/khan-academy"
    mkdir -p "$KIDS_DIR"

    if [ "$FULL_DOWNLOAD" = true ]; then
        echo "Downloading Khan Academy programming playlist (~1-2 GB)..."
        PLAYLIST_ITEMS="1-10"
    else
        echo "Downloading 2 Khan Academy intro videos (~200 MB)..."
        PLAYLIST_ITEMS="1-2"
    fi

    cd "$KIDS_DIR"

    # Khan Academy: Intro to JS Drawing & Animation
    yt-dlp \
        --playlist-items "$PLAYLIST_ITEMS" \
        --format 'bestvideo[height<=720]+bestaudio/best[height<=720]' \
        --output '%(playlist_index)02d-%(title)s.%(ext)s' \
        --no-overwrites \
        --throttled-rate 100K \
        --progress \
        "https://www.youtube.com/playlist?list=PLSQl0a2vh4HC5feHa6Rc5c0wbRTx56nF7" \
        2>&1 | grep --line-buffered -E "(Downloading|has already been downloaded|ETA)" | sed 's/^/  /'

    echo -e "${GREEN}✓ Phase 3 complete${NC}"
    echo ""
}

###############################################################################
# Phase 4: Evening Content (Harvard CS50 - 2 videos)
###############################################################################
download_phase_4() {
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}Phase 4: Evening Content (Harvard CS50)${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo ""

    EVENING_DIR="$CONTENT_ROOT/evening-mixed/harvard-cs50"
    mkdir -p "$EVENING_DIR"

    if [ "$FULL_DOWNLOAD" = true ]; then
        echo "Downloading full CS50 2023 course (5+ lectures, ~2-3 GB)..."
        PLAYLIST_ITEMS="0-4"
    else
        echo "Downloading 2 CS50 lectures (~400 MB)..."
        PLAYLIST_ITEMS="0-1"
    fi

    cd "$EVENING_DIR"

    yt-dlp \
        --playlist-items "$PLAYLIST_ITEMS" \
        --format 'bestvideo[height<=720]+bestaudio/best[height<=720]' \
        --output '%(playlist_index)02d-%(title)s.%(ext)s' \
        --no-overwrites \
        --throttled-rate 100K \
        --progress \
        "https://www.youtube.com/playlist?list=PLhQjrBD2T3817j24-GogXmWqO5Q5vYy0V" \
        2>&1 | grep --line-buffered -E "(Downloading|has already been downloaded|ETA)" | sed 's/^/  /'

    echo -e "${GREEN}✓ Phase 4 complete${NC}"
    echo ""
}

###############################################################################
# Main Execution
###############################################################################

START_TIME=$(date +%s)

case $PHASE in
    1)
        download_phase_1
        ;;
    2)
        download_phase_2
        ;;
    3)
        download_phase_3
        ;;
    4)
        download_phase_4
        ;;
    all)
        download_phase_1
        download_phase_2
        download_phase_3
        download_phase_4
        ;;
    *)
        echo -e "${RED}Invalid phase: $PHASE${NC}"
        echo "Valid phases: 1, 2, 3, 4, all"
        exit 1
        ;;
esac

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo -e "${BLUE}======================================================================${NC}"
echo -e "${GREEN}✓ Download Complete!${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo "Time elapsed: ${MINUTES}m ${SECONDS}s"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Extract metadata and import to database:"
echo "   cd .."
echo "   python3 scripts/add_content_metadata.py"
echo ""
echo "2. Review content library:"
echo "   ls -lhR content/"
echo ""
echo "3. Start orchestrator to test smart scheduling:"
echo "   python3 -m src.main"
echo ""
