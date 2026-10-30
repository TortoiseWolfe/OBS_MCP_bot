#!/usr/bin/env python3
"""Render the Band Wagon replay as one prerecorded film (story set A) and check it.

  python3 prerecord.py render --out DIR [--start S --seconds N] [--workers 6]   # film.mp4, plan.json, checks.json, frames/
  python3 prerecord.py plan   --out DIR                                          # plan.json only, nothing rendered

The sound is the finished story-set mp3 (8 s crossfades already in it). The picture is built from the clock: frame_at(t) is a pure
function of the film time, so the film is cut into 30 s chunks, each rendered by its own worker (nice 19) and joined without re-encoding.
Per song: its own card, lyric cards, comic pages (a slow pan), then the band's portraits and design references; 2.5 s crossfades
between pictures, an 8 s picture crossfade at each song join (matching the sound), a "Now playing" band with Nell's age and the year,
chapter cards with Form's log lines as text. Cards that draw the Bicycle Corps are held (story.json "held": lyric cards and portraits only).
Pictures: the widescreen video cards (1280x632, design A, built by hub build_tracks.py VIDEO=1) fill the picture area with no blurred
filler; chapter, opening and end screens are full screens of their own (cover on the left, big words on the right), so no text sits on card text.
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
W, H, BAND = 1280, 720, 88  # the band is tall enough that its text ends 36+ px above the frame's bottom edge (EBU R95 graphics-safe margin, 5% of 720)
BAND_MARGIN = 36
PH = H - BAND  # picture area above the band
FPS = 30
CHUNK = 30  # seconds per worker job; a multiple of the 2 s keyframe gap
CW, CH = round(W * 1.12), round(PH * 1.12)  # still canvas: 12% bigger than the window, so a zoom has room
UNIT_MAX = 24.0  # longest one picture may stay up, in seconds per weight unit
WEIGHT = {"card": 1.0, "lyrics": 1.6, "page": 2.0, "member": 1.0}  # a clip weighs its length in UNIT_MAX units
CLIP_FPS = 20  # frames kept per second of a clip
CLIP_W, CLIP_H = 1173, PH  # a 16:9 clip fitted into the picture area
LYR_ART = (64, 150, 396, 482)  # where a video lyric page carries the cover (build_tracks.py V_ART); chapter screens crop it from there
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


def video_cards(cards, vdir):
    """The widescreen versions of a song's square cards: [track card, lyric pages...] from `vdir`; the square cards when it has none."""
    if not vdir or not ex(vdir).is_dir():
        return cards, False
    stems = []
    for c in cards:
        st = re.sub(r"-(card|lyrics(-\d+)?)\.jpg$", "", c.name)
        if st not in stems:
            stems.append(st)
    out = []
    for st in stems:
        card = ex(vdir) / f"{st}-card-video.jpg"
        if card.is_file():
            out.append(card)
        out += sorted(ex(vdir).glob(f"{st}-lyrics-video*.jpg"), key=lambda f: int(re.search(r"-(\d+)\.jpg$", f.name).group(1)) if re.search(r"-(\d+)\.jpg$", f.name) else 1)
    return (out, True) if out else (cards, False)


# Reading rule: every screen with words stays fully clear long enough for a young reader (strictest published rate found: Australian children's captioning, 120 words a minute),
# and no screen, text or picture, is clear for less than MIN_CLEAR seconds. "Clear" = the screen's own share of the picture is at least CLEAR_W.
READ_WPS = 2.0  # words a second (120 a minute)
ORIENT = 2.0  # seconds to take in a new screen before reading starts
MIN_CLEAR = 5.0  # shortest a screen may be clear, words or not
MIN_FADE = 2.5  # shortest dissolve into or out of a screen with words, counted from its first visible frame to the moment it is clear (a 4 s crossfade measures about 3 s)
CLEAR_W = 0.9
U = 0.804  # smooth(U) = 0.9: how far into a dissolve a screen reaches CLEAR_W
FILM_FADE = 4.0  # the last picture fades to black over this
CARD_WORDS, CLIP_WORDS, PAGE_WORDS = 8, 20, 15  # words a track card, a clip caption (the longest burned in) and a comic page carry
DROP_ORDER = ["member", "page", "clip", "card", "lyrics"]  # a song too short for every screen sheds these first (the first lyric page and the slides stay)


