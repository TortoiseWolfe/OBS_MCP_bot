"""The song list in playlist.json, the opening song, and ffprobe for a file's length."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def load(path=HERE / "playlist.json"):
    cfg = json.loads(Path(path).read_text())
    base = Path(cfg["audio_dir"]).expanduser()
    for s in cfg["songs"]:
        s["id"] = cfg["audio_prefix"] + s["file"]
        s["path"] = base / s["file"]
    return cfg


def probe_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60, check=True)
    return float(out.stdout.strip())


def opener_source(cfg):
    """The full-length song that opens the show (played once, at the first start), or None."""
    o = cfg.get("opener")
    if not o:
        return None
    song = next(x for x in cfg["songs"] if x["file"] == o["file"])
    return dict(song, kind="opener", opener=True, label=o.get("label", ""))
