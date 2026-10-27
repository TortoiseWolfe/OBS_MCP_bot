"""The words on screen. ffmpeg's drawtext re-reads these small files every frame (reload=1)."""
import textwrap
from pathlib import Path

from .tally import write_json  # noqa: F401  (re-exported for callers that write state beside the text)


def short(text, n):
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def write_text(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def render(out_dir, song, nxt, tally, songs):
    """Write title.txt, tally.txt, top.txt and next.txt for the song now playing."""
    out_dir = Path(out_dir)
    up, down = tally.counts(song["id"])
    write_text(out_dir / "title.txt", "\n".join(textwrap.wrap(song["title"], 22)[:3]))
    if song.get("opener"):
        head, _, tail = song["label"].rpartition(" ")  # "Opening the show" big, "Thursday" under it
        write_text(out_dir / "tally.txt", head)
        write_text(out_dir / "note.txt", tail)
    else:
        write_text(out_dir / "tally.txt", f"UP {up}     DOWN {down}")
        write_text(out_dir / "note.txt", " ")
    top = tally.top_net(songs, 3)
    lines = [f"{i}. {short(r[0]['title'], 30)}  ({r[1] - r[2]:+d})" for i, r in enumerate(top, 1)]
    write_text(out_dir / "top.txt", "\n".join(lines) if lines else "Votes will show up here")
    write_text(out_dir / "next.txt", "Up next: " + short(nxt["title"], 38))
