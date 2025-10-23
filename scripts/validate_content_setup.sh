#!/bin/bash
# Content Library Setup Validation Script (T068)
# Verifies all steps from quickstart.md work correctly
#
# Exit codes:
#   0 = All checks passed
#   1 = One or more checks failed

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track failures
FAILURES=0
CHECKS_PASSED=0
CHECKS_TOTAL=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    echo -e "${YELLOW}  Fix: $2${NC}"
    FAILURES=$((FAILURES + 1))
}

run_check() {
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
}

echo -e "${BLUE}=== Content Library Setup Validation ===${NC}"
echo ""

# ===== Check 1: Prerequisites =====
echo -e "${BLUE}[1/8] Checking Prerequisites...${NC}"

run_check
if command -v yt-dlp &> /dev/null; then
    check_pass "yt-dlp installed ($(yt-dlp --version))"
else
    check_fail "yt-dlp not found" "pip install yt-dlp"
fi

run_check
if command -v ffprobe &> /dev/null; then
    check_pass "ffprobe installed ($(ffprobe -version | head -1))"
else
    check_fail "ffprobe not found" "sudo apt install ffmpeg"
fi

run_check
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    check_pass "Python 3 installed ($PYTHON_VERSION)"
else
    check_fail "Python 3 not found" "Install Python 3.11+"
fi

run_check
if command -v docker &> /dev/null; then
    check_pass "Docker installed ($(docker --version | cut -d' ' -f3 | tr -d ','))"
else
    check_fail "Docker not found" "Install Docker"
fi

echo ""

# ===== Check 2: Directory Structure =====
echo -e "${BLUE}[2/8] Checking Directory Structure...${NC}"

REQUIRED_DIRS=(
    "content"
    "content/general"
    "content/kids-after-school"
    "content/professional-hours"
    "content/evening-mixed"
    "content/failover"
    "data"
    "logs"
    "config"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    run_check
    if [ -d "$dir" ]; then
        check_pass "Directory exists: $dir"
    else
        check_fail "Directory missing: $dir" "mkdir -p $dir"
    fi
done

echo ""

# ===== Check 3: Permissions =====
echo -e "${BLUE}[3/8] Checking Permissions...${NC}"

run_check
if [ -w "content" ]; then
    check_pass "content/ is writable"
else
    check_fail "content/ not writable" "chmod 755 content/"
fi

run_check
if [ -w "data" ]; then
    check_pass "data/ is writable"
else
    check_fail "data/ not writable" "chmod 777 data/"
fi

run_check
if [ -w "logs" ]; then
    check_pass "logs/ is writable"
else
    check_fail "logs/ not writable" "chmod 777 logs/"
fi

echo ""

# ===== Check 4: Content Files =====
echo -e "${BLUE}[4/8] Checking Content Files...${NC}"

run_check
VIDEO_COUNT=$(find content -name "*.mp4" 2>/dev/null | wc -l)
if [ "$VIDEO_COUNT" -gt 0 ]; then
    check_pass "Found $VIDEO_COUNT video files"
else
    check_fail "No video files found" "Run download scripts: cd scripts && ./download_all_content.sh"
fi

run_check
if [ -f "content/failover/default_failover.mp4" ]; then
    check_pass "Failover content exists"
else
    check_fail "Failover content missing" "Download Big Buck Bunny to content/failover/"
fi

echo ""

# ===== Check 5: Database =====
echo -e "${BLUE}[5/8] Checking Database...${NC}"

run_check
if [ -f "data/obs_bot.db" ]; then
    check_pass "Database file exists"

    # Check if database has content_sources table
    run_check
    if sqlite3 data/obs_bot.db "SELECT name FROM sqlite_master WHERE type='table' AND name='content_sources';" | grep -q content_sources; then
        check_pass "content_sources table exists"

        # Check if table has data
        run_check
        ROW_COUNT=$(sqlite3 data/obs_bot.db "SELECT COUNT(*) FROM content_sources;" 2>/dev/null || echo "0")
        if [ "$ROW_COUNT" -gt 0 ]; then
            check_pass "Database has $ROW_COUNT videos"
        else
            check_fail "No videos in database" "Run: python3 scripts/add_content_metadata.py"
        fi
    else
        check_fail "content_sources table missing" "Run database migrations"
    fi
else
    check_fail "Database not found" "Initialize database: docker compose -f docker-compose.prod.yml up -d"
fi

echo ""

# ===== Check 6: Configuration =====
echo -e "${BLUE}[6/8] Checking Configuration...${NC}"

run_check
if [ -f "config/settings.yaml" ]; then
    check_pass "Configuration file exists"

    # Check for critical settings
    run_check
    if grep -q "windows_content_path" config/settings.yaml; then
        check_pass "windows_content_path configured"
    else
        check_fail "windows_content_path not found" "Add to config/settings.yaml"
    fi

    run_check
    if grep -q "time_block_paths" config/settings.yaml; then
        check_pass "time_block_paths configured"
    else
        check_fail "time_block_paths not found" "Add to config/settings.yaml"
    fi
else
    check_fail "config/settings.yaml not found" "Copy from config/settings.example.yaml"
fi

echo ""

# ===== Check 7: WSL2 Path Accessibility =====
echo -e "${BLUE}[7/8] Checking WSL2 Path (if on Windows)...${NC}"

run_check
if grep -qi microsoft /proc/version 2>/dev/null; then
    check_pass "Running on WSL2"

    # Try to resolve Windows UNC path
    run_check
    WSL_DISTRO=$(wsl.exe -l -v 2>/dev/null | grep -o "Debian\|Ubuntu" | head -1 || echo "Unknown")
    if [ "$WSL_DISTRO" != "Unknown" ]; then
        check_pass "WSL distribution detected: $WSL_DISTRO"
    else
        check_fail "Could not detect WSL distribution" "Check wsl -l -v on Windows"
    fi
else
    check_pass "Not on WSL2 (skipping Windows path checks)"
fi

echo ""

# ===== Check 8: Docker Compose =====
echo -e "${BLUE}[8/8] Checking Docker Compose Configuration...${NC}"

run_check
if [ -f "docker-compose.prod.yml" ]; then
    check_pass "docker-compose.prod.yml exists"

    # Check volume mounts
    run_check
    if grep -q "./content:/app/content" docker-compose.prod.yml; then
        check_pass "Content volume mount configured"
    else
        check_fail "Content volume mount missing" "Add to docker-compose.prod.yml"
    fi

    run_check
    if grep -q "./data:/app/data" docker-compose.prod.yml; then
        check_pass "Data volume mount configured"
    else
        check_fail "Data volume mount missing" "Add to docker-compose.prod.yml"
    fi
else
    check_fail "docker-compose.prod.yml not found" "Create Docker Compose configuration"
fi

echo ""

# ===== Summary =====
echo -e "${BLUE}=== Validation Summary ===${NC}"
echo ""
echo "Checks Passed: $CHECKS_PASSED / $CHECKS_TOTAL"
echo ""

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Content library setup is valid.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start orchestrator: docker compose -f docker-compose.prod.yml up -d"
    echo "  2. Check health API: curl http://localhost:8000/health/content-library | jq"
    echo "  3. Monitor logs: docker compose -f docker-compose.prod.yml logs -f obs-orchestrator"
    exit 0
else
    echo -e "${RED}❌ $FAILURES check(s) failed${NC}"
    echo ""
    echo "Review the failures above and apply the suggested fixes."
    exit 1
fi
