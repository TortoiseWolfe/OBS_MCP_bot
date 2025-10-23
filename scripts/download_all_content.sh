#!/bin/bash
# Master script to download all educational content
# This script runs all individual download scripts in sequence

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Educational Content Download Manager${NC}"
echo -e "${BLUE}════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}This will download educational content from:${NC}"
echo -e "  1. MIT OpenCourseWare (Python CS course)"
echo -e "  2. Harvard CS50 (First 5 lectures)"
echo -e "  3. Khan Academy (Programming basics)"
echo -e "\n${YELLOW}Estimated total size: ~5-10 GB${NC}"
echo -e "${YELLOW}Estimated time: 1-3 hours (depending on connection)${NC}\n"

read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Download cancelled."
    exit 0
fi

echo -e "\n${BLUE}Starting downloads...${NC}\n"

# Track success/failure
FAILED_DOWNLOADS=()

# Download MIT OCW
echo -e "\n${GREEN}[1/3] Downloading MIT OpenCourseWare...${NC}"
if bash "$SCRIPT_DIR/download_mit_ocw.sh"; then
    echo -e "${GREEN}✓ MIT OCW download complete${NC}"
else
    echo -e "${RED}✗ MIT OCW download failed${NC}"
    FAILED_DOWNLOADS+=("MIT OCW")
fi

# Download Harvard CS50
echo -e "\n${GREEN}[2/3] Downloading Harvard CS50...${NC}"
if bash "$SCRIPT_DIR/download_cs50.sh"; then
    echo -e "${GREEN}✓ Harvard CS50 download complete${NC}"
else
    echo -e "${RED}✗ Harvard CS50 download failed${NC}"
    FAILED_DOWNLOADS+=("Harvard CS50")
fi

# Download Khan Academy
echo -e "\n${GREEN}[3/3] Downloading Khan Academy...${NC}"
if bash "$SCRIPT_DIR/download_khan_academy.sh"; then
    echo -e "${GREEN}✓ Khan Academy download complete${NC}"
else
    echo -e "${RED}✗ Khan Academy download failed${NC}"
    FAILED_DOWNLOADS+=("Khan Academy")
fi

# Summary
echo -e "\n${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Download Summary${NC}"
echo -e "${BLUE}════════════════════════════════════════════════${NC}"

if [ ${#FAILED_DOWNLOADS[@]} -eq 0 ]; then
    echo -e "${GREEN}All downloads completed successfully!${NC}"
else
    echo -e "${RED}Some downloads failed:${NC}"
    for item in "${FAILED_DOWNLOADS[@]}"; do
        echo -e "${RED}  - $item${NC}"
    done
fi

echo -e "\n${BLUE}Next steps:${NC}"
echo -e "  1. Review downloaded content in ../content/"
echo -e "  2. Update content metadata in database"
echo -e "  3. Configure OBS scenes for new content"
echo -e "  4. Test failover with expanded library"

echo -e "\n${BLUE}Content usage:${NC}"
echo -e "  - All content is licensed CC BY-NC-SA"
echo -e "  - Attribution required (see content/README.md)"
echo -e "  - Non-commercial use only"
echo -e "  - Educational streaming is compliant ✓"
