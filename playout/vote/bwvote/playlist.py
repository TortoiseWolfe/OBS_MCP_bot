"""The song list, how long each song is, and which song is playing at a given moment."""
import json
import subprocess
from bisect import bisect_right
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPEATS = 40  # times the list is written into the audio playlist file (about 50 hours)


def load(path=HERE / "playlist.json"):
    cfg = json.loads(Path(path).read_text())
    base = Path(cfg["audio_dir"]).expanduser()
    for s in cfg["songs"]:
        s["id"] = cfg["audio_prefix"] + s["file"]
        s["path"] = base / s["file"]
    return cfg


def full_songs(songs):
    """Every song in the list at full length, the 7-minute jam takes included. The 30 to 60 second Shorts cuts
    in clips/ are for YouTube and never play on the stream."""
    return [dict(s, kind="song") for s in songs]


def probe_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60, check=True)
    return float(out.stdout.strip())


def with_durations(songs, probe=probe_seconds):
    for s in songs:
        s["seconds"] = probe(s["path"])
    return songs


def opener_source(cfg):
    """The full-length song that opens the show (played once, at the first start), or None."""
    o = cfg.get("opener")
    if not o:
        return None
    song = next(x for x in cfg["songs"] if x["file"] == o["file"])
    return dict(song, kind="opener", opener=True, label=o.get("label", ""))


class Timeline:
    """Maps seconds since the stream started to (song index, seconds into that song).

    `lead` is played once before the loop (the show opener); `at` indexes lead first, then the loop.
    """

    def __init__(self, songs, lead=None):
        self.lead = lead or []
        self.songs = self.lead + songs
        self.starts, t = [], 0.0
        for s in self.songs:
            self.starts.append(t)
            t += s["seconds"]
        self.lead_length = self.starts[len(self.lead)] if self.lead else 0.0
        self.length = t - self.lead_length  # the loop only

    def at(self, position):
        if position < self.lead_length:
            i = bisect_right(self.starts, position) - 1
            return i, position - self.starts[i]
        pos = (position - self.lead_length) % self.length + self.lead_length
        i = bisect_right(self.starts, pos) - 1
        return i, pos - self.starts[i]

    def song_at(self, position):
        return self.songs[self.at(position)[0]]

    def next_song(self, position):
        i = self.at(position)[0]
        n = len(self.lead)
        return self.songs[i + 1] if i + 1 < len(self.songs) else self.songs[n]


def concat_list(songs, repeats=REPEATS, lead=None):
    lines = []
    for s in (lead or []):
        lines.append("file '%s'" % str(s["path"]).replace("'", "'\\''"))
    for _ in range(repeats):
        for s in songs:
            lines.append("file '%s'" % str(s["path"]).replace("'", "'\\''"))
    return "\n".join(lines) + "\n"
