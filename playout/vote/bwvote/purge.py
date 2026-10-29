"""Move a take aside (never delete it) and bring it back.

STATE/purged.json holds {song id: {"at", "reason", "title", "song", "from", "moved_to"}}. catalog.load leaves every id in it out of the
draw, read again at each song change, so a purge takes effect within a song or two with no restart. The factory's catalog.json is
never edited. The file moves to a _purged folder beside it; restore moves it back and drops the record. Votes stay on record.
"""
import json
import shutil
import time
from pathlib import Path

from .tally import write_json


def load(cfg):
    path = cfg.get("purged_file")
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def purge(cfg, song, reason=""):
    """Move song['path'] into a _purged folder beside it. Returns the record. Raises ValueError if it cannot."""
    records = load(cfg)
    if song["id"] in records:
        raise ValueError("already moved aside")
    src = Path(song["path"])
    if not src.is_file():
        raise ValueError(f"file not found: {src.name}")
    dest_dir = src.parent / "_purged"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        dest = dest_dir / f"{src.name}.{int(time.time())}"
    shutil.move(str(src), str(dest))
    records[song["id"]] = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "reason": reason[:200], "title": song.get("title", song["id"]),
                           "song": song.get("song"), "from": str(src), "moved_to": str(dest)}
    write_json(cfg["purged_file"], records)
    return records[song["id"]]


def restore(cfg, song_id):
    """Move the file back where it came from and drop the record. Raises ValueError if it cannot."""
    records = load(cfg)
    rec = records.get(song_id)
    if not rec:
        raise ValueError("not moved aside")
    src, dest = Path(rec["moved_to"]), Path(rec["from"])
    if not src.is_file():
        raise ValueError(f"file not found in _purged: {src.name}")
    if dest.exists():
        raise ValueError(f"{dest.name} already exists at the original place")
    shutil.move(str(src), str(dest))
    del records[song_id]
    write_json(cfg["purged_file"], records)
    return rec