def wordcount(text):
    return len(re.findall(r"[\w'’-]+", text or ""))


def clear_need(words):
    return max(MIN_CLEAR, ORIENT + words / READ_WPS)


def item_words(x, words):
    if x["kind"] == "slide":
        return wordcount(" ".join(str(x["slide"].get(k) or "") for k in ("head", "sub", "log")))
    if x["kind"] == "lyrics":
        return words.get(Path(str(x["path"])).name, 0)
    return {"card": CARD_WORDS, "clip": CLIP_WORDS, "page": PAGE_WORDS}.get(x["kind"], 0)


def hold_needs(items, first_song, last_song, J, F):
    """Seconds each item must hold (boundary to boundary) so that it is clear for its need once the dissolves that eat into it are paid for."""
    n, out = len(items), []
    for i, x in enumerate(items):
        left = (0.0 if first_song else U * J) if i == 0 else (U - 0.5) * F
        right = (U * FILM_FADE if last_song else U * J) if i == n - 1 else (U - 0.5) * F
        need = clear_need(x["words"])
        if x["kind"] == "slide":
            need = max(need, float(x["slide"].get("seconds") or 0) - left - right)
        out.append(need + left + right)
    return out


def fit_items(items, D, first_song, last_song, J, F):
    """Drop the lowest-priority screens until every remaining one can hold its need inside D; returns (items, needs, dropped)."""
    dropped = []
    while True:
        needs = hold_needs(items, first_song, last_song, J, F)
        if sum(needs) <= D:
            return items, needs, dropped
        for kind in DROP_ORDER:
            idx = [i for i, x in enumerate(items) if x["kind"] == kind and not (kind == "lyrics" and x is next((y for y in items if y["kind"] == "lyrics"), None))]
            if idx:
                dropped.append(items.pop(idx[-1]))
                break
        else:
            return items, needs, dropped


def pick_items(story, cfg, song, seconds, words=None):
    """The song's screens in showing order, each {kind, path, w, words}; art may stay up no longer than UNIT_MAX per weight unit. Text screens are not trimmed to fit: see fit_items."""
    words = words or {}
    held = bool(song.get("held"))
    cards, video = video_cards([Path(p) for p in slideshow.track_cards(cfg, {"id": song["id"]})], story.get("video_cards"))
    lyrics = [{"kind": "lyrics", "path": p, "w": WEIGHT["lyrics"], "video": video} for p in cards if "lyrics" in p.name]
    card = [{"kind": "card", "path": p, "w": WEIGHT["card"], "video": video} for p in cards if "lyrics" not in p.name and not held]
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
    cover = next((x["path"] for x in lyrics if x.get("video")), None)
    for x in items:
        x["words"] = item_words(x, words)
    return items, pool, cover


def slide_item(key, cover, head, sub, log, seconds=0):
    s = {"head": head, "sub": sub, "log": log, "seconds": seconds}
    x = {"kind": "slide", "key": key, "path": cover or Path("none"), "cover": bool(cover), "w": 0.0, "slide": s, "video": True}
    x["words"] = item_words(x, {})
    return x


