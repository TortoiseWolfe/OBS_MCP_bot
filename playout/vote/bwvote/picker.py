"""Which take plays next: no take twice until every take has had its turn, liked ones earlier, new ones soon.

A cycle is one pass through the catalog. Inside a cycle each take plays once; the next take is drawn at random with
weight = its vote weight (weights.py: 0.25 to 3, so liked takes tend to come earlier and voted-down ones later) times
NEW_BOOST while it has never been on the air, so a take that just landed is heard within a few songs. At the start of a
cycle a take with a weight under 1 sits that cycle out now and then (weight 0.5: every second cycle); none is dropped for good.
Played takes are remembered in a small file, so a restart carries on the cycle instead of starting over.
"""
import json
import random
from pathlib import Path

from . import weights
from .tally import write_json

NEW_BOOST = 3.0


class Picker:
    def __init__(self, path, rng=None):
        self.path = Path(path)
        try:
            st = json.loads(self.path.read_text())
        except (OSError, ValueError):
            st = {}
        self.cycle = list(st.get("cycle", []))  # ids already played (or sitting out) in this cycle
        self.heard = set(st.get("heard", []))   # every id ever on the air
        self.rest = dict(st.get("rest", {}))    # id -> credit towards its next cycle
        self.last = st.get("last")
        self.rng = rng or random.Random()

    def _save(self):
        write_json(self.path, {"cycle": self.cycle, "heard": sorted(self.heard), "rest": self.rest, "last": self.last})

    def note(self, song):
        """Count a take that was put on the air without a draw (the show opener)."""
        self.cycle.append(song["id"])
        self.heard.add(song["id"])
        self.last = song["id"]
        self._save()

    def _new_cycle(self, songs, w):
        self.cycle = []
        for s in songs:
            c = self.rest.get(s["id"], 0.0) + min(1.0, w[s["id"]])
            if c >= 1.0 - 1e-9:
                self.rest[s["id"]] = c - 1.0
            else:
                self.rest[s["id"]] = c
                self.cycle.append(s["id"])  # sits this cycle out

    def pick(self, songs, tally, now=None):
        w = weights.weights(songs, tally, now)
        left = lambda: [s for s in songs if s["id"] not in self.cycle and s["id"] != self.last]
        pool = left()
        if not pool:
            self._new_cycle(songs, w)
            pool = left() or [s for s in songs if s["id"] != self.last] or songs
        song = self.rng.choices(pool, [w[s["id"]] * (1.0 if s["id"] in self.heard else NEW_BOOST) for s in pool])[0]
        self.note(song)
        return song
