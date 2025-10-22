# Content Library Architecture

## Where Everything Lives

Understanding where content files exist vs. where code runs is critical for this project.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Windows Host / WSL2 Host                                     │
│                                                               │
│  ┌─────────────────────────────────────┐                    │
│  │ OBS Studio (Windows/Host)           │                    │
│  │ - Video encoding/streaming          │                    │
│  │ - Reads video files from disk       │                    │
│  │ - Controlled via WebSocket          │                    │
│  └─────────────────────────────────────┘                    │
│                 ↓ reads files from                           │
│  ┌─────────────────────────────────────┐                    │
│  │ WSL2 Filesystem                     │                    │
│  │ /home/turtle_wolfe/repos/OBS_bot/   │                    │
│  │   ├── content/                      │ ← VIDEO FILES HERE │
│  │   │   ├── general/                  │                    │
│  │   │   ├── kids-after-school/        │                    │
│  │   │   ├── professional-hours/       │                    │
│  │   │   └── failover/                 │                    │
│  │   ├── data/                         │ ← DATABASE HERE    │
│  │   ├── logs/                         │ ← LOGS HERE        │
│  │   └── config/                       │                    │
│  └─────────────────────────────────────┘                    │
│                 ↓ mounted into                               │
│  ┌─────────────────────────────────────┐                    │
│  │ Docker Container                    │                    │
│  │ obs_bot_orchestrator                │                    │
│  │   /app/content → (ro mount)         │ ← METADATA ONLY    │
│  │   /app/data    → (rw mount)         │                    │
│  │   /app/logs    → (rw mount)         │                    │
│  │   /app/config  → (ro mount)         │                    │
│  │                                     │                    │
│  │ Python code runs here:              │                    │
│  │ - Track content metadata            │                    │
│  │ - Tell OBS which file to play       │                    │
│  │ - Monitor stream health             │                    │
│  │ - Handle failover logic             │                    │
│  └─────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

## File Paths Explained

### 1. Content Files (Video Files)

**Physical Location**: WSL2 filesystem
```
/home/turtle_wolfe/repos/OBS_bot/content/
├── general/
│   ├── mit-ocw-6.0001/
│   │   ├── 01-What_is_Computation.mp4
│   │   └── ...
│   └── harvard-cs50/
│       └── ...
├── kids-after-school/
│   └── khan-academy/
│       └── ...
├── professional-hours/
│   └── (advanced content)
├── evening-mixed/
│   └── (algorithms, problem solving)
└── failover/
    └── default_failover.mp4
```

**Time-Block Schedule** (Constitutional requirement for age-appropriate content):

