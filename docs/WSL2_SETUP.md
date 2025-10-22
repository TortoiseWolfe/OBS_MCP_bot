# WSL2 + Windows OBS Setup Guide

**Target Audience**: Developers running Docker Desktop on Windows with WSL2 backend, connecting to OBS Studio running on Windows.

This is the **most common development scenario** and requires special network configuration due to WSL2's virtualized network stack.

---

## Quick Diagnostic: Are You On WSL2?

Run this in your terminal:

```bash
uname -r
```

**If you see** `microsoft` or `WSL2` in the output → You're on WSL2, follow this guide
**If you don't see** `microsoft` → You're on native Linux, use `localhost` and skip this guide

---

## The Problem

WSL2 uses a virtualized network with **Hyper-V**. When you use `ws://localhost:4455` from WSL2:
- ❌ It tries to connect to port 4455 **inside the WSL2 instance**
- ❌ OBS is running on **Windows**, not inside WSL2
- ❌ `localhost` doesn't reach Windows from WSL2

**Solution**: Use the **Hyper-V virtual adapter IP** instead of localhost.

---

## Step-by-Step Setup

### Step 1: Enable OBS WebSocket Server (Windows)

1. **Open OBS Studio** on Windows
2. Click **Tools** → **WebSocket Server Settings**
3. Check **☑ Enable WebSocket server**
4. **Port**: `4455` (default, don't change)
5. Check **☑ Enable Authentication**
6. **Password**: Set a secure password (you'll need this later)
7. Click **Apply**, then **OK**
8. **Keep OBS running** (don't close it)

**Verify OBS is listening** (in Windows PowerShell):

```powershell
netstat -ano | findstr :4455
```

**Expected output**:
```
TCP    0.0.0.0:4455    0.0.0.0:0    LISTENING    [PID]
TCP    [::]:4455       [::]:0       LISTENING    [PID]
```

**If you see nothing**: OBS WebSocket didn't start. Try restarting OBS.

---

### Step 2: Find Windows IP Addresses (WSL2 Terminal)

WSL2 can reach Windows via **two different IP addresses**:

#### Option A: Nameserver IP (sometimes works)

```bash
cat /etc/resolv.conf | grep nameserver | awk '{print $2}'
```

**Example output**: `10.255.255.254`

#### Option B: Hyper-V Adapter IP (more reliable)

**In Windows PowerShell**:

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -like "*WSL*"} | Format-Table InterfaceAlias, IPAddress
```

**Example output**:
```
InterfaceAlias                     IPAddress
--------------                     ---------
vEthernet (WSL (Hyper-V firewall)) 172.x.x.1
```

**Write down both IPs** - we'll test which one works in Step 3.

---

### Step 3: Test Port Connectivity (WSL2 Terminal)

Test **each IP address** you found:

```bash
# Test nameserver IP (replace with your IP from Step 2)
timeout 3 bash -c 'cat < /dev/null > /dev/tcp/10.255.255.254/4455' && echo "✅ Port 4455 is OPEN" || echo "❌ Port 4455 is CLOSED"

# Test Hyper-V adapter IP (replace with your IP from Step 2)
timeout 3 bash -c 'cat < /dev/null > /dev/tcp/172.x.x.1/4455' && echo "✅ Port 4455 is OPEN" || echo "❌ Port 4455 is CLOSED"
```

**Expected Results**:
- **"Port 4455 is OPEN"** ✅ → This IP works! Use it in your `.env`
- **"Port 4455 is CLOSED"** ❌ → This IP blocked, try the other one or check firewall (Step 4)

**In our testing**: The **Hyper-V adapter IP** (`172.x.x.1`) is usually the one that works.

---

### Step 4: Configure Windows Firewall (If Port is CLOSED)

If **both IPs show CLOSED**, Windows Firewall is blocking the connection.

#### Option A: PowerShell (Recommended)

**Open PowerShell as Administrator**, then run:

```powershell
New-NetFirewallRule -DisplayName "OBS WebSocket WSL2" -Direction Inbound -Protocol TCP -LocalPort 4455 -Action Allow
```

**Verify rule was created**:

```powershell
Get-NetFirewallRule -DisplayName "*OBS*" | Format-Table DisplayName, Enabled, Direction, Action
```

**Expected**:
```
DisplayName        Enabled Direction Action
-----------        ------- --------- ------
OBS WebSocket WSL2    True   Inbound  Allow
```

#### Option B: Windows Firewall GUI

1. Press `Win + R`, type: `wf.msc`, press Enter
2. Click **"Inbound Rules"** (left panel)
3. Click **"New Rule..."** (right panel)
4. Select **"Port"** → Next
5. Select **"TCP"**, Specific local ports: **4455** → Next
6. Select **"Allow the connection"** → Next
7. Check **all three** boxes (Domain, Private, Public) → Next
8. Name: **"OBS WebSocket WSL2"** → Finish

#### Re-test After Creating Firewall Rule

```bash
timeout 3 bash -c 'cat < /dev/null > /dev/tcp/YOUR_IP_HERE/4455' && echo "✅ Port 4455 is OPEN" || echo "❌ Port 4455 is CLOSED"
```

Should now show **"✅ Port 4455 is OPEN"**.

---

### Step 5: Update .env Configuration (WSL2 Terminal)

```bash
# Navigate to project directory
cd /home/YOUR_USERNAME/repos/OBS_bot

# Copy example .env
cp .env.example .env

# Edit .env
nano .env  # or vi .env
```

**Update these two lines** with your values:

```bash
# Use the IP that showed "OPEN" in Step 3 (usually Hyper-V adapter IP)
OBS_WEBSOCKET_URL=ws://172.x.x.1:4455

# Use the password you set in Step 1
OBS_WEBSOCKET_PASSWORD=your_password_here
```

**Save and exit** (`Ctrl+X`, `Y`, Enter in nano)

---

### Step 6: Test the Connection

```bash
docker run --rm --network host --env-file .env obs-bot pytest tests/integration/test_obs_integration.py::test_obs_connection -v
```

**Expected output**:
```
tests/integration/test_obs_integration.py::test_obs_connection PASSED [100%]
```

**If test passes** ✅ → Setup complete! You can now develop with OBS.

**If test fails** ❌ → See Troubleshooting section below.

---

## Troubleshooting

### Problem: "Connection refused"

**Symptoms**:
```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Diagnosis**:
1. **OBS not running**: Start OBS Studio on Windows
2. **WebSocket not enabled**: Go to Tools → WebSocket Server Settings → Enable
3. **Wrong IP address**: Try the other IP from Step 2
4. **Port test fails**: Re-run Step 3 to confirm port connectivity

### Problem: Test hangs/freezes

**Symptoms**: Test runs forever, no output

**Diagnosis**: Windows Firewall is **timing out** (not refusing) the connection.

**Fix**: Create firewall rule (Step 4), then press `Ctrl+C` and re-run test.

### Problem: "Authentication failed"

**Symptoms**:
```
obswebsocket.exceptions.AuthenticationFailure
```

**Diagnosis**: Password mismatch between `.env` and OBS settings

**Fix**:
1. Check OBS password: Tools → WebSocket Server Settings
2. Update `.env` with matching password
3. Ensure no extra spaces or quotes in `.env`

### Problem: Hyper-V adapter IP keeps changing

**Symptoms**: Connection works, then breaks after Windows restart

**Diagnosis**: Hyper-V assigns IPs dynamically (can change on reboot)

**Workaround**: After each Windows restart, re-run Step 2 to get current IP, update `.env`

**Better Solution**: Use a startup script to auto-detect IP:

```bash
# In WSL2, before running Docker
export WINDOWS_HOST=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}')
echo "OBS_WEBSOCKET_URL=ws://${WINDOWS_HOST}:4455" > .env
# ... then add password and other vars
```

### Problem: Works from WSL2 but not from Docker container

**Symptoms**: Manual test works, Docker test fails

**Diagnosis**: Docker networking misconfiguration

**Fix**: Ensure using `--network host` in docker run:

```bash
docker run --rm --network host --env-file .env obs-bot [command]
```

### Advanced: Check All Network Interfaces

**WSL2 terminal**:

```bash
ip addr show
```

**Windows PowerShell**:

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias, IPAddress, PrefixLength
```

Look for interfaces containing "WSL" or "Hyper-V" and test those IPs.

---

## Network Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│ Windows Host                                            │
│                                                         │
│  ┌──────────────────┐                                   │
│  │  OBS Studio      │                                   │
│  │  Port: 4455      │◄──────────────┐                   │
│  └──────────────────┘                │                  │
│                                      │                  │
│  Network Adapters:                   │                  │
│  ┌─────────────────────────────┐     │                  │
│  │ Ethernet: 192.168.2.2       │     │                  │
│  │ (Physical network)          │     │                  │
│  └─────────────────────────────┘     │                  │
│                                      │                  │
│  ┌─────────────────────────────┐     │                  │
│  │ vEthernet (WSL):            │     │                  │
│  │ 172.x.x.1 ◄─────────────────┴─────┼──────┐           │
│  │ (Hyper-V virtual adapter)   │           │           │
│  └─────────────────────────────┘           │           │
│          ▲                                 │           │
└──────────┼─────────────────────────────────┼───────────┘
           │ Hyper-V Bridge                  │
           │                                 │
       ┌───┴────────────────────────────┐    │
       │ WSL2 Instance (Ubuntu)          │    │
       │                                 │    │
       │  Docker containers              │    │
       │  ┌──────────────────────┐       │    │
       │  │ obs-bot container    ├───────┘    │
       │  │ (--network host)     │            │
       │  └──────────────────────┘            │
       │                                      │
       │  IP: 172.26.64.x (dynamic)           │
       └──────────────────────────────────────┘
```

**Key Points**:
- ❌ `localhost` in WSL2 → stays in WSL2 (doesn't reach Windows)
- ✅ `172.x.x.1` → Hyper-V bridge → Windows OBS
- ⚠️  Hyper-V adapter IP can change between Windows reboots

---

## Summary Checklist

- [ ] OBS running on Windows
- [ ] WebSocket enabled (Port 4455, with password)
- [ ] Found Hyper-V adapter IP: `172.x.x.1`
- [ ] Port test shows "OPEN"
- [ ] Windows Firewall rule created
- [ ] `.env` configured with correct IP and password
- [ ] Integration test passes

**Once all checked** ✅ → You're ready to develop!

---

## See Also

- [TESTING.md](../TESTING.md) - Full testing guide
- [README.md](../README.md) - Project overview
- [OBS WebSocket Documentation](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md)
