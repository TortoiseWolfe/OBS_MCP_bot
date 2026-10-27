"""Per-song up/down votes. A viewer is stored only as a salted hash, never a name."""
import hashlib
import json
import secrets
import time
from pathlib import Path


def parse_command(text):
    """'!up' or '!down' (any case, extra words allowed) -> 'up' / 'down'; anything else -> None."""
    parts = text.strip().lower().split()
    if parts and parts[0] in ("!up", "!down") and len(text) <= 200:
        return parts[0][1:]
    return None


class Tally:
    def __init__(self, state=None):
        state = state or {}
        self.salt = state.get("salt") or secrets.token_hex(8)
        self.votes = state.get("votes", {})  # song id -> {voter hash: "up" | "down"}
        self.started = state.get("started") or time.strftime("%Y-%m-%d %H:%M:%S")

    def vote(self, song_id, viewer, value):
        h = hashlib.sha256((self.salt + viewer.lower()).encode()).hexdigest()[:16]
        self.votes.setdefault(song_id, {})[h] = value  # a viewer's latest vote on a song is the one that counts

    def counts(self, song_id):
        v = self.votes.get(song_id, {}).values()
        up = sum(x == "up" for x in v)
        return up, len(v) - up

    def ranked(self, songs, key, n=5):
        rows = [(s, *self.counts(s["id"])) for s in songs]
        rows = [r for r in rows if r[1] + r[2]]
        rows.sort(key=key, reverse=True)
        return rows[:n]

    def top_up(self, songs, n=5):
        return self.ranked(songs, lambda r: (r[1], r[1] - r[2]), n)

    def top_down(self, songs, n=5):
        return self.ranked(songs, lambda r: (r[2], r[2] - r[1]), n)

    def top_net(self, songs, n=3):
        return self.ranked(songs, lambda r: (r[1] - r[2], r[1]), n)

    def viewers(self):
        return len({h for v in self.votes.values() for h in v})

    def state(self):
        return {"salt": self.salt, "started": self.started, "votes": self.votes}

    def export(self, songs):
        """The aggregate the hub keeps beside the by-ear votes.json; no viewer data."""
        out = {"source": "twitch", "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
               "viewers": self.viewers(), "songs": {}}
        for s in songs:
            up, down = self.counts(s["id"])
            out["songs"][s["id"]] = {"title": s["title"], "up": up, "down": down}
        return out

    def report_line(self, songs):
        def fmt(rows, i):
            return ", ".join(f"{r[0]['file'][3:-4]} {r[i]}" for r in rows) or "none yet"
        return (f"{time.strftime('%-I:%M %p')} | {self.viewers()} voters | top 5 up: {fmt(self.top_up(songs), 1)}"
                f" | top 5 down: {fmt(self.top_down(songs), 2)}")


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def load_state(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
