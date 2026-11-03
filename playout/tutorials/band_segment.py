"""Build one band segment for the 24/7 rotation: a band member's animated turnaround and 3D still, under one public band track.

The picture alternates the member's silent turnaround clip (played twice) and the still, fitted inside 1080p without
stretching (a blurred, darkened copy of the same picture fills the side bars), with the member's name and the track title
on screen. The sound is one public ScriptHammer band track, trimmed to the stretch that has no silence in it, faded at each
end and set to -16 LUFS (loudness) like the tutorials. The finished file is encoded the way the tutorials are: 1080p, constant
2300 kbps, a keyframe every 2 s, AAC (Advanced Audio Coding) 48 kHz stereo. It is then checked with airproof and a silence scan.

usage:
  python -m playout.tutorials.band_segment build MEMBER OUT.mp4 [--in-dir DIR] [--audio-dir DIR] [--work DIR]
  python -m playout.tutorials.band_segment list
"""
import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

from playout.tutorials.bed import bed_section_lufs
from playout.tutorials.encode_air import FPS, TARGET_LUFS, audio_args, duration, measure_lufs, video_args

W, H = 1920, 1080
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MARGIN_X, MARGIN_Y = 64, 36  # the layout rule's safe margins at 1080p
TURN_REPEATS = 2             # the 8 s turnaround plays twice, then the still
STILL_SECONDS = 12.0
FADE_IN, FADE_OUT = 1.0, 2.0

# member -> (title on screen, file stem, public track id, track title, start s, end s in the track file).
# The start and end skip the near-silent edges and any gap inside the track (found with silencedetect at -45 dB).
# The tracks are the darkest of the 19 public ones by measured brightness (share of energy above 3 kHz, under 3.5 %).
BAND = {
    "Brass": ("Brass", "Brass", "n12", "Signal Lost, Signal Found", 1.4, 144.0),
    "Chops": ("Chops", "Chops", "psy-1", "The Doctor Listens", 0.9, 149.2),
    "Crash": ("Crash", "Crash", "fusion-1", "Breakbeat Bots", 39.5, 144.4),
    "Ivory": ("Ivory", "Ivory", "n11", "Ghost in the Music Box", 0.0, 147.4),
    "Reed": ("Reed", "Reed", "n10", "Static Snow", 0.6, 146.8),
    "Chorus": ("Chorus", "Verse", "n05", "The Night Watch", 8.3, 121.4),
}


def frame_round(seconds):
    """Length rounded down to a whole number of frames, so audio and picture end together."""
    return math.floor(seconds * FPS + 1e-6) / FPS


def window_seconds(start, end):
    return frame_round(end - start)


def cycle_files(total, turn_file, still_file, turn_len, still_len=STILL_SECONDS, repeats=TURN_REPEATS):
    """The file list (in order) that fills `total` seconds: turnaround x repeats, then the still, over and over."""
    block = repeats * turn_len + still_len
    n = math.ceil(total / block)
    return ([turn_file] * repeats + [still_file]) * n


def concat_list(files):
    return "".join(f"file '{f}'\n" for f in files)


def box_width(name, title):
    """Width of the name box: the wider line (DejaVu Sans Bold runs about 0.62 em a character) plus padding either side."""
    return int(max(len(name) * 84 * 0.72, len(title) * 38 * 0.62)) + 2 * 28


def fit_filter(banner_name, banner_title, box_w, fps=FPS):
    """Fit one input inside W x H without stretching (blurred copy behind), then draw the name box. Text comes from files."""
    box_h = 168
    y0 = H - MARGIN_Y - box_h
    return (
        f"[0:v]fps={fps},split=2[bg][fg];"
        f"[bg]scale=192:108:force_original_aspect_ratio=increase,crop=192:108,gblur=sigma=3,scale={W}:{H}:flags=bicubic,eq=brightness=-0.3[b];"
        f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,setsar=1[f];"
        f"[b][f]overlay=(W-w)/2:(H-h)/2,"
        f"drawbox=x={MARGIN_X}:y={y0}:w={box_w}:h={box_h}:color=black@0.65:t=fill,"
        f"drawtext=fontfile={FONT}:textfile={banner_name}:fontcolor=white:fontsize=84:x={MARGIN_X + 28}:y={y0 + 12},"
        f"drawtext=fontfile={FONT}:textfile={banner_title}:fontcolor=white:fontsize=38:x={MARGIN_X + 28}:y={y0 + 118},"
        f"format=yuv420p[v]"
    )


