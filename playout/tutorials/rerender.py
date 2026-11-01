"""Re-render the picture of one tutorial episode's content video with the fixed NarratedSegment, to prove a code fix
before any big re-render. Nothing under ~/clawd-twitch/renders, episodes or episodes.json is written.

What it does, for one episode:
  1. Reads the episode script (~/clawd-twitch/episodes/<episode>.md) with the openclaw repo's own parser.
  2. Finds where each section starts in the OLD content video from the dark dip of its 1 s fade, so each new section
     lasts exactly as long as the old one and the old narration audio still lines up.
  3. Writes one props file per section, as render_episode.py does. Bullet timings are ESTIMATED from where each bullet
     sits in the narration text (the real run uses the text-to-speech word timings, which we do not have here).
  4. Renders the sections in one throwaway Docker container (CPU only, memory capped, one at a time) from the fixed source.
  5. Joins the new pictures, puts the ORIGINAL content audio under them, and writes content-new.mp4.
Intro, card and outro are symlinks to the originals, so the review tool can read the folder as an episode.

Run from the OBS_MCP_bot worktree:  python -m playout.tutorials.rerender --series mongodb --episode mongodb-schema-design
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

CLAWD = Path.home() / "clawd-twitch"
OUT = CLAWD / "air" / "rerender"
HEAVY = Path.home() / ".claude" / "scripts" / "docker-heavy.sh"
FPS = 30
FADES = 60  # 30 frames in, 30 out, added to the narration by render_episode.py
IMAGE = "openclaw-remotion-renderer:latest"


def newest(folder, kind):
    c = sorted(folder.glob(f"{kind}-*.mp4"))
    return c[-1] if c else None


def section_frames(video, n_sections):
    """(head frames, frames of each section). The content video opens with a narrated intro; after it each section
    changes the "Section n of m" header in the top-left corner in one jump (then the header fades in). The first big
    jump of each burst of change is the section start."""
    import numpy as np  # noqa: PLC0415 - only this check needs it
    w, h = 360, 36
    cmd = ["nice", "-n", "19", "timeout", "600", "ffmpeg", "-v", "error", "-i", str(video), "-an", "-vf",
           f"crop={w}:{h}:0:0,format=gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)
    d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
    jumps = [int(i) + 1 for i in np.where(d > 8)[0]]
    starts = []
    for j in jumps:
        if not starts or j - starts[-1] > 60:
            starts.append(j)
    if len(starts) != n_sections:
        raise SystemExit(f"found {len(starts)} header jumps {starts}, the script has {n_sections} sections")
    bounds = starts + [len(a)]
    return starts[0], [bounds[k + 1] - bounds[k] for k in range(n_sections)], starts


def bullet_timings(offsets, narration_len, narration_frames):
    """Estimated frame at which each bullet appears: its place in the narration text, 0.5 s ahead of the voice."""
    if not offsets:
        return []
    if len(offsets) == 1:
        return [1]
    return [max(1, round(o / max(narration_len, 1) * narration_frames) - 15) for o in offsets]


def build_props(episode, durations, parse_mod):
    props = []
    total = len(episode.sections)
    for s, frames in zip(episode.sections, durations):
        narration = parse_mod.bullets_to_narration(s)
        offsets = parse_mod.get_bullet_char_offsets(s)
        props.append({
            "brand": "scripthammer", "sectionTitle": s.title, "sectionNumber": s.number, "totalSections": total,
            "bullets": [parse_mod.parse_bullet_parts(b) for b in s.bullets],
            "codeBlock": s.code_block, "codeLanguage": s.code_language,
            "codeColumnWidth": code_col_width(s.code_block),
            "audioFileName": None, "durationInFrames": frames,
            "bulletTimings": bullet_timings(offsets, len(narration), frames - FADES),
        })
    return props


def code_col_width(code_block):
    """Same rule as render_episode.py _calc_code_column_width (longest line plus line-number gutter, 22 px mono at
    0.6 ratio, plus panel padding and a 14 px safety, capped at half the width)."""
    if not code_block:
        return 0
    shown = code_block.split("\n")[:14]
    longest = max((len(line) for line in shown), default=0)
    gutter = len(str(len(shown))) + 1 + 1.5
    return min(int((longest + gutter) * 22 * 0.6) + 50 + 14, int((1920 - 120) * 0.50))


def render_sections(src, work, props, mem, cpus):
    """One throwaway container renders every section, one after another, on the CPU."""
    for i, p in enumerate(props, 1):
        (work / f"props_{i}.json").write_text(json.dumps(p))
    script = "set -e\n" + "\n".join(
        f"[ -s /work/seg_{i}.mp4 ] || npx remotion render src/index.ts NarratedSegment /work/seg_{i}.mp4 "
        f"--props=/work/props_{i}.json --concurrency=1 --log=error" for i in range(1, len(props) + 1))
    cmd = [str(HEAVY), "--mem", mem, "--cpus", str(cpus), "--timeout", "3000", "--", "docker", "run", "--rm",
           "-v", f"{src}:/app/src:ro", "-v", f"{work}:/work", "--entrypoint", "bash", IMAGE, "-c", script]
    return subprocess.run(["nice", "-n", "19"] + cmd).returncode


def join(work, n, old_content, dest, head):
    """The old opening intro (first `head` frames, unchanged) + the n new sections, with the original audio."""
    inputs = ["-i", str(old_content)]
    parts = "[0:v]trim=end_frame=%d,setpts=PTS-STARTPTS[h]" % head + ";[h]"
    for i in range(1, n + 1):
        inputs += ["-i", str(work / f"seg_{i}.mp4")]
        parts += f"[{i}:v]"
    fc = f"{parts}concat=n={n + 1}:v=1:a=0,fps={FPS},format=yuv420p[v]"
    cmd = ["nice", "-n", "19", "timeout", "1200", "ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc,
           "-map", "[v]", "-map", "0:a:0", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy",
           "-movflags", "+faststart", str(dest)]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--episode", required=True)
    ap.add_argument("--openclaw", default=str(Path.home() / "repos/.worktrees/openclaw--tutorials-fix"))
    ap.add_argument("--mem", default="3g")
    ap.add_argument("--cpus", type=int, default=2)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--out", default=str(OUT), help="output root; use a new folder for each run instead of deleting an old one")
    a = ap.parse_args()
    oc = Path(a.openclaw)
    sys.path.insert(0, str(oc / "toolkit" / "cron-helpers"))
    import parse_episode as pe  # noqa: PLC0415 - path set just above

    old_dir = CLAWD / "renders" / a.series / a.episode
    old = newest(old_dir, "content")
    episode = pe.parse_episode((CLAWD / "episodes" / f"{a.episode}.md").read_text())
    dest_dir = Path(a.out) / a.series / a.episode
    work = dest_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    head, frames, cuts = section_frames(old, len(episode.sections))
    props = build_props(episode, frames, pe)
    plan = {"episode": a.episode, "old_content": str(old), "head_frames": head, "section_frames": frames, "cuts": cuts,
            "bullet_timings": "estimated from narration text position, not from word timing"}
    (dest_dir / "plan.json").write_text(json.dumps(plan, indent=1))
    print(json.dumps(plan))
    if a.plan_only:
        return 0
    rc = render_sections(oc / "remotion" / "src", work, props, a.mem, a.cpus)
    if rc:
        raise SystemExit(f"render failed, exit {rc}")
    new = dest_dir / f"content-{old.stem.split('-')[1]}.mp4"  # same date stamp, so the review tool finds it
    join(work, len(props), old, new, head)
    for kind in ("intro", "card", "outro"):
        src = newest(old_dir, kind)
        if src and not (dest_dir / src.name).exists():
            (dest_dir / src.name).symlink_to(src)
    shutil.rmtree(work)
    print("wrote", new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
