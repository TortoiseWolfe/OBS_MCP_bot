"""Review every latest tutorial episode and write findings.

    python3 -m playout.tutorials.review --all            # every episode (resumes: skips finished ones)
    python3 -m playout.tutorials.review --episode NAME   # one episode
    python3 -m playout.tutorials.review --summary        # rebuild review.md from the findings on disk

Output: ~/clawd-twitch/air/review/<series>/<episode>/findings.json (+ frames/*.png for each finding) and
~/clawd-twitch/air/review/review.md. Nothing under renders/, episodes/ or episodes.json is touched.

Severity: BLOCKER = cannot air. UPDATE = airs, goes on the update list.
"""
import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

from . import catalog, frames, layout, sound

SPARSE_INK, MIN_INK = 52000, 3000
OUT = Path.home() / "clawd-twitch" / "air" / "review"
FADE_FRACTION = 0.8   # a frame whose brightest text is under this share of the segment's brightest is a fade, not a slide
VERSION = 4
_SECTION = re.compile(r"section\s*(\d+)\s*of\s*(\d+)", re.I)
_DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")

_ocr = None


def ocr_lines(frame_rgb):
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
    res, _ = _ocr(np.ascontiguousarray(frame_rgb[:, :, ::-1]))
    return layout.lines_from_ocr(res)


def slide_key(lines, kind, scene):
    """A content slide is its section counter plus title; the title is the first body line."""
    sec = None
    for ln in lines:
        m = _SECTION.search(ln.text.replace(" ", ""))
        m = m or _SECTION.search(ln.text)
        if m and ln.y1 <= layout.HEADER_Y:
            sec = (int(m.group(1)), int(m.group(2)))
    body = [ln for ln in lines if not layout.is_chrome(ln)]
    title = body[0].text.strip().lower() if body else ""
    return (kind, sec, title[:24] if kind == "content" else scene), sec


def mark(frame, findings):
    im = np.ascontiguousarray(frame[:, :, ::-1]).copy()
    for f in findings:
        b = f.get("box")
        if b:
            col = (0, 0, 255) if f["severity"] == "BLOCKER" else (0, 165, 255)
            cv2.rectangle(im, (int(b[0]) - 3, int(b[1]) - 3), (int(b[2]) + 3, int(b[3]) + 3), col, 3)
    return im


