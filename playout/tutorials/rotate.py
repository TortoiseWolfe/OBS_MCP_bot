#!/usr/bin/env python3
"""A list-fed sender: plays pre-encoded episode files one after another through ONE long-running ffmpeg, so the stream
never drops between items, and re-reads the list file at every item boundary so a changed list is picked up without a restart.

How it works
  - receiver: one `ffmpeg -re -f mpegts -i pipe:0 -c copy -f flv <out>` that lives for the whole run (-re = real time).
  - for each item a short-lived `ffmpeg -i item.mp4 -c copy -output_ts_offset <t> -f mpegts pipe:1` feeds the pipe. The offset
    is the sum of the lengths so far, so timestamps run on across joins. Nothing is re-encoded: the files are already in the
    air format (constant bitrate, keyframe every 2 s, 30 fps, AAC 48 kHz), so the stream's settings never change.
  - the list file is JSON: {"items": [{"path": "...", "title": "..."}, ...]}. It is read again before every item. The next item
    is the one after the item just played (found by path); if that path is no longer in the list, the run starts over from the
    top of the new list. A list that is missing, broken or empty is ignored and the last good list keeps going.
  - status.json (beside the list unless --status says otherwise) names the item on now, the next one and the run's age.

`--out` is where the receiver publishes. For real airing it is the local relay (rtmp://127.0.0.1:<port>/relay/air), which holds
the stream key itself, so this script never sees a key and no key is on any command line. For proofs it is a file or "null".
This script never reads or prints a stream key.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

CHUNK = 1 << 16
# Every item starts at least 1 s in. The files begin with a negative decode time (B-frames, audio priming); at offset 0 the muxer
# shifts the first item up by that amount and no later one, which leaves a two-frame overlap at every join.
START_OFFSET = 1.0
# A receiver that ends is started again after these waits (seconds). The first start can land before the relay's nginx is up
# (Docker accepts the port, then resets the connection for about half a second), which ended the first go-live on 2 Nov.
RETRY_WAITS = (2, 5, 10, 20, 30, 30)
GOOD_RUN_SECONDS = 30   # a receiver that lived this long was a good run: the failure count starts over


def load_list(path, last_good=None):
    """The list's items as [{'path','title'}], or `last_good` when the file is missing, broken or empty."""
    try:
        data = json.loads(Path(path).read_text())
        items = [it for it in data["items"] if isinstance(it, dict) and it.get("path")]
    except (OSError, ValueError, KeyError, TypeError):
        return last_good or []
    return items or (last_good or [])


def pick_next(items, last_path, exists=os.path.exists):
    """The item after `last_path`. Path no longer listed (or nothing played yet) -> the top of the list. Missing files are skipped."""
    if not items:
        return None
    start = 0
    if last_path is not None:
        paths = [it["path"] for it in items]
        start = (paths.index(last_path) + 1) % len(items) if last_path in paths else 0
    for k in range(len(items)):
        it = items[(start + k) % len(items)]
        if exists(it["path"]):
            return it
    return None


def probe_seconds(path):
    """Container length: the longer of video and audio, so the next item's offset never overlaps this one."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, timeout=60)
    vals = [float(x) for x in r.stdout.replace(",", "\n").split() if x.replace(".", "", 1).isdigit()]
    if not vals:
        raise RuntimeError(f"no duration for {path}")
    return max(vals)


def receiver_cmd(out, fmt="flv", realtime=True):
    base = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "warning", "-stats"] + (["-re"] if realtime else []) + ["-f", "mpegts", "-i", "pipe:0", "-c", "copy"]
    if out == "null":
        return base + ["-f", "null", "-"]
    return base + ["-f", fmt, str(out)]


def feeder_cmd(path, offset):
    return ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(path), "-c", "copy",
            "-output_ts_offset", f"{offset:.3f}", "-muxdelay", "0", "-muxpreload", "0", "-f", "mpegts", "pipe:1"]


def write_status(path, **kw):
    tmp = f"{path}.tmp"
    Path(tmp).write_text(json.dumps(kw, indent=1))
    os.replace(tmp, path)


def start_receiver(cmd, recv_log):
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=recv_log)


def run(list_path, out, fmt="flv", status=None, max_items=None, log=sys.stderr, stop=None, realtime=True,
        receiver_fn=receiver_cmd, retry_waits=RETRY_WAITS):
    """Plays the list into one receiver. A receiver that ends (the relay was not ready, Twitch dropped us) is started again after
    a wait taken from `retry_waits`; the item in hand restarts from its top and the clock offset starts over, because a new
    connection is a new stream. Only a receiver that keeps dying with no good run in between ends the rotation (return 3)."""
    stop = stop or threading.Event()
    status = status or str(Path(list_path).with_name("status.json"))
    recv_log = open(Path(status).with_name("receiver.log"), "ab")
    recv = start_receiver(receiver_fn(out, fmt, realtime), recv_log)
    recv_since, failures = time.time(), 0
    items, last, offset, played, t0 = [], None, START_OFFSET, 0, time.time()
    try:
        while not stop.is_set() and (max_items is None or played < max_items):
            items = load_list(list_path, items)
            item = pick_next(items, last)
            if item is None:
                log.write("no playable item in the list; waiting 10 s\n")
                stop.wait(10)
                continue
            after = pick_next(items, item["path"])
            secs = probe_seconds(item["path"])
            write_status(status, now=item["path"], title=item.get("title"), next=after["path"] if after else None,
                         items=len(items), played=played, offset_seconds=round(offset, 3), run_seconds=round(time.time() - t0))
            feeder = subprocess.Popen(feeder_cmd(item["path"], offset), stdout=subprocess.PIPE)
            receiver_died = False
            while True:
                buf = feeder.stdout.read(CHUNK)
                if not buf:
                    break
                if stop.is_set():
                    feeder.kill()
                    break
                try:
                    recv.stdin.write(buf)
                except (BrokenPipeError, OSError):
                    receiver_died = True
                    feeder.kill()
                    break
            feeder.wait()
            if receiver_died:
                recv.wait(timeout=60)
                failures = 0 if time.time() - recv_since >= GOOD_RUN_SECONDS else failures + 1
                if failures > len(retry_waits):
                    log.write(f"the receiver ended {failures} times in a row; stopping\n")
                    return 3
                wait = retry_waits[failures - 1] if failures else retry_waits[0]
                log.write(f"the receiver ended (exit {recv.returncode}); starting it again in {wait} s\n")
                if stop.wait(wait):
                    break
                recv = start_receiver(receiver_fn(out, fmt, realtime), recv_log)
                recv_since, offset = time.time(), START_OFFSET
                continue                  # the same item again: `last` has not moved
            if feeder.returncode != 0 and not stop.is_set():
                log.write(f"feeder failed on {item['path']}; moving on\n")
            offset += secs
            last, played = item["path"], played + 1
    finally:
        try:
            recv.stdin.close()
        except OSError:
            pass
        try:
            recv.wait(timeout=60)
        except subprocess.TimeoutExpired:
            recv.kill()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("list")
    ap.add_argument("--out", required=True, help='publish address (the local relay), a file path, or "null"')
    ap.add_argument("--format", default="flv")
    ap.add_argument("--status")
    ap.add_argument("--max-items", type=int)
    ap.add_argument("--no-realtime", action="store_true", help="proof runs only: do not pace at 1x (never for airing)")
    a = ap.parse_args(argv)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    return run(a.list, a.out, a.format, a.status, a.max_items, stop=stop, realtime=not a.no_realtime)


if __name__ == "__main__":
    sys.exit(main())
