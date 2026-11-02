"""Put a quiet music bed under the silent bumpers of an air-format tutorial file, without re-encoding the picture.

Each tutorial file opens with a silent intro and card and closes with a silent outro. This copies the picture stream as it
is (so the constant bitrate and the 2 s keyframes are untouched) and re-encodes only the sound: the lesson audio stays
exactly where it was, and a stretch of one instrumental band track plays under the opening and another stretch under the
closing, at a fixed loudness (about -26 LUFS), with a 1 s fade at each edge of the section.

usage:
  python -m playout.tutorials.bed SRC.mp4 OUT.mp4 --bed TRACK.mp3 --lead 15 --tail 10
         [--lead-start 0] [--tail-start 150] [--bed-lufs -26] [--under-lesson] [--mid-lufs -25] [--mid-start 0] [--mid-track GAPLESS.mp3]

--under-lesson also lays the same track quietly (ducked by the narration with a sidechain, so it sits about 20 dB under the voice while it talks and rises in the pauses) under the whole file, so
the near-1 s digital silence the narration leaves after every sentence never drops to zero. The narration itself is not touched.
"""
import argparse
import json
import subprocess
import sys

from playout.tutorials.encode_air import AUDIO_KBPS, duration, measure_lufs

BED_LUFS = -26.0
MID_LUFS = -25.0  # level of the bed in the pauses between sentences when --under-lesson is used (it is ducked while the voice talks)
DUCK_THRESHOLD = 0.03  # narration level (linear, about -30 dB) above which the bed is pushed down
DUCK_RATIO = 3.0
DUCK_ATTACK_MS = 20
DUCK_RELEASE_MS = 400  # slow enough that the 0.05 to 0.3 s breaths inside a sentence do not make the bed pump
FADE = 1.0
SILENT_DB = -60.0  # the window being filled must already be quieter than this


def section_gain_db(measured_lufs, target=BED_LUFS):
    """Gain that moves a section measured at `measured_lufs` to `target`."""
    return target - measured_lufs


def bed_filter(total, lead, tail, lead_gain, tail_gain, lead_start=0.0, tail_start=150.0, mid_gain=None, mid_start=0.0, final_gain=0.0):
    """Filter graph: input 0 is the air file, input 1 the lead bed track, input 2 the tail bed track.

    With `mid_gain` set, input 3 (the same track) is also laid under the whole file at that gain, with a 1 s fade at each end. That bed is ducked by the narration (sidechain), so it rises only in the pauses."""
    fmt = "aresample=48000,aformat=channel_layouts=stereo"

    def section(idx, label, start, length, gain, delay):
        chain = [f"[{idx}:a]atrim=start={start:.3f}:duration={length:.3f}", "asetpts=PTS-STARTPTS", fmt, f"volume={gain:.3f}dB",
                 f"afade=t=in:st=0:d={FADE}", f"afade=t=out:st={length - FADE:.3f}:d={FADE}"]
        if delay > 0:
            chain.append(f"adelay={int(round(delay * 1000))}:all=1")
        chain.append(f"apad=whole_dur={total:.3f}")
        return ",".join(chain) + f"[{label}]"

    parts = [
        f"[0:a]{fmt}" + ("," + "asplit=2[main][sc]" if mid_gain is not None else "[main]"),
        section(1, "bedA", lead_start, lead, lead_gain, 0.0),
        section(2, "bedB", tail_start, tail, tail_gain, total - tail),
    ]
    labels, n = "[main][bedA][bedB]", 3
    if mid_gain is not None:
        parts.append(section(3, "bedM0", mid_start, total, mid_gain, 0.0))
        parts.append(f"[bedM0][sc]sidechaincompress=threshold={DUCK_THRESHOLD}:ratio={DUCK_RATIO}:attack={DUCK_ATTACK_MS}:release={DUCK_RELEASE_MS}:makeup=1[bedM]")
        labels, n = labels + "[bedM]", 4
    parts.append(f"{labels}amix=inputs={n}:normalize=0:duration=first:dropout_transition=0,atrim=0:{total:.3f},asetpts=PTS-STARTPTS" + (f",volume={final_gain:.3f}dB" if final_gain else "") + "[a]")
    return ";".join(parts)


