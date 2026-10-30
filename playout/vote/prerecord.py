#!/usr/bin/env python3
"""Render the Band Wagon replay as one prerecorded film (story set A) and check it.

  python3 prerecord.py render --out DIR [--start S --seconds N] [--workers 6]   # film.mp4, plan.json, checks.json, frames/
  python3 prerecord.py plan   --out DIR                                          # plan.json only, nothing rendered

The sound is the finished story-set mp3 (8 s crossfades already in it). The picture is built from the clock: frame_at(t) is a pure
function of the film time, so the film is cut into 30 s chunks, each rendered by its own worker (nice 19) and joined without re-encoding.
Per song: its own card, lyric cards, comic pages (a slow pan), then the band's portraits and design references; 2.5 s crossfades
between pictures, an 8 s picture crossfade at each song join (matching the sound), a "Now playing" band with Nell's age and the year,
chapter cards with Form's log lines as text. Cards that draw the Bicycle Corps are held (story.json "held": lyric cards and portraits only).
Stdlib Python plus Pillow and the host ffmpeg/ffprobe; no installs."""
import argparse
import json
import os
import re
import subprocess
import sys
from bisect import bisect_right
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bwvote import slideshow  # noqa: E402

HERE = Path(__file__).resolve().parent
W, H, BAND = 1280, 720, 60
PH = H - BAND  # picture area above the band
FPS = 30
CHUNK = 30  # seconds per worker job; a multiple of the 2 s keyframe gap
CW, CH = round(W * 1.12), round(PH * 1.12)  # still canvas: 12% bigger than the window, so a zoom has room
UNIT_MAX = 24.0  # longest one picture may stay up, in seconds per weight unit
WEIGHT = {"card": 1.0, "lyrics": 1.6, "page": 2.0, "member": 1.0}  # a clip weighs its length in UNIT_MAX units
CLIP_FPS = 20  # frames kept per second of a clip
CLIP_W, CLIP_H = 1173, PH  # a 16:9 clip fitted into the picture area
MEMBERS = ["Form", "Ivory", "Brass", "Chops", "Reed", "Verse", "Crash"]


def ex(p):
    return Path(str(p)).expanduser()


def smooth(a):
    a = min(1.0, max(0.0, a))
    return a * a * (3 - 2 * a)


def probe_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


# ---------------------------------------------------------------- plan

def member_pool(story, singers):
    """Portraits and design references: the song's singers first, then the rest of the band, each picture once."""
    d = ex(story["portraits"])
    seen, out = set(), []
    for name in list(singers) + MEMBERS:
        for f in (d / f"portrait-{name}.png", d / f"ref-{name.lower()}_ref.png"):
            if f.is_file() and f not in seen:
                seen.add(f)
                out.append(f)
    return out


def pick_items(story, cfg, song, seconds):
    """The song's pictures in showing order, each {kind, path, w}; the song fills `seconds` with no picture up longer than UNIT_MAX per weight."""
    held = bool(song.get("held"))
    cards = [Path(p) for p in slideshow.track_cards(cfg, {"id": song["id"]})]
    lyrics = [{"kind": "lyrics", "path": p, "w": WEIGHT["lyrics"]} for p in cards if "lyrics" in p.name]
    card = [{"kind": "card", "path": p, "w": WEIGHT["card"]} for p in cards if "lyrics" not in p.name and not held]
    pages = []
    if song.get("comic_track") and not held:
        data = json.loads(ex(story["pages"]).read_text())["pages"]
        pages = [{"kind": "page", "path": ex(story["pages_dir"]) / f"page{p['page']:02d}.png", "w": WEIGHT["page"]}
                 for p in data if p.get("track") == song["comic_track"]]
        pages = [x for x in pages if x["path"].is_file()]
    clips = []  # making-of clips from NX-01 (turntables, sheets beside the model, fit rounds); a missing file is skipped
    for name in song.get("clips", []):
        f = ex(story.get("visuals", "")) / f"vz-{name}.mp4"
        if f.is_file():
            dur = probe_seconds(f)
            clips.append({"kind": "clip", "path": f, "w": max(0.5, dur / UNIT_MAX), "dur": dur,
                          "loop": name.startswith(("turntable", "crash-"))})
    pool = [{"kind": "member", "path": p, "w": WEIGHT["member"]} for p in member_pool(story, song.get("singers", []))]
    items = card + clips + lyrics + pages
    if held:  # lyric cards and portraits take turns
        items, mem = [], list(pool)
        for ly in lyrics:
            items.append(ly)
            if mem:
                items.append(mem.pop(0))
        pool = mem
        items += clips
    need = seconds / UNIT_MAX
    k = 0
    while sum(x["w"] for x in items) < need and pool:
        items.append(pool.pop(0))
    allm = member_pool(story, song.get("singers", []))
    while sum(x["w"] for x in items) < need and allm:  # a whole pool shown once and still short: go round again
        items.append({"kind": "member", "path": allm[k % len(allm)], "w": WEIGHT["member"]})
        k += 1
    return items