def build_plan(story, cfg, total):
    J, F = float(story["join_seconds"]), float(story["picture_fade"])
    raw = story["songs"]
    vd = story.get("video_cards")
    wf = ex(vd) / "words.json" if vd else None
    words = json.loads(wf.read_text()) if wf and wf.is_file() else {}
    songs = []
    for i, s in enumerate(raw):
        end = raw[i + 1]["start"] + J if i + 1 < len(raw) else total
        D = end - s["start"]
        first, last = i == 0, i + 1 == len(raw)
        items, pool, cover = pick_items(story, cfg, s, D, words)
        head, tail = [], []
        if first:
            o = story["opening"]
            head.append(slide_item("open", cover, o["lines"][0], o["lines"][1], o["lines"][2], o["seconds"]))
        c = s.get("chapter")
        if c:
            head.append(slide_item(f"ch{s['n']}", cover, c["head"], c["sub"], c["log"]))
        if last:
            e = story["ending"]
            tail.append(slide_item("end", cover, e["lines"][0], "", e["lines"][1], e["seconds"]))
        allm = member_pool(story, s.get("singers", []))
        k = 0
        # drop screens until every kept one fits, keeping the slides and the first lyric page
        screens = head + items + tail
        screens, needs, dropped = fit_items(screens, D, first, last, J, F)
        while True:  # art may not sit longer than UNIT_MAX per weight: add portraits while there is room for them
            needs = hold_needs(screens, first, last, J, F)
            spare = D - sum(needs)
            tw = sum(x["w"] for x in screens) or 1.0
            over = any(x["kind"] in ("card", "member", "page") and needs[j] + spare * x["w"] / tw > UNIT_MAX * x["w"] for j, x in enumerate(screens))
            if not over or not allm or k > 60:
                break
            m = pool.pop(0) if pool else {"kind": "member", "path": allm[k % len(allm)], "w": WEIGHT["member"]}
            k += 1
            m["words"] = 0
            at = len(screens) - (1 if tail else 0)
            screens.insert(at, m)
            if sum(hold_needs(screens, first, last, J, F)) > D:
                screens.pop(at)
                break
        needs = hold_needs(screens, first, last, J, F)
        spare = max(0.0, D - sum(needs))
        tw = sum(x["w"] for x in screens) or 1.0
        acc, bounds = 0.0, []
        for x, nd in zip(screens, needs):
            x["need_hold"] = nd
            x["hold"] = nd + spare * x["w"] / tw
            acc += x["hold"]
            bounds.append(acc)
        if bounds and abs(bounds[-1] - D) > 1e-6:  # a song that still cannot fit its needs is stretched; the checks flag it
            scale = D / bounds[-1]
            bounds = [b * scale for b in bounds]
        prev = 0.0
        for x, b in zip(screens, bounds):  # seconds the picture is up, fades included: a clip plays through it (looping if it can)
            x["span"] = (b - prev) + F
            prev = b
        songs.append({**s, "end": end, "items": screens, "bounds": bounds, "dropped": [str(x["path"]) for x in dropped]})
    return {"total": total, "join": J, "fade": F, "songs": songs, "opening": story["opening"], "ending": story["ending"]}


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
        if item.get("video"):  # a widescreen card already fills the picture area
            return art if art.size == (W, PH) else art.resize((W, PH), Image.LANCZOS)
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
        if item["kind"] == "slide":
            return self.slide(item)
        img = self.prepared(item)
        if item["kind"] == "page":
            y = (img.height - PH) * smooth(p)
            return img.resize((W, PH), Image.BILINEAR, box=(0, y, W, y + PH))
        if item.get("video"):  # a lyric page stays still; a track card drifts in 3% (its text sits 64 px from the edge, the safe margin is 36)
            if item["kind"] == "lyrics":
                return img
            q = 0.03 * (1 - p if flip else p)
            bw, bh = W * (1 - q), PH * (1 - q)
            return img.resize((W, PH), Image.BILINEAR, box=((W - bw) / 2, (PH - bh) / 2, (W + bw) / 2, (PH + bh) / 2))
        q = 1.0 if item["kind"] == "lyrics" else (1 - p if flip else p)
        bw, bh = CW - (CW - W) * q, CH - (CH - PH) * q
        x0, y0 = (CW - bw) / 2, (CH - bh) / 2
        return img.resize((W, PH), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))

    # -- one song's picture at song time u
    @staticmethod
    def weights(song, u, F):
        """[(item index, share of the picture)] at song time u: one screen, or two while they dissolve (a smooth F-second crossfade centred on the boundary)."""
        b, n = song["bounds"], len(song["bounds"])
        i = min(bisect_right(b, u), n - 1)
        if i > 0 and u < b[i - 1] + F / 2:
            a = smooth((u - (b[i - 1] - F / 2)) / F)
            return [(i - 1, 1 - a), (i, a)]
        if i < n - 1 and u > b[i] - F / 2:
            a = smooth((u - (b[i] - F / 2)) / F)
            return [(i, 1 - a), (i + 1, a)]
        return [(i, 1.0)]

    def pic(self, song, u):
        b, F = song["bounds"], self.plan["fade"]

        def fr(j):
            lo = b[j - 1] if j else 0.0
            p = (u - (lo - F / 2)) / (b[j] - lo + F)
            return self.item_frame(song["items"][j], min(1.0, max(0.0, p)), j % 2 == 1)

        w = self.weights(song, u, F)
        if len(w) == 1:
            return fr(w[0][0])
        return Image.blend(fr(w[0][0]), fr(w[1][0]), w[1][1])

    def band(self, song):
        n = song["n"]
        if n not in self.bands:
            text = f"Now playing: {song['title']}" + (f"  /  {song['label']}" if song.get("label") else "")
            img = Image.new("RGB", (W, BAND), (0, 0, 0))
            d = ImageDraw.Draw(img)
            size = 38
            while True:
                f = ImageFont.truetype(self.font_path, size)
                if d.textlength(text, font=f) <= W - 128 or size <= 18:  # 64 px each side: the graphics-safe width
                    break
                size -= 2
            bb = d.textbbox((0, 0), text, font=f)
            # the lowest letter (a descender) ends BAND_MARGIN + 2 px above the bottom of the frame
            d.text(((W - d.textlength(text, font=f)) / 2 - bb[0], BAND - BAND_MARGIN - 2 - bb[3]), text, font=f, fill=(255, 255, 255))
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

    # -- slides: the opening, chapter and end screens are items of their own (cover left, big words right); nothing is laid over a card's text
    def slide(self, item):
        """A full picture-area screen: the song's cover cropped from its first video lyric page, then the words."""
        key = item["key"]
        if key in self.panels:
            return self.panels[key]
        head, sub, log = item["slide"]["head"], item["slide"]["sub"], item["slide"]["log"]
        art = Image.open(item["path"]).convert("RGB").crop(LYR_ART) if item.get("cover") else None
        d0 = ImageDraw.Draw(Image.new("RGB", (4, 4)))
        if art:
            img = art.resize((W, W), Image.LANCZOS).crop((0, 300, W, 300 + PH)).filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * 0.2))
            d = ImageDraw.Draw(img)
            ay = PH // 2 - 150
            d.rectangle([60, ay - 4, 64 + 300 + 3, ay + 300 + 3], fill=(232, 179, 76))
            img.paste(art.resize((300, 300), Image.LANCZOS), (64, ay))
            d.rectangle([410, ay, 414, ay + 300], fill=(232, 179, 76))
            x = 446
        else:
            img, x = Image.new("RGB", (W, PH), (16, 11, 8)), 64
        d = ImageDraw.Draw(img)
        lil = lambda n: ImageFont.truetype(self.font_path, n)
        bold = lambda n: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", n)
        logsize = 26 if (head or sub) else 34
        lines = []
        if log:
            line = ""
            for word in log.split():
                if d0.textlength((line + " " + word).strip(), font=bold(logsize)) > W - 64 - x and line:
                    lines.append(line)
                    line = word
                else:
                    line = (line + " " + word).strip()
            lines.append(line)
        rows = []  # (text, font, colour, height)
        if head:
            rows.append((head, lil(46 if sub else 64), (232, 179, 76) if sub else (255, 255, 255), 58 if sub else 80))
        if sub:
            rows.append((sub, lil(76), (255, 255, 255), 92))
        if lines and rows:
            rows.append(("", None, None, 14))
        rows += [(ln, bold(logsize), (246, 236, 210), int(logsize * 1.38)) for ln in lines]
        y = max(40, PH // 2 - sum(r[3] for r in rows) // 2)
        for text, font, colour, h in rows:
            if text:
                d.text((x, y), text, font=font, fill=colour)
            y += h
        self.panels[key] = img
        return img

    def frame_at(self, t):
        pl = self.plan
        k = max(0, bisect_right(self.starts, t) - 1)
        img = self.join_frame(k, t) if k > 0 and t < self.starts[k] + pl["join"] else self.song_frame(k, t)
        left = pl["total"] - t
        if left < FILM_FADE:
            img = Image.blend(img, Image.new("RGB", (W, H)), 1 - smooth(left / FILM_FADE))
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


# ---------------------------------------------------------------- measurement

def shares_at(plan, t):
    """{(song index, item index): share of the picture} at film time t, as the renderer draws it (joins and the closing fade included)."""
    songs, F, J = plan["songs"], plan["fade"], plan["join"]
    k = max(0, bisect_right([s["start"] for s in songs], t) - 1)
    out = {}
    if k > 0 and t < songs[k]["start"] + J:
        a = smooth((t - songs[k]["start"]) / J)
        for kk, m in ((k - 1, 1 - a), (k, a)):
            for j, w in Renderer.weights(songs[kk], t - songs[kk]["start"], F):
                out[(kk, j)] = out.get((kk, j), 0.0) + w * m
    else:
        for j, w in Renderer.weights(songs[k], t - songs[k]["start"], F):
            out[(k, j)] = w
    left = plan["total"] - t
    if left < FILM_FADE:
        g = smooth(left / FILM_FADE)
        out = {key: v * g for key, v in out.items()}
    return out


def measure(plan, extra=(), dt=0.1):
    """Every screen in the film with the seconds it is clear (share >= CLEAR_W), the seconds it is on at all, its words, the dissolve into it and out of it, and what it needs.
    `extra` holds opaque overlays an older film drew on top: {name, words, alpha(t)}; they hide what is under them."""
    rows, idx = [], {}
    for k, s in enumerate(plan["songs"]):
        for j, x in enumerate(s["items"]):
            idx[(k, j)] = len(rows)
            words = x.get("words", 0)
            rows.append({"song": s["n"], "title": s["title"], "kind": x["kind"], "name": x.get("key") or Path(str(x["path"])).name, "words": words,
                         "need_clear": round(clear_need(words), 2), "clear": 0.0, "on": 0.0, "first": None, "last": None, "clear_first": None, "clear_last": None})
    for e in extra:
        rows.append({"song": None, "title": "", "kind": "overlay", "name": e["name"], "words": e["words"], "need_clear": round(clear_need(e["words"]), 2),
                     "clear": 0.0, "on": 0.0, "first": None, "last": None, "clear_first": None, "clear_last": None, "alpha": e["alpha"]})
    t = 0.0
    while t < plan["total"]:
        sh = shares_at(plan, t)
        cover = max((e["alpha"](t) for e in extra), default=0.0)
        vals = {(("i", i)): v * (1 - cover) for (k, j), v in sh.items() for i in [idx[(k, j)]]}
        for r_i, e in zip(range(len(rows) - len(extra), len(rows)), extra):
            vals[("i", r_i)] = e["alpha"](t)
        for (_, i), v in vals.items():
            r = rows[i]
            if v > 0.005:
                r["on"] += dt
                r["first"] = t if r["first"] is None else r["first"]
                r["last"] = t
            if v >= CLEAR_W:
                r["clear"] += dt
                r["clear_first"] = t if r["clear_first"] is None else r["clear_first"]
                r["clear_last"] = t
        t += dt
    for r in rows:
        r.pop("alpha", None)
        if r["first"] is None:
            continue
        if r["clear_first"] is None:  # on screen but never clear: reported as too short, no dissolve to measure
            r["fade_in"] = r["fade_out"] = None
            r["on"] = round(r["on"], 1)
            continue
        r["fade_in"] = None if r["first"] <= dt else round(r["clear_first"] - r["first"], 2)  # time spent dissolving in; None = the film opens on it
        r["fade_out"] = None if r["last"] >= plan["total"] - 2 * dt else round(r["last"] - r["clear_last"], 2)
        for key in ("clear", "on"):
            r[key] = round(r[key], 1)
    return rows


def readability(rows, plan_total):
    """The two numbers the build is judged on: screens clear for less than they need, and dissolves into or out of a screen with words shorter than MIN_FADE.
    Both are measured from the shares the renderer draws, not from the settings."""
    short, fades = [], []
    for r in rows:
        if r["first"] is None:
            short.append({**r, "why": "never shown"})
            continue
        if r["clear"] + 0.15 < r["need_clear"]:
            short.append({k: r[k] for k in ("song", "title", "kind", "name", "words", "need_clear", "clear")})
        if r["words"]:
            for side, key in (("in", "fade_in"), ("out", "fade_out")):
                if r[key] is not None and r[key] < MIN_FADE:
                    fades.append({"song": r["song"], "name": r["name"], "side": side, "seconds": r[key]})
    return short, fades


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
    chk["silences"] = len([m for m in re.findall(r"silence_start: ([\d.]+)", sil) if float(m) < seconds - 6.0])  # the song's own quiet tail under the closing fade is by design
    lu = ff("-i", str(film), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-")
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", lu)
    chk["loudness_lufs"] = float(m[-1]) if m else None
    bd = ff("-i", str(film), "-an", "-vf", "blackdetect=d=1:pix_th=0.05", "-f", "null", "-")
    chk["black_runs_over_1s"] = len(re.findall(r"black_start", bd))
    fd = ff("-i", str(film), "-an", "-vf", "freezedetect=n=-60dB:d=8", "-f", "null", "-")
    chk["frozen_runs_over_8s"] = len(re.findall(r"freeze_start", fd))
    # a still picture is allowed only where it is by design: a lyric page, a slide (the opening, a chapter, the end) or the held last frame of a clip that does not loop
    allowed = []
    for s in plan["songs"]:
        lo = 0.0
        for x, hi in zip(s["items"], s["bounds"]):
            if x["kind"] in ("lyrics", "slide") or (x["kind"] == "clip" and not x.get("loop")):
                allowed.append((s["start"] + lo - plan["fade"], s["start"] + hi + plan["fade"]))
            lo = hi
    runs = list(zip(map(float, re.findall(r"freeze_start: ([\d.]+)", fd)), map(float, re.findall(r"freeze_end: ([\d.]+)", fd))))
    if len(runs) < len(re.findall(r"freeze_start", fd)):  # the last run has no end line: it lasts to the end
        runs.append((float(re.findall(r"freeze_start: ([\d.]+)", fd)[-1]), seconds))
    chk["frozen_outside_still_screens"] = [[a + t0, b + t0] for a, b in runs if not any(lo - 0.5 <= a + t0 and b + t0 <= hi + 0.5 for lo, hi in allowed)]
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
    rows = measure(plan)
    for r in rows:  # the middle of each slide's clear window
        if r["kind"] == "slide" and r["clear_first"] is not None:
            marks.append((f"slide-{r['name']}", (r["clear_first"] + r["clear_last"]) / 2))
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
    chk["square_cards_used"] = [str(x["path"]) for s in plan["songs"] for x in s["items"] if x["kind"] in ("card", "lyrics") and not x.get("video")]
    short, fades = readability(rows, plan["total"])
    chk["reading_rule"] = {"words_per_second": READ_WPS, "orient_seconds": ORIENT, "min_clear_seconds": MIN_CLEAR, "min_dissolve_seconds": MIN_FADE, "clear_share": CLEAR_W,
                           "picture_crossfade_seconds": plan["fade"], "song_join_seconds": plan["join"]}
    chk["screens"] = len(rows)
    chk["screens_too_short"] = short  # every screen: slides, cards, lyric pages, clips, comic pages, portraits
    chk["transitions_too_short"] = fades
    chk["screens_dropped_to_fit"] = [[s["n"], Path(d).name] for s in plan["songs"] for d in s.get("dropped", [])]
    (Path(out) / "screens.json").write_text(json.dumps(rows, indent=1))
    first = [r for r in rows if r["first"] is not None and r["first"] < 15]
    chk["screens_in_first_15s"] = [[r["name"], r["clear"]] for r in sorted(first, key=lambda r: r["first"])]
    chk.update(still_windows(film, rows, t0, seconds))
    chk["readable"] = not (short or fades or chk["unsteady_clear_windows"] or not chk["opens_on_one_clean_screen"])
    return chk


def gray_frames(film, rel0, n):
    """n tiny gray frames, 2 a second, from rel0 seconds into the film."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{rel0:.2f}", "-i", str(film), "-an", "-vf", "fps=2,scale=64:36,format=gray", "-frames:v", str(n), "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    return [raw[i:i + 2304] for i in range(0, len(raw) - 2303, 2304)]


def diff(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


TAIL = 1.6  # seconds trimmed off each end of a clear window: the last tenth of a dissolve (an 8 s join takes 1.6 s over it) still moves the picture
STEADY = 1.5  # mean grey-level change per half second inside a still screen's clear window; a dissolve moves 5 or more


def still_windows(film, rows, t0, seconds):
    """Measure the rendered film by frame difference: a slide or a lyric page must not change inside its clear window, and the film must open on one steady screen."""
    frames = gray_frames(film, 0, int(seconds * 2))
    at = lambda t: frames[min(len(frames) - 1, max(0, round((t - t0) * 2)))]
    bad = []
    for r in rows:
        if r["kind"] not in ("slide", "lyrics") or r["clear_first"] is None or r["clear"] < 1:
            continue
        lo, hi = r["clear_first"] + TAIL, r["clear_last"] - TAIL
        if hi - lo < 1:
            continue
        if lo < t0 or hi > t0 + seconds - 1:
            continue
        worst = max((diff(at(lo + i * 0.5), at(lo + i * 0.5 + 0.5)) for i in range(int((hi - lo) * 2) - 1)), default=0.0)
        if worst > STEADY:
            bad.append({"name": r["name"], "song": r["song"], "worst_change": round(worst, 2)})
    opening = max((diff(at(t0 + i * 0.5), at(t0 + i * 0.5 + 0.5)) for i in range(8)), default=0.0) if t0 == 0 else 0.0
    return {"unsteady_clear_windows": bad, "opening_first_4s_worst_change": round(opening, 2), "opens_on_one_clean_screen": opening <= STEADY}
    return chk


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["plan", "measure", "render", "check"])
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
    if args.cmd == "measure":  # the reading checks on the plan alone, nothing rendered
        rows = measure(plan)
        short, fades = readability(rows, total)
        (out / "screens.json").write_text(json.dumps(rows, indent=1))
        print(json.dumps({"screens": len(rows), "screens_too_short": short, "transitions_too_short": fades}, indent=1))
        return 0 if not (short or fades) else 1
    seconds = args.seconds or (total - args.start)
    seconds = min(seconds, total - args.start)
    if args.cmd == "check":  # the checks again on a film already rendered in out/
        chk = run_checks(out / "film.mp4", plan, args.start, seconds, out)
        (out / "checks.json").write_text(json.dumps(chk, indent=1))
        print(json.dumps(chk, indent=1))
        return 0 if chk["readable"] else 1
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
    return 0 if chk["readable"] else 1  # a film with a screen too short to read, or a dissolve too brief, fails the build


if __name__ == "__main__":
    sys.exit(main())
