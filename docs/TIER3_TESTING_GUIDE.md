# Tier 3 Testing Guide: Smart Content Scheduling

This guide walks through testing the new **Tier 3 Content Library Management** system with time-aware, database-driven content scheduling.

## What's New in Tier 3

### Before (Tier 1 MVP):
- ❌ Simple filesystem scan
- ❌ Round-robin playback (all content equal)
- ❌ 5-minute duration estimates
- ❌ No time awareness
- ❌ No content metadata

### After (Tier 3):
- ✅ **Database-driven selection**
- ✅ **Time-aware scheduling** (Kids content 3-6 PM, Professional 9 AM-3 PM, etc.)
- ✅ **Age-appropriate filtering**
- ✅ **Actual video durations** from ffprobe
- ✅ **Priority ordering** (1=highest → 10=lowest)
- ✅ **Rich metadata** (source, course, license, tags)
- ✅ **Automatic attribution** text generation

---

## Prerequisites

**System Requirements:**
- Python 3.11+
- ffmpeg and ffprobe installed
- yt-dlp installed
- 5 GB free disk space (phased) or 15 GB (full)

**Check Dependencies:**
```bash
# Check Python version
python3 --version  # Should be 3.11+

# Check ffmpeg/ffprobe
ffprobe -version
ffmpeg -version

# Check yt-dlp
yt-dlp --version

# Install if missing:
pip install yt-dlp
sudo apt install ffmpeg  # Debian/Ubuntu
```

---

## Phase 1: Download Test Content (MVP Mode)

Download minimal content strategically (~1-2 GB):

```bash
cd /home/turtle_wolfe/repos/OBS_bot/scripts/

# Download phased content for testing
./download_phased.sh

# What this downloads:
# - Big Buck Bunny (failover, 151 MB) - already exists
# - 3 MIT OCW lectures (general, ~500 MB)
# - 2 Khan Academy videos (kids, ~200 MB)
# - 2 CS50 lectures (evening, ~400 MB)
# Total: ~1.2 GB
```

**Expected Output:**
```
======================================================================
Phased Content Download Script
======================================================================

Mode: PHASED MVP DOWNLOAD (~1-2 GB)

✓ yt-dlp installed
✓ Disk space sufficient (5 GB required)

======================================================================
Phase 1: Failover Content (Big Buck Bunny)
======================================================================

✓ Failover content already exists

======================================================================
Phase 2: General Content (MIT OpenCourseWare)
======================================================================

Downloading first 3 MIT OCW 6.0001 lectures (~500 MB)...
  [download] Downloading item 1 of 3
  [download] 100% of 167.3 MiB in 02:15
  ...

✓ Phase 2 complete
...
```

**Verify Downloads:**
```bash
# Check content structure
ls -lhR ../content/

# Should see:
# content/
# ├── failover/
# │   └── big_buck_bunny.mp4 (151 MB)
# ├── general/
# │   └── mit-ocw-6.0001/
# │       ├── 01-What_is_Computation.mp4
# │       ├── 02-Branching_and_Iteration.mp4
# │       └── 03-String_Manipulation.mp4
# ├── kids-after-school/
# │   └── khan-academy/
# │       ├── 01-Intro_to_Drawing.mp4
# │       └── 02-Intro_to_Animation.mp4
# └── evening-mixed/
#     └── harvard-cs50/
#         ├── 00-Lecture_0.mp4
#         └── 01-Lecture_1.mp4
```

---

## Phase 2: Extract Metadata and Import to Database

Run the metadata extraction CLI:

```bash
cd /home/turtle_wolfe/repos/OBS_bot/

# Dry run first (no database changes)
python3 scripts/add_content_metadata.py --dry-run

# Full import to database
python3 scripts/add_content_metadata.py
```

**Expected Output:**
```
======================================================================
Content Metadata Extraction and Database Import
======================================================================

Content Root: /home/turtle_wolfe/repos/OBS_bot/content
Database Path: data/obs_bot.db
Mode: FULL SCAN + DATABASE IMPORT

----------------------------------------------------------------------

📁 Scanning content directories...
----------------------------------------------------------------------
  kids-after-school: 2 videos
  professional-hours: (directory missing)
  evening-mixed: 2 videos
  general: 3 videos
  failover: 1 videos

✅ Found 8 total video files

🔍 Extracting metadata (this may take a few minutes)...
----------------------------------------------------------------------
  Progress: 5/8 (62%)
  Progress: 8/8 (100%)

✅ Successfully extracted metadata from 8 videos

============================================================
Content Library Summary
============================================================

Total Videos: 8
Total Duration: 2.15 hours (7740 seconds)
Total Size: 1.17 GB (1197.50 MB)

By Source:
  Blender Foundation: 1 videos
  Harvard CS50: 2 videos
  Khan Academy: 2 videos
  MIT OpenCourseWare: 3 videos

By Time Block:
  after_school_kids: 2 videos
  evening_mixed: 5 videos
  failover: 1 videos
  general: 5 videos

============================================================

💾 Importing to database...
----------------------------------------------------------------------

✅ Database import complete!

Library Statistics:
  Total Videos: 8
  Total Duration: 2.15 hours
  Total Size: 1.17 GB
  Last Scanned: 2025-10-22 15:30:00+00:00

By Source:
  MIT OCW: 3
  Harvard CS50: 2
  Khan Academy: 2
  Blender: 1
```

