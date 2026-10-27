#!/usr/bin/env python3
"""Push a set's loop file to Twitch with ffmpeg, never showing the stream key.

usage: push.py <set> [--bandwidthtest] [--seconds N] [--ingest URL] [--dry-run]
  Streams out/<set>-loop.mp4 with -stream_loop -1 -re -c copy -t <set length>.
  --bandwidthtest appends ?bandwidthtest=true to the key: Twitch tests the link and the stream stays invisible.
  Without it, the push is refused before Thu 29 Oct 2026 5:57 PM Eastern (the real show must not start early).
  The key is read only here, from ~/.config/afa/secrets/twitch-scripthammer.key; every log line is redacted.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
KEY_FILE = Path("~/.config/afa/secrets/twitch-scripthammer.key").expanduser()
DEFAULT_INGEST = "rtmp://live.twitch.tv/app"
NOT_BEFORE = datetime(2026, 10, 29, 17, 57, tzinfo=ZoneInfo("America/New_York"))
STATS = re.compile(r"frame=\s*(\d+).*?time=(\S+).*?speed=\s*([\d.]+)x")
DROP = re.compile(r"drop=\s*(\d+)")


def redact(text, key):
    text = re.sub(r"rtmps?://[^\s'\"]+", "rtmp://<ingest redacted>", text)
    return text.replace(key, "<key>") if key else text


def build_cmd(loop, seconds, url):
    return ["ffmpeg", "-hide_banner", "-nostdin", "-re", "-stream_loop", "-1", "-i", str(loop),
            "-c", "copy", "-t", str(seconds), "-f", "flv", url]


def real_push_allowed(now=None):
    return (now or datetime.now(ZoneInfo("America/New_York"))) >= NOT_BEFORE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("set"); ap.add_argument("--bandwidthtest", action="store_true")
    ap.add_argument("--seconds", type=int); ap.add_argument("--ingest", default=DEFAULT_INGEST)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(HERE / "sets" / f"{a.set}.json"))
    seconds = a.seconds or cfg["live_minutes"] * 60
    loop = HERE / "out" / f"{a.set}-loop.mp4"
    if not loop.exists():
        sys.exit(f"missing {loop}: run build_loop.py first")
    if a.dry_run:
        print("would run:", " ".join(build_cmd(loop, seconds, f"{a.ingest}/<key>")))
        return
    if not a.bandwidthtest and not real_push_allowed():
        sys.exit("refused: real push before Thu 29 Oct 5:57 PM; use --bandwidthtest")
    key = KEY_FILE.read_text().strip()
    if a.bandwidthtest:
        key += "?bandwidthtest=true"
    cmd = build_cmd(loop, seconds, f"{a.ingest}/{key}")
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} start {a.set} for {seconds}s bandwidthtest={a.bandwidthtest}", flush=True)
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
    buf, last, worst_speed, drops = b"", 0, None, 0
    while True:
        ch = p.stderr.read(1)
        if not ch:
            break
        if ch not in (b"\r", b"\n"):
            buf += ch; continue
        line = redact(buf.decode("utf-8", "replace"), key); buf = b""
        if not line.strip():
            continue
        m, d = STATS.search(line), DROP.search(line)
        if d: drops = max(drops, int(d.group(1)))
        if m:
            sp = float(m.group(3)); worst_speed = sp if worst_speed is None else min(worst_speed, sp)
            if time.time() - last < 30:
                continue
            last = time.time()
        print(f"{datetime.now():%H:%M:%S} {line}", flush=True)
    rc = p.wait()
    print(f"{datetime.now():%H:%M:%S} done rc={rc} slowest_speed={worst_speed} max_drop={drops}", flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()
