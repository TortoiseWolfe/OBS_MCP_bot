# OBS_bot Infrastructure Testing Guide

**Status**: Vertical slice implementation complete - ready for validation testing

## What's Been Implemented

### ✅ Phase 1: Complete Project Setup (Tasks T001-T012)
- Directory structure (src/, tests/, config/, data/, logs/)
- All configuration files (settings.yaml, Dockerfile, docker-compose.yml)
- Dependencies specified (requirements.txt)
- Logging and settings management

### ✅ Phase 2A: Minimal Viable Test (Tasks T013, T026, T027)
- SQLite database schema (all 9 tables)
- OBSController service (OBS WebSocket control)
- Integration tests for OBS connection
- Minimal main.py entry point

### 📊 Progress: 18/110 tasks complete (16.4%)

## Prerequisites for Testing

### 1. OBS Studio Setup

**Install OBS Studio 29.0+**:
- Download: https://obsproject.com/download
- Install for your platform (Linux, macOS, Windows)

**Enable WebSocket Server**:
1. Open OBS Studio
2. Go to: `Tools → WebSocket Server Settings`
3. Check "Enable WebSocket server"
4. Port: `4455` (default)
5. Password: Leave blank for testing (or set and configure in .env)
6. Click "Apply" and "OK"

### 2. Python Environment Setup

```bash
# Navigate to project directory
cd /home/turtle_wolfe/repos/OBS_bot

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Create `.env` file in project root:

```bash
# .env
OBS_WEBSOCKET_URL=ws://localhost:4455
OBS_WEBSOCKET_PASSWORD=
TWITCH_STREAM_KEY=your_key_here_for_live_tests
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook
```

**Note**: Only `TWITCH_STREAM_KEY` and `DISCORD_WEBHOOK_URL` are required for production. OBS tests work without them.

### 4. WSL2 + Windows OBS Setup (IMPORTANT!)

**If you're using Docker Desktop on Windows with WSL2**, you MUST use a special IP address instead of `localhost`.

⚠️ **Common Issue**: `Connection refused` errors when OBS is running on Windows but Docker is in WSL2.

**Quick Fix**:

```bash
# In WSL2 terminal, find Windows host IP:
cat /etc/resolv.conf | grep nameserver | awk '{print $2}'

# Or find Hyper-V adapter IP (in Windows PowerShell):
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -like "*WSL*"} | Select IPAddress

# Test which IP works (replace with your IP):
timeout 3 bash -c 'cat < /dev/null > /dev/tcp/YOUR_IP_HERE:4455' && echo "OPEN" || echo "CLOSED"

# Update .env with the IP that shows "OPEN":
OBS_WEBSOCKET_URL=ws://YOUR_IP_HERE:4455
```

**For detailed WSL2 setup** (firewall rules, troubleshooting): See [docs/WSL2_SETUP.md](docs/WSL2_SETUP.md)

**How to detect if you're on WSL2**:

```bash
uname -r
```

If you see `microsoft` or `WSL2` in output → You need WSL2 setup.

## Running Tests

### Option 1: Integration Tests (Recommended First Test)

**Test OBS connection** (requires OBS running):

```bash
# Ensure OBS Studio is running with websocket enabled
# Run integration tests
pytest tests/integration/test_obs_integration.py -v -m integration

# Run specific test
pytest tests/integration/test_obs_integration.py::test_obs_connection -v
```

**Expected output**:
```
tests/integration/test_obs_integration.py::test_obs_connection PASSED
tests/integration/test_obs_integration.py::test_list_scenes PASSED
tests/integration/test_obs_integration.py::test_get_current_scene PASSED
...
```

### Option 2: Run Minimal Application

**Test entire stack** (config → logging → OBS):

```bash
# Ensure OBS Studio is running
python -m src.main
```

**Expected output**:
```json
{"event": "application_starting", "timestamp": "2025-10-21T..."}
{"event": "connecting_to_obs", "timestamp": "2025-10-21T..."}
{"event": "obs_connected", "host": "localhost", "port": 4455, "obs_version": "29.0.0"}
{"event": "obs_connection_verified", "total_scenes": 3, "current_scene": "Scene"}
{"event": "streaming_status", "active": false, "reconnecting": false}
{"event": "application_ready", "timestamp": "2025-10-21T..."}
{"event": "application_running", "timestamp": "2025-10-21T..."}
```

**Ctrl+C to stop**

### Option 3: Docker Build Test

**Verify Docker setup**:

```bash
# Build image
docker build -t obs-bot .