def _run(cmd, timeout):
    subprocess.run(cmd, check=True, timeout=timeout)


def make_part(src, out, seconds, name_file, title_file, box_w, still):
    """Near-lossless fitted copy of the turnaround clip (or the still held for `seconds`), name box included."""
    cmd = ["nice", "-n", "19", "timeout", "900", "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    if still:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{seconds:.3f}"]
    cmd += ["-i", str(src), "-filter_complex", fit_filter(name_file, title_file, box_w), "-map", "[v]", "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-pix_fmt", "yuv420p", "-r", str(FPS), "-g", "30", str(out)]
    _run(cmd, 1000)


def build(member, out, in_dir, audio_dir, work, kbps=2300):
    name, stem, track_id, title, start, end = BAND[member]
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    track = Path(audio_dir) / f"bw-{track_id}.mp3"
    (work / "name.txt").write_text(name)
    (work / "title.txt").write_text(title)
    bw = box_width(name, title)
    turn, still = work / "turn.mp4", work / "still.mp4"
    make_part(Path(in_dir) / f"{stem}-turntable.mp4", turn, 0, work / "name.txt", work / "title.txt", bw, False)
    make_part(Path(in_dir) / f"{stem}-still.png", still, STILL_SECONDS, work / "name.txt", work / "title.txt", bw, True)
    total = window_seconds(start, end)
    (work / "list.txt").write_text(concat_list(cycle_files(total, turn, still, duration(turn))))
    gain = TARGET_LUFS - bed_section_lufs(track, start, total)

    def encode(extra_gain):
        af = (f"aresample=48000,aformat=channel_layouts=stereo,volume={gain + extra_gain:.3f}dB,alimiter=limit=0.89,"
              f"afade=t=in:st=0:d={FADE_IN},afade=t=out:st={total - FADE_OUT:.3f}:d={FADE_OUT},apad,atrim=0:{total:.3f}")
        vf = f"fade=t=in:st=0:d={FADE_IN},fade=t=out:st={total - FADE_IN:.3f}:d={FADE_IN},format=yuv420p"
        cmd = ["nice", "-n", "19", "timeout", "3600", "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-threads", "6",
               "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"), "-ss", f"{start:.3f}", "-t", f"{total:.3f}", "-i", str(track),
               "-map", "0:v", "-map", "1:a", "-vf", vf, "-af", af, "-t", f"{total:.3f}"]
        cmd += video_args(kbps) + audio_args() + ["-movflags", "+faststart", str(out)]
        _run(cmd, 3700)
        return measure_lufs(out)

    lufs = encode(0.0)
    if abs(lufs - TARGET_LUFS) > 0.3:
        lufs = encode(TARGET_LUFS - lufs)
    return {"member": member, "name_on_screen": name, "track": track_id, "track_title": title, "window": [start, end],
            "seconds": total, "lufs": round(lufs, 2), "out": str(out)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    b = sub.add_parser("build")
    b.add_argument("member", choices=sorted(BAND))
    b.add_argument("out")
    b.add_argument("--in-dir", default=os.path.expanduser("~/clawd-twitch/air/band-in/2026-11-03-nx01"))
    b.add_argument("--audio-dir", default=os.path.expanduser("~/bandwagon-kit-out/audio"))
    b.add_argument("--work", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "list":
        print(json.dumps(BAND, indent=1))
        return 0
    work = a.work or os.path.join(os.path.dirname(a.out) or ".", f".work-{a.member}")
    print(json.dumps(build(a.member, a.out, a.in_dir, a.audio_dir, work)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
