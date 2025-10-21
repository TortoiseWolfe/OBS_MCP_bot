# Quickstart Guide: Tier 1 OBS Streaming Foundation

**Feature**: 001-tier1-obs-streaming
**Date**: 2025-10-20
**Target Audience**: Developers implementing this feature

## Overview

This guide walks through local development setup for the Tier 1 OBS Streaming Foundation. Follow these steps to get a working development environment that can control OBS, stream to Twitch, and pass all pre-flight validations.

## Prerequisites

### Required Software

1. **Python 3.11+**
   ```bash
   python3 --version  # Should be 3.11 or higher
   ```

2. **OBS Studio 29.0+** with **obs-websocket 5.x** plugin
   - Download: https://obsproject.com/download
   - obs-websocket is included in OBS 28+
   - Verify: OBS → Tools → WebSocket Server Settings

3. **Docker & Docker Compose**
   ```bash
   docker --version
   docker-compose --version
   ```

4. **Twitch Account** with stream key
   - Get your stream key: https://dashboard.twitch.tv/settings/stream

### System Resources

- **CPU**: 4+ cores recommended (OBS encoding + orchestration)
- **RAM**: 8GB minimum, 16GB recommended
- **Network**: 10 Mbps upload minimum for 1080p streaming
- **Disk**: 10GB for logs, state persistence, failover content

---

## Step 1: OBS Studio Setup

### 1.1 Install and Configure OBS

```bash
# Ubuntu/Debian
sudo apt install obs-studio

# macOS
brew install --cask obs

# Windows
# Download installer from https://obsproject.com
```

### 1.2 Enable WebSocket Server

1. Open OBS Studio
2. **Tools** → **WebSocket Server Settings**
3. **Enable WebSocket server**: ✅ Checked
4. **Server Port**: `4455` (default)
5. **Server Password**: Leave blank for development (or note password for production)
6. Click **Apply** → **OK**

### 1.3 Configure Twitch Streaming

1. **Settings** → **Stream**
2. **Service**: Twitch
3. **Server**: Auto (Recommended)
4. **Stream Key**: Paste your Twitch stream key
5. Click **Apply** → **OK**

**⚠️ IMPORTANT**: Do NOT click "Start Streaming" in OBS. The system will control streaming automatically.

---

## Step 2: Project Setup

### 2.1 Clone Repository

```bash
cd ~/repos
git clone https://github.com/owner/obs-bot.git
cd obs-bot
```

### 2.2 Create Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2.3 Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt** (create if doesn't exist):
```txt
# Core
obs-websocket-py==0.11.0
aiosqlite==0.19.0

# API & Web
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0

# Logging
structlog==23.2.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.25.2
```

### 2.4 Create Configuration File

Create `config/settings.yaml`:

```yaml
obs:
  websocket_host: localhost
  websocket_port: 4455
  websocket_password: null  # or your password if set

twitch:
  # Stream key configured in OBS, not needed here
  verify_connection: true

health_api:
  host: 0.0.0.0
  port: 8000

owner_sources:
  # Configure your source names from OBS
  designated_sources:
    - "Screen Capture"  # Adjust to match your OBS source name
  detection_method: "source_enabled"
  debounce_time_sec: 5.0

failover:
  content_path: "/path/to/failover-video.mp4"  # REQUIRED
  verify_on_startup: true

logging:
  level: INFO
  format: json
  log_dir: "./logs"
  max_size_mb: 100
  retention_days: 30

database:
  path: "./data/stream.db"
```

### 2.5 Create Failover Content

The system REQUIRES failover content to pass pre-flight validation (FR-024).

**Option 1: Use sample video**
```bash
mkdir -p data
# Download a copyright-free video
wget -O data/failover.mp4 "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4"
```

**Option 2: Create simple test pattern**
```bash
# Requires ffmpeg
ffmpeg -f lavfi -i testsrc=duration=30:size=1920x1080:rate=30 \
  -f lavfi -i sine=frequency=1000:duration=30 \
  -c:v libx264 -preset fast -crf 22 -c:a aac -b:a 128k \
  data/failover.mp4
```

Update `config/settings.yaml`:
```yaml
failover:
  content_path: "./data/failover.mp4"
```

---

## Step 3: Database Initialization

The system auto-creates SQLite database on first run, but you can initialize manually:

```bash
mkdir -p data logs
python -m src.persistence.db --init
```

This creates:
- `data/stream.db`: SQLite database with schema from `data-model.md`
- `logs/`: Directory for structured JSON logs

---

