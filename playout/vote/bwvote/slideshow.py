"""A looping image slideshow that takes the whole picture inside set time windows (the flyer and the titled covers for a show).
playlist.json: "slideshow": {"images": ["a.png", ...], "seconds": 25, "windows": [{"from": ISO time, "until": ISO time}]}.
It is stateless: the picture is chosen from the clock, so a restart picks up where the loop would have been."""
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .overlay import write_text

W, H = 1280, 720
TEXT_FILES = ("title", "tally", "note", "top", "next")


def current(cfg, now=None):
    """The image the slideshow shows right now, or None outside its windows."""
    if not cfg or not cfg.get("images"):
        return None
    now = now or datetime.now(timezone.utc)
    if not any(datetime.fromisoformat(w["from"]) <= now < datetime.fromisoformat(w["until"]) for w in cfg.get("windows", [])):
        return None
    images = cfg["images"]
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