def window_level_db(path, start, length):
    """Mean volume (dB) of the audio between start and start+length, from ffmpeg's volumedetect."""
    r = subprocess.run(["nice", "-n", "19", "ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-ss", f"{start:.3f}", "-t", f"{length:.3f}",
                        "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    for line in r.stderr.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0])
    return float("-inf")  # fully digital silence has no mean line on some builds


def bed_section_lufs(track, start, length):
    """Integrated loudness of one section of the bed track (cut into a temp wav by pipe)."""
    r = subprocess.run(["nice", "-n", "19", "ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-ss", f"{start:.3f}", "-t", f"{length:.3f}",
                        "-i", str(track), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    tail = r.stderr.rsplit("Summary:", 1)[-1]
    for line in tail.splitlines():
        line = line.strip()
        if line.startswith("I:"):
            return float(line.split()[1])
    raise RuntimeError("no loudness summary for the bed section")


def add_bed(src, out, track, lead, tail, lead_start=0.0, tail_start=150.0, bed_lufs=BED_LUFS, under_lesson=False, mid_lufs=MID_LUFS, mid_start=0.0, mid_track=None,
            target_lufs=-16.0, tolerance=0.2):
    total = duration(src)
    for name, s, n in (("opening", 0.0, lead), ("closing", total - tail, tail)):
        level = window_level_db(src, s, n)
        if level > SILENT_DB:
            raise SystemExit(f"{src}: the {name} window is not silent (mean {level} dB); refusing to lay a bed over sound")
    g1 = section_gain_db(bed_section_lufs(track, lead_start, lead), bed_lufs)
    g2 = section_gain_db(bed_section_lufs(track, tail_start, tail), bed_lufs)
    mid_gain, mid_track = None, mid_track or track
    if under_lesson:
        if duration(mid_track, "a") < mid_start + total:
            raise SystemExit(f"{mid_track} is shorter than the {total:.0f} s file from {mid_start:.0f} s; a longer track or a loop is needed")
        mid_gain = section_gain_db(bed_section_lufs(mid_track, mid_start, total), mid_lufs)
    result = _mix(src, out, track, mid_track, total, lead, tail, g1, g2, lead_start, tail_start, mid_gain, mid_start, 0.0)
    if under_lesson and abs(result["lufs"] - target_lufs) > tolerance:  # the mix reads a little quieter than the file it came from: lift all of it
        result = _mix(src, out, track, mid_track, total, lead, tail, g1, g2, lead_start, tail_start, mid_gain, mid_start, target_lufs - result["lufs"])
    return result


def _mix(src, out, track, mid_track, total, lead, tail, g1, g2, lead_start, tail_start, mid_gain, mid_start, final_gain):
    under_lesson = mid_gain is not None
    cmd = ["nice", "-n", "19", "timeout", "3600", "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(src), "-i", str(track), "-i", str(track)] + (["-i", str(mid_track)] if under_lesson else []) + [
           "-filter_complex", bed_filter(total, lead, tail, g1, g2, lead_start, tail_start, mid_gain, mid_start, final_gain),
           "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", "-ar", "48000", "-ac", "2",
           "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, timeout=3700)
    return {"out": str(out), "seconds": round(total, 3), "lead_gain_db": round(g1, 2), "tail_gain_db": round(g2, 2),
            "mid_gain_db": None if mid_gain is None else round(mid_gain, 2), "final_gain_db": round(final_gain, 2), "lufs": measure_lufs(out)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--bed", required=True)
    ap.add_argument("--lead", type=float, default=15.0)
    ap.add_argument("--tail", type=float, default=10.0)
    ap.add_argument("--lead-start", type=float, default=0.0)
    ap.add_argument("--tail-start", type=float, default=150.0)
    ap.add_argument("--bed-lufs", type=float, default=BED_LUFS)
    ap.add_argument("--under-lesson", action="store_true")
    ap.add_argument("--mid-lufs", type=float, default=MID_LUFS)
    ap.add_argument("--mid-start", type=float, default=0.0)
    ap.add_argument("--mid-track", default=None, help="track for the under-lesson bed (default: --bed); it should have no gaps of its own")
    a = ap.parse_args(argv)
    print(json.dumps(add_bed(a.src, a.out, a.bed, a.lead, a.tail, a.lead_start, a.tail_start, a.bed_lufs, a.under_lesson, a.mid_lufs, a.mid_start, a.mid_track)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
