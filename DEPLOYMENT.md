# OBS_bot Deployment Guide

**Status**: MVP Functional - Streaming Live (2025-10-21)

This guide covers deploying the working MVP (User Story 1) on various platforms.

## Table of Contents

- [Prerequisites](#prerequisites)
- [WSL2 + Docker Desktop (Windows)](#wsl2--docker-desktop-windows)
- [Native Linux + Docker](#native-linux--docker)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Monitoring](#monitoring)

---

## Prerequisites

### Required Software

1. **OBS Studio 29.0+** with obs-websocket 5.x
   - Download: https://obsproject.com/download
   - **Important**: Install on **Windows** (not inside WSL2)
   - Enable WebSocket server: Tools → WebSocket Server Settings
   - Note the port (default: 4455) and password (if set)

2. **Docker + Docker Desktop**
   ```bash
   docker --version       # Should be 20.10+
   docker-compose --version
   ```

3. **Content Files**
   - At least one video file (MP4, MKV, AVI, MOV, WEBM)
   - Test with Big Buck Bunny: http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4

4. **Twitch Stream Key**
   - Get from: https://dashboard.twitch.tv/settings/stream
   - **NEVER commit this to git!**

### System Resources

- **CPU**: 4+ cores (OBS encoding + orchestrator)
- **RAM**: 8GB minimum, 16GB recommended
- **Upload**: 10 Mbps minimum for 1080p/60fps
- **Disk**: 10GB for logs, database, content

---

## WSL2 + Docker Desktop (Windows)

**This is the current working deployment** (tested 2025-10-21)

### 1. Find Windows Host IP

OBS Studio runs on Windows, but the bot runs in WSL2. They need to communicate over the network.

```bash
# Inside WSL2, find the Windows host IP
ip route show | grep -i default | awk '{ print $3}'
# Example output: 172.26.64.1
```

**Save this IP** - you'll need it for `OBS_BOT_OBS__WEBSOCKET_URL`

### 2. Clone Repository

```bash
cd ~
git clone https://github.com/TortoiseWolfe/OBS_MCP_bot.git
cd OBS_MCP_bot
```

### 3. Create Content Directory

```bash
mkdir -p content
cd content

# Download Big Buck Bunny for testing
wget -O BigBuckBunny.mp4 \
  "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

cd ..
```

### 4. Create Environment File

Create `.env` in the project root:

```bash
cat > .env <<'EOF'
# OBS WebSocket Connection (WSL2 → Windows)
# CRITICAL: Use Windows host IP from step 1, NOT localhost!
OBS_BOT_OBS__WEBSOCKET_URL=ws://172.26.64.1:4455
OBS_WEBSOCKET_PASSWORD=

# Twitch Streaming (REQUIRED)
TWITCH_STREAM_KEY=live_123456789_abcdefghijklmnopqrstuvwxyz1234

# Discord Alerts (OPTIONAL - leave empty to disable)
DISCORD_WEBHOOK_URL=
EOF
```

**Important Configuration Notes**:
- `OBS_BOT_OBS__WEBSOCKET_URL`: **MUST** use Windows host IP, not `localhost`
- Double underscore `__` is required for nested config (Pydantic syntax)
- `OBS_WEBSOCKET_PASSWORD`: Leave empty if you didn't set a password in OBS
- `TWITCH_STREAM_KEY`: Get from Twitch dashboard, starts with `live_`

### 5. Start OBS Studio (Windows)

1. Open OBS Studio on Windows
2. Enable WebSocket server:
   - Go to **Tools** → **WebSocket Server Settings**
   - Check **Enable WebSocket server**
   - Port: `4455` (default)
   - Password: Leave empty (or set and update `.env`)
3. **DO NOT** click "Start Streaming" - the bot controls this!

### 6. Build and Run

```bash
# Build Docker image
docker build -t obs-bot .

# Run the orchestrator
docker run --rm --network host --env-file .env \
  -v "$(pwd)/content:/app/content:ro" \
  obs-bot python -m src.main
```

**Expected Output**:
```
{"event": "application_starting", "level": "info", ...}
{"event": "database_connected", "path": "data/obs_bot.db", ...}
{"event": "preflight_validation_starting", ...}
{"event": "obs_connected", "host": "172.26.64.1", "port": 4455, "obs_version": "32.0.1", ...}
{"event": "preflight_check_passed", "check": "obs_connectivity", ...}
{"event": "media_source_created", "file": "//wsl.localhost/Debian/...", ...}
{"event": "streaming_started", ...}
{"event": "application_ready", ...}
```

### 7. Verify Streaming

1. **Check OBS Studio**: "Stop Streaming" button should be visible (not "Start")
2. **Check Twitch**: Go to https://www.twitch.tv/YOUR_CHANNEL
3. **Watch Big Buck Bunny**: Should be playing on your stream

### 8. Stop Streaming

Press `Ctrl+C` in the terminal. The bot will:
1. Switch to "Technical Difficulties" scene
2. Wait 30 seconds
3. Stop streaming gracefully
4. Shut down

---

## Native Linux + Docker

For native Linux (not WSL2), the setup is simpler:

### 1. Install OBS Studio

```bash
# Ubuntu/Debian
sudo add-apt-repository ppa:obsproject/obs-studio
sudo apt update
sudo apt install obs-studio

# Fedora
sudo dnf install obs-studio

# Arch
sudo pacman -S obs-studio
```

### 2. Clone and Setup

```bash
git clone https://github.com/TortoiseWolfe/OBS_MCP_bot.git
cd OBS_MCP_bot
mkdir -p content
```

### 3. Create .env File

```bash
cat > .env <<'EOF'
# OBS WebSocket Connection (localhost for native Linux)
OBS_BOT_OBS__WEBSOCKET_URL=ws://localhost:4455
OBS_WEBSOCKET_PASSWORD=

# Twitch Streaming
TWITCH_STREAM_KEY=live_your_stream_key_here

# Discord Alerts (optional)
DISCORD_WEBHOOK_URL=
EOF
```

### 4. Add Content and Run

```bash
# Add video content
wget -O content/BigBuckBunny.mp4 \
  "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

# Start OBS (enable WebSocket server in settings)
obs &

# Build and run bot
docker build -t obs-bot .
docker run --rm --network host --env-file .env \
  -v "$(pwd)/content:/app/content:ro" \
  obs-bot python -m src.main
```

---

## Configuration

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OBS_BOT_OBS__WEBSOCKET_URL` | Yes | OBS WebSocket URL | `ws://172.26.64.1:4455` (WSL2)<br>`ws://localhost:4455` (Linux) |
| `OBS_WEBSOCKET_PASSWORD` | No | OBS WebSocket password (leave empty if none) | `my_secret_password` |
| `TWITCH_STREAM_KEY` | Yes | Twitch stream key from dashboard | `live_123456789_abc...` |
| `DISCORD_WEBHOOK_URL` | No | Discord webhook for alerts (optional) | `https://discord.com/api/webhooks/...` |

### Advanced Settings (config/settings.yaml)

```yaml
obs:
  connection_timeout_sec: 10
  reconnect_interval_sec: 5
  max_reconnect_attempts: 10

stream:
  resolution: "1920x1080"
  framerate: 60
  bitrate_kbps: 6000
  encoder: "x264"  # or "nvenc" for NVIDIA GPU

content:
  library_path: "/app/content"
  windows_content_path: "//wsl.localhost/Debian/home/turtle_wolfe/repos/OBS_bot/content"
  transition_duration_sec: 2
```

**Critical Path Configuration**:
- `windows_content_path`: **MUST** use forward slashes: `//wsl.localhost/Debian/...`
- **NOT** backslashes: `\\wsl.localhost\Debian\...` (this won't work with OBS Media Source!)

---

## Troubleshooting

### "obs_connectivity: fail"

**Symptoms**: Pre-flight validation fails on OBS connectivity check

**Solutions**:
1. **Verify OBS is running**:
   ```bash
   # Windows: Check Task Manager for obs64.exe
   # Linux: ps aux | grep obs
   ```

2. **Check WebSocket server enabled** in OBS:
   - Tools → WebSocket Server Settings
   - "Enable WebSocket server" should be checked

3. **Test WebSocket connection** (WSL2):
   ```bash
   nc -zv 172.26.64.1 4455  # Should show "succeeded"
   ```

4. **Check firewall**:
   ```bash
   # Windows: Allow port 4455 in Windows Firewall
   # Linux: sudo ufw allow 4455
   ```

5. **Verify correct IP** (WSL2):
   ```bash
   # Get Windows host IP
   ip route show | grep -i default | awk '{ print $3}'
   ```

### "media_source_created" but Black Screen

**Symptoms**: OBS shows "Content Player" source but video is black

**Cause**: Incorrect file path format

**Solution**: Verify `windows_content_path` uses **forward slashes**:
```yaml
# CORRECT:
windows_content_path: "//wsl.localhost/Debian/home/user/repos/OBS_bot/content"

# WRONG (won't work):
windows_content_path: "\\wsl.localhost\Debian\home\user\repos\OBS_bot\content"
```

**Debug Path**:
```bash
# Query OBS to see what path is actually set
docker run --rm --network host --env-file .env obs-bot python3 -c "
from obswebsocket import obsws, requests as obs_requests
import os, json
ws = obsws(host='172.26.64.1', port=4455, password=os.getenv('OBS_WEBSOCKET_PASSWORD', ''))
ws.connect()
response = ws.call(obs_requests.GetInputSettings(inputName='Content Player'))
print(json.dumps(response.getInputSettings(), indent=2))
ws.disconnect()
"
```

### "network_connectivity: fail"

**Symptoms**: Network connectivity check fails despite streaming working

**Solution**: This is a known issue in Docker/WSL2 due to DNS resolution. The check is **disabled** in MVP (line 97 of config/settings.yaml). Actual RTMP streaming works fine.

```yaml
preflight:
  required_checks:
    - obs_connectivity
    - obs_scenes_exist
    - failover_content_exists
    - twitch_credentials_valid
    # - network_connectivity  # Disabled for MVP
```

### "failover_content_available: fail"

**Symptoms**: Pre-flight validation fails on failover content check

**Solution**: Add at least one video file to the `content/` directory:
```bash
mkdir -p content
wget -O content/BigBuckBunny.mp4 \
  "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
```

### "twitch_credentials_configured: fail"

**Symptoms**: Pre-flight validation fails on Twitch credentials

**Solution**: Ensure `TWITCH_STREAM_KEY` is set in `.env`:
```bash
echo $TWITCH_STREAM_KEY  # Should NOT be empty
```

Get your stream key from: https://dashboard.twitch.tv/settings/stream

---

## Monitoring

### Real-time Logs

The bot outputs structured JSON logs. Watch them with:

```bash
# Follow logs (Ctrl+C to stop)
docker run --rm --network host --env-file .env \
  -v "$(pwd)/content:/app/content:ro" \
  obs-bot python -m src.main | jq -R 'fromjson? | select(.event)'
```

**Key Events to Monitor**:
- `preflight_validation_starting` - Beginning validation
- `obs_connected` - OBS WebSocket connection established
- `streaming_started` - Streaming to Twitch initiated
- `application_ready` - Bot fully operational
- `scene_switched` - OBS scene changed
- `content_playing` - Video content started playback

### Health Metrics (Not Yet Implemented)

Health API is planned for User Story 4 (Phase 6). Currently, health metrics are logged but not exposed via REST API.

**Future** (US4 complete):
```bash
# Check current health status
curl http://localhost:8000/health | jq

# Get uptime report
curl http://localhost:8000/health/uptime | jq
```

### Database Inspection

Stream sessions and health metrics are stored in SQLite:

```bash
# Enter the container
docker run -it --rm -v "$(pwd)/data:/app/data" obs-bot bash

# Query database
sqlite3 /app/data/obs_bot.db

# Show stream sessions
SELECT * FROM stream_sessions;

# Show health metrics (last 10)
SELECT * FROM health_metrics ORDER BY timestamp DESC LIMIT 10;
```

---

## Production Deployment

### Docker Compose (Recommended)

Create `docker-compose.yml`:

```yaml
version: "3.8"

services:
  obs-bot:
    build: .
    network_mode: host
    env_file: .env
    volumes:
      - ./content:/app/content:ro
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Run**:
```bash
docker-compose up -d       # Start in background
docker-compose logs -f     # Follow logs
docker-compose down        # Stop gracefully
```

### systemd Service (Linux)

For running without Docker Compose:

```bash
sudo tee /etc/systemd/system/obs-bot.service <<'EOF'
[Unit]
Description=OBS 24/7 Streaming Bot
After=docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=/home/user/OBS_bot
ExecStart=/usr/bin/docker run --rm --network host --env-file .env \
  -v /home/user/OBS_bot/content:/app/content:ro \
  --name obs-bot obs-bot python -m src.main
ExecStop=/usr/bin/docker stop obs-bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable obs-bot
sudo systemctl start obs-bot
sudo systemctl status obs-bot
```

---

## Security Notes

1. **Never commit `.env` file** - Contains sensitive keys
2. **Discord webhook** is optional but recommended for 24/7 monitoring
3. **Health API** (when implemented) is localhost-only by default
4. **OBS WebSocket password** - Consider setting one in production

---

## Testing Owner Live Broadcast Takeover (US2)

The system now supports owner interrupt functionality - you can take over the stream at any time!

### How It Works

The bot continuously monitors OBS for scene changes (polls every 2 seconds). When it detects you've switched to the "Owner Live" scene, it automatically:
1. **Pauses** automated content playback
2. **Creates** an owner session record in the database
3. **Tracks** transition time for metrics
4. **Yields** full control to you

When you switch back to any other scene, it automatically:
1. **Resumes** automated content from where it left off
2. **Finalizes** the owner session with duration
3. **Returns** to normal 24/7 operation

### Testing the Feature

**Prerequisites:**
- Bot is running (streaming to Twitch)
- OBS Studio is open with WebSocket connected

**Steps:**

1. **Watch the automated content** playing:
   ```bash
   # Check logs to see content scheduler running
   docker logs <container-id> --tail 20
   ```
   You should see: `"content_playing"` events

2. **Take over the stream**:
   - In OBS Studio, switch to the "Owner Live" scene
   - Watch the logs for owner interrupt detection:
   ```
   {"event": "owner_going_live_detected", "interrupted_scene": "Automated Content", ...}
   {"event": "content_scheduler_paused", ...}
   {"event": "owner_interrupt_started", "session_id": "...", ...}
   ```

3. **Do your thing**:
   - Stream whatever you want while on "Owner Live" scene
   - The bot won't interfere - content playback is paused
   - Session duration is being tracked in database

4. **Return to automated mode**:
   - Switch to any other scene (e.g., "Automated Content")
   - Watch the logs for owner return detection:
   ```
   {"event": "owner_return_detected", "resumed_scene": "Automated Content", ...}
   {"event": "content_scheduler_resumed", ...}
   {"event": "owner_interrupt_ended", "duration_sec": 120, ...}
   ```

5. **Verify automated content resumed**:
   - Content should continue playing from where it left off
   - Check logs for `"content_playing"` events

### Checking Owner Session Metrics

View your owner interrupt sessions in the database:

```bash
# Enter the container
docker exec -it <container-id> bash

# Query owner sessions
sqlite3 /app/data/obs_bot.db
SELECT
  datetime(start_time) as start,
  datetime(end_time) as end,
  duration_sec,
  content_interrupted,
  transition_time_sec,
  trigger_method
FROM owner_sessions
ORDER BY start_time DESC
LIMIT 5;
```

**Transition Time Compliance:**
- Target: ≤10 seconds (SC-003)
- The system tracks transition times to ensure smooth handoffs
- Query statistics: `SELECT * FROM owner_sessions WHERE transition_time_sec > 10;`

### Expected Behavior

✅ **Normal Operation:**
- Scene change detected within 2 seconds (polling interval)
- Content pauses/resumes seamlessly
- No dead air - smooth transitions
- All sessions logged to database

⚠️ **Edge Cases:**
- If you switch scenes very rapidly (< 2 seconds), some switches may be missed
- If streaming stops during owner session, session is finalized on shutdown
- Database tracks all interrupts for analytics and compliance

---

## Next Steps

- ✅ **Monitor for 7 days** to validate SC-001 (99.9% uptime requirement)
- ✅ **Integration tests complete** (T042-T044, US2 tests)
- ✅ **US2 COMPLETE** (Owner Interrupt Detection)
- ⏳ **Implement US3** (Failover & Recovery)
- ⏳ **Implement US4** (Health Monitoring API)

---

**Last Updated**: 2025-10-21
**MVP Version**: 2.0.0-US2
**Status**: Functional - US1 + US2 Complete - Owner Interrupt Ready