def build_plan(story, cfg, total):
    J = float(story["join_seconds"])
    songs = []
    raw = story["songs"]
    for i, s in enumerate(raw):
        end = raw[i + 1]["start"] + J if i + 1 < len(raw) else total
        D = end - s["start"]
        items = pick_items(story, cfg, s, D)
        tw = sum(x["w"] for x in items)
        acc, bounds = 0.0, []
        for x in items:
            acc += D * x["w"] / tw
            bounds.append(acc)
        for x in items:  # seconds the picture is up, fades included: a clip plays through it (looping if it can)
            x["span"] = D * x["w"] / tw + float(story["picture_fade"])
        songs.append({**s, "end": end, "items": items, "bounds": bounds})
    return {"total": total, "join": J, "fade": float(story["picture_fade"]), "songs": songs,
            "opening": story["opening"], "ending": story["ending"]}


def plan_json(plan):
    def clean(o):
        if isinstance(o, Path):
            return str(o)
        raise TypeError(type(o))
    return json.dumps(plan, indent=1, default=clean)


def extract_clips(plan, out):
    """Decode each clip the plan uses once, into out/clipframes/<name>/NNNNN.jpg at CLIP_FPS, and note the folder on the item."""
    done = {}
    for s in plan["songs"]:
        for x in s["items"]:
            if x["kind"] != "clip":
                continue
            key = str(x["path"])
            if key not in done:
                d = Path(out) / "clipframes" / Path(key).stem
                d.mkdir(parents=True, exist_ok=True)
                if not any(d.glob("*.jpg")):
                    subprocess.run(["nice", "-n", "19", "ffmpeg", "-y", "-loglevel", "error", "-i", key, "-vf",
                                    f"fps={CLIP_FPS},scale={CLIP_W}:{CLIP_H}", "-q:v", "4", str(d / "%05d.jpg")], check=True)
                done[key] = (str(d), len(list(d.glob("*.jpg"))))
            x["frames"], x["count"] = done[key]


# ---------------------------------------------------------------- pictures

