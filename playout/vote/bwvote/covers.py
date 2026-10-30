"""One cover per song. The art lane writes song-covers.json (song file to cover path); it is read again at every song change,
so covers that arrive later show up without a restart of this program."""
import json
from pathlib import Path


def load(path):
    """{song file name: cover path}; {} when the file is missing or unreadable. Keys may or may not end in .mp3."""
    try:
        raw = json.loads(Path(path).expanduser().read_text())
    except (OSError, ValueError):
        return {}
    base = Path(path).expanduser().parent
    out = {}
    for k, v in (raw.items() if isinstance(raw, dict) else []):
        p = Path(str(v)).expanduser()
        out[Path(k).stem] = p if p.is_absolute() else base / p
    return out


def cover_for(song, covers, default):
    """The song's own cover when the file exists, else the show's default cover."""
    p = covers.get(Path(song["id"]).stem)
    return p if p and p.is_file() else Path(default).expanduser()