- **kids-after-school/**: **3-6 PM weekdays** - Creative coding, beginner-friendly content (Khan Academy, Scratch)
- **professional-hours/**: **9 AM-3 PM weekdays** - Advanced CS, development workflows, professional tools
- **evening-mixed/**: **7-10 PM daily** - Algorithms, problem-solving, general computer science
- **general/**: **All times** - Age-appropriate foundational content (MIT OCW, CS50)
- **failover/**: **Emergency use only** - Default content when no suitable videos available

See `config/settings.yaml` for full time-block configuration.

**Accessed By**:

- **OBS Studio** reads from:
  ```
  //wsl.localhost/Debian/home/turtle_wolfe/repos/OBS_bot/content/general/mit-ocw-6.0001/01-What_is_Computation.mp4
  ```
  *(Windows UNC path to WSL2)*

- **Docker Container** sees (read-only mount):
  ```
  /app/content/general/mit-ocw-6.0001/01-What_is_Computation.mp4
  ```
  *(Container path, used for metadata only)*

- **Download Scripts** write to:
  ```
  /home/turtle_wolfe/repos/OBS_bot/content/
  ```
  *(WSL2 path, run from WSL terminal)*

### 2. Database & State

**Physical Location**: WSL2 filesystem
```
/home/turtle_wolfe/repos/OBS_bot/data/
└── obs_bot.db (SQLite database)
```

**Accessed By**:
- **Docker Container** (read-write mount):
  ```
  /app/data/obs_bot.db
  ```

### 3. Configuration

**Physical Location**: WSL2 filesystem
```
/home/turtle_wolfe/repos/OBS_bot/config/
└── settings.yaml
```

**Accessed By**:
- **Docker Container** (read-only mount):
  ```
  /app/config/settings.yaml
  ```

### 4. Logs

**Physical Location**: WSL2 filesystem
```
/home/turtle_wolfe/repos/OBS_bot/logs/
```

**Accessed By**:
- **Docker Container** (read-write mount):
  ```
  /app/logs/
  ```

## Where to Run What

### Download Content (WSL2 Host)

```bash
# In WSL2 terminal (NOT in Docker)
cd /home/turtle_wolfe/repos/OBS_bot

# Activate virtual environment
source .venv/bin/activate

# Install yt-dlp (if not already installed)
pip install yt-dlp

# Run download scripts
cd scripts
./download_all_content.sh
```

**Why WSL2?**
- ✓ OBS needs direct filesystem access
- ✓ Downloads persist outside container
- ✓ Faster I/O (no container overhead)
- ✓ Easier debugging

### Run Orchestrator (Docker)

```bash
# Build and run orchestrator
docker-compose -f docker-compose.prod.yml up -d obs-orchestrator

# View logs
docker-compose -f docker-compose.prod.yml logs -f obs-orchestrator
```

**Why Docker?**
- ✓ Isolated environment
- ✓ Easy restart on crashes
- ✓ Resource limits
- ✓ Health monitoring
- ✓ Production-ready

### Development (WSL2 Host or Docker)

```bash
# Option 1: Run directly on WSL2 (for development)
cd /home/turtle_wolfe/repos/OBS_bot
source .venv/bin/activate
python -m src.main

# Option 2: Run in Docker (production-like)
docker-compose -f docker-compose.prod.yml up obs-orchestrator
```

## Volume Mounts in Docker

From `docker-compose.prod.yml`:

```yaml
volumes:
  # Content: Read-only (OBS owns the files, Docker just reads metadata)
  - ./content:/app/content:ro

  # Data: Read-write (Docker manages database)
  - ./data:/app/data

  # Logs: Read-write (Docker writes logs)
  - ./logs:/app/logs

  # Config: Read-only (Docker reads settings)
  - ./config:/app/config:ro
```

### Why Read-Only Content Mount?

- ✓ Docker doesn't need to modify video files
- ✓ Prevents accidental deletion/corruption
- ✓ OBS owns the files, Docker just tracks metadata
- ✓ Security best practice

## Network Mode: Host

```yaml
network_mode: host
```

**Why?**
- OBS WebSocket runs on `localhost:4455` (on the host)
- Docker needs to connect to `ws://localhost:4455`
- Host mode makes container use host network stack
- Alternative: Use `host.docker.internal` (less reliable)

## Content Flow

### 1. Download Phase (WSL2)
```
[yt-dlp on WSL2] → [/home/.../content/*.mp4]
```

### 2. Metadata Phase (WSL2 or Docker)
```
[Python script] → Scans /app/content → [Writes to /app/data/obs_bot.db]
```

### 3. Streaming Phase (Orchestrator + OBS)
```
[Docker orchestrator] → Reads metadata from DB
                      → Tells OBS: "Play //wsl.localhost/.../video.mp4"
                      → [OBS] reads file and streams to Twitch
```

## Storage Estimates

| Location | Type | Size | Growth |
|----------|------|------|--------|
| `content/` | Videos | 5-50 GB | Manual (downloads) |
| `data/` | SQLite DB | <100 MB | Slow (metrics) |
| `logs/` | JSON logs | <1 GB | Rotation (30 days) |
| `config/` | YAML | <1 MB | Manual |

## Docker Container Size

- **Base image**: `python:3.11-slim` (~150 MB)
- **Dependencies**: `requirements.txt` (~200 MB)
- **Application code**: `src/` (~5 MB)
- **Total**: ~355 MB

**Content files NOT included** (mounted from host)

## Backup Strategy

### What to Back Up

✓ **Critical**:
- `/home/turtle_wolfe/repos/OBS_bot/data/obs_bot.db` (metrics, state)
- `/home/turtle_wolfe/repos/OBS_bot/config/settings.yaml` (configuration)
- `/home/turtle_wolfe/repos/OBS_bot/.env` (secrets)

✓ **Important**:
- `/home/turtle_wolfe/repos/OBS_bot/logs/` (debugging)

⚠️ **Optional** (can re-download):
- `/home/turtle_wolfe/repos/OBS_bot/content/` (large, CC-licensed, re-downloadable)

### Backup Command

```bash
# Backup critical data
cd /home/turtle_wolfe/repos/OBS_bot
tar -czf backup-$(date +%Y%m%d).tar.gz data/ config/ .env

# Exclude content (too large)
```

## Troubleshooting

### "OBS can't find video file"

**Problem**: Path mismatch between Docker metadata and OBS
**Solution**: Check `windows_content_path` in `config/settings.yaml`

```yaml
content:
  windows_content_path: "//wsl.localhost/Debian/home/turtle_wolfe/repos/OBS_bot/content"
```

Test in OBS:
1. Sources → Add Media Source
2. Browse to: `\\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content\failover\default_failover.mp4`
3. If it plays, path is correct

### "Docker can't see content files"

**Problem**: Volume mount not working
**Solution**: Check docker-compose volume mount

```bash
# Verify mount inside container
docker exec -it obs_bot_orchestrator ls -la /app/content/

# Should show: general/, kids-after-school/, failover/, etc.
```

### "Permission denied" errors

**Problem**: Container user can't read host files
**Solution**: Ensure files are readable

```bash
# On WSL2 host
chmod -R 755 /home/turtle_wolfe/repos/OBS_bot/content/
```

### "Out of disk space"

**Problem**: Content library too large
**Solution**: Selective downloads

Edit download scripts:
```bash
# In download_mit_ocw.sh
--playlist-end 5  # Download only first 5 videos
```

---

**Created**: 2025-10-22
**Architecture Version**: 1.0
**Related**: README.md, content/README.md, scripts/SETUP.md
