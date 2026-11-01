"""Sound and picture checks on one segment file, from one ffmpeg pass.

One decode runs silencedetect (gaps), ebur128 (loudness and true peak), blackdetect and freezedetect, and the stream
facts come from ffprobe. Pure parsing functions are separate so tests can feed them captured ffmpeg text.
"""
import re
import subprocess

from . import frames

EXPECT_W, EXPECT_H, EXPECT_FPS = 1920, 1080, 30.0
SILENCE_DB = -50          # same floor the band checks use
SILENCE_MIN = 0.15        # shortest gap we list
DEAD_AIR = 2.0            # a gap this long is dead air (BLOCKER)
LOUD_JUMP = 3.0           # LU between segments of one episode
LEN_MISMATCH = 0.5        # audio vs video length, seconds
BLACK_MIN = 1.0
FREEZE_MIN = 30.0
SILENT_LUFS = -60.0       # integrated loudness at or under this is a silent track
TRUE_PEAK_MAX = -0.1      # dBTP at or above this is clipping

_SIL_START = re.compile(r"silence_start: (-?[\d.]+)")
_SIL_END = re.compile(r"silence_end: (-?[\d.]+) \| silence_duration: ([\d.]+)")
_BLACK = re.compile(r"black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)")
_FREEZE_S = re.compile(r"freeze_start: ([\d.]+)")
_FREEZE_E = re.compile(r"freeze_end: ([\d.]+)")
_FREEZE_D = re.compile(r"freeze_duration: ([\d.]+)")


def parse_silences(text, total):
    """[(start, end)] from silencedetect lines; a start without an end runs to `total`."""
    out, start = [], None
    for line in text.splitlines():
        m = _SIL_START.search(line)
        if m:
            start = float(m.group(1))
            continue
        m = _SIL_END.search(line)
        if m:
            end = float(m.group(1))
            d = float(m.group(2))
            out.append((max(end - d, 0.0), end))
            start = None
    if start is not None:
        out.append((start, total))
    return out


def parse_black(text):
    return [(float(a), float(b)) for a, b, _ in _BLACK.findall(text)]


def parse_freezes(text, total):
    starts = [float(x) for x in _FREEZE_S.findall(text)]
    ends = [float(x) for x in _FREEZE_E.findall(text)]
    out = []
    for i, s in enumerate(starts):
        out.append((s, ends[i] if i < len(ends) else total))
    return out


def parse_loudness(text):
    """Integrated loudness (LUFS) and true peak (dBTP) from the ebur128 summary."""
    lufs = tp = None
    block = text.rsplit("Summary:", 1)[-1] if "Summary:" in text else ""
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", block)
    if m:
        lufs = float(m.group(1))
    m = re.search(r"Peak:\s+(-?[\d.]+) dBFS", block)
    if m:
        tp = float(m.group(1))
    return lufs, tp


def run_pass(path, timeout=1800, threads=2):
    """The single ffmpeg decode. Returns the stderr text."""
    cmd = ["nice", "-n", "19", "ffmpeg", "-nostdin", "-hide_banner", "-threads", str(threads), "-i", path,
           "-af", f"silencedetect=n={SILENCE_DB}dB:d={SILENCE_MIN},ebur128=peak=true",
           "-vf", f"scale=480:-2,blackdetect=d={BLACK_MIN}:pix_th=0.10,freezedetect=n=0.003:d={FREEZE_MIN}",
           "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.stderr


def probe_facts(path):
    info = frames.probe(path)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    return {
        "width": v.get("width"), "height": v.get("height"), "fps": frames.fps_of(v.get("r_frame_rate")),
        "v_dur": float(v.get("duration") or info.get("format", {}).get("duration") or 0),
        "a_dur": float(a.get("duration") or 0) if a else 0.0,
        "has_audio": bool(a), "sample_rate": a.get("sample_rate"), "channels": a.get("channels"),
        "duration": float(info.get("format", {}).get("duration") or 0),
    }


def evaluate(kind, facts, silences, blacks, freezes, lufs, peak, slide_text=None):
    """Turn the measurements into findings. `slide_text(t)` says whether the frame at t carries text (deliberate still)."""
    f = []

    def add(check, sev, detail, t=None):
        f.append(dict(check=check, severity=sev, detail=detail, t=t))

    if (facts["width"], facts["height"]) != (EXPECT_W, EXPECT_H):
        add("resolution", "BLOCKER", f"{facts['width']}x{facts['height']}, expected {EXPECT_W}x{EXPECT_H}")
    if abs(facts["fps"] - EXPECT_FPS) > 0.5:
        add("frame-rate", "BLOCKER", f"{facts['fps']:.2f} fps, expected {EXPECT_FPS:.0f}")
    if not facts["has_audio"]:
        add("no-audio", "BLOCKER", "segment has no audio stream")
    else:
        if facts["a_dur"] and abs(facts["a_dur"] - facts["v_dur"]) > LEN_MISMATCH:
            add("av-length", "BLOCKER", f"audio {facts['a_dur']:.2f}s vs video {facts['v_dur']:.2f}s")
        if peak is not None and peak >= TRUE_PEAK_MAX:
            add("clipping", "BLOCKER", f"true peak {peak:.1f} dBTP")
        if kind != "content" and lufs is not None and lufs <= SILENT_LUFS:
            add("silent-bumper", "UPDATE", f"{kind} has an audio track but it is silent ({lufs:.0f} LUFS)")
        for s, e in silences:
            if e - s >= DEAD_AIR and not (kind in ("intro", "outro", "card") and (s < 0.2 or e >= facts["duration"] - 0.2)):
                add("dead-air", "BLOCKER", f"silence {e - s:.1f}s at {s:.1f}s", s)
    for s, e in blacks:
        add("black", "BLOCKER", f"black picture {e - s:.1f}s at {s:.1f}s", s)
    for s, e in freezes:
        deliberate = slide_text(s + 1.0) if slide_text else False
        if not deliberate:
            add("frozen", "BLOCKER", f"frozen picture {e - s:.0f}s at {s:.0f}s, no text on it", s)
    return f


def loudness_jumps(luf_by_kind):
    """Findings for >3 LU between the segments of one episode. luf_by_kind: {kind: LUFS or None}."""
    vals = {k: v for k, v in luf_by_kind.items() if v is not None and v > SILENT_LUFS}
    out = []
    if len(vals) >= 2:
        lo, hi = min(vals.values()), max(vals.values())
        if hi - lo > LOUD_JUMP:
            out.append(dict(check="loudness-jump", severity="BLOCKER",
                            detail=f"{hi - lo:.1f} LU between segments ({', '.join(f'{k} {v:.1f}' for k, v in vals.items())})", t=None))
    return out


def analyze_segment(path, kind, slide_text=None, timeout=1800):
    facts = probe_facts(path)
    text = run_pass(path, timeout=timeout)
    total = facts["duration"]
    sil = parse_silences(text, total)
    blk = parse_black(text)
    frz = parse_freezes(text, total)
    lufs, peak = parse_loudness(text)
    findings = evaluate(kind, facts, sil, blk, frz, lufs, peak, slide_text)
    return {"facts": facts, "silences": sil, "blacks": blk, "freezes": frz, "lufs": lufs, "peak": peak, "findings": findings}
