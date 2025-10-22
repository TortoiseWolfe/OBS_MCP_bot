# Content Library Troubleshooting Guide

This guide addresses common issues when downloading, managing, and streaming educational content with the OBS_bot content library system.

## Table of Contents

- [Download Issues](#download-issues)
- [OBS Playback Issues](#obs-playback-issues)
- [Docker & Volume Mounts](#docker--volume-mounts)
- [Disk Space Management](#disk-space-management)
- [Video Format Compatibility](#video-format-compatibility)
- [Permission Errors](#permission-errors)
- [Database & Metadata Issues](#database--metadata-issues)
- [Attribution Display Issues](#attribution-display-issues)
- [Performance Issues](#performance-issues)

---

## Download Issues

### `yt-dlp: command not found`

**Problem**: Download scripts fail because `yt-dlp` is not installed.

**Solution**:

```bash
# Option 1: Install via pip (recommended)
pip install yt-dlp

# Option 2: Install via apt (Debian/Ubuntu)
sudo apt update
sudo apt install yt-dlp

# Option 3: Install via pipx (isolated environment)
pipx install yt-dlp

# Verify installation
yt-dlp --version
```

**Verification**: Run `yt-dlp --version` and confirm output shows version number.

---

### HTTP 403 / 429 Errors from YouTube

**Problem**: `yt-dlp` fails with HTTP 403 (Forbidden) or HTTP 429 (Too Many Requests) errors.

**Error Message**:
```
ERROR: unable to download video data: HTTP Error 403: Forbidden
WARNING: [youtube] Sign in to confirm you're not a bot
ERROR: Postprocessing: PO token required
```

**Solution**: Use direct CDN downloads instead of YouTube:

**MIT OCW**:
```bash
# Visit archive.org mirror
https://archive.org/download/MIT6.0001F16/

# Download manually or use wget
wget -r -np -R "index.html*" https://archive.org/download/MIT6.0001F16/
```

**Harvard CS50**:
```bash
# Use CS50 CDN
https://cdn.cs50.net/2023/fall/lectures/

# Download individual lectures
wget https://cdn.cs50.net/2023/fall/lectures/0/lecture0.mp4
```

**Khan Academy**:
- Download directly from Khan Academy website
- Or check if videos are available on archive.org

**Why**: YouTube has anti-bot protections that block automated downloaders. Direct CDN sources are more reliable.

---

### Download Speed Too Slow

**Problem**: Downloads take hours or consume too much bandwidth.

**Solution 1: Rate Limiting** (already implemented in scripts):
```bash
# In download scripts, this flag limits speed:
--throttled-rate 100K  # Limits to 100 KB/s
```

**Solution 2: Selective Downloads**:
```bash
# Edit download script to download only first N videos
--playlist-items 1-5  # Download only first 5 videos
```

**Solution 3: Parallel Downloads** (for CDN sources):
```bash
# Use wget with multiple concurrent connections
wget -c -t 0 --retry-connrefused --waitretry=1 -T 10 -O file.mp4 URL
```

---

### Resume Interrupted Downloads

**Problem**: Download interrupted by network issue or system shutdown.

**Solution**: Scripts already include `--no-overwrites` flag for yt-dlp:

```bash
# Re-run the same download script
cd /home/turtle_wolfe/repos/OBS_bot/scripts
./download_mit_ocw.sh

# yt-dlp will skip already-downloaded files
```

**Verify**: Check `content/general/` directory for existing `.mp4` files before re-running.

---

### Insufficient Disk Space During Download

**Problem**: Download fails with "No space left on device" error.

**Solution**:

```bash
# Check available space
df -h /home/turtle_wolfe/repos/OBS_bot/

# If low on space, delete unnecessary files
# Or download fewer videos (edit script --playlist-items)

# Download scripts check for 10 GB minimum
# MIT OCW: ~3-5 GB
# CS50 (5 lectures): ~2-3 GB
# Khan Academy: ~1-2 GB
```

**Minimum Requirements**:
- **For basic library**: 10 GB free
- **For full library**: 20+ GB free

---

## OBS Playback Issues

### "OBS Can't Find Video File"

**Problem**: OBS media source shows "File not found" error.

**Symptoms**:
- Red "X" on media source in OBS
- "No file selected" error
- Video doesn't play when scheduled

**Root Cause**: Path mismatch between Docker metadata and OBS Windows path.

**Solution**:

1. **Verify Windows UNC Path**:
   ```
   \\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content\failover\default_failover.mp4
   ```

2. **Test Path in OBS**:
   - Sources → Add Media Source
   - Browse to: `\\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content\`
   - If browse works, path is accessible

3. **Check `config/settings.yaml`**:
   ```yaml
   content:
     windows_content_path: "//wsl.localhost/Debian/home/turtle_wolfe/repos/OBS_bot/content"
   ```

4. **Verify WSL Distribution Name**:
   ```bash
   # On Windows PowerShell
   wsl -l -v

   # Output should show "Debian" or your distro name
   # Use that name in UNC path
   ```

**Common Mistakes**:
- ❌ Using `/app/content` (Docker path) in OBS → **Wrong**
- ❌ Using `/home/turtle_wolfe/repos/OBS_bot/content` (WSL path) in OBS → **Wrong**
- ✅ Using `\\wsl.localhost\Debian\home\...` (UNC path) in OBS → **Correct**

---

### Video Plays But Has Wrong Aspect Ratio

**Problem**: Video is stretched, squished, or has black bars.

**Solution**: Dynamic video scaling should handle this automatically.

**Verify Scaling**:
```bash
# Check database for video resolutions
docker compose -f docker-compose.prod.yml exec obs-orchestrator \
  sqlite3 /app/data/obs_bot.db \
  "SELECT title, width, height FROM content_sources LIMIT 5;"
```

**Expected Behavior**:
- Canvas: 1920x1080
- MIT OCW 480x360 → Scaled 3.0x to 1440x1080 (preserves aspect ratio)
- CS50 1280x720 → Scaled 1.5x to 1920x1080 (preserves aspect ratio)

**If Still Wrong**:
1. Check OBS canvas resolution: Settings → Video → Base (Canvas) Resolution
2. Verify `OBSController.calculate_video_transform()` is being called (src/services/obs_controller.py:681-751)
3. Check logs for scaling calculations

---

### Video Plays But No Attribution Overlay

**Problem**: Video plays correctly but no attribution text visible.

**Solution**: See [Attribution Display Issues](#attribution-display-issues) section.

---

## Docker & Volume Mounts

### "Docker Can't See Content Files"

**Problem**: Docker container can't find videos in `/app/content/`.

**Symptoms**:
```bash
docker compose -f docker-compose.prod.yml exec obs-orchestrator ls /app/content/
# Output: empty or "No such file or directory"
```

**Solution**:

1. **Verify Volume Mount in `docker-compose.prod.yml`**:
   ```yaml
   volumes:
     - ./content:/app/content:rw  # Read-write for ongoing content management
   ```

2. **Check Files Exist on Host**:
   ```bash
   ls -la /home/turtle_wolfe/repos/OBS_bot/content/
   # Should show: general/, kids-after-school/, failover/, etc.
   ```

3. **Restart Container**:
   ```bash
   docker compose -f docker-compose.prod.yml down
   docker compose -f docker-compose.prod.yml up -d obs-orchestrator
   ```

4. **Verify Mount Inside Container**:
   ```bash
   docker compose -f docker-compose.prod.yml exec obs-orchestrator ls -la /app/content/
   # Should show same directories as host
   ```

---

### "Permission Denied" in Docker Container

**Problem**: Docker container can read content files but can't write to data/logs directories.

**Solution**:

```bash
# On WSL2 host, ensure directories have correct permissions
cd /home/turtle_wolfe/repos/OBS_bot

# Make content readable
chmod -R 755 content/

# Make data and logs writable
chmod -R 777 data/ logs/

# Verify
ls -ld content/ data/ logs/
```

**Docker User**: Container runs as root by default, so permissions should be permissive.

---

### Container Won't Start After Rebuild

**Problem**: `docker compose up` fails after rebuilding image.

**Solution**:

```bash
# Remove old containers and volumes
docker compose -f docker-compose.prod.yml down -v

# Rebuild image
docker compose -f docker-compose.prod.yml build --no-cache

# Start fresh
docker compose -f docker-compose.prod.yml up -d obs-orchestrator

# Check logs
docker compose -f docker-compose.prod.yml logs -f obs-orchestrator
```

---

## Disk Space Management

### "Out of Disk Space" Error

**Problem**: System runs out of disk space after downloading content.

**Check Current Usage**:
```bash
# Total usage
du -sh /home/turtle_wolfe/repos/OBS_bot/content/

# Breakdown by time block
du -sh /home/turtle_wolfe/repos/OBS_bot/content/*/

# Available space
df -h /home/turtle_wolfe/repos/OBS_bot/
```

**Solution 1: Remove Unnecessary Content**:
```bash
# Remove specific course
rm -rf /home/turtle_wolfe/repos/OBS_bot/content/general/mit-ocw-6.0001/

# Update database after removing files
cd /home/turtle_wolfe/repos/OBS_bot
python3 scripts/add_content_metadata.py
```

**Solution 2: Download Fewer Videos**:
```bash
# Edit download scripts to limit playlist items
# In download_mit_ocw.sh, change:
--playlist-items 1-12  # to:
--playlist-items 1-5   # Only download 5 lectures
```

**Solution 3: Use External Storage**:
```bash
# Mount external drive to /mnt/content
# Update docker-compose.prod.yml:
volumes:
  - /mnt/content:/app/content:rw
```

**Expected Sizes**:
- MIT OCW (12 lectures): ~3-5 GB
- CS50 (5 lectures): ~2-3 GB
- Khan Academy (sample): ~1-2 GB
- **Total for basic library**: 5-10 GB
- **Total for full library**: 20+ GB

---

## Video Format Compatibility

### "OBS Won't Play Video Format"

**Problem**: Video downloads successfully but OBS can't play it.

**Supported Formats**:
- ✅ MP4 (H.264 video, AAC audio) - **Recommended**
- ✅ MKV (with H.264 video)
- ⚠️ WebM (may require transcoding)
- ❌ FLV, AVI (not recommended)

**Check Video Format**:
```bash
ffprobe /path/to/video.mp4 2>&1 | grep -E "Video:|Audio:"
```

**Solution: Re-encode to MP4**:
```bash
# Install ffmpeg
sudo apt install ffmpeg

# Re-encode video to H.264/AAC MP4
ffmpeg -i input.mkv -c:v libx264 -c:a aac -preset fast output.mp4

# Batch re-encode all videos in directory
for f in *.mkv; do
  ffmpeg -i "$f" -c:v libx264 -c:a aac -preset fast "${f%.mkv}.mp4"
done
```

**Download Scripts Already Use Optimal Format**:
```bash
# In download_mit_ocw.sh
--format "bestvideo[height<=720]+bestaudio/best[height<=720]" \
--merge-output-format mp4  # Ensures MP4 output
```

---

### "Video Has No Audio" in OBS

**Problem**: Video plays but no sound.

**Check Audio Codec**:
```bash
ffprobe video.mp4 2>&1 | grep Audio
# Should show: Audio: aac
```

**Solution: Add Audio Track**:
```bash
# Re-encode with audio
ffmpeg -i video.mp4 -c:v copy -c:a aac output.mp4
```

**Check OBS Audio Settings**:
- Right-click media source → Properties
- Verify "Close file when inactive" is **unchecked**
- Check audio track is not muted in OBS mixer

---

## Permission Errors

### "Cannot Write to content/ Directory"

**Problem**: Download scripts fail with "Permission denied" when writing files.

**Solution**:
```bash
# Check current permissions
ls -ld /home/turtle_wolfe/repos/OBS_bot/content/

# Make writable
chmod 755 /home/turtle_wolfe/repos/OBS_bot/content/

# Verify
ls -ld /home/turtle_wolfe/repos/OBS_bot/content/
# Should show: drwxr-xr-x (755)
```

---

### "Cannot Execute Download Script"

**Problem**: `./download_mit_ocw.sh` fails with "Permission denied".

**Solution**:
```bash
# Make script executable
chmod +x /home/turtle_wolfe/repos/OBS_bot/scripts/*.sh

# Verify
ls -l /home/turtle_wolfe/repos/OBS_bot/scripts/*.sh
# Should show: -rwxr-xr-x
```

---

## Database & Metadata Issues

### "No Videos in Database After Download"

**Problem**: Videos downloaded but metadata extraction didn't run or failed.

**Solution**:

1. **Check Files Exist**:
   ```bash
   find /home/turtle_wolfe/repos/OBS_bot/content -name "*.mp4" | wc -l
   # Should show count of downloaded videos
   ```

2. **Run Metadata Extraction Manually**:
   ```bash
   cd /home/turtle_wolfe/repos/OBS_bot
   python3 scripts/add_content_metadata.py
   ```

3. **Check Database**:
   ```bash
   sqlite3 data/obs_bot.db "SELECT COUNT(*) FROM content_sources;"
   # Should match video count
   ```

4. **Check for Errors**:
   ```bash
   # Look for ffprobe errors in script output
   python3 scripts/add_content_metadata.py 2>&1 | grep -i error
   ```

---

### "ffprobe: command not found" During Metadata Extraction

**Problem**: Metadata script fails because `ffprobe` is not installed.

**Solution**:
```bash
# Install ffmpeg (includes ffprobe)
sudo apt update
sudo apt install ffmpeg

# Verify
ffprobe -version
```

**Re-run Metadata Extraction**:
```bash
python3 scripts/add_content_metadata.py
```

---

### "Database Locked" Error

**Problem**: Multiple processes trying to write to SQLite database simultaneously.

**Solution**:

```bash
# Stop all services
docker compose -f docker-compose.prod.yml down

# Remove lock file
rm -f /home/turtle_wolfe/repos/OBS_bot/data/obs_bot.db-shm
rm -f /home/turtle_wolfe/repos/OBS_bot/data/obs_bot.db-wal

# Restart services
docker compose -f docker-compose.prod.yml up -d obs-orchestrator
```

**Prevention**: Only run metadata extraction scripts when orchestrator is stopped.

---

### "Duplicate Videos in Database"

**Problem**: Same video appears multiple times in database.

**Solution**:

```bash
# Check for duplicates
sqlite3 data/obs_bot.db "SELECT file_path, COUNT(*) FROM content_sources GROUP BY file_path HAVING COUNT(*) > 1;"

# Remove duplicates manually
sqlite3 data/obs_bot.db
DELETE FROM content_sources WHERE source_id IN (
  SELECT source_id FROM (
    SELECT source_id, ROW_NUMBER() OVER (PARTITION BY file_path ORDER BY created_at) AS rn
    FROM content_sources
  ) WHERE rn > 1
);
.quit

# Verify
sqlite3 data/obs_bot.db "SELECT COUNT(*) FROM content_sources;"
```

---

## Attribution Display Issues

### "Attribution Overlay Not Showing"

**Problem**: Video plays but attribution text doesn't appear on stream.

**Solution**:

1. **Check Text Source Exists in OBS**:
   - Sources → Check for "Content Attribution" text source
   - If missing, create manually or use `OBSAttributionUpdater.ensure_text_source()`

2. **Verify Text Source is Visible**:
   - Right-click text source → Properties
   - Check text is not blank
   - Verify font size is large enough (recommended: 24-32pt)
   - Check color contrasts with background (white on dark overlay)

3. **Check Scene Configuration**:
   - Text source must be in "Automated Content" scene
   - Text source must be above video source in layer order
   - Text source must be visible (eye icon enabled)

4. **Manual Test**:
   ```bash
   # Update attribution manually
   docker compose -f docker-compose.prod.yml exec obs-orchestrator python3 -c "
   from src.services.obs_attribution_updater import OBSAttributionUpdater
   from src.config.settings import Settings
   import asyncio

   async def test():
       settings = Settings()
       updater = OBSAttributionUpdater(settings.obs)
       await updater.update_attribution(
           source_name='MIT OCW 6.0001',
           title='What is Computation?',
           license_type='CC BY-NC-SA 4.0'
       )

   asyncio.run(test())
   "
   ```

5. **Check OBS WebSocket Connection**:
   ```bash
   # Verify orchestrator can connect to OBS
   docker compose -f docker-compose.prod.yml logs obs-orchestrator | grep -i "obs"
   # Should show: "Connected to OBS WebSocket"
   ```

---

### "Attribution Text is Cut Off"

**Problem**: Attribution text is too long and gets truncated.

**Solution**:

1. **Increase Text Source Width**:
   - Right-click text source → Transform → Edit Transform
   - Set width to 1800+ pixels

2. **Enable Text Wrapping** (if supported by OBS text source)

3. **Shorten Attribution Format**:
   - Edit `OBSAttributionUpdater._format_attribution()` (src/services/obs_attribution_updater.py)
   - Use abbreviations: "CC BY-NC-SA 4.0" → "CC-NC-SA"

---

### "Attribution Update Takes >1 Second"

**Problem**: Attribution updates are slow (violates SC-013 requirement).

**Benchmark**:
```bash
# Time attribution update
time docker compose -f docker-compose.prod.yml exec obs-orchestrator python3 -c "..."
# Should complete in <1 second
```

**Possible Causes**:
- Slow network to OBS WebSocket (check localhost:4455 latency)
- OBS overloaded (too many sources/scenes)
- Text source recreation instead of update

**Solution**:
- Use `update_text_source()` instead of recreating text source
- Reduce OBS scene complexity
- Check OBS is running on host network (not Docker bridge)

---

## Performance Issues

### "Video Playback is Choppy"

**Problem**: Video stutters or drops frames during playback.

**Possible Causes**:
1. Insufficient CPU for encoding
2. Slow disk I/O (especially if using network storage)
3. OBS canvas resolution mismatch
4. Docker resource limits

**Solution**:

1. **Check OBS Performance**:
   - OBS → View → Stats
   - Look for: "Dropped Frames", "Rendering Lag", "Encoding Lag"

2. **Verify Video is on Local Disk**:
   ```bash
   # Content should be on local WSL2 filesystem
   ls /home/turtle_wolfe/repos/OBS_bot/content/
   # NOT on network mount like /mnt/c/ or SMB share
   ```

3. **Lower OBS Output Resolution**:
   - Settings → Output → Video Bitrate → Lower to 2500 kbps
   - Settings → Video → Output (Scaled) Resolution → 1280x720

4. **Check Docker CPU Limits**:
   ```bash
   # Remove CPU limits in docker-compose.prod.yml
   # Or increase:
   cpus: '2.0'  # Allow 2 CPU cores
   ```

---

### "Content Library Scan is Slow"

**Problem**: `scripts/add_content_metadata.py` takes >2 minutes to scan library.

**Expected Performance** (SC-003): 25 videos scanned in <2 minutes.

**Benchmark**:
```bash
time python3 scripts/add_content_metadata.py
```

**Solution**:

1. **Skip Redundant Scans**:
   - Only run metadata extraction when adding new content
   - Use `--incremental` flag if implemented

2. **Optimize ffprobe Calls**:
   - Reduce number of metadata fields extracted
   - Cache results for previously scanned files

---

## Getting Help

If issues persist after trying these solutions:

1. **Check Logs**:
   ```bash
   # Docker orchestrator logs
   docker compose -f docker-compose.prod.yml logs -f obs-orchestrator

   # OBS logs
   # On Windows: %APPDATA%\obs-studio\logs\
   ```

2. **Verify System Requirements**:
   - Python 3.11+
   - Docker & Docker Compose
   - OBS Studio 28+
   - WSL2 (if on Windows)
   - 10+ GB free disk space

3. **Review Documentation**:
   - Architecture: `docs/CONTENT_ARCHITECTURE.md`
   - Setup Guide: `scripts/SETUP.md`
   - Content README: `content/README.md`

4. **Report Issues**:
   - Document exact error messages
   - Include relevant log snippets
   - Note what troubleshooting steps were already tried

---

**Created**: 2025-10-22
**Last Updated**: 2025-10-22
**Related**: CONTENT_ARCHITECTURE.md, scripts/SETUP.md, content/README.md
