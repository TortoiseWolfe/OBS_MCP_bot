"""The take catalog: the songs in playlist.json plus takes-catalog.json, which the takes lane writes as new takes land.

takes-catalog.json is {"takes": [{"file": "bw-lore-1.mp3", "title": "Nell at Millrace Landing", "group": "lore"}, ...]}
(a bare list works too). Optional per take: "feature" (see weights.py) and "hold": true to keep a take off the air.
It is read again at every song change, so a take that lands is on the air within a song or two, no restart.
A catalog take is offered only once its file has stopped changing (a copy still in progress would play as a cut-off song).
"""
import json
import time
from pathlib import Path

from . import playlist

SETTLE_S = 15      # a file younger than this may still be being written
MIN_SECONDS = 5.0  # shorter than this is not a song
_probed = {}       # (path, mtime) -> seconds, so each new file is probed once


def _entries(path):
    try:
        raw = json.loads(Path(path).expanduser().read_text())
    except (OSError, ValueError):
        return []
    raw = raw.get("takes", []) if isinstance(raw, dict) else raw
    return [e for e in raw if isinstance(e, dict) and e.get("file") and not e.get("hold")]


def _title(entry):
    return entry.get("title") or "Take " + Path(entry["file"]).stem.removeprefix("bw-")


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
    songs = [s for s in cfg["songs"] if s["path"].is_file()]
    seen = {s["id"] for s in cfg["songs"]}
    base = Path(cfg["audio_dir"]).expanduser()
    for e in _entries(cfg.get("catalog", "")):
        sid = cfg["audio_prefix"] + e["file"]
        if sid in seen:
            continue
        seen.add(sid)
        path = base / e["file"]
        if _playable(path, now, probe):
            songs.append(dict(e, id=sid, path=path, title=_title(e)))
    return songs
