#!/bin/bash
# Download Khan Academy Programming Content
# License: CC BY-NC-SA
# Subject: Computer Programming

set -e

# Configuration
CONTENT_DIR_KIDS="../content/kids-after-school/khan-academy"
CONTENT_DIR_GENERAL="../content/general/khan-academy"
COURSE_NAME="Khan Academy Computer Programming"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Khan Academy Content Downloader ===${NC}"
echo -e "${BLUE}Course: ${COURSE_NAME}${NC}"
echo -e "${BLUE}License: CC BY-NC-SA${NC}\n"

# Check for yt-dlp
if ! command -v yt-dlp &> /dev/null; then
    echo -e "${RED}Error: yt-dlp is not installed${NC}"
    echo "Install with: pip install yt-dlp"
    echo "Or: sudo apt install yt-dlp (Debian/Ubuntu)"
    exit 1
fi

# Check disk space (require 10 GB minimum)
REQUIRED_SPACE_KB=$((10 * 1024 * 1024))  # 10 GB in KB
AVAILABLE_SPACE_KB=$(df --output=avail "$(dirname "$CONTENT_DIR_KIDS")" | tail -n 1)

if [ "$AVAILABLE_SPACE_KB" -lt "$REQUIRED_SPACE_KB" ]; then
    AVAILABLE_GB=$((AVAILABLE_SPACE_KB / 1024 / 1024))
    echo -e "${RED}Error: Insufficient disk space${NC}"
    echo -e "${RED}Required: 10 GB, Available: ${AVAILABLE_GB} GB${NC}"
    echo "Please free up disk space and try again."
    exit 1
fi

# Create content directories
mkdir -p "$CONTENT_DIR_KIDS"
mkdir -p "$CONTENT_DIR_GENERAL"

echo -e "${YELLOW}Note: Khan Academy videos are on YouTube but may require manual playlist identification.${NC}"
echo -e "${YELLOW}Visit: https://www.khanacademy.org/computing/computer-programming${NC}"
echo -e "${YELLOW}Find the YouTube playlist link for the specific course you want.${NC}\n"

# Example: Intro to JS (Drawing & Animation) - Good for kids
echo -e "${BLUE}Downloading Intro to JS: Drawing & Animation (Kid-friendly)...${NC}"
cd "$CONTENT_DIR_KIDS"

# Khan Academy Intro to JS playlist
JS_PLAYLIST="https://www.youtube.com/playlist?list=PLSQl0a2vh4HC5feHa6Rc5c0wbRTx56nF7"

yt-dlp \
    --format "bestvideo[height<=720]+bestaudio/best[height<=720]" \
    --output "%(playlist_index)02d-%(title)s.%(ext)s" \
    --write-description \
    --write-info-json \
    --add-metadata \
    --concurrent-fragments 4 \
    --throttled-rate 100K \
    --no-overwrites \
    --playlist-end 10 \
    "$JS_PLAYLIST" 2>/dev/null || echo -e "${RED}Playlist not found or restricted. Manual download required.${NC}"

echo -e "\n${GREEN}Downloads saved to:${NC}"
echo -e "${GREEN}- Kids content: ${CONTENT_DIR_KIDS}${NC}"
echo -e "${GREEN}- General content: ${CONTENT_DIR_GENERAL}${NC}"
echo -e "\n${BLUE}License Information:${NC}"
echo "These videos are licensed under CC BY-NC-SA"
echo "Attribution: Khan Academy"
echo "https://www.khanacademy.org/"
