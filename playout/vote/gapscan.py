"""Scan sound files for short gaps (0.15 s and up, under -45 dB) and say what kind each is.

  python3 gapscan.py --out DIR [--film PLAN.json FILM_AUDIO.mp3] [--film-sources MAP.json] [--workers 4]

Scans every take in audio/takes/catalog.json, the older audio/bw-*.mp3, any other non-headline mp3 in audio/takes/,
every take in ~/bandwagon-takes-out/takes/ (catalog.json there), the album masters and any file named in --film-sources
(a JSON map of song id to the file the film's audio was joined from, so a film gap can be traced to its take).
Writes DIR/gaps.json (every gap with its measurements) and DIR/takes-gaps.md. Read-only on the audio.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bwvote import gaps as G  # noqa: E402

TOWER = Path.home() / "band-wagon-tower"
TAKES_OUT = Path.home() / "bandwagon-takes-out" / "takes"


def _scan(job):
    os.nice(19)
    name, path, bpm = job
    found, total = G.detect(path)
    rows = []
    pcm = None
    for s, e in found:
        z = G.zone(s, e, total)
        row = {"take": name, "start": round(s, 3), "end": round(e, 3), "len": round(e - s, 3), "zone": z}
        if z == "inside":
            pcm = pcm or G.decode(path)
            row.update(G.classify(pcm, s, e, bpm))
        rows.append(row)
    return name, total, rows


def sources(film_sources=None):
    bpm = {}
    jobs, seen, names = [], set(), set()

    def add(name, path, b=None):
        p = Path(path)
        if not p.exists():
            return
        rp = str(p.resolve())
        if rp in seen:
            return
        seen.add(rp)
        if name in names:
            name = f"{p.parent.name}/{name}"
        names.add(name)
        jobs.append((name, str(p), b if b is not None else bpm.get(p.stem)))

    for cat_path in (TOWER / "audio" / "takes" / "catalog.json", TAKES_OUT / "catalog.json"):
        if cat_path.exists():
            for c in json.loads(cat_path.read_text()):
                if c.get("bpm"):
                    bpm[Path(c["path"]).stem] = c["bpm"]
    for cat_path in (TOWER / "audio" / "takes" / "catalog.json", TAKES_OUT / "catalog.json"):
        if cat_path.exists():
            for c in json.loads(cat_path.read_text()):
                add(c["take"], c["path"], c.get("bpm"))
    for p in sorted((TOWER / "audio").glob("bw-*.mp3")):
        add(p.stem, p)
    for p in sorted((TOWER / "audio" / "takes").glob("*.mp3")):
        if not p.name.startswith("headline-"):
            add(p.stem, p)
    for p in sorted(TAKES_OUT.glob("*/*.mp3")):
        add(p.stem, p)
    for p in sorted((TOWER / "album-masters-1029").glob("*.mp3")):
        add(p.stem, p)
    for path in (film_sources or {}).values():
        add(Path(path).stem, Path(path).expanduser())
    return jobs


def md(results, film_rows, film_ids, path):
    L = ["# Gaps in the takes (0.15 s or longer, under -45 dB, inside the song)", "",
         "Made with `gapscan.py` (`bwvote/gaps.py` holds the method). A gap in the first or last 0.3 s of a file is a lead-in or a tail and is not counted. "
         "Labels are read from the sound itself: **musical stop** = hard cut or short decay with both edges on the music's sixteenth-note grid; **dropout** = cut mid-note "
         "(an edge off the grid, or the beat shifts across the gap); **dip** = sinks and returns slowly; **unclear** = no tempo or no clear grid, needs ears. "
         "Takes with no catalog tempo (the older `bw-*` files) cannot be grid-checked, so their hard cuts show as unclear.", ""]
    inside = {n: [r for r in rows if r["zone"] == "inside"] for n, _, rows in results}
    tot = {n: t for n, t, _ in results}
    def lab(rs):
        c = {}
        for r in rs:
            c[r["label"]] = c.get(r["label"], 0) + 1
        return ", ".join(f"{v} {k}" for k, v in sorted(c.items()))
    def table(names):
        T = ["| take | seconds | gaps | longest s | kinds | at (start+length, s) |", "|---|---|---|---|---|---|"]
        for n in names:
            rs = inside[n]
            at = "; ".join(f"{r['start']:.1f}+{r['len']:.2f}" for r in rs[:12]) + (f"; ... {len(rs) - 12} more" if len(rs) > 12 else "")
            T.append(f"| {n} | {tot[n] or 0:.0f} | {len(rs)} | {max((r['len'] for r in rs), default=0):.2f} | {lab(rs)} | {at} |")
        return T
    film = [n for n in film_ids if n in inside]
    L += [f"## The {len(film)} takes in film-a7", ""] + table(film) + [""]
    clean = sorted(n for n in inside if not inside[n])
    L += [f"## Clean takes: no gap of 0.15 s or more inside ({len(clean)} of {len(inside)})", "", ", ".join(f"{n}{' (in film-a7)' if n in film_ids else ''}" for n in clean), ""]
    dirty = [n for n in sorted(inside) if inside[n] and n not in film]
    L += [f"## Every other take with gaps ({len(dirty)})", ""] + table(dirty) + [""]
    allr = [r for rs in inside.values() for r in rs]
    L += ["## Totals", "", f"- {len(inside)} takes scanned, {len(clean)} clean, {len(inside) - len(clean)} with gaps, {len(allr)} gaps in all ({lab(allr)}).", ""]
    if film_rows is not None:
        L += ["## film-a7 itself (its audio, same filter), by song", "", "| n | song | made from | gaps in the film | the film's gaps (end s + length) | gaps inside that source file | kinds in the source |", "|---|---|---|---|---|---|---|"]
        for n, sid, src, rows, at, tk, kinds in film_rows:
            L.append(f"| {n} | {sid} | {src} | {rows} | {at} | {tk} | {kinds} |")
        L.append("")
    Path(path).write_text("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--film", nargs=2, metavar=("PLAN", "AUDIO"))
    ap.add_argument("--film-sources", help="JSON map of song id to the file the film audio was joined from")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    film_sources = json.loads(Path(a.film_sources).read_text()) if a.film_sources else {}
    jobs = sources(film_sources)
    with ProcessPoolExecutor(a.workers) as pool:
        results = list(pool.map(_scan, jobs))
    (out / "gaps.json").write_text(json.dumps([r for _, _, rows in results for r in rows], indent=1))
    film_rows, film_ids = None, []
    if a.film:
        plan = json.loads(Path(a.film[0]).read_text())
        film_ids = [s["id"] for s in plan["songs"]]
        found, total = G.detect(a.film[1])
        found = G.inside(found, total)
        byt = {n: [r for r in rows if r["zone"] == "inside"] for n, _, rows in results}
        stem_name = {Path(p).resolve(): n for n, p, _ in jobs}
        film_rows = []
        for s in plan["songs"]:
            mine = [(g, h) for g, h in found if s["start"] <= g < s["end"]]
            at = "; ".join(f"{h:.1f}+{h - g:.2f}" for g, h in mine[:10]) + (f"; ... {len(mine) - 10} more" if len(mine) > 10 else "")
            src = film_sources.get(s["id"])
            nm = stem_name.get(Path(src).expanduser().resolve()) if src else s["id"]
            rs = byt.get(nm or s["id"], [])
            kinds = ", ".join(sorted({r["label"] for r in rs})) or "-"
            film_rows.append((s["n"], s["id"], nm or "(not in the film's source list)", len(mine), at or "-", len(rs), kinds))
    if film_rows:
        film_ids = [r[2] for r in film_rows]
    md(results, film_rows, film_ids, out / "takes-gaps.md")
    print(f"scanned {len(results)} files; {sum(1 for _, _, r in results if any(x['zone'] == 'inside' for x in r))} with gaps")


if __name__ == "__main__":
    main()
