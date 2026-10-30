"""Viewer count, logged once a minute so each play in plays.jsonl can be joined to its audience by the shared clock.

Reads decapi.me's public viewer count (no login, no key); Twitch's own streams endpoint needs an app secret, which
this process never holds. An offline channel or a failed read logs viewers null.
"""
import time
import urllib.request

from .tally import append_jsonl

EVERY = 60


def fetch(channel, timeout=15):
    """The viewer count as an int, or None when decapi gives anything else (offline text, an error, no answer)."""
    try:
        req = urllib.request.Request(f"https://decapi.me/twitch/viewercount/{channel}", headers={"User-Agent": "band-wagon-vote"})
        text = urllib.request.urlopen(req, timeout=timeout).read().decode().strip()
        return int(text) if text.isdigit() else None
    except Exception:
        return None


def row(channel, viewers, now):
    return {"epoch": round(now, 2), "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)), "channel": channel, "viewers": viewers}


def run(channel, path, stop, every=EVERY, get=fetch):
    """Append one row every `every` seconds until `stop` (a threading.Event) is set."""
    while not stop.is_set():
        append_jsonl(path, row(channel, get(channel), time.time()))
        stop.wait(every)
