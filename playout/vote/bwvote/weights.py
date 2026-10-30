"""Weights from the chat votes: liked takes are drawn earlier in a cycle, voted-down takes later and sometimes rest a cycle (picker.py).

A song needs MIN_VOTES distinct voters before its votes count (one stray vote must not move it). Its weight is
1 + 0.5 x (up - down), kept between MIN_WEIGHT and MAX_WEIGHT. Nothing is ever dropped for good.
"""
from datetime import datetime, timezone

MIN_VOTES = 2
MIN_WEIGHT, MAX_WEIGHT = 0.25, 3.0


def weight(up, down):
    if up + down < MIN_VOTES:
        return 1.0
    return max(MIN_WEIGHT, min(MAX_WEIGHT, 1.0 + 0.5 * (up - down)))


def featured_floor(song, now=None):
    """A featured song ({"feature": {"weight": 2, "until": "2026-10-29T12:00:00-04:00"}} in playlist.json) is due at
    least that many times a round until the time given, so new songs get heard whatever the first votes say."""
    f = song.get("feature")
    if not f:
        return 0.0
    now = now or datetime.now(timezone.utc)
    return float(f["weight"]) if now < datetime.fromisoformat(f["until"]) else 0.0


def weights(songs, tally, now=None):
    return {s["id"]: max(weight(*tally.counts(s["id"])), featured_floor(s, now)) for s in songs}
