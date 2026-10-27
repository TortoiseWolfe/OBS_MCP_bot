#!/usr/bin/env python3
"""Render one loop file for a set: songs in order, a card, stills with a now-playing caption.

usage: build_loop.py sets/set1.json [--out DIR] [--dry-run]
Audio: each song is loudness-normalised (two passes, ffmpeg loudnorm) to -16 LUFS, then joined.
Video: 1280x720, 30 fps, keyframe every 2 s, CBR 3500 kbps H.264; AAC 160 kbps 48 kHz.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
LUFS = -16.0
ROBOT_RING = {"Ivory": "#2fb8ff", "Crash": "#ff7a1a", "Chops": "#5fd04a", "Reed": "#1fc9b4",
              "Brass": "#ffd23a", "Verse": "#ff4f9a", "Form": "#a56cff"}


def sh(cmd, timeout=900):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)


def duration(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], 60).stdout)


def measure(path):
    """First loudnorm pass; returns the measured values ffmpeg prints as JSON on stderr."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                        f"loudnorm=I={LUFS}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    return json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.DOTALL).group(0))


def normalise(src, dst):
    m = measure(src)
    af = (f"loudnorm=I={LUFS}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
          "aresample=48000")
    sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-af", af, "-ar", "48000", "-ac", "2", str(dst)], 300)


def font(art, name, size):
    return ImageFont.truetype(str(art / "fonts" / name), size)


def background(art, cover):
    c = Image.open(art / cover).convert("RGB")
    bg = c.resize((W, W)).crop((0, (W - H) // 2, W, (W - H) // 2 + H)).filter(ImageFilter.GaussianBlur(18))
    return Image.eval(bg, lambda v: int(v * 0.35))


def portrait(art, name, d):
    im = Image.open(art / "portraits" / f"{name}.png").convert("RGBA").resize((d, d))
    mask = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d - 1, d - 1), fill=255)
    out = Image.new("RGBA", (d + 16, d + 16), (0, 0, 0, 0))
    ring = ROBOT_RING[name]
    ImageDraw.Draw(out).ellipse((0, 0, d + 15, d + 15), fill=ring)
    out.paste(im, (8, 8), mask)
    return out


def centred(dr, y, text, f, fill="#fff3c4"):
    w = dr.textlength(text, font=f)
    dr.text(((W - w) / 2, y), text, font=f, fill=fill, stroke_width=2, stroke_fill="#1a1006")


def song_still(art, cover, item, path):
    img = background(art, cover).convert("RGBA")
    dr = ImageDraw.Draw(img)
    cv = Image.open(art / cover).convert("RGB").resize((330, 330))
    img.paste(cv, (60, 150))
    dr.rectangle((60, 150, 390, 480), outline="#d9a441", width=4)
    dr.text((430, 130), "NOW PLAYING", font=font(art, "Rye-Regular.ttf", 34), fill="#d9a441")
    title = item["title"]
    dr.text((430, 185), title, font=font(art, "AlfaSlabOne-Regular.ttf", 46 if len(title) < 28 else 34), fill="#fff3c4")
    names = item["robots"]
    dr.text((430, 270), "with " + (", ".join(names) if len(names) < 7 else "the whole band: " + ", ".join(names)),
            font=font(art, "LilitaOne-Regular.ttf", 28 if len(names) < 7 else 22), fill="#e8d9b0")
    d = 120 if len(names) <= 3 else 86
    x = 430
    for n in names:
        p = portrait(art, n, d)
        img.alpha_composite(p, (x, 340)); x += d + 28
    dr.text((60, 650), "Music made with AI", font=font(art, "LilitaOne-Regular.ttf", 30), fill="#ffd23a")
    dr.text((W - 330, 650), "The Band Wagon", font=font(art, "Rye-Regular.ttf", 30), fill="#d9a441")
    img.convert("RGB").save(path)


def card_still(art, cover, item, path):
    img = background(art, cover).convert("RGBA")
    dr = ImageDraw.Draw(img)
    f = font(art, "AlfaSlabOne-Regular.ttf", 76)
    centred(dr, 200, item["lines"][0], f)
    centred(dr, 310, item["lines"][1], f, "#ffd23a")
    x = (W - (2 * 150 + 80)) // 2
    for n, who in (("1", "Ivory"), ("2", "Chops")):
        img.alpha_composite(portrait(art, who, 150), (x, 450)); 
        dr.text((x + 60, 620), n, font=font(art, "Rye-Regular.ttf", 60), fill="#fff3c4", stroke_width=2, stroke_fill="#1a1006")
        x += 230
    dr.text((60, 670), "Music made with AI", font=font(art, "LilitaOne-Regular.ttf", 30), fill="#ffd23a")
    img.convert("RGB").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("setfile"); ap.add_argument("--out", default=str(Path(__file__).parent / "out"))
    ap.add_argument("--stills-only", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(a.setfile))
    audio = Path(cfg["audio_dir"]).expanduser(); art = Path(cfg["art_dir"]).expanduser()
    out = Path(a.out); work = out / cfg["name"]; work.mkdir(parents=True, exist_ok=True)

    segs = []  # (still, audio file, seconds)
    for i, it in enumerate(cfg["items"]):
        still = work / f"{i:02d}.png"
        if it["kind"] == "song":
            song_still(art, cfg["cover"], it, still)
            segs.append((still, audio / it["file"], None))
        else:
            card_still(art, cfg["cover"], it, still)
            segs.append((still, None, it["seconds"]))
    if a.stills_only:
        return
    parts = []
    for i, (still, src, secs) in enumerate(segs):
        wav = work / f"{i:02d}.wav"
        if src:
            normalise(src, wav)
        else:  # card: quiet room tone so the audio track never has a gap
            sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-t", str(secs), str(wav)], 60)
        parts.append((still, wav, duration(wav)))

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for still, wav, secs in parts:
        cmd += ["-loop", "1", "-framerate", "30", "-t", f"{secs:.3f}", "-i", str(still), "-i", str(wav)]
    n = len(parts)
    fc = "".join(f"[{2*i}:v]fps=30,format=yuv420p[v{i}];" for i in range(n))
    fc += "".join(f"[v{i}][{2*i+1}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    loop = out / f"{cfg['name']}-loop.mp4"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-r", "30", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
            "-b:v", "3500k", "-minrate", "3500k", "-maxrate", "3500k", "-bufsize", "7000k",
            "-x264-params", "nal-hrd=cbr:force-cfr=1",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(loop)]
    sh(cmd, 1800)
    print(f"{loop} {duration(loop):.1f} s")


if __name__ == "__main__":
    main()