def review_segment(seg_path, kind, outdir, registered_sections=None, script_title=None):
    """Sound, picture and layout checks on one segment. Returns (findings, slides, section_seq, extras)."""
    outdir.mkdir(parents=True, exist_ok=True)
    findings, slides = [], []
    sec_seq = []

    # layout first, so a frozen-picture check can ask whether the still carries text
    best = {}          # slide key -> (score, t, frame, lines)
    scene = 0
    ocr_cache = {}
    w, h = 1920, 1080

    inks = []          # (t, bright pixels) for every content frame handed over
    slide_span = {}    # slide key -> (first t, last t) on screen
    spans = []         # (start, end, text lines): where on the timeline a slide with text is on screen

    def take(t, fr, span=None):
        lines = ocr_lines(fr)
        key, sec = slide_key(lines, kind, scene)
        score = sum(1 for ln in lines if not layout.is_chrome(ln)) + 3 * sum(1 for ln in lines if ln.w > 400)
        if span:
            sp = slide_span.get(key)
            slide_span[key] = (min(sp[0], span[0]) if sp else span[0], max(sp[1], span[1]) if sp else span[1])
        if key not in best or score > best[key][0]:
            best[key] = (score, t, fr.copy(), lines)
        if sec and (not sec_seq or sec_seq[-1] != sec):
            sec_seq.append(sec)
        ocr_cache[round(t)] = len(lines)
        a, b, _ = span or (t - 12, t + 12, None)
        spans.append((a, b, len(lines)))

    # A content slide's title band changes only when the slide changes; bullets appear below it. So one frame per
    # slide is read: the one with the most bright (text) pixels, which is the slide at its fullest.
    held, held_ink, last_band, held_t, scene_t0 = None, -1, None, 0.0, 0.0
    peak_max = 0.0
    for t, fr, changed in frames.iter_frames(seg_path, w, h, max_gap=2.0 if kind == "content" else 10.0):
        if kind != "content":
            if changed or held is None:
                held = True
                scene += 1 if (last_band is not None) else 0
                last_band = 1
                take(t, fr)
            continue
        gray = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY)
        band = gray[85:170:3, ::6].astype(np.int16)      # the title row only: bullets appear below y 170
        if last_band is not None and float(np.abs(band - last_band).mean()) > 2.5:
            if held is not None:
                take(held_t, held, (scene_t0, t, None))
            held, held_ink, scene_t0 = None, -1, t
            scene += 1
        last_band = band
        ink = int((gray[90:1000, :] > 120).sum())
        inks.append((t, ink))
        # A slide fading out still has all its text but dim: never judge such a frame (its contrast reads low).
        # Peak brightness of the text zone is compared with the brightest seen so far in this segment.
        peak = float(np.percentile(gray[90:1000, :], 99.5))
        peak_max = max(peak_max, peak)
        if peak < FADE_FRACTION * peak_max:
            continue
        if ink > held_ink:
            held, held_ink, held_t = fr.copy(), ink, t
    if kind == "content" and held is not None:
        take(held_t, held, (scene_t0, held_t + 1e6, None))

    def slide_text(t):
        return any(a <= t <= b and n >= 2 for a, b, n in spans)

    n_slide = 0
    for key, (score, t, fr, lines) in best.items():
        text0 = " ".join(ln.text for ln in lines).lower()
        if kind == "content" and t < 15 and ("scripthammer" in text0 or "app factory" in text0) and "section" not in text0:
            # the content file opens with the intro animation again (about 11 s): one finding, no layout checks
            if not any(f_["check"] == "intro-repeat" for f_ in findings):
                findings.append(dict(check="intro-repeat", severity="UPDATE", t=round(t, 1), kind=kind, box=None,
                                     detail="the content video opens with the intro animation again (shown twice)"))
            continue
        found, feats = layout.analyze(fr, lines, kind)
        if kind == "content" and feats["body_lines"] <= 1:
            # a fade-in or fade-out frame (blank, or the title alone): skip it when the same section has a fuller slide
            sec_now = key[1]
            if sec_now is None or any(k2[1] == sec_now and v2[0] > score for k2, v2 in best.items()):
                continue
        for f_ in found:
            f_["t"] = round(t, 1)
            f_["kind"] = kind
        text = " ".join(ln.text for ln in lines)
        if kind == "card":
            m = _DATE.search(text)
            if m:
                found.append(dict(check="stale-date", severity="UPDATE", t=round(t, 1), kind=kind, box=None,
                                  detail=f"card shows a date ({m.group(0)}) that is now in the past"))
            if script_title:
                words = [x for x in re.findall(r"[a-z0-9]+", script_title.lower()) if len(x) > 3]
                joined = re.sub(r"[^a-z0-9]", "", text.lower())
                if words and sum(1 for x in words if x in joined) / len(words) < 0.5:
                    found.append(dict(check="card-title", severity="UPDATE", t=round(t, 1), kind=kind, box=None,
                                      detail=f"card text does not show the script title {script_title!r}: read {text[:80]!r}"))
        if kind == "content" and key in slide_span:
            d0, d1 = slide_span[key]
            d1 = min(d1, inks[-1][0] + 1) if inks else d1
            pts = [(tt, ii) for tt, ii in inks if d0 + 3 <= tt <= d1]
            peak = max((ii for _, ii in pts), default=0)
            if peak > 0 and len(pts) >= 2 and d1 - d0 > 40:
                # SPARSE_INK: bright pixels in the body area; every frame I labelled "looks broken" by eye was under it
                sparse = sum(b[0] - a[0] for a, b in zip(pts, pts[1:]) if MIN_INK < a[1] < SPARSE_INK)
                if sparse > 30 and sparse > 0.4 * (d1 - d0):
                    sev = "BLOCKER" if (sparse > 0.6 * (d1 - d0) and peak < SPARSE_INK) else "UPDATE"
                    found.append(dict(check="slow-reveal", severity=sev, t=round(t, 1), kind=kind, box=None,
                                      detail=f"the slide shows little text for {sparse:.0f} s of its {d1 - d0:.0f} s (bullets appear one by one; fullest state has {peak} bright pixels)"))
        if found:
            png = outdir / f"{kind}-{int(t):05d}.png"
            cv2.imwrite(str(png), mark(fr, found))
            for f_ in found:
                f_["image"] = png.name
        findings += found
        slides.append(dict(kind=kind, t=round(t, 1), section=key[1], title=key[2] if kind == "content" else None,
                           area=round(feats["area"], 3), median_h=feats["median_h"], panel=feats["panel"], n_findings=len(found)))
        n_slide += 1
    if kind == "content" and sec_seq:
        nums = [s[0] for s in sec_seq]
        total = sec_seq[-1][1]
        # slides run in order: the counter must never go backwards and must reach the last section
        if any(b < a for a, b in zip(nums, nums[1:])):
            findings.append(dict(check="section-order", severity="UPDATE", detail=f"section counter jumps backwards: {nums}", t=None, kind=kind, box=None))
        if registered_sections and total != registered_sections:
            findings.append(dict(check="section-count", severity="UPDATE", detail=f"slides say {total} sections, the registry says {registered_sections}", t=None, kind=kind, box=None))
    return findings, slides, slide_text


