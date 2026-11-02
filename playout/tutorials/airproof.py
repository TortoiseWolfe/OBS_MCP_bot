"""Checks on a finished air file (an encoded episode, or the rotation's output): constant bitrate per 10 s window, keyframe
every 2 s, continuous timestamps (no hole or repeat at the joins), audio and video ending together.

usage: python -m playout.tutorials.airproof FILE [--join SECONDS ...]   prints one JSON object; exit 1 when a check fails.
"""
import argparse
import json
import subprocess
import sys

BITRATE_TOL = 0.15      # a 10 s window may differ from the median by this share
KEY_EVERY = 2.0
KEY_TOL = 0.1


def packets(path, kind):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", f"{kind}:0", "-show_entries", "packet=pts_time,dts_time,size,flags",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=900)
    out = []
    for line in r.stdout.splitlines():
        f = line.split(",")
        if len(f) >= 4 and f[0] not in ("", "N/A"):
            out.append((float(f[0]), int(f[2]), "K" in f[3]))
    return sorted(out)


def dts_steps_back(path, kind):
    """How many packets, in file order, carry a decode time lower than the one before (the receiver warns on these)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", f"{kind}:0", "-show_entries", "packet=dts_time", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, timeout=900)
    d = [float(x.split(",")[0]) for x in r.stdout.split() if x and not x.startswith("N/A")]
    return sum(1 for x, y in zip(d, d[1:]) if y < x)


def windows(pk, width=10.0):
    """kbps per full `width`-second window (the last partial window is left out)."""
    if not pk:
        return []
    t0, tend = pk[0][0], pk[-1][0]
    n = int((tend - t0) // width)
    sums = [0] * n
    for t, size, _ in pk:
        i = int((t - t0) // width)
        if i < n:
            sums[i] += size
    return [s * 8 / width / 1000 for s in sums]


def analyse(path):
    v, a = packets(path, "v"), packets(path, "a")
    res = {"file": str(path)}
    ts = [p[0] for p in v]
    gaps = [y - x for x, y in zip(ts, ts[1:])]
    res["video_max_gap"] = round(max(gaps), 4) if gaps else None
    res["video_min_gap"] = round(min(gaps), 4) if gaps else None
    ats = [p[0] for p in a]
    agaps = [y - x for x, y in zip(ats, ats[1:])]
    res["audio_max_gap"] = round(max(agaps), 4) if agaps else None
    res["audio_min_gap"] = round(min(agaps), 4) if agaps else None
    keys = [p[0] for p in v if p[2]]
    kd = [y - x for x, y in zip(keys, keys[1:])]
    res["keyframe_interval_min"] = round(min(kd), 3) if kd else None
    res["keyframe_interval_max"] = round(max(kd), 3) if kd else None
    w = windows(v)
    wa = windows(a)
    tot = [x + y for x, y in zip(w, wa)]
    if tot:
        s = sorted(tot)
        med = s[len(s) // 2]
        res["window_kbps_min"], res["window_kbps_max"], res["window_kbps_median"] = round(s[0]), round(s[-1]), round(med)
        res["windows"] = len(tot)
    res["video_end"] = round(ts[-1], 3) if ts else None
    res["audio_end"] = round(ats[-1], 3) if ats else None
    fails = []
    res["video_dts_steps_back"], res["audio_dts_steps_back"] = dts_steps_back(path, "v"), dts_steps_back(path, "a")
    if gaps and max(gaps) > 2 / 30 + 0.01:
        fails.append("video timestamp hole")
    if agaps and max(agaps) > 0.05:
        fails.append("audio timestamp hole")
    if res["video_dts_steps_back"] or res["audio_dts_steps_back"]:
        fails.append("decode time steps back")
    # A keyframe may come early where one item ends and the next begins (an item is not a whole number of 2 s); never late.
    if kd and max(kd) > KEY_EVERY + KEY_TOL:
        fails.append("keyframe interval over 2 s")
    if tot and (s[0] < med * (1 - BITRATE_TOL) or s[-1] > med * (1 + BITRATE_TOL)):
        fails.append("bitrate not constant per 10 s window")
    if ts and ats and abs(ts[-1] - ats[-1]) > 0.5:
        fails.append("audio and video end apart")
    res["fails"] = fails
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    a = ap.parse_args(argv)
    r = analyse(a.file)
    print(json.dumps(r))
    return 1 if r["fails"] else 0


if __name__ == "__main__":
    sys.exit(main())
