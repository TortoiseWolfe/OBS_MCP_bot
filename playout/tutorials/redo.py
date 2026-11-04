"""Render one tutorial episode's content video again from a new script, with short pauses in the narration.

Used for the OpenClaw 2 redo: the script is rewritten (air/redo/episodes/<episode>.md), the narration is made with
playout.tutorials.narration (Edge TTS, long silences cut to 0.30 s) and the pictures come from the FIXED NarratedSegment
source (code panel clipping, contrast and footer fixes). Same steps as render_episode.py, but nothing goes through the live
remotion-renderer service and nothing under ~/clawd-twitch/renders is written:

  1. parse the script; narrate the intro and every section (resumable: a finished mp3 is kept);
  2. props per section with bullet times from the real sentence timings;
  3. one throwaway container renders StreamIntro and all sections, one after another, on the CPU;
  4. each picture gets its narration (aac 48 kHz stereo), then all are joined with loudnorm -16 LUFS -> content-<date>.mp4;
  5. the episode's intro, card and outro bumpers are linked in from the old render folder (titles do not change).

Run from the OBS_MCP_bot worktree, with the lane venv (it has edge-tts):
  python -m playout.tutorials.redo --series ai-dev --episode multi-agent-orchestration
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from playout.tutorials import narration
from playout.tutorials.rerender import FADES, HEAVY, IMAGE, code_col_width, newest

CLAWD = Path.home() / "clawd-twitch"
OUT = CLAWD / "air" / "redo" / "out"
SCRIPTS = CLAWD / "air" / "redo" / "episodes"
OPENCLAW = Path.home() / "repos" / "openclaw"
FIXED_SRC = Path.home() / "repos" / ".worktrees" / "openclaw--tutorials-fix"
BRAND = "ScriptHammer"
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"


def intro_text(title, n_sections, duration_min):
    """What the voice says over the opening intro (same words as render_episode.py)."""
    return (f"Welcome to {title} on {BRAND}! In this episode, we'll cover {n_sections} sections "
            f"over about {duration_min} minutes. Let's get started.")


def frames_for(seconds):
    """Picture length for a narration of `seconds`: the speech plus 30 frames of fade in and 30 of fade out."""
    return math.ceil(seconds * 30) + FADES


def intro_props(title, seconds):
    return {"brand": "scripthammer", "episodeTitle": title, "audioFileName": None, "durationInFrames": frames_for(seconds)}


def section_props(section, total, seconds, bullet_timings, parse_mod):
    return {
        "brand": "scripthammer", "sectionTitle": section.title, "sectionNumber": section.number, "totalSections": total,
        "bullets": [parse_mod.parse_bullet_parts(b) for b in section.bullets],
        "codeBlock": section.code_block, "codeLanguage": section.code_language,
        "codeColumnWidth": code_col_width(section.code_block),
        "audioFileName": None, "durationInFrames": frames_for(seconds), "bulletTimings": bullet_timings,
    }


def render_script(jobs):
    """Shell script run inside the container: [(composition, name)] -> /work/<name>.mp4, skipping finished ones."""
    lines = ["set -e"]
    for comp, name in jobs:
        lines.append(f"[ -s /work/{name}.mp4 ] || npx remotion render src/index.ts {comp} /work/{name}.mp4 "
                     f"--props=/work/props_{name}.json --concurrency=1 --log=error")
    return "\n".join(lines)


def concat_filter(n):
    """filter_complex joining n merged segments, then normalising the loudness of the whole lesson."""
    ins = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    return f"{ins}concat=n={n}:v=1:a=1[v][a_raw];[a_raw]{LOUDNORM}[a]"


def sh(cmd, timeout):
    r = subprocess.run(["nice", "-n", "19", "timeout", str(timeout)] + cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"failed ({r.returncode}): {' '.join(cmd[:3])}\n{r.stderr[-600:]}")
    return r


def make_narration(text, mp3, timing, voice):
    if mp3.exists() and timing.exists():
        return
    narration.main(["--text", text, "--output", str(mp3), "--timing-output", str(timing), "--voice", voice])


def merge(video, mp3, dest):
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(mp3), "-c:v", "copy", "-c:a", "aac", "-ar", "48000",
        "-ac", "2", "-b:a", "128k", "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(dest)], 300)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--episode", required=True)
    ap.add_argument("--voice", default=narration.VOICE)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--scripts", default=str(SCRIPTS))
    ap.add_argument("--mem", default="3g")
    ap.add_argument("--cpus", type=int, default=2)
    ap.add_argument("--narrate-only", action="store_true", help="make the narration and props, render nothing")
    a = ap.parse_args()

    sys.path[:0] = [str(OPENCLAW / "toolkit" / "video"), str(OPENCLAW / "toolkit" / "cron-helpers")]
    import parse_episode as pe  # noqa: PLC0415 - path set just above
    import render_episode as re_  # noqa: PLC0415

    episode = pe.parse_episode((Path(a.scripts) / f"{a.episode}.md").read_text())
    dest_dir = Path(a.out) / a.series / a.episode
    work = dest_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    total = len(episode.sections)

    # 1 + 2: narration and props
    mp3s, props = {}, {}
    text = intro_text(episode.title, total, episode.duration_min)
    make_narration(text, work / "intro.mp3", work / "intro.timing.json", a.voice)
    mp3s["intro"] = work / "intro.mp3"
    props["intro"] = intro_props(episode.title, narration.probe_duration(mp3s["intro"]))
    jobs = [("StreamIntro", "intro")]
    for s in episode.sections:
        name = f"s{s.number}"
        text = pe.bullets_to_narration(s)
        make_narration(text, work / f"{name}.mp3", work / f"{name}.timing.json", a.voice)
        mp3s[name] = work / f"{name}.mp3"
        sec = narration.probe_duration(mp3s[name])
        timings = re_._map_bullet_timings(s, text, str(work / f"{name}.timing.json"), sec)
        props[name] = section_props(s, total, sec, timings, pe)
        jobs.append(("NarratedSegment", name))
    for name, p in props.items():
        (work / f"props_{name}.json").write_text(json.dumps(p))
    seconds = sum(p["durationInFrames"] for p in props.values()) / 30
    print(f"{a.episode}: {total} sections, {seconds / 60:.1f} min of picture", flush=True)
    if a.narrate_only:
        return 0

    # 3: render in one container
    cmd = [str(HEAVY), "--mem", a.mem, "--cpus", str(a.cpus), "--timeout", "3000", "--", "docker", "run", "--rm",
           "-v", f"{FIXED_SRC / 'remotion' / 'src'}:/app/src:ro", "-v", f"{work}:/work", "--entrypoint", "bash", IMAGE,
           "-c", render_script(jobs)]
    rc = subprocess.run(["nice", "-n", "19"] + cmd).returncode
    if rc:
        raise SystemExit(f"render failed, exit {rc}")

    # 4: audio under each picture, then join
    merged = []
    for _, name in jobs:
        out = work / f"m_{name}.mp4"
        merge(work / f"{name}.mp4", mp3s[name], out)
        merged.append(out)
    stamp = date.today().strftime("%Y%m%d")
    final = dest_dir / f"content-{stamp}.mp4"
    tmp = dest_dir / f"content-{stamp}.tmp.mp4"
    inputs = [x for m in merged for x in ("-i", str(m))]
    sh(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", concat_filter(len(merged)), "-map", "[v]",
        "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-b:a", "128k", "-movflags", "+faststart", str(tmp)], 1800)
    tmp.replace(final)

    # 5: bumpers
    old_dir = CLAWD / "renders" / a.series / a.episode
    for kind in ("intro", "card", "outro"):
        src = newest(old_dir, kind)
        if src and not (dest_dir / src.name).exists():
            (dest_dir / src.name).symlink_to(src)
    shutil.rmtree(work)
    print("wrote", final, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