def review_episode(ep, root=OUT, force=False):
    d = root / ep["series"] / ep["episode"]
    fj = d / "findings.json"
    if fj.exists() and not force:
        try:
            if json.loads(fj.read_text()).get("version") == VERSION:
                return json.loads(fj.read_text())
        except ValueError:
            pass
    t0 = time.time()
    d.mkdir(parents=True, exist_ok=True)
    findings, slides, seg_info = [], [], {}
    title = catalog.script_title(ep["script_path"])
    lufs = {}
    for kind in catalog.KINDS:
        path = ep["segments"].get(kind)
        if not path:
            sev = "BLOCKER" if kind == "content" else "UPDATE"
            findings.append(dict(check="missing-segment", severity=sev, kind=kind, t=None, box=None, detail=f"no {kind} file in the episode folder"))
            continue
        try:
            lay, sl, slide_text = review_segment(path, kind, d / "frames", ep["registered_sections"], title)
            snd = sound.analyze_segment(path, kind, slide_text)
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the run
            findings.append(dict(check="check-failed", severity="BLOCKER", kind=kind, t=None, box=None, detail=f"{type(e).__name__}: {e}"))
            continue
        for f_ in snd["findings"]:
            f_["kind"] = kind
            f_.setdefault("box", None)
        findings += lay + snd["findings"]
        slides += sl
        lufs[kind] = snd["lufs"]
        seg_info[kind] = dict(path=path, **{k: snd[k] for k in ("facts", "lufs", "peak")}, n_silences=len(snd["silences"]),
                              longest_silence=max([e - s for s, e in snd["silences"]] or [0]))
    findings += [dict(f_, kind="episode", box=None) for f_ in sound.loudness_jumps(lufs)]
    seen, uniq = set(), []
    for f_ in findings:
        sig = (f_["check"], f_["severity"], f_.get("kind"), re.sub(r"\d+(\.\d+)?", "#", f_["detail"])) if f_["check"] in ("contrast", "margin") and f_["severity"] == "UPDATE" else None
        if sig and sig in seen:
            continue
        seen.add(sig)
        uniq.append(f_)
    findings = uniq
    n_block = sum(1 for f_ in findings if f_["severity"] == "BLOCKER")
    res = dict(version=VERSION, series=ep["series"], episode=ep["episode"], script=ep["script"], title=title,
               seconds=ep["registered_seconds"], sections=ep["registered_sections"], blockers=n_block,
               updates=sum(1 for f_ in findings if f_["severity"] == "UPDATE"), verdict="FAIL" if n_block else "PASS",
               findings=findings, slides=slides, segments=seg_info, review_seconds=round(time.time() - t0, 1))
    fj.write_text(json.dumps(res, indent=1, default=str))
    return res