## Step 4: OBS Scene Setup (Optional)

The system auto-creates required scenes on first run (FR-003), but you can create them manually for customization:

1. Open OBS Studio
2. In **Scenes** panel, create:
   - **Automated Content** scene
   - **Owner Live** scene
   - **Failover** scene
   - **Technical Difficulties** scene

3. For **Automated Content** scene:
   - Add source: **Media Source**
   - Name: "Content Player"
   - ✅ Local File
   - Browse to your content library

4. For **Owner Live** scene:
   - Add source: **Screen Capture** (match name in config/settings.yaml)
   - Add source: **Video Capture Device** (webcam, optional)
   - Add source: **Audio Input Capture** (microphone, optional)

5. For **Failover** scene:
   - Add source: **Media Source**
   - Point to `data/failover.mp4`
   - ✅ Loop

---

## Step 5: Run Development Server

### 5.1 Start OBS Studio

```bash
# Make sure OBS is running with WebSocket enabled
# Don't start streaming manually - the system handles this
```

### 5.2 Run the Orchestrator

```bash
source .venv/bin/activate
python -m src.main
```

**Expected Output**:
```json
{"timestamp": "2025-10-20T10:00:00Z", "level": "info", "event": "startup_initiated"}
{"timestamp": "2025-10-20T10:00:01Z", "level": "info", "event": "pre_flight_check", "check": "obs_connectivity", "status": "pass"}
{"timestamp": "2025-10-20T10:00:02Z", "level": "info", "event": "pre_flight_check", "check": "scenes_exist", "status": "pass"}
{"timestamp": "2025-10-20T10:00:03Z", "level": "info", "event": "pre_flight_check", "check": "failover_content", "status": "pass"}
{"timestamp": "2025-10-20T10:00:04Z", "level": "info", "event": "pre_flight_check", "check": "twitch_credentials", "status": "pass"}
{"timestamp": "2025-10-20T10:00:05Z", "level": "info", "event": "pre_flight_check", "check": "network_connectivity", "status": "pass"}
{"timestamp": "2025-10-20T10:00:06Z", "level": "info", "event": "streaming_started", "session_id": "550e8400-..."}
```

**If pre-flight fails**:
```json
{"timestamp": "2025-10-20T10:00:02Z", "level": "error", "event": "pre_flight_failed", "check": "obs_connectivity", "details": "Connection refused on localhost:4455"}
```
→ Fix the issue (start OBS, check port, enable WebSocket) and the system will retry every 60 seconds.

### 5.3 Verify Streaming

1. **Check Twitch Dashboard**: https://dashboard.twitch.tv/stream-manager
   - Stream should be LIVE
   - Should see OBS scene content

2. **Check Health API**:
   ```bash
   curl http://localhost:8000/health | jq
   ```

   Expected response:
   ```json
   {
     "streaming": true,
     "uptime_seconds": 15,
     "uptime_percentage": 100.0,
     "current_scene": "Automated Content",
     "stream_quality": {
       "bitrate_kbps": 6000.0,
       "dropped_frames_pct": 0.2,
       "cpu_usage_pct": 45.0,
       "connection_status": "connected"
     },
     "owner_live": false,
     "last_failover": null,
     "session_info": {
       "session_id": "550e8400-e29b-41d4-a716-446655440000",
       "start_time": "2025-10-20T10:00:06Z",
       "total_downtime_sec": 0
     }
   }
   ```

---

## Step 6: Test Owner Interrupt

### 6.1 Configure Owner Source

Make sure `config/settings.yaml` has your actual OBS source name:

```yaml
owner_sources:
  designated_sources:
    - "Screen Capture"  # Must match exactly
```

### 6.2 Trigger Owner Live

1. In OBS Studio, find your "Screen Capture" source (in any scene)
2. Click the **eye icon** to make it visible (enabled)
3. Watch the logs:

```json
{"timestamp": "2025-10-20T10:05:10Z", "level": "info", "event": "owner_source_detected", "source": "Screen Capture"}
{"timestamp": "2025-10-20T10:05:11Z", "level": "info", "event": "transitioning_to_owner", "target_scene": "Owner Live"}
{"timestamp": "2025-10-20T10:05:15Z", "level": "info", "event": "owner_live_started", "transition_time_sec": 5.2}
```

4. Check Health API:
```bash
curl http://localhost:8000/health | jq '.owner_live'
# Should return: true
```

5. **End owner session**: Disable "Screen Capture" source (click eye icon again)

