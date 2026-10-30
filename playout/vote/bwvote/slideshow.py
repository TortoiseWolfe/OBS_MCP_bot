"""A looping image slideshow that takes the whole picture inside set time windows (the flyer and the titled covers for a show).
playlist.json: "slideshow": {"images": ["a.png", ...], "seconds": 25, "windows": [{"from": ISO time, "until": ISO time}]}.
It is stateless: the picture is chosen from the clock, so a restart picks up where the loop would have been."""
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .overlay import write_text

W, H = 1280, 720
TEXT_FILES = ("title", "tally", "note", "top", "next")


def track_cards(cfg, song):
    """The playing song's own cards (card, then lyrics pages), from playlist.json "track_cards": a file of
    {file stem: ["cards/x.jpg", ...]} whose paths are relative to its own folder. [] when there is none; read each call, so a new file shows up without a restart."""
    path = (cfg or {}).get("track_cards")
    if not path or not song:
        return []
    try:
        path = Path(path).expanduser()
        names = json.loads(path.read_text()).get(Path(str(song.get("id", ""))).stem) or []
        return [p for p in (path.parent / n for n in names) if p.is_file()]
    except (OSError, ValueError, AttributeError):
        return []


def current(cfg, now=None, song=None):
    """The image the slideshow shows right now, or None outside its windows.
    With a song that has cards, the cards take turns (card first, then the lyrics pages); other songs get the image loop."""
    if not cfg or not cfg.get("images"):
        return None
    now = now or datetime.now(timezone.utc)
    if not any(datetime.fromisoformat(w["from"]) <= now < datetime.fromisoformat(w["until"]) for w in cfg.get("windows", [])):
        return None
    images = track_cards(cfg, song) or cfg["images"]
    seconds = max(5, float(cfg.get("seconds", 25)))
    return Path(images[int(now.timestamp() // seconds) % len(images)]).expanduser()


def build(image, out):
    """The image, whole, centred on black at 1280x720 (written so ffmpeg never reads half a picture)."""
    art = Image.open(image).convert("RGB")
    scale = min(W / art.width, H / art.height)
    art = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))))
    bg = Image.new("RGB", (W, H), (0, 0, 0))
    bg.paste(art, ((W - art.width) // 2, (H - art.height) // 2))
    out = Path(out)
    tmp = out.with_name(out.stem + ".tmp.png")
    bg.save(tmp)
    tmp.replace(out)


def blank_text(out_dir):
    for name in TEXT_FILES:
        write_text(Path(out_dir) / f"{name}.txt", " ")