class Renderer:
    def __init__(self, plan, font_path):
        self.plan = plan
        self.font_path = font_path
        self.cache = {}
        self.bands = {}
        self.panels = {}
        self.starts = [s["start"] for s in plan["songs"]]

    # -- prepared pictures
    def prepared(self, item):
        key = str(item["path"])
        if key not in self.cache:
            if len(self.cache) >= 6:
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = self._prepare(item)
        return self.cache[key]

    @staticmethod
    def _prepare(item):
        art = Image.open(item["path"]).convert("RGB")
        if item["kind"] == "page":
            k = W / art.width
            return art.resize((W, max(PH, round(art.height * k))), Image.LANCZOS)
        small = art.copy()
        small.thumbnail((CW // 4, CH // 4))
        cover = max(CW / small.width, CH / small.height)
        bg = small.resize((round(small.width * cover), round(small.height * cover)), Image.BILINEAR)
        bg = bg.crop(((bg.width - CW // 4) // 2, (bg.height - CH // 4) // 2, (bg.width + CW // 4) // 2, (bg.height + CH // 4) // 2))
        bg = bg.filter(ImageFilter.GaussianBlur(5)).resize((CW, CH), Image.BILINEAR).point(lambda v: int(v * 0.45))
        fg_h = 654 if item["kind"] == "lyrics" else 600  # a lyric card is shown as large as the picture area allows, still
        k = min(fg_h / art.height, (CW * 0.9) / art.width)
        fg = art.resize((max(1, round(art.width * k)), max(1, round(art.height * k))), Image.LANCZOS)
        bg.paste(fg, ((CW - fg.width) // 2, (CH - fg.height) // 2))
        return bg

    def clip_frame(self, item, p):
        """The clip's picture at its own time: p of the way through the span; it loops if it can, else holds its last frame."""
        t = p * item["span"]
        n = item["count"]
        i = int(t * CLIP_FPS) % n if item.get("loop") else min(n - 1, int(t * CLIP_FPS))
        fg = Image.open(Path(item["frames"]) / f"{i + 1:05d}.jpg").convert("RGB")
        bg = fg.resize((16, 9), Image.BILINEAR).resize((W, PH), Image.BILINEAR).point(lambda v: int(v * 0.45))
        bg.paste(fg, ((W - fg.width) // 2, 0))
        return bg

    def item_frame(self, item, p, flip):
        if item["kind"] == "clip":
            return self.clip_frame(item, p)
        img = self.prepared(item)
        if item["kind"] == "page":
            y = (img.height - PH) * smooth(p)
            return img.resize((W, PH), Image.BILINEAR, box=(0, y, W, y + PH))
        q = 1.0 if item["kind"] == "lyrics" else (1 - p if flip else p)
        bw, bh = CW - (CW - W) * q, CH - (CH - PH) * q
        x0, y0 = (CW - bw) / 2, (CH - bh) / 2
        return img.resize((W, PH), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))

    # -- one song's picture at song time u
    def pic(self, song, u):
        b, n, F = song["bounds"], len(song["bounds"]), self.plan["fade"]
        i = min(bisect_right(b, u), n - 1)

        def fr(j):
            lo = b[j - 1] if j else 0.0
            hi = b[j]
            p = (u - (lo - F / 2)) / (hi - lo + F)
            return self.item_frame(song["items"][j], min(1.0, max(0.0, p)), j % 2 == 1)

        if i > 0 and u < b[i - 1] + F / 2:
            return Image.blend(fr(i - 1), fr(i), smooth((u - (b[i - 1] - F / 2)) / F))
        if i < n - 1 and u > b[i] - F / 2:
            return Image.blend(fr(i), fr(i + 1), smooth((u - (b[i] - F / 2)) / F))
        return fr(i)

    def band(self, song):
        n = song["n"]
        if n not in self.bands:
            text = f"Now playing: {song['title']}" + (f"  /  {song['label']}" if song.get("label") else "")
            img = Image.new("RGB", (W, BAND), (0, 0, 0))
            d = ImageDraw.Draw(img)
            size = 38
            while True:
                f = ImageFont.truetype(self.font_path, size)
                if d.textlength(text, font=f) <= W - 60 or size <= 18:
                    break
                size -= 2
            d.text(((W - d.textlength(text, font=f)) / 2, (BAND - size) / 2 - 4), text, font=f, fill=(255, 255, 255))
            self.bands[n] = img
        return self.bands[n]

    def song_frame(self, k, t):
        song = self.plan["songs"][k]
        out = Image.new("RGB", (W, H))
        out.paste(self.pic(song, t - song["start"]), (0, 0))
        out.paste(self.band(song), (0, PH))
        return out

    def join_frame(self, k, t):
        """Song k's start: the pictures cross over the whole join; the band text fades out, then the new one fades in (two bands laid over each other read as a smear)."""
        a = smooth((t - self.starts[k]) / self.plan["join"])
        old, new = self.plan["songs"][k - 1], self.plan["songs"][k]
        out = Image.new("RGB", (W, H))
        out.paste(Image.blend(self.pic(old, t - old["start"]), self.pic(new, t - new["start"]), a), (0, 0))
        black = Image.new("RGB", (W, BAND))
        out.paste(Image.blend(self.band(old), black, min(1.0, 2 * a)) if a < 0.5 else Image.blend(black, self.band(new), 2 * a - 1), (0, PH))
        return out

    # -- overlays
    def panel(self, key, heading, sub, log, big=False):
        if key in self.panels:
            return self.panels[key]
        rows = []  # (text, size, colour)
        if heading:
            rows.append((heading, 46 if big else 40, (255, 205, 110)))
        if sub:
            rows.append((sub, 58 if big else 50, (255, 255, 255)))
        d = ImageDraw.Draw(Image.new("RGB", (4, 4)))
        if log:
            f = ImageFont.truetype(self.font_path, 30)
            line = ""
            for word in log.split():
                if d.textlength(line + " " + word, font=f) > 1020 and line:
                    rows.append((line, 30, (235, 235, 235)))
                    line = word
                else:
                    line = (line + " " + word).strip()
            rows.append((line, 30, (235, 235, 235)))
        height = sum(int(r[1] * 1.35) for r in rows) + 40
        width = int(max(d.textlength(r[0], font=ImageFont.truetype(self.font_path, r[1])) for r in rows)) + 90
        width = min(W - 40, max(width, 600))
        panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        pd = ImageDraw.Draw(panel)
        pd.rounded_rectangle((0, 0, width - 1, height - 1), radius=22, fill=(0, 0, 0, 185))
        y = 20
        for text, size, colour in rows:
            f = ImageFont.truetype(self.font_path, size)
            pd.text(((width - pd.textlength(text, font=f)) / 2, y), text, font=f, fill=colour)
            y += int(size * 1.35)
        self.panels[key] = panel
        return panel

    def overlays(self, t):
        """[(panel, alpha, centre_y)] showing at film time t."""
        pl, out = self.plan, []
        o = pl["opening"]
        if t < o["seconds"]:
            a = min(1.0, t / 1.0, (o["seconds"] - t) / 1.5)
            out.append((self._open_panel(o), max(0.0, a), PH // 2))
        e = pl["ending"]
        if t > pl["total"] - e["seconds"]:
            a = min(1.0, (t - (pl["total"] - e["seconds"])) / 2.0)
            out.append((self._end_panel(e), a, PH // 2))
        for s in pl["songs"]:
            c = s.get("chapter")
            if not c:
                continue
            t0 = s["start"] + c["at"] + (0 if s["n"] == 1 else pl["join"] / 2)
            if t0 <= t < t0 + 8:
                a = min(1.0, (t - t0) / 1.0, (t0 + 8 - t) / 1.0)
                out.append((self.panel(f"ch{s['n']}", c["head"], c["sub"], c["log"]), a, PH - 190))
        return out

    def _open_panel(self, o):
        if "open" not in self.panels:
            lines = o["lines"]
            self.panels["open"] = self.panel("open-x", lines[0], lines[1], lines[2], True)
        return self.panels["open"]

    def _end_panel(self, e):
        if "end" not in self.panels:
            self.panels["end"] = self.panel("end-x", e["lines"][0], "", e["lines"][1], True)
        return self.panels["end"]

    def frame_at(self, t):
        pl = self.plan
        k = max(0, bisect_right(self.starts, t) - 1)
        if k > 0 and t < self.starts[k] + pl["join"]:
            img = self.join_frame(k, t)
        else:
            img = self.song_frame(k, t)
        for panel, a, cy in self.overlays(t):
            if a <= 0:
                continue
            mask = panel.getchannel("A")
            if a < 1:
                mask = mask.point(lambda v, a=a: int(v * a))
            img.paste(panel.convert("RGB"), ((W - panel.width) // 2, int(cy - panel.height / 2)), mask)
        left = pl["total"] - t
        if left < 1.5:
            img = Image.blend(img, Image.new("RGB", (W, H)), min(1.0, 1 - left / 1.5))
        return img


# ---------------------------------------------------------------- workers

_R = {}


def _init(plan_file, font):
    os.nice(19)
    plan = json.loads(Path(plan_file).read_text())
    for s in plan["songs"]:
        for x in s["items"]:
            x["path"] = Path(x["path"])
    _R["r"] = Renderer(plan, font)


def render_chunk(job):
    t0, seconds, out = job
    r = _R["r"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-profile:v", "main", "-pix_fmt", "yuv420p", "-crf", "22",
           "-maxrate", "2000k", "-bufsize", "4000k", "-g", str(FPS * 2), "-keyint_min", str(FPS * 2), "-sc_threshold", "0",
           "-threads", "2", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(round(seconds * FPS)):
        p.stdin.write(r.frame_at(t0 + i / FPS).tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError(f"ffmpeg failed on chunk {t0}")
    return str(out)


# ---------------------------------------------------------------- checks

def ff(*args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True).stderr


def run_checks(film, plan, t0, seconds, out):
    chk = {"film": str(film), "start": t0, "seconds_asked": seconds}
    v = probe_seconds(film)
    a = float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration", "-of", "csv=p=0", str(film)],
                             capture_output=True, text=True).stdout.strip() or 0)
    vd = float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", str(film)],
                              capture_output=True, text=True).stdout.strip() or 0)
    chk["video_seconds"], chk["audio_seconds"], chk["container_seconds"] = vd, a, v
    chk["audio_video_gap_ok"] = abs(vd - a) <= 0.1
    chk["run_time_ok"] = abs(v - seconds) <= 0.5
    sil = ff("-i", str(film), "-vn", "-af", "silencedetect=n=-50dB:d=2", "-f", "null", "-")
    chk["silences"] = len(re.findall(r"silence_start", sil))
    lu = ff("-i", str(film), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-")
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", lu)
    chk["loudness_lufs"] = float(m[-1]) if m else None
    bd = ff("-i", str(film), "-an", "-vf", "blackdetect=d=1:pix_th=0.05", "-f", "null", "-")
    chk["black_runs_over_1s"] = len(re.findall(r"black_start", bd))
    fd = ff("-i", str(film), "-an", "-vf", "freezedetect=n=-60dB:d=8", "-f", "null", "-")
    chk["frozen_runs_over_8s"] = len(re.findall(r"freeze_start", fd))
    # per song loudness, for songs fully inside the film
    per = []
    for s in plan["songs"]:
        lo, hi = s["start"] - t0, s["end"] - t0 - plan["join"]
        if lo >= 0 and hi <= seconds and hi - lo > 20:
            e = ff("-ss", f"{lo + 1:.2f}", "-t", f"{hi - lo - 2:.2f}", "-i", str(film), "-vn", "-af", "ebur128", "-f", "null", "-")
            mm = re.findall(r"I:\s+(-?[\d.]+) LUFS", e)
            if mm:
                per.append((s["n"], float(mm[-1])))
    chk["song_lufs"] = per
    chk["song_lufs_spread"] = round(max(x[1] for x in per) - min(x[1] for x in per), 2) if len(per) > 1 else None
    # frame grabs: at every join (before, middle, after), every chapter card, the opening and the end
    marks = []
    for s in plan["songs"]:
        if s["n"] > 1:
            for tag, dt in (("a-before", -1.0), ("b-mid", plan["join"] / 2), ("c-after", plan["join"] + 1.0)):
                marks.append((f"join-{s['n']:02d}-{tag}", s["start"] + dt))
        c = s.get("chapter")
        if c:
            marks.append((f"chapter-{s['n']:02d}", s["start"] + c["at"] + (0 if s["n"] == 1 else plan["join"] / 2) + 3))
    marks += [("open-1", 1.0), ("open-5", 5.0), ("end-late", plan["total"] - 8)]
    fdir = Path(out) / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    grabs = []
    for name, ft in marks:
        rel = ft - t0
        if 0 <= rel < seconds - 0.05:
            f = fdir / f"{name}.jpg"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{rel:.2f}", "-i", str(film), "-frames:v", "1", "-q:v", "3", str(f)])
            grabs.append(str(f))
    chk["frame_grabs"] = grabs
    # the held Corps pictures must not appear anywhere in the plan
    bad = []
    for s in plan["songs"]:
        if s.get("held"):
            bad += [str(x["path"]) for x in s["items"] if x["kind"] in ("card", "page")]
    chk["held_pictures_used"] = bad
    return chk


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["plan", "render"])
    ap.add_argument("--story", default=str(HERE / "replay" / "story.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--seconds", type=float, default=0.0, help="0 = to the end of the sound")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)
    os.nice(19)
    story = json.loads(Path(args.story).read_text())
    cfg = json.loads(ex(story["playlist"]).read_text())
    total = probe_seconds(ex(story["audio"]))
    plan = build_plan(story, cfg, total)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.cmd == "render":
        extract_clips(plan, out)
    (out / "plan.json").write_text(plan_json(plan))
    if args.cmd == "plan":
        return 0
    seconds = args.seconds or (total - args.start)
    seconds = min(seconds, total - args.start)
    jobs, t = [], args.start
    while t < args.start + seconds - 1e-6:
        n = min(CHUNK, args.start + seconds - t)
        jobs.append((t, n, out / f"chunk-{len(jobs):04d}.mp4"))
        t += n
    with ProcessPoolExecutor(args.workers, initializer=_init, initargs=(str(out / "plan.json"), cfg["font"])) as pool:
        done = list(pool.map(render_chunk, jobs))
    lst = out / "chunks.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in done))
    film = out / "film.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-ss", f"{args.start:.3f}",
                    "-i", str(ex(story["audio"])), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-t", f"{seconds:.3f}", "-movflags", "+faststart", str(film)], check=True)
    chk = run_checks(film, plan, args.start, seconds, out)
    (out / "checks.json").write_text(json.dumps(chk, indent=1))
    print(json.dumps(chk, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