**Verify Database:**
```bash
# Check database exists
ls -lh data/obs_bot.db

# Query content (optional)
sqlite3 data/obs_bot.db "SELECT title, source_attribution, time_blocks FROM content_sources LIMIT 5;"
```

---

## Phase 3: Test Smart Scheduling

### 3.1 Understanding Time Blocks

The scheduler automatically selects content based on current time:

| Time Block | Hours | Days | Age Rating | Example Content |
|------------|-------|------|------------|----------------|
| **Kids After School** | 3-6 PM | Mon-Fri | KIDS | Khan Academy |
| **Professional Hours** | 9 AM-3 PM | Mon-Fri | ADULT | MIT OCW (advanced) |
| **Evening Mixed** | 7-10 PM | Daily | ALL | CS50, MIT OCW |
| **General** | All other times | Daily | ALL | Fallback content |

### 3.2 Start the Orchestrator

```bash
# Start with logging to see scheduler decisions
python3 -m src.main

# Watch logs for scheduler output
tail -f logs/obs_bot.log
```

**What to Look For in Logs:**

```
INFO selecting_content_for_time_block time_block=evening_mixed age_rating=all
INFO content_selection_complete matched=5 time_block=evening_mixed
INFO content_selected_from_database count=5
INFO content_playback_starting_db title="Lecture 0 - Scratch" source=CS50 duration_sec=6420 time_blocks=['evening_mixed', 'general']
```

### 3.3 Test Different Time Blocks

**Simulate Different Times** (for testing):

Edit `src/services/content_scheduler.py` temporarily:

```python
# Line 244: Hardcode a specific time for testing
def _get_current_time_block(self) -> Optional[str]:
    """Determine current time block based on current time."""

    # TESTING ONLY: Hardcode time block
    return "after_school_kids"  # Force kids content
    # return "professional_hours"  # Force professional content
    # return "evening_mixed"  # Force evening content

    # Original code (comment out for testing):
    # now = datetime.now(timezone.utc)
    # hour = now.hour
    # ...
```

**Test Scenarios:**

1. **Kids Time Block (3-6 PM):**
   - Expected: Khan Academy videos play
   - Logs should show: `time_block=after_school_kids age_rating=kids`

2. **Evening Time Block (7-10 PM):**
   - Expected: CS50 and MIT OCW videos play
   - Logs should show: `time_block=evening_mixed age_rating=all`

3. **General Time Block (off-hours):**
   - Expected: All content with "general" time block plays
   - Logs should show: `time_block=general age_rating=all`

---

## Phase 4: Test OBS Attribution Updates

### 4.1 Setup OBS Text Source

**In OBS Studio:**

