"""Before/after table for episodes re-rendered with a fix: findings per check from the old review and the new one, and one
side-by-side frame. Reads findings.json files only; writes the table and the picture under ~/clawd-twitch/air/rerender/.

python -m playout.tutorials.compare mongodb/mongodb-schema-design [tailwind/...]  [--frame-section 3] [--after-root review-after-v5 --out-dir rerender-v5]
"""
import argparse
import json
from collections import Counter
from pathlib import Path

AIR = Path.home() / "clawd-twitch" / "air"


def counts(findings):
    c = Counter()
    for f in findings:
        c[(f["check"], f["severity"])] += 1
    return c


def table(ep, after_root="review-after"):
    before = json.loads((AIR / "review" / ep / "findings.json").read_text())
    after = json.loads((AIR / after_root / ep / "findings.json").read_text())
    cb, ca = counts(before["findings"]), counts(after["findings"])
    rows = sorted(set(cb) | set(ca), key=lambda k: (k[1] != "BLOCKER", k[0]))
    lines = [f"### {ep}", "", f"Verdict: {before['verdict']} ({before['blockers']} blockers) before, "
             f"{after['verdict']} ({after['blockers']} blockers) after.", "", "| check | severity | before | after |", "|---|---|---|---|"]
    lines += [f"| {c} | {s} | {cb.get((c, s), 0)} | {ca.get((c, s), 0)} |" for c, s in rows]
    return "\n".join(lines) + "\n", before, after


def side_by_side(ep, before, after, section, dest, after_root="review-after"):
    from PIL import Image, ImageDraw  # noqa: PLC0415

    def frame(res, root):
        sl = [s for s in res["slides"] if s["kind"] == "content" and s["section"] and s["section"][0] == section]
        for s in sl:  # the first slide of the section whose frame image was kept
            f = AIR / root / ep / "frames" / f"content-{int(s['t']):05d}.png"
            if f.exists():
                return Image.open(f)
        return None
    a, b = frame(before, "review"), frame(after, after_root)
    if a is None or b is None:
        return False
    w = Image.new("RGB", (a.width, a.height * 2 + 60), (20, 20, 20))
    w.paste(a, (0, 40))
    w.paste(b, (0, a.height + 80))
    d = ImageDraw.Draw(w)
    d.text((10, 10), "BEFORE (original render)", fill=(255, 255, 255))
    d.text((10, a.height + 50), "AFTER (fixed NarratedSegment)", fill=(255, 255, 255))
    w.save(dest)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episodes", nargs="+", help="series/episode")
    ap.add_argument("--frame-section", type=int, default=3)
    ap.add_argument("--after-root", default="review-after", help="folder under ~/clawd-twitch/air holding the after reviews")
    ap.add_argument("--out-dir", default="rerender", help="folder under ~/clawd-twitch/air for the table and the picture (created)")
    a = ap.parse_args()
    out = []
    out_dir = AIR / a.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for ep in a.episodes:
        t, b, af = table(ep, a.after_root)
        out.append(t)
        dest = out_dir / f"{ep.split('/')[1]}-before-after.png"
        ok = side_by_side(ep, b, af, a.frame_section, dest, a.after_root)
        out.append(f"Frame: {dest if ok else 'none (section ' + str(a.frame_section) + ' not found)'}\n")
    text = "\n".join(out)
    (out_dir / "before-after.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