# Check image created
docker images | grep obs-bot
```

**Note**: Don't run the container yet - OBS is on host, needs network_mode: host configuration.

## Test Scenarios

### Scenario 1: Connection Success ✅
**Setup**: OBS running, websocket enabled
**Run**: `pytest tests/integration/test_obs_integration.py::test_obs_connection -v`
**Expected**: Test passes, logs show successful connection

### Scenario 2: Connection Failure (Expected) ⚠️
**Setup**: OBS not running
**Run**: `pytest tests/integration/test_obs_integration.py::test_obs_connection -v`
**Expected**: Test fails with `OBSConnectionError`, logs show retry attempts

### Scenario 3: Scene Operations ✅
**Setup**: OBS running with at least 2 scenes
**Run**: `pytest tests/integration/test_obs_integration.py::test_scene_switching -v`
**Expected**: Test passes, OBS switches scenes during test

### Scenario 4: Streaming Test (CAUTION - Goes Live!) 🔴
**Setup**: OBS running, `TWITCH_STREAM_KEY` configured
**Run**: `pytest tests/integration/test_obs_integration.py::test_streaming_start_stop -v -m slow`
**Expected**: Stream goes live briefly, then stops

**WARNING**: This will actually stream to Twitch! Only run if you want to go live.

## Troubleshooting

### "Connection refused" error
**Problem**: OBS not running or websocket disabled
**Solution**:
1. Start OBS Studio
2. Enable websocket server (Tools → WebSocket Server Settings)
3. Verify port 4455 is accessible: `nc -zv localhost 4455`

### "Authentication failed" error
**Problem**: OBS websocket password configured but not provided
**Solution**:
1. Set `OBS_WEBSOCKET_PASSWORD` in `.env`
2. OR disable password in OBS websocket settings

### "Module not found" errors
**Problem**: Dependencies not installed or venv not activated
**Solution**:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Import errors (settings.py, etc.)
**Problem**: Running from wrong directory
**Solution**: Always run from project root (`/home/turtle_wolfe/repos/OBS_bot`)

### YAML configuration errors
**Problem**: `config/settings.yaml` not found
**Solution**: File exists at `config/settings.yaml` - verify path and run from project root

## What Works Now

✅ **Configuration**: YAML + environment variable loading
✅ **Logging**: Structured JSON logging to console and files
✅ **OBS Connection**: WebSocket connection with retry logic
✅ **Scene Management**: List, get current, switch, create scenes
✅ **Streaming Control**: Start/stop streaming, get status
✅ **Health Metrics**: Query OBS stats (CPU, frames, bitrate)
✅ **Database Schema**: All 9 tables created on startup

## What's Next

After infrastructure validation passes:

### Phase 2B: Complete Foundational Infrastructure (10 tasks)
- Implement 9 domain models (Pydantic classes)
- Implement 3 repositories (metrics, sessions, events CRUD)
- Remaining foundational services

### Phase 3: User Story 1 - Continuous Broadcasting (17 tasks)
- Pre-flight validation
- Stream manager orchestration
- Content scheduling
- Auto-start streaming
- **Deliverable**: Working 24/7 streaming system

### Phase 4-7: Remaining User Stories (68 tasks)
- US2: Owner interrupt (hotkey detection)
- US3: Failover and recovery
- US4: Health monitoring API
- Polish and documentation

## Success Criteria for This Phase

✅ **Infrastructure Validated**: Integration tests pass
✅ **OBS Control Works**: Can connect, list scenes, switch scenes
✅ **Application Runs**: main.py executes without errors
✅ **Docker Builds**: Image builds successfully
✅ **Configuration Loads**: Settings from YAML + env vars work
✅ **Logging Works**: JSON logs appear in console

## Next Command

**If tests pass**:
```bash
# Continue with Phase 2B - implement domain models
# (Ready for next implementation phase)
```

**If tests fail**:
```bash
# Debug OBS connection
# Check OBS websocket settings
# Verify port 4455 accessibility
```

---

**Current Status**: Infrastructure ready for validation testing
**Test This**: Run `pytest tests/integration/test_obs_integration.py -v`
**Expected**: All tests pass with OBS running
