# Quickstart Guide: Content Library Management

**Feature**: 003-content-library-management
**Date**: 2025-10-22
**Phase**: 1 (Design & Contracts)

## Overview

This guide provides step-by-step instructions for setting up and using the content library management feature. Estimated time: 1 hour for initial setup + 1-3 hours for content downloads.

## Prerequisites

### Required Software

1. **Python 3.11+** (existing from Tier 1)
   ```bash
   python3 --version  # Should show 3.11 or higher
   ```

2. **yt-dlp** (video download tool)
   ```bash
   # Install via pip (recommended)
   pip install yt-dlp

   # Or via apt (Debian/Ubuntu)
   sudo apt install yt-dlp

   # Verify installation
   yt-dlp --version
   ```

3. **ffmpeg** (for ffprobe metadata extraction)
   ```bash
   # Install via apt
   sudo apt install ffmpeg

   # Verify installation
   ffprobe -version
   ```

4. **OBS Studio 29.0+** (existing from Tier 1)
   - Must be running on Windows host
   - WebSocket server enabled (Tools → WebSocket Server Settings)

5. **Docker & Docker Compose** (existing from Tier 1)
   ```bash
   docker --version
   docker-compose --version
   ```

### System Resources

- **Disk Space**: 15 GB minimum for initial content (50 GB for full courses)
- **RAM**: 8 GB minimum (existing requirement)
- **Network**: 10 Mbps upload minimum (existing requirement)
- **Download Time**: 1-3 hours for initial content library (20+ hours of video)

## Quick Start (5 Steps)

### Step 1: Verify Prerequisites (5 minutes)

```bash
# Navigate to project directory
cd /home/turtle_wolfe/repos/OBS_bot

# Activate virtual environment
source .venv/bin/activate

# Check Python version
python3 --version

# Install yt-dlp if not present
pip install yt-dlp

# Check ffprobe (from ffmpeg package)
ffprobe -version || sudo apt install ffmpeg

# Verify disk space (need at least 15 GB free)
df -h /home/turtle_wolfe/repos/OBS_bot
```

**Expected Output**:
- Python 3.11+
- yt-dlp installed successfully
- ffprobe from ffmpeg available
- At least 15 GB free disk space

---

### Step 2: Create Content Library Structure (2 minutes)

```bash
# Create time-block directories
mkdir -p content/kids-after-school
mkdir -p content/professional-hours
mkdir -p content/evening-mixed
mkdir -p content/general
# content/failover already exists with Big Buck Bunny

# Verify structure
ls -la content/

# Expected output:
# drwxr-xr-x kids-after-school/
# drwxr-xr-x professional-hours/
# drwxr-xr-x evening-mixed/
# drwxr-xr-x general/
# drwxr-xr-x failover/
```

---

### Step 3: Download Educational Content (1-3 hours)

**Option A: Download Everything (Recommended)**

```bash
cd scripts

# Run master download script
./download_all_content.sh

# This downloads:
# - MIT OCW 6.0001 (12 Python lectures, ~3-5 GB)
# - Harvard CS50 (5 sample lectures, ~2-3 GB)
# - Khan Academy (10 programming basics, ~1-2 GB)
# Total: ~25 videos, ~5-10 GB, 1-3 hours
```

**Option B: Download Selectively**

```bash
cd scripts

# Download only MIT OCW (~3-5 GB, 45-90 minutes)
./download_mit_ocw.sh

# Download only Harvard CS50 (~2-3 GB, 30-60 minutes)
./download_cs50.sh

# Download only Khan Academy (~1-2 GB, 15-30 minutes)
./download_khan_academy.sh
```

**Download Progress Indicators**:
- You'll see progress bars for each video
- Downloads are throttled to prevent ISP throttling
- Resume capability: if interrupted, re-run script (skips completed files)

---

### Step 4: Extract Content Metadata (2 minutes)

```bash
cd scripts

# Run metadata extraction
python3 add_content_metadata.py

# Expected output:
# Scanning content directory: /home/turtle_wolfe/repos/OBS_bot/content
#   Found: general/mit-ocw-6.0001/01-What_is_Computation.mp4
#   Found: general/harvard-cs50/00-Introduction.mp4
#   ... (25+ videos)
#
# ============================================================
# Content Library Summary
# ============================================================
# Total videos: 27
# Total duration: 24h 15m
# Total size: 8.45 GB
#
# By Source:
#   MIT OpenCourseWare: 12 videos
#   Harvard CS50: 5 videos
#   Khan Academy: 10 videos
#
# By Time Block:
#   general: 17 videos
#   kids_after_school: 10 videos
# ============================================================
#
# Exported 27 content items to scripts/content_metadata.json
```

