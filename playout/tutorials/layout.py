"""Text-layout checks on one 1920x1080 tutorial frame.

Input is the frame (RGB array) plus the OCR line boxes. Every function here is pure, so tests can feed it synthetic
pictures. The checks are the ones Jonathan named: text clipped by the frame, a box or a panel; a single word alone on
a line; a slide that is mostly empty; text too dim to read. Thresholds were fitted on frames judged by eye (see
review.md for the numbers).
"""
import re
from dataclasses import dataclass

import cv2
import numpy as np

W, H = 1920, 1080
SAFE_X, SAFE_Y = 64, 36                      # film-design spec: side and top/bottom safe margin
HEADER_Y = 80                                # header band: "Section N of M" and SCRIPTHAMMER
FOOTER_Y = 1020                              # footer band: ScriptHammer.com
PANEL_CLIP_PX = 22                           # a code line ending this close to the panel border is cut by it
GAP_FRAC = 0.16                              # a pixel gap this wide (x line height) is a space between words
EDGE_PX = 6                                  # text this close to the frame edge is cut by the frame
BODY_FLOOR = 1000                            # body text whose box ends below this runs into the footer band

OLD_VERSION = re.compile(r"\b(?:Next(?:\.js)?\s*(?:v)?1[3-5]\b|Node(?:\.js)?\s*(?:v)?(?:18|20)\b|React\s*(?:v)?18\b)", re.I)


@dataclass
class Line:
    x0: int
    y0: int
    x1: int
    y1: int
    text: str
    conf: float = 1.0

    @property
    def h(self):
        return self.y1 - self.y0

    @property
    def w(self):
        return self.x1 - self.x0


def lines_from_ocr(result):
    """rapidocr result [(4 points, text, conf)] -> [Line]."""
    out = []
    for box, text, conf in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        out.append(Line(int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)), str(text), float(conf)))
    return sorted(out, key=lambda ln: (ln.y0, ln.x0))


CHROME_TEXT = re.compile(r"^\s*(?:section\s*\d+\s*of\s*\d+|scripthammer(?:\.com)?)\s*$", re.I)


def is_chrome(ln):
    """Header counter, SCRIPTHAMMER mark and the ScriptHammer.com watermark: the template's frame, not slide content."""
    return ln.y1 <= HEADER_Y or ln.y0 >= FOOTER_Y or bool(CHROME_TEXT.match(ln.text))


def is_gutter(ln):
    """Code-panel line numbers."""
    return ln.w < 70 and ln.text.strip().isdigit() or (ln.w < 40 and len(ln.text.strip()) <= 2)


def find_panel(gray, minrun=250, thr=25):
    """Code panel = two long vertical edges. Returns (left_x, right_x) or None."""
    d = np.abs(np.diff(gray[80:1000].astype(np.int16), axis=1)) > thr
    xs = []
    for x in range(900, 1900):
        col = d[:, x]
        # longest run of True
        padded = np.concatenate(([0], col.view(np.int8), [0]))
        edges = np.flatnonzero(np.diff(padded))
        if len(edges) and (edges[1::2] - edges[0::2]).max() >= minrun:
            xs.append(x)
    if not xs:
        return None
    left = [x for x in xs if 1000 <= x <= 1300]
    right = [x for x in xs if 1840 <= x <= 1880]
    if left and right:
        return min(left), max(right)
    if right and not left:
        return None
    return None


def word_count(gray, ln):
    """Words in a line, counted from pixel gaps (OCR drops spaces). A gap wider than 0.3 x line height splits words."""
    pad = 2
    crop = gray[max(ln.y0 - pad, 0):ln.y1 + pad, max(ln.x0 - pad, 0):ln.x1 + pad].astype(np.int16)
    if crop.size == 0:
        return 1
    bg = np.median(crop)
    ink = (np.abs(crop - bg) > 40).any(axis=0)
    cols = np.flatnonzero(ink)
    if len(cols) == 0:
        return 1
    gap = max(int(GAP_FRAC * (ln.y1 - ln.y0)), 4)
    gaps = np.diff(cols)
    return 1 + int((gaps > gap).sum())