def _work(args):
    ep, force, root = args
    try:
        r = review_episode(ep, root=root, force=force)
        return ep["episode"], r["verdict"], r["blockers"], r["review_seconds"]
    except Exception as e:  # noqa: BLE001
        return ep["episode"], "ERROR", str(e), 0


def summarize(root=OUT):
    """review.md from the findings on disk."""
    res = []
    for fj in sorted(root.glob("*/*/findings.json")):
        try:
            res.append(json.loads(fj.read_text()))
        except ValueError:
            pass
    n = len(res)
    passed = [r for r in res if r["verdict"] == "PASS"]
    hrs = lambda rs: sum(r["seconds"] or 0 for r in rs) / 3600.0  # noqa: E731
    by_check = defaultdict(lambda: Counter())
    eps_with = defaultdict(set)
    series_with = defaultdict(set)
    for r in res:
        for f_ in r["findings"]:
            by_check[f_["check"]][f_["severity"]] += 1
            eps_with[f_["check"]].add(r["episode"])
            series_with[f_["check"]].add(r["series"])
    all_series = {r["series"] for r in res}
    lines = [f"# Tutorial backlog review ({time.strftime('%-d %b %Y')})", "",
             f"{n} episodes, {len(passed)} pass, {n - len(passed)} fail. Passing episodes total {hrs(passed):.1f} h of {hrs(res):.1f} h.", "",
             "BLOCKER = cannot air. UPDATE = airs and goes on the update list.", "",
             "## Defects by check", "", "| check | episodes | series | BLOCKER findings | UPDATE findings | kind |", "|---|---|---|---|---|---|"]
    for c, cnt in sorted(by_check.items(), key=lambda kv: -len(eps_with[kv[0]])):
        share = len(eps_with[c]) / max(n, 1)
        kind = "template (same flaw across most series)" if share >= 0.5 and len(series_with[c]) >= max(5, 0.5 * len(all_series)) else "per episode"
        lines.append(f"| {c} | {len(eps_with[c])} | {len(series_with[c])} | {cnt['BLOCKER']} | {cnt['UPDATE']} | {kind} |")
    lines += ["", "## Episodes", "", "| series | episode | verdict | blockers | updates | top defects |", "|---|---|---|---|---|---|"]
    for r in sorted(res, key=lambda r: (r["series"], r["episode"])):
        top = Counter(f_["check"] for f_ in r["findings"] if f_["severity"] == "BLOCKER").most_common(3)
        lines.append(f"| {r['series']} | {r['episode']} | {r['verdict']} | {r['blockers']} | {r['updates']} | {', '.join(f'{c} x{k}' for c, k in top)} |")
    pj = root / "proof.json"
    if pj.exists():
        from . import proof
        lines += ["", proof.markdown(json.loads(pj.read_text()))]
    (root / "review.md").write_text("\n".join(lines) + "\n")
    return n, len(passed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--episode")
    ap.add_argument("--series")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--segments-root", help="read each episode's segments from <root>/<series>/<episode>/ instead of renders/")
    ap.add_argument("--out", help="write findings under this folder instead of air/review")
    a = ap.parse_args()
    out = Path(a.out) if a.out else OUT
    out.mkdir(parents=True, exist_ok=True)
    if a.summary:
        print(summarize(out))
        return
    eps = catalog.episodes()
    if a.segments_root:
        for e in eps:
            folder = Path(a.segments_root) / e["series"] / e["episode"]
            if folder.exists():
                e["segments"] = {k: (str(p) if (p := catalog._newest(folder, k)) else None) for k in catalog.KINDS}
    if a.episode:
        eps = [e for e in eps if e["episode"] == a.episode]
    if a.series:
        eps = [e for e in eps if e["series"] == a.series]
    if not (a.all or a.episode or a.series):
        ap.error("pick --all, --series or --episode")
    t0 = time.time()
    with Pool(a.workers) as pool:
        for i, r in enumerate(pool.imap_unordered(_work, [(e, a.force, out) for e in eps]), 1):
            print(f"[{i}/{len(eps)} {time.time() - t0:.0f}s] {r}", flush=True)
            if i % 10 == 0:
                summarize(out)
    print(summarize(out))


if __name__ == "__main__":
    sys.exit(main())
