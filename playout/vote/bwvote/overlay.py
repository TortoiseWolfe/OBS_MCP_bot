"""The words on screen. ffmpeg's drawtext re-reads these small files every frame (reload=1)."""
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from .tally import write_json  # noqa: F401  (re-exported for callers that write state beside the text)


def short(text, n):
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def write_text(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def active_announcement(announcements, now=None):
    """The words of the announcement whose window ({"from", "until", "text"}, ISO times) holds `now`, or None.
    The text must fit the note line (about 30 characters at the font size in run.py)."""
    now = now or datetime.now(timezone.utc)
    for a in announcements or []:
        if datetime.fromisoformat(a["from"]) <= now < datetime.fromisoformat(a["until"]):
            return a["text"]
    return None


def youtube_note(song, ids):
    """The note line that says where the song now playing is on YouTube ("YouTube youtu.be/<id>", 28 characters), or None.
    `ids` maps a song file name (with or without .mp3) to its YouTube video id."""
    vid = (ids or {}).get(Path(song["id"]).stem)
    return f"YouTube youtu.be/{vid}" if vid else None


def render(out_dir, song, nxt, tally, songs, announce=None, youtube=None):
    """Write title.txt, tally.txt, top.txt and next.txt for the song now playing; `announce` takes the note line,
    else the song's YouTube address when `youtube` (see youtube_note) has one for it."""
    out_dir = Path(out_dir)
    up, down = tally.counts(song["id"])
    write_text(out_dir / "title.txt", "\n".join(textwrap.wrap(song["title"], 22)[:3]))
    if song.get("opener"):
        head, _, tail = song["label"].rpartition(" ")  # "Opening the show" big, "Thursday" under it
        write_text(out_dir / "tally.txt", head)
        write_text(out_dir / "note.txt", tail)
    else:
        write_text(out_dir / "tally.txt", f"UP {up}     DOWN {down}")
        write_text(out_dir / "note.txt", announce or youtube_note(song, youtube) or " ")
    top = tally.top_net(songs, 3)
    lines = [f"{i}. {short(r[0]['title'], 30)}  ({r[1] - r[2]:+d})" for i, r in enumerate(top, 1)]
    write_text(out_dir / "top.txt", "\n".join(lines) if lines else "Votes will show up here")
    write_text(out_dir / "next.txt", "Up next: " + short(nxt["title"], 38) if nxt else " ")
