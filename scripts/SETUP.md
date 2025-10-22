# Content Library Setup Guide

## Quick Start

This guide will help you download open-source educational content to expand your streaming library beyond Big Buck Bunny.

## Prerequisites

### 1. Install yt-dlp

**Option A: Using pip (Recommended)**
```bash
pip install yt-dlp
```

**Option B: Using apt (Debian/Ubuntu)**
```bash
sudo apt update
sudo apt install yt-dlp
```

**Option C: Using pipx (Isolated installation)**
```bash
pipx install yt-dlp
```

Verify installation:
```bash
yt-dlp --version
```

### 2. Install ffprobe (for metadata extraction)

```bash
sudo apt install ffmpeg
```

This is needed for the metadata script to extract video durations.

## Download Content

### Option 1: Download Everything (Recommended)

This will download all available content sources (~5-10 GB, 1-3 hours):

```bash
cd /home/turtle_wolfe/repos/OBS_bot/scripts
./download_all_content.sh
```

**What gets downloaded:**
- MIT OpenCourseWare 6.0001 (12 Python lectures, ~3-5 GB)
- Harvard CS50 (First 5 lectures as sample, ~2-3 GB)
- Khan Academy (Programming basics sample, ~1-2 GB)

### Option 2: Download Selectively

Download individual sources:

```bash
cd /home/turtle_wolfe/repos/OBS_bot/scripts

# MIT OpenCourseWare only
./download_mit_ocw.sh

# Harvard CS50 only
./download_cs50.sh

# Khan Academy only
./download_khan_academy.sh
```

### Option 3: Manual Download

If you want more control:

1. Visit the source websites:
   - MIT OCW: https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/
   - Harvard CS50: https://cs50.harvard.edu/
   - Khan Academy: https://www.khanacademy.org/computing/computer-programming

2. Download specific videos you want

3. Place them in the appropriate folders:
   ```
   content/
   ├── kids-after-school/    # Creative, beginner content
   ├── professional-hours/   # Advanced content
   ├── evening-mixed/        # Algorithms, problem solving
   └── general/              # CS fundamentals
   ```

## Advanced: Cross Time-Block Content with Symlinks

Some videos are appropriate for multiple time blocks (e.g., a Python fundamentals course suitable for both "general" and "professional-hours"). Use symlinks to avoid duplicating large video files:

### Create Symlinks

```bash
cd /home/turtle_wolfe/repos/OBS_bot/content

# Example: Make MIT OCW available in both general/ and professional-hours/
ln -s ../general/mit-ocw-6.0001 professional-hours/mit-ocw-6.0001

# Example: Make a specific video available in multiple blocks
ln -s ../general/harvard-cs50/00-Lecture_0-Scratch.mp4 kids-after-school/scratch-intro.mp4
```

### Benefits

- **Disk Space**: No file duplication (symlink = 0 bytes)
- **Consistency**: Updates to original automatically apply to all links
- **Flexibility**: Same content available in multiple time blocks

### Limitations

- OBS must be able to follow symlinks (works on WSL2 UNC paths: `//wsl.localhost/...`)
- Metadata scanner will detect symlinked videos as separate entries
- Deleting the original file breaks all symlinks

### Verify Symlinks

```bash
# List symlinks in a directory
ls -lh /home/turtle_wolfe/repos/OBS_bot/content/professional-hours/

# Output shows -> indicating symlink target:
# lrwxrwxrwx 1 user user 24 Oct 22 12:00 mit-ocw-6.0001 -> ../general/mit-ocw-6.0001
```

## Generate Content Metadata

After downloading, scan the content directory and generate metadata:

```bash
cd /home/turtle_wolfe/repos/OBS_bot/scripts
python3 add_content_metadata.py
```

This creates `content_metadata.json` with:
- Video titles and durations
- License information
- Time block assignments
- Source attribution
- Tags and topics

## Verify Downloads

Check what was downloaded:

```bash
# Count videos by directory
find /home/turtle_wolfe/repos/OBS_bot/content -name "*.mp4" | wc -l

# List all downloaded content
ls -lh /home/turtle_wolfe/repos/OBS_bot/content/general/*/

# Check total disk usage
du -sh /home/turtle_wolfe/repos/OBS_bot/content/
```

## Troubleshooting

### yt-dlp: command not found

Install yt-dlp using one of the methods above.

### Download speeds are too slow

Add `--limit-rate 1M` to limit bandwidth usage, or remove `--throttled-rate` from scripts for maximum speed.

### Videos won't play in OBS

Ensure videos are in a compatible format (MP4, H.264). Re-encode if needed:

```bash
ffmpeg -i input.mkv -c:v libx264 -c:a aac output.mp4
```

### Disk space issues

Check available space:
```bash
df -h /home/turtle_wolfe/repos/OBS_bot/
```

To download only specific lectures, edit the download scripts and add:
```bash
--playlist-items 1-5  # Download only items 1-5
```

### Permission errors

Ensure scripts are executable:
```bash
chmod +x /home/turtle_wolfe/repos/OBS_bot/scripts/*.sh
```

## Next Steps After Download

1. **Test playback**: Open downloaded videos in OBS to ensure compatibility

2. **Configure OBS scenes**: Create media sources for new content

3. **Update database**: Import content metadata into SQLite

4. **Test content scheduler**: Verify the system selects appropriate content for each time block

5. **Attribution display**: Configure OBS text overlay for license attribution

6. **Failover testing**: Ensure system gracefully handles content failures

## License Compliance

All downloaded content is licensed under Creative Commons licenses (CC BY-NC-SA):

- ✓ **Attribution required**: Display source in OBS overlay
- ✓ **Non-commercial use**: Educational streaming complies
- ✓ **Share-alike**: Derivatives must use same license
- ✗ **No commercial use**: Don't monetize with ads

See `content/README.md` for complete license information.

## Storage Estimates

| Source | Videos | Size | Duration |
|--------|--------|------|----------|
| MIT OCW 6.0001 | 12 | ~3-5 GB | ~15 hours |
| Harvard CS50 (sample) | 5 | ~2-3 GB | ~6 hours |
| Khan Academy (sample) | 10 | ~1-2 GB | ~3 hours |
| **Total** | **27** | **~5-10 GB** | **~24 hours** |

To download full courses (not just samples), edit the download scripts and remove `--playlist-end N` lines.

## Support

If you encounter issues:
1. Check `yt-dlp` is up to date: `yt-dlp -U`
2. Review script output for error messages
3. Verify internet connectivity
4. Check source URLs are still accessible

---

**Created**: 2025-10-22
**Maintainer**: OBS_bot Project
