#!/bin/bash
# Download Harvard CS50 Content
# License: CC BY-NC-SA 4.0
# Course: CS50's Introduction to Computer Science

set -e

# Configuration
CONTENT_DIR="../content/general/harvard-cs50"
COURSE_NAME="Harvard CS50 - Introduction to Computer Science"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Harvard CS50 Content Downloader ===${NC}"
echo -e "${BLUE}Course: ${COURSE_NAME}${NC}"
echo -e "${BLUE}License: CC BY-NC-SA 4.0${NC}\n"

# Check for yt-dlp
if ! command -v yt-dlp &> /dev/null; then
    echo -e "${RED}Error: yt-dlp is not installed${NC}"
    echo "Install with: pip install yt-dlp"
    echo "Or: sudo apt install yt-dlp (Debian/Ubuntu)"
    exit 1
fi

# Check disk space (require 10 GB minimum)
REQUIRED_SPACE_KB=$((10 * 1024 * 1024))  # 10 GB in KB
AVAILABLE_SPACE_KB=$(df --output=avail "$(dirname "$CONTENT_DIR")" | tail -n 1)

if [ "$AVAILABLE_SPACE_KB" -lt "$REQUIRED_SPACE_KB" ]; then
    AVAILABLE_GB=$((AVAILABLE_SPACE_KB / 1024 / 1024))
    echo -e "${RED}Error: Insufficient disk space${NC}"
    echo -e "${RED}Required: 10 GB, Available: ${AVAILABLE_GB} GB${NC}"
    echo "Please free up disk space and try again."
    exit 1
fi

# Create content directory
mkdir -p "$CONTENT_DIR"
cd "$CONTENT_DIR"

echo -e "${GREEN}Downloading to: $(pwd)${NC}\n"

# CS50 2023 YouTube Playlist (Official)
# These videos are officially hosted by Harvard's CS50 on YouTube
PLAYLIST_URL="https://www.youtube.com/playlist?list=PLhQjrBD2T3817j24-GogXmWqO5Q5vYy0V"

echo -e "${BLUE}Downloading CS50 2023 lecture videos...${NC}"
yt-dlp \
    --format "bestvideo[height<=720]+bestaudio/best[height<=720]" \
    --output "%(playlist_index)02d-%(title)s.%(ext)s" \
    --write-description \
    --write-info-json \
    --write-thumbnail \
    --add-metadata \
    --embed-thumbnail \
    --embed-subs \
    --sub-langs "en" \
    --concurrent-fragments 4 \
    --throttled-rate 100K \
    --no-overwrites \
    --playlist-end 5 \
    "$PLAYLIST_URL"

echo -e "\n${GREEN}Download complete!${NC}"
echo -e "${GREEN}Videos saved to: ${CONTENT_DIR}${NC}"
echo -e "\n${BLUE}Note: This script downloads first 5 lectures as a sample.${NC}"
echo -e "${BLUE}Remove --playlist-end 5 to download all lectures.${NC}"
echo -e "\n${BLUE}License Information:${NC}"
echo "These videos are licensed under CC BY-NC-SA 4.0"
echo "Attribution: Harvard University CS50"
echo "https://cs50.harvard.edu/"