def contrast(frame, ln):
    """WCAG contrast ratio of a text line against its own background."""
    crop = frame[max(ln.y0, 0):ln.y1, max(ln.x0, 0):ln.x1].reshape(-1, 3).astype(np.float64)
    if len(crop) < 20:
        return None
    bg = np.median(crop, axis=0)
    dist = np.abs(crop - bg).sum(axis=1)
    if dist.max() < 30:
        return 1.0
    fg = crop[dist >= 0.8 * dist.max()].mean(axis=0)

    def lum(c):
        c = np.clip(c / 255.0, 0, 1)
        c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    a, b = lum(fg), lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def features(lines, panel=None):
    """Numbers describing how full the slide is, from body text and the panel only."""
    body = [ln for ln in lines if not is_chrome(ln)]
    sw, sh = W - 2 * SAFE_X, H - 2 * SAFE_Y
    boxes = [(ln.x0, ln.y0, ln.x1, ln.y1) for ln in body]
    if panel:
        boxes.append((panel[0], 180, panel[1], 780))
    if not boxes:
        return {"body_lines": 0, "area": 0.0, "w": 0.0, "h": 0.0, "median_h": 0.0, "bottom_empty": 1.0, "right_empty": 1.0}
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    text_only = [ln for ln in body if not panel or ln.x0 < panel[0]]
    med = float(np.median([ln.h for ln in text_only])) if text_only else 0.0
    ink = sum((b[2] - b[0]) * (b[3] - b[1]) for b in boxes)
    return {
        "body_lines": len(body),
        "area": ink / float(sw * sh),                 # sum of text-line (and panel) areas over the safe area
        "w": (x1 - x0) / float(sw),
        "h": (y1 - y0) / float(sh),
        "median_h": med,
        "bottom_empty": max(0.0, (H - SAFE_Y - y1)) / float(sh),
        "right_empty": max(0.0, (W - SAFE_X - x1)) / float(sw),
        "bbox": [x0, y0, x1, y1],
    }


def check_clipping(frame, lines, panel=None):
    out = []
    for ln in lines:
        if ln.x0 <= EDGE_PX or ln.x1 >= W - EDGE_PX or ln.y0 <= EDGE_PX or ln.y1 >= H - EDGE_PX:
            out.append(dict(check="clip-frame", severity="BLOCKER", box=[ln.x0, ln.y0, ln.x1, ln.y1], detail=f"text touches the frame edge: {ln.text[:60]!r}"))
    for ln in lines:
        if is_chrome(ln):
            continue
        t = ln.text.rstrip()
        in_panel = panel is not None and ln.x0 >= panel[0] and ln.h < 60
        if t.endswith("…") or (t.endswith("...") and not in_panel):
            out.append(dict(check="clip-ellipsis", severity="BLOCKER", box=[ln.x0, ln.y0, ln.x1, ln.y1], detail=f"text ends in a truncation mark: {t[-40:]!r}"))
    if panel:
        for ln in lines:
            if is_chrome(ln) or is_gutter(ln) or ln.x0 < panel[0]:
                continue
            if ln.x1 >= panel[1] - PANEL_CLIP_PX and ln.w > 60:
                out.append(dict(check="clip-panel", severity="BLOCKER", box=[ln.x0, ln.y0, ln.x1, ln.y1], detail=f"code line runs into the panel edge: ...{ln.text[-40:]!r}"))
    for ln in lines:
        if is_chrome(ln):
            continue
        if (panel is None or ln.x0 < panel[0]) and ln.y1 >= BODY_FLOOR:
            out.append(dict(check="clip-floor", severity="BLOCKER", box=[ln.x0, ln.y0, ln.x1, ln.y1], detail=f"text reaches the footer band (bottom {ln.y1}): {ln.text[:50]!r}"))
    return out


def check_margins(lines):
    """Safe-margin breaches (UPDATE; a template matter, reported once per layout)."""
    out = []
    for ln in lines:
        if ln.x0 < SAFE_X - 16 or ln.x1 > W - SAFE_X + 16:
            out.append(dict(check="margin", severity="UPDATE", box=[ln.x0, ln.y0, ln.x1, ln.y1], detail=f"text inside the {SAFE_X}px side margin: {ln.text[:40]!r}"))
    return out


