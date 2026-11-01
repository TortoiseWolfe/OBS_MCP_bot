"""Detector proof: run the layout detectors on frames labelled by eye and report precision and recall per detector.

The labels (50 frames from 8 or more series) live in the lane folder with a cached OCR read of each frame
(label_ocr.json), so the proof runs in seconds. `python -m playout.tutorials.proof [labels_dir]` prints the table
and writes proof.json next to review.md.
"""
import json
import sys
from pathlib import Path

import cv2

from . import layout
from .review import MIN_INK, OUT, SPARSE_INK

LANE = Path.home() / ".claude/state/lanes/2026-11-01-tutorials-247/labels"

# Eye labels, frame number -> label. Frames not listed for a check are not scored for it.
WS_BLOCKER = {1, 2, 3, 8, 11, 12, 13, 17, 18, 21, 22, 23, 26, 27, 28, 31, 32, 33, 34, 36, 38, 46}
WS_UPDATE = {14, 19, 24, 48, 37, 39}
WS_OK = {9, 16, 29, 47}
CLIP_PANEL = {4, 9, 16, 29, 37, 39, 47}
CLIP_FLOOR = {9}
SINGLE_WORD = {43}
# every content slide I viewed has body text at 4.5:1 or better, so no frame is a contrast BLOCKER
CONTRAST_BLOCKER = set()
# frames where the picture is blank or a watermark (a transition): not scored
TRANSIENT = {6, 7, 10, 15, 25, 45}


def ink_of(path):
    g = cv2.imread(str(path), 0)
    return int((g[90:1000] > 120).sum())


def score(flags, positives, universe):
    tp = len(flags & positives)
    fp = len((flags & universe) - positives)
    fn = len(positives - flags)
    return dict(tp=tp, fp=fp, fn=fn,
                precision=round(tp / (tp + fp), 3) if tp + fp else None,
                recall=round(tp / (tp + fn), 3) if tp + fn else None)


def run(labels=LANE):
    labels = Path(labels)
    ocr = json.load(open(labels / "label_ocr.json"))
    items = {it["n"]: it for it in json.load(open(labels / "items.json"))}
    got = {}
    for name, raw in ocr.items():
        n = int(name[:2])
        fr = cv2.imread(str(labels / "label" / name))[:, :, ::-1].copy()
        lines = layout.lines_from_ocr([(b, t, c) for b, t, c in raw])
        found, feats = layout.analyze(fr, lines, items[n]["kind"])
        got[n] = dict(found=found, ink=ink_of(labels / "label" / name))
    scored = set(got) - TRANSIENT

    def has(n, check, sev=None):
        return any(f["check"] == check and (sev is None or f["severity"] == sev) for f in got[n]["found"])

    ws_labelled = WS_BLOCKER | WS_UPDATE | WS_OK
    rows = {
        "white-space (text-box rule), BLOCKER": score({n for n in scored if has(n, "white-space", "BLOCKER")}, WS_BLOCKER, ws_labelled),
        "white-space (bright-pixel rule), BLOCKER": score({n for n in scored if MIN_INK < got[n]["ink"] < SPARSE_INK}, WS_BLOCKER, ws_labelled),
        "white-space, either rule, BLOCKER": score({n for n in scored if has(n, "white-space", "BLOCKER") or MIN_INK < got[n]["ink"] < SPARSE_INK}, WS_BLOCKER, ws_labelled),
        "white-space, any severity (BLOCKER or UPDATE)": score({n for n in scored if has(n, "white-space") or MIN_INK < got[n]["ink"] < SPARSE_INK}, WS_BLOCKER | WS_UPDATE, ws_labelled),
        "clip-panel": score({n for n in scored if has(n, "clip-panel")}, CLIP_PANEL, scored),
        "clip-floor": score({n for n in scored if has(n, "clip-floor")}, CLIP_FLOOR, scored),
        "single-word-line": score({n for n in scored if has(n, "single-word-line")}, SINGLE_WORD, scored),
        "contrast, BLOCKER": score({n for n in scored if has(n, "contrast", "BLOCKER")}, CONTRAST_BLOCKER, scored),
    }
    out = dict(frames=len(got), scored=len(scored), series=len({it["series"] for it in items.values()}), rows=rows)
    return out, got


def markdown(proof):
    lines = [f"## Detector proof ({proof['scored']} frames labelled by eye, {proof['series']} series)", "",
             "| detector | caught | missed | false alarms | precision | recall |", "|---|---|---|---|---|---|"]
    for k, r in proof["rows"].items():
        fmt = lambda v: "n/a" if v is None else f"{v:.0%}"
        lines.append(f"| {k} | {r['tp']} | {r['fn']} | {r['fp']} | {fmt(r['precision'])} | {fmt(r['recall'])} |")
    lines += ["", "Known gap: an inline-code pill cut off at the end of its line (two labelled frames) has too little contrast "
              "for the pixel rules; those are found by eye in the flagged and sampled frames and added by hand.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    proof, got = run(sys.argv[1] if len(sys.argv) > 1 else LANE)
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(proof, open(OUT / "proof.json", "w"), indent=1)
    print(markdown(proof))
    for n in sorted(got):
        print(n, sorted({(f["check"], f["severity"][0]) for f in got[n]["found"]}), got[n]["ink"])
