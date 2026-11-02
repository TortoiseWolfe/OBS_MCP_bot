"""Encode one tutorial episode (intro, card, content, outro) into ONE air-format file, once, offline.

Air format: constant bitrate H.264 (CBR, nal-hrd), keyframe every 2 s (60 frames at 30 fps), 30 fps, AAC 48 kHz stereo.
The four segments are joined by the concat filter in one pass, so timestamps run on without a break. Each segment's audio
is padded or cut to its own video length first, so a few milliseconds of extra audio never builds into drift.

usage:
  python -m playout.tutorials.encode_air episode OUT.mp4 intro.mp4 card.mp4 content.mp4 outro.mp4 [--height 1080] [--kbps 2300]
  python -m playout.tutorials.encode_air sample SRC.mp4 START SECONDS OUTDIR   (1080p vs 720p readability test, no stream)
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

FPS = 30
GOP = 2 * FPS
AUDIO_KBPS = 128
TARGET_LUFS = -16.0


def parse_duration(text):
    """First number in ffprobe csv output ('10.000000,' has a trailing comma)."""
    return float(text.strip().splitlines()[0].split(",")[0])


def duration(path, stream="v"):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", f"{stream}:0", "-show_entries", "stream=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60)
    return parse_duration(r.stdout)


def video_args(kbps):
    """x264 CBR flags: min = max = target rate, one 2 s buffer, a keyframe exactly every 2 s."""
    return ["-c:v", "libx264", "-preset", "medium", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-g", str(GOP), "-keyint_min", str(GOP), "-sc_threshold", "0",
            "-b:v", f"{kbps}k", "-minrate", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{2 * kbps}k",
            "-x264-params", "nal-hrd=cbr:force-cfr=1"]


def audio_args():
    return ["-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", "-ar", "48000", "-ac", "2"]


def filter_graph(durations, height, gain_db=0.0):
    """Concat filter graph for n segments with the given video lengths."""
    parts = []
    for i, d in enumerate(durations):
        parts.append(f"[{i}:v]fps={FPS},scale=-2:{height}:flags=lanczos,setsar=1,format=yuv420p[v{i}]")
        parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{d:.5f},asetpts=PTS-STARTPTS[a{i}]")
    ins = "".join(f"[v{i}][a{i}]" for i in range(len(durations)))
    tail = f"{ins}concat=n={len(durations)}:v=1:a=1[v][a0]"
    if abs(gain_db) > 0.05:
        tail += f";[a0]volume={gain_db:.2f}dB[a]"
    else:
        tail += ";[a0]anull[a]"
    return ";".join(parts + [tail])


def measure_lufs(path):
    """Integrated loudness (LUFS) of the file's audio, from ffmpeg's ebur128 summary."""
    r = subprocess.run(["nice", "-n", "19", "ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", str(path), "-vn",
                        "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, timeout=1800)
    tail = r.stderr.rsplit("Summary:", 1)[-1]
    for line in tail.splitlines():
        line = line.strip()
        if line.startswith("I:"):
            return float(line.split()[1])
    raise RuntimeError("no loudness summary in ffmpeg output")


def encode(inputs, out, height=1080, kbps=2300, gain_db=0.0, threads=6):
    durs = [duration(p) for p in inputs]
    cmd = ["nice", "-n", "19", "timeout", "7200", "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-threads", str(threads)]
    for p in inputs:
        cmd += ["-i", str(p)]
    cmd += ["-filter_complex", filter_graph(durs, height, gain_db), "-map", "[v]", "-map", "[a]"]
    cmd += video_args(kbps) + audio_args() + ["-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, timeout=7300)
    return sum(durs)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("episode")
    e.add_argument("out")
    e.add_argument("segments", nargs=4)
    e.add_argument("--height", type=int, default=1080)
    e.add_argument("--kbps", type=int, default=2300)
    e.add_argument("--gain", type=float, default=0.0)
    s = sub.add_parser("sample")
    s.add_argument("src")
    s.add_argument("start", type=float)
    s.add_argument("seconds", type=float)
    s.add_argument("outdir")
    a = ap.parse_args(argv)
    if a.cmd == "episode":
        total = encode(a.segments, a.out, a.height, a.kbps, a.gain)
        print(json.dumps({"out": a.out, "source_seconds": round(total, 3)}))
        return 0
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for h in (1080, 720):
        dst = outdir / f"sample-{h}.mp4"
        cmd = ["nice", "-n", "19", "timeout", "900", "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
               "-ss", str(a.start), "-t", str(a.seconds), "-i", a.src,
               "-vf", f"fps={FPS},scale=-2:{h}:flags=lanczos,setsar=1,format=yuv420p", "-an"] + video_args(2300) + [str(dst)]
        subprocess.run(cmd, check=True, timeout=1000)
        print(dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
