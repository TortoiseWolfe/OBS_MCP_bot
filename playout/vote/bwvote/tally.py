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
        return h

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

    def net(self, song_id):
        up, down = self.counts(song_id)
        return up - down

    def ranked_all(self, songs):
        """Every take, for the control page: net votes high to low, then fewest down votes, then title A to Z."""
        rows = [(s, *self.counts(s["id"])) for s in songs]
        rows.sort(key=lambda r: (-(r[1] - r[2]), r[2], r[0]["title"].lower()))
        return rows

    def bottom(self, songs):
        """Takes voted to the bottom: enough voters for the votes to count and the weight at its floor (weights.py)."""
        from . import weights
        return [s for s in songs if sum(self.counts(s["id"])) >= weights.MIN_VOTES
                and weights.weight(*self.counts(s["id"])) <= weights.MIN_WEIGHT]

    def viewers(self):
        return len({h for v in self.votes.values() for h in v})

    def state(self):
        return {"salt": self.salt, "started": self.started, "votes": self.votes}

    def export(self, songs, purged=None):
        """The aggregate the hub keeps beside the by-ear votes.json; no viewer data. `purged` ({id: record}, purge.py) keeps
        moved-aside takes in the report, marked "purged": true."""
        out = {"source": "twitch", "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
               "viewers": self.viewers(), "songs": {}}
        for s in songs:
            up, down = self.counts(s["id"])
            out["songs"][s["id"]] = {"title": s["title"], "up": up, "down": down}
            if s.get("song"):  # a factory take also counts toward its song, which is what the factory steers by
                tot = out["songs"].setdefault(s["song"], {"title": s["song"], "up": 0, "down": 0})
                tot["up"] += up
                tot["down"] += down
        for sid, rec in (purged or {}).items():
            up, down = self.counts(sid)
            out["songs"][sid] = {"title": rec.get("title", sid), "up": up, "down": down, "purged": True}
            if rec.get("song"):  # its votes still count toward its song
                tot = out["songs"].setdefault(rec["song"], {"title": rec["song"], "up": 0, "down": 0})
                tot["up"] += up
                tot["down"] += down
        return out

    def report_line(self, songs):
        def fmt(rows, i):
            return ", ".join(f"{r[0]['file'].removesuffix('.mp3').removeprefix('bw-')} {r[i]}" for r in rows) or "none yet"
        return (f"{time.strftime('%-I:%M %p')} | {self.viewers()} voters | top 5 up: {fmt(self.top_up(songs), 1)}"
                f" | top 5 down: {fmt(self.top_down(songs), 2)}")


def append_jsonl(path, row):
    """One line per event, appended; the vote log and the play log."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")


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
