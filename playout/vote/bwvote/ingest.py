"""Where ffmpeg pushes to. The key is read here and nowhere else, and never printed."""
import glob
import json
import os
import re
from pathlib import Path

DEFAULT_SERVER = "rtmp://live.twitch.tv/app"
SERVICE_GLOB = "/mnt/c/Users/*/AppData/Roaming/obs-studio/basic/profiles/TSD_with_Jon/service.json"


def service_path():
    env = os.environ.get("BWV_SERVICE_JSON")
    if env:
        return Path(env).expanduser()
    hits = glob.glob(SERVICE_GLOB)
    return Path(hits[0]) if hits else None


def load(bandwidthtest=False, key_file=None):
    """(ingest url with key, key). The key comes from key_file when given (a file holding just the key, as
    push.py uses for ScriptHammer), else from the OBS profile named above."""
    if key_file:
        key, server = Path(key_file).expanduser().read_text().strip(), DEFAULT_SERVER
        if not key:
            raise SystemExit("the key file is empty")
    else:
        p = service_path()
        if not p or not p.exists():
            raise SystemExit("no OBS service file found (set BWV_SERVICE_JSON)")
        s = json.loads(p.read_text()).get("settings", {})
        key = s.get("key", "")
        if not key:
            raise SystemExit("the OBS profile holds no stream key")
        server = s.get("server") or DEFAULT_SERVER
        if "twitch.tv" not in server:
            server = DEFAULT_SERVER  # "auto" and the like
    server = server.rstrip("/")
    secret = key + ("?bandwidthtest=true" if bandwidthtest else "")
    return f"{server}/{secret}", key


def redact(text, key):
    """Hide the key and the ingest address in anything that reaches a log (shared with push.py)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import push
    return push.redact(text, key)