```json
{"timestamp": "2025-10-20T10:10:00Z", "level": "info", "event": "owner_source_deactivated"}
{"timestamp": "2025-10-20T10:10:08Z", "level": "info", "event": "resumed_automated_content"}
```

---

## Step 7: Test Failover

### 7.1 Simulate Content Failure

1. While streaming, stop the media source in "Automated Content" scene
2. Watch for automatic failover:

```json
{"timestamp": "2025-10-20T10:15:05Z", "level": "error", "event": "content_failure_detected", "source": "Content Player"}
{"timestamp": "2025-10-20T10:15:06Z", "level": "info", "event": "failover_triggered", "target_scene": "Failover"}
{"timestamp": "2025-10-20T10:15:09Z", "level": "info", "event": "failover_complete", "recovery_time_sec": 4.1}
```

3. Check Health API:
```bash
curl http://localhost:8000/health | jq '.last_failover'
```

Expected:
```json
{
  "timestamp": "2025-10-20T10:15:05Z",
  "failure_cause": "content_failure",
  "recovery_time_sec": 4.1
}
```

---

## Step 8: Run Tests

### 8.1 Unit Tests

```bash
pytest tests/unit/ -v
```

### 8.2 Integration Tests (requires running OBS)

```bash
# Make sure OBS is running with WebSocket enabled
pytest tests/integration/ -v
```

### 8.3 Contract Tests

```bash
pytest tests/contract/ -v
```

### 8.4 Coverage Report

```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report
```

---

## Step 9: Docker Deployment (Production)

### 9.1 Build Docker Image

```bash
docker-compose build
```

### 9.2 Run in Docker

```bash
docker-compose up -d
```

**docker-compose.yml** (create if doesn't exist):
```yaml
version: '3.8'

services:
  obs-orchestrator:
    build: .
    container_name: obs-streaming
    network_mode: host  # Access OBS on localhost:4455
    volumes:
      - ./config:/app/config:ro
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

### 9.3 View Logs

```bash
docker-compose logs -f
```

---

## Troubleshooting

### Pre-flight Validation Fails

**Error**: `obs_connectivity: fail`
- ✅ OBS Studio is running
- ✅ WebSocket server enabled (Tools → WebSocket Server Settings)
- ✅ Port 4455 accessible: `nc -zv localhost 4455`

**Error**: `failover_content: fail`
- ✅ Failover file exists: `ls -lh data/failover.mp4`
- ✅ File is playable: `ffprobe data/failover.mp4`
- ✅ Path in `config/settings.yaml` matches

**Error**: `twitch_credentials: fail`
- ✅ Stream key configured in OBS (Settings → Stream)
- ✅ Test with manual OBS stream first

**Error**: `network_connectivity: fail`
- ✅ Internet connection working
- ✅ Can reach Twitch: `ping live.twitch.tv`
- ✅ No firewall blocking RTMP (port 1935)

### Owner Source Detection Not Working

**Symptom**: Activating screen capture doesn't trigger owner live

- ✅ Source name in `config/settings.yaml` matches exactly (case-sensitive)
- ✅ Source exists in OBS: Right-click Sources panel → look for exact name
- ✅ Check logs for detection events:
  ```bash
  tail -f logs/stream.log | jq 'select(.event == "source_check")'
  ```

### Health API Not Responding

**Error**: `curl: (7) Failed to connect to localhost port 8000`

- ✅ Check if service is running: `ps aux | grep python`
- ✅ Check port is free before starting: `lsof -i :8000`
- ✅ Review logs for startup errors:
  ```bash
  tail -f logs/stream.log | jq 'select(.level == "error")'
  ```

---

## Next Steps

**Development Complete** → Proceed to `/speckit.tasks` to generate implementation task list.

**Quick Commands Reference**:

```bash
# Start development
source .venv/bin/activate
python -m src.main

# Check health
curl http://localhost:8000/health | jq

# View uptime report
curl http://localhost:8000/health/uptime?period_days=7 | jq

# Watch logs in real-time
tail -f logs/stream.log | jq

# Run tests
pytest tests/ -v --cov=src

# Docker deployment
docker-compose up -d
docker-compose logs -f
```

**Success Criteria Validation**:
- SC-001: Run `curl localhost:8000/health/uptime?period_days=7 | jq '.uptime_percentage'` (should be >99.9%)
- SC-002: Check logs for startup time (should auto-start within 60 sec)
- SC-003: Test owner interrupt 5+ times, check transition times in logs
- SC-005: Check `dropped_frames_pct` in health API (should be <1%)

Happy streaming! 🎥✨