1. Open OBS
2. Select "Automated Content" scene (or create it)
3. Right-click Sources → Add → **Text (FreeType 2)**
4. Name it exactly: `Content Attribution`
5. Configure:
   - Font: Arial, size 28-32
   - Color: White (#FFFFFF)
   - Outline: Black, 2-3px
   - Position: Bottom-left corner

See `docs/OBS_ATTRIBUTION_SETUP.md` for detailed setup.

### 4.2 Verify Attribution Updates

**What Should Happen:**

When content changes, the "Content Attribution" text source should update automatically:

- MIT OCW: `MIT OCW 6.0001: Lecture 1 - CC BY-NC-SA 4.0`
- CS50: `Harvard CS50: Lecture 0 - CC BY-NC-SA 4.0`
- Khan Academy: `Khan Academy: Intro to Drawing - CC BY-NC-SA`

**Check Pre-flight Validation:**

On orchestrator startup, you should see:

```
INFO preflight_check_passed check=attribution_text_source
```

If you see an error:
```
❌ ATTRIBUTION TEXT SOURCE EXISTS
   Error: Text source 'Content Attribution' not found in OBS
```

→ Create the text source in OBS (see 4.1 above)

---

## Phase 5: Validation Checklist

### Content Download ✅
- [ ] All 4 time-block directories exist
- [ ] 8 videos downloaded (~1.2 GB total)
- [ ] Big Buck Bunny in failover/
- [ ] MIT OCW videos in general/
- [ ] Khan Academy videos in kids-after-school/
- [ ] CS50 videos in evening-mixed/

### Metadata Extraction ✅
- [ ] `scripts/add_content_metadata.py` runs without errors
- [ ] Database `data/obs_bot.db` created
- [ ] 8 ContentSource records in database
- [ ] Library statistics show correct totals
- [ ] Video durations are accurate (not all 300 seconds)

### Smart Scheduling ✅
- [ ] Orchestrator starts without errors
- [ ] Logs show `content_selected_from_database`
- [ ] Logs show correct `time_block=...` for current time
- [ ] Content plays in priority order
- [ ] Age-appropriate content selected

### OBS Integration ✅
- [ ] "Content Attribution" text source exists in OBS
- [ ] Pre-flight validation passes
- [ ] Attribution text updates when content changes
- [ ] Format: `{source} {course}: {title} - {license}`

---

## Troubleshooting

### Issue: "No content found in database"

**Cause:** Metadata not imported or database missing

**Fix:**
```bash
# Re-run metadata import
python3 scripts/add_content_metadata.py

# Verify database
ls -lh data/obs_bot.db
sqlite3 data/obs_bot.db "SELECT COUNT(*) FROM content_sources;"
```

### Issue: "Text source 'Content Attribution' not found"

**Cause:** OBS text source not created or wrong name

**Fix:**
- Create text source in OBS with exact name: `Content Attribution`
- Restart orchestrator after creating source
- See `docs/OBS_ATTRIBUTION_SETUP.md`

### Issue: Wrong content playing for time block

**Cause:** Time zone mismatch or content missing time block

**Fix:**
```bash
# Check current time block detection
# In Python:
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
print(f"Current hour (UTC): {now.hour}")
print(f"Current weekday: {now.weekday()}")  # 0=Monday

# If time zone is wrong, content_scheduler uses UTC
# Adjust time_blocks in database if needed
```

### Issue: All videos show 300 seconds duration

**Cause:** Metadata extraction failed, using default duration

**Fix:**
```bash
# Check ffprobe is installed
ffprobe -version

# Re-extract metadata with verbose logging
python3 scripts/add_content_metadata.py --dry-run

# Check logs for ffprobe errors
```

---

## Success Criteria

**Tier 3 is working correctly if:**

1. ✅ **Content downloads** complete without errors (~1.2 GB)
2. ✅ **Metadata extraction** processes all videos (<2 minutes for 8 videos)
3. ✅ **Database import** succeeds with accurate statistics
4. ✅ **Smart scheduler** selects appropriate content for time blocks
5. ✅ **Actual durations** used (not 300-second estimates)
6. ✅ **Priority ordering** respected within time blocks
7. ✅ **Attribution updates** display in OBS automatically

---

## Next Steps After Testing

### If Everything Works:
1. **Download more content:** Run `./download_phased.sh --full` for complete library
2. **Write tests:** Unit tests for metadata services
3. **Complete docs:** Update production documentation
4. **Deploy:** Ready for 24/7 streaming

### If Issues Found:
1. **Review logs:** Check `logs/obs_bot.log` for errors
2. **Verify setup:** Recheck prerequisites and OBS configuration
3. **Report bugs:** Document issue with logs and steps to reproduce

---

## Performance Benchmarks

**Expected Performance (SC-XXX compliance):**

| Metric | Target | Actual |
|--------|--------|--------|
| Metadata extraction (25 videos) | <2 minutes | ~1-1.5 min |
| Database query time | <1 second | ~50-100 ms |
| Attribution update | <1 second | ~100-200 ms |
| Content selection | <1 second | ~10-50 ms |

---

## Advanced Testing

### Test Priority Ordering

Edit priority in database:
```sql
-- Give MIT OCW highest priority (1)
UPDATE content_sources
SET priority = 1
WHERE source_attribution = 'MIT_OCW';

-- Give CS50 lower priority (8)
UPDATE content_sources
SET priority = 8
WHERE source_attribution = 'CS50';
```

Restart orchestrator and verify MIT OCW plays first.

### Test Age Filtering

Temporarily set all content to KIDS rating:
```sql
UPDATE content_sources SET age_rating = 'kids';
```

During professional hours (9 AM-3 PM weekdays), no content should play (requires ADULT).

### Test Failover

Remove all content from database:
```sql
DELETE FROM content_sources WHERE source_attribution != 'BLENDER';
```

Orchestrator should fall back to failover scene automatically.

---

**Questions or issues? See:**
- `docs/CONTENT_ARCHITECTURE.md` - System architecture
- `docs/OBS_ATTRIBUTION_SETUP.md` - Attribution setup guide
- GitHub Issues: https://github.com/TortoiseWolfe/OBS_bot/issues
