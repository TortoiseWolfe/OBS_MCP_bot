# Content Library Quick Start

**Goal**: Expand your content library from 1 video (Big Buck Bunny) to 24+ hours of educational content.

## TL;DR - What You Need to Know

1. **Content lives on WSL2 filesystem** (NOT inside Docker)
2. **Downloads happen on WSL2** (NOT in Docker container)
3. **OBS reads files directly** from WSL2
4. **Docker container** just tracks metadata and tells OBS what to play

## Step-by-Step Setup

### Step 1: Install yt-dlp (WSL2)

```bash
# In WSL2 terminal
cd /home/turtle_wolfe/repos/OBS_bot
source .venv/bin/activate
pip install yt-dlp
```

**Verify**:
```bash
yt-dlp --version
```

### Step 2: Download Content (WSL2)

```bash
# Still in WSL2, with .venv activated
cd scripts
./download_all_content.sh
```

**What happens**:
- Downloads ~27 videos (~5-10 GB)
- Takes 1-3 hours depending on connection
- Saves to `/home/turtle_wolfe/repos/OBS_bot/content/`
- Organized by time blocks (kids, professional, general)

**Alternative** (selective download):
```bash
# Just MIT OCW (~3-5 GB)
./download_mit_ocw.sh

# Just CS50 (~2-3 GB, first 5 lectures)
./download_cs50.sh

# Just Khan Academy (~1-2 GB)
./download_khan_academy.sh
```

### Step 3: Generate Metadata (WSL2)

```bash
# After downloads complete
cd /home/turtle_wolfe/repos/OBS_bot/scripts
python3 add_content_metadata.py
```

**Output**:
- `content_metadata.json` (database import ready)
- Summary: videos by source, time block, total duration

### Step 4: Test in OBS (Windows/Host)

Before running the orchestrator, verify OBS can access the files:

1. Open OBS Studio
2. Sources → Add → Media Source
3. Browse to: `\\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content\failover\default_failover.mp4`
4. If it plays → paths are correct ✓

Try a downloaded video:
```
\\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content\general\mit-ocw-6.0001\01-What_is_Computation.mp4
```

### Step 5: Update Orchestrator Config (Optional)

The configuration is already updated in `config/settings.yaml`. Review if needed:

```bash
cat /home/turtle_wolfe/repos/OBS_bot/config/settings.yaml | grep -A 20 "time_block_paths"
```

### Step 6: Run Orchestrator (Docker)

```bash
# Build and start
cd /home/turtle_wolfe/repos/OBS_bot
docker-compose -f docker-compose.prod.yml up -d obs-orchestrator

# Check logs
docker-compose -f docker-compose.prod.yml logs -f obs-orchestrator

# Verify content mount
docker exec obs_bot_orchestrator ls -la /app/content/
```

## Verification Checklist

After setup, verify:

- [ ] yt-dlp installed on WSL2 (not Docker)
- [ ] Content downloaded to `/home/turtle_wolfe/repos/OBS_bot/content/`
- [ ] Videos organized in time block folders
- [ ] Metadata generated (`content_metadata.json` exists)
- [ ] OBS can play videos from WSL path
- [ ] Docker can see content mount (`/app/content/`)
- [ ] Orchestrator logs show content library detected

## Troubleshooting

### yt-dlp not found

```bash
# Make sure you're in virtual environment
cd /home/turtle_wolfe/repos/OBS_bot
source .venv/bin/activate
pip install yt-dlp
```

### Downloads failing

```bash
# Update yt-dlp
pip install -U yt-dlp

# Test single video
yt-dlp "https://www.youtube.com/watch?v=nykOeWgQcHM"
```

### OBS can't find videos

**Check path format**:
- ✓ Correct: `\\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content\file.mp4`
- ✗ Wrong: `/home/turtle_wolfe/repos/OBS_bot/content/file.mp4` (Linux path)

### Docker can't see content

```bash
# Check mount
docker exec obs_bot_orchestrator ls /app/content/

# If empty, check docker-compose volume:
grep -A 5 "volumes:" docker-compose.prod.yml
```

Should show:
```yaml
volumes:
  - ./content:/app/content:ro
```

### No space left on device

```bash
# Check available space
df -h /home/turtle_wolfe/repos/OBS_bot/

# Selective download (edit scripts)
# Add: --playlist-end 5
```

## File Locations Reference

| What | Where (WSL2) | Where (Docker) | Where (OBS) |
|------|--------------|----------------|-------------|
| Videos | `/home/.../content/` | `/app/content/` (ro) | `\\wsl.localhost\...\content\` |
| Database | `/home/.../data/` | `/app/data/` (rw) | N/A |
| Config | `/home/.../config/` | `/app/config/` (ro) | N/A |
| Logs | `/home/.../logs/` | `/app/logs/` (rw) | N/A |

## Next Steps

After content is downloaded and verified:

1. **Tier 1**: Integrate content scheduler with new library
2. **Tier 2**: Add Twitch chat bot (in progress)
3. **Tier 3**: Implement time-based content filtering
4. **Tier 4**: Add AI teaching personality

## Storage Management

Current setup:
```
content/           5-50 GB   (CC-licensed, re-downloadable)
data/              <100 MB   (backup critical)
logs/              <1 GB     (30-day rotation)
```

To expand library:
- Remove `--playlist-end 5` from `download_cs50.sh` (full course)
- Add more sources (see `content/README.md` for suggestions)
- Download specific topics only

## License Compliance

All content is CC BY-NC-SA licensed:
- ✓ Attribution displayed in OBS
- ✓ Non-commercial (educational streaming)
- ✓ No monetization
- ✓ Twitch TOS compliant

See `content/README.md` for full details.

## Get Help

- **Architecture questions**: See `docs/CONTENT_ARCHITECTURE.md`
- **Download issues**: See `scripts/SETUP.md`
- **License info**: See `content/README.md`
- **Tier 1 spec**: See `specs/001-tier1-obs-streaming/spec.md`

---

**Created**: 2025-10-22
**Status**: Ready for use
**Estimated Time**: 2-4 hours (including downloads)