**Verify Output**:
```bash
# Check metadata JSON was created
ls -lh scripts/content_metadata.json

# View first few entries
head -n 50 scripts/content_metadata.json
```

---

### Step 5: Verify OBS Can Access Content (5 minutes)

**Test Video Playback in OBS**:

1. **Open OBS Studio** (on Windows host)

2. **Add Media Source**:
   - Sources → Add → Media Source → Create new: "Test Content"
   - Click "Browse" button

3. **Navigate to WSL2 Content**:
   - In file browser, paste this path in address bar:
     ```
     \\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content\general\mit-ocw-6.0001
     ```
   - Select first video (e.g., `01-What_is_Computation.mp4`)
   - Click "OK"

4. **Verify Playback**:
   - Video should load and play in OBS preview
   - Audio should be audible
   - No lag or buffering (local file)

5. **Test Other Directories**:
   - Repeat for `kids-after-school/` and `failover/`
   - All directories should be accessible via WSL2 UNC path

**If Videos Don't Play**:
- Check path format: `\\wsl.localhost\Debian\...` (double backslash at start)
- Verify WSL2 is running: `wsl --list --running`
- Check file permissions: `ls -la content/` (should show readable files)
- See troubleshooting section below

---

## OBS Scene Setup

### Create Attribution Text Source

**Purpose**: Display content attribution overlay for CC license compliance.

**Steps**:

1. **Open OBS Studio**

2. **Add Text Source**:
   - Sources → Add → Text (GDI+) → Create new: "Content Attribution"
   - Click "OK"

3. **Configure Text Properties**:
   - **Text**: "MIT OpenCourseWare 6.0001: What is Computation? - CC BY-NC-SA 4.0"
   - **Font**: Arial, Size 24, Bold
   - **Color**: White (RGB 255, 255, 255)
   - **Background Color**: Black (RGB 0, 0, 0), Opacity 180
   - **Alignment**: Bottom-left
   - Click "OK"

4. **Position Text Source**:
   - Drag text source to bottom-left corner of canvas
   - Resize if needed (should fit in ~1/4 of screen width)
   - Ensure text is readable but not intrusive

5. **Lock Text Source** (optional):
   - Right-click "Content Attribution" → Lock
   - Prevents accidental movement

6. **Verify Name**:
   - Source MUST be named exactly "Content Attribution" (case-sensitive)
   - Orchestrator will update this text source automatically during playback

**Apply to All Scenes**:
- Copy "Content Attribution" source to all scenes where content plays
- Or use Scene Collection templates

---

## Configuration Updates

### Update settings.yaml

The configuration should already be updated from earlier setup. Verify it contains:

```yaml
content:
  library_path: "/app/content"
  windows_content_path: "//wsl.localhost/Debian/home/turtle_wolfe/repos/OBS_bot/content"

  time_block_paths:
    kids_after_school: "/app/content/kids-after-school"
    professional_hours: "/app/content/professional-hours"
    evening_mixed: "/app/content/evening-mixed"
    general: "/app/content/general"
    failover: "/app/content/failover"

  sources:
    - name: "MIT OpenCourseWare 6.0001"
      path: "/app/content/general/mit-ocw-6.0001"
      license: "CC BY-NC-SA 4.0"
      attribution: "MIT OpenCourseWare"
    - name: "Harvard CS50"
      path: "/app/content/general/harvard-cs50"
      license: "CC BY-NC-SA 4.0"
      attribution: "Harvard University CS50"
    - name: "Khan Academy Programming"
      path: "/app/content/kids-after-school/khan-academy"
      license: "CC BY-NC-SA"
      attribution: "Khan Academy"

  attribution:
    text_source_name: "Content Attribution"
    update_timeout_sec: 1
    verify_on_startup: true
```

---

## Testing the Integration

### Test 1: Manual Content Playback

```bash
# 1. Start OBS Studio (Windows host)
# 2. Add media source pointing to content file via WSL2 path
# 3. Verify video plays correctly
```

**Expected**: Video loads and plays without errors.

### Test 2: Attribution Text Update (Manual)

```bash
# 1. Open OBS Studio
# 2. Manually edit "Content Attribution" text source
# 3. Change text to different content attribution
# 4. Verify text updates in OBS preview
```

