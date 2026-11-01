"""Short gaps in a sound file: find them, and say what kind each one is.

A gap is a stretch of at least MIN_GAP seconds below THRESH_DB. The old film check only counted silences of
2 s or more, so 0.15 s to 0.6 s holes in the sound went unseen (film-a7, 31 Oct: 83 gaps in 22 of 25 songs).

Each gap is read from the sound around it (needs only ffmpeg and the standard library):
  fall_ms / rise_ms  how fast the sound drops into the gap and comes back; 20 ms or less is a hard cut
  floor_db           the loudest the gap itself gets; under -70 dB is a blank, not a quiet passage
  start/end offset   how far the gap's start and end sit from the nearest sixteenth-note of the music around it
                     (the beat grid is fitted to the onsets in the 5 s before and after, at the catalog tempo)
Labels:
  quiet passage the music on both sides is itself under -42 dB (a breakdown at the threshold, not a cut)
  dip           the sound sinks and returns slowly (no hard edge)
  musical stop  both edges within 30 ms of the sixteenth-note grid, grid fitted well (about a 1 in 8 chance for a cut at random)
  dropout       an edge clearly off the grid, or the beat shifts across the gap (a splice)
  unclear       no tempo, no clear grid, or in between; needs ears (the clips in gap-clips/ are for that)
"""
import array
import cmath
import math
import re
import subprocess

THRESH_DB = -45.0
MIN_GAP = 0.15
EDGE = 0.3  # a gap this close to the start or end of a file is a lead-in or a tail, not a hole inside the song
SR = 22050
FRAME = 110  # 5 ms
HARD_MS = 20.0
GRID_TOL_MS = 30.0
OFF_MS = 45.0
BLANK_DB = -50.0
QUIET_DB = -42.0
GRID_R_MIN = 0.5