def check_single_word(gray, lines, panel=None):
    """A line of one word that finishes a wrapped paragraph (previous line in the same block is long)."""
    body = [ln for ln in lines if not is_chrome(ln) and (panel is None or ln.x0 < panel[0] - 10)]
    body.sort(key=lambda ln: ln.y0)
    if not body:
        return []
    col_right = max(ln.x1 for ln in body)
    out = []
    for i, ln in enumerate(body):
        if i == 0 or word_count(gray, ln) != 1:
            continue
        prev = body[i - 1]
        pitch = ln.y0 - prev.y0
        if pitch > 1.6 * max(ln.h, prev.h) or pitch < 0.6 * max(ln.h, prev.h):
            continue                                   # not the line directly above
        if prev.x1 < 0.6 * col_right or word_count(gray, prev) < 2:
            continue
        if abs(ln.x0 - prev.x0) > 60:
            continue
        out.append(dict(check="single-word-line", severity="BLOCKER", box=[ln.x0, ln.y0, ln.x1, ln.y1], detail=f"one word alone on a line: {ln.text[:40]!r}"))
    return out


def check_whitespace(lines, panel=None):
    f = features(lines, panel)
    out = []
    if f["body_lines"] == 0:
        return out, f
    mh = f["median_h"]
    if f["area"] < 0.12 or (f["area"] < 0.18 and mh < 37):
        out.append(dict(check="white-space", severity="BLOCKER", box=f.get("bbox"), detail=f"slide is mostly empty (text area {f['area']:.2f} of the safe area, text height {mh:.0f}px)"))
    elif f["bottom_empty"] > 0.35 or f["right_empty"] > 0.4:
        out.append(dict(check="white-space", severity="UPDATE", box=f.get("bbox"), detail=f"text fills only part of the slide (bottom empty {f['bottom_empty']:.2f}, right empty {f['right_empty']:.2f})"))
    return out, f


def check_contrast(frame, lines, kind="content"):
    """Body text of a content slide under 4.5:1 is a BLOCKER; chrome, line numbers and the decorative intro/card text are UPDATE."""
    out = []
    for ln in lines:
        if ln.conf < 0.6 or ln.h < 10 or len(ln.text.strip()) < 5:
            continue                     # an OCR fragment under 5 characters is a box slice, not a text line
        c = contrast(frame, ln)
        need = 3.0 if ln.h >= 34 else 4.5          # WCAG large text (24 px and up, a line box of about 34 px) needs 3:1
        if c is not None and c < need:
            sev = "UPDATE" if (is_chrome(ln) or is_gutter(ln) or kind != "content") else "BLOCKER"
            out.append(dict(check="contrast", severity=sev, box=[ln.x0, ln.y0, ln.x1, ln.y1], detail=f"contrast {c:.1f}:1 (needs {need}:1): {ln.text[:40]!r}", ratio=round(float(c), 2)))
    return out


def check_versions(lines):
    out = []
    for ln in lines:
        m = OLD_VERSION.search(ln.text)
        if m:
            out.append(dict(check="old-version", severity="UPDATE", box=[ln.x0, ln.y0, ln.x1, ln.y1], detail=f"old version on screen: {m.group(0)!r}"))
    return out


def analyze(frame, lines, kind="content"):
    """All layout checks on one frame. Returns (findings, features)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    panel = find_panel(gray)
    found = []
    found += check_clipping(frame, lines, panel)
    found += check_margins(lines)
    found += check_single_word(gray, lines, panel)
    ws, feats = check_whitespace(lines, panel)
    if kind != "content":
        # intro, card and outro are title screens: sparse by design, and animated (frames mid-reveal). A weak
        # layout goes on the update list; it never blocks airing. The date pill on a card sits in the footer band.
        for f_ in ws:
            f_["severity"] = "UPDATE"
        found = [f_ for f_ in found if f_["check"] != "clip-floor"]
    found += ws
    found += check_contrast(frame, lines, kind)
    found += check_versions(lines)
    if kind == "card":
        norm = [re.sub(r"[^a-z0-9]", "", ln.text.lower()) for ln in lines if not is_chrome(ln)]
        norm = [n for n in norm if len(n) > 6]
        if len(norm) != len(set(norm)):
            found.append(dict(check="card-duplicate-text", severity="UPDATE", box=None,
                              detail="the card shows the same line twice (title repeated as the subtitle)"))
    feats["panel"] = list(panel) if panel else None
    return found, feats