**Expected**: Text updates immediately when edited.

### Test 3: Docker Volume Mount

```bash
# Build and start orchestrator container
docker-compose -f docker-compose.prod.yml up -d obs-orchestrator

# Verify content mount
docker exec obs_bot_orchestrator ls -la /app/content/

# Expected output:
# drwxr-xr-x kids-after-school/
# drwxr-xr-x professional-hours/
# drwxr-xr-x evening-mixed/
# drwxr-xr-x general/
# drwxr-xr-x failover/

# Check logs for any mount errors
docker-compose -f docker-compose.prod.yml logs obs-orchestrator
```

**Expected**: Container can read content directory, no permission errors.

---

## Troubleshooting

### Problem: yt-dlp Not Found

**Symptoms**: `bash: yt-dlp: command not found`

**Solutions**:
```bash
# Activate virtual environment first
source .venv/bin/activate

# Install yt-dlp
pip install yt-dlp

# Verify
yt-dlp --version
```

---

### Problem: OBS Can't Access WSL2 Files

**Symptoms**: "File not found" or empty preview in OBS

**Solutions**:

1. **Check WSL2 is Running**:
   ```bash
   wsl --list --running
   # Should show "Debian" or your distro name
   ```

2. **Try Alternative Path Format**:
   - Try: `\\wsl$\Debian\home\...` (older format)
   - Try: `\\wsl.localhost\Debian\home\...` (newer format)

3. **Check File Permissions**:
   ```bash
   # In WSL2
   chmod 644 content/**/*.mp4
   chmod 755 content/*/
   ```

4. **Verify File Exists**:
   ```bash
   ls -la content/general/mit-ocw-6.0001/
   ```

---

### Problem: Downloads Failing

**Symptoms**: "ERROR: unable to download video"

**Solutions**:

1. **Update yt-dlp**:
   ```bash
   pip install -U yt-dlp
   ```

2. **Test Single Video**:
   ```bash
   yt-dlp "https://www.youtube.com/watch?v=nykOeWgQcHM"
   ```

3. **Check Network**:
   ```bash
   ping youtube.com
   ```

4. **Try Alternative Source**:
   - MIT OCW: Download from ocw.mit.edu directly
   - CS50: Download from cs50.harvard.edu
   - Internet Archive: archive.org has mirrors

---

### Problem: Insufficient Disk Space

**Symptoms**: "No space left on device"

**Solutions**:

1. **Check Available Space**:
   ```bash
   df -h /home/turtle_wolfe/repos/OBS_bot
   ```

2. **Selective Downloads**:
   - Edit download scripts
   - Add `--playlist-end 5` to limit downloads
   - Example: Only download first 5 lectures instead of all

3. **Clean Up**:
   ```bash
   # Remove partial downloads
   find content/ -name "*.part" -delete
   ```

---

### Problem: ffprobe Not Found

**Symptoms**: "ffprobe: command not found" during metadata extraction

**Solutions**:
```bash
# Install ffmpeg package (includes ffprobe)
sudo apt update
sudo apt install ffmpeg

# Verify
ffprobe -version
```

---

### Problem: Docker Container Can't Read Content

**Symptoms**: Permission errors in Docker logs

**Solutions**:

1. **Check Volume Mount in docker-compose.prod.yml**:
   ```yaml
   volumes:
     - ./content:/app/content:ro  # :ro = read-only
   ```

2. **Verify Host Permissions**:
   ```bash
   chmod 755 content/
   chmod 755 content/*/
   chmod 644 content/**/*.mp4
   ```

3. **Check Docker Logs**:
   ```bash
   docker-compose -f docker-compose.prod.yml logs obs-orchestrator
   ```

---

## Next Steps

After completing this quickstart:

1. **Run `/speckit.tasks`** to generate implementation task list
2. **Begin implementation** with Phase 1 tasks (database schema, models)
3. **Test incrementally** after each component
4. **Integrate with Tier 1** orchestrator for automated content selection
5. **Deploy to production** after all tests pass

---

## Additional Resources

- **Architecture**: See `docs/CONTENT_ARCHITECTURE.md` for detailed system architecture
- **License Info**: See `content/README.md` for full license attribution
- **Setup Details**: See `scripts/SETUP.md` for advanced setup options
- **Data Model**: See `data-model.md` for database schema
- **Service Contracts**: See `contracts/service-contracts.md` for API interfaces

---

**Quickstart Complete**: Content library setup verified, OBS integration tested, ready for implementation phase.