def detect(path, start=0.0, seconds=None):
    """[(start, end)] of every gap, in seconds from `start` in the file. A gap that runs to the end ends at the file's end."""
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    if seconds:
        cmd += ["-t", f"{seconds:.3f}"]
    cmd += ["-i", str(path), "-vn", "-af", f"silencedetect=n={THRESH_DB:g}dB:d={MIN_GAP}", "-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    dur = re.findall(r"time=(\d+):(\d+):([\d.]+)", err)
    total = float(dur[-1][0]) * 3600 + float(dur[-1][1]) * 60 + float(dur[-1][2]) if dur else None
    starts = [max(0.0, float(x)) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else (total if total is not None else s)
        out.append((s, e))
    return out, total


def zone(s, e, total):
    if s < EDGE:
        return "lead-in"
    if total is not None and e > total - EDGE:
        return "tail"
    return "inside"


def inside(gaps, total):
    return [(s, e) for s, e in gaps if zone(s, e, total) == "inside"]


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    return a


def env_db(pcm, t0, t1):
    """5 ms level in dB, one value per frame, from t0 to t1 seconds. Returns (list, first frame's time)."""
    i0 = max(0, int(t0 * SR) // FRAME * FRAME)
    i1 = min(len(pcm), int(t1 * SR))
    out = []
    for i in range(i0, i1 - FRAME + 1, FRAME):
        seg = pcm[i:i + FRAME]
        ms = sum(x * x for x in seg) / FRAME
        out.append(20 * math.log10(max(math.sqrt(ms), 1.0) / 32768.0))
    return out, i0 / SR


def _median(v):
    v = sorted(v)
    return v[len(v) // 2] if v else -96.0


def _edges(pcm, s, e):
    """Level before and after the gap, how fast the sound falls into it and returns, and the gap's own loudest frame."""
    pre, pt = env_db(pcm, s - 0.6, s + 0.05)
    post, qt = env_db(pcm, e - 0.05, e + 0.6)
    gap, _ = env_db(pcm, s + 0.01, e - 0.01)
    if not pre or not post:
        return None
    k = lambda t, t0: int((t - t0) * SR / FRAME)
    pre_level = _median(pre[max(0, k(s - 0.45, pt)):max(1, k(s - 0.1, pt))])
    post_level = _median(post[max(0, k(e + 0.1, qt)):max(1, k(e + 0.45, qt))])
    last = k(s, pt)
    j = min(last, len(pre) - 1)
    while j > 0 and pre[j] < pre_level - 10:  # walk back to the last frame still near the pre-gap level
        j -= 1
    fall = max(0.0, (last - j) * FRAME / SR * 1000)
    first = max(0, k(e, qt))
    j = min(first, len(post) - 1)
    while j < len(post) - 1 and post[j] < post_level - 10:
        j += 1
    rise = max(0.0, (j - first) * FRAME / SR * 1000)
    return {"pre_db": round(pre_level, 1), "post_db": round(post_level, 1), "floor_db": round(max(gap), 1) if gap else None,
            "fall_ms": round(fall), "rise_ms": round(rise)}


def _onsets(pcm, t0, t1):
    db, ft = env_db(pcm, t0, t1)
    flux = [max(0.0, db[i] - db[i - 2]) for i in range(2, len(db))]
    peaks = []
    for i in range(1, len(flux) - 1):
        if flux[i] >= 6.0 and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1]:
            t = ft + (i + 2) * FRAME / SR
            if peaks and t - peaks[-1][0] < 0.06:
                if flux[i] > peaks[-1][1]:
                    peaks[-1] = (t, flux[i])
                continue
            peaks.append((t, flux[i]))
    return peaks


def _grid(pcm, t_near, side, period):
    """Phase and strength (0 to 1) of the half-beat grid, from the onsets within 5 s on one side of a gap edge."""
    lo, hi = (t_near - 5.0, t_near - 0.1) if side < 0 else (t_near + 0.1, t_near + 5.0)
    pk = _onsets(pcm, max(0.0, lo), hi)
    if len(pk) < 6:
        return None
    z = sum(w * (1 - abs(t - t_near) / 5.5) * cmath.exp(2j * math.pi * t / period) for t, w in pk)
    n = sum(w * (1 - abs(t - t_near) / 5.5) for t, w in pk)
    return (cmath.phase(z) / (2 * math.pi) * period) % period, abs(z) / n


def _off(t, phase, period):
    return ((t - phase + period / 2) % period - period / 2) * 1000


def classify(pcm, s, e, bpm):
    f = _edges(pcm, s, e)
    if f is None:
        return {"label": "unclear", "why": "too close to the file's edge to measure"}
    f["len_ms"] = round((e - s) * 1000)
    period = None
    if bpm:
        period = 60.0 / bpm / 4
        gs = _grid(pcm, s, -1, period)
        ge = _grid(pcm, e, +1, period)
        if gs and ge:
            f["start_off_ms"] = round(_off(s, gs[0], period))
            f["end_off_ms"] = round(_off(e, ge[0], period))
            f["grid_r"] = round(min(gs[1], ge[1]), 2)
            f["phase_jump_ms"] = round(_off(ge[0], gs[0], period))
    hard = f["fall_ms"] <= HARD_MS and f["rise_ms"] <= HARD_MS
    blank = f["floor_db"] is not None and f["floor_db"] < BLANK_DB
    have = "grid_r" in f and f["grid_r"] >= GRID_R_MIN
    ongrid = have and abs(f["start_off_ms"]) <= GRID_TOL_MS and abs(f["end_off_ms"]) <= GRID_TOL_MS
    offgrid = have and (abs(f["start_off_ms"]) > OFF_MS or abs(f["end_off_ms"]) > OFF_MS)
    if f["pre_db"] < QUIET_DB and f["post_db"] < QUIET_DB:
        f["label"], f["why"] = "quiet passage", "the music on both sides is itself under -42 dB"
    elif f["fall_ms"] > 60 and f["rise_ms"] > 60:
        f["label"], f["why"] = "dip", "sinks and returns slowly"
    elif ongrid:
        f["label"], f["why"] = "musical stop", "both edges on the sixteenth-note grid"
    elif have and abs(f["phase_jump_ms"]) > OFF_MS:
        f["label"], f["why"] = "dropout", "the beat shifts across the gap (a splice)"
    elif offgrid and (hard or blank):
        f["label"], f["why"] = "dropout", "cut mid-note: an edge is off the beat grid"
    else:
        f["label"], f["why"] = "unclear", "no clear beat grid" if not have else "between on and off the grid"
    return f
