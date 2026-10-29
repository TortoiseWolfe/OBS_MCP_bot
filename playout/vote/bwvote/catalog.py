"""The take catalog: the songs in playlist.json plus the take factory's own catalog, read as the factory writes it.

The factory (beatboard/tools/factory/take_factory.py) keeps a JSON list at <band-wagon audio>/takes/catalog.json, one entry per
finished take: {"song": "story-1", "take": "story-1-t3", "take_n": 3, "style": "...", "seed": 12345, "bpm": 76, "seconds": 215.0,
"path": "/abs/path/story-1-t3.mp3", "kind": "story", ...}. Its songs.json beside it names each song ({"id", "title", ...}).
A take is titled "<song title>, take 3", or by its own "title" when the entry has one. Optional on an entry: "hold": true keeps it off the air.
Ids listed in cfg["purged_file"] (bwvote/purge.py) are left out too.
The file is read again at every song change, so a take that lands is on the air within a song or two, no restart.
A take is offered only once its file has stopped changing (a copy still in progress would play as a cut-off song).
"""
import json
import time
from pathlib import Path

from . import playlist, purge

SETTLE_S = 15      # a file younger than this may still be being written
MIN_SECONDS = 5.0  # shorter than this is not a song
_probed = {}       # (path, mtime) -> seconds, so each new file is probed once


def _read(path):
    try:
        return json.loads(Path(path).expanduser().read_text())
    except (OSError, ValueError):
        return None


def _entries(path):
    raw = _read(path)
    if not isinstance(raw, list):
        return []
    return [e for e in raw if isinstance(e, dict) and e.get("take") and e.get("path") and not e.get("hold")]


def _titles(catalog_path):
    songs = _read(Path(catalog_path).expanduser().with_name("songs.json"))
    return {s["id"]: s.get("title") for s in songs if isinstance(s, dict) and s.get("id")} if isinstance(songs, list) else {}


def _title(entry, titles):
    if entry.get("title"):  # a master with its own name (the album tracks) is titled as named
        return entry["title"]
    song = entry.get("song") or ""
    name = titles.get(song) or song.replace("-", " ").title() or "Take"
    suffix = entry["take"][len(song) + 1:] if entry["take"].startswith(song + "-") else entry["take"]
    return f"{name}, take {suffix.removeprefix('t')}"


def _playable(path, now, probe):
    try:
        st = path.stat()
    except OSError:
        return False
    if st.st_size == 0 or now - st.st_mtime < SETTLE_S:
        return False
    key = (str(path), st.st_mtime)
    if key not in _probed:
        try:
            _probed[key] = probe(path)
        except Exception:
            return False  # not readable yet; tried again at the next pick
    return _probed[key] >= MIN_SECONDS


def load(cfg, now=None, probe=playlist.probe_seconds):
    """Every take that can go on the air now, playlist.json's first. Each has id, path, title, group and file."""
    now = now or time.time()
    aside = set(purge.load(cfg))  # moved aside from the control page or run.py purge: never offered
    songs = [s for s in cfg["songs"] if s["path"].is_file() and s["id"] not in aside]
    seen = {s["id"] for s in cfg["songs"]} | aside
    catalog_path = cfg.get("catalog", "")
    titles = _titles(catalog_path) if catalog_path else {}
    for e in _entries(catalog_path):
        sid = cfg["audio_prefix"] + "takes/" + e["take"]
        if sid in seen:
            continue
        seen.add(sid)
        path = Path(e["path"]).expanduser()
        if _playable(path, now, probe):
            songs.append(dict(e, id=sid, path=path, file=path.name, title=_title(e, titles), group=e.get("kind", "take")))
    return songs
