"""Narration with short pauses: generate a section's speech with Edge TTS, then shorten every long silence.

Edge TTS leaves about 0.8 to 1 s of digital silence after every sentence. Over a 25 minute lesson that is hundreds of dead
gaps. This keeps each pause but cuts it down to PAUSE seconds (cut from the middle of the silence, so no click), and moves the
sentence-boundary times the same amount so the on-screen bullets still appear 0.5 s before the voice reads them.

usage (same arguments render_episode.py gives generate_narration.py):
  python -m playout.tutorials.narration --text TEXT --output OUT.mp3 --timing-output TIMING.json [--voice en-US-GuyNeural]
"""
import argparse
import asyncio
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PAUSE = 0.30       # seconds of silence left after a sentence
MIN_CUT = 0.45     # silences shorter than this are left alone
NOISE_DB = -50.0   # below this level counts as silence
TICKS = 10_000_000  # edge-tts times are in 100 ns ticks
VOICE = "en-US-GuyNeural"


def parse_silences(log):
    """[(start, end)] from ffmpeg silencedetect output. A silence still open at the end of the file is closed at `end`
    only if ffmpeg printed it; an unmatched start is dropped."""
    starts = [float(m) for m in re.findall(r"silence_start: (-?[\d.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", log)]
    return [(max(s, 0.0), e) for s, e in zip(starts, ends)]


def plan_cuts(silences, keep=PAUSE, min_cut=MIN_CUT):
    """[(cut_start, cut_end)] to remove: each silence longer than min_cut shrinks to `keep`, cut from its middle."""
    cuts = []
    for s, e in silences:
        if e - s > min_cut and e - s > keep:
            surplus = (e - s) - keep
            mid = (s + e) / 2
            cuts.append((mid - surplus / 2, mid + surplus / 2))
    return cuts


def remap(t, cuts):
    """Time `t` (seconds) in the original audio -> time in the shortened audio."""
    removed = 0.0
    for a, b in cuts:
        if t >= b:
            removed += b - a
        elif t > a:
            removed += t - a
    return t - removed


def keep_ranges(cuts, total):
    """The stretches that stay: [(start, end)] between the cuts."""
    out, pos = [], 0.0
    for a, b in cuts:
        if a > pos:
            out.append((pos, a))
        pos = b
    if total > pos:
        out.append((pos, total))
    return out


def remap_boundaries(boundaries, cuts):
    """edge-tts boundary dicts (offset and duration in ticks) with times moved by the cuts."""
    out = []
    for b in boundaries:
        start = remap(b["offset"] / TICKS, cuts)
        end = remap((b["offset"] + b["duration"]) / TICKS, cuts)
        out.append({**b, "offset": round(start * TICKS), "duration": max(round((end - start) * TICKS), 0)})
    return out


def run_ffmpeg(args, timeout=600):
    return subprocess.run(["nice", "-n", "19", "timeout", str(timeout), "ffmpeg", "-hide_banner", "-nostats", *args],
                          capture_output=True, text=True)


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, timeout=60)
    return float(r.stdout.strip())


def tighten(src, dest, keep=PAUSE, min_cut=MIN_CUT):
    """Write `dest` (mp3) = `src` with its long silences shortened. Returns the cuts [(start, end)] made."""
    log = run_ffmpeg(["-i", str(src), "-af", f"silencedetect=n={NOISE_DB}dB:d={min_cut}", "-f", "null", "-"]).stderr
    cuts = plan_cuts(parse_silences(log), keep, min_cut)
    total = probe_duration(src)
    if not cuts:
        Path(dest).write_bytes(Path(src).read_bytes())
        return []
    ranges = keep_ranges(cuts, total)
    parts = [f"[0:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS[p{i}]" for i, (a, b) in enumerate(ranges)]
    fc = ";".join(parts) + ";" + "".join(f"[p{i}]" for i in range(len(ranges))) + f"concat=n={len(ranges)}:v=0:a=1[a]"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(fc)
        script = f.name
    try:
        r = run_ffmpeg(["-y", "-i", str(src), "-filter_complex_script", script, "-map", "[a]", "-c:a", "libmp3lame",
                        "-b:a", "96k", str(dest)])
    finally:
        Path(script).unlink(missing_ok=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-400:])
    return cuts


async def speak_once(text, voice):
    import edge_tts  # noqa: PLC0415 - only the lane venv has it
    boundaries, chunks = [], []
    async for chunk in edge_tts.Communicate(text, voice).stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            boundaries.append({"offset": chunk["offset"], "duration": chunk["duration"], "text": chunk["text"]})
    return b"".join(chunks), boundaries


async def speak(text, output, voice, timing_output, tries=4, wait=5.0):
    """Edge TTS now and then answers with no audio at all; ask again after a pause before giving up."""
    for attempt in range(1, tries + 1):
        try:
            data, boundaries = await speak_once(text, voice)
            break
        except Exception as e:  # noqa: BLE001 - the service raises its own error types
            if attempt == tries:
                raise
            print(f"TTS try {attempt} failed ({type(e).__name__}), asking again", file=sys.stderr)
            await asyncio.sleep(wait * attempt)
    Path(output).write_bytes(data)
    return boundaries


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--voice", default=VOICE)
    ap.add_argument("--timing-output")
    a = ap.parse_args(argv)
    raw = Path(a.output).with_suffix(".raw.mp3")
    boundaries = asyncio.run(speak(a.text, str(raw), a.voice, a.timing_output))
    cuts = tighten(raw, a.output)
    raw.unlink(missing_ok=True)
    if a.timing_output:
        Path(a.timing_output).write_text(json.dumps(remap_boundaries(boundaries, cuts)))
    print(f"Audio: {a.output} ({len(cuts)} pauses shortened to {PAUSE} s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
